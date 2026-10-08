"""U1 — task 상세(TODO 0·6·7): the portal's task panel reads GET /api/todolist/{id} (inputs · input_sources · the step's own
events · form) and the instance view (variable_sources · approvals); the worker prints one console line per tool call."""
import json as _json
import logging
import os
import re as _re
import shutil as _shutil
import subprocess as _subprocess
import uuid
from pathlib import Path as _Path

import pytest
from cliagents import ExecEvent, ExecEventKind

from procsvc import decisions as declib, engine, instance_mode, instances, machine, manual_extraction as extraction, procdb
from worker import events as ui_events
from worker.runner import Runner

import test_instance_mode as tim
from test_instance_mode import world  # noqa: F401 — pytest fixture
from test_instances import ALERT, DEF_PATH, NOW, FakeHooks, _by, _worker_turn, rt  # noqa: F401 — rt is a pytest fixture
from test_manual_extraction import document  # noqa: F401 — pytest fixture
from test_worker import _fake_exec, _repo, _settings


# ---------------------------------------------------------------- process: what the panel reads (no new API)
def test_workitem_view_and_instance_view_carry_inputs_sources_events_and_outputs_per_task():
    rt = instances.InstanceRuntime(procdb.MemoryRepo(), engine.Definition.load(DEF_PATH), FakeHooks(), time_scale=20.0)
    inst = rt.on_alert_raise(ALERT, now=NOW)
    diag = _worker_turn(rt)                                   # task:diagnose → cause · failure_mode · guide_card
    rt.repo.record_events([{"job_id": "run-1", "todo_id": diag["id"], "proc_inst_id": inst["proc_inst_id"], "crew_type": "cliagents:claude-code",
                            "event_type": "tool_usage_started", "data": {"tool": "mcp__neo4j__read_neo4j_cypher", "tool_use_id": "t1", "input": {"query": "MATCH …"}}}])
    item = rt.workitem_view(diag["id"])
    # ① 받은 입력: the activity's inputData with values; sources come from the instance (no bound snapshot on this definition)
    assert set(item["inputs"]) == {"pattern", "asset", "alert"} and item["inputs"]["asset"] == "HYD-01" and item["input_state"] == "current"
    view = rt.instance_view(inst["proc_inst_id"])
    assert view["instance"]["variable_sources"]["asset"] == {"kind": "input"}
    # ④ 다음 단계로 넘긴 값: the variable's source names this very work item, and the consumer step reads it
    assert view["instance"]["variable_sources"]["cause"]["kind"] == "workitem" and view["instance"]["variable_sources"]["cause"]["id"] == diag["id"]
    cand = next(a for a in view["definition"]["activities"] if a["id"] == "task:candidates")
    assert "cause" in cand["inputData"] and _by(rt, inst, "task:candidates")["status"] == "IN_PROGRESS"
    # ② 처리 과정: only this task's events, the tool call among them; ③ the stored output
    assert all(e["todo_id"] == diag["id"] for e in item["events"]) and [e["event_type"] for e in item["events"]][-1] == "tool_usage_started"
    assert item["output"]["cause"] == "cause:cooler-fin-fouling" and item["tool"] == "formHandler:diagnose"   # form may be absent: the panel labels by data names then


# ---------------------------------------------------------------- worker: console lines per tool call (TODO 7)
def test_console_log_lines_carry_step_tool_summary_and_elapsed_ms():
    clock = iter([10.0, 10.25])
    console = ui_events.ConsoleLog(clock=lambda: next(clock))
    row = {"proc_inst_id": "anomaly_response.HYD-01-7", "activity_name": "원인 진단"}
    start = ui_events.translate(ExecEvent(kind=ExecEventKind.TOOL_START, tool="mcp__neo4j__read_neo4j_cypher", tool_input={"query": "MATCH  (n)\n RETURN n"}, tool_use_id="t1"))[0]
    end = ui_events.translate(ExecEvent(kind=ExecEventKind.TOOL_END, tool="mcp__neo4j__read_neo4j_cypher", text="x" * 300, tool_use_id="t1", is_error=False))[0]
    assert console.line(start, row) == "[도구 시작] anomaly_response.HYD-01-7 · 원인 진단 · neo4j/read_neo4j_cypher · 입력 {\"query\": \"MATCH (n)\\n RETURN n\"}"   # one line: JSON keeps the newline escaped
    finished = console.line(end, row)
    assert finished.startswith("[도구 끝] anomaly_response.HYD-01-7 · 원인 진단 · neo4j/read_neo4j_cypher · 결과 " + "x" * 120 + "…") and finished.endswith("· 250 ms")
    assert console.line(end, row).endswith("시간 미상")                                   # an end without its start still prints
    assert console.line(ui_events.translate(ExecEvent(kind=ExecEventKind.RUN_START, text="claude-sonnet-4-6", session_id="s"))[0], row) == "[실행 시작] anomaly_response.HYD-01-7 · 원인 진단 · 모델 claude-sonnet-4-6 · 세션 s"
    assert console.line(ui_events.translate(ExecEvent(kind=ExecEventKind.ERROR, text="boom"))[0], row) == "[오류] anomaly_response.HYD-01-7 · 원인 진단 · boom"
    assert console.line(ui_events.translate(ExecEvent(kind=ExecEventKind.THINKING, text="…"))[0], row) is None   # thoughts are not console lines


def test_runner_prints_tool_calls_to_the_console(tmp_path, caplog):
    repo, inst = _repo()
    answer = '```json\n{"cause": "cause:cooler-fin-fouling", "failure_mode": "fm:cooling-loss", "guide_card": {"recommended": []}}\n```'
    r = Runner(_settings(tmp_path), repo, exec_fn=_fake_exec(answer), schema_prompt="# s", resolve_provider=lambda pid: object())
    with caplog.at_level(logging.INFO, logger="worker.runner"):
        assert r.poll_once() == 1
    lines = [m.getMessage() for m in caplog.records if m.name == "worker.runner"]
    start = next(l for l in lines if l.startswith("[도구 시작]")); end = next(l for l in lines if l.startswith("[도구 끝]"))
    assert inst["proc_inst_id"] in start and "원인 진단" in start and "neo4j/read_neo4j_cypher" in start and "MATCH …" in start
    assert "결과 […]" in end and end.endswith(" ms")
    assert lines.index(start) < lines.index(end) and any(l.startswith("[실행 시작]") and "claude-sonnet-4-6" in l for l in lines)


# ---------------------------------------------------------------- worker: the agent's own words between tool calls (블랙박스 0)
def _exec_with_prose(answer: str, deltas_before_tool=("TS1 이 ", "55 ℃ 를 넘었으니 ", "쿨러 오염부터 확인합니다."), deltas_after_tool=("근거가 맞습니다. ",)):
    """Claude Code streams prose as text deltas (cliagents providers/claude_code.py _stream_event), tool calls as whole turns."""
    def fn(provider, request, env):
        yield ExecEvent(kind=ExecEventKind.RUN_START, text="claude-sonnet-4-6", session_id="s")
        for d in deltas_before_tool:
            yield ExecEvent(kind=ExecEventKind.ASSISTANT_TEXT, text=d, session_id="s")
        yield ExecEvent(kind=ExecEventKind.TOOL_START, tool="mcp__neo4j__read_neo4j_cypher", tool_input={"query": "MATCH …"}, tool_use_id="t1", session_id="s")
        yield ExecEvent(kind=ExecEventKind.TOOL_END, tool="mcp__neo4j__read_neo4j_cypher", text="[…]", tool_use_id="t1", session_id="s")
        for d in deltas_after_tool:
            yield ExecEvent(kind=ExecEventKind.ASSISTANT_TEXT, text=d, session_id="s")
        for i in range(0, len(answer), 7):                               # the final answer also arrives as deltas
            yield ExecEvent(kind=ExecEventKind.ASSISTANT_TEXT, text=answer[i:i + 7], session_id="s")
        yield ExecEvent(kind=ExecEventKind.RESULT, text=answer, session_id="s")
    return fn


def test_note_buffer_joins_deltas_into_one_note_cut_at_the_limit_and_skips_the_final_answer():
    buf = ui_events.NoteBuffer(limit=10)
    assert buf.flush() is None                                          # nothing said → nothing stored
    buf.add("  "); assert buf.flush() is None                           # whitespace only is not a note
    buf.add("가나다"); buf.add("라마바사아자차카타")
    note = buf.flush()
    assert note.type == "assistant_note" and note.data == {"type": "text", "content": "가나다라마바사아자차… (생략됨)", "chars": 12, "truncated": True}
    assert buf.flush() is None                                          # flushed text is gone
    buf.add('{"cause": 1}'); assert buf.flush(final_text=' {"cause": 1} ') is None   # the result text is stored by task_completed
    buf.add("설명입니다. {\"a\": 1}"); assert buf.flush(final_text='{"a": 1}').data["content"] == "설명입니다."   # words before the answer stay
    row = ui_events.row_of(note, job_id="j", todo_id="w", proc_inst_id="p", crew_type="agent")
    assert row["event_type"] == "task_working" and row["data"]["type"] == "text"


def test_runner_stores_the_agents_reasoning_before_its_tool_call_and_prints_it(tmp_path, caplog):
    repo, inst = _repo()
    answer = '```json\n{"cause": "cause:cooler-fin-fouling", "failure_mode": "fm:cooling-loss", "guide_card": {"recommended": []}}\n```'
    r = Runner(_settings(tmp_path), repo, exec_fn=_exec_with_prose(answer), schema_prompt="# s", resolve_provider=lambda pid: object())
    with caplog.at_level(logging.INFO, logger="worker.runner"):
        assert r.poll_once() == 1
    diag = next(w for w in repo.list_workitems(proc_inst_id=inst["proc_inst_id"]) if w["activity_id"] == "task:diagnose")
    evs = repo.list_events(todo_id=diag["id"])
    kinds = [(e["event_type"], (e["data"] or {}).get("type")) for e in evs]
    notes = [e["data"]["content"] for e in evs if e["event_type"] == "task_working" and e["data"].get("type") == "text"]
    assert notes == ["TS1 이 55 ℃ 를 넘었으니 쿨러 오염부터 확인합니다.", "근거가 맞습니다."]   # one row per paragraph, the answer not repeated
    first_note, tool = kinds.index(("task_working", "text")), [k for k, _ in kinds].index("tool_usage_started")
    assert first_note < tool                                            # the reason is recorded before the call it explains
    assert any(m.getMessage().startswith("[판단]") and "쿨러 오염부터" in m.getMessage() for m in caplog.records)
    done = next(e for e in evs if e["event_type"] == "task_completed")
    assert '"cause"' in done["data"]["text"]                            # the final answer lives on task_completed only


# ---------------------------------------------------------------- legacy built-in pipeline: the numbers it decided with

GUIDE_CAUSES = [
    {"id": "cause:cooler-fin-fouling", "name": "쿨러 핀 오염", "prior": 0.6, "score": 0.45, "failureModeId": "fm:cooling-loss",
     "evidence": [{"id": "evd:ts1-high", "name": "유온 상승 추세", "weight": 3, "expect": "gt", "threshold": 55, "value": 58.2, "passed": True, "status": "PASS"},
                  {"id": "evd:fan-ok", "name": "팬 정상 운전", "weight": 1, "expect": "gte", "threshold": 90, "value": 60, "passed": False, "status": "FAIL"}]},
    {"id": "cause:high-ambient", "name": "높은 주변 온도", "prior": 0.3, "score": 0.0, "failureModeId": "fm:cooling-loss",
     "evidence": [{"id": "evd:amb", "name": "주변 온도 높음", "weight": 1, "expect": "gt", "threshold": 35, "value": 24, "passed": False, "status": "FAIL"}]},
]


def _full_decision(incident_id):
    p = tim._decision_payload(incident_id)
    opt = p["options"][0]
    opt.update(score=7.5, scoreParts={"bsc": 6.0, "forecast": 2.0, "warn": -0.5}, gains=[], losses=[],
               selectedBy=[{"rule": "rule:cool-select-1", "annotation": "냉각 저하 + 원격 자동 → 팬 증속 후보"}])
    alt = {"id": "skill:derate-night-clean", "sopId": "SOP-COOL-03", "name": "부하 70 % + 야간 세척", "kind": "work_order", "feasible": True, "rank": 2, "score": 3.0,
           "scoreParts": {"bsc": 4.0, "delivery": -1.0}, "approver": {"id": "role:operator", "name": "운전원", "level": 1},
           "actions": [{"code": "WO_CREATE", "kind": "transaction", "value": "쿨러 세척", "target": "sys:cmms"}],
           "violations": [], "penalties": [], "warnings": [], "selectedBy": [{"rule": "rule:cool-select-2", "annotation": "냉각 저하 → 세척 정비 후보"}]}
    p["options"].append(alt)
    p["rankRule"] = {"rule": "rule:rank-default", "annotation": "기본 순위 규칙", "rankingPolicy": {"components": {"bsc": "bsc_gain - bsc_loss", "forecast": "(60 - forecast_ts1) / 2"}}}
    return p


def _legacy_case(world):
    rt, incidents, book = world["rt"], world["incidents"], world["book"]
    inst = rt.on_alert_raise(tim.ALERT)
    inc = next(iter(incidents.values()))
    inc.card = dict(inc.card, recommended=tim.GUIDE_CARD_ACTIONS, causes=GUIDE_CAUSES, topCause="cause:cooler-fin-fouling")
    d = declib.new(_full_decision(inc.id))
    book[d["id"]] = d
    instance_mode._bridge_legacy_agent(d)
    return rt, inst, inc, d


def test_legacy_bridge_records_cause_scores_card_rules_and_score_parts_per_task(world):
    rt, inst, inc, d = _legacy_case(world)
    rows = {w["activity_id"]: w for w in rt.repo.list_workitems(proc_inst_id=inst["proc_inst_id"])}
    ev = {a: [e for e in rt.repo.list_events(todo_id=rows[a]["id"]) if e["event_type"] == "task_working" and (e["data"] or {}).get("type") == "evidence"]
          for a in ("task:diagnose", "task:candidates", "task:compliance", "task:rank")}
    assert all(len(x) == 1 for x in ev.values())                        # one evidence row per agent task
    diag = ev["task:diagnose"][0]["data"]
    assert diag["causes"][0] == {"id": "cause:cooler-fin-fouling", "name": "쿨러 핀 오염", "prior": 0.6, "score": 0.45, "passed": 1, "evidence": 2}
    assert "쿨러 핀 오염" in diag["content"] and "사전확률" in diag["method"]
    cand = ev["task:candidates"][0]["data"]
    assert [c["rules"] for c in cand["cards"]] == [["냉각 저하 + 원격 자동 → 팬 증속 후보"], ["냉각 저하 → 세척 정비 후보"]]
    assert "제외 0장" in ev["task:compliance"][0]["data"]["content"] and "경고 1건" in ev["task:compliance"][0]["data"]["content"]
    rank = ev["task:rank"][0]["data"]
    assert [(c["rank"], c["score"], c["parts"]) for c in rank["cards"]] == [(1, 7.5, {"bsc": 6.0, "forecast": 2.0, "warn": -0.5}), (2, 3.0, {"bsc": 4.0, "delivery": -1.0})]
    assert rank["formula"] == {"bsc": "bsc_gain - bsc_loss", "forecast": "(60 - forecast_ts1) / 2"} and "기본 순위 규칙" in rank["method"]
    # the evidence row comes after task_started and before task_completed of its task (the order the panel shows)
    order = [e["event_type"] for e in rt.repo.list_events(todo_id=rows["task:rank"]["id"])]
    assert order.index("task_started") < order.index("task_working") < order.index("task_completed")


# ---------------------------------------------------------------- portal: the real taskDetail.js renders real runtime data



ROOT = _Path(__file__).resolve().parents[1]
WWW = ROOT / "it" / "portal" / "www"
RENDER = ROOT / "tests" / "js" / "render_task_detail.js"
NODE = _shutil.which("node")
ENGLISH_ID = _re.compile(r"\b(?:task|cause|skill|fm|rule|ev|evd|sop|role|sys|dec):[a-z][\w.-]*"      # ontology / definition ids
                         r"|(?<![\w-])[A-Z][A-Z0-9]*_[A-Z0-9_]+(?![\w-])|\b(?:READY|DONE|FAILED|TODO|PENDING)\b"         # status / code keys (not inside a hyphenated record number like HYD-01-COOLER_DEGRADATION-7)
                         r"|\b[a-z]{3,}(?: [a-z]{3,})+\b|\b[a-z]+_[a-z_]+\b|\b(?:undefined|null|NaN)\b|\[object Object\]")      # English phrases, broken values


def _jsonable(x):
    return _json.loads(_json.dumps(x, ensure_ascii=False, default=lambda o: o.isoformat() if hasattr(o, "isoformat") else str(o)))


def _render(tmp_path, scenarios):
    if NODE is None:
        pytest.skip("node 가 없어 포털 렌더 시험을 돌릴 수 없습니다")
    fx = tmp_path / "fixture.json"
    fx.write_text(_json.dumps({"scenarios": _jsonable(scenarios)}, ensure_ascii=False), encoding="utf-8")
    out = _subprocess.run([NODE, str(RENDER), str(WWW), str(fx)], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    dump = os.environ.get("U1_RENDER_DUMP")                              # evidence: keep the rendered HTML of every scenario
    if dump:
        _Path(dump).mkdir(parents=True, exist_ok=True)
        for name, r in _json.loads(out.stdout).items():
            (_Path(dump) / f"{name}.html").write_text(f"<!-- 지금 -->\n{r['now']}\n<!-- 패널 ({r['hash']}) -->\n{r['panel']}", encoding="utf-8")
    return _json.loads(out.stdout)


def visible(html: str) -> str:
    """What a person reads without opening anything: raw folds (원문) dropped, tags and attributes stripped."""
    # folded verbatim text is kept on purpose: 원문 (raw JSON), 에이전트에게 준 지시 (the prompt as the agent got it), 에이전트 최종 답변
    html = _re.sub(r'<details class="fold small"[^>]*><summary>(?:원문|에이전트에게 준 지시|에이전트 최종 답변)</summary>.*?</details>', "", html, flags=_re.S)
    html = _re.sub(r"<code>.*?</code>", " ", html, flags=_re.S)          # score formulas are code on purpose (점수 식)
    return _re.sub(r"\s+", " ", _re.sub(r"<[^>]+>", " ", html)).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').strip()


def english_left(html: str) -> list[str]:
    return ENGLISH_ID.findall(visible(html))


def _scenario(rt_, inst, wid, name, extra=None):
    """A snapshot taken now (deep copies): later steps of the case mutate the decision and the Incident in place."""
    pid = inst["proc_inst_id"]
    return _jsonable({"name": name, "view": rt_.instance_view(pid), "wid": wid,
                      "http": {f"/api/todolist/{wid}": rt_.workitem_view(wid), **(extra or {})}})


def test_english_detector_catches_a_raw_id_and_a_raw_status_on_purpose():
    # 일부러 깨뜨림: an id the dictionary does not know, a status key and an unrendered object must be flagged
    assert english_left("<td>cause:made-up-cause</td><span>IN_PROGRESS</span><b>[object Object]</b>") == ["cause:made-up-cause", "IN_PROGRESS", "[object Object]"]
    assert english_left("<p>권장 조치 FAN_SET · L8 · legacy agent · READY · work_order</p><code>bsc_gain - bsc_loss</code>") == ["FAN_SET", "legacy agent", "READY", "work_order"]
    assert english_left('<details class="fold small" data-k="raw"><summary>원문</summary><pre>cause:x IN_PROGRESS</pre></details><p>쿨러 핀 오염</p>') == []


def test_panel_shows_five_parts_for_legacy_agent_human_and_system_tasks_in_korean(world, tmp_path):
    rt_, inst, inc, d = _legacy_case(world)
    rows = lambda: {w["activity_id"]: w for w in rt_.repo.list_workitems(proc_inst_id=inst["proc_inst_id"])}
    decision = lambda: {f"/api/decisions/{d['id']}": d}                 # read at each snapshot (select changes it in place)
    pid = inst["proc_inst_id"]
    by_hash = dict(_scenario(rt_, inst, rows()["task:candidates"]["id"], "by-hash"), wid=None, hash=f"#/instances/{pid}/task/{rows()['task:candidates']['id']}")
    sc = [by_hash, _scenario(rt_, inst, rows()["task:diagnose"]["id"], "diagnose"),
          _scenario(rt_, inst, rows()["task:rank"]["id"], "rank", decision()),
          _scenario(rt_, inst, rows()["task:select"]["id"], "select-waiting", decision())]
    sel = rows()["task:select"]
    rt_.select(sel["id"], d["id"], "skill:fan-max-derate", by="이생산", role="role:prod-mgr", reason="납기 오더 진행 중", now=tim.NOW)
    cmd = rows()["task:command"]
    sc.append(_scenario(rt_, inst, cmd["id"], "command-waiting", {f"/api/incidents/{inc.id}": inc.to_dict()}))
    machine.on_status(inc, {"cmdId": inc.cmd_id, "result": "DONE", "t": "2026-10-03T12:00:05Z"}, tim.NOW, tim.NoFx(), time_scale=20)
    rt_.on_incident_update(inc.state, inc.id, inc.cleared, now=tim.NOW)
    reo = rows()["task:reobserve"]
    sc.append(_scenario(rt_, inst, reo["id"], "reobserve-live", {f"/api/incidents/{inc.id}": inc.to_dict()}))
    sc.append(_scenario(rt_, inst, cmd["id"], "command-acked", {f"/api/incidents/{inc.id}": inc.to_dict()}))
    machine.on_alert(inc, {"alertId": inc.alert_id, "state": "CLEAR"}, tim.NoFx())
    machine.on_timer(inc, "reobs", tim.NOW, 50.0, tim.NoFx(), time_scale=20)
    rt_.on_incident_update(inc.state, inc.id, inc.cleared, now=tim.NOW)
    sc.append(_scenario(rt_, inst, reo["id"], "reobserve-done", {f"/api/incidents/{inc.id}": inc.to_dict()}))
    sc.append(_scenario(rt_, inst, sel["id"], "select-done", decision()))
    out = _render(tmp_path, sc)

    for name, r in out.items():
        text = visible(r["panel"])
        for part in ("받은 입력", "처리 과정", "판단 · 출력", "다음 단계로 넘긴 값"):
            assert part in text, (name, part)
        assert english_left(r["panel"]) == [], (name, _re.findall(r".{0,120}(?:dec|task|cause|skill):[a-z][\w.-]*.{0,40}", visible(r["panel"])))
        assert english_left(r["now"]) == [], (name, english_left(r["now"]))
    # a shared link opens the instance's 흐름 tab with that step's panel
    assert out["by-hash"]["sel"] == pid and out["by-hash"]["tab"] == "flow" and "조치 후보 조회" in visible(out["by-hash"]["panel"])
    assert "선정 규칙으로 조치 후보 2장" in visible(out["by-hash"]["panel"]) and "냉각 저하 → 세척 정비 후보" in visible(out["by-hash"]["panel"])
    assert out["diagnose"]["hash"] == f"#/instances/{pid}/task/{rows()['task:diagnose']['id']}"     # the address opens this step again
    diag = visible(out["diagnose"]["panel"])
    # 원인 점수 · 조건 표 (guide_card) + 판단 근거 (evidence row): numbers as the pipeline produced them
    assert "판단 근거" in diag and "원인 후보 2개" in diag and "쿨러 핀 오염" in diag and "0.45" in diag and "0.6" in diag
    assert "유온 상승 추세 > 55" in diag and "관측 58.2" in diag and "조건 충족" in diag and "조건 미충족" in diag
    assert "1 / 2" in diag                                                                # passed / all evidence of the top cause
    rank = visible(out["rank"]["panel"])
    assert "점수 구성" in rank and "성과 지표 +6" in rank and "예측 +2" in rank and "경고 -0.5" in rank and "납기 -1" in rank
    assert "기본 순위 규칙" in rank and "냉각 저하 + 원격 자동 → 팬 증속 후보" not in rank      # selection rules belong to the candidates step
    waiting = visible(out["select-waiting"]["panel"])
    assert "권고 팬 최대 + 부하 80 %" in waiting and "경과" in waiting and "받은 조치 카드" in waiting and "부하 70 % + 야간 세척" in waiting
    assert "지금" in visible(out["select-waiting"]["now"]) and "선택을 기다리는 중" in visible(out["select-waiting"]["now"])
    done = visible(out["select-done"]["panel"])
    assert "고른 조치 팬 최대 + 부하 80 %" in done and "납기 오더 진행 중" in done and "이생산" in done and "생산관리자" in done and "권고와 다름" not in done
    cmdw = visible(out["command-waiting"]["panel"])
    assert "보낸 명령 팬 100 % 부하 80 %" in cmdw and "설비 응답을 기다리는 중" in cmdw and "명령 번호" in cmdw
    assert "설비 응답을 기다리는 중" in visible(out["command-waiting"]["now"])
    assert "설비가 실행함" in visible(out["command-acked"]["panel"])
    live = visible(out["reobserve-live"]["panel"])
    assert "재측정까지" in live and "모의 15분 0초 = 실제 45.0 s (20배속)" in live and "유온 TS1 < 55" in live
    assert "효과를 확인하는 중" in visible(out["reobserve-live"]["now"])
    fin = visible(out["reobserve-done"]["panel"])
    assert "회복 근거" in fin and "이상 완화 유온 TS1 50.0 < 55" in fin and "경보 해제 예" in fin
    assert visible(out["reobserve-done"]["now"]).startswith("끝")


def test_select_that_differs_from_the_recommendation_is_flagged(world, tmp_path):
    # E7 (HITL 분기): choosing the second card is a real select through the runtime, not edited data
    rt_, inst, inc, d = _legacy_case(world)
    sel = next(w for w in rt_.repo.list_workitems(proc_inst_id=inst["proc_inst_id"]) if w["activity_id"] == "task:select")
    rt_.select(sel["id"], d["id"], "skill:derate-night-clean", by="김운전", role="role:operator", reason="야간 정비창에 세척", now=tim.NOW)
    out = _render(tmp_path, [_scenario(rt_, inst, sel["id"], "differs", {f"/api/decisions/{d['id']}": d})])
    text = visible(out["differs"]["panel"])
    assert "권고와 다름" in text and "부하 70 % + 야간 세척" in text and "야간 정비창에 세척" in text and "김운전 (운전원)" in text
    assert "조치 종류 넘김 정비 요청" in text and english_left(out["differs"]["panel"]) == []


def test_worker_task_and_manual_extraction_show_the_agents_words_tools_and_proposal(rt, document, tmp_path):
    runtime, _ = rt
    archive, source, proposal = document
    inst = extraction.start(runtime, source, str(uuid.uuid4()))
    runner = Runner(_settings(tmp_path / "worker"), runtime.repo,
                    exec_fn=_exec_with_prose(_json.dumps({"proposal": proposal}, ensure_ascii=False), deltas_before_tool=("원문 1쪽의 정비 절차를 ", "인용으로 찾습니다."), deltas_after_tool=()),
                    schema_prompt="ManualSection Skill Step", resolve_provider=lambda _: object())
    assert runner.poll_once() == 1
    wid = runtime.repo.list_workitems(proc_inst_id=inst["proc_inst_id"])[0]["id"]
    running = _scenario(runtime, inst, wid, "manual-submitted")
    assert runtime.poll_once() == 1
    out = _render(tmp_path, [running, _scenario(runtime, inst, wid, "manual-done")])
    for name in ("manual-submitted", "manual-done"):
        text = visible(out[name]["panel"])
        assert "에이전트 판단" in text and "원문 1쪽의 정비 절차를 인용으로 찾습니다." in text, name   # the agent's words, not hidden
        assert "neo4j · read_neo4j_cypher" in text or "지식 그래프" in text, name                       # the tool it called
        assert "general.txt" in text or "1쪽" in text, name                                             # manual source summarised, not dumped
        assert "설명입니다. 설명입니다. 설명입니다." not in text, name
        assert english_left(out[name]["panel"]) == [], (name, english_left(out[name]["panel"]))
    done = visible(out["manual-done"]["panel"])
    assert "절차 1" in done and "SOP-EXTRACT-1 벨트 점검" in done and "SOP ID는 등록 제안입니다." in done
    assert "결과 제출 · 다음 단계로 넘기는 중" in visible(out["manual-submitted"]["now"]) and visible(out["manual-done"]["now"]).startswith("끝")
