"""A108 — the Kafka consumer survives a transient DB failure while classifying a RAISE alert (2026-10-07 08:01:10 incident:
one OperationalError right after a container restart ended the consumer for good and every later alert was ignored)."""
import asyncio

from procsvc import main


def test_alert_policy_lookup_retries_transient_db_errors_with_backoff(monkeypatch):
    calls = []

    class Runtime:
        def alert_policy(self, pattern):
            calls.append(pattern)
            if len(calls) < 3:
                raise RuntimeError('connection is bad: connection to server at "fdc4::254" failed: Network is unreachable')
            return {"route": "response", "pattern": pattern}

    sleeps = []

    async def fake_sleep(delay):
        sleeps.append(delay)

    monkeypatch.setattr(main.instance_mode, "current", lambda: Runtime())
    monkeypatch.setattr(main.asyncio, "sleep", fake_sleep)
    main.state.pop("source_policy_error", None)

    out = asyncio.run(main._alert_policy_retrying("COOLER_DEGRADATION"))

    assert out == {"route": "response", "pattern": "COOLER_DEGRADATION"}
    assert calls == ["COOLER_DEGRADATION"] * 3 and sleeps == [1.0, 2.0]      # retried, backoff doubled, then succeeded
    assert "source_policy_error" not in main.state                           # /healthz is clean again after recovery


def test_healthz_reports_the_policy_error_while_retrying():
    from fastapi.testclient import TestClient
    main.state["kafka"] = True
    main.state["source_policy_error"] = "OperationalError: connection is bad"
    try:
        r = TestClient(main.app, raise_server_exceptions=False).get("/healthz")   # no lifespan: the real consumer must not start here
        assert r.status_code == 503 and r.json()["ok"] is False and "source_policy_error" in r.json()
    finally:
        main.state.pop("source_policy_error", None)
