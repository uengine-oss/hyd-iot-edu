"""W4 (2026-10-23 검수): 폼이 없는(자유형식) 에이전트 단계에서 CLI가 아무 글도 내지 않으면 성공이 아니라 「결과 없음」이다."""
from dataclasses import replace

from cliagents import ExecEvent, ExecEventKind

from worker import context, outcome
from worker.runner import Runner

from test_worker import _repo, _settings


def test_empty_text_without_a_form_is_not_a_result():
    for fields in (None, [], context.FREEFORM_FIELDS):
        empty = outcome.interpret("  \n", fields)
        assert empty.contract_met is False and empty.mismatch_reason == outcome.NO_RESULT
        assert outcome.interpret("점검을 마쳤습니다.", fields).contract_met is True


def test_a_freeform_step_whose_cli_returned_nothing_fails_instead_of_submitting_empty_text(tmp_path, monkeypatch):
    repo, inst = _repo()
    real = context.prepare
    monkeypatch.setattr(context, "prepare", lambda *a, **k: replace(real(*a, **k), form_fields=context.FREEFORM_FIELDS))
    rounds = []

    def fn(provider, request, env):
        rounds.append(request.prompt)
        yield ExecEvent(kind=ExecEventKind.RUN_START, text="claude", session_id="sess-E")
        yield ExecEvent(kind=ExecEventKind.RESULT, text="", session_id="sess-E")
    r = Runner(_settings(tmp_path), repo, exec_fn=fn, schema_prompt="# s", resolve_provider=lambda pid: object())
    assert r.poll_once() == 1
    row = next(w for w in repo.list_workitems(proc_inst_id=inst["proc_inst_id"]) if w["activity_id"] == "task:diagnose")
    assert row["status"] == "IN_PROGRESS" and row["draft_status"] == "FAILED"          # not SUBMITTED with {"text": ""}
    assert len(rounds) == 1 + r.s.max_format_corrections                                 # asked again in the same session first
    errors = [e for e in repo.list_events(todo_id=row["id"]) if e["event_type"] == "error"]
    assert errors and outcome.NO_RESULT in errors[-1]["data"]["raw_error"]
