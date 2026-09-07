#!/usr/bin/env python3
"""Environment-independent source qualification for Generation 1 foundation.

Native Rust compilation, dependency-backed Web tests, Primer3/ViennaRNA and the
Linux native/scientific executable qualification is intentionally a separate gate. This
script proves what a source-only release builder can prove without fabricating
those results.
"""
from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import argparse
import atexit
import ast
import json
import os
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

from release_utils import SKIP_PARTS, load_release_identity, source_files, write_json
from source_generators import CURRENT_STATIC_GENERATOR, SOURCE_GENERATORS

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'release/current/SOURCE-QUALIFICATION.json'


def run(name:str, argv:list[str], *, env:dict[str,str]|None=None, timeout_seconds:int=120) -> dict[str,object]:
    try:
        proc=subprocess.run(argv,cwd=ROOT,text=True,capture_output=True,env=env,timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        stdout=(exc.stdout or '') if isinstance(exc.stdout,str) else (exc.stdout or b'').decode(errors='replace')
        stderr=(exc.stderr or '') if isinstance(exc.stderr,str) else (exc.stderr or b'').decode(errors='replace')
        raise SystemExit(f"{name} TIMED OUT after {timeout_seconds}s\n{stdout}\n{stderr}") from exc
    if proc.returncode:
        raise SystemExit(f"{name} FAILED ({proc.returncode})\n{proc.stdout}\n{proc.stderr}")
    print(f"QUALIFY {name}=PASS",flush=True)
    return {'name':name,'status':'PASS','stdout':proc.stdout.strip()[-3000:]}


def parse_sources()->dict[str,int]:
    counts={'python':0,'json':0,'toml':0}
    for rel,path in source_files(ROOT).items():
        suffix=path.suffix.lower()
        try:
            if suffix=='.py': ast.parse(path.read_text(encoding='utf-8'),filename=rel); counts['python']+=1
            elif suffix=='.json': json.loads(path.read_text(encoding='utf-8')); counts['json']+=1
            elif suffix=='.toml': tomllib.loads(path.read_text(encoding='utf-8')); counts['toml']+=1
        except Exception as exc:
            raise SystemExit(f'parse failure {rel}: {exc}') from exc
    return counts


def parse_typescript_syntax()->int:
    """Parse every TS/TSX source with TypeScript without emitting JavaScript.

    Full type checking/building belongs to the dependency-backed Web CI gate.
    A source-only qualifier only needs deterministic syntax validation; calling
    ``transpileModule`` separately for hundreds of files is both much slower
    and semantically misleading because it is not a project type-check.
    """
    files=[rel for rel,path in source_files(ROOT).items() if path.suffix.lower() in {'.ts','.tsx'}]
    node_script=r'''
const fs=require('fs'); const path=require('path'); const root=process.argv[1];
const ts=require(path.join(root,'web/node_modules/typescript'));
const files=JSON.parse(fs.readFileSync(0,'utf8')); let errors=[];
for(const rel of files){ const text=fs.readFileSync(root+'/'+rel,'utf8');
  const kind=rel.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS;
  const sf=ts.createSourceFile(rel,text,ts.ScriptTarget.ES2022,true,kind);
  for(const d of sf.parseDiagnostics||[]){ if(d.category===ts.DiagnosticCategory.Error){
    errors.push(rel+': '+ts.flattenDiagnosticMessageText(d.messageText,' '));
  }}
}
if(errors.length){ console.error(errors.slice(0,100).join('\n')); process.exit(1); }
console.log(files.length);
'''
    proc=subprocess.run(['node','-e',node_script,str(ROOT)],input=json.dumps(files),text=True,capture_output=True,cwd=ROOT)
    if proc.returncode: raise SystemExit(f'TS/TSX syntax parse failed:\n{proc.stderr}')
    return int(proc.stdout.strip())


def hygiene()->dict[str,int]:
    symlinks=[]; cases={}; collisions=[]; caches=[]
    for path in ROOT.rglob('*'):
        rel=path.relative_to(ROOT)
        if any(part in SKIP_PARTS for part in rel.parts):
            if any(part in {'__pycache__','.pytest_cache','.ruff_cache','.next','node_modules','target'} for part in rel.parts): caches.append(rel.as_posix())
            continue
        if path.is_symlink(): symlinks.append(rel.as_posix())
        folded=rel.as_posix().casefold()
        if folded in cases and cases[folded]!=rel.as_posix(): collisions.append((cases[folded],rel.as_posix()))
        cases[folded]=rel.as_posix()
    if symlinks: raise SystemExit(f'symlinks forbidden: {symlinks[:20]}')
    if collisions: raise SystemExit(f'case collisions: {collisions[:20]}')
    # Cached build/test directories must not exist anywhere in a release tree.
    actual_caches=[
        p.relative_to(ROOT).as_posix()
        for p in ROOT.rglob('*')
        if not any(part in SKIP_PARTS for part in p.relative_to(ROOT).parts)
        and any(part in {'__pycache__','.pytest_cache','.ruff_cache','.next','node_modules','target'} for part in p.relative_to(ROOT).parts)
    ]
    if actual_caches: raise SystemExit(f'cache/build residue present: {actual_caches[:30]}')
    return {'symlinks':0,'case_collisions':0,'cache_residue':0}


def supply_chain()->dict[str,int]:
    image_refs=[]
    compose_paths=[ROOT/'compose.yaml',*sorted((ROOT/'docker').glob('*.yaml'))]
    for path in compose_paths:
        image_refs += re.findall(r'(?m)^\s*image:\s*([^\s#]+)',path.read_text(encoding='utf-8'))
    for path in sorted((ROOT/'.github/workflows').glob('*.yml')):
        image_refs += re.findall(r'(?m)^\s*image:\s*([^\s#]+)',path.read_text(encoding='utf-8'))
    for rel in ('docker/api.Dockerfile','docker/web.Dockerfile'):
        text=(ROOT/rel).read_text(encoding='utf-8')
        aliases=set()
        for match in re.finditer(r'(?mi)^FROM\s+([^\s]+)(?:\s+AS\s+([^\s]+))?',text):
            ref=match.group(1); alias=match.group(2)
            if ref not in aliases: image_refs.append(ref)
            if alias: aliases.add(alias)
    # Project-built images are outputs of this source tree rather than
    # external supply-chain inputs. Their source/build binding is audited
    # separately; every external base/service image remains digest-pinned.
    local_project_images={
        'pcrstudio-api:${PCRSTUDIO_IMAGE_TAG:-local}',
        'pcrstudio-runner:${PCRSTUDIO_IMAGE_TAG:-local}',
        'pcrstudio-migrate:${PCRSTUDIO_IMAGE_TAG:-local}',
    }
    unpinned=[ref for ref in image_refs if ref not in local_project_images and not re.search(r'@sha256:[0-9a-f]{64}$',ref)]
    if unpinned: raise SystemExit(f'unpinned external container image(s): {unpinned}')
    action_refs=[]
    for path in (ROOT/'.github/workflows').glob('*.yml'):
        action_refs += re.findall(r'(?m)^\s*-?\s*uses:\s*([^\s#]+)',path.read_text(encoding='utf-8'))
    mutable=[ref for ref in action_refs if not re.search(r'@[0-9a-f]{40}$',ref)]
    if mutable: raise SystemExit(f'mutable GitHub Action ref(s): {mutable}')
    return {'container_images_pinned':len(image_refs),'github_actions_sha_pinned':len(action_refs)}


def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--output',type=Path,default=OUT); ap.add_argument('--no-write',action='store_true',help='Run qualification without modifying the source tree.'); args=ap.parse_args()
    env=os.environ.copy(); env['PYTHONDONTWRITEBYTECODE']='1'; env['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'; env['PYTHONPATH']=str(ROOT/'tools/src')+(os.pathsep+env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
    tmp_root=ROOT/'.local/tmp/source-qualification'
    if tmp_root.exists(): shutil.rmtree(tmp_root,ignore_errors=True)
    tmp_root.mkdir(parents=True,exist_ok=True)
    def cleanup_tmp() -> None:
        shutil.rmtree(tmp_root, ignore_errors=True)
        for parent in (tmp_root.parent, tmp_root.parent.parent):
            try:
                parent.rmdir()
            except OSError:
                pass
    atexit.register(cleanup_tmp)
    pytest_cache=tmp_root/'pytest-cache'
    # Source qualification is normally launched by the project-local Linux
    # preparation flow.  Prefer its virtualenv so a clean machine does not
    # accidentally depend on a globally installed pytest (or on the Python
    # distribution's package selection).
    test_python = ROOT/'tools/.venv/bin/python'
    if not test_python.is_file():
        test_python = Path(sys.executable)
    gates=[]
    for gate_name, script in SOURCE_GENERATORS:
        gates.append(run(gate_name, [sys.executable, f"scripts/{script}", "--check"], env=env))
    current_static_gate, current_static_script = CURRENT_STATIC_GENERATOR
    gates.append(
        run(
            current_static_gate,
            [sys.executable, f"scripts/{current_static_script}", "--check"],
            env=env,
        )
    )
    gates.append(run('canonical-static-audit',[sys.executable,'scripts/audit-source.py'],env=env))
    gates.append(run('high-confidence-secret-scan',[sys.executable,'scripts/scan-secrets.py'],env=env))
    gates.append(run('linux-bootstrap-source-regression',[sys.executable,'scripts/check-linux-bootstrap.py'],env=env))
    gates.append(run('flanking-web-numeric-executable-contract',['node','scripts/check-flanking-web-numeric.js'],env=env))
    gates.append(run('lamp-web-numeric-executable-contract',['node','scripts/check-lamp-web-numeric.js'],env=env))
    gates.append(run('lamp-rust-differential-source-contract',[sys.executable,'scripts/check-lamp-rust-differential.py'],env=env))
    gates.append(run('engine-web-differential-contract',['node','scripts/check-engine-web-contract.js'],env=env))
    gates.append(run('evidence-import-executable-contract',['node','scripts/check-evidence-import.js'],env=env))
    gates.append(run('flanking-rust-source-boundary',[sys.executable,'scripts/check-flanking-rust-boundary.py'],env=env))
    gates.append(run('focused-source-regression-tests',[str(test_python),'-B','-m','pytest','-q','--basetemp',str(tmp_root/'pytest'),'-o',f'cache_dir={pytest_cache}',
      'tools/tests/test_foundation_contract.py','tools/tests/test_lamp_numeric_recipes.py','tools/tests/test_flanking_numeric_recipes.py',
      'tools/tests/test_flanking_deep_closure.py','tools/tests/test_restriction_workflows.py','tools/tests/test_kasp.py','tools/tests/test_fetch.py','tools/tests/test_process_boundary.py',
      'tools/tests/test_engine_contract_regressions.py','tools/tests/test_engine_authority_contract.py','tools/tests/test_method_fidelity.py'],env=env))
    parsed=parse_sources(); ts_count=parse_typescript_syntax(); clean=hygiene(); supply=supply_chain()
    foundation=json.loads((ROOT/'knowledge/runtime/foundation.generated.json').read_text(encoding='utf-8'))
    identity=load_release_identity(ROOT)
    result={
      'schema_version':'1.2.0','release_id':identity['release_id'],'release_class':identity['release_class'],
      'foundation_release':foundation['foundation_release'],
      'scope':'environment-independent-source-qualification',
      'status':'PASS',
      'gates':gates,
      'parse':{**parsed,'typescript_tsx_syntax_parse':ts_count},
      'hygiene':clean,'supply_chain':supply,
      'native_external_gate':{
        'status':'NOT_ASSERTED_HERE',
        'reason':'Linux native execution is delegated to the explicit host gate; cargo/pnpm/native scientific dependencies are not a source-only claim.',
        'entrypoint':'scripts/run-linux-qualification.py'
      }
    }
    if not args.no_write:
        write_json(args.output,result)
    print(json.dumps({'status':'PASS','parse':result['parse'],'hygiene':clean,'supply_chain':supply},indent=2))
    return 0
if __name__=='__main__': raise SystemExit(main())
