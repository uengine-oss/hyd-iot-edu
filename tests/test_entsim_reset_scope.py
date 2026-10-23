"""2026-10-23 점검(.evidence/audit2/enterprise.md) E1 · E2 · E3 · E4 · E6 · E7 — 메모리 업무 시뮬레이터가 고친 뒤 지켜야 할 동작.

B [초기화](reset_pm_counters)는 정기 정비 오더가 잡은 수량만, C [초기화](reset_spare_stock)는 열린 발주를 닫고 그 수량만 되돌린다.
씰 키트(P-PMP-SEAL)는 두 시나리오가 같이 쓰므로, 한쪽 초기화가 다른 쪽 진행 중 건을 지우면 안 된다. 같은 규칙의 업무 DB 시험은
test_entsim_reset_scope_pg.py.
"""
import re

import pytest
from hydcommon.maintenance_plan import plan

from entsim import data
from entsim.state import EnterpriseState, PO_OPEN, CANCELLED
import test_pm_scoped_schedule as T

SEAL = "P-PMP-SEAL"


def stock(st, part=SEAL):
    return st._s["erp"]["spare_stock"][part]


def rows(st):
    return {p: (r["on_hand"], r["reserved"], r["on_order"]) for p, r in st._s["erp"]["spare_stock"].items()}


def start_rows():
    return {p: (b["on_hand"], b["reserved"], 0) for p, b in data.SPARE_BASE.items()}


def b_request(st, effect="reserve", decision="DEC-B"):
    """시나리오 B: HYD-02 원문 정비 범위 단독 오더(씰 1 · 필터 1). reserve = 예정된 정비 시간 예약, issue = 즉시 출고."""
    ctx = T.context(st)
    selected = T.skill("single")
    if effect == "issue":
        selected["maintenance_policy"]["stock_effect"] = "issue"
        window = dict(immediate=True, label="즉시")
    else:
        row = next(r for r in ctx["records"] if r["asset"] == "HYD-02")
        window = dict(id=row["night_window_id"], starts_at=row["night_window_at"], basis="hours_at_next_window", label="이번 예정된 정비 시간")
    return dict(skill="skill:schedule-maintenance-scoped", asset="HYD-02", decision=decision, option="skill:pm-source", by="t",
                params=dict(task="원문 정비", plan=plan(selected, dict(pm_context=ctx), window)))


def c_procure(st, qty=6, decision="DEC-C"):
    return st.execute(dict(skill="skill:procure-part", asset="HYD-03", decision=decision, option="buy", by="t",
                           params=dict(part_no=SEAL, qty=qty, supplier="sup:b", amount=55 * qty)))


def po(st, ref):
    return next(p for p in st._s["erp"]["purchase_requests"] if p["id"] == ref)


# ---------------------------------------------------------------- E1: C [초기화]가 진행 중 B 오더의 예약을 지우지 않는다
def test_e1_c_reset_keeps_open_b_reservation_and_later_b_cancel_restores_base():
    st = EnterpriseState()
    fwd = st.execute(b_request(st))
    assert stock(st)["reserved"] == 3                                  # 기준 2 + B 1
    st.reset_spare_stock(SEAL)                                         # C [초기화]
    assert stock(st)["reserved"] == 3                                  # B 오더(배정됨)가 잡은 1개는 남는다
    st.execute(dict(skill="skill:cancel-maintenance-scoped", asset="HYD-02", decision="DEC-UNDO", option="x", by="t",
                    compensates=fwd["id"], params=dict(ref=fwd["ref"])))
    assert rows(st)[SEAL] == start_rows()[SEAL]                        # HYD-03 기준 예약 2개는 그대로
    assert st._stock_view(stock(st))["available"] == 1


# ---------------------------------------------------------------- E2: B [초기화]가 C 발주의 입고 예정을 지우지 않는다
def test_e2_b_reset_keeps_open_c_purchase_order_on_order():
    st = EnterpriseState()
    pr = c_procure(st)
    st.execute(b_request(st))
    st.reset_pm_counters()                                             # B [초기화]
    assert po(st, pr["ref"])["status"] == PO_OPEN and stock(st)["on_order"] == 6 and stock(st)["reserved"] == 2
    assert st._stock_view(stock(st))["below_reorder_point"] is False   # 발주가 살아 있으니 '재고 보충 필요'가 다시 켜지지 않는다
    st.execute(dict(skill="skill:receive-goods", asset="HYD-03", decision="DEC-GR", option="gr", by="t", params=dict(ref=pr["ref"])))
    assert (stock(st)["on_hand"], stock(st)["on_order"]) == (9, 0)


# ---------------------------------------------------------------- E3: C [초기화]가 열린 발주를 닫는다
def test_e3_c_reset_closes_open_purchase_order_so_old_order_cannot_be_received_or_delayed():
    st = EnterpriseState()
    pr = c_procure(st)
    st.reset_spare_stock(SEAL)
    assert po(st, pr["ref"])["status"] == CANCELLED and po(st, pr["ref"])["cancelled_at"] and stock(st)["on_order"] == 0
    kinds = [m["kind"] for m in st.spare_stock(SEAL)["movements"]]
    assert kinds[:2] == ["RESET", "CANCEL"]                            # 발주 취소도 이동 원장에 남는다
    with pytest.raises(ValueError, match="no open purchase order"):
        st.execute(dict(skill="skill:delay-delivery", asset="HYD-03", by="t", params=dict(part_no=SEAL, days=3)))
    with pytest.raises(ValueError, match="cannot be received"):
        st.execute(dict(skill="skill:receive-goods", asset="HYD-03", decision="DEC-GR", option="gr", by="t", params=dict(ref=pr["ref"])))
    assert rows(st)[SEAL] == start_rows()[SEAL]


# ---------------------------------------------------------------- 수업 시작값으로 돌아가는가 (B만 · C만 · 둘 다 · 순서 바꿔)
@pytest.mark.parametrize("effect", ["reserve", "issue"])
@pytest.mark.parametrize("path", ["B", "C-open", "C-received", "BC-reset-B-then-C", "BC-reset-C-then-B", "CB-received-reset-C-then-B"])
def test_each_scenario_reset_returns_shared_part_to_class_start(path, effect):
    st = EnterpriseState()
    assert rows(st) == start_rows()
    if path.startswith("C"):
        pr = c_procure(st)
        if "received" in path:
            st.execute(dict(skill="skill:receive-goods", asset="HYD-03", decision="DEC-GR", option="gr", by="t", params=dict(ref=pr["ref"])))
    if "B" in path:
        st.execute(b_request(st, effect))
    if path.startswith("BC"):
        c_procure(st)
    order = path.split("reset-")[-1].split("-then-") if "reset-" in path else [path[0]]
    for which in order:
        st.reset_pm_counters() if which == "B" else st.reset_spare_stock(SEAL)
    assert rows(st) == start_rows()
    assert not any(p["status"] == PO_OPEN and p.get("qty") for p in st._s["erp"]["purchase_requests"])
    assert not st._pm_holds()


def test_full_reset_is_still_class_start():
    st = EnterpriseState()
    c_procure(st)
    st.execute(b_request(st))
    st.reset()
    assert rows(st) == start_rows()


def test_c_reset_refuses_rather_than_hiding_parts_issued_to_open_b_order():
    """B가 C 입고분까지 즉시 출고해 시작값 아래로 내려가면 C [초기화]는 조용히 맞추지 않고 거절한다(아무것도 바꾸지 않음)."""
    st = EnterpriseState()
    pr = c_procure(st)
    st.execute(dict(skill="skill:receive-goods", asset="HYD-03", decision="DEC-GR", option="gr", by="t", params=dict(ref=pr["ref"])))
    st.execute(b_request(st, "issue"))
    for o in st._s["cmms"]["work_orders"]:                             # 실제 장부 대신 출고 수량만 키운다(시험 입력)
        for x in o.get("issued_parts") or []:
            if x["part_no"] == SEAL:
                x["qty"] = 5
    before = rows(st)
    with pytest.raises(ValueError, match="B \\[초기화\\] 먼저"):
        st.reset_spare_stock(SEAL)
    assert rows(st) == before


# ---------------------------------------------------------------- E4: 구매요청 취소 보상이 입고 예정을 되돌린다
def test_e4_cancel_purchase_request_returns_on_order_and_records_movement():
    st = EnterpriseState()
    pr = c_procure(st)
    tx = st.execute(dict(skill="skill:cancel-purchase-request", asset="HYD-03", decision="DEC-CX", option="x", by="buyer",
                         compensates=pr["id"], params=dict(ref=pr["ref"])))
    assert po(st, pr["ref"])["status"] == CANCELLED and stock(st)["on_order"] == 0
    view = st._stock_view(stock(st))
    assert view["available"] == 1 and view["below_reorder_point"] is True and view["need_qty"] == 6
    move = st.spare_stock(SEAL)["movements"][0]
    assert (move["kind"], move["qty"], move["ref"], move["by_whom"]) == ("CANCEL", 6, pr["ref"], "buyer") and tx["ref"] == pr["ref"]


def test_e4_cancel_refuses_when_on_order_ledger_is_short():
    st = EnterpriseState()
    pr = c_procure(st)
    stock(st)["on_order"] = 2                                          # 장부가 어긋난 상태(시험 입력)
    with pytest.raises(ValueError, match="on-order quantity"):
        st.execute(dict(skill="skill:cancel-purchase-request", asset="HYD-03", decision="DEC-CX", option="x", by="t",
                        compensates=pr["id"], params=dict(ref=pr["ref"])))
    assert po(st, pr["ref"])["status"] == PO_OPEN and stock(st)["on_order"] == 2


# ---------------------------------------------------------------- E6: 창 지정 작업지시 취소가 '이번 회차 오더' 표시를 지운다
def test_e6_cancel_work_order_clears_pm_plan_pointer():
    st = EnterpriseState()
    win = data.first_window("HYD-02", "N")
    wo = st.execute(dict(skill="skill:schedule-maintenance", asset="HYD-02", decision="DEC-A", option="o", by="t",
                         params=dict(task="펌프 점검", window_id=win["id"])))
    assert st._s["cmms"]["pm_counters"]["HYD-02"]["plan_wo"] == wo["ref"]
    st.execute(dict(skill="skill:cancel-work-order", asset="HYD-02", decision="DEC-A2", option="x", by="t",
                    compensates=wo["id"], params=dict(ref=wo["ref"])))
    counter = st._s["cmms"]["pm_counters"]["HYD-02"]
    assert (counter["plan_wo"], counter["plan_window"], counter["planned_at"]) == (None, None, None)
    row = next(r for r in st._pm_rows() if r["asset"] == "HYD-02")
    assert row["pm_planned_wo"] is None and row["pm_alert"] is True
    assert st.execute(b_request(st))["ref"].startswith("WO-")          # B [정기 점검]이 다시 오더를 등록할 수 있다


# ---------------------------------------------------------------- E7: 번호 난수 12자리
REF = re.compile(r"^(TX|WO|PR|GR|GI|RUN|PMR|SH)-\d{4}-[0-9A-F]{12}$")


def test_e7_every_generated_number_has_48_bit_suffix():
    st = EnterpriseState()
    made = []
    wo = st.execute(dict(skill="skill:schedule-maintenance", asset="HYD-01", decision="D1", option="o", by="t", params=dict(task="오더")))
    made += [wo["id"], wo["ref"]]
    pr = c_procure(st)
    made += [pr["id"], pr["ref"]]
    gr = st.execute(dict(skill="skill:receive-goods", asset="HYD-03", decision="D-GR", option="gr", by="t", params=dict(ref=pr["ref"])))
    made += [gr["id"], gr["ref"]]
    for req in (dict(skill="skill:issue-spare", asset="HYD-03", by="t", params=dict(part_no=SEAL, qty=1)),
                dict(skill="skill:pm-advance", asset="HYD-01", by="t", params=dict(hours=10)),
                dict(skill="skill:pm-reset", asset="HYD-01", by="t", params=dict()),
                dict(skill="skill:substitute-shipment", asset="HYD-01", decision="D-SH", option="o", by="t", params=dict()),
                dict(skill="skill:cancel-work-order", asset="HYD-01", decision="D-X", option="x", by="t", compensates=wo["id"], params=dict(ref=wo["ref"]))):
        tx = st.execute(req)
        made += [tx["id"]] + ([tx["ref"]] if req["skill"] != "skill:cancel-work-order" else [])
    assert all(REF.match(x) for x in made), [x for x in made if not REF.match(x)]
    assert {x.split("-")[0] for x in made} == {"TX", "WO", "PR", "GR", "GI", "RUN", "PMR", "SH"}


def test_reset_refusal_reaches_caller_as_409_with_reason(monkeypatch):
    """B · C [초기화]가 되돌릴 수 없을 때 이유 없는 500 이 아니라 거절 이유를 409 로 낸다(두 백엔드 모두 'INVALID:' 거절)."""
    from fastapi.testclient import TestClient
    from entsim import main as entmain

    def refuse(_arg):
        raise ValueError("INVALID: P-PMP-SEAL 실물 5개가 진행 중인 정비 오더에 출고돼 있어 재고를 시작값으로 되돌릴 수 없습니다(B [초기화] 먼저)")
    monkeypatch.setattr(entmain.ent, "reset_spare_stock", refuse)
    monkeypatch.setattr(entmain.ent, "reset_pm_counters", refuse)
    client = TestClient(entmain.app)
    for path, body in (("/erp/spare/reset", {"part_no": SEAL}), ("/cmms/pm/reset", {})):
        r = client.post(path, json=body)
        assert r.status_code == 409 and "B [초기화] 먼저" in r.json()["detail"]
