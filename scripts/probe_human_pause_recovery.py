"""Real PostgreSQL pause/answer atomicity; CLI responses are explicit fakes."""
from concurrent.futures import ThreadPoolExecutor
import json
import sys
import traceback

from probe_instance_recovery import fixture, another, task, TENANTS, DSN, ROOT
import psycopg
from cliagents import ExecEvent, ExecEventKind, Permission
from worker import hitl
from worker.runner import Runner
from worker.settings import Settings

OUT=ROOT/'.evidence/reaudit/human-pause-pg';OUT.mkdir(exist_ok=True)
REPORT={'scope':'real PostgreSQL; fake CLI; no PLC/enterprise effects','checks':[]}


def worker(rt,answer=None,requests=None):
    def run(provider,req,env):
        if requests is not None:requests.append(req)
        yield ExecEvent(kind=ExecEventKind.RUN_START,session_id='fixture-session')
        yield ExecEvent(kind=ExecEventKind.RESULT,text=json.dumps(answer or {'__human_input__':{'question':'대상 설비는?','options':['HYD-01','HYD-02']}}))
    settings=Settings(tenant_id=rt.tenant_id,cli_agent='codex',default_permission=Permission.READ_ONLY,
                      workspace_root=OUT,consumer=rt.tenant_id+'-worker',cancel_check_every_s=0)
    return Runner(settings,rt.repo,exec_fn=run)


def question(rt,inst):
    wi=task(rt,inst,'task:diagnose')
    events=[e for e in rt.repo.list_events(todo_id=wi['id']) if e['event_type']=='human_asked']
    return wi,events


def file_failure_and_restart():
    rt,hooks,inst,now=fixture(False);original=hitl.remember
    def fail(*a):raise OSError('injected disk failure')
    hitl.remember=fail
    try:worker(rt).poll_once()
    finally:hitl.remember=original
    wi,events=question(rt,inst)
    assert wi['draft_status']=='HUMAN_ASKED' and len(events)==1
    assert wi['draft']['cliagents_session_id']=='fixture-session'
    assert not list((OUT/rt.tenant_id/wi['id']).glob('.processgpt-pending.json'))
    restarted=another(rt);restarted.human_response(wi['id'],events[0]['job_id'],'HYD-02','fixture')
    requests=[];worker(restarted,{'cause':'c','failure_mode':'f','guide_card':{'ok':True}},requests).poll_once()
    assert requests[0].resume_session=='fixture-session'
    assert rt.repo.get_workitem(wi['id'])['status']=='SUBMITTED'
    return {'question_rows':1,'file_exists':False,'new_worker_resume_session':requests[0].resume_session}


def event_failure():
    rt,hooks,inst,now=fixture(False);record=rt.repo.record_events
    def fail(rows):
        if any(e['event_type']=='human_asked' for e in rows):raise RuntimeError('injected event failure')
        return record(rows)
    rt.repo.record_events=fail;worker(rt).poll_once()
    wi,events=question(rt,inst)
    assert wi['draft_status']=='FAILED' and not events and wi['draft'] is None
    return {'draft_status':wi['draft_status'],'question_rows':len(events),'orphan_question':False}


def notification_failure():
    rt,hooks,inst,now=fixture(False)
    def fail(note):raise RuntimeError('injected notification failure')
    rt.repo.insert_notification=fail;worker(rt).poll_once()
    wi,events=question(rt,inst)
    assert wi['draft_status']=='FAILED' and not events and wi['draft'] is None
    return {'draft_status':wi['draft_status'],'question_rows':len(events),'rolled_back_draft':True}


def competing_answers():
    rt,hooks,inst,now=fixture(False);worker(rt).poll_once();wi,events=question(rt,inst)
    runtimes=[another(rt) for _ in range(8)]
    def answer(r):
        try:r.human_response(wi['id'],events[0]['job_id'],'HYD-02','fixture');return 'accepted'
        except ValueError:return 'rejected'
    with ThreadPoolExecutor(8) as pool:results=list(pool.map(answer,runtimes))
    replies=[e for e in rt.repo.list_events(todo_id=wi['id']) if e['event_type']=='human_response']
    assert results.count('accepted')==1 and len(replies)==1
    assert rt.repo.get_workitem(wi['id'])['draft_status']=='FB_REQUESTED'
    return {'connections':8,'results':results,'response_rows':len(replies)}


def main():
    try:
        for case in (file_failure_and_restart,event_failure,notification_failure,competing_answers):
            try:
                detail=case();REPORT['checks'].append(dict(name=case.__name__,ok=True,detail=detail));print(case.__name__+': PASS',flush=True)
            except Exception:
                REPORT['checks'].append(dict(name=case.__name__,ok=False,error=traceback.format_exc()));print(traceback.format_exc(),flush=True)
    finally:
        with psycopg.connect(DSN) as c:
            pids=[r[0] for r in c.execute('select proc_inst_id from bpm_proc_inst where tenant_id=any(%s)',(TENANTS,)).fetchall()]
            REPORT['fixture_instances']=pids
            c.execute('delete from events where proc_inst_id=any(%s)',(pids,))
            for tenant in TENANTS:
                c.execute('delete from notifications where tenant_id=%s',(tenant,))
                c.execute('delete from bpm_proc_inst where tenant_id=%s',(tenant,))
                c.execute('delete from proc_def_version where tenant_id=%s',(tenant,))
                c.execute('delete from proc_def where tenant_id=%s',(tenant,))
                c.execute('delete from tenants where id=%s',(tenant,))
            REPORT['remaining_instances']=c.execute('select count(*) from bpm_proc_inst where tenant_id=any(%s)',(TENANTS,)).fetchone()[0]
            REPORT['remaining_events']=c.execute('select count(*) from events where proc_inst_id=any(%s)',(pids,)).fetchone()[0]
        REPORT['passed']=sum(c['ok'] for c in REPORT['checks']);REPORT['total']=len(REPORT['checks'])
        (OUT/'report.json').write_text(json.dumps(REPORT,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f"{REPORT['passed']}/{REPORT['total']}; remaining={REPORT['remaining_instances']}")
    return 0 if REPORT['passed']==REPORT['total'] else 1


if __name__=='__main__':sys.exit(main())
