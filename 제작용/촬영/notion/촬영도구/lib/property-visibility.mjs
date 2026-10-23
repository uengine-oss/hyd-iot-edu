function state(name){for(const b of document.querySelectorAll('[role=dialog] [aria-label="속성 표시 토글"]')){let e=b.parentElement;for(let i=0;i<7&&e;i++,e=e.parentElement)if(e.textContent.trim()===name&&e.querySelectorAll('[aria-label="속성 표시 토글"]').length===1){const r=b.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2,hidden:!!b.querySelector('svg')?.getAttribute('class')?.includes('eyeSlash')};}}throw Error('Property eye missing '+name);}
export async function hideProperty(c,name){
 for(let i=0;i<5;i++){
  const q=await c.serial(()=>c.p.evaluate(state,name));if(q.hidden)return;
  await c.move(q.x,q.y);const now=await c.serial(()=>c.p.evaluate(state,name));if(Math.hypot(q.x-now.x,q.y-now.y)>2)continue;
  await c.serial(()=>c.p.mouse.click(now.x,now.y));
  for(let j=0;j<30;j++){await c.sleep(200);if((await c.serial(()=>c.p.evaluate(state,name))).hidden)return;}
  throw Error('Property did not hide: '+name);
 }
 throw Error('Property layout did not settle: '+name);
}
