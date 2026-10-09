"""C2 (확정 TODO C) 승인 뒤 실행 부품 — bpmn.io 그림 → 일반 부품으로 가져오기 → 등록 · 배포 → 실제 런타임(MemoryRepo · 실제 Incident 상태기계 ·
승인 경로)으로 끝까지.

  구매(C 모양): ERP 재고 경보 → 에이전트 발주안 → 사람 승인(금액 확정) → 300만 원 초과면 구매팀장 → ERP 발주 → 승인 뒤 MCP 메일 → 입고 확인(대기) → 사건 종결
  정비(일반 모양): 에이전트 → 사람 승인(작업지시만) → CMMS 작업지시(정비창 전달) → 정비창까지 대기 → 정비 수행 모사 → 효과 재관측 → 끝/상급자

일부러 깨뜨림: 승인 앞 MCP 쓰기는 등록 거절, 수량 모르면 승인 거절, 팀장 반려면 발주 없음, 납기 초과 타이머, 회복 안 되면 상급자."""
from copy import deepcopy
from datetime import timedelta

import pytest

from procsvc import bpmn_import as B, business_monitor, decisions, effect_parts, engine, instance_mode
from test_instance_mode import world, ALERT, NOW, _row  # noqa: F401  (world 는 fixture)

NS = 'xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"'
USERS = [{"id": "role:purchasing-mgr", "username": "구매팀장"}]


def xml(body: str, pid: str) -> str:
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<bpmn:definitions {NS} id="D1"><bpmn:process id="{pid}" name="{pid}">{body}</bpmn:process></bpmn:definitions>'


PURCHASE = xml("""
  <bpmn:startEvent id="Start" name="재고 기준 이탈"><bpmn:messageEventDefinition id="M1"/></bpmn:startEvent>
  <bpmn:task id="T_dx" name="원인 진단"/>
  <bpmn:task id="T_cand" name="후보"/>
  <bpmn:task id="T_comp" name="규정 검토"/>
  <bpmn:task id="T_propose" name="제안"/>
  <bpmn:userTask id="T_approve" name="제안 승인"/>
  <bpmn:exclusiveGateway id="G_amount" name="300만 원 초과?"/>
  <bpmn:userTask id="T_mgr" name="금액 초과 추가 승인"/>
  <bpmn:exclusiveGateway id="G_ok" name="승인?"/>
  <bpmn:serviceTask id="T_po" name="ERP 발주"/>
  <bpmn:serviceTask id="T_mail" name="공급사 발주 메일"/>
  <bpmn:serviceTask id="T_gr" name="입고 확인"/>
  <bpmn:boundaryEvent id="B_late" name="납기 초과" attachedToRef="T_gr"><bpmn:timerEventDefinition id="TD1"/></bpmn:boundaryEvent>
  <bpmn:endEvent id="E_done" name="입고 완료"/>
  <bpmn:endEvent id="E_rejected" name="팀장 반려"/>
  <bpmn:endEvent id="E_late" name="지연 통보"/>
  <bpmn:sequenceFlow id="F1" sourceRef="Start" targetRef="T_dx"/>
  <bpmn:sequenceFlow id="F1a" sourceRef="T_dx" targetRef="T_cand"/>
  <bpmn:sequenceFlow id="F1b" sourceRef="T_cand" targetRef="T_comp"/>
  <bpmn:sequenceFlow id="F1c" sourceRef="T_comp" targetRef="T_propose"/>
  <bpmn:sequenceFlow id="F2" sourceRef="T_propose" targetRef="T_approve"/>
  <bpmn:sequenceFlow id="F3" sourceRef="T_approve" targetRef="G_amount"/>
  <bpmn:sequenceFlow id="F_big" name="초과" sourceRef="G_amount" targetRef="T_mgr"/>
  <bpmn:sequenceFlow id="F_small" name="이하" sourceRef="G_amount" targetRef="T_po"/>
  <bpmn:sequenceFlow id="F4" sourceRef="T_mgr" targetRef="G_ok"/>
  <bpmn:sequenceFlow id="F_yes" name="승인" sourceRef="G_ok" targetRef="T_po"/>
  <bpmn:sequenceFlow id="F_no" name="반려" sourceRef="G_ok" targetRef="E_rejected"/>
  <bpmn:sequenceFlow id="F5" sourceRef="T_po" targetRef="T_mail"/>
  <bpmn:sequenceFlow id="F6" sourceRef="T_mail" targetRef="T_gr"/>
  <bpmn:sequenceFlow id="F7" sourceRef="T_gr" targetRef="E_done"/>
  <bpmn:sequenceFlow id="F8" sourceRef="B_late" targetRef="E_late"/>""", "Process_purchase")

MAIL = {"server": "hyd-effects", "tool": "send_mail",
        "arguments": {"to": "supplier@hyd.local", "subject": "[발주] {approved_part_no} {approved_qty}개",
                      "body": "공급사 {approved_supplier}, 금액 {approved_amount}만원, 발주 번호 {purchase_order.ref}"}}


CHAIN_MAP = {"T_dx": {"part": "task:diagnose"}, "T_cand": {"part": "task:candidates"}, "T_comp": {"part": "task:compliance"},
             "T_propose": {"part": "task:rank"}}


def run_agents(rt, inst, d, extra=None):
    """실제 워커가 save_task_result 로 내는 것과 같은 결과를 네 에이전트 단계에 낸다(판단 내용은 이 시험의 관심이 아니다)."""
    rt.submit(_row(rt, inst, "T_dx")["id"], {"cause": d["origin"]["cause"], "failure_mode": d["origin"]["failureMode"], "guide_card": {}}, now=NOW)
    rt.submit(_row(rt, inst, "T_cand")["id"], {"candidates": [o["id"] for o in d["options"]]}, now=NOW)
    rt.submit(_row(rt, inst, "T_comp")["id"], {"compliance": {o["id"]: {"feasible": True} for o in d["options"]}}, now=NOW)
    rt.submit(_row(rt, inst, "T_propose")["id"], {"decision": {"recommended": d["recommended"]}, "decision_id": d["id"]}, now=NOW)
    if extra:
        rt.submit(_row(rt, inst, "T_plan")["id"], extra, now=NOW)


def purchase_mapping(late="P7D"):
    return {"name": "예비품 구매 (시험)", "start": {"kind": "alert", "patterns": ["SPARE_BELOW_MIN"]}, "lanes": {},
            "tasks": dict(CHAIN_MAP,
                      T_approve={"part": "task:select"},
                      T_mgr={"part": "human", "role": "구매팀장",
                                "fields": [{"key": "approval", "type": "select", "text": "승인 여부", "items": ["승인", "반려"]}]},
                      T_po={"part": "svc:erp-po"},
                      T_mail={"part": "svc:mcp-call", "config": deepcopy(MAIL)},
                      T_gr={"part": "svc:goods-receipt"}),
            "timers": {"B_late": late},
            "flows": {"F_big": {"var": "approved_amount", "op": ">", "value": 300}, "F_small": {"default": True},
                      "F_yes": {"var": "approval", "op": "==", "value": "승인"}, "F_no": {"default": True}}}


MAINT = xml("""
  <bpmn:startEvent id="Start" name="경보"><bpmn:messageEventDefinition id="M1"/></bpmn:startEvent>
  <bpmn:task id="T_dx" name="원인 진단"/>
  <bpmn:task id="T_cand" name="후보"/>
  <bpmn:task id="T_comp" name="규정 검토"/>
  <bpmn:task id="T_propose" name="제안"/>
  <bpmn:task id="T_plan" name="정비 시점 산정"/>
  <bpmn:userTask id="T_approve" name="제안 승인"/>
  <bpmn:serviceTask id="T_wo" name="CMMS 예약"/>
  <bpmn:serviceTask id="T_wait" name="정비창까지 대기"/>
  <bpmn:serviceTask id="T_do" name="정비 수행 (모사)"/>
  <bpmn:serviceTask id="T_check" name="효과 재관측"/>
  <bpmn:exclusiveGateway id="G_rec" name="회복?"/>
  <bpmn:userTask id="T_esc" name="상급자 확인"/>
  <bpmn:endEvent id="E_ok" name="종결"/>
  <bpmn:endEvent id="E_esc" name="재정비 필요"/>
  <bpmn:sequenceFlow id="F1" sourceRef="Start" targetRef="T_dx"/>
  <bpmn:sequenceFlow id="F1a" sourceRef="T_dx" targetRef="T_cand"/>
  <bpmn:sequenceFlow id="F1b" sourceRef="T_cand" targetRef="T_comp"/>
  <bpmn:sequenceFlow id="F1c" sourceRef="T_comp" targetRef="T_propose"/>
  <bpmn:sequenceFlow id="F1d" sourceRef="T_propose" targetRef="T_plan"/>
  <bpmn:sequenceFlow id="F2" sourceRef="T_plan" targetRef="T_approve"/>
  <bpmn:sequenceFlow id="F3" sourceRef="T_approve" targetRef="T_wo"/>
  <bpmn:sequenceFlow id="F4" sourceRef="T_wo" targetRef="T_wait"/>
  <bpmn:sequenceFlow id="F5" sourceRef="T_wait" targetRef="T_do"/>
  <bpmn:sequenceFlow id="F6" sourceRef="T_do" targetRef="T_check"/>
  <bpmn:sequenceFlow id="F7" sourceRef="T_check" targetRef="G_rec"/>
  <bpmn:sequenceFlow id="F_ok" name="회복" sourceRef="G_rec" targetRef="E_ok"/>
  <bpmn:sequenceFlow id="F_no" name="미회복" sourceRef="G_rec" targetRef="T_esc"/>
  <bpmn:sequenceFlow id="F8" sourceRef="T_esc" targetRef="E_esc"/>""", "Process_maint")


def maint_mapping():
    return {"name": "정비 계획 (시험)", "start": {"kind": "alert", "patterns": ["COOLER_DEGRADATION"]}, "lanes": {},
            "tasks": dict(CHAIN_MAP, T_plan={"part": "agent", "agent": "sys:agent", "instruction": "정비창 목록에서 정비 시점을 고른다",
                                             "outputs": [{"key": "maintenance_window", "type": "text"}]},
                      T_approve={"part": "task:select"},
                      T_wo={"part": "task:work-order"},
                      T_wait={"part": "svc:wait", "config": {"until": "work_order.after.window_starts_at", "label": "정비창까지"}},
                      T_do={"part": "svc:maintenance", "config": {"component": "cooler", "sop": "SOP-COOL-04"}},
                      T_check={"part": "task:reobserve"},
                      T_esc={"part": "task:escalate"}),
            "timers": {}, "flows": {"F_ok": {"var": "recovered", "op": "==", "value": True}, "F_no": {"default": True}}}


def imported(world, source, mapping, did):
    rt = world["rt"]
    base = rt.definition_for({"proc_def_id": rt.defn.id, "proc_def_version": rt.base_version, "tenant_id": rt.tenant_id}).raw
    cat = B.catalog(base, USERS)
    parsed = B.parse_bpmn(source)
    return cat, B.check(parsed, mapping, {"catalog": cat, "definition_id": did, "version": "1", "file_name": f"{did}.bpmn", "xml_sha256": "x"})


def deploy(world, source, mapping, did):
    _, r = imported(world, source, mapping, did)
    assert r["ok"], r["problems"]
    rt = world["rt"]
    rt.register_definition(r["definition"])
    rt.deploy_definition(did, "1", "tester", "C2 시험")
    return r["definition"]


# ---------------------------------------------------------------- 가짜 바깥 (업무 · 메일 · 설비)
class Outside:
    def __init__(self, world, lead_d=5):
        self.calls, self.mails, self.restores, self.lead_d = [], [], [], lead_d
        ctx, rt = world["ctx"], world["rt"]
        ctx.exec_skill = self.exec_skill
        rt.hooks.enterprise_read = self.read
        rt.hooks.mcp_call = self.mcp
        rt.hooks.plant_restore = self.restore
        ctx.latest_tag = lambda asset, tag: self.value
        self.value = 48.0

    QUOTES = [{"supplier": "sup:a", "name": "A정밀", "price": 35, "lead_d": 2, "avl": True},
              {"supplier": "sup:b", "name": "B-OEM", "price": 55, "lead_d": 5, "avl": True},
              {"supplier": "sup:c", "name": "C트레이딩", "price": 20, "lead_d": 1, "avl": False}]

    def read(self, name, params):
        if name == "part_quotes":
            assert params == {"part": "P-PMP-SEAL"}
            return {"records": deepcopy(self.QUOTES)}
        raise KeyError(name)

    def exec_skill(self, d, item):
        self.calls.append(deepcopy(item))
        code = item["code"]
        out = {"ok": True, "skill": item["skill"], "code": code, "system": item.get("system")}
        if code == "PR_CREATE":
            return out | {"ref": "PR-1", "detail": f"{item['qty']}개 발주", "after": {"lead_d": self.lead_d, "amount": item["amount"]}}
        if code == "GR_CONFIRM":
            return out | {"ref": "GR-1", "detail": "입고 · 검수 합격"}
        if code == "WO_CREATE":
            return out | {"ref": "WO-1", "detail": "작업지시", "after": {"window_starts_at": engine.now_iso(NOW + timedelta(hours=9))}}
        if code == "WO_COMPLETE":
            return out | {"ref": "WO-1", "detail": "작업지시 WO-1 완료"}
        raise AssertionError(code)

    def mcp(self, server, tool, arguments, key):
        self.mails.append((server, tool, deepcopy(arguments), key))
        return {"status": "ok", "result": {"is_error": False, "text": '{"result": "ok"}'}, "arguments": arguments, "idempotent": True}

    def restore(self, asset, component):
        self.restores.append((asset, component))
        return {"ok": True, "asset": asset, "kind": "restore", "targets": {"cooler_health": 1.0}}


def stock_alert(need_qty=6):
    row = {"part_no": "P-PMP-SEAL", "name": "펌프 축 씰 키트", "on_hand": 3, "reserved": 2, "available": 1, "on_order": 0, "reorder_point": 2,
           "target_stock": 7, "need_qty": need_qty, "below_reorder_point": True, "below_since": "2026-10-03T11:59:00+00:00",
           "reserved_for": "HYD-03"}
    return business_monitor.build_alert(business_monitor.RULES[0], row, NOW)


def purchase_decision(inc_id, supplier="sup:b"):
    opts = []
    for sup, name, rank in (("sup:b", "B-OEM 표준 발주", 1), ("sup:a", "A정밀 대체 발주", 2)):
        opts.append({"id": f"skill:sop-pur-{sup[-1]}", "sopId": f"SOP-PUR-{sup[-1]}", "name": name, "kind": "work_order", "feasible": True,
                     "rank": rank, "approver": {"id": "role:prod-mgr", "name": "생산관리자", "level": 2},
                     "actions": [{"code": "PR_CREATE", "kind": "transaction", "value": sup, "target": "sys:erp"}],
                     "violations": [], "penalties": [], "warnings": []})
    return decisions.new({"id": "DEC-C-1", "schema": "v2", "asset": "HYD-03",
                          "origin": {"kind": "alert", "incident": inc_id, "cause": "cause:pump-seal-wear", "failureMode": "fm:volumetric-loss"},
                          "recommended": opts[0]["id"], "explanation": "결품 방지", "options": opts,
                          "roles": {"role:operator": {"level": 1}, "role:prod-mgr": {"level": 2}}})


def open_purchase(world, need_qty=6, late="P7D", supplier="sup:b"):
    deploy(world, PURCHASE, purchase_mapping(late), "spare_purchase")
    out = Outside(world)
    rt = world["rt"]
    inst = rt.on_alert_raise(stock_alert(need_qty), now=NOW)
    assert inst["proc_def_id"] == "spare_purchase"
    inc = world["incidents"][engine.variables(inst)["incident"]]
    assert inc.state == "AWAITING_APPROVAL"
    d = purchase_decision(inc.id)
    world["book"][d["id"]] = d
    run_agents(rt, inst, d)
    opt = next(o for o in d["options"] if o["actions"][0]["value"] == supplier)
    return rt, inst, inc, d, opt, out


def approve(rt, inst, d, opt):
    return rt.select(_row(rt, inst, "T_approve")["id"], d["id"], opt["id"], "manager", "role:prod-mgr", now=NOW)


# ---------------------------------------------------------------- 가져오기 · 등록 검사
def test_catalog_offers_the_generic_execution_parts_and_the_erp_pattern(world):
    cat, r = imported(world, PURCHASE, purchase_mapping(), "spare_purchase")
    parts = {p["key"]: p for p in cat["parts"]}
    for key, tool in (("svc:mcp-call", "mcp:call"), ("svc:erp-po", "enterprise:PR_CREATE"), ("svc:wait", "process:wait"),
                      ("svc:maintenance", "plant:restore"), ("svc:goods-receipt", "enterprise:GR_CONFIRM")):
        assert parts[key]["group"] == "general" and parts[key]["kind"] == "service" and parts[key]["tool"] == tool
    assert parts["svc:wait"]["effect"] is None and parts["svc:erp-po"]["effect"] == "ERP 발주"
    assert "SPARE_BELOW_MIN" in cat["patterns"] and cat["business_patterns"] == ["SPARE_BELOW_MIN"]
    assert {"approved_amount", "approved_qty", "approved_supplier"} <= set(cat["approval_values"])
    assert r["ok"], r["problems"]
    d = r["definition"]
    acts = {a["id"]: a for a in d["activities"]}
    assert acts["T_mail"]["tool"] == "mcp:call" and acts["T_mail"]["service"]["server"] == "hyd-effects"
    assert acts["T_mail"]["outputData"] == ["mcp_receipt"] and acts["T_gr"]["outputData"] == ["goods_receipt", "received"]
    assert next(x for x in d["data"] if x["name"] == "approved_amount")["type"] == "Number"
    assert next(s for s in d["sequences"] if s["id"] == "F_big")["condition"] == "approved_amount > 300"
    assert d["alertPolicy"]["patterns"]["SPARE_BELOW_MIN"]["tag"] == "ERP_SPARE_BELOW_MIN"


def test_mcp_write_before_the_human_approval_is_refused(world):
    m = purchase_mapping()
    m["tasks"]["T_cand"] = {"part": "svc:mcp-call", "config": {"server": "hyd-effects", "tool": "send_mail", "arguments": {"to": "x@y"}}}
    _, r = imported(world, PURCHASE, m, "bad")
    assert not r["ok"] and any("사람 승인" in p["reason"] and p["where"]["id"] == "T_cand" for p in r["problems"])


@pytest.mark.parametrize("key,config,phrase", [
    ("svc:mcp-call", {"server": "Bad Name", "tool": "send_mail"}, "MCP 서버 이름"),
    ("svc:wait", {}, "duration(기간) 또는 until"),
    ("svc:wait", {"duration": "9시간"}, "읽을 수 없습니다"),
    ("svc:maintenance", {"component": "boiler"}, "복구 부품"),
])
def test_part_config_problems_are_reported_at_the_task(world, key, config, phrase):
    m = purchase_mapping()
    m["tasks"]["T_mail"] = {"part": key, "config": config}
    _, r = imported(world, PURCHASE, m, "bad")
    assert not r["ok"] and any(phrase in p["reason"] and p["where"]["id"] == "T_mail" and p["field"] == "config" for p in r["problems"]), r["problems"]


# ---------------------------------------------------------------- 구매: 자동 시작 → 승인 → 금액 분기 → 발주 → 메일 → 입고 → 종결
def test_purchase_over_limit_goes_through_manager_then_orders_mails_receives_and_closes(world):
    rt, inst, inc, d, opt, out = open_purchase(world)
    res = approve(rt, inst, d, opt)
    assert res["purchase"]["approved_amount"] == 330 and res["purchase"]["quote"]["lead_d"] == 5
    v = engine.variables(rt.repo.get_instance(inst["proc_inst_id"]))
    assert (v["approved_supplier"], v["approved_qty"], v["approved_unit_price"], v["approved_amount"]) == ("sup:b", 6, 55, 330)
    assert out.calls == [], "승인 전달이 발주를 먼저 내면 안 된다 (팀장 승인 전)"
    assert _row(rt, inst, "T_mgr")["status"] == "IN_PROGRESS" and _row(rt, inst, "T_po")["status"] == "TODO"
    rt.submit(_row(rt, inst, "T_mgr")["id"], {"approval": "승인"}, now=NOW)
    assert [c["code"] for c in out.calls] == ["PR_CREATE"] and out.calls[0]["amount"] == 330 and out.calls[0]["qty"] == 6
    server, tool, args, key = out.mails[0]
    assert (server, tool) == ("hyd-effects", "send_mail") and args["subject"] == "[발주] P-PMP-SEAL 6개"
    assert "금액 330만원" in args["body"] and "PR-1" in args["body"] and key.endswith(_row(rt, inst, "T_mail")["id"])
    gr = _row(rt, inst, "T_gr")
    assert gr["status"] == "SUBMITTED" and gr["draft"]["wait"]["real_s"] == pytest.approx(5 * 86400 / (20 * 60), rel=1e-3)
    assert rt.reconcile_services(now=NOW + timedelta(seconds=100)) == 0 and _row(rt, inst, "T_gr")["status"] == "SUBMITTED"
    rt.reconcile_services(now=NOW + timedelta(seconds=400))
    assert [c["code"] for c in out.calls] == ["PR_CREATE", "GR_CONFIRM"] and out.calls[1]["ref"] == "PR-1"
    done = rt.repo.get_instance(inst["proc_inst_id"])
    assert done["status"] == "COMPLETED" and done["end_event"] == "E_done"
    assert inc.state == "CLOSED" and engine.variables(done)["received"] is True
    events = [e["job_id"] for e in rt.repo.list_events(proc_inst_id=inst["proc_inst_id"])]
    assert "MCP_EFFECT_CALL" in events and "GOODS_RECEIVED" in events


def test_purchase_under_limit_skips_the_manager(world):
    rt, inst, inc, d, opt, out = open_purchase(world, supplier="sup:a")
    res = approve(rt, inst, d, opt)
    assert res["purchase"]["approved_amount"] == 210
    assert _row(rt, inst, "T_mgr")["status"] == "CANCELLED" or _row(rt, inst, "T_mgr")["status"] == "TODO"
    assert [c["code"] for c in out.calls] == ["PR_CREATE"] and out.calls[0]["value"] == "sup:a"


def test_manager_rejection_ends_without_any_order(world):
    rt, inst, inc, d, opt, out = open_purchase(world)
    approve(rt, inst, d, opt)
    rt.submit(_row(rt, inst, "T_mgr")["id"], {"approval": "반려"}, now=NOW)
    done = rt.repo.get_instance(inst["proc_inst_id"])
    assert done["status"] == "COMPLETED" and done["end_event"] == "E_rejected" and out.calls == [] and out.mails == []


def test_unknown_quantity_refuses_the_approval_so_the_amount_gate_cannot_be_skipped(world):
    rt, inst, inc, d, opt, out = open_purchase(world, need_qty=None)
    with pytest.raises(ValueError, match="수량"):
        approve(rt, inst, d, opt)
    assert _row(rt, inst, "T_approve")["status"] == "IN_PROGRESS" and rt.repo.get_approval(_row(rt, inst, "T_approve")["id"], rt.tenant_id) is None


def test_late_delivery_fires_the_compressed_boundary_timer(world):
    rt, inst, inc, d, opt, out = open_purchase(world, late="P3D")
    approve(rt, inst, d, opt)
    rt.submit(_row(rt, inst, "T_mgr")["id"], {"approval": "승인"}, now=NOW)
    timer = _row(rt, inst, "B_late")
    assert timer["due_date"] == engine.now_iso(NOW + timedelta(seconds=3 * 86400 / (20 * 60)))      # 배속 × 수업 압축
    rt.fire_timeouts(now=NOW + timedelta(seconds=250))
    done = rt.repo.get_instance(inst["proc_inst_id"])
    assert done["end_event"] == "E_late" and _row(rt, inst, "T_gr")["status"] == "CANCELLED"
    assert [c["code"] for c in out.calls] == ["PR_CREATE"]                 # 입고는 기록하지 않았다


def test_effect_part_refuses_to_run_without_an_approval_record(world):
    rt, inst, inc, d, opt, out = open_purchase(world)
    wi = _row(rt, inst, "T_po")
    with pytest.raises(ValueError, match="사람 승인 뒤에만"):
        rt._run_purchase_order(rt.repo.get_instance(inst["proc_inst_id"]), wi, NOW)
    assert out.calls == []


# ---------------------------------------------------------------- 정비: 작업지시(정비창) → 대기 → 정비 모사 → 재관측
def maintenance_decision(inc_id):
    opt = {"id": "skill:wo-cooler-clean", "sopId": "SOP-COOL-04", "name": "쿨러 핀 세척", "kind": "work_order", "feasible": True, "rank": 1,
           "approver": {"id": "role:prod-mgr", "name": "생산관리자", "level": 2},
           "actions": [{"code": "WO_CREATE", "kind": "transaction", "value": "SOP-COOL-04", "target": "sys:cmms"}],
           "violations": [], "penalties": [], "warnings": []}
    return decisions.new({"id": "DEC-M-1", "schema": "v2", "asset": "HYD-01",
                          "origin": {"kind": "alert", "incident": inc_id, "cause": "cause:cooler-fin-fouling", "failureMode": "fm:cooling-loss"},
                          "recommended": opt["id"], "explanation": "야간 정비창", "options": [opt],
                          "roles": {"role:operator": {"level": 1}, "role:prod-mgr": {"level": 2}}})


def run_maintenance(world, value):
    deploy(world, MAINT, maint_mapping(), "maint_plan")
    out = Outside(world)
    out.value = value
    rt = world["rt"]
    inst = rt.on_alert_raise(dict(ALERT, alertId="HYD-01-C2-1"), now=NOW)
    inc = world["incidents"][engine.variables(inst)["incident"]]
    d = maintenance_decision(inc.id)
    world["book"][d["id"]] = d
    run_agents(rt, inst, d, {"maintenance_window": "MW-HYD-01-N-202610032100"})
    rt.select(_row(rt, inst, "T_approve")["id"], d["id"], d["options"][0]["id"], "manager", "role:prod-mgr", now=NOW)
    return rt, inst, inc, out


def test_maintenance_window_reaches_the_work_order_and_the_flow_waits_until_it(world):
    rt, inst, inc, out = run_maintenance(world, 48.0)
    assert out.calls[0]["code"] == "WO_CREATE" and out.calls[0]["window"] == "MW-HYD-01-N-202610032100"
    assert inc.state == "CLOSED" and inc.work_order["id"] == "WO-1"
    wait = _row(rt, inst, "T_wait")
    assert wait["status"] == "SUBMITTED" and wait["draft"]["wait"]["real_s"] == pytest.approx(9 * 3600 / 1200)
    rt.reconcile_services(now=NOW + timedelta(seconds=10))
    assert _row(rt, inst, "T_wait")["status"] == "SUBMITTED" and out.restores == []


def test_maintenance_runs_then_real_reobservation_closes_the_case(world):
    rt, inst, inc, out = run_maintenance(world, 48.0)
    rt.reconcile_services(now=NOW + timedelta(seconds=30))
    assert [c["code"] for c in out.calls] == ["WO_CREATE", "WO_COMPLETE"] and out.calls[1]["ref"] == "WO-1" and out.calls[1]["sop"] == "SOP-COOL-04"
    assert out.restores == [("HYD-01", "cooler")]
    check = _row(rt, inst, "T_check")
    assert check["status"] == "SUBMITTED" and check["draft"]["reobserve"]["window_s"] == 45.0
    # 이전: 사건이 CLOSED 라는 이유만으로 recovered=True 가 바로 나갔다 — 이제 사건 갱신이 와도 관측 창을 기다린다
    rt.on_incident_update(inc.state, inc.id, True, now=NOW + timedelta(seconds=31))
    assert _row(rt, inst, "T_check")["status"] == "SUBMITTED"
    inc.cleared = True
    rt.reconcile_services(now=NOW + timedelta(seconds=80))
    done = rt.repo.get_instance(inst["proc_inst_id"])
    assert done["status"] == "COMPLETED" and done["end_event"] == "E_ok" and engine.variables(done)["recovered"] is True
    notes = [e["job_id"] for e in rt.repo.list_events(proc_inst_id=inst["proc_inst_id"])]
    assert "MAINTENANCE_DONE" in notes and "REOBSERVATION" in notes


def test_reobservation_outside_the_criterion_escalates(world):
    rt, inst, inc, out = run_maintenance(world, 61.0)
    rt.reconcile_services(now=NOW + timedelta(seconds=30))
    inc.cleared = True
    rt.reconcile_services(now=NOW + timedelta(seconds=80))
    assert engine.variables(rt.repo.get_instance(inst["proc_inst_id"]))["recovered"] is False
    assert _row(rt, inst, "T_esc")["status"] == "IN_PROGRESS"


def test_reobservation_waits_for_the_clear_while_the_value_is_inside(world):
    rt, inst, inc, out = run_maintenance(world, 48.0)
    rt.reconcile_services(now=NOW + timedelta(seconds=30))
    rt.reconcile_services(now=NOW + timedelta(seconds=80))          # 값은 기준 안, 경보 해제 아직 → 3분의 1 창 연장
    check = _row(rt, inst, "T_check")
    assert check["status"] == "SUBMITTED" and check["draft"]["reobserve"]["extensions"] == 1
    inc.cleared = True
    rt.reconcile_services(now=NOW + timedelta(seconds=100))
    assert engine.variables(rt.repo.get_instance(inst["proc_inst_id"]))["recovered"] is True


# ---------------------------------------------------------------- 승인 전달: 흐름이 실행할 발주는 미룬다
def test_approval_delivery_still_runs_purchase_in_flows_without_an_order_task(world):
    from test_approval_delivery import ready, choose
    rt, inst, inc, d, wi = ready(world, purchase=True)
    choose(rt, d, wi)
    assert ("DEC-1003-001-ab12", "PR_CREATE") in world["executed"]          # 기준 흐름은 전과 같다(발주 task 가 없으니 승인 전달이 낸다)
