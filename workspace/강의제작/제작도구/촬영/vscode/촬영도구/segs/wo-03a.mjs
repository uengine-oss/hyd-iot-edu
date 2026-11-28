// 06-2 구간 03a(첫 페이지): 스키마 표 세 장 → 질문의 낱말을 가르는 기준 → R3(읽기 — 낱말 가르기 · 물리량 묶음 수 · 식별자 선택지)을 보내고, 기다리는 동안 더 물은 두 가지를 말한다. 답이 끝날 때까지.
// 시작: wo-02d 끝(둘째 페이지) 다음 — 첫 페이지는 wo-02c 끝 화면(앞 take: wo-02c를 주면 화살표가 그 자리에서 시작한다). 끝: R3 답이 다 선 화면. 같은 대화에 이어 보낸다(새 대화를 열지 않는다).
import {atPhrase} from './lab-common.mjs';
import {ui, RESUME, QE, Q, guideIn, guideRing, guideHide, guideShow, guideErase, seamOut, keepEnd, open, mark, label, note, SORT, NOTE, speechEnd, paste, send, answer, askOf} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 0);
 const G = await guideIn(c, ctx, 'vs', {items: QE, ring: RESUME == null ? 'm1' : 'm2'});
 await c.installPointer(ctx.prev ? null : {x: 900, y: 460});
 await ctx.begin();
 let since = RESUME;
 if (since == null) {
  const S = c.pen(SORT);
  await ctx.say('wo0321', async () => {
   await guideRing(G, 'm2');
   await atPhrase(ctx, 'classes에는'); await c.emph(label('classes.csv'), {shape: 'band'});
   await atPhrase(ctx, 'properties에는'); await c.emph(label('properties.csv'), {shape: 'band'});
   await atPhrase(ctx, 'relations에는'); await c.emph(label('relations.csv'), {shape: 'band'});
   await atPhrase(ctx, '무엇을 적을지는'); await guideErase(G, ...Q); await note(c, 'qBig');   // 구석의 질문 글상자를 가운데로 키운다
   await atPhrase(ctx, '따로 가리킬 대상이면 클래스'); await guideHide(G); await S.draw('t1');   // 글상자 옆 석 줄 — 펜 그림은 하나라 길잡이를 잠시 걷는다
   await atPhrase(ctx, '그 대상을 설명하는 값이면 속성'); await S.draw('t2');
   await atPhrase(ctx, '두 대상을 이어 주는 말이면 관계'); await S.draw('t3');
  }, {at: '둘째 칸으로 넘어온'});
  await ctx.say('wo0322', async () => {
   await S.hide(); await c.note(null); G.items.push(...Q); await guideShow(G);   // 글상자를 구석으로 줄인다
   await paste(c, ctx, askOf('wo0322'));
   since = await send(c, ctx, '같이 적어 달라고 했어요');
  }, {at: '낱말이 꽤 많으니까'});
 }
 await ctx.say('wo0323', async () => {
  await open(c, ctx, 'data/sensors.csv'); await mark(c, ctx, 1, {cell: 4, shape: 'box'});
  await atPhrase(ctx, '그래서 속성으로만 둘 때와'); await note(c, 'more');
 }, {at: '센서 표에는 재는것이라는'});
 await ctx.say('wo0336', async () => {
  await note(c, 'more2');
  await speechEnd(ctx); await c.note(null);
 }, {at: '다른 하나는 식별자'});
 const r = await answer(c, ctx, since);
 const cut = await seamOut(c, ctx, G);
 await keepEnd(c, ctx, '03a');
 return {segment: 'wo-03a', page: 0, cut, ask: 'R3', aiRequests: since == null ? 0 : 1, answer: r.message, codexMs: r.ms, used: r.used, next: 'wo-03b: R3 답 보기 · R4(classes.csv)'};
};
