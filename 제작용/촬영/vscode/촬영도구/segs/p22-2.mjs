// 실전 2-2 구간 2(포털 HYD-01): 지식 지도 → 이름 검색 「씰」 → 펌프 축 씰 키트 상세 → 주 펌프 A → B-OEM·C트레이딩 → 지도에 없는 것.
// 시작 상태: 녹화 공간 「portal rec 20261028」(1536x864 dsf1.5), 포털 홈, 「나」 비움(알림 배지 없음), 검색 칸 빈칸, 설비 HYD-01.
import {vscode} from '../ui.mjs';
export default async ctx=>{
 const c=await vscode(ctx);
 const free={x:1240,y:330};   // 본문 오른쪽 빈 곳(지도 밖) — 화면 굴리기 전 화살표 자리
 const link=id=>`#ontoNode a[data-go="${id}"]`;
 await c.installPointer({x:760,y:430});
 await ctx.begin();
 await ctx.say('p22-11',()=>c.clickSel('button[data-tab=ontology]'));
 await ctx.waitFor(()=>document.querySelectorAll('#ontoMap .o-node').length>100&&/항목 \d+/.test(document.querySelector('#ontoStats').innerText));
 await ctx.say('p22-12',async()=>{await c.hoverSel('#ontoLayers .chiptoggle','전략 목표');await ctx.sleep(1400);await c.hoverSel('#ontoLayers .chiptoggle','자원');},{pointFrac:0.3});
 await ctx.say('p22-13',()=>c.hoverSel('#ontoAsset'),{pointFrac:0.05});
 await ctx.say('p22-14',async()=>{await c.clickSel('#ontoSearch');await c.type('씰');});
 await ctx.waitFor(()=>document.querySelector('#ontoStats').innerText.includes('검색 결과'));
 await ctx.say('p22-15',async()=>{await c.hoverSel('#ontoStats');await ctx.sleep(1800);await c.clickSel('#ontoMap .o-node[data-id="part:pump-seal"]');},{pointFrac:0.05});
 await ctx.waitFor(()=>/partNo/.test(document.querySelector('#ontoNode').innerText));
 await ctx.say('p22-16',()=>c.scrollTo('main#content',9999,free));
 await ctx.say('p22-17',async()=>{await c.hoverSel('#ontoNode h3');await ctx.sleep(1500);await c.hoverSel('#ontoNode .kvt th','partNo');},{pointFrac:0.05});
 await ctx.say('p22-18',async()=>{await c.hoverSel('#ontoNode h4','나가는 관계 3');await ctx.sleep(1800);await c.hoverSel(link('sup:c'));},{pointFrac:0.08});
 await ctx.say('p22-19',async()=>{await c.hoverSel('#ontoNode h4','들어오는 관계 6');await ctx.sleep(1800);await c.hoverSel(link('comp:pump-a'));await ctx.sleep(2600);await c.hoverSel(link('cause:pump-shaft-seal-wear'));},{pointFrac:0.05});
 await ctx.say('p22-20',()=>c.clickSel(link('comp:pump-a')));
 await ctx.waitFor(()=>/aliases/.test(document.querySelector('#ontoNode').innerText));
 await ctx.say('p22-21',async()=>{await c.hoverSel(link('asset:hyd-01'));await ctx.sleep(3200);await c.hoverSel(link('part:pump-seal'));},{pointFrac:0.05});
 await ctx.say('p22-22',()=>c.clickSel(link('part:pump-seal')));
 await ctx.waitFor(()=>/partNo/.test(document.querySelector('#ontoNode').innerText));
 await ctx.say('p22-22b',()=>c.clickSel(link('sup:b')));
 await ctx.waitFor(()=>/avl/.test(document.querySelector('#ontoNode').innerText));
 await ctx.say('p22-23',async()=>{await c.hoverSel('#ontoNode .kvt th','avl');await ctx.sleep(5200);await c.hoverSel('#ontoNode h4','들어오는 관계 3');},{pointFrac:0.05});
 await ctx.say('p22-24',()=>c.clickSel(link('part:pump-seal')));
 await ctx.waitFor(()=>/partNo/.test(document.querySelector('#ontoNode').innerText));
 await ctx.say('p22-24b',()=>c.clickSel(link('sup:c')));
 await ctx.waitFor(()=>/avl\s*false/.test(document.querySelector('#ontoNode').innerText));
 await ctx.say('p22-25',()=>c.hoverSel('#ontoNode .kvt th','avl'),{pointFrac:0.05});
 await ctx.say('p22-26',async()=>{await c.hoverSel('#ontoNode h3');await ctx.sleep(2500);await c.hoverSel('#ontoNode .kvt td');},{pointFrac:0.2});
 return 'p22-2 done';
};
