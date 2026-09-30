from det import cep, features


def feed(st, t0, seconds, ts1, ce, slope, step=1.0):
    """Feed constant conditions for `seconds` simulated seconds; return the last non-None event."""
    ev = None
    t = t0
    for _ in range(int(seconds / step)):
        t += step
        out = cep.evaluate(st, "HYD-01", t, ts1, ce, slope)
        if out:
            ev = out
    return ev, t


def test_raise_after_hold_period():
    st = cep.CepState()
    ev, t = feed(st, 0, 30, ts1=57, ce=40, slope=0.02)
    assert ev is None and st.phase == "CANDIDATE"
    ev, t = feed(st, t, 40, ts1=58, ce=40, slope=0.02)
    assert ev and ev["state"] == "RAISE" and ev["pattern"] == "COOLER_DEGRADATION"
    assert ev["alertId"].startswith("ALT-hyd01-") and ev["asset"] == "HYD-01"
    assert st.phase == "RAISED"
    assert ev["evidence"]["ts1"] == 58 and ev["evidence"]["ce"] == 40


def test_candidate_resets_if_condition_breaks():
    st = cep.CepState()
    feed(st, 0, 30, ts1=57, ce=40, slope=0.02)
    assert st.phase == "CANDIDATE"
    feed(st, 30, 5, ts1=57, ce=40, slope=-0.01)   # slope no longer positive
    assert st.phase == "IDLE"
    ev, _ = feed(st, 35, 65, ts1=57, ce=40, slope=0.02)
    assert ev and ev["state"] == "RAISE"


def test_clear_after_recovery_hold():
    st = cep.CepState()
    ev, t = feed(st, 0, 70, ts1=58, ce=40, slope=0.02)
    raised_id = ev["alertId"]
    ev, t = feed(st, t, 30, ts1=51, ce=40, slope=-0.01)
    assert ev is None and st.phase == "CLEARING"
    ev, t = feed(st, t, 40, ts1=50, ce=40, slope=-0.01)
    assert ev and ev["state"] == "CLEAR" and ev["alertId"] == raised_id
    assert st.phase == "IDLE"


def test_clearing_reverts_to_raised_if_hot_again():
    st = cep.CepState()
    ev, t = feed(st, 0, 70, ts1=58, ce=40, slope=0.02)
    feed(st, t, 30, ts1=51, ce=40, slope=-0.01)
    assert st.phase == "CLEARING"
    feed(st, t + 30, 5, ts1=53, ce=40, slope=0.0)
    assert st.phase == "RAISED"


def test_no_raise_when_ce_healthy():
    st = cep.CepState()
    ev, _ = feed(st, 0, 200, ts1=58, ce=85, slope=0.02)
    assert ev is None and st.phase == "IDLE"


def test_trip_alert_raise_and_clear():
    st = cep.TripState()
    assert cep.trip_alert(st, "HYD-01", tripped=False) is None
    ev = cep.trip_alert(st, "HYD-01", tripped=True)
    assert ev["state"] == "RAISE" and ev["pattern"] == "OVERHEAT_TRIP" and ev["severity"] == "CRITICAL"
    assert cep.trip_alert(st, "HYD-01", tripped=True) is None
    ev2 = cep.trip_alert(st, "HYD-01", tripped=False)
    assert ev2["state"] == "CLEAR" and ev2["alertId"] == ev["alertId"]


def test_wave_features_slope_positive_for_ramp():
    f = features.wave_features([float(i) for i in range(100)])
    assert abs(f["mean"] - 49.5) < 1e-9
    assert f["slope"] > 0
    assert f["rms"] > f["mean"]


def test_slope_window_uses_simulated_seconds():
    w = features.SlopeWindow(window_s=60)
    for t in range(0, 61, 5):
        w.push(t, 48 + 0.01 * t)
    assert abs(w.slope() - 0.01) < 1e-6


def test_anomaly_score_normalised():
    b = features.Baseline(n=5)
    for v in (48.0, 48.1, 47.9, 48.0, 48.05):
        b.push("ts1", v)
    assert b.ready("ts1")
    assert features.anomaly_score(0.0, 0.0, 0.0) == 0.0
    assert 0.9 <= features.anomaly_score(8.0, 8.0, 8.0) <= 1.0
    z = b.z("ts1", 58.0)
    assert z > 3


def test_alert_ids_unique_across_detector_restarts():
    """The agent de-duplicates on alertId and the sink upserts on it: a restarted detector must not reuse ids."""
    ids = set()
    for restart in range(3):
        st = cep.CepState()                      # a fresh in-memory state, as after a container restart
        ev, _ = feed(st, 0, 70, ts1=58, ce=40, slope=0.02)
        ids.add(ev["alertId"])
    assert len(ids) == 3, ids
    trip_ids = {cep.trip_alert(cep.TripState(), "HYD-01", tripped=True)["alertId"] for _ in range(3)}
    assert len(trip_ids) == 3
