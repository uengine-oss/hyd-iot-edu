"""HYD 교재 덱 38개의 전체 장수와 단원별 이론 본문 장수를 덱 MD에서 세어 표로 낸다.

    python3 .claude/skills/hyd-course-deck/scripts/장수.py            전체
    python3 .claude/skills/hyd-course-deck/scripts/장수.py 통합반      과정 이름으로 고르기(통합반 · 실전반 · 통합반_오프라인 · 실전반_오프라인)
    python3 .claude/skills/hyd-course-deck/scripts/장수.py --units     단원별 본문 장수까지

본문 장수는 번호가 붙은 간지와 다음 간지 사이의 이론 본문 장 수다.
표지 · 학습목표 · 목차 · 간지 · 실습 설명 · 용어 정리 · 퀴즈 · 정답은 본문에 넣지 않는다.
실습 간지 뒤의 한 장은 실습 설명으로 본다. 제목에 「시연」이 든 실습 간지는 다음 간지나 용어 정리까지를 그 실습의 장으로 보고,
두 장 이상이면 「시연 소개」로 따로 적는다(통합반 11일차의 ProcessGPT 시연).
`문서/교재/3_현황.md`의 표(장수를 적는 한 곳)를 고칠 때 이 표와 맞춘다.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]          # 저장소 루트
DECKS = ROOT / "만들기" / "decks"              # 덱 원고(MD), 그림, 조립 스크립트
DIRS = {"통합반": "integrated", "실전반": "practical", "통합반_오프라인": "integrated-offline", "실전반_오프라인": "practical-offline"}
PREFIX = {"일차": "day", "회차": "session"}
COURSES = [("통합반", "일차"), ("실전반", "일차"), ("통합반_오프라인", "회차"), ("실전반_오프라인", "회차")]


def decks(only: list[str]) -> list[tuple[str, str, Path]]:
    out = []
    for course, unit in COURSES:
        if only and course not in only:
            continue
        for d in sorted((DECKS / DIRS[course]).glob(f"{PREFIX[unit]}[0-9][0-9]")):
            md = d / f"{course}_{d.name[-2:]}{unit}.md"
            if md.is_file():
                out.append((course, f"{d.name[-2:]}{unit}", md))
    return out


def field(block: str, name: str) -> str:
    m = re.search(rf"(?m)^- {name}: *(.*)$", block)
    return m.group(1).strip() if m else ""


def count(md: Path) -> dict:
    text = md.read_text(encoding="utf-8")
    parts = re.split(r"(?m)^(?=## SLIDE )", text)[1:]
    units: list[list] = []                 # [번호, 제목, 본문 장수]
    labs = 0
    demos: list[int] = []                # 시연 실습마다 간지 뒤에 이어진 장 수
    mode = "앞"                            # 앞 | 본문 | 실습 | 시연 | 뒤
    lab_left = 0
    for part in parts:
        head = re.match(r"## SLIDE \S+ — (.*)\n", part)
        title = head.group(1).strip() if head else ""
        kind, no, sep = field(part, "유형"), field(part, "번호"), field(part, "구분")
        if kind == "간지":
            if sep == "실습" or title.startswith("실습:"):
                labs += 1
                if "시연" in title:
                    mode = "시연"
                    demos.append(0)
                else:
                    mode, lab_left = "실습", 1
            elif no:
                units.append([no, title.replace(" / ", " "), 0])
                mode = "본문"
            else:                          # 번호 없는 간지 = 퀴즈 간지
                mode = "뒤"
            continue
        if title.startswith("오늘 다룬 핵심 개념"):
            mode = "뒤"
        if mode == "실습":
            lab_left -= 1
            if lab_left <= 0:
                mode = "본문" if units else "앞"
        elif mode == "시연":
            demos[-1] += 1
        elif mode == "본문":
            units[-1][2] += 1
    return {"전체": len(parts), "본문": sum(u[2] for u in units), "단원": units, "실습": labs, "시연소개": sum(n for n in demos if n > 1)}


def main() -> int:
    ap = argparse.ArgumentParser(description="HYD 교재 덱의 전체 장수와 단원별 본문 장수를 센다.")
    ap.add_argument("course", nargs="*", help="과정 이름(없으면 넷 모두)")
    ap.add_argument("--units", action="store_true", help="단원별 본문 장수를 함께 낸다")
    a = ap.parse_args()
    known = [c for c, _ in COURSES]
    bad = [c for c in a.course if c not in known]
    if bad:
        print(f"[실패] 모르는 과정: {', '.join(bad)} (가능: {', '.join(known)})", file=sys.stderr)
        return 2
    found = decks(a.course)
    if not found:
        print(f"[실패] 덱 MD를 찾지 못함: {DECKS.relative_to(ROOT)}", file=sys.stderr)
        return 1
    head = "| 과정 | 덱 | 전체 | 본문 | 실습 간지 | 단원별 본문 |" if a.units else "| 과정 | 덱 | 전체 | 본문 | 실습 간지 |"
    print(head)
    print("|" + "---|" * head.count("|", 1))
    total = 0
    for course, name, md in found:
        c = count(md)
        total += c["전체"]
        row = f"| {course} | {name} | {c['전체']} | {c['본문']} | {c['실습']} |"
        if a.units:
            cells = [f"{no} {title}({n})" for no, title, n in c["단원"]]
            if c["시연소개"]:
                cells.append(f"시연 소개({c['시연소개']})")
            row += " " + " · ".join(cells) + " |"
        print(row)
    print(f"\n덱 {len(found)}개, 전체 {total}장")
    return 0


if __name__ == "__main__":
    sys.exit(main())
