// 실전 2-2 구간 1(VS Code): 이번 실습의 이유 → VS Code 위치 → START.md → 기록 틀 사본을 결과/에 만들고 연다.
// 시작 상태: 녹화 공간 「vscode rec 20261028」, 실습 폴더 practical-02-map-*, START.md 탭 하나, 결과 폴더 접힘.
import {vscode} from '../ui.mjs';
export default async ctx=>{
 const c=await vscode(ctx);
 const center=sel=>c.serial(()=>ctx.p.evaluate(sel=>{const b=document.querySelector(sel).getBoundingClientRect();return{x:b.x+b.width/2,y:b.y+b.height/2};},sel));
 // 편집기에서 글이 text로 시작하는 줄의 앞쪽(글 시작 + 40px)
 const lineAt=text=>c.serial(()=>ctx.p.evaluate(text=>{const l=[...document.querySelectorAll('.editor-instance .view-lines .view-line')].find(e=>e.textContent.replace(/ /g,' ').startsWith(text));if(!l)throw Error('line '+text);const b=l.querySelector('span').getBoundingClientRect();return{x:b.x+40,y:b.y+b.height/2};},text));
 await c.installPointer({x:900,y:520});
 await ctx.begin();
 await ctx.say('p22-01');
 await ctx.say('p22-02');
 await ctx.say('p22-03',()=>c.hoverSel('.tabs-container .tab .label-name','START.md'),{pointFrac:0.4});
 await ctx.say('p22-04',async()=>{
  const ex=await center('.explorer-folders-view');await c.move(ex.x,ex.y-120);
  await ctx.sleep(2200);const ed=await center('.editor-instance .view-lines');await c.move(ed.x,ed.y);
 },{pointFrac:0.35});
 await ctx.say('p22-05',async()=>{
  for(const t of ['2. ','3. ','4. ']){const q=await lineAt(t);await c.move(q.x,q.y);await ctx.sleep(1700);}
 },{pointFrac:0.3});
 await ctx.say('p22-06',async()=>{
  const q=await c.explorerRow('탐색_기록.md',1);await c.move(q.x,q.y);await c.gate();
  await c.serial(()=>ctx.p.mouse.click(q.x,q.y,{button:'right'}));await ctx.sleep(700);
  await c.menuItem('Copy');
 });
 await ctx.say('p22-07',async()=>{
  const q=await c.explorerRow('결과',1);await c.move(q.x,q.y);await c.gate();
  await c.serial(()=>ctx.p.mouse.click(q.x,q.y,{button:'right'}));await ctx.sleep(700);
  await c.menuItem('Paste');
 });
 await ctx.waitFor(()=>[...document.querySelectorAll('.explorer-folders-view .monaco-list-row')].some(e=>e.getAttribute('aria-level')==='2'&&e.innerText.trim()==='탐색_기록.md'));
 await ctx.say('p22-08',async()=>{const q=await c.explorerRow('탐색_기록.md',2);await c.clickAt(q.x,q.y);});
 await ctx.waitFor(()=>document.querySelector('.tabs-container .tab.active')?.getAttribute('aria-label')?.startsWith('탐색_기록.md'));
 await ctx.say('p22-09',async()=>{
  for(const t of ['## 부품에서','## 이 부품을','## 화면에 있는']){const q=await lineAt(t);await c.move(q.x,q.y);await ctx.sleep(1500);}
 },{pointFrac:0.12});
 await ctx.say('p22-10');
 return 'p22-1 done';
};
