"""그 회차보다 앞 회차들의 이론 덱 원고에서 학습목표 장 · 복습 장 · 용어 정리 장(「오늘 다룬 핵심 개념과 주요 용어 정리」)의 화면 내용만 찍는다. 읽기만 한다.
언제: 덱 · 대본 · 영상 · 코딩랩 · 가이드 일을 시작할 때 앞 회차 흐름을 잡으려고 — 앞 회차 덱을 통째로 읽지 않는다.
명령: <py> workspace/강의제작/제작도구/검사/앞회차.py <통합반|실전반> <NN>
"""
import re
import sys
from pathlib import Path

DECKS = Path(__file__).resolve().parents[1] / "온라인/decks"
DIR = {"통합반": "integrated", "실전반": "practical"}
SLIDE = re.compile(r"^## SLIDE (\d+) — (.*)$")
TERMS = "오늘 다룬 핵심 개념과 주요 용어 정리"


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


def main(argv):
    if len(argv) != 3 or argv[1] not in DIR or not argv[2].isdigit():
        sys.exit("사용: 앞회차.py <통합반|실전반> <NN>")
    course, n = argv[1], int(argv[2])
    if n < 2:
        sys.exit(f"{course} {n:02d}회차: 앞 회차가 없다")
    for k in range(1, n):
        p = DECKS / DIR[course] / f"day{k:02d}" / f"{course}_{k:02d}일차.md"
        if not p.exists():
            sys.exit(f"{p}: 덱 원고 없음")
        all_ = slides(p)
        goal = [s for s in all_ if s[1] == "학습목표"]
        review = [s for s in all_ if s[1].startswith("복습")]
        terms = [s for s in all_ if s[1] == TERMS]
        if len(goal) != 1 or len(terms) != 1 or len(review) > 1:
            sys.exit(f"{p}: 학습목표 {len(goal)}장 · 용어 정리 {len(terms)}장 · 복습 {len(review)}장 — 학습목표와 용어 정리는 1장, 복습은 1장 이하여야 한다")
        print(f"# {course} {k:02d}회차 — {p.relative_to(DECKS.parents[4]).as_posix()}")
        if not review:
            print("(이 회차 덱에는 복습 장이 없다)")
        for _, _, body in goal + review + terms:
            print("\n".join(body).rstrip() + "\n")


if __name__ == "__main__":
    main(sys.argv)
