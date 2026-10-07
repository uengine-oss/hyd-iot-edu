"""One directory per run: where the agent works and what survives afterwards (process-gpt-cli-agent/core/workspace.py).

Each work item has its own artifacts and resume state. Different directories are
an organization boundary, not an OS access-control boundary. The directory
outlives the run: a paused run resumes into it and retention sweeps it later.
"""
from __future__ import annotations

import json
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from cliagents import ArtifactBundle, DirectorySink, registry

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]")

CONSTITUTION = """# HYD 설비 이상 조치 — ProcessGPT 업무 에이전트 작업 규칙

당신은 ProcessGPT 업무 프로세스 안에서 실행되는 에이전트입니다. 프로세스 인스턴스의 한 작업(todolist 한 줄)만 맡습니다.

## 반드시
- 작업 디렉터리 밖의 파일을 읽거나 수정하지 마세요. 홈 디렉터리(`~/.claude` 등)를 찾아보지 마세요.
- 연결된 MCP 도구가 있으면 추측 대신 도구로 확인하세요. 지식은 온톨로지(Neo4j MCP), 현황·업무 값은 업무 DB(enterprise MCP),
  규칙 판정은 DMN 도구(hyd-dmn MCP)의 결정론적 결과를 씁니다. 규칙을 임의로 해석해 바꾸지 않습니다.
- 모든 판단에 온톨로지 노드 id(cause:…, fm:…, skill:…, rule:…, ms:…)를 인용합니다.
- 확실하지 않은 값을 지어내지 말고, 모르면 모른다고 결과에 적으세요. 조회 실패와 값 없음을 구분합니다.
- 결과는 지시된 제출 형식(JSON 객체)으로 마지막 메시지에 냅니다.
- 계산 스크립트가 필요하면 작업 디렉터리 안에 파일로 쓰고 `python <파일>` 한 명령으로 실행하세요. `cd`·`;`·환경변수 설정을 섞은 명령은 승인되지 않습니다.
- 근거가 없어 완료할 수 없으면 값을 꾸며 폼을 채우지 마세요. 보류만 담은 JSON
  {"__deferred__":{"status":"UNKNOWN","reason":"보류 이유","evidence":{}}}를 제출하세요.
  조회 실패/결측은 UNKNOWN, 조회했으나 모든 원인 근거가 불일치하면 UNSUPPORTED입니다.
  evidence에는 실제 도구 응답·출처를 보존합니다. 보류와 완료 폼을 함께 제출하지 않습니다.
  재평가 요청에서는 원천을 새로 조회하며 사람의 요청을 근거 충족이나 설비 승인으로 간주하지 않습니다.

## 절대 금지
- 설비 명령(PLC 쓰기), 업무 시스템 조치 실행, 사람 대신 승인. 사람이 승인하기 전에는 어떤 조치도 실행하지 않습니다.
- 온톨로지 스키마·규칙·스킬의 수정. Neo4j는 조회 도구만 사용합니다.
- hyd-dmn.submit_decision은 선택할 카드의 제출만 허용합니다. 설비/업무 조치의 승인이나 실행이 아닙니다.

온톨로지 스키마 설명은 `context/schema_prompt.md` 에 있습니다.
"""


def _safe(component: str, *, fallback: str = "run") -> str:
    cleaned = _UNSAFE.sub("_", (component or "").strip())[:120].strip("._-")
    return cleaned or fallback


@dataclass(frozen=True)
class Workspace:
    path: Path
    run_id: str

    @property
    def exists(self) -> bool:
        return self.path.is_dir()

    @property
    def context_dir(self) -> Path:
        return self.path / "context"

    def contains(self, candidate: str | Path) -> bool:
        try:
            resolved, root = Path(candidate).resolve(), self.path.resolve()
        except OSError:
            return False
        return resolved == root or root in resolved.parents

    def relative(self, path: str | Path) -> str:
        try:
            return Path(path).resolve().relative_to(self.path.resolve()).as_posix()
        except (ValueError, OSError):
            return Path(path).as_posix()

    def files(self) -> list[Path]:
        return sorted(p for p in self.path.rglob("*") if p.is_file()) if self.exists else []


def locate(root: Path, run_id: str, *, tenant_id: str = "") -> Workspace:
    parts = [root]
    if tenant_id:
        parts.append(Path(_safe(tenant_id, fallback="tenant")))
    parts.append(Path(_safe(run_id)))
    return Workspace(path=Path(*[str(p) for p in parts]), run_id=run_id)


def for_run(root: Path, run_id: str, *, tenant_id: str = "") -> Workspace:
    ws = locate(root, run_id, tenant_id=tenant_id)
    ws.path.mkdir(parents=True, exist_ok=True)
    ws.context_dir.mkdir(parents=True, exist_ok=True)
    return ws


def provision(ws: Workspace, *, agent_id: str, schema_prompt: str, task: dict) -> None:
    """Write what the CLI reads before it starts: the constitution (CLAUDE.md), the schema brief, the task record.
    Idempotent — a resumed run rewrites the same files."""
    bundle = ArtifactBundle().add_constitution(CONSTITUTION)
    registry.get(agent_id).emit(bundle, DirectorySink(str(ws.path)))
    (ws.context_dir / "schema_prompt.md").write_text(schema_prompt, encoding="utf-8")
    (ws.context_dir / "task.json").write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")


def sweep(root: Path, retention_seconds: int, *, now: float | None = None) -> list[Path]:
    """Delete run directories past the retention window (age = newest file inside, so a resumed run is not stale)."""
    if not root.is_dir():
        return []
    cutoff = (now or time.time()) - retention_seconds
    removed: list[Path] = []
    for candidate in _run_dirs(root):
        try:
            if _last_touched(candidate) >= cutoff:
                continue
            shutil.rmtree(candidate)
            removed.append(candidate)
        except OSError:
            continue
    return removed


def _run_dirs(root: Path) -> list[Path]:
    found: list[Path] = []
    for first in root.iterdir():
        if not first.is_dir():
            continue
        children = [c for c in first.iterdir() if c.is_dir()]
        if children and all(not c.name.startswith(".") for c in children) and not (first / "CLAUDE.md").exists():
            found.extend(children)          # a tenant folder holds run folders
        else:
            found.append(first)
    return found


def _last_touched(path: Path) -> float:
    newest = path.stat().st_mtime
    for child in path.rglob("*"):
        try:
            newest = max(newest, child.stat().st_mtime)
        except OSError:
            continue
    return newest
