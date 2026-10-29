"""Classroom gate on the process API: course actions are always open, the rest of the product stays closed.

There is no unlock step (2026-10-29): the prepared flows, the provided documents and the course agents work from
the first lesson. Only actions outside the course are refused here — management functions the course does not
use, documents outside the provided set, flows other than the prepared ones.
"""
import base64
import hashlib
import re

from fastapi.responses import JSONResponse
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware

from hydcommon import course_access as rules


class CourseState:
    """What the portal shows about the course. Free questions are turned on by course_model.mount."""

    def __init__(self):
        self.questions_enabled = False

    def status(self):
        return {'phase': 'course', 'label': '수업',
                'capabilities': {'fixed_agents': True, 'handover': True, 'agent_authoring': True,
                    'provided_manuals': True, 'handover_flow': True, 'free_questions': self.questions_enabled,
                    'tool_inspection': True, 'model_settings': False, 'tool_settings': False}}


PERMANENT = re.compile(r'^/api/(?:ask(?:/|$)|agent-trials(?:/|$)|eval(?:/|$)|mcp(?:/|$)|'
    r'config(?:/|$)|flows(?:/|$)|process/definitions(?:/|$)|roles(?:/|$)|role-members(?:/|$)|'
    r'kg/(?:skills|rules|bsc|ranking-policy|ddl|scm|ingests)(?:/|$))')
AUTHORING = re.compile(r'^/api/(?:agents|skills|agent-assignments|agent-bindings)(?:/|$)')
SOURCE = re.compile(r'^/api/kg/manuals/sources/([^/]+)/(extractions|preview)$')
ROLLBACK = re.compile(r'^/api/kg/manuals/batches/[^/]+/rollback$')


def mount(app, *, archive_factory, tenant, store=None):
    store = store or CourseState()
    app.state.course_access = store

    def source_allowed(sid):
        if not isinstance(sid,str):return False
        try:return rules.approved_document(archive_factory().get(tenant, sid)['sha256'])
        except (KeyError, ValueError):return False

    @app.get('/api/course-access')
    def status():return store.status()

    async def gate(request, call_next):
        if request.method in {'GET','HEAD','OPTIONS'}:return await call_next(request)
        path = request.url.path.rstrip('/')
        from .course_bootstrap import PATHS
        if path in PATHS and request.scope.get('state',{}).get('_course_bootstrap') == (request.method,path):
            return await call_next(request)
        # The classroom tool map offers only fixed read calls, never MCP
        # registration, confirmation, proposal, or write operations.
        tool_call = re.fullmatch(r'/api/mcp/servers/([^/]+)/tools/([^/]+)/call', path)
        if request.method == 'POST' and tool_call:
            from hydcommon.handover_tools import question_read
            if question_read(*tool_call.groups()):return await call_next(request)
        if (path == '/api/ask' or re.fullmatch(r'/api/ask/[^/]+/retry',path)) and request.method == 'POST' and store.questions_enabled:
            return await call_next(request)
        if path.startswith('/api/course-access'):
            return JSONResponse({'detail': '수업 범위는 화면이나 요청으로 바꿀 수 없습니다.'}, 403)
        try:body = await request.json() if AUTHORING.match(path) or path == '/api/instances/start' or path.startswith(('/api/kg/manuals','/api/flows/')) else {}
        except (ValueError, TypeError):body = {}
        if not isinstance(body,dict):body = {}
        reason = None
        if path.startswith('/api/flows/'):
            from hydcommon.course_handover import allowed_request
            if not allowed_request(request.method,path,body):reason = '제공된 교대 BPMN과 시작 입력·검토·보완 연결만 등록할 수 있습니다.'
        elif PERMANENT.match(path):reason = '수업에서 허용하지 않은 관리 기능입니다.'
        elif AUTHORING.match(path):
            if path == '/api/agents/reset':
                reason = '수업 중 전체 에이전트 초기화는 사용할 수 없습니다.'
            elif path.startswith(('/api/agent-assignments', '/api/agent-bindings')):
                if path.startswith('/api/agent-assignments'):
                    if request.method == 'PUT':
                        if not isinstance(body.get('definition_id'),str) or body['definition_id'] not in rules.HANDOVER_DEFINITIONS:reason = '교대 인수인계 단계에만 에이전트를 배정할 수 있습니다.'
                    elif not any(path.startswith('/api/agent-assignments/'+d+'/') for d in rules.HANDOVER_DEFINITIONS):
                        reason = '교대 인수인계 단계에만 에이전트를 배정할 수 있습니다.'
            elif path.startswith('/api/agents') and request.method in {'POST','PUT'}:
                reason = rules.agent_configuration_error(body.get('model'), body.get('tools'))
        elif path == '/api/instances/start':
            did = body.get('definition_id')
            if not isinstance(did,str) or did not in rules.COURSE_RUNS:
                reason = '준비된 수업 흐름만 시작할 수 있습니다.'
        elif path.startswith('/api/kg/manuals'):
            if path == '/api/kg/manuals/preview':
                try:
                    data = body.get('data')
                    if not isinstance(data,str) or len(data)>2000000:raise ValueError()
                    sha = hashlib.sha256(base64.b64decode(data, validate=True)).hexdigest()
                    if not rules.approved_document(sha):reason = '강사가 제공한 수업 문서만 사용할 수 있습니다.'
                except (ValueError, TypeError):reason = '강사가 제공한 수업 문서만 사용할 수 있습니다.'
            elif path in {'/api/kg/manuals/commit','/api/kg/manuals/changes'}:
                if not source_allowed(body.get('source_id')) or body.get('golden_questions'):
                    reason = '수업에서는 제공 문서의 검토·적재만 할 수 있습니다.'
            elif SOURCE.fullmatch(path):
                if not source_allowed(SOURCE.fullmatch(path).group(1)):reason = '강사가 제공한 수업 문서만 사용할 수 있습니다.'
            elif ROLLBACK.fullmatch(path):pass       # 적재 판본 되돌리기: AI 없이 이 PC의 지식만 바뀐다
            else:reason = '수업에서 허용하지 않은 문서 관리 기능입니다.'      # 골든 질문 평가 등: 캐시 없는 AI 실행
        if reason:return JSONResponse({'detail':reason}, 403)
        return await call_next(request)
    # Keep the existing CORS middleware outside the gate, including denial replies.
    app.user_middleware.append(Middleware(BaseHTTPMiddleware, dispatch=gate))
    return store
