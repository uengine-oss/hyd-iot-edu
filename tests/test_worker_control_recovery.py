"""Actual runner state transitions after invalid control replies, refusals and a lost worker."""
import json
from dataclasses import replace

import pytest
from cliagents import ExecEvent, ExecEventKind

from worker.runner import Runner
from test_worker import _repo, _settings, _fake_exec


@pytest.mark.parametrize('allowed', [None, [], ['Read', 'Bash(python *)', 'PowerShell(python *)']])
def test_actual_cli_request_cannot_preapprove_shell_bypass(tmp_path, allowed):
    repo, _ = _repo()
    requests = []
    settings = _settings(tmp_path)
    if allowed is not None:
        settings = replace(settings, allowed_tools=allowed)
    Runner(settings, repo, exec_fn=_fake_exec('{"cause":"c","failure_mode":"f","guide_card":{"x":1}}', requests=requests),
           schema_prompt='s', resolve_provider=lambda _: object()).poll_once()
    flags = requests[0][0].extra_args
    assert {'Bash', 'PowerShell'} <= set(flags[flags.index('--disallowedTools') + 1].split(','))
    if '--allowedTools' in flags:
        assert not any(x.startswith(('Bash', 'PowerShell')) for x in flags[flags.index('--allowedTools') + 1].split(','))


@pytest.mark.parametrize('bad', [{'__human_input__': {'question': ''}},
                                 {'__deferred__': {'status': 'UNKNOWN', 'reason': '', 'evidence': {}}}])
def test_invalid_control_reply_is_corrected_in_same_session(tmp_path, bad):
    repo, inst = _repo()
    calls = []
    def execute(provider, request, env):
        calls.append(request)
        reply = bad if len(calls) == 1 else {'__human_input__': {'question': '센서 상태를 확인해 주세요'}}
        yield from _fake_exec(json.dumps(reply, ensure_ascii=False))(provider, request, env)
    Runner(_settings(tmp_path), repo, exec_fn=execute, schema_prompt='s', resolve_provider=lambda _: object()).poll_once()
    row = repo.list_workitems(proc_inst_id=inst['proc_inst_id'])[0]
    assert row['draft_status'] == 'HUMAN_ASKED' and row['output'] is None
    assert len(calls) == 2 and calls[1].resume_session == 'sess-A'
    assert '센서 상태' in row['draft']['_human_request']['question']


@pytest.mark.parametrize('valid_result', [False, True])
def test_tool_approval_refusal_with_apology_pauses_without_format_retries(tmp_path, valid_result):
    repo, inst = _repo()
    calls = []
    def execute(provider, request, env):
        calls.append(request)
        yield ExecEvent(kind=ExecEventKind.RUN_START, session_id='session-refused')
        yield ExecEvent(kind=ExecEventKind.TOOL_END, tool='Bash', tool_use_id='blocked', is_error=True,
                        text='This tool requires approval', session_id='session-refused')
        yield ExecEvent(kind=ExecEventKind.RESULT, session_id='session-refused',
                        text='{"cause":"c","failure_mode":"f","guide_card":{"x":1}}' if valid_result else '권한이 없어 수행하지 못했습니다.')
    Runner(_settings(tmp_path), repo, exec_fn=execute, schema_prompt='s', resolve_provider=lambda _: object()).poll_once()
    row = repo.list_workitems(proc_inst_id=inst['proc_inst_id'])[0]
    assert len(calls) == 1
    assert row['draft_status'] == ('COMPLETED' if valid_result else 'HUMAN_ASKED')


def test_reclaimed_worker_resumes_session_saved_before_abrupt_exit(tmp_path):
    repo, inst = _repo()
    class AbruptExit(BaseException):
        pass
    def crash(provider, request, env):
        yield ExecEvent(kind=ExecEventKind.RUN_START, session_id='session-before-kill')
        raise AbruptExit()
    runner = Runner(_settings(tmp_path), repo, exec_fn=crash, schema_prompt='s', resolve_provider=lambda _: object())
    with pytest.raises(AbruptExit):
        runner.poll_once()
    row = repo.list_workitems(proc_inst_id=inst['proc_inst_id'])[0]
    assert row['draft_status'] == 'STARTED' and row['consumer']
    assert row['draft']['cliagents_session_id'] == 'session-before-kill'
    old_consumer = row['consumer']
    repo.update_workitem(dict(row, lease_until=0))
    requests = []
    again = Runner(replace(_settings(tmp_path), consumer='replacement'), repo,
                   exec_fn=_fake_exec('{"cause":"c","failure_mode":"f","guide_card":{"x":1}}', requests=requests),
                   schema_prompt='s', resolve_provider=lambda _: object())
    assert again.poll_once() == 1
    assert requests[0][0].resume_session == 'session-before-kill'
    finished = repo.get_workitem(row['id'])
    assert finished['status'] == 'SUBMITTED' and finished['claim_count'] == 2
    assert not repo.save_task_result(row['id'], {'cliagents_session_id': 'stale'}, final=False, expected_consumer=old_consumer)
    assert repo.get_workitem(row['id'])['output']['cliagents_session_id'] != 'stale'
