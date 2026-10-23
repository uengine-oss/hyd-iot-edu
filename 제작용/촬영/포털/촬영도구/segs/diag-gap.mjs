// 진단(본 촬영 아님): 같은 이동 6번을 두 화면에서 하며 페이지 긴 작업(50ms 이상)을 기록한다.
import {portal} from '../ui.mjs';
export default async function(ctx){
 const c=await portal(ctx);
 await ctx.p.evaluate(()=>{window.__lt=[];new PerformanceObserver(l=>{for(const e of l.getEntries())window.__lt.push({s:Math.round(e.startTime),d:Math.round(e.duration)});}).observe({type:'longtask',buffered:false});});
 const out={};
 for(const tab of ['knowledge','scenario']){
  await ctx.p.click(`.rail nav button[data-tab="${tab}"]`);await ctx.sleep(1500);
  if(tab==='knowledge')await ctx.begin();
  const t0=await ctx.p.evaluate(()=>performance.now());
  for(const [x,y] of [[300,200],[900,500],[500,650],[1100,150],[700,400],[250,600]])await ctx.silent(tab+x,'이동 시험입니다.',()=>c.move(x,y));
  out[tab]={t0,lt:await ctx.p.evaluate(t0=>window.__lt.filter(e=>e.s>=t0),t0)};
 }
 return out;
}
