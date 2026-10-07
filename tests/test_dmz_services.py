"""DMZ and sink services (A144, sweep item 35): the behaviours docs/src/arch_internal.py recorded as drifting from their
docstrings — connect-ingest /healthz that was always 200, a non-object plant/+/status payload that killed the paho
thread, the sink's never-set batch-age gauge, and cmd-gateway's audit check names that matched no Decision.check."""
import asyncio
import importlib.util
import json
import sys
from collections import namedtuple
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.responses import JSONResponse

from gw import main as gw_main, validate as gw
from hydcommon import topics
from hydcommon.metrics import Registry
from hydcommon.service import make_app

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    """dmz/connect-ingest and it/connect-sink both ship a package called `app`; load each main.py under its own name."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ingest = _load("connect_ingest_main", ROOT / "dmz" / "connect-ingest" / "app" / "main.py")
sink = _load("connect_sink_main", ROOT / "it" / "connect-sink" / "app" / "main.py")


def _healthz(app):
    route = next(r for r in app.routes if getattr(r, "path", None) == "/healthz")
    body = route.endpoint()
    if isinstance(body, JSONResponse):
        return body.status_code, json.loads(body.body)
    return 200, body


# ---------------------------------------------------------------- hydcommon.service: ok decides the status code
def test_healthz_is_503_only_when_the_service_says_ok_false():
    reg = Registry()
    flag = {"ok": True}
    app = make_app("t", reg, lambda: {"ok": flag["ok"], "detail": 1})
    assert _healthz(app) == (200, {"ok": True, "detail": 1})
    flag["ok"] = False
    assert _healthz(app) == (503, {"ok": False, "detail": 1})
    # a health_fn that never sets `ok` (the old connect-ingest) can only ever be 200 — the defect this file closes
    assert _healthz(make_app("t2", Registry(), lambda: {"mqtt": False, "kafka": False}))[0] == 200


# ---------------------------------------------------------------- connect-ingest
def test_ingest_healthz_reports_each_broken_leg(monkeypatch):
    monkeypatch.setitem(ingest.state, "mqtt", True)
    monkeypatch.setitem(ingest.state, "kafka", True)
    monkeypatch.setitem(ingest.state, "pump_dead", False)
    assert _healthz(ingest.app)[0] == 200 and ingest.health()["ok"] is True
    monkeypatch.setitem(ingest.state, "mqtt", False)              # EMQX gone: on_disconnect flips it
    code, body = _healthz(ingest.app)
    assert code == 503 and body["ok"] is False and body["mqtt"] is False
    monkeypatch.setitem(ingest.state, "mqtt", True)
    monkeypatch.setitem(ingest.state, "kafka", False)             # producer never came up
    assert _healthz(ingest.app)[0] == 503
    monkeypatch.setitem(ingest.state, "kafka", True)
    monkeypatch.setitem(ingest.state, "pump_dead", True)          # pump task exited
    assert _healthz(ingest.app)[0] == 503


def test_ingest_on_disconnect_and_pump_watch_flip_the_flags(monkeypatch):
    monkeypatch.setitem(ingest.state, "mqtt", True)
    ingest._on_disconnect(None, None, None, 7)
    assert ingest.state["mqtt"] is False
    monkeypatch.setitem(ingest.state, "kafka", True)
    monkeypatch.setitem(ingest.state, "pump_dead", False)

    async def boom():
        raise RuntimeError("broker gone")

    async def run():
        task = asyncio.get_running_loop().create_task(boom())
        task.add_done_callback(ingest._watch)
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    asyncio.run(run())
    assert ingest.state["pump_dead"] is True and ingest.state["kafka"] is False and "broker gone" in ingest.state["pump_error"]


@pytest.mark.parametrize("payload", [b"[1, 2, 3]", b"42", b'"text"', b"null"])
def test_ingest_drops_non_object_payloads_instead_of_raising(monkeypatch, payload):
    monkeypatch.setitem(ingest.state, "malformed", 0)
    assert ingest.to_kafka("plant/hyd01/status", payload) is None
    assert ingest.to_kafka("plant/hyd01/tag/TS1", payload) is None
    assert ingest.state["malformed"] == 2
    # the paho callback path: no exception escapes (that is what used to end the network loop thread)
    ingest._on_message(None, None, SimpleNamespace(topic="plant/hyd01/status", payload=payload))


def test_ingest_still_replicates_object_payloads():
    ktopic, key, body = ingest.to_kafka("plant/hyd01/status", b'{"mode": "REMOTE_AUTO", "state": "RUN"}')
    assert ktopic == topics.K_STATUS and key == "hyd01" and body["asset"] == "HYD-01" and body["mode"] == "REMOTE_AUTO"
    ktopic, _, body = ingest.to_kafka("plant/hyd01/tag/TS1", b'{"t": "2026-10-08T00:00:00Z", "v": 55.1}')
    assert ktopic == topics.K_TAG and body["name"] == "TS1" and body["v"] == 55.1 and body["q"] == "good"
    assert ingest.to_kafka("plant/hyd01/status", b"{not json") is None


# ---------------------------------------------------------------- connect-sink
TP = namedtuple("TP", "topic partition")       # aiokafka's TopicPartition is hashable (a dict key in getmany batches)


def _rec(ts_ms, offset=0, value=None):
    return SimpleNamespace(timestamp=ts_ms, offset=offset, value=value or {})


def test_sink_batch_age_is_the_oldest_record_age():
    tp = TP(topics.K_TAG, 0)
    now = 1_700_000_100.0
    batches = {tp: [_rec(1_700_000_090_000, 1), _rec(1_700_000_095_000, 2)]}
    assert sink.batch_age_seconds(batches, now_s=now) == 10.0
    assert sink.batch_age_seconds({tp: []}, now_s=now) is None
    assert sink.batch_age_seconds({tp: [_rec(1_700_000_200_000)]}, now_s=now) == 0.0      # future-stamped record: clamp, not negative


def test_sink_store_records_sets_the_gauge(monkeypatch):
    class Cur:
        async def fetchone(self):
            return (0,)

    class Tx:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class Conn:
        def __init__(self):
            self.sql = []

        def transaction(self):
            return Tx()

        async def execute(self, sql, params=None):
            self.sql.append(sql.strip().split()[0].upper())
            return Cur()

    tp = TP(topics.K_ALERTS, 0)
    old_ms = int((1_700_000_000 - 42) * 1000)
    monkeypatch.setattr(sink.time, "time", lambda: 1_700_000_000.0)
    seen = {}
    monkeypatch.setattr(sink.g_lag, "set", lambda v, **labels: seen.setdefault("v", v))
    conn = Conn()
    # a malformed alert is counted, not written; the offset checkpoint still advances
    asyncio.run(sink.store_records(conn, {tp: [_rec(old_ms, 5, {"_raw": "x"})]}))
    assert seen["v"] == 42.0 and conn.sql[-1] == "INSERT"


# ---------------------------------------------------------------- cmd-gateway
def _cmd(cmd_id="CMD-1", **over):
    from datetime import timedelta
    from hydcommon.timeutil import now, to_iso
    base = {"cmdId": cmd_id, "asset": "HYD-01", "incident": "INC-1", "source": "HITL", "approvalId": "APR-" + cmd_id,
            "actions": [{"code": "FAN_BOOST", "fan_pct": 100}], "approvedBy": "OP-17", "expiresAt": to_iso(now() + timedelta(seconds=120))}
    return dict(base, **over)


def _approve(st, *cmds):
    """A148 check ⑤: register process's ledger record for these commands."""
    from hydcommon import schemas
    for c in cmds:
        assert gw.record_approval(st, {"actor": "process", "event": schemas.CMD_APPROVAL_LEDGER_EVENT, "detail": schemas.approval_ledger_record(c)})


def test_gateway_audit_check_names_are_the_decision_check_values():
    from hydcommon.timeutil import now
    st = gw.GatewayState()
    st.last_status["HYD-01"] = {"mode": "REMOTE_AUTO"}
    produced = set()
    produced.add(gw.validate({"cmdId": "X"}, st, now()).check)
    produced.add(gw.validate(_cmd(actions=[{"code": "OPEN_VALVE"}]), st, now()).check)
    produced.add(gw.validate(_cmd(expiresAt="2000-01-01T00:00:00Z"), st, now()).check)
    produced.add(gw.validate(_cmd("FORGED"), st, now()).check)          # A148: no ledger record → APPROVAL
    d, m, r1, r2, r3 = _cmd("D"), _cmd("M"), _cmd("R1"), _cmd("R2"), _cmd("R3"); _approve(st, d, m, r1, r2, r3)
    assert gw.validate(d, st, now()).ok
    produced.add(gw.validate(d, st, now()).check)
    st.last_status["HYD-01"] = {"mode": "REMOTE_MANUAL"}
    produced.add(gw.validate(m, st, now()).check)
    st.last_status["HYD-01"] = {"mode": "REMOTE_AUTO"}
    t = now()
    gw.validate(r1, st, t); gw.validate(r2, st, t)
    produced.add(gw.validate(r3, st, t).check)
    assert produced == set(gw.CHECKS), produced ^ set(gw.CHECKS)
    # the forwarded-command audit lists exactly these names (it used to say EXPIRY and MODE+RATE, which no rejection ever carries)
    import inspect
    assert "list(gw.CHECKS)" in inspect.getsource(gw_main.handle) and "EXPIRY" not in inspect.getsource(gw_main)
