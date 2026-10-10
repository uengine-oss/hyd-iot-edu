"""연습용 지식 그래프(Neo4j) 연결."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from neo4j import GraphDatabase, Session

from labkit.settings import neo4j_settings


@contextmanager
def graph_session() -> Iterator[Session]:
    """`with graph_session() as session: session.run(...)` 로 쓴다. 끝나면 연결을 닫는다."""
    uri, user, password = neo4j_settings()
    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        driver.verify_connectivity()
        with driver.session() as session:
            yield session
    finally:
        driver.close()


def rows(session: Session, cypher: str, **params: Any) -> list[dict[str, Any]]:
    """질의를 돌려 결과 줄을 사전 목록으로 돌려준다."""
    return [record.data() for record in session.run(cypher, **params)]
