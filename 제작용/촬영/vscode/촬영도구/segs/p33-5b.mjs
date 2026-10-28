// 실전 3-3 구간 5b(VS Code): p33-5 판이 마지막 큐에서 멈춰(다시 연 기록이 아래로 스크롤돼 「대조 결과는 일치」 줄이 화면 밖) 그 큐만 잇는다.
// 시작 상태: p33-5의 p33-37 시작 시점(결과/대조_기록.md를 다시 연 화면, 3절 끝 ~ 5절).
import {vscode} from '../ui.mjs';
export default async ctx=>{
 const c=await vscode(ctx);
 const lineOf=(text,dx=60)=>c.serial(()=>ctx.p.evaluate(({text,dx})=>{const ls=[...document.querySelectorAll('.editor-instance .view-lines .view-line')].filter(e=>e.textContent.replace(/\u00a0/g,' ').includes(text)).sort((a,b)=>a.getBoundingClientRect().top-b.getBoundingClientRect().top);if(!ls.length)throw Error('line '+text);const b=ls[0].querySelector('span').getBoundingClientRect();return{x:b.x+dx,y:b.y+b.height/2};},{text,dx}));
 const point=async(text,dx,ms)=>{const q=await lineOf(text,dx);await c.move(q.x,q.y);await ctx.sleep(ms);};
 await ctx.begin();
 await ctx.say('p33-37',async()=>{await point('75 %에서 완료로',260,4500);await point('## 4. 기준값과 현재 값',60,0);},{pointFrac:0.05});
 return 'p33-5b done';
};
