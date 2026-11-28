// 06-2 구간 09e(둘째 페이지 — PAGE=1): F5 → 「기대 답과 같음 N/N — 다름 1줄」 · 질문 4 줄의 다름 · 답할 수 없음(설비 클래스에 속성이 없음). Codex 부탁 없음.
// 시작: 둘째 페이지에 질문별 대조 화면(wo-08c 끝) — 앞 take wo-09d를 준다. 끝: 질문별 대조 화면(질문 4 다름).
// 처음부터 같음이면 지금 스키마로 답이 되는 질문이라 다른 후보로 바꾼다(대본 wo0914) — 여기서는 멈춘다.
import {atPhrase} from './lab-common.mjs';
import {ui, guideIn, seamOut, resultStart, f5, verdict, cmpState, pageTo, TITLE} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 1);
 await resultStart(c, ctx, TITLE.query);
 const G = await guideIn(c, ctx, 'res', {ring: 'm5'});
 await c.installPointer(ctx.prev ? null : {x: 1400, y: 500});
 await ctx.begin();
 await ctx.say('wo0914', async () => {
  await f5(c, ctx, 'query', G);
  await c.emph(verdict(), {shape: 'underline'});
  await atPhrase(ctx, '답 칸에는'); const s = await pageTo(c, ctx, () => cmpState(c, ctx, '다름', 0), 130, 900); await c.emph({box: s.box}, {shape: 'underline'});
  await c.emph({sel: '.tbl.cmp tr[data-st="다름"] td .chip.off', has: '답할 수 없음'}, {shape: 'box'});
 }, {at: '질문 4 줄만'});
 const cut = await seamOut(c, ctx, G);
 return {segment: 'wo-09e', page: 1, cut, aiRequests: 0, next: 'wo-09f: R19(속성 표에 설치일) — 첫 페이지'};
};
