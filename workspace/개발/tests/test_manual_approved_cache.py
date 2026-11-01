"""강사 서명 제공 문서 묶음(procsvc/manual_approved_cache.py) — 서명 · 계약 · 판본이 맞아야 쓰고, 제공 문서(원문 sha256)만 AI 없이 이 묶음에서 낸다.
실제 묶음(course_extractions.json)과 그것을 바꾼 사본(임시 파일), 실제 보관소에 올린 제공 문서로 판정한다. 처리 건까지 가는 길은 test_manual_api."""
import json

import pytest

import class_knowledge
from procsvc import course_policy, manual_extraction
from procsvc.manual_approved_cache import BUNDLE, ApprovedExtractions
from procsvc.manual_sources import ManualSources

DOCS = {i['doc']: i for i in class_knowledge.reviewed()}


@pytest.fixture
def archive(tmp_path):
    return ManualSources(tmp_path / 'm.sqlite3')


def test_저장소의_묶음은_강사_공개_키로_서명이_확인되고_지금_추출_판본과_같다():
    cache = ApprovedExtractions()
    assert cache.payload['extraction_version'] == manual_extraction.VERSION and len(cache.digest) == 64
    assert set(cache.payload['documents']) == course_policy.DOCUMENTS


def _copy(tmp_path, change):
    envelope = json.loads(BUNDLE.read_text(encoding='utf8'))
    change(envelope)
    path = tmp_path / 'bundle.json'
    path.write_text(json.dumps(envelope, ensure_ascii=False), encoding='utf8')
    return path


def _edit_rule(e):
    doc = next(iter(e['payload']['documents'].values()))
    doc['proposal']['sections'][0]['title'] += ' (고침)'


@pytest.mark.parametrize('change, says', [
    (_edit_rule, '서명'),
    (lambda e: e.update(signature=e['signature'][:-4] + 'AAAA'), '서명'),
], ids=['서명 뒤 내용 고침', '서명 글자 바꿈'])
def test_서명이_맞지_않는_묶음은_쓰지_않는다(tmp_path, change, says):
    with pytest.raises(ValueError, match=says):
        ApprovedExtractions(_copy(tmp_path, change))


def test_다른_키로_서명한_묶음은_쓰지_않는다(tmp_path):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    import base64
    other = Ed25519PrivateKey.generate().public_key().public_bytes_raw()
    with pytest.raises(ValueError, match='서명'):
        ApprovedExtractions(BUNDLE, public_key=base64.urlsafe_b64encode(other).decode())


@pytest.mark.parametrize('doc', sorted(DOCS))
def test_제공_문서는_묶음이_덮고_원문_지문이_맞으면_그_검토본을_준다(archive, doc):
    source = archive.save('hyd', DOCS[doc]['filename'], DOCS[doc]['raw'])
    cache = ApprovedExtractions()
    assert cache.covers(source) and cache.authorize(source)['filename'] == DOCS[doc]['filename']
    assert cache.context(source)['scope'] == 'provided-manuals/' + cache.digest


def test_제공_문서가_아닌_원문은_덮지_않는다(archive):
    source = archive.save('hyd', 'mine.md', '# 우리 매뉴얼\n1. 멈춘다.\n'.encode())
    cache = ApprovedExtractions()
    assert not cache.covers(source)
    with pytest.raises(ValueError, match='강사가 제공한 수업 문서'):
        cache.authorize(source)


def test_확장자를_바꿔_올린_제공_문서는_무엇을_하면_되는지_말하며_거절한다(archive):
    """P2-19: 「강사에게 확인하세요」만 말했다 — 학생이 할 일은 받은 파일 이름 그대로 올리는 것이다."""
    item = DOCS['HM-8']
    source = archive.save('hyd', item['filename'].replace('.md', '.txt'), item['raw'])
    with pytest.raises(ValueError, match=r'파일 이름\(확장자\) 그대로'):
        ApprovedExtractions().authorize(source)
