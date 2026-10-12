"""SYSTEM observations must be visible while the business transaction is still open.

Real PostgreSQL tests use ONLY the root-provisioned disposable localhost:55757 DB.
"""
import os
import threading
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4
from urllib.parse import urlsplit

import pytest
from procsvc import engine, instances, procdb, service_progress
from test_instances import DEF_PATH

DSN = os.environ.get('HYD_SYSTEM_PROGRESS_PG_DSN')


class Runtime(instances.InstanceRuntime):
    fail_after_call = False
    def _tool_of(self, wi):
        return 'isolated:mcp'
    def _service_handlers(self):
        return {'isolated:mcp': self.handle}
    def _project(self, inst):
        pass  # These tests do not invoke Neo4j or external projectors.
    def handle(self, inst, wi, now):
        values = self._require_approval(inst, wi)
        inst['variables_data'].append({'key': 'uncommitted_probe', 'value': True})
        self.repo.update_instance(inst)
        receipt, result = self._call_mcp(inst, wi, values, {'server': 'isolated', 'tool': 'approved_action', 'arguments': {'asset': '{asset}'}}, f"{inst['proc_inst_id']}:{wi['id']}", now)
        if self.fail_after_call:
            raise ValueError('isolated post-call business fault')
        wi.update(status='DONE', consumer=None, output={'receipt': receipt})
        self.repo.update_workitem(wi)
        inst.update(status='COMPLETED')
        self.repo.update_instance(inst)


def create_case(repo, tenant, hook):
    rt = Runtime(repo, engine.Definition.load(DEF_PATH), instances.Hooks(mcp_call=hook), tenant_id=tenant, consumer='isolated-engine')
    pid, todo = 'isolated-progress.' + uuid4().hex, str(uuid4())
    values = [{'key': 'approved_by', 'value': 'isolated-test-delegation'}, {'key': 'chosen_option', 'value': {'evaluation_mode': 'execution', 'execution_checked': True}}, {'key': 'asset', 'value': 'isolated-asset'}]
    repo.insert_instance({'proc_inst_id': pid, 'tenant_id': tenant, 'proc_def_id': rt.defn.id, 'proc_def_version': rt.defn.raw['version'], 'status': 'RUNNING', 'variables_data': values})
    repo.insert_workitems([{'id': todo, 'proc_inst_id': pid, 'tenant_id': tenant, 'activity_id': 'isolated-service', 'activity_name': '격리 승인 도구', 'status': 'SUBMITTED', 'agent_orch': 'hyd-process', 'user_id': 'sys:process', 'consumer': 'isolated-engine', 'tool': 'isolated:mcp', 'retry': 0, 'output': None}])
    return rt, repo.get_instance(pid), repo.get_workitem(todo)


@pytest.fixture(params=['memory', 'pg'])
def repository(request):
    tenant = 'progress-test-' + uuid4().hex
    if request.param == 'pg':
        if not DSN:
            pytest.skip('HYD_SYSTEM_PROGRESS_PG_DSN must name disposable localhost55757 DB')
        target = urlsplit(DSN)
        assert target.hostname == '127.0.0.1' and target.port == 55757 and target.path == '/hyd_system_progress_test', 'refuse non-disposable DB'
        repo = procdb.PgRepo(DSN)
        with repo._conn() as c:
            c.execute('insert into tenants(id,name) values(%s,%s)', (tenant, tenant))
    else:
        repo = procdb.MemoryRepo()
        repo.upsert_tenant({'id': tenant, 'name': tenant})
    yield repo, tenant
    if request.param == 'pg':
        with repo._conn() as c:
            c.execute('delete from events where proc_inst_id in (select proc_inst_id from bpm_proc_inst where tenant_id=%s)', (tenant,))
            c.execute('delete from bpm_proc_inst where tenant_id=%s', (tenant,))
            c.execute('delete from tenants where id=%s', (tenant,))


@pytest.mark.parametrize('outcome', ['success', 'upstream_error', 'upstream_exception', 'business_fault'])
def test_start_is_visible_to_two_readers_before_upstream_returns_and_business_is_atomic(repository, outcome):
    repo, tenant = repository
    entered, release = threading.Event(), threading.Event()
    calls = []
    def hook(server, tool, args, key):
        calls.append((server, tool, deepcopy(args), key))
        entered.set()
        assert release.wait(10), 'test failed to release isolated upstream'
        if outcome == 'upstream_exception':
            raise RuntimeError('isolated upstream exception')
        return {'status': 'failed' if outcome == 'upstream_error' else 'ok', 'error': 'isolated denial' if outcome == 'upstream_error' else None, 'result': {'text': 'isolated actual reply', 'is_error': False}}
    rt, inst, wi = create_case(repo, tenant, hook)
    rt.fail_after_call = outcome == 'business_fault'
    thread = threading.Thread(target=rt._run_service, args=(inst, wi, datetime.now(timezone.utc)), daemon=True)
    thread.start()
    try:
        assert entered.wait(5), 'upstream was not entered'
        if isinstance(repo, procdb.PgRepo):
            # PgRepo opens two separate autocommit reader connections here.
            reader_a, reader_b = procdb.PgRepo(DSN), procdb.PgRepo(DSN)
        else:
            reader_a = reader_b = repo
        events = reader_a.list_events(todo_id=wi['id'])
        starts = [e for e in events if e['event_type'] == 'tool_usage_started']
        assert len(starts) == 1 and not any(e['event_type'] == 'tool_usage_finished' for e in events)
        assert starts[0]['data']['input'] == {'asset': 'isolated-asset'}
        assert starts[0]['data']['system_observation'] is True
        if isinstance(repo, procdb.PgRepo):
            unchanged = reader_b.get_instance(inst['proc_inst_id'])
            assert 'uncommitted_probe' not in engine.variables(unchanged)
            durable_owner = reader_b.get_workitem(wi['id'])['consumer']
            assert durable_owner.startswith('isolated-engine:service:')
            assert starts[0]['data']['owner_claim_hash'] == service_progress.owner_hash(durable_owner)
            # This is the exact production SSE cursor's repository read path.
            assert any(e['id'] == starts[0]['id'] for e in reader_b.list_events_since(starts[0]['timestamp']))
    finally:
        release.set()
        thread.join(10)
    assert not thread.is_alive()
    assert len(calls) == 1 and calls[0][3] == f"{inst['proc_inst_id']}:{wi['id']}"
    evs = repo.list_events(todo_id=wi['id'])
    starts = [e for e in evs if e['event_type'] == 'tool_usage_started']
    finishes = [e for e in evs if e['event_type'] == 'tool_usage_finished']
    assert len(starts) == len(finishes) == 1
    assert starts[0]['data']['tool_use_id'] == finishes[0]['data']['tool_use_id']
    assert starts[0]['data']['attempt_id'] == finishes[0]['data']['attempt_id']
    closures = [e for e in evs if e['job_id'].startswith('SYSTEM_ATTEMPT_')]
    assert len(closures) == 1
    assert closures[0]['data']['attempt_id'] == starts[0]['data']['attempt_id']
    fresh, item = repo.get_instance(inst['proc_inst_id']), repo.get_workitem(wi['id'])
    if outcome == 'success':
        assert fresh['status'] == 'COMPLETED' and item['status'] == 'DONE'
        assert closures[0]['data']['transaction_outcome'] == 'committed'
    else:
        assert fresh['status'] == 'RUNNING' and item['output'] is None
        assert 'uncommitted_probe' not in engine.variables(fresh)
        assert closures[0]['data']['transaction_outcome'] == 'rolled_back'
        assert item['retry'] == 1
        assert finishes[0]['data']['is_error'] is (outcome != 'business_fault')


def test_nested_system_waits_for_parent_commit_and_preserves_single_failed_response(repository):
    repo, tenant = repository
    calls, audits = [], []
    reply = '참석 응답을 읽지 못했습니다 (서버 오류 503)'
    def hook(*args):
        calls.append(args)
        return {'status': 'failed', 'error': reply, 'result': {'text': reply, 'is_error': True}}
    rt, inst, wi = create_case(repo, tenant, hook)
    rt.hooks.audit = lambda *args, **kwargs: audits.append((args, kwargs))
    with rt._transition(inst['proc_inst_id']):
        rt._run_service(inst, wi, datetime.now(timezone.utc))
        assert calls == [] and repo.list_events(todo_id=wi['id']) == []
    rows = repo.list_events(todo_id=wi['id'])
    starts = [r for r in rows if r['event_type'] == 'tool_usage_started']
    finishes = [r for r in rows if r['event_type'] == 'tool_usage_finished']
    closures = [r for r in rows if r['job_id'] == 'SYSTEM_ATTEMPT_ROLLED_BACK']
    assert len(calls) == len(starts) == len(finishes) == len(closures) == 1
    assert calls[0][3] == f"{inst['proc_inst_id']}:{wi['id']}"
    assert starts[0]['data']['tool_use_id'] == finishes[0]['data']['tool_use_id']
    assert reply in str(finishes[0]['data'])
    assert len(audits) == 1 and audits[0][0][2] == 'MCP_EFFECT_FAILED'
    assert 'uncommitted_probe' not in engine.variables(repo.get_instance(inst['proc_inst_id']))
    item = repo.get_workitem(wi['id'])
    assert item['output'] is None and item['retry'] == 1
    assert closures[0]['data']['transaction_outcome'] == 'rolled_back'


def test_recovered_claim_closes_orphan_as_response_unconfirmed_without_replaying_result(repository):
    repo, tenant = repository
    calls = []
    rt, inst, wi = create_case(repo, tenant, lambda *args: calls.append(args) or {'status': 'ok', 'result': {'text': 'new actual reply', 'is_error': False}})
    attempt, use = str(uuid4()), 'orphan-use-' + uuid4().hex
    start = {'id': str(uuid4()), 'job_id': 'MCP_EFFECT_CALL', 'todo_id': wi['id'], 'proc_inst_id': inst['proc_inst_id'],
             'crew_type': 'tool', 'event_type': 'tool_usage_started',
             'data': {'system_observation': True, 'attempt_id': attempt, 'tool_use_id': use,
                      'owner_claim_hash': service_progress.owner_hash(wi['consumer'])}}
    repo.record_service_progress(tenant, inst['proc_inst_id'], wi['id'], wi['consumer'], [start])
    rt._run_service(inst, wi, datetime.now(timezone.utc))
    rows = repo.list_events(todo_id=wi['id'])
    orphan = [r for r in rows if r['event_type'] == 'tool_usage_finished' and r['data']['tool_use_id'] == use]
    assert len(orphan) == 1 and orphan[0]['data']['response_unconfirmed'] is True
    assert orphan[0]['data']['attempt_id'] == attempt
    assert 'result' not in orphan[0]['data']
    assert len(calls) == 1 and calls[0][3] == f"{inst['proc_inst_id']}:{wi['id']}"
    new_start = [r for r in rows if r['event_type'] == 'tool_usage_started' and r['id'] != start['id']]
    assert len(new_start) == 1 and new_start[0]['data']['attempt_id'] != attempt


def test_progress_storage_fault_prevents_upstream_and_does_not_commit_business(repository, monkeypatch):
    repo, tenant = repository
    calls = []
    rt, inst, wi = create_case(repo, tenant, lambda *args: calls.append(args))
    def unavailable(*args):
        raise RuntimeError('isolated journal unavailable')
    monkeypatch.setattr(repo, 'record_service_progress', unavailable)
    rt._run_service(inst, wi, datetime.now(timezone.utc))
    assert calls == []
    assert 'uncommitted_probe' not in engine.variables(repo.get_instance(inst['proc_inst_id']))
    assert repo.get_workitem(wi['id'])['output'] is None
    assert not any(e['event_type'].startswith('tool_usage') for e in repo.list_events(todo_id=wi['id']))


@pytest.mark.parametrize('wrong', ['tenant', 'owner', 'todo', 'business_event', 'orchestration'])
def test_progress_rejects_unowned_or_business_events(repository, wrong):
    repo, tenant = repository
    rt, inst, wi = create_case(repo, tenant, lambda *args: None)
    row = {'id': str(uuid4()), 'job_id': 'MCP_EFFECT_CALL', 'todo_id': wi['id'], 'proc_inst_id': inst['proc_inst_id'], 'crew_type': 'tool', 'event_type': 'tool_usage_started', 'data': {'system_observation': True, 'attempt_id': str(uuid4()), 'owner_claim_hash': service_progress.owner_hash('isolated-engine')}}
    owner = 'wrong' if wrong == 'owner' else 'isolated-engine'
    target_tenant = 'wrong' if wrong == 'tenant' else tenant
    if wrong == 'todo':
        row['todo_id'] = str(uuid4())
    if wrong == 'business_event':
        row['event_type'] = 'task_completed'
    if wrong == 'orchestration':
        changed = repo.get_workitem(wi['id'])
        changed['agent_orch'] = 'cliagents'
        repo.update_workitem(changed)
    with pytest.raises((ValueError, PermissionError)):
        repo.record_service_progress(target_tenant, inst['proc_inst_id'], wi['id'], owner, [row])
    assert not repo.list_events(todo_id=wi['id'])
