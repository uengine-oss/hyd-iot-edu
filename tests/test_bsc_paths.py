from copy import deepcopy
import json

from agentsvc import cards
from test_cards import BASE, DMN, FC, SKILLS
import pytest


def condition(expression='x > 10', source='fact', variable='new_fact'):
    return {'version':1,'description':'explicit condition',
            'inputs':{'x':{'source':source,'variable':variable}},'expression':expression}


def path(key, strength='high', policy=None, text=None):
    return dict(skill='skill:fan',measure='msr:test',name='test measure',direction='UP',dir=1,
        good=True,owner='team',owners=['team'],weight={'high':1,'medium':0.6,'low':0.3}[strength],
        conditional=bool(text or policy),conds=[text or 'explicit condition'] if text or policy else [],
        nodes=['skill:fan',key,'msr:test'], edges=[
            {'key':'affects:'+key,'source':'skill:fan','target':key,'type':'AFFECTS','sign':1},
            {'key':'influence:'+key,'source':key,'target':'msr:test','type':'INFLUENCES','sign':1,
             'strength':strength,'condition':text or ('explicit condition' if policy else None),
             'conditionPolicy':json.dumps(policy) if policy else None}])


def evaluate(paths, facts=None):
    result=cards.evaluate(DMN,SKILLS,dict(BASE,**(facts or {})),FC,paths,[],{})
    return next(o for o in result['options'] if o['id']=='skill:fan')


def test_false_strong_path_does_not_replace_true_weaker_path():
    rows=[path('weak','low'),path('strong',policy=condition())]
    option=evaluate(rows,{'new_fact':0})
    assert option['scoreParts']['bsc']==0.3
    assert sorted(p['status'] for p in option['tradeoffEvaluation'])==['FALSE','TRUE']


def test_unknown_path_is_explicit_and_does_not_double_count_confirmed_effect():
    option=evaluate([path('known','low'),path('unknown',text='unresolved prose')])
    assert option['scoreParts']['bsc']==0.65  # .3 confirmed + .5 * (.7 incremental estimate)
    assert any(p['status']=='UNKNOWN' for p in option['tradeoffEvaluation'])
    assert option['gains'][1]['weight']==0.7


def test_true_condition_uses_full_weight_and_preserves_all_supporting_paths():
    option=evaluate([path('weak','low'),path('strong',policy=condition())],{'new_fact':20})
    assert option['scoreParts']['bsc']==1
    assert len(option['tradeoffEvaluation'])==2


def test_forecast_binding_is_distinct_from_observed_fact():
    option=evaluate([path('conditional',policy=condition('x < 56','forecast','sv:ts1'))],{'sv:ts1':100})
    assert option['scoreParts']['bsc']==1  # candidate forecast is 55.4


def test_changed_description_invalidates_predicate_interpretation():
    option=evaluate([path('changed',policy=condition(),text='different meaning')],{'new_fact':20})
    assert option['tradeoffEvaluation'][0]['status']=='UNKNOWN'


def test_equal_strength_paths_keep_both_conditions():
    option=evaluate([path('one',policy=condition('x > 1')),path('two',policy=condition('x < 100'))],{'new_fact':20})
    assert len(option['tradeoffEvaluation'])==2
    assert option['scoreParts']['bsc']==1


def test_false_edge_dominates_unknown_other_edge_in_same_path():
    row=path('and',policy=condition())
    row['edges'][0].update(condition='no interpretation')
    option=evaluate([row],{'new_fact':0})
    assert option['tradeoffEvaluation'][0]['status']=='FALSE'
    assert not option['gains']


@pytest.mark.parametrize('value',[None, 'false', False])
def test_missing_or_incompatible_fact_is_not_a_true_numeric_condition(value):
    option=evaluate([path('typed',policy=condition())],{'new_fact':value})
    assert option['tradeoffEvaluation'][0]['status']=='UNKNOWN'


def test_unknown_strength_cannot_be_assumed_low():
    row=path('bad');row['edges'][1]['strength']=None
    with pytest.raises(ValueError,match='strength'):
        evaluate([row])


def test_input_values_are_retained_but_stable_applicability_can_be_reviewed():
    from hydcommon import bsc
    a=evaluate([path('stable',policy=condition())],{'new_fact':20})
    b=evaluate([path('stable',policy=condition())],{'new_fact':21})
    assert a['tradeoffEvaluation'][0]['checks'][1]['inputs']['x']['value']==20
    assert a['rankingEvidence']==b['rankingEvidence']
