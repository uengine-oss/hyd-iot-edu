"""효과 영수증 저장소(procsvc/effect_store.py) — 보상 · 사람 확인 영수증은 그 처리 건에만 넣고 요청 id 로 다시 읽는다(실제 DB)."""
import uuid

import pytest

from conftest import definition_version

START = {'asset': 'HYD-01', 'shift_label': '야간 → 주간', 'as_of': '2026-10-30T06:00:00+09:00', 'work_notes': '메모'}


def _pid(world):
    return world.rt.start_definition('shift_handover', definition_version('shift_handover_v1.json'), 'handover:' + uuid.uuid4().hex, values=dict(START))['proc_inst_id']


def _receipt(pid, **changes):
    return dict({'tenant_id': 'hyd', 'proc_inst_id': pid, 'request_id': str(uuid.uuid4()), 'kind': 'review', 'status': 'RECORDED',
                 'request': {'kind': 'review', 'by': 'user:kim-op'}, 'effects': [{'id': 'plc:CMD-1'}], 'results': [], 'error': None,
                 'history': [{'status': 'RECORDED'}]}, **changes)


def test_영수증은_넣은_그대로_요청_id로_다시_읽히고_목록은_넣은_순서다(world):
    pid = _pid(world)
    first, second = _receipt(pid), _receipt(pid, kind='compensation', status='DELIVERED')
    for r in (first, second):
        world.rt.repo.insert_effect_receipt(r)
    got = world.rt.repo.get_effect_receipt('hyd', pid, first['request_id'])
    assert {k: got[k] for k in ('kind', 'status', 'request', 'effects')} == {k: first[k] for k in ('kind', 'status', 'request', 'effects')}
    assert [r['request_id'] for r in world.rt.repo.list_effect_receipts('hyd', pid)] == [first['request_id'], second['request_id']]


@pytest.mark.parametrize('change', [{'tenant_id': 'other'}, {'proc_inst_id': 'no-such-instance'}], ids=['다른 테넌트', '없는 처리 건'])
def test_소유가_다른_영수증은_넣지_않는다(world, change):
    pid = _pid(world)
    with pytest.raises(ValueError, match='ownership mismatch'):
        world.rt.repo.insert_effect_receipt(_receipt(pid, **change))


def test_영수증_갱신은_결과_칸만_바꾸고_없는_영수증이면_실패한다(world):
    pid = _pid(world)
    r = _receipt(pid, kind='compensation', status='PENDING')
    world.rt.repo.insert_effect_receipt(r)
    world.rt.repo.update_effect_receipt(dict(r, status='FAILED', error='역거래 거절', results=[{'effect': 'tx:1', 'ok': False}]))
    got = world.rt.repo.get_effect_receipt('hyd', pid, r['request_id'])
    assert (got['status'], got['error'], got['request']) == ('FAILED', '역거래 거절', r['request'])
    with pytest.raises(KeyError):
        world.rt.repo.update_effect_receipt(dict(r, request_id=str(uuid.uuid4())))
