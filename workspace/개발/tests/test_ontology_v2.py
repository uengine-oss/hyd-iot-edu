"""온톨로지 생성 · 검사 도구(workspace/개발/scripts/ontology_v2.py) — 생성물이 생성기 결과와 같고, 검사가 스키마가 선언한 것을 실제로 재는가."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import ontology_v2 as onto  # noqa: E402


@pytest.fixture(scope='module')
def schema():
    return onto.load_schema()


@pytest.mark.parametrize('value, paths', [
    ({'a': '정상 문장', 'b': ['둘째']}, []),
    ({'a': 'control=PLC ??, work_order=????'}, ['$.a']),
    ({'c': [{'d': '깨진 � 글자'}]}, ['$.c[0].d']),
], ids=['깨끗함', '물음표_둘', '대체_문자'])
def test_원본의_깨진_글자_자리를_좌표로_찾는다(value, paths):
    assert onto.broken_text(value) == paths


def test_지금_스키마_원본에는_깨진_글자가_없다(schema):
    assert onto.broken_text(schema) == []


def test_제약은_클래스마다_한_번만_만들고_손으로_더한_중복이_없다(schema):
    lines = [l for l in onto.gen_constraints(schema).splitlines() if l.startswith('CREATE CONSTRAINT')]
    targets = [l.split(' FOR ')[1] for l in lines]
    assert len(targets) == len(set(targets))
    assert not [l for l in lines if 'execution_projection_id' in l or 'case_projection_id' in l]


def test_전문_검색_색인은_고장_유형_조치_부품_패턴_센서_이름을_찾고_옛_색인을_남기지_않는다(schema):
    text = onto.gen_constraints(schema)
    create = next(l for l in text.splitlines() if l.startswith('CREATE FULLTEXT INDEX ont_names'))
    labels = set(create.split('FOR (n:')[1].split(')')[0].split('|'))
    assert {'FailureMode', 'Skill', 'Part', 'AnomalyPattern', 'Sensor', 'Cause'} <= labels
    assert not labels & {'Incident', 'WorkItem', 'ExecutionActor', 'FlowNode'}
    assert text.index('DROP INDEX ont_names IF EXISTS;') < text.index(create)


def test_OWL_의_같은_이름_속성은_클래스마다_자기_설명과_허용값을_적는다(schema):
    ttl = onto.gen_ttl(schema)
    block = ttl[ttl.index('hyd:kind a owl:DatatypeProperty'):].split(' .\n', 1)[0]
    kinds = {c['name']: p for c in schema['classes'] for p in c['properties'] if p['name'] == 'kind'}
    assert len(kinds) > 1
    for cname, p in kinds.items():
        assert cname in block
        for v in p.get('values') or []:
            assert str(v) in block


def rel(t, a, b):
    return {'type': t, 'a': a, 'b': b, 'la': [], 'lb': [], 'props': {}}


@pytest.mark.parametrize('card, rows, bad', [
    ('1:N', [rel('R', 'p1', 'c1'), rel('R', 'p2', 'c1')], 1),
    ('1:N', [rel('R', 'p1', 'c1'), rel('R', 'p1', 'c2')], 0),
    ('N:1', [rel('R', 'c1', 'p1'), rel('R', 'c1', 'p2')], 1),
    ('N:1', [rel('R', 'c1', 'p1'), rel('R', 'c2', 'p1')], 0),
    ('1:1', [rel('R', 'a', 'x'), rel('R', 'a', 'y'), rel('R', 'b', 'y')], 2),
    ('N:M', [rel('R', 'a', 'x'), rel('R', 'a', 'y'), rel('R', 'b', 'y')], 0),
], ids=['1N_부모_둘', '1N_정상', 'N1_목적지_둘', 'N1_정상', '11_양쪽_위반', 'NM_검사_없음'])
def test_검사는_선언한_다중도를_실제로_잰다(card, rows, bad):
    assert len(onto.cardinality_violations(rows, {'R': {'cardinality': card}})) == bad


def test_생성물은_지금_생성기_결과와_같다(schema):
    """it/neo4j/v2 의 생성물 셋과 workspace/개발/문서/ontology 의 그림 · 표 — 손으로 고치거나 생성기만 바뀐 채로 남지 않는다."""
    for path, text in ((onto.V2 / 'constraints.cypher', onto.gen_constraints(schema)), (onto.V2 / 'ontology-schema.ttl', onto.gen_ttl(schema)),
                       (onto.V2 / 'schema_prompt.md', onto.gen_prompt(schema)), (onto.DOCS / 'ontology-classes.svg', onto.gen_svg(schema)),
                       (onto.DOCS / 'class-table.md', '# 온톨로지 클래스 (생성 파일 — schema.json)\n\n' + onto.gen_class_table(schema))):
        assert path.read_text(encoding='utf-8') == text, f'{path.name} 이 생성기 결과와 다르다 — ontology_v2.py gen 으로 다시 만든다'


def test_kg_seed_가_넣은_수업_그래프는_스키마를_지킨다(seeded_graph, schema):
    with seeded_graph.driver.session() as session:
        nodes, rels, skipped = onto.base_scope(*onto.read_rows(session))
    assert nodes and not skipped
    assert onto.validate(nodes, rels, schema) == []
