"""Live nginx routing boundary against an isolated echo backend, not production."""
import os

import httpx
import pytest

pytestmark = pytest.mark.skipif(os.getenv('HYD_CLASSROOM_GATEWAY_TEST') != '1', reason='requires isolated nginx boundary fixture')
PUBLIC = 'http://127.0.0.1:55759'
PRIVATE = 'http://127.0.0.1:55760'


@pytest.mark.parametrize('path', ['/internal/worker/model-runtime', '/internal/model/v1/messages',
    '/api/kg/manuals/commit', '/api/process-definitions', '/v1/messages', '/v1/chat/completions',
    '/key/generate', '/classroom/internal/model/v1/messages', '/v1/classroom/../../internal/model/v1/messages'])
def test_public_listener_never_exposes_worker_model_or_admin(path):
    assert httpx.post(PUBLIC+path, json={}, timeout=5).status_code == 404


def test_public_classroom_paths_are_forwarded_with_the_mount_prefix():
    response = httpx.post(PUBLIC+'/v1/classroom/extractions', json={'sha256':'a'*64}, timeout=5)
    assert response.status_code == 200 and response.text == '/classroom/v1/classroom/extractions'
    assert response.headers['cache-control'] == 'no-store'
    assert httpx.post(PUBLIC+'/v1/classroom/extractions', content=b'x'*17000, timeout=5).status_code == 413


@pytest.mark.parametrize('path', ['/internal/worker/model-runtime', '/internal/model/v1/messages',
    '/internal/model/v1/messages/count_tokens'])
def test_private_listener_forwards_only_explicit_worker_paths(path):
    response = httpx.post(PRIVATE+path, json={}, timeout=5)
    assert response.status_code == 200 and response.text == '/classroom'+path


def test_private_listener_does_not_expose_admin_or_arbitrary_proxy_routes():
    for path in ('/api/kg/manuals/commit', '/v1/classroom/extractions', '/internal/model/key/generate'):
        assert httpx.post(PRIVATE+path, json={}, timeout=5).status_code == 404
