// 통합 2회차 06-2편 「온톨로지 설계」(큐 wo0101~wo1004)의 구간들(wo-*.mjs)이 함께 쓰는 것: 구간 차례(SEGS) · 부탁 글(대본에서 읽음) · 펜 그림 · 글상자 글 · 찾는 글 표(FIND · PICK) · 짚기 도구 · 녹화 밖 되돌리기 도구.
// 구간 표 · 녹화 차례 · 되돌리기 계획은 작업 폴더 판정/녹화모듈_06-2.md. 조작 층은 lab-common.mjs의 labUi(ctx). 06-1 모듈(wv-common.mjs)의 도구는 그 편 작업자가 고쳐 가는 중이라 쓰지 않고, 06-1 wv0109와 「같은 세 칸」인 펜 그림 STEPS만 그쪽 정의를 그대로 받는다.
// 한 구간은 한 페이지에서 돈다 — 웹 VS Code는 첫 페이지(PAGE 없음), 결과 화면(output/result.html)은 둘째 페이지(PAGE=1). 대상이 없거나 여럿이면 큐 id를 대며 멈춘다(건너뛰지 않는다).
// 녹화 답에 따라 달라지는 글(Codex 답의 낱말 · 고친 파일의 줄 · 후보 번호)은 맨 아래 FIND · PICK 표 한 곳에만 둔다. 지금 값은 완성본(ontology-lab-completed.zip)과 v59 학생 역 리허설로 맞춘 어림이고, 녹화한 답 · 파일을 보고 그 표만 고친다.
// 환경변수(모두 리허설 run.sh dry 전용 — 녹화에 주면 멈춘다): WO_NOSEND=1 = 부탁 글을 넣기까지 해 보고 보내지 않는다(입력칸을 비움, 한도를 쓰지 않음) · WO_TEST_LAB=<폴더> = 결과 화면 구간을 그 폴더의 결과 화면으로 시험.
// 녹화 전용: WO_SINCE=<보낸 시각 ms> = 요청을 보낸 뒤 멈춘 take를 잇는다(보내는 큐까지 건너뛰고 그 시각의 답을 기다린다 — 판정 문서 「요청 뒤에 멈췄을 때」).
import fs from 'node:fs';
import fsp from 'node:fs/promises';
import {labUi, atPhrase, em, LABS, PAUSE, codexEl, codexBoxes, codexView, codexScrollInto, codexFocus, codexSubmit, codexWait, codexDone} from './lab-common.mjs';
import {STEPS} from './wv-common.mjs';

export const TEST = process.env.WO_TEST_LAB ?? null;
export const LAB = (TEST ?? LABS.wo.dir).replace(/\\/g, '/');
export const SNAP = LABS.wo.dir.slice(0, LABS.wo.dir.lastIndexOf('/'));   // 사본 자리 = 촬영 폴더 옆 D:/HYD-Practice/wvp-<해시>/_wo-<구간>/
export const NOSEND = process.env.WO_NOSEND === '1';
export const RESUME = process.env.WO_SINCE ? Number(process.env.WO_SINCE) : null;
export const PROMPT = 'ontology-lab>';
export const RESULT = () => 'file:///' + LAB + '/output/result.html';
const who = ctx => ctx.cueId ?? '(큐 밖)';
const stop = (ctx, why) => { throw Error(who(ctx) + ': ' + why + ' (segs/wo-common.mjs)'); };
const rep = (ctx, o) => ctx.report?.push({cue: ctx.cueId, fail: false, ...o});

// ── 구간 차례: 이름 · 페이지 · 그 구간이 보내는 Codex 부탁(R번호). 되돌리기(wo-reset.mjs)가 앞 구간 · 사본을 이 표로 찾는다 ──
// 큐 나눔(판정 문서 「막힌 곳 ①」)을 대본에 넣은 뒤의 구간이다 — 나눔 전 큐 파일에는 wo0282 · wo0382~0385 · wo0484 · wo0485 · wo0582 · wo0681 · wo0881 · wo0981 · wo1081 · wo1082가 없다.
export const SEGS = [
 ['01', 0], ['02a', 0, 'R1'], ['02b', 0, 'R2'], ['02c', 0], ['02d', 1],
 ['03a', 0, 'R3'], ['03b', 0, 'R4'], ['03c', 0], ['03d', 1], ['03e', 0, 'R5'], ['03f', 0, 'R6'], ['03g', 0], ['03h', 1], ['03i', 0, 'R7'], ['03j', 0], ['03k', 1], ['03l', 0],
 ['04a', 0], ['04b', 1], ['04c', 0, 'R8'], ['04d', 0, 'R9'], ['04e', 0], ['04f', 1],
 ['05a', 0, 'R10'], ['05b', 0, 'R11'], ['05c', 0, 'R12'], ['05d', 0, 'R13'], ['05e', 0], ['05f', 1],
 ['06a', 0], ['06b', 1], ['06c', 0, 'R14'], ['06d', 0],
 ['07a', 0], ['07b', 1],
 ['08a', 0, 'R15'], ['08b', 0], ['08c', 1],
 ['09a', 0, 'R16'], ['09b', 0, 'R17'], ['09c', 0, 'R18'], ['09d', 0], ['09e', 1], ['09f', 0, 'R19'], ['09g', 0], ['09h', 1],
 ['10a', 0], ['10b', 1], ['10c', 0],
].map(([name, page, ask]) => ({name, page, ask: ask ?? null}));

// ── 결과 화면 제목(명령 → 화면 제목 앞머리, app/utils/actions.py COMMANDS) ──
export const TITLE = {sources: '원자료', expected: '기대 답', classes: '클래스와 식별자', properties: '속성과 자료형', relations: '관계와 카디널리티', names: '구성 요소 이름과 실물', quantities: '물리량과 센서', parts: '부품과 모델', query: '질문별 대조', check: '넣기 전 검증'};

// ── 부탁 글: 정본 대본의 조작 칸 「입력: ``…``」을 그대로 읽는다(대본이 한 곳의 주인 — 대본을 고치면 여기는 저절로 따라간다) ──
export const SCRIPT = 'D:/work/study/hyd-iot-edu-system/workspace/강의제작/산출물/통합반/실습/02회차/대본/06_2_실습_온톨로지설계.md';
const BODY = fs.readFileSync(SCRIPT, 'utf8').split('# 촬영 본문 끝')[0].split('\n');
export function askOf(id) {
 const r = BODY.find(l => l.startsWith('| ' + id + ' |'));
 if (!r) throw Error(id + ': 정본 대본에 이 큐의 표 줄이 없음 — 판정/녹화모듈_06-2.md 「막힌 곳 ①」의 큐 나눔을 대본에 넣었는지 본다 (segs/wo-common.mjs askOf)');
 const m = /입력: ``([\s\S]+?)``/.exec(r);
 if (!m) throw Error(id + ': 대본 조작 칸에 「입력: ``…``」이 없음 (segs/wo-common.mjs askOf)');
 return m[1];
}
// 녹화 답에 따라 채우는 부탁(대본이 「○는 녹화 답의 번호」라고 정한 자리)
export function ask17() {
 if (PICK.candidate == null) throw Error('wo0912: R16 답에서 고른 후보 번호가 없음 — segs/wo-common.mjs PICK.candidate를 녹화 답의 번호로 채운다');
 const t = askOf('wo0912');
 if (!t.includes('후보 ○번으로 할게.')) throw Error('wo0912: 대본 부탁 글에 「후보 ○번으로 할게.」가 없음 (segs/wo-common.mjs ask17)');
 return t.replace('후보 ○번으로 할게.', '후보 ' + PICK.candidate + '번으로 할게.' + (PICK.candidateExtra ? ' ' + PICK.candidateExtra : ''));
}

// ── 조작 층 받기: 리허설 전용 환경변수가 녹화에 섞이면 멈춘다. 페이지가 그 구간의 페이지인지 본다 ──
export async function ui(ctx, page) {
 if (!ctx.rehearsal && (TEST || NOSEND)) throw Error('WO_TEST_LAB · WO_NOSEND는 리허설(run.sh dry)에서만 준다 — 녹화하지 않고 멈춤 (segs/wo-common.mjs)');
 if (RESUME != null && !Number.isFinite(RESUME)) throw Error('WO_SINCE는 보낸 시각(ms 숫자) — 멈춘 take 폴더의 since.json 값 (segs/wo-common.mjs)');
 const web = ctx.p.url().startsWith('http');
 if (!TEST && (page === 1 ? web : !web)) throw Error((page === 1 ? '둘째 페이지(결과 화면) 구간 — PAGE=1 ./run.sh …로 돌린다' : '첫 페이지(웹 VS Code) 구간 — PAGE 없이 돌린다') + ' (segs/wo-common.mjs ui)');
 return labUi(ctx);
}
export const speechEnd = async ctx => { const q = ctx.__cue; if (!ctx.rehearsal && q?.t0 != null) { const w = q.t0 + q.dur - Date.now(); if (w > 0) await ctx.sleep(w); } };
// 리허설만: 지금 화면을 <리허설 폴더>/<이름>.jpg로 남긴다(강조가 대상에 그려졌는지 눈으로 본다). 녹화 때는 아무것도 하지 않는다.
export const shot = async (ctx, name) => { if (!ctx.rehearsal) return; await ctx.sleep(300); await ctx.serial(() => ctx.p.screenshot({path: ctx.out + '/' + name + '.jpg', type: 'jpeg', quality: 60})); };
const sayOnly = async (ctx, id) => { ctx.__cue = {id, text: '', from: 0, t0: Date.now(), dur: ctx.rehearsal ? 0 : JSON.parse(await fsp.readFile(ctx.audio + '/' + id + '.json', 'utf8')).duration_ms}; };
// 말만 하는 큐(조작 없음) — 다음 기다림 말이 이 말의 끝을 알 수 있게 「지금 큐」를 적어 둔다
export async function say(ctx, id) { await ctx.say(id); await sayOnly(ctx, id); }

// ── 탐색기 · 편집기 ──
const expanded = (c, ctx, name, level) => c.serial(() => ctx.p.evaluate(({name, level}) => [...document.querySelectorAll('.explorer-folders-view .monaco-list-row')].find(e => e.getAttribute('aria-level') === String(level) && e.querySelector('.label-name')?.textContent.trim() === name)?.getAttribute('aria-expanded') ?? null, {name, level}));
// 폴더가 접혀 있으면 눌러 편다(펴져 있으면 그대로 둔다 — 앞 구간 끝 상태가 무엇이든 같은 결과)
export async function unfold(c, ctx, name, level) {
 const now = await expanded(c, ctx, name, level);
 if (now === null) stop(ctx, '탐색기에 폴더 ' + name + '(깊이 ' + level + ')가 없음');
 if (now === 'true') return;
 const q = await c.explorerRow(name, level); await c.clickAt(q.x - 34, q.y);
 await ctx.waitFor('[...document.querySelectorAll(".explorer-folders-view .monaco-list-row")].find(e => e.getAttribute("aria-level") === "' + level + '" && e.querySelector(".label-name")?.textContent.trim() === ' + JSON.stringify(name) + ')?.getAttribute("aria-expanded") === "true"', 8000);
}
// 랩 폴더 기준 경로(data/sensors.csv · app/features/expected.csv · output/schema.json)의 파일을 탐색기에서 연다(행을 누른 뒤 Enter — 촬영준비 길 4)
export async function open(c, ctx, rel) {
 const parts = rel.split('/');
 for (let i = 0; i < parts.length - 1; i++) await unfold(c, ctx, parts[i], i + 1);
 const name = parts.at(-1), level = parts.length;
 await ctx.waitFor('[...document.querySelectorAll(".explorer-folders-view .monaco-list-row")].some(e => e.getAttribute("aria-level") === "' + level + '" && e.innerText.trim() === ' + JSON.stringify(name) + ')', 8000);
 const q = await c.explorerRow(name, level); await c.clickAt(q.x - 34, q.y); await c.key('Enter');
 await ctx.waitFor('document.querySelector(".tabs-container .tab.active .label-name")?.textContent === ' + JSON.stringify(name), 8000);
 await ctx.sleep(400);
}
// 열려 있는 탭을 앞에 둔다(탭을 누른다)
export async function tab(c, ctx, name) {
 await c.tab(name);
 await ctx.waitFor('document.querySelector(".tabs-container .tab.active .label-name")?.textContent === ' + JSON.stringify(name), 8000);
 await ctx.sleep(300);
}
// 앞에 있는 탭을 닫는다(탭의 닫기 단추)
export async function closeTab(c, ctx, name) {
 const on = await c.serial(() => ctx.p.evaluate(() => document.querySelector('.tabs-container .tab.active .label-name')?.textContent ?? null));
 if (on !== name) stop(ctx, '앞에 있는 탭이 ' + name + '이 아니라 ' + on);
 await c.clickSel('.tabs-container .tab.active .tab-actions .action-label');
 await ctx.waitFor('![...document.querySelectorAll(".tabs-container .tab .label-name")].some(e => e.textContent === ' + JSON.stringify(name) + ')', 8000);
}
export const label = name => ({sel: '.explorer-folders-view .monaco-list-row .label-name', text: name});   // 탐색기 행의 이름 글자
// 페이지 안에서 돈다: 앞에 보이는 편집기에서 편집기 줄 번호 n(~to)의 글자 자리. cell = CSV 칸 번호(0부터 — 따옴표 안의 쉼표는 칸을 나누지 않는다, 빈 칸이면 그 칸을 감싼 쉼표 둘),
// sub = 줄 안의 글 조각(pick = 몇 번째, 0부터), 둘 다 없으면 줄 전체. 꺾여 이어진 화면 줄(md)까지 한 줄로 본다. 편집기 오른쪽 밖으로 나간 글자는 보이는 데까지만.
function edLines({n, to, cell, sub, pick}) {
 const norm = s => s.replace(/\u00a0/g, ' ');
 const eds = [...document.querySelectorAll('.part.editor .editor-instance')].filter(e => e.getBoundingClientRect().width > 0);
 if (eds.length !== 1) throw Error('보이는 편집기가 ' + eds.length + '개');
 const ed = eds[0], A = ed.querySelector('.editor-scrollable').getBoundingClientRect();
 const nums = [...ed.querySelectorAll('.margin-view-overlays .line-numbers')].map(e => ({k: Number(e.textContent.trim()), t: e.getBoundingClientRect().top})).filter(x => x.k).sort((a, b) => a.t - b.t);
 const views = [...ed.querySelectorAll('.view-lines .view-line')].map(e => ({e, t: e.getBoundingClientRect().top})).sort((a, b) => a.t - b.t);
 const csv = t => { const out = []; let s = 0, q = false; for (let i = 0; i <= t.length; i++) { const ch = t[i]; if (ch === '"') q = !q; else if (i === t.length || (ch === ',' && !q)) { out.push([s, i]); s = i + 1; } } return out; };
 const rects = [];
 for (let k = n; k <= (to ?? n); k++) {
  const at = nums.findIndex(x => x.k === k);
  if (at < 0) throw Error('편집기에 ' + k + '행이 보이지 않음 — 먼저 그 행을 화면 안으로 들인다');
  const top = nums[at].t, next = nums[at + 1]?.t ?? Infinity;
  const els = views.filter(v => v.t >= top - 2 && v.t < next - 2).map(v => v.e);
  if (!els.length) throw Error(k + '행의 글 줄을 찾지 못함');
  const nodes = []; let all = '';
  for (const el of els) { const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT); for (let x; (x = w.nextNode());) { nodes.push([x, all.length]); all += norm(x.data); } }
  let s = 0, e = all.length;
  if (cell != null) { const cs = csv(all); if (cell >= cs.length) throw Error(k + '행에 ' + cell + '번째 칸이 없음(칸 ' + cs.length + '개)'); [s, e] = cs[cell]; if (s === e) { s = Math.max(0, s - 1); e = Math.min(all.length, e + 1); } }
  else if (sub != null) { const hits = []; for (let i = all.indexOf(sub); i >= 0; i = all.indexOf(sub, i + 1)) hits.push(i); if (hits[pick ?? 0] == null) throw Error(k + '행에 「' + sub + '」이 ' + hits.length + '번 — ' + (pick ?? 0) + '번째가 없음'); s = hits[pick ?? 0]; e = s + sub.length; }
  if (e <= s) continue;
  const pos = i => { const [x, o] = nodes.findLast(v => v[1] <= i); return [x, i - o]; };
  const g = document.createRange(), a = pos(s), b = pos(e - 1); g.setStart(a[0], a[1]); g.setEnd(b[0], b[1] + 1);
  const ls = [];
  for (const q of g.getClientRects()) { if (q.width <= 0 || q.height <= 0) continue; const m = q.top + q.height / 2, l = ls.find(l => m > l[1] && m < l[3]); if (l) { l[0] = Math.min(l[0], q.left); l[1] = Math.min(l[1], q.top); l[2] = Math.max(l[2], q.right); l[3] = Math.max(l[3], q.bottom); } else ls.push([q.left, q.top, q.right, q.bottom]); }
  for (const l of ls) { if (l[1] < A.top - 1 || l[3] > A.bottom + 1) throw Error(k + '행이 편집기 칸 밖으로 굴러가 있음'); const r = Math.min(l[2], A.right - 24); if (r > l[0]) rects.push([l[0], l[1], r - l[0], l[3] - l[1]]); }
 }
 if (!rects.length) throw Error(n + '행 — 편집기 안에 보이는 글자가 없음(오른쪽 밖이면 그 칸을 짚을 수 없다)');
 return {rects};
}
// 강조 대상: 편집기 줄 번호 n의 줄 · 칸 · 조각 → {rects}(띠는 줄마다, 테두리는 모두를 두르는 상자 하나)
export const ln = (c, ctx, n, o = {}) => c.serial(() => ctx.p.evaluate(edLines, {n, to: o.to ?? null, cell: o.cell ?? null, sub: o.sub ?? null, pick: o.pick ?? 0})).catch(e => stop(ctx, String(e?.message ?? e).replace(/^page\.evaluate: (Error: )?/, '').split('\n')[0]));
// 편집기에서 n~m행이 보이는 칸 안(n이 위에서 셋째 줄쯤)에 오게 굴린다. 이미 온전히 보이면 굴리지 않는다. 화살표를 편집기 빈 곳으로 먼저 옮긴다(휠은 화살표 아래 칸을 굴린다).
export async function reveal(c, ctx, n, m = n) {
 const look = () => c.serial(() => ctx.p.evaluate(() => {
  const ed = [...document.querySelectorAll('.part.editor .editor-instance')].find(e => e.getBoundingClientRect().width > 0);
  const A = ed.querySelector('.editor-scrollable').getBoundingClientRect();
  const nums = [...ed.querySelectorAll('.margin-view-overlays .line-numbers')].map(e => ({k: Number(e.textContent.trim()), b: e.getBoundingClientRect()})).filter(x => x.k && x.b.top >= A.top - 1 && x.b.bottom <= A.bottom + 1).sort((a, b) => a.k - b.k);
  return {first: nums[0]?.k ?? 1, last: nums.at(-1)?.k ?? 1, lh: nums.length > 1 ? (nums.at(-1).b.top - nums[0].b.top) / (nums.at(-1).k - nums[0].k) : 19, x: A.left + A.width * 0.62, y: A.top + A.height * 0.55};
 }));
 let v = await look(), moved = false;
 for (let k = 0; k < 14; k++) {
  if (n >= v.first && m <= v.last && (n > v.first || v.first === 1)) return;
  if (!moved) { await c.move(v.x, v.y); await c.gate(); await ctx.draw.end('굴리기'); moved = true; }   // 굴리면 그려 둔 강조가 글과 어긋나므로 먼저 지운다
  const dy = Math.max(-700, Math.min(700, (Math.max(1, n - 2) - v.first) * v.lh));
  await c.serial(() => ctx.p.mouse.wheel(0, dy)); await ctx.sleep(450);
  const w = await look(); if (w.first === v.first && w.last === v.last) break; v = w;
 }
 if (!(n >= v.first && m <= v.last)) stop(ctx, '편집기를 굴려도 ' + n + '~' + m + '행이 보이는 칸에 오지 않음');
}
// 편집기 줄을 짚는 한 걸음: 그 줄을 보이는 칸에 들이고 강조한다
export async function mark(c, ctx, n, o = {}) { await reveal(c, ctx, n, o.to ?? n); await c.emph(await ln(c, ctx, n, o), {shape: o.shape ?? 'band', keep: o.keep, point: o.point}); }
// 앞에 보이는 편집기의 데이터 줄(# 줄 · 칸 이름 줄 다음부터 끝까지) 번호 — Codex가 적은 줄을 셀 때
export const dataRows = async (rel) => { const t = (await fsp.readFile(LAB + '/' + rel, 'utf8')).replace(/\r/g, '').split('\n'); const head = t.findIndex(x => x.trim() && !x.startsWith('#')); return {head: head + 1, first: head + 2, last: t.length - (t.at(-1) === '' ? 1 : 0), lines: t}; };
// 파일에서 글이 starts로 시작하는 줄의 번호(편집기 줄 번호) — 하나가 아니면 멈춘다
export async function lineOf(ctx, rel, starts) {
 const t = (await fsp.readFile(LAB + '/' + rel, 'utf8')).replace(/\r/g, '').split('\n');
 const hit = t.map((x, i) => [x, i + 1]).filter(([x]) => x.startsWith(starts));
 if (hit.length !== 1) stop(ctx, rel + '에서 「' + starts + '」로 시작하는 줄이 ' + hit.length + '개 — FIND 표를 그 파일에 맞춘다');
 return hit[0][1];
}

// ── 터미널 ──
// 터미널 입력 줄에 초점을 준다(마지막 프롬프트 줄을 누른다). 터미널이 없으면 멈춘다.
export async function termFocus(c, ctx) {
 const z = () => c.serial(() => ctx.p.evaluate(() => { const a = document.activeElement; return !!a?.closest('.terminal-wrapper') && a.classList.contains('xterm-helper-textarea'); }));
 if (await z()) return;
 const q = await c.serial(() => ctx.p.evaluate(p => {
  const rows = document.querySelector('.terminal-wrapper .xterm-rows'); if (!rows || !rows.checkVisibility()) return null;
  const l = [...rows.children].filter(d => d.textContent.includes(p)).pop() ?? [...rows.children].filter(d => d.textContent.trim()).pop();
  const b = (l ?? rows).getBoundingClientRect(); return {x: Math.min(b.x + 520, b.right - 40), y: b.y + b.height / 2};
 }, PROMPT));
 if (!q) stop(ctx, '터미널이 열려 있지 않음 — 앞 구간 끝 상태를 본다');
 await c.clickAt(q.x, q.y);
 if (!(await z())) stop(ctx, '터미널을 눌러도 입력 초점이 오지 않음');
}
// 명령을 친다(typeKeys — 학생과 같은 글자, --no-open 없이). 친 뒤 Enter는 부르는 쪽이 atPhrase로 시점을 정해 c.key('Enter')로 한다.
export async function typeCmd(c, ctx, cmd) { await termFocus(c, ctx); await c.typeKeys(cmd); }
// Enter 뒤 그 명령이 끝나기를 기다린다: output/result.json이 새로 써지고, 터미널 마지막 줄이 다시 프롬프트다(옛 출력의 「결과:」 줄에 속지 않는다).
export async function cmdDone(ctx, since, timeout = 30000) {
 const t0 = Date.now();
 for (;;) {
  const m = await fsp.stat(LAB + '/output/result.json').then(s => s.mtimeMs, () => 0);
  const ready = m >= since - 50 && await ctx.serial(() => ctx.p.evaluate(p => { const rows = [...document.querySelectorAll('.terminal-wrapper .xterm-rows > div')].map(d => d.textContent.replace(/\u00a0/g, ' ').trimEnd()).filter(Boolean); return !!rows.length && rows.at(-1).endsWith(p); }, PROMPT));
  if (ready) return;
  if (Date.now() - t0 > timeout) stop(ctx, '명령이 ' + Math.round(timeout / 1000) + '초 안에 끝나지 않음(output/result.json · 프롬프트)');
  await ctx.sleep(150);
 }
}
// 명령 하나를 큐 안에서: phrase를 말할 때 치고, enter를 말할 때(없으면 바로) Enter, 끝나기를 기다린다. 돌려주는 값 = Enter 시각.
export async function command(c, ctx, cmd, phrase = null, enter = null) {
 if (phrase) await atPhrase(ctx, phrase);
 await typeCmd(c, ctx, cmd);
 if (enter) await atPhrase(ctx, enter);
 const t = Date.now(); await c.key('Enter'); await cmdDone(ctx, t);
 return t;
}
// 터미널에서 text가 든 마지막 줄(강조 대상 — 그 줄 글자만큼)
export const termRow = text => ({sel: '.terminal-wrapper .xterm-rows > div', has: text, pick: 'last', tight: true});

// ── 결과 화면(둘째 페이지) ──
// 구간 시작(녹화 전): 둘째 페이지에 이 랩의 결과 화면이 열려 있는지 보고 맨 위로 올린다. 학생 화면처럼 F5 앞의 옛 화면이다(새로 고침은 구간 안의 f5).
export async function resultStart(c, ctx, title) {
 const u = decodeURI(await c.serial(() => ctx.p.url()));   // 페이지 주소는 한글 등을 %로 바꿔 돌려준다
 if (u !== RESULT()) throw Error('둘째 페이지에 이 랩의 결과 화면(' + RESULT() + ')이 열려 있지 않음: ' + u.slice(0, 120) + ' — SEG=<구간> ./run.sh reset wo-reset.mjs (segs/wo-common.mjs)');
 if (title) { const t = await c.serial(() => ctx.p.title()); if (!t.startsWith(title)) throw Error('F5 앞의 결과 화면이 「' + title + '」가 아니라 「' + t + '」 — 앞 결과 화면 구간 끝 상태가 아님(SEG=<구간> ./run.sh reset wo-reset.mjs) (segs/wo-common.mjs)'); }
 await c.serial(() => ctx.p.evaluate(() => scrollTo(0, 0)));
}
// 학생의 F5: 둘째 페이지를 새로 읽는다(CDP로 보낸 F5 키는 file:// 문서를 다시 읽지 않았다 — 촬영준비 길 6). 새 문서에는 화살표 · 그림 층이 없으므로 같은 자리에 화살표를 다시 놓고 길잡이 그림을 다시 띄운다.
export async function f5(c, ctx, cmd, G = null) {
 const at = await c.serial(() => ctx.p.evaluate(() => { const r = document.getElementById('recording-pointer')?.getBoundingClientRect(); return r ? {x: r.x, y: r.y} : null; }));
 await c.gate(); await ctx.draw.end('F5');
 await c.serial(() => ctx.p.reload()); await ctx.sleep(500);
 await c.installPointer(at);
 rep(ctx, {op: 'key', target: 'F5(결과 화면 새로 고침)'});
 const t = await c.serial(() => ctx.p.title());
 if (!t.startsWith(TITLE[cmd])) stop(ctx, 'F5 뒤 결과 화면 제목이 「' + TITLE[cmd] + '」로 시작하지 않음: ' + t + ' — 앞 구간에서 python run.py ' + cmd + '이 돌았는지 본다');
 if (G) { G.shown = false; await guideShow(G, false); }
}
// 결과 화면에서 get()의 대상이 화면 안(위 margin ~ 아래 margin)에 오게 휠로 굴린다(아래 · 위 모두). 화살표는 옮기지 않는다(굴리는 것은 말하지 않는다).
export async function pageTo(c, ctx, get, top = 130, bottom = 900) {
 await c.gate();
 let last = null;
 for (let n = 0; n < 40; n++) {
  const q = await get(); const y = q.y ?? q.box?.[1] ?? q.rects?.[0]?.[1];
  if (y > top && y < bottom) return q;
  if (last !== null && Math.abs(y - last) < 1) { if (y > 60 && y < 1037 - 60) return q; break; }   // 문서 끝 · 맨 위라 더 굴러가지 않으면 화면 안에 있는 것으로 됐다
  last = y;
  await c.serial(() => ctx.p.mouse.wheel(0, y >= bottom ? 240 : -240)); await ctx.sleep(400);
 }
 stop(ctx, '결과 화면에서 대상이 화면 안에 오지 않음');
}
// 결과 화면 대상 재기(페이지 안 CSS px). 강조 대상 {box} · {rects}를 돌려준다.
const pageBox = (c, ctx, fn, arg, what) => c.serial(() => ctx.p.evaluate(fn, arg)).then(r => { if (r?.error) stop(ctx, what + ' — ' + r.error); return r; });
// 카드: 머리 글(b)이 title인 카드 하나의 요소들. part = 'head'(머리 글) | 'badge' | 'card'(카드 전체) | {li: '줄 이름 앞머리', chip: '조각 글'(없으면 그 줄 전체)}
export const card = (c, ctx, title, part = 'card', within = null) => pageBox(c, ctx, ({title, part, within}) => {
 const scope = within ? [...document.querySelectorAll('section')].filter(s => s.querySelector('h3')?.textContent.startsWith(within)) : [document];
 const cards = scope.flatMap(s => [...s.querySelectorAll('.card')]).filter(k => k.querySelector('.ch b')?.textContent.trim() === title);
 if (cards.length !== 1) return {error: '머리 글이 「' + title + '」인 카드가 ' + cards.length + '개' + (within ? '(「' + within + '」 칸 안)' : '')};
 const k = cards[0]; let el = k;
 if (part === 'head') el = k.querySelector('.ch b');
 else if (part === 'badge') el = k.querySelector('.ch .badge');
 else if (part?.li != null) {
  const name = l => (l.querySelector('span')?.textContent ?? l.textContent).trim(), all = [...k.querySelectorAll('li')];
  const same = all.filter(l => name(l) === part.li), li = same.length ? same : all.filter(l => name(l).startsWith(part.li));   // 같은 이름이 먼저(limit · limit_direction)
  if (li.length !== 1) return {error: '카드 「' + title + '」에서 「' + part.li + '」 줄이 ' + li.length + '개'};
  el = li[0];
  if (part.chip != null) { const ch = [...li[0].querySelectorAll('.chip')].filter(x => x.textContent.trim() === part.chip || x.textContent.includes(part.chip)); if (ch.length !== 1) return {error: '그 줄에 「' + part.chip + '」 조각이 ' + ch.length + '개'}; el = ch[0]; }
  else if (part.name) el = li[0].querySelector('span');
 }
 if (!el) return {error: '카드 「' + title + '」에 ' + JSON.stringify(part) + '이 없음'};
 const b = el.getBoundingClientRect(); return {box: [b.x, b.y, b.width, b.height], x: b.x + 20, y: b.y + b.height / 2};
}, {title, part, within}, '카드');
// 모으는 그림(gather)에서 가운데 칩 글이 mid로 시작하는 한 줄의 칸들(왼쪽 · 가운데 · 오른쪽) — 테두리 하나로 두른다. part = 'row' | 'left' | 'mid' | 'right' | {chip: '그 줄 왼쪽 · 오른쪽의 칩 글'}
export const gatherRow = (c, ctx, mid, part = 'row', within = null) => pageBox(c, ctx, ({mid, part, within}) => {
 const g = [...document.querySelectorAll('section')].filter(s => !within || s.querySelector('h3')?.textContent.startsWith(within)).flatMap(s => [...s.querySelectorAll('.gather')]);
 const own = m => [...(m.querySelector('.chip')?.childNodes ?? [])].filter(n => n.nodeType === 3).map(n => n.textContent).join('').trim();   // 칩의 제 글(앞의 색 점 · 뒤의 작은 글은 뺀다)
 const mids = g.flatMap(x => [...x.querySelectorAll(':scope > .gm')]).filter(m => own(m).startsWith(mid));
 const exact = mids.filter(m => own(m) === mid);
 const pick = exact.length === 1 ? exact : mids;
 if (pick.length !== 1) return {error: '가운데가 「' + mid + '」인 줄이 ' + pick.length + '개'};
 const m = pick[0], kids = [...m.parentElement.children], i = kids.indexOf(m);
 const left = kids[i - 2], right = kids[i + 2]?.classList.contains('gr') ? kids[i + 2] : null;
 const pickEl = part === 'left' ? [left] : part === 'mid' ? [m] : part === 'right' ? [right] : part?.chip ? [...[left, right].filter(Boolean).flatMap(x => [...x.querySelectorAll('.chip')]).filter(x => x.textContent.trim() === part.chip)] : [left, m, right].filter(Boolean);
 if (!pickEl.length || pickEl.some(x => !x)) return {error: '「' + mid + '」 줄에 ' + JSON.stringify(part) + '이 없음'};
 const rs = pickEl.map(x => { const b = x.getBoundingClientRect(); return [b.x, b.y, b.width, b.height]; });
 return {rects: rs, x: rs[0][0] + 20, y: rs[0][1] + rs[0][3] / 2};
}, {mid, part, within}, '모으는 그림');
// 대조 표(compare)에서 짝 칸(질문 · 물을 값 · 항목)이 keys인 줄의 칸. col = 0 견줌 · 1 짝 · 2 기대 · 3 실제. first = 첫째 대조 표만(질문 2 센서 값 표와 칸 머리가 같다)
export const cmpCell = (c, ctx, keys, col) => pageBox(c, ctx, ({keys, col}) => {
 const trs = [...document.querySelectorAll('.tbl.cmp tbody tr')].filter(r => { const ks = [...r.querySelectorAll('td.key span')].map(s => s.textContent.trim()); return ks.length === keys.length && keys.every((k, i) => ks[i] === k); });
 if (trs.length !== 1) return {error: '짝이 「' + keys.join(' | ') + '」인 대조 줄이 ' + trs.length + '개'};
 const b = trs[0].cells[col].getBoundingClientRect(); return {box: [b.x, b.y, b.width, b.height], x: b.x + 20, y: b.y + b.height / 2};
}, {keys, col}, '대조 표');
export const cmpHead = (c, ctx, name) => pageBox(c, ctx, name => {
 const th = [...document.querySelectorAll('.tbl.cmp')][0]?.querySelectorAll('th'); const h = th && [...th].filter(e => e.textContent.trim() === name);
 if (!h || h.length !== 1) return {error: '첫째 대조 표의 칸 머리 「' + name + '」이 ' + (h?.length ?? 0) + '개'};
 const b = h[0].getBoundingClientRect(); return {box: [b.x, b.y, b.width, b.height], x: b.x + 20, y: b.y + b.height / 2};
}, name, '대조 표 칸 머리');
// 접힌 표(자세히 보기) 안에서 칸들의 글이 cells인 줄의 n번째 칸
export const foldCell = (c, ctx, h3, cells, n) => pageBox(c, ctx, ({h3, cells, n}) => {
 const box = [...document.querySelectorAll('details.more .in')].find(x => x.querySelector('h3')?.textContent.startsWith(h3));
 if (!box) return {error: '자세히 보기 안에 「' + h3 + '」 표가 없음'};
 const trs = [...box.querySelectorAll('tbody tr')].filter(r => cells.every((t, i) => t == null || r.cells[i]?.textContent.trim() === t));
 if (trs.length !== 1) return {error: '「' + h3 + '」 표에서 ' + JSON.stringify(cells) + ' 줄이 ' + trs.length + '개'};
 const b = trs[0].cells[n].getBoundingClientRect(); if (!b.width) return {error: '그 칸이 접혀 있어 보이지 않음 — 자세히 보기를 먼저 편다'};
 return {box: [b.x, b.y, b.width, b.height], x: b.x + 20, y: b.y + b.height / 2};
}, {h3, cells, n}, '접힌 표');
// 결과 화면의 노드 그림: data-id가 id인 노드 · 화살표 글(시작 → 끝)
export const node = id => ({sel: 'g.n[data-id="' + id.replace(/"/g, '\\"') + '"]'});
export const edgeText = (a, b) => ({sel: 'g.ll[data-a="' + a + '"][data-b="' + b + '"] text'});
export const verdict = () => ({sel: '.verdict strong'});
export const verdictSub = () => ({sel: '.verdict span'});
export const h3 = text => ({sel: 'h3', starts: text});

// ── Codex 패널 ──
// 새 대화를 연다(오른쪽 위 New chat 단추) — 빈 새 대화가 뜰 때까지 기다린다
export async function newChat(c, ctx) {
 const b = await codexEl(c, ctx, {label: 'New chat'});
 if (NOSEND) { await c.move(b.x, b.y); rep(ctx, {op: 'click', target: 'New chat(WO_NOSEND — 누르지 않음: 앞 대화를 그대로 두어 녹화 첫 화면이 바뀌지 않게)'}); return; }
 await c.clickAt(b.x, b.y);
 const blank = t => t.includes('Ask Codex anything') && !t.includes('Worked for');
 for (let k = 0; !blank(await c.serial(() => ctx.p.text())); k++) { if (k >= 20) stop(ctx, '새 대화를 눌러도 빈 대화가 뜨지 않음'); await ctx.sleep(500); }
}
// 부탁 글을 입력칸에 한 번에 붙여 넣는다(영상 V-14 「긴 명령은 붙여넣는다」). 초점이 Codex에 없으면 넣지 않고 멈추고, 넣은 글이 입력칸에 보이는지 본다.
export async function paste(c, ctx, text) {
 await codexFocus(c, ctx);
 await c.gate(); await ctx.draw?.end('붙여넣기');
 await c.serial(() => ctx.p.keyboard.insertText(text));
 await ctx.sleep(300);
 const seen = await codexBoxes(c, ctx, '[contenteditable=true]', text.trim().slice(0, 12));
 if (seen.length !== 1) stop(ctx, '붙여 넣은 부탁 글이 입력칸에 보이지 않음');
 rep(ctx, {op: 'type', target: 'Codex 입력칸(붙여넣기)', text});
}
// 보낸다(phrase를 말할 때). 리허설에 WO_NOSEND=1을 주면 보내지 않고 입력칸을 비운다(한도를 쓰지 않는다). 보낸 시각을 take 폴더의 since.json에 적는다(멈췄을 때 WO_SINCE로 잇는다).
export async function send(c, ctx, phrase = null) {
 if (phrase) await atPhrase(ctx, phrase);
 if (NOSEND) {
  await c.gate();
  await c.serial(async () => { await ctx.p.keyboard.press('Control+a'); await ctx.p.keyboard.press('Backspace'); });
  rep(ctx, {op: 'key', target: '보내지 않음(WO_NOSEND) — 입력칸을 비움'});
  return null;
 }
 const since = await codexSubmit(c, ctx);
 await fsp.writeFile(ctx.out + '/since.json', JSON.stringify({since, cue: ctx.cueId}));
 return since;
}
// 답이 끝나기를 기다린다(rollout 기록의 task_complete — 촬영준비 길 9). 보내지 않은 리허설이면 기다리지 않는다. 리허설은 답을 take 폴더의 답.md로 남긴다.
export async function answer(c, ctx, since, timeout = 480000) {
 if (since == null) return {message: null, nosend: true};
 const r = await codexWait(ctx, since, timeout);
 if (ctx.rehearsal) { await c.serial(() => ctx.p.screenshot({path: ctx.out + '/답.png'})); await fsp.writeFile(ctx.out + '/답.md', r.message ?? ''); }
 return r;
}
// 기다림 말(영상 V-14) 하나: 앞 말이 끝나고 큐 사이 쉼까지 기다린 뒤, 답이 아직이면 말한다(fn = 그 말에 붙은 조작, 없으면 말만). 말했으면 true.
// 리허설은 말 길이가 0이라 늘 말하는 것으로 센다(조작 검사). lab-common의 waitLines는 조작을 받지 않아 여기 둔다.
export async function waitSay(c, ctx, since, id, fn = null, at = null) {
 const q = ctx.__cue; if (q && !ctx.rehearsal) { const w = q.t0 + q.dur + PAUSE.cue - Date.now(); if (w > 0) await ctx.sleep(w); }
 if (!ctx.rehearsal && since != null && (await codexDone(since)).done) return false;
 if (fn) await ctx.say(id, fn, {gap: 0, at}); else { await ctx.say(id, null, {gap: 0}); await sayOnly(ctx, id); }
 return true;
}
// Codex 답 안의 요소(FIND 표의 [CSS, 든 글, 'last'?]) — 정확히 하나(last면 아래쪽 마지막 것)여야 한다. 상자 {x, y, w, h}(바깥 문서 CSS px).
export async function cx(c, ctx, key) {
 const spec = FIND[key]; if (!spec) stop(ctx, 'FIND 표에 「' + key + '」이 없음');
 const [css, has, last] = spec, l = await codexBoxes(c, ctx, css, has);
 if (!l.length || (l.length > 1 && last !== 'last')) stop(ctx, 'Codex 답에서 「' + has + '」이 든 ' + css + '이 ' + l.length + '개 — 녹화한 답을 보고 FIND.' + key + '를 고친다');
 return last === 'last' ? l.at(-1) : l[0];
}
export async function cxAll(c, ctx, key) {
 const [css, has] = FIND[key] ?? stop(ctx, 'FIND 표에 「' + key + '」이 없음'), l = await codexBoxes(c, ctx, css, has);
 if (!l.length) stop(ctx, 'Codex 답에서 「' + has + '」이 든 ' + css + '이 없음 — 녹화한 답을 보고 FIND.' + key + '를 고친다');
 return l;
}
// 그 요소가 답의 보이는 칸 안(위에서 frac 높이쯤)에 오게 굴리고 상자를 돌려준다
export const cxIn = (c, ctx, key, frac = 0.3) => codexScrollInto(c, ctx, () => cx(c, ctx, key), frac);
// 답 안 요소 강조 한 걸음
export async function cxMark(c, ctx, key, shape = 'band', o = {}) { const b = o.scroll === false ? await cx(c, ctx, key) : await cxIn(c, ctx, key, o.frac ?? 0.3); await c.emph(em.box(b), {shape, keep: o.keep, point: o.point}); return b; }
// key의 요소가 여럿인 덩어리(답 표의 줄들): 첫 것을 보이는 칸에 들인 뒤, 보이는 것을 모두 함께 짚는다
export async function cxRows(c, ctx, key, shape = 'band') {
 await codexScrollInto(c, ctx, async () => (await cxAll(c, ctx, key))[0], 0.2);
 const v = await codexView(c, ctx), l = (await cxAll(c, ctx, key)).filter(b => b.y >= v.top && b.y + b.h <= v.bottom);
 if (!l.length) stop(ctx, 'Codex 답에서 FIND.' + key + '의 요소가 보이는 칸에 없음');
 for (const [i, b] of l.entries()) await c.emph(em.box(b), {shape, keep: i > 0, point: i === 0});
}
// 「답으로 돌아온다」: Codex 답 칸의 빈 곳으로 화살표를 옮긴다
export async function toAnswer(c, ctx) { const v = await codexView(c, ctx); await c.move(v.x + 120, v.top + (v.bottom - v.top) * 0.5); }

// ── 화면 위 그림: 길잡이(작은 다섯 칸 그림 + 세 역량 질문 + 남은 일) · 큰 그림들 · 글상자 ──
// 펜 그림은 한 번에 하나, 글상자도 하나다(draw.mjs). 길잡이는 펜 그림이라, 큰 그림을 그리는 큐에서는 길잡이를 걷고 그 큰 그림이 끝나면 다시 띄운다.
// 구간이 끝날 때 펜 그림 · 글상자가 떠 있으면 녹화가 멈추므로(ctrl.mjs) 구간 끝에서 걷고, 그 걷는 모습은 합성 때 잘라 낸다(seamOut이 돌려주는 cut = 걷기 직전 시각 → encode.py <take>:<cut>). 다음 구간은 녹화 전에 같은 그림을 다시 띄운다(seamIn).
const MINI = ['①\n질문', '②\n낱말', '③\n표', '④\n검증', '⑤\n묻기'];
const QUESTION = ['① 구성 요소마다 어떤 센서가 붙고,\n    그 자리에 어떤 장치(일련번호)가 달렸나', '② 같은 물리량을 재는 센서는 어느 것이고\n    단위 · 정상값 · 한계는', '③ 부품을 어느 설비가 함께 쓰나\n    — 예전 품번 · 다른 표기로 물어도'];
// where = 'vs'(웹 VS Code — 탐색기 아래 빈 곳) | 'res'(결과 화면 — 오른쪽 위 머리 옆). 좌표는 프레임 px(1920×1080) — 리허설 프레임으로 자리를 맞춘다(판정 문서 「미검증」).
export function guideDef(where) {
 if (where === 'vs') {
  const x0 = 68, y0 = 730, w = 60, h = 44, step = 70;   // 판 맨 위 690 — output · data · features를 다 펼친 탐색기 줄(약 690까지) 아래
  return {id: '길잡이', board: [56, 690, 366, 292], items: [
   ...MINI.map((t, i) => ({id: 'm' + (i + 1), kind: 'box', at: [x0 + i * step, y0, w, h], text: t, size: 0.42})),
   {id: 'mb', kind: 'arrow', from: 'm5', to: 'm2', route: 'under', drop: 12},
   {id: 'mbT', kind: 'text', at: [232, 791], text: '막히면 고친다', size: 0.42},
   {id: 'exp', kind: 'arrow', from: 'm1', to: 'm5', route: 'over', drop: 12},
   {id: 'expT', kind: 'text', at: [68, 694], text: '기대 답 — 먼저 적어 둔다', size: 0.42, color: 'red'},
   ...QUESTION.map((t, i) => ({id: 'q' + (i + 1), kind: 'text', at: [68, 816 + i * 50], text: t, size: 0.46})),
   {id: 'todo', kind: 'text', at: [68, 958], text: '남은 일 — 겹친 식별자 1곳', size: 0.5, color: 'red'},
   {id: 'dec5', kind: 'text', at: [68, 958], text: 'decisions.csv 5행 — 같은 물리량의 범위', size: 0.46, color: 'red'},
  ]};
 }
 if (where === 'res') {
  const x0 = 1096, y0 = 30, w = 108, h = 40, step = 128;
  return {id: '길잡이', board: [1080, 14, 660, 120], items: [
   ...MINI.map((t, i) => ({id: 'm' + (i + 1), kind: 'box', at: [x0 + i * step, y0, w, h], text: t.replace('\n', ' '), size: 0.45})),
   {id: 'mb', kind: 'arrow', from: 'm5', to: 'm2', route: 'under', drop: 10},
   {id: 'mbT', kind: 'text', at: [1300, 88], text: '막히면 고친다', size: 0.42},
   {id: 'todo', kind: 'text', at: [1096, 108], text: '남은 일 — 겹친 식별자 1곳', size: 0.5, color: 'red'},
  ]};
 }
 throw Error('길잡이 자리는 vs | res — ' + where);
}
const GUIDE_BASE = ['m1', 'm2', 'm3', 'm4', 'm5', 'mb', 'mbT'];
// 녹화 전(ctx.begin 앞): 앞 구간 끝과 같은 길잡이를 띄운다(긋는 움직임 없이). items = 더 띄울 칸(q1~q3 · exp · expT · todo), ring = 「지금 여기」 동그라미 칸. 조작 기록에는 남기지 않는다(큐 밖).
// 돌려주는 G = {where, items, ring, g(큐 안 조작용 — 조작 기록에 남는다), shown}.
export async function guideIn(c, ctx, where, {items = [], ring = null} = {}) {
 const def = guideDef(where), base = ctx.draw.pen(def, (x, y) => c.move(x, y));
 const keep = items.filter(i => def.items.some(d => d.id === i));
 await base.show(...GUIDE_BASE, ...keep); if (ring) await base.ring(ring);
 return {where, items: keep, ring, def, g: c.pen(def), shown: true, ctx};
}
// 큐 안: 길잡이를 걷고(큰 그림 앞) · 다시 띄우고(같은 칸 · 같은 동그라미) · 칸을 더하고 · 지운다
export async function guideHide(G) { if (G.shown) { await G.g.hide(); G.shown = false; } }
export async function guideShow(G, ring = true) { if (G.shown) return; await G.g.show(...GUIDE_BASE, ...G.items); G.shown = true; if (ring && G.ring) await G.g.ring(G.ring); }
export async function guideRing(G, id) { G.ring = id; await G.g.ring(id); }
export async function guideAdd(G, ...ids) { const ok = ids.filter(i => G.def.items.some(d => d.id === i)); await G.g.draw(...ok); G.items.push(...ok.filter(i => !G.items.includes(i))); }
export async function guideErase(G, ...ids) { await G.g.erase(...ids); G.items = G.items.filter(i => !ids.includes(i)); }
// 구간 끝: 마지막 말이 끝나고 꼬리(400ms)를 둔 뒤 남은 강조 · 길잡이 · 다른 펜 그림 · 글상자를 걷는다. 돌려주는 값 = 합성 때 이 take를 자를 ms(걷기 직전 — encode.py <take>:<cut>).
// 다음 구간이 녹화 전에 같은 그림을 다시 띄우므로, 잘라 낸 합본에서는 그림이 이음새를 넘어 그대로 떠 있다.
export async function seamOut(c, ctx, G = null, {note = false, figs = []} = {}) {
 await speechEnd(ctx); if (!ctx.rehearsal) await ctx.sleep(PAUSE.tail);
 const marks = ctx.draw.marks.filter(h => h.end == null), n0 = ctx.draw.log.length;
 await c.clearEmph();
 for (const f of figs) await f.hide();
 if (G?.shown) await guideHide(G);
 if (note) await c.note(null);
 const times = [...marks.map(h => h.end), ...ctx.draw.log.slice(n0).map(l => l.time)].filter(t => t != null);
 return times.length ? Math.max(0, Math.round(Math.min(...times) - 40)) : null;
}
export const Q = ['q1', 'q2', 'q3'], QE = ['q1', 'q2', 'q3', 'exp', 'expT'];
// 첫 페이지 구간의 끝 화면(탭 · 앞 탭 · 편집기 첫 줄 · 펼친 폴더 · 터미널 · 마지막 명령)을 <work>/_wo/<구간>.end.json에 적는다 — 다음 구간을 다시 찍을 때 wo-reset.mjs가 이 화면으로 되돌린다.
// 모듈이 끝까지 돈 take만 적는다(멈춘 take는 적지 않는다). 리허설 · 녹화 모두 적고, 나중에 적은 것이 이긴다.
export async function keepEnd(c, ctx, seg) {
 const s = await c.serial(() => ctx.p.evaluate(p => {
  const tabs = [...document.querySelectorAll('.tabs-container .tab .label-name')].map(e => e.textContent);
  const active = document.querySelector('.tabs-container .tab.active .label-name')?.textContent ?? null;
  const ed = [...document.querySelectorAll('.part.editor .editor-instance')].find(e => e.getBoundingClientRect().width > 0);
  let top = null;
  if (ed) { const A = ed.querySelector('.editor-scrollable').getBoundingClientRect(); top = [...ed.querySelectorAll('.margin-view-overlays .line-numbers')].map(e => ({k: Number(e.textContent.trim()), t: e.getBoundingClientRect().top})).filter(x => x.k && x.t >= A.top - 1).sort((a, b) => a.t - b.t)[0]?.k ?? null; }
  const path = [], open = [];
  for (const e of document.querySelectorAll('.explorer-folders-view .monaco-list-row')) { const l = Number(e.getAttribute('aria-level')); path.length = l - 1; path[l - 1] = e.querySelector('.label-name')?.textContent.trim(); if (e.getAttribute('aria-expanded') === 'true') open.push(path.slice(0, l).join('/')); }
  const term = !!document.querySelector('.terminal-wrapper')?.checkVisibility();
  const cmd = [...document.querySelectorAll('.terminal-wrapper .xterm-rows > div')].map(d => { const l = d.textContent.replace(/ /g, ' '), i = l.indexOf(p); return i >= 0 ? l.slice(i + p.length).trim() : ''; }).filter(Boolean).pop() ?? null;
  return {tabs, active, top, open, term, cmd};
 }, PROMPT));
 const dir = ctx.out.replace(/\\/g, '/').replace(/\/[^/]+$/, '') + '/_wo';
 await fsp.mkdir(dir, {recursive: true});
 await fsp.writeFile(dir + '/' + seg + '.end.json', JSON.stringify({...s, take: ctx.out.replace(/\\/g, '/').split('/').pop(), rehearsal: !!ctx.rehearsal, at: new Date().toISOString()}, null, 1));
}
// 파일에서 parts가 모두 든 줄의 번호(편집기 줄 번호) — 하나가 아니면 멈춘다(Codex가 적은 줄을 찾을 때)
export async function lineHas(ctx, rel, ...parts) {
 const t = (await fsp.readFile(LAB + '/' + rel, 'utf8')).replace(/\r/g, '').split('\n');
 const hit = t.map((x, i) => [x, i + 1]).filter(([x]) => !x.startsWith('#') && parts.every(p => x.includes(p)));
 if (hit.length !== 1) stop(ctx, rel + '에서 「' + parts.join('」 · 「') + '」이 든 줄이 ' + hit.length + '개 — PICK 표를 Codex가 적은 파일에 맞춘다');
 return hit[0][1];
}
export async function linesHas(ctx, rel, pred) { const t = (await fsp.readFile(LAB + '/' + rel, 'utf8')).replace(/\r/g, '').split('\n'); return t.map((x, i) => [x, i + 1]).filter(([x]) => !x.startsWith('#') && pred(x)).map(([, n]) => n); }
// 줄 번호 목록을 차례로 짚는다(첫 줄만 화살표를 옮기고 나머지는 함께 둔다). 보이는 칸을 넘는 목록이면 굴리는 순간 앞 강조가 지워진다.
export async function markAll(c, ctx, ns, o = {}) { for (const [i, n] of ns.entries()) await mark(c, ctx, n, {...o, keep: i > 0 || o.keep, point: i === 0 && o.point !== false}); }
// 앞에 보이는 편집기에서 보이는 줄 전체(흐린 띠 자리 — 그림 층에는 띠가 하나뿐이다)
export async function visibleLines(c, ctx) {
 const r = await c.serial(() => ctx.p.evaluate(() => { const ed = [...document.querySelectorAll('.part.editor .editor-instance')].find(e => e.getBoundingClientRect().width > 0); const A = ed.querySelector('.editor-scrollable').getBoundingClientRect(); const ns = [...ed.querySelectorAll('.margin-view-overlays .line-numbers')].map(e => ({k: Number(e.textContent.trim()), t: e.getBoundingClientRect().top, b: e.getBoundingClientRect().bottom})).filter(x => x.k && x.t >= A.top - 1 && x.b <= A.bottom + 1).sort((a, b) => a.k - b.k); return [ns[0]?.k, ns.at(-1)?.k]; }));
 return r;
}
// 대조 표에서 견줌이 state(다름 · 같음)인 줄 — 하나가 아니면 멈춘다. col = 칸 번호
export const cmpState = (c, ctx, state, col) => pageBox(c, ctx, ({state, col}) => {
 const trs = [...document.querySelectorAll('.tbl.cmp tbody tr')].filter(r => r.dataset.st === state);
 if (trs.length !== 1) return {error: '견줌이 「' + state + '」인 대조 줄이 ' + trs.length + '개'};
 const b = trs[0].cells[col].getBoundingClientRect(); return {box: [b.x, b.y, b.width, b.height], x: b.x + 20, y: b.y + b.height / 2};
}, {state, col}, '대조 표');
// 대조 표에서 짝의 첫 조각(질문 번호)이 qs에 드는 보이는 줄들(흐린 띠 자리)
// all = true면 화면 밖 줄도 돌려준다(굴려 들일 자리를 잴 때) — 강조에는 보이는 줄만 쓴다
export const cmpRows = (c, ctx, qs, all = false) => pageBox(c, ctx, ({qs, all}) => {
 const rs = [...document.querySelectorAll('.tbl.cmp')][0].querySelectorAll('tbody tr');
 const out = [...rs].filter(r => qs.includes(r.querySelector('td.key span')?.textContent.trim())).map(r => r.getBoundingClientRect()).filter(b => all || (b.top > 0 && b.bottom < innerHeight - 4)).map(b => [b.x, b.y, b.width, b.height]);
 if (!out.length) return {error: '질문 ' + qs.join(' · ') + '의 대조 줄이 ' + (all ? '없음' : '화면에 없음')};
 return {rects: out, x: out[0][0] + 20, y: out[0][1] + out[0][3] / 2};
}, {qs, all}, '대조 표');
// 결과 화면 h3 제목이 text로 시작하는 칸의 표(tbody)에서 보이는 줄들 · n번째 칸들
export const tableRows = (c, ctx, text, n = null) => pageBox(c, ctx, ({text, n}) => {
 const s = [...document.querySelectorAll('section')].find(x => x.querySelector('h3')?.textContent.startsWith(text));
 if (!s) return {error: '「' + text + '」 칸이 없음'};
 const out = [...s.querySelectorAll('tbody tr')].map(r => (n == null ? r : r.cells[n]).getBoundingClientRect()).map(b => [b.x, b.y, b.width, b.height]);
 if (!out.length) return {error: '「' + text + '」 표에 줄이 없음'};
 return {rects: out, x: out[0][0] + 20, y: out[0][1] + out[0][3] / 2};
}, {text, n}, '결과 화면 표');
// 녹화 전: 앞 구간 끝에 떠 있던 글상자를 다시 띄운다(큐 밖)
export async function noteIn(ctx, key) { await ctx.draw.note(NOTE[key].lines, {title: NOTE[key].title, at: NOTE[key].at}); }
export const note = (c, key, lines = null) => c.note(lines ?? NOTE[key].lines, {title: NOTE[key].title, at: NOTE[key].at});

// 펜 그림 정의(프레임 px). 06-1 wv0109의 세 칸(STEPS)은 그 편의 정의를 그대로 쓰고 이 편의 글만 더한다.
for (const id of ['s1', 's2', 's3', 'a12', 'a23']) if (!STEPS.items.some(i => i.id === id)) throw Error('wv-common.mjs STEPS에 「' + id + '」이 없음 — 06-1 wv0109와 같은 세 칸을 쓰는 이 편(wo0101 · wo1004)을 맞춘다 (segs/wo-common.mjs)');
export const STEPS2 = {...STEPS, items: [...STEPS.items,
 {id: 'goal', kind: 'text', at: [210, 346], text: '목표 — 보전팀이 물으면 바로 답이 나오는 지식', color: 'red'},
 {id: 'ok1', kind: 'text', at: [574, 436], text: '✓', size: 1.4, color: 'red'},
 {id: 'ok2', kind: 'text', at: [1114, 436], text: '✓', size: 1.4, color: 'red'},
]};
const FX = [160, 492, 824, 1156, 1488];
// 설계 흐름 다섯 칸(wo0102 · wo0103 · wo1002) — 판은 화면 가운데
export const FLOW = {id: '설계 흐름', board: [120, 186, 1680, 480], items: [
 {id: 'f1', kind: 'box', at: [FX[0], 330, 280, 110], text: '① 역량 질문'},
 {id: 'f2', kind: 'box', at: [FX[1], 330, 280, 110], text: '② 낱말을\n클래스·속성·관계로', size: 0.82},
 {id: 'f3', kind: 'box', at: [FX[2], 330, 280, 110], text: '③ 표에 적기'},
 {id: 'f4', kind: 'box', at: [FX[3], 330, 280, 110], text: '④ 넣기 전 검증'},
 {id: 'f5', kind: 'box', at: [FX[4], 330, 280, 110], text: '⑤ 넣어서 물어보기', size: 0.92},
 {id: 'a12', kind: 'arrow', from: 'f1', to: 'f2'}, {id: 'a23', kind: 'arrow', from: 'f2', to: 'f3'}, {id: 'a34', kind: 'arrow', from: 'f3', to: 'f4'}, {id: 'a45', kind: 'arrow', from: 'f4', to: 'f5'},
 {id: 'back', kind: 'arrow', from: 'f5', to: 'f2', route: 'over', drop: 70},
 {id: 'backT', kind: 'text', at: [860, 204], text: '막히면 고친다', color: 'red'},
 {id: 'fileT', kind: 'text', at: [1500, 462], text: '먼저 파일로 확인', size: 0.85, color: 'red'},
 {id: 'pump', kind: 'text', at: [500, 462], text: '펌프 — 자리와 실물', size: 0.8},
 {id: 'temp', kind: 'text', at: [500, 506], text: '온도 — 재는 곳마다', size: 0.8},
]};
// wo0321: 가운데로 키운 질문 글상자 옆(아래)에 켜는 가르는 기준 석 줄 — 글상자는 한 번에 하나라 이 석 줄은 펜 그림의 글로 띄운다
export const SORT = {id: '가르는 기준', board: [440, 520, 620, 170], items: [
 {id: 't1', kind: 'text', at: [470, 534], text: '따로 가리킬 대상 → 클래스', size: 0.9},
 {id: 't2', kind: 'text', at: [470, 584], text: '대상을 설명하는 값 → 속성', size: 0.9},
 {id: 't3', kind: 'text', at: [470, 634], text: '두 대상을 잇는 말 → 관계', size: 0.9},
]};
// wo0381: 물리량을 속성으로 둘 때 · 클래스로 세울 때 — 판은 편집기 위(Codex 답 칸은 가리지 않는다)
export const PANELS = {id: '물리량 두 길', board: [440, 216, 896, 600], items: [
 {id: 'lt', kind: 'text', at: [468, 232], text: '속성으로 두면', size: 0.9},
 {id: 'l1', kind: 'box', at: [470, 300, 380, 64], text: '센서 — 「유온」', size: 0.85},
 {id: 'l2', kind: 'box', at: [470, 390, 380, 64], text: '센서 — 「오일 온도」', size: 0.85},
 {id: 'l3', kind: 'box', at: [470, 480, 380, 64], text: '센서 — 「유온」', size: 0.85},
 {id: 'l4', kind: 'box', at: [470, 570, 380, 64], text: '센서 — 「유온」', size: 0.85},
 {id: 'rt', kind: 'text', at: [900, 232], text: '클래스로 세우면', size: 0.9},
 {id: 'q', kind: 'box', at: [1046, 470, 150, 70], text: '유온'},
 {id: 'r1', kind: 'box', at: [912, 300, 130, 56], text: '센서', size: 0.85},
 {id: 'r2', kind: 'box', at: [1196, 300, 130, 56], text: '센서', size: 0.85},
 {id: 'r3', kind: 'box', at: [912, 660, 130, 56], text: '센서', size: 0.85},
 {id: 'r4', kind: 'box', at: [1196, 660, 130, 56], text: '센서', size: 0.85},
 {id: 'm1', kind: 'arrow', from: 'r1', to: 'q'}, {id: 'm2', kind: 'arrow', from: 'r2', to: 'q'}, {id: 'm3', kind: 'arrow', from: 'r3', to: 'q'}, {id: 'm4', kind: 'arrow', from: 'r4', to: 'q'},
 {id: 'mt', kind: 'text', at: [1212, 420], text: '잰다', size: 0.8, color: 'red'},
]};
// wo0403 · wo0404: 펌프 자리와 그 자리를 거쳐 간 펌프 두 대(고르기 전의 사실만) · 두 길(글로만) — 판은 편집기 위
export const SEAT = {id: '펌프 자리', board: [440, 196, 896, 640], items: [
 {id: 'seat', kind: 'box', at: [500, 250, 360, 84], text: '펌프가 놓이는 자리'},
 {id: 's1', kind: 'box', at: [980, 228, 300, 56], text: '압력 센서 PS1', size: 0.85},
 {id: 's2', kind: 'box', at: [980, 304, 300, 56], text: '유량 센서 FS1', size: 0.85},
 {id: 'as1', kind: 'arrow', from: 'seat', to: 's1'}, {id: 'as2', kind: 'arrow', from: 'seat', to: 's2'},
 {id: 'line', kind: 'text', at: [470, 410], text: '──── 시간 ───────────────────────▶', size: 0.85},
 {id: 'old', kind: 'box', at: [490, 470, 360, 90], text: 'KP-1902-551\n3월 11일까지', size: 0.85},
 {id: 'oldT', kind: 'text', at: [500, 572], text: '달려 있던 때 · 떼어 냄', size: 0.75, color: 'red'},
 {id: 'now', kind: 'box', at: [910, 470, 360, 90], text: 'KP-2603-114\n3월 11일부터', size: 0.85},
 {id: 'nowT', kind: 'text', at: [920, 572], text: '달려 있는 때 · 지금', size: 0.75, color: 'red'},
 {id: 'p1', kind: 'text', at: [470, 664], text: '길 1 — 일련번호를 속성으로(옛 펌프 줄은 뺌)', size: 0.85},
 {id: 'p2', kind: 'text', at: [470, 724], text: '길 2 — 실물을 클래스로(펌프마다 따로)', size: 0.85},
]};
// 글상자(대본 조작 칸의 글 그대로 — 한 줄이 넓으면 둘로 나눴다). at = 왼쪽 위 프레임 px — 기본 자리(오른쪽 위)는 Codex 답 칸을 가린다.
// 편집기 줄을 짚는 동안 띄우는 글상자는 터미널 칸(y 830~)에 둔다(편집기 줄을 가리지 않게 — 그 큐에서 터미널은 짚지 않는다). 결과 화면 글상자는 짚는 결론 줄을 가리지 않는 자리.
export const NOTE = {
 q3: {lines: ['① 구성 요소마다 어떤 센서가 붙고, 그 자리에 어떤 장치(일련번호)가 달렸나', '② 같은 물리량을 재는 센서는 어느 것이고 단위 · 정상값 · 한계는', '③ 부품을 어느 설비가 함께 쓰나 — 예전 품번 · 다른 표기로 물어도'], at: [450, 470]},
 q1: {lines: ['① 구성 요소마다 어떤 센서가 붙고, 그 자리에 어떤 장치(일련번호)가 달렸나'], at: [200, 880]},
 qBig: {lines: ['① 구성 요소마다 어떤 센서가 붙고,', '    그 자리에 어떤 장치(일련번호)가 달렸나', '② 같은 물리량을 재는 센서는 어느 것이고', '    단위 · 정상값 · 한계는', '③ 부품을 어느 설비가 함께 쓰나', '    — 예전 품번 · 다른 표기로 물어도'], at: [450, 150]},
 more: {title: '더 물은 것', lines: ['물리량: 속성으로만 둘 때 · 클래스로 세울 때, 질문 ②의 답이 몇 묶음?'], at: [450, 560]},
 more2: {title: '더 물은 것', lines: ['물리량: 속성으로만 둘 때 · 클래스로 세울 때, 질문 ②의 답이 몇 묶음?', '식별자: 선택지마다 같은 식별자가 되는 줄이 몇 개?'], at: [450, 560]},
 ts1: {lines: ['TS1 · TS1 · TS1 · TS1', '→ HYD-01:TS1 · HYD-02:TS1 · HYD-03:TS1 · HYD-04:TS1'], at: [450, 880]},
 mpa: {lines: ['18.2 MPa = 182 bar'], at: [700, 880]},
 idf: {title: '식별자 = 설비 코드 + 이름', lines: ['13행 → HYD-02 + 유압 펌프', '14행 → HYD-02 + 유압 펌프', '일련번호는 안 들어감'], at: [450, 470]},
 idf2: {title: '식별자 = 설비 코드 + 이름', lines: ['13행 → HYD-02 + 유압 펌프', '14행 → HYD-02 + 유압 펌프', '일련번호는 안 들어감', '일련번호를 넣으면?'], at: [450, 470]},
 dec4: {title: 'decisions.csv 4행', lines: ['구성 요소 자리와 그 실물'], at: [1000, 880]},
 more8: {title: '길 2를 고르면 늘어나는 것', lines: ['클래스 하나 · 식별자 하나 · 관계 하나'], at: [450, 600]},
 same: {lines: ['이름이 달라도 같은 것 — 유온 · 오일 온도(둘 다 TS1)', '이름이 같아도 다른 것? — 유온(쿨러 쪽 TS1) · 유온(탱크 쪽 TI-1)'], at: [450, 860]},
 ways: {lines: ['길 1 — 기름 온도면 한 물리량', '길 2 — 재는 곳마다 다른 물리량'], at: [450, 880]},
 ways2: {lines: ['길 1 — 기름 온도면 한 물리량', '      온도 재는 곳이 몇 군데인지 셀 때', '길 2 — 재는 곳마다 다른 물리량', '      같은 곳끼리 값을 견줄 때'], at: [450, 830]},
 ts46: {lines: ['TS1끼리: 48 · 48 · 48 · 46'], at: [720, 880]},
 sum35: {lines: ['구성 요소 41줄 − 빈 칸 5줄 − 떼어 낸 펌프 1줄 = 35'], at: [1100, 268]},
 fix: {lines: ['① 왜 걸렸는지 원자료 줄로 묻기(파일은 그대로)', '② 원자료가 맞으면 표의 그 줄 고치기', '③ parts → check'], at: [200, 760]},
 ask4: {title: '더 물을 것', lines: ['질문 ① 설비 HYD-04', '질문 ③ 품번 표기 RF-10 · 없는 품번 P-PMP-SEAL-X'], at: [450, 860]},
 diff: {lines: ['다르면 — 물은 값 · 기대 답 · 실제 답을 함께 보이고 원인부터', '결과에 맞춰 기대 답을 바꾸지 않는다', '두 번 고쳐도 안 되면 새 대화'], at: [200, 760]},
};

// ── 찾는 글 표: 녹화 답 · Codex가 고친 파일에 따라 달라지는 글. 지금은 완성본과 v59 리허설로 맞춘 어림 — 녹화한 답을 보고 이 두 표만 고친다 ──
// FIND = Codex 답 안 요소 [웹뷰 안 CSS, 든 글, 'last'(여럿이면 아래쪽 것)]. 제목 h2 · h3, 굵은 글 strong, 목록 li, 표 table · tr · th, 문단 p, 줄 링크 span.break-words(촬영준비 길 6).
export const FIND = {
 // R1 답(wo0206 · wo0207): 줄 끝의 근거 칸 · 질문 1 HYD-01 오일 쿨러 줄 · 갈래로 남긴 줄(펌프 실물 · 질문 2)
 r1Evidence: ['th', '근거'], r1Oil: ['tr', '오일 쿨러'], r1Pump: ['tr', '실물'], r1Q2: ['tr', '정상값'],
 // R2 답(wo0208): 적었다는 말
 r2Done: ['p', 'expected.csv'],
 // R3 답(wo0324 · wo0381 · wo0337): 첫째 덩어리(낱말 가르기 표)의 클래스 · 속성 · 관계 줄, 둘째 덩어리(속성으로만 둘 때 묶음 수), 셋째 덩어리(식별자 선택지 — 센서 · 구성 요소 · 부품)
 r3Class: ['tr', '| 클래스'], r3Prop: ['tr', '속성'], r3Rel: ['tr', '관계'], r3Groups: ['p', '15'], r3SensorOpt: ['tr', '태그만'], r3SensorClash: ['tr', '설비 코드와 태그'], r3CompOpt: ['tr', '구성 요소'], r3PartOpt: ['tr', '사내 품번'],
 // R5 답(wo0330 · wo0339 · wo0332 · wo0334 · wo0341 · wo0335): 속성 덩어리의 단위 · 한계 줄, 단위 덩어리의 HYD-03 PS1 줄, 자료형 후보, 관계 문장 넷, 카디널리티 줄, 적어도 하나 줄
 r5Unit: ['tr', '단위'], r5Limit: ['tr', '한계'], r5Ps1: ['tr', 'HYD-03'], r5Types: ['table', '자료형'],
 r5Read1: ['li', '가진다'], r5Read2: ['li', '감시된다'], r5Read3: ['li', '잰다'], r5Read4: ['li', '쓴다'],
 r5CardAsset: ['tr', '설비 → 구성 요소'], r5CardSensor: ['tr', '센서 → 물리량'], r5CardPart: ['tr', '구성 요소 → 부품'], r5Least: ['table', '적어도 하나'], r5LeastPart: ['tr', '부품'],
 // R8 답(wo0422 · wo0409): 겹친 까닭 · 일련번호를 넣으면 걸리는 줄 · 속성으로 두는 길 · 실물을 두는 길 · 추천 · 끝 문장
 r8Why: ['p', '설비 코드'], r8Serial: ['p', '35'], r8Attr: ['strong', '속성으로'], r8Unit: ['strong', '실물을'], r8Rec: ['strong', '추천'], r8End: ['p', '결정은 아닙니다'],
 // R10 답(wo0505): 하나로 묶는 쪽 · 그 안의 센서 수 · 나누는 쪽 · HYD-07 지시계가 드는 묶음
 r10One: ['p', '하나로 묶'], r10Count: ['p', '13'], r10Split: ['p', '나누'], r10Ti: ['p', 'TI-1'],
 // R12 답(wo0511): 물어 온 센서 셋
 r12Q1: ['li', 'HYD-02'], r12Q2: ['li', 'HYD-07'], r12Q3: ['li', 'HYD-04'],
 // R13 답(wo0514): 내 답과 코드 줄을 짝지은 대목
 r13Map: ['ul', 'quantity_rules.py'],
 // R14 답(wo0604): 근거 줄 field_notes.md:22
 r14Line: ['span.break-words', '22'],
 // R16 답(wo0912): 후보 셋 · 고른 후보 · 그 줄의 「왜 답할 수 없는지」와 근거 줄
 r16All: ['ol', '설치'], r16Pick: ['li', '설치'], r16Why: ['li', '설치'],
 // R17 답(wo0918): Codex가 물어 온 속성 이름
 r17Ask: ['p', '속성 이름'],
};
// PICK = 고친 파일 · 답에서 고르는 값(편집기 줄의 앞머리 · 후보 번호 · 속성 이름). 완성본 · 대본 조작 칸의 값으로 채운 어림.
export const PICK = {
 candidate: null,        // R16 답에서 강사가 고른 후보 번호(wo0912 부탁의 ○) — 녹화 답을 보고 채운다
 candidateExtra: '',     // 후보가 「2020년 전에 설치한 설비」처럼 다른 꼴로 오면 '가동 중인 설비 가운데 가장 이른 것으로 물을게.'(대본 wo0912 조작 칸)
 askedName: true,        // R17에 Codex가 속성 이름을 되물었는가(묻지 않았으면 09c 구간과 wo0918을 뺀다 — 대본 wo0918 조작 칸)
 installed: 'installed', // 설치일 속성 이름(wo0914 · wo0916 — Codex가 이름을 스스로 지었으면 그 이름)
 limit: 'limit',         // 센서 한계 속성 이름(wo0331 · wo0605 — 3장에서 Codex가 지은 이름)
 tag: 'tag', unit: 'unit',
 idSensor: '{설비코드}:{태그}', idComp: '{설비코드}:{구성요소}', idPart: '{품번}', idQty: '{물리량}', idUnit: '{일련번호}',
 relUnit: '구성 요소,', // relations.csv에서 자리 → 실물 줄의 칸(시작 · 종료 클래스 — 이 글과 '실물'이 함께 든 줄)
 relPart: '구성 요소,부품',  // relations.csv에서 구성 요소 → 부품 줄(시작,종료 칸이 이어진 글)
 clash: 'HYD-02:유압 펌프',  // classes 화면 「식별자가 겹친 곳」 카드의 머리(구성 요소 식별자 틀에 따라 — wo0421)
 seat02: 'HYD-02:주 펌프 (A)', // names 화면 그림의 HYD-02 펌프 자리 노드 id(같은 모델끼리 맞춘 이름 — wo0416 · wo0417)
 pumpItem: '주 펌프 (A) 실물', // query 화면 대조 표의 HYD-02 펌프 실물 줄의 항목(wo0815)
 hyd04: '1,HYD-04,',     // expected.csv에서 HYD-04로 묻는 줄의 앞머리(wo0813)
 rf10: '3,RF-10,', noPart: '3,P-PMP-SEAL-X,', q4: '4,',
 codeLines: [null, null, null],   // quantity_rules.py에서 내 답 ①②③이 들어간 줄 번호(wo0514 — Codex가 짚어 준 줄)
};
