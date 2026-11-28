// 07편 녹화 밖 상태 — 사본(saveState)과 되돌리기(resetTo). 녹화하지 않는다. 부르기(촬영도구 폴더, Git Bash):
//   SEG=<구간> ./run.sh reset wg-save.mjs    그 구간을 녹화해 받아들인 직후 — 랩 폴더(app/features · output)와 화면 상태(탭 · 펼친 폴더 · 터미널 끝 명령 · 결과 화면)를 촬영 폴더 옆 _<구간>/에 남긴다
//   SEG=<구간> ./run.sh reset wg-reset.mjs   그 구간의 시작 상태를 만든다 — 리허설(dry)이나 실패한 take 뒤. 바로 앞 구간의 사본이 있어야 한다(SEG=wg-01은 처음부터)
//   REBUILD=1 … wg-reset.mjs                  랩 DB를 늘 다시 만든다(기본은 그 구간이 랩 DB 단계를 바꾸는 명령을 칠 때 · 연결된 랩 DB가 없을 때만)
// 랩 DB를 다시 만드는 명령은 녹화 밖에서 이 PC의 파이썬으로 --no-open을 붙여 돌린다(학생 화면이 아니다). 터미널 끝 명령은 웹 VS Code의 새 터미널에 학생과 같은 글자로 다시 친다.
// Codex 대화는 되돌릴 수 없다(대화 하나로 이어진다 — 보낸 부탁은 대화에 남는다). 그래서 Codex 요청 구간의 리허설은 WG_NOSEND=1로 보내기 직전까지만 하고, 이 되돌리기는 입력칸만 비운다.
import fs from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import {resetLab, palette, trustFolder, showCodex, focusedIn} from './lab-common.mjs';
import {openPage, folderUrl, NAV, VIEW} from '../page.mjs';
import {LAB, ROOT, RESULT, snapDir, ORDER, STAGES, FEATURES, PROMPT} from './wg-common.mjs';

const PY = 'D:/work/study/hyd-iot-edu-system/.venv314/Scripts/python.exe';   // 녹화 밖 명령의 파이썬(랩은 3.13 이상 표준 라이브러리만 쓴다)
const MARK = ROOT + '/_승인말.txt';
// 탭 이름 → 랩 폴더 안 경로(탭의 title에 경로가 없을 때). 구간 끝에 열려 있을 수 있는 파일만 — schema.json · graph.json은 여는 구간 안에서 닫는다.
const NAMES = {'sensors.csv': 'data/sensors.csv', 'components.csv': 'data/components.csv', 'equipment.csv': 'data/equipment.csv', 'equipment_changes.csv': 'data/changes/2026-10-20/equipment_changes.csv', 'sensor_changes.csv': 'data/changes/2026-10-20/sensor_changes.csv',
 ...Object.fromEntries(FEATURES.map(f => [f.split('/').pop(), f]))};
const stop = why => { throw Error(why + ' (segs/wg-state.mjs)'); };
const idx = seg => { const i = ORDER.findIndex(o => o.seg === seg); if (i < 0) stop('ORDER에 없는 구간: ' + seg + ' — SEG=<구간 이름(wg-02a 꼴)>'); return i; };
const exists = f => fs.stat(f).then(() => true, () => false);
const py = args => {
 try { return execFileSync(PY, ['run.py', ...args, '--no-open'], {cwd: LAB, env: {...process.env, PYTHONUTF8: '1'}, encoding: 'utf8', timeout: 180000}); }
 catch (e) { stop('녹화 밖 명령 python run.py ' + args.join(' ') + ' 실패(종료 ' + e.status + '): ' + String(e.stdout ?? '').slice(-400) + String(e.stderr ?? '').slice(-400)); }
};
const docker = (...a) => execFileSync('docker', a, {encoding: 'utf8'}).trim();

// ── 랩 DB ──
async function dbRemove() {
 const st = await fs.readFile(LAB + '/.lab_connection.json', 'utf8').then(JSON.parse, () => null);
 if (!st) return null;
 if (docker('ps', '-a', '-q', '--filter', 'name=^/' + st.container + '$')) {
  const label = docker('inspect', '--format', '{{index .Config.Labels "hyd.practice.id"}}', st.container);
  if (label !== st.id) stop('연결 파일과 컨테이너 라벨이 다름 — 지우지 않음: ' + st.container);
  docker('rm', '-f', '-v', st.container);
  if (docker('ps', '-a', '-q', '--filter', 'name=^/' + st.container + '$')) stop('랩 DB 컨테이너가 지워지지 않음: ' + st.container);
 }
 await fs.rm(LAB + '/.lab_connection.json');
 return st.container;
}
const dbAlive = async () => { const st = await fs.readFile(LAB + '/.lab_connection.json', 'utf8').then(JSON.parse, () => null); return !!st && docker('ps', '-q', '--filter', 'name=^/' + st.container + '$') !== ''; };
// stage까지 다시 만든다: 지우고 → db → constraints → load → update(지금의 기능 파일로)
async function dbBuild(stage) {
 const gone = await dbRemove(), k = STAGES.indexOf(stage), ran = [];
 for (const [n, cmd] of [[1, 'db'], [2, 'constraints'], [3, 'load'], [4, 'update']]) if (k >= n) { py([cmd]); ran.push(cmd); }
 return {removed: gone, ran, stage};
}

// ── 파일 ──
async function restoreFeatures(snap) {
 const dir = LAB + '/app/features';
 for (const f of await fs.readdir(dir)) if (f !== '__pycache__') await fs.rm(dir + '/' + f, {recursive: true, force: true});
 await fs.cp(snap + '/features', dir, {recursive: true});
}
async function restoreOutput(snap) {
 await fs.rm(LAB + '/output', {recursive: true, force: true});
 if (await exists(snap + '/output')) await fs.cp(snap + '/output', LAB + '/output', {recursive: true});
}

// ── 화면(첫 페이지 웹 VS Code) ──
const measure = p => p.evaluate(PROMPT => {
 const rows = [...document.querySelectorAll('.explorer-folders-view .monaco-list-row')].map(e => ({level: +e.getAttribute('aria-level'), name: e.innerText.replace(/\s*\/\s*/g, '/').trim(), exp: e.getAttribute('aria-expanded')}));
 const stack = [], expanded = [];
 for (const r of rows) { stack.length = r.level - 1; stack[r.level - 1] = r.name; if (r.exp === 'true') expanded.push(stack.slice(0, r.level).join('/')); }
 const tabs = [...document.querySelectorAll('.tabs-container .tab')].map(t => ({name: t.querySelector('.label-name')?.textContent ?? '', active: t.classList.contains('active'), title: t.getAttribute('title') ?? t.querySelector('[title]')?.getAttribute('title') ?? ''}));
 const term = [...document.querySelectorAll('.terminal-wrapper .xterm-rows > div')].map(d => d.textContent.replace(/\u00a0/g, ' ').trimEnd()).filter(l => l.includes(PROMPT + ' python')).pop();
 return {expanded, tabs, term: term ? term.slice(term.indexOf(PROMPT) + PROMPT.length).trim() : null, terminal: !!document.querySelector('.terminal-wrapper')?.checkVisibility(), folder: new URL(location.href).searchParams.get('folder')};
}, PROMPT);
const tabPath = t => { const m = t.title.replace(/\\/g, '/').match(/graph-lab\/(.+)$/); const p = m ? m[1] : NAMES[t.name]; if (!p) stop('탭 「' + t.name + '」의 경로를 알 수 없음 — wg-state.mjs NAMES에 더한다'); return p; };
const waitPrompt = async p => { for (let k = 0; k < 60; k++) { if (await p.evaluate(P => [...document.querySelectorAll('.terminal-wrapper .xterm-rows > div')].some(d => d.textContent.includes(P)), PROMPT)) return; await p.waitForTimeout(500); } stop('새 터미널의 프롬프트(' + PROMPT + ')가 30초 안에 뜨지 않음'); };
async function terminalFresh(p) {
 for (let k = 0; k < 4; k++) { await palette(p, 'Terminal: Kill All Terminals'); await p.waitForTimeout(1500); if (!(await p.evaluate(() => document.querySelectorAll('.terminal-tabs-entry, .single-terminal-tab').length || document.querySelector('.terminal-wrapper')?.checkVisibility()))) break; }
 await palette(p, 'Terminal: Create New Terminal'); await waitPrompt(p); await p.waitForTimeout(1000);
}
async function typeInTerminal(p, text) {
 const r = await p.evaluate(P => { const l = [...document.querySelectorAll('.terminal-wrapper .xterm-rows > div')].filter(d => d.textContent.includes(P)).pop(); const b = l.getBoundingClientRect(); return {x: b.x + 420, y: b.y + b.height / 2}; }, PROMPT);
 await p.mouse.click(r.x, r.y); await focusedIn(p, 'terminal', '터미널 명령 ' + text);
 const t0 = Date.now(); await p.keyboard.type(text, {delay: 10}); await focusedIn(p, 'terminal', '터미널 Enter'); await p.keyboard.press('Enter');
 for (;;) {
  const m = await fs.stat(LAB + '/output/result.json').then(s => s.mtimeMs, () => 0), last = await p.evaluate(() => [...document.querySelectorAll('.terminal-wrapper .xterm-rows > div')].map(d => d.textContent.replace(/\u00a0/g, ' ').trimEnd()).filter(Boolean).pop() ?? '');
  if (m >= t0 - 300 && last.endsWith(PROMPT)) return;
  if (Date.now() - t0 > 120000) stop('터미널 명령이 120초 안에 끝나지 않음: ' + text);
  await p.waitForTimeout(300);
 }
}
async function codexTidy(p) {
 for (const f of p.frames()) {   // 리허설(WG_NOSEND=1)이 넣어 둔 부탁 글을 지운다
  if (f === p.mainFrame()) continue;
  try { const l = f.locator('[contenteditable=true]'); if (!(await l.count()) || !(await l.first().isVisible())) continue;
   if (((await l.first().textContent()) ?? '').trim()) { await l.first().click(); await p.keyboard.press('Control+a'); await p.keyboard.press('Backspace'); await p.waitForTimeout(300); if (((await l.first().textContent()) ?? '').trim()) stop('Codex 입력칸이 비지 않음'); } }
  catch (e) { if (!/detached|destroyed|closed|navigat/i.test(String(e?.message ?? e))) throw e; }
 }
 const a = await p.evaluate(() => { const b = document.querySelector('.part.auxiliarybar')?.getBoundingClientRect(); return b && {x: b.x + b.width / 2, y: b.y + b.height * 0.45}; });
 if (!a) stop('Codex 패널이 열려 있지 않음');
 await p.mouse.move(a.x, a.y); for (let k = 0; k < 6; k++) { await p.mouse.wheel(0, 3000); await p.waitForTimeout(250); }   // 답 끝으로(요청 구간이 끝난 화면처럼)
}
async function uiRestore(p, ui) {
 if (ui.folder !== '/' + LAB) stop('사본의 화면이 이 랩 폴더가 아님: ' + ui.folder);
 const open = URL.canParse(p.url()) ? new URL(p.url()).searchParams.get('folder') : null;
 if (open !== '/' + LAB) { await p.goto(await folderUrl(LAB), NAV); await p.waitForSelector('.monaco-workbench', {timeout: 60000}); await p.waitForTimeout(6000); await trustFolder(p); await showCodex(p); }
 for (let k = 0; ; k++) { if ((await p.text()).includes('Ask Codex anything')) break; if (k >= 60) stop('Codex 패널이 60초 안에 뜨지 않음'); await p.waitForTimeout(1000); }
 await palette(p, 'View: Close All Editors');
 await palette(p, 'File: Collapse Folders in Explorer'); await p.waitForTimeout(800);
 for (const path of ui.expanded) {   // 위 폴더부터 차례로 편다
  const r = await p.evaluate(path => {
   const rows = [...document.querySelectorAll('.explorer-folders-view .monaco-list-row')], stack = [];
   for (const e of rows) { const lv = +e.getAttribute('aria-level'); stack.length = lv - 1; stack[lv - 1] = e.innerText.replace(/\s*\/\s*/g, '/').trim(); if (stack.slice(0, lv).join('/') === path) { const b = (e.querySelector('.label-name') ?? e).getBoundingClientRect(); return {x: b.x + 10, y: b.y + b.height / 2, exp: e.getAttribute('aria-expanded')}; } }
   return null;
  }, path);
  if (!r) stop('탐색기에서 펼칠 폴더를 찾지 못함: ' + path);
  if (r.exp !== 'true') { await p.mouse.click(r.x, r.y); await p.waitForTimeout(600); }
 }
 for (const t of ui.tabs) {
  const path = tabPath(t), name = path.split('/').pop();
  await palette(p, path, true);
  for (let k = 0; k < 30 && await p.evaluate(n => document.querySelector('.tabs-container .tab.active .label-name')?.textContent !== n, name); k++) await p.waitForTimeout(200);
  const e = await p.evaluate(() => { const b = [...document.querySelectorAll('.editor-instance')].map(x => x.getBoundingClientRect()).find(r => r.width > 0 && r.height > 0); return b && {x: b.x + 300, y: b.y + 200}; });
  if (!e) stop('되돌리기: ' + path + '를 열지 못함');
  await p.mouse.click(e.x, e.y); await focusedIn(p, 'editor', path + ' 맨 위로'); await p.keyboard.press('Control+Home'); await p.waitForTimeout(300);
 }
 const act = ui.tabs.find(t => t.active);
 if (act && !(await p.evaluate(n => document.querySelector('.tabs-container .tab.active .label-name')?.textContent === n, act.name))) {
  const b = await p.evaluate(n => { const e = [...document.querySelectorAll('.tabs-container .tab .label-name')].find(x => x.textContent === n); const r = e?.getBoundingClientRect(); return r && {x: r.x + r.width / 2, y: r.y + r.height / 2}; }, act.name);
  if (!b) stop('앞에 둘 탭이 없음: ' + act.name); await p.mouse.click(b.x, b.y); await p.waitForTimeout(500);
 }
 await terminalFresh(p);
 if (ui.term) {
  if (ui.term === 'python run.py') await fs.rm(LAB + '/output', {recursive: true, force: true});   // 첫 실행 줄(F5 안내가 없는 결과 줄)을 그대로 다시 찍는다
  await typeInTerminal(p, ui.term);
 }
 await codexTidy(p);
 const now = await measure(p);
 const same = JSON.stringify([now.expanded, now.tabs.map(t => t.name), now.tabs.find(t => t.active)?.name, now.term]) === JSON.stringify([ui.expanded, ui.tabs.map(t => t.name), ui.tabs.find(t => t.active)?.name, ui.term]);
 if (!same) stop('되돌린 화면이 사본과 다름 — 사본 ' + JSON.stringify(ui) + ' · 지금 ' + JSON.stringify(now));
 return now;
}

// ── 둘째 페이지(결과 화면) ──
const lastResult = i => { for (let k = i - 1; k >= 0; k--) if (ORDER[k].page === 1) return ORDER[k]; return null; };
async function page1Restore(p0, i, snap) {
 const r = lastResult(i); if (!r) return null;
 const rs = snapDir(r.seg), st = JSON.parse(await fs.readFile(rs + '/state.json', 'utf8').catch(() => stop('앞 결과 화면 구간 ' + r.seg + '의 사본이 없음')));
 const pages = p0.context().pages(); if (pages.length < 2) stop('녹화 브라우저에 둘째 페이지가 없음 — ' + r.seg + '를 먼저 찍는다');
 const p1 = pages[1];
 await fs.mkdir(LAB + '/output', {recursive: true});
 await fs.copyFile(rs + '/output/result.html', LAB + '/output/result.html');   // 그 구간이 끝날 때 둘째 페이지에 떠 있던 화면
 await p1.goto(RESULT); await p1.waitForTimeout(800);
 await p1.evaluate(y => scrollTo(0, y), st.page1?.scrollY ?? 0); await p1.waitForTimeout(300);
 await restoreOutput(snap);   // 디스크의 결과 파일은 앞 구간 끝의 것(F5로 새로 읽을 화면)
 return {page1: r.seg, scrollY: st.page1?.scrollY ?? 0};
}

// ── 사본 ──
export async function saveState(seg) {
 const i = idx(seg), o = ORDER[i], dir = snapDir(seg);
 await fs.rm(dir, {recursive: true, force: true}); await fs.mkdir(dir, {recursive: true});
 await fs.cp(LAB + '/app/features', dir + '/features', {recursive: true, filter: s => !s.includes('__pycache__')});
 if (await exists(LAB + '/output')) await fs.cp(LAB + '/output', dir + '/output', {recursive: true});
 const {p, close} = await openPage(0);
 try {
  const ui = await measure(p), pages = p.context().pages();
  const page1 = pages[1] ? {url: decodeURI(pages[1].url()), scrollY: await pages[1].evaluate(() => scrollY).catch(() => 0)} : null;
  const conn = await fs.readFile(LAB + '/.lab_connection.json', 'utf8').then(JSON.parse, () => null);
  if (STAGES.indexOf(o.db) > 0 && !conn) stop(seg + ' 뒤에는 랩 DB가 있어야 하는데(' + o.db + ') 연결 파일이 없음');
  const state = {seg, time: new Date().toISOString(), db: o.db, container: conn?.container ?? null, ui, page1};
  await fs.writeFile(dir + '/state.json', JSON.stringify(state, null, 1));
  console.log(JSON.stringify({saved: dir, db: o.db, tabs: ui.tabs.map(t => t.name), expanded: ui.expanded, term: ui.term, page1}));
 } finally { await close(); }
}

// ── 되돌리기 ──
// 파일과 랩 DB만(녹화 브라우저를 쓰지 않는다): 바로 앞 구간 사본의 기능 파일로 되돌리고, 그 구간이 랩 DB 단계를 바꾸면(또는 연결된 랩 DB가 없으면 · REBUILD=1) 앞 구간 끝의 단계로 다시 만든다.
export async function prepFiles(seg) {
 const i = idx(seg);
 if (i === 0) stop('wg-01은 처음부터 — prepFiles가 아니라 resetTo');
 const prev = ORDER[i - 1], target = ORDER[i], snap = snapDir(prev.seg);
 const st = JSON.parse(await fs.readFile(snap + '/state.json', 'utf8').catch(() => stop('앞 구간 ' + prev.seg + '의 사본이 없음 — 그 구간을 찍어 받아들인 뒤 SEG=' + prev.seg + ' ./run.sh reset wg-save.mjs')));
 const out = {seg, from: prev.seg};
 await restoreFeatures(snap);
 const need = STAGES.indexOf(prev.db) > 0 && !(await dbAlive());
 if (target.db !== prev.db || need || process.env.REBUILD === '1') out.db = await dbBuild(prev.db);
 await restoreOutput(snap);
 return {i, target, snap, st, out};
}
export async function resetTo(seg) {
 if (idx(seg) === 0) return fullStart();
 const {i, target, snap, st, out} = await prepFiles(seg);
 const {p, close} = await openPage(0);
 try {
  await p.cdp('Emulation.setDeviceMetricsOverride', {...VIEW, mobile: false});   // 녹화와 같은 화면 값(resetLab과 같다)
  if (target.page === 0) out.ui = await uiRestore(p, st.ui);
  await restoreOutput(snap);
  if (seg !== 'wg-02b') out.result = await page1Restore(p, i, snap);
 } finally { await close(); }
 const m = await fs.readFile(MARK, 'utf8').catch(() => null);
 if (m && idx(m.split(' ')[0]) >= i) { await fs.rm(MARK); out.approveMark = '지움(' + m.split(' ')[0] + '에서 말한 기록)'; }
 console.log(JSON.stringify(out));
 return out;
}
// 편의 시작: 촬영 폴더를 새 상태로(lab-common resetLab — 랩 DB · output · 기능 파일을 ZIP 그대로, 새 대화) → 지난 사본과 승인 말 기록을 지움 → 터미널 하나를 연다.
async function fullStart() {
 await resetLab('wg', {reload: true, restore: FEATURES});
 for (const d of await fs.readdir(ROOT)) if (d.startsWith('_wg-')) await fs.rm(ROOT + '/' + d, {recursive: true, force: true});
 await fs.rm(MARK, {force: true});
 const {p, close} = await openPage(0);
 try {
  await p.cdp('Emulation.setDeviceMetricsOverride', {...VIEW, mobile: false});
  await terminalFresh(p);
  const ui = await measure(p);
  if (ui.tabs.length || ui.expanded.length || !ui.terminal) stop('첫 화면 확인 실패: ' + JSON.stringify(ui));
  console.log(JSON.stringify({seg: 'wg-01', start: true, ui}));
 } finally { await close(); }
}
