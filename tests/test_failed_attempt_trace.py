"""블랙박스 없음 — 실패한 시스템 task 의 시도마다 무엇을 불렀고(서버.도구 · 입력) 무엇이 돌아왔고(출력/오류) 왜 실패했는지가
처리 건 기록(events)에 남고 task 상세 화면에서 보인다.

원인: 서비스 처리기는 처리 건 전이(instance_transaction) 안에서 돌고, 실패하면 상태와 함께 그 안에서 쓴 사건도 되돌려졌다.
설계: 상태 변경은 되돌린 그대로 두고(정합성), 그 시도의 도구 호출 사건만 따로 모았다가 되돌린 뒤 남긴다(사건 기록은 일지 —
ProcessGPT processgpt_agent_sdk database.record_events_bulk 도 상태와 따로 남긴다). 이어서 _fail 의 error 사건이 사유를 남긴다.
"""
from copy import deepcopy

from procsvc import engine, instances
from test_c2_execution import imported
from test_capstone_g3_mcp_extract import FLOW, mapping, rows
from test_instance_mode import NOW, world  # noqa: F401  (world 는 fixture)
from test_u1_task_detail import _render, _scenario, visible

REPLY = "참석 응답을 읽지 못했습니다 (서버 오류 503)"


def failing_case(world):
    _, r = imported(world, FLOW, mapping(), "qbr")
    assert r["ok"], r["problems"]
    rt = world["rt"]
    rt.register_definition(r["definition"])
    rt.deploy_definition("qbr", "1", "tester", "실패 기록 시험")
    calls = []

    def read(server, tool, arguments):                       # 도구가 오류를 돌려준다 — 매 시도 같은 답
        calls.append(deepcopy(arguments))
        return {"status": "ok", "result": {"is_error": True, "text": REPLY}}
    rt.hooks.mcp_read = read
    inst = rt.start_definition("qbr", "1", "start:QBR-F", values={"request_id": "QBR-2026-Q4-09"}, now=NOW)
    for _ in range(instances.MAX_RETRIES + 1):                # 마지막 한 번은 PENDING 이라 더 집지 않는다
        rt.poll_once(now=NOW)
    return rt, rt.repo.get_instance(inst["proc_inst_id"]), calls


def test_every_failed_attempt_up_to_pending_is_in_the_record(world):
    rt, inst, calls = failing_case(world)
    wi = rows(rt, inst, "T_check")[0]
    assert wi["status"] == "PENDING" and len(calls) == instances.MAX_RETRIES
    evs = rt.repo.list_events(todo_id=wi["id"])
    started = [e for e in evs if e["event_type"] == "tool_usage_started"]
    finished = [e for e in evs if e["event_type"] == "tool_usage_finished"]
    errors = [e for e in evs if e["event_type"] == "error"]
    # 시도마다: 부른 것(서버.도구 · 입력) · 돌아온 것(오류 본문) · 실패 사유 — 회차를 구분하는 호출 id
    assert [e["data"]["tool_use_id"].rsplit(":", 1)[1] for e in started] == ["0", "1", "2"]
    assert all(e["data"]["tool"] == "mcp__gcal__get_event" and e["data"]["input"] == {"event_id": "QBR-2026-Q4-09"} for e in started)
    assert [e["data"]["tool_use_id"] for e in finished] == [e["data"]["tool_use_id"] for e in started]
    assert all(e["data"]["is_error"] is True and e["data"]["output"] == REPLY and e["data"]["attempt_failed"] is True for e in finished)
    assert [e["data"]["retry"] for e in errors] == [1, 2, 3] and all(REPLY in e["data"]["raw_error"] for e in errors)
    # 순서: 그 회차의 호출 기록 다음에 그 회차의 실패 사유
    kinds = [(e["event_type"], (e["data"].get("tool_use_id") or "").rsplit(":", 1)[-1]) for e in evs if e["event_type"] in ("tool_usage_started", "tool_usage_finished", "error")]
    assert kinds == [("tool_usage_started", "0"), ("tool_usage_finished", "0"), ("error", ""),
                     ("tool_usage_started", "1"), ("tool_usage_finished", "1"), ("error", ""),
                     ("tool_usage_started", "2"), ("tool_usage_finished", "2"), ("error", "")]
    # 정합성: 실패한 시도의 상태 변경은 되돌린 그대로 — 출력도 다음 단계도 없다
    assert wi["output"] is None and "all_required_accepted" not in engine.variables(inst)
    assert not any(w["status"] == "DONE" for a in ("R_ok", "R_no") for w in rows(rt, inst, a))


def test_a_successful_attempt_is_recorded_once(world):
    _, r = imported(world, FLOW, mapping(), "qbr")
    rt = world["rt"]
    rt.register_definition(r["definition"])
    rt.deploy_definition("qbr", "1", "tester", "성공 기록 시험")
    rt.hooks.mcp_read = lambda s, t, a: {"status": "ok", "result": {"is_error": False, "text": '{"attendees_ok": true, "attendees": [{"count": 2}]}'}}
    inst = rt.start_definition("qbr", "1", "start:QBR-S", values={"request_id": "QBR-1"}, now=NOW)
    rt.poll_once(now=NOW)
    wi = rows(rt, inst, "T_check")[0]
    evs = [e for e in rt.repo.list_events(todo_id=wi["id"]) if e["event_type"].startswith("tool_usage")]
    assert len(evs) == 2 and not any(e["data"].get("attempt_failed") for e in evs)          # 두 번 남기지 않는다


def test_the_task_panel_shows_each_failed_call_and_why(world, tmp_path):
    rt, inst, _ = failing_case(world)
    wid = rows(rt, inst, "T_check")[0]["id"]
    out = _render(tmp_path, [_scenario(rt, inst, wid, "failed-read")])
    text = visible(out["failed-read"]["panel"])
    assert text.count("get_event") >= instances.MAX_RETRIES, text                         # 회차마다 도구 한 줄
    assert REPLY in text                                                                    # 돌아온 오류 · 실패 사유
