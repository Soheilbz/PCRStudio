#!/usr/bin/env python3
"""Portable PCRStudio worker/reference performance harness.

The script records measurements; it does not invent pass/fail budgets. Native
budgets are frozen only after the operator records a qualified Linux native baseline.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _rss_bytes(pid: int) -> int | None:
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes
            class PMC(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
                ]
            PROCESS_QUERY_INFORMATION=0x0400; PROCESS_VM_READ=0x0010
            kernel=ctypes.WinDLL("kernel32", use_last_error=True); psapi=ctypes.WinDLL("psapi", use_last_error=True)
            handle=kernel.OpenProcess(PROCESS_QUERY_INFORMATION|PROCESS_VM_READ, False, pid)
            if not handle: return None
            try:
                pmc=PMC(); pmc.cb=ctypes.sizeof(PMC)
                if psapi.GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb): return int(pmc.WorkingSetSize)
            finally: kernel.CloseHandle(handle)
        except Exception:
            return None
    else:
        try:
            status=Path(f"/proc/{pid}/status").read_text(encoding="utf-8")
            for line in status.splitlines():
                if line.startswith("VmRSS:"):
                    return int(line.split()[1])*1024
        except Exception:
            return None
    return None


def run_process(argv: list[str], *, stdin: bytes | None = None, env: dict[str,str] | None = None) -> dict[str, Any]:
    started=time.perf_counter(); proc=subprocess.Popen(argv, stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    peak=0; done=False
    def monitor():
        nonlocal peak
        while not done and proc.poll() is None:
            value=_rss_bytes(proc.pid)
            if value is not None: peak=max(peak,value)
            time.sleep(0.01)
    thread=threading.Thread(target=monitor,daemon=True); thread.start()
    out,err=proc.communicate(stdin); done=True; thread.join(timeout=0.1)
    elapsed=(time.perf_counter()-started)*1000.0
    return {"exit_code":proc.returncode,"wall_ms":round(elapsed,3),"peak_rss_bytes":peak or None,
            "stdout":out.decode("utf-8",errors="replace"),"stderr":err.decode("utf-8",errors="replace")}


def summarize(samples: list[dict[str,Any]]) -> dict[str,Any]:
    walls=[float(row["wall_ms"]) for row in samples]
    rss=[int(row["peak_rss_bytes"]) for row in samples if row.get("peak_rss_bytes")]
    return {"iterations":len(samples),"exit_codes":[row["exit_code"] for row in samples],
            "wall_ms":{"min":min(walls),"median":statistics.median(walls),"max":max(walls)},
            "peak_rss_bytes":{"max":max(rss) if rss else None},"samples":samples}


def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--python',default=os.environ.get('PCR_PYTHON') or os.sys.executable)
    ap.add_argument('--iterations',type=int,default=5); ap.add_argument('--corpus',type=Path)
    ap.add_argument('--output',type=Path,default=ROOT/'release/current/PERFORMANCE-MEASUREMENTS.json')
    args=ap.parse_args(); env=os.environ.copy(); env['PYTHONPATH']=str(ROOT/'tools/src') + (os.pathsep+env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
    probes={
      'python-startup':[args.python,'-c','pass'],
      'foundation-import':[args.python,'-c','import pcr_tools.contract_loader,pcr_tools.numeric_recipe,pcr_tools.ipc'],
      'full-worker-import':[args.python,'-c','import pcr_tools.__main__'],
    }
    result={"schema_version":"1.0.0","purpose":"measurement-only; budgets are frozen from qualified native baselines, never invented by this script",
            "platform":os.name,"python":args.python,"probes":{},"scientific_cases":[]}
    for name,cmd in probes.items():
        rows=[run_process(cmd,env=env) for _ in range(args.iterations)]
        # Output/stderr are unnecessary noise for successful probes; retain a short
        # error sample only when the environment lacks a native dependency.
        for row in rows:
            if row['exit_code']==0: row['stdout']=''; row['stderr']=''
            else: row['stdout']=row['stdout'][:1000]; row['stderr']=row['stderr'][:1000]
        result['probes'][name]=summarize(rows)
    if args.corpus:
        corpus=json.loads(args.corpus.read_text(encoding='utf-8'))
        for case in corpus.get('cases',[]):
            command=str(case['command']); envelope=case['envelope']; payload=(json.dumps(envelope,separators=(',',':'))+'\n').encode()
            rows=[run_process([args.python,'-m','pcr_tools',command],stdin=payload,env=env) for _ in range(args.iterations)]
            parsed=[]
            for row in rows:
                try:
                    wire=json.loads(row['stdout']); telemetry=((wire.get('payload') or {}).get('execution_telemetry') if isinstance(wire,dict) else None)
                except Exception: telemetry=None
                parsed.append({**row,'telemetry':telemetry,'stdout':row['stdout'][:2000] if row['exit_code'] else ''})
            result['scientific_cases'].append({'id':case['id'],'module':case.get('module'),'command':command,'summary':summarize(parsed)})
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({k:v['wall_ms'] for k,v in result['probes'].items()},indent=2))
    return 0
if __name__=='__main__': raise SystemExit(main())
