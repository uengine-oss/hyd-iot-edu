"""승인 전달 대기열 저장소(procsvc/approval_store.py) — 처리 건 단계 하나에 승인 의도 하나, 소유 확인, 전달 상태만 바뀐다(실제 DB)."""
import uuid

import pytest

from conftest import definition_version

START = {'asset': 'HYD-01', 'shift_label': '야간 → 주간', 'as_of': '2026-10-30T06:00:00+09:00', 'work_notes': '쿨러 정비 완료라고 전달받음'}


def _case(world):
    inst = world.rt.start_definition('shift_handover', definition_version('shift_handover_v1.json'), 'handover:' + uuid.uuid4().hex, values=dict(START))
    return inst['proc_inst_id'], world.rows(inst['proc_inst_id'])[0]


def _row(pid, wid, **changes):
    return dict({'todo_id': wid, 'proc_inst_id': pid, 'tenant_id': 'hyd', 'decision_id': 'dec-' + uuid.uuid4().hex[:8],
                 'payload': {'option': 'x', 'by': 'user:kim-op'}, 'status': 'PENDING', 'attempts': 0, 'results': [], 'error': None,
                 'history': [{'status': 'PENDING'}]}, **changes)


def test_승인_의도는_그_처리_건의_단계에만_하나_넣고_그대로_읽힌다(world):
    pid, wi = _case(world)
    repo = world.rt.repo
    repo.insert_approval(_row(pid, wi['id']))
    got = repo.get_approval(wi['id'], 'hyd')
    assert (got['status'], got['payload'], got['attempts']) == ('PENDING', {'option': 'x', 'by': 'user:kim-op'}, 0)
    assert [a['todo_id'] for a in repo.list_approvals(pid, 'hyd')] == [wi['id']]


@pytest.mark.parametrize('change, why', [({'tenant_id': 'other'}, '다른 테넌트'), ({'proc_inst_id': 'no-such-instance'}, '다른 처리 건')],
                         ids=['다른 테넌트', '다른 처리 건'])
def test_소유가_다른_승인_의도는_넣지_않고_실패한다(world, change, why):
    pid, wi = _case(world)
    with pytest.raises(ValueError, match='ownership mismatch'):
        world.rt.repo.insert_approval(_row(pid, wi['id'], **change))
    assert world.rt.repo.get_approval(wi['id'], 'hyd') is None, why


def test_같은_단계에_두_번째_승인_의도는_넣지_않는다(world):
    pid, wi = _case(world)
    world.rt.repo.insert_approval(_row(pid, wi['id']))
    with pytest.raises(ValueError, match='already has an approval intent'):
        world.rt.repo.insert_approval(_row(pid, wi['id']))


def test_전달_상태_갱신은_있는_행만_바꾸고_없으면_실패한다(world):
    pid, wi = _case(world)
    repo = world.rt.repo
    repo.insert_approval(_row(pid, wi['id']))
    row = repo.get_approval(wi['id'], 'hyd')
    row.update(status='FAILED', attempts=1, error='전달 실패', history=row['history'] + [{'status': 'FAILED'}])
    repo.update_approval(row)
    assert repo.get_approval(wi['id'], 'hyd')['status'] == 'FAILED'
    with pytest.raises(KeyError):
        repo.update_approval(dict(row, todo_id=str(uuid.uuid4())))


def test_대기_목록은_진행_중_처리_건의_제출된_단계의_PENDING_승인만_준다(world):
    pid, wi = _case(world)
    repo = world.rt.repo
    repo.insert_approval(_row(pid, wi['id']))
    assert wi['id'] not in [a['todo_id'] for a in repo.pending_approvals('hyd')], '단계가 아직 제출되지 않았다'
    import psycopg
    with psycopg.connect(world.dsn, autocommit=True) as db:
        db.execute("UPDATE todolist SET status='SUBMITTED' WHERE id=%s", (wi['id'],))
    assert wi['id'] in [a['todo_id'] for a in repo.pending_approvals('hyd')]
    with psycopg.connect(world.dsn, autocommit=True) as db:
        db.execute("UPDATE bpm_proc_inst SET status='COMPLETED' WHERE proc_inst_id=%s", (pid,))
    assert wi['id'] not in [a['todo_id'] for a in repo.pending_approvals('hyd')], '끝난 처리 건의 승인은 다시 집지 않는다'
