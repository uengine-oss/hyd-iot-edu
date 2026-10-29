// 실전 3-3 구간 4(VS Code): 결과/대조_기록.md 머리 4줄 · 팬 최대 운전 표 · 쿨러 핀 세척 표를 원문 문장과 포털 표시 그대로 채운다.
// 시작 상태: 구간 1 끝(원문 1.1 열림). 포털 관찰은 구간 2 · 3 녹화(2026-10-28 11:06 지식 지도, 11:09 결함 시뮬레이션) 그대로.
// 두 표의 빈 행 글이 같아 줄 번호로 이동한다(Ctrl+G). 기록 틀 줄 번호: 14~17 팬 최대 운전, 23~26 쿨러 핀 세척 — 행을 한 줄씩 바꾸므로 번호가 밀리지 않는다.
import {vscode} from '../ui.mjs';
export default async ctx=>{
 const c=await vscode(ctx);
 const typeQuick=async text=>{await c.gate();for(let i=0;i<text.length;i+=3){const s=text.slice(i,i+3);await c.serial(()=>ctx.p.keyboard.insertText(s));await ctx.sleep(34);}};
 const goto=async n=>{await c.key('Control+g');await ctx.sleep(450);await c.typeFast(String(n));await c.key('Enter');await ctx.sleep(450);};
 const row=async(n,text)=>{await goto(n);await c.key('Shift+End');await typeQuick(text);await ctx.sleep(300);};
 const folder=async(name,level)=>{const q=await c.explorerRow(name,level);await c.clickAt(q.x,q.y);await ctx.waitFor(new Function(`return [...document.querySelectorAll('.explorer-folders-view .monaco-list-row')].some(e=>e.getAttribute('aria-level')==='${level}'&&e.querySelector('.label-name')?.textContent.trim()===${JSON.stringify(name)}&&e.getAttribute('aria-expanded')==='true')`));};
 const open=async(name,level)=>{const q=await c.explorerRow(name,level);await c.clickAt(q.x,q.y);await ctx.waitFor(new Function(`return (document.querySelector('.tabs-container .tab.active')?.getAttribute('aria-label')||'').startsWith(${JSON.stringify(name)})`));};
 await ctx.begin();
 await ctx.say('p33-26',async()=>{
  await folder('결과',1);await ctx.sleep(500);await open('대조_기록.md',2);
  await c.lineEnd('- 확인 일시:');await typeQuick(' 2026-10-28 11:06(지식 지도) · 11:09(결함 시뮬레이션)');
  await c.lineEnd('- 포털에서 연 화면:');await typeQuick(' 지식 지도(조치 방법 팬 최대 운전 · 쿨러 핀 세척 상세), 지식 관리(등록된 매뉴얼 목록), 결함 시뮬레이션(HYD-01 카드)');
  await c.lineEnd('- 대조한 원문 판과');await typeQuick(' HM-8 1.1(현행) · 6a1a66a6000e');
  await c.lineEnd('- 포털 지식이 그 판인지');await typeQuick(' 조치 방법 상세의 citation · source_id 끝 값이 6a1a66a6000e…로 문서 목록 1.1판 SHA-256과 같음. 지식 관리 목록에 HM-8_cooler-fan-manual.md가 현재 판본으로 있음');
 },{at:'대조_기록.md를 엽니다'});
 await ctx.say('p33-27',()=>row(14,'| 적용 조건 | HM-8.5 첫머리 | 원격 조치는 PLC 운전 모드가 REMOTE_AUTO일 때만 한다. | 들어오는 관계 「적용 대상」 규칙: 원격 완화 조치는 PLC 운전 모드가 REMOTE_AUTO일 때만 허용한다. | 표현 다름(절 문장 → 규칙 문장, 뜻 같음) | PLC 운전 모드 — 결함 시뮬레이션 HYD-01 카드 |'),{pointFrac:0.15,commitFrac:0.06});
 await ctx.say('p33-28',async()=>{
  await row(15,'| 금지·제한 | HM-8.8 | 원격 조치(SOP-COOL-11~13)는 REMOTE_AUTO가 아닐 때 쓰지 않는다. / 이미 24시간을 넘겼다면 팬 최대 운전 조치는 팬 수명 손실로 20만 원을 감점해서 비교한다. | 적용 대상 규칙: 팬 100 % 연속 운전이 이미 24시간을 넘겼으면 팬 수명 손실로 20만 원을 감점한다. 원문 금액 단위(만원)와 기존 검토본을 따라 정비 비용 지표를 유지한다. | 표현 다름(금액 단위 설명 덧붙음) | 팬 100 % 누적 운전 시간 — 포털에서 찾지 못함 |');
  await row(16,'| 완료 기준 | HM-8.6 첫 문장 | 조치 뒤 15분 동안 TS1이 55 ℃ 미만이고 경보가 해제된 상태가 유지되면 완화에 성공한 것이다. | 없음(적용 대상의 예측 유온 55 ℃ 규칙은 HM-8.6 둘째 문장) | 포털에서 찾지 못함 | 유온 TS1 · 경보 — 결함 시뮬레이션 HYD-01 카드 |');
  await row(17,'| 승인 | SOP-COOL-11 | 승인: 운전원. | 나가는 관계 승인 역할 운전원 | 일치 | — |');
 },{pointFrac:0.1,commitFrac:0.06});
 await ctx.say('p33-29',async()=>{
  await row(23,'| 적용 조건 | SOP-COOL-14 단계 1 | 설비를 정지하고 현장 패널에서 LOCAL로 전환한 뒤 잠금(LOTO)을 건다. | 나가는 관계 절차 단계(같은 문장) | 일치 | 운전 상태 · 운전 모드 — 결함 시뮬레이션 HYD-01 카드, 잠금은 현장 |');
  await row(24,'| 금지·제한 | SOP-COOL-14 단계 2 | 압축공기로 핀 바깥쪽에서 안쪽으로 세척한다. 고압수는 쓰지 않는다. | 절차 단계(같은 문장) | 일치 | — |');
  await row(25,'| 완료 기준 | SOP-COOL-14 단계 3 | 재가동 후 냉각 효율 CE가 80 % 이상으로 돌아왔는지 확인한다. | 절차 단계(같은 문장) | 일치 | 냉각 효율 CE — 결함 시뮬레이션 HYD-01 카드 |');
  await row(26,'| 승인 | HM-8.7 첫머리 | 승인은 설비보전팀장이 한다. | 나가는 관계 승인 역할 설비보전팀장 | 일치(절 첫머리 문장 → 승인 역할 관계) | — |');
 },{pointFrac:0.1,commitFrac:0.06});
 return 'p33-4 done';
};
