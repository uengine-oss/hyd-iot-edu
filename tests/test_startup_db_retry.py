"""A151 (A148 item 70-A) — a process restarted while the DB is paused waits for the DB with a bounded backoff instead of
dying in startup on the first psycopg.OperationalError (RestartCount 0→1 in .evidence/a148/70/summary.json)."""
import asyncio

import psycopg
import pytest

from procsvc import instance_mode


def _fake_sleep(monkeypatch):
    sleeps = []

    async def fake_sleep(delay):
        sleeps.append(delay)

    monkeypatch.setattr(instance_mode.asyncio, "sleep", fake_sleep)
    return sleeps


def test_startup_step_retries_db_connection_errors_then_succeeds(monkeypatch):
    sleeps = _fake_sleep(monkeypatch)
    calls, seen_while_waiting = [], []
    state = {}

    def build():
        calls.append(1)
        if len(calls) < 4:
            seen_while_waiting.append(state.get("startup_db_error"))
            raise psycopg.OperationalError('connection to server at "host.docker.internal" failed: Network is unreachable')
        return "runtime"

    out = asyncio.run(instance_mode.retry_startup(build, "instance runtime", state, budget_s=60))

    assert out == "runtime" and len(calls) == 4
    assert sleeps == [2.0, 4.0, 8.0]                                   # backoff doubles
    assert seen_while_waiting[1].startswith("instance runtime: OperationalError")   # /healthz shows why it is not ready
    assert "startup_db_error" not in state                             # cleared once the DB answered


def test_startup_step_gives_up_after_the_budget_and_raises(monkeypatch):
    sleeps = _fake_sleep(monkeypatch)
    state = {}

    def build():
        raise psycopg.OperationalError("Network is unreachable")

    with pytest.raises(psycopg.OperationalError):
        asyncio.run(instance_mode.retry_startup(build, "instance runtime", state, budget_s=60))

    assert sleeps == [2.0, 4.0, 8.0, 16.0, 30.0] and sum(sleeps) == 60   # bounded: never more than the budget of waiting
    assert "startup_db_error" in state


def test_startup_step_does_not_retry_non_connection_errors(monkeypatch):
    sleeps = _fake_sleep(monkeypatch)
    calls = []

    def build():
        calls.append(1)
        raise ValueError("정의 버전(version)은 비어 있지 않은 문자열이어야 합니다")

    with pytest.raises(ValueError):
        asyncio.run(instance_mode.retry_startup(build, "instance runtime", {}, budget_s=60))
    assert calls == [1] and sleeps == []


def test_startup_step_awaits_async_steps(monkeypatch):
    _fake_sleep(monkeypatch)
    calls = []

    async def latest_states():
        calls.append(1)
        if len(calls) == 1:
            raise psycopg.OperationalError("server closed the connection unexpectedly")
        return {"HYD-01": "RUN"}

    assert asyncio.run(instance_mode.retry_startup(latest_states, "plant status", {}, budget_s=60)) == {"HYD-01": "RUN"}


def test_healthz_is_not_ready_while_startup_waits_for_the_db():
    from fastapi.testclient import TestClient
    from procsvc import main
    main.state["kafka"] = True
    main.state["startup_db_error"] = "instance runtime: OperationalError: Network is unreachable"
    try:
        r = TestClient(main.app, raise_server_exceptions=False).get("/healthz")   # no lifespan: startup must not run here
        assert r.status_code == 503 and r.json()["ok"] is False
    finally:
        main.state.pop("startup_db_error", None)
