"""교재 지침 일곱(공통.md + 산출물 문서 여섯)의 구조 검사: `## 반드시` 첫 절(많아야 12줄) · 절 순서, 인수 조건 빈 칸,
내용 없이 가리키는 행, 없는 인수 조건을 가리키는 ID, 두 문서에 글자까지 같은 인수 조건, 문서 안 같은 줄, 스킬이 인수 조건을 다시 적음,
공통.md 절의 `(대상: …)` 표시(꼴 · 문서 이름 오타), 그 일이 읽지 않는 공통 절을 가리키는 ID, 공통.md 머리의 자리 표가 표시와 같은지.

사용:
  python 재편검사.py            # 저장소의 workspace/강의제작/지침/<일곱>.md 검사
  python 재편검사.py --자가시험   # 일부러 깨뜨린 사본으로 각 검사가 잡는지 확인
오류가 하나라도 있으면 종료 코드 1, 위치는 파일:줄. 인수 조건 표는 인수검사.py와 같은 파서로 읽는다.
"""
import re
import shutil
import sys
import tempfile
from pathlib import Path

from 인수검사 import TABLE_SEP, WORKS, acceptance_rows, common_blocks

ROOT = Path(__file__).resolve().parents[4]
DOCS = ["공통", "실라버스", "덱", "대본", "영상", "코딩랩", "가이드"]
LETTER = {"공통": "C", "실라버스": "L", "덱": "D", "대본": "S", "영상": "V", "코딩랩": "K", "가이드": "P"}
MUST = "반드시 — 어기면 불통과"
MUST_LINES = 12
SECTIONS = ["목적 · 가치 · 배경", "작업 컨텍스트", "작업 요령", "인수 조건"]
SKILLS = ["hyd-syllabus", "hyd-course-deck", "hyd-script", "hyd-video", "hyd-coding-lab", "hyd-lab-guide"]
ROW_REF = re.compile(r"(?<![A-Za-z0-9_\-:])[CDKLPSV]-\d+(?![0-9A-Za-z\-])")     # `P-PMP-SEAL` · `HM-8.1` · `rule:x-1`은 인수 조건 ID가 아니다
ID_LEAD = re.compile(r"[A-Z]-\d+(?:\s*[·,~]\s*[A-Z]-\d+)*\s*(?:[와과]\s*같다|[와과]\s*같음|[와과]\s*같은\s*판정|[을를]\s*따른다|[을를]\s*본다|(?:으로|로)\s*판정|참조|그대로)")
POINTER_LEN = 40     # 「X와 같은 판정」 뒤에 제 내용을 적으면 이 길이를 넘는다
COMMON_REF = re.compile(r"(?<![A-Za-z0-9_\-:])C(?:맥|요|목)?-\d+(?![0-9A-Za-z\-])")
COMMON_ID = re.compile(r"\*\*(C[맥요목]-\d+)\*\*|\|\s*(C-\d+)\s*\|")
TARGET_FORM = re.compile(r"\(대상: ([^()]+)\)$")
SEAT_HEAD = "읽을 표시 절 — "


def read(p):
    return p.read_text(encoding="utf-8").splitlines()


def check_sections(doc_dir, errs):
    for d in DOCS:
        p = doc_dir / f"{d}.md"
        if not p.exists():
            errs.append(f"{p}: 문서 없음")
            continue
        lines = read(p)
        heads = [(i, l[3:].strip()) for i, l in enumerate(lines) if l.startswith("## ")]
        names = [n for _, n in heads]
        if not names or names[0] != MUST:
            errs.append(f"{p}: 첫 절이 「## {MUST}」가 아님 — 첫 절 {names[:1]}")
        if MUST in names:
            at = names.index(MUST)
            start, end = heads[at][0] + 1, heads[at + 1][0] if at + 1 < len(heads) else len(lines)
            filled = sum(1 for l in lines[start:end] if l.strip() and not l.startswith("#"))   # `### 이론 영상` 같은 소제목은 규칙 문장이 아니다
            if filled > MUST_LINES:
                errs.append(f"{p}:{start}: 「{MUST}」 절이 {filled}줄 — 많아야 {MUST_LINES}줄")
        pos = []
        for s in SECTIONS:
            if s not in names:
                errs.append(f"{p}: 절 「{s}」 없음")
            else:
                pos.append(names.index(s))
        if pos != sorted(pos):
            errs.append(f"{p}: 절 순서가 {SECTIONS}가 아님 — {names}")


def check_acceptance(doc_dir, errs):
    for d in DOCS:
        p = doc_dir / f"{d}.md"
        if not p.exists():
            continue
        rows = acceptance_rows(p)
        if not rows:
            errs.append(f"{p}: 인수 조건 표 행 0")
        for ln, cells in rows:
            if len(cells) < 3:
                errs.append(f"{p}:{ln}: 인수 조건 행의 칸이 3 미만")
            elif not cells[0] or not cells[1] or not cells[2]:
                errs.append(f"{p}:{ln}: 인수 조건 행에 빈 칸(번호 · 통과 기준 · 확인 방법)")


def is_pointer(cell):
    """통과 기준 칸에 제 내용이 없고 다른 행을 가리키기만 하는가(「X와 같은 판정」)."""
    bare = re.sub(r"\([^)]*\)", "", cell).strip()
    return ("같은 판정" in bare and len(bare) <= POINTER_LEN) or (ID_LEAD.match(bare) is not None and len(bare) <= POINTER_LEN)


def check_pointers(doc_dir, errs):
    for d in DOCS:
        p = doc_dir / f"{d}.md"
        if p.exists():
            for ln, cells in acceptance_rows(p):
                if len(cells) > 1 and is_pointer(cells[1]):
                    errs.append(f"{p}:{ln}: {cells[0]} 내용 없이 가리키기만 하는 행 — 「{cells[1][:40]}」")


def check_refs(doc_dir, errs):
    """문서 안 · 문서 사이에서 가리키는 인수 조건 ID가 지금 그 문서의 표에 있는가. 지운 번호를 가리키면 오류다."""
    known = {c[0] for d in DOCS if (doc_dir / f"{d}.md").exists() for _, c in acceptance_rows(doc_dir / f"{d}.md")}
    for d in DOCS:
        p = doc_dir / f"{d}.md"
        if p.exists():
            for i, l in enumerate(read(p), 1):
                for ref in ROW_REF.findall(l):
                    if ref not in known:
                        errs.append(f"{p}:{i}: 없는 인수 조건 {ref}를 가리킴")


def check_same_rows(doc_dir, errs):
    """두 문서에 글자까지 같은 통과 기준. 한쪽을 지우거나 공통.md로 모은다."""
    seen = {}
    for d in DOCS:
        p = doc_dir / f"{d}.md"
        if p.exists():
            for ln, cells in acceptance_rows(p):
                if len(cells) > 1 and cells[1]:
                    seen.setdefault(cells[1], []).append((d, ln, cells[0]))
    for crit, where in seen.items():
        if len({d for d, _, _ in where}) > 1:
            errs.append(f"두 문서에 같은 인수 조건: " + " · ".join(f"{d}.md:{ln} {i}" for d, ln, i in where) + f" — 「{crit[:40]}」")


def check_dup_lines(doc_dir, errs):
    """한 문서 안 같은 줄 두 번(10자 이상, 제목 · 표 머리 · 구분선 제외)."""
    for d in DOCS:
        p = doc_dir / f"{d}.md"
        if not p.exists():
            continue
        seen, lines = {}, read(p)
        for i, l in enumerate(lines, 1):
            s = l.strip()
            header = s.startswith("|") and i < len(lines) and TABLE_SEP.match(lines[i].strip())
            if len(s) < 10 or header or TABLE_SEP.match(s) or s.startswith("#"):
                continue
            if s in seen:
                errs.append(f"{p}:{i}: 같은 줄이 {seen[s]}째 줄에도 있음")
            else:
                seen[s] = i


def check_skills(doc_dir, skill_dir, errs):
    crit = set()
    for d in DOCS:
        p = doc_dir / f"{d}.md"
        if p.exists():
            crit |= {c[1] for _, c in acceptance_rows(p) if len(c) > 1 and len(c[1]) >= 15}
    for s in SKILLS:
        p = skill_dir / s / "SKILL.md"
        if not p.exists():
            errs.append(f"{p}: 스킬 없음")
            continue
        text = p.read_text(encoding="utf-8")
        for c in crit:
            if c in text:
                errs.append(f"{p}: 인수 조건 문장을 다시 적음 — 「{c[:40]}…」")


def check_targets(doc_dir, errs):
    """`(대상: …)` 표시는 공통.md의 `### ` 제목에만, 꼴 그대로, 문서 이름으로, 일부 일만 적는다(여섯 다면 표시가 없는 것과 같다)."""
    for d in DOCS:
        p = doc_dir / f"{d}.md"
        if not p.exists():
            continue
        for i, l in enumerate(read(p), 1):
            if not l.startswith("#") or not ("(대상" in l or "대상:" in l):
                continue
            if d != "공통" or not l.startswith("### "):
                errs.append(f"{p}:{i}: 대상 표시는 공통.md의 `### ` 제목에만 — 「{l[:60]}」")
                continue
            form = TARGET_FORM.search(l.rstrip())
            if not form:
                errs.append(f"{p}:{i}: 대상 표시 꼴이 `(대상: 코딩랩 · 가이드)`가 아님 — 「{l[:60]}」")
                continue
            names = form[1].split(" · ")
            for name in names:
                if name not in WORKS:
                    errs.append(f"{p}:{i}: 대상 「{name}」이 문서 이름이 아님 — {' · '.join(WORKS)}")
            if set(names) >= set(WORKS):
                errs.append(f"{p}:{i}: 대상이 여섯 다다 — 표시를 뺀다")
            if len(names) != len(set(names)):
                errs.append(f"{p}:{i}: 대상 이름이 겹침")


def common_places(p):
    """공통.md의 ID마다 (대상, 절 제목). 대상 None이면 모든 일."""
    lines, places = read(p), {}
    for start, end, title, targets in common_blocks(p):
        for l in lines[start - 1:end]:
            found = COMMON_ID.match(l)
            if found:
                places[found[1] or found[2]] = (targets, title)
    return places


def check_target_refs(doc_dir, errs):
    """지침이 그 일이 읽지 않는 공통 절을 가리키면 기준이 빠진 것이다. 공통.md 안에서도 넓은 절이 좁은 절을 가리키면 못 읽는 일이 생긴다(`## 반드시`는 요약이라 뺀다)."""
    p = doc_dir / "공통.md"
    if not p.exists():
        return
    places = common_places(p)
    for d in DOCS[1:]:
        q = doc_dir / f"{d}.md"
        if not q.exists():
            continue
        for i, l in enumerate(read(q), 1):
            for ref in COMMON_REF.findall(l):
                if ref not in places:
                    if not ROW_REF.fullmatch(ref):      # C-n은 check_refs가 본다
                        errs.append(f"{q}:{i}: 공통.md에 없는 {ref}를 가리킴")
                elif places[ref][0] is not None and d not in places[ref][0]:
                    errs.append(f"{q}:{i}: {ref}는 공통 절 「{places[ref][1]}」(대상: {' · '.join(places[ref][0])})에 있어 {d} 일이 읽지 않는다 — 대상을 넓히거나 가리키는 말을 고친다")
    lines = read(p)
    for start, end, title, targets in common_blocks(p):
        if title == MUST:
            continue
        for i, l in enumerate(lines[start - 1:end], start):
            for ref in COMMON_REF.findall(l):
                if ref not in places:
                    if not ROW_REF.fullmatch(ref):
                        errs.append(f"{p}:{i}: 공통.md에 없는 {ref}를 가리킴")
                    continue
                theirs = places[ref][0]
                if theirs is not None and not set(targets or WORKS) <= set(theirs):
                    errs.append(f"{p}:{i}: 절 「{title}」을 읽는 일 중 {ref}의 절 「{places[ref][1]}」을 안 읽는 일이 있다 — {sorted(set(targets or WORKS) - set(theirs))}")


def check_seats(doc_dir, errs):
    """공통.md 머리의 자리 표(`읽을 표시 절 — 실라버스: 「절」 … / 덱: …`)가 제목의 대상 표시와 같다."""
    p = doc_dir / "공통.md"
    if not p.exists():
        return
    lines = read(p)
    seats = [(i, l) for i, l in enumerate(lines, 1) if l.startswith(SEAT_HEAD)]
    blocks = common_blocks(p)
    if not any(b[3] for b in blocks):
        return
    if len(seats) != 1:
        errs.append(f"{p}: 머리의 자리 표(「{SEAT_HEAD}…」 한 줄)가 {len(seats)}개")
        return
    at, line = seats[0]
    listed = {}
    for part in line[len(SEAT_HEAD):].split(" / "):
        work, _, rest = part.partition(":")
        listed[work.strip()] = re.findall(r"「([^」]+)」", rest)
    for work in WORKS:
        want = [b[2] for b in blocks if b[3] and work in b[3]]
        if listed.get(work) != want:
            errs.append(f"{p}:{at}: 자리 표의 「{work}」 칸이 제목의 대상 표시와 다름 — 적힌 것 {listed.get(work)}, 표시 {want}")


def run(doc_dir, skill_dir):
    errs = []
    check_sections(doc_dir, errs)
    check_acceptance(doc_dir, errs)
    check_pointers(doc_dir, errs)
    check_refs(doc_dir, errs)
    check_same_rows(doc_dir, errs)
    check_dup_lines(doc_dir, errs)
    check_skills(doc_dir, skill_dir, errs)
    check_targets(doc_dir, errs)
    check_target_refs(doc_dir, errs)
    check_seats(doc_dir, errs)
    return errs


def selftest():
    """정상 사본 하나를 만들어 통과를 보고, 하나씩 깨뜨려 기대한 오류로 잡히는지 본다."""
    tmp = Path(tempfile.mkdtemp())
    docs, skills = tmp / "docs", tmp / "skills"
    docs.mkdir()
    letter = LETTER
    for d in DOCS:
        (docs / f"{d}.md").write_text(
            f"# {d}\n\n## {MUST}\n\n1. {d}에서 어기면 불통과인 것({letter[d]}-1, C-1).\n\n"
            f"## 목적 · 가치 · 배경\n{letter[d]}목-1 {d}의 목적 문장 하나.\n\n## 작업 컨텍스트\n{d} 컨텍스트 문장.\n\n"
            f"## 작업 요령\n{letter[d]}요-1 {d} 요령 문장.\n\n## 인수 조건\n\n### 범위\n\n"
            f"| 번호 | 통과 기준 | 확인 방법 |\n|---|---|---|\n| {letter[d]}-1 | {d}만의 결과 조건 문장입니다 | 열어서 봄 |\n"
            f"| {letter[d]}-2 | {d}의 둘째 조건 — 값은 `P-PMP-SEAL`처럼 뜻으로 읽고 C-1과 함께 판정한다 | {letter[d]}-1과 같은 방법 |\n",
            encoding="utf-8")
    common = docs / "공통.md"
    common.write_text(common.read_text(encoding="utf-8")
                      .replace("# 공통\n", "# 공통\n\n" + SEAT_HEAD + "실라버스: 없음 / 덱: 「회 표」 / 대본: 「회 표」 / 영상: 없음 / 코딩랩: 없음 / 가이드: 없음\n")
                      .replace("C목-1 공통", "**C목-1** 공통").replace("C요-1 공통", "**C요-1** 공통")
                      .replace("공통 컨텍스트 문장.", "공통 컨텍스트 문장.\n\n### 회 표 (대상: 덱 · 대본)\n\n**C맥-1** 회 표 문장.\n\n### 근거\n\n**C맥-2** 근거 문장."), encoding="utf-8")
    (docs / "덱.md").write_text((docs / "덱.md").read_text(encoding="utf-8").replace("덱 컨텍스트 문장.", "덱 컨텍스트 문장(C맥-1)."), encoding="utf-8")
    for s in SKILLS:
        (skills / s).mkdir(parents=True)
        (skills / s / "SKILL.md").write_text("문서를 연다.\n", encoding="utf-8")

    def go():
        return run(docs, skills)

    cases = []
    base = go()
    cases.append(("정상 사본 통과", not base, base))

    def mutate(name, f, expect):
        saved = {p: p.read_text(encoding="utf-8") for p in list(docs.glob("*.md")) + list(skills.glob("*/SKILL.md"))}
        f()
        e = go()
        hit = [x for x in e if expect in x]
        cases.append((name, bool(hit), hit[:1] or e[:2]))
        for p, t in saved.items():
            p.write_text(t, encoding="utf-8")

    def p(d):
        return docs / f"{d}.md"

    def sub(d, a, b):
        return lambda: p(d).write_text(p(d).read_text(encoding="utf-8").replace(a, b), encoding="utf-8")

    def swap_sections():
        t = p("가이드").read_text(encoding="utf-8")
        t = t.replace("## 작업 컨텍스트", "## 임시").replace("## 작업 요령", "## 작업 컨텍스트").replace("## 임시", "## 작업 요령")
        p("가이드").write_text(t, encoding="utf-8")

    def many_must():
        lines = "".join(f"{n}. 어기면 불통과인 것 {n}.\n" for n in range(2, MUST_LINES + 2))   # 있던 1줄과 합쳐 13줄
        p("영상").write_text(p("영상").read_text(encoding="utf-8").replace("## 목적 · 가치 · 배경", lines + "\n## 목적 · 가치 · 배경"), encoding="utf-8")

    def move_must():
        t = p("대본").read_text(encoding="utf-8")
        head, rest = t.split(f"## {MUST}\n")
        body, tail = rest.split("## 목적 · 가치 · 배경\n", 1)
        p("대본").write_text(f"{head}## 목적 · 가치 · 배경\n대본 목적.\n\n## {MUST}\n{body}" + tail, encoding="utf-8")

    def row(d, cell):
        return sub(d, f"| {LETTER[d]}-2 | {d}의 둘째 조건 — 값은 `P-PMP-SEAL`처럼 뜻으로 읽고 C-1과 함께 판정한다 |", f"| {LETTER[d]}-2 | {cell} |")

    mutate("공통.md 빠짐", lambda: p("공통").unlink(), "공통.md: 문서 없음")
    mutate("반드시 절 빠짐", sub("덱", f"## {MUST}", "## 첫머리"), f"첫 절이 「## {MUST}」가 아님")
    mutate("반드시 절이 첫 절이 아님", move_must, f"첫 절이 「## {MUST}」가 아님")
    mutate("반드시 절 13줄", many_must, "많아야 12줄")

    def must_with_subheads():
        lines = "### 모든 영상\n\n" + "".join(f"{n}. 어기면 불통과인 것 {n}.\n" for n in range(2, MUST_LINES + 1)) + "\n### 이론 영상\n\n"
        p("영상").write_text(p("영상").read_text(encoding="utf-8").replace("## 목적 · 가치 · 배경", lines + "## 목적 · 가치 · 배경"), encoding="utf-8")
        saved_errs = go()
        if not saved_errs:      # 소제목을 뺀 12줄은 통과해야 한다 — 통과했을 때만 한 줄 더해 잡히는지 본다
            p("영상").write_text(p("영상").read_text(encoding="utf-8").replace("### 이론 영상\n\n", "### 이론 영상\n\n13. 어기면 불통과인 것 13.\n"), encoding="utf-8")

    mutate("소제목 뺀 12줄은 통과, 13줄은 잡음", must_with_subheads, "절이 13줄")
    mutate("공통.md에 반드시 절 빠짐", sub("공통", f"## {MUST}", "## 첫머리"), f"첫 절이 「## {MUST}」가 아님")
    mutate("가리키기만 하는 행(같은 판정)", row("덱", "D-1과 같은 판정이다"), "가리키기만 하는 행")
    mutate("가리키기만 하는 행(꼬리 괄호)", row("대본", "S-1과 같은 판정이다(고친 사실로 다시 판정한다)"), "가리키기만 하는 행")
    mutate("가리키기만 하는 행(따른다)", row("가이드", "P-1을 따른다"), "가리키기만 하는 행")
    mutate("없는 인수 조건을 가리킴(같은 문서)", sub("코딩랩", "K요-1 코딩랩 요령 문장.", "K요-1 코딩랩 요령 문장(K-99)."), "없는 인수 조건 K-99")
    mutate("없는 인수 조건을 가리킴(다른 문서)", sub("영상", "영상 컨텍스트 문장.", "영상 컨텍스트 문장(C-99)."), "없는 인수 조건 C-99")
    mutate("지운 행을 다른 문서가 가리킴", sub("공통", "| C-1 | 공통만의 결과 조건 문장입니다 | 열어서 봄 |\n", ""), "없는 인수 조건 C-1")
    mutate("두 문서에 같은 인수 조건", sub("실라버스", "실라버스만의 결과 조건 문장입니다", "덱만의 결과 조건 문장입니다"), "두 문서에 같은 인수 조건")
    mutate("확인 방법 빈 칸", sub("덱", "| 열어서 봄 |", "|  |"), "빈 칸")
    mutate("절 빠짐", sub("대본", "## 작업 요령", "## 요령"), "절 「작업 요령」 없음")
    mutate("절 순서 뒤집힘", swap_sections, "절 순서")
    mutate("한 문서 안 같은 줄 두 번", sub("코딩랩", "K요-1 코딩랩 요령 문장.", "K요-1 코딩랩 요령 문장이 두 번 들어간 줄\nK요-1 코딩랩 요령 문장이 두 번 들어간 줄"), "같은 줄이")
    mutate("스킬이 인수 조건을 다시 적음", lambda: (skills / "hyd-video" / "SKILL.md").write_text("영상만의 결과 조건 문장입니다\n", encoding="utf-8"), "다시 적음")
    mutate("대상 이름 오타", sub("공통", "(대상: 덱 · 대본)", "(대상: 덱 · 코딩 랩)"), "대상 「코딩 랩」이 문서 이름이 아님")
    mutate("대상 표시 꼴이 틀림", sub("공통", "(대상: 덱 · 대본)", "(대상 덱 · 대본)"), "대상 표시 꼴이")
    mutate("대상을 쉼표로 적음", sub("공통", "(대상: 덱 · 대본)", "(대상: 덱, 대본)"), "대상 「덱, 대본」이 문서 이름이 아님")
    mutate("대상이 여섯 다", sub("공통", "(대상: 덱 · 대본)", "(대상: 실라버스 · 덱 · 대본 · 영상 · 코딩랩 · 가이드)"), "대상이 여섯 다다")
    mutate("공통.md 밖의 대상 표시", sub("가이드", "### 범위", "### 범위 (대상: 가이드)"), "공통.md의 `### ` 제목에만")
    mutate("`## ` 제목의 대상 표시", sub("공통", "## 작업 요령", "## 작업 요령 (대상: 덱)"), "공통.md의 `### ` 제목에만")
    mutate("지침이 읽지 않는 공통 절을 가리킴", sub("가이드", "가이드 컨텍스트 문장.", "가이드 컨텍스트 문장(C맥-1)."), "가이드 일이 읽지 않는다")
    mutate("공통.md에 없는 번호를 가리킴", sub("가이드", "가이드 컨텍스트 문장.", "가이드 컨텍스트 문장(C맥-9)."), "공통.md에 없는 C맥-9")
    mutate("넓은 절이 좁은 절을 가리킴", sub("공통", "**C맥-2** 근거 문장.", "**C맥-2** 근거 문장(C맥-1)."), "안 읽는 일이 있다")
    mutate("자리 표가 표시와 다름", sub("공통", "덱: 「회 표」", "덱: 없음"), "자리 표의 「덱」 칸이")
    mutate("자리 표 없음", sub("공통", SEAT_HEAD, "읽을 절 "), "자리 표")
    shutil.rmtree(tmp)
    ok = True
    for name, caught, detail in cases:
        print(f"{'통과' if caught else '실패'}: {name} — {detail if detail else ''}")
        ok &= caught
    return ok


if __name__ == "__main__":
    if "--자가시험" in sys.argv:
        sys.exit(0 if selftest() else 1)
    errs = run(ROOT / "workspace" / "강의제작" / "지침", ROOT / ".claude" / "skills")
    for e in errs:
        print(e)
    print(f"오류 {len(errs)}")
    sys.exit(1 if errs else 0)
