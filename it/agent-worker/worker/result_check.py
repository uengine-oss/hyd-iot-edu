"""Read-only feedback on the fixed output file before the CLI ends its turn.

ontology-studio tools.batch_ingest parses the saved JSON and returns errors to
the agent. Here ingestion requires human review, so expose only parsing, with
no configurable path, graph access, writes, repair, or model call.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

SERVER = 'hyd-result'
TOOL = 'check_result_json'
INSTRUCTION = ('결과 파일 output/result.json을 Write/Edit로 고친 뒤에는 '
               'mcp__hyd-result__check_result_json 도구로 실제 파일 문법을 검사하세요. '
               'ok=false면 오류 위치를 고치고 다시 검사하되 검사·수정 반복은 최대 3회입니다. '
               'ok=true는 JSON 문법만 확인한 것이며 의미 검증·사람 승인·적재 완료가 아닙니다. '
               '실패가 남으면 고쳤다고 주장하지 말고 남은 오류를 보고하세요.')


def check(workdir, max_bytes):
    root = Path(workdir).resolve()
    path = root/'output/result.json'
    try:
        if path.resolve() != path.absolute():
            return {'ok': False, 'error': '결과 파일의 심볼릭 링크/다른 경로 참조는 허용하지 않습니다'}
        with path.open('rb') as stream:
            raw = stream.read(max_bytes+1)
        if len(raw) > max_bytes:
            return {'ok': False, 'error': '결과 파일 크기 상한 초과', 'max_bytes': max_bytes}
    except OSError:
        return {'ok': False, 'error': 'output/result.json 파일을 읽을 수 없습니다'}
    digest = hashlib.sha256(raw).hexdigest()
    try:
        def non_json_constant(value):
            raise ValueError('JSON은 NaN/Infinity 상수를 허용하지 않습니다')
        value = json.loads(raw.decode('utf-8-sig'), parse_constant=non_json_constant)
    except UnicodeError:
        return {'ok': False, 'error': '결과 파일은 UTF-8이어야 합니다', 'sha256': digest}
    except json.JSONDecodeError as exc:
        from .outcome import _json_syntax_hint
        return {'ok': False, 'error': exc.msg, 'line': exc.lineno, 'column': exc.colno,
                'hint': _json_syntax_hint(raw.decode('utf-8-sig'), exc)[:1400], 'sha256': digest}
    except (ValueError, RecursionError):
        return {'ok': False, 'error': '비표준 상수 또는 과도한 중첩으로 JSON을 읽을 수 없습니다', 'sha256': digest}
    if not isinstance(value, dict):
        return {'ok': False, 'error': '결과 최상위는 JSON 객체여야 합니다', 'sha256': digest}
    return {'ok': True, 'scope': 'JSON syntax only; no semantic validation or approval',
            'bytes': len(raw), 'sha256': digest}


def attach(config, workdir, max_bytes):
    config = dict(config or {})
    servers = dict(config.get('mcpServers') or {})
    # Reserved worker-owned tool. A student's server entry cannot replace it.
    servers[SERVER] = {'command': sys.executable, 'args': ['-m', 'worker.result_check',
                        '--workspace', str(Path(workdir).resolve()), '--max-bytes', str(max_bytes)],
                       'env': {'PYTHONPATH': os.pathsep.join(filter(None, [
                           str(Path(__file__).resolve().parents[1]), os.environ.get('PYTHONPATH','')]))}}
    config['mcpServers'] = servers
    return config


def server(workdir, max_bytes):
    from fastmcp import FastMCP
    mcp = FastMCP('HYD result syntax check')

    @mcp.tool(name=TOOL, annotations={'readOnlyHint': True, 'destructiveHint': False})
    def check_result_json() -> dict:
        """Parse this task's output/result.json; return bounded error locations or its hash.
        Does not repair, submit, approve, or ingest anything. Takes no path or content.
        """
        return check(workdir, max_bytes)

    return mcp


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--max-bytes', type=int, required=True)
    args = parser.parse_args()
    if not 0 < args.max_bytes <= 16*1024*1024:
        parser.error('invalid result size limit')
    server(args.workspace, args.max_bytes).run(transport='stdio')
