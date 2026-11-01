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
#: The one CLI this worker runs (cliagents provider id). The course gateway, the replay recordings and the sandbox are built for it.
PROVIDER = "claude-code"
#: Business agents read/calculate through checked MCP tools and write their result with native workspace editing tools.
#: A Python shell can bypass every MCP read-only check by issuing HTTP/SQL itself; it is never pre-approved. The CLI's
#: built-in tool set is Read · Write · Edit (+ Skill) (cli_sandbox.cli_args), so only those native names are listed.
DEFAULT_ALLOWED_TOOLS = ("mcp__neo4j__get_neo4j_schema,mcp__neo4j__read_neo4j_cypher,mcp__enterprise__*,mcp__hyd-dmn__*,"
                         "mcp__enterprise-maint__*,mcp__enterprise-purchase__*,Read,Write,Edit,Skill")   # Skill = the assigned skills
MODES = ("live", "record", "replay")

BLOCKED_SHELL_TOOLS = ('Bash', 'PowerShell')


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


def allowed_for_run(allowed: list[str], servers: list[str], fixed: dict[str, list[str]] | None,
                    read_tools: dict[str, list[str]] | None) -> list[str]:
    """이 실행의 미리 허용 목록(Claude Code --allowedTools). fixed: 수업이 조회 도구를 정한 단계(질문 · 교대 초안 — procsvc/agents_store.run_servers
    의 정해진 목록)면 {서버: 도구}, 아니면 None. 정해진 단계는 내장 도구(Read · Write · Edit · Skill) + 그 조회 도구만 — 일반 허용
    (mcp__hyd-dmn__* 는 판단 제출까지)을 가져오지 않는다. 목록 밖 도구는 머리 없는 실행에서 승인 요청이 되어 실행되지 않는다."""
    if fixed is None:
        return run_allowed_tools(allowed, servers, read_tools)
    native = run_allowed_tools([t for t in allowed if not t.startswith('mcp__')], [], {})
    return native + [f'mcp__{server}__{tool}' for server in servers for tool in fixed.get(server, ())]


def run_disallowed_tools(blocked_tools: dict[str, list[str]] | None) -> list[str]:
    """B2: the tools a gated server's check found not read-only (write · unmarked) are denied outright (Claude Code
    --disallowedTools), so the agent cannot even ask for them."""
    return [*BLOCKED_SHELL_TOOLS, *[f"mcp__{name}__{tool}" for name, tools in sorted((blocked_tools or {}).items()) for tool in tools]]


def permission_of(value, *, default: Permission = Permission.WORKSPACE_WRITE) -> Permission:
    """단계 정의(agentConfig.permission)가 고른 CLI 권한 → 이 워커가 실행하는 권한. 값이 없으면 default.
    A129: cliagents maps READ_ONLY onto Claude Code's `plan` permission mode (cliagents/providers/claude_code.py), where every MCP
    tool call fails with "Cannot call … while in plan mode" (session 14, first try: the run deferred without reading the business
    DB). A headless business task without its tools is a dead run, so READ_ONLY runs as WORKSPACE_WRITE — writes stay inside the
    run workspace and commands remain gated by the allowed-tools list — and the normalization is logged.
    G1-13: COMMAND_EXEC 는 Claude Code 의 bypassPermissions(권한을 묻지 않음)라 미리 허용 목록(--allowedTools) — 교대 · 질문 단계의
    좁은 조회 목록 — 이 뜻을 잃는다. 이 워커는 그 권한으로 돌지 않는다. 모르는 값(오타)도 기본값으로 바꾸지 않고 멈춘다."""
    from .course_access import Stop
    if value in (None, ''):
        return default
    by_name = {p.value: p for p in Permission}
    permission = by_name.get(str(value))
    if permission is None:
        raise Stop(f"이 단계에 지정된 에이전트 권한({value})은 이 시스템에 없습니다 — 흐름의 에이전트 설정에서 권한 칸을 비우세요"
                   "(작업 폴더 안 쓰기 권한으로 실행합니다).")
    if permission is Permission.COMMAND_EXEC:
        raise Stop("이 단계에 지정된 에이전트 권한(명령 실행 — 권한 묻기 없음)은 쓰지 않습니다. AI 단계는 작업 폴더 안 쓰기와 허용된 조회 "
                   "도구로만 실행합니다 — 흐름의 에이전트 설정에서 권한 칸을 비우세요.")
    if permission is Permission.READ_ONLY:
        log.warning("agentConfig permission=read_only would run Claude Code in plan mode (MCP tools refused); using %s",
                    Permission.WORKSPACE_WRITE.value)
        return Permission.WORKSPACE_WRITE
    return permission


def _csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def _consumer() -> str:
    return os.getenv("CONSUMER_ID") or f"{os.uname().nodename if hasattr(os, 'uname') else 'worker'}:{os.getpid()}"


@dataclass(frozen=True)
class Settings:
    """환경 변수로 받는 것은 compose · 개발용 호스트 워커 스크립트(workspace/개발/scripts/run_worker_host.sh)가 실제로 주는 값뿐이다 — 아무도
    주지 않던 손잡이(실행 시한 · 허용 도구 · 정리 기한 · 폴링 간격 …)는 이 파일의 값 하나로 두었다(검진 G1-24: 오타가 조용히 기본값이 됐다).
    시험은 dataclasses.replace 로 바꾼다."""
    agent_orch: str = AGENT_TYPE
    consumer: str = field(default_factory=_consumer)
    tenant_id: str = os.getenv("TENANT_ID", "hyd")
    poll_interval_s: float = 3.0                         # the product sleeps 10 s when idle
    # the DB the worker claims from and stores into (the product's SUPABASE_URL + service key; here the Postgres DSN) — compose 가 준다
    supabase_dsn: str = os.getenv("SUPABASE_DSN", "")
    # process: the course boundary decision, the local model gateway (the model is the gateway's — course_ledger.POLICY) and the
    # question tools all go to this one address with the one worker credential file
    process_url: str = os.getenv("PROCESS_URL", "")
    runtime_key_file: str = os.getenv("HYD_WORKER_RUNTIME_KEY_FILE", "")
    # 단계 정의가 권한을 정하지 않았을 때의 권한(작업 폴더 안 쓰기)
    default_permission: Permission = Permission.WORKSPACE_WRITE
    run_timeout_s: float = 1800.0
    max_format_corrections: int = 2                      # A086: same-session shape fixes before failing
    # A119 (r14 B1): the agent may write its result to <workspace>/output/result.json instead of the last message; cap on what
    # the worker will read back (EHU40 80-page extraction ≈ 0.3 MB; a 3× manual ≈ 0.5 MB)
    max_result_file_bytes: int = 16 * 1024 * 1024
    # one directory per run under here (must be a persistent volume: a paused run resumes into it)
    workspace_root: Path = Path(os.getenv("CLIAGENTS_WORKSPACE_ROOT", "/workspace"))
    workspace_retention_hours: int = 72
    schema_prompt_path: Path = Path(os.getenv("SCHEMA_PROMPT", "/srv/ontology/schema_prompt.md"))
    # A077: prompts longer than this go to context/prompt.md (Windows argv limit ≈ 32 K chars; keep headroom for the other args)
    max_inline_prompt_chars: int = 16000
    # HYD addition: headless runs cannot answer a permission prompt, so the read-only tools the task needs are pre-approved
    # (Claude Code --allowedTools). Anything else still arrives as a permission_request → human question (HITL). The list lives here only.
    allowed_tools: list[str] = field(default_factory=lambda: _csv(DEFAULT_ALLOWED_TOOLS))
    # 개발용 호스트 워커: 컨테이너 host:port -> 이 PC에서 닿는 주소, tenants.mcp 주소에 적용
    mcp_host_rewrite: str = os.getenv("MCP_HOST_REWRITE", "")
    health_port: int = int(os.getenv("HEALTH_PORT", "8097"))
    cancel_check_every_s: float = 2.0
    lease_renew_every_s: float = 30.0                    # A097: agent-sdk lease.py renews a 120 s lease every 30 s
    # AI 응답(worker/ai_replay.py): live(실제 AI — 같은 요청이 앞서 성공했으면 그 결과를 다시 씀) · record(강사 녹화) · replay(키 없는 PC).
    # 컨테이너 워커는 시작 스크립트(start_all.sh)가 .env 의 LLM_API_KEY 로 정해 compose 가 넘긴다: 키 있음 live · 없음 replay · --record.
    ai_mode: str = os.getenv("AI_MODE", "")              # 없으면 켜지지 않는다(세 모드 밖 — 조용히 실제 AI로 켜지지 않게)
    ai_replay_dir: Path = Path(os.getenv("AI_REPLAY_DIR", str(Path(__file__).resolve().parents[1] / "replay")))
    # W3 (2026-10-23 검수): how long the business DB may stay unreachable during a run (cancel check · lease renewal · progress
    # rows) before the run stops with that reason. Below the 120 s lease, so the run ends before another worker may reclaim it.
    db_outage_limit_s: float = 90.0

    @property
    def retention_seconds(self) -> int:
        return self.workspace_retention_hours * 3600

    @property
    def ai_cache_dir(self) -> Path:
        """키 있는 PC의 같은 요청 저장(이 PC 것 — 녹화 폴더와 따로). 작업 폴더 정리(workspace.sweep)는 점으로 시작하는 폴더를 건너뛴다."""
        return self.workspace_root / ".ai-cache"


settings = Settings()
