#!/usr/bin/env python3
import argparse
from acceptance_common import bind_template,DEFAULT_RESULTS
p=argparse.ArgumentParser(); p.add_argument('--force',action='store_true'); p.add_argument('--results',default=str(DEFAULT_RESULTS)); a=p.parse_args()
path=bind_template(a.force,__import__('pathlib').Path(a.results)); print(f'Created manifest-bound Linux acceptance evidence record: {path}')
