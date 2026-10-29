// 실전 3-3 구간 2(포털): 지식 지도 → 검색 「팬 최대 운전」 → SOP-COOL-11 상세(인용 · source_id 지문 · 승인 · 단계 · 적용 규칙) → 「쿨러 핀 세척」 SOP-COOL-14 상세.
// 시작 상태: 녹화 공간 「portal rec 20261028」, 포털 홈, 「나」 비움, 검색 칸 빈칸, 설비 HYD-01.
import {vscode} from '../ui.mjs';
import {portal} from './p31-common.mjs';
export default async ctx=>{
 const c=await vscode(ctx), p=portal(ctx,c);
 const node=id=>`#ontoMap .o-node[data-id="${id}"]`;
 const link=t=>({sel:'#ontoNode a[data-go]',text:t});
 await c.installPointer({x:760,y:430});
 await ctx.begin();
 await ctx.say('p33-13',async()=>{
  await c.clickSel('button[data-tab=ontology]');
  await ctx.waitFor(()=>document.querySelectorAll('#ontoMap .o-node').length>100,30000);
  await p.click({sel:'#ontoSearch'});await c.type('팬 최대 운전');
 },{at:'지식 지도를 엽니다'});
 await ctx.waitFor(()=>document.querySelector('#ontoStats').innerText.includes('검색 결과'));
 await ctx.say('p33-14',async()=>{await c.clickSel(node('skill:sop-cool-11'));await ctx.waitFor(()=>/SOP-COOL-11/.test(document.querySelector('#ontoNode').innerText));await p.hover({sel:'#ontoNode h3'},0.2);},{at:'팬 최대 운전을 누르고'});
 await ctx.say('p33-15',async()=>{await p.hover({sel:'#ontoNode .kvt th',text:'citation',exact:true},0.3);await ctx.sleep(2600);await p.hover({sel:'#ontoNode .kvt th',text:'source_id',exact:true},0.4);},{pointFrac:0.05});
 await ctx.say('p33-16',async()=>{await p.hover({sel:'#ontoNode h4',text:'나가는 관계'},0.25);await ctx.sleep(900);await p.hover(link('운전원'));await ctx.sleep(2200);await p.hover(link('팬 속도를 100 %로 올린다.'));},{pointFrac:0.05});
 await ctx.say('p33-17',async()=>{await p.hover({sel:'#ontoNode h4',text:'들어오는 관계'},0.25);await ctx.sleep(1500);await p.hover(link('원격 완화 조치는'),0.5);},{pointFrac:0.1});
 await ctx.say('p33-18',async()=>{await p.hover(link('팬 100 % 연속 운전이'),0.5);await ctx.sleep(3500);await p.hover(link('조치 후 예측 유온이'),0.5);await ctx.sleep(3000);await p.hover(link('15분 재관측으로'),0.4);},{pointFrac:0.05});
 await ctx.say('p33-19',async()=>{await p.top();await p.click({sel:'#ontoSearch'});await c.key('Control+a');await c.type('쿨러 핀 세척');},{at:'위로 올라가'});
 await ctx.waitFor(()=>!!document.querySelector('#ontoMap .o-node[data-id="skill:sop-cool-14"].match'),20000);
 await ctx.say('p33-20',async()=>{await c.clickSel(node('skill:sop-cool-14'));await ctx.waitFor(()=>/SOP-COOL-14/.test(document.querySelector('#ontoNode').innerText));await p.hover({sel:'#ontoNode h3'},0.2);},{at:'쿨러 핀 세척을 누르고'});
 await ctx.say('p33-21',async()=>{await p.hover(link('설비보전팀장'),0.35);await ctx.sleep(1800);await p.hover(link('압축공기로'));await ctx.sleep(2200);await p.hover(link('재가동 후'));},{pointFrac:0.05});
 return 'p33-2 done';
};
