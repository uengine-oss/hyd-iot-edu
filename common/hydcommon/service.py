"""Shared FastAPI skeleton: /healthz, /metrics, CORS (the browser calls every service directly on a host port)."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from .metrics import Registry


def make_app(title: str, reg: Registry, health_fn=None) -> FastAPI:
    app = FastAPI(title=title, version="1.0")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    @app.get("/healthz")
    def healthz():
        extra = dict(health_fn() or {}) if health_fn else {}
        ok = bool(extra.pop("ok", True))
        body = {"ok": ok, **extra}
        return body if ok else JSONResponse(status_code=503, content=body)

    @app.get("/metrics", response_class=PlainTextResponse)
    def metrics():
        return reg.render()

    return app
