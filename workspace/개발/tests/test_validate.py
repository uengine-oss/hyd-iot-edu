"""명령 관문의 검사 일곱 · 경보판(dmz/cmd-gateway/gw/validate.py) — G5b-02 · G3b-6 · 22.

규칙: 위조 · 변조 · 재전송 · 형식 오류 · 모드 · 속도를 각 검사 이름으로 거절하고, 거절한 명령은 「보낸 명령」으로 남지 않는다.
승인 장부는 처음 기록을 지킨다. 경보판은 설비의 활성 경보 전부를 보이고 하나가 풀려도 남은 경보가 있으면 경보다.
"""
from datetime import datetime, timedelta, timezone

import pytest

from gw import validate as gw
from hydcommon import schemas

KEY = 'test-fingerprint-key'
NOW = datetime(2026, 10, 30, 5, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def fingerprint_key(monkeypatch):
    monkeypatch.setenv('CMD_FINGERPRINT_KEY', KEY)


def _cmd(**change):
    return dict({'cmdId': 'CMD-1', 'asset': 'HYD-01', 'incident': 'INC-1', 'source': 'HITL', 'approvedBy': 'user:kim-op',
                 'approvalId': 'APR-1', 'expiresAt': (NOW + timedelta(seconds=120)).isoformat(),
                 'actions': [{'code': 'FAN_SET', 'fan_pct': 100}]}, **change)


def _state(cmd, mode='REMOTE_AUTO'):
    st = gw.GatewayState()
    gw.record_approval(st, {'actor': 'process', 'event': schemas.CMD_APPROVAL_LEDGER_EVENT, 'detail': schemas.approval_ledger_record(cmd, KEY)})
    st.last_status['HYD-01'] = {'mode': mode}
    return st


def test_승인_기록과_같은_명령은_PLC_쓰기로_보낸다():
    d = gw.validate(_cmd(), _state(_cmd()), NOW)
    assert (d.ok, d.mqtt_payload['writes']) == (True, [{'res': 'FanSpeedSP', 'v': 100}])


@pytest.mark.parametrize('sent, check', [
    (_cmd(actions=[{'code': 'FAN_SET'}]), 'SCHEMA'),                         # G3b-22: 매개변수 없음 — KeyError 로 기록 없이 사라졌다
    ('not a dict', 'SCHEMA'),
    (_cmd(actions=[{'code': 'PRESSURE_SET', 'value': 200}]), 'WHITELIST'),
    (_cmd(expiresAt=(NOW - timedelta(seconds=1)).isoformat()), 'EXPIRED'),
    (_cmd(expiresAt='soon'), 'EXPIRED'),
    (_cmd(actions=[{'code': 'FAN_SET', 'fan_pct': 99}]), 'APPROVAL'),       # 변조
    (_cmd(cmdId='CMD-forged'), 'APPROVAL'),                                 # 위조
    (_cmd(approvalId='APR-2'), 'APPROVAL'),
])
def test_어긋난_명령은_그_검사_이름으로_거절하고_본_명령으로_남기지_않는다(sent, check):
    st = _state(_cmd())
    d = gw.validate(sent, st, NOW)
    assert (d.ok, d.check) == (False, check) and list(st.seen_cmd_ids) == []


def test_같은_명령을_다시_보내면_중복이다():
    st = _state(_cmd())
    assert gw.validate(_cmd(), st, NOW).ok and gw.validate(_cmd(), st, NOW).check == 'DUPLICATE'


@pytest.mark.parametrize('status, ok', [({'mode': 'REMOTE_AUTO'}, True), ({'mode': 'REMOTE_MANUAL'}, False), (None, False)])
def test_PLC가_원격_자동일_때만_보낸다(status, ok):
    st = _state(_cmd())
    st.last_status = {'HYD-01': status} if status else {}
    d = gw.validate(_cmd(), st, NOW)
    assert d.ok is ok and (ok or d.check == 'MODE')


def test_1초에_세_번째_명령은_속도_제한이다():
    cmds = [_cmd(cmdId=f'CMD-{i}', approvalId=f'APR-{i}') for i in range(3)]
    st = _state(cmds[0])
    for c in cmds[1:]:
        gw.record_approval(st, {'actor': 'process', 'event': schemas.CMD_APPROVAL_LEDGER_EVENT, 'detail': schemas.approval_ledger_record(c, KEY)})
    assert [gw.validate(c, st, NOW).check for c in cmds] == ['PASS', 'PASS', 'RATE_LIMIT']


def test_승인_장부는_처음_기록을_지키고_다른_기록은_충돌이다():
    st = gw.GatewayState()
    rec = {'actor': 'process', 'event': schemas.CMD_APPROVAL_LEDGER_EVENT, 'detail': schemas.approval_ledger_record(_cmd(), KEY)}
    forged = {'actor': 'process', 'event': schemas.CMD_APPROVAL_LEDGER_EVENT,
              'detail': schemas.approval_ledger_record(_cmd(actions=[{'code': 'LOAD_SET', 'load_pct': 60}]), KEY)}
    assert [gw.record_approval(st, r) for r in (rec, rec, forged, {'actor': 'student', 'event': 'X'})] == ['kept', 'same', 'conflict', 'ignored']
    assert st.approvals['CMD-1'] == rec['detail']


def test_거절_검사마다_사람이_읽는_문장이_있다():
    """검사 거절(CHECKS)과 모든 검사를 통과한 뒤 설비 브로커가 받지 않은 거절(PUBLISH_CHECK — G3b-14)마다 학생 문장이 있다."""
    assert set(gw.CHECK_TEXT) == set(gw.CHECKS) | {gw.PUBLISH_CHECK} and all(not t.isascii() for t in gw.CHECK_TEXT.values())


def _alert(aid, pattern, state, t, name):
    return {'alertId': aid, 'asset': 'HYD-01', 'pattern': pattern, 'name': name, 'severity': 'HIGH', 'state': state, 't': t}


def test_경보판은_남은_경보가_있는_동안_경보이고_모든_이름을_보인다():
    """G3b-6: 쿨러 경보가 트립보다 먼저 풀리면 트립이 살아 있는데 FUXA 가 초록 · 「경보 해제」였다."""
    board = gw.AlertBoard()
    board.apply(_alert('A1', 'COOLER_DEGRADATION', 'RAISE', '2026-10-30T05:00:00Z', '쿨러 성능 저하'))
    shown = board.apply(_alert('T1', 'OVERHEAT_TRIP', 'RAISE', '2026-10-30T05:01:00Z', '과열 인터록 트립'))
    assert (shown['level'], shown['display_text']) == (2, '경보 2건 · 쿨러 성능 저하, 과열 인터록 트립')
    shown = board.apply(_alert('A1', 'COOLER_DEGRADATION', 'CLEAR', '2026-10-30T05:02:00Z', '쿨러 성능 저하'))
    assert (shown['level'], shown['display_text']) == (2, '경보 1건 · 과열 인터록 트립')
    shown = board.apply(_alert('T1', 'OVERHEAT_TRIP', 'CLEAR', '2026-10-30T05:03:00Z', '과열 인터록 트립'))
    assert (shown['level'], shown['display_text'], shown['count']) == (0, '경보 없음', 0)


def test_다시_켜진_관문은_보관된_경보판을_한_번만_되읽는다():
    board, live = gw.AlertBoard(), gw.AlertBoard()
    retained = live.apply(_alert('T1', 'OVERHEAT_TRIP', 'RAISE', '2026-10-30T05:01:00Z', None))
    assert board.restore('HYD-01', retained) and board.display('HYD-01')['display_text'] == '경보 1건 · OVERHEAT_TRIP'
    assert not board.restore('HYD-01', {'active': []})                 # 이미 아는 설비는 덮지 않는다
    assert not gw.AlertBoard().restore('HYD-01', {'active': [{'alertId': 5}]})
