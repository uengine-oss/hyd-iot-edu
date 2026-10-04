"""A graph ranking policy is executable data, not just a quoted annotation."""
from copy import deepcopy
import json

import pytest

from agentsvc import cards
from test_cards import BASE, DMN, FC, SKILLS, TRADE


def evaluate(policy, facts=None):
    rules = deepcopy(DMN)
    rules[-1]['rankingPolicy'] = json.dumps(policy)
    return cards.evaluate(rules, SKILLS, dict(BASE, **(facts or {})), FC, TRADE, [], {})


def policy(expression, inputs=None):
    return {'version': 1, 'inputs': inputs or {}, 'components': {'value': expression}, 'tieBreak': 'lower_approver'}


def test_changing_actual_formula_reverses_ranking():
    low = evaluate(policy('-forecast_ts1'))
    high = evaluate(policy('forecast_ts1'))
    assert low['recommended'] == 'skill:mix'
    assert high['recommended'] == 'skill:fan'
    assert high['options'][0]['scoreParts'] == {'value': 55.4}


def test_new_fact_mapping_changes_calculation_without_python_edit():
    p = policy('priority if production == "keep" else 0', {'priority': 'db_new_priority'})
    assert evaluate(p, {'db_new_priority': 100})['recommended'] == 'skill:fan'
    assert evaluate(p, {'db_new_priority': -100})['recommended'] == 'skill:mix'


@pytest.mark.parametrize('expression', ['__import__("os").getcwd()', 'forecast_ts1 / 0', 'missing + 1', '2 ** 1000000', 'min', 'True + 1', '1e309'])
def test_invalid_formula_cannot_silently_fall_back_to_old_score(expression):
    with pytest.raises(ValueError):
        evaluate(policy(expression))


def test_missing_policy_cannot_claim_graph_based_ranking():
    rules = deepcopy(DMN)
    for row in rules:
        row.pop('rankingPolicy', None)
    with pytest.raises(ValueError):
        cards.evaluate(rules, SKILLS, BASE, FC, TRADE, [], {})


def test_unknown_new_fact_is_not_zero():
    with pytest.raises(ValueError):
        evaluate(policy('priority', {'priority':'db_new_priority'}))


def test_explicit_unknown_branch_and_bounded_arithmetic():
    p = policy('0 if x is None else round(clamp(x * 2, -10, 10), 2)', {'x':'new_fact'})
    assert evaluate(p)['options'][0]['score'] == 0
    assert evaluate(p, {'new_fact':123})['options'][0]['score'] == 10


def test_overlapping_ranking_rules_are_not_chosen_by_list_order():
    rules = deepcopy(DMN)
    rules.append(dict(rules[-1], rule='second-rank'))
    with pytest.raises(ValueError, match='exactly one'):
        cards.evaluate(rules, SKILLS, BASE, FC, TRADE, [], {})
