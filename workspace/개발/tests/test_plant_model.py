"""설비 물리 한 벌(common/hydcommon/plant_model.py) — 시뮬레이터와 승인 예측이 같은 식을 쓴다(G3b-16 · 17).

판정은 시뮬레이터 적분(plantsim.thermal.step)과 예측의 닫힌 식(hydcommon.forecast.predict)이 같은 값을 내는지, 그리고 머리말에 적힌
보정 결과(정상 48 ℃ · 열화 트립 · 완화 49 ℃ · 누설 PS1 162)가 실제 식에서 나오는지다.
"""
import pytest

from hydcommon import forecast, plant_model as m
from plantsim import thermal


def _settle(state, seconds, running=True):
    for _ in range(int(seconds)):
        thermal.step(state, 1.0, running)
    return state


@pytest.mark.parametrize('load, fan, health, leak, pump, expected', [
    (90, 60, 1.00, 0.0, 'A', 48.0),        # 정상 운전점
    (80, 100, 0.43, 0.0, 'A', 49.0),       # 완화(팬 100 · 부하 80) — 52 ℃ 해제선 아래
    (90, 60, 0.55, 0.0, 'A', 62.5),        # moderate — 55 경보 위, 65 트립 아래
])
def test_보정한_운전점의_평형_유온이_머리말과_같다(load, fan, health, leak, pump, expected):
    assert m.steady_ts1(load, m.effective_leak(leak, pump), fan, health, True) == pytest.approx(expected, abs=0.6)


def test_정지_트립_중에는_팬_냉각_없이_자연_냉각만_한다():
    """G3b-17: 문서는 「펌프와 팬이 꺼진다」인데 냉각은 팬 설정값으로 계속 식혔다. 펌프가 멈추면 쿨러에 기름이 돌지 않는다."""
    assert m.cooling_coef(100, 1.0, running=False) == m.K_BASE < m.cooling_coef(100, 1.0, running=True)
    hot = thermal.UnitState(ts1=65.5, fan_pct=100)
    _settle(hot, 600, running=False)
    natural = 25 + (65.5 - 25) * (1 - m.K_BASE / m.C) ** 600       # 열 입력 0, 냉각 계수 K_BASE 의 이산 적분
    assert hot.ts1 == pytest.approx(natural, abs=0.01) and hot.ts1 > 55     # 10 설비 분 뒤에도 리셋 온도(55) 위


def test_누설은_펌프_A만이고_예비_B로_바꾸면_압력이_돌아온다():
    leaking = m.pressure(90, m.effective_leak(0.15, 'A'))
    assert leaking == pytest.approx(162, abs=0.6) and leaking < 165
    assert m.pressure(90, m.effective_leak(0.15, 'B')) == pytest.approx(182, abs=0.1)
    assert m.flow(90, 0.15, True) == pytest.approx(7.65) and m.flow(90, 0.15, False) == 0


@pytest.mark.parametrize('state, actions, horizon', [
    ('RUN', [], 900),
    ('RUN', [{'kind': 'command', 'code': 'FAN_SET', 'value': 100}, {'kind': 'command', 'code': 'LOAD_SET', 'value': 80}], 1800),
    ('RUN', [{'kind': 'command', 'code': 'STOP'}], 600),
    ('TRIP', [{'kind': 'command', 'code': 'RESET'}], 300),
])
def test_예측의_닫힌_식은_시뮬레이터_적분과_같은_유온을_낸다(state, actions, horizon):
    ts1 = 50.0 if state == 'TRIP' else 58.0
    snap = {'forecast_model': forecast.MODEL_ID, 'disturbance_ramps': [], 'asset': 'HYD-01', 't': '2026-10-30T05:00:00Z',
            'state': state, 'pump': 'A', 'ts1': ts1, 't_amb': 25.0, 'fan_pct': 60.0, 'load_pct': 90.0,
            'cooler_health': 0.43, 'leak': 0.0, 'bearing_wear': 0.0}
    predicted = forecast.predict(snap, actions, horizon)
    op = predicted['operating']
    sim = thermal.UnitState(ts1=ts1, fan_pct=op['fan_pct'], load_pct=op['load_pct'], cooler_health=0.43)
    _settle(sim, horizon, running=op['state'] == 'RUN')
    assert predicted['values']['ts1'] == pytest.approx(sim.ts1, abs=0.05)
