// Adapted from the verified short sample; portable variant has not been UI-tested.
const fs=await import('node:fs/promises');const path=await import('node:path');
const cfg=JSON.parse(await fs.readFile(new URL('./recording.config.json',import.meta.url),'utf8'));
if(!Number.isInteger(cfg.spaceId)||cfg.spaceId<1||typeof cfg.pageLabel!=='string')throw Error('Set observed spaceId and pageLabel first');
if(typeof cfg.outputDir!=='string'||!path.isAbsolute(cfg.outputDir))throw Error('outputDir must be absolute');
for(const k of ['captionInputIndex','radiusInputIndex'])if(!Number.isInteger(cfg[k])||cfg[k]<0)throw Error('Invalid input index: '+k);
for(const k of ['caption','radius','suffix'])if(typeof cfg[k]!=='string')throw Error('Invalid scene value: '+k);
const root=cfg.outputDir;await fs.mkdir(path.dirname(root),{recursive:true});await fs.mkdir(root);
const task=await taskSpace(cfg.spaceId);const page=task.page(cfg.pageLabel);
if(!(await page.url()).startsWith('https://arrows.app/'))throw Error('This example is for arrows.app only');
await fs.mkdir(root+'/smooth-frames',{recursive:true});
await page.cdp('Emulation.setDeviceMetricsOverride',{width:1280,height:800,deviceScaleFactor:1,mobile:false});
await page.evaluate(()=>{
document.getElementById('recording-pointer')?.remove();
const el=document.createElement('div');el.id='recording-pointer';el.setAttribute('aria-hidden','true');
el.style.cssText='position:fixed;left:0;top:0;width:25px;height:34px;pointer-events:none;z-index:2147483647;transform:translate(790px,420px)';
el.innerHTML='<svg xmlns="http://www.w3.org/2000/svg" width="25" height="34" viewBox="0 0 25 34"><path d="M1 1 L1 25 L7.3 19.7 L12.3 31 L17.1 28.8 L12.1 18.2 L21.2 18.2 Z" fill="white" stroke="#111" stroke-width="1.7" stroke-linejoin="round"/></svg>';
document.documentElement.append(el);window.__recordingEvents=[];
const move=e=>{el.style.transform=`translate(${e.clientX}px,${e.clientY}px)`;};
const down=e=>{const r=el.getBoundingClientRect();window.__recordingEvents.push({type:'down',x:e.clientX,y:e.clientY,pointerX:r.x,pointerY:r.y,trusted:e.isTrusted,time:performance.now()});};
document.addEventListener('mousemove',move,true);document.addEventListener('mousedown',down,true);
window.__removeRecordingPointer=()=>{document.removeEventListener('mousemove',move,true);document.removeEventListener('mousedown',down,true);el.remove();};
});
await page.mouse.move(790,420,{steps:1});
await page.waitForTimeout(500);
await page.cdp('Page.startScreencast',{format:'jpeg',quality:90,maxWidth:1280,maxHeight:800,everyNthFrame:1});
let chain=Promise.resolve();function serial(fn){const r=chain.then(fn);chain=r.catch(()=>{});return r;}
const frames=[];const actions=[];let done=false;const start=Date.now();const sleep=ms=>new Promise(r=>setTimeout(r,ms));
let recordingError=null;const record=(async()=>{while(!done){const events=await serial(()=>page.events());for(const e of events)if(e.method==='Page.screencastFrame'){
const file=`smooth-frames/${String(frames.length).padStart(5,'0')}.jpg`;await fs.writeFile(root+'/'+file,Buffer.from(e.params.data,'base64'));frames.push({file,time:Date.now()-start,sourceTimestamp:e.params.metadata.timestamp});await fs.appendFile(root+'/frames.jsonl',JSON.stringify(frames.at(-1))+'\n');await serial(()=>page.cdp('Page.screencastFrameAck',{sessionId:e.params.sessionId}));
}await sleep(20);}})().catch(e=>{recordingError=e;done=true;});
async function act(name,fn){if(recordingError)throw recordingError;actions.push({name,time:Date.now()-start});return serial(fn);}
let pointerX=790,pointerY=420;
async function move(x,y){
 const fromX=pointerX,fromY=pointerY;const distance=Math.hypot(x-fromX,y-fromY);const steps=Math.max(12,Math.min(24,Math.round(distance/14)));
 const stamp={name:'move '+x+','+y,time:Date.now()-start,steps};actions.push(stamp);
 for(let i=1;i<=steps;i++){if(recordingError)throw recordingError;const t=i/steps;const eased=t*t*(3-2*t);await serial(()=>page.mouse.move(fromX+(x-fromX)*eased,fromY+(y-fromY)*eased,{steps:1}));await sleep(5);}
 pointerX=x;pointerY=y;stamp.end=Date.now()-start;await sleep(350);
}
async function inputClick(index){const pt=await serial(()=>page.evaluate(i=>{const el=document.querySelectorAll('input')[i];if(!el||el.disabled)throw Error('Configured input missing or disabled');const r=el.getBoundingClientRect();if(r.width<=0||r.height<=0||r.top<0||r.bottom>innerHeight)throw Error('Configured input is not visible; inspect the page again');return {x:r.x+r.width*.45,y:r.y+r.height/2};},index));await move(pt.x,pt.y);await act('click input '+index,()=>page.mouse.click(pt.x,pt.y));}
let actionError=null;
try{
await sleep(900);await inputClick(cfg.captionInputIndex);await act('select caption',()=>page.keyboard.press('ControlOrMeta+A'));await move(815,325);
let n=0;for(const ch of cfg.caption){await act('type '+ch,()=>page.keyboard.insertText(ch));await sleep([110,170,135,210,125][n++%5]);}
await act('commit caption',()=>page.keyboard.press('Tab'));await sleep(1100);
await inputClick(cfg.radiusInputIndex);await act('select radius',()=>page.keyboard.press('ControlOrMeta+A'));await move(815,670);
for(const ch of cfg.radius){await act('radius '+ch,()=>page.keyboard.insertText(ch));await sleep(150);}
await act('commit radius',()=>page.keyboard.press('Tab'));await move(730,450);await sleep(1700);
await inputClick(cfg.captionInputIndex);await act('caption end',()=>page.keyboard.press('End'));await move(815,325);
for(const ch of cfg.suffix){await act('type '+ch,()=>page.keyboard.insertText(ch));await sleep([130,190,120][n++%3]);}
await act('commit caption',()=>page.keyboard.press('Tab'));await move(730,450);await sleep(1800);
console.log(await serial(()=>page.snapshot()));
const clicks=await serial(()=>page.evaluate(()=>window.__recordingEvents));await fs.writeFile(root+'/smooth-clicks.json',JSON.stringify(clicks,null,2));
}catch(e){actionError=e;throw e;}finally{
done=true;await record;
await fs.writeFile(root+'/smooth-timing.json',JSON.stringify({frames,actions,duration:Date.now()-start,error:String(actionError||recordingError||'')}));
// Preserve partial capture before cleanup, which may fail after user control changes.
try{await page.cdp('Page.stopScreencast');}catch(e){await fs.appendFile(root+'/cleanup-errors.txt','stop: '+e.message+'\n');}
try{await page.evaluate(()=>window.__removeRecordingPointer?.());}catch(e){await fs.appendFile(root+'/cleanup-errors.txt','pointer: '+e.message+'\n');}
if(recordingError&&!actionError)throw recordingError;console.log({frames:frames.length,duration:Date.now()-start});
}
