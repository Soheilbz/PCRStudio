#!/usr/bin/env python3
"""Build a privacy-conscious public CURRENT release-evidence summary.

Raw Linux host logs remain operator evidence in `.local/`. The public sidecar records
manifest-bound outcomes, commands/selectors, exit codes and cryptographic hashes
without publishing host names, workstation paths or raw logs.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def sha(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()
def evidence_index(doc:dict)->list[dict]:
    rows=[]
    for kind,key in [('module','modules'),('scenario','integration_scenarios')]:
        for ident,row in sorted((doc.get(key) or {}).items()):
            ev=(row or {}).get('evidence') or {}
            rows.append({
                'kind':kind,'id':ident,'status':(row or {}).get('status'),
                'evidence_path':ev.get('path'),'evidence_sha256':ev.get('sha256'),
                'command':ev.get('command'),'test_selector':ev.get('test_selector'),
                'exit_code':ev.get('exit_code')
            })
    return rows
def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--qualification',type=Path,required=True)
    ap.add_argument('--acceptance',type=Path,required=True)
    ap.add_argument('--scientific-snapshot',type=Path,required=True)
    ap.add_argument('--performance',type=Path,required=True)
    ap.add_argument('--capacity',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args()
    q=json.loads(a.qualification.read_text(encoding='utf-8'))
    ac=json.loads(a.acceptance.read_text(encoding='utf-8'))
    sci=json.loads(a.scientific_snapshot.read_text(encoding='utf-8'))
    perf=json.loads(a.performance.read_text(encoding='utf-8'))
    cap=json.loads(a.capacity.read_text(encoding='utf-8'))
    probes={}
    for name,row in sorted((perf.get('probes') or {}).items()):
        probes[name]={k:v for k,v in row.items() if k in {'iterations','exit_codes','wall_ms','peak_rss_bytes'}}
    payload={
      'schema_version':'1.0.0',
      'purpose':'Public-safe manifest-bound CURRENT release evidence summary; raw host logs are intentionally not distributed.',
      'qualification':{
        'overall':q.get('overall'),
        'source_identity':q.get('source_identity'),
        'options':q.get('options'),
        'steps':[{'name':x.get('name'),'status':x.get('status'),'seconds':x.get('seconds')} for x in q.get('steps',[])],
        'sha256':sha(a.qualification),
      },
      'functional_acceptance':{
        'release_id':ac.get('release_id'),'release_class':ac.get('release_class'),
        'source_manifest':ac.get('source_manifest'),'source_sha256':ac.get('source_sha256'),
        'rows':evidence_index(ac),'results_sha256':sha(a.acceptance),
      },
      'scientific_toolchain':{'status':sci.get('status'),'required_features':sci.get('required_features'),'toolchain':sci.get('toolchain'),'sha256':sha(a.scientific_snapshot)},
      'performance_measurements':{'platform':perf.get('platform'),'probes':probes,'sha256':sha(a.performance),'budgets':'measurement-only; no universal performance budget invented'},
      'capacity_measurement':{**{k:cap.get(k) for k in ('requests','concurrency','elapsedMs','requestsPerSecond','statusCounts','p50Ms','p95Ms','p99Ms')},'sha256':sha(a.capacity)},
      'signature_status':'unsigned-public-source; apply operator/CI signature with release signing scripts when a signing identity is available',
    }
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(a.output)
    return 0
if __name__=='__main__': raise SystemExit(main())
