/* Portal logic — plain JS, no framework, so students can read the whole flow in one file.
   Data comes straight from each service on its host port (CORS enabled); the portal container only serves files.
   A122: wording comes from UI.terms (ui.js); cards · chips · folds · empty states from the UI helpers. APIs unchanged. */
const $ = (s, r = document) => r.querySelector(s);
const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
const fmt = (v, d = 1) => (v == null || isNaN(v)) ? '–' : Number(v).toFixed(d);
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const HTTP_DEFAULT_DETAIL = { 'Not Found': '서버에 이 기능의 주소가 없습니다 — 서비스가 이 화면보다 이전 판일 수 있습니다', 'Method Not Allowed': '서버가 이 요청 방식을 받지 않습니다',
  'Internal Server Error': '서버 내부 오류', 'Bad Gateway': '중계 서버 오류', 'Service Unavailable': '서비스를 쓸 수 없는 상태입니다' };
async function requestJ(url, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), options.method ? 30000 : 8000);
  try {
    const r = await fetch(url, { cache: 'no-store', ...options, signal: controller.signal });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) {
      // 서버 프레임워크 기본 문구(영문)는 한국어 + 상태 번호로. 404 "Not Found" 는 그 주소가 없는 것 — 실행 중인 서비스가 이 화면보다 이전 판일 때 흔하다
      const detail = HTTP_DEFAULT_DETAIL[j.detail] ? `${HTTP_DEFAULT_DETAIL[j.detail]} (요청 실패 ${r.status})` : j.detail;
      const error = new Error(typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map(x => x.msg || JSON.stringify(x)).join(' · ') : typeof detail?.reason === 'string' ? detail.reason : `요청 실패 (${r.status})`);
      error.status = r.status;
      throw error;
    }
    return j;
  } catch (e) {
    if (e.name === 'AbortError') throw new Error(options.method ? '응답 시간 초과. 처리 결과를 새로 확인한 뒤 다시 시도하세요.' : '응답 시간 초과. 연결 상태를 확인하세요.');
    throw e;
  } finally { clearTimeout(timer); }
}
const getJ = url => requestJ(url);
const postJ = (url, body, method = 'POST') => requestJ(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
function keyboardItem(item) {
  item.tabIndex = 0; item.setAttribute('role', 'button');
  item.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); item.click(); } });
}

const state = { tab: 'main', plant: null, det: null, incidents: [], runs: [], selected: null, detail: null, run: null, definition: null, audit: [], waves: {}, log: [], selectedAsset: null, showAll: false, incShown: 20 };

/* ---------------- tabs ---------------- */
function selectTab(name) {
  if (!document.getElementById('view-' + name)) return;
  const changed = state.tab !== name;
  state.tab = name;
  document.querySelectorAll('.rail nav button').forEach(b => {
    const active = b.dataset.tab === name;
    b.classList.toggle('active', active);
    if (active) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current');
  });
  const brand = document.getElementById('brandHome'); if (brand) brand.classList.toggle('active', name === 'main');
  document.querySelectorAll('.view').forEach(v => v.classList.toggle('active', v.id === 'view-' + name));
  if (changed) $('main').scrollTo(0, 0);
  if (name === 'scenario') renderUnits();
  if (name === 'incidents') { renderScada(); renderIncList(); renderDetail(); }
  if (name === 'trends') renderTrends();
  updateNavigation(name);
}
document.querySelectorAll('[data-term]').forEach(n => { const t = UI.t(n.dataset.term); if (t !== n.dataset.term) n.textContent = t; });
const navButtons = [...document.querySelectorAll('.rail nav button[data-tab]')];
navButtons.forEach(b => {
  b.dataset.label = b.textContent;
  b.innerHTML = UI.icon(b.dataset.icon) + `<span>${esc(b.dataset.label)}</span>`;
  b.addEventListener('click', () => { selectTab(b.dataset.tab); $('#content').focus({ preventScroll: true }); });
});
function setMenu(open) {
  $('#navigation').classList.toggle('open', open);
  $('#menuToggle').setAttribute('aria-expanded', String(open));
  $('#menuToggle').setAttribute('aria-label', open ? '메뉴 닫기' : '메뉴 열기');
  $('#navScrim').hidden = !open;
  // Off-canvas items must not remain in the keyboard tab order.
  $('#navigation').inert = matchMedia('(max-width:720px)').matches && !open;
}
function updateNavigation(name) {
  const index = navButtons.findIndex(b => b.dataset.tab === name);
  $('#pageLocation').textContent = navButtons[index]?.dataset.label || UI.t('nav.main');
  document.title = `${$('#pageLocation').textContent} · HYD Lab`;
  const prev = navButtons[index - 1], next = navButtons[index + 1];
  for (const [id, target, direction] of [['pagePrev', prev, '이전'], ['pageNext', next, '다음']]) {
    const button = $('#' + id); if (!button) continue;
    button.disabled = !target;
    button.dataset.target = target?.dataset.tab || '';
    button.innerHTML = `<span>${direction}${direction === '다음' ? ' →' : ''}</span><b>${esc(target?.dataset.label || (direction === '이전' ? '첫 화면' : '마지막 화면'))}</b>`;
    button.setAttribute('aria-label', `${direction} 화면: ${target?.dataset.label || '없음'}`);
  }
  const count = $('#pagePosition'); if (count) count.textContent = `${index + 1} / ${navButtons.length}`;
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
    const zone = L.zone === 'mixed' ? 'it' : L.zone;
    const row = el('div', 'layer zone-' + zone + (L.focus ? ' focus' : ''));
    row.append(el('div', 'zone', `<i class="z ${zone}">${esc(zone.toUpperCase())}</i>`));            // A122: zone chip instead of the layer number (UIUX_PLAN §1.6)
    row.append(el('div', 'name', `<strong>${esc(L.name)}</strong><span>${esc(L.role)}</span>`));
    const comps = el('div', 'comps');
    for (const c of L.comps) {
      const key = c.health || c.url;
      const comp = el('div', 'comp');
      const optionalEntry = c.entryHealth || c.optional;
      comp.innerHTML = `<span class="comp-name"><i class="dot ${healthState[key] || 'unknown'}" data-h="${esc(key)}"></i><i class="z ${c.zone}">${c.zone.toUpperCase()}</i>` +
        `<a href="${c.url}" data-entry="${esc(c.url)}" target="_blank" rel="noopener"${optionalEntry ? ' title="선택 도구 — 누르면 켜져 있는지 확인하고 엽니다."' : ''}>${esc(c.name)} ↗</a></span><span class="role-desc">${esc(c.role)}` +
        (optionalEntry ? ` <span class="role" data-entry-status="${esc(c.url)}">(선택 도구)</span>` : '') + '</span>';
      if (optionalEntry) comp.querySelector('a').addEventListener('click', e => openOptional(e, c));
      comps.append(comp);
    }
    row.append(comps); stack.append(row);
  }
}
// A147: 선택 도구(FUXA · Prometheus · Redpanda Console)는 5초 상태 확인에서 뺀다. 꺼진 포트에 보내는 요청은 fetch · img · WebSocket
// 어느 방식이든 브라우저가 콘솔에 ERR_CONNECTION_REFUSED 를 남기기 때문이다(.evidence/a147/probe-methods.txt). 링크를 누를 때만
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
const PATTERN_LABEL = { COOLER_DEGRADATION: '쿨러 성능 저하', PUMP_LEAKAGE: '펌프 내부 누설', FAN_VIBRATION: '팬 진동 상승', OVER_TEMPERATURE: '유온 과열', TEMP_TRIP: '유온 보호 정지', OVERHEAT_TRIP: '유온 보호 정지' };
function phaseHtml(d) {
  // one line per detector pattern that is not idle; the cooler pattern alone when everything is quiet
  const pats = Object.entries(d.patterns || { COOLER_DEGRADATION: { phase: d.phase, alert_id: d.alert_id } });
  const busy = pats.filter(([, p]) => p.phase && p.phase !== 'IDLE');
  if (!busy.length) return UI.chip('IDLE');
  return busy.map(([code, p]) => `${UI.chip(p.phase)} <span class="muted">${esc(PATTERN_LABEL[code] || code)}</span>`).join('<br>');
}
function tsColor(t) { return t >= 65 ? 'trip' : t >= 60 ? 'hot' : ''; }
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
      card.innerHTML = `<header><strong>${asset}</strong><span class="biz-alert"></span><span class="mode"></span></header>
        <div class="big num"><span class="v"></span><small>℃ ${esc(UI.t('plant.ts1'))}</small></div>
        <div class="bar"><i></i><b style="left:65%"></b></div><div class="threshold-note">${esc(UI.t('plant.trip'))}</div>
        <div class="kv"><span>${tagLabel('plant.ce', 'CE')}</span><em class="num ce"></em><span>${tagLabel('plant.cp', 'CP')}</span><em class="num cp"></em>
          <span>${esc(UI.t('plant.fan'))}</span><em class="num fan"></em><span>${esc(UI.t('plant.load'))}</span><em class="num load"></em>
          <span>${tagLabel('plant.ps1', 'PS1')}</span><em class="num ps1"></em><span>${tagLabel('plant.fs1', 'FS1')}</span><em class="num fs1"></em>
          <span>${tagLabel('plant.vs1', 'VS1')}</span><em class="num vs1"></em><span>${esc(UI.t('plant.pump'))}</span><em class="num pump"></em>
          <span>${esc(UI.t('plant.health'))}</span><em class="num health"></em><span>${esc(UI.t('plant.phase'))}</span><em class="phase"></em>
          <span>${esc(UI.t('plant.state'))}</span><em class="plc"></em><span>${esc(UI.t('plant.lastCmd'))}</span><em class="ack"></em></div>
        <svg class="spark" role="img" aria-label="압력 추이"></svg><div class="muted">${esc(UI.t('plant.spark'))}</div>
        <div class="fault"></div>
        <div class="ctl">
          <fieldset class="ctl-group"><legend>${esc(UI.t('plant.faults'))}${EXPERIMENT[asset] ? ` · ${esc(EXPERIMENT[asset].title)}` : ''}</legend><div>
          ${(EXPERIMENT[asset] ? EXPERIMENT[asset].buttons : []).map(([act, label, cls]) => `<button class="btn ${cls}" data-act="${act}">${esc(label)}</button>`).join('\n          ')}
          </div><p class="muted small biz-press" aria-live="polite"></p></fieldset><fieldset class="ctl-group"><legend>${esc(UI.t('plant.modes'))}</legend><div>
          <button class="btn" data-act="mode" data-mode="REMOTE_AUTO">원격 자동</button>
          <button class="btn" data-act="mode" data-mode="REMOTE_MANUAL">원격 수동</button>
          <button class="btn" data-act="mode" data-mode="LOCAL">현장 제어</button>
          </div></fieldset><fieldset class="ctl-group"><legend>${esc(UI.t('plant.manual'))}</legend><div>
          <button class="btn" data-act="fan">팬 80 %</button>
          <button class="btn" data-act="load">부하 70 %</button>
          <button class="btn" data-act="reset">보호 정지 해제</button>
          </div></fieldset>
        </div>`;
      card.querySelectorAll('button').forEach(b => b.addEventListener('click', () => unitAction(asset, b.dataset.act, b.dataset.mode, b)));
      box.append(card);
    }
    const t = u.tags, s = u.status, d = (state.det && state.det.assets && state.det.assets[asset]) || {};
    card.querySelector('.mode').textContent = UI.status(s.mode);
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
    card.querySelector('.plc').innerHTML = UI.chip(s.state, UI.status(s.state) + (s.trip ? ' · ' + s.trip : ''));
    card.querySelector('.ack').textContent = s.cmdId ? UI.status(s.result) + (s.reason ? ' · ' + s.reason : '') : UI.t('plant.none');
    card.querySelector('.ack').title = s.cmdId ? `${s.cmdId}${s.reason ? ' · ' + s.reason : ''}` : '';
    card.querySelectorAll('[data-mode]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.mode === s.mode)));
    const dz = u.disturbances || {};
    const active = [dz.cooler_health != null && dz.cooler_health < 0.999 ? `쿨러 성능 ${fmt(dz.cooler_health * 100, 0)} %` : '', dz.leak > 0 ? `펌프 A 누설 ${fmt(dz.leak * 100, 0)} %` : '', dz.bearing_wear > 0 ? `팬 베어링 마모 ${fmt(dz.bearing_wear * 100, 0)} %` : ''].filter(Boolean);
    const ramps = (u.faults || []).map(k => FAULT_LABEL[k] || k);
    card.querySelector('.fault').textContent = (ramps.length ? `${UI.t('plant.faultOn')}: ${ramps.join(', ')}` : '') + (active.length ? `${ramps.length ? ' · ' : ''}${UI.t('plant.current')}: ${active.join(' · ')}` : '');
    sparkline(card.querySelector('.spark'), state.waves[asset], 150, 195);
    card.querySelector('.biz-alert').innerHTML = bizAlertHtml(asset);
    card.querySelector('.biz-press').textContent = bizPressLine(asset);
  }
}
/* C3 B · C 단순화 — 결함 실험: 설비 카드마다 시나리오 하나(왼쪽부터 A 쿨러 · B 정기 점검 · C 재고 보충). B · C 는 설비까지 가지 않는다 —
   버튼이 처리 건을 바로 열고(POST /api/scenario/{B|C}/start), 처리가 끝나면 카드 머리의 표시(정기 점검 도래 · 재고 보충 필요)가 꺼진다.
   [초기화]는 그 시나리오의 업무 데이터를 수업 시작값으로 되돌려 표시를 다시 켠다. 표시 · 근거 값은 GET /api/scenario/status. */
const EXPERIMENT = {
  'HYD-01': { title: 'A 긴급 대응', buttons: [['degrade', '쿨러 열화 주입', 'danger'], ['restore', '쿨러 복구', '']] },
  'HYD-02': { title: 'B 정기 정비', key: 'B', buttons: [['biz-start', '정기 점검', 'primary'], ['biz-reset', '초기화', '']] },
  'HYD-03': { title: 'C 예비품 구매', key: 'C', buttons: [['biz-start', '재고 보충', 'primary'], ['biz-reset', '초기화', '']] },
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
  if (b.alert) return `<span class="chip tone-warning" title="${esc(bizFactLine(b))}">${esc(b.label)}</span>`;
  if (b.alert === false && b.last) return `<a href="#" class="chip tone-success" data-open-inst="${esc(b.last.instance)}" title="처리 건 화면에서 보기">처리됨${b.last.outcome ? ` · ${esc(b.last.outcome)}` : ''}</a>`;
  return b.error ? `<span class="chip tone-neutral" title="${esc(b.error)}">업무 시스템 응답 없음</span>` : '';
}
// 마지막 수업 버튼(감사 기록 — 처리 건이 없는 [초기화]도 여기서 보인다)
function bizPressLine(asset) {
  const p = state.biz && state.biz.presses && state.biz.presses[asset];
  return p ? `마지막: [${p.button}] ${p.by} · ${UI.time ? UI.time(p.at) : p.at}` : '';
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
// 누가 눌렀나: 포털에서 고른 '나'(로그인 없음 — inbox.js). 처리 건 기록(SCENARIO_BUTTON)과 시작 경보 근거에 남는다
function pressedBy() {
  const me = window.hydInbox && window.hydInbox.me && window.hydInbox.me();
  return { by: me ? me.name : '나 미선택', user_id: me ? me.id : null, roles: me ? me.roles : [] };
}
async function refreshBiz() {
  try { state.biz = await getJ(API.process + '/api/scenario/status'); } catch (e) { state.biz = { failed: e.message }; }
}
const anchorNote = r => r && r.reanchored === false ? ' · 시나리오 시각 기준점은 그대로(진행 중인 처리 건이 있음)' : '';
async function unitAction(asset, act, mode, button) {
  if (button) button.disabled = true;
  scenarioMessage(`${asset} 처리 중…`);
  try {
    if (act === 'degrade') { const r = await postJ(API.process + '/api/scenario/A/degrade', pressedBy()); logLine(`${asset} 쿨러 열화 시작 · ${pressedBy().by} · ${UI.time(r.at)}${anchorNote(r)}`); await refreshBiz(); }
    else if (act === 'restore') { const r = await postJ(API.process + '/api/scenario/A/restore', pressedBy()); logLine(`${asset} 쿨러 복구${r.instance ? ' · 열화로 열린 처리 건에 기록' : ' · 연결된 처리 건 없음(감사 기록에 남김)'}`); await refreshBiz(); }
    else if (act === 'biz-start') {
      const exp = EXPERIMENT[asset];
      const r = await postJ(API.process + `/api/scenario/${exp.key}/start`, pressedBy());
      logLine(`${asset} ${button ? button.textContent : exp.title} → 처리 건 시작 · 근거 ${exp.key === 'B' ? `운전시간 ${r.evidence.hours_since_pm} h` : `가용 ${r.evidence.available} 개`}${anchorNote(r)}`);
      await refreshBiz();
    }
    else if (act === 'biz-reset') {
      const exp = EXPERIMENT[asset];
      state.biz = await postJ(API.process + `/api/scenario/${exp.key}/reset`, pressedBy());
      logLine(`${asset} ${exp.title} 초기화 — 업무 데이터를 수업 시작값으로${anchorNote(state.biz)}`);
    }
    else if (act === 'mode') { await postJ(API.plant + '/api/mode', { asset, mode }); logLine(`${asset} 운전 모드 → ${UI.status(mode)}`); }
    else if (act === 'fan') { const r = await postJ(API.plant + '/api/manual', { asset, writes: { FanSpeedSP: 80 } }); logLine(`${asset} 수동 팬 80 % → ${UI.status(r.result)} ${r.reason || ''}`); }
    else if (act === 'load') { const r = await postJ(API.plant + '/api/manual', { asset, writes: { LoadSP: 70 } }); logLine(`${asset} 수동 부하 70 % → ${UI.status(r.result)} ${r.reason || ''}`); }
    else if (act === 'reset') { const r = await postJ(API.plant + '/api/manual', { asset, writes: { Reset: 1 } }); logLine(`${asset} 보호 정지 해제 → ${UI.status(r.result)} ${r.reason || ''}`); }
  } catch (e) { logLine('실패: ' + e.message); }
  finally { if (button) button.disabled = false; }
  refreshFast();
}
function logLine(s) { state.log.unshift(`${new Date().toLocaleTimeString()}  ${s}`); state.log = state.log.slice(0, 30); if (state.tab === 'scenario') scenarioMessage(s, s.startsWith('실패:') || s.includes('REJECTED')); }
function scenarioMessage(text, failed = false) { const box = $('#scenarioMsg'); box.textContent = text; box.classList.toggle('neg', failed); }
$('#btnReset').addEventListener('click', async (e) => {
  const b = e.currentTarget; b.disabled = true; scenarioMessage('초기화 중…');
  try { await postJ(API.plant + '/api/reset'); logLine('전체 초기화'); scenarioMessage('설비를 정상 운전점으로 초기화했습니다.'); }
  catch (err) { scenarioMessage('초기화 실패: ' + err.message, true); }
  finally { b.disabled = false; await refreshFast(); }
});
let scaleBusy = false;
$('#selScale').addEventListener('change', async (e) => {
  const select = e.target, value = Number(select.value); scaleBusy = true; select.disabled = true;
  try { await postJ(API.plant + '/api/time_scale', { scale: value }); logLine('시간 배율 ' + value + '×'); scenarioMessage('설비 시뮬레이션 배율을 변경했습니다.'); }
  catch (err) { select.value = String(state.plant?.time_scale || 20); scenarioMessage('배율 변경 실패: ' + err.message, true); }
  finally { scaleBusy = false; select.disabled = false; await refreshFast(); }
});

function renderGwLog(entries) {
  const box = $('#gwLog'); box.innerHTML = '';
  const mine = state.log.map(l => `<div>${esc(l)}</div>`).join('');
  const gw = (entries || []).slice(0, 12).map(e => UI.eventRecord({ time: e.t, name: e.ok ? '명령 검증 통과' : '명령 거절', actor: e.asset, detail: e.reason || '', raw: e })).join('');
  box.innerHTML = (mine + gw) || `<div class="muted">${esc(UI.t('plant.noCmd'))}</div>`;
}


/* ---------------- 이상 확인 · 조치: unit schematics + selection ---------------- */
function tsColor2(t) { return t >= 65 ? '#d7263d' : t >= 55 ? '#c77700' : '#1e8e5a'; }
function unitSvg(asset) {
  const fins = [270, 279, 288, 297, 306, 315, 324].map(x => `<line class="fin" x1="${x}" y1="60" x2="${x}" y2="100"/>`).join('');
  const blade = 'M350 80 L350 66 A14 14 0 0 1 362 74 Z';
  return `<svg viewBox="0 0 400 200" role="img" aria-label="${asset} 유압 회로">
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
    <text x="310" y="143" text-anchor="middle">냉각 효율 <tspan class="v-ce">–</tspan> %</text>
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
      card = el('div', 'ucard'); card.dataset.asset = asset; card.tabIndex = 0;
      card.innerHTML = `<header><strong>${esc(asset)}</strong><span class="chips"></span></header>${unitSvg(asset)}<div class="foot"><span class="f-phase"></span><span class="f-inc"></span></div>`;
      card.addEventListener('click', () => selectAsset(asset));
      card.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectAsset(asset); } });
      box.append(card);
    }
    const t = u.tags, s = u.status, d = (state.det && state.det.assets && state.det.assets[asset]) || {};
    const inc = openIncidentFor(asset);
    const alarm = d.phase === 'RAISED' || d.phase === 'CANDIDATE' || d.phase === 'CLEARING' || s.state === 'TRIP';
    card.classList.toggle('alarm', alarm); card.classList.toggle('trip', s.state === 'TRIP'); card.classList.toggle('sel', state.selectedAsset === asset);
    card.querySelector('.chips').innerHTML = UI.chip(s.mode) + UI.chip(s.state, UI.status(s.state) + (s.trip ? ' ' + s.trip : '')) + bizAlertHtml(asset);
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
    card.querySelector('.f-phase').innerHTML = `${esc(UI.t('plant.phase'))} ${UI.chip(d.phase || 'IDLE')}`;
    card.querySelector('.f-inc').title = inc ? inc.id : (s.cmdId ? `${s.cmdId} · ${s.reason || ''}` : '');
    card.querySelector('.f-inc').innerHTML = inc ? `${esc(UI.t('case'))} ${UI.chip(inc.state)}` : (s.cmdId ? `${esc(UI.t('plant.lastCmd'))} · ${esc(UI.status(s.result))}` : esc(UI.t('inc.noAlert')));
  }
}
async function selectAsset(asset) {
  state.selectedAsset = asset; state.showAll = false; state.incShown = UI.PAGE;
  const list = incidentsFor(asset);
  const pick = list.find(i => !i.terminal) || list[0] || null;
  state.selected = pick ? pick.id : null;
  if (!pick) { state.detail = null; state.run = null; }
  renderScada(); renderIncList();
  if (pick) await loadDetail(); else renderDetail();
  const det = $('#hitlPanel'); if (det) det.scrollIntoView({ behavior: 'smooth', block: 'start' });
}
$('#btnAllInc').addEventListener('click', () => { state.showAll = true; state.incShown = UI.PAGE; renderIncList(); });

/* ---------------- 사건 목록 · 상세 ---------------- */
function renderIncList() {
  const box = $('#incList');
  const sig = JSON.stringify([state.selectedAsset, state.showAll, state.selected, state.incidents, state.runs, state.incShown]);
  if (box.dataset.sig === sig) return;
  box.dataset.sig = sig;
  const focused = box.contains(document.activeElement) ? document.activeElement.dataset.itemId : null;
  const scroll = box.scrollTop; box.innerHTML = '';
  const filtered = (state.selectedAsset && !state.showAll) ? incidentsFor(state.selectedAsset) : state.incidents;
  $('#incListTitle').textContent = (state.selectedAsset && !state.showAll) ? `${state.selectedAsset} ${UI.t('inc.list')} (${filtered.length})` : `${UI.t('inc.listAll')} (${state.incidents.length})`;
  if (!filtered.length) { box.innerHTML = UI.empty(UI.t('inc.noCase'), UI.t('inc.noAlertSub'), 'compact'); }
  const paged = UI.page(filtered, state.incShown, inc => inc.id === state.selected);
  for (const inc of paged.rows) {
    const it = el('div', 'item' + (inc.id === state.selected ? ' sel' : ''));
    keyboardItem(it);
    it.dataset.itemId = inc.id;
    it.title = inc.id;   // A141: 사건 id 는 목록 글자로 보이지 않고 상세의 상세 정보 접기에서 본다
    it.innerHTML = `<div class="row"><strong>${esc(inc.asset)} · ${esc(PATTERN_LABEL[(inc.card || {}).alert?.pattern] || UI.t('case'))}</strong>${UI.chip(inc.state)}</div><span class="sub">${esc(UI.t('inc.alertAt'))} ${esc(UI.dateTime(inc.created))}</span>`;
    it.addEventListener('click', () => { state.selected = inc.id; state.selectedAsset = inc.asset; renderScada(); renderIncList(); loadDetail(); });
    box.append(it);
  }
  // runs without incident (withheld / guardrail-rejected) are still worth seeing
  for (const r of state.runs.filter(r => !r.incidentId && r.status !== 'RUNNING' && (!state.selectedAsset || state.showAll || r.asset === state.selectedAsset))) {
    const it = el('div', 'item');
    keyboardItem(it);
    it.dataset.itemId = r.id;
    it.innerHTML = `<div class="row"><strong>${esc(r.asset)} · ${esc(UI.t('inc.runOnly'))}</strong>${UI.chip(r.status)}</div><span class="sub">${esc(UI.dateTime(r.started))}</span>`;
    it.addEventListener('click', () => { state.selected = null; state.detail = null; loadRun(r.id).then(renderDetail); });
    box.append(it);
  }
  if (paged.rest) { const more = el('div', '', UI.moreButton(paged.rest)); more.querySelector('button').addEventListener('click', () => { state.incShown += UI.PAGE; renderIncList(); }); box.append(more); }
  if (focused) [...box.children].find(e => e.dataset.itemId === focused)?.focus({ preventScroll: true });
  box.scrollTop = scroll;
}
async function loadRun(id) { try { state.run = await getJ(API.agent + '/api/agent/runs/' + id); } catch (e) { state.run = null; } }
async function loadDetail() {
  if (!state.selected) return;
  const selected = state.selected;
  try {
    const detail = await getJ(API.process + '/api/incidents/' + selected);
    const found = state.runs.find(r => r.alertId === detail.alertId);
    const run = found ? await getJ(API.agent + '/api/agent/runs/' + found.id).catch(() => null) : null;
    if (state.selected !== selected) return;
    state.detail = detail; state.run = run;
  } catch (e) {
    if (state.selected !== selected) return;
    $('#incDetail').innerHTML = `<div class="neg" role="status">${esc(UI.t('error.load'))} ${esc(e.message)}</div>`;
    $('#incDetail').dataset.signature = ''; state.detail = null; state.run = null; return;
  }
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
    else if (h.state === 'AWAITING_APPROVAL' && inc.approvedBy) note = `${UI.t('inc.approvedBy')} ${inc.approvedBy}`;
    else if (h.state === 'ESCALATED' && inc.reason) note = UI.status(inc.reason);
    else if (h.note && !/^alert |^CMD-|^WO-/.test(h.note)) { note = UI.logText(h.note); raw = note !== h.note.trim() ? h.note : ''; }   // A141: 영문 단계 기록 → 화면 문구, 원문은 접기
    // A141: 수행 주체는 보조 정보 — 카드 글자 대신 title 로만. 화면에는 단계 이름 · 시각 · 결과 한 줄
    const who = h.state === 'AWAITING_APPROVAL' && inc.approvedBy ? inc.approvedBy : UI.who(HISTORY_WHO[h.state] || 'sys:process');
    return `<div class="tl ${cls}"><span class="dot"></span>${UI.card({ title: esc(UI.status(h.state)), attrs: `title="${esc(who)}"`, sub: `<span class="meta"><span>${esc(UI.dateTime(h.t))}</span>${note ? `<span>${esc(note)}</span>` : ''}</span>`, body: raw ? UI.fold(esc(UI.t('log.raw')), `<pre>${esc(raw)}</pre>`, { cls: 'small' }) : '' })}</div>`;
  }).join('') + '</div>';
}
function traceHtml(run) {
  if (!run) return `<div class="muted">${esc(UI.t('inc.noTrace'))}</div>`;
  let html = `<div class="muted">${UI.chip(run.status)} ${esc(UI.t('inst.started'))} ${esc(UI.time(run.started))}${run.ended ? ' · ' + esc(UI.t('inst.ended')) + ' ' + esc(UI.time(run.ended)) : ''}${run.error ? ' · ' + esc(run.error) : ''}</div><div class="trace">`;
  for (const s of run.steps) {
    const out = s.output == null ? '' : JSON.stringify(s.output, null, 1);
    const [name, note] = UI.steps[s.name] || [s.name, s.note || ''];
    html += `<div class="step ${esc(s.status)}"><strong>${esc(name)} <span>${esc(UI.status(s.status))} · ${esc(UI.time(s.t))}</span></strong><span>${esc(note)}</span><details class="fold small"><summary>${esc(UI.t('raw'))}</summary><div class="fold-body">${out ? `<pre>${esc(out)}</pre>` : '<p class="muted">출력 데이터가 없습니다.</p>'}</div></details></div>`;
  }
  return html + '</div>';
}
/* 분석 근거 (C1: no summarySource · citation ids · prior probabilities on screen) */
function guideCardHtml(card) {
  if (!card) return `<div class="muted">${esc(UI.t('inc.noGuide'))}</div>`;
  let summary = card.summary;
  if (!card.summarySource || card.summarySource === 'template') {
    const top = card.causes?.[0], alert = card.alert || {};
    const pattern = PATTERN_LABEL[alert.pattern] || alert.pattern || '설비 이상';
    summary = `${alert.asset || ''} · ${pattern}.` + (top ? ` 가장 유력한 원인은 ‘${top.name}’입니다.` : '') +
      (card.recommended?.length ? ' 권장 조치: ' + card.recommended.map(a => a.name + (a.kind === 'command' ? ` ${a.value}${/_pct$/.test(a.param) ? ' %' : ''}` : '')).join(', ') + '.' : '');
  }
  let html = `<p class="prose" style="margin:0 0 var(--s3)">${esc(summary)}</p>`;
  html += `<div class="kv-line">${esc(UI.t('inc.freshness'))}: ${card.freshness && card.freshness.ok ? esc(UI.t('inc.fresh')) : esc(UI.t('inc.stale'))} (${fmt(card.freshness && card.freshness.age_s, 1)} s)</div>`;
  html += `<h4 style="margin:var(--s4) 0 var(--s2);font-size:13px">${esc(UI.t('inc.causes'))}</h4><div class="stack-list">`;
  (card.causes || []).forEach((c, i) => {
    const ev = (c.evidence || []).map(e => {
      const unknown = e.status === 'UNKNOWN' || e.passed == null || e.value == null || !!e.error;
      return `<div class="kv-line"><span class="${unknown ? 'muted' : e.passed ? 'pos' : 'neg'}">${esc(e.name)}</span> — ${unknown ? esc(UI.t('inc.unknown')) : e.passed ? esc(UI.t('inc.pass')) : esc(UI.t('inc.fail'))} · ${esc(UI.t('inc.observed'))} ${esc(fmt(e.value, 2))}${unknown ? ` <span class="muted">${esc(e.error || e.reason || '')}</span>` : ''}</div>`;
    }).join('');
    html += UI.card({ title: esc(c.name), chips: i === 0 ? UI.chipText(UI.t('dec.causeTop'), 'accent') : '', value: `<span class="kv">${esc(UI.t('card.score'))} <small></small>${fmt(c.score, 2)}</span>`, sub: esc(c.description || ''), body: ev || `<span class="muted">${esc(UI.t('inc.noEvidence'))}</span>`, cls: 'soft' });
  });
  html += `</div><h4 style="margin:var(--s4) 0 var(--s2);font-size:13px">${esc(UI.t('inc.recommended'))}</h4><div class="stack-list">`;
  for (const a of card.recommended || []) {
    let body = '';
    if (a.kind === 'command' && a.paramRange) body += `<div class="kv-line">${esc(({ fan_pct: '팬 속도', load_pct: '펌프 부하', pump: '운전 펌프' })[a.param] || a.param)} <b>${esc(a.value)}${/_pct$/.test(a.param) ? ' %' : ''}</b> · ${esc(UI.t('inc.range'))} ${a.paramRange[0]}~${a.paramRange[1]}${(a.constraints || []).length ? ` · ${esc(UI.t('inc.constraints'))}: ${(a.constraints || []).map(k => esc(k.name)).join(' · ')}` : ''}</div>`;
    if (a.sop && a.sop.steps && a.sop.steps.length) body += `<ol style="margin:var(--s2) 0 0 18px;padding:0">` + a.sop.steps.map(s => `<li>${esc(s.text)}${s.manual ? ` <span class="muted">— 매뉴얼 ${esc(s.manual.ref)} ${esc(s.manual.title)}</span>` : ''}</li>`).join('') + '</ol>';
    html += UI.card({ title: esc(a.name), chips: UI.chipText(a.kind === 'command' ? UI.t('chip.control') : UI.t('chip.workOrder'), a.kind === 'command' ? 'accent' : 'warning'), sub: a.sop ? esc(a.sop.id || '') : '', body, cls: 'soft' });
  }
  return html + '</div>';
}
function renderDetail() {
  const box = $('#incDetail');
  const inc = state.detail, run = state.run;
  const signature = JSON.stringify([inc, run, inc && state.audit.filter(a => a.incident === inc.id), UI.namesVersion]);
  if ((inc || run) && box.dataset.signature === signature) return;
  box.dataset.signature = signature; box.dataset.incident = inc?.id || '';
  if (!inc && !run) {
    if (state.selectedAsset && state.plant && state.plant.units[state.selectedAsset]) {
      const u = state.plant.units[state.selectedAsset], t = u.tags, s = u.status, d = (state.det && state.det.assets && state.det.assets[state.selectedAsset]) || {};
      box.innerHTML = `<div class="detail-head"><div class="row"><h2>${esc(state.selectedAsset)}</h2>${UI.chip(s.mode)}${UI.chip(s.state)}${UI.chip(d.phase || 'IDLE')}</div><div class="sub">${esc(UI.t('plant.ts1'))} ${fmt(t.TS1, 1)} ℃ · ${esc(UI.t('plant.ce'))} ${fmt(t.CE, 0)} % · ${esc(UI.t('plant.fan'))} ${fmt(t.FanSpeedSP, 0)} % · ${esc(UI.t('plant.load'))} ${fmt(t.LoadSP, 0)} %</div></div>` +
        UI.empty(UI.t('inc.noAlert'), UI.t('inc.noAlertSub'), 'compact');
    } else {
      box.innerHTML = UI.empty(UI.t('inc.select'), UI.t('inc.selectSub'));
    }
    return;
  }
  let html = '';
  if (inc) {
    const pattern = PATTERN_LABEL[(inc.card || {}).alert?.pattern] || '';
    // A141: 경보 · 승인자 · 종결 시각 · id 는 상세 정보 접기로
    html += `<div class="detail-head"><div class="row"><h2>${esc(inc.asset)} ${esc(UI.t('case'))}${pattern ? ' · ' + esc(pattern) : ''}</h2>${UI.chip(inc.state)}</div></div>`;
    html += UI.metaFold([[UI.t('inc.alertAt'), esc(UI.dateTime(inc.created))], [UI.t('inc.approvedBy'), esc(inc.approvedBy || '')], [UI.t('closed'), inc.closed ? esc(UI.dateTime(inc.closed)) : ''], ['ID', `<span class="mono">${esc(inc.id)}</span>`]]);
    html += `<h3 style="font-size:14px;margin:var(--s3) 0 var(--s2)">${esc(UI.t('inc.progress'))}</h3>` + timelineHtml(inc);
    if (inc.workOrderRequest && !inc.workOrder) {
      html += `<p class="kv-line">${esc(UI.t('inc.woPending'))}: ${esc(inc.workOrderRequest.item.value || inc.workOrderRequest.item.name || '')}</p>`;
      if (inc.processOwned === false && (inc.state === 'RESOLVED' || (inc.state === 'AWAITING_APPROVAL' && inc.workOrderRequest.work_order_only)))
        html += `<div class="form-actions"><button class="btn small" id="btnWorkOrderRetry">${esc(UI.t('btn.retry'))}</button></div>`;
    }
  }
  const card = (inc && inc.card) || (run && run.card);
  html += '<div class="stack-list" style="margin-top:var(--s4)">';
  html += UI.fold(esc(UI.t('inc.evidence')), guideCardHtml(card));
  html += UI.fold(esc(UI.t('inc.agentTrace')), traceHtml(run));
  if (inc) {
    const audit = state.audit.filter(a => a.incident === inc.id);
    html += UI.fold(`${esc(UI.t('inc.log'))} <span class="chip tone-neutral sm">${audit.length}</span>`, '<div class="audit">' + (audit.map(a => UI.eventRecord({ time: a.t, name: a.event, actor: a.actor, detail: a.detail?.reason || '', raw: a })).join('') || `<div class="muted">${esc(UI.t('empty.noData'))}</div>`) + '</div>');
  }
  html += '</div>';
  box.innerHTML = html;
  const wr = $('#btnWorkOrderRetry'); if (wr) wr.addEventListener('click', async () => {
    wr.disabled = true;
    try { await postJ(API.process + `/api/incidents/${encodeURIComponent(inc.id)}/work-order-retry`, {}); }
    catch (e) { alert(UI.t('workOrder') + ' 재전달 실패: ' + e.message); }
    finally { await refreshSlow(); await loadDetail(); }
  });
}

/* ---------------- 실시간 모니터링 ---------------- */
async function trendsNotice() {
  const n = $('#trendsNotice'); if (!n) return;
  // Grafana sends no CORS headers: an opaque (no-cors) response means reachable, a network error means it is down
  try { await fetch(API.grafana + '/api/health', { mode: 'no-cors', cache: 'no-store' }); n.hidden = true; }
  catch (e) { n.hidden = false; n.innerHTML = '<b>그래프 서비스가 응답하지 않습니다.</b> 센서값은 결함 시뮬레이션 · 이상 확인 화면에서 1초마다 갱신됩니다.'; }
}
function renderTrends() {
  trendsNotice();
  const asset = $('#selAsset').value;
  const base = `${API.grafana}/d-solo/hyd-trend/hyd?orgId=1&var-asset=${asset}&refresh=5s&from=now-10m&to=now&theme=light&panelId=`;
  $('#pTs1').src = base + 7; $('#pScore').src = base + 8; $('#pCe').src = base + 9; $('#pSp').src = base + 11; $('#pAlerts').src = base + 12;
  $('#grafanaLink').href = `${API.grafana}/d/hyd-trend?orgId=1&var-asset=${asset}&refresh=5s`;
}
$('#selAsset').addEventListener('change', renderTrends);

/* ---------------- polling ---------------- */
async function refreshFast() {
  if (refreshFast.busy) return; refreshFast.busy = true;
  try {
    try { state.plant = await getJ(API.plant + '/api/state'); } catch (e) { state.plant = null; }
    try { state.det = await getJ(API.detector + '/api/detector/state'); } catch (e) { state.det = null; }
    if (state.plant) {
      $('#simT').textContent = `${Math.floor(state.plant.sim_t / 60)}분 ${Math.floor(state.plant.sim_t % 60)}초`;
      $('#scale').textContent = state.plant.time_scale;
      if (!scaleBusy && document.activeElement !== $('#selScale')) $('#selScale').value = String(state.plant.time_scale);
      for (const [a, u] of Object.entries(state.plant.units)) {
        const arr = state.waves[a] || []; arr.push(u.tags.PS1); state.waves[a] = arr.slice(-100);
      }
    } else { $('#simT').textContent = '연결 끊김'; $('#scale').textContent = '–'; }
    if (state.tab === 'scenario') { renderUnits(); try { renderGwLog(await getJ(API.gateway + '/api/gateway/log')); } catch (e) { renderGwLog([]); } }
    if (state.tab === 'incidents') renderScada();
  } finally { refreshFast.busy = false; }
}
async function refreshSlow() {
  if (refreshSlow.busy) return; refreshSlow.busy = true;
  try {
    let incidentError = false;
    try { state.incidents = await getJ(API.process + '/api/incidents'); } catch (e) { incidentError = true; }
    try { state.runs = await getJ(API.agent + '/api/agent/runs'); } catch (e) { state.runs = []; }
    try { state.audit = await getJ(API.process + '/api/audit'); } catch (e) { state.audit = []; }
    if (state.tab === 'scenario' || state.tab === 'incidents' || !state.biz || state.biz.failed) await refreshBiz();
    if (!state.definition) { try { state.definition = await getJ(API.process + '/api/definition'); } catch (e) { } }
    $('#openCount').textContent = incidentError ? '–' : state.incidents.filter(i => !i.terminal).length;
    if (state.tab === 'incidents') { renderScada(); renderIncList(); if (state.selected) await loadDetail(); else if (state.selectedAsset) { const o = openIncidentFor(state.selectedAsset); if (o) { state.selected = o.id; await loadDetail(); } else renderDetail(); } }
  } finally { refreshSlow.busy = false; }
}
renderStack(); pollHealth(); refreshFast(); refreshSlow();
setInterval(refreshFast, 1000); setInterval(refreshSlow, 2000); setInterval(pollHealth, 5000);

/* ---------------- presentation hooks (used by video/record_demo.py) ---------------- */
if (new URLSearchParams(location.search).get('present') === '1') document.body.classList.add('present');
window.setCaption = (text) => { $('#caption').textContent = text || ''; };
window.hydApp = { selectTab, state, selectAsset: async (a) => { selectTab('incidents'); await refreshSlow(); await selectAsset(a); },
  selectIncident: async (id) => { state.selected = id; selectTab('incidents'); await refreshSlow(); const inc = state.incidents.find(i => i.id === id); if (inc) state.selectedAsset = inc.asset; renderScada(); renderIncList(); await loadDetail(); }, refreshSlow, refreshFast };
