"""C2 (확정 TODO C) 승인 뒤 실행 부품 — BPMN 시스템 · 서비스 task 로 고르는 일반 부품(시나리오에 묶이지 않음). 순수 로직(IO 없음).

사람 승인 1회 뒤 process 가 실행한다(CLAUDE.md §4). 에이전트는 읽기 도구만 쓰고, 아래 쓰기는 모두 이 부품(시스템 task)이 한다.

  부품(카탈로그 key)        tool                      하는 일                                              효과?
  svc:mcp-call             mcp:call                  등록된 MCP 서버의 도구 하나를 부른다(메일 · 일정 · 기록) — 인자 틀에 처리 건 값 치환   예
  svc:erp-po               enterprise:PR_CREATE      ERP 발주 — 승인 경로가 확정한 공급사 · 수량 · 금액(approved_*)으로             예
  svc:wait                 process:wait              시간 대기 — 기간(ISO) 또는 처리 건 값의 시각까지. 배속 × 수업 압축 배율        아니오
  svc:maintenance          plant:restore             정비 수행 모사 — 작업지시 완료(부품 소모) + 시뮬레이터 복구 + 완료 공지         예
  svc:goods-receipt        enterprise:GR_CONFIRM     입고 확인 — 발주의 입고 예정까지 기다렸다가 입고 · 검수 기록, 사건 종결       예
  svc:test-run             plant:test-run            시운전 확인 — 안정 시간 뒤 압력 · 유량 · 진동을 기준과 비교, 통과면 계수기 리셋   예
  svc:report               process:report            결과 보고 — 결과(정상 · 미달 · 지연 · 알림)를 담당자에게 알리고 사건을 닫는다    아니오

활동(activity) 모양: {"type": "serviceTask", "tool": <tool>, "service": {<부품 설정>}, "inputData": [...], "outputData": [...]}.
설정 · 출력 이름은 validate(activity)가 검사하고(등록 · 가져오기 검사), 실행은 instances.InstanceRuntime 의 부품 처리기가 한다.

시간: 업무 시간(정비창까지 9 h, 리드타임 5일)은 가상 시간이다. 실제 대기 = 가상 시간 ÷ (TIME_SCALE × 수업 압축 배율)
(engine.wait_compression, 환경변수 PROCESS_WAIT_COMPRESSION). 설비 물리 · 감지기 · 재관측 · 사람 응답 타이머는 배속만 쓴다.
"""
from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from . import engine

MCP_TOOL = "mcp:call"
PR_TOOL = "enterprise:PR_CREATE"
WAIT_TOOL = "process:wait"
RESTORE_TOOL = "plant:restore"
GR_TOOL = "enterprise:GR_CONFIRM"
TEST_RUN_TOOL = "plant:test-run"
REPORT_TOOL = "process:report"
TOOLS = (MCP_TOOL, PR_TOOL, WAIT_TOOL, RESTORE_TOOL, GR_TOOL, TEST_RUN_TOOL, REPORT_TOOL)
#: 바깥(업무 시스템 · 메일 · 설비 시뮬레이터)에 효과를 내는 부품 — 앞 경로에 사람 승인이 있어야 등록된다(bpmn_import.check)
EFFECTS = {MCP_TOOL: "MCP 쓰기(메일)", PR_TOOL: "ERP 발주", RESTORE_TOOL: "정비 수행 모사", GR_TOOL: "입고 확인",
           TEST_RUN_TOOL: "시운전 확인 · 계수기 리셋"}
#: 시운전 기준 기본값(파워팩 정상 운전점 PS1 182 bar · FS1 9.0 l/min · VS1 0.6 mm/s, 경보선 = 사건 회복 기준과 같은 값 — definition.RECOVERY)
TEST_RUN_CRITERIA = {"PS1": [">=", 165.0], "FS1": [">=", 8.0], "VS1": ["<", 1.2]}
TEST_RUN_OPS = (">=", ">", "<=", "<")
#: 결과 보고의 결과 → 등급(ok 정상 종결 · fail 미달 종결 · info 알림만, 사건은 그대로)
REPORT_OUTCOMES = {"정상": "ok", "입고 완료": "ok", "미달": "fail", "지연": "fail", "알림": "info", "승인 지연": "info"}

NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9]|-(?!-)){0,39}$")         # mcp_registry.NAME_RE 와 같음
TOOL_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
PATH_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)*$")
PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)*)\}")
COMPONENTS = ("cooler", "pump", "fan")                                  # plant-sim 복구 대상(ot/plant-sim FaultReq.component)
#: 승인 경로(select)가 카드에서 확정해 처리 건 값으로 넣는 발주 값 — ERP 발주 · 공급사 메일 · 결과 보고가 쓴다. 2차 승인은 없다
#: (확정 2026-10-09: 담당자 승인 1회. 전결 기준 300만 원 초과는 에이전트 요약 · 승인 화면에 표시만 한다 — PR-07 규칙 rule:pur-amount WARN)
PURCHASE_VALUES = ("approved_amount", "approved_qty", "approved_supplier", "approved_unit_price", "approved_part_no")

PARTS = {
    "svc:mcp-call": {
        "tool": MCP_TOOL, "name": "승인 뒤 MCP 호출 (메일 등)", "outputs": ["mcp_receipt"],
        "help": "등록된 MCP 서버의 도구 하나를 사람 승인 뒤에 부릅니다(쓰기 도구도 됨, 에이전트에게는 보이지 않음). "
                "인자 값의 {값 이름}은 처리 건 값으로 바뀝니다. 수업 기본 서버 hyd-effects: send_mail(메일 → 수업 메일함 Inbucket, 실제 발송 없음).",
        "config": {"server": "MCP 서버 이름 (예: hyd-effects)", "tool": "도구 이름 (예: send_mail)",
                   "arguments": "인자 틀 {이름: 값} — 문자열 안 {asset} · {approved_amount} · {work_order.ref} 처럼 처리 건 값을 넣는다",
                   "output": "결과를 담을 값 이름 (기본 mcp_receipt)"},
    },
    "svc:erp-po": {
        "tool": PR_TOOL, "name": "ERP 발주", "outputs": ["purchase_order"], "inputs": ["approved_amount"],
        "help": "사람이 승인한 카드의 공급사 · 수량 · 금액(approved_supplier · approved_qty · approved_amount)으로 ERP 발주를 냅니다. "
                "ERP 가 견적 · 승인 공급사(AVL) · 금액을 다시 확인하고 입고 예정을 올립니다. mail 을 정하면 발주 뒤 공급사 · 입고 부서에 메일을 보냅니다.",
        "config": {"mail": "발주 뒤 보낼 메일 {to, subject, body} (선택, 수업 메일함 Inbucket — 실제 발송 없음). {purchase_order.ref} 같은 값을 넣는다"},
    },
    "svc:wait": {
        "tool": WAIT_TOOL, "name": "시간 대기", "outputs": ["waited"],
        "help": "정해진 업무 시간(예: PT9H)이나 처리 건 값의 시각(예: work_order.window_starts_at)까지 기다립니다. "
                "수업에서는 배속 × 수업 압축 배율로 줄어 몇 분이면 끝납니다. 경계 타이머를 붙이면 같은 배율이 적용됩니다.",
        "config": {"duration": "기다릴 업무 시간 ISO-8601 (예: PT9H, P5D)", "until": "기다릴 시각이 든 처리 건 값 (예: work_order.window_starts_at)",
                   "label": "화면에 보일 이름 (예: 정비창까지 대기)"},
    },
    "svc:maintenance": {
        "tool": RESTORE_TOOL, "name": "정비 수행 (모사)", "outputs": ["maintenance"], "inputs": ["asset"],
        "help": "현장 정비를 모사합니다: (until 을 정하면 예정된 정비 시간까지 기다린 뒤) 작업지시가 있으면 CMMS 에서 완료 처리(표준 부품 소모), "
                "설비 시뮬레이터의 대상 부품을 정상으로 되돌리고, 완료 공지를 처리 건 참여자에게 남깁니다. 설비 명령 경로(PLC)가 아닌 실습 시뮬레이터 조작입니다.",
        "config": {"component": "되돌릴 부품: cooler · pump · fan (비우면 설비 전체)", "sop": "작업지시 완료 때 부품 소모 기준 SOP (예: SOP-PMP-04, 비우면 카드의 SOP)",
                   "work_order_var": "작업지시 영수증 값 이름 (기본 work_order)",
                   "until": "먼저 기다릴 시각이 든 처리 건 값 (예: work_order.after.window_starts_at — 예정된 정비 시간, 수업 압축 적용)"},
    },
    "svc:goods-receipt": {
        "tool": GR_TOOL, "name": "입고 확인", "outputs": ["goods_receipt", "received"], "inputs": ["purchase_order"],
        "help": "발주의 입고 예정(리드타임)까지 기다린 뒤 입고 · 검수를 ERP 에 기록하고 재고를 올립니다. 확인되면 사건을 닫습니다. "
                "납기 초과를 보이려면 경계 타이머(예: P7D)를 붙입니다(같은 수업 압축 배율).",
        "config": {"purchase_order_var": "발주 영수증 값 이름 (기본 purchase_order)"},
    },
    "svc:test-run": {
        "tool": TEST_RUN_TOOL, "name": "시운전 확인", "outputs": ["test_run", "passed"], "inputs": ["asset"],
        "help": "정비 뒤 설비를 안정시킨 다음(배속만 적용) 압력 · 유량 · 진동의 최신값을 기준과 비교합니다. 모두 통과하면 CMMS 운전시간 계수기를 "
                "리셋하고 다음 기한을 기록합니다. 결과 passed 로 정상/미달 분기를 그립니다.",
        "config": {"criteria": "기준 {태그: [연산, 값]} (기본 PS1 >= 165 · FS1 >= 8 · VS1 < 1.2)", "settle": "안정 시간 ISO-8601 (기본 PT10M, 배속만 적용)",
                   "reset_counter": "통과하면 계수기 리셋 · 다음 기한 기록 (기본 true)", "work_order_var": "작업지시 영수증 값 이름 (기본 work_order)"},
    },
    "svc:report": {
        "tool": REPORT_TOOL, "name": "결과 보고", "outputs": ["result_report"],
        "help": "처리 결과(정상 · 미달 · 지연 · 알림)를 담당자 화면에 알리고 기록합니다. 정상 · 미달은 사건을 닫고, 알림은 사건을 그대로 둡니다. "
                "사람 task 가 아닙니다 — 담당자는 보기만 합니다.",
        "config": {"outcome": "결과: 정상 · 입고 완료 · 미달 · 지연 · 알림 · 승인 지연", "title": "제목 틀 (예: {asset} 정기 정비 결과)",
                   "summary": "요약 틀 — 처리 건 값 {이름} 을 넣는다. 없는 값은 '(없음)'"},
    },
}
BY_TOOL = {p["tool"]: k for k, p in PARTS.items()}


# ---------------------------------------------------------------- 등록 검사
NOTICE_SERVER, NOTICE_TOOL = "hyd-effects", "send_mail"


def notice_spec(mail) -> dict | None:
    """시스템 task 끝에 붙는 메일 공지 설정 → MCP 호출 설정. 없으면 None. {to, subject, body} 또는 {server, tool, arguments}."""
    if mail in (None, {}, ""):
        return None
    if not isinstance(mail, dict):
        raise ValueError("메일 공지(mail)는 {to, subject, body} 객체여야 합니다")
    if "arguments" in mail:
        spec = {"server": mail.get("server") or NOTICE_SERVER, "tool": mail.get("tool") or NOTICE_TOOL, "arguments": mail["arguments"]}
    else:
        spec = {"server": NOTICE_SERVER, "tool": NOTICE_TOOL, "arguments": {k: v for k, v in mail.items() if k in ("to", "cc", "subject", "body")}}
    if not NAME_RE.match(str(spec["server"])) or not TOOL_RE.match(str(spec["tool"])) or not isinstance(spec["arguments"], dict):
        raise ValueError("메일 공지의 서버 · 도구 · 인자가 올바르지 않습니다")
    if spec["tool"] == NOTICE_TOOL and not all(spec["arguments"].get(k) for k in ("to", "subject")):
        raise ValueError("메일 공지에는 받는 사람(to)과 제목(subject)이 있어야 합니다")
    for name in placeholders(spec["arguments"]):
        if not PATH_RE.match(name):
            raise ValueError(f"메일 공지 틀의 {{{name}}} 을(를) 읽을 수 없습니다")
    return spec


def validate(activity: dict) -> None:
    """부품 설정 · 출력 이름 검사. 틀리면 ValueError(사람이 읽는 사유)."""
    tool = activity.get("tool")
    aid = activity.get("id")
    if tool == "enterprise:WO_CREATE":               # 기준 부품(CMMS 작업지시)의 선택 설정: 정비 시점 값 이름 · 생산팀 공지 메일
        cfg = activity.get("service") or {}
        if not isinstance(cfg, dict) or set(cfg) - {"window_var", "mail"}:
            raise ValueError(f"활동 {aid}: 작업지시 설정은 window_var · mail 만 받습니다")
        if cfg.get("window_var") is not None and (not isinstance(cfg["window_var"], str) or not PATH_RE.match(cfg["window_var"])):
            raise ValueError(f"활동 {aid}: window_var 는 처리 건 값 이름(점으로 안쪽 칸, 예: alert.evidence.night_window_id)이어야 합니다")
        try:
            notice_spec(cfg.get("mail"))
        except ValueError as e:
            raise ValueError(f"활동 {aid}: {e}") from e
        return
    if tool not in TOOLS:
        return
    cfg = activity.get("service") if activity.get("service") is not None else {}
    if not isinstance(cfg, dict):
        raise ValueError(f"활동 {aid}: service 설정은 객체여야 합니다")
    if tool == PR_TOOL:
        try:
            notice_spec(cfg.get("mail"))
        except ValueError as e:
            raise ValueError(f"활동 {aid}: {e}") from e
    outs = list(activity.get("outputData") or [])
    if tool == MCP_TOOL:
        if not isinstance(cfg.get("server"), str) or not NAME_RE.match(cfg["server"]):
            raise ValueError(f"활동 {aid}: MCP 서버 이름을 정하세요 (영소문자 · 숫자 · '-')")
        if not isinstance(cfg.get("tool"), str) or not TOOL_RE.match(cfg["tool"]):
            raise ValueError(f"활동 {aid}: MCP 도구 이름을 정하세요")
        args = cfg.get("arguments", {})
        if not isinstance(args, dict) or any(not isinstance(k, str) or not k for k in args):
            raise ValueError(f"활동 {aid}: MCP 인자 틀은 이름 → 값 객체여야 합니다")
        for name in placeholders(args):
            if not PATH_RE.match(name):
                raise ValueError(f"활동 {aid}: 인자 틀의 {{{name}}} 을(를) 읽을 수 없습니다")
        output = cfg.get("output", "mcp_receipt")
        if not isinstance(output, str) or not IDENT_RE.match(output):
            raise ValueError(f"활동 {aid}: 결과 값 이름이 올바르지 않습니다")
        if outs != [output]:
            raise ValueError(f"활동 {aid}: MCP 호출의 outputData 는 [{output}] 이어야 합니다")
        return
    if tool == WAIT_TOOL:
        has_d, has_u = cfg.get("duration") not in (None, ""), cfg.get("until") not in (None, "")
        if has_d == has_u:
            raise ValueError(f"활동 {aid}: 시간 대기는 duration(기간) 또는 until(시각 값) 하나를 정합니다")
        if has_d:
            try:
                ok = engine.iso_duration_seconds(cfg["duration"]) > 0
            except (ValueError, TypeError):
                ok = False
            if not ok:
                raise ValueError(f"활동 {aid}: 대기 기간 '{cfg['duration']}'을(를) 읽을 수 없습니다 (예: PT9H, P5D)")
        elif not isinstance(cfg["until"], str) or not PATH_RE.match(cfg["until"]):
            raise ValueError(f"활동 {aid}: until 은 처리 건 값 이름(점으로 안쪽 칸, 예: work_order.window_starts_at)이어야 합니다")
    if tool == RESTORE_TOOL and cfg.get("component") not in (None, "", *COMPONENTS):
        raise ValueError(f"활동 {aid}: 복구 부품은 {', '.join(COMPONENTS)} 중 하나입니다")
    if tool == RESTORE_TOOL and cfg.get("until") not in (None, "") and (not isinstance(cfg["until"], str) or not PATH_RE.match(cfg["until"])):
        raise ValueError(f"활동 {aid}: until 은 처리 건 값 이름(예: work_order.after.window_starts_at)이어야 합니다")
    if tool == TEST_RUN_TOOL:
        crit = cfg.get("criteria", TEST_RUN_CRITERIA)
        if not isinstance(crit, dict) or not crit or any(not isinstance(t, str) or not re.match(r"^[A-Za-z][A-Za-z0-9_]{0,31}$", t)
                                                          or not isinstance(c, (list, tuple)) or len(c) != 2 or c[0] not in TEST_RUN_OPS
                                                          or isinstance(c[1], bool) or not isinstance(c[1], (int, float)) for t, c in crit.items()):
            raise ValueError(f"활동 {aid}: 시운전 기준은 {{태그: [연산(>=, >, <=, <), 값]}} 이어야 합니다")
        if cfg.get("settle") not in (None, ""):
            try:
                ok = engine.iso_duration_seconds(cfg["settle"]) >= 0
            except (ValueError, TypeError):
                ok = False
            if not ok:
                raise ValueError(f"활동 {aid}: 안정 시간 '{cfg['settle']}'을(를) 읽을 수 없습니다 (예: PT10M)")
        if "reset_counter" in cfg and not isinstance(cfg["reset_counter"], bool):
            raise ValueError(f"활동 {aid}: reset_counter 는 true/false 입니다")
    if tool == REPORT_TOOL:
        if cfg.get("outcome") not in REPORT_OUTCOMES:
            raise ValueError(f"활동 {aid}: 결과 보고의 결과(outcome)는 {', '.join(REPORT_OUTCOMES)} 중 하나입니다")
        for key in ("title", "summary"):
            if cfg.get(key) is not None and not isinstance(cfg[key], str):
                raise ValueError(f"활동 {aid}: {key} 는 글이어야 합니다")
            for name in placeholders(cfg.get(key) or ""):
                if not PATH_RE.match(name):
                    raise ValueError(f"활동 {aid}: {key} 틀의 {{{name}}} 을(를) 읽을 수 없습니다")
    for key in ("work_order_var", "purchase_order_var"):
        if cfg.get(key) is not None and (not isinstance(cfg[key], str) or not IDENT_RE.match(cfg[key])):
            raise ValueError(f"활동 {aid}: {key} 는 값 이름이어야 합니다")
    expected = PARTS[BY_TOOL[tool]]["outputs"]
    if outs != expected:
        raise ValueError(f"활동 {aid}: {PARTS[BY_TOOL[tool]]['name']} 의 outputData 는 {expected} 이어야 합니다")


def activity_for(key: str, task: dict, config: dict | None, inputs: list[str], role: str | None) -> dict:
    """가져오기(bpmn_import)가 그림의 task 하나를 이 부품의 활동으로 만든다. 검사는 validate 가 한다."""
    part = PARTS[key]
    cfg = deepcopy(config) if isinstance(config, dict) else {}
    outs = [cfg.get("output") or "mcp_receipt"] if part["tool"] == MCP_TOOL else list(part["outputs"])
    ins = list(dict.fromkeys([*(part.get("inputs") or []), *inputs]))
    act = {"id": task["id"], "name": task.get("name") or part["name"], "type": "serviceTask", "tool": part["tool"], "service": cfg,
           "inputData": ins, "outputData": outs, "checkpoints": ["사람 승인 뒤 process 가 실행한다"] if part["tool"] in EFFECTS else [],
           "duration": 1, "description": task.get("name") or part["name"]}
    if role:
        act["role"] = role
    return act


# ---------------------------------------------------------------- 값 읽기 · 인자 틀
def lookup(values: dict, path: str):
    """'work_order.after.window_starts_at' → 처리 건 값 안쪽. 없으면 KeyError(경로)."""
    head, *rest = path.split(".")
    if head not in values:
        raise KeyError(path)
    cur = values[head]
    for part in rest:
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            raise KeyError(path)
    return cur


def placeholders(value) -> list[str]:
    out = []
    if isinstance(value, str):
        out += PLACEHOLDER.findall(value)
    elif isinstance(value, dict):
        for v in value.values():
            out += placeholders(v)
    elif isinstance(value, list):
        for v in value:
            out += placeholders(v)
    return out


def render(value, values: dict):
    """인자 틀 → 실제 인자. 문자열 전체가 {이름} 하나면 그 값을 그대로(숫자 · 객체), 섞여 있으면 글자로 바꿔 넣는다.
    없는 값은 KeyError — 빈 메일을 보내지 않는다."""
    if isinstance(value, str):
        whole = PLACEHOLDER.fullmatch(value)
        if whole:
            return deepcopy(lookup(values, whole.group(1)))
        def text(m):
            v = lookup(values, m.group(1))
            return v if isinstance(v, str) else ("" if v is None else _text(v))
        return PLACEHOLDER.sub(text, value)
    if isinstance(value, dict):
        return {k: render(v, values) for k, v in value.items()}
    if isinstance(value, list):
        return [render(v, values) for v in value]
    return deepcopy(value)


def render_report(template: str | None, values: dict) -> str:
    """결과 보고 글: 없는 값은 '(없음)' — 보고는 값이 모자라도 나가야 한다(실패로 막지 않는다)."""
    def text(m):
        try:
            v = lookup(values, m.group(1))
        except KeyError:
            return "(없음)"
        return v if isinstance(v, str) else ("(없음)" if v is None else _text(v))
    return PLACEHOLDER.sub(text, template or "")


def test_run_verdict(criteria: dict, readings: dict) -> tuple[bool, list[dict]]:
    """시운전 판정: 기준마다 최신값이 기준 안인지. 값이 없으면 미달(모르는 것을 통과로 치지 않는다)."""
    rows, ok_all = [], True
    for tag, (op, limit) in criteria.items():
        v = readings.get(tag)
        ok = v is not None and {">=": v >= limit, ">": v > limit, "<=": v <= limit, "<": v < limit}[op]
        ok_all = ok_all and ok
        rows.append({"tag": tag, "op": op, "limit": limit, "value": v, "ok": ok})
    return ok_all, rows


def _text(v) -> str:
    import json
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)


# ---------------------------------------------------------------- 시간
def parse_time(value) -> datetime:
    if isinstance(value, datetime):
        t = value
    elif isinstance(value, str) and value.strip():
        t = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    else:
        raise ValueError(f"시각으로 읽을 수 없는 값입니다: {value!r}")
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def wait_plan(virtual_seconds: float, now: datetime, time_scale: float, *, label: str | None = None, source: str | None = None) -> dict:
    """가상(업무) 시간 → 실제 끝 시각. 음수(이미 지난 시각)는 0."""
    virtual = max(0.0, float(virtual_seconds))
    factor = max(1.0, float(time_scale)) * engine.wait_compression()
    real = virtual / factor
    return {"label": label, "source": source, "virtual_s": round(virtual, 1), "real_s": round(real, 1),
            "time_scale": max(1.0, float(time_scale)), "compression": engine.wait_compression(),
            "started_at": engine.now_iso(now), "due_at": engine.now_iso(now + timedelta(seconds=real))}


def wait_for(cfg: dict, values: dict, now: datetime, time_scale: float) -> dict:
    """시간 대기 부품의 계획: duration(ISO 업무 기간) 또는 until(처리 건 값의 시각, 지금부터의 업무 시간)."""
    if cfg.get("duration"):
        return wait_plan(engine.iso_duration_seconds(cfg["duration"]), now, time_scale, label=cfg.get("label"), source=cfg["duration"])
    raw = lookup(values, cfg["until"])
    if isinstance(raw, dict):
        raw = raw.get("starts_at") or raw.get("window_starts_at") or raw.get("expected_at")
    target = parse_time(raw)
    return wait_plan((target - now).total_seconds(), now, time_scale, label=cfg.get("label"), source=f"{cfg['until']} = {engine.now_iso(target)}")


def due(plan: dict, now: datetime) -> bool:
    return parse_time(plan["due_at"]) <= now


# ---------------------------------------------------------------- 발주 값 (승인 경로)
def purchase_action(option: dict) -> dict | None:
    """카드의 발주 동작(PR_CREATE, 값 = 공급사 id). 없으면 None."""
    return next((a for a in option.get("actions") or [] if a.get("code") == "PR_CREATE"), None)


def purchase_inputs(values: dict) -> tuple[str | None, int | None]:
    """발주할 부품 · 수량: 처리 건 값(part_no · need_qty — 에이전트 산정이나 시작 입력)이 먼저, 없으면 ERP 재고 경보의 근거."""
    evidence = ((values.get("alert") or {}).get("evidence") or {}) if isinstance(values.get("alert"), dict) else {}
    part = values.get("part_no") or evidence.get("part_no")
    qty = values.get("need_qty") if values.get("need_qty") is not None else evidence.get("need_qty")
    if isinstance(qty, str) and qty.strip().isdigit():
        qty = int(qty.strip())
    if isinstance(qty, float) and qty.is_integer():
        qty = int(qty)
    return (part if isinstance(part, str) and part else None,
            qty if isinstance(qty, int) and not isinstance(qty, bool) and qty > 0 else None)


def purchase_quote(option: dict, values: dict, quotes: list[dict]) -> dict | None:
    """승인한 카드의 발주 값을 확정한다. 카드에 발주가 없으면 None. 부품 · 수량 · 견적을 모르면 ValueError —
    금액을 모르는 채 승인하면 사람이 무엇을 승인했는지(얼마를 발주하는지) 기록이 없으므로 승인을 받지 않는다."""
    action = purchase_action(option)
    if action is None:
        return None
    supplier = action.get("value")
    part, qty = purchase_inputs(values)
    if not supplier or not part or qty is None:
        raise ValueError("발주 카드의 공급사 · 부품 · 수량을 확정할 수 없습니다 — 처리 건에 part_no · need_qty(또는 ERP 재고 경보 근거)가 있어야 "
                         "금액을 계산하고 금액 기준 승인 분기를 탈 수 있습니다")
    quote = next((q for q in quotes or [] if q.get("supplier") == supplier), None)
    if quote is None:
        raise ValueError(f"ERP 에 {part} 의 {supplier} 견적이 없어 발주 금액을 확정할 수 없습니다")
    price = quote["price"]
    amount = price * qty
    return {"approved_supplier": supplier, "approved_part_no": part, "approved_qty": qty, "approved_unit_price": price,
            "approved_amount": int(amount) if float(amount).is_integer() else amount,
            "quote": {"supplier": supplier, "name": quote.get("name"), "price": price, "lead_d": quote.get("lead_d"),
                      "avl": quote.get("avl"), "fail_rate": quote.get("fail_rate")}}
