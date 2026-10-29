"""Classroom boundary: course actions are always open, anything outside the course is refused.

There is no unlock step. Prepared flows (A/B/C cooling · maintenance · spare, shift handover), the provided
documents and the course agents can be used from the first lesson; the AI cost of those actions is served from
signed caches or replayed responses. What stays refused is outside the course: other documents, other
servers, other models. The public key below verifies the instructor-signed extraction bundle
(manual_approved_cache); the signing key never belongs in an image, environment variable, browser asset or Git.
"""
import base64
import json
from pathlib import Path

PUBLIC_KEY = 'uiQXhElZ7HnRyuc_48KCdGsKa4k_oWppx0FKiK-dun0='
# 수업에서 AI가 실행하는 단계: 준비된 흐름 A/B/C 의 판단 단계와 교대 인수인계의 초안 단계
COURSE_RUNS = {'c3_cooling': {'T_agent'}, 'c3_pm': {'T_agent'}, 'c3_spare': {'T_agent'},
               'ShiftHandover': {'task_draft', 'task_draft_r2', 'task_draft_r3'}, 'shift_handover': {'task:draft'}}
HANDOVER_DEFINITIONS = frozenset(('ShiftHandover', 'shift_handover'))
CONTENT = json.loads(Path(__file__).with_name('course_content.json').read_text(encoding='utf8'))
AGENT_SERVERS = frozenset(('neo4j', 'enterprise', 'hyd-dmn'))


def agent_configuration_error(model, tools):
    if model not in (None, '', 'coding'):
        return '수업 모델은 강사가 지정한 기본 모델을 사용합니다.'
    if tools and (not isinstance(tools, list) or any(not isinstance(t, str) or t not in AGENT_SERVERS for t in tools)):
        return '수업에서 준비한 조회 서버만 사용할 수 있습니다.'
    return None


class AccessDenied(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf8')


def decode64(value):
    return base64.b64decode(value + '=' * (-len(value) % 4), altchars=b'-_', validate=True)


def approved_document(sha256):
    return isinstance(sha256, str) and sha256 in CONTENT['document_hashes']


def authorize_task(definition, activity_id, inputs):
    definition = definition or {}
    did = definition.get('processDefinitionId')
    approval = definition.get('classroom_agent')
    if approval:
        did, activity_id = approval.get('definition'), approval.get('activity')
    if activity_id in COURSE_RUNS.get(did, set()):return
    if did == 'ask_agent' and activity_id == 'task:answer':
        question = (inputs or {}).get('question')
        if isinstance(question,str) and question.strip() and len(question)<=1000:return
    # Student ingestion is served from the signed source cache before enqueue.
    # A task reaching the live worker is a missing/bypassed cache, never a
    # reason to spend on another extraction. Teacher preparation has no local
    # course gate and uses its explicitly bounded managed execution instead.
    raise AccessDenied('수업에서 허용한 에이전트·제공 문서만 실행할 수 있습니다.')
