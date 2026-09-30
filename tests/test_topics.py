from hydcommon import topics, schemas


def test_asset_key_and_id_roundtrip():
    assert topics.asset_key("HYD-01") == "hyd01"
    assert topics.asset_id("hyd01") == "HYD-01"


def test_mqtt_topic_builders():
    assert topics.mqtt_tag("hyd01", "TS1") == "plant/hyd01/tag/TS1"
    assert topics.mqtt_wave("hyd01", "PS1") == "plant/hyd01/wave/PS1"
    assert topics.mqtt_status("hyd01") == "plant/hyd01/status"
    assert topics.mqtt_cmd_auto("hyd01") == "plant/hyd01/cmd/auto"
    assert topics.mqtt_cmd_manual("hyd01") == "plant/hyd01/cmd/manual"
    assert topics.mqtt_mode("hyd01") == "plant/hyd01/mode"
    assert topics.mqtt_alert("hyd01") == "plant/hyd01/alert"


def test_parse_mqtt_topic():
    assert topics.parse_mqtt("plant/hyd02/tag/CE") == ("hyd02", "tag", "CE")
    assert topics.parse_mqtt("plant/hyd02/status") == ("hyd02", "status", None)


def test_kafka_topic_constants():
    assert topics.K_TAG == "plant.tag"
    assert topics.K_CMD == "action.cmd"
    assert set(topics.ALL_KAFKA_TOPICS) == {"plant.tag", "plant.wave", "plant.status", "feat.1s", "alerts", "action.cmd", "audit"}


def test_validate_action_cmd_reports_missing_fields():
    errs = schemas.validate_action_cmd({})
    assert any("cmdId" in e for e in errs)
    assert any("expiresAt" in e for e in errs)


def test_validate_action_cmd_accepts_spec_sample():
    sample = {"cmdId": "CMD-0923-0042", "asset": "HYD-01", "incident": "INC-0923-01", "source": "HITL",
              "actions": [{"code": "FAN_BOOST", "fan_pct": 100}, {"code": "REDUCE_LOAD", "load_pct": 80}],
              "approvedBy": "OP-17", "expiresAt": "2026-09-23T10:16:05Z"}
    assert schemas.validate_action_cmd(sample) == []


def test_actions_to_writes_maps_codes():
    writes = schemas.actions_to_writes([{"code": "FAN_BOOST", "fan_pct": 100}, {"code": "REDUCE_LOAD", "load_pct": 80}])
    assert writes == [{"res": "FanSpeedSP", "v": 100}, {"res": "LoadSP", "v": 80}]


def test_decode_value_tolerates_non_json_and_non_objects():
    from hydcommon import kafka
    assert kafka.decode_value(b'{"a": 1}') == {"a": 1}
    assert kafka.decode_value(b"not json") == {"_raw": "not json"}
    assert kafka.decode_value(b"[1, 2]") == {"_raw": "[1, 2]"}
    assert kafka.decode_value(b"\xff\xfe") == {"_raw": "\ufffd\ufffd"}


def test_validate_action_cmd_rejects_raw_wrapper():
    assert schemas.validate_action_cmd({"_raw": "garbage"})
