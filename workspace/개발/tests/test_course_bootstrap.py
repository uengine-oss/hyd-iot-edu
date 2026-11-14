"""수업 흐름 설치(procsvc/course_bootstrap.py · POST /api/course-bootstrap) — 시작 6단계. 배포된 수업 흐름이 course_flows.json 과 같으면 그대로,
옛 판(강사가 흐름을 고쳐 push 하기 전의 PC)이면 새 판본을 등록 · 배포한다(P2-09). 실제 process 앱(world)에서 판정한다 — world 가 켜질 때 이미
시작과 같은 설치를 한 번 했다. 옛 PC 상태는 같은 설치 함수(install)에 옛 흐름 내용(구매팀장 보고가 들어오기 전의 예비품 구매 연결)을 넣어 만든다."""
import asyncio
from copy import deepcopy

import pytest

from procsvc import course_bootstrap as cb
from procsvc.bpmn_import import xml_sha256


def flows(world):
    status, body = world.api('GET', '/api/flows/deployments')
    assert status == 200, body
    return {r['definition']: r for r in body['flows'] if r.get('class_flow')}


def deployed(world, did):
    head = flows(world)[did]
    status, body = world.api('GET', f"/api/process/definitions/{did}?version={head['version']}")
    assert status == 200, body
    return head['version'], body


def test_같은_내용이_배포돼_있으면_아무것도_바꾸지_않는다(world):
    before = flows(world)
    status, body = world.api('POST', '/api/course-bootstrap', {})
    assert status == 200 and [r['reused'] for r in body['flows']] == [True] * len(cb.FLOWS)
    assert {d: r['version'] for d, r in flows(world).items()} == {d: r['version'] for d, r in before.items()}


def _old_spare():
    filename, xml, mapping = deepcopy(cb.FLOWS['c3_spare'])
    mapping['tasks']['R_ok']['config'].pop('notify')      # 10-27(cd4070f7) 전 판 — 구매팀장 보고가 없던 연결
    assert mapping != cb.FLOWS['c3_spare'][2]
    return filename, xml, mapping


def _install_old(world):
    filename, xml, mapping = _old_spare()

    async def go():
        async with cb.internal_client(world.main.app) as client:
            return await cb.install(client, 'c3_spare', filename, xml, mapping)
    box = {}
    import threading
    t = threading.Thread(target=lambda: box.update(v=asyncio.run(go())))
    t.start(); t.join()
    return box['v']


def test_옛_판_흐름이_배포된_PC는_다음_시작_때_지금_판을_새_판본으로_배포한다(world):
    """P2-09: 「이미 수업 흐름이면 건너뜀」이라 흐름을 고쳐 push 해도 시작한 적 있는 PC는 옛 흐름을 썼다."""
    old = _install_old(world)
    version, definition = deployed(world, 'c3_spare')
    assert version == old and not cb.same_content(definition, *cb.FLOWS['c3_spare'][1:])
    status, body = world.api('POST', '/api/course-bootstrap', {})
    assert status == 200, body
    row = next(r for r in body['flows'] if r['definition'] == 'c3_spare')
    assert (row['reused'], row['replaced']) == (False, old) and row['version'] != old
    version, definition = deployed(world, 'c3_spare')
    assert version == row['version'] and cb.same_content(definition, *cb.FLOWS['c3_spare'][1:])
    assert all(r['reused'] for r in body['flows'] if r['definition'] != 'c3_spare')


@pytest.mark.parametrize('body', [{'flows': 'x'}, {'class_flow': True}, b'not json'])
def test_수업_흐름_설치는_설정값을_받지_않는다(world, body):
    import httpx

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=world.main.app), base_url='http://p') as c:
            if isinstance(body, bytes):
                return await c.post('/api/course-bootstrap', content=body)
            return await c.post('/api/course-bootstrap', json=body)
    import threading
    box = {}
    t = threading.Thread(target=lambda: box.update(r=asyncio.run(go())))
    t.start(); t.join()
    assert box['r'].status_code == 422


@pytest.mark.parametrize('change, same', [
    (lambda xml, mapping: (xml, mapping), True),
    (lambda xml, mapping: (xml + ' ', mapping), False),
    (lambda xml, mapping: (xml, dict(mapping, name='다른 이름')), False),
], ids=['같은 그림 · 연결', '그림 글자 하나 다름', '연결 다름'])
def test_같은_내용인지는_정의에_남긴_그림_지문과_연결로_본다(change, same):
    filename, xml, mapping = cb.FLOWS['c3_cooling']
    definition = {'bpmnImport': {'sha256': xml_sha256(xml), 'mapping': deepcopy(mapping)}}
    assert cb.same_content(definition, *change(xml, mapping)) is same


def test_설치_흔적이_없는_정의는_다른_내용으로_본다():
    _, xml, mapping = cb.FLOWS['c3_cooling']
    assert not cb.same_content({}, xml, mapping) and not cb.same_content(None, xml, mapping)


# ---------------------------------------------------------------- 흐름 그림(사람이 배치한 그림 정보)이 화면이 읽는 길로 나온다
def test_기본_제공_흐름의_그림은_가져온_흐름과_같은_길로_배치_정보와_함께_나온다(world):
    """화면은 판본마다 GET /api/flows/{id}/versions/{v}/bpmn 하나로 그림을 읽는다. 수업 흐름은 설치 때 등록한 원문(course_flows.json 의 그림),
    기준 흐름 · 교대 인수인계는 정의 옆의 그림 파일이 기동 때 그 판본에 붙은 것이다. 그림을 두지 않은 흐름은 204, 없는 판본은 404."""
    for did, head in flows(world).items():
        status, xml = world.api('GET', f"/api/flows/{did}/versions/{head['version']}/bpmn")
        assert status == 200 and xml == cb.FLOWS[did][1], did
        assert 'BPMNDiagram' in xml and xml.count('<bpmn:lane ') == 3, did
    status, rows = world.api('GET', '/api/process/definitions')
    assert status == 200
    latest = {r['id']: r['version'] for r in rows}
    for did in ('anomaly_response', 'shift_handover'):
        status, xml = world.api('GET', f"/api/flows/{did}/versions/{latest[did]}/bpmn")
        assert status == 200 and 'BPMNDiagram' in xml and '<bpmn:lane ' in xml, did
        status, definition = world.api('GET', f"/api/process/definitions/{did}?version={latest[did]}")
        from procsvc.bpmn_store import xid
        assert all(f'id="{xid(a["id"])}"' in xml for a in definition['activities']), '그림의 요소는 화면이 정의의 id 에서 만드는 id 로 찾는다'
    status, body = world.api('GET', f"/api/flows/alert_triage/versions/{latest['alert_triage']}/bpmn")
    assert (status, body) == (204, ''), '그림이 없는 판본은 오류가 아니다 — 화면이 정의에서 그린다'
    status, body = world.api('GET', '/api/flows/anomaly_response/versions/0.0/bpmn')
    assert status == 404 and '없습니다' in str(body)

