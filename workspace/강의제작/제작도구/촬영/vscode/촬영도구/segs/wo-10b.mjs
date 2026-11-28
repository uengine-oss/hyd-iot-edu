// 06-2 구간 10b(둘째 페이지 — PAGE=1): F5 → 「기대 답과 같음 N/N」 — 「답도 아까와 똑같네요」. Codex 부탁 없음.
// 시작: 둘째 페이지에 질문별 대조 화면(wo-09h 끝) — 앞 take wo-10a를 준다. 끝: 같은 화면(다시 연 폴더의 결과).
// 큐 wo1081은 대본 wo1001을 나눈 셋째 조각이고 앞 조각(wo1083)이 쉼표로 끝난 한 문장 안이라, 구간 경계 쉼을 두지 않는다(영상 V-14 잇기 — 이음새 쉼은 앞 take의 꼬리와 F5뿐).
import {atPhrase} from './lab-common.mjs';
import {ui, guideIn, seamOut, resultStart, f5, verdict, TITLE} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 1);
 await resultStart(c, ctx, TITLE.query);
 const G = await guideIn(c, ctx, 'res', {ring: 'm5'});
 await c.installPointer(ctx.prev ? null : {x: 1400, y: 500});
 await ctx.begin();
 ctx.__said = true;   // lab-common labUi: 01이 아닌 구간 첫 큐 앞의 경계 쉼(PAUSE.segment − tail)을 건너뛴다 — 한 문장의 뒤쪽이다
 await ctx.say('wo1081', async () => {
  await f5(c, ctx, 'query', G);
  await atPhrase(ctx, '똑같네요'); await c.emph(verdict(), {shape: 'underline'});
 }, {at: '답도 아까와'});
 const cut = await seamOut(c, ctx, G);
 return {segment: 'wo-10b', page: 1, cut, aiRequests: 0, next: 'wo-10c: features에 남은 것 · 되짚기 · 결정 표 · 끝'};
};
