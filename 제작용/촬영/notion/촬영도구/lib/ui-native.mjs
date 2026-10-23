import {extend} from './ui-robust.mjs';
import {currentMotion} from './motion-current.mjs';
import {stableRoles} from './role-stable.mjs';
export async function native(ctx){
 const c=currentMotion(extend(ctx));
 c.installPointer=async()=>c.serial(()=>c.p.evaluate(()=>{
  document.removeEventListener('mousemove',window.__tutorialMove,true);document.removeEventListener('mousedown',window.__tutorialDown,true);document.getElementById('recording-pointer')?.remove();
  const e=document.createElement('div');e.id='recording-pointer';e.setAttribute('aria-hidden','true');e.style.cssText='position:fixed;left:0;top:0;width:14px;height:19px;pointer-events:none;z-index:2147483647;will-change:transform;';
  e.innerHTML='<svg xmlns="http://www.w3.org/2000/svg" width="14" height="19" viewBox="0 0 25 34"><path d="M1 1 L1 25 L7 20 L12 31 L17 29 L12 18 L22 18 Z" fill="white" stroke="#111" stroke-width="1.7" stroke-linejoin="round"/></svg>';
  document.documentElement.append(e);window.__tutorialClicks??=[];
  window.__tutorialMove=ev=>e.style.transform=`translate(${ev.clientX}px,${ev.clientY}px)`;
  window.__tutorialDown=ev=>{const r=e.getBoundingClientRect();window.__tutorialClicks.push({x:ev.clientX,y:ev.clientY,px:r.x,py:r.y,trusted:ev.isTrusted,time:performance.now()});};
  document.addEventListener('mousemove',window.__tutorialMove,true);document.addEventListener('mousedown',window.__tutorialDown,true);
 }));
 c.park=async()=>{const q=await c.serial(()=>c.p.evaluate(()=>({x:innerWidth-38,y:90})));await c.move(q.x,q.y);};
 c.navigate=async url=>{await c.serial(()=>c.p.goto(url));await c.installPointer();await c.serial(async()=>{await c.p.cdp('Page.stopScreencast');await c.p.cdp('Page.startScreencast',{format:'jpeg',quality:85,maxWidth:1920,maxHeight:1080,everyNthFrame:1});});};
 c.type=async text=>{
  if((await c.serial(()=>c.p.url())).includes('3bcf0e285bb4806f93c1cc2ace1f0836'))throw Error('Preserved original: typing forbidden');
  let focus;
  for(let attempt=0;attempt<20;attempt++){
   focus=await c.serial(()=>c.p.evaluate(()=>{const e=document.activeElement;return {editable:!!(e?.isContentEditable||e?.matches('input,textarea')),ai:!!e?.closest('[data-testid="agent-chat-view"]')||!!e?.getAttribute('placeholder')?.includes('AI로')};}));
   if(focus.editable||focus.ai)break;await c.sleep(200);
  }
  if(!focus.editable||focus.ai)throw Error('Typing target is not the intended editor: '+JSON.stringify(focus));
  if(c.rehearsal&&!text.startsWith('/')){await c.serial(()=>c.p.keyboard.insertText(text));return;}
  await c.park();let i=0;for(const ch of text){await c.serial(()=>c.p.keyboard.insertText(ch));await c.sleep([105,125,95,135,110][i++%5]);}
 };
 c.role=async(role,name)=>{
  const q=await c.serial(()=>c.p.evaluate(({role,name})=>{
   const es=[...document.querySelectorAll(`[role="${role}"]`)].filter(e=>{const r=e.getBoundingClientRect();return r.width&&r.height&&r.top>=0&&r.bottom<=innerHeight&&(e.getAttribute('aria-label')===name||e.textContent.trim()===name)});
   if(es.length!==1)throw Error('Role match '+role+' '+name+': '+es.length);const r=es[0].getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2};
  },{role,name}));await c.move(q.x,q.y);await c.serial(()=>c.p.mouse.click(q.x,q.y));await c.sleep(350);
 };
 return stableRoles(c);
}
