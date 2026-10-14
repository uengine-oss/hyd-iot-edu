#!/usr/bin/env python3
"""아스트라의 재개·부분 읽기·덱 검사. 표준 라이브러리만 사용한다.

원문 규칙이나 빌더를 복제하지 않는다. 출력한 범위는 이해의 증명이 아니다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPACE = ROOT / ".astra"
BUILDER = ".claude/skills/lecture-deck/scripts/deck2pptx.py"
LEDGER = SPACE / "reading.json"
CHECKS = SPACE / "checks.json"
STATE = SPACE / "state.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save(path: Path, data: dict) -> None:
    # 하나의 작성자만 갱신한다. 검토자에게 이 파일을 쓰게 하지 않는다.
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def relative_file(name: str) -> Path:
    p = (ROOT / name).resolve()
    try:
        rel = p.relative_to(ROOT)
    except ValueError:
        raise ValueError("저장소 안의 상대 경로만 사용한다") from None
    if Path(name).is_absolute() or not p.is_file():
        raise ValueError(f"읽을 수 없는 상대 파일 경로: {name}")
    if any(x in {".git", ".aws", ".codex"} for x in rel.parts) or p.name.startswith(".env"):
        raise ValueError("인증·환경·Git 내부 파일은 이 읽기 도구로 다루지 않는다")
    return p


def git(*args: str) -> str:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        raise ValueError(r.stderr.strip())
    return r.stdout


def source(name: str, rev: str | None = None) -> tuple[str, str, str]:
    # 삭제된 옛 파일도 git에서 읽을 수 있게 현재 파일의 존재는 요구하지 않는다.
    if rev:
        p = (ROOT / name).resolve()
        if Path(name).is_absolute() or not p.is_relative_to(ROOT):
            raise ValueError("저장소 안의 상대 경로만 사용한다")
        rel = p.relative_to(ROOT).as_posix()
        if any(x in {".git", ".aws", ".codex"} for x in p.relative_to(ROOT).parts) or p.name.startswith(".env"):
            raise ValueError("인증·환경·Git 내부 파일은 읽지 않는다")
        commit = git("rev-parse", "--verify", "--end-of-options", rev + "^{commit}").strip()
        text = git("show", f"{commit}:{rel}")
        return f"{commit}:{rel}", text, sha(text.encode())
    p = relative_file(name)
    raw = p.read_bytes()
    return p.relative_to(ROOT).as_posix(), raw.decode("utf-8"), sha(raw)


def merge_ranges(ranges: list[list[int]]) -> list[list[int]]:
    out: list[list[int]] = []
    for start, end in sorted(ranges):
        if out and start <= out[-1][1] + 1:
            out[-1][1] = max(end, out[-1][1])
        else:
            out.append([start, end])
    return out


def remember(key: str, digest: str, ranges: list[list[int]], note: str = "도구가 출력한 범위") -> None:
    if not ranges:
        return
    data = load(LEDGER)
    old = data.get(key, {})
    previous = old.get("ranges", []) if old.get("sha256") == digest else []
    data[key] = {"sha256": digest, "ranges": merge_ranges(previous + ranges), "basis": note}
    save(LEDGER, data)


def emit(key: str, text: str, digest: str, ranges: list[list[int]], limit: int) -> None:
    lines = text.splitlines()
    count = 0
    shown: list[list[int]] = []
    print(f"{key} | SHA256 {digest[:12]} | 전체 {len(lines)}줄")
    for start, end in ranges:
        if start < 1 or end < start or end > len(lines):
            raise ValueError(f"잘못된 범위 {start}:{end} (전체 {len(lines)}줄)")
        for n in range(start, end + 1):
            row = f"{n}: {lines[n-1]}"
            if count + len(row) + 1 > limit:
                if n > start:
                    shown.append([start, n - 1])
                remember(key, digest, shown, "도구가 실제 출력한 줄; 이해·검토 완료를 뜻하지 않음")
                print(f"[출력 한도] 다음은 {n}줄부터. 이 뒤는 읽기 기록에 넣지 않았다.")
                return
            print(row)
            count += len(row) + 1
        shown.append([start, end])
    remember(key, digest, shown, "도구가 실제 출력한 줄; 이해·검토 완료를 뜻하지 않음")


def deck(day: int) -> str:
    return f"만들기/decks/integrated/day{day:02}/통합반_{day:02}일차.md"


def facts(day: int) -> str:
    span = "01" if day == 1 else "02-04" if day <= 4 else "05-08" if day <= 8 else "09-11"
    return f"문서/교재/사실표/통합반_{span}일차_기술사실표.md"


def slides(text: str) -> list[tuple[int, str, int, int]]:
    lines = text.splitlines()
    hits = [(i + 1, re.match(r"^## SLIDE (\d+)\s*[—–-]\s*(.*)$", ln)) for i, ln in enumerate(lines)]
    found = [(line, m) for line, m in hits if m]
    return [(int(m[1]), m[2], start, found[i+1][0]-1 if i+1 < len(found) else len(lines))
            for i, (start, m) in enumerate(found)]


def inputs(day: int) -> str:
    """검사 관련 파일/환경이 바뀌면 이전 결과를 무효화하는 보수적인 지문."""
    md = relative_file(deck(day))
    files = {md}
    for line in md.read_text(encoding="utf-8").splitlines():
        if line.startswith("- 그림:"):
            image = md.parent / line.split(":", 1)[1].strip()
            files.add(relative_file(image.relative_to(ROOT).as_posix()))
    # 빌더가 사용하는 글꼴 배치·아이콘·로고를 놓치지 않는다. 캐시/문서는 제외.
    for path in (ROOT / ".claude/skills/lecture-deck").rglob("*"):
        if path.is_file() and path.suffix in {".py", ".svg", ".png"} and "__pycache__" not in path.parts:
            files.add(path)
    h = hashlib.sha256()
    for p in sorted(files):
        h.update(p.relative_to(ROOT).as_posix().encode() + b"\0" + p.read_bytes() + b"\0")
    runtime = ROOT / ".venv-deck/bin/python"
    if runtime.exists():
        r = subprocess.run([str(runtime), "-c", "import sys,importlib.metadata as m; print(sys.version); print([(x,m.version(x)) for x in ['python-pptx','PyMuPDF','Pillow']])"],
                           capture_output=True, timeout=20)
        if r.returncode:
            raise ValueError("덱 검사 환경의 패키지 버전을 확인하지 못했다")
        h.update(r.stdout)
    else:
        h.update(b"no-deck-python")
    return h.hexdigest()


def status(day: int, kind: str) -> None:
    state = load(STATE)
    print(f"HEAD {git('rev-parse', '--short', 'HEAD').strip()} | 작업: {state.get('task', '미설정')}")
    print(f"상태: {state.get('status', '미설정')} | 다음: {state.get('next_action', '사용자 요청 확인')}")
    changes = git("-c", "core.quotePath=false", "status", "--short").splitlines()
    print(f"작업 트리: 변경 {len(changes)}개 (내용은 git diff로 확인)")
    for ln in changes[:20]:
        print(ln)
    if len(changes) > 20:
        print(f"… {len(changes)-20}개 생략")
    paths = ["문서/교재/2_기준.md", "문서/교재/3_현황.md", "문서/교재/5_결정_기록.md", "문서/교재/6_남은_일.md", deck(day), facts(day)]
    paths += [".claude/skills/hyd-course-deck/SKILL.md", ".claude/skills/lecture-deck/references/덱MD-PPTX형식.md"]
    if kind == "design":
        paths += [str(p.relative_to(ROOT)) for p in sorted((ROOT / "문서/교재/압축_설계").glob("*.md"))]
    if kind == "script":
        paths += ["문서/교재/4_만드는_법.md"] + [str(p.relative_to(ROOT)) for p in sorted((ROOT / "산출물/교재/대본/통합반_온라인").glob(f"통합반_{day:02}일차*md"))]
    data = load(LEDGER)
    print("자료 경로와 출력/검토 기록 (같은 해시 ≠ 지금 이해하고 있음):")
    for name in paths:
        p = ROOT / name
        if not p.is_file():
            label = "없음"
        elif name not in data:
            label = "기록 없음"
        elif data[name]["sha256"] != sha(p.read_bytes()):
            label = "변경됨 — 원문/차이 확인"
        else:
            ranges = data[name]["ranges"]
            label = "동일 " + ",".join(f"{a}-{b}" for a,b in ranges)
        print(f"  [{label}] {name}")
    n = len(slides((ROOT / deck(day)).read_text(encoding="utf-8")))
    print(f"현재 {day}회차: {n}장. 실라버스: 문서/교재/실라버스/피지컬AI_실라버스_최종본.xlsx")
    result = load(CHECKS).get(str(day))
    valid = bool(result and result.get("passed") and result.get("inputs") == inputs(day))
    print("자동 검사: " + ("현재 입력과 같은 성공 기록 있음" if valid else "현재 입력의 성공 기록 없음/낡음"))
    print(f"직접 검사: python3 .astra/context.py check --day {day} (항상 빌더를 실행)")
    print("작업별 도구·원문 위치: .astra/README.md. 렌더·사실·누락 검토는 자동 검사와 별도다.")


def check(day: int) -> int:
    runtime = ROOT / ".venv-deck/bin/python"
    if not runtime.is_file():
        raise ValueError(".venv-deck/bin/python 없음 — 환경을 확인한다. 자동 설치하지 않는다")
    before = inputs(day)
    # 인수를 고정하고 원래 빌더를 그대로 쓴다. 캐시로 실제 검사를 대신하지 않는다.
    r = subprocess.run([str(runtime), BUILDER, "--check", deck(day)], cwd=ROOT, capture_output=True, text=True)
    output = r.stdout + r.stderr
    print(output, end="")
    after = inputs(day)
    passed = r.returncode == 0 and "[검사 통과]" in output and before == after
    data = load(CHECKS)
    data[str(day)] = {"inputs": after, "passed": passed, "returncode": r.returncode,
                      "at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                      "result": next((x for x in output.splitlines() if "[검사 통과]" in x), "실패 — 이번 실행 출력을 확인"),
                      "scope": "형식·넘침 추정·라벨 간격. 사실·전 장 시각 검토의 증명은 아님"}
    save(CHECKS, data)
    if before != after:
        print("[무효] 검사 도중 입력이 바뀌었다. 동시 수정을 끝낸 뒤 다시 검사한다.")
    return 0 if passed else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("status", help="짧은 재개 정보, 자료 경로, 변경/검사 유효성")
    s.add_argument("--kind", choices=["deck", "design", "polish", "script"], default="deck")
    for cmd in [s, sub.add_parser("check", help="기존 --check를 실행하고 입력 지문과 결과 기록")]:
        cmd.add_argument("--day", type=int, choices=range(1,12), required=True)
    read = sub.add_parser("read", help="원문을 줄 번호와 함께 필요한 범위만 출력")
    read.add_argument("path")
    read.add_argument("--start", type=int, default=1)
    read.add_argument("--end", type=int)
    for cmd in [read, sub.add_parser("outline", help="현재/옛 덱의 장 목록, 내용 보존을 판정하지는 않음"), sub.add_parser("slides", help="지정한 장의 화면·노트·근거를 모두 출력")]:
        cmd.add_argument("--rev", help="예: e0311fe. 생략하면 작업 트리")
        if cmd is not read:
            cmd.add_argument("--day", type=int, choices=range(1,12), required=True)
        if cmd.prog.endswith("slides"):
            cmd.add_argument("--numbers", required=True, help="예: 17-19,25")
        if not cmd.prog.endswith("outline"):
            cmd.add_argument("--limit", type=int, default=16000, help="최대 출력 문자 수; 잘린 줄은 기록하지 않음")
    args = ap.parse_args()
    try:
        if args.cmd == "status":
            status(args.day, args.kind)
        elif args.cmd == "check":
            return check(args.day)
        else:
            key, text, digest = source(args.path if args.cmd == "read" else deck(args.day), args.rev)
            if args.cmd == "outline":
                for number, title, start, end in slides(text):
                    print(f"{number:02} | {start}-{end} | {title}")
                print("장 목록만 출력했다. 본문 읽기 기록은 갱신하지 않았다.")
            else:
                if args.limit < 100:
                    raise ValueError("--limit는 100 이상이어야 한다")
                if args.cmd == "read":
                    ranges = [[args.start, args.end or len(text.splitlines())]]
                else:
                    nums = set()
                    for token in args.numbers.split(","):
                        a, sep, b = token.partition("-")
                        first, last = int(a), int(b) if sep else int(a)
                        if first < 1 or last < first:
                            raise ValueError("잘못된 장 번호 범위")
                        nums.update(range(first, last+1))
                    blocks = slides(text)
                    if nums - {n for n, *_ in blocks}:
                        raise ValueError("없는 장 번호가 있다")
                    ranges = [[a,b] for n, _, a,b in blocks if n in nums]
                emit(key, text, digest, ranges, args.limit)
    except (ValueError, OSError, UnicodeError, subprocess.TimeoutExpired) as e:
        print(f"[오류] {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
