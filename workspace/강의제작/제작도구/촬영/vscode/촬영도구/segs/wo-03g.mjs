// 06-2 구간 03g(첫 페이지): 속성 표를 적었다는 R6 답을 받아 python run.py properties를 돌리며 그 명령이 무엇을 보는지 말한다. Codex 부탁 없음.
// 시작: wo-03f 끝(R6 답이 선 화면, 앞 take를 준다). 끝: 터미널에 결과 줄 — 다음은 wo-03h(PAGE=1). 녹화 뒤 사본 SEG=03g. 큐 wo0383은 대본 wo0331을 나눈 앞쪽(판정 문서 「막힌 곳 ①」).
import {ui, QE, guideIn, seamOut, keepEnd, dataRows, command} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 0);
 const d = await dataRows('app/features/properties.csv');
 if (d.last < d.first) throw Error('properties.csv에 데이터 줄이 없음 — R6 답(Codex가 적었는지 · 되물었는지)을 본다');
 const G = await guideIn(c, ctx, 'vs', {items: [...QE, 'todo'], ring: 'm2'});
 await c.installPointer(ctx.prev ? null : {x: 1500, y: 600});
 await ctx.begin();
 await ctx.say('wo0383', async () => { await command(c, ctx, 'python run.py properties', 'python run.py properties로', '확인해 봅니다'); }, {at: '속성 표도 다 적었다니'});
 const cut = await seamOut(c, ctx, G);
 await keepEnd(c, ctx, '03g');
 return {segment: 'wo-03g', page: 0, cut, aiRequests: 0, next: 'wo-03h: 결과 화면(PAGE=1) F5 — 속성과 자료형'};
};
