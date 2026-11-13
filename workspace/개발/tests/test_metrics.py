"""지표 글(common/hydcommon/metrics.py) — 라벨 값의 따옴표 · 줄바꿈 · 역슬래시를 이스케이프한다(G3b-28)."""
from hydcommon.metrics import Registry


def test_세는_값과_재는_값을_Prometheus_글로_낸다():
    reg = Registry()
    c, g = reg.counter('x_total', 'counted'), reg.gauge('y', 'level')
    c.inc(asset='HYD-01')
    c.inc(2, asset='HYD-01')
    g.set(1.5)
    out = reg.render()
    assert '# TYPE x_total counter' in out and 'x_total{asset="HYD-01"} 3' in out and 'y 1.5' in out


def test_라벨_값의_따옴표_줄바꿈_역슬래시가_글을_깨지_않는다():
    reg = Registry()
    reg.gauge('z', 'a\nb').set(1, tag='a"b\nc\\d')
    lines = reg.render().strip().splitlines()
    assert lines == ['# HELP z a\\nb', '# TYPE z gauge', 'z{tag="a\\"b\\nc\\\\d"} 1']   # 줄바꿈이 새 줄을 만들지 않는다
