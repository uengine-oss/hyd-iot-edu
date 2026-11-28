// 06-2 구간 03i(첫 페이지): R5 답의 관계 쪽으로 굴러 올라가 보기(문장 네 줄 · 카디널리티 · 구성 요소와 부품 — 구성 요소 표 1~5행) → R7(쓰기 — relations.csv)를 보내고 답이 끝날 때까지.
// 시작: 첫 페이지는 wo-03g 끝 화면(R6 답이 선 대화 — 사이에 둘째 페이지 wo-03h). 앞 take wo-03g를 주면 화살표가 그 자리에서 시작한다. 끝: R7 답이 선 화면 → 녹화 뒤 사본 SEG=03i.
// R5 답은 R6 대화보다 위에 있다 — FIND(r5Read* · r5Card* · r5Least*)는 R5 답에만 든 글로 고른다(아래 R6 답에 같은 글이 있으면 여럿으로 멈춘다).
import {atPhrase} from './lab-common.mjs';
import {ui, RESUME, QE, guideIn, seamOut, keepEnd, open, tab, mark, markAll, cx, cxIn, cxMark, toAnswer, paste, send, answer, waitSay, askOf} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 0);
 const G = await guideIn(c, ctx, 'vs', {items: [...QE, 'todo'], ring: 'm2'});
 if (RESUME == null) await cx(c, ctx, 'r5Read1');
 await c.installPointer(ctx.prev ? null : {x: 1500, y: 600});
 await ctx.begin();
 let since = RESUME;
 if (since == null) {
  await ctx.say('wo0332', async () => {
   await cxIn(c, ctx, 'r5Read1', 0.15);   // 「VS Code로 돌아와 Codex 답을 굴려」 — R6 대화 위의 R5 답으로 올라간다
   await atPhrase(ctx, '설비는 구성 요소를 가진다'); await cxMark(c, ctx, 'r5Read1', 'band', {scroll: false});
   await atPhrase(ctx, '구성 요소는 센서로'); await cxMark(c, ctx, 'r5Read2', 'band');
   await atPhrase(ctx, '센서는 물리량을'); await cxMark(c, ctx, 'r5Read3', 'band');
   await atPhrase(ctx, '구성 요소는 부품을'); await cxMark(c, ctx, 'r5Read4', 'band');
   await atPhrase(ctx, '우리 첫 번째 질문이'); await c.emph({pen: 'q1'}, {shape: 'underline'});
  }, {at: '아까 받은 답의'});
  await ctx.say('wo0334', async () => {
   await cxMark(c, ctx, 'r5CardAsset', 'underline');
   await atPhrase(ctx, '센서에서 물리량은'); await cxMark(c, ctx, 'r5CardSensor', 'underline');
  }, {at: '설비에서 구성 요소는'});
  await ctx.say('wo0341', async () => {
   await cxMark(c, ctx, 'r5CardPart', 'underline');
   await atPhrase(ctx, '구성 요소 표에 교체부품 칸이'); await open(c, ctx, 'data/components.csv'); await mark(c, ctx, 1, {cell: 3, shape: 'box'});
   await markAll(c, ctx, [2, 3, 4], {cell: 3, shape: 'underline', keep: true, point: false});
   await atPhrase(ctx, '반대로 같은 부품은'); await toAnswer(c, ctx);
  }, {at: 'Codex가 개수를 둘로'});
  await ctx.say('wo0335', async () => {
   await cxMark(c, ctx, 'r5Least', 'underline');
   await atPhrase(ctx, '다섯 줄이 걸린대요'); await cxMark(c, ctx, 'r5LeastPart', 'underline');
   await atPhrase(ctx, '구성 요소 표 5행'); await tab(c, ctx, 'components.csv'); await mark(c, ctx, 5); await mark(c, ctx, 5, {cell: 3, shape: 'box', keep: true, point: false});
   await atPhrase(ctx, '없음으로 둘게요'); await paste(c, ctx, askOf('wo0335'));
   since = await send(c, ctx, '적어서 보냅니다');
  }, {at: '마지막은 이 관계가'});
 }
 const waited = [];
 if (await waitSay(c, ctx, since, 'wo0394')) waited.push('wo0394');
 const r = await answer(c, ctx, since);
 const cut = await seamOut(c, ctx, G);
 await keepEnd(c, ctx, '03i');
 return {segment: 'wo-03i', page: 0, cut, ask: 'R7', aiRequests: since == null ? 0 : 1, answer: r.message, codexMs: r.ms, used: r.used, waitLines: waited, next: 'wo-03j: python run.py relations'};
};
