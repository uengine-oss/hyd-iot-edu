"""HYD 교재 덱 38개에서 실습 간지와 그 다음 장(설명 장)의 번호 · 제목을 덱 MD에서 뽑아 표로 낸다.

    python3 .claude/skills/hyd-lab-guide/scripts/실습목록.py                  전체
    python3 .claude/skills/hyd-lab-guide/scripts/실습목록.py 통합반            과정 이름으로 고르기(통합반 · 실전반 · 통합반_오프라인 · 실전반_오프라인)
    python3 .claude/skills/hyd-lab-guide/scripts/실습목록.py 통합반 --day 6    그 과정의 6일차(회차)만

실습 간지는 `- 유형: 간지`이고 제목이 `실습:`으로 시작하는 장이다. 설명 장은 바로 다음 장이다.
제목에 「시연」이 든 간지는 강사 시연이며(ProcessGPT) 학생 실습 가이드의 대상이 아니다. 다음 간지나 용어 정리 앞까지를 시연 소개로 센다.
장 번호는 덱을 고치면 바뀐다. `docs/교재/인계/06_실습가이드_착수.md` 3절의 표는 간지 제목만 싣고, 번호는 이 도구로 뽑는다.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]          # 저장소 루트
DECKS = ROOT / "docs" / "교재"
COURSES = [("통합반", "일차"), ("실전반", "일차"), ("통합반_오프라인", "회차"), ("실전반_오프라인", "회차")]


def slides(md: Path) -> list[tuple[str, str, str]]:
    """덱 MD를 (번호, 제목, 유형)의 목록으로 읽는다."""
    out = []
    for part in re.split(r"(?m)^(?=## SLIDE )", md.read_text(encoding="utf-8"))[1:]:
        head = re.match(r"## SLIDE (\S+) — (.*)\n", part)
        if not head:
            raise SystemExit(f"[실패] 장 머리를 읽지 못함: {md.relative_to(ROOT)}: {part[:40]!r}")
        kind = re.search(r"(?m)^- 유형: *(.*)$", part)
        out.append((head.group(1), head.group(2).strip(), kind.group(1).strip() if kind else ""))
    return out


def labs(md: Path) -> list[tuple[int, str, str, str, str]]:
    """(실습 순번, 간지 번호, 간지 제목, 설명 장 번호, 설명 장 제목 또는 시연 소개의 장 수)."""
    s = slides(md)
    out = []
    for i, (no, title, kind) in enumerate(s):
        if kind != "간지" or not title.startswith("실습:"):
            continue
        name = title[len("실습:"):].strip()
        nxt_no, nxt_title = (s[i + 1][0], s[i + 1][1]) if i + 1 < len(s) else ("-", "(다음 장 없음)")
        if "시연" in name:
            n = 0
            for _, t, k in s[i + 1:]:
                if k == "간지" or t.startswith("오늘 다룬 핵심 개념"):
                    break
                n += 1
            nxt_title = f"(강사 시연 — 가이드 대상 아님. 시연 소개 {n}장)"
        out.append((len(out) + 1, no, name, nxt_no, nxt_title))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="HYD 교재 덱의 실습 간지와 설명 장의 번호 · 제목을 뽑는다.")
    ap.add_argument("course", nargs="*", help="과정 이름(없으면 넷 모두)")
    ap.add_argument("--day", type=int, nargs="*", default=[], help="일차(회차) 번호로 고르기")
    a = ap.parse_args()
    known = [c for c, _ in COURSES]
    bad = [c for c in a.course if c not in known]
    if bad:
        print(f"[실패] 모르는 과정: {', '.join(bad)} (가능: {', '.join(known)})", file=sys.stderr)
        return 2
    print("| 과정 | 덱 | # | 실습 간지 | 간지 장 | 설명 장 |")
    print("|---|---|---|---|---|---|")
    decks = total = 0
    for course, unit in COURSES:
        if a.course and course not in a.course:
            continue
        for d in sorted((DECKS / course).glob(f"[0-9][0-9]{unit}")):
            md = d / f"{course}_{d.name}.md"
            if not md.is_file() or (a.day and int(d.name[:2]) not in a.day):
                continue
            decks += 1
            for n, no, name, nxt_no, nxt_title in labs(md):
                total += 1
                print(f"| {course} | {d.name} | {n} | {name} | {no} | {nxt_no} {nxt_title} |")
    if not decks:
        print(f"[실패] 덱 MD를 찾지 못함: {DECKS.relative_to(ROOT)}", file=sys.stderr)
        return 1
    print(f"\n덱 {decks}개, 실습 간지 {total}개")
    return 0


if __name__ == "__main__":
    sys.exit(main())
