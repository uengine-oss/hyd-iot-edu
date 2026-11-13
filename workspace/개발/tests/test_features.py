"""특징 계산(it/detector/det/features.py) — 파형 평균 · RMS · 기울기, 이동 기울기 창, 이상 점수(G5b-02)."""
import pytest

from det import features


@pytest.mark.parametrize('v, mean, rms, slope', [([], None, None, None), ([2.0], 2.0, 2.0, 0.0), ([1.0, 2.0, 3.0], 2.0, (14 / 3) ** .5, 1.0)])
def test_파형_특징(v, mean, rms, slope):
    f = features.wave_features(v)
    assert (f['mean'], f['slope']) == (mean, slope) and (f['rms'] == pytest.approx(rms) if rms else f['rms'] is None)


def test_기울기_창은_창_폭보다_오래된_점을_버린다():
    w = features.SlopeWindow(window_s=60)
    for t, v in [(0, 0.0), (20, 1.0), (40, 2.0), (100, 10.0)]:
        w.push(t, v)
    assert [t for t, _ in w.pts] == [40, 100] and w.slope() == pytest.approx(8 / 60)
    w.trim(200)
    assert w.slope() == 0.0                                # 점이 둘 미만이면 0


@pytest.mark.parametrize('values, score', [({'TS1': 48.0, 'CE': 84.0, 'VS1': 0.6}, 0.0),
                                           ({'TS1': 52.0, 'CE': 84.0, 'VS1': 0.6}, round((16 / 3) ** .5 / 4, 3)),
                                           ({'TS1': 70.0, 'CE': 20.0, 'VS1': 2.0}, 1.0)])
def test_이상_점수는_정상_운전점에서_0이고_멀수록_1에_붙는다(values, score):
    assert features.anomaly_score(values) == score
