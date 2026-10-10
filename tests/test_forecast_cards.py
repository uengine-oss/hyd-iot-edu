from copy import deepcopy
from datetime import datetime, timedelta
from types import SimpleNamespace
import pytest

from agentsvc import cards, decide, forecasting
from dmn_mcp.tools import DmnTools
from plantsim import thermal
from test_cards import BASE, DMN, SKILLS, TRADE
from test_forecast_model import snapshot, action
from test_forecast_source import kg


def skills():
    result = deepcopy(SKILLS)
    result['skill:fan']['actions'] = [action('FAN_SET', 100)]
    result['skill:mix']['actions'] = [action('FAN_SET', 100), action('LOAD_SET', 80)]
    return result


def evaluate(monkeypatch, unit, graph=None):
    reads = []
    monkeypatch.setattr(decide, '_get_json', lambda url:(reads.append(url), snapshot(unit))[1])
    forecasts, contexts = forecasting.candidates(graph or kg(), 'TEST-ASSET', skills())
    return cards.evaluate(DMN, skills(), BASE, forecasts, TRADE, [], {}, contexts), reads


def test_cards_compute_all_candidates_from_one_current_snapshot(monkeypatch):
    result, reads = evaluate(monkeypatch, thermal.UnitState(cooler_health=.43))
    mix = next(o for o in result['options'] if o['id'] == 'skill:mix')
    assert len(reads) == 1 and mix['feasible']
    ctx = mix['forecastContext']
    assert ctx['inputs']['cooler_health'] == .43 and ctx['actions'][1]['value'] == 80
    assert ctx['binding']['model_revision'] == '1.0' and ctx['parameters']['heat_capacity'] == 20
    assert next(f['value'] for f in mix['forecast'] if f['variable'] == 'sv:ts1') == round(ctx['values']['ts1_steady'], 3)


def test_compound_bearing_fault_excludes_otherwise_cool_thermal_solution(monkeypatch):
    result, _ = evaluate(monkeypatch, thermal.UnitState(cooler_health=.43, bearing_wear=.8))
    mix = next(o for o in result['options'] if o['id'] == 'skill:mix')
    assert mix['facts']['forecast_ts1'] < 55
    assert not mix['feasible'] and any(v['rule']=='forecast:predicted-interlock' for v in mix['violations'])


@pytest.mark.parametrize('key,value',[('model_id', None), ('model_revision','2.0'),('scope','real factory'),('horizon_s',float('nan'))])
def test_bad_asset_binding_never_falls_back_to_design_forecasts(monkeypatch, key, value):
    bound = kg().forecast_model('TEST-ASSET'); bound[key] = value
    graph = SimpleNamespace(forecast_model=lambda asset:bound)
    result, reads = evaluate(monkeypatch, thermal.UnitState(), graph)
    assert not reads and result['recommended'] is None
    assert all(not o['forecast'] and not o['feasible'] and o['forecastContext']['error'] for o in result['options'])


def test_current_source_failure_excludes_even_request_only_skills(monkeypatch):
    monkeypatch.setattr(decide,'_get_json',lambda *args:(_ for _ in ()).throw(OSError('offline')))
    forecasts, contexts = forecasting.candidates(kg(), 'TEST-ASSET', skills())
    assert not forecasts and all('offline' in c['error'] for c in contexts.values())


def test_clock_and_small_temperature_drift_do_not_revoke_unchanged_consent(monkeypatch):
    result, _ = evaluate(monkeypatch, thermal.UnitState(cooler_health=.43,ts1=56))
    old = result['options'][0]['forecastContext']
    newer, _ = evaluate(monkeypatch, thermal.UnitState(cooler_health=.43,ts1=56.1))
    assert forecasting.consent_changes(old, newer['options'][0]['forecastContext']) == []


@pytest.mark.parametrize('change', [
    lambda c: c['inputs'].update(cooler_health=.5),
    lambda c: c['actions'][0].update(value=70),
    lambda c: c.update(model_revision='2.0'),
    lambda c: c['parameters'].update(heat=2),
    lambda c: c['values'].update(ts1=c['values']['ts1']+1),
    lambda c: c.update(predicted_interlocks=['HIGH_VIBRATION']),
])
def test_material_prediction_changes_require_new_review(monkeypatch, change):
    result, _ = evaluate(monkeypatch, thermal.UnitState())
    old = result['options'][0]['forecastContext']; new = deepcopy(old); change(new)
    assert forecasting.consent_changes(old, new)


def test_missing_previous_model_context_requires_new_review():
    assert forecasting.consent_changes(None, {})


def _later(context, wall_seconds, **values):
    """The same forecast re-read `wall_seconds` later on the plant clock, with the given predicted values moved."""
    later = deepcopy(context)
    stamp = datetime.fromisoformat(context['source_t'].replace('Z', '+00:00')) + timedelta(seconds=wall_seconds)
    later['source_t'] = stamp.isoformat()
    later['values'].update({k: later['values'][k] + v for k, v in values.items()})
    return later


def test_consent_budget_grows_with_simulated_time_between_review_and_command(monkeypatch):
    # A129 (session 19, 2-fresh-review): at TIME_SCALE=20 the 15 wall seconds between the human's review and the command
    # are 5 simulated minutes in which TS1 legitimately rises; the same rise in 15 real seconds is not legitimate.
    result, _ = evaluate(monkeypatch, thermal.UnitState(cooler_health=.43, ts1=62))
    old = result['options'][0]['forecastContext']
    drifted = _later(old, 15, ts1=1.5, ts1_peak=3.0)
    assert forecasting.consent_changes(old, drifted, time_scale=20) == []
    assert forecasting.consent_changes(old, drifted, time_scale=1) == [
        '예측 ts1 악화 또는 미확인: 새 카드 검토가 필요합니다', '예측 ts1_peak 악화 또는 미확인: 새 카드 검토가 필요합니다']
    # a change larger than the plant can produce in that simulated time is still a different prediction
    assert forecasting.consent_changes(old, _later(old, 15, ts1=8.0), time_scale=20)


def test_stale_review_requires_a_new_card_even_when_values_hold(monkeypatch):
    result, _ = evaluate(monkeypatch, thermal.UnitState(cooler_health=.43, ts1=56))
    old = result['options'][0]['forecastContext']
    assert forecasting.consent_changes(old, _later(old, 120, ts1=0.0), time_scale=20) == [
        '검토한 예측이 시뮬레이션 40분 전 상태입니다: 새 카드 검토가 필요합니다']
    assert forecasting.consent_changes(old, _later(old, 120, ts1=0.0), time_scale=1) == []


def test_time_scale_comes_from_the_running_stack_then_the_environment(monkeypatch):
    monkeypatch.setattr(decide, '_get_json', lambda url: {'time_scale': 20.0})
    assert forecasting.stack_time_scale() == 20.0
    monkeypatch.setattr(decide, '_get_json', lambda url: (_ for _ in ()).throw(OSError('offline')))
    monkeypatch.setenv('TIME_SCALE', '5')
    assert forecasting.stack_time_scale() == 5.0
    monkeypatch.delenv('TIME_SCALE')
    assert forecasting.stack_time_scale() == 1.0


def test_live_submit_cannot_overwrite_source_facts_before_any_io():
    graph = SimpleNamespace()
    with pytest.raises(ValueError,match='읽기 전용'):
        DmnTools(kg=graph, tsdb=object()).submit_decision('HYD-01','p','c','f','incident',
                                                     overrides={'plc_mode':'REMOTE_AUTO','standby_ready':True})


def test_runtime_decide_saves_dynamic_context_and_keeps_what_if_read_only(monkeypatch):
    graph = kg()
    graph.dmn=lambda:DMN; graph.inputs=lambda:[]; graph.skills=lambda ids:list(skills().values())
    graph.tradeoffs=lambda ids:TRADE; graph.precedents=lambda fm:[]; graph.suppliers=lambda:{}; graph.roles=lambda:[]
    graph.forecasts=lambda cause:pytest.fail('static forecast cannot be consulted')
    monkeypatch.setattr(decide, 'gather_facts', lambda *args,**kw:(dict(BASE), []))
    monkeypatch.setattr(decide, '_get_json', lambda url:snapshot(thermal.UnitState(cooler_health=.43)))
    sent=[]; monkeypatch.setattr(decide, 'submit', lambda value:(sent.append(value), {'ok':True})[1])
    cause={'id':'cause:fouling','failureModeId':'fm:cool'}
    record=decide.decide(graph,decide.DecisionRegistry(),None,'TEST-ASSET','COOLER_DEGRADATION',cause,do_submit=True)
    assert record['status']=='SUBMITTED' and len(sent)==1
    assert all(o['forecastContext']['model_revision']=='1.0' for o in sent[0]['options'])
    trial=decide.decide(graph,decide.DecisionRegistry(),None,'TEST-ASSET','COOLER_DEGRADATION',cause,
                        overrides={'plc_mode':'REMOTE_MANUAL'},do_submit=False)
    assert trial['status']=='NO_FEASIBLE_OPTION' and len(sent)==1
    # 라이브 3차 C: 읽기 평가(evaluate_cards)가 DEC- id 를 받아 저장되지 않은 '판단 id'(GET 404)로 보였다 — 제출되는 판단만 DEC-
    assert sent[0]['id']==record['id'] and record['id'].startswith('DEC-') and trial['id'].startswith('EVAL-')
    with pytest.raises(ValueError,match='id 종류'):
        decide.DecisionRegistry().new_id('DECISION')
