"""L8 enterprise decision engine: the ontology supplies options, KPI impact formulas, KPI owners and policies;
enterprise systems supply facts. The engine must show why a department optimum is not the enterprise optimum."""
import pytest

from agentsvc import decision

KPIS = [
    {"id": "kpi:part-cost", "name": "부품 구매단가", "owner": "dept:purchasing", "ownerName": "구매팀", "weight": 1.0},
    {"id": "kpi:reliability", "name": "설비 신뢰성·가동", "owner": "dept:maintenance", "ownerName": "설비보전팀", "weight": 1.0},
    {"id": "kpi:customer", "name": "고객 신뢰·매출", "owner": "dept:sales", "ownerName": "영업팀", "weight": 1.0},
]
POLICIES = [
    {"id": "pol:avl", "name": "핵심 부품은 AVL 공급사만", "kind": "HARD", "expr": "o_avl == 0", "skills": ["skill:procure-part"], "source": "사내 구매규정"},
]


def opt(oid, name, price, fail, avl):
    return {"id": oid, "name": name, "params": {"price": price, "fail_rate": fail, "avl": avl},
            "skills": [{"id": "skill:procure-part", "name": "부품 구매요청", "system": "sys:erp"}],
            "approver": {"id": "role:purchasing-mgr", "name": "구매팀장"},
            "impacts": [
                {"kpi": "kpi:part-cost", "expr": "scm_std_price - o_price"},
                {"kpi": "kpi:reliability", "expr": "-o_fail_rate * erp_failure_cost"},
                {"kpi": "kpi:customer", "expr": "-o_fail_rate * erp_claim_cost"},
            ]}


CTX = {"scenario": {"id": "sc:part", "name": "교체 부품 구매"},
       "kpis": KPIS, "policies": POLICIES,
       "options": [opt("opt:cheap", "저가 공급사", 180, 0.12, 1), opt("opt:oem", "OEM 공급사", 260, 0.02, 1),
                   opt("opt:rock-bottom", "최저가 비승인", 120, 0.20, 0)]}
FACTS = {"scm_std_price": 250, "erp_failure_cost": 900, "erp_claim_cost": 300}


def test_safe_eval_supports_arithmetic_min_max_comparisons_and_conditionals():
    v = {"a": 2, "b": 5}
    assert decision.safe_eval("a * 3 - b", v) == 1
    assert decision.safe_eval("max(0, a - b)", v) == 0
    assert decision.safe_eval("a < b and b > 4", v) is True
    assert decision.safe_eval("10 if a > 1 else -10", v) == 10


@pytest.mark.parametrize("expr", ["__import__('os')", "a.__class__", "open('x')", "[1][0]", "lambda: 1"])
def test_safe_eval_rejects_anything_but_plain_math(expr):
    with pytest.raises(ValueError):
        decision.safe_eval(expr, {"a": 1})


def test_safe_eval_reports_missing_facts():
    with pytest.raises(KeyError):
        decision.safe_eval("erp_unknown + 1", {})


def test_enterprise_winner_differs_from_purchasing_winner():
    r = decision.evaluate(CTX, FACTS)
    assert r["recommended"] == "opt:oem"
    assert r["winners"]["enterprise"] == "opt:oem"
    assert r["winners"]["dept:purchasing"] == "opt:cheap"
    by = {o["id"]: o for o in r["options"]}
    assert by["opt:cheap"]["impacts"]["kpi:part-cost"] == 70
    assert by["opt:cheap"]["total"] == pytest.approx(70 - 108 - 36)
    assert by["opt:oem"]["total"] == pytest.approx(-10 - 18 - 6)


def test_hard_policy_excludes_an_option_even_if_a_department_would_pick_it():
    r = decision.evaluate(CTX, FACTS)
    by = {o["id"]: o for o in r["options"]}
    assert by["opt:rock-bottom"]["feasible"] is False
    assert by["opt:rock-bottom"]["violations"][0]["policy"] == "pol:avl"
    assert r["naiveWinners"]["dept:purchasing"] == "opt:rock-bottom"     # what purchasing would do without the rule


def test_soft_policy_penalty_is_charged_to_its_kpi():
    ctx = dict(CTX, policies=POLICIES + [{"id": "pol:lead", "name": "리드타임 4일 초과 시 임시 세척비", "kind": "SOFT",
                                          "expr": "o_price > 200", "penalty": "-50", "kpi": "kpi:reliability",
                                          "skills": ["skill:procure-part"]}])
    r = decision.evaluate(ctx, FACTS)
    by = {o["id"]: o for o in r["options"]}
    assert by["opt:oem"]["impacts"]["kpi:reliability"] == pytest.approx(-18 - 50)
    assert r["recommended"] == "opt:cheap"                                 # -74 now beats -84


def test_missing_fact_makes_the_option_infeasible_with_a_reason():
    r = decision.evaluate(CTX, {"scm_std_price": 250})
    assert r["recommended"] is None
    assert all(not o["feasible"] for o in r["options"])
    assert any("erp_failure_cost" in e for e in r["errors"])


def test_explanation_names_the_conflict_and_the_drivers():
    r = decision.evaluate(CTX, FACTS)
    text = r["explanation"]
    assert "OEM 공급사" in text and "구매팀" in text and "저가 공급사" in text
    assert r["drivers"][0]["kpi"] == "kpi:reliability"                     # largest difference winner vs runner-up
    assert r["approver"]["name"] == "구매팀장"


def test_context_from_template_rows_parses_params_and_policy_scope():
    ctx = decision.build_context(
        {"scenario": {"id": "sc:x", "name": "X"}, "infos": [None, {"id": "info:a"}]},
        [{"id": "opt:1", "name": "one", "params": '{"peak_ts1": 70}', "skills": [], "impacts": [{"kpi": "kpi:otd", "expr": "0"}], "approver": None}],
        KPIS,
        [{"id": "pol:ts1-limit", "name": "65 ℃", "kind": "HARD", "expr": "o_peak_ts1 >= 65", "skills": [], "scenarioScope": True},
         {"id": "pol:other", "name": "other scenario", "kind": "HARD", "expr": "1 == 1", "skills": [], "scenarioScope": False}])
    assert ctx["options"][0]["params"] == {"peak_ts1": 70}
    assert ctx["infos"] == [{"id": "info:a"}]
    pols = {p["id"]: p for p in ctx["policies"]}
    assert pols["pol:ts1-limit"]["scope"] == "scenario"
    r = decision.evaluate(ctx, {})
    assert r["options"][0]["violations"][0]["policy"] == "pol:ts1-limit"      # scenario-wide policy hits an option with no skills
    assert all(v["policy"] != "pol:other" for v in r["options"][0]["violations"])


def test_facts_are_prefixed_with_the_ontology_prefix_and_keep_provenance():
    infos = [{"id": "info:mes-order", "prefix": "mes", "system": "sys:mes", "systemName": "MES", "endpoint": "/mes/orders?asset={asset}"}]
    facts, prov = decision.assemble_facts(infos, {"info:mes-order": {"system": "MES", "facts": {"due_in_h": 6}, "records": [{"a": 1}]}}, "HYD-01")
    assert facts == {"mes_due_in_h": 6}
    assert prov[0]["endpoint"] == "/mes/orders?asset=HYD-01" and prov[0]["system"] == "sys:mes" and prov[0]["facts"] == {"mes_due_in_h": 6}


def test_decision_guardrail_passes_a_clean_result_and_flags_problems():
    from agentsvc import guardrail
    r = decision.evaluate(CTX, FACTS)
    assert guardrail.check_decision(r, CTX) == []
    bad_ctx = dict(CTX, kpis=KPIS[:2])                                     # an impact cites a KPI the ontology does not have
    assert any("kpi:customer" in v for v in guardrail.check_decision(decision.evaluate(bad_ctx, FACTS), bad_ctx))
    no_owner = dict(CTX, options=[dict(o, approver=None) for o in CTX["options"]])
    assert any("승인 역할" in v for v in guardrail.check_decision(decision.evaluate(no_owner, FACTS), no_owner))


def test_only_departments_whose_kpis_the_scenario_touches_get_a_perspective():
    kpis = KPIS + [{"id": "kpi:energy", "name": "에너지", "owner": "dept:ehs", "ownerName": "환경안전팀", "weight": 1.0}]
    r = decision.evaluate(dict(CTX, kpis=kpis), FACTS)
    assert "dept:ehs" not in r["winners"]
    assert [d["id"] for d in r["departments"]] == ["dept:maintenance", "dept:purchasing", "dept:sales"]


def test_rule_excluded_option_is_only_mentioned_when_strictly_better_for_that_department():
    r = decision.evaluate(CTX, FACTS)
    assert r["explanation"].count("처음부터 제외") == 1                    # purchasing only; maintenance/sales never preferred it


def test_a_policy_that_does_not_apply_does_not_drag_its_kpi_owner_into_the_scenario():
    kpis = KPIS + [{"id": "kpi:energy", "name": "에너지", "owner": "dept:ehs", "ownerName": "환경안전팀", "weight": 1.0}]
    pols = POLICIES + [{"id": "pol:x", "name": "x", "kind": "SOFT", "expr": "1 == 1", "penalty": "-5", "kpi": "kpi:energy", "skills": ["skill:other"]}]
    r = decision.evaluate(dict(CTX, kpis=kpis, policies=pols), FACTS)
    assert "dept:ehs" not in r["winners"]


PREC_KPI = {"id": "kpi:precedent", "name": "현장 판단 선례", "owner": "dept:plant", "ownerName": "공장 경영", "weight": 1.0, "value_per_share": 60}


def test_past_human_choices_add_a_precedent_bonus_that_can_change_the_recommendation():
    ctx = dict(CTX, kpis=KPIS + [PREC_KPI], precedents={"opt:cheap": {"n": 9, "reasons": ["리드타임 급함"]}, "opt:oem": {"n": 1, "reasons": []}})
    r = decision.evaluate(ctx, FACTS)
    by = {o["id"]: o for o in r["options"]}
    assert by["opt:cheap"]["impacts"]["kpi:precedent"] == 54.0            # 60 × 9/10
    assert by["opt:oem"]["impacts"]["kpi:precedent"] == 6.0
    assert by["opt:cheap"]["precedent"] == {"n": 9, "share": 0.9, "reasons": ["리드타임 급함"]}
    assert r["recommended"] == "opt:cheap"                                 # -74+54 = -20 beats -34+6 = -28
    assert "선례" in r["explanation"]


def test_without_precedents_nothing_changes():
    r = decision.evaluate(dict(CTX, kpis=KPIS + [PREC_KPI]), FACTS)
    assert r["recommended"] == "opt:oem"
    assert all("kpi:precedent" not in o["impacts"] for o in r["options"])
