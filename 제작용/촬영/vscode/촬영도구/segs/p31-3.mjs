// 실전 3-1 구간 3(포털): 값 바꿔 보기 → 납기까지 남은 시간 48 → 비교표 → 규칙 바꿔 보기의 순위 식 원문(납기 식) → 원래대로.
// 시작 상태: 구간 2 끝(HYD-01 · 쿨러 성능 저하 기준, 카드별 손익 탭, 팬 최대 운전 항목별 손익 펼침).
import {vscode} from '../ui.mjs';
import {portal} from './p31-common.mjs';
export default async ctx=>{
 const c=await vscode(ctx), p=portal(ctx,c);
 await ctx.begin();
 await ctx.say('p31-14',()=>p.click({sel:'[data-wi-tab]',text:'값 바꿔 보기'},0.25));
 await ctx.waitFor(()=>!!document.querySelector('.tab-pane.on [data-wi-var="due_h"]'));
 await ctx.say('p31-15',async()=>{await p.hover({sel:'.tab-pane.on .field label',text:'납기 지연 위약금'});await ctx.sleep(1500);await p.hover({sel:'.tab-pane.on .field-hint',text:'업무 DB ERP 값 120'});await ctx.sleep(2500);await p.hover({sel:'.tab-pane.on .field label',text:'납기까지 남은 시간'});},{pointFrac:0.1});
 await ctx.say('p31-16',async()=>{await p.click({sel:'.tab-pane.on [data-wi-var="due_h"]'});await c.type('48');await ctx.sleep(400);await p.click({sel:'#wiTry'});},{at:'48을 넣고'});
 await ctx.waitFor(()=>!!document.querySelector('.tab-pane.on table b')&&!document.querySelector('#wiTry')?.disabled,120000);
 await ctx.say('p31-17',async()=>{
  await p.hover({sel:'.tab-pane.on tbody td:first-child',text:'팬 최대 운전',exact:true},0.5);await ctx.sleep(2600);
  await p.hover({sel:'.tab-pane.on tbody td:first-child',text:'부하 70 %와 야간 핀 세척',exact:true});await ctx.sleep(2600);
  await p.hover({sel:'.tab-pane.on thead th',text:'정책 점수'});
 },{pointFrac:0.1});
 await ctx.say('p31-18',async()=>{
  await p.click({sel:'[data-wi-tab]',text:'규칙 바꿔 보기'},0.25);await ctx.sleep(900);
  await p.click({sel:'.tab-pane.on details > summary',text:'순위 식 원문'},0.35);await ctx.sleep(900);
  await p.hover({sel:'.tab-pane.on details[open] .fold-body',text:null},0.35);
 },{at:'규칙 바꿔 보기 탭'});
 await ctx.say('p31-18b',()=>p.hover({sel:'.tab-pane.on details[open] > summary',text:'순위 식 원문'}),{pointFrac:0.4});
 await ctx.say('p31-19',async()=>{await p.click({sel:'.tab-pane.on details[open] > summary',text:'순위 식 원문'});await p.top();await p.click({sel:'#wiReset'});await ctx.waitFor(()=>!document.querySelector('#wiReset'),120000);await p.click({sel:'[data-wi-tab]',text:'카드별 손익'},0.25);},{at:'원래대로를 눌러'});
 await ctx.waitFor(()=>!document.querySelector('#wiReset')&&!/시험값 \d+개 적용 중/.test(document.querySelector('.summary')?.innerText||''),120000);
 return 'p31-3 done';
};
