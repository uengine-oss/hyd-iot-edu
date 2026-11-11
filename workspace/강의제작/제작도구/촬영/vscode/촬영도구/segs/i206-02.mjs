// 통합 2회차 06편 구간 02: 원자료 폴더 → 설비 대장 → run.py → 새 터미널 → python run.py 첫 실행. AI 요청 없음.
// 시작: i206-01 끝(README.md 탭, data · app 접힘, 빈 Codex 새 대화). output/ 없음, 터미널 없음.
// 웹판은 결과 화면을 저절로 열지 않도록 --no-open을 덧붙인다 — 결과 화면은 i206-03(결과 화면 공간)에서 본다.
import {labUi, atPhrase, afterResult, termLine, termWait, lineAt, row, rowSeen, exists, newTerminal, waitRun} from './lab-common.mjs';

const LAB = (await import('./lab-common.mjs')).LABS.i206.dir;   // 촬영 폴더는 lab-common.mjs LABS 한 곳에

export default async ctx => {
 const c = await labUi(ctx);
 if (await exists(ctx, LAB + '/output')) throw Error('output/이 이미 있음 — i206-reset.mjs로 지우고 시작');
 if (await c.serial(() => ctx.p.evaluate(() => !!document.querySelector('.terminal-wrapper')?.checkVisibility()))) throw Error('터미널이 이미 열려 있음');
 await c.installPointer(ctx.prev ? null : {x: 120, y: 160});
 await ctx.begin();
 await ctx.say('i206-0201', async () => {
  const d = await c.explorerRow('data', 1); await c.clickAt(d.x, d.y);
  await rowSeen(ctx, 'equipment.csv', 2);
  const files = [['equipment.csv', '설비 대장'], ['components.csv', '구성 요소'], ['sensors.csv', '센서 목록'], ['spare_parts.csv', '예비품 목록']];
  for (const [name, phrase] of files) { await atPhrase(ctx, phrase); const q = await row(c, name, 2); await c.move(q.x, q.y); }
 }, {at: '데이터 폴더를'});
 await ctx.say('i206-0202', async () => { const q = await row(c, 'field_notes.md', 2); await c.move(q.x, q.y); }, {at: '현장 메모'});
 await ctx.say('i206-0203', async () => { const q = await c.explorerRow('equipment.csv', 2); await c.clickAt(q.x, q.y); await c.key('Enter'); }, {at: '설비 대장부터'});
 await ctx.waitFor(() => document.querySelector('.tabs-container .tab.active .label-name')?.textContent === 'equipment.csv');
 await afterResult(ctx);
 await ctx.say('i206-0204', async () => {
  const h = await lineAt(c, ctx, '설비코드,'); await c.move(h.x, h.y); await atPhrase(ctx, '그 아래로');
  const q = await lineAt(c, ctx, 'HYD-01,'); await c.move(q.x, q.y);
 }, {at: '맨 윗줄은'});
 await ctx.say('i206-0205', async () => { const q = await lineAt(c, ctx, 'HPU-L2-01,'); await c.move(q.x, q.y); }, {at: '바로 아래 줄은'});
 await ctx.say('i206-0206', async () => { const q = await row(c, 'run.py', 1); await c.move(q.x, q.y); }, {at: '맨 아래 run.py', gap: 2300});   // 원자료에서 실행으로 화제가 바뀌는 큐(영상 V-14 구간 전환 쉼, 2회차부터 2.3초)
 await ctx.say('i206-0207', async () => { const q = await c.point('.menubar-menu-button', 'Application Menu'); await c.move(q.x, q.y); }, {at: '창이에요'});
 await ctx.say('i206-0208', () => newTerminal(c, ctx), {at: '줄 세 개 메뉴를'});
 await termWait(ctx, 'ontology-lab>');
 await afterResult(ctx);
 await ctx.say('i206-0209', async () => {
  const q = await c.serial(() => ctx.p.evaluate(() => { const e = [...document.querySelectorAll('.terminal-tabs-entry, .single-terminal-tab, .terminal-tab')].filter(x => x.innerText.trim() === 'cmd' && x.getBoundingClientRect().width > 0); if (e.length !== 1) throw Error('터미널 이름표 cmd가 ' + e.length + '개'); const b = e[0].getBoundingClientRect(); return {x: b.x + b.width / 2, y: b.y + b.height / 2}; }));
  await c.move(q.x, q.y);
 }, {at: 'cmd라고'});
 await ctx.say('i206-0210', async () => { const q = await termLine(c, ctx, 'ontology-lab>'); await c.move(q.x, q.y); }, {at: '글자 앞 경로가'});
 // 학생 명령 · 웹판 덧붙임 · Enter는 말하는 문장마다 큐를 나눈다. 터미널 초점 확인은 공용 lab-common이 맡는다.
 await ctx.say('i206-0211', () => c.typeKeys('python run.py'), {at: 'python run.py를'});
 await ctx.say('i206-0212', () => c.typeKeys(' --no-open'), {at: '빼기 두 개와 no-open을'});
 await ctx.say('i206-0213', () => c.key('Enter'), {at: 'Enter를'});
 await waitRun(ctx, LAB);
 await rowSeen(ctx, 'output', 1);
 await ctx.say('i206-0214', async () => { const q = await termLine(c, ctx, '원자료 파일과 행 수'); await c.move(q.x, q.y); }, {at: '터미널에'});
 await ctx.say('i206-0215', async () => { const q = await row(c, 'output', 1); await c.move(q.x, q.y); }, {at: '탐색기에도'});
 return {segment: 'i206-02', next: 'i206-03: 결과 화면 공간에서 output/result.html', aiRequests: 0};
};
