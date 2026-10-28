"""누락 검사(기계) — 모두 0이어야 그 갈래를 통과한다.

사용:
  PYTHONUTF8=1 .venv314/Scripts/python 제작용/기준정리/누락검사.py S L      # 다 쓴 갈래만 핵심어 검사
  PYTHONUTF8=1 .venv314/Scripts/python 제작용/기준정리/누락검사.py --옛참조 기준_이론대본.md 기준_실습대본.md
  PYTHONUTF8=1 .venv314/Scripts/python 제작용/기준정리/누락검사.py --자가시험 S

검사:
  1. 장부의 모든 행에 표기법에 맞는 갈곳이 있다.
  2. 인자로 준 갈래의 `옮김`·`합침`·`충돌` 행(충돌은 메모에 「결정:」이 적힌 뒤)의 핵심어가
     새 문서의 그 절(`## S6 …` 머리부터 다음 `## ` 전까지)에 실제로 있다. `[묶음]` 꼴 낱말은 묶음 이름이라 빼고 본다.
     `합침 <번호>`는 대표 행의 절에서 찾는다.
  3. `--옛참조 <파일이름…>`: 살아 있는 파일(CLAUDE.md · AGENTS.md · .claude/skills · 문서/교재 최상위 · 제작용 md)에
     옛 문서 이름이 남아 있지 않다(근거/ · 5_결정_기록 · 장부 자체는 뺀다).
  --자가시험: 장부의 첫 `옮김` 행 갈곳을 지우고, 첫 핵심어를 문서에서 지운 사본으로 돌려 둘 다 잡히는지 본다.
"""
from __future__ import annotations

import csv
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "문서/교재/근거/기준정리/장부.tsv"
DOCS = {
    "G": "문서/교재/기준_공통.md", "D": "문서/교재/기준_이론덱.md", "S": "문서/교재/기준_대본.md",
    "L": "문서/교재/기준_실습랩.md", "C": "문서/교재/기준_촬영.md", "H": "문서/교재/기준_실습가이드.md",
}
DEST = re.compile(r"^(옮김 [GDSLCH]\d|합침 \S+|충돌 .+|이력|상태|도구|안내|시스템|폐기: .+)$")
TAG = re.compile(r"^\[.*\]$")


def load() -> list[dict]:
    with LEDGER.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def section_text(doc: str, sec: str) -> str:
    out, on = [], False
    for line in doc.splitlines():
        if line.startswith("## "):
            on = line[3:].strip().startswith(sec)
        if on:
            out.append(line)
    return "\n".join(out)


def check(rows: list[dict], branches: list[str], docs: dict[str, str]) -> list[str]:
    errs: list[str] = []
    by_id = {r["번호"]: r for r in rows}
    for r in rows:
        if r["메모"].startswith("원본변경"):
            continue
        if not DEST.match(r["갈곳"].strip()):
            errs.append(f"{r['번호']} ({r['파일']}:{r['줄']}): 갈곳 없음/표기 오류 {r['갈곳']!r}")
    for r in rows:
        dest = r["갈곳"].strip()
        target = r
        if dest.startswith("합침 "):
            target = by_id.get(dest.split()[1])
            if target is None:
                errs.append(f"{r['번호']}: 합침 대상 {dest.split()[1]} 이 장부에 없음")
                continue
        elif dest.startswith("충돌 "):
            if "결정:" not in r["메모"]:
                if r["갈래"] in branches:
                    errs.append(f"{r['번호']}: 충돌 미결정(메모에 「결정:」 없음)")
                continue
        tdest = target["갈곳"].strip()
        if not tdest.startswith("옮김 "):
            continue
        sec = tdest.split()[1]
        if sec[0] not in branches:
            continue
        text = section_text(docs.get(sec[0], ""), sec)
        if not text:
            errs.append(f"{r['번호']}: 새 문서에 절 {sec} 없음 ({DOCS[sec[0]]})")
            continue
        for kw in [k.strip() for k in r["핵심어"].split(";") if k.strip()]:
            if TAG.match(kw):
                continue
            if kw not in text:
                errs.append(f"{r['번호']} ({r['파일']}:{r['줄']}): 핵심어 {kw!r} 이 {DOCS[sec[0]]} {sec}에 없음")
    return errs


def old_refs(names: list[str]) -> list[str]:
    files = subprocess.run(["git", "-c", "core.quotepath=off", "ls-files", "-z"], cwd=ROOT,
                           capture_output=True, check=True).stdout.decode().split("\0")
    live = [f for f in files if f and (
        f in ("CLAUDE.md", "AGENTS.md") or f.startswith(".claude/skills/")
        or (f.startswith("문서/교재/") and f.count("/") == 2 and f != "문서/교재/5_결정_기록.md")
        or (f.startswith("제작용/") and f.endswith(".md") and not f.startswith("제작용/기준정리/")))]
    errs = []
    for f in live:
        p = ROOT / f
        if not p.is_file() or p.suffix not in {".md", ".py", ".json", ".txt"}:
            continue
        for no, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for n in names:
                if n in line:
                    errs.append(f"{f}:{no}: 옛 문서 참조 {n}")
    return errs


def main(argv: list[str]) -> int:
    if argv and argv[0] == "--옛참조":
        errs = old_refs(argv[1:])
    else:
        selftest = bool(argv) and argv[0] == "--자가시험"
        branches = [a for a in argv if not a.startswith("--")]
        rows = load()
        docs = {k: (ROOT / v).read_text(encoding="utf-8") if (ROOT / v).exists() else "" for k, v in DOCS.items()}
        if selftest:
            base = check(rows, branches, docs)
            victim = next(r for r in rows if r["갈곳"].startswith("옮김 ") and r["갈래"] in branches and r["핵심어"])
            kw = next(k.strip() for k in victim["핵심어"].split(";") if k.strip() and not TAG.match(k.strip()))
            broken_rows = [dict(r) for r in rows]
            for r in broken_rows:
                if r["번호"] == victim["번호"]:
                    r["갈곳"] = ""
            broken_docs = dict(docs)
            sec = victim["갈곳"].split()[1]
            broken_docs[sec[0]] = docs[sec[0]].replace(kw, "")
            e1 = [e for e in check(broken_rows, branches, docs) if e not in base]
            e2 = [e for e in check(rows, branches, broken_docs) if e not in base]
            print(f"자가시험: 갈곳 지운 행 {victim['번호']} → 새 오류 {len(e1)}개, 핵심어 {kw!r} 지움 → 새 오류 {len(e2)}개")
            return 0 if e1 and e2 else 1
        errs = check(rows, branches, docs)
    print(*errs[:200], sep="\n")
    print(f"오류 {len(errs)}")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
