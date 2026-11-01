"""문서 검토(procsvc/manual_review.py) — 줄 구조 읽기(번호 붙은 매뉴얼의 편의 파서)와 적재 전 전체 검증(인용 · 절 · 단계 · 연결 · 지식).
원문은 실제 보관소(ManualSources, 임시 파일)에 제공 문서를 올려 만들고, 검토본은 강사 서명 묶음(course_extractions.json)을 시작과 같은
길(scripts/class_knowledge.commit_body)로 바꾼 것이다 — 시작 지식이 이 검증을 지나는지가 판정 대상이다."""
from copy import deepcopy
from uuid import uuid4

import pytest

import class_knowledge
from procsvc import manual_review
from procsvc.manual_sources import ManualSources

DOCS = {item['doc']: item for item in class_knowledge.reviewed()}


@pytest.fixture
def archive(tmp_path):
    return ManualSources(tmp_path / 'manuals.sqlite3')


def body(archive, doc):
    item = DOCS[doc]
    source = archive.save('hyd', item['filename'], item['raw'])
    preview = {'source_id': source['source_id'], 'document_id': source['document_id'], 'filename': item['filename'],
               'batch': str(uuid4()), 'previous_batch': None}
    return class_knowledge.commit_body(item, preview)


@pytest.mark.parametrize('doc', sorted(DOCS))
def test_시작이_넣는_강사_검토본은_원문_인용과_함께_적재_검증을_지난다(archive, doc):
    plan = manual_review.validate(archive, 'hyd', body(archive, doc))
    item = DOCS[doc]
    assert len(plan['procedures']) == len(item['proposal']['procedures']) and plan['by'] == item['by']
    assert plan['document'] == manual_review.document_key('hyd', plan['document_id'])
    assert all(step['anchor']['source_id'] == plan['source_id'] for p in plan['procedures'] for step in p['steps'])


def test_냉각_검토본의_예측_유온_경고_규칙이_적재_계획에_들어간다(archive):
    """G3a-1 · P2-02: 지운 시작 사본에는 이 경고 규칙이 없었다 — 이제 시작도 서명 묶음 하나에서 읽는다."""
    plan = manual_review.validate(archive, 'hyd', body(archive, 'HM-8'))
    assert 'rule:cooler-forecast-temperature-warning' in {r['id'] for r in plan['knowledge']['rules']}


def _wrong_quote(b):
    b['procedures'][0]['steps'][0]['anchor'] = dict(b['procedures'][0]['steps'][0]['anchor'], quote='원문에 없는 글')


def _missing_section(b):
    b['procedures'][0]['section'] = 'NO-1'


@pytest.mark.parametrize('change, says', [
    (lambda b: b.update(reviewed=False), 'reviewed=true'),
    (lambda b: b.update(by='  '), '담당자'),
    (lambda b: b.update(review_method='guess'), '검토 수행 방식'),
    (lambda b: b.update(batch='not-a-uuid'), '배치 UUID'),
    (lambda b: b.update(procedures=[]), '하나 이상'),
    (_wrong_quote, '일치하지 않습니다'),
    (_missing_section, '실제 문서 절'),
    (lambda b: b['procedures'][0]['steps'][0].update(order=2), '연속'),
    (lambda b: b['procedures'][0].update(id='sop.cool'), 'SOP ID'),
    (lambda b: b['links'][b['procedures'][0]['id']].update(affects=[{'target': 'sv:TS1', 'sign': '+'}]), '소문자'),
], ids=['검토 안 함', '담당자 없음', '검토 방식 틀림', '배치 id 틀림', '절차 없음', '인용이 원문과 다름', '없는 절', '단계 순서', 'SOP 번호 꼴', '영향 대상 꼴'])
def test_검토본의_빈틈은_그래프에_쓰기_전에_까닭과_함께_거절한다(archive, change, says):
    b = body(archive, 'HM-8')
    change(b)
    with pytest.raises(ValueError, match=says):
        manual_review.validate(archive, 'hyd', b)


def test_다른_문서_판본의_인용은_섞지_않는다(archive):
    b = body(archive, 'HM-8')
    other = archive.save('hyd', DOCS['PM-02']['filename'], DOCS['PM-02']['raw'])
    b['sections'][0]['anchor'] = dict(b['sections'][0]['anchor'], source_id=other['source_id'])
    with pytest.raises(ValueError, match='다른 문서 판본'):
        manual_review.validate(archive, 'hyd', b)


def test_번호_붙은_매뉴얼은_줄_구조로_절과_SOP_단계를_읽는다(archive):
    raw = '# 매뉴얼\n## HM-9.1 펌프 점검\n펌프 점검의 기준.\n### SOP-PMP-11 씰 점검\n1. 펌프를 멈춘다.\n2. 씰을 본다.\n'.encode()
    source = archive.save('hyd', 'pump.md', raw)
    out = manual_review.proposal(source, failure_modes=[{'id': 'fm:pump-seal', 'name': '펌프 씰 누설'}])
    assert [s['ref'] for s in out['sections']] == ['HM-9.1'] and out['sections'][0]['excerpt'] == '펌프 점검의 기준.'
    [sop] = out['procedures']
    assert (sop['id'], [s['text'] for s in sop['steps']], sop['suggestedFailureMode']) == ('SOP-PMP-11', ['펌프를 멈춘다.', '씰을 본다.'], 'fm:pump-seal')
    assert sop['steps'][0]['anchor']['quote'] == '1. 펌프를 멈춘다.'


@pytest.mark.parametrize('text, warns', [
    ('1. 절 제목 없는 단계\n', '절 제목 없는 단계'),
    ('### SOP-A-1 절 없는 절차\n', '먼저 원문 절'),
    ('## A-1 절\n1. 하나\n3. 셋\n', '순서를 검토'),
    ('그냥 글입니다\n', '구조화된 SOP를 찾지 못했습니다'),
])
def test_줄_구조로_읽을_수_없는_곳은_자동으로_적재하지_않고_경고한다(archive, text, warns):
    source = archive.save('hyd', 'x.md', ('# 제목\n' + text).encode())
    assert any(warns in w for w in manual_review.proposal(source)['warnings'])


def test_문서_그래프_열쇠는_교육_공간마다_다르다():
    assert manual_review.document_key('hyd', 'd1') != manual_review.document_key('other', 'd1')
    assert manual_review.document_key('hyd', 'd1').endswith(':d1')


def test_같은_원문을_다시_올려도_검토본은_같은_계획이다(archive):
    first = manual_review.validate(archive, 'hyd', body(archive, 'PR-07'))
    second = manual_review.validate(archive, 'hyd', body(archive, 'PR-07'))
    strip = lambda p: {k: v for k, v in p.items() if k not in ('batch', 'source_id', 'document_id', 'document')}
    def rebase(value, sid):
        if isinstance(value, dict):
            return {k: ('S' if k == 'source_id' else rebase(v, sid)) for k, v in value.items()}
        return [rebase(v, sid) for v in value] if isinstance(value, list) else value
    assert rebase(strip(deepcopy(first)), first['source_id']) == rebase(strip(deepcopy(second)), second['source_id'])
