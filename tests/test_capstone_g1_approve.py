"""캡스톤 G1 — 일반 사람 승인 부품(human:approve · formHandler:approve).

학생 흐름(설계안 3.6 회의 준비를 줄인 모양): 시작(사람 입력) → 에이전트 제안(proposal) → 주관자 승인(안 고르기) → ◇ approval
  승인 → 승인 뒤 MCP 호출(gcal.create_event, 인자 틀 {approved_option.slot}) → 결과 보고(정상) → 끝
  반려 → 결과 보고(반려) → 끝
비해피: 권한 없음(다른 역할 · "나" 아님 · 역할 구성원 아님) · 안 없음 · 목록에 없는 안 · 이미 승인됨 · 반려 사유 없음 · 일반 /submit 우회 ·
승인 기록 없는 효과 · 설정 오류 · 보호 값 주입. 판단 엔진 카드 승인(select_card) 흐름은 test_c2_execution 이 그대로 지킨다."""
from copy import deepcopy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from procsvc import approval_part as AP, bpmn_import as B, engine, inbox, instance_mode
from procsvc.definition_registry import PROTECTED_OUTPUTS, validate_definition
from test_c2_execution import xml, lanes, report
from test_instance_mode import world, NOW, _row  # noqa: F401  (world 는 fixture)

ORG, OTHER, STRANGER = "user:han-org", "user:yoo-org", "user:kim-op"
ROLE = "role:organizer"
USERS = [{"id": ROLE, "username": "주관자"}, {"id": "role:operator", "username": "운전원"}]

FLOW = xml("""
  <bpmn:startEvent id="Start" name="회의 요청 접수"/>
  <bpmn:task id="T_agent" name="자료 · 시간 후보 제안"/>
  <bpmn:userTask id="T_approve" name="주관자 승인"/>
  <bpmn:exclusiveGateway id="G_ok" name="승인?"/>
  <bpmn:serviceTask id="T_event" name="일정 등록"/>
  <bpmn:serviceTask id="R_ok" name="결과 보고: 확정"/>
  <bpmn:serviceTask id="R_rej" name="결과 보고: 반려"/>
  <bpmn:endEvent id="E_end" name="끝"/>
  <bpmn:sequenceFlow id="F1" sourceRef="Start" targetRef="T_agent"/>
  <bpmn:sequenceFlow id="F2" sourceRef="T_agent" targetRef="T_approve"/>
  <bpmn:sequenceFlow id="F3" sourceRef="T_approve" targetRef="G_ok"/>
  <bpmn:sequenceFlow id="F_yes" name="승인" sourceRef="G_ok" targetRef="T_event"/>
  <bpmn:sequenceFlow id="F_no" name="반려" sourceRef="G_ok" targetRef="R_rej"/>
  <bpmn:sequenceFlow id="F4" sourceRef="T_event" targetRef="R_ok"/>
  <bpmn:sequenceFlow id="F5" sourceRef="R_ok" targetRef="E_end"/>
  <bpmn:sequenceFlow id="F6" sourceRef="R_rej" targetRef="E_end"/>""", "Process_qbr",
           lanes(["T_approve"], ["T_agent"], ["T_event", "R_ok", "R_rej"]).replace('name="담당자"', 'name="주관자"'))

CONFIG = {"options": "proposal.options", "recommended": "proposal.recommended", "losers": "proposal.losers", "docs": "proposal.docs"}
PROPOSAL = {"options": [{"slot": "금 10:00", "room": "6인실 B", "score": 0.82, "reason": "필수 참석자 전원 · 자료 48시간 전 공유"},
                        {"slot": "다음 주 화 15:00", "room": "6인실 A", "score": 0.61, "reason": "모두 가능하지만 고객 마감 초과"}],
            "recommended": "금 10:00",
            "losers": [{"slot": "내일 10:00", "why": "자료 공유 48시간 규칙 위반"}, {"slot": "목 14:00", "why": "필수 참석자(고객 담당 임원) 불가"}],
            "docs": [{"title": "Q3 회의록", "link": "https://drive.example/q3"}]}


def mapping(config=None):
    return {"name": "분기 리뷰 회의 준비 (시험)", "start": {"kind": "human", "fields": [{"key": "request_id", "text": "요청 ID"}]},
            "lanes": {},
            "tasks": {"T_agent": {"part": "agent", "instruction": "자료를 찾고 규칙을 지키는 시간 후보를 순위와 함께 낸다",
                                  "outputs": [{"key": "proposal", "text": "제안", "type": "object"}], "inputs": ["request_id"]},
                      "T_approve": {"part": AP.KEY, "role": "주관자", "config": deepcopy(CONFIG if config is None else config)},
                      "T_event": {"part": "svc:mcp-call", "config": {"server": "gcal", "tool": "create_event",
                                                                    "arguments": {"slot": "{approved_option.slot}", "room": "{approved_option.room}",
                                                                                  "organizer": "{approved_by}"}}},
                      "R_ok": report("정상", "{request_id} 회의 확정", "{approved_option.slot} · {approved_option.room}"),
                      "R_rej": report("반려", "{request_id} 회의 반려", "사유: {approval_reason}")},
            "timers": {}, "flows": {"F_yes": {"var": "approval", "op": "==", "value": AP.APPROVE}, "F_no": {"default": True}}}


def imported(world, m, did="qbr"):
    rt = world["rt"]
    base = rt.definition_for({"proc_def_id": rt.defn.id, "proc_def_version": rt.base_version, "tenant_id": rt.tenant_id}).raw
    cat = B.catalog(base, USERS)
    return cat, B.check(B.parse_bpmn(FLOW), m, {"catalog": cat, "definition_id": did, "version": "1", "file_name": f"{did}.bpmn",
                                                "xml_sha256": "x"})


class Calendar:
    def __init__(self):
        self.calls = []

    def __call__(self, server, tool, arguments, key):
        self.calls.append((server, tool, deepcopy(arguments), key))
        return {"status": "ok", "result": {"is_error": False, "text": '{"id": "evt-1"}'}, "arguments": arguments, "idempotent": True}


@pytest.fixture
def case(world):
    rt = world["rt"]
    for uid, name in ((ROLE, "주관자"), ("role:operator", "운전원"), (ORG, "한주관"), (OTHER, "유주관"), (STRANGER, "김운전")):
        rt.repo.upsert_user({"id": uid, "username": name, "is_agent": False, "tenant_id": "hyd"})
    rt.repo.set_role_member("hyd", ROLE, ORG, True)
    rt.repo.set_role_member("hyd", "role:operator", STRANGER, True)
    _, r = imported(world, mapping())
    assert r["ok"], r["problems"]
    rt.register_definition(r["definition"])
    rt.deploy_definition("qbr", "1", "tester", "G1 시험")
    cal = Calendar()
    rt.hooks.mcp_call = cal

    def start(proposal=PROPOSAL, event="QBR-1"):
        inst = rt.start_definition("qbr", "1", event, {"request_id": event}, now=NOW)
        rt.submit(_row(rt, inst, "T_agent")["id"], {"proposal": deepcopy(proposal)}, now=NOW)
        return inst, _row(rt, inst, "T_approve")
    return rt, cal, start


def values(rt, inst):
    return engine.variables(rt.repo.get_instance(inst["proc_inst_id"]))


# ---------------------------------------------------------------- 가져오기 · 등록 검사
def test_import_makes_an_approval_task_with_the_part_form_and_counts_it_as_the_approval(world):
    cat, r = imported(world, mapping())
    assert r["ok"], r["problems"]
    part = next(p for p in cat["parts"] if p["key"] == AP.KEY)
    assert part["approval"] and part["kind"] == "human" and part["server_values"] == list(AP.SERVER_VALUES)
    act = next(a for a in r["definition"]["activities"] if a["id"] == "T_approve")
    assert act["tool"] == AP.TOOL and act["approval"] == CONFIG and act["inputData"] == ["proposal"]
    assert act["outputData"] == list(AP.OUTPUTS) and r["definition"]["forms"][AP.FORM_ID] == AP.FORM
    assert act["role"] == "주관자" and {"name": "주관자", "endpoint": ROLE} in [
        {k: x[k] for k in ("name", "endpoint")} for x in r["definition"]["roles"]]
    # 승인 뒤 MCP 호출의 인자 틀이 읽는 approved_option 은 이 승인 task 가 내는 값으로 잡힌다(값 연결 검사 통과)
    assert {"value": "approved_option", "from": "T_approve"} in r["available"]["T_event"]


def test_effect_without_the_approval_in_front_is_refused_naming_both_approval_parts(world):
    m = mapping()
    m["tasks"]["T_agent"] = {"part": "svc:mcp-call", "config": {"server": "gcal", "tool": "create_event", "arguments": {}}}
    _, r = imported(world, m)
    reasons = [p["reason"] for p in r["problems"] if (p.get("where") or {}).get("id") == "T_agent"]
    assert any("사람 승인" in x and "사람 승인 (안 고르기)" in x for x in reasons), r["problems"]


@pytest.mark.parametrize("config,phrase", [
    ({}, "options"),
    ({"options": "proposal options"}, "처리 건 값 이름"),
    ({"options": "proposal.options", "key": "1slot"}, "key"),
    ({"options": "proposal.options", "color": "red"}, "모르는 칸"),
])
def test_bad_config_is_reported_at_the_task(world, config, phrase):
    _, r = imported(world, mapping(config))
    assert not r["ok"] and any(phrase in p["reason"] and p["where"]["id"] == "T_approve" and p["field"] == "config"
                               for p in r["problems"]), r["problems"]


def test_registry_refuses_a_changed_approval_form_missing_input_and_injected_option(world):
    _, r = imported(world, mapping())
    d = r["definition"]
    bad = deepcopy(d)
    bad["forms"][AP.FORM_ID]["fields_json"][0]["items"] = [AP.APPROVE]          # 반려를 지운 폼
    with pytest.raises(ValueError, match="부품 폼"):
        validate_definition(bad)
    bad = deepcopy(d)
    next(a for a in bad["activities"] if a["id"] == "T_approve")["inputData"] = []
    with pytest.raises(ValueError, match="inputData"):
        validate_definition(bad)
    assert "approved_option" in PROTECTED_OUTPUTS
    m = mapping()
    m["tasks"]["T_agent"]["outputs"].append({"key": "approved_option", "type": "object"})
    _, r2 = imported(world, m)
    assert any("서버 승인 경로" in p["reason"] for p in r2["problems"])


def test_start_values_cannot_inject_the_approved_option(case):
    rt, _, _ = case
    with pytest.raises(ValueError, match="승인 결과"):
        rt.start_definition("qbr", "1", "inject", {"request_id": "x", "approved_option": {"slot": "x"}}, now=NOW)


# ---------------------------------------------------------------- 실행: 승인 · 반려
def test_approve_records_who_and_the_chosen_option_then_the_effect_uses_it(case):
    rt, cal, start = case
    inst, wi = start()
    assert inbox.inbox_view(rt, ORG)["tasks"][0]["kind"] == "approve"                 # 내 작업함: 주관자 한 명 → 그 사람에게
    out = rt.approve(wi["id"], AP.APPROVE, "금 10:00", ORG, ROLE, "추천안대로", now=NOW)
    assert out["approval"] == AP.APPROVE and out["approved_option"]["room"] == "6인실 B"
    v = values(rt, inst)
    assert (v["approved_by"], v["approved_role"], v["approved_option"]["slot"]) == (ORG, ROLE, "금 10:00")
    assert v["approval"] == AP.APPROVE and v["approval_reason"] == "추천안대로"
    assert cal.calls == [("gcal", "create_event", {"slot": "금 10:00", "room": "6인실 B", "organizer": ORG}, cal.calls[0][3])]
    done = rt.repo.get_instance(inst["proc_inst_id"])
    rep = engine.variables(done)["result_report"]
    assert done["status"] == "COMPLETED" and rep["outcome"] == "정상" and rep["summary"] == "금 10:00 · 6인실 B"
    assert rep["facts"]["approved_option"]["slot"] == "금 10:00" and rep["facts"]["approved_by"] == ORG
    ev = [e for e in rt.repo.list_events(proc_inst_id=inst["proc_inst_id"]) if e["job_id"] == "APPROVAL_ACCEPTED"]
    assert ev and ev[0]["data"]["option"]["slot"] == "금 10:00" and ev[0]["todo_id"] == wi["id"]


def test_a_losing_option_can_be_chosen_and_is_what_the_effect_gets(case):
    rt, cal, start = case
    inst, wi = start()
    rt.approve(wi["id"], AP.APPROVE, "다음 주 화 15:00", ORG, ROLE, now=NOW)
    assert cal.calls[0][2]["slot"] == "다음 주 화 15:00" and values(rt, inst)["approved_option"]["room"] == "6인실 A"


def test_reject_needs_a_reason_writes_nothing_outside_and_reports_rejection(case):
    rt, cal, start = case
    inst, wi = start()
    with pytest.raises(ValueError, match="반려 사유"):
        rt.approve(wi["id"], AP.REJECT, None, ORG, ROLE, "  ", now=NOW)
    rt.approve(wi["id"], AP.REJECT, None, ORG, ROLE, "고객이 다음 분기로 미룸", now=NOW)
    v = values(rt, inst)
    assert cal.calls == [] and v["approval"] == AP.REJECT and v["approved_by"] is None and v["approved_option"] is None
    done = rt.repo.get_instance(inst["proc_inst_id"])
    rep = v["result_report"]
    assert done["status"] == "COMPLETED" and (rep["outcome"], rep["level"]) == ("반려", "info")
    assert rep["summary"] == "사유: 고객이 다음 분기로 미룸" and _row(rt, inst, "T_event")["status"] not in ("SUBMITTED", "DONE")
    assert any(e["job_id"] == "APPROVAL_REJECTED" for e in rt.repo.list_events(proc_inst_id=inst["proc_inst_id"]))


# ---------------------------------------------------------------- 실행: 거절되는 승인
@pytest.mark.parametrize("by,role,phrase", [
    ("주관자", ROLE, "'나'"),                           # 자유 입력 — 누가 승인했는지 모름
    (STRANGER, "role:operator", "주관자 역할의 일"),    # 다른 역할로
    (OTHER, ROLE, "역할이 아니어서"),                    # 주관자 역할을 내세웠지만 구성원이 아님
])
def test_approval_without_the_right_person_is_refused_and_changes_nothing(case, by, role, phrase):
    rt, cal, start = case
    inst, wi = start()
    with pytest.raises(PermissionError, match=phrase):
        rt.approve(wi["id"], AP.APPROVE, "금 10:00", by, role, now=NOW)
    assert rt.repo.get_workitem(wi["id"])["status"] == "IN_PROGRESS" and "approved_by" not in values(rt, inst) and cal.calls == []


@pytest.mark.parametrize("proposal,option,phrase", [
    ({"recommended": "x"}, "x", "처리 건에 없습니다"),                                       # 에이전트가 안을 내지 않음
    ({"options": []}, "x", "비어 있거나"),
    ({"options": [{"room": "B"}]}, "x", "구분 칸 'slot'"),
    ({"options": [{"slot": "a"}, {"slot": "a"}]}, "a", "두 번"),
    (PROPOSAL, "토 09:00", "있는 안: 금 10:00, 다음 주 화 15:00"),                            # 목록에 없는 안
    (PROPOSAL, None, "안을 고르세요"),
])
def test_missing_or_unknown_options_refuse_the_approval(case, proposal, option, phrase):
    rt, cal, start = case
    inst, wi = start(proposal)
    with pytest.raises(ValueError, match=phrase):
        rt.approve(wi["id"], AP.APPROVE, option, ORG, ROLE, now=NOW)
    assert rt.repo.get_workitem(wi["id"])["status"] == "IN_PROGRESS" and cal.calls == []


def test_an_approval_already_given_cannot_be_given_again_nor_turned_into_a_rejection(case):
    rt, cal, start = case
    inst, wi = start()
    rt.approve(wi["id"], AP.APPROVE, "금 10:00", ORG, ROLE, now=NOW)
    for decision in (AP.APPROVE, AP.REJECT):
        with pytest.raises(ValueError, match="이미 처리된 승인"):
            rt.approve(wi["id"], decision, "다음 주 화 15:00", ORG, ROLE, "바꿈", now=NOW)
    assert len(cal.calls) == 1 and values(rt, inst)["approved_option"]["slot"] == "금 10:00"


def test_unknown_decision_word_is_refused(case):
    rt, _, start = case
    _, wi = start()
    with pytest.raises(ValueError, match="승인 결정"):
        rt.approve(wi["id"], "ok", "금 10:00", ORG, ROLE, now=NOW)


def test_the_effect_refuses_to_run_without_an_approval_record(case):
    rt, cal, start = case
    inst, wi = start()
    fake = {"id": "fake", "proc_inst_id": inst["proc_inst_id"], "activity_id": "T_event", "activity_name": "일정 등록",
            "proc_def_id": "qbr", "version": "1", "tenant_id": "hyd"}
    with pytest.raises(ValueError, match="사람 승인 뒤에만"):
        rt._run_mcp_call(rt.repo.get_instance(inst["proc_inst_id"]), fake, NOW)
    assert cal.calls == []


# ---------------------------------------------------------------- API: 승인 경로 · 일반 제출 우회 금지
def test_api_routes_approval_through_the_role_check_and_blocks_the_generic_submit(case):
    rt, cal, start = case
    inst, wi = start()
    app = FastAPI()
    instance_mode.mount(app, "instance")
    c = TestClient(app)
    url = f"/api/todolist/{wi['id']}"
    assert c.post(url + "/submit", json={"output": {"approval": AP.APPROVE}, "by": ORG}).status_code == 403
    assert c.post(url + "/approve", json={"decision": AP.APPROVE, "option": "금 10:00", "by": OTHER, "role": ROLE}).status_code == 403
    assert c.post(url + "/approve", json={"decision": AP.APPROVE, "option": "토 09:00", "by": ORG, "role": ROLE}).status_code == 400
    assert c.post("/api/todolist/nope/approve", json={"decision": AP.APPROVE, "option": "x", "by": ORG, "role": ROLE}).status_code == 404
    assert cal.calls == []
    r = c.post(url + "/approve", json={"decision": AP.APPROVE, "option": "금 10:00", "by": ORG, "role": ROLE})
    assert r.status_code == 200, r.text
    assert len(cal.calls) == 1
    assert c.post(url + "/approve", json={"decision": AP.APPROVE, "option": "금 10:00", "by": ORG, "role": ROLE}).status_code == 400


# ---------------------------------------------------------------- 사전 검사: 반려(또는 조건 없는) 경로로 효과에 닿으면 거절
def _effect_problems(r):
    return [p for p in r["problems"] if (p.get("where") or {}).get("id") == "T_event" and "반려(또는 조건 없는) 경로" in p["reason"]]


def test_rejection_branch_leading_to_the_effect_is_refused_with_the_path(world):
    m = mapping()
    m["flows"] = {"F_yes": {"var": "approval", "op": "==", "value": AP.REJECT}, "F_no": {"default": True}}   # 반려 → 일정 등록 (뒤바뀜)
    _, r = imported(world, m)
    found = _effect_problems(r)
    assert not r["ok"] and len(found) == 1, r["problems"]
    assert found[0]["field"] == "part" and "경로: '주관자 승인' → '승인?' → '일정 등록'" in found[0]["reason"]
    assert "approval == '승인'" in found[0]["reason"]


def test_approval_wired_straight_to_the_effect_without_a_branch_is_refused(world):
    src = FLOW.replace('<bpmn:sequenceFlow id="F3" sourceRef="T_approve" targetRef="G_ok"/>',
                       '<bpmn:sequenceFlow id="F3" sourceRef="T_approve" targetRef="T_event"/>')
    src = src.replace('<bpmn:sequenceFlow id="F_yes" name="승인" sourceRef="G_ok" targetRef="T_event"/>',
                      '<bpmn:sequenceFlow id="F_yes" name="승인" sourceRef="G_ok" targetRef="R_ok"/>')
    src = src.replace('<bpmn:sequenceFlow id="F4" sourceRef="T_event" targetRef="R_ok"/>',
                      '<bpmn:sequenceFlow id="F4" sourceRef="T_event" targetRef="G_ok"/>')
    rt = world["rt"]
    base = rt.definition_for({"proc_def_id": rt.defn.id, "proc_def_version": rt.base_version, "tenant_id": rt.tenant_id}).raw
    cat = B.catalog(base, USERS)
    r = B.check(B.parse_bpmn(src), mapping(), {"catalog": cat, "definition_id": "qbr", "version": "1", "file_name": "x.bpmn", "xml_sha256": "x"})
    found = _effect_problems(r)
    assert len(found) == 1 and "경로: '주관자 승인' → '일정 등록'" in found[0]["reason"], r["problems"]


def test_not_rejected_condition_also_counts_as_the_approval_gate(world):
    m = mapping()
    m["flows"]["F_yes"] = {"var": "approval", "op": "!=", "value": AP.REJECT}
    _, r = imported(world, m)
    assert r["ok"], r["problems"]


def test_reference_and_c3_flows_still_pass_the_approval_path_check(world):
    """판단 엔진 카드 승인(select_card)은 반려를 내지 않는다 — 기준 흐름 A · B · C · 정비형과 C3 흐름 세 개 모두 그대로 통과한다."""
    import test_c2_execution as c2
    import test_c3_assembly as c3
    for src, m, did in ((c2.A_FLOW, c2.a_mapping(), "a"), (c2.B_FLOW, c2.b_mapping(), "b"), (c2.C_FLOW, c2.c_mapping(), "c"),
                        (c2.MAINT, c2.maint_mapping(), "maint")):
        _, r = c2.imported(world, src, m, did)
        assert r["ok"], (did, r["problems"])
    rt = world["rt"]
    base = rt.definition_for({"proc_def_id": rt.defn.id, "proc_def_version": rt.base_version, "tenant_id": rt.tenant_id}).raw
    cat = B.catalog(base, c3.AGENTS)
    for did, (_, src, m) in c3._flows().FLOWS.items():
        r = B.check(B.parse_bpmn(src), deepcopy(m), {"catalog": cat, "definition_id": did, "version": "1", "file_name": "x", "xml_sha256": "x"})
        assert r["ok"], (did, r["problems"])
