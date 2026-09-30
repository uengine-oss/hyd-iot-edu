from agentsvc import card
from agentsvc.runs import RunRegistry

T1 = [
    {"causeId": "cause:cooler-fin-fouling", "cause": "쿨러 핀 오염", "description": "d1", "failureModeId": "fm:cooler-performance-loss",
     "failureMode": "쿨러 냉각 성능 상실", "component": "오일 쿨러", "prior": 0.5, "symptoms": ["유온 상승"],
     "evidence": [{"id": "ev:ce-low", "name": "CE<70", "weight": 0.4, "expect": "lt", "threshold": 70, "sql": "x"},
                  {"id": "ev:ts1-rising", "name": "TS1 rising", "weight": 0.3, "expect": "gt", "threshold": 3, "sql": "y"},
                  {"id": "ev:fan-commanded-normal", "name": "fan>=50", "weight": 0.3, "expect": "gte", "threshold": 50, "sql": "z"}]},
    {"causeId": "cause:fan-underperformance", "cause": "팬 성능 저하", "description": "d2", "failureModeId": "fm:cooler-performance-loss",
     "failureMode": "쿨러 냉각 성능 상실", "component": "오일 쿨러", "prior": 0.25, "symptoms": [],
     "evidence": [{"id": "ev:ce-low", "name": "CE<70", "weight": 0.4, "expect": "lt", "threshold": 70, "sql": "x"},
                  {"id": "ev:pump-vibration-high", "name": "VS1>0.9", "weight": 0.6, "expect": "gt", "threshold": 0.9, "sql": "v"}]},
    {"causeId": "cause:no-evidence", "cause": "증거 없음", "description": "", "failureModeId": "fm:x", "failureMode": "x",
     "component": None, "prior": 0.9, "symptoms": [], "evidence": []},
]
RESULTS = {"ev:ce-low": {"value": 36.1, "passed": True}, "ev:ts1-rising": {"value": 8.2, "passed": True},
           "ev:fan-commanded-normal": {"value": 60.0, "passed": True}, "ev:pump-vibration-high": {"value": 0.6, "passed": False}}
T2 = {"cause:cooler-fin-fouling": [
    {"actionId": "act:fan-boost", "code": "FAN_BOOST", "name": "팬 상향", "kind": "command", "priority": 1, "description": "",
     "param": "fan_pct", "min": 80, "max": 100, "default": 100, "relation": "MITIGATED_BY", "actuatorId": "HYD-01:CoolerFan", "resource": "FanSpeedSP",
     "procedure": {"id": "SOP-COOL-01", "name": "과열 완화"}, "constraints": [{"id": "cons:fan-range", "name": "0..100", "expr": "x"}],
     "steps": [{"id": "SOP-COOL-01/2", "order": 2, "text": "팬 상향", "manual": {"id": "HM-7.3", "ref": "HM-7.3", "title": "팬", "excerpt": "e"}},
               {"id": "SOP-COOL-01/1", "order": 1, "text": "모드 확인", "manual": {"id": "HM-3.2", "ref": "HM-3.2", "title": "모드", "excerpt": "e"}}]},
    {"actionId": "act:reduce-load", "code": "REDUCE_LOAD", "name": "부하 저감", "kind": "command", "priority": 2, "description": "",
     "param": "load_pct", "min": 60, "max": 90, "default": 80, "relation": "MITIGATED_BY", "actuatorId": "HYD-01:PumpLoad", "resource": "LoadSP",
     "procedure": {"id": "SOP-COOL-01", "name": "과열 완화"}, "constraints": [], "steps": []},
    {"actionId": "act:cooler-clean-wo", "code": "COOLER_CLEAN_WO", "name": "세척 WO", "kind": "work_order", "priority": 3, "description": "",
     "param": None, "min": None, "max": None, "default": None, "relation": "REMEDIED_BY", "actuatorId": None, "resource": None,
     "procedure": {"id": "SOP-COOL-02", "name": "세척"}, "constraints": [], "steps": []},
]}
ALERT = {"alertId": "ALT-hyd01-0001", "asset": "HYD-01", "pattern": "COOLER_DEGRADATION", "severity": "HIGH", "state": "RAISE",
         "t": "2026-09-23T10:12:30Z", "evidence": {"ts1": 56.3, "ce": 36.1, "ts1_slope": 0.012, "score": 1.0}}


def test_rank_causes_weights_by_passed_evidence():
    ranked = card.rank_causes(T1, RESULTS)
    assert [c["id"] for c in ranked][:2] == ["cause:cooler-fin-fouling", "cause:fan-underperformance"]
    top = ranked[0]
    assert abs(top["score"] - 0.5 * 1.0) < 1e-9          # all three evidence rules passed
    second = ranked[1]
    assert abs(second["score"] - 0.25 * (0.4 / 1.0)) < 1e-9   # only ce-low passed (0.4 of 1.0)
    assert second["evidence"][1]["passed"] is False and second["evidence"][1]["value"] == 0.6


def test_rank_causes_without_evidence_gets_discounted_prior():
    ranked = card.rank_causes(T1, RESULTS)
    none = next(c for c in ranked if c["id"] == "cause:no-evidence")
    assert none["score"] < 0.5 and none["evidence"] == []


def test_build_card_includes_sop_and_manual():
    causes = card.rank_causes(T1, RESULTS)
    c = card.build_card("INC-1", ALERT, causes, T2, {"ok": True, "age_s": 1.2})
    assert c["incident"] == "INC-1" and c["alert"]["alertId"] == "ALT-hyd01-0001"
    assert c["topCause"] == "cause:cooler-fin-fouling"
    codes = [a["code"] for a in c["recommended"]]
    assert codes == ["FAN_BOOST", "REDUCE_LOAD", "COOLER_CLEAN_WO"]
    fan = c["recommended"][0]
    assert fan["value"] == 100 and fan["paramRange"] == [80, 100] and fan["param"] == "fan_pct"
    assert [s["order"] for s in fan["sop"]["steps"]] == [1, 2]
    assert fan["sop"]["steps"][1]["manual"]["ref"] == "HM-7.3"
    assert "act:fan-boost" in c["citations"] and "cause:cooler-fin-fouling" in c["citations"] and "HM-7.3" in c["citations"]
    assert "cmdId" not in c and "writes" not in c
    assert isinstance(c["summary"], str) and "HYD-01" in c["summary"]


def test_duplicate_raise_creates_one_run():
    reg = RunRegistry()
    r1 = reg.create_if_new(ALERT)
    r2 = reg.create_if_new(ALERT)
    assert r1 is not None and r2 is None
    assert reg.get(r1.id).alert_id == "ALT-hyd01-0001"
    r1.step("freshness", {"ok": True})
    assert reg.get(r1.id).steps[0]["name"] == "freshness"


def test_evaluate_evidence_rule_comparisons():
    assert card.passes("lt", 36.1, 70) and not card.passes("lt", 80, 70)
    assert card.passes("gte", 50, 50) and card.passes("gt", 8.2, 3) and not card.passes("gt", None, 3)
