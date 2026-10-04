"""Live Kafka/PG storage-error and CLEAR interruption probes.

The insert failure is an explicit PG trigger scoped to this test alert. It is
not a server/network outage. The trigger/function are removed in finally.
"""
import argparse
from datetime import datetime,timezone
import json,os,subprocess,time,uuid
from pathlib import Path
from urllib.request import urlopen
from urllib.error import HTTPError
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from probe_alert_triage import publish
from scenario_instance_test import get,post,PROCESS


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);args=ap.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=False)
    suffix=uuid.uuid4().hex[:10];aid='A033-persist-'+suffix
    function='a033_fail_'+suffix;trigger=function;dsn=os.environ['SUPABASE_DSN'];checks=[]
    def save(name,x):(out/(name+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str),encoding='utf8')
    def check(name,ok,detail=None):
        checks.append({'name':name,'passed':bool(ok),'detail':detail});save('checks',checks)
        print(('PASS ' if ok else 'FAIL ')+name,flush=True);assert ok,name
    def until(fn,seconds=100):
        deadline=time.monotonic()+seconds;last=None
        while time.monotonic()<deadline:
            try:
                value=fn()
                if value:return value
            except Exception as exc:last=str(exc)
            time.sleep(.5)
        raise TimeoutError(last or 'condition not observed')
    def rows():
        with psycopg.connect(dsn,row_factory=dict_row) as c:
            return c.execute("select * from process_source_inbox where tenant_id='hyd' and payload->>'alertId'=%s order by id",(aid,)).fetchall()
    def health():
        try:r=urlopen(PROCESS+'/healthz',timeout=10)
        except HTTPError as exc:r=exc
        return json.loads(r.read())
    def offsets(position):
        code='''import asyncio,json,sys
from aiokafka import AIOKafkaConsumer,TopicPartition
from hydcommon.kafka import bootstrap
async def main():
    p=json.load(sys.stdin);c=AIOKafkaConsumer(bootstrap_servers=bootstrap(),group_id='process',enable_auto_commit=False)
    await c.start()
    try:print(json.dumps({'committed':await c.committed(TopicPartition(p['topic'],p['partition']))}))
    finally:await c.stop()
asyncio.run(main())'''
        r=subprocess.run(['docker','exec','-i','hyd-iot-edu-agent-1','python','-c',code],input=json.dumps(position),text=True,capture_output=True,timeout=30,check=True)
        return json.loads(r.stdout)
    def remove_trigger():
        with psycopg.connect(dsn,autocommit=True) as c:
            c.execute(sql.SQL('drop trigger if exists {} on public.process_source_inbox').format(sql.Identifier(trigger)))
            c.execute(sql.SQL('drop function if exists public.{}()').format(sql.Identifier(function)))
        save('trigger-removed',{'trigger':trigger,'function':function})
    alert={'asset':'HYD-02','alertId':aid,'pattern':'UNSUPPORTED_A033','state':'RAISE',
           't':datetime.now(timezone.utc).isoformat(),'evidence':{'fixture':'scoped PG insert rejection'}}
    trigger_created=False;lock=None;receipt_lock=None;killed=False
    try:
        check('healthy instance mode baseline',health()['ok'] and get(PROCESS+'/api/process/mode')['mode']=='instance')
        with psycopg.connect(dsn,autocommit=True) as c:
            body=sql.SQL("BEGIN IF NEW.tenant_id='hyd' AND NEW.payload->>'alertId'={} THEN RAISE EXCEPTION 'A033 injected source insert failure'; END IF; RETURN NEW; END").format(sql.Literal(aid)).as_string(c)
            c.execute(sql.SQL('create function public.{}() returns trigger language plpgsql as {}').format(sql.Identifier(function),sql.Literal(body)))
            trigger_created=True
            c.execute(sql.SQL('create trigger {} before insert on public.process_source_inbox for each row execute function public.{}()').format(sql.Identifier(trigger),sql.Identifier(function)))
        save('fixture',{'alert':alert,'trigger':trigger,'function':function})
        position=publish(alert);save('published',position)
        failure=until(lambda:(h if 'A033 injected source insert failure' in h.get('source_receive_error','') else None) if (h:=health()) else None)
        check('live consumer reports real PG insert error',failure['ok'] is False);save('health-failure',failure)
        first=offsets(position);time.sleep(2);second=offsets(position)
        save('offsets-blocked',{'first':first,'second':second,'published':position})
        check('unpersisted event has no receipt or Incident',not rows() and not any(i['alertId']==aid for i in get(PROCESS+'/api/incidents')))
        check('Kafka group does not commit past rejected receipt',first['committed']==second['committed']
              and (second['committed'] is None or second['committed']<=position['offset']))
        remove_trigger();trigger_created=False
        raised=until(lambda:next((r for r in rows() if r['kind']=='RAISE' and r['status']=='HANDLED'),None))
        committed=until(lambda:(v if v['committed'] is not None and v['committed']>position['offset'] else None) if (v:=offsets(position)) else None)
        save('raise-handled',raised);save('offset-recovered',committed)
        check('same Kafka delivery persists after storage recovers',raised['payload']==alert and raised['offset_no']==position['offset'] and len(rows())==1)
        check('source receive error clears',health()['ok'] and 'source_receive_error' not in health())
        pid=raised['result']['instance'];iid=raised['result']['incident']
        lock=psycopg.connect(dsn)
        lock.execute('select proc_inst_id from bpm_proc_inst where proc_inst_id=%s for update',(pid,))
        clear=publish(dict(alert,state='CLEAR'));save('clear-published',clear)
        claimed=until(lambda:next((r for r in rows() if r['kind']=='CLEAR' and r['status']=='CLAIMED'),None))
        receipt_lock=psycopg.connect(dsn)
        receipt_lock.execute('select id from process_source_inbox where id=%s for update',(claimed['id'],))
        lock.rollback();lock.close();lock=None
        cleared=until(lambda:(i if i['cleared'] else None) if (i:=get(PROCESS+'/api/incidents/'+iid)) else None)
        check('CLEAR persisted before receipt completion',cleared['state']=='ESCALATED' and next(r for r in rows() if r['id']==claimed['id'])['status']=='CLAIMED')
        blocker=receipt_lock.info.backend_pid
        def pending_finish():
            with psycopg.connect(dsn,row_factory=dict_row) as c:
                return c.execute("""select pid,query,state,wait_event_type,wait_event from pg_stat_activity
                    where %s=any(pg_blocking_pids(pid)) and query like %s""",
                    (blocker,"update process_source_inbox set status='HANDLED'%")).fetchone()
        backend=until(pending_finish);save('clear-blocked-finish',backend)
        save('clear-before-kill',{'incident':cleared,'receipts':rows()})
        subprocess.run(['docker','kill','hyd-iot-edu-process-1'],check=True,capture_output=True,timeout=30);killed=True
        # A server-side statement can outlive its killed client. Abort exactly
        # the observed blocked completion connection before releasing the lock,
        # so this run proves retry after a rolled-back completion transaction.
        with psycopg.connect(dsn,autocommit=True) as c:
            aborted=c.execute('select pg_terminate_backend(pid) from pg_stat_activity where pid=%s and %s=any(pg_blocking_pids(pid))',
                              (backend['pid'],blocker)).fetchone()
        save('clear-completion-connection-aborted',{'backend':backend['pid'],'termination':aborted})
        receipt_lock.rollback();receipt_lock.close();receipt_lock=None
        subprocess.run(['docker','start','hyd-iot-edu-process-1'],check=True,capture_output=True,timeout=30);killed=False
        until(lambda:health()['ok'])
        handled=until(lambda:next((r for r in rows() if r['id']==claimed['id'] and r['status']=='HANDLED'),None),130)
        final=get(PROCESS+'/api/incidents/'+iid);save('clear-after',{'receipt':handled,'incident':final})
        check('same CLEAR resumes after process death',handled['attempts']==2 and handled['failures']==1 and final['cleared'])
        check('CLEAR does not fabricate recovery or PLC command',final['state']=='ESCALATED' and final['cmdId'] is None and final['workOrder'] is None)
        view=get(PROCESS+'/api/instances/'+pid)
        task=next(w for w in view['workitems'] if w['activity_id']=='task:triage' and w['status']=='IN_PROGRESS')
        reply=post(PROCESS+'/api/todolist/'+task['id']+'/submit',{'by':'A033 persistence probe',
            'output':{'note':'Scoped PG write failure and CLEAR process-death verified. No physical recovery or command.'}})
        check('human review recorded',not reply.get('error'))
        save('instance-final',get(PROCESS+'/api/instances/'+pid));save('receipts-final',rows())
    finally:
        if lock is not None:lock.rollback();lock.close()
        if receipt_lock is not None:receipt_lock.rollback();receipt_lock.close()
        if trigger_created:remove_trigger()
        if killed:subprocess.run(['docker','start','hyd-iot-edu-process-1'],check=True,capture_output=True,timeout=30)
        save('result',{'checks':checks,'alert_id':aid,'scope':'real Kafka offset, PG scoped insert error, CLEAR persisted before process SIGKILL plus termination of its blocked PG completion connection; not DB-wide connectivity outage or PLC ACK interruption'})
    print(f'{len(checks)}/{len(checks)} passed',flush=True)


if __name__=='__main__':main()
