"""수업 버튼(procsvc/scenario_buttons.py) — [정기 정비 시작] · [예비품 구매 시작]의 경보 · 거절, 진행 중 [업무 데이터 초기화] 거절, 시나리오 시각 기준점을 붙잡는 처리 건.

실제 업무 DB(enterprise-sim) · 실제 엔진으로 버튼과 같은 함수를 부른다. 처리 건은 에이전트 단계에서 멈춘 채(진행 중) 둔다.
"""
import uuid
from datetime import datetime, timezone

import pytest

from fastapi import HTTPException

from conftest import definition_version
from hydcommon import topics
from procsvc import scenario_buttons as sb

PERSON = {'by': '담당자', 'user_id': 'user:me', 'roles': ['role:purchasing']}
START = {'asset': 'HYD-01', 'shift_label': '야간 → 주간', 'as_of': '2026-10-30T06:00:00+09:00', 'work_notes': '메모'}


def _press(world, key):
    """버튼 누름(초기화 → 검사 · 경보 → 원천 접수)과 같은 길. 돌려줌 = 처리 건 id."""
    world.main._entsim_post(*sb.SCENARIOS[key]['reset'])
    prep = sb.prepare(key, world.instance_mode.enterprise_read, world.rt, world.main._scenario_route, sb.who(PERSON))
    receipt = world.receive(topics.K_ALERTS, prep['alert'])
    assert receipt['status'] == 'HANDLED', receipt
    return receipt['result']['instance']


@pytest.mark.parametrize('body, expected', [
    ({'by': '담당자', 'user_id': 'user:me', 'role': 'role:purchasing'}, PERSON),
    ({'by': '가' * 100, 'roles': ['r'] * 9}, {'by': '가' * 80, 'user_id': None, 'roles': ['r'] * 5}),
], ids=['담당자', '긴 값은 자름'])
def test_누른_사람은_포털이_보낸_담당자_그대로다(body, expected):
    assert sb.who(body) == expected


@pytest.mark.parametrize('body', [None, {}, {'by': '  ', 'user_id': 'user:me'}], ids=['본문 없음', '칸 없음', '빈 칸'])
def test_누른_사람이_비면_자리표를_지어내지_않고_400_으로_거절한다(body):
    """옛 판은 빈 칸을 「나 미선택」으로 채워 경보 근거와 처리 기록에 사람처럼 남겼다."""
    with pytest.raises(HTTPException) as refused:
        sb.who(body)
    assert refused.value.status_code == 400 and '담당자 정보 없이 온 요청' in refused.value.detail


def test_버튼_경보는_업무_감시와_같은_계약이고_누른_사람과_시각을_근거에_싣는다():
    row = {'part_no': 'P-PMP-SEAL', 'available': 1, 'reorder_point': 2, 'need_qty': 6, 'below_since': 'x', 'reserved_for': 'HYD-03'}
    now = datetime(2026, 10, 30, 6, 0, 1, tzinfo=timezone.utc)
    alert = sb.build_alert('C', row, now, PERSON)
    assert alert['alertId'] == 'ERP-SPARE_BELOW_MIN-P-PMP-SEAL-20261030060001' and alert['source'] == 'erp' and alert['state'] == 'RAISE'
    assert alert['evidence']['spare_below_min'] is True and alert['evidence']['requested_user'] == 'user:me'
    assert alert['evidence']['requested_at'] == '2026-10-30T06:00:01+00:00' and alert['asset'] == 'HYD-03'


def test_같은_시나리오_처리_건이_진행_중이면_다시_누름을_거절한다(world):
    started = _press(world, 'C')
    with pytest.raises(sb.Refused, match='이미 진행 중입니다') as caught:
        sb.refusal('C', world.instance_mode.enterprise_read, world.rt, world.main._scenario_route)
    # 어느 건인지 말하고(시작한 때), 화면에 없는 「카드의 '처리 중' 표시」가 아니라 있는 단추를 가리킨다
    assert '시작)' in str(caught.value) and '[처리 건에서 보기]' in str(caught.value) and "'처리 중' 표시" not in str(caught.value), str(caught.value)
    # 시작 단추의 거절 응답(409)이 그 건을 칸으로 싣는다
    status, refused = world.api('POST', '/api/scenario/C/start', {'by': '담당자', 'user_id': 'user:me', 'roles': ['role:purchasing']}, source_loop=True)
    assert status == 409 and refused['detail'] == str(caught.value), refused
    assert refused['instance'] == caught.value.instance and refused['started_at'], refused
    assert started is None or refused['instance'] == started, (refused, started)


def test_시나리오_처리_건이_진행_중이면_초기화를_거절한다(world):
    """H-10: 초기화는 열린 발주를 닫고 재고를 되돌린다 — 진행 중 처리 건의 기록을 그 처리 건 모르게 바꾸지 않는다."""
    _press(world, 'C')
    with pytest.raises(sb.Refused, match='아직 진행 중이라 초기화하지 않았습니다') as caught:
        sb.reset_refusal(world.rt, 'C')
    assert '조치 후보를 승인하거나 반려해 끝낸 뒤 [업무 데이터 초기화]를 누르세요' in str(caught.value), '아직 멈춘 단계가 없는 처리 건'


def test_시나리오_처리_건이_없으면_초기화를_받는다(world):
    assert sb.reset_refusal(world.rt, 'B') is None


def test_교대_인수인계_처리_건은_설비_값이_있어도_시나리오_시각_기준점을_붙잡지_않는다(world):
    """P4-01: 전에는 변수 asset 이 설비 이름이면 모두 붙잡아, 인수 확인을 기다리는 교대 처리 건 하나가 [정기 점검] · [재고 보충]의 기준점 이동을 막았다."""
    pid = world.rt.start_definition('shift_handover', definition_version('shift_handover_v1.json'), 'handover:' + uuid.uuid4().hex, values=dict(START))['proc_inst_id']
    found = sb.reanchor_blockers(world.rt)
    assert pid not in [b['instance'] for b in found['blocked_by'] + found['overdue']]
    assert sb.may_reanchor(world.rt) is True


def test_경보로_연_대응_처리_건이_진행_중이면_기준점을_붙잡는다(world):
    pid = _press(world, 'C')
    found = sb.reanchor_blockers(world.rt)
    assert [b['instance'] for b in found['blocked_by']] == [pid] and found['blocked_by'][0]['why'] == '진행 중'
    assert sb.may_reanchor(world.rt) is False


def test_공급사_납기_지연은_열린_발주가_없으면_까닭과_함께_거절하고_상태가_그_까닭을_싣는다(world):
    """[공급사 납기 지연]은 진행 중인 예비품 구매 처리 건이 낸 열린 발주에만 걸린다. 발주 전(승인 대기)이면 누를 수 없고 화면이 읽는 상태가 까닭을 말한다.
    발주 뒤의 길(지연 통보 → 납기 초과 → 지연 결과 보고)은 test_instances 가 흐름 끝까지 잰다."""
    _press(world, 'C')
    with pytest.raises(sb.Refused, match='아직 발주 전입니다 — 처리 건에서 발주안을 승인하면 발주가 열립니다'):
        sb.delay_target(world.rt, world.instance_mode.enterprise_read, 'C')
    [event] = sb.status(world.instance_mode.enterprise_read, world.rt)['scenarios']['C']['events']
    assert (event['act'], event['button'], event['path'], event['enabled']) == ('delay', '공급사 납기 지연', '/api/scenario/C/delay', False)
    assert '아직 발주 전입니다' in event['why']
    assert sb.status(world.instance_mode.enterprise_read, world.rt)['scenarios']['B']['events'] == [], '정기 정비에는 바깥 사건 단추가 없다'


def test_시나리오_상태는_진행_중_처리_건과_마지막_처리_건을_보인다(world):
    pid = _press(world, 'C')
    status = sb.status(world.instance_mode.enterprise_read, world.rt)
    c = status['scenarios']['C']
    assert c['running']['instance'] == pid and c['last']['instance'] == pid and c['alert'] is True
    assert status['scenarios']['B']['running'] is None
    # 화면 단추의 이름은 서버가 준 이 값 하나다 — 처리 건의 시작 기록(「…의 [단추]를 눌러 열었습니다」)과 거절 문장이 같은 이름을 쓴다
    # (전에는 화면 단추가 [예비품 구매 시작]인데 기록은 [재고 보충]을 눌렀다고 했다)
    assert (c['button'], status['scenarios']['B']['button'], status['reset_button']) == ('예비품 구매 시작', '정기 정비 시작', '업무 데이터 초기화')
    row = {'part_no': 'P-PMP-SEAL', 'available': 1, 'reorder_point': 2, 'need_qty': 6, 'below_since': 'x', 'reserved_for': 'HYD-03'}
    assert sb.build_alert('C', row, datetime(2026, 10, 30, 6, 0, 1, tzinfo=timezone.utc), PERSON)['evidence']['trigger'] == f"결함 시뮬레이션의 [{c['button']}]"
    assert sb.press_event(pid, c['button'], 'HYD-03', PERSON, 'x')['data']['name'] == f"결함 시뮬레이션의 [{c['button']}]"


def test_시나리오_상태는_설비_결함_주입이_지원하는_설비와_결함과_단추를_말한다():
    """전수검사 10-G12: 설비 결함 주입은 가상 설비 한 대의 결함 한 종류인데 서버가 그 범위를 내지 않아 화면이 설비 · 결함을 손으로 적었다."""
    status = sb.status(lambda name, params: {'records': []})
    assert status['fault'] == {'asset': 'HYD-01', 'fault': 'cooler_degradation', 'severity': 'moderate', 'pattern': 'COOLER_DEGRADATION',
                               'buttons': {'degrade': '쿨러 열화 주입', 'restore': '쿨러 복구'}}
    said = sb.unknown_act('pump_leakage')
    assert 'HYD-01' in said and '[쿨러 열화 주입](degrade)' in said and '[쿨러 복구](restore)' in said and "'pump_leakage'" in said


# ---------------------------------------------------------------- D-1: 처리 건이 열린 채 일어난 바깥 조작
from conftest import COOLING, OPERATOR

WINDOW_S = 15 * 60 / 20          # 재관측 창 = 15 시뮬레이션 분 ÷ 배속 20
MAINT = dict(by=OPERATOR['by'], role='role:maint-mgr')


def _cooling_case(world, restored_before_open=False):
    """쿨러 오염(수업 강도)이 끝까지 진행된 설비(감지기 자리가 그 값으로 냉각 경보를 냈다) → 설비가 30분 동안 보고한 뒤(판단 근거의 관측 구간 — 상태의
    바깥 변화 기록 포함) 냉각 경보 → 처리 건. restored_before_open: 경보가 처리 건을 열기 전에 현장에서 쿨러를 되돌렸다(그 바깥 변화는 처리 건이 열릴 때의
    기록에 이미 든다 — 처리 건이 열린 뒤에는 아무도 설비를 건드리지 않는다). 돌려줌 = (경보, 처리 건 id)."""
    pattern, asset = COOLING
    world.plant.inject(asset, 'cooler_degradation', severity='moderate')
    world.settle(1800)
    assert (asset, pattern, 'RAISE') in {(e['asset'], e['pattern'], e['state']) for e in world.detected}, '감지기 자리가 쿨러 열화에 경보를 내지 않았다'
    if restored_before_open:
        world.plant.inject(asset, 'restore')
    world.reported_for(asset)
    tags = world.plant.tags(asset)
    return world.raise_alert(pattern, asset, ts1=tags['TS1'], ce=tags['CE'])


def _until_cleared(world, pid, most_s=150):
    """설비 · 감지기 자리 · 엔진이 함께 시간을 산다(world.pass_time) — 감지기가 설비 값으로 경보를 풀면 그 해제가 원천 접수로 들어간다. 시험은 해제를
    넣지 않는다. most_s 초 안에 안 풀리면 그때의 설비 값으로 실패한다."""
    for _ in range(int(most_s // 10)):
        world.pass_time(10)
        if world.incident(pid).cleared:
            return
    raise AssertionError(f'{most_s}초가 지나도 감지기가 냉각 경보를 풀지 않았다 — 유온 {world.plant.tags("HYD-01")["TS1"]} ℃')


def _effect(world, pid):
    """효과 확인이 판정할 때까지 시간을 흘린다(첫 창, 그 뒤 연장 창마다). 유온 · 경보 해제는 설비 모형과 감지 규칙이 낸다."""
    from procsvc.service_parts import REOBSERVE_MAX_EXTENSIONS
    world.pass_time(WINDOW_S + 1)
    for _ in range(REOBSERVE_MAX_EXTENSIONS):
        if world.inst(pid)['status'] != 'RUNNING':
            break
        world.pass_time(WINDOW_S / 3 + 1)


@pytest.mark.parametrize('press, state', [(True, 'ESCALATED'), (False, 'RESOLVED_WITHOUT_ACTION')],
                         ids=['설비 초기화 뒤 해제', '처리 건이 열린 뒤 바깥 조작 없이 회복'])
def test_승인_대기_중_설비_초기화로_풀린_경보는_자연_회복이_아니라_그_까닭으로_책임자_확인이다(world, press, state):
    """D-1: 처리 건이 승인을 기다리는 동안 [설비 초기화]를 누르면 유온이 바로 48 ℃가 되고 경보가 풀려 「조치 전 자연 회복」으로 끝났고,
    [설비 초기화]는 처리 건에 기록도 남지 않았다(포털이 가상 설비를 바로 불렀다). 지금은 처리 엔진을 거쳐 그 처리 건에 남고, 가상 설비가 실은
    바깥 변화 기록으로 그 뒤의 해제를 자연 회복으로 치지 않는다. 처리 건이 열린 뒤 바깥 조작이 없으면(쿨러는 처리 건이 열리기 전에 되돌려 식는 중)
    자연 회복 그대로다(1초마다 오는 상태는 바깥 변화가 아니다). 두 경우 모두 경보는 감지기가 설비 값으로 푼다."""
    alert, pid = _cooling_case(world, restored_before_open=not press)
    if press:
        status, body = world.api('POST', '/api/scenario/plant-reset', PERSON)
        assert status == 200 and pid in body['instances'], body
        assert world.plant.tags('HYD-01')['TS1'] < 55
    _until_cleared(world, pid)
    inc = world.incident(pid)
    assert inc.state == state, (inc.state, inc.reason)
    report = world.values(pid)['result_report']
    if press:
        assert inc.reason.startswith('OUTSIDE_CHANGE:') and '[설비 초기화]' in inc.reason and PERSON['by'] in inc.reason, inc.reason
        assert any(e['data'].get('button') == '설비 초기화' for e in world.events(pid, job='SCENARIO_BUTTON')), '누름이 처리 건에 남아야 한다'
        assert '승인한 조치 밖에서 바뀌었습니다([설비 초기화]' in report['summary'] and 'OUTSIDE' not in report['summary'], report['summary']
    else:
        assert '조치 전 자연 회복' in report['summary'], report['summary']


@pytest.mark.parametrize('card, press, outcome, state', [
    ('skill:sop-cool-11', 'A/restore', '미달', 'ESCALATED'),      # 팬 최대 명령 → 효과 확인 중 [쿨러 복구]
    ('skill:sop-cool-14', 'plant-reset', '미달', 'ESCALATED'),    # 정비 요청만 → 정비 수행 → 효과 확인 중 [설비 초기화]
    ('skill:sop-cool-14', None, '정상', 'CLOSED'),                # 같은 길, 바깥 조작 없음 — 승인 뒤 정비 복구는 바깥 변화가 아니다
], ids=['명령 뒤 쿨러 복구', '정비 뒤 설비 초기화', '정비 뒤 바깥 조작 없음'])
def test_효과_확인_중_바깥_조작으로_내려간_유온은_승인한_조치의_효과로_적지_않는다(world, card, press, outcome, state):
    """D-1: 지는 대안을 승인해도 효과 확인 동안 [쿨러 복구] · [설비 초기화]를 누르면 창 끝의 값과 경보 해제만 보고 「회복 — 정상」으로 끝나
    회복이 승인한 조치 덕으로 적혔다. 유온은 설비 모형이 낸 값이고(바깥 조작으로 실제로 식는다) 경보 해제는 감지기가 낸다 — 판정이 그 값을
    조치의 효과로 치지 않는다."""
    alert, pid = _cooling_case(world)
    decision = world.agent(pid, 'T_agent')
    world.approve(pid, decision, card, OPERATOR if card == 'skill:sop-cool-11' else MAINT)
    if card == 'skill:sop-cool-11':
        world.ack('HYD-01', world.commanded(pid)['cmdId'])
    world.poll(3)
    reobs = 'T_reobs' if card == 'skill:sop-cool-11' else 'T_reobs_wo'
    assert world.row(pid, reobs)['status'] == 'SUBMITTED', [(w['activity_id'], w['status']) for w in world.rows(pid)]
    if press:
        status, body = world.api('POST', f'/api/scenario/{press}', PERSON)
        assert status == 200, body
    _effect(world, pid)
    assert world.plant.tags('HYD-01')['TS1'] < 55, '설비는 실제로 식었다'
    assert world.inst(pid)['status'] == 'COMPLETED', [(w['activity_id'], w['status'], (w.get('log') or '')[-200:]) for w in world.rows(pid)]
    report, inc = world.values(pid)['result_report'], world.incident(pid)
    assert (report['outcome'], inc.state) == (outcome, state), (report, inc.reason)
    if press:
        button = '쿨러 복구' if press == 'A/restore' else '설비 초기화'
        assert inc.reason.startswith('OUTSIDE_CHANGE:') and f'[{button}]' in inc.reason, inc.reason
        assert f'승인한 조치 밖에서 바뀌었습니다([{button}]' in report['summary'], report['summary']


def test_설비_초기화는_누름을_처리_건에_기록하지_못해도_설비를_되돌리고_되돌린_것과_기록하지_못한_것을_따로_말한다(world):
    """검토 나-3: [설비 초기화]는 설비를 되돌린 뒤 진행 중인 처리 건마다 누름을 기록했는데, 그 업무 DB 쓰기가 실패하면 500 이 나 화면이 「설비 초기화
    실패」라고 말했다 — 설비는 이미 되돌려졌다. 거절하지 않는 마지막 길이라 설비는 먼저 되돌리고, 응답이 둘을 따로 말한다: 200 · 기록한 처리 건 없음 ·
    기록하지 못한 까닭(업무 DB 가 준 까닭 그대로). 누름 기록은 한 번에 쓰므로 일부만 남지 않고, 감사 기록에는 그 까닭과 함께 누름이 남는다.
    업무 DB 의 거절은 바깥(저장소 트리거)에서만 일으킨다 — 설비 · 처리 엔진 · 라우트는 실제 코드다."""
    alert, pid = _cooling_case(world)
    running = [i['proc_inst_id'] for a in topics.ASSETS for i in world.rt.repo.list_instances('RUNNING', None, world.rt.tenant_id, None, a)]
    assert pid in running
    unit = world.plant.units['HYD-01']
    seq, sick = unit.outside['seq'], unit.state.cooler_health
    assert sick < 1.0 and unit.state.ts1 > 55, '쿨러 열화가 진행된 설비다'
    with world.storage_fails('events', "NEW.job_id = 'SCENARIO_BUTTON'"):
        status, body = world.api('POST', '/api/scenario/plant-reset', PERSON)
    assert status == 200 and body['ok'] is True and body['instances'] == [], body
    assert body['record_error'].startswith(f'진행 중인 처리 건 {len(running)}건에 이 누름을 기록하지 못했습니다') \
        and '시험: 저장소가 이 쓰기를 거절함' in body['record_error'], body
    assert (unit.outside['kind'], unit.outside['seq'], unit.state.cooler_health, unit.faults) == ('reset', seq + 1, 1.0, {}) \
        and world.plant.tags('HYD-01')['TS1'] < 55, '설비는 되돌렸다'
    assert not [e for e in world.events(pid, job='SCENARIO_BUTTON') if e['data'].get('button') == sb.PLANT_RESET_BUTTON], '누름 기록은 남지 않았다'
    press = next(e for e in world.main.audit_log if e['event'] == 'SCENARIO_BUTTON' and e['detail'].get('button') == sb.PLANT_RESET_BUTTON)
    assert (press['detail']['instances'], press['detail']['error']) == ([], body['record_error']), press
    # 저장소가 돌아오면 같은 길이 기록까지 한다(까닭 없음)
    status, body = world.api('POST', '/api/scenario/plant-reset', PERSON)
    assert status == 200 and body['record_error'] is None and sorted(body['instances']) == sorted(running), body
    assert [e for e in world.events(pid, job='SCENARIO_BUTTON') if e['data'].get('button') == sb.PLANT_RESET_BUTTON]
