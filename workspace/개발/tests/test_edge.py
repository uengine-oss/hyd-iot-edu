"""엣지(ot/plant-sim/plantsim/edge.py) — MQTT 메시지 → PLC 명령, 틱마다 태그와 상태가 같은 시각(G3b-1 · 4).

브로커는 바깥이라 엣지의 MQTT 연결(hydcommon.mqtt.Link) 대신 발행을 받아 적는 연결을 끼운다 — 그 연결의 꼴(publish · connected)만
쓰고, 메시지 처리는 엣지의 실제 처리기(_on_message)를 그대로 부른다.
"""
import json
from types import SimpleNamespace

import pytest

from plantsim import edge as edge_mod
from plantsim.plant import Plant


class RecordingLink:
    """브로커 자리: 엣지가 낸 것을 (토픽, 본문)으로 남긴다."""
    def __init__(self):
        self.connected, self.sent = True, []

    def publish(self, topic, payload, qos=0, retain=False):
        self.sent.append((topic, json.loads(payload)))
        return True


@pytest.fixture
def edge():
    e = edge_mod.Edge(Plant(time_scale=20), daq_profile='lite')
    e.link = RecordingLink()
    return e


def _msg(topic, payload):
    return SimpleNamespace(topic=topic, payload=payload if isinstance(payload, bytes) else json.dumps(payload).encode())


def test_한_틱의_태그와_상태는_같은_측정_시각이다(edge):
    """G3b-4: 상태 시각이 태그보다 0~2 ms 늦어 감지기가 PLC 상태를 「미래 값」으로 보고 펌프 누설 유지를 끊었다."""
    edge.tick()
    stamps = {body.get('t') for topic, body in edge.link.sent if topic.endswith('/status') or '/tag/' in topic}
    assert len(stamps) == 1 and len(edge.link.sent) > 3


@pytest.mark.parametrize('payload, result, reason', [
    (b'\xff\xfe', 'REJECTED', 'BAD_FORMAT'),                                  # G3b-1: UnicodeDecodeError 가 루프를 끝냈다
    (b'[1, 2]', 'REJECTED', 'BAD_FORMAT'),
    ({'cmdId': 'x', 'writes': 5, 'expiresAt': '2099-01-01T00:00:00Z'}, 'REJECTED', 'BAD_FORMAT'),
    ({'cmdId': 'x', 'writes': [{'res': 'FanSpeedSP', 'v': 90}], 'expiresAt': 5}, 'REJECTED', 'BAD_EXPIRY'),
    ({'cmdId': 'ok', 'writes': [{'res': 'FanSpeedSP', 'v': 90}], 'expiresAt': '2099-01-01T00:00:00Z'}, 'DONE', None),
])
def test_자동_명령은_어떤_꼴이든_응답_상태로_끝난다(edge, payload, result, reason):
    edge._on_message(None, _msg('plant/hyd01/cmd/auto', payload))
    status = [body for topic, body in edge.link.sent if topic == 'plant/hyd01/status'][-1]
    assert (status['result'], status['reason'], status['source']) == (result, reason, 'HITL')


def test_수동_쓰기는_FUXA_출처로_실행되고_원격_수동이_된다(edge):
    edge._on_message(None, _msg('plant/hyd02/cmd/manual', {'FanSpeedSP': 75}))
    status = [body for topic, body in edge.link.sent if topic == 'plant/hyd02/status'][-1]
    assert (status['result'], status['source'], status['mode'], status['fan_pct']) == ('DONE', 'FUXA', 'REMOTE_MANUAL', 75.0)
    assert status['cmdId'].startswith('FUXA-')


@pytest.mark.parametrize('payload, mode', [({'mode': 0}, 'LOCAL'), (b'1', 'REMOTE_MANUAL'), (b'"REMOTE_AUTO"', 'REMOTE_AUTO'),
                                           ({'mode': '2.0'}, 'REMOTE_AUTO')])
def test_FUXA_모드_메시지의_여러_꼴을_모드로_읽는다(edge, payload, mode):
    edge.plant.units['HYD-01'].ctrl.mode = 'REMOTE_MANUAL' if mode != 'REMOTE_MANUAL' else 'LOCAL'
    edge._on_message(None, _msg('plant/hyd01/mode', payload))
    assert edge.plant.units['HYD-01'].ctrl.mode == mode and edge.refused == 0


@pytest.mark.parametrize('payload', [b'\xff', {'mode': 'TURBO'}, {'mode': [1]}, b'true'])
def test_모드가_아닌_메시지는_바꾸지_않고_세어_둔다(edge, payload):
    edge._on_message(None, _msg('plant/hyd01/mode', payload))
    assert edge.plant.units['HYD-01'].ctrl.mode == 'REMOTE_AUTO' and edge.refused == 1


def test_없는_설비_토픽은_건드리지_않는다(edge):
    edge._on_message(None, _msg('plant/hyd09/cmd/auto', {'cmdId': 'x'}))
    assert edge.commands == 0 and edge.link.sent == []


def test_끊긴_동안에는_내보내지_않고_DAQ도_보낸_것으로_치지_않는다(edge):
    edge.link.connected = False
    edge.tick()
    assert edge.link.sent == [] and 'EPS1' in edge.daq.due('HYD-01', edge.plant.tags('HYD-01'), 0.0)
