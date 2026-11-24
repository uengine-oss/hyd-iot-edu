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


@pytest.mark.parametrize('ahead', [0.001, 1.0], ids=['1 ms 늦게 찍힌 상태', '다음 틱의 상태가 먼저 옴'])
def test_평가_시각보다_늦은_상태가_먼저_와도_그_시각까지의_마지막_상태로_판정해_유지가_끊기지_않는다(_runtime, ahead):
    """G3b-4 · 06-4: 상태와 태그는 다른 토픽이라 처리 차례가 정해져 있지 않다. 감지기가 1초 밀려 다음 틱의 상태를 먼저 처리하면(또는 상태 시각이
    태그보다 1 ms 늦으면) 그 틱의 PLC 상태가 「미래 값」이 되어 틱마다 후보가 IDLE 로 돌아가 경보가 오르지 않았다. 평가 시각의 상태는 그 늦은
    표본이 밀어낸 바로 앞 표본이다 — 첫 틱(앞 표본이 없음)만 평가하지 못하고 그 뒤로는 유지가 이어져 한 번 울린다."""
    late = _runtime()
    events = [e for t in range(1000, 1012) for e in _tick(late, float(t), 48.0, ps1=160.0, fs1=7.5, status_at=t + ahead)]
    assert [(e['pattern'], e['state']) for e in events] == [('PUMP_LEAKAGE', 'RAISE')]
    assert late.assets['HYD-02'].runs['PUMP_LEAKAGE'].quality['status'] == 'VALID'


def test_평가_시각까지의_상태가_보호_정지였으면_늦게_온_운전_상태로_덮어_판정하지_않는다(_runtime):
    """같은 규칙의 반대쪽: 밀어낸 앞 표본이 「운전 중」이 아니면(펌프 누설은 운전 중에만 본다) 뒤에 온 운전 상태를 그 시각의 상태로 쓰지 않는다."""
    rt = _runtime()
    events = []
    for t in range(1000, 1012):
        events += _tick(rt, float(t), 48.0, ps1=160.0, fs1=7.5, state='RUN' if t % 2 else 'TRIP', status_at=t + 1.0)
    # 틱 t 의 평가가 읽는 상태는 틱 t-1 이 넣은 것(시각 t) — 짝 · 홀이 번갈아 운전 조건이 이어지지 않는다
    assert not [e for e in events if e['pattern'] == 'PUMP_LEAKAGE']


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


def test_지식의_패턴_기준이_바뀌면_다시_읽은_뒤의_감지가_그_기준으로_달라진다(_runtime, catalog):
    """T-7: 감지기는 15초마다 지식 지도의 이상 패턴을 다시 읽어 실행 목록을 바꾼다(main.refresh_catalog → 이 runtime.replace). 전에는 다시 읽기
    호출이 성공하는지만 봤고, 바뀐 정의로 감지가 실제로 달라지는지를 재는 시험이 없었다. 펌프 누설의 토출 압력 기준(지금 165 bar 미만)을
    150 bar 미만으로 고친 지식을 다시 읽으면, 전에 울리던 값(160 bar)에서는 울리지 않고 새 기준 아래(148 bar)에서 울린다."""
    rows, names = catalog
    rt = _runtime(['PUMP_LEAKAGE'])
    leaking = dict(ps1=160.0, fs1=7.5)
    assert [e['state'] for t in range(1000, 1010) for e in _tick(rt, float(t), 48.0, asset='HYD-02', **leaking)] == ['RAISE']
    changed = []
    for row in rows:
        if row['code'] == 'PUMP_LEAKAGE':
            pressure = [t for t in row['tests'] if t['operator'] == '<' and t['value'] == 165]
            assert len(pressure) == 1, row['tests']
            row = dict(row, tests=[dict(t, value=150) if t is pressure[0] else t for t in row['tests']])
            changed.append(row)
    assert rt.replace(changed, names) == []
    # 같은 값(160 bar)이 다른 설비에서: 새 기준(150 미만)에 닿지 않아 울리지 않는다. 이미 울린 HYD-02 의 경보는 울릴 때의 정의에 묶여 그대로다
    assert not [e for t in range(1000, 1010) for e in _tick(rt, float(t), 48.0, asset='HYD-03', **leaking)]
    assert rt.assets['HYD-02'].runs['PUMP_LEAKAGE'].state.phase == 'RAISED'
    assert [e['state'] for t in range(1010, 1020) for e in _tick(rt, float(t), 48.0, asset='HYD-03', ps1=148.0, fs1=7.5)] == ['RAISE']


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
