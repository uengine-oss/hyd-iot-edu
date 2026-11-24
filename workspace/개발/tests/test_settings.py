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


def test_정해진_조회_단계에_붙은_학생_서버는_그_검사_도장의_읽기_도구만_미리_허용한다():
    """질문 · 교대 초안(정해진 조회 단계)에도 학생이 등록한 서버가 붙으면(run_servers 의 None) 그 서버는 검사 도장의 읽기 도구만 — 쓰기 도구와
    와일드카드는 없다. 기본 제공 서버는 표의 조회 도구 그대로."""
    plan = {'neo4j': list(QUESTION_READS['neo4j']), 'my-stock': None}
    allowed = allowed_for_run(DEFAULT, sorted(plan), {k: v for k, v in plan.items() if v is not None}, {'my-stock': ['find_stock']})
    mcp = {a for a in allowed if a.startswith('mcp__')}
    assert mcp == {f'mcp__neo4j__{t}' for t in QUESTION_READS['neo4j']} | {'mcp__my-stock__find_stock'}, mcp


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


BASE_TOOL_MARKS = ('import asyncio, json, enterprise_mcp.server as s; '
                   'print(json.dumps({n: bool(t.annotations and t.annotations.readOnlyHint) for n, t in asyncio.run(s.mcp.get_tools()).items()}))')


def test_이름_전체로_미리_허용하는_기본_제공_서버의_도구는_읽기이고_읽기가_아닌_것은_판단_카드_등록_둘뿐이다(monkeypatch):
    """전수검사 02-15: 기본 제공 서버는 도구 이름을 하나하나 적지 않고 서버 이름 전체(mcp__<서버>__*)로 미리 허용한다 — 그 서버에 쓰기 도구가 하나 생기면
    연결 검사 없이 승인 전에 불린다. 그 허용이 기대는 사실을 실제 서버의 도구 표시로 잰다: 업무 서버 셋(전체 묶음이 나눈 둘을 품는다 —
    test_enterprise_mcp_server)의 도구는 모두 읽기 표시이고, 판단 서비스에서 읽기가 아닌 도구는 판단 카드를 등록하는 둘뿐이다(설비 명령 · 업무 거래는
    승인 뒤 process 가 낸다 — CLAUDE.md 5절). 새 도구가 이 사실을 깨면 미리 허용 목록을 그 도구 이름으로 다시 정해야 한다."""
    import asyncio
    import json
    import os
    import subprocess
    import sys

    from conftest import HOST_ENV, ROOT
    wild = sorted(a[len('mcp__'):-len('__*')] for a in DEFAULT if a.endswith('__*'))
    assert wild == ['enterprise', 'enterprise-maint', 'enterprise-purchase', 'hyd-dmn']
    # 도구 표시만 읽는다 — 서버는 켜질 때 업무 DB 읽기 주소가 있는지만 보고(없으면 까닭을 말하며 켜지지 않는다) 도구를 부를 때 연결한다. 이 주소로는 연결하지 않는다
    env = dict(HOST_ENV, PYTHONUTF8='1', ENTERPRISE_MCP_TOOLSET='all', ENTERPRISE_DSN='postgresql://reader@127.0.0.1:1/unused',
               PYTHONPATH=os.pathsep.join([str(ROOT / 'common'), str(ROOT / 'it' / 'enterprise-mcp')]))
    done = subprocess.run([sys.executable, '-c', BASE_TOOL_MARKS], capture_output=True, env=env, timeout=120)
    assert done.returncode == 0, done.stderr.decode('utf8', 'replace')[-800:]
    marks = json.loads(done.stdout.decode().splitlines()[-1])
    assert marks and all(marks.values()), sorted(n for n, read in marks.items() if not read)
    monkeypatch.setenv('DAQ_PROFILE', 'lite')            # compose 가 dmn-mcp 에 넘기는 값
    from dmn_mcp import server
    tools = asyncio.run(server.mcp.get_tools())
    assert sorted(n for n, t in tools.items() if not (t.annotations and t.annotations.readOnlyHint)) == ['submit_decision', 'submit_purchase']
