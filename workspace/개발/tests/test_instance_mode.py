"""엔진 폴링과 HTTP 연결(procsvc/instance_mode.py) — 학생 PC 의 단 하나의 구성(처리 건 엔진 + PG + 워커)."""
import contextlib
import uuid

import psycopg
import pytest

from procsvc import instance_mode, instances

from conftest import COOLING, OPERATOR


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
    alert, pid, decision = world.start_cooling()
    world.clock.advance(10 * 60 + 1)
    with _claim_function_missing(world.dsn):
        failed = world.poll()
    assert failed == ['engine']
    assert world.row(pid, 'B_overdue')['status'] == 'DONE' and world.row(pid, 'T_notice')['status'] == 'DONE'


def test_임대가_세_번_끝난_워커_실행은_엔진_폴링의_정리_주기에_실패로_표시된다(world):
    """A-10: 전에는 이 정리가 DDL · SCM 동기화 루프에 묶여 그 주기를 늘리면 죽은 AI 실행이 FAILED 로 바뀌는 시간도 늘었다."""
    alert, pid = world.raise_alert(*COOLING)
    claimed = world.rt.repo.fetch_pending_task('cliagents', 'dead-worker', limit=1, tenant_id='hyd', proc_inst_id=pid)
    with psycopg.connect(world.dsn, autocommit=True) as db:
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
    with psycopg.connect(world.dsn) as db:
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
    with psycopg.connect(world.dsn) as db, pytest.raises(psycopg.errors.UniqueViolation):
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
def test_처리_엔진이_준비되기_전에는_어느_화면이든_같은_쉬운_말로_503이다(world, method, path, body):
    """런타임을 받아 쓰는 경로가 저마다 문장을 갖던 것(지운 처리 엔진 스위치 이름을 학생에게 보이던 곳 포함)을 한 문장으로.
    G5b-07: 우리 상태를 바꿔 끼우지 않고, 기동(시작 처리)을 하지 않은 process 앱을 따로 하나 띄워 판정한다 — 켜지는 중인 process 와 같다."""
    import json
    import os
    import subprocess
    import sys
    from conftest import ROOT
    script = ("import json,sys\nfrom fastapi.testclient import TestClient\nfrom procsvc import main\n"
              "m,p,b=json.loads(sys.argv[1])\nr=TestClient(main.app).request(m,p,json=b)\n"
              "print(json.dumps([r.status_code,r.json()],ensure_ascii=False))")
    env = dict(os.environ, PYTHONUTF8='1', PYTHONPATH=os.pathsep.join(str(ROOT / d) for d in ('common', 'it/process')))
    out = subprocess.run([sys.executable, '-c', script, json.dumps([method, path, body])], env=env, capture_output=True, text=True,
                         encoding='utf8', timeout=120)
    assert out.returncode == 0, out.stderr[-2000:]
    status, answer = json.loads(out.stdout.strip().splitlines()[-1])
    assert (status, answer['detail']) == (503, instances.NOT_READY)


def test_처리_방식_조회는_처리_방식_칸_없이_폴링_상태를_싣는다(world):
    """P1-22: 처리 방식은 하나라 mode · repo 칸을 지웠다 — 화면은 runtime(폴링 상태)으로 켜지는 중 · 실패의 까닭을 보인다."""
    world.poll()
    status, body = world.api('GET', '/api/process/mode')
    assert status == 200 and 'mode' not in body and 'repo' not in body
    assert body['definition'] == 'anomaly_response' and set(body['runtime']) >= {'status', 'ready'}


def test_사건_갱신을_넘길_루프가_없으면_조용히_버리지_않고_실패한다(world):
    """P1-17: 전에는 루프가 없으면 사건 갱신을 아무 말 없이 버렸다(던져 놓은 future 의 예외도 로그로만)."""
    from procsvc import machine
    loop = world.main.loop
    world.main.loop = None
    try:
        with pytest.raises(RuntimeError, match='이벤트 루프'):
            instance_mode.on_incident_update(machine.Incident('INC-x', 'HYD-01', 'ALT-x', {}))
    finally:
        world.main.loop = loop


def test_판본_배포와_되돌리기는_등록된_사람만_하고_거절은_흐름_이름으로_말한다(world):
    """FA2 넘김 · P1-15: 전에는 배포 이력의 「누가」가 아무 글이나 받았다. W3-17(FW2 넘김): 거절 문장이 「정의id@판본」 내부 id 였다."""
    from procsvc.course_policy import HANDOVER
    from procsvc.inbox import NOT_A_PERSON
    # 수업 단계에서 배포 · 되돌리기가 열린 정의는 학생이 가져온 교대 인수인계(ShiftHandover) 하나(course_policy) — 그 흐름으로 잰다
    did = 'ShiftHandover'
    version = world.import_flow(did, HANDOVER['xml'], HANDOVER['mapping'], 'shift-handover.bpmn')
    name = world.rt.definition_for({'proc_def_id': did, 'tenant_id': world.rt.tenant_id, 'proc_def_version': version}).name
    status, body = world.api('POST', f'/api/process/definitions/{did}/deploy', {'version': version, 'by': 'OP-17', 'reason': '시험'})
    assert (status, body['detail']) == (403, NOT_A_PERSON), body
    status, body = world.api('POST', f'/api/process/definitions/{did}/rollback', {'by': '아무개', 'reason': '시험'})
    assert (status, body['detail']) == (403, NOT_A_PERSON), body
    world.api('POST', f'/api/process/definitions/{did}/deploy', {'version': version, 'by': OPERATOR['by'], 'reason': '시험'})   # 아직이면 운영 판본으로
    try:
        status, body = world.api('POST', f'/api/process/definitions/{did}/deploy', {'version': version, 'by': OPERATOR['by'], 'reason': '시험'})
        assert status == 409 and body['detail'] == f'「{name}」의 판본 {version}은(는) 이미 운영 판본입니다', body
        status, body = world.api('POST', f'/api/process/definitions/{did}/deploy', {'version': '999', 'by': OPERATOR['by'], 'reason': '시험'})
        assert status == 404 and body['detail'] == f'「{name}」에 판본 999이(가) 등록돼 있지 않습니다', body
    finally:
        # 이 시험이 배포한 것은 이 시험이 내린다 — 남기면 뒤 시험(test_flows_api)의 흐름 지우기가 「경보 경로에 배포된 흐름」 409 로 멈췄다
        world.rt.repo.clear_deployment(did, 'hyd', actor=OPERATOR['by'], reason='시험 정리')


def test_에이전트_질문_답변에_담당자가_없으면_400_담당자_정보_없음으로_거절한다(world):
    """전수 검사 01 지적 5: 기본값 「담당자」가 「누가」를 지어 넣는 모양이었고(지금은 기본값이 없다), 빈 요청은 사유 없는 422 나 「배정된 담당자만」
    403 으로 나갔다 — 다른 사람 행동과 같은 사유 한 문장으로."""
    from procsvc.inbox import NOT_A_PERSON
    for body in ({'job_id': 'j', 'answer': '예'}, {'job_id': 'j', 'answer': '예', 'by': '  '}, {'job_id': 'j', 'answer': '예', 'by': None}):
        status, out = world.api('POST', f'/api/todolist/{uuid.uuid4()}/human-response', body)
        assert (status, out['detail']) == (400, NOT_A_PERSON), (body, out)
