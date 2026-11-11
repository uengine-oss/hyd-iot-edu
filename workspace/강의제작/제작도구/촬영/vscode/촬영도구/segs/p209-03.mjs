// 실전 2회차 09편 구간 03: 결과 화면 공간(SPACE='통합02 결과화면 20261111', VP='{width:1843,height:1037,dsf:1.25}') — 받은 자료 · 원문 문장 표.
import {labUi, atPhrase, resultView, heading, inView, tableCell, scrollPageTo} from './lab-common.mjs';

const LAB = (await import('./lab-common.mjs')).LABS.p209.dir;   // 촬영 폴더는 lab-common.mjs LABS 한 곳에

export default async ctx => {
 const c = await labUi(ctx);
 const view = await resultView(c, ctx, LAB, '받은 자료');
 const src = (key, n = 0) => tableCell(c, ctx, key, n, 5);
 await c.installPointer({x: 1300, y: 160});
 await ctx.begin();
 await ctx.say('p209-0301', async () => {
  const a = await heading(c, ctx, '받은 자료'); await c.move(a.x, a.y); await atPhrase(ctx, '아래 표가');
  const b = inView(await heading(c, ctx, '매뉴얼 원문 문장')); await c.move(b.x, b.y);
 }, {at: '위 표가'});
 await ctx.say('p209-0302', async () => {
  const a = inView(await src('7')); await c.move(a.x, a.y); await atPhrase(ctx, '33.1처럼');
  const b = await scrollPageTo(c, ctx, () => src('33.1')); await c.move(b.x, b.y);
 }, {at: '원문 칸의'});
 await ctx.say('p209-0304', async () => {
  for (const [n, at] of [[1, '옆의 절'], [2, 'SOP,'], [3, '단계 칸에는']]) { await atPhrase(ctx, at); const q = inView(await src('23', n)); await c.move(q.x, q.y); }   // 33.1과 한 화면에 있는 줄
 }, {at: '옆의 절'});
 await ctx.say('p209-0303', async () => { await c.move(view.w - 260, 200); }, {at: '같은 조건이'});
 return {segment: 'p209-03', view, next: 'p209-04: 웹 VS Code 공간에서 Codex와 자료 파악(가이드 2단계)', aiRequests: 0};
};
