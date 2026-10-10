"""강사용 도구가 함께 쓰는 경로. 키트 폴더를 import 경로에 넣고, 이름이 흔한 모듈은 파일 경로로 불러온다."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

LABS_ROOT = Path(__file__).resolve().parents[2]
KIT = LABS_ROOT / "kit"
ANSWERS = LABS_ROOT / "instructor" / "answers"

if str(KIT) not in sys.path:
    sys.path.insert(0, str(KIT))


def load_module(name: str, path: Path) -> ModuleType:
    """파일 하나를 정해 준 이름의 모듈로 불러온다(같은 이름의 다른 모듈과 섞이지 않게)."""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def judge_engine() -> ModuleType:
    return load_module("cooler_judge_engine", KIT / "day6" / "judge_mcp" / "engine.py")


def answer_recommend() -> ModuleType:
    return load_module("cooler_answer_recommend", ANSWERS / "work" / "recommend.py")
