#!/usr/bin/env python3
"""Linux-native LAMP high-risk qualification slice."""
from pathlib import Path
import os,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
if not sys.platform.startswith('linux'): raise SystemExit('LAMP qualification is Linux-only')
py=ROOT/'tools/.venv/bin/python'
if not py.is_file(): raise SystemExit('tools/.venv is required')
env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1'}
cmd=[str(py),'-B','-m','pytest','-q','-p','no:cacheprovider','tools/tests/test_loop_set.py','tools/tests/test_lamp_geometry.py','-k','lamp','--basetemp',str(ROOT/'.local/tmp/lamp-linux-qualification')]
subprocess.run(cmd,cwd=ROOT,env=env,check=True)
print('LAMP Linux qualification PASS')
