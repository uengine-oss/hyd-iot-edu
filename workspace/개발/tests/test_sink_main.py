"""시계열 적재(it/connect-sink/app/main.py) — 실제 TimescaleDB(compose 이미지 · init.sql 그대로, conftest timescale)에 적는다.

규칙(G3b-2 · 13 · 15 · 21 · 23): 기록 하나가 적재를 멈추지 않는다(거절하고 세며 오프셋은 나아간다), 시각이 틀린 기록은 다른 시각으로
바꿔 적지 않는다, 조치 표는 관문을 통과한 명령(CMD_FORWARDED)만이고 처음 기록을 덮지 않는다, FUXA 수동 응답은 조치가 아니다,
재생은 두 번 적지 않고 다시 만든 토픽은 건너뛰지 않는다, 옛 DB 도 켜질 때 고친 칸 · 보존 작업을 얻는다.
"""
import asyncio
import importlib.util
from types import SimpleNamespace

import psycopg
import pytest
from aiokafka.structs import TopicPartition

from conftest import ROOT
from hydcommon import topics

PATH = ROOT / 'it' / 'connect-sink' / 'app' / 'main.py'
T = '2026-10-30T05:00:00.000Z'
TS = 1_790_000_000_000


@pytest.fixture
def sink(timescale, monkeypatch):
    timescale.clear()
    with psycopg.connect(timescale.dsn, autocommit=True) as db:
        db.execute('DROP TABLE IF EXISTS sink_offsets')
    monkeypatch.setenv('PG_DSN', timescale.dsn)
    spec = importlib.util.spec_from_file_location('connect_sink_main', PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rec(offset, value, ts=TS):
    return SimpleNamespace(offset=offset, timestamp=ts, value=value)


def _store(sink, batches):
    async def run():
        conn = await sink.connect_db()
        try:
            await sink.store_records(conn, {TopicPartition(t, 0): recs for t, recs in batches.items()})
        finally:
            await conn.close()
    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)    # psycopg 비동기는 Windows 의 기본(Proactor) 루프를 못 쓴다


def _rows(timescale, sql):
    with psycopg.connect(timescale.dsn) as db:
        return db.execute(sql).fetchall()


def _tag(name='TS1', v=48.2, t=T, asset='HYD-01'):
    return {'asset': asset, 'name': name, 't': t, 'v': v, 'q': 'good'}


def test_독_기록은_거절하고_세며_같은_묶음의_좋은_기록과_오프셋은_적는다(sink, timescale):
    """G3b-2: 숫자 시각 · 빈 설비 하나로 적재가 영원히 멈췄다(재시작해도 같은 기록에서)."""
    _store(sink, {topics.K_TAG: [_rec(0, _tag()), _rec(1, _tag(t=1730000000)), _rec(2, _tag(asset=None)), _rec(3, {'_raw': 'x'}),
                                 _rec(4, _tag(v='48')), _rec(5, _tag(name='TS2', v=44.0))]})
    assert _rows(timescale, 'SELECT name, value FROM tag_1s ORDER BY name') == [('TS1', 48.2), ('TS2', 44.0)]
    assert sink.state['rejected'] == 4 and _rows(timescale, "SELECT next_offset FROM sink_offsets WHERE topic='plant.tag'") == [(6,)]


def test_시각이_없는_기록을_Kafka_시각으로_바꿔_적지_않는다(sink, timescale):
    """G3b-23: 틀린 시각을 Kafka 시각 · 지금으로 바꿔 Grafana 추세가 거짓이 됐다."""
    _store(sink, {topics.K_TAG: [_rec(0, dict(_tag(), t='bad'))], topics.K_AUDIT: [_rec(0, {'actor': 'a', 'event': 'E'})]})
    assert _rows(timescale, 'SELECT count(*) FROM tag_1s') == [(0,)] and _rows(timescale, 'SELECT count(*) FROM audit') == [(0,)]


def test_같은_기록을_다시_받아도_두_번_적지_않는다(sink, timescale):
    batch = {topics.K_TAG: [_rec(0, _tag()), _rec(1, _tag(v=48.3))]}
    _store(sink, batch)
    _store(sink, batch)                                        # 재시작 · 재배정 뒤의 재생
    assert _rows(timescale, 'SELECT count(*) FROM tag_1s') == [(2,)]


def test_다시_만든_토픽의_새_기록은_체크포인트에_가려지지_않는다(sink, timescale):
    """G3b-13: 오프셋만 견주어 새 토픽의 0번부터를 「이미 처리함」으로 조용히 넘겼다."""
    _store(sink, {topics.K_TAG: [_rec(100, _tag())]})
    _store(sink, {topics.K_TAG: [_rec(0, _tag(v=50.0), ts=TS + 3_600_000)]})
    assert _rows(timescale, 'SELECT value FROM tag_1s ORDER BY value') == [(48.2,), (50.0,)] and sink.state['offset_resets'] == 1


def _forwarded(cmd_id, incident='INC-1', actions=None):
    cmd = {'cmdId': cmd_id, 'asset': 'HYD-01', 'incident': incident, 'source': 'HITL', 'approvedBy': 'user:kim-op',
           'approvalId': 'APR-1', 'expiresAt': '2026-10-30T05:02:00Z', 'actions': actions or [{'code': 'FAN_SET', 'fan_pct': 100}]}
    return {'t': T, 'incident': incident, 'actor': 'cmd-gateway', 'event': 'CMD_FORWARDED', 'detail': {'cmdId': cmd_id, 'command': cmd}}


def _status(cmd_id, source, result='DONE'):
    return {'asset': 'HYD-01', 't': T, 'mode': 'REMOTE_AUTO', 'state': 'RUN', 'cmdId': cmd_id, 'result': result, 'source': source}


def test_조치_표는_관문을_통과한_명령과_자동_명령의_응답만_담고_처음_기록을_지킨다(sink, timescale):
    """G3b-15: action.cmd 를 무엇이든 「승인된 조치」로 적고 같은 cmdId 면 덮어썼다."""
    _store(sink, {topics.K_STATUS: [_rec(0, _status('CMD-1', 'HITL'))]})                     # 응답이 명령보다 먼저 와도
    _store(sink, {topics.K_AUDIT: [_rec(0, _forwarded('CMD-1')),
                                   _rec(1, _forwarded('CMD-1', incident='INC-forged', actions=[{'code': 'LOAD_SET', 'load_pct': 60}])),
                                   _rec(2, {'t': T, 'actor': 'cmd-gateway', 'event': 'CMD_REJECTED', 'detail': {'cmdId': 'CMD-X'}})],
                  topics.K_STATUS: [_rec(1, _status('FUXA-1', 'FUXA')), _rec(2, _status('CMD-1', 'HITL', 'REJECTED'))]})
    rows = _rows(timescale, 'SELECT cmd_id, incident, actions, ack_result FROM actions ORDER BY cmd_id')
    assert rows == [('CMD-1', 'INC-1', [{'code': 'FAN_SET', 'fan_pct': 100}], 'DONE')]
    assert _rows(timescale, "SELECT count(*) FROM audit WHERE event='CMD_REJECTED'") == [(1,)]


def test_경보는_발생_해제를_한_줄로_적고_그래프의_이름을_싣는다(sink, timescale):
    alert = {'alertId': 'A1', 'asset': 'HYD-02', 'pattern': 'PUMP_LEAKAGE', 'name': '펌프 내부 누설', 'severity': 'HIGH',
             'state': 'RAISE', 't': T, 'evidence': {'ps1': 160}}
    _store(sink, {topics.K_ALERTS: [_rec(0, alert), _rec(1, dict(alert, state='CLEAR', t='2026-10-30T05:05:00Z')),
                                    _rec(2, dict(alert, alertId='A2', state='CLEARED'))]})
    rows = _rows(timescale, 'SELECT alert_id, name, state, cleared_at IS NOT NULL FROM alerts')
    assert rows == [('A1', '펌프 내부 누설', 'CLEAR', True)] and sink.state['rejected'] == 1


def test_켜질_때_옛_DB에_칸과_30일_보존_작업을_붙이고_다시_켜도_하나다(sink, timescale):
    for _ in range(2):
        _store(sink, {})
    assert _rows(timescale, "SELECT count(*) FROM timescaledb_information.jobs WHERE proc_name='hyd_prune_events'") == [(1,)]
    assert _rows(timescale, "SELECT count(*) FROM information_schema.columns WHERE table_name='alerts' AND column_name='name'") == [(1,)]


def test_보존_작업은_30일_넘은_해제_경보_조치_감사만_지운다(sink, timescale):
    _store(sink, {})
    with psycopg.connect(timescale.dsn, autocommit=True) as db:
        db.execute("INSERT INTO alerts(alert_id, state, cleared_at) VALUES ('old','CLEAR', now()-interval '31 days'), "
                   "('open','RAISE', NULL), ('new','CLEAR', now())")
        db.execute("INSERT INTO audit(time, actor, event) VALUES (now()-interval '31 days','a','old'), (now(),'a','new')")
        db.execute("CALL hyd_prune_events(0, '{}')")
    assert _rows(timescale, 'SELECT alert_id FROM alerts ORDER BY alert_id') == [('new',), ('open',)]
    assert _rows(timescale, 'SELECT event FROM audit') == [('new',)]
