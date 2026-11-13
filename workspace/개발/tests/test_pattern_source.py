"""감지기의 정의 읽기(it/detector/det/pattern_source.py) — 실제 시드 그래프에서 held 패턴 셋과 모든 패턴 이름을 읽는다(G3b-8 · 24)."""
from det.pattern_source import read_patterns
from det.patterns import compile_catalog


def test_시드_그래프에서_held_패턴_셋을_감지기가_실행할_수_있게_읽는다(seeded_graph):
    rows, names = read_patterns(seeded_graph.driver)
    catalog = compile_catalog(rows, 'lite', 20.0)
    assert set(catalog) == {'COOLER_DEGRADATION', 'PUMP_LEAKAGE', 'FAN_VIBRATION'}
    assert catalog['COOLER_DEGRADATION'].rule.atoms and all(r['tests'] for r in rows)


def test_트립_패턴까지_모든_패턴의_이름을_읽는다(seeded_graph):
    _, names = read_patterns(seeded_graph.driver)
    assert {'COOLER_DEGRADATION', 'PUMP_LEAKAGE', 'FAN_VIBRATION', 'OVERHEAT_TRIP', 'LOW_PRESSURE_TRIP', 'HIGH_VIBRATION_TRIP'} <= set(names)
    assert all(isinstance(v, str) and v and not v.isascii() for v in names.values())


def test_빈_그래프에서는_패턴이_없어_감지기_목록이_만들어지지_않는다(neo4j_graph):
    rows, names = read_patterns(neo4j_graph.driver)
    assert (rows, names) == ([], {})
