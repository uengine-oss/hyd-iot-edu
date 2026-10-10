"""키트 자료에서 계산해 만드는 파일을 다시 만든다. 자료(CSV · 매뉴얼 · 결정표)를 고친 뒤 실행한다.

    python instructor/tools/build_kit_data.py            # 파일을 다시 쓴다
    python instructor/tools/build_kit_data.py --check    # 저장된 파일이 지금 자료와 같은지만 본다

만드는 것: 결정표 기대 결과(labcheck/expected/decision.json), 준비된 그래프(day6/data/prepared_graph.cypher),
검토 랩 확인용 추천안(labcheck/fixtures/day7/).
"""
from __future__ import annotations

import argparse
import copy
import itertools
import json

import labpaths
from labcheck.facts import mapped_assets, prepared_candidates, read_csv, valid_candidate_ids

KIT = labpaths.KIT
evaluate = labpaths.judge_engine().evaluate
build_proposal = labpaths.answer_recommend().build_proposal
TABLE = labpaths.judge_engine().load_table(KIT / "day6" / "judge_mcp" / "decision_table.json")
BOUNDARY_TEMPS = (45, 45.1, 60, 60.1)
BOUNDARY_LOADS = (30, 30.1, 80, 80.1)
FAN_STATES = ("정상", "약함", "정지")
PREPARED_INPUTS = ("normal.json", "just_above.json", "overlap.json")
HIGH_LOAD_PCT = 85
SHORT_WINDOW_MINUTES = 30
INFLATED_NET_BENEFIT = 70


def dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def judged(values: dict) -> dict:
    return evaluate(TABLE, values)["actions"]


def decision_expected() -> str:
    cases = []
    for name in PREPARED_INPUTS:
        values = json.loads((KIT / "day3" / "inputs" / name).read_text(encoding="utf-8"))
        outcome = judged(values)
        cases.append({"name": name, "input": values,
                      "results": {action: item["result"] for action, item in outcome.items()},
                      "applied": {action: item["applied_rule"] for action, item in outcome.items()}})
    boundaries = []
    for temp, fan, load in itertools.product(BOUNDARY_TEMPS, FAN_STATES, BOUNDARY_LOADS):
        values = {"temp_c": temp, "fan_state": fan, "load_pct": load}
        boundaries.append({"input": values, "results": {action: item["result"] for action, item in judged(values).items()}})
    return dump({
        "actions": TABLE["actions"],
        "rules": {rule["id"]: [rule["action"], rule["result"]] for rule in TABLE["rules"]},
        "cases": cases,
        "boundaries": boundaries,
        "invalid_inputs": {
            "팬 상태 '모름'": {"temp_c": 50, "fan_state": "모름", "load_pct": 50},
            "부하 값 없음": {"temp_c": 50, "fan_state": "정상"},
        },
    })


def literal(value) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return "'" + str(value).replace("\\", "\\\\").replace("'", "\\'") + "'"


def props(values: dict) -> str:
    return ", ".join(f"{key}: {literal(value)}" for key, value in values.items())


def merge_node(label: str, node_id: str, values: dict) -> str:
    return f"MERGE (n:{label} {{id: {literal(node_id)}}}) SET n += {{{props(values)}}}"


def merge_relation(start: tuple[str, str], rel: str, end: tuple[str, str], values: dict | None = None, key: dict | None = None) -> str:
    key_text = f" {{{props(key)}}}" if key else ""
    setter = f" SET r += {{{props(values)}}}" if values else ""
    return (f"MATCH (a:{start[0]} {{id: {literal(start[1])}}}), (b:{end[0]} {{id: {literal(end[1])}}}) "
            f"MERGE (a)-[r:{rel}{key_text}]->(b){setter}")


def prepared_graph() -> str:
    schema = json.loads((labpaths.ANSWERS / "work" / "schema.json").read_text(encoding="utf-8"))
    lines = [f"CREATE CONSTRAINT {cls['name'].lower()}_id_unique IF NOT EXISTS FOR (n:{cls['name']}) REQUIRE n.id IS UNIQUE" for cls in schema["classes"]]
    for row in read_csv("day2/data/assets.csv"):
        lines.append(merge_node("Asset", row["asset_id"], {"name": row["name"], "line": row["line"], "model": row["model"]}))
    for row in read_csv("day2/data/components.csv"):
        lines.append(merge_node("Component", row["component_id"], {"name": row["name"], "kind": row["kind"]}))
        lines.append(merge_relation(("Asset", row["asset_id"]), "HAS_COMPONENT", ("Component", row["component_id"])))
    for row in read_csv("day2/data/sensors.csv"):
        lines.append(merge_node("Sensor", row["sensor_id"], {"name": row["name"], "kind": row["kind"], "unit": row["unit"], "tag": row["tag"]}))
        lines.append(merge_relation(("Asset", row["asset_id"]), "HAS_SENSOR", ("Sensor", row["sensor_id"])))
        lines.append(merge_relation(("Component", row["component_id"]), "MONITORED_BY", ("Sensor", row["sensor_id"])))
    for row in read_csv("day3/data/actions.csv"):
        lines.append(merge_node("Action", row["action_id"], {"name": row["name"], "kind": row["kind"]}))
    for row in read_csv("day3/data/measures.csv"):
        lines.append(merge_node("Measure", row["measure_id"], {"name": row["name"], "unit": row["unit"], "better": row["better"]}))
    for row in read_csv("day3/data/action_effects.csv"):
        lines.append(merge_relation(("Action", row["action_id"]), "AFFECTS", ("Measure", row["measure_id"]), {"effect": row["effect"], "basis": row["basis"]}))
    failures: dict[str, str] = {}
    for candidate in prepared_candidates():
        if candidate["id"] not in valid_candidate_ids():
            continue
        for end in (candidate["from"], candidate["to"]):
            lines.append(merge_node(end["label"], end["id"], {"name": end["name"], **end.get("props", {})}))
            if end["label"] == "FailureMode":
                failures[end["id"]] = candidate["source"]["doc"]
        source = candidate["source"]
        lines.append(merge_relation((candidate["from"]["label"], candidate["from"]["id"]), candidate["relation"],
                                    (candidate["to"]["label"], candidate["to"]["id"]),
                                    {"doc": source["doc"], "section": source["section"], "line": source["line"], "quote": source["quote"]},
                                    key={"candidate_id": candidate["id"]}))
    for failure_id, doc in failures.items():
        for asset_id in sorted(mapped_assets(doc)):
            lines.append(merge_relation(("Asset", asset_id), "CAN_HAVE", ("FailureMode", failure_id), {"doc": doc}))
    unique = list(dict.fromkeys(lines))
    header = "// 준비된 연습용 그래프. 2~4일차 랩을 마친 상태와 같다. python -m labkit.prepared_graph 로 넣는다.\n"
    return header + ";\n".join(unique) + ";\n"


def day7_fixtures() -> dict[str, str]:
    base = json.loads((KIT / "day7" / "inputs" / "case_base.json").read_text(encoding="utf-8"))
    highload = copy.deepcopy(base)
    highload["case_id"] = "CASE-CL01-HIGH-LOAD"
    highload["condition"]["load_pct"] = HIGH_LOAD_PCT
    outcomes = judged(highload["condition"])
    for candidate in highload["candidates"]:
        outcome = outcomes[candidate["action_id"]]
        candidate["judgement"] = {"result": outcome["result"], "applied_rule": outcome["applied_rule"]}
    rule_violation = build_proposal(base)
    rule_violation.update(case_id=highload["case_id"], condition=highload["condition"])
    rule_violation["ranking"][0].update(judgement="제외", warning=False)
    time_violation = build_proposal(base)
    time_violation["available_minutes"] = SHORT_WINDOW_MINUTES
    mismatch = build_proposal(base)
    fan = next(item for item in mismatch["ranking"] if item["action_id"] == "ACT-FAN-UP")
    fan["net_benefit_manwon"] = INFLATED_NET_BENEFIT
    fan["reason"] = f"순편익 {INFLATED_NET_BENEFIT}만원으로 가장 크다"
    mismatch["ranking"].sort(key=lambda item: item["net_benefit_manwon"], reverse=True)
    for rank, item in enumerate(mismatch["ranking"], start=1):
        item["rank"] = rank
    mismatch["recommended"] = "ACT-FAN-UP"
    return {
        "case_highload.json": dump(highload),
        "proposal_rule_violation.json": dump(rule_violation),
        "proposal_time_violation.json": dump(time_violation),
        "proposal_reason_mismatch.json": dump(mismatch),
    }


def outputs() -> dict:
    files = {KIT / "labcheck" / "expected" / "decision.json": decision_expected(),
             KIT / "day6" / "data" / "prepared_graph.cypher": prepared_graph()}
    for name, text in day7_fixtures().items():
        files[KIT / "labcheck" / "fixtures" / "day7" / name] = text
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description="키트의 계산 파일 다시 만들기")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    stale = []
    for path, text in outputs().items():
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != text:
                stale.append(str(path.relative_to(labpaths.LABS_ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            print(f"씀: {path.relative_to(labpaths.LABS_ROOT)}")
    if stale:
        raise SystemExit(f"자료와 맞지 않는 파일: {stale}. --check 없이 다시 실행하세요.")


if __name__ == "__main__":
    main()
