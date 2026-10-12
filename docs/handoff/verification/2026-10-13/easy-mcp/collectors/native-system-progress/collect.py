"""Run ONLY after root freeze confirmation. Real disposable PG/HTTP/SSE/component."""
import argparse, hashlib, json, sys, threading, time, traceback
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

T = Path('D:/work/study/hyd-iot-edu/.claude/worktrees/codex-portal-20261011')
OUT = Path(__file__).parent
sys.path[:0] = [str(T/'it/process'), str(T/'common')]
DSN = 'postgresql://hyd_test:isolated-progress-test@127.0.0.1:55757/hyd_system_progress_test'

def save(name, value):
    (OUT/name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

def hashes():
    files = ['it/process/procsvc/'+n+'.py' for n in ('instances','instance_mode','service_parts','service_progress','procdb','engine','mcp_check')]
    files += ['it/portal/www/'+n for n in ('liveStream.js','ui.js','plainWords.js','trace.js','tokens.css','styles.css','instances.css','trace.css','theme.css','names.json')]
    return {f:hashlib.sha256((T/f).read_bytes()).hexdigest() for f in files if (T/f).exists()}

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--root-freeze-confirmed', action='store_true')
    args=parser.parse_args()
    if not args.root_freeze_confirmed: parser.error('Root backend freeze confirmation is mandatory')
    from procsvc import instances, engine, procdb, instance_mode, mcp_check
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, FileResponse, Response
    from fastapi.staticfiles import StaticFiles
    import uvicorn
    from playwright.sync_api import sync_playwright
    before=hashes(); save('source-before.json',before)
    result={'ok':False,'scope':'isolated actual PG → HTTP MCP → production SSE → native liveStream component', 'full_production':False,'google':False,'llm_calls':0}
    entered,release=threading.Event(),threading.Event(); requests=[]; errors=[]
    tenant='native-progress-'+uuid4().hex
    result['tenant']=tenant
    class MCP(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_POST(self):
            data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            method=data.get('method'); requests.append({'method':method,'at':time.time()})
            if 'id' not in data:
                self.send_response(202); self.send_header('Content-Length','0'); self.end_headers(); return
            if method=='initialize':
                value={'protocolVersion':'2024-11-05','capabilities':{'tools':{}},'serverInfo':{'name':'isolated-progress','version':'1'}}
            elif method=='tools/list':
                value={'tools':[{'name':'confirm_progress','description':'격리된 진행 확인','inputSchema':{'type':'object','properties':{'asset':{'type':'string'}},'required':['asset'],'additionalProperties':False},'annotations':{'readOnlyHint':True,'destructiveHint':False,'openWorldHint':False}}]}
            elif method=='tools/call':
                assert data['params']=={'name':'confirm_progress','arguments':{'asset':'isolated-asset'}}
                entered.set()
                if not release.wait(50): raise TimeoutError('Owned blocking tool was not released')
                value={'content':[{'type':'text','text':'격리된 실제 HTTP 응답을 확인했습니다'}],'isError':False}
            else: raise AssertionError(method)
            body=json.dumps({'jsonrpc':'2.0','id':data['id'],'result':value},ensure_ascii=False).encode()
            self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
    mcpserver=ThreadingHTTPServer(('127.0.0.1',8767),MCP)
    threading.Thread(target=mcpserver.serve_forever,daemon=True).start()
    repo=procdb.PgRepo(DSN); reader=procdb.PgRepo(DSN)
    with repo._conn() as c: c.execute('insert into tenants(id,name) values(%s,%s)',(tenant,'격리 실시간 진행 검증'))
    raw={'processDefinitionId':'native-system-progress-'+uuid4().hex,'processDefinitionName':'격리 실시간 진행 검증','version':'1',
         'events':[{'id':'start','type':'startEvent'},{'id':'end','type':'endEvent'}],
         'activities':[{'id':'service','name':'승인된 격리 도구 확인','type':'serviceTask','tool':'mcp:call','outputData':['mcp_receipt'],'service':{'server':'isolated','tool':'confirm_progress','arguments':{'asset':'{asset}'},'effect':True}}],
         'data':[{'name':n} for n in ('approved_by','chosen_option','asset','mcp_receipt')],
         'sequences':[{'id':'s1','source':'start','target':'service'},{'id':'s2','source':'service','target':'end'}]}
    defn=engine.Definition.from_dict(raw)
    spec={'transport':'streamable_http','url':'http://127.0.0.1:8767/mcp','headers':{}}
    def call(server,tool,arguments,key):
        assert server=='isolated'
        return mcp_check.call(spec,tool,arguments,timeout=60)
    rt=instances.InstanceRuntime(repo,defn,instances.Hooks(mcp_call=call),tenant_id=tenant,consumer='isolated-native-engine')
    inst=engine.new_instance(defn,{'approved_by':'explicit-isolated-test-approval','chosen_option':{'evaluation_mode':'execution','execution_checked':True},'asset':'isolated-asset'},tenant_id=tenant)
    inst['current_activity_ids']=['service']; repo.insert_instance(inst)
    wi={'id':str(uuid4()),'proc_inst_id':inst['proc_inst_id'],'tenant_id':tenant,'proc_def_id':defn.id,'version':'1','activity_id':'service','activity_name':'승인된 격리 도구 확인','status':'SUBMITTED','agent_orch':'hyd-process','user_id':'sys:process','consumer':rt.consumer,'tool':'mcp:call','retry':0,'output':None}
    repo.insert_workitems([wi]); inst=repo.get_instance(inst['proc_inst_id']); wi=repo.get_workitem(wi['id'])
    result.update(case=inst['proc_inst_id'],todo=wi['id'],approval=engine.variables(inst)['approved_by'])
    instance_mode._runtime=rt
    app=FastAPI(); instance_mode.mount(app,'instance'); app.mount('/static',StaticFiles(directory=str(T/'it/portal/www')),name='static')
    @app.get('/names.json')
    def names(): return FileResponse(T/'it/portal/www/names.json')
    @app.get('/favicon.ico')
    def favicon(): return Response(status_code=204)
    @app.get('/')
    def page():
        metadata=json.dumps({'I':{'instances':[inst],'view':{'workitems':[wi]}}},ensure_ascii=False)
        return HTMLResponse('''<!doctype html><html lang="ko"><meta charset="utf-8"><title>격리된 실시간 도구 진행 검증</title>
<link rel="stylesheet" href="/static/tokens.css"><link rel="stylesheet" href="/static/styles.css"><link rel="stylesheet" href="/static/instances.css"><link rel="stylesheet" href="/static/trace.css"><link rel="stylesheet" href="/static/theme.css">
<body style="display:block;overflow:auto;height:auto"><main style="padding:24px;overflow:visible"><h1>격리된 실시간 도구 진행 검증</h1><p>임시 PostgreSQL · 실제 HTTP 도구 · 제품 SSE/실시간 컴포넌트. 운영 업무 또는 Google 실행이 아닙니다.</p><section id="streamPanel"></section></main>
<script>const API={process:location.origin};const state={tab:'isolated'};const esc=v=>String(v??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));const getJ=async u=>{const r=await fetch(u);if(!r.ok)throw Error(r.status);return r.json()};window.hydInstances='''+metadata+''';</script>
<script src="/static/ui.js"></script><script src="/static/plainWords.js"></script><script src="/static/trace.js"></script><script src="/static/liveStream.js"></script>
<script>window.actualFrames=[];hydStream.subscribe((event,fresh)=>actualFrames.push({event,fresh,received_at:Date.now()}));</script></body></html>''')
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8766,log_level='warning'))
    thread=threading.Thread(target=server.run,daemon=True);thread.start()
    worker=None
    try:
        deadline=time.monotonic()+15
        while not server.started and time.monotonic()<deadline: time.sleep(.05)
        assert server.started
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True,args=['--disable-gpu']); page=browser.new_page(viewport={'width':1440,'height':1000})
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('console',lambda m: errors.append(m.text) if m.type=='error' else None)
            page.goto('http://127.0.0.1:8766/',wait_until='domcontentloaded',timeout=30000)
            page.wait_for_function('window.hydStream && hydStream.connected()',timeout=15000)
            def run():
                try: rt._run_service(inst,wi,datetime.now(timezone.utc))
                except Exception: errors.append(traceback.format_exc())
            worker=threading.Thread(target=run,daemon=True);worker.start()
            assert entered.wait(15),'Actual tools/call not entered'
            page.wait_for_function("document.querySelector('#streamList')?.innerText.includes('진행 중')",timeout=15000)
            assert page.locator('#streamList .stream-row.tool').is_visible()
            assert page.locator('#streamList .stream-row.tool').bounding_box()['y'] < 1000
            ev=reader.list_events(todo_id=wi['id']); starts=[e for e in ev if e['event_type']=='tool_usage_started']
            assert len(starts)==1 and not any(e['event_type']=='tool_usage_finished' for e in ev)
            assert reader.get_instance(inst['proc_inst_id'])['status']=='RUNNING'
            assert reader.get_workitem(wi['id'])['status']=='SUBMITTED'
            save('blocked-pg-proof.json',{'events':ev,'instance':reader.get_instance(inst['proc_inst_id']),'workitem':reader.get_workitem(wi['id'])})
            page.screenshot(path=str(OUT/'system-tool-running-1440.png'),full_page=True)
            release.set();worker.join(20);assert not worker.is_alive()
            page.wait_for_function("document.querySelector('#streamList')?.innerText.includes('도구 응답을 처리 건에 반영했습니다')",timeout=20000)
            ev=reader.list_events(todo_id=wi['id']);finish=[e for e in ev if e['event_type']=='tool_usage_finished'];close=[e for e in ev if e['job_id']=='SYSTEM_ATTEMPT_COMMITTED']
            assert len(finish)==len(close)==1 and finish[0]['data']['tool_use_id']==starts[0]['data']['tool_use_id']
            final=reader.get_instance(inst['proc_inst_id']);item=reader.get_workitem(wi['id'])
            assert final['status']=='COMPLETED' and item['status']=='DONE' and item['output']['mcp_receipt']['result']=='격리된 실제 HTTP 응답을 확인했습니다'
            frames=page.evaluate('actualFrames');own=[f for f in frames if f['event']['todo_id']==wi['id']]
            assert all(f['fresh'] for f in own) and {f['event']['id'] for f in own}>={starts[0]['id'],finish[0]['id'],close[0]['id']}
            assert page.locator('#streamList').inner_text().find('격리된 실제 HTTP 응답을 확인했습니다')>=0
            assert page.locator('#streamList .stream-row.tool').is_visible()
            overflow=page.evaluate('document.documentElement.scrollWidth>innerWidth');assert not overflow and not errors
            save('final-pg-proof.json',{'events':ev,'instance':final,'workitem':item})
            save('actual-sse-frames.json',frames)
            page.screenshot(path=str(OUT/'system-tool-finished-1440.png'),full_page=True)
            result.update(ok=True,tool_call_count=sum(r['method']=='tools/call' for r in requests),fresh_owned_frames=len(own),overflow=overflow)
            assert result['tool_call_count']==1
            browser.close()
    except Exception:
        result['failure']=traceback.format_exc()
        raise
    finally:
        release.set()
        if worker:worker.join(5)
        server.should_exit=True;thread.join(5);mcpserver.shutdown();mcpserver.server_close()
        after=hashes();save('source-after.json',after)
        result.update(source_unchanged=before==after,console_errors=errors,http_requests=requests)
        if before!=after:result['ok']=False
        save('result.json',result)

if __name__=='__main__':main()
