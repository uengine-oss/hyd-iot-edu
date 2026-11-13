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
      error.status = r.status; error.detail = j.detail;
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
function keyboardItem(item) {
  item.tabIndex = 0; item.setAttribute('role', 'button');
  item.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); item.click(); } });
}

const state = { tab: 'main', plant: null, det: null, detError: '', incidents: [], selected: null, detail: null, incAudit: null, waves: {}, log: [], selectedAsset: null, showAll: false, incShown: 20 };

/* ---------------- tabs ---------------- */
// 탭에 들어올 때 할 일: 화면 모듈은 selectTab 을 감싸지 않고 이 표에 적는다(실린 차례대로 불린다 — 셸이 맨 마지막). fn(name)
const tabHooks = [];
window.hydTabs = { onShow(fn) { tabHooks.push(fn); } };
/* 메뉴 표: index.html 의 주 메뉴 한 곳(button[data-menu][data-tabs])을 읽는다. 메뉴 하나에 화면이 하나 이상 딸리고, 화면이 둘 이상이면 본문 위 탭 줄로 오간다.
   메뉴 줄의 고른 표시 · 탭 줄 · 이전/다음 순서 · 머리줄 위치 표시가 모두 이 표로 그려진다. 화면 이름(탭 이름 = 화면 제목)은 nav.<화면>, 메뉴 이름은 nav.menu.<메뉴>(ui.js).
   화면은 selectTab('<화면>') · 주소 #/<화면> · [data-go-tab="<화면>"] 어느 길로 열어도 그 화면이 든 메뉴와 탭이 고른 상태가 된다. */
const MENU = [...document.querySelectorAll('.rail nav button[data-menu]')].map(button => {
  const noteKey = `nav.menu.${button.dataset.menu}.note`;
  return { id: button.dataset.menu, name: UI.t('nav.menu.' + button.dataset.menu), tabs: button.dataset.tabs.split(/\s+/).filter(Boolean), button,
    note: UI.t(noteKey) === noteKey ? '' : UI.t(noteKey) };
});
const SCREENS = MENU.flatMap(m => m.tabs);                    // 이전 · 다음 단추가 도는 차례
const tabName = tab => UI.t('nav.' + tab);
const menuOf = tab => MENU.find(m => m.tabs.includes(tab)) || null;
window.hydMenu = { list: MENU, screens: SCREENS, of: menuOf, name: tabName };
// 메뉴 표와 화면 구역(view-…)이 어긋나면 그 화면은 어느 메뉴로도 갈 수 없다 — 조용히 두지 않는다
{
  const views = [...document.querySelectorAll('main .view')].map(v => v.id.replace(/^view-/, ''));
  const lost = views.filter(v => !SCREENS.includes(v)), ghost = SCREENS.filter(s => !views.includes(s));
  if (lost.length || ghost.length) throw new Error(`주 메뉴 표(index.html data-tabs)와 화면 구역이 다릅니다 — 메뉴에 없는 화면: ${lost.join(', ') || '없음'} · 화면이 없는 메뉴 항목: ${ghost.join(', ') || '없음'}`);
}
function renderSubTabs(name) {
  const menu = menuOf(name), bar = $('#subTabs'), note = $('#menuNote');
  MENU.forEach(m => {
    const active = m === menu;
    m.button.classList.toggle('active', active);
    if (active) m.button.setAttribute('aria-current', 'page'); else m.button.removeAttribute('aria-current');
  });
  bar.hidden = menu.tabs.length < 2;
  bar.setAttribute('aria-label', `${menu.name} 메뉴의 화면`);
  bar.innerHTML = bar.hidden ? '' : menu.tabs.map(t => `<button type="button" role="tab" class="tab${t === name ? ' on' : ''}" data-tab="${esc(t)}" aria-selected="${t === name}">${esc(tabName(t))}</button>`).join('');
  note.hidden = !menu.note; note.textContent = menu.note;
}
function selectTab(name) {
  if (!document.getElementById('view-' + name)) return;
  const changed = state.tab !== name;
  state.tab = name;
  renderSubTabs(name);
  const brand = document.getElementById('brandHome'); if (brand) brand.classList.toggle('active', name === 'main');
  document.querySelectorAll('.view').forEach(v => v.classList.toggle('active', v.id === 'view-' + name));
  if (changed) $('main').scrollTo(0, 0);
  if (name === 'scenario') renderUnits();
  if (name === 'incidents') { renderScada(); renderIncList(); renderDetail(); }
  if (name === 'trends') renderTrends();
  updateNavigation(name);
  tabHooks.forEach(fn => fn(name));
}
document.querySelectorAll('[data-term]').forEach(n => { const t = UI.t(n.dataset.term); if (t !== n.dataset.term) n.textContent = t; });
// 메뉴 줄 단추는 그 메뉴의 첫 화면을 연다. 그 메뉴의 다른 화면은 탭 줄 단추(button[data-tab])로 연다
MENU.forEach(m => {
  m.button.innerHTML = UI.icon(m.button.dataset.icon) + `<span>${esc(m.name)}</span>`;
  m.button.addEventListener('click', () => { selectTab(m.tabs[0]); $('#content').focus({ preventScroll: true }); });
});
$('#subTabs').addEventListener('click', e => { const b = e.target.closest('button[data-tab]'); if (b) selectTab(b.dataset.tab); });
function setMenu(open) {
  $('#navigation').classList.toggle('open', open);
  $('#menuToggle').setAttribute('aria-expanded', String(open));
  $('#menuToggle').setAttribute('aria-label', open ? '메뉴 닫기' : '메뉴 열기');
  $('#navScrim').hidden = !open;
  // Off-canvas items must not remain in the keyboard tab order.
  $('#navigation').inert = matchMedia('(max-width:720px)').matches && !open;
}
function updateNavigation(name) {
  const index = SCREENS.indexOf(name), menu = menuOf(name);
  // 머리줄 위치: 「메뉴 › 화면」. 화면이 하나뿐인 메뉴는 이름이 같으므로 화면 이름만 보인다
  const group = $('#pageGroup'); group.hidden = menu.tabs.length < 2; group.textContent = menu.name;
  $('#pageLocation').textContent = tabName(name);
  document.title = `${tabName(name)} · HYD Lab`;
  const prev = SCREENS[index - 1], next = SCREENS[index + 1];
  for (const [id, target, direction] of [['pagePrev', prev, '이전'], ['pageNext', next, '다음']]) {
    const button = $('#' + id); if (!button) continue;
    button.disabled = !target;
    button.dataset.target = target || '';
    button.innerHTML = `<span>${direction}${direction === '다음' ? ' →' : ''}</span><b>${esc(target ? tabName(target) : (direction === '이전' ? '첫 화면' : '마지막 화면'))}</b>`;
    button.setAttribute('aria-label', `${direction} 화면: ${target ? tabName(target) : '없음'}`);
  }
  const count = $('#pagePosition'); if (count) count.textContent = `${index + 1} / ${SCREENS.length}`;
  setMenu(false);
}
$('#menuToggle').addEventListener('click', () => {
  const open = $('#menuToggle').getAttribute('aria-expanded') !== 'true'; setMenu(open);
  if (open) $('#navigation [aria-current="page"]')?.focus();
});
$('#navScrim').addEventListener('click', () => { setMenu(false); $('#menuToggle').focus(); });
document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && $('#navigation').classList.contains('open')) { setMenu(false); $('#menuToggle').focus(); }
  if (e.key === 'Tab' && matchMedia('(max-width:720px)').matches && $('#navigation').classList.contains('open')) {
    const items = [...$('#navigation').querySelectorAll('button')];
    if (e.shiftKey && document.activeElement === items[0]) { e.preventDefault(); items.at(-1).focus(); }
    if (!e.shiftKey && document.activeElement === items.at(-1)) { e.preventDefault(); items[0].focus(); }
  }
});
matchMedia('(max-width:720px)').addEventListener('change', () => setMenu(false));
document.querySelectorAll('#pagePrev,#pageNext').forEach(b => b.addEventListener('click', () => {
  if (b.dataset.target) { selectTab(b.dataset.target); $('#content').focus({ preventScroll: true }); }
}));
selectTab('main');

/* ---------------- 시스템 구성: layer stack + health ---------------- */
const healthState = {};
// 층 그림: 줄 = 계층(위가 업무, 아래가 현장), 칸 = 영역(OT · DMZ · IT). 부품은 제 영역의 칸에 놓인다 —
// 두 영역에 걸친 계층(관제 = OT + IT, 이벤트 백본 = DMZ + IT)은 부품이 두 칸에 나뉘어 보이고, OT 와 IT 사이에는 DMZ 칸만 있다(교재의 구조)
// 선택 도구: 서비스 자체가 선택(optional)이거나, 서비스는 기본인데 사람이 여는 화면만 선택 도구(entryHealth — Redpanda 는 기본, Console 은 tools 프로필)인 것
const optionalOf = c => c.entryHealth || c.optional;
const optionalText = c => c.optional ? '(선택 도구)' : '(여는 화면은 선택 도구)';
const ZONES = [['ot', 'OT', '설비 · 실시간 운전'], ['dmz', 'DMZ', '승인된 명령과 데이터가 지나는 통로'], ['it', 'IT', '기록 · 분석 · 지식 · 처리']];
function renderStack() {
  const stack = $('#stack');
  const comp = c => {
    const key = c.health || c.url;
    // 상태를 재지 않는 칸(health 없음)은 회색 점을 두지 않는다 — 「꺼짐」처럼 읽힌다. 글자로 「상태 확인 대상 아님」을 붙인다
    return `<div class="comp"><span class="comp-name">${c.health ? `<i class="dot ${healthState[key] || 'unknown'}" data-h="${esc(key)}"></i>` : ''}<i class="z ${c.zone}">${c.zone.toUpperCase()}</i>` +
      `<a href="${c.url}" data-entry="${esc(c.url)}" target="_blank" rel="noopener"${optionalOf(c) ? ' title="누르면 켜져 있는지 확인하고 엽니다."' : ''}>${esc(c.name)} ↗</a>` +
      (optionalOf(c) ? `<span class="comp-flag" data-entry-status="${esc(c.url)}">${esc(optionalText(c))}</span>` : '') + (c.health ? '' : '<span class="comp-flag">(상태 확인 대상 아님)</span>') + '</span>' +
      `<span class="role-desc">${esc(c.role)}</span>${c.real ? `<span class="role">현업에서는 ${esc(c.real)}</span>` : ''}</div>`;
  };
  stack.innerHTML = `<div class="sys-row sys-head"><div class="sys-layer"></div>${ZONES.map(([z, name, what]) => `<div class="sys-zone ${z}"><b>${name}</b><span>${esc(what)}</span></div>`).join('')}</div>` +
    LAYERS.map(L => `<div class="sys-row layer${L.focus ? ' focus' : ''}"><div class="sys-layer"><strong>${esc(L.name)}</strong><span>${esc(L.role)}</span></div>` +
      ZONES.map(([z]) => `<div class="sys-cell ${z}">${L.comps.filter(c => c.zone === z).map(comp).join('')}</div>`).join('') + '</div>').join('');
  const all = LAYERS.flatMap(L => L.comps);
  stack.querySelectorAll('.comp a').forEach(a => { const c = all.find(x => x.url === a.dataset.entry); if (c && optionalOf(c)) a.addEventListener('click', e => openOptional(e, c)); });
}
// A147: 선택 도구(FUXA · Prometheus · Redpanda Console)는 5초 상태 확인에서 뺀다. 꺼진 포트에 보내는 요청은 fetch · img · WebSocket
// 어느 방식이든 브라우저가 콘솔에 ERR_CONNECTION_REFUSED 를 남기기 때문이다. 링크를 누를 때만
// 한 번 확인해 켜져 있으면 열고, 꺼져 있으면 "(꺼짐)"을 표시한다.
async function reachable(url) {
  const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 3000);
  try { await fetch(url, { mode: 'no-cors', cache: 'no-store', signal: controller.signal }); return true; }
  catch (_) { return false; }
  finally { clearTimeout(timer); }
}
async function openOptional(e, c) {
  e.preventDefault();
  const probe = c.entryHealth || c.health || c.url, status = document.querySelector(`[data-entry-status="${CSS.escape(c.url)}"]`);
  if (status) status.textContent = '(확인 중)';
  const up = await reachable(probe);
  if (c.optional && c.health) { healthState[c.health] = up ? 'up' : 'off'; document.querySelectorAll(`.dot[data-h="${CSS.escape(c.health)}"]`).forEach(d => d.className = 'dot ' + healthState[c.health]); }
  if (status) status.textContent = up ? optionalText(c) : c.optional ? '(꺼짐 — 켜면 열립니다)' : '(여는 화면이 꺼짐 — 켜면 열립니다)';
  if (up) window.open(c.url, '_blank', 'noopener');
}
async function pollHealth() {
  if (pollHealth.busy) return; pollHealth.busy = true;
  const dots = $('#healthDots');
  try {
    await Promise.all(LAYERS.flatMap(L => L.comps).filter(c => c.health && !c.optional).map(async c => {
      const key = c.health;
      const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 4000);
      try {
        if (c.health.endsWith('/healthz')) {            // our services answer JSON with CORS
          const r = await fetch(c.health, { cache: 'no-store', signal: controller.signal }); healthState[key] = r.ok ? 'up' : 'down';
        } else {                                         // third-party UIs: opaque probe = reachable
          await fetch(c.health, { mode: 'no-cors', cache: 'no-store', signal: controller.signal }); healthState[key] = 'up';
        }
      } catch (e) { healthState[key] = 'down'; }
      finally { clearTimeout(timer); }
      document.querySelectorAll(`.dot[data-h="${CSS.escape(key)}"]`).forEach(d => d.className = 'dot ' + healthState[key]);
    }));
    // F10 · A147: optional tools are not counted — off is their normal state, not a failure
    const all = LAYERS.flatMap(L => L.comps).filter(c => c.health && !c.optional);
    const down = all.filter(c => healthState[c.health] === 'down');
    dots.innerHTML = `<span title="서비스 응답 확인입니다. 전체 파이프라인의 성공을 뜻하지 않습니다."><i class="dot ${down.length ? 'down' : 'up'}"></i>${esc(UI.t('header.services'))} ${all.length - down.length}/${all.length}${down.length ? ` — ${esc(UI.t('header.noResponse'))}: ` + esc(down.map(c => c.name.split(' ')[0]).join(', ')) : ''}</span>`;
  } finally { pollHealth.busy = false; }
}

/* ---------------- 결함 시뮬레이션 ---------------- */
const FAULT_LABEL = { cooler_degradation: '쿨러 성능 저하', pump_leakage: '펌프 내부 누설', fan_vibration: '팬 베어링 마모', restore: '복구' };
// 감지기를 못 읽었으면 「감시 중」(정상)으로 보이지 않는다 — 읽기 전 · 실패를 따로 보인다
function detectorUnknown() { return state.det ? '' : UI.chipText(state.detError ? '감지기 응답 없음' : '감지기 확인 중', state.detError ? 'danger' : 'neutral'); }
// 감지기 패턴(쿨러 · 펌프 · 팬 …) 중 가장 급한 단계 — 설비 카드는 쿨러 하나(옛 최상위 phase)가 아니라 모든 패턴을 본다(G3b-11)
const PHASE_ORDER = ['RAISED', 'CLEARING', 'CANDIDATE', 'IDLE'];
function worstPhase(d) { const all = Object.values(d.patterns || {}).map(p => p.phase).filter(Boolean); return PHASE_ORDER.find(x => all.includes(x)) || 'IDLE'; }
// 값 줄의 「경보」 칸(글): 조용하면 「감시 중」, 아니면 조용하지 않은 감지기 패턴마다 단계 · 이름. 칩은 카드 머리의 상태 하나뿐이다
function phaseText(d) {
  if (!state.det) return state.detError ? `감지기 응답 없음 — ${state.detError}` : '감지기 확인 중';
  const busy = Object.entries(d.patterns || {}).filter(([, p]) => p.phase && p.phase !== 'IDLE');
  return busy.length ? busy.map(([code, p]) => `${UI.status(p.phase)} · ${UI.patternName(code)}`).join(' / ') : UI.status('IDLE');
}
// 유온 기준 한 곳: 주의 55 ℃(감지기 경보 · 회복 기준) · 보호 정지 65 ℃ — 막대 · 회로도 전구 · 홈(main.js)이 같이 쓴다
const TS_HOT = 55, TS_TRIP = 65;
function tsColor(t) { return t >= TS_TRIP ? 'trip' : t >= TS_HOT ? 'hot' : ''; }
// 작은 추이 그림(설비 카드): 값이 둘 이상 모이면 선을 그린다. 색과 굵기는 canvas.css(.lab-spark)가 정한다
function sparkline(svg, values, min, max) {
  const w = 300, h = 36, n = (values || []).length;
  svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
  if (n < 2) { svg.removeAttribute('preserveAspectRatio'); svg.innerHTML = '<text class="wait" x="0" y="23">압력 추이를 모으고 있습니다…</text>'; return; }
  const pts = values.map((v, i) => `${((i / Math.max(1, n - 1)) * w).toFixed(1)},${(h - ((v - min) / (max - min || 1)) * (h - 4) - 2).toFixed(1)}`).join(' ');
  svg.setAttribute('preserveAspectRatio', 'none');
  svg.innerHTML = `<polyline vector-effect="non-scaling-stroke" points="${pts}"/>`;
}
// 설비 한 기의 상태 낱말 하나: 보호 정지 → 경보(감지기의 가장 급한 단계) → 운전 상태 차례로 급한 것을 보인다. 감지기를 못 읽었으면 그 사실을 보인다
function unitChip(s, d) {
  if (s.state === 'TRIP') return UI.chip(s.state);
  if (!state.det) return detectorUnknown();
  return worstPhase(d) !== 'IDLE' ? UI.chip(worstPhase(d)) : UI.chip(s.state);
}
// 설비 카드(디자인 기준 5-7): 이름 · 상태 하나 → 큰 숫자(유온)와 기준 막대 → 결함 실험 단추 → 값 여섯 줄 → 압력 추이 → 자세히 · 현장 패널 접기
function renderUnits() {
  const box = $('#units');
  if (!state.plant) { box.innerHTML = UI.empty(UI.t('plant.noConn'), UI.t('plant.noConnSub')); return; }
  if (!box.querySelector('.unit')) box.innerHTML = '';
  const units = state.plant.units;
  const row = (name, cls, tag) => `<dt>${esc(name)}${tag ? ` <small>${esc(tag)}</small>` : ''}</dt><dd class="${cls}"></dd>`;      // 이름 먼저, 태그 코드는 보조(명칭표 「설비」)
  for (const [asset, u] of Object.entries(units)) {
    let card = box.querySelector(`[data-asset="${asset}"]`);
    if (!card) {
      const exp = EXPERIMENT[asset];
      card = el('article', 'unit'); card.dataset.asset = asset; card.setAttribute('aria-label', `${asset} 설비`);
      card.innerHTML = `<header class="lab-head"><h2>${esc(asset)}</h2><span class="lab-state"></span></header>
        <div class="lab-temp"><b class="num v"></b><span>℃ ${esc(UI.t('plant.ts1'))}</span></div>
        <div class="lab-bar" role="img"><i></i><b class="hot" style="left:${TS_HOT}%"></b><b class="trip" style="left:${TS_TRIP}%"></b></div>
        <p class="lab-bar-note">감지기 경보 기준 ${TS_HOT} ℃ · ${esc(UI.t('plant.trip'))}</p>
        ${exp ? `<section class="lab-exp" aria-label="${esc(UI.t('plant.faults'))}">
          <p class="label">${esc(UI.t('plant.faults'))} · ${esc(exp.title)} <span class="biz-alert"></span></p>
          <div class="lab-buttons">${exp.buttons.map(([act, label, cls]) => `<button type="button" class="btn ${cls}" data-act="${act}">${esc(label)}</button>`).join('')}</div>
          <p class="lab-note fault"></p><p class="lab-note repeat-guide" role="status"></p><p class="lab-note biz-press" aria-live="polite"></p></section>` : ''}
        <dl class="kv lab-kv">${row(UI.t('plant.ce'), 'num ce', 'CE')}${row(UI.t('plant.fan'), 'num fan')}${row(UI.t('plant.load'), 'num load')}${row(UI.t('plant.ps1'), 'num ps1', 'PS1')}
          ${row(UI.t('plant.modes'), 'mode')}${row(UI.t('plant.phase'), 'phase')}</dl>
        <svg class="spark lab-spark" role="img" aria-label="압력 추이"></svg><p class="lab-bar-note">${esc(UI.t('plant.spark'))}</p>
        <details class="fold"><summary>자세히 · 그 밖의 값과 최근 명령</summary><div class="fold-body"><dl class="kv lab-kv">
          ${row(UI.t('plant.cp'), 'num cp', 'CP')}${row(UI.t('plant.fs1'), 'num fs1', 'FS1')}${row(UI.t('plant.vs1'), 'num vs1', 'VS1')}${row(UI.t('plant.pump'), 'num pump')}
          ${row(UI.t('plant.health'), 'num health')}${row(UI.t('plant.state'), 'plc')}${row(UI.t('plant.lastCmd'), 'ack')}</dl></div></details>
        <details class="fold unit-more"><summary>${esc(UI.t('plant.modes'))} · ${esc(UI.t('plant.manual'))}</summary><div class="fold-body">
          <p class="label">${esc(UI.t('plant.modes'))}</p>
          <div class="lab-buttons">
          <button type="button" class="btn small" data-act="mode" data-mode="REMOTE_AUTO" title="승인된 원격 명령을 설비가 수신하는 운전 모드입니다. 명령은 사람 승인 뒤에만 나갑니다.">원격 자동</button>
          <button type="button" class="btn small" data-act="mode" data-mode="REMOTE_MANUAL">원격 수동</button>
          <button type="button" class="btn small" data-act="mode" data-mode="LOCAL">현장 제어</button></div>
          <p class="label">${esc(UI.t('plant.manual'))}</p>
          <div class="lab-buttons">
          <button type="button" class="btn small" data-act="fan">팬 80 %</button>
          <button type="button" class="btn small" data-act="load">부하 70 %</button>
          <button type="button" class="btn small" data-act="reset">보호 정지 해제</button></div>
          <p class="lab-note">설비 앞 현장 패널을 흉내 낸 실습 버튼입니다. 사람 승인과 명령 관문을 거치지 않고 설비에 바로 씁니다. AI가 권고한 조치는 이 길이 아니라 처리 건 승인 뒤 명령 관문으로만 나갑니다.</p>
        </div></details>`;
      card.querySelectorAll('button').forEach(b => b.addEventListener('click', () => unitAction(asset, b.dataset.act, b.dataset.mode, b)));
      box.append(card);
    }
    const t = u.tags, s = u.status, d = (state.det && state.det.assets && state.det.assets[asset]) || {};
    const chip = unitChip(s, d), stateBox = card.querySelector('.lab-state');
    if (stateBox._markup !== chip) { stateBox.innerHTML = chip; stateBox._markup = chip; }
    card.querySelector('.mode').textContent = UI.status(s.mode);
    card.querySelector('.mode').title = s.mode === 'REMOTE_AUTO' ? '원격 자동 — 승인된 원격 명령을 설비가 수신하는 운전 모드입니다. 저절로 조치하지 않으며, 명령은 사람 승인 뒤에만 나갑니다.' : '';
    card.querySelector('.lab-temp .v').textContent = fmt(t.TS1, 1);
    const bar = card.querySelector('.lab-bar'), fill = bar.querySelector('i');
    fill.style.width = Math.max(0, Math.min(100, t.TS1)) + '%'; fill.className = tsColor(t.TS1);
    bar.setAttribute('aria-label', `유온 ${fmt(t.TS1, 1)} ℃ — 감지기 경보 기준 ${TS_HOT} ℃, 보호 정지 기준 ${TS_TRIP} ℃`);
    card.querySelector('.ce').textContent = fmt(t.CE, 0) + ' %';
    card.querySelector('.cp').textContent = fmt(t.CP, 1) + ' kW';
    card.querySelector('.fan').textContent = fmt(t.FanSpeedSP, 0) + ' %';
    card.querySelector('.load').textContent = fmt(t.LoadSP, 0) + ' %';
    card.querySelector('.ps1').textContent = fmt(t.PS1, 0) + ' bar';
    card.querySelector('.fs1').textContent = fmt(t.FS1, 1) + ' l/min';
    card.querySelector('.vs1').textContent = fmt(t.VS1, 2) + ' mm/s';
    card.querySelector('.pump').textContent = s.pump ? `${s.pump}${s.pump === 'B' ? ` (${UI.t('plant.standby')})` : ''}` : '–';
    card.querySelector('.health').textContent = fmt(s.cooler_health * 100, 0) + ' %';
    card.querySelector('.phase').textContent = phaseText(d);
    const repeat = card.querySelector('.repeat-guide');
    const guidePattern = (EXPERIMENT[asset] || {}).guide;      // 다시 주입 안내를 보일 감지기 패턴 — 결함 실험 표(EXPERIMENT)가 정한다
    if (guidePattern) {
      const phase = d.patterns?.[guidePattern]?.phase;
      repeat.textContent = !phase ? '감지기 상태를 읽지 못했습니다. 다시 주입하기 전에 연결 상태를 확인하세요.'
        : phase === 'IDLE' ? (s.cooler_health < 1 ? `쿨러 성능 ${fmt(s.cooler_health * 100, 0)} % — 유온이 기준을 넘으면 감지기가 경보를 올립니다. 새 실험은 쿨러 복구 뒤 열화 주입으로 시작합니다.`
          : '감지기가 다음 경보를 기다립니다. 새 실험은 쿨러 열화 주입으로 시작합니다.')
        : '경보가 났습니다. 처리 건의 승인 단계에서 승인하거나 반려하세요. 반려한 뒤 다시 해 보려면 [쿨러 복구]를 누르고 감지기가 대기 상태가 된 뒤 다시 주입하세요.';
    }
    card.querySelector('.plc').textContent = UI.status(s.state) + (s.trip_text ? ' · ' + s.trip_text : '');
    card.querySelector('.ack').textContent = s.cmdId ? UI.status(s.result) + (s.reason ? ' · ' + s.reason : '') : UI.t('plant.none');
    card.querySelector('.ack').title = s.cmdId ? `${s.cmdId}${s.reason ? ' · ' + s.reason : ''}` : '';
    card.querySelectorAll('[data-mode]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.mode === s.mode)));
    const dz = u.disturbances || {};
    const active = [dz.cooler_health != null && dz.cooler_health < 0.999 ? `쿨러 성능 ${fmt(dz.cooler_health * 100, 0)} %` : '', dz.leak > 0 ? `펌프 A 누설 ${fmt(dz.leak * 100, 0)} %` : '', dz.bearing_wear > 0 ? `팬 베어링 마모 ${fmt(dz.bearing_wear * 100, 0)} %` : ''].filter(Boolean);
    const ramps = (u.faults || []).map(k => FAULT_LABEL[k] || k);
    card.querySelector('.fault').textContent = (ramps.length ? `${UI.t('plant.faultOn')}: ${ramps.join(', ')}` : '') + (active.length ? `${ramps.length ? ' · ' : ''}${UI.t('plant.current')}: ${active.join(' · ')}` : '');
    sparkline(card.querySelector('.spark'), state.waves[asset], 150, 195);
    const bizAlert = card.querySelector('.biz-alert');
    const bizMarkup = bizAlertHtml(asset);
    // Preserve the link while polling so a mouse press can finish on the same node.
    if (bizAlert._renderedMarkup !== bizMarkup) {
      bizAlert.innerHTML = bizMarkup;
      bizAlert._renderedMarkup = bizMarkup;
    }
    card.querySelector('.biz-press').textContent = bizPressLine(asset);
  }
}
/* C3 B · C 단순화 — 결함 실험: 설비 카드마다 시나리오 하나(왼쪽부터 A 쿨러 · B 정기 점검 · C 재고 보충). B · C 는 설비까지 가지 않는다 —
   버튼이 처리 건을 바로 열고(POST /api/scenario/{B|C}/start), 처리가 끝나면 카드 머리의 표시(정기 점검 도래 · 재고 보충 필요)가 꺼진다.
   [초기화]는 그 시나리오의 업무 데이터를 수업 시작값으로 되돌려 표시를 다시 켠다. 표시 · 근거 값은 GET /api/scenario/status. */
const EXPERIMENT = {
  // 단추 모양(디자인 기준 5-7): 결함 · 시작 단추는 실습의 정상 동작이라 보조 단추, 초기화만 위험 모양
  'HYD-01': { title: 'A 긴급 대응', guide: 'COOLER_DEGRADATION', buttons: [['degrade', '쿨러 열화 주입', ''], ['restore', '쿨러 복구', '']] },
  'HYD-02': { title: 'B 정기 점검', key: 'B', buttons: [['biz-start', '정기 점검', ''], ['biz-reset', '초기화', 'danger']] },
  'HYD-03': { title: 'C 재고 보충', key: 'C', buttons: [['biz-start', '재고 보충', ''], ['biz-reset', '초기화', 'danger']] },
};
function bizOf(asset) {
  const key = (EXPERIMENT[asset] || {}).key;
  return key && state.biz && state.biz.scenarios ? state.biz.scenarios[key] : null;
}
// 표시 칩: 읽는 중 · 상태를 못 읽음(사유) · 처리 중 · 도래/필요 · 처리됨 · 업무 시스템 응답 없음 — 못 읽은 것을 '표시 없음'으로 보이지 않는다
function bizAlertHtml(asset) {
  if (!(EXPERIMENT[asset] || {}).key) return '';
  if (state.biz === undefined) return '<span class="chip tone-neutral">표시 확인 중…</span>';
  if (state.biz && state.biz.failed) return `<span class="chip tone-danger" title="${esc(state.biz.failed)}">표시를 읽지 못함</span>`;
  const b = bizOf(asset); if (!b) return '';
  if (b.running) return `<a href="#" class="chip tone-accent" data-open-inst="${esc(b.running.instance)}" title="처리 건 화면에서 보기">${esc(b.title)} 처리 중 →</a>`;
  // 2026-10-25 수업 한 바퀴: 거절(반려) 뒤 [초기화]를 눌러도 표시가 「반려」로 남아 초기화가 안 된 것처럼 보였다 — 마지막 처리 건이 끝난 뒤의 [초기화]면 다시 도래/필요
  const press = state.biz && state.biz.presses && state.biz.presses[asset];
  const resetAfter = press && press.button === '초기화' && b.last && b.last.ended_at && Date.parse(press.at) >= Date.parse(b.last.ended_at);
  if (b.alert && (b.last?.outcome !== '반려' || resetAfter)) return `<span class="chip tone-warning" title="${esc(bizFactLine(b))}">${esc(b.label)}</span>`;
  if (b.last && !b.running) return `<a href="#" class="chip tone-${b.last.outcome === '반려' ? 'danger' : 'success'}" data-open-inst="${esc(b.last.instance)}" title="처리 건 화면에서 보기">${b.last.outcome === '반려' ? '반려' : `처리됨${b.last.outcome ? ` · ${esc(b.last.outcome)}` : ''}`}</a>`;
  return b.error ? `<span class="chip tone-neutral" title="${esc(b.error)}">업무 시스템 응답 없음</span>` : '';
}
// 마지막 수업 버튼(감사 기록 — 처리 건이 없는 [초기화]도 여기서 보인다)
function bizPressLine(asset) {
  const p = state.biz && state.biz.presses && state.biz.presses[asset];
  return p ? `최근에 누른 단추: [${p.button}] · ${UI.time ? UI.time(p.at) : p.at}` : '';
}
function bizFactLine(b) {
  const f = b.facts || {};
  if (b.key === 'B') return `운전시간 ${fmt(f.pm_since_h, 0)} h / 주기 ${fmt(f.pm_interval_h, 0)} h — 기한까지 ${fmt(f.pm_due_in_h, 0)} h`;
  return `${f.name || f.part_no || ''} 가용 ${f.available} 개 < 재주문점 ${f.reorder_point} 개 — 필요량 ${f.need_qty} 개`;
}
document.addEventListener('click', e => {
  const a = e.target.closest('[data-open-inst]'); if (!a) return;
  e.preventDefault(); selectTab('instances'); if (window.hydInstancesSelect) window.hydInstancesSelect(a.dataset.openInst);
});
// 누가 눌렀나: 이 PC의 담당자(로그인 없음 — inbox.js me). 처리 건 기록(SCENARIO_BUTTON)과 시작 경보 근거에 남는다
function pressedBy() {
  const me = window.hydInbox && window.hydInbox.me && window.hydInbox.me();
  return { by: me ? me.name : null, user_id: me ? me.id : null, roles: me ? me.roles : [] };   // 담당자를 못 읽었으면 이름을 지어 보내지 않는다(서버가 400 으로 거절한다)
}
async function refreshBiz() {
  try { state.biz = await getJ(API.process + '/api/scenario/status'); } catch (e) { state.biz = { failed: e.message }; }
}
const anchorNote = r => r && r.reanchored === false ? ' · 시나리오 시각 기준점은 그대로(진행 중인 처리 건이 있음)' : '';
async function unitAction(asset, act, mode, button) {
  // [초기화]는 그 시나리오의 업무 데이터를 수업 시작값으로 되돌린다 — 되돌릴 수 없으므로 먼저 묻는다
  if (act === 'biz-reset' && !await UI.confirm({ title: `${EXPERIMENT[asset].title.replace(/^[A-Z]\s+/, '')} 업무 데이터를 수업 시작값으로 되돌릴까요?`, body: '이 시나리오의 업무 데이터가 수업을 시작할 때의 값으로 돌아갑니다. 이미 열린 처리 건은 그대로 남습니다.', ok: '초기화', danger: true })) return;
  if (button) button.disabled = true;
  scenarioMessage(`${asset} 처리 중…`);
  try {
    if (act === 'degrade') { const r = await postJ(API.process + '/api/scenario/A/degrade', pressedBy()); logLine(`${asset} 쿨러 열화 시작 · ${pressedBy().by} · ${UI.time(r.at)}${anchorNote(r)}`); await refreshBiz(); }
    else if (act === 'restore') { const r = await postJ(API.process + '/api/scenario/A/restore', pressedBy()); logLine(`${asset} 쿨러 복구${r.instance ? ' · 열화로 열린 처리 건에 기록' : ' · 연결된 처리 건 없음(감사 기록에 남김)'}`); await refreshBiz(); }
    else if (act === 'biz-start') {
      const exp = EXPERIMENT[asset];
      const r = await postJ(API.process + `/api/scenario/${exp.key}/start`, pressedBy());
      await refreshBiz();
      if (state.tab === 'scenario') renderUnits();
      logLine(`${asset} ${button ? button.textContent : exp.title} → 처리 건 시작 · 근거 ${exp.key === 'B' ? `운전시간 ${r.evidence.hours_since_pm} h` : `가용 ${r.evidence.available} 개`}${anchorNote(r)}`);
    }
    else if (act === 'biz-reset') {
      const exp = EXPERIMENT[asset];
      state.biz = await postJ(API.process + `/api/scenario/${exp.key}/reset`, pressedBy());
      logLine(`${asset} ${exp.title} 초기화 — 업무 데이터를 수업 시작값으로${anchorNote(state.biz)}`);
    }
    else if (act === 'mode') { await postJ(API.plant + '/api/mode', { asset, mode }); logLine(`${asset} 운전 모드 → ${UI.status(mode)}`); }
    else if (act === 'fan') { const r = await postJ(API.plant + '/api/manual', { asset, writes: { FanSpeedSP: 80 } }); logLine(`${asset} 수동 팬 80 % → ${UI.status(r.result)} ${r.reason_text || ''}`); }
    else if (act === 'load') { const r = await postJ(API.plant + '/api/manual', { asset, writes: { LoadSP: 70 } }); logLine(`${asset} 수동 부하 70 % → ${UI.status(r.result)} ${r.reason_text || ''}`); }
    else if (act === 'reset') { const r = await postJ(API.plant + '/api/manual', { asset, writes: { Reset: 1 } }); logLine(`${asset} 보호 정지 해제 → ${UI.status(r.result)} ${r.reason_text || ''}`); }
  } catch (e) { logLine('실패: ' + e.message); }
  finally { if (button) button.disabled = false; }
  refreshFast();
}
function logLine(s) { state.log.unshift(`${UI.time(new Date())}  ${s}`); state.log = state.log.slice(0, 30); if (state.tab === 'scenario') scenarioMessage(s, s.startsWith('실패:') || s.includes('REJECTED')); }
function scenarioMessage(text, failed = false) { const box = $('#scenarioMsg'); box.textContent = text; box.classList.toggle('neg', failed); }
$('#btnReset').addEventListener('click', async (e) => {
  const b = e.currentTarget;
  if (!await UI.confirm({ title: '설비 3기를 정상 운전점으로 되돌릴까요?', body: '진행 중인 결함과 보호 정지가 모두 풀립니다. 열린 처리 건은 그대로 남고, 그 처리 건의 재관측 결과가 달라질 수 있습니다.', ok: '전체 초기화', danger: true })) return;
  b.disabled = true; scenarioMessage('초기화 중…');
  try { await postJ(API.plant + '/api/reset'); logLine('전체 초기화'); scenarioMessage('설비를 정상 운전점으로 초기화했습니다.'); }
  catch (err) { scenarioMessage('초기화 실패: ' + err.message, true); }
  finally { b.disabled = false; await refreshFast(); }
});
// 2026-10-23: 화면의 배율 선택(5 · 10 · 20 · 40)은 설비 물리만 바꿔 감지 · 처리 · 에이전트(20배)와 어긋났다 — 고정 표시로 바꿨다(설비 배율 API는 지움)

// failed: 제어 게이트웨이 기록을 못 읽은 사유 — 「아직 명령 기록이 없습니다」로 보이지 않는다
function renderGwLog(entries, failed = '') {
  const box = $('#gwLog'); box.innerHTML = '';
  // 두 기록은 출처가 다르다 — 이 화면에서 누른 것과 제어 게이트웨이가 남긴 것을 이름을 붙여 나눠 보인다
  const mineRows = state.log.map(l => `<div>${esc(l)}</div>`).join('');
  const gwRows = (entries || []).slice(0, 12).map(e => UI.eventRecord({ time: e.t, name: e.ok ? '명령 검증 통과' : '명령 거절', actor: e.asset, detail: e.reason || '', raw: e })).join('');
  const mine = mineRows ? `<div class="muted">이 화면에서 누른 단추의 결과</div>${mineRows}` : '';
  const gw = gwRows ? `<div class="muted">제어 게이트웨이가 검증한 명령</div>${gwRows}` : '';
  const why = failed ? `<div class="neg" role="status">제어 게이트웨이 기록을 읽지 못했습니다: ${esc(failed)}</div>` : '';
  box.innerHTML = why + ((mine + gw) || (failed ? '' : `<div class="muted">${esc(UI.t('plant.noCmd'))}</div>`));
}


/* ---------------- 설비 회로(유압 실습장): 회로 그림 카드 + 설비 고르기. 조치 후보 · 승인은 처리 건 화면에만 있다 ----------------
   회로 그림은 홈 그림의 설비 부분과 같은 결이다(디자인 기준 6-4): 어두운 캔버스, 윤곽은 밝은 선 2px, 배관은 주황 5px(운전 중이면 흐른다),
   감지기는 빨간 원 안에 이름(TS1 · PS1), 값은 그 옆의 노란 숫자. 유온이 감지기 경보 기준을 넘으면 값이 빨강이 되고 감지기 뒤에 빛이 켜진다. 모양은 canvas.css(.hc-*) */
function unitSvg(asset) {
  // 그림 폭 328 = 카드 안 캔버스 폭(1440 화면의 세 칸)과 거의 같다 — 줄여 그려 글자가 11px 아래로 내려가지 않게 한다
  const fins = (x0, x1, y0, y1, step) => { let d = ''; for (let x = x0; x <= x1; x += step) d += `M${x} ${y0}V${y1}`; return `<path class="hc-fin" d="${d}"/>`; };
  const blade = 'M310 50 L310 41 A9 9 0 0 1 317.8 45.5 Z';
  return `<svg viewBox="0 0 328 196" role="img" aria-label="${esc(asset)} 유압 회로">
    <defs><radialGradient id="hcHot-${esc(asset)}"><stop offset="0" class="hc-hot-0"/><stop offset="1" class="hc-hot-1"/></radialGradient></defs>
    <circle class="hc-glow" cx="190" cy="80" r="40" fill="url(#hcHot-${esc(asset)})"/>
    <path class="hc-pipe" d="M106 164 H190 V135"/>
    <path class="hc-pipe flow" d="M190 106 V50 H238"/>
    <path class="hc-pipe flow ret" d="M258 72 V176 H106"/>
    <rect class="hc-steel" x="10" y="132" width="96" height="54" rx="5"/><rect class="hc-oil" x="12" y="152" width="92" height="32" rx="3"/>
    <text class="hc-cap" x="58" y="124" text-anchor="middle">탱크 <tspan class="hc-val v-ts3">–</tspan></text>
    <rect class="hc-steel" x="120" y="106" width="40" height="28" rx="5"/>${fins(128, 152, 111, 129, 8)}
    <line class="hc-shaft" x1="160" y1="120" x2="176" y2="120"/>
    <circle class="hc-steel" cx="190" cy="120" r="14"/><path class="hc-sym" d="M183 127 L190 110 L197 127 Z"/>
    <text class="hc-cap" x="174" y="100" text-anchor="end">부하 <tspan class="hc-val v-load">–</tspan></text>
    <rect class="hc-steel" x="238" y="28" width="56" height="44" rx="4"/>${fins(248, 284, 35, 65, 9)}
    <text class="hc-cap" x="294" y="88" text-anchor="middle">냉각 효율</text><text class="hc-val v-ce" x="294" y="103" text-anchor="middle">–</text>
    <g class="hc-fan"><circle class="hc-steel" cx="310" cy="50" r="11"/>
      <path class="hc-blade" d="${blade}"/><path class="hc-blade" d="${blade}" transform="rotate(120 310 50)"/><path class="hc-blade" d="${blade}" transform="rotate(240 310 50)"/></g>
    <text class="hc-cap" x="324" y="22" text-anchor="end">팬 <tspan class="hc-val v-fan">–</tspan></text>
    <g class="hc-sensor s-ts1"><circle cx="190" cy="80" r="10"/><text x="190" y="83.5" text-anchor="middle">TS1</text></g>
    <text class="hc-cap" x="174" y="84" text-anchor="end">유온 <tspan class="hc-val main v-ts1">–</tspan></text>
    <g class="hc-sensor"><circle cx="214" cy="50" r="10"/><text x="214" y="53.5" text-anchor="middle">PS1</text></g>
    <text class="hc-cap" x="230" y="32" text-anchor="end">압력 <tspan class="hc-val v-ps1">–</tspan></text>
  </svg>`;
}

function incidentsFor(asset) { return state.incidents.filter(i => i.asset === asset); }
function openIncidentFor(asset) { return incidentsFor(asset).find(i => !i.terminal) || null; }
function renderScada() {
  const box = $('#scada');
  if (!state.plant) { box.innerHTML = UI.empty(UI.t('plant.noConn'), UI.t('plant.noConnSub')); return; }
  if (!box.querySelector('.ucard')) box.innerHTML = '';
  for (const [asset, u] of Object.entries(state.plant.units)) {
    let card = box.querySelector(`[data-asset="${asset}"]`);
    if (!card) {
      card = el('div', 'ucard'); card.dataset.asset = asset; keyboardItem(card);
      card.innerHTML = `<header class="lab-head"><h2>${esc(asset)}</h2><span class="lab-state"></span></header><div class="canvas hc-canvas">${unitSvg(asset)}</div>` +
        `<p class="hc-foot"><span class="f-phase"></span><span class="f-inc"></span><span class="biz-alert"></span></p>`;
      card.addEventListener('click', () => selectAsset(asset));
      box.append(card);
    }
    const t = u.tags, s = u.status, d = (state.det && state.det.assets && state.det.assets[asset]) || {};
    const inc = openIncidentFor(asset);
    const running = s.state === 'RUN';
    card.classList.toggle('sel', state.selectedAsset === asset);
    card.classList.toggle('stopped', !running);
    card.setAttribute('aria-pressed', String(state.selectedAsset === asset));
    card.setAttribute('aria-label', `${asset} — 누르면 이 설비의 사건을 아래에 보입니다`);
    const html = (cls, markup) => { const n = card.querySelector(cls); if (n._markup !== markup) { n.innerHTML = markup; n._markup = markup; } };      // 같은 글이면 다시 그리지 않는다(누르는 동안 링크가 바뀌지 않게)
    html('.lab-state', unitChip(s, d));
    const set = (cls, v) => { card.querySelector('.' + cls).textContent = v; };
    set('v-ts1', fmt(t.TS1, 1) + ' ℃'); set('v-ts3', fmt(t.TS3, 0) + ' ℃'); set('v-ce', fmt(t.CE, 0) + ' %'); set('v-fan', fmt(t.FanSpeedSP, 0) + ' %');
    set('v-load', `${fmt(t.LoadSP, 0)} % · ${fmt(t.EPS1, 1)} kW`); set('v-ps1', fmt(t.PS1, 0) + ' bar');
    const heat = tsColor(t.TS1);                                   // '' | hot(감지기 경보 기준 이상) | trip(보호 정지 기준 이상)
    card.querySelector('.v-ts1').classList.toggle('hot', !!heat);
    card.querySelector('.s-ts1').classList.toggle('hot', !!heat);
    card.querySelector('.hc-glow').classList.toggle('on', !!heat);
    const fan = card.querySelector('.hc-fan'), spinning = running && t.FanSpeedSP > 0;
    fan.classList.toggle('stop', !spinning);
    fan.style.setProperty('--spin', (spinning ? (2.4 * 60 / Math.max(10, t.FanSpeedSP)).toFixed(2) : 2) + 's');
    html('.f-phase', `${esc(UI.t('plant.phase'))} <b>${esc(phaseText(d))}</b>`);
    card.querySelector('.f-inc').title = inc ? inc.id : (s.cmdId ? `${s.cmdId} · ${s.reason || ''}` : '');
    html('.f-inc', inc ? `${esc(UI.t('case'))} <b>${esc(UI.status(inc.state))}</b>` : (s.cmdId ? `${esc(UI.t('plant.lastCmd'))} <b>${esc(UI.status(s.result))}</b>` : ''));
    html('.biz-alert', bizAlertHtml(asset));
  }
}

async function selectAsset(asset) {
  state.selectedAsset = asset; state.showAll = false; state.incShown = UI.PAGE;
  const list = incidentsFor(asset);
  const pick = list.find(i => !i.terminal) || list[0] || null;
  state.selected = pick ? pick.id : null;
  if (!pick) { state.detail = null; state.incAudit = null; }
  renderScada(); renderIncList();
  if (pick) await loadDetail(); else renderDetail();
  $('#incDetail').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}
$('#btnAllInc').addEventListener('click', () => { state.showAll = true; state.incShown = UI.PAGE; renderIncList(); });

/* ---------------- 사건 목록 · 상세 ---------------- */
function renderIncList() {
  const box = $('#incList');
  const sig = JSON.stringify([state.selectedAsset, state.showAll, state.selected, state.incidents, state.incidentError, state.incShown]);
  if (box.dataset.sig === sig) return;
  box.dataset.sig = sig;
  const focused = box.contains(document.activeElement) ? document.activeElement.dataset.itemId : null;
  const scroll = box.scrollTop; box.innerHTML = '';
  if (state.incidentError) box.append(el('div', 'form-msg', `사건 목록을 읽지 못했습니다. ${esc(state.incidentError)}${state.incidents.length ? ' 마지막으로 읽은 목록입니다.' : ''}`));
  const filtered = (state.selectedAsset && !state.showAll) ? incidentsFor(state.selectedAsset) : state.incidents;
  const narrowed = !!state.selectedAsset && !state.showAll;
  $('#incListTitle').textContent = narrowed ? `${state.selectedAsset} ${UI.t('inc.list')} ${filtered.length}` : `${UI.t('inc.listAll')} ${state.incidents.length}`;
  $('#btnAllInc').hidden = !narrowed;      // 이미 전체를 보이고 있으면 [전체 보기]를 두지 않는다(눌러도 바뀌는 것이 없다)
  if (!filtered.length && !state.incidentError) { box.innerHTML = UI.empty(UI.t('inc.noCase'), UI.t('inc.noAlertSub'), 'compact'); }
  const paged = UI.page(filtered, state.incShown, inc => inc.id === state.selected);
  for (const inc of paged.rows) {
    const it = el('div', 'item' + (inc.id === state.selected ? ' sel' : ''));
    keyboardItem(it);
    it.dataset.itemId = inc.id;
    it.title = inc.id;   // A141: 사건 id 는 목록 글자로 보이지 않고 상세의 상세 정보 접기에서 본다
    it.innerHTML = `<div class="row"><strong>${esc(inc.asset)} · ${esc(UI.patternName((inc.card || {}).alert?.pattern) || UI.t('case'))}</strong>${UI.chip(inc.state)}</div><span class="sub">${esc(UI.t('inc.alertAt'))} ${esc(UI.dateTime(inc.created))}</span>`;
    it.addEventListener('click', () => { state.selected = inc.id; state.selectedAsset = inc.asset; renderScada(); renderIncList(); loadDetail(); });
    box.append(it);
  }
  if (paged.rest) { const more = el('div', '', UI.moreButton(paged.rest)); more.querySelector('button').addEventListener('click', () => { state.incShown += UI.PAGE; renderIncList(); }); box.append(more); }
  if (focused) [...box.children].find(e => e.dataset.itemId === focused)?.focus({ preventScroll: true });
  box.scrollTop = scroll;
}
// 사건 상세 = 사건 하나 + 그 사건의 처리 기록(서버가 사건으로 거른 감사 기록 — 전체 최근 100건에서 거르지 않는다, W2-06).
// AI 에이전트의 처리 과정은 처리 건 기록이 정본이다 — 옛 agent 실행 목록(/api/agent/runs, 지금은 판단 채점 실행만 남는다)을 읽지 않는다(W2-05 · G1-07)
async function loadDetail() {
  if (!state.selected) return;
  const selected = state.selected;
  let detail, audit;
  try {
    [detail, audit] = await Promise.all([getJ(API.process + '/api/incidents/' + encodeURIComponent(selected)),
      getJ(API.process + '/api/audit?incident=' + encodeURIComponent(selected) + '&limit=500').then(rows => ({ rows: requireList(rows, '처리 기록') }), e => ({ rows: state.incAudit?.id === selected ? state.incAudit.rows : [], error: e.message }))]);
  } catch (e) {
    if (state.selected !== selected) return;
    $('#incDetail').innerHTML = UI.errorBlock(UI.t('error.load'), e.message);
    $('#incDetail').dataset.signature = ''; state.detail = null; state.incAudit = null; return;
  }
  if (state.selected !== selected) return;
  state.detail = detail; state.incAudit = { id: selected, ...audit };
  renderDetail();
}
/* C5: the case's progress as a vertical, time-ordered card list built from inc.history (state → who → when). */
const HISTORY_WHO = { GUIDE_RECEIVED: 'sys:agent', AWAITING_APPROVAL: 'role:operator', CMD_ISSUED: 'sys:process', AWAITING_ACK: 'sys:scada', ACKED: 'sys:scada', RE_OBSERVING: 'sys:process',
  RESOLVED: 'sys:process', WORK_ORDER_CREATED: 'sys:cmms', CLOSED: 'sys:process', ESCALATED: 'role:prod-mgr', REJECTED_BY_OPERATOR: 'role:operator', RESOLVED_WITHOUT_ACTION: 'sys:process' };
function timelineHtml(inc) {
  const hist = inc.history || [];
  const fail = ['ESCALATED', 'REJECTED_BY_OPERATOR'];
  return '<ol class="hc-steps">' + hist.map((h, i) => {
    const last = i === hist.length - 1;
    const cls = fail.includes(h.state) ? 'fail' : (last && !inc.terminal) ? 'current' : 'done';
    let note = '', raw = '';
    if (h.state === 'ACKED' && inc.ack) note = `${UI.status(inc.ack.result)}${inc.ack.interlock ? ' · ' + UI.status('INTERLOCK') + ' ' + UI.status(inc.ack.interlock) : ''}${inc.ack.reason ? ' · ' + UI.logText(inc.ack.reason) : ''}`;
    else if (h.state === 'WORK_ORDER_CREATED' && inc.workOrder) note = `${inc.workOrder.ref || inc.workOrder.id || ''}${inc.workOrder.requested_value ? ' · ' + inc.workOrder.requested_value : ''}`;
    else if (h.state === 'AWAITING_APPROVAL' && inc.approvedBy) note = `${UI.t('inc.approvedBy')} ${UI.who(inc.approvedBy)}`;
    else if (h.state === 'ESCALATED' && inc.reason) note = UI.logText(inc.reason);   // 서버 사유(영문일 수 있음)는 로그 번역을 거친다(W2-15)
    else if (h.note && !/^alert |^CMD-|^WO-/.test(h.note)) { note = UI.logText(h.note); raw = note !== h.note.trim() ? h.note : ''; }   // A141: 영문 단계 기록 → 화면 문구, 원문은 접기
    // A141: 수행 주체는 보조 정보 — 카드 글자 대신 title 로만. 화면에는 단계 이름 · 시각 · 결과 한 줄
    const who = UI.who(h.state === 'AWAITING_APPROVAL' && inc.approvedBy ? inc.approvedBy : HISTORY_WHO[h.state] || 'sys:process');
    // 한 줄 = 점 · 단계 이름 · 시각, 그 아래 결과 한 줄. 점을 세로 선이 잇는다(카드로 싸지 않는다 — canvas.css .hc-steps)
    return `<li class="${cls}" title="${esc(who)}"><i></i><div><p><b>${esc(UI.status(h.state))}</b><time>${esc(UI.dateTime(h.t))}</time></p>${note ? `<p class="note">${esc(note)}</p>` : ''}` +
      `${raw ? UI.fold(esc(UI.t('log.raw')), `<pre>${esc(raw)}</pre>`) : ''}</div></li>`;
  }).join('') + '</ol>';
}
function traceHtml(run) {
  let html = `<div class="muted">${UI.chip(run.status)} ${esc(UI.t('inst.started'))} ${esc(UI.time(run.started))}${run.ended ? ' · ' + esc(UI.t('inst.ended')) + ' ' + esc(UI.time(run.ended)) : ''}${run.error ? ' · ' + esc(run.error) : ''}</div><div class="trace">`;
  for (const s of run.steps) {
    const out = s.output == null ? '' : JSON.stringify(s.output, null, 1);
    const [name, note] = UI.steps[s.name] || [s.name, s.note || ''];
    html += `<div class="step ${esc(s.status)}"><strong>${esc(name)} <span>${esc(UI.status(s.status))} · ${esc(UI.time(s.t))}</span></strong><span>${esc(note)}</span><details class="fold small"><summary>${esc(UI.t('raw'))}</summary><div class="fold-body">${out ? `<pre>${esc(out)}</pre>` : '<p class="muted">출력 데이터가 없습니다.</p>'}</div></details></div>`;
  }
  return html + '</div>';
}
function renderDetail() {
  const box = $('#incDetail');
  const inc = state.detail;
  const signature = JSON.stringify([inc, state.incAudit, state.woMsg, UI.namesVersion]);
  if (inc && box.dataset.signature === signature) return;
  box.dataset.signature = signature; box.dataset.incident = inc?.id || '';
  if (!inc) {
    if (state.selectedAsset && state.plant && state.plant.units[state.selectedAsset]) {
      // 사건이 없는 설비: 지금 값은 위 회로 그림에 있다 — 여기에 다시 적지 않는다
      box.innerHTML = `<header class="hc-detail-head"><h2>${esc(state.selectedAsset)}</h2></header>` +
        UI.emptyGo('이 설비에서 난 사건이 없습니다', UI.t('inc.noAlertSub'), 'scenario', UI.t('nav.scenario'), 'compact');
    } else {
      box.innerHTML = UI.empty(UI.t('inc.select'), UI.t('inc.selectSub'));
    }
    return;
  }
  const pattern = UI.patternName((inc.card || {}).alert?.pattern);
  // 머리: 사건 이름 + 상태 하나, 둘째 줄에 경보 시각 · 승인자 · 종결 시각. 사건 id 는 맨 아래 접기에
  const when = [`${UI.t('inc.alertAt')} ${UI.dateTime(inc.created)}`, inc.approvedBy ? `${UI.t('inc.approvedBy')} ${UI.who(inc.approvedBy)}` : '', inc.closed ? `${UI.t('closed')} ${UI.dateTime(inc.closed)}` : ''].filter(Boolean);
  let html = `<header class="hc-detail-head"><h2>${esc(inc.asset)} ${esc(UI.t('case'))}${pattern ? ' · ' + esc(pattern) : ''}</h2>${UI.chip(inc.state)}<p>${esc(when.join(' · '))}</p></header>`;
  // 원인 판단 · 조치 후보 · 승인 · 실행 결과는 이 사건의 처리 건 한 곳에 있다 — 여기에는 그리로 가는 길 하나만 둔다(사본 없음)
  html += `<div class="see-instance"><p>AI 에이전트가 판단한 원인과 조치 후보, 승인, 실행 결과는 이 사건의 처리 건에 있습니다.</p>${UI.actions('<button type="button" class="btn primary" id="btnIncInstance">이 사건의 처리 건 보기 →</button>', state.woMsg?.inc === inc.id ? state.woMsg.text : '')}</div>`;
  html += `<h3 class="hc-sec">${esc(UI.t('inc.progress'))}</h3>` + timelineHtml(inc);
  // 정비 요청 전달은 처리 건의 승인 전달이 한다 — 실패하면 그 처리 건의 「정비 요청 전달 실패」에서 같은 내용으로 다시 전달한다(instances.js)
  if (inc.workOrderRequest && !inc.workOrder) html += `<p class="kv-line">${esc(UI.t('inc.woPending'))}: ${esc(inc.workOrderRequest.item.value || inc.workOrderRequest.item.name || '')} — 전달 상태는 처리 건에서 봅니다.</p>`;
  const audit = state.incAudit?.id === inc.id ? state.incAudit.rows : [], auditError = state.incAudit?.id === inc.id ? state.incAudit.error : '';
  const auditFail = auditError ? `<div class="neg" role="status">처리 기록을 읽지 못했습니다: ${esc(auditError)}${audit.length ? ' — 마지막으로 읽은 기록입니다' : ''}</div>` : '';
  html += `<div class="hc-more">` + UI.fold(`이 사건의 감사 ${esc(UI.t('inc.log'))} ${audit.length}건 · 사건 번호`, `<dl class="kv"><dt>사건 번호</dt><dd class="mono">${esc(inc.id)}</dd></dl><div class="audit">` + auditFail +
    (audit.map(a => UI.eventRecord({ time: a.t, name: a.event, actor: a.actor, detail: a.detail?.reason || '', raw: a })).join('') || (auditFail ? '' : `<div class="muted">${esc(UI.t('empty.noData'))}</div>`)) + '</div>') + '</div>';
  box.innerHTML = html;
  // 처리 건으로 가는 단추 — 못 찾거나 실패하면 그 자리에 까닭을 남긴다
  box.querySelector('#btnIncInstance').addEventListener('click', async e => {
    const b = e.currentTarget;
    b.disabled = true; state.woMsg = null;
    try { if (!(await window.hydHitl.openIncident(inc.id))) state.woMsg = { inc: inc.id, text: '이 사건의 처리 건을 찾지 못했습니다. 메뉴 「처리 건」의 목록에서 같은 설비의 건을 여세요.' }; }
    catch (err) { state.woMsg = { inc: inc.id, text: '처리 건을 열지 못했습니다: ' + err.message }; }
    finally { b.disabled = false; if (state.woMsg) renderDetail(); }
  });
}

/* ---------------- 실시간 모니터링 ---------------- */
async function trendsNotice() {
  const n = $('#trendsNotice'); if (!n) return;
  // Grafana sends no CORS headers: an opaque (no-cors) response means reachable, a network error means it is down
  try { await fetch(P(3000) + '/api/health', { mode: 'no-cors', cache: 'no-store' }); n.hidden = true; }
  catch (e) { n.hidden = false; n.innerHTML = UI.errorBlock('그래프 서비스(Grafana)가 응답하지 않습니다', `아래 패널이 그려지지 않습니다. 지금 값은 「${tabName('scenario')}」과 「${tabName('incidents')}」 탭에서 1초마다 갱신됩니다.`); }
}
function renderTrends() {
  trendsNotice();
  const asset = $('#selAsset').value;
  const base = `${P(3000)}/d-solo/hyd-trend/hyd?orgId=1&var-asset=${asset}&refresh=5s&from=now-10m&to=now&theme=light&panelId=`;
  $('#pTs1').src = base + 7; $('#pScore').src = base + 8; $('#pCe').src = base + 9; $('#pSp').src = base + 11; $('#pAlerts').src = base + 12;
  $('#grafanaLink').href = `${P(3000)}/d/hyd-trend?orgId=1&var-asset=${asset}&refresh=5s`;
}
$('#selAsset').addEventListener('change', renderTrends);

/* ---------------- polling ---------------- */
async function refreshFast() {
  if (refreshFast.busy) return; refreshFast.busy = true;
  try {
    try {
      const plant = await getJ(API.plant + '/api/state');
      if (!plant || !plant.units || typeof plant.units !== 'object' || Array.isArray(plant.units) || Object.values(plant.units).some(u => !u?.tags || !u?.status)) throw new Error('설비 상태 응답 형식이 올바르지 않습니다.');
      state.plant = plant; state.plantError = '';
    } catch (e) { state.plant = null; state.plantError = e.message; }
    try { state.det = await getJ(API.detector + '/api/detector/state'); state.detError = ''; } catch (e) { state.det = null; state.detError = e.message; }
    if (state.plant) {
      const st = Math.floor(state.plant.sim_t);
      const simText = `${st >= 3600 ? Math.floor(st / 3600) + '시간 ' : ''}${Math.floor(st % 3600 / 60)}분 ${st % 60}초`;
      $('#simT').textContent = simText; $('#labSimT').textContent = simText;      // 위 막대의 펼침과 결함 시뮬레이션 화면 머리
      $('#scale').textContent = state.plant.time_scale;
      $('#scaleNow').textContent = state.plant.time_scale;
      // 수업은 20배 고정이다(설비 · 감지 · 처리 · 에이전트가 같은 배율로 돈다). 다르면 그 사실을 글로 보인다
      const off = Number(state.plant.time_scale) !== 20;
      $('#scaleFixed').title = off ? '' : '수업은 20배 고정입니다. 설비 · 감지 · 처리 · 에이전트가 같은 배율로 돌아야 해서 화면에서 바꾸지 않습니다';
      $('#scaleWhy').hidden = !off;
      $('#scaleWhy').textContent = off ? `수업 설정(20배)과 다릅니다. 감지 · 처리와 시간이 어긋나니 강사에게 알리세요.` : '';
      for (const [a, u] of Object.entries(state.plant.units)) {
        const arr = state.waves[a] || []; arr.push(u.tags.PS1); state.waves[a] = arr.slice(-100);
      }
    } else { $('#simT').textContent = '설비 상태 읽기 실패'; $('#labSimT').textContent = '읽기 실패'; $('#scale').textContent = '–'; }
    $('#simT').title = state.plantError || ''; $('#labSimT').title = state.plantError || '';
    if (state.tab === 'scenario') { renderUnits(); try { renderGwLog(await getJ(API.gateway + '/api/gateway/log')); } catch (e) { renderGwLog([], e.message); } }
    if (state.tab === 'incidents') renderScada();
  } finally { refreshFast.busy = false; }
}
async function refreshSlow() {
  if (refreshSlow.busy) return; refreshSlow.busy = true;
  try {
    try { state.incidents = requireList(await getJ(API.process + '/api/incidents'), '사건 목록'); state.incidentError = ''; } catch (e) { state.incidentError = e.message; }
    if (state.tab === 'scenario' || state.tab === 'incidents' || !state.biz || state.biz.failed) await refreshBiz();
    $('#openCount').textContent = state.incidentError ? '읽기 실패' : state.incidents.filter(i => !i.terminal).length;
    $('#openCount').title = state.incidentError || '';
    if (state.tab === 'incidents') { renderScada(); renderIncList(); if (state.selected) await loadDetail(); else if (state.selectedAsset) { const o = openIncidentFor(state.selectedAsset); if (o) { state.selected = o.id; await loadDetail(); } else renderDetail(); } }
  } finally { refreshSlow.busy = false; }
}
renderStack(); pollHealth(); refreshFast(); refreshSlow(); UI.loadPatterns();
setInterval(refreshFast, 1000); setInterval(refreshSlow, 2000); setInterval(pollHealth, 5000);
