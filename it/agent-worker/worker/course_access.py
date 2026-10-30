"""워커가 process 와 말하는 곳 — 수업 경계 판정과 로컬 중계 관문의 실행 토큰. 워커에는 규칙 · 한도 사본이 없다(정본은 procsvc/course_policy.py ·
course_ledger.py). 주소는 PROCESS_URL 하나, 인증은 실행기 인증 파일(HYD_WORKER_RUNTIME_KEY_FILE) 하나다(settings).

  decide(row, tenant)   POST /internal/worker/course-decision → {'slot': 수업 AI 자리 | None, 'phase'}   (키 있음 · 키 없음 모두)
  permit(row, tenant)   POST /internal/worker/model-runtime  → CLI 환경(관문 주소 · 실행 토큰 · 모델)       (실제 AI 실행 때만)
  end(row, tenant)      POST /internal/worker/model-runtime/end → 그 점유의 장부 실행을 닫는다            (토큰을 받은 점유가 끝날 때)

학생에게 보일 까닭으로 멈출 때는 Stop(그 하위 종류)을 쓴다 — 문장 그대로 처리 기록의 friendly 칸에, 종류의 title 이 머리말에 간다.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


class Stop(RuntimeError):
    """학생에게 그대로 보일 까닭으로 단계를 멈춘다(내부어 · 예외 이름 없는 문장)."""
    title = 'AI 단계 멈춤'


class CourseDenied(Stop):
    """수업 경계 밖의 AI 단계 · 관문이 연 실행의 거절 — 문장은 process 가 정한 학생용 까닭."""
    title = '수업 권한 확인 필요'


class RuntimeConnectionError(Stop):
    """process(수업 판정 · 관문 · 로그인 연결)에 닿지 못했거나 답이 계약과 다르다."""
    title = '연결 확인 필요'


LOCAL_SERVICES = ('process', '127.0.0.1', 'localhost', '::1')


def process_base(url: str) -> str:
    """process 주소: 이 PC 안의 서비스 이름이면 HTTP, 그 밖은 HTTPS. 사용자 정보 · 경로 · 질의가 붙은 주소는 받지 않는다."""
    parsed = urllib.parse.urlsplit(url or '')
    if (not parsed.hostname or parsed.username or parsed.password or parsed.path not in ('', '/') or parsed.query or parsed.fragment
            or not (parsed.scheme == 'https' or parsed.scheme == 'http' and parsed.hostname in LOCAL_SERVICES)):
        raise RuntimeConnectionError('AI 워커의 process 주소 설정이 올바르지 않습니다. 시작.bat을 다시 실행하세요.')
    return url.rstrip('/')


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def read_key(path) -> str:
    try:
        key = Path(path).read_text(encoding='utf8').strip() if path else ''
    except OSError:
        key = ''
    if len(key) < 32:
        raise RuntimeConnectionError('AI 워커의 실행기 인증 파일을 읽지 못했습니다. 시작.bat을 다시 실행하세요.')
    return key


class CourseAccess:
    def __init__(self, process_url: str, key_file: str):
        self.url, self.key_file = process_url, key_file

    def _post(self, path: str, body: dict, what: str) -> dict:
        request = urllib.request.Request(process_base(self.url) + path, data=json.dumps(body).encode(), method='POST',
                                         headers={'Authorization': 'Bearer ' + read_key(self.key_file), 'Content-Type': 'application/json'})
        try:
            with urllib.request.build_opener(_NoRedirect()).open(request, timeout=15) as response:
                raw = response.read(16385)
            if len(raw) > 16384:
                raise ValueError('oversize')
            reply = json.loads(raw)
        except urllib.error.HTTPError as exc:
            detail = _detail(exc)
            if exc.code == 403 and detail:          # process 가 학생 말로 쓴 거절(수업 경계 · 장부 상한 · 동시 실행)
                raise CourseDenied(detail) from None
            raise RuntimeConnectionError(f'{what}을(를) 받지 못했습니다({exc.code}){" — " + detail if detail else ""}') from None
        except (OSError, ValueError):
            raise RuntimeConnectionError(f'{what}을(를) 받지 못했습니다 — process 서비스에 닿지 않습니다. 시작.bat을 다시 실행하세요.') from None
        if not isinstance(reply, dict):
            raise RuntimeConnectionError(f'{what} 응답 형식이 올바르지 않습니다')
        return reply

    def decide(self, row, tenant_id) -> dict:
        reply = self._post('/internal/worker/course-decision', dict(tenant_id=tenant_id, todo_id=row['id'], consumer=row['consumer']),
                           '수업 판정')
        if reply.get('allowed') is not True or reply.get('phase') not in ('course', 'pbl'):
            raise RuntimeConnectionError('수업 판정 응답 형식이 올바르지 않습니다')
        return {'slot': reply.get('slot'), 'phase': reply['phase']}

    def permit(self, row, tenant_id) -> dict:
        """이 점유의 실행 토큰 → CLI 환경. secrets 는 가림 목록에 더할 값(토큰)."""
        body = dict(tenant_id=tenant_id, todo_id=str(row['id']), consumer=row['consumer'])
        reply = self._post('/internal/worker/model-runtime', body, 'AI 실행 권한')
        if any(reply.get(k) != v for k, v in body.items()) or not reply.get('model') or \
                not isinstance(reply.get('token'), str) or not reply['token'].startswith('HydModel '):
            raise RuntimeConnectionError('AI 실행 권한 응답이 이 작업과 맞지 않습니다')
        model, token = reply['model'], reply['token']
        env = dict(ANTHROPIC_BASE_URL=process_base(self.url) + '/internal/model', ANTHROPIC_API_KEY=token, ANTHROPIC_AUTH_TOKEN='',
                   OPENAI_API_KEY='', LLM_API_KEY='')
        for name in ('ANTHROPIC_MODEL', 'ANTHROPIC_SMALL_FAST_MODEL', 'ANTHROPIC_DEFAULT_OPUS_MODEL',
                     'ANTHROPIC_DEFAULT_SONNET_MODEL', 'ANTHROPIC_DEFAULT_HAIKU_MODEL'):
            env[name] = model
        return dict(model=model, env=env, secrets=[token], deadline=reply.get('expires'))

    def end(self, row, tenant_id) -> None:
        """이 점유를 끝냈다 — 관문 장부의 실행을 닫는다(끝 상태를 작업 행에 쓴 뒤 부른다)."""
        self._post('/internal/worker/model-runtime/end', dict(tenant_id=tenant_id, todo_id=str(row['id']), consumer=row['consumer']),
                   'AI 실행 닫기')


def _detail(exc) -> str:
    try:
        detail = json.loads(exc.read(4097)).get('detail')
    except (OSError, ValueError, AttributeError):
        return ''
    return detail if isinstance(detail, str) else ''
