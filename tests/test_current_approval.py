from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from agentsvc import approval, cards, decide, forecasting
from test_cards import BASE, DMN, SKILLS, FC, TRADE, R, T
from test_forecast_model import snapshot
from plantsim import thermal
from hydcommon.forecast import predict


@pytest.fixture
def context(monkeypatch):
    state = dict(rules=deepcopy(DMN), skills=deepcopy(SKILLS), forecasts=deepcopy(FC), facts=dict(BASE, pattern='COOLER_DEGRADATION'))
    kg = SimpleNamespace(dmn=lambda:state['rules'], inputs=lambda:[], skills=lambda ids:list(state['skills'].values()),
         forecasts=lambda cause:state['forecasts'], suppliers=lambda:{}, tradeoffs=lambda ids:TRADE, precedents=lambda failure:[],
         roles=lambda:[{'id':'role:x','level':2},{'id':'role:boss','level':3}])
    # Isolate policy/rule tests from IO. The dynamic provider has dedicated tests.
    contexts = {sid: predict(snapshot(thermal.UnitState()), [], 900) for sid in state['skills']}
    monkeypatch.setattr(forecasting, 'candidates', lambda *args:(state['forecasts'], contexts))
    result = cards.evaluate(state['rules'], state['skills'], state['facts'], state['forecasts'], TRADE, [], {}, contexts)
    d = dict(id='approval-test', asset='HYD-01', facts=deepcopy(state['facts']), options=deepcopy(result['options']))
    def gather(inputs, asset, known, tsdb, strict=False):
        assert strict is True
        return deepcopy(state['facts']), []
    monkeypatch.setattr(decide, 'gather_facts', gather)
    return state, kg, d


def assess(context):
    _, kg, d = context
    return approval.assess(kg, None, d, 'skill:mix', 'role:x')


def test_unchanged_current_choice_allowed(context):
    result = assess(context)
    assert result['allowed'] and result['policy_sha256'] and result['checked_at']


def test_bsc_change_requires_new_review_even_with_same_actions(context):
    state, kg, decision = context
    changed = deepcopy(TRADE)
    changed[1]['weight'] = 2
    kg.tradeoffs = lambda ids:changed
    result = assess(context)
    assert not result['allowed']
    assert result['current_option']['actions'] == next(o for o in decision['options'] if o['id']=='skill:mix')['actions']
    assert any('rankingEvidence' in r for r in result['reasons'])


@pytest.mark.parametrize('physical', [True, False])
def test_ranking_fact_mapping_is_included_in_consent(context, monkeypatch, physical):
    import json
    from test_physical_facts import INPUT
    from agentsvc.tools.physical import binding
    state, kg, decision = context
    state['rules'][-1]['rankingPolicy'] = json.dumps({'version':1,'inputs':{'x':'db_new'},
        'components':{'business':'x'},'tieBreak':'lower_approver'})
    state['facts']['db_new'] = '2.125'
    provenance = [{'variable':'db_new','binding':binding(INPUT)}] if physical else []
    monkeypatch.setattr(decide, 'gather_facts',lambda *a, **kw:(deepcopy(state['facts']),deepcopy(provenance)))
    data = approval.current_options(kg,None,decision,'skill:mix')
    decision.update(options=[data['current']],facts=data['facts'],provenance=data['provenance'])
    assert assess(context)['allowed']
    state['facts']['db_new'] = '2.500'
    result = assess(context)
    assert not result['allowed'] and any('db_new' in r for r in result['reasons'])


@pytest.mark.parametrize('change', ['unchanged', 'value', 'column', 'name', 'missing'])
def test_physical_consent_rereads_value_and_binding(context, monkeypatch, change):
    from test_physical_facts import INPUT
    from agentsvc.tools.physical import binding
    state, kg, decision = context
    state['rules'].append(R('dec:compliance', 'rule:physical', 'EXCLUDE', [T('db_new', '<', 1)]))
    state['facts']['db_new'] = '2.125'
    decision['facts']['db_new'] = '2.125'
    before = dict(variable='db_new', binding=binding(INPUT), value='2.125')
    decision['provenance'] = [deepcopy(before)]
    rows = [deepcopy(before)]
    monkeypatch.setattr(decide, 'gather_facts', lambda *a, **kw:(deepcopy(state['facts']), deepcopy(rows)))
    # New rule is included in the card actually reviewed by the person.
    decision['options'] = [assess(context)['current_option']]
    if change == 'value':
        state['facts']['db_new'] = '2.000'  # still feasible but different consent context
    elif change in ('column', 'name'):
        rows[0]['binding'][change] = 'changed'
    elif change == 'missing':
        state['facts']['db_new'] = None
    result = assess(context)
    assert result['allowed'] is (change == 'unchanged')
    if change != 'unchanged':
        assert any('db_new' in reason for reason in result['reasons'])


def test_changed_plc_mode_is_not_approved_from_old_feasible_card(context):
    state, _, d = context
    state['facts']['plc_mode'] = 'REMOTE_MANUAL'
    assert next(o for o in d['options'] if o['id']=='skill:mix')['feasible']
    result = assess(context)
    assert not result['allowed'] and result['current_option']['feasible'] is False


def test_missing_plc_mode_does_not_mean_exclusion_rule_is_safe(context):
    context[0]['facts']['plc_mode'] = None
    result = assess(context)
    assert not result['allowed'] and any('plc_mode' in r['variables'] for r in result['unknown'])


def test_known_false_other_condition_does_not_require_irrelevant_unknown(context):
    context[0]['rules'].append(R('dec:compliance','rule:irrelevant','EXCLUDE',
                               [T('skill_kind','==','work_order'),T('nonexistent','==',True)]))
    result = assess(context)
    assert not result['unknown']
    assert any('policy_sha256' in reason for reason in result['reasons'])
    context[2]['options'] = [result['current_option']]
    assert assess(context)['allowed']


def test_changed_policy_threshold_requires_review_even_before_it_fires(context):
    state, _, _ = context
    hard = next(r for r in state['rules'] if r['rule']=='rule:hard')
    hard['tests'][0]['value'] = 64
    result = assess(context)
    assert result['current_option']['feasible']
    assert not result['allowed'] and any('policy_sha256' in r for r in result['reasons'])


def test_unknown_warning_requires_a_new_visible_card_before_consent(context):
    state, _, d = context
    state['rules'].append(R('dec:compliance','rule:unknown-warning','WARN',[T('forecast_other','<',10)]))
    result = assess(context)
    assert not result['allowed'] and any('warnings' in r for r in result['reasons'])
    warning = next(w for w in result['current_option']['warnings'] if w['rule']=='rule:unknown-warning')
    assert warning['unknown'] == ['forecast_other'] and '확인되지 않은' in warning['annotation']
    # Simulate a separately regenerated card presented to the human. This does
    # not invent the missing forecast or convert an EXCLUDE into a warning.
    d['options'] = [result['current_option']]
    current = assess(context)
    assert current['allowed'] and current['unknown'][0]['effect'] == 'WARN'


@pytest.mark.parametrize('change', [
    lambda state: state['skills']['skill:mix']['actions'][0].update(value=999),
    lambda state: state['skills']['skill:mix']['steps'].append({'id':'unreviewed-step'}),
    lambda state: state['skills']['skill:mix']['approver'].update(id='role:boss',level=3),
    lambda state: state['forecasts']['skill:mix']['sv:ts1'].update(value=58),
])
def test_changed_consent_content_requires_new_review(context, change):
    change(context[0])
    assert not assess(context)['allowed']


def test_current_policy_removes_selected_candidate(context):
    context[0]['rules'][0]['outputs'].remove('skill:mix')
    result = assess(context)
    assert not result['allowed'] and result['current_option'] is None


def test_business_fact_change_is_visible_and_requires_review(context):
    state, _, d = context
    d['facts']['order_due_h'] = 24
    state['facts']['order_due_h'] = 2
    result = assess(context)
    assert not result['allowed'] and any('order_due_h' in r for r in result['reasons'])


def test_time_derived_business_fact_compares_its_source_record_not_the_elapsed_hours(context, monkeypatch):
    """A086: hours until the MES due date keep falling while the due date is unchanged. The consent compares the due date
    (provenance anchor); elapsed time reaches the decision through the re-evaluated rules. A moved due date is refused."""
    state, _, d = context
    due = '2026-10-07T03:00:00+00:00'
    d['facts']['order_due_h'] = 6.0
    d['provenance'] = [{'variable': 'order_due_h', 'anchor': due}]
    current = {'anchor': due}
    def gather(inputs, asset, known, tsdb, strict=False):
        return dict(deepcopy(state['facts']), order_due_h=5.97), [{'variable': 'order_due_h', **current}]
    monkeypatch.setattr(decide, 'gather_facts', gather)
    assert assess(context)['allowed']                                    # 2 minutes later, same due date
    current['anchor'] = '2026-10-08T09:00:00+00:00'                      # MES moved the due date
    result = assess(context)
    assert not result['allowed'] and any('order_due_h' in r for r in result['reasons'])
    current.pop('anchor')                                                # the source stopped giving the due date
    result = assess(context)
    assert not result['allowed'] and any('order_due_h' in r for r in result['reasons'])


def test_current_roles_are_checked(context):
    _, kg, d = context
    result = approval.assess(kg,None,d,'skill:mix','role:removed')
    assert not result['allowed'] and any('승인 권한' in r for r in result['reasons'])


@pytest.mark.parametrize('age',[None,60,-30])
def test_strict_source_collection_does_not_treat_stale_sensor_as_current(age):
    inputs=[dict(variable='ts1',source='sen:ts1',sourceKind='Sensor',name='oil',sourceName='sensor',tag='TS1')]
    tsdb=SimpleNamespace(latest=lambda *args:(48,age))
    facts, provenance = decide.gather_facts(inputs,'HYD-01',{},tsdb,strict=True)
    assert facts['ts1'] is None and provenance[0].get('error')


def test_strict_collection_rejects_stale_plant_status(monkeypatch):
    old=(datetime.now(timezone.utc)-timedelta(seconds=60)).isoformat()
    monkeypatch.setattr(decide,'_get_json',lambda *args,**kwargs:{'mode':'REMOTE_AUTO','t':old})
    inputs=[dict(variable='plc_mode',source='sys:scada',sourceKind='System',name='mode',sourceName='PLC')]
    facts, provenance=decide.gather_facts(inputs,'HYD-01',{},None,strict=True)
    assert facts['plc_mode'] is None and provenance[0].get('error')


def test_missing_cmms_readiness_is_unknown_not_implicitly_ready(monkeypatch):
    monkeypatch.setattr(decide.mcp_ent,'fetch',lambda *args:{'facts':{}})
    inputs=[dict(variable='standby_ready',source='sys:cmms',sourceKind='System',name='standby',sourceName='CMMS')]
    facts,_=decide.gather_facts(inputs,'HYD-01',{},None)
    assert facts['standby_ready'] is None


@pytest.mark.parametrize('value', [True, False, None, 'false'])
def test_cmms_readiness_uses_actual_boolean_only(monkeypatch, value):
    monkeypatch.setattr(decide.mcp_ent,'fetch',lambda *args:{'facts':{'standby_ready':value}})
    inputs=[dict(variable='standby_ready',source='sys:cmms',sourceKind='System',name='standby',sourceName='CMMS')]
    facts,_=decide.gather_facts(inputs,'HYD-01',{},None,strict=True)
    assert facts['standby_ready'] is (value if type(value) is bool else None)


def test_missing_qms_quantity_is_not_zero_claim(monkeypatch):
    monkeypatch.setattr(decide.mcp_ent,'fetch',lambda *args:{'facts':{}})
    inputs=[dict(variable='hot_lot_claim',source='sys:qms',sourceKind='System',name='claim',sourceName='QMS')]
    facts,_=decide.gather_facts(inputs,'HYD-01',{},None,strict=True)
    assert facts['hot_lot_claim'] is None
