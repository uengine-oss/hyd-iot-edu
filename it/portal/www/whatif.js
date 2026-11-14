/* A7 조건별 손익 · 규칙 바꿔 보기 — 시험 실행만. window.hydWhatif.mount(el)
   판단 한 번을 읽기 전용으로 계산해 기준으로 삼고(POST /api/agent/whatif), 시험값 · 규칙 시험값은 그 기준의 사본에만 적용한다.
   업무 DB · 지식 그래프 · 순위 정책은 바뀌지 않는다("원래대로"는 시험값을 비우고 기준 결과로 돌아간다).
   짜임(디자인 기준 5-6 「조건 → 결과」): 왼쪽 조건 판(시험 기준 → 바꿔 볼 것과 그 칸 · 계산 단추), 오른쪽 결과 판(결론 한 줄과 숫자 넷 → 조치 후보별 순위와 손익(.opts) → 내역 · 1순위가 바뀌는 값 → 원문 접기).
   부품은 키트의 것(panel · fieldset · field · seg · turn-facts · opts · table · fold)이고 격자는 reading.css(.io)다. 색은 상태에만 쓴다 — 출처의 종류(데이터 · 문서 · 가정 · 시험값)와 순위의 종류는 글로 쓴다.
   B5: 「규칙」 보기의 "관점 중요도" — 성과 관점(이름은 지식 그래프에서)마다 비중을 주면 조치 점수의 성과 지표 득실이 그 비중으로 다시 계산된다. */
(function () {
  const W = { el: null, asset: '', assets: null, assetsError: '', pattern: '', patterns: null, base: null, view: null, bounds: null, boundsMsg: '', tab: 'money',
    busy: false, msg: '', card: '', values: {}, policy: { weights: {}, penalties: {}, perspectives: {} }, perspForm: {}, weeks: null, weeksForm: { card: '', variable: 'load_pct', value: '', weeks: 4 },
    ruleForm: { target: '', value: '' } };
  const won = v => v == null ? '미확인' : `${v < 0 ? '−' : v > 0 ? '+' : ''}${Math.abs(v).toLocaleString('ko-KR')}원`;
  const num = (v, unit) => v == null ? '–' : `${Number(v).toLocaleString('ko-KR', { maximumFractionDigits: 3 })}${unit ? ' ' + unit : ''}`;
  const sec = (title, side, body) => body ? `<div class="panel-sec"><h3>${title}${side ? `<span class="muted">${side}</span>` : ''}</h3>${body}</div>` : '';
  const fact = (label, value) => `<div><dt>${esc(label)}</dt><dd>${value}</dd></div>`;
  const note = (text, attrs = '') => text ? `<p class="muted"${attrs}>${text}</p>` : '';
  // 출처 한 줄: 종류 · 어디서. 원천 위치(표 · 열 경로)는 그 줄에 마우스를 올리면 보인다
  const sourceLines = list => (list || []).map(s => `<div${s.ref ? ` title="${esc(s.ref)}"` : ''}>${esc(s.kind)} · ${esc(plainUnits(s.where))}</div>`).join('') || '<span class="muted">출처 없음</span>';
  const kindLabel = { decision: '판단 순위', money: '손익 순위' };
  const ruleCount = () => Object.keys(W.policy.weights).length + Object.keys(W.policy.penalties).length + Object.keys(W.policy.perspectives || {}).length;
  const trialCount = () => Object.keys(W.values).length + ruleCount();
  const cardOf = id => ((W.view || W.base)?.cards || []).find(c => c.id === id);
  const cardName = id => { const c = cardOf(id); return c ? UI.idText(c.name) : '없음'; };

  async function call(path, body) { return postJ(API.agent + '/api/agent/whatif' + path, body || {}); }

  function mount(el) {
    W.el = el;
    render();
    // 설비 목록은 서버가 준다(plant /api/state 의 units — 유압 설비 화면이 읽는 그 응답). 화면에 설비 이름을 적어 두지 않는다
    if (!W.assets) getJ(API.plant + '/api/state').then(p => { W.assets = Object.keys((p && p.units) || {}); W.assetsError = W.assets.length ? '' : '설비 상태 응답에 설비가 없습니다'; if (!W.asset) W.asset = W.assets[0] || ''; render(); })
      .catch(e => { W.assets = null; W.assetsError = e.message; render(); });
    if (!W.patterns) getJ(API.agent + '/api/ontology/patterns').then(p => { W.patterns = p || []; W.patternsError = ''; if (!W.pattern && W.patterns[0]) W.pattern = W.patterns[0].code; render(); })
      .catch(e => { W.patterns = null; W.patternsError = e.message; render(); });
  }
  // 패턴 목록을 못 읽었으면 셸이 메뉴를 다시 열 때 새로 읽는다
  const failed = () => (!W.patterns && !!W.patternsError) || (!W.assets && !!W.assetsError);

  async function load() {
    if (W.busy) return;
    W.busy = true; W.busySince = new Date().toISOString(); W.msg = ''; W.base = W.view = W.bounds = W.weeks = null; W.values = {}; W.policy = { weights: {}, penalties: {}, perspectives: {} }; W.perspForm = {}; render();
    try {
      const asked = { asset: W.asset, pattern: W.pattern };
      W.base = W.view = await call('', asked);
      W.loaded = asked;      // 아래 결과가 어느 설비 · 이상 패턴의 것인지(고르기 칸을 바꾸면 render 가 어긋남을 알린다)
      const first = W.base.cards.find(c => c.feasible);
      W.weeksForm.card = first ? first.id : '';
      W.card = W.base.top.decision || (first ? first.id : '');
      W.boundsMsg = ''; W.boundsSince = new Date().toISOString();
      call(`/${W.base.id}/boundaries`, {}).then(r => { if (W.base && r.id === W.base.id) { W.bounds = r.boundaries; W.boundsSince = null; render(); } })
        .catch(e => { W.boundsSince = null; W.boundsMsg = '1순위가 바뀌는 값을 계산하지 못했습니다: ' + e.message; render(); });
    } catch (e) { W.msg = '시험 기준을 만들지 못했습니다: ' + e.message; }
    finally { W.busy = false; render(); }
  }

  async function retry() {
    if (!W.base || W.busy) return;
    W.busy = true; W.busySince = new Date().toISOString(); W.msg = ''; render();
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
    if (!f.card) { W.msg = '주별 예측을 볼 조치를 고르세요'; render(); return; }
    W.busy = true; W.busySince = new Date().toISOString(); W.msg = ''; render();
    try {
      const change = f.value === '' ? {} : { [f.variable]: Number(f.value) };
      W.weeks = await call(`/${W.base.id}/weeks`, { card: f.card, weeks: Number(f.weeks) || 4, change, policy: W.policy });
    } catch (e) { W.msg = '주별 예측을 계산하지 못했습니다: ' + e.message; }
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
  const TABS = [['money', '기준'], ['values', '업무 값'], ['rules', '규칙'], ['weeks', '주별']];
  const TAB_SAYS = { money: '시험값 없이 기준 판단의 순위와 손익을 봅니다.', values: '업무 값을 바꿔 순위와 손익이 어떻게 달라지는지 봅니다.',
    rules: '순위 정책의 가중치 · 감점과 성과 관점의 비중을 바꿔 봅니다.', weeks: '조치 하나를 골라 몇 주 뒤의 지표를 봅니다.' };
  const foot = (button, msg = '') => `<footer class="form-foot">${button}</footer>${msg}`;
  function render() {
    if (!W.el) return;
    const pats = (W.patterns || []).map(p => `<option value="${esc(p.code)}" ${p.code === W.pattern ? 'selected' : ''}>${esc(p.name)}${p.failureModes && p.failureModes.length ? ' → ' + esc(p.failureModes.join(', ')) : ''}</option>`).join('');
    const v = W.view;
    const stale = v && W.loaded && (W.loaded.asset !== W.asset || W.loaded.pattern !== W.pattern);
    const count = { values: Object.keys(W.values).length || null, rules: ruleCount() || null };
    // 왼쪽: 조건 판. 주 단추는 하나 — 기준을 불러오기 전에는 [불러오기], 불러온 뒤에는 고른 보기의 계산 단추(기준 보기에서는 [다시 불러오기]가 주 단추다)
    const loadMain = !v || W.tab === 'money';
    let left = `<div class="panel-head"><div><h2>시험 조건</h2></div></div><div class="panel-sec">` +
      UI.section('시험 기준',
        UI.field({ label: '설비', input: `<select id="wiAsset" ${W.assets && W.assets.length ? '' : 'disabled'}>${(W.assets || []).map(a => `<option ${a === W.asset ? 'selected' : ''}>${esc(a)}</option>`).join('')}</select>` }) +
        UI.field({ label: '이상 패턴', input: `<select id="wiPattern">${pats}</select>`, hint: '판단을 한 번 계산해 기준으로 삼습니다. 바꾸는 값은 이 계산에만 쓰고 업무 DB · 지식 · 순위 정책은 그대로 둡니다.' })) +
      foot(`<button type="button" class="btn"${loadMain ? '' : ' data-variant="outline"'} id="wiLoad" ${W.busy || !W.pattern || !W.asset ? 'disabled' : ''}>${UI.icon(v ? 'refresh-cw' : 'play')}${v ? '다시 불러오기' : '불러오기'}</button>`) +
      (stale ? note(`설비나 이상 패턴을 바꿨습니다. 오른쪽은 앞서 불러온 ${esc(W.loaded.asset)}의 결과이며, [다시 불러오기]를 눌러야 바뀝니다.`, ' role="status"') : '') + `</div>`;
    if (v) left += `<div class="panel-sec"><fieldset class="fieldset"><legend>바꿔 볼 것</legend><div role="group">` +
      UI.viewTabs(TABS.map(([k, l]) => [k, l, count[k] || null]), W.tab, 'data-wi-tab', { label: '바꿔 볼 것', small: true }) +
      note(esc(TAB_SAYS[W.tab])) + `</div></fieldset>` + inputsPane(v) + `</div>`;
    // 오른쪽: 결과
    let right = W.patternsError && !W.patterns ? UI.errorBlock('이상 패턴 목록을 읽지 못했습니다', W.patternsError, { retry: true })
      : W.assetsError && !(W.assets && W.assets.length) ? UI.errorBlock('설비 목록을 읽지 못했습니다', W.assetsError, { retry: true }) : '';
    if (W.msg) right += UI.errorBlock('계산하지 못했습니다', W.msg);
    right += v ? resultPane(v) : W.busy ? hydLive.waitHtml('시험 기준을 계산하는 중', { since: W.busySince, hint: '고른 설비와 이상 패턴으로 판단을 한 번 계산해 기준으로 잡는 중입니다(원인 진단 → 조치 후보 → 손익).' })
      : right ? '' : `${UI.empty({ icon: 'calculator', title: `아직 불러온 시험 기준이 없습니다`, sub: `왼쪽에서 설비와 이상 패턴을 고르고 [불러오기]를 누르면 조치 후보별 손익(원), 1순위가 바뀌는 값, 몇 주 뒤 지표를 시험해 볼 수 있습니다.` })}`;
    const html = `<div class="io"><form class="panel io-in" id="wiForm" aria-label="시험 조건">${left}</form><div class="io-out" aria-live="polite">${right}</div></div>`;
    // 다시 그리기(1순위가 바뀌는 값 도착 · 다시 계산 결과)가 치던 칸의 포커스 · 커서와 펼친 접기를 지우지 않게(값은 input 이벤트로 이미 상태에 있다)
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
  const calc = (id, label) => foot(`<button type="button" class="btn" id="${id}" ${W.busy ? 'disabled' : ''}>${UI.icon('calculator')}${esc(label)}</button>`);
  function inputsPane(v) {
    if (W.tab === 'values') {
      const vars = v.variables.filter(x => x.kinds.includes('decision') || x.kinds.includes('money'));
      return UI.section('업무 값', vars.map(x => UI.field({ label: `${x.label} (${x.unit})`, hint: x.source.kind === '데이터' ? `${x.source.where.split(' · ')[0]} 값 ${num(x.base, x.unit)}` : `${x.source.kind} · ${x.source.where}`,
        input: `<input type="number" step="any" data-wi-var="${esc(x.id)}" value="${W.values[x.id] ?? ''}" placeholder="${esc(x.base ?? '')}">` })).join('')) +
        calc('wiTry', '다시 계산') + note('빈 칸은 업무 DB 값 그대로입니다.');
    }
    if (W.tab === 'rules') {
      const p = v.policy || { components: [], penalties: [] };
      const opts = p.components.map(c => [`w:${c.key}`, `순위 항목 '${c.label}' 가중치 (기준 1배)`])
        .concat(p.penalties.map(r => [`p:${r.rule}`, `감점 규칙 '${ruleShort(r.annotation || r.rule)}' 감점 (기준 ${r.penalty})`]));      // 고르기 줄에는 규칙 주석의 첫 문장만(주석 전문은 규칙 판단의 「적용한 규칙」에 있다)
      if (!W.ruleForm.target && opts[0]) W.ruleForm.target = opts[0][0];
      const pv = v.perspectives || { available: false, reason: '관점 정보가 없습니다', perspectives: [] };
      // B5 관점 중요도: 이름 · 지표 소속은 지식 그래프(Perspective ← Objective ← Measure)에서. 기준은 모두 1배
      const persp = !pv.available ? note(esc(pv.reason || ''), ' role="status"')
        : UI.section('관점 중요도', pv.perspectives.map(x => UI.field({ label: `${x.name} (배)`,
            hint: x.inUse ? '이 판단의 득실: ' + x.measures.join(', ') : '이 판단의 득실에 나오지 않는 관점입니다. 바꿔도 순위가 그대로입니다.',
            input: `<input type="number" step="any" min="${lim('perspectives')[0]}" max="${lim('perspectives')[1]}" data-wi-persp="${esc(x.id)}" value="${esc(W.perspForm[x.id] ?? '')}" placeholder="1">` })).join('')) +
          foot(`<button type="button" class="btn" data-variant="outline" id="wiPersp" ${W.busy ? 'disabled' : ''}>관점 비중으로 다시 계산</button>`) +
          note('빈 칸은 1배이고 0은 그 관점을 보지 않습니다.');
      return UI.section('규칙 하나',
        UI.field({ label: '바꿀 규칙', input: `<select id="wiRuleTarget">${opts.map(([k, l]) => `<option value="${esc(k)}" ${k === W.ruleForm.target ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select>` }) +
        UI.field({ label: '시험값', hint: `가중치는 ${lim('weights')[0]} ~ ${lim('weights')[1]}배, 감점은 ${lim('penalties')[0]} ~ ${lim('penalties')[1]}. 바꾼 식도 같은 안전 검사를 다시 통과해야 계산됩니다.`, input: `<input type="number" step="any" id="wiRuleValue" value="${esc(W.ruleForm.value)}">` })) +
        calc('wiRule', '다시 계산') + persp;
    }
    if (W.tab === 'weeks') {
      const f = W.weeksForm;
      const cardOpts = v.cards.filter(c => c.feasible).map(c => `<option value="${esc(c.id)}" ${c.id === f.card ? 'selected' : ''}>${esc(UI.idText(c.name))}</option>`).join('');
      const vars = [{ id: 'load_pct', label: '조치 부하 설정', unit: '%' }].concat(v.variables.filter(x => x.kinds.includes('weeks')));
      return UI.section('주별 예측',
        UI.field({ label: '조치', input: `<select id="wiWCard">${cardOpts}</select>` }) +
        UI.field({ label: '바꿀 값', input: `<select id="wiWVar">${vars.map(x => `<option value="${esc(x.id)}" ${x.id === f.variable ? 'selected' : ''}>${esc(x.label)} (${esc(x.unit)})</option>`).join('')}</select>` }) +
        UI.field({ label: '새 값', hint: '비우면 기준만 계산합니다.', input: `<input type="number" step="any" id="wiWValue" value="${esc(f.value)}">` }) +
        UI.field({ label: '기간 (주)', input: `<input type="number" min="${lim('weeks')[0]}" max="${lim('weeks')[1]}" id="wiWWeeks" value="${esc(f.weeks)}">`, hint: '조치 → 설비 값(부하 · 팬) → 지표(가동률 · 생산량 · 비용 · 이익)를 영향 계수로 이어 주별로 계산합니다.' })) +
        calc('wiWeeks', '주별 계산');
    }
    return '';
  }

  /* ---------- 오른쪽: 결론과 숫자 넷 → 조치 후보별 순위와 손익 → 내역 · 1순위가 바뀌는 값 → 원문 접기 ---------- */
  function resultPane(v) {
    const n = trialCount(), topD = cardOf(v.top.decision), topM = cardOf(v.top.money);
    const cause = [UI.idText(v.cause && v.cause.name || ''), v.cause && v.cause.failureMode ? UI.idText(v.cause.failureMode) : '', v.asset, UI.dateTime(v.created)].filter(Boolean).join(' · ');
    let html = `<section class="panel"><div class="panel-head"><div><div class="result-label">${UI.icon('sparkles')}결론</div><h2>${esc(v.summary)}</h2><p>${esc(cause)}</p></div></div>` +
      `<dl class="turn-facts">${fact('판단 1순위', esc(cardName(v.top.decision)))}${fact('손익 1순위', esc(cardName(v.top.money)))}` +
      `${fact('판단 1순위의 예상 손익', `<span class="num">${esc(won(topD && topD.money ? topD.money.total_won : null))}</span>${topM && topD && topM.id !== topD.id ? `<small>손익 1순위는 ${esc(won(topM.money.total_won))}</small>` : ''}`)}` +
      `${fact('시험값', n ? `<span class="num">${n}</span><small>개 적용 중</small>` : '없음<small>기준 그대로</small>')}</dl>`;
    // 원본이 바뀌었으면 서버(agentsvc main)가 500 으로 거절해 이 응답이 오지 않는다(W3-25)
    const head = (n ? `<footer class="form-foot"><span class="muted" role="status">시험값 ${n}개를 적용한 결과입니다. 업무 DB와 지식의 값은 그대로입니다.</span><button type="button" class="btn" data-variant="outline" data-size="sm" id="wiReset">${UI.icon('rotate-ccw')}원래대로</button></footer>` : '') +
      (W.busy ? hydLive.waitHtml('다시 계산하는 중', { since: W.busySince, hint: '바꾼 시험값으로 순위와 손익을 다시 계산하는 중입니다.' }) : '');
    if (head) html += `<div class="panel-sec">${head}</div>`;
    if (W.tab === 'weeks') html += weeksResult();
    else {
      html += sec('조치 후보별 순위와 손익', n ? '기준 → 시험값' : `${v.cards.length}개`, compareTable(v));
      if (W.tab === 'money') html += cardDetail(v);
      if (W.tab === 'values') {
        const near = (W.bounds || []).filter(b => !b.variable.includes(':')).reduce((acc, b) => {
          const k = b.variable + b.kind; if (!acc[k] || Math.abs(b.value - b.base) < Math.abs(acc[k].value - acc[k].base)) acc[k] = b; return acc; }, {});
        html += sec('1순위가 바뀌는 값', '업무 값마다 가장 가까운 값', boundaryTable(Object.values(near)));
      }
      if (W.tab === 'rules') {
        const p = v.policy || { components: [], penalties: [] };
        html += sec('1순위가 바뀌는 값', '규칙마다', boundaryTable((W.bounds || []).filter(b => b.variable.includes(':')))) + perspectiveTable(v) +
          `<div class="panel-sec">${UI.fold('순위 식 원문', p.components.map(c => `<p>${esc(c.label)}: <code>${esc(c.expr)}</code></p>`).join(''))}</div>`;
      }
    }
    // 평가 범위 안내(규칙 비교 · 모의 순위이고 실제 승인 준비는 확인하지 않음)는 결과 맨 아래에 둔다 — 첫 줄은 결론이다
    return html + `<div class="panel-sec">${v.original && v.original.note ? note(esc(v.original.note)) : ''}${UI.evaluationHtml(v)}</div></section>`;
  }

  // 규칙 주석의 첫 문장(마침표나 줄표 앞까지), 길면 줄인다
  const ruleShort = text => { const t = UI.idText(text), cut = t.split(/(?<=[.。])\s|\s—\s/)[0]; return cut.length > 60 ? cut.slice(0, 58) + '…' : cut; };
  // 계산식 글의 영문 단위를 화면 말로(시간 · 개). 서버가 글로 만들어 주는 식이라 단위 낱말만 바꾼다
  const plainUnits = text => String(text || '').replace(/ea\/h\b/g, '개/시간').replace(/\/h\b/g, '/시간').replace(/(\d)\s?h\b/g, '$1시간').replace(/(\d)\s?ea\b/g, '$1개');
  // 손익 내역: 첫 화면에는 합계와 항목별 금액만 둔다(결론 먼저). 항목마다의 계산식과 출처는 그 아래 접기 안이다
  function moneyTable(m) {
    const value = i => i.value_won == null ? `<span class="muted">미확인${i.missing ? ' — ' + esc(plainUnits(i.missing)) : ''}</span>` : esc(won(i.value_won));
    return `<div class="table-container"><table class="table"><thead><tr><th>항목</th><th class="num">손익</th></tr></thead><tbody>${m.items.map(i => `<tr>
      <td>${esc(i.label)}</td><td class="num">${value(i)}</td></tr>`).join('')}` +
      `<tr><td><b>합계</b></td><td class="num"><b>${m.total_won == null ? '미확인' : esc(won(m.total_won))}</b></td></tr></tbody></table></div>` +
      note(`${esc(plainUnits(m.basis || ''))}${m.hours != null ? ` · 기간 ${num(m.hours, '시간')}` : ''}`) +
      UI.fold(`항목별 계산식과 출처<span class="muted">${m.items.length}개</span>`, `<div class="table-container"><table class="table"><thead><tr><th>항목</th><th>계산</th><th>출처</th></tr></thead><tbody>${m.items.map(i => `<tr>
      <td>${esc(i.label)}</td><td>${esc(plainUnits(i.formula || i.missing || ''))}</td><td class="muted">${sourceLines(i.sources)}</td></tr>`).join('')}</tbody></table></div>`);
  }

  // 1순위가 바뀌는 값: 무엇을 얼마로 바꾸면 1순위가 무엇이 되는지 한 줄씩, 줄 끝의 단추가 그 값으로 다시 계산한다
  function boundaryTable(list) {
    if (!W.bounds && W.boundsSince) return hydLive.waitHtml('1순위가 바뀌는 값을 찾는 중', { since: W.boundsSince, hint: '값을 하나씩 바꿔 가며 판단을 다시 계산해 1순위가 바뀌는 지점을 찾는 중입니다.' });
    if (!W.bounds) return note(esc(W.boundsMsg || '1순위가 바뀌는 값이 아직 없습니다.'), ' role="status"');
    if (!list.length) return note('시험 범위 안에서 1순위를 바꾸는 값이 없습니다.');
    // 글자까지 같은 줄(같은 값 · 같은 방향 · 같은 결과)은 한 번만 보인다 — 조치 후보마다 같은 경계가 따로 계산돼 온다
    const seen = new Set(); list = list.filter(b => { const k = [b.kind, b.label, b.base, b.value, b.direction, b.topAfterName].join('|'); if (seen.has(k)) return false; seen.add(k); return true; });
    return `<div class="table-container"><table class="table"><thead><tr><th>순위</th><th>바꾸는 값</th><th class="num">지금</th><th class="num">바뀌는 값</th><th>바뀐 1순위</th><th></th></tr></thead><tbody>${list.map(b => `<tr>
      <td>${esc(kindLabel[b.kind])}</td><td>${esc(b.label)}</td><td class="num">${esc(num(b.base, b.unit))}</td><td class="num"><b>${esc(num(b.value, b.unit))} ${esc(b.direction)}</b></td><td>${esc(b.topAfterName || '없음')}</td>
      <td class="num"><button type="button" class="btn" data-variant="outline" data-size="sm" data-wi-bound="${W.bounds.indexOf(b)}">이 값으로 계산</button></td></tr>`).join('')}</tbody></table></div>`;
  }

  // 조치 하나의 손익 내역: 조치를 고르면 항목별 손익 · 출처와, 그 조치에서 1순위가 바뀌는 값이 보인다
  function cardDetail(v) {
    const list = v.cards.slice().sort((a, b) => (a.decisionRank || 99) - (b.decisionRank || 99));
    const c = list.find(x => x.id === W.card) || list[0];
    if (!c) return '';
    const picks = `<div class="seg" role="group" aria-label="내역을 볼 조치">${list.map(x => `<button type="button" aria-pressed="${x.id === c.id}" data-wi-card="${esc(x.id)}">${esc(UI.idText(x.name))}</button>`).join('')}</div>`;
    const why = c.feasible ? (c.money.complete ? '' : '계산하지 못한 항목: ' + c.money.missing.join(', ')) : '규정상 제외 — ' + c.excluded.join(' · ');
    return sec('손익 내역', '조치를 골라 항목별로 봅니다', picks + note(esc(why)) + moneyTable(c.money)) +
      sec(`「${esc(UI.idText(c.name))}」에서 1순위가 바뀌는 값`, '', boundaryTable((W.bounds || []).filter(b => b.card === c.id)));
  }

  function compareTable(v) {
    const base = Object.fromEntries((W.base.cards || []).map(c => [c.id, c]));
    const arrow = (a, b, f) => a === b ? esc(f(b)) : `<span class="muted">${esc(f(a))}</span> → <b>${esc(f(b))}</b>`;
    const rank = r => r ? r + '위' : '–';
    const list = v.cards.slice().sort((a, b) => (a.decisionRank || 99) - (b.decisionRank || 99));      // 1순위가 맨 위
    return UI.optionsTable(list.map(c => { const b = base[c.id] || {};
      return { rank: c.feasible && c.decisionRank ? c.decisionRank : '–', name: UI.idText(c.name), code: c.sopId, pick: c.id === v.top.decision, out: !c.feasible,
        note: b.decisionRank !== c.decisionRank ? `판단 순위 ${rank(b.decisionRank)} → ${rank(c.decisionRank)}` : '',
        score: c.score, scoreHtml: !c.feasible ? esc(UI.t('chip.excluded')) : b.score !== c.score ? arrow(b.score, c.score, x => x == null ? '–' : Number(x).toFixed(2)) : null,
        extra: [arrow(b.moneyRank, c.moneyRank, rank), arrow(b.money && b.money.total_won, c.money.total_won, won)] }; }),
      { scoreLabel: '정책 점수', extra: [{ label: '손익 순위' }, { label: '예상 손익', num: true }] });
  }

  function perspectiveTable(v) {
    const pv = v.perspectives || { available: false, perspectives: [] };
    if (!pv.available) return '';
    const names = Object.fromEntries(pv.perspectives.map(p => [p.id, p.name]));
    const base = Object.fromEntries((W.base.cards || []).map(c => [c.id, c]));
    const cell = (c, pid) => { const x = (c.bscByPerspective || []).find(y => y.perspective === pid); return x ? `이득 ${num(x.gain)} · 손실 ${num(x.loss)}` : '–'; };
    const used = pv.perspectives.filter(p => p.inUse);
    const applied = Object.keys(W.policy.perspectives || {}).length ? Object.entries(W.policy.perspectives).map(([k, x]) => `${esc(names[k] || '관점')} ${num(x)}배`).join(' · ') : '';
    return sec('조치 후보별 관점 득실', applied ? '적용 중: ' + applied : '', `<div class="table-container"><table class="table"><thead><tr><th>조치</th>${used.map(p => `<th>${esc(p.name)}</th>`).join('')}<th class="num">성과 지표 점수</th></tr></thead><tbody>${v.cards.map(c => {
      const b = base[c.id] || {}, b0 = (b.scoreParts || {}).bsc, b1 = (c.scoreParts || {}).bsc;
      return `<tr><td>${esc(UI.idText(c.name))}</td>${used.map(p => `<td>${cell(c, p.id)}</td>`).join('')}<td class="num">${b0 === b1 ? esc(num(b1)) : `<span class="muted">${esc(num(b0))}</span> → <b>${esc(num(b1))}</b>`}</td></tr>`;
    }).join('')}</tbody></table></div>`);
  }

  function weeksResult() {
    const w = W.weeks;
    if (!w) return `<div class="panel-sec">${UI.empty('아직 주별로 계산한 결과가 없습니다', '왼쪽에서 조치와 바꿀 값을 고르고 [주별 계산]을 누릅니다.', 'compact')}</div>`;
    const last = rows => rows && rows[rows.length - 1];
    const b = last(w.base), c = last(w.changed);
    const diff = c && c.cum_profit_won != null && b.cum_profit_won != null ? c.cum_profit_won - b.cum_profit_won : null;
    let html = `<div class="panel-sec"><h3>주별 예측<span class="muted">「${esc(UI.idText(w.cardName))}」 · ${esc(w.weeks)}주</span></h3>` +
      `<div class="result"><div class="result-main">${esc(w.weeks)}주 누적 이익은 기준 ${esc(won(b.cum_profit_won))}${c ? `, ${esc(w.change.label)}을(를) ${esc(num(w.change.value, w.change.unit))}로 바꾸면 ${esc(won(c.cum_profit_won))}입니다.` : '입니다.'}</div>` +
      (c ? `<div class="result-sub">${esc(w.change.label)} ${esc(num(w.change.base, w.change.unit))} → ${esc(num(w.change.value, w.change.unit))} · 차이 ${esc(won(diff))}</div>` : '') + `</div>` +
      (w.missing && w.missing.length ? note(`계수 없음: ${esc(w.missing.join(', '))}`, ' data-tone="danger" role="status"') : '') + `</div>`;
    const cell = (r0, r1, k, f) => !r1 || r1[k] === r0[k] ? esc(f(r0[k])) : `<span class="muted">${esc(f(r0[k]))}</span> → <b>${esc(f(r1[k]))}</b>`;
    html += sec('주마다', c ? '기준 → 바꾼 값' : '', `<div class="table-container"><table class="table"><thead><tr><th>주</th><th class="num">가동률</th><th class="num">생산량</th><th class="num">매출</th><th class="num">비용</th><th class="num">이익</th><th class="num">누적 이익</th></tr></thead><tbody>${w.base.map((r0, i) => {
      const r1 = w.changed && w.changed[i];
      return `<tr><td>${r0.week}주</td><td class="num">${cell(r0, r1, 'availability', x => num(x, '%'))}</td><td class="num">${cell(r0, r1, 'output', x => num(x, '개'))}</td>
        <td class="num">${cell(r0, r1, 'revenue_won', won)}</td><td class="num">${cell(r0, r1, 'cost_won', x => x == null ? '미확인' : `${x.toLocaleString('ko-KR')}원`)}</td>
        <td class="num">${cell(r0, r1, 'profit_won', won)}</td><td class="num">${cell(r0, r1, 'cum_profit_won', won)}</td></tr>`;
    }).join('')}</tbody></table></div>`);
    const paths = (w.paths || []).map(p => `<li>${UI.icon('route')}<span>${esc(UI.idText(p.join(' → ')))}</span></li>`).join('');
    html += `<div class="panel-sec">` +
      UI.fold(`조치 → 설비 값 → 지표 연결<span class="muted">${(w.paths || []).length}개</span>`, paths ? `<ul class="evid">${paths}</ul>` : note('지식 지도에 이 조치의 영향 경로가 없습니다.')) +
      UI.fold(`영향 계수와 출처<span class="muted">${w.coefficients.length}개</span>`, `<div class="table-container"><table class="table"><thead><tr><th>계수</th><th class="num">값</th><th>출처</th></tr></thead><tbody>${w.coefficients.map(k => `<tr><td>${esc(k.label)}</td><td class="num">${k.value == null ? '규칙' : esc(num(k.value, k.unit))}</td>
        <td class="muted">${esc(k.kind)} · ${esc(k.source)}</td></tr>`).join('')}</tbody></table></div>`) + `</div>`;
    return html;
  }

  function wire() {
    const el = W.el, q = s => el.querySelector(s);
    q('#wiForm')?.addEventListener('submit', e => e.preventDefault());      // 칸에서 Enter 를 눌러도 화면이 새로 열리지 않게
    // 결과가 떠 있는 동안 설비 · 이상 패턴을 바꾸면 다시 그려, 오른쪽 결과가 앞서 불러온 것임을 알린다
    q('#wiAsset')?.addEventListener('change', e => { W.asset = e.target.value; if (W.view) render(); });
    q('#wiPattern')?.addEventListener('change', e => { W.pattern = e.target.value; if (W.view) render(); });
    q('#wiLoad')?.addEventListener('click', load);
    q('[data-retry]')?.addEventListener('click', () => { W.patternsError = W.assetsError = ''; if (W.assets && !W.assets.length) W.assets = null; mount(W.el); });      // 설비 · 이상 패턴 목록을 다시 읽는다
    el.querySelectorAll('[data-wi-card]').forEach(b => b.addEventListener('click', () => { W.card = b.dataset.wiCard; render(); }));
    q('#wiReset')?.addEventListener('click', reset);
    el.querySelectorAll('[data-wi-tab]').forEach(b => b.addEventListener('click', () => { W.tab = b.dataset.wiTab; W.msg = ''; render(); }));
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

  // 조치 후보 카드에 붙는 손익 접기 (enterprise.js cardHtml). 합계는 접힌 줄에 바로 보인다.
  function moneyFold(m) {
    const rows = m.items.map(i => `<tr><td>${esc(i.label)}<p class="muted">${esc(i.formula || i.missing || '')}</p></td>` +
      `<td class="num">${i.value_won == null ? '<span class="muted">미확인</span>' : esc(won(i.value_won))}</td><td class="muted">${sourceLines(i.sources)}</td></tr>`).join('');
    return UI.fold(`예상 손익 <b class="num">${esc(won(m.total_won))}</b>${m.complete || m.total_won == null ? '' : ' · 일부 미확인'}`,
      `<div class="table-container"><table class="table"><thead><tr><th>항목 · 계산</th><th class="num">손익</th><th>출처</th></tr></thead><tbody>${rows}</tbody></table></div>` +
      `<p class="muted">${esc(m.basis || '')} <a href="#/whatif">조건별 손익에서 값 바꿔 보기 →</a></p>`);
  }

  window.hydWhatif = { mount, failed, moneyFold };
  // 셸(shell.js MOUNTS.whatif)이 #/whatif 를 처음 열 때 mount(#whatifView)를 부른다.
})();
