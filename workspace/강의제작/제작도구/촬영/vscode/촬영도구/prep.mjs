// 녹화 브라우저의 웹 VS Code 화면을 학생 설치판처럼 맞추는 준비(촬영준비 길 4). 부르기: ./run.sh prep [랩 폴더 절대 경로]
// 웹 VS Code의 사용자 설정은 서버가 아니라 녹화 브라우저 프로필(config.json profile)의 저장소에 있다. 프로필을 새로 만들었거나 config.json settings를 고쳤을 때 돌린다.
// 하는 일: ① 폴더를 주면 그 폴더를 연다(주지 않으면 지금 열린 창). Restricted Mode면 폴더 신뢰를 준다 ② F1 → Preferences: Open User Settings (JSON)을 열어 지금 설정을 읽고, config.json settings의 값을 덮어쓴 JSON으로 바꿔 저장한다
//   (다른 키는 그대로 둔다. 주석이 든 설정처럼 JSON으로 읽히지 않으면 고치지 않고 멈춘다) ③ 저장한 글을 다시 읽어 견준다 ④ 창을 새로 고쳐 메뉴 줄 · 색 · 시작 화면을 재고, Screen Reader Optimized가 켜져 있으면 끈다
//   ⑤ Codex 패널이 새 프로필의 첫 안내(「Codex in your IDE」부터 쪽마다 Back · Next)를 띄우면 Next로 끝까지 넘겨 새 대화 화면(「Ask Codex anything」)으로 둔다. Codex 요청은 보내지 않는다.
// 돌려주는 것: {trusted: 이번에 신뢰를 줬는가, settings: 바뀐 키, codexIntro: 넘긴 안내 쪽 수, menubar, hamburger, restricted, theme, tabs, view}.
// 메뉴 줄이 펴지지 않았거나 색이 다르거나 Welcome 탭이 남았거나 Codex 새 대화 화면이 60초 안에 뜨지 않으면 멈춘다.
import {openPage, folderUrl, CFG, WORK, VIEW, NAV} from './page.mjs';
import {palette, focusedIn, trustFolder} from './segs/lab-common.mjs';

const want = Object.fromEntries(Object.entries(CFG.settings).map(([k, v]) => [k, typeof v === 'string' ? v.replace('{work}', WORK) : v]));
// 사용자 설정 편집기(웹 VS Code 1.143은 탭이 아니라 화면 위에 겹친 창으로 연다 — 그 문서 주소로 찾는다)와 그 글. 짧은 파일이라 모든 줄이 그려져 있고, 줄 번호와 그려진 줄 수가 다르면 멈춘다.
const SETTINGS = '[data-uri="vscode-userdata:/User/settings.json"]';
const editorBox = p => p.evaluate(sel => { const ed = [...document.querySelectorAll('.editor-instance')].find(e => e.querySelector(sel) && e.getBoundingClientRect().width > 0); const b = ed?.getBoundingClientRect(); return b ? {x: b.x + b.width / 2, y: b.y + b.height / 2} : null; }, SETTINGS);
const editorText = p => p.evaluate(sel => {
 const ed = [...document.querySelectorAll('.editor-instance')].find(e => e.querySelector(sel) && e.getBoundingClientRect().width > 0);
 const lines = [...ed.querySelectorAll('.view-lines .view-line')].sort((a, b) => a.getBoundingClientRect().y - b.getBoundingClientRect().y);
 const nums = [...ed.querySelectorAll('.margin-view-overlays .line-numbers')].map(e => Number(e.textContent)).filter(Boolean);
 return {text: lines.map(l => l.textContent.replaceAll(String.fromCharCode(160), ' ')).join(String.fromCharCode(10)), drawn: lines.length, last: Math.max(0, ...nums)};
}, SETTINGS);
const workbench = async p => { await p.waitForSelector('.monaco-workbench', {state: 'visible', timeout: 60000}); for (let k = 0; k < 20 && !(await p.evaluate(() => document.querySelectorAll('.statusbar-item').length)); k++) await p.waitForTimeout(1000); await p.waitForTimeout(3000); };

export async function prep(dir = '') {
 const {p, close} = await openPage(0);
 await p.cdp('Emulation.setDeviceMetricsOverride', {...VIEW, mobile: false});
 if (dir) await p.goto(await folderUrl(dir.replaceAll(String.fromCharCode(92), '/')), NAV);
 else if (!p.url().startsWith(CFG.server)) throw Error('녹화 브라우저에 웹 VS Code가 열려 있지 않음 — ./run.sh prep <랩 폴더 절대 경로> (촬영도구/prep.mjs)');
 await workbench(p);
 await p.keyboard.press('Escape');
 // 신뢰가 먼저다 — Restricted Mode에서 설정을 넣으면 「Do you trust the authors …」 창이 떠서 초점을 가져간다.
 const trusted = await trustFolder(p);
 if (trusted) await workbench(p);
 await palette(p, 'Preferences: Open User Settings (JSON)');
 let e = null; for (let k = 0; k < 30 && !(e = await editorBox(p)); k++) await p.waitForTimeout(200);
 if (!e) throw Error('사용자 설정(JSON) 편집기가 열리지 않음 (촬영도구/prep.mjs)');
 await p.mouse.click(e.x, e.y); await focusedIn(p, 'editor', '사용자 설정 읽기');
 const before = await editorText(p);
 if (before.last !== before.drawn) throw Error(`사용자 설정이 길어 화면에 다 그려지지 않음(줄 ${before.last}, 그려진 줄 ${before.drawn}) — 손으로 고친다 (촬영도구/prep.mjs)`);
 let old; try { old = before.text.trim() ? JSON.parse(before.text) : {}; } catch (err) { throw Error('지금 사용자 설정이 JSON으로 읽히지 않음(주석 · 끝 쉼표) — 고치지 않고 멈춤: ' + before.text.slice(0, 200)); }
 const changed = Object.keys(want).filter(k => JSON.stringify(old[k]) !== JSON.stringify(want[k]));
 if (changed.length) {
  // 한 줄로 넣는다 — 여러 줄을 넣으면 편집기가 줄마다 들여쓰기를 더하고 닫는 괄호를 하나 더 붙였다(문서 서식 명령은 「no formatter for 'jsonc'」 창을 띄울 때가 있어 쓰지 않는다).
  await p.keyboard.press('Control+a'); await p.keyboard.press('Backspace'); await p.keyboard.insertText(JSON.stringify({...old, ...want})); await p.waitForTimeout(500);
  const after = await editorText(p);
  if (JSON.stringify(JSON.parse(after.text)) !== JSON.stringify({...old, ...want})) throw Error('넣은 설정이 편집기 글과 다름 — 저장하지 않고 멈춤: ' + after.text.slice(0, 300));
  await focusedIn(p, 'editor', '사용자 설정 저장'); await p.keyboard.press('Control+s'); await p.waitForTimeout(1500);
  if (await p.evaluate(() => !!document.querySelector('.modal-editor-part .dirty, .tabs-container .tab.dirty'))) throw Error('사용자 설정이 저장되지 않음(고친 표시가 남음) (촬영도구/prep.mjs)');
 }
 // 저장했는지는 창을 새로 고친 뒤 설정이 화면에 먹었는지로 다시 판정한다(아래). 새로 고치면 겹친 설정 창도 닫힌다.
 await p.reload(NAV); await workbench(p);
 // 화면 읽기 프로그램 모드가 켜져 있으면 편집기 줄바꿈이 달라지고 상태 표시줄에 그 글이 남는다(촬영준비 길 3)
 const reader = () => p.evaluate(() => [...document.querySelectorAll('.statusbar-item')].some(e => e.innerText.includes('Screen Reader')));
 if (await reader()) { await palette(p, 'Toggle Screen Reader Accessibility Mode'); await p.waitForTimeout(1500); if (await reader()) throw Error('Screen Reader Optimized를 끄지 못함 (촬영도구/prep.mjs)'); }
 // Codex 첫 안내 넘기기. Codex 채팅은 웹뷰 안이라 화면 글 전체(p.text)로 읽고, 단추는 글로 찾아 누른다(p.clickText — 하나가 아니면 멈춘다).
 let codexIntro = 0;
 for (const t0 = Date.now(); ; await p.waitForTimeout(1000)) {
  const lines = (await p.text()).split(String.fromCharCode(10)).map(s => s.trim());
  if (lines.some(s => s.startsWith('Ask Codex anything'))) break;
  if (Date.now() - t0 > 60000) throw Error('Codex 새 대화 화면이 60초 안에 뜨지 않음 — 확장 · 엔진 · 로그인을 본다(촬영준비 길 2 · 4) (촬영도구/prep.mjs)');
  if (lines.includes('Back') && lines.includes('Next')) { if (++codexIntro > 8) throw Error('Codex 첫 안내가 Next 8번 뒤에도 끝나지 않음 (촬영도구/prep.mjs)'); await p.clickText('Next'); }
 }
 const out = await p.evaluate(() => ({
  menubar: [...document.querySelectorAll('.menubar .menubar-menu-button')].filter(e => e.getBoundingClientRect().width > 0).map(e => e.textContent.trim()),
  hamburger: !!document.querySelector('.menubar.compact'),
  restricted: [...document.querySelectorAll('.statusbar-item')].some(e => e.innerText.includes('Restricted Mode')),
  theme: [...document.querySelector('.monaco-workbench').classList].filter(c => /^vs/.test(c)).join(' '),
  tabs: [...document.querySelectorAll('.tabs-container .tab .label-name')].map(e => e.textContent),
  view: {w: innerWidth, h: innerHeight, dpr: devicePixelRatio},
 }));
 await close();
 const res = {trusted, settings: changed, codexIntro, ...out};
 const menus = ['File', 'Edit', 'Selection', 'View', 'Go', 'Run', 'Terminal', 'Help'];
 if (menus.some(m => !out.menubar.includes(m)) || out.hamburger || !out.theme.includes('vs-dark') || out.tabs.includes('Welcome') || out.restricted) throw Error('화면이 설정과 다름(메뉴 줄 · 색 · 시작 화면 · 폴더 신뢰): ' + JSON.stringify(res));
 return res;
}
