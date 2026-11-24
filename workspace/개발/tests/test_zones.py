"""영역 경계 — compose.yaml 이 OT · DMZ · IT 를 망으로 나누고, 값이 올라오고 승인된 명령이 내려가는 길만 이어 두었는가. 그리고 그 길을 먼저 여는 쪽이 공장인가.

Docker 는 같은 망에 붙은 컨테이너끼리만 닿게 한다. 다만 PC 에 연 입구(compose ports)는 이 PC 의 Docker(엔진 29.9.3)가 다른 망의 컨테이너에도
그 포트 연결의 컨테이너 주소로 닿게 둔다(2026-11-24 실측 — PC 에 열지 않은 포트는 다른 망에서 막힌다). 그래서 「누가 누구에게 닿는가」는 compose 의
망 정의와 PC 에 연 입구로 정해지고, PC 에 여는 입구는 학생이 브라우저로 여는 화면으로 줄인다. 이 파일은 그 정의를 읽어 서비스 쌍마다 닿는지를 계산하고 아래를 판정한다(영역은 손으로 적은 표가 아니라 망에서 나온다 — ot-net 에
붙으면 OT, it-net 에 붙으면 IT, 경계 망에만 붙으면 DMZ).
  - 모든 서비스는 한 영역에만 있다.
  - OT 와 IT 는 서로 닿지 않는다. 하나뿐인 예외는 가상 설비 API 망(sim-net)이고 그 구성원은 정해져 있다(실습 조작의 길 — 브로커는 없다).
  - 공장 브로커(ot-broker)에는 OT 만 닿는다. 경계 망에 나와 있는 공장 쪽 부품은 공장 쪽 브리지(ot-bridge) 하나이고, IT 가 DMZ 경계 망에서 만나는 것은
    DMZ 와 IT 뿐이다.
  - 올라오는 길(설비 → 공장 브로커 → 브리지 → DMZ 브로커 → 수집 중계 → 이벤트 로그)과 내려가는 길(process → 이벤트 로그 → 명령 관문 →
    DMZ 브로커 → 브리지 → 공장 브로커 → 설비)이 이어져 있다.
  - 서비스가 환경 값 · 포털 길 표 · 감시 대상 · 브리지 설정으로 부르는 다른 서비스는 실제로 닿는 망에 있다(망을 나누다 길이 끊기지 않게).
  - PC 에 입구를 여는 것은 학생이 브라우저로 여는 화면 넷(포털 · 관제 화면 · 추이 화면 · 지식 그래프 브라우저 — ON_PC)뿐이다. 서비스 API ·
    이벤트 로그 · 시계열 저장소 · MCP 서버 · 브로커 셋은 PC 에 아무 입구도 열지 않는다(열면 공장 · DMZ 의 컨테이너가 IT 의 승인 API · 저장소로,
    IT 가 공장 안으로 곧장 닿는다). 선택 도구(profiles — 감시 · Kafka 화면)는 기본으로 뜨지 않는다. 브로커의 토픽 규칙은 test_ot_broker.py.
    compose 밖의 업무 DB(Supabase CLI)는 이 판정 밖이다 — CLI 가 업무 DB · 메일함 포트를 PC 의 모든 주소에 열어 다른 망에서도 닿는다(compose.yaml
    머리말 · 포털 「영역 경계」가 밝힌다).
  - 연결을 먼저 여는 쪽은 공장이다: DMZ 서비스와 같은 망에 붙인 실제 컨테이너에서 공장 쪽 컨테이너(공장 브로커 · 브리지)의 어느 입구로도 TCP 연결이
    열리지 않는다(이름으로도 주소로도). 같은 자리에서 DMZ 브로커로는 열린다(잰 것이 실제 연결임을 보인다). IT 망에 붙인 컨테이너에서는 공장 쪽
    어느 입구도, DMZ 브로커의 입구도 열리지 않는다. 주소로 재는 대상은 compose 와 똑같이 PC 에 입구를 열지 않은 복사본이다 — 이 자리의 두 브로커는
    PC 쪽 시험이 붙도록 안쪽 입구를 PC 에 열어, 그 주소로 재면 compose 가 아니라 시험 장치의 꼴을 잰다. 값과 명령이 브리지로 실제로 오가는지는 test_ot_bridge.py.
  - 시스템 구성 화면이 그리는 표(it/portal/www/layers.js 의 부품마다 nets · zone, 망 목록 NETS)가 compose 의 망 정의와 같다. 화면은 이 표로 부품을
    영역 띠와 망에 놓으므로, 표가 compose 와 어긋나면 그림이 실제와 다른 구조를 말한다.
"""
import json
import re
import subprocess

import pytest
import yaml

from conftest import CONTAINER_LABEL, CONTAINER_SITE, ROOT, ComposeContainer, _docker, _test_site, site_network

SERVICES = yaml.safe_load((ROOT / 'compose.yaml').read_text(encoding='utf8'))['services']
NETS = {name: set(svc.get('networks') or ()) for name, svc in SERVICES.items()}
OT_NET, IT_NET, BOUNDARY, SIM_NET = 'ot-net', 'it-net', {'ot-dmz-net', 'dmz-it-net'}, 'sim-net'
OT = {s for s, n in NETS.items() if OT_NET in n}
IT = {s for s, n in NETS.items() if IT_NET in n}
DMZ = {s for s, n in NETS.items() if n and n <= BOUNDARY}
SIM_API = {'plant-sim': {'process', 'portal'}}          # 가상 설비 API(:8000)를 부르는 IT 서비스 — 결함 주입 · 정비 수행 모사 · 같은 출처 길
PLANT_BROKER, PLANT_BRIDGE, DMZ_BROKER = 'ot-broker', 'ot-bridge', 'dmz-broker'
BROKER_CONF = {PLANT_BROKER: 'ot/broker/mosquitto.conf', PLANT_BRIDGE: 'ot/bridge/mosquitto.conf', DMZ_BROKER: 'dmz/broker/mosquitto.conf'}
#: 기본 서비스 가운데 PC 에 입구를 여는 것과 그 까닭 — 학생이 PC 브라우저로 여는 화면뿐이다. PC 에 연 입구는 다른 망의 컨테이너도 닿으므로(이 파일
#: 머리), 여기 있는 것은 공장 · DMZ · IT 어디서도 닿는다 — 포털 시스템 구성 화면의 「영역 경계」가 그 차이를 밝힌다(layers.js SYS_DIFFS). 시작 · 점검 ·
#: 개발 도구는 서비스를 포털의 같은 출처 길로 부른다(scripts/prepare_ports.service_url). 여기에 없는 기본 서비스가 PC 에 입구를 열면 걸린다
ON_PC = {
    'portal': '학생 화면 — 서비스 API 는 이 화면의 같은 출처 길 /svc/<서비스>/ 로만 부른다',
    'fuxa': '학생 · 강사가 PC 브라우저로 여는 관제 화면(운전 화면) — 현업은 공장 안에서 연다',
    'grafana': '추이 화면(포털 실시간 모니터링의 추이 링크)',
    'neo4j': '지식 그래프 브라우저(Neo4j Browser — 브라우저가 접속 포트 7687 로 그래프에 붙는다)',
}


def shared(a, b):
    return NETS[a] & NETS[b]


def members(net):
    return {s for s, n in NETS.items() if net in n}


def test_모든_서비스는_한_영역에만_있다():
    zones = {s: [z for z, group in (('OT', OT), ('DMZ', DMZ), ('IT', IT)) if s in group] for s in SERVICES}
    assert {s: z for s, z in zones.items() if len(z) != 1} == {}
    assert DMZ == {DMZ_BROKER, 'connect-ingest', 'cmd-gateway'}       # 영역을 넘는 일은 수집 중계 · 명령 관문만 하고, DMZ 브로커는 공장이 접속해 오는 자리다


def test_업무_DB_망에는_IT_서비스만_있고_업무_DB를_부르는_서비스는_모두_그_망_안의_이름으로_부른다():
    """업무 DB(Supabase)는 IT 영역의 업무 시스템이다 — 그 망(business-db)에 OT · DMZ 서비스는 없다. 업무 DB · 메일함을 부르는 서비스는 호스트에
    연 포트로 돌지 않고 그 망 안의 이름(db.supabase.internal · inbucket)으로 부른다(2026-11-24: 호스트 중계가 PC 전체에서 몇 초씩 멎어 승인이 503)."""
    env = {s: {k: str(v) for k, v in (svc.get('environment') or {}).items()} for s, svc in SERVICES.items()}
    users = {s for s, e in env.items() if any('@db.supabase.internal:5432/' in v or (k == 'SMTP_HOST' and v == 'inbucket') for k, v in e.items())}
    assert users and members('business-db') == users and users <= IT, (members('business-db'), users)
    assert [(s, k) for s, e in env.items() for k, v in e.items() if 'host.docker.internal' in v] == []


def test_OT와_IT는_가상_설비_API_망_말고는_닿지_않는다():
    touching = {(o, i): shared(o, i) for o in OT for i in IT if shared(o, i)}
    assert touching == {(o, i): {SIM_NET} for o, callers in SIM_API.items() for i in callers}
    assert members(SIM_NET) == set(SIM_API) | {i for callers in SIM_API.values() for i in callers}


def test_공장_브로커에는_OT만_닿고_경계_망에_나온_공장_쪽_부품은_브리지_하나다():
    assert {s for s in SERVICES if s != PLANT_BROKER and shared(s, PLANT_BROKER)} == OT - {PLANT_BROKER}
    assert members('ot-dmz-net') == DMZ | {PLANT_BRIDGE}
    assert members('dmz-it-net') - DMZ <= IT and 'redpanda' in members('dmz-it-net')
    assert {(d, o) for d in DMZ for o in OT if shared(d, o)} == {(d, PLANT_BRIDGE) for d in DMZ}
    assert NETS[DMZ_BROKER] == {'ot-dmz-net'}                         # DMZ 브로커는 IT 쪽 경계 망에 나오지 않는다 — IT 에서는 어느 입구도 열리지 않는다(아래 실제 연결)


@pytest.mark.parametrize('path', [
    ['plant-sim', 'ot-broker', 'ot-bridge', 'dmz-broker', 'connect-ingest', 'redpanda', 'detector'],     # 값이 올라오는 길
    ['plant-sim', 'ot-broker', 'ot-bridge', 'dmz-broker', 'connect-ingest', 'redpanda', 'connect-sink'],
    ['process', 'redpanda', 'cmd-gateway', 'dmz-broker', 'ot-bridge', 'ot-broker', 'plant-sim'],         # 승인된 명령이 내려가는 길
    ['fuxa', 'ot-broker', 'plant-sim'],                                                                  # 운전 화면의 감시 · 수동 조작(OT 안)
])
def test_올라오는_길과_내려가는_길이_이어져_있다(path):
    assert [(a, b) for a, b in zip(path, path[1:]) if not shared(a, b)] == []


def _called(text):
    """글 안에서 `<서비스 이름>:<포트>` 로 불린 compose 서비스."""
    return {m[1] for m in re.finditer(r'(?<![\w.-])([a-z][a-z0-9-]*):\d+', str(text)) if m[1] in SERVICES}


def _calls():
    for name, svc in SERVICES.items():
        for key, value in (svc.get('environment') or {}).items():
            for target in _called(value) | ({value} if value in SERVICES else set()):
                yield name, target, f'environment {key}'
    for target in _called((ROOT / 'it/portal/nginx.conf').read_text(encoding='utf8')):
        yield 'portal', target, 'it/portal/nginx.conf 길 표'
    for target in _called((ROOT / 'it/prometheus/prometheus.yml').read_text(encoding='utf8')):
        yield 'prometheus', target, 'it/prometheus/prometheus.yml targets'
    for target in _called((ROOT / 'ot/bridge/mosquitto.conf').read_text(encoding='utf8')):
        yield PLANT_BRIDGE, target, 'ot/bridge/mosquitto.conf address'


def test_서비스가_부르는_서비스는_닿는_망에_있다():
    calls = [c for c in _calls() if c[0] != c[1]]
    assert {('cmd-gateway', DMZ_BROKER), ('connect-ingest', DMZ_BROKER), ('connect-ingest', 'redpanda'), ('portal', 'cmd-gateway'),
            ('agent', 'connect-ingest'), ('process', 'redpanda'), (PLANT_BRIDGE, PLANT_BROKER), (PLANT_BRIDGE, DMZ_BROKER),
            ('plant-sim', PLANT_BROKER)} <= {c[:2] for c in calls}             # 읽기가 비어 있지 않다(길 표 · 환경 값 · 브리지 설정을 실제로 읽었다)
    assert [c for c in calls if not shared(c[0], c[1])] == []
    assert [c for c in calls if c[1] == PLANT_BROKER and c[0] not in OT] == []      # 공장 브로커를 부르는 것은 공장 안의 것뿐이다


def _published(service):
    """compose 가 그 서비스에서 PC 에 여는 컨테이너 쪽 포트들."""
    return {int(str(line).rsplit(':', 1)[1]) for line in SERVICES[service].get('ports') or []}


def _listeners(service):
    """브로커 설정 파일의 입구마다 {포트: 그 입구의 설정 줄들} — per_listener_settings 이면 입구 줄 아래의 줄이 그 입구의 것이다."""
    found, current = {}, None
    for line in (ROOT / BROKER_CONF[service]).read_text(encoding='utf8').splitlines():
        words = line.split()
        if words and words[0] == 'listener':
            current = found.setdefault(int(words[1]), [])
        elif words and current is not None and not line.startswith('#'):
            current.append(line.strip())
    return found


def test_PC에_입구를_여는_기본_서비스는_학생이_여는_화면뿐이고_브로커_셋은_아무것도_열지_않는다():
    """2026-11-24: 서비스 API(8080 · 8090~8097 · 8195~8199 · 8000) · 이벤트 로그(19092 · 9644) · 시계열 저장소(5432) · 학생 구독 입구(1883 · 8083)를
    PC 에 열어 두어, 공장(plant-sim) 컨테이너에서 IT 의 승인 API · 이벤트 로그 · 저장소에 그 주소로 연결이 열렸다(실측). 기본 서비스 가운데 PC 에
    여는 것은 학생 화면 넷뿐이다."""
    opened = {s for s, spec in SERVICES.items() if _published(s) and not spec.get('profiles')}
    assert opened == set(ON_PC), sorted(opened ^ set(ON_PC))
    assert {s: _published(s) for s in (PLANT_BROKER, PLANT_BRIDGE, DMZ_BROKER) if _published(s)} == {}
    assert [s for s in ON_PC if s in OT] == ['fuxa']                  # 공장 쪽에서 PC 에 여는 것은 관제 화면 하나다


# ---------------------------------------------------------------- 연결을 먼저 여는 쪽은 공장이다(실제 연결)
PROBE_IMAGE = SERVICES[DMZ_BROKER]['image']               # 이미 받은 이미지(busybox nc 가 들어 있다)


def _addresses(box):
    """그 컨테이너가 붙은 망마다의 주소."""
    nets = json.loads(_docker('inspect', '-f', '{{json .NetworkSettings.Networks}}', box.name))
    return {net: info['IPAddress'] for net, info in nets.items()}


def _holders(opened):
    """열린 주소마다 그 순간 그 주소를 가진 컨테이너와 망(이 PC 의 모든 망) — 실패 글에 싣는 관측(2026-11-24 한 번, 열린 주소가 나중에 보니 다른
    시험 자리의 것이었다 — 그 순간의 주인을 남긴다)."""
    ips = {item.rsplit(':', 1)[0] for item in opened}
    found = {}
    for net in _docker('network', 'ls', '-q').split():
        info = json.loads(_docker('network', 'inspect', net))[0]
        for box in (info.get('Containers') or {}).values():
            ip = (box.get('IPv4Address') or '').split('/')[0]
            if ip in ips:
                found.setdefault(ip, []).append(f"{box.get('Name')} @ {info['Name']}")
    return found


def _opens_from(nets, targets):
    """nets(compose 망 이름들)에 붙은 새 컨테이너 안에서 (주소, 포트)마다 TCP 연결을 열어 본다 → 열린 것들. 이 자리에 아직 없는 망(it-net —
    이 자리의 MQTT 셋은 IT 망에 붙지 않는다)은 이 자리의 꼬리표를 달아 만든다(자리 정리가 지운다)."""
    for net in nets:
        if not _docker('network', 'ls', '--filter', f'name=^{site_network(net)}$', '--format', '{{.Name}}').strip():
            _docker('network', 'create', '--label', f'{CONTAINER_SITE}={_test_site()}', site_network(net))
    script = '; '.join(f'nc -z -w 2 {host} {port} 2>/dev/null && echo {host}:{port}' for host, port in targets) + '; true'
    name = _docker('create', '--label', f'{CONTAINER_LABEL}=probe', '--label', f'{CONTAINER_SITE}={_test_site()}', '--entrypoint', 'sh',
                   '--network', site_network(nets[0]), PROBE_IMAGE, '-c', script).strip()
    try:
        for net in nets[1:]:
            _docker('network', 'connect', site_network(net), name)
        return set(_docker('start', '-a', name).split())
    finally:
        _docker('rm', '-f', '-v', name)                 # -v: 탐침 이미지(mosquitto)의 익명 볼륨까지


@pytest.fixture(scope='module')
def compose_exact(plant_mqtt):
    """두 브로커의 복사본 — compose 서비스 그대로(이미지 · 설정 · 망)이고, PC 에 여는 입구도 compose 의 ports 와 똑같다(지금은 둘 다 없음).
    같은 망에 붙되 서비스 이름은 달지 않아, 이 자리의 브리지 · 시험은 원래 컨테이너를 그대로 쓴다. 설정의 입구가 모두 실제로 듣기 시작한 뒤에
    돌려준다(듣기 전에 재면 닫혀 있는 것을 「막혔다」로 읽는다). 브리지는 compose 에서도 이 자리에서도 PC 에 입구를 열지 않아 원래 것을 잰다."""
    boxes = {}
    for service in (PLANT_BROKER, DMZ_BROKER):
        inside = sorted(_published(service))
        box = ComposeContainer(service, inside[0] if inside else None, extra_ports=inside[1:], networked=True, alias=False,
                               name=f'hyd-test-{service}-compose-{_test_site()}')
        box.wait(lambda: _listening(box.name, service), f'{service} 복사본의 입구 {sorted(_listeners(service))}가 듣는다', 60)
        boxes[service] = box
    return boxes


def _listening(name, service):
    """그 컨테이너 안에서 설정의 입구가 모두 연결을 받는가(컨테이너가 아직 뜨는 중이면 거짓)."""
    script = ' && '.join(f'nc -z 127.0.0.1 {port}' for port in _listeners(service))
    return subprocess.run(['docker', 'exec', name, 'sh', '-c', script], capture_output=True, timeout=30).returncode == 0


def _targets(service, box):
    """그 컨테이너의 모든 주소 × 설정의 모든 입구."""
    return [(host, port) for host in sorted(_addresses(box).values()) for port in _listeners(service)]


def test_DMZ_자리에서_공장_쪽_어느_입구로도_연결이_열리지_않는다(plant_mqtt, compose_exact):
    """DMZ 서비스(명령 관문)와 같은 망에 붙인 컨테이너에서 공장 브로커 · 브리지의 모든 입구로 연결을 열어 본다 — 이름으로(이 자리의 컨테이너 —
    공장 브로커가 경계 망에 붙어 있으면 이름 ot-broker 로 1883 이 열린다), 그리고 compose 와 똑같이 입구를 연 컨테이너가 가진 모든 주소로(공장
    브로커가 PC 에 입구를 열면 그 주소로 그 입구가 열린다)."""
    dmz_nets = sorted(NETS['cmd-gateway'] & {'ot-dmz-net'}) or pytest.fail('명령 관문이 경계 망 ot-dmz-net 에 없다')
    by_name = [(service, port) for service in (PLANT_BROKER, PLANT_BRIDGE) for port in _listeners(service)]
    by_address = _targets(PLANT_BROKER, compose_exact[PLANT_BROKER]) + _targets(PLANT_BRIDGE, plant_mqtt.bridge_box)
    assert len(by_address) >= 2, by_address                                              # 두 컨테이너의 실제 주소를 읽었다
    control = (DMZ_BROKER, 1883)
    opened = _opens_from(dmz_nets, by_name + by_address + [control])
    assert opened == {f'{control[0]}:{control[1]}'}, (opened, _holders(opened))


def test_IT_자리에서는_공장_쪽도_DMZ_브로커도_열리지_않는다(plant_mqtt, compose_exact):
    """IT 망에 붙인 컨테이너에서 공장 브로커 · 브리지 · DMZ 브로커의 모든 입구로 연결을 열어 본다(이름으로, compose 와 똑같이 입구를 연 컨테이너의
    주소로). 하나도 열리지 않는다 — DMZ 브로커의 입구(명령 관문이 이름만 대고 명령을 놓는 곳)가 IT 에서 열리면 IT 가 승인 없이 명령을 놓을 수
    있게 된다. 브로커가 PC 에 입구를 열면 이 PC 의 Docker 는 그 입구를 IT 망에도 닿게 둔다(실측)."""
    services = (PLANT_BROKER, PLANT_BRIDGE, DMZ_BROKER)
    by_name = [(service, port) for service in services for port in _listeners(service)]
    boxes = {PLANT_BROKER: compose_exact[PLANT_BROKER], PLANT_BRIDGE: plant_mqtt.bridge_box, DMZ_BROKER: compose_exact[DMZ_BROKER]}
    by_address = [target for service, box in boxes.items() for target in _targets(service, box)]
    assert {box.name for service, box in boxes.items() if not _addresses(box)} == set()                # 세 컨테이너의 실제 주소를 읽었다
    opened = _opens_from([IT_NET], by_name + by_address)
    assert opened == set(), (opened, _holders(opened))


def test_공장_자리에서는_공장_브로커와_DMZ_브로커_양쪽으로_연결이_열린다(plant_mqtt):
    """브리지와 같은 망에 붙인 컨테이너에서는 두 브로커가 모두 열린다 — 여는 쪽이 공장이면 길이 있다."""
    assert _opens_from(sorted(NETS[PLANT_BRIDGE]), [(PLANT_BROKER, 1883), (DMZ_BROKER, 1883)]) == {f'{PLANT_BROKER}:1883', f'{DMZ_BROKER}:1883'}


# ---------------------------------------------------------------- 시스템 구성 화면의 표(layers.js) = compose
def _diagram():
    """화면이 읽는 표를 실제 layers.js 에서 꺼낸다: 부품마다 이름 · 붙은 망 · 영역, 그리고 망 목록."""
    from www_node import run
    return run(['layers.js'], "out({ comps: LAYERS.flatMap(L => L.comps.map(c => ({ name: c.name, nets: c.nets || null, zone: c.zone }))), nets: NETS.map(n => n.id) })")


#: 그림에 상자가 없는데 IT 망 밖의 망에 붙는 서비스와 그 까닭. 여기에 없는 서비스가 OT · 경계 · 가상 설비 API 망에 붙으면 그림이 그 사실을 빠뜨린 것이다
NOT_DRAWN = {
    'fuxa-init': '관제 화면(FUXA)에 화면 설정을 한 번 넣고 끝나는 작업 — 떠 있는 부품이 아니다',
    'dmn-mcp': '판단 서비스(agent)의 도구 서버 — 그림의 망 설명이 「포털 · 판단 서비스는 이 망으로 두 부품의 상태만 읽습니다」로 함께 말한다',
}


def test_시스템_구성_화면의_부품마다_붙은_망이_compose와_같다():
    comps = _diagram()['comps']
    assert len(comps) >= 15 and all(c['nets'] for c in comps), [c['name'] for c in comps if not c['nets']]      # 표를 실제로 읽었고 망이 빈 부품이 없다
    unknown = [c['name'] for c in comps if c['name'].lower() not in SERVICES]
    assert unknown == []                                             # 그림의 부품은 모두 compose 의 서비스다(이름은 대소문자만 다르다)
    assert {c['name']: sorted(c['nets']) for c in comps if set(c['nets']) != NETS[c['name'].lower()]} == {}


def test_시스템_구성_화면의_망_목록과_영역이_compose에서_나온_것과_같다():
    diagram = _diagram()
    compose_nets = list(yaml.safe_load((ROOT / 'compose.yaml').read_text(encoding='utf8'))['networks'])
    assert diagram['nets'] == compose_nets                           # 망 여섯의 이름과 차례
    zone_of = {**{s: 'ot' for s in OT}, **{s: 'dmz' for s in DMZ}, **{s: 'it' for s in IT}}
    assert {c['name']: c['zone'] for c in diagram['comps'] if c['zone'] != zone_of[c['name'].lower()]} == {}


def test_IT_망_밖의_망에_붙는_서비스는_모두_그림에_있다():
    drawn = {c['name'].lower() for c in _diagram()['comps']}
    outside = {s for s, nets in NETS.items() if nets - {IT_NET, 'business-db'}}      # OT · 경계 망 둘 · 가상 설비 API 망 가운데 하나에라도 붙는 서비스(업무 DB 망은 IT 영역)
    assert outside - drawn == set(NOT_DRAWN)
