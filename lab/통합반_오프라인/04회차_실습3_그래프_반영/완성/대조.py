"""결과/후보.json 을 문서/ 의 원문과 지난_시간/ 의 스키마 · 그래프에 대어 보고 결과/대조_결과.md 를 쓴다.

검사하는 것
1. 인용: 출처마다 인용이 그 문서의 그 구간 안에 글자 그대로 있는가.
2. 수치: 단계와 조건의 수치(값, 단위)가 그 항목의 인용 안에 있는가.
3. 스키마: 후보의 클래스와 관계의 type 이 schema.json 에 있는가.
   관계의 a 와 b 가 후보의 id 이거나 graph.json 의 id 인가.
4. 등록됨: true 인 후보의 id 는 graph.json 에 있고, false 인 후보의 id 는 없는가.

후보.json 은 읽기만 한다. 문서의 이름, 절의 번호, 인용문은 실행할 때마다 파일에서 읽는다.
"""

import csv
import json
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOC_DIR = ROOT / "문서"
DOC_LIST = DOC_DIR / "문서_목록.csv"
SCHEMA = ROOT / "지난_시간" / "schema.json"
GRAPH = ROOT / "지난_시간" / "graph.json"
CANDIDATES = ROOT / "결과" / "후보.json"
REPORT = ROOT / "결과" / "대조_결과.md"

SECTION_MARK = "## "
NUMBER = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")

# 「사람이 읽을 곳」에 모을 말. 인용에 이 가운데 하나라도 든 단계와 조건을 결과 md 의 끝에 모은다.
READ_WORDS = ["아닐", "않는다", "때만", "미만", "이하", "이상", "초과", "이내"]


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_documents():
    """문서 식별자마다 {절의 번호: 절의 글}을 만든다."""
    documents = {}
    with open(DOC_LIST, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            doc_id = row["문서 식별자"].strip()
            text = (DOC_DIR / row["파일"].strip()).read_text(encoding="utf-8")
            documents[doc_id] = split_sections(text)
    return documents


def split_sections(text):
    """`## ` 줄부터 다음 `## ` 줄의 앞까지를 절 하나로 자른다."""
    sections = {}
    current = None
    for line in text.splitlines(keepends=True):
        if line.startswith(SECTION_MARK):
            words = line[len(SECTION_MARK):].split()
            current = words[0] if words else None
            if current is not None:
                sections[current] = ""
        if current is not None:
            sections[current] += line
    return sections


def check_source(source, documents):
    """출처 한 건을 원문에 대어 보고, 어긋났으면 까닭을 돌려준다."""
    if not isinstance(source, dict):
        return "출처가 객체 하나가 아니다"
    for key in ("문서", "구간", "인용"):
        if not isinstance(source.get(key), str) or not source[key]:
            return f"출처에 `{key}` 칸이 없거나 비어 있다"
    doc_id, section, quote = source["문서"], source["구간"], source["인용"]
    if doc_id not in documents:
        return f"문서 식별자 `{doc_id}` 가 문서_목록.csv 에 없다"
    if section not in documents[doc_id]:
        return f"구간 `{section}` 이 문서 `{doc_id}` 에 없다"
    if quote in documents[doc_id][section]:
        return None
    elsewhere = [name for name, body in documents[doc_id].items() if quote in body]
    if elsewhere:
        return f"인용이 `{section}` 에 없고 `{', '.join(elsewhere)}` 에 있다: 「{quote}」"
    loose = "".join(quote.split())
    if loose and loose in "".join(documents[doc_id][section].split()):
        return f"인용이 `{section}` 의 글과 공백이나 줄바꿈이 다르다: 「{quote}」"
    return f"인용이 `{section}` 에 글자 그대로 있지 않다: 「{quote}」"


def check_figure(figure, quote):
    """수치 한 건의 값과 단위가 인용 안에 붙어서 나오는지 본다."""
    if not isinstance(figure, dict):
        return "수치가 `{값, 단위}` 꼴이 아니다"
    value, unit = figure.get("값"), figure.get("단위")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return f"수치의 값이 수가 아니다: {value!r}"
    if not isinstance(unit, str) or not unit:
        return f"수치의 단위가 없다: 값 {value}"
    want = Decimal(str(value))
    for found in NUMBER.finditer(quote):
        try:
            number = Decimal(found.group().replace(",", ""))
        except InvalidOperation:
            continue
        if number == want and quote[found.end():].lstrip(" \t").startswith(unit):
            return None
    return f"수치 {value} {unit} 가 인용 안에 없다: 「{quote}」"


def main():
    if not CANDIDATES.exists():
        sys.exit(f"{CANDIDATES.relative_to(ROOT)} 이 없다.")
    data = load_json(CANDIDATES)
    documents = load_documents()
    schema = load_json(SCHEMA)
    graph = load_json(GRAPH)

    class_names = {c["name"] for c in schema["classes"]}
    rel_types = {r["type"] for r in schema["relationships"]}
    graph_ids = {n["props"]["id"] for n in graph["nodes"]}
    candidates = data.get("후보", [])
    candidate_ids = {c.get("id") for c in candidates}

    source_count = 0
    problems = []  # (번호, 검사, 까닭)

    def source_of(label, item):
        nonlocal source_count
        source_count += 1
        why = check_source(item.get("출처"), documents)
        if why:
            problems.append((label, "인용", why))

    for cand in candidates:
        label = cand.get("번호", "(번호 없음)")
        source_of(label, cand)

        if cand.get("클래스") not in class_names:
            problems.append((label, "스키마", f"클래스 `{cand.get('클래스')}` 가 schema.json 에 없다"))

        registered, cand_id = cand.get("등록됨"), cand.get("id")
        if not isinstance(registered, bool):
            problems.append((label, "등록됨", f"`등록됨` 이 true 나 false 가 아니다: {registered!r}"))
        elif registered and cand_id not in graph_ids:
            problems.append((label, "등록됨", f"등록됨이 true 인데 id `{cand_id}` 가 graph.json 에 없다"))
        elif not registered and cand_id in graph_ids:
            problems.append((label, "등록됨", f"등록됨이 false 인데 id `{cand_id}` 가 graph.json 에 있다"))

        for kind in ("단계", "조건"):
            for order, item in enumerate(cand.get(kind, []), start=1):
                item_label = f"{label} {kind} {item.get('순서', order) if kind == '단계' else order}"
                source_of(item_label, item)
                source = item.get("출처")
                quote = source.get("인용", "") if isinstance(source, dict) else ""
                for figure in item.get("수치", []):
                    why = check_figure(figure, quote)
                    if why:
                        problems.append((item_label, "수치", why))

    for rel in data.get("관계", []):
        label = rel.get("번호", "(번호 없음)")
        source_of(label, rel)
        if rel.get("type") not in rel_types:
            problems.append((label, "스키마", f"type `{rel.get('type')}` 이 schema.json 에 없다"))
        for end in ("a", "b"):
            if rel.get(end) not in candidate_ids and rel.get(end) not in graph_ids:
                problems.append((label, "스키마", f"`{end}` 의 id `{rel.get(end)}` 가 후보에도 graph.json 에도 없다"))

    for order, held in enumerate(data.get("보류", []), start=1):
        source_of(f"보류 {order}", held)

    write_report(source_count, problems, data)
    print(f"검사한 출처 {source_count}건, 어긋난 것 {len(problems)}건 → {REPORT.relative_to(ROOT)}")


def table_cell(text):
    return str(text).replace("|", "\\|").replace("\n", "⏎")


def items_to_read(data):
    """인용에 READ_WORDS 의 말이 든 단계와 조건을 (번호, 내용, 인용)으로 모은다."""
    rows = []
    for cand in data.get("후보", []):
        label = cand.get("번호", "(번호 없음)")
        for kind in ("단계", "조건"):
            for order, item in enumerate(cand.get(kind, []), start=1):
                source = item.get("출처")
                quote = source.get("인용", "") if isinstance(source, dict) else ""
                if not isinstance(quote, str) or not any(word in quote for word in READ_WORDS):
                    continue
                number = item.get("순서", order) if kind == "단계" else order
                rows.append((f"{label} {kind} {number}", item.get("내용", ""), quote))
    return rows


def write_report(source_count, problems, data):
    kinds = ("인용", "수치", "스키마", "등록됨")
    counts = {kind: sum(1 for p in problems if p[1] == kind) for kind in kinds}
    lines = [
        "# 대조 결과",
        "",
        f"- 검사한 출처: {source_count}건",
        f"- 어긋난 것: {len(problems)}건 ("
        + ", ".join(f"{kind} {counts[kind]}건" for kind in kinds)
        + ")",
        "",
        "## 어긋난 것",
        "",
    ]
    if problems:
        lines += ["| 번호 | 검사 | 까닭 |", "|---|---|---|"]
        for label, kind, why in problems:
            lines.append(f"| {label} | {kind} | {table_cell(why)} |")
    else:
        lines.append("없음")

    rows = items_to_read(data)
    lines += [
        "",
        "## 사람이 읽을 곳",
        "",
        "인용에 " + ", ".join(READ_WORDS) + " 가운데 하나라도 든 단계와 조건이다. "
        "내용의 뜻이 인용과 같은지는 프로그램이 가리지 못하므로 사람이 읽는다.",
        "",
    ]
    if rows:
        lines += ["| 번호 | 내용 | 인용 |", "|---|---|---|"]
        for label, content, quote in rows:
            lines.append(f"| {label} | {table_cell(content)} | {table_cell(quote)} |")
    else:
        lines.append("없음")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
