"""판단 등록의 process_scope 를 모델이 옮겨 적지 않는다(2026-10-25 수업 한 바퀴 final3: 학생 흐름에서 모델이 처리 건 UUID 한 글자를 틀려
(…-b43b-… → …-b43c-…) 판단 등록이 409로 거절되고 AI 단계가 보류됐다 — 학생 PC마다 무작위로 날 수 있는 실패).
워커가 이번 실행의 process_scope 를 판단 서버(hyd-dmn) 연결 헤더로 싣고, dmn-mcp 는 헤더가 있으면 그 값을 쓴다."""
import json

from dmn_mcp import server
from worker import bridge

SCOPE = {"tenant": "hyd", "instance": "my_cooling.bc83afb6-1aa8-43db-b43b-c76ddd22f2d4", "workitem": "552b627b", "generation": 0,
         "version": "1", "consumer": "agent-worker:docker:x"}
CFG = {"mcpServers": {"hyd-dmn": {"type": "url", "url": "http://dmn-mcp:8198/mcp"},
                      "student": {"type": "url", "url": "http://host.docker.internal:8311/mcp"}}}
RUN = {"X-HYD-Process-Scope": json.dumps(SCOPE, separators=(",", ":"))}


def test_worker_writes_the_run_scope_only_into_the_judgment_server_connection(tmp_path):
    bridge.install(tmp_path, CFG, provider_id="claude-code", run_headers=RUN)
    entries = json.loads((tmp_path / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]
    assert json.loads(entries["hyd-dmn"]["headers"]["X-HYD-Process-Scope"]) == SCOPE
    assert "headers" not in entries["student"]                                   # 학생 · 외부 서버에는 싣지 않는다
    res = bridge.install(tmp_path, CFG, provider_id="codex", run_headers=RUN)
    assert "X-HYD-Process-Scope" in res.extra_args[-1] and res.extra_args[-1].count("X-HYD-Process-Scope") == 1


def test_dmn_mcp_uses_the_header_scope_over_what_the_model_typed(monkeypatch):
    typed = dict(SCOPE, instance=SCOPE["instance"].replace("b43b", "b43c"))
    monkeypatch.setattr(server, "get_http_headers", lambda: {"x-hyd-process-scope": RUN["X-HYD-Process-Scope"]})
    assert server.run_scope(typed) == SCOPE
    monkeypatch.setattr(server, "get_http_headers", lambda: {})
    assert server.run_scope(typed) == typed                                       # 헤더 없는 호출(호스트 워커 옛 판 · 직접 호출)
