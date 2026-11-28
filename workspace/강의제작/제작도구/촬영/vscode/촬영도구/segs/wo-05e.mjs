// 06-2 구간 05e(첫 페이지): Codex가 채운 quantity_rules.py(전체 흐린 띠) · 내 답과 코드 줄을 짝지은 답 대목 · 그 세 줄 → python run.py quantities. Codex 부탁 없음.
// 시작: wo-05d 끝(R13 답이 선 화면, 앞 take를 준다). 끝: 터미널에 결과 줄 — 다음은 wo-05f(PAGE=1). 녹화 뒤 사본 SEG=05e. 큐 wo0582는 대본 wo0515를 나눈 앞쪽(판정 문서 「막힌 곳 ①」).
// 코드 세 줄의 번호는 Codex가 짚어 준 줄(PICK.codeLines) — R13 답을 보고 채운다. 규칙이 아니라 목록으로 채웠으면(대본 wo0514) 한 번 더 부탁하는 큐를 정한다.
import {atPhrase} from './lab-common.mjs';
import {ui, LAB, QE, PICK, guideIn, seamOut, keepEnd, open, mark, cxMark, ln, reveal, visibleLines, command} from './wo-common.mjs';

const F = 'app/features/quantity_rules.py';
export default async ctx => {
 const c = await ui(ctx, 0);
 if ((await ctx.fs.readFile(LAB + '/' + F, 'utf8')).includes('raise NotImplementedError')) throw Error('quantity_rules.py가 아직 비어 있음 — R13 답을 본다');
 if (PICK.codeLines.some(n => !Number.isInteger(n))) throw Error('wo0514: PICK.codeLines(내 답 ①②③이 들어간 코드 줄 번호)가 비었음 — R13 답에서 Codex가 짚어 준 줄로 채운다 (segs/wo-common.mjs PICK)');
 const G = await guideIn(c, ctx, 'vs', {items: QE, ring: 'm2'});
 await c.installPointer(ctx.prev ? null : {x: 1500, y: 600});
 await ctx.begin();
 await ctx.say('wo0514', async () => {
  await open(c, ctx, F); await reveal(c, ctx, 1); const [a, b] = await visibleLines(c, ctx); await c.emph(await ln(c, ctx, a, {to: b}), {shape: 'band'});
  await atPhrase(ctx, '볼 곳은 Codex가 짚어 준'); await cxMark(c, ctx, 'r13Map', 'band');
  for (const [i, p] of ['태그가 같으면 같은 곳으로', '붙은 곳을 따른다는', '냉각수는 따로 둔다는'].entries()) { await atPhrase(ctx, p); await mark(c, ctx, PICK.codeLines[i]); }
 }, {at: '코드가 채워졌습니다'});
 await ctx.say('wo0582', async () => { await command(c, ctx, 'python run.py quantities', 'python run.py quantities로'); }, {at: '규칙이 제대로 가르는지는'});
 const cut = await seamOut(c, ctx, G);
 await keepEnd(c, ctx, '05e');
 return {segment: 'wo-05e', page: 0, cut, aiRequests: 0, next: 'wo-05f: 결과 화면(PAGE=1) F5 — 물리량과 센서'};
};
