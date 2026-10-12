"""고장 유형에서 조치를 거쳐 그 조치의 조건까지 따라가서 보여 준다.

실행: python 따라가기.py [고장 유형의 id]
      (예: python 따라가기.py fm:cooler-cooling-performance-loss. 인자가 없으면 모든 고장 유형)
하는 일
  1. 결과/schema.json 과 결과/graph.json 을 읽는다
  2. 고장 유형에서 MITIGATED_BY, REMEDIED_BY 를 따라 조치를 찾는다
  3. 조치마다 HAS_CONDITION 으로 이어진 조건을 구분별로 모은다
  4. 고장 유형마다 뒤에, 조건 노드 하나에 이어진 조치의 절차 번호를 모두 모아 적는다
  5. 화면에 내고, 같은 내용을 결과/조치_조건.md 에 쓴다
조치와 조건의 이름, 식별자, 문장은 모두 graph.json 에서 읽는다. 이 프로그램은 graph.json 을 고치지 않는다.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.path.join(HERE, "결과", "조치_조건.md")
FAILURE_CLASS, CONDITION_CLASS = "FailureMode", "Condition"
CONDITION_REL = "HAS_CONDITION"
# 보이는 순서대로: 완화하는 조치를 먼저, 원인을 없애는 조치를 뒤에 둔다.
SKILL_GROUPS = (("MITIGATED_BY", "완화하는 조치"), ("REMEDIED_BY", "원인을 없애는 조치"))


def load(name):
    with open(os.path.join(HERE, "결과", name), encoding="utf-8") as f:
        return json.load(f)


def kind_order(schema):
    """조건의 구분을 스키마의 허용값에 적힌 순서대로 돌려준다."""
    for cls in schema["classes"]:
        if cls["name"] == CONDITION_CLASS:
            for prop in cls["properties"]:
                if prop["name"] == "kind":
                    return list(prop.get("values", []))
    return []


def sop_key(skill):
    """절차 번호 순서. 번호 안의 수는 수로 견준다."""
    parts = re.split(r"(\d+)", skill.get("sop_id", ""))
    return [(0, int(p), "") if p.isdigit() else (1, 0, p) for p in parts]


def follow(node_id, rel_type, graph, nodes):
    """node_id 에서 rel_type 관계를 따라가 닿는 노드의 props 를 graph.json 에 적힌 순서대로 돌려준다."""
    found = []
    for rel in graph["rels"]:
        if rel["type"] == rel_type and rel["a"] == node_id and rel["b"] in nodes:
            found.append(nodes[rel["b"]]["props"])
    return found


def by_kind(conditions, kinds):
    """조건을 스키마에 적힌 구분의 순서로 늘어놓는다. 순서에 없는 구분은 뒤에 둔다."""
    ordered = kinds + sorted({c.get("kind") for c in conditions} - set(kinds), key=str)
    return [c for kind in ordered for c in conditions if c.get("kind") == kind]


def describe_conditions(failure, graph, nodes, kinds):
    """조건 노드 하나를 한 줄로 삼아, 그 조건에 이어진 조치의 절차 번호를 모두 적는다."""
    skills_of = {}
    for rel_type, _ in SKILL_GROUPS:
        for skill in follow(failure["id"], rel_type, graph, nodes):
            for condition in follow(skill["id"], CONDITION_REL, graph, nodes):
                linked = skills_of.setdefault(condition["id"], [])
                if skill not in linked:
                    linked.append(skill)
    lines = ["### 조건별로 본 조치", ""]
    # graph.json 에 적힌 순서의 조건 노드를 구분의 순서로 다시 늘어놓는다.
    conditions = by_kind([n["props"] for i, n in nodes.items() if i in skills_of], kinds)
    for condition in conditions:
        sops = ", ".join(s.get("sop_id", "(절차 번호 없음)") for s in sorted(skills_of[condition["id"]], key=sop_key))
        lines.append(f"- [{condition.get('kind')}] {condition.get('text')} ({condition.get('source')}) → {sops}")
    if not conditions:
        lines.append("- 그래프에 이어진 조건 없음")
    lines.append("")
    return lines


def describe(failure, graph, nodes, kinds):
    lines = [f"## 고장 유형: {failure['name']} ({failure['id']})", ""]
    for rel_type, title in SKILL_GROUPS:
        lines += [f"### {title} ({rel_type})", ""]
        skills = sorted(follow(failure["id"], rel_type, graph, nodes), key=sop_key)
        if not skills:
            lines += ["그래프에 이어진 조치 없음", ""]
        for skill in skills:
            lines.append(f"#### {skill.get('sop_id', '(절차 번호 없음)')} {skill['name']}")
            conditions = follow(skill["id"], CONDITION_REL, graph, nodes)
            for condition in by_kind(conditions, kinds):
                lines.append(f"- [{condition.get('kind')}] {condition.get('text')} ({condition.get('source')})")
            if not conditions:
                lines.append("- 그래프에 이어진 조건 없음")
            lines.append("")
    return lines + describe_conditions(failure, graph, nodes, kinds)


def main():
    schema, graph = load("schema.json"), load("graph.json")
    nodes = {n["props"]["id"]: n for n in graph["nodes"]}
    failures = [n["props"] for n in graph["nodes"] if FAILURE_CLASS in n.get("labels", [])]

    if len(sys.argv) > 1:
        wanted = sys.argv[1]
        chosen = [f for f in failures if f["id"] == wanted]
        if not chosen:
            print(f"graph.json 에 {wanted} 라는 고장 유형이 없다.")
            print("있는 고장 유형:")
            for failure in failures:
                print(f"  {failure['id']}  {failure['name']}")
            return 1
    else:
        chosen = failures

    kinds = kind_order(schema)
    lines = ["# 고장 유형별 조치와 조건", ""]
    for failure in chosen:
        lines += describe(failure, graph, nodes, kinds)
    text = "\n".join(lines).rstrip("\n") + "\n"

    print(text, end="")
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
