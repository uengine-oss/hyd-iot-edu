"""agent-worker: the ProcessGPT agent type `cliagents` (process-gpt-cli-agent/server.py + agent-sdk ProcessGPTAgentServer).

    poll ─▶ fetch_pending_task(agent_orch=cliagents) ─▶ Runner.handle() ─▶ save_task_result(final)
    (→ SUBMITTED only when the task's agent_mode is COMPLETE; in DRAFT mode only the draft is stored)
The repo method names are the product's; PgRepo runs them as HYD's lock-ordered SQL (claim_process_workitems with a
tenant filter, result saved by a conditional UPDATE on the expected consumer — see it/process/procsvc/procdb.py).
A small HTTP surface answers what an operator asks: /health (runs in flight, AI 모드, 키 없는 PC가 답하는 질문),
/agents (whether the CLI exists here).
"""
from __future__ import annotations

import json
import logging
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

from cliagents import Surface, registry

from . import ai_replay, env_guard, workspace
from .course_access import CourseAccess
from .runner import Runner
from .settings import AGENT_TYPE, PROVIDER, settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("worker")
# A095: settings are captured above; from here on no child process (the CLI agent, its MCP servers) can inherit the
# worker's own credentials. The CLI authenticates only with the per-run gateway token (course_access.permit).
_SCRUBBED = env_guard.scrub()
if _SCRUBBED:
    log.info("child-process environment: removed %s", ", ".join(_SCRUBBED))
status = {"status": "starting", "agent_type": AGENT_TYPE, "ai_mode": None, "runs_in_flight": 0, "max_concurrent_runs": 1, "polls": 0, "handled": 0,
          "last_poll": None, "error": None}
_runner: Runner | None = None
_SWEEP_INTERVAL_S = 3600


def _repo():
    from procsvc.procdb import PgRepo           # same table access as the process service (copied into the image)
    return PgRepo(settings.supabase_dsn)


def agents() -> list[dict]:
    """Whether the CLI this worker runs (settings.PROVIDER) is installed here — the product picker's availability probe."""
    return [{"agent_id": a.agent_id, "installed": a.installed, "install_hint": None if a.installed else a.install_hint}
            for a in registry.availability(Surface.EXEC, refresh=True) if a.agent_id == PROVIDER]


class Http(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        path = urlparse(self.path)
        if path.path in ("/health", "/healthz"):
            body, code = dict(status, runs_in_flight=_runner.in_flight if _runner else 0), 200 if status["status"] == "ok" else 503
        elif path.path == "/agents":
            body, code = {"agents": agents()}, 200
        else:
            body, code = {"error": "not found"}, 404
        data = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        # 포털 상단 상태 점이 브라우저에서 /healthz 를 읽는다(다른 포트 = 다른 출처). 상태만 담은 응답이라 출처를 묻지 않는다
        self.send_header("Access-Control-Allow-Origin", "*")
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


def build_runner(repo) -> Runner:
    """AI_MODE(live · record · replay — 다른 값은 켜지지 않는다)에 따라 AI 응답 자리만 바꾼다. 나머지 실행 · 결과 검사 · 저장은 같다."""
    if not settings.process_url or not settings.runtime_key_file:
        raise RuntimeError("PROCESS_URL(process 주소) · HYD_WORKER_RUNTIME_KEY_FILE(실행기 인증 파일)이 없어 AI 워커를 켜지 않습니다")
    course = ai_replay.Library(settings.ai_replay_dir, ai_replay.COURSE)
    responses = ai_replay.Responses(settings.ai_mode, course=course, cache=ai_replay.Library(settings.ai_cache_dir, ai_replay.REUSE))
    status["ai_mode"] = responses.mode
    status["replay_questions"] = course.questions() if responses.mode == "replay" else []
    if responses.mode == "replay":
        log.warning("AI 응답 재생으로 실행합니다: 강사 녹화(%s, %d개)를 씁니다 — 실제 AI 를 부르지 않습니다.", settings.ai_replay_dir, len(course.docs()))
    elif responses.mode == "record":
        log.info("AI 응답 녹화: 실제 AI 실행을 수업 AI 자리마다 %s 에 남깁니다", settings.ai_replay_dir)
    return Runner(settings, repo, responses=responses, course=CourseAccess(settings.process_url, settings.runtime_key_file))


def install_stop_signals() -> list[str]:
    """W1 (2026-10-23 검수): `pkill -f worker.main` (SIGTERM) or a closed terminal (SIGHUP) used to end the worker without
    running any `finally`, so on macOS · Linux the CLI's process group (start_new_session) lived on, kept calling tools
    and wrote output/result.json into the workspace. Both now unwind like Ctrl+C (SIGINT → KeyboardInterrupt): the run's
    `finally` kills its process group (process_control.controlled_stream). A second signal while unwinding is ignored so
    the teardown is not cut short. Windows keeps its job object (KILL_ON_JOB_CLOSE). Main thread only."""
    installed = []

    def stop(signum, _frame):
        for name in ("SIGTERM", "SIGHUP"):
            sig = getattr(signal, name, None)
            if sig is not None:
                signal.signal(sig, signal.SIG_IGN)
        log.info("stop signal %s: ending the current run and its CLI process group", signal.Signals(signum).name)
        raise SystemExit(128 + signum)

    for name in ("SIGTERM", "SIGHUP"):
        sig = getattr(signal, name, None)
        if sig is not None:
            signal.signal(sig, stop)
            installed.append(name)
    return installed


def main() -> None:
    global _runner
    install_stop_signals()
    threading.Thread(target=serve_http, daemon=True).start()
    threading.Thread(target=sweep_forever, daemon=True).start()
    _runner = build_runner(_repo())
    log.info("cliagents agent type up: consumer=%s agent_orch=%s cli=%s permission=%s http=:%d", settings.consumer, settings.agent_orch,
             PROVIDER, settings.default_permission.value, settings.health_port)
    while True:
        try:
            # 2026-10-25: 켜자마자 일을 집으면 그 일이 끝날 때까지 /healthz 가 503(starting)이라 포털 상태 점이 「응답 없음」이었다
            handled = _runner.poll_once(on_polled=lambda: status.update(status="ok", error=None))
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
