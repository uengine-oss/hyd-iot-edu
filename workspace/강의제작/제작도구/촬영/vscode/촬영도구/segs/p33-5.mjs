// 실전 3-3 구간 5(VS Code): 폐기된 1.0판에서 같은 작업 찾기 → 다른 판과의 차이 · 기준값과 현재 값 · 적용 범위 · 남은 질문 → 저장 · 다시 열기.
// 시작 상태: 구간 4 끝(결과/대조_기록.md 1 · 2절 채움, 원문 1.1 탭도 열림).
// 기록 틀 줄 번호(1 · 2절은 행을 한 줄씩 바꿔 그대로): 31 다른 판 표 구분선, 36 기준값 표 구분선, 41 적용 범위 표 구분선, 44 남은 질문 아래 빈 줄. 앞 표에 넣은 행 수만큼 뒤 번호가 밀린다.
// 1.0판 줄 번호: 37 HM-7.3, 40 SOP-COOL-01, 74 SOP-COOL-04.
import {vscode} from '../ui.mjs';
export default async ctx=>{
 const c=await vscode(ctx);
 const typeQuick=async text=>{await c.gate();for(let i=0;i<text.length;i+=3){const s=text.slice(i,i+3);await c.serial(()=>ctx.p.keyboard.insertText(s));await ctx.sleep(34);}};
 const goto=async n=>{await c.key('Control+g');await ctx.sleep(450);await c.typeFast(String(n));await c.key('Enter');await ctx.sleep(450);};
 const lineOf=(text,dx=60)=>c.serial(()=>ctx.p.evaluate(({text,dx})=>{const ls=[...document.querySelectorAll('.editor-instance .view-lines .view-line')].filter(e=>e.textContent.replace(/ /g,' ').includes(text)).sort((a,b)=>a.getBoundingClientRect().top-b.getBoundingClientRect().top);if(!ls.length)throw Error('line '+text);const b=ls[0].querySelector('span').getBoundingClientRect();return{x:b.x+dx,y:b.y+b.height/2};},{text,dx}));
 const point=async(text,dx,ms)=>{const q=await lineOf(text,dx);await c.move(q.x,q.y);await ctx.sleep(ms);};
 const open=async(name,level)=>{const q=await c.explorerRow(name,level);await c.clickAt(q.x,q.y);await ctx.waitFor(new Function(`return (document.querySelector('.tabs-container .tab.active')?.getAttribute('aria-label')||'').startsWith(${JSON.stringify(name)})`));};
 const toRecord=async()=>{await c.clickSel('.tabs-container .tab .label-name','대조_기록.md');await ctx.waitFor(()=>(document.querySelector('.tabs-container .tab.active')?.getAttribute('aria-label')||'').startsWith('대조_기록.md'));};
 let shift=0;
 // 구분선(원래 번호 n) 아래에 행을 넣는다
 const addRows=async(n,rows)=>{await goto(n+shift);await c.key('End');await typeQuick('\n'+rows.join('\n'));shift+=rows.length;};
 await ctx.begin();
 await ctx.say('p33-30',()=>open('HM-8_rev1.0_cooler-fan-manual.md',3),{at:'1.0판을 열어'});
 await ctx.say('p33-31',async()=>{await goto(40);await point('### SOP-COOL-01',60,1600);await point('## HM-7.3',60,1600);await point('1. HM-3.2 조건을 확인한다.',80,0);},{pointFrac:0.05,commitFrac:0.06});
 await ctx.say('p33-32',async()=>{
  await goto(74);await point('2. 압축공기 또는 저압수로',120,2000);await point('3. 재가동 후 냉각 효율 CE가 75 %',200,1800);await point('1. HM-3.1에 따라',120,1500);
  await toRecord();
  await addRows(31,[
   '| 팬 최대 운전 | 1.0 SOP-COOL-01 · HM-7.3 | 1. HM-3.2 조건을 확인한다. | 1. PLC 운전 모드가 REMOTE_AUTO인지 확인한다. | 운전 모드 조건이 단계에 없어 HM-3.2를 따로 찾아야 함. ID · 절 번호가 달라 포털 · 1.1과 바로 맞춰지지 않음 |',
   '| 쿨러 핀 세척 | 1.0 SOP-COOL-04 · HM-7.6 | 1. HM-3.1에 따라 설비를 정지하고 LOCAL로 전환한다. | 1. 설비를 정지하고 현장 패널에서 LOCAL로 전환한 뒤 잠금(LOTO)을 건다. | 잠금(LOTO) 확인 없이 작업할 수 있음 |',
   '| 쿨러 핀 세척 | 1.0 SOP-COOL-04 · HM-7.6 | 2. 압축공기 또는 저압수로 핀을 세척한다. | 2. 압축공기로 핀 바깥쪽에서 안쪽으로 세척한다. 고압수는 쓰지 않는다. | 물 세척을 해도 된다고 판단함 |',
   '| 쿨러 핀 세척 | 1.0 SOP-COOL-04 · HM-7.6 | 3. 재가동 후 냉각 효율 CE가 75 % 이상으로 돌아왔는지 확인한다. | 3. 재가동 후 냉각 효율 CE가 80 % 이상으로 돌아왔는지 확인한다. | 75 %에서 완료로 판단함 |']);
 },{at:'핀 세척이 특히 다릅니다'});
 await ctx.say('p33-33',()=>addRows(36,[
  '| 유온 TS1 | 55 ℃ 미만이 15분 유지(HM-8.6) | 결함 시뮬레이션 HYD-01 카드 유온 | 48.0 ℃ · 2026-10-28 11:09 |',
  '| 냉각 효율 CE | 80 % 이상(SOP-COOL-14 단계 3) | 같은 카드 냉각 효율 CE | 84 % · 11:09 |',
  '| PLC 운전 모드 | REMOTE_AUTO일 때만 원격 조치(HM-8.5) | 같은 카드 운전 모드 | 원격 자동 · 11:09 |',
  '| 팬 100 % 누적 운전 시간 | 24시간 이내(SOP-COOL-11 단계 2 · HM-8.8) | 포털 화면에서 찾지 못함 | 미확인 |']),{pointFrac:0.1,commitFrac:0.06});
 await ctx.say('p33-34',()=>addRows(41,['| 100 % 연속 운전은 24시간 이내로 한다. | SOP-COOL-11과 SOP-COOL-12(둘 다 팬 100 %) | HM-8.8 「팬 100 % 연속 운전이 24시간을 넘으면 팬 수명이 줄어든다」가 작업을 가리지 않음 | SOP-COOL-11에만 적용하면 SOP-COOL-12는 24시간을 넘겨도 감점 없이 비교됨 |']),{at:'두 작업 모두에 적용한다고'});
 await ctx.say('p33-35',async()=>{await goto(44+shift);await typeQuick('1. 개정 요청 중인 1.2판(CR-2026-031)이 SOP-COOL-11 · SOP-COOL-14의 조건이나 기준을 바꾸는가?\n2. 팬 100 % 누적 운전 시간은 어느 시스템 화면에서 읽는가?');},{pointFrac:0.2,commitFrac:0.06});
 await ctx.say('p33-36',async()=>{
  await c.key('Control+s');
  await ctx.waitFor(()=>!document.querySelector('.tabs-container .tab.active')?.classList.contains('dirty'));
  await c.clickSel('.tabs-container .tab.active .tab-actions .action-label');
  await open('대조_기록.md',2);
 },{at:'Ctrl과 S로 저장하고'});
 await ctx.say('p33-37',()=>point('대조 결과는 일치',200,0),{pointFrac:0.05});
 return 'p33-5 done';
};
