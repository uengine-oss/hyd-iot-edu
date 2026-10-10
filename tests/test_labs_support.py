"""랩 키트 시험이 함께 쓰는 경로와 불러오기. 키트와 강사용 도구를 import 경로에 넣는다."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LABS = REPO / "students" / "labs"
KIT = LABS / "kit"
INSTRUCTOR = LABS / "instructor"
ANSWERS = INSTRUCTOR / "answers"

for entry in (KIT, INSTRUCTOR, INSTRUCTOR / "tools"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))
