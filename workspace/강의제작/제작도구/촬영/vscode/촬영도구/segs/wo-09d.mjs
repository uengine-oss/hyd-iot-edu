// 06-2 구간 09d(첫 페이지): expected.csv 질문 4 줄(기대 답 HYD-01 · HYD-02) → 설비 대장 2 · 3 · 6행(설치일 · 상태) → python run.py query(스키마를 고치기 전). Codex 부탁 없음.
// 시작: wo-09c 끝(R18 답이 선 화면 — 묻지 않았으면 wo-09b 끝, 앞 take를 준다). 끝: 터미널에 query 결과 — 다음은 wo-09e(PAGE=1). 녹화 뒤 사본 SEG=09d. 큐 wo0981은 대본 wo0914를 나눈 앞쪽(판정 문서 「막힌 곳 ①」).
import {atPhrase} from './lab-common.mjs';
import {ui, QE, PICK, guideIn, seamOut, keepEnd, open, mark, markAll, lineOf, command} from './wo-common.mjs';

export default async ctx => {
 const c = await ui(ctx, 0);
 const q4 = await lineOf(ctx, 'app/features/expected.csv', PICK.q4);
 const G = await guideIn(c, ctx, 'vs', {items: QE, ring: 'm5'});
 await c.installPointer(ctx.prev ? null : {x: 1500, y: 600});
 await ctx.begin();
 await ctx.say('wo0913', async () => {
  await open(c, ctx, 'app/features/expected.csv'); await mark(c, ctx, q4);
  await atPhrase(ctx, '기대 답은'); await mark(c, ctx, q4, {cell: 3, shape: 'underline', keep: true, point: false});
  await atPhrase(ctx, '설비 대장을 열어 보면'); await open(c, ctx, 'data/equipment.csv'); await markAll(c, ctx, [2, 3], {cell: 7, shape: 'underline'});
  await atPhrase(ctx, '2017년이죠'); await mark(c, ctx, 6, {cell: 7, shape: 'underline'});
  await atPhrase(ctx, '상태가 가동이 아니라'); await mark(c, ctx, 6, {cell: 8, shape: 'box'});
 }, {at: '질문 4로 한 줄이'});
 await ctx.say('wo0981', async () => { await command(c, ctx, 'python run.py query', 'query를 돌려'); }, {at: '이 상태로'});
 const cut = await seamOut(c, ctx, G);
 await keepEnd(c, ctx, '09d');
 return {segment: 'wo-09d', page: 0, cut, aiRequests: 0, next: 'wo-09e: 결과 화면(PAGE=1) F5 — 질문 4 다름'};
};
