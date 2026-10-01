from plantsim import edge
import json
from unittest.mock import Mock


def test_command_source_is_derived_from_topic_not_payload():
    # a payload claiming source FUXA on cmd/auto must still be treated as HITL (only the gateway publishes cmd/auto)
    assert edge.source_for("cmd/auto", {"source": "FUXA", "cmdId": "X"}) == "HITL"
    assert edge.source_for("cmd/manual", {"source": "HITL"}) == "FUXA"
    assert edge.source_for("cmd/manual", {"FanSpeedSP": 80}) == "FUXA"


def test_successful_ack_clears_fuxa_rejection_without_changing_reason_contract():
    plant = edge.Plant()
    service = object.__new__(edge.Edge)
    service.plant, service.client = plant, Mock()
    ctrl = plant.units['HYD-01'].ctrl
    ctrl.last_result, ctrl.last_reason = 'REJECTED', 'MODE_MISMATCH'
    service._publish_status('HYD-01')
    rejected = json.loads(service.client.publish.call_args.args[1])
    assert rejected['reason_display'] == 'MODE_MISMATCH'
    assert rejected['reason_text'] == '운전 모드 확인 필요'
    assert rejected['result_text'] == '거절'
    ctrl.last_result, ctrl.last_reason = 'DONE', None
    service._publish_status('HYD-01')
    done = json.loads(service.client.publish.call_args.args[1])
    assert done['result'] == 'DONE' and done['reason'] is None
    assert done['reason_display'] == '–'
    assert done['reason_text'] == '–' and done['result_text'] == '완료'
    assert plant.status('HYD-01')['reason'] is None
