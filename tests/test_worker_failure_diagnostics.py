import importlib.util
from pathlib import Path

import pytest

from worker.diagnostics import excerpt
from worker.runner import Runner, RunFailed
from test_worker import _repo, _settings


def test_error_record_keeps_start_and_fatal_tail_and_masks_credentials(tmp_path):
    repo, inst = _repo()
    row = repo.fetch_pending_task('cliagents', 'owner')[0]
    message = ('CLI exit 1: credential store warning ' + 'warning ' * 400
               + ' password="not-for-log" postgres://user:private@host/db Authorization: Bearer abc123'
               + '\nFatal: required MCP server neo4j failed to initialize: uvx not found')
    runner = Runner(_settings(tmp_path), repo, schema_prompt='')
    runner._fail(row, 'job', RunFailed(message))
    raw = repo.list_events(todo_id=row['id'])[-1]['data']['raw_error']
    assert raw.startswith('RunFailed: CLI exit 1:') and len(raw) <= 800
    assert 'required MCP server neo4j failed to initialize: uvx not found' in raw
    assert all(secret not in raw for secret in ('not-for-log', 'private', 'abc123'))
    assert repo.get_workitem(row['id'])['draft_status'] == 'FAILED'


def test_redaction_precedes_truncation_and_preserves_plain_error():
    text = 'API_KEY=' + 'secretvalue' * 200 + '\nFatal: missing executable'
    out = excerpt(text, 150)
    assert 'secretvalue' not in out and 'Fatal: missing executable' in out
    assert excerpt('missing executable') == 'missing executable'


@pytest.mark.parametrize('state', ['FAILED', 'CANCELLED'])
def test_live_approval_wait_exits_immediately_on_terminal_draft(monkeypatch, state):
    path = Path(__file__).resolve().parents[1] / 'scripts/approval_stage_live.py'
    spec = importlib.util.spec_from_file_location('approval_stage_live_test', path)
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    reads = []

    def get(path):
        reads.append(path)
        return {'instance': {'status': 'RUNNING'}, 'workitems': [
            {'activity_id': 'T_agent', 'status': 'IN_PROGRESS', 'draft_status': state}]}

    monkeypatch.setattr(script, 'get', get)
    monkeypatch.setattr(script.time, 'sleep', lambda _: pytest.fail('terminal failure must not sleep'))
    with pytest.raises(SystemExit) as error:
        script.wait_approval('instance')
    assert error.value.code == 2 and len(reads) == 1
