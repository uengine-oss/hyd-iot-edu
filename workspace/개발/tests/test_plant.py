"""설비 세 대와 결함 주입(ot/plant-sim/plantsim/plant.py) — 20배속 하위 걸음, 결함 목표값의 물리 범위(G3b-28)."""
import math

import pytest

from plantsim.plant import DOMAIN, Plant


def test_벽시계_1초는_배속만큼의_설비_초다():
    plant = Plant(time_scale=20)
    plant.tick(1.0)
    assert plant.sim_t == 20


@pytest.mark.parametrize('kind, kwargs, attr, target', [
    ('cooler_degradation', {}, 'cooler_health', 0.43),
    ('cooler_degradation', {'severity': 'moderate'}, 'cooler_health', 0.55),
    ('pump_leakage', {'target': 0.5}, 'leak', 0.5),                     # 경계: 물리 범위 끝
    ('fan_vibration', {'target': 0.0}, 'bearing_wear', 0.0),
])
def test_결함은_목표값까지_천천히_간다(kind, kwargs, attr, target):
    plant = Plant(time_scale=20)
    out = plant.inject('HYD-01', kind, ramp_sim_s=100, **kwargs)
    assert out['targets'] == {attr: target}
    for _ in range(10):
        plant.tick(1.0)                                                 # 200 설비 초 > 램프 100
    assert getattr(plant.units['HYD-01'].state, attr) == pytest.approx(target)


@pytest.mark.parametrize('kwargs, word', [
    ({'target': math.nan}, 'target'), ({'target': 1.5}, 'target'), ({'target': -0.1}, 'target'), ({'target': True}, 'target'),
    ({'ramp_sim_s': 0}, 'ramp_sim_s'), ({'ramp_sim_s': math.inf}, 'ramp_sim_s'), ({'severity': 'extreme'}, 'severity'),
])
def test_물리_범위_밖_목표값_램프_세기는_거절한다(kwargs, word):
    plant = Plant(time_scale=20)
    with pytest.raises(ValueError, match=word):
        plant.inject('HYD-01', 'cooler_degradation', **kwargs)
    assert plant.units['HYD-01'].faults == {} and set(DOMAIN) == {'cooler_health', 'leak', 'bearing_wear'}


def test_복구는_외란을_건강값으로_되돌리고_운전점은_원할_때만_되돌린다():
    plant = Plant(time_scale=20)
    unit = plant.units['HYD-01']
    unit.state.cooler_health, unit.state.fan_pct = 0.43, 100.0
    assert plant.inject('HYD-01', 'restore')['setpoints'] is None and unit.state.fan_pct == 100.0
    out = plant.inject('HYD-01', 'restore', operating_point=True)
    assert out['setpoints']['after'] == {'FanSpeedSP': 60.0, 'LoadSP': 90.0}
    with pytest.raises(ValueError):
        plant.inject('HYD-01', 'cooler_degradation', operating_point=True)


def test_상태의_시각은_부른_쪽이_준_틱_시각이다():
    plant = Plant(time_scale=20)
    assert plant.status('HYD-01', '2026-10-30T05:00:00.000Z')['t'] == '2026-10-30T05:00:00.000Z'


def test_초기화는_세_대를_건강한_원격_자동으로():
    plant = Plant(time_scale=20)
    plant.inject('HYD-02', 'pump_leakage')
    plant.units['HYD-02'].ctrl.mode = 'LOCAL'
    plant.reset()
    u = plant.units['HYD-02']
    assert (u.faults, u.state.leak, u.ctrl.mode, u.ctrl.state, u.ctrl.last_cmd_id) == ({}, 0.0, 'REMOTE_AUTO', 'RUN', None)
