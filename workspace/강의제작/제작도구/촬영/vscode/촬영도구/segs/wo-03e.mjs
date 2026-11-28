// 06-2 구간 03e(첫 페이지): properties.csv 머리(원자료_칸 · 자료형 · 필수) → R5(읽기 — 속성 · 관계에서 정할 것 다섯)를 보내고, 기다리는 동안 PS1 단위(센서 표)와 relations.csv 머리를 짚는다. 답이 끝날 때까지.
// 시작: wo-03c 끝 화면(첫 페이지 — 사이에 둘째 페이지 wo-03d). 끝: R5 답이 선 화면.
import {atPhrase} from './lab-common.mjs';
import {ui, RESUME, QE, guideIn, seamOut, keepEnd, open, tab, mark, markAll, note, speechEnd, paste, send, answer, waitSay, askOf} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 0);
 const G = await guideIn(c, ctx, 'vs', {items: [...QE, 'todo'], ring: 'm2'});
 await c.installPointer(ctx.prev ? null : {x: 900, y: 460});
 await ctx.begin();
 let since = RESUME;
 if (since == null) {
  await ctx.say('wo0328', async () => {
   await open(c, ctx, 'app/features/properties.csv');
   await atPhrase(ctx, '원자료의 어느 칸에서'); await mark(c, ctx, 2, {cell: 2, shape: 'underline'});
   await atPhrase(ctx, '자료형이 수인지'); await mark(c, ctx, 2, {cell: 3, shape: 'underline'});
   await atPhrase(ctx, '비워 둬도 되는지'); await mark(c, ctx, 2, {cell: 4, shape: 'underline'});
  }, {at: '다음은 속성 표와'});
  await ctx.say('wo0342', async () => {
   await paste(c, ctx, askOf('wo0342'));
   since = await send(c, ctx, '세어 달라고 했어요');
  }, {at: '자료형은 그 값으로'});
 }
 await ctx.say('wo0329', async () => {
  await tab(c, ctx, 'sensors.csv');
  for (const n of [5, 15, 35]) { await mark(c, ctx, n, {cell: 5, shape: 'underline', keep: n !== 5, point: n === 5}); await mark(c, ctx, n, {cell: 6, shape: 'underline', keep: true, point: false}); }
  await atPhrase(ctx, 'HYD-03만 MPa로'); await mark(c, ctx, 25); await mark(c, ctx, 25, {cell: 5, shape: 'box', keep: true, point: false}); await mark(c, ctx, 25, {cell: 6, shape: 'box', keep: true, point: false});
  await atPhrase(ctx, '같은 압력을 다른 단위로'); await note(c, 'mpa');
  await speechEnd(ctx); await c.note(null);
 }, {at: 'PS1을 설비마다'});
 await ctx.say('wo0338', async () => {
  await open(c, ctx, 'app/features/relations.csv');
  await atPhrase(ctx, '어느 클래스에서 어느 클래스로'); await mark(c, ctx, 2, {cell: 2, shape: 'underline'}); await mark(c, ctx, 2, {cell: 3, shape: 'underline', keep: true, point: false});
  await atPhrase(ctx, '카디널리티는 무엇으로'); await mark(c, ctx, 2, {cell: 4, shape: 'underline'});
  await atPhrase(ctx, '적어도 하나는 꼭'); await mark(c, ctx, 2, {cell: 5, shape: 'underline'});
  await atPhrase(ctx, '문장으로 읽어서'); await mark(c, ctx, 2, {cell: 1, shape: 'underline'});
 }, {at: '나머지 셋은'});
 const waited = [];
 if (await waitSay(c, ctx, since, 'wo0395')) waited.push('wo0395');
 const r = await answer(c, ctx, since);
 const cut = await seamOut(c, ctx, G);
 await keepEnd(c, ctx, '03e');
 return {segment: 'wo-03e', page: 0, cut, ask: 'R5', aiRequests: since == null ? 0 : 1, answer: r.message, codexMs: r.ms, used: r.used, waitLines: waited, next: 'wo-03f: R5 답(속성 쪽) · R6(properties.csv)'};
};
