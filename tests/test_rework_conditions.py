"""Changed cross-path condition inputs require fresh review and boundary scope."""
from copy import deepcopy
from datetime import timedelta
import pytest
from procsvc import engine, instances
from test_engine import NOW
from test_process_end_barrier import setup
from test_rework_runtime import latest, request


def definition():
    keys=['x','review','old_result','new_result','late_result','hold']
    return dict(processDefinitionId='condition-recheck',processDefinitionName='Condition recheck',version='1',
        roles=[dict(name='Reviewer',endpoint='role:operator')],
        data=[dict(name=k,type='Text') for k in keys],
        forms={k:dict(fields_json=[dict(key=k,type='text',text=k,required=False)]) for k in keys},
        activities=[dict(id=a,type='userTask',role='Reviewer',tool='formHandler:'+key,outputData=[key])
            for a,key in [('a','x'),('b','review'),('c','old_result'),('d','new_result'),('late','late_result'),('hold','hold')]],
        events=[dict(id='s',type='startEvent'),dict(id='e',type='endEvent'),
            dict(id='deadline',type='boundaryEvent',attachedTo='b',eventDefinition='timer',timer='PT5M')],
        gateways=[dict(id='g',type='exclusiveGateway')],
        sequences=[dict(id=src+'-'+dst,source=src,target=dst) for src,dst in
            [('s','a'),('s','b'),('s','hold'),('a','e'),('b','g'),('g','d'),('c','e'),('d','e'),('deadline','late'),('late','e'),('hold','e')]]
            +[dict(id='g-c',source='g',target='c',condition='x == "old"')])


def prepared():
    rt,pid,old=setup(definition())
    rt.submit(old['a']['id'],{'x':'old'},now=NOW)
    rt.submit(old['b']['id'],{'review':'reviewed old'},now=NOW)
    return rt,pid,old


def test_cross_path_gateway_reopens_actual_review_after_fresh_producer():
    rt,pid,old=prepared(); before=deepcopy(rt.repo.get_workitem(old['b']['id']))
    plan=rt.preview_rework(pid,old['a']['id'])
    assert plan['execution_available'],plan['blockers']
    assert 'b' in plan['affected_nodes']
    request(rt,pid,old['a']['id'])
    assert latest(rt,pid,'b')['status']=='TODO'
    assert latest(rt,pid,'c')['status']=='TODO'
    rt.submit(latest(rt,pid,'a')['id'],{'x':'new'},now=NOW+timedelta(seconds=3))
    b=latest(rt,pid,'b'); assert b['status']=='IN_PROGRESS'
    assert b['reference_ids']==[latest(rt,pid,'a')['id']]
    timer=latest(rt,pid,'deadline')
    assert timer['generation']==1 and timer['due_date']==engine.now_iso(NOW+timedelta(seconds=3+300/rt.time_scale))
    assert '[ConditionData]' in b['query'] and 'new' in b['query']
    rt=instances.InstanceRuntime(rt.repo,rt.defn,instances.Hooks())
    rt.submit(b['id'],{'review':'reviewed new'},now=NOW+timedelta(seconds=4))
    assert latest(rt,pid,'d')['status']=='IN_PROGRESS'
    assert latest(rt,pid,'c')['status']=='TODO'
    assert latest(rt,pid,'deadline')['status']=='CANCELLED'
    assert rt.repo.get_workitem(old['b']['id'])==before
    rt.submit(old['hold']['id'],{'hold':'done'},now=NOW)
    rt.submit(latest(rt,pid,'d')['id'],{'new_result':'new branch'},now=NOW)
    assert rt.repo.get_instance(pid)['status']=='COMPLETED'


def test_missing_new_condition_input_cannot_choose_default_from_old_or_seed():
    rt,pid,old=prepared(); request(rt,pid,old['a']['id'])
    rt.submit(latest(rt,pid,'a')['id'],{},now=NOW)
    rt.submit(old['hold']['id'],{'hold':'done'},now=NOW)
    assert latest(rt,pid,'b')['status']=='TODO'
    assert latest(rt,pid,'d')['status']=='TODO'
    assert rt.repo.get_instance(pid)['status']=='RUNNING'


def test_rewriting_waiting_recheck_retargets_condition_producer():
    rt,pid,old=prepared(); request(rt,pid,old['a']['id'])
    previous=latest(rt,pid,'a'); request(rt,pid,previous['id'])
    with pytest.raises(ValueError): rt.submit(previous['id'],{'x':'stale'},now=NOW)
    fresh=latest(rt,pid,'a'); rt.submit(fresh['id'],{'x':'old'},now=NOW)
    b=latest(rt,pid,'b')
    assert b['generation']==2 and b['status']=='IN_PROGRESS' and b['reference_ids']==[fresh['id']]
    rt.submit(b['id'],{'review':'same branch reconsidered'},now=NOW)
    assert latest(rt,pid,'c')['status']=='IN_PROGRESS' and latest(rt,pid,'d')['status']=='TODO'


def test_new_boundary_timer_is_tied_to_new_admission_and_old_timer_cannot_win():
    rt,pid,old=prepared(); old_timer=latest(rt,pid,'deadline')
    request(rt,pid,old['a']['id'])
    rt.submit(latest(rt,pid,'a')['id'],{'x':'new'},now=NOW+timedelta(seconds=10))
    assert rt.fire_timeouts(now=NOW+timedelta(seconds=300/rt.time_scale+1))==[]
    assert len(rt.fire_timeouts(now=NOW+timedelta(seconds=300/rt.time_scale+11)))==1
    assert latest(rt,pid,'b')['status']=='CANCELLED' and latest(rt,pid,'late')['status']=='IN_PROGRESS'
    assert rt.repo.get_workitem(old_timer['id'])['status']=='CANCELLED'
    assert latest(rt,pid,'d')['status']=='TODO'


def test_expired_boundary_review_can_be_reconsidered_from_proven_arrival():
    rt,pid,old=setup(definition()); rt.submit(old['a']['id'],{'x':'old'},now=NOW)
    rt.fire_timeouts(now=NOW+timedelta(seconds=301))
    assert latest(rt,pid,'b')['status']=='CANCELLED'
    request(rt,pid,old['a']['id'],now=NOW+timedelta(seconds=302))
    rt.submit(latest(rt,pid,'a')['id'],{'x':'new'},now=NOW+timedelta(seconds=303))
    assert latest(rt,pid,'b')['status']=='IN_PROGRESS'
    assert latest(rt,pid,'late')['status']=='TODO'
    assert latest(rt,pid,'deadline')['generation']==1
    assert rt.repo.get_workitem(old['deadline']['id'])['status']=='DONE'


def test_gateway_without_prior_work_arrival_is_explicitly_unavailable():
    raw=definition(); raw['sequences']=[s for s in raw['sequences'] if s['id'] not in ('s-b','b-g')]
    raw['sequences'].append(dict(id='s-g',source='s',target='g'))
    rt,pid,old=setup(raw); rt.submit(old['a']['id'],{'x':'old'},now=NOW)
    result=rt.preview_rework(pid,old['a']['id'])
    assert not result['execution_available']
    assert any(b['code']=='condition_replay_requires_arrival' for b in result['blockers'])


def test_missing_review_output_is_pending_instead_of_choosing_default():
    raw=definition(); raw['sequences'][-1]['condition']='x == "new" and review == "yes"'
    rt,pid,old=setup(raw)
    rt.submit(old['a']['id'],{'x':'old'},now=NOW)
    rt.submit(old['b']['id'],{'review':'old review'},now=NOW)
    request(rt,pid,old['a']['id'])
    rt.submit(latest(rt,pid,'a')['id'],{'x':'new'},now=NOW)
    b=latest(rt,pid,'b'); rt.submit(b['id'],{},now=NOW)
    assert latest(rt,pid,'b')['status']=='PENDING'
    assert 'CONDITION_INPUT_UNAVAILABLE' in latest(rt,pid,'b')['log']
    assert latest(rt,pid,'c')['status']==latest(rt,pid,'d')['status']=='TODO'
    rt.submit(b['id'],{'review':'yes'},now=NOW)
    assert latest(rt,pid,'c')['status']=='IN_PROGRESS'


def test_legacy_cancelled_review_without_arrival_evidence_is_not_reopened():
    rt,pid,old=setup(definition()); rt.submit(old['a']['id'],{'x':'old'},now=NOW)
    rt.fire_timeouts(now=NOW+timedelta(seconds=301))
    inst=rt.repo.get_instance(pid); inst['flow_state'].pop('activity_arrivals'); rt.repo.update_instance(inst)
    plan=rt.preview_rework(pid,old['a']['id'])
    assert any(b['code']=='dependency_control_arrival_unavailable' and b['activity']=='b' for b in plan['blockers'])


def test_unused_boundary_condition_does_not_block_normal_review_completion():
    raw=definition()
    next(s for s in raw['sequences'] if s['id']=='deadline-late')['condition']='missing == "yes"'
    rt,pid,old=setup(raw); rt.submit(old['a']['id'],{'x':'old'},now=NOW)
    rt.submit(old['b']['id'],{'review':'old'},now=NOW)
    request(rt,pid,old['a']['id']); rt.submit(latest(rt,pid,'a')['id'],{'x':'new'},now=NOW)
    rt.submit(latest(rt,pid,'b')['id'],{'review':'normal'},now=NOW)
    assert latest(rt,pid,'b')['status']=='DONE' and latest(rt,pid,'d')['status']=='IN_PROGRESS'
