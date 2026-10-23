export function stableRoles(c){c.role=async(role,name)=>{
 for(let attempt=0;attempt<40;attempt++){
  const q=await c.serial(()=>c.p.evaluate(({role,name})=>{const es=[...document.querySelectorAll(`[role="${role}"]`)].filter(e=>{const r=e.getBoundingClientRect();return e.checkVisibility({checkVisibilityCSS:true})&&r.width&&r.height&&r.top>=0&&r.bottom<=innerHeight&&(e.getAttribute('aria-label')===name||e.textContent.trim()===name);});if(!es.length)return null;if(es.length!==1)throw Error('Ambiguous role '+role+' '+name);const r=es[0].getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+r.height/2};},{role,name}));
  if(!q){await c.sleep(250);continue;}
  await c.move(q.x,q.y);await c.serial(()=>c.p.mouse.click(q.x,q.y));await c.sleep(350);return;
 }
 throw Error('Role did not become ready: '+role+' '+name);
};return c;}
