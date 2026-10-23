"""2026-10-23 점검 E8 · E9 · E10 · E11 — 업무 DB(Supabase ent 스키마, migration 20261023000061)가 메모리 백엔드와 같은 규칙을 지키는가.

명시한 일회용 DB(HYD_PM_PG_DSN, migrations + seed 적용)에서만 돈다. 대부분은 한 연결 안에서 업무 전체 초기화로 시작값을 만들고 끝나면
되돌린다(rollback). 읽기 계정 · 잠금 순서 시험은 연결이 둘 이상이라 커밋하고, 끝에 업무 전체 초기화로 시작값에 둔다.
같은 시나리오의 메모리 시험은 test_entsim_contract.py.
"""
import json
import os
import threading
import time

import pytest

from entsim import main as entmain
from entsim.supabase_backend import SupabaseEnterprise
from test_entsim_contract import SEAL, assert_one_shape, run_all_systems

DSN = os.environ.get("HYD_PM_PG_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="HYD_PM_PG_DSN must be an explicit disposable seeded database")
COMPENSATIONS = {"skill:cancel-maintenance-scoped", "skill:cancel-work-order", "skill:cancel-purchase-request"}


@pytest.fixture
def cx():
    import psycopg
    connection = psycopg.connect(DSN)
    try:
        connection.execute("select ent.reset_executions()")
        yield connection
    finally:
        connection.rollback()
        connection.close()


class InTx:
    """SupabaseEnterprise 가 시험 연결 하나의 트랜잭션 안에서 돌게(커밋 · 닫기 없음 — 끝에 시험이 되돌린다)."""
    def __init__(self, cx):
        self.cx = cx

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def cursor(self):
        return self.cx.cursor()

    def commit(self):
        pass

    def rollback(self):
        pass


def ex(cx, req):
    fn = "ent.exec_compensation" if req["skill"] in COMPENSATIONS else "ent.exec_skill"
    return cx.execute(f"select {fn}(%s::jsonb)", (json.dumps(req),)).fetchone()[0]


def one(cx, sql, *args):
    return cx.execute(sql, args).fetchone()[0]


def ent_tables(cx):
    return [t for (t,) in cx.execute("select tablename from pg_tables where schemaname = 'ent' order by tablename")]


# ---------------------------------------------------------------- E9
def test_pg_e9_state_has_the_same_table_and_column_names_as_memory(cx):
    be = SupabaseEnterprise(lambda: InTx(cx))
    run_all_systems(be.execute)
    assert_one_shape(be.snapshot())


# ---------------------------------------------------------------- E8
def test_pg_e8_startup_moves_only_a_passed_anchor(cx, monkeypatch):
    be = SupabaseEnterprise(lambda: InTx(cx))
    monkeypatch.setattr(entmain, "ent", be)
    # 20분 전에 옮긴 기준점(승인 대기 중인 B 카드가 그 창 id 를 들고 있다)
    cx.execute("update ent.maintenance_window_rules set first_at = first_at - interval '20 minutes'")
    cx.execute("update ent.production_orders set due_at = due_at - interval '20 minutes'")
    cx.execute("update ent.fg_inventory set ship_at = ship_at - interval '20 minutes'")
    window = one(cx, "select ent.pm_status_read('HYD-02')")["facts"]["night_window_id"]
    assert one(cx, "select ent.scenario_times_stale()") is False
    entmain._anchor_on_start()
    assert one(cx, "select ent.pm_status_read('HYD-02')")["facts"]["night_window_id"] == window
    cx.execute("update ent.fg_inventory set ship_at = now() - interval '1 minute' where asset = 'HYD-01'")   # 가장 이른 기한이 지남
    assert one(cx, "select ent.scenario_times_stale()") is True
    entmain._anchor_on_start()
    assert one(cx, "select ent.pm_status_read('HYD-02')")["facts"]["night_window_id"] != window
    assert one(cx, "select ent.scenario_times_stale()") is False


# ---------------------------------------------------------------- E10
def test_pg_e10_executions_without_a_decision_have_no_idempotency_key(cx):
    req = {"skill": "skill:pm-advance", "asset": "HYD-01", "params": {"hours": 10}}
    a, b = ex(cx, req), ex(cx, req)
    assert a["ref"] != b["ref"] and a["id"] != b["id"]
    keyed = dict(req, decision="D-PM", option="o", by="t")
    assert ex(cx, keyed) == ex(cx, keyed)
    import psycopg
    with pytest.raises(psycopg.errors.UniqueViolation, match="idempotency"):
        ex(cx, dict(keyed, params={"hours": 20}))


# ---------------------------------------------------------------- E11 ① service_role 권한
def test_pg_e11_service_role_can_run_every_write_rpc(cx):
    missing = [r for r in cx.execute("""
        select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace
         where n.nspname = 'ent' and ((c.relkind = 'r' and not (has_table_privilege('service_role', c.oid, 'select')
                 and has_table_privilege('service_role', c.oid, 'insert') and has_table_privilege('service_role', c.oid, 'update')
                 and has_table_privilege('service_role', c.oid, 'delete')))
              or (c.relkind = 'S' and not has_sequence_privilege('service_role', c.oid, 'usage')))""")]
    assert missing == []
    cx.execute("set local role service_role")
    gi = ex(cx, {"skill": "skill:issue-spare", "asset": "HYD-03", "params": {"part_no": SEAL, "qty": 1}})
    pr = ex(cx, {"skill": "skill:procure-part", "asset": "HYD-03", "decision": "D-SR", "option": "o", "by": "t",
                 "params": {"part_no": SEAL, "qty": 6, "supplier": "sup:b", "amount": 330}})
    ex(cx, {"skill": "skill:receive-goods", "asset": "HYD-03", "decision": "D-SR-GR", "option": "o", "by": "t", "params": {"ref": pr["ref"]}})
    ex(cx, {"skill": "skill:pm-advance", "asset": "HYD-02", "params": {"hours": 10}})
    one(cx, "select ent.reset_spare_stock(%s)", SEAL)
    one(cx, "select ent.reset_pm_counters(null)")
    cx.execute("select ent.reset_executions()")
    assert gi["ref"].startswith("GI-")
    cx.execute("reset role")


# ---------------------------------------------------------------- E11 ② 읽기 계정이 보관 표까지 같은 행을 본다
def test_pg_e11_reader_sees_every_row_the_admin_sees():
    import psycopg
    from psycopg.conninfo import conninfo_to_dict, make_conninfo
    with psycopg.connect(DSN, autocommit=True) as admin:
        ex(admin, {"skill": "skill:issue-spare", "asset": "HYD-03", "params": {"part_no": SEAL, "qty": 1}})
        admin.execute("select ent.reset_executions()")                        # 이동 원장 · 거래 원장이 보관 표로
        reader_dsn = make_conninfo(**dict(conninfo_to_dict(DSN), user="hyd_enterprise_reader", password="hyd-enterprise-read-local"))
        with psycopg.connect(reader_dsn) as reader:
            assert one(reader, "select current_user") == "hyd_enterprise_reader"
            counts = {t: (one(admin, f"select count(*) from ent.{t}"), one(reader, f"select count(*) from ent.{t}")) for t in ent_tables(admin)}
    assert counts["execution_archive"][0] > 0
    assert {t: c for t, c in counts.items() if c[0] != c[1]} == {}


# ---------------------------------------------------------------- E11 ③ 전체 초기화 원장
def test_pg_e11_full_reset_archives_the_ledgers_and_restarts_them_with_reset_rows(cx):
    ex(cx, {"skill": "skill:issue-spare", "asset": "HYD-03", "params": {"part_no": SEAL, "qty": 1}})
    ex(cx, {"skill": "skill:pm-advance", "asset": "HYD-02", "params": {"hours": 10}})
    cx.execute("select ent.reset_executions()")
    moves = sorted(cx.execute("select part_no, kind, qty from ent.stock_movements"))
    parts = [p for (p,) in cx.execute("select part_no from ent.spare_stock order by part_no")]
    assert moves == sorted((p, "RESET", 1 if p == SEAL else 0) for p in parts)
    log = sorted((a, k, float(d)) for a, k, d in cx.execute("select asset, kind, delta_h from ent.pm_counter_log"))
    assert log == [("HYD-01", "BASE", 0.0), ("HYD-02", "BASE", -10.0), ("HYD-03", "BASE", 0.0)]
    kept = set(cx.execute("select table_name, row->>'kind' from ent.execution_archive where reset_no = currval('ent.execution_reset_no')"))
    assert {("stock_movements", "ISSUE"), ("pm_counter_log", "ADVANCE")} <= kept


# ---------------------------------------------------------------- E11 ④ 잠금 순서: 전체 초기화는 계수기 → 작업지시
def test_pg_e11_full_reset_locks_counters_before_work_orders_so_it_cannot_deadlock():
    import psycopg
    with psycopg.connect(DSN, autocommit=True) as admin:
        admin.execute("select ent.reset_executions()")
        wo = ex(admin, {"skill": "skill:schedule-maintenance", "asset": "HYD-02", "params": {}})["ref"]
    holder = psycopg.connect(DSN)            # 원문 범위 전체 취소 · B [초기화] · 일정 변경처럼 계수기 → 작업지시 순으로 잠그는 쪽
    resetter = psycopg.connect(DSN)
    outcome = {}
    try:
        holder.execute("select 1 from ent.pm_counters where asset = 'HYD-02' for update")

        def full_reset():
            try:
                resetter.execute("set lock_timeout = '20s'")
                resetter.execute("select ent.reset_executions()")
                resetter.commit()
                outcome["reset"] = "ok"
            except psycopg.Error as e:
                resetter.rollback()
                outcome["reset"] = e.sqlstate
        worker = threading.Thread(target=full_reset)
        worker.start()
        time.sleep(1.5)                       # 전체 초기화가 계수기 잠금을 기다리는 동안
        try:
            holder.execute("set local lock_timeout = '5s'")
            holder.execute("select 1 from ent.work_orders where id = %s for update", (wo,))
            outcome["holder"] = "ok"
        except psycopg.Error as e:
            outcome["holder"] = e.sqlstate
        holder.rollback()
        worker.join(30)
    finally:
        holder.close()
        resetter.close()
    assert outcome == {"holder": "ok", "reset": "ok"}       # 교착(40P01) · 잠금 대기 초과(55P03) 없음


# ---------------------------------------------------------------- E11 모르는 부품 · 출고 수량 · 정비 이력
def test_pg_e11_unknown_part_or_asset_reset_raises_key_error(cx):
    be = SupabaseEnterprise(lambda: InTx(cx))
    with pytest.raises(KeyError):
        be.reset_spare_stock("P-NOPE")
    with pytest.raises(KeyError):
        be.reset_pm_counters("HYD-99")
    assert be.reset_spare_stock(SEAL)["facts"]["part_no"] == SEAL


def test_pg_e11_issue_quantity_zero_is_refused(cx):
    import psycopg
    for qty in (0, -1):
        cx.execute("savepoint s")
        with pytest.raises(psycopg.Error, match="INVALID: issue quantity must be positive"):
            ex(cx, {"skill": "skill:issue-spare", "asset": "HYD-03", "params": {"part_no": SEAL, "qty": qty}})
        cx.execute("rollback to savepoint s")


def test_pg_e11_completed_maintenance_enters_the_cmms_history_facts(cx):
    before = one(cx, "select ent.cmms_history('HYD-02')")
    assert (before["facts"]["cleans_60d"], before["facts"]["last_clean_days"], before["work_orders"]) == (1, 21, [])
    wo = ex(cx, {"decision": "D-WO", "option": "o", "skill": "skill:schedule-maintenance", "asset": "HYD-02", "by": "t", "params": {}})
    ex(cx, {"decision": "D-DONE", "option": "o", "skill": "skill:complete-maintenance", "asset": "HYD-02", "by": "t", "params": {"ref": wo["ref"]}})
    after = one(cx, "select ent.cmms_history('HYD-02')")
    assert (after["facts"]["cleans_60d"], after["facts"]["last_clean_days"]) == (2, 0)
    assert after["records"][0]["wo"] == wo["ref"] and after["records"][0]["days_ago"] == 0
    assert [w["id"] for w in after["work_orders"]] == [wo["ref"]] and after["work_orders"][0]["window_label"]
