"""수업 흐름 설치(procsvc/course_bootstrap.py · POST /api/course-bootstrap) — 시작 6단계. 배포된 수업 흐름이 지금 코드가 course_flows.json 으로
만드는 정의와 같으면 그대로, 옛 판(강사가 흐름을 고쳐 push 하기 전의 PC · 가져오기가 정의에 넣는 것이 바뀌기 전의 PC)이면 새 판본을 등록 · 배포한다(P2-09). 실제 process 앱(world)에서 판정한다 — world 가 켜질 때 이미
시작과 같은 설치를 한 번 했다. 옛 PC 상태는 같은 설치 함수(install)에 옛 흐름 내용(구매팀장 보고가 들어오기 전의 예비품 구매 연결)을 넣어 만든다."""
import asyncio
from copy import deepcopy

import pytest

from procsvc import course_bootstrap as cb


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
    assert version == old and definition['bpmnImport']['mapping'] != cb.FLOWS['c3_spare'][2]
    status, body = world.api('POST', '/api/course-bootstrap', {})
    assert status == 200, body
    row = next(r for r in body['flows'] if r['definition'] == 'c3_spare')
    assert (row['reused'], row['replaced']) == (False, old) and row['version'] != old
    version, definition = deployed(world, 'c3_spare')
    assert version == row['version'] and definition['bpmnImport']['mapping'] == cb.FLOWS['c3_spare'][2]
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


def _threaded(coro_factory):
    import threading
    box = {}
    t = threading.Thread(target=lambda: box.update(v=asyncio.run(coro_factory())))
    t.start(); t.join()
    return box['v']


def test_그림과_연결이_같아도_배포된_정의가_지금_코드가_만드는_정의와_다르면_새_판본을_배포한다(world):
    """이미 쓰던 PC: 수업 흐름 B 가 옛 코드로 등록돼 경보 정책에 시계열에 없는 자리표 회복 기준(CMMS_PM_DUE)을 가진 채 배포돼 있다 — 그림 · 연결은
    지금과 같다. 그대로 두면 그 PC 만 처리 건 화면에 가짜 회복 기준이 보인다(새 PC 는 없음). 다음 시작이 지금 코드의 정의로 새 판본을 배포한다."""
    version, definition = deployed(world, 'c3_pm')
    assert definition['alertPolicy']['patterns']['PM_DUE'] == {'requireClear': True}, '지금 코드의 정기 정비 경보에는 시계열 회복 기준이 없다'
    stale = deepcopy(definition)
    stale['alertPolicy']['patterns']['PM_DUE'] = {'tag': 'CMMS_PM_DUE', 'op': '<', 'limit': 1, 'requireClear': True}
    from procsvc.bpmn_store import FlowStore
    filename, xml, _ = cb.FLOWS['c3_pm']
    stale = FlowStore(world.rt.repo, 'hyd').register(stale, xml, filename)            # 가져온 흐름의 등록 길 그대로(판본은 다음 번호)
    world.rt.definitions_changed()

    async def put_stale():
        async with cb.internal_client(world.main.app) as client:
            return await cb._call(client, 'POST', '/api/process/definitions/c3_pm/deploy',
                                  {'version': stale['version'], 'by': 'test', 'reason': '옛 코드가 등록한 판', 'class_flow': True}, '배포')
    _threaded(put_stale)
    old, now = deployed(world, 'c3_pm')
    assert old == stale['version'] and now['alertPolicy']['patterns']['PM_DUE'].get('tag') == 'CMMS_PM_DUE'
    assert now['bpmnImport'] == definition['bpmnImport'], '그림 지문 · 연결은 지금과 같다'
    status, body = world.api('POST', '/api/course-bootstrap', {})
    assert status == 200, body
    row = next(r for r in body['flows'] if r['definition'] == 'c3_pm')
    assert (row['reused'], row['replaced']) == (False, old) and row['version'] != old, row
    version, definition = deployed(world, 'c3_pm')
    assert version == row['version'] and definition['alertPolicy']['patterns']['PM_DUE'] == {'requireClear': True}
    assert all(r['reused'] for r in body['flows'] if r['definition'] != 'c3_pm')
    status, body = world.api('POST', '/api/course-bootstrap', {})
    assert status == 200 and [r['reused'] for r in body['flows']] == [True] * len(cb.FLOWS), '한 번 맞춘 뒤에는 다시 배포하지 않는다'


@pytest.mark.parametrize('change, same', [
    (lambda d: d, True),
    (lambda d: dict(d, version='7'), True),
    (lambda d: dict(d, alertPolicy={'patterns': {'PM_DUE': {'tag': 'CMMS_PM_DUE', 'op': '<', 'limit': 1, 'requireClear': True}}}), False),
    (lambda d: dict(d, bpmnImport=dict(d['bpmnImport'], sha256='0' * 64)), False),
    (lambda d: dict(d, bpmnImport=dict(d['bpmnImport'], mapping={'name': '다른 이름'})), False),
    (lambda d: dict(d, bpmnImport=dict(d['bpmnImport'], base={'id': 'anomaly_response', 'version': '2.8'})), True),
    (lambda d: dict(d, activities=[{'id': 'T_agent', 'outputData': ['decision']}]), False),
    (lambda d: None, False),
    (lambda d: {}, False),
], ids=['같은 정의', '판본 번호만 다름', '경보 정책 다름', '그림 지문 다름', '연결 다름', '기준 흐름 판본 기록만 다름', '가져온 부품의 계약 다름',
        '배포된 정의 없음', '빈 정의'])
def test_같은_내용인지는_판본_번호와_기준_흐름_판본_기록만_빼고_정의_전체로_본다(change, same):
    built = {'processDefinitionId': 'c3_pm', 'version': '3', 'alertPolicy': {'patterns': {'PM_DUE': {'requireClear': True}}},
             'bpmnImport': {'sha256': 'a' * 64, 'mapping': {'name': '정기 정비'}, 'base': {'id': 'anomaly_response', 'version': '2.9'}},
             'activities': [{'id': 'T_agent'}]}
    assert cb.same_definition(change(deepcopy(built)), built) is same


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

