"""결과/graph.json 을 결과/schema.json 과 문서/ 의 원문에 대어 본다.

실행: python 검사.py   (인자 없음)
보는 것
  1. 그래프가 스키마의 정의에 맞는가
     (정의되지 않은 클래스 · 속성 · 관계, 자료형과 허용값, 필수 속성, id 의 중복, 관계의 양 끝)
  2. sop_id 가 문서의 절차 번호(### SOP-…)에 있는가
  3. text 와 source 를 가진 노드는 그 문장이 그 절(## 번호)에 글자 그대로 있는가
     preconditions · safety_conditions · prohibitions 의 문장은 문서에 글자 그대로 있는가
마지막 줄에 어긋난 수를 낸다. 0건이면 통과다. 이 프로그램은 파일을 고치지 않는다.
"""
import json
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
SENTENCE_LISTS = ("preconditions", "safety_conditions", "prohibitions")


def load(name):
    with open(os.path.join(HERE, "결과", name), encoding="utf-8") as f:
        return json.load(f)


def squeeze(text):
    """줄바꿈과 겹친 빈칸을 빈칸 하나로 줄인다. 글자는 바꾸지 않는다."""
    return re.sub(r"\s+", " ", text).strip()


def read_documents():
    """문서/ 의 md 파일을 읽어 절 번호별 글과 절차 번호의 모음을 돌려준다."""
    sections, sops, whole = {}, set(), []
    folder = os.path.join(HERE, "문서")
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".md"):
            continue
        with open(os.path.join(folder, name), encoding="utf-8") as f:
            lines = f.read().splitlines()
        current = None
        for line in lines:
            if line.startswith("## "):
                current = line[3:].split()[0]
                sections[current] = []
            elif line.startswith("### "):
                found = re.search(r"SOP-[A-Z0-9-]+", line)
                if found:
                    sops.add(found.group(0))
            if current is not None:
                sections[current].append(line)
            whole.append(line)
    return {k: squeeze("\n".join(v)) for k, v in sections.items()}, sops, squeeze("\n".join(whole))


def type_ok(value, prop):
    kind = prop["type"]
    if kind == "string":
        return isinstance(value, str)
    if kind == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if kind == "boolean":
        return isinstance(value, bool)
    if kind == "string[]":
        return isinstance(value, list) and all(isinstance(x, str) for x in value)
    if kind == "enum":
        return value in prop.get("values", [])
    return False


def check_props(where, props, definitions, problems):
    known = {p["name"]: p for p in definitions}
    for key, value in props.items():
        if key not in known:
            problems.append(f"{where}: 스키마에 없는 속성 {key}")
        elif not type_ok(value, known[key]):
            allowed = known[key].get("values")
            hint = f" (허용값 {allowed})" if allowed else ""
            problems.append(f"{where}: {key} 의 값 {value!r} 이 자료형 {known[key]['type']} 에 맞지 않는다{hint}")
    for name, prop in known.items():
        if prop.get("required") and name not in props:
            problems.append(f"{where}: 필수 속성 {name} 이 없다")


def main():
    schema, graph = load("schema.json"), load("graph.json")
    sections, sops, whole = read_documents()
    classes = {c["name"]: c for c in schema["classes"]}
    relations = {r["type"]: r for r in schema["relationships"]}
    problems = []

    label_of = {}
    for node in graph["nodes"]:
        props = node.get("props", {})
        node_id = props.get("id", "(id 없음)")
        label = node["labels"][0] if node.get("labels") else None
        if node_id in label_of:
            problems.append(f"{node_id}: 같은 id 의 노드가 둘 이상이다")
        label_of[node_id] = label
        if label not in classes:
            problems.append(f"{node_id}: 스키마에 없는 클래스 {label}")
            continue
        check_props(node_id, props, classes[label]["properties"], problems)

        if "sop_id" in props and props["sop_id"] not in sops:
            problems.append(f"{node_id}: sop_id {props['sop_id']} 가 문서의 절차 번호에 없다")
        if "text" in props or "source" in props:
            text, source = props.get("text"), props.get("source")
            if source not in sections:
                problems.append(f"{node_id}: source {source!r} 가 문서의 절 번호에 없다")
            elif not isinstance(text, str) or squeeze(text) not in sections[source]:
                problems.append(f"{node_id}: text 가 {source} 절의 글자와 다르다 → {text!r}")
        for key in SENTENCE_LISTS:
            for sentence in props.get(key, []) if isinstance(props.get(key), list) else []:
                if squeeze(sentence) not in whole:
                    problems.append(f"{node_id}: {key} 의 문장이 문서의 글자와 다르다 → {sentence!r}")

    for rel in graph["rels"]:
        where = f"{rel.get('type')} {rel.get('a')} → {rel.get('b')}"
        definition = relations.get(rel.get("type"))
        if definition is None:
            problems.append(f"{where}: 스키마에 없는 관계")
            continue
        ends_ok = True
        for end, allowed in (("a", definition["from"]), ("b", definition["to"])):
            if rel.get(end) not in label_of:
                problems.append(f"{where}: {end} 의 id 가 nodes 에 없다")
                ends_ok = False
            elif label_of[rel[end]] not in allowed:
                problems.append(f"{where}: {end} 는 {' · '.join(allowed)} 여야 하는데 {label_of[rel[end]]} 다")
        if ends_ok:
            check_props(where, rel.get("props", {}), definition.get("properties", []), problems)

    by_class = Counter(n["labels"][0] for n in graph["nodes"] if n.get("labels"))
    by_type = Counter(r["type"] for r in graph["rels"])
    print(f"노드 {len(graph['nodes'])}개")
    for name in classes:
        print(f"  {name:<14} {by_class.get(name, 0)}")
    print(f"관계 {len(graph['rels'])}개")
    for name in relations:
        print(f"  {name:<14} {by_type.get(name, 0)}")
    print(f"문서의 절 {len(sections)}개, 절차 {len(sops)}편")
    print()
    for line in problems:
        print("어긋남 -", line)
    print(f"어긋남 {len(problems)}건")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
