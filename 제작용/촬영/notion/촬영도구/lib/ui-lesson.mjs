import {native} from './ui-native.mjs';
import {calloutHandle} from './block-handle.mjs';
import {reveal} from './reveal.mjs';
export async function lesson(ctx){
 const c=await native(ctx);const lib=JSON.parse(await c.fs.readFile(c.cueFile,'utf8'));
 const baseClick=c.click;c.click=async(kind,value)=>{await baseClick(kind,value);if(kind==='menu'&&['파란색 배경','회색 배경'].includes(value)&&c.activeCalloutPrefix){const target={prefix:c.activeCalloutPrefix,color:value==='파란색 배경'?'rgb(229, 242, 252)':'rgb(249, 248, 247)'};await c.serial(()=>c.p.waitForFunction(({prefix,color})=>[...document.querySelectorAll('[role=note]')].some(e=>e.textContent.startsWith(prefix)&&getComputedStyle(e.firstElementChild).backgroundColor===color),target,{timeout:8000}));}};
 c.park=async()=>{const q=await c.serial(()=>c.p.evaluate(()=>({x:innerWidth-38,y:90})));await c.move(q.x,q.y);};
 c.source=async(id,fn)=>{const x=lib.find(x=>x.source_action===id);if(!x)throw Error('Unknown source cue '+id);return c.say(x.id,fn);};
 c.line=async(text,fn)=>{const x=lib.find(x=>x.text===text);if(!x)throw Error('Unknown source sentence');return c.say(x.id,fn);};
 c.endOf=async selector=>{
  await reveal(c,selector+' >> nth=-1');
  const q=await c.serial(()=>c.p.evaluate(selector=>{
   const e=[...document.querySelectorAll(selector)].filter(e=>e.getBoundingClientRect().width).at(-1);if(!e)throw Error('End target missing');
   const w=document.createTreeWalker(e,NodeFilter.SHOW_TEXT);let n,last;while(n=w.nextNode())if(n.textContent.length)last=n;
   if(!last)throw Error('No text to position caret');const r=document.createRange();r.setStart(last,Math.max(0,last.length-1));r.setEnd(last,last.length);const b=[...r.getClientRects()].at(-1);return{x:b.right+1,y:b.top+b.height/2,id:e.id};
  },selector));await c.move(q.x,q.y);await c.serial(()=>c.p.mouse.click(q.x,q.y));
  await c.serial(()=>c.p.waitForFunction(id=>{const e=document.getElementById(id),s=getSelection();if(!e||!s?.isCollapsed||!e.contains(s.anchorNode))return false;const r=document.createRange();r.selectNodeContents(e);r.setEnd(s.anchorNode,s.anchorOffset);return r.toString().length===e.textContent.length;},q.id,{timeout:6000}));
 };
 c.noteHandle=async()=>{
  const prefix=await c.serial(()=>c.p.evaluate(()=>[...document.querySelectorAll('[role=note]')].at(-1).textContent));
  c.activeCalloutPrefix=prefix;
  const q=await calloutHandle(c,prefix);await c.serial(()=>c.p.mouse.click(q.x,q.y));
  await c.serial(()=>c.p.waitForSelector('[role=dialog]',{state:'visible'}));
 };
 c.hoverColor=async name=>{
  await c.click('menu','색');const parent=await c.locate('menu','색');
  for(let i=0;i<12;i++){
   const q=await c.serial(()=>c.p.evaluate(name=>{const e=[...document.querySelectorAll('[role=menuitem]')].find(e=>e.textContent.trim()===name);if(!e)return null;const r=e.getBoundingClientRect();let top=10,bottom=innerHeight-10;for(let a=e.parentElement;a;a=a.parentElement){const s=getComputedStyle(a);if(/auto|scroll|hidden/.test(s.overflowY)){const b=a.getBoundingClientRect();top=Math.max(top,b.top);bottom=Math.min(bottom,b.bottom);}}return{x:r.x+r.width/2,y:r.y+r.height/2,top,bottom,h:innerHeight};},name));
   if(!q){await c.sleep(150);continue;}
   await c.move(q.x,Math.max(q.top+30,Math.min(parent.y,q.bottom-30)));
   if(q.y>q.bottom-20){await c.serial(()=>c.p.mouse.wheel(0,Math.min(440,q.y-q.bottom+80)));await c.sleep(200);continue;}
   if(q.y<q.top+20){await c.serial(()=>c.p.mouse.wheel(0,q.y-q.top-80));await c.sleep(200);continue;}
   await c.move(q.x,q.y);return;
  }
  throw Error('Color item not reached: '+name);
 };
 return c;
}
