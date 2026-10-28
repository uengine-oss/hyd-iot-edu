"""기준 정리 장부 만들기 — 원본 문서를 문장 단위로 번호 붙여 TSV로 낸다.

사용: PYTHONUTF8=1 .venv314/Scripts/python 제작용/기준정리/장부.py
출력: 문서/교재/근거/기준정리/장부.tsv, 파일목록.tsv

이미 장부가 있으면 갈 곳·핵심어·메모 열은 (파일, 원문)이 같은 행에서 이어받는다.
원본 문장이 바뀌었으면 새 행이 되고, 사라진 옛 행은 '원본변경' 표시로 남는다(지우지 않는다).
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "문서/교재/근거/기준정리"
LEDGER = OUT / "장부.tsv"

# 코드, 경로, 원래 쓰임(분류 1단계)
SOURCES: list[tuple[str, str, str]] = [
    # 기준 문서 9개
    ("기준", "문서/교재/2_기준.md", "기준"),
    ("만법", "문서/교재/4_만드는_법.md", "기준"),
    ("이덱", "문서/교재/기준_이론덱.md", "기준"),
    ("이대", "문서/교재/기준_이론대본.md", "기준"),
    ("실대", "문서/교재/기준_실습대본.md", "기준"),
    ("실랩", "문서/교재/기준_실습랩.md", "기준"),
    ("실가", "문서/교재/기준_실습가이드.md", "기준"),
    ("검마", "문서/교재/검증과마감.md", "기준"),
    ("실전", "문서/교재/실전반_기준.md", "기준"),
    # 촬영 안내·도구별 촬영준비
    ("촬안", "문서/교재/방법_ego_실습영상_촬영.md", "기준"),
    ("촬AR", "제작용/촬영/arrows/촬영준비.md", "기준"),
    ("촬N4", "제작용/촬영/neo4j/촬영준비.md", "기준"),
    ("촬NO", "제작용/촬영/notion/촬영준비.md", "기준"),
    ("촬VS", "제작용/촬영/vscode/촬영준비.md", "기준"),
    ("촬포", "제작용/촬영/포털/촬영준비.md", "기준"),
    ("촬환", "제작용/촬영/환경세팅/촬영준비.md", "기준"),
    ("촬EG", "제작용/촬영/ego/README.md", "기준"),
    # 프로젝트 계약
    ("클로", "CLAUDE.md", "계약"),
    ("에이", "AGENTS.md", "계약"),
    # 사용자 지시
    ("사용", "문서/교재/근거/2026-10-28_사용자_실습제작절차.md", "지시"),
    # 기록
    ("목적", "문서/교재/1_목적과_방향.md", "기록"),
    ("현황", "문서/교재/3_현황.md", "기록"),
    ("남일", "문서/교재/6_남은_일.md", "기록"),
    ("작상", "문서/교재/작업상태.md", "기록"),
    ("실목", "문서/교재/실습_목록.md", "기록"),
    ("온산", "문서/교재/온라인_최종산출물_목록.md", "기록"),
    ("대조", "문서/교재/대화결정_인계대조표.md", "기록"),
    # 인계
    ("인5", "문서/교재/인계_5분샘플_제작검증.md", "인계"),
    ("인기", "문서/교재/인계_기준정리와레포청소.md", "인계"),
    ("인노", "문서/교재/인계_노션디자인.md", "인계"),
    ("인실", "문서/교재/인계_실습제작과배포.md", "인계"),
    ("인영", "문서/교재/인계_영상과대본점검.md", "인계"),
    ("인오", "문서/교재/인계_오프라인이론덱.md", "인계"),
    ("세A", "문서/교재/세션인계_A_교재재편.md", "인계"),
    ("세B", "문서/교재/세션인계_B_VSCode실습.md", "인계"),
    ("세분", "문서/교재/세션분담_교재와실습_20261027.md", "인계"),
    # 요청문(옛 지시문)
    ("요A", "문서/교재/요청문_Claude_A_교재재편.md", "요청문"),
    ("요B", "문서/교재/요청문_Claude_B_VSCode실습촬영가이드.md", "요청문"),
    ("요AB", "문서/교재/요청문_Claude_교재재편과VSCode촬영.md", "요청문"),
    ("요이", "문서/교재/요청문_실습_이어가기.md", "요청문"),
    ("요영", "문서/교재/요청문_실습영상_새세션.md", "요청문"),
    ("요제", "문서/교재/요청문_실습제작_새세션.md", "요청문"),
    # 스킬
    ("SK덱", ".claude/skills/hyd-course-deck/SKILL.md", "스킬"),
    ("SK가", ".claude/skills/hyd-lab-guide/SKILL.md", "스킬"),
    ("SK영", ".claude/skills/hyd-lecture-video/SKILL.md", "스킬"),
    ("SK포", ".claude/skills/hyd-portal-video/SKILL.md", "스킬"),
    ("SK읽", ".claude/skills/README.md", "스킬"),
    ("LC읽", ".claude/skills/lecture-common/README.md", "스킬"),
    ("LC입", ".claude/skills/lecture-common/rules/skill-admission.md", "스킬"),
    ("LC규", ".claude/skills/lecture-common/rules/스킬-공식규격.md", "스킬"),
    ("LC공", ".claude/skills/lecture-common/공통기준.md", "스킬"),
    ("LD스", ".claude/skills/lecture-deck/SKILL.md", "스킬"),
    ("LD형", ".claude/skills/lecture-deck/references/덱MD-PPTX형식.md", "스킬"),
    ("LD문", ".claude/skills/lecture-deck/references/문체.md", "스킬"),
    ("LV스", ".claude/skills/lecture-deliver/SKILL.md", "스킬"),
    ("LL스", ".claude/skills/lecture-lab/SKILL.md", "스킬"),
    ("LL원", ".claude/skills/lecture-lab/assets/setup-guide-reference/original-instructions.md", "스킬"),
    ("LLH", ".claude/skills/lecture-lab/references/HTML실습가이드.md", "스킬"),
    ("LL도", ".claude/skills/lecture-lab/references/그림도구.md", "스킬"),
    ("LL그", ".claude/skills/lecture-lab/references/그림요구.md", "스킬"),
    ("LLP", ".claude/skills/lecture-lab/references/세팅가이드-PDF.md", "스킬"),
    ("LL틀", ".claude/skills/lecture-lab/references/실습가이드-틀.md", "스킬"),
    ("LP스", ".claude/skills/lecture-plan/SKILL.md", "스킬"),
    ("LP근", ".claude/skills/lecture-plan/references/evidence-led-authoring.md", "스킬"),
    ("LP외", ".claude/skills/lecture-plan/references/외부자료반영.md", "스킬"),
    ("LR스", ".claude/skills/lecture-verify/SKILL.md", "스킬"),
]

COLUMNS = ["번호", "코드", "파일", "줄", "쓰임", "절", "원문", "갈래", "갈곳", "핵심어", "메모"]
CARRY = ["갈래", "갈곳", "핵심어", "메모"]

LIST_MARK = re.compile(r"^(\s*(?:[-*+]|\d+(?:-\d+)?[.)])\s+)")
# 문장 끝: 마침표·물음표·느낌표 뒤 공백. 소수점·파일 확장자는 뒤에 공백이 없어 갈라지지 않는다.
SENT_END = re.compile(r"(?<=[.!?。])\s+(?=\S)")
TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{3,}")


def split_sentences(text: str) -> list[str]:
    parts = [p.strip() for p in SENT_END.split(text)]
    out: list[str] = []
    for p in parts:
        if not p:
            continue
        # 「1.」 「v2.」 같은 짧은 조각은 앞 문장에 붙인다
        if out and len(p) <= 3:
            out[-1] += " " + p
        else:
            out.append(p)
    return out


def units(path: Path):
    """(줄, 절, 원문) 단위를 낸다. 표 행은 행 하나가 한 단위, 나머지는 문장 단위."""
    section = ""
    in_code = False
    for no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.rstrip()
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if not line.strip():
            continue
        if in_code:
            yield no, section, line.strip()
            continue
        if line.lstrip().startswith("#"):
            section = line.lstrip("# ").strip()
            yield no, section, line.strip()
            continue
        if TABLE_SEP.match(line):
            continue
        if line.lstrip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            yield no, section, " | ".join(c for c in cells if c)
            continue
        m = LIST_MARK.match(line)
        prefix = m.group(1).strip() + " " if m else ""
        body = line[m.end():] if m else line.strip()
        sents = split_sentences(body)
        for i, s in enumerate(sents):
            yield no, section, (prefix + s) if i == 0 else s


def load_old() -> dict[tuple[str, str], list[dict]]:
    old: dict[tuple[str, str], list[dict]] = {}
    if LEDGER.exists():
        with LEDGER.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f, delimiter="\t"):
                old.setdefault((row["파일"], row["원문"]), []).append(row)
    return old


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    old = load_old()
    used: set[int] = set()
    rows: list[dict] = []
    missing = []
    for code, rel, kind in SOURCES:
        p = ROOT / rel
        if not p.exists():
            missing.append(rel)
            continue
        seq: dict[int, int] = {}
        for no, sec, text in units(p):
            seq[no] = seq.get(no, 0) + 1
            row = {
                "번호": f"{code}-{no:03d}-{seq[no]}", "코드": code, "파일": rel, "줄": str(no),
                "쓰임": kind, "절": sec, "원문": text, "갈래": "", "갈곳": "", "핵심어": "", "메모": "",
            }
            for prev in old.get((rel, text), []):
                if id(prev) not in used:
                    used.add(id(prev))
                    for c in CARRY:
                        row[c] = prev.get(c, "")
                    break
            rows.append(row)
    # 원본에서 사라진 옛 행은 지우지 않고 표시해 남긴다
    for lst in old.values():
        for prev in lst:
            if id(prev) not in used and not prev["메모"].startswith("원본변경"):
                prev["메모"] = "원본변경: 원문이 원본에 더는 없음. " + prev.get("메모", "")
                rows.append(prev)
            elif id(prev) not in used:
                rows.append(prev)
    if missing:
        print("원본 없음:", *missing, sep="\n  ", file=sys.stderr)
        return 1
    with LEDGER.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, delimiter="\t", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    by: dict[str, int] = {}
    for r in rows:
        by[r["쓰임"]] = by.get(r["쓰임"], 0) + 1
    print(f"행 {len(rows)}", by)
    return 0


if __name__ == "__main__":
    sys.exit(main())
