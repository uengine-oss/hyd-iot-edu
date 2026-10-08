"""B6 (확정 TODO B6, DECISIONS 110 ⑤): 구성 내보내기 · 가져오기 = 막별 "출발본", 하나의 "기준으로 되돌리기".

강사가 막마다 출발본 파일을 주면 학생은 포털에서 한 번에 불러와 같은 지점에서 시작한다. 망쳐도 다시 불러오면 된다.
출발본에는 **학생이 만든 것만** 담는다(B1~B4 가 origin='user' 등으로 구분한 것). 기준(seed) 것은 담지 않는다.

  GET  /api/config/export   → 파일 하나(JSON): 형식 이름 · 판수 · 만든 시각 · 내용
        mcp_servers   B2 학생 서버(포털 등록 · 랩업 SQL). 비밀값(비밀 이름의 env · headers 값, 주소 비밀번호, 비밀이 든 인자)은
                      값 대신 자리표시 ${HYD_SECRET:<칸>} 와 secrets 목록 — 파일에 비밀값이 남지 않는다.
        skills        B1 학생 스킬(SKILL.md 본문 그대로)
        agents        B1 학생 에이전트(id · 프로필 · 스킬 이름 · 도구 서버 이름). id 를 그대로 담아 단계 배정이 같은 에이전트를 가리킨다.
        role_members  B1 학생이 넣은 업무분장(역할 ← 사람)
        flows         B3 가져온 흐름: 판본마다 .bpmn 원본 + 매핑 + 정의 해시, 마지막 초안
        assignments   B1 단계 → 에이전트 배정
        deployments   B4 경보 경로에 올린 학생 흐름(배포 순서대로) · 기준 흐름의 운영 판본이 기준 판본이 아니면 그 판본
  POST /api/config/import   {bundle, secrets?, skip_missing_secrets?, by?} (또는 파일 그대로)
        1) 검증(아무것도 바꾸지 않음): 형식 · 판수 · 칸 · 이름 겹침 · 참조(스킬 · 도구 서버 · 에이전트 · 흐름 · 판본) ·
           흐름은 B3 사전 검사를 그대로 돌리고 다시 만든 정의가 파일의 해시와 같은지 · 비밀값 필요 → 422 사유
        2) 진행 중 처리 건 확인(아래 reset 과 같은 조건) → 409, 아무것도 바꾸지 않음
        3) 지금 학생 구성을 안에서만 보관(비밀값 포함, 응답에 싣지 않음) → 되돌리기(B4 · B3 · B1 · B2 — 질문 기록은 구성이 아니라 그대로)
        4) 순서대로 적용: MCP → 스킬 → 에이전트 → 업무분장 → 흐름 등록(B3 경로, 사전 검사 통과해야) → 단계 배정 → 배포
        5) 다시 내보내 파일 내용과 같은지 대조(빈 성공 금지)
        실패하면 어디서 왜 실패했는지 + 적용된 것 · 안 된 것, 그리고 3)의 보관본으로 적용 전 상태를 다시 세운다(rolled_back).
        같은 파일을 두 번 가져와도 되돌리기 → 적용이라 같은 결과다.
  POST /api/config/reset    하나의 "기준으로 되돌리기": B4 deploy-reset → B3 flows reset → B1 agents reset → B2 mcp reset → B5 ask reset.
        먼저 409 조건을 모두 점검한다(학생 판본을 쓰는 진행 중 처리 건 · 학생 에이전트가 실행 중인 작업). 하나라도 있으면
        아무것도 지우지 않고 사유.

원본 대조: process-gpt-vue3 에는 구성 묶음 내보내기가 없다(정의는 ProcessDefinitionChatHeader.vue 의 BPMN 파일 내보내기/가져오기,
MCP 비밀값은 MCPEnvSecret.vue 의 별도 저장소). HYD 는 수업 출발본이 목적이라 B1~B4 저장소를 묶어 한 파일로 만든다.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import urllib.parse
from copy import deepcopy
from datetime import datetime, timezone

from . import agent_authoring as A
from . import bpmn_import, mcp_check, mcp_registry
from .agents_store import SKILL_NAME_RE, csv_list
from .bpmn_store import FlowStore, next_version

log = logging.getLogger("process.config_bundle")

FORMAT = "hyd-config-bundle"
FORMAT_VERSION = 1
SECRET_RE = re.compile(r"\$\{HYD_SECRET:([^}]+)\}")
AGENT_ID_RE = re.compile(r"^agent:u-[0-9a-f]{4,32}$")
CONTENT_KEYS = ("mcp_servers", "skills", "agents", "role_members", "flows", "assignments", "deployments")
STEPS = (("mcp", "MCP 서버"), ("skills", "스킬"), ("agents", "에이전트"), ("role_members", "업무분장"),
         ("flows", "흐름 등록"), ("assignments", "단계 배정"), ("deployments", "배포"))
STEP_LABEL = dict(STEPS) | {"reset": "적용 전 되돌리기", "verify": "적용 뒤 대조"}
RESET_STEPS = (("deploy_reset", "배포 되돌리기(경보 → 기준 흐름)"), ("flows_reset", "가져온 흐름 지우기"),
               ("agents_reset", "내가 만든 에이전트 · 스킬 · 배정 · 업무분장 지우기"), ("mcp_reset", "내가 등록한 MCP 서버 지우기"),
               ("ask_reset", "끝난 질문 기록 지우기"))
_LOCK = threading.Lock()          # 되돌리기 · 불러오기는 한 번에 하나(두 번 누름 · 두 탭)


class BundleError(Exception):
    """HTTP 상태 + 사람이 읽을 사유 + 덧붙일 칸(problems · applied · needs_secrets …)."""

    def __init__(self, status: int, reason: str, **extra):
        super().__init__(reason)
        self.status, self.reason, self.extra = status, reason, extra

    def detail(self) -> dict:
        return {"reason": self.reason, **self.extra}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def definition_hash(raw: dict) -> str:
    return hashlib.sha256(json.dumps(raw, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def _token(slot: str) -> str:
    return "${HYD_SECRET:" + slot + "}"


# ---------------------------------------------------------------- MCP 서버: 파일 칸 ↔ 등록 본문 (비밀값 자리표시)
def _secret_value(key: str, value: str) -> bool:
    return value != "" and (mcp_check.is_secret_key(key) or mcp_check.mask_text(value) != value)


def server_item(name: str, entry: dict, *, include_secrets: bool = False) -> dict:
    """tenants.mcp 한 칸 → 파일 칸. 비밀값은 자리표시(${HYD_SECRET:칸})로 바꾸고 secrets 에 칸 이름 · 설명을 적는다."""
    spec = mcp_check.normalize(entry)
    item: dict = {"name": name, "origin": mcp_registry.origin_of(name, entry), "transport": spec["transport"]}
    secrets: list[dict] = []

    def hide(slot: str, label: str, value: str) -> str:
        if include_secrets:
            return value
        secrets.append({"slot": slot, "label": label})
        return _token(slot)

    if spec["transport"] == "stdio":
        item["command"] = spec["command"]
        item["args"] = [hide(f"args.{i}", f"명령 인자 {i + 1}번째", a) if mcp_check.mask_text(a) != a else a for i, a in enumerate(spec["args"])]
        item["env"] = {k: (hide(f"env.{k}", f"환경변수 {k}", v) if _secret_value(k, v) else v) for k, v in (spec.get("env") or {}).items()}
        if spec.get("cwd"):
            item["cwd"] = spec["cwd"]
    else:
        url = spec["url"]
        p = urllib.parse.urlsplit(url)
        if p.password and not include_secrets:
            host = (p.hostname or "") + (f":{p.port}" if p.port else "")
            user = urllib.parse.unquote(p.username) if p.username else ""
            url = urllib.parse.urlunsplit((p.scheme, f"{user}:{hide('url.password', '주소의 비밀번호', '')}@{host}", p.path, p.query, p.fragment))
        item["url"] = url
        item["headers"] = {k: (hide(f"headers.{k}", f"접속 헤더 {k}", v) if _secret_value(k, v) else v) for k, v in (spec.get("headers") or {}).items()}
    if isinstance(entry, dict) and entry.get("description"):
        item["description"] = entry["description"]
    item["secrets"] = secrets
    return item


def _fill(text: str, values: dict) -> str:
    return SECRET_RE.sub(lambda m: values[m.group(1)], text)


def register_body(item: dict, values: dict | None = None) -> dict:
    """파일 칸 → B2 등록 본문. values = {칸: 비밀값}. 자리표시가 남으면 KeyError(칸)."""
    values = values or {}
    body = {"name": item.get("name"), "transport": item.get("transport")}
    if item.get("transport") == "stdio":
        body["command"] = item.get("command")
        body["args"] = [_fill(str(a), values) for a in item.get("args") or []]
        body["env"] = {k: _fill(str(v), values) for k, v in (item.get("env") or {}).items()}
        if item.get("cwd"):
            body["cwd"] = item["cwd"]
    else:
        url = str(item.get("url") or "")
        if "url.password" in values and _token("url.password") in url:
            url = url.replace(_token("url.password"), urllib.parse.quote(values["url.password"], safe=""))
        body["url"] = url
        body["headers"] = {k: _fill(str(v), values) for k, v in (item.get("headers") or {}).items()}
    if item.get("description"):
        body["description"] = item["description"]
    return body


def _slots_in(item: dict) -> list[str]:
    text = json.dumps({k: item.get(k) for k in ("url", "args", "env", "headers")}, ensure_ascii=False)
    return sorted(set(SECRET_RE.findall(text)))


# ---------------------------------------------------------------- 내보내기
def _agent_steps(def_id: str, raw: dict) -> list[dict]:
    """정의 하나에서 에이전트가 맡는 단계(agent_authoring.agent_activities 와 같은 규칙)."""
    from . import engine
    roles = {r.get("name"): r for r in raw.get("roles") or [] if isinstance(r, dict)}
    out = []
    for a in raw.get("activities") or []:
        if not isinstance(a, dict) or not a.get("id") or not engine.agent_mode_of(a):
            continue
        if not (a.get("orchestration") in engine.NO_MODE or a.get("orchestration") == engine.AGENT_ORCH):
            continue
        default = csv_list(a.get("agent")) or csv_list((roles.get(a.get("role")) or {}).get("endpoint"))
        out.append({"definition_id": def_id, "activity_id": a["id"], "name": a.get("name") or a["id"], "default_agents": default})
    return out


def export_bundle(rt, base_loader, *, include_secrets: bool = False) -> dict:
    """학생이 만든 것만 담은 출발본. include_secrets=True 는 안에서만(불러오기 실패 때 적용 전 상태로 되돌리는 보관본) 쓴다."""
    from . import flow_deploy
    repo, tenant = rt.repo, rt.tenant_id
    store = mcp_registry.store_for(repo)
    not_included: list[dict] = []
    servers = []
    for name, entry in sorted(store.servers(tenant).items()):
        if name in mcp_registry.BASE_SERVERS:
            continue
        try:
            servers.append(server_item(name, entry, include_secrets=include_secrets))
        except ValueError as e:
            not_included.append({"what": f"MCP 서버 '{name}'", "reason": f"설정을 읽을 수 없어 담지 않았습니다 — {e}"})
    skills = [{"skill_name": s["skill_name"], "description": s.get("description") or "", "content": s.get("content") or ""}
              for s in repo.list_skills(tenant) if A.origin_of(s) == A.USER]
    agents = []
    for u in sorted(repo.list_users(None, tenant), key=lambda u: u["id"]):
        if not (u.get("is_agent") and A.origin_of(u) == A.USER):
            continue
        agents.append({"id": u["id"], "name": u.get("username") or "", "role": u.get("role") or "", "goal": u.get("goal") or "",
                       "persona": u.get("persona") or "", "model": u.get("model") or "", "tools": csv_list(u.get("tools")),
                       "skills": [r["skill_name"] for r in repo.list_agent_skills(tenant, u["id"])]})
    names = {u["id"]: u.get("username") or u["id"] for u in repo.list_users(None, tenant)}
    members = [{"role_id": m["role_id"], "user_id": m["user_id"], "role_name": names.get(m["role_id"], m["role_id"]),
                "user_name": names.get(m["user_id"], m["user_id"])}
               for m in sorted(repo.list_role_members(tenant), key=lambda m: (m["role_id"], m["user_id"])) if A.origin_of(m) == A.USER]
    fstore = FlowStore(repo, tenant)
    flows: dict[str, dict] = {}
    for v in fstore.versions():
        row = repo.get_proc_def(v["id"], tenant, version=v["version"]) or {}
        raw = row.get("definition") or {}
        imp = raw.get("bpmnImport") or {}
        flows.setdefault(v["id"], {"definition_id": v["id"], "versions": [], "draft": None})["versions"].append(
            {"version": v["version"], "file_name": imp.get("fileName"), "bpmn": fstore.bpmn_of(v["id"], v["version"]) or "",
             "mapping": imp.get("mapping") or {}, "definition_sha256": definition_hash(raw)})
    for d in fstore.drafts():
        full = fstore.get_draft(d["proc_def_id"]) or {}
        flows.setdefault(d["proc_def_id"], {"definition_id": d["proc_def_id"], "versions": [], "draft": None})["draft"] = {
            "file_name": full.get("file_name"), "bpmn": full.get("bpmn") or "", "mapping": full.get("mapping") or {}}
    for f in flows.values():
        f["versions"].sort(key=lambda v: int(v["version"]) if str(v["version"]).isdigit() else 0)
    assignments = [{"definition_id": m["proc_def_id"], "activity_id": m["activity_id"], "agent_id": m["agent_id"]}
                   for m in repo.list_agent_map(tenant)]
    routes = flow_deploy.routes(rt)
    deployed = []
    for f in reversed(routes["flows"]):                      # 배포한 순서(오래된 것 먼저) — 같은 패턴은 나중 배포가 이긴다
        versions = {v["version"] for v in (flows.get(f["definition"]) or {}).get("versions", [])}
        if f["version"] in versions:
            deployed.append({"definition_id": f["definition"], "version": f["version"], "patterns": f["patterns"]})
        else:
            not_included.append({"what": f"배포된 흐름 '{f['definition']}' 판본 {f['version']}",
                                 "reason": "포털 흐름 가져오기(B3)로 등록한 판본이 아니라(관리 화면 JSON 등록 등) 출발본에 담지 않았습니다"})
    ref = routes["reference"]
    reference = {"definition_id": ref["definition"], "version": ref["deployed_version"]} if ref.get("changed") else None
    base = base_loader(rt) or {}
    content = {"mcp_servers": servers, "skills": skills, "agents": agents, "role_members": members,
               "flows": [flows[k] for k in sorted(flows)], "assignments": assignments,
               "deployments": {"flows": deployed, "reference": reference}}
    return {"format": FORMAT, "format_version": FORMAT_VERSION, "created_at": _now(), "tenant": tenant,
            "base": {"definition": rt.defn.id, "version": getattr(rt, "base_version", None) or rt.defn.raw.get("version"),
                     "parts_from": {"id": base.get("processDefinitionId"), "version": base.get("version")}},
            "note": "학생이 만든 것만 담은 출발본입니다. 기준(기본 에이전트 · 스킬 · MCP 서버 · 흐름 · 업무분장)은 담지 않습니다. "
                    "MCP 비밀값은 담지 않고 ${HYD_SECRET:칸} 자리표시로 남깁니다 — 불러올 때 입력합니다.",
            "summary": {"mcp_servers": len(servers), "skills": len(skills), "agents": len(agents), "role_members": len(members),
                        "flows": len(flows), "flow_versions": sum(len(f["versions"]) for f in flows.values()),
                        "assignments": len(assignments), "deployments": len(deployed) + (1 if reference else 0),
                        "secrets_needed": sum(len(s["secrets"]) for s in servers)},
            "not_included": not_included, "content": content}


# ---------------------------------------------------------------- 진행 중 확인 · 하나의 되돌리기
def blocking(rt) -> list[dict]:
    """되돌리기를 막는 것(409 조건)을 모두 점검한다 — 아무것도 바꾸지 않는다."""
    out = []
    running = FlowStore(rt.repo, rt.tenant_id).running()
    if running:
        out.append({"step": "flows_reset", "reason": f"내가 가져온 흐름으로 진행 중인 처리 건 {len(running)}건 — 끝내거나 닫은 뒤 되돌리세요",
                    "items": running})
    mine = [u["id"] for u in rt.repo.list_users(None, rt.tenant_id) if u.get("is_agent") and A.origin_of(u) == A.USER]
    busy = A.running_rows(rt.repo, rt.tenant_id, mine)
    if busy:
        out.append({"step": "agents_reset", "reason": f"내가 만든 에이전트가 지금 실행 중인 작업 {len(busy)}건 — 끝난 뒤 되돌리세요",
                    "items": [{"proc_inst_id": w.get("proc_inst_id"), "activity_id": w.get("activity_id"), "agent_id": w.get("user_id")} for w in busy]})
    return out


def _refuse_if_busy(rt, verb: str) -> None:
    found = blocking(rt)
    if found:
        raise BundleError(409, f"진행 중인 처리 건이 있어 {verb} 않았습니다(아무것도 바꾸지 않았습니다) — " + " / ".join(b["reason"] for b in found),
                          blocking=found)


def _reset_steps(rt, by: str, *, ask: bool) -> list[dict]:
    from . import ask as ask_mod
    from . import flow_deploy
    done = []
    work = [("deploy_reset", lambda: flow_deploy.deploy_reset(rt, by, "기준으로 되돌리기(구성 전체)")),
            ("flows_reset", lambda: FlowStore(rt.repo, rt.tenant_id).reset()),
            ("agents_reset", lambda: A.reset(rt, by=by)),
            ("mcp_reset", lambda: mcp_registry.reset(mcp_registry.store_for(rt.repo), rt.tenant_id))]
    if ask:
        work.append(("ask_reset", lambda: ask_mod.reset(rt)))
    labels = dict(RESET_STEPS)
    for step, fn in work:
        try:
            result = fn()
        except Exception as e:  # noqa: BLE001 — 어느 단계에서 왜 멈췄는지 사람이 읽을 사유로(빈 성공 금지)
            reason = getattr(e, "message", None) or getattr(e, "reason", None) or str(e)
            raise BundleError(409 if getattr(e, "status", None) == 409 or type(e).__name__ == "FlowBusy" else 500,
                              f"되돌리기가 '{labels[step]}' 단계에서 멈췄습니다 — {reason}", done=done, failed_step=step,
                              not_done=[s for s, _ in work if s not in {d['step'] for d in done} and s != step]) from e
        if step == "deploy_reset":
            result = {k: result.get(k) for k in ("changes", "already_reference", "message")}
        done.append({"step": step, "label": labels[step], "result": result, "text": _reset_text(step, result)})
    return done


def _reset_text(step: str, r: dict) -> str:
    """되돌리기 단계 결과를 사람이 읽는 한 줄로(화면에 영문 칸 이름을 보이지 않게)."""
    if step == "deploy_reset":
        return r.get("message") or ""
    if step == "flows_reset":
        return f"판본 {r.get('versions', 0)} · 흐름 {r.get('definitions', 0)} · 초안 {r.get('drafts', 0)} · 목록에서 숨긴 끝난 처리 건 {r.get('hidden_instances', 0)}"
    if step == "agents_reset":
        return (f"에이전트 {r.get('agents', 0)} · 스킬 {r.get('skills', 0)} · 스킬 붙이기 {r.get('attachments', 0)} · 단계 배정 {r.get('assignments', 0)} · "
                f"업무분장 {r.get('role_members', 0)} · 기본 담당으로 돌린 열린 단계 {len(r.get('returned_tasks') or [])}")
    if step == "mcp_reset":
        return f"서버 {len(r.get('removed_servers') or [])}({', '.join(r.get('removed_servers') or []) or '없음'}) · 검사 기록 {r.get('removed_checks', 0)}"
    return r.get("note") or ""


def reset_all(rt, *, by: str = "포털", audit=None) -> dict:
    """하나의 '기준으로 되돌리기'. 먼저 409 조건을 모두 점검하고, 하나라도 있으면 아무것도 지우지 않는다."""
    if not _LOCK.acquire(blocking=False):
        raise BundleError(409, "다른 되돌리기 · 불러오기가 진행 중입니다 — 끝난 뒤 다시 누르세요")
    try:
        _refuse_if_busy(rt, "되돌리지")
        steps = _reset_steps(rt, by, ask=True)
    finally:
        _LOCK.release()
    if audit:
        audit("-", by, "CONFIG_RESET", {"steps": [s["step"] for s in steps]})
    return {"steps": steps, "message": "기준으로 되돌렸습니다 — 내가 만든 에이전트 · 스킬 · 배정 · 업무분장 · MCP 서버 · 흐름 · 배포를 지웠고 기준은 그대로입니다"}


# ---------------------------------------------------------------- 검증(아무것도 바꾸지 않음)
def _problem(where: str, reason: str) -> dict:
    return {"where": where, "reason": reason}


def _text(v) -> str:
    return "" if v is None else str(v)


def validate(rt, base_loader, bundle, secrets: dict | None = None, skip_missing_secrets: bool = False) -> dict:
    """파일을 검사해 적용 계획을 돌려준다. 문제가 있으면 BundleError(422, problems | needs_secrets)."""
    problems: list[dict] = []
    if not isinstance(bundle, dict):
        raise BundleError(422, "출발본 파일이 JSON 객체가 아닙니다", problems=[_problem("파일", "JSON 객체({…})여야 합니다")])
    if bundle.get("format") != FORMAT:
        raise BundleError(422, f"출발본 형식이 아닙니다 — 형식 이름 '{_text(bundle.get('format'))[:40]}' (기대: {FORMAT})",
                          problems=[_problem("형식 이름", f"'{FORMAT}' 이어야 합니다")])
    if bundle.get("format_version") != FORMAT_VERSION:
        raise BundleError(422, f"출발본 판수 {_text(bundle.get('format_version'))[:20]} 은(는) 읽을 수 없습니다 — 이 포털은 판수 {FORMAT_VERSION} 만 읽습니다",
                          problems=[_problem("판수", f"{FORMAT_VERSION} 이어야 합니다")])
    content = bundle.get("content")
    if not isinstance(content, dict):
        raise BundleError(422, "출발본에 내용(content)이 없습니다", problems=[_problem("내용", "content 객체가 없습니다")])
    for key in CONTENT_KEYS:
        want = dict if key == "deployments" else list
        if not isinstance(content.get(key, want()), want):
            problems.append(_problem(f"내용 {key}", "목록이어야 합니다" if want is list else "객체여야 합니다"))
    if problems:
        raise BundleError(422, f"출발본 파일을 받을 수 없습니다 ({len(problems)}건) — {problems[0]['where']}: {problems[0]['reason']}", problems=problems)
    repo, tenant = rt.repo, rt.tenant_id
    secrets = secrets if isinstance(secrets, dict) else {}
    users = repo.list_users(None, tenant)
    seed_users = {u["id"]: u for u in users if not (u.get("is_agent") and A.origin_of(u) == A.USER)}
    tenant_servers = mcp_registry.store_for(repo).servers(tenant)

    # -- MCP
    plan_servers, skipped, needs = [], [], []
    seen = set()
    for i, item in enumerate(content.get("mcp_servers") or []):
        where = f"MCP 서버 {i + 1}번째"
        if not isinstance(item, dict):
            problems.append(_problem(where, "객체여야 합니다")); continue
        name = _text(item.get("name")).strip()
        where = f"MCP 서버 '{name or i + 1}'"
        if not mcp_registry.NAME_RE.match(name):
            problems.append(_problem(where, "이름은 소문자 · 숫자 · 하이픈 1~40자여야 합니다")); continue
        if name in mcp_registry.BASE_SERVERS:
            problems.append(_problem(where, "기준(기본 제공) 서버 이름입니다 — 출발본에는 학생 서버만 담습니다")); continue
        if name in seen:
            problems.append(_problem(where, "같은 이름의 서버가 파일에 두 번 있습니다")); continue
        seen.add(name)
        slots = _slots_in(item)
        given = secrets.get(name) if isinstance(secrets.get(name), dict) else {}
        missing = [s for s in slots if not _text(given.get(s)).strip()]
        labels = {s.get("slot"): s.get("label") for s in item.get("secrets") or [] if isinstance(s, dict)}
        if missing:
            if skip_missing_secrets:
                skipped.append({"what": f"MCP 서버 '{name}'", "server": name,
                                "reason": "비밀값(" + ", ".join(labels.get(s) or s for s in missing) + ")을 넣지 않아 이 서버만 건너뛰었습니다"})
                continue
            needs.append({"server": name, "slots": [{"slot": s, "label": labels.get(s) or s} for s in missing]})
            continue
        try:
            body = register_body(item, {s: _text(given.get(s)) for s in slots})
            mcp_registry.entry_from_body(body)
        except KeyError as e:
            problems.append(_problem(where, f"자리표시 {e} 에 넣을 값이 없습니다")); continue
        except mcp_registry.RegistryError as e:
            problems.append(_problem(where, e.reason)); continue
        plan_servers.append({"name": name, "body": dict(body, name=name)})
    skipped_servers = {s["server"] for s in skipped}
    file_servers = {s["name"] for s in plan_servers} | {n["server"] for n in needs}     # 비밀값을 기다리는 서버도 파일에 있는 서버

    # -- 스킬
    plan_skills, seen = [], set()
    for i, s in enumerate(content.get("skills") or []):
        if not isinstance(s, dict):
            problems.append(_problem(f"스킬 {i + 1}번째", "객체여야 합니다")); continue
        name = _text(s.get("skill_name")).strip()
        where = f"스킬 '{name or i + 1}'"
        if not SKILL_NAME_RE.match(name):
            problems.append(_problem(where, "스킬 폴더 이름은 영문 소문자 · 숫자 · 하이픈만 씁니다(최대 64자)")); continue
        if name in seen:
            problems.append(_problem(where, "같은 이름의 스킬이 파일에 두 번 있습니다")); continue
        seen.add(name)
        old = repo.get_skill(tenant, name)
        if old is not None and A.origin_of(old) != A.USER:
            problems.append(_problem(where, "기본 스킬과 이름이 같습니다 — 기준은 덮어쓰지 않습니다")); continue
        try:
            A._skill_fields(name, {"description": s.get("description"), "content": s.get("content")})
        except A.AuthoringError as e:
            problems.append(_problem(where, e.message)); continue
        plan_skills.append({"skill_name": name, "description": _text(s.get("description")), "content": _text(s.get("content"))})
    seed_skills = {s["skill_name"] for s in repo.list_skills(tenant) if A.origin_of(s) != A.USER}
    file_skills = {s["skill_name"] for s in plan_skills}

    # -- 에이전트
    plan_agents, ids, names = [], set(), set()
    seed_names = {(u.get("username") or "").strip().lower() for u in seed_users.values() if u.get("is_agent")}
    for i, a in enumerate(content.get("agents") or []):
        if not isinstance(a, dict):
            problems.append(_problem(f"에이전트 {i + 1}번째", "객체여야 합니다")); continue
        aid, name = _text(a.get("id")).strip(), _text(a.get("name")).strip()
        where = f"에이전트 '{name or aid or i + 1}'"
        if not AGENT_ID_RE.match(aid):
            problems.append(_problem(where, f"에이전트 id '{aid[:40]}' 모양이 아닙니다(agent:u-…)")); continue
        if aid in seed_users:
            problems.append(_problem(where, f"id '{aid}' 가 기본 사용자와 겹칩니다")); continue
        if aid in ids or name.lower() in names:
            problems.append(_problem(where, "같은 id 나 이름의 에이전트가 파일에 두 번 있습니다")); continue
        ids.add(aid); names.add(name.lower())
        if name.lower() in seed_names:
            problems.append(_problem(where, "기본 에이전트와 이름이 같습니다 — 다른 이름을 쓰세요")); continue
        for key, label in (("name", "이름"), ("goal", "목표")):
            if not _text(a.get(key)).strip():
                problems.append(_problem(where, f"{label} 칸이 비어 있습니다"))
        model = _text(a.get("model")).strip()
        if model and not A.MODEL_RE.match(model):
            problems.append(_problem(where, f"모델 이름 모양이 아닙니다: {model[:60]}"))
        tools, dropped = [], []
        for t in csv_list(a.get("tools")):
            if t in skipped_servers:
                dropped.append(t)
            elif t in file_servers or (t in mcp_registry.BASE_SERVERS and t in tenant_servers):
                tools.append(t)
            else:
                problems.append(_problem(where, f"도구 서버 '{t}' 가 파일에도 기준 서버에도 없습니다(참조 없는 도구 서버)"))
        if dropped:
            skipped.append({"what": f"에이전트 '{name}'의 도구 서버 {', '.join(dropped)}", "agent": aid,
                            "reason": "그 서버를 건너뛰어 이 에이전트 도구에서 뺐습니다"})
        for sk in csv_list(a.get("skills")):
            if sk not in file_skills and sk not in seed_skills:
                problems.append(_problem(where, f"스킬 '{sk}' 가 파일에도 기본 스킬에도 없습니다(참조 없는 스킬)"))
        plan_agents.append({"id": aid, "body": {"name": name, "goal": _text(a.get("goal")), "role": _text(a.get("role")),
                                                "persona": _text(a.get("persona")), "model": model, "tools": tools},
                            "skills": list(dict.fromkeys(csv_list(a.get("skills"))))})
    agent_ids = {a["id"] for a in plan_agents} | {u for u, r in seed_users.items() if r.get("is_agent") and (r.get("agent_type") or "agent") == "agent"}

    # -- 업무분장
    from . import inbox
    roles = {r["id"] for r in inbox.role_users(repo, tenant)}
    people = {u["id"] for u in inbox.person_users(repo, tenant)}
    seed_members = {(m["role_id"], m["user_id"]) for m in repo.list_role_members(tenant) if A.origin_of(m) != A.USER}
    plan_members, seen = [], set()
    for i, m in enumerate(content.get("role_members") or []):
        rid, uid = (_text(m.get("role_id")), _text(m.get("user_id"))) if isinstance(m, dict) else ("", "")
        where = f"업무분장 {m.get('role_name') or rid} ← {m.get('user_name') or uid}" if isinstance(m, dict) else f"업무분장 {i + 1}번째"
        if rid not in roles:
            problems.append(_problem(where, f"역할 '{rid}' 이(가) 없습니다")); continue
        if uid not in people:
            problems.append(_problem(where, f"사람 '{uid}' 이(가) 없습니다")); continue
        if (rid, uid) in seed_members or (rid, uid) in seen:
            problems.append(_problem(where, "이미 기본 업무분장이거나 파일에 두 번 있습니다")); continue
        seen.add((rid, uid))
        plan_members.append({"role_id": rid, "user_id": uid})

    # -- 흐름: B3 사전 검사를 적용 뒤의 에이전트 목록으로 미리 돌리고, 다시 만든 정의가 파일의 해시와 같은지
    refs = set(getattr(rt, "reference_ids", None) or {rt.defn.id})
    after_users = list(seed_users.values()) + [{"id": a["id"], "username": a["body"]["name"], "goal": a["body"]["goal"], "is_agent": True,
                                                "agent_type": "agent", "tenant_id": tenant} for a in plan_agents]
    plan_flows, flow_steps, flow_versions = [], {}, {}
    try:
        cat = bpmn_import.catalog(base_loader(rt), after_users)
    except Exception as e:  # noqa: BLE001
        cat = None
        if content.get("flows"):
            problems.append(_problem("흐름", f"부품 목록(기준 정의 파일)을 읽지 못했습니다 — {e}"))
    seen = set()
    fstore = FlowStore(repo, tenant)
    for i, f in enumerate(content.get("flows") or []):
        if not isinstance(f, dict):
            problems.append(_problem(f"흐름 {i + 1}번째", "객체여야 합니다")); continue
        did = _text(f.get("definition_id")).strip()
        where = f"흐름 '{did or i + 1}'"
        if not bpmn_import.valid_definition_id(did):
            problems.append(_problem(where, "흐름 id 는 영문자로 시작하고 영문 · 숫자 · _ . - 만 씁니다")); continue
        if did in refs or (did not in seen and fstore.is_protected(did)):
            problems.append(_problem(where, "기준 흐름 id 입니다 — 기준은 바꾸지 않습니다")); continue
        if did in seen:
            problems.append(_problem(where, "같은 흐름이 파일에 두 번 있습니다")); continue
        seen.add(did)
        versions = f.get("versions") if isinstance(f.get("versions"), list) else []
        draft = f.get("draft") if isinstance(f.get("draft"), dict) else None
        if not versions and not draft:
            problems.append(_problem(where, "판본도 초안도 없습니다")); continue
        plan_v, existing, ok = [], [], True
        for v in versions:
            vwhere = f"{where} 판본 {_text(v.get('version')) if isinstance(v, dict) else '?'}"
            if not isinstance(v, dict) or not _text(v.get("bpmn")).strip() or not isinstance(v.get("mapping"), dict):
                problems.append(_problem(vwhere, "그림(.bpmn)과 매핑이 있어야 합니다")); ok = False; break
            want = next_version(existing)
            if _text(v.get("version")) != want:
                problems.append(_problem(vwhere, f"판본 번호가 이어지지 않습니다(다음 번호는 {want}) — 등록 순서대로 1, 2, 3 …")); ok = False; break
            existing.append(want)
            try:
                parsed = bpmn_import.parse_bpmn(v["bpmn"])
            except bpmn_import.BpmnError as e:
                problems.append(_problem(vwhere, f"그림을 읽을 수 없습니다 — {e}")); ok = False; break
            if cat is None:
                ok = False; break
            result = bpmn_import.check(parsed, v["mapping"], {"catalog": cat, "definition_id": did, "version": want,
                                                               "file_name": v.get("file_name"), "xml_sha256": bpmn_import.xml_sha256(v["bpmn"]), "name": None})
            if not result["ok"]:
                first = result["problems"][0]
                at = (first.get("where") or {})
                at_text = f"{at.get('kind_label', '')} {at.get('name') or at.get('id') or ''}".strip()
                problems.append(_problem(vwhere, f"사전 검사를 통과하지 못합니다 ({len(result['problems'])}건) — {at_text + ': ' if at_text else ''}{first['reason']}"))
                ok = False; break
            sha = _text(v.get("definition_sha256"))
            if sha and definition_hash(result["definition"]) != sha:
                problems.append(_problem(vwhere, "이 포털에서 다시 만든 정의가 내보낼 때와 다릅니다 — 기준 정의 파일(부품)이나 에이전트 목록이 "
                                                  "출발본을 만든 환경과 다릅니다")); ok = False; break
            flow_steps[did] = _agent_steps(did, result["definition"])
            plan_v.append({"version": want, "bpmn": v["bpmn"], "file_name": v.get("file_name"), "mapping": v["mapping"], "sha": sha})
        if not ok:
            continue
        if draft is not None:
            try:
                bpmn_import.parse_bpmn(_text(draft.get("bpmn")))
            except bpmn_import.BpmnError as e:
                problems.append(_problem(f"{where} 초안", f"그림을 읽을 수 없습니다 — {e}")); continue
            if not isinstance(draft.get("mapping"), dict):
                problems.append(_problem(f"{where} 초안", "매핑이 객체여야 합니다")); continue
        flow_versions[did] = set(existing)
        plan_flows.append({"definition_id": did, "versions": plan_v,
                           "draft": {"bpmn": _text(draft.get("bpmn")), "file_name": draft.get("file_name"), "mapping": draft["mapping"]} if draft else None})

    # -- 단계 배정
    for d in A._latest_definitions(rt):
        if d["id"] not in flow_steps and (d["id"] in refs or not fstore.versions(d["id"])):
            flow_steps.setdefault(d["id"], _agent_steps(d["id"], d.get("definition") or {}))
    plan_maps, seen = [], set()
    for i, m in enumerate(content.get("assignments") or []):
        did, act, aid = (_text(m.get("definition_id")), _text(m.get("activity_id")), _text(m.get("agent_id"))) if isinstance(m, dict) else ("", "", "")
        where = f"단계 배정 {did} · {act}"
        steps = {s["activity_id"]: s for s in flow_steps.get(did, [])}
        if did not in flow_steps:
            problems.append(_problem(where, f"흐름 '{did}' 이(가) 파일에도 기준에도 없습니다")); continue
        if act not in steps:
            problems.append(_problem(where, "에이전트가 맡는 단계가 아닙니다(사람 · 시스템 단계이거나 없는 단계)")); continue
        if aid not in agent_ids:
            problems.append(_problem(where, f"에이전트 '{aid}' 가 파일에도 기본 에이전트에도 없습니다(참조 없는 에이전트)")); continue
        if aid in steps[act]["default_agents"]:
            problems.append(_problem(where, "그 단계의 기본 담당입니다 — 배정할 필요가 없습니다")); continue
        if (did, act) in seen:
            problems.append(_problem(where, "같은 단계 배정이 파일에 두 번 있습니다")); continue
        seen.add((did, act))
        plan_maps.append({"definition_id": did, "activity_id": act, "agent_id": aid})

    # -- 배포
    dep = content.get("deployments") or {}
    plan_deploys = []
    for d in dep.get("flows") or []:
        did, ver = (_text(d.get("definition_id")), _text(d.get("version"))) if isinstance(d, dict) else ("", "")
        if ver not in flow_versions.get(did, set()):
            problems.append(_problem(f"배포 {did} 판본 {ver}", "그 흐름 판본이 파일에 없습니다")); continue
        plan_deploys.append({"definition_id": did, "version": ver})
    ref = dep.get("reference")
    plan_ref = None
    if isinstance(ref, dict) and ref.get("version"):
        did, ver = _text(ref.get("definition_id")), _text(ref.get("version"))
        if did != rt.defn.id:
            problems.append(_problem(f"배포 기준 흐름 {did}", f"기준 흐름은 '{rt.defn.id}' 입니다"))
        elif not repo.get_proc_def(did, tenant, version=ver):
            problems.append(_problem(f"배포 기준 흐름 판본 {ver}", "이 환경에 등록되지 않은 기준 흐름 판본입니다"))
        else:
            plan_ref = {"definition_id": did, "version": ver}

    if problems:
        raise BundleError(422, f"출발본 파일을 받을 수 없습니다 ({len(problems)}건) — {problems[0]['where']}: {problems[0]['reason']}",
                          problems=problems, needs_secrets=needs or None)
    if needs:
        raise BundleError(422, "비밀값이 필요한 MCP 서버가 있습니다 — " + ", ".join(f"{n['server']}({', '.join(s['label'] for s in n['slots'])})" for n in needs)
                          + ". 값을 넣어 다시 불러오거나 '그 서버만 건너뛰기'를 고르세요(아무것도 바꾸지 않았습니다)", needs_secrets=needs)
    return {"mcp": plan_servers, "skills": plan_skills, "agents": plan_agents, "role_members": plan_members, "flows": plan_flows,
            "assignments": plan_maps, "deployments": plan_deploys, "reference": plan_ref, "skipped": skipped}


# ---------------------------------------------------------------- 적용
def _apply(rt, base_loader, plan: dict, by: str) -> list[dict]:
    """계획을 순서대로 적용한다. 실패하면 _StepFailed(어느 단계 · 무엇이 적용됐는지)."""
    repo, tenant = rt.repo, rt.tenant_id
    applied: list[dict] = []
    current = {"step": None, "items": []}

    def begin(step):
        current.update(step=step, items=[])

    def done():
        applied.append({"step": current["step"], "label": STEP_LABEL[current["step"]], "count": len(current["items"]), "items": list(current["items"])})

    try:
        begin("mcp")
        store = mcp_registry.store_for(repo)
        for s in plan["mcp"]:
            out = mcp_registry.register(store, tenant, s["body"], by)
            current["items"].append(f"{s['name']} (읽기 도구 {len(out['gate']['read_tools'])}개)")
        done()
        begin("skills")
        for s in plan["skills"]:
            A.create_skill(repo, tenant, s, by=by)
            current["items"].append(s["skill_name"])
        done()
        begin("agents")
        for a in plan["agents"]:
            if repo.list_users([a["id"]], tenant):
                raise A.AuthoringError(f"에이전트 id '{a['id']}' 가 이미 있습니다", 409)
            f = A._agent_fields(repo, tenant, {**a["body"], "skills": a["skills"]})
            f.pop("skills")
            repo.write_agent({"id": a["id"], **f, "is_agent": True, "agent_type": "agent", "tenant_id": tenant, "origin": A.USER}, [], create=True)
            for sk in a["skills"]:                   # 붙인 순서를 지킨다(실행 지시문의 스킬 순서)
                repo.link_skill(tenant, a["id"], sk, True)
            current["items"].append(a["body"]["name"])
        done()
        begin("role_members")
        for m in plan["role_members"]:
            A.add_member(repo, tenant, m["role_id"], m["user_id"])
            names = {u["id"]: u.get("username") or u["id"] for u in repo.list_users([m["role_id"], m["user_id"]], tenant)}
            current["items"].append(f"{names.get(m['role_id'])} ← {names.get(m['user_id'])}")
        done()
        begin("flows")
        fstore = FlowStore(repo, tenant)
        cat = bpmn_import.catalog(base_loader(rt), repo.list_users(None, tenant))
        for f in plan["flows"]:
            did = f["definition_id"]
            if fstore.is_protected(did):
                raise ValueError(f"'{did}' 은(는) 기준 흐름 id 입니다")
            for v in f["versions"]:
                fstore.save_draft(did, v["bpmn"], v["file_name"], v["mapping"])
                existing = [x["version"] for x in fstore.versions(did)]
                ctx = {"catalog": cat, "definition_id": did, "version": next_version(existing), "file_name": v["file_name"],
                       "xml_sha256": bpmn_import.xml_sha256(v["bpmn"]), "name": None}
                result = bpmn_import.check(bpmn_import.parse_bpmn(v["bpmn"]), v["mapping"], ctx)
                if not result["ok"]:
                    first = result["problems"][0]
                    raise ValueError(f"흐름 '{did}' 판본 {v['version']}: 사전 검사를 통과하지 못했습니다 — {first['reason']}")
                raw = fstore.register(result["definition"], v["bpmn"], v["file_name"])
                if raw["version"] != v["version"]:
                    raise ValueError(f"흐름 '{did}': 판본 {v['version']} 대신 {raw['version']} 로 등록됐습니다")
                if v["sha"] and definition_hash(raw) != v["sha"]:
                    raise ValueError(f"흐름 '{did}' 판본 {v['version']}: 등록된 정의가 파일과 다릅니다")
                current["items"].append(f"{raw.get('processDefinitionName') or did} 판본 {raw['version']}")
            if f["draft"]:
                fstore.save_draft(did, f["draft"]["bpmn"], f["draft"]["file_name"], f["draft"]["mapping"])
        done()
        begin("assignments")
        steps = {(s["definition_id"], s["activity_id"]): s for s in A.agent_activities(rt)} if plan["assignments"] else {}
        for m in plan["assignments"]:
            out = A.set_assignment(rt, m["definition_id"], m["activity_id"], m["agent_id"], by=by)
            st = steps.get((m["definition_id"], m["activity_id"])) or {}
            current["items"].append(f"{st.get('definition_name') or m['definition_id']} · {st.get('name') or m['activity_id']} → {out.get('name')}")
        done()
        begin("deployments")
        for d in plan["deployments"]:
            rt.deploy_definition(d["definition_id"], d["version"], by, "출발본 불러오기")
            row = repo.get_proc_def(d["definition_id"], tenant, version=d["version"]) or {}
            current["items"].append(f"{row.get('name') or d['definition_id']} 판본 {d['version']} — 다음 경보부터")
        if plan.get("reference"):
            r = plan["reference"]
            rt.deploy_definition(r["definition_id"], r["version"], by, "출발본 불러오기(기준 흐름 운영 판본)")
            current["items"].append(f"{r['definition_id']} 판본 {r['version']}")
        done()
    except Exception as e:  # noqa: BLE001 — 어느 단계 · 어느 항목에서 왜 실패했는지 그대로 올린다
        reason = getattr(e, "message", None) or getattr(e, "reason", None) or str(e)
        raise _StepFailed(current["step"], reason, applied, list(current["items"])) from e
    return applied


class _StepFailed(Exception):
    def __init__(self, step, reason, applied, partial):
        super().__init__(reason)
        self.step, self.reason, self.applied, self.partial = step, reason, applied, partial


def _comparable(content: dict) -> dict:
    """대조용: 출처 표시(origin)와 사람이 읽을 이름 칸은 빼고, 비밀값 칸은 그대로(자리표시가 채워진 값으로)."""
    c = deepcopy(content)
    for s in c.get("mcp_servers") or []:
        s.pop("origin", None); s.pop("secrets", None)
    for m in c.get("role_members") or []:
        m.pop("role_name", None); m.pop("user_name", None)
    for d in (c.get("deployments") or {}).get("flows") or []:
        d.pop("patterns", None)
    return c


def _expected(bundle_content: dict, plan: dict) -> dict:
    """적용 뒤 내보내기가 돌려줘야 할 내용(건너뛴 서버 · 도구는 빼고, 비밀값은 넣은 값으로, 비어 있어도 되는 칸은 기본값으로)."""
    c = deepcopy(bundle_content)
    for key in CONTENT_KEYS:
        c.setdefault(key, {} if key == "deployments" else [])
    for s in c["skills"]:
        s["description"] = _text(s.get("description"))
    for a in c["agents"]:
        for k in ("role", "persona", "model"):
            a[k] = _text(a.get(k))
        a["skills"] = list(dict.fromkeys(csv_list(a.get("skills"))))
    for f in c["flows"]:
        f.setdefault("draft", None)
        for v in f.setdefault("versions", []):
            v.setdefault("file_name", None)
        if f["draft"]:
            f["draft"].setdefault("file_name", None)
    filled = {s["name"]: s["body"] for s in plan["mcp"]}
    c["mcp_servers"] = []
    for s in bundle_content.get("mcp_servers") or []:
        body = filled.get(s.get("name"))
        if body is None:
            continue
        item = server_item(s["name"], mcp_registry.entry_from_body(body), include_secrets=True)
        c["mcp_servers"].append(item)
    tools = {a["id"]: a["body"]["tools"] for a in plan["agents"]}
    for a in c.get("agents") or []:
        a["tools"] = tools.get(a.get("id"), a.get("tools"))
    for f in c.get("flows") or []:
        for v in f.get("versions") or []:
            v.setdefault("definition_sha256", None)
    dep = c.setdefault("deployments", {})
    dep.setdefault("flows", []); dep.setdefault("reference", None)
    return _comparable(c)


def _diff_paths(a, b, path="") -> list[str]:
    if type(a) is not type(b):
        return [path or "(전체)"]
    if isinstance(a, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(f"{path}.{k}".lstrip("."))
            else:
                out += _diff_paths(a[k], b[k], f"{path}.{k}")
        return out
    if isinstance(a, list):
        if len(a) != len(b):
            return [f"{path} (개수 {len(a)} ≠ {len(b)})".lstrip(".")]
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += _diff_paths(x, y, f"{path}[{i}]")
        return out
    return [] if a == b else [path.lstrip(".")]


CONTENT_WORDS = {"mcp_servers": "MCP 서버", "skills": "스킬", "agents": "에이전트", "role_members": "업무분장", "flows": "흐름",
                 "assignments": "단계 배정", "deployments": "배포"}


def _say(path: str) -> str:
    """'role_members (개수 1 ≠ 0)' → '업무분장 (개수 1 ≠ 0)', 'agents[0].tools' → '에이전트[0].tools'."""
    m = re.match(r"^([a-z_]+)(.*)$", path)
    return (CONTENT_WORDS.get(m.group(1), m.group(1)) + m.group(2)) if m else path


def _verify(rt, base_loader, bundle_content: dict, plan: dict) -> list[str]:
    got = _comparable(export_bundle(rt, base_loader, include_secrets=True)["content"])
    want = _expected(bundle_content, plan)
    for f in want.get("flows") or []:                     # 해시가 없는 옛 파일은 등록된 해시를 그대로 받아들인다
        mine = next((x for x in got.get("flows") or [] if x["definition_id"] == f["definition_id"]), None)
        for i, v in enumerate(f.get("versions") or []):
            if v.get("definition_sha256") is None and mine and i < len(mine["versions"]):
                v["definition_sha256"] = mine["versions"][i]["definition_sha256"]
    return [_say(p) for p in _diff_paths(want, got)]


def import_bundle(rt, base_loader, body: dict, *, audit=None) -> dict:
    body = body if isinstance(body, dict) else {}
    bundle = body if "format" in body else body.get("bundle")
    by = str(body.get("by") or "포털")[:60]
    if not _LOCK.acquire(blocking=False):
        raise BundleError(409, "다른 되돌리기 · 불러오기가 진행 중입니다 — 끝난 뒤 다시 누르세요")
    try:
        plan = validate(rt, base_loader, bundle, body.get("secrets"), bool(body.get("skip_missing_secrets")))
        _refuse_if_busy(rt, "불러오지")
        before = export_bundle(rt, base_loader, include_secrets=True)          # 실패하면 이 상태로 다시 세운다(응답에 싣지 않음)
        try:
            try:
                reset_done = _reset_steps(rt, by, ask=False)
            except BundleError as e:
                raise _StepFailed("reset", e.reason, [], [d["label"] for d in e.extra.get("done") or []]) from e
            applied = _apply(rt, base_loader, plan, by)
            diff = _verify(rt, base_loader, bundle["content"], plan)
            if diff:
                raise _StepFailed("verify", "적용한 뒤 다시 읽은 구성이 파일과 다릅니다 — " + ", ".join(diff[:8]) + (" …" if len(diff) > 8 else ""),
                                  applied, [])
        except _StepFailed as e:
            rolled_back, rollback_error = _restore(rt, base_loader, before, by)
            failed_label = STEP_LABEL.get(e.step, "적용 뒤 대조")
            applied_steps = {a["step"] for a in e.applied}
            not_applied = [{"step": s, "label": l} for s, l in STEPS if s not in applied_steps and s != e.step]
            if audit:
                audit("-", by, "CONFIG_IMPORT_FAILED", {"step": e.step, "reason": e.reason, "rolled_back": rolled_back})
            raise BundleError(422, f"출발본 불러오기가 '{failed_label}' 단계에서 실패했습니다 — {e.reason}. "
                                   + ("불러오기 전 상태로 되돌려 놓았습니다." if rolled_back else f"불러오기 전 상태로 되돌리지 못했습니다 — {rollback_error}"),
                              failed_step=e.step, failed_label=failed_label, applied=e.applied,
                              partially_applied=e.partial, not_applied=not_applied,
                              rolled_back=rolled_back, rollback_error=rollback_error) from None
    finally:
        _LOCK.release()
    if audit:
        audit("-", by, "CONFIG_IMPORTED", {"applied": {a["step"]: a["count"] for a in applied}, "skipped": len(plan["skipped"])})
    total = sum(a["count"] for a in applied)
    return {"ok": True, "message": f"출발본을 불러왔습니다 — {total}건 적용" + (f", {len(plan['skipped'])}건 건너뜀" if plan["skipped"] else ""),
            "reset": reset_done, "applied": applied, "skipped": plan["skipped"], "verified": True}


def _restore(rt, base_loader, before: dict, by: str) -> tuple[bool, str | None]:
    """불러오기 실패 → 지금 것을 되돌리고 보관본을 다시 적용한다."""
    try:
        _reset_steps(rt, by, ask=False)
        content = before["content"]
        if not any((content.get(k) if k != "deployments" else (content[k].get("flows") or content[k].get("reference"))) for k in CONTENT_KEYS):
            return True, None
        secrets = {s["name"]: {} for s in content.get("mcp_servers") or []}
        plan = validate(rt, base_loader, before, secrets, False)
        _apply(rt, base_loader, plan, by)
        diff = _verify(rt, base_loader, content, plan)
        if diff:
            return False, "다시 세운 구성이 불러오기 전과 다릅니다 — " + ", ".join(diff[:5])
        return True, None
    except BundleError as e:
        return False, e.reason
    except _StepFailed as e:
        return False, f"'{STEP_LABEL.get(e.step, e.step)}' 단계 — {e.reason}"
    except Exception as e:  # noqa: BLE001
        log.exception("config restore failed")
        return False, str(e)


# ---------------------------------------------------------------- HTTP
def register(app, *, runtime_factory, audit=lambda *a, **k: None, base_loader=None):
    import asyncio

    from fastapi import HTTPException
    from fastapi.responses import JSONResponse

    if base_loader is None:
        from .flows_api import default_base_loader as base_loader

    def runtime():
        rt = runtime_factory()
        if rt is None:
            raise HTTPException(503, "구성 내보내기 · 가져오기에는 instance 실행 서비스가 필요합니다 (PROCESS_MODE=instance)")
        return rt

    async def run(fn):
        try:
            return await asyncio.get_running_loop().run_in_executor(None, fn)
        except BundleError as e:
            raise HTTPException(e.status, e.detail()) from e

    @app.get("/api/config/export")
    async def config_export():
        rt = runtime()
        out = await run(lambda: export_bundle(rt, base_loader))
        stamp = out["created_at"][:16].replace(":", "").replace("-", "").replace("T", "-")
        return JSONResponse(out, headers={"Content-Disposition": f'attachment; filename="hyd-starter-{stamp}.json"'})

    @app.post("/api/config/import")
    async def config_import(body: dict | None = None):
        rt = runtime()
        return await run(lambda: import_bundle(rt, base_loader, body or {}, audit=audit))

    @app.post("/api/config/reset")
    async def config_reset(body: dict | None = None):
        rt = runtime()
        by = str((body or {}).get("by") or "포털")[:60]
        return await run(lambda: reset_all(rt, by=by, audit=audit))
