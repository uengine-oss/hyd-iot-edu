"""Offline classroom release: only an instructor-signed code opens handover.

The verification key is public. The signing key never belongs in an image,
environment variable, browser asset, or Git. Local administrator/code tampering
is outside this application boundary; HTTP/configuration cannot mint a grant.
"""
import base64
import hashlib
import json
from pathlib import Path

PUBLIC_KEY = 'uiQXhElZ7HnRyuc_48KCdGsKa4k_oWppx0FKiK-dun0='
AUDIENCE = 'hyd-iot-edu-course-v1'
FIXED_RUNS = {'c3_cooling': {'T_agent'}, 'c3_pm': {'T_agent'}, 'c3_spare': {'T_agent'}}
HANDOVER_RUNS = {'ShiftHandover': {'task_draft', 'task_draft_r2', 'task_draft_r3'}, 'shift_handover': {'task:draft'}}
CONTENT = json.loads(Path(__file__).with_name('course_content.json').read_text(encoding='utf8'))
LOCKED_MESSAGE = '이 기능은 수업 잠금 상태입니다. 마지막 날 강사 해제 코드를 입력하세요.'


class AccessDenied(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf8')


def decode64(value):
    return base64.b64decode(value + '=' * (-len(value) % 4), altchars=b'-_', validate=True)


def verify(code, *, public_key=PUBLIC_KEY):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    try:
        if not isinstance(code, str) or not 32 < len(code) <= 512:
            raise ValueError()
        prefix, encoded, signature = code.strip().split('.')
        if prefix != 'HYD1':raise ValueError()
        raw = decode64(encoded)
        expected = {'aud': AUDIENCE, 'phase': 'handover', 'version': 1}
        if raw != canonical(expected):raise ValueError()
        Ed25519PublicKey.from_public_bytes(decode64(public_key)).verify(decode64(signature), raw)
        return expected
    except Exception:
        raise AccessDenied('강사 해제 코드가 올바르지 않습니다.') from None


def phase(grant):
    if not grant:return 'guided'
    verify(grant)
    return 'handover'


def approved_document(sha256):
    return isinstance(sha256, str) and sha256 in CONTENT['document_hashes']


def normalized_review(value):
    if isinstance(value, dict):
        return {k: '<source>' if k == 'source_id' else normalized_review(v) for k, v in value.items()}
    if isinstance(value, list):return [normalized_review(v) for v in value]
    return value


def bootstrap_review(body):
    """Only the exact shipped reviews may seed an initially empty classroom PC."""
    allowed = {'source_id','document_id','filename','batch','previous_batch','sections','procedures',
               'links','knowledge','by','review_method','reviewed'}
    if not isinstance(body, dict) or set(body)-allowed or body.get('reviewed') is not True:return False
    sha = str(body.get('source_id', '')).rsplit(':', 1)[-1]
    expected = CONTENT['bootstrap_reviews'].get(sha)
    review = {k: body.get(k) for k in ('sections','procedures','links','knowledge')}
    return bool(expected and hashlib.sha256(canonical(normalized_review(review))).hexdigest() == expected)


def authorize_task(grant, definition, activity_id, inputs):
    current = phase(grant)
    definition = definition or {}
    did = definition.get('processDefinitionId')
    approval = definition.get('classroom_agent')
    if approval:
        did, activity_id = approval.get('definition'), approval.get('activity')
    if activity_id in FIXED_RUNS.get(did, set()):return
    if current == 'handover' and activity_id in HANDOVER_RUNS.get(did, set()):return
    if current == 'handover' and did == 'manual_source_extraction':
        source = (inputs or {}).get('manual_source') or {}
        if approved_document(source.get('sha256')):return
    raise AccessDenied(LOCKED_MESSAGE if current == 'guided' else '수업에서 허용한 에이전트·제공 문서만 실행할 수 있습니다.')
