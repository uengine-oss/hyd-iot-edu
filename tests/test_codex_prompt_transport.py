"""Full prompt transport through the actual subprocess/cliagents lifecycle."""
import hashlib
import json
import sys
from types import SimpleNamespace

import pytest
from cliagents import ExecRequest, ExecEventKind, Permission
from worker.codex_provider import WorkerCodexProvider, stream_with_prompt_stdin
from worker.runner import _deliver_prompt, _exec_stream


@pytest.mark.parametrize("session", [None, "previous-session"])
def test_large_utf8_prompt_reaches_child_stdin_and_eof(tmp_path, session):
    text = "업무 지시와 MCP 도구\n따옴표 '\" 줄끝\r\n" * 5000 + "끝!"
    received = tmp_path / "received.json"
    child = tmp_path / "reader.py"
    child.write_text(
        "import sys,json,hashlib\n"
        "from pathlib import Path\n"
        "data=sys.stdin.buffer.read()\n"
        "Path(sys.argv[1]).write_text(json.dumps({'sha':hashlib.sha256(data).hexdigest(),"
        "'argv':sys.argv[2:]}),encoding='utf-8')\n"
        "print(json.dumps({'type':'thread.started','thread_id':'resumed'}),flush=True)\n"
        "print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'received'}}),flush=True)\n"
        "print(json.dumps({'type':'turn.completed','usage':{}}),flush=True)\n",
        encoding="utf-8",
    )

    class ChildProvider(WorkerCodexProvider):
        def resolve_executable(self):
            return sys.executable

        def exec_argv(self, request):
            argv = super().exec_argv(request)
            return [sys.executable, str(child), str(received), *argv[1:]]

    ws = SimpleNamespace(path=tmp_path)
    delivered = _deliver_prompt(text, ws, 10, provider_id="codex")
    assert delivered == text
    assert not (tmp_path / "context/prompt.md").exists()
    request = ExecRequest(prompt=delivered, workdir=str(tmp_path),
                          permission=Permission.READ_ONLY, resume_session=session,
                          extra_args=["--ignore-user-config", "-c", "mcp_servers={}"])
    events = list(_exec_stream(ChildProvider(), request, None))
    actual = json.loads(received.read_text(encoding="utf-8"))
    assert actual["sha"] == hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert actual["argv"][-1] == "-"
    assert len(" ".join(actual["argv"])) < 1000
    assert actual["argv"][actual["argv"].index("--sandbox") + 1] == "read-only"
    assert "--ignore-user-config" in actual["argv"]
    if session:
        assert actual["argv"][-3:] == ["resume", session, "-"]
        assert actual["argv"].index("--sandbox") < actual["argv"].index("resume")
    assert any(e.kind is ExecEventKind.RESULT and e.text == "received" for e in events)


def test_stdin_file_closes_after_launch_failure():
    captured = []

    def spawn(*args, **kwargs):
        captured.append(kwargs["stdin"])
        raise OSError("launch failed")

    def stream(provider, request, *, popen, **kwargs):
        popen(["missing"], stdin=None)
        yield

    with pytest.raises(OSError, match="launch failed"):
        list(stream_with_prompt_stdin(stream, None, ExecRequest(prompt="본문"), popen=spawn))
    assert len(captured) == 1 and captured[0].closed


def test_codex_runner_initial_and_correction_keep_full_instructions(tmp_path):
    from cliagents import ExecEvent
    from worker.runner import Runner
    from test_worker import _repo, _settings

    repo, instance = _repo()
    requests = []

    def execute(provider, request, env):
        requests.append(request)
        yield ExecEvent(kind=ExecEventKind.RUN_START, session_id="conversation")
        answer = "형식 오류" if len(requests) == 1 else '{"cause":"fixed","failure_mode":"f","guide_card":{"recommendation":"검토"}}'
        yield ExecEvent(kind=ExecEventKind.RESULT, text=answer, session_id="conversation")

    runner = Runner(_settings(tmp_path, cli_agent="codex", max_inline_prompt_chars=1), repo,
                    exec_fn=execute, schema_prompt="SCHEMA-MARKER",
                    resolve_provider=lambda _: SimpleNamespace(id="codex"))
    assert runner.poll_once() == 1
    assert len(requests) == 2
    assert "SCHEMA-MARKER" in requests[0].prompt and "## 결과 제출 형식" in requests[0].prompt
    assert "cause" in requests[1].prompt and "failure_mode" in requests[1].prompt
    assert requests[1].resume_session == "conversation"
    assert all("먼저 그 파일을 Read 도구로" not in request.prompt for request in requests)
    assert all("--ignore-user-config" in request.extra_args for request in requests)
    row = next(w for w in repo.list_workitems(proc_inst_id=instance["proc_inst_id"])
               if w["activity_id"] == "task:diagnose")
    assert row["status"] == "SUBMITTED" and row["output"]["cause"] == "fixed"
