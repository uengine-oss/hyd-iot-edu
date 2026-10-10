"""랩 키트 자료의 정합성: 실행 환경이 HYD 스택과 겹치지 않는가, 자료에서 계산한 기대값이 저장본 · 정답 예 · 판단 MCP 와 같은가,
학생 자료에 정답 · 비밀값 · 작업 흔적이 없는가."""
from __future__ import annotations

import json
import re

import pytest
import yaml

from test_labs_support import ANSWERS, INSTRUCTOR, KIT, LABS, REPO

import build_kit_data
import labpaths
from labcheck import facts
from labcheck.__main__ import LABS as LAB_REGISTRY

GUIDE_HEADINGS = ["## 만들 것", "## 왜 만드나", "## 주어지는 자료", "## Claude Code에 전달할 요구사항의 뼈대", "## 무엇이 나오면 성공", "## 다음 랩에서 어떻게 쓰이나"]
SYLLABUS_ROWS = [23, 24, 25, 34, 35, 36, 44, 45, 46, 47, 57, 58, 59, 67, 68, 69, 70, 71, 79, 80, 81]
VALID_CANDIDATES = {"C01", "C02", "C04", "C05", "C07", "C08", "C09", "C10"}
STUDENT_TEXT_SUFFIXES = {".md", ".json", ".csv", ".sql", ".yaml", ".toml", ".txt", ".py", ".cypher", ".example"}
WORK_TRACES = re.compile(r"HYD|instructor|정답 예|강사용|실라버스|갈래|worktree|TODO|FIXME|\bA1\d\d\b|행 \d\d")
HOST_PORT = re.compile(r"127\.0\.0\.1:(\d+):\d+")


def kit_files():
    return [path for path in KIT.rglob("*") if path.is_file() and "__pycache__" not in path.parts
            and ".egg-info" not in str(path) and path.name != ".env" and path.parts[len(KIT.parts)] not in ("work", ".claude")
            and path.name != ".mcp.json"]


def compose(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def host_ports(config: dict) -> set[int]:
    return {int(port) for service in config["services"].values() for mapping in service.get("ports", [])
            for port in HOST_PORT.findall(str(mapping))}


# ── 실행 환경 ─────────────────────────────────────────────────
def test_lab_compose_is_separate_from_the_course_stack():
    lab = compose(KIT / "compose.yaml")
    assert lab["name"] == "cooler-lab"
    lab_ports = host_ports(lab)
    assert lab_ports == {17474, 17687, 15432, 18198}
    assert not lab_ports & host_ports(compose(REPO / "compose.yaml")), "루트 compose.yaml 과 호스트 포트가 겹친다"
    assert not {port for port in lab_ports if 54320 <= port <= 54330}, "Supabase 로컬 포트와 겹친다"
    for name, service in lab["services"].items():
        assert all(str(mapping).startswith("127.0.0.1:") for mapping in service["ports"]), f"{name}: 바깥에 열린 포트"
    assert set(lab["volumes"]) == {"lab-neo4j-data", "lab-db-data"}


def test_lab_compose_takes_passwords_only_from_env():
    services = compose(KIT / "compose.yaml")["services"]
    assert services["lab-neo4j"]["environment"]["NEO4J_AUTH"].startswith("neo4j/${LAB_NEO4J_PASSWORD:?")
    assert services["lab-db"]["environment"]["POSTGRES_PASSWORD"].startswith("${LAB_DB_PASSWORD:?")
    assert "environment" not in services["lab-judge-mcp"]


def test_neo4j_browser_points_at_the_lab_graph_not_the_course_graph():
    lab = compose(KIT / "compose.yaml")
    assert lab["services"]["lab-neo4j"]["environment"]["NEO4J_server_bolt_advertised__address"] == "127.0.0.1:17687"


def test_env_example_and_mcp_templates_hold_placeholders_only():
    for line in (KIT / ".env.example").read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition("=")
        if any(word in key for word in ("PASSWORD", "TOKEN", "API_KEY")):
            assert value.startswith("<") and value.endswith(">"), f"{key} 에 실제 값처럼 보이는 것이 있다"
    for template in (KIT / "day6" / "mcp" / "lab.mcp.json", KIT / "day6" / "notion" / "notion.mcp.example.json"):
        for server in json.loads(template.read_text(encoding="utf-8"))["mcpServers"].values():
            for key, value in server.get("env", {}).items():
                assert re.fullmatch(r"\$\{[A-Z0-9_]+\}", value) or key == "NEO4J_READ_ONLY", f"{template.name} {key}"
    neo4j = json.loads((KIT / "day6" / "mcp" / "lab.mcp.json").read_text(encoding="utf-8"))["mcpServers"]["lab-neo4j"]
    assert neo4j["env"]["NEO4J_READ_ONLY"] == "true"


# ── 자료에서 계산한 값 ──────────────────────────────────────────
def test_computed_kit_files_match_their_sources():
    stale = [str(path.relative_to(LABS)) for path, text in build_kit_data.outputs().items()
             if not path.is_file() or path.read_text(encoding="utf-8") != text]
    assert not stale, f"자료를 고친 뒤 build_kit_data.py 를 다시 돌리지 않았다: {stale}"


def test_csv_references_resolve():
    assets = {row["asset_id"] for row in facts.read_csv("day2/data/assets.csv")}
    components = {row["component_id"]: row["asset_id"] for row in facts.read_csv("day2/data/components.csv")}
    assert set(components.values()) <= assets
    tags = set()
    for sensor in facts.read_csv("day2/data/sensors.csv"):
        assert sensor["asset_id"] in assets and components[sensor["component_id"]] == sensor["asset_id"]
        tags.add(sensor["tag"])
    seed = (KIT / "day4" / "db" / "init.sql").read_text(encoding="utf-8")
    assert tags == set(re.findall(r"\('(CL\d\d_\w+)',\s+'CL-\d\d', '", seed)), "센서 tag 와 연습용 DB 의 tags 가 다르다"
    actions = {row["action_id"] for row in facts.read_csv("day3/data/actions.csv")}
    measures = {row["measure_id"] for row in facts.read_csv("day3/data/measures.csv")}
    for effect in facts.read_csv("day3/data/action_effects.csv"):
        assert effect["action_id"] in actions and effect["measure_id"] in measures and effect["effect"] in ("긍정", "부정")
    assert facts.mapped_assets("CM-01") == assets


def test_prepared_candidates_mix_valid_and_three_kinds_of_wrong():
    problems = {c["id"]: facts.candidate_problem(c) for c in facts.prepared_candidates()}
    assert {cid for cid, problem in problems.items() if problem is None} == VALID_CANDIDATES
    assert "나오지 않습니다" in problems["C03"]          # 있는 문장을 다른 고장에 이음
    assert "인용 문장이 다릅니다" in problems["C06"]      # 없는 문장
    assert "인용 문장이 다릅니다" in problems["C11"]      # 문장은 있으나 위치가 틀림
    manual = facts.MANUAL_FILE.read_text(encoding="utf-8")
    by_id = {c["id"]: c for c in facts.prepared_candidates()}
    assert by_id["C03"]["source"]["quote"] in manual and by_id["C11"]["source"]["quote"] in manual
    assert by_id["C06"]["source"]["quote"] not in manual


def test_answer_review_agrees_with_the_source_check():
    review = json.loads((ANSWERS / "work" / "review.json").read_text(encoding="utf-8"))
    assert {cid for cid, entry in review.items() if entry["decision"] == "채택"} == facts.valid_candidate_ids()
    assert set(review) == {c["id"] for c in facts.prepared_candidates()}


def test_manual_names_only_actions_the_kit_defines():
    known = {row["name"] for row in facts.read_csv("day3/data/actions.csv")}
    named = {c["to"]["name"] for c in facts.prepared_candidates() if c["relation"] == "REMEDIED_BY" and c["id"] in VALID_CANDIDATES}
    assert named - known == {"호스 연결부 조이기"}


# ── 결정표 ────────────────────────────────────────────────────
PREPARED_EXPECTATIONS = {
    "normal.json": {"ACT-FAN-UP": ("제외", "F4"), "ACT-LOAD-DOWN": ("제외", "L3"), "ACT-FIN-CLEAN": ("허용", "C3")},
    "just_above.json": {"ACT-FAN-UP": ("허용", "F3"), "ACT-LOAD-DOWN": ("경고", "L2"), "ACT-FIN-CLEAN": ("허용", "C3")},
    "overlap.json": {"ACT-FAN-UP": ("경고", "F2"), "ACT-LOAD-DOWN": ("허용", "L1"), "ACT-FIN-CLEAN": ("제외", "C1")},
}
BOUNDARY_EXPECTATIONS = [
    ({"temp_c": 45, "fan_state": "정상", "load_pct": 50}, "ACT-FAN-UP", "제외"),
    ({"temp_c": 45.1, "fan_state": "정상", "load_pct": 50}, "ACT-FAN-UP", "허용"),
    ({"temp_c": 60, "fan_state": "정상", "load_pct": 50}, "ACT-LOAD-DOWN", "경고"),
    ({"temp_c": 60.1, "fan_state": "정상", "load_pct": 50}, "ACT-LOAD-DOWN", "허용"),
    ({"temp_c": 60, "fan_state": "정상", "load_pct": 80}, "ACT-FIN-CLEAN", "허용"),
    ({"temp_c": 60.1, "fan_state": "정상", "load_pct": 80}, "ACT-FIN-CLEAN", "경고"),
    ({"temp_c": 50, "fan_state": "정상", "load_pct": 80.1}, "ACT-FIN-CLEAN", "제외"),
    ({"temp_c": 62, "fan_state": "정상", "load_pct": 30}, "ACT-LOAD-DOWN", "제외"),
    ({"temp_c": 62, "fan_state": "정상", "load_pct": 30.1}, "ACT-LOAD-DOWN", "허용"),
    ({"temp_c": 40, "fan_state": "약함", "load_pct": 50}, "ACT-FAN-UP", "제외"),
    ({"temp_c": 70, "fan_state": "정지", "load_pct": 50}, "ACT-FAN-UP", "제외"),
]


def judge():
    engine = labpaths.judge_engine()
    return engine, engine.load_table(KIT / "day6" / "judge_mcp" / "decision_table.json")


def answer_evaluate():
    return labpaths.load_module("cooler_answer_evaluate", ANSWERS / "work" / "evaluate.py")


def test_decision_table_gives_the_hand_checked_results():
    engine, table = judge()
    for name, wanted in PREPARED_EXPECTATIONS.items():
        values = json.loads((KIT / "day3" / "inputs" / name).read_text(encoding="utf-8"))
        got = engine.evaluate(table, values)["actions"]
        assert {action: (item["result"], item["applied_rule"]) for action, item in got.items()} == wanted, name
    for values, action, result in BOUNDARY_EXPECTATIONS:
        assert engine.evaluate(table, values)["actions"][action]["result"] == result, (values, action)
    overlap = json.loads((KIT / "day3" / "inputs" / "overlap.json").read_text(encoding="utf-8"))
    assert engine.evaluate(table, overlap)["actions"]["ACT-FIN-CLEAN"]["matched_rules"] == ["C1", "C2"]


def test_decision_rules_document_lists_every_rule_of_the_table():
    _, table = judge()
    document = (KIT / "day3" / "decision_rules.md").read_text(encoding="utf-8")
    for rule in table["rules"]:
        row = next(line for line in document.splitlines() if line.startswith(f"| {rule['id']} |"))
        assert f"| {rule['result']} |" in row and rule["reason"] in row, rule["id"]
    assert set(table["actions"]) == {row["action_id"] for row in facts.read_csv("day3/data/actions.csv")}


def test_answer_evaluator_and_judge_engine_agree_everywhere():
    engine, table = judge()
    answer = answer_evaluate()
    assert json.loads((ANSWERS / "work" / "decision_table.json").read_text(encoding="utf-8")) == table
    expected = json.loads((KIT / "labcheck" / "expected" / "decision.json").read_text(encoding="utf-8"))
    for case in [*expected["cases"], *expected["boundaries"]]:
        assert answer.evaluate(table, case["input"]) == engine.evaluate(table, case["input"])
        assert {a: item["result"] for a, item in engine.evaluate(table, case["input"])["actions"].items()} == case["results"]


@pytest.mark.parametrize("values", [
    {"temp_c": 50, "fan_state": "모름", "load_pct": 50},
    {"temp_c": 50, "fan_state": "정상"},
    {"temp_c": "뜨거움", "fan_state": "정상", "load_pct": 50},
    {"temp_c": 50, "fan_state": "정상", "load_pct": 130},
    {"temp_c": True, "fan_state": "정상", "load_pct": 50},
])
def test_decision_engines_refuse_inputs_outside_the_table(values):
    engine, table = judge()
    with pytest.raises(engine.DecisionError):
        engine.evaluate(table, values)
    with pytest.raises(answer_evaluate().DecisionError):
        answer_evaluate().evaluate(table, values)


def test_decision_engine_reports_a_gap_instead_of_inventing_a_result():
    engine, table = judge()
    holed = {**table, "rules": [rule for rule in table["rules"] if rule["id"] != "C3"]}
    with pytest.raises(engine.DecisionError, match="맞는 규칙이 없습니다"):
        engine.evaluate(holed, {"temp_c": 40, "fan_state": "정상", "load_pct": 50})
    with pytest.raises(engine.DecisionError, match="결정표에 없는 조치"):
        engine.evaluate(table, {"temp_c": 40, "fan_state": "정상", "load_pct": 50}, ["ACT-NONE"])


def test_day7_cases_carry_the_judgement_the_table_gives():
    engine, table = judge()
    for path in (KIT / "day7" / "inputs" / "case_base.json", KIT / "day7" / "inputs" / "case_no_window.json",
                 KIT / "labcheck" / "fixtures" / "day7" / "case_highload.json"):
        case = json.loads(path.read_text(encoding="utf-8"))
        judged = engine.evaluate(table, case["condition"])["actions"]
        for candidate in case["candidates"]:
            outcome = judged[candidate["action_id"]]
            assert candidate["judgement"] == {"result": outcome["result"], "applied_rule": outcome["applied_rule"]}, path.name
            for evidence in candidate["evidence"]:
                if evidence["kind"] == "문서":
                    assert facts.source_problem(evidence, []) is None, f"{path.name}: 매뉴얼에 없는 근거"


# ── 학생 자료 ─────────────────────────────────────────────────
def test_every_lab_has_a_one_page_guide_with_the_six_parts():
    readme = (KIT / "README.md").read_text(encoding="utf-8")
    guides = re.findall(r"\| (\d-\d) \| [^|]+ \| `(day\d/lab\d_\w+\.md)` \|", readme)
    assert [number for number, _ in guides] == list(LAB_REGISTRY)
    for number, relative in guides:
        text = (KIT / relative).read_text(encoding="utf-8")
        assert text.startswith(f"# {number} · "), relative
        positions = [text.find(heading) for heading in GUIDE_HEADINGS]
        assert all(position > 0 for position in positions) and positions == sorted(positions), f"{relative}: 여섯 항목이 빠졌거나 순서가 다르다"
        assert f"python -m labcheck {number}" in text, f"{relative}: 자동 확인 명령이 없다"
    assert len(list(KIT.glob("day*/lab*.md"))) == len(LAB_REGISTRY)


def test_guides_point_only_at_files_that_exist():
    for guide in [KIT / "README.md", *KIT.glob("day*/lab*.md"), *KIT.glob("cooler/*.md")]:
        for relative in re.findall(r"`((?:day\d|cooler|labkit|labcheck)/[\w./-]+\.\w+)`", guide.read_text(encoding="utf-8")):
            assert (KIT / relative).exists(), f"{guide.name}: 없는 파일 {relative}"


def test_student_kit_carries_no_answers_or_work_traces():
    answer_names = {path.name for path in (ANSWERS / "work").rglob("*.py")} | {"review.json", "candidates.json", "SKILL.md"}
    for path in kit_files():
        assert path.name not in answer_names or "labcheck" in path.parts or "judge_mcp" in path.parts, f"정답 예와 같은 이름의 파일: {path}"
        if path.suffix in STUDENT_TEXT_SUFFIXES and path.suffix != ".py":
            found = WORK_TRACES.search(path.read_text(encoding="utf-8"))
            assert not found, f"{path.relative_to(KIT)}: 학생 자료에 '{found.group()}'"
    tracked_work = [path.name for path in (KIT / "work").iterdir()] if (KIT / "work").is_dir() else []
    assert ".gitkeep" in tracked_work


def test_instructor_readme_maps_every_lab_to_its_syllabus_row():
    text = (INSTRUCTOR / "README.md").read_text(encoding="utf-8")
    for number, row in zip(LAB_REGISTRY, SYLLABUS_ROWS, strict=True):
        assert re.search(rf"\| {number} \| {row} \|", text), f"{number} ↔ {row}행"
