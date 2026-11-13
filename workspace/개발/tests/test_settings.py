"""워커 설정(worker/settings.py) — 실행의 미리 허용 도구 목록과 단계 정의의 에이전트 권한.

정해진 조회 도구는 규칙 한 곳(procsvc/agents_store.run_servers — 질문 · 교대 초안의 폼 계약이 고르는 hydcommon.handover_tools 표)이
정하고, 이 모듈은 그 결과를 CLI 허용 목록으로 옮긴다.
"""
import pytest
from cliagents import Permission

from hydcommon.handover_tools import HANDOVER_READS, QUESTION_READS
from procsvc.agents_store import HANDOVER_CONTRACT, QUESTION_CONTRACT, run_servers
from worker.course_access import Stop
from worker.settings import BLOCKED_SHELL_TOOLS, DEFAULT_ALLOWED_TOOLS, allowed_for_run, permission_of, run_allowed_tools, run_disallowed_tools

DEFAULT = DEFAULT_ALLOWED_TOOLS.split(',')
SERVERS = ['enterprise', 'hyd-dmn', 'neo4j', 'enterprise-purchase']


@pytest.mark.parametrize('contract,table', [(HANDOVER_CONTRACT, HANDOVER_READS), (QUESTION_CONTRACT, QUESTION_READS)],
                         ids=['교대 초안', '질문'])
def test_정해진_조회_단계는_그_표의_조회_도구만_미리_허용하고_일반_허용과_셸은_가져오지_않는다(contract, table):
    plan = run_servers(None, SERVERS, contract)
    allowed = allowed_for_run(DEFAULT + ['Bash', 'mcp__hyd-dmn__submit_decision'], sorted(plan), plan, {})
    assert {a for a in allowed if a.startswith('mcp__')} == {f'mcp__{s}__{t}' for s, tools in table.items() if s in SERVERS for t in tools}
    assert not any(a.endswith(('submit_decision', 'submit_purchase')) or a.endswith('__*') for a in allowed)
    assert not set(BLOCKED_SHELL_TOOLS) & set(allowed)
    assert {'Read', 'Write', 'Edit'} <= set(allowed)


def test_정해진_조회_단계에_붙인_서버가_표에_없으면_조회_도구를_하나도_허용하지_않는다():
    plan = run_servers(['enterprise-purchase'], SERVERS, HANDOVER_CONTRACT)
    assert plan == {}
    assert [a for a in allowed_for_run(DEFAULT, [], plan, {}) if a.startswith('mcp__')] == []


def test_정해진_목록이_없는_단계는_기본_허용에_학생_서버의_검사된_읽기_도구만_더하고_셸은_늘_뺀다():
    allowed = allowed_for_run(DEFAULT + ['Bash(python *)'], ['enterprise', 'my-server'], None, {'my-server': ['lookup']})
    assert 'mcp__my-server__lookup' in allowed and 'mcp__my-server__*' not in allowed
    assert 'mcp__enterprise__*' in allowed
    assert not any(a.split('(')[0] in BLOCKED_SHELL_TOOLS for a in allowed)


def test_검사에서_읽기로_확인하지_못한_도구는_거절_목록에_실린다():
    assert run_disallowed_tools({'my-server': ['write_row']}) == [*BLOCKED_SHELL_TOOLS, 'mcp__my-server__write_row']
    assert run_allowed_tools(DEFAULT, ['my-server'], {}) == DEFAULT        # 도장 없는 서버는 아무 도구도 더하지 않는다


@pytest.mark.parametrize('value,expected', [(None, Permission.WORKSPACE_WRITE), ('', Permission.WORKSPACE_WRITE),
                                            ('workspace_write', Permission.WORKSPACE_WRITE), ('read_only', Permission.WORKSPACE_WRITE)],
                         ids=['정하지 않음', '빈 칸', '작업 폴더 쓰기', '읽기 전용 → 작업 폴더 쓰기(plan 모드는 도구 호출을 막는다)'])
def test_단계의_에이전트_권한은_작업_폴더_안_쓰기로_실행한다(value, expected):
    assert permission_of(value) is expected


@pytest.mark.parametrize('value,needle', [('command_exec', '명령 실행'), ('workspace_wirte', 'workspace_wirte'), ('ADMIN', 'ADMIN')],
                         ids=['권한 묻기 없음(bypass)', '오타', '모르는 값'])
def test_지원하지_않는_권한이나_오타는_기본값으로_바꾸지_않고_까닭과_함께_멈춘다(value, needle):
    with pytest.raises(Stop) as stop:
        permission_of(value)
    assert needle in str(stop.value) and '권한 칸을 비우세요' in str(stop.value)
