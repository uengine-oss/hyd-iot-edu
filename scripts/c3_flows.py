"""C3 조립: 확정 흐름 A · B · C 를 포털의 '흐름 가져오기'와 같은 API 로 가져와 등록 · 배포한다(수업 스택용).

  .venv/bin/python scripts/c3_flows.py deploy            # 세 흐름 가져오기 → 사전 검사 → 등록 → 배포
  .venv/bin/python scripts/c3_flows.py check             # 사전 검사만 (등록 안 함)
  .venv/bin/python scripts/c3_flows.py export DIR        # bpmn.io 로 열 수 있는 .bpmn 세 파일과 매핑 JSON 을 DIR 에 쓴다

흐름 모양 · 부품 · 설정은 C2 시험(tests/test_c2_execution.py)의 A · B · C 그림 · 매핑과 같다. 다른 점은 둘이다:
  1) 판단 · 제안 task 를 시나리오 에이전트에 묶는다(agent:cooling · agent:pm-plan · agent:spare-buy — seed.sql, 에이전트마다 SKILL · MCP 서버가 다름).
  2) 담당자 승인 task 의 역할을 시나리오 승인자로 둔다(A 운전원 · B 설비보전팀장 · C 구매 담당).
처리 건 시작은 경보다(A 쿨러 과열 COOLER_DEGRADATION, B 정기 정비 도래 PM_DUE, C 재고 기준 이탈 SPARE_BELOW_MIN).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = os.environ.get("PROCESS_URL", "http://127.0.0.1:8080")
NS = 'xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"'


def xml(body: str, pid: str, name: str, lanes: str) -> str:
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n<bpmn:definitions {NS} id="D_{pid}"><bpmn:process id="{pid}" name="{name}">'
            f'<bpmn:laneSet id="LS">{lanes}</bpmn:laneSet>{body}</bpmn:process></bpmn:definitions>')


def lanes(person: list[str], agent: list[str], system: list[str]) -> str:
    def lane(lid, name, nodes):
        return f'<bpmn:lane id="{lid}" name="{name}">' + "".join(f"<bpmn:flowNodeRef>{n}</bpmn:flowNodeRef>" for n in nodes) + "</bpmn:lane>"
    return lane("L_person", "담당자", person) + lane("L_agent", "에이전트", agent) + lane("L_system", "시스템", system)


def decide(agent: str, instruction: str) -> dict:
    return {"part": "task:decide", "agent": agent, "instruction": instruction}


def report(outcome: str, title: str, summary: str = "") -> dict:
    return {"part": "svc:report", "config": {"outcome": outcome, "title": title, "summary": summary}}


# ================================================================ A 냉각 긴급 대응
A_XML = xml("""
  <bpmn:startEvent id="Start" name="쿨러 과열 경보"><bpmn:messageEventDefinition id="M1"/></bpmn:startEvent>
  <bpmn:task id="T_agent" name="원인 진단 · 냉각 조치 제안"/>
  <bpmn:userTask id="T_approve" name="운전원 승인"/>
  <bpmn:boundaryEvent id="B_overdue" name="승인 지연" attachedToRef="T_approve" cancelActivity="false"><bpmn:timerEventDefinition id="TD1"/></bpmn:boundaryEvent>
  <bpmn:serviceTask id="T_notice" name="승인 지연 알림"/>
  <bpmn:serviceTask id="T_cmd" name="냉각 명령"/>
  <bpmn:serviceTask id="T_reobs" name="재관측"/>
  <bpmn:exclusiveGateway id="G_ok" name="유온 정상?"/>
  <bpmn:serviceTask id="T_wo" name="작업지시 등록"/>
  <bpmn:serviceTask id="R_ok" name="결과 보고: 정상"/>
  <bpmn:serviceTask id="R_fail" name="결과 보고: 미달"/>
  <bpmn:endEvent id="E_notice" name="알림"/>
  <bpmn:endEvent id="E_end" name="끝"/>
  <bpmn:sequenceFlow id="F1" sourceRef="Start" targetRef="T_agent"/>
  <bpmn:sequenceFlow id="F2" sourceRef="T_agent" targetRef="T_approve"/>
  <bpmn:sequenceFlow id="F3" sourceRef="T_approve" targetRef="T_cmd"/>
  <bpmn:sequenceFlow id="F4" sourceRef="T_cmd" targetRef="T_reobs"/>
  <bpmn:sequenceFlow id="F5" sourceRef="T_reobs" targetRef="G_ok"/>
  <bpmn:sequenceFlow id="F_yes" name="예" sourceRef="G_ok" targetRef="T_wo"/>
  <bpmn:sequenceFlow id="F_no" name="아니오" sourceRef="G_ok" targetRef="R_fail"/>
  <bpmn:sequenceFlow id="F6" sourceRef="T_wo" targetRef="R_ok"/>
  <bpmn:sequenceFlow id="F7" sourceRef="R_ok" targetRef="E_end"/>
  <bpmn:sequenceFlow id="F8" sourceRef="R_fail" targetRef="E_end"/>
  <bpmn:sequenceFlow id="F9" sourceRef="B_overdue" targetRef="T_notice"/>
  <bpmn:sequenceFlow id="F10" sourceRef="T_notice" targetRef="E_notice"/>""", "Process_A", "냉각 긴급 대응",
            lanes(["T_approve"], ["T_agent"], ["T_notice", "T_cmd", "T_reobs", "T_wo", "R_ok", "R_fail"]))

A_MAPPING = {
    "name": "냉각 긴급 대응", "start": {"kind": "alert", "patterns": ["COOLER_DEGRADATION"]}, "lanes": {},
    "tasks": {"T_agent": decide("agent:cooling", "쿨러 과열의 원인을 진단하고 냉각 조치 후보를 비교해 추천 카드 한 장과 지는 대안을 낸다"),
              "T_approve": {"part": "task:select", "role": "운전원"},
              "T_notice": report("승인 지연", "{asset} 냉각 조치 승인 지연", "승인 대기 중 — 경보 {alert.alertId}"),
              "T_cmd": {"part": "task:command"}, "T_reobs": {"part": "task:reobserve"}, "T_wo": {"part": "task:work-order"},
              "R_ok": report("정상", "{asset} 긴급 대응 결과", "유온 정상 · 경보 해제, 작업지시 {work_order.ref}"),
              "R_fail": report("미달", "{asset} 긴급 대응 결과", "재관측 기준 미달 — 승인자 {approved_by}")},
    "timers": {"B_overdue": "PT10M"},
    "flows": {"F_yes": {"var": "recovered", "op": "==", "value": True}, "F_no": {"default": True}}}

# ================================================================ B 정기 정비 계획
B_XML = xml("""
  <bpmn:startEvent id="Start" name="정기 정비 도래"><bpmn:messageEventDefinition id="M1"/></bpmn:startEvent>
  <bpmn:task id="T_agent" name="정비 일정 제안"/>
  <bpmn:userTask id="T_approve" name="설비보전팀장 승인"/>
  <bpmn:serviceTask id="T_wo" name="정비 오더 · 생산팀 공지"/>
  <bpmn:serviceTask id="T_do" name="예정된 시간에 정비 수행"/>
  <bpmn:serviceTask id="T_run" name="시운전 확인"/>
  <bpmn:exclusiveGateway id="G_pass" name="기준 통과?"/>
  <bpmn:serviceTask id="R_ok" name="결과 보고: 정상"/>
  <bpmn:serviceTask id="R_fail" name="결과 보고: 미달"/>
  <bpmn:endEvent id="E_end" name="끝"/>
  <bpmn:sequenceFlow id="F1" sourceRef="Start" targetRef="T_agent"/>
  <bpmn:sequenceFlow id="F2" sourceRef="T_agent" targetRef="T_approve"/>
  <bpmn:sequenceFlow id="F3" sourceRef="T_approve" targetRef="T_wo"/>
  <bpmn:sequenceFlow id="F4" sourceRef="T_wo" targetRef="T_do"/>
  <bpmn:sequenceFlow id="F5" sourceRef="T_do" targetRef="T_run"/>
  <bpmn:sequenceFlow id="F6" sourceRef="T_run" targetRef="G_pass"/>
  <bpmn:sequenceFlow id="F_yes" name="예" sourceRef="G_pass" targetRef="R_ok"/>
  <bpmn:sequenceFlow id="F_no" name="아니오" sourceRef="G_pass" targetRef="R_fail"/>
  <bpmn:sequenceFlow id="F7" sourceRef="R_ok" targetRef="E_end"/>
  <bpmn:sequenceFlow id="F8" sourceRef="R_fail" targetRef="E_end"/>""", "Process_B", "정기 정비 계획",
            lanes(["T_approve"], ["T_agent"], ["T_wo", "T_do", "T_run", "R_ok", "R_fail"]))

PRODUCTION_NOTICE = {"to": "production@hyd.local", "subject": "[정비 공지] {asset} {work_order.after.window}",
                     "body": "작업지시 {work_order.ref} — 예정된 정비 시간에 {asset} 정지"}
B_MAPPING = {
    "name": "정기 정비 계획", "start": {"kind": "alert", "patterns": ["PM_DUE"]}, "lanes": {},
    "tasks": {"T_agent": decide("agent:pm-plan", "운전시간 · 허용 오차 · 생산 오더 · 정비 인원 · 부품을 저울질해 언제 정비할지 카드를 낸다"),
              "T_approve": {"part": "task:select", "role": "설비보전팀장"},
              # 정비 시간은 승인한 카드가 실어 온 시점이 우선이다(C3). window_var 는 카드에 시점이 없을 때의 기본(경보의 이번 야간 창)
              "T_wo": {"part": "task:work-order", "config": {"mail": PRODUCTION_NOTICE, "window_var": "alert.evidence.night_window_id"}},
              "T_do": {"part": "svc:maintenance", "config": {"component": "pump", "sop": "SOP-PMP-04", "until": "work_order.after.window_starts_at"}},
              "T_run": {"part": "svc:test-run"},
              "R_ok": report("정상", "{asset} 정기 정비 결과", "시운전 정상 — {test_run.counter.detail}"),
              "R_fail": report("미달", "{asset} 정기 정비 결과", "시운전 기준 미달 — 계수기는 리셋하지 않음")},
    "timers": {}, "flows": {"F_yes": {"var": "passed", "op": "==", "value": True}, "F_no": {"default": True}}}

# ================================================================ C 예비품 구매
C_XML = xml("""
  <bpmn:startEvent id="Start" name="재고 기준 이탈"><bpmn:messageEventDefinition id="M1"/></bpmn:startEvent>
  <bpmn:task id="T_agent" name="발주안 제안"/>
  <bpmn:userTask id="T_approve" name="구매 담당 승인"/>
  <bpmn:serviceTask id="T_po" name="ERP 발주 · 공급사 메일"/>
  <bpmn:serviceTask id="T_gr" name="입고 확인"/>
  <bpmn:boundaryEvent id="B_late" name="납기 초과" attachedToRef="T_gr"><bpmn:timerEventDefinition id="TD1"/></bpmn:boundaryEvent>
  <bpmn:serviceTask id="R_ok" name="결과 보고: 입고 완료"/>
  <bpmn:serviceTask id="R_late" name="결과 보고: 지연"/>
  <bpmn:endEvent id="E_done" name="입고 완료"/>
  <bpmn:endEvent id="E_late" name="지연"/>
  <bpmn:sequenceFlow id="F1" sourceRef="Start" targetRef="T_agent"/>
  <bpmn:sequenceFlow id="F2" sourceRef="T_agent" targetRef="T_approve"/>
  <bpmn:sequenceFlow id="F3" sourceRef="T_approve" targetRef="T_po"/>
  <bpmn:sequenceFlow id="F4" sourceRef="T_po" targetRef="T_gr"/>
  <bpmn:sequenceFlow id="F5" sourceRef="T_gr" targetRef="R_ok"/>
  <bpmn:sequenceFlow id="F6" sourceRef="R_ok" targetRef="E_done"/>
  <bpmn:sequenceFlow id="F7" sourceRef="B_late" targetRef="R_late"/>
  <bpmn:sequenceFlow id="F8" sourceRef="R_late" targetRef="E_late"/>""", "Process_C", "예비품 구매",
            lanes(["T_approve"], ["T_agent"], ["T_po", "T_gr", "R_ok", "R_late"]))

SUPPLIER_MAIL = {"to": "supplier@hyd.local, receiving@hyd.local", "subject": "[발주] {approved_part_no} {approved_qty}개",
                 "body": "공급사 {approved_supplier}, 금액 {approved_amount}만원, 발주 번호 {purchase_order.ref}"}
C_MAPPING = {
    "name": "예비품 구매", "start": {"kind": "alert", "patterns": ["SPARE_BELOW_MIN"]}, "lanes": {},
    "tasks": {"T_agent": decide("agent:spare-buy", "필요량을 정하고 공급사를 금액 · 납기 · 품질 · 회사 규정으로 비교해 발주 카드를 낸다"),
              "T_approve": {"part": "task:select", "role": "구매 담당"},
              "T_po": {"part": "svc:erp-po", "config": {"mail": SUPPLIER_MAIL}},
              "T_gr": {"part": "svc:goods-receipt"},
              "R_ok": report("입고 완료", "{approved_part_no} 발주 결과", "{goods_receipt.detail}"),
              "R_late": report("지연", "{approved_part_no} 발주 결과", "납기 초과 — 발주 {purchase_order.ref}, 공급사 {approved_supplier}")},
    "timers": {"B_late": "P6D"}, "flows": {}}

FLOWS = {"c3_cooling": ("cooling-emergency.bpmn", A_XML, A_MAPPING),
         "c3_pm": ("pm-planning.bpmn", B_XML, B_MAPPING),
         "c3_spare": ("spare-purchase.bpmn", C_XML, C_MAPPING)}


def call(method: str, path: str, body=None) -> dict:
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{method} {path} → {e.code}: {e.read().decode(errors='replace')[:800]}")


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "check"
    if cmd == "export":
        out = Path(argv[2])
        out.mkdir(parents=True, exist_ok=True)
        for did, (fname, src, mapping) in FLOWS.items():
            (out / fname).write_text(src, encoding="utf-8")
            (out / f"{did}.mapping.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {len(FLOWS)} flows to {out}")
        return 0
    for did, (fname, src, mapping) in FLOWS.items():
        call("POST", "/api/flows/import", {"xml": src, "file_name": fname, "definition_id": did})
        view = call("POST", f"/api/flows/{did}/check", {"mapping": mapping})
        problems = (view.get("check") or view).get("problems") or []
        print(did, "check:", "ok" if not problems else json.dumps(problems, ensure_ascii=False)[:600])
        if cmd == "check" or problems:
            continue
        reg = call("POST", f"/api/flows/{did}/register", {"mapping": mapping})
        dep = call("POST", f"/api/process/definitions/{did}/deploy", {"version": reg["version"], "by": "c3-assembly", "reason": "C3 확정 흐름 배포"})
        print(did, "registered", reg["version"], "deployed", json.dumps(dep, ensure_ascii=False)[:200])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
