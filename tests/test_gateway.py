from datetime import timedelta

from gw import validate as gw
from hydcommon.timeutil import now, to_iso


def cmd(cmd_id="CMD-1", actions=None, expires_in=120, asset="HYD-01"):
    return {"cmdId": cmd_id, "asset": asset, "incident": "INC-1", "source": "HITL",
            "actions": actions or [{"code": "FAN_BOOST", "fan_pct": 100}, {"code": "REDUCE_LOAD", "load_pct": 80}],
            "approvedBy": "OP-17", "expiresAt": to_iso(now() + timedelta(seconds=expires_in))}


def state(mode="REMOTE_AUTO"):
    st = gw.GatewayState()
    st.last_status["HYD-01"] = {"mode": mode, "state": "RUN"}
    return st


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
    assert gw.validate(cmd("CMD-9"), st, now()).ok
    d = gw.validate(cmd("CMD-9"), st, now())
    assert not d.ok and d.check == "DUPLICATE"


def test_manual_mode_rejected():
    d = gw.validate(cmd(), state(mode="REMOTE_MANUAL"), now())
    assert not d.ok and d.check == "MODE" and "REMOTE_MANUAL" in d.reason


def test_unknown_asset_status_rejected():
    st = gw.GatewayState()   # no status seen for the asset yet
    d = gw.validate(cmd(), st, now())
    assert not d.ok and d.check == "MODE"


def test_rate_limit_rejects_third_command_in_same_second():
    st = state()
    t = now()
    assert gw.validate(cmd("A"), st, t).ok
    assert gw.validate(cmd("B"), st, t).ok
    d = gw.validate(cmd("C"), st, t)
    assert not d.ok and d.check == "RATE_LIMIT"
    assert gw.validate(cmd("D"), st, t + timedelta(seconds=1)).ok


def test_alert_to_ot_levels():
    raise_ = gw.alert_to_ot({"alertId": "ALT-1", "asset": "HYD-01", "pattern": "COOLER_DEGRADATION", "state": "RAISE", "severity": "HIGH"})
    clear = gw.alert_to_ot({"alertId": "ALT-1", "asset": "HYD-01", "pattern": "COOLER_DEGRADATION", "state": "CLEAR", "severity": "HIGH"})
    assert raise_["level"] == 2 and clear["level"] == 0
    assert raise_["alertId"] == "ALT-1" and "COOLER_DEGRADATION" in raise_["text"]
