"""승인 카드의 예측 신선도(it/agent/agentsvc/forecasting.py consent_changes) — 사람이 읽는 시간은 벽시계, 설비 변화는 허용폭."""
from datetime import datetime, timedelta, timezone

import pytest

from agentsvc import forecasting

T0 = datetime(2026, 10, 30, 9, 0, tzinfo=timezone.utc)


def _context(at, ts1=50.0):
    return {'source_t': at.isoformat(), 'model_id': 'lumped-v1', 'model_revision': '3', 'scope': 'HYD', 'binding': 'HYD-01',
            'horizon_s': 900, 'parameters': {}, 'actions': [{'code': 'FAN_SET', 'fan_pct': 100}], 'assumptions': {},
            'review_policy': forecasting.REVIEW_POLICY, 'inputs': {'ts1': ts1, 'fan_pct': 60},
            'values': {'ts1': ts1, 'ts1_peak': ts1 + 1, 'vs1': 0.5, 'vs1_peak': 0.5}}


@pytest.mark.parametrize('waited_s, stale', [(60, False), (5 * 60, False), (29 * 60, False), (30 * 60, False), (30 * 60 + 1, True),
                                             (31 * 60, True)], ids=['1분', '5분', '29분', '30분 정각(경계 — 아직 신선)', '30분 1초', '31분'])
def test_검토한_카드의_신선도는_벽시계로_30분이다(waited_s, stale):
    """#2: 전에는 1800 시뮬레이션 초 = 20배속 90초라, 학생이 카드를 1분 남짓 읽으면 승인이 「오래된 예측」으로 거절됐다."""
    reasons = forecasting.consent_changes(_context(T0), _context(T0 + timedelta(seconds=waited_s)), time_scale=20)
    assert any('새 카드 검토' in r and '분 전 예측' in r for r in reasons) is stale


def test_신선도는_사람이_동의한_시각까지만_잰다():
    reasons = forecasting.consent_changes(_context(T0), _context(T0 + timedelta(minutes=45)), time_scale=20,
                                          consented_at=(T0 + timedelta(minutes=10)).isoformat())
    assert not any('분 전 예측' in r for r in reasons)


@pytest.mark.parametrize('waited_s, ts1_rise, refused', [
    (60, 0.4, False),          # 허용폭 0.5 ℃ 안
    (60, 25.0, True),          # 1분(벽시계) = 20 시뮬레이션 분 — 허용 0.5 + 1.0 ℃/분 × 20 = 20.5 ℃ 를 넘음
    (30, 5.0, False),          # 30초 = 10 시뮬레이션 분 — 허용 10.5 ℃ 안
])
def test_검토_뒤_설비_변화는_시뮬레이션_시간에_비례한_허용폭으로_지킨다(waited_s, ts1_rise, refused):
    reasons = forecasting.consent_changes(_context(T0), _context(T0 + timedelta(seconds=waited_s), ts1=50.0 + ts1_rise), time_scale=20)
    assert any('예측 유온 악화' in r for r in reasons) is refused


def _snapshot(state='RUN'):
    return {'asset': 'HYD-01', 't': T0.isoformat(), 'state': state, 'pump': 'A', 'forecast_model': 'hydraulic-lumped-simulator-v1',
            'disturbance_ramps': [], 'ts1': 58.0, 't_amb': 28.0, 'fan_pct': 60.0, 'load_pct': 90.0, 'cooler_health': 0.43, 'leak': 0.0,
            'bearing_wear': 0.0}


WORK_ORDER_ONLY = {'actions': [{'code': 'WO_CREATE', 'kind': 'transaction', 'value': 'SOP-COOL-14'}]}


@pytest.mark.parametrize('state, stops_now, added', [('RUN', True, True), ('RUN', False, False), ('STOP', True, False), ('TRIP', True, False)],
                         ids=['운전 중 + 지금 시행 → 정지', '운전 중 + 다음 창에 시행 → 그대로', '이미 정지 → 더하지 않음', '트립 → 더하지 않음'])
def test_지금_작업지시를_시행하는_카드는_운전_중인_설비를_정지한_것으로_예측한다(state, stops_now, added):
    """G1-05: 「지금 정지하고 세척」 카드가 계속 뜨겁게 도는 설비로 예측돼(평형 62 ℃) 예측 · 품질 감점을 받았다."""
    actions = forecasting.plant_actions(WORK_ORDER_ONLY, _snapshot(state), stops_now)
    assert [a['code'] for a in actions] == (['WO_CREATE', 'STOP'] if added else ['WO_CREATE'])
    assert WORK_ORDER_ONLY['actions'] == [{'code': 'WO_CREATE', 'kind': 'transaction', 'value': 'SOP-COOL-14'}]     # 카드 원본은 그대로


def test_정지로_예측한_카드의_평형_유온은_계속_운전한_것보다_낮다():
    from hydcommon.forecast import predict
    running = predict(_snapshot(), forecasting.plant_actions(WORK_ORDER_ONLY, _snapshot(), False), 900)['values']['ts1_steady']
    stopped = predict(_snapshot(), forecasting.plant_actions(WORK_ORDER_ONLY, _snapshot(), True), 900)['values']['ts1_steady']
    assert stopped < 55 <= running
