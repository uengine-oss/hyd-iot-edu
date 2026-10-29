// 실전 3-1 구간 1(VS Code): 이번 실습의 이유 → START.md 순서 → 비교_기록.md 사본을 결과/에 만들고 열어 표 네 개 확인.
// 시작 상태: 녹화 공간 「vscode rec 20261028」, 실습 폴더 practical-03-whatif-*, START.md 탭 하나, 결과 폴더 접힘.
import {vscode} from '../ui.mjs';
export default async ctx=>{
 const c=await vscode(ctx);
 const center=sel=>c.serial(()=>ctx.p.evaluate(sel=>{const b=document.querySelector(sel).getBoundingClientRect();return{x:b.x+b.width/2,y:b.y+b.height/2};},sel));
 // 편집기에서 글이 text로 시작하는 줄의 앞쪽(글 시작 + 40px)
 const lineAt=text=>c.serial(()=>ctx.p.evaluate(text=>{const l=[...document.querySelectorAll('.editor-instance .view-lines .view-line')].find(e=>e.textContent.replace(/ /g,' ').startsWith(text));if(!l)throw Error('line '+text);const b=l.querySelector('span').getBoundingClientRect();return{x:b.x+40,y:b.y+b.height/2};},text));
 await c.installPointer({x:900,y:520});
 await ctx.begin();
 await ctx.say('p31-01',()=>c.hoverSel('.tabs-container .tab .label-name','START.md'),{pointFrac:0.7});
 await ctx.say('p31-02',async()=>{const ed=await center('.editor-instance .view-lines');await c.move(ed.x,ed.y);},{pointFrac:0.5});
 await ctx.say('p31-03',async()=>{
  for(const t of ['2. ','3. ','5. ','6. ']){const q=await lineAt(t);await c.move(q.x,q.y);await ctx.sleep(1900);}
 },{pointFrac:0.2});
 await ctx.say('p31-04',async()=>{
  let q=await c.explorerRow('비교_기록.md',1);await c.move(q.x,q.y);await c.gate();
  await c.serial(()=>ctx.p.mouse.click(q.x,q.y,{button:'right'}));await ctx.sleep(700);
  await c.menuItem('Copy');await ctx.sleep(900);
  q=await c.explorerRow('결과',1);await c.move(q.x,q.y);
  await c.serial(()=>ctx.p.mouse.click(q.x,q.y,{button:'right'}));await ctx.sleep(700);
  await c.menuItem('Paste');
 },{at:'오른쪽 버튼으로 Copy'});
 await ctx.waitFor(()=>[...document.querySelectorAll('.explorer-folders-view .monaco-list-row')].some(e=>e.getAttribute('aria-level')==='2'&&e.innerText.trim()==='비교_기록.md'));
 await ctx.say('p31-05',async()=>{
  const q=await c.explorerRow('비교_기록.md',2);await c.clickAt(q.x,q.y);
  await ctx.waitFor(()=>document.querySelector('.tabs-container .tab.active')?.getAttribute('aria-label')?.startsWith('비교_기록.md'));
  for(const t of ['## 기준 결과','## 한 항목씩','## 순위와 선택','## 목표와 집계']){const r=await lineAt(t);await c.move(r.x,r.y);await ctx.sleep(1300);}
 },{pointFrac:0.05});
 return 'p31-1 done';
};
