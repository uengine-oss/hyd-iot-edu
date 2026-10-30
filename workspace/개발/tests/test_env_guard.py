"""워커 환경 정리(worker/env_guard.py) — CLI 는 그 실행의 관문 토큰으로만 모델을 부른다. 워커 환경에 남은 개인 CLI 키도 자식에게 가지 않는다."""
from worker import env_guard


def test_개인_CLI_키와_업무_비밀은_CLI_에_넘기지_않고_실행에_필요한_설정은_남긴다():
    environ = {'ANTHROPIC_API_KEY': 'sk-ant-personal-0000', 'CLAUDE_CODE_OAUTH_TOKEN': 'oauth-personal-0000', 'OPENAI_API_KEY': 'sk-x',
               'SUPABASE_DSN': 'postgresql://u:p@db/x', 'NEO4J_PASSWORD': 'hydpass123', 'HYD_SECRET_GOOGLE': 'g-secret-0000',
               'PATH': '/usr/bin', 'PROCESS_URL': 'http://process:8080', 'HYD_WORKER_RUNTIME_KEY_FILE': '/run/hyd-credentials/runtime.key'}
    removed = env_guard.scrub(environ)
    assert sorted(environ) == ['HYD_WORKER_RUNTIME_KEY_FILE', 'PATH', 'PROCESS_URL']
    assert {'ANTHROPIC_API_KEY', 'CLAUDE_CODE_OAUTH_TOKEN', 'HYD_SECRET_GOOGLE'} <= set(removed)
    assert env_guard.held_secrets()['HYD_SECRET_GOOGLE'] == 'g-secret-0000'
