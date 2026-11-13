"""조치 카드 판단(procsvc/decisions.py) — 승인 대기 → 승인 · 거절, 역할 등급, 한 작업 · 세대 한 판단."""
import pytest

from procsvc import decisions

ROLES = {'role:operator': {'name': '운전원', 'level': 1}, 'role:supervisor': {'name': '반장', 'level': 2},
         'role:maint-mgr': {'name': '설비보전팀장', 'level': 3}}


def _option(oid, approver='role:operator', feasible=True, **extra):
    return {'id': oid, 'name': f'카드 {oid}', 'sopId': f'sop:{oid}', 'feasible': feasible, 'evaluation_mode': 'execution',
            'execution_checked': True, 'approver': {'id': approver, 'name': ROLES[approver]['name'], 'level': ROLES[approver]['level']},
            'actions': [{'code': 'FAN_SET', 'kind': 'command', 'param': 'fan_pct', 'value': 100, 'target': 'sys:scada'},
                        {'code': 'WO_CREATE', 'kind': 'transaction', 'target': 'sys:cmms'}], **extra}


def _decision(**extra):
    return decisions.new({'id': 'D-1', 'asset': 'HYD-01', 'recommended': 'a', 'roles': ROLES, 'evaluation_mode': 'execution',
                          'execution_checked': True,
                          'options': [_option('a'), _option('b', approver='role:supervisor'), _option('c', feasible=False,
                                      violations=[{'annotation': '재고 부족'}])], **extra})


@pytest.mark.parametrize('option, role, ok', [
    ('a', 'role:operator', True), ('a', 'role:supervisor', True),        # 그 역할 또는 더 높은 역할
    ('b', 'role:operator', False), ('b', 'role:maint-mgr', True),
])
def test_카드의_승인_역할_또는_더_높은_역할만_승인한다(option, role, ok):
    d = _decision()
    if ok:
        plan = decisions.approve(d, option, 'user:x', role, '확인')
        assert d['state'] == 'APPROVED' and d['chosen'] == option and d['override'] is (option != 'a')
        assert [i['code'] for i in plan['ot']] == ['FAN_SET'] and [i['code'] for i in plan['enterprise']] == ['WO_CREATE']
    else:
        with pytest.raises(PermissionError, match='반장 이상'):
            decisions.approve(d, option, 'user:x', role)
        assert d['state'] == 'PENDING_APPROVAL'


def test_규정상_고를_수_없는_카드는_그_까닭으로_거절한다():
    with pytest.raises(ValueError, match='재고 부족'):
        decisions.approve(_decision(), 'c', 'user:x', 'role:maint-mgr')


@pytest.mark.parametrize('act', [lambda d: decisions.approve(d, 'a', 'user:x', 'role:operator'),
                                 lambda d: decisions.reject(d, 'user:x', '다시')])
def test_이미_처리한_판단은_다시_승인_거절하지_않고_쉬운_말로_말한다(act):
    """P1-10: 전에는 「decision is APPROVED」 같은 영문이 학생에게 갔다."""
    d = _decision()
    decisions.reject(d, 'user:x', '현장 확인')
    with pytest.raises(ValueError, match='이미 거절됐습니다'):
        act(d)


def test_승인_없이_처리_건이_끝나면_판단도_끝나고_그_뒤_승인은_쉬운_말로_거절한다():
    d = _decision()
    decisions.close_unapproved(d, '조치 전 해소')
    assert (d['state'], d['history'][-1]['state'], d['history'][-1]['reason']) == ('CLOSED_UNAPPROVED', 'CLOSED_UNAPPROVED', '조치 전 해소')
    with pytest.raises(ValueError, match='승인 없이 처리 건이 끝났습니다'):
        decisions.approve(d, 'a', 'user:x', 'role:operator')


def test_없는_카드를_고르면_판단과_카드_id_를_말한다():
    with pytest.raises(ValueError, match='D-1.*zz'):
        decisions.approve(_decision(), 'zz', 'user:x', 'role:operator')


def test_거절은_실행_준비와_상관없이_승인할_역할이면_한다():
    """모든 카드가 제외된 판단도 승인할 역할이 닫을 수 있다(2026-10-23 B 가 승인 단계에서 멈춘 것)."""
    d = _decision()
    assert decisions.holds_approver_role(d, d['options'][2], 'role:operator')
    assert not decisions.may_approve(d, dict(d['options'][0], execution_checked=False), 'role:operator')


@pytest.mark.parametrize('origin, scope', [
    ({'process_scope': {'tenant': 'hyd', 'instance': 'p', 'workitem': 'w', 'generation': 1, 'version': '1'}}, ('hyd', 'p', 'w', 1, '1')),
    ({'process_scope': {'tenant': 'hyd'}}, None),          # 작업이 없으면 범위가 아니다
    ({}, None),
])
def test_한_작업_세대는_판단_하나를_가진다(origin, scope):
    assert decisions.submission_scope({'origin': origin}) == scope


@pytest.mark.parametrize('option, roles', [
    ('a', ['role:operator', 'role:supervisor', 'role:maint-mgr']),       # 운전원 안 — 그 역할과 더 높은 역할 모두
    ('b', ['role:supervisor', 'role:maint-mgr']),                       # 반장 안 — 운전원은 빠진다
])
def test_안마다_승인할_수_있는_역할은_역할_등급_규칙으로_서버가_정한다(option, roles):
    """W1-11 · W1-25: 전에는 화면이 같은 규칙의 사본(instances.js signs)으로 단추를 껐다 — 서버가 이 목록을 실어 사본을 지운다."""
    d = _decision()
    opt = next(o for o in d['options'] if o['id'] == option)
    assert decisions.approver_roles(d, opt) == roles
    assert all(decisions.holds_approver_role(d, opt, r) == (r in roles) for r in ROLES)
