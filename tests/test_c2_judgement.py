"""C2 → 판단 엔진: B 정기 정비 · C 예비품 구매도 A 와 같은 경로(gather_facts → candidates → compliance → BSC 득실 → rank-actions)로
경쟁하는 대안을 비교한다. 이 파일은 C2 쪽 책임 — '사실이 업무 DB 에서 온톨로지 변수 이름 그대로 온다' — 을 본다.

  * 업무 시스템은 실제 enterprise-sim(메모리 백엔드 = Supabase 와 같은 규칙)을 HTTP 로 부른다(TestClient).
  * 규칙은 C1 문서(PM-02 · PR-07)가 적재하는 것과 같은 변수 · 임계값을 쓴다(c1_fixtures 의 규칙을 줄여 옮김 — 지식 소유는 C1).
  * 정비 · 구매 카드에는 설비 명령이 없어도 지금 운전점 예측(sv:ts1)이 붙는다 — 인터록 규칙(rule:ts1-hard)이 '모름'으로 카드를 지우지 않게.
"""
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from agentsvc import cards, decide, forecasting
from agentsvc.tools import mcp_ent
from entsim import main as entmain
from plantsim import thermal
from test_forecast_model import snapshot
from test_forecast_source import kg

RANK = {"version": 1, "inputs": {}, "components": {"bsc": "bsc_gain - bsc_loss", "warn": "-0.5 * warning_count",
                                                   "penalty": "-penalty_total / 20"}, "tieBreak": "lower_approver"}


def rule(rid, decision, effect, tests, applies=(), outputs=(), penalty=None, ord_=10):
    return {"decision": decision, "rule": rid, "ord": ord_, "effect": effect, "penalty": penalty, "annotation": rid, "sources": [],
            "tests": [{"variable": v, "operator": op, "value": val} for v, op, val in tests], "applies": list(applies),
            "outputs": list(outputs), "penalizes": [], "when": None}


def base_rules():
    return [{"decision": "dec:rank-actions", "rule": "rule:rank-value", "ord": 1, "effect": "RANK", "tests": [], "outputs": [], "applies": [],
             "penalizes": [], "sources": [], "rankingPolicy": RANK},
            rule("rule:ts1-hard", "dec:compliance", "EXCLUDE", [("forecast_ts1", ">=", 65)])]


def skill(sid, sop, actions, addresses=()):
    return {"skillId": sid, "sopId": sop, "name": sop, "kind": "work_order", "relation": "PREVENTED_BY",
            "approver": {"id": "role:maint-mgr", "level": 2}, "addresses": list(addresses), "actions": actions}


def trade(sid, measure, direction, sign):
    """t3_tradeoffs 한 줄(스킬 -AFFECTS-> 성과 지표). sign '+' = 지표 값이 오른다."""
    return {"skill": sid, "measure": measure, "name": measure, "direction": direction, "owners": [], "nodes": [sid, measure], "conds": [],
            "edges": [{"key": f"{sid}>{measure}", "type": "AFFECTS", "source": sid, "target": measure, "sign": 1 if sign == "+" else -1}]}


def inputs(*rows):
    return [{"variable": v, "name": v, "source": src, "sourceName": src, "sourceKind": "System", "representsName": None} for v, src in rows]


@pytest.fixture
def enterprise(monkeypatch):
    """에이전트의 mcp_ent.fetch 가 실제 enterprise-sim 앱을 부른다(업무 DB 메모리 백엔드)."""
    entmain.ent.st.reset()
    client = TestClient(entmain.app)

    def fetch(endpoint, asset, timeout=5.0):
        r = client.get(endpoint.replace("{asset}", asset))
        assert r.status_code == 200, (endpoint, r.text)
        return r.json()
    monkeypatch.setattr(mcp_ent, "fetch", fetch)
    yield client
    entmain.ent.st.reset()


def current_forecasts(monkeypatch, skills):
    monkeypatch.setattr(decide, "_get_json", lambda url: snapshot(thermal.UnitState()))
    return forecasting.candidates(kg(), "TEST-ASSET", skills)


# ================================================================ B 정기 정비
B_SKILLS = {"skill:pm-11": skill("skill:pm-11", "SOP-PM-11", [{"code": "WO_CREATE", "kind": "transaction", "value": "SOP-PM-21"}]),
            "skill:pm-12": skill("skill:pm-12", "SOP-PM-12", [{"code": "WO_CREATE", "kind": "transaction", "value": "SOP-PM-21"}]),
            "skill:pm-13": skill("skill:pm-13", "SOP-PM-13", [{"code": "WO_CREATE", "kind": "transaction", "value": "SOP-PM-21"}]),
            "skill:pm-14": skill("skill:pm-14", "SOP-PM-14", [{"code": "WO_CREATE", "kind": "transaction", "value": "SOP-PM-21"}])}
B_NOW = ["skill:pm-11", "skill:pm-12", "skill:pm-14"]
B_TRADE = [trade("skill:pm-11", "msr:mtbf", "UP", "+"), trade("skill:pm-12", "msr:mtbf", "UP", "+"),
           trade("skill:pm-12", "msr:availability", "UP", "-"), trade("skill:pm-13", "msr:availability", "UP", "+"),
           trade("skill:pm-13", "msr:mtbf", "UP", "-"), trade("skill:pm-14", "msr:mtbf", "UP", "+"),
           trade("skill:pm-14", "msr:availability", "UP", "+")]


def b_rules():
    return base_rules() + [
        rule("rule:cand-pm-due", "dec:action-candidates", "SELECT", [("pattern", "==", "PM_DUE"), ("hours_since_pm", ">=", 1800)],
             outputs=list(B_SKILLS)),
        rule("rule:pm-window-limit", "dec:compliance", "EXCLUDE", [("hours_at_next_window", ">", 2200)], ["skill:pm-11", "skill:pm-14"]),
        rule("rule:pm-defer-limit", "dec:compliance", "EXCLUDE", [("hours_at_following_window", ">", 2200)], ["skill:pm-13"]),
        rule("rule:pm-stop-order", "dec:compliance", "PENALTY", [("order_due_h", "<", 24)], ["skill:pm-12"], penalty=80),
        rule("rule:pm-bundle-crew", "dec:compliance", "PENALTY", [("pm_crew_available", "<", 4)], ["skill:pm-14"], penalty=60),
        rule("rule:pm-spare-none", "dec:compliance", "EXCLUDE", [("spare_available", "<", 1)], B_NOW),
        rule("rule:pm-bundle-spare", "dec:compliance", "EXCLUDE", [("spare_available", "<", 2)], ["skill:pm-14"])]


B_INPUTS = inputs(("hours_since_pm", "sys:cmms"), ("hours_at_next_window", "sys:cmms"), ("hours_at_following_window", "sys:cmms"),
                  ("pm_crew_available", "sys:cmms"), ("spare_available", "sys:cmms"), ("order_due_h", "sys:mes"))


def b_judge(monkeypatch):
    facts, prov = decide.gather_facts(B_INPUTS, "HYD-02", {"pattern": "PM_DUE", "cause": None, "failure_mode": None}, tsdb=None)
    assert not any(p.get("error") for p in prov), prov
    forecasts, contexts = current_forecasts(monkeypatch, B_SKILLS)
    return facts, cards.evaluate(b_rules(), deepcopy(B_SKILLS), facts, forecasts, B_TRADE, [], {}, contexts)


def test_b_facts_come_from_the_cmms_counter_with_the_ontology_variable_names(enterprise, monkeypatch):
    # C3 B · C 단순화: 수업 시작 상태가 곧 HYD-02 1,950 h(정기 점검 도래) · 씰 키트 가용 1(재고 보충 필요) — 버튼 없이 시작값
    facts, result = b_judge(monkeypatch)
    assert (facts["hours_since_pm"], facts["hours_at_next_window"], facts["hours_at_following_window"]) == pytest.approx((1950, 1959, 2230), abs=0.5)
    assert (facts["pm_crew_available"], facts["spare_available"]) == (2, 1) and 19 < facts["order_due_h"] <= 20
    o = {x["sopId"]: x for x in result["options"]}
    assert result["recommended"] == "skill:pm-11"                                  # 이번 예정된 정비 시간에 단독
    assert not o["SOP-PM-13"]["feasible"] and o["SOP-PM-13"]["violations"][0]["rule"] == "rule:pm-defer-limit"   # 미루면 2,230 h > 2,200 h
    assert [p["rule"] for p in o["SOP-PM-12"]["penalties"]] == ["rule:pm-stop-order"]                         # 지금 정지 → 오더 손실
    assert [p["rule"] for p in o["SOP-PM-14"]["penalties"]] == ["rule:pm-bundle-crew"]                        # 두 대 묶기 → 인원 2명 < 4
    assert not o["SOP-PM-14"]["feasible"] and [v["rule"] for v in o["SOP-PM-14"]["violations"]] == ["rule:pm-bundle-spare"]  # 키트 1 < 2 (C 와 이어짐)
    assert all(any(f["variable"] == "sv:ts1" for f in x["forecast"]) for x in result["options"])              # 명령 없는 카드도 지금 운전점 예측


def test_b_without_seal_kits_no_card_is_feasible(enterprise, monkeypatch):
    enterprise.post("/api/exec", json={"skill": "skill:issue-spare", "decision": "GI-1", "asset": "HYD-03",
                                       "params": {"part_no": "P-PMP-SEAL", "qty": 1}})             # 가용 1 → 0
    facts, result = b_judge(monkeypatch)
    assert facts["spare_available"] == 0 and result["recommended"] is None        # 지금 하는 안은 부품 없음, 미루기는 허용 오차 밖


# ================================================================ C 예비품 구매
def pur(sid, sop, sup):
    return skill(sid, sop, [{"code": "PR_CREATE", "kind": "transaction", "value": sup, "target": "sys:erp"}], ["cause:pump-seal-wear"])


C_SKILLS = {"skill:pur-11": pur("skill:pur-11", "SOP-PUR-11", "sup:b"), "skill:pur-12": pur("skill:pur-12", "SOP-PUR-12", "sup:a"),
            "skill:pur-13": pur("skill:pur-13", "SOP-PUR-13", "sup:c")}
C_TRADE = [trade("skill:pur-11", "msr:part-cost", "DOWN", "+"), trade("skill:pur-11", "msr:part-quality", "UP", "+"),
           trade("skill:pur-12", "msr:part-cost", "DOWN", "-"), trade("skill:pur-12", "msr:part-quality", "UP", "-"),
           trade("skill:pur-13", "msr:part-cost", "DOWN", "-"), trade("skill:pur-13", "msr:part-quality", "UP", "-")]
SUPPLIERS = {"sup:a": {"avl": True}, "sup:b": {"avl": True}, "sup:c": {"avl": False}}


def c_rules():
    return base_rules() + [
        rule("rule:cand-spare-purchase", "dec:action-candidates", "SELECT", [("pattern", "==", "SPARE_BELOW_MIN"), ("spare_gap", "<", 0)],
             outputs=list(C_SKILLS)),
        rule("rule:pur-avl", "dec:compliance", "EXCLUDE", [("supplier_avl", "==", False)], list(C_SKILLS)),
        rule("rule:pur-amount", "dec:compliance", "WARN", [("po_amount", ">", 300)], list(C_SKILLS)),
        rule("rule:pur-lead", "dec:compliance", "WARN", [("lead_slack_days", "<", 0)], list(C_SKILLS)),
        # PR-7.4 "불량률이 10 %를 넘는 승인 공급사에 발주할 때는 … 전수 검사 비용 20만 원을 더해 비교한다"(입력 in:supplier-fail-rate)
        rule("rule:pur-inspection", "dec:compliance", "PENALTY", [("supplier_fail_rate", ">", 0.1)], list(C_SKILLS), penalty=20)]


C_INPUTS = inputs(("spare_gap", "sys:erp"), ("po_amount", "sys:agent"), ("lead_slack_days", "sys:agent"), ("supplier_fail_rate", "sys:scm"))


def c_judge(monkeypatch):
    known = {"pattern": "SPARE_BELOW_MIN", "cause": "cause:pump-seal-wear", "failure_mode": "fm:volumetric-loss"}
    facts, prov = decide.gather_facts(C_INPUTS, "HYD-03", known, tsdb=None)
    assert not any(p.get("error") for p in prov), prov
    forecasts, contexts = current_forecasts(monkeypatch, C_SKILLS)
    return facts, cards.evaluate(c_rules(), deepcopy(C_SKILLS), facts, forecasts, C_TRADE, [], SUPPLIERS, contexts)


def test_c_amount_and_lead_slack_are_computed_per_card_from_erp_need_and_scm_quotes(enterprise, monkeypatch):
    facts, result = c_judge(monkeypatch)                                         # 수업 시작 상태: 가용 1 < 재주문점 2
    assert (facts["spare_gap"], facts["need_qty"], facts["need_by_days"], facts["spare_part_no"]) == (-1, 6, 6, "P-PMP-SEAL")
    o = {x["sopId"]: x for x in result["options"]}
    b, a, c = o["SOP-PUR-11"], o["SOP-PUR-12"], o["SOP-PUR-13"]
    assert (b["facts"]["po_amount"], a["facts"]["po_amount"], c["facts"]["po_amount"]) == (330, 210, 120)
    assert (b["facts"]["lead_slack_days"], a["facts"]["lead_slack_days"]) == (1, 4)
    assert not c["feasible"] and c["violations"][0]["rule"] == "rule:pur-avl"                 # 가장 싸지만 비승인 → 제외
    assert [w["rule"] for w in b["warnings"]] == ["rule:pur-amount"]                       # 300만 원 초과 — 표시만(2차 승인 없음)
    assert (a["facts"]["supplier_fail_rate"], b["facts"]["supplier_fail_rate"]) == (0.12, 0.02)    # SCM 견적 그대로
    assert [p["rule"] for p in a["penalties"]] == ["rule:pur-inspection"] and not b["penalties"]   # 싸지만 불량 12 % → 전수 검사 감점
    assert "expected_defect_cost" not in a["facts"]           # PR-7.4와 다른 식으로 계산되던, 어떤 지식도 시험할 수 없던 사실은 없다
    assert result["recommended"] == "skill:pur-11"


def test_c_defect_penalty_follows_the_supplier_not_the_sop_number(enterprise, monkeypatch):
    """라이브 4차: 추출이 SOP-PUR-13(최단 납기)을 A정밀에 연결했다. 불량 감점은 SOP 번호가 아니라 카드가 고른 공급사의 견적 불량률을 본다 —
    어느 SOP가 A정밀을 가리켜도 같은 감점이 붙고, 비승인 C트레이딩을 가리키면 AVL 규정이 제외한다."""
    monkeypatch.setitem(C_SKILLS, "skill:pur-13", pur("skill:pur-13", "SOP-PUR-13", "sup:a"))
    _, result = c_judge(monkeypatch)
    o = {x["sopId"]: x for x in result["options"]}
    assert o["SOP-PUR-13"]["feasible"] and o["SOP-PUR-13"]["facts"]["supplier_fail_rate"] == 0.12
    assert [p["rule"] for p in o["SOP-PUR-13"]["penalties"]] == ["rule:pur-inspection"]
    assert not o["SOP-PUR-11"]["penalties"]


def test_c_lead_time_longer_than_the_need_date_warns_the_card(enterprise, monkeypatch):
    monkeypatch.setitem(entmain.data.SPARE_BASE["P-PMP-SEAL"], "need_by_days", 3)        # 결품까지 3일 — B-OEM 5일은 늦다
    facts, result = c_judge(monkeypatch)
    b = next(x for x in result["options"] if x["sopId"] == "SOP-PUR-11")
    assert b["facts"]["lead_slack_days"] == -2 and {w["rule"] for w in b["warnings"]} == {"rule:pur-amount", "rule:pur-lead"}


def test_business_cause_comes_from_the_graph_path_not_from_a_sensor_diagnosis(enterprise):
    """C 재고 경보에는 증상이 없다: 원인은 '모자란 부품을 쓰는 원인'(Cause -INVOLVES_PART-> Part)으로 읽는다. 엉뚱한 원인은 거절."""
    from dmn_mcp.tools import DmnTools
    calls = []

    class KG:
        def t1_causes(self, pattern, asset):
            return []

    tools = DmnTools(kg=KG(), tsdb=object(), fabric=object())

    def graph(cypher, **params):
        calls.append(params)
        return [{"causeId": "cause:pump-seal-wear", "cause": "축 씰 마모", "failureModeId": "fm:volumetric-loss", "failureMode": "체적 효율 저하",
                 "partNo": "P-PMP-SEAL", "prior": 0.6}] if "P-PMP-SEAL" in (params.get("parts") or []) else []
    tools._graph = graph
    out = tools.business_causes("HYD-03", "SPARE_BELOW_MIN")
    assert out["parts_below_reorder_point"] == ["P-PMP-SEAL"] and out["top_cause"] == "cause:pump-seal-wear"
    assert tools._diagnosed_cause("HYD-03", "SPARE_BELOW_MIN", "cause:pump-seal-wear", "fm:volumetric-loss")["name"] == "축 씰 마모"
    with pytest.raises(ValueError, match="업무 근거"):
        tools._diagnosed_cause("HYD-03", "SPARE_BELOW_MIN", "cause:cooler-fin-fouling", "fm:cooling-loss")
    with pytest.raises(ValueError, match="업무 경보가 아닙니다"):
        tools.business_causes("HYD-01", "COOLER_DEGRADATION")
