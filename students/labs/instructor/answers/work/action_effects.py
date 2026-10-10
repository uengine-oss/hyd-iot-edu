"""조치 하나가 어느 지표에 좋은 영향·나쁜 영향을 주는지 찾는다.

    python work/action_effects.py --action-id ACT-FAN-UP
"""
from __future__ import annotations

import argparse
import json

from labkit.graph import graph_session, rows

FIND_ACTION = "MATCH (a:Action {id: $id}) RETURN a.id AS id, a.name AS name"
FIND_EFFECTS = """
MATCH (a:Action {id: $id})-[r:AFFECTS]->(m:Measure)
RETURN m.id AS measure_id, m.name AS measure, r.effect AS effect, r.basis AS basis
ORDER BY m.id
"""


def action_effects(action_id: str) -> dict:
    with graph_session() as session:
        found = rows(session, FIND_ACTION, id=action_id)
        if not found:
            return {"found": False, "action": None, "positive": [], "negative": []}
        effects = rows(session, FIND_EFFECTS, id=action_id)

    def side(effect: str) -> list[dict]:
        return [{key: row[key] for key in ("measure_id", "measure", "basis")} for row in effects if row["effect"] == effect]

    return {"found": True, "action": found[0], "positive": side("긍정"), "negative": side("부정")}


def main() -> None:
    parser = argparse.ArgumentParser(description="조치가 지표에 주는 영향 찾기")
    parser.add_argument("--action-id", required=True)
    args = parser.parse_args()
    print(json.dumps(action_effects(args.action_id), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
