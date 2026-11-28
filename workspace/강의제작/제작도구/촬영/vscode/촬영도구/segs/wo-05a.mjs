// 06-2 구간 05a(첫 페이지): 두 번째 질문 — 센서 표의 TS1 · TS2 · TS3, 오일 온도(12행) · 이동식 유온계(41행) → 두 길(글상자) · decisions 5행 → R10(읽기 — 묶을 때 · 나눌 때)을 보내고, 기다리는 동안 고를 기준을 세운다. 답이 끝날 때까지.
// 시작: 첫 페이지는 wo-04e 끝 화면(사이에 둘째 페이지 wo-04f) — 앞 take wo-04e. 끝: R10 답이 선 화면, 두 길 글상자가 떠 있다(다음 구간 첫 말에서 걷는다 — 이음새에서는 다시 띄운다).
import {atPhrase} from './lab-common.mjs';
import {ui, RESUME, QE, guideIn, guideRing, guideAdd, guideErase, seamOut, keepEnd, open, mark, markAll, note, NOTE, noteIn, paste, send, answer, waitSay, askOf} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 0);
 const G = await guideIn(c, ctx, 'vs', {items: QE, ring: 'm2'});
 if (RESUME != null) await noteIn(ctx, 'ways');
 await c.installPointer(ctx.prev ? null : {x: 900, y: 460});
 await ctx.begin();
 let since = RESUME;
 if (since == null) {
  await ctx.say('wo0501', async () => {
   await guideRing(G, 'm2');
   await atPhrase(ctx, '같은 물리량을 재는 센서를'); await c.emph({pen: 'q2'}, {shape: 'underline'});
   await atPhrase(ctx, '센서 표에서 HYD-01의'); await open(c, ctx, 'data/sensors.csv'); await mark(c, ctx, 2, {to: 4});
   await atPhrase(ctx, 'TS1은 유온'); await markAll(c, ctx, [2, 3, 4], {cell: 4, shape: 'underline'});
   await atPhrase(ctx, '정상값도 세 줄이'); await markAll(c, ctx, [2, 3, 4], {cell: 6, shape: 'underline'});
  }, {at: '남은 한 군데가'});
  await ctx.say('wo0502', async () => {
   await mark(c, ctx, 12); await mark(c, ctx, 12, {cell: 4, shape: 'underline', keep: true, point: false});
   await atPhrase(ctx, '맨 아래쪽'); await mark(c, ctx, 41); await mark(c, ctx, 41, {cell: 4, shape: 'underline', keep: true, point: false}); await mark(c, ctx, 41, {cell: 3, shape: 'underline', keep: true, point: false});
   await atPhrase(ctx, '이름이 달라도 같은 것이'); await note(c, 'same');
  }, {at: 'HYD-02의 TS1을'});
  await ctx.say('wo0503', async () => {
   await note(c, 'ways');   // 글상자를 걷고 두 길을 글로 — 글상자는 하나라 바꿔 띄운다
   await atPhrase(ctx, 'decisions의 둘째 줄'); await guideAdd(G, 'dec5');
   await atPhrase(ctx, '하는 순서는 펌프 때와'); await guideErase(G, 'dec5'); await paste(c, ctx, askOf('wo0503'));
   since = await send(c, ctx, '같이 물어 둡니다');
  }, {at: '길은 이번에도'});
 }
 await ctx.say('wo0504', async () => {
  await note(c, 'ways2', NOTE.ways2.lines.slice(0, 3));
  await atPhrase(ctx, '탱크끼리만 모여'); await note(c, 'ways2');
  await atPhrase(ctx, '우리한테 물은 사람은'); await c.emph({pen: 'q2'}, {shape: 'underline', phrase: '단위 · 정상값 · 한계'});
 }, {at: '몇 군데인지만 세려는'});
 const waited = [];
 if (await waitSay(c, ctx, since, 'wo0596')) waited.push('wo0596');
 const r = await answer(c, ctx, since);
 const cut = await seamOut(c, ctx, G, {note: true});
 await keepEnd(c, ctx, '05a');
 return {segment: 'wo-05a', page: 0, cut, ask: 'R10', aiRequests: since == null ? 0 : 1, answer: r.message, codexMs: r.ms, used: r.used, waitLines: waited, next: 'wo-05b: R10 답 보기 · TS1 넷 · R11'};
};
