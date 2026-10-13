"""결과/후보.json 과 문서/ 를 읽어 개정을 반영한 결과를 조회하고 결과/개정_조회.md 를 쓴다.

조회하는 것
1. 이전 기준과 새 기준: `이전` 칸이 있는 단계 · 조건 · 보류마다 이전 기준과 지금 기준을 출처와 함께 나란히 적는다.
2. 중복: 번호가 같은 후보나 관계, id 가 같은 후보, 한 조치 안에서 순서가 같은 단계,
   type 과 양 끝(a, b)이 모두 같은 관계. 같은 값을 나눠 가진 묶음 하나를 한 건으로 센다.
3. 낡은 인용: 지금 기준의 출처 가운데, 그 인용이 그 문서의 지금 판본의 그 구간에 없는 것.
   `이전` 에 든 출처는 지금 기준이 아니므로 보지 않는다.
4. 판본별 출처: 문서와 판본마다 지금 기준의 출처와 이전 기준의 출처가 몇 건인지 센다.

후보.json 은 읽기만 한다. 문서의 이름, 판본의 값, 절의 번호, 인용문은 실행할 때마다 파일에서 읽는다.
"""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOC_DIR = ROOT / "문서"
VERSION_LIST = DOC_DIR / "판본_목록.csv"
CANDIDATES = ROOT / "결과" / "후보.json"
REPORT = ROOT / "결과" / "개정_조회.md"

SECTION_MARK = "## "
NO_VERSION = "(없음)"


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


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


def load_versions():
    """판본_목록.csv 를 읽어 (문서, 판본)의 차례, 판본마다의 절, 문서마다의 지금 판본을 돌려준다."""
    order = []  # (문서 식별자, 판본) — 목록에 적힌 차례
    sections = {}  # (문서 식별자, 판본) → {절의 번호: 절의 글}
    pointed = {}  # 문서 식별자 → 다른 줄이 「앞 판본」으로 가리킨 판본
    with open(VERSION_LIST, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            doc_id, version = row["문서 식별자"].strip(), row["판본"].strip()
            order.append((doc_id, version))
            text = (DOC_DIR / row["파일"].strip()).read_text(encoding="utf-8")
            sections[(doc_id, version)] = split_sections(text)
            before = (row["앞 판본"] or "").strip()
            pointed.setdefault(doc_id, set())
            if before:
                pointed[doc_id].add(before)
    current = {}
    for doc_id in pointed:
        leaves = [v for d, v in order if d == doc_id and v not in pointed[doc_id]]
        if len(leaves) != 1:
            sys.exit(f"문서 `{doc_id}` 의 지금 판본을 하나로 정할 수 없다: {leaves}")
        current[doc_id] = leaves[0]
    return order, sections, current


def walk(data):
    """출처를 가진 항목을 (이름표, 항목)으로 차례로 내놓는다. `이전` 은 내놓지 않는다."""
    for cand in data.get("후보", []):
        label = cand.get("번호", "(번호 없음)")
        yield label, cand
        for kind in ("단계", "조건"):
            for order, item in enumerate(cand.get(kind, []), start=1):
                number = item.get("순서", order) if kind == "단계" else order
                yield f"{label} {kind} {number}", item
    for rel in data.get("관계", []):
        yield rel.get("번호", "(번호 없음)"), rel
    for order, held in enumerate(data.get("보류", []), start=1):
        yield f"보류 {order}", held


def source_fields(item):
    source = item.get("출처") if isinstance(item, dict) else None
    if not isinstance(source, dict):
        source = {}
    return tuple(source.get(key, "") for key in ("문서", "판본", "구간", "인용"))


def earlier_of(item):
    earlier = item.get("이전")
    return [old for old in earlier if isinstance(old, dict)] if isinstance(earlier, list) else []


def review_of(item):
    review, reviewer = item.get("검토", ""), item.get("검토자", "")
    return f"{review} ({reviewer})" if reviewer else review


def changed_rows(data):
    """기준이 바뀐 항목마다 이전 기준들과 지금 기준을 오래된 것부터 줄로 만든다."""
    count = 0
    rows = []  # (번호, 구분, 문서, 판본, 구간, 내용, 인용, 검토)
    for label, item in walk(data):
        if "이전" not in item:
            continue
        count += 1
        for old in earlier_of(item):
            doc_id, version, section, quote = source_fields(old)
            rows.append((label, "이전", doc_id, version, section, old.get("내용", ""), quote, ""))
        doc_id, version, section, quote = source_fields(item)
        rows.append((label, "지금", doc_id, version, section, item.get("내용", ""), quote, review_of(item)))
    return count, rows


def find_duplicates(data):
    """중복을 (무엇이 같은가, 같은 값, 어디)로 모은다. 묶음 하나가 한 건이다."""
    groups = {}  # (무엇이 같은가, 같은 값) → [어디]

    def put(kind, value, where):
        groups.setdefault((kind, value), []).append(where)

    candidates, relations = data.get("후보", []), data.get("관계", [])
    for index, cand in enumerate(candidates, start=1):
        where = f"후보 {index}번째 ({cand.get('번호', '번호 없음')}, {cand.get('id', 'id 없음')})"
        if cand.get("번호") is not None:
            put("번호", str(cand["번호"]), where)
        if cand.get("id") is not None:
            put("후보의 id", str(cand["id"]), where)
        # 조치는 후보 한 건이다. 번호가 겹친 다른 후보의 단계와 섞이지 않게 후보의 자리로 묶는다.
        for order, step in enumerate(cand.get("단계", []), start=1):
            if step.get("순서") is not None:
                put(
                    "한 조치 안의 단계 순서",
                    f"후보 {index}번째 ({cand.get('번호', '번호 없음')}) 순서 {step['순서']}",
                    f"후보 {index}번째의 단계 {order}번째",
                )
    for index, rel in enumerate(relations, start=1):
        where = f"관계 {index}번째 ({rel.get('번호', '번호 없음')})"
        if rel.get("번호") is not None:
            put("번호", str(rel["번호"]), where)
        put("관계의 type 과 양 끝", f"{rel.get('type')} {rel.get('a')} → {rel.get('b')}", where)

    return [(kind, value, places) for (kind, value), places in groups.items() if len(places) > 1]


def find_stale(data, sections, current):
    """지금 기준의 출처 가운데 인용이 그 문서의 지금 판본의 그 구간에 없는 것을 모은다."""
    rows = []  # (번호, 문서, 적힌 판본, 지금 판본, 구간, 인용)
    for label, item in walk(data):
        doc_id, version, section, quote = source_fields(item)
        now = current.get(doc_id)
        body = sections.get((doc_id, now), {}).get(section)
        if now is None or body is None or not quote or quote not in body:
            rows.append((label, doc_id, version, now if now is not None else NO_VERSION, section, quote))
    return rows


def count_by_version(data, order):
    """(문서, 판본)마다 지금 기준의 출처와 이전 기준의 출처를 센다."""
    counts = {key: [0, 0] for key in order}  # (문서, 판본) → [지금, 이전]
    for _, item in walk(data):
        doc_id, version, _, _ = source_fields(item)
        counts.setdefault((doc_id, version or NO_VERSION), [0, 0])[0] += 1
        for old in earlier_of(item):
            doc_id, version, _, _ = source_fields(old)
            counts.setdefault((doc_id, version or NO_VERSION), [0, 0])[1] += 1
    return counts


def table_cell(text):
    return str(text).replace("|", "\\|").replace("\n", "⏎")


def table(header, rows):
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for row in rows:
        lines.append("| " + " | ".join(table_cell(cell) for cell in row) + " |")
    return lines


def main():
    if not CANDIDATES.exists():
        sys.exit(f"{CANDIDATES.relative_to(ROOT)} 이 없다.")
    data = load_json(CANDIDATES)
    order, sections, current = load_versions()

    changed_count, changed = changed_rows(data)
    duplicates = find_duplicates(data)
    stale = find_stale(data, sections, current)
    counts = count_by_version(data, order)

    lines = [
        "# 개정 조회",
        "",
        f"- 기준이 바뀐 항목: {changed_count}건",
        f"- 중복: {len(duplicates)}건",
        f"- 낡은 인용: {len(stale)}건",
        "",
        "## 이전 기준과 새 기준",
        "",
    ]
    if changed:
        lines += table(["번호", "구분", "문서", "판본", "구간", "내용", "인용", "검토"], changed)
    else:
        lines.append("없음")

    lines += ["", "## 중복", ""]
    if duplicates:
        lines += table(
            ["무엇이 같은가", "같은 값", "어디"],
            [(kind, value, ", ".join(places)) for kind, value, places in duplicates],
        )
    else:
        lines.append("없음")

    lines += ["", "## 낡은 인용", ""]
    if stale:
        lines += table(["번호", "문서", "적힌 판본", "지금 판본", "구간", "인용"], stale)
    else:
        lines.append("없음")

    lines += ["", "## 판본별 출처", ""]
    lines += table(
        ["문서", "판본", "지금 기준의 출처", "이전 기준의 출처"],
        [(doc_id, version, f"{now}건", f"{old}건") for (doc_id, version), (now, old) in counts.items()],
    )

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        f"기준이 바뀐 항목 {changed_count}건, 중복 {len(duplicates)}건, 낡은 인용 {len(stale)}건"
        f" → {REPORT.relative_to(ROOT)}"
    )


if __name__ == "__main__":
    main()
