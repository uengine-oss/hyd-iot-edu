"""A095 (process-gpt-deepagents docker_sandbox env whitelist, R13 1조): the CLI agent is a child process and the pinned
cliagents provider always starts its environment from `os.environ` (`exec_env`: dict(os.environ) + overrides), so any secret
the worker process carries — the Postgres DSN it claims tasks with, graph passwords — would be readable by the agent's own
shell/tools, bypassing the MCP boundary. The worker reads its settings first, then removes those keys from its own
environment; nothing it spawns afterwards can inherit them. Keys the CLI itself needs (its login, PATH, HOME…) stay."""
from __future__ import annotations

import os

DEFAULT_BLOCK = ("SUPABASE_DSN", "SUPABASE_SERVICE_KEY", "SUPABASE_SERVICE_ROLE_KEY", "NEO4J_PASSWORD", "NEO4J_AUTH", "PGPASSWORD",
                 "DATABASE_URL", "POSTGRES_PASSWORD")
BLOCK_SUFFIXES = ("_DSN", "_PASSWORD", "_SECRET", "_SERVICE_KEY")


def secret_keys(environ, block=DEFAULT_BLOCK, suffixes=BLOCK_SUFFIXES, keep=()) -> list[str]:
    """Which keys of `environ` must not reach a child process (explicit names plus credential-looking suffixes)."""
    out = []
    for k in environ:
        up = k.upper()
        if k in keep:
            continue
        if up in block or any(up.endswith(s) for s in suffixes):
            out.append(k)
    return sorted(out)


def scrub(environ=None, *, keep=()) -> list[str]:
    """Remove the secret keys from the process environment (default: os.environ). Returns what was removed."""
    env = os.environ if environ is None else environ
    removed = secret_keys(env, keep=keep)
    for k in removed:
        del env[k]
    return removed
