// 통합 2회차 07편 「그래프 구현과 검증」(큐 wg0101~wg1308)의 구간들이 함께 쓰는 것: 구간 틀(seg) · 조작 낱개 · 부탁 글(ASK) · 펜 그림 · 찾는 글 표(FIND) · 구간 차례(ORDER).
// 대본 정본: 산출물/통합반/실습/02회차/대본/07_실습_그래프구현과검증.md. 구간 표 · 녹화 차례 · 되돌리기는 작업 폴더 판정/녹화모듈_07.md, 되돌리기 · 사본 코드는 wg-state.mjs.
// 구간 모듈(wg-NN · wg-NNx.mjs)은 `export default seg({…})` 한 줄 묶음이다. cues의 한 칸은
//   {id} 말만 · {id, at, steps: [[구절 | null | END, 조작], …]} 말하며 조작 · {hold: {…}} 답 · 터미널 기다림(기다림 말 포함) · {do: 조작} 말 사이의 조작.
//   steps의 첫 조작은 at 구절에서, 다음 조작은 그 구절을 말하기 시작할 때(atPhrase), END는 그 큐의 말이 끝난 뒤에 한다. 구절이 큐 글에 차례대로 없으면 그 큐에서 멈춘다.
// 녹화 답 · Codex가 쓴 파일 · 그 take의 결과 화면에 따라 달라지는 글은 맨 아래 FIND 표 한 곳에만 둔다. 지금 값은 완성본(graph-lab-completed.zip)과 강사 길로 돌린 결과 화면(판정/녹화모듈_07.md 「확인한 것」)의 글자다.
// 대상이 없거나 여럿이면 큐 id를 대며 멈춘다(건너뛰지 않는다).
// Codex 요청이 있는 구간(kind ask)의 리허설은 WG_NOSEND=1로 돌린다 — 부탁 글을 넣고 보내기 직전까지 해 보고 보내지 않는다(학생 역 계정 한도를 쓰지 않는다). 그 뒤 wg-reset.mjs가 입력칸을 비운다.
import fs from 'node:fs/promises';
import {labUi, atPhrase, em, LABS, PAUSE, termLine, codexEl, codexBoxes, codexView, codexScrollInto, codexFocus, codexType, codexSubmit, codexDone, newTerminal, resultView, page as resultPage} from './lab-common.mjs';

export const LAB = LABS.wg.dir, ROOT = LAB.slice(0, LAB.lastIndexOf('/'));
export const RESULT = resultPage(LAB);
export const snapDir = seg => ROOT + '/_' + seg;   // 사본 자리 = 촬영 폴더 옆 D:/HYD-Practice/wgp-<해시>/_<구간>/
export const END = Symbol('말 끝');
const NOSEND = process.env.WG_NOSEND === '1';
const PASTE_OVER = 400;   // 이보다 긴 부탁 글은 한 번에 붙여 넣는다(영상 V-14 — 긴 글은 붙여넣기). 짧은 글은 06-1 · 5분 예시처럼 빠르게 친다(codexType)
const who = ctx => ctx.cueId ?? '(큐 밖)';
const stop = (ctx, why) => { throw Error(who(ctx) + ': ' + why + ' (segs/wg-common.mjs)'); };
const rep = (ctx, o) => ctx.report?.push({cue: ctx.cueId, fail: false, ...o});
export const speechEnd = async ctx => { const q = ctx.__cue; if (q && !ctx.rehearsal && q.t0 != null) { const w = q.t0 + q.dur - Date.now(); if (w > 0) await ctx.sleep(w); } };
// 말만 하는 큐는 labUi가 「지금 큐」를 바꾸지 않는다 — 기다림 말(hold)이 앞 말의 끝을 알 수 있게 여기서 적어 둔다.
const markSaid = async (ctx, id) => { ctx.__cue = {id, text: '', from: 0, t0: Date.now(), dur: ctx.rehearsal ? 0 : JSON.parse(await fs.readFile(ctx.audio + '/' + id + '.json', 'utf8')).duration_ms}; };
const pointerAt = (c, ctx) => c.serial(() => ctx.p.evaluate(() => { const r = document.getElementById('recording-pointer')?.getBoundingClientRect(); return r ? {x: r.x, y: r.y} : null; }));

// ── 구간 틀 ── spec = {name, page(0 웹 VS Code · 1 결과 화면), kind(say · ask · view · run), first(결과 화면을 처음 여는 구간의 제목 앞머리), check(녹화 전 시작 상태 확인), cues, next}
export const seg = spec => {
 for (const q of spec.cues) if (q.steps && q.at == null) throw Error(spec.name + ' ' + q.id + ': 조작이 있는 큐에 at 구절이 없다 (segs/wg-common.mjs seg)');
 const run = async ctx => {
  const c = await labUi(ctx), w = ctx.__wg = {pens: new Map(), since: 0, ran: 0, ans: null, asks: 0, waited: [], nosend: false};
  ctx.__wgSeg = spec.name;
  const url = await c.serial(() => ctx.p.url()), web = url.startsWith('http');
  if ((spec.page ?? 0) === 1 ? web : !web) throw Error(spec.name + ': ' + (spec.page ? '둘째 페이지(결과 화면) 구간 — PAGE=1 ./run.sh …로 돌린다' : '첫 페이지(웹 VS Code) 구간 — PAGE 없이 돌린다') + ' (지금 주소 ' + url.replace(/tkn=[^&]+/, 'tkn=…').slice(0, 80) + ')');
  const ptr = spec.ptr ?? (spec.page ? {x: 1400, y: 300} : {x: 900, y: 460});
  if (spec.page === 1 && spec.first) { const at = await pointerAt(c, ctx); await resultView(c, ctx, LAB, spec.first); await c.installPointer(at ?? ptr); }   // 첫 결과 화면: 녹화 전에 열고, 앞 구간이 끝난 자리에 화살표를 다시 놓는다
  else if (spec.page === 1 && decodeURI(url) !== RESULT) throw Error(spec.name + ': 둘째 페이지에 이 랩의 결과 화면이 열려 있지 않음 — SEG=' + spec.name + ' ./run.sh reset wg-reset.mjs');
  if (!spec.page) await settle(c, ctx);
  await spec.check?.(c, ctx);
  await c.installPointer(ctx.prev ? null : ptr);
  await ctx.begin();
  for (const q of spec.cues) {
   if (q.do) { await q.do(c, ctx); continue; }
   if (q.hold) { await hold(c, ctx, q.hold); continue; }
   if (!q.steps) { await ctx.say(q.id, null, q.opt); await markSaid(ctx, q.id); continue; }
   await ctx.say(q.id, async () => { for (const [ph, act] of q.steps) { if (ph === END) await speechEnd(ctx); else if (ph != null) await atPhrase(ctx, ph); await act(c, ctx); } }, {at: q.at, ...q.opt});
  }
  return {segment: spec.name, next: spec.next ?? '', aiRequests: w.asks, ...(w.ans ? {answer: w.ans.message, codexMs: w.ans.ms, used: w.ans.used} : {}), waitLines: w.waited, ...(w.nosend ? {nosend: true} : {})};
 };
 run.spec = spec; return run;
};
export const all = (...acts) => async (c, ctx) => { for (const a of acts) await a(c, ctx); };
export const pause = ms => async (c, ctx) => { if (!ctx.rehearsal) await ctx.sleep(ms); };
// 녹화가 시작할 때 다시 건 화면 크기 때문에 터미널 가운데에 「125 x 22」 같은 크기 표시가 잠깐 뜬다(촬영준비 「함정」) — 그 글이 사라진 뒤 녹화를 시작한다.
async function settle(c, ctx) {
 await ctx.sleep(1200);
 for (let n = 0; n < 40; n++) {
  const shown = await c.serial(() => ctx.p.evaluate(() => [...document.querySelectorAll('.part.panel *')].some(e => !e.children.length && /^\s*\d+\s*x\s*\d+\s*$/.test(e.textContent) && e.getBoundingClientRect().width > 0)));
  if (!shown) return;
  await ctx.sleep(250);
 }
 throw Error('터미널 크기 표시(「N x N」)가 10초 뒤에도 남아 있음 (segs/wg-common.mjs settle)');
}

// ── 글자 자리 재기: roots(CSS) 안에서 phrase가 차지한 자리(줄마다 상자 하나). 바깥 문서와 Codex 웹뷰 프레임 안에서 같은 함수를 돌린다. 빈칸은 줄바꿈 없는 빈칸(편집기 · 터미널)을 보통 빈칸과 같게 본다 ──
export const textHits = ({roots, phrase}) => {
 const out = [];
 for (const root of document.querySelectorAll(roots)) {
  if (!root.getClientRects().length) continue;
  const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT), nodes = []; let s = '';
  for (let n; (n = w.nextNode());) { if (!n.data) continue; nodes.push([n, s.length]); s += n.data.replace(/\u00a0/g, ' '); }
  for (let i = s.indexOf(phrase); i >= 0; i = s.indexOf(phrase, i + phrase.length)) {
   const at = k => { const x = nodes.findLast(v => v[1] <= k); return [x[0], k - x[1]]; };
   const r = document.createRange(), a = at(i), b = at(i + phrase.length - 1); r.setStart(a[0], a[1]); r.setEnd(b[0], b[1] + 1);
   const ls = [];
   for (const q of r.getClientRects()) { if (q.width <= 0 || q.height <= 0) continue; const m = q.top + q.height / 2, l = ls.find(l => m > l[1] && m < l[3]);
    if (l) { l[0] = Math.min(l[0], q.left); l[1] = Math.min(l[1], q.top); l[2] = Math.max(l[2], q.right); l[3] = Math.max(l[3], q.bottom); } else ls.push([q.left, q.top, q.right, q.bottom]); }
   if (ls.length) out.push(ls.map(l => [l[0], l[1], l[2] - l[0], l[3] - l[1]]));
  }
 }
 const h = document.documentElement.getBoundingClientRect();
 return {hits: out, origin: [h.left, h.top]};
};
const byPlace = hs => hs.sort((a, b) => a[0][1] - b[0][1] || a[0][0] - b[0][0]);
const union = rs => { const x = Math.min(...rs.map(r => r[0])), y = Math.min(...rs.map(r => r[1])); return {x, y, w: Math.max(...rs.map(r => r[0] + r[2])) - x, h: Math.max(...rs.map(r => r[1] + r[3])) - y}; };

// ── 강조 · 글상자 · 펜 그림 ── 모양은 영상 V-11(띠 band · 밑줄 underline · 테두리 box · 동그라미 circle). o.faint = 대본의 「흐린 …」.
// 그림 층(../draw.mjs)에 흐린 모양이 없어, 방금 그린 강조의 색만 옅게 바꾼다(06-1 wv-common.mjs의 faint와 같은 방법 — 공용 도구로 옮길 거리, 판정/녹화모듈_07.md).
export async function emph(c, ctx, target, shape = 'band', o = {}) {
 await c.emph(target, {shape, ...(o.keep != null ? {keep: o.keep} : {}), ...(o.phrase ? {phrase: o.phrase} : {})});
 if (!o.faint) return;
 const ok = await c.serial(() => ctx.p.evaluate(() => {
  const g = [...document.querySelectorAll('#recording-draw [data-mark]')].pop(); if (!g) return false;
  for (const e of g.children) {
   if (e.style.borderTopWidth) e.style.borderColor = 'rgba(229,57,53,0.4)';
   else if (e.style.backgroundColor.startsWith('rgba(255, 214, 0')) e.style.backgroundColor = 'rgba(255,214,0,0.2)';
   else e.style.backgroundColor = 'rgba(229,57,53,0.4)';
  }
  return true;
 }));
 if (!ok) stop(ctx, '흐리게 할 강조가 화면에 없음');
 rep(ctx, {op: 'emph', target: '흐리게'});
}
export const E = (target, shape = 'band', o = {}) => (c, ctx) => emph(c, ctx, target, shape, o);
export const clr = c => c.clearEmph();
export const note = (lines, o) => c => c.note(lines, o);
export const noteOff = c => c.note(null);
export const N = (line, shape = 'underline', o = {}) => E({note: line}, shape, o);   // 글상자의 줄(줄 번호나 줄에 든 글)
// 펜 그림: P(정의).draw('칸', …) · show · hide · ring · trace · erase — 조작으로 돌려준다. 그림은 띄운 구간 안에서 걷는다(ctrl.mjs). 한 번에 하나만 떠 있을 수 있다(draw.mjs).
export const P = def => new Proxy({}, {get: (_, k) => (...a) => async (c, ctx) => { const m = ctx.__wg.pens; if (!m.has(def.id)) m.set(def.id, c.pen(def)); await m.get(def.id)[k](...a); }});
export const PE = (id, shape = 'box', o = {}) => E({pen: id}, shape, o);

// ── 탐색기 ── level = 폴더 깊이(aria-level, 랩 폴더 바로 아래가 1). like = 한 줄로 합쳐 보이는 폴더(changes/2026-10-20)처럼 이름이 줄 글의 일부일 때.
const xrow = (c, ctx, name, level, like = false) => c.serial(() => ctx.p.evaluate(({name, level, like}) => {
 const rs = [...document.querySelectorAll('.explorer-folders-view .monaco-list-row')].filter(e => (level == null || e.getAttribute('aria-level') === String(level)) && (like ? e.innerText.replace(/\s+/g, '').includes(name) : e.innerText.trim() === name));
 if (rs.length !== 1) throw Error('탐색기 줄 「' + name + '」' + (level == null ? '' : '(깊이 ' + level + ')') + '이 ' + rs.length + '개');
 const l = (rs[0].querySelector('.label-name') ?? rs[0]).getBoundingClientRect(), v = document.querySelector('.explorer-folders-view').getBoundingClientRect();
 return {x: Math.max(v.left + 10, l.x - 14), y: l.y + l.height / 2, open: rs[0].getAttribute('aria-expanded'), out: l.top < v.top ? -1 : l.bottom > v.bottom ? 1 : 0, vx: v.left + v.width / 2, vy: v.top + v.height / 2};
}, {name, level, like}));
const xseen = (ctx, name, level, like = false) => ctx.waitFor('[...document.querySelectorAll(".explorer-folders-view .monaco-list-row")].some(e => ' + (level == null ? '' : 'e.getAttribute("aria-level") === "' + level + '" && ') + (like ? 'e.innerText.replace(/\s+/g, "").includes(' + JSON.stringify(name) + ')' : 'e.innerText.trim() === ' + JSON.stringify(name)) + ')', 15000);
// 줄이 탐색기의 보이는 칸에 오도록 탐색기 위에서 휠로 굴린다(말하지 않는 스크롤 — 영상 V-14). 펼친 폴더가 많아 줄이 칸 밖으로 밀렸을 때.
const xshow = async (c, ctx, name, level, like = false) => {
 await xseen(ctx, name, level, like);
 for (let n = 0; n < 12; n++) {
  const q = await xrow(c, ctx, name, level, like);
  if (!q.out) return q;
  if (!n) { await c.move(q.vx, q.vy); await c.gate(); }
  await c.serial(() => ctx.p.mouse.wheel(0, q.out * 180)); await ctx.sleep(400);
 }
 stop(ctx, '탐색기를 굴려도 줄 「' + name + '」이 보이지 않음');
};
// 접힌 폴더만 눌러 편다(펴져 있으면 화살표만 옮긴다 — 앞 take가 남긴 펼침을 거꾸로 접지 않는다). fold는 그 반대.
export const unfold = (name, level, like) => async (c, ctx) => { const q = await xshow(c, ctx, name, level, like); if (q.open === 'true') return c.move(q.x, q.y); await c.clickAt(q.x, q.y); await ctx.sleep(500); if ((await xrow(c, ctx, name, level, like)).open !== 'true') stop(ctx, '탐색기 폴더 「' + name + '」이 펴지지 않음'); };
export const fold = (name, level, like) => async (c, ctx) => { const q = await xshow(c, ctx, name, level, like); if (q.open !== 'true') return c.move(q.x, q.y); await c.clickAt(q.x, q.y); await ctx.sleep(400); };
export const XE = (name, level, shape = 'underline', o = {}) => async (c, ctx) => { await xshow(c, ctx, name, level); await emph(c, ctx, {sel: '.explorer-folders-view .monaco-list-row' + (level == null ? '' : '[aria-level="' + level + '"]') + ' .label-name', text: name}, shape, o); };
export const rootE = (shape = 'underline') => E({sel: '.pane-header[aria-label^="Explorer Section:"] .title'}, shape);
const tabIs = (ctx, name) => ctx.waitFor('document.querySelector(".tabs-container .tab.active .label-name")?.textContent === ' + JSON.stringify(name), 15000);
// 파일 열기: 탐색기의 그 줄을 누르고 Enter(한 번 누르기는 고르기만 한다 — 촬영준비 길 4). 위쪽 폴더는 먼저 unfold로 편다. 이미 열린 탭이면 그 탭이 앞에 온다.
export const open = (name, level) => async (c, ctx) => { const q = await xshow(c, ctx, name, level); await c.clickAt(q.x, q.y); await c.key('Enter'); await tabIs(ctx, name); await ctx.sleep(600); };
export const closeTab = name => async (c, ctx) => {
 await tabIs(ctx, name); await c.clickSel('.tabs-container .tab.active .tab-actions .action-label');
 await ctx.waitFor('![...document.querySelectorAll(".tabs-container .tab .label-name")].some(e => e.textContent === ' + JSON.stringify(name) + ')', 8000);
};
// 열려 있는 탭으로 옮긴다(이미 앞이면 그대로). 탭이 많아 그 탭이 탭 줄의 보이는 칸 밖이면, 그 자리를 누르지 않고 탐색기의 그 파일(level 깊이)로 앞에 둔다.
export const tab = (name, level = 3) => async (c, ctx) => {
 const t = await c.serial(() => ctx.p.evaluate(n => { const l = [...document.querySelectorAll('.tabs-container .tab .label-name')].filter(e => e.textContent === n); if (l.length !== 1) return {n: l.length}; const tb = l[0].closest('.tab'), r = tb.getBoundingClientRect(), b = (tb.closest('.tabs-and-actions-container') ?? tb.closest('.title') ?? tb.parentElement).getBoundingClientRect(); return {n: 1, active: tb.classList.contains('active'), inside: r.left >= b.left - 1 && r.right <= b.right + 1}; }, name));
 if (t.n !== 1) stop(ctx, '열린 탭 「' + name + '」이 ' + t.n + '개');
 if (t.active) return;
 if (!t.inside) return open(name, level)(c, ctx);
 await c.tab(name); await tabIs(ctx, name); await ctx.sleep(400);
};

// ── 편집기 ── 대상은 보이는 줄에서 글로 찾고(편집기는 화면에 보이는 줄만 그린다), 칸 밖이면 휠로 들인다(긴 한 줄 쿼리는 옆으로). 강조 상자는 편집기 칸의 보이는 폭까지만 쓴다(긴 줄의 띠가 화면 밖으로 나가지 않게).
// o.nth = 같은 글이 여럿일 때 위에서 몇째(0 · -1), o.after = 그 글이 든 줄보다 아래에서만(같은 쿼리 꼴이 여러 질문에 있을 때 「// 질문 3」처럼), o.line = 그 글로 시작하는 줄 안에서만, o.inside = 그 글 자리 안에서만(줄 안의 조각의 조각).
const VL = '.part.editor .editor-instance .view-lines .view-line';
const edBox = (c, ctx) => c.serial(() => ctx.p.evaluate(() => { const b = [...document.querySelectorAll('.part.editor .editor-instance .editor-scrollable')].map(e => e.getBoundingClientRect()).find(r => r.width > 0 && r.height > 0); if (!b) throw Error('열린 편집기가 없음'); return {l: b.left, t: b.top, r: b.right, b: b.bottom}; }));
const lineHits = (c, ctx, starts) => c.serial(() => ctx.p.evaluate(({VL, starts}) => [...document.querySelectorAll(VL)].filter(e => e.textContent.replace(/\u00a0/g, ' ').startsWith(starts)).map(e => { const b = e.getBoundingClientRect(); return [b.x, b.y, b.width, b.height]; }), {VL, starts}));
async function edHits(c, ctx, phrase, o = {}) {
 let hs = byPlace((await c.serial(() => ctx.p.evaluate(textHits, {roots: VL, phrase}))).hits);
 if (o.after != null) { const a = byPlace((await c.serial(() => ctx.p.evaluate(textHits, {roots: VL, phrase: o.after}))).hits)[0]; hs = a ? hs.filter(h => h[0][1] > a[0][1] + 2) : []; }
 if (o.line != null) { const ls = await lineHits(c, ctx, o.line); hs = hs.filter(h => ls.some(l => Math.abs(l[1] - h[0][1]) < l[3] / 2)); }
 if (o.inside != null) { const box = byPlace((await c.serial(() => ctx.p.evaluate(textHits, {roots: VL, phrase: o.inside}))).hits); hs = hs.filter(h => box.some(b => Math.abs(b[0][1] - h[0][1]) < 3 && h[0][0] >= b[0][0] - 1 && h[0][0] + h[0][2] <= b.at(-1)[0] + b.at(-1)[2] + 1)); }
 return hs;
}
async function edFind(c, ctx, phrase, o = {}, far = 14) {
 const b = await edBox(c, ctx), mid = {x: b.l + Math.min(700, (b.r - b.l) * 0.7), y: b.t + (b.b - b.t) * 0.55};
 let moved = false;
 for (let n = 0; n < far + 30; n++) {
  const hs = await edHits(c, ctx, phrase, o), h = hs.at(o.nth ?? 0);
  const dy = !h ? (o.up ? -240 : 240) : h[0][1] < b.t + 4 ? -160 : h.at(-1)[1] + h.at(-1)[3] > b.b - 6 ? 160 : 0;
  const right = h && Math.max(...h.map(r => r[0] + r[2])), wide = h && right - h[0][0] > b.r - b.l - 40;
  const dx = !h || dy ? 0 : h[0][0] < b.l + 6 ? Math.max(-400, h[0][0] - b.l - 60) : (!wide && right > b.r - 24) ? Math.min(400, right - b.r + 80) : 0;
  if (h && !dy && !dx) return h;
  if (!h && n >= far) break;
  if (!moved) { await c.move(mid.x, mid.y); await c.gate(); moved = true; }
  await c.serial(() => ctx.p.mouse.wheel(dx, dy)); await ctx.sleep(420);
 }
 stop(ctx, '편집기에서 「' + phrase + '」' + (o.line ? '(줄 「' + o.line + '」 안)' : '') + (o.after ? '(「' + o.after + '」 아래)' : '') + '을 찾지 못함 — 녹화한 파일의 글자에 맞춰 FIND 표를 고친다');
}
// 편집기 칸의 보이는 폭까지만 남긴 상자
const clip = async (c, ctx, rs) => { const b = await edBox(c, ctx); const out = rs.map(r => { const x0 = Math.max(r[0], b.l + 2), x1 = Math.min(r[0] + r[2], b.r - 16); return [x0, r[1], x1 - x0, r[3]]; }).filter(r => r[2] > 2); if (!out.length) stop(ctx, '강조할 글이 편집기 칸 밖'); return out; };
export const ED = (phrase, shape = 'underline', o = {}) => async (c, ctx) => { const h = await edFind(c, ctx, phrase, o); await emph(c, ctx, shape === 'box' || shape === 'circle' ? {rects: h} : {rects: await clip(c, ctx, h)}, shape, o); };
export const EDin = (inside, sub, shape = 'box', o = {}) => ED(sub, shape, {...o, inside});
export const LP = (starts, phrase, shape = 'underline', o = {}) => ED(phrase, shape, {...o, line: starts});
export const edSee = (phrase, o = {}) => async (c, ctx) => { await edFind(c, ctx, phrase, o); };
// 줄 하나(그 글로 시작하는 줄 — 보이는 폭까지)
export const L = (starts, shape = 'band', o = {}) => async (c, ctx) => {
 await edFind(c, ctx, starts, {...o, line: starts});
 const ls = await lineHits(c, ctx, starts); if (ls.length !== 1) stop(ctx, '편집기에서 「' + starts + '」로 시작하는 보이는 줄이 ' + ls.length + '개');
 const g = await glyphs(c, ctx, starts); await emph(c, ctx, {rects: await clip(c, ctx, g)}, shape, o);
};
// 그 글로 시작하는 줄들의 글자 자리(줄마다 하나)
const glyphs = (c, ctx, starts) => c.serial(() => ctx.p.evaluate(({VL, starts}) => {
 const out = [];
 for (const e of [...document.querySelectorAll(VL)].filter(e => e.textContent.replace(/\u00a0/g, ' ').startsWith(starts))) {
  const g = document.createRange(); g.selectNodeContents(e); const rs = [...g.getClientRects()].filter(r => r.width > 0);
  if (rs.length) out.push([Math.min(...rs.map(r => r.left)), Math.min(...rs.map(r => r.top)), Math.max(...rs.map(r => r.right)) - Math.min(...rs.map(r => r.left)), Math.max(...rs.map(r => r.bottom)) - Math.min(...rs.map(r => r.top))]);
 }
 return out.sort((a, b) => a[1] - b[1]);
}, {VL, starts}));
// 같은 글로 시작하는 줄 모두(「//」 메모 줄처럼 묶어서 한 번에)
export const LS = (starts, shape = 'underline', o = {}) => async (c, ctx) => { await edFind(c, ctx, starts, {line: starts}); const g = await glyphs(c, ctx, starts); if (!g.length) stop(ctx, '「' + starts + '」로 시작하는 보이는 줄이 없음'); await emph(c, ctx, {rects: await clip(c, ctx, g)}, shape, o); };
// 줄 묶음: from으로 시작하는 줄부터 to로 시작하는 줄까지(둘 다 보이게 들인 뒤, 그 사이의 보이는 줄 모두)
export const EDL = (from, to, shape = 'band', o = {}) => async (c, ctx) => {
 await edFind(c, ctx, from, {line: from}); await edFind(c, ctx, to, {line: to});
 const a = await lineHits(c, ctx, from), b = await lineHits(c, ctx, to);
 if (a.length < 1 || b.length < 1) stop(ctx, '줄 묶음 「' + from + '」 ~ 「' + to + '」이 함께 보이지 않음');
 const top = a[0][1], bot = b.at(-1)[1] + b.at(-1)[3];
 if (bot <= top) stop(ctx, '줄 묶음의 끝 줄 「' + to + '」이 첫 줄보다 위');
 const g = (await glyphs(c, ctx, '')).filter(r => r[1] >= top - 1 && r[1] + r[3] <= bot + 1);
 await emph(c, ctx, {rects: await clip(c, ctx, g)}, shape, o);
};
// 줄 번호로 가기(Ctrl+G) — 긴 파일(graph.json)에서 멀리 있는 줄을 볼 때. 간 뒤 seen 글이 보이는지 확인한다.
export const gotoLine = (n, seen) => async (c, ctx) => {
 const b = await edBox(c, ctx); await c.clickAt(b.l + 420, b.t + 140); await c.key('Control+g');
 await ctx.waitFor('!!document.querySelector(".quick-input-widget")?.checkVisibility() && document.activeElement?.closest(".quick-input-widget") != null', 5000);
 for (const d of String(n)) await c.key(d);
 await c.key('Enter'); await ctx.sleep(700);
 if (!(await edHits(c, ctx, seen)).length) stop(ctx, n + '행으로 갔는데 「' + seen + '」이 보이지 않음 — FIND 표의 줄 번호를 지금 파일에 맞춘다');
};

// ── 터미널 ── 명령은 학생과 같은 글자로 친다(--no-open을 붙이지 않는다 — 영상 V-3).
export const PROMPT = 'graph-lab>';
const termRows = (c, ctx) => c.serial(() => ctx.p.evaluate(() => [...document.querySelectorAll('.terminal-wrapper .xterm-rows > div')].map(d => d.textContent.replace(/\u00a0/g, ' ').trimEnd())));
export const cmd = text => async (c, ctx) => { const q = await termLine(c, ctx, PROMPT); await c.clickAt(q.x + 300, q.y); await c.typeKeys(text); };
export const enter = async (c, ctx) => { await c.key('Enter'); ctx.__wg.ran = Date.now(); };
// 명령이 끝나기를 기다린다: 결과 파일이 Enter 뒤에 다시 쓰이고 터미널 끝 줄이 빈 프롬프트로 돌아올 때(앞 실행의 「결과: …」 줄이 화면에 남아 있어 그 글로는 가릴 수 없다).
// after = 끝난 뒤 쉴 ms(기본 조작 결과 뒤 쉼). 첫 python run.py 구간은 결과 줄이 뜬 직후 0.7초쯤에 끝낸다(촬영준비 길 6 「결과 화면이 저절로 열리는 장면」).
export const ran = ({timeout = 60000, after = PAUSE.result} = {}) => async (c, ctx) => {
 const t0 = ctx.__wg.ran; if (!t0) stop(ctx, 'ran 앞에 enter가 없음');
 for (;;) {
  const m = await fs.stat(LAB + '/output/result.json').then(s => s.mtimeMs, () => 0), last = (await termRows(c, ctx)).filter(Boolean).at(-1) ?? '';
  if (m >= t0 - 300 && last.endsWith(PROMPT)) break;
  if (Date.now() - t0 > timeout) stop(ctx, '명령이 ' + timeout / 1000 + '초 안에 끝나지 않음(결과 파일 ' + (m >= t0 - 300 ? '새로 씀' : '그대로') + ', 터미널 끝 줄 「' + last.slice(-60) + '」)');
  await ctx.sleep(200);
 }
 await ctx.sleep(after);
};
export const T = (has, shape = 'underline', o = {}) => E(em.term(has), shape, o);
const termHas = async (c, ctx, text) => (await termRows(c, ctx)).some(r => r.includes(text));
// 터미널이 보이지 않으면 위 메뉴 줄로 새로 연다(폴더를 다시 연 뒤 — 13장).
export const termEnsure = async (c, ctx) => { if (await c.serial(() => ctx.p.evaluate(() => !!document.querySelector('.terminal-wrapper')?.checkVisibility()))) return; await newTerminal(c, ctx); await ctx.waitFor('[...document.querySelectorAll(".terminal-wrapper .xterm-rows > div")].some(d => d.textContent.includes(' + JSON.stringify(PROMPT) + '))', 20000); };

// ── 폴더 닫고 다시 열기(13장 — 미검증: 메뉴 글자는 UI 표) ──
const menuHas = async (c, ctx, has) => {
 const q = await c.serial(() => ctx.p.evaluate(has => { const hits = [...document.querySelectorAll('.monaco-menu .action-label, .context-view .action-label')].filter(e => e.textContent.includes(has) && e.getBoundingClientRect().width > 0); if (hits.length !== 1) return {error: '메뉴에 「' + has + '」이 든 항목이 ' + hits.length + '개'}; const b = hits[0].getBoundingClientRect(); return {x: b.x + b.width / 2, y: b.y + b.height / 2}; }, has));
 if (q.error) stop(ctx, q.error);
 await c.move(q.x, q.y); await ctx.sleep(300); await c.clickAt(q.x, q.y);
};
const menuShown = (ctx, text) => ctx.waitFor('[...document.querySelectorAll(".monaco-menu .action-label, .context-view .action-label")].some(e => e.textContent.trim() === ' + JSON.stringify(text) + ' && e.getBoundingClientRect().width > 0)', 5000);
// 폴더를 닫거나 연 뒤: 탐색기 머리에 그 폴더 이름이 있는지(open) · 없는지로 기다린다. 창이 새로 읽혀 화살표가 사라졌으면 그 자리에 다시 놓는다.
const settled = async (c, ctx, at, open) => {
 for (const t0 = Date.now(); ; await ctx.sleep(300)) {
  const s = await c.serial(() => ctx.p.evaluate(() => ({ready: document.readyState === 'complete' && !!document.querySelector('.monaco-workbench'), head: (document.querySelector('.pane-header[aria-label^="Explorer Section:"]')?.innerText ?? '').toLowerCase(), ptr: !!document.getElementById('recording-pointer')}))).catch(() => null);
  if (s?.ready && s.head.includes('graph-lab') === open) { await ctx.sleep(2500); if (!(await c.serial(() => ctx.p.evaluate(() => !!document.getElementById('recording-pointer'))))) await c.installPointer(at); return; }
  if (Date.now() - t0 > 60000) stop(ctx, '폴더를 ' + (open ? '연' : '닫은') + ' 화면이 60초 안에 서지 않음(탐색기 머리 「' + (s?.head ?? '읽지 못함') + '」)');
 }
};
export const closeFolder = async (c, ctx) => {
 const at = await pointerAt(c, ctx);
 await c.clickSel('.menubar-menu-button', UI.file); await menuShown(ctx, UI.closeFolder); await c.menuItem(UI.closeFolder);
 await settled(c, ctx, at, false);
};
export const reopenFolder = async (c, ctx) => {
 const at0 = await pointerAt(c, ctx);
 await c.clickSel('.menubar-menu-button', UI.file); await menuShown(ctx, UI.openRecent); await c.menuItem(UI.openRecent);
 await ctx.sleep(500); await menuHas(c, ctx, UI.recentHas);
 await settled(c, ctx, at0, true);
};

// ── Codex ── 한 편이 대화 하나로 이어진다(대본에 새 대화를 여는 조작이 없다). ask = 입력칸에 부탁 글 넣기, send = 보내기, hold = 답이 끝날 때까지(기다림 말 · 승인 창).
export const ask = text => async (c, ctx) => {
 await codexFocus(c, ctx);
 if (text.length <= PASTE_OVER) return codexType(c, ctx, text);
 await c.gate(); await c.clearEmph();
 if (!(await c.serial(() => ctx.p.evaluate(() => { const a = document.activeElement; return !!a && (a.tagName === 'IFRAME' || !!a.closest('.part.auxiliarybar, .webview')); })))) stop(ctx, '입력 초점이 Codex가 아님 — 부탁 글을 붙여 넣지 않고 멈춤');
 const t0 = Date.now(); await c.serial(() => ctx.p.keyboard.insertText(text)); rep(ctx, {op: 'type', target: 'Codex 입력칸(붙여넣기)', text, ms: Date.now() - t0});
 await ctx.sleep(400);
};
export const send = async (c, ctx) => {
 const w = ctx.__wg;
 if (ctx.rehearsal && NOSEND) { await c.gate(); rep(ctx, {op: 'key', target: 'Enter(보내지 않음 — WG_NOSEND=1 리허설)'}); w.nosend = true; return; }
 w.since = await codexSubmit(c, ctx); w.asks++; w.ans = null;
};
const frameHits = async (c, ctx, roots, phrase) => c.serial(async () => {
 const out = [];
 for (const f of ctx.p.frames()) {
  if (f === ctx.p.mainFrame()) continue;
  try { const r = await f.evaluate(textHits, {roots, phrase}); if (!r.hits.length) continue; const o = await f.locator('html').boundingBox(); if (!o) continue;
   for (const h of r.hits) out.push(h.map(q => [q[0] + o.x - r.origin[0], q[1] + o.y - r.origin[1], q[2], q[3]])); }
  catch (e) { if (!/detached|destroyed|closed|navigat/i.test(String(e?.message ?? e))) throw e; }
 }
 return byPlace(out);
});
// 입력칸에 넣어 둔 부탁 글의 조각에 밑줄(보내기 전). 조각이 입력칸의 보이는 칸 밖이면 입력칸 위에서 휠로 들인다.
export const IU = (phrase, shape = 'underline') => async (c, ctx) => {
 for (let n = 0; n < 24; n++) {
  const i = await codexEl(c, ctx, {input: true}), top = i.y - i.h / 2, bot = i.y + i.h / 2, hs = await frameHits(c, ctx, '[contenteditable=true]', phrase);
  if (hs.length !== 1) stop(ctx, 'Codex 입력칸에 「' + phrase + '」이 ' + hs.length + '곳 — 부탁 글(wg-common.mjs ASK)과 같은 글자인지 본다');
  const h = hs[0], dy = h[0][1] < top ? -80 : h.at(-1)[1] + h.at(-1)[3] > bot ? 80 : 0;
  if (!dy) return emph(c, ctx, {rects: h}, shape);
  if (!n) await c.move(i.x, i.y);
  await c.serial(() => ctx.p.mouse.wheel(0, dy)); await ctx.sleep(350);
 }
 stop(ctx, 'Codex 입력칸을 굴려도 「' + phrase + '」이 보이지 않음');
};
// Codex 답 안의 자리. find = '글 조각'(그 글자 자리, 대화에서 마지막 것) | {css, has, exact, nth}(그 요소의 상자, 마지막 것 — nth: -2면 끝에서 둘째). 짚기 전에 보이는 칸으로 굴린다.
const cGet = (c, ctx, find) => async () => {
 if (typeof find === 'string') { const hs = await frameHits(c, ctx, 'body', find); if (!hs.length) stop(ctx, 'Codex 답에 「' + find + '」이 없음 — FIND 표를 녹화 답에 맞춘다'); const h = hs.at(-1), u = union(h); return {...u, rects: h}; }
 const l = (await codexBoxes(c, ctx, find.css, find.has ?? null)).filter(b => !find.exact || b.text === find.has), b = l.at(find.nth ?? -1);
 if (!b) stop(ctx, 'Codex 답에 ' + find.css + (find.has ? ' 「' + find.has + '」' : '') + '이 ' + l.length + '개 — FIND 표를 녹화 답에 맞춘다');
 return b;
};
export const X = (find, shape = 'underline', o = {}) => async (c, ctx) => { const b = await codexScrollInto(c, ctx, cGet(c, ctx, find), o.frac ?? 0.3); await emph(c, ctx, b.rects ? {rects: b.rects} : em.box(b), shape, o); };
export const XK = (find, shape = 'underline', o = {}) => async (c, ctx) => { const b = await cGet(c, ctx, find)(), v = await codexView(c, ctx); if (b.y < v.top || b.y + b.h > v.bottom) stop(ctx, '함께 짚을 대상이 보이는 칸 밖 — ' + JSON.stringify(find)); await emph(c, ctx, b.rects ? {rects: b.rects} : em.box(b), shape, {keep: true, ...o}); };
export const codexE = (shape = 'box', o = {}) => E(em.codex(0.02, 0.06, 0.98, 0.9), shape, o);
// 승인 창(조건부 — 대본 wg0415): 「Default permissions」에서는 작업 폴더 안 쓰기에 창이 뜨지 않는다(촬영준비 길 9). 뜨면 창의 글에 이 부탁의 기능 파일(allow)이 있을 때만 Allow once를 누르고,
// 그 편에서 처음이면 wg0415를 말하며 누른다. features 밖의 파일이나 명령 실행(python run.py)을 묻는 창이면 누르지 않고 멈춘다 — 대본 제작 확인용대로 Deny 장면을 새 큐로 쓴다.
const MARK = ROOT + '/_승인말.txt';
const dialogText = (c, ctx) => c.serial(async () => {
 for (const f of ctx.p.frames()) {
  if (f === ctx.p.mainFrame()) continue;
  try { const l = f.getByText(UI.allow, {exact: true}); if (!(await l.count())) continue;
   return await l.first().evaluate(e => { let x = e; for (let k = 0; k < 8 && x.parentElement && (x.textContent ?? '').length < 60; k++) x = x.parentElement; return (x.textContent ?? '').replace(/\s+/g, ' ').trim(); }); }
  catch (e) { if (!/detached|destroyed|closed|navigat/i.test(String(e?.message ?? e))) throw e; }
 }
 return '';
});
const approve = async (c, ctx, h) => {
 if (!(await c.serial(() => ctx.p.text())).includes(UI.allow)) return false;
 const box = await dialogText(c, ctx);
 const file = (h.allow ?? []).find(f => box.includes(f));
 if (!file || /run\.py|python/.test(box)) stop(ctx, '승인 창이 떴는데 이 부탁의 기능 파일(' + ((h.allow ?? []).join(' · ') || '없음') + ') 쓰기가 아님 — 창의 글 「' + box.slice(0, 240) + '」. 누르지 않고 멈춤: 대본 제작 확인용대로 Deny와 그 까닭을 말하는 큐를 새 id로 더한 뒤 다시 찍는다');
 const press = async () => { const b = await codexEl(c, ctx, {text: UI.allow}); await c.clickAt(b.x, b.y); };
 const first = !(await fs.stat(MARK).then(() => true, () => false));
 if (first && !ctx.rehearsal) {
  await ctx.say(UI.approveCue, async () => { await X(file, 'underline')(c, ctx); await atPhrase(ctx, '이번 한 번만 허락해요'); await press(); }, {at: '고치려는 파일이'});
  await fs.writeFile(MARK, ctx.__wgSeg + ' ' + new Date().toISOString() + '\n'); ctx.__wg.waited.push(UI.approveCue);
 } else await press();
 return true;
};
// hold = {lines: [기다림 말 큐 …], term: '터미널에 뜰 글'(없으면 Codex 답), allow: [이 부탁이 쓰는 기능 파일 이름 …], approveCue: true(이 구간의 큐 표에 wg0415가 있다), timeout(ms)}
async function hold(c, ctx, h) {
 const w = ctx.__wg;
 if (!h.term && w.nosend) {   // 리허설(WG_NOSEND=1): 보내지 않았으니 기다리지 않고, 큐 수를 맞추려고 기다림 말을 말로만 센다
  for (const id of h.lines ?? []) { await ctx.say(id); w.waited.push(id); }
  if (h.approveCue) { await ctx.say(UI.approveCue); w.waited.push(UI.approveCue); }
  return;
 }
 if (!h.term && !w.since) stop(ctx, 'hold 앞에 send가 없음');
 const done = async () => h.term ? termHas(c, ctx, h.term) : (w.ans = await codexDone(w.since).then(r => r.done ? r : null)) != null;
 let said = false;
 for (const id of h.lines ?? []) {
  const q = ctx.__cue; if (q && !ctx.rehearsal && q.t0 != null) { const t = q.t0 + q.dur + PAUSE.cue - Date.now(); if (t > 0) await ctx.sleep(t); }
  if (!h.term && await approve(c, ctx, h)) continue;
  if (!ctx.rehearsal && await done()) break;
  await ctx.say(id, null, {gap: 0}); await markSaid(ctx, id); w.waited.push(id); said = true;
 }
 if (said) await speechEnd(ctx);
 for (const t0 = Date.now(), limit = h.timeout ?? 420000; !(await done());) {
  if (!h.term) await approve(c, ctx, h);
  if (Date.now() - t0 > limit) stop(ctx, (h.term ? '터미널에 「' + h.term + '」이 ' : 'Codex 답이 ') + limit / 1000 + '초 안에 오지 않음');
  await ctx.sleep(1000);
 }
 if (h.approveCue && ctx.rehearsal && !w.waited.includes(UI.approveCue)) { await ctx.say(UI.approveCue); w.waited.push(UI.approveCue); }
 if (!h.term && ctx.rehearsal) await fs.writeFile(ctx.out + '/답.md', w.ans.message ?? '');
 await ctx.sleep(PAUSE.result);
}

// ── 결과 화면(둘째 페이지) ── 대상 spec(아래 rfind): top(맨 위 머리) | sec(제목 h3에 든 글 — 그 칸, 「자세히 보기」 안 표 포함) · card(카드 제목 글, cardHas면 든 글) · cmp(대조 표의 둘째 칸 「물은 값 → 볼_열」) · row(표의 첫 칸 글) · bar(막대 이름, col a | b) · barcol(막대 한 줄 a | b — 머리와 그 칸의 막대 모두) · td(그 줄의 몇째 칸) · css(그 안의 요소) · has(든 글) · exact(같은 글) · nth · phrase(그 요소 안의 구절).
// 밑줄 · 띠는 글자 자리(구절이 있으면 구절), 테두리 · 동그라미는 요소 상자에 그린다.
export const rfind = s => {
 const norm = t => (t ?? '').replace(/\u00a0/g, ' ').replace(/\s+/g, ' ').trim();
 const vis = e => { const b = e.getBoundingClientRect(); return b.width > 0 && b.height > 0 && e.checkVisibility({checkVisibilityCSS: true}); };
 let scopes = [document];
 if (s.top) scopes = [document.querySelector('main > header')];
 else if (s.sec != null) scopes = [...document.querySelectorAll('main > section, details.more .in')].filter(x => norm(x.querySelector('h3')?.textContent).includes(s.sec));
 let es = [];
 for (const sc of scopes) {
  if (!sc) continue;
  let base = [sc];
  if (s.card != null) base = [...sc.querySelectorAll('.cards .card')].filter(cd => { const t = norm(cd.querySelector('.ch b')?.textContent); return s.cardHas ? t.includes(s.card) : t === s.card; });
  if (s.cmp != null) base = [...sc.querySelectorAll('.tbl.cmp tbody tr')].filter(tr => norm(tr.cells[1]?.textContent) === s.cmp);
  if (s.row != null) base = [...sc.querySelectorAll('tbody tr')].filter(tr => norm(tr.cells[0]?.textContent) === s.row);
  if (s.td != null) base = base.map(tr => tr.cells?.[s.td]).filter(Boolean);
  if (s.barcol != null) { const k = s.barcol === 'a' ? 0 : 1; base = [...sc.querySelectorAll('.bars')].map(bs => [bs.querySelectorAll('.bh')[k], ...[...bs.querySelectorAll('.bn')].map(n => k ? n.nextElementSibling?.nextElementSibling : n.nextElementSibling)].filter(Boolean)); }
  if (s.bar != null) base = [...sc.querySelectorAll('.bars .bn')].filter(b => norm(b.textContent) === s.bar).map(b => s.col === 'a' ? b.nextElementSibling : s.col === 'b' ? b.nextElementSibling?.nextElementSibling : b).map(x => s.col ? x?.querySelector('em') : x).filter(Boolean);
  if (s.barcol != null) { es.push(...base); continue; }
  for (const b of base) es.push(...(s.css ? b.querySelectorAll(s.css) : [b]));
 }
 if (s.barcol != null) {   // 막대 한 줄(머리와 그 칸의 막대 모두) — 묶음 하나의 상자
  const col = es.find(Array.isArray); if (!col || es.length !== 1) return {n: es.length};
  const rs = col.map(e => e.getBoundingClientRect()), x = Math.min(...rs.map(r => r.left)), y = Math.min(...rs.map(r => r.top)), box = [x, y, Math.max(...rs.map(r => r.right)) - x, Math.max(...rs.map(r => r.bottom)) - y];
  return {n: 1, box, rects: [box], vh: innerHeight, top: scrollY};
 }
 es = [...new Set(es)].filter(vis);
 if (s.has != null) es = es.filter(e => norm(e.textContent).includes(s.has));
 if (s.exact != null) es = es.filter(e => norm(e.textContent) === s.exact);
 if (s.nth != null) es = es.length ? [es.at(s.nth)].filter(Boolean) : [];
 if (es.length !== 1) return {n: es.length};
 const e = es[0], b = e.getBoundingClientRect();
 const merge = rs => { const ls = []; for (const q of rs) { if (q.width <= 0 || q.height <= 0) continue; const m = q.top + q.height / 2, l = ls.find(l => m > l[1] && m < l[3]); if (l) { l[0] = Math.min(l[0], q.left); l[1] = Math.min(l[1], q.top); l[2] = Math.max(l[2], q.right); l[3] = Math.max(l[3], q.bottom); } else ls.push([q.left, q.top, q.right, q.bottom]); } return ls.map(l => [l[0], l[1], l[2] - l[0], l[3] - l[1]]); };
 const g = document.createRange();
 if (s.phrase != null) {
  const w = document.createTreeWalker(e, NodeFilter.SHOW_TEXT), raw = []; let flat = '', map = [], sp = true;
  for (let n; (n = w.nextNode());) for (let i = 0; i < n.data.length; i++) { const ch = n.data[i].replace(/\u00a0/, ' '); if (/\s/.test(ch)) { if (sp) continue; sp = true; flat += ' '; map.push([n, i]); } else { sp = false; flat += ch; map.push([n, i]); } }
  const want = norm(s.phrase), at = flat.indexOf(want);
  if (at < 0 || flat.indexOf(want, at + 1) >= 0) return {n: -1, why: '구절 「' + s.phrase + '」이 대상 안에 ' + (at < 0 ? 0 : '여러') + '번'};
  g.setStart(map[at][0], map[at][1]); const z = map[at + want.length - 1]; g.setEnd(z[0], z[1] + 1);
 } else g.selectNodeContents(e);
 const rects = merge([...g.getClientRects()]);
 return {n: 1, box: [b.x, b.y, b.width, b.height], rects, vh: innerHeight, top: scrollY};
};
const rnow = (c, ctx, spec) => c.serial(() => ctx.p.evaluate(rfind, spec));
// 대상이 화면 안(위 70px · 아래 70px 여백)에 다 들어올 때까지 휠로 굴린다. at = 'top'이면 화면 위쪽에 둔다.
export const see = (spec, o = {}) => async (c, ctx) => {
 let last = null;
 for (let n = 0; n < 40; n++) {
  const r = await rnow(c, ctx, spec);
  if (r.n !== 1) stop(ctx, '결과 화면에 보이는 대상이 ' + r.n + '개' + (r.why ? '(' + r.why + ')' : '') + ' — ' + JSON.stringify(spec) + ' — 그 take의 결과 화면에 맞춰 FIND 표를 고친다');
  const u = union(r.rects.length ? r.rects : [r.box]), H = o.box ? r.box[3] : u.h, Y = o.box ? r.box[1] : u.y;
  const lo = 70, hi = Math.max(lo, r.vh - H - 70), want = o.at === 'top' ? lo : Math.min(hi, r.vh * 0.3);
  const ok = o.at === 'top' ? Math.abs(Y - lo) < 30 : (Y >= lo && Y <= hi);
  const stuck = last !== null && Math.abs(r.top - last) < 1;
  if (ok || (stuck && Y >= 0 && Y + H <= r.vh)) return r;
  if (stuck) stop(ctx, '결과 화면을 굴려도 대상이 화면 안에 다 들어오지 않음(높이 ' + Math.round(H) + 'px) — ' + JSON.stringify(spec));
  last = r.top; await c.clearEmph();
  await c.serial(() => ctx.p.mouse.wheel(0, Math.max(-600, Math.min(600, Y - want)))); await ctx.sleep(450);
 }
 stop(ctx, '결과 화면에서 대상이 자리를 잡지 못함 — ' + JSON.stringify(spec));
};
export const R = (spec, shape = 'underline', o = {}) => async (c, ctx) => {
 const boxy = (shape === 'box' || shape === 'circle') && spec.phrase == null;
 if (!o.keep) await see(spec, {box: boxy})(c, ctx);
 const r = await rnow(c, ctx, spec); if (r.n !== 1) stop(ctx, '결과 화면 대상이 ' + r.n + '개 — ' + JSON.stringify(spec));
 await emph(c, ctx, boxy ? {box: r.box} : {rects: r.rects}, shape, o);
};
export const pin = spec => async (c, ctx) => { await see(spec, {at: 'top', box: true})(c, ctx); };
// 학생의 F5: 결과 화면을 다시 읽고(촬영준비 길 6) 제목을 확인한 뒤 화살표를 그 자리에 다시 놓는다. 굴려 둔 자리는 남으므로 맨 위로 휠을 굴린다(말하지 않는 스크롤 — 영상 V-14).
export const f5 = title => async (c, ctx) => {
 const at = await pointerAt(c, ctx);
 await c.gate(); await c.clearEmph(); await c.serial(() => ctx.p.reload());
 for (let n = 0; ; n++) { const t = await c.serial(() => ctx.p.evaluate(() => document.readyState === 'complete' && !document.getElementById('recording-pointer') ? document.title : null)); if (t != null) { if (!t.startsWith(title)) stop(ctx, '새로 고친 결과 화면의 제목이 「' + title + '」가 아니라 「' + t.split(' · ')[0] + '」 — 앞 구간의 명령이 돌았는지 본다'); break; } if (n > 80) stop(ctx, '결과 화면이 다시 읽히지 않음'); await ctx.sleep(100); }
 await c.installPointer(at); rep(ctx, {op: 'key', target: 'F5(결과 화면 새로 고침)'}); await ctx.sleep(500);
 for (let n = 0; n < 40 && await c.serial(() => ctx.p.evaluate(() => scrollY > 0)); n++) { await c.serial(() => ctx.p.mouse.wheel(0, -600)); await ctx.sleep(350); }
};
// 접힌 「자세히 보기」(근거 표)를 편다 — 쿼리 결과 표가 그 안에 있다
export const openMore = async (c, ctx) => {
 const s = {css: 'details.more > summary'}; const r = await see(s, {box: true})(c, ctx);
 if (await c.serial(() => ctx.p.evaluate(() => document.querySelector('details.more').open))) return;
 await c.clickAt(r.box[0] + 60, r.box[1] + r.box[3] / 2); await ctx.sleep(500);
 if (!(await c.serial(() => ctx.p.evaluate(() => document.querySelector('details.more').open)))) stop(ctx, '「자세히 보기」가 펴지지 않음');
};
export const TOP = {top: true, css: '.verdict strong'};
export const TOPS = phrase => ({top: true, css: '.verdict span', ...(phrase ? {phrase} : {})});

// ── 화면 글(영어 화면) · 조건부 큐 ── 녹화 화면에서 글자가 다르면 여기만 고친다(미검증: 승인 창 · 폴더 닫기 · 최근 폴더 메뉴의 글자)
export const UI = {allow: 'Allow once', approveCue: 'wg0415', file: 'File', closeFolder: 'Close Folder', openRecent: 'Open Recent', recentHas: 'wgp-ba8da7d5'};
// 결과 화면의 제목 앞머리(랩 actions.py COMMANDS의 이름)
export const TITLE = {sources: '원자료와 모델', db: '랩 DB 준비', status: '모델과 DB 개수', expected: '기대 답', constraints: '유일 제약 걸기', probe: '넣기 전 실험', load: '모델 적재', repeat: '같은 적재 다시 실행',
 sensors: '설비별 센서', parts: '설비별 교체 부품', usage: '부품의 사용 설비', changes: '수정본 살펴보기', update: '수정본 반영', export: '그래프 저장', check: '구조 검사'};

// ── 부탁 글(대본 조작 칸의 글 그대로 — 대본을 고치면 여기도 고친다) ──
export const ASK = {
 wg0302: '파일은 바꾸지 말고 `data/model/schema.json`과 `graph.json`을 살펴봐 줘. 종류마다 몇 개인지, 관계는 몇 개이고 어느 쪽에서 어느 쪽으로 가는지, 식별자는 어떻게 지었는지 알려 주고, 원자료 줄 수와 다른 곳이 있으면 원자료 줄(파일:줄)로 까닭을 짚어 줘.',
 wg0409: '파일은 바꾸지 말고, 설비마다 한계가 없는 센서 · 교체 부품이 없는 구성 요소 · 원자료에 사내 품번과 다른 표기로 적힌 교체 부품이 몇 줄씩 있는지 표로 보여 줘. 예 줄은 파일:줄로 짚어 줘.',
 wg0411: '세 역량 질문의 기대 답 후보를 원자료와 제공 모델에서 찾아 근거 줄(파일:줄)과 함께 표로 보여 줘. ① 설비의 구성 요소마다 어떤 센서가 붙는가? ② 설비의 구성 요소마다 어떤 교체 부품이 들어가는가? ③ 부품을 어느 설비가 쓰고 그 설비의 상태는 무엇인가? 다른 표기(예전 품번 · 제조사 품번 · 표기 변형)나 원자료에 없는 품번으로 물으면 어떻게 무엇으로 구별되는가? 질문 1은 설비 HYD-01로, 질문 2는 설비 HYD-02로 물어 줘. 꼴은 `expected.csv` 빈 틀의 첫 줄을 따르고, 볼_열은 component · tag · quantity · limit · part · asset · status · note 가운데 그 줄에 맞는 이름으로 붙여 줘. 질문 1은 같은 설비로 볼_열이 component+tag, tag+quantity, tag+limit인 줄을 하나씩 두고(기대 답은 결과 줄마다 「값=값」), 한계가 없는 센서는 「없음」으로 적어 줘. 질문 2의 부품은 사내 품번으로 적고, 교체 부품이 없는 구성 요소는 빠지지 않게 품번 칸을 「없음」으로 적어 줘. 원자료에 없는 품번으로 물은 줄은 볼_열을 note로, 기대 답을 「원자료에 없는 품번」으로 적어 줘. 질문 3은 수정본에서 상태가 바뀌는 설비가 쓰는 부품과 그 부품의 다른 표기로 묻고, 수정본을 반영하기 전의 답으로 해 줘. 파일은 바꾸지 마.',
 wg0414: '방금 표에서 내가 근거 줄을 열어 본 질문 1의 HYD-01 component+tag 줄은 맞았어. 표의 줄을 `expected.csv`에 적어 줘. 다른 파일은 바꾸지 마.',
 wg0503: '`data/model/schema.json`의 종류(레이블)마다 식별자 `id`에 유일 제약을 거는 쿼리를 `constraints.cypher`에 작성해 줘. 다시 실행해도 오류가 나지 않게 IF NOT EXISTS를 쓰고 쿼리 끝에 ;를 붙여 줘. 데이터를 넣는 쿼리와 다른 파일은 아직 작성하지 마. 작성한 뒤 쿼리 한 줄이 무엇을 하는지 쉬운 말로 풀어 줘.',
 wg0604: '파일은 바꾸지 말고 예측해 줘. 식별자 id에 유일 제약이 걸린 그래프 DB에 ① 같은 노드를 CREATE로 두 번 넣으면 ② MERGE의 패턴에 id와 name을 함께 적었는데 name이 조금 다른 줄을 넣으면 ③ MERGE 패턴의 속성 이름을 id 대신 ID로 적으면 ④ 관계의 화살표를 모델과 거꾸로 넣으면 ⑤ 끝 노드가 아직 없는 관계를 넣으면, 각각 DB가 거절할지 받아 줄지와 그 까닭을 한 줄씩 말해 줘.',
 wg0703: '`load.cypher`에 쿼리 셋을 써 줘. ① Asset 노드: 행은 `data/equipment.csv`의 줄 그대로 넘어오니, `data/model/schema.json`에서 식별자를 무엇으로 짓고 어느 열을 어느 속성에 넣는지 찾아 그대로 옮겨 줘. 스키마에서 자료형이 날짜인 속성은 date(…)로 바꿔 넣어 줘. MERGE의 패턴에는 바뀌지 않는 식별자만 적고 나머지 값은 처음 만들 때만 넣어 줘(ON CREATE SET). ② 설비와 구성 요소를 잇는 관계 ③ 구성 요소와 부품을 잇는 관계: 양 끝 노드를 `schema.json`의 레이블과 식별자로 찾아 MERGE로 잇고, ③에는 관계에 붙는 값(row.props.source_text)도 처음 만들 때 넣어 줘. 노드 쿼리를 관계 쿼리보다 먼저 적고, 행은 $rows로 받고, 쿼리마다 바로 위에 `// 넣을 것: <종류 또는 관계 이름>`을 적어 줘. 다른 파일은 바꾸지 마.',
 wg0801: '`query.cypher`에 질문 1만 작성해 줘. 설비 코드를 $ 자리 하나로 받아 그 설비의 구성 요소 이름(component)과 거기 붙은 센서의 태그(tag), 그 센서가 재는 물리량의 이름(quantity), 단위 · 정상값 · 한계(limit)를 돌려줘. 없는 한계를 0으로 채우지 마. 질문 2와 3은 내가 결과를 본 뒤 하나씩 요청할게.',
 wg0901: '`query.cypher`에 질문 2만 더해 줘. 설비 코드를 $ 자리 하나로 받아 그 설비의 구성 요소마다 이어진 교체 부품의 사내 품번(part)과 품명을 돌려줘. 교체 부품이 없는 구성 요소도 빠지지 않게 「없음」으로 돌려줘. 질문 1은 그대로 두고, 질문 3은 내가 결과를 본 뒤 요청할게.',
 wg1001: '`query.cypher`에 질문 3을 더해 줘. 먼저 사내 품번을 $ 자리 하나로 받아 그 부품의 사내 품번(part)과 그 부품을 쓰는 설비 코드(asset), 설비의 상태(status)를 돌려주는 쿼리만 써 줘. 질문 1 · 2는 그대로 둬.',
 wg1004: '결과 화면에서 「같음」이 아닌 줄이야: 물은 값 RF-10, 기대 답 HYD-01 · HYD-02 · HYD-03 · HYD-04 · HYD-07, 실제 결과 0줄. 왜 다른지 쿼리와 모델 파일로 설명해 줘. 먼저 파일은 바꾸지 마.',
 wg1006: '질문 3 쿼리가 부품의 다른 이름(other_codes)으로도 찾게 고쳐 줘. 원자료에 없는 품번이면 note 열에 「원자료에 없는 품번」이라고 한 줄 돌려줘. 질문 1 · 2는 그대로 둬.',
 wg1104: '파일은 바꾸지 말고 `data/changes/`의 수정본을 살펴봐 줘. 불용이 된 설비와 목록에서 빠진 센서를 그래프에 상태로 남길 때와 지울 때 질문 1 · 3의 답이 각각 어떻게 달라지는지, 그리고 그래프를 보는 사람이 무엇을 보고 무엇을 못 보게 되는지 견줘 줘. 센서를 상태로 남기려면 스키마에 무엇을 더 정해야 하는지도 알려 주고, 추천과 이유도 말해 줘.',
 wg1111: '두 지점을 정했어. 「불용 결정 설비」는 「상태만 바꿔 남긴다」로, 이유는 수정본이 삭제가 아니라 수정으로 적었고 팔리기 전까지는 공장에 있는 설비라 들어간 부품을 물을 일이 남아서이고 열어 본 근거 줄은 data/changes/2026-10-20/equipment_changes.csv:3이야. 그래서 달라지는 답은 질문 3에서 HYD-07이 「불용(매각 예정)」 상태로 계속 나오는 거야. 「목록에서 빠진 센서」는 「떼어 냈다는 상태로 남긴다」로, 이유는 있었는데 고장으로 떼어 낸 센서가 원래 없던 것처럼 보이면 안 되기 때문이고 열어 본 근거 줄은 data/changes/2026-10-20/sensor_changes.csv:3이야. 그래서 달라지는 답은 질문 1에서 HYD-01의 VS1이 「떼어 냄」 상태로 센서 목록에 남는 거야. `decisions.csv`의 두 지점 줄에 적어 줘. 다른 파일은 바꾸지 마.',
 wg1202: '`decisions.csv`의 내 선택대로 수정본을 반영한 뒤의 답으로 `expected.csv`의 질문 1 · 3 줄을 고치고, 수정본에 새로 등록된 표기로 물은 질문 3 줄을 하나 더해 줘. 질문 1은 목록에서 빠진 센서가 붙은 설비로 물은 줄을 두고, 센서를 상태로 남기기로 했으면 그 설비로 볼_열이 tag+status인 줄도 하나 더해 줘(상태가 없는 센서는 「없음」). 다른 파일은 바꾸지 말고, 반영한 뒤 종류마다 있어야 할 개수를 원자료와 수정본의 줄로 세어 알려 줘.',
 wg1207: '센서에 둘 상태 속성의 이름과 자료형, 필수 여부를 나에게 물어보고, 내 답대로 `schema_additions.csv`에 한 줄 적어 줘. 다른 파일은 바꾸지 마.',
 wg1208: '이름은 status, 자료형은 글자, 필수는 아니오로 해 줘. 이유는 떼어 낸 센서를 지우지 않고 남기려면 그 상태를 적을 자리가 있어야 해서이고, 열어 본 근거 줄은 data/changes/2026-10-20/sensor_changes.csv:3이야.',
 wg1210: '`query.cypher`의 질문 1이 방금 정한 센서의 상태 속성도 status 열로 돌려주게 고쳐 줘. 질문 2 · 3은 그대로 둬.',
 wg1212: '수정본을 `update.cypher`에 반영해 줘. 먼저 수정본의 열 이름을 모델의 어느 속성에 넣는지 표로 보여 줘. 쿼리마다 바로 위에 `// 반영할 것: <수정본 파일 이름> <변경>`을 적고 그 줄들을 $rows로 받아, 식별자로 노드를 찾아 수정본에 적힌 칸만 고쳐 줘(수정본에 없는 다른 속성은 건드리지 마). 설비 코드 같은 수정본의 값은 쿼리에 적지 말고 row의 칸으로 받아 줘. 수로 담을 값은 수로, 날짜로 담을 값은 날짜로 바꿔 넣고, 새 표기는 이미 있으면 다시 더하지 않게 해 줘. 불용 설비와 삭제 줄은 `decisions.csv`의 내 선택대로 하고(상태로 남기는 센서는 `schema_additions.csv`에 정한 속성에 적어 줘), 지우는 범위가 분명하지 않으면 쓰기 전에 물어봐.',
};

// ── 펜 그림(프레임 px 1920×1080 — 웹 VS Code의 편집기 칸은 가로 약 430~1340, 터미널은 아래 약 750부터. 결과 화면 구간의 그림은 결과 화면 위) ──
// 여는 말: 모델 파일 두 장 → 그래프 DB → 보전팀의 질문과 답(원통 모양이 그림 층에 없어 「그래프 DB」 칸으로 그린다)
export const FLOW = {id: '파일에서 그래프 DB로', board: [450, 170, 880, 380], items: [
 {id: 'schema', kind: 'box', at: [490, 240, 170, 80], text: '스키마'},
 {id: 'data', kind: 'box', at: [490, 380, 170, 80], text: '데이터'},
 {id: 'db', kind: 'box', at: [800, 300, 200, 110], text: '그래프 DB'},
 {id: 'ask', kind: 'box', at: [1090, 300, 210, 110], text: '보전팀의 질문\n→ 답'},
 {id: 'a1', kind: 'arrow', from: 'schema', to: 'db'}, {id: 'a2', kind: 'arrow', from: 'data', to: 'db'}, {id: 'a3', kind: 'arrow', from: 'db', to: 'ask'},
]};
// 세 칸(오늘 할 일) — 1장에서 긋고 7 · 10 · 11 · 12 · 13장에서 같은 정의로 다시 띄운다(대본은 「글상자 세 칸」 — 한 칸씩 켜고 끝난 표시 · 「식별자」 선을 긋는 일은 글상자로 할 수 없어 펜 그림 칸으로 그린다).
// pre = 준비, l1~l3 = AI가 쓴 쿼리 앞뒤로 우리가 하는 일, d1~d3 = 끝난 표시, key · k1~k3 = 세 번 모두 기댄 것
export const THREE = {id: '오늘 할 일 세 칸', board: [450, 140, 880, 500], items: [
 {id: 'pre', kind: 'text', at: [485, 165], text: '준비 — 견줄 것 마련하기', size: 0.85},
 {id: 's1', kind: 'box', at: [480, 230, 250, 96], text: '① 넣는다'},
 {id: 's2', kind: 'box', at: [760, 230, 270, 96], text: '② 묻는다 ·\n기대 답과 맞춘다'},
 {id: 's3', kind: 'box', at: [1060, 230, 250, 96], text: '③ 바뀐 것만\n고친다'},
 {id: 'd1', kind: 'text', at: [590, 335], text: '✓', color: 'red', size: 1.5}, {id: 'd2', kind: 'text', at: [880, 335], text: '✓', color: 'red', size: 1.5}, {id: 'd3', kind: 'text', at: [1170, 335], text: '✓', color: 'red', size: 1.5},
 {id: 'l1', kind: 'text', at: [500, 420], text: '받기 전 — 들어갈 것을 정해 말한다'},
 {id: 'l2', kind: 'text', at: [500, 485], text: '받은 뒤 — 돌리기 전에 읽는다'},
 {id: 'l3', kind: 'text', at: [500, 550], text: '돌린 뒤 — 개수 · 기대 답에 댄다'},
 {id: 'key', kind: 'box', at: [785, 520, 220, 84], text: '식별자'},
 {id: 'k1', kind: 'arrow', from: 'key', to: 's1'}, {id: 'k2', kind: 'arrow', from: 'key', to: 's2'}, {id: 'k3', kind: 'arrow', from: 'key', to: 's3'},
]};
// 모델이 그래프 DB에 들어가는 모양 석 줄(3장) + 조건은 따라 들어가지 않는다(5장)
export const MAP = {id: '모델이 들어가는 모양', board: [450, 150, 880, 400], items: [
 {id: 'm1', kind: 'text', at: [500, 190], text: '클래스  →  레이블'},
 {id: 'm2', kind: 'text', at: [500, 255], text: '인스턴스  →  노드'},
 {id: 'm3', kind: 'text', at: [500, 320], text: '관계  →  이름과 방향이 있는 화살표'},
 {id: 'm4', kind: 'text', at: [500, 400], text: '조건  →  따라 들어가지 않는다', color: 'red'},
 {id: 'm5', kind: 'text', at: [540, 465], text: '→  DB에 직접 건다: 유일 제약'},
]};
// 관계 그림: 종류 여섯과 화살표 다섯(화살표 위에 관계 이름). 3장에서 긋고 4 · 7 · 8 · 10장에서 쿼리 옆(편집기 아래쪽 — 쿼리 줄을 가리지 않는다)에 다시 띄운다.
export const REL = {id: '종류 여섯과 관계 다섯', board: [450, 540, 880, 470], items: [
 {id: 'asset', kind: 'box', at: [480, 610, 150, 70], text: '설비'},
 {id: 'comp', kind: 'box', at: [710, 610, 180, 70], text: '구성 요소'},
 {id: 'sensor', kind: 'box', at: [970, 610, 140, 70], text: '센서'},
 {id: 'qty', kind: 'box', at: [1180, 610, 130, 70], text: '물리량'},
 {id: 'part', kind: 'box', at: [600, 830, 150, 70], text: '부품'},
 {id: 'unit', kind: 'box', at: [860, 830, 150, 70], text: '실물'},
 {id: 'has', kind: 'arrow', from: 'asset', to: 'comp'}, {id: 'mon', kind: 'arrow', from: 'comp', to: 'sensor'}, {id: 'obs', kind: 'arrow', from: 'sensor', to: 'qty'},
 {id: 'uses', kind: 'arrow', from: 'comp', to: 'part'}, {id: 'inst', kind: 'arrow', from: 'comp', to: 'unit'},
 {id: 'thas', kind: 'text', at: [585, 568], text: 'HAS_COMPONENT', size: 0.62}, {id: 'tmon', kind: 'text', at: [860, 568], text: 'MONITORED_BY', size: 0.62}, {id: 'tobs', kind: 'text', at: [1105, 568], text: 'OBSERVES', size: 0.62},
 {id: 'tuses', kind: 'text', at: [545, 745], text: 'USES_PART', size: 0.62}, {id: 'tinst', kind: 'text', at: [900, 745], text: 'INSTALLED_UNIT', size: 0.62},
 {id: 'chk', kind: 'text', at: [1050, 835], text: '넣은 뒤 개수 ·\n방향으로 확인', size: 0.75},
]};
export const REL_ALL = ['asset', 'has', 'thas', 'comp', 'mon', 'tmon', 'sensor', 'obs', 'tobs', 'qty', 'uses', 'tuses', 'part', 'inst', 'tinst', 'unit'];
// 4장: 세 질문 글상자 밑에 적는 약속(대본 「글상자 아래에 쓴다」 — 글상자 줄마다 밑에 쓸 자리가 없어, 글상자 아래 판에 그 질문 번호를 붙여 적은 차례대로 쓴다)
export const QNOTE = ['① 설비의 구성 요소마다 어떤 센서가 붙나', '② 구성 요소마다 어떤 교체 부품이 들어가나', '③ 부품을 어느 설비가 쓰고 그 설비의 상태는', '    — 다른 표기 · 없는 품번으로 물으면'];
export const QNOTE_AT = [460, 96];
export const ANS = {id: '기대 답에 정해 둘 것', board: [450, 330, 880, 300], items: [
 {id: 'a1', kind: 'text', at: [480, 350], text: '③ 없는 품번 → 「원자료에 없는 품번」 한 줄', size: 0.8},
 {id: 'a2', kind: 'text', at: [480, 405], text: '② 부품 없는 구성 요소 → 「없음」으로 남김', size: 0.8},
 {id: 'a3', kind: 'text', at: [480, 460], text: '① 한계가 없는 센서 → 0이 아니라 「없음」', size: 0.8},
 {id: 'a4', kind: 'text', at: [480, 515], text: '① 답은 짝으로 세 줄 — 구성 요소=센서 · 센서=재는 것 · 센서=한계', size: 0.66},
 {id: 'a5', kind: 'text', at: [480, 570], text: '② 부품은 사내 품번으로', size: 0.8},
]};
// 6장: 넣기 전 실험 다섯 가지와 강사의 예측(대본 「글상자 다섯 줄을 한 줄씩 켠다」 — 한 줄씩 켜고 옆에 예측을 적으려고 펜 그림 글로 쓴다)
export const EXP = {id: '넣기 전 실험 다섯', board: [450, 150, 880, 400], items: [
 {id: 'e1', kind: 'text', at: [480, 180], text: '① CREATE로 같은 노드를 두 번', size: 0.85},
 {id: 'e2', kind: 'text', at: [480, 245], text: '② MERGE 괄호 안에 id와 name — name이 조금 다르면', size: 0.78},
 {id: 'e3', kind: 'text', at: [480, 310], text: '③ 속성 이름을 id 대신 ID로', size: 0.85},
 {id: 'e4', kind: 'text', at: [480, 375], text: '④ 관계의 화살표를 거꾸로', size: 0.85},
 {id: 'e5', kind: 'text', at: [480, 440], text: '⑤ 끝 노드가 아직 없는 관계', size: 0.85},
 {id: 'g1', kind: 'text', at: [1160, 180], text: '거절?', color: 'red', size: 0.85},
 {id: 'g4', kind: 'text', at: [1160, 375], text: '받아 줌?', color: 'red', size: 0.85},
]};
// 6장 결과 화면: 정리 다섯 줄 · Codex의 예측 — 넣기 전 실험 카드의 둘째 줄 오른쪽 빈자리(카드 묶음을 화면 위 40px에 둔 뒤 — pin(SEC6))
export const SEC6 = {sec: '넣는 쿼리를 이렇게 쓰면 DB는 뭐라고 할까', css: '.cards'};
export const SUM5 = {id: '넣는 쿼리를 시키는 법', board: [1215, 440, 485, 465], items: [
 {id: 't1', kind: 'text', at: [1240, 460], text: 'MERGE로', size: 0.8},
 {id: 't2', kind: 'text', at: [1240, 540], text: '괄호 안에는 식별자만', size: 0.8},
 {id: 't3', kind: 'text', at: [1240, 620], text: '노드 먼저, 관계는 그다음', size: 0.8},
 {id: 't4', kind: 'text', at: [1240, 700], text: '방향 · 속성 이름은\n읽어서 확인', size: 0.8},
 {id: 't5', kind: 'text', at: [1240, 820], text: '넣은 뒤 개수 견주기', size: 0.8},
]};
// 7장: 설비 표의 다섯 줄이 $rows로 넘어가 한 줄씩 풀리는 모양 — 편집기 아래쪽
export const ROWS = {id: '명단과 한 줄', board: [450, 560, 880, 420], items: [
 {id: 'list', kind: 'box', at: [490, 640, 250, 120], text: '설비 표의 5줄'},
 {id: 'slot', kind: 'box', at: [860, 665, 170, 70], text: '$rows'},
 {id: 'give', kind: 'arrow', from: 'list', to: 'slot'},
 {id: 'r1', kind: 'box', at: [1100, 610, 200, 54], text: 'HYD-01 …', size: 0.85}, {id: 'r2', kind: 'text', at: [1115, 678], text: 'HYD-02 …', size: 0.85}, {id: 'r3', kind: 'text', at: [1115, 722], text: 'HYD-03 …', size: 0.85},
 {id: 'r4', kind: 'text', at: [1115, 766], text: 'HYD-04 …', size: 0.85}, {id: 'r5', kind: 'text', at: [1115, 810], text: 'HYD-07 …', size: 0.85},
 {id: 'out', kind: 'arrow', from: 'slot', to: 'r1'}, {id: 'row', kind: 'text', at: [1240, 568], text: 'row', color: 'red', size: 0.85},
]};
// 7장: 설비 쿼리의 SET 짝을 견줄 스키마의 source 묶음(대본 「schema.json의 Asset source 묶음을 옆에 띄워」 — 그 묶음을 글상자로 띄운다)
export const SRC8 = ['"code": "설비코드",', '"name": "설비명",', '"model": "모델",', '"status": "상태",', '"maker": "제조사",', '"serial": "일련번호",', '"functional_location": "기능위치",', '"installed": "설치일"'];
export const SRC8_AT = [760, 285];   // 편집기 가운데 아래쪽 — 넣는 쿼리 셋(1~9행)을 가리지 않고 터미널 위에서 끝난다
// 7장: 레이블과 함께 찾기
export const SEEK = {id: '노드를 찾는 두 길', board: [450, 600, 880, 240], items: [
 {id: 'scan', kind: 'text', at: [490, 640], text: '아이디만 — 노드 114개를 다 훑는다', size: 0.85},
 {id: 'seek', kind: 'text', at: [490, 730], text: '레이블 + 아이디 — 레이블마다 만든 아이디 목록에서 바로', size: 0.78},
]};
// 11장: 지운다는 것 — HYD-07과 그 구성 요소 다섯(data/components.csv 38~42행). 가위표를 친 뒤 화살표를 지운다(대본 「흐려진다」 — 획을 흐리게 하는 일이 그림 층에 없어 지운다)
export const DEL = {id: '설비를 지우면', board: [450, 170, 880, 470], items: [
 {id: 'h7', kind: 'box', at: [800, 220, 180, 80], text: 'HYD-07'},
 ...['펌프', '모터', '커플링', '탱크', '리턴 필터'].flatMap((t, i) => [{id: 'c' + i, kind: 'box', at: [480 + i * 168, 500, 150, 70], text: t, size: 0.85}, {id: 'a' + i, kind: 'arrow', from: 'h7', to: 'c' + i}]),
 {id: 'x', kind: 'text', at: [1000, 215], text: '✕', color: 'red', size: 2},
]};
export const DEL_ALL = ['h7', 'c0', 'c1', 'c2', 'c3', 'c4', 'a0', 'a1', 'a2', 'a3', 'a4'];
// 13장 맺음: 층 그림 — 06-1 여는 장(wv0102 · wv0108)의 층 그림(segs/wv-common.mjs LAYERS의 L1 · L1t · L2 · L3 · r2~r4)과 같은 자리 · 같은 글. 그 정의를 고치면 여기도 맞춘다(공용 자리로 옮길 거리 — 판정/녹화모듈_07.md).
export const LAYER = {id: '층 셋', board: [110, 110, 1700, 860], items: [
 {id: 'L1', kind: 'box', at: [330, 700, 1010, 150], text: ''},
 {id: 'L1t', kind: 'text', at: [360, 755], text: '설비 · 구성 요소 · 센서 · 부품'},
 {id: 'L2', kind: 'box', at: [330, 540, 560, 110], text: '작업 절차 · 판단 조건\n(매뉴얼에서 사람이 옮김)'},
 {id: 'L3', kind: 'box', at: [330, 380, 560, 110], text: '문서에서 AI가 뽑고\n사람이 확인한 지식'},
 {id: 'r2', kind: 'text', at: [200, 755], text: '2회차'}, {id: 'r3', kind: 'text', at: [200, 575], text: '3회차'}, {id: 'r4', kind: 'text', at: [200, 415], text: '4회차'},
 {id: 'ok', kind: 'text', at: [1250, 735], text: '✓', color: 'red', size: 1.6},
 {id: 'v1', kind: 'text', at: [420, 648], text: '↓', color: 'red', size: 1.1}, {id: 'v2', kind: 'text', at: [600, 648], text: '↓', color: 'red', size: 1.1}, {id: 'v3', kind: 'text', at: [780, 648], text: '↓', color: 'red', size: 1.1},
 {id: 'v4', kind: 'text', at: [500, 488], text: '↓', color: 'red', size: 1.1}, {id: 'v5', kind: 'text', at: [700, 488], text: '↓', color: 'red', size: 1.1},
]};
// 6장 끝: Codex의 예측 다섯 줄(녹화 답을 줄여 적는다 — FIND.wg0612)과 맞은 줄의 체크
export const predFig = () => ({id: 'Codex의 예측', board: [1215, 440, 485, 465], items: [
 {id: 'h', kind: 'text', at: [1240, 452], text: 'Codex의 예측', size: 0.8},
 ...FIND.wg0612.lines.flatMap((t, i) => [{id: 'p' + (i + 1), kind: 'text', at: [1240, 520 + i * 74], text: t, size: 0.72}, {id: 'k' + (i + 1), kind: 'text', at: [1640, 513 + i * 74], text: '✓', color: 'red', size: 1.1}]),
]});

// ── 찾는 글 표 ── 녹화한 답 · Codex가 쓴 파일 · 그 take의 결과 화면에 맞춰 여기만 고친다. 지금 값: 완성본 파일의 글자와 강사 길로 돌린 결과 화면(판정/녹화모듈_07.md 「확인한 것」).
// Codex 답의 자리: '글 조각'(그 글자 자리) 또는 {css, has, exact, nth}(그 요소). 표는 table, 표의 줄 tr · 칸 td, 굵은 글은 strong, 목록은 li, 문단은 p(촬영준비 길 6). ※ 는 녹화 답을 받아 본 적 없는 어림.
export const FIND = {
 // 2장 결과 화면(sources · db)
 wg0202: {top: TOP, map: {sec: '사용할 모델 — 종류마다 인스턴스 수와 관계', css: '.gbox'}},
 wg0206: {top: TOP, model: {barcol: 'a'}, lab: {barcol: 'b'}, zero: {bar: '노드', col: 'b'}},
 // 3장 — ※ 답: 종류별 개수 표 · 관계 표 · 식별자 문장 · 41줄 → 40개 설명. components.csv 13 · 14행
 wg0304: {table: {css: 'table', has: 'Component'}, kinds: ['Asset', 'Component', 'Sensor', 'Quantity', 'Part', 'Unit'].map(k => ({css: 'td', has: k, exact: true})), id: {css: 'li, p', has: '식별자'}},
 wg0305: {table: {css: 'table', has: 'HAS_COMPONENT'}, ends: ['Asset → Component', 'Component → Sensor', 'Component → Part', 'Sensor → Quantity', 'Component → Unit']},
 wg0306: {why: {css: 'li, p', has: '41'}, l13: 'HYD-02,동력,유압 펌프,PMP-SEAL', l14: 'HYD-02,동력,유압 펌프,P-PMP-SEAL', s13: 'KP-1902-551', s14: 'KP-2603-114'},
 // 4장 — ※ 설비마다 줄 수 표 · 기대 답 후보 표. sensors.csv 2~11행. expected.csv(Codex가 씀)
 wg0410: {hyd01: {css: 'tr', has: 'HYD-01'}, hyd02a: {css: 'tr', has: 'HYD-02'}, hyd02b: {css: 'tr', has: 'HYD-02'}},
 wg0412: {basis: 'data/sensors.csv'},
 wg0413: {pair: {css: 'tr', has: 'component+tag'}, first: 'HYD-01,TS1,', last: 'HYD-01,VS1,', cell: '오일 쿨러', tag: 'TS1', one: '오일 쿨러=TS1', none: 'TS2=없음'},
 wg0416: {head: '질문,물을_값,볼_열,기대_답,근거', first: '1,HYD-01,component+tag', last: '3,P-PMP-SEAL-X', both: 'component+tag'},
 wg0417: {top: TOP, sec: '질문마다 내가 정한 기대 답', cards: ['질문 1', '질문 2', '질문 3']},
 // 5장 — ※ constraints.cypher(쿼리 여섯 줄, 맨 위 // 메모). 결과 화면(constraints)
 wg0505: {memo: '//', first: 'CREATE CONSTRAINT asset_id', last: 'CREATE CONSTRAINT unit_id'},
 wg0506: {create: 'CREATE CONSTRAINT', name: 'asset_id', ifnot: 'IF NOT EXISTS', forNode: 'FOR (n:Asset)', paren: '(n:Asset)', label: ':Asset', req: 'REQUIRE n.id IS UNIQUE', prop: 'n.id', uniq: 'IS UNIQUE'},
 wg0507: {second: 'CREATE CONSTRAINT component_id'},
 wg0508: {top: TOP, sec: '종류마다 걸린 자물쇠', card: 'Asset', said: 'DB가 한 말 — 같은 식별자의 노드가 이미 있다는 뜻', back: '시험한 노드는 되돌렸습니다'},
 // 6장 — ※ Codex의 예측 다섯 줄(답) · 결과 화면(probe). wg0612 lines는 녹화 답의 예측을 줄여 적고, hit는 카드와 맞은 줄 번호(1~5)다 — 대본 wg0612의 ○도 그 수로 맞춘다
 wg0605: {list: {css: 'ol, ul', has: '거절'}},
 wg0606: {top: TOP, cards: ['CREATE로 같은 줄을 두 번 넣으면', 'MERGE 패턴에 식별자 말고 name까지', 'MERGE 패턴의 속성 이름을 id가 아니라 ID로', '화살표를 거꾸로(Component → Asset)', '끝 노드가 아직 없는 관계를 넣으면'],
  says: [null, '패턴 전체(식별자와 name)가 같은 노드를 찾지 못해 새로 만들려다 DB가 거절했습니다', '같은 값을 식별자로 가진 노드가 2개입니다', '모델의 방향(Asset → Component)으로 물으면 0행, 거꾸로 물으면 1행입니다', '만든 관계는 0개입니다 — 끝 노드를 찾지 못한 줄은 아무 말 없이 빠집니다'],
  note: 'DB가 거절하는 것은 유일 제약이 지키는 것뿐이고, 오류 없이 받아 준 것은 넣는 사람이 쿼리와 개수로 확인해야 합니다'},
 wg0612: {lines: ['① 거절 — 같은 id가 이미 있다', '② 거절 — 새로 만들다 제약에 걸림', '③ 받아 줌 — ID는 다른 속성', '④ 받아 줌 — 방향은 안 본다', '⑤ 받아 줌 — 관계가 안 생긴다'], hit: [1, 2, 3, 4, 5]},
 // 7장 — load.cypher 빈 틀 머리(랩 시작본) · ※ Codex가 쓴 쿼리 셋 · equipment.csv · schema.json · components.csv · 결과 화면(load · repeat)
 wg0701: {three: '여기에 쓰는 것은 셋입니다: Asset 노드, 설비와 구성 요소를 잇는 관계, 구성 요소와 부품을 잇는 관계', rest: '나머지 종류 · 관계는 제공 코드가 넣고'},
 wg0702: {raw: 'Asset의 행은 data/equipment.csv의 줄 그대로입니다', head: '설비코드,설비명', name: '"name": "설비명"', status: '"status": "상태"', id: '"Asset": "{설비코드}"'},
 wg0704: {mark: '// 넣을 것: Asset', rows: '$rows'},
 wg0705: {unwind: 'UNWIND', asRow: 'AS row'},
 wg0706: {merge: 'MERGE (n:Asset {id: row.설비코드})', label: ':Asset', key: '{id: row.설비코드}', id: 'id', val: 'row.설비코드'},
 wg0707: {set: 'SET n.code = row.설비코드', name: 'n.name = row.설비명', status: 'n.status = row.상태', date: 'n.installed = date(row.설치일)', on: 'ON CREATE',
  pairs: ['n.code = row.설비코드', 'n.name = row.설비명', 'n.model = row.모델', 'n.status = row.상태', 'n.maker = row.제조사', 'n.serial = row.일련번호', 'n.functional_location = row.기능위치', 'n.installed = date(row.설치일)']},
 wg0708: {line: 'UNWIND $rows AS row MERGE (n:Asset'},
 wg0709: {from: 'UNWIND $rows AS row MERGE (n:Asset', to: 'UNWIND $rows AS row MERGE (n:Asset'},
 wg0710: {from: 'UNWIND $rows AS row MATCH (a:Asset', to: 'UNWIND $rows AS row MATCH (a:Asset', a: 'row.a', b: 'row.b', match: 'MATCH (a:Asset {id: row.a}), (b:Component {id: row.b})', comma: '}), ('},
 wg0711: {la: '(a:Asset {id: row.a})', lb: '(b:Component {id: row.b})', a: ':Asset', b: ':Component'},
 wg0712: {merge: 'MERGE (a)-[r:HAS_COMPONENT]->(b)', head: '->'},
 wg0713: {marks: ['// 넣을 것: Asset', '// 넣을 것: HAS_COMPONENT', '// 넣을 것: USES_PART']},
 wg0714: {from: 'UNWIND $rows AS row MATCH (a:Component', to: 'UNWIND $rows AS row MATCH (a:Component', la: '(a:Component {id: row.a})', lb: '(b:Part {id: row.b})', a: ':Component', b: ':Part', rel: '-[r:USES_PART]->', set: 'ON CREATE SET r.source_text = row.props.source_text',
  l3: 'HYD-01,냉각,쿨러 팬', p3: '팬 베어링 (P-FAN-BRG)', l12: 'HYD-02,냉각,팬,', p12: 'FB-6205'},
 wg0716: {top: TOP, bars: {sec: '모델 파일 ↔ 랩 DB 개수', css: '.bars'}, same: '값과 관계의 방향도 모델 파일과 같습니다', seek: '내 쿼리가 노드를 찾는 법', cards: ['Asset', 'HAS_COMPONENT', 'USES_PART']},
 wg0718: {top: TOP, bars: {sec: '같은 적재를 한 번 더', css: '.bars'}},
 // 8 · 9 · 10장 — ※ query.cypher(Codex가 씀) · graph.json · 결과 화면(sensors · parts · usage)
 wg0802: {match: 'MATCH (a:Asset', asset: '(a:Asset {code: $asset})', slot: '$asset', rels: ['-[:HAS_COMPONENT]->', '-[:MONITORED_BY]->', '-[:OBSERVES]->']},
 wg0803: {ret: 'RETURN c.name AS component', as: ['AS component', 'AS tag', 'AS quantity', 'AS limit'], cols: ['component+tag', 'tag+quantity', 'tag+limit']},
 wg0804: {from: '// 질문 1', to: 'ORDER BY component, tag'},
 wg0805: {top: TOP, pair: 'HYD-01 → component+tag', qty: 'HYD-01 → tag+quantity', lim: 'HYD-01 → tag+limit', none: '=없음', fig: '쿼리가 따라간 길 — 물은 값 「HYD-01」'},
 wg0902: {after: '// 질문 2', match: 'MATCH (a:Asset {code: $asset})-[:HAS_COMPONENT]->(c:Component)', opt: 'OPTIONAL MATCH (c)-[:USES_PART]->(p:Part)', word: 'OPTIONAL'},
 wg0903: {from: '// 질문 2', to: 'ORDER BY component;'},
 wg0904: {top: TOP, table: '질문 2 — 물은 값 「HYD-02」 쿼리 결과', none: '구동 모터', fan: '쿨러 팬', flt: '리턴 필터', fig: '쿼리가 따라간 길 — 물은 값 「HYD-02」'},
 wg1002: {after: '// 질문 3', from: '// 질문 3', to: 'ORDER BY asset;', part: '{part_no: $part}', heads: ['-[:HAS_COMPONENT]->', '-[:USES_PART]->'], ret: 'RETURN p.part_no AS part'},
 wg1003: {top: TOP, same: 'P-CPL-ELM → status', diff: ['RF-10 → asset', 'PS-4510 → asset', 'HI-GS-22 → asset'], noteRow: 'P-PMP-SEAL-X → note', noteHas: '견줄 수 없음', rf: 'RF-10 → asset', card: {sec: '쿼리가 따라간 길 — 물은 값 「RF-10」', card: 'RF-10'}},
 wg1005: {why: {css: 'li, p', has: 'other_codes'}, line: 1289, seen: '"id": "P-RTN-FLT"', codes: ['"HI-RF-10"', '"RF-10"']},
 wg1007: {after: '// 질문 3', where: 'WHERE p.part_no = $part OR $part IN coalesce(p.other_codes, [])', left: 'p.part_no = $part', or: ' OR ', right: '$part IN coalesce(p.other_codes, [])', opt: 'OPTIONAL MATCH (p:Part)', word: 'OPTIONAL', when: "CASE WHEN p IS NULL THEN '원자료에 없는 품번'"},
 wg1008: {from: '// 질문 3', to: 'ORDER BY part, asset, component;'},
 wg1009: {top: TOP, rf: 'RF-10 → asset', fig: '쿼리가 따라간 길 — 물은 값 「RF-10」', noteRow: 'P-PMP-SEAL-X → note'},
 wg1010: {row: 'P-CPL-ELM → status', chip: '예비(보관)'},
 // 11장 — 결과 화면(changes) · ※ 견줌 답 · 수정본 · schema.json · decisions.csv(Codex가 씀)
 wg1102: {top: TOP, name: ['HYD-02', '→'], h7: ['HYD-07', '예비(보관) → 불용(매각 예정)'], ps1: ['HYD-04 · PS1', '140 → 145'], vs1: 'HYD-01 · VS1', fb: 'P-FAN-BRG · FB-6205-2RS'},
 wg1103: {sec: '수정본의 줄마다', note: '「삭제」는 그 담당의 목록에서 빠진 줄이고, 그래프에서 어떻게 할지는 내가 정합니다', decide: '내가 정할 것', points: ['불용 결정 설비', '목록에서 빠진 센서'], ways: ['길 1 — 지우지 않고 상태만 바꿔 남긴다', '길 2 — 그래프에서 지운다']},
 wg1106: {keep7: {css: 'li, td, p', has: 'HYD-07'}, drop7: {css: 'li, td, p', has: '쓰는 설비'}, keepS: {css: 'li, td, p', has: 'VS1'}, dropS: {css: 'li, td, p', has: '아홉'}, schema: {css: 'li, p', has: '스키마'}, pick: {css: 'li, p, strong', has: '추천'}},
 wg1107: {line: '수정,HYD-07', how: '수정', state: '불용(매각 예정)', memo: '2026-10-20 불용 결정'},
 wg1108: {line: '삭제,HYD-01', how: '삭제', memo: '2026-10-19 센서 고장으로 떼어 냄'},
 wg1109: {asset: '"status": "string"', from: '"Sensor": {', to: '"limit_direction": "string"'},
 wg1112: {a: '불용 결정 설비,', b: '목록에서 빠진 센서,'},
 wg1113: {done: '내가 정할 것 2곳 가운데 2곳을 정했습니다', sec: '내가 정할 것', points: ['불용 결정 설비', '목록에서 빠진 센서']},
 // 12장 — ※ expected.csv 고침 · 개수 표 · 물음 셋 · schema_additions.csv · query.cypher · 열 → 속성 표 · update.cypher(쿼리 넷) · 결과 화면(update · status · repeat · sensors · usage)
 wg1201: {set: 'ON CREATE SET'},
 wg1205: {cpl: '3,P-CPL-ELM', status: '불용(매각 예정)', pairRow: '1,HYD-01,component+tag', pair: '쿨러 팬=VS1', tsRow: '1,HYD-01,tag+status', ts: 'VS1=떼어 냄', added: '3,FB-6205-2RS'},
 wg1206: {table: {css: 'table', has: 'Sensor'}},
 wg1207: {head: '클래스,속성,자료형,필수,근거'},
 wg1208: {asks: {css: 'ol, ul', has: '자료형'}},
 wg1209: {row: 'Sensor,status,글자,아니오'},
 wg1211: {status: 's.status AS status', from: '// 질문 2', to: 'ORDER BY part, asset, component;'},
 wg1215: {table: {css: 'table', has: '설비코드'}, rows: [{css: 'tr', has: '설비코드'}, {css: 'tr', has: '설비명'}, {css: 'tr', has: '상태'}, {css: 'tr', has: '태그'}, {css: 'tr', has: '한계'}]},
 wg1216: {marks: ['// 반영할 것: equipment_changes.csv 수정', '// 반영할 것: sensor_changes.csv 수정', '// 반영할 것: sensor_changes.csv 삭제', '// 반영할 것: part_alias_changes.csv 추가'], q1: 'UNWIND $rows AS row MATCH (a:Asset', key: '{id: row.설비코드}', set: 'SET a.name = row.설비명, a.status = row.상태'},
 wg1217: {q2: "UNWIND $rows AS row MATCH (s:Sensor {id: row.설비코드 + ':' + row.태그}) SET s.normal", float: 'toFloat(row.한계)', q3: "UNWIND $rows AS row MATCH (s:Sensor {id: row.설비코드 + ':' + row.태그}) SET s.status", set3: "SET s.status = '떼어 냄'", prop: 's.status'},
 wg1218: {from: 'UNWIND $rows AS row MATCH (p:Part', to: 'SET p.other_codes', where: 'WHERE NOT row.다른표기 IN coalesce(p.other_codes, [])'},
 wg1219: {from: '// 반영할 것: equipment_changes.csv 수정', to: 'SET p.other_codes'},
 wg1220: {top: TOP, sec: '바뀐 노드', cards: {name: 'HYD-02', h7: 'HYD-07', ps1: 'HYD-04:PS1', vs1: 'HYD-01:VS1', fb: 'P-FAN-BRG'}, again: '같은 수정을 한 번 더 실행해도 더 바뀐 것이 없습니다'},
 wg1222: {top: TOP, lab: {barcol: 'b'}},
 wg1224: {top: TOP},
 wg1226: {top: TOP, pair: ['HYD-01 → component+tag', '쿨러 팬=VS1'], ts: ['HYD-01 → tag+status', 'VS1=떼어 냄']},
 wg1228: {top: TOP, cpl: ['P-CPL-ELM → status', '불용(매각 예정)'], fb: 'FB-6205-2RS → asset'},
 // 13장 — 터미널 · 꺼낸 스키마 · 결과 화면(db · check)
 wg1302: {top: TOP, lab: {barcol: 'b'}},
 wg1303: {saved: '랩 DB의 그래프를 저장했습니다', savedPhrase: '랩 DB의 그래프를 저장했습니다 — 노드 114개 · 관계 163개', sensor: '"Sensor": {', status: '"status": "string"'},
 wg1304: {top: TOP, sec: '구조 검사가 맞춰 본 것', checks: ['식별자가 겹치는 노드가 없다', '관계의 양 끝 노드가 실제로 있다', '관계 이름과 시작 · 끝 종류가 스키마와 맞다', '스키마에 없는 속성이 들어가지 않았다']},
};

// ── 구간 차례 ── [구간, 페이지, 종류(say 말 · 조작만 | ask Codex 요청 | view 답 · 파일 보기(끝에 명령이 있을 수 있다) | run 터미널 명령 | result 결과 화면), 그 구간이 치는 명령, 그 구간이 끝난 뒤 랩 DB의 단계]
// 랩 DB 단계: none 없음 → empty 띄움 → constrained 유일 제약 → loaded 넣음 → updated 수정본 반영. 되돌리기 · 사본은 wg-state.mjs.
const D = ['none', 'empty', 'constrained', 'loaded', 'updated'];
export const ORDER = [
 ['wg-01', 0, 'say', [], 0], ['wg-02a', 0, 'run', ['python run.py'], 0], ['wg-02b', 1, 'result', [], 0], ['wg-02c', 0, 'run', ['python run.py db'], 1], ['wg-02d', 1, 'result', [], 1],
 ['wg-03a', 0, 'ask', [], 1], ['wg-03b', 0, 'view', [], 1],
 ['wg-04a', 0, 'ask', [], 1], ['wg-04b', 0, 'view', [], 1], ['wg-04c', 0, 'ask', [], 1], ['wg-04d', 0, 'view', [], 1], ['wg-04e', 0, 'ask', [], 1], ['wg-04f', 0, 'view', ['python run.py expected'], 1], ['wg-04g', 1, 'result', [], 1],
 ['wg-05a', 0, 'ask', [], 1], ['wg-05b', 0, 'view', ['python run.py constraints'], 2], ['wg-05c', 1, 'result', [], 2],
 ['wg-06a', 0, 'ask', [], 2], ['wg-06b', 0, 'view', ['python run.py probe'], 2], ['wg-06c', 1, 'result', [], 2],
 ['wg-07a', 0, 'ask', [], 2], ['wg-07b', 0, 'view', ['python run.py load'], 3], ['wg-07c', 1, 'result', [], 3], ['wg-07d', 0, 'run', ['python run.py repeat'], 3], ['wg-07e', 1, 'result', [], 3],
 ['wg-08a', 0, 'ask', [], 3], ['wg-08b', 0, 'view', ['python run.py sensors'], 3], ['wg-08c', 1, 'result', [], 3],
 ['wg-09a', 0, 'ask', [], 3], ['wg-09b', 0, 'view', ['python run.py parts'], 3], ['wg-09c', 1, 'result', [], 3],
 ['wg-10a', 0, 'ask', [], 3], ['wg-10b', 0, 'view', ['python run.py usage'], 3], ['wg-10c', 1, 'result', [], 3], ['wg-10d', 0, 'ask', [], 3], ['wg-10e', 0, 'view', [], 3], ['wg-10f', 0, 'ask', [], 3], ['wg-10g', 0, 'view', ['python run.py usage'], 3], ['wg-10h', 1, 'result', [], 3],
 ['wg-11a', 0, 'run', ['python run.py changes'], 3], ['wg-11b', 1, 'result', [], 3], ['wg-11c', 0, 'ask', [], 3], ['wg-11d', 0, 'view', [], 3], ['wg-11e', 0, 'ask', [], 3], ['wg-11f', 0, 'view', ['python run.py changes'], 3], ['wg-11g', 1, 'result', [], 3],
 ['wg-12a', 0, 'ask', [], 3], ['wg-12b', 0, 'view', [], 3], ['wg-12c', 0, 'ask', [], 3], ['wg-12d', 0, 'ask', [], 3], ['wg-12e', 0, 'view', [], 3], ['wg-12f', 0, 'ask', [], 3], ['wg-12g', 0, 'view', [], 3], ['wg-12h', 0, 'ask', [], 3],
 ['wg-12i', 0, 'view', ['python run.py update'], 4], ['wg-12j', 1, 'result', [], 4], ['wg-12k', 0, 'run', ['python run.py status'], 4], ['wg-12l', 1, 'result', [], 4], ['wg-12m', 0, 'run', ['python run.py repeat'], 4], ['wg-12n', 1, 'result', [], 4],
 ['wg-12o', 0, 'run', ['python run.py sensors'], 4], ['wg-12p', 1, 'result', [], 4], ['wg-12q', 0, 'run', ['python run.py usage'], 4], ['wg-12r', 1, 'result', [], 4],
 ['wg-13a', 0, 'run', ['python run.py db'], 4], ['wg-13b', 1, 'result', [], 4], ['wg-13c', 0, 'run', ['python run.py export', 'python run.py check'], 4], ['wg-13d', 1, 'result', [], 4], ['wg-13e', 0, 'say', [], 4],
].map(([seg, page, kind, cmds, db]) => ({seg, page, kind, cmds, db: D[db]}));
export const STAGES = D;
export const FEATURES = ['constraints.cypher', 'decisions.csv', 'expected.csv', 'load.cypher', 'query.cypher', 'schema_additions.csv', 'update.cypher'].map(f => 'app/features/' + f);
