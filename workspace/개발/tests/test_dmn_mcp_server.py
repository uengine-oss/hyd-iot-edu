"""판단 엔진 MCP 서버(it/dmn-mcp/dmn_mcp/server.py) — conftest stack 이 Dockerfile 실행 명령 그대로 띄운 dmn-mcp 하나가 hyd-dmn(/mcp)과
수업 neo4j 조회 도구(/neo4j/mcp)를 함께 낸다(H-4). 그래프는 kg-seed 와 같은 시드(seeded_graph), 부르는 쪽은 MCP 클라이언트(fastmcp).
"""
import asyncio
import json
import time

import httpx
import pytest
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport


def call(url, tool, args, headers=None):
    async def run():
        async with Client(StreamableHttpTransport(url, headers=headers or {})) as c:
            r = await c.call_tool(tool, args, raise_on_error=False)
            return r.is_error, r.content[0].text if r.content else ''
    return asyncio.run(run())


def listed(url):
    async def run():
        async with Client(StreamableHttpTransport(url)) as c:
            return sorted(t.name for t in await c.list_tools())
    return asyncio.run(run())


def test_neo4j_조회_도구는_dmn_mcp의_HTTP_주소에서_한도_안에_목록을_낸다(tool_servers, seeded_graph):
    """H-4: stdio 였을 때는 목록마다 파이썬을 새로 띄워 1.8~3.6초가 들고 process 의 4초 한도를 넘겨 학생 질문이 「연결 확인 필요」로 끝났다."""
    started = time.monotonic()
    names = listed(tool_servers['neo4j'])
    assert names == ['get_neo4j_schema', 'read_neo4j_cypher'] and time.monotonic() - started < 1.0


def test_hyd_dmn과_neo4j는_같은_프로세스의_다른_주소다(tool_servers, seeded_graph):
    assert tool_servers['neo4j'].rsplit('/neo4j/mcp', 1)[0] == tool_servers['hyd-dmn'].rsplit('/mcp', 1)[0]
    dmn = listed(tool_servers['hyd-dmn'])
    assert {'diagnose', 'evaluate_cards', 'submit_decision', 'submit_purchase'} <= set(dmn)


@pytest.mark.parametrize('query, error, text', [
    ('MATCH (a:Asset) RETURN a.id AS id ORDER BY id', False, '[{"id":"asset:hyd-01"},{"id":"asset:hyd-02"},{"id":"asset:hyd-03"}]'),
    ("CREATE (x:Probe {id: 'p'}) RETURN x", True, '읽기 전용 조회만 허용합니다'),
], ids=['읽기', '쓰기_거절'])
def test_neo4j_조회는_실제_그래프를_읽고_쓰기_Cypher는_거절한다(tool_servers, seeded_graph, query, error, text):
    is_error, out = call(tool_servers['neo4j'], 'read_neo4j_cypher', {'query': query})
    assert is_error is error and text in out
    assert seeded_graph.query("MATCH (x:Probe) RETURN count(x) AS n")[0]['n'] == 0


@pytest.mark.parametrize('header, reason', [
    ('{not json', '실행 헤더의 process_scope 가 JSON 이 아닙니다'),
    ('["list"]', '실행 헤더의 process_scope 가 객체가 아닙니다'),
], ids=['JSON_아님', '객체_아님'])
def test_실행_헤더의_process_scope가_틀리면_판단을_제출하지_않는다(tool_servers, seeded_graph, header, reason):
    is_error, out = call(tool_servers['hyd-dmn'], 'submit_decision',
                         {'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION', 'cause': 'cause:x', 'failure_mode': 'fm:x', 'incident': 'INC-1'},
                         headers={'x-hyd-process-scope': header})
    body = json.loads(out)
    assert not is_error and body['result'] == 'error' and body['error_kind'] == 'INVALID' and reason in body['message']


@pytest.mark.parametrize('incident', ['', '   '], ids=['빈_값', '공백'])
def test_처리_건_incident_없이는_판단을_제출하지_않는다(tool_servers, seeded_graph, incident):
    """W3-05: 처리 건 밖 판단은 승인할 곳이 없어 영원히 승인 대기로 남았다(구매 submit_purchase 와 같은 규칙)."""
    _, out = call(tool_servers['hyd-dmn'], 'submit_decision',
                  {'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION', 'cause': 'cause:x', 'failure_mode': 'fm:x', 'incident': incident})
    body = json.loads(out)
    assert body['result'] == 'error' and body['error_kind'] == 'INVALID' and 'incident' in body['message']


@pytest.mark.parametrize('args, field', [
    ({'asset': 'HYD-01', 'pattern': ''}, 'pattern'),
    ({'asset': '', 'pattern': 'COOLER_DEGRADATION'}, 'asset'),
    ({'asset': 'HYD-01', 'pattern': '  '}, 'pattern'),
], ids=['빈_경보_패턴', '빈_설비', '공백뿐인_경보_패턴'])
def test_설비나_경보_패턴이_빈_원인_진단은_진단하지_않고_빈_칸을_대며_거절한다(tool_servers, seeded_graph, args, field):
    """빈 이상 패턴이 진단까지 가서 「이 경보의 원인 지식이 지식 지도에 없어 …매뉴얼을 적재」로 엉뚱한 까닭을 냈다 — agent 의 규칙 판단 요청과 같은
    규칙(2026-11-24 3회차 실습 04): 빈 글은 그 칸 이름을 댄 입력 오류다."""
    is_error, out = call(tool_servers['hyd-dmn'], 'diagnose', args)
    assert is_error and field in out and '원인 지식' not in out and 'withheld' not in out, out


def test_건강_검사는_Neo4j에_닿으면_200이다(stack, seeded_graph):
    r = httpx.get(stack.services['dmn-mcp'].url + '/healthz', timeout=20)
    assert r.status_code == 200 and r.json() == {'ok': True, 'neo4j': True}
