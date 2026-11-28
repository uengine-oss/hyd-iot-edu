// 06-2 구간 10a(첫 페이지): 대화 없이 파일만으로 — 파일 메뉴에서 폴더를 닫았다가 다시 열고(Open Recent), features의 파일을 훑고 python run.py parts → 「새로 썼습니다」 → python run.py query. Codex 부탁 없음.
// 시작: 첫 페이지는 wo-09g 끝 화면(사이에 둘째 페이지 wo-09h) — 앞 take wo-09g. 끝: 다시 연 폴더, 터미널에 query 결과 — 다음은 wo-10b(PAGE=1). 큐 wo1083은 대본 wo1001을 나눈 둘째 조각(판정 문서 「막힌 곳 ①」).
// 폴더를 닫고 여는 것은 웹 VS Code 페이지를 두 번 새로 읽는다 — 화살표와 그림 층이 사라지므로 길잡이를 먼저 걷고, 다시 연 뒤에 화살표와 길잡이를 다시 놓는다(녹화 브라우저로는 아직 해 보지 않았다 — 판정 문서 「미검증」).
import {atPhrase} from './lab-common.mjs';
import {newTerminal} from './lab-common.mjs';
import {ui, LAB, QE, guideIn, guideHide, guideShow, seamOut, keepEnd, unfold, label, termRow, typeCmd, cmdDone, command, PROMPT} from './wo-common.mjs';

const FEATURES = ['classes.csv', 'decisions.csv', 'expected.csv', 'properties.csv', 'quantity_rules.py', 'relations.csv', 'row_rules.csv'];
// 페이지를 새로 읽는 동안에도 견디는 기다림(문맥이 바뀌는 순간의 오류는 다시 본다)
async function waitPage(ctx, fn, what, timeout = 40000) {
 const t0 = Date.now();
 for (;;) {
  try { if (await ctx.serial(() => ctx.p.evaluate(fn))) return; } catch (e) { if (!/destroyed|navigat|detached|closed/i.test(String(e?.message ?? e))) throw e; }
  if (Date.now() - t0 > timeout) throw Error(ctx.cueId + ': ' + what + ' — ' + Math.round(timeout / 1000) + '초 안에 되지 않음 (segs/wo-10a.mjs)');
  await ctx.sleep(300);
 }
}
// 위 메뉴의 항목(글이 has를 담은 보이는 것 하나)을 누른다 — Open Recent의 폴더 경로는 표시 꼴(~ · D:)이 달라 글 일부로 찾는다
async function menuHas(c, ctx, has) {
 const q = await c.serial(() => ctx.p.evaluate(has => { const hits = [...document.querySelectorAll('.monaco-menu .action-label, .context-view .action-label')].filter(e => e.textContent.includes(has) && e.getBoundingClientRect().width > 0); if (hits.length !== 1) return {error: '메뉴 항목 「' + has + '」이 ' + hits.length + '개'}; const b = hits[0].getBoundingClientRect(); return {x: b.x + b.width / 2, y: b.y + b.height / 2}; }, has));
 if (q.error) throw Error(ctx.cueId + ': ' + q.error + ' (segs/wo-10a.mjs)');
 await c.clickAt(q.x, q.y);
}

export default async ctx => {
 const c = await ui(ctx, 0);
 const G = await guideIn(c, ctx, 'vs', {items: QE, ring: 'm5'});
 await c.installPointer(ctx.prev ? null : {x: 900, y: 460});
 await ctx.begin();
 const dir = LAB.split('/').at(-2);   // wvp-<해시> — Open Recent에서 이 촬영 폴더를 고르는 글
 await ctx.say('wo1001', async () => {
  const at = await c.serial(() => ctx.p.evaluate(() => { const r = document.getElementById('recording-pointer').getBoundingClientRect(); return {x: r.x, y: r.y}; }));
  await guideHide(G);
  await c.clickSel('.menubar-menu-button', 'File'); await ctx.waitFor('[...document.querySelectorAll(".monaco-menu .action-label")].some(e => e.textContent.trim() === "Close Folder" && e.getBoundingClientRect().width > 0)', 5000);
  await c.menuItem('Close Folder');
  await waitPage(ctx, () => !!document.querySelector('.monaco-workbench') && !document.querySelector('.pane-header[aria-label^="Explorer Section:"]')?.innerText.toLowerCase().includes('ontology-lab'), '폴더 닫기');
  await ctx.sleep(1500); await c.installPointer(at);
  await c.clickSel('.menubar-menu-button', 'File'); await ctx.waitFor('[...document.querySelectorAll(".monaco-menu .action-label")].some(e => e.textContent.trim() === "Open Recent" && e.getBoundingClientRect().width > 0)', 5000);
  await c.menuItem('Open Recent'); await ctx.sleep(400); await menuHas(c, ctx, dir);
  await waitPage(ctx, () => !!document.querySelector('.pane-header[aria-label^="Explorer Section:"]')?.innerText.toLowerCase().includes('ontology-lab') && document.querySelectorAll('.explorer-folders-view .monaco-list-row').length > 0, '폴더 다시 열기');
  await ctx.sleep(1500); await c.installPointer(at);
  await guideShow(G, false);
  await unfold(c, ctx, 'app', 1); await unfold(c, ctx, 'features', 2);
  for (const [i, f] of FEATURES.entries()) await c.emph(label(f), {shape: 'band', keep: i > 0, point: i === 0});
  // 다시 연 창의 터미널: 되살아난 터미널이 보이면 그대로, 없으면 위 메뉴로 새 터미널을 연다(조작 칸에 없는 조작 — 판정 문서 「미검증」)
  for (let k = 0; k < 16 && !(await c.serial(() => ctx.p.evaluate(p => [...document.querySelectorAll('.terminal-wrapper .xterm-rows > div')].some(d => d.textContent.includes(p)), PROMPT))); k++) await ctx.sleep(500);
  if (!(await c.serial(() => ctx.p.evaluate(p => [...document.querySelectorAll('.terminal-wrapper .xterm-rows > div')].some(d => d.textContent.includes(p)), PROMPT)))) { await newTerminal(c, ctx); await ctx.waitFor('[...document.querySelectorAll(".terminal-wrapper .xterm-rows > div")].some(d => d.textContent.includes(' + JSON.stringify(PROMPT) + '))', 20000); }
  await command(c, ctx, 'python run.py parts');
 }, {at: '파일 메뉴에서 폴더를'});
 await ctx.say('wo1083', async () => {
  await c.emph(termRow('새로 썼습니다'), {shape: 'underline'});
  await typeCmd(c, ctx, 'python run.py query'); const t = Date.now(); await c.key('Enter'); await cmdDone(ctx, t);
 }, {at: '모델 파일을 새로 썼다고'});
 const cut = await seamOut(c, ctx, G);
 await keepEnd(c, ctx, '10a');
 return {segment: 'wo-10a', page: 0, cut, aiRequests: 0, next: 'wo-10b: 결과 화면(PAGE=1) F5 — 같은 답'};
};
