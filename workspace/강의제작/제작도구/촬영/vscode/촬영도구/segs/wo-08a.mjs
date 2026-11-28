// 06-2 구간 08a(첫 페이지): 정답표의 약점 — expected.csv 지금 줄들 · 더 물을 것(글상자) → R15(쓰기 — HYD-04 · RF-10 · 없는 품번의 기대 답)를 보내고 답이 끝날 때까지.
// 시작: 첫 페이지는 wo-07a 끝 화면(사이에 둘째 페이지 wo-07b) — 앞 take wo-07a. 끝: R15 답이 선 화면 → 녹화 뒤 사본 SEG=08a.
import {atPhrase} from './lab-common.mjs';
import {ui, RESUME, QE, guideIn, seamOut, keepEnd, open, dataRows, visibleLines, ln, note, paste, send, answer, waitSay, askOf} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 0);
 const G = await guideIn(c, ctx, 'vs', {items: QE, ring: 'm5'});
 await c.installPointer(ctx.prev ? null : {x: 900, y: 460});
 await ctx.begin();
 let since = RESUME;
 if (since == null) {
  await ctx.say('wo0811', async () => {
   const d = await dataRows('app/features/expected.csv');
   await open(c, ctx, 'app/features/expected.csv'); const [, last] = await visibleLines(c, ctx);
   await c.emph(await ln(c, ctx, d.first, {to: Math.min(d.last, last)}), {shape: 'band'});
   await atPhrase(ctx, '정답표에 없던 것을'); await note(c, 'ask4');
  }, {at: '제가 설계하면서 줄곧'});
  await ctx.say('wo0812', async () => {
   await paste(c, ctx, askOf('wo0812'));
   since = await send(c, ctx, '중요하죠'); await c.note(null);
  }, {at: '없는 품번을 일부러'});
 }
 const waited = [];
 if (await waitSay(c, ctx, since, 'wo0891')) waited.push('wo0891');
 const r = await answer(c, ctx, since);
 const cut = await seamOut(c, ctx, G);
 await keepEnd(c, ctx, '08a');
 return {segment: 'wo-08a', page: 0, cut, ask: 'R15', aiRequests: since == null ? 0 : 1, answer: r.message, codexMs: r.ms, used: r.used, waitLines: waited, next: 'wo-08b: 더한 줄 열어 보기 · python run.py query'};
};
