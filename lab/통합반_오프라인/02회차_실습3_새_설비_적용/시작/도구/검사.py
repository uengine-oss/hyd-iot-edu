"""결과/graph.json 이 결과/schema.json 의 정의대로 적혔는지, 처음 받은 것에서 무엇이 달라졌는지 본다.

    python 도구/검사.py

읽기만 한다. 어떤 파일도 고치지 않는다. 파이썬 표준 라이브러리만 쓴다.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def type_ok(value, prop):
    t = prop["type"]
    if t == "string":
        return isinstance(value, str)
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if t == "boolean":
        return isinstance(value, bool)
    if t == "string[]":
        return isinstance(value, list) and all(isinstance(x, str) for x in value)
    if t == "enum":
        return value in prop.get("values", [])
    return False


def check_props(where, props, defs, errors):
    by_name = {p["name"]: p for p in defs}
    for k, v in props.items():
        if k not in by_name:
            errors.append(f"{where}: 스키마에 없는 속성 {k}")
        elif not type_ok(v, by_name[k]):
            errors.append(f"{where}: {k} 의 값 {v!r} 이 자료형 {by_name[k]['type']} 과 맞지 않는다")
    for p in defs:
        if p.get("required") and p["name"] not in props:
            errors.append(f"{where}: 필수 속성 {p['name']} 이 없다")


def check(schema, graph):
    errors, review = [], []
    classes = {c["name"]: c for c in schema["classes"]}
    rels = {r["type"]: r for r in schema["relationships"]}

    label_of = {}
    seen = Counter()
    for n in graph["nodes"]:
        label = n["labels"][0] if n.get("labels") else "?"
        props = n.get("props", {})
        nid = props.get("id", "(id 없음)")
        seen[nid] += 1
        label_of[nid] = label
        if label not in classes:
            errors.append(f"{nid}: 스키마에 없는 클래스 {label}")
            continue
        check_props(nid, props, classes[label]["properties"], errors)
    for nid, k in seen.items():
        if k > 1:
            errors.append(f"{nid}: 같은 식별자를 가진 노드가 {k}개다")

    out_deg = defaultdict(lambda: defaultdict(set))   # 관계 → 시작 노드 → 끝 노드들
    in_deg = defaultdict(lambda: defaultdict(set))    # 관계 → 끝 노드 → 시작 노드들
    pair = Counter()
    for r in graph["rels"]:
        t, a, b = r["type"], r["a"], r["b"]
        where = f"{t} {a} → {b}"
        pair[(t, a, b)] += 1
        if t not in rels:
            errors.append(f"{where}: 스키마에 없는 관계")
            continue
        bad = False
        for end, name in ((a, "시작"), (b, "끝")):
            if end not in label_of:
                errors.append(f"{where}: {name} 노드 {end} 가 nodes 에 없다")
                bad = True
        if bad:
            continue
        d = rels[t]
        if label_of[a] not in d["from"]:
            errors.append(f"{where}: 시작이 {label_of[a]} 인데 스키마는 {' · '.join(d['from'])} 에서 시작한다")
        if label_of[b] not in d["to"]:
            errors.append(f"{where}: 끝이 {label_of[b]} 인데 스키마는 {' · '.join(d['to'])} 에서 끝난다")
        check_props(where, r.get("props", {}), d.get("properties", []), errors)
        out_deg[t][a].add(b)
        in_deg[t][b].add(a)
    for (t, a, b), k in pair.items():
        if k > 1:
            errors.append(f"{t} {a} → {b}: 같은 관계가 {k}번 들어 있다")

    for t, d in rels.items():
        left, right = d.get("cardinality", "N:M").split(":")
        if right == "1":      # 시작 하나에 끝은 하나까지
            for a, bs in sorted(out_deg[t].items()):
                if len(bs) > 1:
                    review.append(f"{t} 는 {d['cardinality']} 인데 {a} 하나에서 끝이 {len(bs)}개로 나간다: {', '.join(sorted(bs))}")
        if left == "1":       # 끝 하나에 시작은 하나까지
            for b, as_ in sorted(in_deg[t].items()):
                if len(as_) > 1:
                    review.append(f"{t} 는 {d['cardinality']} 인데 {b} 하나에 시작이 {len(as_)}개 이어져 있다: {', '.join(sorted(as_))}")
    return errors, review


def rel_key(r):
    return (r["type"], r["a"], r["b"])


def diff(first, now):
    old = {n["props"]["id"]: n for n in first["nodes"]}
    new = {n["props"].get("id"): n for n in now["nodes"]}
    gone = sorted(i for i in old if i not in new)
    changed = sorted(i for i in old if i in new and old[i] != new[i])
    added = [n for n in now["nodes"] if n["props"].get("id") not in old]
    old_r = {rel_key(r): r for r in first["rels"]}
    new_r = {rel_key(r): r for r in now["rels"]}
    gone_r = sorted(k for k in old_r if k not in new_r)
    changed_r = sorted(k for k in old_r if k in new_r and old_r[k] != new_r[k])
    added_r = [r for r in now["rels"] if rel_key(r) not in old_r]
    return gone, changed, added, gone_r, changed_r, added_r


def main():
    schema = load(ROOT / "결과" / "schema.json")
    graph = load(ROOT / "결과" / "graph.json")
    first_schema = load(HERE / "처음_schema.json")
    first_graph = load(HERE / "처음_graph.json")

    print("[1] 스키마")
    print("  결과/schema.json 은 처음 받은 것과 " + ("같다" if schema == first_schema else "다르다  ← 이 실습에서는 스키마를 고치지 않는다"))
    print(f"  클래스 {len(schema['classes'])} · 관계 {len(schema['relationships'])} · conventions {len(schema['conventions'])}문장")

    print("[2] 지금 들어 있는 것")
    by_label = Counter(n["labels"][0] for n in graph["nodes"])
    by_type = Counter(r["type"] for r in graph["rels"])
    print(f"  노드 {len(graph['nodes'])}: " + ", ".join(f"{k} {v}" for k, v in by_label.items()))
    print(f"  관계 {len(graph['rels'])}: " + ", ".join(f"{k} {v}" for k, v in by_type.items()))

    print("[3] 처음 받은 것에서 달라진 것")
    gone, changed, added, gone_r, changed_r, added_r = diff(first_graph, graph)
    print(f"  처음부터 있던 노드 {len(first_graph['nodes'])}: 사라진 것 {len(gone)}, 값이 바뀐 것 {len(changed)}")
    for i in gone:
        print(f"    사라짐 {i}")
    for i in changed:
        print(f"    바뀜 {i}")
    print(f"  처음부터 있던 관계 {len(first_graph['rels'])}: 사라진 것 {len(gone_r)}, 값이 바뀐 것 {len(changed_r)}")
    for k in gone_r + changed_r:
        print(f"    {k[0]} {k[1]} → {k[2]}")
    add_label = Counter(n["labels"][0] for n in added)
    add_type = Counter(r["type"] for r in added_r)
    print(f"  새로 들어온 노드 {len(added)}" + (": " + ", ".join(f"{k} {v}" for k, v in add_label.items()) if added else ""))
    for n in added:
        print(f"    {n['labels'][0]} {n['props'].get('id')} {n['props'].get('name', '')}")
    print(f"  새로 들어온 관계 {len(added_r)}" + (": " + ", ".join(f"{k} {v}" for k, v in add_type.items()) if added_r else ""))

    errors, review = check(schema, graph)
    print(f"[4] 스키마와 맞지 않는 곳 {len(errors)}")
    for x in errors:
        print("  - " + x)
    print(f"[5] 카디널리티와 다르게 이어진 곳 {len(review)}")
    for x in review:
        print("  - " + x)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
