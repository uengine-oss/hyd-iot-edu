"""수업 준비물 students/flows/ — bpmn.io 에서 열리는 A · B · C 참조 흐름이 강사 스택의 정의(scripts/c3_flows.py)와 어긋나지 않는다.

그림 파일은 사람이 bpmn.io 에서 그려 내보낸 형태(collaboration · incoming/outgoing · 그림 배치 bpmndi)라 c3_flows 의 글자와는 다르다. 그래서
글자가 아니라 ① 포털 가져오기가 읽은 구조 ② 같은 연결 값으로 사전 검사를 통과해 나온 **실행 정의** ③ 안내문이 말하는 선택을 맞춰 본다."""
import json
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path

import pytest

from procsvc import bpmn_import as B
from test_instance_mode import world  # noqa: F401  (world 는 fixture)
import test_c3_assembly as c3

ROOT = Path(__file__).resolve().parents[1]
FLOWS_DIR = ROOT / "students" / "flows"
BPMN, DI, DC = (f"{{http://www.omg.org/spec/{p}}}" for p in ("BPMN/20100524/MODEL", "BPMN/20100524/DI", "DD/20100524/DC"))
IDS = sorted(c3._flows().FLOWS)
NODE_KINDS = ("tasks", "starts", "ends", "boundaries", "gateways")
SCENARIO = {"c3_cooling": "A", "c3_pm": "B", "c3_spare": "C"}
SOURCE_ONLY = "bpmnImport"            # 정의에서 원본 파일(이름 · 해시)만 적는 칸 — 그림 글자가 다르니 다를 수밖에 없다


def drawn(did: str) -> tuple[str, dict]:
    fname = c3._flows().FLOWS[did][0]
    return (FLOWS_DIR / fname).read_text(encoding="utf-8"), json.loads((FLOWS_DIR / fname.replace(".bpmn", ".mapping.json")).read_text(encoding="utf-8"))


def shape(parsed: dict) -> dict:
    """가져오기가 읽은 구조에서 실행에 쓰이는 것: 요소(종류 · 이름 · 붙은 곳 · 멈춤 여부) · 선 · 칸 이름 · task 가 놓인 칸."""
    lane_name = {l["id"]: l["name"] for l in parsed["lanes"]}
    nodes = {n["id"]: {k: v for k, v in n.items() if k != "lane"} for kind in NODE_KINDS for n in parsed[kind]}
    return {"process": parsed["process"], "nodes": nodes, "flows": {f["id"]: f for f in parsed["flows"]},
            "lanes": [l["name"] for l in parsed["lanes"]], "task_lane": {t["id"]: lane_name.get(t["lane"]) for t in parsed["tasks"]}}


def definition(world, did: str, xml: str, mapping: dict) -> dict:
    rt = world["rt"]
    base = rt.definition_for({"proc_def_id": rt.defn.id, "proc_def_version": rt.base_version, "tenant_id": rt.tenant_id}).raw
    r = B.check(B.parse_bpmn(xml), deepcopy(mapping), {"catalog": B.catalog(base, c3.AGENTS), "definition_id": did, "version": "1",
                                                       "file_name": "f.bpmn", "xml_sha256": "x"})
    assert r["ok"], r["problems"]
    return {k: v for k, v in r["definition"].items() if k != SOURCE_ONLY}


@pytest.mark.parametrize("did", IDS)
def test_the_drawn_file_reads_as_the_same_flow_and_runs_as_the_same_definition(world, did):
    _, src, mapping = c3._flows().FLOWS[did]
    xml, drawn_mapping = drawn(did)
    theirs, ours = B.parse_bpmn(xml), B.parse_bpmn(src)
    assert not theirs["problems"] and shape(theirs) == shape(ours)
    assert drawn_mapping == mapping                                       # 연결 값 파일 = 강사 스택이 배포하는 연결 값
    assert definition(world, did, xml, drawn_mapping) == definition(world, did, src, mapping)
    assert SOURCE_ONLY in B.check(B.parse_bpmn(xml), deepcopy(mapping), {
        "catalog": B.catalog(world["rt"].defn.raw, c3.AGENTS), "definition_id": did, "version": "1", "file_name": "f.bpmn", "xml_sha256": "x"})["definition"]


@pytest.mark.parametrize("did", IDS)
def test_the_drawn_file_is_a_bpmn_io_export_with_every_element_placed(did):
    """bpmn.io 형태: 풀 하나 · 메시지 시작 · 모든 요소와 선에 자리(bpmndi)가 있고, 모든 요소가 자기가 그려진 칸에 들어 있다."""
    root = ET.fromstring(drawn(did)[0])
    assert root.get("exporter", "").startswith("bpmn-js") and len(root.findall(f"{BPMN}collaboration/{BPMN}participant")) == 1
    proc = root.find(f"{BPMN}process")
    assert proc.find(f"{BPMN}startEvent/{BPMN}messageEventDefinition") is not None
    elements = {el.get("id"): el for el in proc if el.tag != f"{BPMN}laneSet"}
    lanes = {l.get("id"): [r.text for r in l] for l in proc.iter(f"{BPMN}lane")}
    placed = {s.get("bpmnElement"): s.find(f"{DC}Bounds") for s in root.iter(f"{DI}BPMNShape")}
    edges = {e.get("bpmnElement"): e for e in root.iter(f"{DI}BPMNEdge")}
    flows = {i for i, el in elements.items() if el.tag == f"{BPMN}sequenceFlow"}
    assert set(placed) == (set(elements) - flows) | set(lanes) | {root.find(f"{BPMN}collaboration/{BPMN}participant").get("id")}
    assert set(edges) == flows and all(len(e.findall("{http://www.omg.org/spec/DD/20100524/DI}waypoint")) >= 2 for e in edges.values())
    boundaries = {i for i, el in elements.items() if el.tag == f"{BPMN}boundaryEvent"}
    assert sorted(n for ns in lanes.values() for n in ns) == sorted(set(elements) - flows - boundaries)      # 요소마다 칸 하나
    for lane, nodes in lanes.items():
        top, height = float(placed[lane].get("y")), float(placed[lane].get("height"))
        for n in nodes:
            middle = float(placed[n].get("y")) + float(placed[n].get("height")) / 2
            assert top <= middle < top + height, (lane, n)
    for fid in flows:                                                     # incoming · outgoing 이 선과 맞는다(bpmn.io 가 쓰는 대로)
        f = elements[fid]
        assert fid in [o.text for o in elements[f.get("sourceRef")].findall(f"{BPMN}outgoing")]
        assert fid in [o.text for o in elements[f.get("targetRef")].findall(f"{BPMN}incoming")]


def test_the_guide_names_every_step_with_the_part_and_person_the_mapping_picks(world):
    """안내문(README)의 표가 실제 선택과 같다: 단계 이름 · 포털에 보이는 부품 이름 · 에이전트 이름 · 역할 · 시작 경보 · 조건 · 기한."""
    guide = (FLOWS_DIR / "README.md").read_text(encoding="utf-8")
    rt = world["rt"]
    base = rt.definition_for({"proc_def_id": rt.defn.id, "proc_def_version": rt.base_version, "tenant_id": rt.tenant_id}).raw
    cat = B.catalog(base, c3.AGENTS)
    part_name = {p["key"]: p["name"] for p in cat["parts"]}
    agent_name = {a["id"]: a["name"] for a in cat["agents"]}
    for did in IDS:
        fname, src, mapping = c3._flows().FLOWS[did]
        section = guide.split(f"### {SCENARIO[did]} {mapping['name']}")[1].split("\n### ")[0].split("\n## ")[0]
        common = guide.split("### 세 흐름 공통")[1].split("\n### ")[0]
        assert fname in guide and fname.replace(".bpmn", ".mapping.json") in guide and mapping["name"] in guide
        assert all(f"`{p}`" in section for p in mapping["start"]["patterns"]), did
        for t in B.parse_bpmn(src)["tasks"]:
            spec = mapping["tasks"][t["id"]]
            where = common if t["id"] in ("T_approve", "T_notice", "R_rejected") else section
            rows = [r for r in where.splitlines() if r.startswith("|") and part_name[spec["part"]] in r]
            assert rows, (did, t["name"], part_name[spec["part"]])
            if spec.get("agent"):
                assert any(agent_name[spec["agent"]] in r for r in rows), (did, t["name"])
            if spec.get("role"):
                assert spec["role"] in common, (did, spec["role"])
            if spec["part"] == "svc:report":
                assert f'"{spec["config"]["outcome"]}"' in where, (did, t["name"], spec["config"]["outcome"])
        assert all(f"`{d}`" in common for d in mapping["timers"].values())
        for cond in mapping["flows"].values():
            if "var" in cond:
                assert f"`{B.condition_text(cond)}`" in guide, B.condition_text(cond)


def test_a_decide_agent_without_the_decision_engine_is_caught_before_deploy(world):
    # 2026-10-23 점검: 실습 6-5 · 6-7은 4회차에 만든 에이전트(필요한 서버만 연결)를 「판단 · 제안」에 붙인다. 판단 엔진(hyd-dmn)이
    # 없으면 사전 검사는 통과하고 실행 때 evaluate_cards · submit_decision 을 못 불러 그 단계가 실패했다
    did = "c3_cooling"
    _, src, mapping = c3._flows().FLOWS[did]
    base = world["rt"].defn.raw
    node = next(k for k, v in mapping["tasks"].items() if v.get("part") == "task:decide")
    def run(tools):
        agents = c3.AGENTS + [{"id": "agent:student", "username": "학생 에이전트", "is_agent": True, "agent_type": "agent", "tools": tools}]
        m = deepcopy(mapping); m["tasks"][node]["agent"] = "agent:student"
        return B.check(B.parse_bpmn(src), m, {"catalog": B.catalog(base, agents), "definition_id": did, "version": "1",
                                              "file_name": "f.bpmn", "xml_sha256": "x"})
    bad = run("neo4j,enterprise")
    assert not bad["ok"] and any("판단 엔진(hyd-dmn)에 연결되어 있지 않습니다" in p["reason"] and p["field"] == "agent" for p in bad["problems"])
    assert run("neo4j,enterprise,hyd-dmn")["ok"]
    assert run(None)["ok"]                    # 도구를 고르지 않은 에이전트는 등록된 서버를 모두 쓴다
