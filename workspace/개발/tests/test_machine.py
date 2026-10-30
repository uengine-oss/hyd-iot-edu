"""사건 기계(procsvc/machine.py) — 명령 · ACK · 재관측 판정을 사건에 적는다(시한 · 판정 규칙은 작업 행 · 재관측 단계가 갖는다)."""
from datetime import datetime, timezone

import pytest

from procsvc import definition, machine, work_orders

NOW = datetime(2026, 10, 30, 9, 0, tzinfo=timezone.utc)
CARD = {'alert': {'alertId': 'ALT-1', 'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION'},
        'recommended': [{'code': 'FAN_SET', 'kind': 'command', 'param': 'fan_pct', 'paramRange': [0, 100], 'value': 100}]}


def _re_observing():
    inc = machine.Incident.from_card('INC-1', CARD)
    fx = work_orders._Audit()
    machine.on_card(inc)
    cmd = machine.on_approve(inc, 'user:kim-op', [{'code': 'FAN_SET', 'fan_pct': 100}], NOW, fx)
    machine.on_command_sent(inc, cmd['cmdId'], NOW, fx)
    machine.on_status(inc, {'cmdId': cmd['cmdId'], 'result': 'DONE'}, NOW, fx)
    return inc, cmd, fx


def test_명령을_보낸_뒤_ACK_마감은_벽시계_30초로_사건에_적힌다():
    inc = machine.Incident.from_card('INC-1', CARD)
    fx = work_orders._Audit()
    machine.on_card(inc)
    cmd = machine.on_approve(inc, 'user:kim-op', [{'code': 'FAN_SET', 'fan_pct': 100}], NOW, fx)
    assert inc.state == 'CMD_ISSUED' and inc.ack_due_at is None, '보내기 전에는 ACK 를 기다리지 않는다'
    machine.on_command_sent(inc, cmd['cmdId'], NOW, fx)
    assert inc.state == 'AWAITING_ACK' and inc.ack_due_at.startswith('2026-10-30T09:00:30')


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
