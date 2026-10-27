"""Persistent, offline instructor unlock; no management flag or secret in HTTP."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import threading
import time

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware

from hydcommon import course_access as rules


class UnlockRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    code: str = Field(min_length=1, max_length=512, repr=False)


class AccessStore:
    def __init__(self, path, *, verify=rules.verify):
        self.path, self.verify = Path(path), verify
        self.lock = threading.Lock()
        self.failed = []

    def grant(self):
        try:
            if self.path.is_symlink():return None
            with self.path.open('rb') as stream:raw = stream.read(4097)
            if len(raw)>4096:return None
            value = json.loads(raw)
            if set(value) != {'grant'}:return None
            self.verify(value['grant'])
            return value['grant']
        except (OSError, ValueError, TypeError):return None

    def status(self):
        opened = bool(self.grant())
        return {'phase': 'handover' if opened else 'guided', 'unlocked': opened,
                'label': '교대 인수인계 실습' if opened else '기본 수업',
                'capabilities': {'fixed_agents': True, 'handover': opened,
                    'agent_authoring': opened, 'provided_manuals': opened, 'handover_flow': opened,
                    'free_questions': False, 'model_settings': False, 'tool_settings': False}}

    def unlock(self, code):
        with self.lock:
            now = time.monotonic()
            self.failed = [t for t in self.failed if now-t < 60]
            if len(self.failed)>=5:
                raise HTTPException(429, '코드 확인 횟수를 초과했습니다. 1분 뒤 다시 입력하세요.')
            try:self.verify(code)
            except ValueError:
                self.failed.append(now)
                raise HTTPException(403, '강사 해제 코드가 올바르지 않습니다.') from None
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_name(self.path.name+'.'+secrets.token_hex(8)+'.tmp')
            try:
                fd = os.open(temp, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
                with os.fdopen(fd, 'w', encoding='utf8') as stream:
                    json.dump({'grant': code.strip()}, stream)
                    stream.flush();os.fsync(stream.fileno())
                os.replace(temp, self.path)
            finally:temp.unlink(missing_ok=True)
            self.failed.clear()
            return self.status()


PERMANENT = re.compile(r'^/api/(?:ask(?:/|$)|agent-trials(?:/|$)|eval(?:/|$)|mcp(?:/|$)|'
    r'config(?:/|$)|flows(?:/|$)|process/definitions(?:/|$)|roles(?:/|$)|role-members(?:/|$)|'
    r'kg/(?:skills|rules|bsc|ranking-policy|ddl|scm|ingests)(?:/|$))')
AUTHORING = re.compile(r'^/api/(?:agents|skills|agent-assignments|agent-bindings)(?:/|$)')
SOURCE = re.compile(r'^/api/kg/manuals/sources/([^/]+)/(extractions|preview)$')


def mount(app, *, path, archive_factory, tenant, store=None):
    store = store or AccessStore(path)
    app.state.course_access = store

    def source_allowed(sid):
        if not isinstance(sid,str):return False
        try:return rules.approved_document(archive_factory().get(tenant, sid)['sha256'])
        except (KeyError, ValueError):return False

    @app.get('/api/course-access')
    def status():return store.status()

    @app.post('/api/course-access/unlock')
    async def unlock(request: Request):
        try:
            raw = await request.body()
            if len(raw)>2048:raise ValueError()
            body = UnlockRequest.model_validate_json(raw)
        except ValueError:
            raise HTTPException(422, '강사 해제 코드만 입력하세요.') from None
        return store.unlock(body.code)

    async def gate(request, call_next):
        if request.method in {'GET','HEAD','OPTIONS'}:return await call_next(request)
        path = request.url.path.rstrip('/')
        from .course_bootstrap import PATHS
        if path in PATHS and request.scope.get('state',{}).get('_course_bootstrap') == (request.method,path):
            return await call_next(request)
        if path == '/api/course-access/unlock' and request.method == 'POST':return await call_next(request)
        if path.startswith('/api/course-access'):
            return JSONResponse({'detail': '수업 권한은 강사 코드로만 열 수 있습니다.'}, 403)
        opened = bool(store.grant())
        try:body = await request.json() if AUTHORING.match(path) or path == '/api/instances/start' or path.startswith(('/api/kg/manuals','/api/flows/')) else {}
        except (ValueError, TypeError):body = {}
        if not isinstance(body,dict):body = {}
        reason = None
        if path.startswith('/api/flows/') and opened:
            from hydcommon.course_handover import allowed_request
            if not allowed_request(request.method,path,body):reason = '제공된 교대 BPMN과 시작 입력·검토·보완 연결만 등록할 수 있습니다.'
        elif PERMANENT.match(path):reason = '수업에서 허용하지 않은 관리 기능입니다.'
        elif AUTHORING.match(path):
            if not opened:reason = rules.LOCKED_MESSAGE
            elif path.startswith('/api/agent-assignments'):
                if request.method == 'PUT':
                    if not isinstance(body.get('definition_id'),str) or body['definition_id'] not in rules.HANDOVER_RUNS:reason = '교대 인수인계 단계에만 에이전트를 배정할 수 있습니다.'
                elif not any(path.startswith('/api/agent-assignments/'+d+'/') for d in rules.HANDOVER_RUNS):
                    reason = '교대 인수인계 단계에만 에이전트를 배정할 수 있습니다.'
            elif path.startswith('/api/agents') and request.method in {'POST','PUT'}:
                if body.get('model') not in (None,'','coding'):reason = '수업 모델은 강사가 지정한 기본 모델을 사용합니다.'
                tools = body.get('tools')
                if tools and (not isinstance(tools,list) or any(not isinstance(t,str) or t not in {'neo4j','enterprise','hyd-dmn'} for t in tools)):
                    reason = '교대 실습의 조회 도구만 사용할 수 있습니다.'
        elif path == '/api/instances/start':
            did = body.get('definition_id')
            if not isinstance(did,str) or (did not in rules.FIXED_RUNS and not (opened and did in rules.HANDOVER_RUNS)):
                reason = rules.LOCKED_MESSAGE if not opened else '준비된 수업 흐름만 시작할 수 있습니다.'
        elif path.startswith('/api/kg/manuals'):
            if path == '/api/kg/manuals/preview':
                try:
                    data = body.get('data')
                    if not isinstance(data,str) or len(data)>2000000:raise ValueError()
                    sha = hashlib.sha256(base64.b64decode(data, validate=True)).hexdigest()
                    allowed = rules.CONTENT['document_hashes'] if opened else rules.CONTENT['bootstrap_reviews']
                    if sha not in allowed:reason = '강사가 제공한 수업 문서만 사용할 수 있습니다.'
                except (ValueError, TypeError):reason = '강사가 제공한 수업 문서만 사용할 수 있습니다.'
            elif path == '/api/kg/manuals/commit' and not opened:
                if not rules.bootstrap_review(body):reason = rules.LOCKED_MESSAGE
            elif not opened:reason = rules.LOCKED_MESSAGE
            elif path in {'/api/kg/manuals/commit','/api/kg/manuals/changes'}:
                if not source_allowed(body.get('source_id')) or body.get('golden_questions'):
                    reason = '교대 실습은 제공 문서의 검토·적재만 허용합니다.'
            elif SOURCE.fullmatch(path):
                if not source_allowed(SOURCE.fullmatch(path).group(1)):reason = '강사가 제공한 수업 문서만 사용할 수 있습니다.'
            else:reason = '수업에서 허용하지 않은 문서 관리 기능입니다.'
        if reason:return JSONResponse({'detail':reason,'course_locked':not opened}, 403)
        return await call_next(request)
    # Keep the existing CORS middleware outside the gate, including denial replies.
    app.user_middleware.append(Middleware(BaseHTTPMiddleware, dispatch=gate))
    return store
