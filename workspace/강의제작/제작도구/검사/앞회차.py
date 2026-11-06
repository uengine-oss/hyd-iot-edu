"""같은 반·같은 수업 방식의 앞 회차들을 이어받을 맥락만 찍고(--검사면 원고에서 이름 후보를 찾고), 읽기만 한다.
언제: 덱 · 대본 · 영상 · 코딩랩 · 가이드 일을 시작할 때(첫 조각 전 이름표) · 조각을 검토하거나 이름을 바꾼 뒤 — 앞 회차 덱을 통째로 읽지 않는다.
명령: <py> workspace/강의제작/제작도구/검사/앞회차.py <통합반|실전반> <NN> [--오프라인]
      <py> workspace/강의제작/제작도구/검사/앞회차.py <통합반|실전반> <NN> --검사 <덱.md · 이론 · 실습 대본 · START.md · AGENTS.md · 가이드 원고 · 가이드 HTML …>
      <py> workspace/강의제작/제작도구/검사/앞회차.py --자가시험
찍는 것: ① 사실표 「같은 말 · 같은 값」 장부에서 이 회차보다 앞에 처음 푼 이름과 모든 회차의 이름(쓰는 말 · 처음 푼 자리 · 쓰지 않을 말)
② 1~(NN-1)회차마다 실라버스 행(학생이 실제로 마친 활동)과 덱의 용어 정리 장 요소 ③ 바로 앞 회차의 학습목표 장 · 복습 장 화면 내용.
--검사: 장부의 「쓰지 않을 말」과, 앞 회차가 이미 정의한 이름을 다시 정의하는 꼴(「X은 …이다」 · 「X이란」 · 「X =」 · 굵게 쓴 **X** · 용어 정리 표의 「| X |」)을
파일:줄 후보로 내고, 줄 글은 걸린 자리 앞뒤만 보인다. HTML은 style · script를 빼고 화면 글만 읽는다(<b> · <strong>은 굵게, 문단 · 항목 · 칸 끝은 조각 경계).
판정은 사람이 그 줄을 읽어 한다(공통 C-7) — 후보 수와 상관없이 종료 0, 파일이 없거나 장부를 못 읽으면 종료 2.
실전반의 「앞」은 공통.md 「자료」 대응표에서 그 실전 회차가 받는 통합 회차 가운데 가장 앞 회차보다 앞이다. 오프라인은 같은 번호의 통합 회차 기준이다.
"""
import argparse
import html
import re
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
ROOT = TOOLS.parents[2]
LEDGER = ROOT / "workspace/강의제작/지침/사실표/통합반_01일차_기술사실표.md"
COMMON = ROOT / "workspace/강의제작/지침/공통.md"
DIR = {"통합반": "integrated", "실전반": "practical"}
SLIDE = re.compile(r"^## SLIDE (\d+) — (.*)$")
TERMS = "오늘 다룬 핵심 개념과 주요 용어 정리"
QUOTED = re.compile(r"「([^」]+)」")
FIRST = re.compile(r"통합 (\d+)회차")
DEFINES = r"(?:은|는|이란|란|이라는 것은|=)\s"
ENDS = re.compile(r"(?:이다|입니다|이에요|예요|뜻한다|뜻합니다|말한다|말합니다|가리킨다|가리킵니다)")
HIDDEN = re.compile(r"<(style|script)\b.*?</\1\s*>", re.S | re.I)
BOLD = re.compile(r"</?(?:b|strong)\s*>", re.I)
BREAK = re.compile(r"<br\s*/?>|</(?:p|li|h\d|td|th|tr|dt|dd|summary|div|pre|section|blockquote)\s*>", re.I)
TAG = re.compile(r"<[^>]*>")


def pieces(path):
    """[(줄 번호, 읽을 글)] — 원고는 줄 그대로, HTML은 화면 글만(줄 번호는 HTML 파일의 줄)."""
    text = Path(path).read_text(encoding="utf-8-sig")
    if Path(path).suffix.lower() not in (".html", ".htm"):
        return list(enumerate(text.splitlines(), 1))
    text = HIDDEN.sub(lambda m: "\n" * m[0].count("\n"), text)
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        for part in BREAK.split(BOLD.sub("**", line)):
            part = html.unescape(TAG.sub("", part)).strip()
            if part:
                out.append((i, part))
    return out


def excerpt(line, at, width=120):
    """걸린 자리(at)가 보이도록 앞 30자부터 width자."""
    start = max(0, at - 30)
    return ("…" if start else "") + line[start:start + width].strip()


def slides(p):
    """[(번호, 제목, 화면 내용 줄들)] — `### 화면 구성` 앞까지만."""
    out, cur, keep = [], None, False
    for line in p.read_text(encoding="utf-8").splitlines():
        m = SLIDE.match(line)
        if m:
            cur = [int(m[1]), m[2].strip(), [line]]
            out.append(cur)
            keep = True
        elif cur is not None:
            if line.startswith("### 화면 구성"):
                keep = False
            elif keep:
                cur[2].append(line)
    return out


def ledger(path=LEDGER):
    """장부 행: [{대상, 쓰는 말, 처음, 회차(None = 모든 회차), 이름들, 금지}] — 「같은 말」 절의 표에서."""
    text = path.read_text(encoding="utf-8")
    m = re.search(r"^## 같은 말.*?$(.*?)^## ", text, re.S | re.M)
    if not m:
        raise SystemExit(f"{path}: 「## 같은 말 · 같은 값」 절을 찾지 못함")
    head, rows = None, []
    for line in m[1].splitlines():
        if not line.startswith("|") or set(line) <= set("|-: "):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if head is None:
            head = cells
            need = ("대상", "쓰는 말", "처음 푼 자리", "쓰지 않을 말")
            if any(h not in head for h in need):
                raise SystemExit(f"{path}: 장부 머리에 {need} 칸이 다 있어야 한다 — {head}")
            continue
        row = dict(zip(head, cells))
        first = FIRST.search(row["처음 푼 자리"])
        names = [re.sub(r"\(.*?\)$", "", q).strip() for q in QUOTED.findall(row["쓰는 말"])]
        rows.append({"대상": row["대상"], "쓰는 말": row["쓰는 말"], "처음": row["처음 푼 자리"],
                     "회차": int(first[1]) if first else None,
                     "이름들": [n for n in names if n], "금지": QUOTED.findall(row["쓰지 않을 말"])})
    return rows


def first_integrated(course, n, common=COMMON):
    """이 회차가 받는 통합 회차 가운데 가장 앞 회차. 실전반은 공통.md 「자료」 대응표에서 읽는다."""
    if course == "통합반":
        return n
    for line in common.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 3 and cells[0] == str(n) and re.fullmatch(r"[\d, ]+", cells[1]):
            return min(int(x) for x in re.findall(r"\d+", cells[1]))
    raise SystemExit(f"{common}: 「자료」 대응표에서 실전 {n}회차의 통합 회차를 찾지 못함")


def check(files, rows, base):
    """[(파일, 줄, 종류, 말, 줄 글)] — 쓰지 않을 말, 그리고 base 회차보다 앞에 정의한 이름의 다시 정의 꼴."""
    banned = [(w, r["대상"]) for r in rows for w in r["금지"]]
    prior = [(n, r) for r in rows if r["회차"] and r["회차"] < base for n in r["이름들"]]
    redefine = [(n, r, re.compile(rf"\*\*{re.escape(n)}\*\*\(|(?<![가-힣]){re.escape(n)}(?:\([^)]*\))?\s*{DEFINES}"),
                 re.compile(rf"^\s*\d+\.\s*(?:\*\*)?{re.escape(n)}(\([A-Za-z][^)]*\))?(?:\*\*)?\s*\|")) for n, r in prior]
    out = []
    for f in files:
        title = ""   # 덱 원고면 지금 장 제목 — 이름으로 시작하는 표 줄은 용어 정리 장이거나 영문 이름을 함께 실은 줄만 다시 정의로 본다
        for i, line in pieces(f):
            m = SLIDE.match(line)
            if m:
                title = m[2].strip()
            for w, what in banned:
                if w in line:
                    out.append((f, i, "쓰지 않을 말", f"「{w}」({what})", excerpt(line, line.index(w))))
            for n, r, rx, row in redefine:
                hit = rx.search(line)
                cell = row.search(line)
                if (hit and (hit[0].startswith("**") or ENDS.search(line[hit.end():]))) or (
                        cell and (title == TERMS or cell[1] or re.search(r"\|\s*[A-Z][A-Za-z ·]+\s*$", line))):
                    out.append((f, i, "다시 정의", f"「{n}」({r['처음']})", excerpt(line, hit.start() if hit else 0)))
    return out


def context(course, n, offline):
    from openpyxl import load_workbook
    from 실라버스행 import XLSX, sessions
    mode = "오프라인" if offline else "온라인"
    if not XLSX.is_file():
        sys.exit(f"{XLSX}: 정본 실라버스가 없어 앞 회차의 활동을 확인할 수 없다")
    wb = load_workbook(XLSX, read_only=True, data_only=True)
    try:
        names = [name for name in wb.sheetnames if name.startswith(f"{course} {mode}")]
        if len(names) != 1:
            sys.exit(f"{XLSX.name}: {course} {mode} 시트를 하나로 확인할 수 없다")
        table = sessions(wb[names[0]])
    finally:
        wb.close()
    if not table.get(n):
        sys.exit(f"{course} {mode} {n:02d}회차: 실라버스에 이 회차가 없다")
    base = first_integrated(course, n)
    print(f"# 과정 용어 장부 — 통합 {base}회차보다 앞에 처음 푼 이름과 모든 회차의 이름(사실표 「같은 말 · 같은 값」)")
    for r in ledger():
        if r["회차"] is None or r["회차"] < base:
            ban = " · ".join(f"「{w}」" for w in r["금지"]) or "—"
            print(f"- {r['쓰는 말']} | {r['처음']} | 쓰지 않을 말 {ban}")
    if n == 1:
        print(f"\n{course} {mode} 01회차: 첫 회차로 앞 회차가 없다")
        return
    for prev in range(1, n):
        rows = table.get(prev) or []
        print(f"\n# {course} {mode} {prev:02d}회차 — 학생이 마친 활동")
        if not rows:
            print("실라버스 행 미확인")
            continue
        for kind, title, *_ in rows:
            print(f"- [{kind}] {title}")
        if not any(row[0].startswith("이론") for row in rows):
            print("이론 행이 없는 회차다. 위 활동의 가이드 · 실습 결과에서 학생이 어떤 상태를 넘기는지 확인한다.")
            continue
        day = f"{prev:02d}"
        sub = f"off{day}/{course}_오프라인_{day}회차.md" if offline else f"day{day}/{course}_{day}일차.md"
        p = TOOLS / mode / "decks" / DIR[course] / sub
        if not p.is_file():
            print(f"{p.relative_to(ROOT).as_posix()}: 이론 행이 있으나 덱 원고가 없다 — 그 회차의 덱 · 실습 인계를 확인할 때까지 미확인")
            continue
        all_ = slides(p)
        goal = [s for s in all_ if s[1] == "학습목표"]
        terms = [s for s in all_ if s[1] == TERMS]
        if len(goal) != 1 or len(terms) != 1:
            print(f"{p.relative_to(ROOT).as_posix()}: 학습목표 {len(goal)}장 · 용어 정리 {len(terms)}장 — 각 1장이어야 뽑는다(미확인)")
            continue
        print(f"원고 {p.relative_to(ROOT).as_posix()} · 용어 정리 SLIDE {terms[0][0]:02d}")
        print("\n".join(l for l in terms[0][2] if re.match(r"^\s+\d+\. ", l)))
        if prev != n - 1:
            continue
        i = all_.index(terms[0])
        if i == 0 or all_[i - 1][0] <= goal[0][0]:
            print("용어 정리 직전의 복습 자리를 확인할 수 없다(미확인)")
            continue
        print("\n## 바로 앞 회차의 학습목표 장과 복습 장(D-2가 정한 용어 정리 직전 장) — 제목과 실제 화면에서 내용을 확인한다")
        for _, _, body in (goal[0], all_[i - 1]):
            print("\n".join(body).rstrip() + "\n")


def selftest():
    """임시 장부 · 대응표 · 원고로 쓰지 않을 말과 다시 정의 꼴을 잡고, 받아 쓴 줄은 놓아두는지 본다."""
    import tempfile
    cases = []
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        led = d / "사실표.md"
        led.write_text("# 표\n\n## 같은 말 · 같은 값 — 모든 교재 공통\n\n설명\n\n| 대상 | 쓰는 말 | 처음 푼 자리 | 쓰지 않을 말 | 맞추는 법 |\n|---|---|---|---|---|\n"
                       "| 경계 | 「임계치(Threshold)」 | 통합 1회차 37장 | 「임계값」 | — |\n"
                       "| 질문 | 「역량 질문(Competency Question)」 | 통합 2회차 38장 | 「처음 질문」 | — |\n"
                       "| 결정 | 「추천안」 | 모든 회차 | 「조치 카드」 | — |\n\n## 0. 다음\n", encoding="utf-8")
        com = d / "공통.md"
        com.write_text("| 실전 온라인 회차 | 통합 온라인 회차 | 적용 범위 |\n|---|---|---|\n| 2 | 2, 3 | 앞 |\n| 3 | 3, 4 | 뒤 |\n", encoding="utf-8")
        rows = ledger(led)
        cases.append(("장부 세 행 · 모든 회차는 회차 없음", [r["회차"] for r in rows] == [1, 2, None] and rows[0]["이름들"] == ["임계치"], rows))
        cases.append(("실전 3회차는 통합 3회차부터 받는다", first_integrated("실전반", 3, com) == 3, ""))
        deck = d / "덱.md"
        deck.write_text("\n".join([
            "- 메시지: 임계값을 넘으면 경보가 뜬다.",                          # 1 쓰지 않을 말
            "- 노트: · 임계치는 판정을 가르는 경계값이다 / [다음] 비교",          # 2 다시 정의(1회차 이름)
            "- 메시지: **역량 질문**(Competency Question)은 설계의 출발점이다.",  # 3 다시 정의(굵게 + 영문)
            "- 노트: · 임계치를 넘은 값으로 원인을 가린다",                      # 4 받아 씀 — 후보 아님
            "- 메시지: 앞에서 정한 역량 질문에 답하는 쿼리를 쓴다.",              # 5 받아 씀 — 후보 아님
            "- 노트: · 조치 카드가 곧 추천안",                                  # 6 쓰지 않을 말(모든 회차)
            "- 노트: · 임계치(Threshold) = 경계값이에요",                        # 7 다시 정의(= 꼴)
            "  2. 임계치 | 55 ℃ | 본문 표의 한 줄",                              # 8 용어 정리 장 밖의 표 줄 — 후보 아님
            "- 메시지: 값을 **역량 질문**으로 묶는다.",                          # 9 영문 괄호 없는 굵게는 강조 — 후보 아님
            "  3. 임계치 | 판정을 가르는 경계값 | Threshold",                     # 10 영문 이름을 함께 실은 표 줄 — 다시 정의
            "## SLIDE 70 — 오늘 다룬 핵심 개념과 주요 용어 정리",                # 11
            "  1. 역량 질문 | Competency Question / 온톨로지가 답할 질문",        # 12 용어 정리 장의 표 줄 — 다시 정의
        ]) + "\n", encoding="utf-8")
        got = {(i, kind) for _, i, kind, *_ in check([deck], rows, 3)}
        want = {(1, "쓰지 않을 말"), (2, "다시 정의"), (3, "다시 정의"), (6, "쓰지 않을 말"), (7, "다시 정의"), (10, "다시 정의"), (12, "다시 정의")}
        cases.append(("깨뜨린 줄은 모두 잡고 받아 쓴 줄은 놓아둔다", got == want, sorted(got ^ want)))
        early = {(i, kind) for _, i, kind, *_ in check([deck], rows, 2)}
        cases.append(("2회차 기준이면 2회차 이름(역량 질문)의 정의는 후보가 아니다", (3, "다시 정의") not in early and (2, "다시 정의") in early, sorted(early)))
        lab = d / "START.md"   # 실습 쪽 원고: BOM 붙은 START.md와 실습 대본 표 줄
        lab.write_text("﻿# 목표\n"
                       "앞에서 만든 조치 카드를 받아 엽니다.\n"                            # 2 쓰지 않을 말
                       "| 임계치는 판정을 가르는 경계값입니다. | 표를 짚는다 |\n"             # 3 다시 정의(대본 표의 발화 칸)
                       "| 임계치를 넘은 행을 고릅니다. | 클릭 |\n", encoding="utf-8")       # 4 받아 씀 — 후보 아님
        got = {(i, kind) for _, i, kind, *_ in check([lab], rows, 3)}
        want = {(2, "쓰지 않을 말"), (3, "다시 정의")}
        cases.append(("START.md · 실습 대본 표 줄을 읽는다", got == want, sorted(got ^ want)))
        page = d / "guide.html"   # 한 줄에 여러 문단이 붙은 가이드 HTML
        page.write_text('<!doctype html><style>.x::after{content:"임계값"}</style><main><p>머리 '
                        + "가" * 300 + '</p><p><b>역량 질문</b>(Competency Question)은 출발점입니다.</p>'
                        '<p>앞에서 정한 역량 질문으로 엽니다. 임계치는 이 절에서 쓰지 않습니다.</p></main>\n'
                        '<li>값이 &lt;55&gt;이면 임계&#xAC12;입니다</li>\n'
                        '<script>const s = "조치 카드";</script>\n', encoding="utf-8")
        found = check([page], rows, 3)
        got = {(i, kind) for _, i, kind, *_ in found}
        want = {(1, "다시 정의"), (2, "쓰지 않을 말")}
        shown = all(w in line for *_, what, line in found for w in re.findall(r"「([^」]+)」", what)[:1])
        cases.append(("HTML은 화면 글만 읽고 style · script는 놓아둔다", got == want, sorted(got ^ want)))
        cases.append(("긴 줄도 걸린 낱말이 보이게 잘라 보인다", shown, found))
    for name, ok, detail in cases:
        print(f"{'통과' if ok else '실패'}: {name}" + ("" if ok else f" — {detail}"))
    bad = sum(not c[1] for c in cases)
    print(f"자가시험 {len(cases)}건 · 실패 {bad}")
    return bad == 0


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
    if argv[1:] == ["--자가시험"]:
        return 0 if selftest() else 1
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("과정", choices=DIR)
    ap.add_argument("회차", type=int)
    ap.add_argument("--오프라인", action="store_true")
    ap.add_argument("--검사", nargs="+", metavar="파일")
    args = ap.parse_args(argv[1:])
    if args.검사:
        missing = [f for f in args.검사 if not Path(f).is_file()]
        if missing:
            print(f"파일 없음: {' · '.join(missing)}", file=sys.stderr)
            return 2
        base = first_integrated(args.과정, args.회차)
        found = check(args.검사, ledger(), base)
        for f, i, kind, what, line in found:
            print(f"{f}:{i}: {kind} {what} — {line}")
        print(f"앞회차 --검사: 통합 {base}회차 기준 · 파일 {len(args.검사)}개 · 후보 {len(found)}(줄을 읽어 가른다)")
        return 0
    context(args.과정, args.회차, args.오프라인)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
