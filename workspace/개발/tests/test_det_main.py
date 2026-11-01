"""감지기 서비스(it/detector/det/main.py) — 기록 하나로 감지가 멈추지 않고(G3b-3), 쿨러 전용 최상위 칸이 없고(G3b-11),
체크포인트는 경보 때와 주기로만(G3b-12), 다시 만든 토픽을 알아챈다(G3b-13).

Kafka 는 바깥이라 소비 기록은 aiokafka 레코드의 꼴(topic · partition · offset · timestamp · value)만 가진 객체로, 송신은 conftest 의
KafkaRecorder 로 넣는다. 정의는 실제 시드 그래프에서 감지기의 함수(fetch_catalog)로 읽는다.
"""
import asyncio
import importlib
import sys
from types import SimpleNamespace

import pytest

from conftest import KafkaRecorder
from hydcommon import topics

T0 = 1_790_000_000.0


@pytest.fixture
def det(monkeypatch, tmp_path, seeded_graph):
    monkeypatch.setenv('TIME_SCALE', '20')
    monkeypatch.setenv('DAQ_PROFILE', 'lite')
    monkeypatch.setenv('DETECTOR_STATE_PATH', str(tmp_path / 'detector.sqlite3'))
    import det.main as main
    main = importlib.reload(main)                         # 상태를 새로(테스트끼리 남지 않게)
    assert asyncio.run(main.refresh_catalog()), main.catalog_status
    return main


def _iso(t):
    from datetime import datetime, timezone
    return datetime.fromtimestamp(t, timezone.utc).isoformat()


def _rec(topic, value, offset=0, ts=None):
    return SimpleNamespace(topic=topic, partition=0, offset=offset, timestamp=int((ts or T0) * 1000), value=value)


def _feed(det, prod, records):
    async def run():
        for r in records:
            await det.process(prod, r)
    asyncio.run(run())


def _tick(t, asset='HYD-02', ps1=160.0, fs1=7.5, state='RUN', ts1=48.0):
    out = [_rec(topics.K_STATUS, {'asset': asset, 't': _iso(t), 'mode': 'REMOTE_AUTO', 'state': state, 'trip': None})]
    for name, v in (('CE', 84.0), ('PS1', ps1), ('FS1', fs1), ('LoadSP', 90.0), ('TS1', ts1)):
        out.append(_rec(topics.K_TAG, {'asset': asset, 'name': name, 't': _iso(t), 'v': v, 'q': 'good'}))
    return out


def time_now():
    """지금보다 1.5 초 앞 — 감지기는 벽시계로 표본이 오래됐는지(보고 1 s + 여유 2 s) 본다."""
    import time
    return time.time() - 1.5


def _ticks(**kw):
    """벽시계 네 틱(1 초 간격, 지금을 가운데로) — 20배속에서 60 설비 초 유지가 차는 데 필요한 만큼."""
    start = time_now()
    return [r for i in range(4) for r in _tick(start + i, **kw)]


@pytest.mark.parametrize('record', [
    _rec(topics.K_WAVE, {'asset': 'HYD-02', 'sensor': 'PS1', 't0': '2026-10-30T05:00:00Z', 'hz': 10, 'v': ['x']}),   # G3b-3
    _rec(topics.K_STATUS, {'asset': 'HYD-02', 't': '2026-10-30T05:00:00Z', 'mode': 'REMOTE_AUTO', 'state': 'TRIP',
                           'trip': ['OVERTEMP']}),                                                                    # G3b-3
    _rec(topics.K_TAG, {'asset': 'HYD-02', 'name': 'TS1', 't': 1730000000, 'v': 1}),
    _rec(topics.K_TAG, {'asset': 'HYD-99', 'name': 'TS1', 't': '2026-10-30T05:00:00Z', 'v': 1}),                    # G3b-28
    _rec(topics.K_TAG, {'_raw': 'not json'}),
])
def test_계약_밖_기록은_세고_건너뛰며_다음_기록의_감지는_이어진다(det, record):
    prod = KafkaRecorder()
    _feed(det, prod, [record] + _ticks())
    assert det.state['rejected'] == 1 and det.state['last_rejected'].startswith(record.topic)
    assert [e['pattern'] for e in det.pending_alerts] == ['PUMP_LEAKAGE'] and 'HYD-99' not in det.assets


def test_펌프_누설_경보에는_패턴_이름과_근거_값이_실린다(det):
    prod = KafkaRecorder()
    _feed(det, prod, _ticks())
    (alert,) = det.pending_alerts
    assert (alert['name'], alert['evidence']['ps1'], alert['evidence']['load']) == ('펌프 내부 누설', 160.0, 90.0)
    assert prod.of(topics.K_FEAT) and all(f['sensor'] == 'TS1' for f in prod.of(topics.K_FEAT))


def test_PLC_트립은_이름_있는_트립_경보로_울린다(det):
    prod = KafkaRecorder()
    now = time_now()
    _feed(det, prod, [_rec(topics.K_STATUS, {'asset': 'HYD-01', 't': _iso(now), 'mode': 'REMOTE_AUTO', 'state': 'TRIP',
                                             'trip': 'OVERTEMP'})])
    (alert,) = det.pending_alerts
    assert (alert['pattern'], alert['name'], alert['severity']) == ('OVERHEAT_TRIP', '과열 인터록 트립', 'CRITICAL')


def test_상태_API에는_패턴별_단계만_있고_쿨러_전용_최상위_칸이_없다(det):
    """G3b-11: 개요 카드가 최상위 phase(쿨러 하나)를 읽어 펌프 · 팬 경보를 놓쳤다."""
    prod = KafkaRecorder()
    _feed(det, prod, _ticks())
    view = det.detector_state()['assets']['HYD-02']
    assert not {'phase', 'alert_id', 'since', 'cep_state'} & set(view)
    assert view['patterns']['PUMP_LEAKAGE']['phase'] == 'RAISED' and set(det.detector_state()['assets']) == set(topics.ASSETS)


def test_처리_중_예외가_난_기록은_세고_한동안_건강하지_않지만_다음_기록은_처리된다(det):
    class Exploding(KafkaRecorder):
        async def send(self, topic, key=None, value=None):
            raise RuntimeError('broker client crashed')
    _feed(det, Exploding(), _tick(time_now()))
    assert det.state['record_errors'] == 1 and not det.health()['ok']
    _feed(det, KafkaRecorder(), _tick(time_now() + 1, asset='HYD-03'))
    assert det.runtime.asset('HYD-03').observations.samples['TS1']['valid']


def test_배속이나_수집_방식이_없으면_켜지지_않는다(monkeypatch):
    monkeypatch.delenv('DAQ_PROFILE', raising=False)
    sys.modules.pop('det.main', None)
    with pytest.raises(ValueError, match='DAQ_PROFILE'):
        importlib.import_module('det.main')
    monkeypatch.setenv('DAQ_PROFILE', 'lite')
    importlib.import_module('det.main')


def test_경보가_없는_기록은_하나마다가_아니라_주기로만_체크포인트를_쓴다(det, brokers, monkeypatch):
    """G3b-12: 레코드마다 SQLite 체크포인트 + 커밋이면 1초 보고마다 디스크 쓰기가 몰린다 — 경보 때와 CHECKPOINT_S 주기로만.
    실제 redpanda 에 설비 상태 20건을 한꺼번에 내고 실제 run() 이 처리한 뒤의 체크포인트 자리를 본다."""
    import time
    from aiokafka import AIOKafkaProducer
    monkeypatch.setenv('KAFKA_BOOTSTRAP', brokers.kafka)

    def status(i):
        return {'asset': 'HYD-02', 't': _iso(time.time() + i * 0.001), 'mode': 'REMOTE_AUTO', 'state': 'RUN', 'trip': None}

    async def scenario():
        task = asyncio.create_task(det.run())
        sender = AIOKafkaProducer(bootstrap_servers=brokers.kafka, value_serializer=lambda v: __import__('json').dumps(v).encode())
        await sender.start()
        try:
            while not det.state['kafka']:
                assert not task.done(), task.exception()
                await asyncio.sleep(0.05)
            seen = det.state['statuses']
            started = time.monotonic()
            last = None
            for i in range(20):
                last = await sender.send_and_wait(topics.K_STATUS, status(i), key=b'hyd02')
            while det.state['statuses'] < seen + 20:
                await asyncio.sleep(0.02)
            quick = time.monotonic() - started < det.CHECKPOINT_S      # 한 주기 안에 다 처리했을 때만 판정이 선다
            between = det.store.position(topics.K_STATUS, last.partition)[0]
            deadline = time.monotonic() + 30                           # 주기가 지나면 다음 기록과 함께 체크포인트 · 커밋
            while (det.store.position(topics.K_STATUS, last.partition)[0] or 0) <= last.offset:
                assert time.monotonic() < deadline, '주기가 지나도 체크포인트가 쓰이지 않았다'
                await sender.send_and_wait(topics.K_STATUS, status(-1), key=b'hyd02')
                await asyncio.sleep(0.2)
            return quick, between, last.offset
        finally:
            await sender.stop()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    quick, between, last = asyncio.run(scenario())
    assert quick, '20건을 한 주기 안에 처리하지 못해 이 판정을 할 수 없다(PC 가 너무 바쁨)'
    assert between is None or between <= last - 18, f'경보 없는 기록마다 체크포인트를 썼다(처리 직후 자리 {between}, 마지막 {last})'
