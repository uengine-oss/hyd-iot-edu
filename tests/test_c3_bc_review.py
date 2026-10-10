"""C3 B · C 단순화 점검(2026-10-10 review-c3-bc.md) 뒤 근본 수정의 시험.

  F1 처리 기록 화면: 버튼으로 연 처리 건은 '수업 버튼으로 시작'(누른 사람 · 시각 · 버튼 기록 줄), 설비까지 가지 않는 흐름은 그 뜻을 적는다
  F2 시나리오 시각 기준점: 설비 처리 건이 진행 중이면 옮기지 않는다(진행 중 처리 건의 예정된 정비 시간 id 가 사라지지 않게)
  F3 누름 없는 설비 주입은 지난 누름을 지운다(다음 경보 처리 건에 남의 누름이 붙지 않게)
  F4 진행 중 · 연결 처리 건 찾기를 '테넌트 최신 N건'으로 자르지 않는다
  F6 · F7 거절 글에 내부 id 없음, 처리 건이 안 열리면 '시작'이라고 답하지 않는다
  F8 case_started 훅 실패가 처리 건 기록에도 보인다
"""
import asyncio
import json
import re
import shutil
import subprocess
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException

from entsim import state as entstate
from procsvc import engine, scenario_buttons as SB
from test_instance_mode import world, NOW, ALERT  # noqa: F401  (world 는 fixture)
from test_syllabus_flows import deploy

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")


def _reader(st):
    return lambda name, params: {"pm_status": lambda: st.pm_status(params.get("asset")),
                                 "spare_stock": lambda: st.spare_stock(params.get("part"))}[name]()


def _sensor_cases(rt, n, asset="HYD-01", start=NOW):
    """다른 처리 건 n 건을 더 최근에 연다(질문 · 시험 실행 처리 건이 쌓인 수업 중 상태)."""
    for i in range(n):
        rt.on_alert_raise(dict(ALERT, alertId=f"ALT-{asset}-X{i}", asset=asset), now=start + timedelta(seconds=i + 1))


# ---------------------------------------------------------------- F3 설비 주입의 누름
def test_an_injection_without_a_press_clears_the_last_press():
    from plantsim.plant import Plant
    plant = Plant(time_scale=1, assets=["T-1"])
    press = {"id": "PRESS-1", "button": "쿨러 열화 주입", "by": "김운전"}
    assert plant.inject("T-1", "cooler_degradation", severity="moderate", origin=press)["injection"]["id"] == "PRESS-1"
    assert plant.status("T-1")["injection"]["id"] == "PRESS-1"
    plant.units["T-1"].dirty_status = False
    out = plant.inject("T-1", "restore")                            # 정비 수행 모사의 복구(누름 없음)
    assert out["injection"] is None and plant.status("T-1")["injection"] is None and plant.units["T-1"].dirty_status is True


# ---------------------------------------------------------------- F4 진행 중 · 연결 처리 건 찾기
def test_a_running_case_is_found_even_under_many_newer_cases(world):
    deploy(world, "c3_pm")
    rt, st = world["rt"], entstate.EnterpriseState()
    read, route = _reader(st), (lambda p: "c3_pm")
    rt.on_alert_raise(SB.prepare("B", read, rt, route)["alert"], now=NOW)
    _sensor_cases(rt, 70)                                           # 테넌트 최신 60건 밖으로 밀려남
    assert SB.status(read, rt)["scenarios"]["B"]["running"] is not None
    with pytest.raises(SB.Refused, match="진행 중"):
        SB.prepare("B", read, rt, route)


def test_the_restore_press_finds_the_case_its_injection_opened_under_many_newer_cases(world):
    rt = world["rt"]
    press = dict(SB.injection_origin("쿨러 열화 주입", SB.who({"by": "김운전"})), at=NOW.isoformat())
    inst = rt.on_alert_raise(dict(ALERT, alertId="ALT-HYD-01-LINKED"), now=NOW + timedelta(seconds=1))
    rt.repo.record_events([SB.press_event(inst["proc_inst_id"], press["button"], "HYD-01", press, press["at"], {"injection_id": press["id"]})])
    _sensor_cases(rt, 40, start=NOW + timedelta(seconds=2))          # 그 뒤 HYD-01 처리 건 40건
    assert SB.case_of_injection(rt, "HYD-01", press) == inst["proc_inst_id"]
    earlier = dict(press, at=(NOW + timedelta(hours=1)).isoformat())  # 처리 건보다 나중의 주입은 그 처리 건을 열 수 없다
    assert SB.case_of_injection(rt, "HYD-01", earlier) is None


# ---------------------------------------------------------------- F6 · F7 거절 글 · 빈 성공
def test_refusals_name_no_internal_ids_and_a_missing_case_is_not_a_start(world):
    deploy(world, "c3_pm")
    rt, st = world["rt"], entstate.EnterpriseState()
    read = _reader(st)
    rt.on_alert_raise(SB.prepare("B", read, rt, lambda p: "c3_pm")["alert"], now=NOW)
    for key, route in (("B", lambda p: "c3_pm"), ("C", lambda p: None)):
        with pytest.raises(SB.Refused) as e:
            SB.prepare(key, read, rt, route)
        assert not any(x in str(e.value) for x in ("c3_pm", "PM_DUE", "SPARE_BELOW_MIN", "."+"1)")), str(e.value)
    alert = SB.build_alert("C", st.spare_stock("P-PMP-SEAL")["facts"], now=NOW)
    with pytest.raises(SB.NotStarted, match="처리 건이 열리지 않았습니다"):
        SB.started(rt, "C", alert, "c3_spare")                      # 경보는 접수됐는데 처리 건 없음


# ---------------------------------------------------------------- F2 시나리오 시각 기준점
@pytest.fixture
def buttons(world, monkeypatch):
    """process main 의 버튼 API 를 실제 런타임 · 메모리 업무 상태 위에서 부른다(enterprise-sim 호출은 기록만)."""
    from procsvc import main
    deploy(world, "c3_pm")
    deploy(world, "c3_spare")
    rt, st, posts, audits = world["rt"], entstate.EnterpriseState(), [], []
    monkeypatch.setattr(main, "PROCESS_MODE", "instance")
    monkeypatch.setattr(main.instance_mode, "current", lambda: rt)
    monkeypatch.setattr(main.instance_mode, "enterprise_read", _reader(st))
    monkeypatch.setattr(main, "_entsim_post", lambda path, body: posts.append(path) or {"ok": True})
    monkeypatch.setattr(main, "_scenario_route", lambda p: {"PM_DUE": "c3_pm", "SPARE_BELOW_MIN": "c3_spare"}[p])
    monkeypatch.setattr(main, "_audit", lambda *a, **k: audits.append(a))

    async def admit(alert):
        rt.on_alert_raise(alert, now=NOW)
    monkeypatch.setattr(main, "_admit_human_alert", admit)
    return {"main": main, "rt": rt, "posts": posts, "audits": audits}


def test_the_scenario_clock_moves_only_while_no_plant_case_is_running(buttons):
    main, posts = buttons["main"], buttons["posts"]
    first = asyncio.run(main.scenario_start("B", {"by": "박정비"}))
    assert first["reanchored"] is True and posts == ["/api/reanchor"] and first["instance"]
    posts.clear()
    with pytest.raises(HTTPException) as e:                          # 거절된 누름
        asyncio.run(main.scenario_start("B", {"by": "박정비"}))
    assert e.value.status_code == 409 and posts == []
    other = asyncio.run(main.scenario_start("C", {"by": "정구매"}))  # B 가 승인을 기다리는 동안 C 를 눌러도 B 의 정비 시간은 그대로
    assert other["reanchored"] is False and posts == [] and other["instance"]
    reset = asyncio.run(main.scenario_reset("C", {"by": "강사"}))
    assert reset["reanchored"] is False and posts == ["/erp/spare/reset"]


def test_a_press_whose_case_did_not_open_is_a_loud_500(buttons, monkeypatch):
    main = buttons["main"]

    async def lost(alert):
        return None                                                  # 접수 경로가 처리 건을 열지 못함
    monkeypatch.setattr(main, "_admit_human_alert", lost)
    with pytest.raises(HTTPException) as e:
        asyncio.run(main.scenario_start("C", {"by": "정구매"}))
    assert e.value.status_code == 500 and "열리지 않았습니다" in e.value.detail


# ---------------------------------------------------------------- F8 연결 훅 실패
def test_a_failed_case_link_is_written_on_the_case_and_the_case_stays(world):
    rt = world["rt"]

    def broken(inst):
        raise KeyError("button")
    rt.hooks.case_started = broken
    inst = rt.on_alert_raise(ALERT, now=NOW)
    assert inst and rt.repo.get_instance(inst["proc_inst_id"])["status"] == "RUNNING"
    rows = [e for e in rt.repo.list_events(proc_inst_id=inst["proc_inst_id"]) if e["job_id"] == "CASE_LINK_FAILED"]
    assert len(rows) == 1 and rows[0]["event_type"] == "error" and "button" in rows[0]["data"]["friendly"]
    assert "CASE_LINK_FAILED" in world["audits"]


# ---------------------------------------------------------------- F1 처리 기록 화면 (실제 caseRecord.js)
def _record(tmp_path, scenarios):
    if NODE is None:
        pytest.skip("node 가 없어 처리 기록 모델 시험을 돌릴 수 없습니다")
    fx = tmp_path / "fixture.json"
    fx.write_text(json.dumps({"scenarios": scenarios}, ensure_ascii=False, default=str), encoding="utf-8")
    out = subprocess.run([NODE, str(ROOT / "tests" / "js" / "render_case_record.js"), str(ROOT / "it" / "portal" / "www"), str(fx)],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def _text(html):
    """화면 글: 태그를 지우고 빈칸을 하나로(사람이 읽는 줄 그대로)."""
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


def test_the_case_record_shows_the_press_and_that_the_flow_ends_in_the_business_system(world, tmp_path):
    """수업 버튼 기록은 시작 단계에 보인다. '업무 시스템에서 끝남 · 설비 명령 없음'은 설비 단계가 하나도 없는 흐름(예비품 구매)에만 적는다 —
    정기 정비는 실라버스(10-10) 모양으로 정비 · 시운전 단계가 있다."""
    deploy(world, "c3_pm")
    deploy(world, "c3_spare")
    rt, st = world["rt"], entstate.EnterpriseState()
    person = SB.who({"by": "박정비", "user_id": "user:park-maint"})
    alert = SB.build_alert("B", st.pm_status("HYD-02")["facts"], now=NOW, person=person)
    rt.on_alert_raise(alert, now=NOW)
    b = SB.started(rt, "B", alert, "c3_pm", person)["instance"]
    a = rt.on_alert_raise(dict(ALERT, alertId="ALT-HYD-01-A1"), now=NOW)["proc_inst_id"]
    press = dict(SB.injection_origin("쿨러 열화 주입", SB.who({"by": "김운전"})), at=NOW.isoformat())
    rt.repo.record_events([SB.press_event(a, press["button"], "HYD-01", press, press["at"], {"injection_id": press["id"]})])
    c_alert = SB.build_alert("C", st.spare_stock("P-PMP-SEAL")["facts"], now=NOW, person=SB.who({"by": "정구매"}))
    rt.on_alert_raise(c_alert, now=NOW)
    c = SB.started(rt, "C", c_alert, "c3_spare", SB.who({"by": "정구매"}))["instance"]
    out = _record(tmp_path, [{"name": "B", "view": rt.instance_view(b)}, {"name": "A", "view": rt.instance_view(a)},
                             {"name": "C", "view": rt.instance_view(c)}])
    start = out["B"]["steps"][0]
    body = " ".join(x["title"] + " " + x["body"] for x in start["sections"])
    assert start["title"] == "수업 버튼으로 시작" and start["actor"] == "박정비" and "[정기 정비] 버튼을 눌러" in start["sentence"]
    assert "수업 버튼 기록 1줄" in body and "누른 사람" in body
    # 버튼 기록 줄: 무엇을 눌렀나 + 누른 사람 한 번(생산자 name 에는 사람이 없고 by 한 칸만 — 라이브 3차 "박정비 박정비")
    assert _text(body).count("수업 버튼 [정기 정비] 박정비") == 1 and "박정비 박정비" not in _text(body)
    assert "이 흐름의 끝" not in body and "설비 명령 없음" not in start["chips"]      # 정비 · 시운전 단계가 있는 흐름
    c_start = out["C"]["steps"][0]
    assert "이 흐름의 끝" in " ".join(x["title"] for x in c_start["sections"]) and "설비 명령 없음" in c_start["chips"]
    assert "수업 버튼 [예비품 구매] 정구매" in _text(" ".join(x["title"] + " " + x["body"] for x in c_start["sections"]))
    assert not [g for g in out["B"]["gaps"] if "수업 버튼" in g]                 # 버튼 기록이 처리 건에 있다 — '없다'고 적지 않는다
    a_start = out["A"]["steps"][0]
    a_body = " ".join(x["title"] + " " + x["body"] for x in a_start["sections"])
    assert a_start["title"] == "센서 경보로 시작" and "수업 버튼 [쿨러 열화 주입] 김운전" in _text(a_body) and "이 흐름의 끝" not in a_body
    assert "김운전 김운전" not in _text(a_body)


def test_c_agent_step_reads_the_cause_as_why_this_part_not_a_diagnosis(world, tmp_path):
    """라이브 3차: C 기록의 '원인을 ‘축 씰 마모’로 보고' · '판정 원인' · '판정 고장 유형'이 발주를 고장 진단처럼 읽게 했다. 판단 origin.cause_route
    (dmn-mcp 가 실제로 원인을 받아 준 근거)가 부품 경로면 '이 부품이 고치는 원인'으로 읽는다. 진단 근거면 예전 이름표 그대로."""
    import test_c2_execution as c2
    deploy(world, "c3_spare")
    rt, st = world["rt"], entstate.EnterpriseState()
    inst = rt.on_alert_raise(SB.build_alert("C", st.spare_stock("P-PMP-SEAL")["facts"], now=NOW, person=SB.who({"by": "정구매"})), now=NOW)
    d = c2.c_decision(engine.variables(inst)["incident"])
    world["book"][d["id"]] = d
    rt.submit(_row_of(rt, inst, "T_agent")["id"], {"cause": "cause:pump-shaft-seal-wear", "failure_mode": "fm:pump-volumetric-efficiency-loss",
                                                   "decision": {"recommended": d["recommended"]}, "decision_id": d["id"]}, now=NOW)
    prov = [{"variable": "cause", "name": "판정 원인", "value": "cause:pump-shaft-seal-wear", "source": "sys:agent", "sourceName": "AI 에이전트",
             "how": "파이프라인이 이미 가진 값"},
            {"variable": "failure_mode", "name": "판정 고장 유형", "value": "fm:pump-volumetric-efficiency-loss", "source": "sys:agent",
             "sourceName": "AI 에이전트", "how": "파이프라인이 이미 가진 값"}]
    def decision(route):
        return dict(d, provenance=prov, origin=dict(d["origin"], cause="cause:pump-shaft-seal-wear", failureMode="fm:pump-volumetric-efficiency-loss",
                                                  cause_route=route, cause_basis="ontology: cause -INVOLVES_PART-> part"))
    view = rt.instance_view(inst["proc_inst_id"])
    out = _record(tmp_path, [{"name": "part", "view": view, "ext": {"decision": decision("part")}},
                             {"name": "diagnosis", "view": view, "ext": {"decision": decision("diagnosis")}}])
    part = next(s for s in out["part"]["steps"] if s["type"] == "agent")
    body = _text(" ".join(x["body"] for x in part["sections"]))
    assert "이 부품이 고치는 원인 ‘" in part["sentence"] and "원인을 ‘" not in part["sentence"]
    assert "이 부품이 고치는 원인" in part["chips"] and "판정 원인" not in body and "판정 고장 유형" not in body
    assert "이 부품이 고치는 원인" in body and "그 원인이 일으키는 고장" in body
    diag = next(s for s in out["diagnosis"]["steps"] if s["type"] == "agent")
    assert "원인을 ‘" in diag["sentence"] and "판정 원인" in _text(" ".join(x["body"] for x in diag["sections"]))


def _row_of(rt, inst, activity):
    return next(w for w in rt.repo.list_workitems(proc_inst_id=inst["proc_inst_id"]) if w["activity_id"] == activity and w["status"] == "IN_PROGRESS")
