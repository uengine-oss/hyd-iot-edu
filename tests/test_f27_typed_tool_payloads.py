"""Recorded B/C outputs cross the producer, immutable journal and authorized read API."""
import hashlib
import json
from pathlib import Path

import pytest
from cliagents import ExecEvent, ExecEventKind
from procsvc import engine, instances
from worker import events, payloads
from test_a161_trace_gaps import _client, _payload_repo, _runner, instance_mode_def, skill_start


FIXTURE = json.loads((Path(__file__).parent / 'fixtures/actual_tool_payloads_followup.json').read_text(encoding='utf-8'))
RECORDS = list(FIXTURE['payloads'].values())


def _original(record):
    text = ''.join(chunk['content'] for chunk in record['chunks'])
    assert hashlib.sha256(text.encode()).hexdigest() == record['reference']['sha256']
    return json.loads(text)


def _produce(tmp_path, original, *, fail_storage=False):
    repo = _payload_repo()
    inst = skill_start(repo, repo._defn)
    if fail_storage:
        def unavailable(_):
            raise OSError('journal unavailable')
        repo.store_event_payload = unavailable
    def calls(_):
        yield ExecEvent(kind=ExecEventKind.TOOL_START, tool='recorded/tool', tool_use_id='recorded', tool_input={})
        yield ExecEvent(kind=ExecEventKind.TOOL_END, tool='recorded/tool', tool_use_id='recorded', tool_output=original)
    assert _runner(tmp_path, repo, calls).poll_once() == 1
    row = next(e for e in repo.events if e['event_type'] == 'tool_usage_finished')
    runtime = instances.InstanceRuntime(repo, engine.Definition.load(instance_mode_def()), instances.Hooks())
    return repo, inst, row['data'], runtime


@pytest.mark.parametrize('record', RECORDS, ids=lambda r: r['case'] + ':' + r['tool'] + ':' + r['event_id'][:8])
def test_recorded_objects_preserve_typed_original_through_runner_and_chunk_api(record, tmp_path, monkeypatch):
    original = _original(record)
    serialized = json.dumps(original, ensure_ascii=False, default=str)
    repo, inst, data, runtime = _produce(tmp_path, original)
    assert data['output_truncated'] is True
    assert data['output'] == {'kind': 'tool_output_preview', 'truncated': True,
                              'original_chars': len(serialized), 'content_type': 'json'}
    reference = data['full_output']
    assert reference['stored'] and not reference['cut']
    assert reference['original_chars'] == len(serialized) == reference['chars']
    digest = hashlib.sha256(serialized.encode()).hexdigest()
    assert reference['sha256'] == digest
    assert reference['ref'] == payloads.payload_id(inst['proc_inst_id'], digest)
    client = _client(runtime, monkeypatch)
    offset, chunks = 0, []
    while True:
        response = client.get(f"/api/event-payloads/{reference['ref']}?offset={offset}&limit=7000")
        assert response.status_code == 200
        page = response.json()
        assert page['offset'] == offset and page['id'] == reference['ref']
        assert page['meta']['content_sha256'] == digest and page['proc_inst_id'] == inst['proc_inst_id']
        chunks.append(page['content'])
        if page['next_offset'] is None:
            break
        assert page['next_offset'] == offset + len(page['content'])
        offset = page['next_offset']
    restored = ''.join(chunks)
    assert restored == serialized and json.loads(restored) == original
    # A duplicate preserves the first immutable stored original.
    saved = repo.get_event_payload(reference['ref'])
    repo.store_event_payload(dict(saved, content='changed'))
    assert repo.get_event_payload(reference['ref'])['content'] == serialized


@pytest.mark.parametrize('value', [None, False, 0, '', [], {}, {'result': 'error', 'message': '거절'}, [{'type': 'image'}]])
def test_small_and_unknown_values_remain_original_without_claiming_success(value):
    data = events.translate(ExecEvent(kind=ExecEventKind.TOOL_END, tool_output=value))[0].data
    assert data['output'] == value and data['output_truncated'] is False


def test_json_length_drives_preview_and_storage_with_unicode_and_boolean_boundary(monkeypatch):
    original = {'emoji': '😀', 'flag': True, 'missing': None}
    size = len(json.dumps(original, ensure_ascii=False, default=str))
    monkeypatch.setattr(events, 'PREVIEW_MAX', size)
    assert events._truncate(original) == original and not events.preview_cut(original)
    monkeypatch.setattr(events, 'PREVIEW_MAX', size - 1)
    marker = events._truncate(original)
    assert marker['original_chars'] == size and events.preview_cut(original)
    captured = payloads.capture(original, preview_cut=events.preview_cut(original))
    assert json.loads(captured['content']) == original and len(captured['content']) == size


def test_string_preview_explicitly_marks_truncation_and_preserves_original(tmp_path):
    original = '원문😀' * 3000
    repo, _, data, _ = _produce(tmp_path, original)
    assert data['output_truncated'] is True and data['output'].endswith('(생략됨)')
    assert repo.get_event_payload(data['full_output']['ref'])['content'] == original


def test_storage_failure_is_explicit_and_never_references_missing_original(tmp_path):
    original = _original(RECORDS[0])
    repo, _, data, _ = _produce(tmp_path, original, fail_storage=True)
    assert data['output_truncated'] is True
    assert data['full_output']['stored'] is False and data['full_output']['ref'] is None
    assert 'journal unavailable' in data['full_output']['error'] and not repo.event_payloads


def test_payload_read_rejects_foreign_deleted_and_orphan_ownership(tmp_path, monkeypatch):
    repo, inst, data, runtime = _produce(tmp_path, _original(RECORDS[0]))
    ref = data['full_output']['ref']
    other = instances.InstanceRuntime(repo, runtime.defn, instances.Hooks(), tenant_id='other')
    assert _client(other, monkeypatch).get(f'/api/event-payloads/{ref}').status_code == 404
    client = _client(runtime, monkeypatch)
    repo.instances[inst['proc_inst_id']]['is_deleted'] = True
    assert client.get(f'/api/event-payloads/{ref}').status_code == 404
    repo.instances[inst['proc_inst_id']]['is_deleted'] = False
    repo.event_payloads[ref]['proc_inst_id'] = None
    assert client.get(f'/api/event-payloads/{ref}').status_code == 404


def test_payload_cap_remains_explicitly_incomplete_not_parseable_success(tmp_path, monkeypatch):
    original = _original(RECORDS[0])
    monkeypatch.setattr(payloads, 'MAX_CHARS', 20)
    repo, _, data, runtime = _produce(tmp_path, original)
    ref = data['full_output']
    assert ref['stored'] and ref['cut'] and ref['chars'] == 20 < ref['original_chars']
    page = _client(runtime, monkeypatch).get(f"/api/event-payloads/{ref['ref']}").json()
    assert page['meta']['cut'] and page['next_offset'] is None
    assert page['content'] == repo.get_event_payload(ref['ref'])['content']
    with pytest.raises(json.JSONDecodeError):
        json.loads(page['content'])


def test_identical_body_reused_in_same_case_keeps_first_origin_and_remains_readable(tmp_path, monkeypatch):
    original = _original(RECORDS[0])
    repo, inst, first, runtime = _produce(tmp_path, original)
    first_ref = first['full_output']['ref']
    saved = repo.get_event_payload(first_ref)
    event = ExecEvent(kind=ExecEventKind.TOOL_END, tool='another/tool', tool_use_id='later-call', tool_output=original)
    later = _runner(tmp_path, repo, lambda _: iter(()))._keep_full_output(
        events.translate(event)[0], event, {'id': 'later-task', 'proc_inst_id': inst['proc_inst_id']}, 'later-job')
    assert later.data['full_output']['ref'] == first_ref
    assert repo.get_event_payload(first_ref) == saved
    page = _client(runtime, monkeypatch).get(f'/api/event-payloads/{first_ref}').json()
    assert page['job_id'] == saved['job_id'] != 'later-job'
    assert page['todo_id'] == saved['todo_id'] != 'later-task'
    assert page['tool'] == saved['tool'] != 'another/tool'
    assert page['content'] and page['proc_inst_id'] == inst['proc_inst_id']
