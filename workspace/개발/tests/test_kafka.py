"""Kafka 도우미(common/hydcommon/kafka.py) — 깨진 값은 예외 없이 표시, 전송 결과는 브로커 답으로 센다(G3b-14), 재생과 다시 만든
토픽을 가른다(G3b-13). 브로커는 바깥이라 conftest 의 KafkaRecorder(브로커 답 future)를 쓴다."""
import asyncio

import pytest

from conftest import KafkaRecorder
from hydcommon import kafka


@pytest.mark.parametrize('raw, value', [
    (None, {}), (b'{"a": 1}', {'a': 1}), (b'[1]', {'_raw': '[1]'}), (b'not json', {'_raw': 'not json'}),
    (b'\xff\xfe', {'_raw': '��'}),
])
def test_값_해석은_예외를_내지_않고_객체가_아니면_원문으로_표시한다(raw, value):
    assert kafka.decode_value(raw) == value


def test_브로커가_받은_것과_거절한_것을_따로_센다():
    recorder, delivery = KafkaRecorder(), kafka.Delivery()
    recorder.fail.add('audit')

    async def scenario():
        await delivery.send(recorder, 'plant.tag', {'v': 1}, key='hyd01')
        await delivery.send(recorder, 'audit', {'v': 2})
        await asyncio.sleep(0)                      # future 완료 콜백이 돈다
    asyncio.run(scenario())
    assert (delivery.delivered, delivery.failed) == (1, 1) and delivery.last_error.startswith('audit: ConnectionError')
    assert not delivery.healthy() and delivery.healthy(now=delivery.last_error_at + kafka.ERROR_WINDOW_S)


def test_큐에_넣기_전에_거절되면_세고_다시_올린다():
    class Refusing:
        async def send(self, topic, value=None, key=None):
            raise ValueError('message too large')
    delivery = kafka.Delivery()
    with pytest.raises(ValueError):
        asyncio.run(delivery.send(Refusing(), 'plant.tag', {}))
    assert delivery.failed == 1


@pytest.mark.parametrize('offset, ts, position, max_ts, verdict', [
    (10, 5000, None, None, 'new'),         # 처음 보는 파티션
    (10, 5000, 10, 4000, 'new'),           # 체크포인트 다음
    (9, 3000, 10, 4000, 'seen'),           # 재생 — 처리한 것보다 오래된 기록
    (9, 4000, 10, 4000, 'seen'),           # 경계: 같은 시각
    (0, 9000, 10, 4000, 'recreated'),      # 오프셋은 아래인데 처리한 어떤 것보다 새 기록 — 토픽을 다시 만들었다
])
def test_체크포인트_아래_기록은_재생인지_다시_만든_토픽인지_가른다(offset, ts, position, max_ts, verdict):
    assert kafka.replay_verdict(offset, ts, position, max_ts) == verdict
