// 새 구조 코딩 랩(README · data · app · output) 앞 구간들이 함께 쓰는 짚기 도구와 녹화 밖 되돌리기. 조작 층은 ../ui.mjs.
// 온톨로지 파트 두 반의 12편(i206 · i207 · i305 · i306 · i404 · i405 · p207~p209 · p305 · p307 · p308)이 쓴다.
// 터미널 줄을 짚으려면 촬영용 웹 VS Code의 terminal.integrated.gpuAcceleration이 off여야 한다(촬영준비 길 4).
// 구간 모듈은 조작 층을 labUi(ctx)로 받는다. labUi는 ../ui.mjs의 vscode(ctx)에 세 가지를 더한다.
//  ① 짚기 · 클릭 · 타이핑 · 키마다 ctx.report에 {cue, op, target, fail, why}를 남긴다(run.sh dry의 dry.json이 큐 · 조작을 센다 — ../ctrl.mjs dryRun).
//     대상이 그 영역(편집기 · 터미널 · 화면) 밖이면 fail을 남기고 멈춘다. 대상을 못 찾으면 찾는 함수가 멈춘다(dry.json error).
//  ② 글 · 키를 보내기 직전에 입력 초점을 본다. 터미널 글은 터미널, 편집기 글은 편집기에서만, Enter는 터미널 · 탐색기 · 명령 창에서만 보낸다.
//     Codex 웹뷰(iframe)나 다른 곳에 초점이 있으면 fail로 멈춘다 — 글이 Codex 입력칸으로 가서 전송되지 않게 한다.
//  ③ ctx.say를 감싸 지금 큐의 글과 시작 시각을 들고 있다. 한 큐 안의 둘째 조작은 고정 sleep 대신 atPhrase(ctx, '구절')로 그 구절을 말할 때 한다.
//     dry는 at 구절이 큐 JSON(LABS의 cues)의 글에 차례대로 있는지 본다. 말만 하는 큐는 op 'say' 한 줄로 세어, dry.json의 cues가 그 구간의 큐 수와 같다.
//  ④ 강조 · 펜 그림 · 글상자(../draw.mjs — c.emph · c.clearEmph · c.pen · c.note)도 조작으로 세어 ctx.report에 op 'emph' · 'pen' · 'note'로 남긴다.
//     자주 짚는 대상은 아래 em.line · em.term · em.row · em.codex로 만든다.

import fs from 'node:fs/promises';
import {vscode} from '../ui.mjs';
import {openPage, folderUrl, VIEW, NAV} from '../page.mjs';

// 페이지가 읽는 화면 폭(innerWidth). 녹화 브라우저의 실제 픽셀 폭 2304를 배율로 나눈 값이다(../config.json viewport — 1843 × 1.2497은 올림되어 2304가 되고, 페이지는 1844로 읽는다).
const VIEW_W = Math.round(Math.ceil(VIEW.width * VIEW.deviceScaleFactor) / VIEW.deviceScaleFactor);
export const page = lab => 'file:///' + lab + '/output/result.html';

// 랩마다 촬영 폴더 · 정본 ZIP · app/features 시작 파일 수 · 큐 JSON. 촬영 폴더 경로는 이 표 한 곳에만 둔다(구간 모듈 · 되돌리기는 LABS.<접두>.dir을 읽는다).
// readme: false = README.md가 없는 랩(2회차 새 판). 되돌리기가 편집기를 모두 닫은 화면으로 끝낸다.
// 큐 id는 `<접두>-<구간 2자리><번호>`(i206-0101)이거나 `<영문 접두><장 2자리><번호 2자리>`(wv0301)다 — cueKey가 접두와 구간을 가른다.
// 촬영 폴더는 ZIP을 새로 푼 D:/HYD-Practice/<접두>p-<ZIP sha256 앞 8자리>/<랩>이다. 작업 폴더가 아니라 ZIP 판에 묶여 있어 `동기화.py 정리 --실행`이 지우지 않는다(CLAUDE.md 1절).
// ZIP이 바뀌면 resetLab이 멈춘다. 그때 표를 고치는 작업자는 새 ZIP을 새 폴더에 풀어 이 표를 고치고, 옛 폴더를 그 안 랩 DB(.lab_connection.json의 id와 라벨 hyd.practice.id가 같은 컨테이너, docker rm -f -v)와 함께 지운다.
const OUT = 'D:/work/study/hyd-iot-edu-system/workspace/강의제작/산출물/';
const CUES = decodeURIComponent(new URL('../../', import.meta.url).pathname).replace(/^\/([A-Za-z]:)/, '$1');
export const LABS = {
 i206: {dir: 'D:/HYD-Practice/i206p-de28cdbd/ontology-lab', zip: OUT + '통합반/실습/02회차/랩/ontology-lab.zip', features: 13, cues: '통합_02_06_온톨로지설계_큐.json'},
 i207: {dir: 'D:/HYD-Practice/i207p-3b60ca65/graph-lab', zip: OUT + '통합반/실습/02회차/랩/graph-lab.zip', features: 6, cues: '통합_02_07_그래프구현_큐.json'},
 i305: {dir: 'D:/HYD-Practice/i305p-72d62c92/action-criteria-lab', zip: OUT + '통합반/실습/03회차/랩/action-criteria-lab.zip', features: 7, cues: '통합_03_05_조치기준_큐.json'},
 i306: {dir: 'D:/HYD-Practice/i306p-35a16aa0/judgement-lab', zip: OUT + '통합반/실습/03회차/랩/judgement-lab.zip', features: 5, cues: '통합_03_06_판단기능_큐.json'},
 i404: {dir: 'D:/HYD-Practice/i404p-ec273938/knowledge-extract-lab', zip: OUT + '통합반/실습/04회차/랩/knowledge-extract-lab.zip', features: 7, cues: '통합_04_04_문서지식추출_큐.json'},
 i405: {dir: 'D:/HYD-Practice/i405p-99271aa9/knowledge-graph-lab', zip: OUT + '통합반/실습/04회차/랩/knowledge-graph-lab.zip', features: 10, cues: '통합_04_05_그래프반영_큐.json'},
 p207: {dir: 'D:/HYD-Practice/p207p-2a7e8165/ontology-lab', zip: OUT + '실전반/실습/02회차/랩/ontology-lab.zip', features: 5, cues: '실전_02_07_온톨로지설계_큐.json'},
 p208: {dir: 'D:/HYD-Practice/p208p-0b761866/graph-lab', zip: OUT + '실전반/실습/02회차/랩/graph-lab.zip', features: 5, cues: '실전_02_08_그래프구현_큐.json'},
 p209: {dir: 'D:/HYD-Practice/p209p-d3849a15/condition-table-lab', zip: OUT + '실전반/실습/02회차/랩/condition-table-lab.zip', features: 5, cues: '실전_02_09_조치조건표_큐.json'},
 p305: {dir: 'D:/HYD-Practice/p305p-a187ceba/action-review-lab', zip: OUT + '실전반/실습/03회차/랩/action-review-lab.zip', features: 5, cues: '실전_03_05_조치검토_큐.json'},
 p307: {dir: 'D:/HYD-Practice/p307p-e0076eb3/condition-extract-lab', zip: OUT + '실전반/실습/03회차/랩/condition-extract-lab.zip', features: 8, cues: '실전_03_07_지식추출_큐.json'},
 wv: {dir: 'D:/HYD-Practice/wvp-b2ffa6ac/ontology-lab', zip: OUT + '통합반/실습/02회차/랩/ontology-lab.zip', features: 6, cues: '통합_02_06-1_VSCode랩시작하기_큐.json', readme: false},
 p308: {dir: 'D:/HYD-Practice/p308p-f1a55b73/work-card-lab', zip: OUT + '실전반/실습/03회차/랩/work-card-lab.zip', features: 10, cues: '실전_03_08_작업카드_큐.json'},
};
// 쉼(영상 V-14). 큐 사이 쉼 cue는 ../ctrl.mjs의 기본 gap과 같은 값이고, labUi의 ctx.say가 큐마다 이 값을 gap으로 준다.
// 구간 경계: ctrl.mjs는 구간 끝 말 뒤 tail(400ms)을 두고 끝나고, 다음 구간의 첫 큐는 쉼 없이 시작한다(첫 큐에는 앞 말이 없어 gap이 먹지 않는다).
// 그래서 01이 아닌 구간의 첫 큐 앞에 segment − tail을 쉬어 경계 쉼을 segment로 맞춘다(녹화 때만). 앞 구간이 말보다 늦게 끝난 조작으로 닫히면 그만큼 길어진다.
export const PAUSE = {cue: 1300, result: 2000, segment: 2300, tail: 400};
// 조작 결과(열린 탭 · 터미널 프롬프트 · 실행 출력)가 화면에 뜬 것을 확인한 뒤 다음 말 전에 쉰다
export const afterResult = ctx => ctx.sleep(PAUSE.result);
export const cueKey = id => { const m = /^([a-z]+\d*)-(\d{2})/.exec(id) || /^([a-z]+)(\d{2})\d{2}$/.exec(id); if (!m) throw Error('큐 id 꼴이 아님: ' + id + ' (segs/lab-common.mjs cueKey)'); return {key: m[1], seg: m[2]}; };
const labOf = key => { const l = LABS[key]; if (!l) throw Error('LABS에 없는 접두: ' + key + ' (segs/lab-common.mjs)'); return l; };

// 찾는 함수가 돌려준 좌표에 이름과 그 대상이 보여야 할 영역(box)을 붙여 둔다. labUi의 짚기 · 클릭이 같은 좌표를 받으면 이 이름과 영역으로 잰다.
const aimed = (ctx, name, q) => { (ctx.__aims ??= []).push({...q, name}); if (ctx.__aims.length > 16) ctx.__aims.shift(); return {x: q.x, y: q.y}; };
// 터미널에서 글이 text를 담은 마지막 줄의 앞쪽
export const termLine = (c, ctx, text) => c.serial(() => ctx.p.evaluate(text => {
 const rows = document.querySelector('.terminal-wrapper .xterm-rows');
 if (!rows) throw Error('터미널 줄을 DOM에서 읽을 수 없음 — terminal.integrated.gpuAcceleration을 off로');
 const l = [...rows.children].filter(d => d.textContent.includes(text)).pop();
 if (!l) throw Error('터미널 줄 없음: ' + text);
 const b = l.getBoundingClientRect(), w = rows.closest('.terminal-wrapper').getBoundingClientRect();
 return {x: b.x + 120, y: b.y + b.height / 2, box: {left: w.left, top: w.top, right: w.right, bottom: w.bottom}};
}, text)).then(q => aimed(ctx, '터미널 줄 ~' + text, q));
// 터미널에서 text가 담긴 줄이 보일 때까지 터미널 위에서 휠을 굴린다(up = 위로). 출력이 터미널 높이보다 길어 짚을 줄이 밀려 올라갔을 때 쓴다(회귀 dry p308-0210).
// 터미널은 DOM에 보이는 줄만 그리므로, 줄을 찾으면 화면 안이다.
export async function termScrollTo(c, ctx, text, up = true) {
 const seen = () => c.serial(() => ctx.p.evaluate(text => [...document.querySelectorAll('.terminal-wrapper .xterm-rows > div')].some(d => d.textContent.includes(text)), text));
 if (await seen()) return;
 const w = await c.serial(() => ctx.p.evaluate(() => { const b = document.querySelector('.terminal-wrapper').getBoundingClientRect(); return {x: b.x + b.width * 0.6, y: b.y + b.height / 2}; }));
 await c.move(w.x, w.y); await c.gate();
 for (let n = 0; n < 20; n++) { await c.serial(() => ctx.p.mouse.wheel(0, up ? -120 : 120)); await ctx.sleep(300); if (await seen()) return; }
 throw Error('터미널을 굴려도 줄이 보이지 않음: ' + text);
}
// 터미널에 text가 담긴 줄이 뜰 때까지 기다린다
export const termWait = (ctx, text, timeout = 15000) => ctx.waitFor('[...document.querySelectorAll(".terminal-wrapper .xterm-rows > div")].some(d => d.textContent.includes(' + JSON.stringify(text) + '))', timeout);
// 편집기에서 글이 text로 시작하는 줄의 앞쪽(영역 = 편집기의 보이는 줄 칸 — 미리 그려 둔 줄이라도 그 칸 밖이면 화면 밖이다)
export const lineAt = (c, ctx, text) => c.serial(() => ctx.p.evaluate(text => {
 const l = [...document.querySelectorAll('.editor-instance .view-lines .view-line')].find(e => e.textContent.replace(/\u00a0/g, ' ').startsWith(text));
 if (!l) throw Error('줄 없음: ' + text);
 const b = l.getBoundingClientRect(), w = (l.closest('.editor-scrollable') || l.closest('.monaco-editor')).getBoundingClientRect();
 return {x: b.x + 60, y: b.y + b.height / 2, box: {left: w.left, top: w.top, right: w.right, bottom: w.bottom}};
}, text)).then(q => aimed(ctx, '편집기 줄 ' + text, q));
// 탐색기 맨 위 랩 폴더 이름
export const rootHeader = (c, ctx) => c.serial(() => ctx.p.evaluate(() => { const b = document.querySelector('.pane-header[aria-label^="Explorer Section:"] .title').getBoundingClientRect(); return {x: b.x + 20, y: b.y + b.height / 2}; })).then(q => aimed(ctx, '탐색기 폴더 이름', q));
// 탐색기 줄의 접기 화살표 쪽(이름 위에 오래 두면 경로 툴팁이 아래 줄을 가린다 — 촬영준비 함정)
export const row = async (c, name, level) => { const q = await c.explorerRow(name, level); return aimed(c.ctx ?? {}, '탐색기 ' + name, {x: q.x - 34, y: q.y, box: c.ctx?.__aims?.at(-1)?.box}); };
export const rowSeen = (ctx, name, level) => ctx.waitFor('[...document.querySelectorAll(".explorer-folders-view .monaco-list-row")].some(e => e.getAttribute("aria-level") === "' + level + '" && e.innerText.trim() === ' + JSON.stringify(name) + ')', 15000);
// 결과 화면: 표에서 첫 칸 글이 name인 줄의 n번째 칸 · 글이 text로 시작하는 제목
export const cell = (c, ctx, name, n = 0) => c.serial(() => ctx.p.evaluate(({name, n}) => {
 const tr = [...document.querySelectorAll('tr')].filter(r => r.cells[0]?.textContent.trim() === name);
 if (tr.length !== 1) throw Error('표 줄이 ' + tr.length + '개: ' + name);
 const b = tr[0].cells[n].getBoundingClientRect(); return {x: b.x + 30, y: b.y + b.height / 2};
}, {name, n})).then(q => aimed(ctx, '표 ' + name + ' 칸 ' + n, q));
export const heading = (c, ctx, text, sel = 'h3') => c.serial(() => ctx.p.evaluate(({text, sel}) => { const e = [...document.querySelectorAll(sel)].find(x => x.textContent.startsWith(text)); if (!e) throw Error('제목 없음: ' + text); const b = e.getBoundingClientRect(); return {x: b.x + 40, y: b.y + b.height / 2}; }, {text, sel})).then(q => aimed(ctx, '제목 ' + text, q));
export const inView = (q, h = 1037) => { if (q.y < 0 || q.y > h - 10) throw Error('화면 밖 대상: ' + JSON.stringify(q)); return q; };
export const exists = (ctx, path) => ctx.fs.stat(path).then(() => true, () => false);

// 01구간 첫 화면 검사: README.md 탭, 랩 폴더 이름, 화면 폭 · 배율(../config.json viewport), output 없음, 빈 Codex 새 대화, 신뢰됨, 오류 상자 없음.
// 화면 글은 ctx.p.text()로 읽는다 — Codex 새 대화 화면의 글은 웹뷰 iframe 안에 있어 바깥 문서의 DOM으로는 읽히지 않는다(../page.mjs).
export async function firstView(c, ctx, root) {
 const view = await c.serial(() => ctx.p.evaluate(() => ({
  w: innerWidth, h: innerHeight, dpr: devicePixelRatio,
  title: document.querySelector('.tabs-container .tab.active .label-name')?.textContent,
  root: document.querySelector('.pane-header[aria-label^="Explorer Section:"]')?.innerText,
  rows: [...document.querySelectorAll('.explorer-folders-view .monaco-list-row')].map(e => e.innerText.trim()),
  terminal: !!document.querySelector('.terminal-wrapper')?.checkVisibility(),
 })));
 if (view.title !== 'README.md' || view.root?.toLowerCase() !== root || view.w !== VIEW_W || Math.abs(view.dpr - 1.25) > 0.01 || view.rows.includes('output') || view.terminal) throw Error('첫 화면 조건 불일치(화면 폭 기대 ' + VIEW_W + '): ' + JSON.stringify(view));
 const snap = await c.serial(() => ctx.p.text());
 if (!snap.includes('Ask Codex anything.') || !snap.includes('Get Plus') || snap.includes('Intelligence') || snap.includes('Restricted Mode') || snap.includes('Unable to send message')) throw Error('빈 Codex 새 대화 · 모델 · 폴더 신뢰를 먼저 확인합니다.');
 return view;
}

// 결과 화면 공간의 시작: 방금 쓴 결과 파일을 다시 읽고 크기를 확인한다(녹화 전).
export async function resultView(c, ctx, lab, title) {
 await c.serial(() => ctx.p.goto(page(lab))); await ctx.sleep(800);
 await c.serial(() => ctx.p.evaluate(() => scrollTo(0, 0)));
 const view = await c.serial(() => ctx.p.evaluate(() => ({w: innerWidth, h: innerHeight, dpr: devicePixelRatio, title: document.title, sw: document.documentElement.scrollWidth})));
 if (view.w !== VIEW_W || Math.abs(view.dpr - 1.25) > 0.01 || view.sw > view.w || !view.title.startsWith(title)) throw Error('결과 화면 조건 불일치: ' + JSON.stringify(view));
 return view;
}

// 페이지 안에서 실행: 지금 입력 초점이 있는 곳. Codex 채팅은 웹뷰 iframe이라 초점이 iframe 요소로 보인다.
const zoneInPage = () => {
 const a = document.activeElement;
 if (!a || a === document.body) return 'none';
 if (a.tagName === 'IFRAME' || a.closest('.part.auxiliarybar, .webview')) return 'codex';
 if (a.closest('.quick-input-widget')) return 'quick';
 if (a.closest('.terminal-wrapper')) return a.classList.contains('xterm-helper-textarea') ? 'terminal' : 'terminal-other';
 if (a.closest('.part.editor .monaco-editor')) return 'editor';
 if (a.closest('.explorer-folders-view')) return 'explorer';
 return 'other ' + a.tagName.toLowerCase() + '.' + String(a.className).slice(0, 40);
};
const zoneOK = {typeKeys: ['terminal'], type: ['editor'], Enter: ['terminal', 'explorer', 'quick'], key: ['terminal', 'explorer', 'quick', 'editor']};

// ── 녹화 밖에서 웹 VS Code에 명령을 보내는 길(되돌리기 resetLab · 화면 준비 ../prep.mjs가 쓴다). p = ../page.mjs가 준 페이지 ──
// 글 · Enter를 보내기 직전에 초점을 본다 — 초점이 Codex 웹뷰에 있으면 그 글과 Enter가 Codex 입력칸으로 간다.
export const focusedIn = async (p, want, what) => { const z = await p.evaluate(zoneInPage); if (z !== want) throw Error('녹화 밖 조작: ' + what + ' 앞 입력 초점이 ' + want + '이 아니라 ' + z + ' — 보내지 않고 멈춤'); };
// F1 명령 창에 name을 넣고 Enter. file = true면 명령 창의 「>」를 지워 파일 찾기로 쓴다.
export async function palette(p, name, file = false) {
 const focused = (want, what) => focusedIn(p, want, what);
 await p.keyboard.press('Escape'); await p.keyboard.press('Escape');   // 겹쳐 뜬 신뢰 화면 · 메뉴를 먼저 닫는다(떠 있으면 F1이 먹지 않았다)
 const f = await p.evaluate(() => { const e = document.querySelector('.part.sidebar .composite.title .title-label'); const b = e?.getBoundingClientRect(); return b ? {x: b.x + b.width / 2, y: b.y + b.height / 2} : {x: 900, y: 300}; });   // 신뢰 편집기 위를 누르면 그 안의 링크가 눌려 F1이 먹지 않았다 — 탐색기 머리 글자를 누른다
 // 폴더를 연 직후에는 Codex 웹뷰(iframe)가 늦게 떠서 초점을 가져가, F1이 웹뷰로 가고 명령 창이 뜨지 않았다(회귀 dry i306 · p209 · p308 되돌리기, 2026-11-11).
 // 그래서 탐색기 머리를 눌러 초점을 바탕으로 옮기고 F1을 누른 뒤, 보이는 명령 창 입력칸이 초점을 받을 때까지 기다리고, 못 받으면 세 번까지 다시 한다.
 for (let t = 0; t < 3 && await p.evaluate(zoneInPage) !== 'quick'; t++) {
  if (t) { await p.keyboard.press('Escape'); await p.waitForTimeout(1000); }
  await p.mouse.click(f.x, f.y);
  if (await p.evaluate(zoneInPage) === 'codex') await p.evaluate(() => document.activeElement?.blur());
  await p.keyboard.press('F1');
  for (let k = 0; k < 30 && await p.evaluate(zoneInPage) !== 'quick'; k++) await p.waitForTimeout(100);
 }
 await focused('quick', 'F1 명령 ' + name);
 if (file) await p.keyboard.press('Control+a');   // 명령 창의 「>」를 지우면 파일 찾기가 된다
 await p.keyboard.insertText(name); await p.waitForTimeout(700);
 await focused('quick', 'F1 명령 ' + name); await p.keyboard.press('Enter'); await p.waitForTimeout(1500);
}

// 오른쪽 칸의 탭 「Chat | Codex」 가운데 Codex를 앞에 둔다(학생 화면처럼 두 탭이 다 있고, 새 프로필은 Chat이 앞에 있다). Codex 탭이 없으면 멈춘다.
export async function showCodex(p) {
 const tab = () => p.evaluate(() => { const e = [...document.querySelectorAll('.part.auxiliarybar .composite-bar .action-item')].find(x => (x.querySelector('.action-label')?.getAttribute('aria-label') || x.textContent || '').trim().startsWith('Codex')); if (!e) return null; const b = e.getBoundingClientRect(); return {x: b.x + b.width / 2, y: b.y + b.height / 2, on: e.classList.contains('checked')}; });
 let t = null; for (let k = 0; k < 20 && !(t = await tab()); k++) await p.waitForTimeout(1000);
 if (!t) throw Error('오른쪽 칸에 Codex 탭이 없음 — 확장과 폴더 신뢰를 본다(촬영준비 길 2 · 3) (segs/lab-common.mjs showCodex)');
 if (!t.on) { await p.mouse.click(t.x, t.y); await p.waitForTimeout(4000); if (!(await tab())?.on) throw Error('Codex 탭이 앞에 오지 않음 (segs/lab-common.mjs showCodex)'); }
}

// 폴더 신뢰(촬영준비 길 3): 상태 표시줄에 Restricted Mode가 있으면 Workspace Trust 편집기의 Trust 단추를 좌표로 누르고, 그 표시가 사라진 뒤 창을 새로 고친다. 이미 신뢰한 폴더면 아무것도 하지 않는다.
// 그 폴더에 지난 터미널이 살아 있으면 웹 VS Code가 그것을 되살리려고 「Do you trust the authors of the files in this folder?」 창을 편집기 위에 늦게 띄운다.
// 그 창이 떠 있는 동안에는 편집기의 Trust 단추가 눌리지 않으므로, 떠 있으면 그 창의 「Trust Folder & Continue」를 누른다(같은 신뢰다).
export async function trustFolder(p) {
 for (let k = 0; k < 10 && !(await p.evaluate(() => document.querySelectorAll('.statusbar-item').length)); k++) await p.waitForTimeout(1000);
 const restricted = () => p.evaluate(() => [...document.querySelectorAll('.statusbar-item')].some(e => e.innerText.includes('Restricted Mode')));
 const button = (sel, text) => p.evaluate(({sel, text}) => { const x = [...document.querySelectorAll(sel)].find(e => e.textContent.trim() === text && e.getBoundingClientRect().width > 0); const r = x?.getBoundingClientRect(); return r ? {x: r.x + r.width / 2, y: r.y + r.height / 2} : null; }, {sel, text});
 if (!(await restricted())) return false;
 await palette(p, 'Workspaces: Manage Workspace Trust');
 let pressed = false;
 for (const t0 = Date.now(); await restricted(); await p.waitForTimeout(500)) {
  if (Date.now() - t0 > 20000) throw Error('폴더 신뢰를 주지 못함 — 20초 뒤에도 Restricted Mode (segs/lab-common.mjs trustFolder)');
  const d = await button('.monaco-dialog-box .monaco-button', 'Trust Folder & Continue');
  if (d) { await p.mouse.click(d.x, d.y); continue; }
  if (pressed) continue;
  const b = await button('.monaco-button', 'Trust');
  if (!b) throw Error('Workspace Trust 편집기의 Trust 단추가 보이지 않음 (segs/lab-common.mjs trustFolder)');
  await p.mouse.click(b.x, b.y); pressed = true;
 }
 // 신뢰를 준 그 창에서는 Codex 패널에 웹뷰가 생기지 않았다(새 폴더 i206 되돌리기가 60초 기다려도 「Ask Codex anything」 없음, 새로 고치니 4초 만에 뜸 — 2026-11-11). 신뢰 뒤에 창을 한 번 새로 고친다.
 await p.reload(NAV); await p.waitForSelector('.monaco-workbench', {timeout: 60000}); await p.waitForTimeout(3000);
 return true;
}

// 녹화 밖 되돌리기(녹화하지 않는다, 부르기: ../run.sh reset <편>-reset.mjs). key = LABS의 접두. 녹화 브라우저의 첫 페이지에 그 랩 폴더를 열고(처음이면 신뢰), 터미널을 닫고, README.md 하나만 남기고, 폴더를 접는다.
// output/ · 실행 캐시를 지우고, 랩 DB(.lab_connection.json의 ID와 컨테이너 라벨이 같을 때만) 하나를 그 익명 볼륨과 함께 지운다(docker rm -f -v).
// 촬영 폴더 이름의 해시가 정본 ZIP의 sha256 앞 8자리와 다르거나, app/features 파일 수가 시작본과 다르면 멈춘다 — 그때는 ZIP을 새 폴더에 새로 풀고 LABS를 고친다.
// restore = 녹화 구간이 고치는 학생 파일(랩 폴더 기준 경로) — 같은 ZIP에서 그 파일만 다시 꺼내 원본으로 돌린다.
// top = 녹화 구간이 열어 아래로 굴리는 파일(랩 폴더 기준 경로). VS Code는 닫은 파일의 스크롤 자리를 기억해 다음 take에서 그 자리로 다시 연다(회귀 dry p209-02, 2026-11-11) — 열어서 맨 위로 올린 뒤 닫는다.
// reload = 같은 폴더가 열려 있어도 창을 새로 고친다(Codex 패널이 지난 대화 대신 새 대화 화면으로 돌아온다).
export async function resetLab(key, {restore = [], top = [], reload = false} = {}) {
 const {dir: lab, zip, features, readme = true} = labOf(key), root = lab.split('/').pop();
 const {execFileSync} = await import('node:child_process');
 const {createHash} = await import('node:crypto');
 const sha = createHash('sha256').update(await fs.readFile(zip)).digest('hex').slice(0, 8);
 if (!lab.includes('p-' + sha + '/')) throw Error(key + ': 촬영 폴더 ' + lab + '가 지금 ZIP(sha256 ' + sha + ')을 푼 폴더가 아님 — D:/HYD-Practice/' + key + 'p-' + sha + '/에 새로 풀고 segs/lab-common.mjs LABS를 고친다');
 await fs.stat(lab + (readme ? '/README.md' : '/run.py')).catch(() => { throw Error(key + ': 촬영 폴더가 없음 — ' + zip + '을 ' + lab.slice(0, -root.length - 1) + '에 푼다'); });
 const {p, close} = await openPage(0);
 await p.cdp('Emulation.setDeviceMetricsOverride', {...VIEW, mobile: false});
 const n = (await fs.readdir(lab + '/app/features')).filter(f => f !== '__pycache__').length;
 if (n !== features) throw Error('app/features 파일 수 ' + n + '가 시작본 ' + features + '과 다름 — ZIP을 새로 푼다');
 const state = await fs.readFile(lab + '/.lab_connection.json', 'utf8').then(JSON.parse, () => null);
 if (state) {
  const label = execFileSync('docker', ['inspect', '--format', '{{index .Config.Labels "hyd.practice.id"}}', state.container], {encoding: 'utf8'}).trim();
  if (label !== state.id) throw Error('연결 파일과 컨테이너 라벨이 다름 — 지우지 않음');
  execFileSync('docker', ['rm', '-f', '-v', state.container], {encoding: 'utf8'});
  await fs.rm(lab + '/.lab_connection.json');
 }
 if (restore.length) {   // Windows tar(bsdtar)가 zip을 푼다 — Git의 GNU tar는 D:를 원격 주소로 읽고 zip을 못 푼다
  execFileSync('C:/Windows/System32/tar.exe', ['-xf', zip, '-C', lab.slice(0, -root.length - 1), ...restore.map(r => root + '/' + r)], {encoding: 'utf8'});
 }
 await fs.rm(lab + '/output', {recursive: true, force: true});
 for (const d of await fs.readdir(lab, {recursive: true})) if (d.replace(/\\/g, '/').endsWith('__pycache__')) await fs.rm(lab + '/' + d, {recursive: true, force: true});
 // 같은 이름의 랩 폴더가 여럿이라(ontology-lab · graph-lab) 이름이 아니라 주소의 folder 값으로 지금 열린 폴더를 가린다
 const open = URL.canParse(p.url()) ? new URL(p.url()).searchParams.get('folder') : null;   // 막 띄운 녹화 브라우저는 about:blank다
 if (open === '/' + lab && reload) { await p.reload(NAV); await p.waitForSelector('.monaco-workbench', {timeout: 60000}); await p.waitForTimeout(6000); }
 if (open !== '/' + lab) {
  await p.goto(await folderUrl(lab), NAV);
  await p.waitForSelector('.monaco-workbench', {timeout: 60000}); await p.waitForTimeout(6000);
 }
 const command = (name, file = false) => palette(p, name, file);
 const focused = (want, what) => focusedIn(p, want, what);
 await trustFolder(p);
 // 폴더를 연 직후 Codex 웹뷰는 늦게 떠서 뜨는 순간 초점을 가져간다(회귀 dry p308 되돌리기가 두 번 「F1 앞 초점 codex」로 멈춤, 2026-11-11).
 // 신뢰가 있는 폴더에서 새 대화 화면 글이 뜰 때까지 기다린 뒤에 명령을 보낸다(Restricted Mode에서는 Codex가 꺼져 있으므로 신뢰 뒤에 기다린다).
 for (let k = 0; ; k++) { const sn = await p.text(); if (sn.includes('Ask Codex anything') && sn.includes('Get Plus')) break; if (k >= 60) throw Error('되돌리기: Codex 새 대화 화면이 60초 안에 뜨지 않음'); await p.waitForTimeout(1000); }
 await p.waitForTimeout(1000);
 // 폴더를 바꾼 직후에는 Welcome 탭이 늦게 뜬다 — 다 뜬 뒤에 닫는다
 for (let k = 0; k < 15 && !(await p.evaluate(() => document.querySelectorAll('.tabs-container .tab').length)); k++) await p.waitForTimeout(1000);
 await p.waitForTimeout(1500);
 await command('View: Close All Editors');
 // 신뢰 편집기 · Welcome을 먼저 닫은 뒤에 연다(남아 있으면 그 편집기 칸을 눌러 초점이 신뢰 편집기의 목록으로 갔다 — 회귀 dry p308 되돌리기)
 for (const f of top) {
  await command(f, true);
  const name = f.split('/').pop();
  for (let k = 0; k < 30 && await p.evaluate(n => document.querySelector('.tabs-container .tab.active .label-name')?.textContent !== n, name); k++) await p.waitForTimeout(200);
  const e = await p.evaluate(() => { const b = [...document.querySelectorAll('.editor-instance')].map(x => x.getBoundingClientRect()).find(r => r.width > 0 && r.height > 0); return b && {x: b.x + 300, y: b.y + 200}; });   // 줄 묶음(.view-lines)은 굴린 만큼 화면 위로 밀려 있다 — 편집기 칸을 누른다
  if (!e) throw Error('되돌리기: ' + f + '를 열지 못함');
  await p.mouse.click(e.x, e.y); await focused('editor', f + ' 맨 위로'); await p.keyboard.press('Control+Home'); await p.waitForTimeout(500);
 }
 if (top.length) await command('View: Close All Editors');
 await command('File: Collapse Folders in Explorer');
 // 폴더를 다시 열면 VS Code가 그 폴더의 지난 터미널을 늦게 되살린다 — 다른 정리를 마친 뒤 보이는 터미널이 없어질 때까지 닫는다.
 // 터미널 칸이 닫힌 창(새 프로필)에서는 되살아난 터미널이 화면에 없다가, 녹화 구간이 새 터미널을 열 때 목록에 경고 표시와 함께 나타난다. 그래서 보이는 터미널이 없어도 닫는 명령을 한 번은 보낸다.
 for (let k = 0; k < 4; k++) {
  await p.waitForTimeout(1500);
  if (k && !(await p.evaluate(() => !!document.querySelector('.terminal-wrapper')?.checkVisibility() || document.querySelectorAll('.terminal-tabs-entry, .single-terminal-tab').length > 0))) break;
  await command('Terminal: Kill All Terminals');
 }
 if (readme) {
 const r = await p.evaluate(() => { const e = [...document.querySelectorAll('.explorer-folders-view .monaco-list-row .label-name')].find(x => x.textContent.trim() === 'README.md'); const b = e.getBoundingClientRect(); return {x: b.x + b.width / 2, y: b.y + b.height / 2}; });
 await p.mouse.click(r.x, r.y); await focused('explorer', 'README 열기'); await p.keyboard.press('Enter'); await p.waitForTimeout(1500);
 await p.mouse.click(r.x + 600, 500); await focused('editor', 'README 맨 위로'); await p.keyboard.press('Control+Home');
 }
 await showCodex(p);
 // 빈 입력칸에서 Enter가 눌리면 Codex가 「Unable to send message」 상자를 띄운다(요청은 나가지 않는다) — 있으면 OK로 닫는다.
 for (let k = 0; (await p.text()).includes('Unable to send message'); k++) {   // 웹뷰가 자리 잡기 전에는 단추 크기가 0이라 누를 수 없다 — 잠시 뒤 다시
  if (k >= 10) throw Error('Codex 「Unable to send message」 상자를 닫지 못함');
  if (k) await p.waitForTimeout(1000);
  await p.clickText('OK').catch(e => { if (k >= 9) throw e; });   // 아직 못 누르면 다시 재고, 끝내 못 누르면 그 까닭으로 멈춘다
 }
 const out = await p.evaluate(() => ({
  root: document.querySelector('.pane-header[aria-label^="Explorer Section:"]')?.innerText,
  tabs: [...document.querySelectorAll('.tabs-container .tab .label-name')].map(e => e.textContent),
  rows: [...document.querySelectorAll('.explorer-folders-view .monaco-list-row')].map(e => e.innerText.trim()),
  terminal: !!document.querySelector('.terminal-wrapper')?.checkVisibility(),
  restricted: [...document.querySelectorAll('.statusbar-item')].some(e => e.innerText.includes('Restricted Mode')),
  screenReader: [...document.querySelectorAll('.statusbar-item')].some(e => e.innerText.includes('Screen Reader')),
 }));
 out.codex = false;
 for (let k = 0; k < 20 && !out.codex; k++) {   // 폴더를 바꾼 직후에는 Codex 웹뷰가 늦게 뜬다 — 고정 대기 대신 화면 글을 기다린다
  const snap = await p.text();
  out.codex = snap.includes('Ask Codex anything') && snap.includes('Get Plus');
  if (!out.codex) await p.waitForTimeout(1000);
 }
 console.log(JSON.stringify(out));
 await close();
 if (out.root?.toLowerCase() !== root || out.tabs.join() !== (readme ? 'README.md' : '') || out.terminal || out.restricted || out.screenReader || out.rows.includes('output') || !out.codex) throw Error('시작 상태 확인 실패');
 return out;
}

// ── 여러 편이 같은 꼴로 하는 조작 ──
// 위 메뉴 줄의 Terminal → New Terminal(조작만, 큐는 부르는 쪽이 준다). 메뉴 줄은 촬영준비 길 4의 설정(window.menuBarVisibility visible)으로 편다 — ☰ 단추만 있으면 Terminal 단추를 못 찾아 멈춘다
export async function newTerminal(c, ctx) {
 const shown = text => ctx.waitFor('[...document.querySelectorAll(".monaco-menu .action-label, .context-view .action-label")].some(e => e.textContent.trim() === ' + JSON.stringify(text) + ' && e.getBoundingClientRect().width > 0)', 5000);   // 메뉴가 그려진 뒤에 고른다
 await c.clickSel('.menubar-menu-button', 'Terminal'); await shown('New Terminal');
 await c.menuItem('New Terminal');
}
// ── Codex 패널(웹뷰) ── 녹화 브라우저는 웹뷰 프레임 안의 요소까지 잰다. 이름이나 글이 있는 단추와 입력칸은 비율 좌표로 어림하지 않고 codexEl로 잰다.
// want = {label: 'aria-label의 앞 글'}(예: 'New chat' · 'Archive chat') | {text: '정확히 같은 글'} | {input: true}(요청 입력칸). 보이는 요소가 하나가 아니면 멈춘다.
// 돌려주는 값 = 그 요소의 가운데(바깥 문서의 CSS px)와 크기 {x, y, w, h}.
export async function codexEl(c, ctx, want) {
 const name = want.input ? '입력칸' : want.label ?? want.text;
 const q = await c.serial(async () => {
  const hits = [];
  for (const f of ctx.p.frames()) {
   if (f === ctx.p.mainFrame()) continue;
   const l = want.input ? f.locator('[contenteditable=true]') : want.label != null ? f.locator('[aria-label^=' + JSON.stringify(want.label) + ']') : f.getByText(want.text, {exact: true});
   try { const n = await l.count(); for (let i = 0; i < n; i++) if (await l.nth(i).isVisible()) { const b = await l.nth(i).boundingBox(); if (b) hits.push(b); } }
   catch (e) { if (!/detached|destroyed|closed|navigat/i.test(String(e?.message ?? e))) throw e; }   // 웹뷰가 다시 그려지는 순간의 프레임만 건너뛴다
  }
  if (hits.length !== 1) throw Error((ctx.cueId ?? '(큐 밖)') + ': Codex 패널의 「' + name + '」이 ' + hits.length + '개 (segs/lab-common.mjs codexEl)');
  return {x: hits[0].x + hits[0].width / 2, y: hits[0].y + hits[0].height / 2, w: hits[0].width, h: hits[0].height};
 });
 const a = await c.codexArea();
 return {...aimed(ctx, 'Codex ' + name, {x: q.x, y: q.y, box: {left: a.x, top: a.y, right: a.x + a.w, bottom: a.y + a.h}}), w: q.w, h: q.h};
}
// 요청 입력칸을 눌러 초점을 준다. 한 번 눌러 초점이 오지 않으면 세 번까지 누르고, 그래도 초점이 Codex에 없으면 멈춘다.
export async function codexFocus(c, ctx) {
 const q = await codexEl(c, ctx, {input: true});
 for (let k = 0; k < 3; k++) { await c.clickAt(q.x, q.y); await ctx.sleep(300); if (await c.serial(() => ctx.p.evaluate(zoneInPage)) === 'codex') return q; }
 throw Error((ctx.cueId ?? '(큐 밖)') + ': Codex 입력칸이 초점을 받지 않음 — 보내지 않고 멈춤 (segs/lab-common.mjs codexFocus)');
}
// 초점이 있는 입력칸에 부탁 글을 넣는다(긴 글이라 붙여넣듯 빠르게 — 영상 V-14). 초점이 Codex에 없으면 넣지 않고 멈춘다.
export async function codexType(c, ctx, text) {
 if (await c.serial(() => ctx.p.evaluate(zoneInPage)) !== 'codex') throw Error((ctx.cueId ?? '(큐 밖)') + ': 입력 초점이 Codex가 아님 — 글을 보내지 않고 멈춤 (segs/lab-common.mjs codexType)');
 const t0 = Date.now(); await c.typeFast(text); ctx.report?.push({cue: ctx.cueId, op: 'type', target: 'Codex 입력칸', text, ms: Date.now() - t0, fail: false});
}
// Enter로 보낸다(실제 요청이 나간다 — 리허설도 같다). 돌려주는 값 = 보낸 시각(codexWait의 since).
export async function codexSubmit(c, ctx) {
 await c.gate();
 if (await c.serial(() => ctx.p.evaluate(zoneInPage)) !== 'codex') throw Error((ctx.cueId ?? '(큐 밖)') + ': 입력 초점이 Codex가 아님 — Enter를 보내지 않고 멈춤 (segs/lab-common.mjs codexSubmit)');
 const since = Date.now(); await c.serial(() => ctx.p.keyboard.press('Enter')); ctx.report?.push({cue: ctx.cueId, op: 'key', target: 'Enter', zone: 'codex', fail: false});
 return since;
}
// 응답이 끝나기를 기다린다(촬영준비 길 9): 화면이 아니라 <CODEX_HOME>/sessions의 rollout 기록에서 since 뒤의 task_complete를 찾는다.
// CODEX_HOME은 웹 VS Code 서버를 켠 값(촬영준비 길 1)을 실행할 때 환경변수로 준다(CODEX_HOME=… ./run.sh rec …).
// 돌려주는 값 = {message: 끝난 답, used: 계정 한도 사용률 %, ms: 보낸 뒤 걸린 시간, file}. 기록에 오류 사건이 있으면 그 글로 멈춘다(한도 · 로그인).
export async function codexWait(ctx, since, timeout = 180000) {
 const home = process.env.CODEX_HOME;
 if (!home) throw Error('CODEX_HOME 없음 — 웹 VS Code 서버를 켠 값(촬영준비 길 1)을 CODEX_HOME=… ./run.sh 앞에 준다 (segs/lab-common.mjs codexWait)');
 const root = home.replace(/\\/g, '/') + '/sessions';
 let seen = [];
 for (;;) {
  for (const rel of await fs.readdir(root, {recursive: true})) {
   const file = root + '/' + rel.replace(/\\/g, '/');
   if (!/rollout-[^/]*\.jsonl$/.test(file) || (await fs.stat(file)).mtimeMs < since) continue;
   let used = null; seen = [];
   for (const line of (await fs.readFile(file, 'utf8')).split('\n')) {
    if (!line.trim()) continue;
    let o; try { o = JSON.parse(line); } catch { continue; }   // 쓰는 중인 마지막 줄
    if (Date.parse(o.timestamp) < since - 2000) continue;
    const p = o.payload ?? {}; seen.push(p.type ?? o.type);
    if (p.rate_limits?.primary) used = p.rate_limits.primary.used_percent;
    if (o.type === 'event_msg' && /error/.test(p.type ?? '')) throw Error('Codex 오류 사건 ' + p.type + ': ' + String(p.message ?? JSON.stringify(p)).slice(0, 400) + ' (' + file + ')');
    if (o.type === 'event_msg' && p.type === 'task_complete') return {message: p.last_agent_message, used, ms: Date.parse(o.timestamp) - since, file};
   }
  }
  if (Date.now() - since > timeout) throw Error('Codex 응답이 ' + Math.round(timeout / 1000) + '초 안에 끝나지 않음 — 마지막 사건: ' + seen.slice(-5).join(' · ') + ' (segs/lab-common.mjs codexWait)');
  await ctx.sleep(1000);
 }
}
// 그림 한 장을 화면 가득 띄운다(녹화 전) — 웹 VS Code 밖의 화면(06-1 여는 장의 사용자 녹화 첫 프레임) 위에 펜 그림 · 글상자를 그릴 때 쓴다. file = 그림의 절대 경로.
// 16:9가 아니면 찌그러지므로 멈춘다. 둘째 페이지에서 쓴다(PAGE=1 — 첫 페이지의 웹 VS Code를 떠나지 않게).
export async function imageView(c, ctx, file) {
 if (ctx.p.url().startsWith('http')) throw Error('그림은 웹 VS Code 페이지가 아닌 둘째 페이지에 띄운다 — PAGE=1 ./run.sh … (segs/lab-common.mjs imageView)');
 await c.serial(() => ctx.p.goto('file:///' + file.replace(/\\/g, '/')));
 const v = await c.serial(() => ctx.p.evaluate(() => {
  const img = document.images[0]; if (!img || !img.naturalWidth) return null;
  document.documentElement.style.cssText = 'margin:0;background:#000;overflow:hidden'; document.body.style.cssText = 'margin:0;overflow:hidden';
  img.style.cssText = 'display:block;width:100vw;height:100vh;margin:0;cursor:default';
  return {nw: img.naturalWidth, nh: img.naturalHeight, w: innerWidth, h: innerHeight, dpr: devicePixelRatio};
 }));
 if (!v) throw Error('그림을 열지 못함: ' + file + ' (segs/lab-common.mjs imageView)');
 if (v.nw * 9 !== v.nh * 16) throw Error('그림이 16:9가 아님(' + v.nw + '×' + v.nh + ') — 화면 가득 띄우면 찌그러진다: ' + file);
 if (v.w !== VIEW_W) throw Error('그림 화면 조건 불일치(화면 폭 기대 ' + VIEW_W + '): ' + JSON.stringify(v));
 return v;
}
// 명령 뒤 결과 파일과 터미널 끝 줄을 기다린다
export async function waitRun(ctx, lab, endText = '결과: output/result.html', timeout = 20000) {
 const t0 = Date.now();
 while (!(await exists(ctx, lab + '/output/result.json'))) { if (Date.now() - t0 > timeout) throw Error('실행 결과(output/result.json)가 생기지 않음'); await ctx.sleep(200); }
 await termWait(ctx, endText, timeout); await afterResult(ctx);
}
// 편집기에서 글이 text로 시작하는 줄이 편집기 위쪽 limit px 안에 올 때까지 휠로 내린다(화살표는 편집기 빈 곳으로 먼저 옮긴다)
export async function scrollEditorTo(c, ctx, text, limit = 420) {
 const e = await c.serial(() => ctx.p.evaluate(() => { const b = document.querySelector('.editor-instance .view-lines').getBoundingClientRect(); return {x: b.x + 700, y: b.y + 420}; }));
 await c.move(e.x, e.y); await c.gate();
 for (let n = 0; n < 12; n++) {
  const h = await c.serial(() => ctx.p.evaluate(text => { const l = [...document.querySelectorAll('.editor-instance .view-lines .view-line')].find(x => x.textContent.replace(/\u00a0/g, ' ').startsWith(text)); return l ? l.getBoundingClientRect().y : null; }, text));
  if (h !== null && h < limit) return;
  await c.serial(() => ctx.p.mouse.wheel(0, 240)); await ctx.sleep(450);
 }
 throw Error('편집기에서 줄을 찾지 못함: ' + text);
}
// 결과 화면에서 대상이 화면 아래쪽 안에 올 때까지 휠로 내린다(get은 좌표를 돌려주는 함수)
export async function scrollPageTo(c, ctx, get, h = 1037, margin = 160) {
 await c.gate();
 for (let n = 0; n < 30; n++) { const q = await get(); if (q.y < h - margin && q.y > 60) return q; await c.serial(() => ctx.p.mouse.wheel(0, 240)); await ctx.sleep(450); }
 throw Error('결과 화면에서 대상이 화면 안에 오지 않음');
}
// 결과 화면 표: cols칸 표에서 첫 칸이 key인 보이는 줄의 n번째 칸
export const tableCell = (c, ctx, key, n = 0, cols = null) => c.serial(() => ctx.p.evaluate(({key, n, cols}) => {
 const tr = [...document.querySelectorAll('tbody tr')].filter(r => (cols === null || r.cells.length === cols) && r.cells[0].textContent.trim() === key && !r.classList.contains('hide'));
 if (tr.length !== 1) throw Error('표 줄이 ' + tr.length + '개: ' + key);
 const b = tr[0].cells[n].getBoundingClientRect(); return {x: b.x + Math.min(30, b.width / 2), y: b.y + b.height / 2};
}, {key, n, cols})).then(q => aimed(ctx, '표 ' + key + ' 칸 ' + n, q));
export const tableHead = (c, ctx, name) => c.serial(() => ctx.p.evaluate(name => { const th = [...document.querySelectorAll('th')].filter(e => e.textContent.trim() === name && e.getBoundingClientRect().width > 0); if (th.length !== 1) throw Error('표 머리 ' + th.length + '개: ' + name); const b = th[0].getBoundingClientRect(); return {x: b.x + 20, y: b.y + b.height / 2}; }, name)).then(q => aimed(ctx, '표 머리 ' + name, q));

// 강조 대상(c.emph의 첫 인자): 편집기에서 글이 text로 시작하는 줄 · 터미널에서 text가 든 마지막 줄(둘 다 그 줄의 글자가 차지한 폭만큼) · 결과 화면 표에서 첫 칸이 key인 줄(n을 주면 그 줄의 n번째 칸) · Codex 패널 안의 비율 상자(웹뷰라 글을 잴 수 없다 — 녹화 답 화면을 보고 정한다)
export const em = {
 line: text => ({sel: '.editor-instance .view-lines .view-line', starts: text, tight: true}),
 term: text => ({sel: '.terminal-wrapper .xterm-rows > div', has: text, pick: 'last', tight: true}),
 row: (key, n = null) => ({sel: 'tbody tr', cell: [0, key], ...(n == null ? {} : {child: n})}),
 codex: (x0, y0, x1, y1) => ({codex: [x0, y0, x1, y1]}),
};

// ── 조작 층: ../ui.mjs의 vscode(ctx) + 조작 기록 · 화면 안 검사 · 입력 초점 검사 · 말 시점(맨 위 머리말 ①②③) ──
const cueText = async (ctx, id) => {
 if (!ctx.rehearsal) { const a = JSON.parse(await fs.readFile(ctx.audio + '/' + id + '.json', 'utf8')); return {text: a.text, dur: a.duration_ms}; }
 const file = CUES + labOf(cueKey(id).key).cues;
 const q = JSON.parse(await fs.readFile(file, 'utf8')).cues.find(x => x.id === id);   // 큐 파일 꼴은 포털과 같다: {voice_id, model_id, cues: [{id, segment, text}]}
 if (!q) throw Error(id + ': 큐 JSON에 없는 큐 — ' + file);
 return {text: q.text, dur: 0};
};
export async function labUi(ctx) {
 const c = await vscode(ctx);
 c.ctx = ctx;
 const base = {move: c.move, clickAt: c.clickAt, clickSel: c.clickSel, menuItem: c.menuItem, explorerRow: c.explorerRow, codexPoint: c.codexPoint, typeKeys: c.typeKeys, type: c.type, key: c.key, emph: c.emph, clearEmph: c.clearEmph, pen: c.pen, note: c.note};
 const rep = o => { ctx.report?.push({cue: ctx.cueId, ...o}); };
 const bad = (o, why) => { rep({...o, fail: true, why}); throw Error((ctx.cueId ?? '(큐 밖)') + ' ' + o.op + ' ' + (o.target ?? '') + ': ' + why); };
 let inner = 0;   // 클릭 안에서 화살표를 옮기는 것은 짚기로 따로 세지 않는다(화면 안 검사는 한다)
 // 대상이 보여야 할 영역(찾는 함수가 붙인 box, 없으면 화면) 안에 점이 있는가. 화살표 몸통이 오른쪽 아래로 그려지므로 아래 · 오른쪽에 여백을 둔다.
 const check = async (op, x, y, name) => {
  const aim = (ctx.__aims ?? []).findLast(a => Math.abs(a.x - x) < 1 && Math.abs(a.y - y) < 1);
  const v = await c.serial(() => ctx.p.evaluate(() => ({w: innerWidth, h: innerHeight})));
  const box = aim?.box ?? {left: 0, top: 0, right: v.w, bottom: v.h};
  const o = {op, target: name ?? aim?.name ?? `좌표 (${Math.round(x)}, ${Math.round(y)})`, x: Math.round(x), y: Math.round(y)};
  if (!(x >= Math.max(0, box.left) && x <= Math.min(v.w, box.right) - 4 && y >= Math.max(0, box.top) + 2 && y <= Math.min(v.h - 10, box.bottom - 4)))
   bad(o, '화면 밖 대상 — 영역 ' + JSON.stringify(Object.fromEntries(Object.entries(box).map(([k, n]) => [k, Math.round(n)]))));
  return o;
 };
 const zone = () => c.serial(() => ctx.p.evaluate(zoneInPage));
 const needZone = async (o, kind) => { const z = await zone(); if (!zoneOK[kind].includes(z)) bad(o, '입력 초점이 ' + zoneOK[kind].join(' · ') + '이 아니라 ' + z + ' — 보내지 않고 멈춤'); return z; };
 c.explorerRow = async (name, level) => { const q = await base.explorerRow(name, level); const b = await c.serial(() => ctx.p.evaluate(() => document.querySelector('.explorer-folders-view')?.getBoundingClientRect().toJSON())); return aimed(ctx, '탐색기 ' + name, {...q, box: b}); };
 c.codexPoint = async (fx, fy) => { const q = await base.codexPoint(fx, fy); const a = await c.codexArea(); return aimed(ctx, 'Codex 패널', {...q, box: {left: a.x, top: a.y, right: a.x + a.w, bottom: a.y + a.h}}); };
 c.move = async (x, y) => { const o = await check('point', x, y); await base.move(x, y); if (!inner) rep({...o, fail: false}); };
 c.clickAt = async (x, y) => { const o = await check('click', x, y); inner++; try { await base.clickAt(x, y); } finally { inner--; } rep({...o, fail: false}); };
 c.clickSel = async (selector, text) => { inner++; try { await base.clickSel(selector, text); } finally { inner--; } rep({op: 'click', target: text ?? selector, fail: false}); };
 c.menuItem = async text => { inner++; try { await base.menuItem(text); } finally { inner--; } rep({op: 'click', target: '메뉴 ' + text, fail: false}); };
 c.typeKeys = async text => { const o = {op: 'type', target: '터미널', text}; await c.gate(); await needZone(o, 'typeKeys'); const t0 = Date.now(); await base.typeKeys(text); rep({...o, ms: Date.now() - t0, fail: false}); };
 c.type = async (text, aside) => { const o = {op: 'type', target: '편집기', text}; if (aside) await c.move(aside.x, aside.y); await c.gate(); await needZone(o, 'type'); const t0 = Date.now(); await base.type(text); rep({...o, ms: Date.now() - t0, fail: false}); };
 c.key = async k => { const o = {op: 'key', target: k}; await c.gate(); const z = await needZone(o, k === 'Enter' ? 'Enter' : 'key'); await base.key(k); rep({...o, zone: z, fail: false}); };
 // 강조 · 펜 그림 · 글상자: 대상이 없거나 화면 밖이면 ../draw.mjs가 큐 id를 대며 멈추고, 아래 ctx.say가 그 실패를 한 줄로 남긴다.
 const tag = t => typeof t === 'string' ? t : JSON.stringify(t).slice(0, 120);
 c.emph = async (target, o = {}) => { await base.emph(target, o); rep({op: 'emph', target: tag(target), shape: o.shape ?? 'band', ...(o.phrase ? {phrase: o.phrase} : {}), fail: false}); };
 c.clearEmph = async () => { await base.clearEmph(); rep({op: 'emph', target: '지움', fail: false}); };
 c.pen = def => { const f = base.pen(def); for (const k of Object.keys(f)) { const fn = f[k]; f[k] = async (...a) => { await fn(...a); rep({op: 'pen', target: def.id + ' ' + k + (a.length ? ' ' + a.map(tag).join(' ') : ''), fail: false}); }; } return f; };
 c.note = async (lines, o) => { await base.note(lines, o); rep({op: 'note', target: lines ? '띄움 ' + lines.length + '줄' : '걷음', fail: false}); };
 // ctx.say: 지금 큐의 글과 시작 시각을 들고, at 구절이 큐 글에 있는지 보며, 조작이 있는 큐가 조작을 하나도 남기지 않으면 멈춘다.
 const say = ctx.say;
 ctx.say = async (id, fn, opt = {}) => {
  opt = {gap: PAUSE.cue, ...opt};
  if (!ctx.__said) { ctx.__said = true; if (!ctx.rehearsal && cueKey(id).seg !== '01') await ctx.sleep(PAUSE.segment - PAUSE.tail); }
  ctx.cueId = id;
  const q = await cueText(ctx, id);
  const i = opt.at != null ? q.text.indexOf(opt.at) : -1;
  if (opt.at != null && i < 0) bad({op: 'at', target: opt.at}, '큐 글에 없는 at 구절');
  if (!fn) { rep({op: 'say', target: '말만', fail: false}); return say(id, fn, opt); }
  return say(id, async () => {
   const frac = opt.pointFrac ?? (i >= 0 ? Math.max(0, (i - 1) / q.text.length) : null);   // ../ctrl.mjs cue()가 첫 조작을 시작한 시점과 같은 계산
   ctx.__cue = {id, text: q.text, dur: q.dur, from: Math.max(i, 0), t0: frac == null ? null : Date.now() - Math.round(q.dur * frac) - (opt.pointDelay ?? 250)};
   const n0 = ctx.report?.length;
   // 대상을 못 찾는 등 조작 중의 오류는 fail 한 줄로 남기고 멈춘다(앞에서 이미 fail을 남긴 오류는 그대로 멈춘다).
   try { await fn(); } catch (e) { if (ctx.report && !ctx.report.slice(n0).some(r => r.fail)) rep({op: 'find', target: '대상', fail: true, why: String(e?.message ?? e).replace(/^page\.evaluate: (Error: )?/, '').split(String.fromCharCode(10))[0].slice(0, 300)}); throw e; }
   if (ctx.report && ctx.report.length === n0) bad({op: 'say', target: id}, '조작이 있는 큐인데 조작 기록이 없음 — labUi(ctx)의 c로 조작했는지 본다');
  }, opt);
 };
 return c;
}
// 한 큐 안의 다음 조작을 그 구절을 말하기 시작할 때 한다(고정 sleep 대신). 클릭 · 입력은 그 구절이 끝나기 약 250ms 전에 실행된다(gate = ctx.commitAt).
// 시각 계산은 ../ctrl.mjs cue()의 at과 같다(글자 비율 어림). 구절은 앞 구절보다 뒤에 있어야 한다. dry는 기다리지 않고 구절만 확인한다.
export async function atPhrase(ctx, phrase) {
 const q = ctx.__cue;
 if (!q || q.id !== ctx.cueId) throw Error('atPhrase는 labUi(ctx)가 감싼 ctx.say의 조작 안에서만 쓴다: ' + phrase);
 const i = q.text.indexOf(phrase, q.from);
 if (i < 0) { const why = q.text.includes(phrase) ? '앞 구절보다 앞에 있는 구절' : '큐 글에 없는 구절'; ctx.report?.push({cue: q.id, op: 'at', target: phrase, fail: true, why}); throw Error(q.id + ': ' + why + ' — ' + phrase); }
 q.from = i + phrase.length;
 if (ctx.rehearsal) return;
 if (q.t0 == null) throw Error(q.id + ': 첫 조작에 at이 없어 말 시점을 셀 수 없음 — ctx.say에 {at}을 준다');
 const L = q.text.length, w = q.t0 + Math.round(q.dur * Math.max(0, (i - 1) / L)) + 250 - Date.now();
 if (w > 0) await ctx.sleep(w);
 ctx.commitAt = q.t0 + Math.round(q.dur * (i + phrase.length) / L) - 250;
}
