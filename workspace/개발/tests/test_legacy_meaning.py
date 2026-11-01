"""옛 DB 뜻 복원(procsvc/legacy_meaning.py) — 뜻(주석) 없는 열의 관찰(이름 조각 · 샘플 분포 · 키 관계), AI 후보 계약 검사(관찰에 없는 근거 ·
추측한 뜻 거절), 사람 결정(승인 · 고치기 · 거부), 반영(주석 · REPRESENTS · 설비 식별 열 — 사람이 승인한 것만).
표본은 포털이 내주는 제공 파일 samples/legacy-plant-db.sql(주석 · 외래 키 없는 옛 덤프)이다. AI 후보 요청 자체는 수업 단계에서 막히고
(PBL), 이 모듈의 판정은 두 단계 공통이다."""

import pytest

from conftest import SAMPLES

from procsvc import ingest, legacy_meaning as lm

LEGACY = (SAMPLES / 'legacy-plant-db.sql').read_text(encoding='utf-8')
ONTOLOGY = {'stateVariables': [{'id': 'sv:ts1', 'name': '작동유 온도', 'unit': '℃'}], 'measures': [],
            'assets': [{'tag': 'HYD-01'}, {'tag': 'HYD-02'}, {'tag': 'HYD-03'}]}


@pytest.fixture(scope='module')
def tables():
    return ingest.parse_ddl(LEGACY)


@pytest.fixture(scope='module')
def req(tables):
    return lm.request(filename='legacy-plant-db.sql', text=LEGACY, tables=tables, ontology=ONTOLOGY,
                      datasource='hyd-enterprise', catalog='postgres', by='수강생')


def column(req, key):
    return next(c for c in req['columns'] if c['key'] == key)


def test_뜻이_없는_열마다_이름_조각_샘플_분포_키_관계를_관찰한다(req):
    assert req['source']['sha256'] == lm.text_sha256(LEGACY) and len(req['columns']) == 23
    tmp = column(req, 'public.T_EQP01.C_TMP_O')
    assert tmp['name']['tokens'] == ['C', 'TMP', 'O'] and tmp['samples']['rows'] == 15 and 'mean' in tmp['samples']
    eqp = column(req, 'public.T_EQP01.EQP_CD')
    assert eqp['assetTags'] == {'matched': 3, 'of': 3} and eqp['keys']['sameName']




def test_미리보기_요약은_뜻_없는_열_수와_샘플_행_수를_준다(tables):
    summary = lm.summary(tables, LEGACY)
    assert summary['targets'] == 23 and summary['samples'] == {'public.T_EQP00': 4, 'public.T_EQP01': 15, 'public.T_MNT10': 5}


def test_INSERT가_깨져도_DDL_미리보기는_까닭을_적고_이어_간다(tables):
    broken = LEGACY + "\nINSERT INTO \"T_EQP00\" (\"EQP_CD\") VALUES ('a', 'b');\n"
    assert '값 개수' in lm.summary(tables, broken)['error']


def candidate(key, **over):
    return {'column': key, 'status': 'proposed', 'meaning': '작동유 온도', 'unit': '℃', 'link': {'kind': 'none', 'target': None},
            'evidence': [{'kind': 'name', 'text': 'TMP'}], 'confidence': 0.8, 'alternatives': [], **over}


def answers(req, **by_key):
    return {'items': [by_key.get(c['key']) or {'column': c['key'], 'status': 'no_evidence', 'meaning': None, 'confidence': 0.1,
                                                'evidence': [], 'reason': '근거 부족'} for c in req['columns']], 'summary': '한 줄'}


def test_관찰에_맞는_후보는_받고_연결_대상의_이름_단위를_붙인다(req):
    key = 'public.T_EQP01.C_TMP_O'
    out = lm.validate_candidates(req, answers(req, **{key: candidate(key, link={'kind': 'represents', 'target': 'sv:ts1'})}))
    got = next(i for i in out['items'] if i['column'] == key)
    assert got['link'] == {'kind': 'represents', 'target': 'sv:ts1', 'name': '작동유 온도', 'unit': '℃'}


@pytest.mark.parametrize('make, says', [
    (lambda req, k: {'items': []}, '열 수'),
    (lambda req, k: answers(req, **{k: candidate(k, evidence=[{'kind': 'comment', 'text': '주석'}])}), '관찰에 없는 근거'),
    (lambda req, k: answers(req, **{k: candidate(k, evidence=[])}), '근거가 하나 이상'),
    (lambda req, k: answers(req, **{k: candidate(k, status='no_evidence', reason='x')}), 'null'),
    (lambda req, k: answers(req, **{k: candidate(k, link={'kind': 'represents', 'target': 'sv:nope'})}), '목록에 없습니다'),
    (lambda req, k: answers(req, **{k: candidate(k, confidence=2)}), 'confidence'),
    (lambda req, k: answers(req, **{k: candidate(k, link={'kind': 'asset_key', 'target': None})}), '설비 식별 열이라는 근거'),
], ids=['개수 다름', '없는 주석 근거', '근거 없는 뜻', '근거 없음인데 뜻을 채움', '없는 연결 대상', '확신도 범위', '설비 태그와 안 겹치는 식별 열'])
def test_관찰에_없는_근거나_추측한_뜻은_교정_사유로_거절한다(req, make, says):
    with pytest.raises(ValueError, match=says):
        lm.validate_candidates(req, make(req, 'public.T_EQP01.C_TMP_O'))


def review(req, *decisions):
    key = 'public.T_EQP01.C_TMP_O'
    candidates = lm.validate_candidates(req, answers(req, **{key: candidate(key, link={'kind': 'represents', 'target': 'sv:ts1'})}))['items']
    return lm.validate_review(req, candidates, {'by': '수강생', 'decisions': list(decisions)})


def test_승인한_뜻만_주석_SQL과_입력_이름_REPRESENTS로_반영된다(req, tables):
    key = 'public.T_EQP01.C_TMP_O'
    r = review(req, {'column': key, 'verdict': 'APPROVE'}, {'column': 'public.T_EQP01.C_PRS_A', 'verdict': 'REJECT'})
    assert lm.counts(r) == {'approved': 1, 'edited': 0, 'rejected': 1}
    assert lm.comment_sql(r) == ['COMMENT ON COLUMN "public"."T_EQP01"."C_TMP_O" IS \'작동유 온도 (℃)\';']
    copies = ingest.parse_ddl(LEGACY)
    refl = lm.apply_comments(copies, r)
    plan = ingest.plan(copies, filename='legacy-plant-db.sql', batch='b', selection={'T_EQP01': ['C_TMP_O', 'C_PRS_A']})
    assert lm.apply_links(plan, refl, 'review:1') == [key]
    tmp, prs = (next(i for i in plan['inputs'] if i['column'] == c) for c in ('C_TMP_O', 'C_PRS_A'))
    assert (tmp['name'], tmp['represents'], tmp['meaningReview']) == ('작동유 온도 (℃)', 'sv:ts1', 'review:1')
    assert 'represents' not in prs and 'meaningReview' not in prs
    assert lm.expected_input(r, tmp) == {'represents': 'sv:ts1', 'name': '작동유 온도 (℃)', 'assetColumn': None}


def test_사람이_고친_뜻은_그_사람의_말로_반영된다(req):
    r = review(req, {'column': 'public.T_EQP01.C_TMP_O', 'verdict': 'EDIT', 'meaning': '오일 출구 온도', 'unit': '℃'})
    assert lm.reflection(r)['public.T_EQP01.C_TMP_O']['comment'] == '오일 출구 온도 (℃)'


@pytest.mark.parametrize('decisions, body, says', [
    ([], {'by': '수강생'}, '하나 이상'),
    ([{'column': 'public.T_EQP01.C_TMP_O', 'verdict': 'APPROVE'}], {'by': ''}, '검토자'),
    ([{'column': 'nope', 'verdict': 'APPROVE'}], {'by': '수강생'}, '후보에 없는'),
    ([{'column': 'public.T_EQP01.C_TMP_O', 'verdict': 'MAYBE'}], {'by': '수강생'}, '결정은'),
    ([{'column': 'public.T_EQP01.C_PRS_A', 'verdict': 'APPROVE'}], {'by': '수강생'}, '근거 없음 후보'),
    ([{'column': 'public.T_EQP01.C_TMP_O', 'verdict': 'APPROVE'}] * 2, {'by': '수강생'}, '두 번'),
], ids=['결정 없음', '검토자 없음', '없는 열', '없는 결정', '근거 없음을 승인', '같은 열 두 번'])
def test_사람_결정의_빈틈은_거절한다(req, decisions, body, says):
    key = 'public.T_EQP01.C_TMP_O'
    candidates = lm.validate_candidates(req, answers(req, **{key: candidate(key)}))['items']
    with pytest.raises(ValueError, match=says):
        lm.validate_review(req, candidates, dict(body, decisions=decisions))


def test_모든_열에_주석이_있으면_뜻_후보를_묻지_않는다():
    tables = ingest.parse_ddl("CREATE TABLE a (x int); COMMENT ON COLUMN a.x IS '수량';")
    with pytest.raises(ValueError, match='뜻을 복원할 열이 없습니다'):
        lm.request(filename='a.sql', text="CREATE TABLE a (x int);", tables=tables, ontology=ONTOLOGY, datasource='d', catalog='c', by='')


@pytest.mark.parametrize('name, tokens', [('C_PRS_A', ['C', 'PRS', 'A']), ('eqpCode2', ['EQP', 'CODE', '2']), ('MSR_DTM', ['MSR', 'DTM'])])
def test_열_이름은_밑줄_대소문자_숫자_경계로_조각낸다(name, tokens):
    assert lm.name_tokens(name) == tokens


def test_전부_비어_있는_열은_샘플_분포를_근거로_뜻을_낼_수_없다(req):
    key = 'public.T_EQP01.C_PRS_B'
    blank = column(req, key)
    assert blank['samples']['nulls'] == blank['samples']['rows']
    with pytest.raises(ValueError, match='샘플 값 분포 관찰이 없습니다'):
        lm.validate_candidates(req, answers(req, **{key: candidate(key, evidence=[{'kind': 'sample', 'text': '값 범위'}])}))
