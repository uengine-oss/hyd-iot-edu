"""MQTT 브로커 규칙(ot/emqx/emqx.conf · acl.conf · users.csv) — 설비 명령 토픽은 명령 관문만 보낼 수 있다(G3b-5).

실제 EMQX(compose emqx 서비스 그대로 — 이미지 · 설정 파일 마운트, conftest ComposeContainer)에 실제 MQTT 클라이언트로 붙는다.
안쪽 입구 1883(ot-net 서비스, 이름만) · 바깥 입구 1884(호스트 1883) · 웹소켓 8083(계정 student 만, 구독만).
"""
import uuid

import paho.mqtt.client as mqtt
import pytest

from conftest import ComposeContainer, until

INNER, OUTER, WS = 1883, 1884, 8083


@pytest.fixture(scope='module')
def broker():
    box = ComposeContainer('emqx', INNER, extra_ports=(OUTER, WS))

    def ready():
        for port, user in ((INNER, 'plant-sim'), (OUTER, 'student')):      # 두 입구 모두 CONNACK 까지
            probe = Client(box, port, user, 'student' if user == 'student' else None)
            probe.close()
            if not probe.accepted:
                return False
        return True
    box.wait(ready, 'MQTT', 120)
    return box                     # conftest 가 같은 내용의 컨테이너를 다음 묶음에도 다시 쓴다


class Client:
    def __init__(self, broker, port, user=None, password=None, ws=False):
        self.events = {'connect': None, 'disconnect': None, 'suback': None}
        self.messages = []
        self.c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id='t-' + uuid.uuid4().hex[:8],
                             transport='websockets' if ws else 'tcp', protocol=mqtt.MQTTv5)
        if user is not None:
            self.c.username_pw_set(user, password)
        self.c.on_connect = lambda c, u, f, rc, p=None: self.events.__setitem__('connect', str(rc))
        self.c.on_disconnect = lambda c, u, f, rc, p=None: self.events.__setitem__('disconnect', str(rc))
        self.c.on_subscribe = lambda c, u, mid, rcs, p=None: self.events.__setitem__('suback', [str(r) for r in rcs])
        self.c.on_message = lambda c, u, m: self.messages.append(m.topic)
        self.c.connect('127.0.0.1', broker.ports[port], 10)
        self.c.loop_start()
        until(lambda: self.events['connect'] is not None, 'CONNACK', 10)

    @property
    def accepted(self):
        return self.events['connect'] == 'Success'

    def subscribe(self, topic):
        self.c.subscribe(topic, 1)
        until(lambda: self.events['suback'] is not None or self.events['disconnect'] is not None, 'SUBACK', 10)

    def close(self):
        self.c.loop_stop()
        self.c.disconnect()


@pytest.fixture
def plant(broker):
    """설비 자리(plant-sim 의 이름으로 안쪽 입구): 명령 토픽을 구독하고 받은 것을 남긴다."""
    c = Client(broker, INNER, 'plant-sim')
    c.subscribe('plant/+/cmd/auto')
    yield c
    c.close()


def _publish_reaches(broker, plant, port, user, password=None, ws=False, topic='plant/hyd01/cmd/auto'):
    sender = Client(broker, port, user, password, ws)
    if not sender.accepted:
        return 'refused'
    before = len(plant.messages)
    sender.c.publish(topic, '{"cmdId":"x"}', qos=1)
    try:
        until(lambda: len(plant.messages) > before or sender.events['disconnect'] is not None, '전달 또는 끊김', 5)
    finally:
        sender.close()
    return 'delivered' if len(plant.messages) > before else 'dropped'


@pytest.mark.parametrize('port, user, password, ws, outcome', [
    (INNER, 'cmd-gateway', None, False, 'delivered'),      # 명령 관문만
    (INNER, 'fuxa', None, False, 'dropped'),               # FUXA 는 수동 조작 · 모드만
    (INNER, 'plant-sim', None, False, 'dropped'),
    (INNER, None, None, False, 'dropped'),                 # 이름 없음
    (OUTER, 'student', 'student', False, 'dropped'),       # 바깥 입구는 구독만
    (OUTER, 'cmd-gateway', None, False, 'refused'),        # 바깥에서는 서비스 이름으로 들어올 수 없다
    (OUTER, 'cmd-gateway', 'guess', False, 'refused'),
    (OUTER, None, None, False, 'refused'),
    (WS, 'student', 'student', True, 'dropped'),           # 브라우저 웹소켓(출처 검사 없음)도 구독만
    (WS, 'cmd-gateway', None, True, 'refused'),
])
def test_설비_명령_토픽은_명령_관문만_보낼_수_있다(broker, plant, port, user, password, ws, outcome):
    assert _publish_reaches(broker, plant, port, user, password, ws) == outcome


def test_학생은_바깥_입구에서_설비_토픽을_구독해_받는다(broker):
    edge = Client(broker, INNER, 'plant-sim')
    student = Client(broker, OUTER, 'student', 'student')
    try:
        student.subscribe('plant/#')
        assert student.events['suback'] == ['Granted QoS 1']
        edge.c.publish('plant/hyd01/status', '{"mode":"REMOTE_AUTO"}', qos=1, retain=True)
        until(lambda: 'plant/hyd01/status' in student.messages, '학생이 상태를 받는다', 10)
    finally:
        edge.c.publish('plant/hyd01/status', b'', qos=1, retain=True).wait_for_publish(10)   # 남긴 보존 메시지를 지운다(뒤 테스트가 받지 않게)
        edge.close()
        student.close()


def test_FUXA는_수동_조작과_모드를_보내고_설비가_받는다(broker):
    edge, fuxa = Client(broker, INNER, 'plant-sim'), Client(broker, INNER, 'fuxa')
    try:
        edge.subscribe('plant/+/cmd/manual')
        fuxa.c.publish('plant/hyd01/cmd/manual', '{"FanSpeedSP": 80}', qos=1)
        until(lambda: 'plant/hyd01/cmd/manual' in edge.messages, 'FUXA 수동 쓰기가 설비에 닿는다', 10)
    finally:
        edge.close()
        fuxa.close()
