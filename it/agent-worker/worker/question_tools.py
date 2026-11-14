"""「에이전트에게 질문」 전용 MCP 창구: 수업이 허용한 조회 도구(hydcommon.handover_tools.QUESTION_READS)만 보이고 실행한다.

도구 호출은 process 의 MCP 도구 실행 API(/api/mcp/servers/<서버>/tools/<도구>/call)로 간다 — 서버 설정 · 비밀은 process 만 쥔다.
CLI 에는 서버마다 stdio 창구(python -m worker.question_tools)를 붙이고, 창구는 목록 파일에 적힌 허용 도구만 연다.
"""
from hydcommon.words import particle
import asyncio
import json
import os
from pathlib import Path
import sys
from urllib.parse import quote

import httpx
from hydcommon.handover_tools import question_read
from .course_access import RuntimeConnectionError, process_base as _base


class Refused(Exception):
    """The process answered with a 4xx reason (input contract, classroom policy)."""


def _request(method, url, *, body=None, transport=None):
    try:
        with httpx.Client(transport=transport, timeout=30, follow_redirects=False, trust_env=False) as client:
            with client.stream(method, url, json=body) as response:
                raw = bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 1_000_000:raise ValueError()
                status = response.status_code
        result = json.loads(raw)
        if not isinstance(result, dict):raise ValueError()
    except Exception:
        raise RuntimeConnectionError('질문 조회 도구 연결이나 결과를 확인할 수 없습니다') from None
    if 400 <= status < 500 and isinstance(result.get('detail'), str) and result['detail'].strip():
        raise Refused(result['detail'].strip()[:2000])
    if status != 200:
        raise RuntimeConnectionError('질문 조회 도구 연결이나 결과를 확인할 수 없습니다')
    return result


def attach(reads, workdir, url, *, transport=None):
    """reads: 이 질문에 쓰는 서버와 정해진 조회 도구 {서버: [도구 …]} — 규칙 한 곳(procsvc/agents_store.run_servers, 질문 폼 계약의
    QUESTION_READS)이 정한 그대로. 서버마다 process 의 도구 목록을 받아 그 가운데 정해진 조회 도구만(실제로 있고 부를 수 있는 것) 창구에 연다.
    목록 밖 서버를 여기서 거르지 않는다 — 고르는 일은 run_servers 가 했다(예전 사본 튜플이 정기 정비 · 구매 에이전트의 질문을 「수업에 허용되지
    않은 도구 서버」로 멈췄다, 검진 G1-02)."""
    base = _base(url)
    if not isinstance(reads, dict):
        raise RuntimeConnectionError('질문 조회 서버 설정을 확인하세요')
    catalog, names = [], {}
    for server in sorted(reads):
        allowed = {t for t in reads[server] or () if question_read(server, t)}
        try:payload = _request('GET', base+'/api/mcp/servers/'+quote(server,safe='')+'/tools', transport=transport)
        except Refused as refused:raise RuntimeConnectionError(f'질문에 쓸 도구 서버 {server}의 도구 목록을 받지 못했습니다 — {refused}') from None
        if payload.get('status') != 'ok' or not isinstance(payload.get('tools'), list):
            raise RuntimeConnectionError(f'질문에 쓸 도구 서버 {server}{particle(server, "이")} 연결되지 않았습니다 — 도구 연결 화면에서 연결 상태를 확인하세요')
        for tool in payload['tools']:
            if not isinstance(tool, dict):raise RuntimeConnectionError('질문 조회 도구 목록이 올바르지 않습니다')
            name = tool.get('name')
            if name not in allowed or not tool.get('callable'):continue
            schema = tool.get('input_schema')
            if not isinstance(schema, dict) or schema.get('type') != 'object':
                raise RuntimeConnectionError('질문 조회 도구 입력 형식이 올바르지 않습니다')
            catalog.append({'server':server, 'name':name, 'description':tool.get('description') or '', 'inputSchema':schema})
            names.setdefault(server, []).append(name)
        if server not in names:raise RuntimeConnectionError(f'도구 서버 {server}에 질문에 쓸 수 있는 조회 도구가 없습니다')
    path = Path(workdir)/'question-tool-catalog.json'
    path.write_text(json.dumps(catalog,ensure_ascii=False),encoding='utf8')
    servers = {server:{'command':sys.executable,
        'args':['-m','worker.question_tools','--server',server,'--catalog',str(path),'--url',base],
        'env':{'PYTHONPATH':os.pathsep.join(filter(None,[str(Path(__file__).resolve().parents[1]),os.environ.get('PYTHONPATH','')]))}}
        for server in names}
    return {'mcpServers':servers}, names


#: 이 창구가 process 의 도구 실행 API 를 부를 때 밝히는 「누가」 — 사람이 아니라 AI 에이전트 실행(사용자 표의 시스템 행 sys:agent)이다.
#: 그 API 는 호출 기록에 남길 「누가」가 없는 요청을 받지 않는다(procsvc.inbox.actor_or_400 — 사람 이름을 지어 넣지 않게). 이 길에는 작업 토큰이
#: 없다: 창구는 CLI 가 띄운 프로세스이고, 읽기 판정(읽기 도구만)은 process 가 호출마다 다시 한다. 비우면 「담당자 정보 없이 온 요청」으로
#: 거절돼 키 있는 PC 의 질문하기에서 AI 의 조회가 모두 실패했다.
CALLER = 'sys:agent'


class Transport:
    def __init__(self, url, *, transport=None):self.url,self.transport = _base(url),transport
    def call(self, qualified, arguments):
        server, sep, name = qualified.partition('/')
        if not sep or not question_read(server, name):raise RuntimeConnectionError('질문에 허용되지 않은 조회 도구입니다')
        try:
            result = _request('POST',self.url+'/api/mcp/servers/'+quote(server,safe='')+'/tools/'+quote(name,safe='')+'/call',
                              body={'arguments':arguments,'timeout':25,'by':CALLER},transport=self.transport).get('result')
        except Refused as refused:
            return {'state':'FAILED','result':str(refused)}
        if not isinstance(result,dict):raise RuntimeConnectionError('조회 결과 형식이 올바르지 않습니다')
        text = result.get('text')
        # The tool's own refusal goes back to the model so it can correct its
        # arguments (ProcessGPT deepagents tool_retry: error ToolMessage, not a
        # stopped run). A partial result is never handed over as data.
        if result.get('is_error'):
            message = text.strip()[:2000] if isinstance(text, str) and text.strip() else ''
            return {'state':'FAILED','result':message or '조회 도구가 이유 없이 실패했습니다'}
        if result.get('truncated'):
            return {'state':'FAILED','result':'조회 결과가 한도를 넘어 일부만 왔습니다. 조건·LIMIT·페이지로 범위를 줄여 다시 조회하세요'}
        if not isinstance(text, str):raise RuntimeConnectionError('조회 결과 형식이 올바르지 않습니다')
        if result.get('json') is True:
            try:value = json.loads(text)
            except (ValueError, TypeError):raise RuntimeConnectionError('조회 결과 JSON을 확인할 수 없습니다') from None
        else:value = text
        return {'state':'DONE','result':value}


def server(name, tools, transport):
    """목록(tools)의 서버 name 도구를 원래 이름 · 입력 스키마 그대로 여는 FastMCP 창구. 실행은 transport.call(서버/도구, 인자)."""
    from fastmcp import FastMCP
    from fastmcp.tools import Tool
    from fastmcp.tools.tool import ToolResult
    from fastmcp.exceptions import ToolError
    from pydantic import PrivateAttr
    from mcp.types import TextContent, ToolAnnotations

    class CourseTool(Tool):
        _qualified: str = PrivateAttr()

        async def run(self, arguments):
            from procsvc.mcp_check import _argument_problem
            problem = _argument_problem({'input_schema': self.parameters}, arguments)
            if problem:
                raise ToolError('조회 인자가 도구 입력 스키마와 다릅니다: ' + problem['error'])
            try:
                value = await asyncio.to_thread(transport.call, self._qualified, arguments)
            except Exception:
                raise ToolError('현재 상태 조회에 실패했습니다. 다른 설비 상태로 대체하지 마세요') from None
            text = json.dumps(value.get('result'), ensure_ascii=False)
            if value['state'] == 'FAILED':
                raise ToolError(value['result'] if isinstance(value.get('result'), str) else text)
            return ToolResult(content=[TextContent(type='text', text=text)])

    app = FastMCP('HYD course question ' + name)
    for meta in tools:
        if meta['server'] != name:
            continue
        tool = CourseTool(name=meta['name'], description=meta['description'], parameters=meta['inputSchema'],
                          annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
        tool._qualified = name + '/' + meta['name']
        app.add_tool(tool)
    return app


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--server',required=True);parser.add_argument('--catalog',required=True);parser.add_argument('--url',required=True)
    args=parser.parse_args()
    rows=json.loads(Path(args.catalog).read_text(encoding='utf8'))
    # A modified catalog must not expand either discovery or execution.
    if not isinstance(rows,list) or any(not isinstance(r,dict) or not question_read(r.get('server'),r.get('name')) for r in rows):
        raise RuntimeError('수업 조회 목록이 올바르지 않습니다')
    server(args.server,rows,Transport(args.url)).run(transport='stdio')
