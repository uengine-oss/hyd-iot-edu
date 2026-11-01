"""학생 PC 안의 로컬 중계 관문 — 강의 중계(LiteLLM) 키는 process만 쥐고, AI 워커의 CLI에는 그 점유에 묶인 실행 토큰만 준다.

    POST /internal/worker/model-runtime        워커(실행기 인증 파일) → 수업 경계 판정 → 장부 실행 열기 → 실행 토큰(HydModel …)
    POST /internal/model/v1/messages            CLI(토큰) → 살아 있는 점유 · 장부 상한 확인 → 강의 중계로 전달(키는 여기서만 붙는다)
    POST /internal/model/v1/messages/count_tokens
    POST /internal/worker/model-runtime/end    워커(실행기 인증 파일) → 점유를 끝낸 뒤 그 장부 실행을 닫는다

모델은 수업 정책 하나(course_ledger.POLICY['model'])이고 요청이 다른 모델이면 보내지 않는다. 거절 · 중계 실패는 Anthropic 오류 모양
{"type":"error","error":{"type","message"}}이고 message 는 [HYD:<code>] + 학생 문장(course_ledger.REASONS 한 곳)이다 — 중계의 원문은
넘기지 않는다(분류에만 쓴다). 다시 보내도 소용없는 거절에는 x-should-retry: false. 중계 설정 확인은 장부에 적기 전에 한다.
스트리밍 답은 첫 내용 블록이 올 때까지 앞부분을 읽고 나서 흘려보낸다(stream_verdict) — 강의 중계(LiteLLM)는 뒤쪽 모델 계정의 거절
(잔액 소진 등)을 스트리밍에서는 200 + 내용 없는 메시지(토큰 0)로 내므로, 그대로 흘리면 CLI 가 「답 없음」으로 끝나 까닭이 사라진다.
"""
import asyncio
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import HTTPException

from . import worker_credentials
from .course_ledger import POLICY, REASONS, CourseLedger, Denied, coded
from .course_policy import AccessDenied, judged_claim, require_worker

PREFIX = 'HydModel '
TOKEN_SECONDS = 1800
INPUT_MAX = 2_000_000
STREAM_MAX = 32_000_000
LOCAL_HOSTS = ('127.0.0.1', 'localhost', '::1')


def ensure_runtime_key(path):
    """워커 인증 파일(process · 워커가 함께 보는 볼륨)을 처음 한 번 만든다. 다시 켤 때 바꾸지 않는다."""
    if not path:
        raise RuntimeError('HYD_WORKER_RUNTIME_KEY_FILE(워커 인증 파일 자리)이 설정되지 않았습니다')
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(fd, 'w', encoding='utf8') as stream:
            stream.write(secrets.token_urlsafe(48))
            stream.flush()
            os.fsync(stream.fileno())
    if path.is_symlink() or len(path.read_text(encoding='utf8').strip()) < 32:
        raise RuntimeError(f'워커 인증 파일이 올바르지 않습니다: {path}')


def relay_url(url: str) -> str:
    """강의 중계 주소: HTTPS, 또는 이 PC 안(loopback)의 HTTP. 사용자 정보 · 질의 · 조각이 붙은 주소는 받지 않는다(키가 새지 않게)."""
    parsed = urlsplit(url or '')
    if (not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment
            or not (parsed.scheme == 'https' or parsed.scheme == 'http' and parsed.hostname in LOCAL_HOSTS)):
        raise Denied('relay_config')
    return url.rstrip('/')


def classify_relay(status: int, body: bytes) -> str:
    """강의 중계가 200이 아닌 응답을 줬을 때의 종류(원문은 분류에만 쓴다)."""
    text = body[:8192].decode('utf8', 'replace').lower()
    # 키 예산(LiteLLM budget_exceeded)과 중계 뒤쪽 모델 계정의 잔액 소진(OpenAI insufficient_quota — 429 라 혼잡으로 읽혔다)
    if 'budget' in text or 'insufficient_quota' in text or 'credit_balance' in text:
        return 'relay_budget'
    # LiteLLM 은 키에 허용되지 않은 모델을 403 「key not allowed to access model」로 거절한다 — 인증보다 먼저 본다
    if 'model' in text and any(w in text for w in ('not allowed', 'invalid model', 'not found', 'does not exist', 'no access')):
        return 'relay_model'
    if status in (401, 403) or 'authentication' in text or 'invalid api key' in text or 'invalid_api_key' in text:
        return 'relay_auth'
    if status in (429, 503, 529) or 'rate limit' in text or 'overloaded' in text:
        return 'relay_busy'
    if 400 <= status < 500:
        return 'relay_rejected'
    return 'relay_failed'


class Refusal(Exception):
    """모델 호출 거절 — 관문 라우트가 Anthropic 오류 모양(관문 코드 + 학생 문장)으로 답한다(CLI 가 그 message 를 오류 글에 싣는다)."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code

    def response(self):
        from fastapi.responses import JSONResponse
        reason = REASONS[self.code]
        kind = {403: 'permission_error', 409: 'invalid_request_error', 413: 'request_too_large', 422: 'invalid_request_error',
                429: 'rate_limit_error'}.get(reason.status, 'api_error')
        return JSONResponse({'type': 'error', 'error': {'type': kind, 'message': coded(self.code)}}, reason.status,
                            headers={'x-should-retry': 'true' if reason.retry else 'false'})


# ---------------------------------------------------------------- 실행 토큰
def _sign(raw: str) -> str:
    return hmac.new(worker_credentials._key().encode(), ('hyd-model-v1:' + raw).encode(), hashlib.sha256).hexdigest()


def issue(runtime, ledger, policy, body, authorization) -> dict:
    """워커 요청 → 수업 경계 판정(course_policy.judged_claim — 워커용 판정과 같은 함수) → 장부 실행 → 토큰. 거절은 403 + 학생 문장 —
    장부 거절(한도 · 동시 실행 · 시간)은 [HYD:<code>] + 사유 표 문장(워커가 코드로 머리말을 고른다). 입력 크기는 모델 호출마다
    관문이 잰다(INPUT_MAX · 실행당 입력 상한) — 작업 변수 크기를 따로 막지 않는다(문서 넣기 구간 크기와 갈리던 두 번째 한도)."""
    try:
        row, _, _ = judged_claim(policy, runtime, body, authorization)
        run = ledger.open_run(runtime.tenant_id, row)
    except AccessDenied as exc:
        raise HTTPException(403, str(exc)) from None
    except Denied as exc:
        raise HTTPException(403, coded(exc.code)) from None
    binding = dict(tenant_id=runtime.tenant_id, todo_id=str(row['id']), consumer=row['consumer'], run_id=run['run_id'],
                   model=run['model'], expires=min(time.time() + TOKEN_SECONDS, run['deadline']))
    raw = base64.urlsafe_b64encode(json.dumps(binding, separators=(',', ':')).encode()).decode()
    return dict(tenant_id=runtime.tenant_id, todo_id=str(row['id']), consumer=row['consumer'], model=run['model'],
                token=PREFIX + raw + '.' + _sign(raw), expires=binding['expires'])


def verify_token(token) -> dict:
    try:
        if not isinstance(token, str) or not token.startswith(PREFIX) or len(token) > 4096:
            raise ValueError()
        raw, signature = token[len(PREFIX):].split('.')
        if not hmac.compare_digest(signature, _sign(raw)):
            raise ValueError()
        binding = json.loads(base64.urlsafe_b64decode(raw))
        if not time.time() < binding['expires'] <= time.time() + TOKEN_SECONDS + 1:
            raise ValueError()
    except (ValueError, KeyError, TypeError):
        raise Refusal('token') from None
    return binding


def prepare(runtime, ledger, settings, token, raw: bytes, *, count_only=False):
    """모델 호출 하나: 토큰 → 살아 있는 점유 → 요청 모양(수업 모델 · 출력 상한) → 중계 설정 → 장부에 적기. → (중계 주소 · 키, 출력 상한)."""
    binding = verify_token(token)
    try:
        worker_credentials._claim(runtime, binding)
    except HTTPException:
        raise Refusal('claim_ended') from None
    if len(raw) > INPUT_MAX:
        raise Refusal('too_large')
    try:
        request = json.loads(raw)
        if not isinstance(request, dict) or request.get('model') != binding['model']:
            raise ValueError()
        maximum = 1 if count_only else request.get('max_tokens')
        if type(maximum) is not int or maximum <= 0 or not isinstance(request.get('messages'), list) or not request['messages']:
            raise ValueError()
    except (ValueError, UnicodeError, TypeError):
        raise Refusal('bad_request') from None
    key = (settings.get('LLM_API_KEY') or '').strip()
    try:
        url = relay_url((settings.get('LLM_RELAY_URL') or '').strip())
        if not key:
            raise Denied('relay_config')
        ledger.charge(binding['run_id'], todo_id=binding['todo_id'], consumer=binding['consumer'],
                      input_bytes=len(raw), output_tokens=maximum)
    except Denied as exc:
        raise Refusal(exc.code) from None
    return dict(url=url, key=key), binding


async def _chunks(response, deadline):
    """기다림까지 한도 안에서 — HTTPX 시간 제한은 읽기 한 번마다라 전체 기한을 따로 잰다. 넘으면 연결을 끊는다(잘린 응답을 끝난 것처럼 보내지 않는다)."""
    chunks = response.aiter_bytes().__aiter__()
    size = 0
    while True:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            raise TimeoutError('모델 실행 시간 한도 초과')
        try:
            chunk = await asyncio.wait_for(anext(chunks), remaining)
        except StopAsyncIteration:
            return
        size += len(chunk)
        if size > STREAM_MAX:
            raise RuntimeError('모델 응답 크기 한도 초과')
        yield chunk


def stream_verdict(head: bytes) -> str | None:
    """강의 중계 SSE 앞부분 → 'content'(내용 블록이 왔다 — 흘려보낸다) · 거절 코드(내용 없이 끝났다 · 오류 사건) · None(더 읽는다).
    끝난(빈 줄로 닫힌) 사건만 본다. 내용 블록 없이 message_stop 에 닿았고 사용량도 0이면 모델이 불리지 않은 빈 답이다(relay_empty) —
    실제 모델의 답은 입력 토큰이 0일 수 없다."""
    usage = {}
    for raw in head.replace(b'\r\n', b'\n').split(b'\n\n')[:-1]:
        data = b'\n'.join(line[5:].strip() for line in raw.split(b'\n') if line.startswith(b'data:'))
        if not data:
            continue
        try:
            event = json.loads(data)
        except ValueError:
            return 'relay_failed'
        kind = event.get('type') if isinstance(event, dict) else None
        if kind == 'content_block_start':
            return 'content'
        if kind == 'error':
            return classify_relay(502, data)
        if kind == 'message_delta':
            usage = event.get('usage') or {}
        if kind == 'message_stop':
            return 'content' if usage.get('input_tokens') or usage.get('output_tokens') else 'relay_empty'
    return None


def mount(app, *, policy, runtime_factory, settings):
    """policy: course_policy.Policy(수업 경계), settings: 환경(LLM_API_KEY · LLM_RELAY_URL · HYD_WORKER_RUNTIME_KEY_FILE)."""
    import httpx
    from fastapi import Request
    from fastapi.responses import StreamingResponse

    def connect():
        import psycopg
        from psycopg.rows import dict_row
        runtime = runtime_factory()
        dsn = getattr(getattr(runtime, 'repo', None), 'dsn', None)
        if not dsn:
            raise HTTPException(503, '수업 실행 장부가 준비되지 않았습니다')
        return psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5)

    ledger = CourseLedger(connect, POLICY)

    def runtime_of(tenant):
        value = runtime_factory()
        if value is None or value.tenant_id != tenant:
            raise HTTPException(503, '현재 수업의 실행 서비스를 확인하세요')
        return value

    @app.on_event('startup')
    def prepare_key():
        ensure_runtime_key(settings.get('HYD_WORKER_RUNTIME_KEY_FILE'))

    async def body_bytes(request, maximum):
        chunks = bytearray()
        async for chunk in request.stream():
            if len(chunks) + len(chunk) > maximum:
                raise Refusal('too_large')
            chunks.extend(chunk)
        return bytes(chunks)

    @app.post('/internal/worker/model-runtime')
    async def permit(request: Request):
        try:
            body = json.loads(await body_bytes(request, 16384))
            if not isinstance(body, dict) or not isinstance(body.get('tenant_id'), str):
                raise ValueError()
        except (ValueError, UnicodeError, Refusal):
            raise HTTPException(422, '실행 요청 형식이 올바르지 않습니다') from None
        return await asyncio.to_thread(issue, runtime_of(body['tenant_id']), ledger, policy, body, request.headers.get('authorization'))

    @app.post('/internal/worker/model-runtime/end')
    async def end(request: Request):
        """워커가 점유를 끝낸 뒤 그 장부 실행을 닫는다(실행기 인증 파일)."""
        require_worker(request.headers.get('authorization'))
        try:
            body = json.loads(await body_bytes(request, 16384))
            if not isinstance(body, dict) or not all(isinstance(body.get(k), str) and body[k] for k in ('tenant_id', 'todo_id', 'consumer')):
                raise ValueError()
        except (ValueError, UnicodeError, Refusal):
            raise HTTPException(422, '끝낼 실행의 형식이 올바르지 않습니다') from None
        runtime_of(body['tenant_id'])
        ended = await asyncio.to_thread(ledger.end, body['tenant_id'], body['todo_id'], body['consumer'])
        return {'tenant_id': body['tenant_id'], 'todo_id': body['todo_id'], 'consumer': body['consumer'], 'ended': ended}

    async def forward(request, count_only):
        token = request.headers.get('x-api-key') or request.headers.get('authorization', '').removeprefix('Bearer ')
        runtime = runtime_of(verify_token(token)['tenant_id'])
        raw = await body_bytes(request, INPUT_MAX)
        upstream, binding = await asyncio.to_thread(prepare, runtime, ledger, settings, token, raw, count_only=count_only)
        remaining = binding['expires'] - time.time()
        if remaining <= 0:
            raise Refusal('run_time')
        headers = {'x-api-key': upstream['key'], 'Content-Type': 'application/json',
                   'anthropic-version': request.headers.get('anthropic-version', '2023-06-01')}
        if request.headers.get('anthropic-beta'):
            headers['anthropic-beta'] = request.headers['anthropic-beta']
        path = '/v1/messages/count_tokens' if count_only else '/v1/messages'
        client = httpx.AsyncClient(timeout=remaining, follow_redirects=False, trust_env=False)
        deadline = asyncio.get_running_loop().time() + remaining
        try:
            response = await asyncio.wait_for(client.send(client.build_request('POST', upstream['url'] + path, content=raw, headers=headers),
                                                          stream=True), remaining)
        except asyncio.CancelledError:
            await client.aclose()
            raise
        except Exception:  # noqa: BLE001 — 연결 실패 · 시간 초과: 원문 없이 종류만
            await client.aclose()
            raise Refusal('relay_failed') from None
        if response.status_code != 200:
            try:
                body = await asyncio.wait_for(response.aread(), 10)
            except Exception:  # noqa: BLE001 — 분류에 쓸 본문이 없으면 상태로만
                body = b''
            finally:
                await response.aclose()
                await client.aclose()
            raise Refusal(classify_relay(response.status_code, body))
        chunks, head = _chunks(response, deadline), b''
        if response.headers.get('content-type', '').startswith('text/event-stream'):
            verdict = None
            while verdict is None:
                try:
                    head += await anext(chunks)
                except StopAsyncIteration:
                    verdict = 'relay_failed'          # 판정 전에 끊김 — 끝나지 않은 답
                    break
                except asyncio.CancelledError:
                    await response.aclose()
                    await client.aclose()
                    raise
                except Exception:  # noqa: BLE001 — 중계에서 읽기 실패 · 기한 · 크기 한도만: 원문 없이 종류만
                    verdict = 'relay_failed'
                    break
                verdict = stream_verdict(head)    # 판정 함수는 이 try 밖 — 그 함수의 결함은 「다시 실행」으로 가려지지 않고 그대로 오류로 난다
            if verdict != 'content':
                await response.aclose()
                await client.aclose()
                raise Refusal(verdict)

        async def stream():
            try:
                if head:
                    yield head
                async for chunk in chunks:
                    yield chunk
            finally:
                await response.aclose()
                await client.aclose()
        return StreamingResponse(stream(), media_type=response.headers.get('content-type', 'application/json'),
                                 headers={'Cache-Control': 'no-store'})

    @app.post('/internal/model/v1/messages')
    async def messages(request: Request):
        try:
            return await forward(request, False)
        except Refusal as refused:
            return refused.response()

    @app.post('/internal/model/v1/messages/count_tokens')
    async def count_tokens(request: Request):
        try:
            return await forward(request, True)
        except Refusal as refused:
            return refused.response()

    return ledger
