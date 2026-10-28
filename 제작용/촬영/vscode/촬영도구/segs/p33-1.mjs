// 실전 3-3 구간 1(VS Code): 이번 실습의 이유 → START.md 판 표 → 자료/문서_목록.csv 1.1판 지문 → 원문 1.1의 SOP-COOL-11 · HM-8.5 첫머리 · HM-8.6 · HM-8.8 · SOP-COOL-14.
// 시작 상태: 녹화 공간 「vscode rec 20261028」, 실습 폴더 practical-03-manual-*, START.md 탭 하나, 자료 · 결과 폴더 접힘.
// 긴 원문 안의 이동은 줄 번호 이동(Ctrl+G)으로 한다(원문 1.1판 줄 번호 고정: 41 HM-8.5 첫머리, 43 SOP-COOL-11, 67 HM-8.6, 70 HM-8.7 첫머리, 72 SOP-COOL-14, 83 HM-8.8).
import {vscode} from '../ui.mjs';
export default async ctx=>{
 const c=await vscode(ctx);
 const center=sel=>c.serial(()=>ctx.p.evaluate(sel=>{const b=document.querySelector(sel).getBoundingClientRect();return{x:b.x+b.width/2,y:b.y+b.height/2};},sel));
 // 편집기에서 글에 text가 들어 있는 첫 줄의 앞쪽(글 시작 + dx)
 const lineOf=(text,dx=60)=>c.serial(()=>ctx.p.evaluate(({text,dx})=>{const ls=[...document.querySelectorAll('.editor-instance .view-lines .view-line')].filter(e=>e.textContent.replace(/ /g,' ').includes(text)).sort((a,b)=>a.getBoundingClientRect().top-b.getBoundingClientRect().top);if(!ls.length)throw Error('line '+text);const b=ls[0].querySelector('span').getBoundingClientRect();return{x:b.x+dx,y:b.y+b.height/2};},{text,dx}));
 const point=async(text,dx,ms)=>{const q=await lineOf(text,dx);await c.move(q.x,q.y);await ctx.sleep(ms);};
 const goto=async n=>{await c.key('Control+g');await ctx.sleep(450);await c.typeFast(String(n));await c.key('Enter');await ctx.sleep(500);};
 const folder=async(name,level)=>{const q=await c.explorerRow(name,level);await c.clickAt(q.x,q.y);await ctx.waitFor(new Function(`return [...document.querySelectorAll('.explorer-folders-view .monaco-list-row')].some(e=>e.getAttribute('aria-level')==='${level}'&&e.querySelector('.label-name')?.textContent.trim()===${JSON.stringify(name)}&&e.getAttribute('aria-expanded')==='true')`));};
 const open=async(name,level)=>{const q=await c.explorerRow(name,level);await c.clickAt(q.x,q.y);await ctx.waitFor(new Function(`return (document.querySelector('.tabs-container .tab.active')?.getAttribute('aria-label')||'').startsWith(${JSON.stringify(name)})`));};
 await c.installPointer({x:900,y:520});
 await ctx.begin();
 await ctx.say('p33-01',()=>c.hoverSel('.tabs-container .tab .label-name','START.md'),{pointFrac:0.75});
 await ctx.say('p33-02',async()=>{const ed=await center('.editor-instance .view-lines');await c.move(ed.x,ed.y);},{pointFrac:0.6});
 await ctx.say('p33-03',async()=>{for(const t of ['| HM-8 | 1.0','| HM-8 | 1.1','| HM-8 | 1.2']){await point(t,120,1700);}},{pointFrac:0.1});
 await ctx.say('p33-04',async()=>{await folder('자료',1);await ctx.sleep(500);await open('문서_목록.csv',2);await ctx.sleep(600);await c.serial(()=>ctx.p.evaluate(()=>document.querySelectorAll('.notification-toast .codicon-notifications-clear, .notification-toast .codicon-close').forEach(b=>b.click())));},{at:'문서 목록을 열어'});
 await ctx.say('p33-05',async()=>{await point('HM-8,1.1,현행',60,2600);await point('6a1a66a6',200,0);},{pointFrac:0.1});
 await ctx.say('p33-06',async()=>{await folder('원문',2);await ctx.sleep(500);await open('HM-8_cooler-fan-manual.md',3);},{at:'원문 폴더의'});
 await ctx.say('p33-07',async()=>{await goto(43);await point('### SOP-COOL-11',60,1500);for(const t of ['1. PLC 운전 모드가','2. 팬 속도를 100 %로 올린다. 100 %','3. 15분 재관측으로 HM-8.6']){await point(t,80,1400);}},{pointFrac:0.08,commitFrac:0.06});
 await ctx.say('p33-08',()=>point('원격 조치는 PLC 운전 모드가 REMOTE_AUTO일 때만 한다',120,0),{pointFrac:0.2});
 await ctx.say('p33-09',async()=>{await goto(67);await point('## HM-8.6',60,1200);await point('조치 뒤 15분 동안',140,0);},{pointFrac:0.15,commitFrac:0.06});
 await ctx.say('p33-10',async()=>{await goto(83);await point('## HM-8.8',60,1200);await point('- 원격 조치(SOP-COOL-11~13)',120,2600);await point('- 팬 100 % 연속 운전이',120,0);},{pointFrac:0.12,commitFrac:0.06});
 await ctx.say('p33-11',async()=>{await goto(72);await point('### SOP-COOL-14',60,1400);for(const t of ['1. 설비를 정지하고','2. 압축공기로','3. 재가동 후']){await point(t,80,1400);}await point('승인은 설비보전팀장이 한다',300,0);},{pointFrac:0.08,commitFrac:0.06});
 await ctx.say('p33-12');
 return 'p33-1 done';
};
