import copy

from agentsvc import guardrail

GOOD = {
    "incident": "INC-1",
    "alert": {"alertId": "ALT-1", "asset": "HYD-01", "pattern": "COOLER_DEGRADATION"},
    "freshness": {"ok": True, "age_s": 1.0},
    "causes": [{"id": "cause:cooler-fin-fouling", "name": "핀 오염", "score": 0.5,
                "evidence": [{"id": "ev:ce-low", "passed": True, "value": 36.0, "weight": 0.4}]}],
    "topCause": "cause:cooler-fin-fouling",
    "recommended": [
        {"code": "FAN_BOOST", "actionId": "act:fan-boost", "name": "팬 상향", "kind": "command", "param": "fan_pct",
         "value": 100, "paramRange": [80, 100], "constraints": [], "sop": {"id": "SOP-COOL-01", "steps": []}},
        {"code": "COOLER_CLEAN_WO", "actionId": "act:cooler-clean-wo", "name": "세척 WO", "kind": "work_order", "param": None,
         "value": None, "paramRange": None, "constraints": [], "sop": {"id": "SOP-COOL-02", "steps": []}},
    ],
    "citations": ["cause:cooler-fin-fouling", "ev:ce-low", "act:fan-boost", "act:cooler-clean-wo", "SOP-COOL-01", "SOP-COOL-02"],
    "summary": "ok",
}


def test_good_card_passes():
    assert guardrail.check(GOOD) == []


def test_guardrail_rejects_missing_citation():
    c = copy.deepcopy(GOOD)
    c["citations"].remove("act:fan-boost")
    v = guardrail.check(c)
    assert any("act:fan-boost" in x and "cit" in x.lower() for x in v)


def test_guardrail_rejects_action_without_node_id():
    c = copy.deepcopy(GOOD)
    c["recommended"][0]["actionId"] = None
    assert any("FAN_BOOST" in x for x in guardrail.check(c))


def test_guardrail_rejects_out_of_range_value():
    c = copy.deepcopy(GOOD)
    c["recommended"][0]["value"] = 120
    assert any("paramRange" in x or "range" in x.lower() for x in guardrail.check(c))


def test_guardrail_rejects_command_fields():
    c = copy.deepcopy(GOOD)
    c["writes"] = [{"res": "FanSpeedSP", "v": 100}]
    assert any("command" in x.lower() or "writes" in x for x in guardrail.check(c))
    c2 = copy.deepcopy(GOOD)
    c2["recommended"][0]["cmdId"] = "CMD-1"
    assert guardrail.check(c2)


def test_guardrail_rejects_empty_citations_or_causes():
    c = copy.deepcopy(GOOD)
    c["citations"] = []
    assert guardrail.check(c)
    c2 = copy.deepcopy(GOOD)
    c2["causes"] = []
    assert guardrail.check(c2)


def test_guardrail_rejects_stale_data():
    c = copy.deepcopy(GOOD)
    c["freshness"] = {"ok": False, "age_s": 300}
    assert any("fresh" in x.lower() for x in guardrail.check(c))


def test_command_without_parameter_is_allowed():
    """RESET has no parameter: a command needs a range/value only when it has a parameter."""
    c = copy.deepcopy(GOOD)
    c["recommended"].append({"code": "RESET", "actionId": "action:reset", "name": "리셋", "kind": "command", "param": None,
                             "value": 1, "paramRange": None, "constraints": [], "sop": {"id": "SOP-TRIP-01", "steps": []}})
    c["citations"].append("action:reset")
    assert guardrail.check(c) == []


CARDS = {"recommended": "skill:a", "options": [
    {"id": "skill:a", "sopId": "SOP-A", "feasible": True, "violations": [], "approver": {"id": "role:prod-mgr"},
     "selectedBy": [{"rule": "rule:cand"}], "steps": [{"id": "SOP-A/1"}]},
    {"id": "skill:b", "sopId": "SOP-B", "feasible": False, "violations": [{"rule": "rule:x"}], "approver": {"id": "role:operator"},
     "selectedBy": [{"rule": "rule:cand"}], "steps": [{"id": "SOP-B/1"}]}]}


def test_cards_guardrail_passes_a_cited_feasible_recommendation():
    assert guardrail.check_cards(CARDS) == []


def test_cards_guardrail_rejects_uncited_infeasible_or_unapproved_recommendation():
    c = copy.deepcopy(CARDS); c["options"][1]["selectedBy"] = []
    assert any("skill:b" in v for v in guardrail.check_cards(c))
    c = copy.deepcopy(CARDS); c["recommended"] = "skill:b"
    assert any("규정" in v for v in guardrail.check_cards(c))
    c = copy.deepcopy(CARDS); c["options"][0]["approver"] = None
    assert any("승인" in v for v in guardrail.check_cards(c))
    c = copy.deepcopy(CARDS); c["options"][0]["steps"] = []
    assert any("SOP" in v for v in guardrail.check_cards(c))


def test_categorical_command_passes_without_a_numeric_range():
    # PUMP_SELECT pump='B' (ontology actr:pump-selector, min/max null) must pass; a numeric parameter still needs its range
    base = {"alert": {"alertId": "A", "asset": "HYD-02", "pattern": "PUMP_LEAKAGE"}, "freshness": {"ok": True, "age_s": 1.0},
            "causes": [{"id": "cause:pump-seal-wear", "name": "씰", "score": 0.6, "evidence": []}], "topCause": "cause:pump-seal-wear", "summary": "s"}
    pump = {"code": "PUMP_SELECT", "actionId": "action:select-pump", "name": "예비 펌프 전환", "kind": "command", "param": "pump", "value": "B",
            "paramRange": None, "constraints": [], "sop": {"id": "SOP-PMP-01", "steps": []}}
    card = dict(base, recommended=[pump], citations=["cause:pump-seal-wear", "action:select-pump"])
    assert not [x for x in guardrail.check(card) if "PUMP_SELECT" in x]
    load = dict(pump, code="LOAD_SET", actionId="action:set-load", param="load_pct", value=70, paramRange=None)
    card = dict(base, recommended=[load], citations=["cause:pump-seal-wear", "action:set-load"])
    assert any("lacks paramRange" in x for x in guardrail.check(card))
    card = dict(base, recommended=[dict(pump, value=None)], citations=["cause:pump-seal-wear", "action:select-pump"])
    assert any("lacks value" in x for x in guardrail.check(card))
