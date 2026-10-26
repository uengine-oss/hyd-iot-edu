"""Per-task model permits; the managed worker never gives students its upstream key."""
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

from .runtime_credentials import RuntimeConnectionError, _NoRedirect


def attach(row, tenant_id, provider_id):
    url = os.getenv('HYD_MANAGED_MODEL_URL', '').rstrip('/')
    if not url:
        if os.getenv('HYD_MANAGED_MODEL_REQUIRED') == '1':
            raise RuntimeConnectionError('관리 모델 실행 주소가 준비되지 않았습니다')
        return None
    parsed = urllib.parse.urlsplit(url)
    if parsed.username or parsed.password or parsed.query or parsed.fragment or not parsed.hostname or \
            parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in {'localhost', '127.0.0.1', '::1', 'classroom'}):
        raise RuntimeConnectionError('관리 모델 실행 주소는 HTTPS 또는 내부 서비스여야 합니다')
    if provider_id != 'claude-code':
        raise RuntimeConnectionError('관리 모델 경로는 현재 강의 Claude Code 실행기만 지원합니다')
    try:
        key = Path(os.environ['HYD_WORKER_RUNTIME_KEY_FILE']).read_text(encoding='utf8').strip()
        if len(key)<32:
            raise ValueError()
        body = dict(tenant_id=tenant_id, todo_id=row['id'], consumer=row['consumer'])
        request = urllib.request.Request(url+'/internal/worker/model-runtime', data=json.dumps(body).encode(),
                    headers={'Authorization': 'Bearer '+key, 'Content-Type': 'application/json'}, method='POST')
        with urllib.request.build_opener(_NoRedirect()).open(request, timeout=15) as response:
            raw = response.read(16385)
        if len(raw)>16384:
            raise ValueError()
        reply = json.loads(raw)
        if any(reply.get(k)!=v for k,v in body.items()) or not reply.get('model') or \
                not isinstance(reply.get('token'), str) or not reply['token'].startswith('HydModel '):
            raise ValueError()
    except Exception:
        # Never echo URLs, headers, keys or untrusted upstream error bodies.
        raise RuntimeConnectionError('관리 모델 실행 권한을 받지 못했습니다. 담당 단계·승인·예산을 확인하세요') from None
    model, token = reply['model'], reply['token']
    env = dict(ANTHROPIC_BASE_URL=url+'/internal/model', ANTHROPIC_API_KEY=token, ANTHROPIC_AUTH_TOKEN='',
               OPENAI_API_KEY='', LLM_API_KEY='', CODEX_MODEL_PROVIDER_API_KEY='')
    for name in ('ANTHROPIC_MODEL', 'ANTHROPIC_SMALL_FAST_MODEL', 'ANTHROPIC_DEFAULT_OPUS_MODEL',
                 'ANTHROPIC_DEFAULT_SONNET_MODEL', 'ANTHROPIC_DEFAULT_HAIKU_MODEL'):
        env[name] = model
    return dict(model=model, env=env, secrets=[token], url=url, token=token)
