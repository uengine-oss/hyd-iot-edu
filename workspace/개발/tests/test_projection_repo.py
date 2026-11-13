"""처리 건 그래프 반영 대기열(procsvc/projection_repo.py) — 처리한 행은 처리 건마다 마지막 하나만 남고, 실패한 행은 늘어나는 간격으로 다시 보낸다.
그래프는 실제 Neo4j(world 의 수업 그래프), 대기열은 실제 업무 DB."""
import psycopg

from conftest import OPERATOR, until


def _outbox(dsn, pid):
    with psycopg.connect(dsn) as db:
        return db.execute('SELECT count(*) FILTER (WHERE processed_at IS NULL), count(*) FILTER (WHERE processed_at IS NOT NULL) '
                          'FROM execution_projection_outbox WHERE proc_inst_id=%s', (pid,)).fetchone()


def _retry_gap(dsn, pid):
    with psycopg.connect(dsn) as db:
        return db.execute('SELECT attempts, extract(epoch FROM retry_at - now()) FROM execution_projection_outbox '
                          'WHERE proc_inst_id=%s AND processed_at IS NULL ORDER BY id DESC LIMIT 1', (pid,)).fetchone()


def _approve(world):
    alert, pid, decision = world.start_cooling()
    world.approve(pid, decision, 'skill:sop-cool-11', OPERATOR)          # 작업 행이 바뀐다 → 반영 대기열에 한 줄
    return pid


def test_반영을_마친_대기열_행은_처리_건마다_마지막_하나만_남는다(world):
    """A-01: 전에는 처리 표시만 하고 지우지 않아, 작업 행이 바뀔 때마다 한 줄씩 끝없이 쌓였다."""
    pid = _approve(world)
    world.rt.reconcile_projections(limit=200)
    pending, processed = _outbox(world.dsn, pid)
    assert (pending, processed) == (0, 1), (pending, processed)
    status = world.rt.repo.projection_status('hyd', pid)
    assert status['pending'] == 0 and status['last_revision'] is not None, '마지막 반영 판은 남은 한 줄이 말한다'


def test_반영이_실패하면_행을_지우지_않고_다음_반영이_다시_보낸다(world):
    with world.storage_fails('execution_projection_outbox', "NEW.processed_at IS NOT NULL"):
        pid = _approve(world)
        world.rt.reconcile_projections(limit=200)
        pending, processed = _outbox(world.dsn, pid)
        assert pending > 0, '처리 표시를 못 한 행은 남아 다음 반영이 다시 보낸다'

    def settled():
        world.rt.reconcile_projections(limit=200)
        return _outbox(world.dsn, pid) == (0, 1)
    until(settled, '실패 행이 다시 시도 시각 뒤 반영되지 않았다', timeout=30)


def test_다시_보내는_간격은_실패할_때마다_두_배로_늘고_300초를_넘지_않는다(world):
    """P5-07: 그래프가 오래 멈춰도 5초마다 같은 실패를 다시 보내며 경고로 로그를 덮지 않게."""
    pid = _approve(world)
    snapshots = []
    for _ in range(8):                                 # 그래프가 여덟 번 연달아 받지 않았다(반영기가 남기는 실패 영수증 그대로)
        with world.rt.repo.projection_snapshot('hyd', pid) as snap:
            assert snap is not None
            world.rt.repo.finish_projection(snap, 'ServiceUnavailable: 시험 — 그래프가 받지 않음')
        snapshots.append(_retry_gap(world.dsn, pid))
    assert [a for a, _ in snapshots] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert [round(g) for _, g in snapshots] == [5, 10, 20, 40, 80, 160, 300, 300]
    with psycopg.connect(world.dsn, autocommit=True) as db:            # 다음 시도 시각을 지금으로 — 남은 행이 다음 테스트에 끼지 않게 반영해 둔다
        db.execute('UPDATE execution_projection_outbox SET retry_at=now() WHERE proc_inst_id=%s AND processed_at IS NULL', (pid,))
    world.rt.reconcile_projections(limit=200)
    assert _outbox(world.dsn, pid) == (0, 1)


def test_반영_대기_현황은_처리_건_수와_충돌과_가장_오래된_대기를_한눈에_준다(world):
    pid = _approve(world)
    backlog = world.rt.repo.projection_backlog('hyd', limit=10_000)
    assert backlog['rows'] >= 1 and pid in {i['proc_inst_id'] for i in backlog['items']} and backlog['oldest'] is not None
    with psycopg.connect(world.dsn, autocommit=True) as db:            # 그래프 영수증이 맞지 않은 처리 건(충돌)
        db.execute("UPDATE execution_projection_outbox SET last_error='ProjectionConflict: 시험' WHERE proc_inst_id=%s AND processed_at IS NULL", (pid,))
    try:
        assert world.rt.repo.projection_backlog('hyd')['conflicts'] >= 1
        status, out = world.api('GET', '/api/graph-projections')
        assert status == 200 and out['execution']['conflicts'] >= 1 and 'pending' in out
    finally:
        with psycopg.connect(world.dsn, autocommit=True) as db:
            db.execute("UPDATE execution_projection_outbox SET last_error=NULL WHERE proc_inst_id=%s AND processed_at IS NULL", (pid,))
    world.rt.reconcile_projections(limit=200)
    assert pid not in {i['proc_inst_id'] for i in world.rt.repo.projection_backlog('hyd', limit=10_000)['items']}
