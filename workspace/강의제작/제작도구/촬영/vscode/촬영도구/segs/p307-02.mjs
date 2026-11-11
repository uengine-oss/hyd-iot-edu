// 실전 3회차 07편 구간 02: data 펼침 → documents · 제공 조치 검토 자료 → documents 펼침(매뉴얼 세 판 · 제조사 지침 · 스캔본 · 문서 목록) → run.py → 새 터미널 → 첫 실행. AI 요청 없음.
// 시작: p307-01 끝(README.md 탭, 폴더 접힘, 빈 Codex). output/ 없음, 터미널 없음. .env는 만들지 않는다.
import {labUi, atPhrase, afterResult, termLine, termWait, row, rowSeen, exists, newTerminal, waitRun} from './lab-common.mjs';

const LAB = (await import('./lab-common.mjs')).LABS.p307.dir;   // 촬영 폴더는 lab-common.mjs LABS 한 곳에

export default async ctx => {
 const c = await labUi(ctx);
 if (await exists(ctx, LAB + '/output')) throw Error('output/이 이미 있음 — p307-reset.mjs로 지우고 시작');
 if (await exists(ctx, LAB + '/.env')) throw Error('.env가 있음 — 이 구간은 키 없는 폴더에서 찍는다');
 if (await c.serial(() => ctx.p.evaluate(() => !!document.querySelector('.terminal-wrapper')?.checkVisibility()))) throw Error('터미널이 이미 열려 있음');
 await c.installPointer(ctx.prev ? null : {x: 120, y: 200});
 await ctx.begin();
 await ctx.say('p307-0201', async () => {
  const d = await c.explorerRow('data', 1); await c.clickAt(d.x, d.y);
  await rowSeen(ctx, 'documents', 2);
  const m = await row(c, 'documents', 2); await c.move(m.x, m.y);
  for (const [name, at] of [['action_review.json', '조치 검토 결과'], ['conditions.csv', '조건표,'], ['sop.json', 'SOP 구조 파일']]) { await atPhrase(ctx, at); const q = await row(c, name, 2); await c.move(q.x, q.y); }
 }, {at: '데이터 폴더를'});
 await ctx.say('p307-0202', async () => {
  const d = await c.explorerRow('documents', 2); await c.clickAt(d.x, d.y);
  await rowSeen(ctx, 'hm_8_manual.md', 3);
  for (const [name, at] of [['hm_8_manual.md', '쿨러 팬 정비 매뉴얼은'], ['hm_8_rev_1_0_manual.md', '옛 1.0판'], ['hm_8_rev_1_2_change_request.md', '1.2판 개정 요청']]) { await atPhrase(ctx, at); const q = await row(c, name, 3); await c.move(q.x, q.y); }
 }, {at: 'documents 폴더를'});
 await ctx.say('p307-0203', async () => {
  const a = await row(c, 'oem_hpp45a_maintenance_guide_en_ko.md', 3); await c.move(a.x, a.y); await atPhrase(ctx, '종이로만');
  const b = await row(c, 'hm_9_chapter_scan.txt', 3); await c.move(b.x, b.y);
 }, {at: '제조사가 낸'});
 await ctx.say('p307-0204', async () => { const q = await row(c, 'catalog.csv', 3); await c.move(q.x, q.y); }, {at: '맨 위의 catalog'});
 await ctx.say('p307-0205', async () => { const q = await row(c, 'run.py', 1); await c.move(q.x, q.y); }, {at: '맨 아래 run.py'});
 await ctx.say('p307-0206', () => newTerminal(c, ctx), {at: '왼쪽 위 줄 세 개 메뉴에서'});
 await termWait(ctx, 'condition-extract-lab>');
 await afterResult(ctx);
 await ctx.say('p307-0207', async () => { const q = await termLine(c, ctx, 'condition-extract-lab>'); await c.move(q.x, q.y); }, {at: '글자 앞 경로가'});
 await ctx.say('p307-0208', async () => { await c.typeKeys('python run.py'); }, {at: 'python run.py를'});
 await ctx.say('p307-0209', async () => { await c.typeKeys(' --no-open'); await c.key('Enter'); }, {at: 'no-open을 붙여'});
 await waitRun(ctx, LAB);
 await ctx.say('p307-0210', async () => {
  await atPhrase(ctx, '이번 경보의'); const a = await termLine(c, ctx, '의 조치 후보:'); await c.move(a.x, a.y); await atPhrase(ctx, '문서 묶음은');
  const b = await termLine(c, ctx, '문서 묶음 —'); await c.move(b.x, b.y); await atPhrase(ctx, '끝에서 둘째');
  const d = await termLine(c, ctx, '이 작업에 걸린 조건:'); await c.move(d.x, d.y);
 }, {at: '터미널에'});
 await ctx.say('p307-0211', async () => { const q = await termLine(c, ctx, '결과: output/result.html'); await c.move(q.x, q.y); }, {at: '여러분 PC에서는'});
 return {segment: 'p307-02', next: 'p307-03: 결과 화면 공간', aiRequests: 0};
};
