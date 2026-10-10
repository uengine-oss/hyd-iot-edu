"""U2 (TODO A2): agent settings and skills — one source read by the portal API and by the worker's real run.

What a student adds in the wrap-up (a users row, a tenant_skills row, an agent_skills row) must (1) appear on the read-only
portal API and (2) change what the worker actually runs with: the prompt's profile section, the SKILL.md file in the run's
workspace, the model, and only the agent's MCP servers. Broken on purpose: a stale skill, a skill name without a body,
servers that do not overlap, an unknown agent id.
"""
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from procsvc import agents_api, agents_store, engine, instance_mode, instances, procdb
from procsvc.agents_store import agent_settings, skill_markdown, skill_title
from worker import bridge, workspace
from worker.runner import Runner
from worker.settings import Settings, run_allowed_tools

ROOT = Path(__file__).resolve().parents[1]
DEF_PATH = ROOT / "it" / "process" / "definitions" / "anomaly_response.json"
FORM = {"id": "diagnose", "fields_json": [{"key": "cause", "type": "text", "text": "원인"}, {"key": "failure_mode", "type": "text", "text": "고장 유형"},
                                         {"key": "guide_card", "type": "object", "text": "카드"}]}
MCP = {"mcpServers": {"neo4j": {"command": "uvx", "args": ["mcp-neo4j-cypher@0.4.1"]},
                      "enterprise": {"type": "url", "url": "http://enterprise-mcp:8199/mcp", "transport": "streamable_http"},
                      "hyd-dmn": {"type": "url", "url": "http://dmn-mcp:8198/mcp", "transport": "streamable_http"},
                      "fan-vib": {"type": "url", "url": "http://fan-vib:9000/mcp", "transport": "streamable_http", "description": "팬 진동 조회"}}}
# B2: a student's server runs only with the stamp of a passed connection check (read-only tools) made for its current config
MCP["mcpServers"]["fan-vib"]["hyd"] = {"origin": "user", "gate": {"fingerprint": bridge.config_fingerprint(MCP["mcpServers"]["fan-vib"]),
                                                                  "read_tools": ["vibration_rms"], "blocked_tools": ["reset_sensor"]}}
SKILL_MD = "---\nname: fan-vibration-check\ndescription: 팬 진동 점검 순서\n---\n\n# 팬 진동 점검\n\n1. 진동 RMS 를 먼저 본다.\n"
ANSWER = '{"cause": "cause:cooler-fin-fouling", "failure_mode": "fm:cooling-loss", "guide_card": {"recommended": []}}'


def _repo(**agent):
    repo = procdb.MemoryRepo()
    defn = engine.Definition.load(DEF_PATH)
    repo.upsert_proc_def(defn.raw)
    repo.upsert_form(FORM)
    repo.upsert_tenant({"id": "hyd", "name": "hyd", "mcp": MCP})
    repo.upsert_user({"id": "sys:agent", "username": "AI 에이전트", "role": "agent", "is_agent": True, "agent_type": "agent",
                      "goal": "경보 원인 진단", "tools": "neo4j,enterprise,hyd-dmn", **agent})
    repo.upsert_user({"id": "sys:scada", "username": "SCADA", "role": "system", "is_agent": True, "agent_type": "system"})
    repo.upsert_user({"id": "role:operator", "username": "운전원", "is_agent": False})
    return repo, defn


def _start(repo, defn):
    from datetime import datetime, timezone
    now = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
    inst = engine.new_instance(defn, {"asset": "HYD-01", "pattern": "COOLER_DEGRADATION", "alert": {"alertId": "A"}, "incident": "INC-1"}, now=now)
    adv = engine.start(defn, inst, now=now)
    repo.insert_instance(inst)
    repo.insert_workitems(adv.created)
    repo.update_instance(inst)
    return inst


def _run(tmp_path, repo, cli="claude-code"):
    reqs = []

    def fake(provider, request, env):
        from cliagents import ExecEvent, ExecEventKind
        reqs.append(request)
        yield ExecEvent(kind=ExecEventKind.RUN_START, text="m", session_id="s1")
        yield ExecEvent(kind=ExecEventKind.RESULT, text=ANSWER, session_id="s1")
    settings = Settings(workspace_root=tmp_path, schema_prompt_path=tmp_path / "none.md", consumer="t:1", cancel_check_every_s=0, cli_agent=cli)
    runner = Runner(settings, repo, exec_fn=fake, schema_prompt="# s", resolve_provider=lambda pid: object())
    assert runner.poll_once() == 1
    row = next(w for w in repo.list_workitems(limit=None) if w["activity_id"] == "task:diagnose")
    return reqs[0], workspace.for_run(tmp_path, row["id"], tenant_id="hyd"), row


def _prompt_text(request, ws):
    text = request.prompt
    if "input/prompt.md" in text or len(text) < 400:      # long prompts are delivered as a file (A119 _deliver_prompt)
        for p in ws.path.rglob("prompt*.md"):
            text += p.read_text(encoding="utf-8")
    return text


# ---------------------------------------------------------------- the one read function
def test_agent_settings_reads_model_tools_and_skills_from_the_one_source():
    repo, _ = _repo(model="claude-sonnet-4-6", persona="근거부터 말한다")
    repo.put_skill({"skill_name": "fan-vibration-check", "description": "팬 진동 점검 순서", "content": SKILL_MD})
    repo.attach_skill("sys:agent", "fan-vibration-check")
    s = agent_settings(repo, "hyd", "sys:agent")
    assert (s.model, s.model_source) == ("claude-sonnet-4-6", "agent")
    assert (s.tools, s.tools_source) == (["neo4j", "enterprise", "hyd-dmn"], "agent")
    assert s.skill_names == ["fan-vibration-check"] and s.missing_skills == []
    text = s.instructions()
    assert "- 목표: 경보 원인 진단" in text and "- 성격·말투: 근거부터 말한다" in text and "- 역할: AI 에이전트" in text
    assert "`.claude/skills/fan-vibration-check/SKILL.md`" in text and ".agents/skills/fan-vibration-check" in s.instructions(".agents/skills")
    # the activity's explicit choices: its model wins, its tools narrow the agent's, its skills are added (missing ones named)
    caps = {"agent_config": {"agent_model": "o4-mini"}, "tools": ["enterprise", "fan-vib"], "skills": ["no-such-skill"]}
    s = agent_settings(repo, "hyd", "sys:agent", activity=caps)
    assert (s.model, s.model_source) == ("o4-mini", "activity")
    assert (s.tools, s.tools_source) == (["enterprise"], "agent+activity")
    assert s.skill_names == ["fan-vibration-check"] and s.missing_skills == ["no-such-skill"]
    assert agent_settings(repo, "hyd", "sys:agent", activity={"tools": ["fan-vib"]}).tools == []        # no overlap: no server, not all
    assert agent_settings(repo, "hyd", None, activity={"tools": ["fan-vib"]}).tools == ["fan-vib"]
    nothing = agent_settings(repo, "hyd", None)
    assert nothing.tools is None and nothing.model is None and nothing.instructions() == ""
    for bad in ("agent:nobody", "role:operator"):
        with pytest.raises(LookupError):
            agent_settings(repo, "hyd", bad)


def test_skill_file_keeps_a_written_frontmatter_and_gives_a_bare_body_one():
    assert skill_markdown({"skill_name": "fan-vibration-check", "content": SKILL_MD}) == SKILL_MD
    bare = skill_markdown({"skill_name": "x-y", "description": "한 줄\n설명", "content": "# 제목\n본문"})
    assert bare.startswith("---\nname: x-y\ndescription: 한 줄 설명\n---\n\n# 제목") and bare.endswith("본문\n")
    assert skill_title({"skill_name": "fan-vibration-check", "content": SKILL_MD}) == "팬 진동 점검"
    assert skill_title({"skill_name": "x", "description": "설명만", "content": "본문"}) == "설명만"
    repo = procdb.MemoryRepo()
    with pytest.raises(ValueError):
        repo.put_skill({"skill_name": "Fan Check", "content": "x"})          # the migration's name check
    with pytest.raises(ValueError):
        repo.attach_skill("sys:agent", "not-stored")                          # the agent_skills → tenant_skills foreign key


# ---------------------------------------------------------------- the worker's real run
def test_worker_runs_with_the_agents_profile_skill_model_and_servers(tmp_path):
    repo, defn = _repo(model="claude-sonnet-4-6", persona="침착하게 근거부터 말한다", tools="enterprise,fan-vib")
    repo.put_skill({"skill_name": "fan-vibration-check", "description": "팬 진동 점검 순서", "content": SKILL_MD})
    repo.attach_skill("sys:agent", "fan-vibration-check")
    _start(repo, defn)
    request, ws, row = _run(tmp_path, repo)
    assert request.model == "claude-sonnet-4-6"
    text = _prompt_text(request, ws)
    assert "## 에이전트 프로필" in text and "침착하게 근거부터 말한다" in text and ".claude/skills/fan-vibration-check/SKILL.md" in text
    skill = ws.path / ".claude" / "skills" / "fan-vibration-check" / "SKILL.md"
    assert skill.read_text(encoding="utf-8") == SKILL_MD
    mcp = json.loads((ws.path / ".mcp.json").read_text(encoding="utf-8"))
    assert sorted(mcp["mcpServers"]) == ["enterprise", "fan-vib"]                 # only the agent's servers
    allowed = request.extra_args[request.extra_args.index("--allowedTools") + 1].split(",")
    assert "mcp__fan-vib__vibration_rms" in allowed and "mcp__fan-vib__*" not in allowed and "mcp__neo4j__write_neo4j_cypher" not in allowed
    assert request.extra_args[request.extra_args.index("--disallowedTools") + 1] == "mcp__fan-vib__reset_sensor"    # B2: write tool denied
    task = json.loads((ws.context_dir / "task.json").read_text(encoding="utf-8"))
    assert task["agent"]["skills"] == ["fan-vibration-check"] and task["agent"]["tools"] == ["enterprise", "fan-vib"]
    assert repo.get_workitem(row["id"])["status"] in ("SUBMITTED", "DONE")


def test_without_a_profile_change_the_run_keeps_every_server_and_no_skill_folder(tmp_path):
    repo, defn = _repo(tools=None)
    _start(repo, defn)
    request, ws, _ = _run(tmp_path, repo)
    assert sorted(json.loads((ws.path / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]) == sorted(MCP["mcpServers"])
    assert not (ws.path / ".claude" / "skills").exists() and request.model is None
    assert "## 배정된 스킬" not in _prompt_text(request, ws)


def test_codex_gets_the_skill_in_its_own_folder(tmp_path):
    repo, defn = _repo()
    repo.put_skill({"skill_name": "fan-vibration-check", "description": "팬 진동 점검 순서", "content": SKILL_MD})
    repo.attach_skill("sys:agent", "fan-vibration-check")
    _start(repo, defn)
    request, ws, _ = _run(tmp_path, repo, cli="codex")
    assert (ws.path / ".agents" / "skills" / "fan-vibration-check" / "SKILL.md").exists()
    assert ".agents/skills/fan-vibration-check/SKILL.md" in request.prompt


def test_a_skill_from_an_earlier_attempt_does_not_stay_in_the_workspace(tmp_path):
    ws = workspace.for_run(tmp_path, "rerun")
    first = workspace.provision(ws, agent_id="claude-code", constitution="# 규칙", schema_prompt="s", task={"id": "t"},
                                skills=[{"skill_name": "old-skill", "content": "# 옛 절차"}])
    assert first == [".claude/skills/old-skill/SKILL.md"]
    assert workspace.provision(ws, agent_id="claude-code", constitution="# 규칙", schema_prompt="s", task={"id": "t"}, skills=[]) == []
    assert not (ws.path / ".claude" / "skills" / "old-skill").exists()


def test_a_named_skill_without_a_body_is_said_out_loud(tmp_path, monkeypatch):
    from worker import runner as runner_mod
    repo, defn = _repo()
    monkeypatch.setattr(runner_mod.context, "activity_capabilities", lambda d, a: {"agent_config": {}, "skills": ["not-written-yet"], "tools": []})
    _start(repo, defn)
    _, _, row = _run(tmp_path, repo)
    notices = [e for e in repo.list_events(proc_inst_id=row["proc_inst_id"]) if (e.get("data") or {}).get("type") == "notice"]
    assert any("not-written-yet" in str(e["data"].get("content")) for e in notices)


def test_allowed_tools_open_only_servers_the_default_does_not_name():
    base = ["mcp__neo4j__read_neo4j_cypher", "mcp__enterprise__*", "Read"]
    # B2: only the read-only tools the connection check stamped, never mcp__fan-vib__* (that would pre-approve its write tools)
    assert run_allowed_tools(base, ["neo4j", "enterprise", "fan-vib"], {"fan-vib": ["vibration_rms"]}) == base + ["mcp__fan-vib__vibration_rms"]
    assert run_allowed_tools(base, ["neo4j", "enterprise", "fan-vib"]) == base               # no stamp → nothing pre-approved
    assert run_allowed_tools(base, []) == base


# ---------------------------------------------------------------- the portal's read-only API
@pytest.fixture
def api(monkeypatch):
    repo, defn = _repo(persona="근거부터 말한다")
    rt = instances.InstanceRuntime(repo, defn, instances.Hooks())
    monkeypatch.setattr(instance_mode, "_runtime", rt)
    app = FastAPI()
    instance_mode.mount(app, "instance")
    agents_api.mount(app)
    return TestClient(app), repo


def test_portal_api_shows_what_the_wrap_up_added_and_writes_nothing(api):
    client, repo = api
    assert client.get("/api/skills").json() == []
    # the wrap-up: a new agent (users row), a skill and its attachment — the next request shows them
    repo.upsert_user({"id": "agent:fan-check", "username": "팬 진동 점검 에이전트", "role": "팬 진동으로 원인을 좁힌다", "is_agent": True,
                      "agent_type": "agent", "goal": "팬 진동 근거를 모은다", "tools": "fan-vib,ghost-server", "model": "claude-haiku-4-5"})
    repo.put_skill({"skill_name": "fan-vibration-check", "description": "팬 진동 점검 순서", "content": SKILL_MD})
    repo.attach_skill("agent:fan-check", "fan-vibration-check")
    cards = client.get("/api/agents").json()
    assert [c["kind"] for c in cards][:2] == ["agent", "agent"] and cards[-1]["kind"] == "system"
    default = next(c for c in cards if c["id"] == "sys:agent")
    assert [s["activity_id"] for s in default["steps"] if s["agent"]] == ["task:diagnose", "task:candidates", "task:compliance", "task:rank"]
    scada = next(c for c in cards if c["id"] == "sys:scada")
    assert [s["activity_id"] for s in scada["steps"]] == ["task:command"] and not scada["steps"][0]["agent"]
    new = client.get("/api/agents/agent:fan-check").json()
    assert new["steps"] == [] and new["run"]["steps"] == []                     # BPMN is fixed: a new agent takes no step by itself
    assert [(t["name"], t["registered"]) for t in new["tools"]] == [("fan-vib", True), ("ghost-server", False)]
    assert new["tools"][0]["description"] == "팬 진동 조회"
    assert new["skills"] == [{"skill_name": "fan-vibration-check", "found": True, "title": "팬 진동 점검", "description": "팬 진동 점검 순서"}]
    assert new["run"]["settings"]["model"] == "claude-haiku-4-5" and "fan-vibration-check/SKILL.md" in new["run"]["instructions"]
    detail = client.get("/api/agents/sys:agent").json()
    assert detail["persona"] == "근거부터 말한다" and len(detail["run"]["steps"]) == 4
    assert detail["run"]["steps"][0]["settings"]["tools"] == ["neo4j", "enterprise", "hyd-dmn"]
    skills = client.get("/api/skills").json()
    assert skills[0]["title"] == "팬 진동 점검" and skills[0]["agents"] == [{"id": "agent:fan-check", "name": "팬 진동 점검 에이전트"}]
    one = client.get("/api/skills/fan-vibration-check").json()
    assert one["content"] == SKILL_MD and one["agents"][0]["name"] == "팬 진동 점검 에이전트"
    assert client.get("/api/skills/nope").status_code == 404 and client.get("/api/agents/role:operator").status_code == 404
    # agents_api itself only reads (B1's writes live in agent_authoring_api — tests/test_b1_agent_authoring.py); no LLM draft route
    for method, url in (("post", "/api/agents"), ("put", "/api/agents/sys:agent"), ("delete", "/api/agents/sys:agent"),
                        ("post", "/api/skills"), ("put", "/api/skills/fan-vibration-check"), ("delete", "/api/skills/fan-vibration-check"),
                        ("post", "/api/agents/draft"), ("put", "/api/agent-bindings")):
        assert client.request(method.upper(), url, json={}).status_code in (404, 405), (method, url)


def test_portal_api_says_why_in_legacy_mode(monkeypatch):
    monkeypatch.setattr(instance_mode, "_runtime", None)
    app = FastAPI()
    agents_api.mount(app)
    assert TestClient(app).get("/api/agents").status_code == 409
