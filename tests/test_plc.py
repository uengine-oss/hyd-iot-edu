from datetime import timedelta

from plantsim import plc, thermal
from hydcommon.timeutil import now, to_iso


def mk(mode="REMOTE_AUTO", ts1=48.0):
    p = plc.PlcState(mode=mode)
    u = thermal.UnitState()
    u.ts1 = ts1
    return p, u


def auto_cmd(cmd_id="CMD-1", fan=100, load=80, expires_in=120):
    return {"cmdId": cmd_id, "source": "HITL", "expiresAt": to_iso(now() + timedelta(seconds=expires_in)),
            "writes": [{"res": "FanSpeedSP", "v": fan}, {"res": "LoadSP", "v": load}]}


def test_auto_cmd_applied_in_remote_auto():
    p, u = mk()
    r = plc.apply_command(p, u, auto_cmd(), source="HITL", now=now())
    assert r.result == "DONE" and r.reason is None
    assert u.fan_pct == 100 and u.load_pct == 80


def test_auto_cmd_rejected_in_remote_manual():
    p, u = mk(mode="REMOTE_MANUAL")
    r = plc.apply_command(p, u, auto_cmd(), source="HITL", now=now())
    assert r.result == "REJECTED" and r.reason == "MODE_MISMATCH"
    assert u.fan_pct == 60


def test_expired_cmd_rejected():
    p, u = mk()
    r = plc.apply_command(p, u, auto_cmd(expires_in=-5), source="HITL", now=now())
    assert r.result == "REJECTED" and r.reason == "EXPIRED"


def test_duplicate_cmd_id_rejected():
    p, u = mk()
    plc.apply_command(p, u, auto_cmd("CMD-9"), source="HITL", now=now())
    r = plc.apply_command(p, u, auto_cmd("CMD-9"), source="HITL", now=now())
    assert r.result == "REJECTED" and r.reason == "DUPLICATE"


def test_load_below_60_rejected():
    p, u = mk()
    r = plc.apply_command(p, u, auto_cmd(load=50), source="HITL", now=now())
    assert r.result == "REJECTED" and r.reason == "OUT_OF_RANGE"
    assert u.load_pct == 90


def test_command_rejected_while_tripped():
    p, u = mk(ts1=70.0)
    plc.check_interlock(p, u)
    assert p.state == "TRIP" and p.trip == "OVERTEMP"
    r = plc.apply_command(p, u, auto_cmd(), source="HITL", now=now())
    assert r.result == "REJECTED" and r.reason == "INTERLOCK_TRIP"


def test_reset_allowed_below_55_only():
    p, u = mk(ts1=70.0)
    plc.check_interlock(p, u)
    reset = {"cmdId": "R1", "source": "FUXA", "writes": [{"res": "Reset", "v": 1}]}
    r = plc.apply_command(p, u, reset, source="FUXA", now=now())
    assert r.result == "REJECTED" and r.reason == "RESET_TOO_HOT"
    u.ts1 = 50.0
    r = plc.apply_command(p, u, dict(reset, cmdId="R2"), source="FUXA", now=now())
    assert r.result == "DONE" and p.state == "RUN" and p.trip is None


def test_manual_in_auto_reverts_mode():
    p, u = mk(mode="REMOTE_AUTO")
    manual = {"cmdId": "M1", "source": "FUXA", "writes": [{"res": "FanSpeedSP", "v": 80}]}
    r = plc.apply_command(p, u, manual, source="FUXA", now=now())
    assert r.result == "DONE" and u.fan_pct == 80
    assert p.mode == "REMOTE_MANUAL"


def test_manual_rejected_in_local():
    p, u = mk(mode="LOCAL")
    manual = {"cmdId": "M1", "source": "FUXA", "writes": [{"res": "FanSpeedSP", "v": 80}]}
    r = plc.apply_command(p, u, manual, source="FUXA", now=now())
    assert r.result == "REJECTED" and r.reason == "MODE_MISMATCH"


def test_trip_when_ts1_over_65():
    p, u = mk(ts1=65.5)
    plc.check_interlock(p, u)
    assert p.state == "TRIP"
    u.ts1 = 50
    plc.check_interlock(p, u)  # no auto-reset: needs explicit RESET
    assert p.state == "TRIP"


def test_set_mode_only_from_fuxa_or_local():
    p, u = mk()
    assert plc.set_mode(p, "REMOTE_MANUAL", requester="FUXA") is True
    assert p.mode == "REMOTE_MANUAL"
    assert plc.set_mode(p, "REMOTE_AUTO", requester="HITL") is False
    assert p.mode == "REMOTE_MANUAL"
    assert plc.set_mode(p, "BOGUS", requester="FUXA") is False


def test_normalize_manual_simple_payload():
    cmd = plc.normalize_manual({"FanSpeedSP": 80})
    assert cmd["source"] == "FUXA" and cmd["cmdId"].startswith("FUXA-")
    assert cmd["writes"] == [{"res": "FanSpeedSP", "v": 80}]
    full = {"cmdId": "X", "source": "FUXA", "writes": [{"res": "LoadSP", "v": 70}]}
    assert plc.normalize_manual(full) == full


def test_status_payload_contains_ack_fields():
    p, u = mk()
    plc.apply_command(p, u, auto_cmd("CMD-77"), source="HITL", now=now())
    st = plc.status_payload("HYD-01", p, u, "2026-09-23T10:00:00Z")
    assert st["asset"] == "HYD-01" and st["mode"] == "REMOTE_AUTO" and st["state"] == "RUN"
    assert st["cmdId"] == "CMD-77" and st["result"] == "DONE" and st["interlock"] == "PASS"
    assert st["fan_pct"] == 100 and st["load_pct"] == 80
