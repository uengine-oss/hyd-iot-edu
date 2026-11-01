"""패턴 실행(it/detector/det/pattern_runtime.py) — 관측 저장소 하나, 목록 없이도 관측, 틱 시각 하나면 PLC 상태가 끊기지 않음(G3b-4 · 25).

판정은 실제 시드 그래프(conftest seeded_graph — kg-seed 와 같은 시드)에서 감지기와 같은 함수로 읽은 정의에, 설비 시각 그대로의 표본을
넣고 울림 · 해제 · 끊김을 본다(20배속, 1 Hz).
"""
import pytest

from det.pattern_runtime import PatternRuntime
from det.pattern_source import read_patterns


@pytest.fixture
def catalog(seeded_graph):
    return read_patterns(seeded_graph.driver)


@pytest.fixture
def _runtime(catalog):
    rows, names = catalog
    return lambda only=None: PatternRuntime([r for r in rows if only is None or r['code'] in only], 'lite', 20.0, 2.0, names)


def _tick(rt, t, ts1, ce=84.0, ps1=182.0, fs1=9.0, load=90.0, state='RUN', status_at=None, asset='HYD-02'):
    """한 벽시계 초: 태그 넷 · 상태 하나. status_at 이 None 이면 같은 틱 시각(edge 가 그렇게 낸다)."""
    events = []
    rt.observe(asset, 'PLC_STATE', state, status_at if status_at is not None else t, now=t)
    for name, v in (('CE', ce), ('PS1', ps1), ('FS1', fs1), ('LoadSP', load)):
        rt.observe(asset, name, v, t, now=t)
    events += rt.observe(asset, 'TS1', ts1, t, now=t)[1]
    return events


def test_펌프_누설은_60_설비_초_유지_뒤_한_번_울리고_이름이_실린다(_runtime):
    rt = _runtime()
    events = [e for t in range(1000, 1010) for e in _tick(rt, float(t), 48.0, ps1=160.0, fs1=7.5)]
    assert [(e['pattern'], e['state'], e['name']) for e in events] == [('PUMP_LEAKAGE', 'RAISE', '펌프 내부 누설')]


def test_상태가_태그보다_조금_늦게_찍혀도_유지가_끊긴다_그래서_edge는_틱_시각을_하나로_쓴다(_runtime):
    """G3b-4: 상태 시각이 태그보다 1 ms 늦으면 그 틱의 PLC 상태가 「미래 값」이 되어 후보가 IDLE 로 돌아갔다."""
    late = _runtime()
    assert not [e for t in range(1000, 1010) for e in _tick(late, float(t), 48.0, ps1=160.0, fs1=7.5, status_at=t + 0.001)]
    assert late.assets['HYD-02'].runs['PUMP_LEAKAGE'].quality['problems'] == {'PLC_STATE': 'FUTURE_TIMESTAMP'}


def test_목록을_읽기_전에도_관측은_쌓이고_평가만_하지_않는다(catalog):
    rt = PatternRuntime(None, 'lite', 20.0, 2.0)
    assert rt.observe('HYD-01', 'TS1', 48.0, 10.0, now=10.0) == ('valid', [])
    assert rt.asset('HYD-01').observations.samples['TS1']['value'] == 48.0 and rt.source_ready is False
    rows, names = catalog
    rt.replace([r for r in rows if r['code'] == 'COOLER_DEGRADATION'], names)
    assert rt.source_ready and set(rt.asset('HYD-01').runs) == {'COOLER_DEGRADATION'}


def test_무효_표본은_후보를_끊고_울린_경보는_해제하지_않는다(_runtime):
    rt = _runtime()
    for t in range(1000, 1010):
        _tick(rt, float(t), 48.0, ps1=160.0, fs1=7.5)
    rt.invalidate('HYD-02', 'PS1', 'INVALID_RECORD')
    run = rt.assets['HYD-02'].runs['PUMP_LEAKAGE']
    assert run.state.phase == 'RAISED' and run.quality['problems'] == {'PS1': 'INVALID_RECORD'}


def test_기울기는_정의가_쓰는_창에서만_나온다(_runtime):
    rt = _runtime({'COOLER_DEGRADATION', 'PUMP_LEAKAGE'})
    for t in range(1000, 1004):
        _tick(rt, float(t), 48.0 + (t - 1000) * 0.2, asset='HYD-01')
    assert rt.slope('HYD-01', 'TS1') == pytest.approx(0.2 / 20)     # 설비 초당(벽시계 1 s = 20 설비 초)
    assert rt.slope('HYD-01', 'VS1') is None                       # 팬 패턴이 없으면 VS1 기울기 창도 없다


def test_저장했다_되살리면_울린_경보와_이름을_가진다(_runtime):
    rt = _runtime()
    for t in range(1000, 1010):
        _tick(rt, float(t), 48.0, ps1=160.0, fs1=7.5)
    back = PatternRuntime.restore(rt.snapshot())
    assert back.assets['HYD-02'].runs['PUMP_LEAKAGE'].state.phase == 'RAISED' and back.names == rt.names and back.names['PUMP_LEAKAGE'] == '펌프 내부 누설'
    assert back.source_ready is False                               # 원천을 다시 읽기 전까지 새 후보를 세우지 않는다


@pytest.mark.parametrize('at', [float('nan'), 'x', None])
def test_유한한_초가_아닌_시각은_오류다(_runtime, at):
    with pytest.raises(ValueError):
        _runtime().observe('HYD-01', 'TS1', 48.0, at, now=1.0)
