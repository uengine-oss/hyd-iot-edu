"""교재 산출물 문서 재편 검사 (설계: 로컬 .evidence/기준정리/재편_설계.md 6절, 대응표는 같은 폴더의 재편_대응표.tsv).

사용:
  python 재편검사.py            # 저장소의 workspace/강의제작/지침/<여섯>.md 검사
  python 재편검사.py --자가시험   # 일부러 깨뜨린 사본으로 각 검사가 잡는지 확인
오류가 하나라도 있으면 종료 코드 1, 위치는 파일:줄.
"""
import csv
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DOCS = ["실라버스", "덱", "대본", "영상", "코딩랩", "가이드"]
SECTIONS = ["목적 · 가치 · 배경", "작업 컨텍스트", "작업 요령", "인수 조건"]
SKILLS = ["hyd-syllabus", "hyd-course-deck", "hyd-script", "hyd-video", "hyd-coding-lab", "hyd-lab-guide"]
PREFIX_DOC = {"L": "실라버스", "D": "덱", "S": "대본", "V": "영상", "K": "코딩랩", "P": "가이드"}
OLD_NAMES = re.compile(r"기준_(공통|이론덱|대본|실습_도구|실습_코딩랩|실습)(\.md)?")
TABLE_SEP = re.compile(r"^\|\s*:?-{3,}")
NEW_ID = re.compile(r"(?<![\w-])([LDSVKP](?:목|맥|요)?-\d+)")


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


def acceptance_rows(p):
    """인수 조건 절 안 표의 행: (줄, [칸...])."""
    rows, inside, intable = [], False, False
    for i, l in enumerate(read(p), 1):
        if l.startswith("## "):
            inside = l[3:].strip() == "인수 조건"
            continue
        if not inside:
            continue
        if l.startswith("|"):
            if TABLE_SEP.match(l):
                intable = True
                continue
            if intable:
                rows.append((i, [c.strip() for c in l.strip().strip("|").split("|")]))
        else:
            intable = False
    return rows


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


def check_map(map_file, doc_dir, errs):
    """원문 행마다 새 자리가 있고, 대상 문서 하나하나에 그 문서의 새 ID가 있으며, 그 ID가 실제로 문서에 있다."""
    if not map_file.exists():
        errs.append(f"{map_file}: 대응표 없음")
        return
    ids = {}
    for d in DOCS:
        p = doc_dir / f"{d}.md"
        if p.exists():
            ids[d] = set(NEW_ID.findall(p.read_text(encoding="utf-8")))
    with map_file.open(encoding="utf-8", newline="") as f:
        for n, r in enumerate(csv.DictReader(f, delimiter="\t"), 2):
            if r.get("성격") == "제목":
                continue
            new = (r.get("새자리") or "").strip()
            if not new:
                errs.append(f"{map_file}:{n}: {r.get('ID')} 새 자리 없음")
                continue
            # 문서별 폐기: 「[문서] 폐기: 까닭」 (문서 표시가 없으면 대상 전부에 대한 폐기)
            dropped = set()
            for m in re.finditer(r"(?:\[(\S+)\]\s*)?폐기:\s*([^;\[]*)", new):
                if len(m.group(2).strip()) < 6:
                    errs.append(f"{map_file}:{n}: {r.get('ID')} 폐기 까닭이 없음")
                dropped |= {m.group(1)} if m.group(1) else {t.strip() for t in (r.get("대상") or "").split(";")}
            refs = NEW_ID.findall(re.sub(r"(?:\[\S+\]\s*)?폐기:[^;\[]*", "", new))
            for ref in refs:
                if ref not in ids.get(PREFIX_DOC[ref[0]], set()):
                    errs.append(f"{map_file}:{n}: {r.get('ID')} 새 자리 「{ref}」가 {PREFIX_DOC[ref[0]]} 문서에 없음")
            have = {PREFIX_DOC[x[0]] for x in refs} | dropped
            for want in [t.strip() for t in (r.get("대상") or "").split(";") if t.strip()]:
                if want not in have:
                    errs.append(f"{map_file}:{n}: {r.get('ID')} 대상 「{want}」 문서에 새 자리가 없음")


HISTORY = re.compile(r"지난기록|/archive|검증_기록/|작업기록")
# 회차 산출물 안의 옛 참조는 그 회차 검토 때 새 인수 조건(덱 D-88 · D-152 등)으로 고친다 — 오류가 아니라 따로 센다.
ROUND_PRODUCT = re.compile(r"^(workspace/강의제작/제작도구/(온라인|오프라인)/decks/.*\.(md|json)|workspace/강의제작/제작도구/구성/.*/(구성\.json|구성표\.md|원본대응\.json)|workspace/강의제작/산출물/)")
OLD_ANY = re.compile(OLD_NAMES.pattern + r"|lecture-deck|hyd-lecture-video|hyd-portal-video")


SCAN_TEXT = {".md", ".json", ".py", ".html", ".txt", ".yaml", ".yml", ".sh", ".mjs", ".js", ".tsv", ".csv"}
NOT_SCANNED = {Path(__file__).resolve(), (Path(__file__).parent / "재편_대응표.tsv").resolve()}   # 옛 이름을 일부러 담은 것


def scan_files(root):
    """main이 추적하는 파일 + git이 무시하는 작업 자리(workspace · .claude · CLAUDE.md · AGENTS.md)."""
    out = subprocess.run(["git", "-c", "core.quotepath=false", "ls-files"], cwd=root, capture_output=True, check=True)
    files = {root / p for p in out.stdout.decode("utf-8").splitlines()}
    for base in ("workspace", ".claude"):
        files |= {p for p in (root / base).rglob("*") if p.is_file() and "node_modules" not in p.parts}
    files |= {root / "CLAUDE.md", root / "AGENTS.md"}
    return sorted(p for p in files if p.is_file() and p.suffix.lower() in SCAN_TEXT and p.resolve() not in NOT_SCANNED)


def check_old_names(errs, root=ROOT, notes=None):
    later = 0
    for p in scan_files(root):
        path = p.relative_to(root).as_posix()
        if HISTORY.search(path):
            continue
        for i, l in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if not OLD_ANY.search(l):
                continue
            if ROUND_PRODUCT.match(path):
                later += 1
                continue
            errs.append(f"옛 기준 이름 참조: {path}:{i}: {l.strip()[:120]}")
    if notes is not None:
        notes.append(f"회차 산출물 안 옛 참조(회차 검토 몫): {later}")


def run(doc_dir, skill_dir, mapf, with_git=True, notes=None):
    errs = []
    check_sections(doc_dir, errs)
    check_acceptance(doc_dir, errs)
    check_dup_lines(doc_dir, errs)
    check_skills(doc_dir, skill_dir, errs)
    check_map(mapf, doc_dir, errs)
    if with_git:
        check_old_names(errs, notes=notes)
    return errs


def selftest():
    """정상 사본 하나를 만들어 통과를 보고, 하나씩 깨뜨려 기대한 오류로 잡히는지 본다."""
    tmp = Path(tempfile.mkdtemp())
    docs, skills = tmp / "docs", tmp / "skills"
    docs.mkdir()
    letter = {v: k for k, v in PREFIX_DOC.items()}
    for d in DOCS:
        (docs / f"{d}.md").write_text(
            f"# {d}\n\n## 목적 · 가치 · 배경\n{letter[d]}목-1 {d}의 목적 문장 하나.\n\n## 작업 컨텍스트\n{d} 컨텍스트 문장.\n\n"
            f"## 작업 요령\n{letter[d]}요-1 {d} 요령 문장.\n\n## 인수 조건\n"
            f"| 번호 | 통과 기준 | 확인 방법 |\n|---|---|---|\n| {letter[d]}-1 | {d}만의 결과 조건 문장입니다 | 열어서 봄 |\n",
            encoding="utf-8")
    for s in SKILLS:
        (skills / s).mkdir(parents=True)
        (skills / s / "SKILL.md").write_text("문서를 연다.\n", encoding="utf-8")
    mapf = tmp / "map.tsv"
    good_map = "ID\t성격\t대상\t새자리\nGC-0001\t인수조건\t덱;영상\tD-1; V-1\nGC-0002\t요령\t대본\tS요-1\nGC-0003\t컨텍스트\t덱\t폐기: 공통 · 갈래 구조가 없어짐(설계 2절)\nGC-0004\t목적\t영상\tV목-1\n"
    mapf.write_text(good_map, encoding="utf-8")

    def go():
        return run(docs, skills, mapf, with_git=False)

    cases = []
    base = go()
    cases.append(("정상 사본 통과", not base, base))

    def mutate(name, f, expect):
        saved = {p: p.read_text(encoding="utf-8") for p in list(docs.glob("*.md")) + [mapf] + list(skills.glob("*/SKILL.md"))}
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

    def map_with(text):
        return lambda: mapf.write_text(text, encoding="utf-8")

    mutate("확인 방법 빈 칸", sub("덱", "| 열어서 봄 |", "|  |"), "빈 칸")
    mutate("절 빠짐", sub("대본", "## 작업 요령", "## 요령"), "절 「작업 요령」 없음")
    mutate("절 순서 뒤집힘", swap_sections, "절 순서")
    mutate("한 문서 안 같은 줄 두 번", sub("코딩랩", "K요-1 코딩랩 요령 문장.", "K요-1 코딩랩 요령 문장이 두 번 들어간 줄\nK요-1 코딩랩 요령 문장이 두 번 들어간 줄"), "같은 줄이")
    mutate("스킬이 인수 조건을 다시 적음", lambda: (skills / "hyd-video" / "SKILL.md").write_text("영상만의 결과 조건 문장입니다\n", encoding="utf-8"), "다시 적음")
    mutate("대응표 새 자리 빈칸", map_with("ID\t성격\t대상\t새자리\nGC-0001\t요령\t대본\t\n"), "새 자리 없음")
    mutate("대응표가 문서에 없는 ID를 가리킴", map_with("ID\t성격\t대상\t새자리\nGC-0001\t요령\t영상\tV-99\n"), "영상 문서에 없음")
    mutate("대상 문서 하나가 빠짐", map_with("ID\t성격\t대상\t새자리\nGC-0001\t인수조건\t덱;영상\tD-1\n"), "대상 「영상」 문서에 새 자리가 없음")
    mutate("폐기 까닭 없음", map_with("ID\t성격\t대상\t새자리\nGC-0001\t요령\t덱\t폐기:\n"), "폐기 까닭이 없음")
    mutate("문서에서 행을 지워 대응이 끊김", sub("영상", "| V-1 |", "| V-2 |"), "「V-1」가 영상 문서에 없음")
    shutil.rmtree(tmp)
    ok = True
    for name, caught, detail in cases:
        print(f"{'통과' if caught else '실패'}: {name} — {detail if detail else ''}")
        ok &= caught
    return ok


if __name__ == "__main__":
    if "--자가시험" in sys.argv:
        sys.exit(0 if selftest() else 1)
    notes = []
    errs = run(ROOT / "workspace" / "강의제작" / "지침", ROOT / ".claude" / "skills",
               Path(__file__).resolve().parent / "재편_대응표.tsv", notes=notes)
    for e in errs:
        print(e)
    for n in notes:
        print(n)
    print(f"오류 {len(errs)}")
    sys.exit(1 if errs else 0)
