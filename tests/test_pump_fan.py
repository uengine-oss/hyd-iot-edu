"""C4 — the two other anomaly patterns of the ontology actually happen in the plant and travel the whole path:
pump internal leakage (pattern:pump-leakage → fm:volumetric-loss → skill:switch-standby-pump) and fan bearing wear
(pattern:fan-vibration → fm:bearing-degradation → skill:fan-slow-derate). Thresholds and forecast values are the
ontology's (instances.cypher): PS1 < 165 ∧ FS1 < 8.0 ∧ LoadSP ≥ 80 · VS1 > 1.2 rising · fc:pump-switch 182 bar ·
fc:fan-slow-vs1 1.0 mm/s · interlocks PS1 < 130 · VS1 ≥ 2.0."""
from datetime import timedelta

import pytest

from det import cep
from gw import validate as gw
from hydcommon import schemas
from hydcommon.timeutil import now, to_iso
from plantsim import plant as plantmod, plc, thermal
from procsvc import definition, machine


def run(s, seconds, running=True):
    for _ in range(int(seconds)):
        thermal.step(s, 1.0, running)
    return s


def settled(**over):
    s = thermal.UnitState()
    for k, v in over.items():
        setattr(s, k, v)
    return run(s, 1500)


# ---------------------------------------------------------------- thermal model
def test_healthy_unit_matches_the_ontology_design_point():
    s = settled()
    assert 180 <= s.ps1 <= 184 and 8.8 <= s.fs1 <= 9.2 and 0.5 <= s.vs1 <= 0.7      # sv:ps1 182 · sv:fs1 9 · sv:vs1 0.6
    assert 46 <= s.ts1 <= 50


def test_pump_leak_drops_pressure_and_flow_below_the_pattern_lines_at_full_load():
    s = settled(leak=thermal.DEGRADED_LEAK)
    assert s.ps1 < cep.RAISE_PS1 and s.fs1 < cep.RAISE_FS1, (s.ps1, s.fs1)
    assert s.ps1 > thermal.TRIP_PS1                       # a leak this size does not reach the low-pressure interlock
    assert s.ts1 < cep.RAISE_TS1 and s.ce > cep.RAISE_CE  # and it does not look like a cooler problem


def test_switching_to_standby_pump_restores_pressure_fc_pump_switch():
    s = settled(leak=thermal.DEGRADED_LEAK)
    s.pump = "B"
    run(s, 60)
    assert 180 <= s.ps1 <= 184 and s.fs1 >= 8.8          # fc:pump-switch sv:ps1 182 bar


def test_derate_to_70_masks_the_pattern_but_pressure_stays_under_165_fc_pump_derate70():
    s = settled(leak=thermal.DEGRADED_LEAK, load_pct=70.0)
    assert s.load_pct < cep.RAISE_LOAD and s.ps1 < 165    # fc:pump-derate70 sv:ps1 160 bar: mitigation, not recovery


def test_bearing_wear_raises_vibration_above_1_2_and_fan_speed_amplifies_it():
    s = settled(bearing_wear=thermal.DEGRADED_BEARING)
    assert cep.RAISE_VS1 < s.vs1 < thermal.TRIP_VS1, s.vs1
    assert s.ts1 < 52 and s.ce > 80                       # evd:ts1-normal: the oil is fine, it is the fan
    s.fan_pct = 40.0
    run(s, 60)
    assert s.vs1 < cep.RAISE_VS1 and 0.85 <= s.vs1 <= 1.05  # fc:fan-slow-vs1 1.0 mm/s
    s.fan_pct = 100.0
    run(s, 60)
    assert s.vs1 >= thermal.TRIP_VS1                       # "팬이 빠를수록 진동이 크다": fan 100 % on a worn bearing trips


# ---------------------------------------------------------------- soft-PLC
def auto(cmd_id, *writes):
    return {"cmdId": cmd_id, "source": "HITL", "expiresAt": to_iso(now() + timedelta(seconds=120)),
            "writes": [{"res": r, "v": v} for r, v in writes]}


def test_plc_pump_select_and_stop_writes():
    p, u = plc.PlcState(), thermal.UnitState()
    r = plc.apply_command(p, u, auto("C1", ("PumpSelect", 1)), source="HITL", now=now())
    assert r.result == "DONE" and u.pump == "B"
    r = plc.apply_command(p, u, auto("C2", ("Stop", 1)), source="HITL", now=now())
    assert r.result == "DONE" and p.state == "STOP" and p.trip is None
    u.ts1 = 50.0
    r = plc.apply_command(p, u, auto("C3", ("Reset", 1)), source="HITL", now=now())
    assert r.result == "DONE" and p.state == "RUN"
    r = plc.apply_command(p, u, auto("C4", ("PumpSelect", 2)), source="HITL", now=now())
    assert r.result == "REJECTED" and r.reason == "OUT_OF_RANGE"


def test_plc_low_pressure_and_vibration_interlocks():
    p, u = plc.PlcState(), thermal.UnitState()
    u.ps1 = 125.0
    plc.check_interlock(p, u)
    assert p.state == "TRIP" and p.trip == "LOW_PRESSURE"
    p, u = plc.PlcState(), thermal.UnitState()
    u.vs1 = 2.1
    plc.check_interlock(p, u)
    assert p.state == "TRIP" and p.trip == "HIGH_VIBRATION"
    p, u = plc.PlcState(state="STOP"), thermal.UnitState()
    u.vs1 = 2.1
    plc.check_interlock(p, u)
    assert p.state == "STOP"                              # a stopped unit is not tripped again


def test_status_payload_carries_the_disturbances_and_the_running_pump():
    st = plc.status_payload("HYD-01", plc.PlcState(), thermal.UnitState(leak=0.15, pump="B"), "t")
    assert st["leak"] == 0.15 and st["bearing_wear"] == 0.0 and st["pump"] == "B"


# ---------------------------------------------------------------- plant fault injection
def test_plant_injects_each_fault_kind_as_a_ramp_and_restore_undoes_all():
    pl = plantmod.Plant(time_scale=1.0)
    r = pl.inject("HYD-01", "pump_leakage", ramp_sim_s=100)
    assert r["targets"] == {"leak": thermal.DEGRADED_LEAK}
    pl.inject("HYD-01", "fan_vibration", ramp_sim_s=100)
    assert pl.snapshot()["units"]["HYD-01"]["faults"] == ["pump_leakage", "fan_vibration"]
    pl.tick(50)
    u = pl.units["HYD-01"].state
    assert abs(u.leak - thermal.DEGRADED_LEAK / 2) < 0.01 and abs(u.bearing_wear - thermal.DEGRADED_BEARING / 2) < 0.02
    pl.tick(60)
    assert u.leak == thermal.DEGRADED_LEAK and u.bearing_wear == thermal.DEGRADED_BEARING and not pl.units["HYD-01"].faults
    assert pl.snapshot()["units"]["HYD-01"]["disturbances"] == {"cooler_health": 1.0, "leak": 0.15, "bearing_wear": 0.8, "pump": "A"}
    pl.inject("HYD-01", "restore", ramp_sim_s=10)
    pl.tick(20)
    assert (u.cooler_health, u.leak, u.bearing_wear) == (1.0, 0.0, 0.0)
    with pytest.raises(ValueError):
        pl.inject("HYD-01", "meteor")


def test_plant_cooler_injection_keeps_the_legacy_contract():
    pl = plantmod.Plant(time_scale=1.0)
    r = pl.inject("HYD-01", "cooler_degradation", 0.5, ramp_sim_s=10)
    assert r["target_health"] == 0.5 and pl.snapshot()["units"]["HYD-01"]["fault"] == "cooler_degradation"
    pl.tick(20)
    assert pl.units["HYD-01"].state.cooler_health == 0.5


def test_plant_cooler_severity_names_the_strength():
    """A146: no target + no severity = the trip-strength default (lecture scenes unchanged); "moderate" = 0.55;
    an explicit target still wins; unknown names and moderate for other kinds are refused."""
    pl = plantmod.Plant(time_scale=1.0)
    assert pl.inject("HYD-01", "cooler_degradation")["target_health"] == thermal.DEGRADED_HEALTH == 0.43
    assert pl.inject("HYD-01", "cooler_degradation", severity="high")["target_health"] == 0.43
    assert pl.inject("HYD-01", "cooler_degradation", severity="moderate")["target_health"] == thermal.MODERATE_HEALTH == 0.55
    assert pl.inject("HYD-01", "cooler_degradation", 0.3, severity="moderate")["target_health"] == 0.3
    with pytest.raises(ValueError):
        pl.inject("HYD-01", "cooler_degradation", severity="mild")
    with pytest.raises(ValueError):
        pl.inject("HYD-02", "pump_leakage", severity="moderate")
    assert pl.inject("HYD-02", "pump_leakage", severity="high")["targets"] == {"leak": thermal.DEGRADED_LEAK}


# ---------------------------------------------------------------- detector CEP
def feed(fn, st, t0, seconds, **kw):
    ev, t = None, t0
    for _ in range(int(seconds)):
        t += 1
        out = fn(st, "HYD-01", t, **kw)
        if out:
            ev = out
    return ev, t


def test_cep_pump_leakage_raises_after_hold_and_clears_when_pressure_recovers():
    st = cep.CepState()
    ev, t = feed(cep.evaluate_pump, st, 0, 59, ps1=162.0, fs1=7.6, load=90.0)
    assert ev is None and st.phase == "CANDIDATE"
    ev, t = feed(cep.evaluate_pump, st, t, 2, ps1=162.0, fs1=7.6, load=90.0)
    assert ev and ev["pattern"] == "PUMP_LEAKAGE" and ev["state"] == "RAISE" and ev["evidence"] == {"ps1": 162.0, "fs1": 7.6, "load": 90.0, "score": None}
    aid = ev["alertId"]
    ev, t = feed(cep.evaluate_pump, st, t, 61, ps1=182.0, fs1=9.0, load=90.0)      # pump B took over
    assert ev and ev["state"] == "CLEAR" and ev["alertId"] == aid and st.phase == "IDLE"


def test_cep_pump_pattern_needs_load_and_low_load_ends_the_match():
    st = cep.CepState()
    ev, _ = feed(cep.evaluate_pump, st, 0, 200, ps1=160.0, fs1=7.0, load=70.0)
    assert ev is None and st.phase == "IDLE"                                       # low pressure at low load is normal
    ev, t = feed(cep.evaluate_pump, st, 0, 61, ps1=160.0, fs1=7.0, load=90.0)
    assert ev["state"] == "RAISE"
    ev, _ = feed(cep.evaluate_pump, st, t, 61, ps1=156.0, fs1=6.0, load=70.0)      # derate-70: masked, alert clears
    assert ev["state"] == "CLEAR"


def test_stopped_pump_does_not_raise_a_leak_or_claim_existing_leak_repaired():
    st = cep.CepState()
    ev, t = feed(cep.evaluate_pump, st, 0, 120, ps1=155.47, fs1=0, load=90, running=False)
    assert ev is None and st.phase == "IDLE"  # actual OVERTEMP run counterexample
    ev, t = feed(cep.evaluate_pump, st, t, 30, ps1=160, fs1=7, load=90)
    assert st.phase == "CANDIDATE"
    ev, t = feed(cep.evaluate_pump, st, t, 90, ps1=155, fs1=0, load=90, running=False)
    assert ev is None and st.phase == "IDLE"
    ev, t = feed(cep.evaluate_pump, st, t, 61, ps1=160, fs1=7, load=90)
    aid = ev["alertId"]
    ev, t = feed(cep.evaluate_pump, st, t, 120, ps1=180, fs1=9, load=0, running=False)
    assert ev is None and st.phase == "RAISED" and st.alert_id == aid
    ev, t = feed(cep.evaluate_pump, st, t, 61, ps1=180, fs1=9, load=90, running=True)
    assert ev["state"] == "CLEAR" and ev["alertId"] == aid


def test_cep_fan_vibration_raises_only_while_rising_and_clears_under_1_1():
    st = cep.CepState()
    ev, _ = feed(cep.evaluate_fan, st, 0, 200, vs1=1.35, vs1_slope=0.0)
    assert ev is None and st.phase == "IDLE"                                       # high but flat: not the pattern
    ev, t = feed(cep.evaluate_fan, st, 0, 61, vs1=1.35, vs1_slope=0.002)
    assert ev and ev["pattern"] == "FAN_VIBRATION" and ev["state"] == "RAISE"
    ev, t = feed(cep.evaluate_fan, st, t, 61, vs1=1.15, vs1_slope=-0.001)          # between the lines: hysteresis holds
    assert ev is None and st.phase == "RAISED"
    ev, _ = feed(cep.evaluate_fan, st, t, 61, vs1=0.95, vs1_slope=-0.001)
    assert ev and ev["state"] == "CLEAR"


# ---------------------------------------------------------------- command path (schemas → gateway → PLC writes)
def test_actions_to_writes_maps_pump_select_and_stop():
    assert schemas.actions_to_writes([{"code": "PUMP_SELECT", "pump": "B"}, {"code": "STOP"}]) == [{"res": "PumpSelect", "v": 1}, {"res": "Stop", "v": 1}]
    assert schemas.actions_to_writes([{"code": "PUMP_SELECT", "pump": "A"}]) == [{"res": "PumpSelect", "v": 0}]


def test_gateway_forwards_pump_select_and_still_rejects_pressure_set():
    st = gw.GatewayState()
    st.last_status["HYD-01"] = {"mode": "REMOTE_AUTO", "state": "RUN"}
    base = {"cmdId": "CMD-P1", "asset": "HYD-01", "incident": "INC-1", "source": "HITL", "approvedBy": "PM-01",
            "approvalId": "APR-P1", "expiresAt": to_iso(now() + timedelta(seconds=120))}
    from hydcommon import schemas   # A148 check ⑤: the gateway needs process's ledger record for the command
    for c in (base | {"actions": [{"code": "PUMP_SELECT", "pump": "B"}]}, base | {"cmdId": "CMD-P2", "actions": [{"code": "PRESSURE_SET", "pressure_delta": 10}]}):
        gw.record_approval(st, {"actor": "process", "event": schemas.CMD_APPROVAL_LEDGER_EVENT, "detail": schemas.approval_ledger_record(c)})
    d = gw.validate(base | {"actions": [{"code": "PUMP_SELECT", "pump": "B"}]}, st, now())
    assert d.ok and d.mqtt_payload["writes"] == [{"res": "PumpSelect", "v": 1}]
    d = gw.validate(base | {"cmdId": "CMD-P2", "actions": [{"code": "PRESSURE_SET", "pressure_delta": 10}]}, st, now())
    assert not d.ok and d.check == "WHITELIST"                                     # rule:no-pressure-raise's old procedure never reaches the PLC
    p, u = plc.PlcState(), thermal.UnitState(leak=0.15)
    r = plc.apply_command(p, u, {"cmdId": "CMD-P1", "source": "HITL", "expiresAt": base["expiresAt"], "writes": d.mqtt_payload["writes"] if d.ok else [{"res": "PumpSelect", "v": 1}]}, source="HITL", now=now())
    assert r.result == "DONE" and u.pump == "B"


# ---------------------------------------------------------------- process re-observation per pattern
def incident(pattern, recommended):
    card = {"alert": {"alertId": "ALT-x", "asset": "HYD-01", "pattern": pattern, "state": "RAISE"}, "causes": [], "recommended": recommended}
    inc = machine.Incident.from_card("INC-C4", card)
    machine.on_card(inc)
    return inc


class FX(machine.Effects):
    def __init__(self):
        self.cmds, self.audits, self.timers = [], [], []

    def emit_cmd(self, cmd): self.cmds.append(cmd)
    def emit_audit(self, evt): self.audits.append(evt)
    def set_timer(self, name, seconds): self.timers.append((name, seconds))


def test_recovery_criterion_follows_the_alert_pattern():
    assert definition.recovery_for("PUMP_LEAKAGE") == ("PS1", ">=", 165.0) and definition.recovery_for("FAN_VIBRATION") == ("VS1", "<", 1.2)
    assert definition.recovery_for(None) is None and definition.recovery_for("SOMETHING_NEW") is None
    assert not definition.recovered('SOMETHING_NEW', 40.0)
    assert definition.recovered("PUMP_LEAKAGE", 182.0) and not definition.recovered("PUMP_LEAKAGE", 160.0) and not definition.recovered("PUMP_LEAKAGE", None)
    assert definition.as_json()["timers"]["recovery"]["FAN_VIBRATION"] == {"tag": "VS1", "op": "<", "limit": 1.2}


def test_pump_incident_resolves_on_pressure_and_fails_on_a_masked_leak():
    rec = [{"code": "PUMP_SELECT", "actionId": "action:select-pump", "name": "예비 펌프 전환", "kind": "command", "param": "pump", "value": "B", "paramRange": None},
           {"code": "WO_CREATE", "actionId": "action:work-order", "name": "씰 교체", "kind": "work_order", "param": None, "value": None, "paramRange": None}]
    inc, fx = incident("PUMP_LEAKAGE", rec), FX()
    assert inc.recovery == ("PS1", ">=", 165.0)
    cmd = machine.on_approve(inc, "PM-01", [{"code": "PUMP_SELECT", "pump": "B"}], now(), fx, time_scale=20)
    assert cmd["actions"] == [{"code": "PUMP_SELECT", "pump": "B"}]
    machine.on_status(inc, {"asset": "HYD-01", "cmdId": inc.cmd_id, "result": "DONE"}, now(), fx)
    machine.on_alert(inc, {"alertId": "ALT-x", "state": "CLEAR"}, fx)
    machine.on_timer(inc, "reobs", now(), 182.0, fx=fx, time_scale=20)
    assert inc.state == "RESOLVED" and inc.work_order is None
    reob = next(a for a in fx.audits if a["event"] == "REOBSERVATION")
    assert reob["detail"]["criterion"] == "PS1 >= 165.0" and reob["detail"]["value"] == 182.0 and reob["detail"]["ts1"] is None

    # derate-70: the alert clears (load < 80) but PS1 is still 158 → the mitigation did not recover the unit
    inc, fx = incident("PUMP_LEAKAGE", [{"code": "LOAD_SET", "name": "부하 70", "kind": "command", "param": "load_pct", "value": 70, "paramRange": [60, 100]}]), FX()
    machine.on_approve(inc, "OP-17", [{"code": "LOAD_SET", "load_pct": 70}], now(), fx, time_scale=20)
    machine.on_status(inc, {"asset": "HYD-01", "cmdId": inc.cmd_id, "result": "DONE"}, now(), fx)
    machine.on_alert(inc, {"alertId": "ALT-x", "state": "CLEAR"}, fx)
    machine.on_timer(inc, "reobs", now(), 158.0, fx=fx, time_scale=20)
    assert inc.state == "ESCALATED" and inc.reason == "MITIGATION_FAILED" and "PS1=158.0" in inc.history[-1]["note"]


def test_fan_incident_extends_once_when_vibration_is_down_but_clear_is_pending():
    rec = [{"code": "FAN_SET", "name": "팬 40", "kind": "command", "param": "fan_pct", "value": 40, "paramRange": [0, 100]},
           {"code": "LOAD_SET", "name": "부하 80", "kind": "command", "param": "load_pct", "value": 80, "paramRange": [60, 100]}]
    inc, fx = incident("FAN_VIBRATION", rec), FX()
    machine.on_approve(inc, "PM-01", [{"code": "FAN_SET", "fan_pct": 40}, {"code": "LOAD_SET", "load_pct": 80}], now(), fx, time_scale=20)
    machine.on_status(inc, {"asset": "HYD-01", "cmdId": inc.cmd_id, "result": "DONE"}, now(), fx)
    machine.on_timer(inc, "reobs", now(), 0.95, fx=fx, time_scale=20)
    assert inc.state == "RE_OBSERVING" and inc.reobs_extensions == 1 and fx.timers[-1] == ("reobs", 15.0)
    machine.on_alert(inc, {"alertId": "ALT-x", "state": "CLEAR"}, fx)
    machine.on_timer(inc, "reobs", now(), 0.93, fx=fx, time_scale=20)
    assert inc.state == "RESOLVED" and inc.history[-1]["note"] == "VS1 0.93 < 1.2"


# ---------------------------------------------------------------- A160: fan fault ramp vs the held FAN_VIBRATION rule
def _rise_above_line_s(ramp_sim_s, load=90.0, fan=60.0):
    """Noise-free simulated seconds VS1 spends above 1.2 mm/s while the bearing-wear ramp is still rising it."""
    s = settled(load_pct=load, fan_pct=fan)
    rate = thermal.DEGRADED_BEARING / ramp_sim_s
    above = 0
    for _ in range(int(ramp_sim_s)):
        s.bearing_wear = min(thermal.DEGRADED_BEARING, s.bearing_wear + rate)
        if thermal.vibration(s, fan) > cep.RAISE_VS1:
            above += 1
    return above


def test_default_fan_ramp_rises_above_the_line_for_the_hold_plus_three_20x_samples():
    """FAN_VIBRATION = VS1 > 1.2 and still rising, held 60 sim-s. At TIME_SCALE 20 one sample is 20 sim-s, so the rise above
    the line must outlast the hold by a few samples or the raise hangs on sample phase (A160 live miss after 151 s)."""
    need = cep.HOLD_S + 3 * 20
    assert plantmod.DEFAULT_RAMP_S["fan_vibration"] == 900.0
    assert _rise_above_line_s(plantmod.DEFAULT_RAMP_S["fan_vibration"]) >= need
    assert _rise_above_line_s(300.0) < need          # the old shared default: why it flaked


def test_default_fan_ramp_raises_during_the_ramp_at_20x_for_every_sample_phase():
    """Replay the real plant at TIME_SCALE 20 (one VS1 sample per wall second, ±3 ms clock jitter) through the detector's
    slope window and hold: the alert comes while the wear is still ramping, whatever the sample phase or noise seed."""
    import random
    from det.features import SlopeWindow

    def raised_at(phase, seed):
        pl = plantmod.Plant(time_scale=20)
        u = pl.units["HYD-03"]
        u.state.rng.seed(seed)
        pl.tick(60)
        if phase:
            pl.tick(phase / 20)
        r = pl.inject("HYD-03", "fan_vibration")
        assert r["ramp_sim_s"] == 900.0
        w, st, jit, t = SlopeWindow(60.0), cep.CepState(), random.Random(seed), 1000.0
        for k in range(1, 91):
            pl.tick(1.0)
            t += 1.0 + jit.uniform(-0.003, 0.003)
            w.push(t * 20, u.state.vs1)
            vs1 = u.state.vs1
            if cep._step(st, "HYD-03", t * 20, "FAN_VIBRATION", "HIGH", vs1 > cep.RAISE_VS1 and w.slope() > 0,
                         vs1 < cep.CLEAR_VS1, cep.HOLD_S, None, {}, None):
                return k
        return None
    got = [raised_at(phase, seed) for phase in range(0, 20, 4) for seed in (1, 2, 3)]
    assert all(k is not None and k <= 900 / 20 for k in got), got


def test_explicit_ramp_still_wins_and_unknown_kind_is_refused():
    pl = plantmod.Plant(time_scale=20)
    assert pl.inject("HYD-01", "fan_vibration", ramp_sim_s=100)["ramp_sim_s"] == 100
    assert pl.inject("HYD-01", "cooler_degradation")["ramp_sim_s"] == 300.0
    with pytest.raises(ValueError):
        pl.inject("HYD-01", "fan_wobble")
