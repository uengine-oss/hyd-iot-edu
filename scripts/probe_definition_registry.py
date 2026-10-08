"""Published HTTP definitions and real PostgreSQL tenant claims; exact fixture cleanup."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.request
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'it/process'),str(ROOT/'it/agent-worker'),str(ROOT/'common')]
import psycopg
from neo4j import GraphDatabase
from procsvc import engine,instances,procdb
from worker.context import prepare

DSN='postgresql://postgres:postgres@127.0.0.1:54322/postgres'


def review_definition(did, version='1', threshold=5):
    fid=did+'-form'
    return {'processDefinitionId':did,'processDefinitionName':'변경 정의 검토','version':version,
            'roles':[{'name':'검토자','endpoint':'role:operator'}], 'data':[{'name':'score','type':'Number'}],
            'forms':{fid:{'fields_json':[{'key':'score','type':'number','text':'측정 점수'}]}},
            'activities':[{'id':'task:review','name':'점수 검토','type':'userTask','role':'검토자',
                           'tool':'formHandler:'+fid,'outputData':['score']}],
            'events':[{'id':'start','type':'startEvent'},{'id':'accepted','type':'endEvent'}, {'id':'rejected','type':'endEvent'}],
            'gateways':[{'id':'choice','type':'exclusiveGateway'}],
            'sequences':[{'id':'s1','source':'start','target':'task:review'}, {'id':'s2','source':'task:review','target':'choice'},
                         {'id':'s3','source':'choice','target':'accepted','condition':f'score >= {threshold}'},
                         {'id':'s4','source':'choice','target':'rejected','properties':{'default':True}}]}


def http(path,data=None):
    req=urllib.request.Request('http://127.0.0.1:8080'+path,
          data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=30) as r:return r.status,json.loads(r.read())
    except urllib.error.HTTPError as e:return e.code,json.loads(e.read())


def main():
    prefix='registry-'+uuid.uuid4().hex[:10]
    ids=[prefix,prefix+'-other']; tenants=[prefix+'-a',prefix+'-b']
    out=ROOT/'.evidence/reaudit/definition-registry-live.json'
    evidence=ROOT/'.evidence/reaudit'/prefix;evidence.mkdir()
    report={'prefix':prefix,'checks':{}}
    repo=procdb.PgRepo(DSN)
    def check(name,ok,detail=None):
        report['checks'][name]={'passed':bool(ok),'detail':detail}
        out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(name,'PASS' if ok else 'FAIL',flush=True)
        assert ok,name
    def start(did,version,event):
        code,row=http('/api/instances/start',{'definition_id':did,'version':version,'event_id':event})
        assert code==200,(code,row)
        pid=row['proc_inst_id'];view=http('/api/instances/'+pid)[1]
        return pid,view['workitems'][0]
    try:
        v1=review_definition(ids[0]);fid=ids[0]+'-form'
        v2=review_definition(ids[0],'2',10)
        v2['forms'][fid]['fields_json'].append({'key':'note','type':'text','text':'검토 메모'})
        v2['activities'][0]['outputData'].append('note')
        for v in (v1,v2): (evidence/('v'+v['version']+'.json')).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
        check('publish_v1',http('/api/process/definitions',{'definition':v1})[0]==201)
        check('start_cannot_inject_approval',http('/api/instances/start',{'definition_id':ids[0],'version':'1',
              'event_id':'injection','variables':{'commands':[{'code':'STOP'}]}})[0]==400)
        old,w1=start(ids[0],'1','old')
        check('publish_v2',http('/api/process/definitions',{'definition':v2})[0]==201)
        new,w2=start(ids[0],'2','new')
        with psycopg.connect(DSN,autocommit=True) as c:
            c.execute('insert into form_def(id,tenant_id,fields_json) values(%s,%s,%s::jsonb)',
                      (fid,'hyd',json.dumps([{'key':'wrong','type':'text'}])))
        forms=[http('/api/todolist/'+w['id'])[1] for w in (w1,w2)]
        check('api_and_worker_keep_forms_after_live_table_change',
              [f['key'] for f in forms[0]['form']['fields_json']]==['score'] and
              [f['key'] for f in forms[1]['form']['fields_json']]==['score','note'] and
              [f['key'] for f in prepare(repo,w1,'hyd').form_fields]==['score'],forms)
        check('required_form_rejects_before_state_change',http('/api/todolist/'+w2['id']+'/submit',{'output':{'score':7}})[0]==400
              and repo.get_workitem(w2['id'])['status']=='IN_PROGRESS')
        for w,output in ((w1,{'score':7}),(w2,{'score':7,'note':'[회귀 검사] 검토 완료'})):
            code,row=http('/api/todolist/'+w['id']+'/submit',{'output':output,'by':'[회귀 검사] 실측 검토자'})
            assert code==200,(code,row)
        views=[http('/api/instances/'+pid)[1] for pid in (old,new)]
        graphs=[http('/api/instances/'+pid+'/graph')[1] for pid in (old,new)]
        check('changed_definition_changes_real_terminal_branch', [v['instance']['end_event'] for v in views]==['accepted','rejected'],views)
        check('completed_task_cannot_be_requeued_by_human_response',http('/api/todolist/'+w1['id']+'/human-response',
              {'job_id':'invented','answer':'resume'})[0]==409 and repo.get_workitem(w1['id'])['status']=='DONE')
        check('graph_targets_distinct_versions',graphs[0]['graph']['workitems'][0]['executes']!=graphs[1]['graph']['workitems'][0]['executes'],graphs)
        changed=deepcopy(v1);changed['processDefinitionName']='잘못된 덮어쓰기'
        check('overwrite_and_missing_version_rejected',http('/api/process/definitions',{'definition':changed})[0]==409
              and http('/api/process/definitions/'+ids[0]+'?version=missing')[0]==404)
        check('completed_event_cannot_start_twice',http('/api/instances/start',{'definition_id':ids[0],'version':'1','event_id':'old'})[0]==409)
        other=review_definition(ids[1],threshold=9)
        assert http('/api/process/definitions',{'definition':other})[0]==201
        op,ow=start(ids[1],'1','other')
        assert http('/api/todolist/'+ow['id']+'/submit',{'output':{'score':8}})[0]==200
        check('other_definition_same_activity_id_is_independent',http('/api/instances/'+op)[1]['instance']['end_event']=='rejected')
        def publish(n):
            d=deepcopy(v2);d['version']='3';d['processDefinitionName']='경합'+str(n%2)
            return http('/api/process/definitions',{'definition':d})[0]
        with ThreadPoolExecutor(max_workers=4) as pool: statuses=list(pool.map(publish,range(8)))
        check('concurrent_publish_one_content_wins',statuses.count(201)==4 and statuses.count(409)==4,statuses)
        # Neither synthetic tenant is served by the real hyd polling loop.
        with psycopg.connect(DSN,autocommit=True) as c:
            for tenant in tenants:c.execute('insert into tenants(id,name) values(%s,%s)',(tenant,tenant))
        foreign=instances.InstanceRuntime(repo,engine.Definition.from_dict(other),instances.Hooks(),tenant_id=tenants[0])
        fi=foreign.start_definition(ids[1],'1','foreign')
        fw=repo.list_workitems(proc_inst_id=fi['proc_inst_id'])[0]
        check('http_cannot_read_or_submit_foreign_tenant',http('/api/instances/'+fi['proc_inst_id'])[0]==404
              and http('/api/todolist/'+fw['id'])[0]==404
              and http('/api/todolist/'+fw['id']+'/submit',{'output':{'score':7}})[0]==404
              and http('/api/events?proc_inst_id='+fi['proc_inst_id'])[0]==404)
        fw.update(agent_mode='COMPLETE',agent_orch='cliagents');repo.update_workitem(fw)
        check('postgres_worker_claim_is_tenant_scoped',repo.fetch_pending_task('cliagents','b',tenant_id=tenants[1])==[]
              and len(repo.fetch_pending_task('cliagents','a',tenant_id=tenants[0]))==1)
        fw.update(status='SUBMITTED',consumer=None);repo.update_workitem(fw)
        check('postgres_engine_claim_is_tenant_scoped',repo.claim_submitted('b',tenant_id=tenants[1])==[]
              and len(repo.claim_submitted('a',tenant_id=tenants[0]))==1)
    finally:
        with psycopg.connect(DSN,autocommit=True) as c:
            c.execute('delete from events where proc_inst_id in (select proc_inst_id from bpm_proc_inst where proc_def_id=any(%s))',(ids,))
            for table,col in [('todolist','proc_def_id'),('bpm_proc_inst','proc_def_id'),('proc_def_version','proc_def_id'),('proc_def','id')]:
                c.execute(f'delete from {table} where {col}=any(%s)',(ids,))
            c.execute('delete from form_def where id=%s',(ids[0]+'-form',))
            c.execute('delete from tenants where id=any(%s)',(tenants,))
            report['sql_remaining']=c.execute('select count(*) from bpm_proc_inst where proc_def_id=any(%s)',(ids,)).fetchone()[0]
        c=json.loads(subprocess.check_output(['docker','inspect','hyd-iot-edu-neo4j-1']))[0]
        env=dict(x.split('=',1) for x in c['Config']['Env'])
        with GraphDatabase.driver('bolt://127.0.0.1:7687',auth=tuple(env['NEO4J_AUTH'].split('/',1))) as d,d.session() as s:
            s.run('MATCH (n) WHERE n.definition_id IN $ids DETACH DELETE n',ids=ids).consume()
            report['graph_remaining']=s.run('MATCH (n) WHERE n.definition_id IN $ids RETURN count(n) AS n',ids=ids).single()['n']
        out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
