// 포털 지식 지도 구간(클라우드 Playwright · take.mjs). 큐 JSON을 읽어 조작한다. 이 PC ego판(vscode/촬영도구/segs/map-common.mjs)의 대상 · 가리키는 자리 · 굴리기 규칙을 옮기고,
// 화살표는 take.mjs의 가상 포인터로 바꿨다(페이지에 그리지 않고 이동만 기록 → encode.py가 그림). take.sh에 이 모듈 이름(map.mjs)을 그대로 준다.
// 큐: {id, segment, text, gap(이 큐 앞 쉼 초, 없으면 1.3), ops:[[조작, 대상, 시점], …]}. 시점은 0~1 비율이거나 {at:'대사 속 구절'}(그 구절이 시작하는 글자 비율).
//   큐 시작 + 길이 × 비율 − 300ms에 조작을 시작한다. 시점이 없는 조작은 앞 조작이 끝나면 한다. wait의 셋째 값은 기다릴 초.
// 조작: point · click · chip(칸 단추 체크 끄기, 대상은 칸 제목 글) · select(대상, 값) · type(글) · clear(입력칸 전체 고르기) · key(키) · scroll(대상 위끝을 창 위 top px 자리로, 대상에 bottom을 주면 대상 아래끝을 창 아래에서 bottom px 자리로)
//   · wait(대상이 하나 이상 나타날 때까지) · settle(문서 높이 · 굴린 자리가 1.2초 그대로일 때까지, 셋째 값은 최대 초 — 처리 건이 끝나며 위에 결과 칸이 끼어드는 화면).
// 대상: {css, contains, exact, nth, anchor, dx, dy} — 보이는 요소가 정확히 하나여야 한다(아니면 멈춘다). 가리키는 자리는 글을 가리지 않게 aim()이 고른다. after는 글 마지막 줄의 끝 바로 뒤다.
//   phrase: 그 요소 안 구절 하나(한 번만 나와야 한다)를 기준으로 anchor를 잡는다 — after(구절 끝 바로 뒤) · below(구절 밑) · center.
//   pathAt: SVG 선(path) 위의 길이 비율 자리. cy: 지식 지도 캔버스(Cytoscape, window.hydEnt.kg.cy)의 항목 id — 이름표가 보이면 이름표 끝, 아니면 점 오른쪽.
//     '@node' · '@edge'는 캔버스 가운데에 가장 가까운 항목 · 선이다. long: wait에서 6초 넘는 기다림을 실패로 치지 않는다(주입 뒤 경보 · 효과 확인처럼 일부러 기다리는 자리).
// 화면 밖 대상: 안쪽 스크롤 영역(지도 #ontoMap)부터 바깥(본문 main#content, 본문이 굴러가지 않는 판은 문서 자체)까지 페이지 안 애니메이션으로 굴린다. 굴리기는 화살표를 움직이지 않으므로 이동 기록에 넣지 않는다.
// 리허설(take.sh rehearse)이면 조작마다 ① 대상이 하나로 찾아지는가 ② 화살표가 덮는 글자 ③ 입력 시간(2.5초 이하) ④ 결과를 기다린 시간(6초 이하, long 제외)을 <take>/dry-<구간>.json에 남기고, 하나라도 어기면 멈춘다.
// 구간 1은 녹화 밖에서 포털 홈을 새로 열고 브라우저 저장값을 비운다(「서비스 N/N」의 앞뒤 숫자가 같고, 「나」 칸이 있는 판이면 「선택 안 함」인지 확인). 쉬는 화살표 자리는 ctx.rest(대상)가 있으면 그 대상, 없으면 REST다.
// 다음 구간은 앞 구간 끝 화면 그대로 — 브라우저(browser.mjs)가 상태를 쥐고 있다. 포털 주소는 ../config.json의 portal이다.
import fs from 'node:fs/promises';

const PORTAL = JSON.parse(await fs.readFile(new URL('../config.json', import.meta.url), 'utf8')).portal;
const LEAD = 300, CSS_W = 1280, CSS_H = 720;
const REST = {x: 760, y: 84};

export function fracOf(q, o) {
 if (o[0] === 'wait' || o[0] === 'settle') return null;
 const v = o.at(-1);
 if (typeof v === 'number') return v;
 if (v && typeof v === 'object' && v.at != null) {
  const i = q.text.indexOf(v.at);
  if (i < 0) throw Error(`${q.id}: 대사에 없는 구절 — ${v.at}`);
  return i / q.text.length;
 }
 return null;
}

function aim(t, kind) {
 if (t.anchor) return t;
 if (/\.o-node/.test(t.css)) return {...t, anchor: 'right', dx: 12};
 if (/chiptoggle/.test(t.css)) return {...t, anchor: 'left', dx: -14};
 if (/^#onto(Asset|Ns|Focus|Search)$/.test(t.css) || kind === 'click') return {...t, anchor: 'right'};
 // 상세 칸 · 지도 머리글은 그 글자 끝 바로 오른쪽을 짚는다(줄 왼쪽 바깥을 짚으면 어느 줄인지 안 보인다 — 사용자 2026-11-12 「마우스 커서가 좀 정확하지 않고」).
 // 속성 이름(th)은 그 줄의 값(td) 끝을 짚는다 — 이름 바로 뒤는 값 글자를 덮는다.
 if (/^#ontoNode \.kvt th/.test(t.css)) return {...t, anchor: 'value', dy: t.dy ?? -8};   // 표 줄이 촘촘해 꼬리가 아랫줄 값을 덮지 않게 조금 위
 if (/^#ontoNode \.o-kind/.test(t.css)) return {...t, anchor: 'after', dx: t.dx ?? -4, dy: t.dy ?? -14};   // 클래스 글씨 바로 밑이 큰 이름이라 꼬리가 닿지 않게 더 위
 if (/^#ontoNode/.test(t.css)) return {...t, anchor: 'after', dx: t.dx ?? -4, dy: t.dy ?? -6};   // 꼬리가 아래 줄 글을 덮지 않게 조금 위
 if (/\.o-lab|\.o-colh/.test(t.css)) return {...t, anchor: 'after', dx: t.dx ?? -4, dy: t.dy ?? -6};   // 바로 아래 머리글 · 노드 글을 꼬리가 덮지 않게 조금 위
 return {...t, anchor: 'after'};
}

function locateInPage(t) {
 const vis = (e) => { const b = e.getBoundingClientRect(); return b.width > 0 && b.height > 0 && e.checkVisibility({checkVisibilityCSS: true}); };
 const norm = (e) => e.textContent.trim().replace(/\s+/g, ' ');
 let e, x, y, b;
 if (t.cy) {
  // 지식 지도 캔버스: 항목은 DOM이 아니라 Cytoscape가 그린다. 좌표는 캔버스 안 렌더 좌표 + 캔버스 상자 자리
  const cy = window.hydEnt?.kg?.cy;
  if (!cy || !cy.nodes().length) return {error: '지식 지도 캔버스가 아직 그려지지 않음'};
  e = cy.container(); b = e.getBoundingClientRect();
  const W = cy.width(), H = cy.height(), live = (n) => n.visible() && !n.hasClass('dim') && !n.hasClass('gtitle');
  const near = (els, at) => els.reduce((m, el) => { const p = at(el), d = Math.hypot(p.x - W / 2, p.y - H / 2); return !m || d < m.d ? {el, d, p} : m; }, null);
  let p;
  if (t.cy === '@edge') { const m = near(cy.edges().filter((ed) => ed.visible() && !ed.hasClass('dim')), (ed) => ed.renderedMidpoint()); if (!m) return {error: '보이는 선 없음'}; p = m.p; }
  else {
   const n = t.cy === '@node' ? near(cy.nodes().filter(live), (nd) => nd.renderedPosition())?.el : cy.getElementById(t.cy);
   if (!n || !n.length || !n.visible()) return {error: `지식 지도 항목 없음 · 안 보임: ${t.cy}`};
   const lb = n.renderedBoundingBox({includeNodes: false, includeEdges: false, includeLabels: true}), q = n.renderedPosition();
   p = lb.w > 2 && n.style('label') ? {x: lb.x2 + 6, y: (lb.y1 + lb.y2) / 2} : {x: q.x + n.renderedWidth() / 2 + 4, y: q.y};
  }
  if (p.x < 0 || p.y < 0 || p.x > W || p.y > H) return {error: `지식 지도 항목이 캔버스 밖: ${t.cy}`};
  x = b.left + p.x; y = b.top + p.y;
 } else {
  let es = [...document.querySelectorAll(t.css)].filter(vis);
  if (t.contains) es = es.filter((el) => el.textContent.includes(t.contains));
  if (t.exact) es = es.filter((el) => norm(el) === t.exact);
  if (t.nth !== undefined) es = es.slice(t.nth, t.nth + 1);
  if (es.length !== 1 && !(t.any && es.length)) return {error: `대상 ${JSON.stringify({css: t.css, contains: t.contains, exact: t.exact})} — 보이는 요소 ${es.length}개`};
  e = es[0]; b = e.getBoundingClientRect();
  let r = b, rs = null;
  if (t.phrase) {
   // 구절 하나의 글자 상자를 기준으로 삼는다(줄이 꺾이면 마지막 줄 조각)
   const hits = [], w = document.createTreeWalker(e, NodeFilter.SHOW_TEXT);
   for (let n; (n = w.nextNode());) { for (let i = n.data.indexOf(t.phrase); i >= 0; i = n.data.indexOf(t.phrase, i + 1)) hits.push([n, i]); }
   if (hits.length !== 1) return {error: `구절 「${t.phrase}」이 ${hits.length}번: ${t.css}`};
   const g = document.createRange(); g.setStart(hits[0][0], hits[0][1]); g.setEnd(hits[0][0], hits[0][1] + t.phrase.length);
   rs = [...g.getClientRects()].filter((q) => q.width > 0); r = rs.at(-1) || g.getBoundingClientRect();
  }
  x = r.x + r.width / 2; y = r.y + r.height / 2;
  if (t.pathAt != null) { const L = e.getTotalLength(), q = e.getPointAtLength(L * t.pathAt), m = e.getScreenCTM(); x = m.a * q.x + m.c * q.y + m.e; y = m.b * q.x + m.d * q.y + m.f; }
  else if (t.anchor === 'right') { const r1 = e.getClientRects()[0] || b; x = r1.right - Math.min(r1.width / 2, 20); y = r1.top + r1.height / 2; }
  else if (t.anchor === 'left') { x = r.x + Math.min(r.width / 2, 28); }
  else if (t.anchor === 'margin') { const row = e.closest('li, tr') || e; x = Math.max(4, row.getBoundingClientRect().x - 24); y = r.y + Math.min(r.height / 2, 14); }
  else if (t.anchor === 'value') { const td = e.closest('tr')?.querySelector('td') || e; const g = document.createRange(); g.selectNodeContents(td); const q = g.getClientRects(); const last = q[q.length - 1] || td.getBoundingClientRect(); x = last.right + 8; y = last.top + last.height / 2; }
  else if (t.anchor === 'after') {
   let last = r;
   if (!rs) { const g = document.createRange(); g.selectNodeContents(e); rs = [...g.getClientRects()].filter((q) => q.width > 0); last = rs.at(-1) || b; }
   x = last.right + (t.phrase ? 4 : 12); y = last.top + last.height / 2;
  }
  else if (t.anchor === 'below') { x = r.x + Math.min(r.width / 2, 30); y = r.bottom + 6; }
 }
 x += t.dx || 0; y += t.dy || 0;
 const sc = [];
 let pinned = false;      // 고정 · 붙박이 칸(메뉴 줄 · 위 막대 · 열린 대화 상자) 안의 대상은 문서를 굴려도 움직이지 않는다
 for (let a = e.parentElement; a && a !== document.body && a !== document.documentElement; a = a.parentElement) {
  const cs = getComputedStyle(a);
  if (cs.position === 'fixed' || cs.position === 'sticky' || a.matches('dialog[open]')) pinned = true;
  const yv = /(auto|scroll)/.test(cs.overflowY) && a.scrollHeight > a.clientHeight + 2, xv = /(auto|scroll)/.test(cs.overflowX) && a.scrollWidth > a.clientWidth + 2;
  if (!yv && !xv) continue;
  // id 없는 스크롤 영역(에이전트 목록 div.list 등)은 보이지 않는 이름표를 달아 같은 길로 굴린다
  if (!a.id && !a.dataset.hydScroll) a.dataset.hydScroll = String((window.__hydScroll = (window.__hydScroll || 0) + 1));
  const r = a.getBoundingClientRect();
  sc.push({sel: a.id ? '#' + a.id : `[data-hyd-scroll="${a.dataset.hydScroll}"]`, top: Math.max(0, r.top), bottom: Math.min(innerHeight, r.top + a.clientHeight), left: r.left, right: r.left + a.clientWidth, xv, yv});
 }
 // 본문 칸이 아니라 문서가 굴러가는 판(위 막대가 sticky): 문서 자체를 마지막 스크롤 영역으로 둔다. 위 막대 아래부터가 보이는 자리다
 const de = document.scrollingElement;
 if (!pinned && de && de.scrollHeight > innerHeight + 2) {
  const bar = document.querySelector('header.topbar'), barB = bar && getComputedStyle(bar).position === 'sticky' ? bar.getBoundingClientRect().bottom : 0;
  sc.push({sel: 'html', top: Math.max(0, barB), bottom: innerHeight, left: 0, right: innerWidth, xv: false, yv: true});
 }
 const top = document.elementFromPoint(x, y);
 return {x, y, top: b.top, bt: b.bottom, bl: b.left, br: b.right, sc, hit: !!top && (top === e || e.contains(top)), h: innerHeight, w: innerWidth};
}

function coverInPage({x, y, css, contains, exact}) {
 const poly = [[1, 1], [1, 25], [7, 20], [12, 31], [17, 29], [12, 18], [22, 18]].map(([a, b]) => [a * 0.8, b * 0.8]);
 const inside = (px, py) => { let c = false; for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) { const [xi, yi] = poly[i], [xj, yj] = poly[j]; if ((yi > py) !== (yj > py) && px < (xj - xi) * (py - yi) / (yj - yi) + xi) c = !c; } return c; };
 let tgt = [...document.querySelectorAll(css)]; if (contains) tgt = tgt.filter((e) => e.textContent.includes(contains)); if (exact) tgt = tgt.filter((e) => e.textContent.trim().replace(/\s+/g, ' ') === exact);
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

function layer(ctx, report) {
 const rep = (o) => { if (report) report.push({cue: ctx.cueId, ...o}); };
 const name = (t) => t.css + (t.contains ? ` ~${t.contains}` : '') + (t.exact ? ` =${t.exact}` : '');
 const p = ctx.p, q1 = (fn) => ctx.serial(fn), sleep = ctx.sleep;
 const find = (t) => q1(() => p.evaluate(locateInPage, t)).then((r) => { if (r.error) throw Error(r.error); return r; });
 let pos = ctx.virtualPointer;
 const G = {lastMoveEnd: 0};
 // 가상 포인터 이동: 경로만 기록하고(encode.py가 그림) 도착 시각에 실제 입력을 목표로 한 번 보낸다(포털 ui.mjs virtual 갈래와 같은 속도식).
 async function move(x, y) {
  const a = pos, dist = Math.hypot(x - a.x, y - a.y);
  if (dist < 1) { G.lastMoveEnd = Date.now(); return; }
  const ms = Math.round(Math.max(260, Math.min(620, 200 + dist * 0.4))), t0 = Date.now();
  ctx.recordMotion({start: t0, end: t0 + ms, x, y, from: a, planned_ms: ms, glide: t0});
  if (!ctx.rehearsal) await sleep(ms);
  await q1(() => p.mouse.move(x, y, {steps: 1}));
  G.lastMoveEnd = Date.now(); pos = ctx.virtualPointer = {x, y};
 }
 async function over(s) {
  const a = pos;
  if (a.x >= s.left + 10 && a.x <= s.right - 10 && a.y >= s.top + 10 && a.y <= s.bottom - 10) return;
  const cl = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  await move(cl(a.x, s.left + 40, s.right - 40), cl(a.y, s.top + 60, s.bottom - 60));
 }
 async function glide(sel, dx, dy) {
  // 굴릴 수 있는 만큼만 굴린다(끝에 닿은 뒤에도 애니메이션이 도는 동안 화면이 멈춰 보이지 않게)
  [dx, dy] = await q1(() => p.evaluate(({sel, dx, dy}) => {
   const el = document.querySelector(sel); if (!el) return [dx, dy];
   const cw = sel === 'html' ? innerWidth : el.clientWidth, ch = sel === 'html' ? innerHeight : el.clientHeight;
   const cl = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
   return [cl(dx, -el.scrollLeft, el.scrollWidth - cw - el.scrollLeft), cl(dy, -el.scrollTop, el.scrollHeight - ch - el.scrollTop)];
  }, {sel, dx, dy}));
  if (Math.abs(dx) < 1 && Math.abs(dy) < 1) return;
  const ms = Math.round(Math.max(350, Math.min(1400, 220 + Math.hypot(dx, dy) * 0.55)));
  const g = await q1(() => p.evaluate(({sel, dx, dy, ms}) => {
   const el = document.querySelector(sel); if (!el) return null;
   const id = (window.__hydGlide = (window.__hydGlide || 0) + 1);      // 새 굴리기가 시작되면 앞 굴리기는 멈춘다(둘이 서로 다른 자리로 당기지 않게)
   // 2026-11 판 포털은 html에 scroll-behavior: smooth가 있어, 프레임마다 넣는 자리를 브라우저가 다시 부드럽게 늦춰 굴리기가 덜 끝났다 — 굴리는 동안만 끈다
   if (el.dataset.hydSb === undefined) el.dataset.hydSb = el.style.scrollBehavior;
   el.style.scrollBehavior = 'auto';
   const fx = el.scrollLeft, fy = el.scrollTop, s0 = performance.now();
   const step = (now) => { if (window.__hydGlide !== id) return; const u = Math.min(1, (now - s0) / ms), k = u * u * (3 - 2 * u); el.scrollLeft = fx + dx * k; el.scrollTop = fy + dy * k; if (u < 1) requestAnimationFrame(step); };
   requestAnimationFrame(step); return {id, x: fx + dx, y: fy + dy};
  }, {sel, dx, dy, ms}));
  if (!g) throw Error('굴릴 영역 없음: ' + sel);
  await sleep(ms + 120);
  // 리허설은 화면을 받지 않아 그리기(rAF)가 드물어 굴리기가 덜 끝난 채 다음 판정을 했다(06 v0653) — 끝 자리에 닿게 한다. 녹화에서는 이미 닿아 있어 바뀌는 것이 없다
  await q1(() => p.evaluate(({sel, g}) => {
   const el = document.querySelector(sel); if (!el || window.__hydGlide !== g.id) return;
   window.__hydGlide++; el.scrollLeft = g.x; el.scrollTop = g.y;
   el.style.scrollBehavior = el.dataset.hydSb || ''; delete el.dataset.hydSb;
  }, {sel, g}));
 }
 async function inView(t) {
  for (let i = 0; i < 8; i++) {
   const r = await find(t);
   const outY = (s) => s.yv && (r.y < s.top + 6 || r.y > s.bottom - 26), outX = (s) => s.xv && (r.bl < s.left - 2 || Math.min(r.br, r.x) > s.right - 26);   // 가로는 대상 상자로 잰다(왼쪽 여백을 가리키는 머리글은 가리킬 점이 지도 밖이다)
   // 창 가장자리 여백(위 60 · 아래 26)은 굴러가는 영역 안의 대상에만 건다. 어떤 스크롤 영역에도 들지 않는 고정 막대(위 막대 · 메뉴 머리)의 대상은 창 안이면 보인다.
   const winOut = r.sc.length ? (r.y < 60 || r.y > r.h - 26 || r.x < 4 || r.x > r.w - 26) : (r.y < 0 || r.y > r.h || r.x < 0 || r.x > r.w);
   const s = r.sc.find((s) => outY(s) || outX(s)) || (winOut ? (r.sc.find((s) => s.yv && s.sel === '#content') || r.sc.find((s) => s.yv)) : null);
   if (!s) { if (winOut) throw Error('창 밖 대상인데 굴릴 영역 없음: ' + JSON.stringify(t)); r.scrolled = i; return r; }
   if (t.inview) throw Error('대상이 화면 밖이라 누르지 않음(inview): ' + JSON.stringify(t));
   const lo = Math.max(s.top, 60), hi = Math.min(s.bottom, r.h - 26);
   const dy = (outY(s) || winOut) ? Math.round(r.y - (lo + (hi - lo) * (t.place ?? 0.4))) : 0;
   const dx = outX(s) ? Math.round(r.bl - (s.left + (s.right - s.left) * 0.3)) : 0;
   await over({...s, top: lo, bottom: hi}); await glide(s.sel, dx, dy);
  }
  throw Error('화면 안으로 들이지 못함: ' + JSON.stringify(t));
 }
 async function settled(t) {
  let r = await inView(t); const sc = r.scrolled;
  for (let k = 0; k < 10; k++) { await sleep(150); const r2 = await find(t); if (Math.hypot(r2.x - r.x, r2.y - r.y) <= 1) return Object.assign(r2, {scrolled: sc}); r = r2; }
  throw Error('대상 위치가 멈추지 않음: ' + JSON.stringify(t));
 }
 const gate = async () => { const w = G.lastMoveEnd + 150 - Date.now(); if (w > 0) await sleep(w); ctx.committed ??= Date.now(); };
 const L = {};
 L.point = async (t) => {
  const a = aim(t, 'point');
  if (t.cy) { const r = await settled(a); await move(r.x, r.y); rep({op: 'point', target: 'cy:' + t.cy, scrolled: r.scrolled || 0}); return; }      // 캔버스 글자는 DOM 글자가 아니라 덮음 검사를 하지 않는다
  const coverAt = (r) => q1(() => p.evaluate(coverInPage, {x: r.x, y: r.y, css: t.css, contains: t.contains, exact: t.exact}));
  let r = await settled(a), cover = await coverAt(r);
  // 기본 자리(글 끝 오른쪽)가 다른 글을 덮으면(아랫줄이 붙은 칸) 그 줄 왼쪽 여백을 짚는다. 녹화와 리허설이 같은 자리를 고르도록 늘 같은 차례로 본다
  if (cover.length && !t.anchor && a.anchor === 'after') {
   const r2 = await settled({...a, anchor: 'margin'}), c2 = await coverAt(r2);
   if (!c2.length) { r = r2; cover = c2; }
  }
  await move(r.x, r.y);
  rep({op: 'point', target: name(t), scrolled: r.scrolled || 0, covered: cover, fail: cover.length > 0, why: cover.length ? '화살표가 글을 덮음: ' + cover.join(' | ') : undefined});
 };
 L.click = async (t) => {
  const a = aim(t, 'click');
  for (let i = 0; i < 4; i++) {
   const r = await settled(a); await move(r.x, r.y); await gate();
   const now = await find(a);
   if (Math.hypot(now.x - r.x, now.y - r.y) > 2) continue;
   if (!now.hit) throw Error('누를 자리가 다른 요소에 가려짐: ' + JSON.stringify(t));
   await q1(() => p.mouse.click(r.x, r.y)); ctx.recordClick({x: r.x, y: r.y, target: t}); await sleep(150);
   rep({op: 'click', target: name(t), scrolled: r.scrolled || 0}); return;
  }
  throw Error('대상이 계속 움직임: ' + JSON.stringify(t));
 };
 L.chip = async (title) => {
  const checked = await q1(() => p.evaluate((title) => [...document.querySelectorAll('#ontoLayers .chiptoggle')].find((e) => e.textContent.includes(title))?.querySelector('input')?.checked, title));
  if (checked === undefined) throw Error('칸 단추 없음: ' + title);
  if (!checked) throw Error(`칸 단추 「${title}」가 이미 꺼짐 — 시작 상태 확인`);
  await L.click({css: '#ontoLayers .chiptoggle', contains: title});
 };
 L.scrollTop = async (t, top = 96) => {
  const r = await find(t); const s = r.sc.find((s) => s.yv);
  if (!s) throw Error('세로 스크롤 영역 없음: ' + JSON.stringify(t));
  const dy = Math.round(t.bottom != null ? r.bt - (r.h - t.bottom) : r.top - top); if (Math.abs(dy) <= 4) return;
  await over(s); await glide(s.sel, 0, dy);
 };
 // 고르기 칸: 헤드리스 녹화에는 운영체제 목록 창이 찍히지 않는다. 칸을 누른 뒤 값을 고르고 change를 보낸다(포털 ui.mjs select와 같다).
 L.select = async (t, label) => {
  await L.click(t); await gate();
  const ok = await q1(() => p.evaluate(({css, label}) => { const s = document.querySelector(css); const o = s && [...s.options].find((o) => o.textContent.trim() === label || o.value === label); if (!o) return false; s.value = o.value; s.dispatchEvent(new Event('change', {bubbles: true})); s.blur(); return true; }, {css: t.css, label}));
  if (!ok) throw Error('고를 항목 없음: ' + label); await sleep(200);
 };
 L.clear = async () => {
  const f = await q1(() => p.evaluate(() => document.activeElement?.matches('input,textarea') ? document.activeElement.id : null));
  if (!f) throw Error('지울 입력칸에 포커스가 없음');
  await gate(); await q1(() => p.keyboard.press('Control+a')); await sleep(250);
 };
 L.type = async (text) => {
  const f = await q1(() => p.evaluate(() => document.activeElement?.matches('input,textarea') ? document.activeElement.id : null));
  if (!f) throw Error('입력칸에 포커스가 없음: ' + text);
  await gate();
  // 검색 칸은 글자마다 지도를 다시 그린다 — 네 글자 이상은 두 덩이로 넣는다(map-common과 같다).
  const cs = [...text], parts = cs.length >= 4 ? [cs.slice(0, Math.ceil(cs.length / 2)).join(''), cs.slice(Math.ceil(cs.length / 2)).join('')] : [text];
  const t0 = Date.now();
  for (const part of parts) { await q1(() => p.keyboard.insertText(part)); await sleep(160); }
  const ms = Date.now() - t0; rep({op: 'type', text, ms, fail: ms > 2500, why: ms > 2500 ? `입력 ${ms}ms > 2500` : undefined});
 };
 L.key = async (k) => { await gate(); await q1(() => p.keyboard.press(k)); await sleep(200); };
 L.wait = async (t, secs) => {
  const a = Date.now(), limit = (secs || 30) * 1000, label = t.cy ? 'cy:' + t.cy : name(t);
  for (;;) {
   try { const r = await find({...t, any: true}); const ms = Date.now() - a, bad = ms > 6000 && !t.long;
    rep({op: 'wait', target: label, ms, long: !!t.long, fail: bad, why: bad ? `기다림 ${ms}ms > 6000` : undefined});
    if (ms > 500) ctx.recordWait?.({label: 'wait ' + label, start: a, end: Date.now()});
    return r; }
   catch (e) { if (Date.now() - a > limit) throw Error(`나타나지 않음(${secs}초): ${JSON.stringify(t)} — ${e.message}`); await sleep(150); }
  }
 };
 // 화면이 다 그려질 때까지: 문서 높이 · 굴린 자리가 1.2초 동안 그대로면 끝(최대 secs초). 처리 건이 끝나며 맨 위에 결과 칸이 끼어들어 아래 줄이 밀리는 동안 짚지 않으려고 둔다
 L.settle = async (secs = 10) => {
  const a = Date.now(); let last = null, since = a;
  for (;;) {
   const v = await q1(() => p.evaluate(() => { const d = document.scrollingElement, m = document.querySelector('main#content'); return [d.scrollTop, d.scrollHeight, m?.scrollTop, m?.scrollHeight].join('|'); }));
   if (v !== last) { last = v; since = Date.now(); } else if (Date.now() - since >= 1200) break;
   if (Date.now() - a > secs * 1000) break;
   await sleep(150);
  }
  rep({op: 'settle', ms: Date.now() - a});
  if (Date.now() - a > 1500) ctx.recordWait?.({label: 'settle', start: a, end: Date.now()});
 };
 L.op = async (o) => {
  const [k, a, b] = o;
  switch (k) {
   case 'point': return L.point(a);
   case 'click': return L.click(a);
   case 'chip': return L.chip(a);
   case 'scroll': return L.scrollTop(a, a.top ?? 96);
   case 'select': return L.select(a, b);
   case 'type': return L.type(a);
   case 'clear': return L.clear();
   case 'key': return L.key(a);
   case 'wait': return L.wait(a, typeof b === 'number' ? b : undefined);
   case 'settle': return L.settle(typeof b === 'number' ? b : undefined);
  }
  throw Error('모르는 조작 ' + k);
 };
 L.fresh = async () => {
  if (!(await q1(() => p.url())).startsWith(PORTAL)) await q1(() => p.goto(PORTAL, {waitUntil: 'domcontentloaded', timeout: 30000}));
  // 학생의 첫 화면처럼 이 브라우저가 기억하는 값(「나」 · 메뉴 줄 접기 · 고른 보기 …)을 모두 비운다
  await q1(() => p.evaluate(() => { localStorage.clear(); sessionStorage.clear(); }));
  await q1(() => p.goto('about:blank')); await q1(() => p.goto(PORTAL, {waitUntil: 'domcontentloaded', timeout: 30000}));
  const a = Date.now();
  // 서비스 수는 판마다 다르다(옛 판 13, 2026-11 판 16) — 앞뒤 숫자가 같은지만 본다. 「나」 칸(#shellMe)은 그 칸이 있는 옛 판에서만 본다
  const ready = () => { const m = /서비스\s*(\d+)\/(\d+)/.exec(document.body.innerText), me = document.querySelector('#shellMe');
   return !!m && m[1] === m[2] && (!me || /선택 안 함/.test(me.textContent)) && !!document.querySelector('[data-tab=ontology]'); };
  while (!(await q1(() => p.evaluate(ready)))) {
   if (Date.now() - a > 60000) throw Error('포털의 「서비스 N/N」 앞뒤 숫자가 다르거나 「나」가 선택 안 함이 아님 — 스택 확인 뒤 다시');
   await sleep(300);
  }
  await sleep(2500);
  await q1(() => p.evaluate(() => { for (const e of document.querySelectorAll('.rail, main#content')) e.scrollTop = 0; window.scrollTo(0, 0); }));
  const rest = ctx.rest ? await find(aim(ctx.rest, 'point')).then((r) => ({x: r.x, y: r.y})) : REST;
  await ctx.installPointer(rest); pos = ctx.virtualPointer = rest;
  await sleep(500);
 };
 L.view = () => q1(() => p.evaluate(() => ({
  tab: (document.querySelector('.rail nav button.active') || document.querySelector('#menuList a[aria-current=page]'))?.dataset.tab,
  main: document.querySelector('main#content')?.scrollTop, page: document.scrollingElement?.scrollTop,
  mapL: document.querySelector('#ontoMap')?.scrollLeft, mapT: document.querySelector('#ontoMap')?.scrollTop,
  search: document.querySelector('#ontoSearch')?.value, asset: document.querySelector('#ontoAsset')?.value,
  detail: document.querySelector('#ontoNode h3')?.textContent ?? null,
  hidden: [...document.querySelectorAll('#ontoLayers input')].filter((i) => !i.checked).map((i) => i.value) })));
 return L;
}

export async function seg(ctx, n) {
 const cues = JSON.parse(await fs.readFile(ctx.cueFile, 'utf8')).cues.filter((q) => String(q.segment) === String(n));
 if (!cues.length) throw Error(`${ctx.cueFile}: 구간 ${n} 큐 없음`);
 for (const q of cues) for (const o of q.ops || []) fracOf(q, o);   // 녹화 전에 시점 구절을 모두 확인한다
 const report = ctx.rehearsal ? [] : null;
 const L = layer(ctx, report);
 if (n === 1 && !ctx.resuming) await L.fresh();
 const css = await ctx.serial(() => ctx.p.evaluate(() => ({w: innerWidth, h: innerHeight})));
 if (css.w !== CSS_W || css.h !== CSS_H) throw Error(`화면 크기 CSS ${css.w}×${css.h} — ${CSS_W}×${CSS_H}이어야 한다`);
 await ctx.begin();
 try {
  for (const q of cues) {
   const dur = JSON.parse(await fs.readFile(ctx.audio + '/' + q.id + '.json', 'utf8')).duration_ms;
   const ops = q.ops || [];
   const fn = ops.length ? async () => {
    const t0 = Date.now() - LEAD;
    for (const o of ops) {
     const f = fracOf(q, o);
     if (f != null) { const w = t0 + Math.round(dur * f) - Date.now(); if (w > 0) await ctx.sleep(w); }
     ctx.commitAt = 0; await L.op(o);
     // 리허설은 어긴 조작에서 바로 멈춘다 — 같은 큐 뒤쪽의 되돌릴 수 없는 누르기(올리기 · 적재 · 주입 · 승인)를 하기 전에
     if (report?.some((r) => r.fail)) throw Error('DRY FAIL ' + JSON.stringify(report.filter((r) => r.fail)));
    }
   } : null;
   ctx.cueId = q.id;
   await ctx.say(q.id, fn, {pointDelay: 0, gap: Math.round((q.gap ?? 1.3) * 1000)});
   if (report?.some((r) => r.fail)) throw Error('DRY FAIL ' + JSON.stringify(report.filter((r) => r.fail)));
  }
 } finally {
  if (report) await fs.writeFile(`${ctx.out}/dry-${n}.json`, JSON.stringify(report, null, 1));
 }
 if (!ctx.rehearsal) await ctx.sleep(800);   // 마지막 조작의 결과가 프레임에 남도록
 return {view: await L.view()};
}
