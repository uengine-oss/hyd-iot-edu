"""관측 유효성(it/detector/det/observations.py) — 누락 · 무효 · 미래 · 오래됨은 벽시계 초로(G5b-02 · G3b-4 · 29)."""
import math

import pytest

from det.observations import Observations


def _obs():
    o = Observations('lite', 2.0)
    o.record('TS1', 100.0, 48.0)
    o.record('PLC_STATE', 100.0, 'RUN')
    return o


@pytest.mark.parametrize('name, at, now, problem', [
    ('TS1', 100.0, 100.0, None),
    ('TS1', 103.0, 103.0, None),                         # 경계: 1 s 보고 + 여유 2 s = 3 s
    ('TS1', 103.1, 103.1, 'STALE'),
    ('PLC_STATE', 103.0, 103.0, None),                   # G3b-29: 상태도 1 s 주기(+2) — 10 s 를 기다리지 않는다
    ('PLC_STATE', 103.5, 103.5, 'STALE'),
    ('TS1', 99.0, 99.0, 'FUTURE_TIMESTAMP'),             # 평가 시각보다 늦은 표본
    ('CE', 100.0, 100.0, 'MISSING'),
])
def test_표본의_문제는_평가_시각과_벽시계로_가린다(name, at, now, problem):
    assert _obs().problems((name,), at, now).get(name) == problem


@pytest.mark.parametrize('name, value, quality', [('TS1', 'x', 'good'), ('TS1', math.nan, 'good'), ('TS1', 50.0, 'bad'),
                                                  ('PLC_STATE', 'RUNNING', 'good')])
def test_값이나_품질이_틀린_표본은_무효다(name, value, quality):
    o = Observations('lite', 2.0)
    assert o.record(name, 1.0, value, quality) == ('invalid', False)
    assert o.problems((name,), 1.0, 1.0)[name] == 'INVALID_VALUE_OR_QUALITY'


def test_같은_시각_다른_값은_충돌이고_오래된_표본은_무시한다():
    o = _obs()
    assert o.record('TS1', 100.0, 48.0) == ('ignored', False)
    assert o.record('TS1', 99.0, 47.0) == ('ignored', False)
    assert o.record('TS1', 100.0, 49.0) == ('invalid', False)


def test_보고_주기보다_긴_틈은_공백으로_알린다():
    o = _obs()
    assert o.record('TS1', 104.0, 48.0) == ('valid', True) and o.record('TS1', 105.0, 48.0) == ('valid', False)


@pytest.mark.parametrize('profile, grace', [('fast', 2.0), ('lite', -1.0), ('lite', math.inf)])
def test_수집_방식과_여유가_틀리면_만들지_않는다(profile, grace):
    with pytest.raises(ValueError):
        Observations(profile, grace)
