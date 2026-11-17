"""영역 경계 — compose.yaml 이 OT · DMZ · IT 를 망으로 나누고, 값이 올라오고 승인된 명령이 내려가는 길만 이어 두었는가. 그리고 그 길을 먼저 여는 쪽이 공장인가.

Docker 는 같은 망에 붙은 컨테이너끼리만 닿게 하므로, 「누가 누구에게 닿는가」는 compose 의 망 정의로 정해진다. 이 파일은 그 정의를 읽어
서비스 쌍마다 닿는지를 계산하고 아래를 판정한다(영역은 손으로 적은 표가 아니라 망에서 나온다 — ot-net 에 붙으면 OT, it-net 에 붙으면 IT,
경계 망에만 붙으면 DMZ).
  - 모든 서비스는 한 영역에만 있다.
  - OT 와 IT 는 서로 닿지 않는다. 하나뿐인 예외는 가상 설비 API 망(sim-net)이고 그 구성원은 정해져 있다(실습 조작의 길 — 브로커는 없다).
  - 공장 브로커(emqx)에는 OT 만 닿는다. 경계 망에 나와 있는 공장 쪽 부품은 공장 쪽 브리지(ot-bridge) 하나이고, IT 가 DMZ 경계 망에서 만나는 것은
    DMZ 와 IT 뿐이다.
  - 올라오는 길(설비 → 공장 브로커 → 브리지 → DMZ 브로커 → 수집 중계 → 이벤트 로그)과 내려가는 길(process → 이벤트 로그 → 명령 관문 →
    DMZ 브로커 → 브리지 → 공장 브로커 → 설비)이 이어져 있다.
  - 서비스가 환경 값 · 포털 길 표 · 감시 대상 · 브리지 설정으로 부르는 다른 서비스는 실제로 닿는 망에 있다(망을 나누다 길이 끊기지 않게).
  - 브로커가 호스트에 여는 것은 공장 브로커의 구독만 되는 바깥 입구뿐이다(안쪽 입구 · 관리 API · DMZ 브로커 · 브리지는 열지 않는다 — 관리 API 가
    꺼져 있는지는 test_emqx.py).
  - 연결을 먼저 여는 쪽은 공장이다: DMZ 서비스와 같은 망에 붙인 실제 컨테이너에서 공장 쪽 컨테이너(공장 브로커 · 브리지)의 어느 입구로도 TCP 연결이
    열리지 않는다(이름으로도 주소로도). 같은 자리에서 DMZ 브로커로는 열린다(잰 것이 실제 연결임을 보인다). 값과 명령이 브리지로 실제로 오가는지는
    test_ot_bridge.py.
  - 시스템 구성 화면이 그리는 표(it/portal/www/layers.js 의 부품마다 nets · zone, 망 목록 NETS)가 compose 의 망 정의와 같다. 화면은 이 표로 부품을
    영역 띠와 망에 놓으므로, 표가 compose 와 어긋나면 그림이 실제와 다른 구조를 말한다.
"""
import json
import re

import pytest
import yaml

from conftest import CONTAINER_LABEL, CONTAINER_SITE, ROOT, _docker, _test_site, site_network

SERVICES = yaml.safe_load((ROOT / 'compose.yaml').read_text(encoding='utf8'))['services']
NETS = {name: set(svc.get('networks') or ()) for name, svc in SERVICES.items()}
OT_NET, IT_NET, BOUNDARY, SIM_NET = 'ot-net', 'it-net', {'ot-dmz-net', 'dmz-it-net'}, 'sim-net'
OT = {s for s, n in NETS.items() if OT_NET in n}
IT = {s for s, n in NETS.items() if IT_NET in n}
DMZ = {s for s, n in NETS.items() if n and n <= BOUNDARY}
SIM_API = {'plant-sim': {'process', 'portal'}}          # 가상 설비 API(:8000)를 부르는 IT 서비스 — 결함 주입 · 정비 수행 모사 · 같은 출처 길
PLANT_BROKER, PLANT_BRIDGE, DMZ_BROKER = 'emqx', 'ot-bridge', 'dmz-broker'


def shared(a, b):
    return NETS[a] & NETS[b]


def members(net):
    return {s for s, n in NETS.items() if net in n}


def test_모든_서비스는_한_영역에만_있다():
    zones = {s: [z for z, group in (('OT', OT), ('DMZ', DMZ), ('IT', IT)) if s in group] for s in SERVICES}
    assert {s: z for s, z in zones.items() if len(z) != 1} == {}
    assert DMZ == {DMZ_BROKER, 'connect-ingest', 'cmd-gateway'}       # 영역을 넘는 일은 수집 중계 · 명령 관문만 하고, DMZ 브로커는 공장이 접속해 오는 자리다


def test_OT와_IT는_가상_설비_API_망_말고는_닿지_않는다():
    touching = {(o, i): shared(o, i) for o in OT for i in IT if shared(o, i)}
    assert touching == {(o, i): {SIM_NET} for o, callers in SIM_API.items() for i in callers}
    assert members(SIM_NET) == set(SIM_API) | {i for callers in SIM_API.values() for i in callers}


def test_공장_브로커에는_OT만_닿고_경계_망에_나온_공장_쪽_부품은_브리지_하나다():
    assert {s for s in SERVICES if s != PLANT_BROKER and shared(s, PLANT_BROKER)} == OT - {PLANT_BROKER}
    assert members('ot-dmz-net') == DMZ | {PLANT_BRIDGE}
    assert members('dmz-it-net') - DMZ <= IT and 'redpanda' in members('dmz-it-net')
    assert {(d, o) for d in DMZ for o in OT if shared(d, o)} == {(d, PLANT_BRIDGE) for d in DMZ}
    assert NETS[DMZ_BROKER] == {'ot-dmz-net'}                         # DMZ 브로커는 IT 쪽 경계 망에 나오지 않는다 — IT 는 그 브로커에 닿지 못한다


@pytest.mark.parametrize('path', [
    ['plant-sim', 'emqx', 'ot-bridge', 'dmz-broker', 'connect-ingest', 'redpanda', 'detector'],          # 값이 올라오는 길
    ['plant-sim', 'emqx', 'ot-bridge', 'dmz-broker', 'connect-ingest', 'redpanda', 'connect-sink'],
    ['process', 'redpanda', 'cmd-gateway', 'dmz-broker', 'ot-bridge', 'emqx', 'plant-sim'],              # 승인된 명령이 내려가는 길
    ['fuxa', 'emqx', 'plant-sim'],                                                                       # 운전 화면의 감시 · 수동 조작(OT 안)
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


def test_브로커가_호스트에_여는_것은_구독만_되는_바깥_입구뿐이다():
    inside = {int(str(line).rsplit(':', 1)[1]) for line in SERVICES['emqx'].get('ports') or []}
    assert inside == {1884, 8083}                          # ot/emqx/emqx.conf: 1884 · 8083 = 계정 student(구독만). 1883(서비스 이름만) · 18083(관리 API)은 열지 않는다
    assert {s: SERVICES[s].get('ports') for s in (PLANT_BRIDGE, DMZ_BROKER) if SERVICES[s].get('ports')} == {}      # 브리지 · DMZ 브로커는 호스트에 열지 않는다


# ---------------------------------------------------------------- 연결을 먼저 여는 쪽은 공장이다(실제 연결)
PROBE_IMAGE = SERVICES[DMZ_BROKER]['image']               # 이미 받은 이미지(busybox nc 가 들어 있다)
PLANT_SIDE_PORTS = {PLANT_BROKER: (1883, 1884, 8083, 18083), PLANT_BRIDGE: (1883,)}      # 공장 쪽 컨테이너가 안에서 듣는 포트(emqx.conf 입구들 · 브리지의 상태 확인 입구)


def _addresses(box):
    """그 컨테이너가 붙은 망마다의 주소."""
    nets = json.loads(_docker('inspect', '-f', '{{json .NetworkSettings.Networks}}', box.name))
    return {net: info['IPAddress'] for net, info in nets.items()}


def _opens_from(nets, targets):
    """nets(compose 망 이름들)에 붙은 새 컨테이너 안에서 (주소, 포트)마다 TCP 연결을 열어 본다 → 열린 것들."""
    script = '; '.join(f'nc -z -w 2 {host} {port} 2>/dev/null && echo {host}:{port}' for host, port in targets) + '; true'
    name = _docker('create', '--label', f'{CONTAINER_LABEL}=probe', '--label', f'{CONTAINER_SITE}={_test_site()}', '--entrypoint', 'sh',
                   '--network', site_network(nets[0]), PROBE_IMAGE, '-c', script).strip()
    try:
        for net in nets[1:]:
            _docker('network', 'connect', site_network(net), name)
        return set(_docker('start', '-a', name).split())
    finally:
        _docker('rm', '-f', name)


def test_DMZ_자리에서_공장_쪽_어느_입구로도_연결이_열리지_않는다(plant_mqtt):
    """DMZ 서비스(명령 관문)와 같은 망에 붙인 컨테이너에서 공장 브로커 · 브리지의 모든 입구로 연결을 열어 본다 — 이름으로, 그리고 그 컨테이너가 가진
    모든 주소로. 공장 브로커가 경계 망에 붙어 있으면(고치기 전의 compose) 이름 emqx 로 1883 이 열린다."""
    dmz_nets = sorted(NETS['cmd-gateway'] & {'ot-dmz-net'}) or pytest.fail('명령 관문이 경계 망 ot-dmz-net 에 없다')
    boxes = {PLANT_BROKER: plant_mqtt.plant_box, PLANT_BRIDGE: plant_mqtt.bridge_box}
    hosts = {service: {service, *_addresses(box).values()} for service, box in boxes.items()}
    assert all(len(found) >= 2 for found in hosts.values()), hosts                       # 이름 + 실제 주소를 읽었다
    targets = [(host, port) for service, found in hosts.items() for host in sorted(found) for port in PLANT_SIDE_PORTS[service]]
    control = (DMZ_BROKER, 1883)
    assert _opens_from(dmz_nets, targets + [control]) == {f'{control[0]}:{control[1]}'}


def test_공장_자리에서는_공장_브로커와_DMZ_브로커_양쪽으로_연결이_열린다(plant_mqtt):
    """브리지와 같은 망에 붙인 컨테이너에서는 두 브로커가 모두 열린다 — 여는 쪽이 공장이면 길이 있다."""
    assert _opens_from(sorted(NETS[PLANT_BRIDGE]), [(PLANT_BROKER, 1883), (DMZ_BROKER, 1883)]) == {'emqx:1883', 'dmz-broker:1883'}


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
    assert diagram['nets'] == compose_nets                           # 망 다섯의 이름과 차례
    zone_of = {**{s: 'ot' for s in OT}, **{s: 'dmz' for s in DMZ}, **{s: 'it' for s in IT}}
    assert {c['name']: c['zone'] for c in diagram['comps'] if c['zone'] != zone_of[c['name'].lower()]} == {}


def test_IT_망_밖의_망에_붙는_서비스는_모두_그림에_있다():
    drawn = {c['name'].lower() for c in _diagram()['comps']}
    outside = {s for s, nets in NETS.items() if nets - {IT_NET}}      # OT · 경계 망 둘 · 가상 설비 API 망 가운데 하나에라도 붙는 서비스
    assert outside - drawn == set(NOT_DRAWN)
