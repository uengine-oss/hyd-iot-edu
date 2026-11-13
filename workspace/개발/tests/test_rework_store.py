"""다시 수행 영수증 저장소(procsvc/rework_store.py) — 새 차수의 요청 · 결과를 그 처리 건에만 넣고 차수 순으로 읽는다(실제 DB)."""
import uuid

import pytest

from conftest import definition_version

START = {'asset': 'HYD-01', 'shift_label': '야간 → 주간', 'as_of': '2026-10-30T06:00:00+09:00', 'work_notes': '메모'}


def _pid(world):
    return world.rt.start_definition('shift_handover', definition_version('shift_handover_v1.json'), 'handover:' + uuid.uuid4().hex, values=dict(START))['proc_inst_id']


def _receipt(pid, generation, **changes):
    return dict({'tenant_id': 'hyd', 'proc_inst_id': pid, 'request_id': str(uuid.uuid4()), 'generation': generation,
                 'request': {'workitem_id': 'w', 'by': 'user:kim-op'}, 'result': {'generation': generation}}, **changes)


def test_다시_수행_영수증은_요청_id로_읽히고_목록은_차수_순이다(world):
    pid = _pid(world)
    second, first = _receipt(pid, 2), _receipt(pid, 1)
    for r in (second, first):
        world.rt.repo.insert_rework(r)
    got = world.rt.repo.get_rework('hyd', pid, first['request_id'])
    assert (got['generation'], got['request'], got['result']) == (1, first['request'], first['result'])
    assert [r['generation'] for r in world.rt.repo.list_reworks('hyd', pid)] == [1, 2]


@pytest.mark.parametrize('change', [{'tenant_id': 'other'}, {'proc_inst_id': 'no-such-instance'}], ids=['다른 테넌트', '없는 처리 건'])
def test_소유가_다른_다시_수행_영수증은_넣지_않는다(world, change):
    pid = _pid(world)
    with pytest.raises(ValueError, match='ownership mismatch'):
        world.rt.repo.insert_rework(_receipt(pid, 1, **change))


def test_없는_요청_id는_없음으로_읽힌다(world):
    assert world.rt.repo.get_rework('hyd', _pid(world), str(uuid.uuid4())) is None
