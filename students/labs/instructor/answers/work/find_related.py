"""설비 번호나 이름으로 그 설비의 센서와 부품을 찾는다.

    python work/find_related.py --id CL-01
    python work/find_related.py --name "소형 냉각장치 1호" --limit 2
"""
from __future__ import annotations

import argparse
import json

from labkit.graph import graph_session, rows

FIND_ASSET = "MATCH (a:Asset) WHERE a.id = $id OR a.name = $name RETURN a.id AS id, a.name AS name LIMIT 1"
FIND_SENSORS = """
MATCH (a:Asset {id: $id})-[:HAS_SENSOR]->(s:Sensor)
RETURN s.id AS id, s.name AS name, s.kind AS kind, s.unit AS unit, s.tag AS tag
ORDER BY s.id LIMIT $limit
"""
FIND_COMPONENTS = """
MATCH (a:Asset {id: $id})-[:HAS_COMPONENT]->(c:Component)
RETURN c.id AS id, c.name AS name, c.kind AS kind
ORDER BY c.id LIMIT $limit
"""
DEFAULT_LIMIT = 50


def find_related(asset_id: str | None = None, name: str | None = None, limit: int = DEFAULT_LIMIT) -> dict:
    if not asset_id and not name:
        raise ValueError("설비 번호(--id)나 이름(--name) 가운데 하나는 주어야 합니다.")
    if limit < 1:
        raise ValueError("--limit 은 1 이상이어야 합니다.")
    with graph_session() as session:
        found = rows(session, FIND_ASSET, id=asset_id, name=name)
        if not found:
            return {"found": False, "asset": None, "sensors": [], "components": []}
        asset = found[0]
        return {
            "found": True,
            "asset": asset,
            "sensors": rows(session, FIND_SENSORS, id=asset["id"], limit=limit),
            "components": rows(session, FIND_COMPONENTS, id=asset["id"], limit=limit),
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="설비의 센서와 부품 찾기")
    parser.add_argument("--id")
    parser.add_argument("--name")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    args = parser.parse_args()
    try:
        result = find_related(args.id, args.name, args.limit)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
