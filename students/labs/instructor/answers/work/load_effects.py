"""조치·성과 지표와 '조치 → 영향 받는 지표' 관계를 연습용 그래프에 넣는다.

방향(긍정·부정)과 이유만 넣는다. 자료의 note 칸에 있는 추정 숫자는 계산으로 확정한 값이 아니므로 넣지 않는다.
"""
from __future__ import annotations

import csv

from labkit.graph import graph_session
from labkit.settings import KIT_ROOT

DATA_DIR = KIT_ROOT / "day3" / "data"
EFFECTS = ("긍정", "부정")

LOAD_ACTIONS = "UNWIND $rows AS row MERGE (a:Action {id: row.action_id}) SET a.name = row.name, a.kind = row.kind"
LOAD_MEASURES = """
UNWIND $rows AS row
MERGE (m:Measure {id: row.measure_id})
SET m.name = row.name, m.unit = row.unit, m.better = row.better
"""
LOAD_EFFECTS = """
UNWIND $rows AS row
MATCH (a:Action {id: row.action_id})
MATCH (m:Measure {id: row.measure_id})
MERGE (a)-[r:AFFECTS]->(m)
SET r.effect = row.effect, r.basis = row.basis
"""


def read_csv(name: str) -> list[dict[str, str]]:
    with (DATA_DIR / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def effect_rows() -> list[dict[str, str]]:
    rows = read_csv("action_effects.csv")
    for number, row in enumerate(rows, start=2):
        if row["effect"] not in EFFECTS:
            raise ValueError(f"action_effects.csv {number}줄: effect 는 {EFFECTS} 가운데 하나여야 합니다(받은 값 {row['effect']!r}).")
    return [{key: row[key] for key in ("action_id", "measure_id", "effect", "basis")} for row in rows]


def main() -> None:
    with graph_session() as session:
        session.run(LOAD_ACTIONS, rows=read_csv("actions.csv")).consume()
        session.run(LOAD_MEASURES, rows=read_csv("measures.csv")).consume()
        effects = effect_rows()
        session.run(LOAD_EFFECTS, rows=effects).consume()
    print(f"조치 → 지표 관계 {len(effects)}개 반영")


if __name__ == "__main__":
    main()
