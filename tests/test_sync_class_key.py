"""One local class key configures the existing offline lab without exposing it."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'sync_class_key.py'
spec = importlib.util.spec_from_file_location('sync_class_key', SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def lab(root):
    path = root / 'course' / 'labs' / 'offline' / '05-2-cause-agent'
    path.mkdir(parents=True)
    return path


def test_sync_updates_only_three_values_and_is_idempotent(tmp_path):
    root = tmp_path / '교실 PC'; root.mkdir()
    path = lab(root)
    (root / '.env').write_text('OPENAI_BASE_URL=https://relay.example/v1\nLLM_API_KEY="fixture-key"\nLLM_MODEL=coding\n', encoding='utf8')
    target = path / '.env'
    target.write_text('# keep comment\nOTHER_SETTING=keep\nLLM_API_KEY=old\nLLM_API_KEY=duplicate\n', encoding='utf8')
    assert mod.sync(root) == 'updated'
    text = target.read_text(encoding='utf8')
    assert '# keep comment\nOTHER_SETTING=keep\n' in text
    assert mod.values(text) == {'OTHER_SETTING':'keep', 'OPENAI_BASE_URL':'https://relay.example/v1',
                                'LLM_API_KEY':'fixture-key', 'LLM_MODEL':'coding'}
    assert text.count('LLM_API_KEY=') == 1
    assert mod.sync(root) == 'unchanged'
    assert not list(path.glob('.env.sync-*'))


def test_missing_values_and_managed_credential_never_overwrite_lab(tmp_path):
    path = lab(tmp_path); target = path / '.env'; target.write_text('LLM_API_KEY=existing\n', encoding='utf8')
    (tmp_path / '.env').write_text('OPENAI_BASE_URL=https://relay.example/v1\nLLM_MODEL=coding\n', encoding='utf8')
    with pytest.raises(ValueError):
        mod.sync(tmp_path)
    assert target.read_text(encoding='utf8') == 'LLM_API_KEY=existing\n'
    (tmp_path / '.env').write_text('HYD_CLASSROOM_URL=https://example.test\nLLM_API_KEY=managed-token\n', encoding='utf8')
    assert mod.sync(tmp_path) == 'managed'
    assert target.read_text(encoding='utf8') == 'LLM_API_KEY=existing\n'


def test_script_output_never_contains_key_and_startup_invokes_it_after_python(tmp_path):
    path = lab(tmp_path)
    source = SCRIPT.read_text(encoding='utf8')
    (tmp_path / 'scripts').mkdir()
    copy = tmp_path / 'scripts' / 'sync_class_key.py'; copy.write_text(source, encoding='utf8')
    (tmp_path / '.env').write_text('OPENAI_BASE_URL=https://relay.example/v1\nLLM_API_KEY=fixture-secret-key\nLLM_MODEL=coding\n', encoding='utf8')
    result = subprocess.run([sys.executable, str(copy)], capture_output=True, text=True, encoding='utf8',
                            env={**os.environ, 'PYTHONUTF8':'1', 'PYTHONIOENCODING':'utf-8'})
    assert result.returncode == 0 and 'fixture-secret-key' not in result.stdout + result.stderr
    assert mod.values((path / '.env').read_text(encoding='utf8'))['LLM_API_KEY'] == 'fixture-secret-key'
    script = (ROOT / 'scripts' / 'start_all.sh').read_text(encoding='utf8')
    assert script.index('scripts/sync_class_key.py') > script.index('Python 3.14.7 이상이 필요합니다')
    assert script.index('scripts/sync_class_key.py') < script.index('scripts/prepare_ports.py')


def test_actual_lab_client_uses_synced_key_model_and_tool_schema(tmp_path):
    seen = []
    class Relay(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            seen.append((self.path, self.headers.get('Authorization'), body))
            reply = json.dumps({'choices':[{'message':{'role':'assistant','content':'ok'}}]}).encode()
            self.send_response(200); self.send_header('Content-Length',str(len(reply))); self.end_headers(); self.wfile.write(reply)
        def log_message(self, *args): pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Relay)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        path = lab(tmp_path)
        (tmp_path/'.env').write_text(f'OPENAI_BASE_URL=http://127.0.0.1:{server.server_port}/v1\n'
                                      'LLM_API_KEY=fixture-key\nLLM_MODEL=coding\n', encoding='utf8')
        assert mod.sync(tmp_path) == 'updated'
        source = ROOT/'course/labs/offline/05-2-cause-agent/llm_client.py'
        spec = importlib.util.spec_from_file_location('actual_class_lab_client', source)
        client = importlib.util.module_from_spec(spec); spec.loader.exec_module(client)
        client._ENV = path/'.env'
        tools = [{'type':'function','function':{'name':'lookup','parameters':{'type':'object'}}}]
        assert client.chat([{'role':'user','content':'fixture'}], tools)['content'] == 'ok'
        assert len(seen) == 1 and seen[0][0] == '/v1/chat/completions'
        assert seen[0][1] == 'Bearer fixture-key' and seen[0][2]['model'] == 'coding' and seen[0][2]['tools'] == tools
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)
