"""수업 경계의 정본 — 무엇을 열고 무엇을 막는지는 이 모듈 한 곳에만 있다. 포털 화면은 GET /api/course-access, AI 워커는
POST /internal/worker/course-decision 으로 이 판정을 서버에서 읽는다(화면 · 워커에 규칙 사본 없음).

원칙(사용자 확정): 학생은 포털 기능을 다 실제로 써 본다. 통제하는 것은 AI가 답을 만드는 자리(수업 AI 자리)뿐이고, 막는 것은 악용
지점뿐이다 — 허용 밖 문서 · 대용량, 외부 도구 서버 등록, 수업 모델 밖 모델. 비용의 최종 방어는 강의 중계 키의 한도다.

단계 둘: 수업(course) · PBL(pbl). PBL로 바꾸는 것은 강사뿐이다 — 강사 서명이 붙은 단계 선언(course_phase.json, 이 파일 옆)을 저장소에
올리면 학생 PC는 받아서 시작할 때 읽는다(한 곳에서 한 번에). 학생 PC에는 단계를 바꾸는 화면 · API · 설정이 없고, 선언을 고치면 서명이
깨져 process가 뜨지 않는다. 선언이 없거나 기한이 지났으면 수업 단계다.

허용 목록은 손으로 적지 않는다 — 수업 AI 자리는 제공 흐름(course_flows.json · course_handover.json · definitions/shift_handover_v1.json
· ask_agent)에서, 제공 문서는 강사 서명 추출 묶음(course_extractions.json)에서, 기본 도구 서버는 mcp_registry.BASE_SERVERS 에서 읽는다.
"""
import base64
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# 수업 내용(흐름 A · B · C, 제공 교대 그림, 서명 추출 묶음, 단계 선언)은 이 규칙 옆에 둔다 — 읽는 서비스는 process(와 그 코드를 쓰는 워커)뿐이다
HERE = Path(__file__).resolve().parent
DEFINITIONS = Path(__file__).resolve().parent.parent / 'definitions'
PHASE_FILE = Path(__file__).with_name('course_phase.json')

# 강사 서명 공개 키 — 제공 문서 추출 묶음(manual_approved_cache)과 같은 키다. 비밀 키는 이미지 · 환경 변수 · 브라우저 · Git 어디에도
# 두지 않는다. 단계 선언은 서명 영역(PHASE_DOMAIN)이 달라 추출 묶음 서명을 단계 해제로 다시 쓸 수 없다.
PUBLIC_KEY = 'uiQXhElZ7HnRyuc_48KCdGsKa4k_oWppx0FKiK-dun0='
PHASE_KEYS = (PUBLIC_KEY,)
PHASE_DOMAIN = b'hyd-course-phase-v1\x00'
PHASE_CONTRACT = 'hyd-course-phase-v1'
PHASES = {'course': '수업', 'pbl': 'PBL'}

COURSE_MODEL = 'coding'              # 두 단계 모두 수업 모델 하나(다른 모델은 악용 지점)
QUESTION_MAX_CHARS = 1000
HANDOVER_IMPORT_ID = 'ShiftHandover'  # 학생이 bpmn.io 로 가져오는 제공 교대 흐름
FLOW_TEXT_MAX = 200_000              # 흐름 XML · 매핑 글자 수 한도(두 단계 공통 — 대용량은 악용 지점)
BPMN = '{http://www.omg.org/spec/BPMN/20100524/MODEL}'


class AccessDenied(ValueError):
    """수업 경계 밖의 요청. 문장은 학생에게 그대로 보인다."""


class PhaseError(RuntimeError):
    """단계 선언 파일이 깨졌거나 서명이 맞지 않는다 — process 를 띄우지 않는다(조용히 수업 단계로 돌지 않음)."""


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf8')


def decode64(value):
    return base64.b64decode(value + '=' * (-len(value) % 4), altchars=b'-_', validate=True)


# ---------------------------------------------------------------- 단계(수업 / PBL)
@dataclass(frozen=True)
class Phase:
    name: str                    # course | pbl
    note: str = ''               # 강사가 적은 한 줄(PBL 이름 등)
    expires: str | None = None   # PBL 선언의 기한(ISO), 지났으면 수업 단계로 읽는다
    expired: bool = False

    @property
    def label(self):
        return PHASES[self.name]

    @property
    def pbl(self):
        return self.name == 'pbl'


def load_phase(path=PHASE_FILE, keys=PHASE_KEYS, now=None) -> Phase:
    """단계 선언을 읽는다. 파일이 없으면 수업 단계. 서명 · 형식이 틀리면 PhaseError(학생이 고친 선언, 깨진 배포)."""
    path = Path(path)
    if not path.exists():
        return Phase('course')
    try:
        envelope = json.loads(path.read_text(encoding='utf8'))
        payload, signature = envelope['payload'], envelope['signature']
        if not isinstance(payload, dict) or not isinstance(signature, str):
            raise ValueError
    except (ValueError, KeyError, TypeError) as exc:
        raise PhaseError(f'{path.name}: 단계 선언 형식이 아닙니다(payload · signature)') from exc
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    for key in keys:
        try:
            Ed25519PublicKey.from_public_bytes(decode64(key)).verify(decode64(signature), PHASE_DOMAIN + canonical(payload))
            break
        except Exception:  # noqa: BLE001 — 다음 공개 키로; 모두 실패하면 아래에서 거절
            continue
    else:
        raise PhaseError(f'{path.name}: 강사 서명을 확인할 수 없습니다 — 단계 선언은 강사만 바꿀 수 있습니다(저장소의 원래 파일로 되돌리세요)')
    if payload.get('contract') != PHASE_CONTRACT or payload.get('phase') not in PHASES:
        raise PhaseError(f'{path.name}: 단계 선언의 계약 · 단계 이름이 다릅니다')
    expires = payload.get('expires')
    if payload['phase'] == 'pbl':
        try:
            until = datetime.fromisoformat(str(expires).replace('Z', '+00:00'))
            if until.tzinfo is None:
                raise ValueError
        except ValueError as exc:
            raise PhaseError(f'{path.name}: PBL 선언에는 시간대가 있는 기한(expires)이 있어야 합니다') from exc
        if until <= (now or datetime.now(timezone.utc)):
            return Phase('course', note=str(payload.get('note') or ''), expires=expires, expired=True)
    return Phase(payload['phase'], note=str(payload.get('note') or ''), expires=expires)


def sign_phase(payload: dict, private_key) -> dict:
    """강사 도구(workspace/개발/scripts/course_phase_sign.py)와 테스트가 쓰는 서명 — 비밀 키는 부르는 쪽이 쥔다."""
    signature = private_key.sign(PHASE_DOMAIN + canonical(payload))
    return {'payload': payload, 'signature': base64.urlsafe_b64encode(signature).decode().rstrip('=')}


# ---------------------------------------------------------------- 제공 자료에서 뽑는 목록
def _json(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


COURSE_FLOWS = _json(HERE / 'course_flows.json')          # 수업 흐름 A · B · C {id: [파일 이름, BPMN XML, 매핑]}
HANDOVER = _json(HERE / 'course_handover.json')           # 제공 교대 BPMN {xml, mapping}
EXTRACTIONS = _json(HERE / 'course_extractions.json')     # 강사 서명 추출 묶음(문서 sha256 → 검토한 추출본)


def _ai_slots():
    """수업 AI 자리 {(정의 id, 단계 id): 자리 이름}. 같은 자리는 키 없는 PC에서 같은 강사 녹화로 재생된다."""
    slots = {}
    for did, (_, _, mapping) in COURSE_FLOWS.items():
        for task, item in (mapping.get('tasks') or {}).items():
            if isinstance(item, dict) and item.get('agent'):
                slots[(did, task)] = f'{did}/{task}'
    # 교대 초안은 두 판(학생이 가져오는 ShiftHandover · 제공 정의 shift_handover)이 같은 순서의 세 자리(보완 0 · 1 · 2번)다
    imported = sorted(t for t, item in HANDOVER['mapping']['tasks'].items() if isinstance(item, dict) and item.get('agent'))
    shipped = _json(DEFINITIONS / 'shift_handover_v1.json')
    provided = sorted(a['id'] for a in shipped['activities'] if a.get('agentMode'))
    for did, tasks in ((HANDOVER_IMPORT_ID, imported), (shipped['processDefinitionId'], provided)):
        for n, task in enumerate(tasks, 1):
            slots[(did, task)] = f'handover/draft-{n}'
    question = _json(DEFINITIONS / 'ask_agent_v1.json')
    for a in question['activities']:
        if a.get('agentMode'):
            slots[(question['processDefinitionId'], a['id'])] = 'question'
    return slots


AI_SLOTS = _ai_slots()
QUESTION_DEFINITION = next(d for (d, _), s in AI_SLOTS.items() if s == 'question')
HANDOVER_DEFINITIONS = frozenset(d for (d, _), s in AI_SLOTS.items() if s.startswith('handover/'))
COURSE_DEFINITIONS = frozenset(COURSE_FLOWS) | HANDOVER_DEFINITIONS     # 수업 단계에서 시작 · 배포할 수 있는 흐름
DOCUMENTS = frozenset(EXTRACTIONS['payload']['documents'])


def provided_document(sha256) -> bool:
    return isinstance(sha256, str) and sha256 in DOCUMENTS


# ---------------------------------------------------------------- 판정(단계마다 같은 함수)
class Policy:
    """한 PC의 지금 단계에서 내리는 판정. 거절은 AccessDenied(학생에게 보일 까닭)."""

    def __init__(self, phase: Phase):
        self.phase = phase

    # -- AI가 답을 만드는 자리
    def ai_slot(self, definition_id, activity_id, inputs=None):
        """이 AI 단계를 실행해도 되는가 → 수업 AI 자리 이름(PBL의 수업 밖 단계는 None). 수업 단계의 수업 밖 단계는 거절."""
        slot = AI_SLOTS.get((definition_id, activity_id))
        if slot == 'question':
            question = (inputs or {}).get('question')
            if not isinstance(question, str) or not question.strip() or len(question) > QUESTION_MAX_CHARS:
                raise AccessDenied(f'질문은 1~{QUESTION_MAX_CHARS}자로 적습니다.')
        if slot is None and not self.phase.pbl:
            raise AccessDenied('수업에서는 준비된 흐름(냉각 · 정기 정비 · 예비품 구매 · 교대 인수인계)의 AI 단계와 질문만 실행합니다. '
                               '다른 흐름의 AI 단계는 강사가 PBL 단계를 열면 실행됩니다.')
        return slot

    # -- 에이전트 설정(두 단계 공통: 모델은 수업 모델 하나)
    @staticmethod
    def agent_model_error(model):
        if model not in (None, '', COURSE_MODEL):
            return '에이전트 모델은 강사가 지정한 수업 모델 하나만 씁니다 — 다른 모델 이름은 받지 않습니다(비워 두면 수업 모델).'
        return None

    def assign(self, definition_id):
        if not self.phase.pbl and definition_id not in HANDOVER_DEFINITIONS:
            raise AccessDenied('수업에서는 교대 인수인계 단계에만 내 에이전트를 배정합니다(다른 단계는 PBL 단계에서 엽니다).')

    # -- 흐름
    def start(self, definition_id):
        if not self.phase.pbl and definition_id not in COURSE_DEFINITIONS:
            raise AccessDenied('수업에서는 준비된 흐름(냉각 · 정기 정비 · 예비품 구매 · 교대 인수인계)만 시작합니다.')

    def edit_flow(self, definition_id):
        """흐름 가져오기 · 매핑 저장 · 검사 · 배포 · 정의 등록의 대상 흐름."""
        if not self.phase.pbl and definition_id not in (HANDOVER_IMPORT_ID,):
            raise AccessDenied('수업에서 직접 가져오는 흐름은 제공한 교대 인수인계 BPMN 하나입니다(다른 흐름은 PBL 단계에서 엽니다).')

    def import_flow(self, xml, definition_id):
        if not isinstance(xml, str) or len(xml) > FLOW_TEXT_MAX:
            raise AccessDenied(f'흐름 그림(.bpmn)은 {FLOW_TEXT_MAX:,}자 이하여야 합니다.')
        if self.phase.pbl:
            return
        self.edit_flow(definition_id or HANDOVER_IMPORT_ID)
        if not handover_structure_same(xml):
            raise AccessDenied('수업에서는 제공한 교대 인수인계 BPMN의 이름과 배치만 바꿔 가져옵니다 — 단계 · 연결 · 조건을 바꾼 그림은 '
                               'PBL 단계에서 가져옵니다. 원본 파일을 다시 열어 이름 · 배치만 고치세요.')

    def register_flow(self, definition_id, xml, mapping):
        if self.phase.pbl:
            return
        self.edit_flow(definition_id)
        if not handover_structure_same(xml) or not handover_mapping_same(mapping):
            raise AccessDenied('수업에서는 제공한 교대 BPMN과 연결(흐름 이름 · 세 초안 단계의 에이전트만 바꿈)만 등록합니다. '
                               '원본을 다시 가져와 확인하세요.')

    # -- 문서
    def document(self, sha256):
        if not self.phase.pbl and not provided_document(sha256):
            raise AccessDenied('수업에서는 강사가 제공한 수업 문서(내용을 고치지 않은 원문)만 등록합니다. 다른 문서는 PBL 단계에서 엽니다.')

    # -- 경로 단위로 막는 행동(악용 지점 · 수업 밖 AI)
    ACTIONS = {
        'tool_servers.register': ('외부 도구 서버 등록 · 비밀값 · 로그인 연결 · 쓰기 도구를 읽기로 확인하기는 PBL 단계에서 엽니다. '
                                  '수업에서는 준비된 도구 서버를 그대로 씁니다.'),
        'documents.golden': '골든 질문 평가(문서마다 AI가 답하는 검사)는 PBL 단계에서 엽니다. 수업에서는 검토 · 적재 · 되돌리기를 합니다.',
        'ddl.meanings': '옛 DB 뜻 복원(AI가 표 · 열 뜻을 추정)은 PBL 단계에서 엽니다. 구조 읽기 · 적재 · 되돌리기는 수업에서도 됩니다.',
        'config.import': '설정 불러오기는 PBL 단계에서 엽니다(수업 실습에 없는 기능 — 외부 도구 서버 · 다른 흐름이 함께 들어옵니다). '
                         '내보내기 · 기준으로 되돌리기는 수업에서도 됩니다.',
    }

    def action(self, key):
        if not self.phase.pbl and key in self.ACTIONS:
            raise AccessDenied(self.ACTIONS[key])

    def view(self):
        """포털이 읽는 표 — 화면은 이 표로만 단추를 끄고 까닭을 보인다."""
        return {
            'phase': self.phase.name, 'label': self.phase.label, 'note': self.phase.note,
            'expires': self.phase.expires, 'expired': self.phase.expired,
            'model': COURSE_MODEL,
            'actions': {key: {'allowed': self.phase.pbl, 'reason': None if self.phase.pbl else reason}
                        for key, reason in self.ACTIONS.items()},
            'assignable_definitions': None if self.phase.pbl else sorted(HANDOVER_DEFINITIONS),
            'startable_definitions': None if self.phase.pbl else sorted(COURSE_DEFINITIONS),
            'importable_flow': None if self.phase.pbl else HANDOVER_IMPORT_ID,
            'documents': None if self.phase.pbl else 'provided',
        }


# ---------------------------------------------------------------- 제공 교대 BPMN과 같은가(이름 · 배치만 바꾼 것만 같다)
def _skeleton(xml):
    if not isinstance(xml, str) or len(xml) > FLOW_TEXT_MAX or '<!' in xml:
        raise ValueError('unsupported XML')
    root = ET.fromstring(xml)
    processes = root.findall(BPMN + 'process')
    if len(processes) != 1 or any(e.tag.startswith(BPMN) and e is not processes[0] for e in root):
        raise ValueError('one process required')

    def node(e):
        return (e.tag, tuple(sorted((k, v) for k, v in e.attrib.items() if k != 'name')),
                (e.text or '').strip(), tuple(node(child) for child in e))
    return node(processes[0])


def handover_structure_same(xml) -> bool:
    try:
        return _skeleton(xml) == _skeleton(HANDOVER['xml'])
    except (ValueError, TypeError, ET.ParseError):
        return False


def handover_mapping_same(mapping) -> bool:
    if not isinstance(mapping, dict):
        return False
    value = deepcopy(mapping)
    if not isinstance(value.get('name'), str) or not 1 <= len(value['name']) <= 160 or not isinstance(value.get('tasks'), dict):
        return False
    value['name'] = HANDOVER['mapping']['name']
    for task, item in HANDOVER['mapping']['tasks'].items():
        if not (isinstance(item, dict) and item.get('agent')):
            continue
        got = value['tasks'].get(task)
        if not isinstance(got, dict) or not re.fullmatch(r'agent:[A-Za-z0-9_.-]{1,80}', str(got.get('agent', ''))):
            return False
        got['agent'] = item['agent']
    return value == HANDOVER['mapping']


def document_sha256(data_b64: str) -> str:
    return hashlib.sha256(base64.b64decode(data_b64, validate=True)).hexdigest()


# ---------------------------------------------------------------- process API에 붙이기
# 경로 하나가 곧 행동인 것(본문을 볼 필요 없음). 본문을 봐야 하는 판정(흐름 그림 · 매핑 · 문서 · 모델)은 그 라우트가 Policy 를 부른다.
_PATH_ACTIONS = (
    ('POST', re.compile(r'/api/mcp/servers'), 'tool_servers.register'),
    ('PUT', re.compile(r'/api/mcp/servers/[^/]+'), 'tool_servers.register'),
    ('POST', re.compile(r'/api/mcp/servers/[^/]+/read-confirm'), 'tool_servers.register'),
    ('POST', re.compile(r'/api/mcp/check'), 'tool_servers.register'),
    ('POST', re.compile(r'/api/mcp/connections/.+'), 'tool_servers.register'),
    ('PUT', re.compile(r'/api/mcp/secrets/[^/]+'), 'tool_servers.register'),
    ('DELETE', re.compile(r'/api/mcp/secrets/[^/]+'), 'tool_servers.register'),
    ('POST', re.compile(r'/api/kg/manuals/batches/[^/]+/golden-questions'), 'documents.golden'),
    ('POST', re.compile(r'/api/kg/ddl/meanings'), 'ddl.meanings'),
    ('POST', re.compile(r'/api/config/import'), 'config.import'),
)
# 흐름 id 가 주소에 있는 흐름 편집(가져오기 뒤의 매핑 저장 · 검사 · 등록 · 정의 배포 · 되돌리기)
_FLOW_EDIT = re.compile(r'/api/(?:flows/(?P<a>[^/]+)/(?:mapping|check|register)|process/definitions/(?P<b>[^/]+)/(?:deploy|rollback))')
# 제공 흐름을 서버 안에서 설치하는 길(course_bootstrap) 말고는 「수업 흐름」 표시를 보낼 수 없다
_CLASS_FLOW_PATHS = re.compile(r'/api/(?:flows/import|flows/[^/]+/register|process/definitions/[^/]+/deploy)')


def gate_reason(policy: Policy, method: str, path: str, body: dict, internal: bool):
    """쓰기 요청 하나의 판정(경로 · 흐름 id 수준). None = 통과, 문자열 = 학생에게 보일 거절 까닭."""
    try:
        for m, pattern, key in _PATH_ACTIONS:
            if method == m and pattern.fullmatch(path):
                policy.action(key)
        if _CLASS_FLOW_PATHS.fullmatch(path) and body.get('class_flow') and not internal:
            raise AccessDenied('수업 흐름 표시는 시작 스크립트의 제공 흐름 설치만 씁니다. 내 흐름은 표시 없이 등록하세요.')
        if internal:
            return None
        edit = _FLOW_EDIT.fullmatch(path)
        if edit and method in ('POST', 'PUT'):
            policy.edit_flow(edit.group('a') or edit.group('b'))
        elif method == 'POST' and path == '/api/process/definitions':
            policy.edit_flow((body.get('definition') or {}).get('processDefinitionId') if isinstance(body.get('definition'), dict)
                             else body.get('processDefinitionId'))
        elif method == 'POST' and path == '/api/instances/start' and body.get('definition_id') is not None:
            policy.start(body.get('definition_id'))
        elif method == 'PUT' and path == '/api/agent-assignments':
            policy.assign(body.get('definition_id'))
        elif method == 'DELETE' and path.startswith('/api/agent-assignments/'):
            policy.assign(path.split('/')[3])
    except AccessDenied as exc:
        return str(exc)
    return None


def _needs_body(method, path):
    return method in ('POST', 'PUT') and (path == '/api/instances/start' or path == '/api/agent-assignments'
                                          or path == '/api/process/definitions' or bool(_CLASS_FLOW_PATHS.fullmatch(path)))


def mount(app, *, runtime_factory, phase: Phase | None = None):
    """수업 경계를 process API에 붙인다: 판정 표(app.state.course), 화면용 GET /api/course-access, 워커용 판정, 쓰기 요청 문지기."""
    import asyncio
    import hmac
    from fastapi import HTTPException, Request
    from fastapi.responses import JSONResponse
    from starlette.middleware import Middleware
    from starlette.middleware.base import BaseHTTPMiddleware
    from . import engine, worker_credentials

    policy = Policy(phase if phase is not None else load_phase())
    app.state.course = policy

    @app.get('/api/course-access')
    def course_access():
        return policy.view()

    def decide(body, authorization):
        if not hmac.compare_digest((authorization or '').removeprefix('Bearer ').encode(), worker_credentials._key().encode()):
            raise HTTPException(403, '실행기 인증을 확인할 수 없습니다')
        runtime = runtime_factory()
        if runtime is None or body.get('tenant_id') != runtime.tenant_id:
            raise HTTPException(503, '수업 판정에 필요한 실행 서비스가 없습니다')
        row = worker_credentials._claim(runtime, body)
        inst = runtime.repo.get_instance(row['proc_inst_id'])
        if not inst:
            raise HTTPException(409, '판정할 처리 건이 없습니다')
        try:
            slot = policy.ai_slot(inst['proc_def_id'], row['activity_id'], engine.variables(inst))
        except AccessDenied as exc:
            raise HTTPException(403, str(exc)) from None
        return {'allowed': True, 'slot': slot, 'phase': policy.phase.name}

    @app.post('/internal/worker/course-decision')
    async def course_decision(request: Request):
        try:
            body = await request.json()
            if not isinstance(body, dict):
                raise ValueError
        except ValueError:
            raise HTTPException(422, '판정 요청 형식이 올바르지 않습니다') from None
        return await asyncio.to_thread(decide, body, request.headers.get('authorization'))

    async def gate(request, call_next):
        method, path = request.method, request.url.path.rstrip('/') or '/'
        if method in ('GET', 'HEAD', 'OPTIONS') or not path.startswith('/api/'):
            return await call_next(request)
        body = {}
        if _needs_body(method, path):
            try:
                body = await request.json()
            except (ValueError, TypeError):
                body = {}
            if not isinstance(body, dict):
                body = {}
        internal = request.scope.get('state', {}).get('_course_bootstrap') == (method, path)
        reason = gate_reason(policy, method, path, body, internal)
        if reason:
            return JSONResponse({'detail': reason}, 403)
        return await call_next(request)

    # 기존 CORS 미들웨어가 거절 응답도 감싸도록 바깥이 아니라 안쪽에 둔다
    app.user_middleware.append(Middleware(BaseHTTPMiddleware, dispatch=gate))
    return policy
