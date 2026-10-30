"""정의 등록 검사(procsvc/definition_registry.py) — 실행 엔진이 못 다루는 모양을 등록 전에 거절한다."""
import json
from pathlib import Path

import pytest

from procsvc.definition_registry import validate_definition

DEFINITIONS = Path(__file__).resolve().parents[3] / 'it' / 'process' / 'definitions'


def _chain(second_gateway_outgoing):
    """승인 → 분기1(approval) → 분기2(recovered) → 끝들. second_gateway_outgoing = 분기2 의 나가는 선들."""
    forms = {'pick': {'fields_json': [{'key': 'approval', 'type': 'text', 'text': '결정'}, {'key': 'recovered', 'type': 'text', 'text': '회복'}]}}
    return {'processDefinitionId': 'chain', 'processDefinitionName': '분기 연쇄', 'version': '1', 'forms': forms,
            'activities': [{'id': 'pick', 'name': '고르기', 'type': 'userTask', 'role': '담당', 'tool': 'formHandler:pick',
                            'outputData': ['approval', 'recovered']}],
            'events': [{'id': 'start', 'type': 'startEvent'}, {'id': 'ok', 'type': 'endEvent'}, {'id': 'no', 'type': 'endEvent'},
                       {'id': 'other', 'type': 'endEvent'}],
            'gateways': [{'id': 'g1', 'type': 'exclusiveGateway'}, {'id': 'g2', 'type': 'exclusiveGateway', 'name': '회복 분기'}],
            'roles': [{'name': '담당', 'endpoint': 'user:kim-op'}],
            'data': [{'name': 'approval', 'type': 'text'}, {'name': 'recovered', 'type': 'text'}],
            'sequences': [{'id': 's0', 'source': 'start', 'target': 'pick'}, {'id': 's1', 'source': 'pick', 'target': 'g1'},
                          {'id': 's2', 'source': 'g1', 'target': 'g2', 'condition': "approval == '승인'"},
                          {'id': 's3', 'source': 'g1', 'target': 'no'}, *second_gateway_outgoing]}


def test_분기에서_바로_이어지는_분기에_그_밖의_경우가_없으면_등록하지_않는다():
    """#16: 앞 작업의 진행 판정은 분기 한 단계만 본다 — 두 번째 분기의 조건이 모두 거짓이면 흐름이 오류 없이 사라졌다."""
    raw = _chain([{'id': 's4', 'source': 'g2', 'target': 'ok', 'condition': "recovered == 'yes'"},
                  {'id': 's5', 'source': 'g2', 'target': 'other', 'condition': "recovered == 'no'"}])
    with pytest.raises(ValueError, match='회복 분기.*그 밖의 경우'):
        validate_definition(raw)


@pytest.mark.parametrize('default_flow', [
    {'id': 's5', 'source': 'g2', 'target': 'other'},                                                     # 조건 없는 선
    {'id': 's5', 'source': 'g2', 'target': 'other', 'condition': "recovered == 'no'", 'properties': {'default': True}},
])
def test_이어지는_분기에_기본_선이_있으면_등록한다(default_flow):
    raw = _chain([{'id': 's4', 'source': 'g2', 'target': 'ok', 'condition': "recovered == 'yes'"}, default_flow])
    assert validate_definition(raw).id == 'chain'


@pytest.mark.parametrize('name', ['anomaly_response_v22.json', 'alert_triage_v1.json', 'ask_agent_v1.json', 'shift_handover_v1.json'])
def test_제공_정의는_모두_등록_검사를_통과한다(name):
    raw = json.loads((DEFINITIONS / name).read_text(encoding='utf8'))
    assert validate_definition(raw).id == raw['processDefinitionId']
