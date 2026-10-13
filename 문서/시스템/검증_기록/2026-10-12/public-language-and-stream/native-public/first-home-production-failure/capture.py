"""Prepared native public-language collector. Run only after ROOT DEPLOY DONE."""
from pathlib import Path
import argparse,json,hashlib,traceback,base64,time
from urllib.request import urlopen
from urllib.parse import quote
from playwright.sync_api import sync_playwright
O=Path(__file__).parent;R=O.parents[2];T=R/'.claude/worktrees/codex-portal-20261011'
API='http://127.0.0.1:8080';PORTAL='http://127.0.0.1:8088/'
CASES={'B':'c3_pm.d99ee952-f943-42fd-ba53-745b569522f7','C':'c3_spare.01a60b8d-284d-422b-96db-113dda3dd43f'}
def sha(b):return hashlib.sha256(b).hexdigest()
def save(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str),encoding='utf8')
def get(u):
    started=time.monotonic();entry={'url':u,'method':'GET','start_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    with (O/'get-timings.jsonl').open('a',encoding='utf8') as log:log.write(json.dumps(dict(entry,phase='start'))+'\n')
    try:
        with urlopen(u,timeout=45) as response:entry['status']=response.status;body=response.read();entry['bytes']=len(body);return body
    except Exception:entry['exception']=traceback.format_exc();raise
    finally:
        entry['duration_seconds']=time.monotonic()-started
        with (O/'get-timings.jsonl').open('a',encoding='utf8') as log:log.write(json.dumps(dict(entry,phase='finish'))+'\n')
def state(v):return {k:v.get(k) for k in ['instance','workitems','approvals','effects','reworks']}
def metadata(b):
    v=json.loads(b);return {'sha256':sha(b),'bytes':len(b),'status':v.get('instance',{}).get('status'),'business_sha256':sha(json.dumps(state(v),ensure_ascii=False,sort_keys=True).encode())}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--manifest',required=True);ap.add_argument('--owned-draft-id',required=True);ap.add_argument('--root-deploy-done',action='store_true',required=True);a=ap.parse_args()
    assert not (O/'result.json').exists(),'Preserve original run: choose a new collector output directory before retry'
    m=json.loads(Path(a.manifest).read_text(encoding='utf8'));freeze=m.get('source_sha256') or m.get('sha256') or m
    assert isinstance(freeze,dict) and 'it/portal/www/index.html' in freeze
    freeze={k:v for k,v in freeze.items() if isinstance(v,str) and (T/k).is_file()}
    def source():return {k:sha((T/k).read_bytes()) for k in freeze}
    r={'ok':False,'method':'Seven native actual GET screenshots; no DOM overlay, injected SSE or fixture','writes':[],'pageErrors':[],'consoleErrors':[],'captures':[],'checks':[],'manifest':str(Path(a.manifest).resolve())}
    business_stage=O/'business-stage-result.json'
    if business_stage.exists():
        verified=json.loads(business_stage.read_text(encoding='utf8'))
        assert len(verified['captures'])==3 and all(x['passed'] for x in verified['checks']) and verified['source_unchanged'] and all(verified['case_bytes_unchanged'].values())
        r['captures']=verified['captures'];r['checks']=verified['checks'];r['selected_cases']=verified['selected_cases'];r['reused_business_stage']={'path':str(business_stage),'sha256':sha(business_stage.read_bytes()),'new_capture':False}
        assert all(sha((O/x['png']).read_bytes())==x['sha256'] for x in verified['captures'])
    sb=source();assert sb==freeze,'Root final freeze mismatch before any live read'
    before={k:get(API+'/api/instances/'+pid) for k,pid in CASES.items()}
    agent_before=get(API+'/api/agents/'+quote('sys:agent',safe=''))
    assert a.owned_draft_id.startswith('codex-meeting-preflight-20261012-')
    draft_url=API+'/api/flows/'+quote(a.owned_draft_id,safe='');draft_before=get(draft_url);draft=json.loads(draft_before)
    save('owned-draft-before-metadata.json',{'id':a.owned_draft_id,'sha256':sha(draft_before),'bytes':len(draft_before)})
    save('before-metadata.json',{'source':sb,'cases':{k:metadata(b) for k,b in before.items()},'sys_agent':{'sha256':sha(agent_before),'bytes':len(agent_before)}})
    def check(name,condition):
        r['checks'].append({'name':name,'passed':bool(condition)});assert condition,name
    try:
        mounted={k:sha(get(PORTAL+k.removeprefix('it/portal/www/'))) for k in freeze if k.startswith('it/portal/www/')}
        save('mounted-source.json',mounted);check('Root final source is actually mounted',all(mounted[k]==freeze[k] for k in mounted))
        with sync_playwright() as p:
            browser=p.chromium.launch(args=['--disable-gpu']);page=browser.new_page(viewport={'width':1440,'height':1000},locale='ko-KR');page.set_default_navigation_timeout(90000)
            clock=time.monotonic();r['request_timings']=[];starts={}
            def started(q):starts[id(q)]=time.monotonic();r['request_timings'].append({'url':q.url,'method':q.method,'start_seconds':time.monotonic()-clock})
            def finished(q):r['request_timings'].append({'url':q.url,'duration_seconds':time.monotonic()-starts.get(id(q),time.monotonic()),'browser_timing':q.timing,'failure':q.failure})
            page.on('request',started);page.on('requestfinished',finished);page.on('requestfailed',finished)
            def route(q):
                if q.request.method not in ['GET','HEAD','OPTIONS']:r['writes'].append(q.request.url);q.abort()
                else:q.continue_()
            page.route('**/*',route);page.on('pageerror',lambda e:r['pageErrors'].append(str(e)));page.on('console',lambda m:r['consoleErrors'].append(m.text) if m.type=='error' else None)
            def reacquire(action):
                for attempt in range(5):
                    try:return action()
                    except Exception as e:
                        if attempt==4:raise
                        r.setdefault('native_reacquisitions',[]).append({'attempt':attempt+1,'reason':str(e)[:180]});page.wait_for_timeout(350)
            def navcheck():
                check('Navigation uses public condition/profit and performance labels',page.locator('[data-tab="whatif"]').inner_text()=='조건별 손익' and page.locator('[data-tab="kpi"]').inner_text()=='성과 지표')
            def shot(n,w,target):
                page.set_viewport_size({'width':w,'height':1000});reacquire(lambda:target().scroll_into_view_if_needed(timeout=5000));page.wait_for_timeout(250)
                text=target().inner_text();(O/(n+'.txt')).write_text(text,encoding='utf8');page.screenshot(path=str(O/(n+'.png')))
                r['captures'].append({'png':n+'.png','width':w,'sha256':sha((O/(n+'.png')).read_bytes()),'text_sha256':sha(text.encode())});return text
            owned=O/'owned-draft/result.json';prior=json.loads(owned.read_text(encoding='utf8'));check('Reuse unaffected actual owned warning without recapture',prior['ok'] is True)
            r['reused_owned_warning']={'result_path':str(owned),'sha256':sha(owned.read_bytes()),'revision':'Before final four-actor consumer correction; flow/backend unchanged','new_capture':False}
            for case,widths in ([] if business_stage.exists() else [('B',[1440,1024]),('C',[1440])]):
                page.goto(PORTAL+'#/instances/'+quote(CASES[case],safe=''),wait_until='domcontentloaded')
                page.wait_for_function('id=>window.hydInstances?.I.view?.instance?.proc_inst_id===id',arg=CASES[case],timeout=60000)
                page.wait_for_function("()=>window.hydInstances?.I.instances?.length>0&&!window.hydInstances.I.listError&&document.querySelectorAll('#instList .inst-card').length>0",timeout=30000)
                check(case+' native case list loaded without visible error','처리 건 목록을 읽지 못했습니다' not in page.locator('#instList').inner_text() and page.locator('#instList .inst-card').count()>0)
                check(case+' actual business remains completed',json.loads(before[case])['instance']['status']=='COMPLETED');navcheck()
                page.locator('[data-inst-tab="record"]').click()
                report=lambda:page.locator('#instRecord [data-cr-steps] > li').filter(has_text='결과 보고').last
                def openreport():
                    toggle=report().locator('[data-cr-toggle]')
                    if toggle.get_attribute('aria-expanded')=='false':toggle.click()
                    detail=report().locator('details.cr-sec').filter(has=page.locator('summary',has_text='보고 내용')).first
                    if detail.count() and detail.get_attribute('open') is None:detail.locator(':scope > summary').click()
                reacquire(openreport)
                raw=report().locator('details.raw').filter(has=page.locator('summary',has_text='결과 보고 원문')).first
                check(case+' raw report is collapsed',raw.get_attribute('open') is None)
                original=json.loads(raw.locator('pre').text_content());stored=json.loads(before[case])
                check(case+' raw report equals actual stored report',any(isinstance(w.get('output'),dict) and w['output'].get('result_report')==original for w in stored['workitems']))
                save(case+'-original-preservation.json',{'raw_collapsed':True,'exact_stored_match':True,'report_sha256':sha(json.dumps(original,ensure_ascii=False,sort_keys=True).encode())})
                for width in widths:
                    reacquire(openreport);text=shot(case+'-record-'+str(width),width,report)
                    alltext=page.locator('#instRecord').inner_text()
                    check(case+' system actor public label',('업무 처리' in alltext) and (('정비 관리' in alltext) if case=='B' else ('구매 · 재고 관리' in alltext)))
                    check(case+' ordinary report excludes old jargon','작업지시' not in text and 'Source-scoped maintenance orders registered' not in text)
                    r.setdefault('selected_cases',[]).append({'case':case,'id':page.evaluate('window.hydInstances.I.view.instance.proc_inst_id'),'width':width})
            if business_stage.exists():page.goto(PORTAL,wait_until='domcontentloaded')
            page.locator('[data-tab="agents"]').click();pick=page.locator('[data-pick-agent="sys:agent"]');pick.wait_for(state='visible');reacquire(lambda:pick.click())
            detail=lambda:page.locator('#agentsView [data-ag-detail]')
            page.wait_for_function("()=>document.querySelector('#agentsView [data-ag-detail] h2')?.innerText==='인공지능 에이전트'",timeout=30000)
            raw_source=json.loads(agent_before);save('agent-original-metadata.json',{'id':raw_source.get('id'),'original_name':raw_source.get('name'),'sha256':sha(agent_before),'user_source_values_unmodified':True})
            for width in [1440,1024]:
                text=shot('agents-sys-agent-'+str(width),width,detail)
                check('Built-in agent public title at '+str(width),detail().locator('h2').inner_text()=='인공지능 에이전트' and 'AI 에이전트 (Claude Code)' not in text)
                check('Exact agent list ID preserved',pick.get_attribute('data-pick-agent')=='sys:agent')
            page.locator('[data-tab="main"]').click();page.locator('#view-main').wait_for(state='visible')
            text=shot('main-1440',1440,lambda:page.locator('#view-main'));check('Home fixed technical Agent/node labels localized','AI Agent' not in text and 'AI 에이전트' in text)
            page.locator('[data-tab="whatif"]').click();page.locator('#view-whatif').wait_for(state='visible')
            text=shot('whatif-empty-1440',1440,lambda:page.locator('#view-whatif'));check('What-if native empty page public title','조건별 손익' in text and 'What-if' not in text)
            refs=T/'docs/handoff/verification/2026-10-12/final-delegated';files=[refs/'reference-processgpt.png',refs/'reference-dify.png',O/'B-record-1440.png']
            labels=['Preserved historical ProcessGPT reference','Preserved Dify documentation reference','Current actual HYD B native GET']
            html='<html><meta charset="utf-8"><body style="font:16px sans-serif"><div style="display:flex;gap:12px">';prov=[]
            for f,label in zip(files,labels):
                b=f.read_bytes();prov.append({'path':str(f),'sha256':sha(b),'label':label});html+=f'<section style="width:32%"><p>{label}</p><img style="width:100%" src="data:image/png;base64,{base64.b64encode(b).decode()}"></section>'
            (O/'comparison.html').write_text(html+'</div></body></html>',encoding='utf8');save('comparison-provenance.json',prov)
            page.set_viewport_size({'width':1800,'height':1000});page.goto((O/'comparison.html').as_uri());page.screenshot(path=str(O/'comparison.png'),full_page=True);browser.close()
    except Exception:r['exception']=traceback.format_exc()
    finally:
        after={k:get(API+'/api/instances/'+pid) for k,pid in CASES.items()};agent_after=get(API+'/api/agents/'+quote('sys:agent',safe=''));draft_after=get(draft_url);sa=source()
        save('owned-draft-after-metadata.json',{'id':a.owned_draft_id,'sha256':sha(draft_after),'bytes':len(draft_after)});r['owned_draft_bytes_unchanged']=draft_before==draft_after
        save('after-metadata.json',{'source':sa,'cases':{k:metadata(b) for k,b in after.items()},'sys_agent':{'sha256':sha(agent_after),'bytes':len(agent_after)}})
        r['source_unchanged']=sb==sa;r['case_bytes_unchanged']={k:before[k]==after[k] for k in CASES};r['agent_source_unchanged']=agent_before==agent_after
        r['ok']=not r.get('exception') and len(r['captures'])==7 and not r['writes'] and not r['pageErrors'] and not r['consoleErrors'] and r['source_unchanged'] and all(r['case_bytes_unchanged'].values()) and r['agent_source_unchanged'] and r['owned_draft_bytes_unchanged']
        save('result.json',r);print(json.dumps(r,ensure_ascii=False))
if __name__=='__main__':main()
