"""키트 자료(CSV · 매뉴얼 · 준비된 후보)에서 기대 사실을 읽어 낸다. 정답을 따로 적어 두지 않고 자료에서 계산한다."""
from __future__ import annotations

import csv
import json
import re
from functools import lru_cache

from labkit.settings import KIT_ROOT

MANUAL_FILE = KIT_ROOT / "day4" / "manual" / "cooler_manual.md"
CANDIDATES_FILE = KIT_ROOT / "day4" / "candidates" / "prepared_candidates.json"
SECTION_HEADING = re.compile(r"^## (\d+)\. (.+)$")
RELATION_ENDS = {"INDICATES": ("Symptom", "FailureMode"), "CAUSES": ("Cause", "FailureMode"), "REMEDIED_BY": ("FailureMode", "Action")}


def read_csv(relative: str) -> list[dict[str, str]]:
    with (KIT_ROOT / relative).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_kit_json(relative: str):
    return json.loads((KIT_ROOT / relative).read_text(encoding="utf-8"))


@lru_cache
def manual_sections() -> tuple[dict, ...]:
    """매뉴얼의 절마다 본문 줄(빈 줄 제외)과 줄 번호."""
    sections: list[dict] = []
    for number, line in enumerate(MANUAL_FILE.read_text(encoding="utf-8").splitlines(), start=1):
        heading = SECTION_HEADING.match(line)
        if heading:
            sections.append({"section": heading.group(1), "title": heading.group(2), "lines": {}})
        elif sections and line.strip():
            sections[-1]["lines"][number] = line
    return tuple(sections)


def manual_line(section: str, line: int) -> str | None:
    for part in manual_sections():
        if part["section"] == str(section):
            return part["lines"].get(line)
    return None


def source_problem(source: dict, names: list[str]) -> str | None:
    """출처가 원문으로 확인되면 None, 아니면 무엇이 어긋났는지."""
    quote = source.get("quote") or ""
    text = manual_line(str(source.get("section")), source.get("line"))
    if text is None:
        return f"{source.get('section')}절 {source.get('line')}줄에 본문이 없습니다."
    if not quote or quote not in text:
        return f"{source.get('section')}절 {source.get('line')}줄의 원문과 인용 문장이 다릅니다."
    absent = [name for name in names if name not in quote]
    if absent:
        return f"인용 문장에 {absent} 이(가) 나오지 않습니다. 원문이 말하지 않은 연결입니다."
    return None


@lru_cache
def prepared_candidates() -> tuple[dict, ...]:
    return tuple(read_kit_json("day4/candidates/prepared_candidates.json")["candidates"])


def candidate_problem(candidate: dict) -> str | None:
    return source_problem(candidate["source"], [candidate["from"]["name"], candidate["to"]["name"]])


def valid_candidate_ids() -> set[str]:
    return {candidate["id"] for candidate in prepared_candidates() if candidate_problem(candidate) is None}


def mapped_assets(doc: str) -> set[str]:
    return {row["asset_id"] for row in read_csv("day4/data/id_mapping.csv") if row["doc_id"] == doc}
