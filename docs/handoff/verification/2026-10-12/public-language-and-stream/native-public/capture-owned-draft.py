"""GET-only native dependency warning. Requires root deployment and owned draft ID."""
from pathlib import Path
import argparse,json,hashlib,traceback,time
from urllib.request import urlopen
from urllib.parse import quote
from playwright.sync_api import sync_playwright
O=Path(__file__).parent/'owned-draft';R=Path(__file__).parents[3];T=R/'.claude/worktrees/codex-portal-20261011'
API='http://127.0.0.1:8080';PORTAL='http://127.0.0.1:8088/'
def sha(b):return hashlib.sha256(b).hexdigest()
def get(u):
    with urlopen(u,timeout=30) as r:return r.read()
def save(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--manifest',required=True);ap.add_argument('--draft-id',required=True);ap.add_argument('--root-deploy-done',action='store_true',required=True);a=ap.parse_args()
    assert a.draft_id.startswith('codex-meeting-preflight-20261012-'),'Only root-owned draft scope'
    O.mkdir(exist_ok=True);assert not (O/'result.json').exists(),'Preserve earlier collector result before retry'
    frozen=json.loads(Path(a.manifest).read_text(encoding='utf8'))
    def source():return {k:sha((T/k).read_bytes()) for k in frozen}
    sb=source();assert sb==frozen,'Root final source freeze mismatch before HTTP'
    endpoint=API+'/api/flows/'+quote(a.draft_id,safe='');before=get(endpoint);v=json.loads(before)
    r={'ok':False,'draft_id':a.draft_id,'method':'Root-created mapped/checked draft, native GET selection only; no mapping/check/register writes','writes':[],'errors':[],'checks':[]}
    save('before-metadata.json',{'source':sb,'draft_sha256':sha(before),'bytes':len(before)})
    def check(n,c):r['checks'].append({'name':n,'passed':bool(c)});assert c,n
    try:
        c=v['check'];deps=c['dependencies'];check('Stored structural check passes',c['ok'] is True)
        check('Stored dependency warning has exactly two attention steps',deps['attention_count']==2)
        with sync_playwright() as p:
            browser=p.chromium.launch();page=browser.new_page(viewport={'width':1440,'height':1000},locale='ko-KR');page.set_default_navigation_timeout(120000)
            clock=time.monotonic();r['requests']=[];starts={}
            def started(q):starts[id(q)]=time.monotonic();r['requests'].append({'url':q.url,'method':q.method,'start_seconds':time.monotonic()-clock})
            def finished(q):r['requests'].append({'url':q.url,'duration_seconds':time.monotonic()-starts.get(id(q),time.monotonic()),'failure':q.failure})
            page.on('request',started);page.on('requestfinished',finished);page.on('requestfailed',finished)
            def route(q):
                if q.request.method not in ['GET','HEAD','OPTIONS']:r['writes'].append(q.request.url);q.abort()
                else:q.continue_()
            page.route('**/*',route);page.on('pageerror',lambda e:r['errors'].append(str(e)));page.on('console',lambda m:r['errors'].append(m.text) if m.type=='error' else None)
            page.goto(PORTAL,wait_until='domcontentloaded');page.locator('[data-tab="flows"]').click()
            pick=page.locator('#flowList [data-open="'+a.draft_id+'"]')
            pick.wait_for(state='visible');pick.click();warning=page.locator('#flowProblems')
            warning.locator('.flow-dependencies').wait_for(state='visible')
            for attempt in range(5):
                try:warning.scroll_into_view_if_needed(timeout=5000);break
                except Exception:
                    if attempt==4:raise
                    page.wait_for_timeout(300)
            text=warning.inner_text();(O/'dependency-warning-1440.txt').write_text(text,encoding='utf8')
            check('Native structural pass visible','구조 검사 통과' in text)
            check('Native two missing dependency warning visible','연결 도구 준비가 필요한 단계 2개' in text)
            check('Structural pass explicitly separated from connection success','구조 검사 통과는 실제 연결을 보장하지 않습니다.' in text)
            check('Server registration warning visible','서버' in text and '등록' in text)
            for item in deps['items']:check('Exact stored dependency reason rendered: '+item['node_id'],item['reason'] in text)
            check('Owned draft exact ID stays selected',page.locator('#flowEditor').inner_text() and pick.get_attribute('data-open')==a.draft_id)
            page.wait_for_timeout(250);page.screenshot(path=str(O/'dependency-warning-1440.png'));r['png']={'path':'dependency-warning-1440.png','sha256':sha((O/'dependency-warning-1440.png').read_bytes())};r['text']=text
            browser.close()
    except Exception:r['exception']=traceback.format_exc()
    finally:
        after=get(endpoint);sa=source();save('after-metadata.json',{'source':sa,'draft_sha256':sha(after),'bytes':len(after)})
        r['source_unchanged']=sb==sa;r['draft_bytes_unchanged']=before==after;r['ok']=not r.get('exception') and not r['writes'] and not r['errors'] and r['source_unchanged'] and r['draft_bytes_unchanged'] and bool(r.get('png'));save('result.json',r);print(json.dumps(r,ensure_ascii=False))
if __name__=='__main__':main()
