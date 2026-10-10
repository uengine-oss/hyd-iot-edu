"""현재 값(연습용 DB)과 고장 지식(연습용 그래프)을 설비 번호로 이어서 찾는다.

    python work/lookup.py current --asset-id CL-01
    python work/lookup.py failure --asset-id CL-01 --name 과열

찾지 못하면 지어내지 않고 found=false 와 무엇이 없는지(missing)를 돌려준다.
"""
from __future__ import annotations

import argparse
import json
import operator

from labkit.db import connect
from labkit.graph import graph_session, rows

DEFAULT_KIND = "출구 온도"
OPERATORS = {">": operator.gt, ">=": operator.ge, "<": operator.lt, "<=": operator.le}
SOURCE = "{doc: r.doc, section: r.section, line: r.line, quote: r.quote, candidate_id: r.candidate_id}"

FIND_ASSET = "MATCH (a:Asset {id: $asset_id}) RETURN a.id AS id"
FIND_SENSOR = """
MATCH (:Asset {id: $asset_id})-[:HAS_SENSOR]->(s:Sensor {kind: $kind})
RETURN s.id AS sensor_id, s.tag AS tag, s.kind AS kind, s.unit AS unit
"""
LATEST_READING = "SELECT value, measured_at FROM readings WHERE tag = %s ORDER BY measured_at DESC LIMIT 1"
FIND_SYMPTOMS = f"""
MATCH (:Asset {{id: $asset_id}})-[:CAN_HAVE]->(f:FailureMode)<-[r:INDICATES]-(s:Symptom)
WHERE $failure IS NULL OR f.name = $failure
RETURN f.id AS failure_id, f.name AS failure_mode, s.name AS symptom, s.sensor_kind AS sensor_kind,
       s.operator AS operator, s.threshold AS threshold, s.unit AS unit, {SOURCE} AS source
ORDER BY r.candidate_id
"""
FIND_FAILURE = "MATCH (:Asset {id: $asset_id})-[:CAN_HAVE]->(f:FailureMode {name: $name}) RETURN f.id AS failure_id"
FIND_CAUSES = f"""
MATCH (c:Cause)-[r:CAUSES]->(:FailureMode {{id: $failure_id}})
RETURN c.name AS name, {SOURCE} AS source ORDER BY r.candidate_id
"""
FIND_ACTIONS = f"""
MATCH (:FailureMode {{id: $failure_id}})-[r:REMEDIED_BY]->(a:Action)
RETURN a.id AS id, a.name AS name, {SOURCE} AS source ORDER BY r.candidate_id
"""


def not_found(asset_id: str, missing: str, reason: str) -> dict:
    return {"found": False, "asset_id": asset_id, "missing": [missing], "reason": reason}


def latest_reading(tag: str) -> dict | None:
    with connect() as conn:
        return conn.execute(LATEST_READING, (tag,)).fetchone()


def knowledge(session, failure_id: str) -> dict:
    return {
        "causes": rows(session, FIND_CAUSES, failure_id=failure_id),
        "actions": rows(session, FIND_ACTIONS, failure_id=failure_id),
    }


def current_status(asset_id: str, kind: str = DEFAULT_KIND) -> dict:
    """설비의 현재 값을 읽고, 그 값이 넘긴 판정 기준과 이어진 원인·조치를 함께 돌려준다."""
    with graph_session() as session:
        if not rows(session, FIND_ASSET, asset_id=asset_id):
            return not_found(asset_id, "설비", f"그래프에 설비 {asset_id} 가 없습니다.")
        sensors = rows(session, FIND_SENSOR, asset_id=asset_id, kind=kind)
        if not sensors:
            return not_found(asset_id, "센서", f"설비 {asset_id} 에 '{kind}' 센서가 없습니다.")
        sensor = sensors[0]
        reading = latest_reading(sensor["tag"])
        if reading is None:
            return not_found(asset_id, "현재 값", f"연습용 DB 에 {sensor['tag']} 의 측정값이 없습니다.")
        value = float(reading["value"])
        matches = []
        for symptom in rows(session, FIND_SYMPTOMS, asset_id=asset_id, failure=None):
            if symptom["sensor_kind"] != kind or not OPERATORS[symptom["operator"]](value, symptom["threshold"]):
                continue
            matches.append({
                "failure_mode": symptom["failure_mode"],
                "symptom": symptom["symptom"],
                "criterion": {key: symptom[key] for key in ("operator", "threshold", "unit")},
                "source": symptom["source"],
                **knowledge(session, symptom["failure_id"]),
            })
    current = {**sensor, "value": value, "measured_at": reading["measured_at"].isoformat(), "source": "연습용 DB"}
    return {"found": True, "asset_id": asset_id, "current": current, "matches": matches}


def failure_knowledge(asset_id: str, name: str) -> dict:
    """설비에 등록된 고장 하나의 증상·원인·조치를 출처와 함께 돌려준다."""
    with graph_session() as session:
        if not rows(session, FIND_ASSET, asset_id=asset_id):
            return not_found(asset_id, "설비", f"그래프에 설비 {asset_id} 가 없습니다.")
        failures = rows(session, FIND_FAILURE, asset_id=asset_id, name=name)
        if not failures:
            return not_found(asset_id, "고장 지식", f"근거 없음: 설비 {asset_id} 에 '{name}' 고장으로 등록된 지식이 없습니다.")
        symptoms = [
            {"name": row["symptom"], "source": row["source"]}
            for row in rows(session, FIND_SYMPTOMS, asset_id=asset_id, failure=name)
        ]
        return {"found": True, "asset_id": asset_id, "failure_mode": name, "symptoms": symptoms,
                **knowledge(session, failures[0]["failure_id"])}


def main() -> None:
    parser = argparse.ArgumentParser(description="현재 값과 고장 지식 함께 찾기")
    commands = parser.add_subparsers(dest="command", required=True)
    current = commands.add_parser("current", help="현재 값과 그 값에 해당하는 기준·조치")
    current.add_argument("--asset-id", required=True)
    current.add_argument("--kind", default=DEFAULT_KIND)
    failure = commands.add_parser("failure", help="고장 이름으로 원인·조치")
    failure.add_argument("--asset-id", required=True)
    failure.add_argument("--name", required=True)
    args = parser.parse_args()
    result = current_status(args.asset_id, args.kind) if args.command == "current" else failure_knowledge(args.asset_id, args.name)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
