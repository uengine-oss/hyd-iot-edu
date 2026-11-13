"""Shared FastAPI skeleton: /healthz and /metrics.

No CORS: the browser reaches the services only through the portal's same-origin paths (it/portal/nginx.conf), so no
service answers another origin's script. Tools (Grafana · Prometheus · check scripts) call the 127.0.0.1 ports directly,
which needs no CORS either.

No cross-site writes: without CORS a page on another site still can make the browser send a *simple* request (an HTML form
POST, no preflight) — a write route that takes no body would run. Browsers mark every request with Sec-Fetch-Site; a write
(POST · PUT · PATCH · DELETE) marked from another site (`cross-site`, or `same-site` = another port of this PC — not the portal's
same-origin /svc/ path) is refused with 403 here, in the one skeleton every service uses. A browser too old to send
Sec-Fetch-Site still sends Origin on a cross-origin POST (OWASP CSRF: verify the origin) — then the write must come from the
host the browser addressed (X-Forwarded-Host from the portal nginx, else Host). Requests with neither header (tools,
service-to-service calls, scripts) and same-origin portal calls are unchanged.
"""
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from .metrics import Registry


WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
FOREIGN_SITES = frozenset({"cross-site", "same-site"})
CROSS_SITE_REFUSED = ("다른 사이트(또는 이 PC 의 다른 포트)의 페이지가 보낸 쓰기 요청은 받지 않습니다 — "
                      "포털 화면에서 다시 누르세요")


def foreign_write(method: str, headers) -> bool:
    """이 쓰기 요청이 다른 사이트의 페이지에서 왔는가 — Sec-Fetch-Site 가 있으면 그것으로, 없으면 Origin 과 브라우저가 부른 주인(Host)을 견준다."""
    if method not in WRITE_METHODS:
        return False
    site = headers.get("sec-fetch-site")
    if site is not None:
        return site in FOREIGN_SITES
    origin = headers.get("origin")
    if origin is None:
        return False                                          # 도구 · 서비스끼리 · 스크립트(브라우저가 아님)
    host = headers.get("x-forwarded-host") or headers.get("host") or ""
    return origin == "null" or urlsplit(origin).netloc.lower() != host.lower()


def stop_after_loop_end(task, state: dict, log) -> None:
    """소비 루프 task 의 끝남 알림(add_done_callback). 루프가 끝난 까닭을 건강 상태(/healthz 503)와 로그에 남기고,
    서비스가 꺼지는 중이 아니면 프로세스를 내린다 — compose 의 restart: unless-stopped 가 시작 경로 그대로 다시 켠다.
    2026-11-13 전수 검사: 루프가 예외로 끝나면 「죽었다」고 적기만 하고 프로세스는 살아 있어, 다시 켜지지 않은 채
    감지 · 적재 · 명령 전달이 멈춰 있었다(점검의 서비스 12/13). 같은 프로세스 안에서 루프만 다시 돌리지 않는 까닭:
    루프의 시작은 저장 상태 복원 · 구독 위치 잡기를 포함한 시작 경로라서, 시험된 길(프로세스 시작)을 그대로 밟게 한다."""
    if task.cancelled():          # 서비스 끄기 — 내려가는 중이다
        return
    state["consumer_dead"] = True
    state["consumer_error"] = repr(task.exception()) if task.exception() else "exited"
    log.error("consumer task ended: %s — stopping the process so it is restarted", state["consumer_error"])
    _stop_process()


def _stop_process() -> None:
    import os, signal
    os.kill(os.getpid(), signal.SIGTERM)      # uvicorn 이 받아 정상 종료 절차(shutdown 훅)를 밟는다


def make_app(title: str, reg: Registry, health_fn=None, refresh=None) -> FastAPI:
    """health_fn() -> dict with "ok" (False -> 503); refresh() updates gauges that are read from state right before a scrape."""
    app = FastAPI(title=title, version="1.0")

    @app.middleware("http")
    async def refuse_cross_site_writes(request: Request, call_next):
        if foreign_write(request.method, request.headers):
            return JSONResponse(status_code=403, content={"detail": CROSS_SITE_REFUSED})
        return await call_next(request)

    @app.get("/healthz")
    def healthz():
        extra = dict(health_fn() or {}) if health_fn else {}
        ok = bool(extra.pop("ok", True))
        body = {"ok": ok, **extra}
        return body if ok else JSONResponse(status_code=503, content=body)

    @app.get("/metrics", response_class=PlainTextResponse)
    def metrics():
        if refresh:
            refresh()
        return reg.render()

    return app
