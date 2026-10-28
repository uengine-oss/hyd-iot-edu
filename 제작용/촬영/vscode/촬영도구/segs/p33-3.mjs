// 실전 3-3 구간 3(포털): 지식 관리에서 HM-8 등록만 확인 → 결함 시뮬레이션 HYD-01 카드에서 현재 값(유온 · CE · 팬 속도 · 운전 모드) 읽기.
// 시작 상태: 구간 2 끝(지식 지도, SOP-COOL-14 상세).
import {vscode} from '../ui.mjs';
import {portal} from './p31-common.mjs';
export default async ctx=>{
 const c=await vscode(ctx), p=portal(ctx,c);
 const unit='[data-asset="HYD-01"]';
 await ctx.begin();
 await ctx.say('p33-22',async()=>{await p.menu('knowledge');},{at:'지식 관리를 엽니다'});
 await ctx.waitFor(()=>[...document.querySelectorAll('section.card h3 a')].some(a=>a.textContent.trim()==='HM-8_cooler-fan-manual.md'),30000);
 await ctx.say('p33-23',async()=>{await p.hover({sel:'section.card h3 a',text:'HM-8_cooler-fan-manual.md',exact:true},0.35);},{pointFrac:0.1});
 await ctx.say('p33-24',async()=>{await p.menu('scenario');await ctx.waitFor(()=>!!document.querySelector('[data-asset="HYD-01"] .big .v'));await p.top();},{at:'결함 시뮬레이션을 엽니다'});
 await ctx.say('p33-25',async()=>{
  await p.hover({sel:`${unit} .big .v`},0.3);await ctx.sleep(1400);
  await p.hover({sel:`${unit} em.ce`},0.4);await ctx.sleep(1200);
  await p.hover({sel:`${unit} em.fan`},0.4);await ctx.sleep(1200);
  await p.hover({sel:`${unit} header .mode`},0.3);
 },{pointFrac:0.05});
 return 'p33-3 done';
};
