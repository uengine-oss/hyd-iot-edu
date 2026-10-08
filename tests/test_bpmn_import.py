"""B3: bpmn.io .bpmn 가져오기 → 부품 · 담당 매핑 → 사전 검사 → 판본 등록 · 그림 다시 받기 · 기준으로 되돌리기.

기준 흐름(anomaly_response 현재 운영판)을 bpmn.io 형식으로 다시 그린 시험용 그림(tests/fixtures/bpmn/anomaly_response_redraw.bpmn,
손으로 쓴 의미 부분 + 배치 좌표)을 가져와 부품을 고르면 기준 정의와 구조가 같은 정의가 되는지, 그리고 일부러 깨뜨린 그림
(승인 앞 설비 명령 · 끊긴 선 · 조건 누락 · 빠진 값 · 지원하지 않는 요소)이 칸 위치와 함께 거절되는지 본다."""
import json
import shutil
import subprocess
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from procsvc import bpmn_import as B, engine, flows_api, instances, procdb
from procsvc.definition_registry import validate_definition

ROOT = Path(__file__).resolve().parents[1]
BASE = json.loads((ROOT / "it/process/definitions/anomaly_response_v22.json").read_text(encoding="utf-8"))
REDRAW = (ROOT / "tests/fixtures/bpmn/anomaly_response_redraw.bpmn").read_text(encoding="utf-8")
BASE_BY_NAME = {a["name"]: a["id"] for a in BASE["activities"]}       # 학생이 그림의 이름을 보고 부품을 고르는 것과 같다
NS = 'xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"'


def small(body: str, pid: str = "Process_small") -> str:
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<bpmn:definitions {NS} id="D1"><bpmn:process id="{pid}" name="작은 흐름">{body}</bpmn:process></bpmn:definitions>'


LOOP = small("""
  <bpmn:startEvent id="StartEvent_1" name="측정 요청"/>
  <bpmn:userTask id="Activity_measure" name="오일 측정"/>
  <bpmn:exclusiveGateway id="Gateway_ok" name="기준 안?"/>
  <bpmn:endEvent id="Event_done" name="끝"/>
  <bpmn:sequenceFlow id="Flow_1" sourceRef="StartEvent_1" targetRef="Activity_measure"/>
  <bpmn:sequenceFlow id="Flow_2" sourceRef="Activity_measure" targetRef="Gateway_ok"/>
  <bpmn:sequenceFlow id="Flow_back" name="다시 측정" sourceRef="Gateway_ok" targetRef="Activity_measure"/>
  <bpmn:sequenceFlow id="Flow_end" sourceRef="Gateway_ok" targetRef="Event_done"/>""", "Process_loop")

HUMAN_START = small("""
  <bpmn:laneSet id="LS"><bpmn:lane id="Lane_m" name="정비관리자"><bpmn:flowNodeRef>Activity_review</bpmn:flowNodeRef></bpmn:lane>
    <bpmn:lane id="Lane_a" name="AI 에이전트"><bpmn:flowNodeRef>Activity_summary</bpmn:flowNodeRef></bpmn:lane></bpmn:laneSet>
  <bpmn:startEvent id="StartEvent_1" name="오일 분석 입력"/>
  <bpmn:task id="Activity_summary" name="이탈 요약"/>
  <bpmn:userTask id="Activity_review" name="정비 검토"/>
  <bpmn:endEvent id="Event_done" name="끝"/>
  <bpmn:sequenceFlow id="Flow_1" sourceRef="StartEvent_1" targetRef="Activity_summary"/>
  <bpmn:sequenceFlow id="Flow_2" sourceRef="Activity_summary" targetRef="Activity_review"/>
  <bpmn:sequenceFlow id="Flow_3" sourceRef="Activity_review" targetRef="Event_done"/>""", "Process_oil")


def redraw_mapping(parsed) -> dict:
    m, _ = B.merge_mapping(parsed, None, B.catalog(BASE, []))
    for t in parsed["tasks"]:
        m["tasks"][t["id"]] = {"part": BASE_BY_NAME[t["name"]]}
    flows = {f["name"]: f["id"] for f in parsed["flows"] if f["name"]}
    m["flows"] = {flows["선택 스킬 kind == control"]: {"var": "chosen_skill_kind", "op": "==", "value": "control"},
                  flows["선택 스킬 kind == work_order"]: {"var": "chosen_skill_kind", "op": "==", "value": "work_order"},
                  flows["TS1 < 55 and 경보 해제"]: {"var": "recovered", "op": "==", "value": True},
                  flows["미회복"]: {"var": "recovered", "op": "!=", "value": True}}
    return m


def run_check(xml, mapping=None, did="redraw"):
    parsed = B.parse_bpmn(xml)
    cat = B.catalog(BASE, [])
    mapping = redraw_mapping(parsed) if mapping is None else mapping
    return parsed, B.check(parsed, mapping, {"catalog": cat, "definition_id": did, "version": "1", "file_name": "t.bpmn", "xml_sha256": "x"})


def reasons(result, node_id=None, field=None):
    return [p["reason"] for p in result["problems"]
            if (node_id is None or (p.get("where") or {}).get("id") == node_id) and (field is None or p["field"] == field)]


# ---------------------------------------------------------------- 변환: 다시 그린 기준 흐름 = 기준 정의 (구조)
def test_redraw_of_base_flow_converts_to_the_same_structure():
    parsed, r = run_check(REDRAW)
    assert parsed["problems"] == [] and r["ok"], r["problems"]
    got = B.structure(validate_definition(deepcopy(r["definition"])).raw)
    want = B.structure(validate_definition(deepcopy(BASE)).raw)
    assert got == want
    d = r["definition"]
    # 부품 계약은 기준 정의에서 그대로 — 폼 · 입출력 · orchestration
    diag = next(a for a in d["activities"] if a["name"] == "원인 진단")
    assert diag["id"] == "Activity_0diag4n" and diag["orchestration"] == "cliagents" and diag["agentMode"] == "COMPLETE"
    assert d["forms"] == BASE["forms"] and d["alertPolicy"] == BASE["alertPolicy"]
    # 그림에 기간이 없는 경계 타이머는 그 부품의 기준 기간(PT10M)을 기본값으로
    assert next(e for e in d["events"] if e["type"] == "boundaryEvent")["timer"] == "PT10M"


def test_structure_comparison_is_not_vacuous():
    """일부러 깨뜨림: 조건 하나 · 부품 하나를 바꾸면 구조 서명이 달라진다."""
    parsed = B.parse_bpmn(REDRAW)
    base_sig = B.structure(validate_definition(deepcopy(BASE)).raw)
    m = redraw_mapping(parsed)
    flow = next(f["id"] for f in parsed["flows"] if f["name"] == "미회복")
    m["flows"][flow] = {"default": True}
    _, r = run_check(REDRAW, m)
    assert r["ok"] and B.structure(r["definition"]) != base_sig
    m = redraw_mapping(parsed)
    m["tasks"][next(t["id"] for t in parsed["tasks"] if t["name"] == "규정 검토")] = {"part": "task:compliance"}
    m["timers"] = {parsed["boundaries"][0]["id"]: "PT20M"}
    _, r = run_check(REDRAW, m)
    assert r["ok"] and B.structure(r["definition"]) != base_sig


def test_compare_with_base_pairs_drawn_ids_with_the_chosen_parts():
    """B4 기준 비교: 그림 id(Activity_…)는 기준 id와 다르므로 id로 맞추면 전부 삭제+추가(30/30)였다. 고른 부품 · 이웃으로 맞춘다."""
    from procsvc import definition_diff as D
    parsed, r = run_check(REDRAW)
    d = r["definition"]
    plain = D.compare(BASE, d)
    assert plain["counts"]["추가"] >= 20 and plain["counts"]["삭제"] >= 20          # 맞추지 않으면 쓸모없는 목록 (이 시험이 헛돌지 않음)
    same = D.compare_import(BASE, d)
    assert same["counts"]["추가"] == 0 and same["counts"]["삭제"] == 0, same["changes"]
    assert not [c for c in same["changes"] if c["kind"] in ("단계", "연결", "분기점")]
    # 실제로 바꾼 것은 기준 id + 그림 id 로 보인다
    edited = deepcopy(d)
    diag = next(a for a in edited["activities"] if a["id"] == "Activity_0diag4n")
    diag["name"] = "내 원인 진단"
    edited["sequences"] = [s for s in edited["sequences"] if s["target"] != "Activity_0cmpl2r"]
    out = D.compare_import(BASE, edited)
    step = next(c for c in out["changes"] if c["kind"] == "단계" and c["change"] == "변경")
    assert (step["id"], step["drawn_id"]) == ("task:diagnose", "Activity_0diag4n") and step["text"].endswith("변경: 이름")
    gone = [c for c in out["changes"] if c["kind"] == "연결" and c["change"] == "삭제"]
    assert len(gone) == 1 and gone[0]["flow"]["to"] == "규정 검토" and out["counts"]["추가"] == 0
    # 일부러 깨뜨림: 고른 부품(mapping.tasks)을 지우면 task 는 맞출 수 없어 삭제+추가로 돌아간다
    blind = deepcopy(d); blind["bpmnImport"]["mapping"]["tasks"] = {}
    assert D.compare_import(BASE, blind)["counts"]["추가"] >= 9


def test_converted_base_flow_runs_on_the_engine_to_escalation():
    _, r = run_check(REDRAW)
    raw = validate_definition(deepcopy(r["definition"])).raw
    repo = procdb.MemoryRepo()
    rt = instances.InstanceRuntime(repo, engine.Definition.from_dict(deepcopy(BASE)), instances.Hooks())
    repo.upsert_proc_def(raw)
    inst = rt.start_definition("redraw", "1", "alert-1", alert={"alertId": "a1", "asset": "HYD-01", "pattern": "COOLER_DEGRADATION", "state": "RAISE"})
    pid = inst["proc_inst_id"]
    from test_engine import AGENT_OUTPUTS
    by_part = {a["id"]: a["tool"] for a in raw["activities"]}
    tool_of_base = {a["id"]: a["tool"] for a in BASE["activities"]}
    for base_id, out in AGENT_OUTPUTS.items():
        aid = next(k for k, v in by_part.items() if v == tool_of_base[base_id])
        item = next(w for w in repo.list_workitems(proc_inst_id=pid) if w["activity_id"] == aid)
        rt.submit(item["id"], out)
    timer = next(w for w in repo.list_workitems(proc_inst_id=pid) if w["activity_id"] == "Event_0tmot5y")
    rt.fire_timeouts(now=datetime.fromisoformat(timer["due_date"].replace("Z", "+00:00")) + timedelta(seconds=1))
    esc = next(w for w in repo.list_workitems(proc_inst_id=pid) if w["activity_id"] == "Activity_0escl1b")
    rt.submit(esc["id"], {"note": "현장 확인"})
    assert repo.get_instance(pid)["end_event"] == "Event_1escd0t"


# ---------------------------------------------------------------- 일부러 깨뜨림: 칸 위치와 사유로 거절
def test_command_reached_without_approval_is_refused_with_location():
    # 우선순위 → 조치 선택(승인) 선을 분기로 바로 이어 승인을 건너뜀
    xml = REDRAW.replace('sourceRef="Activity_1rank7c" targetRef="Activity_0slct3h"', 'sourceRef="Activity_1rank7c" targetRef="Gateway_1ctrl9q"')
    _, r = run_check(xml)
    assert not r["ok"]
    cmd = reasons(r, "Activity_1cmnd5p", "part")
    assert cmd and "사람 승인" in cmd[0] and "설비 명령" in cmd[0]
    where = next(p["where"] for p in r["problems"] if p["where"]["id"] == "Activity_1cmnd5p")
    assert where["name"] == "PLC 명령 발행" and where["kind_label"] == "작업"
    assert reasons(r, "Activity_0slct3h", "flow")                        # 끊긴 선도 함께


def test_timeout_path_does_not_count_as_approval():
    xml = REDRAW.replace('sourceRef="Event_0tmot5y" targetRef="Activity_0escl1b"', 'sourceRef="Event_0tmot5y" targetRef="Activity_1cmnd5p"')
    _, r = run_check(xml)
    assert any("사람 승인" in x for x in reasons(r, "Activity_1cmnd5p", "part"))


def test_command_repeated_by_a_loop_without_new_approval_is_refused():
    xml = REDRAW.replace('sourceRef="Gateway_0recv2z" targetRef="Activity_0escl1b"', 'sourceRef="Gateway_0recv2z" targetRef="Activity_1cmnd5p"')
    _, r = run_check(xml)
    assert any("되돌아가는 선" in x for x in reasons(r, "Activity_1cmnd5p", "part"))


def test_broken_line_is_refused_with_location():
    xml = REDRAW.replace('<bpmn:sequenceFlow id="Flow_0i9j0f9" sourceRef="Activity_1cmnd5p" targetRef="Activity_0reob6v" />', '')
    _, r = run_check(xml)
    assert any("나가는 선이 없습니다" in x for x in reasons(r, "Activity_1cmnd5p"))
    assert any("들어오는 선이 없습니다" in x for x in reasons(r, "Activity_0reob6v"))
    xml = REDRAW.replace('targetRef="Activity_0reob6v"', 'targetRef="Activity_missing"')
    parsed, r = run_check(xml)
    assert any("끊긴 선" in p["reason"] and p["where"]["id"] == "Flow_0i9j0f9" for p in parsed["problems"]) and not r["ok"]


def test_missing_branch_condition_is_refused_with_flow_location():
    parsed = B.parse_bpmn(REDRAW)
    m = redraw_mapping(parsed)
    flow = next(f["id"] for f in parsed["flows"] if f["name"] == "미회복")
    del m["flows"][flow]
    _, r = run_check(REDRAW, m)
    got = reasons(r, flow, "condition")
    assert got and "'회복?'" in got[0]


def test_value_the_next_step_waits_for_must_be_produced_before():
    parsed = B.parse_bpmn(REDRAW)
    m = redraw_mapping(parsed)
    comp = next(t["id"] for t in parsed["tasks"] if t["name"] == "규정 검토")
    m["tasks"][comp] = {"part": "agent", "agent": "sys:agent", "instruction": "규정을 요약한다", "outputs": [{"key": "review", "type": "text"}]}
    _, r = run_check(REDRAW, m)
    rank = next(t["id"] for t in parsed["tasks"] if t["name"] == "우선순위 · 카드 작성")
    assert any("compliance" in x for x in reasons(r, rank, "inputs"))


def test_unmapped_task_and_unsupported_elements_are_reported():
    parsed = B.parse_bpmn(REDRAW)
    m = redraw_mapping(parsed)
    del m["tasks"]["Activity_0diag4n"]
    _, r = run_check(REDRAW, m)
    assert reasons(r, "Activity_0diag4n", "part") == ["부품을 고르세요"]
    xml = REDRAW.replace('<bpmn:exclusiveGateway id="Gateway_0recv2z" name="회복?">', '<bpmn:inclusiveGateway id="Gateway_0recv2z" name="회복?">') \
                .replace('</bpmn:exclusiveGateway>\n    <bpmn:serviceTask id="Activity_1wkod4m"', '</bpmn:inclusiveGateway>\n    <bpmn:serviceTask id="Activity_1wkod4m"')
    p = B.parse_bpmn(xml)
    hit = [x for x in p["problems"] if (x.get("where") or {}).get("id") == "Gateway_0recv2z"]
    assert hit and hit[0]["where"]["name"] == "회복?" and "포함 분기" in hit[0]["reason"]
    sub = small('<bpmn:startEvent id="s"/><bpmn:subProcess id="Sub_1" name="묶음"/><bpmn:endEvent id="e"/>'
                '<bpmn:sequenceFlow id="f1" sourceRef="s" targetRef="Sub_1"/><bpmn:sequenceFlow id="f2" sourceRef="Sub_1" targetRef="e"/>')
    p = B.parse_bpmn(sub)
    assert any(x["where"]["id"] == "Sub_1" and x["where"]["name"] == "묶음" and "하위 프로세스" in x["reason"] for x in p["problems"])


@pytest.mark.parametrize("xml,needle", [
    ("<bpmn:definitions", "XML 을 읽을 수 없습니다 (1행"),
    ('<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><x/>', "DOCTYPE"),
    ('<root/>', "BPMN 2.0 파일이 아닙니다"),
    (f'<bpmn:definitions {NS} id="D"><bpmn:process id="P1"><bpmn:task id="a"/></bpmn:process>'
     f'<bpmn:process id="P2"><bpmn:task id="b"/></bpmn:process></bpmn:definitions>', "풀(참가자)이 2개"),
    ("", "빈 파일"),
])
def test_unreadable_files_are_refused_with_reason(xml, needle):
    with pytest.raises(B.BpmnError) as e:
        B.parse_bpmn(xml)
    assert needle in str(e.value)


# ---------------------------------------------------------------- 루프 · 사람 입력 시작
def loop_mapping(parsed):
    m, _ = B.merge_mapping(parsed, None, B.catalog(BASE, []))
    m["start"] = {"kind": "human", "fields": [{"key": "sample_id", "text": "시료 번호", "type": "text"}]}
    m["tasks"]["Activity_measure"] = {"part": "human", "role": "운전원", "inputs": ["sample_id"],
                                      "fields": [{"key": "iso_code", "text": "ISO 청정도 등급", "type": "integer"}]}
    m["flows"] = {"Flow_back": {"var": "iso_code", "op": ">", "value": 18}, "Flow_end": {"default": True}}
    return m


def test_loop_back_edge_is_kept_and_runs():
    parsed = B.parse_bpmn(LOOP)
    _, r = run_check(LOOP, loop_mapping(parsed), did="oil_loop")
    assert r["ok"], r["problems"]
    d = r["definition"]
    assert d["loopPolicy"] == "guarded" and r["loops"] == [["Activity_measure", "Gateway_ok"]]
    assert {"id": "Flow_back", "source": "Gateway_ok", "target": "Activity_measure", "name": "다시 측정", "condition": "iso_code > 18"} in d["sequences"]
    repo = procdb.MemoryRepo()
    rt = instances.InstanceRuntime(repo, engine.Definition.from_dict(deepcopy(BASE)), instances.Hooks())
    repo.upsert_proc_def(validate_definition(deepcopy(d)).raw)
    inst = rt.start_definition("oil_loop", "1", "oil-1", values={"sample_id": "S-1"})
    pid = inst["proc_inst_id"]
    def open_measure():
        return [w for w in repo.list_workitems(proc_inst_id=pid) if w["activity_id"] == "Activity_measure" and w["status"] == "IN_PROGRESS"]
    rt.submit(open_measure()[0]["id"], {"iso_code": 21})                  # 기준 밖 → 되돌아가 다시 측정 (새 작업 행)
    assert len(open_measure()) == 1 and repo.get_instance(pid)["status"] == "RUNNING"
    rt.submit(open_measure()[0]["id"], {"iso_code": 16})
    done = repo.get_instance(pid)
    assert done["status"] == "COMPLETED" and done["end_event"] == "Event_done"
    assert len([w for w in repo.list_workitems(proc_inst_id=pid) if w["activity_id"] == "Activity_measure"]) == 2


def test_loop_without_exit_is_refused_and_public_loops_stay_refused():
    xml = LOOP.replace('<bpmn:sequenceFlow id="Flow_end" sourceRef="Gateway_ok" targetRef="Event_done"/>', '')
    parsed = B.parse_bpmn(xml)
    m = loop_mapping(parsed); m["flows"] = {}
    _, r = run_check(xml, m, did="oil_loop")
    assert any("빠져나갈 배타 분기" in p["reason"] for p in r["problems"])
    assert any("끊긴 선" in x for x in reasons(r, "Event_done"))
    # 등록 계약: loopPolicy 없이 그린 반복은 그대로 거절, guarded 라도 빠져나갈 배타 분기가 없으면 거절
    _, ok = run_check(LOOP, loop_mapping(B.parse_bpmn(LOOP)), did="oil_loop")
    d = deepcopy(ok["definition"]); d.pop("loopPolicy")
    with pytest.raises(ValueError, match="반복 실행"):
        validate_definition(d)
    d = deepcopy(ok["definition"])
    d["gateways"].append({"id": "Gateway_par", "type": "parallelGateway"})
    d["sequences"] = [s for s in d["sequences"] if s["id"] != "Flow_back"] + [
        {"id": "x1", "source": "Gateway_ok", "target": "Gateway_par", "condition": "iso_code > 18"},
        {"id": "x2", "source": "Gateway_par", "target": "Activity_measure"}]
    with pytest.raises(ValueError, match="병렬 게이트웨이"):
        validate_definition(d)


def test_human_start_flow_with_general_parts():
    parsed = B.parse_bpmn(HUMAN_START)
    cat = B.catalog(BASE, [{"id": "role:maint-mgr", "username": "정비관리자", "is_agent": False},
                           {"id": "sys:agent", "username": "AI 에이전트", "is_agent": True, "agent_type": "agent"}])
    m, _ = B.merge_mapping(parsed, None, cat)
    assert m["start"] == {"kind": "human", "fields": []} and m["lanes"] == {"Lane_m": "정비관리자", "Lane_a": "AI 에이전트"}
    m["start"]["fields"] = [{"key": "oil_iso", "text": "ISO 청정도", "type": "text"}, {"key": "water_ppm", "text": "수분", "type": "number"}]
    m["tasks"]["Activity_summary"] = {"part": "agent", "instruction": "기준 이탈 항목을 조회해 요약 보고서를 쓴다", "inputs": ["oil_iso", "water_ppm"],
                                      "outputs": [{"key": "summary", "text": "요약", "type": "textarea"}]}
    m["tasks"]["Activity_review"] = {"part": "human", "inputs": ["summary"],
                                     "fields": [{"key": "action", "text": "조치", "type": "select", "items": ["재분석", "교체"]}]}
    r = B.check(parsed, m, {"catalog": cat, "definition_id": "oil_check", "version": "1"})
    assert r["ok"], r["problems"]
    d = r["definition"]
    agent = next(a for a in d["activities"] if a["id"] == "Activity_summary")
    assert (agent["type"], agent["agentMode"], agent["orchestration"], agent["agent"]) == ("userTask", "COMPLETE", "cliagents", "sys:agent")
    review = next(a for a in d["activities"] if a["id"] == "Activity_review")
    assert review["role"] == "정비관리자" and {"name": "정비관리자", "endpoint": "role:maint-mgr"}.items() <= next(
        x for x in d["roles"] if x["name"] == "정비관리자").items()
    assert d["startForm"]["fields_json"][1] == {"key": "water_ppm", "text": "수분", "type": "number"} and "alertPolicy" not in d
    assert d["events"][0]["eventDefinition"] == "none"
    # 일부러 깨뜨림: 사람 입력 시작이 낸 적 없는 값을 기다림 · 서버만 만드는 값 이름 · 사람 역할이 아닌 담당
    bad = deepcopy(m); bad["tasks"]["Activity_summary"]["inputs"] = ["pressure"]
    assert any("pressure" in x for x in reasons(B.check(parsed, bad, {"catalog": cat, "definition_id": "o", "version": "1"}), "Activity_summary", "inputs"))
    bad = deepcopy(m); bad["start"]["fields"] = [{"key": "approved_by", "type": "text"}]
    assert any("서버 승인" in p["reason"] for p in B.check(parsed, bad, {"catalog": cat, "definition_id": "o", "version": "1"})["problems"])
    bad = deepcopy(m); bad["tasks"]["Activity_review"]["role"] = "SCADA"
    assert any("사람 역할이 아닙니다" in x for x in reasons(B.check(parsed, bad, {"catalog": cat, "definition_id": "o", "version": "1"}), "Activity_review", "role"))


# ---------------------------------------------------------------- API: 등록 · 다시 가져오기 · 그림 받기 · 되돌리기
@pytest.fixture
def api():
    repo = procdb.MemoryRepo()
    repo.upsert_user({"id": "sys:agent", "username": "AI 에이전트", "is_agent": True, "agent_type": "agent", "tenant_id": "hyd"})
    repo.upsert_user({"id": "role:maint-mgr", "username": "정비관리자", "is_agent": False, "tenant_id": "hyd"})
    rt = instances.InstanceRuntime(repo, validate_definition(deepcopy(BASE)), instances.Hooks())
    audit = []
    app = FastAPI()
    flows_api.register(app, runtime_factory=lambda: rt, audit=lambda *a, **k: audit.append(a), base_loader=lambda _rt: deepcopy(BASE))
    return TestClient(app), rt, repo, audit


def test_api_registers_new_version_with_bpmn_and_keeps_prod_pointer(api):
    c, rt, repo, audit = api
    base_head = deepcopy(repo.get_proc_def("anomaly_response"))
    r = c.post("/api/flows/import", json={"xml": REDRAW, "file_name": "redraw.bpmn", "definition_id": "my_cooler"})
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["definition_id"] == "my_cooler" and v["next_version"] == "1" and not v["check"]["ok"]
    mapping = redraw_mapping(B.parse_bpmn(REDRAW))
    assert c.put("/api/flows/my_cooler/mapping", json={"mapping": mapping}).json()["check"]["ok"]
    r = c.post("/api/flows/my_cooler/register", json={})
    assert r.status_code == 201, r.text
    assert r.json()["version"] == "1" and r.json()["deployed"] is False
    stored = repo.get_proc_def("my_cooler", version="1")["definition"]
    assert B.structure(stored) == B.structure(validate_definition(deepcopy(BASE)).raw)
    assert stored["bpmnImport"]["mapping"]["tasks"] == mapping["tasks"]
    # 운영 판본 포인터(proc_def 머리)는 그대로, 새 흐름은 머리 없이 판본만
    assert repo.get_proc_def("anomaly_response") == base_head and repo.get_proc_def("my_cooler") is None
    # 그림 다시 받기 = 가져온 원본 그대로
    x = c.get("/api/flows/my_cooler/versions/1/bpmn")
    assert x.status_code == 200 and x.text == REDRAW and 'filename="my_cooler-v1.bpmn"' in x.headers["content-disposition"]
    assert c.get("/api/flows/my_cooler/versions/9/bpmn").status_code == 404
    assert c.get("/api/flows/anomaly_response/versions/2.2/bpmn").status_code == 404
    # 같은 흐름을 다시 등록하면 새 판본 2 (판본 1 은 그대로)
    assert c.post("/api/flows/my_cooler/register", json={}).json()["version"] == "2"
    assert repo.get_proc_def("my_cooler", version="1")["definition"]["version"] == "1"
    assert [a[2] for a in audit] == ["FLOW_REGISTERED", "FLOW_REGISTERED"]
    listed = c.get("/api/flows").json()
    assert [(x["id"], x["version"]) for x in listed["versions"]] == [("my_cooler", "1"), ("my_cooler", "2")]
    # B4 기준 비교는 가져온 흐름을 고른 부품으로 맞춘다(단계 · 연결 추가/삭제 없음)
    from procsvc import flow_deploy
    diff = flow_deploy.compare_with_reference(rt, "my_cooler", "1")
    assert diff["counts"]["추가"] == 0 and diff["counts"]["삭제"] == 0, diff["steps"]
    assert all(f["label"] == "설명" for c in diff["changes"] if c["kind"] != "정의" for f in c["fields"]), diff["steps"]


def test_api_refuses_failed_check_and_base_ids(api):
    c, rt, repo, _ = api
    xml = REDRAW.replace('sourceRef="Activity_1rank7c" targetRef="Activity_0slct3h"', 'sourceRef="Activity_1rank7c" targetRef="Gateway_1ctrl9q"')
    assert c.post("/api/flows/import", json={"xml": xml, "definition_id": "bypass"}).status_code == 200
    r = c.post("/api/flows/bypass/register", json={"mapping": redraw_mapping(B.parse_bpmn(xml))})
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "등록하지 않았습니다" in detail["reason"]
    assert any(p["where"]["id"] == "Activity_1cmnd5p" and "사람 승인" in p["reason"] for p in detail["problems"])
    assert repo.get_proc_def("bypass", version="1") is None
    for did in ("anomaly_response", "alert_triage"):
        if did == "alert_triage":
            rt.register_definition(json.loads((ROOT / "it/process/definitions/alert_triage_v1.json").read_text(encoding="utf-8")))
        r = c.post("/api/flows/import", json={"xml": REDRAW, "definition_id": did})
        assert r.status_code == 409 and "기준 흐름" in r.json()["detail"]["reason"]
    r = c.post("/api/flows/import", json={"xml": "<oops", "definition_id": "x"})
    assert r.status_code == 400 and "XML" in r.json()["detail"]["reason"]
    assert c.post("/api/flows/import", json={"xml": REDRAW, "definition_id": "1bad id"}).status_code == 400
    assert c.post("/api/flows/nothing/register", json={}).status_code == 404


def test_reimport_keeps_mapping_for_the_same_task_ids(api):
    c, rt, repo, _ = api
    c.post("/api/flows/import", json={"xml": REDRAW, "definition_id": "again"})
    mapping = redraw_mapping(B.parse_bpmn(REDRAW))
    c.put("/api/flows/again/mapping", json={"mapping": mapping})
    # 그림 고침: 이름 바꾸기(같은 id) · task 하나 지우고 새 task 하나 (id 다름)
    xml = REDRAW.replace('name="원인 진단"', 'name="원인 찾기"').replace('id="Activity_0cmpl2r"', 'id="Activity_9newone"') \
                .replace('>Activity_0cmpl2r<', '>Activity_9newone<').replace('"Activity_0cmpl2r"', '"Activity_9newone"')
    v = c.post("/api/flows/import", json={"xml": xml, "definition_id": "again"}).json()
    rep = v["reimport"]
    assert rep["previous"] and rep["dropped"] == ["Activity_0cmpl2r"] and rep["new"] == ["Activity_9newone"]
    assert v["mapping"]["tasks"]["Activity_0diag4n"] == {"part": "task:diagnose"} and "Activity_9newone" not in v["mapping"]["tasks"]
    assert v["mapping"]["flows"] == mapping["flows"]
    assert reasons(v["check"], "Activity_9newone", "part") == ["부품을 고르세요"]


def test_human_start_registers_and_starts_through_existing_api(api, monkeypatch):
    c, rt, repo, _ = api
    c.post("/api/flows/import", json={"xml": HUMAN_START, "definition_id": "oil_check", "file_name": "oil.bpmn"})
    m = c.get("/api/flows/oil_check").json()["mapping"]
    m["start"] = {"kind": "human", "fields": [{"key": "oil_iso", "text": "ISO 청정도", "type": "text"}]}
    m["tasks"] = {"Activity_summary": {"part": "agent", "agent": "sys:agent", "instruction": "이탈 항목을 요약한다", "inputs": ["oil_iso"],
                                       "outputs": [{"key": "summary", "type": "text"}]},
                  "Activity_review": {"part": "human", "inputs": ["summary"], "fields": [{"key": "note", "text": "메모", "type": "textarea"}]}}
    r = c.post("/api/flows/oil_check/register", json={"mapping": m})
    assert r.status_code == 201, r.text
    inst = rt.start_definition("oil_check", "1", "oil-1", values={"oil_iso": "20/18/15"})
    rows = repo.list_workitems(proc_inst_id=inst["proc_inst_id"])
    agent = next(w for w in rows if w["activity_id"] == "Activity_summary")
    assert agent["status"] == "IN_PROGRESS" and agent["agent_mode"] == "COMPLETE" and agent["agent_orch"] == "cliagents"
    assert '"oil_iso": "20/18/15"' in agent["query"]


def test_reset_removes_only_user_flows_and_waits_for_running_instances(api):
    c, rt, repo, audit = api
    base_versions = sorted(k for k in repo.def_versions)
    c.post("/api/flows/import", json={"xml": LOOP, "definition_id": "oil_loop"})
    assert c.post("/api/flows/oil_loop/register", json={"mapping": loop_mapping(B.parse_bpmn(LOOP))}).status_code == 201
    inst = rt.start_definition("oil_loop", "1", "oil-1", values={"sample_id": "S-1"})
    r = c.post("/api/flows/reset")
    assert r.status_code == 409 and inst["proc_inst_id"] in r.json()["detail"]["reason"]
    assert repo.get_proc_def("oil_loop", version="1") is not None                       # 거절되면 아무것도 지우지 않음
    w = next(w for w in repo.list_workitems(proc_inst_id=inst["proc_inst_id"]) if w["status"] == "IN_PROGRESS")
    rt.submit(w["id"], {"iso_code": 10})
    r = c.post("/api/flows/reset")
    assert r.status_code == 200 and r.json() == {"versions": 1, "definitions": 1, "drafts": 1, "hidden_instances": 1}
    assert sorted(k for k in repo.def_versions) == base_versions                         # 기준 정의는 그대로
    assert repo.get_proc_def("oil_loop", version="1") is None and c.get("/api/flows").json() == {"drafts": [], "versions": []}
    assert repo.get_instance(inst["proc_inst_id"])["is_deleted"] is True
    assert c.get("/api/flows/oil_loop").status_code == 404
    assert audit[-1][2] == "FLOWS_RESET"


def test_api_needs_instance_mode():
    app = FastAPI()
    flows_api.register(app, runtime_factory=lambda: None)
    assert TestClient(app).get("/api/flows/catalog").status_code == 503


def test_catalog_parts_come_from_the_base_definition_file():
    cat = B.catalog(BASE, [])
    scen = [p for p in cat["parts"] if p["group"] == "scenario"]
    assert [p["key"] for p in scen] == [a["id"] for a in BASE["activities"]]
    assert {p["key"] for p in scen if p["approval"]} == {"task:select"}
    assert {p["key"]: p["effect"] for p in scen if p["effect"]} == {"task:command": "설비 명령", "task:work-order": "작업지시"}
    changed = deepcopy(BASE); changed["activities"][0]["instruction"] = "바뀐 지시"
    assert B.catalog(changed, [])["parts"][0]["contract"]["instruction"] == "바뀐 지시"      # 코드에 복사해 둔 계약이 아니다
    src = (ROOT / "it/process/procsvc/bpmn_import.py").read_text(encoding="utf-8")
    assert "dec:diagnose-cause" not in src and "원인 진단" not in src


def test_portal_pure_helpers():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node 없음")
    script = r"""
const vm = require('vm'); const fs = require('fs');
const ctx = { window: {} }; vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), ctx);
const P = ctx.window.hydFlows.pure;
const f = P.parseFields('oil_iso | ISO 청정도\nkind | 종류 | select | 재분석, 교체\nn||number');
let err = ''; try { P.parseFields('x | y | color'); } catch (e) { err = e.message; }
let err2 = ''; try { P.parseFields('k | 고르기 | select'); } catch (e) { err2 = e.message; }
console.log(JSON.stringify({ f, back: P.fieldsText(f), err, err2, v: [P.parseValue('예'), P.parseValue('18'), P.parseValue('control')],
  m: [P.minutesOf('PT10M'), P.minutesOf('PT1H30M'), P.isoOf(10), P.isoOf(0.5), P.isoOf('')] }));
"""
    out = subprocess.run([node, "-e", script, str(ROOT / "it/portal/www/flows.js")], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    r = json.loads(out.stdout)
    assert r["f"] == [{"key": "oil_iso", "text": "ISO 청정도", "type": "text"}, {"key": "kind", "text": "종류", "type": "select", "items": ["재분석", "교체"]},
                      {"key": "n", "text": "n", "type": "number"}]
    assert P_round(r["back"]) and "1번째 줄" in r["err"] and "고를 값" in r["err2"]
    assert r["v"] == [True, 18, "control"] and r["m"] == [10, 90, "PT10M", "PT30S", ""]


def P_round(text):
    return text.splitlines() == ["oil_iso | ISO 청정도", "kind | 종류 | select | 재분석,교체", "n |  | number"]


# ---------------------------------------------------------------- 실제 Supabase 표 (migration 000001 · 000002 · 000043 적용된 빈 DB)
PG_DSN = __import__("os").getenv("HYD_FLOW_PG_DSN")


@pytest.mark.skipif(not PG_DSN, reason="HYD_FLOW_PG_DSN 이 없으면 Supabase 표 검사는 건너뛴다 (migration 000001 · 000002 · 000043 적용된 빈 DB)")
def test_pg_register_keeps_prod_pointer_stores_bpmn_and_reset_spares_base():
    from procsvc.procdb import PgRepo
    repo = PgRepo(PG_DSN)
    with repo._conn() as c:
        c.execute("insert into tenants (id, name) values ('hyd', 'hyd') on conflict (id) do nothing")
        c.execute("insert into users (id, username, is_agent, agent_type, tenant_id) values ('sys:agent', 'AI 에이전트', true, 'agent', 'hyd') "
                  "on conflict (id) do nothing")
    rt = instances.InstanceRuntime(repo, validate_definition(deepcopy(BASE)), instances.Hooks())   # 기준 정의 등록(origin 없음)
    with repo._conn() as c:
        head = c.execute("select prod_version, definition, bpmn, origin from proc_def where id='anomaly_response' and tenant_id='hyd'").fetchone()
    app = FastAPI()
    flows_api.register(app, runtime_factory=lambda: rt, base_loader=lambda _rt: deepcopy(BASE))
    c = TestClient(app)
    try:
        assert c.post("/api/flows/import", json={"xml": REDRAW, "definition_id": "anomaly_response"}).status_code == 409
        assert c.post("/api/flows/import", json={"xml": REDRAW, "definition_id": "pg_cooler", "file_name": "r.bpmn"}).status_code == 200
        mapping = redraw_mapping(B.parse_bpmn(REDRAW))
        assert c.put("/api/flows/pg_cooler/mapping", json={"mapping": mapping}).json()["check"]["ok"]
        assert c.get("/api/flows/pg_cooler").json()["mapping"]["tasks"] == mapping["tasks"]
        assert c.post("/api/flows/pg_cooler/register", json={}).json()["version"] == "1"
        assert c.post("/api/flows/pg_cooler/register", json={}).json()["version"] == "2"
        stored = repo.get_proc_def("pg_cooler", "hyd", version="2")["definition"]
        assert B.structure(stored) == B.structure(validate_definition(deepcopy(BASE)).raw)
        assert c.get("/api/flows/pg_cooler/versions/1/bpmn").text == REDRAW
        with repo._conn() as db:
            assert db.execute("select prod_version, definition, bpmn, origin from proc_def where id='anomaly_response' and tenant_id='hyd'").fetchone() == head
            mine = db.execute("select prod_version, definition, bpmn, origin from proc_def where id='pg_cooler'").fetchone()
            assert mine["prod_version"] is None and mine["definition"] is None and mine["bpmn"] == REDRAW and mine["origin"] == "user"
            assert db.execute("select count(*) as n from proc_def_version where proc_def_id='pg_cooler' and origin='user' and snapshot=%s",
                              (REDRAW,)).fetchone()["n"] == 2
        assert [(v["id"], v["version"]) for v in c.get("/api/flows").json()["versions"]] == [("pg_cooler", "1"), ("pg_cooler", "2")]
        # 진행 중 처리 건이 있으면 되돌리기 거절, 끝나면 학생 것만 지움
        c.post("/api/flows/import", json={"xml": LOOP, "definition_id": "pg_loop"})
        assert c.post("/api/flows/pg_loop/register", json={"mapping": loop_mapping(B.parse_bpmn(LOOP))}).status_code == 201
        inst = rt.start_definition("pg_loop", "1", "pg-loop-1", values={"sample_id": "S-1"})
        r = c.post("/api/flows/reset")
        assert r.status_code == 409 and r.json()["detail"]["running"][0]["proc_inst_id"] == inst["proc_inst_id"]
        w = next(w for w in repo.list_workitems(proc_inst_id=inst["proc_inst_id"]) if w["status"] == "IN_PROGRESS")
        rt.submit(w["id"], {"iso_code": 10})
        r = c.post("/api/flows/reset")
        assert r.status_code == 200 and r.json() == {"versions": 3, "definitions": 2, "drafts": 2, "hidden_instances": 1}
        assert repo.get_proc_def("anomaly_response", "hyd", version="2.2") is not None
        assert repo.get_proc_def("pg_cooler", "hyd", version="1") is None
    finally:
        with repo._conn() as db:
            db.execute("delete from todolist where proc_inst_id in (select proc_inst_id from bpm_proc_inst where proc_def_id in ('pg_cooler','pg_loop'))")
            db.execute("delete from bpm_proc_inst where proc_def_id in ('pg_cooler','pg_loop')")
            db.execute("delete from proc_def_version where proc_def_id in ('pg_cooler','pg_loop')")
            db.execute("delete from proc_def where id in ('pg_cooler','pg_loop')")
            db.execute("delete from proc_bpmn_draft where proc_def_id in ('pg_cooler','pg_loop')")


# ---------------------------------------------------------------- 수업 기본 경로(AGENT_BRIDGE=legacy): 그림의 task id 로도 내장 판단이 채워진다
from test_instance_mode import ALERT, GUIDE_CARD_ACTIONS, _decision_payload, world  # noqa: E402,F401  (world = fixture)


def test_imported_flow_runs_the_classroom_legacy_bridge_and_approval_path(world):
    from procsvc import decisions as declib, instance_mode
    from procsvc.bpmn_store import FlowStore
    rt, incidents, book = world["rt"], world["incidents"], world["book"]
    _, r = run_check(REDRAW, did="my_cooler")
    raw = FlowStore(rt.repo, rt.tenant_id).register(r["definition"], REDRAW, "redraw.bpmn")
    inst = rt.start_definition("my_cooler", raw["version"], ALERT["alertId"], alert=ALERT)
    inc = next(iter(incidents.values()))
    inc.card = dict(inc.card, recommended=GUIDE_CARD_ACTIONS, causes=[{"id": "cause:cooler-fin-fouling"}], topCause="cause:cooler-fin-fouling")
    d = declib.new(_decision_payload(inc.id))
    book[d["id"]] = d
    instance_mode._bridge_legacy_agent(d)
    items = {w["activity_id"]: w for w in rt.repo.list_workitems(proc_inst_id=inst["proc_inst_id"])}
    assert [items[a]["status"] for a in ("Activity_0diag4n", "Activity_1cand8s", "Activity_0cmpl2r", "Activity_1rank7c")] == ["DONE"] * 4
    assert items["Activity_0slct3h"]["status"] == "IN_PROGRESS"
    rt.select(items["Activity_0slct3h"]["id"], d["id"], "skill:fan-max-derate", by="이생산", role="role:prod-mgr", reason="납기")
    assert inc.state == "AWAITING_ACK" and inc.cmd_id                       # 사람 승인 1회 뒤에만 설비 명령
    assert rt.repo.get_workitem(next(w["id"] for w in rt.repo.list_workitems(proc_inst_id=inst["proc_inst_id"])
                                     if w["activity_id"] == "Activity_1cmnd5p"))["status"] in ("SUBMITTED", "IN_PROGRESS")


def _start_imported(world):
    from procsvc.bpmn_store import FlowStore
    rt = world["rt"]
    _, r = run_check(REDRAW, did="my_cooler")
    raw = FlowStore(rt.repo, rt.tenant_id).register(r["definition"], REDRAW, "redraw.bpmn")
    return rt, rt.start_definition("my_cooler", raw["version"], ALERT["alertId"], alert=ALERT)


def test_imported_flow_is_evaluated_by_the_classroom_legacy_evaluator(world):
    """수업 기본 경로(내장 결정론 판단 C4)가 그림 id 의 원인 진단 task 를 집어 네 에이전트 task 를 채운다."""
    from procsvc import instance_mode
    from procsvc.legacy_assessment import LegacyAssessment
    rt, inst = _start_imported(world)
    inc = engine.variables(inst)["incident"]
    def publish(payload, card):
        world["ctx"].book[payload["id"]] = deepcopy(payload); rt.hooks.update_incident_card(inc, card); return payload
    evaluation = {"status": "EVALUATED", "evaluation": _decision_payload(inc),
                  "card": {"alert": ALERT, "recommended": GUIDE_CARD_ACTIONS, "cause": "cause:cooler-fin-fouling"}}
    worker = LegacyAssessment(rt, lambda alert: deepcopy(evaluation), publish, instance_mode._bridge_legacy_agent)
    assert worker.tick() == 1
    rows = {w["activity_id"]: w for w in rt.repo.list_workitems(proc_inst_id=inst["proc_inst_id"])}
    assert [rows[a]["status"] for a in ("Activity_0diag4n", "Activity_1cand8s", "Activity_0cmpl2r", "Activity_1rank7c")] == ["DONE"] * 4
    assert rows["Activity_0slct3h"]["status"] == "IN_PROGRESS" and not world["executed"]


def test_imported_flow_ends_through_its_escalation_when_the_alert_clears_first(world):
    """A074 경로: 조치 전에 경보가 풀리면 열린 일을 닫고 그림의 상급자 호출 task 로 넘어간다(그림 id 로도)."""
    from procsvc import machine
    from test_instance_mode import NOW, NoFx
    rt, inst = _start_imported(world)
    inc = next(iter(world["incidents"].values()))
    machine.on_alert(inc, {"alertId": inc.alert_id, "state": "CLEAR"}, NoFx())
    assert inc.state == "RESOLVED_WITHOUT_ACTION"
    rt.on_incident_update(inc.state, inc.id, inc.cleared, now=NOW)
    rows = {w["activity_id"]: w for w in rt.repo.list_workitems(proc_inst_id=inst["proc_inst_id"])}
    assert rows["Activity_0diag4n"]["status"] == "CANCELLED" and rows["Activity_0escl1b"]["status"] == "IN_PROGRESS"
    rt.submit(rows["Activity_0escl1b"]["id"], {"note": "조치 전에 경보가 풀림"}, by="이생산", now=NOW)
    assert rt.repo.get_instance(inst["proc_inst_id"])["end_event"] == "Event_1escd0t"
