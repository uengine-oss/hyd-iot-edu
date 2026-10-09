"""B3: bpmn.io 에서 그린 `.bpmn`(BPMN 2.0 XML) → task 별 부품 · 담당 매핑 → 사전 검사 → 실행 가능한 정의 JSON.

순수 로직(DB · HTTP 없음). 저장은 bpmn_store.py, API 는 flows_api.py.

  parse_bpmn(xml)            표준 xml 파서(xml.etree)로 task · 시작/끝/경계 타이머 · exclusive/parallel gateway · sequenceFlow ·
                             lane 을 읽는다. 지원하지 않는 요소는 요소 id · 이름과 사유로 problems 에 남긴다.
  catalog(base, users)       부품 목록. 시나리오 부품은 **기준 정의 파일의 activity 에서 읽어 만든다**(폼 · 입출력 · orchestration
                             계약을 그대로) — 코드에 부품 내용을 복사해 두지 않는다. 일반 부품: 사람 task · 에이전트 task.
  merge_mapping(parsed, old) 다시 가져오기: 같은 task id(·lane · 선 · 타이머 id)의 앞선 매핑을 유지한다.
  check(parsed, mapping, ctx) 정의 JSON 을 만들고 사전 검사(칸 위치와 사유): 부품 · 담당 · 값 연결 · 설비 명령 앞 사람 승인 ·
                             끝 닫힘 · 분기 조건 · 끊긴 선 · 되돌아가는 선(루프). 통과하면 등록 검사(validate_definition)까지.
  structure(raw)             id · 이름을 뺀 구조 서명 — 기준 흐름을 다시 그린 그림이 같은 정의가 되는지 비교(시험)할 때 쓴다.

참고 원본(데이터로만 읽음): process-gpt-bpmn-extractor src/pdf2bpmn/bpmn_to_json.py:155-370(lane → role, task · event ·
gateway · sequenceFlow 추출), process-gpt-vue3 src/components/api/ProcessGPTBackend.ts:573-685(proc_def.bpmn · 판본 snapshot 에
XML 원본). 차이는 docs/handoff/verification/2026-10-08/b3-bpmn.md.
"""
from __future__ import annotations

import ast
import hashlib
import keyword
import math
import re
import xml.etree.ElementTree as ET
from copy import deepcopy

from . import engine, effect_parts
from .definition_registry import PROTECTED_OUTPUTS, validate_definition

BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
MAX_XML_BYTES = 2_000_000

TASK_TYPES = {"task": "작업", "userTask": "사람 작업", "manualTask": "수작업", "serviceTask": "서비스 작업",
              "scriptTask": "스크립트 작업", "businessRuleTask": "규칙 작업", "sendTask": "보내기 작업", "receiveTask": "받기 작업"}
GATEWAY_TYPES = {"exclusiveGateway": "배타 분기", "parallelGateway": "병렬 분기"}
UNSUPPORTED = {
    "subProcess": "하위 프로세스는 아직 실행하지 않습니다 — 펼쳐서 한 흐름으로 그리세요",
    "adHocSubProcess": "임의 하위 프로세스는 실행하지 않습니다",
    "transaction": "트랜잭션 하위 프로세스는 실행하지 않습니다",
    "callActivity": "다른 흐름 부르기(callActivity)는 아직 실행하지 않습니다",
    "inclusiveGateway": "포함 분기(inclusive)는 실행하지 않습니다 — 배타(X) 또는 병렬(+) 분기를 쓰세요",
    "eventBasedGateway": "이벤트 기반 분기는 실행하지 않습니다",
    "complexGateway": "복합 분기는 실행하지 않습니다",
    "intermediateCatchEvent": "중간 이벤트는 실행하지 않습니다 — 기다림은 task 의 경계 타이머로 그리세요",
    "intermediateThrowEvent": "중간 이벤트는 실행하지 않습니다",
}
IGNORED = {"laneSet", "textAnnotation", "association", "group", "dataObject", "dataObjectReference", "dataStoreReference",
           "extensionElements", "documentation", "category", "property", "ioSpecification"}
KIND_LABEL = {"task": "작업", "event": "이벤트", "start": "시작", "end": "끝", "boundary": "경계 타이머", "gateway": "분기", "flow": "선",
              "lane": "칸(레인)", "process": "흐름"}

# 시작 조건별로 처리 건이 시작될 때 이미 있는 값.
#   경보: instances.InstanceRuntime.start_definition 이 경보에서 넣는 값(values.update(asset, alert, alert_id, pattern, incident)).
#   사람 입력/직접 시작: 시작 폼 칸.
ALERT_START_VALUES = ("asset", "alert", "pattern", "alert_id", "incident")
# 사람 승인(조치 선택)이 끝나면 서버 승인 경로가 넣는 값(PROTECTED_OUTPUTS 중 Incident 를 뺀 것).
APPROVAL_SERVER_VALUES = tuple(sorted(PROTECTED_OUTPUTS - {"incident"}))
# 부품 성질은 tool 계약으로 판정한다(이름 · id 로 판정하지 않음).
APPROVAL_TOOL = "formHandler:select_card"                 # 역할 검사가 있는 /select 경로로만 제출되는 사람 승인
EFFECT_TOOLS = {"incident:command": "설비 명령", "enterprise:WO_CREATE": "작업지시",   # 바깥 시스템에 효과를 내는 서비스
                **effect_parts.EFFECTS}                                                 # C2: MCP 쓰기 · ERP 발주 · 정비 수행 모사 · 입고 확인
# C2: 승인 경로가 확정하는 발주 값의 자료형 (분기 조건 approved_amount > 300 의 값)
SERVER_VALUE_TYPES = {"approved_amount": "Number", "approved_qty": "Number", "approved_unit_price": "Number",
                      "approved_supplier": "Text", "approved_part_no": "Text"}
FIELD_TYPES = ("text", "textarea", "number", "integer", "boolean", "select", "object", "array")
DATA_TYPE = {"text": "Text", "textarea": "Text", "select": "Text", "number": "Number", "integer": "Number",
             "boolean": "Boolean", "object": "Object", "array": "Array"}
OPS = ("==", "!=", ">", ">=", "<", "<=")
DEF_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,62}$")


class BpmnError(ValueError):
    """XML 을 읽을 수 없거나 흐름이 없어 매핑 화면을 열 수 없음."""
    def __init__(self, reason: str, problems: list[dict] | None = None):
        super().__init__(reason)
        self.problems = problems or [problem(None, "xml", reason)]


def problem(where: dict | None, field: str, reason: str) -> dict:
    """사전 검사 한 줄: where = {kind, id, name}(칸 위치), field = 매핑 칸 이름, reason = 사람이 읽는 사유."""
    out = {"field": field, "reason": reason}
    if where:
        out["where"] = {"kind": where.get("kind"), "kind_label": KIND_LABEL.get(where.get("kind"), ""),
                        "id": where.get("id"), "name": where.get("name") or ""}
    return out


def _local(tag: str) -> tuple[str | None, str]:
    if tag.startswith("{"):
        ns, _, name = tag[1:].partition("}")
        return ns, name
    return None, tag


def _name(el) -> str:
    return " ".join(str(el.get("name") or "").split())


def _label(item: dict) -> str:
    return f"'{item['name']}'" if item.get("name") else f"(이름 없음 {item['id']})"


# ---------------------------------------------------------------- 1. 읽기
def parse_bpmn(xml_text: str) -> dict:
    if not isinstance(xml_text, str) or not xml_text.strip():
        raise BpmnError("빈 파일입니다 — bpmn.io 의 'Download BPMN diagram'으로 받은 .bpmn 파일을 고르세요")
    if len(xml_text.encode("utf-8")) > MAX_XML_BYTES:
        raise BpmnError(f"파일이 너무 큽니다 (최대 {MAX_XML_BYTES // 1_000_000} MB)")
    head = xml_text[:4096].upper()
    if "<!DOCTYPE" in head or "<!ENTITY" in xml_text.upper():
        raise BpmnError("DOCTYPE · ENTITY 선언이 있는 XML 은 읽지 않습니다 (bpmn.io 파일에는 없습니다)")
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        line, col = getattr(e, "position", (None, None))
        raise BpmnError(f"XML 을 읽을 수 없습니다 ({line}행 {col}열): {e}") from e
    ns, tag = _local(root.tag)
    if ns != BPMN_NS or tag != "definitions":
        raise BpmnError("BPMN 2.0 파일이 아닙니다 (맨 바깥 요소가 bpmn:definitions 가 아님)")
    processes = [p for p in root.findall(f"{{{BPMN_NS}}}process")]
    with_nodes = [p for p in processes if any(_local(c.tag)[1] not in IGNORED for c in p)]
    names = {}
    for part in root.iter(f"{{{BPMN_NS}}}participant"):
        if part.get("processRef"):
            names[part.get("processRef")] = _name(part)
    if not with_nodes:
        raise BpmnError("그림에 흐름(task · 이벤트 · 선)이 없습니다")
    if len(with_nodes) > 1:
        listed = ", ".join(f"{names.get(p.get('id')) or p.get('id')}" for p in with_nodes)
        raise BpmnError(f"풀(참가자)이 {len(with_nodes)}개입니다 ({listed}) — 한 풀 안에 칸(레인)으로 나눠 그리세요")
    proc = with_nodes[0]
    out = {"process": {"id": proc.get("id") or "", "name": _name(proc) or names.get(proc.get("id")) or ""},
           "tasks": [], "starts": [], "ends": [], "boundaries": [], "gateways": [], "flows": [], "lanes": [], "problems": []}
    seen: dict[str, str] = {}

    def node(el, kind: str) -> dict | None:
        nid = el.get("id")
        item = {"id": nid or "", "name": _name(el), "kind": kind}
        if not nid:
            out["problems"].append(problem(item, "id", "id 가 없는 요소입니다"))
            return None
        if nid in seen:
            out["problems"].append(problem(item, "id", f"id {nid} 가 두 번 쓰였습니다"))
            return None
        seen[nid] = kind
        return item

    def definitions_of(el) -> list[str]:
        return [_local(c.tag)[1] for c in el if _local(c.tag)[1].endswith("EventDefinition")]

    for el in proc:
        ns, tag = _local(el.tag)
        if ns != BPMN_NS:
            continue                                   # 확장 요소(bioc · color 등)는 그림 정보일 뿐
        if tag in TASK_TYPES:
            item = node(el, "task")
            if item is None:
                continue
            item["bpmn_type"], item["type_label"] = tag, TASK_TYPES[tag]
            if any(_local(c.tag)[1] in ("standardLoopCharacteristics", "multiInstanceLoopCharacteristics") for c in el):
                out["problems"].append(problem(item, "loop", "task 반복 표시(여러 번 · 반복)는 실행하지 않습니다 — 되돌아가는 선과 분기로 그리세요"))
            out["tasks"].append(item)
        elif tag == "startEvent":
            item = node(el, "start")
            if item is None:
                continue
            defs = definitions_of(el)
            item["definition"] = "message" if defs == ["messageEventDefinition"] else "none" if not defs else None
            if item["definition"] is None:
                out["problems"].append(problem(item, "event", f"지원하지 않는 시작 이벤트 종류입니다 ({', '.join(defs)}) — "
                                               "빈 시작 또는 메시지 시작을 쓰세요(시작 조건은 매핑에서 고릅니다)"))
            out["starts"].append(item)
        elif tag == "endEvent":
            item = node(el, "end")
            if item is None:
                continue
            defs = definitions_of(el)
            item["definition"] = ("none" if not defs else "escalation" if defs == ["escalationEventDefinition"] else None)
            if item["definition"] is None:
                why = ("다른 가지를 멈추는 종료(terminate)는 실행하지 않습니다" if "terminateEventDefinition" in defs
                       else f"지원하지 않는 끝 이벤트 종류입니다 ({', '.join(defs)})")
                out["problems"].append(problem(item, "event", why + " — 빈 끝 또는 에스컬레이션 끝을 쓰세요"))
            out["ends"].append(item)
        elif tag == "boundaryEvent":
            item = node(el, "boundary")
            if item is None:
                continue
            item["attached_to"] = el.get("attachedToRef") or ""
            item["interrupting"] = (el.get("cancelActivity") or "true").lower() != "false"
            defs = [c for c in el if _local(c.tag)[1].endswith("EventDefinition")]
            timer = None
            if len(defs) != 1 or _local(defs[0].tag)[1] != "timerEventDefinition":
                out["problems"].append(problem(item, "event", "경계 이벤트는 시간 초과(타이머)만 실행합니다"))
            else:
                parts = {_local(c.tag)[1]: (c.text or "").strip() for c in defs[0]}
                if parts.get("timeDate") or parts.get("timeCycle"):
                    out["problems"].append(problem(item, "timer", "타이머는 기간(timeDuration)만 씁니다 — 날짜 · 반복 타이머는 실행하지 않습니다"))
                timer = parts.get("timeDuration") or None
            if not item["interrupting"]:
                out["problems"].append(problem(item, "event", "멈추지 않는(non-interrupting) 경계 타이머는 실행하지 않습니다 — 실선 타이머를 쓰세요"))
            item["timer"] = timer
            out["boundaries"].append(item)
        elif tag in GATEWAY_TYPES:
            item = node(el, "gateway")
            if item is None:
                continue
            item["gateway_type"], item["type_label"], item["default"] = tag, GATEWAY_TYPES[tag], el.get("default") or None
            out["gateways"].append(item)
        elif tag == "sequenceFlow":
            item = node(el, "flow")
            if item is None:
                continue
            item["source"], item["target"] = el.get("sourceRef") or "", el.get("targetRef") or ""
            cond = el.find(f"{{{BPMN_NS}}}conditionExpression")
            item["condition_xml"] = (cond.text or "").strip() if cond is not None and (cond.text or "").strip() else None
            out["flows"].append(item)
        elif tag == "laneSet":
            _lanes(el, out["lanes"])
        elif tag in UNSUPPORTED:
            item = {"id": el.get("id") or "", "name": _name(el),
                    "kind": "gateway" if tag.endswith("Gateway") else "event" if "Event" in tag else "task"}
            seen.setdefault(item["id"], item["kind"])
            out["problems"].append(problem(item, "element", UNSUPPORTED[tag]))
        elif tag not in IGNORED:
            out["problems"].append(problem({"kind": "process", "id": el.get("id") or "", "name": _name(el)}, "element",
                                           f"이 요소({tag})는 실행 흐름으로 읽지 않습니다"))
    nodes = {i["id"] for k in ("tasks", "starts", "ends", "boundaries", "gateways") for i in out[k]}
    for f in out["flows"]:
        for end, label in ((f["source"], "출발"), (f["target"], "도착")):
            if end not in nodes:
                why = (f"{label} 쪽이 이어져 있지 않습니다" if not end else
                       f"{label} 요소 {end} 는 실행할 수 없는 요소입니다" if end in seen else f"{label} 요소 {end} 가 그림에 없습니다")
                out["problems"].append(problem(f, "flow", "끊긴 선: " + why))
    tasks = {t["id"] for t in out["tasks"]}
    for b in out["boundaries"]:
        if b["attached_to"] not in tasks:
            out["problems"].append(problem(b, "attached", "경계 타이머가 task 테두리에 붙어 있지 않습니다"))
    lane_of = {}
    for lane in out["lanes"]:
        for n in lane["nodes"]:
            lane_of[n] = lane["id"]
    for k in ("tasks", "starts", "ends", "boundaries", "gateways"):
        for item in out[k]:
            item["lane"] = lane_of.get(item["id"]) or (lane_of.get(item.get("attached_to")) if k == "boundaries" else None)
    return out


def _lanes(lane_set, out: list) -> None:
    """칸(lane)은 가장 안쪽 칸이 담당이다(childLaneSet 안쪽이 바깥을 덮어쓴다)."""
    for lane in lane_set.findall(f"{{{BPMN_NS}}}lane"):
        refs = [(r.text or "").strip() for r in lane.findall(f"{{{BPMN_NS}}}flowNodeRef") if (r.text or "").strip()]
        out.append({"id": lane.get("id") or "", "name": _name(lane), "kind": "lane", "nodes": refs})
        child = lane.find(f"{{{BPMN_NS}}}childLaneSet")
        if child is not None:
            _lanes(child, out)


def xml_sha256(xml_text: str) -> str:
    return hashlib.sha256(xml_text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- 2. 부품 목록 (기준 정의에서 읽음)
def _part_kind(a: dict) -> str:
    if engine.is_agent(a):
        return "agent"
    return "service" if a.get("type") == "serviceTask" else "human"


def catalog(base: dict, users: list[dict] | None = None) -> dict:
    """기준 정의(it/process/definitions/<운영판>.json)의 activity → 시나리오 부품. 부품은 그 activity 의 계약(type · role · agent ·
    agentMode · orchestration · decision · tool · instruction · inputData · outputData · checkpoints · duration)과 폼을 그대로 쓴다.
    경계 타이머는 그림에 그린 것만 쓰되, 기준에서 그 부품에 붙어 있던 기간을 기본값으로 알려 준다."""
    forms = base.get("forms") or {}
    roles = {r["name"]: r for r in base.get("roles") or []}
    events = base.get("events") or []
    parts = []
    for a in base.get("activities") or []:
        tool = a.get("tool") or ""
        form_id = tool.split(":", 1)[1] if tool.startswith("formHandler:") else None
        contract = {k: deepcopy(v) for k, v in a.items() if k not in ("id", "name", "attachedEvents")}
        timers = [e.get("timer") for e in events if e.get("type") == "boundaryEvent" and e.get("attachedTo") == a["id"]
                  and e.get("eventDefinition") == "timer" and e.get("timer")]
        parts.append({"key": a["id"], "group": "scenario", "name": a.get("name") or a["id"], "kind": _part_kind(a),
                      "role": a.get("role"), "agent": a.get("agent"), "tool": tool, "form_id": form_id,
                      "form": deepcopy(forms.get(form_id)) if form_id else None,
                      "inputs": list(a.get("inputData") or []), "outputs": list(a.get("outputData") or []),
                      "approval": tool == APPROVAL_TOOL, "effect": EFFECT_TOOLS.get(tool),
                      "default_timer": timers[0] if timers else None, "contract": contract})
    general = [{"key": "human", "group": "general", "name": "사람 task", "kind": "human",
                "help": "담당 역할 · 폼 칸을 정합니다. 폼 칸이 이 task 가 내는 값입니다."},
               {"key": "agent", "group": "general", "name": "에이전트 task", "kind": "agent",
                "help": "맡길 에이전트 · 지시문 · 결과 값 이름을 정합니다. 승인 전 에이전트는 조회 · 계산 · 보고서만 합니다."}]
    # C2: 승인 뒤 실행 부품(시스템 task) — 시나리오에 묶이지 않은 일반 부품. 설정은 매핑의 tasks[<id>].config (effect_parts.PARTS 의 config 설명)
    general += [{"key": key, "group": "general", "name": spec["name"], "kind": "service", "tool": spec["tool"],
                 "effect": EFFECT_TOOLS.get(spec["tool"]), "approval": False, "outputs": list(spec["outputs"]),
                 "inputs": list(spec.get("inputs") or []), "config": deepcopy(spec["config"]), "help": spec["help"]}
                for key, spec in effect_parts.PARTS.items()]
    role_list = []
    for r in base.get("roles") or []:
        role_list.append({"name": r["name"], "endpoint": r.get("endpoint"), "resolutionRule": r.get("resolutionRule"),
                          "human": str(r.get("endpoint") or "").startswith("role:")})
    known = {r["endpoint"] for r in role_list}
    agents = []
    for u in sorted(users or [], key=lambda u: str(u.get("id"))):
        uid = str(u.get("id") or "")
        if uid.startswith("role:") and not u.get("is_agent") and uid not in known:
            role_list.append({"name": u.get("username") or uid, "endpoint": uid, "human": True,
                              "resolutionRule": f"users 표 역할 {uid} (흐름 가져오기에서 고름)"})
            known.add(uid)
        if u.get("is_agent") and (u.get("agent_type") or "agent") == "agent":
            agents.append({"id": uid, "name": u.get("username") or uid, "goal": u.get("goal")})
    base_agents = {p["agent"] for p in parts if p["kind"] == "agent" and p.get("agent")}
    for aid in sorted(base_agents - {a["id"] for a in agents}):
        agents.insert(0, {"id": aid, "name": aid, "goal": None})
    agent_role = next((p["role"] for p in parts if p["kind"] == "agent" and p.get("role") in roles), None)
    policy = deepcopy(base.get("alertPolicy") or {})
    start_event = next((e for e in events if e.get("type") == "startEvent"), {})
    # B7: 사람 입력 경보 패턴(오일 분석 등, human_alert.PATTERNS)도 경보 시작으로 고를 수 있다 — 기준 정의의 경보 정책은 그대로 두고
    # 이 목록에만 보탠다(기준 흐름은 이 패턴을 받지 않으므로 배포 흐름이 없으면 사람 검토로 간다).
    from . import human_alert, business_monitor
    # C2: 업무 데이터 감시 경보(ERP 재고 기준 이탈 SPARE_BELOW_MIN)도 같은 방식으로 보탠다(business_monitor.PATTERNS)
    offered = policy.get("patterns") and start_event.get("eventDefinition") == "message"
    human = ({p: c for p, c in human_alert.policy_patterns().items() if p not in (policy.get("patterns") or {})} if offered else {})
    business = ({p: c for p, c in business_monitor.policy_patterns().items() if p not in (policy.get("patterns") or {})}
                if offered else {})
    if human or business:
        policy["patterns"] = dict(policy["patterns"], **human, **business)
    return {"base": {"id": base.get("processDefinitionId"), "version": base.get("version"), "name": base.get("processDefinitionName")},
            "parts": parts + general, "roles": role_list, "agents": agents, "agent_role": agent_role,
            "patterns": list((policy.get("patterns") or {}).keys()), "alert_policy": policy, "human_patterns": list(human),
            "business_patterns": list(business),
            "alert_start": {k: deepcopy(v) for k, v in start_event.items() if k not in ("id", "name")} if start_event.get("eventDefinition") == "message" else None,
            "data": {d["name"]: deepcopy(d) for d in base.get("data") or [] if isinstance(d, dict) and d.get("name")},
            "field_types": list(FIELD_TYPES), "ops": list(OPS), "alert_start_values": list(ALERT_START_VALUES),
            "approval_values": list(APPROVAL_SERVER_VALUES)}


# ---------------------------------------------------------------- 3. 매핑 (기본값 · 다시 가져오기)
def empty_mapping() -> dict:
    return {"name": "", "start": {}, "lanes": {}, "tasks": {}, "timers": {}, "flows": {}}


def merge_mapping(parsed: dict, old: dict | None, cat: dict) -> tuple[dict, dict]:
    """같은 id 의 앞선 선택을 유지하고, 그림에서 사라진 id 의 선택은 버린다. 새 task 는 비워 둔다(부품은 사람이 고른다)."""
    old = old if isinstance(old, dict) else {}
    m = empty_mapping()
    m["name"] = str(old.get("name") or "")
    task_ids = {t["id"] for t in parsed["tasks"]}
    lane_ids = {l["id"] for l in parsed["lanes"]}
    timer_ids = {b["id"] for b in parsed["boundaries"]}
    flow_ids = {f["id"] for f in parsed["flows"]}
    report = {"kept": [], "dropped": [], "new": []}
    for key, ids, kind in (("tasks", task_ids, "task"), ("lanes", lane_ids, "lane"), ("timers", timer_ids, "boundary"), ("flows", flow_ids, "flow")):
        for k, v in (old.get(key) or {}).items():
            if k in ids:
                m[key][k] = deepcopy(v)
                if kind == "task":
                    report["kept"].append(k)
            elif kind == "task":
                report["dropped"].append(k)
    report["new"] = [t["id"] for t in parsed["tasks"] if t["id"] not in m["tasks"]]
    start = old.get("start") if isinstance(old.get("start"), dict) else {}
    if start.get("kind") in ("alert", "human"):
        m["start"] = deepcopy(start)
    else:
        message = any(s.get("definition") == "message" for s in parsed["starts"])
        sensor = [p for p in cat["patterns"] if p not in (cat.get("human_patterns") or []) + (cat.get("business_patterns") or [])]   # 메시지 시작의 기본값은 감지기 경보(사람 입력 · 업무 감시는 사람이 고름)
        m["start"] = ({"kind": "alert", "patterns": sensor} if message and sensor
                      else {"kind": "human", "fields": []})
    role_names = {r["name"] for r in cat["roles"]}
    for lane in parsed["lanes"]:
        if lane["id"] not in m["lanes"] and lane["name"] in role_names:
            m["lanes"][lane["id"]] = lane["name"]          # 칸 이름이 역할 이름과 같으면 그 역할(사람이 바꿀 수 있음)
    return m, report


def suggest_definition_id(parsed: dict) -> str:
    raw = parsed["process"]["id"] or ""
    cand = re.sub(r"[^A-Za-z0-9_.-]", "_", raw).strip("_.-")
    if cand and DEF_ID_RE.match(cand):
        return cand
    return "flow_" + hashlib.sha1(raw.encode()).hexdigest()[:8]


def valid_definition_id(def_id) -> bool:
    return isinstance(def_id, str) and bool(DEF_ID_RE.match(def_id))


# ---------------------------------------------------------------- 4. 정의 만들기 + 사전 검사
def _identifier(name) -> bool:
    return isinstance(name, str) and name.isidentifier() and not keyword.iskeyword(name) and name not in ("True", "False", "None")


def _fields(spec, where: dict, field: str, problems: list) -> list[dict] | None:
    """폼 칸 [{key, text, type, items?}] 검사. 틀리면 problems 에 칸 위치와 사유."""
    if spec in (None, ""):
        return []
    if not isinstance(spec, list):
        problems.append(problem(where, field, "폼 칸은 목록이어야 합니다"))
        return None
    out, keys = [], set()
    for i, f in enumerate(spec, 1):
        if not isinstance(f, dict):
            problems.append(problem(where, field, f"{i}번째 칸 형식이 올바르지 않습니다")); return None
        key, kind = str(f.get("key") or "").strip(), f.get("type") or "text"
        if not _identifier(key):
            problems.append(problem(where, field, f"{i}번째 칸 값 이름 '{key}'은(는) 쓸 수 없습니다 (글자로 시작, 띄어쓰기 · 기호 없이)")); return None
        if key in keys:
            problems.append(problem(where, field, f"값 이름 '{key}'이(가) 두 번 있습니다")); return None
        if key in PROTECTED_OUTPUTS or key == "decision_id":
            problems.append(problem(where, field, f"값 이름 '{key}'은(는) 서버 승인 경로만 만들 수 있습니다")); return None
        if kind not in FIELD_TYPES:
            problems.append(problem(where, field, f"'{key}' 칸 종류 {kind} 는 쓸 수 없습니다 ({', '.join(FIELD_TYPES)})")); return None
        item = {"key": key, "text": str(f.get("text") or key), "type": kind}
        if kind == "select":
            items = [str(x).strip() for x in (f.get("items") or []) if str(x).strip()]
            if not items:
                problems.append(problem(where, field, f"'{key}' 선택 칸에 고를 값이 없습니다")); return None
            item["items"] = items
        if f.get("required") is False:
            item["required"] = False
        keys.add(key)
        out.append(item)
    return out


def _literal(value, op: str) -> str | None:
    if isinstance(value, bool):
        return "True" if value else "False"
    if value is None:
        return "None" if op in ("==", "!=") else None
    if isinstance(value, (int, float)):
        return repr(value) if math.isfinite(value) else None
    if isinstance(value, str):
        return repr(value) if op in ("==", "!=") else None
    return None


def condition_text(spec: dict) -> str:
    """{var, op, value} → 엔진 조건식(앞 단계 값 기준). 틀리면 ValueError(사유)."""
    var, op = spec.get("var"), spec.get("op") or "=="
    if not _identifier(var):
        raise ValueError("조건에 쓸 값을 고르세요")
    if op not in OPS:
        raise ValueError(f"비교 방법 {op} 은 쓸 수 없습니다")
    lit = _literal(spec.get("value"), op)
    if lit is None:
        raise ValueError("크기 비교(>, >=, <, <=)에는 숫자 값을 넣으세요")
    text = f"{var} {op} {lit}"
    engine.compile_condition(text)
    return text


class _Graph:
    def __init__(self, parsed: dict):
        self.nodes = {i["id"]: i for k in ("tasks", "starts", "ends", "boundaries", "gateways") for i in parsed[k]}
        self.out, self.inc = {n: [] for n in self.nodes}, {n: [] for n in self.nodes}
        for f in parsed["flows"]:
            if f["source"] in self.nodes and f["target"] in self.nodes:
                self.out[f["source"]].append(f)
                self.inc[f["target"]].append(f)
        self.attached = {}
        for b in parsed["boundaries"]:
            if b["attached_to"] in self.nodes:
                self.attached.setdefault(b["attached_to"], []).append(b["id"])
        self.pred = {n: [] for n in self.nodes}
        for n in self.nodes:
            for m in self.succ(n):
                self.pred[m].append(n)

    def succ(self, n, through=True) -> list[str]:
        return [f["target"] for f in self.out.get(n, [])] + (self.attached.get(n, []) if through else [])

    def reach(self, starts, stop=lambda n: False) -> set[str]:
        """starts 에서 닿는 노드. stop(n) 이면 n 에는 닿되 그 뒤 선은 따르지 않는다(경계 타이머는 따른다 — 승인이 안 된 갈래)."""
        seen, stack = set(), list(starts)
        while stack:
            n = stack.pop()
            if n in seen or n not in self.nodes:
                continue
            seen.add(n)
            stack.extend(self.attached.get(n, []) if stop(n) else self.succ(n))
        return seen

    def ancestors(self, target) -> set[str]:
        seen, stack = set(), list(self.pred.get(target, []))
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            stack.extend(self.pred[n])
        return seen

    def sccs(self) -> list[set[str]]:
        index, low, onstack, stack, out, counter = {}, {}, set(), [], [], [0]
        def strong(v):
            index[v] = low[v] = counter[0]; counter[0] += 1
            stack.append(v); onstack.add(v)
            for w in self.succ(v):
                if w not in index:
                    strong(w); low[v] = min(low[v], low[w])
                elif w in onstack:
                    low[v] = min(low[v], index[w])
            if low[v] == index[v]:
                comp = set()
                while True:
                    w = stack.pop(); onstack.discard(w); comp.add(w)
                    if w == v:
                        break
                if len(comp) > 1 or v in self.succ(v):
                    out.append(comp)
        for v in self.nodes:
            if v not in index:
                strong(v)
        return out


def check(parsed: dict, mapping: dict, ctx: dict) -> dict:
    """정의 JSON 을 만들고 사전 검사한다. ctx = {catalog, definition_id, version, name, file_name, xml_sha256}.
    돌려줌: {ok, problems:[{where, field, reason}], definition, available:{node id: [{value, from}]}}."""
    cat = ctx["catalog"]
    mapping = mapping if isinstance(mapping, dict) else {}
    problems = list(parsed.get("problems") or [])
    g = _Graph(parsed)
    parts = {p["key"]: p for p in cat["parts"]}
    roles = {r["name"]: r for r in cat["roles"]}
    agents = {a["id"] for a in cat["agents"]}
    lanes = {l["id"]: l for l in parsed["lanes"]}
    lane_role = {k: v for k, v in (mapping.get("lanes") or {}).items() if k in lanes}
    for lid, rname in lane_role.items():
        if rname and rname not in roles:
            problems.append(problem(lanes[lid], "role", f"역할 '{rname}'이(가) 역할 목록에 없습니다"))
    task_map = mapping.get("tasks") if isinstance(mapping.get("tasks"), dict) else {}
    activities, forms, used_roles, produced_by = [], {}, [], {}
    start_spec = mapping.get("start") if isinstance(mapping.get("start"), dict) else {}
    start_values: list[str] = []
    start_form = None

    # -- 시작 조건
    starts = parsed["starts"]
    if not starts:
        problems.append(problem({"kind": "process", "id": parsed["process"]["id"], "name": parsed["process"]["name"]}, "start",
                                "시작 이벤트가 없습니다"))
    elif len(starts) > 1:
        for s in starts[1:]:
            problems.append(problem(s, "start", "시작 이벤트는 하나만 둘 수 있습니다"))
    start_node = starts[0] if starts else None
    alert_policy = None
    kind = start_spec.get("kind")
    if kind == "alert":
        chosen = [p for p in (start_spec.get("patterns") or []) if isinstance(p, str)]
        unknown = [p for p in chosen if p not in cat["patterns"]]
        if not cat["alert_start"] or not cat["patterns"]:
            problems.append(problem(start_node, "start", "기준 정의에 경보 시작 계약이 없어 경보로 시작할 수 없습니다"))
        elif unknown:
            problems.append(problem(start_node, "start.patterns", f"경보 패턴 {', '.join(unknown)} 은(는) 경보 정책에 없습니다"))
        elif not chosen:
            problems.append(problem(start_node, "start.patterns", "이 흐름을 시작할 경보 패턴을 하나 이상 고르세요"))
        else:
            policy = cat["alert_policy"]
            alert_policy = {"patterns": {p: deepcopy(policy["patterns"][p]) for p in cat["patterns"] if p in chosen},
                            "unsupported": deepcopy(policy.get("unsupported"))}
        start_values = list(ALERT_START_VALUES)
    elif kind == "human":
        fields = _fields(start_spec.get("fields"), start_node or {"kind": "start", "id": "", "name": ""}, "start.fields", problems)
        if fields is not None:
            start_form = {"fields_json": fields}
            start_values = [f["key"] for f in fields]
    else:
        problems.append(problem(start_node, "start", "시작 조건을 고르세요 (경보 패턴 또는 사람 입력 · 직접 시작)"))

    # -- task → 부품
    for t in parsed["tasks"]:
        m = task_map.get(t["id"]) if isinstance(task_map.get(t["id"]), dict) else {}
        key = m.get("part")
        lane_r = lane_role.get(t.get("lane") or "")
        if not key:
            problems.append(problem(t, "part", "부품을 고르세요")); continue
        p = parts.get(key)
        if p is None:
            problems.append(problem(t, "part", "고른 부품이 부품 목록에 없습니다 (기준 정의가 바뀌었나요?)")); continue
        inputs = [v for v in (m.get("inputs") or []) if isinstance(v, str) and v.strip()]
        bad = [v for v in inputs if not _identifier(v)]
        if bad:
            problems.append(problem(t, "inputs", f"받을 값 이름 {', '.join(bad)} 을(를) 쓸 수 없습니다")); continue
        if p["group"] == "scenario":
            a = deepcopy(p["contract"])
            a["id"], a["name"] = t["id"], t["name"] or p["name"]
            if p["kind"] == "human" and m.get("role"):
                r = roles.get(m["role"])
                if r is None or not r["human"]:
                    problems.append(problem(t, "role", f"'{m['role']}'은(는) 사람 역할이 아닙니다")); continue
                a["role"] = r["name"]
            if p["kind"] == "agent" and m.get("agent"):
                if m["agent"] not in agents:
                    problems.append(problem(t, "agent", f"에이전트 {m['agent']} 가 에이전트 목록에 없습니다")); continue
                a["agent"] = m["agent"]
            if p["form_id"]:
                forms[p["form_id"]] = deepcopy(p["form"])
            if lane_r and lane_r != a.get("role") and p["kind"] != "human":
                pass                                           # 시스템 · 에이전트 부품은 부품 담당이 정한다(칸 이름은 그림 정보)
        elif key in effect_parts.PARTS:                        # C2: 승인 뒤 실행 부품
            config = m.get("config") if isinstance(m.get("config"), dict) else {}
            sys_role = next((r["name"] for r in cat["roles"] if r.get("endpoint") == engine.SYSTEM_USER), None)
            a = effect_parts.activity_for(key, t, config, inputs, sys_role)
            try:
                effect_parts.validate(a)
            except ValueError as e:
                problems.append(problem(t, "config", str(e).split(": ", 1)[-1])); continue
        elif key == "human":
            rname = m.get("role") or lane_r
            r = roles.get(rname or "")
            if r is None:
                problems.append(problem(t, "role", "담당 역할을 고르세요 (칸 이름이 역할 이름과 다르면 직접 고릅니다)")); continue
            if not r["human"]:
                problems.append(problem(t, "role", f"'{rname}'은(는) 사람 역할이 아닙니다 — 시스템 · 에이전트 일은 해당 부품을 고르세요")); continue
            fields = _fields(m.get("fields"), t, "fields", problems)
            if fields is None:
                continue
            fid = _form_id(t["id"], forms)
            forms[fid] = {"fields_json": fields}
            a = {"id": t["id"], "name": t["name"] or "사람 task", "type": "userTask", "role": r["name"], "tool": f"formHandler:{fid}",
                 "agent": None, "instruction": str(m.get("instruction") or ""), "inputData": inputs,
                 "outputData": [f["key"] for f in fields], "checkpoints": [], "duration": 1, "description": t["name"] or "사람 task"}
        else:                                                   # agent
            agent = m.get("agent") or (cat["agents"][0]["id"] if cat["agents"] else None)
            if agent not in agents:
                problems.append(problem(t, "agent", "맡길 에이전트를 고르세요")); continue
            instruction = str(m.get("instruction") or "").strip()
            if not instruction:
                problems.append(problem(t, "instruction", "에이전트 지시문을 쓰세요")); continue
            outs = _fields([o if isinstance(o, dict) else {"key": o} for o in (m.get("outputs") or [])], t, "outputs", problems)
            if outs is None:
                continue
            if not outs:
                problems.append(problem(t, "outputs", "결과 값 이름을 하나 이상 쓰세요")); continue
            if not cat["agent_role"]:
                problems.append(problem(t, "agent", "기준 정의에 에이전트 역할이 없습니다")); continue
            fid = _form_id(t["id"], forms)
            forms[fid] = {"fields_json": outs}
            a = {"id": t["id"], "name": t["name"] or "에이전트 task", "type": "userTask", "role": cat["agent_role"], "agent": agent,
                 "agentMode": "COMPLETE", "orchestration": engine.AGENT_ORCH, "tool": f"formHandler:{fid}", "instruction": instruction,
                 "inputData": inputs, "outputData": [o["key"] for o in outs],
                 "checkpoints": ["승인 전에는 조회 · 계산 · 보고서만 한다 (설비 명령 · 업무 쓰기 없음)"], "duration": 1,
                 "description": t["name"] or "에이전트 task"}
        attached = [b["id"] for b in parsed["boundaries"] if b["attached_to"] == t["id"]]
        if attached:
            a["attachedEvents"] = attached
        else:
            a.pop("attachedEvents", None)
        a["_part"] = p
        activities.append(a)
        if a.get("role") and a["role"] not in used_roles:
            used_roles.append(a["role"])
        outs = list(a.get("outputData") or []) + (list(APPROVAL_SERVER_VALUES) if p.get("approval") else [])
        for v in outs:
            produced_by.setdefault(v, []).append(t["id"])
    acts = {a["id"]: a for a in activities}

    # -- 이벤트
    events = []
    if start_node:
        ev = {"id": start_node["id"], "name": start_node["name"] or "시작", "type": "startEvent"}
        if kind == "alert" and cat["alert_start"]:
            ev.update(deepcopy(cat["alert_start"]))
        else:
            ev["eventDefinition"] = "none"
        events.append(ev)
        for s in starts[1:]:
            events.append({"id": s["id"], "name": s["name"], "type": "startEvent", "eventDefinition": "none"})
    for e in parsed["ends"]:
        events.append({"id": e["id"], "name": e["name"] or "끝", "type": "endEvent", "eventDefinition": e.get("definition") or "none"})
    timers = mapping.get("timers") if isinstance(mapping.get("timers"), dict) else {}
    for b in parsed["boundaries"]:
        host = acts.get(b["attached_to"])
        default = host["_part"].get("default_timer") if host else None
        timer = timers.get(b["id"]) or b.get("timer") or default
        if not timer:
            problems.append(problem(b, "timer", "시간 초과 기간을 정하세요 (예: 10분)"))
        else:
            try:
                ok = engine.iso_duration_seconds(timer) > 0
            except Exception:  # noqa: BLE001
                ok = False
            if not ok:
                problems.append(problem(b, "timer", f"기간 '{timer}'을(를) 읽을 수 없습니다 (예: PT10M)"))
        events.append({"id": b["id"], "name": b["name"] or "시간 초과", "type": "boundaryEvent", "eventDefinition": "timer",
                       "timer": timer, "attachedTo": b["attached_to"]})

    # -- 분기 · 선
    flow_map = mapping.get("flows") if isinstance(mapping.get("flows"), dict) else {}
    gateways, sequences = [], []
    cond_of = {}
    for gw in parsed["gateways"]:
        outs = g.out.get(gw["id"], [])
        item = {"id": gw["id"], "name": gw["name"] or ("분기" if gw["gateway_type"] == "exclusiveGateway" else "함께 진행"),
                "type": gw["gateway_type"]}
        names = set()
        if gw["gateway_type"] == "exclusiveGateway" and len(outs) > 1:
            defaults = 0
            for f in outs:
                spec = flow_map.get(f["id"]) if isinstance(flow_map.get(f["id"]), dict) else None
                if spec is None and gw.get("default") == f["id"]:
                    spec = {"default": True}
                if spec is None and f.get("condition_xml"):
                    try:
                        engine.compile_condition(f["condition_xml"]); spec = {"text": f["condition_xml"]}
                    except Exception:  # noqa: BLE001
                        spec = None
                where = dict(f, name=f["name"] or f"{_label(gw)} → {_label(g.nodes.get(f['target'], {'id': f['target']}))}")
                if not spec:
                    problems.append(problem(where, "condition", f"분기 {_label(gw)}에서 나가는 선의 조건이 없습니다 (값 · 비교 · 기준을 고르거나 '그 밖의 경우')"))
                    continue
                if spec.get("default"):
                    defaults += 1
                    cond_of[f["id"]] = {"default": True}
                    continue
                try:
                    text = spec["text"] if spec.get("text") else condition_text(spec)
                except (ValueError, SyntaxError) as e:
                    problems.append(problem(where, "condition", f"조건이 올바르지 않습니다: {e}"))
                    continue
                cond_of[f["id"]] = {"condition": text}
                names |= {n.id for n in ast.walk(engine.compile_condition(text)) if isinstance(n, ast.Name)} - {"True", "False", "None"}
            if defaults > 1:
                problems.append(problem(gw, "condition", "'그 밖의 경우' 선은 하나만 둘 수 있습니다"))
            item["conditionData"] = sorted(names)
        elif gw["gateway_type"] == "exclusiveGateway":
            item["conditionData"] = []
        gateways.append(item)
    for f in parsed["flows"]:
        if f["source"] not in g.nodes or f["target"] not in g.nodes:
            continue
        s = {"id": f["id"], "source": f["source"], "target": f["target"]}
        if f["name"]:
            s["name"] = f["name"]
        c = cond_of.get(f["id"])
        if c and c.get("condition"):
            s["condition"] = c["condition"]
        elif c and c.get("default"):
            s["properties"] = {"default": True}
        sequences.append(s)

    # -- 그래프 검사: 끊긴 선 · 닿지 않음 · 끝 닫힘 · 갈림
    _graph_problems(parsed, g, start_node, problems)

    # -- 값 연결: 다음 단계가 기다리는 값을 앞 단계(또는 시작)가 내는가
    available = {}
    for nid in g.nodes:
        anc = g.ancestors(nid) if start_node else set()
        vals = [{"value": v, "from": "start"} for v in start_values]
        for v, producers in produced_by.items():
            src = [pid for pid in producers if pid in anc]
            if src:
                vals.append({"value": v, "from": src[0]})
        available[nid] = vals
    for a in activities:
        have = {x["value"] for x in available.get(a["id"], [])}
        t = g.nodes[a["id"]]
        missing = [v for v in a.get("inputData") or [] if v not in have]
        if missing and start_node:
            problems.append(problem(t, "inputs", f"받을 값 {', '.join(missing)} 을(를) 앞 단계(또는 시작)가 내지 않습니다"))
    for f in parsed["flows"]:
        c = cond_of.get(f["id"])
        if not c or not c.get("condition") or not start_node:
            continue
        need = {n.id for n in ast.walk(engine.compile_condition(c["condition"])) if isinstance(n, ast.Name)} - {"True", "False", "None"}
        have = {x["value"] for x in available.get(f["source"], [])}
        miss = sorted(need - have)
        if miss:
            problems.append(problem(f, "condition", f"조건 값 {', '.join(miss)} 을(를) 분기 앞 단계가 내지 않습니다"))

    # -- 안전: 효과 부품(설비 명령 · 작업지시) 앞 경로에 사람 승인(조치 선택)이 있는가
    approvals = {a["id"] for a in activities if a["_part"].get("approval")}
    approval_name = next((p["name"] for p in cat["parts"] if p.get("approval")), "사람 승인")
    if start_node:
        free = g.reach([start_node["id"]], stop=lambda n: n in approvals)
        for a in activities:
            effect = a["_part"].get("effect")
            if not effect:
                continue
            t = g.nodes[a["id"]]
            if a["id"] in free:
                problems.append(problem(t, "part", f"{effect} 부품 앞 경로에 사람 승인('{approval_name}')이 없습니다 — "
                                                   "승인 없이 설비 · 업무에 효과를 내는 흐름은 등록하지 않습니다"))
            elif a["id"] in g.reach(g.succ(a["id"]), stop=lambda n: n in approvals):
                problems.append(problem(t, "part", f"되돌아가는 선이 {effect} 부품을 사람 승인 없이 다시 실행합니다 — "
                                                   f"되돌아가는 선이 '{approval_name}'을(를) 다시 거치게 그리세요"))

    # -- 되돌아가는 선(루프): 빠져나갈 배타 분기가 있어야, 병렬 분기는 안에 둘 수 없음
    loops = g.sccs()
    for comp in loops:
        members = sorted(comp)
        exits = [n for n in comp if n in g.nodes and g.nodes[n]["kind"] == "gateway" and g.nodes[n]["gateway_type"] == "exclusiveGateway"
                 and any(f["target"] not in comp for f in g.out.get(n, []))]
        first = g.nodes[members[0]]
        if not exits:
            problems.append(problem(first, "loop", "되돌아가는 선에서 빠져나갈 배타 분기가 없습니다 (끝나지 않는 반복)"))
        par = [n for n in comp if g.nodes[n]["kind"] == "gateway" and g.nodes[n]["gateway_type"] == "parallelGateway"]
        if par:
            problems.append(problem(g.nodes[par[0]], "loop", "되돌아가는 선 안의 병렬 분기는 아직 실행하지 않습니다"))

    # -- 정의 JSON
    used = []
    for a in activities:
        for v in list(a.get("inputData") or []) + list(a.get("outputData") or []):
            if v not in used:
                used.append(v)
    for gw in gateways:
        for v in gw.get("conditionData") or []:
            if v not in used:
                used.append(v)
    for v in start_values if kind == "human" else []:
        if v not in used:
            used.append(v)
    field_type = {f["key"]: f["type"] for form in forms.values() for f in form["fields_json"]}
    if start_form:
        field_type.update({f["key"]: f["type"] for f in start_form["fields_json"]})
    data = [deepcopy(cat["data"][v]) if v in cat["data"] else
            {"name": v, "type": SERVER_VALUE_TYPES.get(v) or DATA_TYPE.get(field_type.get(v), "Text")}
            for v in used]
    role_rows = []
    for rname in used_roles:
        r = roles.get(rname)
        if r:
            row = {"name": r["name"], "endpoint": r["endpoint"]}
            if r.get("resolutionRule"):
                row["resolutionRule"] = r["resolutionRule"]
            role_rows.append(row)
    for a in activities:
        a.pop("_part", None)
    raw = {"processDefinitionId": ctx.get("definition_id") or "", "processDefinitionName": (mapping.get("name") or ctx.get("name")
           or parsed["process"]["name"] or ctx.get("definition_id") or ""),
           "version": ctx.get("version") or "draft", "description": f"bpmn.io 그림 '{ctx.get('file_name') or ''}'에서 가져온 흐름",
           "data": data, "roles": role_rows, "events": events, "activities": activities, "gateways": gateways,
           "sequences": sequences, "forms": forms}
    if alert_policy:
        raw["alertPolicy"] = alert_policy
    if start_form is not None:
        raw["startForm"] = start_form
    if loops:
        raw["loopPolicy"] = "guarded"
    raw["bpmnImport"] = {"processId": parsed["process"]["id"], "fileName": ctx.get("file_name"),
                         "sha256": ctx.get("xml_sha256"), "base": {"id": cat["base"]["id"], "version": cat["base"]["version"]},
                         "mapping": deepcopy(mapping)}

    # -- 등록 검사(엔진 계약). 위 검사를 통과했을 때만 — 같은 사유를 두 번 보이지 않게.
    if not problems:
        try:
            validate_definition(deepcopy(raw))
        except ValueError as e:
            problems.append(problem({"kind": "process", "id": parsed["process"]["id"], "name": parsed["process"]["name"]},
                                    "registration", f"등록 검사: {e}"))
    return {"ok": not problems, "problems": problems, "definition": raw, "available": available,
            "loops": [sorted(c) for c in loops]}


def _form_id(task_id: str, forms: dict) -> str:
    base = "u_" + (re.sub(r"[^A-Za-z0-9_]", "_", task_id).strip("_") or hashlib.sha1(task_id.encode()).hexdigest()[:8])
    fid, n = base, 2
    while fid in forms:
        fid, n = f"{base}_{n}", n + 1
    return fid


def _graph_problems(parsed: dict, g: _Graph, start_node: dict | None, problems: list) -> None:
    for nid, item in g.nodes.items():
        kind = item["kind"]
        inc, out = g.inc[nid], g.out[nid]
        if kind == "start":
            if inc:
                problems.append(problem(item, "flow", "시작 이벤트로 들어오는 선이 있습니다"))
            if not out:
                problems.append(problem(item, "flow", "끊긴 선: 시작 이벤트에서 나가는 선이 없습니다"))
        elif kind == "end":
            if out:
                problems.append(problem(item, "flow", "끝 이벤트에서 나가는 선이 있습니다"))
            if not inc:
                problems.append(problem(item, "flow", "끊긴 선: 끝 이벤트로 들어오는 선이 없습니다"))
        elif kind == "boundary":
            if inc:
                problems.append(problem(item, "flow", "경계 타이머로 들어오는 선이 있습니다"))
            if not out:
                problems.append(problem(item, "flow", "끊긴 선: 시간 초과 뒤 갈 곳(나가는 선)이 없습니다"))
        else:
            if not inc:
                problems.append(problem(item, "flow", "끊긴 선: 들어오는 선이 없습니다"))
            if not out:
                problems.append(problem(item, "flow", "끊긴 선: 나가는 선이 없습니다 (끝 이벤트로 이어 주세요)"))
        if kind in ("task", "start", "boundary") and len({f["target"] for f in out}) > 1:
            problems.append(problem(item, "flow", f"분기 없이 {len(out)}갈래로 나뉩니다 — 배타(X) 또는 병렬(+) 분기를 거쳐 나누세요"))
    if not parsed["ends"]:
        problems.append(problem({"kind": "process", "id": parsed["process"]["id"], "name": parsed["process"]["name"]}, "end",
                                "끝 이벤트가 없습니다 (끝이 닫히지 않음)"))
    if start_node is None:
        return
    reach = g.reach([start_node["id"]])
    ends = {e["id"] for e in parsed["ends"]}
    to_end, pred = set(), g.pred
    stack = list(ends)
    while stack:
        n = stack.pop()
        if n in to_end:
            continue
        to_end.add(n)
        stack.extend(pred[n])
    for nid, item in g.nodes.items():
        if item["kind"] == "start":
            continue
        if nid not in reach and g.inc[nid]:
            problems.append(problem(item, "flow", "시작에서 닿지 않습니다"))
        if nid in reach and nid not in to_end and g.out[nid]:
            problems.append(problem(item, "flow", "여기서 끝 이벤트에 닿지 못합니다 (끝이 닫히지 않음)"))


# ---------------------------------------------------------------- 5. 구조 서명 (id · 이름 · 설명 제외)
def structure(raw: dict) -> dict:
    acts = {a["id"]: a for a in raw.get("activities") or []}
    events = {e["id"]: e for e in raw.get("events") or []}
    gws = {g["id"]: g for g in raw.get("gateways") or []}
    roles = {r["name"]: r.get("endpoint") for r in raw.get("roles") or []}
    label = {}
    for a in acts.values():
        label[a["id"]] = "A:" + str(a.get("tool"))
    for g in gws.values():
        label[g["id"]] = f"G:{g.get('type')}:{','.join(sorted(g.get('conditionData') or []))}"
    for e in events.values():
        if e["type"] == "boundaryEvent":
            label[e["id"]] = f"B:{e.get('timer')}@{label.get(e.get('attachedTo'))}"
        else:
            label[e["id"]] = f"{e['type']}:{e.get('eventDefinition') or 'none'}"
    def act(a):
        keep = ("type", "agent", "agentMode", "orchestration", "decision", "tool", "instruction", "checkpoints", "duration")
        return {**{k: a.get(k) for k in keep}, "role": roles.get(a.get("role")), "inputData": sorted(a.get("inputData") or []),
                "outputData": sorted(a.get("outputData") or [])}
    edges = sorted((label[s["source"]], label[s["target"]], s.get("condition") or "", bool(engine._properties(s).get("default")))
                   for s in raw.get("sequences") or [])
    edges += sorted((label[a["id"]], label[ev], "boundary", False) for a in acts.values() for ev in a.get("attachedEvents") or [])
    start = [e for e in events.values() if e["type"] == "startEvent"]
    return {"activities": sorted((label[a["id"]], repr(act(a))) for a in acts.values()),
            "events": sorted(label[e] for e in events),
            "start": [{k: v for k, v in e.items() if k not in ("id", "name")} for e in start],
            "gateways": sorted(label[g] for g in gws), "edges": edges, "roles": sorted(roles.items()),
            "data": sorted(d["name"] for d in raw.get("data") or []), "forms": {k: v for k, v in sorted((raw.get("forms") or {}).items())},
            "alertPolicy": raw.get("alertPolicy")}
