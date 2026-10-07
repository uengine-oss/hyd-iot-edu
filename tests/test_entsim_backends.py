"""enterprise-sim: both backends answer the same contract; the Supabase one talks only to ent.* RPCs."""
import json

import pytest

from entsim import main as entmain
from entsim.supabase_backend import SupabaseEnterprise


def test_memory_backend_reads_and_executes_like_before(tmp_path, monkeypatch):
    monkeypatch.setenv("ENTERPRISE_STATE_PATH", str(tmp_path / "e.sqlite3"))
    m = entmain.MemoryEnterprise()
    m.reset()                                                  # A086: the scenario's hours count from this reset
    assert m.read("mes_orders", asset="HYD-01")["facts"]["due_in_h"] == 6 and m.read("ems_demand")["system"] == "EMS"
    assert m.read("scm_suppliers", part="P-CLR-CORE")["facts"]["std_price"] == 250
    tx = m.execute({"decision": "D1", "option": "skill:fan-max-derate", "skill": "skill:schedule-maintenance", "asset": "HYD-01", "by": "x", "params": {}})
    assert tx["system"] == "sys:cmms" and tx["ref"].startswith("WO-") and m.transactions()[0]["id"] == tx["id"]
    assert m.execute({"decision": "D1", "skill": "skill:schedule-maintenance", "option": "skill:fan-max-derate", "asset": "HYD-01", "by": "x", "params": {}}) == tx
    with pytest.raises(KeyError):
        m.read("erp_contract", asset="HYD-99")
    m.reset()
    assert m.transactions() == []


class Cur:
    def __init__(self, log, results):
        self.log, self.results, self.i = log, results, 0

    def __enter__(self): return self
    def __exit__(self, *a): return False

    def execute(self, sql, args=None):
        self.log.append((" ".join(sql.split()), args))

    def fetchone(self):
        r = self.results[self.i]; self.i += 1
        return r

    def fetchall(self):
        r = self.results[self.i]; self.i += 1
        return r


class Conn:
    def __init__(self, log, results):
        self.cur, self.committed = Cur(log, results), 0

    def __enter__(self): return self
    def __exit__(self, *a): return False
    def cursor(self): return self.cur
    def commit(self): self.committed += 1


def test_supabase_backend_reads_via_rpc_and_raises_for_unknown_asset():
    log = []
    be = SupabaseEnterprise(lambda: Conn(log, [({"system": "MES", "facts": {"due_in_h": 6}, "records": []},)]))
    assert be.read("mes_orders", asset="HYD-01")["facts"]["due_in_h"] == 6 and log[0] == ("select ent.mes_orders(%s)", ["HYD-01"])
    be2 = SupabaseEnterprise(lambda: Conn(log, [(json.dumps({"system": "ERP", "facts": None, "records": []}),)]))
    with pytest.raises(KeyError):
        be2.read("erp_contract", asset="HYD-99")


def test_supabase_backend_executes_through_exec_skill_and_commits():
    log = []
    tx = {"id": "TX-1003-AB12", "system": "sys:cmms", "skill": "skill:schedule-maintenance", "ref": "WO-1003-CD34", "detail": "x", "asset": "HYD-01"}
    conn = Conn(log, [(json.dumps(tx),)])
    be = SupabaseEnterprise(lambda: conn)
    req = {"decision": "D1", "option": "skill:fan-max-derate", "skill": "skill:schedule-maintenance", "asset": "HYD-01", "by": "x", "params": {"window": "야간 정비창"}}
    assert be.execute(req) == tx and conn.committed == 1
    sql, args = log[0]
    assert sql == "select ent.exec_skill(%s::jsonb)" and json.loads(args[0]) == req


def test_supabase_backend_transactions_and_reset():
    log = []
    conn = Conn(log, [[("TX-1", "2026-10-03 12:00:00+00", "sys:cmms", "skill:schedule-maintenance", "WO-1", "d", "HYD-01", "D1", "skill:a", "x")], None])
    be = SupabaseEnterprise(lambda: conn)
    rows = be.transactions()
    assert rows[0]["id"] == "TX-1" and rows[0]["decision"] == "D1" and rows[0]["by"] == "x" and isinstance(rows[0]["t"], str)
    be.reset()
    assert log[-1][0] == "select ent.reset_executions()" and conn.committed == 1


def test_app_health_reports_backend():
    h = entmain.app.routes
    assert any(r.path == "/api/exec" for r in h) and entmain.BACKEND in ("memory", "supabase")


def test_decision_receipts_survive_display_feed_truncation_and_reopen(tmp_path):
    from entsim.state import EnterpriseState
    path = tmp_path/'ledger.sqlite'
    state = EnterpriseState(path)
    req = {'decision':'original', 'skill':'skill:schedule-maintenance', 'asset':'HYD-01', 'params':{}}
    first = state.execute(req)
    for number in range(301):
        state.execute(dict(req, decision=f'later-{number}'))
    assert len(state.transactions())==300 and first not in state.transactions()
    assert state.transactions('original')==[first]
    state._db.close()
    restored=EnterpriseState(path)
    assert restored.transactions('original')==[first] and restored.transactions('absent')==[]
    restored._db.close()


def test_pg_decision_receipts_use_exact_query_without_display_limit():
    log=[]
    backend=SupabaseEnterprise(lambda:Conn(log,[[]]))
    assert backend.transactions('decision-older-than-page')==[]
    query,args=log[0]
    assert 'where decision_id=%s' in query and 'limit' not in query.lower()
    assert args==('decision-older-than-page',)


def test_idempotency_conflict_is_409_on_the_memory_backend_too(tmp_path, monkeypatch):
    """A143 (remaining-sweep 16): the supabase backend answered 409 for 'idempotency conflict' (DB error path) while the
    memory backend raised ValueError and answered 400 for the same conflict. One contract for both."""
    from fastapi.testclient import TestClient
    monkeypatch.setenv("ENTERPRISE_STATE_PATH", str(tmp_path / "e.sqlite3"))
    client = TestClient(entmain.app)
    body = {"decision": "D-a143", "option": "skill:x", "skill": "skill:schedule-maintenance", "asset": "HYD-01", "by": "x", "params": {}}
    assert client.post("/api/exec", json=body).status_code == 200
    r = client.post("/api/exec", json=dict(body, asset="HYD-02"))
    assert r.status_code == 409 and "idempotency" in r.json()["detail"]
    assert client.post("/api/exec", json=dict(body, skill="skill:nope", decision="D-other")).status_code == 400   # other ValueErrors stay 400
