"""Keep a long local integration run independent of an interactive tool handle."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True)
    ap.add_argument('--worker',action='store_true')
    # A129: the current selection contract (docs/sessions/19 step 3) reviews the current forecast before approving, so the
    # review is the default; `--no-fresh-review` reproduces the diagnosis-time approval that the approval check refuses.
    ap.add_argument('--fresh-review',dest='fresh_review',action='store_true',default=True)
    ap.add_argument('--no-fresh-review',dest='fresh_review',action='store_false')
    args=ap.parse_args();root=Path(__file__).resolve().parents[1]
    out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=False)
    command=[sys.executable,'-u','scripts/scenario_instance_test.py']
    if args.worker:command.append('--worker')
    if args.fresh_review:command.append('--fresh-review')
    record={'started':datetime.now(timezone.utc).isoformat(),'runner_pid':os.getpid(),'command':command,
        'scenario_sha256':hashlib.sha256((root/'scripts/scenario_instance_test.py').read_bytes()).hexdigest()}
    def write(name):(out/(name+'.json')).write_text(json.dumps(record,indent=2),encoding='utf-8')
    write('started')
    try:
        with (out/'scenario.log').open('w',encoding='utf-8') as log:
            child=subprocess.Popen(command,cwd=root,stdout=log,stderr=subprocess.STDOUT,
                env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8'))
            record['scenario_pid']=child.pid;write('started')
            record['exit_code']=child.wait()
    except BaseException:
        record['runner_error']=traceback.format_exc();raise
    finally:
        record['finished']=datetime.now(timezone.utc).isoformat();write('result')
    return record['exit_code']


if __name__=='__main__':sys.exit(main())
