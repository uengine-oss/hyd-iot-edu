"""같은 반·같은 수업 방식의 바로 앞 회차에서 학습목표 장 · 복습 장 · 용어 정리 장(「오늘 다룬 핵심 개념과 주요 용어 정리」)의 화면 내용만 찍는다. 읽기만 한다.
언제: 덱 · 대본 · 영상 · 코딩랩 · 가이드 일을 시작할 때 앞 회차 흐름을 잡으려고 — 앞 회차 덱을 통째로 읽지 않는다.
명령: <py> workspace/강의제작/제작도구/검사/앞회차.py <통합반|실전반> <NN> [--오프라인]
이론 덱이 없는 실행 중심 회는 실라버스의 마지막 활동을 안내한다. 첫 회에는 앞 회차가 없다.
"""
import argparse
import re
import sys
from pathlib import Path

from openpyxl import load_workbook
from 실라버스행 import XLSX, sessions

TOOLS = Path(__file__).resolve().parents[1]
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
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("과정", choices=DIR)
    ap.add_argument("회차", type=int)
    ap.add_argument("--오프라인", action="store_true")
    args = ap.parse_args(argv[1:])
    course, n = args.과정, args.회차
    mode = "오프라인" if args.오프라인 else "온라인"
    if not XLSX.is_file():
        sys.exit(f"{XLSX}: 정본 실라버스가 없어 직전 회차의 활동을 확인할 수 없다")
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
    if n == 1:
        print(f"{course} {mode} 01회차: 첫 회차로 앞 회차가 없다")
        return

    prev = n - 1
    rows = table.get(prev)
    if not rows:
        sys.exit(f"{course} {mode} {prev:02d}회차: 직전 회차의 실라버스 행 미확인")
    print(f"# {course} {mode} {prev:02d}회차")
    print(f"마지막 편성 활동: [{rows[-1][0]}] {rows[-1][1]}")
    if not any(row[0].startswith("이론") for row in rows):
        print("이론 행이 없는 회차다. 위 활동의 가이드·실습 결과에서 학생이 어떤 상태를 넘기는지 확인한다.")
        return

    day = f"{prev:02d}"
    sub = f"off{day}/{course}_오프라인_{day}회차.md" if args.오프라인 else f"day{day}/{course}_{day}일차.md"
    p = TOOLS / mode / "decks" / DIR[course] / sub
    if not p.is_file():
        sys.exit(f"{p}: 이론 행이 있으나 해당 덱 원고가 없다. 그 회차의 덱·실습 인계를 확인할 때까지 미확인")
    all_ = slides(p)
    goal = [s for s in all_ if s[1] == "학습목표"]
    terms = [s for s in all_ if s[1] == TERMS]
    if len(goal) != 1 or len(terms) != 1:
        sys.exit(f"{p}: 학습목표 {len(goal)}장 · 용어 정리 {len(terms)}장 — 각 1장이어야 한다")
    i = all_.index(terms[0])
    if i == 0 or all_[i - 1][0] <= goal[0][0]:
        sys.exit(f"{p}: 용어 정리 직전의 복습 자리를 확인할 수 없다")
    print(f"원고: {p.relative_to(TOOLS.parents[2]).as_posix()}")
    print("복습은 D-2가 정한 용어 정리 직전 장을 뽑는다. 제목과 실제 화면에서 내용을 확인한다.")
    for _, _, body in (goal[0], all_[i - 1], terms[0]):
        print("\n".join(body).rstrip() + "\n")


if __name__ == "__main__":
    main(sys.argv)
