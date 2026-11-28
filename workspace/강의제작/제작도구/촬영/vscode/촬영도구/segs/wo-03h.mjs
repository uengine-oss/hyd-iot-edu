// 06-2 구간 03h(둘째 페이지 — PAGE=1): F5 → 「속성 N개가 원자료 행과 모두 맞습니다」 · 센서 카드의 필수 · 원자료 칸 · 줄 끝 값 → 「자세히 보기」를 펴고 limit의 빈 행 30. Codex 부탁 없음.
// 시작: 둘째 페이지에 클래스와 식별자 화면(wo-03d 끝) — 앞 take wo-03g를 준다. 끝: 속성과 자료형 화면(자세히 보기를 편 채).
import {atPhrase} from './lab-common.mjs';
import {ui, PICK, guideIn, seamOut, resultStart, f5, verdict, card, foldCell, pageTo, TITLE} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 1);
 await resultStart(c, ctx, TITLE.classes);
 const G = await guideIn(c, ctx, 'res', {items: ['todo'], ring: 'm2'});
 await c.installPointer(ctx.prev ? null : {x: 1400, y: 500});
 await ctx.begin();
 await ctx.say('wo0331', async () => {
  await f5(c, ctx, 'properties', G);
  const st = await c.serial(() => ctx.p.evaluate(() => document.querySelector('.verdict')?.className ?? ''));
  if (!st.includes('v-ok')) throw Error('wo0331: 속성 화면의 결론이 「모두 맞습니다」가 아님(' + st + ') — 대본 「Codex 답에 맞출 큐」의 「걸리는 장면」을 새 큐로 정한다');
  await atPhrase(ctx, '모두 맞다고 나왔네요'); await c.emph(verdict(), {shape: 'underline'});
  const li = name => card(c, ctx, '센서', {li: name, name: true});
  await atPhrase(ctx, '필수라고 붙은 것과'); await pageTo(c, ctx, () => li(PICK.tag + ' (필수)'));
  await c.emph({box: (await li(PICK.tag + ' (필수)')).box}, {shape: 'underline'}); await c.emph({box: (await li(PICK.unit + ' (필수)')).box}, {shape: 'underline', keep: true, point: false}); await c.emph({box: (await li(PICK.limit)).box}, {shape: 'underline', keep: true, point: false});
  await atPhrase(ctx, '바로 옆에 원자료의'); await c.emph({box: (await card(c, ctx, '센서', {li: PICK.tag + ' (필수)', chip: '태그 칸'})).box}, {shape: 'underline'});
  await atPhrase(ctx, '줄 끝에 있는 값은'); await c.emph({sel: '.card li .chip', text: '글자 — TS1'}, {shape: 'underline', phrase: 'TS1'});
  await atPhrase(ctx, '아래 표를 펼치면'); await pageTo(c, ctx, () => c.serial(() => ctx.p.evaluate(() => { const b = document.querySelector('details.more > summary').getBoundingClientRect(); return {x: b.x + 40, y: b.y + b.height / 2}; })), 130, 700);
  await c.clickSel('details.more > summary');
  const cell = () => foldCell(c, ctx, '속성마다 원자료에 채워진 행', ['센서', PICK.limit], 7);
  await c.emph({box: (await pageTo(c, ctx, cell)).box}, {shape: 'box'});
 }, {at: '걸린 줄 없이'});
 const cut = await seamOut(c, ctx, G);
 return {segment: 'wo-03h', page: 1, cut, aiRequests: 0, next: 'wo-03i: R5 답(관계 쪽) · R7(relations.csv)'};
};
