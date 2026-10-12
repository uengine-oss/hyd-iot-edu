"""Declared rule comparisons cannot be consumed as actual maintenance approval."""
from copy import deepcopy
import pytest
from agentsvc import cards
from procsvc import decisions, main, work_orders, effect_compensation
from entsim import state
from test_cards import BASE, DMN, SKILLS, FC, R, T
from test_decisions_process import dec


def pm(mode):
    candidate=deepcopy(SKILLS['skill:mix'])
    candidate.update(relation='PREVENTED_BY',kind='work_order',actions=[dict(code='WO_CREATE',kind='transaction')])
    rules=deepcopy(DMN)+[R('dec:action-candidates','rule:pm','SELECT',[T('pattern','==','PM_DUE')],['skill:mix'])]
    return cards.evaluate(rules,{'skill:mix':candidate},dict(BASE,pattern='PM_DUE'),FC,[],[],{},evaluation_mode=mode)


def test_missing_source_id_cannot_skip_actual_pm_policy_check():
    result=pm('execution')
    assert result['execution_checked'] is True and result['recommended'] is None
    assert any(v['rule']=='execution:pm-plan' for v in result['options'][0]['violations'])


def test_pure_rule_comparison_marks_every_option_not_execution_checked():
    result=pm('rule_analysis')
    assert result['evaluation_mode']=='rule_analysis' and result['execution_checked'] is False
    assert all(o['execution_checked'] is False for o in result['options'])
    assert '실제 승인' in result['execution_notice']


@pytest.mark.parametrize('location',['decision','option'])
def test_persisted_analysis_cannot_approve_even_forged_feasible(location):
    decision=dec();option=decision['options'][0]
    target=decision if location=='decision' else option
    target.update(evaluation_mode='rule_analysis',execution_checked=False)
    decision=decisions.new(decision);before=deepcopy(decision)
    assert decisions.may_approve(decision,option,'role:plant-mgr') is False
    with pytest.raises(ValueError):decisions.approve(decision,option['id'],'review','role:plant-mgr')
    assert decision==before


@pytest.mark.parametrize('origin',['origin','scenario','facts'])
def test_metadata_removed_pm_cannot_execute_or_approve(origin,monkeypatch):
    decision=dec();option=decision['options'][0];decision[origin]=dict(pattern='PM_DUE')
    decision=decisions.new(decision)
    with pytest.raises(ValueError):decisions.approve(decision,option['id'],'review','role:plant-mgr')
    decision['chosen']=option['id'];calls=[]
    monkeypatch.setattr(main.urllib.request,'urlopen',lambda *a,**k:calls.append(a))
    with pytest.raises(ValueError):main.exec_skill(decision,dict(skill=option['id'],code='WO_CREATE'))
    assert not calls


def test_analysis_option_cannot_create_work_order_request():
    with pytest.raises(ValueError):work_orders.request_for_option(pm('rule_analysis')['options'][0])


def test_original_inverse_registry_and_additive_real_scoped_registry_agree():
    assert state.INVERSE_OF==effect_compensation.INVERSE_OF
    assert state.C2_INVERSE_OF==effect_compensation.C2_INVERSE_OF
    assert state.ALL_INVERSE_OF==effect_compensation.ALL_INVERSE_OF
    assert state.ALL_INVERSE_OF['skill:schedule-maintenance-scoped']=='skill:cancel-maintenance-scoped'


@pytest.mark.parametrize('metadata',[
    dict(evaluation_mode='garbage',execution_checked=True),
    dict(evaluation_mode='structural',execution_checked=True),
    dict(evaluation_mode='execution',execution_checked='true'),
    dict(evaluation_mode='execution',execution_checked=1),
    dict(evaluation_mode='execution',execution_checked=0),
    dict(evaluation_mode=None,execution_checked=None),
    dict(evaluation_mode='execution'),dict(execution_checked=True)])
@pytest.mark.parametrize('location',['decision','option'])
def test_explicit_malformed_execution_metadata_never_means_legacy(location,metadata):
    decision=dec();option=decision['options'][0]
    (decision if location=='decision' else option).update(metadata)
    decision=decisions.new(decision)
    assert decisions.may_approve(decision,option,'role:plant-mgr') is False
    with pytest.raises(ValueError):decisions.approve(decision,option['id'],'review','role:plant-mgr')
