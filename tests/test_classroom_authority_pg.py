"""Real PostgreSQL concurrency, isolated from all classroom databases."""
import os
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg import sql
import pytest

from procsvc.classroom_authority import Authority, Denied, key_hash
from test_manual_extraction import document, rt

DSN = os.getenv('HYD_CLASSROOM_TEST_DSN')
pytestmark = pytest.mark.skipif(not DSN, reason='requires disposable classroom authority PostgreSQL')
KEY = 'test-classroom-key-' + 'x'*32
DOC = 'a'*64
POLICY = dict(profile=dict(model='class-test-model', revision='1'), documents={DOC: {'source_id': 'approved-source'}},
              max_concurrency=2, total_calls=3, total_input_bytes=1000, total_output_tokens=300,
              actions={'manual_extract': dict(max_seconds=60, max_calls=3, max_input_bytes=1000, max_output_tokens=300)})


@pytest.fixture
def authority():
    target = urlsplit(DSN)
    assert target.hostname == '127.0.0.1' and target.port == 55758 and target.path == '/hyd_classroom_test'
    name = 'classroom_test_'+uuid4().hex
    with psycopg.connect(DSN, autocommit=True) as db:
        for role in ('anon', 'authenticated'):
            if not db.execute('select 1 from pg_roles where rolname=%s', (role,)).fetchone():
                db.execute(sql.SQL('CREATE ROLE {}').format(sql.Identifier(role)))
        db.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(name)))
    def connect():
        return psycopg.connect(DSN, options='-c search_path='+name, row_factory=dict_row)
    with connect() as db:
        db.execute((Path(__file__).parents[1]/'it/supabase/migrations/20261027000065_classroom_authority.sql').read_text(encoding='utf8'))
        db.execute("INSERT INTO hyd_classroom_grants(key_hash,subject,scope,policy,expires_at) VALUES (%s,'student-1','class-1',%s,now()+interval '1 day')",
                   (key_hash(KEY), Jsonb(POLICY)))
    yield Authority(connect), connect
    with psycopg.connect(DSN, autocommit=True) as db:
        db.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(name)))


def test_content_approval_and_unknown_actions_fail_closed(authority):
    auth, _ = authority
    assert auth.authorize_document(KEY, DOC)['document']['source_id'] == 'approved-source'
    with pytest.raises(Denied): auth.authorize_document(KEY, 'b'*64)
    with pytest.raises(Denied): auth.authorize_document('wrong-'*10, DOC)
    with pytest.raises(Denied): auth.reserve(KEY, 'arbitrary_prompt', {'sha256': DOC})


def test_startup_session_rechecks_grant_without_consuming_budget(authority):
    auth, connect = authority
    assert auth.session(KEY) == {'status': 'ok', 'service': 'classroom-execution'}
    with connect() as db:
        assert db.execute('SELECT count(*) AS n FROM hyd_classroom_runs').fetchone()['n'] == 0
        assert db.execute('SELECT calls FROM hyd_classroom_grants').fetchone()['calls'] == 0
        db.execute('UPDATE hyd_classroom_grants SET enabled=false')
    with pytest.raises(Denied): auth.session(KEY)


def test_concurrent_duplicate_requests_have_one_durable_reservation(authority):
    auth, connect = authority
    with ThreadPoolExecutor(max_workers=8) as pool:
        rows = list(pool.map(lambda _: auth.reserve(KEY, 'manual_extract', {'sha256': DOC}), range(8)))
    assert len({r['id'] for r in rows}) == 1 and sum(not r['reused'] for r in rows) == 1
    assert Authority(connect).reserve(KEY, 'manual_extract', {'sha256': DOC})['id'] == rows[0]['id']


def test_concurrent_paid_call_charge_cannot_exceed_total_budget(authority):
    auth, connect = authority
    run = auth.reserve(KEY, 'manual_extract', {'sha256': DOC})
    def charge(_):
        try:
            auth.charge(KEY, run['id'], input_bytes=100, max_output_tokens=100)
            return True
        except Denied:
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(charge, range(8))) == 3
    with connect() as db:
        row = db.execute('SELECT calls,input_bytes,output_tokens FROM hyd_classroom_grants').fetchone()
        assert row == dict(calls=3, input_bytes=300, output_tokens=300)


@pytest.mark.parametrize('field,value', [('input_bytes', 1001), ('max_output_tokens', 301), ('input_bytes', True)])
def test_oversized_requests_never_charge_or_call_model(authority, field, value):
    auth, connect = authority
    run = auth.reserve(KEY, 'manual_extract', {'sha256': DOC})
    request = dict(input_bytes=100, max_output_tokens=100); request[field] = value
    with pytest.raises(Denied): auth.charge(KEY, run['id'], **request)
    with connect() as db:
        assert db.execute('SELECT calls FROM hyd_classroom_grants').fetchone()['calls'] == 0


def test_failed_run_does_not_become_success_or_free_retry(authority):
    auth, _ = authority
    run = auth.reserve(KEY, 'manual_extract', {'sha256': DOC})
    auth.charge(KEY, run['id'], input_bytes=100, max_output_tokens=100)
    auth.finish(KEY, run['id'], validated=False)
    again = auth.reserve(KEY, 'manual_extract', {'sha256': DOC})
    assert again['state'] == 'FAILED' and again['result_ref'] is None and again['reused']
    with pytest.raises(Denied): auth.charge(KEY, run['id'], input_bytes=100, max_output_tokens=100)


def test_revocation_policy_changes_expiry_and_concurrency_are_enforced(authority):
    auth, connect = authority
    first = auth.reserve(KEY, 'manual_extract', {'sha256': DOC, 'approved_variant': 1})
    auth.reserve(KEY, 'manual_extract', {'sha256': DOC, 'approved_variant': 2})
    with pytest.raises(Denied): auth.reserve(KEY, 'manual_extract', {'sha256': DOC, 'approved_variant': 3})
    with connect() as db:
        db.execute("UPDATE hyd_classroom_runs SET deadline=now()-interval '1 second' WHERE id=%s", (first['id'],))
    assert auth.reserve(KEY, 'manual_extract', {'sha256': DOC, 'approved_variant': 1})['state'] == 'EXPIRED'
    third = auth.reserve(KEY, 'manual_extract', {'sha256': DOC, 'approved_variant': 3})
    with connect() as db:
        new = deepcopy(POLICY); new['profile']['revision'] = '2'
        db.execute('UPDATE hyd_classroom_grants SET policy=%s', (Jsonb(new),))
    with pytest.raises(Denied, match='판본'): auth.charge(KEY, third['id'], input_bytes=10, max_output_tokens=10)
    with connect() as db: db.execute('UPDATE hyd_classroom_grants SET enabled=false')
    with pytest.raises(Denied): auth.authorize_document(KEY, DOC)


def test_only_validated_results_can_be_marked_done(authority):
    auth, _ = authority
    run = auth.reserve(KEY, 'manual_extract', {'sha256': DOC})
    with pytest.raises(Denied): auth.finish(KEY, run['id'], validated=True)
    auth.finish(KEY, run['id'], validated=True, result_ref='verified-artifact')
    again = auth.reserve(KEY, 'manual_extract', {'sha256': DOC})
    assert again['state'] == 'DONE' and again['result_ref'] == 'verified-artifact'


def test_worker_cache_binding_and_private_charge_use_live_policy(authority):
    auth, connect = authority
    contract = {'sha256': DOC, 'cache_key': 'approved-cache'}
    run = auth.reserve(KEY, 'manual_extract', contract)
    context = auth.execution_context('student-1', 'segment-before-bind', 'approved-cache')
    assert context['run_id'] == str(run['id'])
    with pytest.raises(Denied): auth.execution_context('other-student', 'segment-before-bind', 'approved-cache')
    with pytest.raises(Denied): auth.execution_context('student-1', 'unbound', 'other-cache')
    auth.bind_work(KEY, run['id'], 'first-segment')
    auth.charge_execution(run['id'], input_bytes=100, max_output_tokens=100)
    assert auth.read_run(KEY, run['id'])['calls'] == 1
    # A limit/document change without a model revision must also invalidate the
    # old reservation; a concurrent endpoint cannot bind it after revocation.
    policy = deepcopy(POLICY); policy['total_calls'] = 2
    with connect() as db:
        db.execute('UPDATE hyd_classroom_grants SET policy=%s', (Jsonb(policy),))
    with pytest.raises(Denied): auth.reserve(KEY, 'manual_extract', contract)
    with pytest.raises(Denied): auth.bind_work(KEY, run['id'], 'first-segment')
    with pytest.raises(Denied): auth.execution_context('student-1', 'first-segment', 'approved-cache')
    with pytest.raises(Denied): auth.charge_execution(run['id'], input_bytes=100, max_output_tokens=100)


def test_managed_http_uses_approved_server_document_and_rejects_raw_llm_calls(authority, document, rt, tmp_path):
    from fastapi.testclient import TestClient
    from procsvc.classroom_api import create_app
    auth, connect = authority
    archive, source, proposal = document
    runtime, _ = rt
    policy = deepcopy(POLICY)
    policy['documents'] = {source['sha256']: {'source_id': source['source_id']}}
    with connect() as db:
        db.execute("UPDATE hyd_classroom_grants SET policy=%s,subject='hyd'", (Jsonb(policy),))
    app = create_app(auth, source_loader=lambda doc: archive.get('hyd', doc['source_id']),
                     runtime_factory=lambda subject: runtime, catalog_factory=lambda rt: {},
                     archive_factory=lambda subject: archive)
    client = TestClient(app)
    headers = {'Authorization': 'Bearer '+KEY}
    first = client.post('/v1/classroom/extractions', headers=headers, json={'sha256': source['sha256']})
    assert first.status_code == 200, first.text
    second = client.post('/v1/classroom/extractions', headers=headers, json={'sha256': source['sha256']})
    assert first.json()['run_id'] == second.json()['run_id'] and second.json()['reused']
    assert client.get('/v1/classroom/runs/'+first.json()['run_id'], headers=headers).json()['calls'] == 0
    assert client.post('/v1/chat/completions', headers=headers, json={'messages': []}).status_code == 404
    assert client.post('/key/generate', headers=headers, json={}).status_code == 404
    assert client.post('/v1/classroom/extractions', headers=headers,
                       json={'sha256': source['sha256'], 'prompt': 'unapproved', 'model': 'other'}).status_code == 422
    assert client.post('/v1/classroom/extractions', headers=headers, json={'sha256': 'b'*64}).status_code == 403
    result_url = '/v1/classroom/runs/'+first.json()['run_id']+'/result'
    assert client.get(result_url, headers=headers).json()['preview'] is None
    assert client.get(result_url, headers={'Authorization': 'Bearer '+'wrong-'*10}).status_code == 403
    from test_manual_cache import complete
    complete(runtime, proposal)
    finished = client.get(result_url, headers=headers)
    assert finished.status_code == 200, finished.text
    assert finished.json()['status'] == 'DONE' and finished.json()['cache']['validated']
    assert finished.json()['preview']['previous_batch'] is None
    assert 'reviewed' not in finished.json()['preview']
    repeated = client.get(result_url, headers=headers)
    assert repeated.status_code == 200, repeated.text
    first_value, repeated_value = finished.json(), repeated.json()
    assert first_value['preview'].pop('batch') != repeated_value['preview'].pop('batch')
    assert first_value == repeated_value
    state = client.get('/v1/classroom/runs/'+first.json()['run_id'], headers=headers).json()
    assert state['state'] == 'DONE' and state['result_ref'] and state['calls'] == 0
    import httpx
    from procsvc.classroom_client import Client
    def bridge(request):
        response = client.request(request.method, request.url.path, headers=dict(request.headers), content=request.content)
        return httpx.Response(response.status_code, content=response.content, headers={'content-type':'application/json'})
    student = Client('https://class.example', lambda: KEY, tmp_path/'student.sqlite3', transport=httpx.MockTransport(bridge))
    renamed = archive.save('hyd', 'student-alias.txt', archive.original('hyd', source['source_id']))
    renamed = archive.get('hyd', renamed['source_id'])
    joined = student.start('hyd', renamed)
    received = student.result('hyd', renamed, joined['instance'], 'student-current-head')
    assert joined['cache']['reused'] and received['preview']['filename'] == 'student-alias.txt'
    assert received['preview']['previous_batch'] == 'student-current-head'
    assert received['preview']['procedures'][0]['anchor']['source_id'] == renamed['source_id']
    with connect() as db:
        db.execute('UPDATE hyd_classroom_grants SET enabled=false')
    assert client.post('/v1/classroom/extractions', headers=headers, json={'sha256': source['sha256']}).status_code == 403
    assert client.get(result_url, headers=headers).status_code == 403


def test_status_observes_deadline_without_a_new_reservation(authority):
    auth, connect = authority
    run = auth.reserve(KEY, 'manual_extract', {'sha256': DOC})
    with connect() as db:
        db.execute("UPDATE hyd_classroom_runs SET deadline=now()-interval '1 second' WHERE id=%s", (run['id'],))
    assert auth.read_run(KEY, run['id'])['state'] == 'EXPIRED'


@pytest.mark.parametrize('failure', ['invalid_result', 'worker_failed', 'expired'])
def test_managed_result_never_certifies_failed_invalid_or_expired_work(authority, document, rt, monkeypatch, failure):
    from fastapi.testclient import TestClient
    from procsvc import classroom_api
    auth, connect = authority
    archive, source, _ = document
    runtime, _ = rt
    policy = deepcopy(POLICY)
    policy['documents'] = {source['sha256']: {'source_id': source['source_id']}}
    with connect() as db:
        db.execute("UPDATE hyd_classroom_grants SET policy=%s,subject='hyd'", (Jsonb(policy),))
    client = TestClient(classroom_api.create_app(auth,
        source_loader=lambda doc: archive.get('hyd', doc['source_id']), runtime_factory=lambda _: runtime,
        catalog_factory=lambda _: {}, archive_factory=lambda _: archive))
    headers = {'Authorization': 'Bearer '+KEY}
    run_id = client.post('/v1/classroom/extractions', headers=headers, json={'sha256': source['sha256']}).json()['run_id']
    if failure == 'invalid_result':
        def invalid(*args): raise ValueError('semantic validation rejected')
        monkeypatch.setattr(classroom_api.manual_cache, 'result', invalid)
    elif failure == 'worker_failed':
        wi = runtime.repo.fetch_pending_task('cliagents', 'failed-worker')[0]
        runtime.repo.update_task_error(wi['id'])
    else:
        with connect() as db:
            db.execute("UPDATE hyd_classroom_runs SET deadline=now()-interval '1 second' WHERE id=%s", (run_id,))
    response = client.get('/v1/classroom/runs/'+run_id+'/result', headers=headers)
    assert response.status_code == {'invalid_result': 422, 'worker_failed': 200, 'expired': 409}[failure]
    row = auth.read_run(KEY, run_id)
    assert row['state'] != 'DONE' and row['result_ref'] is None and row['calls'] == 0
    if failure != 'invalid_result':
        assert client.post('/v1/classroom/extractions', headers=headers, json={'sha256': source['sha256']}).status_code == 409
