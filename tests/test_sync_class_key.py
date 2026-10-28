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
    (tmp_path / '.env').write_text('OPENAI_BASE_URL=https://relay.example/v1\nLLM_API_KEY=fixture-key\nLLM_MODEL=\n', encoding='utf8')
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


def test_no_key_pc_skips_the_lab_without_error_and_startup_replays(tmp_path):
    # 2026-10-28 K4: 키 없는 온라인 학생 PC는 멈추지 않는다 — 실습랩 설정은 그대로 두고, 시작 스크립트는 AI 단계를 재생으로 켠다
    path = lab(tmp_path); target = path / '.env'; target.write_text('LLM_API_KEY=existing\n', encoding='utf8')
    for env in ('OPENAI_BASE_URL=https://relay.example/v1\nLLM_API_KEY=\nLLM_MODEL=coding\n',
                'OPENAI_BASE_URL=https://relay.example/v1\nLLM_API_KEY= "" \nLLM_MODEL=coding\n', 'LLM_MODEL=coding\n'):
        (tmp_path / '.env').write_text(env, encoding='utf8')
        assert mod.sync(tmp_path) == 'nokey'
    assert target.read_text(encoding='utf8') == 'LLM_API_KEY=existing\n'
    script = (ROOT / 'scripts' / 'start_all.sh').read_text(encoding='utf8')
    step2 = script[script.index('say "2/8'):script.index('say "3/8')]
    assert 'die ".env의 LLM_API_KEY가 비어' not in script
    assert 'AI_MODE_WANT=replay' in step2 and 'AI_MODE_WANT=live' in step2 and 'AI_MODE_WANT=record' in step2
    assert 'set_env AI_MODE "$AI_MODE_WANT"' in step2
    assert 'unset COMPOSE_PROFILES AI_MODE' in script            # 셸에 남은 AI_MODE 가 .env 를 이기지 않게
    step8 = script[script.index('say "8/8'):]
    assert step8.index('[ "$worker_mode" = "$AI_MODE_WANT" ]') < step8.index('if [ "$AI_MODE_WANT" = replay ]')
    assert step8.index('if [ "$AI_MODE_WANT" = replay ]') < step8.index('/models')   # 재생은 강의 중계를 부르지 않는다


@pytest.mark.parametrize('script,var', [('start_all.sh', 'saved'), ('record_replay.sh', 'old')])
def test_counting_saved_replays_survives_zero_files_under_pipefail(tmp_path, script, var):
    # 2026-10-28 실측: 저장분 0개에서 ls 가 2를 내 set -euo pipefail 스크립트가 아무 말 없이 끝났다
    import shutil
    bash = shutil.which('bash')
    if bash is None:
        pytest.skip('bash 없음')
    line = next(l.strip() for l in (ROOT / 'scripts' / script).read_text(encoding='utf8').splitlines() if l.strip().startswith(var + '=$('))
    (tmp_path / 'it' / 'agent-worker' / 'replay').mkdir(parents=True)
    run = lambda: subprocess.run([bash, '-c', f'set -euo pipefail; {line}; echo "n=${var}"'], cwd=tmp_path, capture_output=True, text=True)
    assert run().stdout.strip() == 'n=0'
    (tmp_path / 'it' / 'agent-worker' / 'replay' / 'a.json.gz').write_bytes(b'x')
    assert run().stdout.strip() == 'n=1'
