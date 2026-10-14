"""실습용 그래프 DB 를 이 실습의 처음 상태로 맞춘다.

  python 그래프_준비.py

지난_시간/graph.json 의 노드와 관계를 그래프 DB 에 넣는다. 이미 들어 있으면 늘지 않는다.
이 실습에서 문서를 반영해 생긴 노드와 관계(_manual_document 속성이 붙은 것)와,
등록된 대상에 덧붙은 속성은 걷어 낸다. 그 밖의 노드와 관계는 건드리지 않는다.
"""

import json
import sys
from pathlib import Path

import graphdb

ROOT = Path(__file__).resolve().parent
GRAPH = ROOT / "지난_시간" / "graph.json"
SCHEMA = ROOT / "지난_시간" / "schema.json"
SOURCE_SCHEMA = ROOT / "출처_스키마.json"


def main():
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    known = {c["name"] for c in json.loads(SCHEMA.read_text(encoding="utf-8"))["classes"]}
    known |= {c["name"] for c in json.loads(SOURCE_SCHEMA.read_text(encoding="utf-8"))["classes"]}

    # 이 실습의 것이 아닌 지식이 들어 있는 그래프 DB 에는 넣지 않는다.
    other = [r for r in graphdb.query("MATCH (n) UNWIND labels(n) AS label RETURN label, count(*) AS n ORDER BY label")
             if r["label"] not in known]
    if other:
        names = ", ".join(f"{r['label']} {r['n']}" for r in other[:8])
        print(f"멈춤: 이 그래프 DB({graphdb.ADDRESS})에는 이 실습의 스키마에 없는 종류의 노드가 들어 있다({names} …).")
        print("실습용으로 분리된 그래프 DB 가 아닌 것으로 보인다. 아무것도 넣지 않았다. 강사에게 알린다.")
        return 1

    statements = [
        "MATCH (n) WHERE n._manual_document IS NOT NULL DETACH DELETE n",
        "MATCH ()-[r]->() WHERE r._manual_document IS NOT NULL DELETE r",
    ]
    by_label = {}
    for node in graph["nodes"]:
        by_label.setdefault(node["labels"][0], []).append(node["props"])
    by_type = {}
    for rel in graph["rels"]:
        by_type.setdefault(rel["type"], []).append({"a": rel["a"], "b": rel["b"], "props": rel.get("props", {})})
    params = {}
    for i, (label, rows) in enumerate(by_label.items()):
        params[f"n{i}"] = rows
        statements.append(f"UNWIND $n{i} AS row MERGE (n:{label} {{id: row.id}}) SET n = row")
    for i, (rel_type, rows) in enumerate(by_type.items()):
        params[f"r{i}"] = rows
        statements.append(
            f"UNWIND $r{i} AS row MATCH (a {{id: row.a}}), (b {{id: row.b}}) MERGE (a)-[r:{rel_type}]->(b) SET r = row.props"
        )
    graphdb.run_all(statements, params)

    ids = [n["props"]["id"] for n in graph["nodes"]]
    nodes = graphdb.query("MATCH (n) RETURN count(n) AS n")[0]["n"]
    rels = graphdb.query("MATCH ()-[r]->() RETURN count(r) AS n")[0]["n"]
    mine = graphdb.query("MATCH (n) WHERE n.id IN $ids RETURN count(n) AS n", {"ids": ids})[0]["n"]
    print(f"그래프 DB: {graphdb.ADDRESS}")
    print(f"지난_시간/graph.json: 노드 {len(graph['nodes'])}, 관계 {len(graph['rels'])}")
    print(f"그래프 DB 에 든 것:   노드 {nodes}, 관계 {rels}")
    if mine != len(ids):
        print(f"멈춤: graph.json 의 노드 {len(ids)}개 가운데 {mine}개만 그래프 DB 에 있다.")
        return 1
    if nodes != len(ids):
        print(f"알림: graph.json 에 없는 노드가 {nodes - len(ids)}개 더 들어 있다. 지우지 않고 그대로 두었다.")
    print("준비됨: 지난 시간의 그래프가 그래프 DB 에 들어 있다.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except graphdb.GraphError as error:
        print(f"멈춤: {error}")
        sys.exit(1)
