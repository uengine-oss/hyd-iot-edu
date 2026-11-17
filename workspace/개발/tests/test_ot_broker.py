"""공장 브로커 규칙(ot/broker/mosquitto.conf · acl · passwd) — 설비 명령 토픽은 공장 쪽 브리지만 낼 수 있다(G3b-5).

실제 공장 브로커(compose ot-broker 서비스 그대로 — mosquitto 이미지 · 설정 폴더 마운트, conftest PlantMqtt)에 실제 MQTT 5 클라이언트로 붙는다.
입구 셋: 안쪽 입구 1883(OT 망의 서비스 — 이름만 댄다) · 바깥 입구 1884(호스트 1883) · 웹소켓 8083(호스트 8083). 바깥 둘은 계정 student 만, 구독만.
공장 밖(DMZ)의 서비스 이름(cmd-gateway · connect-ingest)은 이 브로커의 규칙에 없다 — 명령 관문이 DMZ 브로커에 놓은 명령을 공장 쪽 브리지가
가져와 내는 길은 test_ot_bridge.py 가 실제 세 컨테이너로 잰다.
허락되지 않은 발행은 설비 자리에 닿지 않고, 보낸 쪽은 PUBACK 「Not authorized」로 거절을 듣는다(MQTT 5 — 조용히 사라진 것처럼 보이지 않는다).
관리 화면 · 관리 API 는 없다: 브로커가 듣는 입구는 설정한 셋뿐이다. 토픽 규칙을 거치지 않고 메시지를 낼 다른 입구가 생기면 여기서 걸린다
(옛 공장 브로커 EMQX 는 관리 API 의 발행이 토픽 규칙을 거치지 않아, 공개된 초기 비밀번호로 낸 명령을 가상 설비가 실행했다 — 2026-11-14 실측).
"""
import json
import uuid

import pytest

from conftest import MqttClient, _accepts, _docker, until

INNER, OUTER, WS = 1883, 1884, 8083
COMMAND = 'plant/hyd01/cmd/auto'


@pytest.fixture(scope='module')
def broker(plant_mqtt):
    box = plant_mqtt.plant_box
    box.wait(lambda: _accepts(box.ports[INNER], 'plant-sim') and _accepts(box.ports[OUTER], 'student', 'student'), '두 입구의 CONNACK', 120)
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


def _bodies(client, topic):
    return [body for t, body, _ in client.received if t == topic]


def _publish_outcome(broker, plant, port, user, password=None, ws=False):
    """그 입구 · 이름으로 설비 명령을 낸다 → 'refused'(연결을 받지 않음) · 'delivered'(PUBACK 성공, 설비 자리에 닿음) ·
    'denied'(PUBACK 「Not authorized」, 설비 자리에 닿지 않음). 닿지 않았다는 것은 그 뒤에 공장 쪽 브리지 이름으로 낸 표식이 설비 자리에 닿을
    때까지 기다린 뒤에 본다 — 한 브로커가 같은 구독자에게 보내는 차례는 받은 차례라, 앞의 것이 갔다면 표식보다 먼저 와 있다."""
    sender = Client(broker, port, user, password, ws)
    if not sender.accepted:
        sender.close()
        return 'refused'
    body, marker = json.dumps({'cmdId': f'from-{user}-{uuid.uuid4().hex[:6]}'}), json.dumps({'cmdId': f'marker-{uuid.uuid4().hex[:6]}'})
    bridge = Client(broker, INNER, 'ot-bridge')
    try:
        mid = sender.publish(COMMAND, body, qos=1).mid
        until(lambda: mid in sender.puback, f'PUBACK({sender.events})', 5)
        bridge.publish(COMMAND, marker, qos=1)
        until(lambda: marker in _bodies(plant, COMMAND), '표식이 설비 자리에 닿는다', 10)
    finally:
        sender.close()
        bridge.close()
    reached, reason = body in _bodies(plant, COMMAND), sender.puback[mid]
    return {(True, 'Success'): 'delivered', (False, 'Not authorized'): 'denied'}.get((reached, reason), f'닿음={reached} · PUBACK={reason}')


@pytest.mark.parametrize('port, user, password, ws, outcome', [
    (INNER, 'ot-bridge', None, False, 'delivered'),        # 공장 쪽 브리지만(명령 관문이 검증해 DMZ 브로커에 놓은 것을 옮긴다)
    (INNER, 'cmd-gateway', None, False, 'denied'),         # 공장 밖의 이름은 이 브로커에서 아무것도 못 한다
    (INNER, 'connect-ingest', None, False, 'denied'),
    (INNER, 'fuxa', None, False, 'denied'),                # FUXA 는 수동 조작 · 모드만
    (INNER, 'plant-sim', None, False, 'denied'),
    (INNER, 'student', None, False, 'denied'),             # 안쪽 입구에서 student 이름을 대도 낼 수 없다
    (INNER, None, None, False, 'denied'),                  # 이름 없음
    (OUTER, 'student', 'student', False, 'denied'),        # 바깥 입구는 구독만
    (OUTER, 'ot-bridge', None, False, 'refused'),          # 바깥에서는 서비스 이름으로 들어올 수 없다
    (OUTER, 'ot-bridge', 'guess', False, 'refused'),
    (OUTER, 'student', 'guess', False, 'refused'),
    (OUTER, None, None, False, 'refused'),
    (WS, 'student', 'student', True, 'denied'),            # 브라우저 웹소켓(출처 검사 없음)도 구독만
    (WS, 'ot-bridge', None, True, 'refused'),
    (WS, None, None, True, 'refused'),
])
def test_공장_브로커에서_설비_명령_토픽은_공장_쪽_브리지만_낼_수_있다(broker, plant, port, user, password, ws, outcome):
    assert _publish_outcome(broker, plant, port, user, password, ws) == outcome


def test_공장_브로커가_듣는_입구는_설정한_셋뿐이다(broker):
    """관리 화면 · 관리 API 같은 옆문이 없다 — 컨테이너 안에서 실제로 듣는 TCP 입구가 안쪽 · 바깥 · 웹소켓 셋뿐이다(127.0.0.11 은 Docker 의 이름 풀이)."""
    lines = _docker('exec', broker.name, 'netstat', '-ltn').splitlines()
    listening = {int(cols[3].rsplit(':', 1)[1]) for cols in (line.split() for line in lines) if cols and cols[0].startswith('tcp')
                 and not cols[3].startswith('127.0.0.11:')}
    assert listening == {INNER, OUTER, WS}


@pytest.mark.parametrize('port, ws', [(OUTER, False), (WS, True)])
def test_학생은_바깥_입구에서_설비_토픽을_구독해_받는다(broker, port, ws):
    edge = Client(broker, INNER, 'plant-sim')
    student = Client(broker, port, 'student', 'student', ws)
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
        edge.subscribe('plant/+/mode')
        fuxa.c.publish('plant/hyd01/cmd/manual', '{"FanSpeedSP": 80}', qos=1)
        fuxa.c.publish('plant/hyd01/mode', '{"mode": 2}', qos=1)
        until(lambda: {'plant/hyd01/cmd/manual', 'plant/hyd01/mode'} <= set(edge.messages), 'FUXA 수동 쓰기 · 모드가 설비에 닿는다', 10)
    finally:
        edge.close()
        fuxa.close()
