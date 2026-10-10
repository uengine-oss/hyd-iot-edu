"""강사용 도구가 함께 쓰는 경로. 키트 폴더를 import 경로에 넣는다."""
from __future__ import annotations

import sys
from pathlib import Path

LABS_ROOT = Path(__file__).resolve().parents[2]
KIT = LABS_ROOT / "kit"
ANSWERS = LABS_ROOT / "instructor" / "answers"

for entry in (KIT, KIT / "day6" / "judge_mcp", ANSWERS / "work"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))
