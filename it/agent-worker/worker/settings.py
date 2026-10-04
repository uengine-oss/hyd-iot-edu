"""Environment-derived configuration of the agent worker, read once (process-gpt-cli-agent/core/settings.py shape).

Defaults are safe rather than convenient: a permission level that cannot leave the workspace, one run at a time, a
retention window long enough to answer "where did my file go?".
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from cliagents import Permission

#: The orchestration value this worker polls (todolist.agent_orch). One value for every CLI (the product's AGENT_TYPE).
AGENT_TYPE = "cliagents"
_PERMISSION_BY_NAME = {p.value: p for p in Permission}


def _csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def _consumer() -> str:
    return os.getenv("CONSUMER_ID") or os.getenv("WORKER_NAME") or f"{os.uname().nodename if hasattr(os, 'uname') else 'worker'}:{os.getpid()}"


@dataclass(frozen=True)
class Settings:
    agent_orch: str = AGENT_TYPE
    consumer: str = field(default_factory=_consumer)
    tenant_id: str = os.getenv("TENANT_ID", "hyd")
    poll_interval_s: float = float(os.getenv("POLL_INTERVAL_S", "3"))          # the product sleeps 10 s when idle
    # the DB the worker claims from and stores into (the product's SUPABASE_URL + service key; here the Postgres DSN)
    supabase_dsn: str = os.getenv("SUPABASE_DSN", "postgresql://postgres:postgres@host.docker.internal:54322/postgres")
    # which CLI agent runs the task (cliagents provider id), on which model, with how much permission
    cli_agent: str = os.getenv("CLIAGENTS_DEFAULT_CLI", os.getenv("CLI_AGENT", "claude-code"))
    model: str | None = os.getenv("CLI_MODEL") or None
    reasoning_effort: str = os.getenv("CLI_REASONING_EFFORT", "low")
    default_permission: Permission = field(default_factory=lambda: _PERMISSION_BY_NAME.get(os.getenv("CLIAGENTS_DEFAULT_PERMISSION", ""), Permission.WORKSPACE_WRITE))
    run_timeout_s: float = float(os.getenv("CLIAGENTS_RUN_TIMEOUT_SECONDS", "1800"))
    # one directory per run under here (must be a persistent volume: a paused run resumes into it)
    workspace_root: Path = Path(os.getenv("CLIAGENTS_WORKSPACE_ROOT", os.getenv("WORKSPACE_ROOT", "/workspace")))
    workspace_retention_hours: int = int(os.getenv("CLIAGENTS_WORKSPACE_RETENTION_HOURS", "72"))
    schema_prompt_path: Path = Path(os.getenv("SCHEMA_PROMPT", "/srv/ontology/schema_prompt.md"))
    # HYD addition: headless runs cannot answer a permission prompt, so the read-only tools the task needs are pre-approved
    # (Claude Code --allowedTools). Anything else still arrives as a permission_request → human question (HITL).
    allowed_tools: list[str] = field(default_factory=lambda: _csv(os.getenv(
        "ALLOWED_TOOLS", "mcp__neo4j__get_neo4j_schema,mcp__neo4j__read_neo4j_cypher,mcp__enterprise__*,mcp__hyd-dmn__*,Read,Glob,Grep")))
    # Claude Code keeps its login under CLAUDE_CONFIG_DIR. Isolating it per run (the product's RuntimeLease) is only safe when
    # an API key authenticates the CLI; a subscription login lives in the shared config dir and must not be relocated.
    isolate_config_dir: bool = bool(os.getenv("ANTHROPIC_API_KEY"))
    # host run (subscription login): container host:port -> what this machine reaches, applied to tenants.mcp entries
    mcp_host_rewrite: str = os.getenv("MCP_HOST_REWRITE", "")
    health_port: int = int(os.getenv("HEALTH_PORT", os.getenv("PORT", "8097")))
    cancel_check_every_s: float = 2.0

    @property
    def retention_seconds(self) -> int:
        return self.workspace_retention_hours * 3600


settings = Settings()
