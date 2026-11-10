// 통합 2회차 06편 구간 02: 원자료 폴더 → 설비 대장 → run.py → 새 터미널 → python run.py 첫 실행. AI 요청 없음.
// 시작: i206-01 끝 상태(README.md 탭, data · app 접힘, 빈 Codex 새 대화). 실습 폴더에 output/이 없어야 한다(첫 실행 장면).
// 웹판은 결과 화면을 저절로 열지 않도록 --no-open을 덧붙인다 — 결과 화면은 i206-03(결과 화면 공간)에서 본다.
// 터미널 줄을 짚으려면 촬영용 웹 VS Code의 terminal.integrated.gpuAcceleration이 off여야 한다(DOM으로 그려야 .xterm-rows가 있다).
import {vscode} from '../ui.mjs';

const LAB = 'D:/HYD-Practice/i206p-27c52108/ontology-lab';

export default async ctx => {
 const c = await vscode(ctx);
 const start = await c.serial(() => ctx.p.evaluate(() => ({
  w: innerWidth, h: innerHeight, dpr: devicePixelRatio,
  root: document.querySelector('.pane-header[aria-label^="Explorer Section:"]')?.innerText,
  title: document.querySelector('.tabs-container .tab.active .label-name')?.textContent,
  rows: [...document.querySelectorAll('.explorer-folders-view .monaco-list-row')].map(e => e.innerText.trim()),
  terminal: !!document.querySelector('.terminal-wrapper')?.checkVisibility(),
 })));
 if (start.root?.toLowerCase() !== 'ontology-lab' || start.title !== 'README.md' || start.w !== 1843 || Math.abs(start.dpr - 1.25) > 0.01) throw Error('시작 화면 불일치: ' + JSON.stringify(start));
 if (start.rows.includes('output') || start.terminal) throw Error('첫 실행 전 상태가 아님(output/ 또는 열린 터미널): ' + JSON.stringify(start));
 if (await ctx.fs.stat(LAB + '/output').then(() => true, () => false)) throw Error('실습 폴더에 output/이 이미 있음 — i206-reset.mjs로 지우고 시작');
 const lineAt = text => c.serial(() => ctx.p.evaluate(text => {
  const l = [...document.querySelectorAll('.editor-instance .view-lines .view-line')].find(e => e.textContent.replace(/\u00a0/g, ' ').startsWith(text));
  if (!l) throw Error('줄 없음: ' + text);
  const b = l.getBoundingClientRect(); return {x: b.x + 60, y: b.y + b.height / 2};
 }, text));
 // 터미널에서 글이 text를 담은 마지막 줄의 앞쪽
 const termLine = text => c.serial(() => ctx.p.evaluate(text => {
  const rows = document.querySelector('.terminal-wrapper .xterm-rows');
  if (!rows) throw Error('터미널 줄을 DOM에서 읽을 수 없음 — terminal.integrated.gpuAcceleration을 off로');
  const l = [...rows.children].filter(d => d.textContent.includes(text)).pop();
  if (!l) throw Error('터미널 줄 없음: ' + text);
  const b = l.getBoundingClientRect(); return {x: b.x + 120, y: b.y + b.height / 2};
 }, text));
 await c.installPointer(ctx.prev ? null : {x: 120, y: 160});
 await ctx.begin();
 await ctx.say('i206-0201', async () => {
  const d = await c.explorerRow('data', 1); await c.clickAt(d.x, d.y);
  await ctx.waitFor(() => [...document.querySelectorAll('.explorer-folders-view .monaco-list-row')].some(e => e.getAttribute('aria-level') === '2' && e.innerText.trim() === 'equipment.csv'));
  for (const name of ['equipment.csv', 'components.csv', 'sensors.csv', 'spare_parts.csv']) { const q = await c.explorerRow(name, 2); await c.move(q.x - 34, q.y); await ctx.sleep(900); }
 }, {at: '데이터 폴더를'});
 await ctx.say('i206-0202', async () => { const q = await c.explorerRow('field_notes.md', 2); await c.move(q.x - 34, q.y); }, {at: '현장 메모'});
 await ctx.say('i206-0203', async () => { const q = await c.explorerRow('equipment.csv', 2); await c.clickAt(q.x, q.y); await c.key('Enter'); }, {at: '설비 대장부터'});
 await ctx.waitFor(() => document.querySelector('.tabs-container .tab.active .label-name')?.textContent === 'equipment.csv');
 await ctx.say('i206-0204', async () => {
  const h = await lineAt('설비코드,'); await c.move(h.x, h.y); await ctx.sleep(2200);
  const q = await lineAt('HYD-01,'); await c.move(q.x, q.y);
 }, {at: '맨 윗줄은'});
 await ctx.say('i206-0205', async () => { const q = await lineAt('HPU-L2-01,'); await c.move(q.x, q.y); }, {at: '바로 아래 줄은'});
 await ctx.say('i206-0206', async () => { const q = await c.explorerRow('run.py', 1); await c.move(q.x - 34, q.y); }, {at: '맨 아래 run.py'});
 await ctx.say('i206-0207', async () => { const q = await c.point('.menubar-menu-button', 'Application Menu'); await c.move(q.x, q.y); }, {at: '창이에요'});
 await ctx.say('i206-0208', async () => {
  await c.clickSel('.menubar-menu-button', 'Application Menu'); await ctx.sleep(500);
  await c.menuItem('Terminal'); await ctx.sleep(500);
  await c.menuItem('New Terminal');
 }, {at: '줄 세 개 메뉴를'});
 await ctx.waitFor(() => !!document.querySelector('.terminal-wrapper .xterm-rows') && [...document.querySelectorAll('.terminal-wrapper .xterm-rows > div')].some(d => d.textContent.includes('ontology-lab>')), 15000);
 await ctx.sleep(1200);
 await ctx.say('i206-0209', async () => { const q = await c.serial(() => ctx.p.evaluate(() => { const e = [...document.querySelectorAll('.terminal-tabs-entry, .single-terminal-tab, .terminal-tab')].filter(x => x.innerText.trim() === 'cmd' && x.getBoundingClientRect().width > 0); if (e.length !== 1) throw Error('터미널 이름표 cmd가 ' + e.length + '개'); const b = e[0].getBoundingClientRect(); return {x: b.x + b.width / 2, y: b.y + b.height / 2}; })); await c.move(q.x, q.y); }, {at: 'cmd라고'});
 await ctx.say('i206-0210', async () => { const q = await termLine('ontology-lab>'); await c.move(q.x, q.y); }, {at: '글자 앞 경로가'});
 await ctx.say('i206-0211', async () => { await c.typeKeys('python run.py'); }, {at: 'python run.py를'});
 await ctx.say('i206-0212', async () => { await c.typeKeys(' --no-open'); }, {at: '덧붙이겠습니다'});
 await ctx.say('i206-0213', async () => { await c.key('Enter'); }, {at: 'Enter를'});
 const t0 = Date.now();
 while (!(await ctx.fs.stat(LAB + '/output/result.json').then(() => true, () => false))) { if (Date.now() - t0 > 20000) throw Error('첫 실행 결과(output/result.json)가 생기지 않음'); await ctx.sleep(200); }
 await ctx.waitFor(() => [...document.querySelectorAll('.terminal-wrapper .xterm-rows > div')].some(d => d.textContent.includes('결과: output/result.html')), 15000);
 await ctx.waitFor(() => [...document.querySelectorAll('.explorer-folders-view .monaco-list-row')].some(e => e.getAttribute('aria-level') === '1' && e.innerText.trim() === 'output'), 15000);
 await ctx.sleep(800);
 await ctx.say('i206-0214', async () => { const q = await termLine('원자료 파일과 행 수'); await c.move(q.x, q.y); }, {at: '터미널에'});
 await ctx.say('i206-0215', async () => { const q = await c.explorerRow('output', 1); await c.move(q.x - 34, q.y); }, {at: '탐색기에도'});
 return {segment: 'i206-02', next: 'i206-03: 결과 화면 공간에서 output/result.html', aiRequests: 0};
};
