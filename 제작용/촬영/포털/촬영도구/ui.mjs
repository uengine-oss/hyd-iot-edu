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
function findInPage(t){
  const vis=e=>{const b=e.getBoundingClientRect();return b.width>0&&b.height>0&&e.checkVisibility({checkVisibilityCSS:true});};
  let es;
  if(t.tab)es=[...document.querySelectorAll(`.rail nav button[data-tab="${t.tab}"]`)];
  else if(t.css)es=[...document.querySelectorAll(t.css)];
  else if(t.text!==undefined){const root=t.within?[...document.querySelectorAll(t.within)].filter(vis):[document.body];
   es=root.flatMap(r=>[...r.querySelectorAll(t.tag||'*')]).filter(e=>e.textContent.trim().replace(/\s+/g,' ')===t.text);
   es=es.filter(e=>!es.some(o=>o!==e&&e.contains(o)));}
  else return{error:'bad target '+JSON.stringify(t)};
  es=es.filter(vis);
  if(t.nth!==undefined)es=es.slice(t.nth,t.nth+1);
  if(es.length!==1)return{error:'Target '+JSON.stringify(t)+' matched '+es.length};
  const b=es[0].getBoundingClientRect();
  const ax=t.anchor==='left'?Math.min(b.width/2,28):t.anchor==='right'?b.width-Math.min(b.width/2,20):b.width/2;
  return{x:b.x+ax,y:b.y+b.height/2,top:b.top,bottom:b.bottom,left:b.left,right:b.right,h:innerHeight,w:innerWidth,tag:es[0].tagName};
}

export async function portal(ctx){
 const raw=ctx.p,sleep=ctx.sleep,q1=fn=>ctx.serial(fn);
 const gs={lastMoveEnd:0};let lastPos=null;
 const gate=async()=>{const until=Math.max(ctx.commitAt||0,gs.lastMoveEnd+150);const w=until-Date.now();if(w>0)await sleep(w);ctx.committed??=Date.now();};
 const pointerPos=()=>raw.evaluate(()=>{const r=document.getElementById('recording-pointer')?.getBoundingClientRect();if(!r)throw Error('Recording pointer missing');return{x:r.x,y:r.y};});
 // 이동: RPC 하나마다 직렬 큐를 잠깐 쓰고 놓는다. 실제 입력 8단계, 마지막 단계는 정확히 목표 좌표. 애니메이션 끝까지 hold 뒤 해제.
 async function moveCore(x,y){
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
  // 화면 안(위 · 아래 8px 여백)에 다 보이면 그대로 쓴다 — 위 막대처럼 고정된 요소는 굴려도 자리가 같다.
  for(let i=0;i<12;i++){const r=await find(t);if(r.top>=8&&r.bottom<=r.h-8)return r;
   const dy=r.top<70?r.top-160:r.bottom-r.h+120;await wheel(Math.max(-420,Math.min(420,dy)));}
  throw Error('Cannot bring into view: '+JSON.stringify(t));
 }
 async function settled(t){let q=await inView(t);for(let k=0;k<10;k++){await sleep(150);const q2=await find(t);if(Math.hypot(q2.x-q.x,q2.y-q.y)<=1)return q2;q=q2;}throw Error('Target layout did not settle: '+JSON.stringify(t));}
 // 휠: 헤드리스에서는 휠 한 번이 부드럽게 굴러가지 않고 그 거리만큼 바로 뛴다(120px씩 나누니 520px가 프레임 6장 · 공백 191ms, 2026-10-23 test-click-1).
 // 그래서 약 30px씩 프레임 간격(30ms)에 맞춰 굴린다. 처음과 끝은 작게(가속 · 감속). 화살표는 움직이지 않는다.
 async function wheel(dy){const n=Math.max(4,Math.round(Math.abs(dy)/30));let done=0;const t0=Date.now();
  for(let i=1;i<=n;i++){const u=(1-Math.cos(Math.PI*i/n))/2;const step=Math.round(dy*u)-done;done+=step;if(step)await q1(()=>raw.mouse.wheel(0,step));const w=t0+i*30-Date.now();if(w>0)await sleep(w);}
  await sleep(250);}
 const c={raw,gate,sleep,serial:ctx.serial};
 c.move=async(x,y)=>{await moveCore(x,y);};
 c.point=async t=>{const q=await settled(t);await moveCore(q.x+(t.dx||0),q.y+(t.dy||0));return q;};
 c.click=async t=>{
  for(let i=0;i<4;i++){
   const q=await settled(t);const x=q.x+(t.dx||0),y=q.y+(t.dy||0);await moveCore(x,y);await gate();
   const now=await find(t);if(Math.hypot(now.x-q.x,now.y-q.y)>2)continue;
   await q1(()=>raw.mouse.click(x,y));await sleep(150);return now;
  }
  throw Error('Target kept moving: '+JSON.stringify(t));
 };
 // 스크롤: 화살표를 그 영역(대상 또는 지정 지점) 위에 둔 뒤 gate에서 굴린다.
 c.scroll=async(dy,over)=>{if(over)await c.point(over);await gate();await wheel(dy);};
 c.scrollTo=async t=>{await gate();await inView(t);};
 // 입력: 입력칸이 포커스인지 확인하고, 화살표를 칸 아래 여백으로 비킨 뒤 한 글자씩 넣는다(한글은 완성형 글자 단위, IME 조합 시연 아님).
 c.aside=async()=>{const q=await q1(()=>raw.evaluate(()=>{const a=document.activeElement;if(!a?.matches('input,textarea,select,[contenteditable=true]'))return null;const r=a.getBoundingClientRect();return{x:Math.min(innerWidth-30,r.x+24),y:Math.min(innerHeight-30,r.bottom+22)};}));if(!q)throw Error('No focused input for aside');await moveCore(q.x,q.y);};
 c.type=async text=>{await c.aside();await gate();let i=0;for(const ch of text){await q1(()=>raw.keyboard.insertText(ch));await sleep([105,125,95,135,110][i++%5]);}};
 c.key=async k=>{await gate();await q1(()=>raw.keyboard.press(k));await sleep(200);};
 // 고르기 칸: 헤드리스 화면 녹화에는 운영체제 목록 창이 찍히지 않으므로, 칸을 누른 뒤 값을 고르고 change를 보낸다(고른 결과는 칸에 보인다).
 c.select=async(t,label)=>{await c.click(t);await gate();
  const ok=await q1(()=>raw.evaluate(({t,label})=>{const es=[...document.querySelectorAll(t.css||'select')].filter(e=>e.checkVisibility());const s=es[t.nth||0];if(!s)return false;const o=[...s.options].find(o=>o.textContent.trim()===label);if(!o)return false;s.value=o.value;s.dispatchEvent(new Event('change',{bubbles:true}));s.blur();return true;},{t,label}));
  if(!ok)throw Error('Select option missing: '+label);await sleep(200);};
 c.waitFor=(fn,arg,timeout)=>ctx.waitFor(fn,arg,timeout);
 c.waitText=(text,timeout=20000)=>ctx.waitFor(s=>document.body.innerText.includes(s),text,timeout);
 c.pos=()=>lastPos;
 return c;
}
