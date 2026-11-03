"""교재 산출물 문서 여섯의 구조 검사: 절 · 순서, 인수 조건 빈 칸, 문서 안 같은 줄, 스킬이 인수 조건을 다시 적음.

사용:
  python 재편검사.py            # 저장소의 workspace/강의제작/지침/<여섯>.md 검사
  python 재편검사.py --자가시험   # 일부러 깨뜨린 사본으로 각 검사가 잡는지 확인
오류가 하나라도 있으면 종료 코드 1, 위치는 파일:줄. 인수 조건 표는 인수검사.py와 같은 파서로 읽는다.
"""
import shutil
import sys
import tempfile
from pathlib import Path

from 인수검사 import TABLE_SEP, acceptance_rows

ROOT = Path(__file__).resolve().parents[4]
DOCS = ["실라버스", "덱", "대본", "영상", "코딩랩", "가이드"]
SECTIONS = ["목적 · 가치 · 배경", "작업 컨텍스트", "작업 요령", "인수 조건"]
SKILLS = ["hyd-syllabus", "hyd-course-deck", "hyd-script", "hyd-video", "hyd-coding-lab", "hyd-lab-guide"]


def read(p):
    return p.read_text(encoding="utf-8").splitlines()


def check_sections(doc_dir, errs):
    for d in DOCS:
        p = doc_dir / f"{d}.md"
        if not p.exists():
            errs.append(f"{p}: 문서 없음")
            continue
        names = [l[3:].strip() for l in read(p) if l.startswith("## ")]
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


def run(doc_dir, skill_dir):
    errs = []
    check_sections(doc_dir, errs)
    check_acceptance(doc_dir, errs)
    check_dup_lines(doc_dir, errs)
    check_skills(doc_dir, skill_dir, errs)
    return errs


def selftest():
    """정상 사본 하나를 만들어 통과를 보고, 하나씩 깨뜨려 기대한 오류로 잡히는지 본다."""
    tmp = Path(tempfile.mkdtemp())
    docs, skills = tmp / "docs", tmp / "skills"
    docs.mkdir()
    letter = {"실라버스": "L", "덱": "D", "대본": "S", "영상": "V", "코딩랩": "K", "가이드": "P"}
    for d in DOCS:
        (docs / f"{d}.md").write_text(
            f"# {d}\n\n## 목적 · 가치 · 배경\n{letter[d]}목-1 {d}의 목적 문장 하나.\n\n## 작업 컨텍스트\n{d} 컨텍스트 문장.\n\n"
            f"## 작업 요령\n{letter[d]}요-1 {d} 요령 문장.\n\n## 인수 조건\n"
            f"| 번호 | 통과 기준 | 확인 방법 |\n|---|---|---|\n| {letter[d]}-1 | {d}만의 결과 조건 문장입니다 | 열어서 봄 |\n",
            encoding="utf-8")
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

    mutate("확인 방법 빈 칸", sub("덱", "| 열어서 봄 |", "|  |"), "빈 칸")
    mutate("절 빠짐", sub("대본", "## 작업 요령", "## 요령"), "절 「작업 요령」 없음")
    mutate("절 순서 뒤집힘", swap_sections, "절 순서")
    mutate("한 문서 안 같은 줄 두 번", sub("코딩랩", "K요-1 코딩랩 요령 문장.", "K요-1 코딩랩 요령 문장이 두 번 들어간 줄\nK요-1 코딩랩 요령 문장이 두 번 들어간 줄"), "같은 줄이")
    mutate("스킬이 인수 조건을 다시 적음", lambda: (skills / "hyd-video" / "SKILL.md").write_text("영상만의 결과 조건 문장입니다\n", encoding="utf-8"), "다시 적음")
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
