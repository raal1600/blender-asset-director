"""Reproducible offline checks; no Blender/network operation is implied."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--offline',action='store_true',help='Explicit reminder: this runner only runs offline checks');a=p.parse_args()
env=dict(os.environ);env['PYTHONPATH']=str(ROOT/'src')
checks=[]
for name,cmd in [('unit',[sys.executable,'-m','unittest','discover','-s','tests','-v']),('installer',[sys.executable,'tools/install_skill.py','--self-test'])]:
    result=subprocess.run(cmd,cwd=ROOT,env=env,text=True,capture_output=True)
    print(result.stdout,end='');print(result.stderr,end='',file=sys.stderr)
    checks.append({'name':name,'status':'PASS' if result.returncode==0 else 'FAIL','exit_code':result.returncode})
print(json.dumps({'status':'PASS' if all(c['status']=='PASS' for c in checks) else 'FAIL','checks':checks,'headless_blender':'NOT_RUN','live_providers':'NOT_RUN','user_scene':'NOT_RUN'}))
raise SystemExit(0 if all(c['status']=='PASS' for c in checks) else 1)
