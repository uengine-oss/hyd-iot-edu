"""Real PostgreSQL result fencing and real silent process-tree teardown.

No CLI account or business write is used. PowerShell checks process IDs on Windows.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid

from probe_definition_registry import ROOT,DSN
from probe_registered_codex import definition
import psycopg
from cliagents import ExecRequest
from procsvc import engine,instances,procdb
from worker.codex_provider import WorkerCodexProvider
from worker.runner import Runner,RunFailed,Cancelled
from worker.settings import Settings


def main():
    tenant='worker-control-'+uuid.uuid4().hex[:8]
    out=ROOT/'.evidence/reaudit'/tenant;out.mkdir()
    report={'fixture':tenant,'checks':{},'root_and_child_pids':[]};repo=procdb.PgRepo(DSN)
    def save(): (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    def check(name,ok,detail=None):
        report['checks'][name]={'passed':bool(ok),'detail':detail};save()
        print(name,'PASS' if ok else 'FAIL',flush=True);assert ok,name
    try:
        with psycopg.connect(DSN,autocommit=True) as c:c.execute('insert into tenants(id,name) values(%s,%s)',(tenant,tenant))
        rt=instances.InstanceRuntime(repo,engine.Definition.from_dict(definition(tenant,'1')),instances.Hooks(),tenant_id=tenant)
        def claimed(event):
            inst=rt.start_definition(tenant,'1',event)
            return repo.fetch_pending_task('cliagents','owner-'+event,tenant_id=tenant,proc_inst_id=inst['proc_inst_id'])[0]
        for mode in ('status','draft','reassigned','done'):
            row=claimed(mode);owner=row['consumer']
            fresh=dict(row)
            if mode=='status':fresh['status']='CANCELLED'
            elif mode=='draft':fresh['draft_status']='CANCELLED'
            elif mode=='reassigned':fresh['consumer']='new-owner'
            else:fresh.update(status='DONE',consumer=None)
            repo.update_workitem(fresh);before=repo.get_workitem(row['id'])
            ok=not repo.save_task_result(row['id'],{'count':999},True,expected_consumer=owner)
            ok=ok and not repo.update_task_error(row['id'],expected_consumer=owner)
            ok=ok and not repo.set_draft_status(row['id'],'HUMAN_ASKED',expected_consumer=owner)
            check(mode+'_rejects_late_result_error_pause',ok and repo.get_workitem(row['id'])==before)
        row=claimed('winner')
        def finish(n):return repo.save_task_result(row['id'],{'count':n},True,expected_consumer=row['consumer'])
        with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(finish,range(8)))
        check('one_of_eight_result_writers_wins',sum(results)==1,results)
        draft=claimed('draft-mode');draft['agent_mode']='DRAFT';repo.update_workitem(draft)
        check('draft_mode_uses_same_owner_guard',repo.save_task_result(draft['id'],{'count':1},True,expected_consumer=draft['consumer'])
              and repo.get_workitem(draft['id'])['status']=='IN_PROGRESS' and repo.get_workitem(draft['id'])['draft']=={'count':1})
        # The child inherits stdout and stays silent even when its parent exits.
        for mode in ('timeout','cancel','parent-exited'):
            row=claimed(mode);pidfile=out/(mode+'-pids.json');script=out/(mode+'.py')
            script.write_text("import subprocess,sys,os,time,json\nfrom pathlib import Path\n"
              +"child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])\n"
              +f"Path({str(pidfile)!r}).write_text(json.dumps([os.getpid(),child.pid]))\n"
              +("sys.exit(0)\n" if mode=='parent-exited' else "time.sleep(30)\n"),encoding='utf-8')
            class ProbeProvider(WorkerCodexProvider):
                def exec_argv(self,request):return [sys.executable,'-u',str(script)]
            settings=Settings(tenant_id=tenant,consumer=row['consumer'],run_timeout_s=.8,cancel_check_every_s=.03)
            runner=Runner(settings,repo,schema_prompt='')
            def cancel():
                fresh=repo.get_workitem(row['id']);fresh['status']='CANCELLED';repo.update_workitem(fresh)
            timer=threading.Timer(.3,cancel) if mode=='cancel' else None
            if timer:timer.start()
            started=time.monotonic();error=None
            try:runner._stream(row,'probe',ProbeProvider(),ExecRequest(prompt='no network',workdir=str(out)),None,'probe')
            except (RunFailed,Cancelled) as e:error=type(e).__name__
            finally:
                if timer:timer.cancel();timer.join()
            elapsed=time.monotonic()-started
            pids=json.loads(pidfile.read_text());report['root_and_child_pids'].extend(pids);save()
            command='$ids=@('+','.join(str(n)for n in pids)+'); @((Get-CimInstance Win32_Process)|Where-Object {$ids -contains $_.ProcessId}|Select-Object -ExpandProperty ProcessId)|ConvertTo-Json -Compress'
            if os.name=='nt':
                found=subprocess.check_output(['powershell.exe','-NoProfile','-Command',command],text=True).strip()
                alive=json.loads(found) if found else []
            else:
                alive=[n for n in pids if Path(f'/proc/{n}').exists()]
            check(mode+'_silent_tree_stopped',error==('Cancelled' if mode=='cancel' else 'RunFailed') and elapsed<3 and not alive,
                  {'error':error,'elapsed_s':round(elapsed,3),'pids':pids,'remaining':alive})
        print('evidence',out,flush=True)
    finally:
        with psycopg.connect(DSN,autocommit=True) as c:
            c.execute('delete from events where proc_inst_id in(select proc_inst_id from bpm_proc_inst where tenant_id=%s)',(tenant,))
            for table in ('todolist','bpm_proc_inst','proc_def_version','proc_def'):
                c.execute(f'delete from {table} where tenant_id=%s',(tenant,))
            c.execute('delete from tenants where id=%s',(tenant,))
            report['remaining_instances']=c.execute('select count(*) from bpm_proc_inst where tenant_id=%s',(tenant,)).fetchone()[0]
        save()


if __name__=='__main__':main()
