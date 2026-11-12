// 1회차 실습 06 「전체 과정 관찰」을 끊지 않고 한 번에 찍는 구간 모듈(take.mjs가 부른다). 큐 · 조작은 ../../전체과정관찰_큐.json.
// 조작 형식: [종류, 대상, …, 시점]. 시점은 0~1 또는 대사 속 구절(그 구절이 시작될 때). 대상은 포털 소개 이름(tab:knowledge) 또는 {css,anchor,…}.
// 되돌릴 수 없는 조작(적재 · 주입 · 승인)이 있어 리허설은 스냅샷.sh로 시작 상태를 되돌린 뒤 본촬영을 한다.
import fs from 'node:fs/promises';
import os from 'node:os';
import {fileURLToPath} from 'node:url';
import {portal} from '../ui.mjs';
import {target as tourTarget} from './portal_tour.mjs';
const HERE=fileURLToPath(new URL('.',import.meta.url));
export const CUES=HERE+'../../전체과정관찰_큐.json';
const T=t=>typeof t==='string'?tourTarget(t):t;

// 원문 글자 위치. 원문 칸(pre)은 본문(main#content) 안에서 또 따로 굴러간다.
function phraseInPage(phrase){
 const pre=document.querySelector('#manualSourceText pre');if(!pre)return{error:'원문이 펼쳐지지 않음'};
 const n=pre.firstChild,i=n?.textContent.indexOf(phrase)??-1;if(i<0)return{error:'원문에 없는 구절: '+phrase};
 const g=document.createRange();g.setStart(n,i);g.setEnd(n,i+phrase.length);const b=g.getBoundingClientRect();
 const r=pre.getBoundingClientRect(),m=document.querySelector('main#content').getBoundingClientRect();
 return{x:Math.min(innerWidth-30,b.right+12),y:b.top+b.height/2,pre:{top:r.top,bottom:r.bottom,left:r.left,right:r.right,h:r.height},main:{top:m.top,bottom:m.bottom,left:m.left}};
}
// 처리 건 진행 상황에서 단계를 이름으로 찾는다(단계 id는 처리 건마다 새로 생긴다).
function stepInPage(name){
 const s=[...document.querySelectorAll('#instDetail section.tr-step')].filter(e=>e.querySelector('[data-tr-head]')?.textContent.includes(name));
 if(s.length<1)return{error:'단계 없음: '+name+' / 있는 단계: '+[...document.querySelectorAll('#instDetail section.tr-step [data-tr-head]')].map(e=>e.textContent.trim().slice(0,30)).join(' | ')};
 const e=s.at(-1),h=e.querySelector('[data-tr-head]');return{key:e.dataset.key,expanded:h.getAttribute('aria-expanded')==='true'};
}

export async function op(ctx,c,o){
 const [kind,a,b]=o;
 switch(kind){
  case 'point':return c.point(T(a));
  case 'click':return c.click(T(a));
  case 'scroll':return c.scrollTop(T(a),T(a).top??96);
  case 'scrollby':{if(a)await c.point(T(a));return c.scroll(b);}
  // details: 닫혀 있을 때만 눌러 펼친다. 이미 열려 있으면 가리키기만 한다.
  case 'open':{const t=T(a);const open=await ctx.p.evaluate(s=>document.querySelector(s)?.parentElement?.open,t.css);return open?c.point(t):c.click(t);}
  case 'select':return c.select(T(a),b);
  case 'selectwith':{const t=T(a);const v=await ctx.p.evaluate(({css,words})=>{const m=[...document.querySelector(css).options].filter(x=>words.every(w=>x.textContent.includes(w)));return m.length===1?m[0].value:null;},{css:t.css,words:b});if(v===null)throw Error('고를 항목이 하나로 정해지지 않음: '+b.join(' '));return c.select(t,v);}
  case 'download':{const w=ctx.p.waitForEvent('download',{timeout:20000});w.catch(()=>{});await c.click(T(a));await (await w).saveAs(ctx.out+'/'+b);return;}
  // 클라우드 Playwright가 직접 띄운 브라우저에서는 한글이 든 경로의 파일이 파일 칸에 들어가지 않고 오류도 없었다(2026-11-12 길뚫기 — CDP로 붙은
  // 녹화 브라우저에서는 들어갔다). 녹화 폴더(작업/촬영/포털)가 한글이라 영문 임시 폴더로 복사해 넣고, 파일 칸에 실제로 들어갔는지 확인한다.
  case 'file':{const dir=os.tmpdir()+'/hyd-upload';await fs.mkdir(dir,{recursive:true});const src=dir+'/'+b;await fs.copyFile(ctx.out+'/'+b,src);
    const w=ctx.p.waitForFileChooser({timeout:20000});w.catch(()=>{});await c.click(T(a));await (await w).setFiles(src);await c.sleep(400);
    if(!(await ctx.serial(()=>ctx.p.evaluate(n=>[...document.querySelectorAll('input[type=file]')].some(i=>[...i.files].some(f=>f.name===n)),b))))throw Error('파일 칸에 들어가지 않음: '+b);return;}
  case 'type':return c.type(a);
  // 요소 안 글의 한 구절 끝을 짚는다(값 · 조건 글자를 정확히 — 2026-11-12 06 최종 판정 「칠십 밑」을 말할 때 줄 앞을 짚음). a: 대상, b: 구절.
  // 먼저 그 요소를 화면에 들이고(point와 같은 굴림), 구절의 글자 상자 오른쪽 끝 바로 뒤로 간다. 구절이 없거나 여러 번이면 멈춘다.
  case 'textin':{const t=T(a);await c.point({...t,anchor:'left'});
    const q=await ctx.serial(()=>ctx.p.evaluate(({t,b})=>{const vis=e=>e.checkVisibility();let es=[...document.querySelectorAll(t.css)].filter(vis);if(t.contains)es=es.filter(e=>e.textContent.includes(t.contains));if(t.nth!==undefined)es=es.slice(t.nth,t.nth+1);
      if(es.length!==1)return{error:'textin 대상 '+es.length+'개: '+t.css};const el=es[0];const w=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);const hits=[];for(let n;(n=w.nextNode());){let i=-1;while((i=n.textContent.indexOf(b,i+1))>=0)hits.push([n,i]);}
      if(hits.length!==1)return{error:'구절 '+hits.length+'번: '+b};const [n,i]=hits[0];const g=document.createRange();g.setStart(n,i);g.setEnd(n,i+b.length);const rs=[...g.getClientRects()],r=rs.at(-1);return{x:Math.min(innerWidth-30,r.right+8),y:r.top+r.height/2};},{t,b}));
    if(q.error)throw Error(q.error);return c.move(q.x,q.y);}
  // 화면이 다 그려질 때까지: 본문 굴린 자리와 높이가 1.2초 동안 그대로면 끝(최대 b초, 기본 10). 처리 건을 연 직후 포털이 목록 · 상세를 다시 그리며
  // 본문이 조작 없이 위아래로 튀었다(2026-11-12 06 o1102) — 그 동안 말을 시작하지 않으려고 둔다.
  case 'settle':{const t0=Date.now(),lim=(b??10)*1000;let last=null,since=Date.now();
    for(;;){const v=await ctx.serial(()=>ctx.p.evaluate(()=>{const m=document.querySelector('main#content');return m.scrollTop+'|'+m.scrollHeight+'|'+(document.querySelector('#instDetail')?.scrollHeight||0);}));
     if(v!==last){last=v;since=Date.now();}else if(Date.now()-since>=1200)break;
     if(Date.now()-t0>lim)break;await c.sleep(150);}
    ctx.recordWait?.({label:'settle',start:t0,end:Date.now()});return;}
  // 원문 칸이 화면에 다 들어오게 본문을 먼저 굴리고(화살표는 칸 옆 여백), 그다음 칸 안에서 그 구절까지 굴린다(화살표는 칸 위).
  case 'phrase':{for(let i=0;;i++){const q=await ctx.serial(()=>ctx.p.evaluate(phraseInPage,a));if(q.error)throw Error(q.error);
    if(i>=8)throw Error('원문 위치에 닿지 못함: '+a);
    const {pre,main}=q;
    if(pre.top<main.top+8||pre.bottom>main.bottom-8){await c.move((main.left+pre.left)/2,(main.top+main.bottom)/2);await c.scroll(Math.round(pre.top-(main.top+24)));continue;}
    if(q.y>=pre.top+14&&q.y<=pre.bottom-24)return c.move(q.x,q.y);
    await c.move(pre.right-60,(pre.top+pre.bottom)/2);await c.scroll(Math.round(q.y-(pre.top+pre.h*0.2)));}}
  case 'step':{const q=await ctx.serial(()=>ctx.p.evaluate(stepInPage,a));if(q.error)throw Error(q.error);
    const head={css:`section.tr-step[data-key="${q.key}"] [data-tr-head]`,anchor:'left'};
    if(!q.expanded)await c.click(head);
    // 펼친 직후에는 「단계 자세히」가 아직 그려지지 않았을 수 있다(06-r71 C042) — 나타날 때까지 기다린다.
    const open={css:`section.tr-step[data-key="${q.key}"] [data-td-open="${q.key}"]`,anchor:'left'};
    await c.appear(open,15000);return c.click(open);}
  // 진행 중인 처리 건은 단계가 하나씩 붙으므로, 짚을 단계가 나타날 때까지 20초 기다린다(리허설은 말이 없어 단계보다 먼저 온다).
  case 'stepmark':{const t0=Date.now();let q;for(;;){q=await ctx.serial(()=>ctx.p.evaluate(stepInPage,a));if(!q.error||Date.now()-t0>20000)break;await c.sleep(300);}if(q.error)throw Error(q.error);
    if(Date.now()-t0>500)ctx.recordWait?.({label:'stepmark '+a,start:t0,end:Date.now()});return c.point({css:`section.tr-step[data-key="${q.key}"] [data-tr-head]`,anchor:'after'});}
  case 'wait':case 'waittext':case 'waitjs':{const t0=Date.now(),limit=(kind==='wait'?b:(b??180))*1000||30000;
    if(kind==='wait')await c.appear(T(a),limit);
    else if(kind==='waittext')await c.waitText(a,limit);
    else await c.waitFor(a,undefined,limit);
    ctx.recordWait?.({label:kind+' '+JSON.stringify(a).slice(0,80),start:t0,end:Date.now()});return;}
  // 서버 결과가 늦으면 다시 누른다(학생도 같은 버튼을 다시 누른다).
  case 'clickuntil':{const t0=Date.now();for(let i=0;i<30;i++){await c.click(T(a));await c.sleep(1200);
     if(await ctx.serial(()=>ctx.p.evaluate(b)))return ctx.recordWait?.({label:'clickuntil',start:t0,end:Date.now(),tries:i+1});await c.sleep(3000);}
    throw Error('결과가 나타나지 않음: '+b);}
 }
 throw Error('unknown op '+kind);
}
// 시점: 대사 속 구절이면 그 구절 앞까지의 글자 비율. wait · waittext · waitjs의 셋째 값은 기다릴 초라 시점이 아니다 — 앞 조작이 끝나면 바로 기다린다.
// (셋째 값을 시점으로 읽어 C003이 대사 길이 × 30 = 약 504초를 멈췄다, 2026-11-03 06-t1. 리허설은 대사 길이가 0이라 드러나지 않았다.)
function fracOf(q,o){const v=o.at(-1);
 if(['wait','waittext','waitjs','settle'].includes(o[0])&&o.length<4)return null;
 if(typeof v==='number')return v;
 if(v&&typeof v==='object'&&v.at){const i=q.text.indexOf(v.at);if(i<0)throw Error(`${q.id}: 대사에 없는 구절 — ${v.at}`);return i/q.text.length;}
 return null;}
export async function seg(ctx,n){
 const cues=JSON.parse(await fs.readFile(ctx.cueFile||CUES,'utf8')).cues.filter(c=>c.segment===n);
 if(!cues.length)throw Error('구간 '+n+' 큐 없음');
 const c=await portal(ctx);
 if(n===1&&!ctx.resuming){const p=ctx.p;
  // 학생처럼 꼬리 없는 첫 주소로 연다 — 새로 고침은 주소 끝(#/instances/…)의 지난 처리 건을 다시 열어 「이 처리 건은 열 수 없습니다」를 띄웠다(06-t7 C038).
  if(!(await p.url()).startsWith('http://127.0.0.1:8088/'))await p.goto('http://127.0.0.1:8088/',{waitUntil:'domcontentloaded'});
  await p.evaluate(()=>{localStorage.removeItem('hyd.me');sessionStorage.clear();});await p.goto('about:blank');await p.goto('http://127.0.0.1:8088/',{waitUntil:'domcontentloaded'});await ctx.sleep(2000);
  await p.evaluate(()=>{document.querySelector('.rail nav button[data-tab="main"]').click();for(const e of document.querySelectorAll('.rail,main#content'))e.scrollTop=0;});
  await ctx.sleep(2500);await ctx.installPointer({x:760,y:430});}
 await ctx.begin();
 // 구간 사이 쉼(첫 큐의 gap, 영상 V-14 「구간 사이」): 앞 take는 마지막 말 뒤 약 0.4초에서 끝나므로(take.mjs) 그만큼 빼고 이 take 첫 말 앞에서 기다린다.
 // 첫 구간(영상 시작)과 실패 뒤 이어 찍기는 기다리지 않는다.
 if(n!==1&&!ctx.resuming&&!ctx.rehearsal&&cues[0].gap)await ctx.sleep(Math.max(0,cues[0].gap-400));
 for(const q of cues){
  const dur=JSON.parse(await fs.readFile(ctx.audio+'/'+q.id+'.json','utf8')).duration_ms;
  const ops=q.ops||[];const lead=300;
  for(const o of ops)fracOf(q,o);
  const fn=ops.length?async()=>{const start=Date.now()-lead;
   for(const o of ops){const due=start+Math.round(dur*(fracOf(q,o)??0))-Date.now();if(due>0)await ctx.sleep(due);
    ctx.commitAt=0;await op(ctx,c,o);}}:null;
  // 큐의 gap(앞 말과의 쉼, ms)이 있으면 그 값을 쓴다 — 대본의 ▸(잇기) · ‖(쉼)에서 정한 영상 V-14 값. 없으면 take.mjs 기본값.
  await ctx.say(q.id,fn,{pointDelay:lead,gap:q.gap});
 }
 return {pos:c.pos()};
}
