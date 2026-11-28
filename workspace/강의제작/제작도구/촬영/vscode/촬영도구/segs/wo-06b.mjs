// 06-2 구간 06b(둘째 페이지 — PAGE=1): F5 → 「교체부품 칸 35개를 부품 11개에」(셈 글상자) · P-PMP-SEAL 줄 · 「카디널리티 안에」 · 교체부품 칸이 빈 구성 요소 다섯 줄(모터). Codex 부탁 없음.
// 시작: 둘째 페이지에 물리량과 센서 화면(wo-05f 끝) — 앞 take wo-06a를 준다. 끝: 부품과 모델 화면(빈 칸 표까지 굴린 채). 큐 wo0603은 대본 wo0603을 나눈 앞쪽(판정 문서 「막힌 곳 ①」).
import {atPhrase} from './lab-common.mjs';
import {ui, guideIn, seamOut, resultStart, f5, verdict, verdictSub, gatherRow, tableRows, pageTo, note, TITLE} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 1);
 await resultStart(c, ctx, TITLE.quantities);
 const G = await guideIn(c, ctx, 'res', {ring: 'm2'});
 await c.installPointer(ctx.prev ? null : {x: 1400, y: 500});
 await ctx.begin();
 await ctx.say('wo0603', async () => {
  await f5(c, ctx, 'parts', G);
  await c.emph(verdict(), {shape: 'underline'}); await note(c, 'sum35');
  await atPhrase(ctx, '그림에서 왼쪽의'); await c.note(null); const r = await pageTo(c, ctx, () => gatherRow(c, ctx, 'P-PMP-SEAL')); await c.emph({rects: r.rects}, {shape: 'box'});
  await atPhrase(ctx, '맨 위에는 만든 연결이'); await pageTo(c, ctx, () => c.serial(() => ctx.p.evaluate(() => { const b = document.querySelector('.verdict span').getBoundingClientRect(); return {x: b.x, y: b.y}; })));
  await c.emph(verdictSub(), {shape: 'underline', phrase: '만든 연결은 모두 내가 정한 카디널리티 안에 있습니다'});
  await atPhrase(ctx, '조금 내려가면'); const t = await pageTo(c, ctx, () => tableRows(c, ctx, '교체부품 칸이 빈 구성 요소'), 130, 700); await c.emph({rects: t.rects}, {shape: 'band'});
  await atPhrase(ctx, '전부 모터입니다'); await c.emph({rects: (await tableRows(c, ctx, '교체부품 칸이 빈 구성 요소', 2)).rects}, {shape: 'underline'});
 }, {at: '교체부품 칸 서른다섯 개가'});
 const cut = await seamOut(c, ctx, G);
 return {segment: 'wo-06b', page: 1, cut, aiRequests: 0, next: 'wo-06c: R14(빈 칸의 까닭) — 첫 페이지'};
};
