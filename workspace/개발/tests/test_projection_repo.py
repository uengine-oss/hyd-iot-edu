"""처리 건 그래프 반영 대기열(procsvc/projection_repo.py) — 처리한 행은 처리 건마다 마지막 하나만 남는다."""
import psycopg

from test_instances import OPERATOR, _start_cooling


def _outbox(dsn, pid):
    with psycopg.connect(dsn) as db:
        return db.execute('SELECT count(*) FILTER (WHERE processed_at IS NULL), count(*) FILTER (WHERE processed_at IS NOT NULL) '
                          'FROM execution_projection_outbox WHERE proc_inst_id=%s', (pid,)).fetchone()


def test_반영을_마친_대기열_행은_처리_건마다_마지막_하나만_남는다(world):
    """A-01: 전에는 처리 표시만 하고 지우지 않아, 작업 행이 바뀔 때마다 한 줄씩 끝없이 쌓였다."""
    alert, pid, decision = _start_cooling(world)
    world.rt.select(world.row(pid, 'T_approve', 'IN_PROGRESS')['id'], decision, 'skill:sop-cool-11', **OPERATOR)
    world.rt.reconcile_projections(limit=200)
    pending, processed = _outbox(world.services.dsn, pid)
    assert (pending, processed) == (0, 1), (pending, processed)
    status = world.rt.repo.projection_status('hyd', pid)
    assert status['pending'] == 0 and status['last_revision'] is not None, '마지막 반영 판은 남은 한 줄이 말한다'


def test_반영이_실패하면_대기열_행은_지우지_않고_다시_시도한다(world):
    alert, pid, decision = _start_cooling(world)
    with world.storage_fails('execution_projection_outbox', "NEW.processed_at IS NOT NULL AND NEW.proc_inst_id = '{}'".format(pid)):
        world.rt.select(world.row(pid, 'T_approve', 'IN_PROGRESS')['id'], decision, 'skill:sop-cool-11', **OPERATOR)   # 작업 행이 바뀐다
        world.rt.reconcile_projections(limit=200)
        pending, processed = _outbox(world.services.dsn, pid)
        assert pending > 0, '처리 표시를 못 한 행은 남아 다음 폴링이 다시 반영한다'
    world.rt._project({'proc_inst_id': pid})          # 실패 행은 5초(DB 시각) 뒤 폴링이 다시 반영한다 — 그 반영 한 번
    assert _outbox(world.services.dsn, pid) == (0, 1)
