"""Affected native GET views only; no case or LLM replay, no injected records."""
import hashlib, json, sys, traceback
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import quote
from playwright.sync_api import sync_playwright

T=Path('D:/work/study/hyd-iot-edu/.claude/worktrees/codex-portal-20261011')
H=Path(__file__).parent
OUT=H/sys.argv[1]
OUT.mkdir(exist_ok=False)
PORTAL='http://127.0.0.1:8088/'
API='http://127.0.0.1:8080'
CASES={'B':'c3_pm.d99ee952-f943-42fd-ba53-745b569522f7','C':'c3_spare.01a60b8d-284d-422b-96db-113dda3dd43f'}
proof={'method':'native existing B/C GET views, no injected records or writes','checks':[],'pageerrors':[],'consoleErrors':[],'blockedWrites':[],'screenshots':[],'payloadRequests':[],'llm_reruns':0,'whole_reruns':0}
def save(name,v): (OUT/name).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def check(name,v,detail=None): proof['checks'].append({'label':name,'passed':bool(v),'detail':detail})
def get(path):
    with urlopen(API+path,timeout=30) as r:return json.load(r)
def sources():return {p.relative_to(T).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (T/'it/portal/www').rglob('*') if p.suffix in {'.js','.html','.css'}}
def persisted(v):return {k:v.get(k) for k in ('instance','workitems','approvals','effects','reworks')}
frozen=sources();save('source-before.json',frozen)
before={k:get('/api/instances/'+v) for k,v in CASES.items()};save('cases-before.json',before)
try:
    previous=json.loads((T/'docs/handoff/verification/2026-10-12/k3-and-record-followup/completed-source-manifest.json').read_text(encoding='utf-8'))['source_sha256']
    for path,digest in frozen.items():
        if previous.get(path)==digest:continue
        with urlopen(PORTAL+path.removeprefix('it/portal/www/')+'?sha='+digest,timeout=30) as r:actual=hashlib.sha256(r.read()).hexdigest()
        check('mounted bytes '+path,actual==digest,{'expected':digest,'actual':actual})
    with sync_playwright() as pw:
        browser=pw.chromium.launch()
        ctx=browser.new_context(viewport={'width':1440,'height':1000},service_workers='block')
        def guard(route):
            if route.request.method in {'GET','HEAD','OPTIONS'}:route.continue_()
            else:proof['blockedWrites'].append({'url':route.request.url,'method':route.request.method});route.abort()
        ctx.route('**/*',guard)
        page=ctx.new_page();page.set_default_timeout(30000)
        page.on('pageerror',lambda e:proof['pageerrors'].append(str(e)))
        page.on('console',lambda m:proof['consoleErrors'].append(m.text) if m.type=='error' else None)
        page.on('request',lambda r:proof['payloadRequests'].append(r.url) if '/api/event-payloads/' in r.url else None)
        def shot(name,target,width):
            target.scroll_into_view_if_needed()
            target.evaluate('el=>{for(let p=el.parentElement;p;p=p.parentElement){const s=getComputedStyle(p);if(/auto|scroll/.test(s.overflowY)&&p.scrollHeight>p.clientHeight)p.scrollTop+=el.getBoundingClientRect().top-Math.max(p.getBoundingClientRect().top,110)-15;}window.scrollBy(0,el.getBoundingClientRect().top-125);}')
            page.wait_for_timeout(150)
            name=name+'-'+str(width)+'.png';page.screenshot(path=str(OUT/name))
            proof['screenshots'].append({'file':name,'sha256':hashlib.sha256((OUT/name).read_bytes()).hexdigest()})
        page.goto(PORTAL,wait_until='domcontentloaded');page.locator('[data-tab="instances"]').click()
        for key,case in CASES.items():
            page.evaluate('(id)=>hydInstancesSelect(id)',case)
            page.wait_for_function('(id)=>hydInstances.I.view?.instance?.proc_inst_id===id',arg=case)
            page.locator('[data-inst-tab="record"]').click()
            page.locator('#instRecord [data-cr-all]').wait_for()
            if page.locator('#instRecord [data-cr-all]').inner_text()=='모두 펼치기':page.locator('#instRecord [data-cr-all]').click()
            closed_tools=page.locator('#instRecord details.cr-sec.cr-tools:not([open]) > summary')
            while closed_tools.count():
                closed_tools.first.click()
            page.wait_for_function("()=>hydInstances.I.view.events.filter(e=>e.data?.full_output?.stored).every(e=>UI.fullToolIO(e).state==='complete')")
            page.wait_for_function("()=>[...document.querySelectorAll('#instRecord [data-tool-direction=output]')].every(el=>el.dataset.toolPayloadState==='complete')")
            expected=page.evaluate("()=>hydInstances.I.view.events.filter(e=>e.event_type==='tool_usage_finished'&&e.data?.full_output?.stored).map(e=>({id:e.id,tool:e.data.tool,ref:e.data.full_output.ref,label:hydWords.toolName(e.data.tool),state:UI.fullToolIO(e).state,result:UI.toolResult(e)}))")
            save(key+'-resolved-tools.json',expected)
            check(key+' stored originals resolved',bool(expected) and all(x['state']=='complete' and x['result']['value'] is not None for x in expected))
            target=page.locator('#instRecord .cr-r.tool').filter(has_text='구매 후보 비교' if key=='C' else '정비').first
            for width in (1440,1024):
                page.set_viewport_size({'width':width,'height':1000})
                text=page.locator('#instRecord').inner_text();(OUT/(key+'-record-'+str(width)+'.txt')).write_text(text,encoding='utf-8')
                check(key+' record no missing-object claim '+str(width),'구매 결과 기록을 확인할 수 없습니다' not in text and '[object Object]' not in text)
                if key=='C':check('C evaluated and submitted distinct '+str(width),'후보 비교 완료' in text and '구매 판단 등록됨' in text and '사람 승인 · ERP 실행 완료 아님' in text)
                shot(key+'-record-tool',target,width)
            # Native processing pane and the same original summaries.
            for item in expected:
                record=next(r for r in json.loads((H/'F27-actual-stored-payloads-GET.json').read_text(encoding='utf-8'))['payloads'].values() if r['reference']['ref']==item['ref'])
                original=''.join(c['content'] for c in record['chunks'])
                dom=page.locator('#instRecord [data-tool-ref="'+item['ref']+'"][data-tool-direction=output] details pre').first.text_content()
                check(key+' record exact raw original '+item['id'],dom==original,{'chars':len(original),'sha256':hashlib.sha256(original.encode()).hexdigest()})
            page.locator('[data-inst-tab="flow"]').click()
            trace=page.locator('#instTrace');trace.wait_for(state='attached')
            starts=[e for e in before[key]['events'] if e['event_type']=='task_started' and any(w['id']==e.get('todo_id') and w.get('activity_id')=='T_agent' for w in before[key]['workitems'])]
            wid=max(starts,key=lambda e:e.get('timestamp') or '')['todo_id']
            latest=trace.locator('.tr-step[data-key="'+wid+'"] [data-tr-head]')
            latest.wait_for(state='visible')
            closed_steps=trace.locator('[data-tr-head][aria-expanded="false"]')
            while closed_steps.count():
                closed_steps.first.click()
            page.wait_for_function('(wid)=>document.querySelector("#instTrace .tr-step[data-key="+CSS.escape(wid)+"]")?.classList.contains("open")',arg=wid)
            trace_text=trace.inner_text();(OUT/(key+'-trace.txt')).write_text(trace_text,encoding='utf-8')
            for item in expected:check(key+' trace same original summary '+item['id'],item['result']['summary'] in trace_text)
            page.goto(PORTAL+'#/instances/'+quote(case,safe='')+'/task/'+quote(wid,safe=''),wait_until='domcontentloaded')
            page.wait_for_function('(id)=>hydTaskDetail.T.wid===id&&!hydTaskDetail.T.loading&&hydTaskDetail.T.item?.id===id',arg=wid)
            panel=page.locator('#taskDetailPanel [data-task-detail]');timeline=panel.locator('[data-k="trace"]')
            if timeline.get_attribute('open') is None:timeline.locator('summary').click()
            page.wait_for_function("()=>hydTaskDetail.T.item.events.filter(e=>e.data?.full_output?.stored).every(e=>UI.fullToolIO(e).state==='complete')")
            text=timeline.inner_text();(OUT/(key+'-task-trace.txt')).write_text(text,encoding='utf-8')
            for item in expected:
                ev=next(e for e in before[key]['events'] if e['id']==item['id'])
                if ev.get('todo_id')==wid:check(key+' task same original summary '+item['id'],item['result']['summary'] in text)
            if key=='C':
                for width in (1440,1024):
                    page.set_viewport_size({'width':width,'height':1000})
                    target=timeline.locator('.tr-row.tr-k-tool').filter(has_text='구매 판단 등록됨').first
                    shot('C-task-submitted-original',target,width)
            page.locator('[data-tab="instances"]').click()
        browser.close()
except Exception:proof['exception']=traceback.format_exc()
finally:
    after={k:get('/api/instances/'+v) for k,v in CASES.items()};save('cases-after.json',after)
    for key in before:check(key+' case/task/approval/effect unchanged',persisted(before[key])==persisted(after[key]))
    aftersource=sources();save('source-after.json',aftersource)
    check('source stable throughout',frozen==aftersource)
    check('pageerrors zero',not proof['pageerrors'],proof['pageerrors']);check('console errors zero',not proof['consoleErrors'],proof['consoleErrors']);check('attempted writes zero',not proof['blockedWrites'],proof['blockedWrites'])
    proof['driver_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    proof['passed']=not proof.get('exception') and all(x['passed'] for x in proof['checks'])
    save('result.json',proof)
    print(json.dumps({'passed':proof['passed'],'checks':len(proof['checks']),'failures':[x for x in proof['checks'] if not x['passed']],'exception':proof.get('exception'),'out':str(OUT)},ensure_ascii=False))
sys.exit(0 if proof['passed'] else 1)
