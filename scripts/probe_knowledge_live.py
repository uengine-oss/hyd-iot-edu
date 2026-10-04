"""Deployed API/poller observes actual semantic membership changes automatically.

Retains a named one-human-task fixture, completed through the ordinary form API.
This is projection verification, not a Codex/physical-control execution.
"""
import argparse
import json
from pathlib import Path
import subprocess
import time
import uuid
from neo4j import GraphDatabase
from probe_definition_registry import http,review_definition

ROOT=Path(__file__).resolve().parents[1]


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--resume',type=Path);args=ap.parse_args()
    tag='knowledge_a048_'+uuid.uuid4().hex[:8]
    out=args.resume or ROOT/'.evidence/reaudit/a048-deployed'/tag
    if not args.resume:out.mkdir(parents=True)
    env=dict(v.split('=',1) for v in json.loads(subprocess.check_output(['docker','inspect','hyd-iot-edu-neo4j-1']))[0]['Config']['Env'])
    driver=GraphDatabase.driver('bolt://127.0.0.1:7687',auth=tuple(env['NEO4J_AUTH'].split('/',1)))
    def q(query,**params):
        with driver.session() as session:return session.execute_write(lambda tx:tx.run(query,**params).data())
    def save(name,value):(out/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
    def until(fn,timeout=90):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            result=fn()
            if result:return result
            time.sleep(1)
        raise TimeoutError('automatic projection condition not reached')
    checks=[]
    def check(name,ok):
        checks.append(dict(name=name,passed=bool(ok)));save('checks',checks)
        print(('PASS ' if ok else 'FAIL ')+name,flush=True);assert ok,name
    if args.resume:
        fixture=json.loads((out/'fixture.json').read_text(encoding='utf8'));definition=fixture['definition'];pid=fixture['pid'];tag=definition['processDefinitionId']
        (out/'checks-attempt1.json').write_bytes((out/'checks.json').read_bytes())
    else:
        definition=review_definition(tag);definition['processDefinitionName']='A048 지식 연결 자동 복구 확인'
        definition['ontologyRef']='process:'+tag
        for item in definition['activities']+definition['events']+definition['gateways']:item['ontologyRef']='semantic:'+tag+':'+item['id']
        assert http('/api/process/definitions',dict(definition=definition))[0]==201
        status,inst=http('/api/instances/start',dict(definition_id=tag,version='1',event_id=tag));assert status==200
        pid=inst['proc_inst_id'];save('fixture',dict(definition=definition,pid=pid))
    elements=definition['activities']+definition['events']+definition['gateways']
    before=http('/api/instances/'+pid)[1];save('before',before)
    def graph():
        status,value=http('/api/instances/'+pid+'/graph');assert status==200;return value
    initial=until(lambda:graph() if graph().get('graph') else None);save('initial',initial)
    check('deployed instance reports absent ontology process before knowledge is created',initial['graph']['process']['id'] is None and any('ontology process missing' in w for w in initial['graph']['warnings']))
    try:
        q('CREATE (:Process {id:$id,name:$name})',id=definition['ontologyRef'],name='A048 retained semantic fixture')
        for item in elements:
            q('MATCH (p:Process {id:$process}) CREATE (n:FlowNode {id:$id,name:$name}) CREATE (p)-[:HAS_NODE]->(n)',process=definition['ontologyRef'],id=item['ontologyRef'],name=item.get('name') or item['id'])
        repaired=until(lambda: (g if g['graph']['process']['id']==definition['ontologyRef'] and not g['graph']['warnings'] and g['projection']['pending']==0 else None) if (g:=graph()).get('graph') else None)
        save('knowledge-created',repaired)
        check('live poller links late Process and all semantic nodes without task mutation',repaired['graph']['process']['id']==definition['ontologyRef'])
        semantic=definition['activities'][0]['ontologyRef']
        q('MATCH (p:Process {id:$process})-[r:HAS_NODE]->(n:FlowNode {id:$id}) DELETE r',process=definition['ontologyRef'],id=semantic)
        removed=until(lambda: (g if any('task:review' in w for w in g['graph']['warnings']) and g['projection']['pending']==0 else None) if (g:=graph()).get('graph') else None)
        edges=q('MATCH (:ProcessVersion {definition_id:$definition})-[:HAS_NODE]->(n)-[:MAPS_TO]->(s {id:$id}) RETURN n.id AS id',definition=tag,id=semantic)
        save('membership-removed',removed)
        check('live poller removes stale semantic link and exposes warning',not edges)
        q('MATCH (p:Process {id:$process}),(n:FlowNode {id:$id}) CREATE (p)-[:HAS_NODE]->(n)',process=definition['ontologyRef'],id=semantic)
        restored=until(lambda: (g if not g['graph']['warnings'] and g['projection']['pending']==0 else None) if (g:=graph()).get('graph') else None)
        after=http('/api/instances/'+pid)[1];save('after',after);save('membership-restored',restored)
        check('restored knowledge clears warning while preserving actual work and instance',after['instance']==before['instance'] and after['workitems']==before['workitems'])
        status,sync=http('/api/graph-projections');save('sync-status',sync)
        check('deployed status reports observed and durably enqueued knowledge',status==200 and sync['knowledge']['last_error'] is None and sync['knowledge']['observed_digest']==sync['knowledge']['queued']['digest'])
    finally:
        # Finish the isolated human form normally, leaving no active test task.
        current=http('/api/instances/'+pid)[1]
        task=current['workitems'][0]
        if task['status']!='DONE':
            status,result=http('/api/todolist/'+task['id']+'/submit',dict(output={'score':9},by='A048 explicit fixture completion'))
            save('completion-response',dict(status=status,result=result));assert status==200
        final=until(lambda: (v if v['instance']['status']=='COMPLETED' else None) if (v:=http('/api/instances/'+pid)[1]) else None)
        save('final',final);driver.close()
    check('isolated human form completes through its ordinary conditional process',final['instance']['end_event']=='accepted')
    print(json.dumps(dict(evidence=str(out),pid=pid),ensure_ascii=False))


if __name__=='__main__':main()
