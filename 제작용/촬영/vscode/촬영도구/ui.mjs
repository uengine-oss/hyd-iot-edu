// VS Code 웹(serve-web) 조작 층. 포인터·이동·gate는 Notion v10(../../notion/촬영도구/ui.mjs)에서 검증된 코드를 그대로 옮겼다.
// - 표시 포인터: 페이지에 그린 흰 화살표를 컴포지터 애니메이션으로 움직이고, 실제 입력은 같은 경로 8단계(순간이동 없음).
// - gate(): 큐가 정한 실행 시점(행동 문장 끝 약 250ms 전)까지 대기. 클릭·키·입력은 모두 gate를 거친다.
// - Codex 채팅은 웹뷰 iframe이라 DOM으로 찾지 않는다. 바깥 문서의 웹뷰 영역 좌표로 누르고 키보드로 입력한다.
// - 좌표는 CSS 픽셀(뷰포트 2304x1296 dsf1, ego 150% → CSS 1536x864, 캡처 2304x1296 → 1920x1080 프레임).

export function installPointerInPage(pos){
  document.removeEventListener('mousemove',window.__tutorialMove,true);document.removeEventListener('mousedown',window.__tutorialDown,true);
  const old=document.getElementById('recording-pointer');const keep=old?old.style.transform:pos?`translate(${pos.x}px,${pos.y}px)`:'translate(760px,430px)';old?.remove();
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

export async function vscode(ctx){
 const raw=ctx.p,sleep=ctx.sleep,q1=fn=>ctx.serial(fn);
 const gs={lastMoveEnd:0};
 const gate=async()=>{const until=Math.max(ctx.commitAt||0,gs.lastMoveEnd+150);const w=until-Date.now();if(w>0)await sleep(w);ctx.committed??=Date.now();};
 const pointerPos=()=>raw.evaluate(()=>{const r=document.getElementById('recording-pointer')?.getBoundingClientRect();if(!r)throw Error('Recording pointer missing');return{x:r.x,y:r.y};});
 const c={gate,serial:ctx.serial};
 c.installPointer=async at=>q1(()=>raw.evaluate(installPointerInPage,at||null));
 c.move=async(x,y)=>{
  const a=await q1(pointerPos);const dist=Math.hypot(x-a.x,y-a.y);if(dist<1){gs.lastMoveEnd=Date.now();return;}
  const ms=Math.round(Math.max(260,Math.min(620,200+dist*0.4)));const t0=Date.now();
  await q1(()=>raw.evaluate(({ax,ay,x,y,ms})=>window.__startGlide(ax,ay,x,y,ms),{ax:a.x,ay:a.y,x,y,ms}));
  for(let i=1;i<=8;i++){const t=i/8,u=t*t*(3-2*t);const w=t0+ms*t-Date.now();if(w>0)await sleep(w);await q1(()=>raw.mouse.move(a.x+(x-a.x)*u,a.y+(y-a.y)*u,{steps:1}));}
  for(let n=0;n<60&&await q1(()=>raw.evaluate(()=>window.__glide&&window.__glide!=='hold'));n++)await sleep(20);
  await q1(()=>raw.evaluate(()=>{window.__glide=null;}));
  ctx.recordMotion?.({start:t0,end:Date.now(),x,y,from:a,planned_ms:ms});gs.lastMoveEnd=Date.now();
 };
 // 바깥 문서의 대상 중심 좌표. 보이는 대상이 정확히 하나여야 한다(여러 개면 멈춘다).
 c.point=async(selector,text)=>{
  const r=await q1(()=>raw.evaluate(({selector,text})=>{
   const vis=e=>{const b=e.getBoundingClientRect();return b.width>0&&b.height>0&&e.checkVisibility({checkVisibilityCSS:true});};
   let es=[...document.querySelectorAll(selector)].filter(vis);
   if(text!=null)es=es.filter(e=>(e.getAttribute('aria-label')||e.textContent||'').trim()===text);
   if(es.length!==1)return{error:`${selector} ${text??''} matched ${es.length}`};
   const b=es[0].getBoundingClientRect();return{x:b.x+b.width/2,y:b.y+b.height/2};
  },{selector,text}));
  if(r.error)throw Error(r.error);return r;
 };
 c.hoverSel=async(selector,text)=>{const q=await c.point(selector,text);await c.move(q.x,q.y);return q;};
 c.clickSel=async(selector,text)=>{const q=await c.hoverSel(selector,text);await gate();await q1(()=>raw.mouse.click(q.x,q.y));await sleep(150);};
 c.clickAt=async(x,y)=>{await c.move(x,y);await gate();await q1(()=>raw.mouse.click(x,y));await sleep(150);};
 // 탐색기의 파일·폴더(이름이 정확히 같은 줄). 접힌 폴더 안의 파일은 먼저 폴더를 연다.
 c.explorer=async name=>c.clickSel('.explorer-folders-view .monaco-list-row .label-name',name);
 // 열린 편집기 탭
 c.tab=async name=>c.clickSel('.tabs-container .tab .label-name',name);
 // Codex 웹뷰 영역(보조 사이드바) 안의 상대 위치. fx·fy는 0~1 비율, 아래쪽 입력칸은 fy≈0.93.
 c.codexArea=async()=>q1(()=>raw.evaluate(()=>{const b=document.querySelector('.part.auxiliarybar')?.getBoundingClientRect();if(!b||!b.width)throw Error('Codex 패널이 열려 있지 않음');return{x:b.x,y:b.y,w:b.width,h:b.height};}));
 c.codexPoint=async(fx,fy)=>{const a=await c.codexArea();return{x:a.x+a.w*fx,y:a.y+a.h*fy};};
 c.codexInput=async()=>{const q=await c.codexPoint(0.45,0.93);await c.clickAt(q.x,q.y);};
 // 입력: 완성형 글자 단위(IME 조합 시연 아님). 입력 중 포인터는 입력칸 위 여백으로 비킨다.
 c.type=async(text,aside)=>{if(aside)await c.move(aside.x,aside.y);await gate();let i=0;for(const ch of text){await q1(()=>raw.keyboard.insertText(ch));await sleep([70,85,60,95,75][i++%5]);}};
 c.key=async k=>{await gate();await q1(()=>raw.keyboard.press(k));await sleep(200);};
 // 터미널: 열려 있지 않으면 Ctrl+` 로 연다. 명령은 type 뒤 Enter.
 c.terminalOpen=async()=>{const open=await q1(()=>raw.evaluate(()=>!!document.querySelector('.terminal-wrapper')?.checkVisibility()));if(!open)await c.key('Control+Backquote');await sleep(1500);};
 c.waitFor=ctx.waitFor;
 return c;
}
