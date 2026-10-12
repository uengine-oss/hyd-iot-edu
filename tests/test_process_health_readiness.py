"""The real health endpoint must reject an unavailable processing runtime."""
import httpx
import pytest

from procsvc import main


@pytest.mark.asyncio
@pytest.mark.parametrize('status', ['preparing', 'failed', 'cancelled', 'stopped'])
async def test_unavailable_runtime_is_not_healthy(monkeypatch, status):
    monkeypatch.setattr(main, 'PROCESS_MODE', 'instance')
    monkeypatch.setattr(main, 'state', {'kafka': True, 'incidents': 0})
    monkeypatch.setattr(main.instance_mode, 'runtime_readiness', lambda: {
        'ready': False, 'status': status, 'failure_kind': 'OperationalError', 'last_success_at': None})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='http://process') as client:
        response = await client.get('/healthz')
    assert response.status_code == 503
    assert response.json()['ok'] is False
    assert response.json()['runtime']['status'] == status


@pytest.mark.asyncio
async def test_runtime_recovery_preserves_source_failure(monkeypatch):
    monkeypatch.setattr(main, 'PROCESS_MODE', 'instance')
    monkeypatch.setattr(main, 'state', {'kafka': True, 'source_handler_error': '원천 처리 실패'})
    monkeypatch.setattr(main.instance_mode, 'runtime_readiness', lambda: {
        'ready': True, 'status': 'ready', 'failure_kind': None, 'last_success_at': '2026-10-13T00:00:00Z'})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='http://process') as client:
        failed = await client.get('/healthz')
        main.state.pop('source_handler_error')
        recovered = await client.get('/healthz')
    assert failed.status_code == 503
    assert failed.json()['source_handler_error'] == '원천 처리 실패'
    assert recovered.status_code == 200
    assert recovered.json()['ok'] is True


@pytest.mark.asyncio
async def test_legacy_health_does_not_consult_instance_runtime(monkeypatch):
    monkeypatch.setattr(main, 'PROCESS_MODE', 'legacy')
    monkeypatch.setattr(main, 'state', {'kafka': True})
    def forbidden():
        raise AssertionError('legacy mode has no instance polling loop')
    monkeypatch.setattr(main.instance_mode, 'runtime_readiness', forbidden)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='http://process') as client:
        response = await client.get('/healthz')
    assert response.status_code == 200
    assert 'runtime' not in response.json()
