// 실제 줌·빈 배경 드래그로 설명 대상을 읽을 크기로 옮긴다.
export async function focusReadableGraph({p,serial,move,graphPoint,act,label,edge,clickHere,gate,guided=false,first=false}){
 if(guided)await gate(first?.25:.1);
 const blank=await serial(()=>p.evaluate(()=>{const r=document.querySelector('[data-testid="nvl-c2d-canvas"]').getBoundingClientRect();return {x:r.x+15,y:r.y+15};}));
 await move(blank);if(clickHere)await clickHere();else await serial(()=>p.mouse.click(blank.x,blank.y));
 if(guided)await gate(first?.36:.27);
 await act({css:'button[aria-label="Zoom to fit"]'},true);
 await new Promise(r=>setTimeout(r,800));
 let pt=await graphPoint(label,edge,true);
 async function center(pt){const pan=await serial(()=>p.evaluate(pt=>{
  const c=document.querySelector('[data-testid="nvl-c2d-canvas"]'),r=c.getBoundingClientRect();
  const dx=r.x+r.width*.5-pt.x,dy=r.y+r.height*.48-pt.y;
  if(Math.hypot(dx,dy)<45)return null;
  const cs=window.__forestRead.circles.filter(x=>x.canvas===c).slice(-100);let best;
  for(let x=r.x+65;x<r.right-65;x+=55)for(let y=r.y+65;y<r.bottom-65;y+=55){
   if(x+dx<r.left+25||x+dx>r.right-25||y+dy<r.top+25||y+dy>r.bottom-25)continue;
   const dist=Math.min(...cs.map(c=>Math.hypot(x-c.x,y-c.y)-c.r));if(dist>25&&(!best||dist>best.dist))best={x,y,dx,dy,dist};
  }return best;
 },pt));
 if(pan){await move(pan);await serial(()=>p.mouse.down());await move({x:pan.x+pan.dx,y:pan.y+pan.dy});await serial(()=>p.mouse.up());}}
 if(guided)await gate(first?.48:.43);
 await center(pt);
 pt=await graphPoint(label,edge);
 if(!edge&&pt.r<48){await move(pt);await serial(()=>p.mouse.wheel(0,-Math.min(650,Math.log(52/pt.r)/.002)));await new Promise(r=>setTimeout(r,800));await center(await graphPoint(label,edge,true));}
 return await graphPoint(label,edge);
}
