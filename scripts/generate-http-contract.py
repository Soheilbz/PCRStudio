#!/usr/bin/env python3
"""Generate transport-only HTTP contracts from contracts/http-api.toml.

This generator deliberately does not model scientific request/result payloads.
Those remain versioned scientific contracts. HTTP method/path/security/error
shape belongs here so Rust routing, browser paths and OpenAPI cannot drift.
"""
from __future__ import annotations
import argparse, json, re, tomllib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'contracts/http-api.toml'
ALLOWED_METHODS={'GET','POST','PUT','PATCH','DELETE'}
ALLOWED_AUTH={'public','session','operator'}

def load():
    with SRC.open('rb') as f: raw=tomllib.load(f)
    rows=raw.get('endpoint') or []
    seen=set(); operations=set(); out=[]
    for row in rows:
        eid=str(row['id']); method=str(row['method']).upper(); mount=str(row['mount']); local=str(row['local_path']); auth=str(row['auth']); tag=str(row['tag'])
        if not re.fullmatch(r'[a-z][a-z0-9_]*',eid): raise ValueError(f'invalid endpoint id {eid}')
        if eid in seen: raise ValueError(f'duplicate endpoint id {eid}')
        if method not in ALLOWED_METHODS: raise ValueError(f'{eid}: bad method {method}')
        if auth not in ALLOWED_AUTH: raise ValueError(f'{eid}: bad auth {auth}')
        if not local.startswith('/') or (mount and not mount.startswith('/')): raise ValueError(f'{eid}: paths must be absolute fragments')
        full=(mount.rstrip('/')+local) if mount else local
        full=re.sub(r'//+','/',full)
        # A nested Axum router owns `/` as its local fragment, but the stable
        # external URL must be the mount without a trailing slash. Keeping the
        # two forms distinct avoids a browser-side 404 at the collection root.
        if full != '/' and full.endswith('/'):
            full=full[:-1]
        op=(method,full)
        if op in operations: raise ValueError(f'duplicate operation {method} {full}')
        seen.add(eid); operations.add(op)
        out.append({'id':eid,'method':method,'mount':mount,'local_path':local,'api_path':full,'auth':auth,'tag':tag})
    return raw,out

def render_rust(rows):
    lines=['// Generated from contracts/http-api.toml; do not hand-edit.','#![allow(dead_code)]','']
    for r in rows:
        name=r['id'].upper()
        lines.append(f'pub const {name}: &str = {json.dumps(r["local_path"])};')
    return '\n'.join(lines)+'\n'

def render_ts(raw,rows):
    stable=str(raw['stable_prefix'])
    records={r['id']:{'method':r['method'],'path':stable+r['api_path'],'auth':r['auth']} for r in rows if r['api_path'].startswith('/') and r['id'] not in {'health','ready','scientific_ready','operator_diagnostics','operator_metrics'}}
    # Paths outside /api still keep their literal top-level location.
    for r in rows:
        if r['id'] in {'health','ready','scientific_ready','operator_diagnostics','operator_metrics'}:
            records[r['id']]={'method':r['method'],'path':r['api_path'],'auth':r['auth']}
    return ('// Generated from contracts/http-api.toml; do not hand-edit.\n'
            +'export const HTTP_ROUTES = '+json.dumps(records,indent=2,sort_keys=True)+' as const;\n\n'
            +'export type HttpRouteId = keyof typeof HTTP_ROUTES;\n'
            +'export function httpRoute(id: HttpRouteId, params: Record<string, string> = {}): string {\n'
            +'  return HTTP_ROUTES[id].path.replace(/\\{([^}]+)\\}/g, (_match, key: string) => {\n'
            +'    const value = params[key];\n'
            +'    if (value === undefined) throw new Error(`Missing HTTP route parameter: ${key}`);\n'
            +'    return encodeURIComponent(value);\n'
            +'  });\n}\n')

def openapi(raw,rows):
    stable=str(raw['stable_prefix'])
    paths={}
    for r in rows:
        if r['id'] in {'health','ready','scientific_ready','operator_diagnostics','operator_metrics'}:
            path=r['api_path']
        else:
            path=stable+r['api_path']
        op={'operationId':r['id'],'tags':[r['tag']], 'responses':{'200':{'description':'Success'},'default':{'description':'Machine-readable PCRStudio error','content':{'application/json':{'schema':{'$ref':'#/components/schemas/ErrorBody'}}}}}}
        if r['auth']=='session': op['security']=[{'bearerAuth':[]}]
        elif r['auth']=='operator': op['security']=[{'operatorToken':[]}]
        params=[]
        for key in re.findall(r'\{([^}]+)\}',path):
            params.append({'name':key,'in':'path','required':True,'schema':{'type':'string'}})
        if params: op['parameters']=params
        paths.setdefault(path,{})[r['method'].lower()]=op
    return {'openapi':'3.1.0','info':{'title':'PCRStudio HTTP API','version':str(raw['api_version']),'description':'Transport-only contract. Scientific payload schemas are versioned separately.'},'paths':paths,'components':{'securitySchemes':{'bearerAuth':{'type':'http','scheme':'bearer'},'operatorToken':{'type':'apiKey','in':'header','name':'x-pcrstudio-operator-token'}},'schemas':{'ErrorBody':{'type':'object','required':['code','kind','detail','retryable','requestId'],'properties':{'code':{'type':'string'},'kind':{'type':'string'},'detail':{'type':'string'},'fieldPath':{'type':['string','null']},'stage':{'type':['string','null']},'retryable':{'type':'boolean'},'requestId':{'type':'string'}}}}}}

def write(path,text,check):
    p=ROOT/path
    if isinstance(text,dict): text=json.dumps(text,indent=2,sort_keys=True)+'\n'
    if check: return p.is_file() and p.read_text()==text
    p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text,newline='\n'); return True

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--check',action='store_true'); a=ap.parse_args()
    raw,rows=load(); outputs={'crates/pcr-server/src/http_routes.generated.rs':render_rust(rows),'web/src/lib/api/routes.generated.ts':render_ts(raw,rows),'docs/openapi.generated.json':openapi(raw,rows),'contracts/http-api.generated.json':{'schema_version':raw['schema_version'],'api_version':raw['api_version'],'stable_prefix':raw['stable_prefix'],'legacy_alias':raw['legacy_alias'],'endpoints':rows}}
    bad=[p for p,v in outputs.items() if not write(p,v,a.check)]
    if bad:
        print('HTTP_CONTRACT_DRIFT'); print('\n'.join(bad)); return 1
    print(f"HTTP_CONTRACT={'CHECK-PASS' if a.check else 'GENERATED'} endpoints={len(rows)} files={len(outputs)}")
    return 0
if __name__=='__main__': raise SystemExit(main())
