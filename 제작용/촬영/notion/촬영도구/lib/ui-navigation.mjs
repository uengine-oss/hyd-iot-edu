import {lesson} from './ui-lesson.mjs';
import {reveal} from './reveal.mjs';
export async function navigation(ctx){
 const c=await lesson(ctx);
 c.scroll=async dy=>{const q=await c.serial(()=>c.p.evaluate(()=>({x:innerWidth*.7,y:innerHeight*.65})));await c.move(q.x,q.y);await c.serial(()=>c.p.mouse.wheel(0,dy));await c.sleep(350);};
 c.home=async()=>{await c.link('내 학습 노트',true);await c.sleep(400);await c.scroll(400);};
 c.revealText=async text=>{const selector=await c.serial(()=>c.p.evaluate(text=>{const e=[...document.querySelectorAll('[contenteditable=true][role=textbox]')].find(e=>e.textContent.trim()===text&&e.getBoundingClientRect().height);if(!e)throw Error('Text missing '+text);return '#'+CSS.escape(e.id);},text));await reveal(c,selector);};
 c.endText=async text=>{await c.revealText(text);const q=await c.serial(()=>c.p.evaluate(text=>{
  const e=[...document.querySelectorAll('[contenteditable=true][role=textbox]')].find(e=>e.textContent.trim()===text&&e.getBoundingClientRect().height);
  if(!e)throw Error('Text field missing: '+text);const w=document.createTreeWalker(e,NodeFilter.SHOW_TEXT);let n,last;while(n=w.nextNode())if(n.length)last=n;
  const r=document.createRange();r.setStart(last,last.length-1);r.setEnd(last,last.length);const b=[...r.getClientRects()].at(-1);return{x:b.right+1,y:b.top+b.height/2,id:e.id};
 },text));await c.move(q.x,q.y);await c.serial(()=>c.p.mouse.click(q.x,q.y));await c.serial(()=>c.p.waitForFunction(id=>{const e=document.getElementById(id),s=getSelection();if(!e||!s?.isCollapsed||!e.contains(s.anchorNode))return false;const r=document.createRange();r.selectNodeContents(e);r.setEnd(s.anchorNode,s.anchorOffset);return r.toString().length===e.textContent.length;},q.id,{timeout:6000}));};
 c.selectText=async text=>{
  await c.revealText(text);
  const q=await c.serial(()=>c.p.evaluate(text=>{
   const e=[...document.querySelectorAll('[contenteditable=true][role=textbox]')].find(e=>e.textContent.trim()===text&&e.getBoundingClientRect().height);if(!e)throw Error('Selection text missing');
   const w=document.createTreeWalker(e,NodeFilter.SHOW_TEXT),nodes=[];let n;while(n=w.nextNode())if(n.length)nodes.push(n);
   const a=document.createRange(),b=document.createRange();a.setStart(nodes[0],0);a.setEnd(nodes[0],1);const last=nodes.at(-1);b.setStart(last,last.length-1);b.setEnd(last,last.length);
   const ar=a.getBoundingClientRect(),br=b.getBoundingClientRect();return{start:{x:ar.left,y:ar.top+ar.height/2},end:{x:br.right+1,y:br.top+br.height/2}};
  },text));await c.move(q.start.x,q.start.y);await c.serial(()=>c.p.mouse.down());await c.move(q.end.x,q.end.y);await c.serial(()=>c.p.mouse.up());
 };
 // 링크가 화면 아래 끝에 걸쳐 있으면(상단 막대 등으로 본문이 밀린 경우, 2026-10-23 n39) 휠로 보이게 내린 뒤 한 번 더 찾는다.
 const findLink=(text,top)=>c.serial(()=>c.p.evaluate(({text,top})=>{
  const all=[...document.querySelectorAll('a,[role=link]')].filter(e=>e.checkVisibility({checkVisibilityCSS:true})&&e.textContent.trim()===text&&e.getBoundingClientRect().width>0);
  const es=all.filter(e=>{const r=e.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&r.top>=0&&r.bottom<=innerHeight&&(!top||r.top<65);}).sort((a,b)=>a.getBoundingClientRect().top-b.getBoundingClientRect().top);
  if(!es.length){const below=!top&&all.map(e=>e.getBoundingClientRect()).find(r=>r.bottom>innerHeight&&r.top<innerHeight*2);if(below)return{scroll:Math.ceil(below.bottom-innerHeight*0.6)};throw Error('Link missing: '+text);}
  const r=es[0].getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2,href:es[0].getAttribute('href')};
 },{text,top}));
 c.link=async(text,top=false)=>{let q=await findLink(text,top);if(q.scroll){await c.scroll(q.scroll);q=await findLink(text,top);if(q.scroll)throw Error('Link still off screen: '+text);}await c.move(q.x,q.y);await c.serial(()=>c.p.mouse.click(q.x,q.y));if(q.href)await c.serial(()=>c.p.waitForFunction(href=>location.pathname===new URL(href,location.href).pathname,q.href,{timeout:10000}));await c.sleep(400);};
 return c;
}
