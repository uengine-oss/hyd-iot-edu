"""재관측 창 값 줄이기(procsvc/reobs_series.py) — 최대 60점, 끝점은 실제 마지막 값, 못 읽은 창은 까닭과 함께."""
import pytest

from procsvc import reobs_series as rs


def _rows(n, start=60.0, step=-0.1):
    return [(f'2026-10-30T06:00:{i:02d}Z' if i < 60 else f'2026-10-30T06:{i // 60:02d}:{i % 60:02d}Z', start + i * step) for i in range(n)]


@pytest.mark.parametrize('n, points', [(0, 0), (1, 1), (60, 60), (61, 60), (900, 60)], ids=['없음', '하나', '60', '61', '900'])
def test_창_값은_60점까지만_남기고_끝점은_실제_마지막_값이다(n, points):
    rows = _rows(n)
    out = rs.sample(rows)
    assert len(out) == points
    if rows:
        assert out[-1] == {'t': rows[-1][0], 'v': round(rows[-1][1], 4)}


def test_줄인_값과_함께_창의_실제_최솟값_최댓값_처음_끝을_남긴다():
    rows = [('t0', 58.0), ('t1', 61.0), ('t2', 54.0), ('t3', 53.5)]
    s = rs.build(rows, tag='TS1', op='<', limit=55.0, since='a', until='b', after='command')
    assert (s['min'], s['max'], s['first'], s['last']) == (53.5, 61.0, 58.0, 53.5)
    assert (s['inside_last'], s['inside_share'], s['samples']) == (True, 0.5, 4)
    assert s['criterion'] == 'TS1 < 55.0'


@pytest.mark.parametrize('value, op, limit, inside', [(54.9, '<', 55.0, True), (55.0, '<', 55.0, False), (165.0, '>=', 165.0, True),
                                                      (None, '<', 55.0, False)],
                         ids=['아래', '경계는 밖', '이상 경계', '값 없음'])
def test_기준_안_판정은_연산과_경계를_따른다(value, op, limit, inside):
    assert rs.inside(value, op, limit) is inside


def test_읽지_못한_창도_같은_모양으로_까닭과_함께_남는다():
    s = rs.unavailable('시계열 DB 연결 실패', tag='TS1', op='<', limit=55.0, since=None, until='b', after='work_order')
    assert s['error'] == '시계열 DB 연결 실패' and s['samples'] == 0 and s['points'] == [] and s['inside_last'] is False


@pytest.mark.parametrize('history, start', [
    ([{'state': 'AWAITING_ACK', 't': '1'}, {'state': 'RE_OBSERVING', 't': '2'}, {'state': 'RE_OBSERVING', 't': '3'}], '3'),
    ([{'state': 'AWAITING_ACK', 't': '1'}], None), ([], None)], ids=['마지막 재관측', '재관측 없음', '기록 없음'])
def test_재관측_창의_시작은_사건_기록의_마지막_재관측_시각이다(history, start):
    assert rs.window_start(history) == start
