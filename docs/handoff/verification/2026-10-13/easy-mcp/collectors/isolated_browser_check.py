"""One real browser handshake against an isolated OAuth/MCP provider.

Uses the product's actual MCP UI and API with MemoryRepo. It is explicitly not
evidence of Google authorization, production business writes or a CLI/LLM run.
"""
from pathlib import Path
import base64, hashlib, json, os, secrets, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from urllib.parse import parse_qs, urlencode, urlsplit

T = Path('D:/work/study/hyd-iot-edu/.claude/worktrees/codex-portal-20261011')
H = Path('D:/work/study/hyd-iot-edu/.evidence/easy-mcp-20261013/native-isolated')
H.mkdir(parents=True, exist_ok=True)
sys.path[:0] = [str(T/'common'), str(T/'it/process')]
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from procsvc import mcp_api, mcp_oauth, mcp_secrets, procdb
from playwright.sync_api import sync_playwright
import uvicorn

P = 'http://127.0.0.1:8764'
BASE = 'http://127.0.0.1:8765'
RESOURCE = P+'/mcp'
ISSUER = P+'/auth'
TEST_KEY = 'isolated-example-service-key'
provider_calls = []
codes = {}

class Provider(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def send(self, status, body, headers=None):
        self.send_response(status)
        for k,v in (headers or {}).items(): self.send_header(k,v)
        raw = body.encode() if isinstance(body,str) else json.dumps(body).encode()
        self.send_header('Content-Length',str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
    def do_GET(self):
        u=urlsplit(self.path);q=parse_qs(u.query)
        provider_calls.append({'method':'GET','path':u.path})
        if u.path=='/mcp':
            self.send(401,{}, {'WWW-Authenticate':f'Bearer resource_metadata="{P}/resource", scope="read"'})
        elif u.path=='/resource':
            self.send(200,{'resource':RESOURCE,'authorization_servers':[ISSUER]})
        elif 'well-known/oauth-authorization-server' in u.path:
            self.send(200,{'issuer':ISSUER,'authorization_endpoint':P+'/authorize','token_endpoint':P+'/token','registration_endpoint':P+'/register','code_challenge_methods_supported':['S256']})
        elif u.path=='/authorize':
            args={k:v[0] for k,v in q.items()}
            code=secrets.token_urlsafe(16);codes[code]=args
            accept=args['redirect_uri']+'?'+urlencode({'state':args['state'],'code':code,'iss':ISSUER})
            deny=args['redirect_uri']+'?'+urlencode({'state':args['state'],'error':'access_denied','iss':ISSUER})
            self.send(200,'<!doctype html><meta charset=utf-8><h1>검증용 외부 서비스</h1><p>실제 Google 로그인 화면이 아닙니다.</p><a id="accept" href="'+accept+'">권한 동의</a> <a id="deny" href="'+deny+'">동의하지 않음</a>',{'Content-Type':'text/html; charset=utf-8'})
        elif u.path in ['/open/mcp','/key/mcp']:
            self.send(405,{})
        else: self.send(404,{})
    def do_POST(self):
        u=urlsplit(self.path)
        raw=self.rfile.read(int(self.headers.get('Content-Length','0')))
        body=parse_qs(raw.decode()) if self.headers.get('Content-Type','').startswith('application/x-www-form-urlencoded') else json.loads(raw or b'{}')
        provider_calls.append({'method':'POST','path':u.path,'rpc':body.get('method') if isinstance(body,dict) else None})
        if u.path=='/register': self.send(201,{'client_id':'isolated-client','token_endpoint_auth_method':'none'})
        elif u.path=='/token':
            code=(body.get('code') or [''])[0]
            old=codes.pop(code,None)
            verifier=(body.get('code_verifier') or [''])[0]
            challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
            if not old or challenge!=old['code_challenge']:
                self.send(400,{'error':'invalid_grant'})
            else:self.send(200,{'access_token':'isolated-access-token','refresh_token':'isolated-refresh-token','token_type':'Bearer','expires_in':3600})
        elif u.path in ['/mcp','/open/mcp','/key/mcp']:
            if u.path=='/mcp' and self.headers.get('Authorization')!='Bearer isolated-access-token':
                self.send(401,{}, {'WWW-Authenticate':f'Bearer resource_metadata="{P}/resource", scope="read"'});return
            if u.path=='/key/mcp' and self.headers.get('Authorization')!='Bearer '+TEST_KEY:
                self.send(401,{});return
            method=body.get('method');ident=body.get('id')
            if ident is None: self.send(202,'');return
            if method=='initialize': result={'protocolVersion':'2025-03-26','capabilities':{'tools':{}},'serverInfo':{'name':'isolated-provider','version':'1'}}
            elif method=='tools/list': result={'tools':[{'name':'read_status','description':'연결 확인 값을 읽습니다.','inputSchema':{'type':'object','properties':{}},'annotations':{'readOnlyHint':True}}]}
            elif method=='tools/call': result={'content':[{'type':'text','text':'검증용 서비스 연결 확인'}]}
            else:self.send(400,{});return
            self.send(200,{'jsonrpc':'2.0','id':ident,'result':result},{'Content-Type':'application/json'})
        else:self.send(404,{})
    def do_DELETE(self):self.send(204,'')

def main():
    os.environ['HYD_MCP_OAUTH_KEY']=Fernet.generate_key().decode()
    os.environ['HYD_MCP_OAUTH_CALLBACK_URL']=BASE+'/api/mcp/connections/callback'
    os.environ['HYD_MCP_OAUTH_PRIVATE_ORIGINS']=P
    repo=procdb.MemoryRepo();repo.upsert_tenant({'id':'hyd','mcp':{'mcpServers':{}}})
    rt=SimpleNamespace(repo=repo,tenant_id='hyd')
    audit=[]
    app=FastAPI()
    mcp_api.register(app,runtime_factory=lambda:rt,audit=lambda *a,**k:audit.append({'action':a[0] if a else None}))
    mcp_oauth.mount(app,runtime_factory=lambda:rt,audit=lambda *a,**k:audit.append({'action':a[0] if a else None}))
    mcp_secrets.mount(app,runtime_factory=lambda:rt,audit=lambda *a,**k:audit.append({'action':a[0] if a else None}))
    @app.get('/favicon.ico',status_code=204)
    def favicon():
        return HTMLResponse('',status_code=204)
    @app.get('/names.json')
    def names():
        return json.loads((T/'it/portal/www/names.json').read_text(encoding='utf-8'))
    @app.get('/')
    def index():
        return HTMLResponse('''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>격리된 연결 검증</title><link rel="stylesheet" href="/assets/tokens.css"><link rel="stylesheet" href="/assets/styles.css"><body><main class="main"><p>격리된 검증용 외부 서비스 · 실제 Google 계정 연결 증거가 아님</p><div id="mcpArea"></div></main><script>const API={process:location.origin};const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));async function getJ(url){const r=await fetch(url);if(!r.ok)throw new Error('조회 실패');return r.json()}async function postJ(url,b){const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)});const v=await r.json();if(!r.ok)throw new Error(v.detail?.reason||'처리 실패');return v}</script><script src="/assets/ui.js"></script><script src="/assets/plainWords.js"></script><script src="/assets/mcpConnections.js"></script><script src="/assets/mcp.js"></script><script>hydMcp.mount(document.querySelector('#mcpArea'));</script></body></html>''')
    app.mount('/assets',StaticFiles(directory=T/'it/portal/www'))
    provider=ThreadingHTTPServer(('127.0.0.1',8764),Provider)
    pthread=threading.Thread(target=provider.serve_forever,daemon=True);pthread.start()
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8765,log_level='warning',access_log=False))
    thread=threading.Thread(target=server.run,daemon=True);thread.start()
    result={'kind':'isolated actual HTTP OAuth/MCP + product component; no production writes/Google/LLM','checks':[],'screens':[],'page_errors':[],'console_errors':[]}
    names=['mcp.js','mcpConnections.js','ui.js','plainWords.js','tokens.css','styles.css']
    before_sha={name:hashlib.sha256((T/'it/portal/www'/name).read_bytes()).hexdigest() for name in names}
    def check(name,value):result['checks'].append({'name':name,'passed':bool(value)});assert value,name
    try:
        deadline=time.monotonic()+10
        while not server.started and time.monotonic()<deadline:time.sleep(.05)
        check('isolated API started',server.started)
        with sync_playwright() as p:
            browser=p.chromium.launch(args=['--disable-gpu'])
            page=browser.new_page(viewport={'width':1440,'height':1000},locale='ko-KR')
            page.on('pageerror',lambda e:result['page_errors'].append(str(e)))
            page.on('console',lambda m:result['console_errors'].append({'text':m.text,'location':m.location}) if m.type=='error' else None)
            result['http_errors']=[]
            page.on('response',lambda r:result['http_errors'].append({'path':urlsplit(r.url).path,'status':r.status}) if r.status>=400 else None)
            page.goto(BASE)
            page.locator('#mcpConnectService option[value="other"]').wait_for(state='attached',timeout=15000)
            check('operator settings initially closed',not page.locator('#mcpOperator').evaluate('(e)=>e.open'))
            page.locator('#mcpConnectService').select_option('other')
            page.locator('#mcpConnectUrl').fill(RESOURCE)
            with page.expect_popup(timeout=15000) as pending:
                page.locator('[data-connect-start]').click()
            popup=pending.value
            popup.locator('#accept').wait_for(timeout=15000)
            page.screenshot(path=str(H/'consent-wait-1440.png'));result['screens'].append('consent-wait-1440.png')
            popup.locator('#accept').click()
            page.locator('[data-connect-status]').filter(has_text='사용 가능').wait_for(timeout=15000)
            check('real OAuth callback then tools-check registered',len(repo.get_tenant('hyd')['mcp']['mcpServers'])==1)
            check('PKCE code exchanged once',sum(c['path']=='/token' for c in provider_calls)==1)
            check('actual MCP tools/list called',any(c.get('rpc')=='tools/list' for c in provider_calls))
            check('no tool execution needed for registering',not any(c.get('rpc')=='tools/call' for c in provider_calls))
            check('external consent completes without second check click',not page.locator('[data-connect-status]').inner_text().strip().startswith('로그인 필요'))
            page.screenshot(path=str(H/'connected-1440.png'));result['screens'].append('connected-1440.png')
            page.set_viewport_size({'width':1024,'height':1000})
            check('no horizontal overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            page.screenshot(path=str(H/'connected-1024.png'));result['screens'].append('connected-1024.png')
            page.locator('[data-connect-disconnect]').click()
            page.locator('dialog button[value="ok"]').click()
            page.locator('[data-connect-status]').filter(has_text='해제').wait_for(timeout=15000)
            check('disconnect removed only owned registered server',not repo.get_tenant('hyd')['mcp']['mcpServers'])
            with page.expect_popup(timeout=15000) as pending:
                page.locator('[data-connect-start]').click()
            popup=pending.value;popup.locator('#deny').wait_for(timeout=15000);popup.locator('#deny').click()
            page.locator('[data-connect-status]').filter(has_text='동의를 취소').wait_for(timeout=15000)
            check('denied consent never registers',not repo.get_tenant('hyd')['mcp']['mcpServers'])
            page.screenshot(path=str(H/'denied-1024.png'));result['screens'].append('denied-1024.png')
            page.locator('#mcpConnectUrl').fill(P+'/open/mcp')
            page.locator('[data-connect-start]').click()
            page.locator('[data-connect-status]').filter(has_text='사용 가능').wait_for(timeout=15000)
            check('no-auth MCP connected without consent popup',len(repo.get_tenant('hyd')['mcp']['mcpServers'])==1)
            page.locator('#mcpConnectUrl').fill(P+'/key/mcp')
            page.locator('[data-connect-start]').click()
            page.locator('#mcpConnectKey').wait_for(state='visible',timeout=15000)
            check('key-required server not registered prematurely',len(repo.get_tenant('hyd')['mcp']['mcpServers'])==1)
            page.locator('#mcpConnectKey').fill(TEST_KEY)
            page.locator('#mcpConnectKeyMode').select_option('bearer')
            page.locator('[data-connect-start]').click()
            page.locator('[data-connect-status]').filter(has_text='사용 가능').wait_for(timeout=15000)
            check('API-key MCP registered after real tools-check',len(repo.get_tenant('hyd')['mcp']['mcpServers'])==2)
            check('API key cleared from input after use',page.locator('#mcpConnectKey').input_value()=='')
            page.screenshot(path=str(H/'key-connected-1024.png'));result['screens'].append('key-connected-1024.png')
            check('no page errors',not result['page_errors'])
            check('no console errors',not result['console_errors'])
            check('captured product sources unchanged',before_sha=={name:hashlib.sha256((T/'it/portal/www'/name).read_bytes()).hexdigest() for name in names})
            browser.close()
        result['ok']=True
    finally:
        result['provider_calls']=provider_calls
        result['source_sha']={name:hashlib.sha256((T/'it/portal/www'/name).read_bytes()).hexdigest() for name in ['mcp.js','mcpConnections.js','ui.js','plainWords.js','tokens.css','styles.css']}
        result['google_account_authorized']=False;result['production_writes']=0;result['llm_runs']=0
        (H/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        server.should_exit=True;thread.join(timeout=10);provider.shutdown();provider.server_close();pthread.join(timeout=5)
        print(json.dumps({'ok':result.get('ok',False),'checks':result['checks'],'screens':result['screens'],'servers_stopped':not thread.is_alive() and not pthread.is_alive()},ensure_ascii=False))

if __name__=='__main__':main()
