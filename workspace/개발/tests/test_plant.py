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


@pytest.mark.parametrize('targets, restored, not_modeled', [
    (['sv:fouling'], {'cooler_health': 1.0}, []),                       # 쿨러 핀 오염도(지식의 외란 변수) → 쿨러만
    (['comp:pump-a'], {'leak': 0.0}, []),                               # 구성 요소 id → 그 구성 요소의 외란만
    (['sv:bearing-wear', 'sv:fouling'], {'cooler_health': 1.0, 'bearing_wear': 0.0}, []),
    ([], {}, []),                                                       # 다루는 것이 없는 조치 — 아무것도 되돌리지 않는다
    (['comp:tank', 'sv:ts1'], {}, ['comp:tank', 'sv:ts1']),             # 가상 설비가 모형으로 갖지 않은 대상 — 오류가 아니라 「모형에 없음」
], ids=['외란 변수', '구성 요소', '둘', '빈 목록', '모형에 없는 대상'])
def test_정비_복구는_지식_id로_받은_대상의_외란만_되돌리고_나머지_결함은_남긴다(targets, restored, not_modeled):
    """처리 엔진의 정비 수행은 승인한 조치 방법이 지식에서 다루는 것(sv:* · comp:*)만 되돌려 달라고 한다. 전에는 대상을 흐름이 적은 부품 하나로
    받거나 전부 되돌렸다 — 조치가 다루지 않는 결함까지 사라졌다."""
    plant = Plant(time_scale=20)
    for kind in ('cooler_degradation', 'pump_leakage', 'fan_vibration'):
        plant.inject('HYD-01', kind, ramp_sim_s=1)
    plant.tick(1)
    out = plant.inject('HYD-01', 'restore', targets=targets, ramp_sim_s=1)
    assert out['targets'] == restored and out['not_modeled'] == not_modeled
    plant.tick(1)
    state = plant.units['HYD-01'].state
    left = {a: getattr(state, a) for a in ('cooler_health', 'leak', 'bearing_wear')}
    healthy = {'cooler_health': 1.0, 'leak': 0.0, 'bearing_wear': 0.0}
    assert {a for a in left if left[a] == healthy[a]} == set(restored), left


def test_복구_대상_목록은_복구에만_쓰고_부품_하나와_함께_받지_않는다():
    plant = Plant(time_scale=20)
    with pytest.raises(ValueError, match='targets goes with restore only'):
        plant.inject('HYD-01', 'cooler_degradation', targets=['sv:fouling'])
    with pytest.raises(ValueError, match='not together with component'):
        plant.inject('HYD-01', 'restore', component='cooler', targets=['sv:fouling'])


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
