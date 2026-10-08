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
from procsvc.agents_store import SKILL_ROOTS, skill_markdown

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]")

#: A119 (r14 B1, ontology-studio `/workspace/output/_parsed_*.json` → `batch_ingest(path)`): the agent writes its result
#: into this file inside the run workspace; the worker reads it as the result when it exists, and falls back to the last
#: message otherwise. A fixed relative path — nothing outside the workspace can be named. (`outputs/result.json` next to it
#: is what the worker stored after the run; keep the two apart.)
RESULT_FILE = "output/result.json"

CONSTITUTION = """# HYD 설비 이상 조치 — ProcessGPT 업무 에이전트 작업 규칙

당신은 ProcessGPT 업무 프로세스 안에서 실행되는 에이전트입니다. 프로세스 인스턴스의 한 작업(todolist 한 줄)만 맡습니다.

## 반드시
- 작업 디렉터리 밖의 파일을 읽거나 수정하지 마세요. 홈 디렉터리(`~/.claude` 등)를 찾아보지 마세요.
- 연결된 MCP 도구가 있으면 추측 대신 도구로 확인하세요. 지식은 온톨로지(Neo4j MCP), 현황·업무 값은 업무 DB(enterprise MCP),
  규칙 판정은 DMN 도구(hyd-dmn MCP)의 결정론적 결과를 씁니다. 규칙을 임의로 해석해 바꾸지 않습니다.
- 모든 판단에 온톨로지 노드 id(cause:…, fm:…, skill:…, rule:…, ms:…)를 인용합니다.
- 확실하지 않은 값을 지어내지 말고, 모르면 모른다고 결과에 적으세요. 조회 실패와 값 없음을 구분합니다.
- 결과는 지시된 제출 형식(JSON 객체)으로 작업 디렉터리의 `output/result.json` 파일에 쓰거나 마지막 메시지에 냅니다.
  파일에 썼으면 마지막 메시지는 짧은 확인 한 줄만 쓰고 결과 JSON을 되풀이하지 않습니다. 긴 결과(절·단계가 많은 추출 등)는 반드시 파일로 냅니다.
- 계산 스크립트가 필요하면 작업 디렉터리 안에 파일로 쓰고 `python <파일>` 한 명령으로 실행하세요. `cd`·`;`·환경변수 설정을 섞은 명령은 승인되지 않습니다.
- 근거가 없어 완료할 수 없으면 값을 꾸며 폼을 채우지 마세요. 보류만 담은 JSON
  {"__deferred__":{"status":"UNKNOWN","reason":"보류 이유","evidence":{}}}를 제출하세요.
  조회 실패/결측은 UNKNOWN, 조회했으나 모든 원인 근거가 불일치하면 UNSUPPORTED입니다.
  evidence에는 실제 도구 응답·출처를 보존합니다. 보류와 완료 폼을 함께 제출하지 않습니다.
  재평가 요청에서는 원천을 새로 조회하며 사람의 요청을 근거 충족이나 설비 승인으로 간주하지 않습니다.
- 제출 요약·메모·사람에게 보내는 질문 문장은 한국어로 씁니다(코드·식별자·SQL·원문 인용은 원문 그대로).

## SQL을 직접 쓸 때 (업무 DB·시계열 조회)
- 먼저 스키마 도구(enterprise describe_schema 등)로 실제 표·열을 확인하고, 거기 있는 표·열만 씁니다. 표·열 이름을 지어내지 않습니다.
- SELECT 한 문장만 씁니다. SQL 주석(-- 또는 /* */)과 끝의 세미콜론을 넣지 않습니다.
- 오류가 나면 오류 문구와 스키마를 대조해 필요한 부분만 고칩니다. 업무 의도(무엇을 세고 거르는지)는 바꾸지 않습니다. 고치기는 최대 두 번입니다.
- 끝내 실패하거나 결과가 0행이면 그대로 적습니다. 실패를 0이나 빈 값으로 바꿔 성공처럼 제출하지 않습니다. 실행한 SQL과 오류를 근거로 남깁니다.

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

    @property
    def result_file(self) -> Path:
        return self.path / RESULT_FILE

    def clear_result_file(self) -> None:
        """A119: a retained workspace may hold the result of an earlier attempt; a new run must not inherit it."""
        try:
            self.result_file.unlink()
        except FileNotFoundError:
            pass


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


def provision(ws: Workspace, *, agent_id: str, schema_prompt: str, task: dict, skills: list[dict] | None = None) -> list[str]:
    """Write what the CLI reads before it starts: the constitution (CLAUDE.md), the schema brief, the task record, and (U2)
    the assigned agent's skills in the CLI's own layout — cliagents puts a skill at `.claude/skills/<name>/SKILL.md` for
    Claude Code and `.agents/skills/<name>/SKILL.md` for Codex (process-gpt-cli-agent core/skills.py build_bundle → emit).
    Idempotent — a resumed run rewrites the same files; skills left from an earlier attempt are removed first, so the
    folder holds exactly this run's skills. Returns the skill files written (workspace-relative)."""
    for root in SKILL_ROOTS.values():
        shutil.rmtree(ws.path / root, ignore_errors=True)
    bundle = ArtifactBundle().add_constitution(CONSTITUTION)
    for skill in skills or []:
        bundle.add_skill(skill["skill_name"], skill_markdown(skill), description=str(skill.get("description") or ""))
    registry.get(agent_id).emit(bundle, DirectorySink(str(ws.path)))
    (ws.context_dir / "schema_prompt.md").write_text(schema_prompt, encoding="utf-8")
    (ws.context_dir / "task.json").write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
    roots = [ws.path / r for r in SKILL_ROOTS.values()]
    return sorted(str(p.relative_to(ws.path)).replace("\\", "/") for r in roots if r.exists() for p in r.rglob("SKILL.md"))


def sweep(root: Path, retention_seconds: int, *, now: float | None = None, keep=None) -> list[Path]:
    """Delete run directories past the retention window (age = newest file inside, so a resumed run is not stale).
    A104 (process-gpt-session-router kube.go: ask the runner whether it is busy before reclaiming): `keep(run_id)` lets the
    caller spare a directory whose work item is still open — a run waiting for a person's answer (HUMAN_ASKED) keeps its
    CLI session under the directory, so deleting it after 72 h would make the answer impossible to resume."""
    if not root.is_dir():
        return []
    cutoff = (now or time.time()) - retention_seconds
    removed: list[Path] = []
    for candidate in _run_dirs(root):
        try:
            if _last_touched(candidate) >= cutoff:
                continue
            if keep is not None and keep(candidate.name):
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
