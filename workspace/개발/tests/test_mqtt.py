"""MQTT 연결(common/hydcommon/mqtt.py) — 처리기 예외 하나로 네트워크 루프가 끝나지 않고, 세어 건강에 보인다(G3b-1 · 14).

paho 메시지 객체는 바깥(라이브러리)이라 그 꼴(topic · payload)만 가진 객체로 넣고, 연결 사건은 paho 가 부르는 콜백 그대로 부른다.
브로커 규칙(누가 무엇을 보낼 수 있나)은 실제 공장 브로커로 test_ot_broker 가, 실제 브리지와의 맞물림은 test_ot_bridge 가 잰다.

브리지 뒤의 연결(behind_bridge — DMZ 의 수집 중계 · 명령 관문): DMZ 브로커에 붙은 것만으로는 건강하지 않다. 공장 쪽 브리지가 올린 다리 상태
(bridge/ot/broker · bridge/ot/dmz)가 둘 다 「이어짐」일 때만 건강하고 발행을 받는다.
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


# ---------------------------------------------------------------- 브리지 뒤의 연결(DMZ 서비스)
def _leg(link, leg, up):
    link._message(link.client, None, SimpleNamespace(topic=f'bridge/ot/{leg}', payload=b'1' if up else b'0'))


def _behind(handler=lambda c, m: None, on_bridge_up=None):
    link = Link('unit-test', handler, host='127.0.0.1', port=1, behind_bridge=True, on_bridge_up=on_bridge_up)
    _connect(link)
    return link


def test_브리지_뒤의_연결은_다리_둘이_모두_이어졌다고_올라온_뒤에만_건강하다():
    link = _behind()
    assert not link.healthy() and link.health()['ot_bridge_legs'] == {'broker': None, 'dmz': None}      # 붙었지만 다리 상태를 아직 모른다
    _leg(link, 'dmz', True)
    assert not link.healthy() and link.health()['ot_bridge'] is False
    _leg(link, 'broker', True)
    assert link.healthy() and link.health()['ot_bridge'] is True
    _leg(link, 'broker', False)
    assert not link.healthy() and link.health()['ot_bridge_legs'] == {'broker': False, 'dmz': True} and link.health()['mqtt'] is True


def test_다시_붙으면_다리_상태를_모르는_것으로_돌아간다():
    """끊긴 동안 다리가 어떻게 됐는지 모른다 — 앞 연결에서 들은 「이어짐」을 믿고 건강하다고 하지 않는다."""
    link = _behind()
    _leg(link, 'broker', True), _leg(link, 'dmz', True)
    link._disconnected(link.client, None, None, ReasonCode(PacketTypes.DISCONNECT, 'Unspecified error'))
    _connect(link)
    assert link.connected and not link.healthy() and link.health()['ot_bridge_legs'] == {'broker': None, 'dmz': None}


def test_다리_상태_메시지는_처리기에_넘기지_않고_길이_이어질_때마다_알린다():
    seen, ups = [], []
    link = _behind(lambda c, m: seen.append(m.topic), on_bridge_up=lambda client: ups.append(1))
    _leg(link, 'broker', True), _leg(link, 'dmz', True), _leg(link, 'dmz', True)
    assert (seen, len(ups)) == ([], 1)
    _leg(link, 'dmz', False), _leg(link, 'dmz', True)
    link._message(link.client, None, SimpleNamespace(topic='plant/hyd01/status', payload=b'{}'))
    assert (seen, len(ups)) == (['plant/hyd01/status'], 2)


def test_브리지를_쓰지_않는_연결은_다리_상태를_보지_않는다():
    """공장 안의 엣지(plant-sim)는 공장 브로커에 바로 붙는다 — 다리 상태 토픽이 와도 여느 메시지이고 건강은 연결만 본다."""
    seen = []
    link = _link(lambda c, m: seen.append(m.topic))
    _connect(link)
    _leg(link, 'broker', False)
    assert link.healthy() and seen == ['bridge/ot/broker'] and 'ot_bridge' not in link.health()


def test_다리가_끊긴_동안_못_보냄으로_답한_명령은_다리가_이어진_뒤에도_나가지_않는다():
    """DMZ 브로커에는 붙어 있어 paho 는 받아 주지만 공장으로 옮길 다리가 없다 — 받지 않는다(거짓). 관문이 「못 보냄」으로 적은 명령이다."""
    broker = MqttRecorder(retained=[('bridge/ot/broker', '0'), ('bridge/ot/dmz', '1')])
    link = Link('unit-test', lambda c, m: None, host='127.0.0.1', port=broker.port, behind_bridge=True)
    broker.serve()
    link.start()
    try:
        until(lambda: link.health()['ot_bridge_legs'] == {'broker': False, 'dmz': True}, '다리 상태를 받는다')
        assert link.publish('plant/hyd01/cmd/auto', '{"cmdId":"c-3"}', qos=1) is False
        broker.send('bridge/ot/broker', '1')
        until(link.healthy, '다리가 이어진 것을 안다')
        assert link.publish('marker', '{}', qos=1) is True
        until(lambda: ('marker', '{}') in broker.published, '표식 도착')
    finally:
        link.stop()
    assert [topic for topic, _ in broker.published] == ['marker']
