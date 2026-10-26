import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest
from fastapi.testclient import TestClient

from procsvc.classroom_api import create_app
from procsvc.classroom_authority import Denied

spec = importlib.util.spec_from_file_location('check_classroom', Path(__file__).parents[1]/'scripts/check_classroom.py')
startup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(startup)
KEY = 'classroom-test-'+'x'*32


def test_startup_authenticates_without_extraction_or_model_call():
    calls = []
    def session(key):
        calls.append(key)
        if key != KEY:
            raise Denied('invalid classroom key')
        return {'status': 'ok', 'service': 'classroom-execution'}
    def forbidden(*args):
        pytest.fail('startup must not start extraction or model work')
    app = create_app(SimpleNamespace(session=session), source_loader=forbidden,
                     runtime_factory=forbidden, catalog_factory=forbidden)
    client = TestClient(app)
    class Opener:
        def open(self, request, timeout):
            assert timeout == 30
            response = client.get('/v1/classroom/session', headers=dict(request.header_items()))
            assert response.status_code == 200
            return io.BytesIO(response.content)
    startup.check('https://classroom.example', KEY, opener=Opener())
    assert calls == [KEY]
    assert client.get('/v1/classroom/session').status_code == 401
    assert client.get('/v1/classroom/session', headers={'Authorization': 'Bearer wrong'}).status_code == 403


@pytest.mark.parametrize('url', ['http://example.com', 'https://key@example.com',
                                'https://example.com?key=bad', 'https://example.com#bad'])
def test_unsafe_destination_never_receives_key(url):
    with pytest.raises(ValueError):
        startup.check(url, KEY, opener=SimpleNamespace(open=lambda *a, **kw: pytest.fail('sent key')))


def test_redirect_not_followed_and_errors_never_print_credentials(monkeypatch, capsys):
    assert startup.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.example') is None
    monkeypatch.setattr(startup.sys, 'argv', ['check', 'https://classroom.example'])
    monkeypatch.setattr(startup.sys, 'stdin', io.StringIO(KEY))
    def fail(*args):
        raise HTTPError('https://'+KEY, 403, KEY, {}, None)
    monkeypatch.setattr(startup, 'check', fail)
    assert startup.main() == 1
    output = capsys.readouterr().out
    assert '403' in output and KEY not in output


@pytest.mark.parametrize('body', [b'{}', b'x'*4097, b'not json'])
def test_unexpected_response_is_not_authentication_success(body):
    with pytest.raises(ValueError):
        startup.check('https://classroom.example', KEY,
                      opener=SimpleNamespace(open=lambda *args, **kwargs: io.BytesIO(body)))
