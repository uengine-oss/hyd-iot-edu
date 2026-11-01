"""수업 AI 조회 도구 허용 목록(common/hydcommon/handover_tools.py) — 목록의 도구는 실제 도구 서버에 있고 쓰기 도구는 없다(G3b-20 · G4-4).

판정: 실제 dmn-mcp 서버(it/dmn-mcp/dmn_mcp/server.py)에 등록된 도구 이름과 그 주석(READ · WRITE)을 그대로 읽어 견준다.
"""
import asyncio

from hydcommon.handover_tools import HANDOVER_READS, QUESTION_READS, question_read


def _dmn_tools(monkeypatch):
    monkeypatch.setenv('DAQ_PROFILE', 'lite')            # compose 가 dmn-mcp 에 넘기는 값
    from dmn_mcp import server
    tools = asyncio.run(server.mcp.get_tools())
    return {name: bool((t.annotations.readOnlyHint if t.annotations else False)) for name, t in tools.items()}


def test_질문_도구는_모두_dmn_mcp에_있는_읽기_도구다(monkeypatch):
    tools = _dmn_tools(monkeypatch)
    assert set(QUESTION_READS['hyd-dmn']) <= set(tools), set(QUESTION_READS['hyd-dmn']) - set(tools)
    assert all(tools[name] for name in QUESTION_READS['hyd-dmn'])
    assert not any(name.startswith('prometheus') for name in QUESTION_READS['hyd-dmn'])     # 기본 스택에 없는 서버의 도구


def test_교대_도구는_질문_도구의_일부이고_쓰기_도구는_어디에도_없다():
    for server, names in HANDOVER_READS.items():
        assert set(names) <= set(QUESTION_READS[server])
    assert not question_read('hyd-dmn', 'submit_decision') and not question_read('hyd-dmn', 'submit_purchase')
    assert question_read('neo4j', 'read_neo4j_cypher') and not question_read('enterprise-maint', 'query')
