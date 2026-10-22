"""AI 응답 저장 · 재생(worker/ai_replay.py): API 키 없는 워커가 AI가 응답할 단계에만 미리 저장한 응답을 넣고,
나머지(결과 검사 · 저장 · 처리 과정 이벤트)는 실제 실행과 같은 Runner 코드로 처리하는지. 가짜 CLI · MemoryRepo 로 돈다.
규칙: 업무 이름이 같으면 저장된 응답을 쓴다(입력 · 지시문이 달라도). 업무 하나에 파일 하나."""
import json
from pathlib import Path

import pytest

from procsvc import engine
from procsvc.procdb import MemoryRepo
from worker import ai_replay
from worker import runner as runner_mod
from worker.runner import Runner
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
    assert "AI 응답 재생: 「원인 진단」 — 미리 저장한 응답입니다" in texts and "새로 추론한 것이 아닙니다" in texts
    assert "강사" not in texts


def test_no_saved_response_for_the_business_step_fails_instead_of_inventing_one(tmp_path):
    lib = ai_replay.Library(tmp_path / "lib")
    _record(tmp_path, lib, _fake_exec(ANSWER))
    [doc] = lib.docs()                                     # 다른 업무의 저장분만 있다
    lib.path_of("원인 진단").rename(lib.path_of("조치 후보"))
    lib.path_of("조치 후보").write_text(json.dumps(doc | {"step": "조치 후보"}, ensure_ascii=False), encoding="utf-8")
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
    assert len(list((tmp_path / "lib").glob("*.json"))) == 1 and "fan-drive-fault" in json.dumps(doc["runs"])


def test_saved_response_that_breaks_the_result_contract_fails_like_a_live_run(tmp_path):
    lib = ai_replay.Library(tmp_path / "lib")
    _record(tmp_path, lib, _fake_exec("원인은 쿨러입니다 (JSON 없음)"))
    repo, inst = _repo()
    _runner(tmp_path, repo, ai_replay.replaying(lib), "replay").poll_once()
    row = _diagnose(repo, inst)
    # 실제 실행처럼 형식 교정을 요청하지만, 교정 응답은 저장된 적이 없으니 지어내지 않고 실패한다
    assert row["draft_status"] == "FAILED" and row["output"] is None
    assert "이어지는 응답의 저장된 AI 응답이 없습니다" in repo.list_events(todo_id=row["id"])[-1]["data"]["raw_error"]


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
    monkeypatch.setattr(ai_replay, "_SECRET_VALUES", ["sk-test-secret-value-123"])
    lib = ai_replay.Library(tmp_path / "lib")
    _record(tmp_path, lib, _fake_exec('{"cause": "sk-test-secret-value-123", "failure_mode": "f", "guide_card": {}}'))
    assert lib.docs() == []


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


@pytest.mark.parametrize("mode,login,expected", [("auto", False, "replay"), ("auto", None, "live"), ("auto", True, "live"),
                                                 ("replay", True, "replay"), ("live", False, "live"), ("record", False, "record")])
def test_mode_resolution_switches_to_replay_only_when_login_is_known_missing(mode, login, expected):
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
