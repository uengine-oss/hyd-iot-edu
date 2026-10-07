"""agent-worker: the ProcessGPT agent type `cliagents` (process-gpt-cli-agent/server.py + agent-sdk ProcessGPTAgentServer).

    poll ─▶ fetch_pending_task(agent_orch=cliagents) ─▶ Runner.handle() ─▶ save_task_result(final) → SUBMITTED
A small HTTP surface answers what an operator asks: /health (runs in flight), /agents?check_auth=1 (which CLIs exist here).
"""
from __future__ import annotations

import json
import logging
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


def agents(check_auth: bool = False) -> list[dict]:
    """Which CLI agents exist in this container — the same probe the product's picker uses."""
    out = []
    for a in registry.availability(Surface.EXEC, refresh=True):
        out.append({"agent_id": a.agent_id, "installed": a.installed, "install_hint": None if a.installed else a.install_hint,
                    "default": a.agent_id == settings.cli_agent})
    return out


class Http(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        path = urlparse(self.path)
        if path.path in ("/health", "/healthz"):
            body, code = dict(status, runs_in_flight=_runner.in_flight if _runner else 0), 200 if status["status"] == "ok" else 503
        elif path.path == "/agents":
            body, code = {"agents": agents("check_auth=1" in (path.query or ""))}, 200
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
            removed = workspace.sweep(settings.workspace_root, settings.retention_seconds)
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
