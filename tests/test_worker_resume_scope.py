"""사람이 답한 뒤 이어 가는 실행은 이번 실행의 process_scope 를 받는다(2026-10-23 검수 · 라이브 B 판단 등록 409).
답이 오면 작업이 다시 대기열로 가고 워커가 새 담당 표시(consumer)로 잡는다. 이어 가는 세션은 첫 프롬프트에서 읽은 옛 consumer 로
판단 등록을 불러 '현재 판단 작업의 유효한 worker claim이 필요합니다'(409)로 거절됐다."""
import json
from pathlib import Path

from procsvc import decision_scope, engine
from worker import hitl
from worker.runner import Runner
from test_worker import _fake_exec, _repo, _settings


def test_resumed_run_after_a_human_answer_carries_this_claims_process_scope(tmp_path):
    repo, inst = _repo()
    reqs, scopes = [], []

    def fake(answer, **kw):
        inner = _fake_exec(answer, requests=reqs, **kw)
        def run(provider, request, env):
            task = json.loads((Path(request.workdir) / "context" / "task.json").read_text(encoding="utf-8"))
            scopes.append(task["process_scope"])          # 이 실행이 잡은 담당 표시 그대로 — task.json 은 실행마다 다시 쓴다
            yield from inner(provider, request, env)
        return run

    Runner(_settings(tmp_path), repo, exec_fn=fake("", permission_refusal="Claude requested permissions to use Bash, but you haven't granted it yet."),
           schema_prompt="# s", resolve_provider=lambda pid: object()).poll_once()
    row = next(w for w in repo.list_workitems(proc_inst_id=inst["proc_inst_id"]) if w["activity_id"] == "task:diagnose")
    asked = [e for e in repo.list_events(todo_id=row["id"]) if e["event_type"] == "human_asked"][0]
    repo.update_workitem(repo.get_workitem(row["id"]) | {"feedback": {"human_answer": "MCP 로만", "job_id": asked["job_id"]}, "draft_status": "FB_REQUESTED"})
    Runner(_settings(tmp_path), repo, exec_fn=fake('{"cause": "c", "failure_mode": "f", "guide_card": {"x": 1}}'),
           schema_prompt="# s", resolve_provider=lambda pid: object()).poll_once()

    first, second = scopes
    assert first["consumer"] and second["consumer"] and first["consumer"] != second["consumer"]
    resumed = reqs[1][0]
    assert resumed.resume_session == "sess-A" and resumed.prompt.startswith("담당자 응답: MCP 로만")
    assert json.dumps(second, ensure_ascii=False) in resumed.prompt and first["consumer"] not in resumed.prompt
    assert hitl.recall(tmp_path / "hyd" / row["id"]) is None
