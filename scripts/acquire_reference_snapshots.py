"""Read-only repository acquisition for the existing 47-entry audit map.

Does not execute repository code, install dependencies, recurse submodules, or
modify existing checkouts. Missing repos use parent gitlink pins where present.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
import configparser
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
evidence=ROOT/'.evidence/reaudit'
inventory=json.loads((evidence/'a066-reference-inventory.json').read_text(encoding='utf8'))
parent=Path(next(r['local'] for r in inventory if r['id']=='C01'))
env=dict(os.environ,GIT_TERMINAL_PROMPT='0',GCM_INTERACTIVE='never')
def git(path,*args):
    result=subprocess.run(['git','-C',str(path),*args],capture_output=True,text=True,encoding='utf8',errors='replace',env=env,timeout=150)
    if result.returncode: raise RuntimeError(result.stderr.strip()[-1600:])
    return result.stdout.strip()
config=configparser.ConfigParser(); config.read(parent/'.gitmodules',encoding='utf8')
tree={line.split('\t',1)[1]:line.split()[2] for line in git(parent,'ls-tree','-r','HEAD').splitlines() if line.startswith('160000')}
pins={config[s]['url']:tree.get(config[s]['path']) for s in config.sections()}
base=evidence/'references/a066'; base.mkdir(parents=True,exist_ok=True)
def acquire(row):
    result=dict(row,parent_pin=pins.get(row['url']),parent_head=git(parent,'rev-parse','HEAD'),checked_at=datetime.now(timezone.utc).isoformat())
    if row['local']:
        result['status']='existing_preserved'; return result
    if not re.fullmatch(r'[a-zA-Z0-9_.-]+',row['name']) or not row['url'].startswith('https://github.com/uengine-oss/'):
        raise ValueError('unexpected map path or remote')
    dest=base/row['name']
    if dest.exists():
        result.update(status='existing_destination_not_modified',destination=str(dest)); return result
    dest.mkdir()
    try:
        git(dest,'init','--quiet'); git(dest,'remote','add','origin',row['url'])
        target=result['parent_pin'] or 'HEAD'
        git(dest,'fetch','--quiet','--depth=1','--filter=blob:none','origin',target)
        git(dest,'checkout','--quiet','--detach','FETCH_HEAD')
        result.update(status='acquired',local=str(dest),head=git(dest,'rev-parse','HEAD'),requested_revision=target,
                      tracked_files=len(git(dest,'ls-files').splitlines()))
    except Exception as exc:
        result.update(status='acquisition_failed',error=str(exc),destination=str(dest))
    return result
results=[]
def save():
    (evidence/'a066-acquisition.json').write_text(json.dumps(sorted(results,key=lambda r:r['id']),ensure_ascii=False,indent=2),encoding='utf8')
with ThreadPoolExecutor(max_workers=4) as pool:
    for task in as_completed([pool.submit(acquire,r) for r in inventory]):
        row=task.result(); results.append(row); save()
        print(row['id'],row['name'],row['status'],(row.get('head') or '')[:12],flush=True)
print('total',len(results),'acquired',sum(r['status']=='acquired' for r in results),'failed',sum(r['status']=='acquisition_failed' for r in results),flush=True)
