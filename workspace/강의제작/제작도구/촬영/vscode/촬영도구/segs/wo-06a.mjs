// 06-2 구간 06a(첫 페이지): 세 번째 질문 — 교체부품 칸의 섞인 표기(11 · 12 · 21행) → 부품 식별자(classes.csv) · 품번 표(8 · 10행) → python run.py parts(Enter 뒤 말을 마저 한다). Codex 부탁 없음.
// 시작: 첫 페이지는 wo-05e 끝 화면(사이에 둘째 페이지 wo-05f) — 앞 take wo-05e. 끝: 터미널에 parts 결과 — 다음은 wo-06b(PAGE=1). 녹화 뒤 사본 SEG=06a(output/schema.json · graph.json이 생긴다).
import {atPhrase} from './lab-common.mjs';
import {ui, QE, guideIn, guideRing, seamOut, keepEnd, open, mark, markAll, lineOf, command} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 0);
 const G = await guideIn(c, ctx, 'vs', {items: QE, ring: 'm2'});
 await c.installPointer(ctx.prev ? null : {x: 900, y: 460});
 await ctx.begin();
 await ctx.say('wo0601', async () => {
  await guideRing(G, 'm2'); await c.emph({pen: 'q3'}, {shape: 'underline'});
  await atPhrase(ctx, '구성 요소 표의 교체부품 칸을'); await open(c, ctx, 'data/components.csv'); await markAll(c, ctx, [11, 12, 21], {cell: 3, shape: 'underline'});
 }, {at: '세 번째 질문이 남았습니다'});
 await ctx.say('wo0602', async () => {
  await open(c, ctx, 'app/features/classes.csv'); await mark(c, ctx, await lineOf(ctx, 'app/features/classes.csv', '부품,'), {cell: 2, shape: 'underline'});
  await atPhrase(ctx, '구매팀이 보낸 품번 표에'); await open(c, ctx, 'data/part_aliases.csv'); await mark(c, ctx, 8, {sub: 'P-FAN-BRG,FB-6205', shape: 'underline'}); await mark(c, ctx, 10, {sub: 'P-CLR-CORE,HI-CC-45A', shape: 'underline', keep: true, point: false});
  await command(c, ctx, 'python run.py parts', 'python run.py parts를', '돌릴게요');
 }, {at: '부품의 식별자는'});
 const cut = await seamOut(c, ctx, G);
 await keepEnd(c, ctx, '06a');
 return {segment: 'wo-06a', page: 0, cut, aiRequests: 0, next: 'wo-06b: 결과 화면(PAGE=1) F5 — 부품과 모델'};
};
