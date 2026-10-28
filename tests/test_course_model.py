from pathlib import Path

import pytest
import yaml

from procsvc.course_model import ensure_runtime_key
from worker import managed_isolation
from test_course_access import instructor, setup


def test_runtime_identity_survives_restart_and_invalid_file_is_not_reset(tmp_path):
    path = tmp_path/'private/runtime.key'
    ensure_runtime_key(path)
    first = path.read_bytes()
    assert len(first) >= 32
    ensure_runtime_key(path)
    assert path.read_bytes() == first
    path.write_text('invalid')
    with pytest.raises(ValueError):ensure_runtime_key(path)
    assert path.read_text() == 'invalid'


def test_normal_questions_can_open_without_unlocking_management(tmp_path, instructor):
    _, client, store, _, _ = setup(tmp_path, instructor)
    store.questions_enabled = True
    assert client.get('/api/course-access').json()['capabilities']['free_questions']
    assert client.post('/api/ask',json={'question':'학생이 다르게 쓴 질문'}).status_code == 200
    for path in ('/api/ask/reset','/api/mcp/servers','/api/config/import'):
        assert client.post(path,json={}).status_code == 403


def test_distributed_worker_only_receives_private_runtime_credential():
    compose = yaml.safe_load((Path(__file__).resolve().parents[1]/'compose.yaml').read_text(encoding='utf8'))
    process, worker = (compose['services'][n] for n in ('process','agent-worker'))
    assert 'LLM_API_KEY' in process['environment'] and 'LLM_RELAY_URL' in process['environment']
    assert not {'LLM_API_KEY','ANTHROPIC_API_KEY','ANTHROPIC_BASE_URL'} & worker['environment'].keys()
    assert worker['environment']['HYD_MANAGED_MODEL_REQUIRED'] == '1'
    assert 'worker-runtime:/run/hyd-credentials:ro' in worker['volumes']


def test_no_skill_tool_is_advertised_when_no_skill_was_assigned(tmp_path):
    args = managed_isolation.cli_args(tmp_path,[])
    assert args[args.index('--tools')+1].split(',') == ['Read','Write','Edit']


def test_retry_keeps_the_previous_raw_result_without_reusing_it(tmp_path):
    from worker.workspace import for_run
    ws=for_run(tmp_path,'same-work',tenant_id='hyd')
    ws.result_file.parent.mkdir(parents=True,exist_ok=True)
    raw=b'{"proposal": invalid original bytes'
    ws.result_file.write_bytes(raw)
    ws.clear_result_file()
    assert not ws.result_file.exists()
    kept=list((ws.context_dir/'previous-results').glob('*.json'))
    assert len(kept)==1 and kept[0].read_bytes()==raw


def test_permanent_local_quota_is_not_presented_as_a_one_minute_relay_wait():
    from worker.runner import relay_hint
    hint=relay_hint('API Error 429 {"detail":"수업 실행 또는 누적 사용량 한도 초과: calls"}')
    assert '초기화되지는 않습니다' in hint and '1분 뒤' not in hint


def test_worker_gets_the_ai_mode_from_env_and_reads_writes_the_repo_replay_folder():
    # 2026-10-28 K2 · K3: 시작 스크립트가 .env 에 정한 AI_MODE 가 워커에 가고, 녹화 · 재생이 저장소의 it/agent-worker/replay 를 쓴다
    compose = yaml.safe_load((Path(__file__).resolve().parents[1]/'compose.yaml').read_text(encoding='utf8'))
    worker = compose['services']['agent-worker']
    assert worker['environment']['AI_MODE'] == '${AI_MODE:-live}'
    assert worker['environment']['AI_REPLAY_DIR'] == '/srv/replay'
    assert './it/agent-worker/replay:/srv/replay' in worker['volumes']
    assert (Path(__file__).resolve().parents[1]/'it/agent-worker/replay').is_dir()
