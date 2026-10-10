"""schema.json 의 중복 금지 조건을 연습용 그래프의 고유 제약으로 만든다. 여러 번 돌려도 된다."""
from __future__ import annotations

import json
from pathlib import Path

from labkit.graph import graph_session

SCHEMA_FILE = Path(__file__).with_name("schema.json")


def constraint_statements(schema: dict) -> list[str]:
    statements = []
    for cls in schema["classes"]:
        for prop in cls.get("unique", []):
            name = f"{cls['name'].lower()}_{prop}_unique"
            statements.append(
                f"CREATE CONSTRAINT {name} IF NOT EXISTS FOR (n:{cls['name']}) REQUIRE n.{prop} IS UNIQUE"
            )
    return statements


def main() -> None:
    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    statements = constraint_statements(schema)
    with graph_session() as session:
        for statement in statements:
            session.run(statement).consume()
    print(f"고유 제약 {len(statements)}개를 확인했습니다(없던 것은 새로 만듦).")


if __name__ == "__main__":
    main()
