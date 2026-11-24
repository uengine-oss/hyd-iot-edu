"""사건 기계(procsvc/machine.py) — 명령 · ACK · 재관측 판정을 사건에 적는다(시한 · 판정 규칙은 작업 행 · 재관측 단계가 갖는다)."""
from datetime import datetime, timezone

import pytest

from procsvc import definition, machine

NOW = datetime(2026, 10, 30, 9, 0, tzinfo=timezone.utc)
ALERT = {'alertId': 'ALT-1', 'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION'}
POLICY = {'pattern': 'COOLER_DEGRADATION', 'route': 'response', 'criterion': ('TS1', '<', 55.0), 'definition': 'c3_cooling', 'version': '1'}   # alert_policy.for_definition 의 모양
CARD = {'alert': ALERT, 'causes': [], 'skills': []}
# 승인한 판단 카드(조치 방법 한 장) — 실제 판단(dmn-mcp → process /api/decisions)의 option 칸 그대로(라이브 DEC-1031-mcp-003 의 SOP-COOL-11)
OPTION = {'id': 'skill:sop-cool-11', 'sopId': 'SOP-COOL-11', 'name': '팬 최대 운전', 'kind': 'control',
          'actions': [{'id': 'action:set-fan', 'code': 'FAN_SET', 'name': '팬 속도 설정', 'kind': 'command', 'param': 'fan_pct',
                       'min': 0, 'max': 100, 'value': 100, 'seq': 1, 'target': 'actr:fan-drive'},
                      {'id': 'action:work-order', 'code': 'WO_CREATE', 'name': '정비 작업지시 발행', 'kind': 'transaction', 'value': 'SOP-COOL-14'}]}


class Recorder(machine.Effects):
    """사건 기계의 바깥(감사 기록) 자리 — 받은 감사를 남긴다."""
    def __init__(self):
        self.events = []

    def emit_audit(self, evt):
        self.events.append(evt)


def _incident():
    inc = machine.Incident.from_card('INC-1', CARD, recovery_policy=POLICY)
    machine.on_card(inc)
    return inc


def _approved():
    """사람이 승인했고 설비 명령 없이 흐름이 실행 중인 사건."""
    inc = _incident()
    machine.on_flow_approved(inc, 'user:me', Recorder())
    return inc


def _awaiting_ack():
    inc, fx = _incident(), Recorder()
    cmd = machine.on_approve(inc, 'user:me', OPTION, [{'code': 'FAN_SET', 'fan_pct': 100}], NOW, fx)
    machine.on_command_sent(inc, cmd['cmdId'], NOW, fx)
    return inc, cmd, fx


def _re_observing():
    inc, cmd, fx = _awaiting_ack()
    machine.on_status(inc, {'cmdId': cmd['cmdId'], 'result': 'DONE'}, NOW, fx)
    return inc, cmd, fx


def test_경보_정책_없이는_사건을_만들지_않는다():
    """P1-20: 정책이 없으면 코드 상수(definition.RECOVERY)로 회복 기준을 대신하던 호환 갈래를 지웠다 — 기준의 주인은 흐름의 alertPolicy 하나."""
    with pytest.raises(ValueError, match='경보 정책'):
        machine.Incident.from_card('INC-1', CARD, recovery_policy=None)
    assert _incident().recovery == ('TS1', '<', 55.0)
    other = machine.Incident.from_card('INC-2', CARD, recovery_policy=dict(POLICY, pattern='PUMP_LEAKAGE'))
    assert other.recovery is None, '정책의 패턴이 사건의 패턴과 다르면 판정할 기준이 없다'


def test_명령을_보낸_뒤_ACK_마감은_벽시계_30초로_사건에_적힌다():
    inc, fx = _incident(), Recorder()
    cmd = machine.on_approve(inc, 'user:me', OPTION, [{'code': 'FAN_SET', 'fan_pct': 100}], NOW, fx)
    assert inc.state == 'CMD_ISSUED' and inc.ack_due_at is None, '보내기 전에는 ACK 를 기다리지 않는다'
    machine.on_command_sent(inc, cmd['cmdId'], NOW, fx)
    assert inc.state == 'AWAITING_ACK' and inc.ack_due_at.startswith('2026-10-30T09:00:30')


def test_지금_가이드_카드로_연_사건도_승인한_판단_카드의_명령으로_승인된다():
    """한바퀴3 고침 1: 가이드 카드에서 섞인 「권장 조치」(recommended)를 지운 뒤(G1-04)에도 사건 기계는 가이드 카드의 recommended 로 명령을
    검사해 「action FAN_SET is not on the guide card」로 모든 승인을 막았다(실제 스택 흐름 A 승인 뒤 멈춤). 테스트는 옛 카드 모양을 손으로
    만들어(그리고 world 테스트는 G1-04 전 녹화의 가이드 카드로) 통과했다 — 그래서 사건은 지금 생산자(agentsvc.card.build_card)가 만든 카드로 연다."""
    from agentsvc import card
    causes = card.rank_causes([{'causeId': 'cause:cooler-fin-fouling', 'cause': '쿨러 핀 오염', 'prior': 0.6,
                                'failureModeId': 'fm:cooler-cooling-loss', 'failureMode': '쿨러 냉각 성능 상실',
                                'evidence': [{'id': 'evd:ce-low', 'name': '냉각 효율 저하', 'weight': 1, 'expect': 'lt', 'threshold': 70}]}],
                              {'evd:ce-low': {'value': 46.2, 'passed': True}})
    guide = card.build_card(None, ALERT, causes, {'cause:cooler-fin-fouling': [dict(OPTION, skillId=OPTION['id'])]}, {'ok': True})
    inc = machine.Incident.from_card('INC-1', guide, recovery_policy=POLICY)
    machine.on_card(inc)
    cmd = machine.on_approve(inc, 'user:me', OPTION, [{'code': 'FAN_SET', 'fan_pct': 100}], NOW, Recorder())
    assert inc.state == 'CMD_ISSUED' and cmd['actions'] == [{'code': 'FAN_SET', 'fan_pct': 100}]


@pytest.mark.parametrize('actions, words', [
    ([{'code': 'LOAD_SET', 'load_pct': 80}], ['「SOP-COOL-11 팬 최대 운전」에 없는 설비 명령(LOAD_SET)']),
    ([{'code': 'WO_CREATE'}], ['없는 설비 명령(WO_CREATE)']),
    ([{'code': 'FAN_SET'}], ['「팬 속도 설정」에 값이 없습니다']),
    ([{'code': 'FAN_SET', 'fan_pct': 101}], ['값 101', '허용 범위 0~100 밖']),
    ([{'code': 'FAN_SET', 'fan_pct': -1}], ['값 -1', '허용 범위 0~100 밖']),
    ([], ['보낼 설비 명령이 없습니다']),
], ids=['카드에 없는 명령', '명령이 아닌 조치', '값 없음', '범위 위', '범위 아래', '명령 없음'])
def test_승인한_판단_카드_밖의_명령이나_범위_밖_값은_학생_문장으로_거절하고_사건은_승인_대기에_남는다(actions, words):
    inc = _incident()
    with pytest.raises(ValueError) as caught:
        machine.on_approve(inc, 'user:me', OPTION, actions, NOW, Recorder())
    assert all(w in str(caught.value) for w in words) and 'guide card' not in str(caught.value), str(caught.value)
    assert inc.state == 'AWAITING_APPROVAL' and inc.cmd_id is None


@pytest.mark.parametrize('value', [0, 100], ids=['범위 아래 끝', '범위 위 끝'])
def test_범위_끝값의_명령은_승인된다(value):
    inc = _incident()
    cmd = machine.on_approve(inc, 'user:me', OPTION, [{'code': 'FAN_SET', 'fan_pct': value}], NOW, Recorder())
    assert cmd['actions'] == [{'code': 'FAN_SET', 'fan_pct': value}]


def test_재관측_시작과_판정은_사건_이력에_칸으로_남는다():
    """포털이 문장(note)에서 정규식으로 뽑지 않게 — 칸: tag · op · limit · sim_s, 판정이면 value · cleared · recovered · extensions."""
    inc, cmd, fx = _re_observing()
    start = inc.history[-1]
    assert start['state'] == 'RE_OBSERVING' and start['reobservation'] == {'tag': 'TS1', 'op': '<', 'limit': 55.0,
                                                                           'sim_s': definition.REOBSERVE_SIM_S}
    reading = {'tag': 'TS1', 'op': '<', 'limit': 55.0, 'value': None, 'cleared': False, 'criterion': 'TS1 < 55.0'}
    assert machine.on_reobservation(inc, cmd['cmdId'], False, reading, 0, fx)
    verdict = inc.history[-1]
    assert verdict['state'] == 'ESCALATED' and verdict['reobservation'] == {
        'tag': 'TS1', 'op': '<', 'limit': 55.0, 'value': None, 'cleared': False, 'recovered': False, 'extensions': 0,
        'sim_s': definition.REOBSERVE_SIM_S}
    assert verdict['note'] == '회복 미달 — TS1 값 없음 (기준 TS1 < 55.0, 경보 그대로)', 'W2-15: 이력 문장은 학생 말이다'


@pytest.mark.parametrize('passed, state, reason', [(True, 'RESOLVED', None), (False, 'ESCALATED', 'MITIGATION_FAILED')])
def test_재관측_판정이_사건을_회복_또는_완화_실패로_보낸다(passed, state, reason):
    inc, cmd, fx = _re_observing()
    reading = {'tag': 'TS1', 'op': '<', 'limit': 55.0, 'value': 50.0 if passed else 60.0, 'cleared': passed, 'criterion': 'TS1 < 55.0'}
    assert machine.on_reobservation(inc, cmd['cmdId'], passed, reading, 1, fx)
    assert (inc.state, inc.reason, inc.reobs_extensions) == (state, reason, 1)


def test_다른_명령의_재관측_판정과_ACK_마감은_사건을_바꾸지_않는다():
    inc, cmd, fx = _re_observing()
    assert not machine.on_reobservation(inc, 'CMD-other', True, {'criterion': 'TS1 < 55.0'}, 0, fx)
    assert not machine.on_ack_timeout(inc, cmd['cmdId'], fx), 'ACK 가 이미 왔다'
    assert inc.state == 'RE_OBSERVING'


# ---------------------------------------------------------------- G3b-9 명령 관문의 거절은 그 자리에서 사건을 닫는다
def test_명령_관문이_거절하면_30초를_기다리지_않고_관문의_까닭으로_닫는다():
    """G3b-9: 전에는 관문의 거절이 process 에 오지 않아 30초 뒤 「실행됐는지 알 수 없음」으로 끝났다 — 관문 거절은 실행되지 않은 것이 확실하다."""
    inc, cmd, fx = _awaiting_ack()
    text = '설비가 원격 자동 모드가 아니어서 보내지 않았습니다 — 운전 모드를 원격 자동으로 돌린 뒤 다시 승인합니다'
    assert machine.on_gateway_rejected(inc, cmd['cmdId'], 'MODE', text, fx)
    assert (inc.state, inc.reason) == ('ESCALATED', f'GATEWAY_REJECTED: {text}')
    cause, reobserved = definition.escalation_cause(inc.reason)
    assert '명령 관문' in cause and text in cause and reobserved is False


@pytest.mark.parametrize('cmd_id, text, outcome', [
    ('CMD-other', '까닭', False),          # 다른 명령(재작업으로 바뀐 것)의 거절 — 그대로
    (None, '', ValueError),                # 까닭 없는 거절 — 좌표를 붙여 실패
])
def test_명령_관문의_다른_명령_거절은_무시하고_까닭_없는_거절은_받지_않는다(cmd_id, text, outcome):
    inc, cmd, fx = _awaiting_ack()
    if outcome is ValueError:
        with pytest.raises(ValueError, match='까닭 문장이 없습니다'):
            machine.on_gateway_rejected(inc, cmd['cmdId'], 'MODE', text, fx)
    else:
        assert machine.on_gateway_rejected(inc, cmd_id, 'MODE', text, fx) is False
    assert inc.state == 'AWAITING_ACK'


def test_PLC_거절은_PLC_사유로_닫는다():
    """사람이 읽는 사유는 PLC 가 상태에 함께 싣는 문장(reason_text)이다 — 전에는 사유 코드(MODE_MISMATCH)가 결과 보고 문장에 그대로 실렸다."""
    inc, cmd, fx = _awaiting_ack()
    machine.on_status(inc, {'cmdId': cmd['cmdId'], 'result': 'REJECTED', 'reason': 'MODE_MISMATCH', 'reason_text': '운전 모드 확인 필요'}, NOW, fx)
    assert (inc.state, inc.reason, inc.ack['reason']) == ('ESCALATED', 'PLC REJECTED: 운전 모드 확인 필요', 'MODE_MISMATCH')
    text = definition.escalation_cause(inc.reason)[0]
    assert 'PLC 에서 거절됐습니다(사유 운전 모드 확인 필요)' in text and 'MODE_MISMATCH' not in text, text


@pytest.mark.parametrize('status', [{'reason': 'MODE_MISMATCH', 'reason_text': '–'}, {'reason': 'MODE_MISMATCH'}, {'reason': 'MODE_MISMATCH', 'reason_text': '  '}],
                         ids=['자리표 문장', '문장 칸 없음', '빈 문장'])
def test_사유_문장이_없는_PLC_거절도_거절로_닫고_문장이_없다는_사실과_사유_코드를_적는다(status):
    """문장 없는 거절을 실패로 던지면 사건이 응답 대기로 남아 뒤에 「설비 응답이 오지 않음」(ACK 시간 초과)이라는 틀린 까닭으로 닫힌다 — 설비는 응답했다."""
    inc, cmd, fx = _awaiting_ack()
    machine.on_status(inc, {'cmdId': cmd['cmdId'], 'result': 'REJECTED', **status}, NOW, fx)
    assert (inc.state, inc.ack['result'], inc.ack['reason']) == ('ESCALATED', 'REJECTED', 'MODE_MISMATCH')
    assert inc.reason == 'PLC REJECTED: 설비가 거절 사유 문장을 보내지 않음 — 사유 코드 MODE_MISMATCH'
    assert not machine.on_ack_timeout(inc, cmd['cmdId'], fx) and inc.reason.startswith('PLC REJECTED'), '응답 없음으로 다시 닫지 않는다'
    assert '거절됐습니다(사유 설비가 거절 사유 문장을 보내지 않음 — 사유 코드 MODE_MISMATCH)' in definition.escalation_cause(inc.reason)[0]


# ---------------------------------------------------------------- P1-31 결과 보고 · P1-01 처리 건이 끝나면 사건도 닫는다
@pytest.mark.parametrize('level, state, reason', [('ok', 'CLOSED', None), ('fail', 'ESCALATED', definition.RESULT_REPORT)])
def test_결과_보고가_사건을_닫으면_미달에도_사유를_남긴다(level, state, reason):
    """P1-31: 전에는 미달 · 지연으로 닫은 사건만 사유 칸이 비었다."""
    inc, fx = _incident(), Recorder()
    assert machine.on_result_report(inc, level, '재관측 기준 미달', fx)
    assert (inc.state, inc.reason) == (state, reason)
    if state == 'ESCALATED':
        assert definition.escalation_cause(inc.reason) is None, '문장은 결과 보고 틀이 쓴다'


@pytest.mark.parametrize('prepare, changed', [
    (lambda: (_incident(), None), True),                                              # 승인 대기 — 닫는다
    (lambda: _awaiting_ack()[:1] + (None,), False),                                   # 명령 응답 기다림 — 사건이 스스로 판정
    (lambda: (_closed(), None), False),                                               # 이미 끝난 사건 — 그대로
])
def test_사건을_맡은_처리_건이_끝나면_열린_사건을_책임자_확인으로_닫는다(prepare, changed):
    inc, _ = prepare()
    before = inc.state
    assert machine.on_process_ended(inc, '에스컬레이션 종료', Recorder()) is changed
    if changed:
        assert (inc.state, inc.reason) == ('ESCALATED', 'PROCESS_ENDED: 에스컬레이션 종료')
        assert '에스컬레이션 종료' in definition.escalation_cause(inc.reason)[0]
    else:
        assert inc.state == before


def _closed():
    inc = _incident()
    machine.on_result_report(inc, 'ok', '정상', Recorder())
    return inc


# ---------------------------------------------------------------- 재작업 다시 열기 (P4-10 · W2-15)
def test_재작업은_끝나지_않은_사건만_다시_열고_같은_요청은_한_번만_연다():
    inc, cmd, fx = _re_observing()
    machine.on_reobservation(inc, cmd['cmdId'], True, {'tag': 'TS1', 'value': 50.0, 'cleared': True, 'criterion': 'TS1 < 55.0'}, 0, fx)
    assert inc.state == 'RESOLVED'
    assert machine.on_rework_reopen(inc, 'REQ-1', 'user:me', 'role:operator', '다시 판단', {}, fx)
    assert inc.state == 'AWAITING_APPROVAL' and inc.superseded[-1]['request_id'] == 'REQ-1'
    assert inc.history[-1]['note'].startswith('다시 수행으로 사건을 다시 엶')
    assert not machine.on_rework_reopen(inc, 'REQ-1', 'user:me', 'role:operator', '다시 판단', {}, fx), '같은 요청 id 는 한 번만'
    escalated = _incident()
    machine.on_result_report(escalated, 'fail', '미달', fx)
    with pytest.raises(ValueError, match='ESCALATED'):
        machine.on_rework_reopen(escalated, 'REQ-2', 'user:me', 'role:operator', '다시', {}, fx)


def _trip(asset, cleared=False, created=None):
    trip = machine.Incident.from_card('INC-T', {'alert': {'alertId': 'ALT-T', 'asset': asset, 'pattern': 'OVERHEAT_TRIP', 'name': '과열 인터록 트립',
                                                          'evidence': {'trip': 'OVERTEMP'}}, 'causes': [], 'skills': []},
                                      recovery_policy=dict(POLICY, pattern='OVERHEAT_TRIP'))
    trip.cleared = cleared
    if created:
        trip.created = created
    return trip


@pytest.mark.parametrize('others, state', [
    ([], 'RESOLVED_WITHOUT_ACTION'),
    ([_trip('HYD-01')], 'ESCALATED'),
    ([_trip('HYD-02')], 'RESOLVED_WITHOUT_ACTION'),
    ([_trip('HYD-01', cleared=True, created='2000-01-01T00:00:00.000Z')], 'RESOLVED_WITHOUT_ACTION'),
    ([_trip('HYD-01', cleared=True, created='2999-01-01T00:00:00.000Z')], 'ESCALATED'),
], ids=['보호 정지 없음', '같은 설비가 보호 정지 중', '다른 설비의 보호 정지', '이 사건 전에 끝난 보호 정지',
        '이 사건 동안 보호 정지가 있었고 먼저 풀림'])
def test_승인_전_해제는_같은_설비가_보호_정지_중이면_자연_회복이_아니라_책임자_확인이다(others, state):
    """재시작 확인(2026-11-01): HYD-02가 유온 높음으로 보호 정지해 펌프가 멈추고 식어 경보가 풀렸는데 냉각 사건이 「자연 회복」으로 닫혔다."""
    inc, fx = _incident(), Recorder()
    assert inc.state == 'AWAITING_APPROVAL'
    machine.on_alert(inc, dict(ALERT, state='CLEAR'), fx, trip=machine.active_trip(inc.asset, [inc, *others], since=inc.created))
    assert inc.state == state and inc.cleared
    if state == 'ESCALATED':
        text = definition.escalation_cause(inc.reason)[0]
        assert '보호 정지(사유 과열 인터록 트립)' in text and 'OVERTEMP' not in text, text      # 감지기가 실은 경보 이름 — PLC 사유 코드가 아니다


OUTSIDE = {'boot': 'b1', 'seq': 3, 'kind': 'fault', 'what': '[쿨러 열화 주입] — 쿨러 열화 주입', 'by': '담당자', 'at': '2026-11-22T01:00:00.000Z'}
RESET = dict(OUTSIDE, seq=4, kind='reset', what='[설비 초기화] — 설비 3기를 정상 운전점으로 되돌림(결함 · 보호 정지 · 팬 · 부하 지령)')


@pytest.mark.parametrize('before, now, changed', [
    (OUTSIDE, dict(OUTSIDE), False),                    # 1초마다 오는 상태 — 바깥 변화 없음
    (OUTSIDE, RESET, True),
    (OUTSIDE, dict(OUTSIDE, boot='b2', seq=3), True),   # 가상 설비가 다시 켜짐(번호는 0부터 다시) — 기동 번호로 가른다
    (None, RESET, False),                               # 사건이 열릴 때 기록이 없었다 — 견줄 것이 없다
    (OUTSIDE, None, False),                             # 그 기록을 싣지 않는 원천
], ids=['같음', '초기화', '다시 켜짐', '열 때 기록 없음', '기록 없는 원천'])
def test_바깥_변화는_사건이_열릴_때의_기록과_지금_기록이_다를_때만이다(before, now, changed):
    assert (machine.outside_change(before, now) is not None) is changed


def test_승인_전_해제라도_그_사이_설비가_바깥에서_바뀌었으면_자연_회복이_아니라_책임자_확인이다():
    """D-1: 승인 대기 중 [설비 초기화]로 유온이 바로 48 ℃가 되어 경보가 풀리면 「조치 전 자연 회복」(초록)으로 닫혔다."""
    inc, fx = _incident(), Recorder()
    machine.on_alert(inc, dict(ALERT, state='CLEAR'), fx, outside=machine.outside_change(OUTSIDE, RESET))
    assert inc.state == 'ESCALATED' and inc.reason.startswith(definition.OUTSIDE_CHANGE + ':'), inc.reason
    text, reobserved = definition.escalation_cause(inc.reason)
    assert '[설비 초기화]' in text and '자연 회복인지도' in text and 'OUTSIDE' not in text and reobserved is False, text
    natural, fx = _incident(), Recorder()
    machine.on_alert(natural, dict(ALERT, state='CLEAR'), fx, outside=machine.outside_change(OUTSIDE, dict(OUTSIDE)))
    assert natural.state == 'RESOLVED_WITHOUT_ACTION', '바깥 변화가 없으면 진짜 자연 회복이다'


def test_효과_확인_창에서_바깥_변화를_봤으면_회복_값이어도_조치의_효과로_적지_않는다():
    inc, cmd, fx = _re_observing()
    reading = {'tag': 'TS1', 'op': '<', 'limit': 55.0, 'value': 48.0, 'inside': True, 'cleared': True, 'criterion': 'TS1 < 55.0', 'outside': RESET}
    assert machine.on_reobservation(inc, cmd['cmdId'], False, reading, 0, fx)
    assert inc.state == 'ESCALATED' and inc.reason.startswith(definition.OUTSIDE_CHANGE), inc.reason
    assert inc.history[-1]['reobservation']['recovered'] is False


def test_정비형_사건의_효과_확인에서_바깥_변화를_봤으면_종결을_책임자_확인으로_바꾼다():
    inc, fx = _approved(), Recorder()
    machine.on_work_order(inc, {'ok': True, 'ref': 'WO-1'}, fx, work_order_only=True)
    assert inc.state == 'CLOSED'
    assert machine.on_outside_after_work_order(inc, RESET, fx) and inc.state == 'ESCALATED'
    assert inc.reason.startswith(definition.OUTSIDE_CHANGE)
    assert machine.on_result_report(inc, 'fail', '효과 확인(15분) 기준 미달', fx) is False, '결과 보고가 그 까닭을 덮어쓰지 않는다'
    other, fx = _re_observing()[0], Recorder()
    assert machine.on_outside_after_work_order(other, RESET, fx) is False, '명령을 낸 사건은 효과 확인 판정이 적는다'


SITE_ALERT = {'alertId': 'APU-01-APU_AIR_LEAK-2020-07-15T14:00:00', 'asset': 'APU-01', 'pattern': 'APU_AIR_LEAK'}
SITE_POLICY = {'pattern': 'APU_AIR_LEAK', 'route': 'response', 'criterion': None, 'definition': 'my_apu', 'version': '1'}


@pytest.mark.parametrize('route, approved, state', [
    ('response', False, 'RESOLVED_WITHOUT_ACTION'),   # 승인 전에 원천이 해제를 보냈다 — 회복은 원천의 해제다
    ('response', True, 'APPROVED_EXECUTING'),         # 사람이 승인한 뒤다 — 해제만 적고 끝은 흐름의 결과 보고가 정한다
    ('triage', False, 'ESCALATED'),                   # 이 경보를 받는 흐름이 없다 — 처음부터 현장 검토
], ids=['승인 전 해제', '승인 뒤 해제', '받는 흐름 없음'])
def test_시계열_회복_기준이_없는_내_시스템_경보도_받고_회복은_원천의_해제다(route, approved, state):
    """S-A: 회복 기준(시계열 태그 · 비교 · 임계)이 없으면 사건을 「지원하지 않는 경보」로 닫았다 — 학생 시스템 경보는 받는 흐름이 있어도 현장 검토."""
    inc = machine.Incident.from_card('INC-9', {'alert': SITE_ALERT, 'causes': []}, recovery_policy=dict(SITE_POLICY, route=route))
    machine.on_card(inc)
    assert inc.recovery is None and inc.supported is (route == 'response')
    fx = Recorder()
    if approved:
        assert machine.on_flow_approved(inc, 'user:me', fx)
    machine.on_alert(inc, dict(SITE_ALERT, state='CLEAR'), fx)
    assert inc.state == state and inc.cleared, (inc.state, inc.reason)
    if approved:
        assert fx.events[-1]['detail'].get('after_approval') is True
        assert machine.on_result_report(inc, 'ok', '정비 기록을 남겼습니다', fx) and inc.state == 'CLOSED'


def test_설비_명령_없는_승인은_사건을_승인_뒤_실행_중으로_옮기고_승인_전에만_여는_문을_닫는다():
    """승인 뒤 MCP 호출 · 정비 요청만 · 발주처럼 설비 명령 없이 실행하는 승인. 전에는 닫힐 때까지 승인 대기로 남아, 승인 뒤에도 사건이 승인 전이라고
    말했고 그 사이의 해제를 가리려고 처리 건의 작업 기록을 따로 읽었다."""
    inc, fx = _incident(), Recorder()
    assert machine.on_flow_approved(inc, 'user:me', fx)
    assert (inc.state, inc.approved_by, inc.cmd_id) == ('APPROVED_EXECUTING', 'user:me', None)
    assert fx.events[-1]['event'] == 'GUIDE_APPROVED' and fx.events[-1]['detail'] == {'approvedBy': 'user:me', 'actions': []}
    assert definition.state_label(inc.state) == '승인 — 흐름이 실행 중' and inc.state not in definition.TERMINAL
    assert machine.on_flow_approved(inc, 'user:someone-else', fx) is False and inc.approved_by == 'user:me', '같은 승인을 다시 적지 않는다'
    with pytest.raises(ValueError, match='cannot approve'):
        machine.on_approve(inc, 'user:me', OPTION, [{'code': 'FAN_SET', 'fan_pct': 100}], NOW, fx)
    with pytest.raises(ValueError, match='cannot reject'):
        machine.on_reject(inc, 'user:me', '늦은 반려', fx)
    with pytest.raises(ValueError, match='승인 대기 중인 사건만'):
        machine.on_result_report(inc, 'rejected', '늦은 반려', fx)
    assert inc.state == 'APPROVED_EXECUTING'
    with pytest.raises(ValueError, match='승인한 사람 기록이 없는'):
        machine.on_flow_approved(_incident(), '', fx)


@pytest.mark.parametrize('close, state', [
    (lambda inc, fx: machine.on_work_order(inc, {'ok': True, 'ref': 'WO-7'}, fx, work_order_only=True), 'CLOSED'),
    (lambda inc, fx: machine.on_business_effect(inc, {'ok': True, 'ref': 'GR-7', 'kind': 'goods_receipt'}, fx), 'CLOSED'),
    (lambda inc, fx: machine.on_result_report(inc, 'ok', '정상', fx), 'CLOSED'),
    (lambda inc, fx: machine.on_result_report(inc, 'fail', '미달', fx), 'ESCALATED'),
    (lambda inc, fx: machine.on_process_ended(inc, '사람이 닫음', fx), 'ESCALATED'),
], ids=['정비 요청 영수증', '입고 확인', '결과 보고 정상', '결과 보고 미달', '처리 건이 끝남'])
def test_승인_뒤_실행_중인_사건은_업무_효과와_결과_보고와_처리_건_끝으로_닫힌다(close, state):
    inc, fx = _approved(), Recorder()
    close(inc, fx)
    assert inc.state == state and inc.closed


@pytest.mark.parametrize('close, error', [
    (lambda inc, fx: machine.on_work_order(inc, {'ok': True, 'ref': 'WO-7'}, fx, work_order_only=True), 'cannot record work order'),
    (lambda inc, fx: machine.on_business_effect(inc, {'ok': True, 'ref': 'GR-7', 'kind': 'goods_receipt'}, fx), '담당자 승인 대기'),
], ids=['정비 요청 영수증', '입고 확인'])
def test_사람이_승인하지_않은_사건은_업무_효과로_닫지_않는다(close, error):
    inc, fx = _incident(), Recorder()
    with pytest.raises(ValueError, match=error):
        close(inc, fx)
    assert inc.state == 'AWAITING_APPROVAL' and not inc.closed


def test_승인_뒤_흐름이_새_승인으로_되돌아가면_사건도_승인_대기로_돌아가고_다시_수행도_연다():
    inc, fx = _approved(), Recorder()
    assert machine.on_recheck_reopen(inc, 'row-2', 'process', '효과 확인 미달 — 다시 판단', fx)
    assert inc.state == 'AWAITING_APPROVAL' and inc.approved_by is None
    assert (inc.superseded[-1]['kind'], inc.superseded[-1]['state_before'], inc.superseded[-1]['approvedBy']) == ('recheck', 'APPROVED_EXECUTING', 'user:me')
    assert machine.on_recheck_reopen(inc, 'row-2', 'process', '효과 확인 미달 — 다시 판단', fx) is False, '같은 되돌아감은 한 번만'
    with pytest.raises(ValueError, match='담당자 승인 대기'):
        machine.on_recheck_reopen(inc, 'row-3', 'process', '승인 대기 사건은 열 것이 없다', fx)
    machine.on_reject(inc, 'user:me', '두 번째 판단은 반려', fx)
    assert inc.state == 'REJECTED_BY_OPERATOR'
    other, fx = _approved(), Recorder()
    assert machine.on_rework_reopen(other, 'REQ-9', 'user:me', 'role:operator', '다시 판단', {}, fx)
    assert other.state == 'AWAITING_APPROVAL' and other.superseded[-1]['state_before'] == 'APPROVED_EXECUTING'
