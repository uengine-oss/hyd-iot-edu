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
    return dict({'cmdId': 'CMD-1', 'asset': 'HYD-01', 'incident': 'INC-1', 'source': 'HITL', 'approvedBy': 'user:me',
                 'approvalId': 'APR-1', 'expiresAt': exp, 'actions': [{'code': 'FAN_SET', 'fan_pct': 100}]}, **change)


def _now():
    """설비가 지금 보낸 상태의 시각 — 관문은 낡은 상태(STATUS_MAX_AGE_S 초 넘음)로는 명령을 넘기지 않는다."""
    return datetime.now(timezone.utc).isoformat()


def _status(gw, asset_key, body):
    gw._on_message(None, SimpleNamespace(topic=f'plant/{asset_key}/status', payload=json.dumps(body).encode(), retain=True))


def test_통과한_명령은_명령_전체를_실은_CMD_FORWARDED로_적는다(live_gw):
    gw = live_gw
    cmd = _cmd()
    gw.gw.record_approval(gw.gstate, {'actor': 'process', 'event': schemas.CMD_APPROVAL_LEDGER_EVENT,
                                      'detail': schemas.approval_ledger_record(cmd, KEY)})
    _status(gw, 'hyd01', {'t': _now(), 'mode': 'REMOTE_AUTO', 'state': 'RUN'})
    prod = KafkaRecorder()
    d = asyncio.run(gw.handle_command(prod, cmd))
    (audit,) = prod.of(topics.K_AUDIT)
    assert d.ok and (audit['event'], audit['detail']['command']) == ('CMD_FORWARDED', cmd)
    assert schemas.audit_record(audit) and not schemas.validate_action_cmd(audit['detail']['command'])


def test_넘긴_명령이_다시_배달되면_설비로_다시_보내지도_거절로_적지도_않고_센다(live_gw):
    """06-8: 넘긴 명령이 한 번 더 배달되면(위치 커밋 전 리밸런스) 관문이 「중복 거절」(CMD_REJECTED)을 적었고, 처리 엔진은 자기 명령의 거절 기록을
    받으면 처리 건을 거절로 닫는다 — 설비가 실행한 명령인데도. 다시 배달된 같은 명령은 기록 없이 버리고 건강 상태에 센다."""
    gw = live_gw
    cmd = _cmd(cmdId='CMD-AGAIN', approvalId='APR-AGAIN')
    gw.gw.record_approval(gw.gstate, {'actor': 'process', 'event': schemas.CMD_APPROVAL_LEDGER_EVENT,
                                      'detail': schemas.approval_ledger_record(cmd, KEY)})
    _status(gw, 'hyd01', {'t': _now(), 'mode': 'REMOTE_AUTO', 'state': 'RUN'})
    prod = KafkaRecorder()
    first = asyncio.run(gw.handle_command(prod, cmd))
    again = asyncio.run(gw.handle_command(prod, cmd))
    assert first.ok and (again.ok, again.check) == (False, gw.gw.REDELIVERED)
    assert [a['event'] for a in prod.of(topics.K_AUDIT)] == ['CMD_FORWARDED'], '다시 배달된 명령에 거절 기록을 적었다'
    assert (gw.state['forwarded'], gw.state['rejected'], gw.state['redelivered']) == (1, 0, 1)


def test_모드_거절은_원인과_학생_문장을_싣는다(gw):
    """G3b-9: 거절이 audit 에만 영문으로 남고 process 는 30초 뒤 「응답 없음」이었다 — 이제 그 기록에 학생 문장이 있다."""
    cmd = _cmd()
    gw.gw.record_approval(gw.gstate, {'actor': 'process', 'event': schemas.CMD_APPROVAL_LEDGER_EVENT,
                                      'detail': schemas.approval_ledger_record(cmd, KEY)})
    _status(gw, 'hyd01', {'t': _now(), 'mode': 'REMOTE_MANUAL', 'state': 'RUN'})
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


def test_가상_설비_밖의_경보는_계약에_맞아도_공장_경보판에_올리지_않는다(live_gw):
    """S-A: 경보 기록은 바깥 원천(학생 시스템 · 실설비)의 설비 이름도 받는다 — 공장 표시판(plant/{a}/alert)에는 그 설비가 없어 올리지 않는다
    (계약 밖 경보로 세지도 않는다)."""
    gw = live_gw
    asyncio.run(gw.relay_alert({'alertId': 'APU-1', 'asset': 'APU-01', 'pattern': 'APU_AIR_LEAK', 'name': '공기 누설 의심',
                                'severity': 'HIGH', 'state': 'RAISE', 't': '2026-10-30T05:00:00Z', 'evidence': {}}))
    assert 'APU-01' not in gw.board.active and gw.state['malformed'] == 0 and gw.state['alerts_relayed'] == 0


def test_검사를_통과해도_MQTT_가_명령을_받지_않으면_보냄이_아니라_그_까닭의_거절로_적는다(gw):
    """G3b-14: 연결이 끊긴 채 publish 가 거짓인데 CMD_FORWARDED 로 적어 process 는 30초 응답 없음을 기다렸다."""
    cmd = _cmd()
    gw.gw.record_approval(gw.gstate, {'actor': 'process', 'event': schemas.CMD_APPROVAL_LEDGER_EVENT,
                                      'detail': schemas.approval_ledger_record(cmd, KEY)})
    _status(gw, 'hyd01', {'t': _now(), 'mode': 'REMOTE_AUTO', 'state': 'RUN'})
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
    _status(gw, 'hyd01', {'t': _now(), 'mode': 'REMOTE_AUTO', 'state': 'RUN'})
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
        _status(gw, 'hyd01', {'t': _now(), 'mode': 'REMOTE_AUTO', 'state': 'RUN'})
        prod = KafkaRecorder()
        assert asyncio.run(gw.handle_command(prod, cmd)).check == 'MQTT'
        assert gw.health()['ot_bridge'] is False and gw.health()['ot_bridge_legs'] == {'broker': True, 'dmz': False}
        broker.send('bridge/ot/dmz', '1')
        until(lambda: len(broker.published) == 2, '길이 이어진 뒤 경보판을 다시 올린다')
    finally:
        gw.link.stop()
    assert [topic for topic, _ in broker.published] == ['plant/hyd03/alert'] * 2          # 명령 토픽은 없다
    assert [json.loads(body)['count'] for _, body in broker.published] == [1, 1]


def _poison_run(brokers, monkeypatch, poisoned, pause_s=0, on_blocked=None):
    """관문의 명령 고리(run)를 이 자리의 실제 브로커(Redpanda)에 붙여, 이 시험만의 명령 · 경보 토픽(관문과 같은 차례 — action.cmd 가 alerts 앞)에
    poisoned 토픽마다 [좋은 기록, 읽을 수 없는 기록, 좋은 기록]을 넣고 돌린다. 읽을 수 없는 기록은 snappy 로 묶은 기록이고, 바깥인 「압축을 풀
    라이브러리가 없음」만 이 프로세스에서 만든다(2026-10 관문 이미지가 그랬다). 고리가 그 기록에서 처음 멈추면 브로커 컨테이너를 pause_s 초 멈춘다
    (바쁜 PC 에서 브로커가 늦게 답하는 자리 — 2026-11-24 docker-desktop 부하 24~27). 그 뒤 5초 넘게 건강 상태의 막힘(consumer_blocked)을 지켜보고,
    처음 보면 on_blocked() 를 부른다. 깨진 기록을 넘긴 뒤 다른 토픽에 기록을 하나 더 넣는다.
    → (관문 모듈, 처리한 기록 id, 바라던 id, 지켜보는 동안 본 막힘 까닭들)."""
    import subprocess
    import uuid
    import aiokafka.codec
    from aiokafka import AIOKafkaConsumer, AIOKafkaProducer, TopicPartition
    from aiokafka.admin import AIOKafkaAdminClient, NewTopic
    monkeypatch.setenv('CMD_FINGERPRINT_KEY', KEY)
    monkeypatch.setenv('KAFKA_BOOTSTRAP', brokers.kafka)
    import gw.main as main
    gw = importlib.reload(main)
    run_id = uuid.uuid4().hex[:8]
    names = {'cmd': f'test-{run_id}-{topics.K_CMD}', 'alerts': f'test-{run_id}-{topics.K_ALERTS}'}
    assert sorted(names.values()) == [names['cmd'], names['alerts']]
    monkeypatch.setattr(topics, 'K_CMD', names['cmd'])            # 이 시험만의 토픽(관문의 묶음 이름 cmd-gateway 는 그대로)
    monkeypatch.setattr(topics, 'K_ALERTS', names['alerts'])
    box = brokers.kafka_box.name

    def record(kind, n):
        if kind == 'cmd':                                            # 승인 기록이 없어 거절로 적힌다(결정 기록에 남는다)
            return _cmd(cmdId=f'CMD-{n}', approvalId=f'APR-{n}')
        return {'alertId': f'A-{n}', 'asset': 'HYD-03', 'pattern': 'FAN_VIBRATION', 'name': f'A-{n}', 'severity': 'HIGH', 'state': 'RAISE',
                't': _now(), 'evidence': {}}
    first = {kind: [record(kind, 1), record(kind, 'POISON'), record(kind, 2)] for kind in poisoned}
    later = {kind: [record(kind, 3)] for kind in names if kind not in poisoned}      # 깨진 기록을 넘긴 뒤 다른 토픽에 오는 기록

    def key(value):
        return value.get('cmdId') or value.get('alertId')

    def seen():
        return {'cmd': {d['cmdId'] for d in gw.decisions}, 'alerts': set(gw.board.active.get('HYD-03', {}))}

    def ids(batch):
        return {kind: {key(v) for v in values if 'POISON' not in key(v)} for kind, values in batch.items()}

    async def produce(batch):
        plain = AIOKafkaProducer(bootstrap_servers=brokers.kafka, value_serializer=lambda v: json.dumps(v).encode())
        snappy = AIOKafkaProducer(bootstrap_servers=brokers.kafka, value_serializer=lambda v: json.dumps(v).encode(), compression_type='snappy')
        await plain.start()
        await snappy.start()
        try:
            for kind, values in batch.items():
                for value in values:
                    await (snappy if 'POISON' in key(value) else plain).send_and_wait(names[kind], value)
        finally:
            await plain.stop()
            await snappy.stop()

    async def prepare():
        admin = AIOKafkaAdminClient(bootstrap_servers=brokers.kafka)
        await admin.start()
        try:
            await admin.create_topics([NewTopic(name, num_partitions=1, replication_factor=1) for name in names.values()])
        finally:
            await admin.close()
        start = AIOKafkaConsumer(bootstrap_servers=brokers.kafka, group_id='cmd-gateway', enable_auto_commit=False)
        start.assign([TopicPartition(name, 0) for name in names.values()])
        await start.start()
        try:                                                         # 관문이 여기까지 읽은 묶음(처음부터 읽게)
            await start.commit({TopicPartition(name, 0): 0 for name in names.values()})
        finally:
            await start.stop()
        await produce(first)

    async def docker(*args):
        proc = await asyncio.create_subprocess_exec('docker', *args, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
        _, err = await proc.communicate()
        assert proc.returncode == 0, f'docker {" ".join(args)}: {err.decode("utf-8", "replace")[-300:]}'

    async def until_seen(wanted, seconds=90):
        deadline = asyncio.get_running_loop().time() + seconds
        while asyncio.get_running_loop().time() < deadline:
            if all(seen()[kind] >= values for kind, values in wanted.items()):
                return
            await asyncio.sleep(0.2)

    blocked = []

    async def slow_broker():
        deadline = asyncio.get_running_loop().time() + 90             # 시한이 없으면 회귀(고리가 깨진 기록에서 멈추지 않음) 때 실패 대신 끝없이 기다린다
        while not gw.state.get('consumer_errors'):                   # 고리가 깨진 기록에서 처음 멈춘 순간 — 탐침이 도는 동안
            if asyncio.get_running_loop().time() >= deadline:
                raise AssertionError(f'관문의 소비 고리가 90초 동안 깨진 기록에서 한 번도 멈추지 않았다(consumer_errors 없음) — 깨진 기록이 '
                                     f'토픽에 들어갔는지 · 고리가 도는지 본다: {gw.state}')
            await asyncio.sleep(0.002)
        if pause_s:
            await docker('pause', box)
        try:
            deadline = asyncio.get_running_loop().time() + max(pause_s, 5)
            while asyncio.get_running_loop().time() < deadline:
                if gw.state.get('consumer_blocked'):
                    if not blocked and on_blocked:
                        on_blocked()
                    blocked.append(gw.state['consumer_blocked'])
                await asyncio.sleep(0.01)
        finally:
            if pause_s:
                await docker('unpause', box)

    async def consume():
        task = asyncio.create_task(gw.run(KafkaRecorder()))
        slow = asyncio.create_task(slow_broker())
        try:
            await until_seen(ids(first))
            await slow
            await produce(later)
            await until_seen(ids(later))
            await asyncio.sleep(3)                                   # 고리가 같은 기록에서 다시 시작하지 않는지 조금 더 본다
        finally:
            for running in (task, slow):
                running.cancel()
            await asyncio.gather(task, slow, return_exceptions=True)
    asyncio.run(prepare())
    monkeypatch.setattr(aiokafka.codec, 'has_snappy', lambda: False)    # 관문 쪽에는 snappy 를 풀 라이브러리가 없다
    try:
        asyncio.run(consume())
    finally:                                                         # 끊긴 시험이 이 자리의 브로커를 멈춘 채 남기지 않는다
        paused = subprocess.run(['docker', 'inspect', '-f', '{{.State.Paused}}', box], capture_output=True, text=True).stdout.strip()
        if paused == 'true':
            subprocess.run(['docker', 'unpause', box], capture_output=True)
    wanted = {kind: ids(first).get(kind, set()) | ids(later).get(kind, set()) for kind in names}
    return gw, seen(), wanted, blocked


@pytest.mark.parametrize('poisoned', [('alerts',), ('cmd',), ('alerts', 'cmd')], ids=['경보 토픽', '명령 토픽', '둘 다'])
def test_읽을_수_없는_기록은_브로커가_늦어도_그_토픽에서만_한_번_건너뛰고_명령_고리는_뒤의_기록으로_간다(brokers, monkeypatch, poisoned):
    """06-5 · A148: 관문의 명령 고리가 읽을 수 없는 기록을 만나면 그 기록이 든 토픽에서만 한 칸 넘기고, 같은 토픽의 뒤 기록과 다른 토픽의 기록은
    하나도 잃지 않으며, 같은 기록에서 다시 멈추지 않는다. 전에는 그 기록을 다시 읽어 보는 탐침이 0.5초 안에 답을 받지 못하면(브로커가 늦음 —
    여기서는 3초 멈춤) 「읽힌다」로 보아 아무것도 넘기지 않았고, 고리가 같은 기록에서 다시 시작했다(건강 표시는 정상)."""
    gw, seen, wanted, blocked = _poison_run(brokers, monkeypatch, poisoned, pause_s=3)
    state = {k: gw.state.get(k) for k in ('consumer_errors', 'poison_skipped', 'consumer_last_error', 'consumer_blocked')}
    assert sorted(d['cmdId'] for d in gw.decisions) == sorted(wanted['cmd']), state       # 명령마다 한 번 — 잃지도 겹치지도 않는다
    assert seen['alerts'] == wanted['alerts'], state
    assert state['poison_skipped'] == len(poisoned) and 1 <= state['consumer_errors'] <= len(poisoned), state   # 깨진 기록마다 한 번만 멈췄다
    assert not blocked and not state['consumer_blocked'], (blocked, state)


def test_브로커가_탐침_시간을_넘게_답하지_않으면_막힘을_건강에_알리고_다시_읽으면_푼다(brokers, monkeypatch):
    """읽을 수 없는 기록을 넘기려는 탐침이 정한 시간(PROBE_S) 안에 브로커의 답을 받지 못하면 조용히 「읽힌다」로 보지 않고 까닭을 건강
    표시(consumer_blocked — /healthz 의 ok 를 끈다)에 남긴다. 「정한 시간 안에 답이 없음」은 그 시간을 1 ms 로 줄여 만들고, 막힘을 본 뒤 원래
    시간으로 되돌린다(브로커가 다시 답하는 자리) — 고리가 다시 시작해 그 기록을 넘기고 뒤 기록을 읽으며 막힘을 푼다."""
    from hydcommon import kafka
    usual = kafka.PROBE_S
    monkeypatch.setattr(kafka, 'PROBE_S', 0.001)
    gw, seen, wanted, blocked = _poison_run(brokers, monkeypatch, ('alerts',), on_blocked=lambda: setattr(kafka, 'PROBE_S', usual))
    state = {k: gw.state.get(k) for k in ('consumer_errors', 'poison_skipped', 'consumer_blocked')}
    assert blocked and 'did not answer within 0.001 s' in blocked[0] and '-action.cmd/0: ' in blocked[0], (blocked, state)   # 탐침 차례의 첫 파티션에서 시간이 다 됐다
    assert seen == wanted, state
    assert state['poison_skipped'] == 1 and not state['consumer_blocked'] and 'consumer_blocked' not in gw.health(), state


@pytest.mark.parametrize('loop', ['consumer_blocked', 'ledger_blocked'], ids=['명령_고리', '승인_장부_고리'])
def test_깨진_기록을_넘기지_못한_고리가_있으면_건강은_정상이_아니다(live_gw, loop):
    """깨진 기록 하나에서 고리가 멈춘 채 다시 시작만 되풀이해도 /healthz 가 정상이라 아무도 몰랐다 — 넘기지 못한 고리가 있으면 ok 가 아니다.
    관문은 실제 DMZ 브로커에 붙어 있다(live_gw — 다리 둘이 이어짐). Kafka 송신기가 붙은 뒤(_main 이 state["kafka"] 를 켠 뒤)의 자리."""
    gw = live_gw
    gw.state['kafka'] = True
    assert gw.health()['ok'] is True
    gw.state[loop] = "PoisonProbeError('alerts/0: the broker did not answer within 30 s …')"
    assert gw.health()['ok'] is False and gw.health()[loop].startswith('PoisonProbeError')


def test_지문_키가_없으면_관문이_켜지지_않는다(monkeypatch):
    monkeypatch.delenv('CMD_FINGERPRINT_KEY', raising=False)
    sys.modules.pop('gw.main', None)
    with pytest.raises(ValueError, match='CMD_FINGERPRINT_KEY'):
        importlib.import_module('gw.main')
    monkeypatch.setenv('CMD_FINGERPRINT_KEY', KEY)
    importlib.import_module('gw.main')
