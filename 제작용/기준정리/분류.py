"""장부를 작업 묶음별로 나누고(나누기), 묶음별 분류 결과를 장부에 합친다(합치기).

사용:
  PYTHONUTF8=1 .venv314/Scripts/python 제작용/기준정리/분류.py 나누기
  PYTHONUTF8=1 .venv314/Scripts/python 제작용/기준정리/분류.py 합치기

나누기: 문서/교재/근거/기준정리/분류/입력_<묶음>.tsv (번호 · 파일 · 줄 · 절 · 원문)
합치기: 분류/결과_<묶음>.tsv (번호 · 갈래 · 갈곳 · 핵심어 · 메모)를 장부.tsv에 써 넣는다.
결과에 없는 번호 · 장부에 없는 번호 · 표기법에 맞지 않는 갈곳은 좌표와 함께 실패로 알린다.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "문서/교재/근거/기준정리"
LEDGER = BASE / "장부.tsv"
DIR = BASE / "분류"

GROUPS: dict[str, list[str]] = {
    "공통이론": ["기준", "만법", "이덱", "실전"],
    "실습기준": ["이대", "실대", "실랩", "실가", "검마", "사용"],
    "촬영": ["촬안", "촬AR", "촬N4", "촬NO", "촬VS", "촬포", "촬환", "촬EG"],
    "계약기록": ["클로", "에이", "목적", "현황", "남일", "작상", "실목", "온산", "대조"],
    "인계": ["인5", "인기", "인노", "인실", "인영", "인오", "세A", "세B", "세분"],
    "요청문스킬": ["요A", "요B", "요AB", "요이", "요영", "요제", "SK덱", "SK가", "SK영", "SK포", "SK읽"],
    "lecture스킬": ["LC읽", "LC입", "LC규", "LC공", "LD스", "LD형", "LD문", "LV스", "LL스", "LL원",
                    "LLH", "LL도", "LL그", "LLP", "LL틀", "LP스", "LP근", "LP외", "LR스"],
}

SECTIONS = {f"G{i}" for i in range(1, 6)} | {f"D{i}" for i in range(1, 10)} | \
    {f"S{i}" for i in range(1, 9)} | {f"L{i}" for i in range(1, 9)} | \
    {f"C{i}" for i in range(1, 10)} | {f"H{i}" for i in range(1, 6)}
DEST = re.compile(
    r"^(옮김 (?P<sec>[GDSLCH]\d)|합침 (?P<m>\S+)|충돌 (?P<c>.+)|이력|상태|도구|안내|시스템|폐기: .+)$"
)


def read(p: Path) -> list[dict]:
    with p.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def write(p: Path, rows: list[dict], cols: list[str]) -> None:
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def split() -> int:
    DIR.mkdir(exist_ok=True)
    rows = read(LEDGER)
    code2g = {c: g for g, cs in GROUPS.items() for c in cs}
    missing = sorted({r["코드"] for r in rows} - set(code2g))
    if missing:
        print("묶음에 없는 코드:", missing, file=sys.stderr)
        return 1
    for g in GROUPS:
        part = [r for r in rows if code2g[r["코드"]] == g and not r["메모"].startswith("원본변경")]
        write(DIR / f"입력_{g}.tsv", part, ["번호", "파일", "줄", "절", "원문"])
        print(g, len(part))
    return 0


def merge() -> int:
    rows = read(LEDGER)
    by_id = {r["번호"]: r for r in rows}
    errors: list[str] = []
    seen: set[str] = set()
    for g in GROUPS:
        p = DIR / f"결과_{g}.tsv"
        if not p.exists():
            errors.append(f"{p.name}: 파일 없음")
            continue
        for i, res in enumerate(read(p), 2):
            rid = res.get("번호", "")
            if rid not in by_id:
                errors.append(f"{p.name}:{i}: 장부에 없는 번호 {rid!r}")
                continue
            dest = (res.get("갈곳") or "").strip()
            m = DEST.match(dest)
            if not m:
                errors.append(f"{p.name}:{i}: {rid} 갈곳 표기 오류 {dest!r}")
            elif m.group("sec") and m.group("sec") not in SECTIONS:
                errors.append(f"{p.name}:{i}: {rid} 없는 절 {m.group('sec')}")
            seen.add(rid)
            for c in ("갈래", "갈곳", "핵심어", "메모"):
                by_id[rid][c] = (res.get(c) or "").strip()
    unclassified = [r["번호"] for r in rows if r["번호"] not in seen and not r["메모"].startswith("원본변경")]
    for rid in unclassified[:50]:
        errors.append(f"미분류: {rid}")
    if len(unclassified) > 50:
        errors.append(f"미분류 외 {len(unclassified) - 50}행")
    write(LEDGER, rows, list(rows[0].keys()))
    if errors:
        print(*errors, sep="\n", file=sys.stderr)
        return 1
    print("합침 완료", len(rows))
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    sys.exit({"나누기": split, "합치기": merge}.get(cmd, lambda: (print(__doc__), 2)[1])())
