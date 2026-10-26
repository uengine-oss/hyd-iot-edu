"""Instructor wiring checks; no production secrets, databases or model calls."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from procsvc import classroom_config as config


def setup_config(tmp_path, monkeypatch, **overrides):
    settings = dict(HYD_CLASSROOM_AUTHORITY_DSN='postgresql://unused',
                    HYD_CLASSROOM_UPSTREAM_URL='https://relay.example',
                    HYD_CLASSROOM_UPSTREAM_KEY_FILE=str(tmp_path/'upstream.key'),
                    HYD_WORKER_RUNTIME_KEY_FILE=str(tmp_path/'private.key'), TENANT_ID='class-1')
    settings.update(overrides)
    monkeypatch.setattr(config.classroom_api, 'create_app', lambda authority, **kw: kw)
    return config.build(settings=settings, runtime_factory=lambda: SimpleNamespace(tenant_id='class-1'),
                        archive_factory=lambda: object(), driver_factory=lambda: None)


def test_missing_instructor_configuration_cannot_enable_gateway(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match='강사 관리 서버'):
        setup_config(tmp_path, monkeypatch, HYD_CLASSROOM_AUTHORITY_DSN='')


def test_only_explicit_instructor_setting_enables_agent_routes(tmp_path, monkeypatch):
    assert setup_config(tmp_path, monkeypatch)['agent_enabled'] is False
    assert setup_config(tmp_path, monkeypatch, HYD_CLASSROOM_AGENT_ENABLED='1')['agent_enabled'] is True
    assert setup_config(tmp_path, monkeypatch, HYD_CLASSROOM_AGENT_ENABLED='0')['agent_enabled'] is False
    with pytest.raises(ValueError, match='0 또는 1'):
        setup_config(tmp_path, monkeypatch, HYD_CLASSROOM_AGENT_ENABLED='true')


@pytest.mark.parametrize('url', ['http://relay.example', 'https://secret@relay.example', 'https://relay.example?key=secret'])
def test_credentials_and_unencrypted_upstream_urls_are_rejected(tmp_path, monkeypatch, url):
    with pytest.raises(ValueError, match='HTTPS'):
        setup_config(tmp_path, monkeypatch, HYD_CLASSROOM_UPSTREAM_URL=url)


def test_upstream_key_is_read_only_at_execution_and_can_rotate(tmp_path, monkeypatch):
    wiring = setup_config(tmp_path, monkeypatch)
    with pytest.raises(HTTPException) as error:
        wiring['upstream_factory']()
    assert error.value.status_code == 503
    key_file = tmp_path/'upstream.key'
    key_file.write_text('test-only-first-key-value', encoding='utf8')
    assert wiring['upstream_factory']()['key'] == 'test-only-first-key-value'
    key_file.write_text('test-only-rotated-key-value', encoding='utf8')
    assert wiring['upstream_factory']()['key'] == 'test-only-rotated-key-value'
    with pytest.raises(HTTPException): wiring['runtime_factory']('other-class')
    assert wiring['runtime_factory']('class-1').tenant_id == 'class-1'
