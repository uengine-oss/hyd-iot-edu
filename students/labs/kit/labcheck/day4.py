"""4일차 확인: 매뉴얼에서 후보 추출(4-1) · 원문과 대조해 등록(4-2) · 현재 값과 함께 조회(4-3) · 질문 바꾸기(4-4)."""
from __future__ import annotations

import operator
from datetime import datetime

from labcheck import graphstate
from labcheck.core import Report, need_file, read_json, run_json, work_path
from labcheck.facts import (RELATION_ENDS, candidate_problem, manual_sections, mapped_assets, prepared_candidates,
                            source_problem, valid_candidate_ids)
from labcheck.schemafile import check_classes, check_constraints, check_relationships, load_schema
from labkit.db import connect
from labkit.graph import graph_session

KINDS = {"증상", "원인", "조치"}
DECISIONS = {"채택", "보류"}
OPERATORS = {">": operator.gt, ">=": operator.ge, "<": operator.lt, "<=": operator.le}
SOURCE_KEYS = ("doc", "section", "line", "quote")
DEFAULT_KIND = "출구 온도"
UNKNOWN_FAILURE = "소음"
MISSING_ASSET_ID = "CL-99"
NO_READING = ("CL-02", "팬 회전수")
KNOWLEDGE_LABELS = ("Symptom", "FailureMode", "Cause")


def lab4_1(report: Report) -> None:
    sections = read_json(report, work_path("sections.json"), "구간")
    expected = [{"section": part["section"], "lines": part["lines"]} for part in manual_sections()]
    found = [{"section": str(part.get("section")), "lines": {line.get("line"): line.get("text") for line in part.get("lines", [])}}
             for part in sections] if isinstance(sections, list) else []
    report.equal("구간이 매뉴얼의 절과 같고, 줄 번호와 원문이 그대로 보존됐다", found, expected)
    data = read_json(report, work_path("candidates.json"), "후보")
    candidates = data.get("candidates") if isinstance(data, dict) else None
    report.require("후보 파일에 candidates 목록이 있다", isinstance(candidates, list) and bool(candidates), "후보가 하나도 없습니다.")
    incomplete = [index for index, c in enumerate(candidates, start=1)
                  if c.get("kind") not in KINDS or not all(c.get(key) for key in ("failure", "name", "section", "line", "quote"))]
    report.require("후보마다 kind(증상·원인·조치) · failure · name · section · line · quote 가 있다", not incomplete, f"모자란 후보(순서): {incomplete}")
    wrong = {c["name"]: problem for c in candidates if (problem := source_problem(c, [c["failure"]]))}
    report.check("후보의 인용 문장이 모두 그 절 · 그 줄의 원문에 있다", not wrong, f"원문과 어긋난 후보: {wrong}")
    covered = {(c["failure"], c["kind"]) for c in candidates}
    for failure in ("과열", "누수", "유량 저하"):
        report.check(f"'{failure}' 의 원인 후보가 있다", (failure, "원인") in covered, "매뉴얼에 이 고장의 원인 문장이 있습니다.")
    report.check("'과열' 의 증상 · 조치 후보가 있다", {("과열", "증상"), ("과열", "조치")} <= covered, "매뉴얼 2절을 다시 보세요.")


def registered_relations(session) -> list[dict]:
    found = []
    for rel_type in RELATION_ENDS:
        for row in graphstate.relations(session, rel_type):
            found.append({**row, "type": rel_type})
    return found


def check_registered(report: Report, relation: dict, candidate: dict) -> None:
    cid = candidate["id"]
    same = (relation["type"], relation["from_id"], relation["to_id"]) == (candidate["relation"], candidate["from"]["id"], candidate["to"]["id"])
    report.check(f"{cid}: 관계 종류와 양 끝이 후보와 같다", same,
                 f"그래프: {relation['type']} {relation['from_id']} → {relation['to_id']}")
    problem = source_problem(relation["props"], [relation["from_name"], relation["to_name"]])
    report.check(f"{cid}: 관계에 적힌 출처(문서·절·줄·원문)가 매뉴얼로 확인된다",
                 problem is None and all(relation["props"].get(key) for key in SOURCE_KEYS), problem or "출처 속성이 비었습니다.")


def lab4_2(report: Report) -> None:
    candidates = {c["id"]: c for c in prepared_candidates()}
    review = read_json(report, work_path("review.json"), "검토 기록")
    decided = {cid: (review.get(cid) or {}).get("decision") for cid in candidates} if isinstance(review, dict) else {}
    report.require("후보마다 채택 · 보류가 적혀 있다", bool(decided) and all(value in DECISIONS for value in decided.values()),
                   f"적히지 않았거나 다른 값인 후보: {[cid for cid, value in decided.items() if value not in DECISIONS]}")
    report.check("보류한 후보에는 이유가 적혀 있다", all((review[cid].get("reason") or "").strip() for cid, value in decided.items() if value == "보류"),
                 "보류한 까닭을 reason 에 적어 주세요.")
    adopted = {cid for cid, value in decided.items() if value == "채택"}
    schema = load_schema(report)
    check_classes(report, schema, {label: ["id", "name"] for label in KNOWLEDGE_LABELS})
    check_relationships(report, schema, [(rel_type, *ends) for rel_type, ends in RELATION_ENDS.items()] + [("CAN_HAVE", "Asset", "FailureMode")])
    with graph_session() as session:
        check_constraints(report, schema, graphstate.unique_constraints(session), list(KNOWLEDGE_LABELS))
        relations = registered_relations(session)
        can_have = set(graphstate.pairs(graphstate.relations(session, "CAN_HAVE")))
        knowledge_ids = {label: {node.get("id") for node in graphstate.nodes(session, label)} for label in KNOWLEDGE_LABELS}
    registered = {relation["props"].get("candidate_id"): relation for relation in relations}
    report.check("등록된 관계마다 후보 번호(candidate_id)가 있다", None not in registered, "candidate_id 가 없는 관계가 있습니다.")
    report.equal("채택한 후보만 그래프에 등록됐다(보류한 것은 없다)", set(registered) - {None}, adopted)
    report.check("원문으로 확인되는 후보를 빠뜨리지 않고 채택했다", valid_candidate_ids() <= adopted,
                 f"채택했어야 하는 후보: {sorted(valid_candidate_ids() - adopted)}")
    for cid in sorted(adopted & set(registered)):
        check_registered(report, registered[cid], candidates[cid])
    unfounded = sorted(cid for cid in adopted if candidate_problem(candidates[cid]) and cid in registered
                       and source_problem(registered[cid]["props"], [registered[cid]["from_name"], registered[cid]["to_name"]]))
    report.check("원문에 없는 연결은 등록하지 않았다", not unfounded,
                 f"원문으로 확인되지 않는데 등록된 후보: { {cid: candidate_problem(candidates[cid]) for cid in unfounded} }")
    used = {label: set() for label in KNOWLEDGE_LABELS}
    for relation in relations:
        for side in ("from", "to"):
            if relation[f"{side}_label"] in used:
                used[relation[f"{side}_label"]].add(relation[f"{side}_id"])
    report.equal("등록된 관계에 쓰이지 않는 증상 · 고장 · 원인 노드가 없다", knowledge_ids, used)
    doc = prepared_candidates()[0]["source"]["doc"]
    wanted = {(asset, failure) for asset in mapped_assets(doc) for failure in used["FailureMode"]}
    report.check("매뉴얼 대상 설비마다 등록된 고장이 CAN_HAVE 로 이어져 있다", wanted <= can_have, f"없는 연결: {sorted(wanted - can_have)}")


def latest_reading(tag: str) -> dict | None:
    with connect() as conn:
        return conn.execute("SELECT value, measured_at FROM readings WHERE tag = %s ORDER BY measured_at DESC LIMIT 1", (tag,)).fetchone()


def graph_knowledge(asset_id: str) -> dict:
    """설비에 이어진 고장마다 증상 · 원인 · 조치(그래프에 지금 등록된 것)."""
    with graph_session() as session:
        can_have = {failure for asset, failure in graphstate.pairs(graphstate.relations(session, "CAN_HAVE")) if asset == asset_id}
        relations = registered_relations(session)
        symptoms = {node["id"]: node for node in graphstate.nodes(session, "Symptom")}
        sensors = [row["to_id"] for row in graphstate.relations(session, "HAS_SENSOR") if row["from_id"] == asset_id]
        sensor_nodes = {node["id"]: node for node in graphstate.nodes(session, "Sensor") if node["id"] in sensors}
    failures: dict[str, dict] = {}
    for relation in relations:
        failure_end = "to" if relation["type"] != "REMEDIED_BY" else "from"
        other_end = "from" if failure_end == "to" else "to"
        if relation[f"{failure_end}_id"] not in can_have:
            continue
        entry = failures.setdefault(relation[f"{failure_end}_name"], {"INDICATES": [], "CAUSES": [], "REMEDIED_BY": []})
        entry[relation["type"]].append({"id": relation[f"{other_end}_id"], "name": relation[f"{other_end}_name"], "source": relation["props"]})
    return {"failures": failures, "symptoms": symptoms, "sensors": sensor_nodes}


def names(items: list[dict]) -> set:
    return {item.get("name") for item in items}


def sources_ok(items: list[dict]) -> bool:
    return all(isinstance(item.get("source"), dict) and all(item["source"].get(key) for key in SOURCE_KEYS) for item in items)


def expected_matches(knowledge: dict, kind: str, value: float) -> dict[str, dict]:
    matched = {}
    for failure, entry in knowledge["failures"].items():
        for symptom in entry["INDICATES"]:
            node = knowledge["symptoms"][symptom["id"]]
            if node.get("sensor_kind") == kind and OPERATORS[node["operator"]](value, node["threshold"]):
                matched[failure] = entry
    return matched


def check_current(report: Report, asset_id: str) -> dict:
    lookup = work_path("lookup.py")
    knowledge = graph_knowledge(asset_id)
    sensor = next(node for node in knowledge["sensors"].values() if node.get("kind") == DEFAULT_KIND)
    reading = latest_reading(sensor["tag"])
    result = run_json(report, lookup, "current", "--asset-id", asset_id)
    current = result.get("current") or {}
    report.check(f"{asset_id}: found 가 true 이고 현재 값이 연습용 DB 의 가장 늦은 값과 같다",
                 result.get("found") is True and current.get("value") == float(reading["value"]),
                 f"나온 값 {current.get('value')!r} / DB 값 {float(reading['value'])}")
    report.check(f"{asset_id}: 현재 값에 센서 번호 · DB 이름 · 단위 · 측정 시각이 함께 있다",
                 current.get("sensor_id") == sensor["id"] and current.get("tag") == sensor["tag"] and current.get("unit") == sensor["unit"]
                 and same_instant(current.get("measured_at"), reading["measured_at"]), f"나온 값 {current}")
    expected = expected_matches(knowledge, DEFAULT_KIND, float(reading["value"]))
    matches = {match.get("failure_mode"): match for match in result.get("matches", [])}
    report.equal(f"{asset_id}: 현재 값이 기준을 넘긴 고장만 나온다", set(matches), set(expected))
    for failure, entry in expected.items():
        match = matches.get(failure, {})
        report.equal(f"{asset_id} · {failure}: 가능한 조치가 그래프에 등록된 것과 같다", names(match.get("actions", [])), names(entry["REMEDIED_BY"]))
        report.equal(f"{asset_id} · {failure}: 원인이 그래프에 등록된 것과 같다", names(match.get("causes", [])), names(entry["CAUSES"]))
        cited = [match, *match.get("causes", []), *match.get("actions", [])]
        report.check(f"{asset_id} · {failure}: 판정 기준 · 원인 · 조치마다 원문 위치(문서·절·줄·원문)가 있다", sources_ok(cited), "source 가 비었거나 일부만 있습니다.")
        unverified = [item.get("name", failure) for item in cited if isinstance(item.get("source"), dict) and manual_quote_missing(item["source"])]
        report.check(f"{asset_id} · {failure}: 적힌 원문 위치가 실제 매뉴얼과 맞는다", not unverified, f"매뉴얼과 다른 것: {unverified}")
    return result


def manual_quote_missing(source: dict) -> bool:
    return source_problem(source, []) is not None


def same_instant(text, moment: datetime) -> bool:
    try:
        return datetime.fromisoformat(str(text)) == moment
    except ValueError:
        return False


def lab4_3(report: Report) -> None:
    need_file(report, work_path("lookup.py"), "조회 프로그램")
    hot = check_current(report, "CL-01")
    report.check("CL-01: 현재 값이 기준을 넘겨 조치가 하나 이상 나온다", any(match.get("actions") for match in hot.get("matches", [])), "matches 에 조치가 없습니다.")
    normal = check_current(report, "CL-02")
    report.check("CL-02: 정상 온도라 해당하는 고장이 없다(조치를 지어내지 않는다)", normal.get("matches") == [], f"나온 값 {normal.get('matches')}")


def expect_no_ground(report: Report, name: str, result: dict) -> None:
    invented = [key for key in ("causes", "actions", "matches", "symptoms", "current") if result.get(key)]
    report.check(name, result.get("found") is False and bool(result.get("missing")) and bool(result.get("reason")) and not invented,
                 f"found={result.get('found')!r}, missing={result.get('missing')!r}, 근거 없이 채워진 칸: {invented}")


def lab4_4(report: Report) -> None:
    lookup = work_path("lookup.py")
    need_file(report, lookup, "조회 프로그램")
    for asset_id in ("CL-01", "CL-02"):
        knowledge = graph_knowledge(asset_id)
        for failure, entry in sorted(knowledge["failures"].items()):
            result = run_json(report, lookup, "failure", "--asset-id", asset_id, "--name", failure)
            ok = (result.get("found") is True and names(result.get("causes", [])) == names(entry["CAUSES"])
                  and names(result.get("actions", [])) == names(entry["REMEDIED_BY"]))
            report.check(f"{asset_id}: '{failure}' 의 원인과 조치가 그래프에 등록된 것과 같다", ok,
                         f"원인 {sorted(names(result.get('causes', [])))} / 조치 {sorted(names(result.get('actions', [])))}")
            report.check(f"{asset_id}: '{failure}' 답의 원인 · 조치마다 원문 위치가 있다",
                         sources_ok([*result.get("causes", []), *result.get("actions", [])]), "source 가 비었습니다.")
    expect_no_ground(report, f"등록되지 않은 고장('{UNKNOWN_FAILURE}')을 물으면 근거 없음으로 답한다",
                     run_json(report, lookup, "failure", "--asset-id", "CL-01", "--name", UNKNOWN_FAILURE))
    expect_no_ground(report, f"측정값이 없는 센서({NO_READING[0]} {NO_READING[1]})를 물으면 값이 없다고 답한다",
                     run_json(report, lookup, "current", "--asset-id", NO_READING[0], "--kind", NO_READING[1]))
    expect_no_ground(report, f"없는 설비({MISSING_ASSET_ID})를 물으면 설비가 없다고 답한다",
                     run_json(report, lookup, "current", "--asset-id", MISSING_ASSET_ID))
    hot = run_json(report, lookup, "current", "--asset-id", "CL-01")
    normal = run_json(report, lookup, "current", "--asset-id", "CL-02")
    report.check("설비가 바뀌면 현재 값과 답이 달라진다", (hot.get("current") or {}).get("value") != (normal.get("current") or {}).get("value")
                 and hot.get("matches") != normal.get("matches"), "두 설비의 답이 같습니다.")


LABS = {
    "4-1": ("짧은 매뉴얼에서 고장·원인·조치 후보 추출하기", lab4_1),
    "4-2": ("원문과 비교한 후보만 그래프에 등록하기", lab4_2),
    "4-3": ("현재 설비 값과 문서의 조치 지식을 함께 조회하기", lab4_3),
    "4-4": ("질문을 바꿔 답변 근거가 유지되는지 확인하기", lab4_4),
}
