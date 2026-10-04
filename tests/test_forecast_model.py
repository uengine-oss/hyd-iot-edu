from datetime import datetime, timezone
from itertools import product

import pytest

from hydcommon import forecast
from plantsim import thermal, plc
from plantsim.plant import Plant


def test_fault_domain_transitions_request_immediate_status_publication():
    plant = Plant(time_scale=1, assets=['TEST-ASSET'])
    unit = plant.units['TEST-ASSET']; unit.dirty_status = False
    plant.inject('TEST-ASSET', 'pump_leakage', .15, ramp_sim_s=3)
    assert unit.dirty_status and plant.status('TEST-ASSET')['disturbance_ramps']==['leak']
    unit.dirty_status = False
    plant.tick(1)
    assert not unit.dirty_status and unit.faults
    plant.tick(3)
    assert unit.dirty_status and plant.status('TEST-ASSET')['disturbance_ramps']==[]


def snapshot(unit, ctrl=None):
    return dict(plc.status_payload('TEST-ASSET', ctrl or plc.PlcState(), unit, datetime.now(timezone.utc).isoformat()), disturbance_ramps=[])


def action(code, value=None):
    return {'kind':'command', 'code':code, 'value':value}


@pytest.mark.parametrize('health,leak,wear', list(product([1.0, 0.43], [0, 0.15], [0, 0.8])))
@pytest.mark.parametrize('fan,load,pump', [(100,80,'A'),(40,70,'A'),(60,90,'B')])
def test_prediction_matches_independent_simulator_time_steps(health, leak, wear, fan, load, pump):
    unit = thermal.UnitState(ts1=57, cooler_health=health, leak=leak, bearing_wear=wear)
    actions = [action('FAN_SET', fan), action('LOAD_SET', load), action('PUMP_SELECT', pump)]
    result = forecast.predict(snapshot(unit), actions, 900)
    unit.fan_pct, unit.load_pct, unit.pump = fan, load, pump
    for _ in range(900):
        thermal.step(unit, 1, True)
    assert abs(result['values']['ts1'] - unit.ts1) < 0.015
    assert abs(result['values']['ps1'] - unit.ps1) < 1.2
    assert abs(result['values']['vs1'] - unit.vs1) < 0.08


def test_combined_cooler_and_bearing_fault_is_not_a_fixed_cooler_answer():
    unit = thermal.UnitState(ts1=57, cooler_health=0.43, bearing_wear=0.8)
    prediction = forecast.predict(snapshot(unit), [action('FAN_SET',100),action('LOAD_SET',80)],900)
    assert prediction['values']['ts1'] < 55
    assert 'HIGH_VIBRATION' in prediction['predicted_interlocks']


def test_pump_switch_preserves_cooling_fault_and_predicts_temperature_too():
    unit = thermal.UnitState(ts1=57,cooler_health=0.43,leak=0.15)
    prediction = forecast.predict(snapshot(unit),[action('PUMP_SELECT','B')],900)
    assert prediction['values']['ps1'] == 182
    assert prediction['values']['ts1_steady'] > 65  # switching pump does not clean the cooler


def test_stop_matches_passive_cooling_without_claiming_repair():
    unit = thermal.UnitState(ts1=60,cooler_health=0.43,leak=0.15)
    prediction = forecast.predict(snapshot(unit),[action('STOP')],600)
    for _ in range(600):
        thermal.step(unit,1,False)
    assert abs(prediction['values']['ts1']-unit.ts1) < 0.015
    assert prediction['values']['fs1'] == 0 and not prediction['predicted_interlocks']


@pytest.mark.parametrize('field,value',[('forecast_model',None),('t_amb',None),('leak',float('nan')),
                                       ('fan_pct',True),('state','UNKNOWN'),('pump','C'),('disturbance_ramps',['leak'])])
def test_missing_or_invalid_input_cannot_use_a_healthy_default(field,value):
    source=snapshot(thermal.UnitState());source[field]=value
    with pytest.raises(ValueError):
        forecast.predict(source,[action('FAN_SET',100)],900)


def test_unknown_pressure_command_has_no_invented_effect():
    with pytest.raises(ValueError,match='unsupported command'):
        forecast.predict(snapshot(thermal.UnitState()),[action('PRESSURE_SET',190)],900)


def test_hot_reset_is_not_predicted_as_success():
    with pytest.raises(ValueError,match='below 55'):
        forecast.predict(snapshot(thermal.UnitState(ts1=60),plc.PlcState(state='TRIP')),[action('RESET')],900)
