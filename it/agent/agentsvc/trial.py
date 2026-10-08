"""A10 에이전트 시험 실행(드라이런): 고정 시나리오 + 에이전트 설정 → 판단 단계만, 제출·명령 없음.

    원인 진단(hyd-dmn diagnose) → [스킬 절차가 부르는 보조 도구] → 사실 수집(hyd-dmn gather_facts) → 후보 · 규정 · 순위(hyd-dmn
    evaluate_cards와 같은 cards.evaluate). submit_decision · /api/incidents · 설비 명령은 이 모듈 어디에도 없다.

같은 입력 보장 — 입력 스냅숏(record/replay): 세계를 읽는 호출(진단 · 사실 · 판단 엔진 입력 · 보조 도구)은 처음 한 번만 실제 원천에서 읽고
그 결과를 스냅숏 항목으로 남긴다. 같은 스냅숏으로 다시 돌리면(에이전트 B, 같은 에이전트 재실행) 원천을 다시 읽지 않고 같은 값을 쓴다.
따라서 같은 스냅숏 + 같은 설정이면 결과(fingerprint)가 같고, 결과 차이는 에이전트 설정 차이에서만 나온다. 읽기 실패도 스냅숏에 남긴다.

에이전트 설정이 결과를 바꾸는 곳(코드에 정답 없음 — 설정이 닿는 원천과 절차만 바뀐다):
  · 도구(MCP 서버) 구성: hyd-dmn 이 없으면 진단·판단을 못 한다(사유와 함께 멈춤). enterprise 가 없으면 업무 DB(MES·ERP·QMS·CMMS·물리 열)
    출처의 사실을 받지 못해 그 값을 검사하는 규칙·순위 식이 '미확인'으로 계산된다. 테넌트에 등록되지 않은 서버는 없는 것으로 본다.
  · 스킬: 본문에서 도구 이름을 등장 순서대로 읽어 보조 조회로 부른다(인자는 시나리오·진단 결과·본문 코드 블록에서). 본문이 다른 설비·패턴만
    가리키면 그 시나리오에서는 따르지 않는다. 결과는 근거 인용으로 남는다.
실제 Claude Code 워커와의 차이: 워커의 hyd-dmn gather_facts 는 업무 DB 를 엔진 안에서 읽으므로 enterprise 서버가 없어도 값이 온다. 시험 실행은
도구 구성을 '그 에이전트가 읽을 수 있는 원천의 경계'로 정의해 그 차이를 결정론으로 보여 준다(docs/handoff/verification/2026-10-08/u10-agent-compare.md).
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone

from . import card as cardlib, cards, guardrail

ENGINE = "hyd-dmn"
ENTERPRISE = "enterprise"
GRAPH = "neo4j"
ENTERPRISE_SOURCES = frozenset({"sys:mes", "sys:erp", "sys:qms", "sys:cmms"})
PATTERNS = ("COOLER_DEGRADATION", "PUMP_LEAKAGE", "FAN_VIBRATION", "OVERHEAT_TRIP")
ASSET_RE = re.compile(r"\bHYD-0\d\b")
MAX_ROWS = 50

# 스킬 본문에서 부를 수 있는 읽기 도구: 이름 → (서버, 인자 종류). 인자 종류: none · asset · part · failure_mode · skill_ids · sql · cypher
SKILL_TOOLS = {
    "dmn_rules": (ENGINE, "none"), "inputs": (ENGINE, "none"), "precedents": (ENGINE, "failure_mode"),
    "tradeoffs": (ENGINE, "skill_ids"), "timeseries_schema": (ENGINE, "none"), "timeseries_query": (ENGINE, "sql"),
    "mes_orders": (ENTERPRISE, "asset"), "erp_contract": (ENTERPRISE, "asset"), "erp_inventory": (ENTERPRISE, "asset"),
    "cmms_history": (ENTERPRISE, "asset"), "qms_lots": (ENTERPRISE, "asset"), "scm_suppliers": (ENTERPRISE, "part"),
    "ems_demand": (ENTERPRISE, "none"),
    "read_neo4j_cypher": (GRAPH, "cypher"),
}
# 판단 단계 자체인 도구: 스킬이 불러도 별도 호출을 만들지 않는다(정해진 단계 순서에서 한 번 부른다)
ENGINE_STEPS = frozenset({"diagnose", "gather_facts", "evaluate_cards"})
# 시험 실행이 부르지 않는 도구와 그 사유(스킬이 가리키면 '막힘'으로 기록)
REFUSED = {
    "submit_decision": "시험 실행은 판단 결과를 제출하지 않습니다",
    "write_neo4j_cypher": "시험 실행은 지식 그래프에 쓰지 않습니다",
    "forecast_actions": "조치 예측은 판단 단계(evaluate_cards)가 후보마다 계산합니다 — 스킬 보조 호출로는 부르지 않습니다",
    "query": "업무 DB 자유 SQL 은 시험 실행에서 지원하지 않습니다(정해진 읽기 도구를 쓰세요)",
    "describe_schema": "업무 DB 스키마 설명은 시험 실행에서 지원하지 않습니다",
    "describe_catalog": "업무 DB 카탈로그는 시험 실행에서 지원하지 않습니다",
    "get_neo4j_schema": "그래프 스키마 조회는 시험 실행에서 지원하지 않습니다",
}
CYPHER_WRITE = re.compile(r"\b(CREATE|MERGE|SET|DELETE|DETACH|REMOVE|DROP|LOAD\s+CSV|FOREACH)\b|\bCALL\s+(apoc|dbms|db\.create)", re.I)
ENTERPRISE_PATHS = {"mes_orders": "/mes/orders?asset={asset}", "erp_contract": "/erp/contract?asset={asset}",
                    "erp_inventory": "/erp/inventory?asset={asset}", "cmms_history": "/cmms/history?asset={asset}",
                    "qms_lots": "/qms/lots?asset={asset}", "ems_demand": "/ems/demand"}
ERROR_KO = (("ranking rule input is unknown", "순위 규칙의 입력값이 미확인입니다"),
            ("exactly one applicable executable ranking rule", "적용되는 순위 규칙이 정확히 하나가 아닙니다"),
            ("hitPolicy", "결정표 적중 정책이 엔진과 맞지 않습니다"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _plain(value):
    """Snapshot entries travel as JSON (process DB jsonb): neo4j/psycopg values become plain JSON here, once."""
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def key_of(kind: str, *parts) -> str:
    return kind + "|" + canonical(list(parts))


def korean_error(message: str) -> str:
    text = str(message or "")
    for needle, ko in ERROR_KO:
        if needle in text:
            return f"{ko} (원문: {text[:200]})"
    return text[:300]


# ---------------------------------------------------------------- snapshot (record / replay)
class Snapshot:
    """entries: key → {kind, observed_at, ok, value | error}. New reads are collected in `added` for the caller to persist."""

    def __init__(self, entries: dict | None = None):
        self.entries = dict(entries or {})
        self.added: dict[str, dict] = {}

    def read(self, key: str, kind: str, fetch):
        """(ok, value_or_error, source). source = 'snapshot' when replayed, 'live' when read now and recorded."""
        hit = self.entries.get(key)
        if hit is not None:
            return hit["ok"], hit.get("value") if hit["ok"] else hit.get("error"), "snapshot"
        try:
            entry = {"kind": kind, "observed_at": _now(), "ok": True, "value": _plain(fetch())}
        except Exception as e:  # noqa: BLE001 — a failed read is part of the frozen input too (B must see the same failure)
            entry = {"kind": kind, "observed_at": _now(), "ok": False, "error": korean_error(f"{type(e).__name__}: {e}")}
        self.entries[key] = self.added[key] = entry
        return entry["ok"], entry.get("value") if entry["ok"] else entry["error"], "live"


# ---------------------------------------------------------------- live reads (only when the snapshot has no entry)
class LiveWorld:
    """The real sources, read-only: knowledge graph templates, TimescaleDB (read-only role), enterprise GET endpoints.
    Same engine pieces as dmn_mcp.tools.DmnTools (diagnose · gather_facts · evaluate_cards' inputs) — no submission path."""

    def __init__(self, kg, tsdb):
        self._kg, self.tsdb = kg, tsdb

    @property
    def kg(self):
        if self._kg is None:
            raise RuntimeError("지식 그래프에 아직 연결되지 않았습니다")
        return self._kg

    def diagnose(self, asset: str, pattern: str) -> dict:
        from .tools import mcp_prom
        fresh = mcp_prom.freshness(self.tsdb, asset)
        if not fresh["ok"]:
            return {"withheld": True, "freshness": fresh, "causes": [], "reason": f"데이터 신뢰 불가: {fresh['reason']}"}
        t1 = self.kg.t1_causes(pattern, asset)
        results = self.tsdb.evaluate([e for r in t1 for e in (r.get("evidence") or [])], asset)
        causes = cardlib.rank_causes(t1, results)
        assessment = cardlib.evidence_status(causes)
        if assessment["withheld"] or not causes:
            return {"withheld": True, "freshness": fresh, "causes": causes, "evidence_status": assessment,
                    "reason": assessment["reason"] or "원인 후보가 없습니다"}
        t2 = {causes[0]["id"]: self.kg.t2_skills(causes[0]["id"])}
        card = cardlib.build_card(None, {"asset": asset, "pattern": pattern}, causes, t2, fresh)
        return {"withheld": False, "freshness": fresh, "evidence_status": assessment, "causes": causes,
                "skills": card["skills"], "citations": card["citations"]}

    def gather_facts(self, asset: str, pattern: str, cause: dict) -> dict:
        from . import decide as decidelib
        known = {"pattern": pattern, "cause": cause["id"], "failure_mode": cause.get("failureModeId"),
                 "failure_mode_name": cause.get("failureMode")}
        facts, prov = decidelib.gather_facts(self.kg.inputs(), asset, known, self.tsdb)
        return {"facts": facts, "provenance": prov}

    def engine_inputs(self, asset: str, failure_mode: str) -> dict:
        from . import forecasting
        dmn = self.kg.dmn()
        cand_ids = sorted({sid for r in dmn if r["decision"] == "dec:action-candidates" for sid in r.get("outputs") or []})
        skills = {r["skillId"]: r for r in self.kg.skills(cand_ids)}
        forecasts, contexts = forecasting.candidates(self.kg, asset, skills)
        return {"dmn": dmn, "skills": skills, "forecasts": forecasts, "forecast_contexts": contexts,
                "tradeoffs": self.kg.tradeoffs(cand_ids), "precedents": self.kg.precedents(failure_mode or ""),
                "suppliers": self.kg.suppliers()}

    def tool(self, server: str, tool: str, args: dict):
        if server == ENGINE:
            if tool == "dmn_rules":
                return self.kg.dmn()
            if tool == "inputs":
                return self.kg.inputs()
            if tool == "precedents":
                return self.kg.precedents(args["failure_mode"])
            if tool == "tradeoffs":
                return self.kg.tradeoffs(args["skill_ids"])
            if tool == "timeseries_schema":
                return self.tsdb.describe_schema()
            if tool == "timeseries_query":
                return self.tsdb.query(args["sql"])
        if server == ENTERPRISE:
            from .tools import mcp_ent
            if tool == "scm_suppliers":
                return mcp_ent.fetch("/scm/suppliers?part=" + args["part"], "")
            return mcp_ent.fetch(ENTERPRISE_PATHS[tool], args.get("asset", ""))
        if server == GRAPH and tool == "read_neo4j_cypher":
            return read_cypher(self.kg.driver, args["query"])
        raise ValueError(f"시험 실행이 부를 수 없는 도구입니다: {server}/{tool}")


def read_cypher(driver, query: str) -> list[dict]:
    """A skill's own Cypher, read transaction only, refused up front when it writes."""
    if CYPHER_WRITE.search(query or ""):
        raise ValueError("쓰기 Cypher(CREATE·MERGE·SET·DELETE·REMOVE·DROP·CALL apoc…)는 시험 실행에서 거절합니다")
    from neo4j import unit_of_work

    @unit_of_work(timeout=5.0)
    def work(tx):
        return [r.data() for r in tx.run(query)][:200]
    with driver.session(default_access_mode="READ") as s:
        return s.execute_read(work)


# ---------------------------------------------------------------- skills → procedure
def skill_scope(skill: dict, scenario: dict) -> tuple[bool, str | None]:
    """A skill applies everywhere unless its text names assets/patterns — then only there. Never a hidden answer list."""
    text = " ".join(str(skill.get(k) or "") for k in ("name", "description", "content"))
    assets = sorted(set(ASSET_RE.findall(text)))
    patterns = sorted({p for p in PATTERNS if p in text})
    if assets and scenario["asset"] not in assets:
        return False, f"스킬 본문이 다른 설비({', '.join(assets)})만 가리킵니다"
    if patterns and scenario["pattern"] not in patterns:
        return False, f"스킬 본문이 다른 이상 패턴({', '.join(patterns)})만 가리킵니다"
    return True, None


# ASCII boundaries (not \b): Korean particles attach directly to a tool name ("mes_orders로"), and 한글 is \w in Python
TOOL_MENTION = re.compile(r"mcp__([A-Za-z0-9_-]+)__([A-Za-z0-9_]+)|`([A-Za-z0-9_]+)`|(?<![A-Za-z0-9_])([a-z0-9]+(?:_[a-z0-9]+)+)(?![A-Za-z0-9_])")
FENCE = re.compile(r"```(sql|cypher)\s*\n(.*?)```", re.S | re.I)


def skill_procedure(content: str) -> list[dict]:
    """Tool mentions in order of appearance → [{tool, server?, sql?|cypher?}]. Bare words count only when they contain an
    underscore (dmn_rules, mes_orders…); short names (inputs, query) only as `code` or mcp__server__tool."""
    content = str(content or "")
    blocks = {"sql": [b.strip() for lang, b in FENCE.findall(content) if lang.lower() == "sql"],
              "cypher": [b.strip() for lang, b in FENCE.findall(content) if lang.lower() == "cypher"]}
    plain = FENCE.sub(" ", content)
    steps, used = [], {"sql": 0, "cypher": 0}
    for m in TOOL_MENTION.finditer(plain):
        server, name = (m.group(1), m.group(2)) if m.group(2) else (None, m.group(3) or m.group(4))
        known = name in SKILL_TOOLS or name in ENGINE_STEPS or name in REFUSED
        if not known:
            continue
        step = {"tool": name, "server": server}
        kind = SKILL_TOOLS.get(name, (None, None))[1]
        if kind in ("sql", "cypher"):
            i = used[kind]
            step[kind] = blocks[kind][i] if i < len(blocks[kind]) else None
            used[kind] += 1
        steps.append(step)
    return steps


# ---------------------------------------------------------------- one agent, one scenario
def _summary(tool: str, value) -> str:
    if isinstance(value, dict) and "rows" in value and "row_count" in value:
        return f"{value['row_count']}행" + (f" · 첫 행 {canonical(value['rows'][0])[:120]}" if value["rows"] else "")
    if isinstance(value, dict) and "facts" in value and "system" in value:
        facts = value.get("facts") or {}
        return f"{value.get('system')} 사실 {len(facts)}개: " + ", ".join(f"{k}={facts[k]}" for k in list(facts)[:4])
    if isinstance(value, list):
        return f"{len(value)}건"
    if isinstance(value, dict):
        return f"항목 {len(value)}개"
    return str(value)[:120]


def _clip(value):
    if isinstance(value, list) and len(value) > MAX_ROWS:
        return value[:MAX_ROWS] + [{"생략": f"{len(value) - MAX_ROWS}건"}]
    if isinstance(value, dict) and isinstance(value.get("rows"), list) and len(value["rows"]) > MAX_ROWS:
        return dict(value, rows=value["rows"][:MAX_ROWS], clipped=True)
    return value


def _skill_citations(tool: str, value) -> list[str]:
    if tool == "dmn_rules" and isinstance(value, list):
        return [r.get("rule") for r in value if isinstance(r, dict) and r.get("rule")]
    if tool == "inputs" and isinstance(value, list):
        return [r.get("id") for r in value if isinstance(r, dict) and r.get("id")]
    if tool == "precedents" and isinstance(value, list):
        return [r.get("skill") for r in value if isinstance(r, dict) and r.get("skill")]
    if tool == "tradeoffs" and isinstance(value, list):
        return sorted({r.get("measure") for r in value if isinstance(r, dict) and r.get("measure")})
    return []


def _usable_tools(profile: dict, tenant_servers) -> tuple[list[str], list[dict]]:
    """The agent's MCP servers that the tenant actually registers (the worker's bridge.select_servers rule)."""
    usable, notes = [], []
    for t in profile.get("tools") or []:
        if tenant_servers is not None and t not in tenant_servers:
            notes.append({"tool": t, "reason": "테넌트 MCP 에 등록되지 않은 서버라 쓸 수 없습니다"})
        elif t not in usable:
            usable.append(t)
    return usable, notes


def run_trial(scenario: dict, profile: dict, world, snapshot: Snapshot, tenant_servers=None) -> dict:
    """scenario = {asset, pattern}. profile = {id, name, tools[], skills[{name, description, content}]}.
    Returns the trial record; snapshot.added holds the reads made now (to persist with the snapshot)."""
    asset, pattern = scenario["asset"], scenario["pattern"]
    tools, tool_notes = _usable_tools(profile, tenant_servers)
    calls: list[dict] = []
    citations: list[dict] = []

    def cite(refs, by):
        for r in refs or []:
            if r and not any(c["ref"] == r for c in citations):
                citations.append({"ref": r, "by": by})

    def call(phase, server, tool, args, key, kind, fetch, by="engine"):
        entry = {"seq": len(calls) + 1, "phase": phase, "server": server, "tool": tool, "args": args, "by": by}
        calls.append(entry)
        if server not in tools:
            entry.update(status="BLOCKED", reason=f"이 에이전트의 도구 구성에 {server} 가 없어 부르지 못했습니다")
            return None
        ok, value, source = snapshot.read(key, kind, fetch)
        entry["source"] = source
        if not ok:
            entry.update(status="FAILED", reason=value)
            return None
        entry.update(status="DONE")
        return value

    out = {"scenario": {"asset": asset, "pattern": pattern},
           "agent": {"id": profile.get("id"), "name": profile.get("name"), "tools": tools, "tool_notes": tool_notes,
                     "skills": []},
           "calls": calls, "citations": citations, "diagnosis": None, "facts": [], "candidates": [], "compliance": [],
           "ranking": [], "recommended": None, "explanation": None, "guardrail": [], "rules": [], "status": None, "reason": None}

    def finish(status, reason=None):
        out.update(status=status, reason=reason)
        out["fingerprint"] = fingerprint(out)
        return out

    # 1. 원인 진단
    dx = call("원인 진단", ENGINE, "diagnose", {"asset": asset, "pattern": pattern}, key_of("diagnose", asset, pattern),
              "observation", lambda: world.diagnose(asset, pattern))
    if dx is None:
        last = calls[-1]
        return finish("NO_ENGINE_TOOL" if last["status"] == "BLOCKED" else "FAILED",
                      "판단 엔진 도구(hyd-dmn)가 없어 원인 진단·조치 판단을 할 수 없습니다" if last["status"] == "BLOCKED" else last["reason"])
    causes = dx.get("causes") or []
    calls[-1]["summary"] = (f"원인 후보 {len(causes)}개" + (f" · 1위 {causes[0]['id']}" if causes and not dx.get("withheld") else "")
                            + (" · 보류" if dx.get("withheld") else ""))
    calls[-1]["citations"] = [c["id"] for c in causes] + [e["id"] for c in causes for e in c.get("evidence") or []]
    out["diagnosis"] = {"withheld": bool(dx.get("withheld")), "reason": dx.get("reason"),
                        "causes": [{"id": c["id"], "name": c.get("name"), "score": c.get("score"),
                                    "failureModeId": c.get("failureModeId"), "failureMode": c.get("failureMode"),
                                    "evidence": [{k: e.get(k) for k in ("id", "name", "status", "value", "threshold", "expect")}
                                                 for e in c.get("evidence") or []]} for c in causes],
                        "top": None}
    if dx.get("withheld"):
        return finish("WITHHELD", dx.get("reason") or "근거가 부족해 원인 진단을 보류했습니다")
    top = causes[0]
    out["diagnosis"]["top"] = {"id": top["id"], "name": top.get("name"), "failureModeId": top.get("failureModeId"),
                               "failureMode": top.get("failureMode")}
    cite(dx.get("citations") or calls[-1]["citations"], "원인 진단")

    # 2. 스킬 절차 (본문의 도구 언급 순서)
    for skill in sorted(profile.get("skills") or [], key=lambda s: str(s.get("name") or "")):
        info = {"name": skill.get("name"), "applied": False, "reason": None, "steps": 0}
        out["agent"]["skills"].append(info)
        if not str(skill.get("content") or "").strip():
            info["reason"] = skill.get("missing") or "스킬 본문이 비어 있어 따를 절차가 없습니다"
            continue
        applies, why = skill_scope(skill, scenario)
        if not applies:
            info["reason"] = why
            continue
        info["applied"] = True
        by = f"스킬 {skill.get('name')}"
        seen = set()
        for step in skill_procedure(skill.get("content")):
            name = step["tool"]
            if name in ENGINE_STEPS:
                continue
            if name in REFUSED:
                calls.append({"seq": len(calls) + 1, "phase": "스킬 절차", "server": step.get("server") or "-", "tool": name,
                              "args": {}, "by": by, "status": "BLOCKED", "reason": REFUSED[name]})
                info["steps"] += 1
                continue
            server, kind = SKILL_TOOLS[name]
            if step.get("server") and step["server"] != server:
                calls.append({"seq": len(calls) + 1, "phase": "스킬 절차", "server": step["server"], "tool": name, "args": {}, "by": by,
                              "status": "FAILED", "reason": f"{name} 은(는) {server} 서버의 도구입니다(스킬이 {step['server']} 로 적음)"})
                info["steps"] += 1
                continue
            args = {"none": {}, "asset": {"asset": asset}, "part": {"part": "P-CLR-CORE"},
                    "failure_mode": {"failure_mode": top.get("failureModeId")},
                    "skill_ids": {"skill_ids": [s["id"] for s in dx.get("skills") or []]}}.get(kind)
            if kind in ("sql", "cypher"):
                text = step.get(kind)
                if not text:
                    calls.append({"seq": len(calls) + 1, "phase": "스킬 절차", "server": server, "tool": name, "args": {}, "by": by,
                                  "status": "FAILED", "reason": f"스킬에 실행할 {'SQL' if kind == 'sql' else 'Cypher'} 코드 블록(```{kind})이 없습니다"})
                    info["steps"] += 1
                    continue
                args = {"sql": text.replace("{asset}", asset)} if kind == "sql" else {"query": text.replace("{asset}", asset)}
            sig = (server, name, canonical(args))
            if sig in seen:
                continue
            seen.add(sig)
            info["steps"] += 1
            value = call("스킬 절차", server, name, args, key_of("tool", server, name, args), "tool",
                         lambda s=server, n=name, a=args: _clip(world.tool(s, n, a)), by=by)
            if value is not None:
                calls[-1]["summary"] = _summary(name, value)
                refs = _skill_citations(name, value)
                calls[-1]["citations"] = refs or [f"도구:{server}/{name}"]
                cite(calls[-1]["citations"], by)

    # 3. 사실 수집 (도구 구성이 닿는 원천만)
    gathered = call("사실 수집", ENGINE, "gather_facts",
                    {"asset": asset, "pattern": pattern, "cause": top["id"], "failure_mode": top.get("failureModeId")},
                    key_of("gather_facts", asset, pattern, top["id"], top.get("failureModeId")), "observation",
                    lambda: world.gather_facts(asset, pattern, top))
    if gathered is None:
        return finish("FAILED", calls[-1].get("reason"))
    facts = dict(gathered.get("facts") or {})
    blocked = []
    rows = []
    for p in gathered.get("provenance") or []:
        business = p.get("source") in ENTERPRISE_SOURCES or bool(p.get("binding"))
        row = {k: p.get(k) for k in ("variable", "name", "source", "sourceName", "value", "how", "error")}
        if business and ENTERPRISE not in tools:
            facts[p["variable"]] = None
            row.update(value=None, blocked="업무 DB 도구(enterprise)가 없어 이 값을 받지 못했습니다")
            blocked.append(p["variable"])
        rows.append(row)
    out["facts"] = rows
    calls[-1]["summary"] = f"사실 {len(rows)}개" + (f" · 업무 DB 값 {len(blocked)}개 받지 못함" if blocked else "")
    calls[-1]["citations"] = [r["variable"] for r in rows if r.get("value") is not None]
    if blocked:
        calls[-1]["blocked_facts"] = blocked
    cite([f"사실:{v}" for v in calls[-1]["citations"]], "사실 수집")

    # 4. 후보 → 규정 → 순위 (evaluate_cards 와 같은 순수 엔진)
    ctx = call("판단", ENGINE, "evaluate_cards",
               {"asset": asset, "pattern": pattern, "cause": top["id"], "failure_mode": top.get("failureModeId")},
               key_of("engine", asset, top.get("failureModeId")), "knowledge",
               lambda: world.engine_inputs(asset, top.get("failureModeId")))
    if ctx is None:
        return finish("FAILED", calls[-1].get("reason"))
    out["rules"] = sorted({r["rule"] for r in ctx.get("dmn") or []})
    try:
        result = cards.evaluate(ctx["dmn"], ctx["skills"], facts, ctx["forecasts"], ctx["tradeoffs"], ctx["precedents"],
                                ctx["suppliers"], ctx.get("forecast_contexts"))
    except (ValueError, TypeError, KeyError) as e:
        calls[-1].update(status="FAILED", reason=korean_error(str(e)))
        return finish("FAILED", korean_error(str(e)))
    out["candidates"] = [{"rule": t["rule"], "fired": t["fired"], "unknown": t["unknown"]}
                         for t in result["trace"] if t["decision"] == "dec:action-candidates"]
    out["compliance"] = [{"id": o["id"], "sopId": o.get("sopId"), "name": o.get("name"),
                          "excluded": [v.get("annotation") for v in o["violations"]],
                          "penalty": [p.get("annotation") for p in o["penalties"]],
                          "warn": [w.get("annotation") for w in o["warnings"]]} for o in result["options"]]
    out["ranking"] = [{"rank": o["rank"], "id": o["id"], "sopId": o.get("sopId"), "name": o.get("name"),
                       "feasible": o["feasible"], "score": o.get("score"), "scoreParts": o.get("scoreParts")} for o in result["options"]]
    rec = next((o for o in result["options"] if o["id"] == result["recommended"]), None)
    out["recommended"] = {"id": rec["id"], "sopId": rec.get("sopId"), "name": rec.get("name")} if rec else None
    out["explanation"] = result.get("explanation")
    fired = [t["rule"] for t in result["trace"] if t["fired"]]
    rank_rule = (result.get("rankRule") or {}).get("rule")
    calls[-1]["summary"] = (f"후보 {len(result['options'])}장 · 제외 {sum(not o['feasible'] for o in result['options'])}장"
                            + (f" · 1순위 {rec.get('sopId')}" if rec else " · 가능한 조치 없음"))
    calls[-1]["citations"] = fired + ([rank_rule] if rank_rule else [])
    cite(calls[-1]["citations"], "판단 규칙")
    if rec:
        cite([rec["id"], rec.get("sopId")], "1순위")
    out["guardrail"] = guardrail.check_cards(result)
    if out["guardrail"]:
        return finish("REJECTED_BY_GUARDRAIL", "; ".join(out["guardrail"]))
    if not rec:
        return finish("NO_FEASIBLE_OPTION", result.get("explanation"))
    return finish("EVALUATED")


FINGERPRINT_DROP = {"source", "observed_at"}


def _strip(value):
    if isinstance(value, dict):
        return {k: _strip(v) for k, v in value.items() if k not in FINGERPRINT_DROP}
    if isinstance(value, list):
        return [_strip(v) for v in value]
    return value


def fingerprint(trial: dict) -> str:
    """Hash of everything the agent concluded and how (calls in order, results, citations) — not who (two agents with the
    same settings conclude the same), not where a read came from (live vs snapshot) and not when.
    Same snapshot + same settings → same fingerprint."""
    core = {k: v for k, v in trial.items() if k not in ("fingerprint", "agent")}
    return hashlib.sha256(canonical(_strip(core)).encode()).hexdigest()
