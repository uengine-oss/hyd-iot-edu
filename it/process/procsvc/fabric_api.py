"""A11 데이터 패브릭 미니 — 포털용 읽기 전용 API (hydcommon.fabric 을 HTTP로).

GET  /api/fabric/sources                         두 원천 연결 상태 · 표 목록 (실패는 사유)
GET  /api/fabric/sources/{source}/tables         표 · 열 · 주석 · 키
GET  /api/fabric/sources/{source}/tables/{table}/sample?limit=5
GET  /api/fabric/links                           클래스 ↔ 표 · 열 (온톨로지 식별 키 · InputData 원천 링크를 살아 있는 카탈로그에 대어)
GET  /api/fabric/queries                         정의된 교차 조회 목록
POST /api/fabric/query {asset, query, limit, sql}  두 원천 묶어 보기 (에이전트의 MCP 도구 fabric_query 와 같은 함수)

연결은 전용 읽기 계정만(ENTERPRISE_READ_DSN · TSDB_READ_DSN). process 의 쓰기 연결(SUPABASE_DSN · PG_DSN)은 쓰지 않는다.
상태 코드: 입력 오류 · 거부된 SQL 400, 필요한 원천이 모두 실패 503(사유 포함). 한 원천만 실패하면 200 + partial.
"""
from __future__ import annotations

import asyncio

import psycopg
from fastapi import HTTPException

from hydcommon.fabric import Fabric, FabricUnavailable, SOURCES, SourceUnavailable, SqlRejected, failure_reason


def register(app, *, driver_factory, fabric_factory=None):
    def graph(cypher, **params):
        from neo4j import unit_of_work

        @unit_of_work(timeout=5.0)
        def read(tx):
            return [r.data() for r in tx.run(cypher, **params)]
        driver = driver_factory()
        try:
            with driver.session() as session:
                return session.execute_read(read)
        finally:
            driver.close()

    make = fabric_factory or (lambda: Fabric(graph=graph))

    async def run(fn):
        try:
            return await asyncio.get_running_loop().run_in_executor(None, fn)
        except SqlRejected as exc:
            raise HTTPException(400, f'읽기 전용 SELECT만 실행합니다: {exc}') from exc
        except (FabricUnavailable, SourceUnavailable) as exc:
            raise HTTPException(503, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except (psycopg.Error, RuntimeError, OSError) as exc:     # one named source failed (tables · sample)
            raise HTTPException(503, failure_reason(exc)) from exc

    def known(source):
        if source not in SOURCES:
            raise HTTPException(404, f"등록된 원천이 아닙니다 (가능: {', '.join(SOURCES)})")

    @app.get('/api/fabric/sources')
    async def fabric_sources():
        return await run(lambda: make().sources())

    @app.get('/api/fabric/sources/{source}/tables')
    async def fabric_tables(source: str):
        known(source)
        return await run(lambda: make().tables(source))

    @app.get('/api/fabric/sources/{source}/tables/{table}/sample')
    async def fabric_sample(source: str, table: str, limit: int = 5):
        known(source)
        return await run(lambda: make().sample(source, table, limit))

    @app.get('/api/fabric/links')
    async def fabric_links():
        return await run(lambda: make().links())

    @app.get('/api/fabric/queries')
    async def fabric_queries():
        return make().queries()

    @app.post('/api/fabric/query')
    async def fabric_query(body: dict):
        limit = body.get('limit', 50)
        return await run(lambda: make().query(body.get('asset'), body.get('query') or 'asset', limit, body.get('sql')))
