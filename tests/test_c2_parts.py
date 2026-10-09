"""C2 (확정 TODO C) 부품 단위 시험 — 부품 계약(effect_parts) · ERP 재고 감시(business_monitor) · 업무 시스템 메모리 백엔드(재고 · 발주 · 입고 ·
정비 완료 · 예정된 정비 시간 · 출고 버튼) · hyd-effects 쓰기 도구 · 승인 뒤 MCP 호출 클라이언트 · 대기 압축 · 시뮬레이터 부품별 복구 · 사건 종결."""
import json
import smtplib
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from procsvc import business_monitor as BM, effect_parts as P, engine, machine, mcp_check
from entsim import data, state

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 9, 3, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------- 부품 계약
def test_argument_templates_take_case_values_and_refuse_missing_ones():
    values = {"asset": "HYD-03", "approved_amount": 330, "purchase_order": {"ref": "PR-1", "after": {"lead_d": 5}}}
    out = P.render({"subject": "[발주] {asset} {approved_amount}만원", "ref": "{purchase_order.ref}", "lead": "{purchase_order.after.lead_d}",
                    "list": ["{asset}", 3], "fixed": True}, values)
    assert out == {"subject": "[발주] HYD-03 330만원", "ref": "PR-1", "lead": 5, "list": ["HYD-03", 3], "fixed": True}
    with pytest.raises(KeyError):
        P.render({"x": "{nope}"}, values)
    assert P.placeholders({"a": "{x.y} {z}", "b": ["{w}"]}) == ["x.y", "z", "w"]


def test_wait_is_compressed_on_top_of_the_time_scale_only_for_waiting_parts():
    old = engine.wait_compression()
    try:
        engine.configure_wait_compression(60)
        plan = P.wait_for({"duration": "P5D"}, {}, NOW, 20)
        assert plan["virtual_s"] == 432000 and plan["real_s"] == 360.0 and plan["compression"] == 60
        assert P.due(plan, NOW + timedelta(seconds=360)) and not P.due(plan, NOW + timedelta(seconds=359))
        until = P.wait_for({"until": "wo.after.window_starts_at"}, {"wo": {"after": {"window_starts_at": (NOW + timedelta(hours=9)).isoformat()}}}, NOW, 20)
        assert until["real_s"] == 27.0
        past = P.wait_for({"until": "t"}, {"t": (NOW - timedelta(hours=1)).isoformat()}, NOW, 20)
        assert past["real_s"] == 0
        assert engine.timer_scale({"tool": "process:wait"}, 20) == 1200 and engine.timer_scale({"tool": "formHandler:select_card"}, 20) == 20
        with pytest.raises(ValueError):
            engine.configure_wait_compression(0.5)
    finally:
        engine.configure_wait_compression(old)


@pytest.mark.parametrize("activity,phrase", [
    ({"tool": "mcp:call", "service": {"server": "hyd-effects", "tool": "send_mail"}, "outputData": ["x"]}, "outputData"),
    ({"tool": "mcp:call", "service": {"server": "hyd-effects", "tool": "send mail"}, "outputData": ["mcp_receipt"]}, "도구 이름"),
    ({"tool": "mcp:call", "service": {"server": "hyd-effects", "tool": "t", "arguments": {"a": "{1bad}"}}, "outputData": ["mcp_receipt"]}, None),
    ({"tool": "process:wait", "service": {"duration": "PT1H", "until": "x"}, "outputData": ["waited"]}, "하나를"),
    ({"tool": "enterprise:GR_CONFIRM", "service": {}, "outputData": ["goods_receipt"]}, "outputData"),
])
def test_part_validation_reasons(activity, phrase):
    activity = dict(activity, id="T")
    if phrase is None:
        P.validate(activity)            # {1bad} 는 자리표시가 아니라 글자 — 그대로 보낸다
        return
    with pytest.raises(ValueError, match=phrase):
        P.validate(activity)


def test_purchase_quote_is_fixed_from_the_approved_card_and_the_erp_quote():
    quotes = [{"supplier": "sup:b", "name": "B-OEM", "price": 55, "lead_d": 5, "avl": True}]
    option = {"actions": [{"code": "PR_CREATE", "value": "sup:b"}]}
    alert = {"evidence": {"part_no": "P-PMP-SEAL", "need_qty": 6}}
    q = P.purchase_quote(option, {"alert": alert}, quotes)
    assert (q["approved_amount"], q["approved_qty"], q["approved_part_no"]) == (330, 6, "P-PMP-SEAL")
    assert P.purchase_quote(option, {"alert": alert, "need_qty": 2}, quotes)["approved_amount"] == 110      # 에이전트 산정이 먼저
    assert P.purchase_quote({"actions": [{"code": "WO_CREATE"}]}, {}, quotes) is None                    # 발주가 없는 카드
    with pytest.raises(ValueError, match="수량"):
        P.purchase_quote(option, {"alert": {"evidence": {"part_no": "P-PMP-SEAL"}}}, quotes)
    with pytest.raises(ValueError, match="견적"):
        P.purchase_quote({"actions": [{"code": "PR_CREATE", "value": "sup:z"}]}, {"alert": alert}, quotes)


# ---------------------------------------------------------------- ERP 재고 감시
ROW = {"part_no": "P-PMP-SEAL", "available": 1, "reorder_point": 2, "need_qty": 6, "below_reorder_point": True,
       "below_since": "2026-10-09T02:59:00+00:00", "reserved_for": "HYD-03"}


def test_monitor_raises_one_alert_per_episode_in_the_sensor_alert_contract():
    seen = set()
    read = lambda name, params: {"records": [ROW, dict(ROW, part_no="P-FAN-BRG", below_reorder_point=False, below_since=None)]}
    alerts = BM.scan_once(read, seen, now=NOW)
    assert len(alerts) == 1
    a = alerts[0]
    assert a["alertId"] == "ERP-SPARE_BELOW_MIN-P-PMP-SEAL-20261009025900" and a["state"] == "RAISE" and a["asset"] == "HYD-03"
    assert a["source"] == "erp" and a["evidence"]["need_qty"] == 6 and a["evidence"]["part_no"] == "P-PMP-SEAL"
    seen.add(a["alertId"])
    assert BM.scan_once(read, seen, now=NOW) == []                                            # 같은 회차는 다시 내지 않음
    later = lambda n, p: {"records": [dict(ROW, below_since="2026-10-10T01:00:00+00:00")]}
    assert BM.scan_once(later, seen, now=NOW)[0]["alertId"].endswith("20261010010000")      # 회복 뒤 다시 이탈 = 새 처리 건
    assert BM.build_alert(BM.RULES[0], dict(ROW, reserved_for="HYD-99")) is None
    assert BM.is_business_alert(a) and not BM.is_business_alert(dict(a, source="human_input"))


def test_pm_due_monitor_opens_one_case_per_maintenance_cycle_from_the_class_button():
    """시나리오 B: 수업 시작 상태가 곧 HYD-02 1,950 h(PM_DUE, C3 B · C 단순화) — HYD-03 1,880 h 는 허용 오차 안 묶음 후보. 같은 회차는 한 번,
    계수기 리셋(정비 완료) 뒤에는 다음 회차가 될 때까지 경보 없음. 같은 감시 루프 · 같은 경보 계약(재고 규칙과 공용). 감시는 기본 꺼짐 — 포털
    [정기 점검] 버튼(scenario_buttons)이 같은 계약의 경보를 낸다."""
    st = state.EnterpriseState()
    read = lambda name, params: {"spare_stock": st.spare_stock, "pm_status": st.pm_status}[name]()
    seen: set[str] = set()
    alerts = [a for a in BM.scan_once(read, seen, now=NOW) if a["pattern"] == "PM_DUE"]
    assert [a["alertId"] for a in alerts] == ["CMMS-PM_DUE-HYD-02-C1"]
    a = alerts[0]
    assert (a["source"], a["pattern"], a["asset"], a["severity"], a["state"]) == ("cmms", "PM_DUE", "HYD-02", "info", "RAISE")
    ev = a["evidence"]
    assert (ev["pm_since_h"], ev["pm_interval_h"], ev["pm_limit_in_h"], ev["bundle_peer"], ev["bundle_peer_since_h"]) == (1950, 2000, 250, "HYD-03", 1880)
    assert ev["night_within_limit"] is True and ev["monthly_within_limit"] is False and ev["bundle_crew_ok"] is False
    assert ev["spare_gap_after_pm"] == -2 and ev["spare_gap_after_bundle"] == -3        # 씰 키트가 이미 재주문점 아래 (C 와 이어짐)
    assert BM.is_business_alert(a) and not BM.is_business_alert(dict(a, source="erp"))
    seen.update(x["alertId"] for x in BM.scan_once(read, set(), now=NOW))
    assert BM.scan_once(read, seen, now=NOW) == []                                            # 같은 회차 = 같은 처리 건
    st.execute({"skill": "skill:pm-reset", "decision": "D-PM", "asset": "HYD-02", "params": {"ref": "WO-1"}})
    f = st.pm_status("HYD-02")["facts"]
    assert (f["pm_since_h"], f["cycle"], f["pm_due"], f["due_since"], f["pm_alert"]) == (0, 2, False, None, False) and f["last_done_at"]
    assert BM.scan_once(read, seen, now=NOW) == []
    st.execute({"skill": "skill:pm-advance", "decision": "cls-2", "asset": "HYD-03", "params": {"hours": 100}})
    assert [x["alertId"] for x in BM.scan_once(read, seen, now=NOW)] == ["CMMS-PM_DUE-HYD-03-C1"]
    assert {"SPARE_BELOW_MIN", "PM_DUE"} <= set(BM.policy_patterns())


def test_pm_alert_turns_off_when_this_cycles_work_order_is_registered_and_reset_brings_it_back():
    """C3 B · C 단순화: '정기 점검 도래' 표시(pm_alert) = 도래 · 이번 회차 오더 없음. 도래 설비의 작업지시가 이번 회차 오더가 되고(먼저 등록된 것),
    도래가 아닌 설비의 작업지시는 표시와 무관하다. 수업 초기화가 오더 표시를 지워 표시가 다시 켜진다(마이그레이션 47과 같은 규칙)."""
    st = state.EnterpriseState()
    f = st.pm_status("HYD-02")["facts"]
    assert (f["pm_due"], f["pm_alert"], f["pm_planned_wo"], bool(f["due_since"])) == (True, True, None, True)
    other = st.execute({"decision": "D-A", "skill": "skill:schedule-maintenance", "asset": "HYD-01", "params": {"task": "쿨러 핀 세척"}})
    assert st.pm_status("HYD-01")["facts"]["pm_planned_wo"] is None and other["ref"].startswith("WO")
    wo = st.execute({"decision": "D-B", "skill": "skill:schedule-maintenance", "asset": "HYD-02", "params": {"task": "정기 점검"}})
    st.execute({"decision": "D-B2", "skill": "skill:schedule-maintenance", "asset": "HYD-02", "params": {"task": "두 번째"}})
    f = st.pm_status("HYD-02")["facts"]
    assert (f["pm_due"], f["pm_alert"], f["pm_planned_wo"]) == (True, False, wo["ref"]) and f["pm_planned_window"] == "즉시"
    f = st.reset_pm_counters()["records"][1]
    assert (f["asset"], f["pm_since_h"], f["pm_alert"], f["pm_planned_wo"]) == ("HYD-02", 1950, True, None)


def test_one_business_system_down_does_not_stop_the_other_rule():
    def read(name, params):
        if name == "pm_status":
            raise OSError("CMMS down")
        return {"records": [ROW]}
    assert [a["pattern"] for a in BM.scan_once(read, set(), now=NOW)] == ["SPARE_BELOW_MIN"]
    with pytest.raises(RuntimeError, match="CMMS down"):
        BM.scan_once(lambda n, p: (_ for _ in ()).throw(OSError("CMMS down")), set(), now=NOW)


def test_pm_counter_and_delivery_delay_class_buttons_over_http():
    """enterprise-sim 의 수업 API(포털 버튼은 C3 부터 [정기 점검] · [초기화]만 — 계수기 진행 · 납기 지연 API 는 시험 · 강사용으로 남김)."""
    from fastapi.testclient import TestClient
    from entsim import main as entmain
    entmain.ent.st.reset()
    client = TestClient(entmain.app)
    f = client.get("/cmms/pm_status", params={"asset": "HYD-02"}).json()["facts"]
    assert (f["pm_since_h"], f["pm_due"], f["pm_alert"]) == (1950, True, True)              # 수업 시작 상태 = 정기 점검 도래
    r = client.post("/cmms/pm/advance", json={"hours": 300, "asset": "HYD-01"})
    assert r.status_code == 200 and len(r.json()["transactions"]) == 1
    rows = {x["asset"]: x for x in r.json()["pm"]["records"]}
    assert (rows["HYD-01"]["pm_since_h"], rows["HYD-03"]["pm_due"], rows["HYD-03"]["pm_window_open"]) == (1800, False, True)
    assert client.post("/cmms/pm/advance", json={"hours": -5, "asset": "HYD-01"}).status_code == 400
    assert [x["pm_since_h"] for x in client.post("/cmms/pm/reset", json={}).json()["records"]] == [1500, 1950, 1880]
    assert client.post("/erp/purchase_orders/delay", json={"days": 3}).status_code == 400          # 열린 발주가 없으면 거절
    entmain.ent.st.execute({"decision": "D-C", "skill": "skill:procure-part", "asset": "HYD-03",
                            "params": {"supplier": "sup:b", "part_no": "P-PMP-SEAL", "qty": 6, "amount": 330}})
    d = client.post("/erp/purchase_orders/delay", json={"days": 3}).json()["transaction"]
    po = client.get(f"/erp/purchase_orders/{d['ref']}").json()["facts"]
    assert po["delay_d"] == 3 and po["lead_d"] == 5 and po["expected_in_h"] > 7 * 24 - 1
    entmain.ent.st.reset()


# ---------------------------------------------------------------- 업무 시스템 (메모리 백엔드 = Supabase 와 같은 규칙)
def test_stock_issue_order_receipt_and_consumption_move_the_spare_stock():
    st = state.EnterpriseState()
    f = st.spare_stock("P-PMP-SEAL")["facts"]
    # C3 B · C 단순화: 수업 시작 상태가 곧 '재고 보충 필요'(실물 3 − 예약 2 = 가용 1 < 재주문점 2), 필요량 6
    assert (f["available"], f["reorder_point"], f["below_reorder_point"], f["spare_gap"], f["need_qty"]) == (1, 2, True, -1, 6) and f["below_since"]
    for bad, phrase in (({"supplier": "sup:c", "part_no": "P-PMP-SEAL", "qty": 6}, "AVL"),
                        ({"supplier": "sup:b", "part_no": "P-PMP-SEAL", "qty": 6, "amount": 300}, "amount"),
                        ({"supplier": "sup:b", "part_no": "P-PMP-SEAL", "qty": 0}, "quantity")):
        with pytest.raises(ValueError, match=phrase):
            st.execute({"decision": f"D-{phrase}", "skill": "skill:procure-part", "asset": "HYD-03", "params": bad})
    po = st.execute({"decision": "D-C", "skill": "skill:procure-part", "asset": "HYD-03", "by": "buyer",
                     "params": {"supplier": "sup:b", "part_no": "P-PMP-SEAL", "qty": 6, "amount": 330}})
    pr = st.purchase_order(po["ref"])["facts"]
    assert (pr["qty"], pr["unit_price"], pr["amount"], pr["lead_d"]) == (6, 55, 330, 5) and po["after"]["amount"] == 330
    f = st.spare_stock("P-PMP-SEAL")["facts"]
    assert (f["on_order"], f["available"], f["below_reorder_point"]) == (6, 7, False)    # 가용 = 실물 − 예약 + 입고 예정 (PR-07 7.2)
    gr = st.execute({"decision": "D-C", "skill": "skill:receive-goods", "asset": "HYD-03", "by": "process", "params": {"ref": po["ref"]}})
    f = st.spare_stock("P-PMP-SEAL")["facts"]
    assert gr["ref"].startswith("GR-") and (f["on_hand"], f["on_order"], f["below_reorder_point"], f["below_since"]) == (9, 0, False, None)
    assert st.purchase_order(po["ref"])["facts"]["status"] == state.PO_RECEIVED and st.purchase_order(po["ref"])["records"][0]["qty"] == 6
    with pytest.raises(ValueError, match="cannot be received"):
        st.execute({"decision": "D-C2", "skill": "skill:receive-goods", "asset": "HYD-03", "params": {"ref": po["ref"]}})
    assert st.execute({"decision": "D-C", "skill": "skill:receive-goods", "asset": "HYD-03", "by": "process",
                       "params": {"ref": po["ref"]}})["ref"] == gr["ref"]                     # 같은 승인의 재시도는 같은 입고
    wo = st.execute({"decision": "D-B", "skill": "skill:schedule-maintenance", "asset": "HYD-02", "params": {"task": "SOP-PMP-04 씰 교체"}})
    done = st.execute({"decision": "D-B", "skill": "skill:complete-maintenance", "asset": "HYD-02", "params": {"ref": wo["ref"], "sop": "SOP-PMP-04"}})
    assert "1개 소모" in done["detail"] and st.spare_stock("P-PMP-SEAL")["facts"]["on_hand"] == 8
    issue = st.execute({"skill": "skill:issue-spare", "asset": "HYD-03", "by": "강사", "params": {"part_no": "P-PMP-SEAL", "qty": 2}})
    assert issue["ref"].startswith("GI-") and st.spare_stock("P-PMP-SEAL")["facts"]["available"] == 4
    kinds = [m["kind"] for m in st.spare_stock("P-PMP-SEAL")["movements"]]
    assert kinds == ["ISSUE", "CONSUME", "RECEIPT", "ORDER"]
    reset = st.reset_spare_stock()
    seal = reset["records"][2]
    assert (seal["available"], seal["below_reorder_point"], bool(seal["below_since"])) == (1, True, True) and reset["movements"][0]["kind"] == "RESET"


def test_work_order_takes_the_approved_maintenance_window(monkeypatch):
    monkeypatch.setattr(data, "_SCENARIO_START", NOW)
    monkeypatch.setattr(data, "_now", lambda: NOW)
    windows = data.maintenance_windows("HYD-02")
    first = windows["records"][0]
    assert first["kind"] == "N" and first["starts_in_h"] == 9.0 and windows["facts"]["next_window_id"] == first["id"]
    st = state.EnterpriseState()
    wo = st.execute({"decision": "D-W", "skill": "skill:schedule-maintenance", "asset": "HYD-02", "params": {"task": "t", "window_id": first["id"]}})
    assert wo["after"]["window_id"] == first["id"] and wo["after"]["window_starts_at"] == first["starts_at"]
    assert "야간 정비 시간" in wo["after"]["window"] and "정비창" not in wo["after"]["window"]
    with pytest.raises(ValueError, match="unknown maintenance window"):
        st.execute({"decision": "D-W2", "skill": "skill:schedule-maintenance", "asset": "HYD-01", "params": {"window_id": first["id"]}})
    assert data.part_quotes("P-PMP-SEAL")["records"][1] == {"supplier": "sup:b", "name": "B-OEM (순정)", "price": 55, "fail_rate": 0.02,
                                                              "lead_d": 5, "avl": True}
    assert [q["supplier"] for q in data.part_quotes("P-CLR-CORE")["records"]] == ["sup:a", "sup:b", "sup:c"]


def test_spare_issue_button_and_reset_over_http(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from entsim import main as entmain
    entmain.ent.st.reset()
    client = TestClient(entmain.app)
    assert client.get("/erp/spare_stock", params={"part": "P-PMP-SEAL"}).json()["facts"]["available"] == 1   # 시작 상태 = 재고 보충 필요
    r = client.post("/erp/spare/issue", json={"qty": 1, "reason": "타 라인 긴급 사용"})   # 강사 · 시험용 API (포털 버튼에서는 뺐다)
    assert r.status_code == 200 and r.json()["stock"]["facts"]["available"] == 0
    assert r.json()["transaction"]["skill"] == "skill:issue-spare"
    assert client.post("/erp/spare/issue", json={"part_no": "P-PMP-SEAL", "qty": 99}).status_code == 400
    assert client.post("/erp/spare/reset", json={}).json()["records"][2]["available"] == 1
    assert client.get("/scm/quotes", params={"part": "P-PMP-SEAL"}).status_code == 200
    assert client.get("/cmms/windows", params={"asset": "HYD-02"}).json()["system"] == "CMMS"
    assert client.get("/erp/purchase_orders/PR-none").status_code == 404
    entmain.ent.st.reset()


# ---------------------------------------------------------------- hyd-effects 쓰기 도구
class FakeSmtp:
    sent = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def send_message(self, msg):
        FakeSmtp.sent.append(msg)


def test_send_mail_is_idempotent_per_key_and_checks_addresses(tmp_path):
    from effects_mcp.tools import EffectTools, Ledger
    FakeSmtp.sent = []
    tools = EffectTools(Ledger(str(tmp_path / "e.sqlite3")), smtp_factory=FakeSmtp)
    first = tools.send_mail("supplier@hyd.local, receiving@hyd.local", "[발주] 씰 키트 6개", "본문", idempotency_key="inst:task")
    assert first["result"] == "ok" and first["document"]["to"] == ["supplier@hyd.local", "receiving@hyd.local"] and not first["document"]["replayed"]
    again = EffectTools(Ledger(str(tmp_path / "e.sqlite3")), smtp_factory=FakeSmtp).send_mail("x@y.z", "다른", "b", idempotency_key="inst:task")
    assert again["document"]["replayed"] is True and again["document"]["message_id"] == first["document"]["message_id"]
    assert len(FakeSmtp.sent) == 1 and FakeSmtp.sent[0]["X-HYD-Idempotency-Key"] == "inst:task"
    assert tools.send_mail("no-at-sign", "s", "b")["error_kind"] == "INVALID"
    boom = EffectTools(Ledger(None), smtp_factory=lambda: (_ for _ in ()).throw(smtplib.SMTPConnectError(421, b"down")))
    assert boom.send_mail("a@b.c", "s", "b", idempotency_key="k2")["error_kind"] == "UNKNOWN"


def test_effects_server_marks_every_tool_as_write():
    import re
    src = (ROOT / "it/effects-mcp/effects_mcp/server.py").read_text(encoding="utf-8")
    marks = re.findall(r"@mcp\.tool\(annotations=(\w+)\)\ndef (\w+)", src)
    assert marks == [("WRITE", "send_mail")]          # 메일만 — 업무 쓰기는 기존 enterprise-sim 거래를 process 가 직접 쓴다
    assert '"readOnlyHint": False' in src


# ---------------------------------------------------------------- 승인 뒤 MCP 호출 클라이언트 (쓰기 도구도 부른다 — 포털 써 보기와 다른 길)
def test_call_effect_reaches_a_write_tool_that_the_portal_refuses():
    sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
    spec = mcp_check.normalize({"command": sys.executable, "args": [str(ROOT / "tests" / "fixtures" / "mcp_fake_server.py")]})
    refused = mcp_check.call(spec, "submit_note", {"text": "x"}, timeout=10)
    assert refused["status"] == "refused"
    out = mcp_check.call_effect(spec, "submit_note", {"text": "x"}, idempotency_key="i:t", timeout=10)
    assert out["status"] == "ok" and "submit_note" in out["result"]["text"] and out["idempotent"] is False   # 이 도구는 키를 받지 않는다
    assert mcp_check.call_effect(spec, "no_such", {}, timeout=10)["status"] == "refused"


# ---------------------------------------------------------------- 설비 시뮬레이터 · 사건
def test_plant_restore_can_target_one_component():
    from plantsim.plant import Plant
    plant = Plant(time_scale=1, assets=["T-1"])
    u = plant.units["T-1"]
    u.state.leak, u.state.cooler_health = 0.15, 0.4
    out = plant.inject("T-1", "restore", component="pump")
    assert out["targets"] == {"leak": 0.0}
    assert plant.inject("T-1", "restore")["targets"] == {"cooler_health": 1.0, "leak": 0.0}
    with pytest.raises(ValueError, match="unknown component"):
        plant.inject("T-1", "restore", component="boiler")


def test_business_effect_closes_only_an_open_incident_without_a_command():
    class Fx(machine.Effects):
        def emit_audit(self, e):
            pass
    inc = machine.Incident.from_card("INC-1", {"alert": {"alertId": "A", "asset": "HYD-03", "pattern": "SPARE_BELOW_MIN"}},
                                     recovery_policy={"pattern": "SPARE_BELOW_MIN", "criterion": ["ERP_SPARE_BELOW_MIN", "<", 1.0]})
    machine.on_card(inc)
    with pytest.raises(ValueError, match="영수증"):
        machine.on_business_effect(inc, {"ok": True, "ref": ""}, Fx())
    assert machine.on_business_effect(inc, {"ok": True, "ref": "GR-1", "kind": "goods_receipt"}, Fx()) is True
    assert inc.state == "CLOSED" and "GR-1" in inc.history[-1]["note"]
    assert machine.on_business_effect(inc, {"ok": True, "ref": "GR-1"}, Fx()) is False


def test_cmms_window_parameters_from_the_approved_value():
    from procsvc.main import _window_params
    opt = {"id": "skill:wo-x"}
    assert _window_params("MW-HYD-02-N-202610091400", opt) == {"window_id": "MW-HYD-02-N-202610091400"}
    assert _window_params({"id": "MW-1", "label": "야간"}, opt) == {"window_id": "MW-1", "window": "야간"}
    assert _window_params({"label": "주말", "starts_at": "2026-10-10T00:00:00Z"}, opt) == {"window": "주말", "window_starts_at": "2026-10-10T00:00:00Z"}
    assert _window_params("다음 주 화요일 야간", opt) == {"window": "다음 주 화요일 야간"}
    assert _window_params(None, {"id": "skill:night-clean"}) == {"window": "예정된 정비 시간 (야간)"}


def test_c2_transactions_are_listed_as_irreversible_with_the_same_reason():
    from procsvc import effect_compensation as ec
    assert ec.C2_IRREVERSIBLE == state.C2_IRREVERSIBLE and set(state.C2_IRREVERSIBLE) == set(state.C2_SKILLS)
    assert not set(state.C2_SKILLS) & set(state.INVERSE_OF)
