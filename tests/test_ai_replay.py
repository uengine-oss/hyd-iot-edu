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
    monkeypatch.setattr(main, "settings", replace(s, ai_mode="live"))
    assert main.build_runner(MemoryRepo()).exec_fn is runner_mod._exec_stream


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
    put("p.ask", {"question": "?"})
    case = ai_replay.case_of_instance(repo)
    assert case("p.cooler") == "COOLER_DEGRADATION" and case("p.ask") == "" and case("missing") == ""
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
