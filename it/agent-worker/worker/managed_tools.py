"""MCP tools with their original names, executed against the student's state.

Only the instructor's claim-bound gateway supplies the catalog. No instructor
MCP endpoint survives attach(); failure never falls back to instructor data.
"""
import asyncio
import json
import os
from pathlib import Path
import sys
import time
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from .runtime_credentials import RuntimeConnectionError


class Transport:
    def __init__(self,url,token,*,transport=None,timeout=30):
        parsed=urlsplit(url)
        if (not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.scheme!='https' and not (parsed.scheme=='http' and parsed.hostname in {'classroom','localhost','127.0.0.1','::1'})):
            raise RuntimeConnectionError('관리 도구 주소가 올바르지 않습니다')
        if not isinstance(token,str) or not token.startswith('HydModel '):
            raise RuntimeConnectionError('관리 도구 실행 권한이 없습니다')
        if not 0 < timeout <= 30:
            raise ValueError('관리 도구 대기 한도는 30초 이내입니다')
        self.url,self.token,self.transport,self.timeout=url.rstrip('/'),token,transport,timeout

    def request(self,operation,body,*,timeout=None):
        duration=timeout or self.timeout
        async def load():
            async with httpx.AsyncClient(transport=self.transport,timeout=duration,follow_redirects=False) as client:
                async with client.stream('POST',self.url+'/internal/worker/tool-'+operation,
                                   headers={'Authorization':'Bearer '+self.token},json=body) as response:
                    if response.status_code!=200:raise ValueError()
                    raw=bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(raw)+len(chunk)>600000:raise ValueError()
                        raw.extend(chunk)
                    value=json.loads(raw)
                    if not isinstance(value,dict):raise ValueError()
                    return value
        async def bounded():
            return await asyncio.wait_for(load(),duration)
        try:
            return asyncio.run(bounded())
        except Exception:
            raise RuntimeConnectionError('관리 도구 연결 또는 실행 권한을 확인할 수 없습니다') from None

    def call(self,qualified,arguments):
        deadline=time.monotonic()+self.timeout
        reply=self.request('request',{'call_id':str(uuid4()),'tool':qualified,'arguments':arguments})
        from uuid import UUID
        request_id=str(UUID(reply['request_id']))
        while time.monotonic()<deadline:
            remaining=deadline-time.monotonic()
            result=self.request('result',{'request_id':request_id},timeout=max(0.01,remaining))
            if result.get('state') in ('DONE','FAILED'):
                return result
            if result.get('state')!='WAITING':
                raise RuntimeConnectionError('관리 도구 응답 상태가 올바르지 않습니다')
            time.sleep(min(0.5,max(0,deadline-time.monotonic())))
        raise RuntimeConnectionError('학생 현재 상태 조회의 대기 시간이 초과됐습니다')


def attach(managed,workdir,*,transport=None):
    if not managed:
        raise RuntimeConnectionError('관리 에이전트는 강사 실행 권한 없이 시작할 수 없습니다')
    client=Transport(managed['url'],managed['token'],transport=transport)
    tools=client.request('catalog',{}).get('tools')
    if not isinstance(tools,list) or len(tools)>64:
        raise RuntimeConnectionError('관리 도구 목록이 올바르지 않습니다')
    names={}
    from procsvc.classroom_proposals import TOOLS
    required={'server','name','description','inputSchema'}
    for tool in tools:
        if (not isinstance(tool,dict) or not required <= set(tool) or set(tool)-required-{'kind'}
                or not isinstance(tool['inputSchema'],dict)):
            raise RuntimeConnectionError('관리 도구 입력 계약이 올바르지 않습니다')
        qualified=str(tool['server'])+'/'+str(tool['name'])
        if ('kind' in tool and (tool['kind']!='proposal' or qualified not in TOOLS)
                or qualified in TOOLS and tool.get('kind')!='proposal'):
            raise RuntimeConnectionError('관리 제안 도구 분류가 올바르지 않습니다')
        names.setdefault(tool['server'],[]).append(tool['name'])
    path=Path(workdir)/'managed-tool-catalog.json'
    path.write_text(json.dumps(tools,ensure_ascii=False),encoding='utf8')
    servers={name:{'command':sys.executable,'args':['-m','worker.managed_tools','--server',name,'--catalog',str(path)],
        'env':{'HYD_TOOL_RUNTIME_URL':managed['url'],'HYD_TOOL_RUNTIME_TOKEN':managed['token'],
               'PYTHONPATH':os.pathsep.join(filter(None,[str(Path(__file__).resolve().parents[1]),os.environ.get('PYTHONPATH','')]))}}
        for name in names}
    return {'mcpServers':servers},names


def server(name,tools,transport):
    from fastmcp import FastMCP
    from fastmcp.tools import Tool
    from fastmcp.tools.tool import ToolResult
    from fastmcp.exceptions import ToolError
    from pydantic import PrivateAttr
    from mcp.types import TextContent,ToolAnnotations

    class StudentTool(Tool):
        _qualified: str=PrivateAttr()
        async def run(self,arguments):
            from procsvc.mcp_check import _argument_problem
            if _argument_problem({'input_schema':self.parameters},arguments):
                raise ToolError('조회 인자가 승인 도구 입력 스키마와 다릅니다')
            try:
                value=await asyncio.to_thread(transport.call,self._qualified,arguments)
            except Exception:
                raise ToolError('학생 현재 상태 조회에 실패했습니다. 다른 설비 상태로 대체하지 마세요') from None
            text=json.dumps(value.get('result'),ensure_ascii=False)
            if value['state']=='FAILED':raise ToolError(text)
            return ToolResult(content=[TextContent(type='text',text=text)])

    app=FastMCP('HYD managed student '+name)
    for meta in tools:
        if meta['server']!=name:continue
        tool=StudentTool(name=meta['name'],description=meta['description'],parameters=meta['inputSchema'],
                         annotations=ToolAnnotations(readOnlyHint=meta.get('kind')!='proposal',destructiveHint=False))
        tool._qualified=name+'/'+meta['name']
        app.add_tool(tool)
    return app


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--server',required=True);parser.add_argument('--catalog',required=True)
    args=parser.parse_args()
    rows=json.loads(Path(args.catalog).read_text(encoding='utf8'))
    server(args.server,rows,Transport(os.environ['HYD_TOOL_RUNTIME_URL'],os.environ['HYD_TOOL_RUNTIME_TOKEN'])).run(transport='stdio')
