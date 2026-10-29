// 실전 3-1 구간 4(포털): 결함 시뮬레이션에서 HYD-01 운전 모드 현장 제어 → 조건별 손익 다시 불러오기 → 규정상 제외 카드와 이유 → 원격 자동으로 되돌리기.
// 시작 상태: 구간 3 끝(조건별 손익 기준값으로 되돌림, HYD-01 운전 모드 원격 자동).
import {vscode} from '../ui.mjs';
import {portal} from './p31-common.mjs';
export default async ctx=>{
 const c=await vscode(ctx), p=portal(ctx,c);
 const unit='[data-asset="HYD-01"]';
 const modeIs=m=>ctx.waitFor(new Function(`return (document.querySelector('${unit} .mode')?.innerText||'').includes('${m}')`),30000);
 await ctx.begin();
 await ctx.say('p31-20',()=>p.top(),{pointFrac:0.6});
 await ctx.say('p31-21',async()=>{
  await c.clickSel('button[data-tab=scenario]');await modeIs('원격 자동');await ctx.sleep(800);
  await p.hover({sel:`${unit} header .mode`},0.35);await ctx.sleep(1400);
  await p.hover({sel:`${unit} legend`,text:'운전 모드'},0.8);
 },{at:'결함 시뮬레이션을 엽니다'});
 await ctx.say('p31-21b',()=>p.click({sel:`${unit} button[data-mode="LOCAL"]`},0.8));
 await modeIs('현장 제어');
 await ctx.say('p31-22',()=>p.hover({sel:`${unit} header .mode`},0.35),{pointFrac:0.05});
 await ctx.say('p31-23',async()=>{await c.clickSel('button[data-tab=whatif]');await ctx.waitFor(()=>!!document.querySelector('#wiLoad'));await p.top();await p.click({sel:'#wiLoad'});},{at:'조건별 손익으로 돌아가'});
 await p.loaded();
 await ctx.waitFor(()=>[...document.querySelectorAll('.chip')].some(e=>e.textContent.trim()==='규정상 제외'),60000);
 await ctx.say('p31-24',async()=>{
  await p.hover({sel:'.card-chips .chip',text:'규정상 제외',within:'팬 최대 운전'},0.35);await ctx.sleep(2200);
  await p.hover({sel:'.card-value .kv',text:'3',within:'팬 최대 운전'});
 },{pointFrac:0.05});
 await ctx.say('p31-25',async()=>{
  await p.hover({sel:'.card-sub',text:'원격',within:'팬 최대 운전'});await ctx.sleep(3800);
  await p.hover({sel:'.card-chips .chip',text:'규정상 제외',within:'부하 70 %와 야간 핀 세척'},0.5);await ctx.sleep(1500);
  await p.hover({sel:'.card-chips .chip',text:'판단 1위',within:'쿨러 핀 세척'},0.35);
 },{pointFrac:0.1});
 await ctx.say('p31-26',()=>p.hover({sel:'.card-chips .chip',text:'규정상 제외',within:'팬 최대 운전'},0.45),{pointFrac:0.4});
 await ctx.say('p31-27',async()=>{
  await c.clickSel('button[data-tab=scenario]');await modeIs('현장 제어');await ctx.sleep(600);
  await p.click({sel:`${unit} button[data-mode="REMOTE_AUTO"]`},0.8);
 },{pointFrac:0.4});
 await modeIs('원격 자동');
 await ctx.say('p31-28',()=>p.hover({sel:`${unit} header .mode`},0.35),{pointFrac:0.05});
 return 'p31-4 done';
};
