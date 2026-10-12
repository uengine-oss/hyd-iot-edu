from pathlib import Path
import json, hashlib, traceback, base64
from urllib.request import urlopen
from urllib.parse import quote
from playwright.sync_api import sync_playwright
O=Path(__file__).parent; R=O.parents[2]; T=R/'.claude/worktrees/codex-portal-20261011'
CASE='c3_pm.d99ee952-f943-42fd-ba53-745b569522f7'; API='http://127.0.0.1:8080'; URL='http://127.0.0.1:8088/'
def sha(b): return hashlib.sha256(b).hexdigest()
def save(n,v): (O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
def get(u):
    with urlopen(u,timeout=30) as r: return r.read()
freeze=json.loads((O.parent/'labels-fix/result.json').read_text(encoding='utf8'))['sha256']
freeze={k:v for k,v in freeze.items() if not k.startswith('tests/')}
freeze['it/portal/www/index.html']=sha((T/'it/portal/www/index.html').read_bytes())
def sources(): return {k:sha((T/k).read_bytes()) for k in freeze}
def business(v): return {k:v.get(k) for k in ['instance','workitems','approvals','effects','reworks']}
r={'ok':False,'method':'Actual native GET only, two detail screenshots, no fixture/projection injection','writes':[],'errors':[],'captures':[]}
before=get(API+'/api/instances/'+CASE); bv=json.loads(before); sb=sources()
save('before-metadata.json',{'case':CASE,'api_sha256':sha(before),'bytes':len(before),'status':bv['instance']['status'],'source':sb})
try:
    assert sb==freeze and bv['instance']['status']=='COMPLETED'
    mounted={k:sha(get(URL+k.removeprefix('it/portal/www/'))) for k in freeze if k.startswith('it/portal/www/')}
    assert all(mounted[k]==freeze[k] for k in mounted)
    r['mounted_sha256']=mounted
    with sync_playwright() as p:
        browser=p.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':1000},locale='ko-KR')
        def route(q):
            if q.request.method not in ['GET','HEAD','OPTIONS']: r['writes'].append(q.request.url);q.abort()
            else:q.continue_()
        page.route('**/*',route);page.on('pageerror',lambda e:r['errors'].append(str(e)))
        page.on('console',lambda m:r['errors'].append(m.text) if m.type=='error' else None)
        page.goto(URL+'#/instances/'+quote(CASE,safe=''),wait_until='domcontentloaded')
        page.wait_for_function('id=>window.hydInstances?.I.view?.instance?.proc_inst_id===id',arg=CASE,timeout=30000)
        page.locator('[data-inst-tab="record"]').click()
        row=page.locator('#instRecord [data-cr-steps] > li').filter(has_text='HYD-02 정기 정비 결과').last
        row.wait_for(state='visible');toggle=row.locator('[data-cr-toggle]')
        if toggle.get_attribute('aria-expanded')=='false':toggle.click()
        detail=row.locator('details.cr-sec').filter(has=page.locator('summary',has_text='보고 내용')).first
        if detail.get_attribute('open') is None:detail.locator(':scope > summary').click()
        page.wait_for_function("()=>[...document.querySelectorAll('#instRecord .cr-sec-body')].some(e=>e.innerText.includes('현재 사건')&&!e.innerText.includes('현재 사건 상태: 조회 중'))")
        raw=row.locator('details.raw').filter(has=page.locator('summary',has_text='결과 보고 원문')).first
        assert raw.get_attribute('open') is None
        original=json.loads(raw.locator('pre').text_content())
        assert any(isinstance(w.get('output'),dict) and w['output'].get('result_report')==original for w in bv['workitems'])
        assert original['incident_closed'] is False
        assert 'Source-scoped maintenance orders registered' in json.dumps(original)
        save('preserved-original-check.json',{'sha256':sha(json.dumps(original,ensure_ascii=False,sort_keys=True).encode()),'equals_stored_report':True,'collapsed':True,'incident_closed':False,'english_original_preserved':True})
        for width in [1440,1024]:
            page.set_viewport_size({'width':width,'height':1000});detail.scroll_into_view_if_needed();page.wait_for_timeout(250)
            text=detail.inner_text();assert '작업지시' not in text and '정비 오더' not in text
            assert '정비 요청' in text and '이 보고에서 사건 종결 처리: 수행 안 함' in text
            assert '현재 사건' in text and 'Source-scoped maintenance orders registered' not in text
            n=f'B-report-detail-{width}';(O/(n+'.txt')).write_text(text,encoding='utf8');page.screenshot(path=str(O/(n+'.png')))
            r['captures'].append({'path':n+'.png','width':width,'sha256':sha((O/(n+'.png')).read_bytes())})
        refs=T/'docs/handoff/verification/2026-10-12/final-delegated'
        files=[refs/'reference-processgpt.png',refs/'reference-dify.png',O/'B-report-detail-1440.png']
        labels=['Preserved historical ProcessGPT reference, not current HYD','Preserved Dify documentation reference, not HYD execution','Current actual HYD B detail, native GET']
        html='<html><meta charset="utf-8"><body style="margin:12px;font:16px sans-serif"><div style="display:flex;gap:12px">'
        provenance=[]
        for f,label in zip(files,labels):
            b=f.read_bytes();provenance.append({'path':str(f),'sha256':sha(b),'label':label})
            html+=f'<section style="width:32%"><p>{label}</p><img style="width:100%" src="data:image/png;base64,{base64.b64encode(b).decode()}"></section>'
        html+='</div></body></html>';(O/'comparison.html').write_text(html,encoding='utf8');save('comparison-provenance.json',provenance)
        page.set_viewport_size({'width':1800,'height':1000});page.goto((O/'comparison.html').as_uri());page.screenshot(path=str(O/'comparison.png'),full_page=True);browser.close()
except Exception:r['exception']=traceback.format_exc()
finally:
    after=get(API+'/api/instances/'+CASE);av=json.loads(after);sa=sources()
    save('after-metadata.json',{'case':CASE,'api_sha256':sha(after),'bytes':len(after),'status':av['instance']['status'],'source':sa})
    r['source_unchanged']=sb==sa;r['business_unchanged']=business(bv)==business(av);r['api_bytes_unchanged']=before==after
    r['ok']=not r.get('exception') and not r['writes'] and not r['errors'] and r['source_unchanged'] and r['business_unchanged'] and len(r['captures'])==2
    save('result.json',r);print(json.dumps(r,ensure_ascii=False))
