/* Portal logic — plain JS, no framework, so students can read the whole flow in one file.
   Data comes straight from each service on its host port (CORS enabled); the portal container only serves files. */
const $ = (s, r = document) => r.querySelector(s);
const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
const fmt = (v, d = 1) => (v == null || isNaN(v)) ? '–' : Number(v).toFixed(d);
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
async function requestJ(url, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), options.method ? 30000 : 8000);
  try {
    const r = await fetch(url, { cache: 'no-store', ...options, signal: controller.signal });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) {
      const detail = j.detail;
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

const state = { tab: 'main', plant: null, det: null, incidents: [], runs: [], selected: null, detail: null, run: null, definition: null, audit: [], waves: {}, log: [], selectedAsset: null, showAll: false };

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
const navButtons = [...document.querySelectorAll('.rail nav button[data-tab]')];
navButtons.forEach(b => {
  b.dataset.label = b.textContent;
  b.innerHTML = UI.icon(b.dataset.icon) + `<span>${esc(b.dataset.label)}</span>`;
  b.addEventListener('click', () => { selectTab(b.dataset.tab); $('#content').focus({preventScroll:true}); });
});
function setMenu(open) {
  $('#navigation').classList.toggle('open', open);
  $('#menuToggle').setAttribute('aria-expanded', String(open));
  $('#menuToggle').setAttribute('aria-label', open ? '실습 메뉴 닫기' : '실습 메뉴 열기');
  $('#navScrim').hidden = !open;
  // Off-canvas items must not remain in the keyboard tab order.
  $('#navigation').inert = matchMedia('(max-width:720px)').matches && !open;
}
function updateNavigation(name) {
  const index = navButtons.findIndex(b => b.dataset.tab === name);
  $('#pageLocation').textContent = navButtons[index]?.dataset.label || '실습 홈';
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
  if (b.dataset.target) { selectTab(b.dataset.target); $('#content').focus({preventScroll:true}); }
}));
selectTab('main');

/* ---------------- home: layer stack + health ---------------- */
const healthState = {};
function renderStack() {
  const stack = $('#stack'); stack.innerHTML = '';
  for (const L of LAYERS) {
    const row = el('div', 'layer zone-' + (L.zone === 'mixed' ? 'it' : L.zone) + (L.focus ? ' focus' : ''));
    row.append(el('div', 'no', L.no));
    row.append(el('div', 'name', `<strong>${esc(L.name)}</strong><span>${esc(L.role)}</span>`));
    const comps = el('div', 'comps');
    for (const c of L.comps) {
      const key = c.health || c.url;
      const comp = el('div', 'comp');
      const optionalEntry = c.entryHealth || c.optional;
      comp.innerHTML = `<span class="comp-name"><i class="dot ${healthState[key] || 'unknown'}" data-h="${esc(key)}"></i><i class="z ${c.zone}">${c.zone.toUpperCase()}</i>` +
        `<a ${optionalEntry ? 'role="link" aria-disabled="true"' : `href="${c.url}"`} data-entry="${esc(c.url)}" target="_blank" rel="noopener">${esc(c.name)}${optionalEntry ? '' : ' ↗'}</a></span><span class="role-desc">${esc(c.role)}` +
        (optionalEntry ? ` <span class="role" data-entry-status="${esc(c.url)}">(선택 도구 확인 중)</span>` : '') + '</span>';
      comps.append(comp);
    }
    row.append(comps); stack.append(row);
  }
}
async function pollHealth() {
  if (pollHealth.busy) return; pollHealth.busy = true;
  const dots = $('#healthDots');
  try {
  await Promise.all(LAYERS.flatMap(L => L.comps).filter(c => c.health).map(async c => {
    const key = c.health;
    const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 4000);
    try {
      if (c.health.endsWith('/healthz')) {            // our services answer JSON with CORS
        const r = await fetch(c.health, { cache: 'no-store', signal: controller.signal }); healthState[key] = r.ok ? 'up' : 'down';
      } else {                                         // third-party UIs: opaque probe = reachable
        await fetch(c.health, { mode: 'no-cors', cache: 'no-store', signal: controller.signal }); healthState[key] = 'up';
      }
    } catch (e) { healthState[key] = c.optional ? 'off' : 'down'; }
    finally { clearTimeout(timer); }
    document.querySelectorAll(`.dot[data-h="${CSS.escape(key)}"]`).forEach(d => d.className = 'dot ' + healthState[key]);
  }));
  await Promise.all(LAYERS.flatMap(L => L.comps).filter(c => c.entryHealth).map(async c => {
    const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 4000);
    try { await fetch(c.entryHealth, {mode:'no-cors', cache:'no-store', signal:controller.signal}); healthState[c.entryHealth] = 'up'; }
    catch (_) { healthState[c.entryHealth] = 'off'; }
    finally { clearTimeout(timer); }
  }));
  for (const c of LAYERS.flatMap(L => L.comps).filter(c => c.entryHealth || c.optional)) {
    const available = healthState[c.entryHealth || c.health] === 'up';
    const link = document.querySelector(`[data-entry="${CSS.escape(c.url)}"]`);
    if (!link) continue;
    if (available) { link.href = c.url; link.removeAttribute('aria-disabled'); }
    else { link.removeAttribute('href'); link.setAttribute('aria-disabled', 'true'); }
    link.textContent = c.name + (available ? ' ↗' : '');
    link.title = available ? '화면 열기' : '선택 도구를 실행하면 이 링크가 활성화됩니다.';
    document.querySelector(`[data-entry-status="${CSS.escape(c.url)}"]`).textContent = available ? '' : `(${c.entryName || '선택 도구'} 미실행)`;
  }
  const all = LAYERS.flatMap(L => L.comps).filter(c => c.health && !(c.optional && healthState[c.health] === 'off'));
  const down = all.filter(c => healthState[c.health] === 'down');
  dots.innerHTML = `<span title="앱 healthz와 외부 UI 연결 응답입니다. 전체 파이프라인의 성공을 뜻하지 않습니다."><i class="dot ${down.length ? 'down' : 'up'}"></i>구성요소 ${all.length - down.length}/${all.length} 응답${down.length ? ' — 응답 없음: ' + esc(down.map(c => c.name.split(' ')[0]).join(', ')) : ''}</span>`;
  } finally { pollHealth.busy = false; }
}

/* ---------------- scenario ---------------- */
const FAULT_LABEL = { cooler_degradation: '쿨러 성능 저하', pump_leakage: '펌프 내부 누설', fan_vibration: '팬 베어링 마모', restore: '복구' };
const PATTERN_LABEL = { COOLER_DEGRADATION: '쿨러 성능 저하', PUMP_LEAKAGE: '펌프 내부 누설', FAN_VIBRATION: '팬 진동 상승', OVER_TEMPERATURE: '유온 과열', TEMP_TRIP: '유온 보호 정지', OVERHEAT_TRIP: '유온 보호 정지' };
function phaseHtml(d) {
  // one line per CEP pattern that is not idle; the cooler pattern alone when everything is quiet
  const pats = Object.entries(d.patterns || { COOLER_DEGRADATION: { phase: d.phase, alert_id: d.alert_id } });
  const busy = pats.filter(([, p]) => p.phase && p.phase !== 'IDLE');
  if (!busy.length) return `<span class="state IDLE">${UI.status('IDLE')}</span>`;
  return busy.map(([code, p]) => `<span class="state ${esc(p.phase)}">${UI.status(p.phase)}</span> <span class="muted">${esc(PATTERN_LABEL[code] || code)}${p.alert_id ? ' · ' + esc(p.alert_id) : ''}</span>`).join('<br>');
}
function tsColor(t) { return t >= 65 ? 'trip' : t >= 60 ? 'hot' : ''; }
function sparkline(svg, values, min, max) {
  if (!values || values.length < 2) { svg.setAttribute('viewBox','0 0 300 36'); svg.innerHTML = '<text x="0" y="24" fill="#65748b" font-size="12">압력 추이를 수집하고 있습니다…</text>'; return; }
  const w = 300, h = 36, n = values.length;
  const pts = values.map((v, i) => `${(i / Math.max(1, n - 1)) * w},${h - ((v - min) / (max - min || 1)) * (h - 4) - 2}`).join(' ');
  svg.setAttribute('viewBox', `0 0 ${w} ${h}`); svg.setAttribute('preserveAspectRatio', 'none');
  svg.innerHTML = `<polyline fill="none" stroke="#3859d6" stroke-width="2" vector-effect="non-scaling-stroke" points="${pts}"/>`;
}
function renderUnits() {
  const box = $('#units');
  if (!state.plant) { box.innerHTML = '<div class="muted">설비 시뮬레이터와 연결이 끊겼습니다. 서비스 연결을 확인하세요. 연결되면 자동으로 다시 표시됩니다.</div>'; return; }
  if (!box.querySelector('.unit')) box.innerHTML = '';
  const units = state.plant.units;
  for (const [asset, u] of Object.entries(units)) {
    let card = box.querySelector(`[data-asset="${asset}"]`);
    if (!card) {
      card = el('div', 'unit'); card.dataset.asset = asset;
      card.innerHTML = `<header><strong>${asset}</strong><span class="mode"></span></header>
        <div class="big num"><span class="v"></span><small>℃ 유온 TS1</small></div>
        <div class="bar"><i></i><b style="left:65%"></b></div><div class="threshold-note">보호 정지 기준 65 °C</div>
        <div class="kv"><span>냉각 효율 CE</span><em class="num ce"></em><span>냉각 능력 CP</span><em class="num cp"></em>
          <span>팬 속도 SP</span><em class="num fan"></em><span>펌프 부하 SP</span><em class="num load"></em>
          <span>토출 압력 PS1</span><em class="num ps1"></em><span>유량 FS1</span><em class="num fs1"></em>
          <span>팬 진동 VS1</span><em class="num vs1"></em><span>운전 펌프</span><em class="num pump"></em>
          <span>쿨러 성능 비율</span><em class="num health"></em><span>탐지 단계</span><em class="phase"></em>
          <span>PLC 상태</span><em class="plc"></em><span>최근 명령 결과</span><em class="ack"></em></div>
        <svg class="spark" role="img" aria-label="PS1 압력 추이"></svg><div class="muted">PS1 압력 추이 · 화면에서 1초 간격 수집</div>
        <div class="fault"></div>
        <div class="ctl">
          <fieldset class="ctl-group"><legend>결함 실험 · 300 sim-s 동안 서서히 진행</legend><div>
          <button class="btn danger" data-act="degrade">쿨러 열화 주입</button>
          <button class="btn danger" data-act="leak">펌프 누설 주입</button>
          <button class="btn danger" data-act="wear">팬 베어링 마모 주입</button>
          <button class="btn" data-act="restore">결함 복구</button>
          </div></fieldset><fieldset class="ctl-group"><legend>운전 모드</legend><div>
          <button class="btn" data-act="mode" data-mode="REMOTE_AUTO">원격 자동</button>
          <button class="btn" data-act="mode" data-mode="REMOTE_MANUAL">원격 수동</button>
          <button class="btn" data-act="mode" data-mode="LOCAL">현장 제어</button>
          </div></fieldset><fieldset class="ctl-group"><legend>수동 조작 · 적용 시 원격 수동으로 전환</legend><div>
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
    card.querySelector('.pump').textContent = s.pump ? `${s.pump}${s.pump === 'B' ? ' (예비)' : ''}` : '–';
    card.querySelector('.health').textContent = fmt(s.cooler_health * 100, 0) + ' %';
    card.querySelector('.phase').innerHTML = phaseHtml(d);
    card.querySelector('.plc').innerHTML = `<span class="state ${s.state}">${UI.status(s.state)}${s.trip ? ' · ' + s.trip : ''}</span>`;
    card.querySelector('.ack').textContent = s.cmdId ? UI.status(s.result) + (s.reason ? ' · ' + s.reason : '') : '아직 없음';
    card.querySelector('.ack').title = s.cmdId ? `${s.cmdId}${s.reason ? ' · ' + s.reason : ''}` : '';
    card.querySelectorAll('[data-mode]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.mode === s.mode)));
    const dz = u.disturbances || {};
    const active = [dz.cooler_health != null && dz.cooler_health < 0.999 ? `쿨러 성능 ${fmt(dz.cooler_health * 100, 0)} %` : '', dz.leak > 0 ? `펌프 A 누설 ${fmt(dz.leak * 100, 0)} %` : '', dz.bearing_wear > 0 ? `팬 베어링 마모 ${fmt(dz.bearing_wear * 100, 0)} %` : ''].filter(Boolean);
    const ramps = (u.faults || []).map(k => FAULT_LABEL[k] || k);
    card.querySelector('.fault').textContent = (ramps.length ? `결함 진행 중: ${ramps.join(', ')}` : '') + (active.length ? `${ramps.length ? ' · ' : ''}현재 상태: ${active.join(' · ')}` : '');
    sparkline(card.querySelector('.spark'), state.waves[asset], 150, 195);
  }
}
async function unitAction(asset, act, mode, button) {
  if (button) button.disabled = true;
  scenarioMessage(`${asset} 처리 중…`);
  try {
    if (act === 'degrade') { await postJ(API.plant + '/api/fault', { asset, type: 'cooler_degradation' }); logLine(`${asset} 쿨러 열화 주입 (health → 0.43, 300 sim-s 램프)`); }
    else if (act === 'leak') { await postJ(API.plant + '/api/fault', { asset, type: 'pump_leakage' }); logLine(`${asset} 펌프 A 내부 누설 주입 (누설 → 15 %, 300 sim-s 램프) · PS1·FS1 하락`); }
    else if (act === 'wear') { await postJ(API.plant + '/api/fault', { asset, type: 'fan_vibration' }); logLine(`${asset} 팬 베어링 마모 주입 (마모 → 80 %, 300 sim-s 램프) · VS1 상승`); }
    else if (act === 'restore') { await postJ(API.plant + '/api/fault', { asset, type: 'restore', ramp_sim_s: 60 }); logLine(`${asset} 결함 복구 (쿨러·누설·베어링 모두 정상으로)`); }
    else if (act === 'mode') { await postJ(API.plant + '/api/mode', { asset, mode }); logLine(`${asset} 현장 패널: 모드 → ${mode}`); }
    else if (act === 'fan') { const r = await postJ(API.plant + '/api/manual', { asset, writes: { FanSpeedSP: 80 } }); logLine(`${asset} 수동 팬 80 % → ${r.result} ${r.reason || ''}`); }
    else if (act === 'load') { const r = await postJ(API.plant + '/api/manual', { asset, writes: { LoadSP: 70 } }); logLine(`${asset} 수동 부하 70 % → ${r.result} ${r.reason || ''}`); }
    else if (act === 'reset') { const r = await postJ(API.plant + '/api/manual', { asset, writes: { Reset: 1 } }); logLine(`${asset} RESET → ${r.result} ${r.reason || ''}`); }
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
  const gw = (entries || []).slice(0, 12).map(e => UI.eventRecord({time:e.t,name:e.ok ? '명령 검증 통과' : '명령 거절',actor:e.asset,detail:e.reason || '',raw:e})).join('');
  box.innerHTML = (mine + gw) || '<div class="muted">아직 명령 기록이 없습니다.</div>';
}


/* ---------------- 설비 SCADA: unit schematics + selection ---------------- */
const STATE_LABEL = UI.states;
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
    <text x="61" y="121" text-anchor="middle">탱크 · TS3 <tspan class="v-ts3">–</tspan> ℃</text>
    <line x1="162" y1="152" x2="170" y2="152" stroke="#4a5566" stroke-width="3"/>
    <circle class="motor" cx="146" cy="152" r="16"/><text class="sym" x="146" y="156" text-anchor="middle">M</text>
    <circle class="pump" cx="186" cy="152" r="16"/><text class="sym" x="186" y="156" text-anchor="middle">P</text>
    <text x="166" y="185" text-anchor="middle">부하 <tspan class="v-load">–</tspan> % · <tspan class="v-eps">–</tspan> kW</text>
    <circle class="gauge" cx="214" cy="80" r="9"/><text x="214" y="64" text-anchor="middle">PS1 <tspan class="v-ps1">–</tspan> bar</text>
    <circle class="ts1-bulb" cx="240" cy="80" r="11" fill="#1e8e5a"/><text class="sym" x="240" y="84" text-anchor="middle">T</text>
    <text class="ts1 v-ts1" x="240" y="112" text-anchor="middle">–</text>
    <rect class="cooler" x="262" y="55" width="70" height="50" rx="3"/>${fins}
    <text x="310" y="143" text-anchor="middle">쿨러 CE <tspan class="v-ce">–</tspan> %</text>
    <g class="fan"><circle class="fanring" cx="350" cy="80" r="14"/>
      <path class="blade" d="${blade}"/><path class="blade" d="${blade}" transform="rotate(120 350 80)"/><path class="blade" d="${blade}" transform="rotate(240 350 80)"/></g>
    <text x="350" y="110" text-anchor="middle">팬 <tspan class="v-fan">–</tspan> %</text>
  </svg>`;
}
function incidentsFor(asset) { return state.incidents.filter(i => i.asset === asset); }
function openIncidentFor(asset) { return incidentsFor(asset).find(i => !i.terminal) || null; }
function renderScada() {
  const box = $('#scada');
  if (!state.plant) { box.innerHTML = '<div class="muted">설비 시뮬레이터에 연결할 수 없습니다. 연결 상태를 확인해 주세요.</div>'; return; }
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
    const modeCls = s.mode === 'REMOTE_AUTO' ? 'auto' : s.mode === 'REMOTE_MANUAL' ? 'manual' : 'local';
    card.querySelector('.chips').innerHTML = `<span class="chip ${modeCls}" title="${esc(s.mode)}">${esc(UI.status(s.mode))}</span><span class="chip ${s.state === 'TRIP' ? 'trip' : 'run'}" title="${esc(s.state)}">${esc(UI.status(s.state))}${s.trip ? ' ' + esc(s.trip) : ''}</span>`
      + (inc ? `<span class="chip inc">${esc(STATE_LABEL[inc.state] || inc.state)}</span>` : '');
    const set = (cls, v) => { const n = card.querySelector('.' + cls); if (n) n.textContent = v; };
    set('v-ts1', fmt(t.TS1, 1) + ' ℃'); set('v-ts3', fmt(t.TS3, 0)); set('v-ce', fmt(t.CE, 0)); set('v-fan', fmt(t.FanSpeedSP, 0));
    set('v-load', fmt(t.LoadSP, 0)); set('v-eps', fmt(t.EPS1, 1)); set('v-ps1', fmt(t.PS1, 0));
    card.querySelector('.ts1-bulb').setAttribute('fill', tsColor2(t.TS1));
    let readings = card.querySelector('.readings');
    if (!readings) { readings = el('div','readings'); card.querySelector('svg').after(readings); }
    readings.innerHTML = `<span>유온 <b>${fmt(t.TS1,1)} °C</b></span><span>냉각 효율 <b>${fmt(t.CE,0)} %</b></span><span>압력 <b>${fmt(t.PS1,0)} bar</b></span>`;
    const fan = card.querySelector('.fan');
    const running = s.state === 'RUN' && t.FanSpeedSP > 0;
    fan.classList.toggle('stop', !running);
    fan.style.setProperty('--spin', (running ? (2.4 * 60 / Math.max(10, t.FanSpeedSP)).toFixed(2) : 2) + 's');
    card.querySelector('.f-phase').innerHTML = `탐지 <span class="chip ${(d.phase || 'idle').toLowerCase()}" title="${esc(d.phase)}">${esc(UI.status(d.phase))}</span>${d.alert_id ? ' ' + esc(d.alert_id) : ''}`;
    card.querySelector('.f-inc').title = s.cmdId ? `${s.cmdId} · ${s.reason || ''}` : '';
    card.querySelector('.f-inc').textContent = inc ? `${inc.id} · ${STATE_LABEL[inc.state] || inc.state}` : (s.cmdId ? `최근 명령 · ${UI.status(s.result)}` : '경보 없음');
  }
}
async function selectAsset(asset) {
  state.selectedAsset = asset; state.showAll = false;
  const list = incidentsFor(asset);
  const pick = list.find(i => !i.terminal) || list[0] || null;
  state.selected = pick ? pick.id : null;
  if (!pick) { state.detail = null; state.run = null; }
  renderScada(); renderIncList();
  if (pick) await loadDetail(); else renderDetail();
  const det = $('#hitlPanel'); if (det) det.scrollIntoView({ behavior: 'smooth', block: 'start' });
}
$('#btnAllInc').addEventListener('click', () => { state.showAll = true; renderIncList(); });

/* ---------------- incidents ---------------- */
function renderIncList() {
  const box = $('#incList');
  const sig = JSON.stringify([state.selectedAsset, state.showAll, state.selected, state.incidents, state.runs]);
  if (box.dataset.sig === sig) return;
  box.dataset.sig = sig;
  const focused = box.contains(document.activeElement) ? document.activeElement.dataset.itemId : null;
  const scroll = box.scrollTop; box.innerHTML = '';
  const filtered = (state.selectedAsset && !state.showAll) ? incidentsFor(state.selectedAsset) : state.incidents;
  $('#incListTitle').textContent = (state.selectedAsset && !state.showAll) ? `${state.selectedAsset} 인시던트 (${filtered.length})` : `전체 인시던트 (${state.incidents.length})`;
  if (!filtered.length) { box.innerHTML = `<div class="muted">${state.selectedAsset && !state.showAll ? state.selectedAsset + ' 인시던트가 없습니다.' : '인시던트가 없습니다. 결함 시뮬레이션에서 쿨러 열화를 주입해 보세요.'}</div>`; }
  for (const inc of filtered) {
    const it = el('div', 'item' + (inc.id === state.selected ? ' sel' : ''));
    keyboardItem(it);
    it.dataset.itemId = inc.id;
    it.innerHTML = `<strong>${esc(inc.id)} <span class="pill ${esc(inc.state)}">${esc(UI.status(inc.state))}</span></strong><span>${esc(inc.asset)} · ${esc(inc.alertId)} · ${esc(UI.time(inc.created))}</span>`;
    it.addEventListener('click', () => { state.selected = inc.id; state.selectedAsset = inc.asset; renderScada(); renderIncList(); loadDetail(); });
    box.append(it);
  }
  // runs without incident (withheld / guardrail-rejected) are still worth seeing
  for (const r of state.runs.filter(r => !r.incidentId && r.status !== 'RUNNING' && (!state.selectedAsset || state.showAll || r.asset === state.selectedAsset))) {
    const it = el('div', 'item');
    keyboardItem(it);
    it.dataset.itemId = r.id;
    it.innerHTML = `<strong>${esc(r.id)} <span class="pill ESCALATED">${esc(UI.status(r.status))}</span></strong><span>${esc(r.asset)} · ${esc(r.alertId)} · 에이전트 실행만 있음</span>`;
    it.addEventListener('click', () => { state.selected = null; state.detail = null; loadRun(r.id).then(renderDetail); });
    box.append(it);
  }
  if (focused) [...box.children].find(e => e.dataset.itemId === focused)?.focus({preventScroll:true});
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
    $('#incDetail').innerHTML = `<div class="neg" role="status">상세를 불러오지 못했습니다. ${esc(e.message)}</div>`;
    $('#incDetail').dataset.signature = ''; state.detail = null; state.run = null; return;
  }
  renderDetail();
}
function lane(inc) {
  const def = state.definition; if (!def) return '';
  const done = new Set((inc.history || []).map(h => h.state));
  const cur = inc.state;
  const fail = def.failure.find(f => f.id === cur);
  let html = '<div class="lane">';
  for (const s of def.steps) {
    const cls = s.id === cur ? 'now' : done.has(s.id) ? 'done' : '';
    const h = (inc.history || []).find(x => x.state === s.id);
    html += `<div class="st ${cls}">${esc(s.label)}<small>${esc(({startEvent:'시작',endEvent:'종료',userTask:'사람의 확인',serviceTask:'시스템 처리',exclusiveGateway:'조건 분기',intermediateCatchEvent:'응답 대기'})[s.type] || s.type)}${h ? ' · ' + UI.time(h.t) : ''}</small></div>`;
  }
  html += '</div>';
  if (fail) html += `<div class="st fail" style="display:inline-block;padding:6px 10px;border-radius:4px;font-size:12px">${esc(fail.label)}${inc.reason ? ' — ' + esc(inc.reason) : ''}</div>`;
  return html;
}
function traceHtml(run) {
  if (!run) return '<div class="muted">이 경보의 에이전트 실행 기록이 없습니다.</div>';
  let html = `<div class="muted">${esc(run.id)} · ${esc(UI.status(run.status))} · 시작 ${esc(UI.time(run.started))}${run.ended ? ' · 종료 ' + esc(UI.time(run.ended)) : ''}${run.error ? ' · ' + esc(run.error) : ''}</div><div class="trace">`;
  for (const s of run.steps) {
    const out = s.output == null ? '' : JSON.stringify(s.output, null, 1);
    const [name, note] = UI.steps[s.name] || [s.name, s.note || ''];
    html += `<div class="step ${esc(s.status)}"><strong>${esc(name)} <span>${esc(UI.status(s.status))} · ${esc(UI.time(s.t))}</span></strong><span>${esc(note)}</span><details><summary>처리 기록과 출력 데이터</summary><p>${esc(s.name)}${s.note ? ' · ' + esc(s.note) : ''}</p>${out ? `<pre>${esc(out)}</pre>` : '<p>출력 데이터가 없습니다.</p>'}</details></div>`;
  }
  return html + '</div>';
}
function cardHtml(card, editable) {
  if (!card) return '<div class="muted">아직 조치 가이드가 없습니다.</div>';
  let summary = card.summary;
  if (!card.summarySource || card.summarySource === 'template') {
    const top = card.causes?.[0], alert = card.alert || {};
    const pattern = PATTERN_LABEL[alert.pattern] || alert.pattern || '설비 이상';
    summary = `${alert.asset || ''} · ${pattern}.` + (top ? ` 가장 유력한 원인은 ‘${top.name}’입니다 (점수 ${fmt(top.score,2)}).` : '') +
      (card.recommended?.length ? ' 권장 조치: ' + card.recommended.map(a => a.name + (a.kind === 'command' ? ` ${a.value}${/_pct$/.test(a.param) ? ' %' : ''}` : '')).join(', ') + '.' : '');
  }
  let html = `<div class="summary">${esc(summary)} <span class="muted">${card.summarySource && card.summarySource !== 'template' ? 'AI 요약' : '규칙 기반 요약'}</span><details class="source-detail"><summary>요약 원문과 출처</summary><p>${esc(card.summary)}</p><code>${esc(card.summarySource || 'template')}</code></details></div>`;
  html += `<div class="muted">데이터 신선도: ${card.freshness && card.freshness.ok ? '정상' : '신뢰 불가'} (${fmt(card.freshness && card.freshness.age_s, 1)} s) · 인용 노드 ${(card.citations || []).length}개</div>`;
  html += '<h2>가능한 고장 원인과 관측 근거</h2><div class="table-scroll" tabindex="0" role="region" aria-label="고장 원인과 관측 근거 표"><table class="causes"><thead><tr><th>순위</th><th>원인</th><th>사전확률</th><th>점수</th><th>확인한 조건과 관측값</th></tr></thead><tbody>';
  (card.causes || []).forEach((c, i) => {
    const ev = (c.evidence || []).map(e => {
      const unknown = e.status === 'UNKNOWN' || e.passed == null || e.value == null || !!e.error;
      return `<div class="ev" title="${esc(e.id)}"><span class="${unknown ? 'muted' : e.passed ? 'ok' : 'no'}">${esc(e.name)}</span><b>${unknown ? '판정 미확인' : e.passed ? '조건 충족' : '조건 미충족'} · 관측 ${esc(fmt(e.value, 2))}</b>${unknown ? `<span class="muted">${esc(e.error || e.reason || '관측 근거 없음')}</span>` : ''}</div>`;
    }).join('');
    html += `<tr><td>후보 ${i + 1}</td><td><strong title="${esc(c.id)}">${esc(c.name)}</strong><div class="muted">${esc(c.description || '')}</div></td><td data-label="사전확률" class="num">${fmt(c.prior, 2)}</td><td data-label="점수" class="score num">${fmt(c.score, 2)}</td><td data-label="확인한 조건과 관측값">${ev || '<span class="muted">증거 규칙 없음</span>'}</td></tr>`;
  });
  html += '</tbody></table></div><h2>권장 조치와 정비 절차</h2>';
  for (const a of card.recommended || []) {
    html += `<div class="action" data-code="${esc(a.code)}"><header><strong>${esc(a.name)}</strong><span class="code" title="${esc(a.code)} · ${esc(a.relation || '')}">${a.kind === 'command' ? '즉시 조치 명령' : '작업지시'}</span></header>`;
    if (a.kind === 'command' && a.paramRange) {
      html += `<div class="param"><span title="${esc(a.param)}">${esc(({fan_pct:'팬 속도 (%)',load_pct:'펌프 부하 (%)',pump:'운전 펌프'})[a.param] || a.param)}</span>${editable ? `<input type="range" min="${a.paramRange[0]}" max="${a.paramRange[1]}" step="1" value="${a.value}" data-param="${esc(a.param)}">` : ''}<output class="num">${a.value}</output><span class="muted">허용 범위 ${a.paramRange[0]}~${a.paramRange[1]} (온톨로지에 정의된 범위)</span></div>`;
      html += `<div class="muted">제약: ${(a.constraints || []).map(k => esc(k.name)).join(' · ') || '없음'} · 대상 구동기 ${esc(a.resource || '')}</div>`;
    }
    if (a.sop && a.sop.steps && a.sop.steps.length) {
      html += `<div class="muted" style="margin-top:6px">${esc(a.sop.id)} ${esc(a.sop.name || '')}</div><ol>` + a.sop.steps.map(s => `<li>${esc(s.text)} ${s.manual ? `<span>— 매뉴얼 ${esc(s.manual.ref)} ${esc(s.manual.title)}</span>` : ''}</li>`).join('') + '</ol>';
    }
    html += `<div class="cite">인용: ${esc(a.actionId)}${a.sop && a.sop.id ? ', ' + esc(a.sop.id) : ''}</div></div>`;
  }
  return html;
}
function renderDetail() {
  const box = $('#incDetail');
  const inc = state.detail, run = state.run;
  const signature = JSON.stringify([inc, run, inc && state.audit.filter(a => a.incident === inc.id)]);
  if ((inc || run) && box.dataset.signature === signature) return;
  const same = inc && box.dataset.incident === inc.id;
  const active = same && box.contains(document.activeElement) ? document.activeElement : null;
  const focusedKey = active && (active.id || active.dataset.param);
  const selection = active && active.type === 'text' ? [active.selectionStart, active.selectionEnd] : null;
  const draft = same ? [...box.querySelectorAll('input')].map(e => [e.id || e.dataset.param, e.value]) : [];
  box.dataset.signature = signature; box.dataset.incident = inc?.id || '';
  if (!inc && !run) {
    if (state.selectedAsset && state.plant && state.plant.units[state.selectedAsset]) {
      const u = state.plant.units[state.selectedAsset], t = u.tags, s = u.status, d = (state.det && state.det.assets && state.det.assets[state.selectedAsset]) || {};
      const past = incidentsFor(state.selectedAsset);
      box.innerHTML = `<div class="assetinfo"><h2>${esc(state.selectedAsset)} — 인시던트 없음 · PLC ${esc(s.state)}</h2>
        <div class="kv"><span>유온 TS1</span><b class="num">${fmt(t.TS1, 1)} ℃</b><span>냉각 효율 CE</span><b class="num">${fmt(t.CE, 0)} %</b><span>팬 / 부하</span><b class="num">${fmt(t.FanSpeedSP, 0)} % / ${fmt(t.LoadSP, 0)} %</b><span>PLC</span><b>${esc(s.mode)} · ${esc(s.state)}</b><span>탐지 단계</span><b>${esc(d.phase || '–')}</b><span>쿨러 상태(health)</span><b class="num">${fmt(s.cooler_health, 2)}</b></div>
        <p class="muted">경보가 나면 에이전트가 온톨로지에서 원인·조치를 꺼내 카드를 만들고, 그 프로세스가 여기에 나타난다. 결함 시나리오 시뮬레이션에서 이 설비에 쿨러 열화를 주입해 볼 수 있다.${past.length ? ' 왼쪽 목록에 이 설비의 지난 인시던트 ' + past.length + '건이 있다.' : ''}</p></div>`;
    } else {
      box.innerHTML = '<div class="empty">위 도식에서 설비를 선택하면 관련 조치 과정을 확인할 수 있습니다.</div>';
    }
    return;
  }
  let html = '';
  if (inc) {
    html += `<h2 style="margin-top:0">${esc(inc.id)} <span class="pill ${esc(inc.state)}">${esc(UI.status(inc.state))}</span> <span class="muted">${esc(inc.asset)} · 경보 ${esc(inc.alertId)}${inc.cmdId ? ' · 명령 ' + esc(inc.cmdId) : ''}${inc.approvedBy ? ' · 승인 ' + esc(inc.approvedBy) : ''}</span></h2>`;
    html += '<h2>조치 진행 단계</h2>' + lane(inc);
    if (inc.ack) html += `<div class="muted">PLC ACK: ${esc(inc.ack.result)}${inc.ack.reason ? ' (' + esc(inc.ack.reason) + ')' : ''} · 인터록 ${esc(inc.ack.interlock || '')}</div>`;
    if (inc.workOrder) html += `<div class="muted">작업지시 ${esc(inc.workOrder.id)}: ${esc(inc.workOrder.name)} (${esc(inc.workOrder.sop || '')})</div>`;
    if (inc.workOrderRequest && !inc.workOrder) {
      html += `<p>작업지시 발행 대기 · 승인한 내용: ${esc(inc.workOrderRequest.item.value || inc.workOrderRequest.item.name || '')}. 실제 CMMS 응답을 확인해야 종결됩니다.</p>`;
      if (inc.processOwned === false && (inc.state === 'RESOLVED' || (inc.state === 'AWAITING_APPROVAL' && inc.workOrderRequest.work_order_only)))
        html += '<button class="btn" id="btnWorkOrderRetry">같은 작업지시 재전달</button>';
    }
  }
  const card = (inc && inc.card) || (run && run.card);
  const editable = inc && inc.state === 'AWAITING_APPROVAL' && !inc.workOrderRequest;
  html += '<h2>가이드 카드</h2>' + cardHtml(card, false);
  html += '<details class="technical"><summary>에이전트의 분석 과정 확인</summary>' + traceHtml(run) + '</details>';
  if (editable) {
    html += `<p class="hint">가이드는 판단 근거입니다. 조치 카드에서 SOP 전체와 승인 역할을 선택하세요. 승인 시 현재 설비·업무 조건을 다시 확인합니다.</p>`;
  }
  if (inc) {
    const audit = state.audit.filter(a => a.incident === inc.id);
    html += '<h2>감사 로그</h2><div class="audit">' + (audit.map(a => UI.eventRecord({time:a.t,name:a.event,actor:a.actor,detail:a.detail?.reason || '',raw:a})).join('') || '<div class="muted">없음</div>') + '</div>';
  }
  box.innerHTML = html;
  for (const e of box.querySelectorAll('input')) {
    const saved = draft.find(([key]) => key === (e.id || e.dataset.param));
    if (saved) { e.value = saved[1]; if (e.type === 'range') e.parentElement.querySelector('output').textContent = e.value; }
    if (focusedKey && focusedKey === (e.id || e.dataset.param)) {
      e.focus({preventScroll:true});
      if (selection) e.setSelectionRange(...selection);
    }
  }
  box.querySelectorAll('input[type=range]').forEach(r => r.addEventListener('input', () => r.parentElement.querySelector('output').textContent = r.value));
  const rj = $('#btnReject'); if (rj) rj.addEventListener('click', reject);
  const wr = $('#btnWorkOrderRetry'); if (wr) wr.addEventListener('click', async () => {
    wr.disabled = true;
    try { await postJ(API.process + `/api/incidents/${encodeURIComponent(inc.id)}/work-order-retry`, {}); }
    catch (e) { alert('작업지시 재전달 실패: ' + e.message); }
    finally { await refreshSlow(); await loadDetail(); }
  });
}
async function reject() {
  const inc = state.detail; if (!inc) return;
  try { await postJ(API.process + `/api/incidents/${inc.id}/reject`, { by: 'OP-17', reason: $('#rejectReason').value || '운전원 판단' }); }
  catch (e) { alert('거부 실패: ' + e.message); }
  await refreshSlow(); await loadDetail();
}

/* ---------------- trends ---------------- */
async function trendsNotice() {
  const n = $('#trendsNotice'); if (!n) return;
  // Grafana sends no CORS headers: an opaque (no-cors) response means reachable, a network error means it is down
  try { await fetch(API.grafana + '/api/health', { mode: 'no-cors', cache: 'no-store' }); n.hidden = true; }
  catch (e) { n.hidden = false; n.innerHTML = '<b>Grafana가 응답하지 않습니다.</b> 그래프 패널은 Grafana가 그립니다. <code>docker compose up -d grafana</code> 로 띄운 뒤 다시 열어 주세요. 센서값 자체는 결함 시뮬레이션 · 이상 확인 화면에서 1초마다 갱신됩니다.'; }
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
  if (!state.definition) { try { state.definition = await getJ(API.process + '/api/definition'); } catch (e) { } }
  $('#openCount').textContent = incidentError ? '연결 끊김' : state.incidents.filter(i => !i.terminal).length;
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
