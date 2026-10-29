// 통합 2-2 구간 2(포털 HYD-01): 지식 지도 → 검색 「오일 쿨러」 → 상세(클래스 · 별칭 · 나가는/들어오는 관계 방향 · ID 미표시).
// 시작 상태: 녹화 공간 「portal rec 20261028」, 포털 홈, 「나」 비움, 검색 칸 빈칸, 설비 HYD-01.
import {vscode} from '../ui.mjs';
import {portal} from './p31-common.mjs';
export default async ctx=>{
 const c=await vscode(ctx), p=portal(ctx,c);
 const link=t=>({sel:'#ontoNode a[data-go]',text:t});
 await c.installPointer({x:760,y:430});
 await ctx.begin();
 await ctx.say('i22-10',()=>p.menu('ontology'));
 await ctx.waitFor(()=>document.querySelectorAll('#ontoMap .o-node').length>100&&/항목 \d+/.test(document.querySelector('#ontoStats').innerText),30000);
 await ctx.say('i22-11',async()=>{await c.hoverSel('#ontoLayers .chiptoggle','자원');await ctx.sleep(2200);await c.hoverSel('#ontoAsset');},{pointFrac:0.3});
 await ctx.say('i22-12',async()=>{await c.clickSel('#ontoSearch');await c.type('오일 쿨러');},{at:'검색 칸에 오일 쿨러를'});
 await ctx.waitFor(()=>!!document.querySelector('#ontoMap .o-node[data-id="comp:cooler"].match'),20000);
 await ctx.say('i22-13',async()=>{await c.clickSel('#ontoMap .o-node[data-id="comp:cooler"]');await ctx.waitFor(()=>/aliases/.test(document.querySelector('#ontoNode').innerText));await p.hover({sel:'#ontoNode h3'},0.25);},{at:'오일 쿨러를 누르면'});
 await ctx.say('i22-14',async()=>{await p.hover({sel:'#ontoNode h3'},0.25);await ctx.sleep(1800);await p.hover({sel:'#ontoNode .kvt th',text:'aliases',exact:true});},{pointFrac:0.05});
 await ctx.say('i22-15',async()=>{await p.hover({sel:'#ontoNode h4',text:'나가는 관계'},0.3);await ctx.sleep(1000);await p.hover(link('유온 센서'));await ctx.sleep(1800);await p.hover(link('냉각 효율'));await ctx.sleep(1800);await p.hover(link('쿨러 코어'));},{pointFrac:0.05});
 await ctx.say('i22-16',async()=>{await p.hover({sel:'#ontoNode h4',text:'들어오는 관계'},0.4);await ctx.sleep(900);await p.hover(link('HYD-01 유압 파워팩'));},{pointFrac:0.1});
 await ctx.say('i22-17',()=>p.hover({sel:'#ontoNode h3'},0.25),{pointFrac:0.2});
 return 'i22-2 done';
};
