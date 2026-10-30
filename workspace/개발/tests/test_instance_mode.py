"""엔진 폴링과 HTTP 연결(procsvc/instance_mode.py) — 학생 PC 의 단 하나의 구성(처리 건 엔진 + PG + 워커)."""
import contextlib
import uuid

import psycopg
import pytest

from procsvc import instance_mode, instances

from test_instances import COOLING, _start_cooling


@contextlib.contextmanager
def _claim_function_missing(dsn):
    """처리 대기 행을 집는 DB 함수가 없어진 상태(저장소 쪽 장애) — 엔진의 claim_submitted 만 실패한다."""
    sig = 'public.claim_process_workitems(text, integer, text, text, text, text)'
    with psycopg.connect(dsn, autocommit=True) as db:
        db.execute(f'ALTER FUNCTION {sig} RENAME TO claim_process_workitems_engine_test_off')
    try:
        yield
    finally:
        with psycopg.connect(dsn, autocommit=True) as db:
            db.execute('ALTER FUNCTION public.claim_process_workitems_engine_test_off(text, integer, text, text, text, text) '
                       'RENAME TO claim_process_workitems')


def test_폴링_한_바퀴에서_한_일이_실패해도_타이머는_발화한다(world):
    """B-11: 전에는 처리 대기 행 처리(poll_once)와 타이머 발화가 한 try 에 묶여, 앞이 예외면 타이머가 그 바퀴 내내 멈췄다."""
    alert, pid, decision = _start_cooling(world)
    world.clock.advance(10 * 60 + 1)
    with _claim_function_missing(world.services.dsn):
        failed = world.poll()
    assert failed == ['engine']
    assert world.row(pid, 'B_overdue')['status'] == 'DONE' and world.row(pid, 'T_notice')['status'] == 'DONE'


def test_임대가_세_번_끝난_워커_실행은_엔진_폴링의_정리_주기에_실패로_표시된다(world):
    """A-10: 전에는 이 정리가 DDL · SCM 동기화 루프에 묶여 그 주기를 늘리면 죽은 AI 실행이 FAILED 로 바뀌는 시간도 늘었다."""
    alert, pid = world.raise_alert(*COOLING)
    claimed = world.rt.repo.fetch_pending_task('cliagents', 'dead-worker', limit=1, tenant_id='hyd', proc_inst_id=pid)
    with psycopg.connect(world.services.dsn, autocommit=True) as db:
        db.execute("UPDATE todolist SET lease_until = now() - interval '1 minute', claim_count = 3 WHERE id = %s", (claimed[0]['id'],))
    world.tick = instance_mode.LEASE_SWEEP_EVERY - 2
    world.poll()
    assert world.row(pid, 'T_agent')['draft_status'] == 'STARTED', '정리 주기 전에는 그대로'
    world.poll()
    assert world.row(pid, 'T_agent')['draft_status'] == 'FAILED'


def test_강의_도우미의_경보_시작도_원천_접수_한_길로_가고_같은_경보는_같은_처리_건이다(world):
    """B-10: 경보로 처리 건을 여는 길을 원천 접수 하나로 모았다 — /api/instances/start 의 alert 도 접수 기록이 남고, 다시 보내면 409."""
    alert = {'alertId': f'ALT-HYD-01-{uuid.uuid4().hex[:8]}', 'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION', 'state': 'RAISE',
             't': world.now_iso(), 'severity': 'WARN'}
    status, body = world.api('POST', '/api/instances/start', {'alert': alert}, source_loop=True)
    assert status == 200 and body['proc_def_id'] == 'c3_cooling', body
    with psycopg.connect(world.services.dsn) as db:
        rows = db.execute("SELECT source, status FROM process_source_inbox WHERE payload->>'alertId' = %s ORDER BY id", (alert['alertId'],)).fetchall()
    assert rows == [('http', 'HANDLED')]
    status, again = world.api('POST', '/api/instances/start', {'alert': alert}, source_loop=True)
    assert status == 409 and body['proc_inst_id'] in again['detail']


def test_강의_도우미가_다른_흐름을_지정하면_경보가_가는_배포_흐름을_알려_주고_열지_않는다(world):
    alert = {'alertId': f'ALT-HYD-01-{uuid.uuid4().hex[:8]}', 'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION', 'state': 'RAISE',
             't': world.now_iso()}
    version = world.rt.repo.deployed_version('c3_pm', 'hyd')
    status, body = world.api('POST', '/api/instances/start', {'alert': alert, 'definition_id': 'c3_pm', 'version': version})
    assert status == 409 and 'c3_cooling' in body['detail'], body
    assert world.rt.repo.find_event_instance('hyd', 'c3_pm', alert['alertId']) is None


def test_사건_하나에_진행_중_처리_건은_하나뿐이다(world):
    """B-10 저장소 규칙: 같은 사건을 가리키는 두 번째 진행 중 처리 건은 DB 가 받지 않는다."""
    alert, pid = world.raise_alert(*COOLING)
    inst = world.inst(pid)
    with psycopg.connect(world.services.dsn) as db, pytest.raises(psycopg.errors.UniqueViolation):
        db.execute("INSERT INTO bpm_proc_inst (proc_inst_id, proc_def_id, status, tenant_id, variables_data, proc_def_version) "
                   "VALUES (%s, %s, 'RUNNING', 'hyd', %s, %s)",
                   (f'c3_cooling.{uuid.uuid4()}', 'c3_cooling', psycopg.types.json.Jsonb(inst['variables_data']), inst['proc_def_version']))


@pytest.mark.parametrize('method, path, body', [
    ('GET', '/api/instances', None),                       # instance_mode
    ('GET', '/api/flows/deployments', None),               # flow_deploy
    ('GET', '/api/flows', None),                           # flows_api
    ('GET', '/api/mcp/selectable', None),                  # mcp_registry
    ('GET', '/api/mcp/secrets', None),                     # mcp_secrets
    ('GET', '/api/mcp/servers', None),                     # mcp_api
    ('GET', '/api/config/export', None),                   # config_bundle
    ('GET', '/api/agent-trials/options', None),            # agent_trials
    ('POST', '/api/human-alerts', {'pattern': 'OIL_ANALYSIS', 'asset': 'HYD-01'}),   # human_alert
    ('GET', '/api/kg/ddl/meanings/x', None),               # legacy_meaning_api
])
def test_처리_엔진이_준비되기_전에는_어느_화면이든_같은_쉬운_말로_503이다(world, monkeypatch, method, path, body):
    """런타임을 받아 쓰는 경로가 저마다 문장을 갖던 것(지운 처리 엔진 스위치 이름을 학생에게 보이던 곳 포함)을 한 문장으로."""
    monkeypatch.setattr(instance_mode, '_runtime', None)
    status, body = world.api(method, path, body)
    assert (status, body['detail']) == (503, instances.NOT_READY)
