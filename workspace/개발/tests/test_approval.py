"""승인 현재 조건 검사(it/agent/agentsvc/approval.py) — 승인 직전에 규칙 · 원천을 다시 읽어, 사람이 본 카드와 같은지 · 지금도 되는지 본다.
원천을 못 읽으면 거절이 아니라 「검사를 못 함」(503 · 그 자리 까닭 — H-8). 실제 agent 서비스 · 처리 엔진 · 업무 시스템을 지난다."""
import json
import urllib.error
import urllib.request

import pytest

from agentsvc import approval

RULE = {'rule': 'r1', 'effect': 'EXCLUDE', 'tests': [{'variable': 'oil_temp_c', 'operator': '>', 'value': 60}, {'variable': 'plc_mode', 'operator': '==', 'value': 'AUTO'}]}


@pytest.mark.parametrize('facts, missing', [
    ({'oil_temp_c': 65, 'plc_mode': 'AUTO'}, []),
    ({'oil_temp_c': 65}, ['plc_mode']),
    ({'oil_temp_c': 50}, []),
    ({}, ['oil_temp_c', 'plc_mode']),
], ids=['모두 앎', '하나 모름', '하나가 거짓이면 규칙이 안 걸림', '모두 모름'])
def test_적용될_수_있는_규칙의_모르는_사실만_확인할_수_없는_것으로_센다(facts, missing):
    assert approval.unresolved(RULE, facts) == missing


SKILL = {'sopId': 'SOP-COOL-12', 'name': '팬 증속', 'actions': [{'kind': 'command', 'param': 'fan_pct', 'value': 80, 'min': 40, 'max': 100}]}


def test_조치값_변경안은_명시_범위_안의_팬_부하만이고_원문과_구분된_이름을_단다():
    effective, normalized = approval._parameterized(SKILL, {'fan_pct': 100})
    assert normalized == {'fan_pct': 100} and effective['actions'][0]['value'] == 100 and effective['name'] == 'SOP-COOL-12 변경안: 팬 100%'
    assert SKILL['actions'][0]['value'] == 80                       # 원문 스킬은 그대로


@pytest.mark.parametrize('parameters, needle', [
    ({'valve_pct': 10}, 'valve_pct: 이 SOP에 변경 가능한 조치와 명시 범위가 없습니다'),
    ({'load_pct': 50}, 'load_pct: 이 SOP에 변경 가능한 조치와 명시 범위가 없습니다'),
    ({'fan_pct': 101}, 'fan_pct'),
    ('fan=100', '{설정 이름: 값} 꼴'),
], ids=['이 SOP 에 없는 다른 설정', '이 SOP 에 없는 설정', '범위 밖', '형식 아님'])
def test_범위_밖이거나_SOP_에_없는_조치값_변경은_거절한다(parameters, needle):
    with pytest.raises(ValueError) as e:
        approval._parameterized(SKILL, parameters)
    assert needle in str(e.value)


def test_팬_부하가_아닌_설정도_SOP_가_범위와_함께_밝혔으면_바꿀_수_있다():
    """설정 이름을 코드가 정하지 않는다 — 절차(SOP)의 명령 조치가 범위를 밝힌 값이면 받는다(수업 냉각 SOP 밖의 절차)."""
    skill = {'name': '밸브 개도 조정', 'sopId': 'SOP-VLV-01',
             'actions': [{'kind': 'command', 'param': 'valve_pct', 'value': 40, 'min': 20, 'max': 60}]}
    effective, normalized = approval._parameterized(skill, {'valve_pct': 55})
    assert normalized == {'valve_pct': 55} and effective['actions'][0]['value'] == 55 and 'valve_pct 55%' in effective['name']
    with pytest.raises(ValueError) as e:
        approval._parameterized(skill, {'valve_pct': 61})
    assert 'valve_pct' in str(e.value)


def test_판단_근거가_빠진_판단으로는_현재_조건을_다시_계산하지_않는다():
    with pytest.raises(ValueError) as e:
        approval.current_options(None, None, {'asset': 'HYD-01', 'origin': {'pattern': 'COOLER_DEGRADATION'}}, 'SOP-COOL-12')
    assert '다시 판단해야 합니다' in str(e.value)


def test_원래_카드에_없는_선택은_검사하지_않는다():
    with pytest.raises(ValueError) as e:
        approval.assess(None, None, {'id': 'DEC-1', 'options': []}, 'SOP-COOL-12', 'role:operator')
    assert '원래 카드가 없습니다' in str(e.value)


# ---------------------------------------------------------------- 실제 처리 건의 판단으로
def post(url, body, timeout=90):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'null')


@pytest.fixture
def decided(world):
    """흐름 A 의 에이전트 단계가 등록한 판단(키 없는 PC — 강사 녹화 재생, 판단은 이 PC 의 dmn-mcp 가 실제로 등록)."""
    _, pid, did = world.start_cooling()
    decision = world.main.book[did]
    option = next(o for o in decision['options'] if o['id'] == decision['recommended'])
    world.report()
    return world, decision, option


def test_사람이_본_권고_카드를_그_승인_역할로_고르면_지금도_승인된다(decided):
    world, decision, option = decided
    status, report = post(world.stack.services['agent'].url + '/api/agent/approval-check',
                          {'decision': decision, 'option': option['id'], 'role': option['approver']['id']})
    assert status == 200 and report['allowed'] is True and report['reasons'] == [], report.get('reasons')
    assert report['needs_new_preview'] is False


def test_승인_역할이_모자라면_까닭과_함께_거절한다(decided):
    world, decision, option = decided
    status, report = post(world.stack.services['agent'].url + '/api/agent/approval-check',
                          {'decision': decision, 'option': option['id'], 'role': 'role:nobody'})
    assert status == 200 and report['allowed'] is False and '현재 역할 정보에서 승인 권한이 없습니다' in report['reasons']


@pytest.fixture
def pm_decided(world):
    """정기 점검(시나리오 B)의 에이전트 단계가 등록한 판단 — 승인 검사가 업무 시스템(CMMS 계획 · 정비 창)을 다시 읽는다."""
    status, out = world.api('POST', '/api/scenario/B/start', {'by': 'user:kim-op', 'role': 'role:operator'}, source_loop=True)
    assert status == 200, out
    did = world.agent(out['instance'], 'T_agent')
    decision = world.main.book[did]
    world.report()
    return world, decision, next(o for o in decision['options'] if o['id'] == decision['recommended'])


def test_업무_시스템이_답하지_않으면_승인을_거절하지_않고_검사를_못_했다고_503_으로_말한다(pm_decided):
    """H-8: 원천을 못 읽은 것은 「승인 불가」가 아니라 「지금 검사 불가 — 다시 시도」다. (냉각 카드의 승인 검사는 설비 값만 다시 읽어
    업무 시스템에 닿지 않는다 — 업무 사실을 다시 읽는 정기 점검 카드로 잰다.)"""
    world, decision, option = pm_decided
    with world.stack.services['enterprise-sim'].paused():
        status, body = post(world.stack.services['agent'].url + '/api/agent/approval-check',
                            {'decision': decision, 'option': option['id'], 'role': option['approver']['id']})
    assert status == 503 and '읽지 못해 판단을 멈췄습니다' in body['detail'] and '다시 시도' in body['detail'], (status, body)


def test_사람이_본_예측이_검토_기한보다_오래됐으면_거절하고_새_미리_보기가_필요하다고_칸으로_알린다(decided):
    """G4-16: 화면 · 점검은 문장 글자가 아니라 needs_new_preview 칸으로 「새 카드 검토」를 가린다 — 그 칸이 참이 되는 길을 잰다.
    사람이 카드를 본 시각(그 카드 예측의 원천 시각)을 검토 기한(벽시계 30분)보다 앞으로 둔다(벽시계를 기다리지 않고)."""
    import copy
    from datetime import datetime, timedelta, timezone
    world, decision, option = decided
    seen = copy.deepcopy(decision)
    card = next(o for o in seen['options'] if any(a.get('kind') == 'command' for a in o.get('actions') or []))
    old = (datetime.now(timezone.utc) - timedelta(minutes=40)).isoformat()
    card['forecastContext'] = dict(card['forecastContext'], source_t=old)
    status, report = post(world.stack.services['agent'].url + '/api/agent/approval-check',
                          {'decision': seen, 'option': card['id'], 'role': card['approver']['id'],
                           'consented_at': datetime.now(timezone.utc).isoformat()})          # 40분 전 예측을 지금 동의했다
    assert status == 200 and report['allowed'] is False and report['needs_new_preview'] is True, report.get('reasons')
    assert any('새 카드 검토가 필요합니다' in r for r in report['reasons'])


def test_승인_검사도_지금_세우는_카드를_정지한_설비로_다시_예측한다(decided):
    """G1-05(승인 배선): 승인 때 다시 계산하는 예측이 정지 카드를 「운전 계속」으로 내면 사람이 본 예측과 달라 승인이 막히거나 거짓 값이 된다."""
    world, decision, _ = decided
    card = next((o for o in decision['options'] if o.get('sopId') == 'SOP-COOL-14'), None)
    assert card is not None, [o.get('sopId') for o in decision['options']]
    status, report = post(world.stack.services['agent'].url + '/api/agent/approval-check',
                          {'decision': decision, 'option': card['id'], 'role': card['approver']['id']})
    assert status == 200, report
    ts1 = next(x['value'] for x in report['current_option']['forecast'] if x['variable'] == 'sv:ts1')
    assert ts1 < 55, f'승인 검사의 예측이 정지한 설비의 것이 아니다: {ts1}'

