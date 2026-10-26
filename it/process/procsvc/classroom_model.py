"""Private, claim-bound model capabilities for the instructor-managed worker.

Reuse the existing worker runtime secret and live work-item lease checks. The
student classroom key cannot mint a permit or call the upstream model directly.
"""
import base64
import asyncio
import hashlib
import hmac
import json
import time

from fastapi import HTTPException

from . import worker_credentials, engine
from .classroom_authority import Denied


PREFIX = 'HydModel '


async def deadline_chunks(response, deadline):
    """Bound waits as well as received chunks; HTTPX timeouts are per I/O."""
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
        if size > 32_000_000:
            raise RuntimeError('모델 응답 크기 한도 초과')
        yield chunk


def _execution(runtime, authority, row):
    inst = runtime.repo.get_instance(row['proc_inst_id'])
    values = engine.variables(inst) if inst else {}
    managed = values.get('classroom_execution')
    if managed is not None:
        from .classroom_tool_io import identifier
        if not isinstance(managed,dict) or set(managed) != {'run_id'} or values.get('extraction_cache'):
            raise Denied('관리 에이전트 실행 연결이 올바르지 않습니다')
        return authority.execution_context(runtime.tenant_id,row['proc_inst_id'],
                                           execution_run_id=identifier(managed['run_id']))
    cache = values.get('extraction_cache') or {}
    return authority.execution_context(runtime.tenant_id, row['proc_inst_id'], cache.get('key'),
                                       execution_run_id=cache.get('execution_run_id'))


def issue(runtime, authority, body, authorization):
    secret = worker_credentials._key()
    supplied = (authorization or '').removeprefix('Bearer ')
    if not hmac.compare_digest(secret.encode(), supplied.encode()):
        raise HTTPException(403, '관리 실행기 인증을 확인할 수 없습니다')
    row = worker_credentials._claim(runtime, body)
    try:
        execution = _execution(runtime, authority, row)
    except Denied as exc:
        raise HTTPException(403, str(exc)) from None
    binding = dict(tenant_id=runtime.tenant_id, todo_id=row['id'], consumer=body['consumer'],
                   run_id=execution['run_id'], model=execution['model'],
                   expires=min(time.time()+1800, execution['deadline']))
    raw = base64.urlsafe_b64encode(json.dumps(binding, separators=(',', ':')).encode()).decode()
    signature = hmac.new(secret.encode(), ('hyd-model-v1:'+raw).encode(), hashlib.sha256).hexdigest()
    return dict(tenant_id=runtime.tenant_id, todo_id=row['id'], consumer=row['consumer'],
                model=execution['model'], token=PREFIX+raw+'.'+signature)


def verify_token(token):
    try:
        if not isinstance(token, str) or not token.startswith(PREFIX) or len(token)>4096:
            raise ValueError()
        raw, signature = token[len(PREFIX):].split('.')
        expected = hmac.new(worker_credentials._key().encode(), ('hyd-model-v1:'+raw).encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError()
        binding = json.loads(base64.urlsafe_b64decode(raw))
        if not time.time() < binding['expires'] <= time.time()+1801:
            raise ValueError()
    except (ValueError, KeyError, TypeError):
        raise HTTPException(403, '모델 실행 권한이 없거나 만료됐습니다') from None
    return binding


def authorize(runtime, authority, token):
    binding = verify_token(token)
    row = worker_credentials._claim(runtime, binding)
    try:
        execution = _execution(runtime, authority, row)
    except Denied as exc:
        raise HTTPException(403, str(exc)) from None
    if execution['run_id'] != binding['run_id'] or execution['model'] != binding['model']:
        raise HTTPException(403, '모델 실행의 승인 판본이 바뀌었습니다')
    return binding


def prepare(runtime, authority, token, raw, *, count_only=False):
    binding = authorize(runtime, authority, token)
    if len(raw)>2_000_000:
        raise HTTPException(413, '모델 요청 입력 한도 초과')
    try:
        request = json.loads(raw)
        if not isinstance(request, dict) or request.get('model') != binding['model']:
            raise ValueError()
        maximum = 1 if count_only else request.get('max_tokens')
        if type(maximum) is not int or maximum <= 0:
            raise ValueError()
        if not isinstance(request.get('messages'), list) or not request['messages']:
            raise ValueError()
    except (ValueError, UnicodeError, TypeError):
        raise HTTPException(422, '승인된 모델과 입력·출력 한도를 지정해야 합니다') from None
    try:
        authority.charge_execution(binding['run_id'], input_bytes=len(raw), max_output_tokens=maximum)
    except Denied as exc:
        raise HTTPException(429, str(exc)) from None
    return request, binding


def mount(app, authority, runtime_factory, upstream_factory):
    """Anthropic-compatible transport used by the course Claude Code worker.
    The actual model is pinned by instructor policy; this is not a Claude model
    selection. There is no student-key fallback, redirect or automatic retry.
    """
    from urllib.parse import urlsplit
    import httpx
    from fastapi import Request
    from fastapi.responses import StreamingResponse

    async def body_bytes(request, maximum):
        chunks = bytearray()
        async for chunk in request.stream():
            if len(chunks)+len(chunk)>maximum:
                raise HTTPException(413, '요청 크기 한도 초과')
            chunks.extend(chunk)
        return bytes(chunks)

    @app.post('/internal/worker/model-runtime')
    async def permit(request: Request):
        supplied = request.headers.get('authorization', '').removeprefix('Bearer ')
        if not hmac.compare_digest(supplied.encode(), worker_credentials._key().encode()):
            raise HTTPException(403, '관리 실행기 인증을 확인할 수 없습니다')
        try:
            body = json.loads(await body_bytes(request, 16384))
            if not isinstance(body, dict) or not isinstance(body.get('tenant_id'), str):
                raise ValueError()
        except (ValueError, UnicodeError):
            raise HTTPException(422, '실행 요청 형식이 올바르지 않습니다') from None
        runtime = runtime_factory(body['tenant_id'])
        return await asyncio.to_thread(issue, runtime, authority, body, request.headers.get('authorization'))

    async def tool_operation(request, *, read_result):
        from .classroom_tool_io import ToolIO
        token = request.headers.get('authorization', '').removeprefix('Bearer ')
        binding = verify_token(token)
        runtime = runtime_factory(binding['tenant_id'])
        binding = await asyncio.to_thread(authorize,runtime,authority,token)
        try:
            body = json.loads(await body_bytes(request,16384))
            fields = {'request_id'} if read_result else {'call_id','tool','arguments'}
            if not isinstance(body,dict) or set(body) != fields:
                raise ValueError()
        except (ValueError,UnicodeError):
            raise HTTPException(422,'관리 도구 요청 필드가 올바르지 않습니다') from None
        broker = ToolIO(authority)
        try:
            if read_result:
                return await asyncio.to_thread(broker.result,binding['run_id'],body['request_id'])
            request_id = await asyncio.to_thread(broker.enqueue,binding['run_id'],**body)
            return {'request_id':request_id}
        except Denied as exc:
            raise HTTPException(403,str(exc)) from None

    @app.post('/internal/worker/tool-request')
    async def tool_request(request: Request):
        return await tool_operation(request,read_result=False)

    @app.post('/internal/worker/tool-result')
    async def tool_result(request: Request):
        return await tool_operation(request,read_result=True)

    async def forward(request, count_only):
        token = request.headers.get('x-api-key') or request.headers.get('authorization', '').removeprefix('Bearer ')
        binding = verify_token(token)
        runtime = runtime_factory(binding['tenant_id'])
        raw = await body_bytes(request, 2_000_000)
        payload, binding = await asyncio.to_thread(prepare, runtime, authority, token, raw, count_only=count_only)
        upstream = upstream_factory()  # Private secret read only at authorized execution time.
        url = upstream['url'].rstrip('/')
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise HTTPException(503, '관리 중계 주소 설정이 올바르지 않습니다')
        remaining = binding['expires']-time.time()
        if remaining <= 0:
            raise HTTPException(403, '모델 실행 시간이 만료됐습니다')
        client = httpx.AsyncClient(timeout=remaining, follow_redirects=False)
        deadline = asyncio.get_running_loop().time()+remaining
        headers = {'x-api-key': upstream['key'], 'Content-Type': 'application/json',
                   'anthropic-version': request.headers.get('anthropic-version', '2023-06-01')}
        if request.headers.get('anthropic-beta'):
            headers['anthropic-beta'] = request.headers['anthropic-beta']
        path = '/v1/messages/count_tokens' if count_only else '/v1/messages'
        try:
            response = await asyncio.wait_for(
                client.send(client.build_request('POST', url+path, content=raw, headers=headers), stream=True),
                max(0, deadline-asyncio.get_running_loop().time()))
        except asyncio.CancelledError:
            await client.aclose()
            raise
        except Exception:
            await client.aclose()
            raise HTTPException(502, '모델 중계 연결에 실패했습니다. 사용량 예약은 자동 환급하지 않습니다') from None
        if response.status_code != 200:
            status = response.status_code if response.status_code in (400, 408, 429) else 502
            await response.aclose(); await client.aclose()
            raise HTTPException(status, '모델 중계가 요청을 완료하지 못했습니다')
        async def stream():
            try:
                async for chunk in deadline_chunks(response, deadline):
                    yield chunk
            finally:
                await response.aclose(); await client.aclose()
        return StreamingResponse(stream(), media_type=response.headers.get('content-type', 'application/json'),
                                 headers={'Cache-Control': 'no-store'})

    @app.post('/internal/model/v1/messages')
    async def messages(request: Request):
        return await forward(request, False)

    @app.post('/internal/model/v1/messages/count_tokens')
    async def count_tokens(request: Request):
        return await forward(request, True)
