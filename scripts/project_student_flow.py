"""G8 (전체 과정 랩업 — docs/handoff/verification/2026-10-09/capstone-lab.md 5.2): 학생 흐름을 학생 이름 공간 지식 그래프에 투영한다.

기준 흐름(A · B · C)의 Process · Task 는 시드(it/neo4j/v2/instances.cypher 500~540행)에 있지만, 학생이 가져온 흐름은 그래프에 생기지 않는다.
이 스크립트가 흐름 정의(포털 판본 등록 JSON = proc_def.definition, 흐름 가져오기가 만든 것)를 읽어 v2 클래스 · 관계로 MERGE 한다:

  Process(<ns>:proc:<정의 id>) -HAS_NODE-> Event · Task · Gateway(<ns>:<노드 id>) -SEQUENCE_FLOW {id, condition, isDefault}-> …
  Task -PERFORMED_BY-> Role — 레인의 역할이 수업 기준 Role(ns 없음, 예 role:operator)이면 그 노드에 잇고(다리 관계),
                               없으면 학생 Role(<ns>:<역할 endpoint>, level 1)을 만든다. 시스템 수행자(sys:*)는 그래프에 있는 System 에만 잇고,
                               없으면 적재 전에 실패한다.
모든 흐름 노드에 ns · definition_id · element_id(원래 id) · source_type='student_flow'. 기준 흐름 · 시드 노드는 만들거나 바꾸지 않는다.
다시 돌리면 그 정의의 이전 흐름 노드(같은 ns · definition_id · source_type)를 지우고 다시 만든다(멱등). Process 노드는 지우지 않고
MERGE 하므로 학생이 Process 에 단 다리 관계(예: Meeting -PREPARED_BY_PROCESS-> Process)는 남는다. 흐름 노드(Task 등)에 손으로 단 관계는
다시 만들 때 함께 지워지므로 적재 전에 목록으로 알린다. 지원하지 않는 요소 · 빠진 id · 모르는 종류는 버리지 않고 문제로 보고하고 쓰지 않는다.
포털 자동화는 하지 않는다(설계: 선택, 출발본 T2).

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
              "sendTask": "send", "receiveTask": "receive", "subProcess": "subProcess", "callActivity": "callActivity"}
EVENT_POSITIONS = {"startEvent": "start", "endEvent": "end", "boundaryEvent": "boundary"}
EVENT_DEFS = ("none", "message", "timer", "escalation")
GATEWAY_TYPES = {"exclusiveGateway": "exclusive", "parallelGateway": "parallel"}
AGENT_MODES = ("DRAFT", "COMPLETE")
ROLE_PREFIX, SYSTEM_PREFIX = "role:", "sys:"
OWNED_RELS = ("HAS_NODE", "SEQUENCE_FLOW", "ATTACHED_TO", "PERFORMED_BY")      # 이 스크립트가 흐름 노드에 만드는 관계


def _condition(seq: dict) -> str | None:
    c = seq.get("condition") if "condition" in seq else seq.get("conditionExpression")
    if c in (None, "", {}):
        return None
    return c if isinstance(c, str) else json.dumps(c, ensure_ascii=False, sort_keys=True)


def _elements(defn: dict, key: str, problems: list[str]) -> list[tuple[str, dict]]:
    """정의의 한 칸(events · activities · gateways)에서 id 가 있는 요소만. 빠진 id · 객체가 아닌 요소는 좌표(칸[번호])로 보고한다."""
    out = []
    items = defn.get(key) or []
    if not isinstance(items, list):
        problems.append(f"{key}: 목록이어야 한다 (지금 {type(items).__name__})")
        return out
    for i, el in enumerate(items):
        eid = el.get("id") if isinstance(el, dict) else None
        if not isinstance(eid, str) or not eid:
            problems.append(f"{key}[{i}]: id 가 없다")
            continue
        out.append((eid, el))
    return out


def _performer(task_id: str, role_name, roles: dict, prefix: str, problems: list[str]) -> dict | None:
    role = roles.get(str(role_name))
    endpoint = str((role or {}).get("endpoint") or "").split(",")[0].strip()
    if not endpoint:
        problems.append(f"task {task_id}: 레인(역할) {role_name!r} 의 endpoint 가 정의 roles 에 없다")
        return None
    if endpoint.startswith(ROLE_PREFIX):
        kind = "role"
    elif endpoint.startswith(SYSTEM_PREFIX):
        kind = "system"
    else:
        problems.append(f"task {task_id}: 레인(역할) {role_name!r} 의 endpoint {endpoint!r} 는 '{ROLE_PREFIX}' 도 '{SYSTEM_PREFIX}' 도 아니다")
        return None
    return {"task": prefix + task_id, "endpoint": endpoint, "name": str(role.get("name")), "own": f"{prefix}{endpoint}", "kind": kind}


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
    for eid, e in _elements(defn, "events", problems):
        position = EVENT_POSITIONS.get(e.get("type"))
        definition = e.get("eventDefinition") or "none"        # BPMN: 정의가 없는 이벤트가 곧 none 이벤트(기준 정의도 이렇게 씀)
        if position is None:
            problems.append(f"event {eid}: 종류 {e.get('type')!r} 는 v2 Event 가 아니다(start · end · boundary)")
            continue
        if definition not in EVENT_DEFS:
            problems.append(f"event {eid}: eventDefinition {definition!r} 는 v2 값({' · '.join(EVENT_DEFS)})이 아니다")
            continue
        props = dict(common, id=p + eid, name=str(e.get("name") or eid), element_id=eid, position=position, eventDefinition=definition)
        if definition == "timer":
            if not e.get("timer"):
                problems.append(f"event {eid}: 타이머 이벤트에 timer(기간)가 없다")
                continue
            props["timer"] = str(e["timer"])
        if position == "boundary" and not e.get("attachedTo"):
            problems.append(f"event {eid}: 경계 이벤트인데 attachedTo 가 없다")
            continue
        nodes.append({"labels": ["FlowNode", "Event"], "props": props, "attached_to": p + e["attachedTo"] if e.get("attachedTo") else None})
    performers = []
    for aid, a in _elements(defn, "activities", problems):
        task_type = TASK_TYPES.get(a.get("type"))
        if task_type is None:
            problems.append(f"task {aid}: 종류 {a.get('type')!r} 는 v2 Task 종류({' · '.join(TASK_TYPES)})가 아니다")
            continue
        props = dict(common, id=p + aid, name=str(a.get("name") or aid), element_id=aid, taskType=task_type)
        if a.get("tool"):
            props["tool"] = str(a["tool"])
        if a.get("agentMode") in AGENT_MODES:
            props["agentMode"] = a["agentMode"]
        if a.get("orchestration"):
            props["orchestration"] = str(a["orchestration"])
        nodes.append({"labels": ["FlowNode", "Task"], "props": props})
        if a.get("role"):
            pf = _performer(aid, a["role"], roles, p, problems)
            if pf:
                performers.append(pf)
    for gid, g in _elements(defn, "gateways", problems):
        kind = GATEWAY_TYPES.get(g.get("type"))
        if kind is None:
            problems.append(f"gateway {gid}: 종류 {g.get('type')!r} 는 v2 Gateway 가 아니다(exclusive · parallel)")
            continue
        nodes.append({"labels": ["FlowNode", "Gateway"], "props": dict(common, id=p + gid, name=str(g.get("name") or gid), element_id=gid,
                                                                         gatewayType=kind)})
    if not nodes:
        problems.append(f"정의 {did}: 흐름 노드(events · activities · gateways)가 하나도 없다")
    ids = {n["props"]["id"] for n in nodes}
    sequences = []
    for s in defn.get("sequences") or []:
        a, b = p + str(s.get("source")), p + str(s.get("target"))
        if a not in ids or b not in ids:
            problems.append(f"sequence {s.get('id')}: 끝 {s.get('source')} → {s.get('target')} 가 노드에 없다")
            continue
        is_default = (s.get("properties") or {}).get("default") is True        # 흐름 가져오기의 '그 밖의 경우' 선
        props = {k: v for k, v in (("id", p + str(s["id"]) if s.get("id") else None), ("condition", _condition(s)),
                                   ("isDefault", True if is_default else None)) if v is not None}
        sequences.append({"a": a, "b": b, "props": props})
    return {"process": process, "nodes": nodes, "sequences": sequences, "performers": performers, "problems": problems, "definition_id": did, "ns": ns}


def records(proj: dict, base_roles: set[str] = frozenset(), base_systems: set[str] = frozenset()) -> tuple[list[dict], list[dict]]:
    """검사용 노드 · 관계 행(ontology_v2.validate 형식). base_*: 그래프에 이미 있는 수업 기준 Role · System id(다리 관계 끝).
    그래프 없이 부르면(--check) 시스템 수행자는 끝을 모르므로 빠진다 — 적재 때 missing_systems 로 따로 확인한다."""
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


def missing_systems(proj: dict, base_systems: set[str]) -> list[str]:
    return [f"task {pf['task']}: 시스템 수행자 {pf['endpoint']} 가 그래프에 System 노드로 없다 — 시드를 적재했는가"
            for pf in proj["performers"] if pf["kind"] == "system" and pf["endpoint"] not in base_systems]


def check(proj: dict, extra: dict | None = None, base_roles: set[str] = frozenset(), base_systems: set[str] = frozenset()) -> list[str]:
    """투영 결과가 v2 (+ 학생 스키마)와 ns 규칙을 지키는가. 그래프 없이 부르면 레인 역할은 모두 학생 Role 로 본다(가장 엄격)."""
    problems = list(proj["problems"])
    if extra is not None and extra.get(ov.NS_PROP) not in (None, proj["ns"]):
        problems.append(f"--extra 의 ns {extra.get(ov.NS_PROP)!r} 가 --ns {proj['ns']!r} 와 다르다")
    nodes, rels = records(proj, base_roles, base_systems)
    extra = dict(extra or {"classes": [], "relationships": []}, ns=proj["ns"])
    return problems + ov.validate_ns(nodes, rels, ov.load_schema(), extra)


WIPE = "MATCH (n:FlowNode {ns: $ns, definition_id: $def, source_type: $src}) DETACH DELETE n RETURN count(n) AS removed"
FOREIGN = ("MATCH (n:FlowNode {ns: $ns, definition_id: $def, source_type: $src})-[x]-() WHERE NOT type(x) IN $owned "
           "RETURN type(x) AS type, startNode(x).id AS a, endNode(x).id AS b ORDER BY type, a, b")
BASES = ("OPTIONAL MATCH (r:Role) WHERE r.id IN $roles AND r.ns IS NULL WITH collect(r.id) AS roles "
         "OPTIONAL MATCH (s:System) WHERE s.id IN $systems RETURN roles, collect(s.id) AS systems")


def cypher_batches(proj: dict) -> list[tuple[str, dict]]:
    """적재 문장(매개변수만 — 문장에 값을 이어 붙이지 않는다). 순서: 이전 흐름 노드 지우기 → Process(지우지 않고 MERGE) → 노드 → 흐름 → 수행자."""
    ns, did, pid = proj["ns"], proj["definition_id"], proj["process"]["id"]
    out = [(WIPE, {"ns": ns, "def": did, "src": SOURCE_TYPE}),
           ("MERGE (p:Process {id: $p.id}) SET p += $p", {"p": proj["process"]})]
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
    """판본 JSON(proc_def.definition) 또는 그것을 'definition' 칸에 든 행(포털 · 구성 내보내기). 못 읽으면 파일 좌표가 있는 ValueError."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ValueError(f"{path}: 흐름 정의를 읽을 수 없다 — {e}") from e
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: 흐름 정의는 JSON 객체여야 한다 (지금 {type(raw).__name__})")
    return raw["definition"] if isinstance(raw.get("definition"), dict) else raw


def _fail(errs: list[str], wrote: bool = False) -> int:
    for e in errs:
        print(" -", e)
    print(f"FAIL ({len(errs)} problems) — " + ("적재는 했지만 결과가 투영과 다르다" if wrote else "그래프에 쓰지 않았다"))
    return 1


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="학생 흐름 → 학생 이름 공간 지식 그래프(Process · Task · Role · SEQUENCE_FLOW)")
    ap.add_argument("--definition", required=True, help="흐름 정의 JSON (판본 등록 · 구성 내보내기의 definition)")
    ap.add_argument("--ns", required=True, help="학생 이름 공간 (students/<ID>)")
    ap.add_argument("--extra", help="함께 검사할 학생 스키마 파일 (students/<ID>/schema.json)")
    ap.add_argument("--check", action="store_true", help="그래프에 쓰지 않고 v2 · ns 규칙만 검사")
    ap.add_argument("--uri", default=os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"))
    ap.add_argument("--user", default="neo4j")
    ap.add_argument("--password", default=os.getenv("NEO4J_PASSWORD", "hydpass123"))
    a = ap.parse_args(argv)
    try:
        proj = project(load_definition(Path(a.definition)), a.ns)
        extra = ov.load_extra(a.extra) if a.extra else None
    except ValueError as e:
        return _fail([str(e)])
    print(f"{proj['process']['id']}: 노드 {len(proj['nodes'])} · 흐름 {len(proj['sequences'])} · 수행자 {len(proj['performers'])}")
    if a.check:
        errs = check(proj, extra)
        if errs:
            return _fail(errs)
        print("PASS (검사만 — 시스템 수행자가 그래프에 있는지는 적재 때 확인한다)")
        return 0
    from neo4j import GraphDatabase
    with GraphDatabase.driver(a.uri, auth=(a.user, a.password)) as d, d.session() as ses:
        row = ses.run(BASES, {"roles": [pf["endpoint"] for pf in proj["performers"] if pf["kind"] == "role"],
                              "systems": [pf["endpoint"] for pf in proj["performers"] if pf["kind"] == "system"]}).single()
        base_roles, base_systems = set(row["roles"]), set(row["systems"])
        errs = check(proj, extra, base_roles, base_systems) + missing_systems(proj, base_systems)
        if errs:
            return _fail(errs)
        key = {"ns": a.ns, "def": proj["definition_id"], "src": SOURCE_TYPE}
        foreign = ses.run(FOREIGN, dict(key, owned=list(OWNED_RELS))).data()
        for f in foreign:
            print(f" ! 다시 만들며 지우는 손으로 단 관계: ({f['a']})-[:{f['type']}]->({f['b']})")
        for stmt, params in cypher_batches(proj):
            ses.run(stmt, params).consume()
        n = ses.run("MATCH (n:FlowNode {ns: $ns, definition_id: $def, source_type: $src}) RETURN count(n) AS c", key).single()["c"]
        performed = ses.run("MATCH (n:FlowNode {ns: $ns, definition_id: $def, source_type: $src})-[:PERFORMED_BY]->() RETURN count(*) AS c",
                            key).single()["c"]
    if n != len(proj["nodes"]) or performed != len(proj["performers"]):
        return _fail([f"적재 뒤 흐름 노드 {n}/{len(proj['nodes'])} · 수행자 관계 {performed}/{len(proj['performers'])} — 그래프 상태를 확인하라"], wrote=True)
    print(f"PASS — 흐름 노드 {n} · 수행자 관계 {performed} 적재 @ {a.uri} "
          f"(다시 검사: python scripts/ontology_v2.py validate --uri {a.uri} --extra students/{a.ns}/schema.json)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
