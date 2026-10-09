"""확정 TODO C1: 문서 적재가 고장 유형 · 원인 · 증거 · 규칙 · 원자 조치 값까지 만든다(추출 계약 → 검토 → 적재).

LLM 추출은 시험 대역(tests/c1_fixtures.py, 문서 원문 인용에 묶인 결정론 제안)으로 대신한다. 그래프 쪽 확인(check_graph)은
온톨로지 목록을 돌려주는 가짜 세션으로 한다. 실제 Neo4j 적재 · 되돌리기는 scripts/probe_c1_knowledge.py(.evidence/a161-c1/)가 확인한다.
"""
import copy

import pytest

import c1_fixtures as fx
from procsvc import manual_extraction, manual_graph, manual_knowledge, manual_review, manual_segments
from procsvc.manual_sources import ManualSources


@pytest.fixture
def archive(tmp_path):
    return ManualSources(tmp_path / 'manuals.sqlite')


def load(archive, key):
    path, spec, links = fx.DOCS[key]
    source = archive.save('hyd', path.name, path.read_bytes())
    return source, fx.proposal(source, spec, links)


# 온톨로지 목록의 가짜 그래프: 구조판 시드(instances.cypher · scenario_structure.cypher)에 있는 것과 같은 id · 범위 · 결정표 입력
ACTIONS = [dict(id='action:set-fan', code='FAN_SET', kind='command', min=0, max=100), dict(id='action:set-load', code='LOAD_SET', kind='command', min=60, max=100),
           dict(id='action:work-order', code='WO_CREATE', kind='transaction', min=None, max=None),
           dict(id='action:purchase-request', code='PR_CREATE', kind='transaction', min=None, max=None)]
INPUTS = {'dt:diagnose-cause': ['in:pattern:pattern', 'in:ce:ce', 'in:ts1:ts1', 'in:ps1:ps1'],
          'dt:action-candidates': ['in:failure-mode:failure_mode', 'in:pattern:pattern', 'in:cause:cause', 'in:plc-state:plc_state',
                                   'in:hours-since-pm:hours_since_pm'],
          'dt:compliance': ['in:skill-kind:skill_kind', 'in:skill-code:skill_code', 'in:plc-mode:plc_mode', 'in:forecast-ts1:forecast_ts1', 'in:fan100-hours:fan100_hours',
                            'in:supplier-avl:supplier_avl', 'in:pattern:pattern', 'in:po-amount:po_amount', 'in:lead-slack-days:lead_slack_days',
                            'in:supplier-fail-rate:supplier_fail_rate',
                            'in:next-scheduled-time:hours_at_next_window', 'in:hours-if-deferred:hours_at_following_window',
                            'in:order-due:order_due_h', 'in:pm-crew:pm_crew_available', 'in:spare-available:spare_available']}


def seed_compliance_inputs():
    """구조판 시드가 규정 결정(dec:compliance)에 실제로 선언한 입력 id → 변수 이름. instances.cypher의 판단 정의 행 +
    scenario_structure.cypher의 REQUIRES_INPUT 추가분(C · B). 위 가짜 그래프가 시드에 없는 입력을 지어내지 않는지 대조한다."""
    import re
    v2 = fx.ROOT / 'it' / 'neo4j' / 'v2'
    inst, struct = (v2 / 'instances.cypher').read_text(encoding='utf-8'), (v2 / 'scenario_structure.cypher').read_text(encoding='utf-8')
    declared = set(re.search(r"\['dec:compliance','[^']*','[^']*','dt:compliance','COLLECT',\[([^\]]*)\]", inst)[1].replace("'", '').split(','))
    declared |= set(re.search(r"UNWIND \[([^\]]*)\] AS iid\s*\nMATCH \(d:Decision \{id: 'dec:compliance'\}\)", struct)[1].replace("'", '').split(','))
    declared |= set(re.findall(r"\['dec:compliance','task:compliance','(in:[a-z0-9-]+)'\]", struct))
    variables = dict(re.findall(r"\['(in:[a-z0-9-]+)','[^']*','[a-z]+','([a-z0-9_]+)'", inst + struct))
    return {i: variables.get(i) for i in declared}


class FakeTx:
    def run(self, q, **kw):
        class R:
            def __init__(self, rows): self.rows = rows
            def data(self): return self.rows
        if 'MATCH (n:Action)' in q:
            return R(ACTIONS)
        if 'MATCH (s:Supplier)' in q:
            return R([dict(id=s) for s in ('sup:a', 'sup:b', 'sup:c')])
        if 'MATCH (k:Skill)' in q:
            return R([dict(sop='SOP-TPMP-01')])
        if 'DecisionTable' in q:
            return R([dict(id=t, decision='dec:' + t[3:], inputs=[dict(id=i.rsplit(':', 1)[0], variable=i.rsplit(':', 1)[1]) for i in ins])
                      for t, ins in INPUTS.items()])
        raise AssertionError(q)


class FakeSession:
    def execute_read(self, fn):
        return fn(FakeTx())


def plan_of(archive, key):
    source, prop = load(archive, key)
    manual_extraction.validate_proposal(source, prop)
    plan = manual_review.validate(archive, 'hyd', fx.reviewed_body(source, prop))
    return manual_knowledge.check_graph(FakeSession(), plan, manual_graph.skill_id)


def edges(after, kind):
    return [e for e in after['edges'] if e['type'] == kind]


def test_fake_catalog_compliance_inputs_are_declared_by_the_seed():
    """가짜 그래프의 규정 입력은 시드가 선언한 것과 같다(id · 변수). 시드에 자리가 없으면 실제 추출도 사람 검토도 그 규칙을 적재할 수 없다
    (check_graph가 거부) — 라이브 4차에서 PR-7.4 불량률 규칙이 그렇게 빠졌다."""
    seed = seed_compliance_inputs()
    fake = dict(i.rsplit(':', 1) for i in INPUTS['dt:compliance'])
    assert {i: seed.get(i) for i in fake} == fake, set(fake.items()) - set(seed.items())
    used = {t['input'] for spec in (fx.A_KNOWLEDGE, fx.B_KNOWLEDGE, fx.C_KNOWLEDGE) for r in spec['rules'] if r['table'] == 'dt:compliance'
            for t in r['tests']}
    assert used <= set(seed), used - set(seed)
    assert seed['in:supplier-fail-rate'] == 'supplier_fail_rate'


def test_extraction_contract_carries_knowledge_and_the_ontology_catalog():
    d = manual_extraction.definition()
    assert d['version'] == manual_extraction.VERSION == '2.1'
    # 2.1: 단계의 선택 기준과 절차의 적용 조건을 나눈다(라이브 4차 SOP-PUR-13 — 조건을 값 고르기에 미리 적용해 다른 공급사를 골랐다)
    assert '선택 기준을 그대로 적용' in manual_extraction.INSTRUCTION and 'dt:compliance EXCLUDE 규칙으로 옮겨' in manual_extraction.INSTRUCTION
    act = d['activities'][0]
    assert 'ontology_catalog' in act['inputData'] and any(x['name'] == 'ontology_catalog' for x in d['data'])
    for word in ('"knowledge"', 'failure_modes', 'causes', 'evidence', 'rules', '"link"', 'actions', 'addresses', 'ontology_catalog'):
        assert word in manual_extraction.INSTRUCTION, word


@pytest.mark.parametrize('key', ['A', 'B', 'C'])
def test_every_knowledge_item_is_cited_from_the_document(archive, key):
    source, prop = load(archive, key)
    checked = manual_extraction.validate_proposal(source, prop)
    text = source['pages'][0]['text']
    for a in manual_knowledge.anchors(checked['knowledge']):
        assert text[a['start']:a['end']] == a['quote']
    cov = manual_extraction.coverage(source, checked)
    assert cov['cited'] > 0


def test_document_a_yields_cooling_failure_knowledge_rules_and_command_values(archive):
    plan = plan_of(archive, 'A')
    after = manual_graph.desired(plan)
    labels = {}
    for n in after['nodes']:
        labels.setdefault(n['labels'][0], set()).add(n['props']['id'])
    assert labels['FailureMode'] == {'fm:cooling-loss'}
    assert labels['Cause'] == {'cause:cooler-fin-fouling', 'cause:high-ambient', 'cause:fan-drive-fault'}
    assert len(labels['Evidence']) == 4 and len(labels['Rule']) == 5
    assert {'skill:sop-cool-11', 'skill:sop-cool-15', 'skill:sop-fan-11'} <= labels['Skill']
    # 증상 → 고장 유형, 원인 → 고장 유형 · 부품 · 외란, 원인 → 증거(서버가 만든 SQL)
    assert {(e['from_id'], e['to_id']) for e in edges(after, 'INDICATES')} == {('sym:ts1-rise', 'fm:cooling-loss'), ('sym:ce-drop', 'fm:cooling-loss')}
    assert ('cause:cooler-fin-fouling', 'part:cooler-core') in {(e['from_id'], e['to_id']) for e in edges(after, 'INVOLVES_PART')}
    assert {e['props']['sign'] for e in edges(after, 'DISTURBS')} == {1}
    ev = next(n['props'] for n in after['nodes'] if n['props']['id'] == 'evd:ce-low')
    assert ev['sql'] == ("SELECT avg(value) AS value FROM tag_1s WHERE asset = %(asset)s AND name = 'CE' "
                         "AND time > now() - interval '30 seconds'") and ev['rule'] == 'avg(CE) over 30s < 70' and ev['windowSeconds'] == 30
    # 원자 조치 값: 팬 100 % · 부하 80 % · 작업지시 SOP
    cons = {(e['from_id'], e['to_id'], e['props'].get('value'), e['props']['seq']) for e in edges(after, 'CONSISTS_OF')}
    assert ('skill:sop-cool-12', 'action:set-fan', 100, 1) in cons and ('skill:sop-cool-12', 'action:set-load', 80, 2) in cons
    assert ('skill:sop-cool-13', 'action:work-order', 'SOP-COOL-14', 2) in cons
    assert ('skill:sop-cool-14', 'cause:cooler-fin-fouling') in {(e['from_id'], e['to_id']) for e in edges(after, 'ADDRESSES')}
    # 규칙: 결정표 행 · TESTS · 사람이 읽는 when(TESTS에서 생성) · 출력 · 적용 · 감점 · 근거 절
    rules = {n['props']['id']: n['props'] for n in after['nodes'] if n['labels'] == ['Rule']}
    assert rules['rule:dx-cooling-fin']['when'] == "pattern == 'COOLER_DEGRADATION' and ce < 70"
    assert rules['rule:cool-fan-24h']['penalty'] == 20 and rules['rule:cool-fan-24h']['effect'] == 'PENALTY'
    assert ('dt:action-candidates', 'rule:cand-cooling-loss') in {(e['from_id'], e['to_id']) for e in edges(after, 'HAS_RULE')}
    outs = {e['to_id'] for e in edges(after, 'OUTPUTS') if e['from_id'] == 'rule:cand-cooling-loss'}
    assert outs == {'skill:sop-cool-11', 'skill:sop-cool-12', 'skill:sop-cool-13', 'skill:sop-cool-14', 'skill:sop-cool-15',
                    'skill:sop-fan-11', 'skill:sop-fan-12'}
    assert ('rule:cool-fan-24h', 'msr:mtbf') in {(e['from_id'], e['to_id']) for e in edges(after, 'PENALIZES')}
    assert all(e['to_labels'] == ['ManualSection'] for e in edges(after, 'DERIVED_FROM'))
    # 스키마 v2 그대로: 새 지식 레이블 · 관계에는 _manual_document를 붙이지 않는다(문서 소유는 적재 기록이 정한다)
    for n in after['nodes']:
        assert ('_manual_document' in n['props']) == (n['labels'][0] in manual_graph.TAGGED_LABELS)
    for e in after['edges']:
        own_rule_output = e['type'] == 'OUTPUTS' and e['from_id'] in rules
        assert ('_manual_document' in e['props']) == (e['type'] in manual_graph.TAGGED_RELATIONS and not own_rule_output), e


def test_document_c_yields_purchase_rules_and_supplier_values_without_new_failure_knowledge(archive):
    plan = plan_of(archive, 'C')
    after = manual_graph.desired(plan)
    labels = {n['labels'][0] for n in after['nodes']}
    assert 'FailureMode' not in labels and 'Cause' not in labels
    rules = {n['props']['id']: n['props'] for n in after['nodes'] if n['labels'] == ['Rule']}
    assert rules['rule:cand-spare-purchase']['when'] == "pattern == 'SPARE_BELOW_MIN'"
    assert rules['rule:pur-amount']['when'] == 'po_amount > 300' and rules['rule:pur-avl']['when'] == 'supplier_avl == false'
    # PR-7.4 불량률 문턱: 감점은 공급사 견적의 불량률을 시험한다(SOP 번호가 아니라) — 구매 SOP 셋 모두에 걸린다
    assert rules['rule:pur-inspection']['when'] == 'supplier_fail_rate > 0.1' and rules['rule:pur-inspection']['penalty'] == 20
    assert {e['to_id'] for e in edges(after, 'APPLIES_TO') if e['from_id'] == 'rule:pur-inspection'} == \
        {'skill:sop-pur-11', 'skill:sop-pur-12', 'skill:sop-pur-13'}
    assert {(e['from_id'], e['props']['value']) for e in edges(after, 'CONSISTS_OF')} == \
        {('skill:sop-pur-11', 'sup:b'), ('skill:sop-pur-12', 'sup:a'), ('skill:sop-pur-13', 'sup:c')}
    # 구매 SOP는 기존(다른 문서의) 고장 유형 · 원인을 가리킨다 — 새로 만들지 않는다
    assert {(e['from_id'], e['type']) for e in after['edges'] if e['to_id'] == 'skill:sop-pur-11' and e['from_labels'] == ['FailureMode']} == \
        {('fm:volumetric-loss', 'REMEDIED_BY')}
    assert {e['to_id'] for e in edges(after, 'APPROVED_BY')} == {'role:purchasing'}


def test_a_documents_own_candidate_rule_is_not_widened_into_other_candidate_rules(archive):
    plan = plan_of(archive, 'C')
    plan['candidate_rules'] = {'fm:volumetric-loss': ['rule:cand-pump']}
    after = manual_graph.desired(plan)
    assert not [e for e in edges(after, 'OUTPUTS') if e['from_id'] == 'rule:cand-pump']
    plan = plan_of(archive, 'A')
    plan['candidate_rules'] = {'fm:cooling-loss': ['rule:cand-cooling-loss', 'rule:cand-cooler']}   # 재적재: 자기 규칙은 이미 명시
    after = manual_graph.desired(plan)
    outs = [(e['from_id'], e['to_id']) for e in edges(after, 'OUTPUTS')]
    assert len(outs) == len(set(outs)) and not any(r == 'rule:cand-cooler' for r, _ in outs)



def test_prevented_by_is_accepted_and_never_joins_incident_candidate_rules(archive):
    """예방 조치(PREVENTED_BY, 2026-10-09 확정)는 검토 · 적재가 받는 세 번째 관계다. 경보 대응 후보 규칙(A075 자동 연결)에는 합류하지 않는다."""
    from procsvc import kgadmin
    assert kgadmin.FAILURE_RELATIONS == ('MITIGATED_BY', 'REMEDIED_BY', 'PREVENTED_BY')
    assert manual_knowledge.validate_link('SOP-X-1', dict(relation='PREVENTED_BY'), sops=set(), require_failure_mode=False)['relation'] == 'PREVENTED_BY'
    with pytest.raises(ValueError, match='PREVENTED_BY'):
        manual_knowledge.validate_link('SOP-X-1', dict(relation='PREVENTS'), sops=set(), require_failure_mode=False)
    assert kgadmin.validate_skill(dict(name='점검', sopId='SOP-X-01', steps=['a'], failureMode='fm:x', relation='PREVENTED_BY'), create=True)['relation'] == 'PREVENTED_BY'
    plan = plan_of(archive, 'A')
    for p in plan['procedures']:
        if p['id'] == 'SOP-FAN-11':
            p['relation'] = 'PREVENTED_BY'
    plan['knowledge']['rules'] = [r for r in plan['knowledge']['rules'] if r['table'] != 'dt:action-candidates']
    plan['candidate_rules'] = {'fm:cooling-loss': ['rule:cand-cooler']}
    after = manual_graph.desired(plan)
    joined = {e['to_id'] for e in edges(after, 'OUTPUTS') if e['from_id'] == 'rule:cand-cooler'}
    assert 'skill:sop-fan-11' not in joined and 'skill:sop-fan-12' in joined
    pv = [e for e in edges(after, 'PREVENTED_BY')]
    assert [(e['from_id'], e['to_id']) for e in pv] == [('fm:cooling-loss', 'skill:sop-fan-11')] and '_manual_document' in pv[0]['props']

@pytest.mark.parametrize('mutate, message', [
    (lambda k, l: k['evidence'][0].update(tag='XX9'), 'tag'),
    (lambda k, l: k['evidence'][0].update(window_seconds=0), 'window_seconds'),
    (lambda k, l: k['causes'][0].update(prior=1.5), 'prior'),
    (lambda k, l: k['rules'][0].update(effect='EXCLUDE'), 'effect'),
    (lambda k, l: k['rules'][0].update(table='dt:rank-actions'), '순위 정책'),
    (lambda k, l: k['rules'][1].update(outputs=[]), 'outputs'),
    (lambda k, l: k['rules'][1].update(outputs=['SOP-NOT-HERE']), '이 문서의 SOP'),
    (lambda k, l: k['rules'][2].update(tests=[]), 'TESTS'),
    (lambda k, l: k['rules'][4].update(penalizes=None), 'msr'),
    (lambda k, l: k['failure_modes'][0].update(component='cooler'), 'comp'),
    (lambda k, l: k['failure_modes'][0].update(id='FM-1'), 'id'),
    (lambda k, l: k['causes'][1].update(id='cause:cooler-fin-fouling'), 'id'),
    (lambda k, l: k['rules'][0].update(section='HM-9.9'), 'section'),
    (lambda k, l: l['SOP-COOL-11'].update(actions=[dict(action='FAN_SET', value=100)]), 'action'),
    (lambda k, l: l['SOP-COOL-14'].update(addresses=['핀 오염']), 'cause'),
])
def test_malformed_knowledge_is_rejected_before_graph_io(archive, mutate, message):
    source, prop = load(archive, 'A')
    body = fx.reviewed_body(source, prop)
    mutate(body['knowledge'], body['links'])
    with pytest.raises(ValueError, match=message):
        manual_review.validate(archive, 'hyd', body)


@pytest.mark.parametrize('mutate, message', [
    (lambda b: b['links']['SOP-COOL-11'].update(actions=[dict(action='action:set-fan', value=140)]), '0~100'),
    (lambda b: b['links']['SOP-COOL-12'].update(actions=[dict(action='action:set-load', value=50)]), '60~100'),
    (lambda b: b['links']['SOP-COOL-14'].update(actions=[dict(action='action:set-fan', value=80)]), 'control'),
    (lambda b: b['links']['SOP-COOL-14'].update(actions=[dict(action='action:purchase-request', value='C트레이딩')]), '공급사'),
    (lambda b: b['links']['SOP-COOL-14'].update(actions=[dict(action='action:new-thing', value=1)]), '없습니다'),
    (lambda b: b['knowledge']['rules'][0]['tests'].append(dict(input='in:po-amount', operator='>', value=1)), 'REQUIRES_INPUT'),
])
def test_graph_checks_reject_out_of_range_values_and_undeclared_rule_inputs(archive, mutate, message):
    source, prop = load(archive, 'A')
    body = fx.reviewed_body(source, prop)
    mutate(body)
    plan = manual_review.validate(archive, 'hyd', body)
    with pytest.raises(ValueError, match=message):
        manual_knowledge.check_graph(FakeSession(), plan, manual_graph.skill_id)


def test_desired_refuses_rules_whose_input_variables_were_not_resolved(archive):
    source, prop = load(archive, 'A')
    plan = manual_review.validate(archive, 'hyd', fx.reviewed_body(source, prop))
    with pytest.raises(ValueError, match='check_graph'):
        manual_graph.desired(plan)


def test_reviewed_body_without_knowledge_keeps_the_previous_plan_shape(archive):
    source, prop = load(archive, 'A')
    body = fx.reviewed_body(source, prop)
    body.pop('knowledge')
    for link in body['links'].values():
        link.pop('actions', None); link.pop('addresses', None)
    plan = manual_review.validate(archive, 'hyd', body)
    assert 'knowledge' not in plan and all('actions' not in p and 'addresses' not in p for p in plan['procedures'])


def test_suggested_links_are_shape_checked_in_the_proposal(archive):
    source, prop = load(archive, 'A')
    bad = copy.deepcopy(prop)
    bad['procedures'][2]['link']['relation'] = 'FIXES'
    with pytest.raises(ValueError, match='MITIGATED_BY'):
        manual_extraction.validate_proposal(source, bad)
    bad = copy.deepcopy(prop)
    bad['procedures'][2]['link']['affects'] = [dict(target='sv:ts1', sign='up')]
    with pytest.raises(ValueError):
        manual_extraction.validate_proposal(source, bad)


def test_preview_carries_the_knowledge_for_the_review_screen(archive):
    source, prop = load(archive, 'C')
    checked = manual_extraction.validate_proposal(source, prop)
    preview = manual_extraction._preview(source, checked, None, dict(instance='i', workitem='w', session_id=None, generation=0))
    assert preview['knowledge']['rules'][0]['id'] == 'rule:cand-spare-purchase'
    assert all(p.get('link') for p in preview['procedures'])


def test_segmented_extraction_merges_knowledge_and_keeps_first_proposal_of_an_id(archive):
    source, prop = load(archive, 'A')
    seg = dict(index=1, total=2, ranges=[dict(page=1, start=0, end=len(source['pages'][0]['text']))])
    seg2 = dict(seg, index=2)
    dup = copy.deepcopy(prop)
    dup['sections'], dup['procedures'], dup['page_reviews'] = [], [], []
    dup['knowledge'] = {'rules': copy.deepcopy(prop['knowledge']['rules'][:1])}
    merged = manual_segments.merge(source, [(seg, prop), (seg2, dup)])
    assert [r['id'] for r in merged['knowledge']['rules']] == [r['id'] for r in prop['knowledge']['rules']]
    assert any('rule:dx-cooling-fin' in w and '첫 제안' in w for w in merged['warnings'])
    manual_extraction.validate_proposal(source, merged)


def test_extraction_start_pins_the_catalog(monkeypatch):
    captured = {}

    class RT:
        def register_definition(self, d): captured['def'] = d
        def start_definition(self, did, ver, event, values=None, name=None):
            captured['values'] = values
            return dict(proc_inst_id='p')
    source = dict(status='READY', source_id='s', filename='a.md', media_type='text/plain', pages=[dict(page=1, text='짧은 문서')])
    monkeypatch.setattr(manual_segments, 'segments', lambda src: [])
    manual_extraction.start(RT(), source, '00000000-0000-4000-8000-000000000001', catalog={'actions': [{'id': 'action:set-fan'}]})
    assert captured['values']['ontology_catalog'] == {'actions': [{'id': 'action:set-fan'}]}


def test_owned_keys_come_from_the_journal_snapshot():
    snap = {'nodes': [{'labels': ['FailureMode'], 'props': {'id': 'fm:x'}}, {'labels': ['Skill'], 'props': {'id': 'skill:a', '_manual_document': 'd'}}]}
    assert manual_graph.owned_keys(snap) == [('FailureMode', 'fm:x'), ('Skill', 'skill:a')]
    assert manual_graph.owned_keys(None) == []
