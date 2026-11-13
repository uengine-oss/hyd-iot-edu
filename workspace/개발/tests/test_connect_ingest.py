"""설비 → Kafka 복제(dmz/connect-ingest/app/main.py) — 계약 밖 메시지는 이유와 함께 세고 버리며, 보낸 것은 브로커 답으로 센다
(하-06 · G3b-2 · 14 · 28). Kafka 는 바깥이라 송신기는 conftest 의 KafkaRecorder 를 pump 에 넘긴다(우리 함수를 바꿔 끼우지 않는다 — G5b-07).
"""
import asyncio
import importlib.util
from types import SimpleNamespace

import pytest

from conftest import KafkaRecorder, ROOT
from hydcommon import topics

PATH = ROOT / 'dmz' / 'connect-ingest' / 'app' / 'main.py'
T = '2026-10-30T05:00:00.000Z'


@pytest.fixture
def ingest():
    spec = importlib.util.spec_from_file_location('connect_ingest_main', PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)            # 새로 읽어 셈을 0 에서 시작한다
    return module


@pytest.mark.parametrize('topic, payload, why', [
    ('plant/hyd01/tag/TS1', b'\xff\xfe not utf-8', 'UTF-8 JSON'),
    ('plant/hyd01/tag/TS1', b'{"t": 1, ', 'UTF-8 JSON'),
    ('plant/hyd01/tag/TS1', b'[1, 2, 3]', 'object'),
    ('plant/hyd01/tag/TS1', b'{"t": 1730000000, "v": 1}', 't must'),                    # G3b-2: 적재를 멈춘 숫자 시각
    ('plant/hyd01/tag/NOPE', b'{"t": "2026-10-30T05:00:00Z", "v": 1}', 'DAQ tag'),       # G3b-28: 없는 태그
    ('plant/hyd77/tag/TS1', b'{"t": "2026-10-30T05:00:00Z", "v": 1}', 'known asset'),   # G3b-28: 없는 설비
    ('plant/hyd01/wave/PS1', b'{"t0": "2026-10-30T05:00:00Z", "hz": 10, "v": ["x"]}', 'v[0]'),   # G3b-3
    ('plant/hyd01/status', b'{"t": "2026-10-30T05:00:00Z", "mode": "LOCAL", "state": "RUN", "asset": "HYD-02"}', 'topic'),
    ('plant/hyd01/cmd/auto', b'{}', 'replicated kind'),
])
def test_계약_밖_설비_메시지는_버리고_까닭과_함께_센다(ingest, topic, payload, why):
    ingest._on_message(None, SimpleNamespace(topic=topic, payload=payload))
    body = ingest.health()
    assert body['malformed'] == 1 and why in body['last_malformed'] and ingest.queue.qsize() == 0


def test_올바른_설비_메시지는_세지_않고_Kafka_기록으로_바꾼다(ingest):
    ktopic, key, value = ingest.to_kafka('plant/hyd01/tag/TS1', b'{"t": "2026-10-30T05:00:00.000Z", "v": 48.2, "q": "good"}')
    assert (ktopic, key, value) == (topics.K_TAG, 'hyd01', {'asset': 'HYD-01', 'name': 'TS1', 't': T, 'v': 48.2, 'q': 'good'})
    _, _, status = ingest.to_kafka('plant/hyd02/status', b'{"t": "2026-10-30T05:00:00Z", "mode": "LOCAL", "state": "RUN"}')
    assert status['asset'] == 'HYD-02' and ingest.health()['malformed'] == 0


def _pump(ingest, recorder, items):
    async def scenario():
        for item in items:
            ingest.queue.put_nowait(item)
        task = asyncio.create_task(ingest.pump(recorder))
        for _ in range(1000):                   # 조건이 될 때까지 이벤트 루프를 돌린다(벽시계 대기 없음)
            if ingest.queue.empty() and ingest.delivery.delivered + ingest.delivery.failed == len(items):
                break
            await asyncio.sleep(0)
        task.cancel()
    asyncio.run(scenario())


def test_브로커가_거절한_기록은_건강을_나쁘게_하고_받은_기록과_따로_센다(ingest):
    recorder = KafkaRecorder()
    recorder.fail.add(topics.K_STATUS)
    ingest.state['kafka'] = True
    _pump(ingest, recorder, [(topics.K_TAG, 'hyd01', {'v': 1}), (topics.K_STATUS, 'hyd01', {'v': 2})])
    body = ingest.health()
    assert (body['kafka_delivered'], body['kafka_failed'], recorder.of(topics.K_TAG)) == (1, 1, [{'v': 1}])
    assert body['ok'] is False and body['kafka_last_error'].startswith(topics.K_STATUS)


def test_대기열이_차면_버리고_센다(ingest):
    for _ in range(ingest.QUEUE_MAX + 2):
        ingest._enqueue((topics.K_TAG, 'hyd01', {}))
    assert ingest.state['dropped'] == 2
