"""시각과 배속(common/hydcommon/timeutil.py) — 글자가 아닌 시각 값은 ValueError(G3b-1 · 2), 배속은 compose 값만(G3b-25)."""
from datetime import datetime, timezone

import pytest

from hydcommon import timeutil


@pytest.mark.parametrize('text, expected', [
    ('2026-10-30T05:00:00.000Z', datetime(2026, 10, 30, 5, tzinfo=timezone.utc)),
    ('2026-10-30T14:00:00+09:00', datetime(2026, 10, 30, 5, tzinfo=timezone.utc)),
    ('2026-10-30T05:00:00', datetime(2026, 10, 30, 5, tzinfo=timezone.utc)),     # 시간대 없음 = UTC(process 가 저장한 시각)
])
def test_ISO_시각을_UTC로_읽는다(text, expected):
    assert timeutil.parse_iso(text) == expected


@pytest.mark.parametrize('value', [1730000000, None, ['2026-10-30'], 'not a time', ''])
def test_시각이_아닌_값은_ValueError다(value):
    with pytest.raises(ValueError):
        timeutil.parse_iso(value)


def test_ISO_로_쓰고_다시_읽으면_밀리초까지_같다():
    at = datetime(2026, 10, 30, 5, 1, 2, 345000, tzinfo=timezone.utc)
    assert timeutil.to_iso(at) == '2026-10-30T05:01:02.345Z' and timeutil.parse_iso(timeutil.to_iso(at)) == at


@pytest.mark.parametrize('env, scale', [({'TIME_SCALE': '20'}, 20.0), ({'TIME_SCALE': '1'}, 1.0), ({'TIME_SCALE': '0.5'}, 0.5)])
def test_배속은_compose_가_준_값이다(env, scale):
    assert timeutil.time_scale(env) == scale


@pytest.mark.parametrize('env', [{}, {'TIME_SCALE': ''}, {'TIME_SCALE': 'fast'}, {'TIME_SCALE': '0'}, {'TIME_SCALE': '-2'},
                                 {'TIME_SCALE': 'inf'}, {'TIME_SCALE': 'nan'}])
def test_배속이_없거나_잘못되면_변수_이름을_대며_멈춘다(env):
    with pytest.raises(ValueError, match='TIME_SCALE'):
        timeutil.time_scale(env)
