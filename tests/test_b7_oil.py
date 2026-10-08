"""B7 (확정 TODO B7): 작동유 열화 — 사람 입력(오일 분석 기준 이탈)으로 시작하는 정비형 흐름이 끝까지.

  1. 사람 입력 경보: 입력 → 센서 경보와 같은 계약의 경보(pattern OIL_ANALYSIS, 출처 사람 입력, 입력자) → 같은 경보 경로(처리 건 · 사건).
     기준 이탈이 아니면 경보 없음 + 사유. 이 패턴을 받는 배포 흐름이 없으면 기준 흐름의 사람 검토(alert_triage)로.
  2. 학생이 그릴 법한 작동유 흐름(tests/fixtures/bpmn/oil_maintenance_student.bpmn — 시험용, 정답 아님)을 B3 로 가져와 B4 로 배포 →
     오일 분석 입력 → 원인 진단(내장 결정론 판단) → 카드 → 정비관리자 승인 → 작업지시(설비 명령 0건) → 재분석 입력 → 정상이면 종결,
     비정상이면 새 판단 · 승인 · 작업지시로 다시.
  3. 사전 검사: 사람 입력 경보 시작 + 승인 + 작업지시는 통과, 승인 없는 설비 명령 · 작업지시는 여전히 거절.
  4. 결정론 판단(agent): 사람 입력 결과가 근거, HM-9 적재 전(조치 없음 → 사유) · 후(SOP-OIL-21) 차이.
"""
import json
import re
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from procsvc import bpmn_import as B, decisions as declib, engine, human_alert, instance_mode, machine
from procsvc.bpmn_store import FlowStore
from procsvc.legacy_assessment import LegacyAssessment
from test_instance_mode import NOW, NoFx, world  # noqa: F401  (world = fixture)

ROOT = Path(__file__).resolve().parents[1]
BASE = json.loads((ROOT / "it/process/definitions/anomaly_response_v22.json").read_text(encoding="utf-8"))
OIL_BPMN = (ROOT / "tests/fixtures/bpmn/oil_maintenance_student.bpmn").read_text(encoding="utf-8")
MAINT = {"id": "role:maint-mgr", "username": "정비관리자", "is_agent": False, "tenant_id": "hyd"}
ENTRY = {"pattern": "OIL_ANALYSIS", "asset": "HYD-01", "item": "water", "value": 620, "out_of_spec": True,
         "memo": "정기 분석 — 수분 증가", "by": "user:kim", "by_name": "김정비", "role": "role:maint-mgr"}

DIAG, CAND, COMP, RANK = "Activity_0diag7o", "Activity_1cand2o", "Activity_0comp3o", "Activity_1rank4o"
SELECT, WO, RECHECK, BOSS = "Activity_0slct5o", "Activity_1wo7o", "Activity_1chk8o", "Activity_0boss1o"


def oil_mapping(parsed, cat):
    """학생이 포털 매핑 표에서 고를 법한 것(그림 이름을 보고 부품 · 담당 · 조건을 고름)."""
    m, _ = B.merge_mapping(parsed, None, cat)
    m["start"] = {"kind": "alert", "patterns": ["OIL_ANALYSIS"]}
    m["tasks"] = {DIAG: {"part": "task:diagnose"}, CAND: {"part": "task:candidates"}, COMP: {"part": "task:compliance"},
                  RANK: {"part": "task:rank"}, SELECT: {"part": "task:select", "role": "정비관리자"}, WO: {"part": "task:work-order"},
                  RECHECK: {"part": "human", "role": "정비관리자", "inputs": ["work_order"],
                            "fields": [{"key": "recheck_result", "text": "재분석 결과", "type": "select", "items": ["정상", "비정상"]},
                                       {"key": "recheck_note", "text": "메모", "type": "textarea", "required": False}]},
                  BOSS: {"part": "human", "role": "생산관리자", "inputs": ["decision"],
                         "fields": [{"key": "boss_note", "text": "확인 메모", "type": "textarea", "required": False}]}}
    m["flows"] = {"Flow_0ok9": {"var": "recheck_result", "op": "==", "value": "정상"}, "Flow_1again": {"default": True}}
    return m


def oil_check(mapping=None):
    parsed = B.parse_bpmn(OIL_BPMN)
    cat = B.catalog(BASE, [MAINT])
    return parsed, cat, B.check(parsed, mapping or oil_mapping(parsed, cat), {"catalog": cat, "definition_id": "my_oil", "version": "1"})


def reasons(result):
    return [p["reason"] for p in result["problems"]]


# ---------------------------------------------------------------- 1. 사람 입력 → 경보 (형식 · 사유)
def test_out_of_spec_entry_becomes_an_alert_of_the_detector_contract():
    alert, why = human_alert.build_alert(ENTRY, now=NOW)
    assert {k for k in alert} >= {"alertId", "asset", "pattern", "severity", "state", "t", "evidence"}   # det/cep.py _alert 와 같은 칸
    assert (alert["asset"], alert["pattern"], alert["state"], alert["source"]) == ("HYD-01", "OIL_ANALYSIS", "RAISE", "human_input")
    assert alert["enteredBy"] == {"id": "user:kim", "name": "김정비", "role": "role:maint-mgr"}
    assert alert["evidence"]["oil_analysis_out_of_spec"] is True and alert["evidence"]["value"] == 620
    assert alert["alertId"].startswith("HYD-01-OIL_ANALYSIS-H20261003") and "경보" in why
    assert human_alert.build_alert(ENTRY, now=NOW)[0]["alertId"] != alert["alertId"]           # 입력 하나 = 경보 하나


def test_in_spec_entry_makes_no_alert_and_says_why():
    alert, why = human_alert.build_alert(dict(ENTRY, out_of_spec=False))
    assert alert is None and "기준 안" in why and "처리 건은 열리지 않습니다" in why


@pytest.mark.parametrize("change,field", [({"pattern": "COOLER_DEGRADATION"}, "pattern"), ({"asset": "HYD-09"}, "asset"),
                                          ({"item": "colour"}, "item"), ({"out_of_spec": "예"}, "out_of_spec"),
                                          ({"by": ""}, "by"), ({"value": "많음"}, "value"), ({"value": float("nan")}, "value")])
def test_bad_entry_is_refused_with_the_field(change, field):
    with pytest.raises(ValueError, match=f"\\({field}"):
        human_alert.build_alert(dict(ENTRY, **change))


def test_registry_matches_the_seeded_knowledge():
    """사람 입력 패턴 계약의 지식 id · 입력 변수가 시드(knowledge_a098.cypher)에 그대로 있는가 — 이름만 맞춘 가짜 계약을 막는다."""
    seed = (ROOT / "it/neo4j/v2/knowledge_a098.cypher").read_text(encoding="utf-8")
    k = human_alert.PATTERNS["OIL_ANALYSIS"]["knowledge"]
    assert re.search(r"AnomalyPattern \{id: '%s'\}\)\s*\n\s*SET .*p\.code = 'OIL_ANALYSIS'" % re.escape(k["pattern"]), seed)
    assert f"InputData {{id: '{k['input']}'}}) SET i.name" in seed and f"i.variable = '{k['variable']}'" in seed
    assert f"Symptom {{id: '{k['symptom']}'}}" in seed
    assert "rule:cand-oil" in seed and "rule:dx-oil" in seed


# ---------------------------------------------------------------- 1'. API: 같은 경보 경로 · 배포 없으면 사람 검토
@pytest.fixture
def api(world):
    from procsvc import alert_policy  # noqa: F401
    rt = world["rt"]
    rt.repo.upsert_user(dict(MAINT))
    admitted, audit = [], []

    async def admit(alert):
        admitted.append(alert)
        rt.on_alert_raise(alert)                       # main._admit_human_alert 의 원천 접수 없는 갈래(PROCESS_REPO=memory)와 같다

    def open_alerts():
        return [(i.card.get("alert") or {}, i.state) for i in world["incidents"].values() if i.state not in ("CLOSED", "ESCALATED")]
    app = FastAPI()
    human_alert.register(app, runtime_factory=lambda: rt, admit=admit, open_alerts=open_alerts,
                         audit=lambda *a, **k: audit.append(a[2]))
    return TestClient(app), world, admitted, audit


def test_without_a_deployed_oil_flow_the_alert_goes_to_human_review(api):
    c, world, admitted, audit = api
    r = c.post("/api/human-alerts", json=ENTRY)
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["raised"] and v["route"] == "triage" and {k: v["definition"][k] for k in ("definition", "version")} == {"definition": "alert_triage", "version": "1.0"} and v["definition"]["name"]
    assert "사람 검토" in v["route_text"] and admitted[0]["source"] == "human_input"
    inst = world["rt"].repo.get_instance(v["instance"])
    assert inst["proc_def_id"] == "alert_triage" and engine.variables(inst)["alert"] == admitted[0]
    inc = world["incidents"][v["incident"]]
    assert inc.state == "ESCALATED" and inc.reason == "UNSUPPORTED_ALERT_PATTERN"      # 기존 경로 그대로: 사람 검토
    assert audit == ["HUMAN_ALERT_RAISED"]


def test_in_spec_entry_opens_nothing(api):
    c, world, admitted, audit = api
    r = c.post("/api/human-alerts", json=dict(ENTRY, out_of_spec=False))
    assert r.status_code == 200 and r.json()["raised"] is False and "기준 안" in r.json()["reason"]
    assert admitted == [] and world["incidents"] == {} and world["rt"].repo.list_instances() == []
    assert audit == ["HUMAN_INPUT_IN_SPEC"]


def test_bad_entry_is_400_and_form_lists_items(api):
    c, *_ = api
    r = c.post("/api/human-alerts", json=dict(ENTRY, item="colour"))
    assert r.status_code == 400 and "item" in r.json()["detail"]
    f = c.get("/api/human-alerts/form").json()
    assert f["assets"] == ["HYD-01", "HYD-02", "HYD-03"] and [i["key"] for i in f["patterns"][0]["items"]] == ["tan", "water", "cleanliness", "viscosity"]
    assert c.get("/api/human-alerts/current", params={"asset": "HYD-01", "pattern": "OIL_ANALYSIS"}).status_code == 404


def test_api_needs_instance_mode():
    app = FastAPI()

    async def admit(alert):
        raise AssertionError("legacy mode must not admit")
    human_alert.register(app, runtime_factory=lambda: None, admit=admit)
    assert TestClient(app).post("/api/human-alerts", json=ENTRY).status_code == 409


# ---------------------------------------------------------------- 3. 사전 검사(B3)
def test_catalog_offers_the_human_input_pattern_but_message_default_stays_sensor():
    cat = B.catalog(BASE, [MAINT])
    assert "OIL_ANALYSIS" in cat["patterns"] and cat["human_patterns"] == ["OIL_ANALYSIS"]
    assert BASE["alertPolicy"]["patterns"].keys() == {"COOLER_DEGRADATION", "PUMP_LEAKAGE", "FAN_VIBRATION"}   # 기준 정의는 그대로
    redraw = B.parse_bpmn((ROOT / "tests/fixtures/bpmn/anomaly_response_redraw.bpmn").read_text(encoding="utf-8"))
    m, _ = B.merge_mapping(redraw, None, cat)
    assert m["start"]["patterns"] == ["COOLER_DEGRADATION", "PUMP_LEAKAGE", "FAN_VIBRATION"]   # 사람 입력은 사람이 고른다


def test_human_input_alert_start_with_approval_and_work_order_passes_the_check():
    _, _, r = oil_check()
    assert r["ok"], r["problems"]
    d = r["definition"]
    assert d["events"][0]["eventDefinition"] == "message" and list(d["alertPolicy"]["patterns"]) == ["OIL_ANALYSIS"]
    assert d["alertPolicy"]["unsupported"] == {"definition": "alert_triage", "version": "1.0"} and d["loopPolicy"] == "guarded"
    tools = {a["id"]: a["tool"] for a in d["activities"]}
    assert "incident:command" not in tools.values() and tools[WO] == "enterprise:WO_CREATE"      # 설비 명령 없는 정비형
    assert next(a for a in d["activities"] if a["id"] == SELECT)["role"] == "정비관리자"


def test_command_or_work_order_without_approval_is_still_refused():
    parsed = B.parse_bpmn(OIL_BPMN)
    cat = B.catalog(BASE, [MAINT])
    # 승인(조치 선택)을 일반 사람 task 로 바꾸면 작업지시 앞에 승인이 없다
    m = oil_mapping(parsed, cat)
    m["tasks"][SELECT] = {"part": "human", "role": "정비관리자", "inputs": ["decision"],
                          "fields": [{"key": "chosen_skill", "text": "고른 조치", "type": "text"}]}
    r = B.check(parsed, m, {"catalog": cat, "definition_id": "my_oil", "version": "1"})
    assert not r["ok"] and any("작업지시 부품 앞 경로에 사람 승인" in x for x in reasons(r))
    # 작업지시 칸에 설비 명령 부품을 꽂고 승인을 빼면 — 승인 없는 설비 명령
    m["tasks"][WO] = {"part": "task:command"}
    r = B.check(parsed, m, {"catalog": cat, "definition_id": "my_oil", "version": "1"})
    assert any("설비 명령 부품 앞 경로에 사람 승인" in x for x in reasons(r))
    # 다시 판단으로 되돌아가는 선을 작업지시로 바로 돌리면 — 승인 없이 작업지시를 다시 실행
    xml = OIL_BPMN.replace('targetRef="Activity_0diag7o" />', 'targetRef="Activity_1wo7o" />').replace(
        'sourceRef="StartEvent_0oil1n" targetRef="Activity_1wo7o" />', 'sourceRef="StartEvent_0oil1n" targetRef="Activity_0diag7o" />')
    parsed = B.parse_bpmn(xml)
    r = B.check(parsed, oil_mapping(parsed, cat), {"catalog": cat, "definition_id": "my_oil", "version": "1"})
    assert any("되돌아가는 선이 작업지시 부품을 사람 승인 없이" in x for x in reasons(r))


# ---------------------------------------------------------------- 2. 정비형 흐름 끝까지 (수업 기본 경로 AGENT_BRIDGE=legacy)
def _oil_option(sop="SOP-OIL-21", name="작동유 교체 절차", sid="skill:sop-oil-21"):
    return {"id": sid, "sopId": sop, "name": name, "kind": "work_order", "feasible": True, "rank": 1,
            "approver": {"id": "role:maint-mgr", "name": "정비관리자", "level": 2}, "actions": [],
            "steps": [{"id": f"{sid}:1", "order": 1, "text": "설비를 정지하고 잠금(LOTO)"}],
            "violations": [], "penalties": [], "warnings": [], "selectedBy": [{"rule": "rule:cand-oil"}]}


def _evaluation(alert, option):
    """agent /api/agent/evaluate 가 돌려주는 모양(EVALUATED) — 원인은 사람 입력 근거로 진단."""
    card = {"incident": None, "alert": alert, "causes": [{"id": "cause:oil-oxidation"}], "topCause": "cause:oil-oxidation",
            "recommended": [], "withheld": False, "evidence_status": {"status": "SUPPORTED"}}
    payload = {"schema": "v2", "asset": alert["asset"], "recommended": option["id"], "explanation": "작동유 열화 — 후보 1장",
               "origin": {"kind": "alert", "alertId": alert["alertId"], "pattern": "OIL_ANALYSIS",
                          "cause": "cause:oil-oxidation", "failureMode": "fm:oil-degradation"},
               "options": [option], "roles": {"role:operator": {"level": 1}, "role:maint-mgr": {"level": 2}, "role:prod-mgr": {"level": 2}}}
    return {"status": "EVALUATED", "evaluation": payload, "card": card}


def _oil_world(world):
    rt = world["rt"]
    rt.repo.upsert_user(dict(MAINT))
    _, _, r = oil_check()
    assert r["ok"], r["problems"]
    raw = FlowStore(rt.repo, rt.tenant_id).register(r["definition"], OIL_BPMN, "oil.bpmn")
    rt.deploy_definition("my_oil", raw["version"], by="학생1", reason="작동유 흐름 시험")
    commands = []
    world["ctx"].approve_incident = lambda inc, by, cmds: commands.append(cmds) or pytest.fail("설비 명령이 나갔다")

    def publish(payload, card):
        d = declib.new(payload)
        world["book"][d["id"]] = d
        rt.hooks.update_incident_card(payload["origin"]["incident"], card)
        return d
    evaluations = []

    def evaluate(alert):
        evaluations.append(alert)
        return deepcopy(_evaluation(alert, _oil_option(name=f"작동유 교체 절차 {len(evaluations)}회")))
    worker = LegacyAssessment(rt, evaluate, publish, instance_mode._bridge_legacy_agent)
    return rt, raw, worker, evaluations, commands


def _rows(rt, inst):
    return rt.repo.list_workitems(proc_inst_id=inst["proc_inst_id"], limit=None)


def _live(rt, inst, aid):
    return next(w for w in _rows(rt, inst) if w["activity_id"] == aid and w["status"] in ("IN_PROGRESS", "TODO", "SUBMITTED"))


def _round(rt, inst, worker, inc, n):
    """한 바퀴: 결정론 판단 → 카드 → 정비관리자 승인 → 작업지시(실제 CMMS 응답) → 재분석 task 열림."""
    assert worker.tick() == 1
    rows = _rows(rt, inst)
    for aid in (DIAG, CAND, COMP, RANK):
        assert [w["status"] for w in rows if w["activity_id"] == aid].count("DONE") == n, aid
    sel = _live(rt, inst, SELECT)
    d_id = engine.variables(rt.repo.get_instance(inst["proc_inst_id"]))["decision_id"]
    assert inc.state == "AWAITING_APPROVAL"
    with pytest.raises(PermissionError):                                  # 운전원은 정비 카드를 승인할 수 없다(정비관리자 이상)
        rt.select(sel["id"], d_id, "skill:sop-oil-21", by="박운전", role="role:operator", now=NOW)
    rt.select(sel["id"], d_id, "skill:sop-oil-21", by="김정비", role="role:maint-mgr", reason="수분 증가 — 교체", now=NOW)
    return d_id


def test_maintenance_flow_runs_to_the_end_without_any_plant_command(world):
    rt, raw, worker, evaluations, commands = _oil_world(world)
    alert, _ = human_alert.build_alert(ENTRY, now=NOW)
    policy = rt.alert_policy("OIL_ANALYSIS")
    assert policy["route"] == "response" and policy["target"] == {"definition": "my_oil", "version": raw["version"]}
    inst = rt.on_alert_raise(alert, now=NOW)
    assert inst["proc_def_id"] == "my_oil"
    inc = next(iter(world["incidents"].values()))
    assert inc.state == "AWAITING_APPROVAL" and inc.pattern == "OIL_ANALYSIS" and inc.card["alert"]["source"] == "human_input"
    d_id = _round(rt, inst, worker, inc, 1)
    assert evaluations == [alert]                                          # 진단은 사람이 입력한 원래 경보를 그대로 받는다
    assert world["executed"] == [(d_id, "WO_CREATE")] and commands == []   # 작업지시만, 설비 명령 0건
    assert inc.cmd_id is None and inc.state == "CLOSED" and inc.work_order["id"] == "WO-1003-AB12"
    assert inc.history[-2]["state"] == "WORK_ORDER_CREATED"
    wo = next(w for w in _rows(rt, inst) if w["activity_id"] == WO)
    assert wo["status"] == "DONE" and wo["output"]["work_order"]["ref"] == "WO-1003-AB12"
    chk = _live(rt, inst, RECHECK)
    assert chk["status"] == "IN_PROGRESS" and rt.repo.get_instance(inst["proc_inst_id"])["status"] == "RUNNING"
    rt.poll_once(now=NOW)                                                  # 사건이 닫혀도 재분석 입력은 그대로 기다린다(조치 전 종료로 오인하지 않음)
    assert _live(rt, inst, RECHECK)["id"] == chk["id"]
    rt.submit(chk["id"], {"recheck_result": "정상", "recheck_note": "교체 뒤 수분 150 ppm"}, by="김정비", now=NOW)
    done = rt.repo.get_instance(inst["proc_inst_id"])
    assert done["status"] == "COMPLETED" and done["end_event"] == "Event_1done0o"
    assert not any(w["activity_id"] == BOSS for w in _rows(rt, inst))


def test_abnormal_recheck_goes_back_to_a_new_judgment_approval_and_work_order(world):
    rt, raw, worker, evaluations, commands = _oil_world(world)
    alert, _ = human_alert.build_alert(ENTRY, now=NOW)
    inst = rt.on_alert_raise(alert, now=NOW)
    inc = next(iter(world["incidents"].values()))
    first = _round(rt, inst, worker, inc, 1)
    rt.submit(_live(rt, inst, RECHECK)["id"], {"recheck_result": "비정상", "recheck_note": "수분 그대로"}, by="김정비", now=NOW)
    # 되돌아가는 선 → 원인 진단 새 행, 사건은 다음 승인을 기다린다(첫 작업지시는 superseded 로 보존)
    assert inc.state == "AWAITING_APPROVAL" and inc.work_order is None and inc.cmd_id is None
    assert inc.superseded[-1]["kind"] == "recheck" and inc.superseded[-1]["workOrder"]["id"] == "WO-1003-AB12"
    assert _live(rt, inst, DIAG)["status"] == "IN_PROGRESS"
    # 승인된 첫 판단이 새 바퀴를 채우지 않는다(내장 판단 복구 경로) — 새 평가만
    instance_mode.reconcile_legacy_decisions()
    assert _live(rt, inst, DIAG)["output"] is None
    second = _round(rt, inst, worker, inc, 2)
    assert second != first and len(evaluations) == 2
    assert world["executed"] == [(first, "WO_CREATE"), (second, "WO_CREATE")] and commands == [] and inc.cmd_id is None
    assert inc.state == "CLOSED" and len([w for w in _rows(rt, inst) if w["activity_id"] == WO and w["status"] == "DONE"]) == 2
    rt.submit(_live(rt, inst, RECHECK)["id"], {"recheck_result": "정상"}, by="김정비", now=NOW)
    assert rt.repo.get_instance(inst["proc_inst_id"])["status"] == "COMPLETED"
    events = {e["job_id"] for e in rt.repo.list_events(proc_inst_id=inst["proc_inst_id"])}
    assert "INCIDENT_REOPENED_RECHECK" in events


def test_reopen_lost_after_commit_is_redone_by_polling(world, monkeypatch):
    """재분석 제출 커밋 뒤 사건 다시 열기가 실패해도(재기동 등) 다음 폴링이 다시 연다."""
    rt, raw, worker, *_ = _oil_world(world)
    alert, _ = human_alert.build_alert(ENTRY, now=NOW)
    inst = rt.on_alert_raise(alert, now=NOW)
    inc = next(iter(world["incidents"].values()))
    _round(rt, inst, worker, inc, 1)
    hook = rt.hooks.reopen_for_recheck
    rt.hooks.reopen_for_recheck = None                                    # 커밋 뒤 효과가 실패(로그만)
    rt.submit(_live(rt, inst, RECHECK)["id"], {"recheck_result": "비정상"}, by="김정비", now=NOW)
    assert inc.state == "CLOSED"
    rt.hooks.reopen_for_recheck = hook
    rt.poll_once(now=NOW)
    assert inc.state == "AWAITING_APPROVAL" and inc.superseded[-1]["kind"] == "recheck"
    rt.poll_once(now=NOW)
    assert len(inc.superseded) == 1                                        # 같은 행으로 두 번 열지 않는다


def test_recheck_reopen_is_limited_to_a_work_order_only_closure():
    inc = machine.Incident.from_card("INC-1", {"alert": {"alertId": "a", "asset": "HYD-01", "pattern": "OIL_ANALYSIS"}},
                                     recovery_policy={"pattern": "OIL_ANALYSIS", "criterion": ["TS1", "<", 55.0]})
    machine.on_card(inc)
    with pytest.raises(ValueError, match="작업지시로 닫힌 사건만"):
        machine.on_recheck_reopen(inc, "r1", "김정비", "다시", NoFx())       # 아직 열린 사건
    machine.on_work_order(inc, {"ok": True, "ref": "WO-1"}, NoFx(), work_order_only=True)
    assert machine.on_recheck_reopen(inc, "r1", "김정비", "다시", NoFx()) is True and inc.state == "AWAITING_APPROVAL"
    assert machine.on_recheck_reopen(inc, "r1", "김정비", "다시", NoFx()) is False      # 같은 요청은 한 번
    cmd = machine.Incident.from_card("INC-2", {"alert": {"alertId": "b", "asset": "HYD-01", "pattern": "COOLER_DEGRADATION"}})
    cmd.state, cmd.cmd_id, cmd.work_order = "CLOSED", "CMD-1", {"id": "WO-2"}
    with pytest.raises(ValueError, match="명령 CMD-1"):
        machine.on_recheck_reopen(cmd, "r2", "김정비", "다시", NoFx())       # 설비 명령을 낸 사건은 열지 않는다


def test_a_loop_that_does_not_return_to_an_approval_does_not_reopen(world):
    """재분석만 다시 하는 반복(승인으로 돌아가지 않음)은 사건을 다시 열지 않는다."""
    rt, raw, worker, *_ = _oil_world(world)
    _, cat, _ = oil_check()
    parsed = B.parse_bpmn(OIL_BPMN.replace('name="비정상 — 다시 판단" sourceRef="Gateway_0chk9o" targetRef="Activity_0diag7o"',
                                           'name="다시 측정" sourceRef="Gateway_0chk9o" targetRef="Activity_1chk8o"'))
    r = B.check(parsed, oil_mapping(parsed, cat), {"catalog": cat, "definition_id": "oil_measure", "version": "1"})
    assert r["ok"], r["problems"]
    raw2 = FlowStore(rt.repo, rt.tenant_id).register(r["definition"], OIL_BPMN, "m.bpmn")
    rt.deploy_definition("oil_measure", raw2["version"], by="학생1", reason="반복 측정")
    alert, _ = human_alert.build_alert(ENTRY, now=NOW)
    inst = rt.on_alert_raise(alert, now=NOW)
    assert inst["proc_def_id"] == "oil_measure"
    inc = next(i for i in world["incidents"].values() if i.alert_id == alert["alertId"])
    _round(rt, inst, worker, inc, 1)
    rt.submit(_live(rt, inst, RECHECK)["id"], {"recheck_result": "비정상"}, by="김정비", now=NOW)
    assert inc.state == "CLOSED" and _live(rt, inst, RECHECK)["status"] == "IN_PROGRESS"


def test_current_human_alert_is_served_to_the_diagnosis_tool(api):
    c, world, admitted, _ = api
    rt = world["rt"]
    _oil_world(world)
    v = c.post("/api/human-alerts", json=ENTRY).json()
    assert v["route"] == "response" and v["definition"]["definition"] == "my_oil" and "배포된 흐름" in v["route_text"]
    got = c.get("/api/human-alerts/current", params={"asset": "HYD-01", "pattern": "OIL_ANALYSIS"}).json()
    assert got["alert"] == admitted[0] and got["incident_state"] == "AWAITING_APPROVAL"
    assert c.get("/api/human-alerts/current", params={"asset": "HYD-02", "pattern": "OIL_ANALYSIS"}).status_code == 404
    assert rt.repo.get_instance(v["instance"])["proc_def_id"] == "my_oil"


# ---------------------------------------------------------------- 4. 결정론 판단(agent): 사람 입력 근거 · HM-9 적재 전/후
OIL_T1 = [{"causeId": c, "cause": n, "prior": p, "failureModeId": "fm:oil-degradation", "failureMode": "작동유 열화",
           "symptoms": ["오일 분석 기준 이탈"], "evidence": []}
          for c, n, p in (("cause:oil-oxidation", "고온 운전에 의한 산화", 0.4), ("cause:water-ingress", "수분 혼입", 0.25),
                          ("cause:particle-contamination", "오염 입자 유입", 0.25), ("cause:change-interval-exceeded", "교환 주기 초과", 0.1))]


def test_human_entered_analysis_is_the_evidence_of_a_sensorless_pattern():
    from agentsvc import card, guardrail
    alert, _ = human_alert.build_alert(ENTRY, now=NOW)
    # 사람 입력이 없으면(또는 기준 안) 지금처럼 근거 없음 → 보류
    bare = card.rank_causes(OIL_T1, {})
    assert card.evidence_status(bare)["withheld"] and card.with_human_evidence(OIL_T1, {"asset": "HYD-01", "pattern": "OIL_ANALYSIS"}) == (OIL_T1, {})
    rows, results = card.with_human_evidence(OIL_T1, alert)
    causes = card.rank_causes(rows, results)
    status = card.evidence_status(causes)
    assert status["status"] == "SUPPORTED" and [c["id"] for c in causes][0] == "cause:oil-oxidation"   # 지식의 사전확률 순서
    ev = causes[0]["evidence"][0]
    assert ev["id"] == f"human:{alert['alertId']}" and ev["status"] == "PASS" and ev["enteredBy"]["name"] == "김정비"
    guide = card.build_card(None, alert, causes, {}, {"ok": True})
    assert guardrail.check(guide) == [] and ev["id"] in guide["citations"]
    # 센서 증거가 있는 원인은 사람 입력으로 덮지 않는다
    sensor = [dict(OIL_T1[0], evidence=[{"id": "evd:x", "weight": 1}])]
    assert card.with_human_evidence(sensor, alert) == (sensor, {})
    # 출처 표시가 없는 경보는 사람 입력으로 보지 않는다
    assert card.human_evidence(dict(alert, source="detector")) is None


def _kg_with(outputs):
    from test_dmn_mcp import FakeKG

    class OilKG(FakeKG):
        def t1_causes(self, pattern, asset):
            self.calls.append(("t1", pattern))
            return deepcopy(OIL_T1) if pattern == "OIL_ANALYSIS" else super().t1_causes(pattern, asset)

        def t2_skills(self, cause):
            self.calls.append(("t2", cause))
            return []

        def dmn(self):
            from test_cards import DMN
            return [r for r in deepcopy(DMN) if r["decision"] == "dec:rank-actions"] + [
                {"decision": "dec:action-candidates", "rule": "rule:cand-oil", "ord": 8, "effect": "SELECT",
                 "when": "failure_mode == 'fm:oil-degradation'", "annotation": "작동유 열화 후보",
                 "tests": [{"variable": "failure_mode", "operator": "==", "value": "fm:oil-degradation"}],
                 "outputs": list(outputs), "applies": [], "sources": ["HM-9.4"]}]

        def skills(self, ids):
            return []

        def tradeoffs(self, ids):
            return []

        def precedents(self, fm):
            return []

        def suppliers(self):
            return {}

        def roles(self):
            return [{"id": "role:maint-mgr", "name": "정비관리자", "level": 2, "deptName": "정비팀"}]
    return OilKG()


def test_deterministic_pipeline_before_and_after_the_oil_manual(monkeypatch):
    """HM-9 적재 전: 후보 규칙 rule:cand-oil 이 내놓는 조치가 없음 → 보류 + 사유. 적재 뒤(규칙 → SOP-OIL-21): 카드가 나온다.
    그래프 대신 같은 경로(decide → cards.evaluate)를 흉내 낸 가짜 지식으로 본다."""
    from agentsvc import main
    from agentsvc.runs import Run
    alert, _ = human_alert.build_alert(ENTRY, now=NOW)
    monkeypatch.setattr(main.decidelib, "_get_json", lambda *_: {"route": "response"})
    monkeypatch.setattr(main.mcp_prom, "freshness", lambda *_: {"ok": True})
    monkeypatch.setattr(main.tsdb, "evaluate", lambda evidence, asset: {})
    monkeypatch.setattr(main.llm, "summarize", lambda card, fallback: (fallback, "fixture"))
    from agentsvc import forecasting
    monkeypatch.setattr(forecasting, "candidates", lambda kg, asset, skills: ({}, None))
    monkeypatch.setattr(main.decidelib, "gather_facts", lambda inputs, asset, known, tsdb: (dict(known), []))

    monkeypatch.setattr(main, "kg", _kg_with([]))
    before = Run("b7-before", alert["alertId"], "HYD-01", alert)
    main.pipeline(before, do_submit=False)
    assert before.status == "WITHHELD" and "rule:cand-oil" in (before.error or "") and "조치(SOP)가 없다" in before.error
    assert before.card["topCause"] == "cause:oil-oxidation" and not before.card["withheld"]   # 진단은 됐다(사람 입력 근거)

    kg = _kg_with(["skill:sop-oil-21"])
    kg.skill_rows = {"skill:sop-oil-21": {"skillId": "skill:sop-oil-21", "sopId": "SOP-OIL-21", "name": "작동유 교체 절차", "kind": "work_order",
                                          "approver": {"id": "role:maint-mgr", "name": "정비관리자", "level": 2}, "actions": [],
                                          "steps": [{"id": "s1", "order": 1, "text": "잠금"}], "addresses": []}}
    kg.skills = lambda ids: [kg.skill_rows[i] for i in ids if i in kg.skill_rows]
    monkeypatch.setattr(main, "kg", kg)
    after = Run("b7-after", alert["alertId"], "HYD-01", alert)
    main.pipeline(after, do_submit=False)
    assert after.status == "EVALUATED", after.error
    opts = after.evaluation["options"]
    assert [o["sopId"] for o in opts] == ["SOP-OIL-21"] and opts[0]["kind"] == "work_order" and opts[0]["actions"] == []
    assert after.evaluation["origin"]["failureMode"] == "fm:oil-degradation" and after.card["alert"] == alert


def test_real_worker_diagnosis_tool_reads_the_entered_analysis_from_the_process(monkeypatch):
    """실제 워커 경로: dmn-mcp diagnose(asset, pattern[, alert_id]) 는 사람 입력 결과를 호출자 인자가 아니라 process 서버 기록에서 읽는다."""
    import urllib.error
    from dmn_mcp import tools as dmn
    from test_dmn_mcp import FakeTSDB
    alert, _ = human_alert.build_alert(ENTRY, now=NOW)
    monkeypatch.setattr(dmn.mcp_prom, "freshness", lambda tsdb, asset: {"ok": True})
    urls = []

    def served(url):
        urls.append(url)
        if "HYD-01" not in url:
            raise urllib.error.HTTPError(url, 404, "none", {}, None)
        return {"alert": alert, "incident_state": "AWAITING_APPROVAL"}
    monkeypatch.setattr(dmn.decidelib, "_get_json", served)
    t = dmn.DmnTools(kg=_kg_with([]), tsdb=FakeTSDB())
    out = t.diagnose("HYD-01", "OIL_ANALYSIS", alert["alertId"])
    assert not out["withheld"] and out["top_cause"] == "cause:oil-oxidation" and out["failure_mode"] == "fm:oil-degradation"
    assert out["causes"][0]["evidence"][0]["id"] == f"human:{alert['alertId']}"
    assert "/api/human-alerts/current?asset=HYD-01&pattern=OIL_ANALYSIS&alert_id=" in urls[0]
    out = t.diagnose("HYD-02", "OIL_ANALYSIS")                             # 처리 중인 입력이 없으면 지금처럼 근거 없음 → 보류
    assert out["withheld"] and out["evidence_status"]["status"] == "UNSUPPORTED"
    from test_dmn_mcp import FakeKG
    calls = len(urls)
    dmn.DmnTools(kg=FakeKG(), tsdb=FakeTSDB()).diagnose("HYD-01", "COOLER_DEGRADATION")
    assert len(urls) == calls                                              # 센서 증거가 있는 패턴은 묻지도 않는다


def test_ingesting_the_oil_manual_links_its_sop_to_the_oil_candidate_rule():
    """HM-9 적재 경로(manual_api.commit → skill_graph.candidate_rules → manual_graph.desired)가 SOP-OIL-21 을 rule:cand-oil 의 출력으로
    잇는다: 시드의 rule:cand-oil 은 고장 유형 하나만 검사하는 후보 규칙(CANDIDATE_RULES_Q 조건)이고, 적재 계획은 그 규칙 → 스킬 OUTPUTS 를 만든다."""
    from procsvc import manual_graph, skill_graph
    seed = (ROOT / "it/neo4j/v2/knowledge_a098.cypher").read_text(encoding="utf-8")
    block = seed[seed.index("MERGE (n:Rule {id: 'rule:cand-oil'})"):]
    block = block[:block.index(";")]
    assert block.count("[c:TESTS]") == 1 and "c.value = 'fm:oil-degradation'" in block and "InputData {id: 'in:failure-mode'}" in block
    assert "tests[0].input='in:failure-mode'" in skill_graph.CANDIDATE_RULES_Q
    anchor = {"source_id": "src-1", "page": 1, "start": 0, "end": 4, "quote": "작동유"}
    plan = {"document": "doc", "sha256": "x", "filename": "HM-9_oil-degradation-manual.md", "source_id": "src-1", "document_id": "d1",
            "extractor": "test", "sections": [{"ref": "HM-9.3", "title": "작동유 교체", "excerpt": "", "anchor": anchor}],
            "procedures": [{"id": "SOP-OIL-21", "name": "작동유 교체 절차", "kind": "work_order", "anchor": anchor, "failureMode": "fm:oil-degradation",
                            "relation": "REMEDIED_BY", "approver": "role:maint-mgr", "affects": [],
                            "steps": [{"order": 1, "text": "설비를 정지하고 잠금", "manual": "HM-9.3", "anchor": anchor}]}],
            "candidate_rules": {"fm:oil-degradation": ["rule:cand-oil"]}}
    edges = manual_graph.desired(plan)["edges"]
    assert any(e["type"] == "OUTPUTS" and e["from_id"] == "rule:cand-oil" and e["to_labels"] == ["Skill"] for e in edges)
    assert any(e["type"] == "HAS_SKILL" and e["from_id"] == "sys:cmms" for e in edges)          # 정비형(work_order) → CMMS
    assert not any(e["type"] == "OUTPUTS" for e in manual_graph.desired(dict(plan, candidate_rules={}))["edges"])   # 적재 전 = 출력 없음
