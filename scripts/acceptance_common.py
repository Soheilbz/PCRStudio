#!/usr/bin/env python3
"""Linux-native acceptance evidence helpers shared by CURRENT qualification scripts."""
from __future__ import annotations
import hashlib,json,platform,tomllib
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DEFAULT_RESULTS=ROOT/'.local'/'logs'/'linux-acceptance-results.json'

def now(): return datetime.now(timezone.utc).isoformat()
def host(): return platform.node() or 'linux-host'
def sha256(path:Path)->str:
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
 return h.hexdigest()
def release_identity(): return tomllib.loads((ROOT/'release/release.toml').read_text(encoding='utf-8'))
def manifest_binding():
 p=ROOT/'release/FILE-MANIFEST.json'
 if not p.is_file(): raise SystemExit('release/FILE-MANIFEST.json is missing; regenerate release manifests first')
 return 'release/FILE-MANIFEST.json',sha256(p)
def load(path:Path): return json.loads(path.read_text(encoding='utf-8'))
def save(path:Path,doc): path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n',encoding='utf-8')
def ensure_linux():
 import sys
 if not sys.platform.startswith('linux'): raise SystemExit('CURRENT acceptance evidence is Linux-host evidence only')
def bind_template(force=False,path:Path=DEFAULT_RESULTS):
 ensure_linux(); template=ROOT/'knowledge/runtime/linux-acceptance-results.template.json'
 if path.exists() and not force: raise SystemExit(f'Acceptance results already exist: {path}; pass --force to reset')
 doc=load(template); ident=release_identity(); manifest,sha=manifest_binding()
 doc.update(executed_at=now(),host=host(),release_id=ident['release_id'],release_class=ident['release_class'],source_manifest=manifest,source_sha256=sha)
 save(path,doc); return path
def assert_bound(doc):
 ident=release_identity(); manifest,sha=manifest_binding()
 checks={'release_id':ident['release_id'],'release_class':ident['release_class'],'source_manifest':manifest,'source_sha256':sha}
 for k,v in checks.items():
  if doc.get(k)!=v: raise SystemExit(f'Acceptance results are not bound to current {k}: expected {v!r}, got {doc.get(k)!r}')
def evidence(path:Path,command:str,selector:str,exit_code:int=0):
 resolved=path.resolve(); root=ROOT.resolve()
 if root!=resolved and root not in resolved.parents: raise SystemExit('Evidence path must remain inside the PCRStudio work tree')
 if not resolved.is_file(): raise SystemExit(f'Evidence file missing: {resolved}')
 if exit_code!=0: raise SystemExit(f'PASS evidence requires exit_code=0, got {exit_code}')
 return {'path':resolved.relative_to(root).as_posix(),'sha256':sha256(resolved),'command':command.strip(),'test_selector':selector.strip(),'exit_code':0,'executed_at':now()}
