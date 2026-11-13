/* A10 에이전트 시험 비교 — window.hydCompare.mount(el).
   고정 시나리오(쿨러 · 펌프 · 팬) + 에이전트 A · B → 같은 입력 스냅숏으로 판단 단계만 시험 실행(처리 건 · 설비 명령 없음) → 나란히.
   에이전트 설정은 읽기만 한다(「에이전트 · 스킬」 화면에서 만든 에이전트 · 스킬이 그대로 목록에 나온다). B 를 '바꿔 보기'는 이번 시험에만 쓰고 저장하지 않는다.
   짜임(디자인 기준 5-8 「입력 → 결과」): 왼쪽에 시험 조건과 [시험 실행], 오른쪽에 결과(결론 문장 → A · B 나란히 → 도구 호출 순서 → 조치 순위 → 다른 점 → 「자세히」 원본 기록),
   그 아래에 지난 시험과 비교. 칩은 상태 낱말에만 쓴다(끝난 호출에는 칩을 붙이지 않는다). 호출 한 건의 원문은 맨 아래 「원본 기록」 한 곳에 있다.
   도구 이름은 이름 사전 하나(plainWords.js hydWords.toolName). API: process /api/agent-trials/* (it/process/procsvc/agent_trials.py). */
(function () {
  const STATUS = { EVALUATED: ['판단 완료', 'success'], WITHHELD: ['근거 부족으로 보류', 'warning'], NO_ENGINE_TOOL: ['판단 도구 없음', 'danger'],
    FAILED: ['실패', 'danger'], NO_FEASIBLE_OPTION: ['가능한 조치 없음', 'danger'], REJECTED_BY_GUARDRAIL: ['안전 규칙으로 중단', 'danger'] };
  const CALL = { DONE: ['완료', 'success'], BLOCKED: ['차단됨', 'warning'], FAILED: ['실패', 'danger'] };
  const S = { el: null, opts: null, error: null, busy: false, form: { scenario: '', a: '', b: '', input: 'new' }, dropTools: [], dropSkills: [],
    result: null, history: null, pick: { a: '', b: '' }, histBusy: false, histError: null, loadError: null };
  const api = path => API.process + path;
  const toolName = (t, server) => hydWords.toolName(server && server !== '-' ? `mcp__${server}__${t}` : t);
  const serverName = s => s === '-' ? '' : hydWords.serverName(s);   // 도구 서버 이름표는 plainWords.js 하나
  const chip = ([label, tone]) => UI.chipText(label, tone);
  const statusChip = s => chip(STATUS[s] || [s || '–', 'neutral']);
  const agentName = id => (S.opts?.agents || []).find(a => a.id === id)?.name || UI.who(id);
  const nm = id => esc(UI.name(id));
  const group = (label, body) => body ? `<section class="rd-group"><h3 class="rd-label">${label}</h3>${body}</section>` : '';
  const kv = rows => { const r = rows.filter(([, x]) => x != null && x !== ''); return r.length ? `<dl class="kv">${r.map(([k, x]) => `<dt>${esc(k)}</dt><dd>${x}</dd>`).join('')}</dl>` : ''; };
  const ref = r => {
    const s = String(r || '');
    if (s.startsWith('사실:')) return '사실 · ' + esc(UI.idText(s.slice(3)));
    if (s.startsWith('도구:')) { const [server, tool] = s.slice(3).split('/'); return `${esc(toolName(tool,server))} 결과 <small class="muted">${esc(serverName(server))}</small>`; }
    return nm(s);
  };

  async function load() {
    try { S.opts = await getJ(api('/api/agent-trials/options')); S.error = null; S.loadError = null; }
    catch (e) { S.loadError = e.message; }
    const agents = S.opts?.agents || [];
    if (!S.form.a && agents[0]) S.form.a = agents.find(a => a.id === 'sys:agent')?.id || agents[0].id;
    if (!S.form.b && agents[0]) S.form.b = (agents.find(a => a.id !== S.form.a) || agents[0]).id;
    render();
  }

  // 왼쪽: 시험 조건 → [시험 실행] → B 를 바꿔 보기(이번 시험에만)
  function formPane() {
    const o = S.opts;
    if (!o) return S.loadError ? UI.errorBlock('시험 설정을 불러오지 못했습니다', S.loadError, { retry: true, cls: 'compact' }) : UI.loading('', 'compact');
    if (!o.agents.length) return UI.emptyGo('AI 에이전트가 없습니다', '「에이전트 · 스킬」 화면에서 만들거나 코딩 랩에서 추가하면 여기에 나타납니다.', 'agents', '에이전트 · 스킬 열기', 'compact');
    const opt = (list, value, label, cur) => list.map(x => `<option value="${esc(value(x))}" ${value(x) === cur ? 'selected' : ''}>${esc(label(x))}</option>`).join('');
    const b = o.agents.find(a => a.id === S.form.b) || o.agents[0];
    const note = id => (o.agents.find(a => a.id === id) || {}).trial_note || '';   // 시험 시나리오로 그 에이전트의 일을 재지 못하는 까닭(서버가 정함)
    const box = (kind, name, label, off) => `<label class="check"><input type="checkbox" data-drop="${kind}" value="${esc(name)}" ${off ? '' : 'checked'}> <span>${label}</span></label>`;
    const dropped = S.dropTools.length + S.dropSkills.length;
    return `<h2 class="rd-label">시험 조건</h2>
        ${UI.field({ label: '시나리오', input: `<select data-f="scenario"><option value="">시나리오 선택</option>${opt(o.scenarios, s => s.key, s => s.label, S.form.scenario)}</select>`, required: true })}
        ${UI.field({ label: '에이전트 A', input: `<select data-f="a">${opt(o.agents, a => a.id, a => a.name, S.form.a)}</select>`, hint: note(S.form.a) })}
        ${UI.field({ label: '에이전트 B', input: `<select data-f="b">${opt(o.agents, a => a.id, a => a.name, S.form.b)}</select>`, hint: note(S.form.b) })}
        ${UI.field({ label: '입력', input: `<select data-f="input"><option value="new" ${S.form.input === 'new' ? 'selected' : ''}>지금 원천에서 새로 읽어 고정</option><option value="latest" ${S.form.input === 'latest' ? 'selected' : ''}>이 시나리오의 직전 입력 다시 쓰기</option></select>`, hint: '두 에이전트는 항상 같은 입력으로 판단합니다' })}
        ${S.error ? `<p class="field-error" role="alert">${esc(S.error)}</p>` : ''}
        ${S.loadError ? `<p class="field-error" role="alert">시험 설정을 다시 읽지 못해 앞서 읽은 목록을 보이고 있습니다: ${esc(S.loadError)}</p>` : ''}
        <div class="rd-in-actions"><button type="button" class="btn primary" data-act="run" ${S.busy ? 'disabled' : ''}>${S.busy ? '시험 중…' : '시험 실행'}</button></div>
        <p class="rd-in-note">이 시험은 AI 모델을 부르지 않습니다. 스킬 글과 판단 규칙으로 판단 단계만 모의하며, 처리 건과 설비 명령을 만들지 않습니다.</p>
        <hr class="rd-rule"><h2 class="rd-label">B를 바꿔 보기${dropped ? ` · ${dropped}개 뺌` : ''}</h2>
        <p class="rd-in-note">체크를 풀면 B에서 그 도구나 스킬을 빼고 시험합니다. 이번 시험에만 쓰고 저장하지 않습니다. 더하려면 그 에이전트를 고칩니다. <button type="button" class="link-btn" data-go-tab="agents">에이전트 · 스킬 열기 →</button></p>
        <div class="rd-checks"><b class="rd-label">도구</b>${b.tools.length ? b.tools.map(t => box('tool', t, esc(serverName(t) || t), S.dropTools.includes(t))).join('') : '<span class="rd-in-note">없음</span>'}</div>
        <div class="rd-checks"><b class="rd-label">스킬</b>${b.skills.length ? b.skills.map(k => box('skill', k.name, esc(k.description || k.name), S.dropSkills.includes(k.name))).join('') : '<span class="rd-in-note">없음</span>'}</div>
        <div class="rd-in-actions"><button type="button" class="btn small" data-act="reset" ${dropped ? '' : 'disabled'}>원래대로</button></div>`;
  }

  // 결론: 결과가 같은가 한 문장(16px) → 무엇이 다른가 한 줄씩. 접지 않는다
  function headline(r) {
    const d = r.diff, a = r.a;
    const lines = [];
    lines.push(d.same_input ? `같은 입력(${UI.dateTime(r.snapshot?.created_at || a.created_at)}에 고정)으로 판단했습니다.`
      : '두 실행의 입력이 다릅니다(서로 다른 시각에 고정했습니다). 아래 차이에는 입력 변화가 섞여 있습니다.');
    if (!d.cause.same) lines.push(`원인: A ${nm(d.cause.a) || '없음'} · B ${nm(d.cause.b) || '없음'}`);
    lines.push(d.recommended.same ? `1순위는 같습니다: ${esc(d.recommended.a_sop || '없음')} ${nm(d.recommended.a)}`
      : `1순위가 다릅니다: A ${esc(d.recommended.a_sop || '없음')} ${d.recommended.a ? nm(d.recommended.a) : ''} · B ${esc(d.recommended.b_sop || '없음')} ${d.recommended.b ? nm(d.recommended.b) : ''}`);
    if (!d.order_same) lines.push(`도구 호출 순서가 다릅니다: A에만 ${d.calls_only_a}회 · B에만 ${d.calls_only_b}회`);
    if (d.facts.length) lines.push(`판단 사실 ${d.facts.length}개가 다릅니다(도구 구성에 따라 받지 못한 값 포함).`);
    if (d.citations.only_a.length + d.citations.only_b.length) lines.push(`근거 인용: A에만 ${d.citations.only_a.length}개 · B에만 ${d.citations.only_b.length}개`);
    if (d.rules.only_a.length + d.rules.only_b.length) lines.push(`판단 규칙 차이: A에만 ${d.rules.only_a.length}개 · B에만 ${d.rules.only_b.length}개 (지식을 바꾸기 전과 후에 시험한 경우)`);
    return `<h2 class="rd-conclusion rd-state ${d.same_result ? 'ok' : 'warn'}">${d.same_result ? '두 에이전트의 판단 결과가 같습니다.' : '두 에이전트의 판단 결과가 다릅니다.'}</h2>` +
      `<ul class="cmp-headline">${lines.map(l => `<li>${l}</li>`).join('')}</ul>`;
  }

  // 한쪽의 판단: 이름 + 상태 칩 하나 → 원인 · 1순위 → 쓴 도구 · 스킬 → 설명. 시험 번호 · 결과 지문은 「자세히」 안에
  function sideCard(label, t) {
    const r = t.result, top = r.diagnosis?.top, rec = r.recommended;
    const v = t.variant || {}, cut = [...(v.without_tools || []).map(serverName), ...(v.without_skills || [])];
    const skills = (r.agent?.skills || []).map(k => `${esc(k.name)} <small class="muted">${k.applied ? `절차 ${k.steps}개 따름` : '따르지 않음'}${k.reason ? ' — ' + esc(k.reason) : ''}</small>`);
    return `<section class="card cmp-side"><header class="rd-head"><div class="rd-title"><h3>${label} · ${esc(t.setting?.name || agentName(t.agent_id))}</h3>${statusChip(t.status)}</div></header>` +
      kv([['원인', top ? `<b>${nm(top.id)}</b> <small class="muted">${esc(UI.name(top.failureModeId))}</small>` : esc(r.reason || '없음')],
        ['1순위', rec ? `<b>${esc(rec.sopId)} ${nm(rec.id)}</b>` : esc(!top || r.status === 'EVALUATED' ? '없음' : (r.reason || '없음'))],      // 원인을 못 가린 까닭은 원인 줄에 한 번만 쓴다
        ['도구', ((r.agent?.tools || []).map(x => esc(serverName(x))).join(' · ') || '없음') + (cut.length ? ` <small class="muted">(이번 시험에서 뺀 것: ${esc(cut.join(', '))})</small>` : '')],
        ['스킬', skills.join('<br>') || '없음']]) +
      (r.explanation ? `<p class="cmp-why">${esc(UI.idText(r.explanation))}</p>` : '') +
      UI.fold('자세히 · 시험 번호 · 결과 지문', kv([['시험 번호', esc(t.id)], ['입력', esc(t.snapshot_id)], ['결과 지문', `<code>${esc(String(t.fingerprint).slice(0, 12))}</code>`]]) + UI.evaluationHtml(r, undefined, { raw: false }), { cls: 'small' }) +
      `</section>`;
  }

  // mark: 이 줄이 어떻게 다른지(「A에만」 · 「B에만」 · 「결과 다름」) — 줄 색과 함께 글로도 보인다
  function callCell(c, n, mark = '') {
    if (!c) return '<div class="cmp-call cmp-empty">—</div>';
    const diff = mark ? `<small class="rd-mark">${esc(mark)}</small>` : '';
    const st = c.status === 'DONE' ? '' : chip(CALL[c.status] || ['호출 상태 기록 확인 필요', 'neutral']);      // 끝난 호출에는 칩을 붙이지 않는다
    const purchase=window.hydWords?.purchaseTool(c.tool);
    if (purchase && (c.server==='hyd-dmn' || UI.toolKey(c.tool).startsWith('mcp__hyd-dmn__'))) {
      const words=window.hydWords, output=c.output ?? c.result ?? c.value;
      const purchaseError=output!=null && words.purchaseFailed(output);
      const result=output!=null ? words.purchaseGot(purchase,output) : '호출 완료 · 상세 결과 값 기록 없음';
      const reason=String(c.reason || '').replace(/\b(?:purchase_context|evaluate_purchase|submit_purchase)\b/g,key=>toolName(key,'hyd-dmn')).replaceAll('hyd-dmn',serverName('hyd-dmn'));
      const why=reason && /[가-힣]/.test(reason) && !/[A-Za-z]+_[A-Za-z_]+/.test(reason) ? ' · '+words.text(reason) : '';
      const state=c.status==='BLOCKED' ? '구매 도구 요청이 차단됐습니다.'+ (why || ' 차단 사유는 아래 원본 기록에 있습니다.') : c.status==='FAILED' ? '구매 도구 호출에 실패했습니다.'+ (why || ' 사유는 아래 원본 기록에 있습니다.') : result;
      return `<div class="cmp-call"><header><span class="num">${n}</span><b>${esc(toolName(purchase,'hyd-dmn'))}</b><small class="muted">${esc(serverName('hyd-dmn'))}</small>${purchaseError ? chip(['구매 요청 처리 실패','danger']) : st}${diff}</header><p>${esc(words.purchaseAsk(purchase,c.args))}</p><p>${esc(state)}</p></div>`;
    }
    const args = Object.keys(c.args || {}).length ? `<p class="muted cmp-args">입력 <code>${esc(JSON.stringify(c.args))}</code></p>` : '';
    return `<div class="cmp-call"><header><span class="num">${n}</span><b>${esc(toolName(c.tool,c.server))}</b><small class="muted">${esc(serverName(c.server))}${c.by && c.by !== 'engine' ? ' · ' + esc(c.by) : ''}</small>${st}${diff}</header>
      <p>${esc(UI.idText(c.summary || c.reason || ''))}</p>${c.status === 'DONE' && c.reason ? `<p class="muted">${esc(c.reason)}</p>` : ''}${args}</div>`;
  }

  function callTable(r) {
    const A = r.a.result.calls, B = r.b.result.calls;
    const rows = r.diff.calls.map(row => {
      const cls = row.a == null || row.b == null ? 'cmp-only' : row.same ? '' : 'cmp-changed';
      const changed = cls === 'cmp-changed' ? '결과 다름' : '';
      return `<div class="cmp-row ${cls}">${callCell(row.a == null ? null : A[row.a], row.a == null ? '' : row.a + 1, row.b == null ? 'A에만' : changed)}${callCell(row.b == null ? null : B[row.b], row.b == null ? '' : row.b + 1, row.a == null ? 'B에만' : changed)}</div>`;
    }).join('');
    return `<section class="rd-group"><h2 class="rd-sec">도구 호출 순서</h2>` +
      `<p class="rd-note">${r.diff.order_same ? '두 에이전트가 같은 순서로 도구를 불렀습니다.' : '두 에이전트의 호출 순서가 다릅니다.'} 한쪽에만 있는 호출에는 「A에만」이나 「B에만」이, 같은 호출인데 결과 요약이 다르면 「결과 다름」이 붙습니다.</p>` +
      `<div class="cmp-row cmp-head"><b>A</b><b>B</b></div>${rows}</section>`;
  }

  function rankTable(d) {
    if (!d.ranking.length) return '';
    const cell = (rank, ok, score) => rank ? `${rank}위${ok === false ? ' ' + UI.chipText('제외', 'danger') : ''} <span class="muted">${score ?? ''}</span>` : '—';
    return `<section class="rd-group"><h2 class="rd-sec">조치 순위</h2><div class="rd-scroll"><table class="tbl"><thead><tr><th>조치</th><th>A</th><th>B</th></tr></thead><tbody>${d.ranking.map(o =>
      `<tr class="${o.rank_a !== o.rank_b || o.feasible_a !== o.feasible_b ? 'cmp-changed' : ''}"><td>${esc(o.sopId || '')} ${nm(o.id)}</td><td>${cell(o.rank_a, o.feasible_a, o.score_a)}</td><td>${cell(o.rank_b, o.feasible_b, o.score_b)}</td></tr>`).join('')}</tbody></table></div></section>`;
  }

  // 다른 점: 다른 것만 표로 펼치고, 같은 것은 한 줄로 말한다. 원본 기록(JSON)만 「자세히」 접기 안에 둔다
  function details(r) {
    const d = r.diff;
    const val = (f, v, blocked) => blocked ? UI.chipText('받지 못함', 'warning') : esc(v == null ? '미확인' : hydWords.value(f.variable, v));
    const facts = d.facts.length ? `<div class="rd-scroll"><table class="tbl"><thead><tr><th>사실</th><th>A</th><th>B</th></tr></thead><tbody>${d.facts.map(f =>
      `<tr><td>${esc(f.name || f.variable)}</td><td>${val(f, f.a, f.blocked_a)}</td><td>${val(f, f.b, f.blocked_b)}</td></tr>`).join('')}</tbody></table></div>` : '<p class="rd-note">판단 사실이 같습니다.</p>';
    const list = xs => xs.length ? `<ul>${xs.map(x => `<li>${ref(x)}</li>`).join('')}</ul>` : '<p class="rd-note">없음</p>';
    const citeDiff = d.citations.only_a.length + d.citations.only_b.length;
    const cites = (citeDiff ? `<div class="cmp-two"><div><b>A에만</b>${list(d.citations.only_a)}</div><div><b>B에만</b>${list(d.citations.only_b)}</div></div>` : '') +
      `<p class="rd-note">${citeDiff ? '' : '두 에이전트가 인용한 근거가 같습니다. '}같은 인용 ${d.citations.shared}개</p>`;
    const comp = d.compliance.length ? `<div class="rd-scroll"><table class="tbl"><thead><tr><th>조치</th><th>A 제외 사유</th><th>B 제외 사유</th></tr></thead><tbody>${d.compliance.map(c =>
      `<tr><td>${nm(c.id)}</td><td>${esc(UI.idText((c.a || []).join(' / ') || '없음'))}</td><td>${esc(UI.idText((c.b || []).join(' / ') || '없음'))}</td></tr>`).join('')}</tbody></table></div>` : '<p class="rd-note">규정 판정이 같습니다.</p>';
    const rules = d.rules.only_a.length + d.rules.only_b.length ? `<div class="cmp-two"><div><b>A에만 있는 규칙</b>${list(d.rules.only_a)}</div><div><b>B에만 있는 규칙</b>${list(d.rules.only_b)}</div></div>` : '';
    return `<section class="rd-group"><h2 class="rd-sec">다른 점</h2>` + group(`판단 사실 차이 ${d.facts.length}개`, facts) + group(`근거 인용 차이 ${citeDiff}개`, cites) +
      group(`규정 판정 차이 ${d.compliance.length}개`, comp + rules) + `</section>` +
      `<div class="rd-group">${UI.fold('자세히 · 원본 기록 (호출 입력과 결과의 원문)', `<pre>${esc(JSON.stringify({ a: r.a.result, b: r.b.result }, null, 2))}</pre>`, { cls: 'small' })}</div>`;
  }

  function resultView(r) {
    if (!r) return UI.empty('아직 시험한 결과가 없습니다', '왼쪽에서 시나리오와 에이전트 둘을 고르고 [시험 실행]을 누르면, 같은 입력으로 판단한 결과가 나란히 보입니다.', 'compact');
    if (!r.b) return `<div class="cmp-grid">${sideCard('A', r.a)}</div>`;
    return headline(r) + `<div class="cmp-grid rd-group">${sideCard('A', r.a)}${sideCard('B', r.b)}</div>` + callTable(r) + rankTable(r.diff) + details(r);
  }

  // 지난 시험과 비교: 결과 아래에 둔다(기준 5-8 「지난 실행」)
  function historyPane() {
    const h = S.history;
    const rows = h == null ? '' : h.length < 2 ? UI.empty('저장된 시험이 둘 이상 있어야 비교할 수 있습니다', '위에서 시험을 한 번 더 실행하면 비교할 수 있습니다.', 'compact') : `<div class="form-grid">${['a', 'b'].map(side =>
      UI.field({ label: side === 'a' ? '바꾸기 전 시험' : '바꾼 뒤 시험', input: `<select data-pick="${side}"><option value="">시험 선택</option>${h.map(t =>
        `<option value="${esc(t.id)}" ${S.pick[side] === t.id ? 'selected' : ''}>${esc(UI.dateTime(t.created_at))} · ${esc(t.agent_name || agentName(t.agent_id))} · ${esc(t.recommended || STATUS[t.status]?.[0] || t.status)}${(t.variant?.without_tools || []).length + (t.variant?.without_skills || []).length ? ' · 변형' : ''}</option>`).join('')}</select>` })).join('')}</div>`;
    return `<section class="rd-group rd-history"><h2 class="rd-sec">지난 시험과 비교</h2><p class="rd-note">규칙이나 지식을 바꾸기 전과 후에 결과가 그대로인지 봅니다.</p>` +
      rows + (S.histError ? `<p class="field-error" role="alert">${esc(S.histError)}</p>` : '') +
      `<div class="rd-in-actions"><button type="button" class="btn" data-act="${h == null ? 'history' : 'diff'}" ${S.histBusy || (h && (!S.pick.a || !S.pick.b)) ? 'disabled' : ''}>${h == null ? '저장된 시험 불러오기' : '두 실행 비교'}</button></div></section>`;
  }

  function render() {
    if (!S.el) return;
    const open = new Set([...S.el.querySelectorAll('details[open] > summary')].map(x => x.textContent.trim()));      // 다시 그려도 펼친 「자세히」는 그대로 둔다
    S.el.innerHTML = `<p class="page-lead">같은 입력으로 에이전트 둘의 판단 단계를 모의해, 원인과 1순위 조치, 도구 호출이 어떻게 다른지 나란히 봅니다.</p>` +
      `<div class="cmp rd-io"><div class="rd-in">${formPane()}</div><div class="rd-out"><div class="cmp-result" aria-live="polite">${S.busy
        ? UI.loading('시험 실행 중 — 원천을 읽고 판단 단계만 모의합니다', 'compact') : resultView(S.result)}</div>${S.opts && S.opts.agents.length ? historyPane() : ''}</div></div>`;
    S.el.querySelectorAll('details > summary').forEach(x => { if (open.has(x.textContent.trim())) x.parentElement.open = true; });
  }

  async function runTrial() {
    if (!S.form.scenario) { S.error = '시나리오를 고르세요.'; render(); return; }      // 고르지 않은 시나리오로 시험하지 않는다
    S.busy = true; S.error = null; render();
    try {
      S.result = await postJ(api('/api/agent-trials/run'), { scenario: S.form.scenario, reuse_latest: S.form.input === 'latest',
        a: { agent: S.form.a }, b: { agent: S.form.b, variant: { without_tools: S.dropTools, without_skills: S.dropSkills } } });
      S.history = null;
    } catch (e) { S.error = '시험을 실행하지 못했습니다: ' + e.message; S.result = null; }
    S.busy = false; render();
  }

  async function loadHistory() {
    S.histBusy = true; S.histError = null; render();
    try { S.history = await getJ(api('/api/agent-trials?limit=40')); } catch (e) { S.histError = '저장된 시험을 불러오지 못했습니다: ' + e.message; }
    S.histBusy = false; render();
  }

  async function diffStored() {
    S.histBusy = true; S.histError = null; render();
    try { const r = await getJ(api(`/api/agent-trials/diff?a=${encodeURIComponent(S.pick.a)}&b=${encodeURIComponent(S.pick.b)}`)); S.result = { ...r, snapshot: null }; }
    catch (e) { S.histError = '두 시험을 비교하지 못했습니다: ' + e.message; }
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
      if (e.target.closest('[data-retry]')) { load(); return; }
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

})();
