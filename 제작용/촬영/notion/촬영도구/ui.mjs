// v10 조작 층: 기존 검증 경로(ui-properties→navigation→lesson→native→robust)를 재사용하고
// 이동·클릭·입력·키와 페이지 직접 호출만 바꾼다.
// - 표시 포인터: 컴포지터 애니메이션으로 이동, 실제 입력도 같은 경로·시각 16단계(순간이동 없음).
// - gate(): 큐가 정한 실행 시점(행동 문장 끝)까지 대기. 클릭·누르기·놓기·키·입력은 모두 gate를 거친다.
// - c.p 감싸기: mouse.click/down/up·keyboard.*는 gate 뒤 실행. hover/click(selector)/mouse.move 직접 호출은 순간이동이므로 오류.
//   옮긴 모듈은 c.hoverSel/c.clickSel/c.move를 쓴다. 기존 locate의 hover 스크롤은 휠 스크롤로 바꾼다.
import {properties} from './lib/ui-properties.mjs';

const MENU_CLOSES=['콜아웃','제목2','글머리 기호 목록','번호 매기기 목록','토글 목록','구분선','할 일 목록','목차'];

// 페이지 안 녹화 포인터(흰 화살표·검은 테두리, 후광 없음)와 이동 애니메이션을 설치한다. 페이지에서 실행되는 함수라 바깥 변수를 쓰지 않는다.
// pos가 있으면 그 자리에, 없으면 기존 화살표 자리(없으면 1400,650)에 그린다. ctrl.mjs도 이어 찍기 때 이 함수를 쓴다.
export function installPointerInPage(pos){
  document.removeEventListener('mousemove',window.__tutorialMove,true);document.removeEventListener('mousedown',window.__tutorialDown,true);
  const old=document.getElementById('recording-pointer');const keep=old?old.style.transform:pos?`translate(${pos.x}px,${pos.y}px)`:'translate(1400px,650px)';old?.remove();
  const e=document.createElement('div');e.id='recording-pointer';e.setAttribute('aria-hidden','true');
  e.style.cssText='position:fixed;left:0;top:0;width:20px;height:27px;pointer-events:none;z-index:2147483647;will-change:transform;transform:'+keep;
  e.innerHTML='<svg xmlns="http://www.w3.org/2000/svg" width="20" height="27" viewBox="0 0 25 34"><path d="M1 1 L1 25 L7 20 L12 31 L17 29 L12 18 L22 18 Z" fill="white" stroke="#111" stroke-width="1.7" stroke-linejoin="round"/></svg>';
  document.documentElement.append(e);window.__tutorialClicks??=[];window.__glide=null;
  // 이동 중(__glide: 애니메이션 또는 'hold')에는 실제 mousemove로 화살표를 옮기지 않는다. 늦게 도착한 중간 입력이 목표에 닿은 화살표를
  // 뒤로 끌어당겨 휘청이던 결함(2026-10-23 take-29) 방지 — 마지막 실제 입력이 끝난 뒤 ui.mjs가 'hold'를 푼다.
  // 기록: held = 이동 중이라 무시한 실제 입력('hold' 동안 = 예전 방식이면 화살표를 뒤로 끌었을 입력), applied = 화살표를 옮긴 입력.
  window.__ptrStat??={held:0,heldAfterFinish:0,applied:0};
  window.__tutorialMove=ev=>{if(window.__glide){window.__ptrStat.held++;if(window.__glide==='hold')window.__ptrStat.heldAfterFinish++;return;}window.__ptrStat.applied++;e.style.transform=`translate(${ev.clientX}px,${ev.clientY}px)`;};
  window.__tutorialDown=ev=>{const r=e.getBoundingClientRect();window.__tutorialClicks.push({x:ev.clientX,y:ev.clientY,px:r.x,py:r.y,trusted:ev.isTrusted,gliding:!!window.__glide,time:performance.now(),url:location.pathname});};
  document.addEventListener('mousemove',window.__tutorialMove,true);document.addEventListener('mousedown',window.__tutorialDown,true);
  window.__startGlide=(ax,ay,x,y,ms)=>{if(window.__glide?.cancel)window.__glide.cancel();const kf=[];for(let i=0;i<=20;i++){const t=i/20,u=t*t*(3-2*t);kf.push({transform:`translate(${ax+(x-ax)*u}px,${ay+(y-ay)*u}px)`,offset:t});}
   const a=e.animate(kf,{duration:ms,easing:'linear',fill:'forwards'});window.__glide=a;
   a.onfinish=()=>{e.style.transform=`translate(${x}px,${y}px)`;a.cancel();if(window.__glide===a)window.__glide='hold';};};
}

export async function v10(ctx){
 const raw=ctx.p;
 const sleep=ctx.sleep;
 let gateState={commitAt:0,lastMoveEnd:0};let lastPos=null;
 const gate=async()=>{const until=Math.max(ctx.commitAt||0,gateState.lastMoveEnd+150);const w=until-Date.now();if(w>0)await sleep(w);ctx.committed??=Date.now();};
 const pointerPos=()=>raw.evaluate(()=>{const r=document.getElementById('recording-pointer')?.getBoundingClientRect();if(!r)throw Error('Recording pointer missing');return{x:r.x,y:r.y};});
 // 이동: RPC 하나마다 직렬 큐를 잠깐 쓰고 놓는다(그 사이 캡처·ACK가 돈다). 큐를 이동 전체 동안 잡지 않는다.
 const q1=fn=>ctx.serial(fn);
 async function moveCore(x,y){
  const a=await q1(pointerPos);const dist=Math.hypot(x-a.x,y-a.y);if(dist<1){gateState.lastMoveEnd=Date.now();lastPos={x,y};return;}
  const ms=Math.round(Math.max(260,Math.min(620,200+dist*0.4)));const t0=Date.now();
  await q1(()=>raw.evaluate(({ax,ay,x,y,ms})=>window.__startGlide(ax,ay,x,y,ms),{ax:a.x,ay:a.y,x,y,ms}));
  // 실제 입력 8단계(16단계는 명령이 밀려 캡처 공백 · 늦은 도착이 컸다). 마지막 단계는 정확히 목표 좌표.
  for(let i=1;i<=8;i++){const t=i/8,u=t*t*(3-2*t);const w=t0+ms*t-Date.now();if(w>0)await sleep(w);await q1(()=>raw.mouse.move(a.x+(x-a.x)*u,a.y+(y-a.y)*u,{steps:1}));}
  // 애니메이션이 목표에 닿을 때까지 기다린 뒤 고정('hold')을 푼다. 이후 실제 위치 = 목표이므로 화살표가 움직이지 않는다.
  for(let n=0;n<60&&await q1(()=>raw.evaluate(()=>window.__glide&&window.__glide!=='hold'));n++)await sleep(20);
  await q1(()=>raw.evaluate(()=>{window.__glide=null;}));
  ctx.recordMotion?.({start:t0,end:Date.now(),x,y,from:a,planned_ms:ms});gateState.lastMoveEnd=Date.now();lastPos={x,y};
 }
 // ego 선택자 일부(css, X:has-text("T"), loc=role:R[name="N"])를 화면 좌표로. 화면 밖이면 휠로 들인다.
 async function targetPoint(selector){
  for(let i=0;i<10;i++){
   const r=await q1(()=>raw.evaluate(sel=>{
    let es;const ht=sel.match(/^(.*):has-text\("(.*)"\)$/),loc=sel.match(/^loc=role:([a-z]+)\[name="(.*)"\]$/);
    if(ht)es=[...document.querySelectorAll(ht[1])].filter(e=>e.textContent.includes(ht[2]));
    else if(loc)es=[...document.querySelectorAll(`[role="${loc[1]}"],${loc[1]}`)].filter(e=>(e.getAttribute('aria-label')||e.textContent.trim())===loc[2]);
    else es=[...document.querySelectorAll(sel)];
    es=es.filter(e=>{const b=e.getBoundingClientRect();return b.width&&b.height&&e.checkVisibility({checkVisibilityCSS:true});});
    if(ht&&es.length>1)es=es.filter(e=>!es.some(o=>o!==e&&e.contains(o)));
    if(es.length!==1)return{error:'Selector '+sel+' matched '+es.length};
    const b=es[0].getBoundingClientRect();return{x:b.x+Math.min(45,b.width/2),y:b.y+b.height/2,top:b.top,bottom:b.bottom,h:innerHeight};
   },selector));
   if(r.error)throw Error(r.error);
   if(r.top>=60&&r.bottom<=r.h-20)return r;
   const dy=r.top<60?r.top-120:r.bottom-r.h+80;await q1(()=>raw.mouse.wheel(0,Math.max(-500,Math.min(500,dy))));await sleep(250);
  }
  throw Error('Cannot bring into view: '+selector);
 }
 const p=new Proxy(raw,{get(t,k){
  if(k==='hover'||k==='click'||k==='dblclick'||k==='dragAndDrop')return async sel=>{throw Error('Unported page.'+String(k)+'('+sel+'): use c.hoverSel/c.clickSel');};
  if(k==='mouse')return new Proxy(t.mouse,{get(m,j){
   if(j==='move')return async()=>{throw Error('Unported page.mouse.move: use c.move');};
   if(['click','down','up','dblclick'].includes(j))return async(...a)=>{await gate();return m[j](...a);};
   const v=m[j];return typeof v==='function'?v.bind(m):v;}});
  if(k==='keyboard')return new Proxy(t.keyboard,{get(kb,j){const v=kb[j];return typeof v==='function'?async(...a)=>{await gate();return v.apply(kb,a);}:v;}});
  const v=t[k];return typeof v==='function'?v.bind(t):v;}});
 const c=await properties({...ctx,p});
 c.raw=raw;
 const origLocate=c.locate;
 c.locate=async(kind,value)=>{for(let i=0;i<6;i++){try{return await origLocate(kind,value);}catch(e){const m=String(e).match(/Unported page\.hover\((.*)\): use/);if(!m)throw e;await targetPoint(m[1]);}}throw Error('Target could not be brought into view: '+kind+' '+value);};
 c.installPointer=async(at)=>c.serial(()=>raw.evaluate(installPointerInPage,at||lastPos));
 c.setPos=pos=>{lastPos=pos;};
 c.move=async(x,y)=>{await moveCore(x,y);if((ctx.commitAt||0)>Date.now())await gate();};
 // 설명하며 가리키기(누르지 않음). 열린 대화상자 안에서는 그 이름 줄의 버튼 · 스위치를, 아니면 그 글자를 가리킨다.
 // button=true면 대화상자 안에서 그 이름의 버튼 중 마지막 것(탭과 같은 이름의 아래쪽 실행 버튼).
 c.hoverLabel=async(label,button=false)=>{
  const q=await c.serial(()=>raw.evaluate(({label,button})=>{
   const vis=e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&e.checkVisibility({checkVisibilityCSS:true});};
   const dlg=[...document.querySelectorAll('[role=dialog]')].filter(vis).at(-1);const scope=dlg||document;
   let t=null;
   if(button)t=[...scope.querySelectorAll('[role=button],button')].filter(e=>vis(e)&&e.textContent.trim()===label).at(-1);
   else{
    const leaf=[...scope.querySelectorAll('div,span,a,button,[role=tab]')].filter(e=>vis(e)&&e.textContent.trim()===label).filter((e,_,all)=>!all.some(o=>o!==e&&e.contains(o)))[0];
    t=leaf;
    if(leaf&&dlg){for(let p=leaf.parentElement,i=0;p&&p!==dlg&&i<4;p=p.parentElement,i++){const ctl=[...p.querySelectorAll('[role=button],[role=switch],button')].filter(vis).find(e=>!e.contains(leaf));if(ctl){t=ctl;break;}}}
   }
   if(!t)throw Error('Label target missing: '+label);
   const r=t.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2};
  },{label,button}));
  await c.move(q.x,q.y);
 };
 c.hoverSel=async sel=>{const q=await targetPoint(sel);await c.move(q.x,q.y);};
 c.clickSel=async sel=>{const q=await targetPoint(sel);await c.move(q.x,q.y);await gate();await c.serial(()=>raw.mouse.click(q.x,q.y));await sleep(150);};
 c.gate=gate;
 c.click=async(kind,value)=>{
  const before=kind==='menu'&&value==='페이지'?await c.serial(()=>raw.url()):null;
  for(let i=0;i<5;i++){
   // 메뉴 걸러짐·레이아웃 이동 중에 출발하면 도착 뒤 다시 움직여 휘청인다(take-27 116s). 150ms 간격 두 번 같은 위치일 때 출발.
   let q=await c.locate(kind,value);for(let k=0;k<10;k++){await sleep(150);const q2=await c.locate(kind,value);if(Math.hypot(q2.x-q.x,q2.y-q.y)<=1){q=q2;break;}q=q2;}
   await c.move(q.x,q.y);await gate();const now=await c.locate(kind,value);
   if(Math.hypot(now.x-q.x,now.y-q.y)>2)continue;
   await c.serial(()=>raw.mouse.click(now.x,now.y));await sleep(150);
   if(kind==='menu'&&MENU_CLOSES.includes(value))await c.serial(()=>raw.waitForFunction(s=>{const e=document.querySelector(s);return !e||!e.checkVisibility({checkVisibilityCSS:true});},now.selector,{timeout:7000}));
   if(kind==='menu'&&['파란색 배경','회색 배경'].includes(value)&&c.activeCalloutPrefix){const target={prefix:c.activeCalloutPrefix,color:value==='파란색 배경'?'rgb(229, 242, 252)':'rgb(249, 248, 247)'};await c.serial(()=>raw.waitForFunction(({prefix,color})=>[...document.querySelectorAll('[role=note]')].some(e=>e.textContent.startsWith(prefix)&&getComputedStyle(e.firstElementChild).backgroundColor===color),target,{timeout:8000}));}
   if(before)await c.serial(()=>raw.waitForFunction(url=>location.href!==url,before,{timeout:10000}));
   if(kind==='text'&&value==='새로 만들기')await c.serial(()=>raw.waitForSelector('[role=region] a[aria-label="전체 페이지로 열기"]'));
   if(kind==='css'&&value==='[role=region] a[aria-label="전체 페이지로 열기"]')await c.serial(()=>raw.waitForFunction(()=>!document.querySelector('[role=region] a[aria-label="전체 페이지로 열기"]')));
   // 입력칸 클릭: 2초 안에 캐럿이 안 들어가면 사람처럼 같은 자리를 한 번 더 누른다(take-n26 '새 데이터베이스' 칸). 그래도 안 되면 멈춘다.
   if(kind==='title'||(kind==='css'&&value.includes('contenteditable'))){
    const sel=kind==='title'?'h1[contenteditable=true]':value;
    const caretIn=()=>c.serial(()=>raw.waitForFunction(s=>{const e=[...document.querySelectorAll(s)].find(e=>e.checkVisibility({checkVisibilityCSS:true})),a=getSelection()?.anchorNode;return !!e&&!!a&&(e===a||e.contains(a));},sel,{timeout:2000})).then(()=>true,()=>false);
    if(!(await caretIn())){
     await ctx.fs.appendFile(ctx.out+'/reclicks.jsonl',JSON.stringify({target:sel,reason:'caret not placed within 2s'})+String.fromCharCode(10));
     await c.serial(()=>raw.mouse.click(now.x,now.y));await sleep(150);
     if(!(await caretIn()))throw Error('Click did not place the caret in '+sel+' after a second click');
    }
   }
   return;
  }
  throw Error('Target layout did not settle: '+kind+' '+value);
 };
 // 입력 중에는 캐럿이 있는 블록의 시작점 바로 아래 여백으로 비킨다.
 c.aside=async()=>{const q=await c.serial(()=>raw.evaluate(()=>{const s=getSelection();const n=s?.anchorNode,el=n?.nodeType===1?n:n?.parentElement;const a=document.activeElement;
   if(a?.matches('input,textarea')){const r=a.getBoundingClientRect();return{x:Math.min(innerWidth-30,r.x+24),y:Math.min(innerHeight-30,r.bottom+22)};}
   const b=el?.closest('[data-block-id]')||el?.closest('h1,[contenteditable=true]');if(!b)throw Error('No caret block for aside');const r=b.getBoundingClientRect();return{x:Math.min(innerWidth-30,r.x+24),y:Math.min(innerHeight-30,r.bottom+22)};}));await c.move(q.x,q.y);};
 c.park=c.aside;
 c.type=async text=>{
  if((await c.serial(()=>raw.url())).includes(ctx.protect))throw Error('Preserved original (config.protect): typing forbidden');
  const f=await c.serial(()=>raw.evaluate(()=>{const e=document.activeElement;return !!(e?.isContentEditable||e?.matches('input,textarea'))&&!e.closest('[data-testid="agent-chat-view"]')&&!e.getAttribute('placeholder')?.includes('AI로');}));
  if(!f)throw Error('Typing target is not an editor');
  await c.aside();await gate();
  let i=0;for(const ch of text){await c.serial(()=>raw.keyboard.insertText(ch));await sleep([105,125,95,135,110][i++%5]);}
 };
 c.key=async k=>{await gate();await c.serial(()=>raw.keyboard.press(k));await sleep(200);};
 // 안내 상자 안 빈 줄에서 Enter로 상자 밖에 나간다. 1.5초 안에 반영되지 않으면(take-26 실측) 한 번 더 누르고 기록한다.
 const outside=()=>c.serial(()=>raw.evaluate(()=>{const n=getSelection()?.anchorNode,e=n?.nodeType===1?n:n?.parentElement;return !!e&&!e.closest('[role=note]');}));
 c.exitCallout=async()=>{
  await c.key('Enter');for(let i=0;i<8&&!(await outside());i++)await sleep(200);
  if(!(await outside())){await ctx.fs.appendFile(ctx.out+'/reclicks.jsonl',JSON.stringify({key:'Enter',reason:'callout exit not applied within 1.5s'})+String.fromCharCode(10));await c.key('Enter');
   for(let i=0;i<15&&!(await outside());i++)await sleep(200);if(!(await outside()))throw Error('Could not leave the callout with Enter');}
 };
 // 제목 바꾸기: 기존 제목 전체가 선택된 것을 확인한 뒤 입력(37번 '새' 잔류 결함 수정).
 // 제목 바꾸기: 제목 글자를 마우스로 처음부터 끝까지 끌어 선택하고, 전체 선택을 확인한 뒤 입력한다.
 // End → Shift+Home은 Notion 제목에서 End가 끝으로 가지 않아 일부만 선택됐다(오전 full-take9 '새' 잔류, take-37 '새'만 선택).
 c.replaceTitle=async text=>{
  const r=await c.serial(()=>raw.evaluate(()=>{const h=[...document.querySelectorAll('h1[contenteditable=true]')].find(h=>h.checkVisibility({checkVisibilityCSS:true}));if(!h||!h.textContent)throw Error('Visible title missing');
   const w=document.createTreeWalker(h,NodeFilter.SHOW_TEXT),ns=[];let n;while(n=w.nextNode())if(n.length)ns.push(n);
   const a=document.createRange(),b=document.createRange();a.setStart(ns[0],0);a.setEnd(ns[0],1);const l=ns.at(-1);b.setStart(l,l.length-1);b.setEnd(l,l.length);
   const ra=a.getBoundingClientRect(),rb=b.getBoundingClientRect();return{x0:ra.left+1,y0:ra.top+ra.height/2,x1:rb.right+2,y1:rb.top+rb.height/2,text:h.textContent};}));
  // 한 번에 다 선택되지 않으면 사람처럼 다시 끈다(take-37b: 녹화 중 한 번 선택이 안 잡힘, 같은 화면 시험에서는 한 번에 됨).
  const selected=()=>c.serial(()=>raw.waitForFunction(t=>getSelection().toString()===t,r.text,{timeout:1500})).then(()=>true,()=>false);
  let ok=false;
  for(let k=0;k<2&&!ok;k++){await c.move(r.x0,r.y0);await gate();await c.serial(()=>raw.mouse.down());await c.move(r.x1,r.y1);await c.serial(()=>raw.mouse.up());ok=await selected();
   if(!ok)await ctx.fs.appendFile(ctx.out+'/reclicks.jsonl',JSON.stringify({action:'title drag',reason:'not fully selected',try:k+1})+String.fromCharCode(10));}
  if(!ok)throw Error('Title text was not fully selected by drag twice: '+r.text);
  await c.type(text);
  await c.serial(()=>raw.waitForFunction(t=>[...document.querySelectorAll('h1[contenteditable=true]')].some(h=>h.checkVisibility({checkVisibilityCSS:true})&&h.textContent===t),text,{timeout:5000})).catch(()=>{throw Error('Title is not exactly '+text);});
 };
 return c;
}
