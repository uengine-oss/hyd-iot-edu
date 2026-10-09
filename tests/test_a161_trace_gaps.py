"""A161 처리 기록 블랙박스 넷 — the case record must be able to show every step.

G1 the skills a run had (name · content hash · source) and the skill files the agent actually opened;
G2 a tool result too large for an events row (Claude Code's "exceeds maximum allowed tokens … saved to <file>", or the
   worker's 4,000-character preview) is stored whole and the row points at it;
G3 the recovery tag's values during the re-observation window are kept on the Incident (not only the last value);
G4 /api/events pages backwards with a keyset cursor, the default answer unchanged.
Broken on purpose: a skill path outside the provided set, a CLI file path outside tool-results, a repo that cannot store,
an unknown cursor, a series read that fails.
"""
import hashlib
import json
from datetime import timedelta

import pytest
from cliagents import ExecEvent, ExecEventKind
from fastapi import FastAPI
from fastapi.testclient import TestClient

from procsvc import engine, instance_mode, instances, machine, reobs_series
from worker import events as ui_events, payloads
from worker.runner import Runner
from worker.settings import Settings

from test_u2_agents_skills import ANSWER, SKILL_MD, _repo as skill_repo, _start as skill_start
from test_c2_execution import world, run_maintenance, _row, NOW  # noqa: F401  (world 는 fixture)


def _runner(tmp_path, repo, events_fn):
    def fake(provider, request, env):
        yield ExecEvent(kind=ExecEventKind.RUN_START, text="m", session_id="s1")
        yield from events_fn(request)
        yield ExecEvent(kind=ExecEventKind.RESULT, text=ANSWER, session_id="s1")
    settings = Settings(workspace_root=tmp_path, schema_prompt_path=tmp_path / "none.md", consumer="t:1", cancel_check_every_s=0)
    return Runner(settings, repo, exec_fn=fake, schema_prompt="# s", resolve_provider=lambda pid: object())


def _events(repo, **kw):
    return [e for e in repo.events if all(e.get(k) == v for k, v in kw.items())]


# ================================================================ G1 skills
def test_a_run_records_the_skills_it_had_and_the_skill_files_it_read(tmp_path):
    repo, defn = skill_repo()
    repo.put_skill({"skill_name": "fan-vibration-check", "description": "팬 진동 점검 순서", "content": SKILL_MD})
    repo.attach_skill("sys:agent", "fan-vibration-check")
    skill_start(repo, defn)

    def calls(request):
        path = request.workdir + "/.claude/skills/fan-vibration-check/SKILL.md"
        yield ExecEvent(kind=ExecEventKind.TOOL_START, tool="Read", tool_input={"file_path": path}, tool_use_id="r1", session_id="s1")
        yield ExecEvent(kind=ExecEventKind.TOOL_END, tool="Read", text=SKILL_MD, tool_use_id="r1", session_id="s1")
        yield ExecEvent(kind=ExecEventKind.TOOL_START, tool="Read", tool_input={"file_path": path}, tool_use_id="r2", session_id="s1")  # same file again
        yield ExecEvent(kind=ExecEventKind.TOOL_START, tool="Skill", tool_input={"skill": "fan-vibration-check"}, tool_use_id="k1", session_id="s1")
        yield ExecEvent(kind=ExecEventKind.TOOL_START, tool="Bash", tool_input={"command": "cat .claude/skills/someone-else/notes.md"},
                        tool_use_id="b1", session_id="s1")
    assert _runner(tmp_path, repo, calls).poll_once() == 1

    sha = hashlib.sha256(SKILL_MD.encode("utf-8")).hexdigest()
    started = _events(repo, event_type="task_started")[0]["data"]
    assert started["skills"][0] | {"updated_at": None} == {
        "name": "fan-vibration-check", "path": ".claude/skills/fan-vibration-check/SKILL.md", "sha256": sha, "version": sha[:12],
        "chars": len(SKILL_MD), "description": "팬 진동 점검 순서", "source": "agent", "updated_at": None}
    assert started["skills_missing"] == []
    provided = [e["data"] for e in _events(repo, event_type="task_working") if e["data"].get("type") == "skills_provided"]
    assert len(provided) == 1 and provided[0]["cli"] == "claude-code" and provided[0]["skills"][0]["sha256"] == sha
    assert "fan-vibration-check" in provided[0]["content"]

    used = [e["data"] for e in _events(repo, event_type="task_working") if e["data"].get("type") == "skill_used"]
    assert [(u["skill"], u["file"], u["via"], u["known"]) for u in used] == [
        ("fan-vibration-check", "SKILL.md", "Read", True),          # the repeat read of the same file is not recorded twice
        ("someone-else", "notes.md", "Bash", False)]                # a path outside the provided set is still said
    assert used[0]["sha256"] == sha and used[0]["source"] == "agent" and used[0]["tool_use_id"] == "r1"


def test_a_run_without_skills_says_so_on_task_started_and_adds_no_row(tmp_path):
    repo, defn = skill_repo(tools=None)
    skill_start(repo, defn)
    assert _runner(tmp_path, repo, lambda request: iter(())).poll_once() == 1
    started = _events(repo, event_type="task_started")[0]["data"]
    assert started["skills"] == [] and started["skills_missing"] == []
    assert not [e for e in repo.events if e["data"].get("type") in ("skills_provided", "skill_used")]


def test_a_missing_skill_body_is_named_in_the_skills_row():
    ev = ui_events.skills_provided([], cli="codex", missing=["ghost"])
    assert ev.as_dict()["type"] == "skills_provided" and ev.data["missing"] == ["ghost"] and "ghost" in ev.data["content"]


def test_codex_shell_reads_and_windows_paths_are_recognised():
    reads = ui_events.SkillReads([{"name": "pm-check", "sha256": "x" * 64, "version": "x" * 12, "source": "activity"}])
    out = reads.on_tool_start(ExecEvent(kind=ExecEventKind.TOOL_START, tool="shell",
                                        tool_input={"command": ["bash", "-lc", "sed -n 1,80p .agents/skills/pm-check/SKILL.md"]}))
    win = reads.on_tool_start(ExecEvent(kind=ExecEventKind.TOOL_START, tool="Read",
                                        tool_input={"file_path": "C:\\work\\run\\.claude\\skills\\pm-check\\refs\\a.md"}))
    assert [(u.data["skill"], u.data["file"], u.data["known"]) for u in out + win] == [("pm-check", "SKILL.md", True), ("pm-check", "refs/a.md", True)]


# ================================================================ G2 full tool results
def _saved(tmp_path, body: str, folder="tool-results"):
    d = tmp_path / "cfg" / "projects" / "p" / folder
    d.mkdir(parents=True)
    f = d / "mcp-hyd-dmn-evaluate_cards-1.txt"
    f.write_text(body, encoding="utf-8")
    return f


def _cli_message(path) -> str:
    return (f"Error: result (161,234 characters) exceeds maximum allowed tokens. Output has been saved to {path}.\n"
            "Format: JSON array with schema: [{type: string, text: string}]\nUse offset and limit parameters to read specific portions.")


def _run_with_tool_end(tmp_path, repo, text):
    repo_inst = skill_start(repo, repo._defn)
    def calls(request):
        yield ExecEvent(kind=ExecEventKind.TOOL_START, tool="mcp__hyd-dmn__evaluate_cards", tool_input={"asset": "HYD-01"}, tool_use_id="e1", session_id="s1")
        yield ExecEvent(kind=ExecEventKind.TOOL_END, tool="mcp__hyd-dmn__evaluate_cards", text=text, tool_use_id="e1", session_id="s1", is_error=True)
    assert _runner(tmp_path / "ws", repo, calls).poll_once() == 1
    return repo_inst, next(e for e in repo.events if e["event_type"] == "tool_usage_finished")


def _payload_repo():
    repo, defn = skill_repo()
    repo._defn = defn
    return repo


def test_a_result_the_cli_moved_to_a_file_is_stored_whole_and_referenced(tmp_path, monkeypatch):
    inner = json.dumps({"cards": [{"id": f"c{i}", "score": i} for i in range(4000)], "asset": "HYD-01"}, ensure_ascii=False)
    f = _saved(tmp_path, json.dumps([{"type": "text", "text": inner}]))
    repo = _payload_repo()
    inst, row = _run_with_tool_end(tmp_path, repo, _cli_message(f))
    full = row["data"]["full_output"]
    assert row["data"]["output"].startswith("Error: result (161,234 characters)")       # the row still says what the agent saw
    assert full["stored"] is True and full["ref"] == hashlib.sha256(inner.encode("utf-8")).hexdigest() == full["sha256"]
    assert full["source"] == "cli_saved_file" and full["content_type"] == "json" and full["chars"] == len(inner) and full["cut"] is False
    assert "JSON 객체 · 키 2개: cards[4000], asset" in full["summary"]
    stored = repo.get_event_payload(full["ref"])
    assert stored["content"] == inner and stored["meta"]["unwrapped"] is True and stored["proc_inst_id"] == inst["proc_inst_id"]
    assert stored["tool"] == "mcp__hyd-dmn__evaluate_cards" and stored["tool_use_id"] == "e1"

    # the portal expands it in chunks; another tenant's instance does not see it
    rt = instances.InstanceRuntime(repo, engine.Definition.load(instance_mode_def()), instances.Hooks())
    c = _client(rt, monkeypatch)
    first = c.get(f"/api/event-payloads/{full['ref']}?limit=1000").json()
    assert first["content"] == inner[:1000] and first["next_offset"] == 1000 and first["chars"] == len(inner)
    rest = c.get(f"/api/event-payloads/{full['ref']}?offset=1000&limit=200000").json()
    assert first["content"] + rest["content"] == inner and rest["next_offset"] is None
    assert c.get("/api/event-payloads/" + "0" * 64).status_code == 404 and c.get("/api/event-payloads/nothex").status_code == 400
    other = instances.InstanceRuntime(repo, engine.Definition.load(instance_mode_def()), instances.Hooks(), tenant_id="other")
    assert _client(other, monkeypatch).get(f"/api/event-payloads/{full['ref']}").status_code == 404


def test_a_path_outside_tool_results_is_not_read(tmp_path):
    f = _saved(tmp_path, "secret", folder="elsewhere")
    repo = _payload_repo()
    _, row = _run_with_tool_end(tmp_path, repo, _cli_message(f))
    full = row["data"]["full_output"]
    assert full["stored"] is False and full["ref"] is None and "임시 파일" in full["error"] and repo.event_payloads == {}


def test_a_preview_cut_output_keeps_its_full_text(tmp_path):
    text = "행 " * 6000
    repo = _payload_repo()
    _, row = _run_with_tool_end(tmp_path, repo, text)
    full = row["data"]["full_output"]
    assert row["data"]["output"].endswith("(생략됨)") and full["source"] == "event_text" and full["content_type"] == "text"
    assert repo.get_event_payload(full["ref"])["content"] == text


def test_a_short_output_gets_no_payload(tmp_path):
    repo = _payload_repo()
    _, row = _run_with_tool_end(tmp_path, repo, "[3 rows]")
    assert "full_output" not in row["data"] and repo.event_payloads == {}


def test_a_store_failure_is_said_in_the_row_and_the_run_still_completes(tmp_path):
    repo = _payload_repo()
    def broken(payload):
        raise RuntimeError("db down")
    repo.store_event_payload = broken
    _, row = _run_with_tool_end(tmp_path, repo, "x" * 5000)
    full = row["data"]["full_output"]
    assert full["stored"] is False and full["ref"] is None and "db down" in full["error"] and full["sha256"]
    assert any(e["event_type"] == "task_completed" for e in repo.events)


def test_payload_content_is_cut_at_the_cap_and_says_so(monkeypatch):
    monkeypatch.setattr(payloads, "MAX_CHARS", 10)
    row, summary = payloads.payload_row({"content": "0123456789ABC", "source": "event_text", "meta": {}}, tool="t", tool_use_id=None,
                                        job_id="j", todo_id="w", proc_inst_id=None)
    assert row["content"] == "0123456789" and row["meta"] == {"original_chars": 13, "cut": True}
    assert payloads.reference(row, summary, stored=True)["cut"] is True


# ================================================================ G3 re-observation series
def test_series_sampling_keeps_the_last_reading_and_the_true_extremes():
    rows = [(f"2026-10-09T12:00:{i:02d}Z", 60.0 - i * 0.2) for i in range(50)] + [("2026-10-09T12:00:50Z", 70.0)]
    s = reobs_series.build(rows, tag="TS1", op="<", limit=55.0, since="a", until="b", after="command", max_points=10)
    assert len(s["points"]) == 10 and s["points"][-1] == {"t": "2026-10-09T12:00:50Z", "v": 70.0}
    assert s["samples"] == 51 and s["min"] == pytest.approx(50.2) and s["max"] == 70.0 and s["first"] == 60.0 and s["last"] == 70.0
    assert s["inside_last"] is False and 0 < s["inside_share"] < 1 and s["criterion"] == "TS1 < 55.0"
    empty = reobs_series.build([], tag="PS1", op=">=", limit=165.0, since=None, until=None, after="work_order")
    assert empty["points"] == [] and empty["last"] is None and empty["inside_last"] is False
    assert reobs_series.window_start([{"state": "RE_OBSERVING", "t": "t1"}, {"state": "ESCALATED", "t": "t2"},
                                      {"state": "RE_OBSERVING", "t": "t3"}]) == "t3"


class _Fx(machine.Effects):
    def __init__(self):
        self.audits, self.timers = [], []

    def emit_audit(self, evt):
        self.audits.append(evt)

    def set_timer(self, name, seconds):
        self.timers.append(name)


def _observing():
    inc = machine.Incident.from_card("INC-T", {"alert": {"asset": "HYD-01", "alertId": "A1", "pattern": "COOLER_DEGRADATION"},
                                               "recommended": []})
    inc.state = "RE_OBSERVING"
    inc.history.append({"state": "RE_OBSERVING", "t": "2026-10-09T12:00:00Z"})
    return inc


def test_the_timer_keeps_the_window_series_on_the_incident_and_summarises_it_in_the_audit():
    inc, fx = _observing(), _Fx()
    rows = [(f"2026-10-09T12:00:{i:02d}Z", 58.0 - i * 0.15) for i in range(45)]
    series = reobs_series.build(rows, tag="TS1", op="<", limit=55.0, since="2026-10-09T12:00:00Z", until="2026-10-09T12:00:45Z", after="command")
    machine.on_timer(inc, "reobs", NOW, rows[-1][1], fx, series=series)          # inside but not cleared → extended
    assert inc.state == "RE_OBSERVING" and inc.reobs_series["extensions"] == 1 == inc.reobs_extensions
    ext = next(a for a in fx.audits if a["event"] == "REOBSERVATION_EXTENDED")["detail"]["series"]
    assert ext["samples"] == 45 and ext["last"] == series["last"] and "points" not in ext
    inc.cleared = True
    machine.on_timer(inc, "reobs", NOW, rows[-1][1], fx, series=dict(series, samples=60))
    assert inc.state == "RESOLVED" and inc.to_dict()["reobsSeries"]["samples"] == 60 and inc.to_dict()["reobsSeries"]["points"]
    assert next(a for a in fx.audits if a["event"] == "REOBSERVATION")["detail"]["series"]["samples"] == 60
    # without a series (the TimescaleDB read failed) the verdict is unchanged and the last kept series stays
    inc2, fx2 = _observing(), _Fx()
    inc2.cleared = True
    machine.on_timer(inc2, "reobs", NOW, 50.0, fx2)
    assert inc2.state == "RESOLVED" and inc2.reobs_series is None and "series" not in fx2.audits[-1]["detail"]


def test_incident_with_a_series_survives_the_snapshot_round_trip():
    from dataclasses import asdict
    inc = _observing()
    inc.reobs_series = {"tag": "TS1", "points": [{"t": "x", "v": 1.0}]}
    again = machine.Incident(**json.loads(json.dumps(asdict(inc))))
    assert again.reobs_series == inc.reobs_series
    old = asdict(inc); old.pop("reobs_series")                              # a snapshot written before A161-G3
    assert machine.Incident(**old).reobs_series is None


def test_work_order_reobservation_keeps_the_series_on_the_event_and_the_incident(world):
    seen = []

    def window(inc, after, since):
        seen.append((inc.id, after, since))
        return reobs_series.build([(since, 52.0), ("2026-10-03T12:01:00Z", 48.0)], tag="TS1", op="<", limit=55.0, since=since,
                                  until="2026-10-03T12:01:00Z", after=after)
    world["ctx"].window_series = window
    rt, inst, inc, out = run_maintenance(world, 48.0)
    rt.reconcile_services(now=NOW + timedelta(seconds=30))
    plan = _row(rt, inst, "T_check")["draft"]["reobserve"]
    inc.cleared = True
    rt.reconcile_services(now=NOW + timedelta(seconds=80))
    assert seen and seen[-1][1] == "work_order" and seen[-1][2] == plan["started_at"]
    ev = next(e for e in rt.repo.list_events(proc_inst_id=inst["proc_inst_id"]) if e["job_id"] == "REOBSERVATION")
    series = ev["data"]["reading"]["series"]
    assert series["after"] == "work_order" and [p["v"] for p in series["points"]] == [52.0, 48.0]
    assert inc.to_dict()["reobsSeries"] == series
    report = engine.variables(rt.repo.get_instance(inst["proc_inst_id"]))["result_report"]
    assert "series" not in json.dumps(report.get("values"))                    # the result report reads the plain value as before


def test_a_failing_series_read_does_not_stop_the_verdict(world):
    def window(inc, after, since):
        raise OSError("tsdb down")
    world["ctx"].window_series = window
    rt, inst, inc, out = run_maintenance(world, 48.0)
    rt.reconcile_services(now=NOW + timedelta(seconds=30))
    inc.cleared = True
    rt.reconcile_services(now=NOW + timedelta(seconds=80))
    done = rt.repo.get_instance(inst["proc_inst_id"])
    assert engine.variables(done)["recovered"] is True and inc.reobs_series is None


# ================================================================ G4 events paging
def instance_mode_def():
    from test_u2_agents_skills import DEF_PATH
    return DEF_PATH


def _client(rt, monkeypatch):
    monkeypatch.setattr(instance_mode, "_runtime", rt)
    app = FastAPI()
    instance_mode.mount(app, "instance")
    return TestClient(app)


@pytest.fixture
def paged(monkeypatch):
    repo, defn = skill_repo()
    inst = skill_start(repo, defn)
    rt = instances.InstanceRuntime(repo, defn, instances.Hooks())
    monkeypatch.setattr(instance_mode, "_runtime", rt)
    app = FastAPI()
    instance_mode.mount(app, "instance")
    repo.events.clear()
    repo.record_events([{"id": f"ev-{i:03d}", "job_id": "j", "todo_id": "w", "proc_inst_id": inst["proc_inst_id"], "event_type": "task_working",
                         "timestamp": f"2026-10-09T12:00:{i // 10:02d}.{i % 10}00Z", "data": {"n": i}} for i in range(25)])
    return TestClient(app), repo, inst


def test_events_default_answer_is_unchanged_and_says_whether_older_rows_exist(paged):
    c, repo, inst = paged
    r = c.get(f"/api/events?proc_inst_id={inst['proc_inst_id']}")
    assert [e["data"]["n"] for e in r.json()] == list(range(25)) and r.headers["X-Events-Has-More"] == "0" and "X-Events-Before" not in r.headers
    r = c.get(f"/api/events?proc_inst_id={inst['proc_inst_id']}&limit=10")
    assert [e["data"]["n"] for e in r.json()] == list(range(15, 25))
    assert r.headers["X-Events-Has-More"] == "1" and r.headers["X-Events-Before"] == "ev-015"


def test_events_pages_backwards_without_gaps_or_repeats(paged):
    c, repo, inst = paged
    seen, before = [], None
    while True:
        q = f"/api/events?proc_inst_id={inst['proc_inst_id']}&limit=10&page=true" + (f"&before={before}" if before else "")
        body = c.get(q).json()
        seen = [e["data"]["n"] for e in body["events"]] + seen
        if not body["has_more"]:
            break
        before = body["before"]
    assert seen == list(range(25))
    assert c.get(f"/api/events?proc_inst_id={inst['proc_inst_id']}&before=no-such-id").json() == []


def test_instance_view_carries_the_page_cursor(paged, monkeypatch):
    c, repo, inst = paged
    monkeypatch.setattr(instances, "EVENTS_WINDOW", 20)
    view = c.get(f"/api/instances/{inst['proc_inst_id']}").json()
    assert [e["data"]["n"] for e in view["events"]] == list(range(5, 25))
    assert view["events_page"] == {"limit": 20, "has_more": True, "before": "ev-005"}
    older = c.get(f"/api/events?proc_inst_id={inst['proc_inst_id']}&before=ev-005").json()
    assert [e["data"]["n"] for e in older] == list(range(5))
