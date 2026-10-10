"""캡스톤 강사 키트 T0 · T5 · T6 · T7 · T8 (docs/handoff/verification/2026-10-09/capstone-lab.md 6.1) 검사.

라이브 스택 없이 본다: 사례 카드 7칸 · 판정 5개, 구글 안내가 실제 코드의 비밀 자리표시자 규칙 · 읽기 판정과 맞는가,
요령 틀이 승인 카드 칸 이름 약속(G7)을 지키는가, 흐름 그림이 포털 가져오기 파서(bpmn_import)로 읽히고 DI 가 빠짐없는가,
예시 스키마 · 지식이 확정 스키마 v2 변경 없이 학생 검사(check-extra · validate_ns)를 통과하는가,
그리고 G1 · G3 이 없는 지금 예시 흐름이 어떤 사유로 거절되는가(숨기지 않고 기대값으로).
"""
import copy
import importlib.util
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from procsvc import bpmn_import as B, mcp_check, mcp_secrets
from procsvc.agents_store import SKILL_NAME_RE, split_frontmatter

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / "students" / "_template"
EX = KIT / "example_meeting"
spec = importlib.util.spec_from_file_location("ontology_v2_kit", ROOT / "scripts" / "ontology_v2.py")
ov = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ov)
BASE_DEF = json.loads((ROOT / "it/process/definitions/anomaly_response_v22.json").read_text(encoding="utf-8"))
NS = {"bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL", "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI"}
AGENT_ID = "agent:u-0d3e0a11"
USERS = [{"id": "role:demo-organizer", "username": "회의 주관자"},                       # G10 '역할 만들기'로 만든 역할
         {"id": AGENT_ID, "username": "회의 준비 에이전트", "is_agent": True, "agent_type": "agent"}]


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------- T0 사례 카드
def test_case_card_has_seven_slots_five_checks_and_a_filled_example_with_losers_and_unhappy_branch():
    text = read(KIT / "case_card.md")
    blank, example = text.split("## 채운 예", 1)
    rows = lambda part: re.findall(r"^\| ([1-7]) \|", part, re.M)
    assert rows(blank) == list("1234567") and rows(example) == list("1234567")
    assert blank.count("- [ ]") == 5 and example.count("- [x]") == 5
    assert "48시간" in example and "필수 참석자" in example                          # 지는 안 두 개가 규칙 이유로 진다
    assert "거절" in example and "응답하지" in example and "미확정" in example       # 미달 가지
    assert "가상" in example and "example.com" in example


# ---------------------------------------------------------------- T5 구글 MCP 안내 = 실제 코드 규칙
def test_google_guide_placeholder_and_fields_match_the_secret_code():
    text = read(KIT / "google_mcp.md")
    header = re.search(r"`(Authorization=Bearer \$\{SECRET:([A-Z_]+)\})`", text)
    assert header, "접속 헤더 예가 없다"
    key = header.group(2)
    entry = {"type": "url", "url": "https://example.invalid/mcp", "headers": {"Authorization": f"Bearer ${{SECRET:{key}}}"}}
    assert mcp_secrets.valid_key(key) and mcp_secrets.references(entry) == [key] and mcp_secrets.misplaced(entry) == []
    assert mcp_secrets.is_reference_only(entry["headers"]["Authorization"])          # 화면에 보여도 되는 값(이름만)
    assert mcp_secrets.ENV_PREFIX + key in text                                       # 환경 변수 대안 이름
    bad = dict(entry, url="https://x/mcp?t=${SECRET:%s}" % key)
    assert mcp_secrets.misplaced(bad) and "headers · env 값에만" in text           # 안내한 거절이 실제로 난다
    for launcher in ("npx", "uvx", "node", "python"):
        assert launcher in text
    assert "인증이 만료되었거나 없습니다" in text and "비밀 값" in text


def test_google_guide_read_write_table_matches_the_read_only_verdict():
    text = read(KIT / "google_mcp.md")
    assert "readOnlyHint=true" in text and "읽기로 확인" in text
    # 안내 문구: 표시 없는 읽기 도구는 강사가 확인 가능, 쓰기 낱말 · 쓰기 표시 도구는 확인 불가
    assert mcp_check.confirmable({"name": "search_files", "annotations": {}})
    assert not mcp_check.confirmable({"name": "create_event", "annotations": {}})
    assert not mcp_check.confirmable({"name": "list_items", "annotations": {"readOnlyHint": False}})
    assert mcp_check.read_only_verdict({"name": "find_free_slots", "annotations": {"readOnlyHint": True}})[0]
    for word in re.findall(r"쓰기 낱말\(([^)]*)\)", text)[0].replace("…", "").split("·"):
        assert word.strip() in mcp_check._WRITE_WORDS, word
    assert "강사가 고른 서버의 도구 목록으로 채울 칸" in text
    # 실제 구글 도구 이름을 지어 넣지 않았다: 도구 이름 칸이 비어 있다
    rows = [r for r in text.splitlines() if r.startswith("| 드라이브 |") or r.startswith("| 캘린더 |")]
    assert rows and all(r.split("|")[2].strip() == "" for r in rows)


# ---------------------------------------------------------------- T6 · T8 요령 = 승인 카드 칸 약속(G7)
PROMISE = ("options", "recommended", "losers", "docs")


def _result_block(skill_text: str) -> dict:
    body = re.search(r"## 결과 \(output/result.json\)\s*```json\s*(\{.*?\})\s*```", skill_text, re.S).group(1)
    keys = set(re.findall(r'"([a-z_]+)"\s*:', body))
    return {"text": body, "keys": keys}


@pytest.mark.parametrize("path", [KIT / "agent" / "SKILL.md", EX / "agent" / "SKILL.md"])
def test_skill_template_has_five_steps_rule_table_and_the_card_promise(path):
    text = read(path)
    meta, body = split_frontmatter(text)
    assert SKILL_NAME_RE.match(meta["name"]) and meta["description"]
    steps = re.findall(r"^([1-5])\. ", body.split("## 절차", 1)[1].split("##", 1)[0], re.M)
    assert steps == list("12345")
    assert "## 규칙으로 빼기" in body and "승인 전에는 조회 · 계산 · 요약만" in body
    keys = _result_block(body)["keys"]
    assert set(PROMISE) | {"proposal", "slot", "reason", "score", "why", "title", "link"} <= keys


def test_example_proposal_keeps_the_promise_and_has_real_losers():
    p = json.loads(read(EX / "agent" / "proposal.example.json"))["proposal"]
    assert set(PROMISE) <= set(p)
    assert all({"slot", "reason", "score"} <= set(o) for o in p["options"])
    scores = [o["score"] for o in p["options"]]
    assert scores == sorted(scores, reverse=True) and p["recommended"] == p["options"][0]["slot"]
    assert len(p["losers"]) >= 2 and all(re.search(r"D1 \d", l["why"]) for l in p["losers"])   # 규칙 번호로 진다
    assert all({"title", "link"} <= set(d) for d in p["docs"])


def test_example_agent_fields_are_portal_fields_within_limits():
    a = json.loads(read(EX / "agent" / "agent.json"))
    from procsvc.agent_authoring import LIMITS
    assert set(a) - {"_comment"} == {"name", "goal", "role", "persona", "tools", "skills"}
    for k in ("name", "goal", "role", "persona"):
        assert 0 < len(a[k]) <= LIMITS[k], k
    assert "승인 전에는 조회 · 계산 · 요약만" in a["goal"]
    assert a["skills"] == [split_frontmatter(read(EX / "agent" / "SKILL.md"))[0]["name"]]
    assert "목표 문장 틀" in read(KIT / "agent" / "goal.md")


# ---------------------------------------------------------------- T7 · T8 그림: 유효한 BPMN 2.0 + DI, 가져오기 파서로 읽힘
def _di_complete(xml: str) -> list[str]:
    root = ET.fromstring(xml)
    proc = root.find("bpmn:process", NS)
    elems = {e.get("id") for e in proc if e.get("id") and not e.tag.endswith("laneSet")}
    elems |= {l.get("id") for l in proc.iter(f"{{{NS['bpmn']}}}lane")}
    elems |= {p.get("id") for p in root.iter(f"{{{NS['bpmn']}}}participant")}
    drawn = {s.get("bpmnElement") for s in root.iter(f"{{{NS['bpmndi']}}}BPMNShape")} | \
            {s.get("bpmnElement") for s in root.iter(f"{{{NS['bpmndi']}}}BPMNEdge")}
    missing = sorted(elems - drawn)
    ghost = sorted(drawn - elems)
    return [f"그림 없음 {m}" for m in missing] + [f"없는 요소의 그림 {g}" for g in ghost]


def test_blank_flow_template_has_three_lanes_unnamed_tasks_and_full_di():
    xml = read(KIT / "flow.bpmn")
    assert _di_complete(xml) == []
    p = B.parse_bpmn(xml)
    assert p["problems"] == []
    assert [l["name"] for l in p["lanes"]] == ["담당자", "에이전트", "시스템"]
    assert len(p["starts"]) == 1 and len(p["ends"]) == 1 and len(p["gateways"]) == 1
    assert p["tasks"] and all(t["name"] == "" for t in p["tasks"])                    # task 이름은 학생이 채운다
    assert sum(t["bpmn_type"] == "userTask" for t in p["tasks"]) == 1                # 승인 자리 하나


def test_blank_flow_template_imports_cleanly_once_parts_are_chosen():
    """그림 자체에 끊긴 선 · 끝 닫힘 문제가 없는지: 효과 없는 부품으로 채우면 사전 검사 + 등록 검사 문제 0."""
    p = B.parse_bpmn(read(KIT / "flow.bpmn"))
    cat = B.catalog(BASE_DEF, USERS)
    m, _ = B.merge_mapping(p, None, cat)
    empty = B.check(p, m, {"catalog": cat, "definition_id": "blank", "version": "1", "file_name": "flow.bpmn", "xml_sha256": "x"})
    assert {x["field"] for x in empty["problems"]} <= {"part", "condition"}           # 그림 문제 없음, 고를 것만 남음
    t = {x["id"]: x for x in p["tasks"]}
    m["start"] = {"kind": "human", "fields": [{"key": "case_id", "text": "요청 번호"}]}
    m["tasks"] = {"Activity_agent": {"part": "agent", "agent": AGENT_ID, "instruction": "후보를 낸다", "inputs": ["case_id"],
                                     "outputs": [{"key": "proposal", "type": "object"}]},
                  "Activity_approve": {"part": "human", "role": "회의 주관자", "inputs": ["proposal"],
                                       "fields": [{"key": "choice", "type": "select", "items": ["1안", "2안"]}]},
                  "Activity_do": {"part": "svc:wait", "config": {"duration": "PT1H"}},
                  "Activity_check": {"part": "svc:wait", "config": {"duration": "PT1H"}},
                  "Activity_report_ok": {"part": "svc:report", "config": {"outcome": "정상"}},
                  "Activity_report_ng": {"part": "svc:report", "config": {"outcome": "미달"}}}
    assert set(m["tasks"]) == set(t)
    m["flows"] = {"Flow_yes": {"var": "choice", "op": "==", "value": "1안"}, "Flow_no": {"default": True}}
    r = B.check(p, m, {"catalog": cat, "definition_id": "blank", "version": "1", "file_name": "flow.bpmn", "xml_sha256": "x"})
    assert r["ok"], r["problems"]


def test_example_flow_reads_with_lanes_timer_and_branch():
    xml = read(EX / "flow.bpmn")
    assert _di_complete(xml) == []
    p = B.parse_bpmn(xml)
    assert p["problems"] == []
    assert [l["name"] for l in p["lanes"]] == ["회의 주관자", "회의 준비 에이전트", "시스템"]
    assert len(p["tasks"]) == 8 and [g["name"] for g in p["gateways"]] == ["필수 참석자 전원 수락?"]
    (timer,) = p["boundaries"]
    assert timer["attached_to"] == "Activity_approve" and timer["timer"] == "PT4H" and timer["interrupting"] is False


def _example_check():
    p = B.parse_bpmn(read(EX / "flow.bpmn"))
    m = json.loads(read(EX / "mapping.json"))
    m.pop("_comment")
    assert m["tasks"]["Activity_propose"]["agent"] == "<내 에이전트 id>"            # 출발본에는 지어낸 id 가 없다
    m["tasks"]["Activity_propose"]["agent"] = AGENT_ID
    return p, m, B.check(p, m, {"catalog": B.catalog(BASE_DEF, USERS), "definition_id": "qbr_prep", "version": "1",
                                "file_name": "flow.bpmn", "xml_sha256": "x"})


# G1 · G3 합친 뒤 가져오기 검사: 이 시험은 지금 파서가 거절하는 사유를 그대로 적는다. G1(human:approve) · G3(extract)이
# 들어오면 이 기대값이 깨진다 — 그때 "거절 0"으로 바꾼다. 다른 사유(그림 · 값 연결 · 타이머 · 보고 부품)는 지금도 0 이어야 한다.
EXPECTED_BEFORE_G1_G3 = sorted([
    ("Activity_approve", "part", "고른 부품이 부품 목록에 없습니다"),                         # G1 일반 승인 부품 없음
    ("Activity_invite", "inputs", "받을 값 approved_option 을(를) 앞 단계(또는 시작)가 내지 않습니다"),   # G1 이 내는 값
    ("Activity_check", "inputs", "받을 값 event_id 을(를) 앞 단계(또는 시작)가 내지 않습니다"),          # G3 extract
    ("Flow_yes", "condition", "조건 값 all_required_accepted 을(를) 분기 앞 단계가 내지 않습니다"),       # G3 extract
    ("Activity_invite", "part", "앞 경로에 사람 승인"),                                       # G1 승인이 없어 효과 부품 거절
    ("Activity_check", "part", "앞 경로에 사람 승인"),                                        # G3 effect:false 전까지 읽기도 효과로 셈
])


def test_example_flow_is_rejected_only_for_the_missing_g1_g3_parts():
    _, _, r = _example_check()
    got = sorted(((x.get("where") or {}).get("id"), x["field"], x["reason"]) for x in r["problems"])
    assert not r["ok"] and len(got) == len(EXPECTED_BEFORE_G1_G3)
    for (gid, gfield, greason), (eid, efield, ephrase) in zip(got, EXPECTED_BEFORE_G1_G3):
        assert (gid, gfield) == (eid, efield) and ephrase in greason, (gid, gfield, greason)


def test_example_mapping_uses_design_names_for_g1_g3_and_valid_current_parts():
    m = json.loads(read(EX / "mapping.json"))
    assert m["tasks"]["Activity_approve"]["part"] == "human:approve"
    assert m["tasks"]["Activity_check"]["config"]["effect"] is False and "extract" in m["tasks"]["Activity_check"]["config"]
    assert "G1 · G3 합친 뒤 가져오기 검사" in m["_comment"] and "G1 · G3 합친 뒤 가져오기 검사" in read(EX / "README.md")
    outcomes = {t["config"]["outcome"] for t in m["tasks"].values() if t["part"] == "svc:report"}
    assert outcomes == {"정상", "미달", "승인 지연"}                                       # 확정 · 미확정 · 승인 지연 가지


# ---------------------------------------------------------------- T8 스키마 · 지식 · DDL
def _graph():
    g = json.loads(read(EX / "graph.json"))
    labels = {n["props"]["id"]: n["labels"] for n in g["nodes"]}
    rels = [dict(r, la=labels[r["a"]], lb=labels[r["b"]]) for r in g["rels"]]
    return g["nodes"], rels


def test_example_schema_passes_check_extra_and_v2_is_untouched():
    base = ov.load_schema()
    before = copy.deepcopy(base)
    extra = ov.load_extra(EX / "schema.json")
    assert ov.check_extra(base, extra) == [] and ov.main(["check-extra", "--extra", str(EX / "schema.json")]) == 0
    assert ov.load_schema() == before
    assert {c["name"] for c in extra["classes"]} == {"Meeting", "Customer", "Attendee", "AgendaItem", "Document", "PrepGuide"}


def test_example_graph_passes_the_namespace_check_with_no_value_nodes():
    nodes, rels = _graph()
    extra = ov.load_extra(EX / "schema.json")
    assert ov.validate_ns(nodes, rels, ov.load_schema(), extra) == []
    assert all(n["props"]["ns"] == "demo" and n["props"]["id"].startswith("demo:") for n in nodes)
    rules = [n["props"] for n in nodes if "Rule" in n["labels"]]
    assert sorted(r["effect"] for r in rules).count("EXCLUDE") == 5 and any(r["effect"] == "PENALTY" for r in rules)
    bound = [n["props"] for n in nodes if "InputData" in n["labels"] and n["props"].get("table")]
    assert {(b["table"], b["column"]) for b in bound} == {("meeting_request", "due_by"), ("attendee", "email"), ("room", "capacity")}
    assert not any(k in n["props"] for n in nodes for k in ("value", "rows"))          # 지식에 값을 넣지 않는다


def test_example_ddl_follows_t3_format_and_matches_the_graph_bindings():
    sql = read(EX / "table.sql")
    t3 = read(KIT / "table.sql")
    for must in ("create schema if not exists stu_", "nosuperuser nocreaterole nocreatedb nobypassrls", "default_transaction_read_only = on",
                 "alter default privileges in schema stu_", "on conflict", "grant select on all tables in schema stu_", "drop schema stu_"):
        assert must in t3 and must in sql, must
    assert "password 'change-me'" in sql                                             # T4 서버가 자리표시자 암호를 거절한다
    tables = dict(re.findall(r"create table if not exists stu_demo\.(\w+) \((.*?)\n\);", sql, re.S))
    assert set(tables) == {"meeting_request", "attendee", "room"}
    for b in [n["props"] for n in _graph()[0] if "InputData" in n["labels"] and n["props"].get("table")]:
        assert b["schema"] == "stu_demo" and re.search(rf"^\s*{b['column']} ", tables[b["table"]], re.M), b
        assert re.search(rf"^\s*{b['assetColumn']} ", tables[b["table"]], re.M), b
    assert "(가상)" in sql and "@example.com" in sql and "capacity" in sql and "4, 'example-room-a" in sql   # 4인실 지는 가지
