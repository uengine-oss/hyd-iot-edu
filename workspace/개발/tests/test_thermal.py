"""설비 한 대의 1초 걸음(ot/plant-sim/plantsim/thermal.py) — 결함 시나리오가 교재 · 감지 기준대로 나온다(G5b-02)."""
import pytest

from plantsim import thermal


def _run(state, seconds, running=True):
    for _ in range(int(seconds)):
        thermal.step(state, 1.0, running)
    return state


def test_정상_운전점은_48도_압력_182_유량_9_진동_0_6에_머문다():
    s = _run(thermal.UnitState(), 1800)
    assert (round(s.ts1, 1), round(s.ps1), round(s.fs1, 1), round(s.vs1, 1)) == (48.0, 182, 9.0, 0.6)


@pytest.mark.parametrize('health, settles_above', [(0.43, 65.0), (0.55, 55.0)])
def test_쿨러_오염은_경보선을_넘긴다_high는_트립선까지(health, settles_above):
    s = _run(thermal.UnitState(cooler_health=health), 4000)
    assert s.ts1 > settles_above and s.ce < 70


def test_펌프_누설은_압력과_유량을_펌프_누설_기준_아래로():
    s = _run(thermal.UnitState(leak=thermal.DEGRADED_LEAK), 60)
    assert s.ps1 < 165 and s.fs1 < 8.0


@pytest.mark.parametrize('fan, low, high', [(60, 1.2, 1.6), (40, 0.7, 1.1), (100, 2.0, 3.2)])
def test_팬_베어링_마모의_진동은_팬_속도와_함께_커진다(fan, low, high):
    s = _run(thermal.UnitState(bearing_wear=0.8, fan_pct=fan), 30)
    assert low < s.vs1 < high


def test_정지하면_부하_유량_전력이_0이고_팬_진동은_마모만큼_없다():
    s = _run(thermal.UnitState(bearing_wear=0.8), 5, running=False)
    assert (s.fs1, s.eps1) == (0.0, 0.0) and s.vs1 < 0.7


@pytest.mark.parametrize('fn, hz', [(thermal.wave_ps1, 100), (thermal.wave_eps1, 100), (thermal.wave_fs1, 10)])
def test_파형은_hz_개의_점이다(fn, hz):
    assert len(fn(thermal.UnitState(), hz)) == hz
