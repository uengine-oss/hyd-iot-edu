"""영역 경계 — compose.yaml 이 OT · DMZ · IT 를 망으로 나누고, 값이 올라오고 승인된 명령이 내려가는 길만 이어 두었는가.

Docker 는 같은 망에 붙은 컨테이너끼리만 닿게 하므로, 「누가 누구에게 닿는가」는 compose 의 망 정의로 정해진다. 이 파일은 그 정의를 읽어
서비스 쌍마다 닿는지를 계산하고 아래를 판정한다(영역은 손으로 적은 표가 아니라 망에서 나온다 — ot-net 에 붙으면 OT, it-net 에 붙으면 IT,
경계 망 둘에만 붙으면 DMZ).
  - 모든 서비스는 한 영역에만 있다.
  - OT 와 IT 는 서로 닿지 않는다. 하나뿐인 예외는 가상 설비 API 망(sim-net)이고 그 구성원은 정해져 있다(실습 조작의 길 — 브로커는 없다).
  - 브로커(emqx)에는 OT 와 DMZ 만 닿는다. DMZ 가 OT 에서 닿는 것은 브로커 하나, IT 가 DMZ 경계 망에서 만나는 것은 DMZ 와 IT 뿐이다.
  - 올라오는 길(설비 → 브로커 → 수집 중계 → 이벤트 로그)과 내려가는 길(process → 이벤트 로그 → 명령 관문 → 브로커 → 설비)이 이어져 있다.
  - 서비스가 환경 값 · 포털 길 표 · 감시 대상으로 부르는 다른 서비스는 실제로 닿는 망에 있다(망을 나누다 길이 끊기지 않게).
  - 브로커가 호스트에 여는 것은 구독만 되는 바깥 입구뿐이다(안쪽 입구 · 관리 API 는 열지 않는다 — 관리 API 가 꺼져 있는지는 test_emqx.py).
"""
import re

import pytest
import yaml

from conftest import ROOT

SERVICES = yaml.safe_load((ROOT / 'compose.yaml').read_text(encoding='utf8'))['services']
NETS = {name: set(svc.get('networks') or ()) for name, svc in SERVICES.items()}
OT_NET, IT_NET, BOUNDARY, SIM_NET = 'ot-net', 'it-net', {'ot-dmz-net', 'dmz-it-net'}, 'sim-net'
OT = {s for s, n in NETS.items() if OT_NET in n}
IT = {s for s, n in NETS.items() if IT_NET in n}
DMZ = {s for s, n in NETS.items() if n == BOUNDARY}
SIM_API = {'plant-sim': {'process', 'portal'}}          # 가상 설비 API(:8000)를 부르는 IT 서비스 — 결함 주입 · 정비 수행 모사 · 같은 출처 길


def shared(a, b):
    return NETS[a] & NETS[b]


def members(net):
    return {s for s, n in NETS.items() if net in n}


def test_모든_서비스는_한_영역에만_있다():
    zones = {s: [z for z, group in (('OT', OT), ('DMZ', DMZ), ('IT', IT)) if s in group] for s in SERVICES}
    assert {s: z for s, z in zones.items() if len(z) != 1} == {}
    assert DMZ == {'connect-ingest', 'cmd-gateway'}       # 영역을 넘는 일은 이 둘만 한다(수집 중계 · 명령 관문)


def test_OT와_IT는_가상_설비_API_망_말고는_닿지_않는다():
    touching = {(o, i): shared(o, i) for o in OT for i in IT if shared(o, i)}
    assert touching == {(o, i): {SIM_NET} for o, callers in SIM_API.items() for i in callers}
    assert members(SIM_NET) == set(SIM_API) | {i for callers in SIM_API.values() for i in callers}


def test_브로커에는_OT와_DMZ만_닿고_DMZ는_OT에서_브로커만_본다():
    assert {s for s in SERVICES if s != 'emqx' and shared(s, 'emqx')} == (OT - {'emqx'}) | DMZ
    assert members('ot-dmz-net') == DMZ | {'emqx'}
    assert members('dmz-it-net') - DMZ <= IT and 'redpanda' in members('dmz-it-net')
    assert {(d, o) for d in DMZ for o in OT if shared(d, o)} == {(d, 'emqx') for d in DMZ}


@pytest.mark.parametrize('path', [
    ['plant-sim', 'emqx', 'connect-ingest', 'redpanda', 'detector'],          # 값이 올라오는 길
    ['plant-sim', 'emqx', 'connect-ingest', 'redpanda', 'connect-sink'],
    ['process', 'redpanda', 'cmd-gateway', 'emqx', 'plant-sim'],              # 승인된 명령이 내려가는 길
    ['fuxa', 'emqx', 'plant-sim'],                                            # 운전 화면의 감시 · 수동 조작(OT 안)
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


def test_서비스가_부르는_서비스는_닿는_망에_있다():
    calls = [c for c in _calls() if c[0] != c[1]]
    assert {('cmd-gateway', 'emqx'), ('connect-ingest', 'redpanda'), ('portal', 'cmd-gateway'), ('agent', 'connect-ingest'),
            ('process', 'redpanda')} <= {c[:2] for c in calls}                 # 읽기가 비어 있지 않다(길 표 · 환경 값을 실제로 읽었다)
    assert [c for c in calls if not shared(c[0], c[1])] == []


def test_브로커가_호스트에_여는_것은_구독만_되는_바깥_입구뿐이다():
    inside = {int(str(line).rsplit(':', 1)[1]) for line in SERVICES['emqx'].get('ports') or []}
    assert inside == {1884, 8083}                          # ot/emqx/emqx.conf: 1884 · 8083 = 계정 student(구독만). 1883(서비스 이름만) · 18083(관리 API)은 열지 않는다
