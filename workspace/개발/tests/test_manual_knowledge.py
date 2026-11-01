"""문서 지식(procsvc/manual_knowledge.py) — 고장 유형 · 원인 · 증거 · 규칙과 절차 연결의 모양 검사, 지금 그래프(카탈로그)에 비춘 의미 검사.
모양 검사는 강사 서명 묶음의 검토본과 그것을 고친 사본으로, 의미 검사는 kg-seed 가 끝난 그래프(seeded_graph)의 실제
카탈로그로 판정한다."""
from copy import deepcopy

import pytest

import class_knowledge
from procsvc import manual_knowledge as mk

DOCS = {i['doc']: i for i in class_knowledge.reviewed()}
HM8 = DOCS['HM-8']['proposal']
PR07 = DOCS['PR-07']['proposal']


def sections_of(proposal):
    return {s['ref'] for s in proposal['sections']}


def sops_of(proposal):
    return {p['id'] for p in proposal['procedures']}


def check(knowledge, proposal=HM8):
    return mk.validate(knowledge, sections=sections_of(proposal), sops=sops_of(proposal), anchor=lambda a: a)


def test_강사_검토본의_지식은_모양_검사를_지난다():
    out = check(deepcopy(HM8['knowledge']))
    assert {k: len(v) for k, v in out.items()} == {k: len(HM8['knowledge'][k]) for k in mk.KINDS}


def test_지식이_없으면_검사할_것이_없다():
    assert check(None) is None


def _bad_id(k):
    k['causes'][0]['id'] = 'Cause One'


def _dup_id(k):
    k['rules'].append(deepcopy(k['rules'][0]))


def _no_section(k):
    k['evidence'][0]['section'] = 'NO-9'


def _extra_kind(k):
    k['skills'] = []


@pytest.mark.parametrize('change, says', [(_bad_id, 'id 형식'), (_dup_id, '중복'), (_no_section, 'section'), (_extra_kind, 'knowledge는')],
                         ids=['원인 id 꼴', '규칙 id 겹침', '없는 절', '모르는 지식 종류'])
def test_지식의_빈틈은_무엇이_틀렸는지_모아_거절한다(change, says):
    knowledge = deepcopy(HM8['knowledge'])
    change(knowledge)
    with pytest.raises(ValueError, match=says):
        check(knowledge)


def test_절차_연결은_빈_글을_값_없음으로_읽는다():
    assert mk.blanks_as_absent({'failureMode': ' ', 'actions': [{'action': 'action:fan', 'value': ''}]}) == \
        {'failureMode': None, 'actions': [{'action': 'action:fan', 'value': None}]}


@pytest.mark.parametrize('link, says', [
    ({'relation': 'CAUSES'}, 'MITIGATED_BY'),
    ({'kind': 'robot'}, '설비 명령'),
    ({'scope': 'hr'}, '업무 범위'),
    ({'parts': ['part:x']}, '구매(purchase) 절차'),
    ({'failureMode': 'cooler'}, 'fm:'),
    ({'actions': [{'action': 'fan', 'value': 1}]}, 'action:'),
    ({'actions': [{'action': f'action:a{i}', 'value': 1} for i in range(mk.ACTIONS_MAX + 1)]}, f'최대 {mk.ACTIONS_MAX}개'),
], ids=['관계', '종류', '업무 범위', '고장 조치에 구매 칸', '고장 유형 id', '원자 조치 id', '원자 조치 개수'])
def test_절차_연결의_틀린_칸은_SOP_번호와_화면_말로_거절한다(link, says):
    with pytest.raises(ValueError) as refused:
        mk.validate_link('SOP-COOL-11', link, sops={'SOP-COOL-11'}, require_failure_mode=False)
    assert str(refused.value).startswith('SOP-COOL-11') and says in str(refused.value)


def test_적재에서는_고장_조치의_고장_유형이_꼭_있어야_한다():
    with pytest.raises(ValueError, match='고장 유형'):
        mk.validate_link('SOP-COOL-11', {'relation': 'MITIGATED_BY'}, sops={'SOP-COOL-11'}, require_failure_mode=True)


def test_규칙의_사람용_문장은_실행_조건에서_만든다():
    tests = [{'variable': 'ts1', 'operator': '>=', 'value': 55.0}, {'variable': 'mode', 'operator': '==', 'value': 'REMOTE'},
             {'variable': 'ok', 'operator': '==', 'value': True}]
    assert mk.when_text(tests) == "ts1 >= 55 and mode == 'REMOTE' and ok == true"


@pytest.mark.parametrize('aggregate, sql_value, rule', [('avg', 'avg(value)', 'avg(TS1) over 30s > 70'),
                                                       ('range', 'max(value) - min(value)', 'max(TS1) - min(TS1) over 30s > 70')])
def test_증거는_태그_집계_창으로_SQL과_사람용_문장을_만든다(aggregate, sql_value, rule):
    assert mk.evidence_sql('TS1', aggregate, 30).startswith(f'SELECT {sql_value} AS value FROM tag_1s')
    assert mk.evidence_rule('TS1', aggregate, 30, 'gt', 70) == rule


def test_인용에_없는_수치는_원문을_확인하라고_경고한다():
    proposal = deepcopy(HM8)
    rule = next(r for r in proposal['knowledge']['rules'] if r['id'] == 'rule:cooler-forecast-temperature-warning')
    assert mk.source_value_warnings(proposal) == [] or all(rule['id'] not in w for w in mk.source_value_warnings(proposal))
    rule['tests'][0]['value'] = 57
    assert any(rule['id'] in w and '57' in w for w in mk.source_value_warnings(proposal))


# ---------------------------------------------------------------- 지금 그래프에 비춘 의미 검사(시작이 끝난 학생 PC 그래프)
@pytest.fixture
def catalog(seeded_graph, pg_dsn):
    """시작이 kg-seed 뒤 지식 적재 전에 하는 것과 같이 업무 DB 의 공급사 · 견적(정본)을 그래프로 옮긴 뒤의 카탈로그(시드에는 공급사가 없다)."""
    import psycopg
    from hydcommon import graphdb
    from procsvc import scm_sync
    scm_sync.sync(lambda cypher, **params: seeded_graph.query(cypher, **params), lambda: psycopg.connect(pg_dsn))
    with graphdb.connect() as driver, driver.session() as session:
        return mk.catalog(session)


def test_카탈로그는_공급사의_순정_표시를_싣는다(catalog):
    """P2-11 · G3b-27: 순정 여부는 공급사 속성 oem 하나로 본다(표시 이름 글자가 아니다)."""
    assert {s['id']: s['oem'] for s in catalog['suppliers']}['sup:b'] is True
    assert any(s.get('oem') is True for p in catalog['parts'] for s in p['suppliers'])


def _purchase_plan(proposal):
    plan = {'procedures': [], 'knowledge': deepcopy(proposal.get('knowledge') or {})}
    for p in proposal['procedures']:
        link = deepcopy(p.get('link') or {})
        link.setdefault('kind', 'work_order')
        plan['procedures'].append(dict(id=p['id'], name=p['name'], **link))
    return plan


def test_구매_검토본은_지금_그래프의_부품_공급사_역할로_의미_검사를_지난다(catalog):
    _, issues = mk.graph_semantics(_purchase_plan(PR07), catalog)
    assert issues == []


def test_순정_우선_구매에_순정_공급사가_없으면_그_부품을_짚어_멈춘다(catalog):
    without = deepcopy(catalog)
    for p in without['parts']:
        for s in p['suppliers']:
            s['oem'] = False
    _, issues = mk.graph_semantics(_purchase_plan(PR07), without)
    assert any(i['code'] == 'PURCHASE_OEM_SOURCE_MISSING' and '순정' in i['message'] for i in issues)


def test_공급사_이름을_바꿔도_순정_판정은_같다(catalog):
    renamed = deepcopy(catalog)
    for p in renamed['parts']:
        for s in p['suppliers']:
            s['name'] = '이름을 바꾼 공급사'
    assert mk.graph_semantics(_purchase_plan(PR07), renamed)[1] == []


def test_구매_후보_규칙에_재고_경보_조건이_없으면_까닭을_말하며_멈춘다(catalog):
    plan = _purchase_plan(PR07)
    for r in plan['knowledge'].get('rules') or []:
        r['tests'] = [t for t in r['tests'] if t.get('input') != 'in:pattern' and t.get('variable') != 'pattern']
    _, issues = mk.graph_semantics(plan, catalog)
    assert any(i['code'] == 'PURCHASE_RULE_PATTERN_REQUIRED' and '예비품 재고 기준 이탈' in i['message'] for i in issues)
