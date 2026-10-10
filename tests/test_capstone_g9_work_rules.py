"""G9 (전체 과정 랩업 — capstone-lab.md 5.2): 에이전트 작업 규칙 = 공통부 + 업무부(에이전트 칸 users.work_rules).

고정: 기준 에이전트(work_rules = hyd-plant)가 받는 CLAUDE.md 는 분리 전 워커 상수(2fbefff workspace.py CONSTITUTION,
tests/fixtures/constitution_hyd_2fbefff.md)와 바이트 단위로 같다 — Claude Code 작업 폴더 · Codex 프롬프트 둘 다.
업무부가 없는 학생 에이전트는 공통부만 받고 처리 기록에 그 사실이 남는다. 모르는 키는 실행 실패(다른 업무 규칙으로 대신하지 않음).
"""
import json
import re
from pathlib import Path

import pytest

from procsvc import agent_authoring, procdb, work_rules
from worker.runner import NO_WORK_RULES_NOTICE, Runner
from test_worker import _fake_exec, _repo, _settings

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = (ROOT / "tests" / "fixtures" / "constitution_hyd_2fbefff.md").read_bytes()
ANSWER = '{"cause": "cause:c", "failure_mode": "fm:f", "guide_card": {"recommended": []}}'
HYD_WORDS = ("HYD", "Neo4j", "enterprise", "hyd-dmn", "PLC", "설비", "cause:", "describe_schema", "schema_prompt")


def _run(tmp_path, *, rules, cli="claude-code"):
    repo, inst = _repo()
    user = repo.list_users(["sys:agent"], "hyd")[0]
    user["work_rules"] = rules
    repo.upsert_user(user)
    reqs = []
    r = Runner(_settings(tmp_path, cli_agent=cli), repo, exec_fn=_fake_exec(ANSWER, requests=reqs), schema_prompt="# s", resolve_provider=lambda pid: object())
    r.poll_once()
    row = next(w for w in repo.list_workitems(proc_inst_id=inst["proc_inst_id"]) if w["activity_id"] == "task:diagnose")
    ws = tmp_path / "hyd" / row["id"]
    return repo, row, ws, reqs


def _notices(repo, row):
    return [e["data"].get("content") for e in repo.list_events(todo_id=row["id"]) if (e.get("data") or {}).get("type") == "notice"]


# ---------------------------------------------------------------- 바이트 고정
def test_hyd_business_part_rebuilds_the_original_constitution_byte_for_byte():
    assert work_rules.constitution(work_rules.HYD_PLANT).encode("utf-8") == ORIGINAL


def test_a_baseline_agent_gets_the_original_file_and_no_notice(tmp_path):
    repo, row, ws, _ = _run(tmp_path, rules="hyd-plant")
    assert row["draft_status"] == "COMPLETED"
    assert (ws / "CLAUDE.md").read_bytes() == ORIGINAL
    assert NO_WORK_RULES_NOTICE not in _notices(repo, row)
    assert json.loads((ws / "context" / "task.json").read_text(encoding="utf-8"))["agent"]["work_rules"] == "hyd-plant"


def test_codex_prompt_starts_with_the_same_original_text(tmp_path):
    _, row, _, reqs = _run(tmp_path, rules="hyd-plant", cli="codex")
    assert reqs[0][0].prompt.encode("utf-8").startswith(ORIGINAL + "\n\n## Ontology schema\n".encode("utf-8"))


# ---------------------------------------------------------------- 업무부 없음 · 모르는 키
def test_an_agent_without_business_rules_gets_only_the_common_part_and_the_case_says_so(tmp_path):
    repo, row, ws, _ = _run(tmp_path, rules=None)
    text = (ws / "CLAUDE.md").read_text(encoding="utf-8")
    assert text == work_rules.constitution(None)
    for word in HYD_WORDS:                                                  # 조용한 기본 HYD 문구 없음
        assert word not in text, word
    for rule in ("작업 디렉터리 밖", "도구로 확인", "지어내지 말고", "사람이 승인하기 전에는 어떤 조치도", "근거", "output/result.json",
                 "__deferred__", "모든 자연어 문장은 한국어"):
        assert rule in text, rule
    assert NO_WORK_RULES_NOTICE in _notices(repo, row)
    assert json.loads((ws / "context" / "task.json").read_text(encoding="utf-8"))["agent"]["work_rules"] is None


def test_an_unknown_business_key_fails_the_run_with_its_reason(tmp_path):
    repo, row, ws, reqs = _run(tmp_path, rules="meeting-room")
    assert reqs == []                                                       # CLI 를 띄우지 않았다
    assert row["draft_status"] == "FAILED" and not (ws / "CLAUDE.md").exists()
    errors = [json.dumps(e["data"], ensure_ascii=False) for e in repo.list_events(todo_id=row["id"]) if e["event_type"] == "error"]
    assert any("업무 규칙 'meeting-room'이(가) 없습니다" in e for e in errors), errors


# ---------------------------------------------------------------- 칸의 생산자: 시드 · 복제 · 고치기 · 만들기
def test_seed_puts_the_four_baseline_agents_under_the_hyd_rules():
    seed = (ROOT / "it" / "supabase" / "seed.sql").read_text(encoding="utf-8")
    m = re.search(r"update public\.users set work_rules = 'hyd-plant'\s+where tenant_id = 'hyd' and id in \(([^)]*)\)", seed)
    assert m and sorted(x.strip(" '") for x in m.group(1).split(",")) == ["agent:cooling", "agent:pm-plan", "agent:spare-buy", "sys:agent"]
    mig = list((ROOT / "it" / "supabase" / "migrations").glob("*_agent_work_rules.sql"))
    sql = mig[0].read_text(encoding="utf-8") if len(mig) == 1 else ""
    assert "add column if not exists work_rules text" in sql
    # 마이그레이션만 올리는 이미 시드된 DB 에서도 기준 에이전트가 HYD 글을 계속 받는다
    m2 = re.search(r"update public\.users set work_rules = 'hyd-plant'\s+where tenant_id = 'hyd' and id in \(([^)]*)\) and work_rules is null", sql)
    assert m2 and sorted(x.strip(" '") for x in m2.group(1).split(",")) == sorted(x.strip(" '") for x in m.group(1).split(","))


@pytest.fixture
def repo():
    from test_b1_agent_authoring import _seed
    r = procdb.MemoryRepo()
    _seed(r)
    return r


def test_a_clone_keeps_the_rules_and_an_edit_without_the_field_keeps_them_too(repo):
    clone = agent_authoring.clone_agent(repo, "hyd", "sys:agent")
    assert clone["work_rules"] == "hyd-plant"
    agent_authoring.update_agent(repo, "hyd", clone["id"], {"name": clone["username"], "goal": "목표만 고침"})
    assert repo.list_users([clone["id"]], "hyd")[0]["work_rules"] == "hyd-plant"
    agent_authoring.update_agent(repo, "hyd", clone["id"], {"name": clone["username"], "goal": "업무 규칙 뺌", "work_rules": ""})
    assert repo.list_users([clone["id"]], "hyd")[0]["work_rules"] is None


def test_a_new_agent_has_no_rules_and_an_unknown_key_is_refused(repo):
    made = agent_authoring.create_agent(repo, "hyd", {"name": "회의 준비 에이전트", "goal": "시간 후보 3개를 낸다"})
    assert not made.get("work_rules")
    with pytest.raises(agent_authoring.AuthoringError, match="업무 규칙 'meeting-room'"):
        agent_authoring.create_agent(repo, "hyd", {"name": "다른 에이전트", "goal": "g", "work_rules": "meeting-room"})
