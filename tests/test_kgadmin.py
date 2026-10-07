"""L9 knowledge admin: manual upload -> SOP ingestion (parser), skill edit validation."""
import pytest

from procsvc import kgadmin

MANUAL = """# 유압 파워유닛 정비 매뉴얼 (HM-8)

## HM-8.1 쿨러 팬 벨트 점검
팬 지시값은 정상인데 풍량이 부족하면 벨트 장력부터 본다.
진동 VS1이 0.9 mm/s를 넘으면 베어링도 의심한다.

### SOP-FAN-01 쿨러 팬 점검 절차
1. 설비를 정지하고 LOCAL로 전환한다.
2. 벨트 장력을 측정한다 (처짐 10~15 mm).
3) 베어링 소음과 온도를 확인한다.

## HM-8.2 벨트 교체
장력이 기준 밖이면 벨트를 교체한다.
1. 구 벨트를 분리한다.
2. 새 벨트를 걸고 장력을 맞춘다.
"""


def test_sections_are_found_with_ref_title_and_excerpt():
    r = kgadmin.parse_manual(MANUAL, "hm8.md")
    refs = [s["ref"] for s in r["sections"]]
    assert refs == ["HM-8.1", "HM-8.2"]
    s1 = r["sections"][0]
    assert s1["title"] == "쿨러 팬 벨트 점검" and "벨트 장력" in s1["excerpt"]


def test_numbered_lines_become_steps_of_a_procedure_linked_to_their_section():
    r = kgadmin.parse_manual(MANUAL, "hm8.md")
    p = {x["id"]: x for x in r["procedures"]}
    assert p["SOP-FAN-01"]["name"] == "쿨러 팬 점검 절차"
    assert [s["order"] for s in p["SOP-FAN-01"]["steps"]] == [1, 2, 3]
    assert p["SOP-FAN-01"]["steps"][2]["text"] == "베어링 소음과 온도를 확인한다."
    assert all(s["manual"] == "HM-8.1" for s in p["SOP-FAN-01"]["steps"])
    auto = p["SOP-HM-8.2"]                                   # steps without an explicit SOP heading get an automatic procedure
    assert auto["name"] == "벨트 교체" and auto["steps"][1]["manual"] == "HM-8.2"


def test_plain_text_headings_without_markdown_also_work():                # e.g. text extracted from a PDF
    r = kgadmin.parse_manual("HM-9.3 작동유 교환\n오일을 배출한다.\n1. 드레인 밸브를 연다.\n2. 필터를 교체한다.", "x.pdf")
    assert r["sections"][0]["ref"] == "HM-9.3" and r["procedures"][0]["steps"][0]["text"] == "드레인 밸브를 연다."


def test_action_suggestion_by_keyword_overlap():
    actions = [{"id": "act:fan-inspect-wo", "name": "쿨러 팬 점검 작업지시"}, {"id": "act:reduce-load", "name": "펌프 부하 저감"}]
    r = kgadmin.parse_manual(MANUAL, "hm8.md", actions)
    p = {x["id"]: x for x in r["procedures"]}
    assert p["SOP-FAN-01"]["suggestedAction"] == "act:fan-inspect-wo"


def test_empty_or_unstructured_text_is_reported():
    r = kgadmin.parse_manual("그냥 메모입니다.", "memo.txt")
    assert r["sections"] == [] and r["procedures"] == [] and r["warnings"]


def test_skill_validation_for_edit():
    ok = kgadmin.validate_skill({"name": "팬 최대", "description": "팬만 100 %로 올린다", "approver": "role:operator"})
    assert ok == {"name": "팬 최대", "description": "팬만 100 %로 올린다", "approver": "role:operator"}
    with pytest.raises(ValueError):
        kgadmin.validate_skill({"name": "  ", "description": "x"})
    with pytest.raises(ValueError):
        kgadmin.validate_skill({"name": "x" * 200})


def test_new_skill_must_be_an_sop_matched_to_a_failure_mode():
    """조치 방법 = Skill = SOP: a new skill needs an SOP id, at least one step and a failure mode it is matched to."""
    body = {"name": "벨트 교체", "description": "벨트를 교체한다", "sopId": "SOP-FAN-05", "kind": "work_order",
            "failureMode": "fm:bearing-degradation", "relation": "REMEDIED_BY", "steps": "LOCAL로 전환한다.\n\n벨트를 교체한다. ", "approver": "role:maint-mgr"}
    ok = kgadmin.validate_skill(body, create=True)
    assert ok["steps"] == ["LOCAL로 전환한다.", "벨트를 교체한다."] and ok["sopId"] == "SOP-FAN-05" and ok["relation"] == "REMEDIED_BY"
    for bad in ({"sopId": "fan 5"}, {"steps": "  "}, {"failureMode": ""}, {"kind": "business"}, {"relation": "CAUSES"}):
        with pytest.raises(ValueError):
            kgadmin.validate_skill(body | bad, create=True)
    assert kgadmin.skill_id("SOP-FAN-05") == "skill:sop-fan-05"


def test_ties_prefer_work_order_actions_for_maintenance_procedures():
    actions = [{"id": "act:fan-boost", "name": "쿨러 팬 속도 상향", "kind": "command"},
               {"id": "act:cooler-clean-wo", "name": "쿨러 핀 세척 작업지시", "kind": "work_order"},
               {"id": "act:fan-inspect-wo", "name": "쿨러 팬 점검 작업지시", "kind": "work_order"}]
    r = kgadmin.parse_manual("## HM-8.2 쿨러 팬 벨트 교체\n### SOP-FAN-02 벨트 교체 절차\n1. 구 벨트를 분리한다.", "m.md", actions)
    assert r["procedures"][0]["suggestedAction"] == "act:fan-inspect-wo"


def test_existing_skill_can_be_relinked_to_a_failure_mode_for_candidate_rules():
    """A075: a reviewer re-links an admin-registered SOP to a failure mode so the candidate rules can offer it."""
    out = kgadmin.validate_skill({"name": "쿨러 팬 점검 절차", "failureMode": " fm:bearing-degradation ", "relation": "REMEDIED_BY"})
    assert out["failureMode"] == "fm:bearing-degradation" and out["relation"] == "REMEDIED_BY"
    assert "failureMode" not in kgadmin.validate_skill({"name": "이름만"})
    with pytest.raises(ValueError):
        kgadmin.validate_skill({"name": "x", "failureMode": "fm:x", "relation": "CAUSES"})


def test_skill_edit_accepts_impact_links_and_rejects_bad_targets():
    """A098: the admin skill edit carries AFFECTS (target sv:/msr:, sign ±), like the manual-ingestion review (A079)."""
    out = kgadmin.validate_skill({"name": "쿨러 팬 점검 절차", "description": "x", "affects": [{"target": "sv:bearing-wear", "sign": "-", "note": "점검"}, {"target": "msr:maint-cost", "sign": 1}]})
    assert out["affects"] == [{"target": "sv:bearing-wear", "sign": -1, "note": "점검"}, {"target": "msr:maint-cost", "sign": 1, "note": ""}]
    assert "affects" not in kgadmin.validate_skill({"name": "팬", "description": "x"})
    import pytest
    for bad in ([{"target": "sen:ts1", "sign": "+"}], [{"target": "sv:x", "sign": "up"}], [{"target": "sv:x", "sign": "+"}, {"target": "sv:x", "sign": "-"}], "sv:x", [{}] * 13):
        with pytest.raises(ValueError):
            kgadmin.validate_skill({"name": "팬", "description": "x", "affects": bad})
