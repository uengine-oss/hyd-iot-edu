// 06-2 구간 05f(둘째 페이지 — PAGE=1): F5 → 「센서 41개가 물리량 11개로」 · 유온 묶음(TS1 넷) · 탱크 유온 묶음의 HYD-07:TI-1 · 혼자인 센서 카드(HYD-04:FS2) → 단위를 바꾼 센서 카드(HYD-03:PS1 · HYD-04:EPS1). Codex 부탁 없음.
// 시작: 둘째 페이지에 구성 요소 이름과 실물 화면(wo-04f 끝) — 앞 take wo-05e를 준다. 끝: 물리량과 센서 화면.
import {atPhrase} from './lab-common.mjs';
import {ui, guideIn, seamOut, resultStart, f5, verdict, card, gatherRow, pageTo, TITLE} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 1);
 await resultStart(c, ctx, TITLE.names);
 const G = await guideIn(c, ctx, 'res', {ring: 'm2'});
 await c.installPointer(ctx.prev ? null : {x: 1400, y: 500});
 await ctx.begin();
 await ctx.say('wo0515', async () => {
  await f5(c, ctx, 'quantities', G);
  await c.emph(verdict(), {shape: 'underline'});
  await atPhrase(ctx, '그림에서 유온 묶음에는'); const u = await pageTo(c, ctx, () => gatherRow(c, ctx, '유온', 'left')); await c.emph({rects: u.rects}, {shape: 'box'});
  await atPhrase(ctx, '탱크 유온 묶음에는'); const t = await pageTo(c, ctx, () => gatherRow(c, ctx, '탱크 유온', {chip: 'HYD-07:TI-1'})); await c.emph({rects: t.rects}, {shape: 'box'});
  await atPhrase(ctx, '그 아래에는 카드가'); const h = await pageTo(c, ctx, () => card(c, ctx, 'HYD-04:FS2', 'head'), 130, 760); await c.emph({box: h.box}, {shape: 'underline'});
  await atPhrase(ctx, 'HYD-04의 냉각수 유량이네요'); await c.emph({box: (await card(c, ctx, 'HYD-04:FS2', {li: '붙인 물리량 이름'})).box}, {shape: 'underline'}); await c.emph({box: (await card(c, ctx, 'HYD-04:FS2', {li: '원자료 행'})).box}, {shape: 'underline', keep: true, point: false});
 }, {at: '센서 마흔한 개가'});
 await ctx.say('wo0516', async () => {
  const b = await pageTo(c, ctx, () => card(c, ctx, 'HYD-03:PS1', 'badge'), 130, 760); await c.emph({box: b.box}, {shape: 'underline'});
  await c.emph({box: (await card(c, ctx, 'HYD-03:PS1', {li: '원래 정상값'})).box}, {shape: 'underline', keep: true, point: false}); await c.emph({box: (await card(c, ctx, 'HYD-03:PS1', {li: '바꾼 정상값'})).box}, {shape: 'underline', keep: true, point: false});
  await atPhrase(ctx, '옆 카드의 HYD-04 모터'); await c.emph({box: (await card(c, ctx, 'HYD-04:EPS1', 'badge')).box}, {shape: 'underline'});
 }, {at: 'HYD-03의 토출 압력이'});
 const cut = await seamOut(c, ctx, G);
 return {segment: 'wo-05f', page: 1, cut, aiRequests: 0, next: 'wo-06a: 교체부품 칸 · 품번 표 · python run.py parts'};
};
