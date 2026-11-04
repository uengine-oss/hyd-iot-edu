"""온라인 덱 원고와 분할 대본을 장별로 묶어 되풀이 · 순서 점검의 입력을 만든다(원고는 고치지 않는다).
언제: 사용자가 회차 일괄 순서 · 되풀이 점검을 시킬 때만, `의뢰/의뢰_순서되풀이점검.md`로 점검자를 띄우기 전(평소 검토는 hyd-task 3-3). 장 번호가 어긋나면 멈춘다.
명령: <py> workspace/강의제작/제작도구/검사/장묶기.py <통합반|실전반> <NN> <출력.md>

장마다: 덱 제목 · 화면 내용(유형 · 메시지 · 머리 · 요소 등) · 노트 · 화면 구성 · 대본 낭독(파일:줄). 제작 기준은 뺀다. 대본의 > 줄 · 표 · 제목은 낭독이 아니라 뺀다(대기 표시는 남긴다).
"""
import glob, os, re, sys

G = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))   # workspace/강의제작
DECK_DIR = {"통합반": "integrated", "실전반": "practical"}


def read_deck(course, nn):
    path = os.path.join(G, "제작도구/온라인/decks", DECK_DIR[course], f"day{nn}", f"{course}_{nn}일차.md")
    slides, cur, sec = {}, None, None
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        m = re.match(r"^## SLIDE (\d+) — (.*)$", line)
        if m:
            cur = int(m.group(1))
            slides[cur] = {"title": m.group(2), "screen": [], "note": "", "layout": []}
            sec = None
            continue
        if cur is None:
            continue
        if line.startswith("### "):
            sec = line[4:].strip()
            continue
        if sec == "화면 내용":
            if line.startswith("- 노트:"):
                slides[cur]["note"] = line[len("- 노트:"):].strip()
            elif line.strip():
                slides[cur]["screen"].append(line)
        elif sec == "화면 구성" and line.strip():
            slides[cur]["layout"].append(line)
    return path, slides


def read_scripts(course, nn):
    d = os.path.join(G, f"산출물/{course}/이론/{nn}회차/대본")
    blocks = []
    for path in sorted(glob.glob(os.path.join(d, "*.md"))):
        rel = os.path.basename(path)
        cur = None
        for i, line in enumerate(open(path, encoding="utf-8"), 1):
            line = line.rstrip("\n")
            m = re.match(r"^## \[SLIDE (\d+)(?:~(\d+))?\]", line)
            if m:
                cur = {"a": int(m.group(1)), "b": int(m.group(2) or m.group(1)), "file": rel, "lines": []}
                blocks.append(cur)
                continue
            if line.startswith("#"):
                cur = None
                continue
            if cur is None or not line.strip() or line.strip() == "---":
                continue
            if line.startswith("> [대기"):
                cur["lines"].append((i, line))
            elif not line.startswith(">") and not line.startswith("|"):
                cur["lines"].append((i, line))
    return blocks


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    course, nn, out = sys.argv[1:4]
    deck_path, slides = read_deck(course, nn)
    blocks = read_scripts(course, nn)
    covered = sorted(n for b in blocks for n in range(b["a"], b["b"] + 1))
    if covered != sorted(slides):
        sys.exit(f"{course} {nn}: 대본이 덮는 장과 덱 장이 다르다 — 대본만 {sorted(set(covered) - set(slides))}, 덱만 {sorted(set(slides) - set(covered))}, 두 번 {sorted(n for n in set(covered) if covered.count(n) > 1)}")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# 점검 입력 — {course} {nn}회차\n\n덱: 제작도구/온라인/decks/{DECK_DIR[course]}/day{nn}/{os.path.basename(deck_path)}\n대본: 산출물/{course}/이론/{nn}회차/대본/\n\n")
        for b in blocks:
            f.write(f"\n=====\n# 장 {b['a']}" + (f"~{b['b']}" if b["b"] != b["a"] else "") + f" · {b['file']}\n")
            for n in range(b["a"], b["b"] + 1):
                s = slides[n]
                f.write(f"\n[덱 {n}] {s['title']}\n" + "\n".join(s["screen"]) + "\n")
                f.write("화면 구성: " + " ".join(s["layout"]) + "\n")
                f.write("노트: " + s["note"] + "\n")
            f.write("\n[낭독]\n")
            for i, line in b["lines"]:
                f.write(f"L{i}: {line}\n")
    print(course, nn, "장", len(slides), "구획", len(blocks), "크기", os.path.getsize(out))


if __name__ == "__main__":
    main()
