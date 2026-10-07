"""A148 (remaining-sweep 69) — cmd-gateway check ⑤: a command is forwarded only with process's approval ledger record.

Before this check a client that could write `action.cmd` had the PLC act (`.evidence/a148/69/`, forged FAN_SET → ACK DONE).
"""
from datetime import timedelta

from gw import validate as gw
from hydcommon import schemas
from hydcommon.timeutil import now, to_iso
from procsvc import machine


def cmd(cmd_id="CMD-1", actions=None, expires_in=120, asset="HYD-01", approval_id="APR-1"):
    return {"cmdId": cmd_id, "asset": asset, "incident": "INC-1", "source": "HITL",
            "actions": actions or [{"code": "FAN_SET", "fan_pct": 65}], "approvedBy": "OP-17",
            "approvalId": approval_id, "expiresAt": to_iso(now() + timedelta(seconds=expires_in))}


def state():
    st = gw.GatewayState()
    st.last_status["HYD-01"] = {"mode": "REMOTE_AUTO", "state": "RUN"}
    return st


def ledger(st, c, key=None):
    evt = {"t": "x", "incident": c["incident"], "asset": c["asset"], "actor": "process",
           "event": schemas.CMD_APPROVAL_LEDGER_EVENT, "detail": schemas.approval_ledger_record(c, key)}
    assert gw.record_approval(st, evt)
    return evt


def test_fingerprint_is_deterministic_and_covers_the_approved_fields():
    a = cmd()
    assert schemas.cmd_fingerprint(a) == schemas.cmd_fingerprint(dict(a))
    assert schemas.cmd_fingerprint(a, "k1") != schemas.cmd_fingerprint(a, "k2")
    for change in ({"actions": [{"code": "FAN_SET", "fan_pct": 100}]}, {"asset": "HYD-02"}, {"approvedBy": "x"},
                   {"expiresAt": to_iso(now() + timedelta(seconds=10))}, {"approvalId": "APR-9"}, {"cmdId": "CMD-9"}):
        assert schemas.cmd_fingerprint(dict(a, **change)) != schemas.cmd_fingerprint(a), change
    assert schemas.cmd_fingerprint(dict(a, issuedAt="later")) == schemas.cmd_fingerprint(a)   # issuedAt is not approved content


def test_forged_command_without_a_ledger_record_is_rejected_before_mode_and_rate():
    d = gw.validate(cmd(), state(), now())
    assert not d.ok and d.check == "APPROVAL" and "no process approval record" in d.reason
    d = gw.validate({k: v for k, v in cmd().items() if k != "approvalId"}, state(), now())
    assert not d.ok and d.check == "APPROVAL" and "no approvalId" in d.reason


def test_recorded_command_passes_and_then_its_replay_is_a_duplicate():
    st = state(); c = cmd(); ledger(st, c)
    d = gw.validate(c, st, now())
    assert d.ok and d.check == "PASS" and d.mqtt_payload["writes"] == [{"res": "FanSpeedSP", "v": 65}]
    assert gw.validate(c, st, now()).check == "DUPLICATE"


def test_tampered_command_with_a_real_record_is_rejected():
    st = state(); c = cmd(); ledger(st, c)
    d = gw.validate(dict(c, actions=[{"code": "STOP"}]), st, now())
    assert not d.ok and d.check == "APPROVAL" and "fingerprint" in d.reason
    d = gw.validate(dict(c, approvalId="APR-other"), st, now())
    assert not d.ok and d.check == "APPROVAL" and "does not match" in d.reason


def test_record_written_with_another_key_is_not_honoured():
    st = state(); c = cmd(); ledger(st, c, key="attacker-guess")
    d = gw.validate(c, st, now())
    assert not d.ok and d.check == "APPROVAL"


def test_only_process_ledger_events_are_kept_and_the_ledger_is_bounded():
    st = gw.GatewayState()
    assert not gw.record_approval(st, {"actor": "cmd-gateway", "event": schemas.CMD_APPROVAL_LEDGER_EVENT, "detail": schemas.approval_ledger_record(cmd())})
    assert not gw.record_approval(st, {"actor": "process", "event": "CMD_PUBLISHED", "detail": {"cmdId": "CMD-1"}})
    assert not gw.record_approval(st, {"actor": "process", "event": schemas.CMD_APPROVAL_LEDGER_EVENT, "detail": {"cmdId": "CMD-1"}})
    for i in range(gw.APPROVALS_KEPT + 5):
        ledger(st, cmd(cmd_id=f"CMD-{i}"))
    assert len(st.approvals) == gw.APPROVALS_KEPT and "CMD-0" not in st.approvals and f"CMD-{gw.APPROVALS_KEPT + 4}" in st.approvals


class FX(machine.Effects):
    def __init__(self): self.out = []
    def emit_cmd(self, cmd): self.out.append(("cmd", cmd))
    def emit_audit(self, evt): self.out.append(("audit", evt))
    def set_timer(self, name, seconds): pass


def test_process_records_the_ledger_before_publishing_and_the_gateway_accepts_exactly_that_command():
    card = {"incident": None, "alert": {"alertId": "ALT-1", "asset": "HYD-01", "pattern": "COOLER_DEGRADATION", "severity": "HIGH", "state": "RAISE"},
            "freshness": {"ok": True, "age_s": 1.0}, "causes": [], "topCause": "cause:cooler-fin-fouling",
            "recommended": [{"code": "FAN_SET", "actionId": "act:fan-set", "name": "팬 설정", "kind": "command", "param": "fan_pct", "value": 100, "paramRange": [60, 100]}]}
    inc = machine.Incident.from_card("INC-1", card)
    fx = FX(); machine.on_card(inc)
    cmd_out = machine.on_approve(inc, "OP-17", [{"code": "FAN_SET", "fan_pct": 100}], now(), fx)
    kinds = [k for k, _ in fx.out]
    ledger_evt = next(e for k, e in fx.out if k == "audit" and e["event"] == schemas.CMD_APPROVAL_LEDGER_EVENT)
    assert kinds.index("cmd") > fx.out.index(("audit", ledger_evt)), "ledger record must go out before the command"
    assert cmd_out["approvalId"] == inc.approval_id and ledger_evt["detail"]["cmdId"] == cmd_out["cmdId"]
    assert inc.to_dict()["approvalId"] == inc.approval_id
    st = state(); assert gw.record_approval(st, ledger_evt)
    assert gw.validate(cmd_out, st, now()).ok
    assert gw.validate(dict(cmd_out, actions=[{"code": "FAN_SET", "fan_pct": 50}], cmdId="CMD-other"), st, now()).check == "APPROVAL"


def test_consume_loop_survives_an_undecodable_fetch_and_counts_it(monkeypatch):
    """A148: one record aiokafka cannot decode (UnsupportedCodecError from a snappy `rpk topic produce`) ended the loop and
    left /healthz 503 until a restart. Now the record is stepped over, the error counted, and consuming resumes."""
    import asyncio
    from gw import main as gw_main

    class Cons:
        rounds = 0
        def __init__(self): Cons.rounds += 1; self.committed = []; self.stopped = False
        def __aiter__(self): return self
        async def __anext__(self):
            if Cons.rounds == 1:
                raise RuntimeError("Libraries for snappy compression codec not found")
            raise StopAsyncIteration
        def assignment(self): return ["tp0"]
        async def position(self, tp): return 102
        async def commit(self, offsets): self.committed.append(offsets)
        async def stop(self): self.stopped = True

    made = []
    async def fake_consumer(*a, **k):
        c = Cons(); made.append(c); return c
    async def fake_producer(): return object()
    monkeypatch.setattr(gw_main, "make_consumer", fake_consumer)
    monkeypatch.setattr(gw_main, "make_producer", fake_producer)
    sleeps = []
    async def fake_sleep(s):
        sleeps.append(s)
        if Cons.rounds >= 2:
            raise asyncio.CancelledError
    monkeypatch.setattr(gw_main.asyncio, "sleep", fake_sleep)
    gw_main.state.pop("consumer_errors", None)
    try:
        asyncio.run(gw_main.run())
    except asyncio.CancelledError:
        pass
    assert gw_main.state["consumer_errors"] == 1 and "snappy" in gw_main.state["consumer_last_error"]
    assert made[0].committed == [{"tp0": 103}] and made[0].stopped          # stepped over the poison record, consumer closed
    assert Cons.rounds >= 2                                                 # a fresh consumer was opened afterwards


def test_sink_steps_over_an_undecodable_fetch_instead_of_dying(monkeypatch):
    """A148: the same snappy record ended connect-sink's loop (tag_1s stale → judgment deferred on data age)."""
    import asyncio
    import importlib.util
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("connect_sink_main_a148", root / "it" / "connect-sink" / "app" / "main.py")
    sink = importlib.util.module_from_spec(spec); sys.modules["connect_sink_main_a148"] = sink; spec.loader.exec_module(sink)

    class Cons:
        def __init__(self): self.calls = 0; self.seeks = []; self.stopped = False
        async def getmany(self, **k):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("Libraries for snappy compression codec not found")
            raise asyncio.CancelledError                     # second fetch: the loop is alive again; end the test
        def assignment(self): return ["cmd/0", "tag/0"]
        async def position(self, tp): return 102
        def seek(self, tp, off): self.seeks.append((tp, off))
        async def stop(self): self.stopped = True

    class Conn:
        async def close(self): pass
    cons = Cons()
    async def fake_consumer(*a, **k): return cons
    async def fake_db(): return Conn()
    monkeypatch.setattr(sink, "make_consumer", fake_consumer)
    monkeypatch.setattr(sink, "connect_db", fake_db)
    sink.state.pop("fetch_errors", None)
    try:
        asyncio.run(sink.run())
    except asyncio.CancelledError:
        pass
    assert sink.state["fetch_errors"] == 1 and "snappy" in sink.state["fetch_last_error"]
    assert cons.seeks == [("cmd/0", 103), ("tag/0", 103)] and cons.calls == 2 and cons.stopped
