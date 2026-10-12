"""결과/후보.json 에서 사람이 승인한 후보와 관계만 골라, 출처와 함께 그래프 DB 에 넣는 문장을 만든다.

  python 반영.py        결과/반영.cypher 와 결과/반영_요약.md 를 쓴다. 그래프 DB 에는 접속하지 않는다.
  python 반영.py 넣기   결과/반영.cypher 를 다시 만들지 않고 적힌 그대로 그래프 DB 에 보낸다.

만드는 것
1. 문서(KnowledgeSource)와, 승인된 것이 인용한 절(ManualSection). 절은 PART_OF 로 문서에 속한다.
2. 승인된 원인과 조치. 그래프에 이미 있으면 새로 만들지 않고 그 id 로 가리킨다.
   둘 다 REFERS_TO 로 자기 출처의 절을 가리킨다(citation 에 인용).
3. 조치의 작업 단계(Step). 조치가 HAS_STEP 으로 가지고, 단계는 REFERS_TO 로 절을 가리킨다.
4. 조치의 조건. 조치에서 조건이 인용한 절로 가는 REFERS_TO 의 kind, text, citation 에 적는다.
5. 승인된 관계. 출처는 관계의 source(구간)와 citation(인용)에 적는다.
   그래프에 이미 있는 관계는 새로 만들지 않고 출처만 더한다.

후보.json 은 읽기만 한다. 후보의 번호, 이름, 인용문, 문서와 절의 제목은 실행할 때마다 파일에서 읽는다.
"""

import csv
import json
import re
import sys
from pathlib import Path

import graphdb

ROOT = Path(__file__).resolve().parent
DOC_DIR = ROOT / "문서"
DOC_LIST = DOC_DIR / "문서_목록.csv"
SCHEMA = ROOT / "지난_시간" / "schema.json"
SOURCE_SCHEMA = ROOT / "출처_스키마.json"
GRAPH = ROOT / "지난_시간" / "graph.json"
CANDIDATES = ROOT / "결과" / "후보.json"
CHECK_REPORT = ROOT / "결과" / "대조_결과.md"
CYPHER = ROOT / "결과" / "반영.cypher"
SUMMARY = ROOT / "결과" / "반영_요약.md"

SECTION_MARK = "## "
APPROVED = "승인"
EXCLUDED = "제외"
SEND = "넣기"

# 출처_스키마.json 의 클래스와 관계. 이름이 스키마에 있는지는 실행할 때마다 확인한다.
STEP, SECTION, DOCUMENT = "Step", "ManualSection", "KnowledgeSource"
HAS_STEP, REFERS_TO, PART_OF = "HAS_STEP", "REFERS_TO", "PART_OF"
DOCUMENT_KIND = "manual"
# 지난_시간/schema.json 의 조치와, 고장 유형을 조치에 잇는 관계. 요약의 「고장 유형에서 닿지 않는 조치」에 쓴다.
SKILL, MITIGATED_BY = "Skill", "MITIGATED_BY"
MARK = "_manual_document"

# 넣기가 반영.cypher 에서 찾는 말. 하나라도 있으면 보내지 않는다.
FORBIDDEN = re.compile(r"\b(DETACH\s+DELETE|DELETE|REMOVE|DROP|CREATE)\b", re.IGNORECASE)
STRING = re.compile(r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"", re.DOTALL)
MISMATCH = re.compile(r"어긋난 것:\s*(\d+)건")


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_documents():
    """문서 식별자마다 {"name": 제목, "sections": {절의 번호: 절의 제목}}을 만든다."""
    documents = {}
    with open(DOC_LIST, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            text = (DOC_DIR / row["파일"].strip()).read_text(encoding="utf-8")
            sections = {}
            for line in text.splitlines():
                if line.startswith(SECTION_MARK):
                    words = line[len(SECTION_MARK):].split(None, 1)
                    if words:
                        sections[words[0]] = words[1].strip() if len(words) > 1 else ""
            documents[row["문서 식별자"].strip()] = {"name": row["제목"].strip(), "sections": sections}
    return documents


def lit(value):
    """값을 Cypher 에 적는 글로 바꾼다. 글은 고치지 않고 따옴표와 역빗금, 줄바꿈만 이스케이프한다."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    text = str(value).replace("\\", "\\\\").replace("'", "\\'").replace("\r", "\\r").replace("\n", "\\n")
    return "'" + text + "'"


def node(var, label, node_id):
    return f"({var}:{label} {{id: {lit(node_id)}}})"


def assign(var, props):
    return "SET " + ", ".join(f"{var}.{key} = {lit(value)}" for key, value in props.items())


def why_not(item):
    """넣지 않는 까닭을 돌려준다. 넣는 것이면 None 이다."""
    review = item.get("검토")
    if review == APPROVED:
        return None if item.get("검토자") else "승인인데 검토자가 없음"
    if review == EXCLUDED:
        memo = item.get("검토_메모")
        return f"{EXCLUDED} ({memo})" if memo else EXCLUDED
    return str(review) if review else "검토 값이 없음"


class Plan:
    """넣을 문장과, 새로 만드는 것 · 이미 있는 것 · 넣지 않는 것의 목록을 모은다."""

    def __init__(self, schema, source_schema, graph, documents):
        self.documents = documents
        self.classes = {c["name"] for c in schema["classes"]} | {c["name"] for c in source_schema["classes"]}
        self.rel_rules = {r["type"]: r for r in schema["relationships"] + source_schema["relationships"]}
        self.graph_label = {n["props"]["id"]: n["labels"][0] for n in graph["nodes"]}
        self.graph_name = {n["props"]["id"]: n["props"].get("name", "") for n in graph["nodes"]}
        self.graph_rels = {(r["type"], r["a"], r["b"]) for r in graph["rels"]}
        self.label_of = dict(self.graph_label)
        self.body = []            # 후보와 관계의 문장 (설명 줄 포함)
        self.sections = set()     # 승인된 것이 인용한 (문서, 구간)
        self.new_nodes = set()    # (레이블, id)
        self.new_rels = set()     # (유형, a, b, 열쇠)
        self.refers = {}          # REFERS_TO 의 갈래별 수
        self.in_candidates, self.in_relations = [], []
        self.skipped = []         # (번호, 까닭)
        self.kept_nodes, self.kept_rels = [], []

    def check_rel(self, rel_type, a_label, b_label, where):
        rule = self.rel_rules.get(rel_type)
        if rule is None:
            sys.exit(f"멈춤: {where} 의 관계 유형 `{rel_type}` 이 스키마에 없다.")
        if a_label not in rule["from"] or b_label not in rule["to"]:
            sys.exit(f"멈춤: {where} 의 `{rel_type}` 은 {a_label} 에서 {b_label} 로 이을 수 없다.")

    def section(self, source, where):
        """출처의 절을 넣을 절로 올리고 (문서, 구간)을 돌려준다."""
        doc_id, section_id = source["문서"], source["구간"]
        if doc_id not in self.documents:
            sys.exit(f"멈춤: {where} 의 문서 `{doc_id}` 가 문서_목록.csv 에 없다.")
        if section_id not in self.documents[doc_id]["sections"]:
            sys.exit(f"멈춤: {where} 의 구간 `{section_id}` 이 문서 `{doc_id}` 에 없다.")
        self.sections.add((doc_id, section_id))
        return doc_id, section_id

    def new_node(self, label, node_id, props):
        self.new_nodes.add((label, node_id))
        self.body += [f"MERGE {node('n', label, node_id)}", assign("n", props) + ";"]

    def new_rel(self, rel_type, a, b, set_props, key=None, branch=None):
        """a 에서 b 로 가는 관계를 MERGE 로 만든다. key 는 같은 양 끝 사이의 관계를 구별하는 속성이다."""
        a_label, b_label = self.label_of[a], self.label_of[b]
        self.check_rel(rel_type, a_label, b_label, f"{a} → {b}")
        self.new_rels.add((rel_type, a, b, json.dumps(key, ensure_ascii=False, sort_keys=True)))
        if branch:
            self.refers[branch] = self.refers.get(branch, 0) + 1
        inside = " {" + ", ".join(f"{k}: {lit(v)}" for k, v in key.items()) + "}" if key else ""
        self.body += [
            f"MATCH {node('a', a_label, a)}, {node('b', b_label, b)}",
            f"MERGE (a)-[r:{rel_type}{inside}]->(b)",
            assign("r", set_props) + ";",
        ]

    def refer(self, a, source, where, branch, key=None, extra=None):
        doc_id, section_id = self.section(source, where)
        self.label_of[section_id] = SECTION
        self.new_rel(REFERS_TO, a, section_id, {**(extra or {}), MARK: doc_id}, key=key, branch=branch)

    def candidate(self, cand):
        number, label, cand_id, source = cand["번호"], cand["클래스"], cand["id"], cand["출처"]
        if label not in self.classes:
            sys.exit(f"멈춤: {number} 의 클래스 `{label}` 가 스키마에 없다.")
        self.in_candidates.append(number)
        self.body += ["", f"// {number} {label} {cand['name']}"]
        if cand_id in self.graph_label:
            if self.graph_label[cand_id] != label:
                sys.exit(f"멈춤: {number} 의 id `{cand_id}` 는 그래프에서 {self.graph_label[cand_id]} 이다.")
            self.kept_nodes.append((number, label, cand_id, self.graph_name[cand_id]))
            self.body.append("// 그래프에 이미 있는 노드다. 새로 만들지 않고 출처와 단계만 덧붙인다.")
        else:
            self.new_node(label, cand_id, {"name": cand["name"], MARK: source["문서"]})

        self.refer(cand_id, source, number, "원인 · 조치 → 자기 출처의 절", key={"citation": source["인용"]})

        for step in cand.get("단계", []):
            order, step_source = step["순서"], step["출처"]
            if isinstance(order, bool) or not isinstance(order, int):
                sys.exit(f"멈춤: {number} 단계의 순서가 정수가 아니다: {order!r}")
            step_id = f"step:{cand_id.split(':', 1)[1]}/{order}"
            self.label_of[step_id] = STEP
            self.body.append(f"// {number} 단계 {order}")
            self.new_node(STEP, step_id, {"order": order, "text": step["내용"],
                                          "citation": step_source["인용"], MARK: step_source["문서"]})
            self.new_rel(HAS_STEP, cand_id, step_id, {MARK: step_source["문서"]})
            self.refer(step_id, step_source, f"{number} 단계 {order}", "단계 → 절")

        for order, condition in enumerate(cand.get("조건", []), start=1):
            self.body.append(f"// {number} 조건 {order} ({condition['구분']})")
            self.refer(cand_id, condition["출처"], f"{number} 조건 {order}", "조치 → 조건이 인용한 절",
                       key={"citation": condition["출처"]["인용"]},
                       extra={"kind": condition["구분"], "text": condition["내용"]})

    def relation(self, rel):
        number, rel_type, a, b, source = rel["번호"], rel["type"], rel["a"], rel["b"], rel["출처"]
        self.check_rel(rel_type, self.label_of[a], self.label_of[b], number)
        self.in_relations.append(number)
        props = {"source": source["구간"], "citation": source["인용"]}
        self.body += ["", f"// {number} {rel_type} {a} → {b}"]
        if (rel_type, a, b) in self.graph_rels:
            self.kept_rels.append((number, rel_type, a, b))
            self.body += [
                "// 그래프에 이미 있는 관계다. 새로 만들지 않고 출처만 더한다.",
                f"MATCH {node('a', self.label_of[a], a)}-[r:{rel_type}]->{node('b', self.label_of[b], b)}",
                assign("r", props) + ";",
            ]
        else:
            self.new_rel(rel_type, a, b, {**props, MARK: source["문서"]})

    def head(self):
        """문서와 절을 만드는 문장. 승인된 것이 인용한 절만, 원문에 나오는 순서로 만든다."""
        lines = []
        for doc_id in sorted({doc_id for doc_id, _ in self.sections}):
            document = self.documents[doc_id]
            self.new_nodes.add((DOCUMENT, doc_id))
            lines += [
                "", f"// 문서 {doc_id}",
                f"MERGE {node('d', DOCUMENT, doc_id)}",
                assign("d", {"name": document["name"], "kind": DOCUMENT_KIND, "ref": doc_id, MARK: doc_id}) + ";",
            ]
            for section_id, title in document["sections"].items():
                if (doc_id, section_id) not in self.sections:
                    continue
                self.check_rel(PART_OF, SECTION, DOCUMENT, section_id)
                self.new_nodes.add((SECTION, section_id))
                self.new_rels.add((PART_OF, section_id, doc_id, "null"))
                lines += [
                    f"// 절 {section_id}",
                    f"MERGE {node('s', SECTION, section_id)}",
                    assign("s", {"ref": section_id, "title": title, MARK: doc_id}) + ";",
                    f"MATCH {node('s', SECTION, section_id)}, {node('d', DOCUMENT, doc_id)}",
                    f"MERGE (s)-[r:{PART_OF}]->(d)",
                    assign("r", {MARK: doc_id}) + ";",
                ]
        return lines


def make_plan():
    data = load_json(CANDIDATES)
    plan = Plan(load_json(SCHEMA), load_json(SOURCE_SCHEMA), load_json(GRAPH), load_documents())

    approved = []
    for cand in data.get("후보", []):
        why = why_not(cand)
        if why:
            plan.skipped.append((cand["번호"], why))
        else:
            approved.append(cand)
            plan.label_of[cand["id"]] = cand["클래스"]
    for cand in approved:
        plan.candidate(cand)

    # 관계는 양 끝이 그래프에 이미 있거나 승인된 후보일 때에만 넣는다.
    ready = set(plan.graph_label) | {cand["id"] for cand in approved}
    for rel in data.get("관계", []):
        why = why_not(rel)
        missing = [rel[end] for end in ("a", "b") if rel[end] not in ready]
        if why:
            plan.skipped.append((rel["번호"], why))
        elif missing:
            plan.skipped.append((rel["번호"], "한쪽 끝이 승인되지 않음: " + ", ".join(f"`{m}`" for m in missing)))
        else:
            plan.relation(rel)
    return plan


def count_by(items):
    counts = {}
    for item in items:
        counts[item[0]] = counts.get(item[0], 0) + 1
    return counts


def write_cypher(plan, head):
    lines = [
        "// 결과/후보.json 에서 승인된 후보와 관계를 출처와 함께 그래프 DB 에 넣는 문장이다.",
        "// python 반영.py 가 만든 파일이다. 사람이 읽어 본 뒤 python 반영.py 넣기 로 넣는다.",
        "// 두 번 넣어도 노드와 관계가 늘지 않는다.",
        f"// 넣는 후보: {', '.join(plan.in_candidates) or '없음'}",
        f"// 넣는 관계: {', '.join(plan.in_relations) or '없음'}",
    ]
    CYPHER.write_text("\n".join(lines + head + plan.body) + "\n", encoding="utf-8")


def write_summary(plan):
    nodes, rels = count_by(plan.new_nodes), count_by(plan.new_rels)
    lines = [
        "# 반영 요약",
        "",
        f"- 넣는 후보: {', '.join(plan.in_candidates) or '없음'}",
        f"- 넣는 관계: {', '.join(plan.in_relations) or '없음'}",
        "- 넣지 않는 것:" + ("" if plan.skipped else " 없음"),
    ]
    lines += [f"  - {number}: {why}" for number, why in plan.skipped]

    lines += ["", "## 새로 만드는 노드", "", "| 레이블 | 수 |", "|---|---|"]
    lines += [f"| {label} | {count} |" for label, count in nodes.items()]
    lines.append(f"| 합계 | {sum(nodes.values())} |")

    lines += ["", "## 새로 만드는 관계", "", "| 유형 | 수 |", "|---|---|"]
    lines += [f"| {rel_type} | {count} |" for rel_type, count in rels.items()]
    lines.append(f"| 합계 | {sum(rels.values())} |")
    if plan.refers:
        lines += ["", f"{REFERS_TO} 의 갈래: " + ", ".join(f"{name} {count}" for name, count in plan.refers.items())]

    lines += ["", "## 그래프에 이미 있어 늘지 않는 것", ""]
    lines += [f"- 노드 {number}: {label} `{node_id}` {name} — id 와 name 은 그대로 두고 출처의 절과 단계만 덧붙인다"
              for number, label, node_id, name in plan.kept_nodes]
    lines += [f"- 관계 {number}: {rel_type} `{a}` → `{b}` — 새로 만들지 않고 source 와 citation 만 더한다"
              for number, rel_type, a, b in plan.kept_rels]
    if not plan.kept_nodes and not plan.kept_rels:
        lines.append("없음")

    lines += ["", "## 고장 유형에서 닿지 않는 조치", ""]
    unreached = unreached_skills(plan)
    if unreached:
        lines += ["| 번호 | 이름 | 까닭 |", "|---|---|---|"]
        lines += [f"| {number} | {table_cell(name)} | {table_cell(why)} |" for number, name, why in unreached]
    else:
        lines.append("없음")
    SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")


def table_cell(text):
    return str(text).replace("|", "\\|").replace("\n", "⏎")


def unreached_skills(plan):
    """넣는 조치 가운데 고장 유형에서 MITIGATED_BY 로 이어지지 않는 것을 (번호, 이름, 까닭)으로 모은다.

    그래프에 이미 있는 관계와 이번에 넣는 관계를 합쳐서 본다.
    """
    data = load_json(CANDIDATES)
    relations = [rel for rel in data.get("관계", []) if rel.get("type") == MITIGATED_BY]
    reached = {b for rel_type, _, b in plan.graph_rels if rel_type == MITIGATED_BY}
    reached |= {rel["b"] for rel in relations if rel["번호"] in plan.in_relations}
    skipped = dict(plan.skipped)

    rows = []
    for cand in data.get("후보", []):
        number = cand["번호"]
        if number not in plan.in_candidates or cand["클래스"] != SKILL or cand["id"] in reached:
            continue
        # 보류에 이 조치의 MITIGATED_BY 가 적혀 있으면 그 까닭을 그대로 옮긴다.
        held = [h for h in data.get("보류", [])
                if MITIGATED_BY in h.get("내용", "") and re.search(rf"{re.escape(number)}(?!\d)", h["내용"])]
        waiting = [rel["번호"] for rel in relations if rel["b"] == cand["id"] and rel["번호"] in skipped]
        if held:
            why = held[0]["까닭"]
        elif waiting:
            why = "관계 후보를 넣지 않음: " + ", ".join(f"{n}({skipped[n]})" for n in waiting)
        else:
            why = f"후보.json 에 이 조치의 {MITIGATED_BY} 관계 후보가 없음"
        rows.append((number, cand["name"], why))
    return rows


def make():
    if not CANDIDATES.exists():
        sys.exit(f"{CANDIDATES.relative_to(ROOT)} 이 없다.")
    plan = make_plan()
    head = plan.head()
    # 실행할 때마다 같은 순서로 적히도록 정렬해 둔다.
    plan.new_nodes = sorted(plan.new_nodes)
    plan.new_rels = sorted(plan.new_rels)
    write_cypher(plan, head)
    write_summary(plan)
    nodes, rels = count_by(plan.new_nodes), count_by(plan.new_rels)
    print(f"넣는 후보 {len(plan.in_candidates)}건, 넣는 관계 {len(plan.in_relations)}건, 넣지 않는 것 {len(plan.skipped)}건")
    print(f"새로 만드는 노드 {sum(nodes.values())}: " + ", ".join(f"{k} {v}" for k, v in nodes.items()))
    print(f"새로 만드는 관계 {sum(rels.values())}: " + ", ".join(f"{k} {v}" for k, v in rels.items()))
    print(f"→ {CYPHER.relative_to(ROOT)}, {SUMMARY.relative_to(ROOT)}")
    return 0


def reasons_not_to_send():
    """보내기 전에 확인한다. 보내면 안 되는 까닭의 목록을 돌려준다."""
    reasons = []
    if not CYPHER.exists():
        reasons.append(f"{CYPHER.relative_to(ROOT)} 가 없다. python 반영.py 로 먼저 만든다.")
    else:
        for statement in graphdb.split_statements(CYPHER.read_text(encoding="utf-8")):
            found = FORBIDDEN.search(STRING.sub("''", statement))
            if found:
                word = " ".join(found.group().upper().split())
                reasons.append(f"{CYPHER.relative_to(ROOT)} 에 넣으면 안 되는 문장({word})이 있다: "
                               f"{statement.splitlines()[0]}")
    if not CHECK_REPORT.exists():
        reasons.append(f"{CHECK_REPORT.relative_to(ROOT)} 가 없다. python 대조.py 를 먼저 실행한다.")
    else:
        found = MISMATCH.search(CHECK_REPORT.read_text(encoding="utf-8"))
        if not found:
            reasons.append(f"{CHECK_REPORT.relative_to(ROOT)} 에서 어긋난 것의 수를 읽지 못했다.")
        elif int(found.group(1)) != 0:
            reasons.append(f"{CHECK_REPORT.relative_to(ROOT)} 의 어긋난 것이 {found.group(1)}건이다.")
    return reasons


def count_graph():
    nodes = graphdb.query("MATCH (n) RETURN count(n) AS n")[0]["n"]
    rels = graphdb.query("MATCH ()-[r]->() RETURN count(r) AS n")[0]["n"]
    return nodes, rels


def send():
    reasons = reasons_not_to_send()
    if reasons:
        print("멈춤: 그래프 DB 에 보내지 않았다.")
        for reason in reasons:
            print(f"- {reason}")
        return 1
    statements = graphdb.split_statements(CYPHER.read_text(encoding="utf-8"))
    before = count_graph()
    stats = graphdb.run_all(statements)
    after = count_graph()
    print(f"그래프 DB: {graphdb.ADDRESS}")
    print(f"보낸 문장: {len(statements)}개 ({CYPHER.relative_to(ROOT)})")
    print(f"보내기 전: 노드 {before[0]}, 관계 {before[1]}")
    print(f"보낸 뒤:   노드 {after[0]}, 관계 {after[1]}")
    print(f"새로 생긴 것: 노드 {stats['nodes_created']}, 관계 {stats['relationships_created']}, "
          f"속성 {stats['properties_set']}")
    return 0


def main():
    args = sys.argv[1:]
    if not args:
        return make()
    if args == [SEND]:
        try:
            return send()
        except graphdb.GraphError as error:
            print(f"멈춤: {error}")
            return 1
    print(f"쓰는 법: python 반영.py  또는  python 반영.py {SEND}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
