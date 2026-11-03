"""수업 경계의 정본 — 무엇을 열고 무엇을 막는지는 이 모듈 한 곳에서 판정한다. 포털 화면은 GET /api/course-access(판정 결과와
막힌 까닭 문장), AI 워커는 POST /internal/worker/course-decision 으로 이 판정을 서버에서 읽는다(화면 · 워커에 규칙 · 문장 사본 없음).
판정이 쓰는 값 가운데 다른 모듈이 먼저 정한 것은 그 자리를 가리킨다: 수업 모델 이름은 장부 정책(course_ledger.POLICY — 워커도 읽는
표준 라이브러리 모듈), 질문 길이는 질문 계약(ask.MAX_QUESTION_CHARS).

원칙(사용자 확정): 학생은 포털 기능을 다 실제로 써 본다. 통제하는 것은 AI가 답을 만드는 자리(수업 AI 자리)뿐이고, 막는 것은 악용
지점뿐이다 — 허용 밖 문서 · 대용량, 외부 도구 서버 등록, 수업 모델 밖 모델. 비용의 최종 방어는 강의 중계 키의 한도다.

단계 둘: 수업(course) · PBL(pbl). PBL로 바꾸는 것은 강사뿐이다 — 강사 서명이 붙은 단계 선언(course_phase.json, 이 파일 옆)을 저장소에
올리면 학생 PC는 받아서 시작할 때 읽는다. 학생 PC에는 단계를 바꾸는 화면 · API · 설정이 없고, 선언을 고치면 서명이 깨져 process가
뜨지 않는다(코드를 고쳐 다시 빌드하면 바뀐다 — 비용 방어는 중계 키 한도). 선언이 없으면 수업 단계, PBL 기한은 판정할 때마다 지금
시각과 견준다(켜 둔 PC도 기한이 지나면 그때부터 수업 단계).

허용 목록은 손으로 적지 않는다 — 수업 AI 자리는 제공 흐름(course_flows.json · definitions/shift_handover.bpmn · .mapping.json ·
definitions/shift_handover_v1.json · ask_agent)에서, 제공 문서는 강사 서명 추출 묶음(course_extractions.json)에서 읽는다.
"""
import base64
import hashlib
import hmac
import json
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .course_ledger import POLICY as LEDGER_POLICY

# 수업 내용(흐름 A · B · C, 서명 추출 묶음, 단계 선언)은 이 규칙 옆에, 제공 교대 그림 · 정의는 정의 폴더(definitions)에 둔다 — 읽는 서비스는 process 뿐이다
HERE = Path(__file__).resolve().parent
DEFINITIONS = HERE.parent / 'definitions'
PHASE_FILE = HERE / 'course_phase.json'

# 강사 서명 공개 키 — 제공 문서 추출 묶음(manual_approved_cache)과 같은 키다. 비밀 키는 이미지 · 환경 변수 · 브라우저 · Git 어디에도
# 두지 않는다. 단계 선언은 서명 영역(PHASE_DOMAIN)이 달라 추출 묶음 서명을 단계 해제로 다시 쓸 수 없다.
PUBLIC_KEY = 'uiQXhElZ7HnRyuc_48KCdGsKa4k_oWppx0FKiK-dun0='
PHASE_KEYS = (PUBLIC_KEY,)
PHASE_DOMAIN = b'hyd-course-phase-v1\x00'
PHASE_CONTRACT = 'hyd-course-phase-v1'
PHASES = {'course': '수업', 'pbl': 'PBL'}

COURSE_MODEL = LEDGER_POLICY['model']   # 두 단계 모두 수업 모델 하나(다른 모델은 악용 지점) — 관문이 실제로 부르는 모델과 같은 값
HANDOVER_IMPORT_ID = 'ShiftHandover'     # 학생이 bpmn.io 로 가져오는 제공 교대 흐름
TEXT_MAX = 200_000                       # 흐름 그림 · 흐름 연결(매핑) · DDL 글 한도(글자, 두 단계 공통 — 대용량은 악용 지점)
# 녹화 없이 키 없는 PC에서 학생 문장으로 멈추는 수업 AI 자리(확정 방향: 교대 보완 요청 2번째 뒤의 초안). 녹화 목록은 이 자리를 빠짐으로 세지 않는다
UNRECORDED_SLOTS = frozenset({'handover/draft-3'})


class AccessDenied(ValueError):
    """수업 경계 밖의 요청. 문장은 학생에게 그대로 보인다."""


class PhaseError(RuntimeError):
    """단계 선언 파일이 깨졌거나 서명이 맞지 않는다 — process 를 띄우지 않는다(조용히 수업 단계로 돌지 않음)."""


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf8')


def decode64(value):
    return base64.b64decode(value + '=' * (-len(value) % 4), altchars=b'-_', validate=True)


def question_max_chars() -> int:
    """질문 길이 한도 — 질문 계약(ask.MAX_QUESTION_CHARS) 한 곳. 판정할 때 읽는다(이 모듈을 가져올 때 처리 엔진 전체를 끌어오지 않게)."""
    from .ask import MAX_QUESTION_CHARS
    return MAX_QUESTION_CHARS


def _until(expires) -> datetime:
    until = datetime.fromisoformat(str(expires).replace('Z', '+00:00'))
    if until.tzinfo is None:
        raise ValueError('timezone required')
    return until


# ---------------------------------------------------------------- 단계(수업 / PBL)
@dataclass(frozen=True)
class Phase:
    name: str                    # course | pbl
    note: str = ''               # 강사가 적은 한 줄(PBL 이름 등)
    expires: str | None = None   # PBL 선언의 기한(ISO, 시간대 있음)
    expired: bool = False        # 기한이 지나 수업 단계로 돌아왔다

    @property
    def label(self):
        return PHASES[self.name]

    @property
    def pbl(self):
        return self.name == 'pbl'

    def at(self, now: datetime) -> 'Phase':
        """지금 시각의 단계: PBL 선언의 기한이 지났으면 수업 단계(지났다는 표시와 함께)."""
        if self.pbl and self.expires and _until(self.expires) <= now:
            return Phase('course', note=self.note, expires=self.expires, expired=True)
        return self


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
        raise PhaseError(f'{path.name}: 단계 선언의 서명을 확인할 수 없습니다 — 이 파일은 고칠 수 없습니다(저장소의 원래 파일로 되돌리세요)')
    if payload.get('contract') != PHASE_CONTRACT or payload.get('phase') not in PHASES:
        raise PhaseError(f'{path.name}: 단계 선언의 계약 · 단계 이름이 다릅니다')
    expires = payload.get('expires')
    if payload['phase'] == 'pbl':
        try:
            _until(expires)
        except (ValueError, TypeError) as exc:
            raise PhaseError(f'{path.name}: PBL 선언에는 시간대가 있는 기한(expires)이 있어야 합니다') from exc
    return Phase(payload['phase'], note=str(payload.get('note') or ''), expires=expires).at(now or datetime.now(timezone.utc))


def sign_phase(payload: dict, private_key) -> dict:
    """강사 도구(workspace/개발/scripts/course_phase_sign.py)와 테스트가 쓰는 서명 — 비밀 키는 부르는 쪽이 쥔다."""
    signature = private_key.sign(PHASE_DOMAIN + canonical(payload))
    return {'payload': payload, 'signature': base64.urlsafe_b64encode(signature).decode().rstrip('=')}


# ---------------------------------------------------------------- 제공 자료에서 뽑는 목록
def _json(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


COURSE_FLOWS = _json(HERE / 'course_flows.json')          # 수업 흐름 A · B · C {id: [파일 이름, BPMN XML, 매핑]}
HANDOVER = {'xml': (DEFINITIONS / 'shift_handover.bpmn').read_text(encoding='utf8'),     # 제공 교대 BPMN(학생 랩 꾸러미와 같은 파일)
            'mapping': _json(DEFINITIONS / 'shift_handover.mapping.json')}
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
if not UNRECORDED_SLOTS <= set(AI_SLOTS.values()):          # 녹화 없이 멈추는 자리는 지금 수업 AI 자리여야 한다(흐름을 고쳐 자리가 사라지면 가져올 때 멈춤)
    raise RuntimeError(f'course_policy.UNRECORDED_SLOTS 에 수업 AI 자리가 아닌 이름이 있습니다: {sorted(UNRECORDED_SLOTS - set(AI_SLOTS.values()))}')
QUESTION_DEFINITION = next(d for (d, _), s in AI_SLOTS.items() if s == 'question')
HANDOVER_DEFINITIONS = frozenset(d for (d, _), s in AI_SLOTS.items() if s.startswith('handover/'))
HANDOVER_AGENT_TASKS = tuple(sorted(t for (d, t), s in AI_SLOTS.items() if d == HANDOVER_IMPORT_ID))
COURSE_DEFINITIONS = frozenset(COURSE_FLOWS) | HANDOVER_DEFINITIONS     # 수업 단계에서 시작 · 배포할 수 있는 흐름
DOCUMENTS = frozenset(EXTRACTIONS['payload']['documents'])
# 제공 문서 파일 이름(서명 묶음의 차례 — 적재 순서 A · B · C, 교대 실습 D). 포털은 이 목록으로 samples/<파일> 링크를 그린다(W2-21)
DOCUMENT_FILES = [d['filename'] for d in EXTRACTIONS['payload']['documents'].values()]


def within_text_max(value, what: str) -> None:
    """대용량 한 곳(두 단계 공통): 흐름 그림 · 흐름 연결(매핑) · DDL 글이 TEXT_MAX 글자를 넘으면 AccessDenied(무엇 · 한도 · 지금 크기).
    글이 아닌 값(매핑)은 JSON 글로 잰다. process 의 흐름 가져오기 · 등록 · DDL 미리보기가 같이 부른다."""
    size = len(value) if isinstance(value, str) else len(canonical(value).decode('utf8'))
    if size > TEXT_MAX:
        raise AccessDenied(f'{what}은(는) {TEXT_MAX:,}자 이하여야 합니다(지금 {size:,}자).')


def provided_document(sha256) -> bool:
    return isinstance(sha256, str) and sha256 in DOCUMENTS


# ---------------------------------------------------------------- 판정(단계마다 같은 함수)
class Policy:
    """한 PC의 지금 단계에서 내리는 판정. 거절은 AccessDenied(학생에게 보일 까닭)."""

    # 값마다 갈리는 판정의 까닭(수업 단계) — 거절 응답과 화면(view 의 reasons)이 같은 문장을 쓴다
    REASONS = {
        'ai_slot': ('수업에서는 준비된 흐름(냉각 · 정기 정비 · 예비품 구매 · 교대 인수인계)의 AI 단계와 질문만 실행합니다. '
                    '다른 흐름의 AI 단계는 PBL 단계에서 실행됩니다.'),
        'assign': '수업에서는 교대 인수인계 단계에만 내 에이전트를 배정합니다(다른 단계는 PBL 단계에서 엽니다).',
        'start': '수업에서는 준비된 흐름(냉각 · 정기 정비 · 예비품 구매 · 교대 인수인계)만 시작합니다(다른 흐름은 PBL 단계에서 엽니다).',
        'import_flow': ('수업에서 가져오는 흐름은 제공한 교대 인수인계 BPMN 하나입니다(파일 안의 흐름 식별 이름 ShiftHandover는 바꾸지 마세요). '
                        '화면에 보이는 이름과 배치만 바꿔 가져오고, 다른 흐름은 PBL 단계에서 가져옵니다.'),
        'edit_flow': '수업에서 연결(매핑)을 고치고 검사 · 등록하는 흐름은 제공한 교대 인수인계 하나입니다(다른 흐름은 PBL 단계에서 엽니다).',
        'deploy_flow': '수업에서 배포하거나 되돌리는 정의는 준비된 교대 인수인계 흐름뿐입니다(다른 정의는 PBL 단계에서 엽니다).',
        'define_flow': '수업에서는 정의 JSON 을 직접 등록하지 않습니다 — 교대 인수인계는 흐름 가져오기로 등록하고, 정의 등록은 PBL 단계에서 엽니다.',
        'document': '수업에서는 제공된 수업 문서(내용을 고치지 않은 원문)만 등록합니다. 다른 문서는 PBL 단계에서 등록합니다.',
    }

    def __init__(self, phase: Phase, clock=None):
        self._declared = phase
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    @property
    def phase(self) -> Phase:
        """판정 때마다 지금 시각으로 — 켜 둔 PC도 PBL 기한이 지나면 수업 단계."""
        return self._declared.at(self._clock())

    # -- AI가 답을 만드는 자리
    def ai_slot(self, definition_id, activity_id, inputs=None):
        """이 AI 단계를 실행해도 되는가 → 수업 AI 자리 이름(PBL의 수업 밖 단계는 None). 수업 단계의 수업 밖 단계는 거절."""
        slot = AI_SLOTS.get((definition_id, activity_id))
        if slot == 'question':
            question, limit = (inputs or {}).get('question'), question_max_chars()
            if not isinstance(question, str) or not question.strip() or len(question) > limit:
                raise AccessDenied(f'질문은 1~{limit}자로 적습니다.')
        if slot is None and not self.phase.pbl:
            raise AccessDenied(self.REASONS['ai_slot'])
        return slot

    # -- 에이전트 설정(두 단계 공통: 모델은 수업 모델 하나)
    @staticmethod
    def agent_model_error(model):
        if model not in (None, '', COURSE_MODEL):
            return '에이전트 모델은 수업 모델 하나만 씁니다 — 다른 모델 이름은 받지 않습니다(비워 두면 수업 모델).'
        return None

    def assign(self, definition_id):
        if not self.phase.pbl and definition_id not in HANDOVER_DEFINITIONS:
            raise AccessDenied(self.REASONS['assign'])

    # -- 흐름
    def start(self, definition_id):
        if not self.phase.pbl and definition_id not in COURSE_DEFINITIONS:
            raise AccessDenied(self.REASONS['start'])

    def edit_flow(self, definition_id, action='edit_flow'):
        """흐름 편집의 대상: action = import_flow(가져오기) · edit_flow(매핑 저장 · 검사 · 등록) · deploy_flow(정의 배포 · 되돌리기) ·
        define_flow(정의 JSON 등록). 수업 단계에서 고칠 수 있는 흐름은 제공 교대 하나다."""
        if not self.phase.pbl and definition_id != HANDOVER_IMPORT_ID:
            raise AccessDenied(self.REASONS[action])

    def import_flow(self, xml, definition_id):
        if not isinstance(xml, str):
            raise AccessDenied('흐름 그림(.bpmn)의 글이 필요합니다.')
        within_text_max(xml, '흐름 그림(.bpmn)')
        if self.phase.pbl:
            return
        self.edit_flow(definition_id or HANDOVER_IMPORT_ID, 'import_flow')
        changed = handover_structure_changes(xml)
        if changed:
            raise AccessDenied('수업에서는 제공한 교대 인수인계 BPMN의 이름과 배치만 바꿔 가져옵니다 — 이 그림은 '
                               + ' · '.join(changed) + '. 원본 파일을 다시 열어 이름 · 배치만 고치세요(구조를 바꾼 그림은 PBL 단계에서 가져옵니다).')

    def imported_mapping(self, mapping, previous=None):
        """가져온 그림의 연결(매핑). 수업 단계의 제공 교대는 화면이 흐름 이름 · 세 초안 단계 에이전트만 연다(W3-08) — 나머지 칸은 제공한
        연결로 채워 둬야 학생이 등록까지 갈 수 있다(한바퀴3: 자동 연결의 빈 실행 기능 칸이 잠겨 등록할 길이 없었다). 다시 가져오면 앞 초안의
        흐름 이름 · 고른 에이전트를 잇는다. PBL 은 자동 연결 그대로."""
        if self.phase.pbl:
            return mapping
        out = deepcopy(HANDOVER['mapping'])
        prev = previous if isinstance(previous, dict) else {}
        if isinstance(prev.get('name'), str) and 1 <= len(prev['name']) <= 160:
            out['name'] = prev['name']
        for task in HANDOVER_AGENT_TASKS:
            agent = ((prev.get('tasks') or {}).get(task) or {}).get('agent') if isinstance((prev.get('tasks') or {}).get(task), dict) else None
            if isinstance(agent, str) and re.fullmatch(r'agent:[A-Za-z0-9_.-]{1,80}', agent):
                out['tasks'][task]['agent'] = agent
        return out

    def register_flow(self, definition_id, xml, mapping):
        """등록 · 사전 검사가 같이 쓰는 판정(검사에서 먼저 알리고 등록에서 같은 문장으로 거절)."""
        within_text_max(mapping if mapping is not None else {}, '흐름 연결(매핑)')
        if self.phase.pbl:
            return
        self.edit_flow(definition_id)
        changed = handover_structure_changes(xml) + handover_mapping_changes(mapping)
        if changed:
            raise AccessDenied('수업에서는 제공한 교대 인수인계 그림과 연결에서 흐름 이름 · 세 초안 단계의 에이전트만 바꿔 등록합니다 — '
                               '바뀐 곳: ' + ' · '.join(changed) + '. 그 칸을 원본대로 되돌리세요(원본은 흐름 가져오기에서 다시 받을 수 있습니다).')

    # -- 문서
    def document(self, sha256):
        if not self.phase.pbl and not provided_document(sha256):
            raise AccessDenied(self.REASONS['document'])

    # -- 경로 단위로 막는 행동(악용 지점 · 수업 밖 AI)
    ACTIONS = {
        'tool_servers.register': ('외부 도구 서버 등록 · 비밀값 · 쓰기 도구를 읽기로 확인하기는 PBL 단계에서 엽니다. '
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
        """포털이 읽는 표 — 화면은 이 표로만 단추를 끄고 서버가 준 까닭을 보인다(문장 사본 없음)."""
        phase = self.phase
        course = not phase.pbl
        return {
            'phase': phase.name, 'label': phase.label, 'note': phase.note,
            'expires': phase.expires, 'expired': phase.expired,
            'model': COURSE_MODEL,
            'question_max_chars': question_max_chars(),
            'text_max': TEXT_MAX,
            'actions': {key: {'allowed': not course, 'reason': reason if course else None} for key, reason in self.ACTIONS.items()},
            'assignable_definitions': sorted(HANDOVER_DEFINITIONS) if course else None,
            'startable_definitions': sorted(COURSE_DEFINITIONS) if course else None,
            'importable_flow': HANDOVER_IMPORT_ID if course else None,
            # 수업 단계 교대 등록에서 바꿀 수 있는 칸: 흐름 이름 · 이 단계들의 에이전트(나머지 칸은 원본 그대로여야 등록된다)
            'handover_editable': {'flow_name': True, 'agent_tasks': list(HANDOVER_AGENT_TASKS)} if course else None,
            'documents': 'provided' if course else None,
            'provided_documents': DOCUMENT_FILES,
            # 목록 판정의 까닭(값이 목록 밖일 때 화면이 그대로 보인다) — 거절 응답과 같은 문장
            'reasons': {key: self.REASONS[key] for key in ('assign', 'start', 'import_flow', 'edit_flow', 'document')} if course else None,
            # 수업 AI 자리(키 없는 PC에서 강사 녹화로 재생) — recorded=False 는 녹화 없이 학생 문장으로 멈추는 자리
            'ai_slots': [{'slot': s, 'recorded': s not in UNRECORDED_SLOTS} for s in sorted(set(AI_SLOTS.values()))],
        }


# ---------------------------------------------------------------- 제공 교대 BPMN과 같은 흐름인가(이름 · 배치만 바꾼 것만 같다)
def flow_structure(xml) -> dict:
    """그림의 실행 구조 — 흐름 가져오기와 같은 파서(bpmn_import.parse_bpmn: 크기 · DOCTYPE · ENTITY 검사 포함)로 읽은 노드 종류 · id ·
    선 연결 · 분기 조건 · 기본 선 · 경계 타이머 · 읽지 않는 요소. 이름 · 좌표 · 레인 · 도구가 붙이는 꼬리표(incoming/outgoing ·
    exporter 등)는 실행을 바꾸지 않아 넣지 않는다 — 선에서 다시 만들 수 있는 incoming/outgoing 은 sequenceFlow 의 source · target 이 정본이다."""
    from . import bpmn_import
    parsed = bpmn_import.parse_bpmn(xml)
    return {
        'process': parsed['process']['id'],
        'tasks': sorted((t['id'], t['bpmn_type']) for t in parsed['tasks']),
        'starts': sorted((s['id'], s['definition']) for s in parsed['starts']),
        'ends': sorted((e['id'], e['definition']) for e in parsed['ends']),
        'gateways': sorted((g['id'], g['gateway_type'], g['default']) for g in parsed['gateways']),
        'boundaries': sorted((b['id'], b['attached_to'], b['interrupting'], b['timer']) for b in parsed['boundaries']),
        'flows': sorted((f['id'], f['source'], f['target'], f['condition_xml']) for f in parsed['flows']),
        'problems': sorted(((p.get('where') or {}).get('id') or '', p['field']) for p in parsed['problems']),
    }


_STRUCTURE_LABELS = {'process': '흐름(프로세스) id', 'tasks': '단계', 'starts': '시작', 'ends': '끝', 'gateways': '분기',
                     'boundaries': '시한(경계 타이머)', 'flows': '연결선 · 분기 조건', 'problems': '실행하지 않는 요소'}


def handover_structure_changes(xml) -> list[str]:
    """제공 교대 그림과 실행 구조가 다른 곳(학생이 읽을 말). 빈 목록 = 같은 흐름(이름 · 배치만 다름)."""
    try:
        got = flow_structure(xml)
    except ValueError as exc:       # 읽을 수 없는 그림(BpmnError 포함) — 그 까닭 그대로
        return [f'읽을 수 없는 그림입니다({exc})']
    want = flow_structure(HANDOVER['xml'])
    return [f'{_STRUCTURE_LABELS[key]}이(가) 원본과 다릅니다' for key in want if got[key] != want[key]]


def handover_structure_same(xml) -> bool:
    return not handover_structure_changes(xml)


def handover_mapping_changes(mapping) -> list[str]:
    """제공 교대 연결(매핑)과 다른 곳 — 흐름 이름(1~160자)과 세 초안 단계의 에이전트(agent:… id)만 바꿀 수 있다."""
    if not isinstance(mapping, dict) or not isinstance(mapping.get('tasks'), dict):
        return ['연결(매핑)이 제공한 모양이 아닙니다']
    original = HANDOVER['mapping']
    changes = []
    name = mapping.get('name')
    if not isinstance(name, str) or not 1 <= len(name) <= 160:
        changes.append('흐름 이름(1~160자)')
    from . import bpmn_import
    task_names = {t['id']: t['name'] for t in bpmn_import.parse_bpmn(HANDOVER['xml'])['tasks']}
    labels = {'start': '시작 입력 항목', 'lanes': '레인 담당', 'timers': '시한', 'flows': '분기 조건'}
    for key in sorted(set(original) | set(mapping)):
        if key in ('name', 'tasks'):
            continue
        if mapping.get(key) != original.get(key):
            changes.append(labels.get(key, f'연결 칸 {key}'))
    for task in sorted(set(original['tasks']) | set(mapping['tasks'])):
        want, got = original['tasks'].get(task), mapping['tasks'].get(task)
        label = f"단계 「{task_names.get(task, task)}」"
        if not isinstance(got, dict) or want is None:
            changes.append(label)
            continue
        if want.get('agent'):
            if not re.fullmatch(r'agent:[A-Za-z0-9_.-]{1,80}', str(got.get('agent', ''))):
                changes.append(label + '의 에이전트(agent:… 에이전트를 고르세요)')
            got, want = {k: v for k, v in got.items() if k != 'agent'}, {k: v for k, v in want.items() if k != 'agent'}
        if got != want:
            changes.append(label + '의 부품 · 담당')
    return changes


def handover_mapping_same(mapping) -> bool:
    return not handover_mapping_changes(mapping)


def document_sha256(data_b64: str) -> str:
    return hashlib.sha256(base64.b64decode(data_b64, validate=True)).hexdigest()


# ---------------------------------------------------------------- 워커 요청 하나의 판정(수업 판정 · 관문 토큰이 같이 쓴다)
WORKER_AUTH_FAILED = '실행기 인증을 확인할 수 없습니다'


def require_worker(authorization) -> None:
    """워커만 부르는 내부 경로의 실행기 인증(인증 파일 키) 한 곳. 틀리면 401 — 수업 경계 · 장부 거절(403)과 갈라, 워커가 「수업 권한」이
    아니라 「연결 확인 필요(시작 파일 다시 실행)」로 멈추게 한다."""
    from fastapi import HTTPException
    from . import worker_credentials
    if not hmac.compare_digest((authorization or '').removeprefix('Bearer ').encode(), worker_credentials._key().encode()):
        raise HTTPException(401, WORKER_AUTH_FAILED)


def judged_claim(policy: Policy, runtime, body: dict, authorization):
    """실행기 인증 → 실행 서비스(같은 교육 공간) → 살아 있는 점유 → 그 처리 건 → 수업 AI 자리. → (점유 행, 처리 건 변수, 자리).
    거절: HTTPException(인증 401 · 실행 서비스 없음 503 · 점유 409 · 처리 건 409), AccessDenied(수업 경계 — 부르는 쪽이 403으로).
    인증이 먼저다 — 인증 없는 요청에는 실행 서비스 상태도 알리지 않는다."""
    from fastapi import HTTPException
    from . import engine, worker_credentials
    require_worker(authorization)
    if runtime is None or body.get('tenant_id') != runtime.tenant_id:
        raise HTTPException(503, '수업 판정에 필요한 실행 서비스가 없습니다')
    row = worker_credentials._claim(runtime, body)
    inst = runtime.repo.get_instance(row['proc_inst_id'])
    if not inst or inst.get('tenant_id') != runtime.tenant_id:
        raise HTTPException(409, '이 작업의 처리 건이 없습니다')
    values = engine.variables(inst)
    return row, values, policy.ai_slot(inst['proc_def_id'], row['activity_id'], values)


# ---------------------------------------------------------------- process API에 붙이기
# 경로 하나가 곧 행동인 것(본문을 볼 필요 없음). 본문을 봐야 하는 판정(흐름 그림 · 매핑 · 문서 · 모델)은 그 라우트가 Policy 를 부른다.
_PATH_ACTIONS = (
    ('POST', re.compile(r'/api/mcp/servers'), 'tool_servers.register'),
    ('PUT', re.compile(r'/api/mcp/servers/[^/]+'), 'tool_servers.register'),
    ('POST', re.compile(r'/api/mcp/servers/[^/]+/read-confirm'), 'tool_servers.register'),
    ('POST', re.compile(r'/api/mcp/check'), 'tool_servers.register'),
    ('PUT', re.compile(r'/api/mcp/secrets/[^/]+'), 'tool_servers.register'),
    ('DELETE', re.compile(r'/api/mcp/secrets/[^/]+'), 'tool_servers.register'),
    ('POST', re.compile(r'/api/kg/manuals/batches/[^/]+/golden-questions'), 'documents.golden'),
    ('POST', re.compile(r'/api/kg/ddl/meanings'), 'ddl.meanings'),
    ('POST', re.compile(r'/api/config/import'), 'config.import'),
)
# 흐름 id 가 주소에 있는 흐름 편집(가져오기 뒤의 매핑 저장 · 검사 · 등록 · 정의 배포 · 되돌리기)
_FLOW_EDIT = re.compile(r'/api/(?:flows/(?P<a>[^/]+)/(?:mapping|check|register)|process/definitions/(?P<b>[^/]+)/(?:deploy|rollback))')
# 제공 흐름을 서버 안에서 설치하는 길(course_bootstrap) 말고는 「수업 흐름」 표시를 보낼 수 없다
_CLASS_FLOW_PATHS = re.compile(r'/api/(?:flows/import|flows/[^/]+/(?:check|register)|process/definitions/[^/]+/deploy)')


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
            policy.edit_flow(edit.group('a') or edit.group('b'), 'edit_flow' if edit.group('a') else 'deploy_flow')
        elif method == 'POST' and path == '/api/process/definitions':
            policy.edit_flow((body.get('definition') or {}).get('processDefinitionId') if isinstance(body.get('definition'), dict)
                             else body.get('processDefinitionId'), 'define_flow')
        elif method == 'POST' and path == '/api/instances/start' and body.get('definition_id') is not None:
            policy.start(body.get('definition_id'))
        elif method == 'PUT' and path == '/api/agent-assignments':
            policy.assign(body.get('definition_id'))
        elif method == 'DELETE' and path.startswith('/api/agent-assignments/'):
            policy.assign(path.split('/')[3])
    except AccessDenied as exc:
        return str(exc)
    return None


# 본문을 다 읽기 전에 크기로 막는 쓰기(대용량은 악용 지점 — 두 단계 공통). 정의 등록 · 처리 건 시작은 내용 검사(정의 50만 자 · 시작 값
# 25만 6천 자 — definition_registry · instances)보다 넉넉한 바이트(한국어 3바이트)로 먼저 막는다. 그 밖의 본문 크기는 포털 nginx 가 막는다.
BODY_MAX = {'/api/process/definitions': 2_000_000, '/api/instances/start': 1_000_000}


def body_too_large(path, headers):
    """(상태, 학생 문장) 또는 None. 길이를 적지 않은(쪼개 보내는) 본문은 크기를 미리 알 수 없어 받지 않는다."""
    limit = BODY_MAX.get(path)
    if limit is None:
        return None
    length = headers.get('content-length')
    if length is None or not length.isdigit():
        return 411, '요청 본문의 길이(Content-Length)를 적어 보내야 합니다'
    if int(length) > limit:
        return 413, f'요청이 너무 큽니다(최대 {limit // 1_000_000} MB, 지금 {int(length):,}바이트) — 정의 · 시작 값을 줄이세요'
    return None


def _needs_body(method, path):
    return method in ('POST', 'PUT') and (path == '/api/instances/start' or path == '/api/agent-assignments'
                                          or path == '/api/process/definitions' or bool(_CLASS_FLOW_PATHS.fullmatch(path)))


def mount(app, *, runtime_factory, phase: Phase | None = None, clock=None):
    """수업 경계를 process API에 붙인다: 판정 표(app.state.course), 화면용 GET /api/course-access, 워커용 판정, 쓰기 요청 문지기."""
    import asyncio
    from fastapi import HTTPException, Request
    from fastapi.responses import JSONResponse
    from starlette.middleware import Middleware
    from starlette.middleware.base import BaseHTTPMiddleware

    policy = Policy(phase if phase is not None else load_phase(), clock=clock)
    app.state.course = policy

    @app.get('/api/course-access')
    def course_access():
        return policy.view()

    def decide(body, authorization):
        try:
            _, _, slot = judged_claim(policy, runtime_factory(), body, authorization)
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
        if method in ('POST', 'PUT'):
            refused = body_too_large(path, request.headers)
            if refused:
                return JSONResponse({'detail': refused[1]}, refused[0])
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
