"""강사 서명 제공 문서 묶음(procsvc/manual_approved_cache.py) — 서명 · 계약 · 판본이 맞아야 쓰고, 제공 문서(원문 sha256)만 AI 없이 이 묶음에서 낸다.
실제 묶음(course_extractions.json)과 그것을 바꾼 사본(임시 파일), 실제 보관소에 올린 제공 문서로 판정한다. 처리 건까지 가는 길은 이 파일의 world 시험과 test_class_knowledge 의 포털 길(portal_commit)."""
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


def test_저장소의_묶음은_강사_공개_키로_서명이_확인되고_지금_추출_판보다_새_판이_아니다():
    """묶음은 사람이 검토를 마친 고정 결과다 — 맞춰야 할 것은 지시문의 판이 아니라 결과의 꼴(제안 계약)이고(2026-11-22: 지시문을 2.19로 올려도 2.18 묶음을
    다시 서명하지 않는다), 묶음의 제안은 쓸 때마다 지금 계약으로 다시 검사된다(아래 시험)."""
    cache = ApprovedExtractions()
    assert len(cache.digest) == 64 and set(cache.payload['documents']) == course_policy.DOCUMENTS
    made, now = (tuple(map(int, v.split('.'))) for v in (cache.payload['extraction_version'], manual_extraction.VERSION))
    assert made <= now


def _signed_copy(tmp_path, change):
    """다른 키(시험용)로 서명한 묶음 사본 — 서명은 맞고 내용만 바꾼 묶음을 만든다."""
    import base64
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from procsvc.manual_approved_cache import DOMAIN
    key = Ed25519PrivateKey.generate()
    envelope = json.loads(BUNDLE.read_text(encoding='utf8'))
    change(envelope['payload'])
    envelope['signature'] = base64.urlsafe_b64encode(key.sign(DOMAIN + course_policy.canonical(envelope['payload']))).decode()
    path = tmp_path / 'bundle.json'
    path.write_text(json.dumps(envelope, ensure_ascii=False), encoding='utf8')
    return path, base64.urlsafe_b64encode(key.public_key().public_bytes_raw()).decode()


@pytest.mark.parametrize('version, ok', [('2.17', True), (manual_extraction.VERSION, True), ('99.0', False), ('판 2', False), (None, False)],
                         ids=['앞 판의 결과', '지금 판', '앞으로 나올 판', '꼴이 틀린 판', '판 없음'])
def test_묶음은_지금_추출_판보다_새_판이거나_판이_없으면_까닭과_함께_쓰지_않는다(tmp_path, version, ok):
    path, public = _signed_copy(tmp_path, lambda payload: payload.update(extraction_version=version))
    if ok:
        assert ApprovedExtractions(path, public_key=public).payload['extraction_version'] == version
    else:
        with pytest.raises(ValueError, match=f'이 판이 읽는 것: hyd-approved-extractions-v1 · 추출 판 {manual_extraction.VERSION} 이하'):
            ApprovedExtractions(path, public_key=public)


@pytest.mark.parametrize('doc', sorted(set(DOCS) | {'HI-01'}))
def test_서명_묶음의_검토본은_지금_추출_계약과_내용_검사를_그대로_지난다(archive, doc):
    """지시문 판을 올려도 수업 문서의 서명 묶음 결과가 지금 계약(인용 위치 찾기 · 꼴 · 내용 검사)을 그대로 지난다 — 포털의 제공 문서 추출이 쓰는 길과 같은 검사."""
    item = {i['doc']: i for i in class_knowledge.reviewed(order=class_knowledge.ORDER + ('HI-01',))}[doc]
    source = archive.save('hyd', item['filename'], item['raw'])
    checked = manual_extraction.validate_proposal(source, class_knowledge.rebased(item['proposal'], source['source_id']))
    inst = {'proc_def_version': manual_extraction.VERSION}
    assert manual_extraction.content_issues(checked, source, None, **manual_extraction.scopes(inst)) == []
    assert len(checked['procedures']) == len(item['proposal']['procedures'])


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
    assert cache.context(source)['scope'] == 'provided-manuals/' + cache.digest + '/notes-in-origin'


def test_제공_문서가_아닌_원문은_덮지_않는다(archive):
    source = archive.save('hyd', 'mine.md', '# 우리 매뉴얼\n1. 멈춘다.\n'.encode())
    cache = ApprovedExtractions()
    assert not cache.covers(source)
    with pytest.raises(ValueError, match='제공된 문서만'):
        cache.authorize(source)


def test_확장자를_바꿔_올린_제공_문서는_무엇을_하면_되는지_말하며_거절한다(archive):
    """P2-19: 「강사에게 확인하세요」만 말했다 — 학생이 할 일은 받은 파일 이름 그대로 올리는 것이다."""
    item = DOCS['HM-8']
    source = archive.save('hyd', item['filename'].replace('.md', '.txt'), item['raw'])
    with pytest.raises(ValueError, match=r'파일 이름\(확장자\) 그대로'):
        ApprovedExtractions().authorize(source)


def test_제공_문서의_추출_결과에는_그_추출본을_검토한_사람의_작업_메모가_실리지_않는다(world, course_graph):
    """C9(2026-11-22): 묶음 제안의 warnings 는 검토한 사람의 작업 메모다(「AI가 고장 유형 연결을 비움」 · 「이 리허설 추출에는 …」 — 이미 고친 것). 처리 건
    화면이 그것을 추출 제안의 경고로 보여, 학생은 채워진 연결을 「AI가 비웠다」고 읽었다. 실제 API 길(올리기 → 제공 문서 추출 → 결과)에서 학생이 받는
    제안에는 그 메모가 없고, 메모는 출처 기록(cache.origin.review_notes)에만 남는다."""
    import base64
    import uuid
    item = DOCS['HM-8']
    memo = list(item['proposal']['warnings'])
    assert memo, '묶음의 HM-8 제안에 작업 메모가 있어야 이 시험이 무엇을 재는지 뜻이 있다'
    status, preview = world.api('POST', '/api/kg/manuals/preview', {'filename': item['filename'], 'data': base64.b64encode(item['raw']).decode()})
    assert status == 200, preview
    sid = preview['source_id']
    status, started = world.api('POST', f'/api/kg/manuals/sources/{sid}/extractions', {'request_id': str(uuid.uuid4())})
    assert status == 200, started
    world.poll()
    status, result = world.api('GET', f"/api/kg/manuals/sources/{sid}/extractions/{started['instance']}")
    assert status == 200 and result['preview'], result
    assert not set(memo) & set(result['preview']['warnings']), result['preview']['warnings']
    assert set(memo) <= set(result['cache']['origin']['review_notes'])


def test_제공_문서의_이전_추출_결과는_지식이_바뀐_뒤에도_같은_원문의_실행을_모두_보인다(world, course_graph):
    """03-22(2026-11-22): 제공 문서의 추출은 캐시 처리 건이고 그 시작 id 의 열쇠에 그때의 지식 목록이 들어 있다. 「이 문서의 이전 추출 결과」 목록이 지금 지식으로
    만든 열쇠로만 찾아, 문서를 적재하거나 비워 지식이 바뀌면 앞 실행이 목록에서 빠졌다. 실제 API 길에서: 추출 → 지식이 바뀜(역할 하나가 생김) → 앞 실행이
    그대로 보이고, 다시 추출한 새 실행도 함께 보인다. 다른 제공 문서의 실행은 섞이지 않는다."""
    import base64
    import uuid

    def upload(doc):
        item = DOCS[doc]
        status, preview = world.api('POST', '/api/kg/manuals/preview', {'filename': item['filename'], 'data': base64.b64encode(item['raw']).decode()})
        assert status == 200, preview
        return preview['source_id']

    def extract(sid):
        status, started = world.api('POST', f'/api/kg/manuals/sources/{sid}/extractions', {'request_id': str(uuid.uuid4())})
        assert status == 200, started
        world.poll()
        return started['instance']

    def runs(sid):
        status, page = world.api('GET', f'/api/kg/manuals/sources/{sid}/extractions')
        assert status == 200, page
        return [r['proc_inst_id'] for r in page['items']]
    sid, other = upload('HM-8'), upload('PM-02')
    first, theirs = extract(sid), extract(other)
    seen = runs(sid)          # 같은 원문의 실행 전부(이 묶음의 앞 시험이 같은 원문으로 만든 것도 — 같은 지식이면 같은 처리 건을 다시 쓴다)
    assert first in seen and theirs not in seen
    course_graph.query("CREATE (:Role {id:'role:sb-history-check', name:'이력 확인 역할', level:1})")      # 지식이 바뀐다 — 추출 캐시의 열쇠가 갈린다
    assert sorted(runs(sid)) == sorted(seen)                                            # 전에는 지금 열쇠로만 찾아 앞 실행이 빠졌다
    second = extract(sid)
    after = runs(sid)                                                                    # 새 열쇠의 새 실행이 더해지고 앞 실행은 그대로(차례는 시작 시각 — 시험 세계의 시계라 견주지 않는다)
    assert second not in seen and sorted(after) == sorted([second, *seen]) and len(after) == len(set(after))
    status, result = world.api('GET', f'/api/kg/manuals/sources/{sid}/extractions/{first}')
    assert status == 200 and result['preview'], result                                  # 목록에 보인 앞 실행은 열린다
