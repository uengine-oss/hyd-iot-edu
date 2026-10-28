// 실전 3-1 구간 2(포털): 조건별 손익 → HYD-01 · 쿨러 성능 저하 불러오기 → 요약 · 카드 · 미확인 → 팬 최대 운전 항목별 손익 · 출처.
// 시작 상태: 녹화 공간 「portal rec 20261028」(1536x864 dsf1.5), 포털 홈, 「나」 비움, 조건별 손익 미방문(설비 HYD-01 · 패턴 첫 항목).
import {vscode} from '../ui.mjs';
import {portal} from './p31-common.mjs';
export default async ctx=>{
 const c=await vscode(ctx), p=portal(ctx,c);
 await c.installPointer({x:760,y:430});
 await ctx.begin();
 await ctx.say('p31-06',()=>c.clickSel('button[data-tab=whatif]'),{at:'조건별 손익을 누릅니다'});
 await ctx.waitFor(()=>!!document.querySelector('#wiLoad')&&!document.querySelector('#wiLoad').disabled,30000);
 await ctx.say('p31-07',async()=>{await c.hoverSel('#wiAsset');await ctx.sleep(700);await c.hoverSel('#wiPattern');await ctx.sleep(700);await c.clickSel('#wiLoad');},{pointFrac:0.1});
 await p.loaded();
 await ctx.say('p31-08',async()=>{await p.hover({sel:'.summary p',text:'판단 1순위'});await ctx.sleep(2500);await p.hover({sel:'.card-chips .chip',text:'손익 1순위'});},{pointFrac:0.1});
 await ctx.say('p31-09',async()=>{await p.hover({sel:'.card-chips .chip',text:'판단 1위',within:'쿨러 핀 세척'},0.35);await ctx.sleep(1800);await p.hover({sel:'.card-value .kv',text:'미확인',within:'쿨러 핀 세척'});},{pointFrac:0.2});
 await ctx.say('p31-10',()=>p.hover({sel:'.card-sub',text:'계산하지 못한 항목',within:'쿨러 핀 세척'}),{pointFrac:0.05});
 await ctx.say('p31-11',()=>p.click({sel:'details > summary',text:'항목별 손익',within:'팬 최대 운전'},0.3));
 await ctx.say('p31-12',async()=>{
  await p.hover({sel:'tbody tr',text:'고장 위험',within:'팬 최대 운전'},0.45);await ctx.sleep(3200);
  await p.hover({sel:'tbody tr',text:'에너지비',within:'팬 최대 운전'});await ctx.sleep(3200);
  await p.hover({sel:'tbody tr td',text:'데이터 업무 DB EMS',within:'팬 최대 운전'});
 },{pointFrac:0.12});
 await ctx.say('p31-13',()=>p.hover({sel:'.card-value .kv',text:'−',within:'팬 최대 운전'}),{pointFrac:0.3});
 return 'p31-2 done';
};
