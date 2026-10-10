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


def provision(ws: Workspace, *, agent_id: str, constitution: str, schema_prompt: str, task: dict, skills: list[dict] | None = None) -> list[str]:
    """Write what the CLI reads before it starts: the constitution (CLAUDE.md — work_rules.constitution of the agent's
    business part, G9), the schema brief, the task record, and (U2)
    the assigned agent's skills in the CLI's own layout — cliagents puts a skill at `.claude/skills/<name>/SKILL.md` for
    Claude Code and `.agents/skills/<name>/SKILL.md` for Codex (process-gpt-cli-agent core/skills.py build_bundle → emit).
    Idempotent — a resumed run rewrites the same files; skills left from an earlier attempt are removed first, so the
    folder holds exactly this run's skills. Returns the skill files written (workspace-relative)."""
    for root in SKILL_ROOTS.values():
        shutil.rmtree(ws.path / root, ignore_errors=True)
    bundle = ArtifactBundle().add_constitution(constitution)
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
