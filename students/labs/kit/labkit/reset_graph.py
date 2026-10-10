"""연습용 그래프를 비운다(노드·관계·제약 모두). 처음부터 다시 해 보고 싶을 때 쓴다.

    python -m labkit.reset_graph --yes
"""
from __future__ import annotations

import argparse

from labkit.graph import graph_session, rows
from labkit.settings import neo4j_settings

LAB_BOLT_PORT = ":17687"


def reset() -> dict[str, int]:
    uri, _, _ = neo4j_settings()
    if not uri.endswith(LAB_BOLT_PORT):
        raise SystemExit(f"연습용 그래프 주소가 아닙니다({uri}). 포트 17687 인 연습용 그래프만 비울 수 있습니다.")
    with graph_session() as session:
        deleted = session.run("MATCH (n) DETACH DELETE n").consume().counters.nodes_deleted
        constraints = [row["name"] for row in rows(session, "SHOW CONSTRAINTS YIELD name")]
        for name in constraints:
            session.run(f"DROP CONSTRAINT `{name}`").consume()
    return {"nodes_deleted": deleted, "constraints_dropped": len(constraints)}


def main() -> None:
    parser = argparse.ArgumentParser(description="연습용 그래프 비우기")
    parser.add_argument("--yes", action="store_true", help="정말 비울 때 붙인다")
    args = parser.parse_args()
    if not args.yes:
        raise SystemExit("연습용 그래프의 모든 자료가 지워집니다. 정말 비우려면 --yes 를 붙여 다시 실행하세요.")
    result = reset()
    print(f"연습용 그래프를 비웠습니다. 노드 {result['nodes_deleted']}개, 제약 {result['constraints_dropped']}개.")


if __name__ == "__main__":
    main()
