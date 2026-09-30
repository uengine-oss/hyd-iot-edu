from plantsim import edge


def test_command_source_is_derived_from_topic_not_payload():
    # a payload claiming source FUXA on cmd/auto must still be treated as HITL (only the gateway publishes cmd/auto)
    assert edge.source_for("cmd/auto", {"source": "FUXA", "cmdId": "X"}) == "HITL"
    assert edge.source_for("cmd/manual", {"source": "HITL"}) == "FUXA"
    assert edge.source_for("cmd/manual", {"FanSpeedSP": 80}) == "FUXA"
