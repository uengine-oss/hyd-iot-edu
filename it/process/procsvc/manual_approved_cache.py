"""Instructor-reviewed, signed source proposals; no live-model fallback.

This caches ingestion only. Classroom agents continue to read current state and
run the model. The normal process engine still validates and consumes the saved
proposal, and a person still reviews it before graph commit.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from hydcommon import course_access as rules
from . import manual_cache, manual_extraction as extraction


DOMAIN = b'hyd-approved-extractions-v1\x00'
BUNDLE = Path(rules.__file__).with_name('course_extractions.json')


class ApprovedExtractions:
    def __init__(self, path=BUNDLE, *, public_key=rules.PUBLIC_KEY):
        envelope = json.loads(Path(path).read_text(encoding='utf8'))
        payload = envelope['payload']
        try:
            Ed25519PublicKey.from_public_bytes(rules.decode64(public_key)).verify(
                rules.decode64(envelope['signature']), DOMAIN + rules.canonical(payload))
        except Exception:
            raise ValueError('제공 문서 추출 묶음의 강사 서명을 확인할 수 없습니다') from None
        if payload.get('contract') != 'hyd-approved-extractions-v1' or payload.get('extraction_version') != extraction.VERSION:
            raise ValueError('제공 문서 추출 묶음의 계약·판본이 다릅니다')
        self.payload = payload
        self.digest = hashlib.sha256(rules.canonical(payload)).hexdigest()

    def authorize(self, source):
        entry = self.payload['documents'].get(source['sha256'])
        if entry is None or not rules.approved_document(source['sha256']):
            raise ValueError('강사가 제공한 수업 문서만 추출할 수 있습니다')
        if manual_cache.source_fingerprint(source) != entry['source_fingerprint']:
            raise ValueError('제공 문서의 원문·파서 판본이 다릅니다. 강사에게 확인하세요')
        return entry

    def context(self, source):
        self.authorize(source)
        return dict(scope='provided-manuals/' + self.digest,
                    profile=dict(model='reviewed-source-cache', revision=self.payload['revision']))

    def start(self, rt, source, request_id, catalog, feedback=None):
        entry = self.authorize(source)
        feedback = extraction.validate_review_feedback(feedback)
        if feedback and feedback['items']:
            raise ValueError('수정 의견은 현재 제안의 검토 화면에서 반영하세요. 새 추출은 강사 준비에서 수행합니다')
        def rebind(value):
            if isinstance(value, dict):
                return {k: source['source_id'] if k == 'source_id' else rebind(v) for k, v in value.items()}
            if isinstance(value, list):return [rebind(v) for v in value]
            return deepcopy(value)
        proposal = rebind(entry['proposal'])
        context = self.context(source)
        key = manual_cache.identity(rt.tenant_id, source, catalog, **context)
        origin = dict(bundle=self.digest, revision=self.payload['revision'], **entry['origin'])
        inst = extraction.start(rt, source, request_id, catalog=catalog, cache_identity=key,
                                _approved_proposal=proposal, _cache_origin=origin)
        _, state = extraction._task_state(rt, inst)
        return dict(instance=inst['proc_inst_id'], status=state['status'], source_id=source['source_id'], segments=1,
                    cache=dict(key=key, reused=inst['cache_reused'], validated=False, origin=origin))
