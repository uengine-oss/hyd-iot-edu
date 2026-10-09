"""확정 TODO C1: 시드 두 판(수업용 구조판 · 회귀용 전체판).

구조판은 설비 구조 · 역할/조직/시스템 · BSC · 감시 패턴 · 회사 규정 · 순위 정책만 넣고, 고장 · 원인 · 증거 · 조치(SOP) · 매뉴얼 규칙 ·
예측 · 선례는 넣지 않는다(학생이 문서를 적재해 만든다). 전체판은 지금까지의 시드와 같은 그래프를 만든다.
판 고르기 규칙은 두 곳에 있다(컨테이너 bash: it/neo4j/edition.sh, 호스트 파이썬: scripts/ontology_v2.py). 여기서 둘을 대조한다.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ontology_v2 as ov  # noqa: E402

SEED = ROOT / "it" / "neo4j"
FILES = ("instances.cypher", "knowledge_a098.cypher", "scenario_structure.cypher", "detector-patterns.cypher")
KNOWLEDGE = ("FailureMode", "Cause", "Evidence", "Skill", "Step", "ManualSection", "Forecast", "DecisionCase", "Incident")


def text(name):
    return (ov.V2 / name).read_text(encoding="utf-8")


def merged_labels(code):
    code = "\n".join(l for l in code.splitlines() if not l.strip().startswith("//"))
    return set(re.findall(r"MERGE \(\s*\w*\s*:(\w+)", code)) | set(re.findall(r"SET \w+:(\w+)", code))


def edition_code(edition):
    return "\n".join(ov.edition_filter(text(f), edition) for f in FILES)


@pytest.mark.skipif(not shutil.which("bash"), reason="bash 필요")
@pytest.mark.parametrize("edition", ov.EDITIONS)
def test_container_bash_filter_and_host_python_filter_agree(edition):
    for f in FILES:
        out = subprocess.run(["bash", "-c", f'. ./edition.sh; seed_edition_filter {edition} v2/{f}'], cwd=SEED,
                             capture_output=True, text=True, check=True).stdout
        assert out.rstrip("\n") == ov.edition_filter(text(f), edition).rstrip("\n"), f
    out = subprocess.run(["bash", "-c", f'. ./edition.sh; seed_edition_checks {edition} v2/seed_checks.cypher'], cwd=SEED,
                         capture_output=True, text=True, check=True).stdout.splitlines()
    assert out == ov.edition_checks(text("seed_checks.cypher"), edition)


def test_full_edition_runs_every_statement_of_the_seed_files():
    """전체판은 표시를 무시한 것과 같다 — 시드 파일의 모든 문장이 실행된다(회귀 동작 불변). 구조판 전용 문장은 없다."""
    for f in FILES:
        assert ov.split_statements(ov.edition_filter(text(f), "full")) == ov.split_statements(text(f)), f
        assert "// @edition structure" not in text(f), f


def test_structure_edition_has_no_scenario_failure_knowledge():
    code = edition_code("structure")
    labels = merged_labels(code)
    assert not labels & set(KNOWLEDGE), labels & set(KNOWLEDGE)
    # 매뉴얼 규칙(진단 · 후보 · 매뉴얼 근거 규정)은 없고, 회사 규정 · 순위 정책은 남는다(결정 2)
    rules = set(re.findall(r"\['(rule:[a-z0-9-]+)','dt:", code)) | set(re.findall(r"Rule \{id: '(rule:[a-z0-9-]+)'", code))
    assert rules == {"rule:ts1-hard", "rule:avl", "rule:rank-value"}, rules
    assert "rankingPolicy" in code
    for kept in ("Asset", "Component", "Sensor", "StateVariable", "Part", "Supplier", "Role", "OrgUnit", "System", "Measure",
                 "Objective", "Perspective", "AnomalyPattern", "Symptom", "Action", "InputData", "Decision", "DecisionTable", "Process"):
        assert kept in labels, kept
    # 감시 패턴은 증상까지 이어지고(DETECTS), 증상 → 고장 유형(INDICATES)은 문서가 만든다
    assert "DETECTS" in code and "INDICATES" not in code


def test_full_edition_still_merges_every_label_the_full_read_back_lists():
    listed = set(re.findall(r"'([A-Za-z]+)'", ov.edition_checks(text("seed_checks.cypher"), "full")[0]))
    assert merged_labels(edition_code("full")) <= listed


def test_structure_read_back_lists_exactly_the_structure_labels():
    checks = ov.edition_checks(text("seed_checks.cypher"), "structure")
    listed = set(re.findall(r"'([A-Za-z]+)'", checks[0]))
    assert listed == merged_labels(edition_code("structure")) | {"Event", "FlowNode", "Gateway", "Task"} - set(), listed
    assert not listed & set(KNOWLEDGE)
    # 구조판에서는 선례 · 고장 유형 단언을 돌리지 않고, 설비 패턴 → 증상 단언을 돌린다
    assert not any("DecisionCase" in q and "seeded" in q for q in checks)
    assert not any("pattern not linked to a failure mode" in q for q in checks)
    assert any("equipment pattern without symptom" in q for q in checks)
    full = ov.edition_checks(text("seed_checks.cypher"), "full")
    assert any("no seeded DecisionCase" in q for q in full) and any("pattern not linked to a failure mode" in q for q in full)


def test_read_back_pattern_check_skips_the_stock_pattern_only():
    """결정 1(가): 재고 기준 이탈(SPARE_BELOW_MIN)은 설비 증상이 아니다. 단언은 held · plc-trip 이거나 증상을 잇는 패턴만 본다."""
    q = next(q for q in ov.edition_checks(text("seed_checks.cypher"), "full") if "pattern not linked" in q)
    assert "p.detectionMode IN ['held','plc-trip']" in q and "EXISTS { (p)-[:DETECTS]->(:Symptom) }" in q
    s = "\n".join(l for l in text("scenario_structure.cypher").splitlines() if not l.strip().startswith("//"))
    assert "SPARE_BELOW_MIN" in s and "detectionMode" not in s and "DETECTS" not in s


def test_seed_sh_selects_the_edition_and_defaults_to_the_teaching_structure():
    sh = (SEED / "seed.sh").read_text(encoding="utf-8")
    assert "EDITION=${SEED_EDITION:-structure}" in sh and ". \"$SEED_DIR/edition.sh\"" in sh
    for f in FILES:
        assert f"load {f}" in sh, f
    assert "seed_edition_checks \"$EDITION\"" in sh and "exit 1" in sh
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert "SEED_EDITION: ${SEED_EDITION:-structure}" in compose


def test_scenario_structure_uses_only_schema_classes_and_relationships():
    import json
    s = json.loads((ov.V2 / "schema.json").read_text(encoding="utf-8"))
    classes = {c["name"] for c in s["classes"]}
    rels = {r["type"] for r in s["relationships"]}
    code = "\n".join(l for l in text("scenario_structure.cypher").splitlines() if not l.strip().startswith("//"))
    assert set(re.findall(r"\(\s*\w*\s*:(\w+)", code)) <= classes
    assert set(re.findall(r"\[\s*\w*\s*:(\w+)", code)) <= rels
