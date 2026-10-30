"""도구 호출 기록(procsvc/mcp_calls.py) — 처리 기록의 도구 이벤트를 서버 · 도구별 호출 한 줄로 모은다. 도구 이름 형식은 Claude Code 하나."""
import pytest

from procsvc import mcp_calls


@pytest.mark.parametrize('raw, parsed', [
    ('mcp__hyd-dmn__diagnose', ('hyd-dmn', 'diagnose')),
    ('mcp__enterprise-maint__pm_status', ('enterprise-maint', 'pm_status')),
    ('Read', (None, 'Read')),                         # 내장 도구 — MCP 호출 기록이 아니다
    ('hyd-dmn/diagnose', (None, 'hyd-dmn/diagnose')),  # 다른 CLI 형식은 이제 남는 곳이 없다
    ('mcp__hyd-dmn', (None, 'mcp__hyd-dmn')),          # 도구 이름이 빠진 기록
    (None, (None, '')),
])
def test_도구_이름에서_서버와_도구를_읽는다(raw, parsed):
    assert mcp_calls.parse_tool(raw) == parsed


def _event(i, kind, tool, use_id, at, **data):
    return {'id': i, 'todo_id': 't-1', 'proc_inst_id': 'p-1', 'event_type': kind, 'timestamp': at,
            'activity_id': 'T_agent', 'activity_name': '진단', 'proc_inst_name': '냉각 경보',
            'data': {'tool': tool, 'tool_use_id': use_id, **data}}


ROWS = [  # 새것 먼저(recent_tool_events 순서)
    _event(4, 'tool_usage_finished', 'mcp__hyd-dmn__diagnose', 'u-2', '2026-10-30T09:00:05+00:00', output='{"top": "c1"}', is_error=True),
    _event(3, 'tool_usage_started', 'mcp__hyd-dmn__diagnose', 'u-2', '2026-10-30T09:00:04+00:00', input={'asset': 'HYD-01'}),
    _event(2, 'tool_usage_finished', 'mcp__enterprise__query', 'u-1', '2026-10-30T09:00:03+00:00', output='[]'),
    _event(1, 'tool_usage_started', 'mcp__enterprise__query', 'u-1', '2026-10-30T09:00:01.500000+00:00', input={'sql': 'select 1', 'password': 'pw-1'}),
    _event(0, 'tool_usage_started', 'Read', 'u-0', '2026-10-30T09:00:00+00:00', input={'file_path': 'context/task.json'}),
]


@pytest.mark.parametrize('server, tool, expected', [
    (None, None, [('hyd-dmn', 'diagnose'), ('enterprise', 'query')]),
    ('hyd-dmn', None, [('hyd-dmn', 'diagnose')]),
    ('hyd_dmn', None, []),                       # 서버 이름은 그대로 비교한다(밑줄로 바꾼 이름은 다른 서버)
    ('enterprise', 'query', [('enterprise', 'query')]),
    ('enterprise', 'describe_schema', []),
])
def test_서버와_도구로_거른_호출을_새것부터_보인다(server, tool, expected):
    out = mcp_calls.calls(ROWS, server=server, tool=tool)
    assert [(c['server'], c['tool']) for c in out] == expected


def test_시작과_끝_이벤트는_한_호출로_묶여_걸린_시간과_상태와_가린_입력을_보인다():
    diagnose, query = mcp_calls.calls(ROWS)
    assert (diagnose['state'], diagnose['duration_ms'], diagnose['output_summary']) == ('error', 1000, '{"top": "c1"}')
    assert (query['state'], query['duration_ms']) == ('done', 1500)
    assert 'pw-1' not in query['input'] and 'select 1' in query['input']
    assert query['link'] == '#/instances/p-1/task/t-1'
