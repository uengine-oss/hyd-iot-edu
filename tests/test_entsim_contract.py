"""2026-10-23 점검(.evidence/audit2/enterprise.md) E8 · E9 · E10 · E11 — 메모리 업무 시뮬레이터와 HTTP 계약.

E8 재시작이 시나리오 시각 기준점을 옮기지 않는다(기준점이 지났을 때만) · E9 /api/state 는 두 백엔드가 한 모양 ·
E10 결정 id 없는 실행은 멱등 키가 없다 · E11 일시 장애 503 · 모르는 부품 404 · 정비 완료 이력 · 출고 수량 0 거절 · 전체 초기화 원장.
같은 규칙의 업무 DB 시험은 test_entsim_contract_pg.py.
"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from entsim import data, main as entmain
from entsim.state import EnterpriseState, SNAPSHOT_TABLES
from test_entsim_reset_scope import b_request

SEAL = "P-PMP-SEAL"
# 포털 '업무 시스템' 표(it/portal/www/enterprise.js renderSystems)가 읽는 칸
PORTAL_FIELDS = {("cmms", "work_orders"): ("id", "asset", "task", "window"), ("erp", "purchase_requests"): ("id", "supplierName", "status"),
                 ("erp", "shipments"): ("id", "item", "qty", "from"), ("qms", "lot_dispositions"): ("lot", "status", "kind"),
                 ("ems", "ems_actions"): ("action",)}


@pytest.fixture
def memory(tmp_path, monkeypatch):
    monkeypatch.setenv("ENTERPRISE_STATE_PATH", str(tmp_path / "e.sqlite3"))
    data.reanchor()
    m = entmain.MemoryEnterprise()
    m.reset()
    monkeypatch.setattr(entmain, "ent", m)
    yield m
    data.reanchor()


def run_all_systems(execute):
    """한 번씩: 작업지시(창 라벨) · 구매요청 · 대체 출하 · 로트 격리 · 출하 승인 · 수요 제어 — /api/state 의 다섯 표를 모두 채운다."""
    for i, (skill, params) in enumerate((("skill:schedule-maintenance", {"window": "야간 정비창"}), ("skill:procure-part", {"supplier": "sup:b"}),
                                         ("skill:substitute-shipment", {}), ("skill:hold-lot", {}), ("skill:release-lot", {}),
                                         ("skill:demand-control", {}))):
        execute({"decision": f"D-SHAPE-{i}", "option": "o", "skill": skill, "asset": "HYD-01", "by": "t", "params": params})


def assert_one_shape(snap):
    """E9: 두 백엔드 모두 같은 표 이름 · 같은 칸 이름(화면 이름과 업무 DB 칸 이름을 같은 값으로)."""
    assert set(snap) == {"mes", *SNAPSHOT_TABLES}
    for system, names in SNAPSHOT_TABLES.items():
        assert set(snap[system]) == set(names), (system, set(snap[system]))
    for (system, table), fields in PORTAL_FIELDS.items():
        rows = snap[system][table]
        assert rows, (system, table)
        for row in rows:
            assert all(row.get(f) not in (None, "") for f in fields), (table, {f: row.get(f) for f in fields})
    wo, pr, sh = snap["cmms"]["work_orders"][0], snap["erp"]["purchase_requests"][0], snap["erp"]["shipments"][0]
    assert wo["window"] == wo["window_label"] == "야간 정비창"
    assert pr["supplierName"] == pr["supplier_name"] and sh["from"] == sh["source"]
    assert sorted(r["kind"] for r in snap["qms"]["lot_dispositions"]) == ["HOLD", "RELEASE"]     # 격리 · 출하 승인이 한 표에
    assert snap["ems"]["ems_actions"][0]["created_at"]


# ---------------------------------------------------------------- E9
def test_e9_memory_state_has_the_same_table_and_column_names_as_the_business_db(memory):
    run_all_systems(memory.execute)
    snap = TestClient(entmain.app).get("/api/state").json()
    assert_one_shape(snap)
    assert snap["mes"]["orders"][0]["due_in_h"] is not None


# ---------------------------------------------------------------- E8
def test_e8_restart_keeps_the_anchor_so_a_pending_b_plan_still_executes(tmp_path, monkeypatch):
    path = tmp_path / "e.sqlite3"
    monkeypatch.setenv("ENTERPRISE_STATE_PATH", str(path))
    anchor = datetime.now(timezone.utc) - timedelta(minutes=20)
    first = entmain.MemoryEnterprise()
    first.reset()
    first.st.reanchor(anchor)
    req = b_request(first.st)                                   # 승인 대기 중인 B 카드(창 id 는 기준점 + 9 h 시각을 품는다)
    first.st._db.close()
    data.reanchor()                                             # 재시작: 모듈을 다시 읽으면 기준점이 지금
    again = entmain.MemoryEnterprise()                          # 저장 상태에서 기준점도 되살린다
    monkeypatch.setattr(entmain, "ent", again)
    entmain._anchor_on_start()                                  # 지나지 않은 기준점은 옮기지 않는다
    assert data.scenario_start() == anchor
    tx = again.execute(req)
    assert tx["ref"].startswith("WO-")
    again.st._db.close()
    data.reanchor()


def test_e8_startup_reanchors_only_a_passed_anchor(memory):
    data.reanchor(datetime.now(timezone.utc) - timedelta(hours=1, minutes=50))   # 가장 이른 기한(출하 2 h) 전
    assert not memory.scenario_times_stale()
    kept = data.scenario_start()
    entmain._anchor_on_start()
    assert data.scenario_start() == kept
    data.reanchor(datetime.now(timezone.utc) - timedelta(hours=2, minutes=1))    # 출하 기한이 지남 → 시작 때 옮긴다
    assert memory.scenario_times_stale()
    entmain._anchor_on_start()
    assert abs((data.scenario_start() - datetime.now(timezone.utc)).total_seconds()) < 5


# ---------------------------------------------------------------- E10
def test_e10_executions_without_a_decision_have_no_idempotency_key(memory):
    req = {"skill": "skill:pm-advance", "asset": "HYD-01", "params": {"hours": 10}}
    a, b = memory.execute(req), memory.execute(req)
    assert a["ref"] != b["ref"] and a["id"] != b["id"]
    keyed = dict(req, decision="D-PM", option="o", by="t")
    assert memory.execute(keyed) == memory.execute(keyed)
    with pytest.raises(ValueError, match="idempotency"):
        memory.execute(dict(keyed, params={"hours": 20}))


# ---------------------------------------------------------------- E11 일시 장애 · 모르는 부품 · 출고 수량 · 정비 이력 · 전체 초기화 원장
class DownConn:
    def __enter__(self):
        import psycopg
        raise psycopg.OperationalError('connection to server at "host.docker.internal" failed: Connection refused')

    def __exit__(self, *a):
        return False


def test_e11_every_endpoint_answers_503_when_the_business_db_is_down(monkeypatch):
    from entsim.supabase_backend import SupabaseEnterprise
    monkeypatch.setattr(entmain, "ent", SupabaseEnterprise(lambda: DownConn()))
    client = TestClient(entmain.app)
    calls = [("get", "/api/state", None), ("get", "/api/transactions", None), ("get", "/api/archive", None), ("get", "/erp/spare_stock", None),
             ("get", "/cmms/history", None), ("post", "/api/reset", {}), ("post", "/api/reanchor", {}), ("post", "/erp/spare/reset", {"part_no": SEAL}),
             ("post", "/cmms/pm/reset", {}), ("post", "/api/exec", {"skill": "skill:issue-spare", "asset": "HYD-03"})]
    for method, path, body in calls:
        r = getattr(client, method)(path, **({"json": body} if body is not None else {}))
        assert r.status_code == 503 and "업무 DB에 연결하지 못했습니다" in r.json()["detail"], (path, r.status_code, r.text)


def test_e11_a_deadlock_at_execution_is_a_retry_not_a_refusal(monkeypatch):
    import psycopg

    def deadlock(_req):
        raise psycopg.errors.DeadlockDetected("deadlock detected")
    monkeypatch.setattr(entmain.ent, "execute", deadlock)
    r = TestClient(entmain.app).post("/api/exec", json={"decision": "D-1", "skill": "skill:issue-spare", "asset": "HYD-03"})
    assert r.status_code == 503 and "40P01" in r.json()["detail"]


def test_e11_unknown_part_or_asset_reset_is_404_and_changes_nothing(memory):
    client = TestClient(entmain.app)
    before = memory.st.snapshot()
    assert client.post("/erp/spare/reset", json={"part_no": "P-NOPE"}).status_code == 404
    assert client.post("/cmms/pm/reset", json={"asset": "HYD-99"}).status_code == 404
    assert memory.st.snapshot() == before


def test_e11_issue_quantity_zero_is_refused_not_turned_into_one(memory):
    on_hand = memory.st._s["erp"]["spare_stock"][SEAL]["on_hand"]
    for qty in (0, -1, "x", 1.5):
        with pytest.raises(ValueError, match="INVALID: issue quantity"):
            memory.execute({"skill": "skill:issue-spare", "asset": "HYD-03", "params": {"part_no": SEAL, "qty": qty}})
    assert memory.st._s["erp"]["spare_stock"][SEAL]["on_hand"] == on_hand
    memory.execute({"skill": "skill:issue-spare", "asset": "HYD-03", "params": {"part_no": SEAL}})          # 없으면 기본 1개
    assert memory.st._s["erp"]["spare_stock"][SEAL]["on_hand"] == on_hand - 1


def test_e11_completed_maintenance_enters_the_cmms_history_facts(memory):
    before = memory.read("cmms_history", asset="HYD-02")
    assert (before["facts"]["cleans_60d"], before["facts"]["last_clean_days"], before["work_orders"]) == (1, 21, [])
    wo = memory.execute({"decision": "D-WO", "option": "o", "skill": "skill:schedule-maintenance", "asset": "HYD-02", "by": "t", "params": {}})
    memory.execute({"decision": "D-DONE", "option": "o", "skill": "skill:complete-maintenance", "asset": "HYD-02", "by": "t", "params": {"ref": wo["ref"]}})
    after = memory.read("cmms_history", asset="HYD-02")
    assert (after["facts"]["cleans_60d"], after["facts"]["last_clean_days"]) == (2, 0)
    assert after["records"][0]["wo"] == wo["ref"] and after["records"][0]["days_ago"] == 0
    assert [w["id"] for w in after["work_orders"]] == [wo["ref"]] and after["work_orders"][0]["window_label"]


def test_e11_full_reset_archives_the_ledgers_and_restarts_them_with_reset_rows(memory):
    memory.execute({"skill": "skill:issue-spare", "asset": "HYD-03", "params": {"part_no": SEAL, "qty": 1}})
    memory.execute({"skill": "skill:pm-advance", "asset": "HYD-02", "params": {"hours": 10}})
    memory.reset()
    moves = memory.read("spare_stock", part=None)["movements"]
    assert sorted((m["part_no"], m["kind"], m["qty"]) for m in moves) == sorted((p, "RESET", 1 if p == SEAL else 0) for p in data.SPARE_BASE)
    log = memory.read("pm_status", asset=None)["log"]
    assert sorted((x["asset"], x["kind"], x["delta_h"]) for x in log) == [("HYD-01", "BASE", 0), ("HYD-02", "BASE", -10), ("HYD-03", "BASE", 0)]
    kept = memory.archive()["records"]
    newest = max(r["reset_no"] for r in kept)
    tables = {(r["table"], r["row"].get("kind")) for r in kept if r["reset_no"] == newest}
    assert {("stock_movements", "ISSUE"), ("pm_counter_log", "ADVANCE")} <= tables


def test_old_business_db_without_the_new_migration_stops_with_the_command_to_run():
    """supabase start 는 이미 있는 업무 DB 에 새 마이그레이션을 적용하지 않는다(2026-10-23 실측). 새 코드 + 옛 DB 면 시작이 할 일을 알려 주고 멈춘다."""
    import pytest
    from entsim.supabase_backend import SupabaseEnterprise

    class Missing(Exception):
        sqlstate = '42883'

    class Cur:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, *a): raise Missing('function ent.scenario_times_stale() does not exist')

    class Conn:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def cursor(self): return Cur()

    backend = SupabaseEnterprise.__new__(SupabaseEnterprise)
    backend._connect = lambda: Conn()
    with pytest.raises(RuntimeError, match='migration up'):
        backend.scenario_times_stale()
