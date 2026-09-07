#!/usr/bin/env python3
import argparse
from pathlib import Path
from acceptance_common import *
p=argparse.ArgumentParser(); p.add_argument('scenario_id'); p.add_argument('evidence_path'); p.add_argument('--command',required=True); p.add_argument('--test-selector',required=True); p.add_argument('--results',default=str(DEFAULT_RESULTS)); p.add_argument('--note',action='append',default=[]); a=p.parse_args()
path=Path(a.results); doc=load(path); assert_bound(doc)
canonical={x['id'] for x in load(ROOT/'knowledge/runtime/linux-integration-scenarios.json')['scenarios']}
if a.scenario_id not in canonical or a.scenario_id not in doc['integration_scenarios']: raise SystemExit(f'Unknown scenario id: {a.scenario_id}')
row=doc['integration_scenarios'][a.scenario_id]; row.update(status='pass',evidence=evidence(Path(a.evidence_path),a.command,a.test_selector),notes=a.note); doc.update(executed_at=now(),host=host()); save(path,doc)
print(f'Recorded Linux integration acceptance: {a.scenario_id}')
