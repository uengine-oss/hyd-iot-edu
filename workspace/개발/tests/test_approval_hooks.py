"""승인 기록 ↔ 판단 원문 다리(procsvc/approval_hooks.py) — 승인 거절 문장, 검토한 조치값 = 실행 조치값, 실행 기록, 학생 문장."""
import re
from types import SimpleNamespace

import pytest

from procsvc import approval_hooks as ah

LATIN = re.compile(r'[A-Za-z]{4,} [a-z]{2,} [A-Za-z]{3,}')


@pytest.mark.parametrize('state, reason, words', [
    ('RESOLVED_WITHOUT_ACTION', None, ['조치 전에 이미 풀려', '조치 전 해소']),
    ('REJECTED_BY_OPERATOR', '현장 확인', ['이미 끝나', '담당자 반려', '사유 현장 확인', '새 판단']),
    ('ESCALATED', 'ACK_TIMEOUT', ['이미 끝나', '책임자 확인', '응답(ACK)이', '새 판단']),
    ('AWAITING_ACK', None, ['승인 대기 상태가 아니라', '진행 중인 조치가 끝난 뒤']),
], ids=['조치 전 해소', '거절로 끝남', '에스컬레이션', '명령 진행 중'])
def test_승인_대기가_아닌_사건의_승인_거절은_무엇이_왜_다음에_무엇을_말한다(state, reason, words):
    text = ah.approval_refusal(state, reason)
    assert all(w in text for w in words) and not LATIN.search(text), text


ACTION = {'kind': 'command', 'code': 'FAN_SET', 'param': 'fan_pct', 'value': 100}


@pytest.mark.parametrize('commands, ok', [([{'code': 'FAN_SET', 'fan_pct': 100}], True), ([{'code': 'FAN_SET', 'fan_pct': 80}], False), ([], False)],
                         ids=['검토한 값 그대로', '값을 바꿈', '명령 없음'])
def test_승인은_검토한_카드가_보인_조치값만_실행한다(commands, ok):
    option = {'actions': [ACTION, {'kind': 'transaction', 'code': 'WO_CREATE'}]}
    if ok:
        ah.require_reviewed_commands(option, commands)
    else:
        with pytest.raises(ValueError, match='검토한 조치 후보와 실행 조치값이 다릅니다'):
            ah.require_reviewed_commands(option, commands)


def _decision():
    return {'id': 'dec-1', 'chosen': 'opt', 'options': [{'id': 'opt', 'actions': [{'kind': 'transaction', 'code': 'WO_CREATE'},
                                                                                 {'kind': 'transaction', 'code': 'PR_CREATE'}]}]}


def test_실행_기록은_조치마다_마지막_결과를_남기고_판단_상태를_정한다():
    d = _decision()
    ah.record_execution(d, {'skill': 'opt', 'code': 'WO_CREATE', 'ok': True, 'ref': 'WO-1'})
    assert d['state'] == 'APPROVED', '조치 하나가 남았다'
    ah.record_execution(d, {'skill': 'opt', 'code': 'PR_CREATE', 'ok': True, 'ref': 'PR-1'})
    assert d['state'] == 'EXECUTED'
    ah.record_execution(d, {'skill': 'opt', 'code': 'WO_CREATE', 'ok': True, 'ref': 'WO-1'})
    assert len(d['executions']) == 2, '같은 결과를 다시 적어도 한 줄'


def test_같은_조치를_업무_시스템이_다른_번호로_두_번_처리하면_학생_문장으로_멈춘다():
    """P4-22: 전에는 영문 사유(same approved action returned …)가 「내부 오류(ValueError)」로 보였다."""
    d = _decision()
    ah.record_execution(d, {'skill': 'opt', 'code': 'WO_CREATE', 'ok': True, 'ref': 'WO-1'})
    with pytest.raises(ValueError, match='서로 다른 기록 번호로 두 번') as caught:
        ah.record_execution(d, {'skill': 'opt', 'code': 'WO_CREATE', 'ok': True, 'ref': 'WO-2'})
    assert not LATIN.search(str(caught.value))


def test_실패한_조치가_있으면_판단은_일부_실행이다():
    d = _decision()
    ah.record_execution(d, {'skill': 'opt', 'code': 'WO_CREATE', 'ok': False, 'error': '정비 창 없음'})
    assert d['state'] == 'PARTIAL' and d['executions'][0]['detail'] == '정비 창 없음'


@pytest.mark.parametrize('book, error', [
    ({}, '판단 기록\\(dec-1\\)을 찾을 수 없습니다'),
    ({'dec-1': {'state': 'APPROVED', 'options': []}}, '이미 승인됐습니다 — 반려할 수 없습니다'),
    ({'dec-1': {'state': 'PENDING_APPROVAL', 'options': [{'id': 'o', 'approver': {'id': 'role:plant-mgr', 'level': 9}}],
                'roles': {'role:operator': {'level': 1}, 'role:plant-mgr': {'level': 9}}}}, '반려 권한 없음'),
], ids=['판단 없음', '이미 승인됨', '승인 역할 아님'])
def test_조치_카드_거절은_판단이_승인_대기이고_그_역할일_때만_받는다(book, error):
    delivery = ah.DecisionDelivery(SimpleNamespace(book=book))
    with pytest.raises((ValueError, PermissionError), match=error) as caught:
        delivery.check_rejection('dec-1', 'role:operator')
    assert not LATIN.search(str(caught.value)), str(caught.value)
