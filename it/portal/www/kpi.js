/* A8 성과 지표 실적 · 역추적 (읽기 전용). window.hydKpi.mount(el)
   관점(재무 → 고객 → 내부 프로세스 → 학습과 성장) → 목표 → 지표 카드. 지표마다 실적 · 목표 · 달성률과 계산 근거(원천 표 · 열 · 식 · 행 수)를,
   원천이 없는 지표는 "계산 불가 — 사유"를 보여 준다. 미달 카드의 "원인 찾기" → 영향 경로와 같은 기간 처리 건 · 조치 · 설비.
   데이터: process 서비스 GET /api/kpi · /api/kpi/trace (it/process/procsvc/kpi.py). 이 화면은 아무것도 쓰지 않는다.
   B5 목표값 바꿔 보기(시험 실행): POST /api/kpi/try · /api/kpi/try/trace 에 {지표: 시험 목표}를 보내 달성/미달 · 달성률 · 역추적을
   그 목표로 다시 판정한다. 지식 그래프의 목표값은 그대로이고 "원래대로"는 시험 목표를 비운다. */
(function () {
  const PERIODS = [['1h', '최근 1시간'], ['24h', '최근 24시간'], ['7d', '최근 7일'], ['30d', '최근 30일'], ['all', '전체 기록']];
  const STATUS = { met: '달성', missed: '미달', no_target: '목표 없음', partial: '부분 실적', no_data: '기록 없음', unavailable: '계산 불가', error: '조회 실패' };
  const TONE = { met: 'success', missed: 'danger', no_target: 'neutral', partial: 'warning', no_data: 'neutral', unavailable: 'neutral', error: 'danger' };
  const ROLE = { lagging: ['후행 · 결과', 'accent'], leading: ['선행 · 동인', 'neutral'] };
  const EFFECT = { '-1': ['나쁜 쪽', 'danger'], '0': ['경로마다 다름', 'warning'], '1': ['좋은 쪽', 'success'] };
  const escH = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const chip = (label, tone = 'neutral') => `<span class="chip tone-${tone}">${escH(label)}</span>`;
  const num = v => v == null || Number.isNaN(Number(v)) ? '–' : Number(v).toLocaleString('ko-KR', { maximumFractionDigits: 2 });
  const when = v => { if (!v) return '–'; const d = new Date(v); return Number.isNaN(d.getTime()) ? String(v) : d.toLocaleString('ko-KR', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }); };
  const fold = (summary, body, open = false) => (typeof UI !== 'undefined' && UI.fold) ? UI.fold(summary, body, { open })
    : `<details class="fold" ${open ? 'open' : ''}><summary>${summary}</summary><div class="fold-body">${body}</div></details>`;
  const empty = (title, sub = '') => `<div class="empty"><b>${escH(title)}</b>${sub ? `<span>${escH(sub)}</span>` : ''}</div>`;   // UI.empty 와 같은 모양
  const name = id => (typeof UI !== 'undefined' && UI.name) ? UI.name(id) : id;

  function base() {
    // eslint-disable-next-line no-undef
    if (typeof API !== 'undefined' && API.process) return API.process;
    return `${location.protocol}//${location.hostname || 'localhost'}:8080`;
  }
  async function getJSON(path) {
    // eslint-disable-next-line no-undef
    if (typeof requestJ === 'function') return requestJ(base() + path);
    const ctl = new AbortController(); const timer = setTimeout(() => ctl.abort(), 15000);
    try {
      const r = await fetch(base() + path, { cache: 'no-store', signal: ctl.signal });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(typeof j.detail === 'string' ? j.detail : `요청 실패 (${r.status})`);
      return j;
    } catch (e) { throw e.name === 'AbortError' ? new Error('응답 시간 초과. 처리 서비스 연결을 확인하세요.') : e; } finally { clearTimeout(timer); }
  }

  async function postJSON(path, body) {
    // eslint-disable-next-line no-undef
    if (typeof requestJ === 'function') return requestJ(base() + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
    const r = await fetch(base() + path, { method: 'POST', cache: 'no-store', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof j.detail === 'string' ? j.detail : `요청 실패 (${r.status})`);
    return j;
  }
  const trialOn = st => Object.keys(st.applied || {}).length > 0;

  /* ---------------- 지표 카드 ---------------- */
  function valueLine(m) {
    const unit = escH(m.displayUnit || m.unit || '');
    if (m.value == null) return `<span class="kv"><b>–</b></span>`;
    const target = m.target == null ? '' : `<span class="kv"><small>목표</small>${num(m.target)} ${escH(m.unit || '')}</span>`;
    return `<span class="kv"><b>${num(m.value)}</b><small>${unit}</small></span>${target}`;
  }
  function rateBar(m) {
    if (m.rate == null) return '';
    const w = Math.max(0, Math.min(100, m.rate));
    return `<div class="kpi-rate" title="달성률"><span class="kpi-track"><i class="tone-${TONE[m.status]}" style="width:${w}%"></i></span><b>달성률 ${num(m.rate)} %</b></div>`;
  }
  function table(rows) {
    if (!rows || !rows.length) return '';
    const cols = [...new Set(rows.flatMap(r => Object.keys(r)))];
    return `<table class="compact-table"><thead><tr>${cols.map(c => `<th>${escH(c)}</th>`).join('')}</tr></thead><tbody>${
      rows.map(r => `<tr>${cols.map(c => `<td>${escH(r[c] == null ? '–' : typeof r[c] === 'number' ? num(r[c]) : r[c])}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
  }
  function basis(m) {
    const d = m.definition || {};
    const parts = [];
    if (d.kind === 'calc' || d.kind === 'formula') {
      parts.push(`<p class="kv-line"><b>식</b> ${escH(d.formula)}</p>`);
      if (d.sources) parts.push(`<p class="kv-line"><b>원천</b> ${d.sources.map(s => `${escH(s.system)} <code>${escH(s.table)}</code> (${escH(s.columns)})`).join(' · ')}</p>`);
    }
    if (m.rows && m.rows.length) parts.push(`<p class="kv-line"><b>읽은 행</b> ${m.rows.map(r => `${escH(r.system)} <code>${escH(r.table)}</code> ${num(r.rows)}행`).join(' · ')}</p>`);
    if (m.note) parts.push(`<p class="kv-line">${escH(m.note)}</p>`);
    const per = Object.entries(m.perAsset || {});
    if (per.length) parts.push(`<p class="kv-line"><b>설비별</b> ${per.map(([a, v]) => `${escH(a)} ${num(v)}${m.perAssetMet && m.perAssetMet[a] === false ? ' ' + chip('미달', 'danger') : ''}`).join(' · ')}</p>`);
    parts.push(table(m.detail));
    return parts.join('');
  }
  function card(m) {
    const [roleLabel, roleTone] = ROLE[m.kpiRole] || ['역할 없음', 'neutral'];
    const status = chip(STATUS[m.status] || m.status, TONE[m.status]);
    const reason = m.reason ? `<p class="card-sub kpi-reason">${escH(m.reason)}</p>` : '';
    const o = m.original;          // B5: 시험 목표가 걸린 지표 — 원래 목표 · 원래 판정을 옆에
    const trial = o ? `<p class="card-sub">${chip('시험 목표', 'warning')} 원래 목표 ${o.target == null ? '없음' : num(o.target) + ' ' + escH(m.unit || '')} · 원래 판정 ${escH(STATUS[o.status] || o.status)}${o.rate == null ? '' : ` (달성률 ${num(o.rate)} %)`}</p>` : '';
    const action = m.status === 'missed' ? `<button type="button" class="btn small primary" data-kpi-trace="${escH(m.id)}">원인 찾기</button>` : '';
    const body = (m.status === 'unavailable' ? '' : fold('계산 근거', basis(m)));
    const html = `<section class="card kpi-card${m.status === 'missed' ? ' kpi-missed' : ''}" data-kpi="${escH(m.id)}">
      <header class="card-head"><div class="card-title"><h3>${escH(m.name)}</h3><span class="card-chips">${status}${chip(roleLabel, roleTone)}</span></div>
      ${action ? `<div class="card-actions">${action}</div>` : ''}</header>
      <div class="card-value">${valueLine(m)}</div>${rateBar(m)}${trial}${reason}${body ? `<div class="card-body">${body}</div>` : ''}</section>`;
    return html;
  }

  /* ---------------- 역추적 ---------------- */
  function tracePanel(st) {
    const t = st.trace;
    if (!t) return '';
    const head = `<header class="card-head"><div class="card-title"><h3>${escH(t.title)} — 미달 원인 찾기</h3></div><div class="card-actions"><button type="button" class="btn small" data-kpi-close>닫기</button></div></header>`;
    if (t.loading) return `<section class="card kpi-trace" id="kpiTrace">${head}<p class="card-sub">영향 경로와 같은 기간 처리 기록을 맞춰 보는 중…</p></section>`;
    if (t.error) return `<section class="card kpi-trace" id="kpiTrace">${head}<p class="card-sub kpi-reason">역추적 실패: ${escH(t.error)}</p></section>`;
    const d = t.data, m = d.measure;
    const summary = `<p class="kv-line">실적 <b>${num(m.value)} ${escH(m.displayUnit || m.unit || '')}</b> · 목표 ${num(m.target)} ${escH(m.unit || '')} · ${escH(d.window.label)} · 처리 건 ${num(d.instancesRead)}건 중 관련 ${num(d.instanceTotal)}건</p>`;
    const assets = d.assets.length ? `<ol class="stack-list kpi-list">${d.assets.map(a => `<li><b>${escH(a.asset)}</b> ${a.value == null ? '' : num(a.value) + ' ' + escH(m.unit || '')} ${a.met === false ? chip('미달', 'danger') : a.met === true ? chip('달성', 'success') : ''}
        <span class="kv-line">관련 처리 건 ${a.instances}건${a.events.length ? ' · ' + a.events.map(escH).join(' · ') : ''}</span></li>`).join('')}</ol>` : empty('설비별 값이 없습니다');
    const insts = d.instances.length ? `<ol class="stack-list kpi-list">${d.instances.map(i => `<li>
        <div class="row-wrap"><b>${escH(i.asset || '설비 미상')}</b><span>${escH(i.patternName || (String(i.pattern || '').endsWith('_TRIP') ? '보호 정지 경보' : '이상 경보'))}</span>
        <span class="kv-line">${when(i.start)} 시작${i.chosenSkill ? ' · 고른 조치 ' + escH(i.chosenSkillName || name(i.chosenSkill)) : ' · 고른 조치 없음'}${i.causeName ? ' · 원인 ' + escH(i.causeName) : ''}</span>
        <a class="btn small" href="${escH(i.link)}">처리 건 열기 →</a></div>
        <ul class="kpi-why">${i.reasons.map(r => `<li>${escH(r)}</li>`).join('')}</ul></li>`).join('')}</ol>`
      : empty('같은 기간에 이 지표의 영향 경로에 걸린 처리 건이 없습니다', '처리 건이 없거나, 경보 · 조치가 이 지표의 경로와 닿지 않았습니다');
    const actions = d.actions.length ? `<p class="kv-line"><b>고른 조치</b> ${d.actions.map(a => `${escH(a.name)} ×${a.count} ${chip(EFFECT[String(a.effect)]?.[0] || '영향 불명', EFFECT[String(a.effect)]?.[1] || 'neutral')}`).join(' · ')}</p>` : '';
    const drivers = d.drivers.map(x => `<li>${chip(x.effect < 0 ? '오르면 지표 악화' : x.effect > 0 ? '오르면 지표 개선' : '경로마다 다름', x.effect < 0 ? 'danger' : x.effect > 0 ? 'success' : 'warning')} ${escH(x.path)}${x.condition ? ` <small>(${escH(x.condition)})</small>` : ''}</li>`).join('');
    const objectives = d.objectives.map(o => `<li><b>${escH(o.name)}</b>${o.supports.length ? ' → ' + o.supports.map(s => escH(s.name)).join(' → ') : ''}</li>`).join('');
    const skills = d.skills.map(s => `<li>${escH(s.name)} ${chip(EFFECT[String(s.effect)][0], EFFECT[String(s.effect)][1])}${s.harm.length ? ` <small>나쁜 경로: ${s.harm.map(escH).join(' / ')}</small>` : ''}</li>`).join('');
    return `<section class="card kpi-trace" id="kpiTrace">${head}${summary}
      <h4>원인 처리 건</h4>${insts}${actions}
      <h4>설비</h4>${assets}
      ${fold(`영향 경로 ${d.drivers.length}개 (지식 그래프의 영향 관계)`, `<ul class="kpi-why">${drivers}</ul>`)}
      ${fold('이 지표를 움직이는 조치 방법', `<ul class="kpi-why">${skills}</ul>`)}
      ${fold('이 목표가 받치는 목표', `<ul class="kpi-why">${objectives}</ul>`)}</section>`;
  }

  /* ---------------- B5 목표값 바꿔 보기 ---------------- */
  function trialPanel(st, all, d) {
    st.targets = st.targets || {}; st.applied = st.applied || {};
    const on = trialOn(st);
    const changed = (d.trial && d.trial.changed) || [];
    const head = on ? `<div class="summary prose" role="status"><p style="margin:0 0 var(--s2)">${chip(`시험 목표 ${Object.keys(st.applied).length}개 적용 중`, 'warning')} ${escH((d.trial && d.trial.note) || '')}</p>
        ${changed.length ? `<ul class="kpi-why">${changed.map(c => `<li><b>${escH(c.name)}</b> 실적 ${num(c.value)} ${escH(c.unit || '')} — 목표 ${c.before.target == null ? '없음' : num(c.before.target)} → <b>${num(c.after.target)}</b> · ${escH(STATUS[c.before.status] || c.before.status)} → <b>${escH(STATUS[c.after.status] || c.after.status)}</b></li>`).join('')}</ul>`
          : '<p class="kv-line" style="margin:0">판정이 바뀐 지표가 없습니다 (실적이 없거나 계산 불가인 지표는 목표를 바꿔도 그대로입니다).</p>'}
        <div class="form-actions"><button type="button" class="btn small" data-kpi-trial-reset>원래대로</button></div></div>` : '';
    const rows = all.map(m => `<tr><td>${escH(m.name)}</td><td>${(m.original ? m.original.target : m.target) == null ? '–' : num(m.original ? m.original.target : m.target) + ' ' + escH(m.unit || '')}</td>
      <td><input type="number" step="any" data-kpi-target="${escH(m.id)}" value="${st.targets[m.id] ?? ''}" placeholder="그대로" aria-label="${escH(m.name)} 시험 목표" style="width:8em"></td>
      <td>${escH(STATUS[m.status] || m.status)}</td></tr>`).join('');
    const form = `<p class="field-hint">비운 칸은 지식 그래프의 목표 그대로입니다. 시험 판정은 이 화면 계산에만 쓰고 원본 목표는 바꾸지 않습니다.</p>
      <table class="compact-table"><thead><tr><th>지표</th><th>원래 목표</th><th>시험 목표</th><th>지금 판정</th></tr></thead><tbody>${rows}</tbody></table>
      <div class="form-actions"><button type="button" class="btn small primary" data-kpi-trial-run>시험 판정</button>${on ? '<button type="button" class="btn small" data-kpi-trial-reset>원래대로</button>' : ''}</div>
      ${st.trialError ? `<p class="kpi-reason">${escH(st.trialError)}</p>` : ''}`;
    return head + fold(`목표값 바꿔 보기 (시험 실행)${on ? ' ' + chip('적용 중', 'warning') : ''}`, form, !!st.trialOpen);
  }

  /* ---------------- 화면 ---------------- */
  function render(st) {
    const el = st.el;
    const tools = `<div class="page-tools" role="group" aria-label="기간">${PERIODS.map(([k, l]) => `<button type="button" class="btn small${k === st.period ? ' primary' : ''}" data-kpi-period="${k}" aria-pressed="${k === st.period}">${l}</button>`).join('')}
      <button type="button" class="btn small" data-kpi-reload>다시 읽기</button></div>`;
    let body;
    if (st.loading && !st.data) body = empty('성과 지표 실적을 계산하는 중…', '시계열 · 업무 DB · 처리 기록을 읽습니다');
    else if (st.error) body = empty('성과 지표를 불러오지 못했습니다', st.error);
    else {
      const d = st.data, s = d.summary;
      const all = d.perspectives.flatMap(p => p.objectives.flatMap(o => o.measures));
      const stat = (label, n, sub, hot) => `<div class="card${hot ? ' hot' : ''}"><span>${label}</span><b>${n}</b><small>${sub}</small></div>`;
      const stats = `<div class="stat-cards">${stat('미달', s.missed, '원인 찾기를 누르세요', s.missed > 0)}${stat('달성', s.met, '목표 이상')}
        ${stat('실적만', s.no_target + s.partial, `목표 없음 ${s.no_target} · 부분 실적 ${s.partial}`)}${stat('계산 불가 · 기록 없음', s.unavailable + s.no_data + s.error, `원천 없음 ${s.unavailable} · 기록 없음 ${s.no_data} · 조회 실패 ${s.error}`)}</div>`;
      const win = `<p class="kv-line">${escH(d.window.label)}${d.window.start ? ` (${when(d.window.start)} ~ ${when(d.window.end)})` : ''} · 설비 시간 배율 ${num(d.timeScale)}× · 지표 ${s.total}개</p>`;
      const persp = d.perspectives.map(p => `<h2 class="sec">${escH(p.name)}</h2>${p.objectives.map(o => `
        <div class="kpi-obj"><h3>${escH(o.name)}</h3>${o.supports.length ? `<small>받치는 목표 → ${o.supports.map(x => escH(x.name)).join(' · ')}</small>` : ''}</div>
        <div class="cards three">${o.measures.map(card).join('')}</div>`).join('')}`).join('');
      const defs = `<table class="compact-table"><thead><tr><th>지표</th><th>목표</th><th>원천 (표 · 열)</th><th>식 또는 계산 불가 사유</th></tr></thead><tbody>${all.map(m => {
        const df = m.definition || {};
        const src = (df.sources || []).map(x => `${escH(x.system)} <code>${escH(x.table)}</code> ${escH(x.columns)}`).join('<br>') || '–';
        return `<tr><td>${escH(m.name)}</td><td>${m.target == null ? '–' : num(m.target) + ' ' + escH(m.unit || '')}</td><td>${src}</td><td>${df.kind === 'unavailable' ? '계산 불가 — ' + escH(df.reason) : escH(df.formula)}</td></tr>`;
      }).join('')}</tbody></table>`;
      body = stats + win + trialPanel(st, all, d) + tracePanel(st) + persp + `<h2 class="sec">계산 정의</h2>` + fold(`지표별 계산 정의 표 (${all.length}개)`, defs);
    }
    el.innerHTML = `<div class="page-head"><h1>성과 지표</h1>${tools}</div>${body}`;
  }

  async function load(st) {
    st.loading = true; st.error = null; render(st);
    try {
      st.data = trialOn(st) ? await postJSON('/api/kpi/try', { period: st.period, targets: st.applied })
        : await getJSON(`/api/kpi?period=${encodeURIComponent(st.period)}`);
      if (trialOn(st)) st.trialError = null;
    } catch (e) {
      if (trialOn(st)) { st.trialError = '시험 판정을 하지 못했습니다: ' + (e.message || String(e)); st.applied = {}; st.loading = false; return load(st); }
      st.error = e.message || String(e); st.data = null;
    }
    st.loading = false; render(st);
    if (st.trace && st.data) openTrace(st, st.trace.measure);
  }

  async function openTrace(st, measure) {
    const m = st.data && st.data.perspectives.flatMap(p => p.objectives.flatMap(o => o.measures)).find(x => x.id === measure);
    st.trace = { measure, title: m ? m.name : '지표', loading: true };
    render(st);
    const panel = st.el.querySelector('#kpiTrace'); if (panel && panel.scrollIntoView) panel.scrollIntoView({ block: 'nearest' });
    try {
      const data = trialOn(st) ? await postJSON('/api/kpi/try/trace', { measure, period: st.period, targets: st.applied })
        : await getJSON(`/api/kpi/trace?measure=${encodeURIComponent(measure)}&period=${encodeURIComponent(st.period)}`);
      st.trace = { measure, title: st.trace.title, data };
    }
    catch (e) { st.trace = { measure, title: st.trace.title, error: e.message || String(e) }; }
    render(st);
  }

  function mount(el) {
    if (!el) return null;
    if (el._hydKpi) { load(el._hydKpi); return el._hydKpi; }
    const st = { el, period: '24h', data: null, trace: null, loading: false, error: null, targets: {}, applied: {}, trialOpen: false, trialError: null };
    try { st.period = localStorage.getItem('hydKpi.period') || '24h'; } catch (e) { /* 저장소가 없으면 기본 기간 */ }
    if (!PERIODS.some(([k]) => k === st.period)) st.period = '24h';
    el._hydKpi = st;
    el.addEventListener('click', e => {
      const p = e.target.closest('[data-kpi-period]');
      if (p) { st.period = p.dataset.kpiPeriod; try { localStorage.setItem('hydKpi.period', st.period); } catch (x) { /* 무시 */ } load(st); return; }
      if (e.target.closest('[data-kpi-reload]')) { load(st); return; }
      const t = e.target.closest('[data-kpi-trace]');
      if (t) { openTrace(st, t.dataset.kpiTrace); return; }
      if (e.target.closest('[data-kpi-close]')) { st.trace = null; render(st); return; }
      if (e.target.closest('[data-kpi-trial-run]')) {
        st.trialOpen = true; st.applied = {};
        for (const [k, v] of Object.entries(st.targets)) if (v !== '' && v != null) st.applied[k] = Number(v);
        st.trace = null; load(st); return;
      }
      if (e.target.closest('[data-kpi-trial-reset]')) { st.targets = {}; st.applied = {}; st.trialError = null; st.trace = null; load(st); }
    });
    el.addEventListener('change', e => {
      const t = e.target.closest('[data-kpi-target]');
      if (t) { st.trialOpen = true; if (t.value === '') delete st.targets[t.dataset.kpiTarget]; else st.targets[t.dataset.kpiTarget] = t.value; }
    });
    load(st);
    return st;
  }

  window.hydKpi = { mount, _render: render, _card: card, _tracePanel: tracePanel };

  // 지금 셸: #view-kpi 가 열릴 때 #kpiView 에 그린다 (U7 셸 재편 뒤에는 셸이 mount 를 부른다)
  function autoMount() {
    const view = document.getElementById('view-kpi'), host = document.getElementById('kpiView');
    if (!view || !host) return;
    const check = () => { if (view.classList.contains('active')) mount(host); };
    new MutationObserver(check).observe(view, { attributes: true, attributeFilter: ['class'] });
    check();
  }
  if (typeof document !== 'undefined' && document.getElementById) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', autoMount); else autoMount();
  }
})();
