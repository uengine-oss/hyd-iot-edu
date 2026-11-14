/* A4 (U6) 판단 채점 — 사람이 적은 정답표에 AI 판단을 대어 점수를 내고, 실행을 남겨 지식 고치기 전·후를 비교한다.
   API: process /api/eval/* (procsvc/eval_api.py). 정답표는 화면에서 적는 데이터이고 처음엔 비어 있다 — 이 파일에도 정답은 없다.
   화면: window.hydEval.mount(el). 포털 셸이 컨테이너(#evalView)를 주면 그 안에 전부 그린다. 채점은 처리 건 · 설비 명령 · 기준 데이터를 바꾸지 않는다.
   짜임(디자인 기준 5-6 「조건 → 결과」): 보기 셋(채점 · 정답표 · 전 · 후 비교). 채점은 왼쪽 조건 판과 [채점 실행], 오른쪽에 실시간 상자(도는 동안 — 서버가 적는 단계가 하나씩 채워지고,
   항목 몇 개 가운데 몇 개가 끝났는지 진행 막대가 센다) → 고른 실행의 결과(평균 한 줄과 검사 네 가지의 맞은 수 → 항목별 검사 → 원문 접기) → 「지난 실행」 목록.
   부품은 키트의 것(panel · fieldset · field · seg · turn-facts · evid · rows · table · fold · stream · progress)이고 격자는 reading.css(.io)다. 맞음 · 틀림은 상태 뱃지(점 + 글)로 보인다. */
(function () {
  const E = { el: null, golden: [], storage: '', paths: {}, maxRepeats: 10, assets: [], facts: {}, runs: [], sel: null, run: null, editing: null,
    knowledge: null, cands: null, patterns: null, cmp: null, busy: false, picked: new Set(), view: 'run' };
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
  const sec = (title, side, body) => body ? `<div class="panel-sec"><h3>${title}${side ? `<span class="muted">${side}</span>` : ''}</h3>${body}</div>` : '';
  const fact = (label, value) => `<div><dt>${esc(label)}</dt><dd>${value}</dd></div>`;
  const note = (text, attrs = '') => text ? `<p class="muted"${attrs}>${text}</p>` : '';
  const warn = text => `<p class="muted" role="status">${UI.chipText('주의', 'warning')} ${text}</p>`;
  const table = (head, rows) => `<div class="table-container"><table class="table"><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table></div>`;
  const patternName = code => { const p = (E.patterns || []).find(x => x.code === code); return p ? p.name : code; };
  // 누가 적고 실행했는지 = 이 PC의 담당자 id(서버 eval_api.by_of 는 빈 값만 거절한다). 담당자를 못 읽으면 다른 값으로 대신하지 않고 막는다
  const NEED_ME = '담당자 정보를 읽지 못해 보낼 수 없습니다. 화면을 새로 고친 뒤 다시 해 주세요.';
  function meId() { const id = window.hydInbox?.me?.()?.id; if (!id) throw new Error(NEED_ME); return id; }
  // 그래프 관계 종류(영문) → 지식 지도와 같은 이름(enterprise.js RELATION_KO 한 곳). 그 표에 없는 종류만 원문 그대로
  const relName = (type) => (typeof RELATION_KO === 'object' && RELATION_KO[type]) || type;

  // 채점 실행은 N회 판단이라 30초를 넘길 수 있다 — 공용 요청 함수에 시간 제한 없이(끊김 · 거절 문구는 공용 함수가 학생 말로 바꾼다)
  const longJ = (url, method, body) => postJ(url, body, method, { timeout: 0 });
  // 폼 아래 한 줄(못 한 까닭): 빈 글이면 줄이 사라진다
  const msg = (key, text, isBad = true) => { const m = q(`[data-msg="${key}"]`); if (!m) return; m.textContent = text || ''; m.hidden = !text; if (isBad && text) m.dataset.tone = 'danger'; else delete m.dataset.tone; };
  const msgLine = key => `<p class="muted" data-msg="${key}" role="status" hidden></p>`;

  /* ---------------------------------------------------------------- 뼈대 */
  function skeleton() {
    E.el.innerHTML = `
      ${UI.pageHead('eval', { sub: '사람이 적은 정답표에 판단을 대어 점수를 내고, 지식을 고치기 전과 후를 비교합니다.', more: [{ act: 'reload', attrs: 'data-act="reload"' }] })}
      <div class="io-bar"><div class="tabs view-tabs"><nav role="tablist" aria-orientation="horizontal" aria-label="보기" data-r="seg"></nav></div><span class="muted" data-r="knowledge"></span></div>
      <div data-view="run">
        <div class="io"><form class="panel io-in" data-r="runform" aria-label="채점 조건"></form>
          <div class="io-out" aria-live="polite"><div data-r="live" hidden></div><div data-r="cands" hidden></div><div data-r="detail"></div>
            <section class="panel"><div class="panel-head"><div><h2>지난 실행</h2></div></div><div class="panel-sec" data-r="runs"></div></section></div></div>
      </div>
      <div data-view="golden" hidden>
        <div class="io-out">
          <section class="panel"><div class="panel-head"><div><h2>정답표</h2><p>경보 상황마다 기대하는 원인, 1위로 허용되는 조치, 빠져야 할 조치, 있어야 할 근거를 적습니다.</p></div>
            <button type="button" class="btn" data-act="new">${UI.icon('plus')}새 항목 적기</button></div><div class="panel-sec" data-r="golden"></div></section>
          <div data-r="form"></div></div>
      </div>
      <div data-view="cmp" hidden>
        <div class="io"><form class="panel io-in" data-r="cmpform" aria-label="비교할 두 실행"></form><div class="io-out" data-r="cmp" aria-live="polite"></div></div>
      </div>`;
    E.el.addEventListener('click', onClick);
    E.el.addEventListener('change', onChange);
    E.el.addEventListener('submit', e => e.preventDefault());      // 칸에서 Enter 를 눌러도 화면이 새로 열리지 않게
    setView(E.view);
  }
  // 보기 바꾸기: 채점(조건 → 결과 → 지난 실행) · 정답표 · 전 · 후 비교
  function setView(view) {
    E.view = view;
    E.el.querySelectorAll('[data-view]').forEach(n => { n.hidden = n.dataset.view !== view; });
    renderStats();
  }
  // 보기 줄(건수는 이름 뒤 작은 숫자)과 그 오른쪽의 지금 지식 한 줄
  function renderStats() {
    const seg = [['run', '채점', E.runsError || !E.runsRead ? null : E.runs.length], ['golden', '정답표', E.goldenError || !E.goldenRead ? null : E.golden.length], ['cmp', '전 · 후 비교', null]];      // 아직 읽지 못한 것을 0으로 보이지 않는다
    q('[data-r="seg"]').innerHTML = seg.map(([k, l, n]) =>
      `<button type="button" role="tab" data-act="view" data-to="${k}" aria-selected="${k === E.view}" tabindex="${k === E.view ? 0 : -1}">${esc(l)}${n != null ? `<span class="num">${esc(n)}</span>` : ''}</button>`).join('');
    const k = E.knowledge, host = q('[data-r="knowledge"]');
    if (!k) { host.textContent = E.knowledgeError || ''; if (E.knowledgeError) host.dataset.tone = 'danger'; else delete host.dataset.tone; return; }
    delete host.dataset.tone;
    // 이 수가 세는 범위(서버 scope — 가상 설비 3기 전체)는 마우스를 올리면 뜬다: 지식 지도는 고른 설비 하나로 세므로 수가 다르다
    host.title = k.scope || '';
    host.textContent = `지금 지식(설비 전체): 항목 ${k.nodes}개 · 연결 ${k.relationships}개${k.last_change ? ' · 마지막 변경 ' + UI.dateTime(k.last_change) : k.last_change_note ? ' · ' + k.last_change_note : ''}`;
  }

  /* ---------------------------------------------------------------- 1. 정답표 */
  function renderGolden() {
    const host = q('[data-r="golden"]');
    if (!E.golden.length) {
      host.innerHTML = `${UI.empty({ icon: 'clipboard-check', title: `정답표가 비어 있습니다`, sub: `[새 항목 적기]로 경보 상황 하나와 기대하는 판단을 적습니다. 미리 들어 있는 정답은 없습니다.` })}`;
      return;
    }
    host.innerHTML = table('<th>채점</th><th>경보 상황</th><th>기대 원인</th><th>1위 허용</th><th>빠질 조치</th><th>있어야 할 근거</th>',
      E.golden.map(it => `<tr>
        <td><input type="checkbox" class="input" data-pick="${esc(it.id)}" ${E.picked.has(it.id) ? 'checked' : ''} aria-label="${esc(it.title)} 채점에 포함"></td>
        <td><button type="button" class="btn" data-variant="link" data-edit="${esc(it.id)}">${esc(it.title)}</button><p class="muted">${esc(it.asset)} · ${esc(patternName(it.pattern))} · ${esc(factsText(it.facts))}</p></td>
        <td>${nm(it.expected.cause)}<p class="muted">${nm(it.expected.failure_mode)}</p></td>
        <td>${it.allowed_top.map(nm).join('<br>')}</td>
        <td>${it.forbidden.length ? it.forbidden.map(f => `${nm(f.skill)} <span class="muted">${esc(EXPECT[f.expect])}</span>`).join('<br>') : '<span class="muted">없음</span>'}</td>
        <td>${it.required_evidence.map(nm).join('<br>')}</td></tr>`).join('')) +
      note('채점에 포함할 항목에 표시합니다. 아무것도 표시하지 않으면 전체를 채점합니다. 제목을 누르면 고칠 수 있습니다.');
  }

  // 정답표 폼의 고르기: 칸에는 지식의 이름이 보이고, 서버에는 그 항목의 id 를 보낸다(학생이 cause:… · skill:… 같은 id 를 보거나 적지 않는다).
  // 이름 사전(UI.names — 지식 그래프에서 읽은 것)에서 종류별로 「보이는 이름 → id」 표를 만든다. 같은 이름이 둘이면 뒤에 구분 글을 붙인다
  const KINDS = { cause: ['cause:'], fm: ['fm:'], skill: ['skill:'], evidence: ['evd:', 'rule:', 'ks:'], rule: ['rule:'] };
  const KIND_WORD = { 'evd:': '증거', 'rule:': '규칙', 'ks:': '매뉴얼 절' };
  function nameMap(kind) {
    const all = Object.entries(UI.names || {}).filter(([id, name]) => name && KINDS[kind].some(p => id.startsWith(p)));
    const count = {}; all.forEach(([, name]) => { count[name] = (count[name] || 0) + 1; });
    return new Map(all.map(([id, name]) => [count[name] > 1 ? `${name} (${id.split(':').pop()})` : name, id]));
  }
  const labelOf = (kind, id) => { for (const [label, i] of nameMap(kind)) if (i === id) return label; return ''; };
  const shown = (kind, id) => labelOf(kind, id) ? esc(labelOf(kind, id)) : `<span class="muted" data-tone="danger">지식에서 이름을 찾지 못한 항목 (${esc(id)})</span>`;
  const datalists = () => Object.keys(KINDS).map(kind => `<datalist id="evalDl-${kind}">${[...nameMap(kind)].map(([label, id]) =>
    `<option value="${esc(label)}">${kind === 'evidence' ? esc(KIND_WORD[Object.keys(KIND_WORD).find(p => id.startsWith(p))] || '') : ''}</option>`).join('')}</datalist>`).join('');
  // 이름으로 찾아 넣는 칸: 글자를 치면 목록이 좁혀지고, 고르면 아래 「고른 것」 목록에 한 줄이 더해진다
  const picker = (field, kind, label) => `<input class="input" data-add-to="${field}" data-kind="${kind}" list="evalDl-${kind}" placeholder="이름으로 찾아 넣기" aria-label="${esc(label)} 이름으로 찾아 넣기" autocomplete="off">`;
  // 고른 것 목록(이름으로 보이고 줄마다 [빼기]). 빠져야 할 조치는 줄마다 기대(제외돼야 함 · 1위면 안 됨)와 근거 규칙(선택)을 고른다
  function picksHtml(field) {
    const d = E.editing.draft, xs = d[field], kind = field === 'required_evidence' ? 'evidence' : 'skill';
    const drop = i => `<button type="button" class="btn" data-variant="ghost" data-size="sm" data-unpick="${field}" data-i="${i}">${UI.icon('x')}빼기</button>`;
    if (!xs.length) return note('아직 고른 것이 없습니다.');
    if (field !== 'forbidden') return `<ul class="evid">${xs.map((id, i) => `<li>${UI.icon('check')}<span><b>${shown(kind, id)}</b> ${drop(i)}</span></li>`).join('')}</ul>`;
    return `<ul class="evid">${xs.map((x, i) => `<li>${UI.icon('x')}<span><b>${shown('skill', x.skill)}</b> ` +
      `<select class="select" data-size="sm" data-forbid="${i}" aria-label="기대">${Object.entries(EXPECT).map(([v, l]) => `<option value="${v}" ${x.expect === v ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select> ` +
      `<input class="input" data-size="sm" data-forbid-rule="${i}" list="evalDl-rule" value="${esc(labelOf('rule', x.rule) || '')}" placeholder="근거 규칙(선택)" aria-label="근거 규칙" autocomplete="off"> ${drop(i)}</span></li>`).join('')}</ul>`;
  }
  const paintPicks = field => { const host = q(`[data-picks="${field}"]`); if (host) host.innerHTML = picksHtml(field); };
  // 항목의 열쇠(서버 계약: 영문 소문자 · 숫자 · 하이픈 2~64자, 저장 뒤 바뀌지 않음 — judgment_eval.ITEM_ID). 화면에 보이지 않는 안쪽 이름이라 학생이 짓지 않고 화면이 만든다
  const newItemId = () => 'item-' + Date.now().toString(36);

  function renderForm() {
    const host = q('[data-r="form"]');
    const add = q('[data-act="new"]'); if (add) { if (E.editing) add.dataset.variant = 'outline'; else delete add.dataset.variant; }      // 폼이 열려 있는 동안 주 단추는 [저장] 하나
    if (!E.editing) { host.innerHTML = ''; return; }
    const it = E.editing.item || { facts: {}, expected: {}, allowed_top: [], forbidden: [], required_evidence: [] };
    const isNew = !E.editing.item;
    const sel = (id, opts, cur, blank) => `<select data-f="${id}">${blank ? `<option value="">${esc(blank)}</option>` : ''}${opts.map(([v, l]) => `<option value="${esc(v)}" ${String(cur ?? '') === String(v) ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select>`;
    const pats = (E.patterns || []).map(p => [p.code, p.name]);
    const f = it.facts || {};
    // 고르는 동안의 값(id)은 여기에 둔다 — 칸에는 이름만 보인다
    const d = E.editing.draft = E.editing.draft || { cause: it.expected.cause || '', failure_mode: it.expected.failure_mode || '', allowed_top: [...(it.allowed_top || [])],
      forbidden: (it.forbidden || []).map(x => ({ ...x })), required_evidence: [...(it.required_evidence || [])] };
    // 고치는 폼은 정답표 아래의 판 하나: 절마다 fieldset → 맨 아래에 [지우기] · 못 한 까닭 · [취소] · [저장](주 단추)
    host.innerHTML = `<form class="panel" aria-label="정답표 항목"><div class="panel-head"><div><h2>${isNew ? '새 정답표 항목' : '정답표 항목 고치기'}</h2></div></div><div class="panel-sec">` +
      datalists() +
      UI.section('경보 상황',
        UI.field({ label: '제목', required: true, input: `<input data-f="title" value="${esc(it.title || '')}" placeholder="예: 쿨러 성능 저하 · 원격 자동 운전">` }) +
        UI.field({ label: '설비', required: true, input: sel('asset', E.assets.map(a => [a, a]), it.asset || '', '설비 선택') }) +
        UI.field({ label: '이상 패턴', required: true, error: E.patterns ? '' : E.patternError || '', input: pats.length ? `<select data-f="pattern"><option value="">이상 패턴 선택</option>${UI.patternOptions(E.patterns, it.pattern || '')}</select>` : '<select data-f="pattern" disabled><option value="">목록을 읽지 못함</option></select>' })) +
      UI.section('가정 사실(비우면 지금 값을 씁니다)', Object.entries(E.facts).map(([k, spec]) => UI.field({ label: spec.label,
        input: spec.number ? `<input data-f="${esc(k)}" data-fact="number" type="number" min="0" step="1" value="${esc(f[k] ?? '')}" placeholder="지금 값">`
          : sel(k, [['', '지금 값'], ...spec.choices.map(([v, l]) => [JSON.stringify(v), l])], f[k] == null ? '' : JSON.stringify(f[k])) })).join('')) +
      UI.section('기대하는 판단',
        UI.field({ label: '기대 원인', required: true, input: `<input data-f="cause" list="evalDl-cause" value="${esc(labelOf('cause', d.cause) || '')}" placeholder="원인 이름으로 찾기" autocomplete="off">`, hint: '지식의 원인 이름 가운데 고릅니다.' }) +
        UI.field({ label: '고장 유형', required: true, input: `<input data-f="failure_mode" list="evalDl-fm" value="${esc(labelOf('fm', d.failure_mode) || '')}" placeholder="고장 유형 이름으로 찾기" autocomplete="off">` }) +
        UI.field({ label: '1위로 허용되는 조치', required: true, cls: 'wide', hint: '조치 방법 이름을 찾아 고르면 아래에 더해집니다. 여러 개를 고를 수 있습니다.', input: `${picker('allowed_top', 'skill', '1위로 허용되는 조치')}<div data-picks="allowed_top">${picksHtml('allowed_top')}</div>` }) +
        UI.field({ label: '빠져야 할 조치', cls: 'wide', hint: '판단에서 제외돼야 하거나 1위가 되면 안 되는 조치 방법을 고릅니다. 줄마다 어느 쪽인지 고르고, 그 근거가 되는 규칙이 있으면 함께 고릅니다.', input: `${picker('forbidden', 'skill', '빠져야 할 조치')}<div data-picks="forbidden">${picksHtml('forbidden')}</div>` }) +
        UI.field({ label: '근거에 있어야 할 지식', required: true, cls: 'wide', hint: '판단의 근거에 들어 있어야 할 증거, 규칙, 매뉴얼 절을 이름으로 찾아 고릅니다.', input: `${picker('required_evidence', 'evidence', '근거에 있어야 할 지식')}<div data-picks="required_evidence">${picksHtml('required_evidence')}</div>` })) +
      UI.section('', UI.field({ label: UI.t('form.note'), cls: 'wide', input: `<input data-f="note" value="${esc(it.note || '')}" placeholder="이 항목을 왜 적었는지(선택)">` })) +
      (pats.length ? '' : UI.errorBlock('이상 패턴 목록을 읽지 못해 지금은 저장할 수 없습니다', '화면 위의 [다시 읽기]를 눌러 주세요.')) +
      `<footer class="form-foot">${isNew ? '' : `<button type="button" class="btn" data-variant="destructive" data-act="delete" data-tooltip="지워도 지난 채점 실행 기록은 남습니다">${UI.icon('trash-2')}이 항목 지우기</button>`}` +
      `<span class="muted" data-msg="form" role="status" hidden></span>` +
      `<button type="button" class="btn" data-variant="outline" data-act="cancel">${esc(UI.t('btn.cancel'))}</button>` +
      `<button type="button" class="btn" data-act="save" ${pats.length ? '' : 'disabled'}>${esc(UI.t('btn.save'))}</button></footer></div></form>`;
    host.scrollIntoView({ block: 'start', behavior: 'smooth' });
  }

  function readForm() {
    const v = (k) => { const n = q(`[data-f="${k}"]`); return n ? n.value.trim() : ''; };
    const facts = {};
    Object.entries(E.facts).forEach(([k, spec]) => { const raw = v(k);           // 선택지 값은 JSON 글로 담아 종류(글 · 참/거짓)를 그대로 되살린다
      if (raw !== '') facts[k] = spec.number ? Number(raw) : JSON.parse(raw); });
    const d = E.editing.draft;
    // 이름 칸에 적힌 글 → id. 목록에 없는 글이면 보내지 않고 말한다(빈 정답이나 엉뚱한 id 로 저장되지 않게)
    const pick = (kind, text, what) => { if (!text) throw new Error(`${what} 칸이 비어 있습니다`); const id = nameMap(kind).get(text); if (!id) throw new Error(`${what} 「${text}」: 목록에 있는 이름을 고르세요`); return id; };
    const cause = pick('cause', v('cause'), '기대 원인'), failure_mode = pick('fm', v('failure_mode'), '고장 유형');
    if (!d.allowed_top.length) throw new Error('1위로 허용되는 조치를 하나 이상 고르세요');
    if (!d.required_evidence.length) throw new Error('근거에 있어야 할 지식을 하나 이상 고르세요');
    const forbidden = d.forbidden.map(x => ({ skill: x.skill, expect: x.expect, ...(x.rule ? { rule: x.rule } : {}), ...(x.why ? { why: x.why } : {}) }));
    if (!v('asset')) throw new Error('설비를 고르세요');
    if (!v('pattern')) throw new Error('이상 패턴을 고르세요');
    const by = meId();
    return { by, item: { id: E.editing.item ? E.editing.item.id : (E.editing.newId = E.editing.newId || newItemId()), title: v('title'), asset: v('asset'), pattern: v('pattern'), facts,
      expected: { cause, failure_mode }, allowed_top: [...d.allowed_top], forbidden, required_evidence: [...d.required_evidence], note: v('note') } };
  }

  /* ---------------------------------------------------------------- 2. 채점 실행 */
  // 왼쪽: 채점 조건 → [채점 실행]. 지난 처리 건 경로면 채점할 처리 건 표가 오른쪽 맨 위에 나온다
  function renderRunForm() {
    const path = E.path || 'decide';
    const picked = E.golden.filter(it => E.picked.has(it.id));
    const target = path === 'worker' ? '오른쪽 표에서 채점할 처리 건을 고릅니다.'
      : `채점할 항목: ${picked.length ? picked.map(it => it.title).join(' · ') : `정답표 전체 (${E.golden.length}개)`}`;
    const toGolden = (label) => `<button type="button" class="btn" data-variant="link" data-act="view" data-to="golden">${label}${UI.icon('arrow-right')}</button>`;
    q('[data-r="runform"]').innerHTML = `<div class="panel-head"><div><h2>채점 조건</h2></div></div><div class="panel-sec">` +
      // 고를 것(판단 경로)만 위에 둔다. 어느 경로가 AI 인지는 한 줄로 말하고, 고른 경로의 자세한 안내(서버 문장 judgment_eval.PATH_NOTES)는 그 줄의 도움말(올리면 나온다)에 둔다. 반복 횟수 · 메모는 기본값으로 접는다
      `<div class="io-fields">${UI.field({ label: '판단 경로', input: `<select data-f="path">${Object.entries(PATH).map(([k, l]) => `<option value="${k}" ${k === path ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select>`, hint: 'AI가 판단하는 것은 「지난 처리 건」 하나입니다. 나머지 둘은 AI 모델 없이 계산합니다.' }).replace('<p class="field-hint">', `<p class="field-hint" data-eval-ai-note title="${esc(String(E.paths[path] || ''))}">`)}</div>` +
      `<details class="fold io-more"${E.moreOpen ? ' open' : ''} data-eval-more><summary>더 정하기<span class="muted">반복 ${esc(E.repeats || 1)}회</span></summary><div class="fold-body io-fields">` +
        (path === 'worker' ? '' : UI.field({ label: '반복 횟수', input: `<input data-f="repeats" type="number" min="1" max="${E.maxRepeats}" value="${esc(E.repeats || 1)}">`, hint: '여러 번 판단해 결과가 흔들리는지 봅니다.' })) +
        UI.field({ label: UI.t('form.note'), input: `<input data-f="runNote" placeholder="예: 관계 하나 끊기 전">` }) + '</div></details>' +
      (E.golden.length ? note(`${esc(target)}${path === 'worker' ? '' : ' ' + toGolden('정답표에서 고르기')}`)
        : E.goldenError ? '' : note(`정답표가 비어 있어 채점할 수 없습니다. ${toGolden('정답표 적기')}`, ' role="status"')) +
      `<footer class="form-foot"><button type="button" class="btn" data-act="run" ${E.golden.length && !E.busy ? '' : 'disabled'}>${UI.icon('play')}채점 실행</button></footer>` + msgLine('run') +
      `</div>`;
    q('[data-eval-more]')?.addEventListener('toggle', e => { E.moreOpen = e.target.open; });
    const cands = q('[data-r="cands"]'); cands.hidden = path !== 'worker'; cands.innerHTML = path === 'worker' ? renderCands() : '';
    showRunWait();
  }
  // 서버 문장 속의 처리 건 안쪽 번호와 경보 코드는 화면 말로 바꾼다(「처리 건 c3_cooling.6655…(HYD-01 · COOLER_DEGRADATION)에 …」 → 「이 처리 건(HYD-01 · 쿨러 성능 저하)에 …」)
  const matchNote = text => String(text || '맞는 항목 없음').replace(/처리 건 \S+?\(([^)]*)\)/, (m, inner) => `이 처리 건(${inner.split(' · ').map(x => patternName(x)).join(' · ')})`);
  function renderCands() {
    const panel = body => `<section class="panel"><div class="panel-head"><div><h2>채점할 지난 처리 건</h2><p>원인 진단과 조치 후보 단계까지 끝난 처리 건입니다. 정답표에 맞는 항목이 있는 건만 고를 수 있습니다.</p></div></div><div class="panel-sec">${body}</div></section>`;
    if (E.cands == null) return panel(UI.loading());
    if (E.cands.error) return UI.errorBlock('지난 처리 건을 읽지 못했습니다', E.cands.error, { retry: true });
    if (!E.cands.length) return panel(UI.emptyGo('채점할 지난 처리 건이 없습니다', '원인 진단과 조치 후보 단계까지 끝난 처리 건이 여기에 나타납니다.', 'scenario', '결함 시뮬레이션에서 사건 만들기', 'compact'));
    return panel(table('<th>채점</th><th>처리 건</th><th>AI 에이전트의 판단</th><th>맞는 정답표 항목</th>', E.cands.map(c => {
      const item = E.golden.find(it => it.id === c.item);
      return `<tr><td><input type="checkbox" class="input" data-cand="${esc(c.instance)}" ${item ? '' : 'disabled'} aria-label="${esc(c.name || '처리 건')} 채점에 포함"></td>
        <td>${esc(c.name || '이름 없는 처리 건')}<p class="muted">${esc(UI.dateTime(c.started))} · ${esc(UI.status(c.status))}</p></td>
        <td>${nm(c.cause)} → ${nm(c.chosen_skill)}<p class="muted">${esc(factsText(c.facts))}</p></td>
        <td>${item ? esc(item.title) : `<span class="muted">${esc(matchNote(c.match_note))}</span>`}</td></tr>`;
    }).join('')));
  }
  async function loadCands() {
    E.cands = null; const host = q('[data-r="cands"]'); if (host) host.innerHTML = renderCands();
    try { E.cands = await getJ(API.process + '/api/eval/worker-candidates?limit=30'); } catch (e) { E.cands = { error: e.message }; }
    const h = q('[data-r="cands"]'); if (h) h.innerHTML = renderCands();
  }

  // 채점이 도는 동안: 단추는 「채점하는 중 · 걸린 시간」, 결과 자리 맨 위의 실시간 상자에 서버가 적는 진행이 하나씩 채워진다
  // (정답표 읽기 → 지식 상태 읽기 → 항목마다 결과 → 저장 — hydLive.track). 그 머리 아래의 진행 막대는 서버가 적은 항목 단계를 센 값이다(항목 5개 가운데 2개).
  // 실행 칸이 다시 그려져도(항목 고르기 등) 실시간 상자는 결과 자리에 그대로 있다
  function showRunWait() {
    const w = E.runWait, btn = q('[data-act="run"]'), live = q('[data-r="live"]'); if (!w || !btn || !live) return;
    hydLive.busy(btn, '채점하는 중', w.since);
    if (w.mounted) return;
    w.mounted = true; live.hidden = false; w.track.mount(live);
    const root = live.firstElementChild, steps = root && root.querySelector('[data-lv-track-steps]');
    if (!steps) return;
    const bar = document.createElement('div'); bar.className = 'io-progress'; bar.hidden = true;
    bar.innerHTML = `<span data-r="count"></span><div class="progress" role="progressbar" aria-valuemin="0" aria-label="끝난 항목"><span style="width:0%"></span></div>`;
    steps.before(bar);
    const count = () => {      // 서버가 정답표를 읽은 뒤에야 항목 단계가 생긴다 — 그 전에는 막대를 그리지 않는다(지어낸 진행률 없음)
      const items = [...steps.querySelectorAll('[data-step^="item:"]')], done = items.filter(n => n.classList.contains('ok') || n.classList.contains('fail')).length;
      bar.hidden = !items.length; if (!items.length) return;
      bar.querySelector('[data-r="count"]').textContent = `${w.unit} ${items.length}개 가운데 ${done}개 끝남`;
      const p = bar.querySelector('.progress'); p.setAttribute('aria-valuemax', items.length); p.setAttribute('aria-valuenow', done);
      p.firstElementChild.style.width = Math.round(done / items.length * 100) + '%';
    };
    w.watch = new MutationObserver(count); w.watch.observe(steps, { childList: true, subtree: true, attributes: true, attributeFilter: ['class'] });
  }
  async function runEval() {
    if (E.busy) return;
    const path = q('[data-f="path"]').value, runNote = q('[data-f="runNote"]').value.trim();
    let by; try { by = meId(); } catch (e) { msg('run', e.message); return; }
    const body = { path, by, note: runNote || null };
    if (path === 'worker') {
      body.instances = [...E.el.querySelectorAll('[data-cand]:checked')].map(n => ({ instance: n.dataset.cand }));
      if (!body.instances.length) { msg('run', '채점할 처리 건을 하나 이상 고르세요'); return; }
    } else {
      body.repeats = Math.max(1, Math.min(E.maxRepeats, Number(q('[data-f="repeats"]').value) || 1)); E.repeats = body.repeats;
      if (E.picked.size) body.items = [...E.picked];
    }
    E.busy = true; E.busyWhy = '채점 중에는 할 수 없습니다. 채점이 끝난 뒤 다시 눌러 주세요.';
    const n = path === 'worker' ? body.instances.length : (body.items || E.golden).length * body.repeats;
    // 서버는 항목(또는 처리 건) 하나를 끝낼 때마다 진행 기록에 그 결과를 적는다 — 화면은 그것을 읽어 아래에 하나씩 채운다. 채점 결과 전체는 끝난 뒤 한 번에 온다
    const since = new Date().toISOString();
    E.runWait = { since, unit: path === 'worker' ? '처리 건' : '항목', track: hydLive.track({ since, text: `판단 ${n}회를 정답표와 견주는 중`, hint: path === 'worker' ? '고른 지난 처리 건의 AI 판단을 정답표 항목과 차례로 견줍니다.'
      : `판단 엔진에 ${n}번 묻습니다(항목 ${n / body.repeats}개 × ${body.repeats}회). 항목이 끝날 때마다 아래에 결과가 채워집니다.` }) };
    body.request_id = E.runWait.track.id;
    msg('run', ''); showRunWait();
    let failed = null;
    try {
      const run = await longJ(API.process + '/api/eval/runs', 'POST', body);
      E.sel = run.id; E.run = run;
      await loadRuns(); renderDetail();
      UI.toast(`채점을 마쳤습니다. 평균 ${run.summary.score}점입니다.`, { tone: 'ok' });
    } catch (e) { failed = e.message; }
    finally {
      E.runWait.track.stop(); E.runWait.watch?.disconnect(); E.busy = false; E.runWait = null;
      const live = q('[data-r="live"]');      // 실시간 상자는 끝나면 거둔다 — 성공이면 그 아래에 결과가 열려 있고, 실패면 그 자리에 까닭이 남는다
      live.innerHTML = failed ? UI.errorBlock('채점하지 못했습니다', failed) : ''; live.hidden = !failed;
      renderRunForm();      // 실행 칸을 다시 그려 단추를 원래대로 한다
    }
  }

  /* ---------------------------------------------------------------- 3. 실행 기록 */
  // 지난 실행: 표 한 장(시각 · 판단 경로 · 항목 · 평균 · 메모). 줄을 누르면(또는 Enter) 위 결과 자리에 그 실행이 열린다
  function renderRuns() {
    const host = q('[data-r="runs"]');
    if (!E.runs.length) { host.innerHTML = UI.empty('아직 채점 실행이 없습니다', '정답표를 적고 [채점 실행]을 누르면 여기에 남습니다.', 'compact'); return; }
    host.innerHTML = `<div class="table-container"><table class="table eval-runs"><thead><tr><th>시각</th><th>판단 경로</th><th class="num">항목</th><th class="num">평균</th><th>메모</th></tr></thead><tbody>${E.runs.map(r =>
      `<tr data-run="${esc(r.id)}" tabindex="0" role="button"${r.id === E.sel ? ' data-pick aria-current="true"' : ''}><td>${esc(UI.dateTime(r.created))}</td><td>${esc(PATH[r.path] || r.path)}</td><td class="num">${esc(r.summary.items)}</td><td class="num"><b>${esc(r.summary.score)}</b>점</td><td class="muted">${esc(r.note || '')}</td></tr>`).join('')}</tbody></table></div>`;
    host.querySelectorAll('tr[data-run]').forEach(tr => tr.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); tr.click(); } }));
  }
  // 검사 한 줄: 맞음 · 틀림은 상태 뱃지(점 + 글)로, 그 뒤에 판단과 정답
  function checkLine(key, c) {
    let detail = '';
    if (key === 'cause') detail = `판단 ${nm(c.got)} · 정답 ${nm(c.want)}` + (c.got_failure_mode !== c.want_failure_mode ? ` <span class="muted">(고장 유형 ${nm(c.got_failure_mode)} / ${nm(c.want_failure_mode)})</span>` : '');
    if (key === 'top') detail = `1위 ${nm(c.got)} · 허용 ${c.allowed.map(nm).join(', ')}`;
    if (key === 'forbidden') detail = c.detail.length ? c.detail.map(d => `${nm(d.skill)} ${esc(EXPECT[d.expect])} → ${esc(UI.idText(d.got))}${d.ok ? '' : ' (틀림)'}`).join(' · ') : '정답표에 빠질 조치 없음 — 점수에 넣지 않음';
    if (key === 'evidence') detail = `${pct(c.ratio)}` + (c.missing.length ? ` · 빠진 근거 ${c.missing.map(nm).join(', ')}` : '');
    return `<li>${UI.icon(c.ok ? 'check' : 'x')}<span><b>${esc(CHECK[key])}</b> ${UI.chipText(c.ok ? '맞음' : '틀림', c.ok ? 'success' : 'danger')} ${detail}</span></li>`;
  }
  // 반복이면 검사마다 N회 중 맞은 수(서버 aggregate 의 check_hits), 아래 상세 줄은 마지막 회차 — 점수(평균)와 섞어 읽지 않게 밝힌다
  function checkLines(r) {
    const list = `<ul class="evid">${Object.keys(CHECK).map(k => checkLine(k, r.checks[k])).join('')}</ul>`;
    if (!(r.repeats > 1) || !r.check_hits) return list;
    const hits = Object.keys(CHECK).map(k => `${esc(CHECK[k])} ${esc(r.check_hits[k])}/${esc(r.repeats)}`).join(' · ');
    return note(`<b>${esc(r.repeats)}회 중 맞은 수</b> ${hits} — 아래는 마지막 회차의 검사입니다.`) + list;
  }
  // 항목 하나: 제목 · 점수 → 판단 한 줄 → 검사 네 가지 → 접기(조치 순위 원문 · 회차별 결과 · 채점한 처리 건)
  function itemResult(r) {
    const title = (E.golden.find(it => it.id === r.item) || {}).title || r.title;
    const repeat = r.repeats > 1 ? (r.identical ? note(`${esc(r.repeats)}회 모두 같은 결과${r.deterministic ? ' — 같은 지식과 같은 사실이면 늘 같은 결과가 나오는 경로라 1회와 같습니다' : ''}`)
      : warn(`흔들림: ${esc(r.repeats)}회 중 가장 많은 결과 ${pct(r.stability)} · 점수 ${esc(r.min)}~${esc(r.max)}`)) : '';
    const mismatch = (r.facts_mismatch || []).length ? warn(`정답표의 가정과 판단 때 사실이 다릅니다: ${r.facts_mismatch.map(m => `${esc(factLabel(m.key))} 정답표 ${esc(factVal(m.key, m.want))} / 판단 때 ${esc(factVal(m.key, m.got))}`).join(' · ')}`) : '';
    const more =
      `<p><b>조치 순위 (판단 원문)</b></p><ol>${(r.checks.top.order || []).map(o => `<li>${esc(UI.idText(o.replace(/^\d+\.\s*/, '')))}</li>`).join('') || '<li>후보 없음</li>'}</ol>` +
      (r.repeats > 1 && !r.identical ? `<p><b>회차별 결과</b></p><ul>${Object.entries(r.outcomes).map(([o, n]) => `<li>${esc(outcomeText(o))} <span class="muted">${esc(n)}회</span></li>`).join('')}</ul>` : '') +
      ((r.instances || []).length ? `<p><b>채점한 처리 건 ${r.instances.length}건</b></p><ul>${r.instances.map(i => `<li>${esc(i.name || '이름 없는 처리 건')} · 고른 조치 ${nm(i.chosen_skill)} <span class="muted">${esc(UI.dateTime(i.started))}</span></li>`).join('')}</ul>` : '');
    return `<div class="panel-sec" data-item="${esc(r.item)}"><h3>${esc(title)}${r.status && r.status !== 'EVALUATED' ? ' ' + UI.chip(r.status) : ''}<span class="muted"><b class="num">${esc(r.score)}점</b></span></h3>` +
      note(`${esc(r.asset)} · ${esc(patternName(r.pattern))} · ${esc(factsText(r.facts))}`) +
      `<div class="result"><div class="result-label">판단</div><div class="result-main">${esc(outcomeText(r.modal_outcome))}</div>${r.reason ? `<div class="result-sub">${esc(UI.idText(r.reason))}</div>` : ''}</div>` +
      checkLines(r) + mismatch + repeat + UI.fold('조치 순위 원문', more) + `</div>`;
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
    if (!r) { host.innerHTML = `${UI.empty({ icon: 'clipboard-check', title: `아직 고른 채점 실행이 없습니다`, sub: `왼쪽에서 [채점 실행]을 누르거나 아래 「지난 실행」에서 한 줄을 고르면 항목별 점수와 검사 네 가지가 보입니다.` })}`; return; }
    const s = r.summary, of = k => `<span class="num">${esc(s[k])}</span><small>/ ${esc(s.items)}</small>`;
    const extra = [s.withheld ? `판단 없음(보류 · 오류) ${esc(s.withheld)}개` : '', s.unstable ? `흔들림 ${esc(s.unstable)}개` : ''].filter(Boolean).join(' · ');
    host.innerHTML = `<section class="panel"><div class="panel-head"><div><div class="result-label">${UI.icon('sparkles')}결론</div><h2>평균 ${esc(s.score)}점 — 항목 ${esc(s.items)}개 · ${esc(PATH[r.path] || r.path)}</h2>` +
      `<p>${esc(UI.dateTime(r.created))} · ${esc(UI.who(r.by))}${r.note ? ' · ' + esc(r.note) : ''}</p></div></div>` +
      `<dl class="turn-facts">${fact('원인 적중', of('cause_hits'))}${fact('1위 허용', of('top_ok'))}${fact('빠질 조치 미추천', of('forbidden_ok'))}${fact('근거 모두 포함', of('evidence_ok'))}</dl>` +
      (extra ? `<div class="panel-sec">${warn(extra)}</div>` : '') +
      (r.items || []).map(itemResult).join('') +
      `<div class="panel-sec">${note('채점 때 지식: ' + knowledgeLine(r.knowledge))}</div></section>`;
  }
  async function selectRun(id) {
    E.sel = id; renderRuns();
    q('[data-r="detail"]').innerHTML = `<section class="panel"><div class="panel-head">${UI.loading()}</div></section>`;
    try { E.run = await getJ(API.process + '/api/eval/runs/' + encodeURIComponent(id)); } catch (e) { E.run = null; q('[data-r="detail"]').innerHTML = UI.errorBlock('채점 실행을 읽지 못했습니다', e.message); return; }
    renderDetail(); UI.revealDetail(q('[data-r="detail"]'));
  }

  /* ---------------------------------------------------------------- 4. 전 · 후 비교 */
  function renderCmpForm() {
    const host = q('[data-r="cmpform"]');
    const opts = (cur) => E.runs.map(r => `<option value="${esc(r.id)}" ${r.id === cur ? 'selected' : ''}>${esc(UI.dateTime(r.created))} · ${esc(r.summary.score)}점${r.note ? ' · ' + esc(r.note) : ''}</option>`).join('');
    const head = `<div class="panel-head"><div><h2>비교할 두 실행</h2></div></div>`;
    if (E.runsError) { host.innerHTML = head + `<div class="panel-sec">${UI.errorBlock('실행 기록을 읽지 못해 비교할 수 없습니다', E.runsError, { retry: true })}</div>`; return; }
    if (E.runs.length < 2) {
      host.innerHTML = head + `<div class="panel-sec">${note('비교하려면 채점 실행이 두 개 필요합니다. 지식을 고치기 전에 한 번, 고친 뒤에 한 번 채점합니다(예: Neo4j Browser에서 관계 하나 끊기, 매뉴얼 하나 더 넣기).')}` +
        `<footer class="form-foot"><button type="button" class="btn" data-variant="outline" data-act="view" data-to="run">채점하러 가기${UI.icon('arrow-right')}</button></footer></div>`;
      return;
    }
    host.innerHTML = head + `<div class="panel-sec">` +
      UI.section('두 실행',
        UI.field({ label: '고치기 전 실행', input: `<select data-f="before">${opts(E.cmpBefore || E.runs[1].id)}</select>` }) +
        UI.field({ label: '고친 뒤 실행', input: `<select data-f="after">${opts(E.cmpAfter || E.runs[0].id)}</select>` })) +
      `<footer class="form-foot"><button type="button" class="btn" data-act="compare">${UI.icon('git-compare')}두 실행 비교</button></footer>` + msgLine('cmp') + `</div>`;
  }
  // 비교 결과의 차례: 평균이 얼마나 바뀌었나(결론) → 좋아짐 · 나빠짐 · 같음의 수 → 두 실행 사이 지식 변화 → 항목별 변화 표
  function renderCmp() {
    const host = q('[data-r="cmp"]'), c = E.cmp;
    if (!c) { host.innerHTML = `${UI.empty({ icon: 'git-compare', title: `아직 비교한 결과가 없습니다`, sub: `왼쪽에서 고치기 전 실행과 고친 뒤 실행을 고르고 [두 실행 비교]를 누릅니다.` })}`; return; }
    const kd = c.knowledge || {};
    // 지식 변화: 서버가 바뀐 항목의 이름을 함께 준다(kd.names — 지식 지도와 같은 차례로 고른 이름). 이름이 있는 항목과 연결은 이름으로 보이고,
    // 이름이 없는 항목은 수만 말하고 원문은 접기에 둔다. 서버의 항목 수 · 연결 수는 지식 지도가 그리는 것만 센다(실행 기록 · 적재 이력은 세지 않는다 — judgment_eval.NOT_KNOWLEDGE_LABELS)
    const names = kd.names || {}, named = id => !!names[id] || !!UI.names[id];
    const nk = id => `<span title="${esc(id || '')}">${esc(names[id] || UI.name(id) || '–')}</span>`;
    const rel = (x) => `${nk(x.from)} → <span class="muted">${esc(relName(x.type))}</span> → ${nk(x.to)}`;
    const line = (icon, label, body) => `<li>${UI.icon(icon)}<span><b>${label}</b> ${body}</span></li>`;
    const split = (xs, ok) => [(xs || []).filter(ok), (xs || []).filter(x => !ok(x))];
    const relOk = x => named(x.from) && named(x.to);
    const [remR, remRx] = split(kd.removed_rels, relOk), [addR, addRx] = split(kd.added_rels, relOk);
    const [addN, addNx] = split(kd.added_nodes, named), [remN, remNx] = split(kd.removed_nodes, named), [chgN, chgNx] = split(kd.changed_nodes, named);
    const shownN = remR.length + addR.length + addN.length + remN.length + chgN.length, restN = remRx.length + addRx.length + addNx.length + remNx.length + chgNx.length;
    const rawRel = x => `${x.from} -[${x.type}]-> ${x.to}`;
    const rest = restN ? UI.raw([
      ...addNx.map(x => '새 항목  ' + x), ...remNx.map(x => '없어진 항목  ' + x), ...chgNx.map(x => '속성 바뀜  ' + x), ...addRx.map(x => '연결 추가  ' + rawRel(x)), ...remRx.map(x => '연결 삭제  ' + rawRel(x))].join('\n'), { title: `이름이 없는 항목의 변화 ${restN}개` }) : '';
    const know = !kd.comparable ? note(esc(kd.note || '')) : !kd.changed ? note('두 실행 사이에 지식 그래프가 바뀌지 않았습니다.') :
      (kd.counts ? `<p>${shownN ? `지식 항목과 연결 ${shownN}곳이 바뀌었습니다.` : '이름이 있는 지식 항목과 연결(원인 · 증거 · 규칙 · 조치 방법 · 매뉴얼)은 바뀌지 않았습니다.'}` +
          `${restN ? ` 그 밖에 이름이 없는 항목 ${restN}개가 달라졌습니다.` : ''}</p>` +
        (shownN ? `<ul class="evid">${remR.map(x => line('unlink', '연결 삭제', rel(x))).join('')}${addR.map(x => line('link', '연결 추가', rel(x))).join('')}` +
          `${addN.length ? line('plus', '새 항목', addN.map(nk).join(', ')) : ''}${remN.length ? line('minus', '없어진 항목', remN.map(nk).join(', ')) : ''}` +
          `${chgN.length ? line('pencil', '속성 바뀜', chgN.map(nk).join(', ')) : ''}</ul>` : '') + rest : note(esc(kd.note || ''))) +
      note(`지식 항목 ${esc(kd.nodes[0])}개 → ${esc(kd.nodes[1])}개 · 연결 ${esc(kd.relationships[0])}개 → ${esc(kd.relationships[1])}개 (가상 설비 3기 전체)`);
    const verdict = { improved: ['좋아짐', 'success'], regressed: ['나빠짐', 'danger'], same: ['같음', 'neutral'] };
    const delta = c.delta == null ? '–' : (c.delta > 0 ? '+' : '') + c.delta;
    const title = i => esc((E.golden.find(it => it.id === i) || {}).title || i);
    // 한쪽 실행에서만 채점한 항목: 지금 정답표에 있으면 제목으로, 지워진 항목은 수로 말한다(항목의 안쪽 이름을 보이지 않는다)
    // 제목은 서버가 그 실행에 적힌 것으로 준다(item_titles — 정답표에서 지워진 항목도 채점 당시 제목이 있다). 제목이 없는 것만 수로 말한다
    const onlyOne = [...c.only_before, ...c.only_after], onlyNames = onlyOne.map(i => (c.item_titles || {})[i] || (E.golden.find(it => it.id === i) || {}).title).filter(Boolean), onlyGone = onlyOne.length - onlyNames.length;
    const says = c.delta == null ? '두 실행에 함께 채점한 항목이 없어 평균 점수를 견줄 수 없습니다.' : c.delta === 0 ? '평균 점수가 그대로입니다.' : `평균 점수가 ${Math.abs(c.delta)}점 ${c.delta > 0 ? '올랐습니다' : '내렸습니다'}.`;
    host.innerHTML = `<section class="panel"><div class="panel-head"><div><div class="result-label">${UI.icon('sparkles')}결론</div><h2>${esc(says)}</h2>` +
      `<p>전 ${esc(UI.dateTime(c.before.created))} ${esc(c.before.note || '')} → 후 ${esc(UI.dateTime(c.after.created))} ${esc(c.after.note || '')}</p></div></div>` +
      `<dl class="turn-facts">${fact('평균 변화', `<span class="num">${esc(delta)}</span><small>점</small>`)}${fact('좋아짐', `<span class="num">${esc(c.improved)}</span><small>개</small>`)}${fact('나빠짐', `<span class="num">${esc(c.regressed)}</span><small>개</small>`)}${fact('같음', `<span class="num">${esc(c.same)}</span><small>개</small>`)}</dl>` +
      sec('두 실행 사이 지식 변화', '', know) +
      (c.golden_changed.length ? `<div class="panel-sec">${warn(`정답표가 두 실행 사이에 바뀐 항목: ${c.golden_changed.map(title).join(', ')} — 이 항목의 점수 변화는 지식이 아니라 정답 때문일 수 있습니다.`)}</div>` : '') +
      sec('항목별 변화', `${c.rows.length}개`, table('<th>항목</th><th class="num">전</th><th class="num">후</th><th>변화</th><th>바뀐 검사</th><th>판단 전 → 후</th>', c.rows.map(r => `<tr>
          <td>${esc(r.title)}</td><td class="num">${esc(r.before)}</td><td class="num">${esc(r.after)}</td><td><span class="num">${(r.delta > 0 ? '+' : '') + esc(r.delta)}</span> ${UI.chipText(verdict[r.verdict][0], verdict[r.verdict][1])}</td>
          <td>${r.changed.map(x => `${esc(CHECK[x.check])} ${x.before ? '맞음' : '틀림'} → ${x.after ? '맞음' : '틀림'}`).join('<br>') || '–'}${r.evidence_lost.length ? `<p class="muted">잃은 근거 ${r.evidence_lost.map(nm).join(', ')}</p>` : ''}${r.evidence_gained.length ? `<p class="muted">얻은 근거 ${r.evidence_gained.map(nm).join(', ')}</p>` : ''}</td>
          <td>${esc(outcomeText(r.outcome_before))}<p class="muted">→ ${esc(outcomeText(r.outcome_after))}</p></td></tr>`).join('')) +
        (c.only_before.length || c.only_after.length ? note(`한쪽 실행에서만 채점해 견주지 않은 항목 ${onlyOne.length}개${onlyNames.length ? ': ' + esc(onlyNames.join(', ')) : ''}${onlyGone ? ` (제목이 남지 않은 항목 ${onlyGone}개${onlyNames.length ? ' 포함' : ''})` : ''}`) : '')) + `</section>`;
  }
  async function compare() {
    E.cmpBefore = q('[data-f="before"]').value; E.cmpAfter = q('[data-f="after"]').value;
    if (E.cmpBefore === E.cmpAfter) { msg('cmp', '서로 다른 두 실행을 고르세요'); return; }
    msg('cmp', '');
    const end = hydLive.busy(q('[data-act="compare"]'), '비교하는 중');
    q('[data-r="cmp"]').innerHTML = `<section class="panel"><div class="panel-head">${UI.loading()}</div></section>`;
    try { E.cmp = await getJ(API.process + '/api/eval/compare?' + new URLSearchParams({ before: E.cmpBefore, after: E.cmpAfter })); renderCmp(); }
    catch (e) { E.cmp = null; q('[data-r="cmp"]').innerHTML = UI.errorBlock('두 실행을 비교하지 못했습니다', e.message); }
    finally { end(false); }
  }

  /* ---------------------------------------------------------------- 이벤트 · 읽기 */
  async function onClick(e) {
    const t = e.target.closest('[data-act],[data-edit],[data-run],[data-retry],[data-unpick]');
    if (!t) return;
    if (t.dataset.unpick) { E.editing.draft[t.dataset.unpick].splice(+t.dataset.i, 1); paintPicks(t.dataset.unpick); return; }
    // 채점 실행은 오래 걸린다 — 그동안에도 실행 기록 고르기와 [변경 취소]는 되고, 나머지는 왜 안 되는지 알린다(말없이 먹지 않게)
    if (E.busy && !t.dataset.run && !['cancel', 'view'].includes(t.dataset.act)) { UI.toast(E.busyWhy, { tone: 'neutral' }); return; }
    if (t.hasAttribute('data-retry')) return load();
    if (t.dataset.edit) { E.editing = { item: E.golden.find(it => it.id === t.dataset.edit) }; renderForm(); return; }
    if (t.dataset.run) { selectRun(t.dataset.run); return; }
    const act = t.dataset.act;
    if (act === 'reload') { const end = hydLive.busy(t, '읽는 중'); try { await load(); } finally { end(false); } return; }
    if (act === 'view') { setView(t.dataset.to); return; }
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
          UI.toast('정답표 항목을 저장했습니다.', { tone: 'ok' });
        } else {
          const by = meId();
          await requestJ(API.process + '/api/eval/golden/items/' + encodeURIComponent(E.editing.item.id) + '?by=' + encodeURIComponent(by), { method: 'DELETE' });
          E.picked.delete(E.editing.item.id);
          UI.toast('정답표 항목을 지웠습니다.', { tone: 'ok' });
        }
        E.editing = null; renderForm(); await loadGolden();
      } catch (err) { msg('form', err.message); }
      finally { E.busy = false; renderRunForm(); }      // 저장하는 동안 다시 그려진 [채점 실행]이 꺼진 채 남지 않게
    }
  }
  function onChange(e) {
    const t = e.target;
    if (t.dataset.pick) { t.checked ? E.picked.add(t.dataset.pick) : E.picked.delete(t.dataset.pick); renderRunForm(); return; }
    if (t.dataset.addTo) {      // 이름으로 찾아 넣기: 목록에 있는 이름만 받아 「고른 것」에 한 줄 더한다(값은 그 항목의 id)
      const field = t.dataset.addTo, text = t.value.trim(), d = E.editing.draft;
      if (!text) return;
      const id = nameMap(t.dataset.kind).get(text);
      if (!id) { msg('form', `「${text}」: 목록에 있는 이름을 고르세요`); return; }
      const has = field === 'forbidden' ? d.forbidden.some(x => x.skill === id) : d[field].includes(id);
      if (has) { msg('form', `「${text}」은(는) 이미 골랐습니다`); t.value = ''; return; }
      d[field].push(field === 'forbidden' ? { skill: id, expect: 'excluded' } : id);
      t.value = ''; msg('form', ''); paintPicks(field);
      return;
    }
    if (t.dataset.forbid) { E.editing.draft.forbidden[+t.dataset.forbid].expect = t.value; return; }
    if (t.dataset.forbidRule != null) {      // 근거 규칙(선택): 비우면 없앤다
      const row = E.editing.draft.forbidden[+t.dataset.forbidRule], text = t.value.trim(), id = text ? nameMap('rule').get(text) : '';
      if (text && !id) { msg('form', `근거 규칙 「${text}」: 목록에 있는 이름을 고르세요`); return; }
      if (id) row.rule = id; else delete row.rule; msg('form', '');
      return;
    }
    if (t.dataset.f === 'path') { E.path = t.value; renderRunForm(); if (t.value === 'worker') loadCands(); }
  }
  async function loadGolden() {
    try {
      const g = await getJ(API.process + '/api/eval/golden');
      E.golden = g.items || []; E.storage = g.storage; E.paths = g.paths || {}; E.maxRepeats = g.max_repeats; E.assets = g.assets || []; E.facts = g.facts || {};
      for (const id of [...E.picked]) if (!E.golden.some(it => it.id === id)) E.picked.delete(id);
      E.goldenError = ''; E.goldenRead = true;
      renderGolden();
    } catch (e) { E.golden = []; E.goldenError = e.message; q('[data-r="golden"]').innerHTML = UI.errorBlock('정답표를 읽지 못했습니다', e.message, { retry: true }); }
    renderRunForm(); renderStats();
    if (E.goldenError) msg('run', '정답표를 읽지 못해 채점할 수 없습니다: ' + E.goldenError);
  }
  async function loadRuns() {
    try { E.runs = await getJ(API.process + '/api/eval/runs?limit=50'); E.runsError = ''; E.runsRead = true; renderRuns(); }
    catch (e) { E.runs = []; E.runsError = e.message; q('[data-r="runs"]').innerHTML = UI.errorBlock('실행 기록을 읽지 못했습니다', e.message, { retry: true }); }
    renderCmpForm(); renderStats();
  }
  async function load() {
    try { E.patterns = await getJ(API.agent + '/api/ontology/patterns'); E.patternError = ''; } catch (e) { E.patterns = null; E.patternError = '이상 패턴 목록을 읽지 못했습니다: ' + e.message; }
    try { E.knowledge = await getJ(API.process + '/api/eval/knowledge'); E.knowledgeError = ''; } catch (e) { E.knowledge = null; E.knowledgeError = '지식 상태를 읽지 못했습니다: ' + e.message; }
    await Promise.all([loadGolden(), loadRuns()]);
    if (E.sel) selectRun(E.sel); else renderDetail();
    renderCmp();
    if (E.path === 'worker') loadCands();
  }
  function mount(el) {
    if (!el) throw new Error('판단 채점 화면을 그릴 자리가 없습니다');
    if (E.el !== el) { E.el = el; skeleton(); }
    return load();
  }
  window.hydEval = { mount };
})();
