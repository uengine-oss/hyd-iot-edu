"""PM schedules use actual existing orders; no new-order fallback for source SOPs."""
from copy import deepcopy
import pytest
from hydcommon.maintenance_plan import plan
from procsvc.work_orders import request_for_option
from entsim.state import EnterpriseState
from agentsvc import cards
from agentsvc import decide
from test_cards import DMN, FC, R, T, SKILLS, BASE
from test_pm_scoped_schedule import contract


def facts():
    row=dict(asset='HYD-02',cycle=1,pm_planned_wo='WO-PM',pm_since_h=1950,pm_total_h=11950,
             pm_interval_h=2000,pm_tolerance_pct=10,pm_crew_available=2,service_position=None,
             following_window_id='MW-FOLLOWING',following_window_at='2026-10-23T00:00:00Z',hours_at_following_window=2100)
    row['existing_pm_order']=dict(reserved_parts=[dict(part_no='P-PMP-SEAL',qty=1),dict(part_no='P-RTN-FLT',qty=1)])
    return dict(pm_planned_wo='WO-PM',pm_cycle=1,pm_limit_hours=2200,hours_at_following_window=2100,
                existing_pm_order=dict(id='WO-PM',asset='HYD-02',status='배정됨',completed_at=None),
                pm_context=dict(asset='HYD-02',records=[row],parts=[dict(part_no='P-PMP-SEAL',available=5),dict(part_no='P-RTN-FLT',available=5)]))


def skill():
    policy=contract();policy['stock_effect']='preserve';policy['anchor']['source_id']='source:pm';policy['model_anchor']['source_id']='source:pm'
    return dict(id='skill:pm13',sopId='SOP-PM-13',source_id='source:pm',kind='work_order',maintenance_policy=policy,
                actions=[dict(code='WO_RESCHEDULE',value='SOP-PM-13',kind='transaction',target='sys:cmms')])


def window():return dict(id='MW-FOLLOWING',basis='hours_at_following_window',starts_at='2026-10-23T00:00:00Z')


@pytest.mark.parametrize('change',['no_order','wrong_plan','closed','no_window','wrong_window','overdue','unknown_deadline','empty_actions'])
def test_no_fabricated_existing_order_or_window_or_effect(change):
    f=facts();s=skill();w=window()
    if change=='no_order':f['existing_pm_order']=None
    if change=='wrong_plan':f['pm_planned_wo']='WO-UNRELATED'
    if change=='closed':f['existing_pm_order']['status']='완료'
    if change=='no_window':w=None
    if change=='wrong_window':w['basis']='hours_at_next_window'
    if change=='overdue':f['hours_at_following_window']=2201
    if change=='unknown_deadline':f['pm_limit_hours']=None
    if change=='empty_actions':s['actions']=[]
    with pytest.raises(ValueError):plan(s,f,w)


def test_source_plan_request_is_exact_reschedule_and_legacy_followup_remains():
    s=skill();s['maintenancePlan']=plan(s,facts(),window())
    item=request_for_option(s)
    assert item['code']=='WO_RESCHEDULE' and item['ref']=='WO-PM'
    assert item['expected_order']==facts()['existing_pm_order']
    blank=dict(s,actions=[])
    with pytest.raises(ValueError):request_for_option(blank)
    blank.pop('source_id');blank.pop('maintenancePlan')
    assert request_for_option(blank)['source']=='process-definition-followup'


def test_following_window_missing_id_never_becomes_an_immediate_plan():
    s=skill();s['skillId']=s['id']
    assert cards.option_window([dict(applies=[s['id']],tests=[dict(variable='hours_at_following_window')])],s['id'],s,
                               dict(hours_at_following_window=dict(starts_at='2026-10-23'))) is None


def configured_state():
    state=EnterpriseState()
    c=state._s['cmms']['pm_counters']['HYD-02'];c['since_pm_h']=1000
    order=dict(id='WO-PM',asset='HYD-02',task='PM',status='배정됨',window='previous',window_id='previous',completed_at=None)
    state._s['cmms']['work_orders'].append(order);c['plan_wo']=order['id']
    row=state.pm_status('HYD-02')['facts']
    req=dict(skill='skill:reschedule-maintenance',asset='HYD-02',decision='DEC-PM',option='skill:pm13',by='test-reviewer',
             params=dict(ref=order['id'],expected_order=deepcopy(order),cycle=c['cycle'],window_id=row['following_window_id']))
    return state,req


def test_actual_memory_reschedule_changes_existing_row_only_and_replays_exactly():
    state,req=configured_state();count=len(state._s['cmms']['work_orders'])
    tx=state.execute(req)
    assert tx['ref']=='WO-PM' and tx['before']['window_id']=='previous'
    assert tx['after']['window_id']==req['params']['window_id']
    assert len(state._s['cmms']['work_orders'])==count
    assert state.execute(req)==tx
    other=deepcopy(req);other['params']['window_id']='changed'
    with pytest.raises(ValueError,match='idempotency'):state.execute(other)


@pytest.mark.parametrize('change',['unrelated_order','closed','stale','deadline','missing_window','wrong_cycle'])
def test_memory_executor_rechecks_and_preserves_existing_records_on_failure(change):
    state,req=configured_state()
    if change=='unrelated_order':state._s['cmms']['pm_counters']['HYD-02']['plan_wo']=None
    if change=='closed':state._s['cmms']['work_orders'][-1]['status']='완료'
    if change=='stale':req['params']['expected_order']['task']='changed'
    if change=='deadline':state._s['cmms']['pm_counters']['HYD-02']['since_pm_h']=3000
    if change=='missing_window':req['params']['window_id']=None
    if change=='wrong_cycle':req['params']['cycle']=999
    before=deepcopy(state._s)
    with pytest.raises(ValueError):state.execute(req)
    assert state._s==before and not state._tx


def test_failed_durable_save_rolls_back_new_pm_effect(monkeypatch):
    state,req=configured_state();before=deepcopy(state._s)
    monkeypatch.setattr(state,'_save',lambda:(_ for _ in ()).throw(OSError('disk failure')))
    with pytest.raises(OSError):state.execute(req)
    assert state._s==before and not state._done and not state._tx


def test_source_pm_empty_action_is_visible_infeasible_not_a_new_work_order():
    s=deepcopy(SKILLS['skill:mix']);s.update(source_id='source:pm',relation='PREVENTED_BY',kind='work_order',actions=[])
    rules=deepcopy(DMN)+[R('dec:action-candidates','rule:pm-source','SELECT',[T('pattern','==','PM_DUE')],['skill:mix'])]
    result=cards.evaluate(rules,{'skill:mix':s},dict(BASE,pattern='PM_DUE'),FC,[],[],{},evaluation_mode='execution')
    assert result['options'] and result['recommended'] is None
    assert any(v['rule']=='execution:pm-plan' for v in result['options'][0]['violations'])


def test_source_pm_explicit_stop_and_create_has_immediate_window_without_guessing_future_id():
    s=deepcopy(SKILLS['skill:mix']);s.update(source_id='source:pm',maintenance_policy=skill()['maintenance_policy'],relation='PREVENTED_BY',kind='control',
        actions=[dict(code='STOP',kind='command'),dict(code='WO_CREATE',kind='transaction',value='SOP-PM-12')])
    s['maintenance_policy']['stock_effect']='reserve'
    rules=deepcopy(DMN)+[R('dec:action-candidates','rule:pm-source','SELECT',[T('pattern','==','PM_DUE')],['skill:mix'])]
    result=cards.evaluate(rules,{'skill:mix':s},dict(BASE,pattern='PM_DUE',pm_context=facts()['pm_context']),FC,[],[],{},evaluation_mode='execution')
    option=result['options'][0]
    assert option['maintenancePlan']['code']=='WO_CREATE' and option['window']['immediate'] is True
    assert not any(v['rule']=='execution:pm-plan' for v in option['violations'])


@pytest.mark.parametrize('records,expected',[
    ([dict(asset='HYD-02',status='RUNNING')],True),
    ([dict(asset='HYD-02',status='DONE')],False),
    ([dict(asset='HYD-01',status='RUNNING')],False),([],False),(None,None),([dict(asset='HYD-02')],None)])
def test_production_running_uses_actual_current_asset_mes_records(monkeypatch,records,expected):
    monkeypatch.setattr(decide.mcp_ent,'fetch',lambda *args:dict(records=records,facts={},as_of='2026-10-12T00:00:00Z'))
    facts,provenance=decide.gather_facts([dict(variable='production_running',source='sys:mes',sourceKind='System',
                                             name='생산 중',sourceName='MES')],'HYD-02',{},None)
    assert facts['production_running'] is expected
    if expected is None:assert provenance[0].get('error')
