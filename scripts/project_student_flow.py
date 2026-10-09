"""G8 (전체 과정 랩업 — docs/handoff/verification/2026-10-09/capstone-lab.md 5.2): 학생 흐름을 학생 이름 공간 지식 그래프에 투영한다.

기준 흐름(A · B · C)의 Process · Task 는 시드(it/neo4j/v2/instances.cypher 500~540행)에 있지만, 학생이 가져온 흐름은 그래프에 생기지 않는다.
이 스크립트가 흐름 정의(포털 판본 등록 JSON = proc_def.definition, 흐름 가져오기가 만든 것)를 읽어 v2 클래스 · 관계로 MERGE 한다:

  Process(<ns>:proc:<정의 id>) -HAS_NODE-> Event · Task · Gateway(<ns>:<노드 id>) -SEQUENCE_FLOW {condition}-> …
  Task -PERFORMED_BY-> Role — 레인의 역할이 수업 기준 Role(ns 없음, 예 role:operator)이면 그 노드에 잇고(다리 관계),
                               없으면 학생 Role(<ns>:<역할 endpoint>, level 1)을 만든다. 시스템 수행자(sys:*)는 있는 노드에만 잇는다.
모든 노드에 ns · definition_id · element_id(원래 id) · source_type='student_flow'. 기준 흐름 · 시드 노드는 만들거나 바꾸지 않는다.
다시 돌리면 그 정의의 이전 투영(같은 ns · definition_id)을 지우고 다시 만든다(멱등). 포털 자동화는 하지 않는다(설계: 선택, 출발본 T2).

  python scripts/project_student_flow.py --definition my_flow.json --ns s01 --check [--extra students/s01/schema.json]   # 그래프 없이 검사만
  python scripts/project_student_flow.py --definition my_flow.json --ns s01 [--uri bolt://127.0.0.1:7687]               # 적재
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ontology_v2 as ov  # noqa: E402

SOURCE_TYPE = "student_flow"
TASK_TYPES = {"userTask": "user", "serviceTask": "service", "businessRuleTask": "businessRule", "manualTask": "manual", "scriptTask": "script",
              "sendTask": "send", "receiveTask": "receive", "subProcess": "subProcess", "callActivity": "callActivity", "task": "user"}
EVENT_POSITIONS = {"startEvent": "start", "endEvent": "end", "boundaryEvent": "boundary"}
EVENT_DEFS = ("none", "message", "timer", "escalation")
GATEWAY_TYPES = {"exclusiveGateway": "exclusive", "parallelGateway": "parallel"}
AGENT_MODES = ("DRAFT", "COMPLETE")


def _condition(seq: dict) -> str | None:
    c = seq.get("condition") if "condition" in seq else seq.get("conditionExpression")
    if c in (None, "", {}):
        return None
    return c if isinstance(c, str) else json.dumps(c, ensure_ascii=False, sort_keys=True)


def project(defn: dict, ns: str) -> dict:
    """정의 JSON → {process, nodes, sequences, performers, problems}. 그래프에 닿지 않는 순수 함수(시험 · --check 가 쓴다)."""
    if not ov.NS_RE.match(ns or ""):
        raise ValueError(f"ns {ns!r}: 소문자로 시작하는 소문자 · 숫자 · 하이픈 32자 이내")
    did = str(defn.get("processDefinitionId") or defn.get("id") or "").strip()
    if not did:
        raise ValueError("정의에 processDefinitionId 가 없습니다")
    p = f"{ns}:"
    common = {"ns": ns, "definition_id": did, "source_type": SOURCE_TYPE}
    process = {"id": f"{p}proc:{did}", "name": str(defn.get("processDefinitionName") or did), "isExecutable": True, "ns": ns}
    nodes, problems = [], []
    roles = {str(r.get("name")): r for r in defn.get("roles") or [] if isinstance(r, dict)}
    for e in defn.get("events") or []:
        position = EVENT_POSITIONS.get(e.get("type"))
        if position is None:
            problems.append(f"event {e.get('id')}: 종류 {e.get('type')!r} 는 v2 Event 가 아니다(start · end · boundary)")
            continue
        definition = e.get("eventDefinition") if e.get("eventDefinition") in EVENT_DEFS else "none"
        props = dict(common, id=p + e["id"], name=str(e.get("name") or e["id"]), element_id=e["id"], position=position, eventDefinition=definition)
        if definition == "timer" and e.get("timer"):
            props["timer"] = str(e["timer"])
        nodes.append({"labels": ["FlowNode", "Event"], "props": props, "attached_to": p + e["attachedTo"] if e.get("attachedTo") else None})
    performers = []
    for a in defn.get("activities") or []:
        props = dict(common, id=p + a["id"], name=str(a.get("name") or a["id"]), element_id=a["id"], taskType=TASK_TYPES.get(a.get("type"), "user"))
        if a.get("tool"):
            props["tool"] = str(a["tool"])
        if a.get("agentMode") in AGENT_MODES:
            props["agentMode"] = a["agentMode"]
        if a.get("orchestration"):
            props["orchestration"] = str(a["orchestration"])
        nodes.append({"labels": ["FlowNode", "Task"], "props": props})
        role = roles.get(str(a.get("role") or ""))
        endpoint = str((role or {}).get("endpoint") or "").split(",")[0].strip()
        if a.get("role") and not endpoint:
            problems.append(f"task {a['id']}: 레인(역할) {a.get('role')!r} 의 endpoint 가 정의 roles 에 없다")
        elif endpoint:
            performers.append({"task": p + a["id"], "endpoint": endpoint, "name": str(role.get("name")), "own": f"{p}{endpoint}",
                               "kind": "role" if endpoint.startswith("role:") else "system"})
    for g in defn.get("gateways") or []:
        kind = GATEWAY_TYPES.get(g.get("type"))
        if kind is None:
            problems.append(f"gateway {g.get('id')}: 종류 {g.get('type')!r} 는 v2 Gateway 가 아니다(exclusive · parallel)")
            continue
        nodes.append({"labels": ["FlowNode", "Gateway"], "props": dict(common, id=p + g["id"], name=str(g.get("name") or g["id"]), element_id=g["id"],
                                                                         gatewayType=kind)})
    ids = {n["props"]["id"] for n in nodes}
    sequences = []
    for s in defn.get("sequences") or []:
        a, b = p + str(s.get("source")), p + str(s.get("target"))
        if a not in ids or b not in ids:
            problems.append(f"sequence {s.get('id')}: 끝 {s.get('source')} → {s.get('target')} 가 노드에 없다")
            continue
        props = {k: v for k, v in (("id", p + str(s["id"]) if s.get("id") else None), ("condition", _condition(s))) if v is not None}
        sequences.append({"a": a, "b": b, "props": props})
    return {"process": process, "nodes": nodes, "sequences": sequences, "performers": performers, "problems": problems, "definition_id": did, "ns": ns}


def records(proj: dict, base_roles: set[str] = frozenset(), base_systems: set[str] = frozenset()) -> tuple[list[dict], list[dict]]:
    """검사용 노드 · 관계 행(ontology_v2.validate 형식). base_*: 그래프에 이미 있는 수업 기준 Role · System id(다리 관계 끝)."""
    nodes = [{"labels": ["Process"], "props": proj["process"]}] + [{"labels": n["labels"], "props": n["props"]} for n in proj["nodes"]]
    label_of = {n["props"]["id"]: n["labels"] for n in nodes}
    rels = [{"type": "HAS_NODE", "a": proj["process"]["id"], "la": ["Process"], "b": n["props"]["id"], "lb": n["labels"], "props": {}} for n in proj["nodes"]]
    rels += [{"type": "SEQUENCE_FLOW", "a": s["a"], "la": label_of[s["a"]], "b": s["b"], "lb": label_of[s["b"]], "props": s["props"]} for s in proj["sequences"]]
    rels += [{"type": "ATTACHED_TO", "a": n["props"]["id"], "la": n["labels"], "b": n["attached_to"], "lb": label_of.get(n["attached_to"], []), "props": {}}
             for n in proj["nodes"] if n.get("attached_to")]
    own_roles = {}
    for pf in proj["performers"]:
        if pf["kind"] == "role" and pf["endpoint"] in base_roles:
            nodes_b, target = ["Role"], pf["endpoint"]
        elif pf["kind"] == "role":
            own_roles.setdefault(pf["own"], {"labels": ["Role"], "props": {"id": pf["own"], "name": pf["name"], "level": 1, "ns": proj["ns"]}})
            nodes_b, target = ["Role"], pf["own"]
        elif pf["endpoint"] in base_systems:
            nodes_b, target = ["System"], pf["endpoint"]
        else:
            continue
        rels.append({"type": "PERFORMED_BY", "a": pf["task"], "la": ["FlowNode", "Task"], "b": target, "lb": nodes_b, "props": {}})
    return nodes + list(own_roles.values()), rels


def check(proj: dict, extra: dict | None = None) -> list[str]:
    """그래프 없이: 투영 결과가 v2 (+ 학생 스키마)와 ns 규칙을 지키는가. 레인 역할은 모두 학생 Role 로 본다(가장 엄격)."""
    nodes, rels = records(proj)
    extra = dict(extra or {"classes": [], "relationships": []}, ns=proj["ns"])
    return proj["problems"] + ov.validate_ns(nodes, rels, ov.load_schema(), extra)


WIPE = ("MATCH (n {ns: $ns, definition_id: $def, source_type: $src}) DETACH DELETE n",
        "MATCH (p:Process {id: $pid, ns: $ns}) DETACH DELETE p")


def cypher_batches(proj: dict) -> list[tuple[str, dict]]:
    """적재 문장(매개변수만 — 문장에 값을 이어 붙이지 않는다). 순서: 이전 투영 지우기 → Process → 노드 → 흐름 → 수행자."""
    ns, did, pid = proj["ns"], proj["definition_id"], proj["process"]["id"]
    out = [(WIPE[0], {"ns": ns, "def": did, "src": SOURCE_TYPE}), (WIPE[1], {"pid": pid, "ns": ns})]
    out.append(("MERGE (p:Process {id: $p.id}) SET p += $p", {"p": proj["process"]}))
    for label in ("Event", "Task", "Gateway"):
        rows = [n["props"] for n in proj["nodes"] if label in n["labels"]]
        if rows:
            out.append((f"UNWIND $rows AS r MERGE (n:FlowNode {{id: r.id}}) SET n:{label}, n += r "
                        "WITH n MATCH (p:Process {id: $pid}) MERGE (p)-[:HAS_NODE]->(n)", {"rows": rows, "pid": pid}))
    if proj["sequences"]:
        out.append(("UNWIND $rows AS r MATCH (a:FlowNode {id: r.a}), (b:FlowNode {id: r.b}) MERGE (a)-[f:SEQUENCE_FLOW]->(b) SET f += r.props",
                    {"rows": proj["sequences"]}))
    attached = [{"e": n["props"]["id"], "t": n["attached_to"]} for n in proj["nodes"] if n.get("attached_to")]
    if attached:
        out.append(("UNWIND $rows AS r MATCH (e:Event {id: r.e}), (t:Task {id: r.t}) MERGE (e)-[:ATTACHED_TO]->(t)", {"rows": attached}))
    roles = [pf for pf in proj["performers"] if pf["kind"] == "role"]
    if roles:   # 수업 기준 Role(ns 없음)이 있으면 그 노드에, 없으면 학생 Role 을 만든다
        out.append(("UNWIND $rows AS r MATCH (t:Task {id: r.task}) OPTIONAL MATCH (base:Role {id: r.endpoint}) WHERE base.ns IS NULL "
                    "FOREACH (_ IN CASE WHEN base IS NULL THEN [] ELSE [1] END | MERGE (t)-[:PERFORMED_BY]->(base)) "
                    "WITH t, r, base WHERE base IS NULL "
                    "MERGE (own:Role {id: r.own}) SET own.name = r.name, own.level = coalesce(own.level, 1), own.ns = $ns "
                    "MERGE (t)-[:PERFORMED_BY]->(own)", {"rows": roles, "ns": ns}))
    systems = [pf for pf in proj["performers"] if pf["kind"] == "system"]
    if systems:
        out.append(("UNWIND $rows AS r MATCH (t:Task {id: r.task}), (s:System {id: r.endpoint}) MERGE (t)-[:PERFORMED_BY]->(s)", {"rows": systems}))
    return out


def load_definition(path: Path) -> dict:
    """판본 JSON(proc_def.definition) 또는 그것을 'definition' 칸에 든 행(포털 · 구성 내보내기)."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return raw.get("definition") if isinstance(raw.get("definition"), dict) else raw


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="학생 흐름 → 학생 이름 공간 지식 그래프(Process · Task · Role · SEQUENCE_FLOW)")
    ap.add_argument("--definition", required=True, help="흐름 정의 JSON (판본 등록 · 구성 내보내기의 definition)")
    ap.add_argument("--ns", required=True, help="학생 이름 공간 (students/<ID>)")
    ap.add_argument("--extra", help="--check 때 함께 쓸 학생 스키마 파일")
    ap.add_argument("--check", action="store_true", help="그래프에 쓰지 않고 v2 · ns 규칙만 검사")
    ap.add_argument("--uri", default=os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"))
    ap.add_argument("--user", default="neo4j")
    ap.add_argument("--password", default=os.getenv("NEO4J_PASSWORD", "hydpass123"))
    a = ap.parse_args(argv)
    proj = project(load_definition(Path(a.definition)), a.ns)
    print(f"{proj['process']['id']}: 노드 {len(proj['nodes'])} · 흐름 {len(proj['sequences'])} · 수행자 {len(proj['performers'])}")
    errs = check(proj, ov.load_extra(a.extra) if a.extra else None)
    for e in errs:
        print(" -", e)
    if errs:
        print(f"FAIL ({len(errs)} problems) — 그래프에 쓰지 않았다")
        return 1
    if a.check:
        print("PASS (검사만)")
        return 0
    from neo4j import GraphDatabase
    with GraphDatabase.driver(a.uri, auth=(a.user, a.password)) as d, d.session() as ses:
        for stmt, params in cypher_batches(proj):
            ses.run(stmt, params).consume()
        n = ses.run("MATCH (n {ns: $ns, definition_id: $def}) RETURN count(n) AS c", {"ns": a.ns, "def": proj["definition_id"]}).single()["c"]
    print(f"PASS — {n} 노드 적재 (python scripts/ontology_v2.py validate --extra students/{a.ns}/schema.json 로 다시 검사)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
