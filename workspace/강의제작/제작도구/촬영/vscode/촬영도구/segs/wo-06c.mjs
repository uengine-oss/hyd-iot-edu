// 06-2 구간 06c(첫 페이지): R14(읽기 — 결과 화면 「교체부품 칸이 빈 구성 요소」 줄들이 왜 이어지지 않았는지 원자료 · 메모 줄로)를 보내고 답이 끝날 때까지.
// 시작: 첫 페이지는 wo-06a 끝 화면(사이에 둘째 페이지 wo-06b) — 앞 take wo-06a. 끝: R14 답이 선 화면. 큐 wo0681은 대본 wo0603을 나눈 뒤쪽(판정 문서 「막힌 곳 ①」).
import {ui, RESUME, QE, guideIn, seamOut, keepEnd, paste, send, answer, waitSay, askOf} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 0);
 const G = await guideIn(c, ctx, 'vs', {items: QE, ring: 'm2'});
 await c.installPointer(ctx.prev ? null : {x: 900, y: 460});
 await ctx.begin();
 let since = RESUME;
 if (since == null) await ctx.say('wo0681', async () => { await paste(c, ctx, askOf('wo0681')); since = await send(c, ctx, '찾아 달라고 하죠'); }, {at: '관계 표를 적을 때'});
 const waited = [];
 if (await waitSay(c, ctx, since, 'wo0691')) waited.push('wo0691');
 const r = await answer(c, ctx, since);
 const cut = await seamOut(c, ctx, G);
 await keepEnd(c, ctx, '06c');
 return {segment: 'wo-06c', page: 0, cut, ask: 'R14', aiRequests: since == null ? 0 : 1, answer: r.message, codexMs: r.ms, used: r.used, waitLines: waited, next: 'wo-06d: R14 답 · 메모 22행 · 모델 파일 둘'};
};
