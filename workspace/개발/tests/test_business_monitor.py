"""업무 경보 계약(procsvc/business_monitor.py) — 수업 버튼 B · C 가 내는 경보의 근거 값과 출처, 흐름 가져오기에 보탤 경보 패턴."""
import pytest

from procsvc import alert_policy, business_monitor as bm

SPARE_ROW = {'part_no': 'P-PMP-SEAL', 'name': '펌프 축 씰 키트', 'on_hand': 3, 'reserved': 2, 'available': 1, 'on_order': 0,
             'reorder_point': 2, 'target_stock': 7, 'need_qty': 6, 'below_since': '2026-10-30T06:00:00+00:00', 'reserved_for': 'HYD-03',
             'unit_price': 55}
PM_ROW = {'asset': 'HYD-02', 'cycle': 7, 'pm_since_h': 1950, 'pm_interval_h': 2000, 'pm_due_in_h': 50, 'night_window_id': 'MW-N-1',
          'hours_since_pm': 1950, 'pm_crew_available': True, 'internal_note': '판단에 쓰지 않는 칸'}


@pytest.mark.parametrize('pattern, row, flag, dropped', [
    ('SPARE_BELOW_MIN', SPARE_ROW, 'spare_below_min', 'unit_price'),
    ('PM_DUE', PM_ROW, 'pm_due', 'internal_note'),
], ids=['재고 C', '정기 정비 B'])
def test_업무_경보의_근거는_규칙이_정한_칸만_싣고_이탈_표시를_더한다(pattern, row, flag, dropped):
    rule = next(r for r in bm.RULES if r.pattern == pattern)
    evidence = rule.evidence(row)
    assert evidence[flag] is True and dropped not in evidence
    assert {k: v for k, v in evidence.items() if k != flag} == {k: row[k] for k in evidence if k != flag}


@pytest.mark.parametrize('alert, expected', [
    ({'pattern': 'SPARE_BELOW_MIN', 'source': 'erp'}, True),
    ({'pattern': 'PM_DUE', 'source': 'cmms'}, True),
    ({'pattern': 'PM_DUE', 'source': 'erp'}, False),
    ({'pattern': 'COOLER_DEGRADATION', 'source': 'detector'}, False),
    (None, False),
], ids=['ERP 재고', 'CMMS 정비', '출처가 다름', '센서 경보', '경보 아님'])
def test_업무_경보는_패턴과_그_패턴의_업무_시스템_출처가_맞아야_한다(alert, expected):
    assert bm.is_business_alert(alert) is expected


def test_흐름_가져오기에_보탤_업무_경보_패턴은_경보_정책_계약을_만족한다():
    patterns = bm.policy_patterns()
    assert set(patterns) == {'SPARE_BELOW_MIN', 'PM_DUE'}
    alert_policy.validate({'alertPolicy': {'patterns': patterns, 'unsupported': {'definition': 'alert_triage', 'version': '1.0'}}})
    patterns['PM_DUE']['limit'] = 99
    assert bm.PATTERNS['PM_DUE']['policy']['limit'] == 1.0, '돌려준 것은 사본이다'
