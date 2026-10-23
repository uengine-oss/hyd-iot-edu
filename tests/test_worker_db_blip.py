"""W3 (2026-10-23 검수): 실행 중 취소 확인 · 처리 과정 기록의 일시적인 DB 오류 한 번이 살아 있는 실행을 끝내지 않는다
(리스 갱신처럼 다음 주기에 다시 한다). 오류가 db_outage_limit_s 동안 이어지면 사유와 함께 실패한다."""
import time
from dataclasses import replace

import pytest
from cliagents import ExecEvent, ExecEventKind, ExecRequest
from procsvc.procdb import MemoryRepo
from worker.runner import Runner, RunFailed
from worker.settings import Settings

from test_worker_process_control import setup_run


def _flaky(real, fail_on):
    state = {"n": 0}

    def call(*a, **k):
        state["n"] += 1
        if fail_on(state["n"]):
            raise ConnectionError("server closed the connection unexpectedly")
        return real(*a, **k)
    return call, state


def test_one_transient_db_error_in_the_cancel_check_does_not_end_a_live_run(tmp_path):
    runner, repo, row, provider, request = setup_run(tmp_path, timeout=10)
    repo.get_workitem, state = _flaky(repo.get_workitem, lambda n: n == 3)
    text, _, _ = runner._stream(row, "job", provider, request, None, "test")
    assert state["n"] > 3                                       # the check went on after the error
    assert '"answer":"late"' in text.replace(" ", "")          # the 3 s CLI finished and its answer came back


def test_a_db_outage_that_lasts_stops_the_run_with_its_reason(tmp_path):
    runner, repo, row, provider, request = setup_run(tmp_path, timeout=10)
    runner.s = replace(runner.s, db_outage_limit_s=.3)
    repo.get_workitem, _ = _flaky(repo.get_workitem, lambda n: n >= 2)
    started = time.monotonic()
    with pytest.raises(RunFailed, match="업무 DB에 .*취소 확인.*ConnectionError"):
        runner._stream(row, "job", provider, request, None, "test")
    assert time.monotonic() - started < 2.5                     # stopped before the 3 s CLI finished, by the limit


def _fake_run(tmp_path, *, limit=90.0):
    repo = MemoryRepo()
    row = {"id": "w3", "proc_inst_id": "p-w3", "activity_id": "t", "status": "IN_PROGRESS", "draft_status": "STARTED",
           "consumer": "c", "tenant_id": "hyd", "start_date": "2026-10-04T00:00:00Z"}
    repo.insert_workitems([row])

    def fn(provider, request, env):
        yield ExecEvent(kind=ExecEventKind.RUN_START, text="claude", session_id="s")
        yield ExecEvent(kind=ExecEventKind.TOOL_START, tool="mcp__neo4j__read_neo4j_cypher", tool_input={"query": "q"}, tool_use_id="t1", session_id="s")
        yield ExecEvent(kind=ExecEventKind.TOOL_END, tool="mcp__neo4j__read_neo4j_cypher", text="[1]", tool_use_id="t1", session_id="s")
        yield ExecEvent(kind=ExecEventKind.RESULT, text="끝", session_id="s")
    runner = Runner(Settings(consumer="c", workspace_root=tmp_path, cancel_check_every_s=0, db_outage_limit_s=limit), repo, exec_fn=fn,
                    schema_prompt="")
    return runner, repo, row


def test_a_progress_row_that_could_not_be_written_is_written_with_the_next_event(tmp_path):
    runner, repo, row = _fake_run(tmp_path)
    repo.record_events, state = _flaky(repo.record_events, lambda n: n == 1)
    text, _, _ = runner._stream(row, "job", object(), ExecRequest(prompt="x", workdir=str(tmp_path)), None, "cliagents:claude-code")
    assert text == "끝" and state["n"] >= 2
    kinds = [e["event_type"] for e in repo.list_events(todo_id="w3")]
    assert "tool_usage_started" in kinds and "tool_usage_finished" in kinds       # the first event's row was not lost


def test_a_final_cancel_check_db_error_leaves_the_decision_to_the_fenced_result_write(tmp_path):
    runner, repo, row = _fake_run(tmp_path)
    real = repo.get_workitem
    calls = {"n": 0}

    def last_fails(wid):
        calls["n"] += 1
        frame = __import__("sys")._getframe(1)
        if frame.f_code.co_name == "_cancelled" and frame.f_back.f_code.co_name == "_stream":
            raise ConnectionError("blip at the end")
        return real(wid)
    repo.get_workitem = last_fails
    text, _, _ = runner._stream(row, "job", object(), ExecRequest(prompt="x", workdir=str(tmp_path)), None, "cliagents:claude-code")
    assert text == "끝"
