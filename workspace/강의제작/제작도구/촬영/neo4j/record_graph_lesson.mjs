// Neo4j Browser 녹화 코어. 큐 파일(cues)의 op마다 정해 둔 조작을 말에 맞춰 하고, 화면 프레임 · 큐 시각 · 이동 · 클릭을 남긴다.
// 브라우저 연결만 둘로 갈린다(openPages). 아래 조작 층은 페이지 모양(cdp · mouse · keyboard · evaluate · waitForFunction)만 쓴다.
//   클라우드 Playwright(정본): 상주 브라우저(포털 browser.mjs, HYD_BROWSER_CONFIG=neo4j/촬영도구/config.json)에 CDP로 붙는다.
//     Neo4j Browser 탭과 안내 문서 탭(cfg.guide가 있으면)을 찾고, 녹화하는 탭(show)만 screencast한다. 구간 사이에도 두 탭의 상태가 남는다.
//   ego(이 PC, taskSpace가 있을 때): 옛 길. 안내 문서 탭은 다루지 않는다.
// 리듬(영상 V-14): 큐 시작 = 앞 말과 앞 조작이 모두 끝난 뒤 gap(큐의 gap, 없으면 설정 gap)만큼 쉰 때. 조작은 말 안의 비율(gate)에서 한다.
//   hold = 학생이 따라 할 시간(그 큐의 말과 조작이 끝난 뒤 화면을 그대로 두는 ms).
// 설정(globalThis.HYD_RECORDING): take(새 이름) · cues(큐 파일) · host(연결 창 주소) · segments(찍을 구간 번호들, 없으면 전부) · only(큐 id들) ·
//   continue(앞 구간 끝 화면에서 이어 찍기) · pointer({x,y} 시작 위치) · silent(음성 없이 글 길이로 시험 — 숫자면 그 배로 빠르게) · gap(기본 큐 쉼 ms) ·
//   guide(안내 문서 주소의 끝부분, 예: 안내.html).
// 출력: <work>/<take>/frames · timing.json · end-state.json · pointer-start.json · progress.json
import {focusReadableGraph} from './readable_graph.mjs';
import {installGraphObserver,graphTarget} from './graph_targets.mjs';
import fs from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const HERE=path.dirname(fileURLToPath(import.meta.url));
const TOOL=JSON.parse(await fs.readFile(HERE+'/촬영도구/config.json','utf8'));
const cfg=globalThis.HYD_RECORDING;
if(!cfg?.take||!cfg?.cues||!cfg?.host)throw Error('HYD_RECORDING에 take · cues · host가 있어야 한다(현재 브라우저와 랩 연결을 확인한 값)');
const WORK=path.resolve(HERE,'촬영도구',TOOL.work),AUDIO=path.resolve(HERE,'촬영도구',cfg.audio||TOOL.audio);
const out=WORK+'/'+cfg.take;await fs.mkdir(out+'/frames',{recursive:true});
if((await fs.readdir(out+'/frames')).length)throw Error('Existing take preserved');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const SPEECH_RATE=422/60000; // 음성 없는 시험의 말 길이(글자/ms) — 포털 take.mjs와 같은 실측값

async function openPages(){
 if(typeof taskSpace==='function'){
  const p=(await taskSpace(cfg.space)).page(cfg.page||'p1');
  return {ego:true,main:p,guide:null,view:{width:cfg.width||1920,height:cfg.height||1080,deviceScaleFactor:1},close:async()=>{}};
 }
 const {createRequire}=await import('node:module');
 const {chromium}=createRequire(import.meta.url)(process.env.PLAYWRIGHT_MODULE||'/opt/node22/lib/node_modules/playwright');
 const browser=await chromium.connectOverCDP(`http://127.0.0.1:${TOOL.cdp}`);
 const ctx=browser.contexts()[0];if(!ctx)throw Error('상주 브라우저 문맥 없음(browser.mjs 먼저)');
 await ctx.grantPermissions(['clipboard-read','clipboard-write']).catch(()=>{});
 const pages=ctx.pages();
 const main=pages.find(x=>x.url().includes('/browser/'));if(!main)throw Error('Neo4j Browser 탭 없음: '+pages.map(x=>x.url()).join(' | '));
 const guide=cfg.guide?pages.find(x=>decodeURIComponent(x.url()).endsWith(cfg.guide)):null;
 if(cfg.guide&&!guide)throw Error('안내 문서 탭 없음: '+cfg.guide);
 const attached=[];
 const attach=async pg=>{const s=await ctx.newCDPSession(pg);pg.__session=s;pg.cdp=(m,a)=>s.send(m,a);s.on('Page.screencastFrame',params=>onFrame(pg,params));attached.push(pg);return s;};
 for(const pg of [main,guide].filter(Boolean))await attach(pg);
 const v=TOOL.viewport;
 return {ego:false,main,guide,view:{width:v.width,height:v.height,deviceScaleFactor:v.deviceScaleFactor},newPage:()=>ctx.newPage(),attach,
  close:async()=>{for(const pg of attached)await pg.__session.detach().catch(()=>{});await browser.close().catch(()=>{});}};
}

let done=false,start=null,error=null,active=null,writes=Promise.resolve();const frames=[],motions=[],clicks=[];
function jpegSize(bytes){for(let k=2;k<bytes.length-9;){if(bytes[k]!==255){k++;continue;}const marker=bytes[k+1],len=bytes.readUInt16BE(k+2);if([192,193,194].includes(marker))return [bytes.readUInt16BE(k+7),bytes.readUInt16BE(k+5)];if(len<2)break;k+=2+len;}return null;}
let recordingRequestedAt=Infinity;
function onFrame(pg,params){
 pg.cdp('Page.screencastFrameAck',{sessionId:params.sessionId}).catch(x=>{error??=String(x);});
 if(done||pg!==active)return;
 const bytes=Buffer.from(params.data,'base64'),size=jpegSize(bytes);
 if(!size||size[0]!==1920||size[1]!==1080){if(start!==null)error??='Capture dimensions '+JSON.stringify(size);return;}
 const stamp=params.metadata.timestamp*1000;if(start===null&&stamp<recordingRequestedAt)return;if(start===null)start=stamp;
 const f={file:'frames/'+String(frames.length).padStart(6,'0')+'.jpg',time:stamp-start,sourceTimestamp:params.metadata.timestamp,page:pg===P.main?'main':pg===P.guide?'guide':'file'};frames.push(f);
 writes=writes.then(()=>fs.writeFile(out+'/'+f.file,bytes));
}

const P=await openPages();let p=P.main;active=p;
const metrics=pg=>pg.cdp('Emulation.setDeviceMetricsOverride',{...P.view,mobile:false});
await metrics(p);await p.waitForFunction(w=>innerWidth===w,P.ego?P.view.width:P.view.width,{timeout:10000}).catch(async()=>{await p.waitForFunction(()=>innerWidth>=1280,undefined,{timeout:10000});});
if(P.guide)await metrics(P.guide);
await p.evaluate(installGraphObserver);
if(!cfg.continue)await p.evaluate(()=>{for(const e of document.querySelectorAll('*'))if(e.scrollTop)e.scrollTop=0;window.scrollTo(0,0);});
// 연결 창의 글과 단추(제목 · 주소 칸 · Connect · Cancel)가 모두 화면 안에 있어야 한다. 5.26 연결 창은 아래 여백 상자가 CSS 864보다 조금 길지만 그 안의 글은 다 보인다.
const bounds=await p.evaluate(()=>{const d=document.querySelector('[role="dialog"]');if(!d)return null;const parts=[...d.querySelectorAll('h1,h2,input,button')].filter(e=>e.getBoundingClientRect().height>0).map(e=>e.getBoundingClientRect());return {top:Math.min(...parts.map(r=>r.top)),bottom:Math.max(...parts.map(r=>r.bottom)),height:innerHeight,n:parts.length};});
if(!cfg.continue&&(!bounds||bounds.top<0||bounds.bottom>bounds.height))throw Error('Connection dialog clipped: '+JSON.stringify(bounds));
let targets=[],pos=cfg.pointer||{x:500,y:240};
const overlay=TOOL.pointer==='overlay'&&!P.ego;
const point=spec=>p.evaluate(spec=>{
 let all=Array.from(document.querySelectorAll(spec.css||'button'));
 if(spec.text)all=all.filter(e=>e.textContent.trim()===spec.text);
 if(spec.contains)all=all.filter(e=>e.textContent.includes(spec.contains));
 const e=all.find(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&r.y>=0&&r.y<innerHeight;});
 if(!e)throw Error('Visible target missing: '+JSON.stringify(spec));
 const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};
},spec);
const installPointer=(pg,q)=>pg.evaluate(({q,hidden})=>{
 document.getElementById('recording-pointer')?.remove();
 const e=document.createElement('div');e.id='recording-pointer';e.setAttribute('aria-hidden','true');
 e.style.cssText=`position:fixed;left:0;top:0;width:20px;height:27px;pointer-events:none;z-index:2147483647;will-change:transform;transform:translate(${q.x}px,${q.y}px);opacity:${hidden?0:1}`;
 e.innerHTML='<svg xmlns="http://www.w3.org/2000/svg" width="20" height="27" viewBox="0 0 25 34"><path d="M1 1 L1 25 L7 20 L12 31 L17 29 L12 18 L22 18 Z" fill="white" stroke="#111" stroke-width="1.7" stroke-linejoin="round"/></svg>';
 document.documentElement.append(e);
 if(!window.__recordClickHook){window.__recordClickHook=true;window.__recordClicks=[];
  document.addEventListener('mouseup',()=>{document.querySelector('#recording-pointer path')?.setAttribute('fill','white');},{capture:true});
  document.addEventListener('mousedown',e=>{if(!e.isTrusted)return;document.querySelector('#recording-pointer path')?.setAttribute('fill','#d6d6d6');const r=document.getElementById('recording-pointer').getBoundingClientRect();window.__recordClicks.push({x:e.clientX,y:e.clientY,px:r.x,py:r.y,gliding:window.__recordGlide?.playState==='running'});},{capture:true});}
},{q,hidden:overlay});
await installPointer(p,pos);if(P.guide)await installPointer(P.guide,pos);
await p.mouse.move(pos.x,pos.y,{steps:1});
await fs.writeFile(out+'/pointer-start.json',JSON.stringify({x:pos.x,y:pos.y,mode:overlay?'overlay':'page'}));
let queue=Promise.resolve();const serial=fn=>{const r=queue.then(fn);queue=r.catch(()=>{});return r;};

const initial=await p.evaluate(()=>({host:document.querySelector('input[name="hostname"]')?.value,protocol:document.querySelector('[role="dialog"] .ndl-select-control')?.textContent,user:document.querySelector('input[name="username"]')?.value,oldResult:document.querySelector('[role="table"]')!==null}));
if(!cfg.continue&&(initial.host!==cfg.host||initial.protocol!=='bolt://'||initial.user!=='neo4j'||initial.oldResult))throw Error('Unexpected initial state: '+JSON.stringify(initial));
await fs.writeFile(out+'/initial-state.json',JSON.stringify(initial,null,2));
const SCREENCAST={format:'jpeg',quality:95,maxWidth:1920,maxHeight:1080,everyNthFrame:1};
// 정지 화면에서는 프레임이 오지 않으므로 화면에 남지 않는 아주 작은 변화로 한 장을 받는다.
const nudge=pg=>pg.evaluate(()=>{const e=document.documentElement,o=e.style.opacity;e.style.opacity='0.999';requestAnimationFrame(()=>{e.style.opacity=o;});});
const capture=P.ego?(async()=>{while(!done){for(const e of await serial(()=>p.events()))if(e.method==='Page.screencastFrame')onFrame(p,e.params);await sleep(8);}})().catch(e=>{error=String(e);done=true;}):Promise.resolve();
recordingRequestedAt=Date.now();
await p.cdp('Page.startScreencast',SCREENCAST);await nudge(p);
// 녹화하는 탭을 바꾼다(안내 문서 ↔ Neo4j Browser). 화면에는 탭 줄이 없으므로 말이 「안내 문서로 가서」처럼 바뀜을 짚는다.
async function show(target){
 if(target===active)return;
 const n=frames.length;await serial(()=>active.cdp('Page.stopScreencast'));
 await serial(()=>target.bringToFront());await serial(()=>metrics(target));
 await serial(()=>target.mouse.move(pos.x,pos.y,{steps:1}));
 active=target;p=target;await serial(()=>target.cdp('Page.startScreencast',SCREENCAST));await serial(()=>nudge(target));
 const t=Date.now();while(frames.length===n){if(error)throw Error(error);if(Date.now()-t>5000)throw Error('탭을 바꾼 뒤 프레임이 오지 않음');await sleep(20);}
}
async function move(target){
 if(Math.hypot(target.x-pos.x,target.y-pos.y)<1)return;
 const a={...pos},ms=Math.round(Math.max(260,Math.min(620,200+Math.hypot(target.x-a.x,target.y-a.y)*.4))),t0=Date.now();
 await serial(()=>p.evaluate(({a,b,ms})=>{const e=document.getElementById('recording-pointer');window.__recordGlide=e.animate([{transform:`translate(${a.x}px,${a.y}px)`},{transform:`translate(${b.x}px,${b.y}px)`}],{duration:ms,easing:'ease-in-out',fill:'forwards'});},{a,b:target,ms}));
 const glide=Date.now();
 const steps=Math.max(8,Math.ceil(ms/33));for(let i=1;i<=steps;i++){const t=i/steps,u=t*t*(3-2*t);await sleep(Math.max(0,glide+ms*t-Date.now()));await serial(()=>p.mouse.move(a.x+(target.x-a.x)*u,a.y+(target.y-a.y)*u,{steps:1}));}
 await serial(()=>p.evaluate(b=>{const e=document.getElementById('recording-pointer');e.style.transform=`translate(${b.x}px,${b.y}px)`;window.__recordGlide?.cancel();},target));
 pos={x:target.x,y:target.y};motions.push({start:t0-start,glide:glide-start,end:Date.now()-start,from:a,...pos,planned_ms:ms,cue:current});
}
const actions=[];let current=null;
const spec=JSON.parse(await fs.readFile(cfg.cues,'utf8'));
let savedDownload=null,lastDownload=null;
const DOWNLOADS=out+'/받은 파일';
try{
 const waitStart=Date.now();while(start===null){if(error)throw Error(error);if(Date.now()-waitStart>10000)throw Error('No recording frames');await sleep(20);}
 const clickHere=async()=>{await serial(()=>p.mouse.down());await sleep(95);await serial(()=>p.mouse.up());clicks.push({x:pos.x,y:pos.y,cue:current,time:Date.now()-start,page:p===P.guide?'guide':'main'});};
 const act=async(spec,click=false)=>{let target;for(let i=0;i<15;i++){const a=await serial(()=>point(spec));await sleep(150);target=await serial(()=>point(spec));if(Math.hypot(a.x-target.x,a.y-target.y)<1)break;if(i===14)throw Error('Unstable target');}await move(target);if(click){const r=await serial(()=>point(spec));if(Math.hypot(r.x-target.x,r.y-target.y)>2)throw Error('Target moved');await clickHere();}};
 let free=Date.now()-60000;
 const cue=async(c,operation)=>{
  current=c.id;
  const meta=cfg.silent?{text:c.text,duration_ms:Math.round(c.text.replace(/\s/g,'').length/SPEECH_RATE/(typeof cfg.silent==='number'?cfg.silent:1))}:JSON.parse(await fs.readFile(AUDIO+'/'+c.id+'.json','utf8').catch(()=>{throw Error('Voice cue missing: '+c.id+' (voice.py로 만든 뒤 촬영)');}));
  if(!cfg.silent&&meta.text!==c.text)throw Error('음성 글이 큐와 다름: '+c.id);
  const at=Math.max(Date.now()+30,free+(c.gap??cfg.gap??1300));
  const a={id:c.id,text:meta.text,time:at-start,duration:meta.duration_ms,segment:c.segment};actions.push(a);await sleep(Math.max(0,at-Date.now()));
  const gate=async(fraction)=>{await sleep(Math.max(0,at+meta.duration_ms*fraction-Date.now()));if(error)throw Error(error);};
  a.actionStart=Date.now()-start;await operation(gate,a);a.actionEnd=Date.now()-start;
  await sleep(Math.max(0,at+meta.duration_ms-Date.now()));
  free=Date.now()+(c.hold||0);a.hold=c.hold||0;};

 const editor={css:'[aria-label="Cypher Editor"]'};
 const runButton={css:'[data-testid="run-button"]'};
 // 입력칸을 비우고 글을 넣는다. paste:true면 붙여넣기(안내 문서에서 복사한 글)로 넣고, 들어간 글이 기대한 문장과 같은지 본다.
 async function input(text,{paste=false}={}){
  await act(editor);await clickHere();await serial(()=>p.keyboard.press('ControlOrMeta+A'));await serial(()=>p.keyboard.press('Backspace'));
  if(paste){await serial(()=>p.keyboard.press('ControlOrMeta+V'));}
  else{await move({x:650,y:135});await serial(()=>p.keyboard.insertText(text));}
  const got=await serial(()=>p.evaluate(()=>{const e=Array.from(document.querySelectorAll('[aria-label="Cypher Editor"]')).find(e=>e.getBoundingClientRect().height>0);return e?.querySelector('.cm-content')?.innerText??e?.innerText;}));
  if(paste&&got.replace(/\s+/g,' ').trim()!==text.replace(/\s+/g,' ').trim())throw Error('붙여 넣은 글이 다름: '+JSON.stringify(got));
  if(paste)await move({x:650,y:135});
  await serial(()=>p.keyboard.press('Escape'));
 }
 const resultPoint=async()=>act({css:'[role="table"] [role="cell"]'});
 const hasDetails=()=>p.evaluate(()=>Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6,[role="heading"]')).some(e=>/^(Node details|Relationship details|Results overview)$/.test(e.textContent.trim())&&e.getBoundingClientRect().height>0));
 const graphButton=name=>({css:`button[aria-label="${name}"]`});
 async function graphPoint(label,edge=false,allowOutside=false){let now;for(let i=0;i<25;i++){try{const before=await serial(()=>p.evaluate(graphTarget,{label,edge,allowOutside}));await sleep(150);now=await serial(()=>p.evaluate(graphTarget,{label,edge,allowOutside}));if(Math.hypot(before.x-now.x,before.y-now.y)<1)return now;}catch(e){if(i===24)throw e;}await sleep(80);}throw Error('Unstable graph target '+label);}
 // between:[A,B] — 두 노드 원 중심을 frac(기본 .5)로 나눈 점. 같은 관계 유형이 여럿일 때 그 선을 고른다.
 async function betweenPoint([A,B],frac=.5){const a=await graphPoint(A),b=await graphPoint(B);return {x:a.x+(b.x-a.x)*frac,y:a.y+(b.y-a.y)*frac};}
 async function chooseGraph(c,a,g){if(!await serial(hasDetails)){await act(graphButton('Toggle graph details panel'),true);}const pick=()=>c.between?betweenPoint(c.between,c.frac):graphPoint(c.label,c.op==='edge');
 let target=c.direct?await pick():await focusReadableGraph({p,serial,move,graphPoint,act,label:c.between?c.between[1]:c.label,edge:c.op==='edge'&&!c.between,clickHere,gate:g,guided:c.guided_focus,first:!!c.first});if(c.between&&!c.direct)target=await pick();if(c.guided_focus||c.direct)await g(c.click_at??(c.first?.86:.81));await move(target);target=await pick();if(Math.hypot(pos.x-target.x,pos.y-target.y)>2)await move(target);await clickHere();a.clickAt=Date.now()-start;await serial(()=>p.waitForFunction(({verify})=>{const h=Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6,[role="heading"]')).find(e=>/^(Node details|Relationship details)$/.test(e.textContent.trim())&&e.getBoundingClientRect().height>0);return h?.parentElement?.parentElement?.innerText.includes(verify);},{verify:c.verify},{timeout:10000}));a.details=await serial(()=>p.evaluate(()=>{const h=Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6,[role="heading"]')).find(e=>/^(Node details|Relationship details)$/.test(e.textContent.trim())&&e.getBoundingClientRect().height>0);return h.parentElement.parentElement.innerText;}));a.selectionVerified=true;a.selectionReady=Date.now()-start;}
 let graph=false;
 const activeCues=spec.cues.filter(c=>(!cfg.only||cfg.only.includes(c.id))&&(!cfg.segments||cfg.segments.includes(c.segment)));
 if(!activeCues.length)throw Error('찍을 큐가 없다(segments · only 확인)');
 // 큐 하나에 조작이 여럿이면(ops) 차례로 한다. 조작마다 자기 at(말 안의 비율)을 기다린다.
 const visibleText=(contains,within)=>p.evaluate(({contains,within})=>{const root=within?document.querySelector(within):document;const e=Array.from(root.querySelectorAll('*')).filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&r.y>=0&&r.bottom<=innerHeight&&e.textContent.trim().includes(contains)&&![...e.children].some(k=>k.textContent.includes(contains));})[0];if(!e)throw Error('화면에 그 글이 없다: '+contains);const r=e.getBoundingClientRect();return {x:r.x+Math.min(r.width/2,90),y:r.y+r.height/2,w:r.width};},{contains,within});
 const pointAt=async q=>{const t=q.css?await serial(()=>point(q)):await serial(()=>visibleText(q.contains??q.text,q.within));await move({x:t.x+(q.dx??14),y:t.y+(q.dy??8)});};
 const clickText=async(text,css='button')=>{await act({css,text},true);};
 async function doOp(c,g,a){
   a.op=(a.op?a.op+'+':'')+c.op;
   switch(c.op){
    case 'none':break;
    // 결과 카드(그림 · 표)를 위에서부터 센 n번째(0 = 맨 위 새 카드)의 윗부분을 짚는다. 화면 안에 없으면 멈춘다.
    case 'pointCard':{await g(c.at??.2);const r=await serial(()=>p.evaluate(n=>{const els=[...document.querySelectorAll('[data-testid="nvl-c2d-canvas"],[role="table"]')].filter(e=>e.getBoundingClientRect().height>0).sort((a,b)=>a.getBoundingClientRect().top-b.getBoundingClientRect().top);const e=els[n];if(!e)throw Error('그 카드가 없다: '+n);const r=e.getBoundingClientRect();if(r.top>innerHeight-50)throw Error('그 카드가 화면 아래에 있다: '+n);return {x:r.x+r.width*.4,y:Math.min(r.top+50,innerHeight-30)};},c.n));await move(r);break;}
    case 'point':for(const q of c.points){await g(q.at??.1);await pointAt(q);}break;
    case 'pointText':await g(c.at??.1);await pointAt({contains:c.contains,within:c.within,dx:c.dx,dy:c.dy});break;
    case 'pointStream':await g(c.at??.1);{const r=await serial(()=>p.evaluate(()=>{const e=[...document.querySelectorAll('article,[data-testid*="frame"],section')].find(e=>{const r=e.getBoundingClientRect();return r.y>150&&r.height>120&&r.x>400;});if(!e)throw Error('결과 카드가 없다');const r=e.getBoundingClientRect();return {x:r.x+r.width*.45,y:r.y+Math.min(r.height*.4,180)};}));await move(r);}break;
    // 처음 쓰는 사람용 안내 창(Work in tabs의 Dismiss, Discover more actions의 OK, got it)을 닫는다. 창이 없으면 학생 화면과 달라진 것이라 멈춘다.
    case 'tour':await g(c.point_at??Math.max(0,(c.at??.85)-.25));await act({css:'button',text:c.button});await g(c.at??.85);await act({css:'button',text:c.button},true);
     await serial(()=>p.waitForFunction(t=>![...document.querySelectorAll('button')].some(b=>b.textContent.trim()===t&&b.getBoundingClientRect().height>0),c.button,{timeout:5000}));break;
    case 'sidebar':
     if(await serial(()=>p.evaluate(()=>!!document.querySelector('button[title="Open Sidebar"]')))){await g(c.open_at??.2);await act({css:'button[title="Open Sidebar"]'},true);}
     await g(c.at??.8);await act({css:`[aria-label="${c.button}"]`},true);break;
    case 'openSidebar':await g(c.at??.8);await act({css:'button[title="Open Sidebar"]'},true);break;
    case 'collapse':await g(c.at??.8);await act({css:'button[title="Collapse Sidebar"]'},true);break;
    case 'fit':await g(c.at??.8);await act({css:'button[aria-label="Zoom to fit"]'},true);await sleep(500);break;
    case 'closeDetails':await g(c.at??.8);if(await serial(hasDetails))await act({css:'button[aria-label="Toggle graph details panel"]'},true);break;
    case 'layout':await g(c.at??.6);await act({css:'button[aria-label="Select layout"]'},true);await sleep(250);await act({css:'[role="menuitemradio"]',text:'Hierarchical layout'},true);await sleep(600);break;
    case 'guideShow':{
     if(!P.guide)throw Error('안내 문서 탭이 없다(cfg.guide)');
     await g(c.at??.9);await show(P.guide);
     const w=await serial(()=>p.evaluate(q=>{const b=Array.from(document.querySelectorAll('.block')).find(b=>b.querySelector('pre')?.innerText.replace(/\s+/g,' ').trim()===q.replace(/\s+/g,' ').trim());if(!b)throw Error('안내 문서에 그 칸이 없다');const r=b.querySelector('pre').getBoundingClientRect();return {x:r.x+Math.min(r.width*.55,640),y:r.y+r.height*.5,bottom:b.getBoundingClientRect().bottom};},c.query));
     if(w.bottom>P.view.height-10)throw Error('안내 문서의 그 칸이 화면 아래로 잘림 — prep guide로 그 절에 맞춰 둔다');
     await move(w);break;}
    case 'guideCopy':{
     const where=()=>p.evaluate(q=>{const b=Array.from(document.querySelectorAll('.block')).find(b=>b.querySelector('pre')?.innerText.replace(/\s+/g,' ').trim()===q.replace(/\s+/g,' ').trim());const r=b.querySelector('.copy').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};},c.query);
     await g(c.point_at??.15);let w=await serial(where);await move(w);
     await g(c.at??.8);w=await serial(where);if(Math.hypot(w.x-pos.x,w.y-pos.y)>2)await move(w);await clickHere();
     await serial(()=>p.waitForFunction(()=>Array.from(document.querySelectorAll('.copied')).some(e=>e.textContent.startsWith('복사했습니다')),undefined,{timeout:5000}));a.copied=true;break;}
    case 'mainShow':await g(c.at??.6);await show(P.main);break;
    case 'fileShow':await g(c.at??.6);await show(P.file);break;
    case 'paste':await g(c.at??.5);await input(c.query,{paste:true});a.query=c.query;a.pasted=true;break;
    // 받은 그림 파일을 새 탭으로 연다(학생이 내려받기 표시에서 여는 것과 같은 그림). 녹화 밖에서 열어 두지 않고 그 자리에서 연다.
    case 'openFile':{await g(c.at??.4);if(!lastDownload)throw Error('열 파일이 없다(앞 png 조작)');
     const pg=await P.newPage();await P.attach(pg);await pg.goto('file://'+lastDownload);await serial(()=>metrics(pg));await installPointer(pg,pos);P.file=pg;await show(pg);break;}
    case 'newTab':await g(c.at??.8);await act({css:'button[aria-label="Add new tab"]'},true);await serial(()=>p.waitForFunction(()=>[...document.querySelectorAll('[role="tab"]')].some(e=>/Untitled Query/.test(e.textContent)),undefined,{timeout:5000}));break;
    case 'closeTab':await g(c.at??.8);await act({css:'button[aria-label="Close tab"]'},true);break;
    case 'openSaved':await g(c.at??.8);await act({css:`[role="group"][aria-label="${spec.saved_title}"]`},true);
     await serial(()=>p.waitForFunction(t=>Array.from(document.querySelectorAll('[aria-label="Cypher Editor"]')).some(e=>e.getBoundingClientRect().height>0&&e.innerText.includes(t)),spec.saved_title,{timeout:10000}));a.reopened=true;break;
    case 'savedPoint':await g(c.at??.2);await act({css:`[role="group"][aria-label="${spec.saved_title}"]`});break;
    case 'intro':await g(.15);await move(c.to||{x:500,y:240});break;
    case 'talk':for(let i=0;i<(c.points||[]).length;i++){await g(c.points[i].at);await move(c.points[i]);}break;
    case 'connect':
     await g(c.at?.[0]??.2);await act({css:'.ndl-select-control'});
     await g(c.at?.[1]??.32);await act({css:'input[name="hostname"]'});
     await g(c.at?.[2]??.52);await act({css:'input[name="username"]'});
     await g(c.at?.[3]??.68);await act({css:'input[name="password"]'});
     await g(c.at?.[4]??.88);await act({text:'Connect'},true);
     await serial(()=>p.waitForFunction(()=>!!document.querySelector('[data-testid="connection-status-indicator-success"]')&&document.body.innerText.includes('neo4j'),undefined,{timeout:15000}));
     break;
    case 'connected':await g(.12);await act({css:'[data-testid="instance-menu-button"]'});await g(.4);await act({css:'[data-testid="database-menu-button"]'});break;
    case 'clear':
     await g(c.at??.25);await input(':clear');await g(c.enter_at??.65);await serial(()=>p.keyboard.press('Enter'));
     await serial(()=>p.waitForFunction(()=>!document.querySelector('[role="table"]')&&!document.querySelector('[data-testid="nvl-c2d-canvas"]')&&!document.body.innerText.includes(':welcome'),undefined,{timeout:10000}));
     await serial(()=>p.keyboard.press('ControlOrMeta+A'));await serial(()=>p.keyboard.press('Backspace'));graph=false;break;
    case 'overview':
     if(await serial(()=>p.evaluate(()=>!!document.querySelector('button[title="Open Sidebar"]')))){await g(.12);await act({css:'button[title="Open Sidebar"]'},true);}
     await g(c.at?.[0]??.25);await act({css:'button[title="Collapse Sidebar"]'},true);await g(c.at?.[1]??.45);await act({css:'button[title="Open Sidebar"]'},true);
     await g(c.at?.[2]??.7);await act({css:'button[aria-label="Database overview"]'},true);break;
    case 'overviewResult':
     await g(.12);await act({css:'button[aria-label="All Nodes"]'});await g(.6);await act({css:'button[aria-label="All Relationships"]'});break;
    case 'editorTour':await g(.12);await act(editor);await g(.4);await act(runButton);await g(.7);await move({x:900,y:270});break;
    // 안내 문서 탭으로 가서 그 칸(글이 c.query인 블록)의 복사 단추를 누르고, Neo4j Browser로 돌아와 입력칸에 붙여 넣는다.
    case 'guideCopy':{
     if(!P.guide)throw Error('안내 문서 탭이 없다(cfg.guide)');
     await g(c.at?.[0]??.1);await show(P.guide);
     const block={css:'.block .copy',within:c.query};
     const where=()=>p.evaluate(q=>{const b=Array.from(document.querySelectorAll('.block')).find(b=>b.querySelector('pre')?.innerText.replace(/\s+/g,' ').trim()===q.replace(/\s+/g,' ').trim());if(!b)throw Error('안내 문서에 그 칸이 없다');const r=b.querySelector('.copy').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2,top:b.getBoundingClientRect().top};},c.query);
     let w=await serial(where);if(w.y<0||w.y>P.view.height-40)throw Error('복사 단추가 화면 밖: '+JSON.stringify(w)+' — 안내 문서를 그 칸에 맞춰 둔 뒤 찍는다');
     await g(c.at?.[1]??.35);await move({x:w.x,y:w.y});w=await serial(where);if(Math.hypot(w.x-pos.x,w.y-pos.y)>2)await move(w);
     await g(c.at?.[2]??.45);await clickHere();
     await serial(()=>p.waitForFunction(()=>Array.from(document.querySelectorAll('.copied')).some(e=>e.textContent.startsWith('복사했습니다')),undefined,{timeout:5000}));
     a.copied=true;
     await g(c.at?.[3]??.7);await show(P.main);
     await g(c.at?.[4]??.8);await input(c.query,{paste:true});a.query=c.query;a.pasted=true;break;}
    case 'query':await g(c.at??.15);await input(c.query);a.query=c.query;break;
    case 'editorPoint':await g(.15);await move({x:700,y:110+(c.line-1)*12});break;
    case 'run':
     const previous=await serial(()=>p.evaluate(()=>document.querySelector('[role="table"]')?.innerText||''));await g(c.at??.43);await act(runButton,true);a.runAt=Date.now()-start;
     await serial(()=>p.waitForFunction(({rows,graph,previous,nodes,edges})=>graph?Array.from(document.querySelectorAll('[role="status"]')).find(e=>e.textContent.startsWith('A graph visualization'))?.textContent.includes(`with ${nodes} ${nodes===1?"node":"nodes"} and ${edges} ${edges===1?"relationship":"relationships"}`):Array.from(document.querySelector('[role="table"]')?.querySelectorAll('[role="row"]')||[]).filter(e=>e.querySelector('[role="cell"]')).length===rows&&(document.querySelector('[role="table"]')?.innerText||'')!==previous,{rows:c.rows,graph:c.graph,previous,nodes:c.nodes,edges:c.edges},{timeout:15000}));
     a.resultVerified=true;a.nodes=c.nodes;a.edges=c.edges;a.rows=c.rows;a.resultReady=Date.now()-start;graph=c.graph;break;
    case 'runSummary':
     await g(c.at??.35);await act(runButton,true);a.runAt=Date.now()-start;
     await serial(()=>p.waitForFunction(verify=>document.body.innerText.includes(verify),c.verify,{timeout:15000}));
     a.resultVerified=true;a.summary=c.verify;a.resultReady=Date.now()-start;graph=false;break;
    case 'summaryTalk':await g(.15);await move(c.to||{x:600,y:290});break;
    case 'result':await g(.15);await resultPoint();break;
    case 'mapLayout':
     await g(.12);if(await serial(()=>p.evaluate(()=>!!document.querySelector('button[title="Collapse Sidebar"]'))))await act({css:'button[title="Collapse Sidebar"]'},true);
     if(await serial(hasDetails))await act(graphButton('Toggle graph details panel'),true);
     await g(c.at?.[0]??.4);await act(graphButton('Select layout'),true);await act({css:'[role="menuitemradio"]',text:'Hierarchical layout'},true);
     await g(c.at?.[1]??.7);await act(graphButton('Zoom to fit'),true);break;
    case 'basicFit':
     await g(c.at?.[0]??.25);if(await serial(()=>p.evaluate(()=>!!document.querySelector('button[title="Collapse Sidebar"]'))))await act({css:'button[title="Collapse Sidebar"]'},true);
     if(await serial(hasDetails))await act(graphButton('Toggle graph details panel'),true);
     await g(c.at?.[1]??.65);await act(graphButton('Zoom to fit'),true);break;
    case 'node':case 'edge':await g(.08);await chooseGraph(c,a,g);break;
    case 'details':
     await g(.2);const prop=await serial(()=>p.evaluate(()=>{const h=Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6,[role="heading"]')).find(e=>/^(Node details|Relationship details)$/.test(e.textContent.trim())&&e.getBoundingClientRect().height>0);const r=h?.parentElement?.parentElement?.getBoundingClientRect();return r&&{x:r.x+Math.min(r.width-30,140),y:r.y+150};}));if(prop)await move(prop);break;
    // 정보 칸의 글(이름표 · 속성 이름)을 차례로 짚는다. points: [{text, at}] — 그 글이 정보 칸에 정확히 있어야 한다.
    case 'detailsTour':
     for(const q of c.points){await g(q.at);const t=await serial(()=>p.evaluate(text=>{const h=Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6,[role="heading"]')).find(e=>/^(Node details|Relationship details)$/.test(e.textContent.trim())&&e.getBoundingClientRect().height>0);const box=h.parentElement.parentElement;const e=Array.from(box.querySelectorAll('*')).filter(e=>e.children.length===0&&e.textContent.trim()===text&&e.getBoundingClientRect().height>0)[0];if(!e)throw Error('정보 칸에 글 없음: '+text);const r=e.getBoundingClientRect();return {x:r.x+Math.min(r.width/2,60),y:r.y+r.height/2};},q.text));await move({x:t.x+14,y:t.y+6});}break;
    case 'mapTour':case 'graphTalk':
     for(let i=0;i<(c.points||[]).length;i++){const q=c.points[i],label=typeof q==='string'?q:q.label;await g(typeof q==='string'?.15+i*.2:q.at);await move(q.between?await betweenPoint(q.between,q.frac):await graphPoint(label,!!q.edge));}break;
    case 'png':{
     await g(c.at??.7);const pngWait=p.waitForEvent('download',{timeout:15000});await act(graphButton('Download as PNG'),true);const png=await pngWait;
     a.png=DOWNLOADS+'/'+png.suggestedFilename();await fs.mkdir(DOWNLOADS,{recursive:true});await png.saveAs(a.png);lastDownload=a.png;break;}
    case 'graphResult':await g(.15);await move(c.to||{x:850,y:330});break;
    case 'newSaved':
     await g(.12);if(await serial(()=>p.evaluate(()=>!!document.querySelector('button[title="Open Sidebar"]'))))await act({css:'button[title="Open Sidebar"]'},true);await g(c.at?.[0]??.32);await act({css:'button[aria-label="Queries"]'},true);await g(c.at?.[1]??.55);await act({css:'button[aria-label="Add new tab"]'},true);break;
    case 'saveText':await g(c.at??.5);await input(spec.saved_query);await serial(()=>p.keyboard.press('ControlOrMeta+Home'));a.savedText=true;break;
    case 'reopen':
     await serial(()=>p.waitForSelector(`[role="group"][aria-label="${spec.saved_title}"]`,{timeout:10000}));
     await g(c.at?.[0]??.3);await act({css:'button[aria-label="Close tab"]'},true);
     await g(c.at?.[1]??.57);await act({css:`[role="group"][aria-label="${spec.saved_title}"]`},true);
     await serial(()=>p.waitForFunction(t=>Array.from(document.querySelectorAll('[aria-label="Cypher Editor"]')).some(e=>e.getBoundingClientRect().height>0&&e.innerText.includes(t)),spec.saved_title,{timeout:10000}));a.reopened=true;break;
    case 'download':
     await g(c.at??.73);const waiting=p.waitForEvent('download',{timeout:15000});await act({css:'button[aria-label="Download all"]'},true);
     const d=await waiting;savedDownload=DOWNLOADS+'/'+d.suggestedFilename();await fs.mkdir(DOWNLOADS,{recursive:true});await d.saveAs(savedDownload);a.download=savedDownload;break;
    case 'savedResult':await g(.1);await act({css:`[role="group"][aria-label="${spec.saved_title}"]`});break;
    case 'outro':await g(.1);await move(c.to||{x:900,y:300});break;
    default:throw Error('모르는 op: '+c.op);
   }
 }
 for(const c of activeCues){
  await cue(c,async(g,a)=>{for(const o of (c.ops||[c]))await doOp({...o,id:c.id},g,a);});
  await fs.writeFile(out+'/progress.json',JSON.stringify({lastCue:c.id,completed:actions.length,frames:frames.length,elapsed_ms:Date.now()-start}));
  console.log('captured '+c.id+' '+c.op);
 }
 await sleep(Math.max(0,free-Date.now())+400);
}catch(e){error=String(e?.stack||e);}
done=true;await capture;await writes;await active.cdp('Page.stopScreencast').catch(()=>{});
const duration=Date.now()-start;
await fs.writeFile(out+'/timing.json',JSON.stringify({start,duration,frames,motions,actions,error,result:error?null:'recorded'},null,2));
await fs.writeFile(out+'/end-state.json',JSON.stringify({url:await P.main.url(),page:active===P.guide?'guide':'main',pointer:pos,clicks:await P.main.evaluate(()=>window.__recordClicks||[]),guideClicks:P.guide?await P.guide.evaluate(()=>window.__recordClicks||[]):[],sentClicks:clicks,targets},null,2));
await P.close();
console.log(JSON.stringify({frames:frames.length,duration,error}));
