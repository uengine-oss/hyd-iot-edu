"""판단 등록이 거절되면 process 가 준 사유를 그대로 올린다 — 2026-10-23 라이브: 에이전트와 처리 기록에 'HTTP Error 409: Conflict'만 남아 원인을 알 수 없었다."""
import io
import json
import urllib.error

import pytest

from agentsvc import decide


def refused(code, body):
    def urlopen(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, code, 'Conflict', {}, io.BytesIO(body))
    return urlopen


def test_refusal_carries_the_process_reason(monkeypatch):
    reason = '이 사건은 조치 카드 접수 대상이 아닙니다. 현장 검토 상태를 확인하세요'
    monkeypatch.setattr(decide.urllib.request, 'urlopen', refused(409, json.dumps({'detail': reason}, ensure_ascii=False).encode()))
    with pytest.raises(decide.SubmitRefused) as e:
        decide.submit({'id': 'DEC-T', 'options': [{}]})
    assert 'HTTP 409' in str(e.value) and reason in str(e.value)


def test_refusal_without_json_body_keeps_the_raw_text(monkeypatch):
    monkeypatch.setattr(decide.urllib.request, 'urlopen', refused(502, b'bad gateway'))
    with pytest.raises(decide.SubmitRefused, match='HTTP 502.*bad gateway'):
        decide.submit({'id': 'DEC-T', 'options': [{}]})
