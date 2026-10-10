"""랩 연결 설정. 값은 .env 와 환경 변수에서만 읽는다(환경 변수가 먼저). 없으면 어느 값이 없는지 알리고 멈춘다."""
from __future__ import annotations

import os
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDER_OPEN = "<"


class SettingsError(RuntimeError):
    """연결 설정이 없거나 자리표시자 그대로일 때."""


def project_dir() -> Path:
    """학생 결과(work/, .mcp.json, .claude/)가 놓이는 폴더. 기본은 키트 폴더."""
    override = os.environ.get("LAB_PROJECT_DIR")
    return Path(override).resolve() if override else KIT_ROOT


def work_dir() -> Path:
    return project_dir() / "work"


def env_file() -> Path:
    return KIT_ROOT / ".env"


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise SettingsError(f"{path}:{number} 줄을 읽을 수 없습니다. '이름=값' 모양이어야 합니다.")
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def setting(key: str) -> str:
    value = os.environ.get(key) or read_env_file(env_file()).get(key)
    if not value:
        raise SettingsError(f"{key} 값이 없습니다. {env_file()} 에 '{key}=값' 줄을 넣어 주세요(.env.example 참고).")
    if value.startswith(PLACEHOLDER_OPEN):
        raise SettingsError(f"{key} 가 예시 글자 그대로입니다. {env_file()} 에서 실제 값으로 바꿔 주세요.")
    return value


def setting_or(key: str, default: str) -> str:
    """꼭 없어도 되는 설정. 없으면 정해 둔 기본값을 쓴다."""
    return os.environ.get(key) or read_env_file(env_file()).get(key) or default


def neo4j_settings() -> tuple[str, str, str]:
    return setting("LAB_NEO4J_URI"), setting("LAB_NEO4J_USER"), setting("LAB_NEO4J_PASSWORD")


def db_settings() -> dict[str, str]:
    return {
        "host": setting("LAB_DB_HOST"),
        "port": setting("LAB_DB_PORT"),
        "dbname": setting("LAB_DB_NAME"),
        "user": setting("LAB_DB_USER"),
        "password": setting("LAB_DB_PASSWORD"),
    }


def judge_mcp_url() -> str:
    return setting("LAB_JUDGE_MCP_URL")
