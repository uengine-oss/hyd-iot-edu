"""공장 MQTT 브로커 규칙(ot/emqx/emqx.conf · acl.conf · users.csv) — 설비 명령 토픽은 공장 쪽 브리지만 낼 수 있다(G3b-5).

실제 EMQX(compose emqx 서비스 그대로 — 이미지 · 설정 파일 마운트, conftest PlantMqtt)에 실제 MQTT 클라이언트로 붙는다.
안쪽 입구 1883(OT 망의 서비스, 이름만) · 바깥 입구 1884(호스트 1883) · 웹소켓 8083(계정 student 만, 구독만).
공장 밖(DMZ)의 서비스 이름(cmd-gateway · connect-ingest)은 이 브로커의 규칙에 없다 — 명령 관문이 DMZ 브로커에 놓은 명령을 공장 쪽 브리지가
가져와 내는 길은 test_ot_bridge.py 가 실제 세 컨테이너로 잰다.
관리 화면 · 관리 API(18083)는 꺼져 있다 — 관리 API 의 발행은 토픽 규칙을 거치지 않는다(2026-11-14 실측: 공개된 초기 비밀번호로 들어가
plant/hyd03/cmd/auto 에 낸 명령을 가상 설비가 실행했다).
"""
import http.client

import pytest

from conftest import MqttClient, until

INNER, OUTER, WS, ADMIN = 1883, 1884, 8083, 18083


@pytest.fixture(scope='module')
def broker(plant_mqtt):
    box = plant_mqtt.plant_box

    def ready():
        for port, user in ((INNER, 'plant-sim'), (OUTER, 'student')):      # 두 입구 모두 CONNACK 까지
            probe = Client(box, port, user, 'student' if user == 'student' else None)
            probe.close()
            if not probe.accepted:
                return False
        return True
    box.wait(ready, 'MQTT', 120)
    return box                     # conftest 가 같은 내용의 컨테이너를 다음 묶음에도 다시 쓴다


def Client(broker, port, user=None, password=None, ws=False):
    return MqttClient(broker.ports[port], user, password, ws)


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
    (INNER, 'ot-bridge', None, False, 'delivered'),        # 공장 쪽 브리지만(명령 관문이 검증해 DMZ 브로커에 놓은 것을 옮긴다)
    (INNER, 'cmd-gateway', None, False, 'dropped'),        # 공장 밖의 이름은 이 브로커에서 아무것도 못 한다
    (INNER, 'connect-ingest', None, False, 'dropped'),
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
def test_공장_브로커에서_설비_명령_토픽은_공장_쪽_브리지만_낼_수_있다(broker, plant, port, user, password, ws, outcome):
    assert _publish_reaches(broker, plant, port, user, password, ws) == outcome


def test_관리_API는_꺼져_있어_토픽_규칙_밖으로_명령을_낼_길이_없다(broker):
    """관리 API 자리(18083)에 로그인을 보내면 HTTP 로 답하는 것이 없어야 한다 — 답이 오면(200 이든 401 이든) 관리 API 가 켜져 있는 것이고,
    그 API 의 발행은 acl.conf 를 거치지 않는다."""
    conn = http.client.HTTPConnection('127.0.0.1', broker.ports[ADMIN], timeout=5)
    try:
        conn.request('POST', '/api/v5/login', body='{"username":"admin","password":"public"}', headers={'Content-Type': 'application/json'})
        answered = conn.getresponse().status
    except (OSError, http.client.HTTPException):
        answered = None
    finally:
        conn.close()
    assert answered is None


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
