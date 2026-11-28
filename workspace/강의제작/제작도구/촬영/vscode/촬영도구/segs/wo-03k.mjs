// 06-2 구간 03k(둘째 페이지 — PAGE=1): F5 → 「관계 4개를 정했습니다」 · 클래스 상자 다섯 · 화살표의 글 → 카드 넷의 「문장으로 읽기」 → 구성 요소와 부품 카드의 카디널리티 · 적어도 하나. Codex 부탁 없음.
// 시작: 둘째 페이지에 속성과 자료형 화면(wo-03h 끝) — 앞 take wo-03j를 준다. 끝: 관계와 카디널리티 화면. 큐 wo0385는 대본 wo0340을 나눈 앞쪽(판정 문서 「막힌 곳 ①」).
// 카드 머리 = 「시작 → 읽는 말 → 종료」(R7 부탁에서 강사가 정한 읽는 말 — 가진다 · 감시된다 · 잰다 · 쓴다).
import {atPhrase} from './lab-common.mjs';
import {ui, guideIn, seamOut, resultStart, f5, verdict, card, pageTo, node, edgeText, TITLE} from './wo-common.mjs';

const CARD = ['설비 → 가진다 → 구성 요소', '구성 요소 → 감시된다 → 센서', '센서 → 잰다 → 물리량', '구성 요소 → 쓴다 → 부품'];
export default async ctx => {
 const c = await ui(ctx, 1);
 await resultStart(c, ctx, TITLE.properties);
 const G = await guideIn(c, ctx, 'res', {items: ['todo'], ring: 'm2'});
 await c.installPointer(ctx.prev ? null : {x: 1400, y: 500});
 await ctx.begin();
 await ctx.say('wo0333', async () => {
  await f5(c, ctx, 'relations', G);
  await c.emph(verdict(), {shape: 'underline'});
  await atPhrase(ctx, '상자가 클래스고'); for (const [i, k] of ['설비', '구성 요소', '센서', '물리량', '부품'].entries()) await c.emph(node(k), {shape: 'box', keep: i > 0, point: i === 0});
  await atPhrase(ctx, '화살표 위에는'); await c.emph(edgeText('설비', '구성 요소'), {shape: 'underline'});
  await atPhrase(ctx, '아래 카드에는');
  const read = k => card(c, ctx, CARD[k], {li: '문장으로 읽기'});
  for (const [k, p] of ['HYD-01은 오일 쿨러를', '오일 쿨러는 유온 센서로', '유온 센서는 유온을', '오일 쿨러는 쿨러 코어를'].entries()) {
   await atPhrase(ctx, p); const b = await pageTo(c, ctx, () => read(k), 130, 980); await c.emph({box: b.box}, {shape: 'band'});
  }
 }, {at: '상자가 클래스고'});
 await ctx.say('wo0385', async () => {
  const b = await pageTo(c, ctx, () => card(c, ctx, CARD[3], {li: '카디널리티'}), 130, 980); await c.emph({box: b.box}, {shape: 'underline'});
  await atPhrase(ctx, '적어도 하나는 없음으로'); await c.emph({box: (await card(c, ctx, CARD[3], {li: '적어도 하나'})).box}, {shape: 'underline'});
 }, {at: '구성 요소와 부품 카드를 보면'});
 const cut = await seamOut(c, ctx, G);
 return {segment: 'wo-03k', page: 1, cut, aiRequests: 0, next: 'wo-03l: 표 세 장(첫 페이지)'};
};
