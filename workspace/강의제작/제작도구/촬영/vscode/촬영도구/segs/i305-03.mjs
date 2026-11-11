// 통합 3회차 05편 구간 03: 결과 화면 공간(SPACE='통합02 결과화면 20261111', VP='{width:1843,height:1037,dsf:1.25}') — 받은 자료 · 원문 문장 번호 표.
// 원문 표는 첫 화면 아래로 이어지므로 33.1 줄은 휠로 내린 뒤 짚는다.
import {labUi, atPhrase, resultView, heading, inView, tableCell, scrollPageTo} from './lab-common.mjs';

const LAB = (await import('./lab-common.mjs')).LABS.i305.dir;   // 촬영 폴더는 lab-common.mjs LABS 한 곳에

export default async ctx => {
 const c = await labUi(ctx);
 const view = await resultView(c, ctx, LAB, '받은 자료');
 const src = (key, n = 0) => tableCell(c, ctx, key, n, 5);
 await c.installPointer({x: 1300, y: 160});
 await ctx.begin();
 await ctx.say('i305-0301', async () => {
  const a = await heading(c, ctx, '받은 자료'); await c.move(a.x, a.y); await atPhrase(ctx, '아래 표는');
  const b = inView(await heading(c, ctx, '매뉴얼 원문 문장')); await c.move(b.x, b.y);
 }, {at: '위의 표는'});
 await ctx.say('i305-0306', async () => { const q = inView(await heading(c, ctx, '모두 보기', 'button.more')); await c.move(q.x, q.y); }, {at: '표 위의 모두 보기'});   // 짚기만 하고 누르지 않는다
 await ctx.say('i305-0302', async () => {
  const a = inView(await src('7')); await c.move(a.x, a.y); await atPhrase(ctx, '33.1처럼');
  const b = await scrollPageTo(c, ctx, () => src('33.1')); await c.move(b.x, b.y);
 }, {at: '원문 칸의'});
 await ctx.say('i305-0303', async () => {
  const e = inView(await src('33.1', 2)); await c.move(e.x, e.y); await atPhrase(ctx, '23처럼');
  const a = inView(await src('23', 2)); await c.move(a.x, a.y); await atPhrase(ctx, '이 줄은 벨트');
  const b = inView(await src('23', 3)); await c.move(b.x, b.y);
 }, {at: '이 줄처럼'});
 await ctx.say('i305-0304', async () => { const q = inView(await src('23')); await c.move(q.x, q.y); }, {at: '앞으로 절차와'});
 await ctx.say('i305-0305', async () => { await c.move(view.w - 260, 200); }, {at: '이 일곱 절차마다'});
 return {segment: 'i305-03', view, next: 'i305-04: 웹 VS Code 공간에서 Codex와 자료 파악(가이드 2단계)', aiRequests: 0};
};
