"""agent-worker: the ProcessGPT agent type `cliagents` (process-gpt-cli-agent/server.py + agent-sdk ProcessGPTAgentServer).

    poll ─▶ fetch_pending_task(agent_orch=cliagents) ─▶ Runner.handle() ─▶ save_task_result(final) → SUBMITTED
A small HTTP surface answers what an operator asks: /health (runs in flight), /agents?check_auth=1 (which CLIs exist here).
"""
from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

from cliagents import Surface, registry

from . import env_guard, workspace
from .runner import Runner
from .settings import AGENT_TYPE, settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("worker")
# A095: settings are captured above; from here on no child process (the CLI agent, its MCP servers) can inherit the
# worker's own credentials. The Codex GPU key is handed over by name only when that provider runs (settings.codex_model_provider_env_key).
_SCRUBBED = env_guard.scrub(keep=(settings.codex_model_provider_env_key,))
if _SCRUBBED:
    log.info("child-process environment: removed %s", ", ".join(_SCRUBBED))
status = {"status": "starting", "agent_type": AGENT_TYPE, "runs_in_flight": 0, "max_concurrent_runs": 1, "polls": 0, "handled": 0,
          "last_poll": None, "error": None}
_runner: Runner | None = None
_SWEEP_INTERVAL_S = 3600


def _repo():
    from procsvc.procdb import PgRepo           # same table access as the process service (copied into the image)
    return PgRepo(settings.supabase_dsn)


#: A129 (process-gpt-cli-agent core/availability.py): how each CLI is asked whether it has credentials — read-only status
#: commands, no model call. `installed` is cheap (PATH); `authenticated` costs a subprocess per agent, so it is opt-in
#: (`/agents?check_auth=1`), and a probe that hangs or errors reports None ("unknown") rather than a false "log in first".
_AUTH_PROBES = {"claude-code": ["auth", "status"], "codex": ["login", "status"]}
_PROBE_TIMEOUT_S = 10


def _probe_auth(agent_id: str, executable: str | None, *, runner=None) -> tuple[bool | None, str]:
    probe = _AUTH_PROBES.get(agent_id)
    if not probe or not executable:
        return None, ""
    try:
        completed = (runner or subprocess.run)([executable, *probe], capture_output=True, text=True, timeout=_PROBE_TIMEOUT_S)
    except (OSError, subprocess.SubprocessError):
        return None, ""
    if completed.returncode == 0:
        return True, ""
    detail = (completed.stderr or completed.stdout or "").strip().splitlines()
    return False, detail[0] if detail else "not logged in"


def agents(check_auth: bool = False) -> list[dict]:
    """Which CLI agents exist in this container — the same probe the product's picker uses (auth state on request)."""
    out = []
    for a in registry.availability(Surface.EXEC, refresh=True):
        row = {"agent_id": a.agent_id, "installed": a.installed, "install_hint": None if a.installed else a.install_hint,
               "default": a.agent_id == settings.cli_agent}
        if check_auth:
            row["authenticated"], row["auth_hint"] = _probe_auth(a.agent_id, a.executable_path) if a.installed else (None, "")
        out.append(row)
    return out


class Http(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        path = urlparse(self.path)
        if path.path in ("/health", "/healthz"):
            body, code = dict(status, runs_in_flight=_runner.in_flight if _runner else 0), 200 if status["status"] == "ok" else 503
        elif path.path == "/agents":
            body, code = {"agents": agents(any(f"check_auth={v}" in (path.query or "") for v in ("1", "true", "yes")))}, 200
        else:
            body, code = {"error": "not found"}, 404
        data = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):  # quiet
        pass


def serve_http() -> None:
    HTTPServer(("0.0.0.0", settings.health_port), Http).serve_forever()


def sweep_forever() -> None:
    while True:
        try:
            removed = workspace.sweep(settings.workspace_root, settings.retention_seconds,
                                  keep=lambda wid: (_repo().get_workitem(wid) or {}).get("status") == "IN_PROGRESS")   # A104: open work keeps its session
            if removed:
                log.info("swept %d expired workspaces", len(removed))
        except Exception:  # noqa: BLE001
            log.exception("workspace sweep failed")
        time.sleep(_SWEEP_INTERVAL_S)


def main() -> None:
    global _runner
    threading.Thread(target=serve_http, daemon=True).start()
    threading.Thread(target=sweep_forever, daemon=True).start()
    _runner = Runner(settings, _repo())
    log.info("cliagents agent type up: consumer=%s agent_orch=%s cli=%s permission=%s http=:%d", settings.consumer, settings.agent_orch,
             settings.cli_agent, settings.default_permission.value, settings.health_port)
    while True:
        try:
            handled = _runner.poll_once()
            status.update(status="ok", error=None, handled=status["handled"] + handled)
            if handled:
                continue                                       # there was work → poll again at once (the product's loop)
        except Exception as e:  # noqa: BLE001 — DB not up yet, etc.
            status.update(status="error", error=f"{type(e).__name__}: {str(e)[:200]}")
            log.warning("poll failed: %s", status["error"])
        status["polls"] += 1
        status["last_poll"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        time.sleep(settings.poll_interval_s)


if __name__ == "__main__":
    main()
