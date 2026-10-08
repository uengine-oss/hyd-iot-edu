/* A10 에이전트 시험 비교 — window.hydCompare.mount(el).
   고정 시나리오(쿨러 · 펌프 · 팬) + 에이전트 A · B → 같은 입력 스냅숏으로 판단 단계만 시험 실행(처리 건 · 설비 명령 없음) → 나란히.
   에이전트 설정은 읽기만 한다(랩업에서 추가한 에이전트 · 스킬이 그대로 목록에 나온다). B 를 '바꿔 보기'는 이번 시험에만 쓰고 저장하지 않는다.
   API: process /api/agent-trials/* (it/process/procsvc/agent_trials.py). 화면 문구 · 컴포넌트는 UI.*(ui.js). */
(function () {
  const TOOL = {
    diagnose: '원인 진단', gather_facts: '판단 사실 수집', evaluate_cards: '후보 · 규정 · 순위 판단', precedents: '과거 선택 조회',
    tradeoffs: '성과 지표 득실 조회', dmn_rules: '판단 규칙 조회', inputs: '판단 입력 · 출처 조회', timeseries_schema: '시계열 구조 조회',
    timeseries_query: '시계열 질의', mes_orders: 'MES 생산오더 조회', erp_contract: 'ERP 계약 조회', erp_inventory: 'ERP 재고 조회',
    cmms_history: 'CMMS 정비 이력 조회', qms_lots: 'QMS 로트 조회', scm_suppliers: 'SCM 공급사 조회', ems_demand: 'EMS 전력 조회',
    read_neo4j_cypher: '지식 그래프 질의', submit_decision: '판단 제출', write_neo4j_cypher: '지식 그래프 쓰기', forecast_actions: '조치 예측',
    query: '업무 DB 자유 질의', describe_schema: '업무 DB 구조 조회', describe_catalog: '업무 DB 목록 조회', get_neo4j_schema: '그래프 구조 조회',
  };
  const SERVER = { 'hyd-dmn': '판단 엔진', enterprise: '업무 DB', neo4j: '지식 그래프', '-': '' };
  const STATUS = { EVALUATED: ['판단 완료', 'success'], WITHHELD: ['근거 부족 · 보류', 'warning'], NO_ENGINE_TOOL: ['판단 도구 없음', 'danger'],
    FAILED: ['실패', 'danger'], NO_FEASIBLE_OPTION: ['가능한 조치 없음', 'danger'], REJECTED_BY_GUARDRAIL: ['안전 규칙으로 중단', 'danger'] };
  const CALL = { DONE: ['완료', 'success'], BLOCKED: ['막힘', 'warning'], FAILED: ['실패', 'danger'] };
  const S = { el: null, opts: null, error: null, busy: false, form: { scenario: 'cooler', a: '', b: '', input: 'new' }, dropTools: [], dropSkills: [],
    result: null, history: null, pick: { a: '', b: '' }, histBusy: false };
  const api = path => API.process + path;
  const toolName = t => TOOL[t] || UI.toolName(t);
  const serverName = s => SERVER[s] ?? s;
  const chip = ([label, tone]) => UI.chipText(label, tone);
  const statusChip = s => chip(STATUS[s] || [s || '–', 'neutral']);
  const agentName = id => (S.opts?.agents || []).find(a => a.id === id)?.name || UI.who(id);
  const nm = id => esc(UI.name(id));
  const ref = r => {
    const s = String(r || '');
    if (s.startsWith('사실:')) return '사실 · ' + esc(UI.idText(s.slice(3)));
    if (s.startsWith('도구:')) { const [server, tool] = s.slice(3).split('/'); return `${esc(toolName(tool))} 결과 <small class="muted">${esc(serverName(server))}</small>`; }
    return nm(s);
  };

  async function load() {
    try { S.opts = await getJ(api('/api/agent-trials/options')); S.error = null; }
    catch (e) { S.error = '시험 설정을 불러오지 못했습니다: ' + e.message; }
    const agents = S.opts?.agents || [];
    if (!S.form.a && agents[0]) S.form.a = agents.find(a => a.id === 'sys:agent')?.id || agents[0].id;
    if (!S.form.b && agents[0]) S.form.b = (agents.find(a => a.id !== S.form.a) || agents[0]).id;
    render();
  }

  function formCard() {
    const o = S.opts;
    if (!o) return S.error ? UI.empty('시험 설정을 불러오지 못했습니다', S.error) : UI.empty(UI.t('loading'));
    if (!o.agents.length) return UI.empty('AI 에이전트가 없습니다', '랩업에서 에이전트를 추가하면(users · is_agent) 여기에 나타납니다.');
    const opt = (list, value, label, cur) => list.map(x => `<option value="${esc(value(x))}" ${value(x) === cur ? 'selected' : ''}>${esc(label(x))}</option>`).join('');
    const b = o.agents.find(a => a.id === S.form.b) || o.agents[0];
    const box = (kind, name, label, off) => `<label class="cmp-check"><input type="checkbox" data-drop="${kind}" value="${esc(name)}" ${off ? '' : 'checked'}> ${label}</label>`;
    const variant = UI.fold(`B를 바꿔 보기 <span class="muted">— 이번 시험에만, 저장하지 않음</span>${S.dropTools.length + S.dropSkills.length ? ` ${UI.chipText(`${S.dropTools.length + S.dropSkills.length}개 뺌`, 'warning')}` : ''}`,
      `<p class="field-hint">체크를 풀면 B에서 그 도구 · 스킬을 빼고 시험합니다. 더하기는 랩업(Claude Code)에서 합니다.</p>
       <div class="cmp-checks"><b>도구</b>${b.tools.length ? b.tools.map(t => box('tool', t, esc(serverName(t) || t), S.dropTools.includes(t))).join('') : '<span class="muted">없음</span>'}</div>
       <div class="cmp-checks"><b>스킬</b>${b.skills.length ? b.skills.map(k => box('skill', k.name, esc(k.description || k.name), S.dropSkills.includes(k.name))).join('') : '<span class="muted">없음</span>'}</div>
       <button type="button" class="btn small" data-act="reset" ${S.dropTools.length + S.dropSkills.length ? '' : 'disabled'}>원래대로</button>`, { open: !!(S.dropTools.length + S.dropSkills.length) });
    const body = `<div class="form-grid">
        ${UI.field({ label: '시나리오', input: `<select data-f="scenario">${opt(o.scenarios, s => s.key, s => s.label, S.form.scenario)}</select>` })}
        ${UI.field({ label: '에이전트 A', input: `<select data-f="a">${opt(o.agents, a => a.id, a => a.name, S.form.a)}</select>` })}
        ${UI.field({ label: '에이전트 B', input: `<select data-f="b">${opt(o.agents, a => a.id, a => a.name, S.form.b)}</select>` })}
        ${UI.field({ label: '입력', input: `<select data-f="input"><option value="new" ${S.form.input === 'new' ? 'selected' : ''}>지금 원천에서 새로 읽어 고정</option><option value="latest" ${S.form.input === 'latest' ? 'selected' : ''}>이 시나리오의 직전 입력 다시 쓰기</option></select>`, hint: '두 에이전트는 항상 같은 입력으로 판단합니다' })}
      </div>${variant}`;
    return UI.card({ title: '시험 조건', chips: UI.chipText('처리 건 · 설비 명령 없음', 'neutral'), body,
      actions: `<button type="button" class="btn primary" data-act="run" ${S.busy ? 'disabled' : ''}>${S.busy ? '시험 중…' : '시험 실행'}</button>` })
      + (S.error && S.opts ? `<p class="form-msg neg" role="alert">${esc(S.error)}</p>` : '');
  }

  // 요약: 지금 무엇을 · 누가 · 결과가 같은가 — 접지 않는다
  function headline(r) {
    const d = r.diff, a = r.a, b = r.b;
    const lines = [];
    lines.push(d.same_input ? `같은 입력(${UI.dateTime(r.snapshot?.created_at || a.created_at)}에 고정)으로 판단했습니다.`
      : '두 실행의 입력이 다릅니다(다른 시각에 고정) — 아래 차이에는 입력 변화가 섞여 있습니다.');
    lines.push(d.same_result ? '두 에이전트의 판단 결과가 같습니다.' : '두 에이전트의 판단 결과가 다릅니다.');
    if (!d.cause.same) lines.push(`원인: A ${nm(d.cause.a) || '없음'} · B ${nm(d.cause.b) || '없음'}`);
    lines.push(d.recommended.same ? `1순위는 같습니다: ${esc(d.recommended.a_sop || '없음')} ${nm(d.recommended.a)}`
      : `1순위가 다릅니다: A ${esc(d.recommended.a_sop || '없음')} ${d.recommended.a ? nm(d.recommended.a) : ''} · B ${esc(d.recommended.b_sop || '없음')} ${d.recommended.b ? nm(d.recommended.b) : ''}`);
    if (!d.order_same) lines.push(`도구 호출 순서가 다릅니다: A에만 ${d.calls_only_a}회 · B에만 ${d.calls_only_b}회`);
    if (d.facts.length) lines.push(`판단 사실 ${d.facts.length}개가 다릅니다(도구 구성에 따라 받지 못한 값 포함).`);
    if (d.citations.only_a.length + d.citations.only_b.length) lines.push(`근거 인용: A에만 ${d.citations.only_a.length}개 · B에만 ${d.citations.only_b.length}개`);
    if (d.rules.only_a.length + d.rules.only_b.length) lines.push(`판단 규칙 차이: A에만 ${d.rules.only_a.length}개 · B에만 ${d.rules.only_b.length}개 (지식이 바뀐 전 · 후)`);
    return UI.card({ title: '비교 요약', chips: chip(d.same_result ? ['결과 같음', 'success'] : ['결과 다름', 'warning']),
      body: `<ul class="cmp-headline">${lines.map(l => `<li>${l}</li>`).join('')}</ul>` });
  }

  function sideCard(label, t) {
    const r = t.result, top = r.diagnosis?.top, rec = r.recommended;
    const v = t.variant || {}, cut = [...(v.without_tools || []).map(serverName), ...(v.without_skills || [])];
    const skills = (r.agent?.skills || []).map(k => `${esc(k.name)} ${k.applied ? UI.chipText(`절차 ${k.steps}개 따름`, 'accent') : UI.chipText('따르지 않음', 'neutral')}${k.reason ? ` <small class="muted">${esc(k.reason)}</small>` : ''}`);
    const body = `<dl class="cmp-dl">
        <div><dt>도구</dt><dd>${(r.agent?.tools || []).map(x => esc(serverName(x))).join(' · ') || '없음'}${cut.length ? ` ${UI.chipText('뺌: ' + cut.join(', '), 'warning')}` : ''}</dd></div>
        <div><dt>스킬</dt><dd>${skills.join('<br>') || '없음'}</dd></div>
        <div><dt>원인</dt><dd>${top ? `<b>${nm(top.id)}</b> <small class="muted">${esc(UI.name(top.failureModeId))}</small>` : esc(r.reason || '없음')}</dd></div>
        <div><dt>1순위</dt><dd>${rec ? `<b>${esc(rec.sopId)} ${nm(rec.id)}</b>` : esc(r.status === 'EVALUATED' ? '없음' : (r.reason || '없음'))}</dd></div>
      </dl>${r.explanation ? `<p class="cmp-why">${esc(UI.idText(r.explanation))}</p>` : ''}`;
    const meta = UI.metaFold([['시험 번호', esc(t.id)], ['입력', esc(t.snapshot_id)], ['결과 지문', `<code>${esc(String(t.fingerprint).slice(0, 12))}</code>`]]);
    return UI.card({ title: `${label} · ${esc(t.setting?.name || agentName(t.agent_id))}`, chips: statusChip(t.status), body: body + meta });
  }

  function callCell(c, n) {
    if (!c) return '<div class="cmp-call cmp-empty">—</div>';
    const st = CALL[c.status] || [c.status, 'neutral'];
    const args = Object.keys(c.args || {}).length ? UI.fold('입력', `<pre>${esc(JSON.stringify(c.args, null, 2))}</pre>`, { cls: 'small' }) : '';
    return `<div class="cmp-call"><header><span class="num">${n}</span><b>${esc(toolName(c.tool))}</b><small class="muted">${esc(serverName(c.server))}${c.by && c.by !== 'engine' ? ' · ' + esc(c.by) : ''}</small>${chip(st)}</header>
      <p>${esc(UI.idText(c.summary || c.reason || ''))}</p>${c.status === 'DONE' && c.reason ? `<p class="muted">${esc(c.reason)}</p>` : ''}${args}</div>`;
  }

  function callTable(r) {
    const A = r.a.result.calls, B = r.b.result.calls;
    const rows = r.diff.calls.map(row => {
      const cls = row.a == null || row.b == null ? 'cmp-only' : row.same ? '' : 'cmp-changed';
      return `<div class="cmp-row ${cls}">${callCell(row.a == null ? null : A[row.a], row.a == null ? '' : row.a + 1)}${callCell(row.b == null ? null : B[row.b], row.b == null ? '' : row.b + 1)}</div>`;
    }).join('');
    return UI.card({ title: '도구 호출 순서', chips: chip(r.diff.order_same ? ['순서 같음', 'success'] : ['순서 다름', 'warning']),
      sub: '한쪽에만 있는 호출은 노란 줄, 같은 호출인데 결과 요약이 다르면 파란 줄입니다.',
      body: `<div class="cmp-row cmp-head"><b>A</b><b>B</b></div>${rows}` });
  }

  function rankTable(d) {
    if (!d.ranking.length) return '';
    const cell = (rank, ok, score) => rank ? `${rank}위${ok === false ? ' ' + UI.chipText('제외', 'danger') : ''} <small class="muted">${score ?? ''}</small>` : '—';
    return UI.card({ title: '조치 순위', body: `<table class="cmp-table"><thead><tr><th>조치</th><th>A</th><th>B</th></tr></thead><tbody>${d.ranking.map(o =>
      `<tr class="${o.rank_a !== o.rank_b || o.feasible_a !== o.feasible_b ? 'cmp-changed' : ''}"><td>${esc(o.sopId || '')} ${nm(o.id)}</td><td>${cell(o.rank_a, o.feasible_a, o.score_a)}</td><td>${cell(o.rank_b, o.feasible_b, o.score_b)}</td></tr>`).join('')}</tbody></table>` });
  }

  function details(r) {
    const d = r.diff;
    const val = (v, blocked) => blocked ? UI.chipText('받지 못함', 'warning') : esc(v == null ? '미확인' : typeof v === 'object' ? JSON.stringify(v) : v);
    const facts = d.facts.length ? `<table class="cmp-table"><thead><tr><th>사실</th><th>A</th><th>B</th></tr></thead><tbody>${d.facts.map(f =>
      `<tr><td>${esc(f.name || f.variable)}</td><td>${val(f.a, f.blocked_a)}</td><td>${val(f.b, f.blocked_b)}</td></tr>`).join('')}</tbody></table>` : UI.empty('판단 사실이 같습니다');
    const list = xs => xs.length ? `<ul>${xs.map(x => `<li>${ref(x)}</li>`).join('')}</ul>` : '<p class="muted">없음</p>';
    const cites = `<div class="cmp-two"><div><b>A에만</b>${list(d.citations.only_a)}</div><div><b>B에만</b>${list(d.citations.only_b)}</div></div><p class="muted">같은 인용 ${d.citations.shared}개</p>`;
    const comp = d.compliance.length ? `<table class="cmp-table"><thead><tr><th>조치</th><th>A 제외 사유</th><th>B 제외 사유</th></tr></thead><tbody>${d.compliance.map(c =>
      `<tr><td>${nm(c.id)}</td><td>${esc(UI.idText((c.a || []).join(' / ') || '없음'))}</td><td>${esc(UI.idText((c.b || []).join(' / ') || '없음'))}</td></tr>`).join('')}</tbody></table>` : UI.empty('규정 판정이 같습니다');
    const rules = d.rules.only_a.length + d.rules.only_b.length ? `<div class="cmp-two"><div><b>A에만 있는 규칙</b>${list(d.rules.only_a)}</div><div><b>B에만 있는 규칙</b>${list(d.rules.only_b)}</div></div>` : '';
    return UI.fold(`판단 사실 차이 <span class="chip tone-neutral sm">${d.facts.length}</span>`, facts, { open: d.facts.length > 0 })
      + UI.fold(`근거 인용 차이 <span class="chip tone-neutral sm">${d.citations.only_a.length + d.citations.only_b.length}</span>`, cites)
      + UI.fold(`규정 판정 차이 <span class="chip tone-neutral sm">${d.compliance.length}</span>`, comp + rules)
      + UI.fold('원본 기록', `<pre>${esc(JSON.stringify({ a: r.a.result, b: r.b.result }, null, 2))}</pre>`, { cls: 'small' });
  }

  function resultView(r) {
    if (!r) return '';
    if (!r.b) return `<div class="cmp-grid">${sideCard('A', r.a)}</div>`;
    return headline(r) + `<div class="cmp-grid">${sideCard('A', r.a)}${sideCard('B', r.b)}</div>` + callTable(r) + rankTable(r.diff) + details(r);
  }

  function historyCard() {
    const h = S.history;
    const rows = h == null ? '' : h.length < 2 ? UI.empty('저장된 시험이 둘 이상 있어야 비교할 수 있습니다') : `<div class="form-grid">${['a', 'b'].map(side =>
      UI.field({ label: side === 'a' ? '전' : '후', input: `<select data-pick="${side}"><option value="">고르기</option>${h.map(t =>
        `<option value="${esc(t.id)}" ${S.pick[side] === t.id ? 'selected' : ''}>${esc(UI.dateTime(t.created_at))} · ${esc(t.agent_name || agentName(t.agent_id))} · ${esc(t.recommended || STATUS[t.status]?.[0] || t.status)}${(t.variant?.without_tools || []).length + (t.variant?.without_skills || []).length ? ' · 변형' : ''}</option>`).join('')}</select>` })).join('')}</div>`;
    return UI.fold('지난 시험과 비교 (전 · 후) <span class="muted">— 규칙 · 지식을 바꾸기 전과 후, 기존 쿨러 결과가 그대로인지</span>',
      rows + `<div class="form-actions"><button type="button" class="btn" data-act="${h == null ? 'history' : 'diff'}" ${S.histBusy || (h && (!S.pick.a || !S.pick.b)) ? 'disabled' : ''}>${h == null ? '저장된 시험 불러오기' : '두 실행 비교'}</button></div>`);
  }

  function render() {
    if (!S.el) return;
    const open = [...S.el.querySelectorAll('details')].map(d => d.open);
    S.el.innerHTML = `<div class="cmp">${formCard()}${historyCard()}<div class="cmp-result" aria-live="polite">${S.busy ? UI.empty('시험 실행 중…', '원천을 읽고 판단 단계만 돌립니다. 제출 · 명령은 하지 않습니다.') : resultView(S.result)}</div></div>`;
    S.el.querySelectorAll('details').forEach((d, i) => { if (open[i] != null && i < 2) d.open = open[i]; });
  }

  async function runTrial() {
    S.busy = true; S.error = null; render();
    try {
      S.result = await postJ(api('/api/agent-trials/run'), { scenario: S.form.scenario, reuse_latest: S.form.input === 'latest',
        a: { agent: S.form.a }, b: { agent: S.form.b, variant: { without_tools: S.dropTools, without_skills: S.dropSkills } } });
      S.history = null;
    } catch (e) { S.error = '시험 실행 실패: ' + e.message; S.result = null; }
    S.busy = false; render();
  }

  async function loadHistory() {
    S.histBusy = true; render();
    try { S.history = await getJ(api('/api/agent-trials?limit=40')); } catch (e) { S.error = '저장된 시험을 불러오지 못했습니다: ' + e.message; }
    S.histBusy = false; render();
  }

  async function diffStored() {
    S.histBusy = true; render();
    try { const r = await getJ(api(`/api/agent-trials/diff?a=${encodeURIComponent(S.pick.a)}&b=${encodeURIComponent(S.pick.b)}`)); S.result = { ...r, snapshot: null }; }
    catch (e) { S.error = '비교 실패: ' + e.message; }
    S.histBusy = false; render();
  }

  function bind(el) {
    el.addEventListener('change', e => {
      const t = e.target;
      if (t.dataset.f) { S.form[t.dataset.f] = t.value; if (t.dataset.f === 'b') { S.dropTools = []; S.dropSkills = []; } render(); }
      else if (t.dataset.drop) {
        const list = t.dataset.drop === 'tool' ? S.dropTools : S.dropSkills;
        const i = list.indexOf(t.value);
        if (!t.checked && i < 0) list.push(t.value); else if (t.checked && i >= 0) list.splice(i, 1);
        render();
      } else if (t.dataset.pick) { S.pick[t.dataset.pick] = t.value; render(); }
    });
    el.addEventListener('click', e => {
      const act = e.target.closest('[data-act]')?.dataset.act;
      if (act === 'run') runTrial();
      else if (act === 'reset') { S.dropTools = []; S.dropSkills = []; render(); }
      else if (act === 'history') loadHistory();
      else if (act === 'diff') diffStored();
    });
  }

  window.hydCompare = {
    mount(el) {
      if (!el) return;
      if (S.el !== el) { S.el = el; bind(el); }
      render();
      load();
    },
  };

  // 셸이 mount 를 부르기 전(지금의 탭 방식): 화면이 처음 보일 때 한 번 그린다
  const host = document.getElementById('compareView');
  const nav = document.querySelector('.rail nav button[data-tab="compare"]');
  if (host && nav) nav.addEventListener('click', () => { if (S.el !== host) window.hydCompare.mount(host); });
})();
