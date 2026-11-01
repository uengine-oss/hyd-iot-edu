"""MQTT 연결(common/hydcommon/mqtt.py) — 처리기 예외 하나로 네트워크 루프가 끝나지 않고, 세어 건강에 보인다(G3b-1 · 14).

paho 메시지 객체는 바깥(라이브러리)이라 그 꼴(topic · payload)만 가진 객체로 넣고, 연결 사건은 paho 가 부르는 콜백 그대로 부른다.
브로커 규칙(누가 무엇을 보낼 수 있나)은 실제 EMQX 로 test_emqx 가 잰다.
"""
from types import SimpleNamespace

from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.reasoncodes import ReasonCode

from hydcommon.mqtt import ERROR_WINDOW_S, Link


def _link(handler):
    return Link('unit-test', handler, host='127.0.0.1', port=1)


def _connect(link, reason='Success'):
    link._connected(link.client, None, None, ReasonCode(PacketTypes.CONNACK, reason))


def test_처리기가_예외를_내도_네트워크_루프로_올리지_않고_세며_다음_메시지는_처리된다():
    seen = []

    def handler(client, msg):
        if msg.payload == b'bad':
            raise TypeError('unhashable list')
        seen.append(msg.payload)
    link = _link(handler)
    link._message(link.client, None, SimpleNamespace(topic='plant/hyd01/mode', payload=b'bad'))
    link._message(link.client, None, SimpleNamespace(topic='plant/hyd01/mode', payload=b'good'))
    assert seen == [b'good'] and link.handler_errors == 1
    assert link.health()['mqtt_last_error'].startswith('plant/hyd01/mode: TypeError')


def test_처리기_실패_뒤_한동안은_건강하지_않다():
    link = _link(lambda c, m: 1 / 0)
    _connect(link)
    assert link.healthy()
    link._message(link.client, None, SimpleNamespace(topic='t', payload=b''))
    assert not link.healthy() and link.healthy(now=link.last_error_at + ERROR_WINDOW_S + 1)


def test_연결_상태는_실제_연결_끊김_거절_사건을_따른다():
    link = _link(lambda c, m: None)
    assert link.health()['mqtt'] is False
    _connect(link)
    assert link.connected
    link._disconnected(link.client, None, None, ReasonCode(PacketTypes.DISCONNECT, 'Unspecified error'))
    assert not link.connected and not link.healthy()
    _connect(link, 'Not authorized')
    assert not link.connected


def test_연결되지_않았을_때의_발행은_거짓이다():
    assert _link(lambda c, m: None).publish('plant/hyd01/status', '{}') is False
