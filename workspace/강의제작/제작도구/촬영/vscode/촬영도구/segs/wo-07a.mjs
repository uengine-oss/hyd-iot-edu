// 06-2 구간 07a(첫 페이지): 넣기 전 검증 — 길잡이 ④ → python run.py check(F5는 다음 구간 첫머리). Codex 부탁 없음.
// 시작: wo-06d 끝(graph.json이 열린 화면, 앞 take를 준다). 끝: 터미널에 check 결과 — 다음은 wo-07b(PAGE=1). 녹화 뒤 사본 SEG=07a.
import {atPhrase} from './lab-common.mjs';
import {ui, QE, guideIn, guideRing, seamOut, keepEnd, command} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 0);
 const G = await guideIn(c, ctx, 'vs', {items: QE, ring: 'm3'});
 await c.installPointer(ctx.prev ? null : {x: 900, y: 460});
 await ctx.begin();
 await ctx.say('wo0711', async () => {
  await guideRing(G, 'm4');
  await command(c, ctx, 'python run.py check', 'python run.py check입니다');
 }, {at: '그림의 넷째 칸'});
 const cut = await seamOut(c, ctx, G);
 await keepEnd(c, ctx, '07a');
 return {segment: 'wo-07a', page: 0, cut, aiRequests: 0, next: 'wo-07b: 결과 화면(PAGE=1) F5 — 넣기 전 검증'};
};
