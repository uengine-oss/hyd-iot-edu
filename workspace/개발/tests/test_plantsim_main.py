"""plant-sim HTTP API(ot/plant-sim/plantsim/main.py) — 현장 패널 쓰기 · 결함 주입 검증 · 건강 · CORS 없음(G3b-10 · 14 · 18 · 28).

브로커는 바깥이라 엣지가 연결하지 않은 채(startup 을 부르지 않는 TestClient) 앱을 부른다 — 그러면 MQTT 가 끊긴 설비의 건강이 보인다.
"""
import importlib
import sys

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv('TIME_SCALE', '20')
    monkeypatch.setenv('DAQ_PROFILE', 'lite')
    import plantsim.main as main
    main = importlib.reload(main)                    # 설비 상태를 새로(테스트끼리 남지 않게)
    return main, TestClient(main.app)                # with 없이 — startup(엣지 연결)을 부르지 않는다


def test_MQTT가_끊긴_설비는_건강하지_않다(api):
    main, client = api
    r = client.get('/healthz')
    assert r.status_code == 503 and r.json()['mqtt'] is False


def test_현장_패널은_현장_제어_모드에서도_쓰고_한국어_사유를_준다(api):
    main, client = api
    assert client.post('/api/mode', json={'asset': 'HYD-01', 'mode': 'LOCAL'}).status_code == 200
    r = client.post('/api/manual', json={'asset': 'HYD-01', 'writes': {'FanSpeedSP': 70}}).json()
    assert (r['result'], r['applied']) == ('DONE', {'FanSpeedSP': 70.0}) and r['cmdId'].startswith('LOCAL-')
    r = client.post('/api/manual', json={'asset': 'HYD-01', 'writes': {'FanSpeedSP': 170}}).json()
    assert (r['result'], r['reason'], r['reason_text']) == ('REJECTED', 'OUT_OF_RANGE', '허용 범위 초과')


@pytest.mark.parametrize('body, code', [
    ({'asset': 'HYD-01', 'type': 'pump_leakage', 'target': 0.2}, 200),
    ({'asset': 'HYD-01', 'type': 'pump_leakage', 'target': 0.9}, 400),        # 물리 범위 밖
    ({'asset': 'HYD-01', 'type': 'cooler_degradation', 'ramp_sim_s': -1}, 400),
    ({'asset': 'HYD-01', 'type': 'meteor'}, 400),
    ({'asset': 'HYD-07', 'type': 'pump_leakage'}, 404),
    ({'asset': 'HYD-01', 'type': 'cooler_degradation', 'origin': {'id': ' '}}, 400),
    ({'type': 'pump_leakage'}, 422),              # 설비 없음 — HYD-01 로 대신 넣지 않는다(가짜 · 해피패스 조사 8)
    ({'asset': 'HYD-02'}, 422),                   # 결함 종류 없음 — 쿨러 열화로 대신 넣지 않는다
    ({}, 422),
])
def test_결함_주입은_범위_밖이면_까닭과_함께_거절한다(api, body, code):
    main, client = api
    assert client.post('/api/fault', json=body).status_code == code


def test_다른_출처에_CORS로_답하지_않는다(api):
    main, client = api
    r = client.options('/api/fault', headers={'Origin': 'https://evil.example', 'Access-Control-Request-Method': 'POST'})
    assert 'access-control-allow-origin' not in {k.lower() for k in r.headers}


def test_배속이_없으면_켜지지_않는다(monkeypatch):
    monkeypatch.delenv('TIME_SCALE', raising=False)
    sys.modules.pop('plantsim.main', None)
    with pytest.raises(ValueError, match='TIME_SCALE'):
        importlib.import_module('plantsim.main')
