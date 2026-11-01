"""CMMS 작업지시 요청(procsvc/work_orders.py) — 승인한 카드에서 요청을 만들고, 저장한 그 요청만 다시 보내며, 거절은 학생 문장으로."""
import re
from types import SimpleNamespace

import pytest

from procsvc import machine, work_orders as wo

CARD = {'id': 'skill:sop-cool-11', 'sopId': 'SOP-COOL-11', 'name': '팬 최대 운전', 'executable': True,
        'actions': [{'kind': 'command', 'code': 'FAN_SET', 'param': 'fan_pct', 'value': 100}]}
WO_CARD = dict(CARD, id='skill:sop-cool-04', sopId='SOP-COOL-04', name='쿨러 핀 세척',
               actions=[{'kind': 'transaction', 'code': 'WO_CREATE', 'name': '정비 작업지시', 'target': 'sys:cmms', 'value': '야간'}])
LATIN = re.compile(r'[A-Za-z]{4,} [a-z]{3,} [a-z]{3,}')     # 영문 문장(내부 사유)이 학생에게 가지 않는다


@pytest.mark.parametrize('card, value, source', [
    (CARD, '선택한 조치 이후 정비 점검: 팬 최대 운전', 'process-definition-followup'),
    (WO_CARD, '야간', 'approved-action'),
], ids=['명령 카드 뒤 점검', '작업지시 카드'])
def test_작업지시_요청은_승인한_카드의_조치_방법과_값으로_만든다(card, value, source):
    item = wo.request_for_option(card)
    assert (item['skill'], item['sop'], item['code'], item['value'], item['source'], item['system']) == \
        (card['id'], card['sopId'], 'WO_CREATE', value, source, 'sys:cmms')


@pytest.mark.parametrize('card, error', [
    (dict(WO_CARD, actions=WO_CARD['actions'] * 2), '작업지시 동작이 둘 이상'),
    (dict(CARD, sopId=None), '조치 방법\\(SOP\\)이 없어'),
    (dict(WO_CARD, actions=[dict(WO_CARD['actions'][0], target='sys:erp')]), '정비 시스템\\(CMMS\\)으로만'),
    (dict(CARD, source_id='doc:1', actions=[]), '빈 Action을 새 정비 오더'),
], ids=['동작 둘', 'SOP 없음', '대상이 ERP', '원문 절차의 빈 동작'])
def test_작업지시로_낼_수_없는_카드는_학생이_읽는_까닭과_함께_거절한다(card, error):
    """P4-22: 전에는 영문 사유가 학생 화면에서 「내부 오류(ValueError)」가 됐다."""
    with pytest.raises(ValueError, match=error) as caught:
        wo.request_for_option(card)
    assert not LATIN.search(str(caught.value)), str(caught.value)


def _ctx(state, card=CARD):
    inc = machine.Incident(id='inc-1', asset='HYD-01', alert_id='ALT-1', card={'alert': {'pattern': 'COOLER_DEGRADATION'}}, state=state)
    saved = []
    ctx = SimpleNamespace(incidents={'inc-1': inc}, persist=lambda: saved.append(True))
    decision = {'id': 'dec-1', 'asset': 'HYD-01', 'origin': {'incident': 'inc-1'}, 'chosen': card['id'], 'options': [card],
                'approvedBy': 'user:kim-op'}
    return ctx, inc, decision, saved


@pytest.mark.parametrize('state, card, error', [
    ('RESOLVED', CARD, None),
    ('AWAITING_APPROVAL', WO_CARD, None),
    ('AWAITING_APPROVAL', CARD, '회복이 확인됐거나 작업지시만 고른 승인 뒤'),
    ('ESCALATED', CARD, '회복이 확인됐거나'),
], ids=['명령 뒤 회복 확인', '작업지시만 고른 승인', '명령 뒤 회복 전', '에스컬레이션'])
def test_작업지시는_회복_확인_뒤나_작업지시만_고른_승인_뒤에_요청을_저장하고_보낸다(state, card, error):
    ctx, inc, decision, saved = _ctx(state, card)
    item = wo.request_for_option(card)
    if error is None:
        assert wo.prepare(ctx, decision, item) is inc
        assert inc.work_order_request['item'] == item and saved == [True], '부르기 전에 그 요청을 저장한다'
    else:
        with pytest.raises(ValueError, match=error) as caught:
            wo.prepare(ctx, decision, item)
        assert inc.work_order_request is None and not LATIN.search(str(caught.value))


def test_다시_보내는_작업지시가_저장한_요청과_다르면_보내지_않는다():
    ctx, inc, decision, _ = _ctx('RESOLVED')
    wo.prepare(ctx, decision, wo.request_for_option(CARD))
    with pytest.raises(ValueError, match='처음 저장한 요청과 다릅니다'):
        wo.prepare(ctx, decision, dict(wo.request_for_option(CARD), value='다른 값'))


def test_승인한_사람이_없는_판단으로는_작업지시를_내지_않는다():
    ctx, inc, decision, _ = _ctx('RESOLVED')
    decision['approvedBy'] = None
    with pytest.raises(ValueError, match='승인한 사람 기록이 없어'):
        wo.prepare(ctx, decision, wo.request_for_option(CARD))


def test_작업지시_영수증은_사건을_닫고_감사_기록을_남긴다():
    ctx, inc, decision, _ = _ctx('RESOLVED')
    item = wo.request_for_option(CARD)
    wo.prepare(ctx, decision, item)
    audits = []
    ctx.audit = lambda *a, **k: audits.append(a[2])
    wo.confirm(ctx, inc, item, {'ok': True, 'ref': 'WO-1', 'detail': '등록'})
    assert inc.state == 'CLOSED' and inc.work_order['ref'] == 'WO-1' and inc.approved_by == 'user:kim-op' and audits


def test_작업지시_영수증을_저장하지_못하면_사건은_영수증_전_그대로다():
    from copy import deepcopy
    ctx, inc, decision, _ = _ctx('RESOLVED')
    item = wo.request_for_option(CARD)
    wo.prepare(ctx, decision, item)
    before = deepcopy(inc.__dict__)

    def broken():
        raise OSError('저장소 실패')
    ctx.persist = broken
    with pytest.raises(OSError):
        wo.confirm(ctx, inc, item, {'ok': True, 'ref': 'WO-2', 'detail': '등록'})
    assert inc.__dict__ == before
