#!/usr/bin/env python3
import argparse
from pathlib import Path
from acceptance_common import *
p=argparse.ArgumentParser(); p.add_argument('module_id'); p.add_argument('evidence_path'); p.add_argument('--command',required=True); p.add_argument('--test-selector',required=True); p.add_argument('--results',default=str(DEFAULT_RESULTS)); p.add_argument('--note',action='append',default=[]); a=p.parse_args()
path=Path(a.results); doc=load(path); assert_bound(doc)
if a.module_id not in doc['modules']: raise SystemExit(f'Unknown module id: {a.module_id}')
row=doc['modules'][a.module_id]; row.update(status='pass',happy_path=True,refusal_paths=True,strict_mode=True,evidence=evidence(Path(a.evidence_path),a.command,a.test_selector),notes=a.note); doc.update(executed_at=now(),host=host()); save(path,doc)
print(f'Recorded Linux module acceptance: {a.module_id}')
