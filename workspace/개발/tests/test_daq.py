"""DAQ 필터(ot/plant-sim/plantsim/daq.py) — lite 예외 보고 · full 전부, 나가지 못한 값은 보낸 것으로 치지 않는다(G3b-14)."""
import pytest

from plantsim.daq import DaqFilter

TAGS = {'TS1': 48.0, 'TS2': 44.0, 'EPS1': 2.8}


def test_lite는_매초_태그만_매초_나머지는_처음_한번_뒤_하트비트나_데드밴드():
    daq = DaqFilter('lite')
    first = daq.due('HYD-01', TAGS, 0.0)
    for name, v in first.items():
        daq.sent('HYD-01', name, v, 0.0)
    assert set(first) == {'TS1', 'TS2', 'EPS1'}
    assert set(daq.due('HYD-01', TAGS, 1.0)) == {'TS1'}
    assert set(daq.due('HYD-01', dict(TAGS, EPS1=2.86), 1.0)) == {'TS1', 'EPS1'}      # 데드밴드 0.05 넘음
    assert set(daq.due('HYD-01', TAGS, 10.0)) == {'TS1', 'EPS1'}                       # 하트비트 10 초(보조는 30 초)
    assert set(daq.due('HYD-01', TAGS, 30.0)) == {'TS1', 'TS2', 'EPS1'}


def test_보내지_못한_값은_다음_틱에_다시_나온다():
    daq = DaqFilter('lite')
    assert 'EPS1' in daq.due('HYD-01', TAGS, 0.0)        # sent() 를 부르지 않음 — 연결이 끊겨 나가지 못했다
    assert 'EPS1' in daq.due('HYD-01', TAGS, 1.0)


def test_full은_모든_태그와_파형을_낸다():
    daq = DaqFilter('full')
    assert daq.due('HYD-01', TAGS, 0.0) == TAGS and daq.waves


@pytest.mark.parametrize('profile', ['Full', 'fulll', '', None])
def test_모르는_수집_방식은_lite로_바꾸지_않고_거절한다(profile):
    with pytest.raises(ValueError):
        DaqFilter(profile)
