"""공장 쪽 브리지(ot/bridge/mosquitto.conf)와 DMZ 브로커(dmz/broker/mosquitto.conf · acl) — 값은 공장이 내보내고, 승인된 명령은 공장이 가져간다.

실제 세 컨테이너(conftest PlantMqtt — compose 의 emqx · dmz-broker · ot-bridge 그대로, 망도 compose 대로)에 실제 MQTT 클라이언트로 붙는다.
공장 안의 자리(plant-sim · fuxa)는 공장 브로커의 안쪽 입구에, DMZ 의 자리(명령 관문 · 수집 중계)는 DMZ 브로커에 붙는다 — 시험이 두 브로커를
잇지 않으므로, 한쪽에 낸 것이 다른 쪽에 닿았다면 브리지가 옮긴 것이다.
  - 값(측정값 · 파형 · 설비 상태)은 공장 브로커 → DMZ 브로커로 올라간다.
  - 설비 명령은 DMZ 브로커에 명령 관문이 놓은 것만 공장 브로커로 내려간다(다른 이름이 놓으려 하면 DMZ 브로커가 받지 않는다).
  - 경보판은 보존된 채로 내려가, 뒤에 붙는 운전 화면도 받는다.
  - 다리가 끊기면 DMZ 의 서비스가 그 사실을 안다(hydcommon.mqtt.Link behind_bridge): 건강하지 않고, 발행을 받지 않으며, 끊긴 동안 DMZ
    브로커에 놓인 명령은 다시 이어져도 설비로 내려가지 않는다.
누가 누구에게 망으로 닿는지(DMZ 에서 공장 브로커로 연결이 열리지 않는다)는 test_zones.py 가 잰다.
"""
import json

import pytest

from conftest import MqttClient, _docker, site_network, until
from hydcommon.mqtt import Link

LEGS_UP = {'broker': True, 'dmz': True}


@pytest.fixture
def clients(plant_mqtt):
    """(이름, 자리) → 그 이름으로 붙은 클라이언트. 자리 plant = 공장 브로커 안쪽 입구, dmz = DMZ 브로커. 끝나면 모두 닫는다."""
    plant_mqtt.wait_bridge(LEGS_UP)
    opened = []

    def join(name, side):
        client = MqttClient({'plant': plant_mqtt.plant, 'dmz': plant_mqtt.dmz}[side][1], name)
        opened.append(client)
        assert client.accepted, (name, side, client.events)
        return client
    yield join
    for client in opened:
        client.close()


def _bodies(client, topic):
    return [body for t, body, _ in client.received if t == topic]


def test_공장_브로커에_나온_값은_DMZ_브로커로_올라간다(clients):
    edge, ingest = clients('plant-sim', 'plant'), clients('connect-ingest', 'dmz')
    for topic in ('plant/+/tag/+', 'plant/+/wave/+', 'plant/+/status'):
        ingest.subscribe(topic)
    sent = {'plant/hyd02/tag/TS1': '{"t":"2026-11-17T00:00:00Z","v":48.5,"q":"good"}',
            'plant/hyd02/wave/PS1': '{"t0":"2026-11-17T00:00:00Z","hz":10,"v":[1.0,2.0]}',
            'plant/hyd02/status': '{"t":"2026-11-17T00:00:00Z","mode":"LOCAL","state":"RUN"}'}
    try:
        for topic, body in sent.items():
            edge.publish(topic, body, qos=1, retain=topic.endswith('/status'))
        until(lambda: all(body in _bodies(ingest, topic) for topic, body in sent.items()), f'값이 DMZ 브로커에 닿는다(받은 것 {ingest.received})', 15)
    finally:
        edge.publish('plant/hyd02/status', b'', qos=1, retain=True).wait_for_publish(10)      # 남긴 보존 메시지를 지운다(브리지가 DMZ 쪽 것도 지운다)


@pytest.mark.parametrize('name, reaches', [
    ('cmd-gateway', True),            # 명령 관문만 DMZ 브로커의 명령 토픽에 놓을 수 있고, 놓인 것은 브리지가 가져간다
    ('connect-ingest', False),        # 수집 중계는 읽기만 한다
    ('ot-bridge', False),             # 브리지의 이름으로도 DMZ 쪽 명령 토픽에는 놓지 못한다(가져가기만 한다)
    ('student', False), ('fuxa', False), ('plant-sim', False),
    (None, False),                    # 이름 없음
])
def test_DMZ_브로커에_명령_관문이_놓은_명령만_설비_자리로_내려간다(clients, name, reaches):
    plant, sender = clients('plant-sim', 'plant'), clients(name, 'dmz')
    gateway = sender if name == 'cmd-gateway' else clients('cmd-gateway', 'dmz')
    plant.subscribe('plant/+/cmd/auto')
    sender.publish('plant/hyd01/cmd/auto', json.dumps({'cmdId': f'from-{name}'}), qos=1).wait_for_publish(10)
    gateway.publish('plant/hyd03/cmd/auto', '{"cmdId":"marker"}', qos=1)                 # 표식: 관문이 뒤에 놓은 것이 닿을 때까지 기다린다
    until(lambda: '{"cmdId":"marker"}' in _bodies(plant, 'plant/hyd03/cmd/auto'), '표식 명령이 설비 자리에 닿는다', 15)
    assert (json.dumps({'cmdId': f'from-{name}'}) in _bodies(plant, 'plant/hyd01/cmd/auto')) is reaches


def test_경보판은_보존된_채로_내려가_뒤에_붙은_운전_화면도_받는다(clients):
    gateway = clients('cmd-gateway', 'dmz')
    board = '{"level":2,"count":1,"display_text":"경보 1건 · 팬 진동 상승"}'
    gateway.publish('plant/hyd03/alert', board, qos=1, retain=True).wait_for_publish(10)
    try:
        def late_screen_has_it():
            screen = clients('fuxa', 'plant')          # 판이 올라온 뒤에 붙는 운전 화면
            screen.subscribe('plant/+/alert')
            try:
                until(lambda: screen.received, '보존된 경보판', 2)
            except TimeoutError:
                return False
            return ('plant/hyd03/alert', board, True) in screen.received
        until(late_screen_has_it, '뒤에 붙은 운전 화면이 보존된 경보판을 받는다', 15)
    finally:
        gateway.publish('plant/hyd03/alert', b'', qos=1, retain=True).wait_for_publish(10)


def _dmz_link(plant_mqtt, name='cmd-gateway'):
    link = Link(name, lambda client, msg: None, host=plant_mqtt.dmz[0], port=plant_mqtt.dmz[1], behind_bridge=True)
    link.start()
    return link


def test_브리지가_멈추면_DMZ_서비스는_건강하지_않고_그동안_놓인_명령은_다시_이어져도_내려가지_않는다(plant_mqtt, clients):
    plant, raw = clients('plant-sim', 'plant'), clients('cmd-gateway', 'dmz')
    plant.subscribe('plant/+/cmd/auto')
    link = _dmz_link(plant_mqtt)
    try:
        until(link.healthy, f'다리 둘이 이어진 동안은 건강하다({link.health()})', 15)
        assert link.health()['ot_bridge'] is True and link.health()['ot_bridge_legs'] == LEGS_UP
        _docker('stop', '-t', '2', plant_mqtt.bridge_box.name)
        until(lambda: not link.healthy(), '브리지가 멈춘 것을 안다', 20)
        body = link.health()
        assert body['mqtt'] is True and body['ot_bridge'] is False            # DMZ 브로커에는 붙어 있다 — 그것만으로 「정상」이 아니다
        assert link.publish('plant/hyd01/cmd/auto', '{"cmdId":"refused"}', qos=1) is False
        raw.publish('plant/hyd01/cmd/auto', '{"cmdId":"while-down"}', qos=1).wait_for_publish(10)      # 연결 규칙을 건너뛰고 브로커에 놓인 명령
    finally:
        _docker('start', plant_mqtt.bridge_box.name)
        try:
            plant_mqtt.wait_bridge(LEGS_UP)
            until(link.healthy, f'다시 이어지면 건강하다({link.health()})', 20)
            assert link.publish('plant/hyd01/cmd/auto', '{"cmdId":"after"}', qos=1) is True
            until(lambda: '{"cmdId":"after"}' in _bodies(plant, 'plant/hyd01/cmd/auto'), '다시 이어진 뒤의 명령은 내려간다', 15)
            assert _bodies(plant, 'plant/hyd01/cmd/auto') == ['{"cmdId":"after"}']       # 끊긴 동안의 것(refused · while-down)은 오지 않았다
        finally:
            link.stop()


def test_공장_브로커와_끊기면_어느_다리인지와_함께_드러난다(plant_mqtt):
    """공장 브로커가 OT 망에서 떨어진 것처럼(망에서 뗀다) — DMZ 쪽 다리는 살아 있어 DMZ 브로커 연결만 보면 아무 일도 없어 보인다."""
    link = _dmz_link(plant_mqtt, 'connect-ingest')
    plant, net = plant_mqtt.plant_box.name, site_network('ot-net')
    try:
        until(link.healthy, f'다리 둘이 이어진 동안은 건강하다({link.health()})', 15)
        _docker('network', 'disconnect', net, plant)
        try:
            until(lambda: link.health()['ot_bridge_legs'] == {'broker': False, 'dmz': True}, f'공장 브로커 쪽 다리가 끊긴 것을 안다({link.health()})', 30)
            assert not link.healthy() and link.health()['mqtt'] is True
        finally:
            _docker('network', 'connect', '--alias', 'emqx', net, plant)
        plant_mqtt.wait_bridge(LEGS_UP)
        until(link.healthy, f'다시 이어지면 건강하다({link.health()})', 20)
    finally:
        link.stop()
