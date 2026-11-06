// 포털 지식 지도 구간 공통(통합 2-05 m05-* · 실전 2-06 r06-*). 큐 JSON(포털 촬영도구 형식 ops)을 읽어 이 PC ego 녹화 공간에서 조작한다.
// 화면: VP='{width:1920,height:1080,dsf:1.5}'(ego 150 % → CSS 1280x720, 클라우드 정본과 같은 배율). CSS 1100 미만이면 상세 칸이 한 단으로 내려가 「오른쪽의 관계」가 아래로 간다.
// 시점: ops의 마지막 값이 0~1이면 그 비율, {at:'구절'}이면 대사에서 그 구절이 시작하는 글자 비율이다. 큐 시작 + 길이 × 비율 − 300ms에 그 조작을 시작한다
//   (포털 촬영도구 segs/one06.mjs와 같은 규칙). wait의 셋째 값은 기다릴 초다. 시점이 없는 조작은 앞 조작이 끝나면 바로 한다.
//   at 구절이 대사와 다르게 적힌 곳은 HYD-0N을 낭독(에이치와이디 영…)으로 읽고, 그래도 없으면 AT_FIX의 실제 구절로 잡는다(큐 글자 · id는 그대로).
// 대상: {css, contains} — 보이는 요소가 정확히 하나여야 한다(아니면 멈춘다). wait만 하나 이상 나타나면 된다. 가리키는 자리는 글을 가리지 않게 aim()이 고른다.
// 화면 밖 대상: 안쪽 스크롤 영역(지도 #ontoMap, 가로 · 세로)부터 바깥(본문 main#content)까지, 화살표를 그 영역 위에 둔 채 페이지 안 애니메이션으로 굴린다
//   (ego 휠은 찔끔찔끔 움직인다 — 포털 촬영도구 ui.mjs wheel 주석). 굴리기는 이동 기록(kind:'scroll')에 남아 measure.py가 프레임 간격을 잰다.
// 첫 구간(first)은 녹화 밖에서 포털 홈을 새로 열고 「나」를 비운다. 다음 구간은 앞 take가 돌려준 view(굴린 자리)로 되돌린 뒤 찍는다.
import fs from 'node:fs/promises';
import {vscode} from '../ui.mjs';

const HERE = decodeURIComponent(new URL('.', import.meta.url).pathname).replace(/^\/([A-Za-z]:)/, '$1');
const CUE_DIR = HERE + '../../../포털/';
const PORTAL = 'http://127.0.0.1:8088/';
const LEAD = 300;
const CSS_W = 1280, CSS_H = 720;
const REST = {x: 760, y: 84};   // 첫 구간 시작 화살표 자리(홈 제목 줄의 빈 곳 — 도식 · 카드를 가리지 않는다)
const READ = {'HYD-01': '에이치와이디 영일', 'HYD-02': '에이치와이디 영이', 'HYD-03': '에이치와이디 영삼'};
// 큐 ops의 at 구절이 대사 글자와 다른 곳 → 대사 속 실제 구절(같은 자리를 가리킨다).
const AT_FIX = {
 'm05-305': {'예측 모형에 관한': '포캐스트로 시작하는'},
 'm05-611': {'부품 번호 칸에': '품번 칸에'},
 'm05-805': {'이 지도에는': '이 지도는'},
 'r06-303': {'공급사 셋이': '공급사 셋,'},
 'r06-504': {'절들이 줄지어': '절 일곱 개가'},
 'r06-602b': {'공급사를 누르': '순정을 누르'},
};

export function fracOf(q, o) {
 if (o[0] === 'wait') return null;
 const v = o.at(-1);
 if (typeof v === 'number') return v;
 if (v && typeof v === 'object' && v.at != null) {
  let a = AT_FIX[q.id]?.[v.at] ?? v.at;
  if (!q.text.includes(a)) a = a.replace(/HYD-0[1-3]/g, (m) => READ[m]);
  const i = q.text.indexOf(a);
  if (i < 0) throw Error(`${q.id}: 대사에 없는 구절 — ${v.at}`);
  return i / q.text.length;
 }
 return null;
}

// 가리키는 자리: 지도 상자는 오른쪽 끝(이름 글자 밖), 층 단추는 체크 칸, 고르기 · 검색 칸은 칸 오른쪽, 누를 때는 대상 안 오른쪽, 상세 칸 안과 지도 클래스 머리글은 그 줄 왼쪽 여백, 나머지는 글 끝 오른쪽.
function aim(t, kind) {
 if (t.anchor) return t;
 if (/\.o-node/.test(t.css)) return {...t, anchor: 'right', dx: 12};
 if (/chiptoggle/.test(t.css)) return {...t, anchor: 'left', dx: -14};   // 층 단추: 체크 칸(글자 왼쪽)
 if (/^#onto(Asset|Ns|Focus|Search)$/.test(t.css) || kind === 'click') return {...t, anchor: 'right'};
 // 상세 칸(#ontoNode) 안은 그 줄의 왼쪽 여백을 가리킨다. 글 끝 오른쪽에 두면 화살표 몸통이 아랫줄 글(종류 아래 이름, 관계 묶음 제목 아래 첫 줄)을 덮었다(m05-3-t1).
 if (/^#ontoNode/.test(t.css)) return {...t, anchor: 'margin'};
 // 지도의 클래스 머리글도 왼쪽 여백 — 글 끝에 두면 바로 아래 상자 이름을 덮었다(m05-8-t1 m05-804 「센서 · 5」 아래 「냉각 효율 (가상)」).
 if (/\.o-lab/.test(t.css)) return {...t, anchor: 'margin'};
 return {...t, anchor: 'after'};
}

// 페이지 안에서 실행: 대상 하나의 가리킬 자리와, 대상을 담은 스크롤 영역들(안쪽부터).
function locateInPage(t) {
 const vis = (e) => { const b = e.getBoundingClientRect(); return b.width > 0 && b.height > 0 && e.checkVisibility({checkVisibilityCSS: true}); };
 let es = [...document.querySelectorAll(t.css)].filter(vis);
 if (t.contains) es = es.filter((e) => e.textContent.includes(t.contains));
 if (es.length !== 1 && !(t.any && es.length)) return {error: `대상 ${JSON.stringify({css: t.css, contains: t.contains})} — 보이는 요소 ${es.length}개`};
 const e = es[0], b = e.getBoundingClientRect();
 let x = b.x + b.width / 2, y = b.y + b.height / 2;
 // 오른쪽 끝은 첫 줄 상자에서 잡는다 — 두 줄로 접힌 링크는 전체 상자의 가운데 높이가 줄 사이 빈 곳이다(r06-502 「첫 단계」).
 if (t.anchor === 'right') { const r1 = e.getClientRects()[0] || b; x = r1.right - Math.min(r1.width / 2, 20); y = r1.top + r1.height / 2; }
 else if (t.anchor === 'margin') { const row = e.closest('li, tr') || e; x = Math.max(4, row.getBoundingClientRect().x - 24); y = b.y + Math.min(b.height / 2, 14); }
 else if (t.anchor === 'after') { const g = document.createRange(); g.selectNodeContents(e); const r = g.getBoundingClientRect(); x = (r.width ? r.right : b.right) + 12; }
 x += t.dx || 0;
 const sc = [];
 for (let a = e.parentElement; a && a !== document.body && a !== document.documentElement; a = a.parentElement) {
  const cs = getComputedStyle(a);
  const yv = /(auto|scroll)/.test(cs.overflowY) && a.scrollHeight > a.clientHeight + 2, xv = /(auto|scroll)/.test(cs.overflowX) && a.scrollWidth > a.clientWidth + 2;
  if (!yv && !xv) continue;
  if (!a.id) return {error: `이름 없는 스크롤 영역 ${a.tagName}.${a.className}`};
  const r = a.getBoundingClientRect();
  sc.push({sel: '#' + a.id, top: r.top, bottom: r.top + a.clientHeight, left: r.left, right: r.left + a.clientWidth, xv, yv});
 }
 const top = document.elementFromPoint(x, y);
 return {x, y, top: b.top, sc, hit: !!top && (top === e || e.contains(top))};
}

// 페이지 안에서 실행: 화살표 끝을 (x, y)에 둘 때 화살표 몸통(SVG 경로, 20×27)이 덮는 글자. 가리키는 대상의 글은 뺀다.
// 몸통 안 3px 격자 점마다 그 자리의 글자 한 칸(HTML은 caretRangeFromPoint, SVG는 text 요소)을 찾는다. 리허설의 ② 검사다.
function coverInPage({x, y, css, contains}) {
 const poly = [[1, 1], [1, 25], [7, 20], [12, 31], [17, 29], [12, 18], [22, 18]].map(([a, b]) => [a * 0.8, b * 0.8]);
 const inside = (px, py) => { let c = false; for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) { const [xi, yi] = poly[i], [xj, yj] = poly[j]; if ((yi > py) !== (yj > py) && px < (xj - xi) * (py - yi) / (yj - yi) + xi) c = !c; } return c; };
 let tgt = [...document.querySelectorAll(css)]; if (contains) tgt = tgt.filter((e) => e.textContent.includes(contains));
 const own = (n) => tgt.some((e) => e.contains(n));
 const hit = new Set();
 for (let dx = 0; dx <= 18; dx += 3) for (let dy = 0; dy <= 26; dy += 3) {
  if (!inside(dx, dy)) continue;
  const px = x + dx, py = y + dy, el = document.elementFromPoint(px, py); if (!el || own(el)) continue;
  const svgText = el.closest('text');
  if (svgText && svgText instanceof SVGElement) { if (!own(svgText)) hit.add(svgText.textContent.trim().slice(0, 20)); continue; }
  const r = document.caretRangeFromPoint(px, py); const n = r?.startContainer;
  if (!n || n.nodeType !== 3 || own(n)) continue;
  for (const o of [r.startOffset, r.startOffset - 1]) {
   if (o < 0 || o >= n.length || !n.data[o].trim()) continue;
   const g = document.createRange(); g.setStart(n, o); g.setEnd(n, o + 1); const b = g.getBoundingClientRect();
   if (px >= b.left && px <= b.right && py >= b.top && py <= b.bottom) { hit.add(n.data.slice(Math.max(0, o - 3), o + 4).trim()); break; }
  }
 }
 return [...hit];
}

function layer(ctx, c) {
 // 리허설 기록(ctx.report가 있을 때만): 조작마다 큐 id, 대상, 숫자, 실패 까닭.
 const rep = (o) => { if (ctx.report) ctx.report.push({cue: ctx.cueId, ...o}); };
 const p = ctx.p, q1 = (fn) => ctx.serial(fn), sleep = ctx.sleep;
 const find = (t) => q1(() => p.evaluate(locateInPage, t)).then((r) => { if (r.error) throw Error(r.error); return r; });
 const pos = () => q1(() => p.evaluate(() => { const r = document.getElementById('recording-pointer')?.getBoundingClientRect(); if (!r) throw Error('Recording pointer missing'); return {x: r.x, y: r.y}; }));
 // 화살표가 그 스크롤 영역 밖이면 영역 안으로 옮긴다(사람은 굴릴 곳 위에서 휠을 쓴다).
 async function over(s) {
  const a = await pos();
  if (a.x >= s.left + 10 && a.x <= s.right - 10 && a.y >= s.top + 10 && a.y <= s.bottom - 10) return;
  const cl = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  await move(cl(a.x, s.left + 40, s.right - 40), cl(a.y, s.top + 60, s.bottom - 60));
 }
 // 페이지 안 애니메이션 굴리기. 직렬 큐를 붙잡지 않도록 시작만 하고 바깥에서 기다린다(프레임 ACK가 밀리지 않게).
 async function glide(sel, dx, dy) {
  const ms = Math.round(Math.max(350, Math.min(1400, 220 + Math.hypot(dx, dy) * 0.55)));
  const a = await pos(), t0 = Date.now();
  const ok = await q1(() => p.evaluate(({sel, dx, dy, ms}) => {
   const el = document.querySelector(sel); if (!el) return false;
   const fx = el.scrollLeft, fy = el.scrollTop, s0 = performance.now();
   const step = (now) => { const u = Math.min(1, (now - s0) / ms), k = u * u * (3 - 2 * u); el.scrollLeft = fx + dx * k; el.scrollTop = fy + dy * k; if (u < 1) requestAnimationFrame(step); };
   requestAnimationFrame(step); return true;
  }, {sel, dx, dy, ms}));
  if (!ok) throw Error('굴릴 영역 없음: ' + sel);
  await sleep(ms + 120);
  ctx.recordMotion?.({start: t0, end: Date.now(), x: a.x, y: a.y, from: a, planned_ms: ms, kind: 'scroll', target: sel});
 }
 async function inView(t) {
  for (let i = 0; i < 8; i++) {
   const r = await find(t);
   // 가리킬 점이 영역 안(위 6 · 아래 20 · 왼쪽 6 · 오른쪽 26px 여백 — 화살표 몸통이 오른쪽 아래로 그려진다)이면 그대로 쓴다.
   const outY = (s) => s.yv && (r.y < s.top + 6 || r.y > s.bottom - 20), outX = (s) => s.xv && (r.x < s.left + 6 || r.x > s.right - 26);
   const s = r.sc.find((s) => outY(s) || outX(s));
   if (!s) { r.scrolled = i; return r; }
   // 대상에 inview:true가 있으면 굴리지 않는다 — 말이 굴리기를 말하지 않는 자리(r06-402 지도의 주 펌프). 화면 밖이면 멈춘다.
   if (t.inview) throw Error('대상이 화면 밖이라 누르지 않음(inview): ' + JSON.stringify(t) + ` y ${Math.round(r.y)} 영역 ${Math.round(s.top)}~${Math.round(s.bottom)}`);
   const dy = outY(s) ? Math.round(r.y - (s.top + (s.bottom - s.top) * 0.4)) : 0;
   const dx = outX(s) ? Math.round(r.x - (s.left + (s.right - s.left) * 0.3)) : 0;
   await over(s); await glide(s.sel, dx, dy);
  }
  throw Error('화면 안으로 들이지 못함: ' + JSON.stringify(t));
 }
 async function settled(t) {
  let r = await inView(t);
  const sc = r.scrolled;
  for (let k = 0; k < 10; k++) { await sleep(150); const r2 = await find(t); if (Math.hypot(r2.x - r.x, r2.y - r.y) <= 1) return Object.assign(r2, {scrolled: sc}); r = r2; }
  throw Error('대상 위치가 멈추지 않음: ' + JSON.stringify(t));
 }
 // 화살표 이동: 표시 화살표는 페이지 안 애니메이션으로 움직이고, 실제 입력은 도착한 뒤 목표 좌표로 한 번만 보낸다(포털 촬영도구 ui.mjs의 ego 방식).
 // 지도 화면에서 단계별 mouse.move는 한 번에 수백 ms씩 직렬 큐를 붙잡아 프레임 ACK가 밀리고, 이동 중 프레임이 0.3~0.8초 비어 화살표가 순간이동한 것처럼 찍혔다(m05-2-t1 · t2 · t3).
 const G = {lastMoveEnd: 0};
 async function move(x, y) {
  const a = await pos(), dist = Math.hypot(x - a.x, y - a.y);
  if (dist < 1) { G.lastMoveEnd = Date.now(); return; }
  const ms = Math.round(Math.max(260, Math.min(620, 200 + dist * 0.4))), t0 = Date.now();
  await q1(() => p.evaluate(({ax, ay, x, y, ms}) => window.__startGlide(ax, ay, x, y, ms), {ax: a.x, ay: a.y, x, y, ms}));
  await sleep(ms);
  for (let n = 0; n < 60 && await q1(() => p.evaluate(() => window.__glide && window.__glide !== 'hold')); n++) await sleep(20);
  await q1(() => p.mouse.move(x, y, {steps: 1}));
  await q1(() => p.evaluate(() => { window.__glide = null; }));
  ctx.recordMotion?.({start: t0, end: Date.now(), x, y, from: a, planned_ms: ms}); G.lastMoveEnd = Date.now();
 }
 const gate = async () => { const w = G.lastMoveEnd + 150 - Date.now(); if (w > 0) await sleep(w); ctx.committed ??= Date.now(); };
 const L = {};
 L.point = async (t) => {
  const a = aim(t, 'point'), r = await settled(a); await move(r.x, r.y);
  if (ctx.report) { const cover = await q1(() => p.evaluate(coverInPage, {x: r.x, y: r.y, css: t.css, contains: t.contains}));
   rep({op: 'point', target: t.css + (t.contains ? ` ~${t.contains}` : ''), scrolled: r.scrolled || 0, overlap: cover.length, covered: cover, fail: cover.length > 0, why: cover.length ? '화살표가 글을 덮음: ' + cover.join(' | ') : undefined}); }
 };
 L.click = async (t) => {
  const a = aim(t, 'click');
  for (let i = 0; i < 4; i++) {
   const r = await settled(a); await move(r.x, r.y); await gate();
   const now = await find(a);
   if (Math.hypot(now.x - r.x, now.y - r.y) > 2) continue;
   if (!now.hit) throw Error('누를 자리가 다른 요소에 가려짐: ' + JSON.stringify(t));
   await q1(() => p.mouse.click(r.x, r.y)); await sleep(150); rep({op: 'click', target: t.css + (t.contains ? ` ~${t.contains}` : ''), scrolled: r.scrolled || 0}); return;
  }
  throw Error('대상이 계속 움직임: ' + JSON.stringify(t));
 };
 // 대상의 윗변이 화면 위 top px 자리에 오도록, 대상을 담은 세로 스크롤 영역을 굴린다.
 L.scrollTop = async (t, top = 96) => {
  const r = await find(t); const s = r.sc.find((s) => s.yv);
  if (!s) throw Error('세로 스크롤 영역 없음: ' + JSON.stringify(t));
  const dy = Math.round(r.top - top); if (Math.abs(dy) <= 4) return;
  await over(s); await glide(s.sel, 0, dy);
 };
 // 고르기 칸: 화면 있는 ego에서 실제로 누르면 운영체제 목록 창이 떠 녹화에 안 찍히고 입력을 붙잡는다. 칸을 가리킨 뒤 값을 고르고 change를 보낸다.
 L.select = async (t, label) => {
  await L.point(t); await gate();
  const ok = await q1(() => p.evaluate(({css, label}) => { const s = document.querySelector(css); const o = s && [...s.options].find((o) => o.textContent.trim() === label || o.value === label); if (!o) return false; s.value = o.value; s.dispatchEvent(new Event('change', {bubbles: true})); s.blur(); return true; }, {css: t.css, label}));
  if (!ok) throw Error('고를 항목 없음: ' + label); await sleep(200);
 };
 L.type = async (text) => {
  const f = await q1(() => p.evaluate(() => document.activeElement?.matches('input,textarea') ? document.activeElement.id : null));
  if (!f) throw Error('입력칸에 포커스가 없음: ' + text);
  // 검색 칸은 글자가 들어올 때마다 지도 전체를 다시 그려(상자마다 글 길이를 잰다) 한 글자에 0.5~1초씩 걸렸다(r06-2-t1 「유압 파워팩」 6글자 약 6초, 말 없는 틈 5.2초).
  // 그래서 네 글자 이상은 두 덩이로 나눠 넣는다(빠른 타이핑처럼 보이고, 다시 그리기는 두 번).
  await gate();
  const parts = [...text].length >= 4 ? [[...text].slice(0, Math.ceil([...text].length / 2)).join(''), [...text].slice(Math.ceil([...text].length / 2)).join('')] : [text];
  const t0 = Date.now();
  for (const part of parts) { await q1(() => p.keyboard.insertText(part)); await sleep(160); }
  // ③ 입력에 걸린 시간. 2.5초를 넘으면 말 없는 틈이 생긴다(r06-2-t1 6글자 약 6초).
  const ms = Date.now() - t0; rep({op: 'type', text, ms, fail: ms > 2500, why: ms > 2500 ? `입력 ${ms}ms > 2500` : undefined});
 };
 L.key = async (k) => { await gate(); await q1(() => p.keyboard.press(k)); await sleep(200); };
 L.wait = async (t, secs) => {
  const a = Date.now(), limit = (secs || 30) * 1000;
  // ④ 결과가 그려질 때까지 기다린 시간. 6초를 넘으면 말 없이 멈춘 화면이 된다.
  for (;;) { try { const r = await find({...t, any: true}); const ms = Date.now() - a; rep({op: 'wait', target: t.css + (t.contains ? ` ~${t.contains}` : ''), ms, fail: ms > 6000, why: ms > 6000 ? `기다림 ${ms}ms > 6000` : undefined}); return r; } catch (e) { if (Date.now() - a > limit) throw Error(`나타나지 않음(${secs}초): ${JSON.stringify(t)} — ${e.message}`); await sleep(150); } }
 };
 L.op = async (o) => {
  const [k, a, b] = o;
  switch (k) {
   case 'point': return L.point(a);
   case 'click': return L.click(a);
   case 'scroll': return L.scrollTop(a, a.top ?? 96);
   case 'select': return L.select(a, b);
   case 'type': return L.type(a);
   case 'key': return L.key(a);
   case 'wait': return L.wait(a, b);
  }
  throw Error('모르는 조작 ' + k);
 };
 L.view = () => q1(() => p.evaluate(() => ({
  main: document.querySelector('main#content')?.scrollTop, rail: document.querySelector('aside#navigation, .rail')?.scrollTop,
  mapL: document.querySelector('#ontoMap')?.scrollLeft, mapT: document.querySelector('#ontoMap')?.scrollTop,
  search: document.querySelector('#ontoSearch')?.value, asset: document.querySelector('#ontoAsset')?.value,
  detail: document.querySelector('#ontoNode h3')?.textContent ?? null,
  hidden: [...document.querySelectorAll('#ontoLayers input')].filter((i) => !i.checked).map((i) => i.value),
  focus: document.activeElement?.id || document.activeElement?.tagName })));
 // 첫 구간 시작 상태(녹화 밖): 포털 홈을 새로 열고(지도 화면 상태가 처음으로 돌아간다) 「나」를 비운다. 위 막대가 서비스 13/13이어야 시작한다.
 L.fresh = async () => {
  if (!(await q1(() => p.url())).startsWith(PORTAL)) await q1(() => p.goto(PORTAL, {timeout: 30000}));
  await q1(() => p.evaluate(() => { localStorage.removeItem('hyd.me'); sessionStorage.clear(); }));
  await q1(() => p.goto('about:blank')); await q1(() => p.goto(PORTAL, {timeout: 30000}));
  const a = Date.now();
  while (!(await q1(() => p.evaluate(() => /서비스 13\/13/.test(document.body.innerText) && !!document.querySelector('button[data-tab=ontology]'))))) {
   if (Date.now() - a > 60000) throw Error('포털 위 막대가 서비스 13/13이 아님 — 스택 확인 뒤 다시');
   await sleep(300);
  }
  await sleep(2500);
  await q1(() => p.evaluate(() => { for (const e of document.querySelectorAll('aside#navigation, .rail, main#content')) e.scrollTop = 0; }));
  await c.installPointer(REST); await q1(() => p.mouse.move(REST.x, REST.y, {steps: 1}));
  await sleep(500);
 };
 // 다음 구간 시작 상태(녹화 밖): 앞 take 끝의 굴린 자리로 되돌린다(호출 사이에 화면 배율이 풀렸다 다시 걸리면 스크롤이 밀릴 수 있다).
 L.restore = async (v) => {
  if (!v) throw Error('앞 take의 view가 없음 — run.sh rec에 앞 구간 이름을 준다');
  await q1(() => p.evaluate((v) => { const m = document.querySelector('main#content'), r = document.querySelector('aside#navigation, .rail'), g = document.querySelector('#ontoMap'); if (m) m.scrollTop = v.main; if (r) r.scrollTop = v.rail; if (g) { g.scrollLeft = v.mapL; g.scrollTop = v.mapT; } }, v));
  const now = await L.view();
  for (const k of ['main', 'mapL', 'mapT', 'search', 'asset', 'detail']) if (typeof v[k] === 'number' ? Math.abs(now[k] - v[k]) > 1 : now[k] !== v[k]) throw Error(`앞 take 끝과 화면 상태가 다름: ${k} ${JSON.stringify(v[k])} → ${JSON.stringify(now[k])}`);
  await sleep(300);
 };
 return L;
}

// 한 구간 녹화. file = 포털 폴더의 큐 파일 이름(또는 절대 경로), n = 큐의 segment 값. ctx.rehearsal(run.sh dry)이면 대사 길이를 0으로 보고 조작만 차례로 하며,
// ctx.report에 조작마다 ① 대상이 하나로 찾아지고 화면 안에 들어왔는가(못 하면 멈춘다) ② 화살표가 덮는 글자 ③ 입력 시간 ④ 결과를 기다린 시간을 남긴다.
export async function mapSeg(ctx, file, n, {first = false} = {}) {
 const cues = JSON.parse(await fs.readFile(/^([A-Za-z]:|\/)/.test(file) ? file : CUE_DIR + file, 'utf8')).cues.filter((q) => String(q.segment) === String(n));
 if (!cues.length) throw Error(`${file}: 구간 ${n} 큐 없음`);
 for (const q of cues) for (const o of q.ops || []) fracOf(q, o);   // 녹화 전에 시점 구절을 모두 확인한다
 // 가리키는 자리와 상세 칸 두 단은 CSS 1280×720(VP {1920,1080,dsf:1})을 전제로 한다. 다르면 녹화 · 리허설 모두 멈춘다.
 const css = await ctx.serial(() => ctx.p.evaluate(() => ({w: innerWidth, h: innerHeight})));
 if (css.w !== CSS_W || css.h !== CSS_H) throw Error(`화면 크기 CSS ${css.w}×${css.h} — ${CSS_W}×${CSS_H}이어야 한다(VP='{width:1920,height:1080,dsf:1}')`);
 const c = await vscode(ctx);
 const L = layer(ctx, c);
 if (first) await L.fresh(); else if (!ctx.rehearsal) await L.restore(ctx.prev?.view);
 await ctx.begin();
 for (const q of cues) {
  const dur = ctx.rehearsal ? 0 : JSON.parse(await fs.readFile(ctx.audio + '/' + q.id + '.json', 'utf8')).duration_ms;
  const ops = q.ops || [];
  const fn = ops.length ? async () => {
   const t0 = Date.now() - LEAD;
   for (const o of ops) {
    const f = fracOf(q, o);
    if (f != null) { const w = t0 + Math.round(dur * f) - Date.now(); if (w > 0) await ctx.sleep(w); }
    ctx.commitAt = 0; await L.op(o);
   }
  } : null;
  const now = await ctx.serial(() => ctx.p.evaluate(() => innerWidth + '×' + innerHeight));
  if (now !== CSS_W + '×' + CSS_H) throw Error(`${q.id}: 화면 크기가 도중에 바뀜 — CSS ${now}`);
  ctx.cueId = q.id; await ctx.say(q.id, fn, {pointFrac: 0, pointDelay: 0});
 }
 // 마지막 조작의 결과(지도가 그려지는 등)가 녹화 프레임에 남도록 잠깐 둔다 — 화면이 바뀌어야 프레임이 오므로, 바로 끝내면 끝 프레임이 결과 전 화면이 된다(m05-1-t1).
 if (!ctx.rehearsal) await ctx.sleep(800);
 return {view: await L.view()};
}
