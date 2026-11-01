"""A095 (process-gpt-deepagents docker_sandbox env whitelist, R13 1조): the CLI agent is a child process and the pinned
cliagents provider always starts its environment from `os.environ` (`exec_env`: dict(os.environ) + overrides), so any secret
the worker process carries — the Postgres DSN it claims tasks with, graph passwords — would be readable by the agent's own
shell/tools, bypassing the MCP boundary. The worker reads its settings first, then removes those keys from its own
environment; nothing it spawns afterwards can inherit them. The CLI has no login of its own here: it authenticates only with
the per-run gateway token the runner hands it (course_access.permit), so personal CLI keys (ANTHROPIC_API_KEY · CLAUDE_CODE_OAUTH_TOKEN …)
are removed like every other credential — a key left in the worker's environment cannot route a run around the course gateway."""
from __future__ import annotations

import os

DEFAULT_BLOCK = ("SUPABASE_DSN", "SUPABASE_SERVICE_KEY", "SUPABASE_SERVICE_ROLE_KEY", "NEO4J_PASSWORD", "NEO4J_AUTH", "PGPASSWORD",
                 "DATABASE_URL", "POSTGRES_PASSWORD")
BLOCK_SUFFIXES = ("_DSN", "_PASSWORD", "_SECRET", "_SERVICE_KEY",
                  # A114 (A113 r14 A5; deepagents 10-06 now passes only TENANT_ID into its sandbox): tokens and API keys
                  # of other services (GH_TOKEN, LLM_API_KEY of the internal narrative model …) are not the CLI's business
                  "_TOKEN", "_API_KEY", "_ACCESS_KEY", "_PRIVATE_KEY")
#: 이름이 비밀을 말하는 변수(HYD_SECRET_<이름>) — 예전에는 도구 서버 비밀 값을 여기서 받아 채웠고 그 길은 지웠다(비밀 값 원천은 비밀 값 표
#: 하나, procsvc/mcp_secrets). 강사가 아직 이 이름으로 값을 두었어도 CLI 에는 넘기지 않는다.
BLOCK_PREFIXES = ("HYD_SECRET_",)


def secret_keys(environ, block=DEFAULT_BLOCK, suffixes=BLOCK_SUFFIXES, prefixes=BLOCK_PREFIXES) -> list[str]:
    """Which keys of `environ` must not reach a child process (explicit names plus credential-looking suffixes · prefixes)."""
    out = []
    for k in environ:
        up = k.upper()
        if up in block or any(up.endswith(s) for s in suffixes) or any(up.startswith(p) for p in prefixes):
            out.append(k)
    return sorted(out)


def scrub(environ=None) -> list[str]:
    """Remove the secret keys from the process environment (default: os.environ). Returns what was removed."""
    env = os.environ if environ is None else environ
    removed = secret_keys(env)
    for k in removed:
        del env[k]
    return removed
