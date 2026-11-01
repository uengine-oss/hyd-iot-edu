"""원천 접수(procsvc/source_inbox.py) — 경보 · 명령 응답 · 관문 거절은 접수 기록으로, 설비 상태와 상태마다 다시 실려 오는 같은 명령 응답은
설비별 최신 한 줄로, 그 밖의 감사 기록은 행 없이."""
import uuid

import psycopg

from hydcommon import topics

from conftest import OPERATOR
from procsvc.source_inbox import source_record


def _count(dsn, kind):
    with psycopg.connect(dsn) as db:
        return db.execute('SELECT count(*) FROM process_source_inbox WHERE kind=%s', (kind,)).fetchone()[0]


def _state(dsn, asset):
    with psycopg.connect(dsn) as db:
        return db.execute('SELECT payload, receipt_id FROM process_source_state WHERE tenant_id=%s AND asset=%s', ('hyd', asset)).fetchone()


def test_설비_상태_수신은_접수_기록을_남기지_않고_최신_상태만_바꾼다(world):
    """A-01: 전에는 상태 수신마다 원문을 가진 접수 행이 영구히 쌓였다(20배속 초당 약 3.6건)."""
    dsn = world.dsn
    before = _count(dsn, 'STATUS')
    world.clock.advance(1)
    first = world.receive(topics.K_STATUS, {'asset': 'HYD-02', 't': world.now_iso(), 'mode': 'REMOTE_AUTO', 'state': 'RUN', 'TS1': 41.0})
    world.clock.advance(1)
    world.receive(topics.K_STATUS, {'asset': 'HYD-02', 't': world.now_iso(), 'mode': 'REMOTE_AUTO', 'state': 'RUN', 'TS1': 42.0})
    assert first is None                                       # 접수 행이 없다(최신 상태 표만)
    assert _count(dsn, 'STATUS') == before
    payload, receipt = _state(dsn, 'HYD-02')
    assert payload['TS1'] == 42.0 and receipt is None


def test_늦게_온_옛_상태는_최신_상태를_덮지_않는다(world):
    dsn = world.dsn
    world.clock.advance(5)
    newer = world.now_iso()
    world.receive(topics.K_STATUS, {'asset': 'HYD-03', 't': newer, 'state': 'RUN', 'TS1': 50.0})
    world.receive(topics.K_STATUS, {'asset': 'HYD-03', 't': '2026-01-01T00:00:00.000Z', 'state': 'RUN', 'TS1': 70.0})
    assert _state(dsn, 'HYD-03')[0]['TS1'] == 50.0


def test_시각이_없는_상태는_무엇이_잘못_들어왔는지_접수_기록으로_남긴다(world):
    row = world.receive(topics.K_STATUS, {'asset': 'HYD-02', 'state': 'RUN'})
    assert row['status'] == 'INVALID' and 'timestamp' in row['error']


def test_명령_응답은_접수_기록으로_남고_최신_상태가_그_접수를_가리킨다(world):
    alert, pid, decision = world.start_cooling()
    world.approve(pid, decision, 'skill:sop-cool-11', OPERATOR)
    cmd = world.commanded(pid)
    receipt = world.ack('HYD-01', cmd['cmdId'])
    assert receipt['kind'] == 'ACK' and receipt['status'] == 'HANDLED'
    payload, receipt_id = _state(world.dsn, 'HYD-01')
    assert payload['cmdId'] == cmd['cmdId'] and receipt_id == receipt['id']


def _rows(dsn, cmd_id):
    with psycopg.connect(dsn) as db:
        return db.execute("SELECT status FROM process_source_inbox WHERE kind='ACK' AND event_key=%s ORDER BY id",
                          ('["command-ack","%s"]' % cmd_id,)).fetchall()


def _heartbeat(world, cmd_id, result='DONE', **values):
    """PLC 상태 수신 하나 — 마지막 명령 응답(cmdId · result)을 붙여 보낸다(plantsim plc 와 같은 꼴)."""
    world.clock.advance(1)
    return world.receive(topics.K_STATUS, {'asset': 'HYD-02', 't': world.now_iso(), 'mode': 'REMOTE_AUTO', 'state': 'RUN',
                                           'cmdId': cmd_id, 'result': result, **values})


def test_상태마다_다시_실려_오는_같은_명령_응답은_접수_행을_더_만들지_않고_최신_상태만_바꾼다(world):
    """P2-01: 명령 하나 뒤 상태 수신마다 같은 응답이 「중복 접수」 행(원문 + 전송 원문)으로 쌓였다(24분에 1,282행)."""
    cmd = 'CMD-TEST-' + __import__('uuid').uuid4().hex[:8]
    first = _heartbeat(world, cmd, TS1=40.0)
    repeats = [_heartbeat(world, cmd, TS1=40.0 + n) for n in range(1, 4)]
    assert first['kind'] == 'ACK' and first['id'] is not None
    assert repeats == [None] * 3                                # 접수 행이 없다(최신 상태만)
    assert len(_rows(world.dsn, cmd)) == 1
    payload, receipt = _state(world.dsn, 'HYD-02')
    assert (payload['TS1'], receipt) == (43.0, first['id'])


def test_같은_명령의_다른_결과는_내용마다_한_번만_충돌로_남는다(world):
    cmd = 'CMD-TEST-' + __import__('uuid').uuid4().hex[:8]
    _heartbeat(world, cmd, 'DONE')
    conflicts = [_heartbeat(world, cmd, 'REJECTED', reason='INTERLOCK') for _ in range(3)]
    assert conflicts[0]['status'] == 'CONFLICT' and conflicts[1:] == [None] * 2
    dsn = world.dsn
    assert [r[0] for r in _rows(dsn, cmd)][1:] == ['CONFLICT']


# ---------------------------------------------------------------- 명령 관문의 거절(G3b-9) — audit 토픽
def _rejected(cmd_id, asset='HYD-01', **over):
    return {'t': '2026-11-02T09:00:00Z', 'incident': None, 'asset': asset, 'actor': 'cmd-gateway', 'event': 'CMD_REJECTED',
            'detail': {'cmdId': cmd_id, 'check': 'MODE', 'reason': 'mode LOCAL', 'reason_text': '설비가 현장 조작 상태라 원격 명령을 받지 않습니다'},
            **over}


def test_관문_거절은_명령마다_REJECT_접수로_처리기가_읽는_칸만_싣는다():
    record = source_record(topics.K_AUDIT, 0, 7, _rejected('CMD-1'))
    assert (record['kind'], record['event_key'], record['error']) == ('REJECT', '["command-reject","CMD-1"]', None)
    assert record['payload'] == {'asset': 'HYD-01', 'cmdId': 'CMD-1', 'check': 'MODE',
                                 'reason_text': '설비가 현장 조작 상태라 원격 명령을 받지 않습니다'}


def test_다른_감사_기록은_원천_사건이_아니다():
    for value in ({'actor': 'process', 'event': 'CMD_SENT', 'asset': 'HYD-01', 'detail': {'cmdId': 'CMD-1'}},
                  _rejected('CMD-1', actor='someone-else'), {'_raw': 'not json'}):
        assert source_record(topics.K_AUDIT, 0, 1, value)['kind'] == 'AUDIT'


def test_명령_번호가_없는_관문_거절은_무엇이_빠졌는지_남긴다():
    record = source_record(topics.K_AUDIT, 0, 1, _rejected(None))
    assert record['kind'] == 'INVALID' and 'cmdId' in record['error']


def test_관문_거절은_한_번만_접수되고_감사_기록은_행을_만들지_않는다(world):
    cmd = 'CMD-TEST-' + uuid.uuid4().hex[:8]
    assert world.receive(topics.K_AUDIT, {'actor': 'process', 'event': 'CMD_SENT', 'asset': 'HYD-01', 'detail': {'cmdId': cmd}}) is None
    first = world.receive(topics.K_AUDIT, _rejected(cmd))
    again = world.receive(topics.K_AUDIT, _rejected(cmd))
    world.deliver()
    assert (first['kind'], again['status'], again['parent_id']) == ('REJECT', 'DUPLICATE', first['id'])
    handled = world.main.source_inbox.get(first['id'])          # 어느 사건에도 없는 명령 — 처리기가 「할 일 없음」으로 끝낸다
    assert handled['status'] == 'HANDLED' and handled['result']['cmdId'] == cmd
    assert _count(world.dsn, 'AUDIT') == 0
