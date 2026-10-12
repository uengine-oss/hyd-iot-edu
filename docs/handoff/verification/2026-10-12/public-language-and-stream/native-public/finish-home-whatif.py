from pathlib import Path
import json,hashlib,traceback,time,base64
from urllib.request import urlopen
from urllib.parse import quote
from playwright.sync_api import sync_playwright
O=Path(__file__).parent;R=O.parents[2];T=R/'.claude/worktrees/codex-portal-20261011';API='http://127.0.0.1:8080';URL='http://127.0.0.1:8088/'
def sha(b):return hashlib.sha256(b).hexdigest()
def save(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
def get(u):
    start=time.monotonic()
    try:
        with urlopen(u,timeout=45) as response:b=response.read();entry={'url':u,'status':response.status,'bytes':len(b)};return b
    except Exception:entry={'url':u,'exception':traceback.format_exc()};raise
    finally:
        with (O/'final-get-timings.jsonl').open('a',encoding='utf8') as f:f.write(json.dumps(dict(entry,seconds=time.monotonic()-start))+'\n')
frozen=json.loads((O.parent/'capture-manifest.json').read_text(encoding='utf8'))
def source():return {k:sha((T/k).read_bytes()) for k in frozen}
prior_path=O/'first-home-production-failure/result.json';prior=json.loads(prior_path.read_text(encoding='utf8'))
assert len(prior['captures'])==6 and prior['source_unchanged'] and all(prior['case_bytes_unchanged'].values()) and prior['agent_source_unchanged']
prior_source=json.loads((O/'first-home-production-failure/after-metadata.json').read_text(encoding='utf8'))['source']
sb=source();assert sb==frozen
changed=[k for k in sb if sb[k]!=prior_source[k]]
assert all(k in ['it/portal/www/main.js','it/portal/www/index.html','tests/js/test_public_display_language.js'] for k in changed),changed
captures=prior['captures'][:5];assert all(sha((O/x['png']).read_bytes())==x['sha256'] for x in captures)
r={'ok':False,'method':'Merged actual GET evidence by revision: preserved final B/C3 and agents2; new final home1/emptywhatif1 only; ownedwarning1 earlier unaffected revision','captures':captures,'checks':[c for c in prior['checks'] if c['passed']],'writes':[],'errors':[],'request_timings':[],'source_changed_from_previous_stage':changed,'previous_stage':{'path':str(prior_path),'sha256':sha(prior_path.read_bytes())},'reused_owned_warning':prior['reused_owned_warning']}
endpoints={'B':API+'/api/instances/c3_pm.d99ee952-f943-42fd-ba53-745b569522f7','C':API+'/api/instances/c3_spare.01a60b8d-284d-422b-96db-113dda3dd43f','sys_agent':API+'/api/agents/'+quote('sys:agent',safe=''),'owned_draft':API+'/api/flows/codex-meeting-preflight-20261012-6016ea04'}
before={k:get(u) for k,u in endpoints.items()};save('final-before-metadata.json',{'source':sb,'api':{k:{'sha256':sha(b),'bytes':len(b)} for k,b in before.items()}})
def check(n,c):r['checks'].append({'name':n,'passed':bool(c)});assert c,n
try:
    mounted={k:sha(get(URL+k.removeprefix('it/portal/www/'))) for k in sb if k.startswith('it/portal/www/')};check('Current changed static files actually mounted',all(mounted[k]==sb[k] for k in mounted));save('final-mounted-source.json',mounted)
    with sync_playwright() as p:
        browser=p.chromium.launch(args=['--disable-gpu']);page=browser.new_page(viewport={'width':1440,'height':1000},locale='ko-KR');page.set_default_navigation_timeout(90000)
        def route(q):
            if q.request.method not in ['GET','HEAD','OPTIONS']:r['writes'].append(q.request.url);q.abort()
            else:q.continue_()
        page.route('**/*',route);page.on('pageerror',lambda e:r['errors'].append(str(e)));page.on('console',lambda m:r['errors'].append(m.text) if m.type=='error' else None)
        page.on('requestfinished',lambda q:r['request_timings'].append({'url':q.url,'timing':q.timing,'failure':q.failure}));page.on('requestfailed',lambda q:r['request_timings'].append({'url':q.url,'timing':q.timing,'failure':q.failure}))
        page.goto(URL,wait_until='domcontentloaded');page.locator('[data-tab="main"]').click();main=page.locator('#view-main');main.wait_for(state='visible')
        svg=main.locator('.m-hero-svg');svg.wait_for(state='visible');label=svg.locator('.m-agent-t').text_content()+' '+svg.locator('.m-agent-s').text_content()
        check('Actual SVG supplied node label rendered in Korean',label=='인공지능 에이전트');check('Actual SVG no standalone old Agent',not any(x.strip()=='Agent' for x in svg.locator('text').all_text_contents()))
        check('Home public node names preserved','구매 · 재고' in svg.text_content() and '정비 관리' in svg.text_content())
        def shot(n,target):
            for attempt in range(5):
                try:target.scroll_into_view_if_needed(timeout=5000);break
                except Exception:
                    if attempt==4:raise
                    page.wait_for_timeout(300)
            page.wait_for_timeout(250);text=target.inner_text();(O/(n+'.txt')).write_text(text,encoding='utf8');page.screenshot(path=str(O/(n+'.png')));r['captures'].append({'png':n+'.png','width':1440,'sha256':sha((O/(n+'.png')).read_bytes()),'text_sha256':sha(text.encode())})
        shot('main-1440',main)
        page.locator('[data-tab="whatif"]').click();whatif=page.locator('#view-whatif');whatif.wait_for(state='visible');text=whatif.inner_text()
        check('Native empty condition/profit page public title','조건별 손익' in text and 'What-if' not in text);check('Public navigation','조건별 손익'==page.locator('[data-tab="whatif"]').inner_text() and '성과 지표'==page.locator('[data-tab="kpi"]').inner_text());shot('whatif-empty-1440',whatif)
        refs=T/'docs/handoff/verification/2026-10-12/final-delegated';files=[refs/'reference-processgpt.png',refs/'reference-dify.png',O/'main-1440.png',O/'B-record-1440.png'];labels=['Preserved historical ProcessGPT reference','Preserved Dify documentation reference','Current final HYD home native GET','Preserved actual HYD B after actor fix']
        html='<html><meta charset="utf-8"><body style="font:16px sans-serif"><div style="display:flex;gap:12px">';prov=[]
        for f,label in zip(files,labels):
            b=f.read_bytes();prov.append({'path':str(f),'sha256':sha(b),'label':label});html+=f'<section style="width:24%"><p>{label}</p><img style="width:100%" src="data:image/png;base64,{base64.b64encode(b).decode()}"></section>'
        (O/'comparison.html').write_text(html+'</div></body></html>',encoding='utf8');save('comparison-provenance.json',prov);page.set_viewport_size({'width':2000,'height':1000});page.goto((O/'comparison.html').as_uri());page.screenshot(path=str(O/'comparison.png'),full_page=True);browser.close()
except Exception:r['exception']=traceback.format_exc()
finally:
    after={k:get(u) for k,u in endpoints.items()};sa=source();save('final-after-metadata.json',{'source':sa,'api':{k:{'sha256':sha(b),'bytes':len(b)} for k,b in after.items()}})
    r['source_unchanged']=sb==sa;r['api_bytes_unchanged']={k:before[k]==after[k] for k in before};r['ok']=not r.get('exception') and len(r['captures'])==7 and all(r['api_bytes_unchanged'].values()) and r['source_unchanged'] and not r['writes'] and not r['errors'];save('result.json',r);print(json.dumps({k:v for k,v in r.items() if k!='request_timings'},ensure_ascii=False))
