// 진단: 실제 마우스 입력 없이 화살표 애니메이션만 6번(같은 경로 · 같은 시간). 이동 기록은 직접 남긴다.
export default async function(ctx){
 await ctx.p.click('.rail nav button[data-tab="knowledge"]');await ctx.sleep(1200);
 await ctx.begin();
 let a={x:768,y:432};
 for(const [x,y] of [[300,200],[900,500],[500,650],[1100,150],[700,400],[250,600]]){
  const ms=Math.round(Math.max(260,Math.min(620,200+Math.hypot(x-a.x,y-a.y)*0.4)));const t0=Date.now();
  await ctx.p.evaluate(({ax,ay,x,y,ms})=>window.__startGlide(ax,ay,x,y,ms),{ax:a.x,ay:a.y,x,y,ms});
  await ctx.sleep(ms+40);ctx.recordMotion({start:t0,end:Date.now(),x,y,from:a,planned_ms:ms});a={x,y};await ctx.sleep(600);
 }
}
