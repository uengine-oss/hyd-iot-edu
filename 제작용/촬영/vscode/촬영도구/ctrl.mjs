// VS Code 웹(serve-web) 녹화 제어기 — Notion v10 제어기를 복사해 Notion 전용 검사만 뺐다. 한 번 실행에 구간 모듈 하나를 녹화한다(기능 구간별 분할 촬영). run.sh rec가 부른다.
// 리듬: 행동 문장 안에서 가리키고 문장 끝 약 250ms 전에 실행(gate), 결과 발화는 행동 종료 뒤. 모든 ego 호출은 한 직렬 큐.
// 출력: <work>/<name>/frames/*.jpg · timing.json(프레임·큐·이동) · end-state.json(URL·클릭) · end-snapshot.txt
const fs=await import('node:fs/promises');
const HERE=decodeURIComponent(new URL('.',import.meta.url).pathname).replace(/^\/([A-Za-z]:)/,'$1');
const CFG=JSON.parse(await fs.readFile(HERE+'config.json','utf8'));
const abs=r=>new URL(r,'file:///'+HERE).pathname.replace(/^\/([A-Za-z]:)/,'$1').replace(/\/$/,'');
const WORK=decodeURIComponent(abs(CFG.work)),AUDIO=decodeURIComponent(abs(CFG.audio));

function jpegSize(b){let i=2;while(i<b.length){if(b[i]!==255){i++;continue;}const marker=b[i+1];i+=2;if(marker===216||marker===217)continue;const len=b.readUInt16BE(i);if([192,193,194].includes(marker))return {width:b.readUInt16BE(i+5),height:b.readUInt16BE(i+3)};i+=len;}throw Error('JPEG dimensions missing');}
const ACT=/(누르|눌러|누를|클릭|선택|입력|적을|적어|적겠|닫는|닫을|열겠|엔터|가져가)/;
// 행동 문장 = 조작 동사가 있는 마지막 문장. 시점은 글자 비율 추정(단어 시각 없음).
function plan(c){
 const s=c.text.split(/(?<=[.?!])\s+/);const total=c.text.length;let at=0;const spans=s.map(x=>{const a=at;at+=x.length+1;return{a,b:Math.min(total,at-1),x};});
 const k=[...spans].reverse().find(x=>ACT.test(x.x))||spans.at(-1);
 return{pointFrac:k.a/total,commitFrac:k.b/total,sentence:k.x};
}

// opts: {name, module(segs/ 기준 파일명), pointer:{x,y}|null(앞 구간 끝 포인터)}
export async function run(opts){
 const out=WORK+'/'+opts.name;
 await fs.mkdir(out+'/frames',{recursive:true});
 if((await fs.readdir(out+'/frames')).length)throw Error('Output folder already has frames: '+out);
 // opts.space·opts.viewport: VS Code 밖 화면(포털)을 다른 작업 공간에서 찍을 때. 포털은 1536x864 dsf1.5(→2304x1296 렌더 → 1920x1080 프레임).
 const task=await taskSpace(opts.space||CFG.space);const p=task.page('p1');const VP=opts.viewport||CFG.viewport;
 await p.cdp('Emulation.setDeviceMetricsOverride',{width:VP.width,height:VP.height,deviceScaleFactor:VP.dsf||1,mobile:false});
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
  if(await fs.stat(WORK+'/STOP').then(()=>true).catch(()=>false))throw Error('Stop requested');
  if(!opt.overlap&&pending){await pending;pending=null;}
  const w=Math.max(speechFree,opt.overlap?0:actionFree)+(opt.gap??250)-Date.now();if(w>0)await sleep(w);
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
 let result=null;
 try{
  const ctx={p,serial,sleep,fs,out,cueFile:HERE+'source-cues.json',protect:CFG.protect,page:CFG.page,
   recordMotion:m=>motions.push({...m,start:m.start-start,end:m.end-start}),
   waitFor:async(fn,timeout=12000)=>{const a=Date.now();while(!(await serial(()=>p.evaluate(fn)))){if(Date.now()-a>timeout)throw Error('Expected page state did not appear');await sleep(100);}},
   snapshot:async()=>serial(()=>p.snapshot()),
   begin:async()=>{await serial(()=>p.evaluate(()=>{window.__ptrStat={held:0,heldAfterFinish:0,applied:0};}));recording=true;await serial(()=>p.cdp('Page.startScreencast',{format:'jpeg',quality:85,maxWidth:1920,maxHeight:1080,everyNthFrame:1}));const t=Date.now();while(!frames.length){if(error)throw Error(error);if(Date.now()-t>12000)throw Error('Initial recording frame missing');await sleep(30);}await fs.writeFile(out+'/recording-start.json',JSON.stringify({start,url:await serial(()=>p.url())}));},
  };
  ctx.say=async(id,fn,opt)=>{const f=AUDIO+'/'+id+'.json';const c=JSON.parse(await fs.readFile(f,'utf8').catch(()=>{throw Error('Voice cue missing: '+f+' (생성 후 촬영)');}));await cue(ctx,c,fn,opt);};
  // 이어 찍기: 앞 구간 끝 포인터 위치에 표시·실제 포인터를 둔다(녹화 전, 화면에 남지 않음).
  // 이어 찍기: 앞 구간이 끝난 페이지가 아니면 녹화 전에 그 페이지를 연다(화면에 남지 않음).
  // 이어 찍기: 앞 구간 끝 URL과 다르면 녹화 전에 그 주소를 연다(화면에 남지 않음). 토큰은 config.tokenFile에서 읽어 붙인다.
  if(opts.resumeUrl){if(!(await serial(()=>p.url())).startsWith(opts.resumeUrl.split('?')[0])){const tkn=(await fs.readFile(CFG.tokenFile,'utf8')).trim();await serial(()=>p.goto(opts.resumeUrl.replace('tkn=REDACTED','tkn='+tkn)));await serial(()=>p.waitForSelector('.monaco-workbench',{state:'visible',timeout:60000}));await sleep(4000);}}
  // 페이지를 새로 열었으면 화살표가 없으므로 ui.mjs의 설치 함수로 그 자리에 다시 그린다.
  if(opts.pointer){const q=opts.pointer;const {installPointerInPage}=await import('file:///'+HERE+'ui.mjs?'+Date.now());
   await serial(()=>p.evaluate(installPointerInPage,q));await serial(()=>p.evaluate(q=>{const e=document.getElementById('recording-pointer');if(window.__glide?.cancel)window.__glide.cancel();window.__glide=null;e.style.transform=`translate(${q.x}px,${q.y}px)`;},q));await serial(()=>p.mouse.move(q.x,q.y,{steps:1}));}
  const mod=await import('file:///'+HERE+'segs/'+opts.module+'?'+Date.now());
  result=await mod.default(ctx);
  if(pending)await pending;
  const tail=speechFree-Date.now();if(tail>0)await sleep(tail+400);
 }catch(e){error=String(e?.stack||e);}
 finally{
  recording=false;done=true;await capture;const duration=start===null?0:Date.now()-start;await writeQueue;
  try{await p.cdp('Page.stopScreencast');}catch(e){}
  const state={url:(await p.url().catch(()=>null))?.replace(/tkn=[0-9a-f]+/,'tkn=REDACTED'),clicks:await p.evaluate(()=>window.__tutorialClicks||[]).catch(()=>[]),pointer:await p.evaluate(()=>window.__ptrStat||null).catch(()=>null)};
  await fs.writeFile(out+'/end-state.json',JSON.stringify(state,null,2));
  await fs.writeFile(out+'/end-snapshot.txt',await p.snapshot().catch(e=>String(e)));
  await fs.writeFile(out+'/timing.json',JSON.stringify({start,frames,actions,motions,duration,error,result},null,2));
  return {duration,frames:frames.length,cues:actions.length,error,result,url:state.url};
 }
}
