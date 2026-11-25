// VS Code 웹(serve-web) 녹화 제어기. 한 번 실행에 구간 모듈 하나를 녹화한다(기능 구간별 분할 촬영). run.sh rec · dry가 부른다.
// 브라우저: page.mjs가 녹화 브라우저(run.sh up이 띄운 헤드리스 Chromium)에 붙어 준 페이지. opts.pageIndex = 그 브라우저의 몇 번째 페이지인가(0 웹 VS Code, 1 랩 결과 화면), opts.page = 이미 가진 Playwright 페이지(draw_check.mjs의 흉내 화면).
// 리듬: 행동 문장 안에서 가리키고 문장 끝 약 250ms 전에 실행(gate), 결과 발화는 행동 종료 뒤. 페이지로 보내는 모든 호출은 한 직렬 큐.
// 출력: <work>/<name>/frames/*.jpg · timing.json(프레임·큐·이동·강조 highlights·펜 그림과 글상자 drawings) · end-state.json(URL·클릭) · end-text.txt(끝 화면 글 — 바깥 문서와 Codex 웹뷰)
// 화면 위 그림 층(강조 · 펜 그림 · 글상자, draw.mjs): 구간마다 빈 층에서 시작하고(ctx.draw), 남은 강조는 구간의 마지막 말이 끝날 때 지운다.
// 구간 모듈이 끝났는데 펜 그림이나 글상자가 떠 있으면 멈춘다(다음 구간은 빈 층에서 시작해 이음새에서 그림이 튄다) — 리허설도 같다.
const fs=await import('node:fs/promises');
const HERE=decodeURIComponent(new URL('.',import.meta.url).pathname).replace(/^\/([A-Za-z]:)/,'$1');
const CFG=JSON.parse(await fs.readFile(HERE+'config.json','utf8'));
const abs=r=>new URL(r,'file:///'+HERE).pathname.replace(/^\/([A-Za-z]:)/,'$1').replace(/\/$/,'');
const WORK=decodeURIComponent(abs(CFG.work)),AUDIO=decodeURIComponent(abs(CFG.audio));
const {openPage,wrap,folderUrl,NAV}=await import(new URL('page.mjs',import.meta.url).href);
// 페이지와 화면 값. 화면 값은 config.json viewport(CSS 크기 × 배율)이고, VS Code 밖 화면을 다른 크기로 찍을 때만 opts.viewport({width,height,dsf})로 바꾼다.
const pageOf=async opts=>opts.page?{p:await wrap(opts.page),close:async()=>{}}:openPage(opts.pageIndex??0);
const metrics=(p,opts)=>{const v=opts.viewport||CFG.viewport;return p.cdp('Emulation.setDeviceMetricsOverride',{width:v.width,height:v.height,deviceScaleFactor:v.deviceScaleFactor??v.dsf??1,mobile:false});};

function jpegSize(b){let i=2;while(i<b.length){if(b[i]!==255){i++;continue;}const marker=b[i+1];i+=2;if(marker===216||marker===217)continue;const len=b.readUInt16BE(i);if([192,193,194].includes(marker))return {width:b.readUInt16BE(i+5),height:b.readUInt16BE(i+3)};i+=len;}throw Error('JPEG dimensions missing');}
const ACT=/(누르|눌러|누를|클릭|선택|입력|적을|적어|적겠|닫는|닫을|열겠|엔터|가져가)/;
// 행동 문장 = 조작 동사가 있는 마지막 문장. 시점은 글자 비율 추정(단어 시각 없음).
function plan(c){
 const s=c.text.split(/(?<=[.?!])\s+/);const total=c.text.length;let at=0;const spans=s.map(x=>{const a=at;at+=x.length+1;return{a,b:Math.min(total,at-1),x};});
 const k=[...spans].reverse().find(x=>ACT.test(x.x))||spans.at(-1);
 return{pointFrac:k.a/total,commitFrac:k.b/total,sentence:k.x};
}

// 리허설(run.sh dry): 녹화 · 프레임 저장 · 음성 대기 없이 구간 모듈의 조작을 녹화와 같은 화면 크기로 실제로 해 본다.
// 구간 모듈은 ctx.report에 조작마다 검사 결과(fail 포함)를 남긴다(segs/map-common.mjs). 결과 = <work>/<name>/dry.json.
// 첫 실패 조작에서 멈추는 오류(대상 없음 · 화면 밖 · 화면 크기 다름)와 기준을 넘은 값(fail)을 모두 실패로 돌려준다.
async function dryRun(opts,audio,out){
 await fs.mkdir(out,{recursive:true});
 const {p,close}=await pageOf(opts);await metrics(p,opts);
 let queue=Promise.resolve();const serial=fn=>{const r=queue.then(fn);queue=r.catch(()=>{});return r;};
 const sleep=ms=>new Promise(r=>setTimeout(r,ms));const report=[];let error=null,result=null;
 const {drawLayer}=await import('file:///'+HERE+'draw.mjs?'+Date.now());const t0=Date.now();
 const ctx={p,serial,sleep,fs,out,audio,rehearsal:true,report,commitAt:0,prev:null,recordMotion:()=>{},begin:async()=>{},
  waitFor:async(fn,timeout=12000)=>{const a=Date.now();while(!(await serial(()=>p.evaluate(fn)))){if(Date.now()-a>timeout)throw Error('Expected page state did not appear');await sleep(100);}},
  say:async(id,fn)=>{ctx.cueId=id;if(fn){ctx.commitAt=0;await fn();}}};
 ctx.draw=drawLayer({p,serial,sleep,clock:()=>Date.now()-t0,cue:()=>ctx.cueId});await ctx.draw.reset();
 // 녹화와 같은 조건: screencast를 돌려 프레임은 받는 즉시 ACK만 한다(저장 없음). screencast 없이 두면 도중에 화면 크기 설정이 풀렸다(리허설 d05-8, CSS 1280 → 864).
 let live=true;await serial(()=>p.cdp('Page.startScreencast',{format:'jpeg',quality:30,maxWidth:640,maxHeight:360,everyNthFrame:1}));
 const pump=(async()=>{while(live){for(const e of await serial(()=>p.events()))if(e.method==='Page.screencastFrame')serial(()=>p.cdp('Page.screencastFrameAck',{sessionId:e.params.sessionId})).catch(()=>{});await sleep(30);}})().catch(()=>{});
 try{const mod=await import((opts.moduleUrl||'file:///'+HERE+'segs/'+opts.module)+'?'+Date.now());result=await mod.default(ctx);
  const left=ctx.draw.left();if(left.length)throw Error('구간 끝에 '+left.join(' · ')+'이 떠 있음 — 구간 안에서 걷는다(hide · note(null))');
 }catch(e){error=String(e?.stack||e).slice(0,800);}
 await ctx.draw.reset().catch(()=>{});   // 리허설이 그린 것을 화면에 남기지 않는다
 live=false;await pump;await p.cdp('Page.stopScreencast');await close();
 const fails=report.filter(r=>r.fail);const num=(k,op)=>{const v=report.filter(r=>(!op||r.op===op)&&typeof r[k]==='number').map(r=>r[k]);return v.length?[Math.min(...v),Math.max(...v)]:null;};
 const sum={dry:true,ok:!error&&!fails.length,error,cues:[...new Set(report.map(r=>r.cue))].length,ops:report.length,
  found_inview:report.filter(r=>r.target).length,scrolled:report.filter(r=>r.scrolled).length,overlap_chars:num('overlap','point'),type_ms:num('ms','type'),wait_ms:num('ms','wait'),
  highlights:ctx.draw.marks.length,drawings:ctx.draw.log.length,
  failures:fails.map(r=>({cue:r.cue,op:r.op,why:r.why})),view:result?.view??null};
 await fs.writeFile(out+'/dry.json',JSON.stringify({...sum,report},null,2));
 return sum;
}

// opts: {name, module(segs/ 기준 파일명), pointer:{x,y}|null(앞 구간 끝 포인터)}
export async function run(opts){
 const work=opts.work||WORK,audio=opts.audio||AUDIO;
 const out=work+'/'+opts.name;
 if(opts.dry)return dryRun(opts,audio,out);
 await fs.mkdir(out+'/frames',{recursive:true});
 if((await fs.readdir(out+'/frames')).length)throw Error('Output folder already has frames: '+out);
 const {p,close}=await pageOf(opts);await metrics(p,opts);
 let queue=Promise.resolve();const serial=fn=>{const r=queue.then(fn);queue=r.catch(()=>{});return r;};
 const sleep=ms=>new Promise(r=>setTimeout(r,ms));
 let recording=false,done=false,error=null,writeQueue=Promise.resolve(),bufferBytes=0,start=null;const frames=[],actions=[],motions=[];
 const capture=(async()=>{while(!done){
  const evs=await serial(()=>p.events());
  for(const e of evs)if(e.method==='Page.screencastFrame'){
   serial(()=>p.cdp('Page.screencastFrameAck',{sessionId:e.params.sessionId})).catch(x=>{error=String(x);});
   if(!recording)continue;const b=Buffer.from(e.params.data,'base64');const d=jpegSize(b);
   if(d.width!==1920||d.height!==1080){if(start===null)continue;throw Error('Capture dimensions '+JSON.stringify(d));}
   if(start===null)start=Date.now();
   const f={file:'frames/'+String(frames.length).padStart(6,'0')+'.jpg',time:Date.now()-start,sourceTimestamp:e.params.metadata.timestamp};frames.push(f);bufferBytes+=b.length;
   if(bufferBytes>64*1024*1024)throw Error('Capture disk queue exceeded 64MiB');
   writeQueue=writeQueue.then(async()=>{await fs.writeFile(out+'/'+f.file,b);await fs.appendFile(out+'/frames.jsonl',JSON.stringify(f)+'\n');bufferBytes-=b.length;});
  }
  await sleep(8);
 }})().catch(e=>{error=String(e);done=true;});
 let speechFree=0,actionFree=0,pending=null;
 async function cue(ctx,c,fn,opt={}){
  if(error)throw Error(error);
  if(!recording||start===null)throw Error('Cue '+c.id+' before recording began (call c.begin() first)');
  if(await fs.stat(work+'/STOP').then(()=>true).catch(()=>false))throw Error('Stop requested');
  if(!opt.overlap&&pending){await pending;pending=null;}
  // 큐 사이 기본 쉼 1300ms = 영상 V-14(큐와 큐 사이 1.3초). 조작 직후 같은 문맥의 말은 opt.gap으로 짧게 준다.
  const w=Math.max(speechFree,opt.overlap?0:actionFree)+(opt.gap??1300)-Date.now();if(w>0)await sleep(w);
  const t0=Date.now();const a={id:c.id,text:c.text,time:t0-start,duration:c.duration_ms};actions.push(a);
  speechFree=t0+c.duration_ms;
  if(!fn){actionFree=Math.max(actionFree,t0);return;}
  // opt.at = 대사 속 구절: 그 구절이 끝나는 시점에 첫 클릭·입력(여러 조작 중 첫 동작이 앞 문장에 있을 때). 없으면 오류.
  const pl=plan(c);if(opt.at!=null){const i=c.text.indexOf(opt.at);if(i<0)throw Error(`${c.id}: at 구절 없음 — ${opt.at}`);Object.assign(pl,{pointFrac:Math.max(0,(i-1)/c.text.length),commitFrac:(i+opt.at.length)/c.text.length,sentence:opt.at});}const pointAt=t0+Math.round(c.duration_ms*(opt.pointFrac??pl.pointFrac))+(opt.pointDelay??250);
  const commitAt=t0+Math.round(c.duration_ms*(opt.commitFrac??pl.commitFrac))-(opt.commitLead??250);
  Object.assign(a,{plannedPoint:pointAt-start,plannedCommit:commitAt-start,actionSentence:pl.sentence,estimate:'character-proportional'});
  const go=(async()=>{const w2=pointAt-Date.now();if(w2>0)await sleep(w2);ctx.commitAt=commitAt;ctx.committed=null;a.actionStart=Date.now()-start;
   await fn();a.commit=ctx.committed?ctx.committed-start:null;a.actionEnd=Date.now()-start;actionFree=Date.now();})();
  if(opt.async){pending=go;return;}
  await go;
 }
 let result=null,draw=null;
 try{
  const ctx={p,serial,sleep,fs,out,audio,
   recordMotion:m=>motions.push({...m,start:m.start-start,end:m.end-start}),
   waitFor:async(fn,timeout=12000)=>{const a=Date.now();while(!(await serial(()=>p.evaluate(fn)))){if(Date.now()-a>timeout)throw Error('Expected page state did not appear');await sleep(100);}},
   begin:async()=>{await serial(()=>p.evaluate(()=>{window.__ptrStat={held:0,heldAfterFinish:0,applied:0};}));recording=true;await serial(()=>p.cdp('Page.startScreencast',{format:'jpeg',quality:85,maxWidth:1920,maxHeight:1080,everyNthFrame:1}));const t=Date.now();while(!frames.length){if(error)throw Error(error);if(Date.now()-t>12000)throw Error('Initial recording frame missing');await sleep(30);}await fs.writeFile(out+'/recording-start.json',JSON.stringify({start,url:p.url().replace(/tkn=[^&]+/,'tkn=REDACTED')}));},
  };
  // 앞 take가 남긴 화면 상태(구간 모듈이 돌려준 result). 녹화 밖에서 그 상태(굴린 자리 등)로 되돌릴 때 쓴다. 앞 take를 주었는데 기록이 없으면 멈춘다.
  ctx.prev=opts.prev?JSON.parse(await fs.readFile(work+'/'+opts.prev+'/timing.json','utf8').catch(()=>{throw Error('앞 take 기록 없음: '+work+'/'+opts.prev+'/timing.json (촬영도구/ctrl.mjs)');})).result:null;
  // 화면 위 그림 층: 앞 take가 남긴 것을 녹화 전에 지우고 빈 층에서 시작한다.
  const {drawLayer}=await import('file:///'+HERE+'draw.mjs?'+Date.now());
  draw=ctx.draw=drawLayer({p,serial,sleep,clock:()=>Date.now()-start,cue:()=>ctx.cueId});await draw.reset();
  ctx.say=async(id,fn,opt)=>{ctx.cueId=id;const f=audio+'/'+id+'.json';const c=JSON.parse(await fs.readFile(f,'utf8').catch(()=>{throw Error('Voice cue missing: '+f+' (생성 후 촬영)');}));await cue(ctx,c,fn,opt);};
  // 이어 찍기: 페이지가 앞 구간이 끝난 주소가 아니면 녹화 전에 그 주소를 연다(화면에 남지 않음). 웹 VS Code 주소는 page.mjs folderUrl이 접속 토큰을 붙여 만든다.
  if(opts.resumeUrl&&!p.url().startsWith(opts.resumeUrl.split('?')[0])){const folder=new URL(opts.resumeUrl).searchParams.get('folder');
   if(folder){const u=await folderUrl(folder.replace(/^\//,''));await serial(()=>p.goto(u,NAV));await serial(()=>p.waitForSelector('.monaco-workbench',{state:'visible',timeout:60000}));await sleep(4000);}
   else await serial(()=>p.goto(opts.resumeUrl,{timeout:60000}));}
  // 이어 찍기: 앞 구간 끝 포인터 위치에 표시 · 실제 포인터를 둔다(녹화 전, 화면에 남지 않음).
  // 페이지를 새로 열었으면 화살표가 없으므로 ui.mjs의 설치 함수로 그 자리에 다시 그린다.
  if(opts.pointer){const q=opts.pointer;const {installPointerInPage}=await import('file:///'+HERE+'ui.mjs?'+Date.now());
   await serial(()=>p.evaluate(installPointerInPage,q));await serial(()=>p.evaluate(q=>{const e=document.getElementById('recording-pointer');if(window.__glide?.cancel)window.__glide.cancel();window.__glide=null;e.style.transform=`translate(${q.x}px,${q.y}px)`;},q));await serial(()=>p.mouse.move(q.x,q.y,{steps:1}));}
  const mod=await import((opts.moduleUrl||'file:///'+HERE+'segs/'+opts.module)+'?'+Date.now());
  result=await mod.default(ctx);
  if(pending)await pending;
  const left=draw.left();if(left.length)throw Error('구간 끝에 '+left.join(' · ')+'이 떠 있음 — 구간 안에서 걷는다(hide · note(null))');
  // 남은 강조는 마지막 말이 끝날 때 지운다(그 뒤 꼬리 400ms 동안 지워진 화면이 찍힌다).
  const tail=speechFree-Date.now();if(tail>0)await sleep(tail);await draw.end('구간 끝');if(tail>0)await sleep(400);
 }catch(e){error=String(e?.stack||e);}
 finally{
  if(draw)await draw.end(error?'녹화 끝':'구간 끝').catch(()=>{});   // 오류로 끝난 take의 강조도 끝 시각을 남기고 화면에서 지운다
  recording=false;done=true;await capture;const duration=start===null?0:Date.now()-start;await writeQueue;
  // 끝 상태를 읽지 못하면(페이지가 닫힘 등) 그 까닭을 녹화 오류로 남긴다
  const state={url:p.url().replace(/tkn=[^&]+/,'tkn=REDACTED'),clicks:[],pointer:null};
  try{await p.cdp('Page.stopScreencast');state.clicks=await p.evaluate(()=>window.__tutorialClicks||[]);state.pointer=await p.evaluate(()=>window.__ptrStat||null);await fs.writeFile(out+'/end-text.txt',await p.text());}
  catch(e){error??='끝 상태 읽기 실패: '+String(e?.message??e);}
  await fs.writeFile(out+'/end-state.json',JSON.stringify(state,null,2));
  await fs.writeFile(out+'/timing.json',JSON.stringify({start,frames,actions,motions,highlights:draw?.marks??[],drawings:draw?.log??[],duration,error,result},null,2));
  await close().catch(e=>{error??='녹화 브라우저에서 떨어지지 못함: '+String(e?.message??e);});
  return {duration,frames:frames.length,cues:actions.length,error,result,url:state.url};
 }
}
