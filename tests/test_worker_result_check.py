import asyncio
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from fastmcp import Client

from worker import result_check
from worker.runner import Runner
from procsvc import manual_extraction
from test_manual_extraction import document, rt, _delivered_prompt
from test_worker import _settings, _fake_exec


def test_checker_reads_real_file_without_repair_or_semantic_approval(tmp_path):
    path = tmp_path/'output/result.json'
    path.parent.mkdir()
    broken = b'{"proposal":{"steps":[{"text":"keep original","anchor":{"page":1}}]}'
    path.write_bytes(broken)
    check = result_check.check(tmp_path, 4096)
    assert not check['ok'] and check['line'] == 1 and check['column'] > 1
    assert path.read_bytes() == broken
    path.write_bytes(b'{"proposal":{}}')
    checked = result_check.check(tmp_path, 4096)
    assert checked['ok'] and 'no semantic' in checked['scope']
    assert checked['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert not result_check.check(tmp_path, 1)['ok']
    path.unlink()
    assert not result_check.check(tmp_path, 4096)['ok']


def test_non_json_constants_are_not_reported_as_valid(tmp_path):
    path=tmp_path/'output/result.json';path.parent.mkdir()
    for constant in ('NaN','Infinity','-Infinity'):
        path.write_text('{"value":'+constant+'}')
        assert not result_check.check(tmp_path,4096)['ok']


def test_mcp_exposes_one_read_only_fixed_path_tool(tmp_path):
    path = tmp_path/'output/result.json'; path.parent.mkdir(); path.write_text('{}')
    async def run():
        async with Client(result_check.server(tmp_path, 4096)) as client:
            tools = await client.list_tools()
            assert [t.name for t in tools] == ['check_result_json']
            assert tools[0].inputSchema.get('properties', {}) == {}
            assert tools[0].annotations.readOnlyHint is True
            result = await client.call_tool('check_result_json', {})
            value = json.loads(result.content[0].text)
            assert value['ok'] and value['bytes'] == 2
    asyncio.run(run())
    assert path.read_text() == '{}'


def test_manual_worker_registers_checker_and_actual_allowed_tool(rt, document, tmp_path):
    runtime, _ = rt
    _, source, proposal = document
    manual_extraction.start(runtime, source, str(uuid4()))
    requests = []
    runner = Runner(_settings(tmp_path), runtime.repo,
                    exec_fn=_fake_exec(json.dumps({'proposal': proposal}), requests=requests),
                    schema_prompt='# schema', resolve_provider=lambda _: object())
    assert runner.poll_once() == 1 and requests
    request = requests[0][0]
    allowed = request.extra_args[request.extra_args.index('--allowedTools')+1]
    assert 'mcp__hyd-result__check_result_json' in allowed
    assert result_check.INSTRUCTION in _delivered_prompt(request, Path(request.workdir))
    config = json.loads((Path(request.workdir)/'.mcp.json').read_text(encoding='utf8'))
    helper = config['mcpServers']['hyd-result']
    assert helper['args'][:2] == ['-m','worker.result_check']
    assert helper['args'][3] == str(Path(request.workdir).resolve())


def test_student_entry_cannot_replace_worker_owned_checker(tmp_path):
    original = {'mcpServers': {'hyd-result': {'command': 'untrusted'}, 'other': {'command': 'kept'}}}
    attached = result_check.attach(original, tmp_path, 1234)
    assert attached['mcpServers']['hyd-result']['command'] != 'untrusted'
    assert original['mcpServers']['hyd-result']['command'] == 'untrusted'
    assert attached['mcpServers']['other'] == original['mcpServers']['other']
