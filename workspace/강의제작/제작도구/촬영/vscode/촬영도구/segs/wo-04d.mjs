// 06-2 구간 04d(첫 페이지): R8 답 보기(겹친 까닭 · 일련번호를 넣으면 35줄 — 구성 요소 표의 일련번호 칸 · 두 길 · 추천 · 끝 문장) → 내 이유로 고르기(질문 ① · 13행 비고 · 날짜) → R9(쓰기 — 결정 하나에 걸린 파일 여섯)를 보내고 답이 끝날 때까지.
// 시작: wo-04c 끝(R8 답이 선 화면, 앞 take를 준다). 끝: R9 답이 선 화면 → 녹화 뒤 사본 SEG=04d. 답을 짚는 글은 FIND(r8*).
import {atPhrase} from './lab-common.mjs';
import {ui, RESUME, QE, guideIn, seamOut, keepEnd, tab, mark, cx, cxMark, toAnswer, say, paste, send, answer, waitSay, askOf} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 0);
 const G = await guideIn(c, ctx, 'vs', {items: QE, ring: 'm2'});
 if (RESUME == null) await cx(c, ctx, 'r8Rec');
 await c.installPointer(ctx.prev ? null : {x: 1500, y: 600});
 await ctx.begin();
 let since = RESUME;
 if (since == null) {
  await ctx.say('wo0422', async () => {
   await cxMark(c, ctx, 'r8Why', 'band');
   await atPhrase(ctx, '서른다섯 줄이 걸린다고'); await cxMark(c, ctx, 'r8Serial', 'underline');
   await atPhrase(ctx, '구성 요소 표를 보면'); await tab(c, ctx, 'components.csv');
   await mark(c, ctx, 13, {cell: 4, shape: 'underline'}); await mark(c, ctx, 14, {cell: 4, shape: 'underline', keep: true, point: false});
   for (const n of [11, 12, 15, 16]) await mark(c, ctx, n, {cell: 4, keep: true, point: false});   // 위아래 구성 요소 줄의 빈 일련번호 칸(흐린 띠 — 그림 층의 띠는 하나뿐)
   await atPhrase(ctx, '두 줄을 풀려다'); await toAnswer(c, ctx);
  }, {at: '겹친 까닭은'});
  await ctx.say('wo0409', async () => {
   await cxMark(c, ctx, 'r8Attr', 'band');
   await atPhrase(ctx, '실물을 따로 두는 길에서는'); await cxMark(c, ctx, 'r8Unit', 'band');
   await atPhrase(ctx, '추천은 실물 쪽인데'); await cxMark(c, ctx, 'r8Rec', 'underline');
   await atPhrase(ctx, '추천일 뿐'); await cxMark(c, ctx, 'r8End', 'underline');
  }, {at: '일련번호를 속성으로 두는 길에서는'});
  await ctx.say('wo0411', async () => {
   await c.emph({pen: 'q1'}, {shape: 'underline', phrase: '그 자리에 어떤 장치(일련번호)가 달렸나'});
   await atPhrase(ctx, '보전팀이 옛 펌프의 줄을'); await tab(c, ctx, 'components.csv'); await mark(c, ctx, 13, {cell: 6, shape: 'underline'});
   await atPhrase(ctx, '비고 칸에만'); await mark(c, ctx, 13, {sub: '2026-03-11', shape: 'underline'}); await mark(c, ctx, 14, {sub: '2026-03-11', shape: 'underline', keep: true, point: false});
  }, {at: '우리 질문이'});
  await say(ctx, 'wo0412');
  await ctx.say('wo0413', async () => {
   await paste(c, ctx, askOf('wo0413'));
   since = await send(c, ctx, '같이 맞춰 달라고 할게요');
  }, {at: '고른 것은 Codex한테'});
 }
 const waited = [];
 if (await waitSay(c, ctx, since, 'wo0495')) waited.push('wo0495');
 const r = await answer(c, ctx, since);
 const cut = await seamOut(c, ctx, G);
 await keepEnd(c, ctx, '04d');
 return {segment: 'wo-04d', page: 0, cut, ask: 'R9', aiRequests: since == null ? 0 : 1, answer: r.message, codexMs: r.ms, used: r.used, waitLines: waited, next: 'wo-04e: 고친 파일 열어 보기 · python run.py names'};
};
