"""Registered scheduling effects are physically neutral, never generic no-ops."""
from copy import deepcopy

import pytest

from agentsvc import cards, decide, forecasting
from hydcommon.forecast import predict
from plantsim import thermal
from test_cards import DMN, R, T, skill
from test_forecast_model import snapshot
from test_forecast_source import kg


def reschedule():
    return dict(id='action:pm-reschedule', code='WO_RESCHEDULE', kind='transaction')


def test_registered_reschedule_preserves_physical_state_and_original_action():
    source = snapshot(thermal.UnitState(ts1=57, leak=.15, cooler_health=.43))
    action = reschedule()
    before = deepcopy((source, action))
    baseline = predict(source, [], 900)
    changed = predict(source, [action], 900)
    for key in ('inputs', 'operating', 'values', 'predicted_interlocks'):
        assert changed[key] == baseline[key]
    assert changed['actions'] == [action]
    assert (source, action) == before


@pytest.mark.parametrize('action', [
    {}, dict(kind='transaction'), dict(kind='transaction', code='WO_UNKNOWN'),
    dict(code='WO_RESCHEDULE'), dict(kind='work_order', code='WO_RESCHEDULE'),
    dict(kind='command', code='WO_RESCHEDULE'),
])
def test_missing_unknown_or_mistyped_effect_cannot_be_ignored(action):
    with pytest.raises(ValueError):
        predict(snapshot(thermal.UnitState()), [action], 900)


def test_real_forecast_adapter_removes_only_reschedule_model_error(monkeypatch):
    state = snapshot(thermal.UnitState())
    reads = []
    monkeypatch.setattr(decide, '_get_json', lambda url: (reads.append(url), state)[1])
    k = skill('skill:reschedule', 'SOP-PM-13', kind='work_order', codes=())
    k.update(relation='PREVENTED_BY', actions=[reschedule()])
    forecasts, contexts = forecasting.candidates(kg(), 'TEST-ASSET', {k['skillId']: k})
    assert len(reads) == 1 and k['skillId'] in forecasts
    assert 'error' not in contexts[k['skillId']]
    assert contexts[k['skillId']]['execution_authorized'] is False
    assert contexts[k['skillId']]['actions'] == [reschedule()]
    rules = [R('dec:action-candidates', 'rule:pm', 'SELECT',
               [T('pattern', '==', 'PM_DUE')], [k['skillId']]), deepcopy(DMN[-1])]
    result = cards.evaluate(rules, {k['skillId']: k}, dict(pattern='PM_DUE'),
                            forecasts, [], [], {}, contexts, evaluation_mode='execution')
    option = result['options'][0]
    assert not any(v['rule'] == 'forecast:model-unavailable' for v in option['violations'])
    # Model support does not supply the missing source policy, existing PM order,
    # inventory allocations or a permissible maintenance window.
    assert not option['feasible']
    assert any(v['rule'] == 'execution:pm-plan' for v in option['violations'])


def test_unknown_effect_remains_an_explicit_adapter_failure(monkeypatch):
    monkeypatch.setattr(decide, '_get_json', lambda url: snapshot(thermal.UnitState()))
    action = dict(kind='transaction', code='WO_UNKNOWN')
    forecasts, contexts = forecasting.candidates(kg(), 'TEST-ASSET', {'unknown': dict(actions=[action])})
    assert forecasts == {}
    assert 'unsupported non-command effect' in contexts['unknown']['error']
    assert contexts['unknown']['actions'] == [action]
    assert contexts['unknown']['execution_authorized'] is False
