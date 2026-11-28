// 06-2 구간 04a(첫 페이지): 「아까 표시해 둔 그 한 곳으로」 — 길잡이의 남은 일에 테두리 → python run.py classes(말 뒤에 친다). Codex 부탁 없음.
// 시작: wo-03l 끝 화면. 끝: 터미널에 결과 줄 — 다음은 wo-04b(PAGE=1). 큐 wo0484는 대본 wo0421을 나눈 앞쪽(판정 문서 「막힌 곳 ①」).
import {ui, QE, guideIn, seamOut, keepEnd, speechEnd, typeCmd, cmdDone} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 0);
 const G = await guideIn(c, ctx, 'vs', {items: [...QE, 'todo'], ring: 'm3'});
 await c.installPointer(ctx.prev ? null : {x: 900, y: 460});
 await ctx.begin();
 await ctx.say('wo0484', async () => {
  await c.emph({pen: 'todo'}, {shape: 'box'});
  await speechEnd(ctx); await typeCmd(c, ctx, 'python run.py classes');   // 「classes를 다시 돌려 보면」은 다음 구간 첫 말 — 말이 끝난 뒤에 친다
  const t = Date.now(); await c.key('Enter'); await cmdDone(ctx, t);
 }, {at: '아까 표시해 둔'});
 const cut = await seamOut(c, ctx, G);
 await keepEnd(c, ctx, '04a');
 return {segment: 'wo-04a', page: 0, cut, aiRequests: 0, next: 'wo-04b: 결과 화면(PAGE=1) F5 — 겹친 곳'};
};
