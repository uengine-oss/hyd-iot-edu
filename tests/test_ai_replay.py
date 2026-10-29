"""AI 응답 저장 · 재생(worker/ai_replay.py): API 키 없는 워커가 AI가 응답할 단계에만 미리 저장한 응답을 넣고,
나머지(결과 검사 · 저장 · 처리 과정 이벤트)는 실제 실행과 같은 Runner 코드로 처리하는지. 가짜 CLI · MemoryRepo 로 돈다.
규칙: 업무 이름이 같으면 저장된 응답을 쓴다(입력 · 지시문이 달라도). 업무 하나에 파일 하나."""
import gzip
import json
from pathlib import Path

import pytest

from procsvc import engine
from procsvc.procdb import MemoryRepo
from worker import ai_replay
from worker import runner as runner_mod
from worker.runner import Runner
from cliagents import ExecEvent, ExecEventKind
from test_worker import _fake_exec, _repo, _settings, DEF_PATH, NOW

ANSWER = '{"cause": "cause:cooler-fin-fouling", "failure_mode": "fm:cooling-loss", "guide_card": {"recommended": ["skill:fan-max"]}}'
ASK_BASH = "Claude requested permissions to use Bash, but you haven't granted it yet."


def _diagnose(repo, inst):
    return next(w for w in repo.list_workitems(proc_inst_id=inst["proc_inst_id"]) if w["activity_id"] == "task:diagnose")


def _runner(tmp_path, repo, exec_fn, mode):
    return Runner(_settings(tmp_path / mode), repo, exec_fn=exec_fn, schema_prompt="# s", resolve_provider=lambda pid: object(), ai_mode=mode)


def _record(tmp_path, lib, exec_fn, repo_inst=None):
    repo, inst = repo_inst or _repo()
    _runner(tmp_path, repo, ai_replay.recording(exec_fn, lib, lambda p: "claude-code"), "record").poll_once()
    return repo, inst


def _replay(tmp_path, lib, repo_inst=None):
    repo, inst = repo_inst or _repo()                    # 새 처리 건: id · 시각이 저장할 때와 다르다
    assert _runner(tmp_path, repo, ai_replay.replaying(lib), "replay").poll_once() == 1
    return repo, inst, _diagnose(repo, inst)


def _texts(repo, row):
    return json.dumps([e["data"] for e in repo.list_events(todo_id=row["id"])], ensure_ascii=False)


def _answer(repo, row, text):
    asked = [e for e in repo.list_events(todo_id=row["id"]) if e["event_type"] == "human_asked"][-1]
    repo.update_workitem(repo.get_workitem(row["id"]) | {"feedback": {"human_answer": text, "job_id": asked["job_id"]}, "draft_status": "FB_REQUESTED"})


def test_saved_response_is_replayed_without_calling_the_cli(tmp_path):
    lib = ai_replay.Library(tmp_path / "lib")
    rrepo, rinst = _record(tmp_path, lib, _fake_exec(ANSWER))
    [doc] = lib.docs()
    assert doc["step"] == "원인 진단" and len(doc["runs"]) == 1 and doc["runs"][0]["events"][-1]["kind"] == "result"

    repo, inst, row = _replay(tmp_path, lib)               # replaying 은 CLI 실행 함수를 받지 않는다
    assert inst["proc_inst_id"] != rinst["proc_inst_id"]
    assert row["status"] == "SUBMITTED" and row["output"]["cause"] == "cause:cooler-fin-fouling"
    assert row["output"]["cliagents_session_id"].startswith("replay:")
    texts = _texts(repo, row)
    assert "AI 응답 재생 — 미리 저장한 응답이며 지금 AI가 새로 추론한 것이 아닙니다(「원인 진단」," in texts
    assert "강사" not in texts


def test_no_saved_response_for_the_business_step_fails_instead_of_inventing_one(tmp_path):
    lib = ai_replay.Library(tmp_path / "lib")
    _record(tmp_path, lib, _fake_exec(ANSWER))
    [doc] = lib.docs()                                     # 다른 업무의 저장분만 있다
    lib.path_of("원인 진단").rename(lib.path_of("조치 후보"))
    lib.path_of("조치 후보").write_bytes(gzip.compress(json.dumps(doc | {"step": "조치 후보"}, ensure_ascii=False).encode("utf-8")))
    repo, inst = _repo()
    _runner(tmp_path, repo, ai_replay.replaying(lib), "replay").poll_once()
    row = _diagnose(repo, inst)
    assert row["draft_status"] == "FAILED" and row["output"] is None
    err = repo.list_events(todo_id=row["id"])[-1]["data"]["raw_error"]
    assert "「원인 진단」 업무의 저장된 AI 응답이 없습니다" in err and "API 키" in err


def test_same_business_step_replays_even_with_other_input_or_instructions(tmp_path):
    lib = ai_replay.Library(tmp_path / "lib")
    _record(tmp_path, lib, _fake_exec(ANSWER))
    # 다른 입력(학생 사건의 다른 경보 값)
    repo, _ = _repo()
    defn = engine.Definition.load(DEF_PATH)
    inst = engine.new_instance(defn, {"asset": "HYD-01", "pattern": "COOLER_DEGRADATION", "alert": {"alertId": "B", "ts1": 57.3}, "incident": "INC-2"}, now=NOW)
    adv = engine.start(defn, inst, now=NOW)
    repo.insert_instance(inst); repo.insert_workitems(adv.created); repo.update_instance(inst)
    for w in repo.list_workitems():
        if w["proc_inst_id"] != inst["proc_inst_id"]:
            repo.update_workitem(w | {"status": "DONE"})
    # 학생이 고친 지시문
    row = _diagnose(repo, inst)
    repo.update_workitem(row | {"query": "[Instruction]\n학생이 고쳐 쓴 지시문\n\n[InputData]\n{}"})
    repo, inst, row = _replay(tmp_path, lib, (repo, inst))
    assert row["status"] == "SUBMITTED" and row["output"]["cause"] == "cause:cooler-fin-fouling"


def test_saving_again_overwrites_the_one_file_of_that_business_step(tmp_path):
    lib = ai_replay.Library(tmp_path / "lib")
    _record(tmp_path, lib, _fake_exec(ANSWER))
    _record(tmp_path, lib, _fake_exec(ANSWER.replace("cooler-fin-fouling", "fan-drive-fault")))
    [doc] = lib.docs()
    assert len(list((tmp_path / "lib").glob("*.json.gz"))) == 1 and "fan-drive-fault" in json.dumps(doc["runs"])


def test_saved_response_that_breaks_the_result_contract_fails_like_a_live_run(tmp_path):
    lib = ai_replay.Library(tmp_path / "lib")
    _record(tmp_path, lib, _fake_exec("원인은 쿨러입니다 (JSON 없음)"))
    repo, inst = _repo()
    _runner(tmp_path, repo, ai_replay.replaying(lib), "replay").poll_once()
    row = _diagnose(repo, inst)
    # 저장할 때처럼 형식 교정이 이어지고(저장된 교정 응답도 형식에 안 맞음), 실제 실행과 같은 형식 검사 오류로 끝난다
    assert row["draft_status"] == "FAILED" and row["output"] is None
    assert "출력 형식과 맞지 않습니다" in repo.list_events(todo_id=row["id"])[-1]["data"]["raw_error"]


def test_format_correction_is_saved_and_replayed_in_order(tmp_path):
    lib = ai_replay.Library(tmp_path / "lib")
    answers = iter(["원인은 쿨러 핀 오염입니다 (JSON 없음)", ANSWER])
    def fn(provider, request, env):
        yield from _fake_exec(next(answers))(provider, request, env)
    _record(tmp_path, lib, fn)
    assert len(lib.docs()[0]["runs"]) == 2                 # 첫 응답 + 같은 세션의 교정 응답
    repo, inst, row = _replay(tmp_path, lib)
    assert row["status"] == "SUBMITTED" and row["output"]["cause"] == "cause:cooler-fin-fouling"


def test_question_and_answer_continue_with_the_saved_follow_up(tmp_path):
    lib = ai_replay.Library(tmp_path / "lib")
    repo, inst = _record(tmp_path, lib, _fake_exec("", permission_refusal=ASK_BASH))      # AI 가 사람에게 묻는다
    _answer(repo, _diagnose(repo, inst), "Bash 없이 MCP 로만")
    _record(tmp_path, lib, _fake_exec(ANSWER), (repo, inst))                               # 답 뒤의 실행
    assert len(lib.docs()[0]["runs"]) == 2
    # 학생: 같은 질문이 오고, 다른 글로 답해도 저장된 다음 응답으로 이어진다
    srepo, sinst = _repo()
    _runner(tmp_path, srepo, ai_replay.replaying(lib), "replay").poll_once()
    srow = _diagnose(srepo, sinst)
    assert srow["draft_status"] == "HUMAN_ASKED"
    _answer(srepo, srow, "학생이 쓴 다른 답")
    assert _runner(tmp_path, srepo, ai_replay.replaying(lib), "replay").poll_once() == 1
    final = srepo.get_workitem(srow["id"])
    assert final["status"] == "SUBMITTED" and final["output"]["cause"] == "cause:cooler-fin-fouling"


def test_secret_values_are_never_saved(tmp_path, monkeypatch):
    monkeypatch.setattr(ai_replay, "_SECRET_ENV", {"OPENAI_API_KEY": "sk-test-secret-value-123"})
    lib = ai_replay.Library(tmp_path / "lib")
    _record(tmp_path, lib, _fake_exec('{"cause": "sk-test-secret-value-123", "failure_mode": "f", "guide_card": {}}'))
    [path] = list((tmp_path / "lib").glob("*.json.gz"))                 # 가리고 저장한다 — 그 단계는 재생할 수 있다
    saved = gzip.decompress(path.read_bytes()).decode("utf-8")
    assert "sk-test-secret-value-123" not in saved and "********" in saved


def test_secret_env_names_follow_the_worker_rule_not_every_name_with_pwd():
    env = {"PWD": "/home/teacher/hyd-iot-edu", "OLDPWD": "/home/teacher", "GIT_CONFIG_KEY_0": "http.extraheader",
           "ANTHROPIC_API_KEY": "sk-ant-xxxxxxxx", "SUPABASE_DSN": "postgresql://u:p@h/db", "HYD_SECRET_GOOGLE": "tok-123456789", "GH_TOKEN": "ghp_123456789"}
    assert sorted(ai_replay._secret_env(env)) == ["ANTHROPIC_API_KEY", "GH_TOKEN", "HYD_SECRET_GOOGLE", "SUPABASE_DSN"]


def test_tool_server_tokens_of_the_run_are_never_saved(tmp_path):
    # 학생이 등록한 서버의 토큰은 환경 변수가 아니라 이번 실행의 .mcp.json headers 로 CLI 에 간다
    lib = ai_replay.Library(tmp_path / "lib")
    def echoes_token(provider, request, env):
        cfg = Path(request.workdir) / ".mcp.json"
        doc = json.loads(cfg.read_text(encoding="utf-8"))
        doc["mcpServers"]["hyd-dmn"]["headers"] = {"Authorization": "Bearer tok-run-only-777"}
        cfg.write_text(json.dumps(doc), encoding="utf-8")
        yield from _fake_exec(ANSWER.replace("cooler-fin-fouling", "tok-run-only-777"))(provider, request, env)
    _record(tmp_path, lib, echoes_token)
    [path] = list((tmp_path / "lib").glob("*.json.gz"))
    saved = gzip.decompress(path.read_bytes()).decode("utf-8")
    assert "tok-run-only-777" not in saved and "Bearer" not in saved and "********" in saved


def test_result_file_is_saved_and_restored(tmp_path):
    lib = ai_replay.Library(tmp_path / "lib")
    def writes_file(provider, request, env):
        p = Path(request.workdir) / "output" / "result.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(ANSWER, encoding="utf-8")
        yield from _fake_exec("결과를 output/result.json 에 썼습니다")(provider, request, env)
    _record(tmp_path, lib, writes_file)
    assert lib.docs()[0]["runs"][0]["result_file"] == ANSWER
    repo, inst, row = _replay(tmp_path, lib)
    assert row["output"]["cause"] == "cause:cooler-fin-fouling"


@pytest.mark.parametrize("mode,login,expected", [("auto", False, "replay"), ("auto", None, "replay"), ("auto", True, "live"),
                                                 ("replay", True, "replay"), ("live", False, "live"), ("record", False, "record")])
def test_auto_mode_is_live_only_when_a_key_or_login_is_confirmed(mode, login, expected):
    assert ai_replay.resolve_mode(mode, lambda: login) == expected


def test_unknown_mode_is_an_error():
    with pytest.raises(ValueError, match="AI_MODE"):
        ai_replay.resolve_mode("magic", lambda: None)


def test_worker_without_cli_login_starts_in_replay(monkeypatch, tmp_path):
    from dataclasses import replace
    from types import SimpleNamespace
    from worker import main
    s = replace(main.settings, ai_mode="auto", ai_replay_dir=tmp_path / "lib", isolate_config_dir=False)
    monkeypatch.setattr(main, "settings", s)
    monkeypatch.setattr(main.registry, "availability", lambda surface, refresh=False:
                        [SimpleNamespace(agent_id=s.cli_agent, installed=False, executable_path=None, install_hint="")])
    assert main._ai_login() is False                       # CLI 가 없다 → 로그인 없음으로 확인
    r = main.build_runner(MemoryRepo())
    assert main.status["ai_mode"] == "replay" and r.ai_mode == "replay" and hasattr(r.exec_fn, "last")
    assert r.course_access is not None
    monkeypatch.setattr(main, "settings", replace(s, ai_mode="live"))
    live = main.build_runner(MemoryRepo())
    assert live.exec_fn is runner_mod._exec_stream and live.course_access is not None


def test_business_name_ignores_spacing_and_case(tmp_path):
    lib = ai_replay.Library(tmp_path / "lib")
    assert lib.path_of("원인 진단") == lib.path_of(" 원인진단 ") and lib.path_of("Root Cause") == lib.path_of("rootcause")


def test_replay_runs_without_the_cli_installed(monkeypatch, tmp_path):
    # 키 · CLI 가 없는 학생 PC: 실제 실행의 제공자 확인(runner._resolve_provider)을 그대로 거쳐도 재생은 CLI 실행 파일을 찾지 않는다
    from cliagents import Surface, registry
    lib = ai_replay.Library(tmp_path / "lib")
    _record(tmp_path, lib, _fake_exec(ANSWER))
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    registry.availability(Surface.EXEC, refresh=True)                    # 설치 확인 결과를 이 PATH 로 다시 읽는다
    try:
        repo, inst = _repo()
        r = Runner(_settings(tmp_path / "r"), repo, exec_fn=ai_replay.replaying(lib), schema_prompt="# s", ai_mode="replay")
        assert r.poll_once() == 1 and _diagnose(repo, inst)["status"] == "SUBMITTED"
    finally:
        monkeypatch.undo()
        registry.availability(Surface.EXEC, refresh=True)


def _new_case(incident, alert, pattern="COOLER_DEGRADATION"):
    repo, _ = _repo()
    defn = engine.Definition.load(DEF_PATH)
    inst = engine.new_instance(defn, {"asset": "HYD-01", "pattern": pattern, "alert": {"alertId": alert}, "incident": incident}, now=NOW)
    adv = engine.start(defn, inst, now=NOW)
    repo.insert_instance(inst); repo.insert_workitems(adv.created); repo.update_instance(inst)
    for w in repo.list_workitems():
        if w["proc_inst_id"] != inst["proc_inst_id"]:
            repo.update_workitem(w | {"status": "DONE"})
    return repo, inst


def _submits_decision(provider, request, env):
    """저장할 때의 AI: 판단 등록(쓰기 도구)을 이 처리 건의 사건 · process_scope 로 부르고, 돌려받은 판단 id 를 결과에 쓴다."""
    task = json.loads((Path(request.workdir) / "context" / "task.json").read_text(encoding="utf-8"))
    inputs = json.loads(task["query"].split("[InputData]")[1])
    args = {"asset": "HYD-01", "alert_id": inputs["alert"]["alertId"], "process_scope": task["process_scope"]}
    s = "sess-W"
    yield ExecEvent(kind=ExecEventKind.RUN_START, session_id=s)
    yield ExecEvent(kind=ExecEventKind.TOOL_START, tool="mcp__neo4j__read_neo4j_cypher", tool_input={"query": "MATCH (a)"}, tool_use_id="r1", session_id=s)
    yield ExecEvent(kind=ExecEventKind.TOOL_END, tool="mcp__neo4j__read_neo4j_cypher", tool_output=[{"type": "text", "text": "[]"}], tool_use_id="r1", session_id=s)
    yield ExecEvent(kind=ExecEventKind.TOOL_START, tool="mcp__hyd-dmn__submit_decision", tool_input=args, tool_use_id="w1", session_id=s)
    yield ExecEvent(kind=ExecEventKind.TOOL_END, tool="mcp__hyd-dmn__submit_decision", tool_use_id="w1", session_id=s,
                    tool_output=[{"type": "text", "text": json.dumps({"id": "dec-rec-0001", "status": "PENDING_APPROVAL"})}])
    said = f"{inputs['alert']['alertId']} 의 판단 dec-rec-0001 을 올렸습니다."
    for k in range(0, len(said), 3):                                # 실제 CLI 처럼 설명이 토큰 조각으로 온다(id 가 조각 경계에 걸린다)
        yield ExecEvent(kind=ExecEventKind.ASSISTANT_TEXT, text=said[k:k + 3], session_id=s)
    yield ExecEvent(kind=ExecEventKind.RESULT, session_id=s, text=json.dumps(
        {"cause": "cause:cooler-fin-fouling", "failure_mode": "fm:cooling-loss", "guide_card": {"decision": "dec-rec-0001", "alert": inputs["alert"]["alertId"]}}))


def _fake_servers(monkeypatch, calls, reply='{"id": "dec-live-0042", "status": "PENDING_APPROVAL"}', is_error=False):
    from procsvc import mcp_check
    def check(spec, timeout=None):
        calls.append(("list", spec["url"]))
        return {"status": "ok", "tools": [{"name": "submit_decision", "callable": False}, {"name": "evaluate_cards", "callable": True}]}
    def call_effect(spec, tool, arguments, **kw):
        calls.append((tool, arguments))
        return {"status": "ok", "result": {"is_error": is_error, "text": reply}}
    monkeypatch.setattr(mcp_check, "check", check)
    monkeypatch.setattr(mcp_check, "call_effect", call_effect)


def test_write_tool_is_called_again_with_this_case_values_and_its_new_id_is_used(tmp_path, monkeypatch):
    lib = ai_replay.Library(tmp_path / "lib")
    _record(tmp_path, lib, _submits_decision, _new_case("INC-rec-1", "AL-rec-1"))
    calls = []
    _fake_servers(monkeypatch, calls)
    repo, inst = _new_case("INC-stu-7", "AL-stu-7")
    assert _runner(tmp_path, repo, ai_replay.replaying(lib), "replay").poll_once() == 1
    row = _diagnose(repo, inst)
    [(tool, args)] = [c for c in calls if c[0] == "submit_decision"]          # 읽기 도구(neo4j)는 다시 부르지 않는다
    assert args["alert_id"] == "AL-stu-7" and args["asset"] == "HYD-01"
    assert args["process_scope"]["instance"] == inst["proc_inst_id"] and args["process_scope"]["workitem"] == row["id"]
    assert row["status"] == "SUBMITTED" and row["output"]["guide_card"] == {"decision": "dec-live-0042", "alert": "AL-stu-7"}
    texts = _texts(repo, row)
    assert "AL-stu-7 의 판단 dec-live-0042" in texts and "dec-rec-0001" not in texts and "AL-rec-1" not in texts
    assert "쓰기 도구(hyd-dmn/submit_decision)는 이 PC에서 다시 실행했습니다" in texts


def test_write_tool_failure_on_this_pc_fails_the_step_with_its_reason(tmp_path, monkeypatch):
    lib = ai_replay.Library(tmp_path / "lib")
    _record(tmp_path, lib, _submits_decision, _new_case("INC-rec-1", "AL-rec-1"))
    _fake_servers(monkeypatch, [], reply='{"error": "판단의 작업/세대/정의 판본이 일치하지 않습니다"}', is_error=True)
    repo, inst = _new_case("INC-stu-8", "AL-stu-8")
    _runner(tmp_path, repo, ai_replay.replaying(lib), "replay").poll_once()
    row = _diagnose(repo, inst)
    err = repo.list_events(todo_id=row["id"])[-1]["data"]["raw_error"]
    assert row["draft_status"] == "FAILED" and "쓰기 도구를 이 PC에서 다시 부르지 못했습니다" in err and "세대" in err


def _persists_big_result(keep_file=True):
    """Claude Code 처럼 큰 도구 결과를 작업 폴더 안 파일로 빼고 AI 에게는 안내문과 앞부분만 준다(2026-10-23 실측: 발주안 등록 51 KB)."""
    def run(provider, request, env):
        for ev in _submits_decision(provider, request, env):
            if ev.kind is ExecEventKind.TOOL_END and ev.tool_use_id == "w1":
                full = ev.tool_output[0]["text"]
                p = Path(request.workdir) / ".agent-home" / "claude-code" / "projects" / "p" / "s" / "tool-results" / "w1.txt"
                if keep_file:
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(full, encoding="utf-8")
                ev = ExecEvent(kind=ExecEventKind.TOOL_END, tool=ev.tool, tool_use_id="w1", session_id=ev.session_id,
                               tool_output=f"<persisted-output>\nOutput too large (51.6KB). Full output saved to: {p}\n\nPreview (first 2KB):\n{full[:12]}\n...\n</persisted-output>")
            yield ev
    return run


def test_write_tool_result_moved_to_a_file_still_gets_its_new_id(tmp_path, monkeypatch):
    lib = ai_replay.Library(tmp_path / "lib")
    _record(tmp_path, lib, _persists_big_result(), _new_case("INC-rec-1", "AL-rec-1"))
    _fake_servers(monkeypatch, [])
    repo, inst = _new_case("INC-stu-5", "AL-stu-5")
    _runner(tmp_path, repo, ai_replay.replaying(lib), "replay").poll_once()
    row = _diagnose(repo, inst)
    assert row["status"] == "SUBMITTED" and row["output"]["guide_card"] == {"decision": "dec-live-0042", "alert": "AL-stu-5"}
    assert "dec-rec-0001" not in _texts(repo, row)


def test_write_tool_result_that_cannot_be_read_fails_instead_of_keeping_the_saved_id(tmp_path, monkeypatch):
    lib = ai_replay.Library(tmp_path / "lib")
    _record(tmp_path, lib, _persists_big_result(keep_file=False), _new_case("INC-rec-1", "AL-rec-1"))
    _fake_servers(monkeypatch, [])
    repo, inst = _new_case("INC-stu-6", "AL-stu-6")
    _runner(tmp_path, repo, ai_replay.replaying(lib), "replay").poll_once()
    row = _diagnose(repo, inst)
    err = repo.list_events(todo_id=row["id"])[-1]["data"]["raw_error"]
    assert row["draft_status"] == "FAILED" and "저장된 결과를 읽을 수 없어 새로 만든 id 를 바꿔 끼울 수 없습니다" in err


def test_result_file_gets_this_case_values_too(tmp_path, monkeypatch):
    def to_file(provider, request, env):
        for ev in _submits_decision(provider, request, env):
            if ev.kind is ExecEventKind.RESULT:
                p = Path(request.workdir) / "output" / "result.json"
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(ev.text, encoding="utf-8")
                ev = ExecEvent(kind=ExecEventKind.RESULT, text="결과를 output/result.json 에 썼습니다", session_id=ev.session_id)
            yield ev
    lib = ai_replay.Library(tmp_path / "lib")
    _record(tmp_path, lib, to_file, _new_case("INC-rec-1", "AL-rec-1"))
    _fake_servers(monkeypatch, [])
    repo, inst = _new_case("INC-stu-9", "AL-stu-9")
    _runner(tmp_path, repo, ai_replay.replaying(lib), "replay").poll_once()
    assert _diagnose(repo, inst)["output"]["guide_card"] == {"decision": "dec-live-0042", "alert": "AL-stu-9"}


def test_same_business_name_under_another_alert_type_is_another_business(tmp_path):
    # 쿨러 열화 · 펌프 누설 · 팬 진동은 같은 흐름 · 같은 업무 이름(원인 진단 …)을 쓴다 — 쿨러 응답을 펌프 사건에 주면 안 된다
    root = tmp_path / "lib"
    cooler = _new_case("INC-c", "AL-c")
    _record(tmp_path, ai_replay.Library(root, case_of=ai_replay.case_of_instance(cooler[0])), _fake_exec(ANSWER), cooler)
    [doc] = ai_replay.Library(root).docs()
    assert doc["case"] == "COOLER_DEGRADATION"
    repo, inst = _new_case("INC-p", "AL-p", pattern="PUMP_LEAKAGE")
    _runner(tmp_path, repo, ai_replay.replaying(ai_replay.Library(root, case_of=ai_replay.case_of_instance(repo))), "replay").poll_once()
    row = _diagnose(repo, inst)
    err = repo.list_events(todo_id=row["id"])[-1]["data"]["raw_error"]
    assert row["draft_status"] == "FAILED" and "「원인 진단」 업무(경보 PUMP_LEAKAGE)의 저장된 AI 응답이 없습니다" in err
    repo, inst = _new_case("INC-c2", "AL-c2")                       # 같은 경보 종류면 재생한다
    _runner(tmp_path, repo, ai_replay.replaying(ai_replay.Library(root, case_of=ai_replay.case_of_instance(repo))), "replay").poll_once()
    assert _diagnose(repo, inst)["status"] == "SUBMITTED"
    pump = _new_case("INC-p2", "AL-p2", pattern="PUMP_LEAKAGE")      # 펌프를 저장하면 쿨러와 따로 남는다
    _record(tmp_path, ai_replay.Library(root, case_of=ai_replay.case_of_instance(pump[0])), _fake_exec(ANSWER), pump)
    assert sorted(d["case"] for d in ai_replay.Library(root).docs()) == ["COOLER_DEGRADATION", "PUMP_LEAKAGE"]


def test_document_extraction_is_told_apart_by_document_content_and_segment():
    rows = {}
    def put(pid, values):
        rows[pid] = {"proc_inst_id": pid, "variables_data": [{"key": k, "value": v} for k, v in values.items()]}
    repo = type("Repo", (), {"get_instance": lambda self, pid: rows.get(pid)})()
    put("p.cooler", {"pattern": "COOLER_DEGRADATION"})
    put("p.hm8-a", {"manual_source": {"source_id": "manual:u1:abc", "sha256": "abcdef0123456789ffff"}})
    put("p.hm8-b", {"manual_source": {"source_id": "manual:u2:abc", "sha256": "abcdef0123456789ffff"}})   # 같은 문서를 다시 올림
    put("p.hm8-seg", {"manual_source": {"sha256": "abcdef0123456789ffff"}, "segment": {"index": 2, "total": 3}})
    put("p.ask", {"question": "냉각 경보  원인은?"})
    put("p.ask2", {"question": " 냉각 경보 원인은 "})
    case = ai_replay.case_of_instance(repo)
    assert case("p.cooler") == "COOLER_DEGRADATION" and case("missing") == ""
    assert case("p.ask") == case("p.ask2") == "질문 냉각 경보 원인은"           # 띄어쓰기 · 끝 물음표는 같은 질문
    assert case("p.hm8-a") == case("p.hm8-b") == "문서 abcdef0123456789" and case("p.hm8-seg") == "문서 abcdef0123456789 구간 2"


def test_three_runs_in_the_same_cli_session_are_all_kept_in_order(tmp_path):
    # Claude Code 는 이어 하기(--resume)에도 세션 id 가 같다: 형식 교정 두 번 = 같은 세션의 실행 셋
    lib = ai_replay.Library(tmp_path / "lib")
    answers = iter(["첫 답 (JSON 없음)", "둘째 답 (JSON 없음)", ANSWER])
    def fn(provider, request, env):
        yield from _fake_exec(next(answers), session="sess-same")(provider, request, env)
    repo, inst = _repo()
    Runner(_settings(tmp_path / "rec", max_format_corrections=2), repo, exec_fn=ai_replay.recording(fn, lib, lambda p: "claude-code"),
           schema_prompt="# s", resolve_provider=lambda pid: object(), ai_mode="record").poll_once()
    assert [r["events"][-1]["text"] for r in lib.docs()[0]["runs"]] == ["첫 답 (JSON 없음)", "둘째 답 (JSON 없음)", ANSWER]
    repo, inst = _repo()
    Runner(_settings(tmp_path / "rep", max_format_corrections=2), repo, exec_fn=ai_replay.replaying(lib), schema_prompt="# s",
           resolve_provider=lambda pid: object(), ai_mode="replay").poll_once()
    assert _diagnose(repo, inst)["status"] == "SUBMITTED"


def test_codex_run_servers_are_read_for_write_tool_reruns_and_secrets(tmp_path, monkeypatch):
    # Codex 는 .mcp.json 이 아니라 codex-mcp.toml(mcp_servers={…}) 로 서버를 받는다 — 같은 서버 · 머리글 · 비밀을 읽어야 한다
    from worker import bridge
    from test_worker import TENANT_MCP
    mcp = json.loads(json.dumps(TENANT_MCP))
    mcp["mcpServers"]["hyd-dmn"]["headers"] = {"Authorization": "Bearer tok-codex-55555"}
    bridge.install(tmp_path, mcp, provider_id="codex")
    assert not (tmp_path / ".mcp.json").exists() and (tmp_path / "codex-mcp.toml").exists()
    servers = ai_replay._run_servers(tmp_path)
    assert servers["hyd-dmn"]["url"].endswith("/mcp") and servers["neo4j"]["command"] == "uvx"
    assert "tok-codex-55555" in ai_replay._secrets_in(tmp_path).values()
    calls = []
    _fake_servers(monkeypatch, calls)
    tools = ai_replay._Tools(tmp_path)
    assert ai_replay._mcp_target("hyd-dmn/submit_decision") == ("hyd-dmn", "submit_decision")
    assert tools.writes("hyd-dmn", "submit_decision") and not tools.writes("hyd-dmn", "evaluate_cards") and not tools.writes("neo4j", "read_neo4j_cypher")


def test_listing_shows_each_saved_business_step(tmp_path, capsys):
    # 촬영 뒤 확인: 업무마다 한 줄(경보 종류 · 업무 이름 · 실행 수)
    root = tmp_path / "lib"
    cooler = _new_case("INC-c", "AL-c")
    _record(tmp_path, ai_replay.Library(root, case_of=ai_replay.case_of_instance(cooler[0])), _fake_exec(ANSWER), cooler)
    assert ai_replay.main([str(root)]) == 0
    out = capsys.readouterr().out
    assert "업무 1개" in out and "COOLER_DEGRADATION  「원인 진단」  실행 1개" in out
    assert ai_replay.main([str(tmp_path / "없음")]) == 0 and "업무 0개" in capsys.readouterr().out


def test_new_write_tool_id_carries_into_the_follow_up_run_of_the_same_step(tmp_path, monkeypatch):
    """2026-10-23 라이브(A): 저장분이 '판단 등록 → 결과 형식 교정(이어 하기)' 두 실행이었다. 이어 하기 실행이 저장 때의 판단 id 를
    결과에 다시 써 승인이 'decision is EXECUTED'로 거부됐다 — 앞 실행이 다시 부른 쓰기 도구의 새 id 를 다음 실행이 이어 받는다."""
    lib = ai_replay.Library(tmp_path / "lib")
    calls = iter(["first", "fix"])
    def fn(provider, request, env):
        if next(calls) == "first":
            for ev in _submits_decision(provider, request, env):
                yield ev if ev.kind is not ExecEventKind.RESULT else ExecEvent(kind=ExecEventKind.RESULT, session_id=ev.session_id,
                                                                               text="판단 dec-rec-0001 을 올렸습니다 (JSON 없음)")
            return
        yield ExecEvent(kind=ExecEventKind.RUN_START, session_id="sess-W")
        yield ExecEvent(kind=ExecEventKind.RESULT, session_id="sess-W", text=json.dumps(
            {"cause": "cause:cooler-fin-fouling", "failure_mode": "fm:cooling-loss", "guide_card": {"decision": "dec-rec-0001"}}))
    repo, inst = _new_case("INC-rec-1", "AL-rec-1")
    _record(tmp_path, lib, fn, (repo, inst))
    assert len(lib.docs()[0]["runs"]) == 2
    _fake_servers(monkeypatch, [])
    srepo, sinst = _new_case("INC-stu-9", "AL-stu-9")
    assert _runner(tmp_path, srepo, ai_replay.replaying(lib), "replay").poll_once() == 1
    row = _diagnose(srepo, sinst)
    assert row["status"] == "SUBMITTED" and row["output"]["guide_card"] == {"decision": "dec-live-0042"}


# ---------------------------------------------------------------- 검수 2026-10-23(.evidence/audit2/worker_ingest_replay.md) R1~R5
def _retrying_write(provider, request, env):
    """저장할 때의 AI: 판단 등록을 틀린 세대로 불러 409 를 받고, 고쳐 다시 불러 성공했다(실제로 흔한 모양)."""
    task = json.loads((Path(request.workdir) / "context" / "task.json").read_text(encoding="utf-8"))
    inputs = json.loads(task["query"].split("[InputData]")[1])
    good = {"asset": "HYD-01", "alert_id": inputs["alert"]["alertId"], "process_scope": task["process_scope"]}
    bad = dict(good, process_scope=dict(task["process_scope"], generation=99))
    s = "sess-R"
    yield ExecEvent(kind=ExecEventKind.RUN_START, session_id=s)
    yield ExecEvent(kind=ExecEventKind.TOOL_START, tool="mcp__hyd-dmn__submit_decision", tool_input=bad, tool_use_id="w1", session_id=s)
    yield ExecEvent(kind=ExecEventKind.TOOL_END, tool="mcp__hyd-dmn__submit_decision", tool_use_id="w1", session_id=s, is_error=True,
                    tool_output=[{"type": "text", "text": "HTTP 409: 판단의 작업/세대/정의 판본이 일치하지 않습니다"}])
    yield ExecEvent(kind=ExecEventKind.TOOL_START, tool="mcp__hyd-dmn__submit_decision", tool_input=good, tool_use_id="w2", session_id=s)
    yield ExecEvent(kind=ExecEventKind.TOOL_END, tool="mcp__hyd-dmn__submit_decision", tool_use_id="w2", session_id=s,
                    tool_output=[{"type": "text", "text": json.dumps({"id": "dec-rec-0001", "status": "PENDING_APPROVAL"})}])
    yield ExecEvent(kind=ExecEventKind.RESULT, session_id=s, text=json.dumps(
        {"cause": "cause:cooler-fin-fouling", "failure_mode": "fm:cooling-loss", "guide_card": {"decision": "dec-rec-0001"}}))


def _numbered_servers(monkeypatch, calls, rejects_wrong_generation=False):
    from procsvc import mcp_check
    monkeypatch.setattr(mcp_check, "check", lambda spec, timeout=None: {"status": "ok", "tools": [{"name": "submit_decision", "callable": False}]})
    def call_effect(spec, tool, arguments, **kw):
        calls.append(arguments)
        if rejects_wrong_generation and (arguments.get("process_scope") or {}).get("generation") == 99:
            return {"status": "ok", "result": {"is_error": True, "text": "HTTP 409: 판단의 작업/세대/정의 판본이 일치하지 않습니다"}}
        return {"status": "ok", "result": {"is_error": False, "text": json.dumps({"id": f"dec-live-{len(calls):04d}", "status": "PENDING_APPROVAL"})}}
    monkeypatch.setattr(mcp_check, "call_effect", call_effect)


@pytest.mark.parametrize("server_rejects_the_bad_call_too", [True, False])
def test_write_call_that_failed_when_recorded_is_not_called_again_only_the_fixed_call_is(tmp_path, monkeypatch, server_rejects_the_bad_call_too):
    """R3: 녹화 때 오류였던 쓰기 호출은 다시 부르지 않고 저장된 오류를 보인다 — 이번에도 오류여서 회복 전에 단계가 끝나거나(전),
    이번엔 받아들여져 판단만 등록된 채 실패하지(전) 않는다. 고친 두 번째 호출만 이 PC에서 부르고 그 새 id 를 쓴다."""
    lib = ai_replay.Library(tmp_path / "lib")
    _record(tmp_path, lib, _retrying_write, _new_case("INC-rec-1", "AL-rec-1"))
    calls = []
    _numbered_servers(monkeypatch, calls, rejects_wrong_generation=server_rejects_the_bad_call_too)
    repo, inst = _new_case("INC-stu-2", "AL-stu-2")
    _runner(tmp_path, repo, ai_replay.replaying(lib), "replay").poll_once()
    row = _diagnose(repo, inst)
    [args] = calls                                                     # 판단은 하나만 등록된다
    assert args["process_scope"]["generation"] == 0 and args["process_scope"]["workitem"] == row["id"]
    assert row["status"] == "SUBMITTED" and row["output"]["guide_card"] == {"decision": "dec-live-0001"}
    texts = _texts(repo, row)
    assert "HTTP 409" in texts                                         # AI 가 본 오류는 저장 때 그대로 보인다
    assert "저장 때 오류였던 쓰기 호출 1건은 다시 부르지 않고" in texts


def test_recorded_error_envelope_without_the_error_flag_is_not_called_again(tmp_path, monkeypatch):
    """R3: 업무 도구 서버는 오류를 봉투({"result": "error"})로 돌려줘 CLI 가 오류로 표시하지 않을 수 있다 — 그것도 녹화 때 오류다."""
    def fn(provider, request, env):
        for ev in _retrying_write(provider, request, env):
            if ev.kind is ExecEventKind.TOOL_END and ev.tool_use_id == "w1":
                ev = ExecEvent(kind=ExecEventKind.TOOL_END, tool=ev.tool, tool_use_id="w1", session_id=ev.session_id,
                               tool_output=[{"type": "text", "text": json.dumps({"result": "error", "error_kind": "INVALID", "message": "세대 불일치"})}])
            yield ev
    lib = ai_replay.Library(tmp_path / "lib")
    _record(tmp_path, lib, fn, _new_case("INC-rec-1", "AL-rec-1"))
    calls = []
    _numbered_servers(monkeypatch, calls)
    repo, inst = _new_case("INC-stu-3", "AL-stu-3")
    _runner(tmp_path, repo, ai_replay.replaying(lib), "replay").poll_once()
    assert len(calls) == 1 and _diagnose(repo, inst)["output"]["guide_card"] == {"decision": "dec-live-0001"}


def test_rerun_write_that_returns_an_error_envelope_now_fails_the_step(tmp_path, monkeypatch):
    """R3: 다시 부른 호출이 이번에 오류 봉투를 돌려주면(CLI 오류 표시 없이) 사유와 함께 실패한다 — 저장 때 판단 id 로 넘어가지 않는다."""
    lib = ai_replay.Library(tmp_path / "lib")
    _record(tmp_path, lib, _submits_decision, _new_case("INC-rec-1", "AL-rec-1"))
    _fake_servers(monkeypatch, [], reply=json.dumps({"result": "error", "error_kind": "INVALID", "message": "사건이 승인 대기 상태가 아닙니다"},
                                                    ensure_ascii=False))
    repo, inst = _new_case("INC-stu-4", "AL-stu-4")
    _runner(tmp_path, repo, ai_replay.replaying(lib), "replay").poll_once()
    row = _diagnose(repo, inst)
    err = repo.list_events(todo_id=row["id"])[-1]["data"]["raw_error"]
    assert row["draft_status"] == "FAILED" and "오류를 돌려줬습니다" in err and "승인 대기 상태가 아닙니다" in err


def test_unpairable_write_result_names_the_id_already_registered_on_this_pc(tmp_path, monkeypatch):
    """R3: 짝을 못 지어 멈출 때 이 PC에서 이미 등록된 판단 id 를 처리 과정에 남긴다(주인 없는 승인 대기 판단을 찾을 수 있게)."""
    lib = ai_replay.Library(tmp_path / "lib")
    _record(tmp_path, lib, _persists_big_result(keep_file=False), _new_case("INC-rec-1", "AL-rec-1"))
    _fake_servers(monkeypatch, [])
    repo, inst = _new_case("INC-stu-6", "AL-stu-6")
    _runner(tmp_path, repo, ai_replay.replaying(lib), "replay").poll_once()
    row = _diagnose(repo, inst)
    assert "이 PC에서는 이미 등록됐습니다(id dec-live-0042)" in repo.list_events(todo_id=row["id"])[-1]["data"]["raw_error"]


SAVED_CARDS = {"id": "DEC-1023-001-ab12", "cards": [{"rank": 1, "id": "skill:fan-max", "sopId": "SOP-COOL-11"},
                                                     {"rank": 2, "id": "skill:load-cut", "sopId": "SOP-COOL-12"}]}
LIVE_CARDS = {"id": "DEC-1023-007-cd34", "cards": [{"rank": 1, "id": "skill:load-cut", "sopId": "SOP-COOL-12"},
                                                    {"rank": 2, "id": "skill:fan-max", "sopId": "SOP-COOL-11"}]}


@pytest.mark.parametrize("wrap", [lambda d: d, lambda d: {"result": "ok", "document": d}])
def test_only_the_new_document_id_of_a_write_result_is_paired_not_knowledge_ids(wrap):
    """R1: 이 PC의 사실이 달라 카드 순위가 뒤집혀도 기존 지식 id(스킬 · 절차)는 맞바꾸지 않는다. 새로 만든 판단 id 만 짝짓는다."""
    s = ai_replay._Swaps()
    s.pair_ids(wrap(SAVED_CARDS), wrap(LIVE_CARDS))
    assert s.exact == {"DEC-1023-001-ab12": "DEC-1023-007-cd34"}
    assert s.apply({"recommended": "SOP-COOL-11", "skill": "skill:fan-max", "decision": "DEC-1023-001-ab12"}) == \
        {"recommended": "SOP-COOL-11", "skill": "skill:fan-max", "decision": "DEC-1023-007-cd34"}


def test_swapped_pairs_in_text_are_replaced_at_once_not_chained():
    """R1: A→B 와 B→A 가 함께 있어도 두 값이 같아지지 않는다. 긴 값이 먼저 맞는다(AL-10 이 AL-1 로 잘리지 않는다)."""
    s = ai_replay._Swaps()
    s.exact.update({"SOP-COOL-11": "SOP-COOL-12", "SOP-COOL-12": "SOP-COOL-11", "AL-01": "AL-77", "AL-010": "AL-88"})
    assert s.text("SOP-COOL-11 을 권하고 SOP-COOL-12 는 후순위") == "SOP-COOL-12 을 권하고 SOP-COOL-11 는 후순위"
    assert s.text("AL-010 과 AL-01") == "AL-88 과 AL-77"


def test_replayed_result_keeps_its_procedure_when_the_rerun_ranks_cards_differently(tmp_path, monkeypatch):
    """R1(처리 흐름으로): 저장된 AI 결과가 고른 절차는 그대로, 판단 id 만 이 PC의 것이 된다."""
    def fn(provider, request, env):
        for ev in _submits_decision(provider, request, env):
            if ev.kind is ExecEventKind.TOOL_END and ev.tool_use_id == "w1":
                ev = ExecEvent(kind=ExecEventKind.TOOL_END, tool=ev.tool, tool_use_id="w1", session_id=ev.session_id,
                               tool_output=[{"type": "text", "text": json.dumps({"result": "ok", "document": dict(SAVED_CARDS, id="dec-rec-0001")})}])
            if ev.kind is ExecEventKind.RESULT:
                ev = ExecEvent(kind=ExecEventKind.RESULT, session_id=ev.session_id, text=json.dumps(
                    {"cause": "cause:cooler-fin-fouling", "failure_mode": "fm:cooling-loss",
                     "guide_card": {"decision": "dec-rec-0001", "recommended": "SOP-COOL-11", "note": "SOP-COOL-11 을 권하고 SOP-COOL-12 는 후순위"}}))
            yield ev
    lib = ai_replay.Library(tmp_path / "lib")
    _record(tmp_path, lib, fn, _new_case("INC-rec-1", "AL-rec-1"))
    _fake_servers(monkeypatch, [], reply=json.dumps({"result": "ok", "document": dict(LIVE_CARDS, id="dec-live-0042")}))
    repo, inst = _new_case("INC-stu-1", "AL-stu-1")
    _runner(tmp_path, repo, ai_replay.replaying(lib), "replay").poll_once()
    assert _diagnose(repo, inst)["output"]["guide_card"] == {"decision": "dec-live-0042", "recommended": "SOP-COOL-11",
                                                             "note": "SOP-COOL-11 을 권하고 SOP-COOL-12 는 후순위"}


def test_catalog_lists_are_not_paired_by_position():
    """R4: 고정 입력 ontology_catalog 가 학생 그래프와 한 항목만 달라도(개수는 같음) 제안의 지식 id 가 밀리지 않는다.
    처리 건마다 달라지는 값(문서 판본 id 등)은 그대로 바꿔 끼운다. 같은 id 항목끼리는 짝짓는다."""
    saved_ctx = {"id": "t-rec", "inputs": {"manual_source": {"source_id": "manual:rec:v1"}, "ontology_catalog": {"failure_modes": [
        {"id": "fm:bearing-degradation"}, {"id": "fm:cooling-loss", "name": "냉각 손실"}, {"id": "fm:oil-degradation"}, {"id": "fm:overheat-trip"}]}}}
    now_ctx = {"id": "t-stu", "inputs": {"manual_source": {"source_id": "manual:stu:v2"}, "ontology_catalog": {"failure_modes": [
        {"id": "fm:bearing-degradation"}, {"id": "fm:belt-slip"}, {"id": "fm:cooling-loss", "name": "냉각 저하"}, {"id": "fm:oil-degradation"}]}}}
    s = ai_replay._Swaps()
    s.pair(saved_ctx, now_ctx)
    proposal = {"source": "manual:rec:v1", "procedures": [{"id": "SOP-COOL-11", "link": {"failureMode": "fm:cooling-loss", "relation": "MITIGATED_BY"}}],
                "knowledge": {"causes": [{"id": "cause:x", "failure_mode": "fm:oil-degradation"}]}}
    out = s.apply(proposal)
    assert out["procedures"][0]["link"]["failureMode"] == "fm:cooling-loss"
    assert out["knowledge"]["causes"][0]["failure_mode"] == "fm:oil-degradation"
    assert out["source"] == "manual:stu:v2"
    assert s.apply({"name": "냉각 손실"}) == {"name": "냉각 저하"}        # 같은 id 의 항목끼리는 짝짓는다


DEFER = json.dumps({"__deferred__": {"status": "UNKNOWN", "reason": "센서 값이 없어 판단 보류", "evidence": {"tag": "ts1"}}})


def _lib(tmp_path, repo):
    return ai_replay.Library(tmp_path / "lib", case_of=ai_replay.case_of_instance(repo))     # 워커(main.build_runner)와 같게


def _reassess(repo, row):
    import uuid
    from procsvc import task_deferral
    d = repo.get_workitem(row["id"])["draft"]["_deferral"]
    task_deferral.reassess(repo, "hyd", row["id"], deferral_id=d["id"], request_id=uuid.uuid4().hex, by="학생", reason="센서를 다시 붙였다")


def test_recorded_deferral_then_reassessment_replays_in_the_same_order(tmp_path):
    """R2: 녹화 때 보류 → 재평가였으면 학생도 보류 → 재평가 순서를 밟는다. 재평가 녹화가 첫 실행(보류)을 덮어쓰지 않는다."""
    rrepo, rinst = _repo()
    _runner(tmp_path, rrepo, ai_replay.recording(_fake_exec(DEFER), _lib(tmp_path, rrepo), lambda p: "claude-code"), "record").poll_once()
    _reassess(rrepo, _diagnose(rrepo, rinst))
    _runner(tmp_path, rrepo, ai_replay.recording(_fake_exec(ANSWER, session="sess-B"), _lib(tmp_path, rrepo), lambda p: "claude-code"), "record").poll_once()
    assert _diagnose(rrepo, rinst)["status"] == "SUBMITTED"
    [doc] = _lib(tmp_path, rrepo).docs()                                 # 업무 하나에 파일 하나 — 그 안에 두 차례
    assert [r["session_id"] for r in doc["runs"]] == ["sess-A", "sess-B"]
    assert [ai_replay._run_attempt(r) for r in doc["runs"]] == [(0, 0), (0, 1)]
    srepo, sinst = _repo()
    _runner(tmp_path, srepo, ai_replay.replaying(_lib(tmp_path, srepo)), "replay").poll_once()
    row = _diagnose(srepo, sinst)
    assert row["status"] == "PENDING" and "_deferral" in row["draft"]   # 학생의 첫 실행도 보류
    _reassess(srepo, row)
    _runner(tmp_path, srepo, ai_replay.replaying(_lib(tmp_path, srepo)), "replay").poll_once()
    final = srepo.get_workitem(row["id"])
    assert final["status"] == "SUBMITTED" and final["output"]["cause"] == "cause:cooler-fin-fouling"
    assert "(「원인 진단」 · 재평가 1회째," in _texts(srepo, final)


def test_reassessment_with_no_saved_reassessment_fails_instead_of_repeating_the_deferral(tmp_path):
    """R2: 저장분이 보류뿐이면 학생의 재평가는 같은 보류를 끝없이 되풀이하지 않고, 저장분 없음으로 분명히 실패한다."""
    rrepo, _ = _repo()
    _runner(tmp_path, rrepo, ai_replay.recording(_fake_exec(DEFER), _lib(tmp_path, rrepo), lambda p: "claude-code"), "record").poll_once()
    srepo, sinst = _repo()
    _runner(tmp_path, srepo, ai_replay.replaying(_lib(tmp_path, srepo)), "replay").poll_once()
    _reassess(srepo, _diagnose(srepo, sinst))
    _runner(tmp_path, srepo, ai_replay.replaying(_lib(tmp_path, srepo)), "replay").poll_once()
    row = _diagnose(srepo, sinst)
    err = srepo.list_events(todo_id=row["id"])[-1]["data"]["raw_error"]
    assert row["draft_status"] == "FAILED" and "_deferral" not in (row.get("draft") or {})
    assert "「원인 진단」 업무(경보 COOLER_DEGRADATION · 재평가 1회째)의 저장된 AI 응답이 없습니다" in err


def _generation_case(generation):
    """재작업 세대의 처리 건: 처리 건의 rework_generation 이 그 세대이고 작업도 그 세대로 만들어진다(engine.start)."""
    repo, _ = _repo()
    defn = engine.Definition.load(DEF_PATH)
    inst = engine.new_instance(defn, {"asset": "HYD-01", "pattern": "COOLER_DEGRADATION", "alert": {"alertId": "G"}, "incident": "INC-G"}, now=NOW)
    inst["rework_generation"] = generation
    adv = engine.start(defn, inst, now=NOW)
    repo.insert_instance(inst); repo.insert_workitems(adv.created); repo.update_instance(inst)
    for w in repo.list_workitems():
        if w["proc_inst_id"] != inst["proc_inst_id"]:
            repo.update_workitem(w | {"status": "DONE"})
    assert _diagnose(repo, inst)["generation"] == generation
    return repo, inst


def test_rework_generation_is_its_own_turn_and_does_not_overwrite_the_first(tmp_path):
    """R2: 재작업 세대(같은 업무 이름의 새 작업)는 첫 세대 저장분을 덮어쓰지 않고, 녹화가 없으면 첫 세대 응답을 되풀이하지 않는다."""
    rrepo, _ = _repo()
    _runner(tmp_path, rrepo, ai_replay.recording(_fake_exec(ANSWER), _lib(tmp_path, rrepo), lambda p: "claude-code"), "record").poll_once()
    srepo, sinst = _generation_case(1)
    _runner(tmp_path, srepo, ai_replay.replaying(_lib(tmp_path, srepo)), "replay").poll_once()
    row = _diagnose(srepo, sinst)
    assert row["draft_status"] == "FAILED" and "(경보 COOLER_DEGRADATION · 재작업 세대 1)의 저장된 AI 응답이 없습니다" in \
        srepo.list_events(todo_id=row["id"])[-1]["data"]["raw_error"]
    grepo, ginst = _generation_case(1)                                  # 강사가 재작업 세대도 녹화했다
    _runner(tmp_path, grepo, ai_replay.recording(_fake_exec(ANSWER.replace("cooler-fin-fouling", "fan-drive-fault"), session="sess-G"),
                                                 _lib(tmp_path, grepo), lambda p: "claude-code"), "record").poll_once()
    [doc] = _lib(tmp_path, grepo).docs()
    assert [ai_replay._run_attempt(r) for r in doc["runs"]] == [(0, 0), (1, 0)]
    frepo, finst = _repo()
    _runner(tmp_path, frepo, ai_replay.replaying(_lib(tmp_path, frepo)), "replay").poll_once()
    assert _diagnose(frepo, finst)["output"]["cause"] == "cause:cooler-fin-fouling"      # 첫 세대는 첫 세대 응답
    nrepo, ninst = _generation_case(1)                                  # 재작업 세대는 그 세대 응답
    _runner(tmp_path, nrepo, ai_replay.replaying(_lib(tmp_path, nrepo)), "replay").poll_once()
    assert _diagnose(nrepo, ninst)["output"]["cause"] == "cause:fan-drive-fault"


def test_replay_notice_says_alert_strength_cause_and_human_answer_are_not_used(tmp_path):
    """R5: 같은 업무면 같은 응답을 쓰는 설계 — 경보 세기 · 원인 가지 · 사람의 답이 무시된다는 것을 재생 알림 한 줄에 밝힌다."""
    lib = ai_replay.Library(tmp_path / "lib")
    _record(tmp_path, lib, _fake_exec(ANSWER))
    repo, inst, row = _replay(tmp_path, lib)
    [notice] = [e["data"]["content"] for e in repo.list_events(todo_id=row["id"])
                if isinstance(e["data"], dict) and str(e["data"].get("content") or "").startswith("AI 응답 재생 —")]
    assert notice.startswith("AI 응답 재생 — 미리 저장한 응답이며 지금 AI가 새로 추론한 것이 아닙니다(「원인 진단」,")
    assert "지금의 경보 세기 · 원인 · 사람의 답이 저장 때와 달라도 응답은 그대로입니다" in notice and "\n" not in notice


def test_continuation_does_not_run_into_the_next_turn(tmp_path):
    """R2: 이어 하기(형식 교정 · 사람 답 뒤)는 같은 차례의 다음 실행만 쓴다 — 다음 실행이 재평가 차례의 첫 실행이면 이어지는 응답이 없다."""
    from types import SimpleNamespace
    lib = ai_replay.Library(tmp_path / "lib")
    key = ai_replay._key("원인 진단")
    lib.root.mkdir(parents=True)
    doc = {"format": ai_replay.FORMAT, "step": "원인 진단", "case": "", "recorded_at": "-", "runs": [
        {"session_id": "s1", "events": []}, {"session_id": "s1", "events": []},
        {"session_id": "s2", "events": [], "attempt": {"generation": 0, "reassessment": 1}}]}
    lib.file_of(key).write_bytes(gzip.compress(json.dumps(doc).encode("utf-8")))
    ask = lambda n: SimpleNamespace(prompt="", workdir=str(tmp_path), resume_session=f"replay:{key}:{n}")   # noqa: E731
    assert lib.find(ask(0))[1] == 1                                    # 첫 차례 안의 이어 하기
    assert lib.find(ask(1))[1] == 3                                    # 다음 실행은 재평가 차례 → 없음(실행 수)
    fresh = SimpleNamespace(prompt="## 업무\n원인 진단\n", workdir=str(tmp_path), resume_session=None)
    assert lib.find(fresh, (0, 1))[1] == 2 and lib.find(fresh, (0, 2))[1] == 3 and lib.find(fresh, (0, 0))[1] == 0


def test_worker_default_mode_is_live_without_ai_mode_env(monkeypatch):
    """교실 워커는 원본 키를 환경에 두지 않는다. AI_MODE 를 안 주면 재생이 아니라 실제 AI로 켜져야 한다(2026-10-28 회귀)."""
    import importlib
    monkeypatch.delenv("AI_MODE", raising=False)
    import worker.settings as ws
    assert importlib.reload(ws).Settings().ai_mode == "live"


# ---------------------------------------------------------------- 키 없는 교실 PC(2026-10-28 K1): 재생은 실행 토큰을 받지 않는다
def _managed_attach(calls, token="HydModel tok-managed-run-0123456789"):
    def attach(row, tenant_id, provider_id):
        calls.append(row["id"])
        return {"model": "coding", "env": {"ANTHROPIC_API_KEY": token}, "secrets": [token], "deadline": None}
    return attach


def test_replay_never_asks_process_for_a_model_runtime_token(tmp_path, monkeypatch):
    from worker import managed_isolation, managed_model
    monkeypatch.setattr(managed_isolation, "cli_args", lambda *a, **k: [])
    calls = []
    monkeypatch.setattr(managed_model, "attach", _managed_attach(calls))
    lib = ai_replay.Library(tmp_path / "lib")
    _record(tmp_path, lib, _fake_exec(ANSWER))
    assert len(calls) == 1                                # 녹화는 실제 AI — 실행 토큰을 받는다
    def no_key_pc(*args, **kwargs):                       # 키 없는 PC: process 가 실행 토큰을 줄 수 없다
        raise AssertionError("replay asked process for a model runtime token")
    monkeypatch.setattr(managed_model, "attach", no_key_pc)
    repo, inst, row = _replay(tmp_path, lib)
    assert row["status"] == "SUBMITTED" and row["output"]["cause"] == "cause:cooler-fin-fouling"


def test_per_run_model_token_given_to_the_cli_is_never_saved(tmp_path, monkeypatch):
    # 교실 워커는 원본 키 없이 작업마다 실행 토큰을 CLI 환경으로 받는다 — 워커가 켜질 때의 환경에는 없다
    from worker import managed_isolation, managed_model
    monkeypatch.setattr(managed_isolation, "cli_args", lambda *a, **k: [])
    monkeypatch.setattr(managed_model, "attach", _managed_attach([]))
    lib = ai_replay.Library(tmp_path / "lib")
    _record(tmp_path, lib, _fake_exec(ANSWER.replace("cooler-fin-fouling", "tok-managed-run-0123456789")))
    [path] = list((tmp_path / "lib").glob("*.json.gz"))
    saved = gzip.decompress(path.read_bytes()).decode("utf-8")
    assert "tok-managed-run-0123456789" not in saved and "********" in saved


# ---------------------------------------------------------------- 온라인 질문은 강의에서 다룬 질문만(2026-10-29)
def test_keyless_pc_answers_only_the_questions_recorded_in_class(tmp_path):
    asked = {"q": "질문 냉각 경보 원인은"}
    case_of = lambda pid: asked["q"]
    lib = ai_replay.Library(tmp_path / "lib", case_of=case_of)
    _record(tmp_path, lib, _fake_exec(ANSWER))
    repo, inst, row = _replay(tmp_path, lib)                            # 같은 질문: 저장된 답
    assert row["status"] == "SUBMITTED" and row["output"]["cause"] == "cause:cooler-fin-fouling"
    asked["q"] = "질문 우리 회사 매출은"
    repo, inst, row = _replay(tmp_path, lib)                            # 다른 질문: 지어내지 않고 다룬 질문을 알린다
    text = _texts(repo, row)
    assert row["status"] != "SUBMITTED"
    assert "강의에서 다룬 질문에만" in text and "냉각 경보 원인은" in text
