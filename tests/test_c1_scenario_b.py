"""시나리오 B 정기 정비(2026-10-09 확정): 문서 PM-02를 적재하면 정기 정비 지식과 경쟁하는 시행 방식이 생긴다.

- 정비 패키지 SOP와 단계, 시행 방식 SOP 넷(이번 정비 시간 단독 · 지금 정지 · 미루기 · 두 대 묶기), 모두 예방 조치(PREVENTED_BY).
- 주기 · 허용 오차 · 생산 · 인원 · 부품 규칙은 문장이 아니라 TESTS 관계(임계값)다.
- C 구매 SOP가 기대는 펌프 고장 지식(fm:volumetric-loss · cause:pump-seal-wear)을 B가 만든다 — 적재 순서 A → B → C.
- 해피패스가 아니다: 지는 대안이 실제 이유로 진다(미루기 → 허용 오차 위반 제외, 지금 정지 → 오더 손실 감점, 두 대 묶기 → 인력 부족 감점).
  순위는 에이전트가 쓰는 판단 엔진(agentsvc.cards.evaluate)과 시드 순위 정책(rule:rank-value)으로 계산한다.
LLM 추출은 tests/c1_fixtures.py 결정론 대역으로 대신한다. 실제 Neo4j 적재 · 순위는 scripts/probe_c1_knowledge.py가 확인한다.
"""
import copy
import json
import re

import pytest

import c1_fixtures as fx
from agentsvc import cards
from procsvc import manual_graph
from test_c1_knowledge import archive, edges, load, plan_of  # noqa: F401  (pytest fixture 재사용)

ROOT = fx.ROOT
# 성과 지표 방향(instances.cypher의 BSC 성과 지표와 같은 값)
DIRECTION = {'msr:mtbf': 'UP', 'msr:availability': 'UP', 'msr:throughput': 'UP', 'msr:maint-cost': 'DOWN', 'msr:penalty': 'DOWN'}


def rank_policy():
    text = (ROOT / 'it/neo4j/v2/instances.cypher').read_text(encoding='utf-8')
    raw = re.search(r"SET r\.rankingPolicy = '(.*)';", text).group(1)
    return raw.replace("\\'", "'")


def engine_inputs(plan):
    """그래프 템플릿(t3_dmn · t3_skills · t3_tradeoffs)이 적재 결과에서 읽을 모양을 계획(plan)에서 그대로 만든다."""
    after = manual_graph.desired(plan)
    sid = {p['id']: manual_graph.skill_id(p['id']) for p in plan['procedures']}
    to_skill = lambda ref: sid.get(ref, ref)
    dmn = [dict(decision='dec:rank-actions', rule='rule:rank-value', ord=1, effect='RANK', tests=[], outputs=[], applies=[],
                penalizes=[], sources=['ks:strategy-map'], rankingPolicy=rank_policy(), when='true'),
           dict(decision='dec:compliance', rule='rule:ts1-hard', ord=2, effect='EXCLUDE', when='forecast_ts1 >= 65', applies=[], outputs=[],
                tests=[dict(input='in:forecast-ts1', variable='forecast_ts1', operator='>=', value=65)], penalizes=[], sources=['ks:sr-04'])]
    for r in plan['knowledge']['rules']:
        if r['table'] == 'dt:diagnose-cause':
            continue
        dmn.append(dict(decision='dec:' + r['table'][3:], rule=r['id'], ord=r['order'] or 100, effect=r['effect'], penalty=r['penalty'],
                        when=next(n['props']['when'] for n in after['nodes'] if n['props']['id'] == r['id']), annotation=r['annotation'],
                        tests=[dict(input=t['input'], variable=t['variable'], operator=t['operator'], value=t['value']) for t in r['tests']],
                        outputs=[to_skill(o) for o in r['outputs']], applies=[to_skill(a) for a in r['applies_to']],
                        penalizes=[r['penalizes']] if r['penalizes'] else [], sources=[r['section']]))
    skills, tradeoffs = {}, []
    for p in plan['procedures']:
        k = sid[p['id']]
        skills[k] = dict(skillId=k, sopId=p['id'], name=p['name'], kind=p['kind'], relation=p['relation'],
                         approver=dict(id=p['approver'], level=2), addresses=p.get('addresses') or [],
                         actions=[dict(code='WO_CREATE', kind='transaction', value=a['value']) for a in p.get('actions') or []])
        for a in p.get('affects') or []:
            tradeoffs.append(dict(skill=k, measure=a['target'], name=a['target'], direction=DIRECTION[a['target']], owners=[],
                                  nodes=[k, a['target']], conds=[],
                                  edges=[dict(key=f"{k}>{a['target']}", type='AFFECTS', source=k, target=a['target'], sign=a['sign'])]))
    # 정비 · 구매 카드는 설비 명령이 없다: 예측은 지금 운전점 그대로(공칭 48 ℃) — 인터록 규칙이 '모름'으로 막지 않게
    forecasts = {k: {'sv:ts1': dict(value=48.0, variableName='유온', unit='℃', method='nominal', id='fc:nominal')} for k in skills}
    return dmn, skills, tradeoffs, forecasts


def rank(plan, **changes):
    dmn, skills, tradeoffs, forecasts = engine_inputs(plan)
    facts = dict(fx.B_FACTS, **changes)
    return cards.evaluate(dmn, skills, facts, forecasts, tradeoffs, [], {})


def by_sop(result):
    return {o['sopId']: o for o in result['options']}


# ------------------------------------------------------------------ 문서 → 지식

def test_document_b_yields_preventive_skills_steps_parts_and_threshold_rules(archive):
    plan = plan_of(archive, 'B')
    after = manual_graph.desired(plan)
    sops = {p['id'] for p in plan['procedures']}
    assert sops == {'SOP-PM-11', 'SOP-PM-12', 'SOP-PM-13', 'SOP-PM-14', 'SOP-PM-21', 'SOP-PM-22', 'SOP-PM-23'}
    # 모든 B 스킬은 예방 조치(PREVENTED_BY)로 펌프 체적 효율 저하에 매칭 — 시정 관계(MITIGATED_BY · REMEDIED_BY)는 없다
    assert {(e['from_id'], e['to_id']) for e in edges(after, 'PREVENTED_BY')} == \
        {('fm:volumetric-loss', manual_graph.skill_id(s)) for s in sops}
    assert not edges(after, 'MITIGATED_BY') and not edges(after, 'REMEDIED_BY')
    # 패키지 단계: LOTO · 잔압 해제 · 씰 · 필터 · 시운전
    steps = [s['text'] for p in plan['procedures'] if p['id'] == 'SOP-PM-21' for s in p['steps']]
    assert len(steps) == 7 and '잠금(LOTO)' in steps[0] and '잔압' in steps[1] and '0 bar' in steps[2] and '씰 키트' in steps[3] \
        and '리턴 필터' in steps[4] and 'PM-2.9' in steps[6]
    # 펌프 고장 지식(C가 기대는 id) · 부품(리턴 필터는 구조판 시드 부품)
    labels = {}
    for n in after['nodes']:
        labels.setdefault(n['labels'][0], set()).add(n['props']['id'])
    assert labels['FailureMode'] == {'fm:volumetric-loss'} and labels['Cause'] == {'cause:pump-seal-wear', 'cause:oil-contamination'}
    assert {(e['from_id'], e['to_id']) for e in edges(after, 'INVOLVES_PART')} == \
        {('cause:pump-seal-wear', 'part:pump-seal'), ('cause:oil-contamination', 'part:return-filter')}
    # 시행 방식은 모두 이번 차례 패키지(SOP-PM-21) 정비 오더를 낸다. 시행 방식은 원인 한정(ADDRESSES)이 없다 — 도래 경보에는 원인이 없다
    cons = {(e['from_id'], e['props'].get('value')) for e in edges(after, 'CONSISTS_OF')}
    assert {(manual_graph.skill_id(s), 'SOP-PM-21') for s in fx.B_OPTIONS} <= cons
    assert not {e['from_id'] for e in edges(after, 'ADDRESSES')} & {manual_graph.skill_id(s) for s in fx.B_OPTIONS}
    assert {e['to_id'] for e in edges(after, 'APPROVED_BY')} == {'role:maint-mgr'}


def test_interval_and_tolerance_are_tests_relations_not_sentences(archive):
    plan = plan_of(archive, 'B')
    after = manual_graph.desired(plan)
    tests = {(e['from_id'], e['to_id'], e['props']['operator'], e['props']['value']) for e in edges(after, 'TESTS')}
    assert ('rule:cand-pm-due', 'in:pattern', '==', 'PM_DUE') in tests and ('rule:cand-pm-due', 'in:hours-since-pm', '>=', 1800) in tests
    assert ('rule:pm-window-limit', 'in:next-scheduled-time', '>', 2200) in tests
    assert ('rule:pm-defer-limit', 'in:hours-if-deferred', '>', 2200) in tests
    assert ('rule:pm-stop-order', 'in:order-due', '<', 24) in tests and ('rule:pm-bundle-crew', 'in:pm-crew', '<', 4) in tests
    rules = {n['props']['id']: n['props'] for n in after['nodes'] if n['labels'] == ['Rule']}
    assert rules['rule:cand-pm-due']['when'] == "pattern == 'PM_DUE' and hours_since_pm >= 1800"
    assert rules['rule:pm-defer-limit']['when'] == 'hours_at_following_window > 2200' and rules['rule:pm-defer-limit']['effect'] == 'EXCLUDE'
    assert rules['rule:pm-bundle-crew']['penalty'] == 60 and rules['rule:pm-stop-order']['penalty'] == 80
    # 후보 규칙은 시행 방식 넷만 낸다(패키지 SOP는 정비 오더의 내용이지 후보가 아니다)
    assert {e['to_id'] for e in edges(after, 'OUTPUTS') if e['from_id'] == 'rule:cand-pm-due'} == \
        {manual_graph.skill_id(s) for s in fx.B_OPTIONS}
    assert all(e['to_labels'] == ['ManualSection'] for e in edges(after, 'DERIVED_FROM'))


def test_b_creates_exactly_the_pump_knowledge_that_document_c_links_to(archive):
    """적재 순서 A → B → C: C의 구매 SOP가 가리키는 고장 유형 · 원인은 B가 만든 id다(구조판에는 없다)."""
    b = plan_of(archive, 'B')
    c = plan_of(archive, 'C')
    made = {f['id'] for f in b['knowledge']['failure_modes']} | {x['id'] for x in b['knowledge']['causes']}
    wanted = {p['failureMode'] for p in c['procedures']} | {a for p in c['procedures'] for a in p.get('addresses') or []}
    assert wanted and wanted <= made
    a = plan_of(archive, 'A')
    ids = lambda plan: {i['id'] for kind in plan['knowledge'].values() for i in kind}
    assert not ids(a) & ids(b) and not ids(b) & ids(c)                      # 문서끼리 같은 지식 id를 다시 만들지 않는다
    assert not {p['id'] for p in a['procedures']} & {p['id'] for p in b['procedures']}


def test_b_document_has_no_second_approval_and_no_forbidden_word():
    text = fx.DOC_B.read_text(encoding='utf-8')
    assert '정비창' not in text and '추가 승인' not in text and '추가로 승인' not in text
    for doc in (fx.DOC_A, fx.DOC_C):
        other = doc.read_text(encoding='utf-8')
        assert '정비창' not in other and '추가로 승인' not in other and '추가 승인' not in other


# ------------------------------------------------------------------ 경쟁: 지는 대안이 실제 이유로 진다

def test_b_recommends_tonight_alone_and_each_alternative_loses_for_its_own_reason(archive):
    result = rank(plan_of(archive, 'B'))
    o = by_sop(result)
    assert set(o) == set(fx.B_OPTIONS)
    assert result['recommended'] == manual_graph.skill_id('SOP-PM-11')
    # 허용 오차 밖으로 미루기 → 규정 위반으로 제외
    assert not o['SOP-PM-13']['feasible'] and [v['rule'] for v in o['SOP-PM-13']['violations']] == ['rule:pm-defer-limit']
    # 지금 바로 정지 → 오더 손실 감점 + 생산 정지
    assert o['SOP-PM-12']['feasible'] and [p['rule'] for p in o['SOP-PM-12']['penalties']] == ['rule:pm-stop-order']
    assert o['SOP-PM-12']['production'] == 'stop'
    # 두 대 묶기 → 인력 부족 감점. 감점이 없으면 정지 횟수가 줄어 묶기가 더 나은 안이다(진짜 경쟁)
    assert [p['rule'] for p in o['SOP-PM-14']['penalties']] == ['rule:pm-bundle-crew']
    assert o['SOP-PM-14']['scoreParts']['bsc'] > o['SOP-PM-11']['scoreParts']['bsc']
    assert o['SOP-PM-11']['score'] > o['SOP-PM-14']['score'] > o['SOP-PM-12']['score']
    # 부품: 지금 출고하는 안에는 구매 경보 예정 경고(C 예고)
    assert {s for s, x in o.items() if any(w['rule'] == 'rule:pm-spare-warn' for w in x['warnings'])} == set(fx.B_NOW)
    assert [x['rank'] for x in sorted(o.values(), key=lambda x: x['rank'])][-1] == o['SOP-PM-13']['rank']
    json.dumps(result, ensure_ascii=False, default=str)                     # 카드로 보낼 수 있는 모양


@pytest.mark.parametrize('change, winner, why', [
    (dict(pm_crew_available=4), 'SOP-PM-14', '인원이 4명이면 묶음 감점이 없어 정지 한 번으로 두 대를 하는 안이 이긴다'),
    (dict(spare_available=1), 'SOP-PM-11', '씰 키트가 1개면 두 대 묶기는 부품 부족으로 제외된다'),
    (dict(spare_available=0), None, '씰 키트가 없으면 지금 하는 안은 모두 제외, 미루기도 허용 오차 밖 — 추천 없음(비해피 가지)'),
    (dict(hours_at_next_window=2210), None, '이번 정비 시간이 상한을 넘으면 기다리는 안이 제외된다'),
])
def test_b_ranking_moves_with_the_facts_not_with_a_fixed_answer(archive, change, winner, why):
    result = rank(plan_of(archive, 'B'), **change)
    o = by_sop(result)
    if winner:
        assert result['recommended'] == manual_graph.skill_id(winner), why
    elif 'spare_available' in change:
        assert result['recommended'] is None, why
    else:
        assert not o['SOP-PM-11']['feasible'] and not o['SOP-PM-14']['feasible'], why
        assert result['recommended'] == manual_graph.skill_id('SOP-PM-12'), '남는 것은 지금 바로 정지뿐 — 오더 손실을 감수한다'
    if change.get('spare_available') == 1:
        assert [v['rule'] for v in o['SOP-PM-14']['violations']] == ['rule:pm-bundle-spare']


def test_b_options_are_not_candidates_for_other_alerts(archive):
    """도래 경보가 아닌 처리 건(설비 경보 · 재고 경보)에서는 정기 정비 시행 방식이 후보로 나오지 않는다."""
    for facts in (dict(pattern='PUMP_LEAKAGE', failure_mode='fm:volumetric-loss', cause='cause:pump-seal-wear'),
                  dict(pattern='SPARE_BELOW_MIN'), dict(pattern='PM_DUE', hours_since_pm=1700)):
        assert rank(plan_of(archive, 'B'), **facts)['options'] == [], facts
