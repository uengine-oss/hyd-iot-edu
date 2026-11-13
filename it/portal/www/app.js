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
function renderStack() {
  const stack = $('#stack'); stack.innerHTML = '';
  for (const L of LAYERS) {
    // 두 영역에 걸친 계층(관제 = OT + IT, 이벤트 백본 = DMZ + IT)은 걸친 영역을 모두 보인다 — IT 하나로 그리면 교재의 구조와 다르게 읽힌다
    const zones = L.zone === 'mixed' ? ['ot', 'dmz', 'it'].filter(z => L.comps.some(c => c.zone === z)) : [L.zone];
    const zone = zones[zones.length - 1];
    const row = el('div', 'layer zone-' + zone + (L.focus ? ' focus' : ''));
    row.append(el('div', 'zone', zones.map(z => `<i class="z ${z}">${esc(z.toUpperCase())}</i>`).join(' ')));            // A122: zone chip instead of the layer number (UIUX_PLAN §1)
    row.append(el('div', 'name', `<strong>${esc(L.name)}</strong><span>${esc(L.role)}</span>`));
    const comps = el('div', 'comps');
    for (const c of L.comps) {
      const key = c.health || c.url;
      const comp = el('div', 'comp');
      const optionalEntry = c.entryHealth || c.optional;
      // 상태를 재지 않는 칸(health 없음)은 회색 점을 두지 않는다 — 「꺼짐」처럼 읽힌다. 글자로 「상태 확인 대상 아님」을 붙인다
      comp.innerHTML = `<span class="comp-name">${c.health ? `<i class="dot ${healthState[key] || 'unknown'}" data-h="${esc(key)}"></i>` : ''}<i class="z ${c.zone}">${c.zone.toUpperCase()}</i>` +
        `<a href="${c.url}" data-entry="${esc(c.url)}" target="_blank" rel="noopener"${optionalEntry ? ' title="선택 도구 — 누르면 켜져 있는지 확인하고 엽니다."' : ''}>${esc(c.name)} ↗</a></span><span class="role-desc">${esc(c.role)}${c.real ? ` <span class="role">· 현업에서는 ${esc(c.real)}</span>` : ''}` +
        (optionalEntry ? ` <span class="role" data-entry-status="${esc(c.url)}">(선택 도구)</span>` : '') + (c.health ? '' : ' <span class="role">(상태 확인 대상 아님)</span>') + '</span>';
      if (optionalEntry) comp.querySelector('a').addEventListener('click', e => openOptional(e, c));
      comps.append(comp);
    }
    row.append(comps); stack.append(row);
  }
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
  if (status) status.textContent = up ? '(선택 도구)' : '(꺼짐 — 켜면 열립니다)';
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
function phaseChip(d) { return detectorUnknown() || UI.chip(worstPhase(d)); }
function phaseHtml(d) {
  if (detectorUnknown()) return detectorUnknown() + (state.detError ? ` <span class="muted">${esc(state.detError)}</span>` : '');
  // one line per detector pattern that is not idle; the cooler pattern alone when everything is quiet
  const pats = Object.entries(d.patterns || {});
  const busy = pats.filter(([, p]) => p.phase && p.phase !== 'IDLE');
  if (!busy.length) return UI.chip('IDLE');
  return busy.map(([code, p]) => `${UI.chip(p.phase)} <span class="muted">${esc(UI.patternName(code))}</span>`).join('<br>');
}
// 유온 기준 한 곳: 주의 55 ℃(감지기 경보 · 회복 기준) · 보호 정지 65 ℃ — 막대 · 회로도 전구 · 홈(main.js)이 같이 쓴다
const TS_HOT = 55, TS_TRIP = 65;
function tsColor(t) { return t >= TS_TRIP ? 'trip' : t >= TS_HOT ? 'hot' : ''; }
function sparkline(svg, values, min, max) {
  if (!values || values.length < 2) { svg.setAttribute('viewBox', '0 0 300 36'); svg.innerHTML = '<text x="0" y="24" fill="#65748b" font-size="12">압력 추이를 수집하고 있습니다…</text>'; return; }
  const w = 300, h = 36, n = values.length;
  const pts = values.map((v, i) => `${(i / Math.max(1, n - 1)) * w},${h - ((v - min) / (max - min || 1)) * (h - 4) - 2}`).join(' ');
  svg.setAttribute('viewBox', `0 0 ${w} ${h}`); svg.setAttribute('preserveAspectRatio', 'none');
  svg.innerHTML = `<polyline fill="none" stroke="#3859d6" stroke-width="2" vector-effect="non-scaling-stroke" points="${pts}"/>`;
}
const tagLabel = (term, tag) => `${esc(UI.t(term))}<small>${esc(tag)}</small>`;     // 이름 먼저, 태그 코드는 보조 (명칭표 "설비")
function renderUnits() {
  const box = $('#units');
  if (!state.plant) { box.innerHTML = UI.empty(UI.t('plant.noConn'), UI.t('plant.noConnSub')); return; }
  if (!box.querySelector('.unit')) box.innerHTML = '';
  const units = state.plant.units;
  for (const [asset, u] of Object.entries(units)) {
    let card = box.querySelector(`[data-asset="${asset}"]`);
    if (!card) {
      card = el('div', 'unit'); card.dataset.asset = asset;
      card.innerHTML = `<header><strong>${esc(asset)}</strong><span class="biz-alert"></span><span class="mode"></span></header>
        <div class="big num"><span class="v"></span><small>℃ ${esc(UI.t('plant.ts1'))}</small></div>
        <div class="bar"><i></i><b style="left:65%"></b></div><div class="threshold-note">${esc(UI.t('plant.trip'))}</div>
        <div class="fault"></div><div class="repeat-guide field-hint" role="status"></div>
        <div class="ctl">
          <fieldset class="ctl-group"><legend>${esc(UI.t('plant.faults'))}${EXPERIMENT[asset] ? ` · ${esc(EXPERIMENT[asset].title)}` : ''}</legend><div>
          ${(EXPERIMENT[asset] ? EXPERIMENT[asset].buttons : []).map(([act, label, cls]) => `<button class="btn ${cls}" data-act="${act}">${esc(label)}</button>`).join('\n          ')}
          </div><p class="muted small biz-press" aria-live="polite"></p></fieldset>
        </div>
        <div class="kv"><span>${tagLabel('plant.ce', 'CE')}</span><em class="num ce"></em><span>${tagLabel('plant.cp', 'CP')}</span><em class="num cp"></em>
          <span>${esc(UI.t('plant.fan'))}</span><em class="num fan"></em><span>${esc(UI.t('plant.load'))}</span><em class="num load"></em>
          <span>${tagLabel('plant.ps1', 'PS1')}</span><em class="num ps1"></em><span>${tagLabel('plant.fs1', 'FS1')}</span><em class="num fs1"></em>
          <span>${tagLabel('plant.vs1', 'VS1')}</span><em class="num vs1"></em><span>${esc(UI.t('plant.pump'))}</span><em class="num pump"></em>
          <span>${esc(UI.t('plant.health'))}</span><em class="num health"></em><span>${esc(UI.t('plant.phase'))}</span><em class="phase"></em>
          <span>${esc(UI.t('plant.state'))}</span><em class="plc"></em><span>${esc(UI.t('plant.lastCmd'))}</span><em class="ack"></em></div>
        <svg class="spark" role="img" aria-label="압력 추이"></svg><div class="muted">${esc(UI.t('plant.spark'))}</div>
        <details class="fold small unit-more"><summary>${esc(UI.t('plant.modes'))} · ${esc(UI.t('plant.manual'))}</summary><div class="fold-body ctl">
          <fieldset class="ctl-group"><legend>${esc(UI.t('plant.modes'))}</legend><div>
          <button class="btn" data-act="mode" data-mode="REMOTE_AUTO" title="승인된 원격 명령을 설비가 수신하는 운전 모드입니다. 명령은 사람 승인 뒤에만 나갑니다.">원격 자동</button>
          <button class="btn" data-act="mode" data-mode="REMOTE_MANUAL">원격 수동</button>
          <button class="btn" data-act="mode" data-mode="LOCAL">현장 제어</button>
          </div></fieldset><fieldset class="ctl-group"><legend>${esc(UI.t('plant.manual'))}</legend><div>
          <button class="btn" data-act="fan">팬 80 %</button>
          <button class="btn" data-act="load">부하 70 %</button>
          <button class="btn" data-act="reset">보호 정지 해제</button>
          </div></fieldset>
          <p class="field-hint">설비 앞 현장 패널을 흉내 낸 실습 버튼입니다. 사람 승인과 명령 관문을 거치지 않고 설비에 바로 씁니다. AI가 권고한 조치는 이 길이 아니라 처리 건 승인 뒤 명령 관문으로만 나갑니다.</p>
        </div></details>`;
      card.querySelectorAll('button').forEach(b => b.addEventListener('click', () => unitAction(asset, b.dataset.act, b.dataset.mode, b)));
      box.append(card);
    }
    const t = u.tags, s = u.status, d = (state.det && state.det.assets && state.det.assets[asset]) || {};
    card.querySelector('.mode').textContent = UI.status(s.mode);
    card.querySelector('.mode').title = s.mode === 'REMOTE_AUTO' ? '원격 자동 — 승인된 원격 명령을 설비가 수신하는 운전 모드입니다. 저절로 조치하지 않으며, 명령은 사람 승인 뒤에만 나갑니다.' : '';
    card.querySelector('.big .v').textContent = fmt(t.TS1, 1);
    const bar = card.querySelector('.bar i'); bar.style.width = Math.min(100, t.TS1) + '%'; bar.className = tsColor(t.TS1);
    card.querySelector('.ce').textContent = fmt(t.CE, 0) + ' %';
    card.querySelector('.cp').textContent = fmt(t.CP, 1) + ' kW';
    card.querySelector('.fan').textContent = fmt(t.FanSpeedSP, 0) + ' %';
    card.querySelector('.load').textContent = fmt(t.LoadSP, 0) + ' %';
    card.querySelector('.ps1').textContent = fmt(t.PS1, 0) + ' bar';
    card.querySelector('.fs1').textContent = fmt(t.FS1, 1) + ' l/min';
    card.querySelector('.vs1').textContent = fmt(t.VS1, 2) + ' mm/s';
    card.querySelector('.pump').textContent = s.pump ? `${s.pump}${s.pump === 'B' ? ` (${UI.t('plant.standby')})` : ''}` : '–';
    card.querySelector('.health').textContent = fmt(s.cooler_health * 100, 0) + ' %';
    card.querySelector('.phase').innerHTML = phaseHtml(d);
    const repeat = card.querySelector('.repeat-guide');
    const guidePattern = (EXPERIMENT[asset] || {}).guide;      // 다시 주입 안내를 보일 감지기 패턴 — 결함 실험 표(EXPERIMENT)가 정한다
    if (guidePattern) {
      const phase = d.patterns?.[guidePattern]?.phase;
      repeat.textContent = !phase ? '감지기 상태를 읽지 못했습니다. 다시 주입하기 전에 연결 상태를 확인하세요.'
        : phase === 'IDLE' ? (s.cooler_health < 1 ? `쿨러 성능 ${fmt(s.cooler_health * 100, 0)} % — 유온이 기준을 넘으면 감지기가 경보를 올립니다. 새 실험은 쿨러 복구 뒤 열화 주입으로 시작합니다.`
          : '감지기가 다음 경보를 기다립니다. 새 실험은 쿨러 열화 주입으로 시작합니다.')
        : '경보가 났습니다. 처리 건의 승인 단계에서 승인하거나 반려하세요. 반려한 뒤 다시 해 보려면 [쿨러 복구]를 누르고 감지기가 대기 상태가 된 뒤 다시 주입하세요.';
    }
    card.querySelector('.plc').innerHTML = UI.chip(s.state, UI.status(s.state) + (s.trip_text ? ' · ' + s.trip_text : ''));
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
  'HYD-01': { title: 'A 긴급 대응', guide: 'COOLER_DEGRADATION', buttons: [['degrade', '쿨러 열화 주입', 'danger'], ['restore', '쿨러 복구', '']] },
  'HYD-02': { title: 'B 정기 점검', key: 'B', buttons: [['biz-start', '정기 점검', 'primary'], ['biz-reset', '초기화', '']] },
  'HYD-03': { title: 'C 재고 보충', key: 'C', buttons: [['biz-start', '재고 보충', 'primary'], ['biz-reset', '초기화', '']] },
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


/* ---------------- 설비 회로(유압 실습장): 회로 그림 카드 + 설비 고르기. 조치 후보 · 승인은 처리 건 화면에만 있다 ---------------- */
function tsColor2(t) { return t >= TS_TRIP ? '#d7263d' : t >= TS_HOT ? '#c77700' : '#1e8e5a'; }
function unitSvg(asset) {
  const fins = [270, 279, 288, 297, 306, 315, 324].map(x => `<line class="fin" x1="${x}" y1="60" x2="${x}" y2="100"/>`).join('');
  const blade = 'M350 80 L350 66 A14 14 0 0 1 362 74 Z';
  return `<svg viewBox="0 0 400 200" role="img" aria-label="${esc(asset)} 유압 회로">
    <path class="pipe" d="M106 152 H170"/>
    <path class="pipe" d="M186 137 V80 H262"/>
    <path class="pipe ret" d="M297 107 V172 H106"/>
    <polygon points="186,110 181,119 191,119" fill="#4a5566"/><polygon points="297,148 292,139 302,139" fill="#7c8794"/>
    <rect class="tank" x="16" y="128" width="90" height="52" rx="4"/><rect class="oil" x="19" y="146" width="84" height="31"/>
    <text x="61" y="121" text-anchor="middle">탱크 <tspan class="v-ts3">–</tspan> ℃</text>
    <line x1="162" y1="152" x2="170" y2="152" stroke="#4a5566" stroke-width="3"/>
    <circle class="motor" cx="146" cy="152" r="16"/><text class="sym" x="146" y="156" text-anchor="middle">M</text>
    <circle class="pump" cx="186" cy="152" r="16"/><text class="sym" x="186" y="156" text-anchor="middle">P</text>
    <text x="166" y="185" text-anchor="middle">부하 <tspan class="v-load">–</tspan> % · <tspan class="v-eps">–</tspan> kW</text>
    <circle class="gauge" cx="214" cy="80" r="9"/><text x="214" y="64" text-anchor="middle">압력 <tspan class="v-ps1">–</tspan> bar</text>
    <circle class="ts1-bulb" cx="240" cy="80" r="11" fill="#1e8e5a"/><text class="sym" x="240" y="84" text-anchor="middle">T</text>
    <text class="ts1 v-ts1" x="240" y="112" text-anchor="middle">–</text>
    <rect class="cooler" x="262" y="55" width="70" height="50" rx="3"/>${fins}
    <text x="305" y="143" text-anchor="start">냉각 효율 <tspan class="v-ce">–</tspan> %</text>
    <g class="fan"><circle class="fanring" cx="350" cy="80" r="14"/>
      <path class="blade" d="${blade}"/><path class="blade" d="${blade}" transform="rotate(120 350 80)"/><path class="blade" d="${blade}" transform="rotate(240 350 80)"/></g>
    <text x="350" y="110" text-anchor="middle">팬 <tspan class="v-fan">–</tspan> %</text>
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
      card.innerHTML = `<header><strong>${esc(asset)}</strong><span class="chips"></span></header>${unitSvg(asset)}<div class="foot"><span class="f-phase"></span><span class="f-inc"></span></div>`;
      card.addEventListener('click', () => selectAsset(asset));
      box.append(card);
    }
    const t = u.tags, s = u.status, d = (state.det && state.det.assets && state.det.assets[asset]) || {};
    const inc = openIncidentFor(asset);
    const alarm = worstPhase(d) !== 'IDLE' || s.state === 'TRIP';
    card.classList.toggle('alarm', alarm); card.classList.toggle('trip', s.state === 'TRIP'); card.classList.toggle('sel', state.selectedAsset === asset);
    card.setAttribute('aria-pressed', String(state.selectedAsset === asset));
    card.querySelector('.chips').innerHTML = UI.chip(s.mode) + UI.chip(s.state, UI.status(s.state) + (s.trip_text ? ' · ' + s.trip_text : '')) + bizAlertHtml(asset);
    const set = (cls, v) => { const n = card.querySelector('.' + cls); if (n) n.textContent = v; };
    set('v-ts1', fmt(t.TS1, 1) + ' ℃'); set('v-ts3', fmt(t.TS3, 0)); set('v-ce', fmt(t.CE, 0)); set('v-fan', fmt(t.FanSpeedSP, 0));
    set('v-load', fmt(t.LoadSP, 0)); set('v-eps', fmt(t.EPS1, 1)); set('v-ps1', fmt(t.PS1, 0));
    card.querySelector('.ts1-bulb').setAttribute('fill', tsColor2(t.TS1));
    let readings = card.querySelector('.readings');
    if (!readings) { readings = el('div', 'readings'); card.querySelector('svg').after(readings); }
    readings.innerHTML = `<span>${esc(UI.t('plant.ts1'))} <b>${fmt(t.TS1, 1)} °C</b></span><span>${esc(UI.t('plant.ce'))} <b>${fmt(t.CE, 0)} %</b></span><span>${esc(UI.t('plant.ps1'))} <b>${fmt(t.PS1, 0)} bar</b></span>`;
    const fan = card.querySelector('.fan');
    const running = s.state === 'RUN' && t.FanSpeedSP > 0;
    fan.classList.toggle('stop', !running);
    fan.style.setProperty('--spin', (running ? (2.4 * 60 / Math.max(10, t.FanSpeedSP)).toFixed(2) : 2) + 's');
    card.querySelector('.f-phase').innerHTML = `${esc(UI.t('plant.phase'))} ${phaseChip(d)}`;
    card.querySelector('.f-inc').title = inc ? inc.id : (s.cmdId ? `${s.cmdId} · ${s.reason || ''}` : '');
    card.querySelector('.f-inc').innerHTML = inc ? `${esc(UI.t('case'))} ${UI.chip(inc.state)}` : (s.cmdId ? `${esc(UI.t('plant.lastCmd'))} · ${esc(UI.status(s.result))}` : esc(UI.t('inc.noAlert')));
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
  $('#incListTitle').textContent = (state.selectedAsset && !state.showAll) ? `${state.selectedAsset} ${UI.t('inc.list')} (${filtered.length})` : `${UI.t('inc.listAll')} (${state.incidents.length})`;
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
  return '<div class="timeline">' + hist.map((h, i) => {
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
    return `<div class="tl ${cls}"><span class="dot"></span>${UI.card({ title: esc(UI.status(h.state)), attrs: `title="${esc(who)}"`, sub: `<span class="meta"><span>${esc(UI.dateTime(h.t))}</span>${note ? `<span>${esc(note)}</span>` : ''}</span>`, body: raw ? UI.fold(esc(UI.t('log.raw')), `<pre>${esc(raw)}</pre>`, { cls: 'small' }) : '' })}</div>`;
  }).join('') + '</div>';
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
      const u = state.plant.units[state.selectedAsset], t = u.tags, s = u.status, d = (state.det && state.det.assets && state.det.assets[state.selectedAsset]) || {};
      box.innerHTML = `<div class="detail-head"><div class="row"><h2>${esc(state.selectedAsset)}</h2>${UI.chip(s.mode)}${UI.chip(s.state)}${phaseChip(d)}</div><div class="sub">${esc(UI.t('plant.ts1'))} ${fmt(t.TS1, 1)} ℃ · ${esc(UI.t('plant.ce'))} ${fmt(t.CE, 0)} % · ${esc(UI.t('plant.fan'))} ${fmt(t.FanSpeedSP, 0)} % · ${esc(UI.t('plant.load'))} ${fmt(t.LoadSP, 0)} %</div></div>` +
        UI.emptyGo(UI.t('inc.noAlert'), UI.t('inc.noAlertSub'), 'scenario', UI.t('nav.scenario'), 'compact');
    } else {
      box.innerHTML = UI.empty(UI.t('inc.select'), UI.t('inc.selectSub'));
    }
    return;
  }
  let html = '';
  if (inc) {
    const pattern = UI.patternName((inc.card || {}).alert?.pattern);
    // A141: 경보 · 승인자 · 종결 시각 · id 는 상세 정보 접기로
    html += `<div class="detail-head"><div class="row"><h2>${esc(inc.asset)} ${esc(UI.t('case'))}${pattern ? ' · ' + esc(pattern) : ''}</h2>${UI.chip(inc.state)}</div></div>`;
    html += UI.metaFold([[UI.t('inc.alertAt'), esc(UI.dateTime(inc.created))], [UI.t('inc.approvedBy'), esc(inc.approvedBy ? UI.who(inc.approvedBy) : '')], [UI.t('closed'), inc.closed ? esc(UI.dateTime(inc.closed)) : ''], ['ID', `<span class="mono">${esc(inc.id)}</span>`]]);
    // 원인 판단 · 조치 후보 · 승인 · 실행 결과는 이 사건의 처리 건 한 곳에 있다 — 여기에는 그리로 가는 길 하나만 둔다(사본 없음)
    html += `<div class="see-instance"><p>AI 에이전트가 판단한 원인과 조치 후보, 승인, 실행 결과는 이 사건의 처리 건에 있습니다.</p>${UI.actions('<button class="btn small primary" id="btnIncInstance">이 사건의 처리 건 보기 →</button>', state.woMsg?.inc === inc.id ? state.woMsg.text : '')}</div>`;
    html += `<h3 style="font-size:14px;margin:var(--s3) 0 var(--s2)">${esc(UI.t('inc.progress'))}</h3>` + timelineHtml(inc);
    // 정비 요청 전달은 처리 건의 승인 전달이 한다 — 실패하면 그 처리 건의 「정비 요청 전달 실패」에서 같은 내용으로 다시 전달한다(instances.js)
    if (inc.workOrderRequest && !inc.workOrder) html += `<p class="kv-line">${esc(UI.t('inc.woPending'))}: ${esc(inc.workOrderRequest.item.value || inc.workOrderRequest.item.name || '')} — 전달 상태는 처리 건에서 봅니다.</p>`;
  }
  html += '<div class="stack-list" style="margin-top:var(--s4)">';
  {
    const audit = state.incAudit?.id === inc.id ? state.incAudit.rows : [], auditError = state.incAudit?.id === inc.id ? state.incAudit.error : '';
    const auditFail = auditError ? `<div class="neg" role="status">처리 기록을 읽지 못했습니다: ${esc(auditError)}${audit.length ? ' — 마지막으로 읽은 기록입니다' : ''}</div>` : '';
    html += UI.fold(`${esc(UI.t('inc.log'))} <span class="chip tone-neutral sm">${audit.length}</span>`, '<div class="audit">' + auditFail + (audit.map(a => UI.eventRecord({ time: a.t, name: a.event, actor: a.actor, detail: a.detail?.reason || '', raw: a })).join('') || (auditFail ? '' : `<div class="muted">${esc(UI.t('empty.noData'))}</div>`)) + '</div>');
  }
  html += '</div>';
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
  catch (e) { n.hidden = false; n.innerHTML = `<b>그래프 서비스가 응답하지 않습니다.</b> 센서값은 「${esc(tabName('scenario'))}」과 「${esc(tabName('incidents'))}」 탭에서 1초마다 갱신됩니다.`; }
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
      $('#simT').textContent = `${st >= 3600 ? Math.floor(st / 3600) + '시간 ' : ''}${Math.floor(st % 3600 / 60)}분 ${st % 60}초`;
      $('#scale').textContent = state.plant.time_scale;
      $('#scaleNow').textContent = state.plant.time_scale;
      $('#scaleFixed').classList.toggle('neg', Number(state.plant.time_scale) !== 20);
      $('#scaleFixed').title = Number(state.plant.time_scale) === 20 ? '수업은 20배 고정입니다. 설비 · 감지 · 처리 · 에이전트가 같은 배율로 돌아야 해서 화면에서 바꾸지 않습니다'
        : `설비 배율이 ${state.plant.time_scale}배로 수업 설정(20배)과 다릅니다 — 감지 · 처리와 시간이 어긋납니다. 강사에게 알리세요`;
      for (const [a, u] of Object.entries(state.plant.units)) {
        const arr = state.waves[a] || []; arr.push(u.tags.PS1); state.waves[a] = arr.slice(-100);
      }
    } else { $('#simT').textContent = '설비 상태 읽기 실패'; $('#scale').textContent = '–'; }
    $('#simT').title = state.plantError || '';
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
