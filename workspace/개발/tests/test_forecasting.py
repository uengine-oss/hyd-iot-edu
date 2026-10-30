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


@pytest.mark.parametrize('waited_s, stale', [(60, False), (5 * 60, False), (29 * 60, False), (31 * 60, True)])
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
