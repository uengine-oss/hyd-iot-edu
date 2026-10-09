"""G4 (전체 과정 랩업 — docs/handoff/verification/2026-10-09/capstone-lab.md 3.3 안 다 · 5.2): 학생 온톨로지 이름 공간.

비유: 공용 사전(확정 스키마 v2)은 그대로 두고, 내 부서 용어집(students/<ID>/schema.json)을 덧대 공용 사전 단어에 잇는다.
① 검사기가 학생 스키마 파일을 "추가 층"으로 받는다(validate --extra · check-extra) — v2 는 그대로 검사, 학생 클래스는 학생 파일로.
② 학생 노드 규칙: ns = "<ID>" 필수, id 는 "<ID>:" 로 시작. ③ 지식 지도는 이름 공간을 고른다(기본 = 수업 기준, 학생 노드가 섞이지 않음).
확정 스키마 파일(it/neo4j/v2/schema.json)은 한 글자도 바꾸지 않는다.
"""
import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ontology_v2_g4", ROOT / "scripts" / "ontology_v2.py")
ov = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ov)
BASE = ov.load_schema()
TEMPLATE = ROOT / "students" / "_template" / "schema.json"
TEMPLATES = ROOT / "it" / "neo4j" / "templates"


def _node(labels, **props):
    return {"labels": labels, "props": props}


def _rel(t, a, la, b, lb, **props):
    return {"type": t, "a": a, "la": la, "b": b, "lb": lb, "props": props}


def _extra(ns="s01"):
    extra = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    extra["ns"] = ns
    return extra


def _student_graph(ns="s01"):
    p = f"{ns}:"
    nodes = [_node(["Meeting"], id=p + "meeting-q3", name="3분기 고객 리뷰", kind="customer_review", minAttendees=6, ns=ns),
             _node(["AgendaItem"], id=p + "agenda-1", name="지연 납기 건", status="open", ns=ns),
             _node(["Material"], id=p + "material-1", name="계약 요약", link="https://drive.example/f/1", ns=ns),
             _node(["Role"], id=p + "organizer", name="회의 주관자", level=2, ns=ns),                      # v2 클래스, 내 이름 공간
             _node(["KnowledgeSource"], id=p + "minutes-q2", name="2분기 회의록", kind="manual", ns=ns),
             _node(["Role"], id="role:operator", name="운전원", level=1)]                                   # 수업 기준 노드(다리 끝)
    rels = [_rel("HAS_AGENDA", p + "meeting-q3", ["Meeting"], p + "agenda-1", ["AgendaItem"]),
            _rel("NEEDS_MATERIAL", p + "meeting-q3", ["Meeting"], p + "material-1", ["Material"]),
            _rel("ORGANIZED_BY", p + "meeting-q3", ["Meeting"], p + "organizer", ["Role"]),
            _rel("RAISED_IN", p + "agenda-1", ["AgendaItem"], p + "minutes-q2", ["KnowledgeSource"])]
    return nodes, rels


# ---------------------------------------------------------------- 확정 스키마 변경 0 · 출발본 T1 이 형식 검사를 통과
def test_template_passes_and_the_confirmed_schema_is_not_touched():
    before = copy.deepcopy(BASE)
    extra = ov.load_extra(TEMPLATE)
    assert ov.check_extra(BASE, extra) == []
    merged = ov.merge_schema(BASE, extra)
    assert BASE == before and ov.load_schema() == before                                       # 합쳐도 원본은 그대로
    assert {c["name"] for c in merged["classes"]} - {c["name"] for c in BASE["classes"]} == {"Meeting", "AgendaItem", "Material"}
    assert ov.main(["check-extra", "--extra", str(TEMPLATE)]) == 0


def test_folder_name_is_the_namespace_when_the_file_has_none(tmp_path):
    folder = tmp_path / "students" / "s07"
    folder.mkdir(parents=True)
    extra = _extra(); extra.pop("ns")
    (folder / "schema.json").write_text(json.dumps(extra, ensure_ascii=False), encoding="utf-8")
    assert ov.load_extra(folder / "schema.json")["ns"] == "s07"


def test_student_schema_cannot_redefine_v2_names_and_must_use_the_same_format():
    bad = _extra("S 01")
    bad["classes"].append({"name": "Role", "label_ko": "역할", "layer": "resource", "properties": [{"name": "id"}, {"name": "name"}]})
    bad["classes"].append({"name": "Room", "label_ko": "회의실", "layer": "space", "properties": [{"name": "id"}, {"name": "name"}, {"name": "ns"}]})
    bad["classes"].append({"name": "Note", "layer": "resource", "properties": [{"name": "id"}]})
    bad["relationships"].append({"type": "PERFORMED_BY", "from": ["Meeting"], "to": ["Role"], "cardinality": "N:1"})
    bad["relationships"].append({"type": "BOOKS", "from": ["Meeting"], "to": ["Ghost"], "cardinality": "N:1"})
    bad["relationships"].append({"type": "LINKS_V2", "from": ["Task"], "to": ["System"], "cardinality": "N:1"})
    bad["relationships"].append({"type": "NO_CARD", "from": ["Meeting"], "to": ["Material"]})
    errs = "\n".join(ov.check_extra(BASE, bad))
    for phrase in ("ns:", "class Role: 확정 스키마 v2 에 있는 클래스", "layer 'space'", "ns 는 검사기가", "class Note: label_ko",
                   "class Note: id · name", "rel PERFORMED_BY: 확정 스키마 v2 에 있는 관계", "끝점 Ghost", "양 끝이 모두 v2", "rel NO_CARD: cardinality"):
        assert phrase in errs, phrase


# ---------------------------------------------------------------- 학생 노드 규칙(ns 필수 · id 접두어) + v2 · 학생 스키마로 검사
def test_a_clean_student_slice_passes_and_base_nodes_are_out_of_scope():
    nodes, rels = _student_graph()
    nodes.append(_node(["Role"], id="role:broken", name="기준인데 level 없음"))          # 수업 기준 노드의 결함은 학생 검사 범위 밖
    assert ov.validate_ns(nodes, rels, BASE, _extra()) == []
    mine, my_rels = ov.scope_to_ns(nodes, rels, "s01", ["Meeting", "AgendaItem", "Material"])
    assert {n["props"]["id"] for n in mine} == {"s01:meeting-q3", "s01:agenda-1", "s01:material-1", "s01:organizer", "s01:minutes-q2"}
    assert len(my_rels) == 4


def test_ns_rules_catch_missing_ns_wrong_prefix_and_schema_violations():
    nodes, rels = _student_graph()
    nodes[0]["props"].pop("ns")                                                       # 학생 클래스인데 ns 없음
    nodes[1]["props"]["id"] = "agenda-2"; rels[0]["b"] = "agenda-2"                  # 접두어 없음
    nodes[2]["props"]["color"] = "red"                                               # 학생 스키마에 없는 속성
    nodes[3]["props"].pop("level")                                                   # v2 Role 의 필수 속성은 학생 노드에도
    rels.append(_rel("HAS_AGENDA", "s01:material-1", ["Material"], "s01:agenda-1", ["AgendaItem"]))   # 끝점 틀림
    errs = "\n".join(ov.validate_ns(nodes, rels, BASE, _extra()))
    for phrase in ("node s01:meeting-q3: 학생 노드는 ns = 's01'", "node agenda-2: 학생 노드 id 는 's01:'", "스키마에 없는 속성 color",
                   "필수 속성 level 없음", "rel HAS_AGENDA: s01:material-1"):
        assert phrase in errs, phrase


def test_another_students_node_on_my_class_is_reported_and_ns_is_not_a_v2_property():
    nodes, rels = _student_graph()
    nodes.append(_node(["Meeting"], id="s02:meeting", name="남의 회의", kind="internal", ns="s02"))
    assert any("다른 이름 공간(s02)" in e for e in ov.validate_ns(nodes, rels, BASE, _extra()))
    # 수업 기준 검사(--extra 없음)는 지금처럼 v2 만 안다 — ns 를 단 노드는 v2 위반으로 보인다(학생 것은 --extra 로 검사)
    assert any("스키마에 없는 속성 ns" in e for e in ov.validate([_node(["Role"], id="s01:r", name="r", level=1, ns="s01")], [], BASE))


# ---------------------------------------------------------------- 지식 지도 이름 공간 고르기(기본 = 수업 기준)
def test_knowledge_map_templates_filter_by_namespace():
    nodes_q = (TEMPLATES / "t0_graph_nodes.cypher").read_text(encoding="utf-8")
    edges_q = (TEMPLATES / "t0_graph_edges.cypher").read_text(encoding="utf-8")
    assert "coalesce($ns, '') = '' THEN n.ns IS NULL" in nodes_q and "m.ns = $ns" in nodes_q
    assert "THEN a.ns IS NULL AND b.ns IS NULL ELSE a.ns = $ns OR b.ns = $ns" in edges_q
    assert "n.ns IS NOT NULL" in (TEMPLATES / "t0_namespaces.cypher").read_text(encoding="utf-8")


def test_knowledge_graph_passes_the_namespace():
    from agentsvc.tools.mcp_kg import KnowledgeGraph
    calls = []
    kg = object.__new__(KnowledgeGraph)
    kg._run = lambda name, **params: calls.append((name, params)) or []
    assert kg.graph("HYD-01") == {"nodes": [], "edges": []}
    kg.graph("HYD-01", "s01")
    kg.namespaces()
    assert calls == [("t0_graph_nodes", {"asset": "HYD-01", "ns": ""}), ("t0_graph_edges", {"asset": "HYD-01", "ns": ""}),
                     ("t0_graph_nodes", {"asset": "HYD-01", "ns": "s01"}), ("t0_graph_edges", {"asset": "HYD-01", "ns": "s01"}),
                     ("t0_namespaces", {})]
