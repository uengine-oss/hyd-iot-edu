// 통합 2-2 구간 4(VS Code): 결과/탐색_기록.md에 포털에서 확인한 것만 적고(연결 · 같은 이름 다른 대상 · 설비를 바꿔 본 결과) 저장 → 탭 닫고 다시 열어 확인.
// 시작 상태: 구간 1 끝(결과/탐색_기록.md 사본이 열린 편집기). 값은 구간 2 · 3 녹화 화면(2026-10-28 11:18 HYD-01, 11:21 HYD-02) 그대로.
// 상세 칸에는 대상 ID가 표시되지 않고, 설비 노드(HYD-01 유압 파워팩) · 쿨러 코어는 열지 않아 클래스를 보지 않았다 — 미확인으로 적는다.
import {vscode} from '../ui.mjs';
export default async ctx=>{
 const c=await vscode(ctx);
 const rows=(...r)=>r.join('\n');
 const typeQuick=async text=>{await c.gate();for(let i=0;i<text.length;i+=3){const s=text.slice(i,i+3);await c.serial(()=>ctx.p.keyboard.insertText(s));await ctx.sleep(34);}};
 // 글이 정확히 text인 줄(nbsp 정규화)을 눌러 줄 끝으로 → 줄 전체 선택. 빈 표 행은 접두가 겹치므로 일치로 찾는다.
 const selectRow=async text=>{
  const q=await c.serial(()=>ctx.p.evaluate(text=>{const ls=[...document.querySelectorAll('.editor-instance .view-lines .view-line')].filter(e=>e.textContent.replace(/ /g,' ').trim()===text);if(ls.length!==1)return{error:`row ${text} matched ${ls.length}`};const b=ls[0].querySelector('span').getBoundingClientRect();return{x:b.right+6,y:b.y+b.height/2};},text));
  if(q.error)throw Error(q.error);
  await c.clickAt(q.x,q.y);await c.key('End');await c.key('Shift+Home');
 };
 const lineOf=text=>c.serial(()=>ctx.p.evaluate(text=>{const l=[...document.querySelectorAll('.editor-instance .view-lines .view-line')].sort((a,b)=>a.getBoundingClientRect().top-b.getBoundingClientRect().top).find(e=>e.textContent.replace(/ /g,' ').includes(text));if(!l)throw Error('line '+text);const b=l.querySelector('span').getBoundingClientRect();return{x:b.x+60,y:b.y+b.height/2};},text));
 await ctx.begin();
 await ctx.say('i22-27',async()=>{
  await c.lineEnd('- 포털 주소와 확인 시각:');await typeQuick(' http://127.0.0.1:8088 · 2026-10-28 11:18');
  await c.lineEnd('- 선택한 설비:');await typeQuick(' HYD-01(마지막에 HYD-02로 바꿔 비교)');
 },{pointFrac:0.3,commitFrac:0.3});
 await ctx.say('i22-28',async()=>{
  await selectRow('| | | | | |');
  await typeQuick(rows(
   '| HYD-01 유압 파워팩 · 클래스 미확인 | 구성 요소 | 오일 쿨러 · 구성 요소 | aliases ["쿨러","열교환기"] | 두 대상의 ID(상세에 표시 없음) |',
   '| 오일 쿨러 · 구성 요소 | 관측 센서 | 유온 센서 · 센서 | tag TS1, unit ℃, virtual false | 두 대상의 ID |',
   '| 오일 쿨러 · 구성 요소 | 교체 부품 | 쿨러 코어 · 클래스 미확인 | — | 쿨러 코어의 ID · 클래스 · 속성(열지 않음) |',
   '| 유온 센서 · 센서 | 읽는 상태 변수 | 유온 · 상태 변수 | normal 48, limit 65, unit ℃ | 두 대상의 ID |'));
 },{pointFrac:0.1,commitFrac:0.1});
 await ctx.say('i22-29',async()=>{
  await selectRow('| | | | |');
  await typeQuick(rows(
   '| TS1 | 화면에서 미확인 | 센서(유온 센서의 tag) | 다른 대상 — 클래스가 다르다. 센서는 값을 재는 장치 |',
   '| TS1 | 화면에서 미확인 | 상태 변수(유온의 aliases) | 다른 대상 — 재는 값의 종류. 센서가 「읽는 상태 변수」 관계로 가리킨다 |'));
 },{pointFrac:0.1,commitFrac:0.1});
 await ctx.say('i22-30',async()=>{
  await c.lineEnd('- HYD-02에서 같은 노드가 이어졌는가:');await typeQuick(' 예 — 오일 쿨러의 들어오는 관계가 HYD-02 유압 파워팩으로 바뀌고, 나가는 관계(유온 센서 · 냉각 효율(가상) · 쿨러 코어)는 HYD-01과 같음');
  await c.lineEnd('- 기준 지도가 세 설비를 표현하는 방식:');await typeQuick(' 설비 노드만 바뀌고 오일 쿨러 · 유온 센서는 설비마다 따로 두지 않은 한 노드로 보임(HYD-03은 화면에서 미확인)');
  await c.lineEnd('- 다음 모델에서 비교할 질문:');await typeQuick(' 설비마다 센서를 따로 두면 HYD-01과 HYD-02의 TS1 값을 어떻게 구별해 조회하는가? 한 노드로 두면 어느 설비의 값인지 어디에 남는가?');
 },{pointFrac:0.1,commitFrac:0.1});
 await ctx.say('i22-31',()=>c.key('Control+s'),{at:'S를 누르면 저장돼요'});
 await ctx.waitFor(()=>!document.querySelector('.tabs-container .tab.active')?.classList.contains('dirty'));
 await ctx.say('i22-32',async()=>{
  await c.clickSel('.tabs-container .tab.active .tab-actions .action-label');
  const q=await c.explorerRow('탐색_기록.md',2);await c.clickAt(q.x,q.y);
 },{at:'탭을 닫고'});
 await ctx.waitFor(()=>document.querySelector('.tabs-container .tab.active')?.getAttribute('aria-label')?.startsWith('탐색_기록.md'));
 await ctx.say('i22-33',async()=>{const q=await lineOf('| TS1 |');await c.move(q.x+200,q.y);},{pointFrac:0.05});
 return 'i22-4 done';
};
