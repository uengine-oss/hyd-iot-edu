import asyncio
import json
from types import SimpleNamespace

import pytest

from procsvc import instance_mode as mode


@pytest.mark.parametrize("failure_step", ["poll", "timeouts", "cleanup", "reconcile"])
def test_full_poll_failure_then_recovery(monkeypatch, failure_step, caplog):
    snapshots = []
    calls = []
    turn = 0

    def operation(name):
        def run():
            calls.append((turn, name))
            if turn == 1 and name == failure_step:
                raise ConnectionError("postgresql://private-user:private-token@private-host")
        return run

    async def execute(fn, *args):
        return fn(*args)

    async def sleep(delay):
        nonlocal turn
        snapshots.append(mode.runtime_readiness())
        turn += 1
        if turn == 3:
            raise asyncio.CancelledError()

    async def scenario():
        task = asyncio.current_task()
        monkeypatch.setattr(mode, "_poll_task", task)
        await mode._polling()

    state = {"source_policy_error": "existing unrelated failure"}
    monkeypatch.setattr(mode, "_ctx", SimpleNamespace(state=state))
    monkeypatch.setattr(mode, "_poll_status", {"status": "preparing", "last_success_at": None, "failure_kind": None})
    monkeypatch.setattr(mode, "_runtime", SimpleNamespace(poll_once=operation("poll"),
        fire_timeouts=operation("timeouts"), repo=SimpleNamespace(cleanup_stale_consumers=operation("cleanup"))))
    monkeypatch.setattr(mode, "reconcile_legacy_decisions", operation("reconcile"))
    monkeypatch.setattr(mode, "AGENT_BRIDGE", "legacy")
    monkeypatch.setattr(mode, "STALE_CLEANUP_EVERY", 1)
    monkeypatch.setattr(mode, "_in_executor", execute)
    monkeypatch.setattr(mode.asyncio, "sleep", sleep)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(scenario())
    assert snapshots[0]["status"] == "preparing" and not snapshots[0]["ready"]
    assert snapshots[1]["status"] == "failed" and snapshots[1]["failure_kind"] == "ConnectionError"
    assert not snapshots[1]["ready"] and snapshots[1]["last_success_at"] is None
    assert snapshots[2]["ready"] and snapshots[2]["last_success_at"]
    assert snapshots[2]["failure_kind"] is None
    assert state == {"source_policy_error": "existing unrelated failure"}
    assert [name for tick, name in calls if tick == 2] == ["poll", "reconcile", "timeouts", "cleanup"]
    assert "private-token" not in json.dumps(snapshots) + caplog.text
    assert mode.runtime_readiness()["status"] == "cancelled"


def test_no_task_or_dead_task_cannot_report_ready(monkeypatch):
    monkeypatch.setattr(mode, "_poll_status", {"status": "ready", "last_success_at": "previous", "failure_kind": None})
    monkeypatch.setattr(mode, "_poll_task", None)
    assert not mode.runtime_readiness()["ready"]
    monkeypatch.setattr(mode, "_poll_task", SimpleNamespace(done=lambda: True, cancelled=lambda: False))
    assert mode.runtime_readiness() == {"status": "stopped", "ready": False,
        "last_success_at": "previous", "failure_kind": None}


def test_real_task_lifecycle_first_poll_cancel_and_unexpected_exit(monkeypatch):
    async def scenario():
        monkeypatch.setattr(mode, "_poll_task", None)
        monkeypatch.setattr(mode, "AGENT_BRIDGE", "off")
        mode.start_loops(SimpleNamespace(), SimpleNamespace())
        task = mode._poll_task
        assert mode.runtime_readiness()["status"] == "preparing"
        with pytest.raises(RuntimeError, match="already running"):
            mode.start_loops(SimpleNamespace(), SimpleNamespace())
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert mode.runtime_readiness()["status"] == "cancelled"
        async def failed_sleep(_):
            raise RuntimeError("private connection detail")
        monkeypatch.setattr(mode.asyncio, "sleep", failed_sleep)
        mode.start_loops(SimpleNamespace(), SimpleNamespace())
        with pytest.raises(RuntimeError):
            await mode._poll_task
        status = mode.runtime_readiness()
        assert status["status"] == "stopped" and not status["ready"]
        assert status["failure_kind"] == "RuntimeError" and "private" not in json.dumps(status)
    asyncio.run(scenario())
