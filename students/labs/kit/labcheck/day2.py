"""2일차 확인: 스키마(2-1) · CSV 적재(2-2) · 설비로 센서·부품 찾기(2-3)."""
from __future__ import annotations

from collections import Counter

from labcheck import graphstate
from labcheck.core import Report, ids, need_file, run_json, run_script, work_path
from labcheck.facts import read_csv
from labcheck.schemafile import check_classes, check_constraints, check_relationships, load_schema
from labkit.graph import graph_session

MISSING_ASSET_ID = "CL-99"
DAY2_CLASSES = {"Asset": ["id", "name"], "Component": ["id", "name"], "Sensor": ["id", "name", "tag"]}
DAY2_RELATIONS = [("HAS_COMPONENT", "Asset", "Component"), ("HAS_SENSOR", "Asset", "Sensor"), ("MONITORED_BY", "Component", "Sensor")]


def expected_day2() -> dict:
    assets, components, sensors = (read_csv(f"day2/data/{name}.csv") for name in ("assets", "components", "sensors"))
    return {
        "Asset": {row["asset_id"]: row for row in assets},
        "Component": {row["component_id"]: row for row in components},
        "Sensor": {row["sensor_id"]: row for row in sensors},
        "HAS_COMPONENT": sorted((row["asset_id"], row["component_id"]) for row in components),
        "HAS_SENSOR": sorted((row["asset_id"], row["sensor_id"]) for row in sensors),
        "MONITORED_BY": sorted((row["component_id"], row["sensor_id"]) for row in sensors),
    }


def lab2_1(report: Report) -> None:
    schema = load_schema(report)
    check_classes(report, schema, DAY2_CLASSES)
    check_relationships(report, schema, DAY2_RELATIONS)
    with graph_session() as session:
        check_constraints(report, schema, graphstate.unique_constraints(session), list(DAY2_CLASSES))


def check_day2_graph(report: Report, session) -> None:
    expected = expected_day2()
    for label in ("Asset", "Component", "Sensor"):
        found = graphstate.nodes(session, label)
        report.check(f"{label} 노드에 같은 id 가 두 번 없다", not graphstate.duplicate_ids(session, label),
                     f"겹친 id: {graphstate.duplicate_ids(session, label)}. 새로 만들기만 하면(CREATE) 넣을 때마다 늘어납니다.")
        report.equal(f"{label} 노드의 id 가 CSV 와 같다", ids(found), set(expected[label]))
        wrong = [node.get("id") for node in found
                 if node.get("id") in expected[label] and node.get("name") != expected[label][node["id"]]["name"]]
        report.check(f"{label} 노드의 name 이 CSV 와 같다", not wrong, f"name 이 다른 노드: {wrong}")
    tags = {node.get("id"): node.get("tag") for node in graphstate.nodes(session, "Sensor")}
    report.equal("Sensor 노드의 tag 가 CSV 와 같다", tags, {key: row["tag"] for key, row in expected["Sensor"].items()})
    for rel_type in ("HAS_COMPONENT", "HAS_SENSOR", "MONITORED_BY"):
        found = sorted(graphstate.pairs(graphstate.relations(session, rel_type)))
        repeated = [pair for pair, count in Counter(found).items() if count > 1]
        report.check(f"{rel_type} 관계가 같은 쌍에 두 번 없다", not repeated, f"겹친 관계: {repeated}")
        report.equal(f"{rel_type} 관계가 CSV 와 같다(방향 포함)", sorted(set(found)), expected[rel_type])


def lab2_2(report: Report) -> None:
    loader = work_path("load_csv.py")
    need_file(report, loader, "적재 프로그램")
    with graph_session() as session:
        check_day2_graph(report, session)
        before = graphstate.counts(session)
    done = run_script(loader)
    report.require("적재 프로그램을 한 번 더 실행해도 오류가 없다", done.returncode == 0, done.stderr.strip()[-600:])
    with graph_session() as session:
        report.equal("같은 자료를 다시 넣어도 노드·관계 수가 그대로다(중복 0)", graphstate.counts(session), before)


def lab2_3(report: Report) -> None:
    finder = work_path("find_related.py")
    need_file(report, finder, "조회 프로그램")
    expected = expected_day2()
    for asset_id, asset in expected["Asset"].items():
        result = run_json(report, finder, "--id", asset_id)
        report.check(f"{asset_id}: found 가 true 다", result.get("found") is True, f"나온 값 {result.get('found')!r}")
        report.equal(f"{asset_id}: 그 설비의 센서만 나온다", ids(result.get("sensors", [])),
                     {sensor for owner, sensor in expected["HAS_SENSOR"] if owner == asset_id})
        report.equal(f"{asset_id}: 그 설비의 부품만 나온다", ids(result.get("components", [])),
                     {component for owner, component in expected["HAS_COMPONENT"] if owner == asset_id})
        by_name = run_json(report, finder, "--name", asset["name"])
        report.equal(f"이름 '{asset['name']}' 으로 찾아도 같은 센서가 나온다", ids(by_name.get("sensors", [])), ids(result.get("sensors", [])))
    limited = run_json(report, finder, "--id", "CL-01", "--limit", "1")
    report.check("--limit 1 이면 센서 · 부품이 하나씩만 나온다",
                 len(limited.get("sensors", [])) == 1 and len(limited.get("components", [])) == 1,
                 f"센서 {len(limited.get('sensors', []))}개, 부품 {len(limited.get('components', []))}개")
    missing = run_json(report, finder, "--id", MISSING_ASSET_ID)
    report.check(f"없는 설비 번호({MISSING_ASSET_ID})는 found 가 false 이고 빈 결과다",
                 missing.get("found") is False and not missing.get("sensors") and not missing.get("components"),
                 f"나온 값 {missing}")


LABS = {
    "2-1": ("연습용 설비의 클래스·관계 스키마 만들기", lab2_1),
    "2-2": ("설비·부품·센서 자료를 그래프에 등록하기", lab2_2),
    "2-3": ("설비 이름으로 센서와 부품 찾기", lab2_3),
}
