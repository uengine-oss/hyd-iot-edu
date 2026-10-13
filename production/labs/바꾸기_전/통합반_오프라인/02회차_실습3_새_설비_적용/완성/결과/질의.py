"""설비의 구성 요소마다 붙은 센서, 센서가 재는 값, 쓰는 부품을 표로 낸다.

    python 결과/질의.py <설비 코드> [<설비 코드> ...]

거꾸로, 부품을 쓰는 구성 요소와 그 구성 요소를 가진 설비를 표로 낸다.

    python 결과/질의.py --부품 <품번> [<품번> ...]

실행할 때마다 결과/graph.json 을 읽는다. 읽기만 한다. 어떤 파일도 고치지 않는다. 파이썬 표준 라이브러리만 쓴다.
"""
import json
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent

HEAD = ["구성 요소", "센서", "재는 값", "부품"]
PART_FLAG = "--부품"
PART_HEAD = ["구성 요소", "설비"]
NONE = "-"
SEP = ", "


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def width(text):
    # 한글처럼 넓은 글자는 두 칸으로 센다
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in text)


def pad(text, n):
    return text + " " * (n - width(text))


def sensor_text(p):
    return f"{p['tag']} {p['name']}"


def variable_text(p):
    return f"{p['name']} ({p['unit']})" if p.get("unit") else p["name"]


def part_text(p):
    return f"{p['name']} ({p['part_no']})"


def cell(texts):
    return SEP.join(texts) if texts else NONE


def query(graph, code):
    """설비 코드 하나의 줄들과 센 수를 돌려준다. 그런 설비가 없으면 None."""
    node = {n["props"]["id"]: n for n in graph["nodes"]}
    label = {i: n["labels"][0] for i, n in node.items()}
    rels = graph["rels"]

    asset = next((i for i, n in node.items() if label[i] == "Asset" and n["props"].get("code") == code), None)
    if asset is None:
        return None

    def forward(start, rel_type):       # start 에서 나가는 관계의 끝들, 적힌 순서대로
        return [r["b"] for r in rels if r["type"] == rel_type and r["a"] == start]

    def backward(end, rel_type):        # end 로 들어오는 관계의 시작들, 적힌 순서대로
        return [r["a"] for r in rels if r["type"] == rel_type and r["b"] == end]

    rows, sensors_seen, parts_seen = [], set(), set()
    components = forward(asset, "HAS_COMPONENT")
    for comp in components:
        sensors = [s for s in backward(comp, "MOUNTED_ON") if label[s] == "Sensor"]
        variables = [v for s in sensors for v in forward(s, "MEASURES")]
        parts = forward(comp, "USES_PART")
        sensors_seen.update(sensors)
        parts_seen.update(parts)
        rows.append([
            node[comp]["props"]["name"],
            cell([sensor_text(node[s]["props"]) for s in sensors]),
            cell([variable_text(node[v]["props"]) for v in variables]),
            cell([part_text(node[p]["props"]) for p in parts]),
        ])
    return rows, len(components), len(sensors_seen), len(parts_seen)


def query_part(graph, part_no):
    """품번 하나의 줄들과 센 수를 돌려준다. 그런 부품이 없으면 None."""
    node = {n["props"]["id"]: n for n in graph["nodes"]}
    label = {i: n["labels"][0] for i, n in node.items()}
    rels = graph["rels"]

    part = next((i for i, n in node.items() if label[i] == "Part" and n["props"].get("part_no") == part_no), None)
    if part is None:
        return None

    def backward(end, rel_type):        # end 로 들어오는 관계의 시작들, 적힌 순서대로
        return [r["a"] for r in rels if r["type"] == rel_type and r["b"] == end]

    rows, assets_seen = [], set()
    components = backward(part, "USES_PART")
    for comp in components:
        assets = backward(comp, "HAS_COMPONENT")
        assets_seen.update(assets)
        rows.append([
            node[comp]["props"]["name"],
            cell([node[a]["props"]["code"] for a in assets]),
        ])
    return rows, len(components), len(assets_seen)


def table(head, rows):
    widths = [max(width(line[k]) for line in [head] + rows) for k in range(len(head))]
    print("| " + " | ".join(pad(h, w) for h, w in zip(head, widths)) + " |")
    print("|" + "|".join("-" * (w + 2) for w in widths) + "|")
    for row in rows:
        print("| " + " | ".join(pad(c, w) for c, w in zip(row, widths)) + " |")


def show(code, result):
    print(f"[{code}]")
    if result is None:
        print(f"그래프에 설비 코드가 {code} 인 설비가 없다.")
        return
    rows, n_comp, n_sensor, n_part = result
    table(HEAD, rows)
    print(f"구성 요소 {n_comp} · 센서 {n_sensor} · 부품 {n_part}")


def show_part(part_no, result):
    print(f"[{part_no}]")
    if result is None:
        print(f"그래프에 품번이 {part_no} 인 부품이 없다.")
        return
    rows, n_comp, n_asset = result
    table(PART_HEAD, rows)
    print(f"구성 요소 {n_comp} · 설비 {n_asset}")


def main():
    args = sys.argv[1:]
    by_part = bool(args) and args[0] == PART_FLAG
    keys = args[1:] if by_part else args
    if not keys:
        print("쓰는 법: python 결과/질의.py <설비 코드> [<설비 코드> ...]")
        print(f"        python 결과/질의.py {PART_FLAG} <품번> [<품번> ...]")
        return 2
    graph = load(HERE / "graph.json")
    for k, key in enumerate(keys):
        if k:
            print()
        if by_part:
            show_part(key, query_part(graph, key))
        else:
            show(key, query(graph, key))
    return 0


if __name__ == "__main__":
    sys.exit(main())
