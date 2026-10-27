"""Question-only MCP facade: disclose and execute approved classroom reads only."""
import json
import os
from pathlib import Path
import sys
from urllib.parse import quote, urlsplit

import httpx
from hydcommon.handover_tools import question_read
from .runtime_credentials import RuntimeConnectionError


def _base(url):
    parsed = urlsplit(url)
    if (parsed.scheme != 'http' or parsed.hostname not in ('process', '127.0.0.1', 'localhost')
            or parsed.username or parsed.password or parsed.path not in ('', '/') or parsed.query or parsed.fragment):
        raise RuntimeConnectionError('수업 조회 연결 주소를 확인하세요')
    return url.rstrip('/')


def _request(method, url, *, body=None, transport=None):
    try:
        with httpx.Client(transport=transport, timeout=30, follow_redirects=False, trust_env=False) as client:
            with client.stream(method, url, json=body) as response:
                if response.status_code != 200:
                    raise ValueError()
                raw = bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 1_000_000:raise ValueError()
        result = json.loads(raw)
        if not isinstance(result, dict):raise ValueError()
        return result
    except Exception:
        raise RuntimeConnectionError('수업 조회 도구 연결이나 결과를 확인할 수 없습니다') from None


def attach(config, workdir, url, *, transport=None):
    base = _base(url)
    selected = ((config or {}).get('mcpServers') or {})
    if not isinstance(selected, dict):raise RuntimeConnectionError('수업 조회 서버 설정을 확인하세요')
    catalog, names = [], {}
    for server in sorted(selected):
        if not isinstance(server, str) or server not in ('neo4j', 'enterprise', 'hyd-dmn'):
            raise RuntimeConnectionError('수업에 허용되지 않은 도구 서버입니다')
        payload = _request('GET', base+'/api/mcp/servers/'+quote(server,safe='')+'/tools', transport=transport)
        if payload.get('status') != 'ok' or not isinstance(payload.get('tools'), list):
            raise RuntimeConnectionError('선택한 수업 조회 서버가 연결되지 않았습니다')
        for tool in payload['tools']:
            if not isinstance(tool, dict):raise RuntimeConnectionError('수업 조회 도구 목록이 올바르지 않습니다')
            name = tool.get('name')
            if not question_read(server, name) or not tool.get('callable'):continue
            schema = tool.get('input_schema')
            if not isinstance(schema, dict) or schema.get('type') != 'object':
                raise RuntimeConnectionError('수업 조회 도구 입력 형식이 올바르지 않습니다')
            catalog.append({'server':server, 'name':name, 'description':tool.get('description') or '', 'inputSchema':schema})
            names.setdefault(server, []).append(name)
        if server not in names:raise RuntimeConnectionError('선택한 서버에 허용된 조회 도구가 없습니다')
    path = Path(workdir)/'question-tool-catalog.json'
    path.write_text(json.dumps(catalog,ensure_ascii=False),encoding='utf8')
    servers = {server:{'command':sys.executable,
        'args':['-m','worker.question_tools','--server',server,'--catalog',str(path),'--url',base],
        'env':{'PYTHONPATH':os.pathsep.join(filter(None,[str(Path(__file__).resolve().parents[1]),os.environ.get('PYTHONPATH','')]))}}
        for server in names}
    return {'mcpServers':servers}, names


class Transport:
    def __init__(self, url, *, transport=None):self.url,self.transport = _base(url),transport
    def call(self, qualified, arguments):
        server, sep, name = qualified.partition('/')
        if not sep or not question_read(server, name):raise RuntimeConnectionError('허용되지 않은 수업 조회 도구입니다')
        result = _request('POST',self.url+'/api/mcp/servers/'+quote(server,safe='')+'/tools/'+quote(name,safe='')+'/call',
                          body={'arguments':arguments,'timeout':25},transport=self.transport).get('result')
        if not isinstance(result,dict) or result.get('is_error') or result.get('truncated'):
            raise RuntimeConnectionError('조회에 실패했거나 결과가 너무 깁니다')
        text = result.get('text')
        if not isinstance(text, str):raise RuntimeConnectionError('조회 결과 형식이 올바르지 않습니다')
        if result.get('json') is True:
            try:value = json.loads(text)
            except (ValueError, TypeError):raise RuntimeConnectionError('조회 결과 JSON을 확인할 수 없습니다') from None
        else:value = text
        return {'state':'DONE','result':value}


if __name__ == '__main__':
    import argparse
    from .managed_tools import server
    parser=argparse.ArgumentParser();parser.add_argument('--server',required=True);parser.add_argument('--catalog',required=True);parser.add_argument('--url',required=True)
    args=parser.parse_args()
    rows=json.loads(Path(args.catalog).read_text(encoding='utf8'))
    # A modified catalog must not expand either discovery or execution.
    if not isinstance(rows,list) or any(not isinstance(r,dict) or not question_read(r.get('server'),r.get('name')) for r in rows):
        raise RuntimeError('수업 조회 목록이 올바르지 않습니다')
    server(args.server,rows,Transport(args.url)).run(transport='stdio')
