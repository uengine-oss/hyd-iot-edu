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
