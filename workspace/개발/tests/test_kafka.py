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


class _Consumer:
    """aiokafka 소비자 자리(브로커 쪽 — 바깥): 파티션마다 위치 · 끝 오프셋과, 다음 기록이 읽히는지 · 풀지 못하는지 · 브로커가 답하지 않는지만 가진다.
    실제 브로커에서의 동작(늦은 브로커 포함)은 test_gw_main 의 관문 고리 시험이 잰다."""

    def __init__(self, positions, poisoned, silent=()):
        self.positions, self.poisoned, self.silent, self.committed = dict(positions), set(poisoned), set(silent), {}
        self.ends = {tp: at + 1 for tp, at in positions.items()}     # 위치마다 기록 하나가 기다린다

    def assignment(self):
        return set(self.positions)

    async def position(self, tp):
        return self.positions[tp]

    async def end_offsets(self, tps):
        return {tp: self.ends[tp] for tp in tps}

    async def getmany(self, tp, timeout_ms, max_records):
        if tp in self.silent:                        # 브로커가 답하지 않는다 — 한 번의 기다림이 빈손으로 끝난다
            await asyncio.sleep(timeout_ms / 1000)
            return {}
        if tp in self.poisoned:
            raise RuntimeError('UnsupportedCodecError: snappy')
        self.positions[tp] += 1                      # 읽으면 위치가 나아간다(탐침이 읽은 기록)
        return {tp: [object()]}

    def seek(self, tp, offset):
        self.positions[tp] = offset

    async def commit(self, offsets):
        self.committed.update(offsets)


@pytest.mark.parametrize('poisoned', [['alerts'], ['action.cmd'], [], ['alerts', 'action.cmd']], ids=['경보 토픽', '명령 토픽', '없음', '둘 다'])
def test_읽을_수_없는_기록은_그_파티션만_하나_건너뛰고_멀쩡한_파티션은_제자리다(poisoned):
    """06-5: 관문의 소비 고리가 읽을 수 없는 기록 하나를 만나면 배정된 모든 파티션을 하나씩 건너뛰었다 — 경보 토픽의 깨진 기록 때문에 아직
    처리하지 않은 설비 명령 하나가 사라졌다. 파티션마다 따로 읽어 다시 실패하는 곳만 건너뛴다."""
    from aiokafka.structs import TopicPartition
    start = {TopicPartition('action.cmd', 0): 40, TopicPartition('alerts', 0): 7}
    cons = _Consumer(start, [tp for tp in start if tp.topic in poisoned])
    stepped = asyncio.run(kafka.step_over_poison(cons))
    assert sorted(tp.topic for tp, _, _ in stepped) == sorted(poisoned)
    assert cons.positions == {tp: at + (tp.topic in poisoned) for tp, at in start.items()}
    assert cons.committed == {tp: at + 1 for tp, at in start.items() if tp.topic in poisoned}


def test_다음_기록이_있는데_브로커가_정한_시간_안에_답하지_않으면_읽힌다로_보지_않고_그_자리를_말하며_실패한다():
    """답이 없는 것을 「읽힌다」로 보면 깨진 기록을 넘기지 못한 채 고리가 같은 기록에서 다시 시작한다 — 시끄럽게 실패하고, 그 파티션은 제자리다."""
    from aiokafka.structs import TopicPartition
    cmd, alerts = TopicPartition('action.cmd', 0), TopicPartition('alerts', 0)
    cons = _Consumer({cmd: 40, alerts: 7}, [alerts], silent=[cmd])
    with pytest.raises(kafka.PoisonProbeError, match=r'action\.cmd/0: .*record at 40 \(end 41\)'):
        asyncio.run(kafka.step_over_poison(cons, probe_s=1.2))
    assert cons.positions == {cmd: 40, alerts: 7} and cons.committed == {}
