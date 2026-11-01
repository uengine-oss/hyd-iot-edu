"""네 단계 상태 기계와 PLC 트립 경보(it/detector/det/cep.py) — 유지 · 해제 · 끊김 · 트립 원인과 이름(G5b-02 · G3b-8)."""
import pytest

from det import cep

NAMES = {'OVERHEAT_TRIP': '과열 인터록 트립', 'COOLER_DEGRADATION': '쿨러 성능 저하'}


def _drive(st, ticks, hold=60.0):
    out = []
    for t, cond, clear in ticks:
        ev = cep._step(st, 'HYD-01', t, 'COOLER_DEGRADATION', 'HIGH', cond, clear, hold, f't{t}', {}, max_gap_s=60.0,
                       name=NAMES['COOLER_DEGRADATION'])
        if ev:
            out.append((t, ev['state'], ev['alertId']))
    return out


def test_조건이_유지_시간_내내_참이면_한_번_울리고_해제도_같은_id로_한_번():
    st = cep.CepState()
    events = _drive(st, [(t, True, False) for t in range(0, 81, 20)] + [(t, False, True) for t in range(100, 181, 20)])
    assert [(t, s) for t, s, _ in events] == [(60, 'RAISE'), (160, 'CLEAR')] and events[0][2] == events[1][2]


def test_중간에_거짓이_되면_유지를_처음부터_다시_잰다():
    st = cep.CepState()
    assert _drive(st, [(0, True, False), (40, False, False), (60, True, False), (100, True, False)]) == []
    assert _drive(st, [(120, True, False)])[0][1] == 'RAISE'


def test_관측_공백이_한도를_넘으면_후보가_끊기고_울린_경보는_풀리지_않는다():
    st = cep.CepState()
    assert _drive(st, [(0, True, False), (100, True, False)]) == []        # 100 − 0 > 60: 공백 — 후보를 다시
    assert st.phase == 'CANDIDATE' and st.since == 100
    st = cep.CepState(phase='RAISED', alert_id='A1', last_t=0)
    cep.interrupt(st)
    assert st.phase == 'RAISED'


def test_경보에는_그래프의_패턴_이름이_실린다():
    st = cep.CepState()
    ev = cep._step(st, 'HYD-01', 0, 'COOLER_DEGRADATION', 'HIGH', True, False, 0.0, 't', {}, name='쿨러 성능 저하')
    ev = ev or cep._step(st, 'HYD-01', 1, 'COOLER_DEGRADATION', 'HIGH', True, False, 0.0, 't', {}, name='쿨러 성능 저하')
    assert ev['name'] == '쿨러 성능 저하' and ev['state'] == 'RAISE'


@pytest.mark.parametrize('reason, pattern', [('OVERTEMP', 'OVERHEAT_TRIP'), ('LOW_PRESSURE', 'LOW_PRESSURE_TRIP'),
                                             ('HIGH_VIBRATION', 'HIGH_VIBRATION_TRIP'), (None, 'PLC_TRIP')])
def test_PLC_트립은_원인에_맞는_패턴으로_울리고_풀릴_때_같은_패턴_id로_풀린다(reason, pattern):
    st = cep.TripState()
    raise_ = cep.trip_alert(st, 'HYD-01', True, 't1', reason, NAMES)
    assert cep.trip_alert(st, 'HYD-01', True, 't2', reason, NAMES) is None          # 트립이 이어지는 동안 다시 울리지 않는다
    clear = cep.trip_alert(st, 'HYD-01', False, 't3', None, NAMES)
    assert (raise_['pattern'], clear['pattern'], clear['alertId'], clear['state']) == (pattern, pattern, raise_['alertId'], 'CLEAR')
    assert raise_['name'] == NAMES.get(pattern) and raise_['severity'] == 'CRITICAL'
