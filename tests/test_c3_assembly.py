"""C3 조립: 열린 일들을 닫은 것 — 카드가 실어 온 정비 시간 · 결과 보고 측정값 · 시나리오 에이전트 묶기 · 워커 한국어 규칙."""
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
import importlib.util

import pytest

from agentsvc import cards, decide as decide_mod
from procsvc import bpmn_import as B, effect_parts, engine
from entsim import data as entdata
from test_instance_mode import world, NOW  # noqa: F401  (world 는 fixture)
import test_c2_execution as c2

ROOT = Path(__file__).resolve().parents[1]


def _flows():
    spec = importlib.util.spec_from_file_location("c3_flows", ROOT / "scripts" / "c3_flows.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------- 카드가 정비 시간을 싣는다
WINDOWS = {"hours_at_next_window": {"id": "MW-HYD-02-N-1", "starts_at": "2026-10-09T21:00:00+09:00", "name": "이번 예정된 정비 시간"},
           "hours_at_following_window": {"id": "MW-HYD-02-M-1", "starts_at": "2026-10-21T06:00:00+09:00", "name": "그다음 예정된 정비 시간"}}
COMPLIANCE = [
    {"rule": "rule:pm-window-limit", "applies": ["skill:pm-11", "skill:pm-14"], "tests": [{"variable": "hours_at_next_window", "operator": ">", "value": 2200}]},
    {"rule": "rule:pm-defer-limit", "applies": ["skill:pm-13"], "tests": [{"variable": "hours_at_following_window", "operator": ">", "value": 2200}]},
    {"rule": "rule:pm-stop-order", "applies": ["skill:pm-12"], "tests": [{"variable": "order_due_h", "operator": "<", "value": 24}]},
    {"rule": "rule:ts1-hard", "tests": [{"variable": "forecast_ts1", "operator": ">=", "value": 65}]}]


def test_each_pm_card_carries_the_window_its_own_rules_test_and_a_stop_card_is_immediate():
    wo = {"kind": "work_order", "actions": [{"code": "WO_CREATE", "kind": "transaction"}]}
    assert cards.option_window(COMPLIANCE, "skill:pm-11", wo, WINDOWS)["id"] == "MW-HYD-02-N-1"
    assert cards.option_window(COMPLIANCE, "skill:pm-14", wo, WINDOWS)["id"] == "MW-HYD-02-N-1"
    w13 = cards.option_window(COMPLIANCE, "skill:pm-13", wo, WINDOWS)
    assert w13["id"] == "MW-HYD-02-M-1" and w13["basis"] == "hours_at_following_window"
    assert cards.option_window(COMPLIANCE, "skill:pm-12", wo, WINDOWS) == {"immediate": True, "name": "즉시 (지금 정지하고 시행)", "label": "즉시"}
    # 일정 판단이 아니면(창 사실 없음) 카드에 시점이 없다 — A · C 카드는 그대로
    assert cards.option_window(COMPLIANCE, "skill:pm-11", wo, None) is None
    assert cards.option_window(COMPLIANCE, "skill:fan-max", {"kind": "control"}, WINDOWS) is None
    # 정비 작업이 없는 카드(발주만 하는 구매 카드)는 작업지시 종류여도 정비 시점이 없다 — 발주 카드에 '즉시 (지금 정지하고 시행)'이 붙지 않는다
    buy = {"kind": "work_order", "actions": [{"code": "PR_CREATE", "kind": "transaction", "value": "sup:b"}]}
    assert cards.option_window(COMPLIANCE, "skill:sop-pur-11", buy, WINDOWS) is None


def test_pm_windows_come_from_the_cmms_row_and_the_memory_row_has_the_following_window():
    row = entdata.pm_row("HYD-02", {"since_pm_h": 1950, "total_h": 9950, "cycle": 1}, None, {})
    assert row["following_window_id"].startswith("MW-HYD-02-M-") and row["following_window_at"]
    wins = decide_mod.pm_windows(row)
    assert wins["hours_at_next_window"]["id"] == row["night_window_id"] and wins["hours_at_following_window"]["id"] == row["following_window_id"]
    assert decide_mod.pm_windows({}) == {}                                   # 창 id 가 없으면 지어내지 않는다


def _b_with_card_window(world, window, readings=None):
    c2.deploy(world, c2.B_FLOW, c2.b_mapping(), "b_pm")
    out = c2.Outside(world)
    out.tags = dict(readings or c2.GOOD)
    rt = world["rt"]
    inst = rt.on_alert_raise(c2.pm_alert(), now=NOW)
    inc = world["incidents"][engine.variables(inst)["incident"]]
    d = c2.b_decision(inc.id)
    d["options"][0]["window"] = window
    world["book"][d["id"]] = d
    rt.submit(c2._row(rt, inst, "T_agent")["id"], {"decision": {"recommended": d["recommended"]}, "decision_id": d["id"]}, now=NOW)
    rt.select(c2._row(rt, inst, "T_approve")["id"], d["id"], d["options"][0]["id"], "박정비", "role:prod-mgr", now=NOW)
    return rt, inst, out


def test_b_work_order_follows_the_chosen_cards_window_not_the_alerts_night_window(world):
    following = {"id": "MW-HYD-02-M-202610210600", "starts_at": "2026-10-21T06:00:00+09:00", "name": "그다음 예정된 정비 시간",
                 "basis": "hours_at_following_window"}
    rt, inst, out = _b_with_card_window(world, following)
    wo = out.calls[0]
    night = engine.variables(inst)["alert"]["evidence"]["night_window_id"]
    assert wo["code"] == "WO_CREATE" and wo["window"] == {"id": following["id"], "starts_at": following["starts_at"]} and wo["window"] != night


def test_b_immediate_card_skips_the_wait_and_maintains_now(world):
    rt, inst, out = _b_with_card_window(world, {"immediate": True, "name": "즉시 (지금 정지하고 시행)", "label": "즉시"})
    assert out.calls[0]["window"] == {"label": "즉시"}
    rt.reconcile_services(now=NOW + timedelta(seconds=1))
    assert out.restores == [("HYD-02", "pump")]                                # 예정된 정비 시간 대기 없이 바로 정비
    do = c2._row(rt, inst, "T_do")
    assert do["status"] in ("DONE", "COMPLETED") or do["draft"]["wait"]["immediate"] is True


# ---------------------------------------------------------------- 결과 보고 측정값
def test_report_values_turn_measurements_into_named_rows_without_inventing_values():
    rows = effect_parts.report_values({"reobservation": {"tag": "TS1", "op": "<", "limit": 55.0, "value": 49.234, "inside": True, "cleared": True}})
    assert rows[0] == {"name": "유온 (TS1)", "value": 49.2, "unit": " ℃", "limit": "< 55 ℃", "ok": True}
    assert rows[1] == {"name": "경보 해제", "value": "예", "ok": True}
    tr = effect_parts.report_values({"test_run": {"readings": [{"tag": "PS1", "op": ">=", "limit": 165.0, "value": None, "ok": False}]}})
    assert tr == [{"name": "압력 (PS1)", "value": "값 없음", "limit": "≥ 165 bar", "ok": False},
                  {"name": "다음 정비 시점", "value": "갱신하지 않음 (시운전 미달)", "ok": False}]
    renewed = effect_parts.report_values({"test_run": {"readings": [], "counter": {"detail": "계수기 리셋 — 다음 기한 2000 h"}}})
    assert renewed == [{"name": "다음 정비 시점", "value": "계수기 리셋 — 다음 기한 2000 h", "ok": True}]
    assert effect_parts.report_values({"asset": "HYD-01"}) == []


def test_a_result_report_carries_the_measured_oil_temperature_and_a_verdict(world):
    rt, inst, inc, d = c2.open_a(world)
    c2.a_approve_and_ack(rt, inst, inc, d)
    world["ctx"].latest_tag = lambda asset, tag: 61.0
    c2.machine.on_timer(inc, "reobs", NOW, 61.0, c2.NoFx(), time_scale=20)
    rt.on_incident_update(inc.state, inc.id, inc.cleared, now=NOW)
    rep = engine.variables(rt.repo.get_instance(inst["proc_inst_id"]))["result_report"]
    assert (rep["outcome"], rep["verdict"]) == ("미달", "fail") and inc.state == "ESCALATED"
    oil = next(v for v in rep["values"] if v["name"] == "유온 (TS1)")
    assert oil["value"] == 61.0 and oil["ok"] is False and "approved_by" in rep["facts"]


def test_b_result_report_lists_the_test_run_readings(world):
    rt, inst, out = _b_with_card_window(world, None, dict(c2.GOOD, PS1=158.0))
    rt.reconcile_services(now=NOW + timedelta(seconds=28))
    rt.reconcile_services(now=NOW + timedelta(seconds=60))
    rep = engine.variables(rt.repo.get_instance(inst["proc_inst_id"]))["result_report"]
    names = {v["name"]: v for v in rep["values"]}
    assert rep["outcome"] == "미달" and names["압력 (PS1)"]["ok"] is False and names["유량 (FS1)"]["ok"] is True


# ---------------------------------------------------------------- 흐름 세 개 · 시나리오 에이전트
AGENTS = [{"id": "agent:cooling", "username": "냉각 긴급 대응 에이전트", "is_agent": True, "agent_type": "agent"},
          {"id": "agent:pm-plan", "username": "정기 정비 계획 에이전트", "is_agent": True, "agent_type": "agent"},
          {"id": "agent:spare-buy", "username": "예비품 구매 에이전트", "is_agent": True, "agent_type": "agent"},
          {"id": "role:maint-mgr", "username": "설비보전팀장", "is_agent": False},
          {"id": "role:purchasing", "username": "구매 담당", "is_agent": False}]


@pytest.mark.parametrize("did", ["c3_cooling", "c3_pm", "c3_spare"])
def test_c3_flows_import_with_their_own_agent_and_approver(world, did):
    flows = _flows()
    _, src, mapping = flows.FLOWS[did]
    rt = world["rt"]
    base = rt.definition_for({"proc_def_id": rt.defn.id, "proc_def_version": rt.base_version, "tenant_id": rt.tenant_id}).raw
    cat = B.catalog(base, AGENTS)
    r = B.check(B.parse_bpmn(src), deepcopy(mapping), {"catalog": cat, "definition_id": did, "version": "1", "file_name": f"{did}.bpmn",
                                                       "xml_sha256": "x"})
    assert r["ok"], r["problems"]
    acts = {a["id"]: a for a in r["definition"]["activities"]}
    assert acts["T_agent"]["agent"] == mapping["tasks"]["T_agent"]["agent"]
    assert acts["T_approve"]["role"] == mapping["tasks"]["T_approve"]["role"]
    humans = [a for a in r["definition"]["activities"] if str(a.get("tool") or "").startswith("formHandler:select")]
    assert len(humans) == 1                                                      # 사람 task 는 승인 하나


def test_seed_has_three_scenario_agents_with_distinct_servers_and_skills():
    seed = (ROOT / "it" / "supabase" / "seed.sql").read_text(encoding="utf-8")
    for aid, tools, skill in (("agent:cooling", "neo4j,enterprise,hyd-dmn", "cooling-emergency-response"),
                              ("agent:pm-plan", "neo4j,hyd-dmn,enterprise-maint", "pm-schedule-planning"),
                              ("agent:spare-buy", "neo4j,hyd-dmn,enterprise-purchase", "spare-purchase-planning")):
        assert f"'{aid}'" in seed and f"'{tools}'" in seed and f"('{aid}', 'hyd', '{skill}')" in seed
    assert "'설비보전팀장'" in seed and "'정비관리자'" not in seed


def test_worker_prompt_ends_with_the_korean_narration_rule():
    import sys
    sys.path.insert(0, str(ROOT / "it" / "agent-worker"))
    from worker import prompt
    text = prompt.build({"activity_name": "판단 · 제안"}, {}, workdir="/tmp/x")
    assert text.rstrip().endswith(prompt.LANGUAGE_RULE) and "Next I'll" in prompt.LANGUAGE_RULE
    from procsvc import work_rules
    assert "모든 자연어 문장은 한국어" in work_rules.constitution(None)          # G9: 공통부 — 업무 규칙이 없는 에이전트도 받는다


# ---------------------------------------------------------------- 조립 스크립트 명령 (라이브 3차: 없는 명령 deploy-reset 이 배포로 처리됨)
@pytest.mark.parametrize("argv", [["deploy-reset"], ["deploy_reset", "x"], ["depoly"], ["export"], ["check", "extra"], []])
def test_c3_flows_refuses_unknown_commands_without_calling_any_api(argv, monkeypatch, capsys):
    mod = _flows()
    calls = []
    monkeypatch.setattr(mod, "call", lambda *a, **k: calls.append(a) or {})
    assert mod.main(["c3_flows.py", *argv]) == 2
    assert calls == []                                                           # 모르는 명령은 배포로 넘어가지 않는다
    assert "사용: c3_flows.py" in capsys.readouterr().err


def test_c3_flows_deploy_reset_is_an_explicit_command_on_the_reset_api(monkeypatch):
    mod = _flows()
    calls = []
    monkeypatch.setattr(mod, "call", lambda *a, **k: calls.append(a) or {"changes": [], "message": "이미 기준 흐름입니다"})
    assert mod.main(["c3_flows.py", "deploy-reset", "강사"]) == 0
    assert [(m, p) for m, p, *_ in calls] == [("POST", "/api/flows/deploy-reset")] and calls[0][2]["by"] == "강사"


def test_c3_flows_check_never_registers_and_a_failed_check_is_a_failing_exit(monkeypatch):
    mod = _flows()
    calls = []
    def fake(method, path, body=None):
        calls.append((method, path))
        return {"check": {"problems": ["틀림"] if path.endswith("c3_pm/check") else []}}
    monkeypatch.setattr(mod, "call", fake)
    assert mod.main(["c3_flows.py", "check"]) == 1
    assert not [p for _, p in calls if p.endswith("/register") or p.endswith("/deploy")]
