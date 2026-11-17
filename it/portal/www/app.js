/* Portal logic — plain JS, no framework, so students can read the whole flow in one file.
   Data comes from each service through the portal's own origin (/svc/<service>/… — nginx.conf passes it on; addresses in layers.js API).
   A122: wording comes from UI.terms (ui.js); cards · chips · folds · empty states from the UI helpers. APIs unchanged. */
const $ = (s, r = document) => r.querySelector(s);
const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
const fmt = (v, d = 1) => (v == null || isNaN(v)) ? '–' : Number(v).toFixed(d);
const HTTP_DEFAULT_DETAIL = { 'Not Found': '서버에 이 기능의 주소가 없습니다 — 서비스가 이 화면보다 이전 판일 수 있습니다', 'Method Not Allowed': '서버가 이 요청 방식을 받지 않습니다',
  'Internal Server Error': '서버 내부 오류', 'Bad Gateway': '중계 서버 오류', 'Service Unavailable': '서비스를 쓸 수 없는 상태입니다' };
const NETWORK_DOWN = '서비스에 연결하지 못했습니다(서비스가 꺼져 있거나 주소가 다릅니다). 서비스 상태를 확인한 뒤 다시 시도하세요.';
// 포털의 요청 함수 하나. options.timeout(ms): 기본은 읽기 8초 · 쓰기 30초, 0 이면 제한 없음(오래 걸리는 계산 · 채점처럼 화면이 따로 진행을 보일 때만).
// options.withHeaders: 응답 머리글도 필요할 때(파일 이름) — {body, headers} 를 돌려준다.
async function requestJ(url, options = {}) {
  const { timeout, withHeaders, ...init } = options;
  const limit = timeout != null ? timeout : init.method ? 30000 : 8000;
  const controller = new AbortController();
  const timer = limit > 0 ? setTimeout(() => controller.abort(), limit) : 0;
  try {
    const r = await fetch(url, { cache: 'no-store', ...init, signal: controller.signal });
    let j;
    try { j = await r.json(); }
    catch (_) { throw new Error(`서버 응답을 읽을 수 없습니다 (${r.status}). 다시 조회하세요.`); }
    if (!r.ok) {
      // 서버 프레임워크 기본 문구(영문)는 한국어 + 상태 번호로. 404 "Not Found" 는 그 주소가 없는 것 — 실행 중인 서비스가 이 화면보다 이전 판일 때 흔하다
      // 알려진 영문 거절 사유(T_approve is DONE 등)는 한국어 한 줄로(UI.serverText) — 원문은 error.detail 에 남긴다
      const detail = HTTP_DEFAULT_DETAIL[j.detail] ? `${HTTP_DEFAULT_DETAIL[j.detail]} (요청 실패 ${r.status})` : typeof j.detail === 'string' && typeof UI !== 'undefined' && UI.serverText ? UI.serverText(j.detail) : j.detail;
      const error = new Error(typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map(x => typeof UI !== 'undefined' && UI.validationText ? UI.validationText(x) : x.msg || JSON.stringify(x)).join(' · ') : typeof detail?.reason === 'string' ? detail.reason : `요청 실패 (${r.status})`);
      error.status = r.status; error.detail = j.detail; error.body = j;      // body: 서버가 까닭과 함께 실은 칸(409 의 instance · started_at 등)
      throw error;
    }
    return withHeaders ? { body: j, headers: r.headers } : j;
  } catch (e) {
    if (e.name === 'AbortError') throw new Error(init.method ? '응답 시간 초과. 처리 결과를 새로 확인한 뒤 다시 시도하세요.' : '응답 시간 초과. 연결 상태를 확인하세요.');
    if (e instanceof TypeError && e.status == null) throw new Error(NETWORK_DOWN);   // 연결 거부 · 네트워크 끊김(영문 Failed to fetch)
    throw e;
  } finally { clearTimeout(timer); }
}
const getJ = (url, options) => requestJ(url, options);
function requireList(value, label) {
  if (!Array.isArray(value)) throw new Error(`${label} 응답 형식이 올바르지 않습니다. 다시 조회하세요.`);
  return value;
}
const postJ = (url, body, method = 'POST', options = {}) => requestJ(url, { ...options, method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });

const state = { tab: 'main', plant: null, det: null, detError: '', incidents: [], log: [], showAll: false, incShown: 20 };

/* ---------------- 메뉴 · 화면 전환 ---------------- */
// 화면에 들어올 때 할 일: 화면 모듈은 selectTab 을 감싸지 않고 이 표에 적는다(실린 차례대로 불린다 — 셸이 맨 마지막). fn(name)
const tabHooks = [];
window.hydTabs = { onShow(fn) { tabHooks.push(fn); } };
/* 메뉴 표: index.html 의 메뉴 정의 한 곳(#menuList 의 button[data-menu][data-tabs][data-icon])을 읽는다. 메뉴 하나에 화면이 하나 이상 딸린다.
   메뉴 줄(이 파일 renderMenu) · 위 막대의 위치(updateNavigation) · 화면 찾기(shell.js)가 모두 이 표로 그려진다. 화면 이름(= 화면 제목)은 nav.<화면>, 메뉴 이름은 nav.menu.<메뉴>(ui.js).
   화면은 selectTab('<화면>') · 주소 #/<화면> · [data-go-tab="<화면>"] · 메뉴 줄 · 화면 찾기 어느 길로 열어도 그 화면이 든 메뉴가 펼쳐지고 그 화면이 고른 상태가 된다. */
const MENU = [...document.querySelectorAll('#menuList > button[data-menu]')].map(def =>
  ({ id: def.dataset.menu, name: UI.t('nav.menu.' + def.dataset.menu), icon: def.dataset.icon, tabs: def.dataset.tabs.split(/\s+/).filter(Boolean) }));
const SCREENS = MENU.flatMap(m => m.tabs);                    // 모든 화면(메뉴 표의 차례)
const tabName = tab => UI.t('nav.' + tab);
const menuOf = tab => MENU.find(m => m.tabs.includes(tab)) || null;
window.hydMenu = { list: MENU, screens: SCREENS, of: menuOf, name: tabName };
// 메뉴 표와 화면 구역(view-…)이 어긋나면 그 화면은 어느 메뉴로도 갈 수 없다 — 조용히 두지 않는다
{
  const views = [...document.querySelectorAll('main .view')].map(v => v.id.replace(/^view-/, ''));
  const lost = views.filter(v => !SCREENS.includes(v)), ghost = SCREENS.filter(s => !views.includes(s));
  if (lost.length || ghost.length) throw new Error(`주 메뉴 표(index.html data-tabs)와 화면 구역이 다릅니다 — 메뉴에 없는 화면: ${lost.join(', ') || '없음'} · 화면이 없는 메뉴 항목: ${ghost.join(', ') || '없음'}`);
}
/* 메뉴 줄(키트의 sidebar 마크업): 화면이 하나인 메뉴는 그 화면으로 가는 줄 하나, 둘 이상인 메뉴는 접기(details) — 펼치면 그 안의 화면이 들여쓰기로 보인다.
   줄마다 주소(#/<화면>)를 가진 링크라 새 탭으로도 열린다. 「처리 건」 곁의 건수 점(#navTodo — 내 차례인 처리 건 수)은 refreshTodoCount 가 채우고, 비어 있으면 CSS 가 그리지 않는다.
   이름 툴팁(data-tooltip)은 메뉴 줄을 접어 아이콘만 보일 때만 뜬다(portal-kit.css). */
const miniRail = () => document.documentElement.dataset.rail === 'mini' && matchMedia('(min-width: 768px)').matches;
function renderMenu() {
  const tip = m => `data-tooltip="${esc(m.name)}" data-side="right"`;
  $('#menuList').innerHTML = '<ul>' + MENU.map(m => m.tabs.length === 1
    ? `<li><a href="#/${esc(m.tabs[0])}" data-menu="${esc(m.id)}" data-tab="${esc(m.tabs[0])}" ${tip(m)}>${UI.icon(m.icon)}<span>${esc(m.name)}</span>${m.id === 'instances' ? '<span class="nav-count num" id="navTodo"></span>' : ''}</a></li>`
    : `<li><details><summary data-menu="${esc(m.id)}" ${tip(m)}>${UI.icon(m.icon)}<span>${esc(m.name)}</span></summary><ul>${
      m.tabs.map(t => `<li><a href="#/${esc(t)}" data-tab="${esc(t)}"><span>${esc(tabName(t))}</span></a></li>`).join('')}</ul></details></li>`).join('') + '</ul>';
}
// 그 화면이 든 메뉴를 펼치고(다른 메뉴는 접고) 그 화면의 줄을 고른 상태로 둔다
function markMenu(name) {
  const menu = menuOf(name);
  document.querySelectorAll('#menuList summary[data-menu]').forEach(s => {
    const on = s.dataset.menu === menu.id;
    if (on) s.dataset.active = 'true'; else delete s.dataset.active;
    s.parentElement.open = on;
  });
  document.querySelectorAll('#menuList a[data-tab]').forEach(a => { if (a.dataset.tab === name) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); });      // 상표(홈으로 가는 링크)는 메뉴 항목이 아니라 고른 표시를 받지 않는다
}
const lastTab = {};                                            // 메뉴 → 그 메뉴에서 마지막으로 본 화면(접은 메뉴 줄에서 아이콘을 누르면 그 화면으로 돌아간다)
function selectTab(name) {
  if (!document.getElementById('view-' + name)) return;
  const changed = state.tab !== name;
  state.tab = name;
  lastTab[menuOf(name).id] = name;
  markMenu(name);
  document.querySelectorAll('.view').forEach(v => v.classList.toggle('active', v.id === 'view-' + name));
  if (changed) window.scrollTo(0, 0);
  if (name === 'scenario') renderUnits();
  if (name === 'incidents') renderScada();
  if (name === 'trends') renderTrends();
  updateNavigation(name);
  tabHooks.forEach(fn => fn(name));
}
document.querySelectorAll('[data-term]').forEach(n => { const t = UI.t(n.dataset.term); if (t !== n.dataset.term) n.textContent = t; });
renderMenu();
UI.fillIcons();      // 틀(index.html)의 아이콘 자리([data-icon])를 채운다 — 메뉴 정의는 위에서 이미 목록으로 바뀌었다
// 메뉴 줄의 링크(상표 포함): 그 화면을 연다. Ctrl · Shift · 가운데 단추로 누르면 브라우저가 새 탭 · 새 창으로 연다(주소가 #/<화면> 이다)
$('#sidebar').addEventListener('click', e => {
  const link = e.target.closest('a[data-tab]');
  if (link) {
    if (e.button || e.ctrlKey || e.metaKey || e.shiftKey) return;
    e.preventDefault(); selectTab(link.dataset.tab); $('#content').focus({ preventScroll: true });
    return;
  }
  const head = e.target.closest('summary[data-menu]');
  if (!head) return;
  // 접은 메뉴 줄(아이콘만)에서는 안의 화면 목록이 보이지 않는다 — 아이콘을 누르면 그 메뉴에서 마지막으로 본 화면(없으면 첫 화면)을 연다
  if (miniRail()) { e.preventDefault(); const m = MENU.find(x => x.id === head.dataset.menu); selectTab(lastTab[m.id] || m.tabs[0]); return; }
  // 메뉴 이름 줄을 누르면 그 메뉴가 펼쳐진다(브라우저의 접기 동작). 고른 메뉴만 펼친다 — 펼쳐져 있던 다른 메뉴는 접는다
  document.querySelectorAll('#menuList details[open]').forEach(d => { if (d !== head.parentElement) d.open = false; });
});
/* 메뉴 줄 접기 · 펴기(위 막대 첫 단추): 넓은 폭에서는 아이콘만 남기고(html[data-rail="mini"] — 고른 값은 이 브라우저에 남긴다), 좁은 폭(768px 아래)에서는
   키트가 메뉴 줄을 겹쳐 뜨는 서랍으로 바꾸므로 그 서랍을 열고 닫는다. 서랍은 화면을 고르거나 바깥을 누르거나 Esc 를 누르면 닫힌다 */
const RAIL_KEY = 'hyd.rail';
const wide = matchMedia('(min-width: 768px)');
function setRail(mini) {
  if (mini) document.documentElement.dataset.rail = 'mini'; else delete document.documentElement.dataset.rail;
  // 단추의 이름이 누르면 일어날 일을 말한다(접혀 있으면 「펴기」). 눌린 모양(aria-expanded · aria-pressed)은 주지 않는다 — 키트가 그 상태의 글자 단추에 바탕색을 칠해 늘 눌려 있는 것처럼 보인다
  const label = UI.t(mini ? 'shell.railOpen' : 'shell.railFold'), button = $('#railToggle');
  button.setAttribute('aria-label', label); button.dataset.tooltip = label; button.dataset.side = 'bottom'; button.dataset.align = 'start';
}
{
  let saved = '';
  try { saved = localStorage.getItem(RAIL_KEY) || ''; } catch (e) { /* 저장소를 못 쓰는 브라우저 — 펼친 채로 시작한다 */ }
  setRail(saved === 'mini');
}
$('#railToggle').addEventListener('click', () => {
  const side = $('#sidebar');
  if (!wide.matches) { side.toggle(); return; }
  const mini = document.documentElement.dataset.rail !== 'mini';
  setRail(mini);
  try { localStorage.setItem(RAIL_KEY, mini ? 'mini' : 'full'); } catch (e) { /* 위와 같다 — 이번 화면에서만 접힌다 */ }
});
document.addEventListener('keydown', e => { if (e.key === 'Escape' && !wide.matches && $('#sidebar').getAttribute('aria-hidden') === 'false') { $('#sidebar').close(); $('#railToggle').focus(); } });
// 폭이 경계를 넘으면 메뉴 줄의 열림을 그 폭의 기본으로 되돌린다(넓으면 늘 보이고, 좁으면 닫힌 서랍)
wide.addEventListener('change', () => { const side = $('#sidebar'); if (typeof side.open === 'function') { if (wide.matches) side.open(); else side.close(); } });
function updateNavigation(name) {
  const menu = menuOf(name), many = menu.tabs.length > 1;
  // 위 막대의 위치: 「메뉴 › 화면」. 화면이 하나뿐인 메뉴는 이름이 같으므로 화면 이름만 보인다
  const group = $('#pageGroup'); group.hidden = !many; group.textContent = menu.name;
  $('#pageSep').hidden = !many;
  $('#pageLocation').textContent = tabName(name);
  document.title = `${tabName(name)} · HYD 포털`;
}
selectTab('main');

/* ---------------- 시스템 구성: 구조 그림 + 서비스 상태 ----------------
   밝은 캔버스 하나에 세로 띠 셋(OT · DMZ · IT) × 계층 아홉(layers.js 의 차례 그대로 — 위가 업무, 아래가 현장), 부품 상자, 길 넷(디자인기준 6-4).
   부품의 계층 · 영역 · 역할 · 현업 대응 · 주소 · 상태 확인 주소는 layers.js 의 표에서 읽는다. 이 화면이 갖는 것은 화면 이름 · 아이콘 · 띠 안의 칸과 길뿐이다.
   길은 실제 통로대로 그린다: 값은 설비 → 공장 브로커 → 공장 쪽 브리지 → DMZ 브로커 → 수집 중계 → 이벤트 저장 → 탐지 · 시계열로, 승인된 명령은 흐름 엔진 → 이벤트 저장 → 명령 관문 → DMZ 브로커 → 공장 쪽 브리지 → 공장 브로커 → 설비로.
   공장과 DMZ 사이의 두 길은 모두 공장 쪽 브리지가 DMZ 브로커에 먼저 접속해 연다(화살표는 값 · 명령이 가는 방향이고, 그 두 길 사이의 글이 연결을 여는 쪽을 말한다). */
const healthState = {};
// 선택 도구: 서비스 자체가 선택(optional)이거나, 서비스는 기본인데 사람이 여는 화면만 선택 도구(entryHealth — Redpanda 는 기본, Console 은 tools 프로필)인 것
const optionalOf = c => c.entryHealth || c.optional;
const SYS = {
  /* 그림의 치수(viewBox 단위). 캔버스가 화면 머리 아래를 가로 · 세로로 가득 쓰고 그림은 그 안에 통째로 맞춰진다(1440 × 900 창에서 한 단위가 약 0.93px).
     그림의 글자는 모두 14 단위 이상이다 — 그 창에서 13px 아래로 줄지 않는다(디자인기준 6-1). 상자 160 × 48, 줄 사이 76(상자 사이 28 — 길과 이름표가 그 사이를 지난다), 영역 띠 사이 12.
     범례는 그림 안 오른쪽 아래(영역 띠 밖의 빈 줄)에 있다 — 캔버스 위에 따로 줄을 차지하지 않는다 */
  W: 1240, NW: 160, NH: 48, y0: 110, dy: 76,
  band: { ot: [116, 192, 'OT', '현장 · 실시간 제어', 'cv-red'], dmz: [320, 368, 'DMZ', '값은 중계하고 명령은 검증한다', 'cv-amber'], it: [700, 528, 'IT', '업무 · 분석 · 지식 · AI', 'cv-blue'] },
  col: { ot: 212, d1: 414, d2: 594, a: 792, b: 964, c: 1136 },
  // 부품(layers.js 이름의 첫 낱말) → [화면 이름, 아이콘, 칸, 폭]
  node: {
    process: ['흐름 엔진', 'workflow', 'a'], portal: ['포털', 'layout-grid', 'b'], 'enterprise-sim': ['업무 시스템', 'receipt-text', 'c'],
    'agent-worker': ['AI 에이전트', 'bot', 'b'], agent: ['판단 서비스', 'scale', 'c'], Neo4j: ['지식 그래프', 'network', 'c'],
    FUXA: ['관제 화면', 'gauge', 'ot'], Grafana: ['추이 화면', 'chart-line', 'b'], Prometheus: ['서비스 감시', 'signal', 'c'],
    TimescaleDB: ['시계열 저장소', 'database', 'b'], 'connect-sink': ['시계열 기록', 'download', 'c'], detector: ['이상 탐지', 'activity', 'b'],
    'ot-bridge': ['공장 쪽 브리지', 'plug', 'ot'], 'cmd-gateway': ['명령 관문', 'shield-check', 'd1'], 'connect-ingest': ['수집 중계', 'arrow-up-right', 'd2'], Redpanda: ['이벤트 저장', 'layers', 'a'],
    EMQX: ['공장 브로커', 'radio', 'ot', 168], 'dmz-broker': ['DMZ 브로커', 'inbox', 'd2'], 'plant-sim': ['유압 설비 3기', 'factory', 'ot', 168],
  },
  ai: ['agent-worker', 'agent', 'Neo4j'],
  // 길의 종류와 범례의 말(그림 안 오른쪽 아래)
  legend: [['data', '값이 올라가는 길'], ['cmd', '승인된 명령이 내려가는 길'], ['ai', 'AI가 지식을 읽는 길'], ['sim', '명령 길 밖의 조작']],
};
const sysKey = c => c.name.split(' ')[0];
const sysComps = () => LAYERS.flatMap((L, row) => L.comps.map(c => ({ ...c, key: sysKey(c), layer: L.name, row })));
function sysStatus(c) {      // ok · down · wait(아직 확인 전) · opt(선택 도구 — 꺼져 있는 것이 보통) · none(상태를 재지 않는 부품)
  if (!c.health) return 'none';
  const h = healthState[c.health];
  if (c.optional) return h === 'up' ? 'ok' : 'opt';
  return h === 'up' ? 'ok' : h === 'down' ? 'down' : 'wait';
}
function sysStatusText(c) {
  const st = sysStatus(c);
  if (st === 'opt') return healthState[c.health] === 'off' ? '선택 도구 · 꺼져 있음' : '선택 도구';
  return { ok: '정상', down: '응답 없음', wait: '확인 중', none: '상태 확인 대상 아님' }[st];
}
function renderStack() {
  const stack = $('#stack'), comps = sysComps();
  const lost = comps.filter(c => !SYS.node[c.key]).map(c => c.name);
  if (lost.length) { stack.innerHTML = UI.errorBlock('구조 그림에 자리가 없는 부품이 있습니다', `부품 표(layers.js)에는 있는데 그림의 자리 표(app.js SYS.node)에 없습니다: ${lost.join(', ')}`); return; }
  // HB = 영역 띠가 끝나는 높이. 그 아래 한 줄은 영역 밖의 길(가상 설비 API 망 — SIM)이 지나고 오른쪽에 범례가 놓이는 자리다
  const { W, NW, NH, y0, dy } = SYS, HB = y0 + dy * (LAYERS.length - 1) + dy / 2, SIM = HB + 16, H = HB + 50;
  const at = Object.fromEntries(comps.map(c => { const [, , col, w] = SYS.node[c.key]; return [c.key, { x: SYS.col[col], y: y0 + c.row * dy, w: w || NW }]; }));
  const Lp = (k, d = 0) => [at[k].x - at[k].w / 2, at[k].y + d], Rp = (k, d = 0) => [at[k].x + at[k].w / 2, at[k].y + d];
  const Tp = (k, d = 0) => [at[k].x + d, at[k].y - NH / 2], Bp = (k, d = 0) => [at[k].x + d, at[k].y + NH / 2];
  const path = (pts, r = 10) => {      // 꺾이는 자리를 둥글게
    let d = `M${pts[0][0]},${pts[0][1]}`;
    for (let i = 1; i < pts.length - 1; i++) {
      const [px, py] = pts[i - 1], [x, y] = pts[i], [nx, ny] = pts[i + 1];
      const a = Math.min(r, Math.hypot(x - px, y - py) / 2), b = Math.min(r, Math.hypot(nx - x, ny - y) / 2);
      d += ` L${x - Math.sign(x - px) * a},${y - Math.sign(y - py) * a} Q${x},${y} ${x + Math.sign(nx - x) * b},${y + Math.sign(ny - y) * b}`;
    }
    const e = pts[pts.length - 1]; return d + ` L${e[0]},${e[1]}`;
  };
  const rowY = i => y0 + i * dy;      // 위에서 i 번째 계층의 가운데 높이
  const gw = at['cmd-gateway'], bus = at.Redpanda, br = at['ot-bridge'], dz = at['dmz-broker'];
  // 공장 쪽 브리지와 DMZ 브로커 사이의 두 길: 브리지의 오른쪽에서 나와 OT 띠와 DMZ 띠 사이(X_UP · X_DOWN)로 내려가, 비어 있는 맨 아래 계층의 DMZ 칸(Y_UP · Y_DOWN)을 지나
  // DMZ 브로커의 아래로 닿는다 — 명령 관문과 DMZ 브로커 사이(「검증을 통과한 명령」과 그 이름표의 자리)를 지나지 않는다. 값의 길이 바깥, 명령의 길이 안쪽이라 서로 가로지르지 않는다.
  // 관제 화면의 길은 OT 띠 왼쪽 가장자리(X_HMI)로 브리지 상자를 돌아 내려간다
  const X_UP = br.x + br.w / 2 + 16, X_DOWN = X_UP + 14, Y_DOWN = dz.y + NH / 2 + 34, Y_UP = Y_DOWN + 16, X_HMI = br.x - br.w / 2 - 8, GAP = NH / 2 + (dy - NH) / 2;
  /* 길: [종류, 꺾이는 점들, 이름표, 이름표 자리, 맞춤, 이름표 색(없으면 길의 종류)]. 이름표는 그 길 곁의 빈 자리에 둔다 — 다른 길 · 상자 · 이름표와 겹치지 않고 글자 높이만큼 떨어진다(시험이 실제 브라우저에서 잰다).
     「검증할 명령」은 이벤트 저장에서 한 계층 위(부품이 없는 스트림 처리 줄의 DMZ 칸)로 올라가 명령 관문의 위로 내려온다 — 상자 사이의 좁은 틈을 지나지 않는다.
     세로로 긴 두 길(경보 · 사건이 올라가는 길, 승인된 명령이 내려가는 길)의 이름표는 그 길 위에, 서로 다른 계층 높이에 둔다 */
  const P = [
    // 값이 올라가는 길
    ['data', [Tp('plant-sim', 34), Bp('EMQX', 34)]],
    ['data', [Tp('EMQX', 34), Bp('ot-bridge', 34)]],
    ['data', [Rp('ot-bridge', 12), [X_UP, br.y + 12], [X_UP, Y_UP], [dz.x + 34, Y_UP], Bp('dmz-broker', 34)], '연결은 공장 쪽이 엽니다', [(X_DOWN + dz.x - 34) / 2, Y_UP + 20], 'middle', 'plain'],      // 두 길(값 · 명령) 아래의 글 — 어느 한 길의 이름이 아니라 둘 다에 대한 말이라 길 색을 쓰지 않는다
    ['data', [Tp('dmz-broker', 20), Bp('connect-ingest', 20)]],
    ['data', [Rp('connect-ingest'), Lp('Redpanda')]],
    ['data', [Rp('Redpanda', -12), [at.detector.x, bus.y - 12], Bp('detector')]],
    ['data', [Rp('Redpanda', 12), [at['connect-sink'].x, bus.y + 12], Bp('connect-sink')]],
    ['data', [Lp('connect-sink'), Rp('TimescaleDB')]],
    ['data', [Tp('TimescaleDB'), Bp('Grafana')]],
    ['data', [Tp('Redpanda', -30), Bp('process', -30)], '경보 · 사건', [bus.x - 30, rowY(2) + 5], 'middle'],
    // 승인된 명령이 내려가는 길
    ['cmd', [Bp('process', 30), Tp('Redpanda', 30)], '승인된 명령', [bus.x + 30, rowY(3) + 5], 'middle'],
    ['cmd', [Tp('Redpanda', -56), [bus.x - 56, at.detector.y], [gw.x, at.detector.y], Tp('cmd-gateway')], '검증할 명령', [(gw.x + bus.x - 56) / 2 - 40, at.detector.y - 11], 'middle'],
    ['cmd', [Bp('cmd-gateway'), [gw.x, dz.y], Lp('dmz-broker')], '검증을 통과한 명령', [dz.x - dz.w / 2 - 16, dz.y + 19], 'end'],
    ['cmd', [Bp('dmz-broker', -34), [dz.x - 34, Y_DOWN], [X_DOWN, Y_DOWN], [X_DOWN, br.y - 12], Rp('ot-bridge', -12)]],
    ['cmd', [Bp('ot-bridge', -34), Tp('EMQX', -34)]],
    ['cmd', [Bp('EMQX', -34), Tp('plant-sim', -34)]],
    // AI 가 지식을 읽는 길
    ['ai', [Bp('process', 56), [at.process.x + 56, at['agent-worker'].y], Lp('agent-worker')]],
    ['ai', [Rp('agent-worker'), Lp('agent')]],
    ['ai', [Bp('agent'), Tp('Neo4j')]],
    // 그 밖의 연결
    ['plain', [Lp('FUXA'), [X_HMI, at.FUXA.y], [X_HMI, br.y + GAP], [at.EMQX.x - 62, br.y + GAP], Tp('EMQX', -62)], '감시 · 수동 조작', [X_HMI + 8, rowY(5) - 9], 'start'],
    ['plain', [Lp('portal'), Rp('process')]],      // 사람은 포털에서 승인한다
    ['plain', [Tp('process', 34), [at.process.x + 34, at.process.y - NH / 2 - 14], [at['enterprise-sim'].x, at.process.y - NH / 2 - 14], Tp('enterprise-sim')], '정비 요청 · 구매', [at.portal.x, at.process.y - NH / 2 - 22], 'middle'],
    // 명령 길 밖: 흐름 엔진 · 포털 → 가상 설비 API(sim-net). 영역 띠 바깥(아래)으로 돌아 설비에 직접 닿는다 — 브로커와 명령 관문을 지나지 않는다
    ['sim', [Lp('process'), [SYS.band.it[0] - 6, at.process.y], [SYS.band.it[0] - 6, SIM], [at['plant-sim'].x, SIM], Bp('plant-sim')], '결함 주입 · 현장 패널 · 정비 수행 — 가상 설비에 직접(sim-net), 브로커와 명령 관문을 거치지 않음', [SYS.band.it[0] - 18, SIM + 22], 'end'],
  ];
  const COLOR = { data: 'var(--cv-blue)', cmd: 'var(--cv-amber)', ai: 'var(--cv-violet)', plain: 'var(--cv-edge)', sim: 'var(--cv-red)' };
  const netsOf = zone => NETS.filter(n => n.zone === zone).map(n => n.id).join(' · ');
  const node = c => {
    const [title, icon] = SYS.node[c.key], { x, y, w } = at[c.key], x0 = x - w / 2, y0n = y - NH / 2;
    return `<a class="sys-nd comp" data-key="${esc(c.key)}" data-zone="${esc(c.zone)}" data-st="${sysStatus(c)}"${SYS.ai.includes(c.key) ? ' data-ai' : ''} ${c.url ? `href="${esc(c.url)}" target="_blank" rel="noopener"` : 'tabindex="0"'} aria-label="${esc(title)} (${esc(c.key)}) — ${esc(c.layer)}">
      <title>${esc(title)} (${esc(c.key)}) — ${esc(c.role)}${c.real ? ` · 현업에서는 ${esc(c.real)}` : ''}</title>
      <rect class="box" x="${x0}" y="${y0n}" width="${w}" height="${NH}" rx="12"/>
      <rect class="ib" x="${x0 + 10}" y="${y - 14}" width="28" height="28" rx="8"/>
      <svg class="ico" x="${x0 + 16}" y="${y - 8}" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><use href="vendor/lucide/icons.svg#${icon}"/></svg>
      <text class="t" x="${x0 + 46}" y="${y - 3}">${esc(title)}</text><text class="s" x="${x0 + 46}" y="${y + 15}">${esc(c.key)}</text>
      <circle class="st" cx="${x0 + w - 12}" cy="${y0n + 11}" r="4"/></a>`;
  };
  // 계층 이름: 교재의 「Layer 9 · 프로세스 · 승인 · 앱」을 세 줄(번호 · 첫 낱말 · 나머지)로 — 왼쪽 칸을 좁혀 그림에 폭을 준다. 나머지가 길면 한 줄을 더 쓴다
  const layerLines = (L, i) => {
    const [head, ...rest] = L.name.split(' · '), tail = rest.join(' · ');
    const more = !tail ? [] : tail.length <= 8 ? [tail] : rest;
    const lines = [['sys-row-n', `Layer ${LAYERS.length - i}`], ['sys-row-t', head], ...more.map(t => ['sys-row-cap', t])], top = rowY(i) - (lines.length - 1) * 8.5 + 5;
    return lines.map(([cls, t], k) => `<text class="${cls}" x="16" y="${top + k * 17}">${esc(t)}</text>`).join('');
  };
  // 범례(영역 띠 아래 오른쪽): 두 줄 × 두 칸
  const LX = SYS.band.it[0] + SYS.band.it[1] - 392, legend = SYS.legend.map(([k, t], n) => { const x = LX + (n % 2) * 180, y = HB + 20 + Math.floor(n / 2) * 20;
    return `<path class="sys-p sys-lg" data-k="${k}" d="M${x},${y - 5} h26"/><text class="sys-lg-t" x="${x + 34}" y="${y}">${esc(t)}</text>`; }).join('');
  stack.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="group" aria-label="OT · DMZ · IT 세 영역과 계층 아홉의 부품, 값이 올라가는 길과 승인된 명령이 내려가는 길">
    <defs>${Object.entries(COLOR).map(([k, c]) => `<marker id="sysAh-${k}" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M1,1.5 L9,5 L1,8.5" fill="none" stroke="${c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></marker>`).join('')}</defs>
    ${Object.entries(SYS.band).map(([zone, [x, w, name, what, color]]) => `<rect class="sys-band" x="${x}" y="12" width="${w}" height="${HB - 12}" rx="14" style="fill:color-mix(in srgb, var(--${color}) 4%, transparent);stroke:color-mix(in srgb, var(--${color}) 40%, transparent)"/>` +
      `<text class="sys-band-t" x="${x + 16}" y="38" style="fill:var(--${color})">${name}</text><text class="sys-band-s" x="${x + 16 + name.length * 13 + 10}" y="38">${esc(what)}</text>` +
      `<text class="sys-band-n" x="${x + 16}" y="59">망 ${esc(netsOf(zone))}</text>`).join('')}
    <text class="sys-row-t" x="16" y="38">계층</text><text class="sys-row-cap" x="16" y="57">위가 업무</text><text class="sys-row-cap" x="16" y="74">아래가 현장</text>
    ${LAYERS.map((L, i) => `${i % 2 ? '' : `<rect class="sys-row-bg" x="8" y="${rowY(i) - dy / 2 + 3}" width="${W - 16}" height="${dy - 6}" rx="10"/>`}${layerLines(L, i)}`).join('')}
    ${P.map(([k, pts], i) => `<path class="sys-p" data-k="${k}" data-i="${i}" d="${path(pts)}" marker-end="url(#sysAh-${k})"/>`).join('')}
    ${P.map(([k, , t, pos, anchor, tk], i) => t ? `<text class="sys-p-t" data-k="${tk || k}" data-i="${i}" x="${pos[0]}" y="${pos[1]}" text-anchor="${anchor}">${esc(t)}</text>` : '').join('')}
    ${comps.map(node).join('')}
    <g class="sys-legend" aria-label="길의 종류">${legend}</g>
    <rect id="sysSlot" x="${SYS.band.it[0] + 12}" y="${bus.y + NH / 2 + 10}" width="${SYS.band.it[1] - 24}" height="${HB - 10 - (bus.y + NH / 2 + 10)}" fill="none" pointer-events="none"/></svg>`;
  // 그림 아래: 이 구성이 현업 공장과 다른 곳(layers.js SYS_DIFFS) — 이름 + 한 문장씩
  $('#sysDiffs').innerHTML = SYS_DIFFS.map(d => `<div class="sys-diff">${UI.icon(d.icon)}<dt>${esc(d.name)}</dt><dd>${esc(d.text)}</dd></div>`).join('');
  sysShow(null); sysPlace();
}
// 정보 카드의 자리: 그림에서 늘 비어 있는 칸(IT 영역의 이벤트 저장 상자 아래 — 아래 두 계층, #sysSlot)에 맞춰 캔버스 위에 띄운다. 그림이 창에 맞춰 커지고 줄어도 부품 상자를 가리지 않는다.
// 좁은 폭(그림을 끌어서 보는 폭)에서는 CSS 가 이 값을 쓰지 않고 카드를 그림 아래에 둔다
function sysPlace() {
  const slot = $('#sysSlot'), info = $('#sysInfo'); if (!slot) return;
  const s = slot.getBoundingClientRect(), c = info.parentElement.getBoundingClientRect(); if (!s.width || !c.width) return;
  info.style.setProperty('--slot-l', `${Math.round(s.left - c.left)}px`); info.style.setProperty('--slot-t', `${Math.round(s.top - c.top)}px`);
  info.style.setProperty('--slot-w', `${Math.round(s.width)}px`); info.style.setProperty('--slot-h', `${Math.round(s.height)}px`);
}
// 정보 띠: 고른 부품의 이름 · 하는 일 · 「현업에서는 …」 · 상태 · [열기]. 아무것도 고르지 않았으면 안내 한 줄
let sysPicked = null, sysNote = '';
function sysShow(key) {
  const info = $('#sysInfo'), c = key && sysComps().find(x => x.key === key);
  if (sysPicked !== key) sysNote = '';
  sysPicked = c ? key : null;
  document.querySelectorAll('#stack .sys-nd').forEach(n => n.toggleAttribute('data-on', n.dataset.key === sysPicked));
  // 아무것도 고르지 않았을 때: 쓰는 법 한 줄(명령 길 밖의 조작은 그림의 빨간 길과 그림 아래 목록이 말한다)
  if (!c) { info.innerHTML = `<p class="sys-hint">${UI.icon('info')}부품에 올리면 하는 일과 상태가 보이고, 누르면 그 도구가 새 탭으로 열립니다. 점선 상자는 꺼 두어도 되는 선택 도구입니다.</p>`; return; }
  const [title, icon] = SYS.node[c.key], st = sysStatus(c);
  const nets = c.nets.map(id => `<span title="${esc((NETS.find(n => n.id === id) || {}).what || '')}">${esc(id)}</span>`).join(', ');
  info.innerHTML = `<h3>${UI.icon(icon)}${esc(title)} <code class="mono">${esc(c.key)}</code><small>Layer ${LAYERS.length - c.row} · ${esc(c.zone.toUpperCase())}</small></h3>` +
    `<span class="state"><i class="dot"${st === 'ok' ? ' data-tone="ok"' : st === 'down' ? ' data-tone="danger"' : ''}></i>${esc(sysNote || sysStatusText(c))}</span>` +
    (c.url ? `<a class="btn-cv open" href="${esc(c.url)}" target="_blank" rel="noopener" data-sys-open="${esc(c.key)}">열기${UI.icon('external-link')}</a>` : '') +      // 여는 화면이 없는 부품은 [열기]를 두지 않는다
    `<p>${esc(c.role)}${c.real ? ` <b>· 현업에서는 ${esc(c.real)}</b>` : ''} <span class="sys-nets">· 망 ${nets}</span></p>${c.url ? '' : `<p>${esc(c.how || '여는 화면이 없습니다.')}</p>`}` +
    (c.key === 'detector' && (state.leftOut || []).length ? `<p class="sys-warn"><b>감지에서 빠진 이상 패턴 ${state.leftOut.length}</b> — ${state.leftOut.map(r => esc(leftOutLine(r))).join(' / ')}</p>` : '');
}
// 감지에서 빠진 이상 패턴 한 줄: 이름(코드) — 까닭. 까닭이 영문 예외 글이면 한국어 틀을 씌우고 원문을 그대로 붙인다(지어 옮기지 않는다)
const requireListOr = x => Array.isArray(x) ? x : [];
function leftOutLine(r) {
  const name = r.code ? `${UI.patternName(r.code)}${UI.patternName(r.code) !== r.code ? ` (${r.code})` : ''}` : (r.id || '이름 없는 패턴');
  const reason = String(r.reason || '까닭 기록 없음');
  return `${name} — ${/[가-힣]/.test(reason) ? reason : `조건식을 읽지 못했습니다 (원문: ${reason})`}`;
}
// 결함 시뮬레이션 머리 아래: 빠진 패턴이 있을 때만 한 판(없으면 자리도 없다)
function paintLeftOut() {
  const box = $('#labLeftOut'), out = state.leftOut || [];
  const sig = JSON.stringify(out); if (box.dataset.sig === sig) return; box.dataset.sig = sig;
  box.hidden = !out.length;
  box.innerHTML = out.length ? `<div class="alert" role="status">${UI.icon('triangle-alert')}<h2>이상 패턴 ${out.length}개가 감지에서 빠져 있습니다</h2><section>이 패턴의 결함은 넣어도 경보가 나지 않습니다. 지식 지도에서 그 패턴의 조건식을 고치면 다시 감지합니다.<ul>${out.map(r => `<li>${esc(leftOutLine(r))}</li>`).join('')}</ul></section></div>` : '';
}
function paintHealth() {
  const comps = sysComps();
  document.querySelectorAll('#stack .sys-nd').forEach(n => { const c = comps.find(x => x.key === n.dataset.key); if (c) n.dataset.st = sysStatus(c); });
  // 머리 오른쪽 요약: 선택 도구는 세지 않는다(꺼져 있는 것이 보통이다)
  const need = comps.filter(c => c.health && !c.optional), bad = need.filter(c => healthState[c.health] === 'down'), wait = need.filter(c => !healthState[c.health]);
  const sum = $('#sysSum');
  // 머리에는 응답 없는 서비스가 있을 때만 적는다 — 정상일 때의 「서비스 14/14」는 메뉴 줄 아래 한 곳에 있다
  const out = state.leftOut || [];
  sum.hidden = !bad.length && !out.length;
  if (bad.length) { sum.dataset.tone = 'danger'; sum.textContent = sum.title = `응답 없음 ${bad.length} — ${bad.map(c => c.key).join(', ')}`; }
  else if (out.length) { sum.dataset.tone = 'warn'; sum.textContent = `감지에서 빠진 이상 패턴 ${out.length}`; sum.title = out.map(leftOutLine).join('\n'); }
  if (sysPicked) sysShow(sysPicked);
}
// 선택 도구(Prometheus · Redpanda Console)는 5초 상태 확인에서 뺀다 — 꺼진 포트에 보내는 요청은 어느 방식이든 브라우저가 콘솔에 연결 거부 오류를 남긴다.
// 열려고 누를 때만 한 번 확인해 켜져 있으면 열고, 꺼져 있으면 정보 띠에 그 사실을 적는다.
async function reachable(url) {
  const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 3000);
  try { await fetch(url, { mode: 'no-cors', cache: 'no-store', signal: controller.signal }); return true; }
  catch (_) { return false; }
  finally { clearTimeout(timer); }
}
async function openOptional(c) {
  sysNote = '켜져 있는지 확인 중'; sysShow(c.key);
  const up = await reachable(c.entryHealth || c.health || c.url);
  if (c.optional && c.health) healthState[c.health] = up ? 'up' : 'off';
  sysNote = up ? '' : c.optional ? '꺼져 있음 — 켜면 열립니다' : '여는 화면이 꺼져 있음 — 켜면 열립니다';
  paintHealth(); sysShow(c.key);
  if (up) window.open(c.url, '_blank', 'noopener');
}
{
  const stack = $('#stack'), touch = matchMedia('(hover: none)');
  const pick = e => { const a = e.target.closest('.sys-nd'); if (a) sysShow(a.dataset.key); };
  stack.addEventListener('mouseover', pick); stack.addEventListener('focusin', pick);
  // 누르면 그 도구가 새 탭으로 열린다. 손가락으로 쓰는 화면에서는 첫 누름이 고르기다(올려 보기가 없다) — 여는 것은 정보 띠의 [열기]
  const open = (e, key, direct) => {
    const c = sysComps().find(x => x.key === key); if (!c) return;
    if (!c.url || (!direct && touch.matches)) { e.preventDefault(); sysShow(key); return; }
    if (optionalOf(c)) { e.preventDefault(); openOptional(c); }
  };
  let dragged = false;
  stack.addEventListener('click', e => { if (dragged) { e.preventDefault(); dragged = false; return; } const a = e.target.closest('.sys-nd'); if (a) open(e, a.dataset.key, false); });
  $('#sysInfo').addEventListener('click', e => { const a = e.target.closest('[data-sys-open]'); if (a) open(e, a.dataset.sysOpen, true); });
  /* 좁은 폭: 그림이 캔버스보다 넓으면(최소 980px) 끌어서 옮긴다. 그 사실을 범례 아래 한 줄(#sysPan)로 알리고, 영역 단추 셋으로 그 영역을 바로 가운데에 놓는다.
     지금 가운데에 보이는 영역의 단추가 눌린 모양이다. 넓은 폭에서는 이 줄이 없다 */
  const pan = $('#sysPan'), bands = Object.entries(SYS.band);
  const scale = () => stack.scrollWidth / SYS.W;
  const paintPan = () => {
    const on = stack.scrollWidth > stack.clientWidth + 2;
    pan.toggleAttribute('data-on', on); stack.toggleAttribute('data-pan', on);
    if (!on) return;
    const mid = (stack.scrollLeft + stack.clientWidth / 2) / scale();
    const now = (bands.find(([, [x, w]]) => mid >= x && mid <= x + w) || bands.reduce((a, b) => Math.abs(b[1][0] + b[1][1] / 2 - mid) < Math.abs(a[1][0] + a[1][1] / 2 - mid) ? b : a))[0];
    pan.querySelectorAll('button[data-band]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.band === now)));
  };
  pan.addEventListener('click', e => {
    const b = e.target.closest('button[data-band]'); if (!b) return;
    const [x, w] = SYS.band[b.dataset.band];
    stack.scrollTo({ left: Math.max(0, (x + w / 2) * scale() - stack.clientWidth / 2), behavior: 'smooth' });
  });
  stack.addEventListener('scroll', paintPan, { passive: true });
  new ResizeObserver(() => { paintPan(); sysPlace(); }).observe(stack);
  let from = null;
  stack.addEventListener('pointerdown', e => { if (e.pointerType === 'mouse' && e.button === 0 && stack.hasAttribute('data-pan')) from = { x: e.clientX, left: stack.scrollLeft }; });
  window.addEventListener('pointermove', e => { if (!from) return; const dx = e.clientX - from.x; if (Math.abs(dx) > 4) { dragged = true; stack.classList.add('dragging'); } stack.scrollLeft = from.left - dx; });
  window.addEventListener('pointerup', () => { if (from) { from = null; stack.classList.remove('dragging'); setTimeout(() => { dragged = false; }, 0); } });
}
async function pollHealth() {
  if (pollHealth.busy) return; pollHealth.busy = true;
  const dots = $('#healthDots');
  try {
    const said = {};      // 우리 서비스의 /healthz 가 말한 것(503 이어도 본문은 읽는다) — 여는 화면이 없는 부품(MQTT 브로커 둘 · 공장 쪽 브리지)의 상태를 여기서 읽는다(layers.js healthOf)
    await Promise.all(LAYERS.flatMap(L => L.comps).filter(c => c.health && !c.optional && !c.healthOf).map(async c => {
      const key = c.health;
      const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 4000);
      try {
        if (c.health.endsWith('/healthz')) {            // 우리 서비스: 같은 출처의 /healthz 가 JSON 으로 답한다
          const r = await fetch(c.health, { cache: 'no-store', signal: controller.signal }); healthState[key] = r.ok ? 'up' : 'down';
          said[key] = await r.json().catch(() => null);
        } else {                                         // 바깥 도구: 그 포트에 닿는지만 본다
          await fetch(c.health, { mode: 'no-cors', cache: 'no-store', signal: controller.signal }); healthState[key] = 'up';
        }
      } catch (e) { healthState[key] = 'down'; }
      finally { clearTimeout(timer); }
    }));
    // 브로커 둘 · 공장 쪽 브리지: 붙어 있는 서비스 가운데 하나라도 「이어져 있다」고 하면 정상, 그런 서비스 없이 「끊겼다」는 서비스가 있으면 응답 없음.
    // 아무도 모르면(답한 서비스가 없거나, 답한 서비스가 그 부품을 볼 자리에 없다) 「확인 중」으로 둔다 — 그 서비스들이 응답 없음으로 따로 보인다
    LAYERS.flatMap(L => L.comps).filter(c => c.healthOf).forEach(c => {
      const heard = c.healthOf.from.map(u => said[u]).filter(h => h && typeof h === 'object').map(c.healthOf.read);
      healthState[c.health] = heard.includes(true) ? 'up' : heard.includes(false) ? 'down' : undefined;
    });
    // 감지기가 감지에서 뺀 이상 패턴(/healthz 의 patterns.rejected — 조건식이 틀린 패턴은 그것만 빠지고 감지기는 정상으로 답한다). 서비스 점이 초록인 채
    // 조용히 감지되지 않는 일이 없게 메뉴 줄 · 시스템 구성 머리 · 이상 탐지 부품의 정보 띠 · 결함 시뮬레이션에 그 사실과 까닭을 보인다
    const det = said[API.detector + '/healthz'];
    if (det) state.leftOut = requireListOr(det.patterns && det.patterns.rejected);
    paintHealth(); paintLeftOut();
    const all = LAYERS.flatMap(L => L.comps).filter(c => c.health && !c.optional);
    const down = all.filter(c => healthState[c.health] === 'down');
    // 메뉴 줄 맨 아래 한 줄: 「서비스 14/14」 또는 「서비스 11/14 · 3개 응답 없음」(뒤에 refreshFast 가 「· 20배속」을 붙인다). 점은 모두 응답하면 초록(살아 있는 점),
    // 일부가 없으면 주황, 모두 없으면 빨강. 어느 서비스인지는 title 과 시스템 구성 화면(누르면 열린다)이 말한다. 접은 메뉴 줄에서는 점만 보이고 같은 글이 툴팁으로 나온다
    const up = all.length - down.length, status = $('#railStatus'), dot = $('#healthDot');
    const out = (state.leftOut || []).length;
    // 조각(.rail-bit — 서비스 수 · 응답 없음 또는 빠진 패턴 · 배속)은 저마다 한 덩어리이고, 한 줄에 다 들어가지 않으면 조각 단위로 다음 줄로 넘어간다(portal-kit.css — 글을 말줄임으로 자르지 않는다)
    const more = down.length ? `${down.length}개 ${esc(UI.t('header.noResponse'))}` : out ? `감지에서 빠진 패턴 ${out}` : '';
    dots.innerHTML = `<span class="rail-bit">${esc(UI.t('header.services'))} <b class="num">${up}/${all.length}</b></span>${more ? `<span class="rail-bit"><span class="sep"> · </span>${more}</span>` : ''}`;
    dot.dataset.tone = !down.length ? (out ? 'warn' : 'ok') : up ? 'warn' : 'danger';
    dot.toggleAttribute('data-live', !down.length && !out);
    status.toggleAttribute('data-down', down.length > 0);
    status.dataset.tooltip = dots.textContent;
    status.title = (down.length ? `${UI.t('header.noResponse')}: ${down.map(c => c.name.split(' ')[0]).join(', ')}. ` : '') + '서비스 응답 확인입니다. 전체 파이프라인의 성공을 뜻하지 않습니다. 누르면 시스템 구성을 엽니다.';
  } finally { pollHealth.busy = false; }
}

/* ---------------- 관리: 보기 탭(내 설정 · 접수 기록)이 판(details)의 열림을 바꾼다 — 딸린 모듈은 자기 판이 열릴 때(toggle) 읽는다 ---------------- */
{
  const list = $('#adminList');
  const pick = id => {
    UI.markViewTab(list, b => b.dataset.admin === id);
    document.querySelectorAll('.admin-pane').forEach(d => { d.open = d.id === id; });
  };
  list.addEventListener('click', e => { const b = e.target.closest('[data-admin]'); if (b) pick(b.dataset.admin); });
  pick('configBundlePanel');
}

/* ---------------- 설비 한 기의 상태 낱말과 유온 기준 — 결함 시뮬레이션 · 실시간 모니터링 · 설비 회로 · 홈(main.js)이 함께 쓴다 ---------------- */
const FAULT_LABEL = { cooler_degradation: '쿨러 성능 저하', pump_leakage: '펌프 내부 누설', fan_vibration: '팬 베어링 마모', restore: '복구' };
// 감지기 패턴(쿨러 · 펌프 · 팬 …) 중 가장 급한 단계 — 설비 카드는 쿨러 하나가 아니라 모든 패턴을 본다
const PHASE_ORDER = ['RAISED', 'CLEARING', 'CANDIDATE', 'IDLE'];
function worstPhase(d) { const all = Object.values(d.patterns || {}).map(p => p.phase).filter(Boolean); return PHASE_ORDER.find(x => all.includes(x)) || 'IDLE'; }
// 「경보」 한 줄: 조용하면 「감시 중」, 아니면 조용하지 않은 감지기 패턴마다 단계 · 이름. 감지기를 못 읽었으면 「감시 중」(정상)으로 보이지 않는다
function phaseText(d) {
  if (!state.det) return state.detError ? `감지기 응답 없음 — ${state.detError}` : '감지기 확인 중';
  const busy = Object.entries(d.patterns || {}).filter(([, p]) => p.phase && p.phase !== 'IDLE');
  return busy.length ? busy.map(([code, p]) => `${UI.status(p.phase)} · ${UI.patternName(code)}`).join(' / ') : UI.status('IDLE');
}
// 유온 기준 한 곳: 경보 조건 55 ℃(감지기) · 보호 정지 65 ℃ — 눈금 막대 · 회로 그림 · 추이의 기준선 · 홈(main.js)이 같이 쓴다. 눈금 막대는 30~70 ℃
const TS_HOT = 55, TS_TRIP = 65, TS_MIN = 30, TS_MAX = 70;
const tsPct = t => Math.max(0, Math.min(100, (t - TS_MIN) / (TS_MAX - TS_MIN) * 100));
function tsColor(t) { return t >= TS_TRIP ? 'trip' : t >= TS_HOT ? 'hot' : ''; }
// 설비 한 기의 상태 낱말 하나: 보호 정지 → 경보(감지기의 가장 급한 단계) → 운전 상태 차례로 급한 것을 보인다. 감지기를 못 읽었으면 그 사실을 보인다.
// tone 은 상태 알약(UI.chipText)의 색 이름이다. 경보 쪽 단계(이상 징후 · 경보 발생 · 해제 확인)는 주의(주황), 실패색(빨강)은 보호 정지와 감지기 응답 없음뿐이다
function unitState(s, d) {
  if (s.state === 'TRIP') return { label: UI.status('TRIP'), tone: 'danger' };
  if (!state.det) return { label: state.detError ? '감지기 응답 없음' : '감지기 확인 중', tone: state.detError ? 'danger' : 'neutral' };
  if (worstPhase(d) !== 'IDLE') return { label: UI.status(worstPhase(d)), tone: 'warning' };
  return { label: UI.status(s.state), tone: UI.toneOf(s.state) };
}
const KIT_TONE = { accent: 'run', success: 'ok', warning: 'warn', danger: 'danger' };      // 알약의 색 이름 → 점 · 회로 카드 · 카드 테의 data-tone
const detOf = asset => (state.det && state.det.assets && state.det.assets[asset]) || {};
// 카드 머리 줄의 상태 알약(이름 바로 뒤 — 디자인기준 4-5)과 카드 테(경보 · 보호 정지일 때만 색). 같은 알약이면 다시 그리지 않는다
function paintState(card, st) {
  const tag = UI.chipText(st.label, st.tone), box = card.querySelector('[data-f="state"]');
  if (box._markup !== tag) { box.innerHTML = tag; box._markup = tag; }
  const alert = KIT_TONE[st.tone];
  if (alert === 'danger' || alert === 'warn') card.dataset.alert = alert; else delete card.dataset.alert;
}
/* 실시간 모니터링의 설비 카드(디자인기준 5-7): 설비의 지금 값이 크게 보이는 곳은 이 화면 하나다(1-2).
   머리 줄(이름 · 상태 알약 · 운전 모드) → 큰 유온과 작은 추이 선 → 눈금 막대(경보 · 정지 자리부터 주황 · 빨강, 지금 값에 핀) → 작은 값 여섯.
   카드 전체가 그 설비의 추이를 고르는 단추이고, 그 설비에 열린 처리 건이 있을 때만 아래 고정 줄에 「처리 건에서 보기」가 나타난다 */
const VALUE_CELLS = { PS1: ['plant.ps1', 'bar', 1], FS1: ['plant.fs1', 'L/min', 2], VS1: ['plant.vs1', 'mm/s', 2], CE: ['plant.ce', '%', 0], FanSpeedSP: ['plant.fan', '%', 0], LoadSP: ['plant.load', '%', 0] };
function monCardHtml(asset) {
  return `<article class="card unit" data-asset="${esc(asset)}"><button type="button" class="unit-pick" aria-pressed="false">
    <div class="unit-head"><b>${esc(asset)}</b><span data-f="state"></span><span class="muted" data-f="mode"></span></div>
    <div class="unit-main"><div><div class="unit-cap">${esc(UI.t('plant.ts1'))}</div><div class="unit-big num"><span data-f="TS1">–</span><small>℃</small></div></div><div class="unit-spark" data-f="spark"></div></div>
    <div class="gauge" role="img" data-f="gauge" style="--hot:${tsPct(TS_HOT)}%;--trip:${tsPct(TS_TRIP)}%"><i data-f="pin"></i></div>
    <div class="gauge-scale" aria-hidden="true" style="--hot:${tsPct(TS_HOT)}%;--trip:${tsPct(TS_TRIP)}%"><span>${TS_MIN}</span><span>경보 ${TS_HOT}</span><span>정지 ${TS_TRIP}</span><span>${TS_MAX}</span></div>
    <dl class="unit-grid">${Object.entries(VALUE_CELLS).map(([k, [term, unit]]) => `<div><dt>${esc(UI.t(term))}</dt><dd class="num"><span data-f="${k}">–</span><small>${unit}</small></dd></div>`).join('')}</dl>
  </button><footer hidden>${UI.goLink('instances', '처리 건에서 보기')}</footer></article>`;
}
function paintMonCard(card, asset, u) {
  const t = u.tags, s = u.status;
  const set = (f, text) => { const n = card.querySelector(`[data-f="${f}"]`); if (n && n.textContent !== text) n.textContent = text; };
  paintState(card, unitState(s, detOf(asset)));
  set('mode', UI.status(s.mode)); set('TS1', fmt(t.TS1, 1));
  Object.entries(VALUE_CELLS).forEach(([k, [, , digits]]) => set(k, fmt(t[k], digits)));
  card.querySelector('[data-f="pin"]').style.left = tsPct(t.TS1) + '%';
  card.querySelector('[data-f="gauge"]').setAttribute('aria-label', `유온 ${fmt(t.TS1, 1)} ℃ — 경보 조건 ${TS_HOT} ℃, 보호 정지 ${TS_TRIP} ℃`);
}
function incidentsFor(asset) { return state.incidents.filter(i => i.asset === asset); }
function openIncidentFor(asset) { return incidentsFor(asset).find(i => !i.terminal) || null; }
// 사건의 처리 건을 연다 — 사건의 경과 · 판단 · 승인 · 결과는 처리 건 화면 한 곳에 있다. 못 찾거나 실패하면 까닭을 알린다
async function openIncidentCase(id) {
  try { if (!(await window.hydHitl.openIncident(id))) UI.toast('이 사건의 처리 건을 찾지 못했습니다. 메뉴 「처리 건」의 목록에서 같은 설비의 건을 여세요.', { tone: 'neg' }); }
  catch (e) { UI.toast('처리 건을 열지 못했습니다: ' + e.message, { tone: 'neg' }); }
}
document.addEventListener('click', e => {
  const inc = e.target.closest('[data-open-incident]');
  if (inc) { e.preventDefault(); openIncidentCase(inc.dataset.openIncident); return; }
  const a = e.target.closest('[data-open-inst]'); if (!a) return;
  e.preventDefault(); selectTab('instances'); if (window.hydInstancesSelect) window.hydInstancesSelect(a.dataset.openInst);
});

/* ---------------- 결함 시뮬레이션(디자인기준 5-7 카드 줄) ----------------
   설비 카드 셋. 카드 한 장 = 그 설비에 일으킬 사건 하나이고, 줄의 차례와 수가 세 카드에서 같다:
     머리 줄(이름 · 상태 알약) → 사건 이름 한 줄(업무 사건은 그 표시 알약) → 그 사건이 보는 값 한 줄 → 단추 줄 둘(첫 줄: 일으키기 · 바깥 사건 / 둘째 줄: 되돌리기)
     → 현장 패널 접기(오른쪽 끝에 지금 운전 모드) → 아래 고정 줄(그 설비의 처리 건이 있을 때만 「처리 건에서 보기」).
   그 카드에 없는 단추(HYD-01 · HYD-02 의 바깥 사건)는 그 자리를 비워 둔다 — 같은 종류의 단추가 카드마다 같은 줄 · 같은 차례에 선다.
   설비의 큰 값(유온 · 눈금 막대 · 냉각 효율 · 팬 · 부하)은 여기에 두지 않는다 — 실시간 모니터링 한 곳에 있다(1-2).
   HYD-01 은 설비 결함(쿨러 열화 — 유온이 올라 감지기가 경보를 낸다), 나머지는 업무 사건(서버의 GET /api/scenario/status 가 말하는 설비 · 이름 · 단추 — 정기 점검 도래 · 재고 보충 필요).
   업무 사건은 설비까지 가지 않고 단추가 처리 건을 바로 연다(POST /api/scenario/{key}/start). 되돌리기는 그 사건이 바꾼 것을 처음 값으로 돌린다(쿨러 성능 · 업무 데이터).
   주입 뒤 경보 · 처리 건까지의 과정은 hydLive.follow 로 한 줄씩 보인다(실제 사건이 올 때만 넘어간다). */
const FAULT_UNIT = { asset: 'HYD-01', pattern: 'COOLER_DEGRADATION', fault: 'cooler_degradation' };      // 설비 결함 주입은 쿨러 열화 하나다(서버 POST /api/scenario/A/degrade · restore)
function bizOf(asset) {
  const all = state.biz && state.biz.scenarios ? Object.values(state.biz.scenarios) : [];
  return all.find(b => b.asset === asset) || null;
}
// 업무 사건의 표시 알약(사건 이름 바로 뒤): 읽는 중 · 상태를 못 읽음(사유) · 처리 중 · 도래/필요 · 업무 시스템 응답 없음 — 못 읽은 것을 「표시 없음」으로 보이지 않는다.
// 알약은 그 사건의 지금 표시(업무 데이터의 도래 · 필요 — 바로 아래 값 한 줄과 같은 사실)와 진행 중인 처리 건이 있는지만 말한다. 끝난 처리 건의 결과(반려 · 정상 · 미달)는 여기에 두지 않는다 —
// 사건 한 건의 결과는 처리 건 화면 한 곳에 있고, 반려된 뒤에도 표시가 켜져 있으면 알약은 그 표시(「정기 점검 도래」 · 「재고 보충 필요」)다(값 줄 옆의 「반려」는 「반려돼서 재고가 그대로」로 읽혔다).
// 표시가 꺼졌고 진행 중인 건도 없으면 알약이 없다(값 한 줄이 「보충할 수량 없음」처럼 그 사실을 말한다). 그 처리 건으로 가는 길은 카드 아래 고정 줄 「처리 건에서 보기」 하나다(알약을 링크로 쓰지 않는다)
function bizAlertHtml(asset) {
  const pill = (label, tone, why = '') => why ? `<span title="${esc(why)}">${UI.chipText(label, tone)}</span>` : UI.chipText(label, tone);
  if (asset === FAULT_UNIT.asset) return '';
  if (state.biz === undefined) return pill('확인 중');
  if (state.biz && state.biz.failed) return pill('표시를 읽지 못함', 'danger', state.biz.failed);
  const b = bizOf(asset); if (!b) return '';
  if (b.running) return pill('처리 중', 'accent');
  if (b.alert) return pill(b.label, 'warning');
  return b.error ? pill('업무 시스템 응답 없음', 'neutral', b.error) : '';
}
// 설비마다 마지막으로 누른 단추(서버의 감사 기록 — 처리 건이 없는 [초기화]도 남는다). 화면 아래 「조작 기록」 접기 안에 보인다
function pressLines() {
  const presses = (state.biz && state.biz.presses) || {};
  return Object.entries(presses).filter(([, p]) => p).map(([asset, p]) => `<div class="line biz-press" data-asset="${esc(asset)}">${UI.icon('history')}<span class="line-text">${esc(asset)} [${esc(p.button)}]${p.by ? ` · ${esc(p.by)}` : ''}</span><time class="line-time num">${esc(UI.time(p.at))}</time></div>`).join('');
}
// 업무 사건이 보는 값 한 줄: 그 사건이 왜 생기는지의 사실이다(처리 건의 시작 근거와 같은 값)
function bizFactLine(b) {
  const f = b.facts || {};
  if (b.pattern === 'PM_DUE') return `운전 시간 ${fmt(f.pm_since_h, 0)} h / 정비 주기 ${fmt(f.pm_interval_h, 0)} h — 기한까지 ${fmt(f.pm_due_in_h, 0)} h`;
  // 재고: 가용(보유 − 예약 + 발주 중)이 재주문점 아래일 때만 「<」와 필요 수량을 말한다. 기준 이상이면(발주가 열린 뒤 · 입고 뒤) 그 사실과 발주 중 수량을 말한다
  const part = f.name || f.part_no || '', n = x => fmt(x, 0);
  if (f.available == null || f.reorder_point == null) return `${part} 재고 값을 읽지 못했습니다`;
  if (f.available < f.reorder_point) return `${part} 가용 ${n(f.available)}개 < 재주문점 ${n(f.reorder_point)}개 — 필요 수량 ${n(f.need_qty)}개`;
  return `${part} 가용 ${n(f.available)}개 ≥ 재주문점 ${n(f.reorder_point)}개 — 보충할 수량 없음${f.on_order > 0 ? ` (발주 중 ${n(f.on_order)}개 포함)` : ''}`;
}
/* 카드의 단추. 무엇을 하는 단추인지는 도움말이, 누른 뒤의 일은 과정 판이 말한다. 카드의 단추 도움말(사건 절 · 현장 패널 안 모두)은 뜨는 조각이 아니라 카드 본문 맨 아래의 제자리 줄(.lab-hint — 카드마다 하나)에 나온다 —
   뜨는 조각은 위에 뜨면 사건 이름 · 값 줄을, 아래에 뜨면 「현장 패널」 줄을, 현장 패널 안에서는 옆 단추를 덮는다(사용자가 곧 누를 자리다). 올리거나 초점을 주면 그 줄에 글이 나오고 떠나면 비운다(labHint).
   그 줄은 단추 줄과 「현장 패널」 사이가 아니라 카드 본문의 맨 아래에 있다 — 두 줄 높이를 늘 지키지만 카드 가운데에 빈 띠를 만들지 않는다.
   일으키기는 카드의 주 단추(단추 줄 첫 자리 — 4-1), 바깥 사건과 되돌리기는 보통 단추다.
   지금 누를 수 없는 단추는 흐리게 두고 도움말과 누른 뒤의 한 줄이 까닭을 말한다(눌러서 아무 일도 없는 단추를 두지 않는다):
   같은 업무 사건의 처리 건이 진행 중이면 새로 시작할 수 없다(서버는 409), 그 사건의 표시가 꺼져 있으면(이미 처리됨 — 서버는 409) 시작할 사건이 없다, 바깥 사건은 서버가 준 까닭(scenarios.<키>.events[].why) */
const BIZ_RUNNING = '진행 중인 처리 건이 있어 새로 시작할 수 없습니다. 카드 아래 「처리 건에서 보기」로 그 건을 끝낸 뒤 시작하세요.';
// 업무 사건 [시작]을 지금 누를 수 없는 까닭(누를 수 있으면 빈 글). 서버가 준 상태 값만 본다: 진행 중인 처리 건(running) → 표시가 꺼짐(alert 가 false — 서버의 거절 문장과 같은 사실).
// 업무 시스템을 못 읽어 표시를 모를 때(alert 가 null · error)는 끄지 않는다 — 모르는 것을 「이미 처리됨」으로 말하지 않고, 누르면 서버가 까닭을 말한다
function bizStartOff(b) {
  if (b.running) return BIZ_RUNNING;
  if (b.alert === false) return `「${b.label}」 표시가 꺼져 있습니다(이번 사건은 이미 처리됐습니다). 다시 하려면 [${state.biz.reset_button}]를 누르세요.`;      // 카드의 도움말 줄(두 줄)에 들어가는 길이다
  return '';
}
const labBtn = (act, label, { primary = false, icon = '', tip = '', off = false, attrs = '', cls = '' } = {}) =>
  `<button type="button" class="btn${cls ? ' ' + cls : ''}"${primary ? '' : ' data-variant="outline"'} data-size="sm" data-act="${act}"${attrs ? ' ' + attrs : ''}${off ? ' aria-disabled="true"' : ''}${tip ? ` data-tooltip="${esc(tip)}" data-side="bottom" data-align="start"` : ''}>${icon ? UI.icon(icon) : ''}<span>${esc(label)}</span></button>`;
const LAB_SLOT = '<span class="btn lab-slot" data-variant="outline" data-size="sm" aria-hidden="true">&nbsp;</span>';      // 그 카드에 없는 단추의 빈 자리(단추와 같은 상자 — 보이지 않는다)
const eventBtn = ev => labBtn('biz-event', ev.button, { icon: 'clock', off: !ev.enabled, attrs: `data-event="${esc(ev.act)}"`, tip: ev.enabled ? ev.help || '' : ev.why || '지금은 누를 수 없습니다' });
{
  const units = $('#units'), hintOf = e => { const b = e.target.closest && e.target.closest('.unit [data-tooltip]'); return b ? [b, b.closest('.unit').querySelector('.lab-hint')] : []; };
  const labHint = on => e => { const [b, box] = hintOf(e); if (box) box.textContent = on ? b.dataset.tooltip : ''; };
  units.addEventListener('mouseover', labHint(true)); units.addEventListener('focusin', labHint(true));
  units.addEventListener('mouseout', labHint(false)); units.addEventListener('focusout', labHint(false));
}
function expHtml(asset) {
  const what = (text, pill = false) => `<p class="lab-what"><span>${esc(text)}</span>${pill ? '<span class="biz-alert"></span>' : ''}</p>`;
  if (asset === FAULT_UNIT.asset) return what(`설비 결함 · ${UI.patternName(FAULT_UNIT.pattern)}`) + `<p class="lab-fact" data-f="fact"></p>
    <div class="lab-buttons">${labBtn('degrade', '쿨러 열화 주입', { primary: true, icon: 'zap', tip: '쿨러 성능을 서서히 떨어뜨립니다. 유온이 오르면 경보가 납니다' })}${LAB_SLOT}${labBtn('restore', '쿨러 복구', { icon: UI.acts.repair[1], tip: '쿨러 성능을 처음 값으로 되돌립니다', cls: 'lab-undo' })}</div>`;
  if (state.biz === undefined) return what('업무 사건') + '<div class="skeleton" style="height:96px"></div>';
  if (state.biz && state.biz.failed) return what('업무 사건', true) + `<p class="lab-fact" data-tone="danger">업무 사건의 상태를 읽지 못했습니다: ${esc(state.biz.failed)} — 잠시 뒤 다시 읽습니다.</p>`;
  const b = bizOf(asset);
  if (!b) return what('업무 사건') + '<p class="lab-fact">이 설비에 걸린 업무 사건이 없습니다.</p>';
  const events = b.events || [];
  return what(`업무 사건 · ${b.title}`, true) + `<p class="lab-fact" title="${esc(bizFactLine(b))}">${esc(bizFactLine(b))}</p>
    <div class="lab-buttons">${labBtn('biz-start', b.button, { primary: true, icon: 'play', off: !!bizStartOff(b), tip: bizStartOff(b) || '설비를 거치지 않고 처리 건이 바로 열립니다' })}${events.length ? events.map(eventBtn).join('') : LAB_SLOT}${labBtn('biz-reset', state.biz.reset_button, { icon: 'rotate-ccw', tip: '업무 데이터를 처음 값으로 되돌립니다', cls: 'lab-undo' })}</div>`;
}
function labCardHtml(asset) {
  const manual = (act, label, tip = '') => labBtn(act, label, { tip });
  return UI.card({ cls: 'unit', attrs: `data-asset="${esc(asset)}" role="group" aria-label="${esc(asset)} 설비"`, title: esc(asset), chips: '<span data-f="state"></span>',
    body: `<div class="lab-exp"></div>
      <details class="fold lab-field"><summary>현장 패널<span class="muted" data-f="mode"></span></summary><div class="fold-body lab-panel">
        <div role="group" class="field"><label for="mode-${esc(asset)}">${esc(UI.t('plant.modes'))}</label><select class="select" id="mode-${esc(asset)}" data-mode-pick><option value="REMOTE_AUTO">원격 자동 — 승인된 원격 명령을 받음</option><option value="REMOTE_MANUAL">원격 수동</option><option value="LOCAL">현장 제어</option></select></div>
        <div class="lab-manual" role="group" aria-label="수동 조작">${manual('fan', '팬 80 %', '적용하면 원격 수동으로 바뀝니다')}${manual('load', '부하 70 %', '적용하면 원격 수동으로 바뀝니다')}${manual('reset', '보호 정지 해제')}</div>
        <dl class="kv"><dt>${esc(UI.t('plant.state'))}</dt><dd class="plc"></dd><dt>${esc(UI.t('plant.lastCmd'))}</dt><dd class="ack"></dd></dl>
      </div></details><p class="lab-hint" aria-hidden="true"></p>`,
    foot: UI.goLink('instances', '처리 건에서 보기') });
}
function renderUnits() {
  const box = $('#units');
  // 아직 한 번도 읽지 못한 것(읽는 중)과 읽기 실패를 가른다 — 처음 여는 순간을 「읽지 못했습니다」로 보이지 않는다
  if (!state.plant && !state.plantError) { box.innerHTML = '<div class="skeleton" style="height:280px"></div>'.repeat(3); return; }
  if (!state.plant) { box.innerHTML = UI.errorBlock(UI.t('plant.noConn'), `${state.plantError || ''} ${UI.t('plant.noConnSub')}`.trim()); return; }
  if (!box.querySelector('.unit')) box.innerHTML = '';
  for (const [asset, u] of Object.entries(state.plant.units)) {
    let card = box.querySelector(`[data-asset="${asset}"]`);
    if (!card) {
      box.insertAdjacentHTML('beforeend', labCardHtml(asset)); card = box.lastElementChild;
      card.querySelector(':scope > footer').hidden = true;
      card.querySelector('[data-mode-pick]').addEventListener('change', e => unitAction(asset, 'mode', e.target.value, null));
      card.addEventListener('click', e => { const b = e.target.closest('button[data-act]'); if (b) unitAction(asset, b.dataset.act, b.dataset.mode, b); });
    }
    const s = u.status, d = detOf(asset), own = asset === FAULT_UNIT.asset, b = bizOf(asset);
    paintState(card, unitState(s, d));
    const mode = card.querySelector('[data-f="mode"]'), modeText = UI.status(s.mode);
    if (mode.textContent !== modeText) mode.textContent = modeText;
    mode.title = s.mode === 'REMOTE_AUTO' ? '원격 자동 — 승인된 원격 명령을 설비가 받는 운전 모드입니다. 저절로 조치하지 않으며, 명령은 사람이 승인한 뒤에만 나갑니다.' : '';
    // 사건 절(이름 · 값 한 줄 · 단추)은 내용이 바뀔 때만 다시 그린다(누르는 동안 단추가 바뀌지 않게). 알약 · 값 · 안내 줄은 그 아래에서 따로 맞춘다
    const exp = card.querySelector('.lab-exp');
    const expSig = own ? UI.patternName(FAULT_UNIT.pattern) : JSON.stringify([state.biz === undefined, state.biz && state.biz.failed, b && [b.title, b.button, bizFactLine(b), bizStartOff(b), (b.events || []).map(ev => [ev.act, ev.button, ev.enabled, ev.why])]]);
    if (exp._sig !== expSig) {
      exp._sig = expSig;
      exp.innerHTML = expHtml(asset) + '<p class="lab-note fault"></p><p class="lab-note repeat-guide" role="status"></p>';
    }
    const bizAlert = card.querySelector('.biz-alert'), bizMarkup = bizAlertHtml(asset);
    if (bizAlert && bizAlert._markup !== bizMarkup) { bizAlert.innerHTML = bizMarkup; bizAlert._markup = bizMarkup; }
    const dz = u.disturbances || {};
    // 지금 걸려 있는 그 밖의 결함 한 줄(없으면 줄도 없다). 쿨러 성능은 결함 설비 카드의 값 한 줄이 이미 말하므로 거기서는 되풀이하지 않는다
    const active = [!own && dz.cooler_health != null && dz.cooler_health < 0.999 ? `쿨러 성능 ${fmt(dz.cooler_health * 100, 0)} %` : '', dz.leak > 0 ? `펌프 A 누설 ${fmt(dz.leak * 100, 0)} %` : '', dz.bearing_wear > 0 ? `팬 베어링 마모 ${fmt(dz.bearing_wear * 100, 0)} %` : ''].filter(Boolean);
    const ramps = (u.faults || []).filter(k => !(own && k === FAULT_UNIT.fault)).map(k => FAULT_LABEL[k] || k);
    card.querySelector('.fault').textContent = (ramps.length ? `${UI.t('plant.faultOn')}: ${ramps.join(', ')}` : '') + (active.length ? `${ramps.length ? ' · ' : ''}${active.join(' · ')}` : '');
    // 아래 고정 줄: 그 설비에 진행 중인 처리 건이 있을 때만 나타난다(경과 · 승인 · 결과는 처리 건에서 — 이 카드는 끝난 건의 결과를 따로 보이지 않는다).
    // 설비 결함 카드는 열린 사건의 처리 건으로, 업무 사건 카드는 진행 중인 처리 건으로
    const openInc = openIncidentFor(asset), foot = card.querySelector(':scope > footer'), go = foot.querySelector('.go');
    const bizCase = !own && b ? b.running : null;
    foot.hidden = own ? !openInc : !bizCase;
    if (own && openInc) go.dataset.openIncident = openInc.id; else delete go.dataset.openIncident;
    if (bizCase) go.dataset.openInst = bizCase.instance; else delete go.dataset.openInst;
    if (own) {
      const pat = d.patterns?.[FAULT_UNIT.pattern], phase = pat?.phase, ramping = (u.faults || []).includes(FAULT_UNIT.fault);
      // 값 한 줄: 이 결함이 바꾸는 값(쿨러 성능)과 그 값이 올리는 유온의 지금 값 — 업무 사건 카드의 근거 한 줄과 같은 자리. 감지기의 단계는 머리 줄의 상태 알약이 말한다
      const fact = card.querySelector('[data-f="fact"]'), text = `유온 ${fmt(u.tags.TS1, 1)} ℃ · 쿨러 성능 ${fmt(s.cooler_health * 100, 0)} %${ramping ? ' · 떨어지는 중' : ''}`;
      if (fact.textContent !== text) fact.textContent = text;
      if (s.cooler_health < 0.999) fact.dataset.tone = 'warn'; else delete fact.dataset.tone;
      const handled = !!pat?.alert_id && state.incidents.some(i => i.alertId === pat.alert_id);      // 이 경보의 사건이 이미 있으면(끝난 것 포함) 이어 보일 과정이 없다
      // 안내는 그 상황일 때만 한 줄: 감지기를 못 읽었을 때, 그리고 결함이 걸린 채 새 경보가 나지 않는 때(경보의 처리 건이 이미 끝났거나, 결함은 남았는데 감지기가 조용할 때)
      const stuck = s.cooler_health < 0.999 && !openInc && state.incidentsRead && (phase === 'IDLE' || (phase === 'RAISED' && handled)) && !ramping;
      card.querySelector('.repeat-guide').textContent = !phase ? '감지기 상태를 읽지 못했습니다.' : stuck ? '다시 하려면 [쿨러 복구]를 누르고, 위 상태가 「운전 중」으로 돌아온 뒤 주입하세요.' : '';
      // 화면을 다시 열었는데 결함이 진행 중이면 그 과정을 이어서 보인다(한 번만 — 닫았으면 다시 열지 않는다)
      if (!labFollow && !renderUnits.resumed && state.incidentsRead && !handled && (ramping || ['CANDIDATE', 'RAISED'].includes(phase))) { renderUnits.resumed = true; followFault(true); }
    }
    card.querySelector('.plc').textContent = UI.status(s.state) + (s.trip_text && s.trip_text !== '–' ? ' · ' + s.trip_text : '');
    card.querySelector('.ack').textContent = s.cmdId ? UI.status(s.result) + (s.reason ? ' · ' + s.reason : '') : UI.t('plant.none');
    card.querySelector('.ack').title = s.cmdId ? `${s.cmdId}${s.reason ? ' · ' + s.reason : ''}` : '';
    const pickMode = card.querySelector('[data-mode-pick]'); if (document.activeElement !== pickMode && pickMode.value !== s.mode) pickMode.value = s.mode;
  }
}
/* 주입 뒤의 과정(디자인기준 7절): 결함 주입 → 유온이 오름 → 감지기가 조건을 잡음 → 경보 → 처리 건 열림. 줄마다 그 사실이 실제로 일어났는지를 1초마다 확인하고,
   일어난 것만 채운다(시간으로 넘기지 않는다). 사실은 이 파일이 이미 읽는 것(설비 상태 · 감지기 상태 · 사건 목록 · 업무 사건 상태)에서 본다. */
let labFollow = null;
// resumed: 화면을 다시 열어 이미 진행 중인 과정을 이어 보이는 것. 이미 지난 줄은 언제 일어났는지 이 화면이 모른다 —
// 그 줄들에는 걸린 시간을 적지 않는다(첫 확인에서 곧바로 채워진 줄 수만큼 시간 칸을 감춘다). 그 뒤 지켜본 줄에는 실제로 걸린 시간이 남는다
function showFollow(title, stages, resumed = false) {
  if (labFollow) labFollow.stop();
  $('#labFollowPanel').hidden = false; $('#labFollowTitle').textContent = title;
  const note = $('#labFollowNote'); note.hidden = !resumed;      // 이어 보일 때만 한 줄 — 처음부터 지켜보는 과정에는 설명이 필요 없다
  note.textContent = resumed ? '이 화면을 열기 전에 시작된 과정을 이어서 보입니다.' : '';
  const host = el('div'), past = el('style'); $('#labFollow').replaceChildren(past, host);
  labFollow = hydLive.follow(host, stages, { label: title });
  if (resumed) setTimeout(() => {
    const n = host.querySelectorAll('.lv-step.ok').length;
    if (n) past.textContent = `#labFollow .lv-step:nth-child(-n+${n}) .lv-time { display: none; }`;
  }, 1500);
}
$('#gwLog').closest('details').addEventListener('toggle', () => refreshFast());      // 조작 기록을 펴면 명령 관문의 기록을 곧바로 읽어 그린다
$('#labFollowClose').addEventListener('click', () => { if (labFollow) labFollow.stop(); $('#labFollowPanel').hidden = true; });
function followFault(resumed = false) {
  const { asset, pattern, fault } = FAULT_UNIT;
  const unit = () => state.plant && state.plant.units[asset], pat = () => detOf(asset).patterns?.[pattern];
  showFollow(`${asset} ${UI.patternName(pattern)} — 주입에서 처리 건까지`, [
    { key: 'inject', label: '결함을 넣는 중', hint: '설비 시뮬레이터가 결함을 받았는지 확인합니다.',
      check: () => { const u = unit(); return u && ((u.faults || []).includes(fault) || u.status.cooler_health < 0.999) ? { health: u.status.cooler_health } : null; },
      done: () => '결함이 들어갔습니다 — 쿨러 성능이 떨어지기 시작했습니다', note: f => `쿨러 성능 ${fmt(f.health * 100, 0)} %` },
    { key: 'rise', label: '유온이 오르는 중', hint: `유온이 경보 조건 ${TS_HOT} ℃를 넘을 때까지 기다립니다. 쿨러 성능이 떨어질수록 빨리 오릅니다.`,
      check: () => { const u = unit(); return u && u.tags.TS1 >= TS_HOT ? { ts1: u.tags.TS1, ce: u.tags.CE } : null; },
      now: () => { const u = unit(); return u ? `지금 유온 ${fmt(u.tags.TS1, 1)} ℃ → 경보 조건 ${TS_HOT} ℃ · 쿨러 성능 ${fmt(u.status.cooler_health * 100, 0)} % · 냉각 효율 ${fmt(u.tags.CE, 0)} %` : '설비 값을 읽지 못했습니다'; },
      done: () => `유온이 경보 조건 ${TS_HOT} ℃를 넘었습니다`, note: f => `유온 ${fmt(f.ts1, 1)} ℃ · 냉각 효율 ${fmt(f.ce, 0)} %` },
    { key: 'detect', label: '감지기가 이상 패턴의 조건을 맞춰 보는 중', hint: '유온 · 냉각 효율 · 오르는 기울기가 모두 조건에 들어야 합니다.',
      check: () => { const p = pat(); return p && ['CANDIDATE', 'RAISED'].includes(p.phase) ? { phase: p.phase } : null; },
      now: () => { const u = unit(), p = pat(); return !p ? '감지기 상태를 읽지 못했습니다' : u ? `감지기 ${UI.status(p.phase)} · 지금 유온 ${fmt(u.tags.TS1, 1)} ℃ · 냉각 효율 ${fmt(u.tags.CE, 0)} %` : ''; },
      done: () => '감지기가 이상 패턴을 잡았습니다', note: () => `${UI.patternName(pattern)} · 조건이 이어지는지 지켜봅니다` },
    { key: 'alert', label: '조건이 이어지는지 지켜보는 중', hint: '조건이 정해진 시간 동안 이어져야 경보가 됩니다. 잠깐 스친 값으로는 경보를 내지 않습니다.',
      check: () => { const p = pat(); return p && p.phase === 'RAISED' ? { alert: p.alert_id } : null; },
      now: () => { const u = unit(); return u ? `조건이 이어지는 중 · 지금 유온 ${fmt(u.tags.TS1, 1)} ℃` : ''; },
      done: () => '경보가 났습니다', note: () => UI.patternName(pattern) },
    { key: 'case', label: '처리 건이 열리기를 기다리는 중', hint: '경보가 흐름 엔진에 닿으면 처리 건이 열립니다.',
      check: f => { const inc = incidentsFor(asset).find(i => f && f.alert ? i.alertId === f.alert : i.pattern === pattern && !i.terminal); return inc ? { inc: inc.id, ended: inc.terminal } : null; },      // 이 경보로 열린 사건(이미 끝난 것이면 그렇다고 말한다). 경보 번호를 모르면 이 경보 종류(사건의 pattern)의 열린 사건 — 같은 설비의 다른 경보(정기 정비 · 재고) 사건을 잡지 않는다
      done: f => f.ended ? '이 경보로 열린 처리 건은 이미 끝났습니다' : '처리 건이 열렸습니다',
      note: f => f.ended ? '경보가 아직 꺼지지 않아 새 처리 건이 열리지 않습니다. 새로 해 보려면 [쿨러 복구]를 누르고, 이 설비의 상태가 「운전 중」으로 돌아온 뒤 다시 주입하세요.' : 'AI 에이전트가 원인과 조치 후보를 판단합니다',
      link: f => ({ text: '처리 건에서 보기', go: () => openIncidentCase(f.inc) }) },
  ], resumed);
}
function followBiz(asset, title) {
  showFollow(`${asset} ${title} — 처리 건이 열릴 때까지`, [
    { key: 'case', label: '처리 건을 여는 중', hint: '흐름 엔진이 업무 데이터를 근거로 처리 건을 엽니다.',
      check: () => { const b = bizOf(asset); return b && b.running ? { inst: b.running.instance } : null; },
      done: () => '처리 건이 열렸습니다', note: () => 'AI 에이전트가 판단을 시작합니다',
      link: f => ({ text: '처리 건에서 보기', go: () => { selectTab('instances'); if (window.hydInstancesSelect) window.hydInstancesSelect(f.inst); } }) },
  ]);
}
// 누가 눌렀나: 이 PC의 담당자(로그인 없음 — inbox.js me). 처리 건 기록(SCENARIO_BUTTON)과 시작 경보 근거에 남는다
function pressedBy() {
  const me = window.hydInbox && window.hydInbox.me && window.hydInbox.me();
  return { by: me ? me.name : null, user_id: me ? me.id : null, roles: me ? me.roles : [] };   // 담당자를 못 읽었으면 이름을 지어 보내지 않는다(서버가 400 으로 거절한다)
}
async function refreshBiz() {
  try { state.biz = await getJ(API.process + '/api/scenario/status'); } catch (e) { state.biz = { failed: e.message }; }
}
const anchorNote = r => r && r.reanchored === false ? ' · 업무 데이터의 기준 시각은 그대로 둡니다(진행 중인 처리 건이 있습니다)' : '';
async function unitAction(asset, act, mode, button) {
  const b = bizOf(asset);
  // [초기화]는 그 업무 사건의 업무 데이터를 처음 값으로 되돌린다 — 되돌릴 수 없으므로 먼저 묻는다
  if (act === 'biz-reset' && !await UI.confirm({ title: `${b.title} 업무 데이터를 처음 값으로 되돌릴까요?`, body: `${b.title}의 업무 데이터가 처음 값으로 돌아가 「${b.label}」 표시가 다시 켜집니다. 이미 열린 처리 건은 그대로 남습니다.`, ok: state.biz.reset_button, danger: true })) return;
  if (button) button.disabled = true;
  scenarioMessage(`${asset} 요청을 보내는 중`);
  try {
    if (act === 'degrade') { const r = await postJ(API.process + '/api/scenario/A/degrade', pressedBy()); logLine(`${asset} 쿨러 열화 주입 · ${pressedBy().by} · ${UI.time(r.at)}${anchorNote(r)}`); followFault(); await refreshBiz(); }
    else if (act === 'restore') { const r = await postJ(API.process + '/api/scenario/A/restore', pressedBy()); logLine(`${asset} 쿨러 복구${r.instance ? ' · 열화로 열린 처리 건에 기록했습니다' : ' · 이어진 처리 건이 없어 감사 기록에만 남겼습니다'}`); await refreshBiz(); }
    else if (act === 'biz-start') {
      const off = bizStartOff(b);
      if (off) { logLine(`[${b.button}]을 지금 누를 수 없습니다 — ${off}`, true); return; }
      const r = await postJ(API.process + `/api/scenario/${b.key}/start`, pressedBy());
      followBiz(asset, b.title);
      await refreshBiz();
      if (state.tab === 'scenario') renderUnits();
      logLine(`${asset} ${b.title} 처리 건 시작 · 근거 ${b.pattern === 'PM_DUE' ? `운전 시간 ${r.evidence.hours_since_pm} h` : `가용 ${r.evidence.available} 개`}${anchorNote(r)}`);
    }
    else if (act === 'biz-event') {
      const ev = (b.events || []).find(x => x.act === button.dataset.event);
      if (!ev) throw new Error('이 단추의 상태를 다시 읽는 중입니다. 잠시 뒤 다시 누르세요');
      if (!ev.enabled) { logLine(`[${ev.button}]을 지금 누를 수 없습니다 — ${ev.why || '까닭을 읽지 못했습니다'}`, true); return; }
      const r = await postJ(API.process + ev.path, pressedBy());
      logLine(`${asset} ${r.button} · 발주 ${r.purchase_order}의 납기를 ${r.days}일 늦췄습니다`);
      await refreshBiz();
      if (state.tab === 'scenario') renderUnits();
    }
    else if (act === 'biz-reset') {
      state.biz = await postJ(API.process + `/api/scenario/${b.key}/reset`, pressedBy());
      logLine(`${asset} ${b.title} 초기화 — 업무 데이터를 처음 값으로 되돌렸습니다${anchorNote(state.biz)}`);
    }
    else if (act === 'mode') { await postJ(API.plant + '/api/mode', { asset, mode }); logLine(`${asset} 운전 모드 → ${UI.status(mode)}`); }
    else if (act === 'fan') { const r = await postJ(API.plant + '/api/manual', { asset, writes: { FanSpeedSP: 80 } }); logLine(`${asset} 수동 팬 80 % → ${UI.status(r.result)} ${r.reason_text || ''}`, r.result === 'REJECTED'); }
    else if (act === 'load') { const r = await postJ(API.plant + '/api/manual', { asset, writes: { LoadSP: 70 } }); logLine(`${asset} 수동 부하 70 % → ${UI.status(r.result)} ${r.reason_text || ''}`, r.result === 'REJECTED'); }
    else if (act === 'reset') { const r = await postJ(API.plant + '/api/manual', { asset, writes: { Reset: 1 } }); logLine(`${asset} 보호 정지 해제 → ${UI.status(r.result)} ${r.reason_text || ''}`, r.result === 'REJECTED'); }
  } catch (e) {
    // 이미 도는 처리 건 때문에 거절됐으면(409 — 서버가 그 건을 instance · started_at 칸으로 싣는다) 까닭 옆에 그 처리 건으로 가는 길을 둔다
    const running = e.status === 409 && e.body && e.body.instance;
    logLine('실패: ' + e.message, true, running ? { href: '#/instances/' + encodeURIComponent(e.body.instance), label: `${e.body.started_at ? UI.time(e.body.started_at) + '에 시작한 ' : ''}처리 건에서 보기` } : null);
  }
  finally { if (button) button.disabled = false; }
  refreshFast();
}
// 이 화면에서 누른 단추의 결과: 카드 아래 한 줄(#scenarioMsg)과 「조작 기록」 접기에 남는다
function logLine(s, failed = false, go = null) { state.log.unshift({ t: new Date(), text: s, failed }); state.log = state.log.slice(0, 30); if (state.tab === 'scenario') scenarioMessage(s, failed, go); }
function scenarioMessage(text, failed = false, go = null) {
  const box = $('#scenarioMsg'); box.textContent = text; if (failed) box.dataset.tone = 'danger'; else delete box.dataset.tone;
  if (go) box.insertAdjacentHTML('beforeend', ` <a class="go" href="${esc(go.href)}">${esc(go.label)}</a>`);
}
// [설비 초기화]는 화면 머리의 더 보기(「…」) 안에 있다(index.html data-head-more — 이름과 아이콘은 동작 사전의 것)
$('#btnReset').addEventListener('click', async () => {
  if (!await UI.confirm({ title: '설비 3기를 정상 운전점으로 되돌릴까요?', body: '진행 중인 결함과 보호 정지가 모두 풀립니다. 열린 처리 건은 그대로 남고, 그 처리 건의 효과 확인 결과가 달라질 수 있습니다.', ok: UI.acts.plantReset[0], danger: true })) return;
  scenarioMessage('설비를 되돌리는 중');
  try { await postJ(API.plant + '/api/reset'); logLine('설비 3기를 정상 운전점으로 되돌렸습니다'); }
  catch (err) { logLine('설비 초기화 실패: ' + err.message, true); }
  finally { await refreshFast(); }
});
// 조작 기록: 출처가 다른 두 기록을 이름을 붙여 나눠 보인다 — 이 화면에서 누른 것과 명령 관문이 검증한 것. failed 는 명령 관문 기록을 못 읽은 사유(「기록 없음」으로 보이지 않는다)
function renderGwLog(entries, failed = '') {
  const box = $('#gwLog');
  const mine = state.log.map(l => `<div class="line" data-kind="${l.failed ? 'fail' : 'ok'}">${UI.icon(l.failed ? 'circle-x' : 'check')}<span class="line-text">${esc(l.text)}</span><time class="line-time num">${esc(UI.time(l.t))}</time></div>`).join('');
  // 명령 관문의 기록(줄마다 원문 접기가 딸린다)은 접기를 펴 둔 동안에만 그린다 — 접힌 채 1초마다 다시 그리지 않는다
  const open = box.closest('details').open;
  const gw = open ? (entries || []).slice(0, 12).map(e => UI.eventRecord({ time: e.t, name: e.ok ? '명령 검증 통과' : '명령 거절', actor: e.asset, detail: e.reason || '', raw: e })).join('') : '';
  const last = pressLines();
  const html = (mine ? `<h4>이 화면에서 누른 단추의 결과</h4>${mine}` : '') + (last ? `<h4>설비마다 마지막으로 누른 단추</h4>${last}` : '') + (!open ? '' : failed ? UI.errorBlock('명령 관문의 기록을 읽지 못했습니다', failed) : gw ? `<h4>명령 관문이 검증한 명령</h4>${gw}` : '') ||
    (open ? `<p class="muted">${esc(UI.t('plant.noCmd'))}</p>` : '');
  if (box._html !== html) { box.innerHTML = html; box._html = html; }      // 1초마다 불리지만 같으면 다시 그리지 않는다(펴 둔 원문 접기가 닫히지 않게)
}

/* ---------------- 설비 회로(디자인기준 6-4): 밝은 캔버스 하나에 설비 세 대의 회로를 같은 크기로 세로로 쌓아 캔버스를 채운다 ----------------
   줄 하나 = 설비 하나: 머리 줄(이름 · 상태 알약 · 운전 모드와 감지기가 보는 것 · 진행 중인 처리 건이 있을 때만 오른쪽 끝에 「처리 건에서 보기 →」) → 그 설비의 회로.
   고르는 것이 없다 — 카드는 누르는 것이 아니라서 손가락 모양 · 올림 표시를 두지 않는다(디자인기준 1-6). 누르는 것은 머리 줄의 링크 하나다.
   사건의 경과 · 판단 · 승인 · 결과는 처리 건 화면 한 곳에 있다 — 이 화면은 그 링크로 그리로 잇는다(사본 없음).
   회로 그림(가로로 긴 한 줄 — 탱크 → 펌프 → 유온 센서 → 압력 센서 → 쿨러와 팬 → 탱크로 돌아오는 배관): 윤곽은 짙은 선 2px, 배관은 주황 5px(운전 중이면 흐른다),
   센서는 빨간 원 안에 이름(TS1 · PS1), 값은 그 부품 위의 숫자. 유온이 경보 조건을 넘으면 값이 빨강이 되고 센서 뒤에 빛이 켜진다. 모양은 plant.css(.hc-*) */
function unitSvg(asset) {
  const fins = (x0, x1, y0, y1, step) => { let d = ''; for (let x = x0; x <= x1; x += step) d += `M${x} ${y0}V${y1}`; return `<path class="hc-fin" d="${d}"/>`; };
  const blade = 'M592 110 L592 99 A11 11 0 0 1 601.5 104.5 Z';
  return `<svg viewBox="0 26 650 126" role="img" aria-label="${esc(asset)} 유압 회로">
    <defs><radialGradient id="hcHot-${esc(asset)}"><stop offset="0" class="hc-hot-0"/><stop offset="1" class="hc-hot-1"/></radialGradient></defs>
    <circle class="hc-glow" cx="300" cy="110" r="40" fill="url(#hcHot-${esc(asset)})"/>
    <path class="hc-pipe" d="M110 110 H200"/>
    <path class="hc-pipe flow" d="M228 110 H500"/>
    <path class="hc-pipe flow ret" d="M532 132 V144 H60 V138"/>
    <rect class="hc-steel" x="10" y="78" width="100" height="60" rx="5"/><rect class="hc-oil" x="12" y="98" width="96" height="38" rx="3"/>
    <text class="hc-cap" x="60" y="68" text-anchor="middle">탱크 <tspan class="hc-val v-ts3">–</tspan></text>
    <rect class="hc-steel" x="194" y="58" width="40" height="26" rx="5"/>${fins(202, 226, 63, 79, 8)}
    <line class="hc-shaft" x1="214" y1="84" x2="214" y2="96"/>
    <circle class="hc-steel" cx="214" cy="110" r="14"/><path class="hc-sym" d="M207 103 L224 110 L207 117 Z"/>
    <text class="hc-cap" x="214" y="48" text-anchor="middle">부하 <tspan class="hc-val v-load">–</tspan></text>
    <rect class="hc-steel" x="500" y="88" width="64" height="44" rx="4"/>${fins(510, 554, 95, 125, 9)}
    <text class="hc-cap" x="532" y="80" text-anchor="middle">냉각 효율 <tspan class="hc-val v-ce">–</tspan></text>
    <g class="hc-fan"><circle class="hc-steel" cx="592" cy="110" r="13"/>
      <path class="hc-blade" d="${blade}"/><path class="hc-blade" d="${blade}" transform="rotate(120 592 110)"/><path class="hc-blade" d="${blade}" transform="rotate(240 592 110)"/></g>
    <text class="hc-cap" x="602" y="142" text-anchor="middle">팬 <tspan class="hc-val v-fan">–</tspan></text>
    <g class="hc-sensor s-ts1"><circle cx="300" cy="110" r="14"/><text x="300" y="110" text-anchor="middle" dominant-baseline="central">TS1</text></g>
    <text class="hc-cap" x="300" y="86" text-anchor="middle">유온 <tspan class="hc-val main v-ts1">–</tspan></text>
    <g class="hc-sensor"><circle cx="410" cy="110" r="14"/><text x="410" y="110" text-anchor="middle" dominant-baseline="central">PS1</text></g>
    <text class="hc-cap" x="410" y="86" text-anchor="middle">압력 <tspan class="hc-val v-ps1">–</tspan></text>
  </svg>`;
}
/* 그림 안에 13px 글자를 넣을 수 없는 좁은 폭에서 그림 아래에 보이는 값 줄(같은 여섯 값 — plant.css 가 [data-tight] 일 때만 보인다) */
const HC_VALS = [['v-ts1', '유온'], ['v-ts3', '탱크'], ['v-ps1', '압력'], ['v-load', '부하'], ['v-ce', '냉각 효율'], ['v-fan', '팬']];
function renderScada() {
  const box = $('#scada');
  if (!state.plant) { box.innerHTML = state.plantError ? UI.errorBlock(UI.t('plant.noConn'), `${state.plantError} ${UI.t('plant.noConnSub')}`) : '<div class="skeleton hc-wait"></div>'; renderIncList(); return; }
  if (!box.querySelector('.ucard')) box.innerHTML = '';
  for (const [asset, u] of Object.entries(state.plant.units)) {
    let card = box.querySelector(`[data-asset="${asset}"]`);
    if (!card) {
      card = el('article', 'ucard'); card.dataset.asset = asset; card.setAttribute('aria-label', `${asset} 유압 회로`);
      card.innerHTML = `<header class="hc-head"><h2>${esc(asset)}</h2><span data-f="state"></span><span class="hc-mode" data-f="mode"></span><span class="hc-go" data-f="go"></span></header>${unitSvg(asset)}
        <dl class="hc-vals">${HC_VALS.map(([cls, name]) => `<div><dt>${esc(name)}</dt><dd class="num ${cls}">–</dd></div>`).join('')}</dl>`;
      box.append(card);
    }
    const t = u.tags, s = u.status, d = detOf(asset), st = unitState(s, d), running = s.state === 'RUN';
    card.classList.toggle('stopped', !running);
    paintState(card, st);
    const set = (cls, v) => card.querySelectorAll('.' + cls).forEach(n => { if (n.textContent !== v) n.textContent = v; });
    set('hc-mode', `${UI.status(s.mode)} · 감지기 ${phaseText(d).replace(/^감지기 /, '')}${s.cmdId ? ` · ${UI.t('plant.lastCmd')} ${UI.status(s.result)}` : ''}`);
    set('v-ts1', fmt(t.TS1, 1) + ' ℃'); set('v-ts3', fmt(t.TS3, 0) + ' ℃'); set('v-ce', fmt(t.CE, 0) + ' %'); set('v-fan', fmt(t.FanSpeedSP, 0) + ' %');
    set('v-load', `${fmt(t.LoadSP, 0)} % · ${fmt(t.EPS1, 1)} kW`); set('v-ps1', fmt(t.PS1, 0) + ' bar');
    const heat = tsColor(t.TS1);                                   // '' | hot(경보 조건 이상) | trip(보호 정지 기준 이상)
    card.querySelectorAll('.v-ts1').forEach(n => n.classList.toggle('hot', !!heat));
    card.querySelector('.s-ts1').classList.toggle('hot', !!heat);
    card.querySelector('.hc-glow').classList.toggle('on', !!heat);
    const fan = card.querySelector('.hc-fan'), spinning = running && t.FanSpeedSP > 0;
    fan.classList.toggle('stop', !spinning);
    fan.style.setProperty('--spin', (spinning ? (2.4 * 60 / Math.max(10, t.FanSpeedSP)).toFixed(2) : 2) + 's');
    // 그 설비의 경보로 열려 아직 진행 중인 처리 건이 있을 때만 그리로 가는 길 하나(없으면 자리를 지키는 글을 두지 않는다 — 디자인기준 1-4)
    const open = state.incidentsRead ? openIncidentFor(asset) : null, go = open ? UI.goLink('instances', '처리 건에서 보기', `data-open-incident="${esc(open.id)}"`) : '', goBox = card.querySelector('[data-f="go"]');
    if (goBox._markup !== go) { goBox.innerHTML = go; goBox._markup = go; }
  }
  scadaFit(); renderIncList();
}
/* 회로의 글자는 화면에서 13px 아래로 줄지 않는다(디자인기준 6-1): 그림은 카드에 맞춰 줄어들므로, 줄어든 만큼 글자의 그림 단위 크기를 키운다(넓은 카드에서는 바탕 크기 그대로).
   그림은 글자가 16.5 단위까지 커져도 서로 겹치지 않게 그렸다. 그보다 더 키워야 13px 이 되는 좁은 폭(data-tight)에서는 그림에 글자를 그리지 않고 같은 값을 그림 아래 줄(.hc-vals)에 보인다.
   센서 원 안의 이름(TS1 · PS1)은 원보다 커질 수 없어, 13px 로 읽히지 않는 폭(data-nosen)에서는 그리지 않는다(그 위의 「유온」 · 「압력」 글이 같은 것을 말한다) */
function scadaFit() {
  document.querySelectorAll('#scada .ucard').forEach(card => {
    const m = card.querySelector('svg').getScreenCTM();
    if (!m || !m.a) return;
    const k = m.a, need = 13.2 / k, px = (base, min) => `${Math.max(base, min / k).toFixed(2)}px`;
    card.style.setProperty('--hc-cap', px(10, 13.2)); card.style.setProperty('--hc-val', px(10.5, 13.4)); card.style.setProperty('--hc-main', px(12, 14)); card.style.setProperty('--hc-sen', px(9, 13.2));
    card.toggleAttribute('data-tight', need > 16.5);
    card.toggleAttribute('data-nosen', need > 11.5);
  });
}
new ResizeObserver(() => { if (state.tab === 'incidents') scadaFit(); }).observe($('#scada'));
/* 캔버스 발치(#incList): 진행 중인 처리 건이 어느 설비에도 없을 때만, 이 화면에서 다음에 할 일로 가는 길 하나(결함 시뮬레이션)를 둔다.
   진행 중인 건이 있으면 그 설비의 머리 줄에 「처리 건에서 보기 →」가 있다. 처리 건의 목록 · 건수 · 상태 이름은 처리 건 화면이 정본이다 — 이 화면에 사본을 두지 않는다.
   처리 건 목록을 읽지 못했으면 「없음」으로 보이지 않고 읽지 못했다고 말한다 */
function renderIncList() {
  const box = $('#incList');
  let html = '';
  if (!state.plant) html = '';
  else if (state.incidentError && !state.incidents.length) html = UI.errorBlock('처리 건 목록을 읽지 못했습니다', state.incidentError);
  else if (state.incidentsRead && !Object.keys(state.plant.units).some(a => openIncidentFor(a))) html = `<div class="hc-foot">${UI.goLink('scenario', `${UI.t('nav.scenario')}에서 결함 넣기`)}</div>`;
  if (box._html !== html) { box.innerHTML = html; box._html = html; }
}

/* ---------------- 실시간 모니터링: 설비 카드 셋 + 추이(uPlot) — 디자인기준 5-7 ----------------
   값은 포털이 1초마다 읽는 설비 상태(refreshFast)를 이 창을 연 뒤부터 모은 것이다(설비마다 최근 30분). 더 긴 기간과 다른 패널은 Grafana 에서 본다.
   한 차트에 값 하나. 기준선: 감지기의 이상 패턴 조건(GET /api/detector/patterns 의 조건식에서 그 태그의 문턱)을 주황 점선으로, 유온의 보호 정지 기준을 빨강 점선으로 긋는다. */
const TREND_TAGS = { TS1: ['plant.ts1', '℃', 1, [40, 70]], CE: ['plant.ce', '%', 0, [0, 100]], PS1: ['plant.ps1', 'bar', 1, [120, 200]], FS1: ['plant.fs1', 'L/min', 2, [0, 12]], VS1: ['plant.vs1', 'mm/s', 2, [0, 2.5]] };
const TREND = { asset: null, tag: 'TS1', chart: null, sparks: {}, opened: Date.now(), hist: {}, limits: null, limitsError: '', ready: null, KEEP: 1800 };
function trendPush(plant) {
  const now = Date.now() / 1000;
  for (const [a, u] of Object.entries(plant.units)) {
    const h = TREND.hist[a] || (TREND.hist[a] = { t: [], ...Object.fromEntries(Object.keys(TREND_TAGS).map(k => [k, []])) });
    h.t.push(now); Object.keys(TREND_TAGS).forEach(k => h[k].push(u.tags[k]));
    if (h.t.length > TREND.KEEP) Object.values(h).forEach(arr => arr.shift());
  }
}
// 감지기 조건식("CE < 70.0 and TS1 > 55.0 and slope(TS1) > 0.0")에서 태그마다의 문턱을 읽는다 — 태그와 숫자를 바로 견주는 항만(기울기 · 상태 항은 기준선이 아니다)
function limitsFromCatalog(body) {
  const out = {}, catalog = (body.applied || {}).catalog || {}, names = (body.applied || {}).names || {};
  for (const [code, p] of Object.entries(catalog)) for (const term of String(p.condition || '').split(/\s+and\s+/)) {
    const m = /^([A-Za-z][A-Za-z0-9]*) (<=?|>=?) (-?\d+(?:\.\d+)?)$/.exec(term.trim());
    if (m && TREND_TAGS[m[1]]) (out[m[1]] = out[m[1]] || []).push({ value: Number(m[3]), below: m[2].startsWith('<'), pattern: names[code] || code });
  }
  return out;
}
async function loadLimits() {
  try { TREND.limits = limitsFromCatalog(await getJ(API.detector + '/api/detector/patterns')); TREND.limitsError = ''; }
  catch (e) { TREND.limits = null; TREND.limitsError = e.message; }
}
function trendLines(tag) {
  const cs = getComputedStyle(document.documentElement), unit = TREND_TAGS[tag][1];
  const lines = ((TREND.limits || {})[tag] || []).map(l => ({ value: l.value, color: cs.getPropertyValue('--st-warn').trim(), text: `${l.pattern} 조건 ${l.value} ${unit} ${l.below ? '미만' : '초과'}` }));
  if (tag === 'TS1') lines.push({ value: TS_TRIP, color: cs.getPropertyValue('--st-fail').trim(), text: `보호 정지 ${TS_TRIP} ℃` });
  return lines;
}
function trendBuild() {
  const box = $('#trendChart'), h = TREND.hist[TREND.asset], [, , , base] = TREND_TAGS[TREND.tag], lines = trendLines(TREND.tag);
  const cs = getComputedStyle(document.documentElement), ink = cs.getPropertyValue('--muted-foreground').trim(), brand = cs.getPropertyValue('--primary').trim();
  $('#trendTitle').textContent = `${TREND.asset} 추이`;
  if (TREND.chart) { TREND.chart.destroy(); TREND.chart = null; }
  box.innerHTML = '';
  const width = Math.floor(box.getBoundingClientRect().width);
  if (width <= 0 || !h) return;      // 가려진 화면 — 다시 보일 때(ResizeObserver) 그린다
  const axis = { stroke: ink, font: '12px "Pretendard Variable", sans-serif', grid: { stroke: cs.getPropertyValue('--border').trim(), width: 1 }, ticks: { show: false }, gap: 8 };
  const two = n => String(n).padStart(2, '0');
  TREND.chart = new uPlot({ width, height: 300, legend: { show: false }, padding: [14, 8, 0, 4],
    cursor: { points: { size: 8, width: 2 }, y: false, drag: { x: false, y: false } },
    scales: { x: { time: true }, y: { range: (u, min, max) => [Math.min(base[0], ...lines.map(l => l.value), min ?? base[0]), Math.max(base[1], ...lines.map(l => l.value), max ?? base[1])] } },
    axes: [{ ...axis, values: (u, ts) => ts.map(t => { const d = new Date(t * 1000); return `${two(d.getHours())}:${two(d.getMinutes())}:${two(d.getSeconds())}`; }), space: 90 }, { ...axis, size: 46, values: (u, vs) => vs.map(x => String(x)) }],
    series: [{}, { label: UI.t(TREND_TAGS[TREND.tag][0]), stroke: brand, width: 2, points: { show: false }, spanGaps: true,
      fill: u => { const g = u.ctx.createLinearGradient(0, u.bbox.top, 0, u.bbox.top + u.bbox.height); g.addColorStop(0, 'rgba(23,23,23,.10)'); g.addColorStop(1, 'rgba(23,23,23,0)'); return g; } }],      // 선 아래 옅은 면도 무채색(색은 기준선 — 상태 — 에만)
    hooks: { draw: [u => { const ctx = u.ctx; ctx.save(); lines.forEach(l => { const y = Math.round(u.valToPos(l.value, 'y', true)); ctx.strokeStyle = l.color; ctx.lineWidth = 1.5 * devicePixelRatio; ctx.setLineDash([6 * devicePixelRatio, 5 * devicePixelRatio]); ctx.beginPath(); ctx.moveTo(u.bbox.left, y); ctx.lineTo(u.bbox.left + u.bbox.width, y); ctx.stroke(); }); ctx.restore(); }] },
  }, [h.t, h[TREND.tag]], box);
  trendLegend();
}
function trendLegend() {
  const h = TREND.hist[TREND.asset], [term, unit, digits] = TREND_TAGS[TREND.tag], last = h && h[TREND.tag].length ? h[TREND.tag][h[TREND.tag].length - 1] : null;
  $('#trendLegend').innerHTML = `<span><i></i>${esc(UI.t(term))} <b class="num">${last == null ? '–' : fmt(last, digits)}</b> ${unit}</span>` +
    trendLines(TREND.tag).map(l => `<span class="th"><i style="--c:${l.color}"></i>${esc(l.text)}</span>`).join('') +
    (TREND.limitsError ? `<span class="th" title="${esc(TREND.limitsError)}">감지기의 경보 조건을 읽지 못해 기준선 일부가 빠져 있습니다</span>` : '');
  const sec = Math.round((Date.now() - TREND.opened) / 1000);
  $('#trendRange').textContent = `이 창을 연 뒤 ${sec >= 60 ? Math.floor(sec / 60) + '분 ' : ''}${sec % 60}초`;
}
function trendPick(asset) {
  TREND.asset = asset;
  document.querySelectorAll('#monUnits .unit').forEach(c => { const on = c.dataset.asset === asset; c.setAttribute('aria-current', String(on)); c.querySelector('.unit-pick').setAttribute('aria-pressed', String(on)); });
  $('#grafanaLink').href = `${P(3000)}/d/hyd-trend?orgId=1&var-asset=${encodeURIComponent(asset)}&refresh=5s`;
  if (TREND.chart || window.uPlot) trendBuild();
}
$('#trendMetric').innerHTML = Object.entries(TREND_TAGS).map(([k, [term]]) => `<button type="button" data-tag="${k}" aria-pressed="${k === TREND.tag}">${esc(UI.t(term))}</button>`).join('');
$('#trendMetric').addEventListener('click', e => {
  const b = e.target.closest('button[data-tag]'); if (!b) return;
  TREND.tag = b.dataset.tag;
  document.querySelectorAll('#trendMetric button').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
  if (window.uPlot && TREND.asset) trendBuild();
});
$('#monUnits').addEventListener('click', e => { const b = e.target.closest('.unit-pick'); if (b) trendPick(b.closest('.unit').dataset.asset); });
// 차트와 작은 추이 선은 담긴 칸의 너비를 따라간다(메뉴 줄을 접거나 창 크기를 바꿀 때, 가려졌다 다시 보일 때)
const trendResize = new ResizeObserver(() => {
  if (state.tab !== 'trends' || !window.uPlot) return;
  const box = $('#trendChart'), w = Math.floor(box.getBoundingClientRect().width);
  if (w > 0) { if (TREND.chart) TREND.chart.setSize({ width: w, height: 300 }); else if (TREND.asset) trendBuild(); }
  for (const [a, sp] of Object.entries(TREND.sparks)) { const host = document.querySelector(`#monUnits [data-asset="${a}"] [data-f="spark"]`), sw = host ? Math.floor(host.getBoundingClientRect().width) : 0; if (sw > 0) sp.setSize({ width: sw, height: 44 }); }
});
trendResize.observe($('#trendChart'));
function renderTrends() {
  const box = $('#monUnits'), notice = $('#trendsNotice');
  if (!state.plant) {
    notice.hidden = !state.plantError; notice.innerHTML = state.plantError ? UI.errorBlock(UI.t('plant.noConn'), `${state.plantError} ${UI.t('plant.noConnSub')}`) : '';
    if (!box.children.length) box.innerHTML = '<div class="skeleton" style="height:228px"></div>'.repeat(3);
    return;
  }
  notice.hidden = true;
  const units = state.plant.units;
  if (!box.querySelector('.unit')) {
    box.innerHTML = Object.keys(units).map(monCardHtml).join('');
    trendResize.observe(box);
  }
  for (const [a, u] of Object.entries(units)) {
    const card = box.querySelector(`[data-asset="${a}"]`); if (!card) continue;
    paintMonCard(card, a, u);
    // 아래 고정 줄은 그 설비에 열린 처리 건이 있을 때만 나타난다(「열린 처리 건 없음」 줄로 빈 자리를 지키지 않는다 — 1-4)
    const inc = openIncidentFor(a), foot = card.querySelector(':scope > footer'), go = foot.querySelector('.go');
    foot.hidden = !inc; if (inc) go.dataset.openIncident = inc.id; else delete go.dataset.openIncident;
  }
  if (!TREND.asset || !units[TREND.asset]) trendPick(Object.keys(units)[0]);
  // 차트 부품(uPlot)과 감지기의 경보 조건은 이 화면을 처음 열 때 한 번 싣는다. 실패하면 까닭을 차트 자리에 적고 다음에 열 때 다시 싣는다
  if (!TREND.ready) TREND.ready = Promise.all([UI.need('chart'), loadLimits()]).then(() => { trendSparks(); trendBuild(); },
    e => { TREND.ready = null; $('#trendChart').innerHTML = UI.errorBlock('추이 그림 부품을 싣지 못했습니다', e.message); });
  if (!window.uPlot) return;
  if (!TREND.limits && TREND.limitsError && !loadLimits.again) { loadLimits.again = setTimeout(async () => { await loadLimits(); loadLimits.again = 0; if (TREND.limits) trendBuild(); }, 10000); }
  trendSparks();
  const h = TREND.hist[TREND.asset];
  if (TREND.chart && h) { TREND.chart.setData([h.t, h[TREND.tag]]); trendLegend(); } else if (!TREND.chart) trendBuild();
}
function trendSparks() {
  if (!window.uPlot) return;
  for (const [a, h] of Object.entries(TREND.hist)) {
    const host = document.querySelector(`#monUnits [data-asset="${a}"] [data-f="spark"]`); if (!host) continue;
    if (!TREND.sparks[a]) {
      const w = Math.floor(host.getBoundingClientRect().width); if (w <= 0) continue;
      TREND.sparks[a] = new uPlot({ width: w, height: 44, cursor: { show: false }, legend: { show: false }, select: { show: false }, padding: [4, 0, 4, 0], scales: { x: { time: false }, y: { range: (u, min, max) => [Math.min(40, min ?? 40), Math.max(TS_MAX, max ?? TS_MAX)] } }, axes: [{ show: false }, { show: false }],
        series: [{}, { stroke: getComputedStyle(document.documentElement).getPropertyValue('--primary').trim(), width: 1.6, points: { show: false },
          fill: u => { const g = u.ctx.createLinearGradient(0, 0, 0, u.bbox.height); g.addColorStop(0, 'rgba(23,23,23,.10)'); g.addColorStop(1, 'rgba(23,23,23,0)'); return g; } }] }, [[], []], host);
    }
    TREND.sparks[a].setData([h.t.slice(-90), h.TS1.slice(-90)]);
  }
}

/* ---------------- 주기 읽기 ---------------- */
async function refreshFast() {
  if (refreshFast.busy) return; refreshFast.busy = true;
  try {
    try {
      const plant = await getJ(API.plant + '/api/state');
      if (!plant || !plant.units || typeof plant.units !== 'object' || Array.isArray(plant.units) || Object.values(plant.units).some(u => !u?.tags || !u?.status)) throw new Error('설비 상태 응답 형식이 올바르지 않습니다.');
      state.plant = plant; state.plantError = ''; trendPush(plant);
    } catch (e) { state.plant = null; state.plantError = e.message; }
    try { state.det = await getJ(API.detector + '/api/detector/state'); state.detError = ''; } catch (e) { state.det = null; state.detError = e.message; }
    if (state.plant) {
      $('#scale').textContent = state.plant.time_scale; $('#railScale').hidden = false;      // 메뉴 줄 맨 아래 「· 20배속」
      // 설비와 감지기는 같은 배율로 돌아야 한다. 다르면 감지 · 처리와 시간이 어긋난다 — 그 사실과 고칠 곳을 글로 보인다
      const det = state.det && Number(state.det.time_scale), off = !!det && det !== Number(state.plant.time_scale), why = $('#scaleWhy');
      const html = off ? `<div class="alert" role="alert">${UI.icon('triangle-alert')}<h2>설비와 감지기의 시간 배율이 다릅니다 (설비 ${esc(String(state.plant.time_scale))}배 · 감지기 ${esc(String(det))}배)</h2><section>경보가 나는 때와 처리 시간이 어긋납니다. compose.yaml 의 TIME_SCALE 값이 서비스마다 같은지 확인한 뒤 스택을 다시 시작하세요.</section></div>` : '';
      if (why._html !== html) { why.innerHTML = html; why._html = html; why.hidden = !off; }
    } else { $('#scale').textContent = '–'; $('#railScale').hidden = true; }      // 배속을 모르면 그 조각을 그리지 않는다
    if (state.tab === 'scenario') { renderUnits(); try { renderGwLog(await getJ(API.gateway + '/api/gateway/log')); } catch (e) { renderGwLog([], e.message); } }
    if (state.tab === 'incidents') renderScada();
    if (state.tab === 'trends') renderTrends();
  } finally { refreshFast.busy = false; }
}
// 메뉴 「처리 건」 곁의 건수 점: 내 차례의 수 — 처리 건 화면의 「내 차례」 묶음과 같은 셈(ui.js hydCases.groups).
// 0 이면 그리지 않는다. 못 읽었으면 지난 수를 지우고 까닭을 메뉴 줄의 title 에 둔다(0 건으로 읽히지 않게 「?」를 보인다)
async function refreshTodoCount() {
  const dot = $('#navTodo'), button = dot.closest('a');
  try {
    const rows = requireList(await getJ(API.process + '/api/todolist?status=IN_PROGRESS'), '담당 작업 목록');
    const n = hydCases.groups({ todo: rows }).mine.length;
    state.todo = n; state.todoRows = rows; state.todoError = '';
    dot.textContent = n ? (n > 99 ? '99+' : String(n)) : ''; dot.classList.remove('unknown');
    if (n) dot.setAttribute('aria-label', `내가 할 일 ${n}건`); else dot.removeAttribute('aria-label');
    button.title = n ? `내가 할 일 ${n}건` : '';
  } catch (e) { state.todo = null; state.todoRows = null; state.todoError = e.message; dot.textContent = '?'; dot.classList.add('unknown'); button.title = '내가 할 일 수를 읽지 못했습니다: ' + e.message; }
}
// 홈의 단계 카드가 보이는 처리 건 수: 처리 건 화면이 읽는 것과 같은 목록(최근 50건 · 진행 중인 건 · 담당 작업)을 같은 함수로 센다. 홈이 열려 있을 때만 읽는다
async function refreshCases() {
  if (state.tab !== 'main') return;
  try {
    if (state.todoRows == null) throw new Error(state.todoError || '담당 작업 목록을 읽지 못했습니다.');
    const list = status => getJ(API.process + `/api/instances?limit=${hydCases.WINDOW}` + (status ? '&status=' + status : '')).then(rows => requireList(rows, '처리 건 목록'));
    const [all, running] = await Promise.all([list(''), list('RUNNING')]);
    state.cases = hydCases.groups({ all, running, todo: state.todoRows }); state.caseError = '';
  } catch (e) { state.caseError = e.message; }
}
async function refreshSlow() {
  if (refreshSlow.busy) return; refreshSlow.busy = true;
  try {
    try { state.incidents = requireList(await getJ(API.process + '/api/incidents'), '사건 목록'); state.incidentError = ''; state.incidentsRead = true; } catch (e) { state.incidentError = e.message; }
    if (state.tab === 'scenario' || state.tab === 'incidents' || !state.biz || state.biz.failed || labFollow) await refreshBiz();
    await refreshTodoCount();
    await refreshCases();
    if (state.tab === 'incidents') renderScada();
  } finally { refreshSlow.busy = false; }
}
renderStack(); pollHealth(); refreshFast(); refreshSlow(); UI.loadPatterns();
setInterval(refreshFast, 1000); setInterval(refreshSlow, 2000); setInterval(pollHealth, 5000);
