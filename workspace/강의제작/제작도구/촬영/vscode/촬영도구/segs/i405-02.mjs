// 통합 4회차 05편 구간 02: data 펼침 → reviews · model · sop.json · conditions.csv · documents(자기 결과는 선택) → run.py → 새 터미널 → 첫 실행. AI 요청 없음.
// 시작: i405-01 끝(README.md 탭, 폴더 접힘, 빈 Codex). output/ 없음, 터미널 없음. 랩 DB는 이 범위에서 만들지 않는다(가이드 4단계).
import {labUi, atPhrase, afterResult, termLine, termWait, row, rowSeen, exists, newTerminal, waitRun} from './lab-common.mjs';

const LAB = (await import('./lab-common.mjs')).LABS.i405.dir;   // 촬영 폴더는 lab-common.mjs LABS 한 곳에

export default async ctx => {
 const c = await labUi(ctx);
 if (await exists(ctx, LAB + '/output')) throw Error('output/이 이미 있음 — i405-reset.mjs로 지우고 시작');
 if (await c.serial(() => ctx.p.evaluate(() => !!document.querySelector('.terminal-wrapper')?.checkVisibility()))) throw Error('터미널이 이미 열려 있음');
 await c.installPointer(ctx.prev ? null : {x: 120, y: 200});
 await ctx.begin();
 await ctx.say('i405-0201', async () => {
  const d = await c.explorerRow('data', 1); await c.clickAt(d.x, d.y);
  await rowSeen(ctx, 'reviews', 2);
  const m = await row(c, 'reviews', 2); await c.move(m.x, m.y);
 }, {at: 'reviews 폴더는'});
 await ctx.say('i405-0202', async () => {   // 탐색기 차례(위에서 아래): model → conditions.csv → sop.json
  const a = await row(c, 'model', 2); await c.move(a.x, a.y); await atPhrase(ctx, 'conditions.csv의');
  const b = await row(c, 'conditions.csv', 2); await c.move(b.x, b.y); await atPhrase(ctx, 'sop.json의');
  const d = await row(c, 'sop.json', 2); await c.move(d.x, d.y);
 }, {at: 'model 폴더의'});
 await ctx.say('i405-0203', async () => { const q = await row(c, 'documents', 2); await c.move(q.x, q.y); }, {at: 'documents 폴더에는'});
 await ctx.say('i405-0204', async () => { const q = await row(c, 'reviews', 2); await c.move(q.x, q.y); }, {at: '직접 만든'});
 await ctx.say('i405-0205', async () => { const q = await row(c, 'run.py', 1); await c.move(q.x, q.y); }, {at: '맨 아래 run.py'});
 await ctx.say('i405-0206', () => newTerminal(c, ctx), {at: '왼쪽 위 줄 세 개 메뉴에서'});
 await termWait(ctx, 'knowledge-graph-lab>');
 await afterResult(ctx);
 await ctx.say('i405-0207', async () => { const q = await termLine(c, ctx, 'knowledge-graph-lab>'); await c.move(q.x, q.y); }, {at: '글자 앞 경로가'});
 await ctx.say('i405-0208', async () => { await c.typeKeys('python run.py'); }, {at: 'python run.py를'});
 await ctx.say('i405-0209', async () => { await c.typeKeys(' --no-open'); await c.key('Enter'); }, {at: 'no-open을 붙여'});
 await waitRun(ctx, LAB);
 await ctx.say('i405-0210', async () => {
  const a = await termLine(c, ctx, '검토 결과 —'); await c.move(a.x, a.y); await atPhrase(ctx, '종류마다의');
  const b = await termLine(c, ctx, '기존 ID(설비 모델'); await c.move(b.x, b.y); await atPhrase(ctx, '그래프에 넣을');
  const d = await termLine(c, ctx, '승인 후보 찾아보기'); await c.move(d.x, d.y);
 }, {at: '터미널에'});
 await ctx.say('i405-0211', async () => { const q = await termLine(c, ctx, '결과: output/result.html'); await c.move(q.x, q.y); }, {at: '여러분 PC에서는'});
 return {segment: 'i405-02', next: 'i405-03: 결과 화면 공간', aiRequests: 0};
};
