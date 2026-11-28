// 통합 2회차 06-1편(VS Code 랩 시작하기)의 구간들(wv-*.mjs)이 함께 쓰는 값 · 펜 그림 정의 · 짚기 도구. 조작 층은 lab-common.mjs의 labUi(ctx).
// 구간 차례 · 페이지 · 시작과 끝 상태 · 녹화 명령은 작업 폴더 판정/녹화모듈_06-1.md에 있다. 부탁 글 · 글상자 글 · 펜 그림 글은 정본 대본의 조작 칸 그대로다(대본을 고치면 여기도 고친다).
// Codex 답에서 찾는 글(녹화할 때마다 답이 다르다)은 여기가 아니라 그 답을 짚는 구간 모듈(wv-06b · wv-09a · wv-09b) 머리의 표 한 곳에 둔다.
// 좌표: 펜 그림 · 글상자 자리는 프레임 px(1920×1080), 그 밖은 페이지 CSS px(config.json viewport). Codex 패널은 프레임 x 약 1342부터라 9장처럼 답과 함께 보이는 판은 x 1330 안에 둔다.
import fs from 'node:fs/promises';
import {rowSeen, em, LABS, codexEl, codexScrollInto, codexView, palette} from './lab-common.mjs';
import {VIEW} from '../page.mjs';

export const LAB = LABS.wv.dir;
// 1장 펜 그림의 배경(1920×1080). 지금은 임시 그림이다 — 사용자 녹화가 오면 그 첫 프레임을 뽑아(촬영준비 길 6: ffmpeg -i <사용자 녹화> -frames:v 1 <첫프레임.png>) 이 경로를 사용자 녹화 첫 프레임으로 바꾼다.
export const FIRST_FRAME = 'D:/work/study/hyd-iot-edu-system/작업/2026-11-19_통합2-VSCode-실습영상/임시그림/첫화면_임시.png';
export const RESULT_TITLE = '원자료';   // python run.py 결과 화면의 제목 앞머리
export const PROMPT = 'ontology-lab>';   // 터미널 프롬프트의 끝

// 부탁 글(대본 wv0601 · wv0802~wv0804 조작 칸). 갖춘 부탁은 세 대목을 빈칸 하나로 이어 붙인다.
export const ASK_VAGUE = '현장 메모 정리해 줘';
export const ASK1 = '보전팀이 자주 묻는 것에 답하는 설비 지식을 만들려고 해. 그 전에 자료부터 알고 싶어.';
export const ASK2 = '현장 메모에 적힌 파일 다섯 개가 data 폴더에 있는지, 표마다 몇 행이고 한 행이 무엇을 뜻하는지, 표끼리 어떤 칸으로 이어지는지, 같은 것을 다르게 적은 곳과 다른 것을 같은 이름으로 적은 곳은 어디인지 알고 싶어.';
export const ASK3 = '어느 표 몇 행인지 예를 들고, 개수도 함께 알려 줘. 파일은 바꾸지 말고, 모르는 것은 먼저 물어봐 줘.';
// 갖춘 부탁을 짚는 대목(입력칸 · 보낸 부탁 글 안의 구절)
export const PART = {
 use: ASK1,
 files: '현장 메모에 적힌 파일 다섯 개가 data 폴더에 있는지',
 rows: '표마다 몇 행이고 한 행이 무엇을 뜻하는지',
 links: '표끼리 어떤 칸으로 이어지는지',
 mixed: '같은 것을 다르게 적은 곳과 다른 것을 같은 이름으로 적은 곳은 어디인지',
 form: '어느 표 몇 행인지 예를 들고, 개수도',
 keep: '파일은 바꾸지 말고',
 ask: '모르는 것은 먼저 물어봐 줘',
};

// 글상자(대본 조작 칸의 글). 자리는 프레임 px — 편집기(x 약 430~1330) 위에 두어 Codex 패널을 가리지 않는다.
export const NOTE = {
 vibe: {lines: ['바이브 코딩 — 말로 시키고, 결과는 내가 판단한다'], at: [470, 330]},
 asked: {title: '물은 것 넷', lines: ['① 파일이 다 있나', '② 표마다 몇 행 · 한 행의 뜻', '③ 표끼리 이어지는 칸', '④ 엇갈리게 적힌 곳'], at: [450, 700]},
 rows: {at: [450, 850]},   // 9장 「Codex가 적은 행」 — 터미널 위 구석
 order: {lines: ['① 파일을 바꾸지 않고 파악', '② 나와야 할 답을 먼저 적기', '③ 추천을 따져 보고 결정', '④ 하나씩 작게 만들기', '⑤ 원자료와 맞춰 보기', '⑥ 고치기', '⑦ 다시 열어 확인'], at: [560, 170]},
 // 8장 「끝에 붙인 말」 — Codex가 답을 쓰는 동안 패널이 저절로 굴러가, 보낸 말풍선을 짚은 띠가 엉뚱한 줄 위에 남았다(wv08-b1, 2026-11-28). 그래서 그 세 대목을 편집기 위 글상자로 띄워 짚는다.
 tail: {title: '끝에 붙인 말', lines: ['어느 표 몇 행인지 예를 들고, 개수도 함께 알려 줘', '파일은 바꾸지 말고', '모르는 것은 먼저 물어봐 줘'], at: [470, 300]},
 todo: {title: '스키마를 정하며 풀 것', lines: ['TS1 × 4대(무엇으로 구별?)', '번호가 여럿인 부품', '오일 쿨러와 열교환기(무엇을 같은 것으로?)'], at: [470, 300]},
};
export const note = (c, key, extra = {}) => c.note(NOTE[key].lines, {title: NOTE[key].title, at: NOTE[key].at, ...extra});

// ── 말 · 리허설 ──
// 지금 큐의 말이 끝날 때까지 기다린다(리허설은 말 길이가 0이라 기다리지 않는다)
export const speechEnd = async ctx => { const q = ctx.__cue; if (!ctx.rehearsal && q?.t0 != null) { const w = q.t0 + q.dur - Date.now(); if (w > 0) await ctx.sleep(w); } };
// 리허설만: 지금 화면을 <리허설 폴더>/<이름>.jpg로 남긴다(강조가 말한 대상에 그려졌는지 눈으로 본다 — 리허설은 프레임을 저장하지 않는다). 녹화 때는 아무것도 하지 않는다.
export const snap = async (ctx, name) => { if (!ctx.rehearsal) return; await ctx.sleep(350); await ctx.serial(() => ctx.p.screenshot({path: ctx.out + '/' + name + '.jpg', type: 'jpeg', quality: 60})); };
// 이름 없는 대상 여럿을 한 말 동안 차례로 짚을 때(「숫자는 읽지 않는다」처럼 짚을 구절이 없는 자리): 구절 from에서 구절 to 사이를 k등분한 말 시점을 차례로 기다리는 함수를 돌려준다.
// 시점 계산은 lab-common.mjs atPhrase와 같은 글자 비율 어림이다. 리허설은 기다리지 않고 구절만 확인한다.
export function between(ctx, from, to, k) {
 const q = ctx.__cue;
 if (!q || q.id !== ctx.cueId) throw Error('between은 labUi(ctx)가 감싼 ctx.say의 조작 안에서만 쓴다: ' + from);
 const a = q.text.indexOf(from), b = q.text.indexOf(to, a + 1);
 if (a < 0 || b < 0) { ctx.report?.push({cue: q.id, op: 'at', target: from + ' … ' + to, fail: true, why: '큐 글에 없는 구절(차례대로)'}); throw Error(q.id + ': 큐 글에 없는 구절 — ' + from + ' … ' + to + ' (segs/wv-common.mjs between)'); }
 return async i => {
  if (ctx.rehearsal || q.t0 == null) return;
  const w = q.t0 + Math.round(q.dur * (a + (b - a) * i / k) / q.text.length) + 250 - Date.now();
  if (w > 0) await ctx.sleep(w);
 };
}

// ── 흐린 강조 ──
// 대본의 「흐린 띠 · 흐린 테두리」(지금 말의 중심이 아니라 둘레를 보일 때): 그림 층(../draw.mjs)에 흐린 모양이 없어, 방금 그린 강조의 색만 옅게 바꾼다.
// 강조의 시작 · 끝 시각 기록(timing.json highlights)은 그대로이고 모양 이름만 기록에 「흐리게」로 남는다. 그림 층에 흐린 모양이 생기면 이 함수를 지우고 그 모양을 쓴다.
export async function faint(c, ctx, target, o = {}) {
 await c.emph(target, o);
 const ok = await c.serial(() => ctx.p.evaluate(() => {
  const g = [...document.querySelectorAll('#recording-draw [data-mark]')].pop(); if (!g) return false;
  for (const e of g.children) {
   if (e.style.borderTopWidth) e.style.borderColor = 'rgba(229,57,53,0.4)';
   else if (e.style.backgroundColor.startsWith('rgba(255, 214, 0')) e.style.backgroundColor = 'rgba(255,214,0,0.2)';
   else e.style.backgroundColor = 'rgba(229,57,53,0.4)';
  }
  return true;
 }));
 if (!ok) throw Error(ctx.cueId + ': 흐리게 할 강조가 화면에 없음 (segs/wv-common.mjs faint)');
 ctx.report?.push({cue: ctx.cueId, op: 'emph', target: '흐리게', fail: false});
}

// ── 탐색기 ──
export const label = name => ({sel: '.explorer-folders-view .monaco-list-row .label-name', text: name});   // 강조 대상: 탐색기 행의 이름 글자
// 탐색기 행을 짚는 화살표 자리: 이름 왼쪽의 접기 화살표 칸(파일 아이콘보다 왼쪽). 이름이나 아이콘 위에 서면 전체 경로 풍선이 떠 아래 행을 가린다(촬영준비 함정 — wv03-dry2의 components.csv).
// lab-common.mjs row(이름 가운데에서 34px 왼쪽)는 긴 이름에서 아직 글자 위라 쓰지 않는다.
export const twistie = (c, ctx, name, level) => c.serial(() => ctx.p.evaluate(({name, level}) => { const r = [...document.querySelectorAll('.explorer-folders-view .monaco-list-row')].filter(e => e.getAttribute('aria-level') === String(level) && e.querySelector('.label-name')?.textContent.trim() === name); if (r.length !== 1) throw Error('탐색기 행 ' + name + '(깊이 ' + level + ')이 ' + r.length + '개'); const b = r[0].querySelector('.label-name').getBoundingClientRect(); return {x: b.left - 30, y: b.top + b.height / 2}; }, {name, level}));
const expanded = (c, ctx, name, level) => c.serial(() => ctx.p.evaluate(({name, level}) => [...document.querySelectorAll('.explorer-folders-view .monaco-list-row')].find(e => e.getAttribute('aria-level') === String(level) && e.querySelector('.label-name')?.textContent.trim() === name)?.getAttribute('aria-expanded') ?? null, {name, level}));
// 폴더를 눌러 펴거나(open = true) 접는다 — 접기 화살표 칸을 누른다(twistie). 이미 그 상태면 앞 구간의 끝 상태가 어긋난 것이므로 큐 id를 대며 멈춘다(누르면 거꾸로 된다).
export async function fold(c, ctx, name, level, open) {
 const now = await expanded(c, ctx, name, level);
 if (now === null) throw Error(ctx.cueId + ': 탐색기에 폴더 ' + name + '(깊이 ' + level + ')가 없음 (segs/wv-common.mjs fold)');
 if ((now === 'true') === open) throw Error(ctx.cueId + ': 탐색기 폴더 ' + name + '가 이미 ' + (open ? '펴져' : '접혀') + ' 있음 — 앞 구간의 끝 상태가 아니다 (segs/wv-common.mjs fold)');
 const q = await twistie(c, ctx, name, level); await c.clickAt(q.x, q.y);
 await ctx.waitFor('[...document.querySelectorAll(".explorer-folders-view .monaco-list-row")].find(e => e.getAttribute("aria-level") === "' + level + '" && e.querySelector(".label-name")?.textContent.trim() === ' + JSON.stringify(name) + ')?.getAttribute("aria-expanded") === "' + open + '"', 8000);
}
// 탐색기의 파일을 연다(행을 누른 뒤 Enter — 촬영준비 길 4, 누르는 자리는 이름 왼쪽 twistie). 이미 열린 탭이면 그 탭이 앞에 온다.
export async function openFile(c, ctx, name, level) {
 await rowSeen(ctx, name, level);
 const f = await twistie(c, ctx, name, level); await c.clickAt(f.x, f.y); await c.key('Enter');
 await ctx.waitFor('document.querySelector(".tabs-container .tab.active .label-name")?.textContent === ' + JSON.stringify(name));
 await ctx.sleep(400);
}
// 앞에 있는 편집기 탭을 닫는다(탭의 닫기 단추)
export async function closeTab(c, ctx, name) {
 const on = await c.serial(() => ctx.p.evaluate(() => document.querySelector('.tabs-container .tab.active .label-name')?.textContent ?? null));
 if (on !== name) throw Error(ctx.cueId + ': 앞에 있는 탭이 ' + name + '이 아니라 ' + on + ' (segs/wv-common.mjs closeTab)');
 await c.clickSel('.tabs-container .tab.active .tab-actions .action-label');
 await ctx.waitFor('![...document.querySelectorAll(".tabs-container .tab .label-name")].some(e => e.textContent === ' + JSON.stringify(name) + ')', 8000);
}
// 열린 편집기 탭 이름들(앞뒤 차례)
export const tabs = (c, ctx) => c.serial(() => ctx.p.evaluate(() => [...document.querySelectorAll('.tabs-container .tab .label-name')].map(e => e.textContent)));

// ── 편집기 ──
export const tabName = (name = null) => name ? {sel: '.tabs-container .tab .label-name', text: name} : {sel: '.tabs-container .tab.active .label-name'};   // 편집기 탭의 파일 이름
export const lineNo = n => ({sel: '.editor-instance .margin-view-overlays .line-numbers', text: String(n)});   // 줄 번호 칸의 숫자
// 편집기 줄들의 글자 자리(줄마다 하나) — from으로 시작하는 줄부터 to로 시작하는 줄까지. more = true면 to 줄이 꺾여 이어진 화면 줄(빈 줄 앞까지)도 넣는다.
// 돌려주는 값은 강조 대상 {rects}다. 띠는 줄마다, 테두리는 모두를 두르는 상자 하나로 그려진다(draw.mjs). 글자가 편집기 오른쪽 밖으로 나간 줄은 보이는 데까지만 잰다.
export const lines = (c, ctx, from, to = from, more = false) => c.serial(() => ctx.p.evaluate(({from, to, more}) => {
 const norm = s => s.replace(/\u00a0/g, ' ');
 const ls = [...document.querySelectorAll('.editor-instance .view-lines .view-line')].filter(e => e.getBoundingClientRect().height > 0).sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top);
 const i0 = ls.findIndex(e => norm(e.textContent).startsWith(from)); let i1 = ls.findIndex(e => norm(e.textContent).startsWith(to));
 if (i0 < 0 || i1 < i0) throw Error('편집기에 줄 없음: ' + (i0 < 0 ? from : to));
 if (more) while (i1 + 1 < ls.length && norm(ls[i1 + 1].textContent).trim() !== '') i1++;
 const A = (ls[i0].closest('.editor-scrollable') || ls[i0].closest('.monaco-editor')).getBoundingClientRect(), out = [];
 for (const e of ls.slice(i0, i1 + 1)) {
  const g = document.createRange(); g.selectNodeContents(e); let l = Infinity, t = Infinity, r = -Infinity, b = -Infinity;
  for (const q of g.getClientRects()) { if (q.width <= 0 || q.height <= 0) continue; l = Math.min(l, q.left); t = Math.min(t, q.top); r = Math.max(r, q.right); b = Math.max(b, q.bottom); }
  if (r === -Infinity) continue;
  if (t < A.top - 1 || b > A.bottom + 1) throw Error('편집기 줄이 보이는 칸 밖으로 굴러가 있음: ' + norm(e.textContent).slice(0, 30));
  r = Math.min(r, A.right - 24); if (r > l) out.push([l, t, r - l, b - t]);
 }
 if (!out.length) throw Error('편집기 줄에 글자가 없음: ' + from);
 return {rects: out};
}, {from, to, more}));
// 편집기에서 starts로 시작하는 첫 줄 안의 조각 sub가 차지한 자리. pick = 몇 번째 것인지(0부터) 또는 'all'(쉼표처럼 여럿을 함께). 같은 조각이 한 줄에 여러 번 나와 구절(phrase)로 못 짚는 자리에 쓴다.
// 편집기 오른쪽 끝(미니맵 앞) 밖으로 나간 조각은 빼고, 보이는 조각이 없으면 멈춘다.
export const piece = (c, ctx, starts, sub, pick = 0) => c.serial(() => ctx.p.evaluate(({starts, sub, pick}) => {
 const norm = s => s.replace(/\u00a0/g, ' ');
 const e = [...document.querySelectorAll('.editor-instance .view-lines .view-line')].filter(e => e.getBoundingClientRect().height > 0).sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top).find(e => norm(e.textContent).startsWith(starts));
 if (!e) throw Error('편집기에 줄 없음: ' + starts);
 const A = (e.closest('.editor-scrollable') || e.closest('.monaco-editor')).getBoundingClientRect(), eb = e.getBoundingClientRect();
 if (eb.top < A.top - 1 || eb.bottom > A.bottom + 1) throw Error('편집기 줄이 보이는 칸 밖으로 굴러가 있음: ' + starts);
 const nodes = [], w = document.createTreeWalker(e, NodeFilter.SHOW_TEXT); let all = '';
 for (let n; (n = w.nextNode());) { nodes.push([n, all.length]); all += norm(n.data); }
 const hits = []; for (let i = all.indexOf(sub); i >= 0; i = all.indexOf(sub, i + sub.length)) hits.push(i);
 const use = pick === 'all' ? hits : [hits[pick]];
 if (!hits.length || use.some(h => h == null)) throw Error('줄 「' + starts + '」에 조각 「' + sub + '」이 ' + hits.length + '번 — ' + JSON.stringify(pick) + '번째를 짚을 수 없음');
 const at = k => { const [n, o] = [...nodes].reverse().find(([, o]) => o <= k); return [n, k - o]; };
 const out = use.map(h => { const g = document.createRange(), a = at(h), b = at(h + sub.length - 1); g.setStart(a[0], a[1]); g.setEnd(b[0], b[1] + 1); const r = g.getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }).filter(r => r[0] + r[2] <= A.right - 24);
 if (!out.length) throw Error('줄 「' + starts + '」의 조각 「' + sub + '」이 편집기 보이는 폭 밖');
 return {rects: out};
}, {starts, sub, pick}));
// 편집기에서 줄 번호 n부터 m까지(파일의 줄 — 화면에서 꺾여 여러 줄로 보이면 그 화면 줄 모두)의 글자 자리(화면 줄마다 하나) → 강조 대상 {rects}.
// phrase를 주면 줄 n 안에서 그 구절이 차지한 글자 자리만 준다(꺾인 자리를 넘어도 된다, 한 번만 나와야 한다 — 같은 글이 여럿이면 [구절, 몇 번째(0부터)]로 준다). 줄 번호 칸이 화면에 그려져 있어야 하고, 보이는 칸 밖이면 멈춘다.
export const rows = (c, ctx, n, m = n, phrase = null) => c.serial(() => ctx.p.evaluate(({n, m, phrase}) => {
 const norm = s => s.replace(/\u00a0/g, ' ');
 const vis = e => { const b = e.getBoundingClientRect(); return b.height > 0 && b.width > 0; };
 const top = e => e.getBoundingClientRect().top;
 const nums = [...document.querySelectorAll('.editor-instance .margin-view-overlays .line-numbers')].filter(vis).map(e => ({k: Number(e.textContent.trim()), t: top(e)})).filter(x => x.k > 0).sort((a, b) => a.t - b.t);
 const views = [...document.querySelectorAll('.editor-instance .view-lines .view-line')].filter(vis).sort((a, b) => top(a) - top(b));
 if (!views.length) throw Error('보이는 편집기가 없음');
 const A = views[0].closest('.editor-scrollable').getBoundingClientRect();
 const span = k => { const i = nums.findIndex(x => x.k === k); if (i < 0) throw Error('편집기에 줄 번호 ' + k + '가 보이지 않음 — 먼저 그 줄을 보이는 칸에 들인다'); const t0 = nums[i].t, t1 = i + 1 < nums.length ? nums[i + 1].t : Infinity; return views.filter(v => top(v) >= t0 - 2 && top(v) < t1 - 2); };
 const merge = rs => { const ls = []; for (const r of rs) { if (r.width <= 0 || r.height <= 0) continue; const c = r.top + r.height / 2, l = ls.find(l => c > l[1] && c < l[3]); if (l) { l[0] = Math.min(l[0], r.left); l[1] = Math.min(l[1], r.top); l[2] = Math.max(l[2], r.right); l[3] = Math.max(l[3], r.bottom); } else ls.push([r.left, r.top, r.right, r.bottom]); } return ls; };
 let ls = [];
 if (phrase != null) {
  const nodes = []; let all = '';
  for (const v of span(n)) { const w = document.createTreeWalker(v, NodeFilter.SHOW_TEXT); for (let t; (t = w.nextNode());) { nodes.push([t, all.length]); all += norm(t.data); } }
  const [p, nth] = Array.isArray(phrase) ? phrase : [phrase, null];
  const hits = []; for (let i = all.indexOf(p); i >= 0; i = all.indexOf(p, i + 1)) hits.push(i);
  if (nth == null ? hits.length !== 1 : hits[nth] == null) throw Error('줄 ' + n + '에 구절 「' + p + '」이 ' + hits.length + '번' + (nth == null ? '' : ' — ' + nth + '번째가 없음'));
  const h = hits[nth ?? 0], at = k => { const [t, o] = [...nodes].reverse().find(([, o]) => o <= k); return [t, k - o]; };
  const g = document.createRange(), a = at(h), b = at(h + p.length - 1); g.setStart(a[0], a[1]); g.setEnd(b[0], b[1] + 1);
  ls = merge([...g.getClientRects()]);
 } else for (let k = n; k <= m; k++) for (const v of span(k)) { const g = document.createRange(); g.selectNodeContents(v); ls.push(...merge([...g.getClientRects()])); }
 if (!ls.length) throw Error('줄 ' + n + (m !== n ? '~' + m : '') + '에 글자가 없음');
 for (const l of ls) if (l[1] < A.top - 1 || l[3] > A.bottom + 1) throw Error('줄 ' + n + '이 편집기 보이는 칸 밖으로 굴러가 있음');
 return {rects: ls.map(l => [l[0], l[1], Math.min(l[2], A.right - 24) - l[0], l[3] - l[1]]).filter(r => r[2] > 0)};
}, {n, m, phrase}));
// 편집기를 굴려 줄 번호 n~m이 모두 보이는 칸 안에 오게 한다(화살표를 편집기 빈 곳으로 옮긴 뒤 휠 — 굴리기는 말하지 않는다, 영상 V-14)
export async function editorShow(c, ctx, n, m = n) {
 const read = () => c.serial(() => ctx.p.evaluate(({n, m}) => {
  const vis = e => { const b = e.getBoundingClientRect(); return b.height > 0 && b.width > 0; };
  const sc = [...document.querySelectorAll('.editor-instance .editor-scrollable')].find(vis); if (!sc) return null;
  const A = sc.getBoundingClientRect();
  const nums = [...document.querySelectorAll('.editor-instance .margin-view-overlays .line-numbers')].filter(vis).map(e => ({k: Number(e.textContent.trim()), b: e.getBoundingClientRect()})).filter(x => x.k > 0 && x.b.top >= A.top - 1 && x.b.bottom <= A.bottom + 1).sort((a, b) => a.k - b.k);
  if (!nums.length) return null;
  const lh = nums.length > 1 ? (nums.at(-1).b.top - nums[0].b.top) / (nums.at(-1).k - nums[0].k) : 19;
  return {first: nums[0].k, last: nums.at(-1).k, lh, x: A.x + A.width * 0.7, y: A.y + A.height * 0.5};
 }, {n, m}));
 let v = await read(); if (!v) throw Error(ctx.cueId + ': 보이는 편집기가 없음 (segs/wv-common.mjs editorShow)');
 if (v.first <= n && v.last >= m) return;
 await c.move(v.x, v.y); await c.gate();
 let f = 1, last = null;
 for (let k = 0; k < 20; k++) {
  const up = v.first > n, dy = up ? (n - v.first - 1) * v.lh : (m - v.last + 1) * v.lh;
  if (k && up !== last) f /= 2; last = up;   // 넘쳐 굴러 방향이 바뀌면 한 번에 굴리는 양을 줄인다
  await c.serial(() => ctx.p.mouse.wheel(0, Math.round(dy * f))); await ctx.sleep(450);
  v = await read(); if (v && v.first <= n && v.last >= m) return;
 }
 throw Error(ctx.cueId + ': 편집기를 굴려도 줄 ' + n + '~' + m + '이 함께 보이지 않음 (segs/wv-common.mjs editorShow)');
}
// 편집기를 맨 위로 굴린다(화살표를 편집기 빈 곳으로 옮긴 뒤 휠) — first = 그 파일 첫 줄의 앞 글
export async function editorTop(c, ctx, first) {
 const e = await c.serial(() => ctx.p.evaluate(() => { const b = document.querySelector('.editor-instance .editor-scrollable').getBoundingClientRect(); return {x: b.x + b.width * 0.75, y: b.y + b.height * 0.6}; }));
 await c.move(e.x, e.y); await c.gate();
 const seen = () => c.serial(() => ctx.p.evaluate(first => { const A = document.querySelector('.editor-instance .editor-scrollable').getBoundingClientRect(); const l = [...document.querySelectorAll('.editor-instance .view-lines .view-line')].find(x => x.textContent.replace(/\u00a0/g, ' ').startsWith(first)); return !!l && l.getBoundingClientRect().top >= A.top - 1; }, first));
 for (let n = 0; n < 20; n++) { if (await seen()) return; await c.serial(() => ctx.p.mouse.wheel(0, -480)); await ctx.sleep(450); }
 throw Error(ctx.cueId + ': 편집기를 올려도 첫 줄이 보이지 않음 — ' + first + ' (segs/wv-common.mjs editorTop)');
}
// 편집기 줄을 짚는 화살표 자리: 그 줄 왼쪽 줄 번호 칸 옆(글을 덮지 않는다). t = 강조 대상({rects} · {box})
export const gutter = (c, ctx, t) => c.serial(() => ctx.p.evaluate(r => { const v = [...document.querySelectorAll('.editor-instance .view-lines')].find(e => e.getBoundingClientRect().height > 0); if (!v) throw Error('보이는 편집기가 없음'); const b = v.getBoundingClientRect(); return {x: b.x - 22, y: r[1] + r[3] / 2 - 6}; }, (t.rects ?? [t.box])[0]));
// 랩 data 폴더의 파일을 줄 번호로 읽는다(lines[1] = 첫 줄). 9장처럼 원자료의 행을 짚는 구간이 줄 글을 손으로 옮겨 적지 않게 한다.
export const dataLines = async name => ['', ...(await fs.readFile(LAB + '/data/' + name, 'utf8')).replace(/\r/g, '').split('\n')];

// ── 터미널 ──
// 터미널에서 글 from이 든 마지막 줄(after만큼 아래 줄)부터 그 뒤 글 to가 든 줄까지의 글자 자리(줄마다 하나) → 강조 대상 {rects}
export const termRows = (c, ctx, from, to, after = 0) => c.serial(() => ctx.p.evaluate(({from, to, after}) => {
 const rs = [...document.querySelectorAll('.terminal-wrapper .xterm-rows > div')];
 let i0 = -1; rs.forEach((d, i) => { if (d.textContent.includes(from)) i0 = i; });
 const i1 = rs.findIndex((d, i) => i >= i0 && d.textContent.includes(to));
 if (i0 < 0 || i1 < 0) throw Error('터미널 줄 없음: ' + (i0 < 0 ? from : to));
 const out = [];
 for (const d of rs.slice(i0 + after, i1 + 1)) { const g = document.createRange(); g.selectNodeContents(d); let l = Infinity, t = Infinity, r = -Infinity, b = -Infinity; for (const q of g.getClientRects()) { if (q.width <= 0 || q.height <= 0 || !q.width) continue; l = Math.min(l, q.left); t = Math.min(t, q.top); r = Math.max(r, q.right); b = Math.max(b, q.bottom); } if (r > l) out.push([l, t, r - l, b - t]); }
 if (!out.length) throw Error('터미널 줄에 글자가 없음: ' + from);
 return {rects: out};
}, {from, to, after}));

// ── 화면의 칸 · 그림 ──
// 바깥 문서의 요소 하나를 안쪽으로 inset만큼 줄인 상자(테두리가 화면 밖으로 나가지 않게) — 탐색기 칸 · 편집기 칸
export const area = (c, ctx, sel, inset = 10) => c.serial(() => ctx.p.evaluate(({sel, inset}) => {
 const es = [...document.querySelectorAll(sel)].filter(e => e.getBoundingClientRect().width > 0);
 if (es.length !== 1) throw Error('보이는 칸이 ' + es.length + '개: ' + sel);
 const b = es[0].getBoundingClientRect(); return {box: [b.x + inset, b.y + inset, b.width - 2 * inset, b.height - 2 * inset]};
}, {sel, inset}));
// 결과 화면(둘째 페이지)의 요소 하나의 상자 — SVG 글자처럼 글자 자리를 잴 수 없는 대상의 밑줄 · 테두리에 쓴다
export const boxOf = (c, ctx, sel, pad = 0) => c.serial(() => ctx.p.evaluate(({sel, pad}) => {
 const es = [...document.querySelectorAll(sel)].filter(e => e.getBoundingClientRect().width > 0);
 if (es.length !== 1) throw Error('보이는 대상이 ' + es.length + '개: ' + sel);
 const b = es[0].getBoundingClientRect(); return {box: [b.x - pad, b.y - pad, b.width + 2 * pad, b.height + 2 * pad]};
}, {sel, pad}));
// 결과 화면의 그림은 노드에 마우스가 올라가면 속성 풍선이 뜨고 나머지가 흐려진다(노드에 마우스를 올리면 속성). 짚는 화살표가 노드 위에 서지 않게,
// 대상 상자 b(boxOf의 box)의 둘레에서 어떤 노드 · 풍선 위도 아닌 자리를 골라 강조의 at으로 준다. 고를 자리가 없으면 큐 id를 대며 멈춘다.
export const freeAt = (c, ctx, b, prefer = ['below', 'left', 'right', 'above']) => c.serial(() => ctx.p.evaluate(({b, prefer}) => {
 const [x, y, w, h] = b, spot = {below: [x + 6, y + h + 12], left: [x - 30, y + h / 2 - 8], right: [x + w + 12, y + h / 2 - 8], above: [x + 6, y - 34]};
 const free = (px, py) => { for (const [dx, dy] of [[0, 0], [10, 14], [18, 26]]) { if (px + dx < 2 || py + dy < 2 || px + dx > innerWidth - 4 || py + dy > innerHeight - 12) return false; if (document.elementsFromPoint(px + dx, py + dy).some(e => e.closest?.('svg.g .n, #tip'))) return false; } return true; };
 for (const k of prefer) { const [px, py] = spot[k]; if (free(px, py)) return {x: px, y: py}; }
 throw Error('강조 대상 둘레에 노드가 아닌 자리가 없음: ' + JSON.stringify(b.map(Math.round)));
}, {b, prefer}));
// 떠 있는 글상자의 줄 from~to(1부터)를 함께 짚는 대상 — to를 빼면 모든 줄
export const noteLines = (c, ctx, from = 1, to = Infinity) => c.serial(() => ctx.p.evaluate(({from, to}) => {
 const ls = [...document.querySelectorAll('#recording-draw [data-note] [data-line]')].filter(l => Number(l.dataset.line) >= from && Number(l.dataset.line) <= (to ?? Infinity)).map(l => l.querySelector('.note-text'));
 if (!ls.length) throw Error('떠 있는 글상자에 줄 ' + from + '~' + to + '이 없음');
 return {rects: ls.map(e => { const b = e.getBoundingClientRect(); return [b.x, b.y, b.width, b.height]; })};
}, {from, to: to === Infinity ? null : to}));
export const noteAll = (c, ctx) => noteLines(c, ctx);
// 떠 있는 펜 그림의 글 여럿을 함께 짚는 대상(테두리 하나로 그려진다)
export const penTexts = (c, ctx, ...ids) => c.serial(() => ctx.p.evaluate(ids => {
 const out = ids.map(id => document.querySelector('#recording-draw [data-pen="' + CSS.escape(id) + '"] .pen-text'));
 if (out.some(e => !e)) throw Error('떠 있는 펜 그림에 글이 없음: ' + ids.join(' · '));
 return {rects: out.map(e => { const b = e.getBoundingClientRect(); return [b.x, b.y, b.width, b.height]; })};
}, ids));
// 펜 그림 정의의 칸들(프레임 px [x, y, w, h])을 함께 두르는 대상
export const penArea = (c, ctx, ...ats) => c.serial(() => ctx.p.evaluate(ats => { const k = innerWidth / 1920; return {rects: ats.map(a => a.map(v => v * k))}; }, ats));

// ── 결과 화면을 VS Code 옆에 띄우기(9장 wv0902 「결과 화면을 옆에 띄워 상자의 행 수와 나란히 보인 뒤 돌아온다」) ──
// 한 구간은 한 페이지에서 찍고(촬영준비 길 6) wv0902는 한 큐 안에서 Codex 답 → 결과 화면 → 다시 답으로 오가므로 둘째 페이지로 넘어갈 수 없다.
// 그래서 녹화 전에 같은 녹화 브라우저의 임시 페이지에서 학생의 결과 화면(output/result.html)을 열어 「원자료 표가 이어지는 칸」 칸을 그림으로 찍어 두고(배율 2),
// 말에 맞춰 그 그림을 VS Code 위, Codex 패널 왼쪽에 띄웠다가 걷는다. 그림은 그림 층(#recording-draw) 안에 두어 구간 시작의 그림 층 비우기에 함께 지워진다.
// 돌려주는 값: show(top) — top = 그림 위 끝의 CSS y, hide(), count(파일 이름) = 그 상자의 「N행」 글자 자리(강조 대상 {box}), on() = 떠 있는가.
export async function resultInset(c, ctx) {
 const pg = await ctx.p.context().newPage();
 let m, png;
 try {
  const s = await ctx.p.context().newCDPSession(pg);
  await s.send('Emulation.setDeviceMetricsOverride', {width: VIEW.width, height: VIEW.height, deviceScaleFactor: 2, mobile: false});
  await pg.goto('file:///' + LAB + '/output/result.html');
  m = await pg.evaluate(() => {
   const sec = [...document.querySelectorAll('section')].find(e => e.querySelector('h3')?.textContent.startsWith('원자료 표가 이어지는 칸'));
   const svg = sec?.querySelector('svg.g'); if (!svg) return null;
   const S = sec.getBoundingClientRect(), x0 = S.x, x1 = S.right;   // 칸 전체(제목 · 그림 · 아래 설명) — 그림만 자르면 제목이 잘린다(t-wv-helpers2)
   const counts = {};
   for (const g of svg.querySelectorAll('g.n')) { const t = g.querySelector('text.s'); if (!t) continue; const b = t.getBoundingClientRect(); counts[g.dataset.id] = [b.x - x0, b.y - S.y, b.width, b.height]; }
   return {clip: {x: x0, y: S.y + scrollY, width: x1 - x0, height: S.height}, counts};
  });
  if (!m) throw Error('결과 화면에 「원자료 표가 이어지는 칸」 그림이 없음 — 첫 실행(python run.py)의 결과인지 본다');
  png = (await pg.screenshot({clip: m.clip})).toString('base64');
 } finally { await pg.close(); }
 const id = 'wv-inset';
 let shown = null;
 const it = {
  on: () => c.serial(() => ctx.p.evaluate(id => !!document.getElementById(id), id)),
  show: async top => {
   shown = await c.serial(() => ctx.p.evaluate(({id, png, m, top}) => {
    let r = document.getElementById('recording-draw');
    if (!r) { r = document.createElement('div'); r.id = 'recording-draw'; r.setAttribute('aria-hidden', 'true'); r.style.cssText = 'position:fixed;left:0;top:0;width:100vw;height:100vh;pointer-events:none;z-index:2147483646;overflow:hidden'; document.documentElement.append(r); }
    const panel = document.querySelector('.part.auxiliarybar')?.getBoundingClientRect(); if (!panel?.width) throw Error('Codex 패널이 열려 있지 않음');
    const w = Math.min(m.clip.width, panel.x - 70), k = w / m.clip.width, h = m.clip.height * k, x = panel.x - 24 - w, y = Math.max(40, Math.min(top, innerHeight - h - 40));
    const box = document.createElement('div'); box.id = id; box.dataset.inset = '1';
    box.style.cssText = `position:absolute;left:${x}px;top:${y}px;width:${w}px;height:${h}px;border-radius:10px;overflow:hidden;background:#fff;box-shadow:0 10px 44px rgba(0,0,0,.55),0 0 0 1px rgba(255,255,255,.25)`;
    const img = document.createElement('img'); img.src = 'data:image/png;base64,' + png; img.style.cssText = `display:block;width:${w}px;height:${h}px`; box.append(img);
    r.append(box); box.animate([{opacity: 0}, {opacity: 1}], {duration: 200});
    return {x, y, k};
   }, {id, png, m, top}));
   await ctx.sleep(260);
   ctx.report?.push({cue: ctx.cueId, op: 'note', target: '결과 화면 그림 띄움', fail: false});
  },
  hide: async () => {
   await ctx.draw?.end('결과 화면 그림 걷기');
   const was = await c.serial(() => ctx.p.evaluate(id => { const e = document.getElementById(id); if (!e) return false; e.id = ''; e.animate([{opacity: 1}, {opacity: 0}], {duration: 200, fill: 'forwards'}).onfinish = () => e.remove(); return true; }, id));
   if (!was) throw Error(ctx.cueId + ': 걷을 결과 화면 그림이 없음 (segs/wv-common.mjs resultInset)');
   shown = null; await ctx.sleep(260);
   ctx.report?.push({cue: ctx.cueId, op: 'note', target: '결과 화면 그림 걷음', fail: false});
  },
  count: file => {
   if (!shown) throw Error(ctx.cueId + ': 결과 화면 그림이 떠 있지 않음 (segs/wv-common.mjs resultInset)');
   const b = m.counts[file]; if (!b) throw Error(ctx.cueId + ': 결과 화면 그림에 ' + file + ' 상자가 없음 (segs/wv-common.mjs resultInset)');
   return {box: [shown.x + b[0] * shown.k, shown.y + b[1] * shown.k, b[2] * shown.k, b[3] * shown.k]};
  },
 };
 return it;
}

// ── Codex 패널(웹뷰) ──
// 답 · 보낸 부탁 · 입력칸 안의 요소를 찾는 꼴(spec):
//   [CSS, 든 글]            그 CSS에 맞고 그 글이 든 보이는 요소(제목 h2 · h3, 굵은 글 strong, 목록 li, 표 table, 메모 줄 링크 span.break-words, 입력칸 [contenteditable=true])
//   ['*', 든 글]            그 글이 든 가장 안쪽 요소(문단 · 보낸 부탁 글처럼 CSS로 가리기 어려운 것)
//   [CSS | '*', 든 글, 'last']   여럿이면 문서 차례로 마지막 것(보낸 부탁 글은 패널 위 대화 제목에도 같은 글이 있어 아래쪽 말풍선을 고른다)
//   {cell: [표에 든 글, 행 첫 칸에 든 글, 칸 번호]}   Codex 답 표의 칸 하나(머리 줄도 된다) · {row: [표에 든 글, 행 첫 칸에 든 글]} 그 행
//   {within: [CSS, 든 글], css, eq: 글}   그 요소(하나) 안에서 글이 꼭 같은 CSS 요소(한 항목 안의 품번 code처럼 같은 글이 다른 글 속에도 든 자리)
// 보이는 것이 정확히 하나가 아니면 큐 id와 찾은 수를 대며 멈춘다 — 녹화한 답을 보고 그 구간 모듈 머리의 표를 고친다.
const FIND = `(({css, has, cell, row, within, eq}) => {
 const vis = e => e.getClientRects().length > 0 && e.checkVisibility();
 const txt = e => e.textContent || '';
 if (within) { const roots = [...document.querySelectorAll(within[0])].filter(e => vis(e) && txt(e).includes(within[1])); if (roots.length !== 1) return roots; /* 담는 요소가 없거나 여럿이면 그 수로 멈추게 한다 */ return [...roots[0].querySelectorAll(css)].filter(e => vis(e) && txt(e).trim() === eq); }
 if (cell || row) { const [th, rh, col] = cell || row; const out = []; for (const t of document.querySelectorAll('table')) { if (!vis(t) || !txt(t).includes(th)) continue; for (const r of t.rows) if (r.cells[0] && txt(r.cells[0]).includes(rh)) { const e = row ? r : r.cells[col]; if (e) out.push(e); } } return out; }
 if (css === '*') { const out = []; const walk = e => { let inner = false; for (const k of e.children) if (txt(k).includes(has)) { inner = true; walk(k); } if (!inner && vis(e)) out.push(e); }; if (document.body && txt(document.body).includes(has)) walk(document.body); return out; }
 return [...document.querySelectorAll(css)].filter(e => vis(e) && (has == null || txt(e).includes(has)));
})`;
const specArg = spec => Array.isArray(spec) ? {css: spec[0], has: spec[1], last: spec[2] === 'last'} : {...spec, last: false};
const specName = spec => Array.isArray(spec) ? '「' + spec[1] + '」이 든 ' + spec[0] : JSON.stringify(spec);   // 멈출 때 대는 이름
async function cxPick(c, ctx, spec) {
 const a = specArg(spec), hits = [];
 for (const f of ctx.p.frames()) {
  if (f === ctx.p.mainFrame()) continue;
  try { const n = await f.evaluate(FIND + '(' + JSON.stringify(a) + ').length'); if (n) hits.push([f, n]); }
  catch (e) { if (!/detached|destroyed|closed|navigat/i.test(String(e?.message ?? e))) throw e; }   // 웹뷰가 다시 그려지는 순간의 프레임만 건너뛴다
 }
 const total = hits.reduce((s, [, n]) => s + n, 0);
 if (!total || (total > 1 && !a.last)) throw Error((ctx.cueId ?? '(큐 밖)') + ': Codex 패널에서 ' + specName(spec) + '이 ' + total + '개 — 녹화한 답을 보고 그 구간 모듈 머리의 표를 고친다 (segs/wv-common.mjs)');
 const [f, n] = hits.at(-1);
 const h = (await f.evaluateHandle(FIND + '(' + JSON.stringify(a) + ')[' + (n - 1) + ']')).asElement();
 if (!h) throw Error((ctx.cueId ?? '(큐 밖)') + ': Codex 패널의 ' + specName(spec) + '을 잡지 못함 (segs/wv-common.mjs)');
 return h;
}
// 그 요소의 상자(바깥 문서 CSS px, 폭은 패널 안에 보이는 만큼) — 굴려 들이기(cxScroll) · 테두리 · 띠에 쓴다
export async function cxBox(c, ctx, spec) {
 const a = await c.codexArea(), right = a.x + a.w - 10;
 return c.serial(async () => { const h = await cxPick(c, ctx, spec); const b = await h.boundingBox(); await h.dispose(); if (!b) throw Error((ctx.cueId ?? '(큐 밖)') + ': Codex 패널의 ' + specName(spec) + '이 그려져 있지 않음 (segs/wv-common.mjs cxBox)'); return {x: b.x, y: b.y, w: Math.min(b.width, right - b.x), h: b.height}; });
}
// 그 요소 안 글자의 자리(줄마다 하나) — phrase를 주면 그 구절의 글자 자리만(그 요소에 한 번만 나와야 한다). 바깥 문서 CSS px, 패널 안에 보이는 폭까지 → 강조 대상 {rects}
export async function cxRects(c, ctx, spec, phrase = null) {
 const a = await c.codexArea(), right = a.x + a.w - 10;
 return c.serial(async () => {
  const h = await cxPick(c, ctx, spec), bb = await h.boundingBox();
  const r = await h.evaluate((el, phrase) => {
   const nodes = [], w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT); let all = '';
   for (let n; (n = w.nextNode());) { nodes.push([n, all.length]); all += n.data; }
   const g = document.createRange();
   if (phrase != null) {
    const found = []; for (let i = all.indexOf(phrase); i >= 0; i = all.indexOf(phrase, i + 1)) found.push(i);
    if (found.length !== 1) return {count: found.length};
    const at = k => { const [n, o] = [...nodes].reverse().find(([, o]) => o <= k); return [n, k - o]; };
    const s = at(found[0]), t = at(found[0] + phrase.length - 1); g.setStart(s[0], s[1]); g.setEnd(t[0], t[1] + 1);
   } else g.selectNodeContents(el);
   const ls = [];
   for (const q of g.getClientRects()) { if (q.width <= 0 || q.height <= 0) continue; const m = q.top + q.height / 2, l = ls.find(l => m > l[1] && m < l[3]); if (l) { l[0] = Math.min(l[0], q.left); l[1] = Math.min(l[1], q.top); l[2] = Math.max(l[2], q.right); l[3] = Math.max(l[3], q.bottom); } else ls.push([q.left, q.top, q.right, q.bottom]); }
   const b = el.getBoundingClientRect(); return {bx: b.x, by: b.y, ls};
  }, phrase);
  await h.dispose();
  if (r.count != null || !bb) throw Error((ctx.cueId ?? '(큐 밖)') + ': Codex 패널의 ' + specName(spec) + ' 안에 구절 「' + phrase + '」이 ' + (r.count ?? '(상자 없음)') + '번 — 한 번만 나오는 구절로 고친다 (segs/wv-common.mjs cxRects)');
  const rects = r.ls.map(l => { const x = bb.x + l[0] - r.bx, y = bb.y + l[1] - r.by; return [x, y, Math.min(bb.x + l[2] - r.bx, right) - x, l[3] - l[1]]; }).filter(q => q[2] > 0);
  if (!rects.length) throw Error((ctx.cueId ?? '(큐 밖)') + ': Codex 패널의 ' + specName(spec) + '에 보이는 글자가 없음 (segs/wv-common.mjs cxRects)');
  return {rects};
 });
}
// 그 요소가 답의 보이는 칸 안(위에서 frac 높이쯤)에 오게 굴린다(lab-common.mjs codexScrollInto). lazy = true면 이미 보이는 칸 안에 온전히 있을 때 굴리지 않는다. 돌려주는 값 = 그 요소의 상자.
export async function cxScroll(c, ctx, spec, frac = 0.25, lazy = false) {
 if (lazy) { const b = await cxBox(c, ctx, spec), v = await codexView(c, ctx); if (b.y >= v.top && b.y + b.h <= v.bottom) return b; }
 return codexScrollInto(c, ctx, () => cxBox(c, ctx, spec), frac);
}
// Codex 답 칸의 빈 곳(비율 좌표)으로 화살표를 옮긴다 — 「답으로 돌아온다」
export async function toAnswer(c, ctx, fx = 0.5, fy = 0.45) { const q = await c.codexPoint(fx, fy); await c.move(q.x, q.y); }
// Codex 요청 입력칸의 상자(테두리로 짚는다)
export const codexInput = async (c, ctx) => { const q = await codexEl(c, ctx, {input: true}); return em.box({x: q.x - q.w / 2, y: q.y - q.h / 2, w: q.w, h: q.h}); };
// 초점이 있는 Codex 입력칸에 글을 한 번에 붙여 넣는다(대본 「붙여 넣는다」 — 영상 V-14 「긴 명령은 붙여넣는다」). 초점이 Codex에 없으면 넣지 않고 멈추고, 넣은 글이 입력칸에 보이는지 확인한다.
export async function codexPaste(c, ctx, text) {
 const inCodex = () => c.serial(() => ctx.p.evaluate(() => { const a = document.activeElement; return !!a && (a.tagName === 'IFRAME' || !!a.closest('.part.auxiliarybar, .webview')); }));
 if (!(await inCodex())) { ctx.report?.push({cue: ctx.cueId, op: 'type', target: 'Codex 입력칸', fail: true, why: '입력 초점이 Codex가 아님'}); throw Error(ctx.cueId + ': 입력 초점이 Codex가 아님 — 붙여 넣지 않고 멈춤 (segs/wv-common.mjs codexPaste)'); }
 await c.gate(); await ctx.draw?.end('붙여넣기');
 await c.serial(() => ctx.p.keyboard.insertText(text));
 await ctx.sleep(300);
 await cxBox(c, ctx, ['[contenteditable=true]', text.trim().slice(0, 12)]);
 ctx.report?.push({cue: ctx.cueId, op: 'type', target: 'Codex 입력칸(붙여넣기)', text, fail: false});
}

// ── 녹화 전 상태 맞춤(Codex 답을 짚는 구간) ──
// 답을 짚는 구간은 녹화한 답을 보고 리허설(dry)한 뒤 바로 녹화한다. 리허설은 답을 굴리고 탭을 열고 닫아, 그대로 녹화하면 첫 프레임이 앞 take의 끝 프레임과 달라 이음새에서 화면이 튄다.
// 그래서 그 구간은 녹화 전(ctx.begin 앞, 화면에 남지 않는다)에 settle로 앞 take가 끝난 모습을 다시 만든다. 화살표는 옮기지 않고, 끝에 실제 마우스만 화살표 자리로 되돌린다.
// Codex 대화 칸의 굴린 자리(scrollTop): answerScroll(c, ctx) = 읽기, answerScroll(c, ctx, 값 | 'end') = 맞추기. 답을 짚는 구간은 끝에 이 값을 돌려주고(timing.json result.answerScroll), 다음 구간이 ctx.prev로 받아 맞춘다.
const SCROLLER = `(() => { let best = null, area = 0; for (const e of document.querySelectorAll('*')) { const st = getComputedStyle(e); if (!/(auto|scroll)/.test(st.overflowY) || e.scrollHeight <= e.clientHeight + 20 || !e.getClientRects().length) continue; const a = e.clientWidth * e.clientHeight; if (a > area) { area = a; best = e; } } return best; })()`;
export async function answerScroll(c, ctx, to = undefined) {
 return c.serial(async () => {
  const hits = [];
  for (const f of ctx.p.frames()) {
   if (f === ctx.p.mainFrame()) continue;
   try { const r = await f.evaluate('(() => { const e = ' + SCROLLER + '; return e ? {top: e.scrollTop, area: e.clientWidth * e.clientHeight} : null; })()'); if (r) hits.push([f, r]); }
   catch (e) { if (!/detached|destroyed|closed|navigat/i.test(String(e?.message ?? e))) throw e; }
  }
  // 굴릴 칸이 없음 = 답이 패널 한 화면에 다 들어와 굴릴 것이 없다(wv06a-b1의 짧은 답). 그 모습의 굴린 자리는 0이다.
  // 앞 take가 굴려 둔 자리(0보다 큰 값)를 맞추라는데 지금 굴릴 칸이 없으면 앞 take와 화면이 다르므로 멈춘다.
  if (!hits.length) { if (to === undefined || to === 'end' || to === 0) return 0; throw Error((ctx.cueId ?? '(녹화 전)') + ': Codex 대화 칸이 한 화면에 다 들어와 굴릴 수 없는데 앞 take의 굴린 자리는 ' + to + ' (segs/wv-common.mjs answerScroll)'); }
  const [f, r] = hits.sort((a, b) => b[1].area - a[1].area)[0];
  if (to === undefined) return r.top;
  return f.evaluate('(to => { const e = ' + SCROLLER + '; e.scrollTop = to === "end" ? e.scrollHeight : to; return e.scrollTop; })(' + JSON.stringify(to) + ')');
 });
}
// 녹화(rec)에서는 run.sh가 앞 take 끝 자리에 화살표를 그려 둔 뒤 구간 모듈을 부르므로, settle은 그 화살표를 그 자리에 둔 채 끝난다.
// tabs = 앞 take 끝의 편집기 탭(차례대로 — 없는 탭은 열고 남는 탭은 닫는다, 빼면 탭은 건드리지 않는다), active = 앞에 둘 탭(top이면 1행으로), answer = answerScroll에 줄 값(null · undefined면 건드리지 않는다).
export async function settle(c, ctx, {tabs = null, active = null, top = false, answer = null} = {}) {
 const p = ctx.p, now = () => c.serial(() => p.evaluate(() => [...document.querySelectorAll('.tabs-container .tab .label-name')].map(e => e.textContent)));
 // 화살표 자리를 먼저 적어 둔다 — 명령 창을 여는 누르기가 실제 마우스를 옮기면 그려 둔 화살표도 따라가므로(ui.mjs) 끝에 그 자리로 되돌린다(t-wv-settle3)
 const q0 = await c.serial(() => p.evaluate(() => { const r = document.getElementById('recording-pointer')?.getBoundingClientRect(); return r ? {x: r.x, y: r.y} : null; }));
 if (tabs) {
  for (const t of await now()) if (!tabs.includes(t)) { await c.serial(() => palette(p, t, true)); await c.serial(() => palette(p, 'View: Close Editor')); }
  for (const t of tabs) if (!(await now()).includes(t)) await c.serial(() => palette(p, t, true));
  const got = await now(); if (got.join() !== tabs.join()) throw Error('녹화 전 상태 맞춤: 편집기 탭이 ' + got.join(' · ') + ' — 앞 take 끝은 ' + tabs.join(' · ') + ' (segs/wv-common.mjs settle)');
 }
 if (active) {
  const on = await c.serial(() => p.evaluate(() => ({tab: document.querySelector('.tabs-container .tab.active .label-name')?.textContent, first: Math.min(...[...document.querySelectorAll('.editor-instance .margin-view-overlays .line-numbers')].filter(e => e.getBoundingClientRect().height > 0).map(e => Number(e.textContent.trim()) || Infinity))})));
  if (on.tab !== active || (top && on.first !== 1)) await c.serial(() => palette(p, active + (top ? ':1' : ''), true));   // 이미 그 모습이면 건드리지 않는다(초점이 옮겨 가지 않게)
 }
 if (answer != null) await answerScroll(c, ctx, answer);
 await ctx.sleep(400);
 if (q0) await c.serial(() => p.mouse.move(q0.x, q0.y));
}

// ── 펜 그림(프레임 px 1920×1080 — 촬영준비 길 6) ──
// 1장(그림 한 장 위): 배운 것 · 읽은 것 → 맨땅에서 직접 세우기
export const INTRO = {id: '맨땅에서', board: [330, 330, 1260, 400], items: [
 {id: 'past', kind: 'box', at: [410, 440, 400, 180], text: '이론 (배움)\n포털 (읽기)'},
 {id: 'make', kind: 'box', at: [1110, 440, 400, 180], text: '맨땅에서\n직접 세우기'},
 {id: 'go', kind: 'arrow', from: 'past', to: 'make'},
]};
// 1장: 층 셋(아래에서 위로) · 매뉴얼의 TS1 한 줄과 설비 네 대의 TS1 · 층마다 도는 고리 · 회차 · 회사 시스템의 표
export const LAYERS = {id: '층 셋', board: [110, 110, 1700, 860], items: [
 {id: 'L1', kind: 'box', at: [330, 700, 1010, 150], text: ''},
 {id: 'L1t', kind: 'text', at: [360, 755], text: '설비 · 구성 요소 · 센서 · 부품'},
 {id: 'L2', kind: 'box', at: [330, 540, 560, 110], text: '작업 절차 · 판단 조건\n(매뉴얼에서 사람이 옮김)'},
 {id: 'L3', kind: 'box', at: [330, 380, 560, 110], text: '문서에서 AI가 뽑고\n사람이 확인한 지식'},
 // wv0106 — 큐 끝에서 지운다(LAYERS_EXTRA)
 {id: 'say', kind: 'box', at: [960, 560, 440, 80], text: '유온 TS1이 ○도를 넘으면 경보', size: 0.9},
 {id: 't1', kind: 'box', at: [800, 745, 120, 64], text: 'HYD-01\nTS1', size: 0.7},
 {id: 't2', kind: 'box', at: [930, 745, 120, 64], text: 'HYD-02\nTS1', size: 0.7},
 {id: 't3', kind: 'box', at: [1060, 745, 120, 64], text: 'HYD-03\nTS1', size: 0.7},
 {id: 't4', kind: 'box', at: [1190, 745, 120, 64], text: 'HYD-04\nTS1', size: 0.7},
 {id: 's1', kind: 'arrow', from: 'say', to: 't1'}, {id: 's2', kind: 'arrow', from: 'say', to: 't2'}, {id: 's3', kind: 'arrow', from: 'say', to: 't3'}, {id: 's4', kind: 'arrow', from: 'say', to: 't4'},
 {id: 'which', kind: 'text', at: [1420, 665], text: '어느 설비?'},
 {id: 'lost', kind: 'text', at: [1420, 555], text: '?', size: 1.8, color: 'red'},
 // wv0107 — 층 하나를 쌓는 고리
 {id: 'q', kind: 'box', at: [980, 180, 300, 80], text: '질문'},
 {id: 'a', kind: 'box', at: [1400, 180, 300, 80], text: '답 먼저 적기'},
 {id: 's', kind: 'box', at: [1400, 380, 300, 80], text: '스키마 · 담기'},
 {id: 'c', kind: 'box', at: [980, 380, 300, 80], text: '물어서 견주기'},
 {id: 'qa', kind: 'arrow', from: 'q', to: 'a'}, {id: 'as', kind: 'arrow', from: 'a', to: 's'}, {id: 'sc', kind: 'arrow', from: 's', to: 'c'}, {id: 'cq', kind: 'arrow', from: 'c', to: 'q'},
 {id: 'ok', kind: 'text', at: [590, 648], text: '✓', size: 1.3, color: 'red'},
 // wv0108 — 회차
 {id: 'r2', kind: 'text', at: [200, 755], text: '2회차'}, {id: 'r3', kind: 'text', at: [200, 575], text: '3회차'}, {id: 'r4', kind: 'text', at: [200, 415], text: '4회차'},
 // wv0105 — 바탕의 재료
 {id: 'src', kind: 'box', at: [1500, 730, 270, 90], text: '회사 시스템의 표'},
 {id: 'feed', kind: 'arrow', from: 'src', to: 'L1'},
]};
export const LAYERS_EXTRA = ['say', 't1', 't2', 't3', 't4', 's1', 's2', 's3', 's4', 'which', 'lost'];
// 1장: 상황 — 보전팀이 표 다섯 장과 메모 한 장을 보냈다
export const SITUATION = {id: '상황', board: [240, 210, 1440, 640], items: [
 {id: 'team', kind: 'box', at: [320, 430, 300, 120], text: '보전팀'},
 {id: 'me', kind: 'box', at: [1240, 430, 360, 120], text: '나\n(설비 지식 정리 담당)', size: 0.9},
 {id: 'send', kind: 'arrow', from: 'team', to: 'me'},
 {id: 'f1', kind: 'box', at: [690, 330, 72, 64], text: '표', size: 0.8}, {id: 'f2', kind: 'box', at: [774, 330, 72, 64], text: '표', size: 0.8}, {id: 'f3', kind: 'box', at: [858, 330, 72, 64], text: '표', size: 0.8},
 {id: 'f4', kind: 'box', at: [942, 330, 72, 64], text: '표', size: 0.8}, {id: 'f5', kind: 'box', at: [1026, 330, 72, 64], text: '표', size: 0.8},
 {id: 'memo', kind: 'box', at: [1114, 330, 90, 64], text: '메모', size: 0.8},
 {id: 'b1', kind: 'box', at: [300, 600, 420, 70], text: '어떤 센서가 붙어 있나?', size: 0.9},
 {id: 'b2', kind: 'box', at: [300, 690, 420, 70], text: '어느 설비가 같이 쓰나?', size: 0.9},
 {id: 'know', kind: 'text', at: [1250, 590], text: '물으면 답이 나오는 지식', color: 'red'},
]};
// 1장: 이번 회차의 세 걸음
export const STEPS = {id: '세 걸음', board: [140, 330, 1640, 420], items: [
 {id: 's1', kind: 'box', at: [210, 430, 420, 130], text: '① 자료 살피기'},
 {id: 's2', kind: 'box', at: [750, 430, 420, 130], text: '② 스키마 정하고\n옮겨 담기'},
 {id: 's3', kind: 'box', at: [1290, 430, 420, 130], text: '③ 그래프 DB에 넣고\n묻기'},
 {id: 'a12', kind: 'arrow', from: 's1', to: 's2'}, {id: 'a23', kind: 'arrow', from: 's2', to: 's3'},
 {id: 'how', kind: 'text', at: [225, 610], text: 'AI와 함께 · 결과를 믿는 법'},
]};
// 6장: 블랙박스 — 판은 편집기 위(Codex 답을 가리지 않게 x 1330 안)
export const BLACKBOX = {id: '블랙박스', board: [420, 300, 900, 380], items: [
 {id: 'ask', kind: 'box', at: [460, 450, 240, 100], text: '알아서 해 줘'},
 {id: 'bb', kind: 'box', at: [790, 430, 220, 140], text: '', fill: 'black'},
 {id: 'out', kind: 'box', at: [1090, 450, 190, 100], text: '결과'},
 {id: 'in', kind: 'arrow', from: 'ask', to: 'bb'}, {id: 'ex', kind: 'arrow', from: 'bb', to: 'out'},
 {id: 'name', kind: 'text', at: [825, 360], text: '블랙박스', color: 'red'},
]};
// 7장: AI를 어디에 두고 일할까 — 왼쪽 ① 모를 때(나란히 물어 가며), 오른쪽 ② 알고 나면(내가 위에서 방향을 잡고 판단)
export const ROLE = {id: 'AI와 일하는 자리', board: [420, 240, 900, 540], items: [
 {id: 'h1', kind: 'box', at: [470, 400, 160, 90], text: '사람'},
 {id: 'a1', kind: 'box', at: [750, 400, 160, 90], text: 'AI'},
 {id: 'ha', kind: 'arrow', from: 'h1', to: 'a1'},
 {id: 'ah', kind: 'arrow', from: 'a1', to: 'h1', route: 'under', drop: 40},
 {id: 'k1', kind: 'text', at: [460, 320], text: '무엇에 쓸지', size: 0.85},
 {id: 'k2', kind: 'text', at: [720, 320], text: '파일을 다 읽는다', size: 0.85},
 {id: 't1', kind: 'text', at: [470, 620], text: '① 모를 때\n물어 가며 파악'},
 {id: 'h2', kind: 'box', at: [1080, 320, 160, 80], text: '사람'},
 {id: 'a2', kind: 'box', at: [1080, 480, 160, 80], text: 'AI'},
 {id: 'down', kind: 'arrow', from: 'h2', to: 'a2'},
 {id: 't2', kind: 'text', at: [1000, 620], text: '② 알고 나면\n내가 방향을 잡고 판단'},
]};
// 9장: 표가 이어지는 칸 — 설비코드로 셋, 품번으로 둘 더. 판은 편집기 위(x 1320 안), 아래 「물은 것 넷」 글상자(y 700~)와 겹치지 않게 y 670까지.
export const LINKS = {id: '표가 이어지는 칸', board: [440, 220, 880, 450], items: [
 {id: 'eq', kind: 'box', at: [480, 290, 230, 80], text: '설비 대장', size: 0.9},
 {id: 'se', kind: 'box', at: [1060, 290, 230, 80], text: '센서 표', size: 0.9},
 {id: 'co', kind: 'box', at: [770, 420, 230, 80], text: '구성 요소 표', size: 0.9},
 {id: 'e_c', kind: 'arrow', from: 'eq', to: 'co'}, {id: 'e_s', kind: 'arrow', from: 'eq', to: 'se'},
 {id: 'code', kind: 'text', at: [810, 240], text: '설비코드', color: 'red'},
 {id: 'sp', kind: 'box', at: [480, 570, 230, 80], text: '예비품 표', size: 0.9},
 {id: 'al', kind: 'box', at: [1060, 570, 230, 80], text: '품번 표기 표\npart_aliases', size: 0.8},
 {id: 'c_p', kind: 'arrow', from: 'co', to: 'sp'}, {id: 'p_a', kind: 'arrow', from: 'al', to: 'sp'},
 {id: 'pn', kind: 'text', at: [470, 505], text: '교체부품 — 품번', color: 'red', size: 0.85},
]};
// 9장: 엇갈리게 적힌 곳 석 줄. 「물은 것 넷」 글상자가 떠 있는 동안이라 글상자가 아니라 펜 그림의 글로 띄운다(글상자는 한 번에 하나다). 석 줄 테두리는 penTexts로 짚는다.
export const MIXED = {id: '엇갈린 곳', board: [440, 300, 880, 250], items: [
 {id: 'm1', kind: 'text', at: [480, 335], text: '다른 것인데 이름이 같다 — TS1 × 4대(HYD-01 ~ 04)', size: 0.85},
 {id: 'm2', kind: 'text', at: [480, 405], text: '같은 것인데 이름이 다르다 — 부품 하나에 번호 여럿', size: 0.85},
 {id: 'm3', kind: 'text', at: [480, 475], text: '같은 것일까? — 오일 쿨러와 열교환기', size: 0.85},
]};
// 10장: 이렇게 말하는 대신 → 이렇게(왼쪽 막연한 말 · 오른쪽 갖춘 말 · 끝에 꼬리표). 오른쪽 칸 글은 8장에서 실제로 보낸 부탁의 대목이다. 강사는 글을 읽지 않는다.
const RY = [330, 450, 570, 690], LX = 220, RX = 760, RW = 760, TX = 1540;
export const INSTEAD = {id: '이렇게 말하는 대신', board: [160, 200, 1620, 640], items: [
 {id: 'ttl', kind: 'text', at: [220, 235], text: '이렇게 말하는 대신   →   이렇게'},
 {id: 'L0', kind: 'box', at: [LX, RY[0], 340, 90], text: '현장 메모 정리해 줘', size: 0.9},
 {id: 'L1', kind: 'box', at: [LX, RY[0], 220, 90], text: '정리해 줘', size: 0.9},
 {id: 'L2', kind: 'box', at: [LX, RY[1], 250, 90], text: '이거 좀 봐 줘', size: 0.9},
 {id: 'L3', kind: 'box', at: [LX, RY[2], 480, 90], text: '다르게 적힌 데 있으면 알려 줘', size: 0.9},
 {id: 'L4', kind: 'box', at: [LX, RY[3], 250, 90], text: '알아서 해 줘', size: 0.9},
 {id: 'R1', kind: 'box', at: [RX, RY[0], RW, 90], text: '○○을 만들려고 해. 그 전에 자료부터 알고 싶어', size: 0.8},
 {id: 'R2', kind: 'box', at: [RX, RY[1], RW, 90], text: '메모에 적힌 파일 다섯 개가 data 폴더에 있는지,\n표마다 몇 행인지', size: 0.8},
 {id: 'R3', kind: 'box', at: [RX, RY[2], RW, 90], text: '어느 표 몇 행인지 예를 들고, 개수도 함께 알려 줘', size: 0.8},
 {id: 'R4', kind: 'box', at: [RX, RY[3], RW, 90], text: '파일은 바꾸지 말고, 모르는 것은 먼저 물어봐 줘', size: 0.8},
 {id: 'T1', kind: 'text', at: [TX, RY[0] + 28], text: '무엇에 쓸지', size: 0.8, color: 'red'},
 {id: 'T2', kind: 'text', at: [TX, RY[1] + 12], text: '볼 자료와\n알고 싶은 것', size: 0.8, color: 'red'},
 {id: 'T3', kind: 'text', at: [TX, RY[2] + 28], text: '답의 꼴', size: 0.8, color: 'red'},
 {id: 'T4', kind: 'text', at: [TX, RY[3] + 12], text: '지킬 것 ·\n되묻게 하기', size: 0.8, color: 'red'},
]};
export const INSTEAD_LEFT = [LX, RY[0], 480, RY[3] + 90 - RY[0]];   // 왼쪽 칸 전체(프레임 px)
