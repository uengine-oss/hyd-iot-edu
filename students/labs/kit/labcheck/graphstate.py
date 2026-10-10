"""연습용 그래프의 지금 상태를 읽는 질의 모음(확인용, 읽기만 한다)."""
from __future__ import annotations

from neo4j import Session

from labkit.graph import rows


def unique_constraints(session: Session) -> set[tuple[str, str]]:
    found = rows(session, "SHOW CONSTRAINTS YIELD type, labelsOrTypes, properties "
                          "WHERE type IN ['UNIQUENESS', 'NODE_KEY'] RETURN labelsOrTypes AS labels, properties")
    return {(row["labels"][0], row["properties"][0]) for row in found if len(row["properties"]) == 1}


def nodes(session: Session, label: str) -> list[dict]:
    return [row["props"] for row in rows(session, f"MATCH (n:{label}) RETURN properties(n) AS props")]


def duplicate_ids(session: Session, label: str) -> list[str]:
    return [row["id"] for row in rows(session, f"MATCH (n:{label}) WITH n.id AS id, count(*) AS c WHERE c > 1 RETURN id")]


def relations(session: Session, rel_type: str) -> list[dict]:
    """관계마다 양 끝의 이름표·id 와 관계 속성."""
    return rows(session, f"MATCH (a)-[r:{rel_type}]->(b) RETURN labels(a)[0] AS from_label, a.id AS from_id, a.name AS from_name, "
                         "labels(b)[0] AS to_label, b.id AS to_id, b.name AS to_name, properties(r) AS props")


def pairs(found: list[dict]) -> list[tuple[str, str]]:
    return [(row["from_id"], row["to_id"]) for row in found]


def counts(session: Session) -> dict[str, int]:
    return {
        "nodes": rows(session, "MATCH (n) RETURN count(n) AS c")[0]["c"],
        "relations": rows(session, "MATCH ()-[r]->() RETURN count(r) AS c")[0]["c"],
    }
