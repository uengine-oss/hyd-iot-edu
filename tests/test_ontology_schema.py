"""Ontology v2: the schema is self-consistent, generated files are up to date, the instance script only uses
declared classes/relationships, and the validator actually catches violations."""
import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ontology_v2", ROOT / "scripts" / "ontology_v2.py")
ov = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ov)
S = ov.load_schema()
CLASSES = {c["name"] for c in S["classes"]}
RELS = {r["type"] for r in S["relationships"]}


def test_relationship_endpoints_are_declared_classes():
    for r in S["relationships"]:
        assert set(r["from"]) <= CLASSES and set(r["to"]) <= CLASSES, r["type"]
        for a, b in r.get('endpointPairs', []):
            assert a in r['from'] and b in r['to']


def test_execution_projection_schema_and_crossed_pairs():
    nodes = [_node(['ProcessInstance'], id='p.1', name='run', status='RUNNING', tenant_id='hyd'),
             _node(['WorkItem'], id='w', activity_id='t', activity_name='task', status='PENDING', tenant_id='hyd')]
    rels = [_rel('IN_INSTANCE', 'w', ['WorkItem'], 'p.1', ['ProcessInstance']),
            _rel('INSTANCE_OF', 'p.1', ['ProcessInstance'], 'p', ['Process'], version='1'),
            _rel('EXECUTES', 'w', ['WorkItem'], 't', ['Task'])]
    assert ov.validate(nodes, rels, S) == []
    for wrong in [_rel('INSTANCE_OF', 'p.1', ['ProcessInstance'], 'd', ['Decision']),
                  _rel('EXECUTES', 'w', ['WorkItem'], 's', ['Skill']),
                  _rel('EXECUTES', 't', ['Task'], 't2', ['Task'])]:
        assert '허용된 끝점 쌍' in '\n'.join(ov.validate([], [wrong], S))


def test_every_class_has_layer_standard_and_id_or_parent():
    layers = {l["id"] for l in S["layers"]}
    for c in S["classes"]:
        assert c["layer"] in layers and c["standard"], c["name"]
        assert any(p["name"] == "id" for p in ov.all_props(S, c["name"])), c["name"]


def test_no_process_words_as_classes():
    """The meeting's verdict: trigger, info type and decision scenario are not classes."""
    assert not CLASSES & {"Scenario", "InfoType", "Trigger", "Option", "BusinessProcess"}


def test_generated_files_are_up_to_date():
    assert (ov.V2 / "constraints.cypher").read_text(encoding="utf-8") == ov.gen_constraints(S)
    assert (ov.V2 / "ontology-schema.ttl").read_text(encoding="utf-8") == ov.gen_ttl(S)
    assert (ov.V2 / "schema_prompt.md").read_text(encoding="utf-8") == ov.gen_prompt(S)
    assert (ov.DOCS / "ontology-classes.svg").read_text(encoding="utf-8") == ov.gen_svg(S)
    assert ov.gen_class_table(S) in (ov.DOCS / "class-table.md").read_text(encoding="utf-8")


def test_every_class_has_a_korean_name_and_the_value_layer_is_bsc():
    assert all(c.get("label_ko") for c in S["classes"])
    value = {c["name"] for c in S["classes"] if c["layer"] == "value"}
    assert value == {"Perspective", "Objective", "Measure"} and "KPI" not in CLASSES
    by = {r["type"]: r for r in S["relationships"]}
    assert by["ACHIEVES"]["to"] == ["Objective"]          # 프로세스는 BSC 전략 목표(조직 목표)를 달성한다


def test_instance_script_uses_only_declared_labels_and_relationships():
    text = (ov.V2 / "instances.cypher").read_text(encoding="utf-8")
    code = "\n".join(l for l in text.splitlines() if not l.strip().startswith("//"))
    labels = set(re.findall(r"\(\s*\w*\s*:(\w+)", code)) | set(re.findall(r"SET \w+:(\w+)", code))
    rels = set(re.findall(r"\[\s*\w*\s*:(\w+)", code))
    assert labels <= CLASSES, labels - CLASSES
    assert rels <= RELS, rels - RELS


def _node(labels, **props):
    return {"labels": labels, "props": props}


def _rel(t, a, la, b, lb, **props):
    return {"type": t, "a": a, "b": b, "la": la, "lb": lb, "props": props}


def test_validator_passes_a_conforming_fragment():
    nodes = [_node(["Measure"], id="msr:a", name="A", unit="%", direction="UP"),
             _node(["Measure"], id="msr:b", name="B", unit="%", direction="DOWN"),
             _node(["Task", "FlowNode"], id="t", name="T", taskType="user")]
    rels = [_rel("INFLUENCES", "msr:a", ["Measure"], "msr:b", ["Measure"], sign=-1)]
    assert ov.validate(nodes, rels, S) == []


def test_validator_catches_each_kind_of_violation():
    nodes = [_node(["Scenario"], id="sc:1", name="x"),                                  # undeclared class
             _node(["Measure"], id="msr:a", name="A", unit="%"),                             # missing required direction
             _node(["Measure"], id="msr:b", name="B", unit="%", direction="SIDEWAYS"),       # bad enum
             _node(["Task"], id="t", name="T", taskType="user"),                         # missing parent label FlowNode
             _node(["Skill"], id="s", name="S", description="d", kind="control", color="red")]  # undeclared property
    rels = [_rel("INFLUENCES", "msr:a", ["Measure"], "msr:b", ["Measure"]),                    # missing sign
            _rel("INFLUENCES", "msr:a", ["Measure"], "msr:b", ["Measure"], sign=0),            # sign 0 is not allowed
            _rel("AFFECTS", "msr:a", ["Measure"], "s", ["Skill"], sign=1),                  # wrong endpoints
            _rel("HAS_OPTION", "msr:a", ["Measure"], "s", ["Skill"])]                       # undeclared relationship
    errs = "\n".join(ov.validate(nodes, rels, S))
    for needle in ["Scenario", "direction 없음", "SIDEWAYS", "부모 레이블 FlowNode", "속성 color",
                   "필수 속성 sign", "sign=0", "허용된 끝점", "HAS_OPTION"]:
        assert needle in errs, needle


def test_query_file_parses_with_questions_and_params():
    qs = ov.parse_queries((ov.V2 / "queries.cypher").read_text(encoding="utf-8"))
    assert len(qs) >= 10
    for q in qs:
        assert q["ask"] and q["cypher"].upper().startswith(("MATCH", "CALL")), q["name"]
        for p in re.findall(r"\$(\w+)", q["cypher"]):
            assert p in q["params"], (q["name"], p)


def test_skill_is_an_sop_matched_to_a_failure_mode():
    """조치 방법은 Skill(= SOP)이고 고장 유형에 매칭된다: 단계 없는 스킬, 고장 유형에 매칭되지 않은 스킬은 위반."""
    assert "Procedure" not in CLASSES and "FOLLOWS" not in RELS
    by = {r["type"]: r for r in S["relationships"]}
    assert by["HAS_STEP"]["from"] == ["Skill"]
    assert by["MITIGATED_BY"]["from"] == ["FailureMode"] and by["REMEDIED_BY"]["from"] == ["FailureMode"]
    skill = _node(["Skill"], id="skill:x", name="X", sopId="SOP-X-01", description="d", kind="control")
    step = _node(["Step"], id="SOP-X-01/1", order=1, text="t")
    fm = _node(["FailureMode"], id="fm:x", name="F")
    cause = _node(["Cause"], id="cause:x", name="C", prior=0.5)
    bare = "\n".join(ov.validate([skill], [], S))
    assert "SOP 단계" in bare and "고장 유형" in bare
    wrong_source = [_rel("HAS_STEP", "skill:x", ["Skill"], "SOP-X-01/1", ["Step"]),
                    _rel("MITIGATED_BY", "cause:x", ["Cause"], "skill:x", ["Skill"])]   # v1 style: cause → skill
    assert "고장 유형" in "\n".join(ov.validate([skill, step, cause], wrong_source, S))
    ok = [_rel("HAS_STEP", "skill:x", ["Skill"], "SOP-X-01/1", ["Step"]),
          _rel("MITIGATED_BY", "fm:x", ["FailureMode"], "skill:x", ["Skill"])]
    assert ov.validate([skill, step, fm], ok, S) == []


def test_minimal_set_bpmn_dmn_bsc_links_exist():
    """BPMN 시작 · 대상 · 데이터 출력, DMN 임계값 검사, 입력 데이터 → 상태 변수 · 성과 지표 연결이 스키마에 있다."""
    by = {r["type"]: r for r in S["relationships"]}
    assert by["ACTS_ON"]["from"] == ["Process"] and by["PRODUCES"]["to"] == ["InputData"]
    assert set(by["TESTS"]["from"]) == {"Rule", "AnomalyPattern"}
    assert {p["name"] for p in by["TESTS"]["properties"] if p.get("required")} == {"operator", "value"}
    assert set(by["REPRESENTS"]["to"]) == {"StateVariable", "Measure"}
    assert "USES" not in RELS
    hp = next(p for p in ov.classes_by_name(S)["DecisionTable"]["properties"] if p["name"] == "hitPolicy")
    assert hp["values"] == ["PRIORITY", "COLLECT"]


def _dmn_fixture(when="forecast_ts1 >= 65", declare=True, task_reads=True, sourced=True):
    nodes = [_node(["Decision"], id="dec:c", name="C", question="q"),
             _node(["DecisionTable"], id="dt:c", name="T", hitPolicy="COLLECT"),
             _node(["Rule"], id="rule:x", order=1, when=when, effect="EXCLUDE"),
             _node(["InputData"], id="in:f", name="F", typeRef="number", variable="forecast_ts1"),
             _node(["Task", "FlowNode"], id="task:c", name="검토", taskType="businessRule"),
             _node(["System"], id="sys:agent", name="A", zone="IT")]
    rels = [_rel("IMPLEMENTED_BY", "dec:c", ["Decision"], "dt:c", ["DecisionTable"]),
            _rel("HAS_RULE", "dt:c", ["DecisionTable"], "rule:x", ["Rule"]),
            _rel("TESTS", "rule:x", ["Rule"], "in:f", ["InputData"], operator=">=", value=65),
            _rel("INVOKES", "task:c", ["Task", "FlowNode"], "dec:c", ["Decision"])]
    if declare:
        rels.append(_rel("REQUIRES_INPUT", "dec:c", ["Decision"], "in:f", ["InputData"]))
    if task_reads:
        rels.append(_rel("READS", "task:c", ["Task", "FlowNode"], "in:f", ["InputData"]))
    if sourced:
        rels.append(_rel("SOURCED_FROM", "in:f", ["InputData"], "sys:agent", ["System"]))
    return nodes, rels


def test_integrity_passes_a_connected_threshold_rule():
    assert ov.integrity(*_dmn_fixture()) == []


def test_integrity_catches_dmn_and_bpmn_gaps():
    assert "드러나지 않는다" in "\n".join(ov.integrity(*_dmn_fixture(when="forecast_ts1 >= 60")))
    assert "REQUIRES_INPUT" in "\n".join(ov.integrity(*_dmn_fixture(declare=False)))
    assert "READS" in "\n".join(ov.integrity(*_dmn_fixture(task_reads=False)))
    assert "출처" in "\n".join(ov.integrity(*_dmn_fixture(sourced=False)))


def test_rule_without_threshold_test_is_a_violation_except_rank():
    rank = _node(["Rule"], id="rule:r", order=1, when="true", effect="RANK")
    bare = _node(["Rule"], id="rule:b", order=2, when="x > 1", effect="EXCLUDE")
    errs = "\n".join(ov.validate([rank, bare], [], S))
    assert "rule:b" in errs and "rule:r" not in errs
