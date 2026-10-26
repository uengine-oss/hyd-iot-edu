"""Education adapter for the mcp-neo4j-cypher read/schema tool contract.

0.4.1 silently drops lists >=128 and cuts JSON tokens without a marker. This adapter
keeps small results compatible, bounds large results explicitly, and checks Neo4j's
compiled query type before executing. It never exposes a write tool.
"""
import json
import os

MAX_ROWS = 100
MAX_CHARS = 16000
MAX_CELL_CHARS = 1200
MAX_LIST = 64


def local_launch(command, args):
    """Use this installation, even when the CLI starts the server from a per-task workspace."""
    if command in ('python', 'python3') and args == ['-m', 'hydcommon.neo4j_mcp']:
        import sys
        return sys.executable, [os.path.abspath(__file__)]
    return command, args


def dumps(value):
    return json.dumps(value, ensure_ascii=False, default=str, separators=(',', ':'))


def bounded_result(rows, *, more=False):
    truncated = more
    def cell(value, depth=0):
        nonlocal truncated
        if depth > 12:
            truncated = True
            return {'truncated': True, 'reason': 'nested_value', 'hint': '필요한 속성만 RETURN 하세요'}
        if isinstance(value, str) and len(value) > MAX_CELL_CHARS:
            truncated = True
            return {'preview': value[:MAX_CELL_CHARS], 'truncated': True, 'original_chars': len(value)}
        if isinstance(value, dict):
            return {str(k): cell(v, depth+1) for k,v in value.items()}
        if isinstance(value, (list, tuple)):
            items = [cell(v, depth+1) for v in value[:MAX_LIST]]
            if len(value) > MAX_LIST:
                truncated = True
                return {'items': items, 'truncated': True, 'original_count': len(value)}
            return items
        return value
    kept = []
    used = 2
    for row in rows[:MAX_ROWS]:
        clean = cell(row)
        size = len(dumps(clean)) + 1
        if used + size > MAX_CHARS - 600:
            truncated = True
            break
        kept.append(clean)
        used += size
    truncated |= len(rows) > MAX_ROWS
    if not truncated:
        return dumps(kept)
    return dumps({'rows': kept, 'truncated': True, 'returned_rows': len(kept),
                  'available_rows_at_least': len(rows) + int(more),
                  'limits': {'rows': MAX_ROWS, 'characters': MAX_CHARS, 'cell_characters': MAX_CELL_CHARS, 'list_items': MAX_LIST},
                  'hint': '전체 결과가 아닙니다. 필요한 속성·조건과 ORDER BY/SKIP/LIMIT으로 나눠 조회하세요. 긴 문자열은 substring으로 필요한 구간만 조회하세요.'})


async def read(driver, query, params=None, *, database='neo4j', timeout=30):
    from neo4j import Query
    if not isinstance(query, str) or not query.strip():
        raise ValueError('조회문이 필요합니다')
    async with driver.session(database=database, default_access_mode='READ') as session:
        # A regex misses write procedures. EXPLAIN compiles but never runs them.
        plan = await session.run(Query('EXPLAIN ' + query, timeout=timeout), params or {})
        summary = await plan.consume()
        if summary.query_type != 'r':
            raise ValueError('읽기 전용 조회만 허용합니다. 승인 뒤 실행은 프로세스가 담당합니다')
        result = await session.run(Query(query, timeout=timeout), params or {})
        records = await result.fetch(MAX_ROWS + 1)
        rows = [r.data() for r in records]
        # Only fetched records are materialised; no r.data() over an unbounded result.
        return bounded_result(rows[:MAX_ROWS], more=len(rows) > MAX_ROWS)


def create_server(driver, *, database='neo4j', timeout=30):
    from fastmcp import FastMCP
    app = FastMCP('hyd-neo4j-read')
    annotations = {'readOnlyHint': True, 'destructiveHint': False, 'idempotentHint': True}
    @app.tool(annotations=annotations)
    async def read_neo4j_cypher(query: str, params: dict | None = None) -> str:
        """읽기 전용 Cypher. 큰 응답은 truncated 표시와 함께 제한하므로 필요한 속성과 범위만 조회하세요."""
        return await read(driver, query, params, database=database, timeout=timeout)
    @app.tool(annotations=annotations)
    async def get_neo4j_schema() -> str:
        """APOC로 현재 그래프 구조를 조회합니다. 큰 구조는 필요한 label의 속성만 추가 조회하세요."""
        return await read(driver, 'CALL apoc.meta.schema() YIELD value RETURN value', database=database, timeout=timeout)
    return app


def main():
    from neo4j import AsyncGraphDatabase
    driver = AsyncGraphDatabase.driver(os.environ['NEO4J_URI'],
        auth=(os.getenv('NEO4J_USERNAME', 'neo4j'), os.environ['NEO4J_PASSWORD']))
    create_server(driver, database=os.getenv('NEO4J_DATABASE', 'neo4j')).run(transport='stdio')


if __name__ == '__main__':
    main()
