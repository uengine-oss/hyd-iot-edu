"""V 통합 검증 — 학생이 포털 "직접 만들기"로 만든 구성으로 시나리오 4개(쿨러 · 펌프 · 팬/가림 · 작동유)를 끝까지 (HANDOFF A160 ⑤).

    .venv/bin/python scripts/probe_v_student_paths.py --expect worker --out .evidence/a160/v-worker     # AGENT_BRIDGE=off, 호스트 워커 1~2개
    .venv/bin/python scripts/probe_v_student_paths.py --expect legacy --out .evidence/a160/v-legacy     # AGENT_BRIDGE=legacy, 호스트 워커 정지
    ... --only cooler|pump|fan|oil|bundle   (쉼표로 여러 개 가능, 예 --only pump,fan)

브라우저 클릭 대신 **포털 화면 JS(it/portal/www/*.js)가 부르는 것과 같은 HTTP API를 같은 본문으로** 순서대로 부른다. 어느 화면의
어느 호출인지는 `docs/handoff/verification/2026-10-08/v-student-paths.md` 표에 파일:줄로 적었다.

학생 동선(DECISIONS §111 ④ · TODO B · V 행):
  0 준비     모드 확인(/api/process/mode) · 시작 상태 내보내기(/api/config/export) · 기준으로 되돌리기(/api/config/reset, --no-reset-start 로 끔)
  1 쿨러     B1 기본 진단 에이전트 복제 → 이름 바꿈 → 스킬 만들기 · 붙이기 → 역할 → 사람 · B2 MCP 서버 등록(잘못된 주소 거절 1건) ·
             B3 기준 흐름을 bpmn.io 로 다시 그린 그림 가져오기 → 매핑 → 사전 검사 → 등록 · B1 원인 진단 단계 → 내 에이전트 배정 ·
             B4 배포(경보 표: 쿨러 · 펌프 · 팬이 학생 판본) → 쿨러 열화(moderate) → 학생 흐름 처리 건 → 에이전트 4작업 → 승인 → PLC ACK →
             재관측 → 작업지시 → 종결
  2 펌프     같은 배포 흐름으로 펌프 누설 → (근거 부족이면) 보류 → 명시 재평가 → 카드 → 승인 → 종결
  3 팬/가림  B5 What-if 관점 중요도 · KPI 목표 바꿔 보기(원본 불변) · 에이전트에게 질문(worker) → 팬 정상 조치 완주 →
             가림(부하 70 % → 경보 해제 뒤 MITIGATION_FAILED → 상급자 확인)
  4 작동유   scripts/probe_b7_oil_live.py 의 run() 을 다른 흐름 id 로 그대로 부른다(그 파일은 고치지 않음)
  5 끝       B6 내보내기 → 기준으로 되돌리기 → 불러오기 → 내보낸 칸 비교 → 마지막 기준으로 되돌리기(--keep-config 로 끔)

모드 차이(코드 근거는 메모 "모드별 차이"): 단계 → 에이전트 배정은 두 모드 모두 작업 행 담당(user_id)과 실행 설정에 반영된다
(agent_authoring.apply_agent_map · agents_api run.steps). worker 모드는 그 담당의 프로필 · 스킬로 실제 워커가 실행하고
(agent-worker runner.run → agent_settings), legacy 모드는 내장 결정론 판단이 task 를 채운다(instance_mode._bridge_legacy_agent,
task_started 이름 "legacy agent"). 질문하기는 워커가 없으면 503 + 사유(ask.readiness) — legacy 에서는 그 거절을 검사한다.

증거: --out 에 단계별 JSON, checks.json, failures.json(단계 · 요청 · 응답 앞 300자), probe.log. 마지막 줄은
`ALL PASS — n/n checks` 또는 `k FAILED — m/n checks` (scripts/run_regression.py PASS_PATTERNS).
정답 하드코딩 없음: 1순위 카드는 판단의 사실과 순위 정책으로 다시 계산하고(scenario_instance_test.policy_top), 그림의 task id 는
등록된 정의의 bpmnImport.mapping.tasks(그림 id → 고른 부품)에서 읽는다.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
H = "http://127.0.0.1"
PLANT, DETECTOR, PROCESS, ENT, AGENT = f"{H}:8000", f"{H}:8092", f"{H}:8080", f"{H}:8095", f"{H}:8091"
REDRAW = ROOT / "tests/fixtures/bpmn/anomaly_response_redraw.bpmn"
BY = "[검사] 학생1"
STAGES = ("cooler", "pump", "fan", "oil", "bundle")
AGENT_PARTS = ("task:diagnose", "task:candidates", "task:compliance", "task:rank")
SENSOR_PATTERNS = ("COOLER_DEGRADATION", "PUMP_LEAKAGE", "FAN_VIBRATION")
# 그림의 조건 선 이름 → 학생이 매핑 표에 적는 조건 (tests/test_bpmn_import.py redraw_mapping 과 같은 선택)
FLOW_CONDITIONS = {"선택 스킬 kind == control": {"var": "chosen_skill_kind", "op": "==", "value": "control"},
                   "선택 스킬 kind == work_order": {"var": "chosen_skill_kind", "op": "==", "value": "work_order"},
                   "TS1 < 55 and 경보 해제": {"var": "recovered", "op": "==", "value": True},
                   "미회복": {"var": "recovered", "op": "!=", "value": True}}
SKILL_TEXT = """---
name: {name}
description: 경보 원인 진단 때 지식 경로와 실제 질의를 근거로 남기는 요령
---
# 경보 원인 진단 요령 (학생이 포털에서 만든 스킬)

1. 경보의 설비 · 패턴으로 지식 그래프에서 패턴 → 증상 → 고장 유형 → 원인 경로를 먼저 조회한다.
2. 원인을 고를 때는 실제로 실행한 질의와 그 결과를 근거로 함께 적는다.
3. 원천 값이 근거 규칙에 못 미치면 원인을 지어내지 않고 보류 사유를 적는다.
"""
ASK_QUESTION = "완제품 재고가 가장 적은 설비와 그 수량은?"     # 포털 질문하기 화면의 예시 문장(it/portal/www/ask.js threadHtml)
ASK_LIVE = {"waiting", "running", "submitted", "correcting", "asking"}   # ask.js LIVE

results: list[dict] = []
failures: list[dict] = []
LAST: dict = {}
OUT: Path | None = None
STAGE = {"key": "0", "title": "준비"}


class Abort(Exception):
    """이후 단계가 의존하는 검사가 실패 — 이 단계(또는 전체)를 멈춘다."""


class HttpFail(Exception):
    pass


# ---------------------------------------------------------------- 기록
def _short(v, n=300):
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str)
    return s if len(s) <= n else s[:n] + "…"


def section(key: str, title: str) -> None:
    STAGE.update(key=key, title=title)
    print(f"\n== {title}", flush=True)


def check(name: str, ok, detail="") -> bool:
    ok = bool(ok)
    d = detail if isinstance(detail, str) else json.dumps(detail, ensure_ascii=False, default=str)
    results.append({"stage": STAGE["title"], "name": name, "passed": ok, "detail": d[:1500]})
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}  {d[:400]}", flush=True)
    if not ok:
        failures.append({"stage": STAGE["title"], "check": name, "detail": d[:1500],
                         "request": {k: LAST.get(k) for k in ("method", "url", "body")},
                         "response": {"status": LAST.get("status"), "head": LAST.get("response")}})
    return ok


def require(name: str, ok, detail="") -> None:
    if not check(name, ok, detail):
        raise Abort(name)


def info(name: str, detail="") -> None:
    """기록만 하는 갈래(예: 보류가 나지 않음) — 통과로 센다(검사 실패가 아니라 관찰)."""
    check(f"(기록) {name}", True, detail)


def save(name: str, value) -> None:
    if OUT is None:
        return
    path = OUT / f"{STAGE['key']}-{name}.json"
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


# ---------------------------------------------------------------- HTTP (포털 JS 와 같은 JSON 요청)
def call(method: str, url: str, data=None, timeout: float = 60):
    body = None if data is None else json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method=method)
    LAST.clear()
    LAST.update(method=method, url=url, body=None if data is None else _short(data))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            code, raw = r.status, r.read()
    except urllib.error.HTTPError as e:
        code, raw = e.code, e.read()
    text = raw.decode("utf-8", "replace")
    try:
        parsed = json.loads(text) if text and text[:1] in "{[" else text
    except ValueError:
        parsed = text
    LAST.update(status=code, response=text[:300])
    return code, parsed


def get(url: str, timeout: float = 30):
    code, body = call("GET", url, timeout=timeout)
    if code != 200:
        raise HttpFail(f"GET {url} → {code} {str(body)[:300]}")
    return body


def post(url: str, data=None, timeout: float = 60):
    """scenario_*_test.py 의 post 와 같은 모양: 실패면 {'error': 코드, 'body': 앞 300자}."""
    code, body = call("POST", url, data or {}, timeout=timeout)
    if code >= 400:
        return {"error": code, "body": str(body)[:300] if not isinstance(body, dict) else json.dumps(body, ensure_ascii=False)[:300]}
    return body if isinstance(body, dict) else {"body": body}


def wait_for(fn, timeout: float, every: float = 1.5):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            v = fn()
            if v:
                return v, time.time() - t0
        except (HttpFail, urllib.error.URLError, OSError, KeyError, ValueError):
            pass
        time.sleep(every)
    return None, time.time() - t0


def worker_health():
    for port in (8097, 8098):
        try:
            with urllib.request.urlopen(f"{H}:{port}/health", timeout=3) as r:
                return port, json.loads(r.read())
        except Exception:  # noqa: BLE001
            continue
    return None, None


# ---------------------------------------------------------------- 처리 건 읽기
def variables(inst: dict) -> dict:
    return {v["key"]: v.get("value") for v in (inst.get("variables_data") or [])}


def view(pid: str) -> dict:
    return get(f"{PROCESS}/api/instances/{pid}")


def by_activity(v: dict) -> dict:
    """activity_id → 마지막 작업 행(같은 단계가 다시 열리면 나중 것)."""
    out = {}
    for w in v["workitems"]:
        out[w["activity_id"]] = w
    return out


def instance_for(alert_id: str):
    for inst in get(f"{PROCESS}/api/instances?limit=40"):
        if variables(inst).get("alert_id") == alert_id:
            return inst
    return None


def incident(inc_id: str) -> dict:
    return get(f"{PROCESS}/api/incidents/{inc_id}")


def pattern_state(asset: str, pattern: str) -> dict:
    return (get(f"{DETECTOR}/api/detector/state")["assets"].get(asset, {}).get("patterns") or {}).get(pattern) or {}


def tags(asset: str) -> dict:
    return get(f"{PLANT}/api/state")["units"][asset]


def reobservation(inc_id: str) -> dict:
    audits = [a for a in get(f"{PROCESS}/api/audit") if a.get("incident") == inc_id and a.get("event") == "REOBSERVATION"]
    return (audits[0] if audits else {}).get("detail") or {}


# ---------------------------------------------------------------- 학생 구성(B3 매핑 · 등록 정의에서 읽는 칸)
def student_mapping(imp: dict, catalog: dict) -> tuple[dict, list[str]]:
    """포털 흐름 매핑 표에서 학생이 하는 것: 그림의 task 이름을 보고 같은 이름의 시나리오 부품을 고르고, 조건 선에 조건을 적는다.
    시작 조건 · 칸(역할)은 merge_mapping 기본값 그대로(메시지 시작 → 감지기 경보 패턴 전부, 칸 이름 = 역할 이름).
    돌려주는 두 번째 값은 고르지 못한 그림 요소(이름이 부품과 다른 task · 조건을 모르는 선)."""
    m = deepcopy(imp["mapping"])
    parts = {p["name"]: p["key"] for p in catalog.get("parts") or [] if p.get("group") == "scenario"}
    missing = []
    for t in imp["parsed"]["tasks"]:
        if t["id"] in m["tasks"] and (m["tasks"][t["id"]] or {}).get("part"):
            continue                                            # 다시 가져오기: 앞선 선택 유지(merge_mapping)
        if t.get("name") in parts:
            m["tasks"][t["id"]] = {"part": parts[t["name"]]}
        else:
            missing.append(f"task {t['id']}({t.get('name')})")
    for f in imp["parsed"]["flows"]:
        if f.get("name") in FLOW_CONDITIONS and f["id"] not in m["flows"]:
            m["flows"][f["id"]] = dict(FLOW_CONDITIONS[f["name"]])
        elif f.get("name") and f["id"] not in m["flows"]:
            missing.append(f"선 {f['id']}({f['name']})")
    return m, missing


def flow_ids(definition: dict) -> dict:
    """등록된 학생 정의에서 부품 → 그림 id, 경계 타이머, 끝 이벤트(작업지시 뒤 = 종결, 상급자 호출 뒤 = 에스컬레이션)."""
    tasks = ((definition.get("bpmnImport") or {}).get("mapping") or {}).get("tasks") or {}
    act = {}
    for drawn, spec in tasks.items():
        part = (spec or {}).get("part")
        if part and part not in act:
            act[part] = drawn
    ends = {e["id"] for e in definition.get("events") or [] if e.get("type") == "endEvent"}
    after = {}
    for s in definition.get("sequences") or []:
        if s.get("target") in ends:
            after[s.get("source")] = s["target"]
    timer = next((e["id"] for e in definition.get("events") or []
                  if e.get("type") == "boundaryEvent" and e.get("attachedTo") == act.get("task:select")), None)
    return {"act": act, "timer": timer, "end_closed": after.get(act.get("task:work-order")),
            "end_escalated": after.get(act.get("task:escalate"))}


def comparable(content: dict) -> dict:
    """B6 대조: config_bundle._comparable 과 같은 칸을 뺀다(출처 표시 · 사람이 읽을 이름 · 배포 패턴 목록)."""
    c = deepcopy(content or {})
    for s in c.get("mcp_servers") or []:
        s.pop("origin", None)
        s.pop("secrets", None)
    for m in c.get("role_members") or []:
        m.pop("role_name", None)
        m.pop("user_name", None)
    for d in (c.get("deployments") or {}).get("flows") or []:
        d.pop("patterns", None)
    return c


def diff_paths(a, b, path="") -> list[str]:
    if type(a) is not type(b):
        return [path or "(전체)"]
    if isinstance(a, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(f"{path}.{k}".lstrip("."))
            else:
                out += diff_paths(a[k], b[k], f"{path}.{k}")
        return out
    if isinstance(a, list):
        if len(a) != len(b):
            return [f"{path} (개수 {len(a)} ≠ {len(b)})".lstrip(".")]
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += diff_paths(x, y, f"{path}[{i}]")
        return out
    return [] if a == b else [path.lstrip(".")]


def flip_target(m: dict):
    """KPI 목표 바꿔 보기: 지금 판정(달성/미달)을 뒤집는 시험 목표. UP 지표는 실적 ≥ 목표가 달성, DOWN 은 실적 ≤ 목표."""
    value, direction, status = m.get("value"), (m.get("direction") or "UP"), m.get("status")
    if not isinstance(value, (int, float)) or status not in ("met", "missed"):
        return None
    span = abs(value) + 1.0
    if direction == "DOWN":
        return round(value + span, 2) if status == "missed" else round(value - span, 2)
    return round(value - span, 2) if status == "missed" else round(value + span, 2)


# ---------------------------------------------------------------- 실행 맥락
class Ctx:
    def __init__(self, args):
        self.args = args
        self.expect = args.expect
        self.worker = args.expect == "worker"
        self.agent_wait = 900 if self.worker else 150
        self.clock = 1.0
        self.agent_id = None
        self.agent_name = None
        self.skill = None
        self.mcp_name = None
        self.def_id = args.def_id
        self.version = None
        self.ids = None
        self.setup_failed = False
        self.started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- 0 준비
def stage_prepare(ctx: Ctx, reset_start: bool) -> None:
    section("0", "0. 준비 — 모드 · 서비스 · 시작 상태")
    mode = get(f"{PROCESS}/api/process/mode")
    save("mode", mode)
    ctx.clock = 20.0 / max(float(mode.get("time_scale") or 20.0), 1.0)
    require("process 가 instance 모드", mode.get("mode") == "instance", mode)
    want = "off" if ctx.worker else "legacy"
    require(f"AGENT_BRIDGE={want} (--expect {ctx.expect})", mode.get("agent_bridge") == want, mode)
    check("배속 TIME_SCALE=20 (CLAUDE.md §3)", float(mode.get("time_scale") or 0) == 20.0, f"time_scale={mode.get('time_scale')}")
    port, wh = worker_health()
    if ctx.worker:
        require("호스트 워커 응답(실제 Claude Code 워커)", wh is not None and wh.get("status") in ("ok", "starting"), f"port={port} {wh}")
    else:
        require("호스트 워커 정지(내장 판단의 에이전트 작업을 가져가지 않게)", wh is None, f"port={port}")
    h = get(f"{PROCESS}/healthz")
    check("process 정상 · Supabase 연결", h.get("ok") and h.get("supabase") is True, {k: h.get(k) for k in ("ok", "mode", "supabase")})
    start = get(f"{PROCESS}/api/config/export")
    save("start-export", start)
    check("시작 상태 내보내기(/api/config/export)", start.get("format") == "hyd-config-bundle", start.get("summary"))
    if reset_start:
        code, r = call("POST", f"{PROCESS}/api/config/reset", {"by": BY}, timeout=120)
        save("start-reset", r)
        require("시작 전 기준으로 되돌리기(학생 구성 정리 — 열린 처리 건이 있으면 사유와 함께 멈춤)", code == 200,
                f"{code} {_short(r)}")


# ---------------------------------------------------------------- 1 쿨러 따라하기: B1 · B2 · B3 · B4
def setup_student(ctx: Ctx) -> None:
    a = ctx.args
    section("1", "1. 쿨러 따라하기 — B1 내 에이전트 · 스킬 · 업무분장")
    opts = get(f"{PROCESS}/api/agent-authoring/options")
    save("b1-options", opts)
    agents = get(f"{PROCESS}/api/agents")
    base = next((x for x in agents if x["id"] == "sys:agent"), None)
    require("기본 진단 에이전트(sys:agent) 보호 표시(origin=seed, 고칠 수 없음)", base and base.get("origin") == "seed" and not base.get("editable"),
            base)
    base_run = get(f"{PROCESS}/api/agents/sys:agent")["run"]
    save("b1-base-run-before", base_run)
    code, r = call("PUT", f"{PROCESS}/api/agents/sys:agent", {"name": base["name"], "goal": base.get("goal") or "목표", "by": BY})
    check("기본 에이전트 고치기 거절(403 + '복제해서 고치기' 안내)", code == 403 and "복제" in json.dumps(r, ensure_ascii=False), f"{code} {_short(r)}")
    code, clone = call("POST", f"{PROCESS}/api/agents/sys:agent/clone", {})      # agents.js cloneAgent
    save("b1-clone", clone)
    require("기본 진단 에이전트 복제(사본 origin=user)", code == 201 and str(clone.get("id", "")).startswith("agent:u-") and clone.get("origin") == "user",
            f"{code} {_short(clone)}")
    ctx.agent_id = clone["id"]
    card = get(f"{PROCESS}/api/agents/{ctx.agent_id}")
    body = {"name": a.agent_name, "role": clone.get("role") or "", "goal": clone.get("goal") or card.get("goal") or "",
            "persona": clone.get("persona") or "", "model": clone.get("model") or "",
            "tools": [t["name"] for t in card.get("tools") or []], "skills": [s["skill_name"] for s in card.get("skills") or []]}
    code, r = call("PUT", f"{PROCESS}/api/agents/{ctx.agent_id}", body)        # agents.js submitForm (PUT)
    if code == 409:                                                             # 같은 이름이 남아 있으면(--no-reset-start) 시각을 붙인다
        body["name"] = f"{a.agent_name} {datetime.now().strftime('%H%M%S')}"
        code, r = call("PUT", f"{PROCESS}/api/agents/{ctx.agent_id}", body)
    save("b1-rename", r)
    require("사본 이름 바꾸기(PUT /api/agents/{id})", code == 200 and r.get("username") == body["name"], f"{code} {_short(r)}")
    ctx.agent_name = body["name"]
    skill = a.skill_name
    code, r = call("POST", f"{PROCESS}/api/skills", {"skill_name": skill, "description": "", "content": SKILL_TEXT.format(name=skill)})
    if code == 409:
        skill = f"{a.skill_name}-{datetime.now().strftime('%H%M%S')}"
        code, r = call("POST", f"{PROCESS}/api/skills", {"skill_name": skill, "description": "", "content": SKILL_TEXT.format(name=skill)})
    save("b1-skill", r)
    require("스킬 만들기(SKILL.md, origin=user)", code == 201 and r.get("skill_name") == skill, f"{code} {_short(r)}")
    ctx.skill = skill
    code, r = call("POST", f"{PROCESS}/api/agents/{ctx.agent_id}/skills", {"skill_name": skill})     # agents.js 스킬 상세 '붙이기'
    require("내 에이전트에 스킬 붙이기", code == 200 and skill in (r.get("skills") or []), f"{code} {_short(r)}")
    code, r = call("POST", f"{PROCESS}/api/role-members", {"role_id": a.role_id, "user_id": a.role_user})   # agents.js 업무분장
    save("b1-role-member", r)
    check(f"역할 → 사람 배정({a.role_id} ← {a.role_user})", code == 201 and a.role_user in (r.get("members") or []), f"{code} {_short(r)}")

    section("1", "1. 쿨러 따라하기 — B2 MCP 서버 등록 · 연결 검사")
    code, bad = call("POST", f"{PROCESS}/api/mcp/servers", {"name": "my-bad-server", "transport": "streamable_http",
                                                             "url": a.bad_mcp_url, "description": "[검사] 잘못된 주소", "timeout": 4, "by": BY})
    save("b2-bad", bad)
    check("잘못된 주소는 사유와 함께 거절(422 · 연결 검사 실패)", code == 422 and "연결 검사 실패" in json.dumps(bad, ensure_ascii=False), f"{code} {_short(bad)}")
    listed = get(f"{PROCESS}/api/mcp/servers")
    check("거절된 서버는 등록되지 않음", "my-bad-server" not in {s["name"] for s in listed.get("servers") or []}, [s["name"] for s in listed.get("servers") or []])
    name = a.mcp_name
    body = {"name": name, "transport": "streamable_http", "url": a.mcp_url, "description": "[검사] 학생이 등록한 판단 도구 서버", "timeout": 8, "by": BY}
    code, r = call("POST", f"{PROCESS}/api/mcp/servers", body, timeout=60)            # mcp.js submitForm(검사 후 등록)
    if code == 409:
        name = body["name"] = f"{a.mcp_name}-{datetime.now().strftime('%H%M%S')}"
        code, r = call("POST", f"{PROCESS}/api/mcp/servers", body, timeout=60)
    save("b2-register", r)
    ok = code == 201 and (r.get("check") or {}).get("status") == "ok"
    check(f"정상 서버 등록 = 연결 검사 통과 · 도구 목록({a.mcp_url})", ok and (r.get("check") or {}).get("tools"),
          f"{code} tools={len((r.get('check') or {}).get('tools') or [])} {_short(r)}")
    if ok:
        ctx.mcp_name = name
        code, rc = call("POST", f"{PROCESS}/api/mcp/servers/{name}/check", {"timeout": 8, "by": BY}, timeout=60)   # mcp.js '연결 검사'
        check("등록한 서버 다시 연결 검사", code == 200 and (rc.get("check") or {}).get("status") == "ok", f"{code} {_short(rc)}")
        sel = get(f"{PROCESS}/api/mcp/selectable")
        save("b2-selectable", sel)
        mine = next((s for s in sel.get("servers") or [] if s["name"] == name), {})
        writes = [t for t in mine.get("tools") or [] if not t.get("read_only")]
        check("검사 통과 서버는 에이전트 도구로 고를 수 있음(읽기 표시 도구)", mine.get("selectable") and any(t.get("selectable") for t in mine.get("tools") or []),
              {k: mine.get(k) for k in ("selectable", "reason")})
        check("쓰기 도구는 고를 수 없음(사유와 함께)", all(not t.get("selectable") and t.get("reason") for t in writes),
              [(t["name"], t.get("selectable"), (t.get("reason") or "")[:60]) for t in writes] or "쓰기 도구 없음")
    after_run = get(f"{PROCESS}/api/agents/sys:agent")["run"]
    save("b1-base-run-after", after_run)
    check("내 에이전트 · 스킬 · MCP 를 만들어도 기본 에이전트 실행 설정 불변", after_run.get("instructions") == base_run.get("instructions")
          and after_run.get("settings") == base_run.get("settings"), {"before": base_run.get("settings"), "after": after_run.get("settings")})

    section("1", "1. 쿨러 따라하기 — B3 bpmn.io 그림 가져오기 · 매핑 · 사전 검사 · 등록")
    cat = get(f"{PROCESS}/api/flows/catalog")
    save("b3-catalog", cat)
    code, imp = call("POST", f"{PROCESS}/api/flows/import", {"xml": REDRAW.read_text(encoding="utf-8"), "file_name": REDRAW.name,
                                                              "definition_id": ctx.def_id}, timeout=60)   # flows.js 가져오기
    save("b3-import", imp)
    require(f"그림 가져오기(.bpmn → 흐름 id {ctx.def_id})", code == 200 and isinstance(imp, dict) and imp.get("mapping") and imp.get("parsed"),
            f"{code} {_short(imp)}")
    report = imp.get("reimport") or {}
    if report.get("previous"):
        info("같은 흐름 id 를 다시 가져옴 — 앞선 매핑 유지(merge_mapping)", {k: report.get(k) for k in ("kept", "dropped", "new")})
    else:
        problems = (imp.get("check") or {}).get("problems") or []
        check("가져온 직후 사전 검사는 부품을 고르기 전이라 통과하지 않음(칸 위치와 사유)",
              not (imp.get("check") or {}).get("ok") and problems and all(p.get("where") and p.get("reason") for p in problems),
              [(p.get("where", {}).get("id"), p.get("reason", "")[:50]) for p in problems[:5]])
    mapping, missing = student_mapping(imp, cat)
    check("그림의 task · 조건 선을 모두 부품 · 조건으로 고름", not missing, missing)
    code, put = call("PUT", f"{PROCESS}/api/flows/{ctx.def_id}/mapping", {"mapping": mapping})      # flows.js 매핑 저장
    save("b3-mapping", put)
    problems = ((put or {}).get("check") or {}).get("problems") if isinstance(put, dict) else put
    require("매핑 저장 → 사전 검사 통과(값 연결 · 설비 명령 앞 사람 승인 · 끝 닫힘)", code == 200 and put["check"].get("ok"),
            f"{code} {_short(problems)}")
    code, reg = call("POST", f"{PROCESS}/api/flows/{ctx.def_id}/register", {"mapping": mapping})   # flows.js 판본 등록
    save("b3-register", reg)
    require("판본 등록(origin=user, 배포 전)", code == 201 and reg.get("version") and reg.get("deployed") is False, f"{code} {_short(reg)}")
    ctx.version = reg["version"]
    ctx.ids = flow_ids(reg["definition"])
    act = ctx.ids["act"]
    require("등록된 정의에서 부품 → 그림 id 를 읽음(9부품 · 끝 2개)",
            all(p in act for p in AGENT_PARTS + ("task:select", "task:command", "task:reobserve", "task:work-order", "task:escalate"))
            and ctx.ids["end_closed"] and ctx.ids["end_escalated"], ctx.ids)
    tools = {x["id"]: x.get("tool") for x in reg["definition"]["activities"]}
    check("설비 명령 부품 앞에 사람 승인(조치 카드 선택) — 그림 id 로", tools.get(act["task:command"]) == "incident:command"
          and tools.get(act["task:select"]) == "formHandler:select_card", {k: tools.get(v) for k, v in act.items()})
    code, bpmn = call("GET", f"{PROCESS}/api/flows/{ctx.def_id}/versions/{ctx.version}/bpmn")
    check("그림 다시 받기 = 가져온 원본 그대로(proc_def.bpmn)", code == 200 and bpmn == REDRAW.read_text(encoding="utf-8"), f"{code} {len(str(bpmn))}자")

    section("1", "1. 쿨러 따라하기 — B1 원인 진단 단계 → 내 에이전트 배정")
    diag = act["task:diagnose"]
    board = get(f"{PROCESS}/api/agent-assignments")
    step = next((s for s in board.get("steps") or [] if s["definition_id"] == ctx.def_id and s["activity_id"] == diag), None)
    check("배정 표에 내 흐름의 원인 진단 단계(기본 담당 sys:agent)", step and "sys:agent" in (step.get("default_agents") or []), step)
    code, r = call("PUT", f"{PROCESS}/api/agent-assignments", {"definition_id": ctx.def_id, "activity_id": diag, "agent_id": ctx.agent_id})
    require("원인 진단 → 내 에이전트 배정", code == 200 and r.get("agent_id") == ctx.agent_id, f"{code} {_short(r)}")
    board = get(f"{PROCESS}/api/agent-assignments")
    save("b1-board", board)
    if ctx.worker:
        check("배정 표: 워커 경로라 내장 경로 안내 없음", board.get("agent_bridge") == "off" and not board.get("bridge_note"), board.get("agent_bridge"))
    else:
        check("배정 표: legacy 안내('판단은 내장 경로' — 배정은 담당 기록 · 표시만)", board.get("agent_bridge") == "legacy" and board.get("bridge_note"),
              _short(board.get("bridge_note")))
    card = get(f"{PROCESS}/api/agents/{ctx.agent_id}")
    save("b1-agent-card", card)
    run_step = next((s for s in (card.get("run") or {}).get("steps") or [] if s["definition_id"] == ctx.def_id and s["activity_id"] == diag), None)
    settings = (run_step or {}).get("settings") or {}
    check("실행 설정(워커가 쓰는 agent_settings)에 배정 · 붙인 스킬 반영", run_step and settings.get("id") == ctx.agent_id
          and ctx.skill in (settings.get("skills") or []), settings)

    section("1", "1. 쿨러 따라하기 — B4 배포 · 경보 표 · 기준과 비교")
    code, dep = call("POST", f"{PROCESS}/api/process/definitions/{ctx.def_id}/deploy",
                     {"version": ctx.version, "by": BY, "reason": "[검사] 학생 흐름 배포"})      # definitionDeploy.js '이 판본 배포'
    save("b4-deploy", dep)
    require(f"판본 {ctx.version} 배포", code == 200, f"{code} {_short(dep)}")
    routes = get(f"{PROCESS}/api/flows/deployments")
    save("b4-routes", routes)
    rows = {r["pattern"]: r for r in routes.get("routes") or []}
    check("경보 표: 쿨러 · 펌프 · 팬 경보가 학생 판본으로 열림",
          all(rows.get(p, {}).get("definition") == ctx.def_id and str(rows.get(p, {}).get("version")) == str(ctx.version) for p in SENSOR_PATTERNS),
          {p: (rows.get(p, {}).get("definition"), rows.get(p, {}).get("version"), rows.get(p, {}).get("source")) for p in SENSOR_PATTERNS})
    cmp_ = get(f"{PROCESS}/api/flows/deploy-compare?definition={ctx.def_id}&version={ctx.version}")
    save("b4-compare", cmp_)
    counts = cmp_.get("counts") or {}
    check("기준과 비교: 단계 · 연결 추가 0 · 삭제 0(다시 그린 같은 흐름)", counts.get("추가") == 0 and counts.get("삭제") == 0, cmp_.get("summary"))


def load_existing(ctx: Ctx) -> bool:
    """--only pump|fan|bundle 단독: 앞 실행이 남긴 학생 구성(배포된 학생 흐름 · 원인 진단 배정)을 그대로 쓴다. 없으면 False."""
    routes = get(f"{PROCESS}/api/flows/deployments")
    row = next((r for r in routes.get("routes") or [] if r["pattern"] == "COOLER_DEGRADATION"), {})
    if row.get("definition") != ctx.def_id or row.get("source") != "내가 배포한 흐름":
        return False
    raw = get(f"{PROCESS}/api/process/definitions/{ctx.def_id}?version={row['version']}")
    ids = flow_ids(raw)
    board = get(f"{PROCESS}/api/agent-assignments")
    step = next((s for s in board.get("steps") or [] if s["definition_id"] == ctx.def_id and s["activity_id"] == ids["act"].get("task:diagnose")), None)
    if not step or not step.get("assigned"):
        return False
    ctx.version, ctx.ids = str(row["version"]), ids
    ctx.agent_id, ctx.agent_name = step["assigned"]["agent_id"], step["assigned"]["name"]
    info("앞 실행의 학생 구성을 그대로 씀(배포된 학생 흐름 · 원인 진단 배정)", {"definition": ctx.def_id, "version": ctx.version, "agent": ctx.agent_id})
    return True


def do_setup(ctx: Ctx) -> None:
    """B1~B4 준비. 실패하면 뒤 단계가 같은 준비를 되풀이하지 않게 표시한다(좌표는 처음 실패에 남음)."""
    if ctx.setup_failed:
        raise Abort("학생 구성 준비가 앞에서 실패함 — 그 좌표를 보세요")
    try:
        setup_student(ctx)
    except Exception:
        ctx.setup_failed = True
        raise


def ensure_setup(ctx: Ctx) -> None:
    if ctx.ids:
        return
    if ctx.setup_failed:
        raise Abort("학생 구성 준비가 앞에서 실패함 — 그 좌표를 보세요")
    if not load_existing(ctx):
        do_setup(ctx)


# ---------------------------------------------------------------- 흐름 공통(그림 id 기준)
def A(ctx: Ctx, part: str) -> str:
    return ctx.ids["act"][part]


def check_performer(ctx: Ctx, v: dict, label: str) -> None:
    """원인 진단 작업 행의 담당 = 내 에이전트(배정 → 작업 행 user_id), 실행 주체는 모드별."""
    diag = by_activity(v).get(A(ctx, "task:diagnose")) or {}
    via = [x for x in diag.get("assignees") or [] if isinstance(x, dict) and x.get("resolution") == "agent-map"]
    check(f"{label}: 원인 진단 담당 = 내 에이전트(단계 배정이 작업 행에 반영)", diag.get("user_id") == ctx.agent_id and via,
          {"user_id": diag.get("user_id"), "assignees": diag.get("assignees")})
    started = [e for e in v.get("events") or [] if e.get("todo_id") == diag.get("id") and e.get("event_type") == "task_started"]
    text = json.dumps(started, ensure_ascii=False)
    if ctx.worker:
        tools = [e for e in v.get("events") or [] if e.get("todo_id") == diag.get("id") and str(e.get("event_type", "")).startswith("tool_usage")]
        check(f"{label}: 원인 진단은 실제 워커가 실행(task_started 가 내장 경로가 아님 · 도구 호출 이벤트)",
              started and "legacy agent" not in text and tools, f"task_started {len(started)} · tool_usage {len(tools)}")
    else:
        check(f"{label}: 원인 진단은 내장 결정론 판단이 채움(task_started 'legacy agent')", started and "legacy agent" in text, f"task_started {len(started)}")


def wait_selection(ctx: Ctx, pid: str, alert_id: str, injected_at: float, *, reassess: bool = True, abort=None):
    """에이전트 4작업 → 조치 카드 선택 열림. 원인 진단이 보류(PENDING + _deferral)되면 새 2분 원천 창 뒤 명시 재평가(사람 요청)를
    한 번 보낸다(scenario_pump_fan_test.run_to_selection --reassess-held · run_scenario_pump_fan_evidence 와 같은 계약).
    돌려줌: (작업 표, 걸린 시간, 멈춘 사유, 보류 기록)"""
    sel, held_part = A(ctx, "task:select"), A(ctx, "task:diagnose")
    stopped: dict = {}
    seen_runs: set = set()

    def selected_or_stopped():
        cur = by_activity(view(pid))
        if cur.get(sel, {}).get("status") == "IN_PROGRESS":
            return cur
        why = abort(cur) if abort else None
        if why:                     # 물리 창이 닫힘(트립 · 경보 해제 · 조치 전 종료) — 시간 초과까지 기다리지 않는다
            stopped.update(reason=why)
            return cur
        pending = [w["activity_id"] for w in cur.values() if w["status"] == "PENDING"]
        if pending:
            stopped.update(reason="task pending", tasks=pending)
            return cur
        if not ctx.worker:          # 내장 판단 실행 기록이 실패로 끝났으면 기다리지 않는다(WITHHELD 는 곧 보류 task 가 된다)
            runs = [x for x in get(f"{AGENT}/api/agent/runs") if x.get("alertId") == alert_id and x.get("id") not in seen_runs]
            latest = max(runs, key=lambda x: x.get("started") or "", default=None)
            if latest and latest["status"] in {"FAILED", "REJECTED_BY_GUARDRAIL"}:
                stopped.update(run=latest["id"], status=latest["status"], reason=latest.get("error"))
                return cur
        return None

    tl, dt = wait_for(selected_or_stopped, ctx.agent_wait)
    held = (tl or {}).get(held_part) or {}
    hold = None
    if reassess and held.get("status") == "PENDING":
        receipt = (held.get("draft") or {}).get("_deferral") or {}
        assessment = receipt.get("assessment") or {}
        inc_id = variables(view(pid)["instance"]).get("incident")
        hold = {"held": True, "assessment": assessment}
        if not check("근거 부족 → 원인 진단 보류(UNSUPPORTED/UNKNOWN · 사유) · PLC 명령 없음 · 판단 없음",
                     assessment.get("status") in {"UNKNOWN", "UNSUPPORTED"} and assessment.get("reason")
                     and incident(inc_id).get("cmdId") is None and not variables(view(pid)["instance"]).get("decision_id"),
                     _short(assessment, 800)):
            return None, dt, "held without a readable assessment", hold
        remaining = max(0.0, 125 - (time.monotonic() - injected_at))
        print(f"  새 2분 원천 창을 위해 {remaining:.0f}초 기다린 뒤 명시 재평가", flush=True)
        time.sleep(remaining)
        if not ctx.worker:
            seen_runs.update(x.get("id") for x in get(f"{AGENT}/api/agent/runs") if x.get("alertId") == alert_id)
        request = {"deferral_id": receipt.get("id"), "request_id": "v-" + uuid.uuid4().hex, "by": "이생산",
                   "reason": "[검사] 고장 주입 뒤 2분 원천 창을 새로 관측했으므로 재평가를 요청한다"}
        response = post(f"{PROCESS}/api/todolist/{held['id']}/reassess", request)       # taskDeferral.js 재평가 요청
        hold.update(request=request, response=response)
        if not check("명시 재평가 접수(사람의 요청 — 승인 아님)", not response.get("error"), _short(response)):
            return None, dt, "reassessment refused", hold
        stopped.clear()
        tl, dt2 = wait_for(selected_or_stopped, ctx.agent_wait)
        dt += dt2
    return tl, dt, (stopped or None), hold


def select_with_review(sel: dict, dec: dict, option: str, by: str, role: str, reason: str, inc_id: str) -> dict:
    """instances.js previewCard → selectCard: 현재 원천 검토(decision-preview) 뒤 그 검토 id 로 승인."""
    review = post(f"{PROCESS}/api/todolist/{sel['id']}/decision-preview", {"decision": dec["id"], "option": option, "parameters": {}}, timeout=60)
    first = (review.get("snapshot", {}).get("options") or [{}])[0]
    if not check("승인 전 현재 원천 검토(선택한 카드가 지금도 가능)", review.get("id") and first.get("feasible") is True,
                 _short({"review": review.get("id"), "feasible": first.get("feasible"), "violations": first.get("violations"), "body": review.get("body")})):
        return {"error": 409, "body": "review unavailable/infeasible"}
    check("검토는 PLC 명령을 내지 않음", incident(inc_id).get("cmdId") is None)
    return post(f"{PROCESS}/api/todolist/{sel['id']}/select",
                dict(decision=dec["id"], option=option, review_id=review["id"], by=by, role=role, reason=reason), timeout=60)


def finish(ctx: Ctx, pid: str, inc_id: str, expect_end: str, timeout: float = 360):
    esc_ = A(ctx, "task:escalate")

    def terminal_or_review():
        cur = view(pid)
        if cur["instance"]["status"] == "COMPLETED":
            return cur
        if expect_end == ctx.ids["end_closed"] and by_activity(cur).get(esc_, {}).get("status") == "IN_PROGRESS":
            return cur          # 사람 검토로 간 실패 가지 — 조용히 다 기다리지 않는다
        return None
    fin, dt = wait_for(terminal_or_review, timeout)
    ok = fin is not None and fin["instance"]["status"] == "COMPLETED" and fin["instance"].get("end_event") == expect_end
    check(f"처리 건 COMPLETED · 끝 {expect_end}", ok, f"{dt:.0f}s end_event={fin and fin['instance'].get('end_event')} "
          f"incident={incident(inc_id).get('state')}")
    return fin if ok else None


def open_instance(ctx: Ctx, asset: str, fault: str, pattern: str, raise_timeout: float, *, severity: str | None = None, top_level=False):
    """고장 주입 → 감지 RAISE → 학생 흐름의 처리 건. 돌려줌 (pid, inc_id, alert_id, injected_at) 또는 None."""
    injected_at = time.monotonic()
    body = {"asset": asset, "type": fault}
    if severity:
        body["severity"] = severity
    r = post(f"{PLANT}/api/fault", body)
    check(f"{asset} {fault} 주입" + (f" ({severity})" if severity else ""), r.get("kind") == fault, _short(r))

    def raised():
        if top_level:     # 쿨러는 감지기의 기본 CEP 상태(scenario_instance_test 와 같음)
            d = get(f"{DETECTOR}/api/detector/state")["assets"].get(asset, {})
            return d if d.get("phase") == "RAISED" else None
        st = pattern_state(asset, pattern)
        return st if st.get("phase") == "RAISED" else None
    st, dt = wait_for(raised, raise_timeout)
    if not check(f"감지기 RAISED {pattern}", st is not None, f"{dt:.0f}s"):
        return None
    alert_id = st["alert_id"]
    inst, dt = wait_for(lambda: instance_for(alert_id), 30)
    if not check("경보가 학생 흐름의 처리 건을 엶(배포된 판본)", inst is not None and inst.get("proc_def_id") == ctx.def_id
                 and str(inst.get("proc_def_version")) == str(ctx.version) and inst.get("status") == "RUNNING",
                 {"alert": alert_id, "proc_def_id": (inst or {}).get("proc_def_id"), "version": (inst or {}).get("proc_def_version"),
                  "status": (inst or {}).get("status"), "after_s": round(dt)}):
        return None
    pid, inc_id = inst["proc_inst_id"], variables(inst).get("incident")
    print(f"  처리 건 {pid} · 사건 {inc_id} · 경보 {alert_id}", flush=True)
    st0 = {k: w["status"] for k, w in by_activity(view(pid)).items()}
    check("모든 단계가 계획됨(TODO) · 원인 진단 진행 · 상급자 호출 TODO",
          st0.get(A(ctx, "task:diagnose")) in ("IN_PROGRESS", "SUBMITTED", "DONE", "PENDING") and st0.get(A(ctx, "task:escalate")) == "TODO", st0)
    return pid, inc_id, alert_id, injected_at


def agents_done(ctx: Ctx, tl: dict | None) -> bool:
    return bool(tl) and tl.get(A(ctx, "task:select"), {}).get("status") == "IN_PROGRESS" \
        and all(tl.get(A(ctx, p), {}).get("status") == "DONE" for p in AGENT_PARTS)


def save_run(name: str, pid: str) -> None:
    try:
        v = view(pid)
        save(f"{name}-instance", v)
        vd = variables(v["instance"])
        if vd.get("decision_id"):
            save(f"{name}-decision", get(f"{PROCESS}/api/decisions/{vd['decision_id']}"))
        if vd.get("incident"):
            save(f"{name}-incident", incident(vd["incident"]))
    except Exception as e:  # noqa: BLE001
        print(f"  (증거 저장 실패 {name}: {e})", flush=True)


# ---------------------------------------------------------------- 1 쿨러 실행
def stage_cooler(ctx: Ctx) -> None:
    do_setup(ctx)
    section("1", "1. 쿨러 — 학생 흐름으로 열화 처리 건 끝까지")
    sys.path.insert(0, str(SCRIPTS))
    from scenario_instance_test import policy_top     # 순위 정책으로 1순위 다시 계산(정답 하드코딩 없음)
    post(f"{PLANT}/api/reset")
    post(f"{ENT}/api/reset")
    time.sleep(2)
    opened = open_instance(ctx, "HYD-01", "cooler_degradation", "COOLER_DEGRADATION", 200 * ctx.clock, severity="moderate", top_level=True)
    if not opened:
        return
    pid, inc_id, alert_id, injected = opened
    try:
        inc = incident(inc_id)
        check("사건 승인 대기(AWAITING_APPROVAL) · 같은 경보", inc.get("state") == "AWAITING_APPROVAL" and inc.get("alertId") == alert_id, inc.get("state"))
        def cooler_abort(cur):      # scenario_instance_test.physical_abort 와 같은 사유(그림 id 로)
            d = get(f"{DETECTOR}/api/detector/state")["assets"].get("HYD-01", {})
            if d.get("tripped") or d.get("plc_state") == "TRIP":
                return f"PLC TRIP — 고장이 에이전트 창보다 강함 (ts1={d.get('ts1')})"
            if d.get("phase") != "RAISED" or d.get("alert_id") != alert_id:
                return f"에이전트가 끝나기 전에 쿨러 경보 해제 (phase={d.get('phase')})"
            if cur.get(A(ctx, "task:escalate"), {}).get("status") == "IN_PROGRESS" or \
                    any(cur.get(A(ctx, p), {}).get("status") == "CANCELLED" for p in AGENT_PARTS):
                return "조치 전에 흐름이 상급자 호출로 감(_abort_before_action)"
            return None
        tl, dt, stopped, hold = wait_selection(ctx, pid, alert_id, injected, abort=cooler_abort)
        if hold:
            info("쿨러: 원인 진단 보류 → 재평가 뒤 진행", _short(hold.get("assessment")))
        if not check("에이전트 4작업 DONE → 조치 카드 선택 IN_PROGRESS", agents_done(ctx, tl),
                     f"{dt:.0f}s " + _short({"tasks": {k: v['status'] for k, v in (tl or by_activity(view(pid))).items()}, "stopped": stopped}, 600)):
            return
        v = view(pid)
        check_performer(ctx, v, "쿨러")
        check("에이전트 작업이 save_task_result 로 닫힘(draft COMPLETED · 점유 해제)",
              all(tl[A(ctx, p)].get("draft_status") == "COMPLETED" and tl[A(ctx, p)].get("consumer") is None for p in AGENT_PARTS),
              {p: tl[A(ctx, p)].get("draft_status") for p in AGENT_PARTS})
        timer = tl.get(ctx.ids["timer"]) or {}
        check("선택 시간 초과 경계 타이머가 작업 행(due_date)", timer.get("status") == "IN_PROGRESS" and bool(timer.get("due_date")),
              {k: timer.get(k) for k in ("status", "due_date", "user_id")})
        vd = variables(v["instance"])
        check("처리 건 변수: 원인 · decision_id", vd.get("cause") == "cause:cooler-fin-fouling" and vd.get("decision_id"),
              {k: vd.get(k) for k in ("cause", "failure_mode", "decision_id")})
        dec = get(f"{PROCESS}/api/decisions/{vd['decision_id']}")
        top, drift = policy_top(dec)
        check("카드 순위 = 판단 사실과 순위 정책으로 다시 계산한 1순위 · fan-max-derate 가능",
              len(dec.get("options", [])) >= 2 and not drift and dec.get("recommended") == top
              and any(o["id"] == "skill:fan-max-derate" and o.get("feasible", True) for o in dec.get("options", [])),
              {"order": [o.get("sopId") for o in dec.get("options", [])], "recommended": dec.get("recommended"), "policy_top": top, "drift": drift})
        sel = tl[A(ctx, "task:select")]
        r = post(f"{PROCESS}/api/todolist/{sel['id']}/select", {"decision": dec["id"], "option": "skill:fan-max-derate", "by": "김운전",
                                                                 "role": "role:operator", "reason": "[검사] 권한 밖 승인 시도"})
        check("운전원 승인 거절(403 — 생산관리자 카드)", r.get("error") == 403, _short(r))
        r = select_with_review(sel, dec, "skill:fan-max-derate", "이생산", "role:prod-mgr", "[검사] 납기 오더 진행 중 — 생산을 멈추지 않고 유온을 내린다", inc_id)
        if not check("생산관리자 승인(사람 승인 1회)", "instance" in r and not r.get("error"), _short(r)):
            return
        check("승인 의도 1회 전달(DELIVERED)", r.get("accepted") is True and r.get("approval_status") == "DELIVERED",
              {k: r.get(k) for k in ("accepted", "approval_status")})
        inc, dt = wait_for(lambda: (x if (x := incident(inc_id)).get("cmdId") else None), 30)
        check("승인 뒤에만 PLC 명령(action.cmd)", inc is not None and inc["state"] in ("AWAITING_ACK", "ACKED", "RE_OBSERVING", "RESOLVED",
                                                                                    "WORK_ORDER_CREATED", "CLOSED"),
              f"{inc and inc['state']} cmd={inc and inc.get('cmdId')} {dt:.0f}s")
        cmd, reob = A(ctx, "task:command"), A(ctx, "task:reobserve")
        tl2, dt = wait_for(lambda: (c if (c := by_activity(view(pid))).get(reob, {}).get("status") in ("SUBMITTED", "DONE") else None), 60)
        check("PLC ACK → 명령 단계 DONE → 재관측 진행", tl2 is not None and tl2[cmd]["status"] == "DONE", f"{dt:.0f}s")
        fin = finish(ctx, pid, inc_id, ctx.ids["end_closed"], timeout=300 * ctx.clock)
        if fin:
            wi = by_activity(fin)
            done = {a for a, w in wi.items() if w["status"] == "DONE"}
            need = {A(ctx, p) for p in AGENT_PARTS + ("task:select", "task:command", "task:reobserve", "task:work-order")}
            check("8단계 DONE · 상급자 호출 CANCELLED(가지 않은 가지)", need <= done and wi.get(A(ctx, "task:escalate"), {}).get("status") == "CANCELLED",
                  {k: v["status"] for k, v in wi.items()})
            wo = (wi.get(A(ctx, "task:work-order")) or {}).get("output", {}).get("work_order") or {}
            check("CMMS 작업지시 번호", wo.get("ok") is True and str(wo.get("ref", "")).startswith("WO-"), _short(wo))
            rd = reobservation(inc_id)
            check("재관측 판정 통과(TS1 기준)", rd.get("passed") is True, _short(rd))
            check("recovered=true 기록", variables(fin["instance"]).get("recovered") is True, variables(fin["instance"]).get("recovered"))
    finally:
        save_run("cooler", pid)
        post(f"{PLANT}/api/reset")


# ---------------------------------------------------------------- 2 펌프
def stage_pump(ctx: Ctx) -> None:
    ensure_setup(ctx)
    section("2", "2. 펌프 — 같은 배포 흐름 · 근거 부족 보류 · 명시 재평가 · 종결")
    post(f"{PLANT}/api/reset")
    time.sleep(3)
    opened = open_instance(ctx, "HYD-02", "pump_leakage", "PUMP_LEAKAGE", 120)
    if not opened:
        return
    pid, inc_id, alert_id, injected = opened
    try:
        tl, dt, stopped, hold = wait_selection(ctx, pid, alert_id, injected)
        save("pump-hold-branch", hold or {"held": False})
        if hold is None:
            info("이번 실행은 보류 없이 진단됨(보류 갈래를 밟지 않음)", f"모드 {ctx.expect}")
        if not check("에이전트 4작업 DONE → 조치 카드 선택 IN_PROGRESS", agents_done(ctx, tl),
                     f"{dt:.0f}s " + _short({"tasks": {k: v['status'] for k, v in (tl or by_activity(view(pid))).items()}, "stopped": stopped}, 600)):
            return
        check_performer(ctx, view(pid), "펌프")
        vd = variables(view(pid)["instance"])
        dec = get(f"{PROCESS}/api/decisions/{vd['decision_id']}")
        opts = {o["id"]: o for o in dec.get("options", [])}
        check("원인 = 펌프 씰 마모(rule:dx-pump)", vd.get("cause") == "cause:pump-seal-wear", {k: vd.get(k) for k in ("cause", "failure_mode", "pattern")})
        check("카드: 압력 상향 제외(rule:no-pressure-raise) · 예비 펌프 전환 추천",
              dec.get("recommended") == "skill:switch-standby-pump" and opts.get("skill:raise-pressure", {}).get("feasible") is False,
              {k: (o.get("rank"), o.get("feasible")) for k, o in opts.items()})
        sel = by_activity(view(pid))[A(ctx, "task:select")]
        r = select_with_review(sel, dec, "skill:switch-standby-pump", "이생산", "role:prod-mgr", "[검사] 예비 펌프 정비 완료 상태", inc_id)
        if not check("생산관리자 예비 펌프 전환 승인", "instance" in r and not r.get("error"), _short(r)):
            return
        inc, dt = wait_for(lambda: (x if (x := incident(inc_id)).get("state") in ("RE_OBSERVING", "RESOLVED", "WORK_ORDER_CREATED", "CLOSED") else None), 60)
        check("PUMP_SELECT 명령 → PLC ACK", inc is not None and (inc.get("ack") or {}).get("result") == "DONE",
              _short({"state": inc and inc.get("state"), "ack": inc and inc.get("ack")}))
        s, dt = wait_for(lambda: (u if (u := tags("HYD-02"))["status"].get("pump") == "B" and u["tags"]["PS1"] >= 165 else None), 15, every=0.25)
        s = s or tags("HYD-02")
        check("PLC 펌프 B · PS1 ≥ 165 회복", s["status"].get("pump") == "B" and s["tags"]["PS1"] >= 165, f"pump={s['status'].get('pump')} PS1={s['tags']['PS1']}")
        fin = finish(ctx, pid, inc_id, ctx.ids["end_closed"])
        if fin:
            wo = (by_activity(fin).get(A(ctx, "task:work-order")) or {}).get("output", {}).get("work_order") or {}
            check("작업지시(씰 교체) CMMS", wo.get("ok") is True, _short(wo))
            rd = reobservation(inc_id)
            check("재관측은 PS1 ≥ 165 로 판정(TS1 아님)", rd.get("criterion") == "PS1 >= 165.0" and rd.get("passed") is True, _short(rd))
    finally:
        save_run("pump", pid)


# ---------------------------------------------------------------- 3 팬/가림 (B5 What-if · KPI · 질문하기 + 실패 가지)
def stage_b5(ctx: Ctx) -> None:
    a = ctx.args
    section("3", "3. 팬/가림 — B5 What-if 관점 중요도 바꿔 보기")
    code, base = call("POST", f"{AGENT}/api/agent/whatif", {"asset": a.whatif_asset, "pattern": a.whatif_pattern}, timeout=120)   # whatif.js start
    save("whatif-base", base)
    if check(f"What-if 기준 판단({a.whatif_asset} · {a.whatif_pattern}) — 읽기 전용", code == 200 and isinstance(base, dict) and base.get("id")
             and (base.get("original") or {}).get("unchanged"), f"{code} {_short(base)}"):
        pv = base.get("perspectives") or {}
        used = [p for p in pv.get("perspectives") or [] if p.get("inUse")]
        unused = [p for p in pv.get("perspectives") or [] if not p.get("inUse")]
        if check("관점(지식 그래프의 BSC 관점) 읽힘 · 이 판단이 쓰는 관점 있음", pv.get("available") and used,
                 [(p.get("name"), p.get("inUse")) for p in pv.get("perspectives") or []] or pv.get("reason")):
            p = used[0]
            code, t = call("POST", f"{AGENT}/api/agent/whatif/{base['id']}/try",
                           {"values": {}, "policy": {"weights": {}, "penalties": {}, "perspectives": {p["id"]: 3}}}, timeout=120)
            save("whatif-perspective-x3", t)
            before = {c["id"]: c.get("score") for c in base.get("cards") or []}
            after = {c["id"]: c.get("score") for c in (t.get("cards") if isinstance(t, dict) else None) or []}
            check(f"관점 '{p.get('name')}' ×3 → 카드 점수(성과 지표 득실)가 그 비중으로 다시 계산", code == 200 and after and after != before,
                  {"before": before, "after": after, "top": (t or {}).get("top") if isinstance(t, dict) else None})
            check("시험 실행은 원본(판단 묶음 · 정책) 불변", isinstance(t, dict) and (t.get("original") or {}).get("unchanged")
                  and (t.get("original") or {}).get("fingerprint") == (base.get("original") or {}).get("fingerprint"), (t or {}).get("original") if isinstance(t, dict) else t)
            if unused:
                code, u = call("POST", f"{AGENT}/api/agent/whatif/{base['id']}/try",
                               {"values": {}, "policy": {"weights": {}, "penalties": {}, "perspectives": {unused[0]["id"]: 5}}}, timeout=120)
                check(f"이 판단이 쓰지 않는 관점('{unused[0].get('name')}') ×5 → 점수 그대로", code == 200
                      and {c["id"]: c.get("score") for c in u.get("cards") or []} == before, _short(u))
        code, back = call("POST", f"{AGENT}/api/agent/whatif/{base['id']}/try", {}, timeout=120)        # whatif.js '원래대로'
        check("원래대로 = 기준 1순위", code == 200 and back.get("top") == base.get("baseTop"), {"top": back.get("top") if isinstance(back, dict) else back,
                                                                                         "baseTop": base.get("baseTop")})

    section("3", "3. 팬/가림 — B5 KPI 목표 바꿔 보기")
    rep = get(f"{PROCESS}/api/kpi?period=24h", timeout=120)                                             # kpi.js
    save("kpi-base", rep)
    flat = {m["id"]: m for p in rep.get("perspectives") or [] for o in p.get("objectives") or [] for m in o.get("measures") or []}
    pick = next((m for mid, m in sorted(flat.items(), key=lambda kv: (kv[0] != "msr:availability", kv[0])) if flip_target(m) is not None), None)
    if check("실적이 계산된 지표가 있음(목표 바꿔 볼 대상)", pick is not None, {k: v.get("status") for k, v in flat.items()}):
        trial = flip_target(pick)
        code, t = call("POST", f"{PROCESS}/api/kpi/try", {"period": "24h", "targets": {pick["id"]: trial}}, timeout=120)
        save("kpi-try", t)
        changed = {c["id"]: c for c in ((t.get("trial") or {}).get("changed") or [])} if isinstance(t, dict) else {}
        ch = changed.get(pick["id"]) or {}
        check(f"'{pick.get('name')}' 목표 {pick.get('target')} → {trial}: 달성/미달 판정이 뒤집힘(실적은 그대로)",
              code == 200 and ch and ch["before"]["status"] == pick["status"] and ch["after"]["status"] != pick["status"],
              {"value": pick.get("value"), "direction": pick.get("direction"), "change": ch})
        again = get(f"{PROCESS}/api/kpi?period=24h", timeout=120)
        flat2 = {m["id"]: m for p in again.get("perspectives") or [] for o in p.get("objectives") or [] for m in o.get("measures") or []}
        check("저장된 목표 불변(시험 뒤 다시 읽어도 원래 목표)", flat2.get(pick["id"], {}).get("target") == pick.get("target"),
              {"before": pick.get("target"), "after": flat2.get(pick["id"], {}).get("target")})

    section("3", "3. 팬/가림 — B5 에이전트에게 질문하기")
    st = get(f"{PROCESS}/api/ask/status")
    save("ask-status", st)
    hist0 = get(f"{PROCESS}/api/ask")
    who = ctx.agent_id if any(x["id"] == ctx.agent_id for x in st.get("agents") or []) else "sys:agent"
    code, v = call("POST", f"{PROCESS}/api/ask", {"question": ASK_QUESTION, "agent": who, "by": "수강생", "request_id": str(uuid.uuid4())})
    save("ask-start", v)
    if not ctx.worker:
        check("legacy: 답할 일꾼 없음 → 처리 건을 만들지 않고 503 + 사유", code == 503 and "AGENT_BRIDGE=legacy" in json.dumps(v, ensure_ascii=False)
              and not st.get("ready"), f"{code} {_short(v)}")
        check("legacy: 질문 기록 늘지 않음", len(get(f"{PROCESS}/api/ask")) == len(hist0), len(hist0))
        return
    if not check(f"질문 하나 = 처리 건 하나(답할 에이전트 {who})", code == 201 and isinstance(v, dict) and v.get("id")
                 and (v.get("agent") or {}).get("id") == who, f"{code} {_short(v)}"):
        return
    done, dt = wait_for(lambda: (x if (x := get(f"{PROCESS}/api/ask/{v['id']}"))["state"] not in ASK_LIVE else None), ctx.args.ask_wait, every=3)
    save("ask-final", done or get(f"{PROCESS}/api/ask/{v['id']}"))
    res = (done or {}).get("result") or {}
    check("질문이 끝남(답 또는 답할 수 없음)", done is not None and done["state"] == "done", f"{dt:.0f}s state={(done or {}).get('state')} {(done or {}).get('message')}")
    check("실제 도구 조회가 있었음(도구 호출 기록)", ((done or {}).get("counts") or {}).get("calls", 0) >= 1, (done or {}).get("counts"))
    check("근거 있는 답(실행 기록에서 확인) 또는 '답할 수 없음 + 이유'",
          (res.get("kind") == "answered" and (res.get("verified") or 0) >= 1) or (res.get("kind") == "unanswerable" and res.get("reason")),
          _short({k: res.get(k) for k in ("kind", "answer", "verified", "reason", "by")}, 600))


def stage_fan(ctx: Ctx) -> None:
    ensure_setup(ctx)
    stage_b5(ctx)
    section("3", "3. 팬/가림 — 팬 베어링 마모 → 팬 40 % + 부하 80 % → 종결")
    post(f"{PLANT}/api/reset")
    time.sleep(3)
    opened = open_instance(ctx, "HYD-03", "fan_vibration", "FAN_VIBRATION", 150)
    if opened:
        pid, inc_id, alert_id, injected = opened
        try:
            tl, dt, stopped, hold = wait_selection(ctx, pid, alert_id, injected)
            if hold:
                info("팬: 원인 진단 보류 → 재평가 뒤 진행", _short(hold.get("assessment")))
            if check("에이전트 4작업 DONE → 조치 카드 선택 IN_PROGRESS", agents_done(ctx, tl),
                     f"{dt:.0f}s " + _short({"tasks": {k: v['status'] for k, v in (tl or by_activity(view(pid))).items()}, "stopped": stopped}, 600)):
                check_performer(ctx, view(pid), "팬")
                vd = variables(view(pid)["instance"])
                dec = get(f"{PROCESS}/api/decisions/{vd['decision_id']}")
                opts = {o["id"]: o for o in dec.get("options", [])}
                check("원인 = 팬 베어링 마모(rule:dx-fan)", vd.get("cause") == "cause:fan-bearing-wear", {k: vd.get(k) for k in ("cause", "failure_mode")})
                check("후보 카드 = 팬 SOP", {"skill:fan-slow-derate", "skill:fan-slow"} <= set(opts), sorted(opts))
                sel = by_activity(view(pid))[A(ctx, "task:select")]
                r = select_with_review(sel, dec, "skill:fan-slow-derate", "이생산", "role:prod-mgr", "[검사] 유온 상승 없이 진동만 낮춘다", inc_id)
                if check("생산관리자 팬 감속 + 부하 저감 승인", "instance" in r and not r.get("error"), _short(r)):
                    inc, dt = wait_for(lambda: (x if (x := incident(inc_id)).get("state") in ("RE_OBSERVING", "RESOLVED", "WORK_ORDER_CREATED", "CLOSED") else None), 60)
                    check("FAN_SET 40 · LOAD_SET 80 ACK", inc is not None and (inc.get("ack") or {}).get("result") == "DONE",
                          _short({"actions": inc and inc.get("actions"), "ack": inc and inc.get("ack")}))
                    s, dt = wait_for(lambda: (u if (u := tags("HYD-03"))["tags"]["VS1"] < 1.2 else None), 60)
                    check("VS1 < 1.2 mm/s", s is not None, f"{dt:.0f}s VS1={(s or tags('HYD-03'))['tags']['VS1']}")
                    if finish(ctx, pid, inc_id, ctx.ids["end_closed"]):
                        rd = reobservation(inc_id)
                        check("재관측은 VS1 < 1.2 로 판정", rd.get("criterion") == "VS1 < 1.2" and rd.get("passed") is True, _short(rd))
        finally:
            save_run("fan", pid)
    stage_mask(ctx)


def stage_mask(ctx: Ctx) -> None:
    section("3", "3. 가림 — HYD-01 펌프 누설 → 부하 70 % → 경보 해제 · PS1 미회복 → MITIGATION_FAILED → 상급자 확인")
    opened = open_instance(ctx, "HYD-01", "pump_leakage", "PUMP_LEAKAGE", 120)
    if not opened:
        return
    pid, inc_id, alert_id, injected = opened
    try:
        tl, dt, stopped, hold = wait_selection(ctx, pid, alert_id, injected)
        if hold:
            info("가림: 원인 진단 보류 → 재평가 뒤 진행", _short(hold.get("assessment")))
        if not check("에이전트 4작업 DONE → 조치 카드 선택 IN_PROGRESS", agents_done(ctx, tl),
                     f"{dt:.0f}s " + _short({"tasks": {k: v['status'] for k, v in (tl or by_activity(view(pid))).items()}, "stopped": stopped}, 600)):
            return
        vd = variables(view(pid)["instance"])
        dec = get(f"{PROCESS}/api/decisions/{vd['decision_id']}")
        sel = by_activity(view(pid))[A(ctx, "task:select")]
        r = select_with_review(sel, dec, "skill:derate-70", "김운전", "role:operator", "[검사] 일단 부하를 낮춘다", inc_id)
        if not check("운전원 부하 70 % 선택(승인 역할 운전원)", "instance" in r and not r.get("error"), _short(r)):
            return
        st, dt = wait_for(lambda: (x if (x := pattern_state("HYD-01", "PUMP_LEAKAGE")).get("phase") == "IDLE" else None), 90)
        t = tags("HYD-01")["tags"]
        check("부하 < 80 으로 경보 해제(가려짐)", st is not None, f"{dt:.0f}s load={t.get('LoadSP')} PS1={t.get('PS1')}")
        check("그래도 PS1 < 165 bar", t.get("PS1", 999) < 165, f"PS1={t.get('PS1')}")
        inc, dt = wait_for(lambda: (x if (x := incident(inc_id)).get("state") == "ESCALATED" else None), 240)
        check("사건 ESCALATED · MITIGATION_FAILED", inc is not None and inc.get("reason") == "MITIGATION_FAILED", f"{dt:.0f}s {inc and inc.get('state')} {inc and inc.get('reason')}")
        rd = reobservation(inc_id)
        check("재관측: 경보는 해제됐지만 PS1 기준 실패", rd.get("cleared") is True and rd.get("passed") is False and rd.get("criterion") == "PS1 >= 165.0", _short(rd))
        esc_ = A(ctx, "task:escalate")
        esc, dt = wait_for(lambda: (w if (w := by_activity(view(pid)).get(esc_, {})).get("status") == "IN_PROGRESS" else None), 30)
        to_mgr = esc is not None and (esc.get("user_id") == "role:prod-mgr" or any(
            x.get("via") == "role:prod-mgr" and x.get("endpoint") == esc.get("user_id") for x in esc.get("assignees") or [] if isinstance(x, dict)))
        check("상급자 호출 IN_PROGRESS → 생산관리자(역할 또는 그 구성원)", to_mgr, {"user_id": (esc or {}).get("user_id")})
        if esc:
            r = post(f"{PROCESS}/api/todolist/{esc['id']}/submit", {"output": {"note": "[검사] 부하 저감으로는 압력이 회복되지 않음. 예비 펌프 전환 지시."}, "by": "이생산"})
            check("생산관리자 확인 제출(instances.js submitTask)", "instance" in r and not r.get("error"), _short(r))
        fin = finish(ctx, pid, inc_id, ctx.ids["end_escalated"], timeout=60)
        if fin:
            check("작업지시 CANCELLED(가지 않은 가지)", by_activity(fin).get(A(ctx, "task:work-order"), {}).get("status") == "CANCELLED",
                  {k: v["status"] for k, v in by_activity(fin).items()})
    finally:
        save_run("mask", pid)
        post(f"{PLANT}/api/reset")


# ---------------------------------------------------------------- 4 작동유 (probe_b7_oil_live.run 재사용)
def stage_oil(ctx: Ctx) -> None:
    section("4", f"4. 작동유 — probe_b7_oil_live.run(흐름 id {ctx.args.oil_def_id})")
    sys.path.insert(0, str(SCRIPTS))
    import probe_b7_oil_live as b7
    oil_out = OUT / "4-oil"
    oil_out.mkdir(parents=True, exist_ok=True)
    ns = SimpleNamespace(out=str(oil_out), expect=ctx.expect, def_id=ctx.args.oil_def_id)
    oil_save = lambda name, v: (oil_out / f"{name}.json").write_text(json.dumps(v, ensure_ascii=False, indent=2, default=str), encoding="utf-8")  # noqa: E731
    start = len(b7.results)
    wait = 300 if ctx.expect == "legacy" else 1500        # probe_b7_oil_live.main 과 같은 대기
    try:
        b7.run(ns, oil_save, wait, datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    except Exception as e:  # noqa: BLE001 — 작동유 검사기 안의 예외도 좌표와 함께 실패로
        check("작동유 검사기 실행 중 예외 없음", False, f"{type(e).__name__}: {e}")
    finally:
        for name, ok, detail in b7.results[start:]:
            results.append({"stage": STAGE["title"], "name": name, "passed": bool(ok), "detail": str(detail)[:1500]})
            if not ok:
                failures.append({"stage": STAGE["title"], "check": name, "detail": str(detail)[:1500],
                                 "request": "probe_b7_oil_live 안의 요청(4-oil/ 증거 참조)", "response": None})
        (oil_out / "checks.json").write_text(json.dumps(b7.results[start:], ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- 5 끝 (B6)
def stage_bundle(ctx: Ctx, keep: bool) -> None:
    section("5", "5. 끝 — B6 구성 내보내기 → 기준으로 되돌리기 → 불러오기 → 같은 상태")
    e1 = get(f"{PROCESS}/api/config/export")                         # configBundle.js 내보내기
    if not all((e1.get("summary") or {}).get(k) for k in ("agents", "skills", "flows")):
        ensure_setup(ctx)          # --only bundle 단독 등: 내보낼 학생 구성이 없으면 B1~B4 를 먼저 만든다
        e1 = get(f"{PROCESS}/api/config/export")
    save("export-1", e1)
    s = e1.get("summary") or {}
    require("내보내기에 학생 구성(에이전트 · 스킬 · 흐름)", s.get("agents") and s.get("skills") and s.get("flows"), s)
    check("내보낸 파일에 비밀값 없음(자리표시만)", "hydpass123" not in json.dumps(e1, ensure_ascii=False), s.get("secrets_needed"))
    code, r = call("POST", f"{PROCESS}/api/config/reset", {"by": BY}, timeout=180)     # configBundle.js 기준으로 되돌리기
    save("reset-1", r)
    require("기준으로 되돌리기(열린 처리 건 없음)", code == 200, f"{code} {_short(r)}")
    e0 = get(f"{PROCESS}/api/config/export")
    save("export-after-reset", e0)
    c0 = e0.get("content") or {}
    check("되돌린 뒤 학생 구성 0(7칸)", not any(c0.get(k) for k in ("mcp_servers", "skills", "agents", "role_members", "flows", "assignments"))
          and not (c0.get("deployments") or {}).get("flows"), e0.get("summary"))
    routes = get(f"{PROCESS}/api/flows/deployments")
    check("경보 표가 기준 흐름으로", routes.get("at_reference") is True, [(x["pattern"], x["definition"]) for x in routes.get("routes") or []])
    code, imp = call("POST", f"{PROCESS}/api/config/import", {"bundle": e1, "secrets": {}, "skip_missing_secrets": False, "by": BY}, timeout=300)
    save("import", imp)
    require("내보낸 파일 불러오기(검증 → 적용 → 다시 내보내 대조)", code == 200 and isinstance(imp, dict) and imp.get("ok") and imp.get("verified"),
            f"{code} {_short(imp)}")
    e2 = get(f"{PROCESS}/api/config/export")
    save("export-2", e2)
    a, b = comparable(e1.get("content")), comparable(e2.get("content"))
    for key in ("mcp_servers", "skills", "agents", "role_members", "flows", "assignments", "deployments"):
        d = diff_paths(a.get(key), b.get(key), key)
        check(f"불러온 뒤 같은 상태: {key}", not d, d[:8])
    routes = get(f"{PROCESS}/api/flows/deployments")
    rows = {x["pattern"]: x for x in routes.get("routes") or []}
    if ctx.ids or any(f.get("definition_id") == ctx.def_id for f in a.get("flows") or []):
        check("불러온 뒤 경보 표: 학생 흐름이 다시 경보를 받음", all(rows.get(p, {}).get("definition") == ctx.def_id for p in SENSOR_PATTERNS),
              {p: rows.get(p, {}).get("definition") for p in SENSOR_PATTERNS})
    if keep:
        info("--keep-config: 학생 구성을 남김(끝나면 포털 '기준으로 되돌리기')")
        return
    code, r = call("POST", f"{PROCESS}/api/config/reset", {"by": BY}, timeout=180)
    save("reset-final", r)
    check("마지막 기준으로 되돌리기(학생 구성 정리 — 열린 처리 건이 있으면 사유)", code == 200, f"{code} {_short(r)}")


# ---------------------------------------------------------------- 실행
def summary() -> int:
    failed = [r for r in results if not r["passed"]]
    if OUT:
        (OUT / "checks.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        (OUT / "failures.json").write_text(json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")
    for r in failed:
        print(f"  FAILED: [{r['stage']}] {r['name']}  {r['detail'][:300]}")
    n, k = len(results), len(failed)
    print(f"\n{'ALL PASS' if not failed else str(k) + ' FAILED'} — {n - k}/{n} checks", flush=True)
    return 1 if failed else 0


class Tee:
    def __init__(self, path: Path):
        self.f, self.o = open(path, "w", encoding="utf-8"), sys.stdout

    def write(self, s):
        self.o.write(s)
        self.f.write(s)

    def flush(self):
        self.o.flush()
        self.f.flush()


def parse(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--expect", choices=["worker", "legacy"], required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="", help="cooler|pump|fan|oil|bundle (쉼표로 여러 개)")
    ap.add_argument("--no-reset-start", action="store_true", help="시작 전 '기준으로 되돌리기'를 하지 않음(--only 단독 실행은 기본으로 안 함)")
    ap.add_argument("--keep-config", action="store_true", help="끝에 학생 구성을 지우지 않음")
    ap.add_argument("--def-id", default="my_cooler", help="학생 흐름 id(쿨러 · 펌프 · 팬이 쓰는 배포 흐름)")
    ap.add_argument("--oil-def-id", default="my_oil_v", help="작동유 학생 흐름 id(probe_b7_oil_live 기본 my_oil 과 겹치지 않게)")
    ap.add_argument("--agent-name", default="내 진단 에이전트")
    ap.add_argument("--skill-name", default="my-cooler-check")
    ap.add_argument("--role-id", default="role:operator", help="역할 → 사람 배정(이미 구성원이 둘인 역할이라 배정 결과는 역할 공용 그대로)")
    ap.add_argument("--role-user", default="user:lee-prod")
    ap.add_argument("--mcp-name", default="my-dmn")
    ap.add_argument("--mcp-url", default="http://dmn-mcp:8198/mcp", help="정상 MCP 주소(process 컨테이너에서 연결 검사)")
    ap.add_argument("--bad-mcp-url", default="http://127.0.0.1:9/mcp", help="거절돼야 하는 주소")
    ap.add_argument("--whatif-asset", default="HYD-01")
    ap.add_argument("--whatif-pattern", default="COOLER_DEGRADATION")
    ap.add_argument("--ask-wait", type=float, default=900)
    args = ap.parse_args(argv)
    only = [s.strip() for s in args.only.split(",") if s.strip()]
    bad = [s for s in only if s not in STAGES]
    if bad:
        ap.error(f"--only: {bad} (가능: {', '.join(STAGES)})")
    args.stages = only or list(STAGES)
    return args


def main(argv=None) -> int:
    global OUT
    args = parse(argv)
    OUT = Path(args.out)
    OUT.mkdir(parents=True, exist_ok=False)
    sys.stdout = Tee(OUT / "probe.log")
    (OUT / "started.json").write_text(json.dumps({"argv": sys.argv, "started": datetime.now(timezone.utc).isoformat()}, ensure_ascii=False), encoding="utf-8")
    ctx = Ctx(args)
    full = not args.only
    reset_start = (full or "cooler" in args.stages) and not args.no_reset_start
    try:
        stage_prepare(ctx, reset_start)
    except (Abort, HttpFail, urllib.error.URLError, OSError) as e:
        if not isinstance(e, Abort):
            check("준비 단계 요청", False, f"{type(e).__name__}: {e}")
        return summary()
    runners = {"cooler": stage_cooler, "pump": stage_pump, "fan": stage_fan, "oil": stage_oil,
               "bundle": lambda c: stage_bundle(c, args.keep_config)}
    for name in STAGES:
        if name not in args.stages:
            continue
        try:
            runners[name](ctx)
        except Abort as e:
            print(f"  ({name} 단계를 멈춤: {e})", flush=True)
        except (HttpFail, urllib.error.URLError, OSError, KeyError, TypeError, ValueError) as e:
            check(f"{name} 단계 요청 · 응답 모양", False, f"{type(e).__name__}: {e}")
    return summary()


if __name__ == "__main__":
    sys.exit(main())
