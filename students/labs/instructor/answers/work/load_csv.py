"""설비·부품·센서 CSV 를 연습용 그래프에 넣는다. MERGE 로 넣으므로 다시 돌려도 늘지 않는다."""
from __future__ import annotations

import csv

from labkit.graph import graph_session
from labkit.settings import KIT_ROOT

DATA_DIR = KIT_ROOT / "day2" / "data"

LOAD_ASSETS = """
UNWIND $rows AS row
MERGE (a:Asset {id: row.asset_id})
SET a.name = row.name, a.line = row.line, a.model = row.model
"""
LOAD_COMPONENTS = """
UNWIND $rows AS row
MATCH (a:Asset {id: row.asset_id})
MERGE (c:Component {id: row.component_id})
SET c.name = row.name, c.kind = row.kind
MERGE (a)-[:HAS_COMPONENT]->(c)
"""
LOAD_SENSORS = """
UNWIND $rows AS row
MATCH (a:Asset {id: row.asset_id})
MATCH (c:Component {id: row.component_id})
MERGE (s:Sensor {id: row.sensor_id})
SET s.name = row.name, s.kind = row.kind, s.unit = row.unit, s.tag = row.tag
MERGE (a)-[:HAS_SENSOR]->(s)
MERGE (c)-[:MONITORED_BY]->(s)
"""


def read_csv(name: str) -> list[dict[str, str]]:
    with (DATA_DIR / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    steps = [("assets.csv", LOAD_ASSETS), ("components.csv", LOAD_COMPONENTS), ("sensors.csv", LOAD_SENSORS)]
    with graph_session() as session:
        for name, cypher in steps:
            rows = read_csv(name)
            session.run(cypher, rows=rows).consume()
            print(f"{name}: {len(rows)}줄 반영")


if __name__ == "__main__":
    main()
