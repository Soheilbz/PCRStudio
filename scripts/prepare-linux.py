#!/usr/bin/env python3
"""Prepare the CURRENT source tree for canonical Linux qualification."""
from __future__ import annotations
import argparse,os,shutil,subprocess,sys
from pathlib import Path
sys.dont_write_bytecode = True
ROOT=Path(__file__).resolve().parents[1]
def run(*cmd):
 env=os.environ.copy(); env['PYTHONDONTWRITEBYTECODE']='1'
 print('>',*cmd); subprocess.run([str(x) for x in cmd],cwd=ROOT,check=True,env=env)
def req(name):
 if not shutil.which(name): raise SystemExit(f'Required command unavailable: {name}')
def pnpm_cmd():
 direct=shutil.which('pnpm')
 if direct: return [direct]
 corepack=shutil.which('corepack')
 if corepack: return [corepack,'pnpm']
 raise SystemExit('Required package manager unavailable: install pnpm or Node Corepack')

def purge_source_cache_residue():
 # Qualification treats generated Python/test caches as source contamination.
 # Remove only cache directories/files under the project source roots so a
 # previous manual invocation cannot make the next bootstrap non-reproducible.
 # Tests and their helper packages are source too: running pytest locally
 # must not make the next deterministic qualification fail on its caches.
 for root in (ROOT/'tools/src', ROOT/'tools/tests', ROOT/'scripts'):
  if not root.is_dir(): continue
  for path in sorted(root.rglob('__pycache__'), reverse=True):
   if path.is_dir(): shutil.rmtree(path, ignore_errors=True)
  for suffix in ('.pyc', '.pyo'):
   for path in root.rglob(f'*{suffix}'):
    if path.is_file(): path.unlink(missing_ok=True)
def main():
 from source_generators import CURRENT_STATIC_GENERATOR, SOURCE_GENERATORS
 if not sys.platform.startswith('linux'): raise SystemExit('CURRENT preparation is Linux-only')
 p=argparse.ArgumentParser(); p.add_argument('--sync-dependencies',action='store_true'); p.add_argument('--provision-tools',action='store_true'); p.add_argument('--approve-scientific-freeze',action='store_true'); p.add_argument('--pnpm-store-dir'); a=p.parse_args()
 purge_source_cache_residue()
 for _gate_name, script in SOURCE_GENERATORS:
  run(sys.executable,f'scripts/{script}')
 _static_gate, static_script = CURRENT_STATIC_GENERATOR
 run(sys.executable,f'scripts/{static_script}')
 if a.sync_dependencies:
  req('uv'); pnpm=pnpm_cmd(); run('uv','sync','--project','tools','--frozen','--extra','dev','--extra','folding')
  install_cmd=[*pnpm,'install','--frozen-lockfile']
  if a.pnpm_store_dir: install_cmd.extend(['--store-dir',a.pnpm_store_dir])
  run(*install_cmd)
 if a.provision_tools:
  provision_args=[sys.executable,'scripts/provision-tools.py']
  if a.approve_scientific_freeze: provision_args.append('--approve-scientific-freeze')
  run(*provision_args)
  # Reassert the project test environment before source qualification. This
  # also makes a retry safe after a partially completed network provisioning
  # attempt.
  run('uv','sync','--project','tools','--frozen','--extra','dev','--extra','folding')
 # Qualification writes SOURCE-QUALIFICATION.json, which is itself part of the
 # source manifest. Run it before release identity is generated. Then refresh
 # the static report (it records the qualification status) and prove that the
 # converged tree qualifies without another write.
 run(sys.executable,'scripts/qualify-source.py')
 run(sys.executable,'scripts/generate-current-static-audit.py')
 purge_source_cache_residue()
 run(sys.executable,'scripts/qualify-source.py','--no-write')
 # Generated verification artifacts excluded from FILE-MANIFEST have an
 # intentional order: manifests first, then attestation, then SHA256SUMS refresh.
 # This avoids hash cycles while leaving one independently verifiable tree.
 run(sys.executable,'scripts/generate-release-manifests.py','--baseline-manifest','release/baseline/R15-FILE-MANIFEST.json')
 run(sys.executable,'scripts/generate-source-attestation.py')
 run(sys.executable,'scripts/generate-release-manifests.py','--baseline-manifest','release/baseline/R15-FILE-MANIFEST.json')
 run(sys.executable,'scripts/verify-release.py','--root',str(ROOT))
 print('CURRENT Linux preparation complete.')
if __name__=='__main__': main()
