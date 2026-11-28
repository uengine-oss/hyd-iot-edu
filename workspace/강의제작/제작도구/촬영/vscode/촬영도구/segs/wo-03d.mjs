// 06-2 구간 03d(둘째 페이지 — PAGE=1): F5 → 클래스 카드의 두 수(센서 41 → 41) · 「재는것」 15가지 → 구성 요소 41 → 40 · 맨 위 「겹치는 원자료 행 1곳」 → 길잡이에 「남은 일」. Codex 부탁 없음.
// 시작: 둘째 페이지에 기대 답 화면(wo-02d 끝) — 앞 take wo-03c를 준다. 끝: 클래스와 식별자 화면, 길잡이에 남은 일.
import {atPhrase} from './lab-common.mjs';
import {ui, guideIn, guideAdd, seamOut, resultStart, f5, verdict, card, pageTo, TITLE} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 1);
 await resultStart(c, ctx, TITLE.expected);
 const G = await guideIn(c, ctx, 'res', {ring: 'm2'});
 await c.installPointer(ctx.prev ? null : {x: 1400, y: 500});
 await ctx.begin();
 await ctx.say('wo0327', async () => {
  await f5(c, ctx, 'classes', G);
  await atPhrase(ctx, '센서는 마흔한 줄에'); const b = await pageTo(c, ctx, () => card(c, ctx, '센서', 'badge')); await c.emph({box: b.box}, {shape: 'underline'});
  await atPhrase(ctx, '맨 아래 카드에는'); const k = await pageTo(c, ctx, () => card(c, ctx, '15가지', 'head')); await c.emph({box: k.box}, {shape: 'underline'});
 }, {at: '카드 오른쪽에'});
 await ctx.say('wo0343', async () => {
  const b = await pageTo(c, ctx, () => card(c, ctx, '구성 요소', 'badge')); await c.emph({box: b.box}, {shape: 'box'});
  await atPhrase(ctx, '맨 위에도'); await pageTo(c, ctx, () => c.serial(() => ctx.p.evaluate(() => { const r = document.querySelector('.verdict').getBoundingClientRect(); return {x: r.x, y: r.y + 140}; }))); await c.emph(verdict(), {shape: 'underline'});
  await atPhrase(ctx, '화면에 표시해 둘게요'); await guideAdd(G, 'todo');
 }, {at: '그런데 한 군데가'});
 const cut = await seamOut(c, ctx, G);
 return {segment: 'wo-03d', page: 1, cut, aiRequests: 0, next: 'wo-03e: properties.csv 머리 · R5'};
};
