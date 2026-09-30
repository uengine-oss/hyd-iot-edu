"""DAQ 'lite' profile: the CEP inputs (TS1, CE) go out every second, other tags only on a real change or a heartbeat,
and the auxiliary channels on a slow heartbeat. Cuts OT->Kafka->DB volume ~7x without starving detector or evidence SQL."""
from plantsim.daq import DaqFilter


def tags(**over):
    base = {"TS1": 48.0, "CE": 84.0, "CP": 8.1, "FanSpeedSP": 60.0, "LoadSP": 90.0, "PS1": 181.9, "PS2": 150.0, "VS1": 0.56}
    return base | over


def test_full_profile_publishes_everything_every_second():
    f = DaqFilter("full")
    assert set(f.select("HYD-01", tags(), 0.0)) == set(tags())
    assert set(f.select("HYD-01", tags(), 1.0)) == set(tags())


def test_lite_always_sends_cep_inputs_but_holds_steady_tags():
    f = DaqFilter("lite")
    first = f.select("HYD-01", tags(), 0.0)
    assert set(first) == set(tags())                     # first sample of every tag goes out
    second = f.select("HYD-01", tags(PS1=182.3), 1.0)     # PS1 moved 0.4 bar < 1.0 deadband
    assert set(second) == {"TS1", "CE"}


def test_lite_sends_a_tag_that_moves_past_its_deadband():
    f = DaqFilter("lite")
    f.select("HYD-01", tags(), 0.0)
    out = f.select("HYD-01", tags(FanSpeedSP=100.0, PS1=184.0), 1.0)
    assert {"FanSpeedSP", "PS1"} <= set(out)


def test_lite_heartbeats_core_and_aux_tags():
    f = DaqFilter("lite")
    f.select("HYD-01", tags(), 0.0)
    assert "CP" in f.select("HYD-01", tags(), 10.0)       # core heartbeat 10 s
    assert "PS2" not in f.select("HYD-01", tags(), 11.0)  # aux heartbeat is 30 s
    assert "PS2" in f.select("HYD-01", tags(), 30.0)


def test_assets_are_tracked_independently():
    f = DaqFilter("lite")
    f.select("HYD-01", tags(), 0.0)
    assert set(f.select("HYD-02", tags(), 1.0)) == set(tags())


def test_waves_only_in_full_profile():
    assert DaqFilter("full").waves is True
    assert DaqFilter("lite").waves is False
