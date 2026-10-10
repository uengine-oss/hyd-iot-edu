"""준비된 연습용 그래프를 넣는다(6일차). 2~4일차 랩을 마친 상태와 같은 그래프가 된다.

    python -m labkit.prepared_graph

몇 번을 돌려도 같은 그래프가 된다(이미 있는 것은 다시 만들지 않는다).
"""
from __future__ import annotations

from pathlib import Path

from labkit.graph import graph_session
from labkit.settings import KIT_ROOT

PREPARED_GRAPH_FILE = KIT_ROOT / "day6" / "data" / "prepared_graph.cypher"


def statements(path: Path = PREPARED_GRAPH_FILE) -> list[str]:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if not line.startswith("//")]
    return [part.strip() for part in "\n".join(lines).split(";\n") if part.strip()]


def load() -> int:
    todo = statements()
    with graph_session() as session:
        for statement in todo:
            session.run(statement).consume()
    return len(todo)


def main() -> None:
    count = load()
    print(f"준비된 그래프를 넣었습니다(문장 {count}개). http://127.0.0.1:17474 에서 확인하세요.")


if __name__ == "__main__":
    main()
