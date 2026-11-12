// 포털 조작 층(Notion v10 ui.mjs의 이동 · 화살표 · gate를 그대로 옮기고 대상 찾기만 포털 DOM으로 바꿈).
// - 표시 포인터: 컴포지터 애니메이션으로 이동, 실제 입력도 같은 경로 8단계(순간이동 없음). 실제 입력이 모두 끝날 때까지 화살표를 목표에 고정(hold).
// - gate(): 큐가 정한 실행 시점(행동 문장 끝 약 250ms 전)까지 대기. 클릭 · 키 · 입력 · 스크롤은 모두 gate를 거친다.
// - 대상: {tab:'scenario'} 왼쪽 메뉴, {text:'글자', within:'css'} 보이는 요소 중 글자가 정확히 같은 가장 안쪽 요소, {css:'선택자'}.
//   위치가 움직이는 대상은 150ms 간격 두 번 같은 위치일 때 출발하고, 누르기 직전에 다시 읽어 움직였으면 다시 간다.

// 페이지 안 녹화 포인터(흰 화살표 · 얇은 검은 테두리, 후광 없음)와 이동 애니메이션. 페이지에서 실행되는 함수라 바깥 변수를 쓰지 않는다.
export function installPointerInPage(pos){
  document.removeEventListener('mousemove',window.__tutorialMove,true);document.removeEventListener('mousedown',window.__tutorialDown,true);
  const old=document.getElementById('recording-pointer');const keep=pos?`translate(${pos.x}px,${pos.y}px)`:old?old.style.transform:'translate(760px,430px)';old?.remove();
  const e=document.createElement('div');e.id='recording-pointer';e.setAttribute('aria-hidden','true');
  e.style.cssText='position:fixed;left:0;top:0;width:20px;height:27px;pointer-events:none;z-index:2147483647;will-change:transform;transform:'+keep;
  e.innerHTML='<svg xmlns="http://www.w3.org/2000/svg" width="20" height="27" viewBox="0 0 25 34"><path d="M1 1 L1 25 L7 20 L12 31 L17 29 L12 18 L22 18 Z" fill="white" stroke="#111" stroke-width="1.7" stroke-linejoin="round"/></svg>';
  document.documentElement.append(e);window.__tutorialClicks??=[];window.__glide=null;
  window.__ptrStat??={held:0,heldAfterFinish:0,applied:0};
  window.__tutorialMove=ev=>{if(window.__glide){window.__ptrStat.held++;if(window.__glide==='hold')window.__ptrStat.heldAfterFinish++;return;}window.__ptrStat.applied++;e.style.transform=`translate(${ev.clientX}px,${ev.clientY}px)`;};
  window.__tutorialDown=ev=>{const r=e.getBoundingClientRect();window.__tutorialClicks.push({x:ev.clientX,y:ev.clientY,px:r.x,py:r.y,trusted:ev.isTrusted,gliding:!!window.__glide,time:performance.now(),url:location.pathname});};
  document.addEventListener('mousemove',window.__tutorialMove,true);document.addEventListener('mousedown',window.__tutorialDown,true);
  window.__startGlide=(ax,ay,x,y,ms)=>{if(window.__glide?.cancel)window.__glide.cancel();const kf=[];for(let i=0;i<=20;i++){const t=i/20,u=t*t*(3-2*t);kf.push({transform:`translate(${ax+(x-ax)*u}px,${ay+(y-ay)*u}px)`,offset:t});}
   const a=e.animate(kf,{duration:ms,easing:'linear',fill:'forwards'});window.__glide=a;
   a.onfinish=()=>{e.style.transform=`translate(${x}px,${y}px)`;a.cancel();if(window.__glide===a)window.__glide='hold';};};
}

// 대상 하나를 화면 좌표로(페이지 안에서 실행). 여러 개면 오류 — 고정 좌표로 누르지 않는다.
export function findInPage(t){
  const vis=e=>{const b=e.getBoundingClientRect();return b.width>0&&b.height>0&&e.checkVisibility({checkVisibilityCSS:true});};
  let es;
  if(t.tab)es=[...document.querySelectorAll(`.rail nav button[data-tab="${t.tab}"]`)];
  else if(t.css)es=[...document.querySelectorAll(t.css)];
  else if(t.text!==undefined){const root=t.within?[...document.querySelectorAll(t.within)].filter(vis):[document.body];
   es=root.flatMap(r=>[...r.querySelectorAll(t.tag||'*')]).filter(e=>e.textContent.trim().replace(/\s+/g,' ')===t.text);
   es=es.filter(e=>!es.some(o=>o!==e&&e.contains(o)));}
  else return{error:'bad target '+JSON.stringify(t)};
  // contains: 글자를 포함하는 요소만, cell0: 표 행의 첫 칸 글자가 정확히 같은 행만, cell: 그 행의 몇 번째 칸
  if(t.contains)es=es.filter(e=>e.textContent.includes(t.contains));
  if(t.cell0)es=es.filter(e=>e.cells&&e.cells[0]?.textContent.trim()===t.cell0);
  es=es.filter(vis);
  if(t.cell!==undefined)es=es.map(e=>e.cells[t.cell]).filter(Boolean);
  if(t.nth!==undefined)es=es.slice(t.nth,t.nth+1);
  if(es.length!==1)return{error:'Target '+JSON.stringify(t)+' matched '+es.length};
  const b=es[0].getBoundingClientRect();
  // 가리키는 자리: 글자를 가리지 않게 margin(문단 왼쪽 여백) · pad(표 칸 · 코드 상자 안쪽 여백) · below(글자 바로 아래), 기본은 가운데
  let x=b.x+b.width/2,y=b.y+b.height/2;
  if(t.anchor==='left')x=b.x+Math.min(b.width/2,28);
  else if(t.anchor==='right')x=b.x+b.width-Math.min(b.width/2,20);
  else if(t.anchor==='margin'){x=Math.max(4,b.x-24);y=b.y+Math.min(b.height/2,14);}
  else if(t.anchor==='pad'){x=b.x+6;y=b.y+Math.min(b.height/2,22);}
  else if(t.anchor==='below'){x=b.x+Math.min(b.width/2,30);y=b.bottom+4;}
  else if(t.anchor==='after'){const g=document.createRange();g.selectNodeContents(es[0]);const tb=g.getBoundingClientRect();x=(tb.width?tb.right:b.right)+12;y=b.y+b.height/2;}
  // 대상을 담은 스크롤 영역(포털은 왼쪽 메뉴 .rail과 본문 main#content가 따로 굴러간다). 고정 위치(위 막대)면 굴리지 않는다.
  let fixed=false,a=es[0].parentElement,sc=null;
  // 고정: position fixed면 늘 보인다. sticky는 굴러가는 칸 안에서는 그 칸과 함께 화면 밖으로 나갈 수 있으므로(처리 건 목록 칸, 2026-11-12 06 o1104)
  // 스크롤 영역이 없을 때만 고정으로 본다 — 아래 스크롤 영역을 찾은 뒤 판단한다.
  let sticky=false;for(let n=es[0];n&&n!==document.documentElement;n=n.parentElement){const ps=getComputedStyle(n).position;if(ps==='fixed')fixed=true;else if(ps==='sticky')sticky=true;}
  // 스크롤 영역이 겹쳐 있으면(처리 건 목록 #instList가 본문 main#content 안에서 또 굴러간다) 안쪽 칸의 크기만 보고 「보인다」고 하면 안 된다 —
  // 안쪽 칸이 본문 아래로 뻗어 있으면 화면 밖(y 1025, 창 높이 720)을 가리킨 적이 있다(2026-11-12 06 o1104). 안쪽부터 보아 가리킬 지점이 그 칸 밖이면
  // 그 칸을 굴리고, 모든 칸 안이면 가장 안쪽 칸을 쓴다. 「보이는 범위」(vtop · vbottom)는 그 칸을 바깥 칸들과 창으로 잘라 낸 범위다.
  const scs=[];for(;a&&a!==document.body&&a!==document.documentElement;a=a.parentElement){const cs=getComputedStyle(a);if(/(auto|scroll)/.test(cs.overflowY)&&a.scrollHeight>a.clientHeight+2){const r=a.getBoundingClientRect();scs.push({top:r.top,bottom:r.bottom,left:r.left,right:r.right});}}
  if(scs.length){let k=scs.findIndex(s=>y<s.top||y>s.bottom);if(k<0)k=0;sc={...scs[k],vtop:Math.max(0,...scs.slice(k).map(s=>s.top)),vbottom:Math.min(innerHeight,...scs.slice(k).map(s=>s.bottom))};}
  // 문서 전체가 굴러가지 않는 화면(포털)에서 스크롤 영역 밖 요소(위 막대)는 늘 보인다.
  if(sticky&&!sc)fixed=true;
  if(!sc&&document.scrollingElement.scrollHeight<=innerHeight+2)fixed=true;
  // hit: 누를 지점의 맨 위 요소가 이 대상이거나 그 안쪽인가(다른 요소에 가려졌으면 false).
  const top=document.elementFromPoint(x+(t.dx||0),y+(t.dy||0));const hit=!!top&&(top===es[0]||es[0].contains(top));
  return{x,y,top:b.top,bottom:b.bottom,left:b.left,right:b.right,h:innerHeight,w:innerWidth,tag:es[0].tagName,fixed,sc,hit};
}

export async function portal(ctx){
 const raw=ctx.p,sleep=ctx.sleep,q1=fn=>ctx.serial(fn);
 // ctx.virtualPointer(take.mjs): 페이지에 화살표를 움직이지 않는다. 경로만 기록해 합성 때 그리고, 실제 입력은 도착 시각에 목표로 한 번 보낸다 — 입력 지연이 화살표를 끌지 못한다.
 const virtual=ctx.virtualPointer||null;
 const gs={lastMoveEnd:0};let lastPos=virtual;
 const gate=async()=>{const until=Math.max(ctx.commitAt||0,gs.lastMoveEnd+150);const w=until-Date.now();if(w>0)await sleep(w);ctx.committed??=Date.now();};
 const pointerPos=()=>raw.evaluate(()=>{const r=document.getElementById('recording-pointer')?.getBoundingClientRect();if(!r)throw Error('Recording pointer missing');return{x:r.x,y:r.y};});
 // 이동: RPC 하나마다 직렬 큐를 잠깐 쓰고 놓는다. 실제 입력 8단계, 마지막 단계는 정확히 목표 좌표. 애니메이션 끝까지 hold 뒤 해제.
 async function moveCore(x,y){
  if(virtual){const a=lastPos,dist=Math.hypot(x-a.x,y-a.y);if(dist<1){gs.lastMoveEnd=Date.now();return;}
   const ms=Math.round(Math.max(260,Math.min(620,200+dist*0.4))),t0=Date.now();ctx.recordMotion({start:t0,end:t0+ms,x,y,from:a,planned_ms:ms,glide:t0});
   if(!ctx.rehearsal)await sleep(ms);await q1(()=>raw.mouse.move(x,y,{steps:1}));gs.lastMoveEnd=Date.now();lastPos=ctx.virtualPointer={x,y};return;}
  const a=await q1(pointerPos);const dist=Math.hypot(x-a.x,y-a.y);if(dist<1){gs.lastMoveEnd=Date.now();lastPos={x,y};return;}
  const ms=Math.round(Math.max(260,Math.min(620,200+dist*0.4)));const t0=Date.now();
  const g0=Date.now();await q1(()=>raw.evaluate(({ax,ay,x,y,ms})=>window.__startGlide(ax,ay,x,y,ms),{ax:a.x,ay:a.y,x,y,ms}));const glideAt=Math.round((g0+Date.now())/2);
  for(let i=1;i<=8;i++){const t=i/8,u=t*t*(3-2*t);const w=t0+ms*t-Date.now();if(w>0)await sleep(w);await q1(()=>raw.mouse.move(a.x+(x-a.x)*u,a.y+(y-a.y)*u,{steps:1}));}
  for(let n=0;n<60&&await q1(()=>raw.evaluate(()=>window.__glide&&window.__glide!=='hold'));n++)await sleep(20);
  await q1(()=>raw.evaluate(()=>{window.__glide=null;}));
  ctx.recordMotion?.({start:t0,end:Date.now(),x,y,from:a,planned_ms:ms,glide:glideAt});gs.lastMoveEnd=Date.now();lastPos={x,y};
 }
 const find=t=>q1(()=>raw.evaluate(findInPage,t)).then(r=>{if(r.error)throw Error(r.error);return r;});
 // 화면 밖 대상은 휠로 들인다(스크롤도 사람이 하는 조작이므로 화살표가 그 영역 위에 있을 때 몇 번에 나눠 굴린다).
 async function inView(t){
  // 가리킬 지점이 그 스크롤 영역 안(위 20 · 아래 20px 여백, 창 전체가 영역이면 위 60 · 아래 40px)에 있으면 그대로 쓴다. 고정된 위 막대는 굴려도 자리가 같다.
  // 밖이면 화살표를 먼저 그 영역 위로 옮긴 뒤 굴린다(휠은 화살표 아래 영역을 굴린다 — 메뉴 칸 위에서 굴려야 메뉴가 움직인다).
  for(let i=0;i<12;i++){const r=await find(t);const y=r.y+(t.dy||0);ctx.lastView={i,y:Math.round(y),top:Math.round(r.top),sc:r.sc,pos:lastPos};if(r.fixed)return r;
   const lo=r.sc?r.sc.vtop+20:60,hi=r.sc?r.sc.vbottom-20:r.h-40;if(y>=lo&&y<=hi&&r.top>=-r.h)return r;
   await over(r);const dy=y<lo?y-lo-140:y-hi+140;await wheel(virtual?dy:Math.max(-420,Math.min(420,dy)),r.sc);}
  throw Error('Cannot bring into view: '+JSON.stringify(t)+' '+JSON.stringify(ctx.lastView||null));
 }
 async function over(r){if(!r.sc)return;const p=lastPos||await q1(pointerPos);const s=r.sc;
  const vt=s.vtop??s.top,vb=s.vbottom??s.bottom;   // 칸이 창 밖으로 뻗어 있어도 화살표는 보이는 범위 안에 둔다
  if(p.x>=s.left+10&&p.x<=s.right-10&&p.y>=vt+10&&p.y<=vb-10)return;
  const cl=(v,a,b)=>Math.max(a,Math.min(b,v));await moveCore(cl(r.x,s.left+40,s.right-40),cl(p.y,vt+80,vb-80));}
 async function settled(t){let q=await inView(t);for(let k=0;k<10;k++){await sleep(150);const q2=await find(t);if(Math.hypot(q2.x-q.x,q2.y-q.y)<=1)return q2;q=q2;}throw Error('Target layout did not settle: '+JSON.stringify(t));}
 // 휠: 헤드리스에서는 휠 한 번이 부드럽게 굴러가지 않고 그 거리만큼 바로 뛴다(120px씩 나누니 520px가 프레임 6장 · 공백 191ms, 2026-10-23 test-click-1).
 // 그래서 약 30px씩 프레임 간격(30ms)에 맞춰 굴린다. 처음과 끝은 작게(가속 · 감속). 화살표는 움직이지 않는다.
 // virtual(ego): 휠 호출 하나가 긴 화면에서 수백 ms라 나눠 보내면 찔끔찔끔 움직인다(2026-11-03 06 리허설 한 번 이동 50초). 화살표 아래 스크롤 영역을 페이지 안 애니메이션으로 한 번에 굴린다.
 async function wheel(dy,sc){
  if(virtual){const ms=Math.round(Math.max(350,Math.min(1400,220+Math.abs(dy)*0.55)));
   const ok=await q1(()=>raw.evaluate(({x,y,dy,ms,sc})=>{let a=document.elementFromPoint(x,y);
    // sc: 대상을 담은 스크롤 영역. 화살표 아래 입력칸 · 원문 칸이 먼저 굴러가 본문이 안 움직이는 일을 막는다.
    for(;a&&a!==document.documentElement;a=a.parentElement){const s=getComputedStyle(a),b=a.getBoundingClientRect();if(/(auto|scroll)/.test(s.overflowY)&&a.scrollHeight>a.clientHeight+1&&(!sc||(Math.abs(b.top-sc.top)<2&&Math.abs(b.left-sc.left)<2))&&(sc||(dy>0?a.scrollTop+a.clientHeight<a.scrollHeight-1:a.scrollTop>0)))break;}
    if(!a||a===document.documentElement)return false;
    // 실제 휠처럼 화살표 아래 요소에 휠 이벤트를 알린다(굴리기는 아래 애니메이션이 한다). 포털 처리 과정은 진행 중이면 새 줄로 화면을 저절로 끌어내리고
    // 휠이 오면 6초 멈춘다(it/portal/www/trace.js followNewest). 알리지 않으면 재관측 중 위 단계로 굴리는 조작과 맞서 「Cannot bring into view」(2026-11-03 06 C045).
    const tell=()=>document.elementFromPoint(x,y)?.dispatchEvent(new WheelEvent('wheel',{bubbles:true,cancelable:true,deltaY:dy,clientX:x,clientY:y}));tell();
    const from=a.scrollTop,t0=performance.now(),step=now=>{const u=Math.min(1,(now-t0)/ms);a.scrollTop=from+dy*(u*u*(3-2*u));if(u<1)requestAnimationFrame(step);else tell();};requestAnimationFrame(step);return true;},{x:lastPos.x,y:lastPos.y,dy,ms,sc:sc||null}));
   if(!ok)throw Error(`굴릴 영역 없음: 화살표 (${Math.round(lastPos.x)},${Math.round(lastPos.y)}) 아래, ${dy}px`);
   await sleep(ms+150);return;}
  const n=Math.max(4,Math.round(Math.abs(dy)/30));let done=0;const t0=Date.now();
  for(let i=1;i<=n;i++){const u=(1-Math.cos(Math.PI*i/n))/2;const step=Math.round(dy*u)-done;done+=step;if(step)await q1(()=>raw.mouse.wheel(0,step));const w=t0+i*30-Date.now();if(w>0)await sleep(w);}
  await sleep(250);}
 const c={raw,gate,sleep,serial:ctx.serial};
 c.move=async(x,y)=>{await moveCore(x,y);};
 c.point=async t=>{const q=await settled(t);await moveCore(q.x+(t.dx||0),q.y+(t.dy||0));return q;};
 c.click=async t=>{
  for(let i=0;i<4;i++){
   const q=await settled(t);const x=q.x+(t.dx||0),y=q.y+(t.dy||0);await moveCore(x,y);await gate();
   const now=await find(t);
   // virtual: 화살표는 나중에 그리므로, 이동 중 대상이 밀렸으면 기록된 도착점을 고쳐 한 번에 간 것으로 그린다(휘청임이 생기지 않는다).
   if(virtual&&Math.hypot(now.x-q.x,now.y-q.y)>2){const nx=now.x+(t.dx||0),ny=now.y+(t.dy||0);ctx.retarget?.({target:t,by:[Math.round(now.x-q.x),Math.round(now.y-q.y)],hit:now.hit});
    // 많이 밀려 화면 밖으로 나갔거나 가려졌으면 처음부터 다시 찾아 간다(화면이 다시 그려진 경우).
    if(!now.hit)continue;
    ctx.amendMotion(nx,ny);await q1(()=>raw.mouse.move(nx,ny,{steps:1}));lastPos=ctx.virtualPointer={x:nx,y:ny};await q1(()=>raw.mouse.click(nx,ny));ctx.recordClick?.({x:nx,y:ny,target:t});await sleep(150);return now;}
   if(Math.hypot(now.x-q.x,now.y-q.y)>2){ctx.retarget?.(t);continue;}
   if(virtual&&!now.hit)throw Error('Target covered at click point: '+JSON.stringify(t));
   await q1(()=>raw.mouse.click(x,y));ctx.recordClick?.({x,y,target:t});await sleep(150);return now;
  }
  throw Error('Target kept moving: '+JSON.stringify(t));
 };
 // 스크롤: 화살표를 그 영역(대상 또는 지정 지점) 위에 둔 뒤 gate에서 굴린다.
 c.scroll=async(dy,over)=>{if(over)await c.point(over);await gate();await wheel(dy);};
 c.scrollTo=async t=>{await gate();await inView(t);};
 // 그 대상(제목 등)이 화면 위 top px 자리에 오도록 굴린다. 시점은 부르는 쪽이 정한다(gate 없음).
 c.scrollTop=async(t,top=96)=>{const r=await find(t);const dy=Math.round(r.top-top);if(Math.abs(dy)>4){await over(r);await wheel(dy,r.sc);}};
 // 입력: 입력칸이 포커스인지 확인하고, 화살표를 칸 아래 여백으로 비킨 뒤 한 글자씩 넣는다(한글은 완성형 글자 단위, IME 조합 시연 아님).
 c.aside=async()=>{const q=await q1(()=>raw.evaluate(()=>{const a=document.activeElement;if(!a?.matches('input,textarea,select,[contenteditable=true]'))return null;const r=a.getBoundingClientRect();return{x:Math.min(innerWidth-30,r.x+24),y:Math.min(innerHeight-30,r.bottom+22)};}));if(!q)throw Error('No focused input for aside');await moveCore(q.x,q.y);};
 c.type=async text=>{await c.aside();await gate();let i=0;for(const ch of text){await q1(()=>raw.keyboard.insertText(ch));await sleep([105,125,95,135,110][i++%5]);}};
 c.key=async k=>{await gate();await q1(()=>raw.keyboard.press(k));await sleep(200);};
 // 고르기 칸: 헤드리스 화면 녹화에는 운영체제 목록 창이 찍히지 않으므로, 칸을 누른 뒤 값을 고르고 change를 보낸다(고른 결과는 칸에 보인다).
 // virtual(화면 있는 ego)은 실제로 누르면 운영체제 목록 창이 열려 녹화에 안 찍히고 입력을 붙잡으므로, 칸을 가리킨 뒤 값을 고른다.
 c.select=async(t,label)=>{if(virtual)await c.point(t);else await c.click(t);await gate();
  const ok=await q1(()=>raw.evaluate(({t,label})=>{const es=[...document.querySelectorAll(t.css||'select')].filter(e=>e.checkVisibility());const s=es[t.nth||0];if(!s)return false;const o=[...s.options].find(o=>o.textContent.trim()===label||o.value===label);if(!o)return false;s.value=o.value;s.dispatchEvent(new Event('change',{bubbles:true}));s.blur();return true;},{t,label}));
  if(!ok)throw Error('Select option missing: '+label);await sleep(200);};
 c.waitFor=(fn,arg,timeout)=>ctx.waitFor(fn,arg,timeout);
 c.waitText=(text,timeout=20000)=>ctx.waitFor(s=>document.body.innerText.includes(s),text,timeout);
 c.pos=()=>lastPos;
 // 대상이 화면에 하나로 나타날 때까지 기다린다(서버 응답 뒤에 그려지는 결과). 시간 안에 안 나오면 오류.
 c.appear=async(t,timeout=30000)=>{const a=Date.now();for(;;){try{return await find(t);}catch(e){if(Date.now()-a>timeout)throw Error('Did not appear: '+JSON.stringify(t));await sleep(200);}}};
 return c;
}
