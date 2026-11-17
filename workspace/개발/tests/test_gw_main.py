"""명령 관문 서비스(dmz/cmd-gateway/gw/main.py) — 결정마다 감사 기록, 거절은 사유와 학생 문장으로(G3b-9 · 15 · 22), 상태는 토픽의 설비로(G3b-28).

Kafka 송신은 conftest KafkaRecorder, MQTT 메시지는 paho 메시지 꼴(topic · payload · retain)의 객체로 처리기에 넣는다(바깥만 대체).
"""
import asyncio
import importlib
import sys
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from conftest import KafkaRecorder
from hydcommon import schemas, topics

KEY = 'gw-test-key'


@pytest.fixture
def gw(monkeypatch):
    monkeypatch.setenv('CMD_FINGERPRINT_KEY', KEY)
    import gw.main as main
    return importlib.reload(main)


@pytest.fixture
def live_gw(brokers, monkeypatch):
    """관문을 이 자리의 실제 DMZ 브로커(cmd-gateway 이름 — 토픽 규칙 dmz/broker/acl 그대로)에 붙인다. 그 브로커에는 실제 공장 쪽 브리지가
    공장 브로커(ot-broker)와 이어 붙어 있다(conftest PlantMqtt) — 다리 둘이 이어졌다고 올라올 때까지 기다린다."""
    from conftest import until
    monkeypatch.setenv('CMD_FINGERPRINT_KEY', KEY)
    monkeypatch.setenv('MQTT_HOST', brokers.mqtt[0])
    monkeypatch.setenv('MQTT_PORT', str(brokers.mqtt[1]))
    import gw.main as main
    main = importlib.reload(main)
    main.link.start()
    until(lambda: main.link.healthy(), f'관문이 테스트 DMZ 브로커에 붙어 브리지의 다리 상태를 받지 못했다({main.link.health()})', 60)
    yield main
    main.link.client.disconnect()
    main.link.stop()


def _cmd(**change):
    exp = (datetime.now(timezone.utc) + timedelta(seconds=120)).isoformat()
    return dict({'cmdId': 'CMD-1', 'asset': 'HYD-01', 'incident': 'INC-1', 'source': 'HITL', 'approvedBy': 'user:kim-op',
                 'approvalId': 'APR-1', 'expiresAt': exp, 'actions': [{'code': 'FAN_SET', 'fan_pct': 100}]}, **change)


def _status(gw, asset_key, body):
    gw._on_message(None, SimpleNamespace(topic=f'plant/{asset_key}/status', payload=json.dumps(body).encode(), retain=True))


def test_통과한_명령은_명령_전체를_실은_CMD_FORWARDED로_적는다(live_gw):
    gw = live_gw
    cmd = _cmd()
    gw.gw.record_approval(gw.gstate, {'actor': 'process', 'event': schemas.CMD_APPROVAL_LEDGER_EVENT,
                                      'detail': schemas.approval_ledger_record(cmd, KEY)})
    _status(gw, 'hyd01', {'t': '2026-10-30T05:00:00Z', 'mode': 'REMOTE_AUTO', 'state': 'RUN'})
    prod = KafkaRecorder()
    d = asyncio.run(gw.handle_command(prod, cmd))
    (audit,) = prod.of(topics.K_AUDIT)
    assert d.ok and (audit['event'], audit['detail']['command']) == ('CMD_FORWARDED', cmd)
    assert schemas.audit_record(audit) and not schemas.validate_action_cmd(audit['detail']['command'])


def test_모드_거절은_원인과_학생_문장을_싣는다(gw):
    """G3b-9: 거절이 audit 에만 영문으로 남고 process 는 30초 뒤 「응답 없음」이었다 — 이제 그 기록에 학생 문장이 있다."""
    cmd = _cmd()
    gw.gw.record_approval(gw.gstate, {'actor': 'process', 'event': schemas.CMD_APPROVAL_LEDGER_EVENT,
                                      'detail': schemas.approval_ledger_record(cmd, KEY)})
    _status(gw, 'hyd01', {'t': '2026-10-30T05:00:00Z', 'mode': 'REMOTE_MANUAL', 'state': 'RUN'})
    prod = KafkaRecorder()
    asyncio.run(gw.handle_command(prod, cmd))
    (audit,) = prod.of(topics.K_AUDIT)
    assert (audit['event'], audit['detail']['check'], audit['incident']) == ('CMD_REJECTED', 'MODE', 'INC-1')
    assert '원격 자동' in audit['detail']['reason_text'] and schemas.audit_record(audit)


@pytest.mark.parametrize('sent', [_cmd(actions=[{'code': 'FAN_SET'}]), 'garbage', {'cmdId': 7, 'incident': ['x']}])
def test_형식이_틀린_명령도_감사_기록이_남는다(gw, sent):
    prod = KafkaRecorder()
    d = asyncio.run(gw.handle_command(prod, sent))
    (audit,) = prod.of(topics.K_AUDIT)
    assert (d.check, audit['detail']['check']) == ('SCHEMA', 'SCHEMA') and schemas.audit_record(audit)


@pytest.mark.parametrize('topic, payload, known', [
    ('plant/hyd01/status', {'t': '2026-10-30T05:00:00Z', 'mode': 'LOCAL', 'state': 'RUN', 'asset': 'HYD-02'}, False),  # 다른 설비 이름
    ('plant/hyd01/status', [1], False),                                         # G3b-1: AttributeError 로 루프가 끝났다
    ('plant/hyd01/status', b'\xff', False),                                     # G3b-1: UnicodeDecodeError
    ('plant/hyd01/status', {'t': '2026-10-30T05:00:00Z', 'mode': 'LOCAL', 'state': 'RUN'}, True),
])
def test_상태는_토픽의_설비로만_기억하고_틀린_상태는_센다(gw, topic, payload, known):
    raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    gw._on_message(None, SimpleNamespace(topic=topic, payload=raw, retain=False))
    assert ('HYD-01' in gw.gstate.last_status) is known and gw.state['malformed'] == (0 if known else 1)


def test_경보는_경보판으로_계약_밖_경보는_센다(live_gw):
    gw = live_gw
    asyncio.run(gw.relay_alert({'alertId': 'A1', 'asset': 'HYD-03', 'pattern': 'FAN_VIBRATION', 'name': '팬 진동 상승',
                                'severity': 'HIGH', 'state': 'RAISE', 't': '2026-10-30T05:00:00Z', 'evidence': {}}))
    asyncio.run(gw.relay_alert({'asset': 'HYD-03', 'state': 'RAISE'}))
    assert gw.board.display('HYD-03')['display_text'] == '경보 1건 · 팬 진동 상승' and gw.state['malformed'] == 1
    assert (gw.state['alerts_relayed'], gw.state['alert_relay_failed']) == (1, 0)


def test_검사를_통과해도_MQTT_가_명령을_받지_않으면_보냄이_아니라_그_까닭의_거절로_적는다(gw):
    """G3b-14: 연결이 끊긴 채 publish 가 거짓인데 CMD_FORWARDED 로 적어 process 는 30초 응답 없음을 기다렸다."""
    cmd = _cmd()
    gw.gw.record_approval(gw.gstate, {'actor': 'process', 'event': schemas.CMD_APPROVAL_LEDGER_EVENT,
                                      'detail': schemas.approval_ledger_record(cmd, KEY)})
    _status(gw, 'hyd01', {'t': '2026-10-30T05:00:00Z', 'mode': 'REMOTE_AUTO', 'state': 'RUN'})
    prod = KafkaRecorder()
    d = asyncio.run(gw.handle_command(prod, cmd))                 # 이 관문은 브로커에 붙지 않았다
    (audit,) = prod.of(topics.K_AUDIT)
    assert (d.ok, audit['event'], audit['detail']['check'], audit['detail']['cmdId']) == (False, 'CMD_REJECTED', 'MQTT', 'CMD-1')
    assert '설비 통신(MQTT)' in audit['detail']['reason_text'] and (gw.state['forwarded'], gw.state['rejected']) == (0, 1)
    assert schemas.audit_record(audit)


def test_MQTT_가_경보판을_받지_않으면_전달로_세지_않고_실패를_센다(gw):
    asyncio.run(gw.relay_alert({'alertId': 'A1', 'asset': 'HYD-03', 'pattern': 'FAN_VIBRATION', 'name': '팬 진동 상승',
                                'severity': 'HIGH', 'state': 'RAISE', 't': '2026-10-30T05:00:00Z', 'evidence': {}}))
    assert (gw.state['alerts_relayed'], gw.state['alert_relay_failed']) == (0, 1)


def test_끊긴_동안의_경보판은_다시_붙으면_올리고_못_보냄으로_적은_명령은_올리지_않는다(monkeypatch):
    """끊긴 동안: 명령은 「못 보냄」으로 닫혔으므로 뒤늦게 설비에 닿으면 안 되고(06-3), 경보판은 지금 상태이므로 다시 붙으면 올라가야 한다."""
    from conftest import MqttRecorder, until
    broker = MqttRecorder(retained=MqttRecorder.BRIDGE_UP)
    monkeypatch.setenv('CMD_FINGERPRINT_KEY', KEY)
    monkeypatch.setenv('MQTT_HOST', '127.0.0.1')
    monkeypatch.setenv('MQTT_PORT', str(broker.port))
    import gw.main as main
    gw = importlib.reload(main)
    cmd = _cmd()
    gw.gw.record_approval(gw.gstate, {'actor': 'process', 'event': schemas.CMD_APPROVAL_LEDGER_EVENT,
                                      'detail': schemas.approval_ledger_record(cmd, KEY)})
    _status(gw, 'hyd01', {'t': '2026-10-30T05:00:00Z', 'mode': 'REMOTE_AUTO', 'state': 'RUN'})
    prod = KafkaRecorder()
    assert asyncio.run(gw.handle_command(prod, cmd)).check == 'MQTT'
    asyncio.run(gw.relay_alert({'alertId': 'A1', 'asset': 'HYD-03', 'pattern': 'FAN_VIBRATION', 'name': 'fan',
                                'severity': 'HIGH', 'state': 'RAISE', 't': '2026-10-30T05:00:00Z', 'evidence': {}}))
    asyncio.run(gw.relay_alert({'alertId': 'A1', 'asset': 'HYD-03', 'pattern': 'FAN_VIBRATION', 'name': 'fan',
                                'severity': 'HIGH', 'state': 'CLEAR', 't': '2026-10-30T05:01:00Z', 'evidence': {}}))
    broker.serve()
    gw.link.start()
    try:
        until(lambda: broker.published, '다시 붙은 뒤 경보판')
        until(lambda: not gw.unsent_boards, '올리지 못한 경보판 비우기')
    finally:
        gw.link.stop()
    ((topic, body),) = broker.published
    assert topic == 'plant/hyd03/alert' and json.loads(body)['count'] == 0      # 마지막 판(해제) 하나만, 명령 토픽은 없음


def test_브리지가_끊겼다_이어지면_이미_올린_경보판도_다시_올린다(monkeypatch):
    """DMZ 브로커에 붙은 채 공장 쪽 브리지만 끊긴 동안: 명령은 「못 보냄」이고, 길이 다시 이어지면 설비마다 지금 경보판을 다시 올린다 —
    그 사이 다시 켜진 브로커가 보존해 둔 판을 잃었어도 운전 화면과 관문의 기억이 맞는다."""
    from conftest import MqttRecorder, until
    broker = MqttRecorder(retained=MqttRecorder.BRIDGE_UP)
    monkeypatch.setenv('CMD_FINGERPRINT_KEY', KEY)
    monkeypatch.setenv('MQTT_HOST', '127.0.0.1')
    monkeypatch.setenv('MQTT_PORT', str(broker.port))
    import gw.main as main
    gw = importlib.reload(main)
    raise_ = {'alertId': 'A1', 'asset': 'HYD-03', 'pattern': 'FAN_VIBRATION', 'name': 'fan', 'severity': 'HIGH', 'state': 'RAISE',
              't': '2026-10-30T05:00:00Z', 'evidence': {}}
    broker.serve()
    gw.link.start()
    try:
        until(gw.link.healthy, '관문이 붙고 다리 상태를 받는다')
        asyncio.run(gw.relay_alert(raise_))
        until(lambda: len(broker.published) == 1, '경보판 한 번')
        broker.send('bridge/ot/dmz', '0')
        until(lambda: not gw.link.healthy(), '브리지가 끊긴 것을 안다')
        cmd = _cmd()
        gw.gw.record_approval(gw.gstate, {'actor': 'process', 'event': schemas.CMD_APPROVAL_LEDGER_EVENT,
                                          'detail': schemas.approval_ledger_record(cmd, KEY)})
        _status(gw, 'hyd01', {'t': '2026-10-30T05:00:00Z', 'mode': 'REMOTE_AUTO', 'state': 'RUN'})
        prod = KafkaRecorder()
        assert asyncio.run(gw.handle_command(prod, cmd)).check == 'MQTT'
        assert gw.health()['ot_bridge'] is False and gw.health()['ot_bridge_legs'] == {'broker': True, 'dmz': False}
        broker.send('bridge/ot/dmz', '1')
        until(lambda: len(broker.published) == 2, '길이 이어진 뒤 경보판을 다시 올린다')
    finally:
        gw.link.stop()
    assert [topic for topic, _ in broker.published] == ['plant/hyd03/alert'] * 2          # 명령 토픽은 없다
    assert [json.loads(body)['count'] for _, body in broker.published] == [1, 1]


def test_지문_키가_없으면_관문이_켜지지_않는다(monkeypatch):
    monkeypatch.delenv('CMD_FINGERPRINT_KEY', raising=False)
    sys.modules.pop('gw.main', None)
    with pytest.raises(ValueError, match='CMD_FINGERPRINT_KEY'):
        importlib.import_module('gw.main')
    monkeypatch.setenv('CMD_FINGERPRINT_KEY', KEY)
    importlib.import_module('gw.main')
