"""재생 모드(문서/시스템/참조/재생모드.md): 저장소에 든 재생 사례가 안내서 · 녹화 · 강의 자료 · 포털 판본과 맞는지, 비밀값이 없는지.
브라우저로 끝까지 따라 하는 검사는 scripts/replay_e2e.py(스택 없이 정적 서버만으로 돈다)."""
import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("replay_case", ROOT / "scripts" / "replay_case.py")
rc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rc)
CASES = [c["id"] for c in rc.load_index()["cases"]]


def test_replay_script_loads_before_portal_scripts():
    html = (rc.WWW / "index.html").read_text(encoding="utf-8")
    srcs = re.findall(r'<script src="([^"?]+)', html)
    assert srcs[0] == "replay.js", srcs[:3]


def test_without_query_only_checks_live_capability():
    js = (rc.WWW / "replay.js").read_text(encoding="utf-8")
    # 쿼리가 없으면 실제 실행이 되는지만 확인하고 빠져나간다(키 없으면 재생이 기본). fetch · EventSource · 저장소 · Date 는 바꾸지 않는다
    head = js[: js.index("const MODE")]
    assert "if (!replayId && !recordId) { if (params.get('live') !== '1') defaultToReplay(); return; }" in head
    for patched in ("window.fetch =", "window.EventSource =", "window.Date =", "defineProperty(window"):
        assert patched not in head, patched
    # 실제 실행을 막지 않는 조건: 내장 판단 · 판단 불가는 그대로 둔다
    assert "mode.agent_bridge !== 'off') return;" in head and "if (!r.ok) return;" in head


@pytest.mark.parametrize("case_id", CASES)
def test_case_consistent(case_id):
    assert rc.check_case(case_id) == []


def test_match_writes_rejects_unlisted_write():
    guide = {"items": [{"kind": "action", "title": "주입", "match": {"method": "POST", "key": "process/api/scenario/A/degrade"}}], "allow": []}
    writes = [{"method": "POST", "key": "plant/api/reset", "request": "", "t_req": 1},
              {"method": "POST", "key": "process/api/scenario/A/degrade", "request": "{}", "t_req": 2}]
    with pytest.raises(rc.CaseError, match="안내서에 없는 쓰기"):
        rc.match_writes(guide, writes, "시험")


def test_match_writes_rejects_other_input():
    guide = {"items": [{"kind": "action", "title": "주입", "match": {"method": "POST", "key": "process/api/scenario/A/degrade", "body": {"user_id": "user:kim-op"}}}]}
    writes = [{"method": "POST", "key": "process/api/scenario/A/degrade", "request": json.dumps({"user_id": None}), "t_req": 2}]
    with pytest.raises(rc.CaseError, match="정해진 입력"):
        rc.match_writes(guide, writes, "시험")


def test_secret_scan_catches_env_value(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "abcd1234efgh5678")
    assert rc.scan_secrets('{"x":"abcd1234efgh5678"}', "시험") == ["시험: 환경 변수 LLM_API_KEY 의 값"]
    assert any("키 모양" in p for p in rc.scan_secrets("token sk-" + "a" * 24, "시험"))
    assert rc.scan_secrets('{"by":"user:kim-op"}', "시험") == []


def test_recorded_mistake_is_allowed_only_when_server_refused():
    guide = {"items": [{"kind": "action", "title": "승인", "match": {"method": "POST", "key": "process/api/todolist/[0-9a-f-]+/select", "body": {"option": "skill:fan-max"}}}],
             "mistakes": [{"method": "POST", "key": "process/api/todolist/[0-9a-f-]+/select", "body": {"option": "skill:derate"}, "explain": "권한 밖 안"}]}
    refused = {"method": "POST", "key": "process/api/todolist/ab-1/select", "request": json.dumps({"option": "skill:derate"}), "status": 403, "t_req": 1}
    ok = {"method": "POST", "key": "process/api/todolist/ab-1/select", "request": json.dumps({"option": "skill:fan-max"}), "status": 200, "t_req": 2}
    assert rc.match_writes(guide, [refused, ok], "시험") == [ok]
    # 같은 모양이라도 서버가 받아들인(2xx) 쓰기는 실수로 넘기지 않는다 — 상태가 바뀐 것이기 때문
    accepted = dict(refused, status=200)
    with pytest.raises(rc.CaseError, match="정해진 입력과 다릅니다"):
        rc.match_writes(guide, [accepted, ok], "시험")
