"""Environment-derived configuration of the agent worker, read once (process-gpt-cli-agent/core/settings.py shape).

Defaults are safe rather than convenient: a permission level that cannot leave the workspace, one run at a time, a
retention window long enough to answer "where did my file go?".
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from cliagents import Permission

log = logging.getLogger("worker.settings")
#: The orchestration value this worker polls (todolist.agent_orch). One value for every CLI (the product's AGENT_TYPE).
AGENT_TYPE = "cliagents"
_PERMISSION_BY_NAME = {p.value: p for p in Permission}
#: Claude Code --allowedTools for a headless run: the read-only MCP tools the task needs plus `python <file>` for the A077
#: citation-offset script (file writes stay under the workspace permission mode). Single source of truth (see allowed_tools).
DEFAULT_ALLOWED_TOOLS = ("mcp__neo4j__get_neo4j_schema,mcp__neo4j__read_neo4j_cypher,mcp__enterprise__*,mcp__hyd-dmn__*,Read,Glob,Grep,"
                         "Bash(python *),Bash(python3 *),PowerShell(python *),Skill")   # U2: Skill = the assigned .claude/skills/<name>/SKILL.md


def run_allowed_tools(allowed: list[str], servers: list[str]) -> list[str]:
    """U2: a tenant MCP server the default list does not name (one a student registered for their agent) gets its tools
    allowed for the run that registers it — otherwise the headless CLI would refuse every call to it as a permission
    request. Servers the default list already names keep their narrower entries (neo4j: read tools only)."""
    out = list(allowed)
    for name in servers:
        if not any(a.startswith(f"mcp__{name}__") for a in out):
            out.append(f"mcp__{name}__*")
    return out


def effective_permission(provider_id: str, permission: Permission) -> Permission:
    """A129: cliagents maps READ_ONLY onto Claude Code's `plan` permission mode (cliagents/providers/claude_code.py), where
    every MCP tool call fails with "Cannot call … while in plan mode" (session 14, first try: the run deferred without
    reading the business DB). A headless business task without its tools is a dead run, so for Claude Code READ_ONLY is
    normalized to WORKSPACE_WRITE — the worker's default: writes stay inside the run workspace and commands remain gated by
    the allowed-tools list — and the normalization is logged. Other CLIs keep the definition's value."""
    if provider_id == "claude-code" and permission is Permission.READ_ONLY:
        log.warning("agentConfig permission=read_only would run Claude Code in plan mode (MCP tools refused); using %s",
                    Permission.WORKSPACE_WRITE.value)
        return Permission.WORKSPACE_WRITE
    return permission


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
    # HYD addition (A073): run Codex against an OpenAI-compatible model server (the lecturer's GPU SGLang) by inline
    # `-c model_provider` overrides per run — the personal ~/.codex/config.toml is never edited (--ignore-user-config).
    # The API key stays in the worker process environment under `codex_model_provider_env_key`; it is never written to a file.
    codex_model_provider_base_url: str = os.getenv("CODEX_MODEL_PROVIDER_BASE_URL", "")
    codex_model_provider_name: str = os.getenv("CODEX_MODEL_PROVIDER_NAME", "HYD GPU model server")
    codex_model_provider_env_key: str = os.getenv("CODEX_MODEL_PROVIDER_ENV_KEY", "HYD_GPU_API_KEY")
    codex_model: str | None = os.getenv("CODEX_MODEL") or None
    default_permission: Permission = field(default_factory=lambda: _PERMISSION_BY_NAME.get(os.getenv("CLIAGENTS_DEFAULT_PERMISSION", ""), Permission.WORKSPACE_WRITE))
    run_timeout_s: float = float(os.getenv("CLIAGENTS_RUN_TIMEOUT_SECONDS", "1800"))
    max_format_corrections: int = int(os.getenv("MAX_FORMAT_CORRECTIONS", "2"))     # A086: same-session shape fixes before failing
    # A119 (r14 B1): the agent may write its result to <workspace>/output/result.json instead of the last message; cap on what
    # the worker will read back (EHU40 80-page extraction ≈ 0.3 MB; a 3× manual ≈ 0.5 MB)
    max_result_file_bytes: int = int(os.getenv("MAX_RESULT_FILE_BYTES", str(16 * 1024 * 1024)))
    # one directory per run under here (must be a persistent volume: a paused run resumes into it)
    workspace_root: Path = Path(os.getenv("CLIAGENTS_WORKSPACE_ROOT", os.getenv("WORKSPACE_ROOT", "/workspace")))
    workspace_retention_hours: int = int(os.getenv("CLIAGENTS_WORKSPACE_RETENTION_HOURS", "72"))
    schema_prompt_path: Path = Path(os.getenv("SCHEMA_PROMPT", "/srv/ontology/schema_prompt.md"))
    # HYD addition: headless runs cannot answer a permission prompt, so the read-only tools the task needs are pre-approved
    # (Claude Code --allowedTools). Anything else still arrives as a permission_request → human question (HITL).
    # A077: prompts longer than this go to context/prompt.md (Windows argv limit ≈ 32 K chars; keep headroom for the other args)
    max_inline_prompt_chars: int = int(os.getenv("MAX_INLINE_PROMPT_CHARS", "16000"))
    # The default list lives here only (compose passes ALLOWED_TOOLS through as `${ALLOWED_TOOLS:-}`; an empty value means
    # this default). It used to be duplicated in compose.yaml without the python entries, so the container could not run
    # the A077 citation-offset script without a permission request.
    allowed_tools: list[str] = field(default_factory=lambda: _csv(os.getenv("ALLOWED_TOOLS") or DEFAULT_ALLOWED_TOOLS))
    # Claude Code keeps its login under CLAUDE_CONFIG_DIR. Isolating it per run (the product's RuntimeLease) is only safe when
    # an API key authenticates the CLI; a subscription login lives in the shared config dir and must not be relocated.
    isolate_config_dir: bool = bool(os.getenv("ANTHROPIC_API_KEY"))
    # host run (subscription login): container host:port -> what this machine reaches, applied to tenants.mcp entries
    mcp_host_rewrite: str = os.getenv("MCP_HOST_REWRITE", "")
    health_port: int = int(os.getenv("HEALTH_PORT", os.getenv("PORT", "8097")))
    cancel_check_every_s: float = 2.0
    lease_renew_every_s: float = float(os.getenv("LEASE_RENEW_EVERY_S", "30"))     # A097: agent-sdk lease.py renews a 120 s lease every 30 s

    @property
    def retention_seconds(self) -> int:
        return self.workspace_retention_hours * 3600


settings = Settings()
