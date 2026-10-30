"""승인 뒤 메일 도구 서버(it/effects-mcp/effects_mcp/server.py) — process 만 아는 값이 맞는 호출만 받는다(하-04).

실제 서버 앱을 이 PC 포트에 띄우고(conftest engine_services), process 가 실제로 부르는 클라이언트(procsvc.mcp_check.call_effect)로 부른다.
"""
import os
import uuid

import pytest

from procsvc import mcp_check

ARGS = {'to': 'production@hyd.local', 'subject': '[정비 공지] 시험', 'body': '시험 메일'}


@pytest.mark.parametrize('headers, sent', [
    ({'X-HYD-Process-Caller': os.environ['PROCESS_CALLER_TOKEN']}, True),        # process 의 시스템 단계
    ({}, False),                                                                # 머리글 없음(에이전트 · 학생이 직접 부름)
    ({'X-HYD-Process-Caller': 'guess-' + 'x' * 20}, False),                      # 틀린 값
])
def test_메일_도구는_process만_아는_값이_맞는_호출만_실행한다(engine_services, headers, sent):
    spec = {'type': 'url', 'url': engine_services.effects, 'transport': 'streamable_http', 'headers': headers}
    before = len(engine_services.smtp.messages)
    out = mcp_check.call_effect(spec, 'send_mail', dict(ARGS), idempotency_key='test:' + uuid.uuid4().hex)
    assert out['status'] == 'ok'
    assert bool(out['result'].get('is_error')) is not sent
    assert len(engine_services.smtp.messages) - before == (1 if sent else 0)
    if not sent:
        assert 'process' in out['result']['text'] and '승인' in out['result']['text']


def test_같은_멱등_키로_다시_불러도_메일은_한_통이다(engine_services):
    spec = {'type': 'url', 'url': engine_services.effects, 'transport': 'streamable_http',
            'headers': {'X-HYD-Process-Caller': os.environ['PROCESS_CALLER_TOKEN']}}
    key, before = 'test:' + uuid.uuid4().hex, len(engine_services.smtp.messages)
    for _ in range(2):
        out = mcp_check.call_effect(spec, 'send_mail', dict(ARGS), idempotency_key=key)
        assert out['status'] == 'ok' and not out['result'].get('is_error')
    assert len(engine_services.smtp.messages) - before == 1
