"""New extraction versions follow explicit deployment selection; old pins remain."""
import copy
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import pytest

from procsvc import manual_extraction as extraction
from test_manual_extraction import document, rt
from test_worker import _settings, _fake_exec
from worker.runner import Runner


SNAPSHOTS = Path(__file__).parent / 'fixtures' / 'extraction-definitions'
# 2.2: git HEAD (2190a84 definition), 2.3: captured before the 2.4 change and
# compared with the registered live API definition on 2026-10-12. These are
# independent historical fixtures, never built from the current definition.
SNAPSHOT_HASHES = {
    '2.2': '0255073309e47fc24c0829027d12ec9486a90e6ab280e30161e208df14a19a8e',
    '2.3': 'a4bf8df1fbdc7fc32ab2ae96135836241703e77505d1ba3651b9aa2660e0b6f0',
}


def historical_definition(version):
    raw = (SNAPSHOTS / ('manual_extraction_v' + version.replace('.', '') + '.json')).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SNAPSHOT_HASHES[version]
    definition = json.loads(raw)
    assert definition['version'] == version
    return definition


@pytest.mark.parametrize('provider', ['codex', 'claude-code'])
def test_new_extraction_follows_deployment_without_rewriting_prior_version(rt, document, tmp_path, provider):
    runtime, _ = rt
    _, source, proposal = document
    before = {}
    for version in SNAPSHOT_HASHES:
        runtime.register_definition(historical_definition(version))
        before[version] = copy.deepcopy(runtime.repo.get_proc_def(extraction.DEFINITION_ID, 'hyd', version=version))
    inst = extraction.start(runtime, source, str(uuid4()))
    seen = []

    def resolve(name):
        seen.append(name)
        return object()

    runner = Runner(_settings(tmp_path / 'worker', cli_agent=provider), runtime.repo,
                    exec_fn=_fake_exec(json.dumps({'proposal': proposal})),
                    schema_prompt='ManualSection Skill Step', resolve_provider=resolve)
    assert runner.poll_once() == 1
    assert seen == [provider]
    assert runtime.poll_once() == 1
    assert extraction.result(runtime, source, inst['proc_inst_id'], None)['status'] == 'DONE'
    assert inst['version'] == extraction.VERSION == '2.13'
    for version, snapshot in before.items():
        assert runtime.repo.get_proc_def(extraction.DEFINITION_ID, 'hyd', version=version) == snapshot
    assert 'agentConfig' not in extraction.definition()['activities'][0]


def test_registered_23_work_remains_pinned_and_readable_after_24_starts(rt, document, tmp_path):
    from worker.context import prepare

    runtime, _ = rt
    _, source, proposal = document
    old = historical_definition('2.3')
    runtime.register_definition(old)
    inst = runtime.start_definition(extraction.DEFINITION_ID, '2.3', 'old-extraction', values={'manual_source': source})
    old_row = runtime.repo.list_workitems(proc_inst_id=inst['proc_inst_id'])[0]
    old_query = old_row['query']
    assert old['activities'][0]['instruction'] in old_query
    current = extraction.start(runtime, source, str(uuid4()))
    assert current['version'] == extraction.VERSION == '2.13'
    assert prepare(runtime.repo, old_row, 'hyd').definition == old
    assert runtime.repo.get_workitem(old_row['id'])['query'] == old_query

    runner = Runner(_settings(tmp_path / 'worker', cli_agent='codex'), runtime.repo,
                    exec_fn=_fake_exec(json.dumps({'proposal': proposal})),
                    schema_prompt='ManualSection Skill Step', resolve_provider=lambda _: object())
    # The worker claims one work item per poll; finish both pinned versions.
    assert runner.poll_once() == 1
    assert runner.poll_once() == 1
    assert runtime.poll_once() == 2
    assert extraction.result(runtime, source, inst['proc_inst_id'], None)['status'] == 'DONE'
    assert extraction.result(runtime, source, current['proc_inst_id'], None)['status'] == 'DONE'
    assert runtime.repo.get_proc_def(extraction.DEFINITION_ID, 'hyd', version='2.3')['definition'] == old


@pytest.mark.parametrize('version', ['2.2', '2.3'])
def test_registered_historical_version_rejects_new_instruction(rt, version):
    runtime, _ = rt
    old = historical_definition(version)
    runtime.register_definition(old)
    changed = copy.deepcopy(old)
    changed['activities'][0]['instruction'] = extraction.INSTRUCTION
    with pytest.raises(ValueError, match='새 버전'):
        runtime.register_definition(changed)
    assert runtime.repo.get_proc_def(extraction.DEFINITION_ID, 'hyd', version=version)['definition'] == old
