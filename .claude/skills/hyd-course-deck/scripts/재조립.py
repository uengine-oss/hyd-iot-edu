"""통합반 원 덱에서 조립 덱(실전반 온라인, 통합반 · 실전반 오프라인)을 다시 만들고, 바뀐 덱의 PPTX를 빌드한다.

    python3 .claude/skills/hyd-course-deck/scripts/재조립.py --dry-run          돌릴 스크립트와 읽는 통합반 일차만 출력
    python3 .claude/skills/hyd-course-deck/scripts/재조립.py                    조립 스크립트를 모두 차례로 돌린다
    python3 .claude/skills/hyd-course-deck/scripts/재조립.py --day 9 11         통합반 9 · 11일차를 읽는 스크립트만
    python3 .claude/skills/hyd-course-deck/scripts/재조립.py --build            조립한 뒤, 덱 MD가 커밋과 달라진 덱만 PPTX 빌드
    python3 .claude/skills/hyd-course-deck/scripts/재조립.py --build-only       조립은 건너뛰고 빌드만

조립 스크립트는 `만들기/decks/practical/만들기_01일차.py`와 각 일차 · 회차 폴더의 `조립.py`다.
가져오던 장의 제목이나 손질 목록의 원문 문구가 통합반 원 덱에서 바뀌었으면 그 스크립트가 멈춘다.
이 도구는 멈춘 스크립트와 그 까닭(마지막 줄)을 모아 보이고 나머지를 계속 돌린다. 멈춘 곳은 그 `조립.py`의 순서표 · 손질 목록을 고친다.

「바뀐 덱」은 `git status`에서 덱 MD가 커밋과 다른 덱이다(손으로 고친 통합반 원 덱과 다시 조립돼 내용이 달라진 조립 덱).
빌드는 `uv`가 있어야 한다. `--pptx-dir <폴더>`를 주면 저장소의 PPTX를 덮어쓰지 않고 그 폴더에 만든다(시험용).
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]          # 저장소 루트
DECKS = ROOT / "만들기" / "decks"              # 덱 원고(MD), 그림, 조립 스크립트
SLIDES = ROOT / "산출물" / "교재" / "PPTX"           # 덱 PPTX (과정 폴더 이름은 PPTX_DIRS)
DIRS = {"통합반": "integrated", "실전반": "practical", "통합반_오프라인": "integrated-offline", "실전반_오프라인": "practical-offline"}
PREFIX = {"일차": "day", "회차": "session"}
PPTX_DIRS = {"integrated": "통합반_온라인", "practical": "실전반_온라인", "integrated-offline": "통합반_오프라인", "practical-offline": "실전반_오프라인"}  # 원고 폴더 → PPTX 폴더
BUILDER = ROOT / ".claude" / "skills" / "lecture-deck" / "scripts" / "deck2pptx.py"
COURSES = [("통합반", "일차"), ("실전반", "일차"), ("통합반_오프라인", "회차"), ("실전반_오프라인", "회차")]


def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def scripts() -> list[Path]:
    out = [DECKS / "practical" / "만들기_01일차.py"]
    for course in ("practical", "integrated-offline", "practical-offline"):
        out += sorted((DECKS / course).glob("*[0-9][0-9]/조립.py"))
    return [p for p in out if p.is_file()]


def sources(script: Path) -> list[int]:
    """그 스크립트가 읽는 통합반 일차. 스크립트 머리(첫 함수 앞)의 SRC · DAY 선언에서 읽는다."""
    head = script.read_text(encoding="utf-8").split("\ndef ", 1)[0]
    days: set[int] = set()
    for m in re.finditer(r'"integrated"\s*/\s*"day(\d{2})"', head):
        days.add(int(m.group(1)))
    for m in re.finditer(r'for d in \(([^)]*)\)', head):
        days.update(int(x) for x in re.findall(r'"(\d{1,2})"', m.group(1)))
    for m in re.finditer(r'(?m)^DAY\s*=\s*"(\d{1,2})"', head):
        days.add(int(m.group(1)))
    return sorted(days)


def deck_mds() -> list[Path]:
    out = []
    for course, unit in COURSES:
        for d in sorted((DECKS / DIRS[course]).glob(f"{PREFIX[unit]}[0-9][0-9]")):
            md = d / f"{course}_{d.name[-2:]}{unit}.md"
            if md.is_file():
                out.append(md)
    return out


def changed_mds() -> list[Path]:
    """덱 MD 가운데 커밋과 다른 것(고침 · 새 파일)."""
    r = subprocess.run(["git", "-c", "core.quotepath=off", "status", "--porcelain", "--", "만들기/decks"],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"[실패] git status: {r.stderr.strip()}")
    dirty = set()
    for line in r.stdout.splitlines():
        path = line[3:].split(" -> ")[-1].strip().strip('"')
        dirty.add((ROOT / path).resolve())
    out = []
    for md in deck_mds():
        if md.resolve() in dirty or any(d in md.resolve().parents for d in dirty):
            out.append(md)
    return out


def build(md: Path, pptx_dir: Path | None) -> tuple[bool, str]:
    home = SLIDES / PPTX_DIRS[md.parent.parent.name]  # 원고는 만들기/decks/<과정>/…, PPTX는 산출물/교재/PPTX/<과정 한글>/
    pptx = (pptx_dir or home) / md.with_suffix(".pptx").name
    lock = home / ("~$" + md.with_suffix(".pptx").name)
    if not pptx_dir and lock.exists():
        return False, "PowerPoint가 이 PPTX를 열고 있다(잠금 파일). 닫고 다시 돌린다"
    cmd = ["uv", "run", "--no-project", "--with", "python-pptx", "--with", "pymupdf", "python",
           rel(BUILDER), rel(md), str(pptx) if pptx_dir else rel(pptx)]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    tail = (r.stdout + r.stderr).strip().splitlines()
    return r.returncode == 0, (tail[-1] if tail else "")


def main() -> int:
    ap = argparse.ArgumentParser(description="조립 덱을 다시 만들고 바뀐 덱만 빌드한다.")
    ap.add_argument("--dry-run", action="store_true", help="돌릴 것만 출력하고 아무것도 실행하지 않는다")
    ap.add_argument("--day", type=int, nargs="+", metavar="N", help="통합반 N일차를 읽는 스크립트만")
    ap.add_argument("--build", action="store_true", help="조립 뒤 덱 MD가 커밋과 달라진 덱의 PPTX를 빌드한다")
    ap.add_argument("--build-only", action="store_true", help="조립은 건너뛰고 빌드만 한다")
    ap.add_argument("--pptx-dir", type=Path, help="PPTX를 저장소 대신 이 폴더에 만든다(시험용)")
    a = ap.parse_args()

    todo = [(s, sources(s)) for s in scripts()]
    if a.day:
        todo = [(s, d) for s, d in todo if set(d) & set(a.day)]
    failed: list[tuple[str, str]] = []

    if not a.build_only:
        print(f"조립 스크립트 {len(todo)}개" + (f" (통합반 {', '.join(map(str, a.day))}일차를 읽는 것)" if a.day else ""))
        for n, (s, days) in enumerate(todo, 1):
            src = "통합반 " + " · ".join(map(str, days)) + "일차" if days else "원천을 읽지 못함"
            if a.dry_run:
                print(f"  {n:2d}. {rel(s)}  ← {src}")
                continue
            r = subprocess.run([sys.executable, str(s)], cwd=ROOT, capture_output=True, text=True)
            lines = (r.stdout + r.stderr).strip().splitlines()
            last = lines[-1] if lines else ""
            if r.returncode == 0:
                print(f"  {n:2d}. 됨    {last}")
            else:
                print(f"  {n:2d}. 멈춤  {rel(s)}\n        {last}")
                failed.append((rel(s), last))

    if a.build or a.build_only:
        if failed:
            print("\n멈춘 조립 스크립트가 있어 빌드하지 않는다.")
        else:
            mds = changed_mds()
            print(f"\n덱 MD가 커밋과 다른 덱 {len(mds)}개" + (" (빌드하지 않고 목록만)" if a.dry_run else ""))
            if a.pptx_dir and not a.dry_run:
                a.pptx_dir.mkdir(parents=True, exist_ok=True)
            for md in mds:
                if a.dry_run:
                    print(f"  {rel(md)}")
                    continue
                ok, last = build(md, a.pptx_dir)
                print(f"  {'됨  ' if ok else '실패'}  {rel(md)}\n        {last}")
                if not ok:
                    failed.append((rel(md), last))

    if failed:
        print(f"\n[실패] {len(failed)}건")
        for path, why in failed:
            print(f"  {path}: {why}")
        return 1
    if not a.dry_run:
        print("\n모두 됨. 장수가 바뀌었으면 `장수.py`로 세어 문서/교재/3_현황.md 7절과 만들기/decks/README.md의 숫자를 맞춘다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
