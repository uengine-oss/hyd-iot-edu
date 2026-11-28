// 06-2 구간 09h(둘째 페이지 — PAGE=1): F5 → 「기대 답과 같음 N/N」 · 질문 4 줄 같음 · 질문 1~3 줄(흐린 띠) → 길잡이를 한 바퀴(① → ⑤ → ②) 덧긋는다. Codex 부탁 없음.
// 시작: 둘째 페이지에 질문별 대조 화면(wo-09e 끝, 다름 1줄) — 앞 take wo-09g를 준다. 끝: 질문별 대조 화면(모두 같음).
import {atPhrase} from './lab-common.mjs';
import {ui, guideIn, seamOut, resultStart, f5, verdict, cmpRows, pageTo, TITLE} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 1);
 await resultStart(c, ctx, TITLE.query);
 const G = await guideIn(c, ctx, 'res', {ring: 'm5'});
 await c.installPointer(ctx.prev ? null : {x: 1400, y: 500});
 await ctx.begin();
 await ctx.say('wo0917', async () => {
  await f5(c, ctx, 'query', G);
  const st = await c.serial(() => ctx.p.evaluate(() => document.querySelector('.verdict')?.className ?? ''));
  if (!st.includes('v-ok')) throw Error('wo0917: 설치일 속성을 더한 뒤에도 모두 같음이 아님(' + st + ') — 그 줄을 Codex에 보이는 장면을 새 큐로 정한다');
  await atPhrase(ctx, '이번에는 질문 4까지'); await c.emph(verdict(), {shape: 'underline'});
  await pageTo(c, ctx, () => cmpRows(c, ctx, ['4'], true), 130, 900); await c.emph({rects: (await cmpRows(c, ctx, ['4'])).rects}, {shape: 'box'});
  await atPhrase(ctx, '앞의 세 질문도'); await c.emph({rects: (await cmpRows(c, ctx, ['1', '2', '3'])).rects}, {shape: 'band'});
  await atPhrase(ctx, '한 바퀴 더'); await c.clearEmph();
  for (const id of ['m1', 'm2', 'm3', 'm4', 'm5', 'mb']) await G.g.trace(id, {keep: true});
 }, {at: '검증은 그대로 통과했고'});
 const cut = await seamOut(c, ctx, G);
 return {segment: 'wo-09h', page: 1, cut, aiRequests: 0, next: 'wo-10a: 폴더를 닫았다 다시 열고 parts · query'};
};
