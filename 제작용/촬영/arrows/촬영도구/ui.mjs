// ARROWS 조작 층. Notion v10(ui-v10.mjs)의 이동·실행 방식을 그대로 쓴다.
// - 표시 포인터: 페이지 안 SVG(흰 화살표·얇은 검은 테두리·후광 없음)를 element.animate로 이동.
// - 실제 입력: 같은 경로·시각으로 mouse.move(steps:1) 16회. RPC마다 직렬 큐를 잠깐 쓰고 놓는다.
// - gate(): 큐가 정한 실행 시점(행동 문장 끝 약250ms 전)까지 기다린 뒤 클릭·입력·키를 보낸다.
// - 원 위치: 캔버스 arc/fillText 호출을 기록해 Caption 글자가 들어 있는 원을 찾는다(화면 좌표, 추측 좌표 없음).
export async function makeUI(ctx){
 const raw=ctx.p, sleep=ctx.sleep, q1=fn=>ctx.serial(fn);
 let lastPos=ctx.startPos, lastMoveEnd=0;
 const gate=async()=>{const until=Math.max(ctx.commitAt||0,lastMoveEnd+150);const w=until-Date.now();if(w>0)await sleep(w);ctx.committed??=Date.now();};
 const pointerPos=()=>raw.evaluate(()=>{const r=document.getElementById('recording-pointer')?.getBoundingClientRect();if(!r)throw Error('Recording pointer missing');return{x:r.x,y:r.y};});
 async function install(){
  await q1(()=>raw.evaluate(pos=>{
   document.removeEventListener('mousemove',window.__tutorialMove,true);document.removeEventListener('mousedown',window.__tutorialDown,true);
   document.getElementById('recording-pointer')?.remove();
   const e=document.createElement('div');e.id='recording-pointer';e.setAttribute('aria-hidden','true');
   e.style.cssText='position:fixed;left:0;top:0;width:20px;height:27px;pointer-events:none;z-index:2147483647;will-change:transform;transform:'+`translate(${pos.x}px,${pos.y}px)`;
   e.innerHTML='<svg xmlns="http://www.w3.org/2000/svg" width="20" height="27" viewBox="0 0 25 34"><path d="M1 1 L1 25 L7 20 L12 31 L17 29 L12 18 L22 18 Z" fill="white" stroke="#111" stroke-width="1.7" stroke-linejoin="round"/></svg>';
   document.documentElement.append(e);window.__tutorialClicks??=[];window.__glide=null;
   window.__tutorialMove=ev=>{if(!window.__glide)e.style.transform=`translate(${ev.clientX}px,${ev.clientY}px)`;};
   window.__tutorialDown=ev=>{const r=e.getBoundingClientRect();window.__tutorialClicks.push({x:ev.clientX,y:ev.clientY,px:r.x,py:r.y,trusted:ev.isTrusted,gliding:!!window.__glide,time:performance.now(),url:location.href});};
   document.addEventListener('mousemove',window.__tutorialMove,true);document.addEventListener('mousedown',window.__tutorialDown,true);
   window.__startGlide=(ax,ay,x,y,ms)=>{window.__glide?.cancel();const kf=[];for(let i=0;i<=20;i++){const t=i/20,u=t*t*(3-2*t);kf.push({transform:`translate(${ax+(x-ax)*u}px,${ay+(y-ay)*u}px)`,offset:t});}
    const a=e.animate(kf,{duration:ms,easing:'linear',fill:'forwards'});window.__glide=a;
    a.onfinish=()=>{e.style.transform=`translate(${x}px,${y}px)`;a.cancel();if(window.__glide===a)window.__glide=null;};};
   // 캔버스 기록: 그린 원·글자의 화면 좌표와 시각. 원래 함수는 한 번만 보관하고 설치 때마다 새로 감싼다.
   const P=CanvasRenderingContext2D.prototype;P.__orig??={arc:P.arc,fillText:P.fillText};
   {const cv=document.querySelector('canvas');if(cv){cv.__arcs=[];cv.__texts=[];}}
   {const scr=(c,x,y)=>{const m=c.getTransform(),r=c.canvas.getBoundingClientRect();return{x:r.x+(m.a*x+m.c*y+m.e)*r.width/c.canvas.width,y:r.y+(m.b*x+m.d*y+m.f)*r.height/c.canvas.height,k:Math.hypot(m.a,m.b)*r.width/c.canvas.width};};
    const main=c=>c.canvas===document.querySelector('canvas');const keep=a=>{if(a.length>3000)a.splice(0,a.length-1500);return a;};
    const oa=P.__orig.arc;P.arc=function(x,y,rad,...a){if(main(this)){const s=scr(this,x,y);keep(this.canvas.__arcs??=[]).push({x:s.x,y:s.y,r:rad*s.k,t:performance.now()});}return oa.call(this,x,y,rad,...a);};
    const ot=P.__orig.fillText;P.fillText=function(t,x,y,...a){if(main(this)){const w=this.measureText(t).width,off=this.textAlign==='center'?0:(this.textAlign==='right'||this.textAlign==='end')?-w/2:w/2;const s=scr(this,x+off,y);keep(this.canvas.__texts??=[]).push({t:String(t),x:s.x,y:s.y,at:performance.now()});}return ot.call(this,t,x,y,...a);};
   }
  },lastPos));
 }
 async function moveCore(x,y){
  const a=await q1(pointerPos);const dist=Math.hypot(x-a.x,y-a.y);if(dist<1){lastMoveEnd=Date.now();lastPos={x,y};return;}
  const ms=Math.round(Math.max(260,Math.min(620,200+dist*0.4)));const t0=Date.now();
  await q1(()=>raw.evaluate(({ax,ay,x,y,ms})=>window.__startGlide(ax,ay,x,y,ms),{ax:a.x,ay:a.y,x,y,ms}));
  for(let i=1;i<=16;i++){const t=i/16,u=t*t*(3-2*t);const w=t0+ms*t-Date.now();if(w>0)await sleep(w);await q1(()=>raw.mouse.move(a.x+(x-a.x)*u,a.y+(y-a.y)*u,{steps:1}));}
  for(let n=0;n<60&&await q1(()=>raw.evaluate(()=>!!window.__glide));n++)await sleep(20);
  ctx.recordMotion?.({start:t0,end:Date.now(),x,y,from:a,planned_ms:ms});lastMoveEnd=Date.now();lastPos={x,y};
 }
 // 원 찾기: 마지막으로 그린 한 판에서 Caption 글자(줄바꿈 조각)를 담은 원. 기록이 비면 resize로 한 번 다시 그리게 한다.
 // arrows는 그림 전체를 화면에 자동으로 맞추므로 저장 좌표로 화면 위치를 계산하지 않는다.
 // 화면 맞춤 애니메이션 중이면 위치가 움직이므로, 150ms 간격으로 두 번 읽어 2px 안으로 같을 때 쓴다.
 async function node(caption){
  let prev=null;
  for(let k=0;k<12;k++){const r=await node1(caption);if(prev&&Math.hypot(prev.x-r.x,prev.y-r.y)<2&&Math.abs(prev.r-r.r)<1)return r;prev=r;await sleep(150);}
  return prev;
 }
 async function node1(caption){
  for(let i=0;i<10;i++){
   const r=await q1(()=>raw.evaluate(cap=>new Promise(res=>{const c=document.querySelector('canvas');if(!(c.__arcs||[]).length)window.dispatchEvent(new Event('resize'));
    requestAnimationFrame(()=>requestAnimationFrame(()=>{
     const A=(c.__arcs||[]).filter(a=>a.t>0),T=(c.__texts||[]).filter(t=>t.at>0),la=Math.max(0,...A.map(a=>a.t)),lt=Math.max(0,...T.map(t=>t.at));
     const arcs=A.filter(a=>a.t>=la-20&&a.r<160&&a.r>Math.max(8,0.75*Math.max(...A.filter(b=>b.t>=la-20&&b.r<160).map(b=>b.r)))),texts=T.filter(t=>t.at>=lt-20),want=cap.replace(/\s/g,'');
     const seen=[];for(const a of [...arcs].sort((p,q)=>p.r-q.r)){if(seen.some(s=>Math.hypot(s.x-a.x,s.y-a.y)<4))continue;seen.push(a);}
     const part=t=>{const v=t.t.replace(/\s/g,'');return v&&want.includes(v);};
     const LABELS=['Asset','Component','Sensor','Symptom','FailureMode','Cause','Skill','ManualSection'];const other=t=>{const v=t.t.trim();return v&&!part(t)&&!LABELS.includes(v)&&!/^[A-Z_]+$/.test(v);};
     const near=t=>seen.reduce((m,c)=>Math.hypot(c.x-t.x,c.y-t.y)<Math.hypot(m.x-t.x,m.y-t.y)?c:m);
     const hits=seen.map(a=>{const inn=texts.filter(t=>Math.hypot(t.x-a.x,t.y-a.y)<a.r*0.95&&near(t)===a);return{a,bad:inn.some(other),j:inn.filter(part).sort((p,q)=>p.y-q.y).map(t=>t.t).join('').replace(/\s/g,'')};}).filter(h=>h.j===want&&!h.bad);
     if(hits.length!==1)return res({error:cap+' matched '+hits.length+' of '+seen.length+' circles'});
     res({x:hits[0].a.x,y:hits[0].a.y,r:hits[0].a.r});
    }));}),caption));
   if(!r.error)return r;
   if(i===9)throw Error('Node not found on canvas: '+r.error);
   await q1(()=>raw.evaluate(()=>window.dispatchEvent(new Event('resize'))));await sleep(150);
  }
 }
 // 마지막 판의 원 목록(겹침 확인용).
 async function circles(){
  for(let i=0;i<8;i++){const r=await circles0();if(r.list.length)return r;await q1(()=>raw.evaluate(()=>window.dispatchEvent(new Event('resize'))));await sleep(150);}
  throw Error('No circles on canvas');
 }
 async function circles0(){
  return q1(()=>raw.evaluate(()=>{const c=document.querySelector('canvas'),A=(c.__arcs||[]).filter(a=>a.t>0),la=Math.max(0,...A.map(a=>a.t));const out=[];for(const a of A.filter(a=>a.t>=la-20&&a.r<160&&a.r>Math.max(8,0.75*Math.max(...A.filter(b=>b.t>=la-20&&b.r<160).map(b=>b.r)))).sort((p,q)=>p.r-q.r)){if(!out.some(s=>Math.hypot(s.x-a.x,s.y-a.y)<4))out.push({x:a.x,y:a.y,r:a.r});}
   const b=c.getBoundingClientRect();return{list:out,box:{l:b.left,t:b.top,r:b.right,b:b.bottom}};}));
 }
 // 패널·메뉴의 DOM 대상 좌표. 화면 밖이면 오류(배치를 바꾸지 않는다).
 async function dom(name){
  const r=await q1(()=>raw.evaluate(name=>{
   const vis=e=>{const b=e.getBoundingClientRect();return b.width>0&&b.height>0&&b.bottom>0&&b.top<innerHeight&&b.right>0&&b.left<innerWidth;};
   const btn=t=>[...document.querySelectorAll('button,a')].filter(e=>vis(e)&&e.textContent.trim()===t);
   const field=(title,pick)=>{const lab=[...document.querySelectorAll('form *')].find(e=>e.childElementCount===0&&e.textContent.trim()===title&&vis(e));if(!lab)return [];let box=lab.parentElement,ins=[];for(let k=0;k<3&&!ins.length;k++){ins=[...box.querySelectorAll('input')].filter(vis);if(!ins.length)box=box.parentElement;}return pick(ins);};
   let es;
   if(name==='addNode')es=[...document.querySelectorAll('button')].filter(e=>vis(e)&&e.textContent.trim()==='Add Node');
   else if(name==='customize')es=btn('Customize');
   else if(name==='reverse')es=btn('Reverse');
   else if(name==='cypherText')es=[...document.querySelectorAll('.modal textarea, .modal pre, .modal code')].filter(vis).slice(0,1);
   else if(name==='panelToggle')es=[...document.querySelectorAll('a.item')].filter(e=>{const r=e.getBoundingClientRect();return vis(e)&&r.x>innerWidth-80&&r.y<45;}).slice(-1);
   else if(name==='labelPlus')es=btn('Label');
   else if(name==='propPlus')es=btn('Property');
   else if(name==='export')es=btn('Download / Export');
   else if(name==='done')es=btn('Done');
   else if(name==='download')es=btn('Download').slice(0,1);
   else if(name==='importButton')es=[...document.querySelectorAll('button')].filter(e=>vis(e)&&e.textContent.trim()==='Import'&&!e.closest('[role=listbox]'));
   else if(name==='chooseFile')es=btn('Choose File');
   else if(name.startsWith('tab:'))es=[...document.querySelectorAll('a,button,.item')].filter(e=>vis(e)&&e.textContent.trim()===name.slice(4)&&!e.closest('[role=listbox]'));
   else if(name==='logo')es=[...document.querySelectorAll('[role=listbox]')].filter(vis).slice(0,1);
   else if(name==='menu:New')es=[...document.querySelectorAll('[role=option]')].filter(e=>vis(e)&&e.textContent.startsWith('NewStore'));
   else if(name==='menu:newLocal'){const n=[...document.querySelectorAll('[role=option]')].find(e=>e.textContent.startsWith('NewStore'));es=n?[...n.querySelectorAll('[role=option]')].filter(e=>vis(e)&&e.textContent.trim()==='Web Browser storage'):[];}
   else if(name==='menu:Import')es=[...document.querySelectorAll('[role=option]')].filter(e=>vis(e)&&e.textContent.trim()==='Import');
   else if(name==='caption')es=field('Caption',a=>a.slice(0,1));
   else if(name==='type')es=field('Type',a=>a.slice(0,1));
   else if(name==='labelInput')es=field('Labels',a=>a.slice(-1));
   else if(name==='propKey')es=field('Properties',a=>a.slice(-2,-1));
   else if(name==='propVal')es=field('Properties',a=>a.slice(-1));
   else if(name.startsWith('style:')){const row=[...document.querySelectorAll('form tr')].find(r=>vis(r)&&r.querySelector('td')?.textContent.trim()===name.slice(6)+':');es=row?[...row.querySelectorAll('input')].slice(0,1):[];}
   else return{error:'unknown target '+name};
   if(!es||es.length!==1)return{error:'target '+name+' matched '+(es?es.length:0)};
   const b=es[0].getBoundingClientRect();const inp=es[0].tagName==='INPUT';
   return{x:inp?b.x+Math.min(40,b.width/3):b.x+b.width/2,y:b.y+b.height/2,input:inp,bottom:b.bottom,left:b.x};
  },name));
  if(r.error)throw Error(r.error);return r;
 }
 const FIXED={canvasMid:{x:560,y:430},panelMid:{x:1290,y:300}};
 // 빈 곳: 고정 좌표는 배치가 바뀌면 원·화살표에 맞아 선택이 풀리지 않는다(10구간 radius가 원 하나에만 들어간 원인).
 // 지금 화면의 원·화살표·글자에서 가장 먼 캔버스 지점을 고른다.
 async function blank(){
  return q1(()=>raw.evaluate(()=>{
   const c=document.querySelector('canvas'),b=c.getBoundingClientRect(),A=(c.__arcs||[]).filter(a=>a.t>0),la=Math.max(0,...A.map(a=>a.t));
   const arcs=[];for(const a of A.filter(a=>a.t>=la-20&&a.r<160&&a.r>Math.max(8,0.75*Math.max(...A.filter(b=>b.t>=la-20&&b.r<160).map(b=>b.r)))).sort((p,q)=>q.r-p.r))if(!arcs.some(s=>Math.hypot(s.x-a.x,s.y-a.y)<4))arcs.push(a);
   const T=(c.__texts||[]).filter(t=>t.at>0),lt=Math.max(0,...T.map(t=>t.at)),texts=T.filter(t=>t.at>=lt-20&&t.t.trim());
   // 화살표 선분: 저장 좌표 범위와 화면 원 중심 범위를 맞춰 옮긴다(arrows는 그림 전체를 화면에 맞춘다).
   const id=location.hash.split('id=')[1],g=JSON.parse(localStorage.getItem('GRAPH|'+id)).graph,P=Object.fromEntries(g.nodes.map(n=>[n.id,n.position]));
   const gx=g.nodes.map(n=>n.position.x),gy=g.nodes.map(n=>n.position.y),sx=arcs.map(a=>a.x),sy=arcs.map(a=>a.y);
   const k=(Math.max(...sx)-Math.min(...sx))/((Math.max(...gx)-Math.min(...gx))||1),tx=x=>Math.min(...sx)+(x-Math.min(...gx))*k,ty=y=>Math.min(...sy)+(y-Math.min(...gy))*k;
   const segs=g.relationships.filter(r=>P[r.fromId]&&P[r.toId]).map(r=>[{x:tx(P[r.fromId].x),y:ty(P[r.fromId].y)},{x:tx(P[r.toId].x),y:ty(P[r.toId].y)}]);
   let best=null;
   for(let x=b.left+40;x<=b.right-40;x+=30)for(let y=b.top+40;y<=b.bottom-40;y+=30){
    let s=Infinity;for(const a of arcs)s=Math.min(s,Math.hypot(a.x-x,a.y-y)-a.r);
    for(const [p,q] of segs){const vx=q.x-p.x,vy=q.y-p.y,L=vx*vx+vy*vy||1,t=Math.max(0,Math.min(1,((x-p.x)*vx+(y-p.y)*vy)/L));s=Math.min(s,Math.hypot(p.x+t*vx-x,p.y+t*vy-y));}
    for(const t of texts)s=Math.min(s,Math.hypot(t.x-x,t.y-y)-30);
    if(!best||s>best.s)best={x,y,s};}
   return best;}));
 }
 async function point(name){
  if(name==='blank')return blank();
  if(FIXED[name])return FIXED[name];
  if(name.startsWith('node:'))return node(name.slice(5));
  if(name.startsWith('look:')){const n=await node(name.slice(5));return{x:n.x+n.r*0.78,y:n.y+n.r*0.78};}
  if(name.startsWith('props:')){const n=await node(name.slice(6));return{x:n.x+n.r+40,y:n.y};}
  return dom(name);
 }
 const ui={raw,install,gate,node,dom,circles,
  pos:()=>lastPos,
  move:async(x,y)=>{await moveCore(x,y);},
  point:async name=>{const q=await point(name);await moveCore(q.x,q.y);},
  click:async name=>{
   for(let i=0;i<4;i++){
    const q=await point(name);await moveCore(q.x,q.y);await gate();const now=name==='blank'?q:await point(name);
    if(Math.hypot(now.x-q.x,now.y-q.y)>2)continue;
    await q1(()=>raw.mouse.click(now.x,now.y));await sleep(160);
    if(now.input)ctx.focusBox=now;return;
   }
   throw Error('Target layout did not settle: '+name);
  },
  // 입력 중에는 입력칸 바로 아래 여백으로 비킨다.
  type:async text=>{
   const ok=await q1(()=>raw.evaluate(()=>document.activeElement?.matches('input,textarea')));if(!ok)throw Error('Typing target is not an input');
   if(ctx.focusBox)await moveCore(ctx.focusBox.left+24,ctx.focusBox.bottom+22);
   await gate();let i=0;for(const ch of text){await q1(()=>raw.keyboard.insertText(ch));await sleep([105,125,95,135,110][i++%5]);}
  },
  key:async k=>{await gate();await q1(()=>raw.keyboard.press(k));await sleep(200);},
  // 간격 넓히기: 그림 중심에서 먼 원부터 바깥쪽으로 dist만큼 끈다. 가장자리에 닿으면 arrows가 그림 전체를 축소해 맞춘다.
  spread:async(count,dist)=>{
   const {list,box}=await circles();const cx=list.reduce((a,c)=>a+c.x,0)/list.length,cy=list.reduce((a,c)=>a+c.y,0)/list.length;
   const far=[...list].sort((p,q)=>Math.hypot(q.x-cx,q.y-cy)-Math.hypot(p.x-cx,p.y-cy)).slice(0,count);
   for(const f of far){const cur=(await circles()).list.reduce((b,c)=>Math.hypot(c.x-f.x,c.y-f.y)<Math.hypot(b.x-f.x,b.y-f.y)?c:b);
    const a=Math.atan2(cur.y-cy,cur.x-cx);let tx=cur.x+dist*Math.cos(a),ty=cur.y+dist*Math.sin(a);
    tx=Math.max(box.l+cur.r*0.6,Math.min(box.r-cur.r*0.6,tx));ty=Math.max(box.t+cur.r*0.6,Math.min(box.b-cur.r*0.6,ty));
    await moveCore(cur.x,cur.y);await gate();await q1(()=>raw.mouse.down());await moveCore(tx,ty);await q1(()=>raw.mouse.up());await sleep(350);}
  },
  // 배치 정리: 원을 기준 원(anchor)에서 반지름 단위 (dx,dy) 위치로 끈다. 옮긴 뒤 겹치거나 그림이 크게 줄면(폭주) 실행 취소하고 다음으로 넘어간다.
  arrange:async moves=>{
   const done=[];
   for(const [cap,anchor,dx,dy] of moves){
    const before=await circles();const n=await node(cap),a=await node(anchor);const r=a.r,tx=a.x+dx*r,ty=a.y+dy*r,b=before.box;
    if(tx<b.l+r*0.8||tx>b.r-r*0.8||ty<b.t+r*0.8||ty>b.b-r*0.8||before.list.some(c=>Math.hypot(c.x-n.x,c.y-n.y)>4&&Math.hypot(c.x-tx,c.y-ty)<c.r+r+30)){done.push(cap+':skip');continue;}
    await moveCore(n.x,n.y);await gate();await q1(()=>raw.mouse.down());await moveCore(tx,ty);await q1(()=>raw.mouse.up());await sleep(400);
    const after=await circles();const m=await node(cap);const rs=after.list[0].r;
    const bad=rs<r*0.8||after.list.some(c=>c.x<b.l||c.x>b.r||c.y<b.t||c.y>b.b)||after.list.some(c=>Math.hypot(c.x-m.x,c.y-m.y)>4&&Math.hypot(c.x-m.x,c.y-m.y)<c.r+m.r);
    if(bad){await q1(()=>raw.keyboard.press('ControlOrMeta+Z'));await sleep(400);done.push(cap+':undo');}else done.push(cap+':ok');
   }
   return done;
  },
  // 배치 정리(절대 위치): 화면을 보고 정한 CSS 좌표로 원을 끈다. 그림이 15% 넘게 줄면(가장자리 폭주) 그 한 번만 실행 취소한다.
  place:async moves=>{
   const done=[];
   for(const [cap,tx,ty] of moves){
    const r0=(await circles()).list[0].r;const n=await node(cap);
    await moveCore(n.x,n.y);await gate();await q1(()=>raw.mouse.down());await moveCore(tx,ty);await q1(()=>raw.mouse.up());await sleep(400);
    const r1=(await circles()).list[0].r;if(r1<r0*0.85){await q1(()=>raw.keyboard.press('ControlOrMeta+Z'));await sleep(400);done.push(cap+':undo');}else done.push(cap+':ok');
   }
   return done;
  },
  // 그림 좌표 배치: 두 기준 원의 저장 좌표·화면 좌표로 배율을 재서 목표 그림 좌표를 화면 좌표로 바꾼 뒤 끈다(원 하나마다 다시 잰다).
  // 목표는 현재 그림 범위 안이므로 arrows가 화면을 다시 맞추지 않는다. 옮긴 뒤 저장 좌표가 목표와 맞는지 확인한다.
  layout:async(moves,ref)=>{
   const G=()=>q1(()=>raw.evaluate(()=>{const id=location.hash.split('id=')[1];return JSON.parse(localStorage.getItem('GRAPH|'+id)).graph.nodes.map(n=>[n.caption,n.position.x,n.position.y]);}));
   const res={};
   for(const [cap,gx,gy] of moves){
    const g=Object.fromEntries((await G()).map(([c,x,y])=>[c,{x,y}]));
    if(Math.hypot(g[cap].x-gx,g[cap].y-gy)<20){res[cap]=cap+':0,0';continue;}
    const A=await node(ref[0]),B=await node(ref[1]),ga=g[ref[0]],gb=g[ref[1]];const k=(B.x-A.x)/(gb.x-ga.x);
    const tx=A.x+(gx-ga.x)*k,ty=A.y+(gy-ga.y)*k;const n=await node(cap);
    await moveCore(n.x,n.y);await gate();await q1(()=>raw.mouse.down());await moveCore(tx,ty);await q1(()=>raw.mouse.up());await sleep(400);
    await q1(()=>raw.waitForFunction(()=>document.body.innerText.includes('Saved to Web Browser storage'),undefined,{timeout:8000})).catch(()=>{});
    const p=Object.fromEntries((await G()).map(([c,x,y])=>[c,{x,y}]))[cap];res[cap]=cap+':'+Math.round(p.x-gx)+','+Math.round(p.y-gy);
   }
   return moves.map(([c])=>res[c]);
  },
  // Ctrl을 누른 채 클릭(여러 원 함께 선택).
  ctrlclick:async name=>{const q=await point(name);await moveCore(q.x,q.y);await gate();await q1(()=>raw.keyboard.down('Control'));await q1(()=>raw.mouse.click(q.x,q.y));await q1(()=>raw.keyboard.up('Control'));await sleep(160);},
  // 원 테두리를 빈 곳으로 끌어 새 원+화살표 만들기. 놓을 자리에 다른 원이 있거나 그림 밖이면 각도를 15도씩 돌려 빈 곳을 찾는다.
  grow:async(source,deg)=>{
   const s=await node(source);await ui.click('node:'+source);
   // 이미 이어진 화살표 방향은 피한다(시작점이 화살표 위에 놓이면 원 대신 화살표를 잡는다).
   const nb=await q1(()=>raw.evaluate(cap=>{const id=location.hash.split('id=')[1];const g=JSON.parse(localStorage.getItem('GRAPH|'+id)).graph;const me=g.nodes.find(n=>n.caption===cap);const by=Object.fromEntries(g.nodes.map(n=>[n.id,n.caption]));return g.relationships.filter(r=>r.fromId===me.id||r.toId===me.id).map(r=>by[r.fromId===me.id?r.toId:r.fromId]);},source));
   const busy=[];for(const c of nb){const t=await node(c);busy.push(Math.atan2(t.y-s.y,t.x-s.x));}
   // 모든 화살표 선분: 시작점이 어떤 화살표 근처(16px)에 놓이면 원 대신 화살표를 잡으므로 피한다.
   const rels=await q1(()=>raw.evaluate(()=>{const id=location.hash.split('id=')[1];const g=JSON.parse(localStorage.getItem('GRAPH|'+id)).graph;const by=Object.fromEntries(g.nodes.map(n=>[n.id,n.caption]));return g.relationships.map(r=>[by[r.fromId],by[r.toId]]);}));
   const pos={};for(const [a,b] of rels)for(const c of [a,b])if(c&&!pos[c])pos[c]=await node(c);
   const segs=rels.filter(([a,b])=>pos[a]&&pos[b]).map(([a,b])=>[pos[a],pos[b]]);
   const nearSeg=(x,y)=>segs.some(([p,q])=>{const vx=q.x-p.x,vy=q.y-p.y,L=vx*vx+vy*vy||1,t=Math.max(0,Math.min(1,((x-p.x)*vx+(y-p.y)*vy)/L));return Math.hypot(p.x+t*vx-x,p.y+t*vy-y)<16;});
   // 원 바깥에 표시된 글자(조건 Property·관계 이름) 위를 잡으면 원 대신 글자를 잡으므로 피한다.
   const texts=await q1(()=>raw.evaluate(()=>{const c=document.querySelector('canvas'),T=(c.__texts||[]).filter(t=>t.at>0),lt=Math.max(0,...T.map(t=>t.at));return T.filter(t=>t.at>=lt-20&&t.t.trim()).map(t=>({x:t.x,y:t.y}));}));
   const {list,box}=await circles();const r=s.r;let pick=null;
   for(const f of [6.6,6.0,5.3,4.6,4.0])for(let k=0;k<=12&&!pick;k++)for(const sg of k?[1,-1]:[1]){if(pick)break;const d=r*f,a=(deg+15*k*sg)*Math.PI/180,x=s.x+d*Math.cos(a),y=s.y+d*Math.sin(a);
    if(busy.some(b=>Math.abs(Math.atan2(Math.sin(a-b),Math.cos(a-b)))<0.45))continue;
    if(nearSeg(s.x+r*1.09*Math.cos(a),s.y+r*1.09*Math.sin(a)))continue;
    if(texts.some(t=>Math.hypot(t.x-(s.x+r*1.09*Math.cos(a)),t.y-(s.y+r*1.09*Math.sin(a)))<22))continue;
    if(x<box.l+r*0.7||x>box.r-r*0.7||y<box.t+r*0.7||y>box.b-r*0.7)continue;if(list.some(c=>Math.hypot(c.x-x,c.y-y)<c.r+r+40))continue;pick={a,x,y};break;}
   if(!pick)throw Error('No free spot around '+source);
   const sx=s.x+r*1.09*Math.cos(pick.a),sy=s.y+r*1.09*Math.sin(pick.a);
   const n0=(await circles()).list.length;
   await moveCore(sx,sy);await gate();await q1(()=>raw.mouse.down());await moveCore(pick.x,pick.y);await q1(()=>raw.mouse.up());await sleep(300);
   const n1=(await circles()).list.length;if(n1!==n0+1)throw Error(`grow from ${source}: circles ${n0} -> ${n1}`);
  },
  // 두 원 사이 화살표를 눌러 관계 선택(Type 칸 확인).
  edge:async(a,b)=>{
   // 한가운데 대신 출발 원 쪽 35% 지점: 여러 화살표가 모이는 도착 원 근처에서 다른 선을 누르지 않게 한다.
   const p=await node(a),t=await node(b);const x=p.x+(t.x-p.x)*0.35,y=p.y+(t.y-p.y)*0.35;
   await moveCore(x,y);await gate();await q1(()=>raw.mouse.click(x,y));await sleep(200);
   await q1(()=>raw.waitForFunction(()=>[...document.querySelectorAll('form *')].some(e=>e.childElementCount===0&&e.textContent.trim()==='Type'),undefined,{timeout:3000})).catch(()=>{throw Error('Relationship not selected between '+a+' and '+b);});
  },
  // 이미 있는 원을 화면에서 (dx,dy)만큼 끌어 옮기기(겹침·이름 잘림 정리). 끝난 뒤 실제로 움직였는지 확인한다.
  move:async(caption,dx,dy)=>{
   const n=await node(caption);await moveCore(n.x,n.y);await gate();await q1(()=>raw.mouse.down());await moveCore(n.x+dx,n.y+dy);await q1(()=>raw.mouse.up());await sleep(300);
   const m=await node(caption);const others=(await circles()).list.filter(c=>Math.hypot(c.x-m.x,c.y-m.y)>4);
   if(others.some(c=>Math.hypot(c.x-m.x,c.y-m.y)<c.r+m.r))throw Error('After move '+caption+' overlaps another node');
  },
  drag:async(caption,x,y)=>{
   const n=await node(caption);await moveCore(n.x,n.y);await gate();
   await q1(()=>raw.mouse.down());await moveCore(x,y);await q1(()=>raw.mouse.up());await sleep(200);
   const m=await node(caption);if(Math.hypot(m.x-x,m.y-y)>12)throw Error(`Drag ${caption}: at ${Math.round(m.x)},${Math.round(m.y)} expected ${x},${y}`);
  },
  connect:async(a,b)=>{
   const p=await node(a),t=await node(b);const base=Math.atan2(t.y-p.y,t.x-p.x);
   const rels=await q1(()=>raw.evaluate(()=>{const id=location.hash.split('id=')[1];const g=JSON.parse(localStorage.getItem('GRAPH|'+id)).graph;const by=Object.fromEntries(g.nodes.map(n=>[n.id,n.caption]));return g.relationships.map(r=>[by[r.fromId],by[r.toId]]);}));
   const pos={};for(const [x,y] of rels)for(const c of [x,y])if(c&&!pos[c])pos[c]=await node(c);
   const segs=rels.filter(([x,y])=>pos[x]&&pos[y]).map(([x,y])=>[pos[x],pos[y]]);
   const near=(x,y)=>segs.some(([P,Q])=>{const vx=Q.x-P.x,vy=Q.y-P.y,L=vx*vx+vy*vy||1,u=Math.max(0,Math.min(1,((x-P.x)*vx+(y-P.y)*vy)/L));return Math.hypot(P.x+u*vx-x,P.y+u*vy-y)<16;});
   let ang=base;for(const d of [0,0.25,-0.25,0.5,-0.5,0.75,-0.75]){const g=base+d;if(!near(p.x+Math.cos(g)*p.r*1.09,p.y+Math.sin(g)*p.r*1.09)){ang=g;break;}}
   const sx=p.x+Math.cos(ang)*p.r*1.09,sy=p.y+Math.sin(ang)*p.r*1.09;
   await moveCore(sx,sy);await gate();await q1(()=>raw.mouse.down());await moveCore(t.x,t.y);await q1(()=>raw.mouse.up());await sleep(250);
   await q1(()=>raw.waitForFunction(()=>[...document.querySelectorAll('form *')].some(e=>e.childElementCount===0&&e.textContent.trim()==='Type'),undefined,{timeout:3000})).catch(()=>{throw Error('Relationship not created: '+a+' -> '+b);});
  },
 };
 return ui;
}
