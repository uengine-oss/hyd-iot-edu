// 06-2 구간 04b(둘째 페이지 — PAGE=1): F5 → 여전히 「겹치는 원자료 행 1곳」 · 겹친 곳 카드(HYD-02:유압 펌프 · 13 · 14행) · 「인스턴스 하나가 됩니다」 · 첫 번째 질문 → 남은 일을 걷고 길잡이 ②. Codex 부탁 없음.
// 시작: 둘째 페이지에 관계와 카디널리티 화면(wo-03k 끝) — 앞 take wo-04a를 준다. 끝: 클래스와 식별자 화면.
// 「구석의 질문 글상자 ①」 — 결과 화면의 길잡이에는 질문 줄을 두지 않아(자리 — 판정 문서) 질문 ①을 글상자로 잠깐 띄워 짚는다.
import {atPhrase} from './lab-common.mjs';
import {ui, PICK, guideIn, guideErase, guideRing, seamOut, resultStart, f5, verdict, verdictSub, card, pageTo, note, speechEnd, TITLE} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 1);
 await resultStart(c, ctx, TITLE.relations);
 const G = await guideIn(c, ctx, 'res', {items: ['todo'], ring: 'm3'});
 await c.installPointer(ctx.prev ? null : {x: 1400, y: 500});
 await ctx.begin();
 await ctx.say('wo0421', async () => {
  await f5(c, ctx, 'classes', G);
  await atPhrase(ctx, '여전히 걸려 있습니다'); await c.emph(verdict(), {shape: 'underline'});
  await atPhrase(ctx, '겹친 곳은'); const h = await pageTo(c, ctx, () => card(c, ctx, PICK.clash, 'head')); await c.emph({box: h.box}, {shape: 'underline'});
  await atPhrase(ctx, '13행과 14행이라고'); await c.emph({box: (await card(c, ctx, PICK.clash, {li: '겹친 원자료 행', chip: 'components.csv:13'})).box}, {shape: 'underline'});
  await atPhrase(ctx, '인스턴스 하나로 합쳐져요'); await pageTo(c, ctx, () => c.serial(() => ctx.p.evaluate(() => { const r = document.querySelector('.verdict span').getBoundingClientRect(); return {x: r.x, y: r.y}; })));
  await c.emph(verdictSub(), {shape: 'underline', phrase: '겹친 식별자 하나는 인스턴스 하나가 됩니다'});
  await atPhrase(ctx, '우리 첫 번째 질문'); await note(c, 'q1'); await c.emph({note: 1}, {shape: 'underline', phrase: '그 자리에 어떤 장치(일련번호)가 달렸나'});
  await speechEnd(ctx); await c.note(null); await guideErase(G, 'todo'); await guideRing(G, 'm2');
 }, {at: 'classes를 다시 돌려 보면'});
 const cut = await seamOut(c, ctx, G);
 return {segment: 'wo-04b', page: 1, cut, aiRequests: 0, next: 'wo-04c: 원자료 13 · 14행 · 자리와 실물 · R8'};
};
