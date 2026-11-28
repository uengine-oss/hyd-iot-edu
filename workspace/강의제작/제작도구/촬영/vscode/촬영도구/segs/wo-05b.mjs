// 06-2 구간 05b(첫 페이지): 두 길 글상자를 걷고 R10 답 보기(하나로 묶을 때 열세 개 · 나눌 때 · HYD-07 지시계) → TS1 넷의 정상값(46 — 메모 20행) → 재는 곳마다 나누기로 고르고 R11(쓰기 — decisions · expected 질문 2)을 보내고 답이 끝날 때까지.
// 시작: wo-05a 끝(R10 답, 두 길 글상자 — 녹화 전에 다시 띄운다. 앞 take를 준다). 끝: R11 답이 선 화면 → 녹화 뒤 사본 SEG=05b. 답을 짚는 글은 FIND(r10*).
import {atPhrase} from './lab-common.mjs';
import {ui, RESUME, QE, guideIn, seamOut, keepEnd, open, tab, mark, markAll, note, noteIn, cx, cxMark, lineOf, paste, send, answer, waitSay, askOf} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 0);
 const G = await guideIn(c, ctx, 'vs', {items: QE, ring: 'm2'});
 if (RESUME == null) { await noteIn(ctx, 'ways2'); await cx(c, ctx, 'r10Split'); }
 await c.installPointer(ctx.prev ? null : {x: 1500, y: 600});
 await ctx.begin();
 let since = RESUME;
 if (since == null) {
  await ctx.say('wo0505', async () => {
   await c.note(null);
   await atPhrase(ctx, '전부 하나로 묶으면'); await cxMark(c, ctx, 'r10One', 'band');
   await atPhrase(ctx, '온도 센서 열세 개가'); await cxMark(c, ctx, 'r10Count', 'underline');
   await atPhrase(ctx, '재는 곳마다 나누면'); await cxMark(c, ctx, 'r10Split', 'band');
   await atPhrase(ctx, '이동식 설비의 유온계는'); await cxMark(c, ctx, 'r10Ti', 'underline');
  }, {at: '답을 보죠'});
  await ctx.say('wo0506', async () => {
   await tab(c, ctx, 'sensors.csv'); await markAll(c, ctx, [2, 12, 22], {cell: 6, shape: 'underline'});
   await atPhrase(ctx, 'HYD-04 한 대만'); await mark(c, ctx, 32); await mark(c, ctx, 32, {cell: 6, shape: 'box', keep: true, point: false});
   await atPhrase(ctx, '왜 그런지는 메모에'); await open(c, ctx, 'data/field_notes.md'); await mark(c, ctx, 20, {sub: 'HYD-04는 같은 회사의 후속 모델(HPP-45B)입니다. 열교환기가 수냉식이라', shape: 'underline'});
   await atPhrase(ctx, '같은 곳을 재는 센서끼리'); await tab(c, ctx, 'sensors.csv'); await note(c, 'ts46');
  }, {at: '네 대의 TS1을'});
  await ctx.say('wo0507', async () => { await c.note(null); }, {at: '그래서 저는 재는 곳마다'});
  await ctx.say('wo0508', async () => {
   await paste(c, ctx, askOf('wo0508'));
   since = await send(c, ctx, '채워 달라고 합니다');
   await atPhrase(ctx, '이 이름이 곧 식별자가'); await open(c, ctx, 'app/features/classes.csv'); await mark(c, ctx, await lineOf(ctx, 'app/features/classes.csv', '물리량,'), {cell: 2, shape: 'underline'});
  }, {at: '고른 것은 펌프 때와'});
 }
 const waited = [];
 if (await waitSay(c, ctx, since, 'wo0593')) waited.push('wo0593');
 const r = await answer(c, ctx, since);
 const cut = await seamOut(c, ctx, G);
 await keepEnd(c, ctx, '05b');
 return {segment: 'wo-05b', page: 0, cut, ask: 'R11', aiRequests: since == null ? 0 : 1, answer: r.message, codexMs: r.ms, used: r.used, waitLines: waited, next: 'wo-05c: decisions · expected 열어 보기 · quantity_rules.py · R12'};
};
