/* A4 (U6) 판단 채점 — 사람이 적은 정답표에 AI 판단을 대어 점수를 내고, 실행을 남겨 지식 고치기 전·후를 비교한다.
   API: process /api/eval/* (procsvc/eval_api.py). 정답표는 화면에서 적는 데이터이고 처음엔 비어 있다 — 이 파일에도 정답은 없다.
   화면: window.hydEval.mount(el). 포털 셸이 컨테이너(#evalView)를 주면 그 안에 전부 그린다. 채점은 처리 건 · 설비 명령 · 기준 데이터를 바꾸지 않는다.
   짜임(디자인 기준 5-8 「입력 → 결과」): 보기 셋(채점 · 정답표 · 전 · 후 비교). 채점은 왼쪽에 조건과 [채점 실행], 오른쪽에 고른 실행의 결과(평균 → 검사 네 가지 → 항목별)와
   그 아래 「지난 실행」 표. 맞음 · 틀림은 줄 앞의 점 색으로 보이고(칩을 줄줄이 세우지 않는다), 조치 순위 원문 · 회차별 결과는 항목의 [자세히]를 눌렀을 때 열린다. */
(function () {
  const E = { el: null, golden: [], storage: '', paths: {}, maxRepeats: 10, assets: [], facts: {}, runs: [], sel: null, run: null, editing: null,
    knowledge: null, cands: null, patterns: null, cmp: null, busy: false, picked: new Set(), view: 'run', openItem: null };
  const PATH = { decide: '규칙 판단', evaluate: '규칙 읽기 평가', worker: '지난 처리 건 (실제 AI 에이전트)' };
  const CHECK = { cause: '원인 적중', top: '1위 허용', forbidden: '빠질 조치 미추천', evidence: '근거 포함' };
  const EXPECT = { excluded: '제외돼야 함', not_recommended: '1위면 안 됨' };
  // 설비 목록 · 가정 사실(이름 · 선택지)은 서버가 준다(GET /api/eval/golden 의 assets · facts — judgment_eval.FACT_CHOICES)
  const factLabel = k => (E.facts[k] || {}).label || k;
  const q = (sel) => E.el.querySelector(sel);
  const nm = (id) => `<span title="${esc(id || '')}">${esc(UI.name(id) || '–')}</span>`;
  const outcomeText = (o) => String(o || '').split(' → ').map(x => x === '-' ? '없음' : UI.name(x)).join(' → ');
  const factVal = (k, v) => { const hit = ((E.facts[k] || {}).choices || []).find(([value]) => value === v); return hit ? hit[1] : typeof v === 'string' ? UI.status(v) : String(v); };
  const factsText = (f) => Object.entries(f || {}).map(([k, v]) => `${factLabel(k)} ${factVal(k, v)}`).join(' · ') || '가정 사실 없음 (지금 값 사용)';
  const pct = (x) => Math.round((x || 0) * 100) + ' %';
  const group = (label, body) => body ? `<section class="rd-group"><h3 class="rd-label">${label}</h3>${body}</section>` : '';
  const kv = rows => { const r = rows.filter(([, x]) => x != null && x !== ''); return r.length ? `<dl class="kv">${r.map(([k, x]) => `<dt>${esc(k)}</dt><dd>${x}</dd>`).join('')}</dl>` : ''; };
  // 누가 적고 실행했는지 = 이 PC의 담당자 id(서버 eval_api.by_of 는 빈 값만 거절한다). 담당자를 못 읽으면 다른 값으로 대신하지 않고 막는다
  const NEED_ME = '담당자 정보를 읽지 못해 보낼 수 없습니다. 화면을 새로 고친 뒤 다시 해 주세요.';
  function meId() { const id = window.hydInbox?.me?.()?.id; if (!id) throw new Error(NEED_ME); return id; }
  // 그래프 관계 종류(영문) → 지식 지도와 같은 이름(enterprise.js RELATION_KO 한 곳). 그 표에 없는 종류만 원문 그대로
  const relName = (type) => (typeof RELATION_KO === 'object' && RELATION_KO[type]) || type;

  // 채점 실행은 N회 판단이라 30초를 넘길 수 있다 — 공용 요청 함수에 시간 제한 없이(끊김 · 거절 문구는 공용 함수가 학생 말로 바꾼다)
  const longJ = (url, method, body) => postJ(url, body, method, { timeout: 0 });
  const msg = (key, text, bad = true) => { const m = q(`[data-msg="${key}"]`); if (m) { m.textContent = text || ''; m.className = 'form-msg ' + (bad ? 'neg' : 'pos'); } };

  /* ---------------------------------------------------------------- 뼈대 */
  function skeleton() {
    E.el.innerHTML = `
      <div class="page-head"><h1>${esc(UI.t('nav.eval'))}</h1><div class="page-tools"><button type="button" class="btn" data-act="reload">${esc(UI.t('btn.reload'))}</button></div></div>
      <p class="page-lead">사람이 적은 정답표에 판단을 대어 점수를 내고, 지식을 고치기 전과 후의 채점을 비교합니다.</p>
      <div class="rd-seg" role="tablist" aria-label="보기" data-r="seg"></div>
      <div data-view="run">
        <div class="rd-io"><div class="rd-in" data-r="runform"></div>
          <div class="rd-out"><div data-r="cands"></div><div data-r="detail"></div>
            <section class="rd-group rd-history"><h2 class="rd-sec">지난 실행</h2><div data-r="runs"></div></section></div></div>
      </div>
      <div data-view="golden" hidden>
        <div class="rd-sec-head"><h2 class="rd-sec">정답표</h2><button type="button" class="btn" data-act="new">새 항목 적기</button></div>
        <div data-r="golden"></div>
        <div data-r="form"></div>
      </div>
      <div data-view="cmp" hidden>
        <div class="rd-io"><div class="rd-in" data-r="cmpform"></div><div class="rd-out" data-r="cmp"></div></div>
      </div>`;
    E.el.addEventListener('click', onClick);
    E.el.addEventListener('change', onChange);
    E.el.addEventListener('input', onInput);
    setView(E.view);
  }
  // 보기 바꾸기: 채점(조건 → 결과 → 지난 실행) · 정답표 · 전 · 후 비교
  function setView(view) {
    E.view = view;
    E.el.querySelectorAll('[data-view]').forEach(n => { n.hidden = n.dataset.view !== view; });
    renderStats();
  }
  // 보기 줄(건수는 이름 뒤 작은 숫자) — 요약 카드 넷이 말하던 것은 여기 건수와 「지난 실행」 표, 조건 칸 아래의 지식 한 줄이 말한다
  function renderStats() {
    const seg = [['run', '채점', E.runsError ? null : E.runs.length], ['golden', '정답표', E.goldenError ? null : E.golden.length], ['cmp', '전 · 후 비교', null]];
    q('[data-r="seg"]').innerHTML = seg.map(([k, l, n]) =>
      `<button type="button" role="tab" class="${k === E.view ? 'on' : ''}" data-act="view" data-to="${k}" aria-selected="${k === E.view}">${esc(l)}${n != null ? `<span class="n">${esc(n)}</span>` : ''}</button>`).join('');
    E.el.querySelectorAll('[data-r="knowledge"]').forEach(n => { n.innerHTML = knowledgeNow(); });
  }
  function knowledgeNow() {
    const k = E.knowledge;
    if (!k) return E.knowledgeError ? `<span class="neg">${esc(E.knowledgeError)}</span>` : '';
    return `지금 지식: 지식 항목 ${esc(k.nodes)}개 · 연결 ${esc(k.relationships)}개${k.last_change ? ' · 마지막 변경 ' + esc(UI.dateTime(k.last_change)) : k.last_change_note ? ' · ' + esc(k.last_change_note) : ''}`;
  }

  /* ---------------------------------------------------------------- 1. 정답표 */
  function renderGolden() {
    const host = q('[data-r="golden"]');
    if (!E.golden.length) {
      host.innerHTML = UI.empty('정답표가 비어 있습니다', '[새 항목 적기]로 경보 상황 하나와 기대하는 판단을 적습니다. 내장 정답은 없습니다.', 'compact');
      return;
    }
    host.innerHTML = `<div class="rd-scroll"><table class="tbl"><thead><tr><th>채점</th><th>경보 상황</th><th>기대 원인</th><th>1위 허용</th><th>빠질 조치</th><th>있어야 할 근거</th></tr></thead><tbody>${
      E.golden.map(it => `<tr>
        <td><input type="checkbox" data-pick="${esc(it.id)}" ${E.picked.has(it.id) ? 'checked' : ''} aria-label="${esc(it.title)} 채점에 포함"></td>
        <td><button type="button" class="link-btn" data-edit="${esc(it.id)}">${esc(it.title)}</button><small>${esc(it.asset)} · ${esc(patternName(it.pattern))} · ${esc(factsText(it.facts))}</small></td>
        <td>${nm(it.expected.cause)}<small>${nm(it.expected.failure_mode)}</small></td>
        <td>${it.allowed_top.map(nm).join('<br>')}</td>
        <td>${it.forbidden.length ? it.forbidden.map(f => `${nm(f.skill)} <span class="muted">${esc(EXPECT[f.expect])}</span>`).join('<br>') : '<span class="muted">없음</span>'}</td>
        <td>${it.required_evidence.map(nm).join('<br>')}</td></tr>`).join('')}</tbody></table></div>
      <p class="rd-note">채점에 포함할 항목에 표시합니다. 아무것도 표시하지 않으면 전체를 채점합니다. 제목을 누르면 고칠 수 있습니다.</p>`;
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
    return `<datalist id="evalDlCause">${by('cause:')}</datalist><datalist id="evalDlFm">${by('fm:')}</datalist>` +
      `<datalist id="evalDlSkill">${by('skill:')}</datalist><datalist id="evalDlEvidence">${by('evd:')}${by('rule:')}${by('ks:')}</datalist>`;
  }
  // 조치 · 근거 칸 아래의 「이름으로 찾아 넣기」: 이름 사전에서 고르면 그 항목의 id 를 위 칸에 한 줄 더한다(id 를 외워 적지 않게)
  function picker(field, list, label) {
    return `<input data-add-to="${field}" list="${list}" placeholder="이름으로 찾아 넣기" aria-label="${esc(label)} 이름으로 찾아 넣기" autocomplete="off">`;
  }

  function renderForm() {
    const host = q('[data-r="form"]');
    if (!E.editing) { host.innerHTML = ''; return; }
    const it = E.editing.item || { facts: {}, expected: {}, allowed_top: [], forbidden: [], required_evidence: [] };
    const isNew = !E.editing.item;
    const sel = (id, opts, cur, blank) => `<select data-f="${id}">${blank ? `<option value="">${esc(blank)}</option>` : ''}${opts.map(([v, l]) => `<option value="${esc(v)}" ${String(cur ?? '') === String(v) ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select>`;
    const pats = (E.patterns || []).map(p => [p.code, p.name]);
    const f = it.facts || {};
    const forbiddenText = (it.forbidden || []).map(x => `${x.skill} = ${x.expect === 'excluded' ? '제외' : '1위 아님'}${x.rule ? ` (${x.rule})` : ''}`).join('\n');
    // 폼은 한 열(기준 5-6): 제목 → 절마다 칸 → 맨 아래 왼쪽에 [저장] · [취소], 오른쪽 끝에 [지우기]
    host.innerHTML = `<section class="rd-group eval-form"><h3 class="rd-sec">${isNew ? '새 정답표 항목' : '정답표 항목 고치기'}</h3><div class="rd-form">` +
      datalists() +
      UI.section('경보 상황',
        UI.field({ label: '제목', required: true, input: `<input data-f="title" value="${esc(it.title || '')}" placeholder="예: 쿨러 성능 저하 · 원격 자동 운전">` }) +
        UI.field({ label: '항목 이름(영문)', required: true, hint: '영문 소문자, 숫자, 하이픈만 씁니다. 저장한 뒤에는 바꿀 수 없습니다.', input: `<input data-f="id" value="${esc(it.id || '')}" ${isNew ? '' : 'disabled'} placeholder="예: cooler-auto">` }) +
        UI.field({ label: '설비', required: true, input: sel('asset', E.assets.map(a => [a, a]), it.asset || '', '설비 선택') }) +
        UI.field({ label: '이상 패턴', required: true, error: E.patterns ? '' : E.patternError || '', input: pats.length ? sel('pattern', pats, it.pattern || '', '이상 패턴 선택') : '<select data-f="pattern" disabled><option value="">목록을 읽지 못함</option></select>' })) +
      UI.section('가정 사실(비우면 지금 값을 씁니다)', Object.entries(E.facts).map(([k, spec]) => UI.field({ label: spec.label,
        input: spec.number ? `<input data-f="${esc(k)}" data-fact="number" type="number" min="0" step="1" value="${esc(f[k] ?? '')}" placeholder="지금 값">`
          : sel(k, [['', '지금 값'], ...spec.choices.map(([v, l]) => [JSON.stringify(v), l])], f[k] == null ? '' : JSON.stringify(f[k])) })).join('')) +
      UI.section('기대하는 판단',
        UI.field({ label: '기대 원인', required: true, input: `<input data-f="cause" list="evalDlCause" value="${esc(it.expected.cause || '')}">`, hint: '지식 지도의 원인 이름을 고르세요' }) +
        UI.field({ label: '고장 유형', required: true, input: `<input data-f="failure_mode" list="evalDlFm" value="${esc(it.expected.failure_mode || '')}">` }) +
        UI.field({ label: '1위로 허용되는 조치', required: true, cls: 'wide', hint: '한 줄에 하나씩 적습니다. 아래 칸에서 조치 방법 이름을 찾아 고르면 한 줄이 더해집니다.', input: `<textarea data-f="allowed_top" rows="2">${esc((it.allowed_top || []).join('\n'))}</textarea>${picker('allowed_top', 'evalDlSkill', '1위로 허용되는 조치')}<p class="field-hint" data-preview="allowed_top">${namePreview((it.allowed_top || []).join('\n'))}</p>` }) +
        UI.field({ label: '빠져야 할 조치', cls: 'wide', hint: '한 줄에 하나씩 「조치 = 제외」 또는 「조치 = 1위 아님」으로 적습니다. 근거 규칙이 있으면 줄 끝 괄호 안에 적습니다. 아래 칸에서 조치 방법 이름을 고르면 「= 제외」 줄이 더해집니다.', input: `<textarea data-f="forbidden" rows="3">${esc(forbiddenText)}</textarea>${picker('forbidden', 'evalDlSkill', '빠져야 할 조치')}<p class="field-hint" data-preview="forbidden">${namePreview(forbiddenText.replace(/=.*$/gm, ''))}</p>` }) +
        UI.field({ label: '근거에 있어야 할 지식', required: true, cls: 'wide', hint: '증거, 규칙, 매뉴얼 절을 한 줄에 하나씩 적습니다. 아래 칸에서 이름을 찾아 고르면 한 줄이 더해집니다.', input: `<textarea data-f="required_evidence" rows="3">${esc((it.required_evidence || []).join('\n'))}</textarea>${picker('required_evidence', 'evalDlEvidence', '근거에 있어야 할 지식')}<p class="field-hint" data-preview="required_evidence">${namePreview((it.required_evidence || []).join('\n'))}</p>` })) +
      UI.section('', UI.field({ label: UI.t('form.note'), input: `<input data-f="note" value="${esc(it.note || '')}">` })) +
      `<p><span class="form-msg" data-msg="form" role="status"></span></p>` +
      (pats.length ? '' : '<p class="field-error" role="alert">이상 패턴 목록을 읽지 못해 지금은 저장할 수 없습니다. 화면 위의 [다시 읽기]를 눌러 주세요.</p>') +
      `<div class="rd-form-actions"><button type="button" class="btn primary" data-act="save" ${pats.length ? '' : 'disabled'}>${esc(UI.t('btn.save'))}</button>` +
      `<button type="button" class="btn" data-act="cancel">${esc(UI.t('btn.cancel'))}</button>` +
      (isNew ? '' : `<button type="button" class="btn danger rd-end" data-act="delete" title="지워도 지난 채점 실행 기록은 남습니다">이 항목 지우기</button>`) + `</div></div></section>`;
    host.scrollIntoView({ block: 'start', behavior: 'smooth' });
  }

  function readForm() {
    const v = (k) => { const n = q(`[data-f="${k}"]`); return n ? n.value.trim() : ''; };
    const facts = {};
    Object.entries(E.facts).forEach(([k, spec]) => { const raw = v(k);           // 선택지 값은 JSON 글로 담아 종류(글 · 참/거짓)를 그대로 되살린다
      if (raw !== '') facts[k] = spec.number ? Number(raw) : JSON.parse(raw); });
    const forbidden = String(q('[data-f="forbidden"]').value || '').split('\n').map(s => s.trim()).filter(Boolean).map((line, i) => {
      const m = line.match(/^(\S+)\s*=\s*(제외|1위\s*아님)\s*(?:\((\S+)\))?$/);
      if (!m) throw new Error(`빠져야 할 조치 ${i + 1}번째 줄: "조치 = 제외" 또는 "조치 = 1위 아님" 형식으로 적으세요`);
      return { skill: m[1], expect: m[2] === '제외' ? 'excluded' : 'not_recommended', ...(m[3] ? { rule: m[3] } : {}) };
    });
    if (!v('asset')) throw new Error('설비를 고르세요');
    if (!v('pattern')) throw new Error('이상 패턴을 고르세요');
    const by = meId();
    return { by, item: { id: E.editing.item ? E.editing.item.id : v('id'), title: v('title'), asset: v('asset'), pattern: v('pattern'), facts,
      expected: { cause: v('cause'), failure_mode: v('failure_mode') }, allowed_top: lines(q('[data-f="allowed_top"]').value),
      forbidden, required_evidence: lines(q('[data-f="required_evidence"]').value), note: v('note') } };
  }

  /* ---------------------------------------------------------------- 2. 채점 실행 */
  // 왼쪽: 채점 조건 → [채점 실행]. 지난 처리 건 경로면 채점할 처리 건 표가 오른쪽 맨 위에 나온다
  function renderRunForm() {
    const path = E.path || 'decide';
    const picked = E.golden.filter(it => E.picked.has(it.id));
    const target = path === 'worker' ? '오른쪽 표에서 채점할 처리 건을 고릅니다.'
      : `채점할 항목: ${picked.length ? picked.map(it => it.title).join(' · ') : `정답표 전체 (${E.golden.length}개)`}`;
    const blocked = E.golden.length ? '' : `<p class="rd-in-note">정답표가 비어 있어 채점할 수 없습니다. <button type="button" class="link-btn" data-act="view" data-to="golden">정답표 적기 →</button></p>`;
    q('[data-r="runform"]').innerHTML = `<h2 class="rd-label">채점 조건</h2>` +
      UI.field({ label: '판단 경로', input: `<select data-f="path">${Object.entries(PATH).map(([k, l]) => `<option value="${k}" ${k === path ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select>`, hint: String(E.paths[path] || '') }) + // 경로 안내는 서버 문장(judgment_eval.PATH_NOTES) 그대로
      (path === 'worker' ? '' : UI.field({ label: '반복 횟수', input: `<input data-f="repeats" type="number" min="1" max="${E.maxRepeats}" value="${esc(E.repeats || 1)}">`,
        hint: '같은 항목을 여러 번 판단해 결과가 흔들리는지 봅니다. 모두 같으면 「N회 모두 같음」으로 보입니다.' })) +
      UI.field({ label: UI.t('form.note'), input: `<input data-f="runNote" placeholder="예: 관계 하나 끊기 전">` }) +
      `<p class="rd-in-note">${esc(target)}${path === 'worker' || !E.golden.length ? '' : ` <button type="button" class="link-btn" data-act="view" data-to="golden">정답표에서 고르기 →</button>`}</p>` +
      `<p><span class="form-msg" data-msg="run" role="status"></span></p>` +
      `<div class="rd-in-actions"><button type="button" class="btn primary" data-act="run" ${E.golden.length && !E.busy ? '' : 'disabled'}>채점 실행</button></div>` + blocked +
      `<p class="rd-in-note" data-eval-ai-note>세 판단 경로 가운데 AI가 판단하는 것은 「지난 처리 건」 하나입니다. 「규칙 판단」과 「규칙 읽기 평가」는 AI 모델 없이 판단 엔진만으로 계산합니다. 채점은 처리 건, 설비 명령, 기준 데이터를 바꾸지 않습니다.</p>` +
      `<p class="rd-in-note" data-r="knowledge">${knowledgeNow()}</p>`;
    q('[data-r="cands"]').innerHTML = path === 'worker' ? renderCands() : '';
    showRunWait();
  }
  function renderCands() {
    if (E.cands == null) return UI.loading('', 'compact');
    if (E.cands.error) return UI.errorBlock('지난 처리 건을 읽지 못했습니다', E.cands.error, { cls: 'compact' });
    if (!E.cands.length) return UI.emptyGo('채점할 지난 처리 건이 없습니다', '원인 진단과 조치 후보 단계까지 끝난 처리 건이 여기에 나타납니다.', 'scenario', '결함 시뮬레이션에서 사건 만들기', 'compact');
    return group('채점할 지난 처리 건', `<div class="rd-scroll"><table class="tbl"><thead><tr><th>채점</th><th>처리 건</th><th>AI 에이전트의 판단</th><th>맞는 정답표 항목</th></tr></thead><tbody>${E.cands.map(c => {
      const item = E.golden.find(it => it.id === c.item);
      return `<tr><td><input type="checkbox" data-cand="${esc(c.instance)}" ${item ? '' : 'disabled'} aria-label="${esc(c.name || '처리 건')} 채점에 포함"></td>
        <td>${esc(c.name || '이름 없는 처리 건')}<small>${esc(UI.dateTime(c.started))} · ${esc(UI.status(c.status))}</small></td>
        <td>${nm(c.cause)} → ${nm(c.chosen_skill)}<small>${esc(factsText(c.facts))}</small></td>
        <td>${item ? esc(item.title) : `<span class="neg">${esc(c.match_note || '맞는 항목 없음')}</span>`}</td></tr>`;
    }).join('')}</tbody></table></div>`);
  }
  async function loadCands() {
    E.cands = null; const host = q('[data-r="cands"]'); if (host) host.innerHTML = renderCands();
    try { E.cands = await getJ(API.process + '/api/eval/worker-candidates?limit=30'); } catch (e) { E.cands = { error: e.message }; }
    const h = q('[data-r="cands"]'); if (h) h.innerHTML = renderCands();
  }

  // 채점이 도는 동안: 단추는 「채점하는 중 · 걸린 시간」, 그 위 줄은 무엇을 기다리는지. 실행 칸이 다시 그려져도(항목 고르기 등) 같은 시각에서 이어 보인다
  function showRunWait() {
    const w = E.runWait, btn = q('[data-act="run"]'), m = q('[data-msg="run"]'); if (!w || !btn || !m) return;
    hydLive.busy(btn, '채점하는 중', w.since);
    m.className = 'form-msg'; m.innerHTML = hydLive.waitHtml(w.text, { since: w.since, hint: w.hint });
  }
  async function runEval() {
    if (E.busy) return;
    const path = q('[data-f="path"]').value, note = q('[data-f="runNote"]').value.trim();
    let by; try { by = meId(); } catch (e) { msg('run', e.message); return; }
    const body = { path, by, note: note || null };
    if (path === 'worker') {
      body.instances = [...E.el.querySelectorAll('[data-cand]:checked')].map(n => ({ instance: n.dataset.cand }));
      if (!body.instances.length) { msg('run', '채점할 처리 건을 하나 이상 고르세요'); return; }
    } else {
      body.repeats = Math.max(1, Math.min(E.maxRepeats, Number(q('[data-f="repeats"]').value) || 1)); E.repeats = body.repeats;
      if (E.picked.size) body.items = [...E.picked];
    }
    E.busy = true; E.busyWhy = '채점 중에는 할 수 없습니다. 채점이 끝난 뒤 다시 눌러 주세요.'; const btn = q('[data-act="run"]');
    const n = path === 'worker' ? body.instances.length : (body.items || E.golden).length * body.repeats;
    // 서버는 판단 n회를 모두 끝낸 뒤 결과를 한 번에 준다(항목별 진행은 내보내지 않는다) — 그래서 걸린 시간과 무엇을 기다리는지만 보인다
    E.runWait = { since: new Date().toISOString(), text: `판단 ${n}회를 정답표와 견주는 중`, hint: path === 'worker' ? '고른 지난 처리 건의 AI 판단을 정답표 항목과 견주는 중입니다. 서버가 모두 끝낸 뒤 결과를 한 번에 줍니다.'
      : `판단 엔진에 ${n}번 묻는 중입니다(항목 ${n / body.repeats}개 × ${body.repeats}회). 서버가 모두 끝낸 뒤 결과를 한 번에 줍니다.` };
    E.runSaid = null; showRunWait();
    try {
      const run = await longJ(API.process + '/api/eval/runs', 'POST', body);
      E.sel = run.id; E.run = run; E.runSaid = [`채점 완료. 평균 ${run.summary.score}점입니다.`, false];
      await loadRuns(); renderDetail();
    } catch (e) { E.runSaid = [e.message, true]; }
    finally { E.busy = false; E.runWait = null; renderRunForm(); if (E.runSaid) msg('run', E.runSaid[0], E.runSaid[1]); }      // 실행 칸을 다시 그려 단추를 원래대로 하고 결과 문장을 쓴다   // 채점 중에 실행 칸이 다시 그려졌어도 지금 단추를 켠다
  }

  /* ---------------------------------------------------------------- 3. 실행 기록 */
  // 지난 실행: 표 한 장. 줄을 누르면 위 결과 자리에 그 실행이 열린다
  function renderRuns() {
    const host = q('[data-r="runs"]');
    if (!E.runs.length) { host.innerHTML = UI.empty('아직 채점 실행이 없습니다', '정답표를 적고 [채점 실행]을 누르면 여기에 남습니다.', 'compact'); return; }
    host.innerHTML = `<div class="rd-scroll"><table class="tbl"><thead><tr><th>실행 시각</th><th>판단 경로</th><th class="r">평균</th><th class="r">항목</th><th>메모</th></tr></thead><tbody>${E.runs.map(r =>
      `<tr class="${r.id === E.sel ? 'pick' : ''}" data-run="${esc(r.id)}" data-row-open tabindex="0" role="button" aria-pressed="${r.id === E.sel}">
        <td>${esc(UI.dateTime(r.created))}</td><td>${esc(PATH[r.path] || r.path)}</td><td class="r">${esc(r.summary.score)}점</td><td class="r">${esc(r.summary.items)}개</td>
        <td>${esc(r.note || '')}</td></tr>`).join('')}</tbody></table></div>`;
  }
  // 검사 한 줄: 맞음 · 틀림은 앞의 점 색(초록 · 빨강)과 글로
  function checkLine(key, c) {
    let detail = '';
    if (key === 'cause') detail = `판단 ${nm(c.got)} · 정답 ${nm(c.want)}` + (c.got_failure_mode !== c.want_failure_mode ? ` <span class="muted">(고장 유형 ${nm(c.got_failure_mode)} / ${nm(c.want_failure_mode)})</span>` : '');
    if (key === 'top') detail = `1위 ${nm(c.got)} · 허용 ${c.allowed.map(nm).join(', ')}`;
    if (key === 'forbidden') detail = c.detail.length ? c.detail.map(d => `${nm(d.skill)} ${esc(EXPECT[d.expect])} → ${esc(UI.idText(d.got))}${d.ok ? '' : ' (틀림)'}`).join(' · ') : '정답표에 빠질 조치 없음 — 점수에 넣지 않음';
    if (key === 'evidence') detail = `${pct(c.ratio)}` + (c.missing.length ? ` · 빠진 근거 ${c.missing.map(nm).join(', ')}` : '');
    return `<li class="rd-state ${c.ok ? 'ok' : 'bad'}"><span><b>${esc(CHECK[key])}</b> ${c.ok ? '맞음' : '틀림'} — ${detail}</span></li>`;
  }
  // 반복이면 검사마다 N회 중 맞은 수(서버 aggregate 의 check_hits), 아래 상세 줄은 마지막 회차 — 점수(평균)와 섞어 읽지 않게 밝힌다
  function checkLines(r) {
    const lines = `<ul class="rd-checklist">${Object.keys(CHECK).map(k => checkLine(k, r.checks[k])).join('')}</ul>`;
    if (!(r.repeats > 1) || !r.check_hits) return lines;
    const hits = Object.keys(CHECK).map(k => `${esc(CHECK[k])} ${esc(r.check_hits[k])}/${esc(r.repeats)}`).join(' · ');
    return `<p class="rd-p"><b>${esc(r.repeats)}회 중 맞은 수</b> ${hits}</p><p class="rd-note">아래는 마지막 회차의 검사입니다.</p>` + lines;
  }
  // 항목 하나: 제목 · 점수 → 판단 한 줄 → 검사 네 가지 → [자세히](조치 순위 원문 · 회차별 결과 · 채점한 처리 건)
  function itemResult(r) {
    const title = (E.golden.find(it => it.id === r.item) || {}).title || r.title;
    const open = E.openItem === r.item;
    const repeat = r.repeats > 1 ? (r.identical ? `<p class="rd-note">${esc(r.repeats)}회 모두 같은 결과${r.deterministic ? ' — 결정론적이라 1회와 같습니다' : ''}</p>`
      : `<p class="rd-state warn">흔들림: ${esc(r.repeats)}회 중 가장 많은 결과 ${pct(r.stability)} · 점수 ${esc(r.min)}~${esc(r.max)}</p>`) : '';
    const mismatch = (r.facts_mismatch || []).length ? `<p class="rd-state warn">정답표의 가정과 판단 때 사실이 다릅니다: ${r.facts_mismatch.map(m => `${esc(factLabel(m.key))} 정답표 ${esc(factVal(m.key, m.want))} / 판단 때 ${esc(factVal(m.key, m.got))}`).join(' · ')}</p>` : '';
    const more = !open ? '' :
      group('조치 순위 (판단 원문)', `<ol>${(r.checks.top.order || []).map(o => `<li>${esc(UI.idText(o.replace(/^\d+\.\s*/, '')))}</li>`).join('') || '<li>후보 없음</li>'}</ol>`) +
      (r.repeats > 1 && !r.identical ? group('회차별 결과', `<ul class="rd-lines">${Object.entries(r.outcomes).map(([o, n]) => `<li><span>${esc(outcomeText(o))}</span><small>${esc(n)}회</small></li>`).join('')}</ul>`) : '') +
      ((r.instances || []).length ? group(`채점한 처리 건 ${r.instances.length}건`, `<ul class="rd-lines">${r.instances.map(i => `<li><span>${esc(i.name || '이름 없는 처리 건')} · 고른 조치 ${nm(i.chosen_skill)}</span><small>${esc(UI.dateTime(i.started))}</small></li>`).join('')}</ul>`) : '');
    return `<section class="rd-group rd-item"><header class="rd-head"><div><div class="rd-title"><h3>${esc(title)}</h3>${r.status && r.status !== 'EVALUATED' ? UI.chip(r.status) : ''}</div>` +
      `<p class="rd-sub">${esc(r.asset)} · ${esc(patternName(r.pattern))} · ${esc(factsText(r.facts))}</p></div><b class="rd-score">${esc(r.score)}점</b></header>` +
      `<p class="rd-p"><b>판단</b> ${esc(outcomeText(r.modal_outcome))}</p>` + (r.reason ? `<p class="field-error">${esc(UI.idText(r.reason))}</p>` : '') +
      checkLines(r) + mismatch + repeat +
      `<button type="button" class="link-btn" data-act="item" data-item="${esc(r.item)}" aria-expanded="${open}">${open ? '자세히 닫기' : '자세히 · 조치 순위 원문'}</button>` + more + `</section>`;
  }
  function knowledgeLine(k) {
    if (!k) return '';
    // 그래프 지문(해시)은 화면 글로 보이지 않는다 — 마우스를 올리면 뜨는 설명에만 둔다
    return `<span${k.fingerprint ? ` title="지식 그래프 지문 ${esc(k.fingerprint)}"` : ''}>지식 항목 ${esc(k.nodes)}개 · 연결 ${esc(k.relationships)}개 · 조치 방법 ${esc(k.skills ?? '–')}개 · 규칙 ${esc(k.rules ?? '–')}개 · ` +
      esc(k.last_change ? '마지막 변경 ' + UI.dateTime(k.last_change) : k.last_change_note || '') + '</span>';
  }
  // 결과의 차례: 평균 점수(결론) → 검사 네 가지의 맞은 수 → 항목별
  function renderDetail() {
    const host = q('[data-r="detail"]'), r = E.run;
    if (!r) { host.innerHTML = UI.empty('아직 고른 채점 실행이 없습니다', '왼쪽에서 [채점 실행]을 누르거나 아래 「지난 실행」에서 한 줄을 고르면, 항목별 점수와 검사 네 가지가 보입니다.', 'compact'); return; }
    const s = r.summary;
    host.innerHTML = `<h2 class="rd-conclusion">평균 ${esc(s.score)}점 — 항목 ${esc(s.items)}개 · ${esc(PATH[r.path] || r.path)}</h2>` +
      `<p class="rd-note">${esc(UI.dateTime(r.created))} · ${esc(UI.who(r.by))}${r.note ? ' · ' + esc(r.note) : ''}</p>` +
      kv([...Object.entries({ cause_hits: '원인 적중', top_ok: '1위 허용', forbidden_ok: '빠질 조치 미추천', evidence_ok: '근거 모두 포함' }).map(([k, l]) => [l, `${esc(s[k])} / ${esc(s.items)}`]),
        ['판단 없음(보류 · 오류)', s.withheld ? esc(s.withheld) : ''], ['흔들림', s.unstable ? esc(s.unstable) : '']]) +
      (r.items || []).map(itemResult).join('') +
      `<p class="rd-note rd-group">채점 때 지식: ${knowledgeLine(r.knowledge)}</p>`;
  }
  async function selectRun(id) {
    E.sel = id; E.openItem = null; renderRuns();
    q('[data-r="detail"]').innerHTML = UI.loading('', 'compact');
    try { E.run = await getJ(API.process + '/api/eval/runs/' + encodeURIComponent(id)); } catch (e) { E.run = null; q('[data-r="detail"]').innerHTML = UI.errorBlock('채점 실행을 읽지 못했습니다', e.message, { cls: 'compact' }); return; }
    renderDetail(); UI.revealDetail(q('[data-r="detail"]'));
  }

  /* ---------------------------------------------------------------- 4. 전 · 후 비교 */
  function renderCmpForm() {
    const host = q('[data-r="cmpform"]');
    const opts = (cur) => E.runs.map(r => `<option value="${esc(r.id)}" ${r.id === cur ? 'selected' : ''}>${esc(UI.dateTime(r.created))} · ${esc(UI.who(r.by))} · ${esc(r.summary.score)}점${r.note ? ' · ' + esc(r.note) : ''}</option>`).join('');
    const head = `<h2 class="rd-label">비교할 두 실행</h2>`;
    if (E.runsError) { host.innerHTML = head + `<p class="field-error" role="alert">실행 기록을 읽지 못해 비교할 수 없습니다: ${esc(E.runsError)}</p>`; return; }
    if (E.runs.length < 2) {
      host.innerHTML = head + `<p class="rd-in-note">비교하려면 채점 실행이 두 개 필요합니다. 지식을 고치기 전에 한 번, 고친 뒤에 한 번 채점합니다(예: Neo4j Browser에서 관계 하나 끊기, 매뉴얼 하나 더 넣기).</p>` +
        `<div class="rd-in-actions"><button type="button" class="btn" data-act="view" data-to="run">채점하러 가기</button></div>`;
      return;
    }
    host.innerHTML = head +
      UI.field({ label: '고치기 전 실행', input: `<select data-f="before">${opts(E.cmpBefore || E.runs[1].id)}</select>` }) +
      UI.field({ label: '고친 뒤 실행', input: `<select data-f="after">${opts(E.cmpAfter || E.runs[0].id)}</select>` }) +
      `<p><span class="form-msg" data-msg="cmp" role="status"></span></p>` +
      `<div class="rd-in-actions"><button type="button" class="btn primary" data-act="compare">두 실행 비교</button></div>` +
      `<p class="rd-in-note" data-r="knowledge">${knowledgeNow()}</p>`;
  }
  // 비교 결과의 차례: 평균이 얼마나 바뀌었나(결론) → 두 실행 사이 지식 변화 → 항목별 변화 표
  function renderCmp() {
    const host = q('[data-r="cmp"]'), c = E.cmp;
    if (!c) { host.innerHTML = UI.empty('아직 비교한 결과가 없습니다', '왼쪽에서 고치기 전 실행과 고친 뒤 실행을 고르고 [두 실행 비교]를 누릅니다.', 'compact'); return; }
    const kd = c.knowledge || {};
    const rel = (x) => `${nm(x.from)} → <span class="muted">${esc(relName(x.type))}</span> → ${nm(x.to)}`;
    const line = (label, body) => `<li><span><b>${label}</b> ${body}</span></li>`;
    const know = !kd.comparable ? `<p class="rd-note">${esc(kd.note || '')}</p>` : !kd.changed ? '<p class="rd-p">두 실행 사이에 지식 그래프가 바뀌지 않았습니다.</p>' :
      `<p class="rd-p">지식 항목 ${esc(kd.nodes[0])}개 → ${esc(kd.nodes[1])}개 · 연결 ${esc(kd.relationships[0])}개 → ${esc(kd.relationships[1])}개</p>` +
      (kd.counts ? `<ul class="rd-lines">${(kd.removed_rels || []).map(x => line('연결 삭제', rel(x))).join('')}${(kd.added_rels || []).map(x => line('연결 추가', rel(x))).join('')}` +
        `${(kd.added_nodes || []).length ? line('새 항목', kd.added_nodes.map(nm).join(', ')) : ''}${(kd.removed_nodes || []).length ? line('없어진 항목', kd.removed_nodes.map(nm).join(', ')) : ''}` +
        `${(kd.changed_nodes || []).length ? line('속성 바뀜', kd.changed_nodes.map(nm).join(', ')) : ''}</ul>` : `<p class="rd-note">${esc(kd.note || '')}</p>`);
    const verdict = { improved: ['좋아짐', 'success'], regressed: ['나빠짐', 'danger'], same: ['같음', 'neutral'] };
    host.innerHTML = `<h2 class="rd-conclusion">평균 ${c.delta == null ? '–' : (c.delta > 0 ? '+' : '') + esc(c.delta)}점 — 좋아짐 ${esc(c.improved)} · 나빠짐 ${esc(c.regressed)} · 같음 ${esc(c.same)}</h2>` +
      `<p class="rd-note">전 ${esc(UI.dateTime(c.before.created))} ${esc(c.before.note || '')} → 후 ${esc(UI.dateTime(c.after.created))} ${esc(c.after.note || '')}</p>` +
      group('두 실행 사이 지식 변화', know) +
      (c.golden_changed.length ? `<p class="rd-state warn rd-group">정답표가 두 실행 사이에 바뀐 항목: ${c.golden_changed.map(i => esc((E.golden.find(it => it.id === i) || {}).title || i)).join(', ')} — 이 항목의 점수 변화는 지식이 아니라 정답 때문일 수 있습니다.</p>` : '') +
      group('항목별 변화', `<div class="rd-scroll"><table class="tbl"><thead><tr><th>항목</th><th class="r">전</th><th class="r">후</th><th>변화</th><th>바뀐 검사</th><th>판단 전 → 후</th></tr></thead><tbody>${c.rows.map(r => `<tr>
          <td>${esc(r.title)}</td><td class="r">${esc(r.before)}</td><td class="r">${esc(r.after)}</td><td>${(r.delta > 0 ? '+' : '') + esc(r.delta)} ${r.verdict === 'same' ? '같음' : UI.chipText(verdict[r.verdict][0], verdict[r.verdict][1])}</td>
          <td>${r.changed.map(x => `${esc(CHECK[x.check])} ${x.before ? '맞음' : '틀림'}→${x.after ? '맞음' : '틀림'}`).join('<br>') || '–'}${r.evidence_lost.length ? `<small>잃은 근거 ${r.evidence_lost.map(nm).join(', ')}</small>` : ''}${r.evidence_gained.length ? `<small>얻은 근거 ${r.evidence_gained.map(nm).join(', ')}</small>` : ''}</td>
          <td>${esc(outcomeText(r.outcome_before))}<small>→ ${esc(outcomeText(r.outcome_after))}</small></td></tr>`).join('')}</tbody></table></div>`) +
        (c.only_before.length || c.only_after.length ? `<p class="rd-note">한쪽 실행에만 있는 항목: ${[...c.only_before, ...c.only_after].map(i => esc((E.golden.find(it => it.id === i) || {}).title || i)).join(', ')}</p>` : '');
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
    if (!t) return;
    // 채점 실행은 오래 걸린다 — 그동안에도 실행 기록 고르기와 [변경 취소]는 되고, 나머지는 왜 안 되는지 알린다(말없이 먹지 않게)
    if (E.busy && !t.dataset.run && !['cancel', 'view', 'item'].includes(t.dataset.act)) { UI.toast(E.busyWhy, { tone: 'neutral' }); return; }
    if (t.dataset.edit) { E.editing = { item: E.golden.find(it => it.id === t.dataset.edit) }; renderForm(); return; }
    if (t.dataset.run) { selectRun(t.dataset.run); return; }
    const act = t.dataset.act;
    if (act === 'reload') return load();
    if (act === 'view') { setView(t.dataset.to); return; }
    if (act === 'item') { E.openItem = E.openItem === t.dataset.item ? null : t.dataset.item; renderDetail(); return; }
    if (act === 'new') { E.editing = { item: null }; renderForm(); return; }
    if (act === 'cancel') { E.editing = null; renderForm(); return; }
    if (act === 'run') return runEval();
    if (act === 'compare') return compare();
    if (act === 'save' || act === 'delete') {
      if (act === 'delete' && !await UI.confirm({ title: '이 정답표 항목을 지울까요?', body: '지난 채점 실행 기록은 남습니다. 지운 항목은 되살릴 수 없습니다.', ok: '지우기', danger: true })) return;
      E.busy = true; E.busyWhy = '저장하는 중입니다. 끝난 뒤 다시 눌러 주세요.';
      try {
        if (act === 'save') {
          const { by, item } = readForm();
          const url = API.process + '/api/eval/golden/items' + (E.editing.item ? '/' + encodeURIComponent(item.id) : '');
          await postJ(url, { item, by }, E.editing.item ? 'PUT' : 'POST');
        } else {
          const by = meId();
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
    if (t.dataset.addTo) {      // 이름으로 찾아 넣기: 사전에 있는 id 만 위 칸에 더한다
      const id = t.value.trim(), area = q(`[data-f="${t.dataset.addTo}"]`);
      if (!id || !area) return;
      if (!UI.names[id]) { msg('form', `「${id}」: 목록에 있는 이름을 고르세요`); return; }
      const line = t.dataset.addTo === 'forbidden' ? `${id} = 제외` : id;
      area.value = (area.value.trim() ? area.value.replace(/\s+$/, '') + '\n' : '') + line;
      t.value = ''; msg('form', '');
      area.dispatchEvent(new Event('input', { bubbles: true }));      // 이름 미리 보기를 다시 그린다(onInput)
      return;
    }
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
      E.golden = g.items || []; E.storage = g.storage; E.paths = g.paths || {}; E.maxRepeats = g.max_repeats; E.assets = g.assets || []; E.facts = g.facts || {};
      for (const id of [...E.picked]) if (!E.golden.some(it => it.id === id)) E.picked.delete(id);
      E.goldenError = '';
      renderGolden();
    } catch (e) { E.golden = []; E.goldenError = e.message; q('[data-r="golden"]').innerHTML = UI.errorBlock('정답표를 읽지 못했습니다', e.message, { cls: 'compact' }); }
    renderRunForm(); renderStats();
  }
  async function loadRuns() {
    try { E.runs = await getJ(API.process + '/api/eval/runs?limit=50'); E.runsError = ''; renderRuns(); }
    catch (e) { E.runs = []; E.runsError = e.message; q('[data-r="runs"]').innerHTML = UI.errorBlock('실행 기록을 읽지 못했습니다', e.message, { cls: 'compact' }); }
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
})();
