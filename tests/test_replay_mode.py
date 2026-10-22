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


def test_replay_is_inert_without_query():
    js = (rc.WWW / "replay.js").read_text(encoding="utf-8")
    # 쿼리가 없으면 첫 분기에서 빠져나가 fetch · EventSource · 저장소를 건드리지 않는다
    head = js[: js.index("const MODE")]
    assert "if (!replayId && !recordId) return;" in head


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
