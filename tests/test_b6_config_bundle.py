"""B6 (확정 TODO B6, DECISIONS 110 ⑤): 구성 내보내기 · 가져오기 = 막별 출발본 + 하나의 "기준으로 되돌리기".

완료 기준: 학생 구성 만들기 → 내보내기 → 되돌리기 → 가져오기 → 같은 상태(에이전트 실행 설정 · 흐름 정의 · 배포 표가 내보내기 전과 같음) /
기준 것은 파일에 없음 / 비밀값 파일에 없음 / 잘못된 파일(형식 · 판수 · 참조 없는 스킬 …)은 사유와 함께 거절 · 아무것도 안 바뀜 /
두 번 가져오기 같은 결과 / 진행 중 처리 건이 있으면 reset 409 · 아무것도 안 지움 / 적용 중 실패 → 어느 단계 · 무엇이 적용됐는지 + 적용 전 상태로.
일부러 깨뜨림: 업무분장 적용을 몰래 빼면 대조가 잡는다 · 비밀값 판정을 끄면 비밀값 시험이 잡는다 · 사전 점검을 끄면 되돌리기가 반쯤 지운다.
MCP 는 U3/B2 시험의 가짜 서버(stdio · HTTP)에 실제로 연결 검사를 한다.
"""
from __future__ import annotations

import json
import os
import socket
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from procsvc import (agent_authoring, agent_authoring_api, agents_api, bpmn_import as B, config_bundle, flow_deploy, flows_api,
                     instance_mode, instances, mcp_registry, procdb)
from procsvc.agents_store import activity_capabilities, agent_settings
from procsvc.bpmn_store import FlowStore
from procsvc.definition_registry import validate_definition

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
from test_b2_mcp_registry import FAKE, SEED_MCP  # noqa: E402
from test_bpmn_import import BASE, LOOP, REDRAW, HUMAN_START, loop_mapping, redraw_mapping  # noqa: E402
from test_instances import ALERT, FakeHooks  # noqa: E402
from test_mcp_check import _Handler, _serve  # noqa: E402

KIM, CHOI, LEE = "user:kim-op", "user:choi-op", "user:lee-prod"
SKILL = "---\nname: cooler-check\ndescription: 쿨러 점검 순서\n---\n\n# 쿨러 점검\n\n1. 냉각 효율부터 본다.\n"
SEED_SKILL = "---\nname: fan-vibration-check\ndescription: 팬 진동 점검 순서\n---\n\n# 팬 진동 점검\n\n1. 진동 RMS 를 먼저 본다.\n"
TOKEN, BEARER = "tok-123456-secret", "abcdef1234567890"
NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)


def _closed_port() -> int:
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    return port


@pytest.fixture
def http():
    srv = _serve("json")
    yield f"http://127.0.0.1:{srv.server_port}/mcp"
    for q in list(_Handler.stream_queues.values()):
        q.put(None)
    srv.shutdown(); srv.server_close()


def _seed(repo):
    """seed.sql 모양의 기준: 기준 MCP 세 서버 · 기본 에이전트 · 시스템 수행자 · 역할 · 사람 · 업무분장 · 랩업 스킬(origin 없음 = 기준)."""
    repo.upsert_tenant({"id": "hyd", "name": "hyd", "mcp": deepcopy(SEED_MCP)})
    repo.upsert_user({"id": "sys:agent", "username": "AI 에이전트 (Claude Code)", "role": "agent", "is_agent": True, "agent_type": "agent",
                      "goal": "경보의 원인을 진단하고 조치 카드를 올린다", "tools": "neo4j,enterprise,hyd-dmn", "tenant_id": "hyd", "work_rules": "hyd-plant"})
    repo.upsert_user({"id": "sys:scada", "username": "SCADA", "role": "system", "is_agent": True, "agent_type": "system", "tenant_id": "hyd"})
    for uid, name in (("role:operator", "운전원"), ("role:prod-mgr", "생산관리자"), ("role:maint-mgr", "정비관리자"),
                      (KIM, "김운전"), (CHOI, "최운전"), (LEE, "이생산")):
        repo.upsert_user({"id": uid, "username": name, "is_agent": False, "tenant_id": "hyd"})
    for role, uid in (("role:operator", KIM), ("role:operator", CHOI), ("role:prod-mgr", LEE)):
        repo.set_role_member("hyd", role, uid, True)
    repo.put_skill({"skill_name": "fan-vibration-check", "description": "팬 진동 점검 순서", "content": SEED_SKILL})


@pytest.fixture
def env(monkeypatch):
    repo = procdb.MemoryRepo()
    _seed(repo)
    return _client(monkeypatch, repo)


def _client(monkeypatch, repo):
    hooks = FakeHooks()
    hooks.new_incident = lambda alert, **kw: {"id": "INC-1008-01"}                 # 2.2 정의는 recovery_policy 를 함께 넘긴다
    rt = instances.InstanceRuntime(repo, validate_definition(deepcopy(BASE)), hooks, time_scale=20.0)
    monkeypatch.setattr(instance_mode, "_runtime", rt)
    audits = []
    app = FastAPI()
    instance_mode.mount(app, "instance")
    agents_api.mount(app)
    agent_authoring_api.mount(app)
    mcp_registry.mount(app, runtime_factory=lambda: rt, audit=lambda *a: audits.append(a))
    flows_api.register(app, runtime_factory=lambda: rt, audit=lambda *a, **k: audits.append(a), base_loader=lambda _rt: deepcopy(BASE))
    config_bundle.register(app, runtime_factory=lambda: rt, audit=lambda *a, **k: audits.append(a), base_loader=lambda _rt: deepcopy(BASE))
    c = TestClient(app)
    c.rt, c.repo, c.audits = rt, repo, audits
    return c


def ok(r, code=200):
    assert r.status_code == code, r.text
    return r.json()


def build_student(c, http_url) -> dict:
    """학생 구성 한 벌: MCP 서버 2(stdio 비밀 환경변수 · HTTP 비밀 헤더) · 스킬 · 에이전트 2(새로 · 복제) · 업무분장 ·
    흐름 2(판본 2개 등록 + 초안만) · 단계 배정 2(학생 흐름 · 기준 흐름) · 배포."""
    ok(c.post("/api/mcp/servers", json={"name": "my-fake", "transport": "stdio", "command": sys.executable, "args": [FAKE],
                                         "env": {"FAKE_TOKEN": TOKEN, "LOG_LEVEL": "info"}, "description": "가짜 stdio"}), 201)
    ok(c.post("/api/mcp/servers", json={"name": "my-http", "transport": "streamable_http", "url": http_url,
                                         "headers": {"Authorization": f"Bearer {BEARER}", "X-Team": "a"}}), 201)
    ok(c.post("/api/skills", json={"skill_name": "cooler-check", "description": "", "content": SKILL}), 201)
    a1 = ok(c.post("/api/agents", json={"name": "쿨러 점검 에이전트", "role": "쿨러를 먼저 본다", "goal": "쿨러 원인 근거를 모은다",
                                        "persona": "짧게", "model": "claude-haiku-4-5", "tools": ["enterprise", "my-fake", "my-http"],
                                        "skills": ["fan-vibration-check"]}), 201)
    ok(c.post(f"/api/agents/{a1['id']}/skills", json={"skill_name": "cooler-check"}))       # 붙인 순서: 기본 스킬 → 내 스킬
    a2 = ok(c.post("/api/agents/sys:agent/clone", json={}), 201)
    ok(c.post("/api/role-members", json={"role_id": "role:maint-mgr", "user_id": KIM}), 201)
    ok(c.post("/api/flows/import", json={"xml": REDRAW, "file_name": "redraw.bpmn", "definition_id": "my_cooler"}))
    m = redraw_mapping(B.parse_bpmn(REDRAW))
    ok(c.post("/api/flows/my_cooler/register", json={"mapping": m}), 201)
    m2 = dict(deepcopy(m), name="내 쿨러 흐름")
    m2["start"] = dict(m2.get("start") or {}, kind="alert", patterns=["PUMP_LEAKAGE"])
    ok(c.post("/api/flows/my_cooler/register", json={"mapping": m2}), 201)
    ok(c.post("/api/flows/import", json={"xml": HUMAN_START, "file_name": "oil.bpmn", "definition_id": "oil_check"}))   # 초안만
    ok(c.put("/api/agent-assignments", json={"definition_id": "my_cooler", "activity_id": "Activity_0diag4n", "agent_id": a1["id"]}))
    ok(c.put("/api/agent-assignments", json={"definition_id": "anomaly_response", "activity_id": "task:diagnose", "agent_id": a2["id"]}))
    ok(c.post("/api/process/definitions/my_cooler/deploy", json={"version": "2", "by": "강사", "reason": "펌프는 내 흐름"}))
    return {"a1": a1["id"], "a2": a2["id"]}


AGENT_STEPS = ["task:diagnose", "task:candidates", "task:compliance", "task:rank"]


def state(c) -> dict:
    """비교할 상태: 에이전트 실행 설정(워커가 읽는 것) · 스킬 · MCP 서버와 게이트 · 업무분장 · 흐름 정의 · 초안 · 배정 · 배포 표."""
    rt, repo = c.rt, c.repo

    def settings(aid):
        out = {"base": agent_settings(repo, "hyd", aid)}
        out.update({a: agent_settings(repo, "hyd", aid, activity=activity_capabilities(rt.defn.raw, a)) for a in AGENT_STEPS})
        return {k: {"summary": v.summary(), "instructions": v.instructions(), "codex": v.instructions(".agents/skills"),
                    "profile": {x: y for x, y in v.profile.items() if x not in ("created_at", "updated_at")}} for k, v in out.items()}
    agents = sorted(u["id"] for u in repo.list_users(None, "hyd") if u.get("is_agent"))
    servers = {n: {**{k: v for k, v in e.items() if k != "hyd"},
                   "gate": {k: (e.get("hyd") or {}).get("gate", {}).get(k) for k in ("fingerprint", "read_tools", "blocked_tools")}}
               for n, e in mcp_registry.store_for(repo).servers("hyd").items()}
    store = FlowStore(repo, "hyd")
    routes = flow_deploy.routes(rt)
    for f in routes["flows"]:
        f.pop("deployed_at", None)
    return {"agents": {a: settings(a) for a in agents},
            "skills": [(s["skill_name"], s.get("description"), s.get("content"), agent_authoring.origin_of(s)) for s in repo.list_skills("hyd")],
            "mcp": json.loads(json.dumps(servers, sort_keys=True)),
            "members": sorted((m["role_id"], m["user_id"], agent_authoring.origin_of(m)) for m in repo.list_role_members("hyd")),
            "flows": [(v["id"], v["version"], repo.get_proc_def(v["id"], "hyd", version=v["version"])["definition"], store.bpmn_of(v["id"], v["version"]))
                      for v in store.versions()],
            "drafts": [(d["proc_def_id"], d.get("file_name"), d.get("mapping"), (store.get_draft(d["proc_def_id"]) or {}).get("bpmn")) for d in store.drafts()],
            "maps": sorted((m["proc_def_id"], m["activity_id"], m["agent_id"]) for m in repo.list_agent_map("hyd")),
            "routes": routes}


def base_state(c) -> dict:
    s = state(c)
    return {"agents": sorted(s["agents"]), "default": s["agents"]["sys:agent"], "skills": s["skills"], "mcp": sorted(s["mcp"]),
            "members": s["members"], "flows": s["flows"], "maps": s["maps"], "at_reference": s["routes"]["at_reference"]}


# ---------------------------------------------------------------- 같은 상태 · 두 번 가져오기
def test_export_reset_import_gives_the_same_state_twice(env, http):
    c = env
    ids = build_student(c, http)
    before = state(c)
    assert before["routes"]["routes"] and any(r["source"] == "내가 배포한 흐름" for r in before["routes"]["routes"])
    bundle = ok(c.get("/api/config/export"))
    assert bundle["format"] == "hyd-config-bundle" and bundle["format_version"] == 1 and bundle["created_at"].endswith("Z")
    s = bundle["summary"]
    assert (s["mcp_servers"], s["skills"], s["agents"], s["role_members"], s["flows"], s["flow_versions"], s["assignments"], s["deployments"]) \
        == (2, 1, 2, 1, 2, 2, 2, 1)
    assert s["secrets_needed"] == 2 and bundle["not_included"] == []

    # 하나의 되돌리기 → 기준 상태
    r = ok(c.post("/api/config/reset", json={"by": "학생"}))
    assert [x["step"] for x in r["steps"]] == ["deploy_reset", "flows_reset", "agents_reset", "mcp_reset", "ask_reset"]
    clean = base_state(c)
    assert clean["agents"] == ["sys:agent", "sys:scada"] and clean["mcp"] == ["enterprise", "hyd-dmn", "neo4j"]
    assert clean["flows"] == [] and clean["maps"] == [] and clean["at_reference"] is True
    assert clean["members"] == [("role:operator", CHOI, "seed"), ("role:operator", KIM, "seed"), ("role:prod-mgr", LEE, "seed")]
    assert clean["default"] == before["agents"]["sys:agent"]                       # 기본 에이전트 실행 설정은 그대로

    secrets = {"my-fake": {"env.FAKE_TOKEN": TOKEN}, "my-http": {"headers.Authorization": f"Bearer {BEARER}"}}
    out = ok(c.post("/api/config/import", json={"bundle": bundle, "secrets": secrets, "by": "학생"}))
    assert out["ok"] and out["verified"] and out["skipped"] == []
    assert [a["step"] for a in out["applied"]] == ["mcp", "skills", "agents", "role_members", "flows", "assignments", "deployments"]
    assert {a["step"]: a["count"] for a in out["applied"]} == {"mcp": 2, "skills": 1, "agents": 2, "role_members": 1, "flows": 2,
                                                              "assignments": 2, "deployments": 1}
    after = state(c)
    for key in before:
        assert after[key] == before[key], key
    assert ids["a1"] in after["agents"]                                            # 같은 id 로 돌아와 배정이 같은 에이전트를 가리킨다

    # 같은 파일을 한 번 더 → 같은 결과
    ok(c.post("/api/config/import", json={"bundle": bundle, "secrets": secrets}))
    again = state(c)
    for key in before:
        assert again[key] == before[key], key
    # 두 번째 내보내기 = 첫 내보내기(만든 시각만 다름)
    second = ok(c.get("/api/config/export"))
    assert {k: v for k, v in second.items() if k != "created_at"} == {k: v for k, v in bundle.items() if k != "created_at"}
    assert [a[2] for a in c.audits if str(a[2]).startswith("CONFIG_")] == ["CONFIG_RESET", "CONFIG_IMPORTED", "CONFIG_IMPORTED"]


def test_seed_and_secrets_are_not_in_the_file(env, http):
    c = env
    build_student(c, http)
    text = c.get("/api/config/export").text
    bundle = json.loads(text)
    content = bundle["content"]
    # 비밀값 없음 — 자리표시만
    assert TOKEN not in text and BEARER not in text
    fake = next(s for s in content["mcp_servers"] if s["name"] == "my-fake")
    web = next(s for s in content["mcp_servers"] if s["name"] == "my-http")
    assert fake["env"] == {"FAKE_TOKEN": "${HYD_SECRET:env.FAKE_TOKEN}", "LOG_LEVEL": "info"}
    assert web["headers"] == {"Authorization": "${HYD_SECRET:headers.Authorization}", "X-Team": "a"}
    assert [x["slot"] for x in fake["secrets"]] == ["env.FAKE_TOKEN"] and "hyd" not in fake and "gate" not in json.dumps(fake)
    # 기준 것 없음
    assert {s["name"] for s in content["mcp_servers"]} == {"my-fake", "my-http"}
    assert [s["skill_name"] for s in content["skills"]] == ["cooler-check"]
    assert not {"sys:agent", "sys:scada"} & {a["id"] for a in content["agents"]} and "AI 에이전트 (Claude Code)\"" not in text
    assert [(m["role_id"], m["user_id"]) for m in content["role_members"]] == [("role:maint-mgr", KIM)]
    assert {f["definition_id"] for f in content["flows"]} == {"my_cooler", "oil_check"}
    assert "anomaly_response" not in {f["definition_id"] for f in content["flows"]}
    assert content["deployments"] == {"flows": [{"definition_id": "my_cooler", "version": "2", "patterns": ["PUMP_LEAKAGE"]}], "reference": None}
    cooler = next(f for f in content["flows"] if f["definition_id"] == "my_cooler")
    assert [v["version"] for v in cooler["versions"]] == ["1", "2"] and cooler["versions"][0]["bpmn"] == REDRAW
    assert next(f for f in content["flows"] if f["definition_id"] == "oil_check")["versions"] == []


def test_breaking_secret_detection_is_caught(env, http, monkeypatch):
    """일부러 깨뜨림: 비밀값 판정을 끄면 위 시험의 '비밀값 없음' 단언이 잡는다(시험이 공허하지 않다)."""
    build_student(env, http)
    monkeypatch.setattr(config_bundle, "_secret_value", lambda k, v: False)
    text = env.get("/api/config/export").text
    assert TOKEN in text and BEARER in text


# ---------------------------------------------------------------- 잘못된 파일: 사유와 함께 거절, 아무것도 안 바뀜
def _bad(bundle, fn):
    b = deepcopy(bundle)
    fn(b)
    return b


BAD_CASES = [
    ("형식 이름", lambda b: b.update(format="something-else"), "출발본 형식이 아닙니다"),
    ("판수", lambda b: b.update(format_version=2), "판수 2"),
    ("내용 없음", lambda b: b.pop("content"), "내용(content)"),
    ("참조 없는 스킬", lambda b: b["content"]["agents"][0]["skills"].append("no-such-skill"), "참조 없는 스킬"),
    ("참조 없는 도구 서버", lambda b: b["content"]["agents"][0]["tools"].append("ghost-mcp"), "참조 없는 도구 서버"),
    ("참조 없는 에이전트", lambda b: b["content"]["assignments"][0].update(agent_id="agent:u-deadbeef"), "참조 없는 에이전트"),
    ("없는 흐름 판본 배포", lambda b: b["content"]["deployments"]["flows"][0].update(version="9"), "그 흐름 판본이 파일에 없습니다"),
    ("기본 에이전트 이름", lambda b: b["content"]["agents"][0].update(name="AI 에이전트 (Claude Code)"), "기본 에이전트와 이름이 같습니다"),
    ("기본 스킬 이름", lambda b: b["content"]["skills"][0].update(skill_name="fan-vibration-check"), "기본 스킬과 이름이 같습니다"),
    ("기준 서버 이름", lambda b: b["content"]["mcp_servers"][0].update(name="enterprise"), "기준(기본 제공) 서버 이름"),
    ("기준 흐름 id", lambda b: b["content"]["flows"][0].update(definition_id="anomaly_response"), "기준 흐름 id"),
    ("빈 스킬", lambda b: b["content"]["skills"][0].update(content="---\nname: cooler-check\n---\n"), "빈 스킬"),
    ("판본 번호 건너뜀", lambda b: b["content"]["flows"][0]["versions"][1].update(version="3"), "판본 번호가 이어지지 않습니다"),
    ("부품 빠짐", lambda b: b["content"]["flows"][0]["versions"][0]["mapping"]["tasks"].pop("Activity_0diag4n"), "사전 검사를 통과하지 못합니다"),
    ("정의가 다름", lambda b: b["content"]["flows"][0]["versions"][0].update(definition_sha256="0" * 64), "다시 만든 정의가 내보낼 때와 다릅니다"),
    ("사람 단계 배정", lambda b: b["content"]["assignments"][0].update(activity_id="Activity_0slct3h"), "에이전트가 맡는 단계가 아닙니다"),
    ("없는 역할", lambda b: b["content"]["role_members"][0].update(role_id="role:nobody"), "역할 'role:nobody'"),
    ("모르는 업무 규칙", lambda b: b["content"]["agents"][0].update(work_rules="meeting-room"), "업무 규칙 'meeting-room'이(가) 없습니다"),   # G9
]


@pytest.mark.parametrize("label,fn,needle", BAD_CASES, ids=[x[0] for x in BAD_CASES])
def test_bad_files_are_refused_with_reason_and_change_nothing(env, http, label, fn, needle):
    c = env
    build_student(c, http)
    bundle = ok(c.get("/api/config/export"))
    before = state(c)
    secrets = {"my-fake": {"env.FAKE_TOKEN": TOKEN}, "my-http": {"headers.Authorization": f"Bearer {BEARER}"}}
    r = c.post("/api/config/import", json={"bundle": _bad(bundle, fn), "secrets": secrets})
    assert r.status_code == 422, r.text
    assert needle in r.text, r.json()
    assert "failed_step" not in r.text, r.json()                                   # 적용 단계가 아니라 검사 단계에서 거절(G9 업무 규칙 키 포함)
    assert state(c) == before                                                      # 검증에서 거절 → 되돌리기도 하지 않았다


def test_missing_secret_asks_first_then_skips_only_that_server(env, http):
    c = env
    build_student(c, http)
    bundle = ok(c.get("/api/config/export"))
    ok(c.post("/api/config/reset", json={}))
    clean = base_state(c)
    r = c.post("/api/config/import", json={"bundle": bundle, "secrets": {"my-http": {"headers.Authorization": f"Bearer {BEARER}"}}})
    assert r.status_code == 422
    d = r.json()["detail"]
    assert "비밀값이 필요한 MCP 서버" in d["reason"] and "환경변수 FAKE_TOKEN" in d["reason"]
    assert d["needs_secrets"] == [{"server": "my-fake", "slots": [{"slot": "env.FAKE_TOKEN", "label": "환경변수 FAKE_TOKEN"}]}]
    assert base_state(c) == clean                                                  # 입력을 요구할 뿐 아무것도 바꾸지 않음
    out = ok(c.post("/api/config/import", json={"bundle": bundle, "skip_missing_secrets": True,
                                                 "secrets": {"my-http": {"headers.Authorization": f"Bearer {BEARER}"}}}))
    assert out["verified"]
    assert [s["what"] for s in out["skipped"]] == ["MCP 서버 'my-fake'", "에이전트 '쿨러 점검 에이전트'의 도구 서버 my-fake"]
    assert "비밀값(환경변수 FAKE_TOKEN)을 넣지 않아" in out["skipped"][0]["reason"]
    servers = mcp_registry.store_for(c.repo).servers("hyd")
    assert "my-fake" not in servers and servers["my-http"]["headers"]["Authorization"] == f"Bearer {BEARER}"
    a1 = next(u for u in c.repo.list_users(None, "hyd") if u.get("username") == "쿨러 점검 에이전트")
    assert a1["tools"] == "enterprise,my-http"


def test_failure_while_applying_reports_where_and_restores_the_previous_state(env, http):
    c = env
    build_student(c, http)
    bundle = ok(c.get("/api/config/export"))
    before = state(c)
    broken = deepcopy(bundle)
    web = next(s for s in broken["content"]["mcp_servers"] if s["name"] == "my-http")
    web["url"] = f"http://127.0.0.1:{_closed_port()}/mcp"                          # 형식은 맞고 연결만 안 되는 주소
    r = c.post("/api/config/import", json={"bundle": broken, "secrets": {"my-fake": {"env.FAKE_TOKEN": TOKEN},
                                                                         "my-http": {"headers.Authorization": f"Bearer {BEARER}"}}})
    assert r.status_code == 422, r.text
    d = r.json()["detail"]
    assert d["failed_step"] == "mcp" and "'MCP 서버' 단계에서 실패" in d["reason"] and "연결 검사 실패" in d["reason"]
    assert d["partially_applied"] == [next(i for i in d["partially_applied"] if i.startswith("my-fake"))]   # my-fake 는 들어갔고 my-http 에서 멈춤
    assert [s["step"] for s in d["not_applied"]] == ["skills", "agents", "role_members", "flows", "assignments", "deployments"]
    assert d["rolled_back"] is True and d["rollback_error"] is None and "불러오기 전 상태로 되돌려 놓았습니다" in d["reason"]
    assert state(c) == before
    assert [a[2] for a in c.audits if str(a[2]).startswith("CONFIG_")] == ["CONFIG_IMPORT_FAILED"]


def test_breaking_an_apply_step_is_caught_by_the_final_comparison(env, http, monkeypatch):
    """일부러 깨뜨림: 업무분장 적용을 조용히 건너뛰게 하면 '적용 뒤 대조'가 잡고 이전 상태로 되돌린다(빈 성공 금지)."""
    c = env
    build_student(c, http)
    bundle = ok(c.get("/api/config/export"))
    before = state(c)
    monkeypatch.setattr(agent_authoring, "add_member", lambda repo, t, r, u: {"role_id": r, "members": []})
    r = c.post("/api/config/import", json={"bundle": bundle, "secrets": {"my-fake": {"env.FAKE_TOKEN": TOKEN},
                                                                         "my-http": {"headers.Authorization": f"Bearer {BEARER}"}}})
    assert r.status_code == 422, r.text
    d = r.json()["detail"]
    assert d["failed_step"] == "verify" and "적용한 뒤 다시 읽은 구성이 파일과 다릅니다 — 업무분장" in d["reason"]
    # 되돌리기도 같은(깨진) 함수로 업무분장을 넣으므로 이전 상태를 다 세우지 못한다 — 그 사실을 숨기지 않는다
    assert d["rolled_back"] is False and "업무분장" in d["rollback_error"]
    monkeypatch.undo()
    s = state(c)
    assert {k: v for k, v in s.items() if k != "members"} == {k: v for k, v in before.items() if k != "members"}


# ---------------------------------------------------------------- 진행 중 처리 건 → reset 409, 아무것도 안 지움
def _register_loop(c):
    ok(c.post("/api/flows/import", json={"xml": LOOP, "definition_id": "oil_loop"}))
    ok(c.post("/api/flows/oil_loop/register", json={"mapping": loop_mapping(B.parse_bpmn(LOOP))}), 201)
    return c.rt.start_definition("oil_loop", "1", "oil-1", values={"sample_id": "S-1"})


def test_reset_with_a_running_student_flow_is_refused_and_deletes_nothing(env, http):
    c = env
    build_student(c, http)
    inst = _register_loop(c)
    before = state(c)
    r = c.post("/api/config/reset", json={})
    assert r.status_code == 409
    d = r.json()["detail"]
    assert "아무것도 바꾸지 않았습니다" in d["reason"] and [b["step"] for b in d["blocking"]] == ["flows_reset"]
    assert d["blocking"][0]["items"][0]["proc_inst_id"] == inst["proc_inst_id"]
    assert state(c) == before                                                      # 배포도 그대로(B4 되돌리기도 하지 않음)
    bundle = ok(c.get("/api/config/export"))
    r = c.post("/api/config/import", json={"bundle": bundle, "skip_missing_secrets": True})
    assert r.status_code == 409 and state(c) == before                             # 불러오기도 같은 조건으로 거절
    # 끝내면 된다
    w = next(w for w in c.repo.list_workitems(proc_inst_id=inst["proc_inst_id"]) if w["status"] == "IN_PROGRESS")
    c.rt.submit(w["id"], {"iso_code": 10})
    ok(c.post("/api/config/reset", json={}))
    assert base_state(c)["flows"] == []


def test_reset_with_a_student_agent_at_work_is_refused(env, http):
    c = env
    build_student(c, http)
    ok(c.post("/api/config/reset", json={}))                                        # 학생 흐름 배포 없이 배정만 다시 만든다
    a2 = ok(c.post("/api/agents/sys:agent/clone", json={}), 201)
    ok(c.put("/api/agent-assignments", json={"definition_id": "anomaly_response", "activity_id": "task:diagnose", "agent_id": a2["id"]}))
    inst = c.rt.on_alert_raise(dict(ALERT), NOW)
    (wi,) = c.repo.fetch_pending_task("cliagents", "w", proc_inst_id=inst["proc_inst_id"])    # 워커가 집음(STARTED)
    assert wi["user_id"] == a2["id"]
    before = state(c)
    r = c.post("/api/config/reset", json={})
    assert r.status_code == 409 and [b["step"] for b in r.json()["detail"]["blocking"]] == ["agents_reset"]
    assert state(c) == before


def test_breaking_the_precheck_lets_reset_half_delete(env, http, monkeypatch):
    """일부러 깨뜨림: 사전 점검을 끄면 B4 배포 되돌리기가 먼저 일어난 뒤 B3 에서 409 — 반쯤 지운 상태가 된다(그래서 점검이 먼저다)."""
    c = env
    build_student(c, http)
    _register_loop(c)
    monkeypatch.setattr(config_bundle, "blocking", lambda rt: [])
    r = c.post("/api/config/reset", json={})
    assert r.status_code == 409
    d = r.json()["detail"]
    assert d["failed_step"] == "flows_reset" and [x["step"] for x in d["done"]] == ["deploy_reset"]
    assert flow_deploy.routes(c.rt)["at_reference"] is True                        # 배포는 이미 지워졌다 — 사전 점검이 막아야 하는 상태


def test_needs_instance_mode():
    app = FastAPI()
    config_bundle.register(app, runtime_factory=lambda: None, base_loader=lambda _rt: BASE)
    c = TestClient(app)
    assert c.get("/api/config/export").status_code == 503
    assert c.post("/api/config/reset", json={}).status_code == 503


def test_import_accepts_the_raw_file_and_an_empty_starter(env):
    """빈 출발본(학생 것 없음) = 기준으로 되돌리기와 같다. 파일을 본문 그대로 보내도 된다."""
    c = env
    empty = ok(c.get("/api/config/export"))
    assert empty["summary"]["agents"] == 0 and all(not v for k, v in empty["content"].items() if k != "deployments")
    ok(c.post("/api/skills", json={"skill_name": "cooler-check", "description": "", "content": SKILL}), 201)
    out = ok(c.post("/api/config/import", json=empty))
    assert out["verified"] and sum(a["count"] for a in out["applied"]) == 0
    assert [s["skill_name"] for s in c.repo.list_skills("hyd")] == ["fan-vibration-check"]


def test_portal_script_parses():
    import shutil
    import subprocess
    node = shutil.which("node")
    if not node:
        pytest.skip("node 없음")
    subprocess.run([node, "--check", str(ROOT / "it/portal/www/configBundle.js")], check=True)


# ---------------------------------------------------------------- 실제 PostgreSQL(마이그레이션 전부 + seed.sql 적용한 버릴 DB)
PG_DSN = os.getenv("HYD_B6_PG_DSN")


@pytest.mark.skipif(not PG_DSN, reason="HYD_B6_PG_DSN 이 없으면 PostgreSQL 왕복은 건너뛴다 (마이그레이션 전부 + seed.sql 적용한 버릴 DB)")
def test_pg_export_reset_import_roundtrip(monkeypatch, http):
    repo = procdb.PgRepo(PG_DSN)
    with repo._conn() as cx:     # 랩업 SQL 로 넣은 스킬처럼(origin 없음 = 기준)
        cx.execute("insert into tenant_skills (tenant_id, skill_name, description, content) values ('hyd', 'fan-vibration-check', %s, %s) "
                   "on conflict do nothing", ("팬 진동 점검 순서", SEED_SKILL))
        seed_rows = cx.execute("select id, origin from users order by id").fetchall()
        seed_mcp = cx.execute("select mcp from tenants where id='hyd'").fetchone()["mcp"]
    c = _client(monkeypatch, repo)
    try:
        build_student(c, http)
        before = state(c)
        bundle = ok(c.get("/api/config/export"))
        assert TOKEN not in json.dumps(bundle) and BEARER not in json.dumps(bundle)
        ok(c.post("/api/config/reset", json={}))
        with repo._conn() as cx:
            assert cx.execute("select id, origin from users order by id").fetchall() == seed_rows
            assert cx.execute("select mcp from tenants where id='hyd'").fetchone()["mcp"] == seed_mcp
            assert cx.execute("select count(*) n from proc_def_version where origin='user'").fetchone()["n"] == 0
        secrets = {"my-fake": {"env.FAKE_TOKEN": TOKEN}, "my-http": {"headers.Authorization": f"Bearer {BEARER}"}}
        for _ in range(2):                                                         # 두 번 가져와도 같은 결과
            out = ok(c.post("/api/config/import", json={"bundle": bundle, "secrets": secrets}))
            assert out["verified"]
            after = state(c)
            for key in before:
                assert after[key] == before[key], key
        with repo._conn() as cx:
            head = cx.execute("select prod_version, origin, bpmn = %s as same from proc_def where id='my_cooler'", (REDRAW,)).fetchone()
            assert dict(head) == {"prod_version": "2", "origin": "user", "same": True}
    finally:
        ok(c.post("/api/config/reset", json={}))
        with repo._conn() as cx:
            cx.execute("delete from tenant_skills where skill_name='fan-vibration-check'")
