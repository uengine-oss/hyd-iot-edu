"""적재 전 기계 검사(procsvc/manual_preflight.py) — 검토 화면이 보이는 검사(무엇이 지금 지식에 없는지 · 판단이 이 절차를 후보로 낼 길이 있는지 ·
정기 정비 · 구매 실행에 필요한 원문 정책). 사람 검토도 적재 허락도 아니다. 실제 그래프(kg-seed 가 끝난 그래프)의 카탈로그와 강사 서명 묶음의
검토본으로 판정한다. 검사 문장은 학생에게 보이므로 화면 말이다(P2-19)."""
import re
from copy import deepcopy

import pytest

import class_knowledge
from procsvc import manual_knowledge, manual_preflight

DOCS = {i['doc']: i for i in class_knowledge.reviewed()}


@pytest.fixture
def catalog(seeded_graph, pg_dsn):
    """kg-seed 뒤 업무 DB 의 공급사 · 견적을 그래프로 옮긴 카탈로그(시작이 지식 적재 전에 하는 것과 같다)."""
    import psycopg
    from hydcommon import graphdb
    from procsvc import scm_sync
    scm_sync.sync(lambda cypher, **params: seeded_graph.query(cypher, **params), lambda: psycopg.connect(pg_dsn))
    with graphdb.connect() as driver, driver.session() as session:
        return manual_knowledge.catalog(session)


def proposal(doc):
    return deepcopy(DOCS[doc]['proposal'])


def codes(result):
    return {i['code'] for i in result['issues']}


def test_냉각_검토본의_남은_빈틈은_벨트_교체를_후보로_낼_규칙이_없는_것_하나다(catalog):
    """강사 서명 묶음의 HM-8 은 SOP-FAN-12(벨트 교체)를 결과로 둔 후보 규칙이 없고, 그 고장 유형(fm:cooler-cooling-loss)으로 합류할 시드 후보
    규칙도 없다 — 판단이 벨트 교체를 후보로 내지 못한다. 묶음은 강사 재검토 · 재서명 대상이다(FB_고침.md 「사용자만 정할 수 있는 것」).
    그 밖의 기술 검사는 지난다. 검사는 알릴 뿐 적재를 막지 않는다."""
    result = manual_preflight.validate(proposal('HM-8'), catalog)
    assert [(i['code'], i['sop']) for i in result['issues']] == [('CANDIDATE_RULE_MISSING', 'SOP-FAN-12')], result['issues']
    assert (result['needs_human_review'], result['can_commit']) == (True, False)


def test_지금_지식에_없는_고장_유형을_가리키면_칸_이름과_함께_알린다(catalog):
    p = proposal('HM-8')
    p['procedures'][0]['link']['failureMode'] = 'fm:no-such-mode'
    result = manual_preflight.validate(p, catalog)
    found = [i for i in result['issues'] if i['code'] == 'REFERENCE_NOT_FOUND']
    assert found and '고장 유형 칸에 적은 fm:no-such-mode' in found[0]['message'] and not re.search(r'link\.', found[0]['message'])


def test_후보로_낼_규칙이_없는_절차는_조치_후보_규칙을_더하라고_화면_말로_알린다(catalog):
    p = proposal('HM-8')
    p['knowledge']['rules'] = [r for r in p['knowledge']['rules'] if r.get('table') != 'dt:action-candidates']
    found = [i for i in manual_preflight.validate(p, catalog)['issues'] if i['code'] == 'CANDIDATE_RULE_MISSING']
    assert found and all('조치 후보 규칙' in i['message'] and 'dt:' not in i['message'] for i in found)


def test_고장_유형을_고르지_않은_고장_조치는_고르라고_알린다(catalog):
    p = proposal('HM-8')
    sop = p['procedures'][0]
    sop['link'] = {k: v for k, v in sop['link'].items() if k not in ('failureMode', 'relation', 'addresses')}
    found = [i for i in manual_preflight.validate(p, catalog)['issues'] if i['sop'] == sop['id'] and i['code'] == 'FAILURE_MODE_REQUIRED']
    assert found and '고장 유형' in found[0]['message'] and 'failureMode' not in found[0]['message']


def test_검토_화면의_빈_연결로_제안_연결을_지울_수_있다(catalog):
    p = proposal('HM-8')
    sop = p['procedures'][0]['id']
    p['links'] = {sop: {}}
    assert 'FAILURE_MODE_REQUIRED' in codes(manual_preflight.validate(p, catalog))


def test_정비_시행_절차는_구조_검사만_했다고_실행_때_다시_확인한다고_알린다(seeded_graph, catalog):
    """PM-02 는 냉각 문서의 고장 유형 · 부품을 쓴다 — 시작과 같은 순서로 HM-8 지식이 있는 그래프가 아니면 참조가 비므로 그 사실만 본다."""
    result = manual_preflight.validate(proposal('PM-02'), catalog)
    pm = [e for e in result.get('execution') or [] if any(i['code'] == 'PM_ACTUAL_CONTEXT_REQUIRED' for i in e['issues'])]
    assert pm and all(e['ready'] is False and e['evaluation_mode'] == 'structural' for e in pm)
    assert all('정기 정비' in i['message'] or '실제 운전 시간' in i['message'] for e in pm for i in e['issues'] if i['code'].startswith('PM_'))


def test_실행_구매_절차에_총비용_정책이_없으면_구매_판단_준비가_안_됐다고_알린다(catalog):
    p = proposal('PR-07')
    for x in p['procedures']:
        (x.get('link') or {}).pop('purchase_comparison_policy', None)
    result = manual_preflight.validate(p, catalog)
    buying = [e for e in result.get('execution') or [] if e['executable'] is True]
    assert buying and all(any(i['code'] == 'PURCHASE_COMPARISON_POLICY_REQUIRED' for i in e['issues']) for e in buying)
    assert result['executable_ready'] is False


def test_적재할_절차가_없으면_그렇게_말한다(catalog):
    result = manual_preflight.validate({'sections': [], 'procedures': []}, catalog)
    assert codes(result) == {'NO_PROCEDURES'}


def test_검사는_제안을_고치지_않는다(catalog):
    p = proposal('HM-8')
    before = deepcopy(p)
    manual_preflight.validate(p, catalog)
    assert p == before
