"""처리 건 저장소(procsvc/procdb.py — PgRepo) — 실제 PostgreSQL(새 업무 DB 와 같은 마이그레이션 · 시드)에 쓰고 읽는다."""
import threading
import uuid

import psycopg
from psycopg.types.json import Jsonb
import pytest

from conftest import new_database
from procsvc import procdb

TENANT = 'hyd'


@pytest.fixture(scope='module')
def repo(pg_dsn):
    with new_database(pg_dsn, schema=True) as dsn:
        yield procdb.PgRepo(dsn)


def _definition(def_id, version, note=''):
    return {'processDefinitionId': def_id, 'processDefinitionName': def_id, 'version': version, 'description': note, 'forms': {},
            'activities': [], 'events': [{'id': 's', 'type': 'startEvent'}, {'id': 'e', 'type': 'endEvent'}],
            'sequences': [{'id': 'f', 'source': 's', 'target': 'e'}]}


def _instance(repo, status='RUNNING', variables=(), start_event_id=None, def_id='p'):
    pid = f'{def_id}.{uuid.uuid4()}'
    repo.insert_instance({'proc_inst_id': pid, 'proc_def_id': def_id, 'proc_def_version': '1', 'tenant_id': TENANT, 'status': status,
                          'variables_data': list(variables), 'start_event_id': start_event_id or uuid.uuid4().hex,
                          'start_date': '2026-10-30T09:00:00.000Z'})
    return pid


def _row(repo, pid, **fields):
    wid = str(uuid.uuid4())
    repo.insert_workitems([dict({'id': wid, 'proc_inst_id': pid, 'tenant_id': TENANT, 'proc_def_id': 'p', 'version': '1', 'activity_id': 'a',
                                 'activity_name': 'a', 'status': 'TODO', 'start_date': '2026-10-30T09:00:00.000Z'}, **fields)])
    return wid


# ---------------------------------------------------------------- 정의 판본
@pytest.mark.parametrize('versions, ordered', [
    (['1', '2', '10', '9'], ['1', '2', '9', '10']),                  # P3-13: 글자 순이면 10 이 9 보다 앞이었다
    (['2.10', '2.9', '2.2'], ['2.2', '2.9', '2.10']),
    (['1', '1.1', 'beta'], ['1', '1.1', 'beta']),                    # 숫자가 아닌 판본은 숫자 판본 뒤
])
def test_정의_판본은_숫자_순으로_오래된_것부터_마지막이_최신이다(repo, versions, ordered):
    def_id = 'order_' + uuid.uuid4().hex[:6]
    for v in versions:
        repo.upsert_proc_def(_definition(def_id, v), TENANT)
    assert [r['prod_version'] for r in repo.list_definitions(TENANT) if r['id'] == def_id] == ordered
    assert sorted(v for d, v in repo.registered_versions(TENANT) if d == def_id) == sorted(versions)


def test_등록한_판본은_같은_원문만_다시_받고_다른_원문이면_거절한다(repo):
    def_id = 'immutable_' + uuid.uuid4().hex[:6]
    repo.upsert_proc_def(_definition(def_id, '1'), TENANT)
    repo.upsert_proc_def(_definition(def_id, '1'), TENANT)
    with pytest.raises(ValueError, match='새 버전'):
        repo.upsert_proc_def(_definition(def_id, '1', note='설명만 고침'), TENANT)


@pytest.mark.parametrize('version', ['', '  ', None, 1])
def test_판본_번호가_비었거나_글이_아니면_등록하지_않는다(repo, version):
    with pytest.raises(ValueError, match='version'):
        repo.upsert_proc_def(_definition('bad', version), TENANT)


# ---------------------------------------------------------------- 같은 질문 다시 보내기 (P1-02)
def _coalescing(key, events):
    return [{'key': '_runtime_coalescing', 'name': '_runtime_coalescing', 'value': {'key': key, 'events': list(events)}},
            {'key': 'answer', 'name': '답', 'value': None}]


def test_같은_질문_다시_보내기는_요청_id_하나만_더하고_다른_칸은_그대로_둔다(repo):
    pid = _instance(repo, variables=_coalescing('K', ['e1']))
    merged = repo.add_coalesced_event(pid, 'K', 'e2')
    assert merged['proc_inst_id'] == pid
    after = repo.get_instance(pid)
    values = {v['key']: v['value'] for v in after['variables_data']}
    assert values['_runtime_coalescing']['events'] == ['e1', 'e2'] and after['status'] == 'RUNNING'


@pytest.mark.parametrize('status, key, result', [('COMPLETED', 'K', None), ('RUNNING', 'OTHER', None)])
def test_끝난_처리_건이나_다른_질문에는_더하지_않는다(repo, status, key, result):
    pid = _instance(repo, status=status, variables=_coalescing('K', ['e1']))
    assert repo.add_coalesced_event(pid, key, 'e2') is result


def test_다시_보내기_한도를_넘으면_쉬운_말로_거절한다(repo):
    pid = _instance(repo, variables=_coalescing('K', [f'e{i}' for i in range(3)]))
    with pytest.raises(ValueError, match='3번 넘게'):
        repo.add_coalesced_event(pid, 'K', 'e9', limit=3)


def test_다시_보내기는_엔진이_잡은_처리_건_행을_기다렸다가_끝난_뒤의_상태를_본다(repo):
    """P1-02: 전에는 잠금 없이 읽은 옛 행 전체를 덮어써, 그 사이 엔진이 저장한 답 · 끝 상태를 지울 수 있었다."""
    pid = _instance(repo, variables=_coalescing('K', ['e1']))
    held, release, result = threading.Event(), threading.Event(), {}

    def engine_transition():
        with repo.instance_transaction(TENANT, pid):
            inst = repo.get_instance(pid)
            repo.update_instance(dict(inst, status='COMPLETED', variables_data=[
                v if v['key'] != 'answer' else dict(v, value='답 저장됨') for v in inst['variables_data']]))
            held.set()
            assert release.wait(30)

    worker = threading.Thread(target=engine_transition)
    worker.start()
    assert held.wait(30)
    other = procdb.PgRepo(repo.dsn)
    resend = threading.Thread(target=lambda: result.update(merged=other.add_coalesced_event(pid, 'K', 'e2')))
    resend.start()
    resend.join(1)
    assert resend.is_alive(), '엔진이 행을 잡은 동안 다시 보내기는 기다려야 한다'
    release.set()
    worker.join(30)
    resend.join(30)
    after = repo.get_instance(pid)
    assert result['merged'] is None and after['status'] == 'COMPLETED'
    assert {v['key']: v['value'] for v in after['variables_data']}['answer'] == '답 저장됨'


# ---------------------------------------------------------------- 읽기 스냅숏 (P1-04)
def test_읽기_스냅숏_안의_읽기는_한_시점을_보고_쓰기는_DB_가_거절한다(repo):
    pid = _instance(repo)
    with repo.read_snapshot():
        before = repo.get_instance(pid)['status']
        with psycopg.connect(repo.dsn, autocommit=True) as db:       # 스냅숏 밖의 다른 연결이 바꾼다
            db.execute("UPDATE bpm_proc_inst SET status='COMPLETED' WHERE proc_inst_id=%s", (pid,))
        assert repo.get_instance(pid)['status'] == before == 'RUNNING', '같은 스냅숏은 바뀌기 전을 본다'
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            repo.update_instance({'proc_inst_id': pid, 'status': 'RUNNING'})
    assert repo.get_instance(pid)['status'] == 'COMPLETED'


# ---------------------------------------------------------------- 엔진 집기 (P1-05)
def test_엔진_이름으로_남은_제출_행만_놓고_시스템_단계_표식과_승인_대기는_건드리지_않는다(repo):
    pid = _instance(repo)
    engine_row = _row(repo, pid, status='SUBMITTED', consumer='process-engine:host:1')
    service_row = _row(repo, pid, status='SUBMITTED', consumer='process-engine:host:1:service:abc')
    approval_row = _row(repo, pid, status='SUBMITTED', consumer='approval:waiting')
    other_engine = _row(repo, pid, status='SUBMITTED', consumer='process-engine:other:2')
    assert repo.release_engine_claims('process-engine:host:1', TENANT) == 1
    assert repo.get_workitem(engine_row)['consumer'] is None
    assert [repo.get_workitem(w)['consumer'] for w in (service_row, approval_row, other_engine)] == [
        'process-engine:host:1:service:abc', 'approval:waiting', 'process-engine:other:2']
    assert repo.release_engine_claims('process-engine:host:1', TENANT) == 0


# ---------------------------------------------------------------- 멈춘 단계 · 워커 결과
def test_멈춘_단계_후보는_보류와_실패_취소만_한_질의로_돌려준다(repo):
    pid = _instance(repo)
    stuck = {_row(repo, pid, status='PENDING'), _row(repo, pid, status='IN_PROGRESS', draft_status='FAILED'),
             _row(repo, pid, status='IN_PROGRESS', draft_status='CANCELLED')}
    _row(repo, pid, status='IN_PROGRESS', draft_status='STARTED')
    _row(repo, pid, status='DONE')
    assert {w['id'] for w in repo.stuck_workitems(TENANT, [pid])} == stuck
    assert repo.stuck_workitems(TENANT, []) == []


def test_워커_결과는_그_행을_집은_워커만_저장한다(repo):
    pid = _instance(repo)
    wid = _row(repo, pid, status='IN_PROGRESS', draft_status='STARTED', consumer='worker-1', agent_mode='COMPLETE', agent_orch='cliagents')
    with pytest.raises(ValueError, match='expected_consumer'):
        repo.save_task_result(wid, {'x': 1}, True, None)
    assert repo.save_task_result(wid, {'x': 1}, True, 'late-worker') is False
    assert repo.save_task_result(wid, {'x': 1}, True, 'worker-1') is True
    row = repo.get_workitem(wid)
    assert (row['status'], row['output'], row['consumer']) == ('SUBMITTED', {'x': 1}, None)


# ---------------------------------------------------------------- 시작 요청 id 로 고른 처리 건 (P4-05)
def test_시작_요청_id_앞부분으로_고른_처리_건은_정의_상태_빼기로_좁힌다(repo):
    prefix = 'button:' + uuid.uuid4().hex[:6] + ':'
    running = _instance(repo, start_event_id=prefix + '1', def_id='c3_spare')
    done = _instance(repo, status='COMPLETED', start_event_id=prefix + '2', def_id='c3_spare')
    triage = _instance(repo, start_event_id=prefix + '3', def_id='alert_triage')
    _instance(repo, start_event_id='other:' + uuid.uuid4().hex, def_id='c3_spare')
    every = {r['proc_inst_id'] for r in repo.list_source_runs(TENANT, None, prefix)}
    assert every == {running, done, triage}
    assert [r['proc_inst_id'] for r in repo.list_source_runs(TENANT, None, prefix, status='RUNNING', exclude_def='alert_triage')] == [running]
    assert {r['proc_inst_id'] for r in repo.list_source_runs(TENANT, 'c3_spare', prefix)} == {running, done}
    assert 'variables_data' not in repo.list_source_runs(TENANT, None, prefix)[0]


def test_판본_순서_키는_숫자_조각을_수로_비교한다():
    assert sorted(['10', '9', '1.10', '1.9', 'x'], key=procdb.version_key) == ['1.9', '1.10', '9', '10', 'x']


def _event(pid, note):
    return {'id': str(uuid.uuid4()), 'job_id': note, 'proc_inst_id': pid, 'crew_type': 'agent', 'event_type': 'task_started', 'data': {}}


def test_처리_기록_흐름은_늦게_커밋된_앞선_시각의_기록도_이어_받기_위치_뒤에서_준다(repo):
    """G2-11 · P1-13: 위치는 커밋된 기록에만 매긴다 — 시각 순서로 읽으면 늦게 커밋된(시각은 앞선) 기록이 이미 받은 위치 앞에 숨는다."""
    pid = _instance(repo)
    late = _event(pid, 'late')
    with psycopg.connect(repo.dsn) as held:                                  # 시각(트랜잭션 시작)은 앞서고 커밋은 늦은 기록
        held.execute('select record_events_bulk(%s)', (Jsonb([late]),))
        early = _event(pid, 'early')
        repo.record_events([early])
        rows = repo.list_stream_events(None, 50)
        mine = [r for r in rows if r['proc_inst_id'] == pid]
        assert [r['id'] for r in mine] == [early['id']], '커밋 전 기록은 흐름에 없다'
        cursor = mine[-1]['stream_cursor']
    after = [r for r in repo.list_stream_events(cursor, 50) if r['proc_inst_id'] == pid]
    assert [r['id'] for r in after] == [early['id'], late['id']], '이어 받기는 받은 위치부터(포함) — 늦게 커밋된 기록이 그 뒤에 온다'
    assert after[1]['timestamp'] < after[0]['timestamp'], '시각으로는 앞선 기록이다'


def test_처리_기록_흐름은_모르는_이어_받기_위치를_받지_않는다(repo):
    with pytest.raises(ValueError, match='이어 받기 위치'):
        repo.list_stream_events('2026-10-30T09:00:00Z', 10)
