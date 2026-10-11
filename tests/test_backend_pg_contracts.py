"""Disposable migrated PostgreSQL contracts. Never point HYD_BACKEND_PG_DSN at class data."""
import json
import os
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from procsvc import agent_authoring_api, agents_api, engine, instance_mode, instances, mcp_secrets, procdb
from procsvc.store import Store
from test_instances import DEF_PATH
from test_failed_attempt_trace import failing_case

DSN = os.environ.get('HYD_BACKEND_PG_DSN')
pytestmark = pytest.mark.skipif(not DSN, reason='HYD_BACKEND_PG_DSN must identify a disposable migrated PostgreSQL')


@pytest.fixture
def pg(monkeypatch, tmp_path):
    repo = procdb.PgRepo(DSN)
    tenant = 'backend-test-' + uuid4().hex
    with repo._conn() as cx:
        cx.execute("insert into tenants(id,name,mcp) values (%s,%s,%s)", (tenant, tenant, json.dumps({'mcpServers': {}})))
    audit = []
    audit_store = Store(tmp_path / 'audit.db')
    def record_audit(asset, actor, event, detail, incident=None):
        audit.append({'t': '2026-10-12T00:00:00Z', 'asset': asset, 'actor': actor, 'event': event, 'detail': detail, 'incident': incident})
        audit_store.save({}, {}, audit)
    def graph(q, **p):
        return [dict(projection_key=p['id'], projection_revision=p['revision'], projection_hash=p['payload_hash'])]
    rt = instances.InstanceRuntime(repo, engine.Definition.load(DEF_PATH),
        instances.Hooks(audit=record_audit, record_cypher=graph), tenant_id=tenant)
    monkeypatch.setattr(instance_mode, '_runtime', rt)
    app = FastAPI()
    instance_mode.mount(app, 'instance')
    agents_api.mount(app)
    agent_authoring_api.mount(app)
    yield TestClient(app), rt, audit_store
    with repo._conn() as cx:
        for table in ('bpm_proc_inst', 'activity_agent_map', 'agent_skills', 'users', 'tenant_skills',
                      'proc_def_deployment', 'proc_def_version', 'proc_def', 'mcp_secrets',
                      'execution_projection_outbox', 'tenants'):
            col = 'id' if table == 'tenants' else 'tenant_id'
            cx.execute(f'delete from {table} where {col}=%s', (tenant,))


def test_pg_work_rules_insert_update_omit_and_clear(pg):
    client, rt, _ = pg
    body = {'name': '저장 계약', 'goal': '정본 업무 규칙 적용', 'work_rules': 'hyd-plant'}
    response = client.post('/api/agents', json=body)
    assert response.status_code == 201, response.text
    aid = response.json()['id']
    assert client.get(f'/api/agents/{aid}').json()['work_rules'] == 'hyd-plant'
    body.pop('work_rules')
    assert client.put(f'/api/agents/{aid}', json=body).status_code == 200
    assert rt.repo.list_users([aid], rt.tenant_id)[0]['work_rules'] == 'hyd-plant'
    assert client.put(f'/api/agents/{aid}', json={**body, 'work_rules': None}).status_code == 200
    assert rt.repo.list_users([aid], rt.tenant_id)[0]['work_rules'] is None


def test_pg_secrets_values_and_metadata_do_not_cross_tenants(pg):
    _, rt, _ = pg
    repo, tenant = rt.repo, rt.tenant_id
    saved = mcp_secrets.put(repo, tenant, 'CONTRACT_TOKEN', 'fixture-secret', '테스터', '2026-10-12T00:00:00Z')
    assert saved['stored'] and 'fixture-secret' not in json.dumps(saved)
    store = mcp_secrets.store_for(repo)
    assert store.values(tenant) == {'CONTRACT_TOKEN': 'fixture-secret'}
    assert store.values(tenant + '-other') == {}
    assert 'fixture-secret' not in json.dumps(store.keys(tenant), default=str)
    mcp_secrets.put(repo, tenant, 'CONTRACT_TOKEN', 'rotated-fixture', '테스터', '2026-10-12T00:00:00Z')
    assert store.values(tenant)['CONTRACT_TOKEN'] == 'rotated-fixture'
    assert mcp_secrets.remove(repo, tenant, 'CONTRACT_TOKEN')['deleted']


def test_pg_failed_attempts_audit_cursor_asset_filter_and_close(pg):
    client, rt, audit_store = pg
    rt, inst, calls = failing_case({'rt': rt})
    wi = next(w for w in rt.repo.list_workitems(proc_inst_id=inst['proc_inst_id']) if w['activity_id'] == 'T_check')
    assert wi['status'] == 'PENDING' and len(calls) == 3
    events = rt.repo.list_events(todo_id=wi['id'])
    assert len([e for e in events if e['event_type'] == 'tool_usage_started']) == 3
    assert len([e for e in events if e['event_type'] == 'tool_usage_finished' and e['data']['attempt_failed']]) == 3
    assert len([e for e in events if e['event_type'] == 'error']) == 3
    assert wi['output'] is None
    persisted = audit_store.restore()[2]
    assert len([e for e in persisted if e['event'].startswith('MCP_') and e['detail'].get('attempt_failed')]) == 3
    response = client.get('/api/events', params={'proc_inst_id': inst['proc_inst_id'], 'before': str(uuid4())})
    assert response.status_code == 404, response.text
    inst['variables_data'].append({'key': 'asset', 'value': 'TEST-ASSET'})
    rt.repo.update_instance(inst)
    assert [i['proc_inst_id'] for i in rt.repo.list_instances(tenant_id=rt.tenant_id, asset='TEST-ASSET')] == [inst['proc_inst_id']]
    assert rt.repo.list_instances(tenant_id=rt.tenant_id, asset='OTHER') == []
    response = client.post(f"/api/todolist/{wi['id']}/close", json={'by': '담당자', 'reason': '연결 오류 확인 후 실습 닫기'})
    assert response.status_code == 200, response.text
    assert response.json()['end_event'] == 'closed-by-human'
    assert rt.repo.get_workitem(wi['id'])['status'] == 'CANCELLED'
