// 06-2 구간 03c(첫 페이지): Codex가 적은 classes.csv 열어 보기(의미 · 식별자 틀 · 근거) → python run.py classes. Codex 부탁 없음.
// 시작: wo-03b 끝(R4 답이 선 화면, 앞 take를 준다). 끝: 터미널에 결과 줄 — 다음은 wo-03d(PAGE=1, F5). 녹화 뒤 사본 SEG=03c. 큐 wo0382는 대본 wo0327을 나눈 앞쪽(판정 문서 「막힌 곳 ①」).
import {atPhrase} from './lab-common.mjs';
import {ui, QE, PICK, guideIn, seamOut, keepEnd, open, mark, lineOf, dataRows, ln, visibleLines, command} from './wo-common.mjs';

const F = 'app/features/classes.csv';
export default async ctx => {
 const c = await ui(ctx, 0);
 const d = await dataRows(F);
 if (d.last < d.first) throw Error('classes.csv에 데이터 줄이 없음 — R4 답(Codex가 적었는지 · 되물었는지)을 본다');
 const G = await guideIn(c, ctx, 'vs', {items: QE, ring: 'm2'});
 await c.installPointer(ctx.prev ? null : {x: 1500, y: 600});
 await ctx.begin();
 await ctx.say('wo0326', async () => {
  await open(c, ctx, F); const [, last] = await visibleLines(c, ctx);
  await c.emph(await ln(c, ctx, d.first, {to: Math.min(d.last, last)}), {shape: 'band'});
  await atPhrase(ctx, '의미 한 문장과'); await mark(c, ctx, d.head, {cell: 1, shape: 'underline'});
  await atPhrase(ctx, '센서는 설비 코드 뒤에 태그'); await mark(c, ctx, await lineOf(ctx, F, '센서,'), {sub: PICK.idSensor, shape: 'underline'});
  await atPhrase(ctx, '구성 요소는 설비 코드 뒤에 이름'); await mark(c, ctx, await lineOf(ctx, F, '구성 요소,'), {sub: PICK.idComp, shape: 'underline'});
  await atPhrase(ctx, '부품은 품번 하나로요'); await mark(c, ctx, await lineOf(ctx, F, '부품,'), {sub: PICK.idPart, shape: 'underline'});
  await atPhrase(ctx, '근거 칸에 이유도'); await mark(c, ctx, d.head, {cell: 3, shape: 'underline'});
 }, {at: '클래스 표가 찼습니다'});
 await ctx.say('wo0382', async () => { await command(c, ctx, 'python run.py classes', 'python run.py classes입니다'); }, {at: '숫자가 맞는지는'});
 const cut = await seamOut(c, ctx, G);
 await keepEnd(c, ctx, '03c');
 return {segment: 'wo-03c', page: 0, cut, aiRequests: 0, next: 'wo-03d: 결과 화면(PAGE=1) F5 — 클래스와 식별자'};
};
