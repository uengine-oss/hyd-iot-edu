"""다시 수행 허용(procsvc/rework_effects.py) — 사건 전체 효과를 읽고, 효과가 정리되기 전에는 막고, 정리되면 사건을 다시 연다."""
import uuid

from conftest import OPERATOR
from procsvc import rework_effects


def _evidence(**incident):
    return {'incident': dict({'id': 'inc-1', 'asset': 'HYD-01'}, **incident), 'decisions': [{'id': 'dec-1'}],
            'enterprise_receipts': {'dec-1': []}}


def test_효과가_없다는_판정은_사건_전체와_모든_판단_원장을_본다():
    assert rework_effects.no_effects(_evidence(), [{'results': []}]) is True
    assert rework_effects.no_effects(_evidence(cmdId='CMD-1'), []) is False
    assert rework_effects.no_effects(dict(_evidence(), enterprise_receipts={}), []) is False, '원장을 읽지 못한 판단이 있으면 없다고 하지 않는다'
    assert rework_effects.no_effects(_evidence(), [{'results': [{'ok': True}]}]) is False


def test_사건이_없는_처리_건과_사건을_못_읽으면_까닭과_함께_멈춘다(world):
    alert, pid, decision = world.start_cooling()
    inst = world.inst(pid)
    world.main.incidents.pop(world.values(pid)['incident'])
    try:
        rework_effects.collect(world.main.instance_context(), inst)
    except ValueError as e:
        assert '사건 원문/설비를 확인할 수 없습니다' in str(e)
    else:
        raise AssertionError('사건을 못 읽었는데 효과 조회가 성공했다')


def test_설비_명령을_확인하면_효과가_정리돼_사건을_다시_열고_새_차수를_요청할_수_있다(world):
    alert, pid, decision = world.start_cooling()
    world.approve(pid, decision, 'skill:sop-cool-11', OPERATOR)
    cmd = world.commanded(pid)
    world.ack('HYD-01', cmd['cmdId'])
    plc = next(e for e in world.rt.effects_view(pid)['effects'] if e['kind'] == 'plc')
    world.rt.review_effects(pid, str(uuid.uuid4()), OPERATOR['by'], OPERATOR['role'], '현장 확인함', [plc['id']])
    plan = world.rt.preview_rework(pid, world.row(pid, 'T_agent')['id'])
    assert plan['reopen_incident'] is True and plan['effects_resolution']['pending'] == []
    assert plan['blockers'] == [], [b['code'] for b in plan['blockers']]


def test_발주가_나간_예비품_구매_처리_건은_발주를_취소한_뒤에야_판단부터_다시_수행하고_사건이_승인_대기로_돌아간다(world):
    """13C-17: 다시 수행의 실제 흐름 판정이 모두 흐름 A(설비 명령 효과)였다 — 업무 영수증 효과(발주)가 남은, 설비 명령이 없는 흐름은 재지 않았다.
    흐름 C: 승인 → 발주(업무 DB 구매요청) → 입고 대기. 그때 판단 단계부터 다시 수행하려 하면 발주라는 효과가 남아 막히고, 발주를 업무 시스템의
    역거래(구매요청 취소)로 되돌리면 막힘이 풀려 새 차수가 열리며, 「승인 — 흐름이 실행 중」이던 사건이 승인 대기로 돌아간다(새 판단 · 승인을 받는다)."""
    import psycopg
    import pytest
    from test_instances import BUYER, ME, _button
    world.main._entsim_post('/erp/spare/reset', {'part_no': 'P-PMP-SEAL'})
    alert, pid = _button(world, 'C', dict(by='담당자', user_id=ME, roles=['role:purchasing']))
    decision = world.agent(pid, 'T_agent')
    world.approve(pid, decision, world.main.book[decision]['recommended'], BUYER)
    world.poll(2)
    inc = world.incident(pid)
    assert world.row(pid, 'T_gr')['status'] == 'SUBMITTED' and inc.state == 'APPROVED_EXECUTING'
    agent = world.row(pid, 'T_agent')

    plan = world.rt.preview_rework(pid, agent['id'])
    codes = [b['code'] for b in plan['blockers']]
    assert 'effects_require_compensation_or_review' in codes and 'incident_not_active_for_rework' not in codes, codes
    with pytest.raises(ValueError, match='다시 수행할 수 없습니다: '):
        world.rt.request_rework(pid, agent['id'], str(uuid.uuid4()), plan['snapshot_token'], BUYER['by'], BUYER['role'], '수량을 다시 판단')
    po = next(e for e in world.rt.effects_view(pid)['effects'] if (e.get('ref') or '').startswith('PR-'))
    assert po['reversible'] is True, po
    with psycopg.connect(world.dsn, autocommit=True) as db:
        assert db.execute('SELECT status FROM ent.purchase_requests WHERE id=%s', (po['ref'],)).fetchone() == ('승인됨 → 발주',)

    receipt = world.rt.compensate_effects(pid, str(uuid.uuid4()), BUYER['by'], BUYER['role'], '발주 취소 — 수량을 다시 판단', [po['id']])
    assert receipt['status'] == 'DELIVERED', receipt
    with psycopg.connect(world.dsn, autocommit=True) as db:
        status = db.execute('SELECT status FROM ent.purchase_requests WHERE id=%s', (po['ref'],)).fetchone()[0]
    assert status != '승인됨 → 발주', status                                                       # 업무 DB 의 발주가 실제로 취소됐다

    plan = world.rt.preview_rework(pid, agent['id'])
    assert plan['blockers'] == [] and plan['effects_resolution']['pending'] == [], plan['blockers']
    result = world.rt.request_rework(pid, agent['id'], str(uuid.uuid4()), plan['snapshot_token'], BUYER['by'], BUYER['role'], '수량을 다시 판단')
    assert result['generation'] == 1
    new = next(w for w in world.rows(pid) if w['id'] == result['start_workitem'])
    assert new['activity_id'] == 'T_agent' and new['supersedes_id'] == agent['id']
    waits = sorted(w['status'] for w in world.rows(pid) if w['activity_id'] == 'T_gr')
    assert waits == ['CANCELLED', 'TODO'], f'옛 차수의 입고 대기는 취소되고 새 차수의 것은 아직 닿지 않은 예정 행이다: {waits}'
    assert world.incident(pid).state == 'AWAITING_APPROVAL', '새 판단 · 승인을 받도록 사건이 승인 대기로 돌아간다'

