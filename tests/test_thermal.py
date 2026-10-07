from plantsim import thermal


def run(s, seconds, running=True):
    for _ in range(int(seconds)):
        thermal.step(s, 1.0, running)
    return s


def test_normal_equilibrium_about_48():
    s = thermal.UnitState()
    run(s, 6000)
    assert 46.0 <= s.ts1 <= 50.0, s.ts1


def test_degraded_reaches_trip_within_20_sim_minutes():
    s = thermal.UnitState()
    run(s, 3000)  # settle
    s.cooler_health = thermal.DEGRADED_HEALTH
    t = 0
    while s.ts1 < thermal.TRIP_TS1 and t < 3000:
        thermal.step(s, 1.0, True)
        t += 1
    assert 600 <= t <= 1800, f"reached 65C after {t}s (ts1={s.ts1:.1f})"


def test_moderate_degradation_alarms_but_never_trips():
    """A146: severity "moderate" must cross the alarm line (TS1 > 55, CE < 70) and settle below the 65 C trip."""
    s = thermal.UnitState()
    run(s, 3000)
    s.cooler_health = thermal.MODERATE_HEALTH
    peak = 0.0
    for _ in range(6000):   # 100 simulated minutes — past 6 time constants, i.e. the plateau
        thermal.step(s, 1.0, True)
        peak = max(peak, s.ts1)
    assert peak < thermal.TRIP_TS1 - 1.0, f"moderate fault approached the trip: peak {peak:.2f}"
    assert s.ts1 > 55.0 and s.ce < 70.0, (s.ts1, s.ce)
    assert abs(s.ts1 - thermal.equilibrium_ts1(90, 60, thermal.MODERATE_HEALTH)) < 0.1
    assert thermal.equilibrium_ts1(80, 100, thermal.MODERATE_HEALTH) < 52.0   # fan 100 + load 80 still clears the alarm


def test_mitigation_equilibrium_about_49():
    s = thermal.UnitState()
    s.cooler_health = thermal.DEGRADED_HEALTH
    s.fan_pct = 100
    s.load_pct = 80
    run(s, 6000)
    assert 47.0 <= s.ts1 <= 51.0, s.ts1


def test_ce_drops_below_70_when_degraded():
    s = thermal.UnitState()
    thermal.step(s, 1.0, True)
    assert s.ce > 80
    s.cooler_health = thermal.DEGRADED_HEALTH
    thermal.step(s, 1.0, True)
    assert s.ce < 70


def test_tripped_unit_cools_and_stops_pump():
    s = thermal.UnitState()
    s.ts1 = 66.0
    run(s, 600, running=False)
    assert s.eps1 == 0.0 and s.fs1 == 0.0
    assert s.ts1 < 66.0


def test_derived_sensors_are_consistent():
    s = thermal.UnitState()
    thermal.step(s, 1.0, True)
    assert s.ts2 < s.ts1
    assert 150 < s.ps1 < 200
    assert 0 < s.se <= 100


def test_mitigation_from_hot_state_falls_below_52_within_20_sim_minutes():
    s = thermal.UnitState()
    s.cooler_health = thermal.DEGRADED_HEALTH
    s.ts1 = 58.0
    s.fan_pct, s.load_pct = 100, 80
    t = 0
    while s.ts1 >= 52.0 and t < 3000:
        thermal.step(s, 1.0, True)
        t += 1
    assert t <= 1200, f"took {t}s to fall below 52C"
