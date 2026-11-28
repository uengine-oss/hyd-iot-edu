// 06-2 구간 02c(첫 페이지): Codex가 적은 expected.csv를 열어 보고(추가된 줄 · 오일 쿨러 줄) 터미널에서 python run.py expected를 돌린다. Codex 부탁 없음.
// 시작: wo-02b 끝(R2 답이 선 화면, 앞 take를 준다). 끝: 터미널에 결과 줄이 뜬 화면(다음은 둘째 페이지 wo-02d — F5부터). 녹화 뒤 사본 SEG=02c.
// 큐 wo0282는 대본 wo0209를 나눈 앞쪽이다(판정 문서 「막힌 곳 ①」 — 나눔을 대본에 넣기 전에는 이 구간이 큐 JSON에 없는 큐로 멈춘다).
import {atPhrase} from './lab-common.mjs';
import {ui, QE, guideIn, seamOut, keepEnd, open, mark, lineOf, dataRows, visibleLines, ln, command} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 0);
 const d = await dataRows('app/features/expected.csv');
 if (d.last < d.first) throw Error('expected.csv에 데이터 줄이 없음 — R2 답(Codex가 적었는지)을 본다');
 const G = await guideIn(c, ctx, 'vs', {items: QE, ring: 'm1'});
 await c.installPointer(ctx.prev ? null : {x: 1500, y: 600});
 await ctx.begin();
 await ctx.say('wo0208', async () => {
  await open(c, ctx, 'app/features/expected.csv');
  const [, last] = await visibleLines(c, ctx);
  await c.emph(await ln(c, ctx, d.first, {to: Math.min(d.last, last)}), {shape: 'band'});
  await atPhrase(ctx, '오일 쿨러 줄이'); await mark(c, ctx, await lineOf(ctx, 'app/features/expected.csv', '1,HYD-01,오일 쿨러'), {shape: 'underline'});
 }, {at: '파일을 열어 봐야죠'});
 await ctx.say('wo0282', async () => { await command(c, ctx, 'python run.py expected', 'python run.py expected를', '돌리고'); }, {at: '나머지 줄의 근거도'});
 const cut = await seamOut(c, ctx, G);
 await keepEnd(c, ctx, '02c');
 return {segment: 'wo-02c', page: 0, cut, aiRequests: 0, next: 'wo-02d: 결과 화면(PAGE=1) F5 — 기대 답'};
};
