export async function reveal(c,selector){
 for(let i=0;i<12;i++){
  const r=await c.serial(()=>c.p.evaluate(selector=>{const last=selector.endsWith(' >> nth=-1');const s=last?selector.slice(0,-10):selector;const es=[...document.querySelectorAll(s)].filter(e=>e.getBoundingClientRect().height);const e=last?es.at(-1):es[0];if(!e)throw Error('Reveal target missing '+selector);const r=e.getBoundingClientRect();return{x:r.x,w:r.width,top:r.top,bottom:r.bottom,h:innerHeight,iw:innerWidth};},selector));
  if(r.top>=65&&r.bottom<=r.h-25)return;
  const dy=r.top<65?r.top-100:r.bottom-r.h+60;
  await c.move(Math.max(70,Math.min(r.iw-60,r.x+r.w*.7)),r.h*.6);await c.serial(()=>c.p.mouse.wheel(0,Math.max(-500,Math.min(500,dy))));await c.sleep(220);
 }
 throw Error('Cannot reveal '+selector);
}
