// 포털 녹화 제어기(Notion v10 제어기를 Playwright로 옮김). 한 번 실행에 구간 모듈 하나를 녹화한다(기능 구간별 분할 촬영). run.sh rec가 부른다.
// ego와 다른 점: browser.mjs가 띄워 둔 브라우저에 CDP로 붙는다(구간 사이 페이지 상태 유지). 화면 프레임은 CDP 이벤트로 받아 바로 ACK한다
// (ego의 events 폴링 · 직렬 큐 · EPERM 문제가 없음). 조작(mouse · keyboard · evaluate)은 직렬 큐 하나로 보낸다.
// 리듬: 행동 문장 안에서 가리키고 문장 끝 약 250ms 전에 실행(gate), 결과 발화는 행동 종료 뒤.
// 출력: <work>/<name>/frames/*.jpg · timing.json(프레임 · 큐 · 이동) · end-state.json(URL · 탭 · 스크롤 · 클릭) · end-snapshot.txt
import {createRequire} from 'node:module';
import fs from 'node:fs/promises';
import {fileURLToPath,pathToFileURL} from 'node:url';
import path from 'node:path';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'/opt/node22/lib/node_modules/playwright');
const HERE=fileURLToPath(new URL('.',import.meta.url));
const CFG=JSON.parse(await fs.readFile(HERE+'config.json','utf8'));
const abs=r=>path.resolve(HERE,r);
const WORK=abs(CFG.work),AUDIO=abs(CFG.audio);
const W=Math.round(CFG.viewport.width*CFG.viewport.deviceScaleFactor),H=Math.round(CFG.viewport.height*CFG.viewport.deviceScaleFactor);

function jpegSize(b){let i=2;while(i<b.length){if(b[i]!==255){i++;continue;}const marker=b[i+1];i+=2;if(marker===216||marker===217)continue;const len=b.readUInt16BE(i);if([192,193,194].includes(marker))return {width:b.readUInt16BE(i+5),height:b.readUInt16BE(i+3)};i+=len;}throw Error('JPEG dimensions missing');}
const ACT=/(누르|눌러|누를|클릭|선택|입력|적을|적어|적겠|닫는|닫을|열겠|열어|엔터|가져가|내려|올려|넣겠|넣어|바꿔|바꾸)/;
// 행동 문장 = 조작 동사가 있는 마지막 문장. 시점은 글자 비율 추정(단어 시각 없음).
function plan(c){
 const s=c.text.split(/(?<=[.?!])\s+/);const total=c.text.length;let at=0;const spans=s.map(x=>{const a=at;at+=x.length+1;return{a,b:Math.min(total,at-1),x};});
 const k=[...spans].reverse().find(x=>ACT.test(x.x))||spans.at(-1);
 return{pointFrac:k.a/total,commitFrac:k.b/total,sentence:k.x};
}

// opts: {name, module(segs/ 기준 파일명), pointer:{x,y}|null(앞 구간 끝 포인터), resume:end-state(앞 구간 끝 상태)|null}
export async function run(opts){
 const out=WORK+'/'+opts.name;
 await fs.mkdir(out+'/frames',{recursive:true});
 if((await fs.readdir(out+'/frames')).length)throw Error('Output folder already has frames: '+out);
 const browser=await chromium.connectOverCDP(`http://127.0.0.1:${CFG.cdp}`);
 const p=browser.contexts()[0]?.pages()[0];if(!p)throw Error('browser.mjs page missing (run.sh up 먼저)');
 const cdp=await p.context().newCDPSession(p);
 // 다른 사이트(GitHub 등)로 옮기면 상주 브라우저의 화면 크기 설정이 풀려 800x600이 된다(2026-10-23). 녹화마다 이 세션에서 다시 정한다.
 const metrics=()=>cdp.send('Emulation.setDeviceMetricsOverride',{width:CFG.viewport.width,height:CFG.viewport.height,deviceScaleFactor:CFG.viewport.deviceScaleFactor,mobile:false});
 await metrics();await p.waitForFunction(w=>innerWidth===w,CFG.viewport.width,{timeout:5000});
 let queue=Promise.resolve();const serial=fn=>{const r=queue.then(fn);queue=r.catch(()=>{});return r;};
 const sleep=ms=>new Promise(r=>setTimeout(r,ms));
 let recording=false,error=null,writeQueue=Promise.resolve(),bufferBytes=0,start=null;const frames=[],actions=[],motions=[];
 cdp.on('Page.screencastFrame',e=>{
  cdp.send('Page.screencastFrameAck',{sessionId:e.sessionId}).catch(x=>{error??=String(x);});
  if(!recording)return;const b=Buffer.from(e.data,'base64');const d=jpegSize(b);
  if(d.width!==W||d.height!==H){if(start===null)return;error??='Capture dimensions '+JSON.stringify(d);return;}
  if(start===null)start=Date.now();
  const f={file:'frames/'+String(frames.length).padStart(6,'0')+'.jpg',time:Date.now()-start,sourceTimestamp:e.metadata.timestamp};frames.push(f);bufferBytes+=b.length;
  if(bufferBytes>64*1024*1024){error??='Capture disk queue exceeded 64MiB';return;}
  writeQueue=writeQueue.then(async()=>{await fs.writeFile(out+'/'+f.file,b);await fs.appendFile(out+'/frames.jsonl',JSON.stringify(f)+'\n');bufferBytes-=b.length;});
 });
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
  const pl=plan(c);const pointAt=t0+Math.round(c.duration_ms*(opt.pointFrac??pl.pointFrac))+(opt.pointDelay??250);
  const commitAt=t0+Math.round(c.duration_ms*(opt.commitFrac??pl.commitFrac))-(opt.commitLead??250);
  Object.assign(a,{plannedPoint:pointAt-start,plannedCommit:commitAt-start,actionSentence:pl.sentence,estimate:'character-proportional'});
  const go=(async()=>{const w2=pointAt-Date.now();if(w2>0)await sleep(w2);ctx.commitAt=commitAt;ctx.committed=null;a.actionStart=Date.now()-start;
   await fn();a.commit=ctx.committed?ctx.committed-start:null;a.actionEnd=Date.now()-start;actionFree=Date.now();})();
  if(opt.async){pending=go;return;}
  await go;
 }
 let result=null;
 const state=()=>p.evaluate(()=>({url:location.href,tab:document.querySelector('.rail nav button.active')?.dataset.tab||null,
   scroll:[...document.querySelectorAll('*')].filter(e=>e.scrollTop>0).slice(0,5).map(e=>({sel:e.id?'#'+e.id:e.className?.toString().split(' ')[0]||e.tagName,top:e.scrollTop})).concat(scrollY?[{sel:'window',top:scrollY}]:[]),
   clicks:window.__tutorialClicks||[],pointer:window.__ptrStat||null}));
 try{
  const ctx={p,cdp,serial,sleep,fs,out,
   recordMotion:m=>motions.push({...m,start:m.start-start,end:m.end-start,...(m.glide?{glide:m.glide-start}:{})}),
   waitFor:async(fn,arg,timeout=15000)=>{const a=Date.now();while(!(await serial(()=>p.evaluate(fn,arg)))){if(Date.now()-a>timeout)throw Error('Expected page state did not appear');await sleep(120);}},
   begin:async()=>{await serial(()=>p.evaluate(()=>{window.__ptrStat={held:0,heldAfterFinish:0,applied:0};window.__tutorialClicks=[];}));recording=true;
    await cdp.send('Page.startScreencast',{format:'jpeg',quality:Number(process.env.JPEG_Q||85),maxWidth:W,maxHeight:H,everyNthFrame:1});
    // 정지 화면에서는 프레임이 오지 않으므로 화살표 투명도를 아주 조금 바꿔 첫 프레임을 받는다(화면에 남지 않는 변화).
    await serial(()=>p.evaluate(()=>{const e=document.getElementById('recording-pointer');if(e){const o=e.style.opacity||'1';e.style.opacity=o==='0'?'0.001':'0.999';requestAnimationFrame(()=>{e.style.opacity=o;});}}));
    const t=Date.now();while(!frames.length){if(error)throw Error(error);if(Date.now()-t>12000)throw Error('Initial recording frame missing');await sleep(30);}
    await fs.writeFile(out+'/recording-start.json',JSON.stringify({start,url:p.url()}));},
  };
  ctx.say=async(id,fn,opt)=>{const f=AUDIO+'/'+id+'.json';const c=JSON.parse(await fs.readFile(f,'utf8').catch(()=>{throw Error('Voice cue missing: '+f+' (voice.py로 생성 후 촬영)');}));await cue(ctx,c,fn,opt);};
  // 시험용: 음성 없이 문장 길이(분당 422자 실측값)로 큐를 만든다. 본 촬영에서는 쓰지 않는다.
  ctx.silent=async(id,text,fn,opt)=>cue(ctx,{id,text,duration_ms:Math.round(text.replace(/\s/g,'').length/422*60000)},fn,opt);
  // 이어 찍기: 앞 구간 끝 탭이 아니면 녹화 전에 그 탭을 연다(화면에 남지 않음). 화살표는 앞 구간 끝 위치에 다시 그린다.
  if(opts.resume?.tab){const now=await serial(()=>p.evaluate(()=>document.querySelector('.rail nav button.active')?.dataset.tab||null));
   if(now!==opts.resume.tab){await serial(()=>p.click(`.rail nav button[data-tab="${opts.resume.tab}"]`));await sleep(1200);}}
  const {installPointerInPage}=await import(pathToFileURL(HERE+'ui.mjs').href+'?'+Date.now());
  const q=opts.pointer||{x:CFG.viewport.width*0.6,y:CFG.viewport.height*0.6};
  await serial(()=>p.evaluate(installPointerInPage,q));await serial(()=>p.mouse.move(q.x,q.y,{steps:1}));
  // pointer=overlay: 페이지 화살표는 투명하게 두고(위치 · 클릭 기록은 그대로) 합성 때 기록된 경로로 화살표를 그린다(encode.py).
  // 클라우드 4코어에서 1920x1080 화면 녹화가 이동의 약 1/5에서 100~190ms 끊겨(2026-10-23 진단) 화살표가 건너뛰어 보였기 때문이다.
  if(CFG.pointer==='overlay')await serial(()=>p.evaluate(()=>{document.getElementById('recording-pointer').style.opacity='0';}));
  await fs.writeFile(out+'/pointer-start.json',JSON.stringify({x:q.x,y:q.y,mode:CFG.pointer||'page'}));
  const mod=await import(pathToFileURL(HERE+'segs/'+opts.module).href+'?'+Date.now());
  result=await mod.default(ctx);
  if(pending)await pending;
  const tail=speechFree-Date.now();if(tail>0)await sleep(tail+400);
 }catch(e){error=String(e?.stack||e);}
 finally{
  recording=false;const duration=start===null?0:Date.now()-start;
  try{await cdp.send('Page.stopScreencast');}catch(e){}
  await sleep(100);await writeQueue;
  const st=await state().catch(e=>({error:String(e)}));
  await fs.writeFile(out+'/end-state.json',JSON.stringify(st,null,2));
  await fs.writeFile(out+'/end-snapshot.txt',await p.locator('body').ariaSnapshot().catch(e=>String(e)));
  await fs.writeFile(out+'/timing.json',JSON.stringify({start,frames,actions,motions,duration,error,result},null,2));
  await cdp.detach().catch(()=>{});await browser.close().catch(()=>{});
  return {duration,frames:frames.length,cues:actions.length,error,result,url:st.url,tab:st.tab};
 }
}
