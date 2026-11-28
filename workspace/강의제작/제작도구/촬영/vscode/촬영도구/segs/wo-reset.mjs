// 06-2편 녹화 밖 되돌리기: 구간 하나를 다시 찍기 전에 그 구간의 시작 상태를 만든다(녹화하지 않는다). 부르기: SEG=<구간> ./run.sh reset wo-reset.mjs (녹화 브라우저가 떠 있어야 한다 — ./run.sh up)
// 처음부터 차례로 찍을 때는 부르지 않는다 — 앞 구간 끝 화면이 그대로 다음 구간의 시작이다. 멈춘 take 뒤에 그 구간을 다시 찍을 때만 부른다.
// 하는 일(lab-common.mjs resetLab은 output/을 지우고 ZIP에서 되돌리므로 이 편에는 쓰지 않는다):
//  ① 파일: 앞 첫 페이지 구간의 사본(_wo-<구간> — wo-reset-snap.mjs가 남김)으로 app/features · output을 통째로 바꿔 끼운다(앞 구간 끝과 같은 파일).
//  ② 둘째 페이지 구간: F5 앞의 옛 결과 화면을 둘째 페이지에 띄운다 — 옛 화면을 낸 사본의 result.html로 잠깐 바꿔 끼워 열고, ①의 새 결과로 되돌린다(그 구간의 F5가 새 결과를 읽는다).
//  ③ 첫 페이지 구간: 앞 첫 페이지 구간이 끝난 화면(<work>/_wo/<구간>.end.json — keepEnd가 적음)으로 탭 · 앞 탭의 첫 줄 · 펼친 폴더 · 터미널(지우고 마지막 명령을 다시 쳐 같은 끝 줄)을 맞추고, Codex 답을 끝까지 굴린다.
// Codex 대화는 되돌릴 수 없다 — 요청을 보낸 뒤에 멈춘 take는 다시 보내지 않고 WO_SINCE로 잇는다(판정/녹화모듈_06-2.md 「요청 뒤에 멈췄을 때」).
import fs from 'node:fs/promises';
import path from 'node:path';
import {openPage, folderUrl, VIEW, NAV, WORK} from '../page.mjs';
import {LABS, palette, focusedIn, trustFolder, showCodex} from './lab-common.mjs';
import {SEGS, SNAP, RESULT, PROMPT} from './wo-common.mjs';

const seg = process.env.SEG ?? '', i = SEGS.findIndex(s => s.name === seg);
if (i < 0) throw Error('SEG=' + seg + ' — 구간 이름(' + SEGS.map(s => s.name).join(' · ') + ') (segs/wo-reset.mjs)');
const S = SEGS[i], LAB = LABS.wo.dir;
const page0Before = k => SEGS.slice(0, k).reverse().find(s => s.page === 0)?.name ?? '00';
const prev0 = page0Before(i);
const snap = name => SNAP + '/_wo-' + name;
await fs.access(snap(prev0)).catch(() => { throw Error('사본 ' + snap(prev0) + '이 없음 — 그 구간을 받아들인 뒤 SEG=' + prev0 + ' ./run.sh reset wo-reset-snap.mjs를 불렀는지 본다 (segs/wo-reset.mjs)'); });
const put = async (from, only = null) => {
 for (const d of only ? ['output'] : ['app/features', 'output']) {
  if (only) { for (const f of only) await fs.copyFile(from + '/output/' + f, LAB + '/output/' + f); continue; }
  await fs.rm(LAB + '/' + d, {recursive: true, force: true}); await fs.cp(from + '/' + d, LAB + '/' + d, {recursive: true});
 }
};
await put(snap(prev0));
const log = {seg, page: S.page, files: '_wo-' + prev0};

if (S.page === 1) {
 // F5 앞에 둘째 페이지가 보이던 화면 = 앞 둘째 페이지 구간이 끝난 화면 = 그 구간 앞 첫 페이지 구간의 사본이 낸 결과(첫 둘째 페이지 구간이면 06-1 끝 _wo-00)
 const j = SEGS.slice(0, i).map((s, k) => [s, k]).reverse().find(([s]) => s.page === 1)?.[1];
 const oldFrom = j == null ? '00' : page0Before(j);
 await put(snap(oldFrom), ['result.html', 'result.json']);
 const {p, close} = await openPage(1);
 await p.cdp('Emulation.setDeviceMetricsOverride', {...VIEW, mobile: false});
 await p.goto(RESULT(), {waitUntil: 'load'}); await p.evaluate(() => scrollTo(0, 0)); await p.waitForTimeout(500);
 log.oldScreen = {from: '_wo-' + oldFrom, title: await p.title()};
 await close();
 await put(snap(prev0), ['result.html', 'result.json']);
 console.log(JSON.stringify(log));
} else {
 const endFile = path.join(WORK, '_wo', prev0 + '.end.json');
 const st = await fs.readFile(endFile, 'utf8').then(JSON.parse, () => null);
 if (!st) { console.log(JSON.stringify({...log, ui: '없음 — ' + endFile + '이 없다(06-1 끝 화면이면 06-1 모듈 쪽에서 맞춘다)'})); }
 else {
  const {p, close} = await openPage(0);
  await p.cdp('Emulation.setDeviceMetricsOverride', {...VIEW, mobile: false});
  if (new URL(p.url()).searchParams.get('folder') !== '/' + LAB) { await p.goto(await folderUrl(LAB), NAV); await p.waitForSelector('.monaco-workbench', {timeout: 60000}); await p.waitForTimeout(6000); }
  await trustFolder(p); await showCodex(p);
  for (let k = 0; k < 60 && !(await p.text()).includes('Codex'); k++) await p.waitForTimeout(1000);
  const all = (await fs.readdir(LAB, {recursive: true})).map(f => f.replace(/\\/g, '/')).filter(f => !f.includes('__pycache__'));
  const rel = name => { const h = all.filter(f => f.split('/').pop() === name); if (h.length !== 1) throw Error('탭 「' + name + '」의 파일이 ' + h.length + '개 (segs/wo-reset.mjs)'); return h[0]; };
  await palette(p, 'View: Close All Editors');
  for (const name of [...st.tabs.filter(t => t !== st.active), ...(st.active ? [st.active] : [])]) await palette(p, rel(name), true);
  if (st.active && st.top > 1) {   // 앞 탭의 첫 줄을 끝 화면과 같게 — 편집기를 누르고 맨 위로 간 뒤 휠로 내린다
   const e = await p.evaluate(() => { const b = [...document.querySelectorAll('.editor-instance')].map(x => x.getBoundingClientRect()).find(r => r.width > 0); return {x: b.x + 300, y: b.y + 200}; });
   await p.mouse.click(e.x, e.y); await focusedIn(p, 'editor', '앞 탭 맨 위로'); await p.keyboard.press('Control+Home'); await p.waitForTimeout(300);
   for (let k = 0; k < 30; k++) {
    const top = await p.evaluate(() => { const ed = [...document.querySelectorAll('.part.editor .editor-instance')].find(x => x.getBoundingClientRect().width > 0); const A = ed.querySelector('.editor-scrollable').getBoundingClientRect(); const ns = [...ed.querySelectorAll('.margin-view-overlays .line-numbers')].map(x => ({k: Number(x.textContent.trim()), t: x.getBoundingClientRect().top})).filter(x => x.k && x.t >= A.top - 1).sort((a, b) => a.t - b.t); return [ns[0]?.k ?? 1, ns.length > 1 ? ns[1].t - ns[0].t : 20]; });
    if (top[0] >= st.top) break;
    await p.mouse.wheel(0, Math.min(800, (st.top - top[0]) * top[1])); await p.waitForTimeout(350);
   }
  }
  await palette(p, 'File: Collapse Folders in Explorer');
  for (const f of st.open) {   // 펼친 폴더를 얕은 것부터 다시 편다
   const parts = f.split('/'), name = parts.at(-1), level = parts.length;
   const r = await p.evaluate(({name, level}) => { const e = [...document.querySelectorAll('.explorer-folders-view .monaco-list-row')].find(x => x.getAttribute('aria-level') === String(level) && x.querySelector('.label-name')?.textContent.trim() === name); if (!e) return null; const b = e.getBoundingClientRect(); return {x: b.x + 40, y: b.y + b.height / 2, open: e.getAttribute('aria-expanded') === 'true'}; }, {name, level});
   if (!r) throw Error('탐색기에 폴더 ' + f + '가 없음 (segs/wo-reset.mjs)');
   if (!r.open) { await p.mouse.click(r.x, r.y); await p.waitForTimeout(500); }
  }
  const visible = () => p.evaluate(() => !!document.querySelector('.terminal-wrapper')?.checkVisibility());
  if (st.term) {
   if (!(await visible())) await palette(p, 'Terminal: Create New Terminal');
   for (let k = 0; k < 20 && !(await p.evaluate(q => [...document.querySelectorAll('.terminal-wrapper .xterm-rows > div')].some(d => d.textContent.includes(q)), PROMPT)); k++) await p.waitForTimeout(500);
   await palette(p, 'Terminal: Clear'); await p.waitForTimeout(500);
   if (st.cmd) {   // 끝 화면의 마지막 명령을 다시 쳐 터미널 끝 줄을 같게 만든다(같은 사본이라 같은 출력)
    const q = await p.evaluate(() => { const rows = [...document.querySelectorAll('.terminal-wrapper .xterm-rows > div')]; const l = rows.filter(d => d.textContent.trim()).pop() ?? rows[0]; const b = l.getBoundingClientRect(); return {x: b.x + 300, y: b.y + b.height / 2}; });
    await p.mouse.click(q.x, q.y); await focusedIn(p, 'terminal', '마지막 명령 다시 치기');
    await p.keyboard.type(st.cmd, {delay: 20}); await p.keyboard.press('Enter'); await p.waitForTimeout(4000);
   }
  } else if (await visible()) await palette(p, 'View: Close Panel');
  const a = await p.evaluate(() => { const b = document.querySelector('.part.auxiliarybar').getBoundingClientRect(); return {x: b.x + b.width / 2, y: b.y + b.height * 0.5}; });
  await p.mouse.move(a.x, a.y); for (let k = 0; k < 12; k++) { await p.mouse.wheel(0, 3000); await p.waitForTimeout(150); }   // Codex 답을 끝까지
  const out = await p.evaluate(() => ({tabs: [...document.querySelectorAll('.tabs-container .tab .label-name')].map(e => e.textContent), active: document.querySelector('.tabs-container .tab.active .label-name')?.textContent ?? null, terminal: !!document.querySelector('.terminal-wrapper')?.checkVisibility()}));
  await close();
  console.log(JSON.stringify({...log, ui: '_wo/' + prev0 + '.end.json', want: {tabs: st.tabs, active: st.active, term: st.term, cmd: st.cmd}, got: out}));
  if (out.active !== st.active || out.terminal !== st.term) throw Error('되돌린 화면이 끝 화면과 다름 — 위 want · got을 본다 (segs/wo-reset.mjs)');
 }
}
