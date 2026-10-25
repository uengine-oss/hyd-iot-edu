"""W1 (2026-10-23 검수): 워커를 멈출 때 CLI 자식 프로세스 무리가 고아로 남지 않는다 — 실제 자식 프로세스로 확인한다.

① SIGTERM(`pkill -f worker.main`) · SIGHUP: 워커가 정상 종료 경로(finally → killpg)를 타서 CLI 무리를 끝낸다.
② SIGKILL처럼 처리할 수 없는 종료: 작업 폴더에 남은 프로세스 무리 기록으로 다음 실행이 시작 전에 그 무리를 끝낸다.
③ 다음 실행은 이전 실행의 output/result.json을 자기 결과로 읽지 않는다(시작 전에 고아를 끝내고 파일을 치운다).
"""
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from worker import process_control

pytestmark = pytest.mark.skipif(os.name == "nt", reason="POSIX process groups (Windows uses a job object)")
ROOT = Path(__file__).resolve().parents[1]
ENV = dict(os.environ, PYTHONPATH=os.pathsep.join(str(ROOT / p) for p in ("common", "it/process", "it/agent-worker")))

CHILD = """import json, os, sys, time, pathlib
ws = pathlib.Path(sys.argv[1])
(ws / 'child.pid').write_text(str(os.getpid()))
time.sleep(float(sys.argv[2]))
(ws / 'output').mkdir(exist_ok=True)
(ws / 'output' / 'result.json').write_text(json.dumps({'decision_id': 'DEC-ORPHAN'}))
print(json.dumps({'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'done'}}), flush=True)
"""

DRIVER = """import pathlib, sys
from cliagents import ExecRequest
from procsvc.procdb import MemoryRepo
from worker.codex_provider import WorkerCodexProvider
from worker.runner import Runner
from worker.settings import Settings
from worker import main as worker_main
ws = pathlib.Path(sys.argv[1]); child = sys.argv[2]
if sys.argv[3] == 'signals':
    worker_main.install_stop_signals()
class P(WorkerCodexProvider):
    def exec_argv(self, request): return [sys.executable, '-u', child, str(ws), '4']
repo = MemoryRepo()
row = {'id': 'orphan', 'proc_inst_id': 'p', 'activity_id': 't', 'status': 'IN_PROGRESS', 'draft_status': 'STARTED',
       'consumer': 'o', 'tenant_id': 'hyd', 'start_date': '2026-10-04T00:00:00Z'}
repo.insert_workitems([row])
r = Runner(Settings(consumer='o', run_timeout_s=60, cancel_check_every_s=.05, workspace_root=ws), repo, schema_prompt='')
r._stream(row, 'job', P(), ExecRequest(prompt='x', workdir=str(ws)), None, 't')
"""


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:            # a zombie (exited, not yet reaped by its parent) is not running
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        return True


def _wait(cond, timeout: float) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(.05)
    return cond()


def _start_driver(tmp_path, mode):
    ws = tmp_path / "ws"; ws.mkdir()
    (tmp_path / "child.py").write_text(CHILD, encoding="utf-8")
    (tmp_path / "driver.py").write_text(DRIVER, encoding="utf-8")
    proc = subprocess.Popen([sys.executable, str(tmp_path / "driver.py"), str(ws), str(tmp_path / "child.py"), mode],
                            env=ENV, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert _wait(lambda: (ws / "child.pid").exists() and (ws / "child.pid").read_text(), 15), proc.communicate(timeout=5)[0]
    return proc, ws, int((ws / "child.pid").read_text())


@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGHUP])
def test_stop_signal_ends_the_cli_process_group_with_the_worker(tmp_path, sig):
    proc, ws, child = _start_driver(tmp_path, "signals")
    assert (ws / process_control.GROUP_FILE).exists()                      # the run recorded its group in the workspace
    proc.send_signal(sig)
    proc.wait(timeout=15)
    assert proc.returncode == 128 + sig                                    # unwound (SystemExit), not killed by the signal
    assert _wait(lambda: not _alive(child), 3), "CLI child survived the worker's stop signal (orphan)"
    time.sleep(4.5)                                                        # past the child's own 4 s
    assert not (ws / "output" / "result.json").exists()                    # the orphan never wrote a result
    assert not (ws / process_control.GROUP_FILE).exists()                  # group killed → record removed


def test_a_worker_killed_without_unwinding_leaves_a_group_the_next_run_reaps(tmp_path):
    proc, ws, child = _start_driver(tmp_path, "signals")
    proc.kill(); proc.wait(timeout=10)                                     # SIGKILL: no handler, no finally
    assert _alive(child)                                                   # the orphan exists — this is what reap is for
    killed = process_control.reap_stale_group(ws)
    assert killed == child
    assert _wait(lambda: not _alive(child), 3)
    time.sleep(4.5)
    assert not (ws / "output" / "result.json").exists()
    assert process_control.reap_stale_group(ws) is None                    # record consumed


def test_reap_leaves_a_reused_pid_alone(tmp_path):
    other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True)
    try:
        (tmp_path / process_control.GROUP_FILE).write_text(json.dumps({"pgid": other.pid, "start": "proc:1"}), encoding="utf-8")
        assert process_control.reap_stale_group(tmp_path) is None          # same pid, other start time → not ours
        assert _alive(other.pid)
    finally:
        other.kill(); other.wait()


def test_the_next_run_kills_the_orphan_before_clearing_and_does_not_read_its_result(tmp_path):
    """Runner.run: an orphan from a killed worker is still running in the work item's workspace and would write
    output/result.json after the clear. The new run kills it first; the result comes from the new run only."""
    sys.path.insert(0, str(Path(__file__).parent))
    from test_worker import _repo, _settings
    from cliagents import ExecEvent, ExecEventKind
    from worker.runner import Runner
    repo, inst = _repo()
    row0 = next(w for w in repo.list_workitems(proc_inst_id=inst["proc_inst_id"]) if w["activity_id"] == "task:diagnose")
    ws = tmp_path / "hyd" / row0["id"]; (ws / "output").mkdir(parents=True)
    (tmp_path / "child.py").write_text(CHILD, encoding="utf-8")
    orphan = subprocess.Popen([sys.executable, "-u", str(tmp_path / "child.py"), str(ws), "1.5"], start_new_session=True,
                              stdout=subprocess.DEVNULL)
    assert _wait(lambda: (ws / "child.pid").exists(), 10)
    process_control._remember_group(ws / process_control.GROUP_FILE, orphan.pid)
    seen = {}

    def fn(provider, request, env):
        # SIGKILL was sent before this run started; the kernel ends the process at its next scheduling point
        seen["orphan_alive"] = not _wait(lambda: orphan.poll() is not None, 2)
        yield ExecEvent(kind=ExecEventKind.RUN_START, text="claude", session_id="sess-N")
        time.sleep(2.0)                                                    # past the orphan's 1.5 s
        yield ExecEvent(kind=ExecEventKind.RESULT, session_id="sess-N",
                        text='{"cause": "cause:new-run", "failure_mode": "fm:cooling-loss", "guide_card": {"k": 1}}')
    try:
        r = Runner(_settings(tmp_path), repo, exec_fn=fn, schema_prompt="# s", resolve_provider=lambda pid: object())
        assert r.poll_once() == 1
    finally:
        if orphan.poll() is None:
            orphan.kill()
        orphan.wait()
    assert seen["orphan_alive"] is False
    row = repo.get_workitem(row0["id"])
    assert row["status"] == "SUBMITTED" and row["output"]["cause"] == "cause:new-run"
    assert "decision_id" not in row["output"]
    assert any("이전 실행기가 남긴" in str(e["data"]) for e in repo.list_events(todo_id=row["id"]))


def test_the_worker_entry_point_installs_the_stop_signals_before_its_first_poll(monkeypatch):
    from worker import main as worker_main
    seen = {}

    class StopAtFirstPoll:
        def __init__(self, *a, **k):
            pass

        def poll_once(self, on_polled=None):
            seen["term"] = signal.getsignal(signal.SIGTERM)
            seen["hup"] = signal.getsignal(signal.SIGHUP)
            raise SystemExit(0)
    previous = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGHUP)}
    monkeypatch.setattr(worker_main, "Runner", StopAtFirstPoll)
    monkeypatch.setattr(worker_main, "_repo", lambda: None)
    monkeypatch.setattr(worker_main.threading, "Thread", lambda *a, **k: type("T", (), {"start": lambda self: None})())
    try:
        with pytest.raises(SystemExit):
            worker_main.main()
    finally:
        for s, h in previous.items():
            signal.signal(s, h)
    assert callable(seen["term"]) and seen["term"] is seen["hup"] and seen["term"] not in (signal.SIG_DFL, signal.SIG_IGN)
