"""work/schema.json 이 약속한 모양인지 보는 확인(2~4일차 공용)."""
from __future__ import annotations

from labcheck.core import Report, read_json, work_path


def load_schema(report: Report) -> dict:
    schema = read_json(report, work_path("schema.json"), "스키마")
    report.require("스키마 파일에 classes 와 relationships 가 있다",
                   isinstance(schema, dict) and isinstance(schema.get("classes"), list) and isinstance(schema.get("relationships"), list),
                   "cooler/schema_guide.md 의 '스키마 파일의 모양'을 따라 주세요.")
    return schema


def check_classes(report: Report, schema: dict, required: dict[str, list[str]]) -> None:
    """required: 클래스 이름 → 꼭 있어야 하는 속성 이름."""
    classes = {cls.get("name"): cls for cls in schema["classes"]}
    for name, props in required.items():
        if not report.check(f"스키마에 클래스 {name} 이 있다", name in classes, "스키마 설명의 클래스 이름 그대로 넣어 주세요."):
            continue
        declared = {prop.get("name"): prop for prop in classes[name].get("properties", [])}
        missing = [prop for prop in props if not declared.get(prop, {}).get("required")]
        report.check(f"{name} 의 필수 속성 {props} 이 required 로 적혀 있다", not missing, f"빠졌거나 required 가 아닌 속성: {missing}")
        report.check(f"{name} 에 중복 금지 조건(unique)으로 id 가 적혀 있다", "id" in classes[name].get("unique", []),
                     "같은 번호의 노드가 두 개 생기지 않게 unique 에 id 를 넣어 주세요.")


def check_relationships(report: Report, schema: dict, required: list[tuple[str, str, str]]) -> None:
    declared = {(rel.get("type"), rel.get("from"), rel.get("to")) for rel in schema["relationships"]}
    by_type = {rel.get("type"): rel for rel in schema["relationships"]}
    for rel_type, start, end in required:
        if rel_type not in by_type:
            report.check(f"스키마에 관계 {rel_type} 이 있다", False, "빠진 관계입니다. Claude Code 에 이 관계를 더하라고 지시해 주세요.")
            continue
        got = by_type[rel_type]
        report.check(f"관계 {rel_type} 의 방향이 {start} → {end} 이다", (rel_type, start, end) in declared,
                     f"스키마에는 {got.get('from')} → {got.get('to')} 로 적혀 있습니다.")


def check_constraints(report: Report, schema: dict, graph_constraints: set[tuple[str, str]], labels: list[str]) -> None:
    for label in labels:
        report.check(f"그래프에 {label}.id 고유 제약이 있다", (label, "id") in graph_constraints,
                     "스키마 파일에만 적혀 있고 그래프에는 아직 제약이 없습니다.")
    declared = {(cls["name"], prop) for cls in schema["classes"] for prop in cls.get("unique", []) if cls.get("name")}
    report.check("스키마 파일의 중복 금지 조건이 모두 그래프 제약으로 있다", declared <= graph_constraints,
                 f"그래프에 없는 것: {sorted(declared - graph_constraints)}")
