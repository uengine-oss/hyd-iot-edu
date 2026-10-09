/* A4 (U6) 판단 채점 — 사람이 적은 정답표에 AI 판단을 대어 점수를 내고, 실행을 남겨 지식 고치기 전·후를 비교한다.
   API: process /api/eval/* (procsvc/eval_api.py). 정답표는 화면에서 적는 데이터이고 처음엔 비어 있다 — 이 파일에도 정답은 없다.
   화면: window.hydEval.mount(el). 포털 셸이 컨테이너(#evalView)를 주면 그 안에 전부 그린다. 채점은 처리 건 · 설비 명령 · 기준 데이터를 바꾸지 않는다. */
(function () {
  const E = { el: null, golden: [], storage: '', paths: {}, maxRepeats: 10, runs: [], sel: null, run: null, editing: null,
    knowledge: null, cands: null, patterns: null, cmp: null, busy: false, picked: new Set() };
  const PATH = { decide: '규칙 판단', evaluate: '에이전트 읽기 평가', worker: '지난 처리 건 (실제 AI 일꾼)' };
  const CHECK = { cause: '원인 적중', top: '1위 허용', forbidden: '빠질 조치 미추천', evidence: '근거 포함' };
  const EXPECT = { excluded: '제외돼야 함', not_recommended: '1위면 안 됨' };
  const FACT = { plc_mode: '운전 모드', plc_state: '설비 상태', standby_ready: '예비 펌프', fan100_hours: '팬 100 % 누적 (시간)' };
  const ASSETS = ['HYD-01', 'HYD-02', 'HYD-03'];
  const q = (sel) => E.el.querySelector(sel);
  const nm = (id) => `<span title="${esc(id || '')}">${esc(UI.name(id) || '–')}</span>`;
  const outcomeText = (o) => String(o || '').split(' → ').map(x => x === '-' ? '없음' : UI.name(x)).join(' → ');
  const factVal = (k, v) => k === 'standby_ready' ? (v ? '가용' : '정비 중') : typeof v === 'string' ? UI.status(v) : String(v);
  const factsText = (f) => Object.entries(f || {}).map(([k, v]) => `${FACT[k] || k} ${factVal(k, v)}`).join(' · ') || '가정 사실 없음 (지금 값 사용)';
  const pct = (x) => Math.round((x || 0) * 100) + ' %';
  const ok = (b) => UI.chipText(b ? '맞음' : '틀림', b ? 'success' : 'danger');

  async function longJ(url, method, body) {           // 채점 실행은 N회 판단이라 30초를 넘길 수 있다 — 끊지 않고 기다린다
    const r = await fetch(url, { method, cache: 'no-store', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) { const d = j.detail; throw new Error(typeof d === 'string' ? d : Array.isArray(d) ? d.map(x => x.msg || JSON.stringify(x)).join(' · ') : `요청 실패 (${r.status})`); }
    return j;
  }
  const msg = (key, text, bad = true) => { const m = q(`[data-msg="${key}"]`); if (m) { m.textContent = text || ''; m.className = 'form-msg ' + (bad ? 'neg' : 'pos'); } };

  /* ---------------------------------------------------------------- 뼈대 */
  function skeleton() {
    E.el.innerHTML = `
      <div class="page-head"><h1>판단 채점</h1><div class="page-tools"><button type="button" class="btn small" data-act="reload">${esc(UI.t('btn.reload'))}</button></div></div>
      <p class="card-sub">경보 상황마다 기대하는 원인 · 1위로 허용되는 조치 · 빠져야 할 조치 · 있어야 할 근거를 정답표에 적고, AI 판단을 대어 점수를 냅니다. 지식을 고치기 전과 후에 한 번씩 채점해 두 실행을 비교합니다. 채점은 처리 건 · 설비 명령 · 기준 데이터를 바꾸지 않습니다.</p>
      <div class="stat-cards" data-r="stats"></div>
      <div class="sec-head"><h2>1. 정답표</h2><button type="button" class="btn small" data-act="new">새 항목 적기</button></div>
      <div data-r="golden"></div>
      <div data-r="form"></div>
      <div class="sec-head"><h2>2. 채점 실행</h2></div>
      <section class="card" data-r="runform"></section>
      <div class="sec-head"><h2>3. 실행 기록</h2></div>
      <div class="split"><div><div class="list" data-r="runs"></div></div><div class="detail" data-r="detail"></div></div>
      <div class="sec-head"><h2>4. 지식 고치기 전 · 후 비교</h2></div>
      <section class="card" data-r="cmpform"></section>
      <div data-r="cmp"></div>`;
    E.el.addEventListener('click', onClick);
    E.el.addEventListener('change', onChange);
    E.el.addEventListener('input', onInput);
  }

  function renderStats() {
    const last = E.runs[0], k = E.knowledge;
    const card = (label, value, sub = '') => `<section class="card"><span>${esc(label)}</span><b>${value}</b>${sub ? `<small>${sub}</small>` : ''}</section>`;
    q('[data-r="stats"]').innerHTML =
      card('정답표 항목', esc(E.golden.length), E.golden.length ? '' : '비어 있음 — 먼저 적으세요') +
      card('채점 실행', esc(E.runs.length), last ? esc(UI.dateTime(last.created)) : '아직 없음') +
      card('최근 평균 점수', last ? esc(last.summary.score) + '점' : '–', last ? esc(PATH[last.path] || last.path) : '') +
      card('지금 지식', k ? `노드 ${esc(k.nodes)} · 관계 ${esc(k.relationships)}` : '–',
        k ? esc(k.last_change ? '마지막 변경 ' + UI.dateTime(k.last_change) : k.last_change_note || '') : esc(E.knowledgeError || ''));
  }

  /* ---------------------------------------------------------------- 1. 정답표 */
  function renderGolden() {
    const host = q('[data-r="golden"]');
    if (!E.golden.length) {
      host.innerHTML = UI.empty('정답표가 비어 있습니다', '"새 항목 적기"로 경보 상황 하나와 기대하는 판단을 적으세요. 내장 정답은 없습니다.');
      return;
    }
    host.innerHTML = `<div class="table-scroll"><table><thead><tr><th>채점</th><th>경보 상황</th><th>기대 원인</th><th>1위 허용</th><th>빠질 조치</th><th>있어야 할 근거</th></tr></thead><tbody>${
      E.golden.map(it => `<tr>
        <td><input type="checkbox" data-pick="${esc(it.id)}" ${E.picked.has(it.id) ? 'checked' : ''} aria-label="${esc(it.title)} 채점에 포함"></td>
        <td><button type="button" class="btn small" data-edit="${esc(it.id)}">${esc(it.title)}</button><br><small>${esc(it.asset)} · ${esc(patternName(it.pattern))} · ${esc(factsText(it.facts))}</small></td>
        <td>${nm(it.expected.cause)}<br><small>${nm(it.expected.failure_mode)}</small></td>
        <td>${it.allowed_top.map(nm).join('<br>')}</td>
        <td>${it.forbidden.length ? it.forbidden.map(f => `${nm(f.skill)} <small>${esc(EXPECT[f.expect])}</small>`).join('<br>') : '<small>없음</small>'}</td>
        <td>${it.required_evidence.map(nm).join('<br>')}</td></tr>`).join('')}</tbody></table></div>
      <p class="field-hint">채점에 포함할 항목에 표시하세요. 아무것도 표시하지 않으면 전체를 채점합니다. 제목을 누르면 고칠 수 있습니다.</p>`;
  }
  function patternName(code) { const p = (E.patterns || []).find(x => x.code === code); return p ? p.name : code; }

  function lines(text) { return String(text || '').split(/\n|,/).map(s => s.trim()).filter(Boolean); }
  function namePreview(text) {
    const ids = lines(text);
    if (!ids.length) return '';
    return ids.map(id => UI.names[id] ? `${esc(UI.names[id])}` : `<span class="neg" title="이름 사전에 없음 — 저장할 때 지식 그래프에서 다시 확인합니다">${esc(id)} ?</span>`).join(' · ');
  }
  function datalists() {
    const by = (prefix) => Object.entries(UI.names || {}).filter(([k]) => k.startsWith(prefix)).map(([k, v]) => `<option value="${esc(k)}">${esc(v)}</option>`).join('');
    return `<datalist id="evalDlCause">${by('cause:')}</datalist><datalist id="evalDlFm">${by('fm:')}</datalist>`;
  }

  function renderForm() {
    const host = q('[data-r="form"]');
    if (!E.editing) { host.innerHTML = ''; return; }
    const it = E.editing.item || { facts: {}, expected: {}, allowed_top: [], forbidden: [], required_evidence: [] };
    const isNew = !E.editing.item;
    const sel = (id, opts, cur) => `<select data-f="${id}">${opts.map(([v, l]) => `<option value="${esc(v)}" ${String(cur ?? '') === String(v) ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select>`;
    const pats = (E.patterns || []).map(p => [p.code, p.name]);
    const f = it.facts || {};
    const forbiddenText = (it.forbidden || []).map(x => `${x.skill} = ${x.expect === 'excluded' ? '제외' : '1위 아님'}${x.rule ? ` (${x.rule})` : ''}`).join('\n');
    host.innerHTML = UI.card({ title: isNew ? '새 정답표 항목' : '정답표 항목 고치기', cls: 'eval-form', body:
      datalists() +
      UI.section('경보 상황',
        UI.field({ label: '제목', required: true, input: `<input data-f="title" value="${esc(it.title || '')}" placeholder="예: 쿨러 성능 저하 · 원격 자동 운전">` }) +
        UI.field({ label: '항목 이름 (영문 소문자 · 숫자 · 하이픈)', required: true, hint: '저장한 뒤에는 바꿀 수 없습니다', input: `<input data-f="id" value="${esc(it.id || '')}" ${isNew ? '' : 'disabled'} placeholder="예: cooler-auto">` }) +
        UI.field({ label: '설비', required: true, input: sel('asset', ASSETS.map(a => [a, a]), it.asset || ASSETS[0]) }) +
        UI.field({ label: '이상 패턴', required: true, error: E.patterns ? '' : E.patternError || '', input: pats.length ? sel('pattern', pats, it.pattern || pats[0][0]) : `<input data-f="pattern" value="${esc(it.pattern || '')}">` })) +
      UI.section('가정 사실 (비우면 지금 값)',
        UI.field({ label: FACT.plc_mode, input: sel('plc_mode', [['', '지금 값'], ['REMOTE_AUTO', '원격 자동'], ['REMOTE_MANUAL', '원격 수동'], ['LOCAL', '현장 제어']], f.plc_mode) }) +
        UI.field({ label: FACT.plc_state, input: sel('plc_state', [['', '지금 값'], ['RUN', '운전 중'], ['TRIP', '보호 정지']], f.plc_state) }) +
        UI.field({ label: FACT.standby_ready, input: sel('standby_ready', [['', '지금 값'], ['true', '가용'], ['false', '정비 중']], f.standby_ready == null ? '' : String(f.standby_ready)) }) +
        UI.field({ label: FACT.fan100_hours, input: `<input data-f="fan100_hours" type="number" min="0" step="1" value="${esc(f.fan100_hours ?? '')}" placeholder="지금 값">` })) +
      UI.section('기대하는 판단',
        UI.field({ label: '기대 원인', required: true, input: `<input data-f="cause" list="evalDlCause" value="${esc(it.expected.cause || '')}">`, hint: '지식 지도의 원인 이름을 고르세요' }) +
        UI.field({ label: '고장 유형', required: true, input: `<input data-f="failure_mode" list="evalDlFm" value="${esc(it.expected.failure_mode || '')}">` }) +
        UI.field({ label: '1위로 허용되는 조치 — 한 줄에 하나', required: true, cls: 'wide', input: `<textarea data-f="allowed_top" rows="2">${esc((it.allowed_top || []).join('\n'))}</textarea><p class="field-hint" data-preview="allowed_top">${namePreview((it.allowed_top || []).join('\n'))}</p>` }) +
        UI.field({ label: '빠져야 할 조치 — "조치 = 제외" 또는 "조치 = 1위 아님", 근거 규칙은 괄호', cls: 'wide', input: `<textarea data-f="forbidden" rows="3">${esc(forbiddenText)}</textarea><p class="field-hint" data-preview="forbidden">${namePreview(forbiddenText.replace(/=.*$/gm, ''))}</p>` }) +
        UI.field({ label: '근거에 있어야 할 지식 — 한 줄에 하나 (증거 · 규칙 · 매뉴얼 절)', required: true, cls: 'wide', input: `<textarea data-f="required_evidence" rows="3">${esc((it.required_evidence || []).join('\n'))}</textarea><p class="field-hint" data-preview="required_evidence">${namePreview((it.required_evidence || []).join('\n'))}</p>` })) +
      UI.section('', UI.field({ label: UI.t('form.by'), required: true, input: `<input data-f="by" value="${esc(E.by || '')}">` }) + UI.field({ label: UI.t('form.note'), input: `<input data-f="note" value="${esc(it.note || '')}">` })) +
      UI.actions(`<span class="form-msg" data-msg="form" role="status"></span><button type="button" class="btn" data-act="cancel">${esc(UI.t('btn.cancel'))}</button><button type="button" class="btn primary" data-act="save">${esc(UI.t('btn.save'))}</button>`) +
      (isNew ? '' : UI.fold('이 항목 지우기', `<p class="field-hint">지워도 지난 채점 실행 기록은 남습니다.</p><button type="button" class="btn small" data-act="delete">지우기</button>`)) });
    host.scrollIntoView({ block: 'start', behavior: 'smooth' });
  }

  function readForm() {
    const v = (k) => { const n = q(`[data-f="${k}"]`); return n ? n.value.trim() : ''; };
    const facts = {};
    if (v('plc_mode')) facts.plc_mode = v('plc_mode');
    if (v('plc_state')) facts.plc_state = v('plc_state');
    if (v('standby_ready')) facts.standby_ready = v('standby_ready') === 'true';
    if (v('fan100_hours') !== '') facts.fan100_hours = Number(v('fan100_hours'));
    const forbidden = String(q('[data-f="forbidden"]').value || '').split('\n').map(s => s.trim()).filter(Boolean).map((line, i) => {
      const m = line.match(/^(\S+)\s*=\s*(제외|1위\s*아님)\s*(?:\((\S+)\))?$/);
      if (!m) throw new Error(`빠져야 할 조치 ${i + 1}번째 줄: "조치 = 제외" 또는 "조치 = 1위 아님" 형식으로 적으세요`);
      return { skill: m[1], expect: m[2] === '제외' ? 'excluded' : 'not_recommended', ...(m[3] ? { rule: m[3] } : {}) };
    });
    const by = v('by');
    if (!by) throw new Error(UI.t('form.err.required') + ': ' + UI.t('form.by'));
    E.by = by;
    return { by, item: { id: E.editing.item ? E.editing.item.id : v('id'), title: v('title'), asset: v('asset'), pattern: v('pattern'), facts,
      expected: { cause: v('cause'), failure_mode: v('failure_mode') }, allowed_top: lines(q('[data-f="allowed_top"]').value),
      forbidden, required_evidence: lines(q('[data-f="required_evidence"]').value), note: v('note') } };
  }

  /* ---------------------------------------------------------------- 2. 채점 실행 */
  function renderRunForm() {
    const path = E.path || 'decide';
    const picked = E.golden.filter(it => E.picked.has(it.id));
    const target = path === 'worker' ? '' : `<p class="field-hint">채점할 항목: ${picked.length ? picked.map(it => esc(it.title)).join(' · ') : `정답표 전체 (${E.golden.length}개)`}</p>`;
    q('[data-r="runform"]').innerHTML =
      `<div class="form-grid">` +
      UI.field({ label: '판단 경로', input: `<select data-f="path">${Object.entries(PATH).map(([k, l]) => `<option value="${k}" ${k === path ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select>`, hint: UI.clean(String(E.paths[path] || '').replace(/\s*\((?:agent|process)\s+\/api\/[^)]*\)/g, '').replace(/N>1 은/g, '여러 번은')), cls: 'wide' })   // A161-U1 (결함 18): 내부 API 경로는 화면에 두지 않는다 +
      (path === 'worker' ? '' : UI.field({ label: '반복 횟수', input: `<input data-f="repeats" type="number" min="1" max="${E.maxRepeats}" value="${esc(E.repeats || 1)}">`,
        hint: path === 'decide' ? '규칙 판단은 결정론적이라 1회면 충분합니다. 여러 번 돌려 모두 같으면 "N회 모두 같음"으로 보입니다.' : '같은 경보를 여러 번 판단해 흔들림을 잽니다.' })) +
      UI.field({ label: UI.t('form.by'), required: true, input: `<input data-f="runBy" value="${esc(E.by || '')}">` }) +
      UI.field({ label: UI.t('form.note'), input: `<input data-f="runNote" placeholder="예: 관계 하나 끊기 전">` }) +
      `</div>` + target + (path === 'worker' ? `<div data-r="cands">${renderCands()}</div>` : '') +
      UI.actions(`<span class="form-msg" data-msg="run" role="status"></span><button type="button" class="btn primary" data-act="run" ${E.golden.length ? '' : 'disabled'}>채점 실행</button>`);
  }
  function renderCands() {
    if (E.cands == null) return `<p class="field-hint">${esc(UI.t('loading'))}</p>`;
    if (E.cands.error) return `<p class="form-msg neg" role="alert">${esc(E.cands.error)}</p>`;
    if (!E.cands.length) return UI.empty('채점할 지난 처리 건이 없습니다', '원인 진단과 조치 후보 단계까지 끝난 처리 건이 여기에 나타납니다');
    return `<div class="table-scroll"><table><thead><tr><th>채점</th><th>처리 건</th><th>AI 일꾼의 판단</th><th>맞는 정답표 항목</th></tr></thead><tbody>${E.cands.map(c => {
      const item = E.golden.find(it => it.id === c.item);
      return `<tr><td><input type="checkbox" data-cand="${esc(c.instance)}" ${item ? '' : 'disabled'} aria-label="${esc(c.name || '처리 건')} 채점에 포함"></td>
        <td>${esc(c.name || UI.defName(c.instance))}<br><small>${esc(UI.dateTime(c.started))} · ${esc(UI.status(c.status))}</small></td>
        <td>${nm(c.cause)} → ${nm(c.chosen_skill)}<br><small>${esc(factsText(c.facts))}</small></td>
        <td>${item ? esc(item.title) : `<small class="neg">${esc(c.match_note || '맞는 항목 없음')}</small>`}</td></tr>`;
    }).join('')}</tbody></table></div>`;
  }
  async function loadCands() {
    E.cands = null; const host = q('[data-r="cands"]'); if (host) host.innerHTML = renderCands();
    try { E.cands = await getJ(API.process + '/api/eval/worker-candidates?limit=30'); } catch (e) { E.cands = { error: e.message }; }
    const h = q('[data-r="cands"]'); if (h) h.innerHTML = renderCands();
  }

  async function runEval() {
    if (E.busy) return;
    const path = q('[data-f="path"]').value, by = q('[data-f="runBy"]').value.trim(), note = q('[data-f="runNote"]').value.trim();
    if (!by) { msg('run', UI.t('form.err.required') + ': ' + UI.t('form.by')); return; }
    E.by = by;
    const body = { path, by, note: note || null };
    if (path === 'worker') {
      body.instances = [...E.el.querySelectorAll('[data-cand]:checked')].map(n => ({ instance: n.dataset.cand }));
      if (!body.instances.length) { msg('run', '채점할 처리 건을 하나 이상 고르세요'); return; }
    } else {
      body.repeats = Math.max(1, Math.min(E.maxRepeats, Number(q('[data-f="repeats"]').value) || 1)); E.repeats = body.repeats;
      if (E.picked.size) body.items = [...E.picked];
    }
    E.busy = true; const btn = q('[data-act="run"]'); btn.disabled = true;
    const n = path === 'worker' ? body.instances.length : (body.items || E.golden).length * body.repeats;
    msg('run', `채점 중… 판단 ${n}회`, false);
    try {
      const run = await longJ(API.process + '/api/eval/runs', 'POST', body);
      msg('run', `채점 완료 — 평균 ${run.summary.score}점`, false);
      E.sel = run.id; E.run = run;
      await loadRuns(); renderDetail();
    } catch (e) { msg('run', e.message); }
    finally { E.busy = false; btn.disabled = false; }
  }

  /* ---------------------------------------------------------------- 3. 실행 기록 */
  function renderRuns() {
    const host = q('[data-r="runs"]');
    if (!E.runs.length) { host.innerHTML = UI.empty('아직 채점 실행이 없습니다', '정답표를 적고 채점을 실행하면 여기에 남습니다'); return; }
    host.innerHTML = E.runs.map(r => `<div class="item${r.id === E.sel ? ' sel' : ''}" data-run="${esc(r.id)}" tabindex="0" role="button">
      <div class="row"><strong>평균 ${esc(r.summary.score)}점 · 항목 ${esc(r.summary.items)}</strong>${UI.chipText(PATH[r.path] || r.path, r.path === 'worker' ? 'accent' : 'neutral')}</div>
      <span class="sub">${esc(UI.dateTime(r.created))} · ${esc(r.by)}${r.note ? ' · ' + esc(r.note) : ''}</span></div>`).join('');
  }
  function checkLine(key, c) {
    let detail = '';
    if (key === 'cause') detail = `판단 ${nm(c.got)} · 정답 ${nm(c.want)}` + (c.got_failure_mode !== c.want_failure_mode ? ` <small>(고장 유형 ${nm(c.got_failure_mode)} / ${nm(c.want_failure_mode)})</small>` : '');
    if (key === 'top') detail = `1위 ${nm(c.got)} · 허용 ${c.allowed.map(nm).join(', ')}`;
    if (key === 'forbidden') detail = c.detail.length ? c.detail.map(d => `${nm(d.skill)} ${esc(EXPECT[d.expect])} → ${esc(UI.idText(d.got))}${d.ok ? '' : ' ✗'}`).join(' · ') : '정답표에 빠질 조치 없음';
    if (key === 'evidence') detail = `${pct(c.ratio)}` + (c.missing.length ? ` · 빠진 근거 ${c.missing.map(nm).join(', ')}` : '');
    return `<li>${ok(c.ok)} <b>${esc(CHECK[key])}</b> ${detail}</li>`;
  }
  function itemResult(r) {
    const title = (E.golden.find(it => it.id === r.item) || {}).title || r.title;
    const repeat = r.repeats > 1 ? (r.identical ? `<p class="field-hint">${esc(r.repeats)}회 모두 같은 결과${r.deterministic ? ' — 결정론적이라 1회와 같습니다' : ''}</p>`
      : `<p class="form-msg neg">흔들림: ${esc(r.repeats)}회 중 가장 많은 결과 ${pct(r.stability)} · 점수 ${esc(r.min)}~${esc(r.max)}</p>` +
        UI.fold('회차별 결과', `<ul class="plain">${Object.entries(r.outcomes).map(([o, n]) => `<li>${esc(outcomeText(o))} — ${esc(n)}회</li>`).join('')}</ul>`)) : '';
    const mismatch = (r.facts_mismatch || []).length ? `<p class="form-msg neg">정답표의 가정과 판단 때 사실이 다릅니다: ${r.facts_mismatch.map(m => `${esc(FACT[m.key] || m.key)} 정답표 ${esc(factVal(m.key, m.want))} / 판단 때 ${esc(factVal(m.key, m.got))}`).join(' · ')}</p>` : '';
    const inst = (r.instances || []).length ? UI.fold(`채점한 처리 건 ${r.instances.length}건`, `<ul class="plain">${r.instances.map(i => `<li>${esc(i.name || UI.defName(i.instance))} · ${esc(UI.dateTime(i.started))} · 고른 조치 ${nm(i.chosen_skill)}</li>`).join('')}</ul>`) : '';
    return UI.card({ title: esc(title), chips: r.status && r.status !== 'EVALUATED' ? UI.chip(r.status) : '', value: `${esc(r.score)}점`,
      sub: `${esc(r.asset)} · ${esc(patternName(r.pattern))} · ${esc(factsText(r.facts))}`,
      body: `<p><b>판단</b> ${esc(outcomeText(r.modal_outcome))}</p>` + (r.reason ? `<p class="form-msg neg">${esc(UI.idText(r.reason))}</p>` : '') +
        `<ul class="plain">${Object.keys(CHECK).map(k => checkLine(k, r.checks[k])).join('')}</ul>` + mismatch + repeat + inst +
        UI.fold('조치 순위 (판단 원문)', `<ol>${(r.checks.top.order || []).map(o => `<li>${esc(UI.idText(o.replace(/^\d+\.\s*/, '')))}</li>`).join('') || '<li>후보 없음</li>'}</ol>`) });
  }
  function knowledgeLine(k) {
    if (!k) return '';
    return `노드 ${esc(k.nodes)} · 관계 ${esc(k.relationships)} · 조치 방법 ${esc(k.skills ?? '–')} · 규칙 ${esc(k.rules ?? '–')} · ` +
      esc(k.last_change ? '마지막 변경 ' + UI.dateTime(k.last_change) : k.last_change_note || '') + (k.fingerprint ? ` <small title="그래프 지문">· 지문 ${esc(k.fingerprint)}</small>` : '');
  }
  function renderDetail() {
    const host = q('[data-r="detail"]'), r = E.run;
    if (!r) { host.innerHTML = UI.empty('실행을 선택하세요', '항목별 점수와 검사 네 칸이 보입니다'); return; }
    const s = r.summary;
    host.innerHTML = UI.card({ title: `평균 ${esc(s.score)}점`, chips: UI.chipText(PATH[r.path] || r.path),
      sub: `${esc(UI.dateTime(r.created))} · ${esc(r.by)}${r.note ? ' · ' + esc(r.note) : ''}`,
      body: `<p>${Object.entries({ cause_hits: '원인 적중', top_ok: '1위 허용', forbidden_ok: '빠질 조치 미추천', evidence_ok: '근거 모두 포함' }).map(([k, l]) => `${esc(l)} <b>${esc(s[k])}/${esc(s.items)}</b>`).join(' · ')}` +
        (s.withheld ? ` · 판단 없음(보류 · 오류) <b>${esc(s.withheld)}</b>` : '') + (s.unstable ? ` · 흔들림 <b>${esc(s.unstable)}</b>` : '') + `</p>` +
        `<p class="field-hint">채점 때 지식: ${knowledgeLine(r.knowledge)}</p>` }) + (r.items || []).map(itemResult).join('');
  }
  async function selectRun(id) {
    E.sel = id; renderRuns();
    q('[data-r="detail"]').innerHTML = `<p class="field-hint">${esc(UI.t('loading'))}</p>`;
    try { E.run = await getJ(API.process + '/api/eval/runs/' + encodeURIComponent(id)); } catch (e) { E.run = null; q('[data-r="detail"]').innerHTML = `<p class="form-msg neg" role="alert">${esc(e.message)}</p>`; return; }
    renderDetail(); UI.revealDetail(q('[data-r="detail"]'));
  }

  /* ---------------------------------------------------------------- 4. 전 · 후 비교 */
  function renderCmpForm() {
    const opts = (cur) => E.runs.map(r => `<option value="${esc(r.id)}" ${r.id === cur ? 'selected' : ''}>${esc(UI.dateTime(r.created))} · ${esc(r.by)} · ${esc(r.summary.score)}점${r.note ? ' · ' + esc(r.note) : ''}</option>`).join('');
    if (E.runs.length < 2) { q('[data-r="cmpform"]').innerHTML = UI.empty('비교하려면 채점 실행이 두 개 필요합니다', '지식을 고치기 전에 한 번, 고친 뒤에 한 번 채점하세요 (예: Neo4j Browser에서 관계 하나 끊기 · 매뉴얼 하나 더 넣기)'); return; }
    q('[data-r="cmpform"]').innerHTML = `<div class="form-grid">` +
      UI.field({ label: '전 (고치기 전 실행)', input: `<select data-f="before">${opts(E.cmpBefore || E.runs[1].id)}</select>` }) +
      UI.field({ label: '후 (고친 뒤 실행)', input: `<select data-f="after">${opts(E.cmpAfter || E.runs[0].id)}</select>` }) + `</div>` +
      UI.actions(`<span class="form-msg" data-msg="cmp" role="status"></span><button type="button" class="btn primary" data-act="compare">두 실행 비교</button>`);
  }
  function renderCmp() {
    const host = q('[data-r="cmp"]'), c = E.cmp;
    if (!c) { host.innerHTML = ''; return; }
    const kd = c.knowledge || {};
    const rel = (x) => `${nm(x.from)} —${esc(x.type)}→ ${nm(x.to)}`;
    const know = !kd.comparable ? `<p class="field-hint">${esc(kd.note || '')}</p>` : !kd.changed ? '<p>두 실행 사이에 지식 그래프가 바뀌지 않았습니다.</p>' :
      `<p>노드 ${esc(kd.nodes[0])} → ${esc(kd.nodes[1])} · 관계 ${esc(kd.relationships[0])} → ${esc(kd.relationships[1])}</p>` +
      (kd.counts ? `<ul class="plain">${(kd.removed_rels || []).map(x => `<li>${UI.chipText('끊김', 'danger')} ${rel(x)}</li>`).join('')}${(kd.added_rels || []).map(x => `<li>${UI.chipText('생김', 'success')} ${rel(x)}</li>`).join('')}` +
        `${(kd.added_nodes || []).length ? `<li>${UI.chipText('새 항목', 'success')} ${kd.added_nodes.map(nm).join(', ')}</li>` : ''}${(kd.removed_nodes || []).length ? `<li>${UI.chipText('없어진 항목', 'danger')} ${kd.removed_nodes.map(nm).join(', ')}</li>` : ''}` +
        `${(kd.changed_nodes || []).length ? `<li>${UI.chipText('속성 바뀜', 'warning')} ${kd.changed_nodes.map(nm).join(', ')}</li>` : ''}</ul>` : `<p class="field-hint">${esc(kd.note || '')}</p>`);
    const verdict = { improved: ['좋아짐', 'success'], regressed: ['나빠짐', 'danger'], same: ['같음', 'neutral'] };
    host.innerHTML = UI.card({ title: `평균 ${c.delta == null ? '–' : (c.delta > 0 ? '+' : '') + esc(c.delta)}점`, chips: UI.chipText(`좋아짐 ${c.improved}`, 'success') + UI.chipText(`나빠짐 ${c.regressed}`, c.regressed ? 'danger' : 'neutral') + UI.chipText(`같음 ${c.same}`),
      sub: `전 ${esc(UI.dateTime(c.before.created))} ${esc(c.before.note || '')} → 후 ${esc(UI.dateTime(c.after.created))} ${esc(c.after.note || '')}`,
      body: `<h4>두 실행 사이 지식 변화</h4>${know}` +
        (c.golden_changed.length ? `<p class="form-msg neg">정답표가 두 실행 사이에 바뀐 항목: ${c.golden_changed.map(i => esc((E.golden.find(it => it.id === i) || {}).title || i)).join(', ')} — 이 항목의 점수 변화는 지식이 아니라 정답 때문일 수 있습니다.</p>` : '') +
        `<div class="table-scroll"><table><thead><tr><th>항목</th><th>전</th><th>후</th><th>변화</th><th>바뀐 검사</th><th>판단 전 → 후</th></tr></thead><tbody>${c.rows.map(r => `<tr>
          <td>${esc(r.title)}</td><td>${esc(r.before)}</td><td>${esc(r.after)}</td><td>${UI.chipText((r.delta > 0 ? '+' : '') + r.delta + ' · ' + verdict[r.verdict][0], verdict[r.verdict][1])}</td>
          <td>${r.changed.map(x => `${esc(CHECK[x.check])} ${x.before ? '맞음' : '틀림'}→${x.after ? '맞음' : '틀림'}`).join('<br>') || '–'}${r.evidence_lost.length ? `<br><small>잃은 근거 ${r.evidence_lost.map(nm).join(', ')}</small>` : ''}${r.evidence_gained.length ? `<br><small>얻은 근거 ${r.evidence_gained.map(nm).join(', ')}</small>` : ''}</td>
          <td><small>${esc(outcomeText(r.outcome_before))}<br>→ ${esc(outcomeText(r.outcome_after))}</small></td></tr>`).join('')}</tbody></table></div>` +
        (c.only_before.length || c.only_after.length ? `<p class="field-hint">한쪽에만 있는 항목: ${[...c.only_before, ...c.only_after].map(esc).join(', ')}</p>` : '') });
  }
  async function compare() {
    E.cmpBefore = q('[data-f="before"]').value; E.cmpAfter = q('[data-f="after"]').value;
    if (E.cmpBefore === E.cmpAfter) { msg('cmp', '서로 다른 두 실행을 고르세요'); return; }
    msg('cmp', UI.t('loading'), false);
    try { E.cmp = await getJ(API.process + '/api/eval/compare?' + new URLSearchParams({ before: E.cmpBefore, after: E.cmpAfter })); msg('cmp', ''); }
    catch (e) { E.cmp = null; msg('cmp', e.message); }
    renderCmp();
  }

  /* ---------------------------------------------------------------- 이벤트 · 읽기 */
  async function onClick(e) {
    const t = e.target.closest('[data-act],[data-edit],[data-run]');
    if (!t || E.busy && t.dataset.act !== 'cancel') return;
    if (t.dataset.edit) { E.editing = { item: E.golden.find(it => it.id === t.dataset.edit) }; renderForm(); return; }
    if (t.dataset.run) { selectRun(t.dataset.run); return; }
    const act = t.dataset.act;
    if (act === 'reload') return load();
    if (act === 'new') { E.editing = { item: null }; renderForm(); return; }
    if (act === 'cancel') { E.editing = null; renderForm(); return; }
    if (act === 'run') return runEval();
    if (act === 'compare') return compare();
    if (act === 'save' || act === 'delete') {
      E.busy = true;
      try {
        if (act === 'save') {
          const { by, item } = readForm();
          const url = API.process + '/api/eval/golden/items' + (E.editing.item ? '/' + encodeURIComponent(item.id) : '');
          await postJ(url, { item, by }, E.editing.item ? 'PUT' : 'POST');
        } else {
          const by = (q('[data-f="by"]').value || '').trim();
          if (!by) throw new Error(UI.t('form.err.required') + ': ' + UI.t('form.by'));
          await requestJ(API.process + '/api/eval/golden/items/' + encodeURIComponent(E.editing.item.id) + '?by=' + encodeURIComponent(by), { method: 'DELETE' });
          E.picked.delete(E.editing.item.id);
        }
        E.editing = null; renderForm(); await loadGolden();
      } catch (err) { msg('form', err.message); }
      finally { E.busy = false; }
    }
  }
  function onChange(e) {
    const t = e.target;
    if (t.dataset.pick) { t.checked ? E.picked.add(t.dataset.pick) : E.picked.delete(t.dataset.pick); renderRunForm(); return; }
    if (t.dataset.f === 'path') { E.path = t.value; renderRunForm(); if (t.value === 'worker') loadCands(); }
  }
  function onInput(e) {
    const f = e.target.dataset.f, p = f && q(`[data-preview="${f}"]`);
    if (p) p.innerHTML = namePreview(f === 'forbidden' ? e.target.value.replace(/=.*$/gm, '') : e.target.value);
  }
  E.onKey = (e) => { const t = e.target.closest('[data-run]'); if (t && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); selectRun(t.dataset.run); } };

  async function loadGolden() {
    try {
      const g = await getJ(API.process + '/api/eval/golden');
      E.golden = g.items || []; E.storage = g.storage; E.paths = g.paths || {}; E.maxRepeats = g.max_repeats || 10;
      for (const id of [...E.picked]) if (!E.golden.some(it => it.id === id)) E.picked.delete(id);
      renderGolden();
    } catch (e) { E.golden = []; q('[data-r="golden"]').innerHTML = `<p class="form-msg neg" role="alert">정답표를 읽지 못했습니다: ${esc(e.message)}</p>`; }
    renderRunForm(); renderStats();
  }
  async function loadRuns() {
    try { E.runs = await getJ(API.process + '/api/eval/runs?limit=50'); renderRuns(); }
    catch (e) { E.runs = []; q('[data-r="runs"]').innerHTML = `<p class="form-msg neg" role="alert">실행 기록을 읽지 못했습니다: ${esc(e.message)}</p>`; }
    renderCmpForm(); renderStats();
  }
  async function load() {
    try { E.patterns = await getJ(API.agent + '/api/ontology/patterns'); E.patternError = ''; } catch (e) { E.patterns = null; E.patternError = '이상 패턴 목록을 읽지 못했습니다: ' + e.message; }
    try { E.knowledge = await getJ(API.process + '/api/eval/knowledge'); E.knowledgeError = ''; } catch (e) { E.knowledge = null; E.knowledgeError = '지식 상태를 읽지 못했습니다: ' + e.message; }
    await Promise.all([loadGolden(), loadRuns()]);
    if (E.sel) selectRun(E.sel); else renderDetail();
    if (E.path === 'worker') loadCands();
  }
  function mount(el) {
    if (!el) throw new Error('판단 채점 화면을 그릴 자리가 없습니다');
    if (E.el !== el) { E.el = el; skeleton(); el.addEventListener('keydown', E.onKey); }
    return load();
  }
  window.hydEval = { mount };

  // 포털 셸이 아직 mount 를 부르지 않으면: 판단 채점 화면이 처음 보일 때 그린다.
  const view = document.getElementById('view-evaluation'), host = document.getElementById('evalView');
  if (view && host) {
    const once = () => { if (view.classList.contains('active') && E.el !== host) mount(host); };
    new MutationObserver(once).observe(view, { attributes: true, attributeFilter: ['class'] });
    once();
  }
})();
