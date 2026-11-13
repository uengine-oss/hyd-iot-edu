"""다시 수행 허용(procsvc/rework_effects.py) — 사건 전체 효과를 읽고, 효과가 정리되기 전에는 막고, 정리되면 사건을 다시 연다."""
import uuid

from conftest import OPERATOR
from procsvc import rework, rework_effects


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


def test_막힘은_만든_자리에서_문장을_갖는다(world):
    alert, pid, decision = world.start_cooling()
    world.approve(pid, decision, 'skill:sop-cool-11', OPERATOR)
    world.commanded(pid)
    plan = world.rt.preview_rework(pid, world.row(pid, 'T_agent')['id'])
    assert plan['blockers'] and all(b['text'] == rework.BLOCKER_TEXT[b['code']] for b in plan['blockers'])
