// 끊지 않는 한 번 녹화(로컬 ego · 클라우드 Playwright). 구간 여러 개를 녹화 한 번으로 찍어 이음새가 생기지 않는다. encode.py가 그대로 합성한다.
// 실행: take.sh가 부른다 — ego는 ego-browser nodejs -e "…await take({...})", 리눅스는 node <실행 파일>(먼저 run.sh up). 브라우저 연결은 아래 openPage 한 곳.
//   mode:'rehearse'  소리 길이 0 · 녹화 없음으로 같은 조작을 한다. 통과한 큐마다 조작 표시를 rehearsal-<이름 앞부분>.json에 남긴다. 이어서 돌린 리허설도 합친다.
//   mode:'record'    모든 큐가 지금 조작 그대로 통과했을 때만 녹화한다. 큐 하나를 고치면 그 큐만 다시 리허설한다(대사만 바꾼 큐는 다시 돌지 않는다).
// 커서: 페이지에 그리지 않고 이동을 기록해 합성 때 그린다(ui.mjs virtualPointer). 클릭은 도착 뒤 대상을 다시 찾고 맨 위 요소인지 확인한 뒤 누른다.
// 실패 복구: resume:{prev,fromCue} — 페이지를 그대로 둔 채 그 큐부터 이어 찍는다. 앞 take는 그 큐 시작에서 잘라 쓴다(이음.json). 이음새검수.py가 두 화면이 같은지 잰다.
// 출력: <work>/<name>/frames · timing.json · end-state.json · pointer-start.json · frames.jsonl · 이음.json(이어 찍었을 때)
const fs=await import('node:fs/promises');
const {createHash}=await import('node:crypto');
const HERE=decodeURIComponent(new URL('.',import.meta.url).pathname).replace(/^\/([A-Za-z]:)/,'$1');
const CFG=JSON.parse(await fs.readFile(HERE+'config.json','utf8'));
const abs=r=>decodeURIComponent(new URL(r,'file:///'+HERE).pathname).replace(/^\/([A-Za-z]:)/,'$1').replace(/\/$/,'');
const WORK=abs(CFG.work);
const SPEECH_RATE=422/60000; // 음성 없는 시험의 문장 길이(글자/ms). ctrl.mjs ctx.silent와 같은 실측값.

const opsMark=c=>createHash('sha256').update(JSON.stringify(c.ops||[])).digest('hex').slice(0,16);
function jpegSize(b){let i=2;while(i<b.length){if(b[i]!==255){i++;continue;}const m=b[i+1];i+=2;if(m===216||m===217)continue;const len=b.readUInt16BE(i);if([192,193,194].includes(m))return{width:b.readUInt16BE(i+5),height:b.readUInt16BE(i+3)};i+=len;}throw Error('JPEG dimensions missing');}

// 앞 take에서 이을 지점: 그 큐를 시작하기 전(말이 없는 자리)과 그때의 커서 위치.
// 녹화가 도중에 꺼지면 timing.json이 없다. 큐마다 남긴 partial.json과 frames.jsonl로 다시 만든다.
async function loadTiming(name){
 const dir=WORK+'/'+name,done=await fs.readFile(dir+'/timing.json','utf8').catch(()=>null);
 if(done)return JSON.parse(done);
 const part=JSON.parse(await fs.readFile(dir+'/partial.json','utf8').catch(()=>{throw Error('이어 찍기 거부: '+name+'에 기록이 없다');}));
 const frames=(await fs.readFile(dir+'/frames.jsonl','utf8')).trim().split(String.fromCharCode(10)).map(l=>JSON.parse(l));
 const t={...part,frames,duration:frames.at(-1).time,error:'중단됨: 기록을 큐 단위로 복원',result:null};
 await fs.writeFile(dir+'/timing.json',JSON.stringify(t));
 await fs.writeFile(dir+'/end-state.json',JSON.stringify({url:null,tab:null,clicks:part.clicks.map(c=>({x:c.x,y:c.y,px:c.x,py:c.y}))}));
 return t;
}
async function resumePoint({prev,fromCue}){
 const t=await loadTiming(prev);
 const a=t.actions.find(x=>x.id===fromCue);
 const cut=a?a.time:Math.max(...t.actions.map(x=>x.time+x.duration));
 if(cut>t.duration)throw Error(`이어 찍기 거부: ${prev}의 마지막 말이 녹화 끝을 넘음 — ${fromCue}로 이을 수 없다`);
 const m=t.motions.filter(x=>x.glide+x.planned_ms<=cut).at(-1);
 const ps=JSON.parse(await fs.readFile(WORK+'/'+prev+'/pointer-start.json','utf8'));
 return{cut,pointer:m?{x:m.x,y:m.y}:{x:ps.x,y:ps.y}};
}

// 브라우저 연결만 둘로 갈린다. 아래 코드는 ego 페이지 모양(cdp · events · waitForFileChooser · mouse · evaluate)만 쓴다. 둘 다 CSS 1280x720 · 프레임 1920x1080이라 encode.py가 같은 값으로 화살표를 그린다.
//   ego(로컬 Windows, taskSpace가 있을 때): 작업 공간의 페이지. ego 150 %라 1920x1080 dsf1 → CSS 1280x720.
//   Playwright(클라우드 리눅스): browser.mjs가 띄워 둔 헤드리스 Chromium에 CDP로 붙는다 — 녹화가 실패해도 페이지가 남아 그 큐부터 이어 찍는다. config.json viewport(CSS 1280x720 × 1.5).
async function openPage(opts){
 if(typeof taskSpace==='function'){const p=(await taskSpace(opts.space)).page('p1');return{p,view:{width:1920,height:1080,deviceScaleFactor:1},close:async()=>{}};}
 const {createRequire}=await import('node:module');
 const {chromium}=createRequire(import.meta.url)(process.env.PLAYWRIGHT_MODULE||'/opt/node22/lib/node_modules/playwright');
 const browser=await chromium.connectOverCDP(`http://127.0.0.1:${CFG.cdp}`);
 const p=browser.contexts()[0]?.pages()[0];if(!p)throw Error('녹화 브라우저 페이지 없음(run.sh up 먼저)');
 const s=await p.context().newCDPSession(p),got=[];s.on('Page.screencastFrame',params=>got.push({method:'Page.screencastFrame',params}));
 const url=p.url.bind(p);
 Object.assign(p,{cdp:(m,a)=>s.send(m,a),events:()=>got.splice(0),waitForFileChooser:o=>p.waitForEvent('filechooser',o),url:async()=>url()});
 const v=CFG.viewport;
 return{p,view:{width:v.width,height:v.height,deviceScaleFactor:v.deviceScaleFactor},close:async()=>{await s.detach().catch(()=>{});await browser.close().catch(()=>{});}};
}

// opts: {mode, name, cueFile, module(segs/ 기준), segments:[구간 번호…], space, silent, resume:{prev,fromCue}, after(앞 구간 take 이름 — 그 끝 커서에서 시작), failAt(복구 시험용: 그 큐에서 일부러 실패)}
export async function take(opts){
 const rehearsal=opts.mode==='rehearse',out=WORK+'/'+opts.name;
 const proof=WORK+'/rehearsal-'+opts.name.replace(/-.*$/,'')+'.json';
 const allCues=JSON.parse(await fs.readFile(opts.cueFile,'utf8')).cues.filter(c=>opts.segments.includes(c.segment));
 const passed=await fs.readFile(proof,'utf8').then(JSON.parse).catch(()=>({}));
 if(!rehearsal){const miss=allCues.filter(c=>passed[c.id]!==opsMark(c)).map(c=>c.id);
  if(miss.length)throw Error('본촬영 거부: 리허설을 통과하지 않았거나 조작이 바뀐 큐 — '+miss.join(' '));}
 const audio=out+'/길이';await fs.mkdir(audio,{recursive:true});await fs.mkdir(out+'/frames',{recursive:true});
 if((await fs.readdir(out+'/frames')).length)throw Error('Output folder already has frames: '+out);
 for(const c of allCues){const src=abs(CFG.audio)+'/'+c.id+'.json';
  // 대사가 같은 음성만 쓴다.
  const meta=opts.silent?null:await fs.readFile(src,'utf8').then(JSON.parse).catch(()=>null);
  const real=meta&&meta.text===c.text?meta:null;
  if(!real&&!opts.silent&&!rehearsal)throw Error('음성 없음 또는 대사 변경: '+c.id+' — voice.py로 만든 뒤 촬영한다');
  const ms=rehearsal?0:(real?real.duration_ms:Math.round(c.text.replace(/\s/g,'').length/SPEECH_RATE));
  await fs.writeFile(audio+'/'+c.id+'.json',JSON.stringify({text:c.text,duration_ms:ms}));}
 const {p,view,close}=await openPage(opts);
 const metrics=()=>p.cdp('Emulation.setDeviceMetricsOverride',{...view,mobile:false});
 await metrics();
 let queue=Promise.resolve();const serial=fn=>{const r=queue.then(fn);queue=r.catch(()=>{});return r;};
 const sleep=ms=>new Promise(r=>setTimeout(r,ms));
 let recording=false,done=false,error=null,writeQueue=Promise.resolve(),bufferBytes=0,start=null,captures=0,current=null;
 const frames=[],actions=[],motions=[],clicks=[],retargets=[],waits=[];
 const capture=rehearsal?Promise.resolve():(async()=>{while(!done){
  for(const e of await serial(()=>p.events()))if(e.method==='Page.screencastFrame'){
   serial(()=>p.cdp('Page.screencastFrameAck',{sessionId:e.params.sessionId})).catch(x=>{error??=String(x);});
   if(!recording)continue;const b=Buffer.from(e.params.data,'base64'),d=jpegSize(b);
   if(d.width!==1920||d.height!==1080){if(start===null)continue;throw Error('Capture dimensions '+JSON.stringify(d));}
   if(start===null)start=Date.now();
   const f={file:'frames/'+String(frames.length).padStart(6,'0')+'.jpg',time:Date.now()-start,sourceTimestamp:e.params.metadata.timestamp};frames.push(f);bufferBytes+=b.length;
   if(bufferBytes>64*1024*1024)throw Error('Capture disk queue exceeded 64MiB');
   writeQueue=writeQueue.then(async()=>{await fs.writeFile(out+'/'+f.file,b);await fs.appendFile(out+'/frames.jsonl',JSON.stringify(f)+'\n');bufferBytes-=b.length;});
  }
  await sleep(8);
 }})().catch(e=>{error=String(e);done=true;});
 let speechFree=0,actionFree=0,result=null;
 const seam=opts.resume?await resumePoint(opts.resume):null;
 if(seam)await fs.writeFile(out+'/이음.json',JSON.stringify({prev:opts.resume.prev,fromCue:opts.resume.fromCue,cut_ms:seam.cut,pointer:seam.pointer}));
 // after: 구간으로 나눠 찍을 때 앞 take(끝까지 찍은 것)의 마지막 커서 자리에서 시작한다 — 영상 길 16. 페이지는 앞 take 끝 화면 그대로다(browser.mjs가 쥐고 있다).
 const after=opts.after?await loadTiming(opts.after).then(t=>{if(t.error)throw Error('앞 take가 실패로 끝남: '+opts.after);const m=t.motions.at(-1);if(m)return {x:m.x,y:m.y};   // 움직임 없이 끝난 take(말만 하는 구간)는 시작 자리에 커서가 그대로 있다
  return fs.readFile(WORK+'/'+opts.after+'/pointer-start.json','utf8').then(JSON.parse).then(q=>({x:q.x,y:q.y})).catch(()=>null);}):null;
 if(opts.after&&!after)throw Error('앞 take에 커서 기록이 없다: '+opts.after);
 // 구간 경계의 쉼: 앞 take는 마지막 말이 끝나고 조금 뒤에 끝난다(끝 여백). 이어 찍는 take의 첫 큐는 「그 큐의 gap − 앞 take 끝 여백」만큼 기다려, 합본에서 경계 쉼이 큐의 gap과 같아지게 한다.
 const afterTail=opts.after?await loadTiming(opts.after).then(t=>{const a=t.actions.at(-1);return a?Math.max(0,t.duration-(a.time+a.duration)):0;}):null;
 const pos0=seam?seam.pointer:after||{x:760,y:430};
 if(after)await fs.writeFile(out+'/이음.json',JSON.stringify({prev:opts.after,fromCue:null,cut_ms:(await loadTiming(opts.after)).duration+1,pointer:after}));   // 이음새검수.py가 앞 take 끝 프레임과 이 take 첫 프레임을 견준다
 let waitingFor=opts.resume?.fromCue||null;
 const ctx={p,serial,sleep,fs,out,audio,cueFile:opts.cueFile,rehearsal,virtualPointer:pos0,resuming:!!seam,
  recordMotion:m=>motions.push({...m,cue:current,start:m.start-start,end:m.end-start,glide:m.glide-start}),
  recordClick:c=>clicks.push({...c,cue:current,time:Date.now()-start}),
  amendMotion:(x,y)=>{const m=motions.at(-1);if(m)Object.assign(m,{x,y,amended:true});},
  retarget:t=>retargets.push({cue:current,...t}),
  recordWait:w=>waits.push({...w,cue:current,start:w.start-start,end:w.end-start}),
  waitFor:async(fn,arg,timeout=15000)=>{const a=Date.now();while(!(await serial(()=>arg===undefined?p.evaluate(fn):p.evaluate(fn,arg)))){if(Date.now()-a>timeout)throw Error('Expected page state did not appear');await sleep(120);}},
  installPointer:async(q=pos0)=>{await serial(()=>p.mouse.move(q.x,q.y,{steps:1}));await fs.writeFile(out+'/pointer-start.json',JSON.stringify({x:q.x,y:q.y,mode:'overlay'}));},
  // 녹화는 전체에서 한 번만 시작한다. 구간 모듈이 begin을 몇 번 불러도 다시 시작하지 않는다.
  begin:async()=>{if(start!==null)return;
   await fs.writeFile(out+'/recording-start.json','{}');
   await serial(()=>p.evaluate(()=>{window.__takeClicks=[];if(!window.__takeClickHook){window.__takeClickHook=true;document.addEventListener('mousedown',e=>window.__takeClicks.push({x:e.clientX,y:e.clientY}),true);}}));
   if(rehearsal){start=Date.now();recording=true;return;}
   await metrics();recording=true;captures++;
   await serial(()=>p.cdp('Page.startScreencast',{format:'jpeg',quality:85,maxWidth:1920,maxHeight:1080,everyNthFrame:1}));
   await serial(()=>p.evaluate(()=>{const e=document.documentElement,o=e.style.opacity;e.style.opacity='0.999';requestAnimationFrame(()=>{e.style.opacity=o;});}));
   const t=Date.now();while(!frames.length){if(error)throw Error(error);if(Date.now()-t>12000)throw Error('Initial recording frame missing');await sleep(30);}
   if(afterTail!=null)speechFree=Date.now()-afterTail;},
  say:async(id,fn,opt={})=>{
   if(error)throw Error(error);
   if(waitingFor){if(id!==waitingFor)return;waitingFor=null;}
   current=id;
   const c=JSON.parse(await fs.readFile(audio+'/'+id+'.json','utf8'));
   // 큐 사이 기본 쉼 1000ms = 영상 V-14(큐 1.0초). 조작 직후 같은 문맥의 말은 opt.gap으로 짧게 준다.
   const w=Math.max(speechFree,actionFree)+(rehearsal?0:(opt.gap??1000))-Date.now();if(w>0)await sleep(w);
   const t0=Date.now(),a={id,text:c.text,time:t0-start,duration:c.duration_ms};actions.push(a);speechFree=t0+c.duration_ms;
   if(!rehearsal)await fs.writeFile(out+'/partial.json',JSON.stringify({start,actions,motions,clicks,retargets,waits,captures}));
   if(opts.failAt===id&&!opts.resume)throw Error('복구 시험: 일부러 실패');
   if(!fn){actionFree=Math.max(actionFree,t0);return;}
   const pw=t0+(opt.pointDelay??250)-Date.now();if(pw>0&&!rehearsal)await sleep(pw);
   ctx.commitAt=0;ctx.committed=null;a.actionStart=Date.now()-start;await fn();a.commit=ctx.committed?ctx.committed-start:null;a.actionEnd=Date.now()-start;actionFree=Date.now();},
 };
 try{
  await ctx.installPointer(pos0);
  const mod=await import('file:///'+HERE+'segs/'+opts.module+'?'+Date.now());
  for(const n of opts.segments){current='구간'+n+' 시작';await mod.seg(ctx,n);}
  const tail=speechFree-Date.now();if(tail>0)await sleep(tail+400);
 }catch(e){error=`${current}: ${e?.stack||e}`;}
 recording=false;done=true;await capture;
 const duration=start===null?0:Date.now()-start;await writeQueue;
 if(!rehearsal)await p.cdp('Page.stopScreencast').catch(()=>{});
 // 「나」는 끝까지 찍었을 때만 비운다. 실패한 take는 페이지를 그대로 두어야 그 큐부터 같은 화면으로 이어 찍는다.
 if(!error)await p.evaluate(()=>localStorage.removeItem('hyd.me')).catch(()=>{});
 // 페이지가 실제로 받은 클릭 좌표를 기록에 잇는다(ui.mjs가 보낸 값이 아니라 받은 값으로 검사하려고).
 const received=await p.evaluate(()=>window.__takeClicks||[]).catch(()=>[]);
 clicks.forEach((c,i)=>{if(received[i])Object.assign(c,{page_x:received[i].x,page_y:received[i].y});});
 const state={url:await p.url().catch(()=>null),tab:await p.evaluate(()=>document.querySelector('.rail nav button.active')?.dataset.tab||null).catch(()=>null),clicks:clicks.map(c=>({x:c.x,y:c.y,px:c.x,py:c.y}))};
 await fs.writeFile(out+'/end-state.json',JSON.stringify(state,null,2));
 await fs.writeFile(out+'/timing.json',JSON.stringify({start,frames,actions,motions,clicks,retargets,waits,captures,duration,error,result},null,2));
 // 실패했으면 마지막 큐만 빼고 통과로 친다. 고친 뒤 그 큐부터 이어 돌리면 된다.
 if(rehearsal){const ok=new Set(actions.slice(0,error?-1:undefined).map(a=>a.id));for(const c of allCues)if(ok.has(c.id))passed[c.id]=opsMark(c);await fs.writeFile(proof,JSON.stringify(passed,null,1));}
 await close();
 const r={mode:opts.mode,duration,frames:frames.length,captures,cues:actions.length,motions:motions.length,clicks:clicks.length,retargets:retargets.length,error};
 console.log(JSON.stringify(r));return r;
}
