"""Live layout evidence: expanded screens, scroll positions, hit targets and SVG labels.

Read-only except browser form drafts and decision calculation (no approval).
Geometry candidates need visual review; this is not an accessibility certification.
"""
import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.evidence/ux-audit' / (sys.argv[1] if len(sys.argv) > 1 else 'current')
OUT.mkdir(parents=True, exist_ok=True)
SCAN = r"""() => {
 const rect = e => e.getBoundingClientRect();
 const visible = e => {const r=rect(e); return r.width>0 && r.height>0 && getComputedStyle(e).visibility!=='hidden';};
 const overlap=(a,b)=>Math.min(a.right,b.right)-Math.max(a.left,b.left)>2 && Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>2;
 const labels=[...document.querySelectorAll('.view.active svg text')].filter(visible);
 const textOverlaps=[];
 for(let i=0;i<labels.length;i++) for(let j=i+1;j<labels.length;j++) {
   if(overlap(rect(labels[i]),rect(labels[j]))) textOverlaps.push([labels[i].textContent,labels[j].textContent]);
 }
 const svgOverflow=[];
 document.querySelectorAll('.view.active .m-node,.view.active .o-node,.view.active .b-node').forEach(g=>{
   const box=g.querySelector('rect'), t=g.querySelector('text');
   if(box && t && visible(g)) {const b=rect(box),r=rect(t);if(r.right>b.right-2 || r.left<b.left+2) svgOverflow.push(t.textContent);}
 });
 const blocked=[]; let tested=0;
 document.querySelectorAll('button,input,select,textarea,a[href],[role=button],.o-node').forEach(e=>{
   if(!visible(e)||e.disabled) return;
   const r=e.matches('.o-node') ? rect(e.querySelector('rect')) : [...e.getClientRects()].find(r=>r.width>2&&r.height>2);
   if(!r)return;
   // Hit-test the visible intersection. A fractional center at the scroll edge
   // can round onto the adjacent footer even when the link has visible pixels.
   let left=Math.max(0,r.left),right=Math.min(innerWidth,r.right),top=Math.max(0,r.top),bottom=Math.min(innerHeight,r.bottom);
   for(let p=e.parentElement;p;p=p.parentElement){const c=getComputedStyle(p),b=rect(p);
     if(/auto|scroll|hidden|clip/.test(c.overflowX)){left=Math.max(left,b.left+p.clientLeft);right=Math.min(right,b.left+p.clientLeft+p.clientWidth);}
     if(/auto|scroll|hidden|clip/.test(c.overflowY)){top=Math.max(top,b.top+p.clientTop);bottom=Math.min(bottom,b.top+p.clientTop+p.clientHeight);}
   }
   if(right-left<3||bottom-top<3)return;
   const x=(left+right)/2,y=(top+bottom)/2;
   tested++; const hit=document.elementFromPoint(x,y);
   if(hit && hit!==e && !e.contains(hit) && !(hit.tagName==='LABEL' && hit.control===e)) blocked.push({target:e.id||e.textContent.trim().slice(0,60),by:hit.id||hit.className});
 });
 return {textOverlaps,svgOverflow,blocked,tested,overflow:document.querySelector('main').scrollWidth>document.querySelector('main').clientWidth+2};
}"""

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 900}, reduced_motion='reduce')
    errors, records = [], []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('http://localhost:8088')
    expect(page.locator('#scale')).not_to_have_text('–')
    # Verify the detector against both intentionally broken and repaired geometry.
    probe=browser.new_page()
    probe.set_content('<main><section class="view active"><svg width="200" height="100"><text x="10" y="30">One</text><text x="10" y="30">Two</text></svg></section></main>')
    assert probe.evaluate(SCAN)['textOverlaps'], 'overlap detector missed known collision'
    probe.locator('text').nth(1).evaluate('(e)=>e.setAttribute("y",70)')
    assert not probe.evaluate(SCAN)['textOverlaps'], 'overlap detector rejected separated labels'
    probe.set_content('<main><button style="position:absolute;left:10px;top:10px;width:100px;height:40px">Covered</button><div id="shield" style="position:absolute;left:10px;top:10px;width:100px;height:40px"></div></main>')
    assert probe.evaluate(SCAN)['blocked'], 'hit-test missed a covered button'
    probe.locator('#shield').evaluate('(e)=>e.remove()')
    assert not probe.evaluate(SCAN)['blocked'], 'hit-test rejected an uncovered button'
    probe.close()
    for width, height in [(1920,1080),(1440,900),(1262,624),(1024,768)]:
        page.set_viewport_size({'width':width,'height':height})
        for name in ['main','home','scenario','incidents','trends','ontology','skills','decision','process']:
            page.locator('#brandHome' if name=='main' else f'.rail [data-tab={name}]').click()
            page.wait_for_timeout(900)
            if name=='incidents':
                expect(page.locator('#incList .item').first).to_be_visible()
                page.locator('#incList .item').first.click()
                expect(page.locator('#hitlPanel .bpmn')).to_be_visible()
            elif name=='ontology':
                expect(page.locator('.o-node').first).to_be_visible()
                page.locator('.o-node').first.click()
            elif name=='skills':
                expect(page.locator('#skName')).to_be_visible()
                page.locator('#skName').fill('설비 운전 상황에 따른 정비 작업지시 및 부서별 승인 처리')
            elif name=='decision':
                page.locator('.scn button').first.click()
                expect(page.locator('#decResult .mtx')).to_be_visible(timeout=45000)
            elif name=='process':
                expect(page.locator('#decList .item').first).to_be_visible()
                page.locator('#decList .item').first.click()
                expect(page.locator('#decDetail h2').first).to_be_visible()
            page.locator('main').evaluate('(e)=>e.scrollTop=0')
            extent=page.locator('main').evaluate('(e)=>Math.max(0,e.scrollHeight-e.clientHeight)')
            for label, top in [('top',0),('middle',extent/2),('bottom',extent)]:
                page.locator('main').evaluate('(e,t)=>e.scrollTop=t',top)
                page.wait_for_timeout(100)
                result=page.evaluate(SCAN)
                result.update(width=width,view=name,position=label)
                records.append(result)
                (OUT/'geometry.json').write_text(json.dumps({'records':records,'errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
                page.screenshot(path=str(OUT/f'{width}-{name}-{label}.png'))
            if name=='process':
                region=page.locator('#procBpmn .bpmn-scroll')
                region.scroll_into_view_if_needed()
                region.evaluate('(e)=>e.scrollLeft=e.scrollWidth')
                page.screenshot(path=str(OUT/f'{width}-bpmn-right.png'))
                page.locator('#procBpmn [data-bpmn-fit]').click()
                assert region.evaluate('(e)=>e.scrollWidth<=e.clientWidth+2')
                page.screenshot(path=str(OUT/f'{width}-bpmn-fit.png'))
                page.locator('#procBpmn [data-bpmn-fit]').click()
            print(width,name,'overlaps',len(result['textOverlaps']),'labels',len(result['svgOverflow']),flush=True)
    (OUT/'geometry.json').write_text(json.dumps({'records':records,'errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
    browser.close()
assert not errors, errors
assert not any(r['textOverlaps'] or r['svgOverflow'] or r['blocked'] or r['overflow'] for r in records), 'Review geometry.json candidates'
