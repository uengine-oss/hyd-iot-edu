// 실전 3회차 08편 구간 02: data 펼침 → reviews · model · sop.json · conditions.csv · documents(자기 결과는 선택) → run.py db로 랩 DB를 처음 만들고 모델 · 조치 기준을 올린다. AI 요청 없음.
// 시작: p308-01 끝(README.md 탭, 폴더 접힘, 빈 Codex). output/ 없음, 터미널 없음, 이 폴더의 랩 DB 없음(.lab_connection.json 없음 — p308-reset.mjs).
// 0208을 말한 뒤 출력이 나올 때까지의 무출력 대기(이 PC 23초)는 합성 때 가운데만 줄인다(cut.py, 앞뒤 2초는 남긴다).
import {labUi, atPhrase, afterResult, termLine, termScrollTo, termWait, row, rowSeen, exists, newTerminal} from './lab-common.mjs';

const LAB = (await import('./lab-common.mjs')).LABS.p308.dir;   // 촬영 폴더는 lab-common.mjs LABS 한 곳에

export default async ctx => {
 const c = await labUi(ctx);
 if (await exists(ctx, LAB + '/output')) throw Error('output/이 이미 있음 — p308-reset.mjs로 지우고 시작');
 if (await exists(ctx, LAB + '/.lab_connection.json')) throw Error('이 폴더의 랩 DB가 이미 있음 — 「처음 만든 DB」 장면이 아니다');
 if (await c.serial(() => ctx.p.evaluate(() => !!document.querySelector('.terminal-wrapper')?.checkVisibility()))) throw Error('터미널이 이미 열려 있음');
 await c.installPointer(ctx.prev ? null : {x: 120, y: 200});
 await ctx.begin();
 await ctx.say('p308-0201', async () => {   // 탐색기 차례(위에서 아래): documents → model
  const d = await c.explorerRow('data', 1); await c.clickAt(d.x, d.y);
  await rowSeen(ctx, 'documents', 2);
  const m = await row(c, 'documents', 2); await c.move(m.x, m.y); await atPhrase(ctx, 'model 폴더는');
  const o = await row(c, 'model', 2); await c.move(o.x, o.y);
 }, {at: '데이터 폴더를 펼치면'});
 await ctx.say('p308-0202', async () => {   // reviews → conditions.csv → sop.json
  const r = await row(c, 'reviews', 2); await c.move(r.x, r.y); await atPhrase(ctx, '아래쪽 conditions.csv는');
  const a = await row(c, 'conditions.csv', 2); await c.move(a.x, a.y); await atPhrase(ctx, 'sop.json은');
  const b = await row(c, 'sop.json', 2); await c.move(b.x, b.y);
 }, {at: 'reviews 폴더에는'});
 await ctx.say('p308-0203', async () => { const q = await row(c, 'reviews', 2); await c.move(q.x, q.y); }, {at: '앞에서 만들어'});
 await ctx.say('p308-0204', async () => { const q = await row(c, 'run.py', 1); await c.move(q.x, q.y); }, {at: '이번에는 처음부터'});
 await ctx.say('p308-0205', () => newTerminal(c, ctx), {at: '왼쪽 위 줄 세 개 메뉴에서'});
 await termWait(ctx, 'work-card-lab>');
 await afterResult(ctx);
 await ctx.say('p308-0206', async () => { const q = await termLine(c, ctx, 'work-card-lab>'); await c.move(q.x, q.y); }, {at: '커서 앞의 경로가'});
 await ctx.say('p308-0207', async () => { await c.typeKeys('python run.py db'); }, {at: 'python run.py db를'});
 await ctx.say('p308-0208', async () => { await c.typeKeys(' --no-open'); await c.key('Enter'); }, {at: 'no-open을 붙여'});
 await ctx.say('p308-0209');   // 말만(기다리는 동안)
 await termWait(ctx, '전체 노드 253개', 180000);
 await termWait(ctx, '결과: output/result.html');
 await afterResult(ctx);
 await ctx.say('p308-0210', async () => {
  await termScrollTo(c, ctx, '랩 DB 준비 완료');   // 출력이 터미널 높이보다 길어 이 줄이 위로 밀려 있다
  const a = await termLine(c, ctx, '랩 DB 준비 완료'); await c.move(a.x, a.y); await atPhrase(ctx, '설비 모델과 조치 기준을');
  const b = await termLine(c, ctx, '설비 모델과 조치 기준 적재'); await c.move(b.x, b.y); await atPhrase(ctx, '전체 개수 줄이');
  const d = await termLine(c, ctx, '전체 노드 253개'); await c.move(d.x, d.y);
 }, {at: '터미널에'});
 await ctx.say('p308-0211', async () => { await termScrollTo(c, ctx, '결과: output/result.html', false); const q = await termLine(c, ctx, '결과: output/result.html'); await c.move(q.x, q.y); }, {at: '여러분 PC에서는'});
 if (!(await exists(ctx, LAB + '/.lab_connection.json'))) throw Error('랩 DB 연결 파일이 생기지 않음');
 return {segment: 'p308-02', next: 'p308-03: 결과 화면 공간', aiRequests: 0};
};
