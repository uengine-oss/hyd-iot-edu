// 1회차 실습4 가이드 11단계(파일로 남기기 · 다시 열기)의 사진을 영상 밖에서 따로 찍는다 — 2026-11-20 클라우드.
// 화면 값은 녹화와 같다(촬영도구/config.json cloud: CSS 2128×1197 × 배율 0.9022556 = 1920×1080, 맑은 고딕).
// 앞: 촬영도구 run.sh up → run.sh open → dismiss.mjs(첫 안내 창 닫기). run.sh restore는 이 화면 값에서 오른쪽 칸을 접어 버려(그림판 폭 1703 > 1400)
// 같은 일(끝 그림 r2-11 end-state 가져오기 + 원 크기 60 + 관계 글 가로)을 여기서 한다.
// 사진은 <out>/ex-*.png(1920×1080 그대로), 받은 파일은 <out>/받은파일/, 그림 상태 기록은 <out>/capture-log.json.
import {createRequire} from 'node:module';
import fs from 'node:fs';
const require=createRequire(import.meta.url);
const {chromium}=require('/opt/node22/lib/node_modules/playwright');
const OUT=process.argv[2];fs.mkdirSync(OUT+'/받은파일',{recursive:true});
const END=new URL('./끝그림.json',import.meta.url).pathname;   // 영상 11구간 끝 그림(r2-11 end-state의 graph)
const log=[];const note=(k,v)=>{log.push({k,v});console.log(k,JSON.stringify(v));};
const b=await chromium.connectOverCDP('http://127.0.0.1:9334');
const p=b.contexts()[0].pages().find(x=>x.url().includes('arrows.app'));
const sleep=ms=>p.waitForTimeout(ms);
const G=()=>p.evaluate(()=>{const id=location.hash.split('id=')[1];return JSON.parse(localStorage.getItem('GRAPH|'+id)).graph;});
const center=async loc=>{const r=await loc.boundingBox();return {x:r.x+r.width/2,y:r.y+r.height/2};};
const clickLoc=async loc=>{const c=await center(loc);await p.mouse.move(c.x,c.y,{steps:5});await p.mouse.click(c.x,c.y);};
const blank=async()=>{const c=await p.evaluate(()=>{const r=document.querySelector('canvas').getBoundingClientRect();return {x:r.x+r.width-60,y:r.y+r.height-60};});await p.mouse.click(c.x,c.y);await sleep(300);};
const shot=async name=>{await p.mouse.move(5,600);await sleep(600);await p.screenshot({path:`${OUT}/${name}.png`});note('shot',name);};
const panelOpen=()=>p.evaluate(()=>document.querySelector('canvas').getBoundingClientRect().width<1900);
const hamburger=async()=>{const h=await p.evaluate(()=>{const e=[...document.querySelectorAll('a.item')].filter(e=>{const r=e.getBoundingClientRect();return r.x>innerWidth-80&&r.y<45;}).pop();const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};});await p.mouse.click(h.x,h.y);await sleep(500);};
const styleRow=k=>p.locator('form tr').filter({has:p.locator(`td:text-is("${k}:")`)});
const step=process.argv[3]||'all';
if(step==='setup'||step==='all'){
 if(!await panelOpen())await hamburger();
 note('panelOpen',await panelOpen());
 // 기본 빈 원 지우기 → 끝 그림 가져오기(Import 창의 글 칸)
 await blank();if((await G()).nodes.length){await p.keyboard.press('ControlOrMeta+A');await sleep(200);await p.click('button:has-text("Delete")');await sleep(300);}
 const end=JSON.parse(fs.readFileSync(END,'utf8')).graph.graph;
 await p.click('css=[role=listbox] >> nth=0');await sleep(300);await p.click('[role=option]:text-is("Import")');await sleep(500);
 await p.fill('textarea',JSON.stringify({nodes:end.nodes,relationships:end.relationships,style:end.style}));
 await p.click('role=button[name="Import"]');await sleep(1000);await blank();
 // 원 크기 60 · 관계 글 가로(학생이 1단계에서 Customize로 바꾼 두 값) — 줄은 첫 칸 글자로 찾는다(restore.mjs와 같은 길)
 const rowRect=(k,sel)=>p.evaluate(([k,sel])=>{const r=[...document.querySelectorAll('form tr')].find(r=>r.querySelector('td')?.textContent.trim()===k+':');if(!r)return null;const e=r.querySelector(sel);e.scrollIntoView({block:'center'});const b=e.getBoundingClientRect();return {x:b.x+Math.min(20,b.width/2),y:b.y+b.height/2};},[k,sel]);
 if(!await rowRect('radius','input')){await p.click('button:has-text("Customize")');await sleep(400);}
 let q=await rowRect('radius','input');await sleep(300);q=await rowRect('radius','input');await p.mouse.click(q.x,q.y);await p.keyboard.press('ControlOrMeta+A');await p.keyboard.insertText('60');await p.keyboard.press('Tab');await sleep(600);
 q=await rowRect('detail-orientation','[role=listbox]');await sleep(300);q=await rowRect('detail-orientation','[role=listbox]');await p.mouse.click(q.x,q.y);await sleep(400);
 const o=await p.evaluate(()=>{const r=[...document.querySelectorAll('form tr')].find(r=>r.querySelector('td')?.textContent.trim()==='detail-orientation:');const e=[...r.querySelectorAll('[role=option]')].find(e=>e.textContent.trim()==='horizontal');const b=e.getBoundingClientRect();return {x:b.x+b.width/2,y:b.y+b.height/2};});
 await p.mouse.click(o.x,o.y);await sleep(600);
 await blank();
 await p.waitForFunction(()=>document.body.innerText.includes('Saved to Web Browser storage'),undefined,{timeout:10000});
 const g=await G();const rel=ns=>{const a=ns.find(n=>n.caption==='HYD-01 유압 파워팩').position;return ns.map(n=>[n.caption,Math.round(n.position.x-a.x),Math.round(n.position.y-a.y)]).sort().join('|');};
 note('restored',{nodes:g.nodes.length,rels:g.relationships.length,radius:g.style.radius,orient:g.style['detail-orientation'],relSame:rel(g.nodes)===rel(end.nodes),colored:g.nodes.filter(n=>n.style['node-color']).length,props:g.nodes.reduce((s,n)=>s+Object.keys(n.properties).length,0)+g.relationships.reduce((s,r)=>s+Object.keys(r.properties).length,0)});
}
if(step==='export'||step==='all'){
 if(await p.locator('.modal button:has-text("Done")').count()){await p.click('.modal button:has-text("Done")');await sleep(600);}
 // 오른쪽 칸을 맨 위로
 await p.evaluate(()=>{for(const e of document.querySelectorAll('*')){if(e.scrollTop>0)e.scrollTop=0;}});await blank();
 await shot('ex-00-main');
 await clickLoc(p.locator('button:has-text("Download / Export")'));await sleep(1200);
 await shot('ex-01-png');
 let w=p.waitForEvent('download',{timeout:20000});await clickLoc(p.locator('.modal :is(a,button):has-text("Download")').first());let d=await w;await d.saveAs(OUT+'/받은파일/'+d.suggestedFilename());note('download',d.suggestedFilename());await sleep(500);
 await clickLoc(p.locator('.modal a:text-is("JSON"), .modal .item:text-is("JSON")').first());await sleep(800);
 await shot('ex-02-json');
 w=p.waitForEvent('download',{timeout:20000});await clickLoc(p.locator('.modal :is(a,button):has-text("Download")').first());d=await w;await d.saveAs(OUT+'/받은파일/'+d.suggestedFilename());note('download',d.suggestedFilename());await sleep(500);
 await clickLoc(p.locator('.modal a:text-is("Cypher"), .modal .item:text-is("Cypher")').first());await sleep(800);
 await shot('ex-03-cypher');
 note('cypherHead',(await p.locator('.modal textarea, .modal pre').first().innerText().catch(()=>'')).slice(0,60));
 await clickLoc(p.locator('.modal button:has-text("Done")'));await sleep(600);
 await blank();
}
if(step==='reopen'||step==='all'){
 if(await p.locator('.modal button:has-text("Done")').count()){await p.click('.modal button:has-text("Done")');await sleep(600);}
 await blank();
 // 로고 › New › Web Browser storage(새 그림) — 지금 줄에서 오른쪽으로 먼저 옮긴 뒤 내려간다(촬영준비 함정)
 await clickLoc(p.locator('[role=listbox]').first());await sleep(400);
 const np=await p.evaluate(()=>{const e=[...document.querySelectorAll('[role=option]')].find(e=>e.textContent.startsWith('NewStore'));const r=e.getBoundingClientRect();return {x:r.x+20,y:r.y+r.height/2};});
 await p.mouse.move(np.x,np.y,{steps:5});await sleep(500);
 const wc=await p.evaluate(()=>{const n=[...document.querySelectorAll('[role=option]')].find(e=>e.textContent.startsWith('NewStore'));const r=[...n.querySelectorAll('[role=option]')].find(e=>e.textContent.trim()==='Web Browser storage').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};});
 await p.mouse.move(wc.x,np.y,{steps:5});await p.mouse.move(wc.x,wc.y,{steps:5});await sleep(500);
 await p.screenshot({path:`${OUT}/ex-04-menu.png`});note('shot','ex-04-menu (커서는 Web Browser storage 위)');
 const before=p.url();await p.mouse.click(wc.x,wc.y);await p.waitForFunction(u=>location.href!==u,before,{timeout:8000});await sleep(600);
 note('newGraph',{url:p.url(),nodes:(await G()).nodes.length});
 await blank();await sleep(300);
 await clickLoc(p.locator('[role=listbox]').first());await sleep(400);const im=await p.evaluate(()=>{const e=[...document.querySelectorAll('[role=option]')].find(e=>e.textContent.trim()==='Import');const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};});await p.mouse.move(im.x,im.y,{steps:5});await p.mouse.click(im.x,im.y);await sleep(800);
 await shot('ex-05-import');
 const fc=p.waitForEvent('filechooser',{timeout:10000});await clickLoc(p.locator('.modal button:has-text("Choose File"), .modal label:has-text("Choose File")').first());const ch=await fc;
 const json=fs.readdirSync(OUT+'/받은파일').find(f=>f.endsWith('.json'));await ch.setFiles(OUT+'/받은파일/'+json);await sleep(800);
 await shot('ex-05b-chosen');
 await clickLoc(p.locator('.modal button').filter({hasText:/^Import$/}).first());await sleep(1500);
 await shot('ex-06-imported');
 const g=await G();const named=g.nodes.filter(n=>n.caption);
 note('imported',{nodesAll:g.nodes.length,named:named.length,rels:g.relationships.length,radius:g.style.radius,orient:g.style['detail-orientation'],colored:g.nodes.filter(n=>n.style['node-color']).length,
  props:named.reduce((s,n)=>s+Object.keys(n.properties).length,0),relProps:g.relationships.filter(r=>Object.keys(r.properties).length).map(r=>r.properties['절차']).sort(),selText:(await p.evaluate(()=>document.body.innerText.match(/nodes:\s*\d+[\s\S]{0,40}?relationships:\s*\d+/)?.[0]||''))});
}
fs.writeFileSync(OUT+'/capture-log.json',JSON.stringify(log,null,1));
process.exit(0);
