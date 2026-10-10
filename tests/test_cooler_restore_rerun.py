"""A 를 연달아 돌리기: 승인한 조치(팬 100 % · 부하 80 %)로 끝난 뒤 [쿨러 복구] → 곧바로 [쿨러 열화 주입]이 다시 경보를 낸다.

결함(2026-10-10): [쿨러 복구]는 외란(쿨러 건전도)만 되돌리고 조치가 쓴 지령(FanSpeedSP 100 · LoadSP 80)을 남겼다. 그 지령에서는 moderate
열화의 평형 유온이 경보선(55 ℃) 아래라, 다음 주입이 경보를 내지 못했다(설비 /api/reset 이 있어야 다시 돌았다). 복구가 운전점도 되돌린다.
경보 판정은 detector 의 실제 규칙(det.cep.evaluate)으로 한다 — 유온 숫자만 보지 않는다."""
import asyncio

import pytest

from det import cep
from plantsim import plant as plantmod, thermal
from procsvc import scenario_buttons as SB

ASSET = SB.A_ASSET
MITIGATION = {"FanSpeedSP": 100.0, "LoadSP": 80.0}        # A 에서 승인되는 조치(팬 최대 + 부하 조정)가 PLC 에 쓰는 지령
SAMPLE_S = 20                                              # 20배속에서 표본 하나 = 시뮬레이션 20초
BUTTON_DEGRADE = SB.A_BUTTONS["degrade"]["fault"]
BUTTON_RESTORE = SB.A_BUTTONS["restore"]["fault"]


def press(pl, fault):
    """버튼이 plant-sim 에 보내는 것과 같은 주입(type → kind)."""
    body = dict(fault)
    return pl.inject(ASSET, body.pop("type"), **body)


def alerts_over(pl, st, sim_seconds):
    """sim_seconds 동안 표본마다 detector 규칙을 돌려 나온 경보(RAISE · CLEAR) 목록."""
    u, out, prev = pl.units[ASSET].state, [], pl.units[ASSET].state.ts1
    for _ in range(int(sim_seconds // SAMPLE_S)):
        pl.tick(SAMPLE_S)                                  # time_scale 1.0 → 시뮬레이션 20초
        alert = cep.evaluate(st, ASSET, pl.sim_t, u.ts1, u.ce, (u.ts1 - prev) / SAMPLE_S)
        prev = u.ts1
        if alert:
            out.append(alert["state"])
    return out


def mitigated_and_cleared():
    """열화 주입 → 경보 → 승인한 조치 지령 → 경보 해제까지 간 설비와 detector 상태."""
    pl, st = plantmod.Plant(time_scale=1.0), cep.CepState()
    press(pl, BUTTON_DEGRADE)
    assert alerts_over(pl, st, 3000) == ["RAISE"]
    u = pl.units[ASSET].state
    u.fan_pct, u.load_pct = MITIGATION["FanSpeedSP"], MITIGATION["LoadSP"]
    assert alerts_over(pl, st, 3000) == ["CLEAR"]
    return pl, st


def test_restore_then_immediate_degrade_raises_the_alarm_again():
    pl, st = mitigated_and_cleared()
    r = press(pl, BUTTON_RESTORE)
    u = pl.units[ASSET].state
    assert (u.fan_pct, u.load_pct) == (thermal.NORMAL_FAN_PCT, thermal.NORMAL_LOAD_PCT)        # 지령은 그 자리에서 평소 값
    assert r["setpoints"] == {"before": MITIGATION, "after": {"FanSpeedSP": 60.0, "LoadSP": 90.0}}
    assert r["targets"] == {"cooler_health": 1.0} and pl.units[ASSET].dirty_status
    press(pl, BUTTON_DEGRADE)                                                                  # 곧바로(복구 램프가 끝나기 전)
    assert alerts_over(pl, st, 3000) == ["RAISE"]
    assert u.ts1 < plantmod.plc.TRIP_TS1 and pl.units[ASSET].ctrl.state == "RUN"               # moderate: 경보만, 보호 정지는 아님


def test_without_the_operating_point_the_next_degrade_never_alarms():
    """고치기 전 동작의 원인 고정: 외란만 되돌리면 지령이 조치 값으로 남아 다음 주입의 평형이 경보선 아래다."""
    pl, st = mitigated_and_cleared()
    r = pl.inject(ASSET, "restore", component="cooler")
    u = pl.units[ASSET].state
    assert r["setpoints"] is None and (u.fan_pct, u.load_pct) == (100.0, 80.0)
    press(pl, BUTTON_DEGRADE)
    assert alerts_over(pl, st, 6000) == []
    assert thermal.equilibrium_ts1(80.0, 100.0, thermal.MODERATE_HEALTH) < cep.RAISE_TS1
    assert thermal.equilibrium_ts1(thermal.NORMAL_LOAD_PCT, thermal.NORMAL_FAN_PCT, thermal.MODERATE_HEALTH) > cep.RAISE_TS1


def test_the_restore_button_asks_for_the_operating_point_and_the_maintenance_restore_does_not():
    assert BUTTON_RESTORE == {"type": "restore", "component": "cooler", "operating_point": True}
    from procsvc import instance_mode
    import inspect
    assert "operating_point" not in inspect.getsource(instance_mode.plant_restore)             # 정비 복구(C2)는 지령을 건드리지 않는다


def test_operating_point_only_goes_with_restore_and_says_nothing_changed_when_already_normal():
    pl = plantmod.Plant(time_scale=1.0)
    with pytest.raises(ValueError, match="operating_point goes with restore only"):
        pl.inject(ASSET, "cooler_degradation", operating_point=True)
    assert not pl.units[ASSET].faults                                                          # 거절된 요청은 아무것도 바꾸지 않는다
    pl.units[ASSET].dirty_status = False
    r = pl.inject(ASSET, "restore", component="cooler", operating_point=True)
    assert r["setpoints"]["before"] == r["setpoints"]["after"] and not pl.units[ASSET].dirty_status
    other = pl.units["HYD-02"].state
    other.fan_pct = 100.0
    pl.inject(ASSET, "restore", operating_point=True)
    assert other.fan_pct == 100.0                                                              # 다른 설비의 지령은 그대로


def test_the_http_request_reaches_the_plant_and_a_wrong_pairing_is_a_400(monkeypatch):
    from fastapi import HTTPException
    from plantsim import main as plantmain
    pl = plantmod.Plant(time_scale=1.0)
    monkeypatch.setattr(plantmain, "plant", pl)
    pl.units[ASSET].state.fan_pct = 100.0
    out = plantmain.fault(plantmain.FaultReq(asset=ASSET, **BUTTON_RESTORE))
    assert out["setpoints"]["before"]["FanSpeedSP"] == 100.0 and pl.units[ASSET].state.fan_pct == thermal.NORMAL_FAN_PCT
    with pytest.raises(HTTPException) as e:
        plantmain.fault(plantmain.FaultReq(asset=ASSET, type="pump_leakage", operating_point=True))
    assert e.value.status_code == 400


def test_the_portal_button_sends_the_restore_and_records_the_set_point_change(monkeypatch):
    """process 의 [쿨러 복구] API → plant-sim 요청 본문 → 열화로 열린 처리 건의 기록 · 감사 기록에 지령 전 · 후가 남는다."""
    from procsvc import main

    class Repo:
        def __init__(self):
            self.events = []

        def list_instances(self, *a, **k):
            return []

        def record_events(self, rows):
            self.events += rows

    class Rt:
        tenant_id, repo = "t", Repo()

    pl, sent, audits = plantmod.Plant(time_scale=1.0), [], []
    pl.inject(ASSET, "cooler_degradation", severity="moderate", origin={"id": "PRESS-degrade", "button": "쿨러 열화 주입"})
    pl.units[ASSET].state.fan_pct, pl.units[ASSET].state.load_pct = 100.0, 80.0

    def plant_post(path, body):
        sent.append((path, body))
        body = dict(body)
        return pl.inject(body.pop("asset"), body.pop("type"), **body)

    monkeypatch.setattr(main, "PROCESS_MODE", "instance")
    monkeypatch.setattr(main.instance_mode, "current", lambda: Rt)
    monkeypatch.setattr(main, "_plant_post", plant_post)
    monkeypatch.setattr(main, "_audit", lambda *a, **k: audits.append(a))
    monkeypatch.setitem(main.plant_status, ASSET, {"injection": pl.units[ASSET].injection})
    monkeypatch.setattr(main.scenario_buttons, "case_of_injection", lambda rt, asset, inj: "c3_cooling.case-1")
    out = asyncio.run(main.scenario_a_button("restore", {"by": "김운전"}))
    (path, body), = sent
    assert path == "/api/fault" and body["operating_point"] is True and body["component"] == "cooler" and body["origin"]["id"] == out["injection_id"]
    change = {"before": {"FanSpeedSP": 100.0, "LoadSP": 80.0}, "after": {"FanSpeedSP": 60.0, "LoadSP": 90.0}}
    assert out["plant"]["setpoints"] == change and out["instance"] == "c3_cooling.case-1"
    (event,) = Rt.repo.events
    assert event["proc_inst_id"] == "c3_cooling.case-1" and event["data"]["setpoints"] == change and event["data"]["restores"] == "PRESS-degrade"
    assert audits[-1][3]["setpoints"] == change
    assert pl.units[ASSET].injection["kind"] == "restore"            # 마지막 주입은 복구 — 다음 경보가 이 누름에 잘못 이어지지 않는다
