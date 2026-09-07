#!/usr/bin/env python3
import argparse,re
from pathlib import Path
from acceptance_common import *
p=argparse.ArgumentParser(); p.add_argument('--results',default=str(DEFAULT_RESULTS)); a=p.parse_args(); path=Path(a.results); doc=load(path); ensure_linux(); assert_bound(doc)
if doc.get('schema_version')!='1.3.0': raise SystemExit(f"Unsupported Linux acceptance schema: {doc.get('schema_version')}")
modules=set(load(ROOT/'knowledge/runtime/linux-acceptance-matrix.json')['modules']); actual=set(doc.get('modules',{}))
if modules!=actual: raise SystemExit('Acceptance module set must exactly match canonical module matrix')
scenarios={x['id'] for x in load(ROOT/'knowledge/runtime/linux-integration-scenarios.json')['scenarios']}; actual_s=set(doc.get('integration_scenarios',{}))
if scenarios!=actual_s: raise SystemExit('Acceptance integration-scenario set must exactly match canonical matrix')
def check_ev(label,ev):
 if not isinstance(ev,dict): raise SystemExit(f'{label} lacks evidence')
 for k in ('path','sha256','command','test_selector','exit_code'):
  if ev.get(k) in (None,''): raise SystemExit(f'{label} evidence lacks {k}')
 if ev['exit_code']!=0: raise SystemExit(f'{label} evidence exit_code is not zero')
 p=(ROOT/ev['path']).resolve()
 if ROOT.resolve()!=p and ROOT.resolve() not in p.parents: raise SystemExit(f'{label} evidence escapes source tree')
 if not p.is_file() or not re.fullmatch('[0-9a-f]{64}',str(ev['sha256'])) or sha256(p)!=ev['sha256']: raise SystemExit(f'{label} evidence SHA-256 mismatch')
for mid in sorted(modules):
 r=doc['modules'][mid]
 if r.get('status')!='pass' or not all(r.get(k) is True for k in ('happy_path','refusal_paths','strict_mode')): raise SystemExit(f'Module acceptance not fully PASS: {mid}')
 check_ev(f'Module {mid}',r.get('evidence'))
for sid in sorted(scenarios):
 r=doc['integration_scenarios'][sid]
 if r.get('status')!='pass': raise SystemExit(f'Integration scenario not PASS: {sid}')
 check_ev(f'Integration scenario {sid}',r.get('evidence'))
print(f'Linux acceptance PASS and manifest-bound: modules={len(modules)} scenarios={len(scenarios)} source_sha256={doc["source_sha256"]}')
