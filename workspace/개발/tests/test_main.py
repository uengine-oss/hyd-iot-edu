"""process HTTP · 기동(procsvc/main.py) — 학생 PC 의 단 하나의 구성(옛 처리 엔진 · 메모리판 경로 없음).

판단 접수는 처리 건의 에이전트 단계 안에서만(사건 + 지금 점유된 생산 작업), 바깥 서비스의 거절 까닭은 버리지 않고, 감사 기록은 사건으로 거른다.
"""
import asyncio
import json
import time
import urllib.error
import urllib.request
import uuid

import psycopg
import pytest

from conftest import COOLING, _docker, _run_async
from procsvc import flow_deploy, scenario_buttons as sb


@pytest.mark.parametrize('method, path, status', [
    ('POST', '/api/incidents', 405),                               # 옛 자동 파이프라인의 가이드 카드 진입 — 그 주소는 읽기(GET)만 남았다
    ('POST', '/api/incidents/INC-x/approve', 404), ('POST', '/api/incidents/INC-x/reject', 404),
    ('POST', '/api/incidents/INC-x/decide', 404), ('POST', '/api/incidents/INC-x/decision-preview', 404),
    ('POST', '/api/incidents/INC-x/work-order-retry', 404),
    ('POST', '/api/decisions/D-x/approve', 404), ('POST', '/api/decisions/D-x/reject', 404),
    ('GET', '/api/summary', 404), ('GET', '/api/definition', 404),     # 쓰는 곳 0 — 지웠다(P5-13 · P5-14)
    ('POST', '/api/kg/rules/sql', 404), ('POST', '/api/kg/ddl/sync', 404), ('POST', '/api/kg/scm/sync', 404),   # 공급 동기화 요청은 /api/kg/scm-sync 하나
    ('GET', '/api/kg/ranking-policy/rule:x', 404), ('GET', '/api/kg/bsc/conditions', 404),
])
def test_처리_건_밖의_옛_경로와_쓰는_곳_없는_경로는_없다(world, method, path, status):
    got, _ = world.api(method, path, {} if method == 'POST' else None)
    assert got == status


def test_배속은_한_곳에서_읽는다(world):
    status, out = world.api('GET', '/api/time-scale')
    assert status == 200 and out == {'time_scale': world.main.TIME_SCALE}


def test_사건_판단_조회와_경보_정책은_처리_엔진으로_답한다(world):
    alert, pid = world.raise_alert(*COOLING)
    status, incidents = world.api('GET', '/api/incidents')
    assert status == 200 and any(i['id'] == world.values(pid)['incident'] for i in incidents)
    status, policy = world.api('GET', '/api/alerts/policy?pattern=COOLER_DEGRADATION')
    assert status == 200 and policy['target']['definition'] == 'c3_cooling'


# ---------------------------------------------------------------- 판단 접수(P5-01 · P1-20 · W3-05 · P5-08)
@pytest.fixture
def producing(world):
    """냉각 처리 건 하나의 판단 단계를 워커처럼 점유한 상태 → (사건 id, 맞는 process_scope, 경보)."""
    alert, pid = world.raise_alert(*COOLING)
    consumer = 'decision-test:' + uuid.uuid4().hex[:8]
    [wi] = world.rt.repo.fetch_pending_task('cliagents', consumer, limit=1, tenant_id='hyd', proc_inst_id=pid)
    inst = world.inst(pid)
    scope = {'tenant': 'hyd', 'instance': pid, 'workitem': wi['id'], 'generation': int(wi.get('generation') or 0),
             'version': inst['proc_def_version'], 'consumer': consumer}
    return world.values(pid)['incident'], scope, alert


def _decision(incident, scope, alert, **change):
    body = {'id': 'DEC-TEST-' + uuid.uuid4().hex[:10], 'schema': 'v2', 'asset': alert['asset'],
            'origin': {'kind': 'alert', 'incident': incident, 'alertId': alert['alertId'], 'pattern': alert['pattern'], 'process_scope': scope},
            'options': [{'id': 'skill:sop-cool-11', 'sopId': 'SOP-COOL-11'}, {'id': 'skill:sop-cool-04', 'sopId': 'SOP-COOL-04'}],
            'recommended': 'skill:sop-cool-11'}
    for key, value in change.items():
        if value is ...:
            body.pop(key, None)
        else:
            body[key] = value
    return body


def _origin(body, **change):
    origin = dict(body['origin'])
    for key, value in change.items():
        if value is ...:
            origin.pop(key)
        else:
            origin[key] = value
    return origin


def test_점유된_판단_단계가_낸_판단은_승인_대기로_접수된다(world, producing):
    body = _decision(*producing)
    status, out = world.api('POST', '/api/decisions', body)
    assert status == 200 and out == {'id': body['id'], 'state': 'PENDING_APPROVAL'}, out
    status, again = world.api('POST', '/api/decisions', body)              # 같은 판단을 다시 보내면 새로 만들지 않는다
    assert status == 200 and again == {'id': body['id'], 'state': 'PENDING_APPROVAL', 'duplicate': True}
    assert world.api('GET', f"/api/decisions/{body['id']}")[1]['origin']['incident'] == producing[0]


@pytest.mark.parametrize('change, field', [
    ({'id': ...}, 'id'),
    ({'id': ['DEC-x']}, 'id'),                                    # 글이 아닌 id(전에는 500 · 장부에 남음)
    ({'id': 'D' * 201}, 'id'),
    ({'asset': ...}, 'asset'),
    ({'options': []}, 'options'),
    ({'options': 'abc'}, 'options'),
    ({'options': [{'sopId': 'SOP-COOL-11'}]}, 'options[0]'),
    ({'options': [{'id': 'skill:a'}, {'id': 'skill:a'}]}, 'options'),
    ({'recommended': 'skill:none'}, 'recommended'),
    ({'origin': 'alert'}, 'origin'),
])
def test_모양이_틀린_판단은_400_과_칸_이름으로_거절하고_장부에_남기지_않는다(world, producing, change, field):
    body = _decision(*producing, **change)
    status, out = world.api('POST', '/api/decisions', body)
    assert status == 400 and field in [p['field'] for p in out['detail']['problems']], out
    assert field in out['detail']['reason']
    if isinstance(body.get('id'), str):
        assert world.api('GET', f"/api/decisions/{body['id']}")[0] == 404          # 거절한 판단은 장부에 남지 않는다


@pytest.mark.parametrize('origin, words', [
    ({'incident': ...}, '처리 건의 에이전트 단계 안에서만'),                   # 사건 없음 — 승인할 길이 없는 판단(W3-05)
    ({'incident': '  '}, '처리 건의 에이전트 단계 안에서만'),
    ({'process_scope': ...}, '처리 건의 에이전트 단계 안에서만'),              # 0세대도 생산 작업 범위 필수(P1-20)
    ({'incident': 'INC-NONE'}, '맡은 처리 건이 없습니다'),
    ({'process_scope': {'workitem': 'not-a-uuid'}}, '작업 id 꼴이 아닙니다'),
    ({'process_scope': {'workitem': str(uuid.uuid4())}}, '소유권'),            # 다른 작업(없는 작업)
])
def test_처리_건_작업_범위가_맞지_않는_판단은_409_로_거절한다(world, producing, origin, words):
    body = _decision(*producing)
    body['origin'] = _origin(body, **origin)
    status, out = world.api('POST', '/api/decisions', body)
    assert status == 409 and words in out['detail'], out
    assert world.api('GET', f"/api/decisions/{body['id']}")[0] == 404


def test_그_작업을_점유한_워커가_아니면_판단을_쓸_수_없다(world, producing):
    """P5-08: 판단 접수는 에이전트 전용 쓰기 — 작업 · 세대가 맞아도 점유한 워커(consumer)가 다르면 받지 않는다."""
    incident, scope, alert = producing
    body = _decision(incident, dict(scope, consumer='someone-else'), alert)
    status, out = world.api('POST', '/api/decisions', body)
    assert status == 409 and 'worker claim' in out['detail']


# ---------------------------------------------------------------- 감사 기록(W2-06)
def test_사건의_감사_기록은_전체의_최근_100줄_밖이어도_그_사건으로_걸러_돌려준다(world):
    mine, other = 'INC-AUDIT-' + uuid.uuid4().hex[:6], 'INC-NOISE-' + uuid.uuid4().hex[:6]
    audit = world.main.instance_context().audit             # 감사 기록을 쓰는 길(처리 엔진 · 라우트가 받는 그 함수)
    audit('HYD-01', 'test', 'TEST_EVENT', {'n': 0}, incident=mine)
    for n in range(150):
        audit('HYD-01', 'test', 'TEST_EVENT', {'n': n}, incident=other)
    status, latest = world.api('GET', '/api/audit')
    assert status == 200 and len(latest) == 100 and all(e['incident'] == other for e in latest)
    status, rows = world.api('GET', f'/api/audit?incident={mine}')
    assert status == 200 and [e['incident'] for e in rows] == [mine]


@pytest.mark.parametrize('limit, status', [(1, 200), (500, 200), (0, 400), (501, 400)])
def test_감사_기록_한_번에_읽는_줄_수의_경계(world, limit, status):
    got, out = world.api('GET', f'/api/audit?limit={limit}')
    assert got == status
    if status == 200:
        assert len(out) <= limit
    else:
        assert '1~500' in out['detail']


# ---------------------------------------------------------------- 바깥 서비스의 거절 까닭(P5-04 · G2-12)
def test_업무_시스템이_거래를_거절하면_그_까닭을_그대로_실패_사유로_남긴다(world):
    d = {'id': 'DEC-EXEC-' + uuid.uuid4().hex[:8], 'asset': 'HYD-03', 'chosen': 'skill:purchase', 'approvedBy': 'user:kim-op',
         'options': [{'id': 'skill:purchase', 'name': '씰 키트'}], 'origin': {'pattern': 'SPARE_BELOW_MIN'}}
    item = {'skill': 'skill:purchase', 'code': 'PR_CREATE', 'system': 'sys:erp', 'value': 'sup:none', 'part_no': 'P-PMP-SEAL', 'qty': 1,
            'amount': 1}
    body = {'decision': d['id'], 'option': 'skill:purchase', 'skill': 'skill:procure-part', 'system': 'sys:erp', 'asset': 'HYD-03',
            'by': 'user:kim-op', 'params': {'supplier': 'sup:none', 'part': '씰 키트', 'part_no': 'P-PMP-SEAL', 'qty': 1, 'amount': 1}}
    request = urllib.request.Request(world.main.ENTERPRISE_URL + '/api/exec', data=json.dumps(body).encode(), method='POST',
                                     headers={'Content-Type': 'application/json', **world.instance_mode.caller_headers()})
    with pytest.raises(urllib.error.HTTPError) as direct:                 # 업무 시스템이 스스로 주는 거절 까닭(바깥에서 직접)
        urllib.request.urlopen(request, timeout=10)
    detail = json.loads(direct.value.read())['detail']
    out = world.main.exec_skill(d, item)
    assert out['ok'] is False and detail in out['error'], out
    assert f'HTTP {direct.value.code}' in out['error'] and 'Bad Request' not in out['error']


def test_정비_시점을_싣지_않은_작업지시는_카드_id_글자와_상관없이_즉시다(world):
    """G2-09: 정비 시점이 없으면 카드 id 에 night 가 들어 있는지로 「야간」을 짐작했다."""
    d = {'id': 'DEC-WO-' + uuid.uuid4().hex[:8], 'asset': 'HYD-01', 'chosen': 'skill:sop-cool-night', 'approvedBy': 'user:kim-op',
         'options': [{'id': 'skill:sop-cool-night', 'name': '쿨러 핀 세척', 'sopId': 'SOP-COOL-04'}], 'origin': {'pattern': 'COOLER_DEGRADATION'}}
    item = {'skill': 'skill:sop-cool-night', 'code': 'WO_CREATE', 'system': 'sys:cmms', 'value': '핀 세척', 'sop': 'SOP-COOL-04'}
    out = world.main.exec_skill(d, item)
    assert out['ok'] is True, out
    with psycopg.connect(world.dsn) as db:
        assert db.execute('SELECT window_label FROM ent.work_orders WHERE id=%s', (out['ref'],)).fetchone()[0] == '즉시'


# ---------------------------------------------------------------- 원천 접수(P2-01)
def test_어느_사건에도_없는_명령_응답은_기다리지_않고_할_일_없음으로_끝난다(world):
    receipt = world.ack('HYD-01', 'FUXA-' + str(int(time.time() * 1000)))
    assert receipt['status'] == 'HANDLED', receipt
    assert receipt['result']['disposition'] == 'process 가 낸 명령의 응답이 아님 — 할 일 없음'


# ---------------------------------------------------------------- 시계열 읽기(P5-05)
def test_시계열_최신값은_행이_없으면_None_이고_읽지_못하면_까닭과_함께_실패한다(world):
    world.stack.timescale.clear()
    assert world.main.latest_tag('HYD-02', 'PS1') is None
    world.tag('HYD-02', 'PS1', 171.5)
    assert world.main.latest_tag('HYD-02', 'PS1') == 171.5
    name = world.stack.timescale.box.name
    _docker('pause', name)
    try:
        with pytest.raises(world.main.TagReadError) as caught:
            world.main.latest_tag('HYD-02', 'PS1')
    finally:
        _docker('unpause', name)
    assert 'HYD-02 PS1' in str(caught.value) and '읽지 못했습니다' in str(caught.value)


# ---------------------------------------------------------------- DDL 미리보기(P5-03 · P2-21)
@pytest.mark.parametrize('body', [{'filename': 'schema.sql'}, {'filename': 'schema.sql', 'text': '   '},
                                  {'filename': 'schema.sql', 'data': 'Q1JFQVRFIFRBQkxFIHQoYSBpbnQpOw=='}])
def test_DDL_미리보기는_글이_비면_쉬운_말로_거절한다(world, body):
    """예전 base64(data) 갈래는 읽는 함수가 없어 부르면 내부 오류(이름 없음)가 학생 화면에 나왔다."""
    status, out = world.api('POST', '/api/kg/ddl/preview', body)
    assert status == 400 and 'CREATE TABLE' in out['detail'] and 'not defined' not in out['detail']


def _ddl(tables):
    return '\n'.join(f'CREATE TABLE t{i} (id int primary key, name text, qty numeric(8,2), at timestamptz);' for i in range(tables))


def test_DDL_미리보기는_수업_글자_한도를_넘으면_해석하지_않고_거절한다(world):
    from procsvc.course_policy import TEXT_MAX
    text = _ddl(4000)
    assert len(text) > TEXT_MAX
    status, out = world.api('POST', '/api/kg/ddl/preview', {'filename': 'big.sql', 'text': text})
    assert status == 400 and f'{TEXT_MAX:,}자 이하' in out['detail'] and f'{len(text):,}자' in out['detail']


def test_제공_DDL은_미리보기에서_표와_열을_돌려준다(world):
    from procsvc.course_policy import DEFINITIONS
    text = (DEFINITIONS.parent.parent / 'portal' / 'www' / 'samples' / 'legacy-plant-db.sql').read_text(encoding='utf8')
    status, plan = world.api('POST', '/api/kg/ddl/preview', {'filename': 'legacy-plant-db.sql', 'text': text})
    assert status == 200 and plan['chars'] == len(text) and plan['inputs'], plan


def test_큰_DDL을_해석하는_동안에도_process는_다른_요청에_답한다(world):
    """P5-03: 해석을 이벤트 루프에서 돌려 몇 초 동안 상태 확인 · 원천 접수가 멈췄다 — 이제 작업 스레드에서 돈다."""
    import httpx
    from procsvc.course_policy import TEXT_MAX
    n = 1
    while len(_ddl(n * 2)) <= TEXT_MAX:
        n *= 2
    text = _ddl(n)

    async def measure():
        """미리보기 한 번이 도는 동안 이벤트 루프가 얼마나 오래 멈췄는가(10 ms 마다 깨는 눈금의 가장 긴 틈)."""
        gaps, done = [], asyncio.Event()

        async def ticker():
            last = time.monotonic()
            while not done.is_set():
                await asyncio.sleep(0.01)
                now = time.monotonic()
                gaps.append(now - last)
                last = now
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=world.main.app), base_url='http://process', timeout=120) as client:
            tick = asyncio.create_task(ticker())
            started = time.monotonic()
            response = await client.post('/api/kg/ddl/preview', json={'filename': 'big.sql', 'text': text})
            took = time.monotonic() - started
            done.set()
            await tick
        return response, took, max(gaps)
    response, took, longest = _run_async(measure())
    assert response.status_code == 200, response.text
    assert took > 1.0, took                                   # 해석이 루프를 멈췄다면 보일 만큼 무거운 글이다
    assert longest < took / 3, (longest, took)                # 그동안 루프는 계속 돌았다(전에는 가장 긴 틈 ≈ 해석 시간)


# ---------------------------------------------------------------- 수업 버튼(P5-18 · P4-24)
def _night_anchor(dsn):
    with psycopg.connect(dsn) as db:
        return db.execute("SELECT first_at FROM ent.maintenance_window_rules WHERE kind='N'").fetchone()[0]


def test_거절된_재고_보충_누름은_업무_시각을_옮기지_않고_감사_기록에_까닭이_남는다(world):
    flow_deploy.deploy_reset(world.rt, 'user:kim-op', '거절 확인', include_class=True)      # 재고 보충 흐름이 배포돼 있지 않은 상태
    try:
        # 재고 보충 표시가 있는 수업 시작 상태 — 앞 테스트가 흐름 C 를 끝내 표시를 지웠으면 「이미 처리됐습니다」로 다른 까닭의 거절이 된다(전체 테스트 1)
        world.main._entsim_post(*sb.SCENARIOS['C']['reset'])
        before = _night_anchor(world.dsn)
        status, out = world.api('POST', '/api/scenario/C/start', {'by': 'user:kim-op'})
        assert status == 409 and '배포되어 있지 않습니다' in out['detail'], out
        assert _night_anchor(world.dsn) == before
        press = next(e for e in world.main.audit_log if e['event'] == 'SCENARIO_BUTTON')
        assert press['detail']['refused'] is True and press['detail']['error'] == out['detail'] and press['detail']['reanchored'] is False
    finally:
        world.install_course_flows()


# ---------------------------------------------------------------- 기동(결정 6 · G5b-03) · 끄기 감시(P5-16)
def test_다시_켜면_저장한_사건_판단_감사가_같은_사전으로_돌아온다(world):
    alert, pid = world.raise_alert(*COOLING)
    incident = world.values(pid)['incident']
    incidents, book, audit = world.main.incidents, world.main.book, world.main.audit_log
    world.restart()
    assert world.main.incidents is incidents and incident in incidents      # 다른 모듈이 쥔 사전(ProcessContext)이 그대로 새 값을 본다
    assert world.main.book is book and world.main.audit_log is audit
    assert any(e.get('incident') == incident for e in audit)


def test_백그라운드_반복이_끝나면_상태_확인이_그_이름과_까닭을_싣는다(world):
    async def broken():
        raise RuntimeError('시험: 반복이 멈춤')

    async def run():
        task = world.main.background(broken(), '시험 반복')
        await asyncio.gather(task, return_exceptions=True)
        await asyncio.sleep(0)                              # 끝남 알림(_watch)이 불릴 차례를 준다
    try:
        _run_async(run())
        status, out = world.api('GET', '/healthz')
        assert status == 503 and out['stopped_loops']['시험 반복'] == 'RuntimeError: 시험: 반복이 멈춤'
    finally:
        world.main.state.get('stopped_loops', {}).pop('시험 반복', None)      # 다음 테스트의 상태 확인에 남지 않게


def test_공급사_견적_동기화를_요청하면_한_번_옮기고_보고를_돌려준다(world):
    """G3a-25(FB 넘김): 수업 지식 적재(scripts/class_knowledge.py)가 매뉴얼을 넣기 전에 부르는 길 — 60초 반복을 기다리지 않는다.
    보고는 동기화 그대로(missing_part = 그래프에 없는 부품의 견적 — 부른 쪽이 그 좌표로 멈춘다)."""
    status, first = world.api('POST', '/api/kg/scm-sync', {})
    assert status == 200, first
    assert first['source_rows'] > 0 and isinstance(first['missing_part'], list)
    status, again = world.api('POST', '/api/kg/scm-sync', {})
    assert status == 200 and again['changed'] == 0, again                  # 이미 옮긴 것은 다시 쓰지 않는다


def test_판단_조회는_안마다_승인할_수_있는_역할을_싣고_장부_원본은_그대로다(world, producing):
    """FA1 넘김(W1-11 · W1-25): 화면이 역할 규칙 사본 없이 단추를 켜고 끄게 — 그 안의 승인 역할이거나 그보다 높은 역할, 등급 낮은 순."""
    roles = {'role:operator': {'level': 1}, 'role:maint-mgr': {'level': 2}, 'role:plant-mgr': {'level': 3}}
    body = _decision(*producing, roles=roles, options=[
        {'id': 'skill:sop-cool-11', 'sopId': 'SOP-COOL-11', 'approver': {'id': 'role:maint-mgr', 'level': 2}},
        {'id': 'skill:sop-cool-04', 'sopId': 'SOP-COOL-04'}])                            # 승인 역할이 없는 안 = 역할 표 전부
    status, out = world.api('POST', '/api/decisions', body)
    assert status == 200, out
    status, got = world.api('GET', f"/api/decisions/{body['id']}")
    assert status == 200
    assert [o['approvable_roles'] for o in got['options']] == [['role:maint-mgr', 'role:plant-mgr'],
                                                               ['role:operator', 'role:maint-mgr', 'role:plant-mgr']]
    assert all('approvable_roles' not in o for o in world.main.book[body['id']]['options'])


def test_명령_관문이_감사_토픽에_낸_거절을_process_가_Kafka_에서_받아_접수한다(world, brokers, monkeypatch):
    """G3b-9: 관문 거절(audit · CMD_REJECTED)은 process 가 구독해야 원천 접수(REJECT)가 된다 — 실제 Redpanda 에 내고 실제 consume() 이 받는다."""
    from aiokafka import AIOKafkaProducer
    from conftest import until
    from hydcommon import topics
    main = world.main
    cmd = 'CMD-KAFKA-' + uuid.uuid4().hex[:8]
    rejected = {'t': '2026-11-02T09:00:00Z', 'incident': None, 'asset': 'HYD-01', 'actor': 'cmd-gateway', 'event': 'CMD_REJECTED',  # gw/main.py 의 꼴
                'detail': {'cmdId': cmd, 'check': 'MODE', 'reason': 'mode LOCAL', 'reason_text': '설비가 현장 조작 상태라 원격 명령을 받지 않습니다'}}
    monkeypatch.setenv('KAFKA_BOOTSTRAP', brokers.kafka)

    def received():
        with psycopg.connect(world.dsn) as db:
            return db.execute("SELECT kind FROM process_source_inbox WHERE topic=%s AND event_key=%s",
                              (topics.K_AUDIT, json.dumps(['command-reject', cmd], separators=(',', ':')))).fetchall()

    async def run():
        task = asyncio.create_task(main.consume())
        sender = AIOKafkaProducer(bootstrap_servers=brokers.kafka, value_serializer=lambda v: json.dumps(v).encode())
        await sender.start()
        try:
            await sender.send_and_wait(topics.K_AUDIT, rejected, key=topics.asset_key('HYD-01').encode())
            await asyncio.to_thread(until, received, 'process 가 감사 토픽의 관문 거절을 60초 안에 접수하지 않았다', 60)
        finally:
            await sender.stop()
            task.cancel()
            for client in (main.consumer_client, main.producer):
                if client is not None and client is not world.kafka:
                    await client.stop()
    try:
        _run_async(run())
    finally:
        main.producer = world.kafka            # world 의 송신 기록기로 되돌린다(consume 이 실제 송신기로 바꿨다)
    assert received() == [('REJECT',)]


def test_다른_사이트의_양식이_본문_없는_수업_버튼_경로를_부르면_403이고_실행하지_않는다():
    """넘김 FA2 → FO(보안): /api/scenario/A/{act} 는 본문이 없어도 된다 — 다른 사이트 페이지의 양식 POST(단순 요청)로 설비 주입이 일어났다."""
    from fastapi.testclient import TestClient
    from hydcommon.service import CROSS_SITE_REFUSED
    from procsvc import main
    r = TestClient(main.app).post('/api/scenario/A/inject', headers={'Sec-Fetch-Site': 'cross-site'})
    assert (r.status_code, r.json()) == (403, {'detail': CROSS_SITE_REFUSED})


def test_끄기는_작업_스레드에_맡긴_처리_건_갱신이_끝날_때까지_기다린다(world):
    """FA1 검증 §4-6 · FA2 검증 P5-17: 끄기(main._shutdown)와 world 닫기가 작업 스레드의 사건 갱신(instance_mode._schedule)을 기다리지 않고
    저장소를 닫아, 끄는 순간의 갱신이 닫힌 저장소에 부딪히거나 다음 테스트 준비 중에 앞 world 의 갱신이 돌았다."""
    import threading
    from procsvc import instance_mode
    started, gate, finished = threading.Event(), threading.Event(), []

    def update():                                   # 작업 스레드에서 도는 처리 건 갱신 하나(끝을 시험이 정한다)
        started.set()
        gate.wait(30)
        finished.append(world.main.store.db.execute('SELECT 1').fetchone()[0])    # 저장소가 아직 열려 있어야 한다
    instance_mode._schedule(update)
    assert started.wait(30), '갱신이 작업 스레드에서 시작하지 않았다'
    import concurrent.futures
    drain = asyncio.run_coroutine_threadsafe(world.main.drain_scheduled_updates(), world.loop_thread.loop)
    with pytest.raises(concurrent.futures.TimeoutError):           # 도는 갱신이 있는 동안 끝나지 않아야 한다
        drain.result(timeout=1)
    gate.set()
    drain.result(timeout=30)
    assert finished == [1]


def test_끄기는_송신기를_보낸_뒤_닫고_폴링을_멈추고_사건_저장소를_닫는다(world):
    """FA2 검증 P5-17: 끄기(main._shutdown)의 저장소 · 송신기 정리에 시험이 없었다 — 끈 뒤 저장소에 쓰면 닫힌 저장소 오류여야 한다."""
    import sqlite3
    from procsvc import instance_mode
    recorder = world.main.producer
    asyncio.run_coroutine_threadsafe(world.main._shutdown(), world.loop_thread.loop).result(timeout=120)
    assert recorder.stopped is True and world.main.producer is None and instance_mode._poll_task is None
    with pytest.raises(sqlite3.ProgrammingError):
        world.main.store.db.execute('SELECT 1')


def test_설비의_일이_아닌_감사_기록은_HYD_01_의_키로_보내지_않는다(world):
    """가짜 · 해피패스 조사 8: 설비 코드가 아닌 감사 기록(조치 방법 편집 · 설정 되돌리기 — asset '-')을 HYD-01 의 Kafka 키로 바꿔 보냈다."""
    from conftest import until
    from hydcommon import topics
    world.main._audit('-', 'user:me', 'KEY_TEST_NO_ASSET', {})
    world.main._audit('HYD-02', 'user:me', 'KEY_TEST_ASSET', {})

    def keys():
        return {v['event']: k for t, k, v in world.kafka.sent if t == topics.K_AUDIT and v['event'].startswith('KEY_TEST')}
    until(lambda: len(keys()) == 2, '감사 기록 둘이 송신기에 닿음')
    assert keys() == {'KEY_TEST_NO_ASSET': None, 'KEY_TEST_ASSET': 'hyd02'}
