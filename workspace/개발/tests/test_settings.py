"""워커 설정(worker/settings.py)의 허용 도구 — 교대 인수인계는 허용 목록 한 곳(hydcommon.handover_tools)에서만 정한다(하-07)."""
from hydcommon.handover_tools import HANDOVER_READS
from worker.settings import BLOCKED_SHELL_TOOLS, DEFAULT_ALLOWED_TOOLS, handover_allowed_tools, run_allowed_tools

DEFAULT = DEFAULT_ALLOWED_TOOLS.split(',')
SERVERS = ['enterprise', 'hyd-dmn', 'neo4j', 'enterprise-purchase']


def test_교대_인수인계는_허용_목록의_조회_도구만_미리_허용한다():
    allowed = handover_allowed_tools(DEFAULT + ['Bash', 'mcp__hyd-dmn__submit_decision'], SERVERS)
    expected_reads = {f'mcp__{s}__{t}' for s, tools in HANDOVER_READS.items() if s in SERVERS for t in tools}
    assert {a for a in allowed if a.startswith('mcp__')} == expected_reads
    assert not any(a.endswith(('submit_decision', 'submit_purchase')) or a.endswith('__*') for a in allowed)
    assert not set(BLOCKED_SHELL_TOOLS) & set(allowed)


def test_교대_단계에_없는_서버의_조회_도구는_넣지_않는다():
    allowed = handover_allowed_tools(DEFAULT, ['neo4j'])
    assert {a for a in allowed if a.startswith('mcp__')} == {f'mcp__neo4j__{t}' for t in HANDOVER_READS['neo4j']}


def test_학생이_등록한_서버는_검사에서_읽기로_확인된_도구만_허용하고_셸은_늘_뺀다():
    allowed = run_allowed_tools(DEFAULT + ['Bash(python *)'], ['enterprise', 'my-server'], {'my-server': ['lookup']})
    assert 'mcp__my-server__lookup' in allowed and 'mcp__my-server__*' not in allowed
    assert not any(a.split('(')[0] in BLOCKED_SHELL_TOOLS for a in allowed)
