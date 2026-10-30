"""수업 경계 정본(procsvc/course_policy.py) — 수업 단계에서 허용 · 거절, 강사 서명으로 PBL을 푼 뒤, 학생이 스스로 풀려 할 때.

강사 비밀 키는 저장소에 없다. 서명이 실제로 도는지는 테스트마다 그때 만든 임시 키 쌍으로 확인한다(load_phase 의 keys 인자).
문지기(쓰기 요청 판정)는 실제 미들웨어를 작은 FastAPI 앱에 붙여 확인한다 — 뒤 라우트는 통과했다는 표시만 돌려준다.
"""
import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from procsvc import course_policy as cp

NOW = datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc)
HANDOVER_XML = cp.HANDOVER['xml']
HANDOVER_MAPPING = cp.HANDOVER['mapping']


def keypair():
    private = Ed25519PrivateKey.generate()
    raw = private.public_key().public_bytes_raw()
    return private, base64.urlsafe_b64encode(raw).decode().rstrip('=')


def pbl_payload(**over):
    return {'contract': cp.PHASE_CONTRACT, 'phase': 'pbl', 'note': '1기 PBL',
            'expires': (NOW + timedelta(days=30)).isoformat(), **over}


def write(tmp_path, envelope):
    path = tmp_path / 'course_phase.json'
    path.write_text(json.dumps(envelope, ensure_ascii=False), encoding='utf8')
    return path


COURSE = cp.Policy(cp.Phase('course'))
PBL = cp.Policy(cp.Phase('pbl'))


# ---------------------------------------------------------------- 단계 선언(강사 서명)
def test_단계_선언이_없으면_수업_단계다(tmp_path):
    assert cp.load_phase(tmp_path / 'course_phase.json', now=NOW) == cp.Phase('course')


def test_강사_서명이_맞는_PBL_선언이면_PBL_단계다(tmp_path):
    private, public = keypair()
    path = write(tmp_path, cp.sign_phase(pbl_payload(), private))
    phase = cp.load_phase(path, keys=(public,), now=NOW)
    assert (phase.name, phase.note, phase.expired) == ('pbl', '1기 PBL', False)


def test_기한이_지난_PBL_선언은_수업_단계로_읽고_지났다고_알린다(tmp_path):
    private, public = keypair()
    path = write(tmp_path, cp.sign_phase(pbl_payload(expires=(NOW - timedelta(seconds=1)).isoformat()), private))
    phase = cp.load_phase(path, keys=(public,), now=NOW)
    assert (phase.name, phase.expired) == ('course', True)


def _tampered_phase(private):           # 학생이 서명 뒤 단계를 바꿈
    envelope = cp.sign_phase(pbl_payload(phase='course'), private)
    envelope['payload']['phase'] = 'pbl'
    return envelope


def _other_domain(private):             # 같은 키로 다른 서명 영역(제공 문서 추출 묶음)에 붙은 서명을 재사용
    payload = pbl_payload()
    signature = private.sign(b'hyd-approved-extractions-v1\x00' + cp.canonical(payload))
    return {'payload': payload, 'signature': base64.urlsafe_b64encode(signature).decode().rstrip('=')}


@pytest.mark.parametrize('make, why', [
    (lambda private: {'payload': pbl_payload(), 'signature': ''}, '서명 없음'),
    (lambda private: cp.sign_phase(pbl_payload(), Ed25519PrivateKey.generate()), '학생이 만든 다른 키'),
    (_tampered_phase, '서명 뒤 내용 고침'),
    (_other_domain, '다른 서명 영역의 서명 재사용'),
    (lambda private: {'payload': pbl_payload()}, '서명 칸 없음'),
    (lambda private: cp.sign_phase(pbl_payload(contract='other'), private), '계약 이름이 다름'),
    (lambda private: cp.sign_phase(pbl_payload(phase='admin'), private), '없는 단계 이름'),
    (lambda private: cp.sign_phase(pbl_payload(expires='2026-12-01'), private), '시간대 없는 기한'),
    (lambda private: cp.sign_phase(pbl_payload(expires=None), private), '기한 없음'),
])
def test_학생이_만든_단계_선언은_process를_띄우지_않는다(tmp_path, make, why):
    private, public = keypair()
    path = write(tmp_path, make(private))
    with pytest.raises(cp.PhaseError):
        cp.load_phase(path, keys=(public,), now=NOW)


def test_깨진_JSON_단계_선언은_파일_이름을_대며_멈춘다(tmp_path):
    path = tmp_path / 'course_phase.json'
    path.write_text('{"payload": ', encoding='utf8')
    with pytest.raises(cp.PhaseError, match='course_phase.json'):
        cp.load_phase(path, now=NOW)


def test_저장소의_단계_선언은_실제_강사_공개_키로_확인된다():
    # 저장소에 선언 파일이 있으면 지금 공개 키로 통과해야 한다(없으면 수업 단계)
    phase = cp.load_phase()
    assert phase.name in cp.PHASES


# ---------------------------------------------------------------- 수업 AI 자리(제공 흐름에서 파생)
@pytest.mark.parametrize('definition, activity, slot', [
    ('c3_cooling', 'T_agent', 'c3_cooling/T_agent'),
    ('c3_pm', 'T_agent', 'c3_pm/T_agent'),
    ('c3_spare', 'T_agent', 'c3_spare/T_agent'),
    ('ShiftHandover', 'task_draft', 'handover/draft-1'),
    ('ShiftHandover', 'task_draft_r2', 'handover/draft-2'),
    ('ShiftHandover', 'task_draft_r3', 'handover/draft-3'),
    ('shift_handover', 'task:draft', 'handover/draft-1'),
    ('shift_handover', 'task:draft-r2', 'handover/draft-2'),       # 결함 1: 보완 요청 뒤 초안이 막히던 자리
    ('shift_handover', 'task:draft-r3', 'handover/draft-3'),
])
def test_수업_단계에서_준비된_흐름의_AI_단계는_수업_자리로_실행된다(definition, activity, slot):
    assert COURSE.ai_slot(definition, activity, {}) == slot


def test_수업_AI_자리는_제공_흐름의_에이전트_단계와_같다():
    from_flows = {(did, task) for did, (_, _, m) in cp.COURSE_FLOWS.items()
                  for task, item in m['tasks'].items() if isinstance(item, dict) and item.get('agent')}
    from_handover = {(cp.HANDOVER_IMPORT_ID, t) for t, item in cp.HANDOVER['mapping']['tasks'].items() if item.get('agent')}
    shipped = cp._json(cp.DEFINITIONS / 'shift_handover_v1.json')
    from_shipped = {(shipped['processDefinitionId'], a['id']) for a in shipped['activities'] if a.get('agentMode')}
    assert set(cp.AI_SLOTS) == from_flows | from_handover | from_shipped | {('ask_agent', 'task:answer')}


@pytest.mark.parametrize('definition, activity', [
    ('anomaly_response', 'task:diagnose'),       # 기준 흐름(펌프 · 팬) — 수업 밖
    ('my_cooling', 'T_agent'),                   # 학생이 따로 등록한 흐름
    ('manual_source_extraction', 'task:extract'),  # 제공 밖 문서의 실제 AI 추출
    ('c3_cooling', 'T_approve'),                 # 수업 흐름의 사람 단계 이름
])
def test_수업_단계에서_수업_밖_AI_단계는_까닭과_함께_거절된다(definition, activity):
    with pytest.raises(cp.AccessDenied, match='PBL'):
        COURSE.ai_slot(definition, activity, {})


@pytest.mark.parametrize('definition, activity', [('anomaly_response', 'task:diagnose'), ('my_cooling', 'T_agent'),
                                                  ('manual_source_extraction', 'task:extract')])
def test_PBL_단계에서는_수업_밖_AI_단계도_실행된다(definition, activity):
    assert PBL.ai_slot(definition, activity, {}) is None


@pytest.mark.parametrize('question, ok', [
    ('HM-8 매뉴얼의 쿨러 즉시 조치는?', True),
    ('가' * cp.QUESTION_MAX_CHARS, True),
    ('가' * (cp.QUESTION_MAX_CHARS + 1), False),
    ('   ', False),
    ('', False),
    (None, False),
    (['목록'], False),
])
@pytest.mark.parametrize('policy', [COURSE, PBL], ids=['수업', 'PBL'])
def test_질문은_두_단계_모두_1자에서_1000자까지만_AI가_답한다(policy, question, ok):
    if ok:
        assert policy.ai_slot('ask_agent', 'task:answer', {'question': question}) == 'question'
    else:
        with pytest.raises(cp.AccessDenied, match='1~1000자'):
            policy.ai_slot('ask_agent', 'task:answer', {'question': question})


# ---------------------------------------------------------------- 에이전트 · 흐름 · 문서 · 행동
@pytest.mark.parametrize('model, ok', [(None, True), ('', True), ('coding', True), ('gpt-6', False), ('claude-opus', False), ('Coding', False)])
def test_에이전트_모델은_두_단계_모두_수업_모델만(model, ok):
    assert (cp.Policy.agent_model_error(model) is None) is ok


@pytest.mark.parametrize('definition', ['ShiftHandover', 'shift_handover'])
def test_수업_단계에서_교대_단계에는_내_에이전트를_배정한다(definition):
    COURSE.assign(definition)


@pytest.mark.parametrize('definition', ['c3_cooling', 'anomaly_response', 'my_cooling', None])
def test_수업_단계에서_교대_밖_배정은_거절되고_PBL에서는_된다(definition):
    with pytest.raises(cp.AccessDenied, match='교대 인수인계'):
        COURSE.assign(definition)
    PBL.assign(definition)


@pytest.mark.parametrize('definition', sorted(cp.COURSE_DEFINITIONS))
def test_수업_단계에서_준비된_흐름은_시작된다(definition):
    COURSE.start(definition)


@pytest.mark.parametrize('definition', ['anomaly_response', 'my_cooling', 'alert_triage', ''])
def test_수업_단계에서_준비되지_않은_흐름의_시작은_거절되고_PBL에서는_된다(definition):
    with pytest.raises(cp.AccessDenied):
        COURSE.start(definition)
    PBL.start(definition)


def _renamed_and_moved(xml):
    import re
    renamed = re.sub(r'name="([^"]*)"', lambda m: f'name="{m.group(1)} (내 이름)"', xml)
    return re.sub(r'(<dc:Bounds [^>]*x=")(\d+)', lambda m: m.group(1) + str(int(m.group(2)) + 40), renamed)


def _structure_changed(xml):
    return xml.replace('</bpmn:process>', '<bpmn:task id="extra_step" name="추가 단계"/></bpmn:process>', 1)


@pytest.mark.parametrize('name, make, course_ok', [
    ('제공 그림 그대로', lambda x: x, True),
    ('이름 · 배치만 바꾼 그림', _renamed_and_moved, True),
    ('구조를 바꾼 그림', _structure_changed, False),
    ('깨진 XML', lambda x: x[: len(x) // 2], False),
    ('한도를 넘는 큰 그림', lambda x: x + ' ' * cp.FLOW_TEXT_MAX, False),
    ('DOCTYPE 이 든 그림', lambda x: '<!DOCTYPE x>' + x, False),
])
def test_수업_단계의_흐름_가져오기는_제공_교대_그림의_이름_배치만_바꾼_것까지(name, make, course_ok):
    xml = make(HANDOVER_XML)
    if course_ok:
        COURSE.import_flow(xml, 'ShiftHandover')
    else:
        with pytest.raises(cp.AccessDenied):
            COURSE.import_flow(xml, 'ShiftHandover')


def test_이름_배치만_바꾼_그림은_실제로_원본과_다른_글이다():
    assert _renamed_and_moved(HANDOVER_XML) != HANDOVER_XML


@pytest.mark.parametrize('name, make, pbl_ok', [
    ('구조를 바꾼 그림', _structure_changed, True),
    ('한도를 넘는 큰 그림', lambda x: x + ' ' * cp.FLOW_TEXT_MAX, False),
])
def test_PBL_단계의_흐름_가져오기는_구조를_바꿔도_되지만_대용량은_막힌다(name, make, pbl_ok):
    xml = make(HANDOVER_XML)
    if pbl_ok:
        PBL.import_flow(xml, 'my_flow')
    else:
        with pytest.raises(cp.AccessDenied):
            PBL.import_flow(xml, 'my_flow')


def test_수업_단계에서_교대_말고_다른_흐름_id로_가져오면_거절된다():
    with pytest.raises(cp.AccessDenied, match='교대'):
        COURSE.import_flow(HANDOVER_XML, 'my_cooling')


def _mapping(**changes):
    from copy import deepcopy
    mapping = deepcopy(HANDOVER_MAPPING)
    for key, value in changes.items():
        if key == 'agent':
            for task in ('task_draft', 'task_draft_r2', 'task_draft_r3'):
                mapping['tasks'][task]['agent'] = value
        else:
            mapping[key] = value
    return mapping


@pytest.mark.parametrize('name, mapping, ok', [
    ('제공 연결 그대로', _mapping(), True),
    ('흐름 이름만 바꿈', _mapping(name='우리 반 교대 인수인계'), True),
    ('세 초안 단계에 내 에이전트', _mapping(agent='agent:u-1a2b3c4d'), True),
    ('흐름 이름이 빔', _mapping(name=''), False),
    ('흐름 이름이 161자', _mapping(name='가' * 161), False),
    ('에이전트 칸이 에이전트 id 모양이 아님', _mapping(agent='user:kim-op'), False),
    ('시작 조건을 바꿈', _mapping(start={'kind': 'alert', 'patterns': ['PUMP_LEAKAGE']}), False),
    ('연결이 객체가 아님', None, False),
])
def test_수업_단계의_교대_등록은_흐름_이름과_세_초안_에이전트만_바꾼_연결까지(name, mapping, ok):
    if ok:
        COURSE.register_flow('ShiftHandover', HANDOVER_XML, mapping)
    else:
        with pytest.raises(cp.AccessDenied):
            COURSE.register_flow('ShiftHandover', HANDOVER_XML, mapping)
    PBL.register_flow('ShiftHandover', HANDOVER_XML, mapping)


@pytest.mark.parametrize('sha, course_ok', [
    *[(sha, True) for sha in sorted(cp.DOCUMENTS)],                 # 제공 문서 넷(HM-8 · PM-02 · PR-07 · HI-01)
    ('0' * 64, False),                                             # 허용 밖 문서
    ('', False), (None, False),
])
def test_수업_단계는_제공_문서만_받고_PBL은_어느_문서나_받는다(sha, course_ok):
    if course_ok:
        COURSE.document(sha)
    else:
        with pytest.raises(cp.AccessDenied, match='제공한 수업 문서'):
            COURSE.document(sha)
    PBL.document(sha)


def test_제공_문서_목록은_포털_예시_파일의_실제_해시와_같다():
    import hashlib
    samples = Path(__file__).resolve().parents[3] / 'it' / 'portal' / 'www' / 'samples'
    hashes = {hashlib.sha256(p.read_bytes()).hexdigest() for p in samples.iterdir() if p.is_file()}
    assert cp.DOCUMENTS <= hashes


@pytest.mark.parametrize('key', sorted(cp.Policy.ACTIONS))
def test_악용_지점과_수업_밖_AI_행동은_수업_단계에서만_막힌다(key):
    with pytest.raises(cp.AccessDenied, match='PBL'):
        COURSE.action(key)
    PBL.action(key)


def test_화면용_표는_단계마다_막힌_행동과_까닭을_내준다():
    course, pbl = COURSE.view(), PBL.view()
    assert all(not v['allowed'] and v['reason'] for v in course['actions'].values())
    assert all(v['allowed'] and v['reason'] is None for v in pbl['actions'].values())
    assert course['assignable_definitions'] == sorted(cp.HANDOVER_DEFINITIONS) and pbl['assignable_definitions'] is None
    assert course['model'] == pbl['model'] == cp.COURSE_MODEL


# ---------------------------------------------------------------- 문지기(실제 미들웨어)
def gate_app(policy_phase):
    app = FastAPI()
    policy = cp.mount(app, runtime_factory=lambda: None, phase=policy_phase)   # 실제 라우트가 먼저 — 아래 통과 표시는 그 밖의 경로만

    @app.api_route('/{path:path}', methods=['POST', 'PUT', 'DELETE'])
    async def passed(path: str, request: Request):
        return {'passed': path}

    assert app.state.course is policy
    return TestClient(app)


GATE_CASES = [
    # (방법, 경로, 본문, 수업 단계 통과?, PBL 통과?)
    ('POST', '/api/mcp/servers', {'name': 'outside', 'url': 'https://x.example/mcp'}, False, True),
    ('PUT', '/api/mcp/servers/neo4j', {}, False, True),
    ('POST', '/api/mcp/servers/neo4j/read-confirm', {'tool': 'submit_decision'}, False, True),
    ('POST', '/api/mcp/check', {'url': 'https://x.example/mcp'}, False, True),
    ('POST', '/api/mcp/connections/abc/start', {}, False, True),
    ('PUT', '/api/mcp/secrets/k', {'value': 'x'}, False, True),
    ('POST', '/api/mcp/servers/neo4j/check', {}, True, True),            # 준비된 서버 연결 검사는 수업에서도 된다
    ('POST', '/api/mcp/servers/neo4j/tools/read_neo4j_cypher/call', {}, True, True),
    ('POST', '/api/kg/manuals/batches/b1/golden-questions', {}, False, True),
    ('POST', '/api/kg/ddl/meanings', {}, False, True),
    ('POST', '/api/kg/ddl/preview', {}, True, True),                     # 구조 읽기(AI 없음)는 수업에서도
    ('POST', '/api/config/import', {}, False, True),
    ('POST', '/api/config/reset', {}, True, True),
    ('POST', '/api/agent-trials/run', {}, True, True),                   # 시험 비교 · 판단 채점은 AI 0 — 연다
    ('POST', '/api/eval/runs', {}, True, True),
    ('POST', '/api/roles', {}, True, True),
    ('POST', '/api/role-members', {}, True, True),
    ('PUT', '/api/kg/skills/s1', {}, True, True),
    ('POST', '/api/ask/reset', {}, True, True),
    ('DELETE', '/api/flows/ShiftHandover', {}, True, True),
    ('POST', '/api/flows/reset', {}, True, True),
    ('PUT', '/api/flows/ShiftHandover/mapping', {'mapping': {}}, True, True),   # 매핑 초안 저장 — 등록 때 검사(D2-02)
    ('PUT', '/api/flows/my_cooling/mapping', {'mapping': {}}, False, True),
    ('POST', '/api/flows/my_cooling/register', {}, False, True),
    ('POST', '/api/process/definitions/my_cooling/deploy', {'version': '1'}, False, True),
    ('POST', '/api/process/definitions/ShiftHandover/deploy', {'version': '1'}, True, True),
    ('POST', '/api/process/definitions', {'definition': {'processDefinitionId': 'my_cooling'}}, False, True),
    ('POST', '/api/instances/start', {'definition_id': 'c3_cooling', 'version': '1'}, True, True),
    ('POST', '/api/instances/start', {'definition_id': 'anomaly_response', 'version': '2.2'}, False, True),
    ('POST', '/api/instances/start', {'alert': {'alertId': 'a', 'asset': 'HYD-01'}}, True, True),
    ('PUT', '/api/agent-assignments', {'definition_id': 'ShiftHandover', 'activity_id': 'task_draft'}, True, True),
    ('PUT', '/api/agent-assignments', {'definition_id': 'c3_cooling', 'activity_id': 'T_agent'}, False, True),
    ('DELETE', '/api/agent-assignments/c3_cooling/T_agent', {}, False, True),
    ('POST', '/api/flows/import', {'xml': '<x/>', 'class_flow': True}, False, False),   # 수업 흐름 표시는 서버 안 설치만
    ('POST', '/api/process/definitions/c3_cooling/deploy', {'version': '1', 'class_flow': True}, False, False),
]


@pytest.mark.parametrize('method, path, body, course_ok, pbl_ok', GATE_CASES,
                         ids=[f'{m} {p}' for m, p, *_ in GATE_CASES])
def test_문지기는_수업_단계와_PBL에서_행동마다_다르게_통과시킨다(method, path, body, course_ok, pbl_ok):
    for phase, ok in ((cp.Phase('course'), course_ok), (cp.Phase('pbl'), pbl_ok)):
        response = gate_app(phase).request(method, path, json=body)
        if ok:
            assert response.status_code == 200, (phase.name, response.text)
        else:
            assert response.status_code == 403 and response.json()['detail'], (phase.name, response.text)


def test_학생은_요청으로_단계를_바꿀_수_없다():
    client = gate_app(cp.Phase('course'))
    for method in ('POST', 'PUT', 'DELETE'):
        client.request(method, '/api/course-access', json={'phase': 'pbl'})
    assert client.get('/api/course-access').json()['phase'] == 'course'


def test_화면은_지금_단계의_표를_읽는다():
    assert gate_app(cp.Phase('pbl')).get('/api/course-access').json()['label'] == 'PBL'


# ---------------------------------------------------------------- 워커용 판정 경로(인증 · 본문 해석)
@pytest.fixture
def runtime_key(tmp_path, monkeypatch):
    path = tmp_path / 'runtime.key'
    path.write_text('k' * 48, encoding='utf8')
    monkeypatch.setenv('HYD_WORKER_RUNTIME_KEY_FILE', str(path))
    return 'k' * 48


@pytest.mark.parametrize('authorization, status', [
    (None, 403),                       # 인증 없음
    ('Bearer ' + 'x' * 48, 403),       # 다른 키
    ('Bearer ' + 'k' * 48, 503),       # 맞는 키 — 판정까지 가서 처리 건 런타임이 없다는 까닭(본문을 JSON으로 읽었다는 뜻)
])
def test_워커용_판정은_실행기_인증을_확인하고_본문을_읽는다(runtime_key, authorization, status):
    client = gate_app(cp.Phase('course'))
    headers = {'authorization': authorization} if authorization else {}
    response = client.post('/internal/worker/course-decision', json={'tenant_id': 'hyd', 'todo_id': 'w1', 'consumer': 'c'},
                           headers=headers)
    assert response.status_code == status, response.text
    assert isinstance(response.json()['detail'], str)


@pytest.mark.parametrize('body', ['[1, 2]', 'not json', '"text"'])
def test_워커용_판정은_객체가_아닌_본문을_422로_거절한다(runtime_key, body):
    response = gate_app(cp.Phase('course')).post('/internal/worker/course-decision', content=body,
                                                  headers={'authorization': 'Bearer ' + 'k' * 48, 'content-type': 'application/json'})
    assert response.status_code == 422 and '형식' in response.json()['detail']
