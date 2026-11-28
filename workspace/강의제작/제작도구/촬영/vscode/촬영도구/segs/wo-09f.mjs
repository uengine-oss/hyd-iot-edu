// 06-2 구간 09f(첫 페이지): R19(쓰기 — properties.csv에 설치일 한 줄, 날짜 · 필수 아니오와 그 이유)를 보내고 답이 끝날 때까지.
// 시작: 첫 페이지는 wo-09d 끝 화면(사이에 둘째 페이지 wo-09e) — 앞 take wo-09d. 끝: R19 답이 선 화면 → 녹화 뒤 사본 SEG=09f.
import {ui, RESUME, QE, guideIn, seamOut, keepEnd, paste, send, answer, waitSay, askOf} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 0);
 const G = await guideIn(c, ctx, 'vs', {items: QE, ring: 'm5'});
 await c.installPointer(ctx.prev ? null : {x: 900, y: 460});
 await ctx.begin();
 let since = RESUME;
 if (since == null) await ctx.say('wo0915', async () => { await paste(c, ctx, askOf('wo0915')); since = await send(c, ctx, '필수로는 두지 않을게요'); }, {at: '이제 스키마를 고칩니다'});
 const waited = [];
 if (await waitSay(c, ctx, since, 'wo0992')) waited.push('wo0992');
 const r = await answer(c, ctx, since);
 const cut = await seamOut(c, ctx, G);
 await keepEnd(c, ctx, '09f');
 return {segment: 'wo-09f', page: 0, cut, ask: 'R19', aiRequests: since == null ? 0 : 1, answer: r.message, codexMs: r.ms, used: r.used, waitLines: waited, next: 'wo-09g: 설치일 줄 · parts → check → query'};
};
