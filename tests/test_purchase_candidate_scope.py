"""Business purchasing cannot become a plant remedy because it shares an FM."""
from copy import deepcopy

import pytest

from agentsvc import cards, decide, forecasting
from dmn_mcp.tools import DmnTools, enveloped
from test_cards import BASE, DMN, FC, SKILLS, R, T


def purchase():
    return dict(skillId='skill:purchase', sopId='SOP-PUR-11', name='공급사 발주', kind='work_order',
                relation='REMEDIED_BY', approver=dict(id='role:purchasing', name='구매 담당', level=1),
                addresses=[], steps=[dict(id='step:purchase', order=1, text='승인된 구매요청을 발행한다')], actions=[dict(id='action:purchase-request', code='PR_CREATE',
                                                     kind='transaction', value='sup:a')])


def fixture_data():
    rules = deepcopy(DMN)
    rules.append(R('dec:action-candidates', 'rule:purchase', 'SELECT',
                   [T('pattern', '==', 'SPARE_BELOW_MIN')], ['skill:purchase']))
    skills = deepcopy(SKILLS)
    skills['skill:purchase'] = purchase()
    facts = dict(BASE, pattern='SPARE_BELOW_MIN', spare_gap=-1, need_qty=6, need_by_days=6,
                 spare_quotes={'sup:a':dict(price=2, lead_d=1, fail_rate=0.01)})
    return rules, skills, facts


def test_pure_selected_purchase_cards_never_include_shared_failure_mode_plant_cards():
    rules, skills, facts = fixture_data()
    before = deepcopy((rules, skills, facts))
    result = cards.evaluate(rules, skills, facts, FC, [], [], {'sup:a':dict(avl=True)})
    assert {o['id'] for o in result['options']} == {'skill:purchase'}
    assert (rules, skills, facts) == before


def test_no_purchase_skill_does_not_return_plant_cards_even_if_the_rule_fires():
    result = cards.evaluate(DMN, SKILLS, dict(BASE, pattern='SPARE_BELOW_MIN'), FC, [], [], {})
    assert result['options'] == [] and result['recommended'] is None


def test_mixed_or_command_purchase_skill_is_not_a_purchase_execution():
    p = purchase()
    p['actions'].append(dict(code='LOAD_SET', kind='command', value=70))
    assert cards.scoped_skills('SPARE_BELOW_MIN', {p['skillId']:p}) == {}
    p = purchase()
    p['kind'] = 'control'
    assert cards.scoped_skills('SPARE_BELOW_MIN', {p['skillId']:p}) == {}
    assert cards.scoped_skills('COOLER_DEGRADATION', SKILLS) is SKILLS


def test_pm_scope_keeps_only_prevention_including_real_control_alternatives():
    skills = deepcopy(SKILLS)
    skills['skill:prevent'] = deepcopy(SKILLS['skill:mix'])
    skills['skill:prevent']['skillId'] = 'skill:prevent'
    skills['skill:prevent']['relation'] = 'PREVENTED_BY'
    selected = cards.scoped_skills('PM_DUE', skills)
    assert set(selected) == {'skill:prevent'} and selected['skill:prevent']['kind'] == 'control'


def test_pm_missing_prevention_is_not_submitted_as_a_failure_remedy(pipeline):
    tools, _, _, facts, forecasts, submitted = pipeline
    facts['pattern'] = 'PM_DUE'
    result = enveloped(tools.submit_decision)('HYD-02','PM_DUE','cause:fouling','fm:cool','INC-B')
    assert result['result'] == 'error' and '예방 정비 후보 지식이 없습니다' in result['message']
    assert submitted == [] and forecasts == []


@pytest.fixture
def pipeline(monkeypatch):
    rules, skills, facts = fixture_data()

    class KG:
        def dmn(self): return rules
        def inputs(self): return []
        def skills(self, ids): return [s for sid,s in skills.items() if sid in ids]
        def tradeoffs(self, ids): return []
        def precedents(self, fm): return []
        def suppliers(self): return {'sup:a':dict(avl=True)}
        def roles(self): return []
        def t1_causes(self, *args): raise AssertionError('business alarms must not switch to sensor diagnosis')

    monkeypatch.setattr(decide, 'gather_facts', lambda *a: (deepcopy(facts), []))
    forecast_inputs = []
    def forecasts(kg, asset, selected):
        forecast_inputs.append(set(selected))
        return {sid:deepcopy(FC['skill:mix']) for sid in selected}, {sid:dict(error=None) for sid in selected}
    monkeypatch.setattr(forecasting, 'candidates', forecasts)
    submitted = []
    monkeypatch.setattr(decide, 'submit', lambda payload: submitted.append(payload) or {'id':payload['id']})
    tools = DmnTools(kg=KG(), tsdb=object())
    monkeypatch.setattr(tools, 'business_causes', lambda *a: {'causes':[dict(causeId='cause:fouling', cause='마모',
                                                                         failureModeId='fm:cool', failureMode='손실')]})
    return tools, rules, skills, facts, forecast_inputs, submitted


@pytest.mark.parametrize('submit', [False, True])
def test_pipeline_refuses_missing_purchase_knowledge_and_keeps_failure_trace(pipeline, submit):
    tools, _, skills, _, forecast_inputs, submitted = pipeline
    skills.pop('skill:purchase')
    fn = tools.submit_decision if submit else tools.evaluate_cards
    args = ('HYD-03', 'SPARE_BELOW_MIN', 'cause:fouling', 'fm:cool') + (('INC-C',) if submit else ())
    result = enveloped(fn)(*args)
    assert result['result'] == 'error' and result['error_kind'] == 'INVALID'
    assert '구매 후보 지식이 없습니다' in result['message']
    assert submitted == [] and forecast_inputs == []
    record = tools.registry.all()[-1]
    assert record['status'] == 'FAILED' and record['steps'][-1]['status'] == 'FAILED'


def test_pipeline_missing_business_facts_is_an_error_not_a_guessed_order(pipeline):
    tools, _, _, facts, _, submitted = pipeline
    facts['need_qty'] = None
    result = enveloped(tools.evaluate_cards)('HYD-03','SPARE_BELOW_MIN','cause:fouling','fm:cool')
    assert result['result'] == 'error' and '실제 업무 사실' in result['message'] and submitted == []


@pytest.mark.parametrize('submit', [False, True])
def test_registered_purchase_skill_still_requires_a_fired_candidate_rule(pipeline, submit):
    tools, rules, _, _, _, submitted = pipeline
    next(r for r in rules if r['rule'] == 'rule:purchase')['tests'][0]['value'] = 'OTHER_PATTERN'
    fn = tools.submit_decision if submit else tools.evaluate_cards
    args = ('HYD-03','SPARE_BELOW_MIN','cause:fouling','fm:cool') + (('INC-C',) if submit else ())
    result = enveloped(fn)(*args)
    assert result['result'] == 'error' and '발화한 구매 후보가 없습니다' in result['message']
    assert submitted == []


@pytest.mark.parametrize('submit', [False, True])
def test_valid_purchase_candidate_scope_is_kept_through_submission(pipeline, submit):
    tools, _, _, _, forecast_inputs, submitted = pipeline
    fn = tools.submit_decision if submit else tools.evaluate_cards
    args = ('HYD-03','SPARE_BELOW_MIN','cause:fouling','fm:cool') + (('INC-C',) if submit else ())
    result = enveloped(fn)(*args)
    assert result['result'] == 'ok', result
    record = tools.registry.all()[-1]
    assert {o['id'] for o in record['result']['options']} == {'skill:purchase'}
    assert forecast_inputs == [{'skill:purchase'}]
    assert len(submitted) == int(submit)
    if submit:
        assert {o['id'] for o in submitted[0]['options']} == {'skill:purchase'}


@pytest.mark.parametrize('pattern', ['SPARE_BELOW_MIN','PM_DUE'])
def test_explicit_business_pattern_never_admits_a_sensor_only_cause(pipeline, monkeypatch, pattern):
    tools, _, _, _, _, _ = pipeline
    monkeypatch.setattr(tools.kg, 't1_causes', lambda *a: [dict(causeId='cause:sensor', failureModeId='fm:sensor')])
    with pytest.raises(ValueError, match='업무 근거'):
        tools._diagnosed_cause('HYD-03', pattern, 'cause:sensor','fm:sensor')
