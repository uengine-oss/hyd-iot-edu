"""Public prose is persisted before the next CLI boundary; private reasoning is absent."""
from cliagents import ExecEvent, ExecEventKind
from worker.runner import Runner
from test_worker import _repo,_settings


def test_text_arrives_before_boundary_complete_and_untruncated(tmp_path,monkeypatch):
    clock=[0.0]
    monkeypatch.setattr('worker.runner.time.monotonic',lambda:clock[0])
    repo,inst=_repo();text='공개 설명 '*1800;observed=[]
    def records():
        return [e for e in repo.list_events(proc_inst_id=inst['proc_inst_id'])
                if (e.get('data') or {}).get('message_id')]
    def stream(provider,request,env):
        yield ExecEvent(kind=ExecEventKind.THINKING,text='private-marker')
        yield ExecEvent(kind=ExecEventKind.ASSISTANT_TEXT,text=text)
        observed.extend(records())
        assert observed and observed[-1]['data']['content']==text
        assert observed[-1]['data']['complete'] is False
        clock[0]+=.3
        yield ExecEvent(kind=ExecEventKind.ASSISTANT_TEXT,text='끝')
        assert records()[-1]['data']['content']==text+'끝'
        yield ExecEvent(kind=ExecEventKind.TOOL_START,tool='Read',tool_use_id='r',tool_input={})
        yield ExecEvent(kind=ExecEventKind.RESULT,text='{"cause":"c","failure_mode":"f","guide_card":{}}')
    runner=Runner(_settings(tmp_path),repo,exec_fn=stream,schema_prompt='s',resolve_provider=lambda _:object())
    assert runner.poll_once()==1
    rows=records();assert rows[-1]['data']['complete'] is True
    assert rows[-1]['data']['content']==text+'끝'
    assert len({e['data']['message_id'] for e in rows})==1
    assert [e['data']['sequence'] for e in rows]==[1,2,3]
    assert not any('private-marker' in str(e.get('data')) for e in repo.list_events(proc_inst_id=inst['proc_inst_id']))


def test_final_answer_snapshot_clears_duplicate_and_failure_preserves_prose(tmp_path):
    for failed in (False,True):
        repo,inst=_repo();answer='{"cause":"c","failure_mode":"f","guide_card":{}}'
        def stream(provider,request,env):
            yield ExecEvent(kind=ExecEventKind.ASSISTANT_TEXT,text=answer if not failed else '실패 전 공개 설명')
            if failed:raise RuntimeError('actual failure')
            yield ExecEvent(kind=ExecEventKind.RESULT,text=answer)
        Runner(_settings(tmp_path/str(failed)),repo,exec_fn=stream,schema_prompt='s',resolve_provider=lambda _:object()).poll_once()
        rows=[e for e in repo.list_events(proc_inst_id=inst['proc_inst_id']) if (e.get('data') or {}).get('message_id')]
        assert rows[-1]['data']['content']==('실패 전 공개 설명' if failed else '')
        assert rows[-1]['data']['complete'] is True


def test_high_frequency_deltas_keep_first_and_full_end_without_quadratic_writes(tmp_path,monkeypatch):
    clock=[0.0];monkeypatch.setattr('worker.runner.time.monotonic',lambda:clock[0])
    repo,inst=_repo()
    def stream(provider,request,env):
        for i in range(1000):
            clock[0]=i/10000
            yield ExecEvent(kind=ExecEventKind.ASSISTANT_TEXT,text='공개')
        raise RuntimeError('boundary absent')
    Runner(_settings(tmp_path),repo,exec_fn=stream,schema_prompt='s',resolve_provider=lambda _:object()).poll_once()
    rows=[e for e in repo.list_events(proc_inst_id=inst['proc_inst_id']) if (e.get('data') or {}).get('message_id')]
    assert len(rows)==2 and rows[0]['data']['content']=='공개'
    assert rows[-1]['data']['content']=='공개'*1000 and rows[-1]['data']['complete']
    assert sum(len(e['data']['content']) for e in rows)==2002


def test_portal_snapshot_replay_order_duplicates_runs_and_final_clear(tmp_path):
    import shutil,subprocess
    from pathlib import Path
    node=shutil.which('node');assert node, 'Node is required for the actual portal consumer contract'
    script=tmp_path/'snapshot.cjs'
    source=Path(__file__).resolve().parents[1]/'it/portal/www/trace.js'
    script.write_text('''const fs=require('fs'),assert=require('assert');
global.window={};global.UI={terms:{}};global.setInterval=()=>{};
eval(fs.readFileSync(process.argv[2],'utf8'));
const row=(seq,text,run='r')=>({id:String(seq)+run,timestamp:'now',todo_id:'task',job_id:'job',event_type:'task_working',data:{type:'text',public_run:run,message_id:run+':0',sequence:seq,content:text}});
const merge=window.hydTrace.publicNotes;
assert.equal(merge([row(2,'whole'),row(1,'first'),row(2,'whole')]).length,1);
assert.equal(merge([row(2,'whole'),row(1,'first')])[0].data.content,'whole');
assert.equal(merge([row(2,'whole')])[0].data.content,'whole');
assert.equal(merge([row(1,'one'),row(1,'two','other')]).length,2);
assert.equal(merge([row(1,'answer'),row(2,'')]).length,0);
const long='공개'.repeat(10000);assert.equal(merge([row(3,long)])[0].data.content,long);
''',encoding='utf8')
    result=subprocess.run([node,str(script),str(source)],capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stderr


def test_public_snapshot_database_to_actual_sse_generator_reconnect():
    import asyncio
    from procsvc import procdb
    from test_event_stream import _collect
    repo=procdb.MemoryRepo()
    events=[dict(id=str(n),timestamp=f'2026-10-12T00:00:0{n}+00:00',job_id='job',todo_id='task',event_type='task_working',
        data=dict(type='public_text',message_id='run:0',public_run='run',sequence=n,content='공개'*n,complete=False)) for n in (1,2)]
    repo.record_events(events[:1])
    frames=asyncio.run(_collect(repo,None,[lambda:repo.record_events(events[1:]),None]))
    assert [e['data']['content'] for _,e in frames]==['공개','공개공개']
    reconnect=asyncio.run(_collect(repo,events[0]['timestamp'],[None]))
    assert reconnect[-1][1]['data']['content']=='공개공개'
