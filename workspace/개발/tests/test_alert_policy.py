"""경보 정책(procsvc/alert_policy.py) — 흐름 정의의 alertPolicy 하나가 경보를 받을지 · 회복 기준 · 사람 검토 경로를 정한다."""
import json
from copy import deepcopy

import pytest

from conftest import DEFINITIONS
from procsvc import alert_policy, engine

ANOMALY = json.loads((DEFINITIONS / 'anomaly_response_v22.json').read_text(encoding='utf-8'))
TRIAGE = json.loads((DEFINITIONS / 'alert_triage_v1.json').read_text(encoding='utf-8'))
POLICY = {'patterns': {'PUMP_LEAKAGE': {'tag': 'PS1', 'op': '>=', 'limit': 165.0, 'requireClear': True}},
          'unsupported': {'definition': 'alert_triage', 'version': '1.0'}}


def _with(**changes):
    policy = deepcopy(POLICY)
    for path, value in changes.items():
        if path == 'unsupported':
            policy['unsupported'] = value
        else:
            policy['patterns']['PUMP_LEAKAGE'][path] = value
    return {'alertPolicy': policy}


@pytest.mark.parametrize('raw, error', [
    ({}, None),                                                   # 정책 없는 정의(교대 · 질문)는 경보 정책 검사 대상이 아니다
    ({'alertPolicy': POLICY}, None),
    ({'alertPolicy': {'patterns': {}}}, '명시 경보/회복 기준'),
    (_with(op='>'), '지원 비교 연산'),
    (_with(tag=''), '지원 비교 연산'),
    (_with(limit=float('nan')), '유한 임계값'),
    (_with(limit=True), '유한 임계값'),
    (_with(requireClear=False), 'requireClear'),
    (_with(unsupported={'definition': 'alert_triage'}), '사람 검토 정의/버전'),
], ids=['정책 없음', '정상', '패턴 없음', '모르는 연산', '태그 없음', '한계 NaN', '한계가 참거짓', '해제 필요 아님', '사람 검토 판본 없음'])
def test_경보_정책은_회복_기준과_사람_검토_경로를_빠짐없이_적어야_등록된다(raw, error):
    if error is None:
        alert_policy.validate(raw)
    else:
        with pytest.raises(ValueError, match=error):
            alert_policy.validate(raw)


@pytest.mark.parametrize('pattern, route, criterion, target', [
    ('PUMP_LEAKAGE', 'response', ('PS1', '>=', 165.0), {'definition': 'anomaly_response', 'version': ANOMALY['version']}),
    ('UNKNOWN_PATTERN', 'triage', None, ANOMALY['alertPolicy']['unsupported']),
    (None, 'triage', None, ANOMALY['alertPolicy']['unsupported']),
], ids=['정책에 있는 패턴', '정책에 없는 패턴', '패턴 없음'])
def test_기준_흐름은_정책에_있는_패턴만_대응하고_나머지는_사람_검토로_보낸다(pattern, route, criterion, target):
    got = alert_policy.for_definition(ANOMALY, pattern)
    assert (got['route'], got['criterion'], got['target']) == (route, criterion, target)
    if pattern == 'PUMP_LEAKAGE':
        assert criterion == tuple(ANOMALY['alertPolicy']['patterns'][pattern][k] for k in ('tag', 'op', 'limit'))


def test_경보_정책이_없는_정의는_코드_상수_기준으로_대신하지_않고_경보를_거절한다():
    """P5-14 · P1-20: 전에는 정책 없는 정의에 코드 상수(definition.RECOVERY)의 회복 기준과 alert_triage 1.0 을 몰래 붙였다."""
    raw = {k: v for k, v in ANOMALY.items() if k != 'alertPolicy'}
    with pytest.raises(ValueError, match='경보 정책\\(alertPolicy\\)이 없어 경보를 받을 수 없습니다'):
        alert_policy.for_definition(raw, 'PUMP_LEAKAGE')


@pytest.mark.parametrize('raw, ok', [(TRIAGE, True), (ANOMALY, False)], ids=['사람 검토 정의', '조치 · 에이전트가 있는 기준 흐름'])
def test_미지원_경보_경로는_사람_단계만_있는_정의여야_한다(raw, ok):
    defn = engine.Definition.from_dict(raw)
    if ok:
        alert_policy.require_triage(defn)
    else:
        with pytest.raises(ValueError, match='사람 검토여야 합니다'):
            alert_policy.require_triage(defn)
