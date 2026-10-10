"""랩 자동 확인이 판정하려는 것을 재는가: 정답 예는 통과하고, 틀린 결과는 그 기준에서 미통과가 난다.

여기서는 실행 환경(그래프 · DB · MCP) 없이 판정할 수 있는 랩과 공용 부품을 본다. 실행 환경이 필요한 랩은 test_labs_live.py.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

import pytest

from test_labs_support import ANSWERS, KIT

import wrong_results
from labcheck import day5, mcpclient
from labcheck.__main__ import run_lab
from labcheck.core import Report, Stop
from labkit import settings

OFFLINE_LABS = ["3-1", "3-2", "4-1", "5-1", "6-1", "6-4", "7-1", "7-2", "7-3"]
OFFLINE_WRONGS = [wrong for wrong in wrong_results.WRONGS
                  if wrong.lab in OFFLINE_LABS and wrong.files and not (wrong.graph or wrong.undo or wrong.after)]


def make_project(tmp_path, monkeypatch):
    """정답 예를 학생 폴더 모양으로 놓는다(실행 환경이 필요 없는 랩에 쓰는 것만)."""
    project = tmp_path / "project"
    work = project / "work"
    work.mkdir(parents=True)
    for name in ("decision_table.json", "evaluate.py", "split_manual.py", "candidates.json", "recommend.py", "review.py", "hitl.py"):
        shutil.copy2(ANSWERS / "work" / name, work / name)
    shutil.copytree(ANSWERS / "work" / "meeting", work / "meeting")
    shutil.copytree(ANSWERS / ".claude", project / ".claude")
    (work / "agent" / "answers").mkdir(parents=True)
    for name in ("system_prompt.md", "agent.py"):
        shutil.copy2(ANSWERS / "work" / "agent" / name, work / "agent" / name)
    draft = {"question_id": "q1", "question": "…", "status": "보류", "answer": "도구가 없어 확인하지 못했습니다.", "causes": [], "actions": [],
             "evidence": [], "missing": ["조회 도구가 연결되지 않음"], "control": "없음", "tool_calls": []}
    (work / "agent" / "answers" / "draft_q1.json").write_text(json.dumps(draft, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("LAB_PROJECT_DIR", str(project))
    env = {"LAB_PROJECT_DIR": str(project), "PYTHONPATH": str(KIT)}
    run = lambda *command: subprocess.run([sys.executable, *command], cwd=KIT, env={**os.environ, **env},  # noqa: E731
                                          capture_output=True, text=True, check=True)
    run(str(work / "split_manual.py"))
    case = str(KIT / "day7" / "inputs" / "case_base.json")
    run(str(work / "recommend.py"), "--case", case, "--out", str(work / "day7" / "proposal_base.json"))
    run(str(work / "recommend.py"), "--case", case, "--available-minutes", "30", "--out", str(work / "day7" / "proposal_whatif.json"))
    for name in ("ok", "missing_evidence"):
        done = run(str(work / "review.py"), "--case", case, "--proposal", str(KIT / "day7" / "inputs" / f"proposal_{name}.json"))
        (work / "day7" / f"review_{name}.json").write_text(done.stdout, encoding="utf-8")
    return project


@pytest.fixture
def project(tmp_path, monkeypatch):
    return make_project(tmp_path, monkeypatch)


@pytest.mark.parametrize("lab", OFFLINE_LABS)
def test_answers_pass_the_check(project, lab):
    report = run_lab(lab)
    assert report.passed, report.failed_names()
    assert len(report.items) >= 3, "기준이 너무 적다"


def test_enough_wrong_results_are_covered_offline():
    assert len(OFFLINE_WRONGS) >= 20
    assert {wrong.lab for wrong in OFFLINE_WRONGS} == set(OFFLINE_LABS)


@pytest.mark.parametrize("wrong", OFFLINE_WRONGS, ids=[f"{wrong.lab} {wrong.what}" for wrong in OFFLINE_WRONGS])
def test_a_wrong_result_fails_the_criterion_it_breaks(project, wrong):
    wrong.files(project)
    report = run_lab(wrong.lab)
    assert not report.passed
    assert any(wrong.expect in name for name in report.failed_names()), report.failed_names()


@pytest.mark.parametrize("lab", OFFLINE_LABS)
def test_an_empty_work_folder_fails_and_never_passes(tmp_path, monkeypatch, lab):
    monkeypatch.setenv("LAB_PROJECT_DIR", str(tmp_path))
    report = run_lab(lab)
    assert not report.passed and "파일이 있다" in report.failed_names()[0]


def test_a_report_with_no_criteria_is_not_a_pass():
    assert not Report("x", "빈 확인").passed


def test_require_stops_the_lab_at_the_first_unmet_precondition():
    report = Report("x", "멈춤")
    with pytest.raises(Stop):
        report.require("앞 기준", False, "이유")
    assert report.failed_names() == ["앞 기준"] and report.items[0].detail == "이유"


def test_check_that_cannot_reach_the_lab_graph_is_neither_pass_nor_fail(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    shutil.copy2(ANSWERS / "work" / "schema.json", work / "schema.json")
    env = {**os.environ, "PYTHONPATH": str(KIT), "LAB_PROJECT_DIR": str(tmp_path),
           "LAB_NEO4J_URI": "bolt://127.0.0.1:1", "LAB_NEO4J_USER": "neo4j", "LAB_NEO4J_PASSWORD": "not-used-here"}
    done = subprocess.run([sys.executable, "-m", "labcheck", "2-1"], cwd=KIT, env=env, capture_output=True, text=True)
    assert done.returncode == 2, done.stdout + done.stderr
    assert "확인할 수 없습니다" in done.stderr and "성공 기준을 모두 채웠습니다" not in done.stdout


def test_unknown_lab_number_is_refused():
    done = subprocess.run([sys.executable, "-m", "labcheck", "9-9"], cwd=KIT, env={**os.environ, "PYTHONPATH": str(KIT)},
                          capture_output=True, text=True)
    assert done.returncode != 0 and "모르는 랩" in done.stderr


# ── 공용 부품 ─────────────────────────────────────────────────
def test_settings_refuse_missing_and_placeholder_values(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("LAB_NEO4J_PASSWORD=<여기에_내가_정한_비밀번호>\nLAB_DB_HOST=127.0.0.1\n", encoding="utf-8")
    monkeypatch.setattr(settings, "env_file", lambda: env_file)
    for key in ("LAB_NEO4J_PASSWORD", "LAB_DB_HOST", "LAB_DB_PORT"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(settings.SettingsError, match="예시 글자 그대로"):
        settings.setting("LAB_NEO4J_PASSWORD")
    with pytest.raises(settings.SettingsError, match="LAB_DB_PORT 값이 없습니다"):
        settings.setting("LAB_DB_PORT")
    assert settings.setting("LAB_DB_HOST") == "127.0.0.1"
    monkeypatch.setenv("LAB_DB_HOST", "db.example")
    assert settings.setting("LAB_DB_HOST") == "db.example", "환경 변수가 .env 보다 먼저다"
    env_file.write_text("이름만있는줄\n", encoding="utf-8")
    with pytest.raises(settings.SettingsError, match=":1 줄"):
        settings.setting("LAB_DB_PORT")


def test_reset_graph_refuses_anything_but_the_lab_graph(monkeypatch):
    from labkit import reset_graph
    monkeypatch.setattr(reset_graph, "neo4j_settings", lambda: ("bolt://127.0.0.1:7687", "neo4j", "x"))
    with pytest.raises(SystemExit, match="연습용 그래프 주소가 아닙니다"):
        reset_graph.reset()


def test_mcp_config_placeholders_are_expanded_and_literals_are_reported(monkeypatch):
    monkeypatch.setenv("LAB_NEO4J_URI", "bolt://lab")
    server = {"command": "uvx", "env": {"NEO4J_URI": "${LAB_NEO4J_URI}", "NEO4J_PASSWORD": "typed-in-file", "NEO4J_READ_ONLY": "true"}}
    assert mcpclient.expand(server)["env"]["NEO4J_URI"] == "bolt://lab"
    assert set(mcpclient.literal_values(server)) == {"NEO4J_PASSWORD", "NEO4J_READ_ONLY"}
    monkeypatch.delenv("LAB_MISSING", raising=False)
    monkeypatch.setattr(settings, "env_file", lambda: KIT / "no-such-env-file")
    with pytest.raises(settings.SettingsError):
        mcpclient.expand({"url": "${LAB_MISSING}"})


def test_evidence_is_grounded_only_when_a_tool_output_holds_the_same_values():
    outputs = [{"ok": True, "causes": [{"name": "방열핀 막힘", "source": {"doc": "CM-01", "section": "2", "line": 12, "quote": "원문"}}],
                "current": {"sensor_id": "CL-01-TT-OUT", "value": 63.2, "unit": "℃"}}]
    assert day5.grounded({"kind": "문서", "doc": "CM-01", "section": "2", "line": 12, "quote": "원문"}, outputs)
    assert day5.grounded({"kind": "현재 값", "sensor_id": "CL-01-TT-OUT", "value": 63.2}, outputs)
    assert not day5.grounded({"kind": "문서", "doc": "CM-01", "section": "2", "line": 12, "quote": "지어낸 문장"}, outputs)
    assert not day5.grounded({"kind": "현재 값", "sensor_id": "CL-01-TT-OUT", "value": 70.0}, outputs)
    assert not day5.grounded({"kind": "문서"}, outputs), "값이 하나도 없는 근거는 근거가 아니다"
    assert day5.names_in(outputs) == {"방열핀 막힘"}


def test_judge_mcp_server_serves_the_table_and_refuses_unknown_actions():
    """판단 MCP 서버를 같은 프로세스에서 띄워 MCP 클라이언트로 부른다(컨테이너 없이)."""
    import asyncio

    from fastmcp import Client
    from fastmcp.exceptions import ToolError

    import labpaths
    sys.path.insert(0, str(KIT / "day6" / "judge_mcp"))
    try:
        server = labpaths.load_module("cooler_judge_server", KIT / "day6" / "judge_mcp" / "server.py")
    finally:
        sys.path.remove(str(KIT / "day6" / "judge_mcp"))

    async def scenario():
        async with Client(server.mcp) as client:
            tools = {tool.name for tool in await client.list_tools()}
            judged = (await client.call_tool("evaluate_actions", {"temp_c": 63, "fan_state": "약함", "load_pct": 85})).structured_content
            with pytest.raises(ToolError, match="결정표에 없는 조치"):
                await client.call_tool("evaluate_actions", {"temp_c": 63, "fan_state": "약함", "load_pct": 85, "action_ids": ["ACT-NONE"]})
            with pytest.raises(ToolError, match="결정표에 없습니다"):
                await client.call_tool("evaluate_actions", {"temp_c": 63, "fan_state": "모름", "load_pct": 85})
            return tools, judged

    tools, judged = asyncio.run(scenario())
    assert tools == {"describe_decision_table", "evaluate_actions"}
    assert {action: item["result"] for action, item in judged["actions"].items()} == {
        "ACT-FAN-UP": "경고", "ACT-LOAD-DOWN": "허용", "ACT-FIN-CLEAN": "제외"}
