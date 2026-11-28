// 06-2 구간 03j(첫 페이지): 관계 표를 적었다는 R7 답을 받아 python run.py relations. Codex 부탁 없음.
// 시작: wo-03i 끝(R7 답이 선 화면, 앞 take를 준다). 끝: 터미널에 결과 줄 — 다음은 wo-03k(PAGE=1). 녹화 뒤 사본 SEG=03j. 큐 wo0384는 대본 wo0333을 나눈 앞쪽(판정 문서 「막힌 곳 ①」).
import {ui, QE, guideIn, seamOut, keepEnd, dataRows, command} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 0);
 const d = await dataRows('app/features/relations.csv');
 if (d.last < d.first) throw Error('relations.csv에 데이터 줄이 없음 — R7 답(Codex가 적었는지 · 되물었는지)을 본다');
 const G = await guideIn(c, ctx, 'vs', {items: [...QE, 'todo'], ring: 'm2'});
 await c.installPointer(ctx.prev ? null : {x: 1500, y: 600});
 await ctx.begin();
 await ctx.say('wo0384', async () => { await command(c, ctx, 'python run.py relations', 'python run.py relations입니다'); }, {at: '바로 돌려 볼게요'});
 const cut = await seamOut(c, ctx, G);
 await keepEnd(c, ctx, '03j');
 return {segment: 'wo-03j', page: 0, cut, aiRequests: 0, next: 'wo-03k: 결과 화면(PAGE=1) F5 — 관계와 카디널리티'};
};
