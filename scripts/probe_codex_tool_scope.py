"""Observe per-invocation apps=false without editing user configuration.

This checks the exposed MCP tool catalogue and three read calls. It does not
prove OS/network sandbox isolation or disable the CLI's built-in tools.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/p) for p in ('it/agent-worker','it/process','common')]
from cliagents import ExecRequest, Permission
from procsvc.procdb import PgRepo
from worker import bridge
from worker.runner import _resolve_provider, _exec_stream


def main():
    out=ROOT/'.evidence/reaudit'/('codex-tool-scope-'+uuid.uuid4().hex[:8]);out.mkdir()
    home=Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))
    config=home/'config.toml'
    before=hashlib.sha256(config.read_bytes()).hexdigest()
    tenant=PgRepo('postgresql://postgres:postgres@127.0.0.1:54322/postgres').get_tenant('hyd')
    bridged=bridge.install(out,tenant['mcp'],provider_id='codex',host_rewrite=bridge.parse_host_rewrite(
        'neo4j:7687=127.0.0.1:7687,enterprise-mcp:8199=127.0.0.1:8199,dmn-mcp:8198=127.0.0.1:8198'))
    prompt=('This is a tool-catalogue integration test. First use functions.exec to output exactly '
        'text(ALL_TOOLS.map(t=>t.name).filter(n=>n.startsWith("mcp__"))) without calling any listed tool. '
        'Then call neo4j get_neo4j_schema, enterprise query with {"sql":"SELECT COUNT(*) FROM ent.assets"}, '
        'and hyd-dmn inputs. Wait for and report all three results; if batching use Promise.allSettled. '
        'Do not call external app tools, shell, or write tools. Finish with short JSON of the observed counts only.')
    request=ExecRequest(prompt=prompt,workdir=str(out),model='gpt-5.6-sol',permission=Permission.READ_ONLY,
        extra_args=bridged.extra_args+['-c','model_reasoning_effort="low"'])
    deadline=time.monotonic()+240
    def check_stop():
        if time.monotonic()>deadline:raise TimeoutError('tool-scope probe deadline')
    sid=None; completed=[]
    with (out/'events.jsonl').open('w',encoding='utf-8') as f:
        for e in _exec_stream(_resolve_provider('codex'),request,bridged.env or None,check_stop=check_stop):
            f.write(json.dumps({'kind':e.kind.value,'text':e.text,'tool':e.tool,'session_id':e.session_id,'raw':e.raw},ensure_ascii=False,default=str)+'\n');f.flush()
            sid=e.session_id or sid
            item=e.raw.get('item') or {}
            if e.kind.value=='tool_end' and item.get('type')=='mcp_tool_call':completed.append(item)
    report={'session':sid,'config_unchanged':before==hashlib.sha256(config.read_bytes()).hexdigest(),'config_sha256':before,'completed_mcp_calls':completed,'passed':False}
    names=None
    for src in (home/'sessions').rglob(f'*{sid}.jsonl'):
        shutil.copy2(src,out/src.name)
        for line in src.read_text(encoding='utf-8').splitlines():
            payload=json.loads(line).get('payload',{})
            if payload.get('type')!='custom_tool_call_output':continue
            for block in payload.get('output',[]):
                if not isinstance(block,dict):continue
                try:value=json.loads(block.get('text',''))
                except (ValueError,TypeError):continue
                if isinstance(value,list) and value and all(isinstance(x,str) and x.startswith('mcp__') for x in value):names=value
    report['catalogue_mcp_names']=names
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    assert names,'no raw catalogue result was observed'
    assert all(n.startswith(('mcp__neo4j__','mcp__enterprise__','mcp__hyd_dmn__')) for n in names),names
    assert {i.get('server') for i in completed}=={'neo4j','enterprise','hyd-dmn'},completed
    assert all(i.get('status')=='completed' and not i.get('error') for i in completed), 'MCP failure; see preserved report'
    query_results=[i['result']['structured_content'] for i in completed if i['server']=='enterprise']
    assert any(r.get('result')=='ok' and r['document']['rows']==[[3]] for r in query_results), query_results
    assert report['config_unchanged']
    report['passed']=True
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('tool catalogue probe PASS',out,flush=True)


if __name__=='__main__':main()
