export function currentMotion(c){
 c.move=async(x,y)=>{
  const start=Date.now();
  const a=await c.serial(()=>c.p.evaluate(()=>{const r=document.getElementById('recording-pointer')?.getBoundingClientRect();return r?{x:r.x,y:r.y}:{x:0,y:0};}));
  for(let i=1;i<=16;i++){const t=i/16,u=t*t*(3-2*t);await c.serial(()=>c.p.mouse.move(a.x+(x-a.x)*u,a.y+(y-a.y)*u,{steps:1}));await c.sleep(5);}
  c.recordMotion?.({start,end:Date.now(),x,y});await c.sleep(180);
 };return c;
}
