/* A7 조건별 손익 · 규칙 바꿔 보기 — 시험 실행만. window.hydWhatif.mount(el)
   판단 한 번을 읽기 전용으로 계산해 기준으로 삼고(POST /api/agent/whatif), 시험값 · 규칙 시험값은 그 기준의 사본에만 적용한다.
   업무 DB · 지식 그래프 · 순위 정책은 바뀌지 않는다("원래대로"는 시험값을 비우고 기준 결과로 돌아간다).
   짜임(디자인 기준 5-8 「입력 → 결과」): 왼쪽에 조건(시험 기준 → 바꿔 볼 것과 그 칸 · 계산 단추), 오른쪽에 결과(결론 문장 → 1순위 → 카드별 순위와 손익 표 → 내역).
   색은 상태에만 쓴다 — 출처의 종류(데이터 · 문서 · 가정 · 시험값)와 순위의 종류는 글로 쓴다. 계수 · 연결 경로 · 순위 식 원문은 「자세히」 접기 안에 있다.
   B5: 규칙 탭의 "관점 중요도" — 성과 관점(이름은 지식 그래프에서)마다 비중을 주면 카드 점수의 성과 지표 득실이 그 비중으로 다시 계산된다. */
(function () {
  const W = { el: null, asset: 'HYD-01', pattern: '', patterns: null, base: null, view: null, bounds: null, boundsMsg: '', tab: 'money',
    busy: false, msg: '', card: '', values: {}, policy: { weights: {}, penalties: {}, perspectives: {} }, perspForm: {}, weeks: null, weeksForm: { card: '', variable: 'load_pct', value: '', weeks: 4 },
    ruleForm: { target: '', value: '' } };
  const won = v => v == null ? '미확인' : `${v < 0 ? '−' : v > 0 ? '+' : ''}${Math.abs(v).toLocaleString('ko-KR')}원`;
  const num = (v, unit) => v == null ? '–' : `${Number(v).toLocaleString('ko-KR', { maximumFractionDigits: 3 })}${unit ? ' ' + unit : ''}`;
  const group = (label, body) => body ? `<section class="rd-group"><h3 class="rd-label">${label}</h3>${body}</section>` : '';
  const kv = rows => { const r = rows.filter(([, x]) => x != null && x !== ''); return r.length ? `<dl class="kv">${r.map(([k, x]) => `<dt>${esc(k)}</dt><dd>${x}</dd>`).join('')}</dl>` : ''; };
  // 출처 한 줄: 종류 · 어디서. 원천 위치(표 · 열 경로)는 그 줄에 마우스를 올리면 보인다
  const sourceLines = list => (list || []).map(s => `<div${s.ref ? ` title="${esc(s.ref)}"` : ''}>${esc(s.kind)} · ${esc(s.where)}</div>`).join('') || '<span class="neg">출처 없음</span>';
  const kindLabel = { decision: '판단 순위', money: '손익 순위' };
  const ruleCount = () => Object.keys(W.policy.weights).length + Object.keys(W.policy.penalties).length + Object.keys(W.policy.perspectives || {}).length;
  const trialCount = () => Object.keys(W.values).length + ruleCount();
  const cardName = id => ((W.view || W.base)?.cards || []).find(c => c.id === id)?.name || '없음';

  async function call(path, body) { return postJ(API.agent + '/api/agent/whatif' + path, body || {}); }

  function mount(el) {
    W.el = el;
    render();
    if (!W.patterns) getJ(API.agent + '/api/ontology/patterns').then(p => { W.patterns = p || []; W.patternsError = ''; if (!W.pattern && W.patterns[0]) W.pattern = W.patterns[0].code; render(); })
      .catch(e => { W.patterns = null; W.patternsError = e.message; render(); });
  }
  // 패턴 목록을 못 읽었으면 셸이 메뉴를 다시 열 때 새로 읽는다
  const failed = () => !W.patterns && !!W.patternsError;

  async function load() {
    if (W.busy) return;
    W.busy = true; W.msg = ''; W.base = W.view = W.bounds = W.weeks = null; W.values = {}; W.policy = { weights: {}, penalties: {}, perspectives: {} }; W.perspForm = {}; render();
    try {
      const asked = { asset: W.asset, pattern: W.pattern };
      W.base = W.view = await call('', asked);
      W.loaded = asked;      // 아래 결과가 어느 설비 · 이상 패턴의 것인지(고르기 칸을 바꾸면 render 가 어긋남을 알린다)
      const first = W.base.cards.find(c => c.feasible);
      W.weeksForm.card = first ? first.id : '';
      W.card = W.base.top.decision || (first ? first.id : '');
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

  // 시험값 한도는 서버(agentsvc whatif 시작 응답 limits)가 정한다 — 화면에 숫자 사본을 두지 않는다(W3-26)
  function lim(key) {
    const v = W.base && W.base.limits && W.base.limits[key];
    if (!Array.isArray(v) || v.length !== 2) throw new Error(`조건별 손익 시작 응답에 한도(${key})가 없습니다 — 서비스가 이 화면과 다른 판일 수 있습니다`);
    return v;
  }
  function reset() { W.values = {}; W.policy = { weights: {}, penalties: {}, perspectives: {} }; W.perspForm = {}; W.view = W.base; W.weeks = null; W.msg = ''; render(); }

  async function runWeeks() {
    if (!W.base || W.busy) return;
    const f = W.weeksForm;
    if (!f.card) { W.msg = '주간 조건별 예측을 볼 카드를 고르세요'; render(); return; }
    W.busy = true; W.msg = ''; render();
    try {
      const change = f.value === '' ? {} : { [f.variable]: Number(f.value) };
      W.weeks = await call(`/${W.base.id}/weeks`, { card: f.card, weeks: Number(f.weeks) || 4, change, policy: W.policy });
    } catch (e) { W.msg = '주간 조건별 예측을 계산하지 못했습니다: ' + e.message; }
    finally { W.busy = false; render(); }
  }

  function applyBoundary(i) {
    const b = (W.bounds || [])[i]; if (!b) return;
    W.values = { ...(b.trial || {}) };
    W.policy = { weights: { ...((b.policy || {}).weights || {}) }, penalties: { ...((b.policy || {}).penalties || {}) }, perspectives: { ...((b.policy || {}).perspectives || {}) } };
    W.perspForm = { ...W.policy.perspectives };
    W.tab = b.variable.startsWith('w:') || b.variable.startsWith('p:') || b.variable.startsWith('v:') ? 'rules' : 'values';
    retry();
  }

  /* ---------------------------------------------------------------- 그리기 */
  const TABS = [['money', '기준 그대로'], ['values', '업무 값'], ['rules', '규칙 · 관점'], ['weeks', '주별 예측']];
  function render() {
    if (!W.el) return;
    const pats = (W.patterns || []).map(p => `<option value="${esc(p.code)}" ${p.code === W.pattern ? 'selected' : ''}>${esc(p.name)}${p.failureModes && p.failureModes.length ? ' → ' + esc(p.failureModes.join(', ')) : ''}</option>`).join('');
    const v = W.view;
    const stale = v && W.loaded && (W.loaded.asset !== W.asset || W.loaded.pattern !== W.pattern);
    const count = { values: Object.keys(W.values).length || null, rules: ruleCount() || null };
    // 왼쪽: 조건. 주 단추는 하나 — 기준을 불러오기 전에는 [불러오기], 불러온 뒤에는 고른 보기의 계산 단추
    let left = `<h2 class="rd-label">시험 기준</h2>
        <div class="field"><label for="wiAsset">설비</label><select id="wiAsset">${['HYD-01', 'HYD-02', 'HYD-03'].map(a => `<option ${a === W.asset ? 'selected' : ''}>${a}</option>`).join('')}</select></div>
        <div class="field"><label for="wiPattern">이상 패턴</label><select id="wiPattern">${pats}</select></div>
        <div class="rd-in-actions"><button class="btn${v ? '' : ' primary'}" id="wiLoad" ${W.busy || !W.pattern ? 'disabled' : ''}>${W.busy && !W.base ? '계산 중…' : v ? '다시 불러오기' : '불러오기'}</button></div>
        <p class="rd-in-note">판단을 한 번 계산해 기준으로 삼습니다. 바꾸는 값은 이 계산에만 쓰고 업무 DB · 지식 · 순위 정책은 그대로 둡니다.</p>`;
    if (stale) left += `<p class="rd-in-note" role="status">설비나 이상 패턴을 바꿨습니다. 오른쪽은 앞서 불러온 ${esc(W.loaded.asset)}의 결과이며, [다시 불러오기]를 눌러야 바뀝니다.</p>`;
    if (v) left += `<hr class="rd-rule"><h2 class="rd-label">바꿔 볼 것</h2><div class="rd-seg" role="tablist" aria-label="바꿔 볼 것">${TABS.map(([k, l]) =>
      `<button type="button" role="tab" class="${k === W.tab ? 'on' : ''}" data-wi-tab="${k}" aria-selected="${k === W.tab}">${esc(l)}${count[k] ? `<span class="n">${count[k]}</span>` : ''}</button>`).join('')}</div>` + inputsPane(v);
    // 오른쪽: 결과
    let right = W.patternsError && !W.patterns ? UI.errorBlock('이상 패턴 목록을 읽지 못했습니다', W.patternsError, { retry: true, cls: 'compact' }) : '';
    if (W.msg) right += `<p class="field-error" role="alert">${esc(W.msg)}</p>`;
    right += v ? resultPane(v) : W.busy ? UI.loading('시험 기준을 계산하는 중', 'compact')
      : UI.empty('아직 불러온 시험 기준이 없습니다', '왼쪽에서 설비와 이상 패턴을 고르고 [불러오기]를 누르면 카드별 손익(원), 1순위가 바뀌는 값, 몇 주 뒤 지표를 시험해 볼 수 있습니다.', 'compact');
    const html = `<p class="page-lead">판단 한 번을 기준으로 잡고 업무 값과 규칙을 시험값으로 바꿔, 조치의 순위와 손익이 어떻게 달라지는지 봅니다.</p>` +
      `<div class="rd-io"><div class="rd-in">${left}</div><div class="rd-out">${right}</div></div>`;
    // 다시 그리기(경계값 도착 · 다시 계산 결과)가 치던 칸의 포커스 · 커서와 펼친 접기를 지우지 않게(값은 input 이벤트로 이미 상태에 있다)
    const a = document.activeElement, key = a && W.el.contains(a) ? focusKey(a) : null, typed = key && /^(INPUT|TEXTAREA)$/.test(a.tagName) ? a.value : null;
    let caret = null; try { caret = a && typeof a.selectionStart === 'number' ? [a.selectionStart, a.selectionEnd] : null; } catch (_) { caret = null; }
    const open = new Set([...W.el.querySelectorAll('details[open] > summary')].map(x => x.textContent.trim()));
    W.el.innerHTML = html;
    W.el.querySelectorAll('details > summary').forEach(x => { if (open.has(x.textContent.trim())) x.parentElement.open = true; });
    wire();
    const next = key && W.el.querySelector(key);
    if (next && !next.disabled) { if (typed != null && next.value !== typed) next.value = typed; next.focus({ preventScroll: true }); if (caret && next.setSelectionRange) { try { next.setSelectionRange(...caret); } catch (_) { /* 커서 없는 칸 */ } } }
  }
  function focusKey(x) {
    if (x.id) return '#' + CSS.escape(x.id);
    const attrs = [...x.attributes].filter(a => a.name.startsWith('data-')).map(a => `[${a.name}="${CSS.escape(a.value)}"]`).join('');
    return attrs ? x.tagName.toLowerCase() + attrs : null;
  }

  /* ---------- 왼쪽: 고른 보기의 입력 칸과 계산 단추 ---------- */
  function inputsPane(v) {
    if (W.tab === 'values') {
      const vars = v.variables.filter(x => x.kinds.includes('decision') || x.kinds.includes('money'));
      return vars.map(x => UI.field({ label: `${x.label} (${x.unit})`, hint: x.source.kind === '데이터' ? `${x.source.where.split(' · ')[0]} 값 ${num(x.base, x.unit)}` : `${x.source.kind} · ${x.source.where}`,
        input: `<input type="number" step="any" data-wi-var="${esc(x.id)}" value="${W.values[x.id] ?? ''}" placeholder="${esc(x.base ?? '')}">` })).join('') +
        `<div class="rd-in-actions"><button class="btn primary" id="wiTry" ${W.busy ? 'disabled' : ''}>다시 계산</button></div>` +
        `<p class="rd-in-note">빈 칸은 업무 DB 값 그대로입니다. 값을 넣고 다시 계산하면 두 순위와 손익이 기준에서 어떻게 바뀌는지 오른쪽에 보입니다.</p>`;
    }
    if (W.tab === 'rules') {
      const p = v.policy || { components: [], penalties: [] };
      const opts = p.components.map(c => [`w:${c.key}`, `순위 항목 '${c.label}' 가중치 (기준 1배)`])
        .concat(p.penalties.map(r => [`p:${r.rule}`, `감점 규칙 '${UI.idText(r.annotation || r.rule)}' 감점 (기준 ${r.penalty})`]));
      if (!W.ruleForm.target && opts[0]) W.ruleForm.target = opts[0][0];
      const pv = v.perspectives || { available: false, reason: '관점 정보가 없습니다', perspectives: [] };
      // B5 관점 중요도: 이름 · 지표 소속은 지식 그래프(Perspective ← Objective ← Measure)에서. 기준은 모두 1배
      const persp = !pv.available ? `<p class="field-error">${esc(pv.reason || '')}</p>`
        : pv.perspectives.map(x => UI.field({ label: `${x.name} (배)`,
            hint: x.inUse ? '이 판단의 득실: ' + x.measures.join(', ') : '이 판단의 카드 득실에 나오지 않는 관점입니다. 바꿔도 순위가 그대로입니다',
            input: `<input type="number" step="any" min="${lim('perspectives')[0]}" max="${lim('perspectives')[1]}" data-wi-persp="${esc(x.id)}" value="${esc(W.perspForm[x.id] ?? '')}" placeholder="1">` })).join('') +
          `<div class="rd-in-actions"><button class="btn" id="wiPersp" ${W.busy ? 'disabled' : ''}>관점 비중으로 다시 계산</button></div>` +
          `<p class="rd-in-note">성과 관점마다 중요도(배)를 주면 카드 점수의 성과 지표 득실이 그 비중으로 다시 계산됩니다. 빈 칸은 1배이고 0은 그 관점을 보지 않습니다.</p>`;
      return UI.field({ label: '바꿀 규칙', input: `<select id="wiRuleTarget">${opts.map(([k, l]) => `<option value="${esc(k)}" ${k === W.ruleForm.target ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select>` }) +
        UI.field({ label: '시험값', hint: `가중치는 ${lim('weights')[0]} ~ ${lim('weights')[1]}배, 감점은 ${lim('penalties')[0]} ~ ${lim('penalties')[1]}`, input: `<input type="number" step="any" id="wiRuleValue" value="${esc(W.ruleForm.value)}">` }) +
        `<div class="rd-in-actions"><button class="btn primary" id="wiRule" ${W.busy ? 'disabled' : ''}>다시 계산</button></div>` +
        `<p class="rd-in-note">순위 정책 항목 하나의 가중치나 감점 규칙 하나의 감점을 시험값으로 바꿉니다. 바꾼 식도 같은 안전 검사를 다시 통과해야 계산됩니다.</p>` +
        `<hr class="rd-rule"><h2 class="rd-label">관점 중요도</h2>` + persp;
    }
    if (W.tab === 'weeks') {
      const f = W.weeksForm;
      const cardOpts = v.cards.filter(c => c.feasible).map(c => `<option value="${esc(c.id)}" ${c.id === f.card ? 'selected' : ''}>${esc(UI.idText(c.name))}</option>`).join('');
      const vars = [{ id: 'load_pct', label: '조치 부하 설정', unit: '%' }].concat(v.variables.filter(x => x.kinds.includes('weeks')));
      return UI.field({ label: '조치 카드', input: `<select id="wiWCard">${cardOpts}</select>` }) +
        UI.field({ label: '바꿀 값', input: `<select id="wiWVar">${vars.map(x => `<option value="${esc(x.id)}" ${x.id === f.variable ? 'selected' : ''}>${esc(x.label)} (${esc(x.unit)})</option>`).join('')}</select>` }) +
        UI.field({ label: '새 값', hint: '비우면 기준만 계산합니다', input: `<input type="number" step="any" id="wiWValue" value="${esc(f.value)}">` }) +
        UI.field({ label: '기간 (주)', input: `<input type="number" min="${lim('weeks')[0]}" max="${lim('weeks')[1]}" id="wiWWeeks" value="${esc(f.weeks)}">` }) +
        `<div class="rd-in-actions"><button class="btn primary" id="wiWeeks" ${W.busy ? 'disabled' : ''}>주별 계산</button></div>` +
        `<p class="rd-in-note">조치 → 설비 값(부하 · 팬) → 지표(가동률 · 생산량 · 비용 · 이익)를 영향 계수로 이어 주별로 계산합니다. 값 하나만 바꿉니다.</p>`;
    }
    return `<p class="rd-in-note">시험값 없이 기준 판단의 순위와 손익을 봅니다. 값이나 규칙을 바꿔 보려면 위에서 고릅니다.</p>`;
  }

  /* ---------- 오른쪽: 결론 → 1순위 → 표 → 내역 → 자세히 ---------- */
  // 평가 범위 안내(규칙 비교 · 모의 순위이고 실제 승인 준비는 확인하지 않음)는 결과 맨 아래에 둔다 — 첫 줄은 결론이다
  function resultPane(v) { return resultBody(v) + `<div class="rd-group">${UI.evaluationHtml(v)}</div>`; }
  function resultBody(v) {
    const n = trialCount();
    const cause = [UI.idText(v.cause && v.cause.name || ''), v.cause && v.cause.failureMode ? UI.idText(v.cause.failureMode) : '', v.asset, UI.dateTime(v.created)].filter(Boolean).join(' · ');
    let html = `<h2 class="rd-conclusion">${esc(v.summary)}</h2>` +
      kv([['판단 1순위', esc(cardName(v.top.decision))], ['손익 1순위', esc(cardName(v.top.money))], ['기준 판단', esc(cause)],
        ['시험값', n ? `<span class="rd-inline">${n}개 적용 중<button class="btn small" id="wiReset">원래대로</button></span>` : '없음 (업무 DB와 지식의 값 그대로)']]) +      // 원본이 바뀌었으면 서버(agentsvc main)가 500 으로 거절해 이 응답이 오지 않는다(W3-25)
      (v.original && v.original.note ? `<p class="rd-note rd-after">${esc(v.original.note)}</p>` : '') +
      (W.busy ? UI.loading('다시 계산하는 중', 'compact') : '');
    if (W.tab === 'weeks') return html + weeksResult();
    html += group(n ? '카드별 순위와 손익 · 기준 → 시험값' : '카드별 순위와 손익', compareTable(v));
    if (W.tab === 'money') html += cardDetail(v);
    if (W.tab === 'values') {
      const near = (W.bounds || []).filter(b => !b.variable.includes(':')).reduce((acc, b) => {
        const k = b.variable + b.kind; if (!acc[k] || Math.abs(b.value - b.base) < Math.abs(acc[k].value - acc[k].base)) acc[k] = b; return acc; }, {});
      html += group('값마다 1순위가 바뀌는 가장 가까운 값', boundaryLines(Object.values(near)));
    }
    if (W.tab === 'rules') {
      const p = v.policy || { components: [], penalties: [] };
      html += group('규칙마다 1순위가 바뀌는 값', boundaryLines((W.bounds || []).filter(b => b.variable.includes(':')))) + perspectiveTable(v) +
        `<div class="rd-group">${UI.fold('자세히 · 순위 식 원문', p.components.map(c => `<div>${esc(c.label)}: <code>${esc(c.expr)}</code></div>`).join(''), { cls: 'small' })}</div>`;
    }
    return html;
  }

  function moneyTable(m) {
    return `<div class="rd-scroll"><table class="tbl"><thead><tr><th>항목</th><th class="r">손익</th><th>계산</th><th>출처</th></tr></thead><tbody>${m.items.map(i => `<tr>
      <td>${esc(i.label)}</td><td class="r ${i.value_won < 0 ? 'neg' : ''}">${i.value_won == null ? `<span class="neg">미확인</span>` : esc(won(i.value_won))}</td>
      <td>${esc(i.formula || i.missing || '')}</td><td>${sourceLines(i.sources)}</td></tr>`).join('')}</tbody></table></div>
      <p class="rd-note">${esc(m.basis || '')}${m.hours != null ? ` · 기간 ${num(m.hours, '시간')}` : ''}</p>`;
  }

  function boundaryLines(list) {
    if (!W.bounds) return `<p class="rd-note">${esc(W.boundsMsg || '경계값이 아직 없습니다')}</p>`;
    if (!list.length) return '<p class="rd-note">시험 범위 안에서 1순위를 바꾸는 값이 없습니다.</p>';
    return `<ul class="rd-lines">${list.map(b => `<li><span>${esc(kindLabel[b.kind])} · ${esc(b.label)} ${esc(num(b.base, b.unit))} → <b>${esc(num(b.value, b.unit))} ${esc(b.direction)}</b>이면 1순위가 '${esc(b.topAfterName || '없음')}'</span>
      <button type="button" class="btn small" data-wi-bound="${W.bounds.indexOf(b)}">이 값으로 계산</button></li>`).join('')}</ul>`;
  }

  // 카드 하나의 손익 내역: 카드를 고르면 항목별 손익 · 출처와, 그 카드에서 1순위가 바뀌는 값이 보인다
  function cardDetail(v) {
    const list = v.cards.slice().sort((a, b) => (a.decisionRank || 99) - (b.decisionRank || 99));
    const c = list.find(x => x.id === W.card) || list[0];
    if (!c) return '';
    const picks = `<div class="rd-picks" role="group" aria-label="내역을 볼 카드">${list.map(x => `<button type="button" class="btn small${x.id === c.id ? '' : ' ghost'}" aria-pressed="${x.id === c.id}" data-wi-card="${esc(x.id)}">${esc(UI.idText(x.name))}</button>`).join('')}</div>`;
    const why = c.feasible ? (c.money.complete ? '' : '계산하지 못한 항목: ' + c.money.missing.join(', ')) : '규정상 제외 — ' + c.excluded.join(' · ');
    return group('카드별 손익 내역', picks + (why ? `<p class="rd-note">${esc(why)}</p>` : '') + moneyTable(c.money)) +
      group(`'${esc(UI.idText(c.name))}'에서 1순위가 바뀌는 값`, boundaryLines((W.bounds || []).filter(b => b.card === c.id)));
  }

  function compareTable(v) {
    const base = Object.fromEntries((W.base.cards || []).map(c => [c.id, c]));
    const arrow = (a, b, f) => a === b ? esc(f(b)) : `<span class="muted">${esc(f(a))}</span> → <b>${esc(f(b))}</b>`;
    const rank = r => r ? r + '위' : '–';
    const list = v.cards.slice().sort((a, b) => (a.decisionRank || 99) - (b.decisionRank || 99));      // 1순위가 맨 위(기준 5-3 「고른 줄을 맨 위에」)
    return `<div class="rd-scroll"><table class="tbl"><thead><tr><th>카드</th><th>판단 순위</th><th class="r">정책 점수</th><th>손익 순위</th><th class="r">예상 손익</th></tr></thead><tbody>${list.map(c => {
      const b = base[c.id] || {};
      return `<tr class="${c.id === v.top.decision ? 'pick' : ''}"><td>${esc(UI.idText(c.name))}${c.feasible ? '' : ' ' + UI.chipText('제외', 'danger')}</td>
        <td>${arrow(b.decisionRank, c.decisionRank, rank)}</td><td class="r">${arrow(b.score, c.score, x => x == null ? '–' : String(x))}</td>
        <td>${arrow(b.moneyRank, c.moneyRank, rank)}</td><td class="r">${arrow(b.money && b.money.total_won, c.money.total_won, won)}</td></tr>`;
    }).join('')}</tbody></table></div>`;
  }

  function perspectiveTable(v) {
    const pv = v.perspectives || { available: false, perspectives: [] };
    if (!pv.available) return '';
    const names = Object.fromEntries(pv.perspectives.map(p => [p.id, p.name]));
    const base = Object.fromEntries((W.base.cards || []).map(c => [c.id, c]));
    const cell = (c, pid) => { const x = (c.bscByPerspective || []).find(y => y.perspective === pid); return x ? `이득 ${num(x.gain)} · 손실 ${num(x.loss)}` : '–'; };
    const used = pv.perspectives.filter(p => p.inUse);
    return group('카드별 관점 득실', `<div class="rd-scroll"><table class="tbl"><thead><tr><th>카드</th>${used.map(p => `<th>${esc(p.name)}</th>`).join('')}<th class="r">성과 지표 점수</th></tr></thead><tbody>${v.cards.map(c => {
      const b = base[c.id] || {}, b0 = (b.scoreParts || {}).bsc, b1 = (c.scoreParts || {}).bsc;
      return `<tr><td>${esc(UI.idText(c.name))}</td>${used.map(p => `<td>${cell(c, p.id)}</td>`).join('')}<td class="r">${b0 === b1 ? esc(num(b1)) : `<span class="muted">${esc(num(b0))}</span> → <b>${esc(num(b1))}</b>`}</td></tr>`;
    }).join('')}</tbody></table></div>${Object.keys(W.policy.perspectives || {}).length ? `<p class="rd-note">적용 중: ${Object.entries(W.policy.perspectives).map(([k, x]) => `${esc(names[k] || '관점')} ${num(x)}배`).join(' · ')}</p>` : ''}`);
  }

  function weeksResult() {
    const w = W.weeks;
    if (!w) return UI.empty('아직 주별로 계산한 결과가 없습니다', '왼쪽에서 조치 카드와 바꿀 값을 고르고 [주별 계산]을 누릅니다.', 'compact');
    const last = rows => rows && rows[rows.length - 1];
    const b = last(w.base), c = last(w.changed);
    let html = `<section class="rd-group"><h3 class="rd-label">주별 예측</h3><p class="rd-conclusion">'${esc(UI.idText(w.cardName))}' ${w.weeks}주 누적 이익: 기준 ${esc(won(b.cum_profit_won))}`
      + (c ? ` · ${esc(w.change.label)} ${esc(num(w.change.base, w.change.unit))} → ${esc(num(w.change.value, w.change.unit))}이면 ${esc(won(c.cum_profit_won))} (차이 ${esc(won(c.cum_profit_won == null || b.cum_profit_won == null ? null : c.cum_profit_won - b.cum_profit_won))})` : '')
      + `</p>${w.missing && w.missing.length ? `<p class="field-error">계수 없음: ${esc(w.missing.join(', '))}</p>` : ''}`;
    const cell = (r0, r1, k, f) => !r1 || r1[k] === r0[k] ? esc(f(r0[k])) : `<span class="muted">${esc(f(r0[k]))}</span> → <b>${esc(f(r1[k]))}</b>`;
    html += `<div class="rd-scroll"><table class="tbl"><thead><tr><th>주</th><th class="r">가동률</th><th class="r">생산량</th><th class="r">매출</th><th class="r">비용</th><th class="r">이익</th><th class="r">누적 이익</th></tr></thead><tbody>${w.base.map((r0, i) => {
      const r1 = w.changed && w.changed[i];
      return `<tr><td class="r">${r0.week}주</td><td class="r">${cell(r0, r1, 'availability', x => num(x, '%'))}</td><td class="r">${cell(r0, r1, 'output', x => num(x, '개'))}</td>
        <td class="r">${cell(r0, r1, 'revenue_won', won)}</td><td class="r">${cell(r0, r1, 'cost_won', x => x == null ? '미확인' : `${x.toLocaleString('ko-KR')}원`)}</td>
        <td class="r">${cell(r0, r1, 'profit_won', won)}</td><td class="r">${cell(r0, r1, 'cum_profit_won', won)}</td></tr>`;
    }).join('')}</tbody></table></div></section>`;
    const paths = (w.paths || []).map(p => `<li><span>${esc(UI.idText(p.join(' → ')))}</span></li>`).join('');
    html += `<div class="rd-group">${UI.fold('자세히 · 조치 → 설비 값 → 지표 연결 · 영향 계수와 출처',
      group('조치 → 설비 값 → 지표 연결', paths ? `<ul class="rd-lines">${paths}</ul>` : '<p class="rd-note">지식 지도에 이 카드의 영향 경로가 없습니다.</p>') +
      group('영향 계수와 출처', `<div class="rd-scroll"><table class="tbl"><thead><tr><th>계수</th><th class="r">값</th><th>출처</th></tr></thead><tbody>${w.coefficients.map(k => `<tr><td>${esc(k.label)}</td><td class="r">${k.value == null ? '규칙' : esc(num(k.value, k.unit))}</td>
        <td>${esc(k.kind)} · ${esc(k.source)}</td></tr>`).join('')}</tbody></table></div>`), { cls: 'small' })}</div>`;
    return html;
  }

  function wire() {
    const el = W.el, q = s => el.querySelector(s);
    // 결과가 떠 있는 동안 설비 · 이상 패턴을 바꾸면 다시 그려, 아래 결과가 앞서 불러온 것임을 알린다
    q('#wiAsset')?.addEventListener('change', e => { W.asset = e.target.value; if (W.view) render(); });
    q('#wiPattern')?.addEventListener('change', e => { W.pattern = e.target.value; if (W.view) render(); });
    q('#wiLoad')?.addEventListener('click', load);
    q('[data-retry]')?.addEventListener('click', () => { W.patternsError = ''; mount(W.el); });      // 이상 패턴 목록을 다시 읽는다
    el.querySelectorAll('[data-wi-card]').forEach(b => b.addEventListener('click', () => { W.card = b.dataset.wiCard; render(); }));
    q('#wiReset')?.addEventListener('click', reset);
    el.querySelectorAll('[data-wi-tab]').forEach(b => b.addEventListener('click', () => { W.tab = b.dataset.wiTab; render(); }));
    el.querySelectorAll('[data-wi-bound]').forEach(b => b.addEventListener('click', () => applyBoundary(Number(b.dataset.wiBound))));
    // 값은 칠 때마다(input) 상태에 담는다 — change(포커스를 뺄 때)만 쓰면 그 사이 다시 그리기가 친 값을 지웠다
    const both = (node, fn) => { node?.addEventListener('input', fn); node?.addEventListener('change', fn); };
    el.querySelectorAll('[data-wi-var]').forEach(i => both(i, () => {
      if (i.value === '') delete W.values[i.dataset.wiVar]; else W.values[i.dataset.wiVar] = Number(i.value);
    }));
    q('#wiTry')?.addEventListener('click', retry);
    q('#wiRuleTarget')?.addEventListener('change', e => { W.ruleForm.target = e.target.value; });
    both(q('#wiRuleValue'), e => { W.ruleForm.value = e.target.value; });
    q('#wiRule')?.addEventListener('click', () => {
      const t = W.ruleForm.target, val = W.ruleForm.value;
      W.policy = { weights: {}, penalties: {}, perspectives: {} }; W.perspForm = {};
      if (val !== '' && t) (t.startsWith('w:') ? W.policy.weights : W.policy.penalties)[t.slice(2)] = Number(val);
      retry();
    });
    el.querySelectorAll('[data-wi-persp]').forEach(i => both(i, () => {
      if (i.value === '') delete W.perspForm[i.dataset.wiPersp]; else W.perspForm[i.dataset.wiPersp] = Number(i.value);
    }));
    q('#wiPersp')?.addEventListener('click', () => { W.policy = { weights: {}, penalties: {}, perspectives: { ...W.perspForm } }; retry(); });
    q('#wiWCard')?.addEventListener('change', e => { W.weeksForm.card = e.target.value; });
    q('#wiWVar')?.addEventListener('change', e => { W.weeksForm.variable = e.target.value; });
    both(q('#wiWValue'), e => { W.weeksForm.value = e.target.value; });
    both(q('#wiWWeeks'), e => { W.weeksForm.weeks = e.target.value; });
    q('#wiWeeks')?.addEventListener('click', runWeeks);
  }

  // 조치 판단 카드에 붙는 손익 접기 (enterprise.js cardHtml). 합계는 접힌 줄에 바로 보인다.
  function moneyFold(m) {
    const rows = m.items.map(i => `<tr><td>${esc(i.label)}<small>${esc(i.formula || i.missing || '')}</small></td>` +
      `<td class="r ${i.value_won < 0 ? 'neg' : ''}">${i.value_won == null ? '<span class="neg">미확인</span>' : esc(won(i.value_won))}</td><td>${sourceLines(i.sources)}</td></tr>`).join('');
    return UI.fold(`예상 손익 <b class="${m.total_won < 0 ? 'neg' : ''}">${esc(won(m.total_won))}</b>${m.complete || m.total_won == null ? '' : ' · 일부 미확인'}`,
      `<div class="rd-scroll"><table class="tbl"><thead><tr><th>항목 · 계산</th><th class="r">손익</th><th>출처</th></tr></thead><tbody>${rows}</tbody></table></div>` +
      `<p class="rd-note">${esc(m.basis || '')} <a href="#/whatif">조건별 손익에서 값 바꿔 보기 →</a></p>`, { cls: 'small' });
  }

  window.hydWhatif = { mount, failed, moneyFold };
  // 셸(shell.js MOUNTS.whatif)이 #/whatif 를 처음 열 때 mount(#whatifView)를 부른다.
})();
