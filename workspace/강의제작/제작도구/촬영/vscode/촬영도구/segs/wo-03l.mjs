// 06-2 구간 03l(첫 페이지): 「표 세 장이 다 찼다」 — 탐색기의 classes · properties · relations에 테두리, 길잡이 ③. Codex 부탁 없음.
// 시작: 첫 페이지는 wo-03j 끝 화면(사이에 둘째 페이지 wo-03k). 끝: 같은 화면, 길잡이 ③에 동그라미. 큐 wo0340은 대본 wo0340을 나눈 뒤쪽(판정 문서 「막힌 곳 ①」).
import {atPhrase} from './lab-common.mjs';
import {ui, QE, guideIn, guideRing, seamOut, keepEnd, label} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 0);
 const G = await guideIn(c, ctx, 'vs', {items: [...QE, 'todo'], ring: 'm2'});
 await c.installPointer(ctx.prev ? null : {x: 900, y: 460});
 await ctx.begin();
 await ctx.say('wo0340', async () => {
  for (const [i, f] of ['classes.csv', 'properties.csv', 'relations.csv'].entries()) await c.emph(label(f), {shape: 'box', keep: i > 0, point: i === 0});
  await atPhrase(ctx, '그 표가 여기서는'); await guideRing(G, 'm3');
 }, {at: '이걸로 표 세 장이'});
 const cut = await seamOut(c, ctx, G);
 await keepEnd(c, ctx, '03l');
 return {segment: 'wo-03l', page: 0, cut, aiRequests: 0, next: 'wo-04a: 남은 일로 돌아가 python run.py classes'};
};
