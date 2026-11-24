"""문서 검토(procsvc/manual_review.py) — 적재 전 전체 검증(인용 · 절 · 단계 · 연결 · 지식).
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


def test_문서_등록_응답은_원문_요약만_싣고_절과_절차를_싣지_않는다(archive):
    """절 · 절차는 AI 추출 결과만 싣는다 — 번호 붙은 줄 모양을 읽어 추출 전에 결과처럼 보이던 길은 없다(2026-11-13 삭제)."""
    raw = '# 매뉴얼\n## HM-9.1 펌프 점검\n펌프 점검의 기준.\n### SOP-PMP-11 씰 점검\n1. 펌프를 멈춘다.\n2. 씰을 본다.\n'.encode()
    source = archive.save('hyd', 'pump.md', raw)
    out = manual_review.registered(source)
    assert (out['source_id'], out['document_id'], out['filename'], out['status']) == (source['source_id'], source['document_id'], 'pump.md', source['status'])
    assert out['chars'] == sum(len(p['text']) for p in source['pages']) and out['pages'] == len(source['pages'])
    assert out['warnings'] == source['warnings'] and out['previous_batch'] is None
    assert 'sections' not in out and 'procedures' not in out and 'validation' not in out
    assert out['batch'] != manual_review.registered(source)['batch']      # 등록 응답마다 새 배치 번호


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


def test_자동_검증만_거친_적재는_계획과_적재_기록에_그_사실이_남고_다른_값은_받지_않는다(archive):
    """C10(2026-11-22): 「한 번에 적재」는 사람이 검토 화면을 열지 않는데, 적재 기록은 「담당자가 검토함」(reviewed=true · by)으로만 남았다. 그 길은
    review_scope='automatic' 을 싣고, 계획과 적재 영수증(manual_graph._receipt)이 그것을 남긴다. 기본 제공 판 표시(review_method)와는 다른 칸이다."""
    from procsvc import manual_graph
    b = {k: v for k, v in body(archive, 'HM-8').items() if k not in ('review_method', 'provided_revision')}      # 포털의 검토본(기본 제공 판 표시 없음)
    assert 'review_scope' not in manual_review.validate(archive, 'hyd', b)
    plan = manual_review.validate(archive, 'hyd', dict(b, review_scope='automatic'))
    assert plan['review_scope'] == 'automatic' and 'review_method' not in plan
    assert manual_graph._receipt(dict(plan, candidate_rules={}), 'now')['review_scope'] == 'automatic'
    with pytest.raises(ValueError, match='검토 범위'):
        manual_review.validate(archive, 'hyd', dict(b, review_scope='skipped'))


def _apu_preview(archive):
    """다른 설비의 실제 규모 문서(apu_document)를 올려 추출 계약을 지난 제안 — 화면이 받는 추출 결과의 꼴(원문 id · 문서 id · 파일 이름)."""
    import apu_document as apu
    from procsvc import manual_extraction
    source = archive.save('hyd', apu.FILENAME, apu.RAW)
    checked = manual_extraction.validate_proposal(source, apu.proposal(source['source_id']))
    return dict(checked, document_id=source['document_id'], filename=source['filename'])


def test_새_항목은_넣기를_고른_검토본만_받고_자동_검증만_거친_적재에는_싣지_않는다(archive):
    """다른 설비 문서의 새 항목(구성 요소 · 증상 · 센서)은 사람이 항목마다 넣기를 고른 것만 계획에 들어간다. 「제외」를 고른 항목은 검토본에 없고,
    넣기 표시가 없는 새 항목은 거절된다. 검토 화면을 열지 않은 적재(한 번에 적재 — review_scope automatic)는 새 항목을 싣지 못한다."""
    import apu_document as apu
    preview = _apu_preview(archive)
    plan = manual_review.validate(archive, 'hyd', apu.reviewed(preview, drop={'sen:apu-caudal-impulses'}))
    assert len(plan['knowledge']['sensors']) == 14 and 'sen:apu-caudal-impulses' not in {s['id'] for s in plan['knowledge']['sensors']}
    assert {k: len(plan['knowledge'][k]) for k in ('components', 'symptoms')} == {'components': 9, 'symptoms': 7}
    unchosen = apu.reviewed(preview)
    del unchosen['knowledge']['symptoms'][0]['approved']
    with pytest.raises(ValueError, match='「넣기」를 골라야 적재됩니다'):
        manual_review.validate(archive, 'hyd', unchosen)
    automatic = dict(apu.reviewed(preview), review_scope='automatic')
    with pytest.raises(ValueError, match=r'자동 검증만 거친 적재에는 새 항목\(구성 요소 · 증상 · 센서\) 31개를 넣지 않습니다'):
        manual_review.validate(archive, 'hyd', automatic)
