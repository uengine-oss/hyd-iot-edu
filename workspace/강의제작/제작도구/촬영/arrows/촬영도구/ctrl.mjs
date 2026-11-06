// ARROWS 구간 녹화 제어기(Notion ctrl-v10 방식). 한 번 실행에 구간 하나를 녹화한다(분할 촬영).
// - 음성은 큐 단위 클립. 행동 문장이 시작되면 가리키고, 클릭·입력·키는 그 문장 끝 약250ms 전에 실행한다.
// - 다음 음성은 행동 종료 +250ms. 전체 음성 길이만큼 기다리는 고정 대기는 없다.
// - 캡처 ACK는 즉시, 모든 ego 호출은 하나의 직렬 큐. 무거운 인코딩은 녹화 뒤에 한다.
export async function run(SEG){
const fs0=await import('node:fs/promises');const {fileURLToPath}=await import('node:url');const path=await import('node:path');
// 근거 폴더 · 작업 공간 번호는 이 폴더의 config.json에서 읽는다(PC마다 절대 경로를 코드에 두지 않는다).
const here=path.dirname(fileURLToPath(import.meta.url));const conf=JSON.parse(await fs0.readFile(path.join(here,'config.json'),'utf8'));
const base=path.resolve(here,conf.work).split(path.sep).join('/');
const boot=m=>fs0.appendFile(base+'/boot.log',new Date().toISOString().slice(11,23)+' '+SEG.name+' '+m+String.fromCharCode(10));await boot('enter');
const {makeUI}=await import('./ui.mjs?'+SEG.name);
const fs=await import('node:fs/promises');
const out=base+'/'+SEG.name;
await fs.mkdir(out+'/frames',{recursive:true});
if((await fs.readdir(out+'/frames')).length)throw Error('Output folder already has frames: '+out);
const log=m=>fs.appendFile(out+'/progress.log',new Date().toISOString().slice(11,23)+' '+m+'\n');
await log('start '+JSON.stringify(SEG));
const cfg=JSON.parse(await fs.readFile(base+'/cues.json','utf8'));
const cues=cfg.cues.filter(c=>c.segment===SEG.segment&&(!SEG.from||c.id>=SEG.from)&&(!SEG.to||c.id<=SEG.to));
await boot('taskSpace');const task=await taskSpace(SEG.space||conf.space);const p=task.page('p1');await boot('page');
await p.cdp('Emulation.setDeviceMetricsOverride',{width:2304,height:1296,deviceScaleFactor:1,mobile:false});
// 같은 창에서 다른 탭(사용자 탭 · 확장 탭)이 앞에 있으면 screencast 프레임이 띄엄띄엄 와서 커서가 0.5~1.3초씩 끊긴다. 녹화 탭을 앞으로 가져온다(다른 탭은 닫지 않는다).
{const all=await task.cdp('Target.getTargets');const here=await p.url();const me=all.targetInfos.find(x=>x.type==='page'&&x.url===here);if(me)await task.cdp('Target.activateTarget',{targetId:me.targetId});}
await p.cdp('Page.bringToFront');
let queue=Promise.resolve();function serial(fn){const r=queue.then(fn);queue=r.catch(()=>{});return r;}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
let recording=false,done=false,error=null,writeQueue=Promise.resolve(),bufferBytes=0,start=null;const frames=[],actions=[],motions=[];
function jpegSize(b){let i=2;while(i<b.length){if(b[i]!==255){i++;continue;}const marker=b[i+1];i+=2;if(marker===216||marker===217)continue;const len=b.readUInt16BE(i);if([192,193,194].includes(marker))return {width:b.readUInt16BE(i+5),height:b.readUInt16BE(i+3)};i+=len;}throw Error('JPEG dimensions missing');}
try{await p.cdp('Page.stopScreencast');}catch(e){}
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
const ACT=/(누르|확정|넓힐|옮기겠|정리할|놓겠|칠하겠|눌러|누를|클릭|선택|적을|적어|적겠|적고|엔터|끌어|끌고|끌면|옮겨|둘게|바꾸고|고르|내려받|들어갈)/;
function plan(text){
 const s=text.split(/(?<=[.?!])\s+/);const total=text.length;let at=0;const spans=s.map(x=>{const a=at;at+=x.length+1;return{a,b:Math.min(total,at-1),x};});
 const k=[...spans].reverse().find(x=>ACT.test(x.x))||spans.at(-1);
 return{pointFrac:k.a/total,commitFrac:k.b/total,sentence:k.x};
}
let speechFree=0,actionFree=0;const ctx={p,serial,sleep,saved:{}};
ctx.recordMotion=m=>motions.push({...m,start:m.start-start,end:m.end-start});
async function cue(c,fn,pointing){
 if(error)throw Error(error);
 if(await fs.stat(base+'/STOP').then(()=>true).catch(()=>false))throw Error('Stop requested');
 const ready=Math.max(speechFree,actionFree)+250;const w=ready-Date.now();if(w>0)await sleep(w);
 const t0=Date.now();const a={id:c.id,text:c.text,time:t0-start,duration:c.duration_ms};actions.push(a);await log('cue '+c.id);
 speechFree=t0+c.duration_ms;ctx.cueT0=t0;ctx.cueDur=c.duration_ms;
 if(!fn){actionFree=t0;return;}
 const pl=plan(c.text);
 const pointAt=pointing?t0+150:t0+Math.round(c.duration_ms*pl.pointFrac)+250;
 const commitAt=t0+Math.round(c.duration_ms*pl.commitFrac)-250;
 Object.assign(a,{plannedPoint:pointAt-start,plannedCommit:commitAt-start,actionSentence:pl.sentence});
 const w2=pointAt-Date.now();if(w2>0)await sleep(w2);ctx.commitAt=pointing?0:commitAt;ctx.committed=null;a.actionStart=Date.now()-start;
 await fn();a.commit=ctx.committed?ctx.committed-start:null;a.actionEnd=Date.now()-start;actionFree=Date.now();
}
await boot('capture loop');let result=null,ui=null;
try{
 const prev=SEG.startState?JSON.parse(await fs.readFile(base+'/'+SEG.startState+'/end-state.json','utf8')):null;
 ctx.startPos=prev?.pointer||{x:700,y:420};
 ctx.saved=prev?.saved||{};
 ui=await makeUI(ctx);
 const url=await serial(()=>p.url());
 if(SEG.expectUrl&&!url.includes(SEG.expectUrl))throw Error('Start URL '+url+' does not contain '+SEG.expectUrl);
 if(prev&&prev.url!==url&&!SEG.relaxUrl)throw Error('Start URL differs from previous end state: '+url);
 await ui.install();
 // 녹화 전: 캔버스 기록이 비지 않도록 화면 크기를 1px 바꿨다 되돌려 한 번 다시 그리게 한다(녹화 프레임에는 남지 않음).
 if(url.includes('arrows.app')){await serial(()=>p.cdp('Emulation.setDeviceMetricsOverride',{width:2305,height:1296,deviceScaleFactor:1,mobile:false}));await sleep(300);await serial(()=>p.cdp('Emulation.setDeviceMetricsOverride',{width:2304,height:1296,deviceScaleFactor:1,mobile:false}));await sleep(400);
  const n=(await ui.circles()).list.length;await log('circles before recording '+n);if(!n)throw Error('Canvas not recorded before start');
  // 이어 찍기: 크기 바꾸기(resize)는 약 0.3초 뒤 그림 맞춤을 다시 하므로, 그 뒤에 앞 판 끝 화면의 보기(SEG.view: 확대율 · 위치)를 넣고 0.8초 동안 그대로인지 본다(녹화 프레임에는 남지 않음).
  if(SEG.view){const same=g=>g&&Math.abs(g.scale-SEG.view.scale)<1e-9&&Math.abs(g.offset.dx-SEG.view.dx)<1e-6&&Math.abs(g.offset.dy-SEG.view.dy)<1e-6;
   const vt=set=>serial(()=>p.evaluate(([v,set])=>{const root=document.getElementById('root');const k=Object.keys(root).find(x=>x.startsWith('__reactContainer'));const seen=new Set(),st=[root[k]];let s=null;while(st.length&&!s){const f=st.pop();if(!f||seen.has(f))continue;seen.add(f);if(f.memoizedProps?.store?.getState)s=f.memoizedProps.store;else st.push(f.child,f.sibling);}if(!s)return null;if(set)s.dispatch({type:'ADJUST_VIEWPORT',scale:v.scale,panX:v.dx,panY:v.dy});return s.getState().viewTransformation;},[SEG.view,set]));
   let ok=false;for(let i=0;i<4&&!ok;i++){await sleep(600);await vt(true);await sleep(800);ok=same(await vt(false));}
   if(!ok)throw Error('View not stable: '+JSON.stringify(await vt(false)));await log('view '+JSON.stringify(SEG.view));}
 }
 await serial(()=>p.mouse.move(ctx.startPos.x,ctx.startPos.y,{steps:1}));await sleep(500);
 recording=true;await serial(()=>p.cdp('Page.startScreencast',{format:'jpeg',quality:85,maxWidth:1920,maxHeight:1080,everyNthFrame:1}));
 {const t=Date.now();while(!frames.length){if(error)throw Error(error);if(Date.now()-t>12000)throw Error('Initial recording frame missing');await sleep(30);}}
 await fs.writeFile(out+'/recording-start.json',JSON.stringify({start,url,clicksBefore:await serial(()=>p.evaluate(()=>(window.__tutorialClicks||[]).length))}));
 // 이어 찍기: 앞 녹화에서 멈춘 동작의 나머지를 음성 없이 먼저 수행한다(SEG.pre).
 if(SEG.pre){const pre=JSON.parse(SEG.pre);ctx.cueT0=Date.now();ctx.cueDur=0;ctx.commitAt=0;for(const o of pre)await exec(o);await log('pre done');}
 for(const c0 of cues){
  const c={...c0,...JSON.parse(await fs.readFile(base+'/audio/'+c0.id+'.json','utf8'))};
  const ops=c0.ops;const pointing=ops.length&&ops.every(o=>['at','point','verify'].includes(o[0]));
  await cue(c,ops.length?async()=>{for(const o of ops)await exec(o);}:null,pointing);
 }
 const tail=speechFree-Date.now();if(tail>0)await sleep(tail+400);
 // arrows는 바뀐 그림을 늦게 저장한다(「Saving to Web Browser storage...」). 저장이 끝난 화면까지 녹화해야 끝 프레임과 끝 상태(end-state의 그림)가 같은 그림이 된다.
 if((await serial(()=>p.url())).includes('arrows.app')){const t1=Date.now();await sleep(300);while(!(await serial(()=>p.evaluate(()=>document.body.innerText.includes('Saved to Web Browser storage'))))){if(Date.now()-t1>5000)throw Error('Graph not saved within 5s after last cue');await sleep(100);}await sleep(300);}
 result='segment '+SEG.segment+' done';
}catch(e){error=String(e?.stack||e);}
async function exec(o){
 const [op,...a]=o;
 if(op==='at'){const w=ctx.cueT0+ctx.cueDur*a[0]-Date.now();if(w>0)await sleep(w);return;}
 if(op==='point')return ui.point(a[0]);
 if(op==='click')return ui.click(a[0]);
 if(op==='type')return ui.type(a[0]);
 if(op==='key')return ui.key(a[0]);
 if(op==='drag')return ui.drag(a[0],a[1],a[2]);
 if(op==='connect')return ui.connect(a[0],a[1]);
 if(op==='ctrlclick')return ui.ctrlclick(a[0]);
 // 사람처럼 그 자리에서 다시 시도: 끌어내기는 방향을 바꿔, 화살표 선택·잇기는 한 번 더. 녹화는 멈추지 않는다.
 if(op==='grow'){for(const d of [0,60]){try{return await ui.grow(a[0],a[1]+d);}catch(e){await log('retry grow '+a[0]+' '+String(e).slice(0,80));}}throw Error('grow failed 3 times from '+a[0]);}
 if(op==='move')return ui.move(a[0],a[1],a[2]);
 // 사용자가 직접 조작하는 동안 녹화만 유지한다. DONE 파일이 생기면 끝(최대 15분). 포인터는 사용자 마우스 이동을 따라간다.
 if(op==='manual'){await log('manual start');const t0=Date.now();while(!(await fs.stat(base+'/DONE').then(()=>true).catch(()=>false))){if(Date.now()-t0>900000)throw Error('manual timeout');await sleep(300);}await log('manual done');return;}
 if(op==='place'){const r=await ui.place(a[0]);await log('place '+r.join(' '));return;}
 // 비율 배치: [이름, 가로 비율, 세로 비율]을 지금 그림 범위(저장 좌표)에 맞춰 그림 좌표로 바꾼 뒤 layout으로 옮긴다.
 if(op==='layoutNorm'){const g=await serial(()=>p.evaluate(()=>{const id=location.hash.split('id=')[1];return JSON.parse(localStorage.getItem('GRAPH|'+id)).graph.nodes.map(n=>n.position);}));const X=g.map(q=>q.x),Y=g.map(q=>q.y),x0=Math.min(...X),x1=Math.max(...X),y0=Math.min(...Y),y1=Math.max(...Y);return exec(['layout',a[0].map(([c,nx,ny])=>[c,Math.round(x0+nx*(x1-x0)),Math.round(y0+ny*(y1-y0))]),a[1]]);}
 if(op==='layout'){const r=await ui.layout(a[0],a[1]);await log('layout '+r.join(' '));const off=a[0].filter((m,i)=>{const d=r[i].split(':').pop().split(',').map(Number);return Math.hypot(d[0],d[1])>20;});if(off.length){const r2=await ui.layout(off,a[1]);await log('layout pass2 '+r2.join(' '));}return;}
 if(op==='spread')return ui.spread(a[0],a[1]);
 if(op==='arrange'){const r=await ui.arrange(a[0]);await log('arrange '+r.join(' '));return;}
 if(op==='edge'){try{return await ui.edge(a[0],a[1]);}catch(e){await log('retry edge');await ui.click('blank');return ui.edge(a[0],a[1]);}}
 if(op==='openLink'){
  const q=await serial(()=>p.evaluate(()=>{const h=[...document.querySelectorAll('a h3')].find(e=>e.textContent.trim()==='Arrows.app');if(!h)return null;const b=h.getBoundingClientRect();return{x:b.x+Math.min(60,b.width/2),y:b.y+b.height/2};}));
  if(!q)throw Error('Arrows.app link not on page');
  await ui.move(q.x,q.y);await ui.gate();await serial(()=>p.mouse.click(q.x,q.y));
  await serial(()=>p.waitForURL(/arrows\.app/,{timeout:15000}));await serial(()=>p.waitForSelector('canvas',{timeout:15000}));
  await ui.install();await sleep(300);return;
 }
 if(op==='download'){
  const kind=a[0];const wait=p.waitForEvent('download',{timeout:20000});wait.catch(()=>{}); // 대기열 밖: 대기열에 넣으면 뒤의 클릭이 막힌다
  await ui.click('download');const d=await wait;const path=base+'/saved/'+(a[1]||'쿨러_지식그래프')+'.'+kind;await d.saveAs(path);ctx.saved[kind]=path;await log('saved '+path);return;
 }
 if(op==='choose'){
  const path=ctx.saved[a[0]];if(!path)throw Error('No saved '+a[0]+' file to choose');
  const wait=p.waitForFileChooser({timeout:10000});await ui.click('chooseFile');const ch=await wait;await ch.setFiles(path);await sleep(300);return;
 }
 if(op==='verify'){
  const g=await serial(()=>p.evaluate(()=>{const id=location.hash.split('id=')[1];return JSON.parse(localStorage.getItem('GRAPH|'+id)).graph;}));
  const props=g.nodes.filter(n=>Object.keys(n.properties||{}).length).map(n=>n.caption+':'+Object.keys(n.properties).length);
  await log('verify '+g.nodes.length+' nodes '+g.relationships.length+' rels '+props.join(','));
  const want=[cfg.nodes.length,cfg.relationships.length,Object.keys(cfg.properties).length];
  if(g.nodes.length!==want[0]||g.relationships.length!==want[1]||props.length!==want[2])throw Error('Reopened graph mismatch: '+g.nodes.length+'/'+g.relationships.length+' '+props.join(',')+' want '+want.join('/'));
  return;
 }
 throw Error('Unknown op '+op);
}
recording=false;done=true;await capture;const duration=start===null?0:Date.now()-start;await writeQueue;
try{await p.cdp('Page.stopScreencast');}catch(e){}
// 끝 화면의 보기(확대율 · 위치)도 남긴다 — 다음 호출에서 화면 크기가 풀리면 그림 맞춤이 다시 되므로, 이어 찍는 구간은 이 값을 SEG.view로 넣는다.
const view=await p.evaluate(()=>{const root=document.getElementById('root');const k=Object.keys(root).find(x=>x.startsWith('__reactContainer'));const seen=new Set(),st=[root[k]];let s=null;while(st.length&&!s){const f=st.pop();if(!f||seen.has(f))continue;seen.add(f);if(f.memoizedProps?.store?.getState)s=f.memoizedProps.store;else st.push(f.child,f.sibling);}if(!s)return null;const g=s.getState().viewTransformation;return {scale:g.scale,dx:g.offset.dx,dy:g.offset.dy};}).catch(()=>null);
const state={url:await p.url().catch(()=>null),pointer:ui?ui.pos():null,saved:ctx.saved,view,
 clicks:await p.evaluate(()=>window.__tutorialClicks||[]).catch(()=>[]),
 graph:await p.evaluate(()=>{const id=location.hash.split('id=')[1];return id?JSON.parse(localStorage.getItem('GRAPH|'+id)):null;}).catch(()=>null)};
await fs.writeFile(out+'/end-state.json',JSON.stringify(state,null,1));
await fs.writeFile(out+'/timing.json',JSON.stringify({start,frames,actions,motions,duration,error,result},null,1));
await log('end '+(error?error.slice(0,200):result));
return {duration,frames:frames.length,cues:actions.length,error,result,url:state.url};
}
