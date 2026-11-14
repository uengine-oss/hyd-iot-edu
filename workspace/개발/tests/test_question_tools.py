"""「에이전트에게 질문」 전용 도구 창구(worker/question_tools.py) — 정해진 조회 도구(hydcommon.handover_tools.QUESTION_READS)만 열고,
호출은 process 의 도구 실행 API 로 간다. 실제 process(world) · 실제 도구 서버(dmn-mcp · neo4j 도구 · enterprise-mcp)와 실제 그래프.

CLI 가 띄우는 모양 그대로도 본다: attach() 가 준 설정(python -m worker.question_tools …)을 MCP stdio 로 띄워 목록 · 호출.
"""
import asyncio
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import ROOT, TENANT, _dockerfile, _python_path
from hydcommon.handover_tools import QUESTION_READS
from procsvc import agents_store
from worker import question_tools
from worker.course_access import RuntimeConnectionError

READ = 'neo4j/read_neo4j_cypher'


def listed(world, server):
    """process 가 지금 그 서버에서 받은 도구 목록(포털 도구 연결 화면과 같은 API) → {이름: 도구}."""
    status, body = world.api('GET', f'/api/mcp/servers/{server}/tools')
    assert status == 200 and body['status'] == 'ok', body
    return {t['name']: t for t in body['tools']}


def closed_url():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return f'http://127.0.0.1:{s.getsockname()[1]}'


@pytest.fixture
def image_path(monkeypatch):
    """워커 이미지(/srv)와 같은 패키지 자리 — Dockerfile COPY 의 hydcommon · procsvc · worker. 개발용 호스트 워커도 같은 PYTHONPATH 로 돈다."""
    path = os.pathsep.join(_python_path(_dockerfile('agent-worker')[0]))
    monkeypatch.setenv('PYTHONPATH', path)
    return path


def rows(value):
    """neo4j 조회 도구의 결과 글 → 행 목록(도구는 {"result": "<행 JSON>"} 로 낸다)."""
    while isinstance(value, (str, dict)):
        value = json.loads(value) if isinstance(value, str) else value['result']
    return value


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------- 창구 붙이기(attach)
def test_질문_창구는_정해진_조회_도구_가운데_process_가_부를_수_있다고_낸_것만_연다(world, tmp_path):
    reads = {server: list(tools) for server, tools in QUESTION_READS.items()}
    config, names = question_tools.attach(reads, tmp_path, world.url)
    expected = {s: {n for n, t in listed(world, s).items() if t['callable']} & set(tools) for s, tools in reads.items()}
    assert {s: set(v) for s, v in names.items()} == expected and all(expected.values())
    catalog = json.loads((tmp_path / 'question-tool-catalog.json').read_text(encoding='utf8'))
    assert sorted((c['server'], c['name']) for c in catalog) == sorted((s, n) for s, v in expected.items() for n in v)
    for c in catalog:
        assert c['inputSchema'] == listed(world, c['server'])[c['name']]['input_schema']
    for server, spec in config['mcpServers'].items():
        assert spec['command'] == sys.executable
        assert spec['args'] == ['-m', 'worker.question_tools', '--server', server, '--catalog', str(tmp_path / 'question-tool-catalog.json'),
                                '--url', world.url]
        assert spec['env']['PYTHONPATH'].split(os.pathsep)[0] == str(ROOT / 'it' / 'agent-worker')


def test_서버가_부를_수_있는_도구라도_질문_조회_목록_밖이면_열지_않는다(world, tmp_path):
    """질문 창구의 열쇠는 QUESTION_READS 한 곳 — 요청 목록(reads)에 적혀 와도 그 밖의 도구는 열지 않는다(정비용 업무 서버의 읽기 도구)."""
    callable_ = sorted(n for n, t in listed(world, 'enterprise-maint').items() if t['callable'])
    assert callable_, 'enterprise-maint 가 읽기 도구를 내지 않아 이 판정을 잴 수 없다'
    with pytest.raises(RuntimeConnectionError) as e:
        question_tools.attach({'enterprise-maint': callable_}, tmp_path, world.url)
    assert str(e.value) == '도구 서버 enterprise-maint에 질문에 쓸 수 있는 조회 도구가 없습니다'


def test_정기_정비_에이전트의_질문도_수업이_고른_서버만으로_붙는다(world, tmp_path):
    """G1-02: 붙일 서버를 워커가 따로 적은 튜플로 걸러 정기 정비 · 구매 에이전트의 질문이 「수업에 허용되지 않은 도구 서버」로 멈췄다.
    고르는 일은 agents_store.run_servers 한 곳 — 그 결과를 그대로 붙인다."""
    servers = {name: None for name in world.stack.tools}
    reads = agents_store.run_servers(['neo4j', 'hyd-dmn', 'enterprise-maint'], servers, agents_store.QUESTION_CONTRACT)
    _, names = question_tools.attach(reads, tmp_path, world.url)
    assert set(names) == set(reads) == {'neo4j', 'hyd-dmn'}


@pytest.mark.parametrize('reads, text', [
    ({'enterprise': ['fgb_no_such_tool']}, '도구 서버 enterprise에 질문에 쓸 수 있는 조회 도구가 없습니다'),
    ({'fgb-no-such-server': ['query']}, "질문에 쓸 도구 서버 fgb-no-such-server의 도구 목록을 받지 못했습니다 — MCP 서버 'fgb-no-such-server' 가 설정(tenants.mcp)에 없습니다"),
    (['neo4j'], '질문 조회 서버 설정을 확인하세요'),
], ids=['열 도구 없음', '설정에 없는 서버', '목록이 아님'])
def test_열_조회_도구가_없거나_서버가_설정에_없으면_까닭과_함께_멈춘다(world, tmp_path, reads, text):
    with pytest.raises(RuntimeConnectionError) as e:
        question_tools.attach(reads, tmp_path, world.url)
    assert str(e.value) == text and e.value.title == '연결 확인 필요'
    assert not (tmp_path / 'question-tool-catalog.json').exists()


def test_도구_서버가_답하지_않으면_연결_화면을_보라는_까닭으로_멈춘다(world, tmp_path):
    with world.stack.services['enterprise-mcp'].paused():
        with pytest.raises(RuntimeConnectionError) as e:
            question_tools.attach({'enterprise': ['query']}, tmp_path, world.url)
    assert str(e.value) == '질문에 쓸 도구 서버 enterprise가 연결되지 않았습니다 — 도구 연결 화면에서 연결 상태를 확인하세요'


@pytest.mark.parametrize('url', ['http://process.example.org:8080', 'http://user:pw@127.0.0.1:1', ''], ids=['바깥 HTTP', '사용자 정보', '빈 주소'])
def test_process_주소가_계약_밖이면_요청_없이_멈춘다(tmp_path, url):
    with pytest.raises(RuntimeConnectionError):
        question_tools.attach({'neo4j': ['read_neo4j_cypher']}, tmp_path, url)


def test_process_에_닿지_않으면_연결_확인_필요다(tmp_path):
    with pytest.raises(RuntimeConnectionError) as e:
        question_tools.attach({'neo4j': ['read_neo4j_cypher']}, tmp_path, closed_url())
    assert str(e.value) == '질문 조회 도구 연결이나 결과를 확인할 수 없습니다'


# ---------------------------------------------------------------- 호출(Transport.call — process 도구 실행 API)
def test_정해진_조회_도구는_process_를_거쳐_실제_결과를_받는다(world, course_graph):
    (expected,) = course_graph.query("MATCH (a:Asset {code: 'HYD-01'}) RETURN a.code AS code")
    reply = question_tools.Transport(world.url).call(READ, {'query': "MATCH (a:Asset {code: 'HYD-01'}) RETURN a.code AS code"})
    assert reply['state'] == 'DONE'
    assert rows(reply['result']) == [expected]


@pytest.mark.parametrize('arguments, text', [
    ({'query': 'RETURN'}, None),
    ({'query': "CREATE (n:FgbProbe) RETURN n"}, None),
    ({}, '도구 입력이 서버가 정한 입력 형식과 맞지 않습니다'),
], ids=['질의 문법 오류', '쓰기 질의', '입력 칸 빠짐'])
def test_도구나_process_가_거절한_호출은_모델이_고칠_수_있게_실패_결과로_돌려준다(world, course_graph, arguments, text):
    """ProcessGPT deepagents tool_retry 처럼 실행을 멈추지 않고 오류 글을 모델에게 돌려준다."""
    reply = question_tools.Transport(world.url).call(READ, arguments)
    assert reply['state'] == 'FAILED' and isinstance(reply['result'], str) and reply['result'].strip()
    if text:
        assert text in reply['result']
    assert course_graph.query('MATCH (n:FgbProbe) RETURN count(n) AS n') == [{'n': 0}]


@pytest.mark.parametrize('qualified', ['neo4j/write_neo4j_cypher', 'hyd-dmn/submit_decision', 'neo4j', 'fgb/read_neo4j_cypher'],
                         ids=['쓰기 도구', '판단 제출', '서버 이름만', '없는 서버'])
def test_질문_조회_목록_밖의_도구는_process_를_부르기_전에_거절한다(qualified):
    with pytest.raises(RuntimeConnectionError) as e:
        question_tools.Transport('http://127.0.0.1:1').call(qualified, {})      # 닿지 않는 주소 — 부르지 않으니 연결 오류가 아니다
    assert str(e.value) == '질문에 허용되지 않은 조회 도구입니다'


# ---------------------------------------------------------------- 창구 서버(FastMCP) — 목록 · 인자 검사 · 실패 글
def _catalog(world, tmp_path):
    question_tools.attach({'neo4j': list(QUESTION_READS['neo4j'])}, tmp_path, world.url)
    return json.loads((tmp_path / 'question-tool-catalog.json').read_text(encoding='utf8'))


def test_창구는_그_서버의_목록_도구만_원래_이름과_입력_형식으로_읽기_전용_표시와_함께_연다(world, tmp_path):
    from fastmcp import Client
    rows = _catalog(world, tmp_path) + [{'server': 'enterprise', 'name': 'query', 'description': '', 'inputSchema': {'type': 'object'}}]
    app = question_tools.server('neo4j', rows, question_tools.Transport(world.url))

    async def tools():
        async with Client(app) as client:
            return await client.list_tools()
    found = {t.name: t for t in run(tools())}
    assert set(found) == {r['name'] for r in rows if r['server'] == 'neo4j'}
    for row in rows[:-1]:
        assert found[row['name']].inputSchema == row['inputSchema']
        assert found[row['name']].annotations.readOnlyHint is True and found[row['name']].annotations.destructiveHint is False


def test_창구는_입력_형식과_다른_인자를_process_에_보내기_전에_거절한다(world, tmp_path):
    from fastmcp import Client
    from fastmcp.exceptions import ToolError
    app = question_tools.server('neo4j', _catalog(world, tmp_path), question_tools.Transport(closed_url()))

    async def call():
        async with Client(app) as client:
            await client.call_tool('read_neo4j_cypher', {'query': 7})
    with pytest.raises(ToolError) as e:
        run(call())
    assert '조회 인자가 도구 입력 스키마와 다릅니다' in str(e.value)


def test_process_에_닿지_않으면_창구는_다른_설비_상태로_대체하지_말라는_실패를_낸다(world, tmp_path):
    from fastmcp import Client
    from fastmcp.exceptions import ToolError
    app = question_tools.server('neo4j', _catalog(world, tmp_path), question_tools.Transport(closed_url()))

    async def call():
        async with Client(app) as client:
            await client.call_tool('read_neo4j_cypher', {'query': 'RETURN 1 AS one'})
    with pytest.raises(ToolError) as e:
        run(call())
    assert '현재 상태 조회에 실패했습니다' in str(e.value)


# ---------------------------------------------------------------- CLI 가 띄우는 그대로(stdio)
def test_CLI_가_띄우는_창구는_목록의_조회_도구만_보이고_호출은_process_결과를_낸다(world, course_graph, tmp_path, image_path):
    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport
    config, names = question_tools.attach({'neo4j': list(QUESTION_READS['neo4j'])}, tmp_path, world.url)
    spec = config['mcpServers']['neo4j']
    (expected,) = course_graph.query("MATCH (a:Asset {code: 'HYD-02'}) RETURN a.code AS code")

    async def session():
        async with Client(StdioTransport(spec['command'], spec['args'], env=dict(os.environ, **spec['env']))) as client:
            tools = sorted(t.name for t in await client.list_tools())
            result = await client.call_tool('read_neo4j_cypher', {'query': "MATCH (a:Asset {code: 'HYD-02'}) RETURN a.code AS code"})
            return tools, result.content[0].text
    tools, text = run(session())
    assert tools == sorted(names['neo4j'])
    assert rows(text) == [expected]


def test_고친_목록_파일로는_창구가_켜지지_않는다(tmp_path, image_path):
    """목록 파일은 작업 폴더에 있다 — CLI 가 고쳐 쓴 목록(질문 조회 밖 도구)으로는 발견도 실행도 넓어지지 않는다."""
    catalog = tmp_path / 'question-tool-catalog.json'
    catalog.write_text(json.dumps([{'server': 'hyd-dmn', 'name': 'submit_decision', 'description': '', 'inputSchema': {'type': 'object'}}]),
                       encoding='utf8')
    done = subprocess.run([sys.executable, '-m', 'worker.question_tools', '--server', 'hyd-dmn', '--catalog', str(catalog), '--url',
                           'http://127.0.0.1:1'], capture_output=True, timeout=120, env=dict(os.environ, PYTHONUTF8='1'))
    assert done.returncode != 0 and '수업 조회 목록이 올바르지 않습니다' in done.stderr.decode('utf8', 'replace')
