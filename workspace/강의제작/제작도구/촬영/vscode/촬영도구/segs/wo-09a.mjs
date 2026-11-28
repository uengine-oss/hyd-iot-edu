// 06-2 구간 09a(첫 페이지): 새 질문으로 한 바퀴 더 — 길잡이의 굽은 화살표를 덧긋고 R16(읽기 — 지금 스키마로 답할 수 없는 질문 후보 셋)을 보내고 답이 끝날 때까지.
// 시작: 첫 페이지는 wo-08b 끝 화면(사이에 둘째 페이지 wo-08c) — 앞 take wo-08b. 끝: R16 답이 선 화면.
import {atPhrase} from './lab-common.mjs';
import {ui, RESUME, QE, guideIn, seamOut, keepEnd, paste, send, answer, waitSay, askOf} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 0);
 const G = await guideIn(c, ctx, 'vs', {items: QE, ring: 'm5'});
 await c.installPointer(ctx.prev ? null : {x: 900, y: 460});
 await ctx.begin();
 let since = RESUME;
 if (since == null) await ctx.say('wo0911', async () => {
  await G.g.trace('mb');
  await atPhrase(ctx, '질문 후보는 Codex한테'); await paste(c, ctx, askOf('wo0911'));
  since = await send(c, ctx, '세 개로 받습니다');
 }, {at: '그림의 굽은 화살표가'});
 const waited = [];
 if (await waitSay(c, ctx, since, 'wo0991')) waited.push('wo0991');
 const r = await answer(c, ctx, since);
 const cut = await seamOut(c, ctx, G);
 await keepEnd(c, ctx, '09a');
 return {segment: 'wo-09a', page: 0, cut, ask: 'R16', aiRequests: since == null ? 0 : 1, answer: r.message, codexMs: r.ms, used: r.used, waitLines: waited, next: 'wo-09b: 후보 고르기 · R17(질문 4 기대 답)'};
};
