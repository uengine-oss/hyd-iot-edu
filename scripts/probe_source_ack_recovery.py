"""Real approved fan action/PLC ACK, then kill before ACK receipt completion.

A scoped PG trigger blocks only completion of this Incident's ACK. Terminating
the observed DB connection ensures the completion transaction was aborted;
client SIGKILL alone does not guarantee that. No Codex worker is used here.
"""
import argparse,json,os,subprocess,time,uuid
from pathlib import Path
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
import scenario_pump_fan_test as s


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);args=ap.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=False)
    dsn=os.environ['SUPABASE_DSN'];suffix=uuid.uuid4().hex[:10];name='a033_ack_'+suffix;key=name
    checks=[];gate=None;created=False;killed=False;pid=iid=None
    def save(n,x):(out/(n+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str),encoding='utf8')
    def check(n,ok):
        checks.append({'name':n,'passed':bool(ok)});save('checks',checks)
        print(('PASS ' if ok else 'FAIL ')+n,flush=True);assert ok,n
    def until(fn,seconds=90):
        end=time.monotonic()+seconds;error=None
        while time.monotonic()<end:
            try:
                v=fn()
                if v:return v
            except Exception as exc:error=str(exc)
            time.sleep(.3)
        raise TimeoutError(error or 'condition not observed')
    def incident():return s.get(s.PROCESS+'/api/incidents/'+iid)
    def remove_trigger():
        with psycopg.connect(dsn,autocommit=True) as c:
            c.execute(sql.SQL('drop trigger if exists {} on public.process_source_inbox').format(sql.Identifier(name)))
            c.execute(sql.SQL('drop function if exists public.{}()').format(sql.Identifier(name)))
        save('trigger-removed',{'name':name})
    def ack_rows(cmd):
        with psycopg.connect(dsn,row_factory=dict_row) as c:
            return c.execute("select * from process_source_inbox where tenant_id='hyd' and payload->>'cmdId'=%s order by id",(cmd,)).fetchall()
    def command_messages(cmd):
        code='''import asyncio,json,sys
from aiokafka import AIOKafkaConsumer,TopicPartition
from hydcommon.kafka import bootstrap
from hydcommon import topics
async def main():
    target=json.load(sys.stdin);c=AIOKafkaConsumer(bootstrap_servers=bootstrap(),enable_auto_commit=False)
    await c.start()
    try:
        parts=[TopicPartition(topics.K_CMD,p) for p in c.partitions_for_topic(topics.K_CMD) or []]
        if not parts:
            await c.topics();parts=[TopicPartition(topics.K_CMD,p) for p in c.partitions_for_topic(topics.K_CMD)]
        c.assign(parts);end=await c.end_offsets(parts);await c.seek_to_beginning(*parts);found=[]
        while not all([await c.position(p)>=end[p] for p in parts]):
            batch=await c.getmany(timeout_ms=2000,max_records=500)
            for p,rows in batch.items():
                for r in rows:
                    if r.offset>=end[p]:continue
                    v=json.loads(r.value)
                    if v.get('cmdId')==target:found.append({'partition':r.partition,'offset':r.offset,'value':v})
        print(json.dumps(found))
    finally:await c.stop()
asyncio.run(main())'''
        r=subprocess.run(['docker','exec','-i','hyd-iot-edu-agent-1','python','-c',code],input=json.dumps(cmd),text=True,capture_output=True,timeout=35,check=True)
        return json.loads(r.stdout)
    try:
        mode=s.get(s.PROCESS+'/api/process/mode');check('20x instance legacy baseline',mode['time_scale']==20 and mode['mode']=='instance' and mode['agent_bridge']=='legacy')
        s.post(s.PLANT+'/api/reset');time.sleep(3)
        selection=s.run_to_selection('HYD-03','fan_vibration','FAN_VIBRATION',150)
        check('real fan alert reaches human selection',selection is not None and all(ok for _,ok,_ in s.results))
        pid,iid,decision,task,_=selection;save('selection',{'instance':pid,'incident':iid,'decision':decision,'task':task})
        gate=psycopg.connect(dsn,autocommit=True)
        gate.execute('select pg_advisory_lock(hashtextextended(%s,0))',(key,))
        with psycopg.connect(dsn,autocommit=True) as c:
            body=sql.SQL("BEGIN IF NEW.kind='ACK' AND NEW.status='HANDLED' AND NEW.result->>'incident'={} THEN PERFORM pg_advisory_xact_lock(hashtextextended({},0)); END IF; RETURN NEW; END").format(sql.Literal(iid),sql.Literal(key)).as_string(c)
            c.execute(sql.SQL('create function public.{}() returns trigger language plpgsql as {}').format(sql.Identifier(name),sql.Literal(body)));created=True
            c.execute(sql.SQL('create trigger {} before update on public.process_source_inbox for each row execute function public.{}()').format(sql.Identifier(name),sql.Identifier(name)))
        response=s.post(s.PROCESS+'/api/todolist/'+task['id']+'/select',{'decision':decision['id'],'option':'skill:fan-slow-derate','by':'A033 ACK 검증','role':'role:prod-mgr','reason':'팬 조치 ACK 접수 중단 후 재시작 검토 경계 확인'})
        save('approval',response);check('explicit human selection accepted',response.get('accepted') is True)
        ack=until(lambda:(i if (i.get('ack') or {}).get('result')=='DONE' and i['state']=='RE_OBSERVING' else None) if (i:=incident()) else None)
        save('incident-before-kill',ack);cmd=ack['cmdId']
        blocker=gate.info.backend_pid
        def blocked():
            with psycopg.connect(dsn,row_factory=dict_row) as c:
                return c.execute("select pid,query,wait_event from pg_stat_activity where %s=any(pg_blocking_pids(pid)) and query like %s",(blocker,"update process_source_inbox set status='HANDLED'%")).fetchone()
        backend=until(blocked);save('blocked-completion',backend)
        receipt=next(r for r in ack_rows(cmd) if r['parent_id'] is None);save('receipt-before-kill',receipt)
        check('actual PLC ACK is persisted while source completion waits',receipt['kind']=='ACK' and receipt['status']=='CLAIMED' and ack['actions']==[{'code':'FAN_SET','fan_pct':40},{'code':'LOAD_SET','load_pct':80}])
        subprocess.run(['docker','kill','hyd-iot-edu-process-1'],check=True,capture_output=True,timeout=30);killed=True
        with psycopg.connect(dsn,autocommit=True) as c:
            result=c.execute('select pg_terminate_backend(pid) from pg_stat_activity where pid=%s and %s=any(pg_blocking_pids(pid))',(backend['pid'],blocker)).fetchone()
        save('aborted-completion',{'pid':backend['pid'],'terminated':result})
        gate.close();gate=None;remove_trigger();created=False
        subprocess.run(['docker','start','hyd-iot-edu-process-1'],check=True,capture_output=True,timeout=30);killed=False
        until(lambda:s.get(s.PROCESS+'/healthz')['ok'])
        resumed=until(lambda:next((r for r in ack_rows(cmd) if r['id']==receipt['id'] and r['status']=='HANDLED'),None),130)
        final=incident();save('receipt-after',resumed);save('incident-after',final)
        check('same ACK retries with original command identity',resumed['attempts']==2 and resumed['failures']==1 and resumed['payload']==receipt['payload'] and final['cmdId']==cmd)
        check('late ACK preserves restart review instead of recovery',final['state']=='ESCALATED' and final['reason']=='PROCESS_RESTART_REVIEW' and final['workOrder'] is None)
        commands=command_messages(cmd);save('kafka-commands',commands)
        check('Kafka has exactly one publication of the approved command',len(commands)==1)
        view=until(lambda:(v if any(w['activity_id']=='task:escalate' and w['status']=='IN_PROGRESS' for w in v['workitems']) else None) if (v:=s.view(pid)) else None)
        esc=next(w for w in view['workitems'] if w['activity_id']=='task:escalate')
        reply=s.post(s.PROCESS+'/api/todolist/'+esc['id']+'/submit',{'by':'A033 ACK 검증','output':{'note':'실제 PLC ACK 뒤 수신완료 거래 중단/재시작 검토 확인. 회복 종결로 처리하지 않음.'}})
        check('human restart review accepted',not reply.get('error'))
        completed=s.view(pid);save('instance-final',completed)
        check('ends by escalation, without CMMS branch',completed['instance']['end_event']=='ev:escalated'
              and next(w for w in completed['workitems'] if w['activity_id']=='task:work-order')['status']=='CANCELLED')
    finally:
        if gate is not None:gate.close()
        if created:remove_trigger()
        if killed:subprocess.run(['docker','start','hyd-iot-edu-process-1'],check=True,capture_output=True,timeout=30)
        if iid:
            try:save('last-incident',incident())
            except Exception as exc:save('observation-error',{'error':str(exc)})
        save('plant-reset',s.post(s.PLANT+'/api/reset'))
        save('result',{'checks':checks,'setup_checks':s.results,'instance':pid,'incident':iid,
            'scope':'real fan simulator, legacy agent, explicit approval, Kafka command/PLC ACK, process SIGKILL and scoped PG completion connection termination; no Codex'})
    print(f'{len(checks)}/{len(checks)} passed',flush=True)


if __name__=='__main__':main()
