"""G3 (전체 과정 랩업 — capstone-lab.md 3.6 · 5.2): MCP 결과를 분기 값으로.

svc:mcp-call 설정 extract {값 이름: {path, type}} — 결과 JSON 에서 값을 꺼내 outputData 로 함께 낸다. 사전 검사는 자료형 선언과
분기 조건이 그 값을 쓰는 방식(연결 · 자료형)을 본다. effect: false 는 읽기 확인 — 효과로 세지 않지만, 부르기 직전 읽기 판정
(mcp_check.call · read_only_verdict)을 통과한 도구만 부른다. 실패 가지: JSON 아님 · 잘림 · 경로 없음 · 자료형 불일치 · 쓰기 도구.
"""
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from procsvc import effect_parts, engine, instance_mode, instances
from test_c2_execution import imported, xml
from test_instance_mode import NOW, world  # noqa: F401  (world 는 fixture)

FAKE = str(Path(__file__).resolve().parent / "fixtures" / "mcp_fake_server.py")

# 3.6 의 뒤쪽: 응답 확인(시스템 · 읽기) → ◇ 필수 참석자 전원 수락? → 결과 보고 확정 | 미확정
FLOW = xml("""
  <bpmn:startEvent id="Start" name="회의 요청 접수"/>
  <bpmn:serviceTask id="T_check" name="참석 응답 확인"/>
  <bpmn:exclusiveGateway id="G_all" name="필수 참석자 전원 수락?"/>
  <bpmn:serviceTask id="R_ok" name="결과 보고: 확정"/>
  <bpmn:serviceTask id="R_no" name="결과 보고: 미확정"/>
  <bpmn:endEvent id="E_end" name="끝"/>
  <bpmn:sequenceFlow id="F1" sourceRef="Start" targetRef="T_check"/>
  <bpmn:sequenceFlow id="F2" sourceRef="T_check" targetRef="G_all"/>
  <bpmn:sequenceFlow id="F_yes" name="예" sourceRef="G_all" targetRef="R_ok"/>
  <bpmn:sequenceFlow id="F_no" name="아니오" sourceRef="G_all" targetRef="R_no"/>
  <bpmn:sequenceFlow id="F3" sourceRef="R_ok" targetRef="E_end"/>
  <bpmn:sequenceFlow id="F4" sourceRef="R_no" targetRef="E_end"/>""", "Process_qbr")

EXTRACT = {"all_required_accepted": {"path": "attendees_ok", "type": "Boolean"},
           "accepted_count": {"path": "attendees.0.count", "type": "Number"}}


def check_config(**over):
    cfg = {"server": "gcal", "tool": "get_event", "arguments": {"event_id": "{request_id}"}, "effect": False, "extract": deepcopy(EXTRACT)}
    cfg.update(over)
    return cfg


def mapping(cfg=None, cond=None):
    return {"name": "회의 응답 확인 (시험)", "start": {"kind": "human", "fields": [{"key": "request_id", "text": "회의 요청 번호", "type": "text"}]},
            "lanes": {},
            "tasks": {"T_check": {"part": "svc:mcp-call", "config": cfg or check_config()},
                      "R_ok": {"part": "svc:report", "config": {"outcome": "정상", "title": "{request_id} 회의 확정", "summary": "수락 {accepted_count}명"}},
                      "R_no": {"part": "svc:report", "config": {"outcome": "미달", "title": "{request_id} 회의 미확정"}}},
            "flows": {"F_yes": cond or {"var": "all_required_accepted", "op": "==", "value": True}, "F_no": {"default": True}}}


def problems_at(r, node, field):
    return [p["reason"] for p in r["problems"] if p["where"]["id"] == node and p["field"] == field]


# ================================================================ 사전 검사
def test_extracted_values_are_outputs_with_their_declared_types_and_feed_the_branch(world):
    _, r = imported(world, FLOW, mapping(), "qbr")
    assert r["ok"], r["problems"]
    d = r["definition"]
    act = next(a for a in d["activities"] if a["id"] == "T_check")
    assert act["outputData"] == ["mcp_receipt", "all_required_accepted", "accepted_count"]
    assert act["checkpoints"] == [effect_parts.READ_CHECKPOINT]
    types = {x["name"]: x["type"] for x in d["data"]}
    assert types["all_required_accepted"] == "Boolean" and types["accepted_count"] == "Number"
    assert {"value": "all_required_accepted", "from": "T_check"} in r["available"]["G_all"]
    assert next(s for s in d["sequences"] if s["id"] == "F_yes")["condition"] == "all_required_accepted == True"


@pytest.mark.parametrize("cond,phrase", [
    ({"var": "all_required_accepted", "op": ">", "value": 3}, "'>' 비교를 쓸 수 없습니다"),
    ({"var": "all_required_accepted", "op": "==", "value": "예"}, "자료형이 다릅니다"),
    ({"var": "accepted_count", "op": "==", "value": "여섯"}, "자료형이 다릅니다"),
    ({"text": "accepted_count"}, "참/거짓 값이 아니라"),
])
def test_a_branch_that_uses_an_extracted_value_against_its_type_is_refused(world, cond, phrase):
    _, r = imported(world, FLOW, mapping(cond=cond), "qbr")
    assert not r["ok"] and any(phrase in x for x in problems_at(r, "F_yes", "condition")), r["problems"]


def test_a_branch_on_a_value_nobody_extracts_is_refused(world):
    cfg = check_config(extract={"accepted_count": EXTRACT["accepted_count"]})
    _, r = imported(world, FLOW, mapping(cfg), "qbr")
    assert not r["ok"] and any("all_required_accepted" in x and "내지 않습니다" in x for x in problems_at(r, "F_yes", "condition"))


@pytest.mark.parametrize("extract,phrase", [
    ({"ok": {"path": "a b", "type": "Boolean"}}, "JSON 경로"),
    ({"ok": {"path": "a", "type": "Date"}}, "자료형은"),
    ({"ok": "attendees_ok"}, "{path, type}"),
    ({"approved_by": {"path": "who", "type": "Text"}}, "서버 승인 경로만"),
    ({"decision_id": {"path": "id", "type": "Text"}}, "서버 승인 경로만"),
    ({"mcp_receipt": {"path": "id", "type": "Text"}}, "쓸 수 없습니다"),
])
def test_bad_extract_config_is_reported_at_the_task(world, extract, phrase):
    _, r = imported(world, FLOW, mapping(check_config(extract=extract), cond={"default": True}) | {"flows": {"F_yes": {"default": True}, "F_no": {"var": "request_id", "op": "==", "value": "x"}}}, "qbr")
    assert not r["ok"] and any(phrase in x for x in problems_at(r, "T_check", "config")), r["problems"]


@pytest.mark.parametrize("task,part,config,bad", [
    ("T_check", "svc:mcp-call", check_config(extarct={"x": {"path": "a", "type": "Text"}}), "extarct"),
    ("R_ok", "svc:report", {"outcome": "정상", "title": "t", "sumary": "오타"}, "sumary"),
])
def test_unknown_config_keys_are_refused_with_the_task_and_the_key(world, task, part, config, bad):
    """설정 칸 오타가 조용히 무시되면 설정한 줄 알고 돌린다 — 등록 전에 task · 칸 이름과 함께 거절한다."""
    m = mapping()
    m["tasks"][task] = {"part": part, "config": config}
    _, r = imported(world, FLOW, m, "qbr")
    assert not r["ok"] and any(f"모르는 설정 칸 {bad}" in x for x in problems_at(r, task, "config")), r["problems"]


def test_baseline_flows_and_definitions_use_only_known_config_keys(world):
    """기준 흐름 A · B · C(scripts/c3_flows.py)와 기준 정의 파일 전부가 새 검사에 걸리지 않는다."""
    import importlib.util
    import json
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("c3_flows", root / "scripts" / "c3_flows.py")
    flows = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(flows)
    from procsvc import bpmn_import as B
    from test_c3_assembly import AGENTS
    rt = world["rt"]
    cat = B.catalog(rt.definition_for({"proc_def_id": rt.defn.id, "proc_def_version": rt.base_version, "tenant_id": rt.tenant_id}).raw, AGENTS)
    for did, (_, src, m) in flows.FLOWS.items():
        r = B.check(B.parse_bpmn(src), deepcopy(m), {"catalog": cat, "definition_id": did, "version": "1", "file_name": did, "xml_sha256": "x"})
        assert r["ok"], (did, r["problems"])
    for f in sorted((root / "it" / "process" / "definitions").glob("*.json")):
        for act in json.loads(f.read_text(encoding="utf-8")).get("activities") or []:
            effect_parts.validate(act)


def test_effect_flag_must_be_a_boolean(world):
    _, r = imported(world, FLOW, mapping(check_config(effect="no")), "qbr")
    assert not r["ok"] and any("effect 는 true/false" in x for x in problems_at(r, "T_check", "config"))


def test_without_the_read_flag_the_same_call_is_an_effect_and_needs_an_approval_before_it(world):
    cfg = check_config()
    del cfg["effect"]
    _, r = imported(world, FLOW, mapping(cfg), "qbr")
    assert not r["ok"] and any("사람 승인" in x for x in problems_at(r, "T_check", "part"))


# ================================================================ 실행
class Calls:
    def __init__(self, rt, text, *, truncated=False):
        self.reads, self.effects, self.text, self.truncated = [], [], text, truncated
        rt.hooks.mcp_read = self.read
        rt.hooks.mcp_call = self.effect

    def read(self, server, tool, arguments):
        self.reads.append((server, tool, deepcopy(arguments)))
        return {"status": "ok", "result": {"is_error": False, "text": self.text, "truncated": self.truncated, "size_chars": 30000}}

    def effect(self, server, tool, arguments, key):
        self.effects.append((server, tool))
        return {"status": "ok", "result": {"is_error": False, "text": "{}"}}


def run(world, text, **kw):
    _, r = imported(world, FLOW, mapping(), "qbr")
    assert r["ok"], r["problems"]
    rt = world["rt"]
    rt.register_definition(r["definition"])
    rt.deploy_definition("qbr", "1", "tester", "G3 시험")
    calls = Calls(rt, text, **kw)
    inst = rt.start_definition("qbr", "1", "start:QBR-1", values={"request_id": "QBR-2026-Q4-01"}, now=NOW)
    for _ in range(3):
        rt.poll_once(now=NOW)
    return rt, rt.repo.get_instance(inst["proc_inst_id"]), calls


def rows(rt, inst, activity):
    return [w for w in rt.repo.list_workitems(proc_inst_id=inst["proc_inst_id"], limit=None) if w["activity_id"] == activity]


def ran(rt, inst, activity) -> bool:
    return any(w["status"] == "DONE" for w in rows(rt, inst, activity))


def events(rt, inst, job):
    return [e for e in rt.repo.list_events(inst["proc_inst_id"]) if e.get("job_id") == job]


@pytest.mark.parametrize("accepted,branch", [(True, "R_ok"), (False, "R_no")])
def test_read_check_extracts_values_and_the_branch_follows_them(world, accepted, branch):
    rt, inst, calls = run(world, f'{{"attendees_ok": {str(accepted).lower()}, "attendees": [{{"count": 6}}]}}')
    v = engine.variables(inst)
    assert v["all_required_accepted"] is accepted and v["accepted_count"] == 6
    assert calls.reads == [("gcal", "get_event", {"event_id": "QBR-2026-Q4-01"})] and calls.effects == []   # 읽기 경로만, 승인 없이
    assert ran(rt, inst, branch) and not ran(rt, inst, "R_no" if branch == "R_ok" else "R_ok") and inst["status"] == "COMPLETED"
    out = rows(rt, inst, "T_check")[0]["output"]
    assert out["all_required_accepted"] is accepted and out["mcp_receipt"]["tool"] == "get_event"
    ev = events(rt, inst, "MCP_RESULT_VALUES")                         # 처리 기록: 무엇을 어느 경로에서 꺼냈는지
    assert len(ev) == 1 and ev[0]["data"]["values"] == {"all_required_accepted": accepted, "accepted_count": 6}
    assert "(경로 attendees_ok)" in ev[0]["data"]["content"]
    assert [e["data"]["name"] for e in events(rt, inst, "MCP_READ_CALL")] == ["읽기 확인 MCP 호출", "읽기 확인 MCP 호출 결과"]


@pytest.mark.parametrize("text,kw,phrase", [
    ("참석 6명 중 6명 수락", {}, "JSON 이 아니라"),
    ('{"attendees": [{"count": 6}]}', {}, "경로 'attendees_ok'"),
    ('{"attendees_ok": "true", "attendees": [{"count": 6}]}', {}, '값 "true" 은(는) Boolean 가 아닙니다'),
    ('{"attendees_ok": true, "attendees": [{"count": true}]}', {}, "Number 가 아닙니다"),
    ('{"attendees_ok": tr', {"truncated": True}, "잘렸습니다"),
])
def test_unreadable_results_fail_the_task_with_where_and_what_and_pass_no_value(world, text, kw, phrase):
    rt, inst, calls = run(world, text, **kw)
    wi = rows(rt, inst, "T_check")[0]
    assert wi["status"] == "PENDING" and "참석 응답 확인" in wi["log"] and "gcal.get_event" in wi["log"] and phrase in wi["log"]
    assert "결과 앞부분" in wi["log"] and text[:10] in wi["log"]
    v = engine.variables(inst)
    assert "all_required_accepted" not in v and "accepted_count" not in v
    assert not ran(rt, inst, "R_ok") and not ran(rt, inst, "R_no") and inst["status"] == "RUNNING"
    assert len(calls.reads) == instances.MAX_RETRIES                   # 정해진 재시도 뒤 멈춘다(무한 반복 없음)
    errors = [e for e in rt.repo.list_events(inst["proc_inst_id"]) if e["event_type"] == "error"]
    assert errors and phrase in errors[-1]["data"]["raw_error"]


# ================================================================ 읽기 판정 (instance_mode.mcp_read → 실제 mcp_check.call · 가짜 MCP 서버)
def run_real(world, monkeypatch, tool, arguments):
    monkeypatch.setitem(instance_mode.EFFECT_MCP_SERVERS, "fake", {"command": sys.executable, "args": [FAKE]})
    _, r = imported(world, FLOW, mapping(check_config(server="fake", tool=tool, arguments=arguments,
                                                      extract={"all_required_accepted": {"path": "ok", "type": "Boolean"}})), "qbr")
    assert r["ok"], r["problems"]
    rt = world["rt"]
    rt.register_definition(r["definition"])
    rt.deploy_definition("qbr", "1", "tester", "G3 시험")
    rt.hooks.mcp_call = lambda *a: pytest.fail("읽기 확인이 쓰기 경로를 불렀습니다")
    inst = rt.start_definition("qbr", "1", "start:QBR-W", values={"request_id": "QBR-1"}, now=NOW)
    rt.poll_once(now=NOW)
    return rt, rt.repo.get_instance(inst["proc_inst_id"])


@pytest.mark.parametrize("tool,phrase", [("submit_note", "readOnlyHint=false"), ("delete_rows", "'delete'"), ("greet", "표시하지 않았습니다")])
def test_a_write_tool_marked_as_a_read_check_is_refused_before_it_is_called(world, monkeypatch, tool, phrase):
    rt, inst = run_real(world, monkeypatch, tool, {"text": "{request_id}"} if tool == "submit_note" else {})
    wi = rows(rt, inst, "T_check")[0]
    assert wi["status"] == "SUBMITTED" and phrase in wi["log"], wi["log"]          # 실패 · 재시도 대기(사유 보존)
    errors = [e for e in rt.repo.list_events(inst["proc_inst_id"]) if e["event_type"] == "error"]
    assert errors and phrase in errors[-1]["data"]["raw_error"] and errors[-1]["data"]["service_result"]["tool"] == tool
    assert "all_required_accepted" not in engine.variables(inst)


def test_a_real_read_tool_passes_the_verdict_and_its_json_reaches_the_case(world, monkeypatch):
    rt, inst = run_real(world, monkeypatch, "add", {"a": 2, "b": 3})
    wi = rows(rt, inst, "T_check")[0]
    assert wi["status"] == "SUBMITTED" and "경로 'ok'" in wi["log"] and '"sum": 5' in wi["log"]    # 불렸고(읽기), 결과에 ok 칸이 없어 실패
