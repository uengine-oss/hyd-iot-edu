"""A10 에이전트 시험 실행 · 비교 (TODO 확정 A10, E3 스킬 · E4 도구 구성, 랩업 L16 · L17 · L19 · L24).

고정 시나리오(쿨러 HYD-01 · 펌프 HYD-02 · 팬 HYD-03) + 에이전트 A · B → agent 서비스의 읽기 전용 판단(`POST /api/agent/trial`,
it/agent/agentsvc/trial.py)을 같은 입력 스냅숏으로 두 번 → 나란히 비교. 처리 건(bpm_proc_inst) · 작업(todolist) · 판단 제출 · 설비 명령을
만들지 않는다. 이 모듈이 쓰는 곳은 시험 기록 두 표(agent_trial_snapshots · agent_trials, migration 20261008000040)뿐이다.

에이전트 설정은 포털에서 바꾸지 않는다(읽기 전용). 원천은 랩업이 쓰는 그대로: users(is_agent, agent_type='agent')의 tools · skills,
스킬 본문은 스킬 저장소(tenant_skills — A2/U2 가 있으면 그 repo 함수, 없으면 같은 표를 직접 읽음). 비교용 변형은 저장된 설정에서
도구 · 스킬을 '빼 보기'만 하며 저장하지 않는다(원래대로 = 변형 없음).

실제 Claude Code 워커 경로(b)를 쓰지 않는 이유: 워커는 todolist 행을 claim_process_workitems(…,'worker')로 집는데, 이 함수는 RUNNING
상태의 부모 처리 건(bpm_proc_inst)이 있는 행만 고른다(migration 20261007000021). 결과 저장은 행을 SUBMITTED 로 바꿔 엔진이 다음 단계로
진행시킨다. 테넌트 MCP 의 hyd-dmn 서버에는 쓰기 도구 submit_decision 도 있다. 즉 기존 todolist/워커 구조로 시험 task 를 돌리면 처리 건이
생기므로 '처리 건 · 명령 0'을 지킬 수 없다 → 서버 내장 판단(a)만 구현한다.
"""
from __future__ import annotations

import asyncio
import json
import os
import secrets
import urllib.error
import urllib.request
from datetime import datetime, timezone

from fastapi import HTTPException

SCENARIOS = [
    {"key": "cooler", "asset": "HYD-01", "pattern": "COOLER_DEGRADATION", "label": "쿨러 성능 저하 · HYD-01"},
    {"key": "pump", "asset": "HYD-02", "pattern": "PUMP_LEAKAGE", "label": "펌프 내부 누설 · HYD-02"},
    {"key": "fan", "asset": "HYD-03", "pattern": "FAN_VIBRATION", "label": "팬 진동 상승 · HYD-03"},
]
BY_KEY = {s["key"]: s for s in SCENARIOS}
AGENT_TIMEOUT_S = float(os.getenv("AGENT_TRIAL_TIMEOUT_S", "120"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _id(prefix: str) -> str:
    return f"{prefix}-{datetime.now(timezone.utc):%m%d-%H%M%S}-{secrets.token_hex(2)}"


def csv_list(value) -> list[str]:
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    return []


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


# ---------------------------------------------------------------- agent settings (read-only, same source as the lab)
def _skill_rows(repo, tenant: str, names: list[str]) -> tuple[dict, str | None]:
    """Skill bodies by name from the skill store. Returns (rows by name, note when the store itself is missing)."""
    if not names:
        return {}, None
    reader = getattr(repo, "list_skills", None)          # A2/U2 repo function, when merged
    if callable(reader):
        return {r["skill_name"]: r for r in reader(tenant, names)}, None
    conn = getattr(repo, "_conn", None)
    if conn is None:
        return {}, "스킬 저장소(tenant_skills)를 읽을 수 없는 저장소입니다"
    with conn() as c:
        exists = c.execute("select to_regclass('public.tenant_skills') is not null as ok").fetchone()
        if not (exists or {}).get("ok"):
            return {}, "스킬 저장소(tenant_skills)가 아직 없습니다"
        rows = c.execute("select skill_name, description, content from tenant_skills where tenant_id = %s and skill_name = any(%s)",
                         (tenant, list(names))).fetchall()
    return {r["skill_name"]: dict(r) for r in rows}, None


def agent_profiles(repo, tenant: str) -> dict:
    """AI agents of the tenant (users.is_agent and agent_type 'agent' — systems like sys:scada are not agents) with their MCP
    servers and skills. A skill named on the agent but absent from the store is kept with the reason, never dropped."""
    users = repo.list_users(None, tenant)
    agents = [u for u in users if u.get("is_agent") and (u.get("agent_type") or "agent") == "agent"]
    assigned = {}
    pairs = getattr(repo, "list_agent_skills", None)
    if callable(pairs):
        for row in pairs(tenant):
            assigned.setdefault(row["user_id"], []).append(row["skill_name"])
    names = sorted({n for u in agents for n in csv_list(u.get("skills")) + assigned.get(u["id"], [])})
    store, store_note = _skill_rows(repo, tenant, names)
    tenant_row = repo.get_tenant(tenant) or {}
    mcp = tenant_row.get("mcp") or {}
    if isinstance(mcp, str):
        mcp = json.loads(mcp or "{}")
    servers = sorted((mcp.get("mcpServers") or {}).keys())
    out = []
    for u in sorted(agents, key=lambda u: u["id"]):
        skills = []
        for n in dict.fromkeys(csv_list(u.get("skills")) + assigned.get(u["id"], [])):
            row = store.get(n)
            skills.append({"name": n, "description": (row or {}).get("description") or "", "content": (row or {}).get("content") or "",
                           **({} if row else {"missing": store_note or "스킬 저장소에 이 이름의 스킬 본문이 없습니다"})})
        out.append({"id": u["id"], "name": u.get("username") or u["id"], "goal": u.get("goal"), "model": u.get("model"),
                    "tools": csv_list(u.get("tools")), "skills": skills})
    return {"agents": out, "tenant_servers": servers, "skill_store": store_note}


def apply_variant(profile: dict, variant: dict | None) -> tuple[dict, dict]:
    """Remove tools/skills for the comparison only (nothing is saved). Unknown names are an error, not ignored."""
    variant = variant or {}
    drop_t, drop_s = csv_list(variant.get("without_tools")), csv_list(variant.get("without_skills"))
    unknown = [t for t in drop_t if t not in profile["tools"]] + [s for s in drop_s if s not in [k["name"] for k in profile["skills"]]]
    if unknown:
        raise ValueError(f"에이전트 설정에 없는 도구·스킬은 뺄 수 없습니다: {', '.join(unknown)}")
    used = dict(profile, tools=[t for t in profile["tools"] if t not in drop_t],
                skills=[k for k in profile["skills"] if k["name"] not in drop_s])
    return used, {"without_tools": drop_t, "without_skills": drop_s}


# ---------------------------------------------------------------- store (memory · Supabase)
class MemoryTrials:
    def __init__(self):
        self.snapshots: dict[str, dict] = {}
        self.trials: dict[str, dict] = {}

    def create_snapshot(self, tenant, scenario) -> dict:
        s = {"id": _id("SNAP"), "tenant_id": tenant, "asset": scenario["asset"], "pattern": scenario["pattern"],
             "entries": {}, "created_at": _now(), "updated_at": _now()}
        self.snapshots[s["id"]] = s
        return json.loads(json.dumps(s))

    def get_snapshot(self, tenant, sid) -> dict | None:
        s = self.snapshots.get(sid)
        return json.loads(json.dumps(s)) if s and s["tenant_id"] == tenant else None

    def latest_snapshot(self, tenant, scenario) -> dict | None:
        rows = [s for s in self.snapshots.values() if s["tenant_id"] == tenant and s["asset"] == scenario["asset"]
                and s["pattern"] == scenario["pattern"]]
        return json.loads(json.dumps(max(rows, key=lambda s: s["created_at"]))) if rows else None

    def add_entries(self, tenant, sid, added: dict) -> None:
        s = self.snapshots[sid]
        for k, v in added.items():
            s["entries"].setdefault(k, v)            # first read wins: a recorded input is never replaced
        s["updated_at"] = _now()

    def save_trial(self, rec: dict) -> dict:
        self.trials[rec["id"]] = json.loads(json.dumps(rec))
        return rec

    def get_trial(self, tenant, tid) -> dict | None:
        t = self.trials.get(tid)
        return json.loads(json.dumps(t)) if t and t["tenant_id"] == tenant else None

    def list_trials(self, tenant, asset=None, limit=30) -> list[dict]:
        rows = [t for t in self.trials.values() if t["tenant_id"] == tenant and (asset is None or t["asset"] == asset)]
        return [summary(t) for t in sorted(rows, key=lambda t: (t["created_at"], t["id"]), reverse=True)[:limit]]


class PgTrials:
    def __init__(self, repo):
        self.repo = repo

    def _c(self):
        return self.repo._conn()

    def create_snapshot(self, tenant, scenario) -> dict:
        with self._c() as c:
            return dict(c.execute("insert into agent_trial_snapshots (id, tenant_id, asset, pattern) values (%s, %s, %s, %s) returning *",
                                  (_id("SNAP"), tenant, scenario["asset"], scenario["pattern"])).fetchone())

    def get_snapshot(self, tenant, sid) -> dict | None:
        with self._c() as c:
            row = c.execute("select * from agent_trial_snapshots where id = %s and tenant_id = %s", (sid, tenant)).fetchone()
            return dict(row) if row else None

    def latest_snapshot(self, tenant, scenario) -> dict | None:
        with self._c() as c:
            row = c.execute("select * from agent_trial_snapshots where tenant_id = %s and asset = %s and pattern = %s "
                            "order by created_at desc limit 1", (tenant, scenario["asset"], scenario["pattern"])).fetchone()
            return dict(row) if row else None

    def add_entries(self, tenant, sid, added: dict) -> None:
        if not added:
            return
        with self._c() as c:
            # new || existing: on a key both have, the existing (first recorded) value wins
            c.execute("update agent_trial_snapshots set entries = %s::jsonb || entries, updated_at = now() where id = %s and tenant_id = %s",
                      (json.dumps(added, ensure_ascii=False), sid, tenant))

    def save_trial(self, rec: dict) -> dict:
        Jsonb = self.repo._Jsonb
        with self._c() as c:
            c.execute("insert into agent_trials (id, tenant_id, snapshot_id, asset, pattern, agent_id, setting, variant, status, fingerprint, result, created_at) "
                      "values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                      (rec["id"], rec["tenant_id"], rec["snapshot_id"], rec["asset"], rec["pattern"], rec["agent_id"], Jsonb(rec["setting"]),
                       Jsonb(rec["variant"]), rec["status"], rec["fingerprint"], Jsonb(rec["result"]), rec["created_at"]))
        return rec

    def get_trial(self, tenant, tid) -> dict | None:
        with self._c() as c:
            row = c.execute("select * from agent_trials where id = %s and tenant_id = %s", (tid, tenant)).fetchone()
        if not row:
            return None
        row = dict(row)
        row["created_at"] = row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else row["created_at"]
        return row

    def list_trials(self, tenant, asset=None, limit=30) -> list[dict]:
        with self._c() as c:
            rows = c.execute("select * from agent_trials where tenant_id = %s and (%s::text is null or asset = %s) "
                             "order by created_at desc, id desc limit %s", (tenant, asset, asset, limit)).fetchall()
        return [summary(dict(r, created_at=r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else r["created_at"]))
                for r in rows]


def store_for(repo):
    if hasattr(repo, "dsn") and hasattr(repo, "_conn"):
        return PgTrials(repo)
    if not hasattr(repo, "_agent_trials"):
        repo._agent_trials = MemoryTrials()
    return repo._agent_trials


def summary(t: dict) -> dict:
    r = t.get("result") or {}
    dx = (r.get("diagnosis") or {}).get("top") or {}
    return {"id": t["id"], "created_at": t["created_at"], "snapshot_id": t["snapshot_id"], "asset": t["asset"], "pattern": t["pattern"],
            "agent_id": t.get("agent_id"), "agent_name": (t.get("setting") or {}).get("name"), "variant": t.get("variant"),
            "status": t["status"], "fingerprint": t["fingerprint"], "cause": dx.get("id"),
            "recommended": (r.get("recommended") or {}).get("sopId"), "calls": len(r.get("calls") or [])}


# ---------------------------------------------------------------- comparison (pure)
def _sig(call: dict) -> str:
    return canonical([call.get("server"), call.get("tool"), call.get("args")])


def align(a: list[dict], b: list[dict]) -> list[dict]:
    """LCS alignment of two tool-call sequences: rows {a: index|None, b: index|None, same}."""
    sa, sb = [_sig(c) for c in a], [_sig(c) for c in b]
    n, m = len(sa), len(sb)
    L = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            L[i][j] = L[i + 1][j + 1] + 1 if sa[i] == sb[j] else max(L[i + 1][j], L[i][j + 1])
    rows, i, j = [], 0, 0
    while i < n or j < m:
        if i < n and j < m and sa[i] == sb[j]:
            same = a[i].get("status") == b[j].get("status") and a[i].get("summary") == b[j].get("summary")
            rows.append({"a": i, "b": j, "same": same})
            i, j = i + 1, j + 1
        elif j < m and (i == n or L[i][j + 1] >= L[i + 1][j]):
            rows.append({"a": None, "b": j, "same": False})
            j += 1
        else:
            rows.append({"a": i, "b": None, "same": False})
            i += 1
    return rows


def compare(ta: dict, tb: dict) -> dict:
    """What differs between two stored trials. Same snapshot → any difference comes from the agent settings."""
    a, b = ta["result"], tb["result"]
    top = lambda r: ((r.get("diagnosis") or {}).get("top") or {})   # noqa: E731
    rec = lambda r: (r.get("recommended") or {})                     # noqa: E731
    rows = align(a.get("calls") or [], b.get("calls") or [])
    cites_a = [c["ref"] for c in a.get("citations") or []]
    cites_b = [c["ref"] for c in b.get("citations") or []]
    rank_a = {o["id"]: o for o in a.get("ranking") or []}
    rank_b = {o["id"]: o for o in b.get("ranking") or []}
    ranking = []
    for sid in list(dict.fromkeys(list(rank_a) + list(rank_b))):
        x, y = rank_a.get(sid) or {}, rank_b.get(sid) or {}
        ranking.append({"id": sid, "sopId": x.get("sopId") or y.get("sopId"), "name": x.get("name") or y.get("name"),
                        "rank_a": x.get("rank"), "rank_b": y.get("rank"), "feasible_a": x.get("feasible"), "feasible_b": y.get("feasible"),
                        "score_a": x.get("score"), "score_b": y.get("score")})
    ranking.sort(key=lambda r: (r["rank_a"] or 99, r["rank_b"] or 99))
    fa = {f["variable"]: f for f in a.get("facts") or []}
    fb = {f["variable"]: f for f in b.get("facts") or []}
    facts = [{"variable": v, "name": (fa.get(v) or fb.get(v) or {}).get("name"),
              "a": (fa.get(v) or {}).get("value"), "b": (fb.get(v) or {}).get("value"),
              "blocked_a": (fa.get(v) or {}).get("blocked"), "blocked_b": (fb.get(v) or {}).get("blocked")}
             for v in dict.fromkeys(list(fa) + list(fb))
             if canonical((fa.get(v) or {}).get("value")) != canonical((fb.get(v) or {}).get("value"))
             or bool((fa.get(v) or {}).get("blocked")) != bool((fb.get(v) or {}).get("blocked"))]
    fired = lambda r: {c["rule"] for c in r.get("candidates") or [] if c.get("fired")}   # noqa: E731
    excluded = lambda r: {c["id"]: c["excluded"] for c in r.get("compliance") or []}      # noqa: E731
    ex_a, ex_b = excluded(a), excluded(b)
    return {
        "same_input": ta["snapshot_id"] == tb["snapshot_id"],
        "same_result": ta["fingerprint"] == tb["fingerprint"],
        "status": {"a": a.get("status"), "b": b.get("status")},
        "cause": {"a": top(a).get("id"), "b": top(b).get("id"), "a_name": top(a).get("name"), "b_name": top(b).get("name"),
                  "same": top(a).get("id") == top(b).get("id")},
        "recommended": {"a": rec(a).get("id"), "b": rec(b).get("id"), "a_sop": rec(a).get("sopId"), "b_sop": rec(b).get("sopId"),
                        "a_name": rec(a).get("name"), "b_name": rec(b).get("name"), "same": rec(a).get("id") == rec(b).get("id")},
        "calls": rows,
        "order_same": [_sig(c) for c in a.get("calls") or []] == [_sig(c) for c in b.get("calls") or []],
        "calls_only_a": sum(1 for r in rows if r["b"] is None),
        "calls_only_b": sum(1 for r in rows if r["a"] is None),
        "citations": {"only_a": [c for c in cites_a if c not in cites_b], "only_b": [c for c in cites_b if c not in cites_a],
                      "shared": len([c for c in cites_a if c in cites_b])},
        "ranking": ranking,
        "facts": facts,
        "candidates": {"only_a": sorted(fired(a) - fired(b)), "only_b": sorted(fired(b) - fired(a))},
        "compliance": [{"id": k, "a": ex_a.get(k), "b": ex_b.get(k)} for k in dict.fromkeys(list(ex_a) + list(ex_b))
                       if canonical(ex_a.get(k)) != canonical(ex_b.get(k))],
        "rules": {"only_a": sorted(set(a.get("rules") or []) - set(b.get("rules") or [])),
                  "only_b": sorted(set(b.get("rules") or []) - set(a.get("rules") or []))},
    }


# ---------------------------------------------------------------- the agent service call
def call_agent(scenario: dict, agent: dict, entries: dict, tenant_servers: list[str]) -> dict:
    url = os.getenv("AGENT_URL", "http://agent:8091") + "/api/agent/trial"
    body = json.dumps({"scenario": {"asset": scenario["asset"], "pattern": scenario["pattern"]}, "agent": agent,
                       "entries": entries, "tenant_servers": tenant_servers}, ensure_ascii=False, default=str).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=AGENT_TIMEOUT_S) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"판단 서비스가 시험 실행을 거절했습니다 ({e.code}): {detail}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise RuntimeError(f"판단 서비스(agent)에 연결하지 못했습니다: {e}") from e


class TrialService:
    def __init__(self, repo, tenant: str, evaluate=call_agent):
        self.repo, self.tenant, self.evaluate = repo, tenant, evaluate
        self.store = store_for(repo)

    def options(self) -> dict:
        p = agent_profiles(self.repo, self.tenant)
        return {"scenarios": SCENARIOS, **p}

    def _scenario(self, key) -> dict:
        s = BY_KEY.get(key)
        if s is None:
            raise ValueError(f"고정 시나리오가 아닙니다: {key} (쿨러 · 펌프 · 팬 중에서 고릅니다)")
        return s

    def _snapshot(self, scenario: dict, snapshot_id: str | None, reuse_latest: bool) -> tuple[dict, bool]:
        if snapshot_id:
            s = self.store.get_snapshot(self.tenant, snapshot_id)
            if s is None:
                raise LookupError("저장된 입력 스냅숏을 찾을 수 없습니다")
            if (s["asset"], s["pattern"]) != (scenario["asset"], scenario["pattern"]):
                raise ValueError("입력 스냅숏의 시나리오가 고른 시나리오와 다릅니다")
            return s, True
        if reuse_latest:
            s = self.store.latest_snapshot(self.tenant, scenario)
            if s is not None:
                return s, True
        return self.store.create_snapshot(self.tenant, scenario), False

    def _run_one(self, scenario, snap, profiles, servers, side: dict) -> dict:
        agent_id = (side or {}).get("agent")
        profile = next((p for p in profiles if p["id"] == agent_id), None)
        if profile is None:
            raise LookupError(f"에이전트를 찾을 수 없습니다: {agent_id}")
        used, variant = apply_variant(profile, side.get("variant"))
        out = self.evaluate(scenario, used, snap["entries"], servers)
        trial, added = out["trial"], out.get("added") or {}
        self.store.add_entries(self.tenant, snap["id"], added)
        for k, v in added.items():
            snap["entries"].setdefault(k, v)
        rec = {"id": _id("TRY"), "tenant_id": self.tenant, "snapshot_id": snap["id"], "asset": scenario["asset"],
               "pattern": scenario["pattern"], "agent_id": profile["id"], "setting": used, "variant": variant,
               "status": trial["status"], "fingerprint": trial["fingerprint"], "result": trial, "created_at": _now()}
        return self.store.save_trial(rec)

    def run(self, body: dict) -> dict:
        scenario = self._scenario(body.get("scenario"))
        p = agent_profiles(self.repo, self.tenant)
        sides = [s for s in (body.get("a"), body.get("b")) if s]
        if not sides:
            raise ValueError("시험할 에이전트를 하나 이상 고르세요")
        snap, reused = self._snapshot(scenario, body.get("snapshot"), bool(body.get("reuse_latest")))
        trials = [self._run_one(scenario, snap, p["agents"], p["tenant_servers"], s) for s in sides]
        out = {"scenario": scenario, "snapshot": {"id": snap["id"], "created_at": snap["created_at"], "reused": reused,
                                                  "entries": len(snap["entries"])},
               "a": trials[0], "b": trials[1] if len(trials) > 1 else None}
        if len(trials) > 1:
            out["diff"] = compare(trials[0], trials[1])
        return out

    def diff(self, a_id: str, b_id: str) -> dict:
        ta, tb = self.store.get_trial(self.tenant, a_id), self.store.get_trial(self.tenant, b_id)
        if ta is None or tb is None:
            raise LookupError("저장된 시험 실행을 찾을 수 없습니다")
        return {"a": ta, "b": tb, "diff": compare(ta, tb)}


def register(app, *, runtime_factory, evaluate=None):
    """Routes under /api/agent-trials. runtime_factory → the instance runtime (repo · tenant_id), like manual_api."""
    def service() -> TrialService:
        rt = runtime_factory()
        if rt is None:
            raise HTTPException(503, "에이전트 설정 원천(업무 흐름 DB)에 연결된 instance 실행 서비스가 필요합니다")
        return TrialService(rt.repo, rt.tenant_id, evaluate or call_agent)

    async def run(fn):
        try:
            return await asyncio.get_running_loop().run_in_executor(None, fn)
        except LookupError as e:
            raise HTTPException(404, str(e)) from e
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        except RuntimeError as e:
            raise HTTPException(503, str(e)) from e

    @app.get("/api/agent-trials/options")
    async def trial_options():
        return await run(lambda: service().options())

    @app.post("/api/agent-trials/run")
    async def trial_run(body: dict):
        return await run(lambda: service().run(body))

    @app.get("/api/agent-trials")
    async def trial_list(asset: str | None = None, limit: int = 30):
        def work():
            svc = service()
            return svc.store.list_trials(svc.tenant, asset, max(1, min(limit, 100)))
        return await run(work)

    @app.get("/api/agent-trials/diff")
    async def trial_diff(a: str, b: str):
        return await run(lambda: service().diff(a, b))

    @app.get("/api/agent-trials/{trial_id}")
    async def trial_get(trial_id: str):
        def work():
            svc = service()
            t = svc.store.get_trial(svc.tenant, trial_id)
            if t is None:
                raise LookupError("저장된 시험 실행을 찾을 수 없습니다")
            return t
        return await run(work)
