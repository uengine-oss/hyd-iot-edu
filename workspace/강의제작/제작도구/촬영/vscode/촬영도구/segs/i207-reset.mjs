// 통합 2회차 07편: 녹화 밖 상태 맞춤 — i207-01 시작 화면을 만든다(녹화하지 않는다).
// 부르기: ego-browser nodejs -e "await import('file:///<이 파일>?<판>')" < /dev/null
// 하는 일: 촬영 공간 p1에 graph-lab 폴더를 열고(처음이면 신뢰), 터미널을 닫고, README.md 하나만 남기고, 폴더를 접는다.
// 그리고 이 폴더의 output/ · 실행 캐시 · 랩 DB(.lab_connection.json이 가리키는 컨테이너 하나)를 지워 「처음 만든 DB」 장면을 다시 찍을 수 있게 한다.
// 원자료 · app/features · AGENTS.md · README.md는 건드리지 않는다. 학생 파일을 바꾼 구간 뒤에는 쓰지 않는다(그때는 ZIP을 새로 푼다).
const fs = await import('node:fs/promises');
const {execFileSync} = await import('node:child_process');
const LAB = 'D:/HYD-Practice/i207p-505d6d69/graph-lab';
const task = await taskSpace('통합02 VSCode 촬영준비 20261111');
const p = task.page('p1');
await p.cdp('Emulation.setDeviceMetricsOverride', {width: 2304, height: 1296, deviceScaleFactor: 1, mobile: false});
if ((await fs.readdir(LAB + '/app/features')).length !== 6) throw Error('app/features 파일 수가 시작본과 다름 — ZIP을 새로 푼다');
const state = await fs.readFile(LAB + '/.lab_connection.json', 'utf8').then(JSON.parse, () => null);
if (state) {
 const label = execFileSync('docker', ['inspect', '--format', '{{index .Config.Labels "hyd.practice.id"}}', state.container], {encoding: 'utf8'}).trim();
 if (label !== state.id) throw Error('연결 파일과 컨테이너 라벨이 다름 — 지우지 않음');
 execFileSync('docker', ['rm', '-f', state.container]);
 await fs.rm(LAB + '/.lab_connection.json');
}
for (const rel of ['output', 'app/__pycache__', 'app/utils/__pycache__', 'app/ui/__pycache__', 'app/features/__pycache__']) await fs.rm(LAB + '/' + rel, {recursive: true, force: true});
const root = await p.evaluate(() => document.querySelector('.pane-header[aria-label^="Explorer Section:"]')?.innerText?.toLowerCase());
if (root !== 'graph-lab') {
 const tkn = (await fs.readFile('D:/work/study/hyd-iot-edu-system/작업/촬영/vscode/v143/access.txt', 'utf8')).trim();
 await p.goto('http://127.0.0.1:8793/?tkn=' + tkn + '&folder=' + encodeURIComponent('/' + LAB), {timeout: 60000});
 await p.waitForSelector('.monaco-workbench', {timeout: 60000}); await p.waitForTimeout(6000);
}
const command = async name => {
 await p.keyboard.press('Escape'); await p.keyboard.press('Escape');   // 겹쳐 뜬 신뢰 화면 · 메뉴를 먼저 닫는다(떠 있으면 F1이 먹지 않았다)
 await p.mouse.click(900, 300, {label: 'focus editor'});
 await p.keyboard.press('F1');
 await p.waitForSelector('.quick-input-widget input', {timeout: 10000});
 await p.keyboard.insertText(name); await p.waitForTimeout(700); await p.keyboard.press('Enter'); await p.waitForTimeout(1500);
};
if (await p.evaluate(() => [...document.querySelectorAll('.statusbar-item')].some(e => e.innerText.includes('Restricted Mode')))) {
 await command('Workspaces: Manage Workspace Trust');
 const b = await p.evaluate(() => { const x = [...document.querySelectorAll('.monaco-button')].find(e => e.textContent.trim() === 'Trust' && e.getBoundingClientRect().width > 0); const r = x.getBoundingClientRect(); return {x: r.x + r.width / 2, y: r.y + r.height / 2}; });
 await p.mouse.click(b.x, b.y, {label: 'trust workspace'});
 await p.waitForFunction(() => ![...document.querySelectorAll('.statusbar-item')].some(e => e.innerText.includes('Restricted Mode')), undefined, {timeout: 20000});
}
if (await p.evaluate(() => !!document.querySelector('.terminal-wrapper'))) await command('Terminal: Kill All Terminals');
// 폴더를 바꾼 직후에는 Welcome 탭이 늦게 뜬다 — 다 뜬 뒤에 닫는다
for (let n = 0; n < 15 && !(await p.evaluate(() => document.querySelectorAll('.tabs-container .tab').length)); n++) await p.waitForTimeout(1000);
await p.waitForTimeout(1500);
await command('View: Close All Editors');
await command('File: Collapse Folders in Explorer');
const row = await p.evaluate(() => { const e = [...document.querySelectorAll('.explorer-folders-view .monaco-list-row .label-name')].find(x => x.textContent.trim() === 'README.md'); const r = e.getBoundingClientRect(); return {x: r.x + r.width / 2, y: r.y + r.height / 2}; });
await p.mouse.click(row.x, row.y, {label: 'select README'}); await p.keyboard.press('Enter'); await p.waitForTimeout(1500);
const cx = await p.evaluate(() => { const e = [...document.querySelectorAll('.part.auxiliarybar .composite-bar .action-label')].find(x => (x.getAttribute('aria-label') || '').startsWith('Codex')); if (!e) return null; const r = e.getBoundingClientRect(); return {x: r.x + r.width / 2, y: r.y + r.height / 2}; });
if (cx) { await p.mouse.click(cx.x, cx.y, {label: 'open Codex tab'}); await p.waitForTimeout(4000); }
// 빈 입력칸에서 Enter가 눌리면 Codex가 「Unable to send message」 상자를 띄운다(요청은 나가지 않는다) — 있으면 OK로 닫는다.
for (let n = 0; (await p.snapshot()).includes('Unable to send message'); n++) {   // 웹뷰가 자리 잡기 전에는 단추 크기가 0이라 누를 수 없다 — 잠시 뒤 다시
 if (n >= 10) throw Error('Codex 「Unable to send message」 상자를 닫지 못함');
 await p.click('text="OK"').catch(() => null); await p.waitForTimeout(1000);
}
const out = await p.evaluate(() => ({
 root: document.querySelector('.pane-header[aria-label^="Explorer Section:"]')?.innerText,
 tabs: [...document.querySelectorAll('.tabs-container .tab .label-name')].map(e => e.textContent),
 rows: [...document.querySelectorAll('.explorer-folders-view .monaco-list-row')].map(e => e.innerText.trim()),
 terminal: !!document.querySelector('.terminal-wrapper')?.checkVisibility(),
 restricted: [...document.querySelectorAll('.statusbar-item')].some(e => e.innerText.includes('Restricted Mode')),
}));
out.codex = false;
for (let n = 0; n < 20 && !out.codex; n++) {   // 폴더를 바꾼 직후에는 Codex 웹뷰가 늦게 뜬다 — 고정 대기 대신 화면 글을 기다린다
 const snap = await p.snapshot();
 out.codex = snap.includes('Ask Codex anything') && snap.includes('6-Luna') && snap.includes('Medium');
 if (!out.codex) await p.waitForTimeout(1000);
}
console.log(JSON.stringify(out));
if (out.root?.toLowerCase() !== 'graph-lab' || out.tabs.join() !== 'README.md' || out.terminal || out.restricted || out.rows.includes('output') || !out.codex) throw Error('시작 상태 확인 실패');
