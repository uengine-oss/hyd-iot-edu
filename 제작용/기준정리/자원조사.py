"""레포 리소스 전수 조사 — 쓰인다는 증거가 있는지 적대적으로 본다.

사용: PYTHONUTF8=1 .venv314/Scripts/python 제작용/기준정리/자원조사.py
출력: 문서/교재/근거/기준정리/자원목록.tsv

단위: 추적 파일을 폴더 단위(아래 UNIT 깊이)로 묶는다. 단위마다
  파일 수 · 바이트 · 마지막 커밋일 · 같은 바이트 사본(다른 단위에 같은 해시) ·
  들어오는 참조(살아 있는 문서 · 스킬 · 코드가 그 단위의 경로나 파일 이름을 언급한 수)를 잰다.
살아 있는 참조 원본 = 근거/ · 5_결정_기록 · 산출물 대본 본문을 뺀 텍스트 파일(이력에서만 언급되면 쓰임이 아니다).
"""
from __future__ import annotations

import csv
import hashlib
import re
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "문서/교재/근거/기준정리/자원목록.tsv"

SYSTEM = {"it", "tests", "scripts", "common", "ot", "dmz", ".dockerignore", ".gitattributes",
          ".gitignore", ".env.example", "compose.yaml", "compose.classroom.yaml", "pytest.ini",
          "requirements-dev.txt"}
# 폴더별 묶는 깊이(경로 조각 수)
UNIT = {"제작용": 3, "산출물": 4, "course": 3, "students": 3, ".claude": 3, "문서": 3}
TEXT = {".md", ".py", ".json", ".txt", ".html", ".sh", ".mjs", ".js", ".yaml", ".yml", ".toml",
        ".cmd", ".bat", ".command", ".csv", ".cypher"}
HISTORY = re.compile(r"^(문서/교재/근거/|문서/교재/5_결정_기록\.md|문서/시스템/검증_기록/|문서/시스템/5_결정_기록\.md)")


def git(*args: str) -> str:
    return subprocess.run(["git", "-c", "core.quotepath=off", *args], cwd=ROOT, capture_output=True,
                          check=True).stdout.decode("utf-8", "replace")


def unit_of(path: str) -> str:
    parts = path.split("/")
    depth = UNIT.get(parts[0], 1)
    return "/".join(parts[:depth]) if len(parts) > depth else path


def main() -> None:
    files = [f for f in git("ls-files", "-z").split("\0") if f]
    last = {}
    # 마지막 커밋일: 파일별로 한 번에(log 이름 목록을 거꾸로 훑는다)
    for block in git("log", "--format=@%cs", "--name-only").split("@")[1:]:
        lines = block.strip().splitlines()
        if not lines:
            continue
        day = lines[0]
        for f in lines[1:]:
            last.setdefault(f.strip(), day)
    units: dict[str, dict] = defaultdict(lambda: {"files": 0, "bytes": 0, "last": "", "hashes": set(), "names": set()})
    owner: dict[str, str] = {}
    hash_units: dict[str, set] = defaultdict(set)
    for f in files:
        p = ROOT / f
        if not p.is_file():
            continue
        u = unit_of(f)
        owner[f] = u
        d = units[u]
        data = p.read_bytes()
        d["files"] += 1
        d["bytes"] += len(data)
        d["last"] = max(d["last"], last.get(f, ""))
        h = hashlib.sha1(data).hexdigest()
        d["hashes"].add(h)
        hash_units[h].add(u)
        d["names"].add(Path(f).name)
    # 살아 있는 텍스트 원본 읽기
    live = []
    for f in files:
        if HISTORY.match(f) or Path(f).suffix.lower() not in TEXT:
            continue
        p = ROOT / f
        if p.is_file() and p.stat().st_size < 2_000_000:
            live.append((f, p.read_text(encoding="utf-8", errors="replace")))
    rows = []
    for u, d in sorted(units.items()):
        needles = {u}
        if "/" in u:
            needles.add(u.split("/")[-1])
        # 단위가 파일 하나면 이름, 폴더면 폴더 이름과 그 안의 고유한 파일 이름 몇 개
        refs_from = set()
        for f, text in live:
            if owner.get(f) == u:
                continue
            for n in needles:
                if len(n) >= 4 and n in text:
                    refs_from.add(f)
                    break
        dup = sorted({x for h in d["hashes"] for x in hash_units[h] if x != u})
        top = u.split("/")[0]
        rows.append({
            "단위": u, "구역": "시스템" if top in SYSTEM else top, "파일수": d["files"], "바이트": d["bytes"],
            "마지막커밋": d["last"], "살아있는참조수": len(refs_from),
            "참조예": "; ".join(sorted(refs_from)[:4]), "같은바이트사본단위": "; ".join(dup[:4]),
        })
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print("단위", len(rows), "참조 0:", sum(1 for r in rows if r["살아있는참조수"] == 0))


if __name__ == "__main__":
    main()
