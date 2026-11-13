"""서비스 뼈대(common/hydcommon/service.py) — /healthz 의 ok 가 거짓이면 503, 다른 출처에 CORS 를 답하지 않고 다른 사이트의 쓰기는 403(결정 1 · W2-10 · 넘김 FA2 → FO)."""
import pytest
from fastapi.testclient import TestClient

from hydcommon.metrics import Registry
from hydcommon.service import CROSS_SITE_REFUSED, make_app


def test_건강이_나쁘면_503이고_본문에_까닭이_있다():
    state = {'ok': True, 'mqtt': True}
    client = TestClient(make_app('t', Registry(), lambda: dict(state)))
    assert client.get('/healthz').status_code == 200
    state.update(ok=False, mqtt=False)
    r = client.get('/healthz')
    assert r.status_code == 503 and r.json() == {'ok': False, 'mqtt': False}


def test_다른_출처의_요청에_허락_머리글을_답하지_않는다():
    client = TestClient(make_app('t', Registry()))
    pre = client.options('/healthz', headers={'Origin': 'https://evil.example', 'Access-Control-Request-Method': 'POST'})
    get = client.get('/healthz', headers={'Origin': 'https://evil.example'})
    assert get.status_code == 200
    assert all('access-control-allow-origin' not in {k.lower() for k in r.headers} for r in (pre, get))


def test_지표는_긁기_직전에_상태에서_다시_읽는다():
    reg, seen = Registry(), {'v': 1}
    gauge = reg.gauge('v', 'value')
    client = TestClient(make_app('t', reg, refresh=lambda: gauge.set(seen['v'])))
    seen['v'] = 7
    assert 'v 7' in client.get('/metrics').text



@pytest.mark.parametrize('method, site, status', [
    ('POST', 'cross-site', 403), ('DELETE', 'cross-site', 403), ('PUT', 'same-site', 403),     # 다른 사이트 · 이 PC 다른 포트의 페이지
    ('POST', 'same-origin', 200), ('POST', None, 200),                                          # 포털의 같은 출처 /svc/ · 도구 · 서비스끼리
    ('GET', 'cross-site', 200),                                                                 # 읽기는 그대로(CORS 가 없어 답을 못 읽는다)
], ids=['다른 사이트 POST', '다른 사이트 DELETE', '같은 PC 다른 포트 PUT', '같은 출처 POST', '머리글 없는 POST', '다른 사이트 GET'])
def test_다른_사이트의_페이지가_보낸_쓰기는_본문이_없어도_실행하지_않는다(method, site, status):
    app = make_app('t', Registry())
    ran = []

    @app.api_route('/w', methods=['GET', 'POST', 'PUT', 'DELETE'])
    def write():
        ran.append(1)
        return {'ok': True}
    r = TestClient(app).request(method, '/w', headers={'Sec-Fetch-Site': site} if site else {})
    assert r.status_code == status
    assert (r.json() == {'detail': CROSS_SITE_REFUSED}) == (status == 403) and bool(ran) == (status == 200)


# TestClient 의 Host 는 testserver. 포털 nginx 를 지난 요청은 X-Forwarded-Host(브라우저가 부른 포털 주소)를 싣는다.
@pytest.mark.parametrize('method, headers, status', [
    ('POST', {'Origin': 'https://evil.example'}, 403),                                                       # 옛 브라우저 · 다른 사이트
    ('POST', {'Origin': 'http://127.0.0.1:9999', 'X-Forwarded-Host': '127.0.0.1:8088'}, 403),               # 옛 브라우저 · 이 PC 다른 포트
    ('POST', {'Origin': 'null'}, 403),                                                                       # 출처를 숨긴 페이지(샌드박스)
    ('POST', {'Origin': 'http://127.0.0.1:8088', 'X-Forwarded-Host': '127.0.0.1:8088'}, 200),               # 옛 브라우저 · 포털 같은 출처
    ('POST', {'Origin': 'http://testserver'}, 200),                                                          # 프록시 없이 같은 주인
    ('POST', {}, 200),                                                                                       # 도구 · 서비스끼리(Origin 없음)
    ('POST', {'Sec-Fetch-Site': 'same-origin', 'Origin': 'https://evil.example'}, 200),                     # 새 브라우저: Sec-Fetch-Site 가 이긴다
    ('POST', {'Sec-Fetch-Site': 'cross-site', 'Origin': 'http://testserver'}, 403),
    ('GET', {'Origin': 'https://evil.example'}, 200),                                                        # 읽기는 그대로
], ids=['Origin 다른 사이트', 'Origin 다른 포트', 'Origin null', 'Origin 포털 같음', 'Origin Host 같음', '머리글 없음',
        'Sec-Fetch 같은 출처', 'Sec-Fetch 다른 사이트', '읽기'])
def test_Sec_Fetch_Site_를_보내지_않는_브라우저의_쓰기는_Origin_이_부른_주인과_다르면_실행하지_않는다(method, headers, status):
    """메인 결정(OWASP CSRF — 출처 확인): Sec-Fetch-Site 가 없으면 통과시켜 옛 브라우저에서 다른 사이트 양식 POST 가 실행됐다."""
    app = make_app('t', Registry())
    ran = []

    @app.api_route('/w', methods=['GET', 'POST'])
    def write():
        ran.append(1)
        return {'ok': True}
    r = TestClient(app).request(method, '/w', headers=headers)
    assert r.status_code == status and bool(ran) == (status == 200)


def _ended(coro):
    import asyncio

    async def go():
        task = asyncio.ensure_future(coro)
        await asyncio.wait([task])
        return task
    return asyncio.run(go())


def test_소비_루프가_예외로_끝나면_까닭을_남기고_프로세스를_내린다(monkeypatch):
    """2026-11-13 전수 검사: 루프가 끝나도 프로세스가 살아 있어 compose 가 다시 켜지 않았다(감지 · 적재가 멈춘 채 서비스 12/13)."""
    import logging
    from hydcommon import service
    stopped = []
    monkeypatch.setattr(service, '_stop_process', lambda: stopped.append(True))

    async def boom():
        raise RuntimeError('broker gone')
    state = {}
    service.stop_after_loop_end(_ended(boom()), state, logging.getLogger('t'))
    assert stopped == [True]
    assert state['consumer_dead'] is True and 'broker gone' in state['consumer_error']


def test_소비_루프가_말없이_끝나도_프로세스를_내리고_끄는_중의_취소는_내리지_않는다(monkeypatch):
    import asyncio, logging
    from hydcommon import service
    stopped = []
    monkeypatch.setattr(service, '_stop_process', lambda: stopped.append(True))

    async def quiet():
        return None
    state = {}
    service.stop_after_loop_end(_ended(quiet()), state, logging.getLogger('t'))
    assert stopped == [True] and state['consumer_error'] == 'exited'

    async def cancelled():
        task = asyncio.ensure_future(asyncio.sleep(60))
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.wait([task])
        return task
    stopped.clear(); state = {}
    service.stop_after_loop_end(asyncio.run(cancelled()), state, logging.getLogger('t'))
    assert stopped == [] and state == {}
