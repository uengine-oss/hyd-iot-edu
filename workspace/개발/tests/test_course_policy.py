"""수업 경계 정본(procsvc/course_policy.py) — 수업 단계에서 허용 · 거절, 강사 서명으로 PBL을 푼 뒤, 기한이 지난 뒤, 학생이 스스로 풀려 할 때.

강사 비밀 키는 저장소에 없다. 서명이 실제로 도는지는 테스트마다 그때 만든 임시 키 쌍으로 확인한다(load_phase 의 keys 인자).
시계는 바깥이라 대체한다(Policy 의 clock — 기한 판정). 흐름 그림 비교는 실제 bpmn-js 17.11.1 로 저장한 제공 교대 그림 셋(data/bpmn)과
그것을 Camunda Modeler 식(incoming/outgoing · exporter)으로 다시 쓴 그림 · 구조를 바꾼 그림으로 판정한다.
문지기(쓰기 요청 판정)는 실제 미들웨어를 작은 FastAPI 앱에 붙여 확인한다 — 뒤 라우트는 통과했다는 표시만 돌려준다.
"""
import base64
import gzip
import json
import re
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from procsvc import ask, course_ledger, course_policy as cp
from conftest import REPLAY_DIR as REPLAY, SAMPLES, EngineClock as Clock, definition_version

NOW = datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc)
HERE = Path(__file__).resolve().parent
BPMN_DIR = HERE / 'data' / 'bpmn'
HANDOVER_XML = cp.HANDOVER['xml']
HANDOVER_MAPPING = cp.HANDOVER['mapping']
COURSE = cp.Policy(cp.Phase('course'))
PBL = cp.Policy(cp.Phase('pbl'))
LIMIT = ask.MAX_QUESTION_CHARS


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


# ---------------------------------------------------------------- 단계 선언(강사 서명)
def test_단계_선언이_없으면_수업_단계다(tmp_path):
    assert cp.load_phase(tmp_path / 'course_phase.json', now=NOW) == cp.Phase('course')


def test_강사_서명이_맞는_PBL_선언이면_PBL_단계다(tmp_path):
    private, public = keypair()
    path = write(tmp_path, cp.sign_phase(pbl_payload(), private))
    phase = cp.load_phase(path, keys=(public,), now=NOW)
    assert (phase.name, phase.note, phase.expired) == ('pbl', '1기 PBL', False)


def test_공개_키를_끝_등호를_붙여_적어도_같은_키로_서명을_확인한다(tmp_path):
    private, public = keypair()
    padded = public + '=' * (-len(public) % 4)
    path = write(tmp_path, cp.sign_phase(pbl_payload(), private))
    assert cp.load_phase(path, keys=(padded,), now=NOW).name == 'pbl'


def test_켤_때_기한이_이미_지난_PBL_선언은_수업_단계로_읽고_지났다고_알린다(tmp_path):
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
], ids=lambda v: v if isinstance(v, str) else '')
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


# ---------------------------------------------------------------- 켜 둔 PC의 PBL 기한(P2-07)
@pytest.mark.parametrize('seconds, phase, expired', [(-1, 'pbl', False), (0, 'course', True), (3600, 'course', True)],
                         ids=['기한 1초 전', '기한 그 시각', '기한 1시간 뒤'])
def test_켜_둔_PC도_PBL_기한이_지나면_그때부터_수업_단계로_판정한다(seconds, phase, expired):
    until = NOW + timedelta(days=1)
    clock = Clock(NOW)
    policy = cp.Policy(cp.Phase('pbl', note='1기 PBL', expires=until.isoformat()), clock=clock)
    assert policy.phase.name == 'pbl'                               # 켤 때는 PBL
    clock.at = until + timedelta(seconds=seconds)
    assert (policy.phase.name, policy.phase.expired) == (phase, expired)
    assert (policy.view()['phase'], policy.view()['expired']) == (phase, expired)


def test_기한이_지난_뒤에는_수업_밖_AI_단계를_다시_거절한다():
    until = NOW + timedelta(hours=1)
    clock = Clock(NOW)
    policy = cp.Policy(cp.Phase('pbl', expires=until.isoformat()), clock=clock)
    assert policy.ai_slot('anomaly_response', 'task:diagnose', {}) is None
    clock.at = until
    with pytest.raises(cp.AccessDenied, match='PBL'):
        policy.ai_slot('anomaly_response', 'task:diagnose', {})


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
    ('ask_agent', 'task:answer', 'question'),
])
def test_수업_단계에서_준비된_흐름의_AI_단계는_수업_자리로_실행된다(definition, activity, slot):
    inputs = {'question': '쿨러 즉시 조치는?'} if slot == 'question' else {}
    assert COURSE.ai_slot(definition, activity, inputs) == slot


def _recorded_slots():
    return {json.loads(gzip.decompress(p.read_bytes()))['slot'] for p in REPLAY.glob('*.json.gz')}


def test_수업_AI_자리는_모두_강사_녹화가_있거나_녹화_없이_멈추는_자리로_정해져_있다():
    slots = set(cp.AI_SLOTS.values())
    assert slots - cp.UNRECORDED_SLOTS <= _recorded_slots()          # 녹화가 빠진 수업 자리 없음
    assert cp.UNRECORDED_SLOTS <= slots and not cp.UNRECORDED_SLOTS & _recorded_slots()


def test_강사_녹화는_모두_지금_수업_AI_자리의_것이다():
    assert _recorded_slots() <= set(cp.AI_SLOTS.values())


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
    ('가', True),                                 # 경계: 1자
    ('HM-8 매뉴얼의 쿨러 즉시 조치는?', True),
    ('가' * LIMIT, True),                         # 경계: 한도 그대로
    ('가' * (LIMIT + 1), False),
    ('   ', False),
    ('', False),
    (None, False),
    (['목록'], False),
])
@pytest.mark.parametrize('policy', [COURSE, PBL], ids=['수업', 'PBL'])
def test_질문은_두_단계_모두_질문_계약의_길이_안에서만_AI가_답한다(policy, question, ok):
    if ok:
        assert policy.ai_slot('ask_agent', 'task:answer', {'question': question}) == 'question'
    else:
        with pytest.raises(cp.AccessDenied, match=f'1~{LIMIT}자'):
            policy.ai_slot('ask_agent', 'task:answer', {'question': question})


# ---------------------------------------------------------------- 에이전트 · 흐름 · 문서 · 행동
@pytest.mark.parametrize('model, ok', [(None, True), ('', True), ('coding', True), ('gpt-6', False), ('claude-opus', False), ('Coding', False)])
def test_에이전트_모델은_두_단계_모두_수업_모델만(model, ok):
    assert (cp.Policy.agent_model_error(model) is None) is ok


def test_수업_모델은_관문이_실제로_부르는_모델과_같은_값이다():
    assert cp.COURSE_MODEL == course_ledger.POLICY['model'] == COURSE.view()['model']


@pytest.mark.parametrize('definition', ['ShiftHandover', 'shift_handover'])
def test_수업_단계에서_교대_단계에는_내_에이전트를_배정한다(definition):
    COURSE.assign(definition)


@pytest.mark.parametrize('definition', ['c3_cooling', 'anomaly_response', 'my_cooling', None])
def test_수업_단계에서_교대_밖_배정은_서버_까닭으로_거절된다(definition):
    with pytest.raises(cp.AccessDenied) as refused:
        COURSE.assign(definition)
    assert str(refused.value) == cp.Policy.REASONS['assign']


@pytest.mark.parametrize('definition', ['c3_cooling', 'anomaly_response', 'my_cooling', None])
def test_PBL_단계에서는_어느_단계에나_내_에이전트를_배정한다(definition):
    PBL.assign(definition)


@pytest.mark.parametrize('definition', sorted(cp.COURSE_DEFINITIONS))
def test_수업_단계에서_준비된_흐름은_시작된다(definition):
    COURSE.start(definition)


@pytest.mark.parametrize('definition', ['anomaly_response', 'my_cooling', 'alert_triage', ''])
def test_수업_단계에서_준비되지_않은_흐름의_시작은_서버_까닭으로_거절된다(definition):
    with pytest.raises(cp.AccessDenied) as refused:
        COURSE.start(definition)
    assert str(refused.value) == cp.Policy.REASONS['start']


@pytest.mark.parametrize('definition', ['anomaly_response', 'my_cooling', 'alert_triage', ''])
def test_PBL_단계에서는_어느_흐름이나_시작된다(definition):
    PBL.start(definition)


# ---------------------------------------------------------------- 흐름 그림: 이름 · 배치만 바꾼 것만 제공 교대와 같다(P5-12 · P2-25)
def bpmn(name):
    return (BPMN_DIR / f'ShiftHandover_bpmnjs17_{name}.bpmn').read_text(encoding='utf8')


def camunda_style(xml):
    """Camunda Modeler 처럼 다시 쓴 그림: 노드마다 그 노드로 들어오고 나가는 선을 incoming/outgoing 자식으로 적고 exporter 를 단다."""
    flows = re.findall(r'<bpmn:sequenceFlow id="([^"]+)"[^>]*?sourceRef="([^"]+)" targetRef="([^"]+)"', xml)
    def node(m):
        tag, nid, rest = m.group(1), m.group(2), m.group(3)
        refs = [f'<bpmn:incoming>{f}</bpmn:incoming>' for f, _, t in flows if t == nid] + \
               [f'<bpmn:outgoing>{f}</bpmn:outgoing>' for f, s, _ in flows if s == nid]
        return f'<bpmn:{tag} id="{nid}"{rest}>' + ''.join(refs) + f'</bpmn:{tag}>' if refs else m.group(0)
    xml = re.sub(r'<bpmn:(startEvent|endEvent|userTask|exclusiveGateway) id="([^"]+)"([^>]*?) />', node, xml)
    return xml.replace('targetNamespace=', 'exporter="Camunda Modeler" exporterVersion="5.31.0" targetNamespace=', 1)


@pytest.mark.parametrize('name, make', [
    ('bpmn-js 로 저장만 한 그림', lambda: bpmn('plain')),
    ('bpmn-js 에서 단계 이름을 바꾼 그림', lambda: bpmn('renamed')),
    ('bpmn-js 에서 단계를 옮긴 그림', lambda: bpmn('moved')),
    ('Camunda Modeler 식 incoming/outgoing · exporter', lambda: camunda_style(bpmn('renamed'))),
    ('저장소의 제공 원본 그대로', lambda: HANDOVER_XML),
])
def test_수업_단계에서_이름_배치만_바꿔_저장한_교대_그림은_가져온다(name, make):
    COURSE.import_flow(make(), 'ShiftHandover')


def test_Camunda_식으로_다시_쓴_그림은_실제로_incoming_outgoing을_담는다():
    xml = camunda_style(bpmn('plain'))
    assert xml.count('<bpmn:incoming>') == xml.count('<bpmn:sequenceFlow ') and 'exporter="Camunda Modeler"' in xml


STRUCTURE_CHANGES = [
    ('선이 가는 곳을 바꿈', lambda x: x.replace('sourceRef="gw_sender" targetRef="ev_rejected"', 'sourceRef="gw_sender" targetRef="ev_followup"'), '연결선'),
    ('선을 지움', lambda x: re.sub(r'\s*<bpmn:sequenceFlow id="seq_8" [^>]*/>', '', x, count=1), '연결선'),
    ('단계를 더함', lambda x: x.replace('</bpmn:process>', '<bpmn:userTask id="task_extra" name="추가 단계" /></bpmn:process>', 1), '단계'),
    ('단계 종류를 바꿈', lambda x: x.replace('<bpmn:userTask id="task_draft" ', '<bpmn:serviceTask id="task_draft" ', 1), '단계'),
    ('단계 id 를 바꿈', lambda x: x.replace('"task_sender"', '"task_sender_x"'), '단계'),
    ('분기에 기본 선을 둠', lambda x: x.replace('<bpmn:exclusiveGateway id="gw_sender" ', '<bpmn:exclusiveGateway id="gw_sender" default="seq_5" ', 1), '분기'),
    ('선에 조건식을 붙임', lambda x: re.sub(r'(<bpmn:sequenceFlow id="seq_3" [^>]*?) />',
                                         r'\1><bpmn:conditionExpression>${sender_decision == "approve"}</bpmn:conditionExpression></bpmn:sequenceFlow>', x, count=1), '연결선'),
    ('시한(경계 타이머)을 붙임', lambda x: x.replace('</bpmn:process>', '<bpmn:boundaryEvent id="b_late" attachedToRef="task_sender"><bpmn:timerEventDefinition>'
                                                 '<bpmn:timeDuration>PT10M</bpmn:timeDuration></bpmn:timerEventDefinition></bpmn:boundaryEvent></bpmn:process>', 1), '시한'),
]


@pytest.mark.parametrize('name, change, says', STRUCTURE_CHANGES, ids=[c[0] for c in STRUCTURE_CHANGES])
def test_수업_단계에서_구조를_바꾼_교대_그림은_어디가_다른지_말하며_거절된다(name, change, says):
    xml = change(bpmn('renamed'))
    assert xml != bpmn('renamed')
    with pytest.raises(cp.AccessDenied, match=says):
        COURSE.import_flow(xml, 'ShiftHandover')


@pytest.mark.parametrize('name, change, says', STRUCTURE_CHANGES, ids=[c[0] for c in STRUCTURE_CHANGES])
def test_PBL_단계에서는_구조를_바꾼_그림도_가져온다(name, change, says):
    PBL.import_flow(change(bpmn('renamed')), 'my_flow')


@pytest.mark.parametrize('name, xml, says', [
    ('깨진 XML', HANDOVER_XML[: len(HANDOVER_XML) // 2], '읽을 수 없는'),
    ('DOCTYPE 이 든 그림', '<!DOCTYPE x>' + HANDOVER_XML, '읽을 수 없는'),
    ('글이 아님', None, '글이 필요'),
])
def test_읽을_수_없는_그림은_수업_단계에서_까닭과_함께_거절된다(name, xml, says):
    with pytest.raises(cp.AccessDenied, match=says):
        COURSE.import_flow(xml, 'ShiftHandover')


@pytest.mark.parametrize('policy', [COURSE, PBL], ids=['수업', 'PBL'])
def test_대용량_그림은_두_단계_모두_한도_글자에서_거절된다(policy):
    big = HANDOVER_XML + ' ' * (cp.TEXT_MAX - len(HANDOVER_XML) + 1)
    with pytest.raises(cp.AccessDenied, match=f'{cp.TEXT_MAX:,}자'):
        policy.import_flow(big, 'ShiftHandover')


def test_한도_글자_그대로의_그림은_크기로_거절되지_않는다():
    exactly = HANDOVER_XML + ' ' * (cp.TEXT_MAX - len(HANDOVER_XML))
    assert len(exactly) == cp.TEXT_MAX
    COURSE.import_flow(exactly, 'ShiftHandover')


def test_수업_단계에서_교대_말고_다른_흐름_id로_가져오면_거절된다():
    with pytest.raises(cp.AccessDenied) as refused:
        COURSE.import_flow(HANDOVER_XML, 'my_cooling')
    assert str(refused.value) == cp.Policy.REASONS['import_flow']


# ---------------------------------------------------------------- 흐름 연결(매핑): 흐름 이름 · 세 초안 에이전트만 바꿀 수 있다
def _mapping(**changes):
    mapping = deepcopy(HANDOVER_MAPPING)
    for key, value in changes.items():
        if key == 'agent':
            for task in cp.HANDOVER_AGENT_TASKS:
                mapping['tasks'][task]['agent'] = value
        else:
            mapping[key] = value
    return mapping


def _sender_part_changed():
    mapping = _mapping()
    mapping['tasks']['task_sender']['part'] = 'part:other'
    return mapping


@pytest.mark.parametrize('name, mapping', [
    ('제공 연결 그대로', _mapping()),
    ('흐름 이름만 바꿈', _mapping(name='우리 반 교대 인수인계')),
    ('흐름 이름 1자', _mapping(name='가')),
    ('흐름 이름 160자', _mapping(name='가' * 160)),
    ('세 초안 단계에 내 에이전트', _mapping(agent='agent:u-1a2b3c4d')),
])
def test_수업_단계의_교대_등록은_흐름_이름과_세_초안_에이전트만_바꾼_연결을_받는다(name, mapping):
    COURSE.register_flow('ShiftHandover', bpmn('renamed'), mapping)


@pytest.mark.parametrize('name, mapping, says', [
    ('흐름 이름이 빔', _mapping(name=''), '흐름 이름'),
    ('흐름 이름이 161자', _mapping(name='가' * 161), '흐름 이름'),
    ('에이전트 칸이 에이전트 id 모양이 아님', _mapping(agent='user:kim-op'), '에이전트'),
    ('시작 조건을 바꿈', _mapping(start={'kind': 'alert', 'patterns': ['PUMP_LEAKAGE']}), '시작 입력 항목'),
    ('분기 조건을 바꿈', _mapping(flows={}), '분기 조건'),
    ('사람 단계의 부품을 바꿈', _sender_part_changed(), '인계자 검토'),
    ('연결이 객체가 아님', None, '모양'),
])
def test_수업_단계의_교대_등록은_다른_칸을_바꾼_연결을_바뀐_곳과_함께_거절한다(name, mapping, says):
    with pytest.raises(cp.AccessDenied, match=says):
        COURSE.register_flow('ShiftHandover', bpmn('renamed'), mapping)


@pytest.mark.parametrize('name, mapping', [('시작 조건을 바꿈', _mapping(start={'kind': 'alert'})), ('사람 단계의 부품을 바꿈', _sender_part_changed())])
def test_PBL_단계의_교대_등록은_어느_칸을_바꿔도_받는다(name, mapping):
    PBL.register_flow('ShiftHandover', bpmn('renamed'), mapping)


@pytest.mark.parametrize('policy', [COURSE, PBL], ids=['수업', 'PBL'])
def test_대용량_연결은_두_단계_모두_등록에서_거절된다(policy):
    mapping = _mapping(name='가')
    mapping['tasks']['task_draft']['note'] = '가' * cp.TEXT_MAX
    with pytest.raises(cp.AccessDenied, match='흐름 연결'):
        policy.register_flow('ShiftHandover', HANDOVER_XML, mapping)


def test_수업_단계의_교대_등록은_구조를_바꾼_그림도_거절한다():
    with pytest.raises(cp.AccessDenied, match='연결선'):
        COURSE.register_flow('ShiftHandover', STRUCTURE_CHANGES[0][1](bpmn('renamed')), _mapping())


# ---------------------------------------------------------------- 문서
@pytest.mark.parametrize('sha, course_ok', [
    *[(sha, True) for sha in sorted(cp.DOCUMENTS)],                 # 제공 문서 넷(HM-8 · PM-02 · PR-07 · HI-01)
    ('0' * 64, False),                                             # 허용 밖 문서
    ('', False), (None, False),
])
def test_수업_단계는_제공_문서만_받는다(sha, course_ok):
    if course_ok:
        COURSE.document(sha)
    else:
        with pytest.raises(cp.AccessDenied) as refused:
            COURSE.document(sha)
        assert str(refused.value) == cp.Policy.REASONS['document']


@pytest.mark.parametrize('sha', ['0' * 64, '', None])
def test_PBL_단계는_어느_문서나_받는다(sha):
    PBL.document(sha)


def test_제공_문서_목록은_포털_예시_파일의_실제_해시와_같다():
    import hashlib
    hashes = {hashlib.sha256(p.read_bytes()).hexdigest() for p in SAMPLES.iterdir() if p.is_file()}
    assert cp.DOCUMENTS <= hashes


@pytest.mark.parametrize('key', sorted(cp.Policy.ACTIONS))
def test_악용_지점과_수업_밖_AI_행동은_수업_단계에서_막힌다(key):
    with pytest.raises(cp.AccessDenied, match='PBL'):
        COURSE.action(key)


@pytest.mark.parametrize('key', sorted(cp.Policy.ACTIONS))
def test_PBL_단계에서는_그_행동이_열린다(key):
    PBL.action(key)


# ---------------------------------------------------------------- 화면용 표(GET /api/course-access)
def test_수업_단계의_표는_막힌_행동과_목록_판정마다_거절_응답과_같은_까닭을_준다():
    view = COURSE.view()
    assert all(not v['allowed'] and v['reason'] == cp.Policy.ACTIONS[k] for k, v in view['actions'].items())
    for key, refuse in (('assign', lambda: COURSE.assign('c3_cooling')), ('start', lambda: COURSE.start('my_flow')),
                        ('import_flow', lambda: COURSE.import_flow(HANDOVER_XML, 'my_flow')), ('document', lambda: COURSE.document('0' * 64))):
        with pytest.raises(cp.AccessDenied) as refused:
            refuse()
        assert view['reasons'][key] == str(refused.value)
    assert view['assignable_definitions'] == sorted(cp.HANDOVER_DEFINITIONS)
    assert view['handover_editable'] == {'flow_name': True, 'agent_tasks': ['task_draft', 'task_draft_r2', 'task_draft_r3']}


def test_표의_제공_문서는_포털이_내주는_파일이고_그_파일만_수업_문서로_받는다():
    """W2-21: 화면의 제공 문서 링크는 이 목록으로 그린다(index.html 손 목록 없음) — 목록의 파일은 포털 samples 의 실제 파일이고 서명 묶음이 그 내용을 안다."""
    import hashlib
    samples = SAMPLES
    files = COURSE.view()['provided_documents']
    assert files == PBL.view()['provided_documents'] and len(files) == 4 and files[:3] == [f'{d}_' + f.split('_', 1)[1] for d, f in zip(('HM-8', 'PM-02', 'PR-07'), files)]
    assert all(cp.provided_document(hashlib.sha256((samples / f).read_bytes()).hexdigest()) for f in files)


def test_PBL_단계의_표는_막힌_것도_까닭도_없다():
    view = PBL.view()
    assert all(v['allowed'] and v['reason'] is None for v in view['actions'].values())
    assert [view[k] for k in ('assignable_definitions', 'startable_definitions', 'importable_flow', 'documents', 'reasons',
                              'handover_editable')] == [None] * 6


@pytest.mark.parametrize('policy', [COURSE, PBL], ids=['수업', 'PBL'])
def test_표는_두_단계_모두_수업_모델_질문_한도_대용량_한도_수업_AI_자리를_준다(policy):
    view = policy.view()
    assert (view['model'], view['question_max_chars'], view['text_max']) == (course_ledger.POLICY['model'], LIMIT, cp.TEXT_MAX)
    assert {s['slot'] for s in view['ai_slots']} == set(cp.AI_SLOTS.values())
    assert {s['slot'] for s in view['ai_slots'] if not s['recorded']} == cp.UNRECORDED_SLOTS


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
    ('PUT', '/api/mcp/secrets/k', {'value': 'x'}, False, True),
    ('POST', '/api/mcp/servers/neo4j/check', {}, True, True),            # 준비된 서버 연결 검사는 수업에서도 된다
    ('POST', '/api/mcp/servers/neo4j/tools/read_neo4j_cypher/call', {}, True, True),
    ('POST', '/api/kg/manuals/batches/b1/golden-questions', {}, False, True),
    ('POST', '/api/kg/ddl/meanings', {}, False, True),
    ('POST', '/api/kg/ddl/preview', {}, True, True),                     # 구조 읽기(AI 없음)는 수업에서도
    ('POST', '/api/kg/ddl/commit', {}, True, True),                      # 업무 데이터 연결 적재(실라버스 4회차)
    ('DELETE', '/api/kg/ingests/ddl-1', {}, True, True),                 # 그 배치 되돌리기
    ('POST', '/api/fabric/query', {}, True, True),                       # 데이터 연결 질의 직접 실행
    ('POST', '/api/config/import', {}, False, True),
    ('POST', '/api/config/reset', {}, True, True),
    ('POST', '/api/agent-trials/run', {}, True, True),                   # 시험 비교 · 판단 채점은 AI 0 — 연다
    ('POST', '/api/eval/runs', {}, True, True),
    ('POST', '/api/roles', {}, True, True),
    ('POST', '/api/role-members', {}, True, True),
    ('DELETE', '/api/role-members', {}, True, True),
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
    ('POST', '/api/instances/start', {'definition_id': 'anomaly_response', 'version': definition_version('anomaly_response_v22.json')}, False, True),
    ('POST', '/api/instances/start', {'alert': {'alertId': 'a', 'asset': 'HYD-01'}}, True, True),
    ('PUT', '/api/agent-assignments', {'definition_id': 'ShiftHandover', 'activity_id': 'task_draft'}, True, True),
    ('PUT', '/api/agent-assignments', {'definition_id': 'c3_cooling', 'activity_id': 'T_agent'}, False, True),
    ('DELETE', '/api/agent-assignments/c3_cooling/T_agent', {}, False, True),
    ('POST', '/api/flows/import', {'xml': '<x/>', 'class_flow': True}, False, False),   # 수업 흐름 표시는 서버 안 설치만
    ('POST', '/api/process/definitions/c3_cooling/deploy', {'version': '1', 'class_flow': True}, False, False),
    ('POST', '/api/flows/c3_cooling/check', {'mapping': {}, 'class_flow': True}, False, False),   # 수업 흐름 설치의 검사 표시도 서버 안만
]


@pytest.mark.parametrize('phase', ['course', 'pbl'], ids=['수업', 'PBL'])
@pytest.mark.parametrize('method, path, body, course_ok, pbl_ok', GATE_CASES, ids=[f'{m} {p}' for m, p, *_ in GATE_CASES])
def test_문지기는_단계마다_행동별로_통과시키거나_까닭과_함께_거절한다(phase, method, path, body, course_ok, pbl_ok):
    response = gate_app(cp.Phase(phase)).request(method, path, json=body)
    if (course_ok if phase == 'course' else pbl_ok):
        assert response.status_code == 200, response.text
    else:
        assert response.status_code == 403 and response.json()['detail'], response.text


@pytest.mark.parametrize('method, path, body, reason', [
    ('PUT', '/api/flows/my_cooling/mapping', {'mapping': {}}, 'edit_flow'),
    ('POST', '/api/process/definitions/my_cooling/deploy', {'version': '1'}, 'deploy_flow'),
    ('POST', '/api/process/definitions/my_cooling/rollback', {}, 'deploy_flow'),
    ('POST', '/api/process/definitions', {'definition': {'processDefinitionId': 'my_cooling'}}, 'define_flow'),
])
def test_수업_단계의_흐름_편집_거절은_그_행동에_맞는_까닭을_말한다(method, path, body, reason):
    response = gate_app(cp.Phase('course')).request(method, path, json=body)
    assert (response.status_code, response.json()['detail']) == (403, cp.Policy.REASONS[reason])


def test_학생은_process_요청으로_단계를_바꿀_수_없다():
    """실제 process 앱(procsvc.main.app): 단계를 쓰는 길이 없다 — 쓰기 방법은 405, 단계는 그대로."""
    from procsvc import main
    client = TestClient(main.app)
    before = client.get('/api/course-access').json()['phase']
    statuses = {client.request(method, '/api/course-access', json={'phase': 'pbl'}).status_code for method in ('POST', 'PUT', 'DELETE')}
    assert statuses == {405}
    assert client.get('/api/course-access').json()['phase'] == before


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
    (None, 401),                       # 인증 없음
    ('Bearer ' + 'x' * 48, 401),       # 다른 키
], ids=['인증 없음', '다른 키'])
def test_워커용_판정은_실행기_인증이_틀리면_실행_서비스를_보기_전에_401이다(runtime_key, authorization, status):
    """FGB: 인증 거절이 수업 경계와 같은 403 이라 워커가 「수업 권한 확인 필요」로 보였다 — 인증은 401(연결 확인), 수업 경계 · 장부는 403."""
    headers = {'authorization': authorization} if authorization else {}
    response = gate_app(cp.Phase('course')).post('/internal/worker/course-decision', json={'tenant_id': 'hyd', 'todo_id': 'w1', 'consumer': 'c'},
                                                 headers=headers)
    assert response.status_code == status and response.json()['detail'] == '실행기 인증을 확인할 수 없습니다'


def test_워커용_판정은_처리_엔진이_없으면_503_까닭을_준다(runtime_key):
    response = gate_app(cp.Phase('course')).post('/internal/worker/course-decision', json={'tenant_id': 'hyd', 'todo_id': 'w1', 'consumer': 'c'},
                                                 headers={'authorization': 'Bearer ' + 'k' * 48})
    assert response.status_code == 503 and '실행 서비스' in response.json()['detail']


@pytest.mark.parametrize('body', ['[1, 2]', 'not json', '"text"'])
def test_워커용_판정은_객체가_아닌_본문을_422로_거절한다(runtime_key, body):
    response = gate_app(cp.Phase('course')).post('/internal/worker/course-decision', content=body,
                                                  headers={'authorization': 'Bearer ' + 'k' * 48, 'content-type': 'application/json'})
    assert response.status_code == 422 and '형식' in response.json()['detail']


# ---------------------------------------------------------------- 수업 흐름 보고 틀(학생이 처리 기록 · 결과 보고에서 읽는 글)
INTERNAL_WORDS = ('재관측', '작업지시', '오더', 'ACK', 'WO_', 'HITL')       # 화면에서 쓰지 않는 말(UIUX_PLAN §4 · 화면 말: 효과 확인 · 정비 요청)


@pytest.mark.parametrize('definition', sorted(cp.COURSE_FLOWS))
def test_수업_흐름의_보고_틀은_화면_말로_쓴다(definition):
    """W1-13: 「재관측 기준 미달」 · 「작업지시 {work_order.ref}」가 결과 보고 카드 · 처리 기록에 그대로 보였다."""
    texts = [str(v) for task in cp.COURSE_FLOWS[definition][2]['tasks'].values() if isinstance(task, dict)
             for key, v in (task.get('config') or {}).items() if key in ('title', 'summary', 'outcome', 'subject', 'body')]
    assert texts and not [t for t in texts if any(w in t for w in INTERNAL_WORDS)]


@pytest.mark.parametrize('path, size, status', [
    ('/api/process/definitions', cp.BODY_MAX['/api/process/definitions'], 200),
    ('/api/process/definitions', cp.BODY_MAX['/api/process/definitions'] + 1, 413),
    ('/api/instances/start', cp.BODY_MAX['/api/instances/start'] + 1, 413),
], ids=['정의 한도 그대로', '정의 한도 넘음', '시작 한도 넘음'])
@pytest.mark.parametrize('phase', ['course', 'pbl'], ids=['수업', 'PBL'])
def test_정의_등록과_시작은_본문을_다_읽기_전에_크기로_막는다(phase, path, size, status):
    """P1-16: 정의 · 시작 본문을 크기 확인 없이 다 읽었다(대용량은 두 단계 공통의 악용 지점)."""
    body = '{"definition_id": "c3_cooling", "pad": "' + 'x' * (size - 45) + '"}'
    body = body + ' ' * (size - len(body.encode()))
    assert len(body.encode()) == size
    response = gate_app(cp.Phase(phase)).post(path, content=body, headers={'content-type': 'application/json'})
    if status == 200:
        assert response.status_code != 413, response.text
    else:
        assert response.status_code == 413 and 'MB' in response.json()['detail']


@pytest.mark.parametrize('kind', ['purchase', 'other'])
def test_흐름_A의_실행하지_않는_조치_종류_보고는_코드_값을_학생_화면에_싣지_않는다(kind):
    """마지막고침 검증 H3: 「알 수 없음」 갈래(R_kind) 보고 글이 chosen_skill_kind 값을 그대로 넣어 (other) · (purchase)가 학생 화면에 보였다.
    실제 보고 렌더러에 승인 결과 값을 넣고 나온 글을 본다."""
    from procsvc.effect_parts import render_report
    from procsvc.instances import ACTION_KINDS
    task = cp.COURSE_FLOWS['c3_cooling'][2]['tasks']['R_kind']
    out = render_report(task['config']['summary'], {'chosen_skill_kind': kind, 'chosen_skill': 'skill:x'})
    assert out and not any(k in out for k in ACTION_KINDS), out


@pytest.mark.parametrize('action', sorted(cp.Policy.REASONS))
def test_수업_단계의_막힌_까닭은_학생이_읽는_말로_쓴다(action):
    """한바퀴 화면 순회: 흐름 화면의 막힌 까닭에 「흐름 id」가 그대로 보였다 — 서버가 내는 까닭 문장 전부를 학생 화면 말로 본다."""
    text = cp.Policy.REASONS[action]
    assert not any(w in text for w in ('흐름 id', ' id ', 'id)')), text
