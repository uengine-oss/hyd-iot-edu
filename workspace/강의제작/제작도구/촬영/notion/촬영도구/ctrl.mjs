// Notion 녹화 제어기.
//  run()   : 구간 모듈 하나를 녹화한다(옛 판 segs/seg-*.mjs, run.sh rec — 지금 게시본 재현용).
//  chain() : v12 구간 모듈(segs/v12-*.mjs)을 한 ego 실행 안에서 큐 파일의 단계 차례대로 녹화한다(run.sh chain12). 화면 크기를 한 번만 걸고
//            탭 · 페이지 · 커서를 이어 쓰므로 구간 경계에서 화면이 다시 배치되지 않는다. 구간마다 녹화 · end-state.json · timing.json을 따로 남기고,
//            구간이 끝날 때마다 실측(이동 공백)과 오류 · 업데이트 막대 검사(녹화 중 2초마다 글로 본다)를 해서 걸리면 그 구간에서 멈춘다.
//            rehearsal=true(run.sh rehearse12)면 녹화 · 음성 없이 조작만 끝까지 돌린다(영상 길 16의 리허설). 큐 길이는 촬영/시간계수.json의 말 계수로
//            어림하고 REHEARSAL_SCALE을 곱해 줄인다. 홈 제목은 「내 학습 노트 리허설」이라 녹화 페이지와 섞이지 않는다.
// 리듬: 행동 문장 안에서 가리키고 문장 끝 약 250ms 전에 실행(gate), 결과 발화는 행동 종료 뒤. 모든 ego 호출은 한 직렬 큐.
// 출력: <work>/<name>/frames/*.jpg · timing.json(프레임·큐·이동) · end-state.json(URL·클릭) · end-snapshot.txt
const fs=await import('node:fs/promises');
const HERE=decodeURIComponent(new URL('.',import.meta.url).pathname).replace(/^\/([A-Za-z]:)/,'$1');
const CFG=JSON.parse(await fs.readFile(HERE+'config.json','utf8'));
const abs=r=>decodeURIComponent(new URL(r,'file:///'+HERE).pathname.replace(/^\/([A-Za-z]:)/,'$1').replace(/\/$/,''));
const WORK=abs(CFG.work),AUDIO=abs(CFG.audio_play);  // 녹화가 읽는 음성 = 음성쉼.py가 쉼을 넓힌 판
const SC={format:'jpeg',quality:85,maxWidth:1920,maxHeight:1080,everyNthFrame:1};
const HOME_TITLE='내 학습 노트',REHEARSAL_TITLE='내 학습 노트 리허설',REHEARSAL_SCALE=0.5;
// 리허설 큐 길이(ms): 시간계산.py speech_seconds와 같은 셈(음절 · 숫자 · 영문 · 부호 개수 × 초/개).
let COEF=null;
async function speechMs(text){COEF??=JSON.parse(await fs.readFile(HERE+'../../시간계수.json','utf8')).speech;const f=[/[가-힣]/g,/[0-9]/g,/[A-Za-z]/g,/[.?!,]/g].map(r=>(text.match(r)||[]).length);return Math.round(1000*f.reduce((a,n,i)=>a+n*COEF[i],0));}

function jpegSize(b){let i=2;while(i<b.length){if(b[i]!==255){i++;continue;}const marker=b[i+1];i+=2;if(marker===216||marker===217)continue;const len=b.readUInt16BE(i);if([192,193,194].includes(marker))return {width:b.readUInt16BE(i+5),height:b.readUInt16BE(i+3)};i+=len;}throw Error('JPEG dimensions missing');}
const ACT=/(누르|눌러|누를|클릭|선택|입력|적을|적어|적겠|닫는|닫을|열겠|엔터|가져가)/;
// 행동 문장 = 조작 동사가 있는 마지막 문장. 시점은 글자 비율 추정(단어 시각 없음). v12는 큐 끝(▸)이 조작 자리라 pointFrac · commitFrac를 직접 준다.
function plan(c){
 const s=c.text.split(/(?<=[.?!])\s+/);const total=c.text.length;let at=0;const spans=s.map(x=>{const a=at;at+=x.length+1;return{a,b:Math.min(total,at-1),x};});
 const k=[...spans].reverse().find(x=>ACT.test(x.x))||spans.at(-1);
 return{pointFrac:k.a/total,commitFrac:k.b/total,sentence:k.x};
}

// 한 ego 실행의 공유 상태: 작업 공간, 녹화 탭 p1, 지금 앞에 둔 탭(cur), 열어 둔 다른 탭(pages), 직렬 큐, 구간 사이에 넘기는 값(state).
async function session(space){
 const task=await taskSpace(space);const p=task.page('p1');
 let queue=Promise.resolve();
 const sess={task,p,cur:p,sized:new Set(),pages:new Map(),state:{},serial:(fn,label='input')=>{const tq=Date.now();const r=queue.then(async()=>{const t0=Date.now();try{return await fn();}finally{if(sess.qlog)sess.qlog.push([label,tq,t0,Date.now()]);}});queue=r.catch(()=>{});return r;}};  // qlog: 직렬 큐 계측(라벨 · 넣은 시각 · 시작 · 끝)
 await size(sess,p);await korean(p);return sess;
}
// 노션 화면 언어 고정: 같은 쿠키(ko-KR)인데도 새로 불러올 때마다 영어로 그려지는 일이 섞여(2026-11-12 실측 다섯 번 중 한 번만 한국어),
// 탭마다 로캘과 Accept-Language를 ko-KR로 건다(건 뒤 실측 다섯 번 중 네 번 한국어 — 남는 영어는 구간 준비가 다시 불러 맞춘다).
// 서비스 워커를 거치지 않는다: 쿠키(NEXT_LOCALE · notion_locale) · navigator.language가 모두 ko-KR인데도 sw.js가 캐시한 앱 판을 쓰면 열 번 중 세 번
// 영어로 그렸고, 거치지 않게 하자 열 번 모두 한국어였다(2026-11-13 실측).
async function korean(pg){await pg.cdp('Emulation.setLocaleOverride',{locale:'ko-KR'});await pg.cdp('Network.enable');await pg.cdp('Network.setBypassServiceWorker',{bypass:true});await pg.cdp('Network.setExtraHTTPHeaders',{headers:{'Accept-Language':'ko-KR,ko;q=0.9'}});}
async function size(sess,pg){await pg.cdp('Emulation.setDeviceMetricsOverride',{width:CFG.viewport.width,height:CFG.viewport.height,deviceScaleFactor:1,mobile:false});sess.sized.add(pg);}

// 지금 앞에 둔 탭의 화면 한 장을 녹화와 같은 길(screencast)로 받는다. 녹화 밖에서만 쓴다.
async function grabFrame(sess){const pg=sess.cur;return sess.serial(async()=>{await pg.events();await pg.cdp('Page.startScreencast',SC);let f=null;
 for(let i=0;i<100&&!f;i++){for(const e of await pg.events())if(e.method==='Page.screencastFrame'){await pg.cdp('Page.screencastFrameAck',{sessionId:e.params.sessionId});f=e;break;}if(!f)await new Promise(r=>setTimeout(r,50));}
 await pg.cdp('Page.stopScreencast');if(!f)throw Error('No screencast frame within 5s');return Buffer.from(f.params.data,'base64');});}

// 이동마다 첫 프레임 뒤의 최대 프레임 공백(measure.py와 같은 셈). chain의 멈춤 기준: 0.5초 넘는 공백 3회 이상(영상 V-14).
function measureGaps(frames,motions,start){
 const src=frames.map(f=>f.sourceTimestamp*1000-start).sort((a,b)=>a-b);const gaps=[];
 // 재는 창은 화살표가 실제로 움직이는 동안(계획 시간 + 150ms)이다. 그 뒤는 화살표가 목표에 고정된 채 실제 입력(RPC)이 끝나기를 기다리는 정지라
 // 바뀔 것이 없어 프레임이 오지 않는다(k3 v12-02: 0.5초 넘는 공백 4곳이 모두 도착 뒤 정지였다).
 for(const m of motions){const end=Math.min(m.end,m.start+(m.planned_ms??(m.end-m.start))+150);const v=src.filter(x=>x>=m.start&&x<=end);if(!v.length){gaps.push(Math.round(end-m.start));continue;}let g=0;for(let i=0;i<v.length;i++)g=Math.max(g,(i+1<v.length?v[i+1]:end)-v[i]);gaps.push(Math.round(g));}
 return{moves:gaps.length,maxGap:gaps.length?Math.max(...gaps):null,over100:gaps.filter(g=>g>=100),gaps500:gaps.filter(g=>g>=500).length};
}

// 구간 하나 녹화. body(ctx)가 구간 본문이다. opts: name, lead(앞 구간 끝 쉼 ms — 첫 큐의 쉼에서 뺀다), tail(끝 쉼 ms), watchBanner, cues, cueText, prev.
async function record(sess,opts,body){
 const out=WORK+'/'+opts.name;
 await fs.mkdir(out+'/frames',{recursive:true});
 if((await fs.readdir(out+'/frames')).length)throw Error('Output folder already has frames: '+out);
 const {p,serial}=sess;sess.qlog=[];
 const sleep=ms=>new Promise(r=>setTimeout(r,ms));
 let recording=false,done=false,error=null,writeQueue=Promise.resolve(),bufferBytes=0,start=null,lastPoll=0;const frames=[],actions=[],motions=[],banners=[];
 const capture=(async()=>{while(!done){
  const pg=sess.cur;const evs=await serial(()=>pg.events(),'events');
  for(const e of evs)if(e.method==='Page.screencastFrame'){
   serial(()=>pg.cdp('Page.screencastFrameAck',{sessionId:e.params.sessionId}),'ack').catch(x=>{error=String(x);});
   if(!recording||pg!==sess.cur)continue;const b=Buffer.from(e.params.data,'base64');const d=jpegSize(b);
   if(d.width!==1920||d.height!==1080){if(start===null)continue;throw Error('Capture dimensions '+JSON.stringify(d));}
   if(start===null)start=Date.now();
   const f={file:'frames/'+String(frames.length).padStart(6,'0')+'.jpg',time:Date.now()-start,sourceTimestamp:e.params.metadata.timestamp};frames.push(f);bufferBytes+=b.length;
   if(bufferBytes>64*1024*1024)throw Error('Capture disk queue exceeded 64MiB');
   writeQueue=writeQueue.then(async()=>{await fs.writeFile(out+'/'+f.file,b);await fs.appendFile(out+'/frames.jsonl',JSON.stringify(f)+'\n');bufferBytes-=b.length;});
  }
  // Notion 오류 문구 · 「최신 버전으로 업데이트」 막대를 녹화 중 2초마다 글로 본다. 보이면 그 take는 쓸 수 없으니 다음 큐에서 멈춘다.
  if(opts.watchBanner&&recording&&sess.cur===p&&Date.now()-lastPoll>2000){lastPoll=Date.now();
   const t=await serial(()=>p.evaluate(()=>{const s=document.body.innerText;return s.includes('최신 버전으로 업데이트')?'update':/문제가 발생했습니다/.test(s)?'error':null;}),'banner').catch(()=>null);
   if(t){banners.push({kind:t,time:Date.now()-start});error??='Notion '+t+' banner during recording';}}
  await sleep(8);
 }})().catch(e=>{error=String(e);done=true;});
 let speechFree=0,actionFree=0,pending=null;
 async function cue(ctx,c,fn,opt={}){
  if(error)throw Error(error);
  if(!recording||start===null)throw Error('Cue '+c.id+' before recording began (call c.begin() first)');
  if(await fs.stat(WORK+'/STOP').then(()=>true).catch(()=>false))throw Error('Stop requested');
  if(!opt.overlap&&pending){await pending;pending=null;}
  // 큐 사이 기본 쉼 1000ms = 영상 V-14(큐 1.0초). 조작 직후 같은 문맥의 말은 opt.gap으로 짧게 준다. v12는 큐 파일의 pause_before를 준다.
  const w=Math.max(speechFree,opt.overlap?0:actionFree)+(opt.gap??1000)-Date.now();if(w>0)await sleep(w);
  const t0=Date.now();const a={id:c.id,text:c.text,time:t0-start,duration:c.duration_ms};actions.push(a);
  speechFree=t0+c.duration_ms;ctx.cueT0=t0;ctx.cueDur=c.duration_ms;
  if(!fn){actionFree=Math.max(actionFree,t0);return;}
  const pl=plan(c);const pointAt=t0+Math.round(c.duration_ms*(opt.pointFrac??pl.pointFrac))+(opt.pointDelay??250);
  const commitAt=t0+Math.round(c.duration_ms*(opt.commitFrac??pl.commitFrac))-(opt.commitLead??250);
  Object.assign(a,{plannedPoint:pointAt-start,plannedCommit:commitAt-start,actionSentence:opt.pointFrac!=null?c.text.slice(Math.round(c.text.length*opt.pointFrac)):pl.sentence,estimate:'character-proportional'});
  const go=(async()=>{const w2=pointAt-Date.now();if(w2>0)await sleep(w2);ctx.commitAt=commitAt;ctx.committed=null;a.actionStart=Date.now()-start;
   await fn();a.commit=ctx.committed?ctx.committed-start:null;a.actionEnd=Date.now()-start;actionFree=Date.now();})();
  if(opt.async){pending=go;return;}
  await go;
 }
 let result=null;
 try{
  const ctx={p,serial,sleep,fs,out,abs,work:WORK,rehearsal:!!opts.rehearsal,homeTitle:opts.rehearsal?REHEARSAL_TITLE:HOME_TITLE,cueFile:HERE+'source-cues.json',protect:CFG.protect,page:CFG.page,v12:CFG.v12,sess,cues:opts.cues,prev:opts.prev,segName:opts.segName,
   prevOut:opts.prev?WORK+'/'+opts.prev:null,
   recordMotion:m=>motions.push({...m,start:m.start-start,end:m.end-start}),
   waitFor:async(fn,timeout=12000)=>{const a=Date.now();while(!(await serial(()=>p.evaluate(fn)))){if(Date.now()-a>timeout)throw Error('Expected page state did not appear');await sleep(100);}},
   snapshot:async()=>serial(()=>sess.cur.snapshot()),
   begin:async()=>{await serial(()=>p.evaluate(()=>{window.__ptrStat={held:0,heldAfterFinish:0,applied:0};}));
    // 리허설도 시작 화면 한 장은 실제 프레임으로 받아 둔다(first-frame.jpg — 첫 프레임의 흔적 · 언어 · 막대를 눈으로 볼 수 있게).
    if(opts.rehearsal&&!opts.capture){await fs.writeFile(out+'/first-frame.jpg',await grabFrame(sess));recording=true;start=Date.now();if(opts.lead!=null)speechFree=actionFree=Date.now()-opts.lead;await fs.writeFile(out+'/recording-start.json',JSON.stringify({start,rehearsal:true,url:await serial(()=>sess.cur.url())}));return;}
    const pg=sess.cur;await serial(async()=>{await pg.events();recording=true;});   // 앞 구간 끝에 남은 프레임은 버린다
    await serial(()=>pg.cdp('Page.startScreencast',SC));const t=Date.now();while(!frames.length){if(error)throw Error(error);if(Date.now()-t>12000)throw Error('Initial recording frame missing');await sleep(30);}
    if(opts.lead!=null){speechFree=actionFree=Date.now()-opts.lead;}
    await fs.writeFile(out+'/recording-start.json',JSON.stringify({start,url:await serial(()=>pg.url())}));},
   // 탭 바꾸기: 앞 탭의 screencast를 멈추고 남은 프레임을 버린 뒤, 새 탭을 앞에 놓고(크기를 처음 한 번 걸고) 녹화 중이면 그 탭에서 다시 받는다.
   front:async pg=>{await serial(async()=>{const old=sess.cur;if(old!==pg){if(recording)await old.cdp('Page.stopScreencast').catch(()=>{});await old.events().catch(()=>{});}
    // 탭을 바꾸면 ego가 화면 크기 지정을 풀 때가 있다(리허설 r16: 가이드 탭 높이 727px) — 앞에 놓을 때마다 같은 값으로 다시 건다.
    await pg.cdp('Page.bringToFront');await size(sess,pg);await korean(pg).catch(()=>{});await pg.events().catch(()=>{});sess.cur=pg;if(recording&&old!==pg&&(!opts.rehearsal||opts.capture))await pg.cdp('Page.startScreencast',SC);});},
   restartCapture:async()=>{if(opts.rehearsal&&!opts.capture)return;const pg=sess.cur;await serial(async()=>{await pg.cdp('Page.stopScreencast').catch(()=>{});await pg.cdp('Page.startScreencast',SC);});},
   openPage:async(name,url)=>{if(sess.pages.has(name))throw Error('Page already open: '+name);const pg=await serial(()=>sess.task.newPage());sess.pages.set(name,pg);await serial(()=>size(sess,pg));await serial(()=>korean(pg)).catch(()=>{});await serial(()=>pg.goto(url));return pg;},
   pageNamed:name=>sess.pages.get(name)||null,
  };
  ctx.say=async(id,fn,opt)=>{if(opts.rehearsal){const text=opts.cueText.get(id);if(text==null)throw Error('Cue not in the cue file: '+id);await cue(ctx,{id,text,duration_ms:Math.round(await speechMs(text)*(opts.capture?1:REHEARSAL_SCALE))},fn,opt);return;}
   const f=AUDIO+'/'+id+'.json';const c=JSON.parse(await fs.readFile(f,'utf8').catch(()=>{throw Error('Voice cue missing: '+f+' (생성 후 촬영)');}));
   if(opts.cueText&&opts.cueText.has(id)&&opts.cueText.get(id)!==c.text)throw Error('Voice text differs from the cue file: '+id+' (voice.py source-cues-v12.json → 음성쉼.py)');
   // 쉼을 넓힌 음성은 point(마지막 문장 시작)를 새 길이로 옮겨 적는다(음성쉼.py) — 그 값을 쓴다.
   if(c.point!=null&&ctx.cue?.id===id){if(opt&&opt.pointFrac===ctx.cue.point)opt.pointFrac=c.point;ctx.cue={...ctx.cue,point:c.point};}
   await cue(ctx,c,fn,opt);};
  result=await body(ctx);
  if(pending)await pending;
  if(opts.tail!=null){const w=Math.max(speechFree,actionFree)+opts.tail-Date.now();if(w>0)await sleep(w);}
  else{const tail=speechFree-Date.now();if(tail>0)await sleep(tail+400);}
 }catch(e){error=String(e?.stack||e);}
 finally{
  recording=false;done=true;await capture;const duration=start===null?0:Date.now()-start;await writeQueue;
  if(!opts.rehearsal||opts.capture)try{await sess.cur.cdp('Page.stopScreencast');}catch(e){}
  const clicks=[];for(const [name,pg] of [['notion',p],...sess.pages])clicks.push(...(await pg.evaluate(()=>window.__tutorialClicks||[]).catch(()=>[])).map(x=>({...x,page:name})));
  const state={url:await sess.cur.url().catch(()=>null),notionUrl:await p.url().catch(()=>null),clicks,pointer:await p.evaluate(()=>window.__ptrStat||null).catch(()=>null)};
  await fs.writeFile(out+'/end-state.json',JSON.stringify(state,null,2));
  await fs.writeFile(out+'/end-snapshot.txt',await sess.cur.snapshot().catch(e=>String(e)));
  await fs.writeFile(out+'/timing.json',JSON.stringify({start,frames,actions,motions,duration,error,result,banners},null,2));
  if(sess.qlog){await fs.writeFile(out+'/queue.json',JSON.stringify(sess.qlog.map(([l,q,s,e])=>[l,q-start,s-q,e-s])));sess.qlog=[];}
  const measure=start===null||(opts.rehearsal&&!opts.capture)?{moves:motions.length,maxGap:null,over100:[],gaps500:0}:measureGaps(frames,motions,start);
  return {duration,frames:frames.length,cues:actions.length,error,result,url:state.url,banners,measure};
 }
}

// 이어 찍기 준비(녹화 전, 화면에 남지 않음): 앞 구간이 끝난 Notion 페이지가 아니면 그 페이지를 열고, 업데이트 막대가 있으면 멈추고, 화살표를 그 자리에 둔다.
async function resume(ctx,{resumeUrl,pointer}){
 const {p,serial,sleep}=ctx;
 if(resumeUrl&&/notion\.(com|so)/.test(resumeUrl)){const want=new URL(resumeUrl).pathname.split('-').pop();if(!(await serial(()=>p.url())).includes(want)){await serial(()=>p.goto(resumeUrl,{timeout:150000,waitUntil:'domcontentloaded'}));// 쪽이면 제목 칸, 「홈」(제목 칸 없음 — k5가 여기서 90초 멈췄다)이면 왼쪽 목록이 뜰 때까지 기다린다.
   await serial(()=>p.waitForFunction(()=>!!document.querySelector('h1[contenteditable=true]')||(document.title.startsWith('홈 |')&&!!document.querySelector('[role=treeitem]')),undefined,{timeout:90000}));await sleep(1500);}}
 // Notion이 새 버전을 배포하면 새로고침 전까지 상단에 「최신 버전으로 업데이트」 막대가 남는다(2026-10-23 n25~n39 전부 찍힘). 열린 대화상자를 잃지 않게
 // 자동 새로고침하지 않고 녹화 전에 멈춘다 — 상태 경계에서 run.sh restore reload 뒤 다시.
 if(await serial(()=>p.evaluate(()=>document.body.innerText.includes('최신 버전으로 업데이트'))))throw Error('Notion update banner on screen before recording: ./run.sh restore reload');
 // 페이지를 새로 열었으면 화살표가 없으므로 ui.mjs의 설치 함수로 그 자리에 다시 그린다.
 if(pointer){const q=pointer;const {installPointerInPage}=await import('file:///'+HERE+'ui.mjs?'+Date.now());
  await serial(()=>p.evaluate(installPointerInPage,q));await serial(()=>p.evaluate(q=>{const e=document.getElementById('recording-pointer');if(window.__glide?.cancel)window.__glide.cancel();window.__glide=null;e.style.transform=`translate(${q.x}px,${q.y}px)`;},q));await serial(()=>p.mouse.move(q.x,q.y,{steps:1}));}
}

// opts: {name, module(segs/ 기준 파일명), pointer:{x,y}|null(앞 구간 끝 포인터), resumeUrl}
export async function run(opts){
 const sess=await session(CFG.space);
 const r=await record(sess,opts,async ctx=>{await resume(ctx,opts);const mod=await import('file:///'+HERE+'segs/'+opts.module+'?'+Date.now());return mod.default(ctx);});
 return {duration:r.duration,frames:r.frames,cues:r.cues,error:r.error,result:r.result,url:r.url};
}

// opts: {prefix(take 이름 앞), from(시작 구간 이름, 예 'v12-07' — 없으면 처음부터), prev(앞 구간 take 이름 — from을 주면 필수)}
// take 이름은 take-<prefix>-<구간 이름>. 결과 줄은 <work>/chain-<prefix>.jsonl에도 쌓인다.
// 말도 없고 화면도 그대로인 가장 긴 연속 시간(ms)과 그 시작 시각. 프레임은 화면이 바뀔 때만 오므로, 이웃 프레임 사이에서 말하는 구간을 뺀 시간이다.
export function stillOf(t){const fr=t.frames.map(f=>f.time).sort((a,b)=>a-b);fr.push(t.duration);const sp=t.actions.map(a=>[a.time,a.time+a.duration]);let still={ms:0,at:null};
 for(let k=1;k<fr.length;k++){const a=fr[k-1],b=fr[k];if(b-a<=3000)continue;
  const cuts=sp.filter(([x,y])=>y>a&&x<b).sort((p,q)=>p[0]-q[0]);let cur=a,best=0,bestAt=a;for(const [x,y] of cuts){if(x>cur&&x-cur>best){best=x-cur;bestAt=cur;}cur=Math.max(cur,y);}if(b>cur&&b-cur>best){best=b-cur;bestAt=cur;}
  if(best>still.ms)still={ms:Math.round(best),at:Math.round(bestAt)};}
 return still;}

export async function chain({prefix,from=null,prev=null,rehearsal=false,capture=[],until=null,retake=[],why=''}){
 const {preflight}=await import('file:///'+HERE+'preflight12.mjs?'+Date.now());
 const plan=await preflight({audio:!rehearsal});
 let list=plan.segments;
 if(from){const i=list.findIndex(s=>s.id===from);if(i<0)throw Error('Unknown v12 segment '+from+' (있는 것: '+list.map(s=>s.id).join(' ')+')');list=list.slice(i);
  if(i>0&&!prev)throw Error('Resuming at '+from+' needs the previous take name: ./run.sh chain12 <prefix> '+from+' <앞 구간 take>');}
 if(until){const j=list.findIndex(s=>s.id===until);if(j<0)throw Error('Unknown or earlier UNTIL segment '+until);list=list.slice(0,j+1);}
 // 통과한 구간은 다시 찍지 않는다(사용자가 세 번 지적: 실패할 때마다 1단계부터 다시 찍음). 녹화 묶음(<work>/v12-set.txt의 접두어들)의 chain 결과에서
 // 통과한 구간이 이번 차례에 들어 있으면 멈춘다. 정말 다시 찍을 때만 RETAKE=v12-NN과 RETAKE_WHY="까닭"을 주고, 그 까닭을 retakes.jsonl에 남긴다.
 if(!rehearsal){const setF=WORK+'/v12-set.txt';const set=(await fs.readFile(setF,'utf8').catch(()=>'')).split(/\r?\n/).filter(Boolean);
  const passed=new Map();for(const p of set){for(const l of (await fs.readFile(WORK+'/chain-'+p+'.jsonl','utf8').catch(()=>'')).split('\n').filter(Boolean)){const r=JSON.parse(l);if(!r.stop)passed.set(r.segment,p);}}
  const again=list.filter(s=>passed.has(s.id)&&!retake.includes(s.id));
  if(again.length)throw Error('통과한 구간: '+again.map(s=>s.id+'('+passed.get(s.id)+')').join(', ')+' — FROM=<실패 구간>으로 이어 찍는다 (다시 찍으려면 RETAKE=<구간> RETAKE_WHY="까닭")');
  const re=list.filter(s=>retake.includes(s.id));if(re.length){if(!why.trim())throw Error('RETAKE에는 RETAKE_WHY(다시 찍는 까닭 한 줄)가 있어야 한다');
   await fs.appendFile(WORK+'/retakes.jsonl',JSON.stringify({prefix,segments:re.map(s=>s.id),why,at:new Date().toISOString()})+'\n');}
  if(!set.includes(prefix))await fs.appendFile(setF,prefix+'\n');}
 let resumeOpts={};
 if(prev){const t=JSON.parse(await fs.readFile(WORK+'/'+prev+'/timing.json','utf8')),st=JSON.parse(await fs.readFile(WORK+'/'+prev+'/end-state.json','utf8'));
  if(t.error)throw Error('Previous take '+prev+' ended with an error — 그 구간부터 다시 찍는다');const m=t.motions.at(-1);resumeOpts={resumeUrl:st.notionUrl||st.url,pointer:m?{x:m.x,y:m.y}:null};}
 const {playSegment}=await import('file:///'+HERE+'lib/ui-v12.mjs?'+Date.now());
 const sess=await session(CFG.v12?.space||CFG.space);
 // 시작 검사(리허설 · 녹화 모두): ego 확대 100%(사용자 2026-11-12 결정)와 프레임 크기를 실제 화면으로 잰다. 다르면 멈춘다. 그 프레임을 첫 화면으로 남긴다.
 const {liveCheck}=await import('file:///'+HERE+'preflight12.mjs?'+Date.now());
 const frame=await grabFrame(sess);await fs.writeFile(WORK+'/'+prefix+'-첫화면.jpg',frame);
 await liveCheck({metrics:await sess.serial(()=>sess.p.evaluate(()=>({iw:innerWidth,ih:innerHeight,dpr:devicePixelRatio}))),frame:jpegSize(frame),viewport:CFG.viewport});
 // 녹화에서만: 왼쪽 목록에 리허설 쪽이 남아 있으면 멈춘다(사이드바를 읽으려고 앱이 아니면 v12.home을 녹화 밖에서 연다).
 if(!rehearsal){if(!/app\.notion/.test(await sess.serial(()=>sess.p.url()))){await sess.serial(()=>sess.p.goto(CFG.v12.home,{timeout:150000,waitUntil:'domcontentloaded'}));await sess.serial(()=>sess.p.waitForSelector('[role=treeitem]',{timeout:90000}));}
  const {sidebarLeftovers}=await import('file:///'+HERE+'preflight12.mjs?'+Date.now());const left=await sess.serial(()=>sess.p.evaluate(sidebarLeftovers));
  if(left.length)throw Error('왼쪽 목록에 리허설 쪽이 남아 있어 녹화하지 않는다: '+left.join(', ')+' — 녹화 전에 정리한다(preflight12.mjs sidebarLeftovers)');}
 const takes=[];let prevName=prev;
 for(const [i,s] of list.entries()){
  const name=(rehearsal?'rehearsal-':'take-')+prefix+'-'+s.id;const first=i===0;
  const r=await record(sess,{name,segName:s.id,cues:plan.cues,cueText:plan.text,lead:first&&!prev?null:200,tail:200,watchBanner:true,prev:prevName,rehearsal,capture:rehearsal&&capture.includes(s.id)},
   async ctx=>{if(first&&prev)await resume(ctx,resumeOpts);return playSegment(ctx,s.mod);});
  // 말 없이 화면만 굴러간 시간: 앞 큐 말이 끝난 뒤 다음 큐 말까지에서 정한 쉼(pause_before)을 뺀 몫. 4초를 넘으면 멈춘다(사용자 2026-11-13 — 2.6초쯤은 사람 강사도 하는 일이라 허용).
  // 2.5~4초는 결과 줄 silentMax에 후보로만 남는다(녹화만 — 리허설은 말 길이가 어림이다).
  // 리허설이 못 잡은 결함: k1 s02-10 커버 고르기 뒤 말 없이 8.8초 스크롤(사용자가 싫다고 한 「오래 멈춘 화면」과 같은 꼴).
  let silent={ms:0,cue:null};if(!rehearsal&&!r.error){const t=JSON.parse(await fs.readFile(WORK+'/'+name+'/timing.json','utf8'));const pb=new Map(plan.cues.map(c=>[c.id,c.pause_before]));
   for(let k=1;k<t.actions.length;k++){const a=t.actions[k-1],b=t.actions[k];const ms=b.time-(a.time+a.duration)-(pb.get(b.id)??0);if(ms>silent.ms)silent={ms,cue:a.id};}}
  // 멈추는 정지: 말도 없고 화면도 그대로인 시간이 3초를 넘는 곳(학생이 따라 하기를 기다려 주는 꼴 — 사용자 2026-11-13 「다 멈추고 그대로 따라하기를
  // 기다려 주는 시간 같은 것만 필요 없다」). 프레임은 화면이 바뀔 때만 오므로 이웃 프레임 사이에서 말하는 구간을 뺀 연속 시간으로 잰다.
  // 말 없이 화면이 움직이는 시간(silentMax)과 0.5초 끊김(gaps500)은 기록만 하고 멈추지 않는다.
  const still=!rehearsal&&!r.error?stillOf(JSON.parse(await fs.readFile(WORK+'/'+name+'/timing.json','utf8'))):{ms:0,at:null};
  const stop=r.error?'error':r.banners.length?'banner':still.ms>3000?'still':null;
  const row={name,segment:s.id,steps:s.steps,duration_s:Math.round(r.duration/100)/10,cues:r.cues,error:r.error?String(r.error).slice(0,400):null,banners:r.banners,maxGap:r.measure.maxGap,gaps500:r.measure.gaps500,silentMax:silent,stillMax:still,stop};
  takes.push(row);await fs.appendFile(WORK+'/'+(rehearsal?'rehearsal-':'chain-')+prefix+'.jsonl',JSON.stringify(row)+'\n');
  if(stop)return {stopped:s.id,reason:stop,resume:'./run.sh '+(rehearsal?'rehearse12':'chain12')+' <새 접두어> '+s.id+(prevName?' '+prevName:''),takes};
  prevName=name;
 }
 return {done:true,takes};
}
