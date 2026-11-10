// 통합 2회차 07편 구간 02: 새 터미널 → 경로 확인 → python run.py 첫 실행(원자료와 모델 개수). AI 요청 없음.
// 시작: i207-01 끝(README.md 탭, data 펼침, 빈 Codex). output/ 없음, 터미널 없음.
import {vscode} from '../ui.mjs';
import {LAB, termLine} from './i207-common.mjs';

export default async ctx => {
 const c = await vscode(ctx);
 if (await ctx.fs.stat(LAB + '/output').then(() => true, () => false)) throw Error('output/이 이미 있음 — i207-reset.mjs로 지우고 시작');
 if (await c.serial(() => ctx.p.evaluate(() => !!document.querySelector('.terminal-wrapper')?.checkVisibility()))) throw Error('터미널이 이미 열려 있음');
 await c.installPointer(ctx.prev ? null : {x: 120, y: 200});
 await ctx.begin();
 await ctx.say('i207-0201', async () => {
  await c.clickSel('.menubar-menu-button', 'Application Menu'); await ctx.sleep(500);
  await c.menuItem('Terminal'); await ctx.sleep(500);
  await c.menuItem('New Terminal');
 }, {at: '왼쪽 위 줄 세 개 메뉴에서'});
 await ctx.waitFor(() => [...document.querySelectorAll('.terminal-wrapper .xterm-rows > div')].some(d => d.textContent.includes('graph-lab>')), 15000);
 await ctx.sleep(800);
 await ctx.say('i207-0202', async () => { const q = await termLine(c, ctx, 'graph-lab>'); await c.move(q.x, q.y); }, {at: '글자 앞 경로가'});
 await ctx.say('i207-0203', async () => {
  await c.typeKeys('python run.py');
  await ctx.sleep(2600);
  await c.typeKeys(' --no-open'); await c.key('Enter');
 }, {at: 'python run.py를'});
 const t0 = Date.now();
 while (!(await ctx.fs.stat(LAB + '/output/result.json').then(() => true, () => false))) { if (Date.now() - t0 > 20000) throw Error('첫 실행 결과가 생기지 않음'); await ctx.sleep(200); }
 await ctx.waitFor(() => [...document.querySelectorAll('.terminal-wrapper .xterm-rows > div')].some(d => d.textContent.includes('결과: output/result.html')), 15000);
 await ctx.sleep(800);
 await ctx.say('i207-0204', async () => { const q = await termLine(c, ctx, '노드 206'); await c.move(q.x, q.y); }, {at: '터미널에'});
 await ctx.say('i207-0205', async () => { const q = await termLine(c, ctx, '결과: output/result.html'); await c.move(q.x, q.y); }, {at: '여러분 PC에서는'});
 return {segment: 'i207-02', next: 'i207-03: 결과 화면 공간', aiRequests: 0};
};
