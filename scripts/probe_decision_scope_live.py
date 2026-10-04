"""Live HTTP/PG/DMN MCP producer binding; first three outputs are labelled recorded fixtures, not new Codex work."""
import argparse
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import sys
import subprocess
import time
import uuid
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'it/process'), str(ROOT/'it/agent-worker'), str(ROOT/'common')]
from procsvc import procdb, engine
from worker.context import process_scope
from probe_alert_triage import publish

BASE = 'http://127.0.0.1:8080'


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True); ap.add_argument('--rework', action='store_true'); args = ap.parse_args()
    run_rework = args.rework
    out = Path(args.out); out.mkdir(parents=True, exist_ok=False); checks = []
    def save(name, value): (out/(name+'.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding='utf8')
    def call(path, data=None):
        try:
            req = Request(BASE+path, data=json.dumps(data).encode() if data is not None else None, headers={'Content-Type': 'application/json'})
            with urlopen(req, timeout=30) as r: return r.status, json.load(r)
        except HTTPError as e: return e.code, json.load(e)
    def ok(path, data=None):
        status, body = call(path, data); assert status == 200, (status, body); return body
    def check(name, passed):
        checks.append({'name': name, 'passed': bool(passed)}); save('checks', checks)
        print(('PASS ' if passed else 'FAIL ') + name, flush=True); assert passed, name
    def until(fn, seconds=65):
        end = time.monotonic()+seconds
        while time.monotonic() < end:
            value = fn()
            if value: return value
            time.sleep(.4)
        raise TimeoutError('condition not reached')
    def mcp_call(arguments=None):
        # Use the server image's installed MCP client. The host test venv does
        # not include fastmcp; this still traverses the live HTTP MCP endpoint.
        code = '''import asyncio,json,sys
from fastmcp import Client
async def main():
    arguments=json.load(sys.stdin)
    async with Client('http://127.0.0.1:8198/mcp',timeout=60) as client:
        if arguments is None:
            print(json.dumps([t.model_dump() for t in await client.list_tools()]))
        else:
            result=await client.call_tool('submit_decision',arguments)
            print(next(c.text for c in result.content if c.type=='text'))
asyncio.run(main())'''
        result = subprocess.run(['docker','exec','-i','hyd-iot-edu-dmn-mcp-1','python','-c',code],
                                input=json.dumps(arguments).encode(),capture_output=True,timeout=90)
        if result.returncode: raise RuntimeError(result.stderr.decode('utf8',errors='replace'))
        return json.loads(result.stdout)
    save('health-before', ok('/healthz')); save('mode', ok('/api/process/mode'))
    schema = mcp_call(); save('mcp-schema', schema)
    check('live MCP exposes process_scope argument', 'process_scope' in next(t for t in schema if t['name']=='submit_decision')['inputSchema']['properties'])
    recorded = json.loads((ROOT/'.evidence/reaudit/a034-codex/traces/instance.json').read_text(encoding='utf8'))
    repo = procdb.PgRepo('postgresql://postgres:postgres@127.0.0.1:54322/postgres')
    alert = {'alertId': 'A039-fixture-'+uuid.uuid4().hex[:10], 'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION', 'state': 'RAISE',
             'evidence': {'fixture': 'producer scope only; no physical fault; first three recorded outputs'}}
    inst = ok('/api/instances/start', {'alert': alert}); pid = inst['proc_inst_id']; path = '/api/instances/'+pid
    incident = engine.variables(inst)['incident']; save('start', {'instance': inst, 'alert': alert})
    consumer = 'a039-fixture-'+uuid.uuid4().hex[:8]
    def task(aid): return next(w for w in ok(path)['workitems'] if w['activity_id'] == aid)
    def claim(aid):
        until(lambda: task(aid)['status']=='IN_PROGRESS')
        row, = repo.fetch_pending_task('cliagents', consumer, tenant_id='hyd', proc_inst_id=pid)
        assert row['activity_id'] == aid; return row
    try:
        for aid in ['task:diagnose', 'task:candidates', 'task:compliance']:
            row = claim(aid)
            result = deepcopy(next(w['output'] for w in recorded['workitems'] if w['activity_id']==aid))
            if isinstance(result.get('guide_card'), dict):
                result['guide_card']['alert'] = alert; result['guide_card']['incident'] = incident
            save(aid.replace(':','-')+'-fixture', {'claim': row, 'recorded_fixture_output': result})
            assert repo.save_task_result(row['id'], result, True, expected_consumer=consumer)
            until(lambda: task(aid)['status']=='DONE')
        row = claim('task:rank'); scope = process_scope(row); save('rank-claim', row)
        baseline = ok(path)
        template = {'asset': alert['asset'], 'id': 'A039-rejected-'+uuid.uuid4().hex,
                    'origin': {'incident': incident, 'pattern': alert['pattern'], 'process_scope': scope},
                    'options': [{'id': 'fixture-never-accepted'}]}
        rejected = []
        for field, value in [('tenant','other'), ('instance','other'), ('generation',1), ('consumer','old'), ('version','other'), ('workitem',task('task:diagnose')['id'])]:
            payload = deepcopy(template); payload['origin']['process_scope'][field] = value
            response = call('/api/decisions', payload); rejected.append({'field': field, 'response': response})
            assert response[0] == 409, response
        save('rejected-scopes', rejected)
        check('wrong owner generation claim version and producer all rejected before storage', call('/api/decisions/'+template['id'])[0]==404 and ok(path)==baseline)
        values = engine.variables(ok(path)['instance'])
        args = {'asset': alert['asset'], 'pattern': alert['pattern'], 'cause': values['cause'],
                'failure_mode': values['failure_mode'], 'incident': incident, 'alert_id': alert['alertId'], 'process_scope': scope}
        save('mcp-request', args); result = mcp_call(args); save('mcp-response', result)
        document = result['document']
        check('real DMN MCP evaluates and submits a new decision', result['result']=='ok' and document['status']=='SUBMITTED')
        did = document['id']; decision = ok('/api/decisions/'+did); save('decision', decision)
        check('process stores exact producer scope and pending decision', decision['origin']['process_scope']==scope and decision['state']=='PENDING_APPROVAL')
        duplicate = ok('/api/decisions', decision)
        check('same live producer replay preserves original decision', duplicate.get('duplicate') and ok('/api/decisions/'+did)==decision)
        conflict = deepcopy(decision); conflict['origin']['process_scope']['consumer']='stale'
        check('duplicate ID with another claim is rejected', call('/api/decisions', conflict)[0]==409 and ok('/api/decisions/'+did)==decision)
        check('legacy bridge does not complete scoped rank in advance', task('task:rank')['status']=='IN_PROGRESS' and task('task:select')['status']=='TODO')
        result_output = {'decision_id': did, 'decision': {'recommended': document['recommended'], 'explanation': document['explanation'], 'order': document['cards']}}
        assert repo.save_task_result(row['id'], result_output, True, expected_consumer=consumer)
        until(lambda: task('task:rank')['status']=='DONE')
        check('real PG result advances exact new decision to human selection', engine.variables(ok(path)['instance'])['decision_id']==did and task('task:select')['status']=='IN_PROGRESS')
        check('finished producer cannot register a later decision', call('/api/decisions', dict(decision,id='A039-late-'+uuid.uuid4().hex))[0]==409)
        if run_rework:
            prior_rank=task('task:rank');prior_selection=task('task:select');original=deepcopy(decision)
            proposal=ok(path+'/rework-preview?workitem_id='+prior_rank['id']);save('active-rework-preview',proposal)
            check('live effects preview permits pre-effect incident rework',proposal['execution_available'] and not proposal['blockers'])
            request={'workitem_id':prior_rank['id'],'request_id':str(uuid.uuid4()),'snapshot_token':proposal['snapshot_token'],
                     'by':'A040 fixture reviewer','role':'role:prod-mgr','reason':'Re-evaluate current facts with a new producing work item'}
            receipt=ok(path+'/rework',request);save('rework-receipt',receipt)
            check('live request creates generation 1 and preserves original decision',receipt['generation']==1 and ok('/api/decisions/'+did)==original)
            # Helpers below must now follow the newest work item, not the older
            # preserved DONE row that intentionally has the same activity id.
            def task(aid): return max((w for w in ok(path)['workitems'] if w['activity_id']==aid),key=lambda w:(w.get('generation') or 0,w['start_date']))
            row=claim('task:rank');scope=process_scope(row)
            newargs=dict(args,process_scope=scope)
            unscoped=deepcopy(original);unscoped['id']='A040-unscoped-'+uuid.uuid4().hex;unscoped['origin'].pop('process_scope')
            check('generation 1 refuses unscoped decision submission',call('/api/decisions',unscoped)[0]==409)
            response=mcp_call(newargs);save('generation1-mcp-response',response);document=response['document']
            check('live MCP submits distinct generation 1 decision',response['result']=='ok' and document['status']=='SUBMITTED' and document['id']!=did)
            did=document['id'];decision=ok('/api/decisions/'+did);save('generation1-decision',decision)
            output={'decision_id':did,'decision':{'recommended':document['recommended'],'explanation':document['explanation'],'order':document['cards']}}
            assert repo.save_task_result(row['id'],output,True,expected_consumer=consumer)
            until(lambda:task('task:rank')['status']=='DONE')
            selection=task('task:select')
            check('new generation waits for separate human consent',selection['status']=='IN_PROGRESS' and selection['generation']==1
                  and ok('/api/incidents/'+incident)['cmdId'] is None and engine.variables(ok(path)['instance'])['decision_id']==did)
            stale={'decision':original['id'],'option':original['recommended'],'by':'A040 stale requester','role':'role:prod-mgr'}
            check('both old human work and old decision on new work are refused',
                  call('/api/todolist/'+prior_selection['id']+'/select',stale)[0]==400
                  and call('/api/todolist/'+selection['id']+'/select',stale)[0]==400)
            graph=ok(path+'/graph');save('generation1-graph',graph)
            check('live Neo4j projects new generation and preserved predecessor',
                  graph['graph']['instance']['rework_generation']==1 and any(w['id']==row['id'] and w['generation']==1
                      and w['supersedes_id']==prior_rank['id'] for w in graph['graph']['workitems']))
        # End only this synthetic alert through real source handling and the
        # definition's normal timeout/human escalation path, without approving.
        save('clear-publication', publish(dict(alert, state='CLEAR')))
        until(lambda: ok('/api/incidents/'+incident)['cleared'])
        until(lambda: task('task:escalate')['status']=='IN_PROGRESS')
        ok('/api/todolist/'+task('task:escalate')['id']+'/submit', {'by': 'A039 fixture reviewer',
           'output': {'note': 'Producer-scope fixture reviewed; source cleared; no physical fault or action asserted.'}})
        final = ok(path); inc = ok('/api/incidents/'+incident); save('final', final); save('incident-final', inc)
        check('normal timeout and human review end without command or work order', final['instance']['status']=='COMPLETED' and inc['cmdId'] is None and not inc.get('workOrder'))
        unscoped = deepcopy(decision); unscoped['id']='A039-ended-'+uuid.uuid4().hex; unscoped['origin'].pop('process_scope')
        check('ended process rejects a fresh unscoped decision', call('/api/decisions', unscoped)[0]==409)
    finally:
        save('result', {'scope': __doc__, 'instance': pid, 'incident': incident, 'checks': checks,
                        'generation': 1 if run_rework else 0, 'new_codex_execution': False, 'incident_rework_execution': run_rework})
        save('last-instance', ok(path)); save('last-incident', ok('/api/incidents/'+incident))
    print(f'{len(checks)}/{len(checks)} passed', flush=True)


if __name__ == '__main__': main()
