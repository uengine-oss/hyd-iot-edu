// 06-2 구간 08b(첫 페이지): R15가 더한 expected.csv 줄(HYD-04 · RF-10 · 없는 품번) 열어 보기 → 길잡이 ⑤ · python run.py query. Codex 부탁 없음.
// 시작: wo-08a 끝(R15 답이 선 화면, 앞 take를 준다). 끝: 터미널에 query 결과 — 다음은 wo-08c(PAGE=1). 녹화 뒤 사본 SEG=08b. 큐 wo0881은 대본 wo0814를 나눈 앞쪽(판정 문서 「막힌 곳 ①」).
import {atPhrase} from './lab-common.mjs';
import {ui, QE, PICK, guideIn, guideRing, seamOut, keepEnd, open, mark, markAll, linesHas, lineOf, command} from './wo-common.mjs';

const F = 'app/features/expected.csv';
export default async ctx => {
 const c = await ui(ctx, 0);
 const h4 = await linesHas(ctx, F, x => x.startsWith(PICK.hyd04)), rf = await lineOf(ctx, F, PICK.rf10), no = await lineOf(ctx, F, PICK.noPart);
 if (!h4.length) throw Error('expected.csv에 HYD-04로 묻는 줄이 없음 — R15 답을 본다(PICK.hyd04)');
 const G = await guideIn(c, ctx, 'vs', {items: QE, ring: 'm5'});
 await c.installPointer(ctx.prev ? null : {x: 1500, y: 600});
 await ctx.begin();
 await ctx.say('wo0813', async () => {
  await open(c, ctx, F); await markAll(c, ctx, [...h4, rf, no]);
  await atPhrase(ctx, 'HYD-04로 묻는 줄이'); await markAll(c, ctx, h4, {shape: 'underline'});
  await atPhrase(ctx, 'RF-10 줄에는'); await mark(c, ctx, rf, {cell: 2, shape: 'underline'}); await mark(c, ctx, rf, {cell: 3, shape: 'underline', keep: true, point: false});
  await atPhrase(ctx, '없는 품번 줄의'); await mark(c, ctx, no, {cell: 3, shape: 'underline'}); await mark(c, ctx, no, {cell: 4, shape: 'underline', keep: true, point: false});
 }, {at: '더해진 줄을'});
 await ctx.say('wo0881', async () => {
  await guideRing(G, 'm5');
  await command(c, ctx, 'python run.py query', 'python run.py query예요');
 }, {at: '이제 맞춰 봅니다'});
 const cut = await seamOut(c, ctx, G);
 await keepEnd(c, ctx, '08b');
 return {segment: 'wo-08b', page: 0, cut, aiRequests: 0, next: 'wo-08c: 결과 화면(PAGE=1) F5 — 질문별 대조'};
};
