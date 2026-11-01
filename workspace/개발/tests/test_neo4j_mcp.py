"""수업 neo4j 조회 도구(common/hydcommon/neo4j_mcp.py) — 읽기 전용 Cypher 와 스키마 조회만 내고, 큰 결과는 「전체가 아님」 표시와 함께 자른다.

- bounded_result: 행 100 · 전체 16,000자 · 칸 1,200자 · 목록 64개 · 깊이 12 를 넘으면 잘라 truncated 와 원래 크기를 단다(조용히 버리지 않는다).
- read: Neo4j 가 컴파일한 질의 종류(EXPLAIN)로 읽기만 실행한다 — 쓰기 문장 · 쓰기 프로시저는 실행 전에 거절(글자 검사가 아니다).
- schema: 구간 · 범위를 검사하고 APOC 메타데이터를 쪽으로 나눈다.
- create_server: 도구는 둘(read_neo4j_cypher · get_neo4j_schema), 쓰기 도구는 없다.
실제 테스트 그래프(neo4j_graph · seeded_graph)에 비동기 드라이버로 붙는다(dmn-mcp 가 /neo4j/mcp 로 내는 것과 같은 함수).
"""
import asyncio
import json

import pytest
from neo4j import AsyncGraphDatabase

from hydcommon import neo4j_mcp as nm


@pytest.mark.parametrize('rows', [[], [{'n': 1}], [{'n': i} for i in range(nm.MAX_ROWS)]], ids=['빈 결과', '한 행', '딱 100행'])
def test_한도_안의_결과는_행_목록_그대로다(rows):
    assert json.loads(nm.bounded_result(rows)) == rows


def _cut(rows, **kw):
    out = json.loads(nm.bounded_result(rows, **kw))
    assert isinstance(out, dict) and out['truncated'] is True and '전체 결과가 아닙니다' in out['hint']
    return out


def test_100행을_넘으면_100행과_적어도_몇_행인지를_준다():
    out = _cut([{'n': i} for i in range(nm.MAX_ROWS + 1)])
    assert (out['returned_rows'], out['available_rows_at_least'], out['rows'][-1]) == (100, 101, {'n': 99})


def test_더_있다는_표시가_오면_행이_적어도_잘린_결과다():
    out = _cut([{'n': 1}], more=True)
    assert (out['returned_rows'], out['available_rows_at_least']) == (1, 2)


@pytest.mark.parametrize('value, check', [
    ('가' * (nm.MAX_CELL_CHARS + 1), lambda c: c['preview'] == '가' * nm.MAX_CELL_CHARS and c['original_chars'] == nm.MAX_CELL_CHARS + 1),
    (list(range(nm.MAX_LIST + 1)), lambda c: c['items'] == list(range(nm.MAX_LIST)) and c['original_count'] == nm.MAX_LIST + 1),
    ({'k': list(range(nm.MAX_LIST + 1)), 'keep': 'x'}, lambda c: c['k']['original_count'] == nm.MAX_LIST + 1 and c['keep'] == 'x'),
], ids=['긴 글 칸', '긴 목록', '안쪽 긴 목록'])
def test_칸이_한도를_넘으면_그_칸만_자르고_원래_크기를_단다(value, check):
    out = _cut([{'v': value}])
    cell = out['rows'][0]['v']
    assert (cell.get('k') or cell)['truncated'] is True and check(cell)


@pytest.mark.parametrize('length', [nm.MAX_CELL_CHARS], ids=['딱 1200자'])
def test_한도와_같은_칸은_자르지_않는다(length):
    assert json.loads(nm.bounded_result([{'v': 'a' * length}])) == [{'v': 'a' * length}]


def test_깊이_12를_넘는_값은_필요한_속성만_돌려_달라는_표시로_바꾼다():
    deep = 'bottom'
    for _ in range(14):
        deep = {'d': deep}
    out = _cut([{'v': deep}])
    node = out['rows'][0]['v']
    while 'd' in node:
        node = node['d']
    assert node['reason'] == 'nested_value'


def test_전체_글자_한도를_넘기_전에서_행을_멈춘다():
    rows = [{'v': 'x' * 1000} for _ in range(30)]                    # 한 행 약 1,010자 — 16,000자 한도 안에는 15행
    out = _cut(rows)
    assert 10 < out['returned_rows'] < 30 and len(nm.dumps(out['rows'])) <= nm.MAX_CHARS - 600


# ---------------------------------------------------------------- 실제 그래프
def _run(graph, fn):
    async def go():
        driver = AsyncGraphDatabase.driver(graph.uri, auth=graph.auth)
        try:
            return await fn(driver)
        finally:
            await driver.close()
    return asyncio.run(go())


def test_읽기_질의는_인자와_함께_실행해_행을_준다(neo4j_graph):
    out = _run(neo4j_graph, lambda d: nm.read(d, 'UNWIND range(1, $n) AS i RETURN i ORDER BY i', {'n': 3}))
    assert json.loads(out) == [{'i': 1}, {'i': 2}, {'i': 3}]


@pytest.mark.parametrize('n, truncated', [(100, False), (101, True), (500, True)], ids=['100행', '101행', '500행'])
def test_읽기_질의가_100행을_넘으면_101행까지만_가져와_잘린_결과로_준다(neo4j_graph, n, truncated):
    out = json.loads(_run(neo4j_graph, lambda d: nm.read(d, f'UNWIND range(1, {n}) AS i RETURN i')))
    if truncated:
        assert out['truncated'] is True and out['returned_rows'] == 100 and out['available_rows_at_least'] == 101
    else:
        assert len(out) == 100


@pytest.mark.parametrize('query', [
    "CREATE (n:Fo2Probe {id: 'x'}) RETURN n",
    "MERGE (n:Fo2Probe {id: 'x'}) RETURN n",
    "MATCH (n) DETACH DELETE n",
    "CALL apoc.create.node(['Fo2Probe'], {id: 'x'}) YIELD node RETURN node",       # 쓰기 프로시저 — 글자로는 CREATE 가 없다
], ids=['CREATE', 'MERGE', 'DELETE', '쓰기 프로시저'])
def test_쓰기_질의는_실행하지_않고_거절한다(seeded_graph, query):
    before = seeded_graph.query('MATCH (n) RETURN count(n) AS n')[0]['n']
    with pytest.raises(ValueError, match='읽기 전용 조회만 허용합니다'):
        _run(seeded_graph, lambda d: nm.read(d, query))
    assert seeded_graph.query('MATCH (n) RETURN count(n) AS n')[0]['n'] == before
    assert seeded_graph.query('MATCH (n:Fo2Probe) RETURN count(n) AS n')[0]['n'] == 0


@pytest.mark.parametrize('query', ['', '   ', None], ids=['빈 글', '공백', '없음'])
def test_빈_조회문은_거절한다(neo4j_graph, query):
    with pytest.raises(ValueError, match='조회문이 필요합니다'):
        _run(neo4j_graph, lambda d: nm.read(d, query))


def test_스키마_이름_목록은_쪽으로_나누고_다음_쪽_위치를_준다(seeded_graph):
    first = json.loads(_run(seeded_graph, lambda d: nm.schema(d, limit=3)))
    labels = sorted({r['l'] for r in seeded_graph.query('MATCH (n) UNWIND labels(n) AS l RETURN DISTINCT l')})
    assert [r['name'] for r in first['rows']] == labels[:3] and first['next_offset'] == 3
    last = json.loads(_run(seeded_graph, lambda d: nm.schema(d, offset=len(labels) - 1, limit=3)))
    assert [r['name'] for r in last['rows']] == labels[-1:] and last['next_offset'] is None
    props = json.loads(_run(seeded_graph, lambda d: nm.schema(d, name='Sensor', section='properties')))
    assert {'id', 'tag', 'unit'} <= {r['property'] for r in props['rows']}


@pytest.mark.parametrize('kw, word', [
    ({'section': 'indexes'}, '스키마 구간'),
    ({'limit': 0}, '스키마 구간'),
    ({'limit': 51}, '스키마 구간'),
    ({'offset': -1}, '스키마 구간'),
    ({'offset': 1.5}, '스키마 구간'),
    ({'name': ' '}, '스키마 이름'),
    ({'name': 'x' * 201}, '스키마 이름'),
    ({'section': 'properties'}, '상세 조회에는 목록의 이름이 필요합니다'),
], ids=['모르는 구간', 'limit 0', 'limit 51', 'offset 음수', 'offset 소수', '이름 공백', '이름 201자', '상세에 이름 없음'])
def test_스키마_조회_범위가_어긋나면_그래프에_묻지_않고_거절한다(kw, word):
    with pytest.raises(ValueError, match=word):
        asyncio.run(nm.schema(None, **kw))                     # 드라이버 없이 — 검사가 먼저다


def test_도구_서버는_읽기_도구_둘만_낸다(neo4j_graph):
    from fastmcp import Client

    async def go(driver):
        async with Client(nm.create_server(driver)) as client:
            tools = {t.name: t for t in await client.list_tools()}
            result = await client.call_tool('read_neo4j_cypher', {'query': 'RETURN 1 AS one'})
            return tools, result
    tools, result = _run(neo4j_graph, go)
    assert set(tools) == {'read_neo4j_cypher', 'get_neo4j_schema'}
    assert all(t.annotations.readOnlyHint is True and t.annotations.destructiveHint is False for t in tools.values())
    assert json.loads(result.content[0].text) == [{'one': 1}]
