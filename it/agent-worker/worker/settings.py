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
#: The one CLI this worker runs (cliagents provider id). The course gateway, the replay recordings and the sandbox are built for it.
PROVIDER = "claude-code"
#: Business agents read/calculate through checked MCP tools and write their result with native workspace editing tools.
#: A Python shell can bypass every MCP read-only check by issuing HTTP/SQL itself; it is never pre-approved. The CLI's
#: built-in tool set is Read · Write · Edit (+ Skill) (cli_sandbox.cli_args), so only those native names are listed.
DEFAULT_ALLOWED_TOOLS = ("mcp__neo4j__get_neo4j_schema,mcp__neo4j__read_neo4j_cypher,mcp__enterprise__*,mcp__hyd-dmn__*,"
                         "mcp__enterprise-maint__*,mcp__enterprise-purchase__*,Read,Write,Edit,Skill")   # Skill = the assigned skills
MODES = ("live", "record", "replay")

BLOCKED_SHELL_TOOLS = ('Bash', 'PowerShell')

from hydcommon.handover_tools import HANDOVER_READS


def handover_allowed_tools(allowed, servers):
    """교대 인수인계 단계는 허용 목록 한 곳(hydcommon.handover_tools.HANDOVER_READS)의 조회 도구만 미리 허용한다 — hyd-dmn 의
    일반 허용(mcp__hyd-dmn__*, 판단 제출 포함)을 가져오지 않는다. 목록 밖 도구는 머리 없는 실행에서 승인 요청이 되어 실행되지 않는다."""
    native = [tool for tool in allowed if not tool.startswith('mcp__') and tool.split('(', 1)[0] not in BLOCKED_SHELL_TOOLS]
    return native +[f'mcp__{server}__{tool}' for server, names in HANDOVER_READS.items() if server in servers for tool in names]


def run_allowed_tools(allowed: list[str], servers: list[str], read_tools: dict[str, list[str]] | None = None) -> list[str]:
    """U2 + B2: a tenant MCP server the default list does not name (one a student registered for their agent) gets only the
    read-only tools its connection check stamped (bridge.gate_servers) — never `mcp__<server>__*`, which would also pre-approve
    its write tools. Without a stamp it adds nothing (gate_servers already left such a server out of the run). Servers the
    default list already names keep their narrower entries (neo4j: read tools only)."""
    out = [a for a in allowed if a.split('(', 1)[0] not in BLOCKED_SHELL_TOOLS]
    for name in servers:
        if not any(a.startswith(f"mcp__{name}__") for a in out):
            out += [f"mcp__{name}__{tool}" for tool in (read_tools or {}).get(name, [])]
    return out


def run_disallowed_tools(blocked_tools: dict[str, list[str]] | None) -> list[str]:
    """B2: the tools a gated server's check found not read-only (write · unmarked) are denied outright (Claude Code
    --disallowedTools), so the agent cannot even ask for them."""
    return [*BLOCKED_SHELL_TOOLS, *[f"mcp__{name}__{tool}" for name, tools in sorted((blocked_tools or {}).items()) for tool in tools]]


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
    # process: the course boundary decision, the local model gateway (the model is the gateway's — course_ledger.POLICY), the
    # question tools and OAuth MCP credentials all go to this one address with the one worker credential file
    process_url: str = os.getenv("PROCESS_URL", "")
    runtime_key_file: str = os.getenv("HYD_WORKER_RUNTIME_KEY_FILE", "")
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
    # host run (subscription login): container host:port -> what this machine reaches, applied to tenants.mcp entries
    mcp_host_rewrite: str = os.getenv("MCP_HOST_REWRITE", "")
    health_port: int = int(os.getenv("HEALTH_PORT", os.getenv("PORT", "8097")))
    cancel_check_every_s: float = 2.0
    lease_renew_every_s: float = float(os.getenv("LEASE_RENEW_EVERY_S", "30"))     # A097: agent-sdk lease.py renews a 120 s lease every 30 s
    # AI 응답(worker/ai_replay.py): live(실제 AI — 같은 요청이 앞서 성공했으면 그 결과를 다시 씀) · record(강사 녹화) · replay(키 없는 PC).
    # 컨테이너 워커는 시작 스크립트(start_all.sh)가 .env 의 LLM_API_KEY 로 정해 compose 가 넘긴다: 키 있음 live · 없음 replay · --record.
    ai_mode: str = os.getenv("AI_MODE", "")              # 없으면 켜지지 않는다(세 모드 밖 — 조용히 실제 AI로 켜지지 않게)
    ai_replay_dir: Path = Path(os.getenv("AI_REPLAY_DIR", str(Path(__file__).resolve().parents[1] / "replay")))


    # W3 (2026-10-23 검수): how long the business DB may stay unreachable during a run (cancel check · lease renewal · progress
    # rows) before the run stops with that reason. Below the 120 s lease, so the run ends before another worker may reclaim it.
    db_outage_limit_s: float = float(os.getenv("DB_OUTAGE_LIMIT_S", "90"))

    @property
    def retention_seconds(self) -> int:
        return self.workspace_retention_hours * 3600

    @property
    def ai_cache_dir(self) -> Path:
        """키 있는 PC의 같은 요청 저장(이 PC 것 — 녹화 폴더와 따로). 작업 폴더 정리(workspace.sweep)는 점으로 시작하는 폴더를 건너뛴다."""
        return self.workspace_root / ".ai-cache"


settings = Settings()
