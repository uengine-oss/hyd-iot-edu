import {focusReadableGraph} from './readable_graph.mjs';
import {installGraphObserver,graphTarget} from './graph_targets.mjs';
import fs from 'node:fs/promises';
const cfg=globalThis.HYD_RECORDING;
if(!cfg?.evidence||!cfg?.repo||!cfg?.take||!cfg?.space||!cfg?.host)throw Error('Set HYD_RECORDING after checking the current browser space and lab connection');
const base=cfg.evidence;
const out=base+'/'+cfg.take;await fs.mkdir(out+'/frames',{recursive:true});
if((await fs.readdir(out+'/frames')).length)throw Error('Existing take preserved');
const task=await taskSpace(cfg.space),p=task.page(cfg.page||'p1');
await p.cdp('Emulation.setDeviceMetricsOverride',{width:cfg.width||(cfg.readable?1920:2560),height:cfg.height||(cfg.readable?1080:1440),deviceScaleFactor:1,mobile:false});
await p.waitForFunction(()=>innerWidth>=1280,undefined,{timeout:10000});
await p.evaluate(installGraphObserver);
await p.evaluate(()=>{for(const e of document.querySelectorAll('*'))if(e.scrollTop)e.scrollTop=0;window.scrollTo(0,0);});
const bounds=await p.evaluate(()=>{const r=document.querySelector('[role="dialog"]')?.getBoundingClientRect();return r&&{top:r.top,bottom:r.bottom,height:innerHeight};});
if(!cfg.continue&&(!bounds||bounds.top<0||bounds.bottom>bounds.height))throw Error('Connection dialog clipped: '+JSON.stringify(bounds));
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const cells=()=>p.evaluate(()=>Array.from(document.querySelectorAll('[role="table"] [role="cell"]')).slice(0,6).map(e=>{const r=e.getBoundingClientRect();return {text:e.innerText,x:r.x+Math.min(110,r.width-20),y:r.y+r.height/2};}));
let targets=[],pos=cfg.pointer||{x:500,y:240};
const point=spec=>p.evaluate(spec=>{
 let all=Array.from(document.querySelectorAll(spec.css||'button'));
 if(spec.text)all=all.filter(e=>e.textContent.trim()===spec.text);
 const e=all.find(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&r.y>=0&&r.y<innerHeight;});
 if(!e)throw Error('Visible target missing: '+JSON.stringify(spec));
 const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};
},spec);
await p.evaluate(pos=>{
 document.getElementById('recording-pointer')?.remove();
 const e=document.createElement('div');e.id='recording-pointer';e.setAttribute('aria-hidden','true');
 e.style.cssText=`position:fixed;left:0;top:0;width:20px;height:27px;pointer-events:none;z-index:2147483647;will-change:transform;transform:translate(${pos.x}px,${pos.y}px)`;
 e.innerHTML='<svg xmlns="http://www.w3.org/2000/svg" width="20" height="27" viewBox="0 0 25 34"><path d="M1 1 L1 25 L7 20 L12 31 L17 29 L12 18 L22 18 Z" fill="white" stroke="#111" stroke-width="1.7" stroke-linejoin="round"/></svg>';
 document.documentElement.append(e);
},pos);
await p.mouse.move(pos.x,pos.y,{steps:1});
let queue=Promise.resolve();const serial=fn=>{const r=queue.then(fn);queue=r.catch(()=>{});return r;};
let done=false,start=null,error=null;const frames=[],motions=[];let writes=Promise.resolve();

const initial=await p.evaluate(()=>({host:document.querySelector('input[name="hostname"]')?.value,protocol:document.querySelector('[role="dialog"] .ndl-select-control')?.textContent,user:document.querySelector('input[name="username"]')?.value,oldResult:document.querySelector('[role="table"]')!==null}));
if(!cfg.continue&&(initial.host!==cfg.host||initial.protocol!=='bolt://'||initial.user!=='neo4j'||initial.oldResult))throw Error('Unexpected initial state: '+JSON.stringify(initial));
await fs.writeFile(out+'/initial-state.json',JSON.stringify(initial,null,2));
await p.events();const recordingRequestedAt=Date.now();
await p.cdp('Page.startScreencast',{format:'jpeg',quality:cfg.readable?95:80,maxWidth:1920,maxHeight:1080,everyNthFrame:1});
const capture=(async()=>{while(!done){for(const e of await serial(()=>p.events()))if(e.method==='Page.screencastFrame'){
 await serial(()=>p.cdp('Page.screencastFrameAck',{sessionId:e.params.sessionId}));
 const bytes=Buffer.from(e.params.data,'base64');let size=null;
 for(let k=2;k<bytes.length-9;){if(bytes[k]!==255){k++;continue;}const marker=bytes[k+1],len=bytes.readUInt16BE(k+2);if([192,193,194].includes(marker)){size=[bytes.readUInt16BE(k+7),bytes.readUInt16BE(k+5)];break;}if(len<2)break;k+=2+len;}
 if(start===null&&(!size||size[0]!==1920||size[1]!==1080))continue;
 const stamp=e.params.metadata.timestamp*1000;if(start===null&&stamp<recordingRequestedAt)continue;if(start===null)start=stamp;
 const f={file:'frames/'+String(frames.length).padStart(6,'0')+'.jpg',time:stamp-start,sourceTimestamp:e.params.metadata.timestamp};frames.push(f);
 const b=Buffer.from(e.params.data,'base64');writes=writes.then(()=>fs.writeFile(out+'/'+f.file,b));
}await sleep(8);}})().catch(e=>{error=String(e);done=true;});
async function move(target){
 if(Math.hypot(target.x-pos.x,target.y-pos.y)<1)return;
 const a={...pos},ms=Math.round(Math.max(260,Math.min(620,200+Math.hypot(target.x-a.x,target.y-a.y)*.4))),t0=Date.now();
 await serial(()=>p.evaluate(({a,b,ms})=>{const e=document.getElementById('recording-pointer');window.__recordGlide=e.animate([{transform:`translate(${a.x}px,${a.y}px)`},{transform:`translate(${b.x}px,${b.y}px)`}],{duration:ms,easing:'ease-in-out',fill:'forwards'});},{a,b:target,ms}));
 const steps=Math.max(8,Math.ceil(ms/33));for(let i=1;i<=steps;i++){const t=i/steps,u=t*t*(3-2*t);await sleep(Math.max(0,t0+ms*t-Date.now()));await serial(()=>p.mouse.move(a.x+(target.x-a.x)*u,a.y+(target.y-a.y)*u,{steps:1}));}
 await serial(()=>p.evaluate(b=>{const e=document.getElementById('recording-pointer');e.style.transform=`translate(${b.x}px,${b.y}px)`;window.__recordGlide?.cancel();},target));
 pos={x:target.x,y:target.y};motions.push({start:t0-start,end:Date.now()-start,from:a,...pos,planned_ms:ms});
}
const actions=[];
const spec=JSON.parse(await fs.readFile(cfg.cues||cfg.repo+'/제작용/촬영/neo4j/통합반_그래프탐색_큐.json','utf8'));
let savedDownload=null;
try{
 const waitStart=Date.now();while(start===null){if(error)throw Error(error);if(Date.now()-waitStart>10000)throw Error('No recording frames');await sleep(20);}
 await serial(()=>p.evaluate(()=>{window.__recordClicks=[];document.addEventListener('mouseup',()=>{document.querySelector('#recording-pointer path')?.setAttribute('fill','white');},{capture:true});document.addEventListener('mousedown',e=>{if(!e.isTrusted)return;document.querySelector('#recording-pointer path')?.setAttribute('fill','#d6d6d6');const r=document.getElementById('recording-pointer').getBoundingClientRect();window.__recordClicks.push({x:e.clientX,y:e.clientY,px:r.x,py:r.y,gliding:window.__recordGlide?.playState==='running'});},{capture:true});}));
 const clickHere=async()=>{await serial(()=>p.mouse.down());await sleep(95);await serial(()=>p.mouse.up());};
 const act=async(spec,click=false)=>{let target;for(let i=0;i<15;i++){const a=await serial(()=>point(spec));await sleep(150);target=await serial(()=>point(spec));if(Math.hypot(a.x-target.x,a.y-target.y)<1)break;if(i===14)throw Error('Unstable target');}await move(target);if(click){const r=await serial(()=>point(spec));if(Math.hypot(r.x-target.x,r.y-target.y)>2)throw Error('Target moved');await clickHere();}};
 const cue=async(id,operation)=>{const meta=JSON.parse(await fs.readFile(base+'/'+(cfg.audio||'relations-audio')+'/'+id+'.json','utf8'));const at=Date.now()+250;const a={id,text:meta.text,time:at-start,duration:meta.duration_ms};actions.push(a);await sleep(Math.max(0,at-Date.now()));
  const gate=async(fraction)=>{await sleep(Math.max(0,at+meta.duration_ms*fraction-Date.now()));if(error)throw Error(error);};
  await operation(gate,a);await sleep(Math.max(0,at+meta.duration_ms+250-Date.now()));};

 const editor={css:'[aria-label="Cypher Editor"]'};
 const runButton={css:'[data-testid="run-button"]'};
 async function input(text){
  await act(editor);await clickHere();await serial(()=>p.keyboard.press('ControlOrMeta+A'));await serial(()=>p.keyboard.press('Backspace'));
  await move({x:650,y:135});await serial(()=>p.keyboard.insertText(text));await serial(()=>p.keyboard.press('Escape'));
 }
 const resultPoint=async()=>act({css:'[role="table"] [role="cell"]'});
 const hasDetails=()=>p.evaluate(()=>Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6,[role="heading"]')).some(e=>/^(Node details|Relationship details|Results overview)$/.test(e.textContent.trim())&&e.getBoundingClientRect().height>0));
 const graphButton=name=>({css:`button[aria-label="${name}"]`});
 async function graphPoint(label,edge=false,allowOutside=false){let now;for(let i=0;i<25;i++){try{const before=await serial(()=>p.evaluate(graphTarget,{label,edge,allowOutside}));await sleep(150);now=await serial(()=>p.evaluate(graphTarget,{label,edge,allowOutside}));if(Math.hypot(before.x-now.x,before.y-now.y)<1)return now;}catch(e){if(i===24)throw e;}await sleep(80);}throw Error('Unstable graph target '+label);}
 async function chooseGraph(c,a,g){if(!await serial(hasDetails)){await act(graphButton('Toggle graph details panel'),true);}let target=cfg.readable?await focusReadableGraph({p,serial,move,graphPoint,act,label:c.label,edge:c.op==='edge',clickHere,gate:g,guided:c.guided_focus,first:c.id==='forest012'}):await graphPoint(c.label,c.op==='edge');if(c.guided_focus)await g(c.id==='forest012'?.86:.81);await move(target);target=await graphPoint(c.label,c.op==='edge');if(Math.hypot(pos.x-target.x,pos.y-target.y)>2)await move(target);await clickHere();a.clickAt=Date.now()-start;await serial(()=>p.waitForFunction(({verify})=>{const h=Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6,[role="heading"]')).find(e=>/^(Node details|Relationship details)$/.test(e.textContent.trim())&&e.getBoundingClientRect().height>0);return h?.parentElement?.parentElement?.innerText.includes(verify);},{verify:c.verify},{timeout:10000}));a.details=await serial(()=>p.evaluate(()=>{const h=Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6,[role="heading"]')).find(e=>/^(Node details|Relationship details)$/.test(e.textContent.trim())&&e.getBoundingClientRect().height>0);return h.parentElement.parentElement.innerText;}));a.selectionVerified=true;a.selectionReady=Date.now()-start;}
 let graph=false;
 const activeCues=spec.cues.filter(c=>!cfg.only||cfg.only.includes(c.id));
 for(const c of activeCues){
  await cue(c.id,async(g,a)=>{
   a.op=c.op;
   switch(c.op){
    case 'intro':await g(.15);await move({x:500,y:240});break;
    case 'connect':
     await g(.2);await act({css:'.ndl-select-control'});
     await g(.32);await act({css:'input[name="hostname"]'});
     await g(.52);await act({css:'input[name="username"]'});
     await g(.68);await act({css:'input[name="password"]'});
     await g(.88);await act({text:'Connect'},true);
     await serial(()=>p.waitForFunction(()=>!!document.querySelector('[data-testid="connection-status-indicator-success"]')&&document.body.innerText.includes('neo4j'),undefined,{timeout:15000}));
     break;
    case 'connected':await g(.12);await act({css:'[data-testid="instance-menu-button"]'});await g(.4);await act({css:'[data-testid="database-menu-button"]'});break;
    case 'clear':
     await g(.25);await input(':clear');await g(.65);await serial(()=>p.keyboard.press('Enter'));
     await serial(()=>p.waitForFunction(()=>!document.querySelector('[role="table"]')&&!document.querySelector('[data-testid="nvl-c2d-canvas"]')&&!document.body.innerText.includes(':welcome'),undefined,{timeout:10000}));
     await serial(()=>p.keyboard.press('ControlOrMeta+A'));await serial(()=>p.keyboard.press('Backspace'));graph=false;break;
    case 'overview':
     if(await serial(()=>p.evaluate(()=>!!document.querySelector('button[title="Open Sidebar"]')))){await g(.12);await act({css:'button[title="Open Sidebar"]'},true);}
     await g(.25);await act({css:'button[title="Collapse Sidebar"]'},true);await g(.45);await act({css:'button[title="Open Sidebar"]'},true);
     await g(.7);await act({css:'button[aria-label="Database overview"]'},true);break;
    case 'overviewResult':
     await g(.12);await act({css:'button[aria-label="All Nodes"]'});await g(.6);await act({css:'button[aria-label="All Relationships"]'});break;
    case 'editorTour':await g(.12);await act(editor);await g(.4);await act(runButton);await g(.7);await move({x:900,y:270});break;
    case 'query':await g(.15);await input(c.query);a.query=c.query;break;
    case 'editorPoint':await g(.15);await move({x:700,y:110+(c.line-1)*12});break;
    case 'run':
     const previous=await serial(()=>p.evaluate(()=>document.querySelector('[role="table"]')?.innerText||''));await g(.43);await act(runButton,true);a.runAt=Date.now()-start;
     await serial(()=>p.waitForFunction(({rows,graph,previous,nodes,edges})=>graph?Array.from(document.querySelectorAll('[role="status"]')).find(e=>e.textContent.startsWith('A graph visualization'))?.textContent.includes(`with ${nodes} ${nodes===1?"node":"nodes"} and ${edges} ${edges===1?"relationship":"relationships"}`):Array.from(document.querySelector('[role="table"]')?.querySelectorAll('[role="row"]')||[]).filter(e=>e.querySelector('[role="cell"]')).length===rows&&(document.querySelector('[role="table"]')?.innerText||'')!==previous,{rows:c.rows,graph:c.graph,previous,nodes:c.nodes,edges:c.edges},{timeout:15000}));
     a.resultVerified=true;a.nodes=c.nodes;a.edges=c.edges;a.rows=c.rows;a.resultReady=Date.now()-start;graph=c.graph;break;
    case 'result':await g(.15);await resultPoint();break;
    case 'mapLayout':
     await g(.12);await act({css:'button[title="Collapse Sidebar"]'},true);
     if(await serial(hasDetails))await act(graphButton('Toggle graph details panel'),true);
     await g(.4);await act(graphButton('Select layout'),true);await act({css:'[role="menuitemradio"]',text:'Hierarchical layout'},true);
     await g(.7);await act(graphButton('Zoom to fit'),true);break;
    case 'node':case 'edge':await g(.08);await chooseGraph(c,a,g);break;
    case 'details':
     await g(.2);const prop=await serial(()=>p.evaluate(()=>{const h=Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6,[role="heading"]')).find(e=>/^(Node details|Relationship details)$/.test(e.textContent.trim())&&e.getBoundingClientRect().height>0);const r=h?.parentElement?.parentElement?.getBoundingClientRect();return r&&{x:r.x+Math.min(r.width-30,140),y:r.y+150};}));if(prop)await move(prop);break;
    case 'mapTour':case 'graphTalk':
     for(let i=0;i<(c.points||[]).length;i++){await g(.15+i*.2);await move(await graphPoint(c.points[i]));}break;
    case 'png':
     await g(.15);if(await serial(hasDetails))await act(graphButton('Toggle graph details panel'),true);
     const blank=await serial(()=>p.evaluate(()=>{const r=document.querySelector('[data-testid="nvl-c2d-canvas"]').getBoundingClientRect();return {x:r.x+35,y:r.y+30};}));await move(blank);await clickHere();
     await g(.45);await act(graphButton('Zoom to fit'),true);await g(.68);const pngWait=p.waitForEvent('download',{timeout:15000});await act(graphButton('Download as PNG'),true);const png=await pngWait;a.png=out+'/'+png.suggestedFilename();await png.saveAs(a.png);break;
    case 'graphResult':await g(.15);await move({x:850,y:330});break;
    case 'newSaved':
     await g(.12);if(await serial(()=>p.evaluate(()=>!!document.querySelector('button[title="Open Sidebar"]'))))await act({css:'button[title="Open Sidebar"]'},true);await g(.32);await act({css:'button[aria-label="Queries"]'},true);await g(.55);await act({css:'button[aria-label="Add new tab"]'},true);break;
    case 'saveText':await g(.16);await input(spec.saved_query);await serial(()=>p.keyboard.press('ControlOrMeta+Home'));a.savedText=true;break;
    case 'reopen':
     await serial(()=>p.waitForSelector('[role="group"][aria-label="설비 연결 탐색"]',{timeout:10000}));
     await g(.3);await act({css:'button[aria-label="Close tab"]'},true);
     await g(.57);await act({css:'[role="group"][aria-label="설비 연결 탐색"]'},true);
     await serial(()=>p.waitForFunction(()=>Array.from(document.querySelectorAll('[aria-label="Cypher Editor"]')).some(e=>e.getBoundingClientRect().height>0&&e.innerText.includes('설비 연결 탐색')),undefined,{timeout:10000}));a.reopened=true;break;
    case 'download':
     await g(.73);const waiting=p.waitForEvent('download',{timeout:15000});await act({css:'button[aria-label="Download all"]'},true);
     const d=await waiting;savedDownload=out+'/'+d.suggestedFilename();await d.saveAs(savedDownload);a.download=savedDownload;break;
    case 'savedResult':await g(.1);await act({css:'[role="group"][aria-label="설비 연결 탐색"]'});break;
    case 'outro':await g(.1);await move({x:900,y:300});break;
   }
  });
  await fs.writeFile(out+'/progress.json',JSON.stringify({lastCue:c.id,completed:actions.length,frames:frames.length,elapsed_ms:Date.now()-start}));
  console.log('captured '+c.id+' '+c.op);
 }
}catch(e){error=String(e);}
done=true;await capture;await writes;await p.cdp('Page.stopScreencast');
const duration=Date.now()-start;
await fs.writeFile(out+'/timing.json',JSON.stringify({start,duration,frames,motions,actions,error,result:error?null:'result explanation segment captured'},null,2));
await fs.writeFile(out+'/end-state.json',JSON.stringify({url:await p.url(),pointer:pos,clicks:await p.evaluate(()=>window.__recordClicks||[]),targets},null,2));
console.log({frames:frames.length,duration,error});
