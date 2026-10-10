"""T2 학생 지식 적재 · 되돌리기 · 꼭 답할 질문 검사 틀 (전체 과정 랩업 — docs/handoff/verification/2026-10-09/capstone-lab.md 6.1, 단계 3).

students/<내ID>/ 로 복사해 그 폴더의 schema.json(T1) · graph.json · questions.cypher 를 읽는다(다른 폴더는 --dir, 예: --dir students/_template/example_meeting).
확정 스키마 v2 와 수업 기준 노드는 바꾸지 않는다.

  python students/<내ID>/load_graph.py check                 # 그래프 없이 파일만 검사(쓰지 않음)
  python students/<내ID>/load_graph.py load  [--uri …]       # MERGE 적재 — 검사를 통과해야만 한 번에 반영된다
  python students/<내ID>/load_graph.py ask   [--uri …]       # questions.cypher 의 꼭 답할 질문을 읽기 전용으로 돌린다(0행 = 실패)
  python students/<내ID>/load_graph.py wipe  [--uri …]       # 되돌리기 — 내 이름 공간(ns) 노드만 지운다

graph.json: {"ns": "<내ID>", "nodes": [{"labels": ["Meeting"], "props": {"id": "<내ID>:…", "ns": "<내ID>", …}}],
             "rels": [{"type": "HAS_AGENDA", "a": "<id>", "b": "<id>", "props": {}}]}
규칙(어기면 좌표와 함께 거절하고 아무것도 쓰지 않는다):
  · 모든 노드는 ns = <내ID>, id 는 '<내ID>:' 로 시작한다. 같은 id 의 남의 노드(수업 기준 · 다른 학생)가 그래프에 있으면 덮어쓰지 않는다.
  · 관계의 한쪽 끝은 내 파일의 노드다. 다른 끝이 파일에 없으면 그래프의 수업 기준 노드(ns 없음)여야 한다(다리 관계).
  · 적재한 뒤, 커밋하기 전에 그래프에서 내 이름 공간을 다시 읽어 v2 + 내 스키마로 검사한다(scripts/ontology_v2.py validate --extra 와 같은 검사).
    위반이 하나라도 있으면 되돌리고 실패한다. 수업 기준 노드 수가 달라져도 되돌린다.
파일에서 뺀 노드 · 관계는 load 가 지우지 않는다(그래프에만 있는 내 것을 목록으로 알린다). 지우려면 wipe 뒤 load.
wipe 는 흐름 투영(scripts/project_student_flow.py, G8)이 만든 내 흐름 노드도 함께 지운다 — 지우기 전에 종류별 개수를 보여 준다.
questions.cypher 형식은 it/neo4j/v2/queries.cypher 와 같다(// @query 이름 · // @ask 질문 · // @params {…}). 질문은 $ns 로 내 이름 공간을 봐야 한다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FLOW_SOURCE = "student_flow"            # scripts/project_student_flow.py 가 흐름 노드에 다는 표시
LABEL_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")
REL_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
ROW_PREVIEW = 3                         # ask 가 질문마다 보여 주는 행 수
ROW_TEXT_MAX = 300


def repo_root(start: Path = HERE) -> Path:
    for folder in (start, *start.parents):
        if (folder / "scripts" / "ontology_v2.py").is_file():
            return folder
    raise SystemExit(f"{start}: 위쪽 폴더에서 scripts/ontology_v2.py 를 찾지 못했다 — 이 스크립트는 레포 안(students/<내ID>/)에서 돌린다")


sys.path.insert(0, str(repo_root() / "scripts"))
import ontology_v2 as ov  # noqa: E402


class GraphFileError(ValueError):
    """graph.json · questions.cypher 가 약속한 모양이 아님(좌표가 든 문제 목록)."""

    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def read_graph(path: Path, ns: str) -> dict:
    """graph.json → {"nodes": [...], "rels": [...]}. 모양 · ns · id 접두어 · 중복 · 관계 끝점을 좌표와 함께 본다."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise GraphFileError([f"{path}: 지식 파일을 읽을 수 없다 — {e}"]) from e
    if not isinstance(raw, dict) or not isinstance(raw.get("nodes"), list) or not isinstance(raw.get("rels"), list):
        raise GraphFileError([f"{path}: 맨 바깥은 {{\"ns\": …, \"nodes\": […], \"rels\": […]}} 객체여야 한다"])
    problems, prefix, ids = [], f"{ns}:", set()
    if raw.get("ns") != ns:
        problems.append(f"{path}: ns {raw.get('ns')!r} 가 스키마 파일의 ns {ns!r} 와 다르다")
    if not raw["nodes"]:
        problems.append(f"{path}: nodes 가 비어 있다 — 적재할 지식이 없다")
    for i, n in enumerate(raw["nodes"]):
        labels, props = (n.get("labels"), n.get("props")) if isinstance(n, dict) else (None, None)
        if not (isinstance(labels, list) and labels and all(isinstance(l, str) and LABEL_RE.match(l) for l in labels)):
            problems.append(f"nodes[{i}]: labels 는 클래스 이름 목록이어야 한다 (예: [\"Meeting\"]) — 지금 {labels!r}")
            continue
        nid = props.get("id") if isinstance(props, dict) else None
        if not isinstance(nid, str) or not nid:
            problems.append(f"nodes[{i}] {labels}: props.id 가 없다")
            continue
        if not nid.startswith(prefix) or nid == prefix:
            problems.append(f"nodes[{i}] {nid}: id 는 '{prefix}' 로 시작해야 한다")
        if props.get(ov.NS_PROP) != ns:
            problems.append(f"nodes[{i}] {nid}: ns = {ns!r} 가 있어야 한다 (지금 {props.get(ov.NS_PROP)!r})")
        if nid in ids:
            problems.append(f"nodes[{i}] {nid}: 같은 id 가 두 번 나온다")
        ids.add(nid)
    seen = set()
    for i, r in enumerate(raw["rels"]):
        ok = isinstance(r, dict) and isinstance(r.get("type"), str) and REL_RE.match(r["type"]) \
            and all(isinstance(r.get(k), str) and r[k] for k in ("a", "b")) and isinstance(r.get("props", {}), dict)
        if not ok:
            problems.append(f"rels[{i}]: {{\"type\": \"HAS_AGENDA\", \"a\": \"<id>\", \"b\": \"<id>\", \"props\": {{}}}} 모양이어야 한다 — 지금 {r!r}")
            continue
        if r["a"] not in ids and r["b"] not in ids:
            problems.append(f"rels[{i}] {r['type']} ({r['a']} → {r['b']}): 양 끝이 모두 내 파일 밖이다 — 한쪽 끝은 내 노드여야 한다")
        key = (r["type"], r["a"], r["b"])
        if key in seen:
            problems.append(f"rels[{i}] {r['type']} ({r['a']} → {r['b']}): 같은 관계가 두 번 나온다")
        seen.add(key)
    if problems:
        raise GraphFileError(problems)
    return {"nodes": [{"labels": list(n["labels"]), "props": dict(n["props"])} for n in raw["nodes"]],
            "rels": [{"type": r["type"], "a": r["a"], "b": r["b"], "props": dict(r.get("props") or {})} for r in raw["rels"]]}


def outside_ids(graph: dict) -> list[str]:
    """관계 끝점 가운데 내 파일에 없는 id — 그래프의 수업 기준 노드여야 하는 다리 끝."""
    mine = {n["props"]["id"] for n in graph["nodes"]}
    return sorted({end for r in graph["rels"] for end in (r["a"], r["b"]) if end not in mine})


def rows_for_check(graph: dict, outside: dict[str, list[str]]) -> tuple[list[dict], list[dict]]:
    """검사기(ontology_v2.validate_ns)가 읽는 행. outside = 다리 끝 id → 그래프에서 읽은 레이블. 끝 레이블을 모르는 관계는 넣지 않는다."""
    labels = {n["props"]["id"]: n["labels"] for n in graph["nodes"]} | outside
    return graph["nodes"], [dict(r, la=labels[r["a"]], lb=labels[r["b"]]) for r in graph["rels"] if r["a"] in labels and r["b"] in labels]


def bridge_problems(graph: dict, found: list[dict]) -> list[str]:
    """다리 끝이 그래프에 있고 수업 기준 노드(ns 없음)인가. found = [{id, labels, ns}] (그래프에서 읽음)."""
    by_id = {f["id"]: f for f in found}
    problems = []
    for end in outside_ids(graph):
        if end not in by_id:
            problems.append(f"끝점 {end}: 내 파일에도 그래프에도 없다 — id 가 맞는가, 수업 기준 그래프에 붙었는가")
        elif by_id[end]["ns"] is not None:
            problems.append(f"끝점 {end}: 다른 이름 공간({by_id[end]['ns']})의 노드다 — 다리 관계는 수업 기준 노드에만 잇는다")
    return problems


def clash_problems(found: list[dict], ns: str) -> list[str]:
    """내 파일의 id 를 이미 남(수업 기준 · 다른 이름 공간)이 쓰고 있으면 덮어쓰지 않는다. found = [{id, ns}]."""
    return [f"node {f['id']}: 그래프에 이미 있는 {'수업 기준' if f['ns'] is None else f['ns'] + ' 이름 공간'} 노드다 — 덮어쓰지 않는다"
            for f in found if f["ns"] != ns]


def write_batches(graph: dict) -> list[tuple[str, dict]]:
    """적재 문장(값은 매개변수로만). 레이블 · 관계 이름은 문장에 들어가므로 read_graph 가 낱말 모양을 확인한 것만 쓴다."""
    out, by_labels, by_type = [], {}, {}
    for n in graph["nodes"]:
        by_labels.setdefault(tuple(n["labels"]), []).append({"id": n["props"]["id"], "props": n["props"]})
    for labels, rows in by_labels.items():
        rest = "".join(f":`{l}`" for l in labels[1:])
        out.append((f"UNWIND $rows AS r MERGE (n:`{labels[0]}` {{id: r.id}}) SET n = r.props" + (f" SET n{rest}" if rest else ""), {"rows": rows}))
    for r in graph["rels"]:
        by_type.setdefault(r["type"], []).append({"a": r["a"], "b": r["b"], "props": r["props"]})
    for rel_type, rows in by_type.items():
        out.append((f"UNWIND $rows AS r MATCH (a {{id: r.a}}), (b {{id: r.b}}) MERGE (a)-[x:`{rel_type}`]->(b) SET x = r.props", {"rows": rows}))
    return out


def stale(graph: dict, nodes: list[dict], rels: list[dict]) -> list[str]:
    """그래프의 내 이름 공간에는 있는데 파일에는 없는 것(예전 적재분, 흐름 투영이 만든 Process · Role). 흐름 노드(G8)와 거기 닿는 관계는 세지 않는다."""
    file_ids = {n["props"]["id"] for n in graph["nodes"]}
    file_rels = {(r["type"], r["a"], r["b"]) for r in graph["rels"]}
    flow = {n["props"]["id"] for n in nodes if n["props"].get("source_type") == FLOW_SOURCE}
    out = [f"node {n['props']['id']}" for n in nodes if n["props"]["id"] not in file_ids | flow]
    out += [f"rel {r['type']} ({r['a']} → {r['b']})" for r in rels
            if (r["type"], r["a"], r["b"]) not in file_rels and r["a"] not in flow and r["b"] not in flow]
    return sorted(out)


BASE_COUNT = "MATCH (n) WHERE n.ns IS NULL RETURN count(n) AS c"
FIND = "MATCH (n) WHERE n.id IN $ids RETURN n.id AS id, labels(n) AS labels, n.ns AS ns"
MINE = "MATCH (n {ns: $ns}) RETURN CASE WHEN n.source_type = $flow THEN 'flow' ELSE 'knowledge' END AS kind, count(n) AS c"
WIPE = "MATCH (n {ns: $ns}) DETACH DELETE n"
LEFTOVER = "MATCH (n) WHERE n.id STARTS WITH $prefix RETURN n.id AS id, n.ns AS ns ORDER BY id"


class Refused(Exception):
    """검사에 걸려 쓰지 않았거나 되돌렸다."""

    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def load_into(tx, graph: dict, base: dict, extra: dict) -> dict:
    """한 트랜잭션 안에서 적재 → 다시 읽어 검사. 문제가 있으면 Refused(부른 쪽이 되돌린다)."""
    ns = extra[ov.NS_PROP]
    file_ids = [n["props"]["id"] for n in graph["nodes"]]
    found = tx.run(FIND, {"ids": file_ids + outside_ids(graph)}).data()
    problems = clash_problems([f for f in found if f["id"] in set(file_ids)], ns) + bridge_problems(graph, found)
    if not problems:
        outside = {f["id"]: f["labels"] for f in found if f["id"] not in set(file_ids)}
        problems = ov.validate_ns(*rows_for_check(graph, outside), base, extra)
    if problems:
        raise Refused(problems)
    base_before = tx.run(BASE_COUNT).single()["c"]
    for stmt, params in write_batches(graph):
        tx.run(stmt, params).consume()
    nodes, rels = ov.read_rows(tx)
    problems = ov.validate_ns(nodes, rels, base, extra)
    mine, my_rels = ov.scope_to_ns(nodes, rels, ns, [c["name"] for c in extra.get("classes") or []])
    written = {(r["type"], r["a"], r["b"]) for r in my_rels}
    problems += [f"rel {r['type']} ({r['a']} → {r['b']}): 적재 뒤 그래프에 없다" for r in graph["rels"] if (r["type"], r["a"], r["b"]) not in written]
    ids = [n["props"]["id"] for n in mine]
    problems += [f"node {i}: 같은 id 의 노드가 그래프에 {ids.count(i)}개다 — 예전에 다른 클래스로 적재했는가(wipe 뒤 load)" for i in sorted(set(ids)) if ids.count(i) > 1]
    base_after = sum(1 for n in nodes if n["props"].get(ov.NS_PROP) is None)
    if base_after != base_before:
        problems.append(f"수업 기준 노드 수가 {base_before} → {base_after} 로 달라졌다")
    if problems:
        raise Refused(problems)
    return {"nodes": len(graph["nodes"]), "rels": len(graph["rels"]), "in_graph": len(mine), "base": base_after, "stale": stale(graph, mine, my_rels)}


def wipe_from(tx, ns: str) -> dict:
    """내 이름 공간 노드만 지운다. 지울 것이 없거나, 수업 기준 노드 수가 달라지거나, 내 접두어 id 가 남으면 Refused."""
    kinds = {r["kind"]: r["c"] for r in tx.run(MINE, {"ns": ns, "flow": FLOW_SOURCE})}
    if not kinds:
        raise Refused([f"ns {ns}: 이 이름 공간의 노드가 그래프에 0개다 — 되돌릴 것이 없다(접속 --uri 가 적재한 그래프인가)"])
    base_before = tx.run(BASE_COUNT).single()["c"]
    tx.run(WIPE, {"ns": ns}).consume()
    base_after = tx.run(BASE_COUNT).single()["c"]
    left = tx.run(LEFTOVER, {"prefix": f"{ns}:"}).data()
    problems = [f"node {l['id']}: id 는 '{ns}:' 인데 ns 가 {l['ns']!r} 라 지우지 않았다 — 누가 만든 노드인지 확인한다" for l in left]
    if base_after != base_before:
        problems.append(f"수업 기준 노드 수가 {base_before} → {base_after} 로 달라졌다")
    if problems:
        raise Refused(problems)
    return {"knowledge": kinds.get("knowledge", 0), "flow": kinds.get("flow", 0), "base": base_after}


def read_questions(path: Path) -> list[dict]:
    try:
        questions = ov.parse_queries(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise GraphFileError([f"{path}: 질문 파일을 읽을 수 없다 — {e}"]) from e
    problems = [] if questions else [f"{path}: 질문이 0개다 — // @query 이름 · // @ask 질문 · Cypher 를 적는다"]
    for q in questions:
        if not q["ask"]:
            problems.append(f"{path} @query {q['name']}: // @ask 질문 문장이 없다")
        if not q["cypher"]:
            problems.append(f"{path} @query {q['name']}: Cypher 가 없다")
        elif "$ns" not in q["cypher"]:
            problems.append(f"{path} @query {q['name']}: $ns 를 쓰지 않는다 — 내 이름 공간의 지식으로 답해야 한다")
        if "ns" in q["params"]:
            problems.append(f"{path} @query {q['name']}: @params 에 ns 를 적지 않는다(스키마 파일의 ns 가 들어간다)")
    if problems:
        raise GraphFileError(problems)
    return questions


def ask(run_read, questions: list[dict], ns: str) -> list[dict]:
    """run_read(cypher, params) → 행 목록(읽기 전용으로 돌린다). 0행인 질문은 answered False."""
    out = []
    for q in questions:
        rows = run_read(q["cypher"], dict(q["params"], ns=ns))
        out.append({"name": q["name"], "ask": q["ask"], "rows": rows, "answered": bool(rows)})
    return out


def _fail(problems: list[str], what: str) -> int:
    for p in problems:
        print(" -", p)
    print(f"FAIL ({len(problems)} problems) — {what}")
    return 1


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="학생 지식 적재 · 되돌리기 · 꼭 답할 질문 검사 (T2)")
    ap.add_argument("cmd", choices=["check", "load", "ask", "wipe"])
    ap.add_argument("--dir", default=str(HERE), help="schema.json · graph.json · questions.cypher 가 있는 폴더 (기본: 이 스크립트 폴더)")
    ap.add_argument("--uri", default=os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"), help="포털 지식 지도가 읽는 그래프")
    ap.add_argument("--user", default="neo4j")
    ap.add_argument("--password", default=os.getenv("NEO4J_PASSWORD", "hydpass123"))
    a = ap.parse_args(argv)
    folder = Path(a.dir)
    schema_path, graph_path, questions_path = folder / "schema.json", folder / "graph.json", folder / "questions.cypher"
    base = ov.load_schema()
    try:
        extra = ov.load_extra(schema_path)
    except ValueError as e:
        return _fail([str(e)], "그래프에 닿지 않았다")
    problems = ov.check_extra(base, extra)
    if problems:
        return _fail(problems, f"학생 스키마 {schema_path} 부터 고친다")
    ns = extra[ov.NS_PROP]
    try:
        graph = read_graph(graph_path, ns) if a.cmd in ("check", "load") else None
        questions = read_questions(questions_path) if a.cmd in ("check", "ask") else None
    except GraphFileError as e:
        return _fail(e.problems, "그래프에 닿지 않았다")

    if a.cmd == "check":
        outside = outside_ids(graph)
        problems = ov.validate_ns(*rows_for_check(graph, {}), base, extra)
        if problems:
            return _fail(problems, "그래프에 닿지 않았다")
        for end in outside:
            print(f" ! 다리 끝 {end}: 내 파일에 없다 — 수업 기준 노드인지는 load 가 그래프에서 확인한다(이 끝에 닿는 관계는 여기서 검사하지 않았다)")
        print(f"PASS (파일만 검사) — ns {ns!r}: 노드 {len(graph['nodes'])} · 관계 {len(graph['rels'])} · 질문 {len(questions)}"
              + (f" · 그래프에서 확인할 다리 끝 {len(outside)}" if outside else ""))
        return 0

    import neo4j
    with neo4j.GraphDatabase.driver(a.uri, auth=(a.user, a.password)) as driver:
        if a.cmd == "ask":
            with driver.session(default_access_mode=neo4j.READ_ACCESS) as ses:
                results = ask(lambda cypher, params: ses.execute_read(lambda tx: tx.run(cypher, params).data()), questions, ns)
            for r in results:
                print(f"{'답함' if r['answered'] else '못 답함'}  {r['name']} — {r['ask']} ({len(r['rows'])}행)")
                for row in r["rows"][:ROW_PREVIEW]:
                    print("     ", json.dumps(row, ensure_ascii=False, default=str)[:ROW_TEXT_MAX])
            missed = [f"{r['name']} — {r['ask']}: 0행" for r in results if not r["answered"]]
            if missed:
                return _fail(missed, f"ns {ns!r} @ {a.uri} 의 지식으로 답하지 못한 질문")
            print(f"PASS — 질문 {len(results)}개 모두 ns {ns!r} @ {a.uri} 의 지식으로 답했다")
            return 0
        with driver.session() as ses, ses.begin_transaction() as tx:
            try:
                done = load_into(tx, graph, base, extra) if a.cmd == "load" else wipe_from(tx, ns)
            except Refused as e:
                tx.rollback()
                return _fail(e.problems, f"그래프 {a.uri} 는 바뀌지 않았다(되돌림)")
            tx.commit()
    if a.cmd == "wipe":
        print(f"PASS — ns {ns!r} @ {a.uri}: 흐름 노드 {done['flow']} · 그 밖의 내 노드 {done['knowledge']} 삭제, 수업 기준 노드 {done['base']} 그대로")
        return 0
    for s in done["stale"]:
        print(f" ! 그래프에만 있는 내 것: {s}")
    print(f"PASS — ns {ns!r} @ {a.uri}: 노드 {done['nodes']} · 관계 {done['rels']} 적재(그래프의 내 노드 {done['in_graph']}), 수업 기준 노드 {done['base']} 그대로"
          + (f" · 그래프에만 있는 내 것 {len(done['stale'])}개(예전 적재분이면 wipe 뒤 load)" if done["stale"] else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
