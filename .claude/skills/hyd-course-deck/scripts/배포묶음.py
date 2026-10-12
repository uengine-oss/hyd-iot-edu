"""교재 PPTX 38개를 과정별 폴더로 묶어 `docs/교재/배포/교재_전체.zip`을 만든다.

    python3 .claude/skills/hyd-course-deck/scripts/배포묶음.py --check    zip을 새로 쓰지 않고, 지금 zip의 구성과 낡은 항목만 검사
    python3 .claude/skills/hyd-course-deck/scripts/배포묶음.py            zip을 다시 만든다

zip 안의 폴더는 `통합반_온라인/` · `실전반_온라인/` · `통합반_오프라인/` · `실전반_오프라인/`이고(`docs/교재/배포/README.md`),
파일은 과정 폴더의 PPTX를 그대로 넣는다. 덱을 다시 빌드했으면 이 묶음도 다시 만든다.
"""
from __future__ import annotations

import argparse
import sys
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]          # 저장소 루트
DECKS = ROOT / "docs" / "교재"
ZIP = DECKS / "배포" / "교재_전체.zip"
# (과정 폴더, 일차 · 회차, zip 안의 폴더, 있어야 할 덱 수)
COURSES = [("통합반", "일차", "통합반_온라인", 11), ("실전반", "일차", "실전반_온라인", 8),
           ("통합반_오프라인", "회차", "통합반_오프라인", 10), ("실전반_오프라인", "회차", "실전반_오프라인", 9)]


def members() -> tuple[dict[str, Path], list[str], list[str]]:
    """{zip 안의 이름: PPTX 경로}, 문제 목록, 알림 목록."""
    out: dict[str, Path] = {}
    problems: list[str] = []
    notes: list[str] = []
    for course, unit, folder, want in COURSES:
        found = 0
        for d in sorted((DECKS / course).glob(f"[0-9][0-9]{unit}")):
            pptx = d / f"{course}_{d.name}.pptx"
            if pptx.is_file():
                out[f"{folder}/{pptx.name}"] = pptx
                found += 1
            else:
                problems.append(f"PPTX 없음: {pptx.relative_to(ROOT).as_posix()}")
            if (d / ("~$" + pptx.name)).exists():
                notes.append(f"알림: 잠금 파일(~$)이 있다 — PowerPoint에서 고치는 중이면 저장하고 닫은 뒤 묶는다: {pptx.relative_to(ROOT).as_posix()}")
        if found != want:
            problems.append(f"{course}: PPTX {found}개 (있어야 할 수 {want})")
    return out, problems, notes


def crc(path: Path) -> int:
    c = 0
    with path.open("rb") as f:
        while chunk := f.read(1 << 20):
            c = zlib.crc32(chunk, c)
    return c


def check(want: dict[str, Path]) -> list[str]:
    if not ZIP.is_file():
        return [f"zip 없음: {ZIP.relative_to(ROOT).as_posix()}"]
    problems = []
    with zipfile.ZipFile(ZIP) as z:
        bad = z.testzip()
        if bad:
            problems.append(f"zip이 깨짐: {bad}")
        have = {i.filename: i for i in z.infolist() if not i.is_dir()}
    for name in sorted(set(want) - set(have)):
        problems.append(f"zip에 없음: {name}")
    for name in sorted(set(have) - set(want)):
        problems.append(f"zip에만 있음: {name}")
    for name in sorted(set(want) & set(have)):
        if have[name].file_size != want[name].stat().st_size or have[name].CRC != crc(want[name]):
            problems.append(f"낡음(과정 폴더의 PPTX와 다름): {name}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description="교재 PPTX 배포 묶음을 만들거나 검사한다.")
    ap.add_argument("--check", action="store_true", help="zip을 쓰지 않고 구성과 낡은 항목만 검사한다")
    a = ap.parse_args()
    want, problems, notes = members()
    for n in notes:
        print(f"  {n}")
    if a.check:
        problems += check(want)
        print(f"과정 폴더의 PPTX {len(want)}개, zip: {ZIP.relative_to(ROOT).as_posix()}")
        for p in problems:
            print(f"  {p}")
        print("검사 통과: zip이 과정 폴더의 PPTX와 같다." if not problems else f"[어긋남] {len(problems)}건 — 빌드가 끝났으면 `--check` 없이 돌려 다시 만든다.")
        return 1 if problems else 0
    if problems:
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        print("[실패] 위 문제를 풀고 다시 돌린다. zip은 쓰지 않았다.", file=sys.stderr)
        return 1
    tmp = ZIP.with_suffix(".zip.tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name, path in want.items():
            z.write(path, name)
    tmp.replace(ZIP)
    left = check(want)
    print(f"{ZIP.relative_to(ROOT).as_posix()} 만듦: PPTX {len(want)}개, {ZIP.stat().st_size / 1e6:.1f} MB")
    for p in left:
        print(f"  {p}")
    return 1 if left else 0


if __name__ == "__main__":
    sys.exit(main())
