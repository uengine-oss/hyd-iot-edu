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
def secret_keys(environ, block=DEFAULT_BLOCK, suffixes=BLOCK_SUFFIXES) -> list[str]:
    """Which keys of `environ` must not reach a child process (explicit names plus credential-looking suffixes)."""
    out = []
    for k in environ:
        up = k.upper()
        if up in block or any(up.endswith(s) for s in suffixes):
            out.append(k)
    return sorted(out)


#: G2 (capstone): values for MCP `${SECRET:KEY}` placeholders the lecturer put in the worker's environment as HYD_SECRET_<KEY>.
#: They are held here and removed from the environment like every other secret — bridge.install writes them only into the
#: run's .mcp.json headers/env (cleared after the run), never into the CLI's environment.
SECRET_PREFIX = "HYD_SECRET_"
_HELD: dict[str, str] = {}


def held_secrets() -> dict[str, str]:
    """HYD_SECRET_* values scrub() took out of the environment (name with the prefix -> value)."""
    return dict(_HELD)


def scrub(environ=None) -> list[str]:
    """Remove the secret keys from the process environment (default: os.environ). Returns what was removed."""
    env = os.environ if environ is None else environ
    held = sorted(k for k in env if k.upper().startswith(SECRET_PREFIX))
    removed = sorted(set(secret_keys(env)) | set(held))
    for k in removed:
        if k in held:
            _HELD[k] = env[k]
        del env[k]
    return removed
