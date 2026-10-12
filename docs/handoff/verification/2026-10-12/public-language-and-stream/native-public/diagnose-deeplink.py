from pathlib import Path
import json
from playwright.sync_api import sync_playwright
O=Path(__file__).parent;CASE='c3_pm.d99ee952-f943-42fd-ba53-745b569522f7'
r={'responses':[],'failures':[],'writes':[],'errors':[]}
with sync_playwright() as p:
    b=p.chromium.launch();page=b.new_page(viewport={'width':1440,'height':1000})
    def route(q):
        if q.request.method not in ['GET','HEAD','OPTIONS']:r['writes'].append(q.request.url);q.abort()
        else:q.continue_()
    page.route('**/*',route);page.on('response',lambda x:r['responses'].append({'url':x.url,'status':x.status}) if '/api/instances' in x.url else None);page.on('requestfailed',lambda x:r['failures'].append({'url':x.url,'failure':x.failure}));page.on('pageerror',lambda e:r['errors'].append(str(e)))
    page.goto('http://127.0.0.1:8088/#/instances/'+CASE,wait_until='domcontentloaded');page.wait_for_timeout(5000)
    r['before']=page.evaluate('({hash:location.hash,tab:window.hydApp?.state?.tab,I:window.hydInstances?.I ? {sel:hydInstances.I.sel,pid:hydInstances.I.view?.instance?.proc_inst_id,error:hydInstances.I.error}:null})')
    r['body_before']=page.locator('body').inner_text()
    page.locator('[data-tab="instances"]').click();page.wait_for_timeout(4000)
    r['after_native_tab']=page.evaluate('({hash:location.hash,tab:window.hydApp?.state?.tab,I:window.hydInstances?.I ? {sel:hydInstances.I.sel,pid:hydInstances.I.view?.instance?.proc_inst_id,error:hydInstances.I.error}:null})')
    r['body_after_native_tab']=page.locator('body').inner_text();b.close()
(O/'deeplink-diagnostic.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps({k:v for k,v in r.items() if not k.startswith('body')},ensure_ascii=False))
