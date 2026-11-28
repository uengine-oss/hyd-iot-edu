// 06-2 구간 05c(첫 페이지): R11이 고친 decisions(둘째 줄) · expected(질문 2 줄 — 탱크 유온에 HYD-07:TI-1) 열어 보기 → quantity_rules.py(함수 머리 둘) → R12(읽기 — 갈리는 센서를 먼저 물어보게)를 보내고 답이 끝날 때까지.
// 시작: wo-05b 끝(R11 답이 선 화면, 앞 take를 준다). 끝: R12 답(Codex가 물어 온 센서 셋)이 선 화면.
import {atPhrase} from './lab-common.mjs';
import {ui, RESUME, QE, guideIn, seamOut, keepEnd, open, mark, lineOf, lineHas, linesHas, ln, paste, send, answer, waitSay, askOf} from './wo-common.mjs';

const A = 'app/features/';
export default async ctx => {
 const c = await ui(ctx, 0);
 const q2 = await linesHas(ctx, A + 'expected.csv', x => x.startsWith('2,'));
 if (RESUME == null && !q2.length) throw Error('expected.csv에 질문 2 줄이 없음 — R11 답을 본다');
 const G = await guideIn(c, ctx, 'vs', {items: QE, ring: 'm2'});
 await c.installPointer(ctx.prev ? null : {x: 1500, y: 600});
 await ctx.begin();
 let since = RESUME;
 if (since == null) {
  await ctx.say('wo0581', async () => {
   await open(c, ctx, A + 'decisions.csv'); await mark(c, ctx, await lineHas(ctx, A + 'decisions.csv', '같은 물리량의 범위'));
   await atPhrase(ctx, '기대 답에도'); await open(c, ctx, A + 'expected.csv'); await mark(c, ctx, q2[0], {to: q2.at(-1)});
   await atPhrase(ctx, '탱크 유온 묶음에'); await mark(c, ctx, await lineHas(ctx, A + 'expected.csv', '2,', '탱크 유온', 'HYD-07:TI-1'), {sub: 'HYD-07:TI-1', shape: 'underline'});
  }, {at: '결정 표에 둘째 줄이'});
  await ctx.say('wo0510', async () => {
   await open(c, ctx, A + 'quantity_rules.py');
   await atPhrase(ctx, '읽으실 필요는'); await mark(c, ctx, await lineOf(ctx, A + 'quantity_rules.py', 'def same_quantity')); await mark(c, ctx, await lineOf(ctx, A + 'quantity_rules.py', 'def quantity_name'), {keep: true, point: false});
   await atPhrase(ctx, '그래서 코드를 쓰기 전에'); await paste(c, ctx, askOf('wo0510'));
   since = await send(c, ctx, '먼저 물어보라고 할게요');
  }, {at: 'quantity_rules가 그 규칙을'});
 }
 const waited = [];
 if (await waitSay(c, ctx, since, 'wo0597')) waited.push('wo0597');
 const r = await answer(c, ctx, since);
 const cut = await seamOut(c, ctx, G);
 await keepEnd(c, ctx, '05c');
 return {segment: 'wo-05c', page: 0, cut, ask: 'R12', aiRequests: since == null ? 0 : 1, answer: r.message, codexMs: r.ms, used: r.used, waitLines: waited, next: 'wo-05d: 물어 온 센서에 답하기 · R13(규칙 코드)'};
};
