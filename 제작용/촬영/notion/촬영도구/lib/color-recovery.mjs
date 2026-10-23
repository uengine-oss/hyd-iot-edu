import {calloutHandle} from './block-handle.mjs';
export async function correctHandle(c,prefix){c.activeCalloutPrefix=prefix;const q=await calloutHandle(c,prefix);await c.serial(()=>c.p.mouse.click(q.x,q.y));await c.serial(()=>c.p.waitForSelector('[role=dialog]',{state:'visible'}));}
async function deprecatedHandle(c,prefix){
 const selector=await c.serial(()=>c.p.evaluate(prefix=>{const n=[...document.querySelectorAll('[role=note]')].find(e=>e.textContent.startsWith(prefix));if(!n)throw Error('Callout missing '+prefix);return '[data-block-id="'+n.closest('.notion-callout-block').getAttribute('data-block-id')+'"]';},prefix));
 await c.serial(()=>c.p.hover(selector));
 for(let i=0;i<8;i++){
  const r=await c.serial(()=>c.p.evaluate(s=>{const r=document.querySelector(s).getBoundingClientRect();return {x:r.x-8,y:r.y+22,top:r.top};},selector));
  await c.move(r.x,r.y);await c.sleep(350);
  const h=await c.locate('aria','드래그하여 이동하고 클릭하여 메뉴를 여세요');
  if(Math.abs(h.y-r.y)<30&&h.x<r.x){await c.move(h.x,h.y);await c.serial(()=>c.p.mouse.click(h.x,h.y));await c.sleep(400);return;}
 }
 throw Error('Callout handle did not align');
}
export async function recover(c){
 await c.say('live-color-recovery');
 for(const [prefix,color,voice] of [['짧게 적고','파란색 배경','live-color-intro-blue'],['01 ·','회색 배경','live-color-first-gray'],['02 ·','회색 배경','live-color-second-gray']]){
  await c.say(voice,async()=>{await correctHandle(c,prefix);await c.hoverColor(color);await c.click('menu',color);});
 }
 await c.fs.writeFile(c.out+'/recovered-colors.json',JSON.stringify(await c.serial(()=>c.p.evaluate(()=>[...document.querySelectorAll('[role=note]')].map(e=>({text:e.textContent,color:getComputedStyle(e.firstElementChild).backgroundColor})))),null,2));
}
