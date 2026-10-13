"""Final native B result, incident lookup and preserved raw report; GET only."""
from pathlib import Path
import argparse
import json,hashlib,traceback
from urllib.request import urlopen,Request
from urllib.parse import quote
from playwright.sync_api import sync_playwright
O=Path(__file__).parent;H=O.parent;T=H.parent.parent/'.claude/worktrees/codex-portal-20261011'
CASE='c3_pm.d99ee952-f943-42fd-ba53-745b569522f7';API='http://127.0.0.1:8080';PORTAL='http://127.0.0.1:8088/'
def sha(b):return hashlib.sha256(b).hexdigest()
def save(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str),encoding='utf8')
def get(url,binary=False):
    with urlopen(Request(url,method='GET'),timeout=25) as r:return r.read() if binary else json.load(r)
def private(e):
    d=e.get('data') or {};return d.get('private') is True or d.get('visibility')=='private' or d.get('type') in ['thinking','reasoning','analysis'] or d.get('name')=='THINKING' or e.get('job_id')=='THINKING'
def public(v):return {**v,'events':[e for e in v.get('events',[]) if not private(e)]}
def state(v):return {k:v.get(k) for k in ['instance','workitems','approvals','effects','reworks']}
manifest=json.loads((H/'runtime-B-final-source-manifest.json').read_text(encoding='utf8'))
def source():return {p:sha((T/p).read_bytes()) for p in manifest}
r={'method':'Actual native result/report detail/raw fold at1440/1024; stored final result, no new business run','blockedWrites':[],'pageErrors':[],'consoleErrors':[],'captures':[],'incidentGET':[]}
parser=argparse.ArgumentParser();parser.add_argument('--raw-tail-only',action='store_true');args=parser.parse_args()
before=get(API+'/api/instances/'+CASE);save('case-before.json',public(before));frozen=source();save('source-before.json',frozen)
try:
    assert before['instance']['status']=='COMPLETED'
    assert frozen==manifest,'Source differs from root final freeze'
    mounted={p:sha(get(PORTAL+p.removeprefix('it/portal/www/'),True)) for p in ['it/portal/www/resultReport.js','it/portal/www/caseRecord.js']}
    save('mounted-consumers.json',mounted);assert all(manifest[p]==h for p,h in mounted.items())
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':1000},locale='ko-KR')
        def route(route):
            if route.request.method not in ['GET','HEAD','OPTIONS']:r['blockedWrites'].append(route.request.url);route.abort()
            else:route.continue_()
        page.route('**/*',route);page.on('pageerror',lambda e:r['pageErrors'].append(str(e)))
        page.on('console',lambda m:r['consoleErrors'].append(m.text) if m.type=='error' else None)
        def response(response):
            if '/api/incidents/' in response.url:
                r['incidentGET'].append({'url':response.url,'status':response.status,'method':response.request.method})
        page.on('response',response)
        page.goto(PORTAL+'#/instances/'+quote(CASE,safe=''),wait_until='domcontentloaded')
        page.wait_for_function('id=>window.hydInstances?.I.view?.instance?.proc_inst_id===id',arg=CASE,timeout=30000)
        page.locator('[data-inst-tab="record"]').click()
        row=page.locator('#instRecord [data-cr-steps] > li').filter(has_text='HYD-02 정기 정비 결과').last
        row.wait_for(state='visible')
        def shot(name,target,width):
            page.set_viewport_size({'width':width,'height':1000});target.scroll_into_view_if_needed();page.wait_for_timeout(250)
            text=target.inner_text();(O/(name+'.txt')).write_text(text,encoding='utf8');page.screenshot(path=str(O/(name+'.png')),full_page=False)
            r['captures'].append({'png':name+'.png','width':width,'sha256':sha((O/(name+'.png')).read_bytes()),'text_sha256':sha(text.encode())})
        normal=row.inner_text();assert 'Source-scoped maintenance orders registered' not in normal
        r['normal_display_text']=normal
        for width in ([] if args.raw_tail_only else [1440,1024]):shot('B-final-result-'+str(width),row,width)
        toggle=row.locator('[data-cr-toggle]')
        if toggle.get_attribute('aria-expanded')=='false':toggle.click()
        detail=row.locator('details.cr-sec').filter(has=page.locator('summary',has_text='보고 내용')).first
        if detail.get_attribute('open') is None:detail.locator(':scope > summary').click()
        page.wait_for_function("()=>[...document.querySelectorAll('#instRecord .cr-sec-body')].some(e=>e.innerText.includes('현재 사건')&&!e.innerText.includes('현재 사건 상태: 조회 중'))")
        detail_text=detail.inner_text();r['incident_display_text']=detail_text
        assert '이 보고에서 사건 종결 처리: 수행 안 함' in detail_text
        assert '현재 사건' in detail_text
        assert 'Source-scoped maintenance orders registered' not in detail_text
        for width in ([] if args.raw_tail_only else [1440,1024]):shot('B-final-report-detail-'+str(width),detail,width)
        raw=row.locator('details.raw').filter(has=page.locator('summary',has_text='결과 보고 원문')).first
        raw.locator(':scope > summary').click()
        original=json.loads(raw.locator('pre').inner_text());r['original_report']=original
        stored=[w['output']['result_report'] for w in before['workitems'] if isinstance(w.get('output'),dict) and w['output'].get('result_report')==original]
        assert stored,'Native original differs from actual stored workitem report'
        assert 'Source-scoped maintenance orders registered' in json.dumps(original,ensure_ascii=False)
        assert original.get('incident_closed') is False
        for width in [1440,1024]:
            if args.raw_tail_only:
                page.set_viewport_size({'width':width,'height':1000});raw.locator('pre').hover();page.mouse.wheel(0,800);page.wait_for_timeout(200)
                shot('B-final-report-original-tail-'+str(width),raw,width)
            else:shot('B-final-report-original-'+str(width),raw,width)
        browser.close()
except Exception:r['exception']=traceback.format_exc()
finally:
    after=get(API+'/api/instances/'+CASE);save('case-after.json',public(after));r['business_unchanged']=state(before)==state(after);r['source_unchanged']=frozen==source();save('source-after.json',source())
    r['passed']=not r.get('exception') and not r['blockedWrites'] and not r['pageErrors'] and not r['consoleErrors'] and r['business_unchanged'] and r['source_unchanged']
    save('raw-tail-result.json' if args.raw_tail_only else 'result.json',r);print(json.dumps(r,ensure_ascii=False))
