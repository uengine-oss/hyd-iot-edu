"""2026-10-23 점검 E1 · E2 · E3 · E4 · E6 · E7 — 업무 DB(Supabase ent 스키마, migration 20261023000060)가 메모리 백엔드와 같은 규칙을 지키는가.

명시한 일회용 DB(HYD_PM_PG_DSN, migrations + seed 적용)에서만 돈다. 각 시험은 한 연결 안에서 업무 전체 초기화로 수업 시작값을 만든 뒤
끝나면 되돌린다(rollback). 같은 시나리오의 메모리 시험은 test_entsim_reset_scope.py.
"""
import json
import os
import re

import pytest
from hydcommon.maintenance_plan import plan

import test_pm_scoped_schedule as T

DSN = os.environ.get("HYD_PM_PG_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="HYD_PM_PG_DSN must be an explicit disposable seeded database")
SEAL = "P-PMP-SEAL"
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


def ex(cx, req):
    fn = "ent.exec_compensation" if req["skill"] in COMPENSATIONS else "ent.exec_skill"
    return cx.execute(f"select {fn}(%s::jsonb)", (json.dumps(req),)).fetchone()[0]


def one(cx, sql, *args):
    return cx.execute(sql, args).fetchone()[0]


def rows(cx):
    return {p: (h, r, o) for p, h, r, o in cx.execute("select part_no, on_hand, reserved, on_order from ent.spare_stock order by part_no")}


def start_rows(cx):
    return {p: (h, r, 0) for p, h, r in cx.execute("select part_no, base_on_hand, base_reserved from ent.spare_stock order by part_no")}


def b_request(cx, effect="reserve", decision="PG-B"):
    records = one(cx, "select ent.pm_status_read(null)")["records"]
    parts = one(cx, "select ent.spare_stock_read(null)")["records"]
    ctx = dict(asset="HYD-02", records=records, parts=parts)
    selected = T.skill("single")
    if effect == "issue":
        selected["maintenance_policy"]["stock_effect"] = "issue"
        window = dict(immediate=True, label="즉시")
    else:
        row = next(r for r in records if r["asset"] == "HYD-02")
        window = dict(id=row["night_window_id"], starts_at=row["night_window_at"], basis="hours_at_next_window", label="이번 예정된 정비 시간")
    return dict(skill="skill:schedule-maintenance-scoped", asset="HYD-02", decision=decision, option="skill:pm-source", by="test:review",
                params=dict(task="원문 정비", plan=plan(selected, dict(pm_context=ctx), window)))


def c_procure(cx, qty=6, decision="PG-C"):
    return ex(cx, dict(skill="skill:procure-part", asset="HYD-03", decision=decision, option="buy", by="test:buyer",
                       params=dict(part_no=SEAL, qty=qty, supplier="sup:b", amount=55 * qty)))


def receive(cx, ref):
    return ex(cx, dict(skill="skill:receive-goods", asset="HYD-03", decision="PG-GR", option="gr", by="t", params=dict(ref=ref)))


def po_status(cx, ref):
    return one(cx, "select status from ent.purchase_requests where id = %s", ref)


def test_pg_e1_c_reset_keeps_open_b_reservation_and_later_b_cancel_restores_base(cx):
    fwd = ex(cx, b_request(cx))
    assert rows(cx)[SEAL][1] == 3
    cx.execute("select ent.reset_spare_stock(%s)", (SEAL,))
    assert rows(cx)[SEAL][1] == 3
    ex(cx, T.cancellation(fwd))
    assert rows(cx)[SEAL] == start_rows(cx)[SEAL]


def test_pg_e2_b_reset_keeps_open_c_purchase_order_on_order(cx):
    pr = c_procure(cx)
    ex(cx, b_request(cx))
    cx.execute("select ent.reset_pm_counters(null)")
    assert po_status(cx, pr["ref"]) == "승인됨 → 발주" and rows(cx)[SEAL] == (3, 2, 6)
    assert one(cx, "select below_since is null from ent.spare_stock where part_no = %s", SEAL)
    receive(cx, pr["ref"])
    assert rows(cx)[SEAL] == (9, 2, 0)


def test_pg_e3_c_reset_closes_open_purchase_order(cx):
    import psycopg
    pr = c_procure(cx)
    cx.execute("select ent.reset_spare_stock(%s)", (SEAL,))
    assert po_status(cx, pr["ref"]) == "취소" and rows(cx)[SEAL] == start_rows(cx)[SEAL]
    kinds = [k for (k,) in cx.execute("select kind from ent.stock_movements where part_no = %s order by id desc limit 2", (SEAL,))]
    assert kinds == ["RESET", "CANCEL"]
    for req in (dict(skill="skill:delay-delivery", asset="HYD-03", by="t", params=dict(part_no=SEAL, days=3)),
                dict(skill="skill:receive-goods", asset="HYD-03", decision="PG-GR", option="gr", by="t", params=dict(ref=pr["ref"]))):
        cx.execute("savepoint s")
        with pytest.raises(psycopg.Error):
            ex(cx, req)
        cx.execute("rollback to savepoint s")


@pytest.mark.parametrize("effect", ["reserve", "issue"])
@pytest.mark.parametrize("path", ["B", "C-open", "C-received", "BC-reset-B-then-C", "BC-reset-C-then-B", "CB-received-reset-C-then-B"])
def test_pg_each_scenario_reset_returns_shared_part_to_class_start(cx, path, effect):
    assert rows(cx) == start_rows(cx)
    if path.startswith("C"):
        pr = c_procure(cx)
        if "received" in path:
            receive(cx, pr["ref"])
    if "B" in path:
        ex(cx, b_request(cx, effect))
    if path.startswith("BC"):
        c_procure(cx)
    order = path.split("reset-")[-1].split("-then-") if "reset-" in path else [path[0]]
    for which in order:
        cx.execute("select ent.reset_pm_counters(null)" if which == "B" else f"select ent.reset_spare_stock('{SEAL}')")
    assert rows(cx) == start_rows(cx)
    assert one(cx, "select count(*) from ent.purchase_requests where status = '승인됨 → 발주' and qty is not null") == 0
    assert one(cx, "select count(*) from ent.pm_part_reservations where released_at is null") == 0


def test_pg_full_reset_is_still_class_start(cx):
    c_procure(cx)
    ex(cx, b_request(cx))
    cx.execute("select ent.reset_executions()")
    assert rows(cx) == start_rows(cx)


def test_pg_e4_cancel_purchase_request_returns_on_order_and_records_movement(cx):
    pr = c_procure(cx)
    ex(cx, dict(skill="skill:cancel-purchase-request", asset="HYD-03", decision="PG-CX", option="x", by="test:buyer",
                compensates=pr["id"], params=dict(ref=pr["ref"])))
    assert po_status(cx, pr["ref"]) == "취소" and rows(cx)[SEAL] == (3, 2, 0)
    assert one(cx, "select below_since is not null from ent.spare_stock where part_no = %s", SEAL)
    move = cx.execute("select kind, qty, ref, by_whom from ent.stock_movements where part_no = %s order by id desc limit 1", (SEAL,)).fetchone()
    assert move == ("CANCEL", 6, pr["ref"], "test:buyer")


def test_pg_e6_cancel_work_order_clears_pm_plan_pointer(cx):
    window = one(cx, "select night_window_id from ent.pm_status where asset = 'HYD-02'")
    wo = ex(cx, dict(skill="skill:schedule-maintenance", asset="HYD-02", decision="PG-A", option="o", by="t",
                     params=dict(task="펌프 점검", window_id=window)))
    assert one(cx, "select plan_wo from ent.pm_counters where asset = 'HYD-02'") == wo["ref"]
    ex(cx, dict(skill="skill:cancel-work-order", asset="HYD-02", decision="PG-A2", option="x", by="t",
                compensates=wo["id"], params=dict(ref=wo["ref"])))
    assert cx.execute("select plan_wo, plan_window, planned_at from ent.pm_counters where asset = 'HYD-02'").fetchone() == (None, None, None)
    assert one(cx, "select pm_alert from ent.pm_status where asset = 'HYD-02'") is True
    assert ex(cx, b_request(cx))["ref"].startswith("WO-")


REF = re.compile(r"^(TX|WO|PR|GR|GI|RUN|PMR|SH)-\d{4}-[0-9A-F]{12}$")


def test_pg_e7_every_generated_number_has_48_bit_suffix(cx):
    made = []
    wo = ex(cx, dict(skill="skill:schedule-maintenance", asset="HYD-01", decision="PG-1", option="o", by="t", params=dict(task="오더")))
    pr = c_procure(cx)
    gr = receive(cx, pr["ref"])
    made += [wo["id"], wo["ref"], pr["id"], pr["ref"], gr["id"], gr["ref"]]
    for req in (dict(skill="skill:issue-spare", asset="HYD-03", decision="PG-GI", option="o", by="t", params=dict(part_no=SEAL, qty=1)),
                dict(skill="skill:pm-advance", asset="HYD-01", decision="PG-RUN", option="o", by="t", params=dict(hours=10)),
                dict(skill="skill:pm-reset", asset="HYD-01", decision="PG-PMR", option="o", by="t", params=dict()),
                dict(skill="skill:substitute-shipment", asset="HYD-01", decision="PG-SH", option="o", by="t", params=dict())):
        tx = ex(cx, req)
        made += [tx["id"], tx["ref"]]
    undo = ex(cx, dict(skill="skill:cancel-work-order", asset="HYD-01", decision="PG-X", option="x", by="t", compensates=wo["id"], params=dict(ref=wo["ref"])))
    made.append(undo["id"])
    assert all(REF.match(x) for x in made), [x for x in made if not REF.match(x)]
    assert {x.split("-")[0] for x in made} == {"TX", "WO", "PR", "GR", "GI", "RUN", "PMR", "SH"}
