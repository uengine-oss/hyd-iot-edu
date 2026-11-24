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


def test_설명이_없는_규칙은_적재하지_않고_그_규칙을_대며_거절한다():
    """규칙에는 이름이 없어 설명(annotation)이 하나뿐인 사람 말이다 — 판단 기록 · 규칙 판단의 「적용한 규칙」 표 · 검토 화면이 이 글로 규칙을 부른다.
    전에는 비워도 받아, 다른 설비 문서를 실제 AI 로 추출한 적재(2026-11-23)의 후보 규칙 여덟이 화면에 「규칙 표시 이름 미등록」으로 보였다
    (2026-11-24 3회차 실습 04). 빠진 것과 빈칸만 있는 것 모두 그 규칙 id 를 대며 거절한다(추출이면 AI 교정으로 돌아간다)."""
    knowledge = deepcopy(HM8['knowledge'])
    missing, blank = knowledge['rules'][0], knowledge['rules'][1]
    missing.pop('annotation')
    blank['annotation'] = '  '
    with pytest.raises(ValueError) as e:
        check(knowledge)
    assert all(f"{r['id']} 설명(annotation" in str(e.value) for r in (missing, blank)), e.value
    assert check(deepcopy(HM8['knowledge']))['rules'][0]['annotation'] == HM8['knowledge']['rules'][0]['annotation'].strip()


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


def test_판단이_읽지_않는_입력을_견주는_규칙은_쓸_수_없는_까닭과_쓸_수_있는_입력을_말한다(catalog):
    """전수 대조 10-G4: 학생이 지식 › 데이터 원천(표 정의)으로 만든 입력을 문서 규칙이 견주면 「… 이 입력 …을 선언하지 않았습니다(REQUIRES_INPUT).
    선언된 입력: [...]」으로 멈췄다 — 관계 이름과 id 목록만 보이고, 표 정의로 만든 입력은 판단 규칙에 쓸 수 없다는 것과 무엇으로 바꾸면 되는지를
    말하지 않았다. 판단에 입력을 잇는 길은 기본 제공 지식뿐이다(넓히지 않는다) — 그 범위를 말하고 멈춘다."""
    plan = _purchase_plan(PR07)
    rule = next(r for r in plan['knowledge']['rules'] if r['tests'])
    table = next(t for t in catalog['decision_tables'] if t['id'] == rule['table'])
    usable = next(i for i in table['inputs'] if i.get('name'))
    rule['tests'][0]['input'] = 'in:legacy-scrap-rate'                    # 표 정의 적재가 만든 입력 꼴 — 이 판단이 읽는 입력이 아니다
    _, issues = mk.graph_semantics(plan, catalog)
    (said,) = [i['message'] for i in issues if i['code'] == 'RULE_INPUT_NOT_DECLARED']
    assert rule['id'] in said and 'in:legacy-scrap-rate' in said
    assert '「지식 › 문서 등록 › 업무 DB 표 정의」로 만든 입력은 판단 규칙에 쓸 수 없습니다' in said             # 안 되는 것은 안 된다고 — 표 정의를 넣는 실제 메뉴 이름으로(C14)
    assert f"{usable['id']}({usable['name']})" in said                     # 바꿀 수 있는 입력은 id 와 사람이 읽는 이름으로
    assert 'REQUIRES_INPUT' not in said


# ---------------------------------------------------------------- 새 항목 제안(다른 설비의 구성 요소 · 증상 · 센서) — 꼴 검사
def _apu_validated(tmp_path):
    """다른 설비의 실제 규모 문서(apu_document)를 보관소에 올리고 추출 계약을 지난 제안(인용 좌표가 채워진 것)."""
    import apu_document as apu
    from procsvc import manual_extraction
    from procsvc.manual_sources import ManualSources
    source = ManualSources(tmp_path / 'm.sqlite3').save('hyd', apu.FILENAME, apu.RAW)
    return manual_extraction.validate_proposal(source, apu.proposal(source['source_id']))


def test_새_항목은_추출_제안에는_승인_없이만_있고_검토본에는_넣기를_고른_것만_있다(tmp_path):
    """새 항목은 몰래 만들지 않는다 — AI 가 낸 제안은 승인할 수 없고(approved 칸을 쓰면 거절), 사람이 검토한 본문은 넣기를 고른 항목(approved=true)만 받는다.
    그 판정이 있는 문서에서 지식의 꼴은 새 항목 종류를 함께 돌려준다."""
    p = _apu_validated(tmp_path)
    out = check(deepcopy(p['knowledge']), p)
    assert {k: len(out[k]) for k in mk.NEW_KINDS} == {'components': 9, 'symptoms': 7, 'sensors': 15}
    smuggled = deepcopy(p['knowledge'])
    smuggled['components'][0]['approved'] = True
    with pytest.raises(ValueError, match='추출 제안은 새 구성 요소 「공기 압축기」를 승인하지 않습니다'):
        check(smuggled, p)
    unchosen = deepcopy(p['knowledge'])
    for kind in mk.NEW_KINDS:
        for item in unchosen[kind]:
            item['approved'] = True
    del unchosen['sensors'][0]['approved']
    with pytest.raises(ValueError, match='새 센서 「압축기 압력」은 사람이 검토 화면에서 「넣기」를 골라야 적재됩니다'):
        mk.validate(unchosen, sections=sections_of(p), sops=sops_of(p), anchor=lambda a: a, reviewed=True)
    unchosen['sensors'][0]['approved'] = True
    assert len(mk.validate(unchosen, sections=sections_of(p), sops=sops_of(p), anchor=lambda a: a, reviewed=True)['sensors']) == 15


def test_새_항목이_없는_문서의_지식은_전과_같은_꼴이다():
    """수업 문서의 적재 계획은 새 항목 종류의 빈 목록을 싣지 않는다 — 계획 · 영수증 · 검토 화면이 전과 같다."""
    assert set(check(deepcopy(HM8['knowledge']))) == set(mk.KINDS)


def test_증거는_수집_태그면_판단_엔진이_평가할_SQL을_갖고_센서_태그면_SQL이_없다(tmp_path):
    p = _apu_validated(tmp_path)
    apu_evidence = check(deepcopy(p['knowledge']), p)['evidence']
    assert apu_evidence and all('sql' not in e for e in apu_evidence)
    assert all(e['sql'].startswith('SELECT') for e in check(deepcopy(HM8['knowledge']))['evidence'])
    bad = deepcopy(p['knowledge'])
    bad['evidence'][0]['tag'] = '압력 값'
    with pytest.raises(ValueError, match='tag는 수집 계약의 태그'):
        check(bad, p)
    note = mk.unevaluated_note('TP2', '압축기 압력')
    assert '「압축기 압력」(태그 TP2)는' in note and '판단 엔진이 이 증거를 평가하지 않습니다' in note and '도구 서버' in note


@pytest.mark.parametrize('change, says', [
    (lambda s: s[0].update(tag='TS1'), '이 시스템이 수집하는 유압 설비 값의 이름이라 새 센서의 태그로 쓸 수 없습니다'),
    (lambda s: s[1].update(tag=s[0]['tag']), '쓰는 새 센서가 둘 이상입니다'),
    (lambda s: s[0].update(tag='TP 2'), '그 설비 시스템이 쓰는 센서 태그입니다'),
    (lambda s: s[0].pop('component'), 'comp:… 형식의 온톨로지 id가 필요합니다'),
], ids=['수집 태그와 같은 이름', '두 센서가 같은 태그', '태그 꼴', '붙은 구성 요소 없음'])
def test_새_센서의_태그와_구성_요소가_틀리면_까닭과_함께_거절한다(tmp_path, change, says):
    p = _apu_validated(tmp_path)
    knowledge = deepcopy(p['knowledge'])
    change(knowledge['sensors'])
    with pytest.raises(ValueError, match=says):
        check(knowledge, p)
