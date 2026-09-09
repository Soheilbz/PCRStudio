#!/usr/bin/env python3
"""Canonical PCRStudio CURRENT Linux qualification orchestrator.

Default mode is a non-mutating source/static qualification suitable for an
offline review environment. ``--full`` additionally requires installed Rust,
Node/pnpm and Python dependencies and executes native build/test gates. Optional
flags add scientific-tool, functional-acceptance and live-stack gates.
"""
from __future__ import annotations
import argparse,hashlib,json,os,platform,shutil,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LOG=ROOT/'.local/logs/linux-qualification-result.json'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(cmd):
 if not shutil.which(cmd): raise SystemExit(f'Full Linux qualification requires command: {cmd}')
def pnpm_cmd():
 direct=shutil.which('pnpm')
 if direct: return [direct]
 corepack=shutil.which('corepack')
 if corepack: return [corepack,'pnpm']
 raise SystemExit('Full Linux qualification requires pnpm or Node Corepack')
def require_version(prefix,name,expected_prefix):
 cp=subprocess.run(prefix+['--version'],cwd=ROOT,text=True,capture_output=True)
 if cp.returncode:
  raise SystemExit(f'Unable to query {name} version: {cp.stderr or cp.stdout}')
 actual=cp.stdout.strip()
 if not actual.startswith(expected_prefix):
  raise SystemExit(f'Full Linux qualification requires {name} {expected_prefix}x; found {actual}')
 return actual
def invoke_step(name,cmd,steps,env=None):
 print(f'\n=== {name} ===\n>',' '.join(map(str,cmd))); t=time.time()
 cp=subprocess.run([str(x) for x in cmd],cwd=ROOT,env=env or os.environ.copy(),text=True,capture_output=True)
 if cp.stdout: print(cp.stdout,end='')
 if cp.stderr: print(cp.stderr,end='',file=sys.stderr)
 steps.append({'name':name,'command':[str(x) for x in cmd],'exit_code':cp.returncode,'duration_seconds':round(time.time()-t,3)})
 if cp.returncode: raise SystemExit(f'Qualification gate failed: {name}')
def source_identity():
 manifest=ROOT/'release/FILE-MANIFEST.json'; runtime=ROOT/'release/RUNTIME-CONTRACT-MANIFEST.json'
 return {'file_manifest_sha256':sha(manifest),'file_manifest_verified':True,'verified_file_count':len(json.loads(manifest.read_text())['files']),'runtime_contract_manifest_sha256':sha(runtime),'source_artifact_identity_binding':'release/FILE-MANIFEST.json','source_identity':'PCRStudio CURRENT Linux source'}
def main():
 if not sys.platform.startswith('linux'): raise SystemExit('CURRENT qualification is Linux-only')
 ap=argparse.ArgumentParser(); ap.add_argument('--full',action='store_true'); ap.add_argument('--build-web',action='store_true'); ap.add_argument('--probe-running-stack',action='store_true'); ap.add_argument('--approve-scientific-environment',action='store_true'); ap.add_argument('--require-olivar',action='store_true'); ap.add_argument('--require-functional-acceptance',action='store_true'); ap.add_argument('--require-scientific-toolchain',action='store_true'); a=ap.parse_args()
 steps=[]; started=datetime.now(timezone.utc).isoformat()
 # Source identity is read before and after; every gate below is non-mutating.
 before=source_identity()
 invoke_step('CURRENT source qualifier (non-mutating verification)',[sys.executable,'scripts/qualify-source.py','--no-write'],steps)
 invoke_step('CURRENT static source audit',[sys.executable,'scripts/audit-source.py'],steps)
 invoke_step('CURRENT foundation generated projection check',[sys.executable,'scripts/generate-foundation-contracts.py','--check'],steps)
 invoke_step('Unified engine authority projection check',[sys.executable,'scripts/generate-engine-authorities.py','--check'],steps)
 invoke_step('Unified engine contract projection check',[sys.executable,'scripts/generate-engine-contracts.py','--check'],steps)
 if a.full:
  for c in ('uv','cargo','rustc','node'): require(c)
  pnpm=pnpm_cmd()
  require_version(['rustc'],'rustc','rustc 1.94.')
  require_version(['node'],'Node.js','v24.')
  require_version(pnpm,'pnpm','11.26.0')
  py=ROOT/'tools/.venv/bin/python'
  if not py.is_file(): raise SystemExit('Full qualification requires tools/.venv/bin/python; run prepare-linux.py --sync-dependencies')
  env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1'}
  invoke_step('Python full test suite',[str(py),'-B','-m','pytest','-q','-p','no:cacheprovider','tools/tests','--basetemp',str(ROOT/'.local/tmp/pytest-linux-qualification')],steps,env)
  invoke_step('Unified engine differential/property contracts',['cargo','test','--locked','-p','pcr-core','--test','engine_differential_contract'],steps)
  invoke_step('Rust workspace tests',['cargo','test','--locked','--workspace'],steps)
  invoke_step('Rust clippy',['cargo','clippy','--locked','--workspace','--all-targets','--','-D','warnings'],steps)
  invoke_step('Web typecheck',[*pnpm,'--filter','web','typecheck'],steps)
  invoke_step('Web lint',[*pnpm,'--filter','web','lint'],steps)
  invoke_step('Web tests',[*pnpm,'--filter','web','test'],steps)
  if a.build_web or a.full: invoke_step('web production build',[*pnpm,'--filter','web','build'],steps)
  invoke_step('Unified engine high-risk acceptance scenarios',[sys.executable,'scripts/run-engine-acceptance.py'],steps)
  invoke_step('LAMP Linux qualification',[sys.executable,'scripts/run-lamp-linux-qualification.py'],steps)
 if a.approve_scientific_environment:
  invoke_step('ApproveScientificEnvironment',[sys.executable,'scripts/provision-tools.py','--approve-scientific-freeze'],steps)
 if a.full or a.require_scientific_toolchain or a.approve_scientific_environment or a.require_olivar:
  scientific_py=ROOT/'tools/.venv/bin/python'
  if not scientific_py.is_file(): scientific_py=Path(sys.executable)
  scientific_output=ROOT/'.local/logs/scientific-toolchain.json'
  cmd=[str(scientific_py),'scripts/check-scientific-toolchain.py','--output',str(scientific_output)]
  if a.require_olivar: cmd += ['--require-feature','olivar']
  invoke_step('CURRENT scientific toolchain identity snapshot',cmd,steps)
 if a.require_olivar:
  envfile=ROOT/'.local/tools/olivar.json'
  if not envfile.is_file(): raise SystemExit('RequireOlivar: configure Olivar with scripts/configure-olivar-linux.py first')
 if a.require_functional_acceptance:
  invoke_step('module functional acceptance evidence',[sys.executable,'scripts/validate-linux-acceptance-results.py'],steps)
 if a.probe_running_stack:
  invoke_step('running-stack health/readiness probe',[sys.executable,'scripts/probe-running-stack.py'],steps)
 after=source_identity()
 if before!=after: raise SystemExit('Source artifact identity changed during non-mutating qualification')
 result={'schema_version':'1.0.0','platform':'linux','architecture':platform.machine(),'started_at':started,'completed_at':datetime.now(timezone.utc).isoformat(),'mode':'full' if a.full else 'source','source_identity':after,'steps':steps,'status':'pass'}
 LOG.parent.mkdir(parents=True,exist_ok=True); LOG.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
 print(f'\nCURRENT Linux qualification PASS ({result["mode"]}). Evidence: {LOG}')
if __name__=='__main__': main()
