/* A7 손익 · What-if · 규칙 바꿔 보기 — 시험 실행만. window.hydWhatif.mount(el)
   판단 한 번을 읽기 전용으로 계산해 기준으로 삼고(POST /api/agent/whatif), 시험값 · 규칙 시험값은 그 기준의 사본에만 적용한다.
   업무 DB · 지식 그래프 · 순위 정책은 바뀌지 않는다("원래대로"는 시험값을 비우고 기준 결과로 돌아간다).
   요약(지금 1순위 · 무엇이 바뀌었나)을 먼저, 상세(항목별 출처 · 경계값 · 계수)는 접어 둔다. */
(function () {
  const W = { el: null, asset: 'HYD-01', pattern: '', patterns: null, base: null, view: null, bounds: null, boundsMsg: '', tab: 'money',
    busy: false, msg: '', values: {}, policy: { weights: {}, penalties: {} }, weeks: null, weeksForm: { card: '', variable: 'load_pct', value: '', weeks: 4 },
    ruleForm: { target: '', value: '' } };
  const won = v => v == null ? '미확인' : `${v < 0 ? '−' : v > 0 ? '+' : ''}${Math.abs(v).toLocaleString('ko-KR')}원`;
  const num = (v, unit) => v == null ? '–' : `${Number(v).toLocaleString('ko-KR', { maximumFractionDigits: 3 })}${unit ? ' ' + unit : ''}`;
  const tone = { '데이터': 'success', '문서': 'accent', '가정': 'warning', '시험값': 'danger' };
  const kindLabel = { decision: '판단 순위', money: '손익 순위' };
  const trialCount = () => Object.keys(W.values).length + Object.keys(W.policy.weights).length + Object.keys(W.policy.penalties).length;
  const cardName = id => ((W.view || W.base)?.cards || []).find(c => c.id === id)?.name || '없음';

  async function call(path, body) { return postJ(API.agent + '/api/agent/whatif' + path, body || {}); }

  function mount(el) {
    W.el = el;
    render();
    if (!W.patterns) getJ(API.agent + '/api/ontology/patterns').then(p => { W.patterns = p || []; if (!W.pattern && W.patterns[0]) W.pattern = W.patterns[0].code; render(); })
      .catch(e => { W.patterns = []; W.msg = '이상 패턴 목록을 읽지 못했습니다: ' + e.message; render(); });
  }

  async function load() {
    if (W.busy) return;
    W.busy = true; W.msg = ''; W.base = W.view = W.bounds = W.weeks = null; W.values = {}; W.policy = { weights: {}, penalties: {} }; render();
    try {
      W.base = W.view = await call('', { asset: W.asset, pattern: W.pattern });
      const first = W.base.cards.find(c => c.feasible);
      W.weeksForm.card = first ? first.id : '';
      W.boundsMsg = '경계값을 계산하는 중…';
      call(`/${W.base.id}/boundaries`, {}).then(r => { if (W.base && r.id === W.base.id) { W.bounds = r.boundaries; W.boundsMsg = ''; render(); } })
        .catch(e => { W.boundsMsg = '경계값을 계산하지 못했습니다: ' + e.message; render(); });
    } catch (e) { W.msg = '시험 기준을 만들지 못했습니다: ' + e.message; }
    finally { W.busy = false; render(); }
  }

  async function retry() {
    if (!W.base || W.busy) return;
    W.busy = true; W.msg = ''; render();
    try { W.view = await call(`/${W.base.id}/try`, { values: W.values, policy: W.policy }); }
    catch (e) { W.msg = '다시 계산하지 못했습니다: ' + e.message; }
    finally { W.busy = false; render(); }
  }

  function reset() { W.values = {}; W.policy = { weights: {}, penalties: {} }; W.view = W.base; W.weeks = null; W.msg = ''; render(); }

  async function runWeeks() {
    if (!W.base || W.busy) return;
    const f = W.weeksForm;
    if (!f.card) { W.msg = '몇 주 What-if를 볼 카드를 고르세요'; render(); return; }
    W.busy = true; W.msg = ''; render();
    try {
      const change = f.value === '' ? {} : { [f.variable]: Number(f.value) };
      W.weeks = await call(`/${W.base.id}/weeks`, { card: f.card, weeks: Number(f.weeks) || 4, change, policy: W.policy });
    } catch (e) { W.msg = '몇 주 What-if를 계산하지 못했습니다: ' + e.message; }
    finally { W.busy = false; render(); }
  }

  function applyBoundary(i) {
    const b = (W.bounds || [])[i]; if (!b) return;
    W.values = { ...(b.trial || {}) };
    W.policy = { weights: { ...((b.policy || {}).weights || {}) }, penalties: { ...((b.policy || {}).penalties || {}) } };
    W.tab = b.variable.startsWith('w:') || b.variable.startsWith('p:') ? 'rules' : 'values';
    retry();
  }

  /* ---------------------------------------------------------------- 그리기 */
  function render() {
    if (!W.el) return;
    const pats = (W.patterns || []).map(p => `<option value="${esc(p.code)}" ${p.code === W.pattern ? 'selected' : ''}>${esc(p.name)}${p.failureModes && p.failureModes.length ? ' → ' + esc(p.failureModes.join(', ')) : ''}</option>`).join('');
    let html = UI.card({ title: '시험 기준 불러오기', body: `<div class="form-grid">
        <div class="field"><label for="wiAsset">설비</label><select id="wiAsset">${['HYD-01', 'HYD-02', 'HYD-03'].map(a => `<option ${a === W.asset ? 'selected' : ''}>${a}</option>`).join('')}</select></div>
        <div class="field wide-2"><label for="wiPattern">이상 패턴</label><select id="wiPattern">${pats}</select></div></div>
        <p class="field-hint">판단을 한 번 계산해 기준으로 삼습니다. 아래에서 바꾸는 값은 이 계산에만 쓰고 업무 DB · 지식 · 순위 정책은 그대로 둡니다.</p>`,
      actions: `<button class="btn primary" id="wiLoad" ${W.busy || !W.pattern ? 'disabled' : ''}>${W.busy && !W.base ? '계산 중…' : '불러오기'}</button>` });
    if (W.msg) html += `<p class="neg" role="status">${esc(W.msg)}</p>`;
    const v = W.view;
    if (!v) { W.el.innerHTML = html + UI.empty('설비와 이상 패턴을 고르고 불러오기를 누르세요', '카드별 손익(원), 1순위가 바뀌는 값, 몇 주 뒤 지표를 시험해 봅니다'); wire(); return; }
    html += summaryHtml(v);
    html += UI.tabs([['money', '카드별 손익'], ['values', '값 바꿔 보기', Object.keys(W.values).length || null], ['weeks', '몇 주 What-if'],
      ['rules', '규칙 바꿔 보기', Object.keys(W.policy.weights).length + Object.keys(W.policy.penalties).length || null]], W.tab, 'data-wi-tab');
    html += `<div class="tab-pane ${W.tab === 'money' ? 'on' : ''}">${moneyPane(v)}</div><div class="tab-pane ${W.tab === 'values' ? 'on' : ''}">${valuesPane(v)}</div>`
      + `<div class="tab-pane ${W.tab === 'weeks' ? 'on' : ''}">${weeksPane(v)}</div><div class="tab-pane ${W.tab === 'rules' ? 'on' : ''}">${rulesPane(v)}</div>`;
    W.el.innerHTML = html;
    wire();
  }

  function summaryHtml(v) {
    const n = trialCount();
    const chips = UI.chipText(`판단 1순위 · ${cardName(v.top.decision)}`, 'accent') + ' ' + UI.chipText(`손익 1순위 · ${cardName(v.top.money)}`, 'success')
      + ' ' + (v.original && v.original.unchanged ? UI.chipText('원본 그대로', 'neutral') : UI.chipText('원본 확인 실패', 'danger'))
      + (n ? ' ' + UI.chipText(`시험값 ${n}개 적용 중`, 'warning') : '') + (W.busy ? ' ' + UI.chipText('다시 계산하는 중…', 'neutral') : '');
    return `<div class="summary prose" style="margin-top:var(--s4)"><p style="margin:0 0 var(--s2)">${esc(v.summary)}</p><div class="card-chips">${chips}</div>`
      + `${n ? `<div class="form-actions" style="margin-top:var(--s2)"><button class="btn" id="wiReset">원래대로</button></div>` : ''}`
      + UI.fold('기준 판단', `<p style="margin:0">${esc(UI.idText(v.cause && v.cause.name || ''))}${v.cause && v.cause.failureMode ? ' · ' + esc(UI.idText(v.cause.failureMode)) : ''} · ${esc(v.asset)} · ${esc(UI.dateTime(v.created))}</p><p class="muted" style="margin:0">${esc(v.original ? v.original.note : '')}</p>`, { cls: 'small' })
      + '</div>';
  }

  function moneyTable(m) {
    return `<table class="compact-table"><thead><tr><th>항목</th><th>손익</th><th>계산</th><th>출처</th></tr></thead><tbody>${m.items.map(i => `<tr>
      <td>${esc(i.label)}</td><td class="num ${i.value_won < 0 ? 'neg' : ''}">${i.value_won == null ? `<span class="neg">미확인</span>` : esc(won(i.value_won))}</td>
      <td>${esc(i.formula || i.missing || '')}</td>
      <td>${(i.sources || []).map(s => `<div>${UI.chipText(s.kind, tone[s.kind] || 'neutral')} ${esc(s.where)}</div>`).join('') || '<span class="neg">출처 없음</span>'}
        ${(i.sources || []).some(s => s.ref) ? UI.fold('원천 위치', (i.sources || []).filter(s => s.ref).map(s => `<div class="muted">${esc(s.ref)}</div>`).join(''), { cls: 'small' }) : ''}</td></tr>`).join('')}</tbody></table>
      <p class="field-hint">${esc(m.basis || '')}${m.hours != null ? ` · 기간 ${num(m.hours, 'h')}` : ''}</p>`;
  }

  function boundaryLines(list) {
    if (!W.bounds) return `<p class="muted">${esc(W.boundsMsg || '경계값이 아직 없습니다')}</p>`;
    if (!list.length) return '<p class="muted">시험 범위 안에서 1순위를 바꾸는 값이 없습니다.</p>';
    return list.map(b => `<div class="kv-line">${UI.chipText(kindLabel[b.kind], b.kind === 'money' ? 'success' : 'accent')} ${esc(b.label)} ${esc(num(b.base, b.unit))} → <b>${esc(num(b.value, b.unit))} ${esc(b.direction)}</b>이면 1순위 '${esc(b.topAfterName || '없음')}'
      <button type="button" class="btn small" data-wi-bound="${W.bounds.indexOf(b)}">이 값으로 계산</button></div>`).join('');
  }

  function moneyPane(v) {
    const list = v.cards.slice().sort((a, b) => (a.decisionRank || 99) - (b.decisionRank || 99));
    return `<div class="stack-list">${list.map(c => {
      const chips = (c.feasible ? UI.chipText(`판단 ${c.decisionRank}위`, c.id === v.top.decision ? 'accent' : 'neutral') : UI.chipText('규정상 제외', 'danger'))
        + ' ' + (c.moneyRank ? UI.chipText(`손익 ${c.moneyRank}위`, c.id === v.top.money ? 'success' : 'neutral') : UI.chipText('손익 순위 없음', 'neutral'));
      const mine = (W.bounds || []).filter(b => b.card === c.id);
      return UI.card({ title: esc(UI.idText(c.name)), chips,
        value: `<span class="kv ${c.money.total_won < 0 ? 'neg' : ''}">${esc(won(c.money.total_won))}<small>예상 손익</small></span><span class="kv">${esc(c.score)}<small>정책 점수</small></span>`,
        sub: c.feasible ? (c.money.complete ? '' : esc('계산하지 못한 항목: ' + c.money.missing.join(', '))) : esc(c.excluded.join(' · ')),
        body: UI.fold(`항목별 손익 · 출처 <span class="chip tone-neutral sm">${c.money.items.length}</span>`, moneyTable(c.money), { cls: 'small' })
          + UI.fold(`1순위가 바뀌는 값${W.bounds ? ` <span class="chip tone-neutral sm">${mine.length}</span>` : ''}`, boundaryLines(mine), { cls: 'small' }) });
    }).join('')}</div>`;
  }

  function compareTable(v) {
    const base = Object.fromEntries((W.base.cards || []).map(c => [c.id, c]));
    const arrow = (a, b, f) => a === b ? esc(f(b)) : `<span class="muted">${esc(f(a))}</span> → <b>${esc(f(b))}</b>`;
    const rank = r => r ? r + '위' : '–';
    return `<table class="compact-table"><thead><tr><th>카드</th><th>판단 순위</th><th>정책 점수</th><th>손익 순위</th><th>예상 손익</th></tr></thead><tbody>${v.cards.map(c => {
      const b = base[c.id] || {};
      return `<tr class="${c.id === v.top.decision || c.id === v.top.money ? 'rec' : ''}"><td>${esc(UI.idText(c.name))}${c.feasible ? '' : ' ' + UI.chipText('제외', 'danger')}</td>
        <td>${arrow(b.decisionRank, c.decisionRank, rank)}</td><td>${arrow(b.score, c.score, x => x == null ? '–' : String(x))}</td>
        <td>${arrow(b.moneyRank, c.moneyRank, rank)}</td><td class="num">${arrow(b.money && b.money.total_won, c.money.total_won, won)}</td></tr>`;
    }).join('')}</tbody></table>`;
  }

  function valuesPane(v) {
    const vars = v.variables.filter(x => x.kinds.includes('decision') || x.kinds.includes('money'));
    const fields = vars.map(x => UI.field({ label: `${x.label} (${x.unit})`, hint: x.source.kind === '데이터' ? `${x.source.where.split(' · ')[0]} 값 ${num(x.base, x.unit)}` : `${x.source.kind} · ${x.source.where}`,
      input: `<input type="number" step="any" data-wi-var="${esc(x.id)}" value="${W.values[x.id] ?? ''}" placeholder="${esc(x.base ?? '')}">` })).join('');
    const near = (W.bounds || []).filter(b => !b.variable.includes(':')).reduce((acc, b) => {
      const k = b.variable + b.kind; if (!acc[k] || Math.abs(b.value - b.base) < Math.abs(acc[k].value - acc[k].base)) acc[k] = b; return acc; }, {});
    return `<p class="field-hint">빈 칸은 업무 DB 값 그대로입니다. 값을 넣고 다시 계산하면 두 순위와 손익이 기준 대비 어떻게 바뀌는지 보입니다.</p>`
      + `<div class="form-grid">${fields}</div>` + UI.actions(`<button class="btn primary" id="wiTry" ${W.busy ? 'disabled' : ''}>다시 계산</button>`)
      + compareTable(v)
      + UI.fold('값마다 가장 가까운 경계값', boundaryLines(Object.values(near)), { cls: 'small' });
  }

  function rulesPane(v) {
    const p = v.policy || { components: [], penalties: [] };
    const opts = p.components.map(c => [`w:${c.key}`, `순위 항목 '${c.label}' 가중치 (기준 1배)`])
      .concat(p.penalties.map(r => [`p:${r.rule}`, `감점 규칙 '${UI.idText(r.annotation || r.rule)}' 감점 (기준 ${r.penalty})`]));
    if (!W.ruleForm.target && opts[0]) W.ruleForm.target = opts[0][0];
    const ruleBounds = (W.bounds || []).filter(b => b.variable.includes(':'));
    return `<p class="field-hint">순위 정책 항목 하나의 가중치나 감점 규칙 하나의 감점을 시험값으로 바꿉니다. 정책 원본은 그대로이며, 바꾼 식도 같은 안전 검사를 다시 통과해야 계산됩니다.</p>`
      + `<div class="form-grid">${UI.field({ label: '바꿀 규칙', input: `<select id="wiRuleTarget">${opts.map(([k, l]) => `<option value="${esc(k)}" ${k === W.ruleForm.target ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select>` })}`
      + UI.field({ label: '시험값', hint: '가중치는 −10 ~ 10배, 감점은 0 ~ 1000', input: `<input type="number" step="any" id="wiRuleValue" value="${esc(W.ruleForm.value)}">` }) + '</div>'
      + UI.actions(`<button class="btn primary" id="wiRule" ${W.busy ? 'disabled' : ''}>다시 계산</button>`)
      + compareTable(v)
      + UI.fold('규칙마다 1순위가 바뀌는 값', boundaryLines(ruleBounds), { cls: 'small' })
      + UI.fold('순위 식 원문', p.components.map(c => `<div>${esc(c.label)}: <code>${esc(c.expr)}</code></div>`).join(''), { cls: 'small' });
  }

  function weeksPane(v) {
    const f = W.weeksForm, w = W.weeks;
    const cardOpts = v.cards.filter(c => c.feasible).map(c => `<option value="${esc(c.id)}" ${c.id === f.card ? 'selected' : ''}>${esc(UI.idText(c.name))}</option>`).join('');
    const vars = [{ id: 'load_pct', label: '조치 부하 설정', unit: '%' }].concat(v.variables.filter(x => x.kinds.includes('weeks')));
    let html = `<p class="field-hint">조치 → 설비 값(부하 · 팬) → 지표(가동률 · 생산량 · 비용 · 이익)를 영향 계수로 이어 주별로 계산합니다. 값 하나만 바꿉니다. 같은 입력은 같은 결과입니다.</p>`
      + `<div class="form-grid">${UI.field({ label: '조치 카드', input: `<select id="wiWCard">${cardOpts}</select>` })}`
      + UI.field({ label: '바꿀 값', input: `<select id="wiWVar">${vars.map(x => `<option value="${esc(x.id)}" ${x.id === f.variable ? 'selected' : ''}>${esc(x.label)} (${esc(x.unit)})</option>`).join('')}</select>` })
      + UI.field({ label: '새 값', hint: '비우면 기준만 계산합니다', input: `<input type="number" step="any" id="wiWValue" value="${esc(f.value)}">` })
      + UI.field({ label: '기간 (주)', input: `<input type="number" min="1" max="12" id="wiWWeeks" value="${esc(f.weeks)}">` }) + '</div>'
      + UI.actions(`<button class="btn primary" id="wiWeeks" ${W.busy ? 'disabled' : ''}>주별 계산</button>`);
    if (!w) return html + UI.empty('카드와 바꿀 값을 고르고 주별 계산을 누르세요', '');
    const last = rows => rows && rows[rows.length - 1];
    const b = last(w.base), c = last(w.changed);
    html += `<div class="summary prose"><p style="margin:0">'${esc(UI.idText(w.cardName))}' ${w.weeks}주 누적 이익: 기준 ${esc(won(b.cum_profit_won))}`
      + (c ? ` · ${esc(w.change.label)} ${esc(num(w.change.base, w.change.unit))} → ${esc(num(w.change.value, w.change.unit))}이면 <b>${esc(won(c.cum_profit_won))}</b> (차이 ${esc(won(c.cum_profit_won == null || b.cum_profit_won == null ? null : c.cum_profit_won - b.cum_profit_won))})` : '')
      + `</p>${w.missing && w.missing.length ? `<p class="neg" style="margin:0">계수 없음: ${esc(w.missing.join(', '))}</p>` : ''}</div>`;
    const cell = (r0, r1, k, f) => !r1 || r1[k] === r0[k] ? esc(f(r0[k])) : `<span class="muted">${esc(f(r0[k]))}</span> → <b>${esc(f(r1[k]))}</b>`;
    html += `<table class="compact-table"><thead><tr><th>주</th><th>가동률</th><th>생산량</th><th>매출</th><th>비용</th><th>이익</th><th>누적 이익</th></tr></thead><tbody>${w.base.map((r0, i) => {
      const r1 = w.changed && w.changed[i];
      return `<tr><td style="white-space:nowrap">${r0.week}주</td><td>${cell(r0, r1, 'availability', x => num(x, '%'))}</td><td>${cell(r0, r1, 'output', x => num(x, 'ea'))}</td>
        <td class="num">${cell(r0, r1, 'revenue_won', won)}</td><td class="num">${cell(r0, r1, 'cost_won', x => x == null ? '미확인' : `${x.toLocaleString('ko-KR')}원`)}</td>
        <td class="num">${cell(r0, r1, 'profit_won', won)}</td><td class="num">${cell(r0, r1, 'cum_profit_won', won)}</td></tr>`;
    }).join('')}</tbody></table>`;
    html += UI.fold(`조치 → 설비 값 → 지표 연결 <span class="chip tone-neutral sm">${(w.paths || []).length}</span>`,
      (w.paths || []).map(p => `<div class="kv-line">${esc(UI.idText(p.join(' → ')))}</div>`).join('') || '<p class="muted">지식 지도에 이 카드의 영향 경로가 없습니다.</p>', { cls: 'small' });
    html += UI.fold(`영향 계수와 출처 <span class="chip tone-neutral sm">${w.coefficients.length}</span>`,
      `<table class="compact-table"><thead><tr><th>계수</th><th>값</th><th>출처</th></tr></thead><tbody>${w.coefficients.map(k => `<tr><td>${esc(k.label)}</td><td class="num">${k.value == null ? '규칙' : esc(num(k.value, k.unit))}</td>
        <td>${UI.chipText(k.kind, tone[k.kind] || 'neutral')} ${esc(k.source)}</td></tr>`).join('')}</tbody></table>`, { cls: 'small' });
    return html;
  }

  function wire() {
    const el = W.el, q = s => el.querySelector(s);
    q('#wiAsset')?.addEventListener('change', e => { W.asset = e.target.value; });
    q('#wiPattern')?.addEventListener('change', e => { W.pattern = e.target.value; });
    q('#wiLoad')?.addEventListener('click', load);
    q('#wiReset')?.addEventListener('click', reset);
    el.querySelectorAll('[data-wi-tab]').forEach(b => b.addEventListener('click', () => { W.tab = b.dataset.wiTab; render(); }));
    el.querySelectorAll('[data-wi-bound]').forEach(b => b.addEventListener('click', () => applyBoundary(Number(b.dataset.wiBound))));
    el.querySelectorAll('[data-wi-var]').forEach(i => i.addEventListener('change', () => {
      if (i.value === '') delete W.values[i.dataset.wiVar]; else W.values[i.dataset.wiVar] = Number(i.value);
    }));
    q('#wiTry')?.addEventListener('click', retry);
    q('#wiRuleTarget')?.addEventListener('change', e => { W.ruleForm.target = e.target.value; });
    q('#wiRuleValue')?.addEventListener('change', e => { W.ruleForm.value = e.target.value; });
    q('#wiRule')?.addEventListener('click', () => {
      const t = W.ruleForm.target, val = W.ruleForm.value;
      W.policy = { weights: {}, penalties: {} };
      if (val !== '' && t) (t.startsWith('w:') ? W.policy.weights : W.policy.penalties)[t.slice(2)] = Number(val);
      retry();
    });
    q('#wiWCard')?.addEventListener('change', e => { W.weeksForm.card = e.target.value; });
    q('#wiWVar')?.addEventListener('change', e => { W.weeksForm.variable = e.target.value; });
    q('#wiWValue')?.addEventListener('change', e => { W.weeksForm.value = e.target.value; });
    q('#wiWWeeks')?.addEventListener('change', e => { W.weeksForm.weeks = e.target.value; });
    q('#wiWeeks')?.addEventListener('click', runWeeks);
  }

  // 조치 판단 카드에 붙는 손익 접기 (enterprise.js cardHtml). 합계는 접힌 줄에 바로 보인다.
  function moneyFold(m) {
    const rows = m.items.map(i => `<div style="margin-bottom:var(--s2)"><div class="kv-line"><b>${esc(i.label)}</b> ${i.value_won == null ? '<span class="neg">미확인</span>' : `<span class="${i.value_won < 0 ? 'neg' : ''}">${esc(won(i.value_won))}</span>`}</div>`
      + `<div class="muted">${esc(i.formula || i.missing || '')}</div>`
      + UI.fold(`출처 ${(i.sources || []).length}`, (i.sources || []).map(x => `<div>${UI.chipText(x.kind, tone[x.kind] || 'neutral')} ${esc(x.where)}</div>`).join('') || '<span class="neg">출처 없음</span>', { cls: 'small' }) + '</div>').join('');
    return UI.fold(`예상 손익 <b class="${m.total_won < 0 ? 'neg' : ''}">${esc(won(m.total_won))}</b>${m.complete ? '' : ' <span class="chip tone-warning sm">일부 미확인</span>'}`,
      rows + `<p class="field-hint">${esc(m.basis || '')} · 값 바꿔 보기와 경계값은 '손익 · What-if' 화면에서</p>`, { cls: 'small' });
  }

  window.hydWhatif = { mount, moneyFold };
  // 셸(shell.js MOUNTS.whatif)이 #/whatif 를 처음 열 때 mount(#whatifView)를 부른다.
})();
