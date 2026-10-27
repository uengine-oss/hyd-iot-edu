"""Real PostgreSQL handover result and citation audit, never a classroom database."""
import json
from uuid import uuid4

import pytest

from test_backend_pg_contracts import pg, DSN
from test_handover import PATH, START, unknown_draft, _query_evidence, _record_query

pytestmark = pytest.mark.skipif(not DSN, reason='requires disposable fully migrated PostgreSQL')


def _prepared(pg):
    _,runtime,_=pg
    definition=json.loads(PATH.read_text(encoding='utf8'))
    runtime.register_definition(definition)
    with runtime.repo._conn() as db:
        db.execute("insert into users(id,username,is_agent,agent_type,tenant_id) values (%s,%s,true,'agent',%s)",
                   ('agent:handover','인계 에이전트',runtime.tenant_id))
    inst=runtime.start_definition('shift_handover',definition['version'],str(uuid4()),values=START)
    wi=runtime.repo.fetch_pending_task('cliagents','pg-reconcile',tenant_id=runtime.tenant_id)[0]
    actual,document,claim=_query_evidence();_record_query(runtime.repo,inst,wi,actual,document)
    output=unknown_draft();output['evidence']=[claim]
    output['checks'][0].update(state='observed',evidence_indices=[0])
    assert runtime.repo.save_task_result(wi['id'],output,final=True,expected_consumer='pg-reconcile')
    return runtime,inst,wi,actual,claim


def test_reconciled_citation_is_persisted_with_its_audit(pg):
    runtime,inst,wi,actual,_=_prepared(pg)
    assert runtime.poll_once()==1
    saved=runtime.repo.get_workitem(wi['id'])
    events=runtime.repo.list_events(todo_id=wi['id'])
    audits=[e for e in events if str(e.get('job_id','')).startswith('citation-reconcile:')]
    assert saved['status']=='DONE' and saved['output']['evidence'][0]['query']==actual
    assert len(audits)==1 and audits[0]['data']['changes'][0]['actual_query']==actual
    assert runtime.repo.get_instance(inst['proc_inst_id'])['status']=='RUNNING'


def test_failed_audit_rolls_back_correction_and_does_not_open_sender(pg,monkeypatch):
    runtime,inst,wi,_,claim=_prepared(pg)
    original=runtime.repo.record_events
    def fail_reconcile(events):
        if any(str(event.get('job_id','')).startswith('citation-reconcile:') for event in events):
            raise RuntimeError('simulated audit write failure')
        return original(events)
    monkeypatch.setattr(runtime.repo,'record_events',fail_reconcile)
    runtime.poll_once()
    saved=runtime.repo.get_workitem(wi['id'])
    assert saved['status']!='DONE' and saved['output']['evidence'][0]['query']==claim['query']
    assert not any(w['activity_id'].startswith('task:sender') and w['status']=='IN_PROGRESS'
                   for w in runtime.repo.list_workitems(proc_inst_id=inst['proc_inst_id']))
