"""감지기의 정의 읽기(it/detector/det/pattern_source.py) — 패턴이 없는 그래프. 시드 그래프의 감지 패턴 셋과 트립 이름을 실행 정의로 읽는 것은
test_neo4j_seed.test_감지기는_시드의_감지_패턴_셋을_그대로_실행_정의로_읽는다 가 본다."""
from det.pattern_source import read_patterns


def test_빈_그래프에서는_패턴이_없어_감지기_목록이_만들어지지_않는다(neo4j_graph):
    rows, names = read_patterns(neo4j_graph.driver)
    assert (rows, names) == ([], {})
