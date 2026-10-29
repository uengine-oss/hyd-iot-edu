// 실전 2-2 구간 4(VS Code): 결과/탐색_기록.md에 확인한 것만 적고 저장 → 탭 닫고 다시 열어 확인.
// 시작 상태: 구간 1 끝(결과/탐색_기록.md 사본이 열린 편집기). 포털 확인 시각은 녹화 시각(분 단위).
import {vscode} from '../ui.mjs';
export default async ctx=>{
 const c=await vscode(ctx);
 const now=new Date(Date.now()+9*3600e3).toISOString().slice(0,16).replace('T',' ');
 const rows=(...r)=>r.join('\n');
 await ctx.begin();
 await ctx.say('p22-34',async()=>{
  await c.lineEnd('- 포털 주소와 확인 시각:');await c.typeFast(' http://127.0.0.1:8088 · '+now);
  await c.lineEnd('- 확인한 부품:');await c.typeFast(' 펌프 축 씰 키트 · partNo P-PMP-SEAL');
 });
 await ctx.say('p22-35',async()=>{
  await c.lineEnd('| | | | | |');await c.key('Shift+Home');
  await c.typeFast(rows('| P-PMP-SEAL · 부품 | 공급사 | A정밀 저가 · 공급사 | avl true | 공급사 ID, 단가·납기 |','| P-PMP-SEAL · 부품 | 공급사 | B-OEM 순정 · 공급사 | avl true | 공급사 ID, 단가·납기 |','| P-PMP-SEAL · 부품 | 공급사 | C트레이딩 최저가 · 공급사 | avl false | 공급사 ID, 단가·납기 |'));
 });
 await ctx.say('p22-36',async()=>{
  await c.typeFast('\n'+rows('| 주 펌프 A · 구성 요소 | 교체 부품 | P-PMP-SEAL · 부품 | 표시 없음 | 사용 수량 |','| 펌프 축 씰 마모 · 원인 | 관련 부품 | P-PMP-SEAL · 부품 | 표시 없음 | 원인 판별 기준 |','| 발주 조치 방법 4개 · 조치 방법 | 관련 부품 | P-PMP-SEAL · 부품 | 표시 없음 | 매뉴얼 절 직접 연결 없음 |'));
 },{pointFrac:0.05});
 await ctx.say('p22-37',async()=>{
  await c.lineEnd('| | |');await c.key('Shift+Home');
  await c.typeFast(rows('| HYD-01 | HYD-01 유압 파워팩 → 주 펌프 A → 펌프 축 씰 키트 |','| HYD-02 | HYD-02 유압 파워팩 → 주 펌프 A → 펌프 축 씰 키트 |','| HYD-03 | HYD-03 유압 파워팩 → 주 펌프 A → 펌프 축 씰 키트 |'));
 },{pointFrac:0.3});
 await ctx.say('p22-38',async()=>{
  await c.lineEnd('- 지도에서 확인한 공급 조건:');await c.typeFast(' 공급사 3곳 연결과 승인 여부 avl — A정밀 true, B-OEM true, C트레이딩 false');
  await c.lineEnd('- 지도에 없어 판단하지 않은 것');await c.typeFast(' 단가, 납기, 재고 수량, 발주 상태. 공급 연결만으로 확보 여부를 판단하지 않음');
 },{pointFrac:0.25});
 await ctx.say('p22-39',async()=>{
  await c.lineEnd('1.');await c.typeFast(' 승인 공급사 A정밀과 B-OEM의 펌프 축 씰 키트 단가·납기·불량률은 각각 얼마이고, 기준일에 유효한 견적은 어느 것인가?');
  await c.lineEnd('2.');await c.typeFast(' 승인되지 않은 C트레이딩의 조건은 공급 후보에 남기는가, 빼는가? 그 근거는 어느 자료에 있는가?');
 },{pointFrac:0.3});
 await ctx.say('p22-40',()=>c.key('Control+s'));
 await ctx.waitFor(()=>!document.querySelector('.tabs-container .tab.active')?.classList.contains('dirty'));
 await ctx.say('p22-41',async()=>{
  await c.clickSel('.tabs-container .tab.active .tab-actions .action-label');
  const q=await c.explorerRow('탐색_기록.md',2);await c.clickAt(q.x,q.y);
 });
 await ctx.waitFor(()=>document.querySelector('.tabs-container .tab.active')?.getAttribute('aria-label')?.startsWith('탐색_기록.md'));
 await ctx.say('p22-42',async()=>{const q=await c.serial(()=>ctx.p.evaluate(()=>{const l=[...document.querySelectorAll('.editor-instance .view-lines .view-line')].find(e=>e.textContent.replace(/ /g,' ').includes('C트레이딩 최저가'));const b=l.querySelector('span').getBoundingClientRect();return{x:b.x+260,y:b.y+b.height/2};}));await c.move(q.x,q.y);},{pointFrac:0.05});
 await ctx.say('p22-43');
 return 'p22-4 done';
};
