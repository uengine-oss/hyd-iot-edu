"""soft-PLC(ot/plant-sim/plantsim/plc.py) — 명령 형식 · 출처 · 시한 · 중복 · 범위 · 인터록(G3b-1 · 10 · 8).

규칙: 어떤 꼴의 명령도 예외가 아니라 거절 사유로 끝난다. 거절한 명령은 아무것도 바꾸지 않고 「본 명령」으로 남지 않는다. 쓰기 0개는
완료가 아니라 거절. 모드마다 쓰는 주체가 정해져 있다(현장 패널 LOCAL 은 늘, FUXA 는 원격 모드, 관문 HITL 은 원격 자동만).
"""
from datetime import datetime, timezone

import pytest

from plantsim import plc, thermal

NOW = datetime(2026, 10, 30, 5, tzinfo=timezone.utc)
LATER = '2026-10-30T05:02:00Z'


def _cmd(writes=None, cmd_id='C1', **extra):
    return dict({'cmdId': cmd_id, 'writes': [{'res': 'FanSpeedSP', 'v': 80}] if writes is None else writes, 'expiresAt': LATER}, **extra)


@pytest.mark.parametrize('cmd, source, reason', [
    ('not an object', 'HITL', 'BAD_FORMAT'),
    ({'writes': [{'res': 'FanSpeedSP', 'v': 80}], 'expiresAt': LATER}, 'HITL', 'BAD_FORMAT'),     # cmdId 없음
    (_cmd(cmd_id=''), 'HITL', 'BAD_FORMAT'),                                                      # 빈 id
    (_cmd(writes=5), 'HITL', 'BAD_FORMAT'),                                                       # G3b-1: TypeError 였다
    (_cmd(writes=['x']), 'HITL', 'BAD_FORMAT'),
    (_cmd(writes=[]), 'HITL', 'NO_WRITES'),                                                       # G3b-10: 빈 쓰기가 DONE 이었다
    (_cmd(expiresAt=5), 'HITL', 'BAD_EXPIRY'),                                                    # G3b-1: AttributeError 였다
    ({'cmdId': 'C1', 'writes': [{'res': 'FanSpeedSP', 'v': 80}]}, 'HITL', 'BAD_EXPIRY'),          # 자동 명령에 시한 없음
    (_cmd(expiresAt='2026-10-30T04:59:00Z'), 'HITL', 'EXPIRED'),
    (_cmd(expiresAt='soon'), 'HITL', 'BAD_EXPIRY'),
    (_cmd(writes=[{'res': 'ValveSP', 'v': 1}]), 'HITL', 'UNKNOWN_RESOURCE'),
    (_cmd(writes=[{'res': 'FanSpeedSP', 'v': 101}]), 'HITL', 'OUT_OF_RANGE'),
    (_cmd(writes=[{'res': 'LoadSP', 'v': 59.9}]), 'HITL', 'OUT_OF_RANGE'),
    (_cmd(writes=[{'res': 'FanSpeedSP', 'v': '80'}]), 'HITL', 'OUT_OF_RANGE'),
    (_cmd(), 'SCRIPT', 'UNKNOWN_SOURCE'),
])
def test_어떤_꼴의_명령도_예외가_아니라_거절_사유로_끝나고_아무것도_바꾸지_않는다(cmd, source, reason):
    p, u = plc.PlcState(), thermal.UnitState()
    r = plc.apply_command(p, u, cmd, source, NOW)
    assert (r.result, r.reason, u.fan_pct, u.load_pct, list(p.recent_cmd_ids)) == ('REJECTED', reason, 60.0, 90.0, [])
    assert (p.last_result, p.last_reason) == ('REJECTED', reason)


@pytest.mark.parametrize('mode, source, ok', [
    ('REMOTE_AUTO', 'HITL', True), ('REMOTE_AUTO', 'FUXA', True), ('REMOTE_AUTO', 'LOCAL', True),
    ('REMOTE_MANUAL', 'HITL', False), ('REMOTE_MANUAL', 'FUXA', True), ('REMOTE_MANUAL', 'LOCAL', True),
    ('LOCAL', 'HITL', False), ('LOCAL', 'FUXA', False), ('LOCAL', 'LOCAL', True),      # G3b-10: 현장 제어에서 어떤 쓰기도 못 했다
])
def test_모드마다_쓸_수_있는_주체가_정해져_있다(mode, source, ok):
    p, u = plc.PlcState(mode=mode), thermal.UnitState()
    r = plc.apply_command(p, u, _cmd(), source, NOW)
    assert (r.result == 'DONE') is ok and (u.fan_pct == 80.0) is ok
    assert r.reason == (None if ok else 'MODE_MISMATCH')


def test_수동_쓰기는_원격_자동을_원격_수동으로_바꾸고_자동_명령은_모드를_두고_간다():
    p = plc.PlcState()
    plc.apply_command(p, thermal.UnitState(), _cmd(cmd_id='A1'), 'HITL', NOW)
    assert p.mode == 'REMOTE_AUTO'
    plc.apply_command(p, thermal.UnitState(), _cmd(cmd_id='F1'), 'FUXA', NOW)
    assert p.mode == 'REMOTE_MANUAL'


def test_실행한_명령만_중복으로_막고_거절한_명령의_id는_다시_쓸_수_있다():
    p, u = plc.PlcState(mode='REMOTE_MANUAL'), thermal.UnitState()
    assert plc.apply_command(p, u, _cmd(), 'HITL', NOW).reason == 'MODE_MISMATCH'
    p.mode = 'REMOTE_AUTO'
    assert plc.apply_command(p, u, _cmd(), 'HITL', NOW).result == 'DONE'
    assert plc.apply_command(p, u, _cmd(), 'HITL', NOW).reason == 'DUPLICATE'


def test_트립_중에는_리셋만_되고_뜨거우면_리셋도_거절한다():
    p, u = plc.PlcState(state='TRIP', trip='OVERTEMP'), thermal.UnitState(ts1=60.0)
    assert plc.apply_command(p, u, _cmd(cmd_id='a'), 'HITL', NOW).reason == 'INTERLOCK_TRIP'
    assert plc.apply_command(p, u, _cmd([{'res': 'Reset', 'v': 1}], 'b'), 'HITL', NOW).reason == 'RESET_TOO_HOT'
    u.ts1 = 54.9
    assert plc.apply_command(p, u, _cmd([{'res': 'Reset', 'v': 1}], 'c'), 'HITL', NOW).result == 'DONE' and p.state == 'RUN'


@pytest.mark.parametrize('ts1, ps1, vs1, trip', [(65.1, 180, 0.6, 'OVERTEMP'), (48, 129.9, 0.6, 'LOW_PRESSURE'),
                                                 (48, 180, 2.0, 'HIGH_VIBRATION'), (65.0, 130.0, 1.99, None)])
def test_인터록은_경계를_넘을_때만_트립한다(ts1, ps1, vs1, trip):
    p = plc.PlcState()
    plc.check_interlock(p, thermal.UnitState(ts1=ts1, ps1=ps1, vs1=vs1))
    assert (p.state, p.trip) == (('TRIP', trip) if trip else ('RUN', None))


@pytest.mark.parametrize('payload, writes', [
    ({'FanSpeedSP': 80}, [{'res': 'FanSpeedSP', 'v': 80}]),                     # FUXA 의 맨 꼴
    ({'writes': [{'res': 'LoadSP', 'v': 70}]}, [{'res': 'LoadSP', 'v': 70}]),
    ({'mode_text': 'x'}, []),                                                   # 자원이 아닌 칸 — 쓰기 0개(NO_WRITES 로 거절된다)
    (None, []),
])
def test_수동_쓰기는_두_꼴_모두_한_명령으로_바뀌고_id를_얻는다(payload, writes):
    cmd = plc.normalize_manual(payload, 'FUXA')
    assert cmd['writes'] == writes and cmd['cmdId'].startswith('FUXA-') and cmd['source'] == 'FUXA'


def test_수동_쓰기마다_다른_id다():
    assert len({plc.normalize_manual({'FanSpeedSP': 80}, 'LOCAL')['cmdId'] for _ in range(50)}) == 50


def test_상태에는_모든_사유의_한국어_표시가_있다():
    p = plc.PlcState(state='TRIP', trip='LOW_PRESSURE')
    plc.apply_command(p, thermal.UnitState(ts1=60), _cmd([{'res': 'Reset', 'v': 1}]), 'FUXA', NOW)
    st = plc.status_payload('HYD-02', p, thermal.UnitState(), '2026-10-30T05:00:00Z')
    assert (st['reason'], st['reason_text'], st['trip_text'], st['mode_text']) == ('RESET_TOO_HOT', plc.TEXT['RESET_TOO_HOT'], '토출 압력 낮음', '원격 자동')
    assert all(not v.isascii() for k, v in plc.TEXT.items()), '표시 사전에 영문이 남았다'
