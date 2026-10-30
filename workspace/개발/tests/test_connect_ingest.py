"""설비 → Kafka 복제(dmz/connect-ingest/app/main.py) — 버리는 메시지는 반드시 세어 /healthz 에 보인다(하-06).

규칙: 복제하지 못하고 버린 메시지는 종류별로 센다 — 해석할 수 없는 글(UTF-8 · JSON 아님 · 객체 아님) = malformed,
Kafka 로 보내지 못한 것 = send_failed. 둘 다 /healthz 본문에 나온다. Kafka 는 바깥이라 보내기가 실패하는 대체 생산자를 쓴다.
"""
import asyncio
import importlib.util
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[3] / 'dmz' / 'connect-ingest' / 'app' / 'main.py'


@pytest.fixture
def ingest():
    spec = importlib.util.spec_from_file_location('connect_ingest_main', PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)            # 새로 읽어 셈을 0 에서 시작한다
    return module


@pytest.mark.parametrize('payload', [b'\xff\xfe not utf-8', b'{"t": 1, ', b'[1, 2, 3]', b'"just text"', b'42'])
def test_해석할_수_없는_설비_메시지는_버리고_malformed로_센다(ingest, payload):
    assert ingest.to_kafka('plant/hyd01/tag/TS1', payload) is None
    assert ingest.health()['malformed'] == 1


def test_올바른_설비_메시지는_세지_않고_Kafka_형태로_바꾼다(ingest):
    out = ingest.to_kafka('plant/hyd01/tag/TS1', b'{"t": 1.5, "v": 48.2}')
    assert out is not None and out[2]['v'] == 48.2 and ingest.health()['malformed'] == 0


def test_Kafka로_보내지_못한_메시지는_send_failed로_센다(ingest):
    class RefusingProducer:                     # Kafka 자리: 보내기마다 실패
        async def send(self, *args, **kwargs):
            raise ConnectionError('broker down')

    async def scenario():
        async def make_producer():
            return RefusingProducer()
        ingest.make_producer = make_producer
        task = asyncio.create_task(ingest.pump())
        ingest.queue.put_nowait(('plant.tag', 'hyd01', {'v': 1}))
        for _ in range(1000):                   # 조건이 될 때까지 이벤트 루프를 돌린다(벽시계 대기 없음)
            if ingest.state.get('send_failed'):
                break
            await asyncio.sleep(0)
        task.cancel()
        return ingest.health()

    body = asyncio.run(scenario())
    assert body['send_failed'] == 1 and body['replicated'] == 0
