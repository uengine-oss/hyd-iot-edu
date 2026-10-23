// 녹화 밖 상태 복원: 이전 구간 끝 상태(end-state.json)의 그림 데이터를 새 그림으로 가져와 그 화면에 맞춘다.
// 실행 취소로 되돌리지 않는다(입력칸 포커스 · 스타일 · 글자 단위 기록 때문에 내용을 잃는다).
// 가져오기는 원 크기를 50으로 넣으므로 이전 끝의 크기로 되돌리고, 상대 위치가 같은지 확인한 뒤 마지막 선택(화살표)을 다시 만든다.
// 새 그림은 주소가 바뀌므로 이어 찍는 첫 구간은 relaxUrl:true로 실행한다.
export async function restore({take, edge, space}){
 const fs=await import('node:fs/promises');const {fileURLToPath}=await import('node:url');const path=await import('node:path');
 const here=path.dirname(fileURLToPath(import.meta.url));const conf=JSON.parse(await fs.readFile(path.join(here,'config.json'),'utf8'));
 const base=path.resolve(here,conf.work);
 const end=JSON.parse(await fs.readFile(path.join(base,take,'end-state.json'),'utf8')).graph.graph;
 const t=await taskSpace(space||conf.space);
 let p=(await Promise.all((await t.tabs()).map(async x=>[x,x.url]))).find(([x,u])=>u&&u.includes('arrows.app'))?.[0];
 p=p?(p.label?t.page(p.label):await t.adopt(p.page)):t.page('p1');
 await p.cdp('Emulation.setDeviceMetricsOverride',{width:2304,height:1296,deviceScaleFactor:1,mobile:false});
 if(!(await p.url()).includes('arrows.app')){await p.goto('https://arrows.app');await p.waitForSelector('canvas');}
 const G=()=>p.evaluate(()=>{const id=location.hash.split('id=')[1];return JSON.parse(localStorage.getItem('GRAPH|'+id)).graph;});
 // 새 그림(New ▸ Web Browser storage)
 const before=await p.url();
 await p.click('css=[role=listbox] >> nth=0');await p.waitForTimeout(300);
 const np=await p.evaluate(()=>{const e=[...document.querySelectorAll('[role=option]')].find(e=>e.textContent.startsWith('NewStore'));const r=e.getBoundingClientRect();return {x:r.x+20,y:r.y+r.height/2};});
 await p.mouse.move(np.x,np.y);await p.waitForTimeout(400);
 const pt=await p.evaluate(()=>{const n=[...document.querySelectorAll('[role=option]')].find(e=>e.textContent.startsWith('NewStore'));const r=[...n.querySelectorAll('[role=option]')].find(e=>e.textContent.trim()==='Web Browser storage').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};});
 await p.mouse.move(pt.x,np.y);await p.mouse.move(pt.x,pt.y);await p.mouse.click(pt.x,pt.y);
 await p.waitForFunction(u=>location.href!==u,before,{timeout:8000});await p.waitForTimeout(500);
 // 패널이 접혀 있으면 연다
 if(await p.evaluate(()=>document.querySelector('canvas').getBoundingClientRect().width>1400)){const hb=await p.evaluate(()=>{const e=[...document.querySelectorAll('a.item')].filter(e=>{const r=e.getBoundingClientRect();return r.x>innerWidth-80&&r.y<45;}).pop();const r=e.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2};});await p.mouse.click(hb.x,hb.y);await p.waitForTimeout(400);}
 // 기본 빈 원 지우기 → 가져오기
 await p.mouse.click(300,150);if((await G()).nodes.length){await p.keyboard.press('ControlOrMeta+A');await p.click('button:has-text("Delete")');}
 await p.click('css=[role=listbox] >> nth=0');await p.click('text="Import"');await p.waitForTimeout(400);
 await p.fill('textarea',JSON.stringify({nodes:end.nodes,relationships:end.relationships,style:end.style}));
 await p.click('loc=role:button[name="Import"]');await p.waitForTimeout(800);
 await p.mouse.click(300,150);await p.waitForTimeout(300);
 await p.waitForFunction(()=>document.body.innerText.includes('Saved to Web Browser storage'),undefined,{timeout:10000});
 // 원 크기를 이전 끝으로 되돌림(Import는 50으로 넣는다)
 if(!(await p.evaluate(()=>[...document.querySelectorAll('form tr')].some(r=>r.querySelector('td')?.textContent.trim()==='radius:'))))await p.click('button:has-text("Customize")');
 const rp=await p.evaluate(()=>{const r=[...document.querySelectorAll('form tr')].find(r=>r.querySelector('td')?.textContent.trim()==='radius:').querySelector('input').getBoundingClientRect();return{x:r.x+20,y:r.y+r.height/2};});
 await p.mouse.click(rp.x,rp.y);await p.keyboard.press('ControlOrMeta+A');await p.keyboard.insertText(String(end.style.radius));await p.keyboard.press('Tab');await p.waitForTimeout(600);
 const g=await G();
 const rel=ns=>{const by=Object.fromEntries(ns.map(n=>[n.caption,n.position]));const a=by[ns.map(n=>n.caption).sort()[0]];return ns.map(n=>[n.caption,Math.round(n.position.x-a.x),Math.round(n.position.y-a.y)]).sort().join('|');};
 // 마지막 선택을 다시 만든다(ui의 화살표 선택 방식 그대로)
 if(edge){
  const {makeUI}=await import('./ui.mjs?restore'+Date.now());
  let q=Promise.resolve();const serial=fn=>{const r=q.then(fn);q=r.catch(()=>{});return r;};
  const ui=await makeUI({p,serial,sleep:ms=>new Promise(r=>setTimeout(r,ms)),startPos:{x:700,y:400}});await ui.install();
  await p.cdp('Emulation.setDeviceMetricsOverride',{width:2305,height:1296,deviceScaleFactor:1,mobile:false});await p.waitForTimeout(300);await p.cdp('Emulation.setDeviceMetricsOverride',{width:2304,height:1296,deviceScaleFactor:1,mobile:false});await p.waitForTimeout(400);
  await ui.edge(edge[0],edge[1]);
 }
 const out={url:await p.url(),nodes:g.nodes.length,rels:g.relationships.length,radius:(await G()).style.radius,wantRadius:end.style.radius,relSame:rel(g.nodes)===rel(end.nodes)};
 if(!out.relSame||out.nodes!==end.nodes.length||out.rels!==end.relationships.length||out.radius!==end.style.radius)throw Error('restore mismatch '+JSON.stringify(out));
 return out;
}

// 읽기 전용: 이 브라우저의 arrows 그림 저장 좌표를 모두 읽는다(사용자가 ego에서 직접 잡은 배치를 그대로 쓰기 위해).
export async function coords({space}={}){
 const fs=await import('node:fs/promises');const {fileURLToPath}=await import('node:url');const path=await import('node:path');
 const here=path.dirname(fileURLToPath(import.meta.url));const conf=JSON.parse(await fs.readFile(path.join(here,'config.json'),'utf8'));
 const p=(await taskSpace(space||conf.space)).page('p1');
 if(!(await p.url()).includes('arrows.app')){await p.goto('https://arrows.app');await p.waitForSelector('canvas');}
 return p.evaluate(()=>{const cur=location.hash.split('id=')[1];const res=[];for(let i=0;i<localStorage.length;i++){const k=localStorage.key(i);if(!k.startsWith('GRAPH|'))continue;try{const g=JSON.parse(localStorage.getItem(k)).graph;res.push({id:k.slice(6),current:k.slice(6)===cur,nodes:g.nodes.map(n=>[n.caption,Math.round(n.position.x),Math.round(n.position.y)]),rels:g.relationships.length,radius:g.style.radius});}catch(e){}}return res;});
}
