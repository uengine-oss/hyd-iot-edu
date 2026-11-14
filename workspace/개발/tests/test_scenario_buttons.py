"""수업 버튼(procsvc/scenario_buttons.py) — [정기 점검] · [재고 보충]의 경보 · 거절, 진행 중 [초기화] 거절, 시나리오 시각 기준점을 붙잡는 처리 건.

실제 업무 DB(enterprise-sim) · 실제 엔진으로 버튼과 같은 함수를 부른다. 처리 건은 에이전트 단계에서 멈춘 채(진행 중) 둔다.
"""
import uuid
from datetime import datetime, timezone

import pytest

from fastapi import HTTPException

from conftest import definition_version
from hydcommon import topics
from procsvc import scenario_buttons as sb

PERSON = {'by': '담당자', 'user_id': 'user:me', 'roles': ['role:purchasing']}
START = {'asset': 'HYD-01', 'shift_label': '야간 → 주간', 'as_of': '2026-10-30T06:00:00+09:00', 'work_notes': '메모'}


def _press(world, key):
    """버튼 누름(초기화 → 검사 · 경보 → 원천 접수)과 같은 길. 돌려줌 = 처리 건 id."""
    world.main._entsim_post(*sb.SCENARIOS[key]['reset'])
    prep = sb.prepare(key, world.instance_mode.enterprise_read, world.rt, world.main._scenario_route, sb.who(PERSON))
    receipt = world.receive(topics.K_ALERTS, prep['alert'])
    assert receipt['status'] == 'HANDLED', receipt
    return receipt['result']['instance']


@pytest.mark.parametrize('body, expected', [
    ({'by': '담당자', 'user_id': 'user:me', 'role': 'role:purchasing'}, PERSON),
    ({'by': '가' * 100, 'roles': ['r'] * 9}, {'by': '가' * 80, 'user_id': None, 'roles': ['r'] * 5}),
], ids=['담당자', '긴 값은 자름'])
def test_누른_사람은_포털이_보낸_담당자_그대로다(body, expected):
    assert sb.who(body) == expected


@pytest.mark.parametrize('body', [None, {}, {'by': '  ', 'user_id': 'user:me'}], ids=['본문 없음', '칸 없음', '빈 칸'])
def test_누른_사람이_비면_자리표를_지어내지_않고_400_으로_거절한다(body):
    """옛 판은 빈 칸을 「나 미선택」으로 채워 경보 근거와 처리 기록에 사람처럼 남겼다."""
    with pytest.raises(HTTPException) as refused:
        sb.who(body)
    assert refused.value.status_code == 400 and '담당자 정보 없이 온 요청' in refused.value.detail


def test_버튼_경보는_업무_감시와_같은_계약이고_누른_사람과_시각을_근거에_싣는다():
    row = {'part_no': 'P-PMP-SEAL', 'available': 1, 'reorder_point': 2, 'need_qty': 6, 'below_since': 'x', 'reserved_for': 'HYD-03'}
    now = datetime(2026, 10, 30, 6, 0, 1, tzinfo=timezone.utc)
    alert = sb.build_alert('C', row, now, PERSON)
    assert alert['alertId'] == 'ERP-SPARE_BELOW_MIN-P-PMP-SEAL-20261030060001' and alert['source'] == 'erp' and alert['state'] == 'RAISE'
    assert alert['evidence']['spare_below_min'] is True and alert['evidence']['requested_user'] == 'user:me'
    assert alert['evidence']['requested_at'] == '2026-10-30T06:00:01+00:00' and alert['asset'] == 'HYD-03'


def test_같은_시나리오_처리_건이_진행_중이면_다시_누름을_거절한다(world):
    _press(world, 'C')
    with pytest.raises(sb.Refused, match='이미 진행 중입니다'):
        sb.refusal('C', world.instance_mode.enterprise_read, world.rt, world.main._scenario_route)


def test_시나리오_처리_건이_진행_중이면_초기화를_거절한다(world):
    """H-10: 초기화는 열린 발주를 닫고 재고를 되돌린다 — 진행 중 처리 건의 기록을 그 처리 건 모르게 바꾸지 않는다."""
    _press(world, 'C')
    with pytest.raises(sb.Refused, match='아직 진행 중이라 초기화하지 않았습니다') as caught:
        sb.reset_refusal(world.rt, 'C')
    assert '조치 카드를 승인하거나 거절해 끝낸 뒤 [초기화]를 누르세요' in str(caught.value), '아직 멈춘 단계가 없는 처리 건'


def test_시나리오_처리_건이_없으면_초기화를_받는다(world):
    assert sb.reset_refusal(world.rt, 'B') is None


def test_교대_인수인계_처리_건은_설비_값이_있어도_시나리오_시각_기준점을_붙잡지_않는다(world):
    """P4-01: 전에는 변수 asset 이 설비 이름이면 모두 붙잡아, 인수 확인을 기다리는 교대 처리 건 하나가 [정기 점검] · [재고 보충]의 기준점 이동을 막았다."""
    pid = world.rt.start_definition('shift_handover', definition_version('shift_handover_v1.json'), 'handover:' + uuid.uuid4().hex, values=dict(START))['proc_inst_id']
    found = sb.reanchor_blockers(world.rt)
    assert pid not in [b['instance'] for b in found['blocked_by'] + found['overdue']]
    assert sb.may_reanchor(world.rt) is True


def test_경보로_연_대응_처리_건이_진행_중이면_기준점을_붙잡는다(world):
    pid = _press(world, 'C')
    found = sb.reanchor_blockers(world.rt)
    assert [b['instance'] for b in found['blocked_by']] == [pid] and found['blocked_by'][0]['why'] == '진행 중'
    assert sb.may_reanchor(world.rt) is False


def test_시나리오_상태는_진행_중_처리_건과_마지막_처리_건을_보인다(world):
    pid = _press(world, 'C')
    status = sb.status(world.instance_mode.enterprise_read, world.rt)
    c = status['scenarios']['C']
    assert c['running']['instance'] == pid and c['last']['instance'] == pid and c['alert'] is True
    assert status['scenarios']['B']['running'] is None


def test_시나리오_상태는_설비_결함_주입이_지원하는_설비와_결함과_단추를_말한다():
    """전수검사 10-G12: 설비 결함 주입은 가상 설비 한 대의 결함 한 종류인데 서버가 그 범위를 내지 않아 화면이 설비 · 결함을 손으로 적었다."""
    status = sb.status(lambda name, params: {'records': []})
    assert status['fault'] == {'asset': 'HYD-01', 'fault': 'cooler_degradation', 'severity': 'moderate',
                               'buttons': {'degrade': '쿨러 열화 주입', 'restore': '쿨러 복구'}}
    said = sb.unknown_act('pump_leakage')
    assert 'HYD-01' in said and '[쿨러 열화 주입](degrade)' in said and '[쿨러 복구](restore)' in said and "'pump_leakage'" in said
