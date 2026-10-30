"""원천 접수(procsvc/source_inbox.py) — 경보 · 명령 응답은 접수 기록으로, 설비 상태는 설비별 최신 한 줄로."""
import psycopg

from hydcommon import topics


def _count(dsn, kind):
    with psycopg.connect(dsn) as db:
        return db.execute('SELECT count(*) FROM process_source_inbox WHERE kind=%s', (kind,)).fetchone()[0]


def _state(dsn, asset):
    with psycopg.connect(dsn) as db:
        return db.execute('SELECT payload, receipt_id FROM process_source_state WHERE tenant_id=%s AND asset=%s', ('hyd', asset)).fetchone()


def test_설비_상태_수신은_접수_기록을_남기지_않고_최신_상태만_바꾼다(world):
    """A-01: 전에는 상태 수신마다 원문을 가진 접수 행이 영구히 쌓였다(20배속 초당 약 3.6건)."""
    dsn = world.services.dsn
    before = _count(dsn, 'STATUS')
    world.clock.advance(1)
    first = world.receive(topics.K_STATUS, {'asset': 'HYD-02', 't': world.now_iso(), 'mode': 'REMOTE_AUTO', 'state': 'RUN', 'TS1': 41.0})
    world.clock.advance(1)
    world.receive(topics.K_STATUS, {'asset': 'HYD-02', 't': world.now_iso(), 'mode': 'REMOTE_AUTO', 'state': 'RUN', 'TS1': 42.0})
    assert first['status'] == 'STATE_ONLY' and first['id'] is None
    assert _count(dsn, 'STATUS') == before
    payload, receipt = _state(dsn, 'HYD-02')
    assert payload['TS1'] == 42.0 and receipt is None


def test_늦게_온_옛_상태는_최신_상태를_덮지_않는다(world):
    dsn = world.services.dsn
    world.clock.advance(5)
    newer = world.now_iso()
    world.receive(topics.K_STATUS, {'asset': 'HYD-03', 't': newer, 'state': 'RUN', 'TS1': 50.0})
    world.receive(topics.K_STATUS, {'asset': 'HYD-03', 't': '2026-01-01T00:00:00.000Z', 'state': 'RUN', 'TS1': 70.0})
    assert _state(dsn, 'HYD-03')[0]['TS1'] == 50.0


def test_시각이_없는_상태는_무엇이_잘못_들어왔는지_접수_기록으로_남긴다(world):
    row = world.receive(topics.K_STATUS, {'asset': 'HYD-02', 'state': 'RUN'})
    assert row['status'] == 'INVALID' and 'timestamp' in row['error']


def test_명령_응답은_접수_기록으로_남고_최신_상태가_그_접수를_가리킨다(world):
    from test_instances import OPERATOR, _commanded, _start_cooling
    alert, pid, decision = _start_cooling(world)
    world.rt.select(world.row(pid, 'T_approve', 'IN_PROGRESS')['id'], decision, 'skill:sop-cool-11', **OPERATOR)
    cmd = _commanded(world, pid)
    receipt = world.ack('HYD-01', cmd['cmdId'])
    assert receipt['kind'] == 'ACK' and receipt['status'] == 'HANDLED'
    payload, receipt_id = _state(world.services.dsn, 'HYD-01')
    assert payload['cmdId'] == cmd['cmdId'] and receipt_id == receipt['id']
