from datetime import timedelta

from gw import validate as gw
from hydcommon import schemas
from hydcommon.timeutil import now, to_iso

_APPROVED = []   # commands these tests treat as approved by process (A148 check ⑤ — the ledger is filled by state())


def cmd(cmd_id="CMD-1", actions=None, expires_in=120, asset="HYD-01"):
    c = {"cmdId": cmd_id, "asset": asset, "incident": "INC-1", "source": "HITL",
         "actions": actions or [{"code": "FAN_BOOST", "fan_pct": 100}, {"code": "REDUCE_LOAD", "load_pct": 80}],
         "approvedBy": "OP-17", "approvalId": "APR-" + cmd_id, "expiresAt": to_iso(now() + timedelta(seconds=expires_in))}
    _APPROVED.append(c)
    return c


def state(mode="REMOTE_AUTO"):
    st = gw.GatewayState()
    st.last_status["HYD-01"] = {"mode": mode, "state": "RUN"}
    _ledger(st)
    return st


def _ledger(st):
    for c in _APPROVED:
        gw.record_approval(st, {"actor": "process", "event": schemas.CMD_APPROVAL_LEDGER_EVENT, "detail": schemas.approval_ledger_record(c)})


def test_valid_cmd_passes_and_maps_writes():
    d = gw.validate(cmd(), state(), now())
    assert d.ok and d.check == "PASS"
    assert d.mqtt_payload["cmdId"] == "CMD-1" and d.mqtt_payload["source"] == "HITL"
    assert d.mqtt_payload["writes"] == [{"res": "FanSpeedSP", "v": 100}, {"res": "LoadSP", "v": 80}]
    assert "expiresAt" in d.mqtt_payload


def test_schema_error_rejected():
    d = gw.validate({"cmdId": "X"}, state(), now())
    assert not d.ok and d.check == "SCHEMA"


def test_unknown_action_rejected():
    d = gw.validate(cmd(actions=[{"code": "OPEN_VALVE", "pct": 50}]), state(), now())
    assert not d.ok and d.check == "WHITELIST"


def test_expired_rejected():
    d = gw.validate(cmd(expires_in=-1), state(), now())
    assert not d.ok and d.check == "EXPIRED"


def test_duplicate_rejected():
    st = state()
    c = cmd("CMD-9"); _ledger(st)
    assert gw.validate(c, st, now()).ok
    d = gw.validate(c, st, now())
    assert not d.ok and d.check == "DUPLICATE"


def test_manual_mode_rejected():
    d = gw.validate(cmd(), state(mode="REMOTE_MANUAL"), now())
    assert not d.ok and d.check == "MODE" and "REMOTE_MANUAL" in d.reason


def test_unknown_asset_status_rejected():
    st = gw.GatewayState()   # no status seen for the asset yet
    c = cmd(); _ledger(st)
    d = gw.validate(c, st, now())
    assert not d.ok and d.check == "MODE"


def test_rate_limit_rejects_third_command_in_same_second():
    st = state()
    t = now()
    a, b, c, d_ = cmd("A"), cmd("B"), cmd("C"), cmd("D"); _ledger(st)
    assert gw.validate(a, st, t).ok
    assert gw.validate(b, st, t).ok
    d = gw.validate(c, st, t)
    assert not d.ok and d.check == "RATE_LIMIT"
    assert gw.validate(d_, st, t + timedelta(seconds=1)).ok


def test_alert_to_ot_levels():
    raise_ = gw.alert_to_ot({"alertId": "ALT-1", "asset": "HYD-01", "pattern": "COOLER_DEGRADATION", "state": "RAISE", "severity": "HIGH"})
    clear = gw.alert_to_ot({"alertId": "ALT-1", "asset": "HYD-01", "pattern": "COOLER_DEGRADATION", "state": "CLEAR", "severity": "HIGH"})
    assert raise_["level"] == 2 and clear["level"] == 0
    assert raise_["alertId"] == "ALT-1" and "COOLER_DEGRADATION" in raise_["text"]
    assert raise_["display_text"] == "경보 발생 · 쿨러 성능 저하"
    assert clear["display_text"] == "경보 해제 · 쿨러 성능 저하"


def test_legacy_alert_display_upgrade_preserves_event_and_is_idempotent():
    old = {"alertId": "ALT-1", "pattern": "OVERHEAT_TRIP", "state": "CLEAR",
           "t": "2026-10-01T00:00:00Z", "level": 0, "text": "CLEAR OVERHEAT_TRIP (ALT-1)"}
    upgraded = gw.upgrade_retained_alert(old)
    assert {k: upgraded[k] for k in old} == old
    assert upgraded["display_text"] == "경보 해제 · 유온 보호 정지"
    assert gw.upgrade_retained_alert(upgraded) is None
    assert gw.upgrade_retained_alert({"state": "CLEAR"}) is None
    assert gw.upgrade_retained_alert([]) is None
