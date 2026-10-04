"""Deployed quarantine and operator CLI repair of completed A048/A046 fixtures.

Only derived graph state/outbox are changed; process/incident business snapshots
must stay identical. This is neither a business restore nor a new agent run.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid
import psycopg
from neo4j import GraphDatabase
from probe_definition_registry import http

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.evidence/reaudit/a049-deployed'
DSN='postgresql://postgres:postgres@127.0.0.1:54322/postgres'
PID='knowledge_a048_56296646.b1e7fb00-7995-4cc3-91d3-ebfc286b8fc4'
INC='INC-1004-01-4ff2'


def main():
    global OUT
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['prepare','repair']);ap.add_argument('--out',type=Path);args=ap.parse_args()
    if args.out:OUT=args.out
    OUT.mkdir(exist_ok=args.phase!='prepare')
    def save(name,value):(OUT/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str),encoding='utf8')
    def read(name):return json.loads((OUT/(name+'.json')).read_text(encoding='utf8'))
    checks=read('checks') if args.phase=='repair' else []
    def check(name,ok):
        checks.append(dict(name=name,passed=bool(ok)));save('checks',checks)
        print(('PASS ' if ok else 'FAIL ')+name,flush=True);assert ok,name
    def until(fn,timeout=80):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            try:
                value=fn()
                if value:return value
            except OSError:pass
            time.sleep(1)
        raise TimeoutError('live condition not reached')
    def cli(command,name):
        result=subprocess.run(command,capture_output=True,cwd=ROOT,timeout=60)
        (OUT/(name+'.log')).write_bytes(result.stdout+result.stderr)
        assert result.returncode==0,(name,result.returncode)
    env=dict(v.split('=',1) for v in json.loads(subprocess.check_output(['docker','inspect','hyd-iot-edu-neo4j-1']))[0]['Config']['Env'])
    driver=GraphDatabase.driver('bolt://127.0.0.1:7687',auth=tuple(env['NEO4J_AUTH'].split('/',1)))
    def q(query,**params):
        with driver.session() as session:return session.execute_write(lambda tx:tx.run(query,**params).data())
    def view():
        status,data=http('/api/instances/'+PID);assert status==200;return data
    def graph():
        status,data=http('/api/instances/'+PID+'/graph');assert status==200;return data
    def incident():
        status,data=http('/api/incidents/'+INC);assert status==200;return data
    if args.phase=='prepare':
        before=view();case_before=incident()
        assert before['instance']['status']=='COMPLETED' and case_before['state']=='CLOSED'
        save('before',before);save('incident-before',case_before);save('graph-before',graph())
        with psycopg.connect(DSN) as conn:
            seq=conn.execute('select last_value from hyd_projection_revision').fetchone()[0]
        fence=q('MATCH (f:ExecutionProjection {id:$id}) RETURN f.revision AS revision,f.payload_hash AS payload_hash',id=PID)
        assert len(fence)==1
        save('fence-before',fence)
        q('MATCH (f:ExecutionProjection {id:$id}) SET f.revision=$revision',id=PID,revision=seq+100)
        with psycopg.connect(DSN) as conn:conn.execute('insert into execution_projection_outbox(tenant_id,proc_inst_id) values(%s,%s)',('hyd',PID))
        blocked=until(lambda:(g if (g['projection']['last_error'] or '').startswith('ProjectionConflict:') else None) if (g:=graph()) else None)
        save('quarantined',blocked)
        check('live service retains a refused graph delivery as pending review',blocked['projection']['pending']>0)
        with psycopg.connect(DSN) as conn:
            attempts=conn.execute('select sum(attempts) from execution_projection_outbox where tenant_id=%s and proc_inst_id=%s and processed_at is null',('hyd',PID)).fetchone()[0]
            conn.execute('insert into execution_projection_outbox(tenant_id,proc_inst_id) values(%s,%s)',('hyd',PID))
        end=time.monotonic()+8
        while time.monotonic()<end:time.sleep(1)
        with psycopg.connect(DSN) as conn:after=conn.execute('select sum(attempts) from execution_projection_outbox where tenant_id=%s and proc_inst_id=%s and processed_at is null',('hyd',PID)).fetchone()[0]
        check('new queue rows do not bypass durable quarantine',attempts==after and graph()['projection']['pending']>0)
        edge=q('MATCH (:Incident {id:$id})-[r:ON_ASSET]->(a) RETURN a.code AS code',id=INC)
        assert edge==[dict(code='HYD-01')]
        save('incident-incoming-before',q('MATCH (a)-[r]->(:Incident {id:$id}) RETURN a.id AS source,type(r) AS type ORDER BY source,type',id=INC))
        q('MATCH (i:Incident {id:$id}) DETACH DELETE i',id=INC)
        save('state',dict(pid=PID,incident=INC,requests={kind:str(uuid.uuid4()) for kind in ['Execution','Incident']}))
        print('READY for live UI inspection and explicit CLI repair',flush=True)
    else:
        state=read('state')
        for kind,sid in [('Execution',PID),('Incident',INC)]:
            file='/tmp/a049-'+state['requests'][kind]+'.json'
            base=['docker','exec','hyd-iot-edu-process-1','python','-m','procsvc.projection_repair']
            cli(base+['inspect','--kind',kind,'--id',sid,'--file',file],kind+'-inspect')
            cli(['docker','cp','hyd-iot-edu-process-1:'+file,str(OUT/(kind+'-plan.json'))],kind+'-copy-plan')
            plan=read(kind+'-plan')
            if kind=='Execution':check('CLI inspection captures the exact completed source and rejected receipt',plan['source']['instance']['proc_inst_id']==PID and plan['source']['instance']['status']=='COMPLETED' and any((p['last_error'] or '').startswith('ProjectionConflict:') for p in plan['pending']))
            else:check('CLI inspection captures the closed source, absent graph and dependent judgments',plan['source']['id']==INC and plan['source']['state']=='CLOSED' and not plan['graph']['nodes'] and len(plan['dependents'])>0)
            cli(base+['apply','--file',file,'--by','A049 operator verification','--reason','repair isolated derived fixture after source comparison','--request-id',state['requests'][kind]],kind+'-apply')
            resultfile=file.removesuffix('.json')+'.result.json'
            cli(['docker','cp','hyd-iot-edu-process-1:'+resultfile,str(OUT/(kind+'-result.json'))],kind+'-copy-result')
        repaired=until(lambda:(g if g['projection']['pending']==0 and not g['graph']['warnings'] else None) if (g:=graph()) else None)
        until(lambda:q('MATCH (:Incident {id:$id})-[:ON_ASSET]->(a {code:"HYD-01"}) RETURN a.code AS code',id=INC))
        save('graph-repaired',repaired)
        check('ordinary delivery confirms both graph repairs',repaired['projection']['last_error'] is None)
        expected=read('incident-incoming-before')
        until(lambda:q('MATCH (a)-[r]->(:Incident {id:$id}) RETURN a.id AS source,type(r) AS type ORDER BY source,type',id=INC)==expected)
        check('whole incident recreation restores original incoming decision and execution links',True)
        check('repair changes no actual business instance, task or incident',view()['instance']==read('before')['instance'] and view()['workitems']==read('before')['workitems'] and incident()==read('incident-before'))
        cli(['docker','compose','restart','process'],'restart')
        until(lambda:http('/healthz')[0]==200)
        for kind in ['Execution','Incident']:
            file='/tmp/a049-'+state['requests'][kind]+'.json'
            cli(['docker','exec','hyd-iot-edu-process-1','python','-m','procsvc.projection_repair','apply','--file',file,'--by','A049 operator verification','--reason','repair isolated derived fixture after source comparison','--request-id',state['requests'][kind]],kind+'-replay-after-restart')
        after=view();save('after-restart',after);save('sync',http('/api/graph-projections')[1])
        check('service restart and CLI replay preserve current source and zero execution pending',after['instance']==read('before')['instance'] and after['workitems']==read('before')['workitems'] and graph()['projection']['pending']==0)
        with psycopg.connect(DSN) as conn:count=conn.execute('select count(*) from projection_repairs where request_id=%s',(state['requests']['Execution'],)).fetchone()[0]
        check('replayed execution repair has exactly one durable journal receipt',count==1)
    driver.close()


if __name__=='__main__':main()
