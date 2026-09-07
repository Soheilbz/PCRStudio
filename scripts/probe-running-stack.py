#!/usr/bin/env python3
"""Probe a running local/VM PCRStudio stack without mutating it."""
import argparse,json,urllib.error,urllib.request
p=argparse.ArgumentParser(); p.add_argument('--api',default='http://127.0.0.1:8080'); p.add_argument('--web',default='http://127.0.0.1:3000'); a=p.parse_args()
def get(url,allowed=(200,)):
 try:
  with urllib.request.urlopen(url,timeout=10) as r: code=r.status; body=r.read(65536).decode('utf-8','replace')
 except urllib.error.HTTPError as e: code=e.code; body=e.read(65536).decode('utf-8','replace')
 if code not in allowed: raise SystemExit(f'{url}: HTTP {code}, expected {allowed}')
 return code,body
for path in ('/health','/ready'):
 code,body=get(a.api+path); print(path,code,body[:300])
code,body=get(a.api+'/ready/scientific',(200,503)); print('/ready/scientific',code,body[:500])
code,_=get(a.web+'/'); print('web /',code)
print('Running-stack probe PASS')
