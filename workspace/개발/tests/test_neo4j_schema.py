"""온톨로지 스키마 원본(it/neo4j/v2/schema.json)과 그 생성물이 맞는지: 저장소의 생성물은 지금 생성기(workspace/개발/scripts/ontology_v2.py gen)의
출력과 바이트까지 같아야 한다 — 원본만 고치고 다시 만들지 않으면(또는 생성물을 손으로 고치면) 여기서 실패한다. 생성기는 파일에 쓰지 않고 메모리에서 부른다."""
import importlib.util

import pytest
from conftest import ROOT


def _tool():
    spec = importlib.util.spec_from_file_location('ontology_v2', ROOT / 'workspace' / '개발' / 'scripts' / 'ontology_v2.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TOOL = _tool()
V2, DOCS = ROOT / 'it' / 'neo4j' / 'v2', ROOT / 'workspace' / '개발' / '문서' / 'ontology'
GENERATED = [
    (V2 / 'constraints.cypher', TOOL.gen_constraints),
    (V2 / 'ontology-schema.ttl', TOOL.gen_ttl),
    (V2 / 'schema_prompt.md', TOOL.gen_prompt),
    (DOCS / 'ontology-classes.svg', TOOL.gen_svg),
    (DOCS / 'class-table.md', lambda s: '# 온톨로지 클래스 (생성 파일 — schema.json)\n\n' + TOOL.gen_class_table(s)),
]


@pytest.mark.parametrize('path, generate', GENERATED, ids=[p.name for p, _ in GENERATED])
def test_저장소의_생성물은_지금_스키마로_생성기를_돌린_결과와_같다(path, generate):
    assert path.read_bytes() == generate(TOOL.load_schema()).encode('utf-8')

