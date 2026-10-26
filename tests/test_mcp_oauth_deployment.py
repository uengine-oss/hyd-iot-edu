"""Deployment keeps OAuth credentials out of logs and never rotates keys silently."""
import importlib.util
import logging
from pathlib import Path

import pytest

from procsvc.oauth_access_log import CallbackFilter, install

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('hyd_mcp_key_setup', ROOT / 'scripts/setup_mcp_oauth_keys.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


def test_managed_worker_receives_only_runtime_secret_not_process_archive():
    import yaml
    config = yaml.safe_load((ROOT / 'compose.classroom.yaml').read_text(encoding='utf8'))
    worker = config['services']['agent-worker']
    process = config['services']['process']
    assert not worker.get('volumes')  # Never add process-data to base worker-data.
    assert worker['secrets'] == ['classroom_worker_runtime']
    assert set(process['secrets']) == {'classroom_upstream', 'classroom_worker_runtime'}
    key_path = '/run/secrets/classroom_worker_runtime'
    assert worker['environment']['HYD_WORKER_RUNTIME_KEY_FILE'] == key_path
    assert process['environment']['HYD_WORKER_RUNTIME_KEY_FILE'] == key_path
    assert 'HYD_CLASSROOM_WORKER_KEY_FILE:?' in config['secrets']['classroom_worker_runtime']['file']


def test_callback_access_log_never_contains_authorization_code():
    record = logging.LogRecord('uvicorn.access', logging.INFO, '', 0,
        '%s - "%s %s HTTP/%s" %d', ('client', 'GET', '/api/mcp/connections/callback?code=private-code&state=private-state', '1.1', 200), None)
    assert CallbackFilter().filter(record) is False
    record.args = ('client', 'GET', '/api/mcp/connections', '1.1', 200)
    assert CallbackFilter().filter(record) is True


def test_log_filter_installs_once():
    install()
    install()
    assert sum(isinstance(item, CallbackFilter) for item in logging.getLogger('uvicorn.access').filters) == 1


def test_keys_persist_and_are_not_in_report(tmp_path):
    directory = tmp_path / 'private'
    first = setup.provision(directory)
    originals = {p.name: p.read_bytes() for p in directory.iterdir()}
    second = setup.provision(directory)
    assert all(item['created'] for item in first['files'])
    assert all(not item['created'] for item in second['files'])
    assert originals == {p.name: p.read_bytes() for p in directory.iterdir()}
    assert all(value.strip().decode() not in str(first) + str(second) for value in originals.values())
    assert originals['oauth.key'] != originals['worker-runtime.key']


def test_keys_refuse_git_checkout(tmp_path):
    (tmp_path / '.git').write_text('gitdir: another-worktree', encoding='utf-8')
    with pytest.raises(ValueError, match='outside Git'):
        setup.provision(tmp_path / 'keys')
    assert not (tmp_path / 'keys').exists()


def test_invalid_existing_key_is_never_replaced(tmp_path):
    (tmp_path / 'oauth.key').write_bytes(b'invalid existing key')
    with pytest.raises(ValueError):
        setup.provision(tmp_path)
    assert (tmp_path / 'oauth.key').read_bytes() == b'invalid existing key'
