"""MQTT 연결(common/hydcommon/mqtt.py) — 처리기 예외 하나로 네트워크 루프가 끝나지 않고, 세어 건강에 보인다(G3b-1 · 14).

paho 메시지 객체는 바깥(라이브러리)이라 그 꼴(topic · payload)만 가진 객체로 넣고, 연결 사건은 paho 가 부르는 콜백 그대로 부른다.
브로커 규칙(누가 무엇을 보낼 수 있나)은 실제 EMQX 로 test_emqx 가 잰다.
"""
from types import SimpleNamespace

from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.reasoncodes import ReasonCode

from conftest import MqttRecorder, until
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


def _publishes_after_reconnect(link, broker):
    """브로커를 열어 연결을 붙이고 표식 하나를 보낸 뒤, 브로커가 받은 PUBLISH 토픽을 돌려준다(표식보다 먼저 온 것이 「뒤늦게 나간」 것)."""
    broker.serve()
    link.start()
    try:
        until(lambda: link.connected, '대역 브로커에 연결')
        assert link.publish('marker', '{}', qos=1) is True
        until(lambda: ('marker', '{}') in broker.published, '표식 도착')
    finally:
        link.stop()
    return [topic for topic, _ in broker.published]


def test_끊긴_동안_못_보냄으로_답한_명령은_다시_붙은_뒤에도_나가지_않는다():
    """관문은 발행이 거짓이면 「못 보냄」(CMD_REJECTED)을 적고 process 가 처리 건을 닫는다. 그 명령이 재연결 뒤 설비에 닿으면 기록과 설비가 어긋난다."""
    broker = MqttRecorder()
    link = Link('unit-test', lambda c, m: None, host='127.0.0.1', port=broker.port)
    assert link.publish('plant/hyd01/cmd/auto', '{"cmdId":"c-1"}', qos=1) is False
    assert _publishes_after_reconnect(link, broker) == ['marker']


def test_끊김_사건보다_먼저_소켓이_사라진_순간의_발행도_거짓이고_나가지_않는다():
    """connected 가 아직 참인데 paho 가 연결 없음으로 답하는 틈 — paho 는 그 QoS 1 메시지를 보낼 줄에 남겨 재연결 때 보낸다."""
    broker = MqttRecorder()
    link = Link('unit-test', lambda c, m: None, host='127.0.0.1', port=broker.port)
    link.connected = True
    assert link.publish('plant/hyd01/cmd/auto', '{"cmdId":"c-2"}', qos=1) is False
    link.connected = False                       # 뒤따라 온 끊김 사건
    assert _publishes_after_reconnect(link, broker) == ['marker']
