"""G8 (전체 과정 랩업 — docs/handoff/verification/2026-10-09/capstone-lab.md 5.2, 선택): 학생 흐름을 학생 이름 공간 그래프에 투영.

흐름 정의(판본 JSON) → Process · Event · Task · Gateway · SEQUENCE_FLOW · PERFORMED_BY 를 v2 클래스 그대로, ns · id 접두어를 붙여 만든다.
그래프 없이 본다: 투영 결과가 v2 + ns 규칙 검사(ontology_v2.validate_ns)를 통과하는가, 레인 역할을 수업 기준 Role 에 잇거나 학생 Role 로 만드는가,
적재 문장이 값을 문장에 붙이지 않고 매개변수로만 넘기는가, 다시 돌리면 그 정의의 이전 투영만 지우는가.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("project_student_flow", ROOT / "scripts" / "project_student_flow.py")
pf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pf)

FLOW = {
    "processDefinitionId": "meeting_prep", "processDefinitionName": "분기 고객 리뷰 회의 준비", "version": "1",
    "roles": [{"name": "회의 주관자", "endpoint": "role:s01-organizer"}, {"name": "회의 준비 에이전트", "endpoint": "sys:agent"},
              {"name": "운전원", "endpoint": "role:operator"}],
    "events": [{"id": "ev:start", "type": "startEvent", "name": "분기 리뷰 요청"},
               {"id": "ev:timeout", "type": "boundaryEvent", "eventDefinition": "timer", "timer": "PT1H", "attachedTo": "task:approve", "name": "승인 시간 초과"},
               {"id": "ev:done", "type": "endEvent", "name": "회의 확정"}, {"id": "ev:fail", "type": "endEvent", "name": "미확정 보고"}],
    "activities": [{"id": "task:propose", "type": "userTask", "name": "시간 후보 제안", "role": "회의 준비 에이전트", "agentMode": "COMPLETE", "orchestration": "cliagents"},
                   {"id": "task:approve", "type": "userTask", "name": "안 고르기", "role": "회의 주관자"},
                   {"id": "task:invite", "type": "serviceTask", "name": "초대 보내기", "tool": "svc:mcp-call"},
                   {"id": "task:watch", "type": "userTask", "name": "현장 확인", "role": "운전원"}],
    "gateways": [{"id": "gw:all", "type": "exclusiveGateway", "name": "필수 참석자 전원 수락?"}],
    "sequences": [{"id": "f1", "source": "ev:start", "target": "task:propose"}, {"id": "f2", "source": "task:propose", "target": "task:approve"},
                  {"id": "f3", "source": "task:approve", "target": "task:invite"}, {"id": "f4", "source": "task:invite", "target": "gw:all"},
                  {"id": "f5", "source": "gw:all", "target": "ev:done", "condition": {"field": "all_required_accepted", "op": "==", "value": True}},
                  {"id": "f6", "source": "gw:all", "target": "task:watch", "condition": "미달"}, {"id": "f7", "source": "task:watch", "target": "ev:fail"}],
}


def test_projection_uses_v2_classes_with_the_namespace_and_passes_the_ns_check():
    proj = pf.project(FLOW, "s01")
    assert proj["process"] == {"id": "s01:proc:meeting_prep", "name": "분기 고객 리뷰 회의 준비", "isExecutable": True, "ns": "s01"}
    by = {n["props"]["element_id"]: n for n in proj["nodes"]}
    assert by["task:propose"]["props"]["taskType"] == "user" and by["task:propose"]["props"]["agentMode"] == "COMPLETE"
    assert by["task:invite"]["props"]["taskType"] == "service" and by["gw:all"]["props"]["gatewayType"] == "exclusive"
    assert by["ev:timeout"]["props"]["position"] == "boundary" and by["ev:timeout"]["attached_to"] == "s01:task:approve"
    assert all(n["props"]["ns"] == "s01" and n["props"]["id"].startswith("s01:") for n in proj["nodes"])
    cond = {s["props"]["id"]: s["props"].get("condition") for s in proj["sequences"]}
    assert json.loads(cond["s01:f5"]) == {"field": "all_required_accepted", "op": "==", "value": True} and cond["s01:f6"] == "미달"
    assert proj["problems"] == [] and pf.check(proj) == []
    extra = json.loads((ROOT / "students" / "_template" / "schema.json").read_text(encoding="utf-8"))
    assert pf.check(proj, extra) == []                                    # 학생 스키마와 함께 검사해도 통과


def test_lane_roles_bridge_to_base_roles_or_become_student_roles():
    proj = pf.project(FLOW, "s01")
    nodes, rels = pf.records(proj, base_roles={"role:operator"}, base_systems={"sys:agent"})
    performed = {r["a"]: r["b"] for r in rels if r["type"] == "PERFORMED_BY"}
    assert performed == {"s01:task:propose": "sys:agent", "s01:task:approve": "s01:role:s01-organizer", "s01:task:watch": "role:operator"}
    own = [n for n in nodes if n["labels"] == ["Role"]]
    assert own == [{"labels": ["Role"], "props": {"id": "s01:role:s01-organizer", "name": "회의 주관자", "level": 1, "ns": "s01"}}]
    assert "s01:task:invite" not in performed                               # 레인 없는 시스템 task 는 수행자 없음


def test_load_statements_are_parameterised_and_wipe_only_this_definition():
    proj = pf.project(FLOW, "s01")
    batches = pf.cypher_batches(proj)
    assert batches[0] == (pf.WIPE[0], {"ns": "s01", "def": "meeting_prep", "src": "student_flow"})
    assert batches[1] == (pf.WIPE[1], {"pid": "s01:proc:meeting_prep", "ns": "s01"})
    for stmt, _ in batches:
        assert "s01" not in stmt and "meeting" not in stmt and "회의" not in stmt          # 값은 문장에 붙이지 않는다
    labels = [stmt.split("SET n:")[1].split(",")[0] for stmt, _ in batches if "SET n:" in stmt]
    assert labels == ["Event", "Task", "Gateway"]
    assert any("WHERE base.ns IS NULL" in stmt for stmt, _ in batches)                    # 수업 기준 Role 이 있으면 그 노드에


def test_unsupported_elements_are_reported_not_dropped_silently():
    bad = json.loads(json.dumps(FLOW))
    bad["gateways"].append({"id": "gw:or", "type": "inclusiveGateway"})
    bad["events"].append({"id": "ev:mid", "type": "intermediateThrowEvent"})
    bad["sequences"].append({"id": "f9", "source": "gw:or", "target": "ev:done"})
    bad["activities"].append({"id": "task:x", "type": "userTask", "role": "없는 레인"})
    probs = "\n".join(pf.check(pf.project(bad, "s01")))
    for phrase in ("gateway gw:or", "event ev:mid", "sequence f9", "task task:x: 레인(역할) '없는 레인'"):
        assert phrase in probs, phrase


def test_cli_check_reads_a_registered_definition_row(tmp_path):
    path = tmp_path / "def.json"
    path.write_text(json.dumps({"id": "meeting_prep", "definition": FLOW}, ensure_ascii=False), encoding="utf-8")
    assert pf.main(["--definition", str(path), "--ns", "s01", "--check"]) == 0
    with pytest.raises(ValueError, match="ns"):
        pf.project(FLOW, "S 01")
