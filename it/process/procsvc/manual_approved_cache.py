"""Instructor-reviewed, signed source proposals; no live-model fallback.

This caches ingestion only. Classroom agents continue to read current state and
run the model. The normal process engine still validates and consumes the saved
proposal, and a person still reviews it before graph commit.
"""
from copy import deepcopy
import hashlib
import json
import re
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from . import course_policy as rules
from . import manual_cache, manual_extraction as extraction


DOMAIN = b'hyd-approved-extractions-v1\x00'
BUNDLE = rules.HERE / 'course_extractions.json'


def _version(value):
    """'2.18' → (2, 18). 꼴이 다르면 None."""
    return tuple(map(int, value.split('.'))) if isinstance(value, str) and re.fullmatch(r'\d+\.\d+', value) else None


class ApprovedExtractions:
    def __init__(self, path=BUNDLE, *, public_key=rules.PUBLIC_KEY):
        envelope = json.loads(Path(path).read_text(encoding='utf8'))
        payload = envelope['payload']
        try:
            Ed25519PublicKey.from_public_bytes(rules.decode64(public_key)).verify(
                rules.decode64(envelope['signature']), DOMAIN + rules.canonical(payload))
        except Exception:
            raise ValueError('제공 문서 추출 묶음의 서명을 확인할 수 없습니다') from None
        # 묶음은 사람이 검토를 마친 고정 결과라, 맞춰야 할 것은 그 결과를 만든 지시문의 판이 아니라 결과의 꼴(제안 계약 extraction.CONTRACT)이다 — 지시문은 판을
        # 올려도(새 항목 제안 등) 제안의 꼴은 판과 무관한 같은 계약이고(validate_proposal), 묶음의 제안은 쓸 때마다 지금 계약 · 지금 카탈로그로 다시 검사된다:
        # 포털의 제공 문서 추출은 start → extraction.start(validate_proposal · content_issues), 시작의 적재(scripts/class_knowledge)는 /commit →
        # manual_review.validate · manual_knowledge.check_graph. 그래서 여기서는 그 판이 지금 지시문의 판보다 새 판이 아닌지만 본다(앞으로 나올 계약의 묶음은 읽지 못한다).
        made = _version(payload.get('extraction_version'))
        if payload.get('contract') != 'hyd-approved-extractions-v1' or made is None or made > _version(extraction.VERSION):
            raise ValueError(f"제공 문서 추출 묶음의 계약·판본이 다릅니다 — 묶음 {payload.get('contract')!r} · 추출 판 {payload.get('extraction_version')!r}, "
                             f"이 판이 읽는 것: hyd-approved-extractions-v1 · 추출 판 {extraction.VERSION} 이하")
        self.payload = payload
        self.digest = hashlib.sha256(rules.canonical(payload)).hexdigest()

    def covers(self, source):
        """이 문서(원문 sha256)가 강사가 검토 · 서명한 추출본을 가졌는가 — 가졌으면 AI 없이 이 묶음에서 낸다."""
        return source['sha256'] in self.payload['documents']

    def authorize(self, source):
        entry = self.payload['documents'].get(source['sha256'])
        if entry is None:
            raise ValueError('제공된 문서만 추출할 수 있습니다')
        if manual_cache.source_fingerprint(source) != entry['source_fingerprint']:
            raise ValueError('제공 문서와 내용은 같지만 파일 형식(확장자)이나 글 읽는 방식이 달라 검토를 마친 추출본을 쓸 수 없습니다 — 포털에서 받은 제공 문서 파일 이름(확장자) 그대로 올리세요')
        return entry

    def context(self, source):
        self.authorize(source)
        # 범위 끝의 notes-in-origin: 제안에서 작업 메모를 걷어 낸 판(start). 걷기 전에 이 PC에 만들어진 캐시 처리 건(메모가 제안에 남은 것)을 다시 쓰지 않게 열쇠를 가른다
        return dict(scope='provided-manuals/' + self.digest + '/notes-in-origin',
                    profile=dict(model='reviewed-source-cache', revision=self.payload['revision']))

    def start(self, rt, source, request_id, catalog):
        entry = self.authorize(source)
        def rebind(value):
            if isinstance(value, dict):
                return {k: source['source_id'] if k == 'source_id' else rebind(v) for k, v in value.items()}
            if isinstance(value, list):return [rebind(v) for v in value]
            return deepcopy(value)
        proposal = rebind(entry['proposal'])
        # 묶음 제안의 warnings 는 그 추출본을 검토한 사람이 남긴 작업 메모다(「이 리허설 추출에는 …」 · 「AI가 고장 유형 연결을 비움」 — 이미 고친 것을 적은 글).
        # 학생이 받는 추출 결과에는 싣지 않는다 — 처리 건 화면이 제안의 경고로 보여 「AI가 연결을 비웠다」를 사실로 믿게 했다(C9). 메모는 출처 기록(origin)에만 남긴다
        notes = list(entry['origin'].get('review_notes') or []) + list(proposal.get('warnings') or [])
        proposal['warnings'] = []
        context = self.context(source)
        key = manual_cache.identity(rt.tenant_id, source, catalog, **context)
        # extraction_version: 이 검토본을 만든 추출 지시문의 판(이 처리 건의 정의 판과 다를 수 있다 — 위 __init__)
        origin = dict(bundle=self.digest, revision=self.payload['revision'], extraction_version=self.payload['extraction_version'],
                      **dict(entry['origin'], review_notes=notes))
        inst = extraction.start(rt, source, request_id, catalog=catalog, cache_identity=key,
                                _approved_proposal=proposal, _cache_origin=origin)
        _, state = extraction._task_state(rt, inst)
        return dict(instance=inst['proc_inst_id'], status=state['status'], source_id=source['source_id'], segments=1,
                    cache=dict(key=key, reused=inst['cache_reused'], validated=False, origin=origin))
