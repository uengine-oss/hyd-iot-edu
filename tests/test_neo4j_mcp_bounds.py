import asyncio
import json
import os

import pytest
from fastmcp import Client
from neo4j import AsyncGraphDatabase

from hydcommon import neo4j_mcp as adapter
from test_manual_revision_history import graph, URI


def test_small_result_preserves_unicode_nulls_and_empty_lists():
    rows = [{'name': '팬 온도', 'empty': [], 'missing': None}]
    text = adapter.bounded_result(rows)
    assert json.loads(text) == rows and '팬 온도' in text and '\\u' not in text


def test_long_cells_and_collections_never_silently_disappear():
    rows = [{'plan': '한글원문' * 40000, 'ids': list(range(150)), 'status': 'ACTIVE'}]
    text = adapter.bounded_result(rows)
    out = json.loads(text)
    assert out['truncated'] and len(text) <= adapter.MAX_CHARS
    assert out['rows'][0]['ids']['original_count'] == 150
    assert out['rows'][0]['ids']['items'] == list(range(adapter.MAX_LIST))
    assert out['rows'][0]['plan']['original_chars'] == 160000
    assert out['rows'][0]['status'] == 'ACTIVE'
    assert 'substring' in out['hint']


def test_whole_response_budget_and_rows_are_explicit():
    rows = [{'text': '대상' * 500, 'id': i} for i in range(150)]
    out = adapter.bounded_result(rows)
    assert len(out) <= adapter.MAX_CHARS and json.loads(out)['truncated']
    assert json.loads(out)['returned_rows'] < 100
    # A single extremely wide row also gets an explicit marker, never invalid JSON.
    out = adapter.bounded_result([{str(i): '값' * 100 for i in range(500)}])
    assert len(out) <= adapter.MAX_CHARS and json.loads(out)['truncated']


def test_real_mcp_compiled_read_guard_and_result_limits(graph):
    """The exposed MCP tool itself, actual Neo4j query compilation and writes refused before execution."""
    before = graph.run('MATCH (n) RETURN count(n) AS n').single()['n']
    async def run():
        async with AsyncGraphDatabase.driver(URI, auth=('neo4j', os.environ['HYD_MANUAL_NEO4J_PASSWORD'])) as driver:
            async with Client(adapter.create_server(driver)) as client:
                tools = await client.list_tools()
                assert {t.name for t in tools} == {'get_neo4j_schema', 'read_neo4j_cypher'}
                assert all(t.annotations.readOnlyHint for t in tools)
                result = await client.call_tool('read_neo4j_cypher', {'query': 'RETURN $name AS name', 'params': {'name': '한글'}})
                assert json.loads(result.content[0].text) == [{'name': '한글'}]
                result = await client.call_tool('read_neo4j_cypher', {'query': 'UNWIND range(1,150) AS i RETURN i ORDER BY i'})
                out = json.loads(result.content[0].text)
                assert out['truncated'] and out['returned_rows'] == 100
                result = await client.call_tool('read_neo4j_cypher', {'query': 'RETURN range(1,150) AS ids'})
                assert json.loads(result.content[0].text)['rows'][0]['ids']['original_count'] == 150
                # Words inside string literals are harmless; a regex used to reject this valid read.
                result = await client.call_tool('read_neo4j_cypher', {'query': "RETURN 'CREATE DELETE SET' AS example"})
                assert json.loads(result.content[0].text)[0]['example'] == 'CREATE DELETE SET'
                for query in ('CREATE (:MustNotExist {id:1})', 'MATCH (n) DETACH DELETE n', 'CALL db.createLabel("ForbiddenLabel")'):
                    with pytest.raises(Exception, match='읽기 전용|ProcedureNotFound'):
                        await client.call_tool('read_neo4j_cypher', {'query': query})
    asyncio.run(run())
    assert graph.run('MATCH (n) RETURN count(n) AS n').single()['n'] == before


def test_registered_adapter_launches_from_a_task_directory_with_the_worker_interpreter(graph, tmp_path):
    from procsvc import mcp_check
    from worker import bridge
    import sys
    spec = {'command': 'python', 'args': ['-m', 'hydcommon.neo4j_mcp'],
            'env': {'NEO4J_URI': URI, 'NEO4J_USERNAME': 'neo4j', 'NEO4J_PASSWORD': os.environ['HYD_MANUAL_NEO4J_PASSWORD']},
            'cwd': str(tmp_path)}
    stdio, _ = bridge.servers_of({'mcpServers': {'neo4j': spec}})
    assert stdio[0].command == sys.executable and os.path.isabs(stdio[0].args[0])
    result = mcp_check.call(dict(mcp_check.normalize(spec), cwd=str(tmp_path)), 'read_neo4j_cypher', {'query': "RETURN '새 작업 폴더' AS name"}, timeout=15)
    assert result['status'] == 'ok', result
    assert '새 작업 폴더' in json.dumps(result, ensure_ascii=False)
