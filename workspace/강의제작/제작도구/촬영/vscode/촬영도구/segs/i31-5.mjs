// 통합 3-1 구간 5(VS Code): 결과/비교_기록.md에 포털에서 확인한 것만 적고(기준 결과 · 시험 · 목표와 집계) 저장 → 탭 닫고 다시 열어 확인.
// 시작 상태: 구간 1 끝(결과/비교_기록.md 사본이 열린 편집기). 값은 실전 3-1 구간 p31-2 · 3 녹화 화면(통합 3-1 영상이 재사용)(2026-10-28 10:41 KST 불러오기) 그대로.
import {vscode} from '../ui.mjs';
export default async ctx=>{
 const c=await vscode(ctx);
 const rows=(...r)=>r.join('\n');
 // 글이 정확히 text인 줄(nbsp 정규화)을 눌러 줄 끝으로 → 줄 전체 선택. 빈 표 행은 접두가 겹치므로 일치로 찾는다.
 const selectRow=async text=>{
  const q=await c.serial(()=>ctx.p.evaluate(text=>{const ls=[...document.querySelectorAll('.editor-instance .view-lines .view-line')].filter(e=>e.textContent.replace(/ /g,' ').trim()===text);if(ls.length!==1)return{error:`row ${text} matched ${ls.length}`};const b=ls[0].querySelector('span').getBoundingClientRect();return{x:b.right+6,y:b.y+b.height/2};},text));
  if(q.error)throw Error(q.error);
  await c.clickAt(q.x,q.y);await c.key('End');await c.key('Shift+Home');
 };
 const lineOf=text=>c.serial(()=>ctx.p.evaluate(text=>{const l=[...document.querySelectorAll('.editor-instance .view-lines .view-line')].find(e=>e.textContent.replace(/ /g,' ').includes(text));if(!l)throw Error('line '+text);const b=l.querySelector('span').getBoundingClientRect();return{x:b.x+60,y:b.y+b.height/2};},text));
 // 긴 표 행은 세 글자씩 넣는다(한 글자씩이면 네 줄에 20초 가까이 말 없이 입력만 보임, 2026-10-28 첫 합본 검사).
 const typeQuick=async text=>{await c.gate();for(let i=0;i<text.length;i+=3){const s=text.slice(i,i+3);await c.serial(()=>ctx.p.keyboard.insertText(s));await ctx.sleep(34);}};
 await ctx.begin();
 await ctx.say('i31-06',async()=>{
  await c.lineEnd('- 포털 주소와 확인 시각:');await typeQuick(' http://127.0.0.1:8088 · 2026-10-28 10:41');
  await c.lineEnd('- 설비와 이상 패턴:');await typeQuick(' HYD-01 · 쿨러 성능 저하');
 },{pointFrac:0.3});
 await ctx.say('i31-07',async()=>{
  await selectRow('| | | | | |');
  await typeQuick(rows(
   '| 쿨러 핀 세척 | 허용 | 표시 없음 | 판단 1위 · 정책 점수 4.47 · 손익 순위 없음 | 미확인(계산하지 못한 항목: 생산 감소, 납기 지연 위약금, 정비 작업비) |',
   '| 팬 최대 운전 | 허용 | 표시 없음 | 판단 2위 · 정책 점수 3.69 · 손익 1위 | −39,501원(항목별 손익 · 출처 7개) |',
   '| 부하 70 %와 야간 핀 세척 | 허용 | 표시 없음 | 판단 3위 · 정책 점수 3.07 · 손익 순위 없음 | 미확인(계산하지 못한 항목: 생산 감소, 납기 지연 위약금, 정비 작업비) |',
   '| 팬 최대 운전과 부하 80 % | 허용 | 표시 없음 | 판단 4위 · 정책 점수 2.59 · 손익 2위 | −620,945원 |'));
 });
 await ctx.say('i31-08',async()=>{
  await selectRow('| | | | | | | |');
  await typeQuick('| 1 | 납기까지 남은 시간 | h | 5.39 → 48 | 판단 순위 팬 최대 운전 2위 → 3위, 부하 70 %와 야간 핀 세척 3위 → 2위. 정책 점수 4.47 → 3.3, 3.69 → 2.52, 3.07 → 2.6, 2.59 → 2.12 | 순위 식 원문의 납기 항목: 24시간 넘으면 0, 부하 유지 카드 ×1 · 부하 감소 카드 ×0.4 | 원래대로 누름 |');
 });
 await ctx.say('i31-09',async()=>{
  const q=await c.explorerRow('kpi.csv',1);await c.clickAt(q.x,q.y);
  await ctx.waitFor(()=>document.querySelector('.tabs-container .tab.active')?.getAttribute('aria-label')?.startsWith('kpi.csv'));
  // CSV를 처음 열면 확장 설치 권유 알림이 뜨고 끝까지 남는다(2026-10-28 둘째 녹화) — 닫는다.
  await ctx.sleep(600);await c.serial(()=>ctx.p.evaluate(()=>document.querySelectorAll('.notification-toast .codicon-notifications-clear, .notification-toast .codicon-close').forEach(b=>b.click())));
  for(const t of ['HYD-01,','HYD-02,','HYD-03,']){const r=await lineOf(t);await c.move(r.x,r.y);await ctx.sleep(1500);}
 },{pointFrac:0.15});
 await ctx.say('i31-10',async()=>{
  await c.clickSel('.tabs-container .tab .label-name','비교_기록.md');
  await ctx.waitFor(()=>document.querySelector('.tabs-container .tab.active')?.getAttribute('aria-label')?.startsWith('비교_기록.md'));
  await c.lineEnd('| 평균 | | |');await c.key('End');await c.key('Shift+Home');await typeQuick('| 평균 | 11.27 | 목표 10 이상 — 달성 |');
  await c.lineEnd('| 최솟값 | | |');await c.key('End');await c.key('Shift+Home');await typeQuick('| 최솟값 | 2.53(HYD-01) | 목표 10 미달. 인터록 여유는 한 대라도 한계에 가까우면 위험하므로 최솟값으로 판단 |');
 },{pointFrac:0.2});
 await ctx.say('i31-11',async()=>{
  await c.key('Control+s');
  await ctx.waitFor(()=>!document.querySelector('.tabs-container .tab.active')?.classList.contains('dirty'));
  await c.clickSel('.tabs-container .tab.active .tab-actions .action-label');
  const q=await c.explorerRow('비교_기록.md',2);await c.clickAt(q.x,q.y);
 },{at:'Ctrl과 S로 저장하고'});
 await ctx.waitFor(()=>document.querySelector('.tabs-container .tab.active')?.getAttribute('aria-label')?.startsWith('비교_기록.md'));
 await ctx.say('i31-12',async()=>{const q=await lineOf('순위 식 원문의 납기 항목');await c.move(q.x+200,q.y);},{pointFrac:0.05});
 return 'i31-5 done';
};
