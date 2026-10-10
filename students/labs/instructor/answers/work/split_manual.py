"""매뉴얼을 절(구간)로 나누고 줄 번호를 보존해 sections.json 으로 저장한다."""
from __future__ import annotations

import json
import re
from pathlib import Path

from labkit.settings import KIT_ROOT

MANUAL_FILE = KIT_ROOT / "day4" / "manual" / "cooler_manual.md"
OUTPUT_FILE = Path(__file__).with_name("sections.json")
SECTION_HEADING = re.compile(r"^## (\d+)\. (.+)$")


def split_sections(text: str) -> list[dict]:
    sections: list[dict] = []
    for number, line in enumerate(text.splitlines(), start=1):
        heading = SECTION_HEADING.match(line)
        if heading:
            sections.append({"section": heading.group(1), "title": heading.group(2), "line_start": number, "line_end": number, "lines": []})
        elif sections and line.strip():
            sections[-1]["lines"].append({"line": number, "text": line})
            sections[-1]["line_end"] = number
    return sections


def main() -> None:
    sections = split_sections(MANUAL_FILE.read_text(encoding="utf-8"))
    OUTPUT_FILE.write_text(json.dumps(sections, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(sections)}개 절, 본문 {sum(len(s['lines']) for s in sections)}줄을 {OUTPUT_FILE.name} 에 저장")


if __name__ == "__main__":
    main()
