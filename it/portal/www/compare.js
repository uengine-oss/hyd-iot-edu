/* A10 에이전트 시험 비교 — window.hydCompare.mount(el).
   이 시험이 재는 것(서버 it/agent/agentsvc/trial.py · it/process/procsvc/agent_trials.py 의 실제 동작):
     AI 모델을 돌리지 않는다. 에이전트의 「구성」(쓸 수 있는 도구 서버, 붙인 스킬 문서)을 같은 입력 스냅숏에 대어 판단 단계를 계산한다 —
     ① 판단 도구 서버가 구성에 없으면 진단 · 판단을 못 하고, 업무 도구 서버가 없으면 업무 값을 받지 못해 그 값을 읽는 규칙이 「미확인」으로 계산된다.
     ② 스킬 문서는 뜻을 읽는 것이 아니라 문서에 적힌 도구 이름을 등장 순서대로 찾아 보조 조회로 부른다(다른 설비 · 이상 패턴만 가리키는 문서는 따르지 않는다).
     그래서 같은 입력 + 같은 구성이면 결과가 늘 같고, 두 결과의 차이는 구성의 차이에서만 나온다. 실제 AI 에이전트의 판단(처리 건)은 이 화면이 재지 않는다 — 그것은 판단 채점의 「지난 처리 건」 경로가 잰다.
   화면은 이 사실을 머리 문장 · 조건 판 · 결론 줄에서 그대로 말한다(「AI를 돌려 시험했다」고 읽히는 말을 쓰지 않는다).
   결론은 두 구성이 같은 원인 · 같은 1순위 조치에 이르렀는가, 한쪽만 판단에 이르지 못했는가, 둘 다 판단을 보류했는가로 말한다(verdict). 서버의 same_result(호출 기록 지문)는 결론에 쓰지 않는다.
   판단 보류(그 설비에 지금 이상 값이 없음)는 실패가 아니라 정상 결과이고, 시나리오가 다른 시험 둘은 견주지 않는다.
   에이전트 설정은 읽기만 한다(「에이전트 · 스킬」 화면에서 만든 에이전트 · 스킬이 그대로 목록에 나온다). B 에서 '빼 보기'는 이번 시험에만 쓰고 저장하지 않는다.
   짜임(디자인 기준 5-6 「조건 → 결과」): 왼쪽 조건 판과 [시험 실행], 오른쪽에 실시간 상자(도는 동안 — 서버가 적는 단계가 하나씩) → 결과 판(결론 한 줄과 숫자 넷 → 무엇이 다른가 →
   A · B 나란히 → 도구 호출 순서 → 조치 순위 → 다른 점과 원본 기록 접기) → 지난 시험과 비교. 부품은 키트의 것이고 격자는 reading.css(.io · .io-two)다.
   도구 이름은 이름 사전 하나(plainWords.js hydWords.toolName). API: process /api/agent-trials/*. */
(function () {
  const STATUS = { EVALUATED: ['계산 완료', 'neutral'], WITHHELD: ['근거 부족으로 보류', 'warning'], NO_ENGINE_TOOL: ['판단 도구 없음', 'danger'],
    FAILED: ['실패', 'danger'], NO_FEASIBLE_OPTION: ['가능한 조치 없음', 'danger'], REJECTED_BY_GUARDRAIL: ['안전 규칙으로 중단', 'danger'] };
  const CALL = { DONE: ['완료', 'success'], BLOCKED: ['부르지 못함', 'warning'], FAILED: ['실패', 'danger'] };
  const S = { el: null, opts: null, error: null, busy: false, form: { scenario: '', a: '', b: '', input: 'new' }, dropTools: [], dropSkills: [],
    result: null, history: null, pick: { a: '', b: '' }, histBusy: false, histError: null, loadError: null };
  const api = path => API.process + path;
  // 스킬 문서가 가리켰지만 시험이 부르지 않은 도구는 서버 칸이 비어 온다('-') — 이름 사전의 서버들에서 찾고, 없으면 문서에 적힌 이름 그대로 보인다
  const toolName = (t, server) => {
    if (server && server !== '-') return hydWords.toolName(`mcp__${server}__${t}`);
    for (const s of ['hyd-dmn', 'enterprise', 'neo4j']) { const n = hydWords.toolName(`mcp__${s}__${t}`); if (!String(n).startsWith('도구 표시 이름')) return n; }
    return t;
  };
  const serverName = s => s === '-' ? '' : hydWords.serverName(s);   // 도구 서버 이름표는 plainWords.js 하나
  const chip = ([label, tone]) => UI.chipText(label, tone);
  const statusChip = s => chip(STATUS[s] || [s || '–', 'neutral']);
  const agentName = id => (S.opts?.agents || []).find(a => a.id === id)?.name || UI.who(id);
  const nm = id => esc(UI.name(id));
  const sec = (title, side, body) => body ? `<div class="panel-sec"><h3>${title}${side ? `<span class="muted">${side}</span>` : ''}</h3>${body}</div>` : '';
  const fact = (label, value) => `<div><dt>${esc(label)}</dt><dd>${value}</dd></div>`;
  const note = (text, attrs = '') => text ? `<p class="muted"${attrs}>${text}</p>` : '';
  const kv = rows => { const r = rows.filter(([, x]) => x != null && x !== ''); return r.length ? `<dl class="kv">${r.map(([k, x]) => `<dt>${esc(k)}</dt><dd>${x}</dd>`).join('')}</dl>` : ''; };
  const table = (head, rows) => `<div class="table-container"><table class="table"><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table></div>`;
  const badge = text => `<span class="badge" data-variant="secondary">${esc(text)}</span>`;
  const ref = r => {
    const s = String(r || '');
    if (s.startsWith('사실:')) return '사실 · ' + esc(UI.idText(s.slice(3)));
    if (s.startsWith('도구:')) { const [server, tool] = s.slice(3).split('/'); return `${esc(toolName(tool, server))} 결과 <span class="muted">${esc(serverName(server))}</span>`; }
    return nm(s);
  };
  // 이 시험이 무엇을 재는지 — 조건 판 아래와 결과의 결론 줄 아래에 같은 말로 적는다
  // 이 시험이 하는 일의 범위 한 줄(폼 아래). 「AI 모델은 돌리지 않습니다」는 화면 머리가 한 번 말한다
  const WHAT = '스킬 문서는 뜻을 읽지 않습니다. 문서에 적힌 도구 이름만 찾아 적힌 차례대로 부르고, 나머지 절차 글은 계산에 쓰지 않습니다. 처리 건과 설비 명령은 만들지 않습니다.';
  // 이 시험의 범위와, 판단을 보류하는 것이 실패가 아니라는 것 — 시나리오 칸 아래와 보류 결론 아래에 같은 말로 적는다
  const HOLD = '이 시험은 그 설비의 지금 값으로 계산합니다. 그 설비에 지금 이상 값이 없으면 어느 구성이든 원인 진단을 보류합니다(실패가 아니라 판단하지 않은 것입니다). 「유압 설비」 화면에서 그 이상을 일으킨 뒤 시험하면 판단까지 갑니다.';
  const scenarioOf = t => (S.opts?.scenarios || []).find(s => s.asset === t.asset && s.pattern === t.pattern);
  const scenarioLabel = t => scenarioOf(t)?.label || `${UI.name(t.pattern)} · ${t.asset}`;
  const skillShow = name => { for (const a of S.opts?.agents || []) { const k = (a.skills || []).find(x => x.name === name); if (k) return UI.skillLabel(k).label; } return name; };      // 스킬은 등록한 설명으로 부른다(없으면 등록 이름)
  // 서버 문장 속의 도구 서버 id(「… 은 enterprise 서버의 도구입니다」)는 이름표로 읽는다. 앞의 두 바꿈은 옛 서버 판본이 저장한 시험 기록(지난 시험과 비교)에만 남아 있는 말이다
  const plainReason = s => UI.idText(String(s || '').replaceAll('판단 엔진 도구(hyd-dmn)', '판단 시스템 도구 서버').replace(/hyd-dmn 가/g, '판단 시스템 도구 서버가')
    .replace(/\b(hyd-dmn|enterprise-maint|enterprise-purchase|enterprise|neo4j)(?= 서버)/g, id => serverName(id)).replaceAll('hyd-dmn', serverName('hyd-dmn')));
  // 한쪽이 판단에 이르렀는가: ok = 원인과 1순위 조치까지 / hold = 근거가 없어 판단하지 않음(정상 결과) / none = 판단에 이르지 못함
  const reach = t => t.status === 'EVALUATED' ? 'ok' : t.status === 'WITHHELD' ? 'hold' : 'none';
  const whyNot = t => t.status === 'NO_ENGINE_TOOL' ? '구성에 판단 시스템 도구 서버가 없어 원인 진단부터 하지 못했습니다'
    : t.status === 'NO_FEASIBLE_OPTION' ? '원인은 가렸지만 규정상 실행할 수 있는 조치가 없습니다'
    : t.status === 'WITHHELD' ? '지금 관측 값으로 뒷받침되는 원인이 없어 판단을 보류했습니다'
    : plainReason(t.result?.reason) || (STATUS[t.status] || [t.status])[0];

  // 결론: 학생이 알고 싶은 것 — 두 구성이 같은 원인 · 같은 1순위 조치에 이르렀는가, 한쪽만 못 이르렀는가(무엇이 없어서), 둘 다 판단하지 않았는가.
  // 서버의 same_result 는 호출 기록 전체의 지문이라(막힌 호출 한 줄만 달라도 「다름」, 둘 다 보류여도 「같음」) 결론에 쓰지 않는다 — 호출 차이는 그 아래 한 줄이다
  function verdict(r) {
    const d = r.diff, a = r.a, b = r.b, ka = reach(a), kb = reach(b);
    const got = t => `원인 ${UI.name(t.result.diagnosis?.top?.id)}, 1순위 조치 ${UI.name(t.result.recommended?.id)}`;
    if (a.asset !== b.asset || a.pattern !== b.pattern) return { apart: true, title: '서로 다른 시나리오의 시험이라 견줄 수 없습니다.',
      sub: `A는 「${scenarioLabel(a)}」, B는 「${scenarioLabel(b)}」의 시험입니다. 설비와 경보가 달라 결과의 차이가 구성에서 온 것인지 가릴 수 없습니다. 같은 시나리오의 시험 둘을 고르세요.` };
    if (ka === 'ok' && kb === 'ok') {
      if (d.cause.same && d.recommended.same) return { title: `두 구성이 같은 원인(${UI.name(d.cause.a)})과 같은 1순위 조치(${UI.name(d.recommended.a)})에 이르렀습니다.`, sub: '' };
      if (!d.cause.same) return { title: `두 구성이 가린 원인이 다릅니다 — A는 ${UI.name(d.cause.a)}, B는 ${UI.name(d.cause.b)}.`, sub: '' };
      return { title: `원인은 같고 1순위 조치가 다릅니다 — A는 ${UI.name(d.recommended.a)}, B는 ${UI.name(d.recommended.b)}.`, sub: `두 구성 모두 원인은 ${UI.name(d.cause.a)}입니다.` };
    }
    if (ka === 'hold' && kb === 'hold') return { title: '두 구성 모두 판단을 보류했습니다 — 지금 그 설비의 관측 값으로 뒷받침되는 원인이 없습니다.', sub: HOLD };
    if (ka === 'ok' || kb === 'ok') { const [miss, hit, m, h] = ka === 'ok' ? ['B', 'A', b, a] : ['A', 'B', a, b];
      return { title: `${miss}만 판단에 이르지 못했습니다 — ${whyNot(m)}.`, sub: `${hit}는 ${got(h)}에 이르렀습니다.` }; }
    return { title: '두 구성 모두 판단에 이르지 못했습니다.', sub: whyNot(a) === whyNot(b) ? `${whyNot(a)}.` : `A: ${whyNot(a)}. B: ${whyNot(b)}.` };
  }

  async function load() {
    try { S.opts = await getJ(api('/api/agent-trials/options')); S.error = null; S.loadError = null; }
    catch (e) { S.loadError = e.message; }
    const agents = S.opts?.agents || [];
    if (!S.form.a && agents[0]) S.form.a = agents.find(a => a.id === 'sys:agent')?.id || agents[0].id;
    if (!S.form.b && agents[0]) S.form.b = (agents.find(a => a.id !== S.form.a) || agents[0]).id;
    render();
  }

  // 왼쪽: 시험 조건 → [시험 실행] → B 에서 빼 보기(이번 시험에만)
  function formPane() {
    const o = S.opts, head = `<div class="panel-head"><div><h2>시험 조건</h2></div></div>`;
    if (!o) return head + `<div class="panel-sec">${S.loadError ? UI.errorBlock('시험 설정을 불러오지 못했습니다', S.loadError, { retry: true }) : UI.loading()}</div>`;
    if (!o.agents.length) return head + `<div class="panel-sec">${UI.emptyGo('AI 에이전트가 없습니다', '「에이전트 · 스킬」 화면에서 만들면 여기에 나타납니다.', 'agents', '에이전트 · 스킬 열기', 'compact')}</div>`;
    const opt = (list, value, label, cur) => list.map(x => `<option value="${esc(value(x))}" ${value(x) === cur ? 'selected' : ''}>${esc(label(x))}</option>`).join('');
    const b = o.agents.find(a => a.id === S.form.b) || o.agents[0];
    const hint = id => (o.agents.find(a => a.id === id) || {}).trial_note || '';   // 시험 시나리오로 그 에이전트의 일을 재지 못하는 까닭(서버가 정함)
    const box = (kind, name, label, off, i) => `<div role="group" class="field" data-orientation="horizontal"><input type="checkbox" class="input" id="cmpDrop-${kind}-${i}" data-drop="${kind}" value="${esc(name)}" ${off ? '' : 'checked'}><label for="cmpDrop-${kind}-${i}">${label}</label></div>`;
    const dropped = S.dropTools.length + S.dropSkills.length;
    return head + `<div class="panel-sec">` +
      UI.section('',
        UI.field({ label: '시나리오', input: `<select data-f="scenario"><option value="">시나리오 선택</option>${opt(o.scenarios, s => s.key, s => s.label, S.form.scenario)}</select>`, hint: '가상 설비 3기의 경보 셋 가운데 고릅니다. 그 설비에 지금 이상 값이 없으면 어느 구성이든 원인 진단을 보류합니다.' }).replace('<p class="field-hint">', `<p class="field-hint" title="${esc(HOLD)}">`) +
        UI.field({ label: '에이전트 A', input: `<select data-f="a">${opt(o.agents, a => a.id, a => a.name, S.form.a)}</select>`, hint: hint(S.form.a) }) +
        UI.field({ label: '에이전트 B', input: `<select data-f="b">${opt(o.agents, a => a.id, a => a.name, S.form.b)}</select>`, hint: hint(S.form.b) }) +
        UI.field({ label: '입력', input: `<select data-f="input"><option value="new" ${S.form.input === 'new' ? 'selected' : ''}>지금 값을 새로 읽어 고정</option><option value="latest" ${S.form.input === 'latest' ? 'selected' : ''}>이 시나리오의 직전 입력 다시 쓰기</option></select>`, hint: '두 에이전트는 늘 같은 입력으로 계산합니다.' })) +
      (S.loadError ? note(`시험 설정을 다시 읽지 못해 앞서 읽은 목록을 보이고 있습니다: ${esc(S.loadError)}`, ' data-tone="danger" role="status"') : '') +
      `<footer class="form-foot"><button type="button" class="btn" data-act="run" ${S.busy ? 'disabled' : ''}>${UI.icon('play')}시험 실행</button></footer>` +
      (S.error ? note(esc(S.error), ' data-tone="danger" role="alert"') : '') + `</div>` +
      `<div class="panel-sec"><details class="fold io-more" data-cmp-drop${dropped || S.dropOpen ? ' open' : ''}><summary>B에서 빼 보기<span class="muted num">${dropped ? `${dropped}개 뺌` : ''}</span></summary><div class="fold-body">` +
        note('체크를 풀면 B에서 그 도구 서버나 스킬을 빼고 계산합니다. 저장하지 않습니다.') +
        `<div class="field"><label>도구 서버</label>${b.tools.length ? b.tools.map((t, i) => box('tool', t, esc(serverName(t) || t), S.dropTools.includes(t), i)).join('') : note('없음')}</div>` +
        `<div class="field"><label>스킬</label>${b.skills.length ? b.skills.map((k, i) => box('skill', k.name, esc(UI.skillLabel(k).label), S.dropSkills.includes(k.name), i)).join('') : note('없음')}</div>` +
      `<footer class="form-foot">${dropped ? `<button type="button" class="btn" data-variant="outline" data-size="sm" data-act="reset">${UI.actHtml('revert')}</button>` : ''}` +
        `<button type="button" class="btn" data-variant="link" data-go-tab="agents">에이전트 · 스킬 열기${UI.icon('arrow-right')}</button></footer>${note(WHAT, ' data-cmp-what')}</div></details></div>`;
  }

  // 무엇이 다른가: 한 줄씩(아이콘 + 문장). 접지 않는다
  function headlineLines(r) {
    const d = r.diff, a = r.a, b = r.b, lines = [], both = reach(a) === 'ok' && reach(b) === 'ok';
    const one = (id, sop) => id ? `${esc(sop || '')} ${nm(id)}` : '없음';
    lines.push(['lock', d.same_input ? `같은 입력(${esc(UI.dateTime(r.snapshot?.created_at || a.created_at))}에 고정)으로 계산했습니다. 차이는 구성에서만 나옵니다.`
      : `두 시험의 입력이 다릅니다 — A는 ${esc(UI.dateTime(a.created_at))}, B는 ${esc(UI.dateTime(b.created_at))}에 읽은 값입니다. 아래 차이에는 그 사이 설비 값과 지식의 변화가 섞여 있습니다.`]);
    if (both && !d.cause.same) lines.push(['search', `<b>원인이 다릅니다</b> A ${one(d.cause.a)} · B ${one(d.cause.b)}`]);
    if (both) lines.push(['scale', d.recommended.same ? `<b>1순위는 같습니다</b> ${one(d.recommended.a, d.recommended.a_sop)}`
      : `<b>1순위가 다릅니다</b> A ${one(d.recommended.a, d.recommended.a_sop)} · B ${one(d.recommended.b, d.recommended.b_sop)}`]);
    // 호출 차이: 한쪽에만 있는 호출 가운데 실제로 부른 것과 부르지 못한 것을 갈라 말한다(막힌 제출 호출 한 줄을 「다른 판단」으로 읽지 않게)
    const only = (t, key) => d.calls.filter(row => row[key] != null && row[key === 'a' ? 'b' : 'a'] == null).map(row => t.result.calls[row[key]]);
    const cnt = xs => { const miss = xs.filter(c => c.status !== 'DONE').length; return `${xs.length}회${miss ? `(부르지 못한 호출 ${miss}회 포함)` : ''}`; };
    lines.push(['plug', d.order_same ? '<b>도구 호출 순서는 같습니다</b>' : `<b>도구 호출이 다릅니다</b> A에만 ${cnt(only(a, 'a'))} · B에만 ${cnt(only(b, 'b'))}. 아래 「도구 호출 순서」에서 줄마다 봅니다.`]);
    if (both && d.facts.length) lines.push(['database', `<b>판단 사실 ${d.facts.length}개가 다릅니다</b> 도구 구성에 따라 받지 못한 값을 포함합니다.`]);
    if (both && d.citations.only_a.length + d.citations.only_b.length) lines.push(['file-text', `<b>근거 인용</b> A에만 ${d.citations.only_a.length}개 · B에만 ${d.citations.only_b.length}개`]);
    // 읽은 규칙의 차이는 두 쪽이 모두 판단까지 갔을 때만 뜻이 있다(한쪽이 판단하지 않았으면 그쪽은 규칙을 읽지 않은 것이다). 같은 입력이면 지식이 같으므로 차이가 나지 않는다
    if (both && !d.same_input && d.rules.only_a.length + d.rules.only_b.length) lines.push(['list-checks', `<b>읽은 판단 규칙이 다릅니다</b> A에만 ${d.rules.only_a.length}개 · B에만 ${d.rules.only_b.length}개 — 두 시험 사이에 지식의 규칙이 바뀌었습니다.`]);
    return `<ul class="evid">${lines.map(([ic, l]) => `<li>${UI.icon(ic)}<span>${l}</span></li>`).join('')}</ul>`;
  }

  // 한쪽의 계산: 이름 + 상태 뱃지 하나 → 원인 · 1순위 → 쓴 도구 서버 · 스킬 → 설명. 시험 번호 · 결과 지문은 접기 안에
  function sideCard(label, t) {
    const r = t.result, top = r.diagnosis?.top, rec = r.recommended;
    const v = t.variant || {}, cutTools = (v.without_tools || []).map(serverName), cutSkills = (v.without_skills || []).map(skillShow);
    const cutNote = xs => xs.length ? ` <span class="muted">(이번 시험에서 뺀 것: ${esc(xs.join(', '))})</span>` : '';
    // 스킬 줄: 문서에서 알아본 도구 호출 수, 실제로 부른 수, 부르지 못한 수와 까닭(서버가 적은 호출 기록에서 센다). 「따랐다」고 뭉뚱그리지 않는다
    const skillLine = k => {
      if (!k.applied) return `이 시험에서는 쓰지 않음${k.reason ? ' — ' + esc(k.reason) : ''}`;
      const mine = (r.calls || []).filter(c => c.by === `스킬 ${k.name}`), miss = mine.filter(c => c.status !== 'DONE');
      if (!mine.length) return '문서에서 따로 부를 도구 이름을 찾지 못했습니다. 절차 글은 계산에 쓰지 않습니다.';
      const whys = [...new Set(miss.map(c => plainReason(c.reason)).filter(Boolean))];
      return `문서에서 알아본 도구 호출 ${mine.length}개 · 실제로 부른 것 ${mine.length - miss.length}개` + (miss.length ? ` · 부르지 못한 것 ${miss.length}개(${esc(whys.join(' / '))})` : '');
    };
    const ran = r.agent?.skills || [], has = (t.setting?.skills || []).length;
    const skills = ran.length ? ran.map(k => `${esc(skillShow(k.name))} <span class="muted">${skillLine(k)}</span>`).join('<br>')
      : has ? `<span class="muted">붙인 스킬 ${has}개 — 원인 진단에서 멈춰 스킬 문서의 도구 호출까지 가지 않았습니다.</span>` : '없음';
    return UI.card({ title: `${label} · ${esc(t.setting?.name || agentName(t.agent_id))}`, chips: statusChip(t.status), body:
      kv([['원인', top ? `<b>${nm(top.id)}</b> <span class="muted">${esc(UI.name(top.failureModeId))}</span>` : esc(whyNot(t))],
        ['1순위', rec ? `<b>${esc(rec.sopId)} ${nm(rec.id)}</b>` : top ? esc(whyNot(t)) : '원인을 가리지 않아 조치를 견주지 않았습니다'],      // 원인을 못 가린 까닭은 원인 줄에 한 번만 쓴다
        ['도구 서버', ((r.agent?.tools || []).map(x => esc(serverName(x))).join(' · ') || '없음') + cutNote(cutTools)],
        ['스킬', skills + cutNote(cutSkills)]]) +
      (r.explanation ? UI.fold('판단 엔진 설명 전문', note(esc(UI.idText(r.explanation)))) : '') +
      UI.fold('시험 번호 · 결과 지문', kv([['시험 번호', `<span class="mono">${esc(t.id)}</span>`], ['입력', `<span class="mono">${esc(t.snapshot_id)}</span>`], ['결과 지문', `<span class="mono">${esc(String(t.fingerprint).slice(0, 12))}</span>`]]) + UI.evaluationHtml(r, undefined, { raw: false })) });
  }

  // 호출 한 칸: 번호 · 도구 이름 · 서버 → 무엇이 나왔나. mark = 이 줄이 어떻게 다른지(「A에만」 · 「B에만」 · 「결과 다름」) — 글로 적는다
  function callCell(c, n, mark = '', side = '') {
    if (!c) return `<td class="muted"><span class="io-side">${side}</span>—</td>`;
    const diff = mark ? ' ' + badge(mark) : '';
    const st = c.status === 'DONE' ? '' : ' ' + chip(CALL[c.status] || ['호출 상태 기록 확인 필요', 'neutral']);      // 끝난 호출에는 상태 뱃지를 붙이지 않는다
    const purchase = window.hydWords?.purchaseTool(c.tool);
    if (purchase && (c.server === 'hyd-dmn' || UI.toolKey(c.tool).startsWith('mcp__hyd-dmn__'))) {
      const words = window.hydWords, output = c.output ?? c.result ?? c.value;
      const purchaseError = output != null && words.purchaseFailed(output);
      const result = output != null ? words.purchaseGot(purchase, output) : '호출 완료 · 상세 결과 값 기록 없음';
      const reason = String(c.reason || '').replace(/\b(?:purchase_context|evaluate_purchase|submit_purchase)\b/g, key => toolName(key, 'hyd-dmn')).replaceAll('hyd-dmn', serverName('hyd-dmn'));
      const why = reason && /[가-힣]/.test(reason) && !/[A-Za-z]+_[A-Za-z_]+/.test(reason) ? ' · ' + words.text(reason) : '';
      const state = c.status === 'BLOCKED' ? '구매 도구 요청을 부르지 못했습니다.' + (why || ' 사유는 아래 원본 기록에 있습니다.') : c.status === 'FAILED' ? '구매 도구 호출에 실패했습니다.' + (why || ' 사유는 아래 원본 기록에 있습니다.') : result;
      return `<td><span class="io-side">${side}</span><span class="num muted">${n}</span> <b>${esc(toolName(purchase, 'hyd-dmn'))}</b> <span class="muted">${esc(serverName('hyd-dmn'))}</span>${purchaseError ? ' ' + chip(['구매 요청 처리 실패', 'danger']) : st}${diff}<p>${esc(words.purchaseAsk(purchase, c.args))}</p><p class="muted">${esc(state)}</p></td>`;
    }
    // 호출 입력의 원문(JSON)은 칸에 펼치지 않는다 — 맨 아래 「원본 기록」 접기에 호출마다 들어 있다. 스킬이 부른 호출은 스킬의 등록 설명으로 적는다
    const by = String(c.by || '').startsWith('스킬 ') ? `스킬 「${skillShow(c.by.slice(3))}」의 문서에 적힌 호출` : '';
    return `<td><span class="io-side">${side}</span><span class="num muted">${n}</span> <b>${esc(toolName(c.tool, c.server))}</b> <span class="muted">${esc(serverName(c.server))}</span>${st}${diff}` +
      `<p>${esc(callSummary(c))}</p>${by ? `<p class="muted">${esc(by)}</p>` : ''}${c.status === 'DONE' && c.reason ? `<p class="muted">${esc(plainReason(c.reason))}</p>` : ''}</td>`;
  }
  // 호출 결과 한 줄: 서버 요약의 내부 말(「후보 4장 · 제외 0장」, id)을 화면 말로
  // 「후보 n장」은 옛 서버 판본이 저장한 시험 기록에만 남아 있는 말이다(지금 서버는 「조치 후보 n개」로 준다)
  const callSummary = c => plainReason(c.summary || c.reason || '').replace(/(?<!조치 )후보 (\d+)장/g, '조치 후보 $1개').replace(/제외 (\d+)장/g, '제외 $1개');

  function callTable(r) {
    const A = r.a.result.calls, B = r.b.result.calls;
    const rows = r.diff.calls.map(row => {
      const changed = row.a != null && row.b != null && !row.same ? '결과 다름' : '';
      return `<tr>${callCell(row.a == null ? null : A[row.a], row.a == null ? '' : row.a + 1, row.b == null ? 'A에만' : changed, 'A')}${callCell(row.b == null ? null : B[row.b], row.b == null ? '' : row.b + 1, row.a == null ? 'B에만' : changed, 'B')}</tr>`;
    }).join('');
    return sec('도구 호출 순서', r.diff.order_same ? '두 구성이 같은 순서로 불렀습니다' : '두 구성의 호출 순서가 다릅니다',
      table('<th>A</th><th>B</th>', rows).replace('<table class="table"', '<table class="table io-even"') + note('한쪽에만 있는 호출에는 「A에만」이나 「B에만」이, 같은 호출인데 결과 요약이 다르면 「결과 다름」이 붙습니다.'));
  }

  function rankTable(d) {
    if (!d.ranking.length) return '';
    const cell = (rank, ok, score) => rank ? `${esc(rank)}위${ok === false ? ' ' + UI.chipText('제외', 'danger') : ''} <span class="muted num">${esc(score ?? '')}</span>` : '—';
    return sec('조치 순위', `${d.ranking.length}개`, UI.optionsTable(d.ranking.map(o => ({ rank: o.rank_a || o.rank_b || '–', name: UI.name(o.id), code: o.sopId,
      nameHtml: o.rank_a !== o.rank_b || o.feasible_a !== o.feasible_b ? ' ' + badge('다름') : '', extra: [cell(o.rank_a, o.feasible_a, o.score_a), cell(o.rank_b, o.feasible_b, o.score_b)] })),
      { extra: [{ label: 'A' }, { label: 'B' }] }));
  }

  // 다른 점: 차이마다 접기 하나(차이가 있는 것은 펼쳐서 시작). 원본 기록(JSON)은 맨 아래 접기 안에 둔다
  function details(r) {
    const d = r.diff;
    const val = (f, v, blocked) => blocked ? UI.chipText('받지 못함', 'warning') : esc(v == null ? '미확인' : hydWords.value(f.variable, v));
    const facts = d.facts.length ? table('<th>사실</th><th>A</th><th>B</th>', d.facts.map(f =>
      `<tr><td>${esc(f.name || hydWords.fieldName(f.variable))}</td><td>${val(f, f.a, f.blocked_a)}</td><td>${val(f, f.b, f.blocked_b)}</td></tr>`).join('')) : note('판단 사실이 같습니다.');
    const list = xs => xs.length ? `<ul>${xs.map(x => `<li>${ref(x)}</li>`).join('')}</ul>` : note('없음');
    const citeDiff = d.citations.only_a.length + d.citations.only_b.length;
    const two = (a, b) => `<div class="io-two"><div><p><b>A에만</b></p>${list(a)}</div><div><p><b>B에만</b></p>${list(b)}</div></div>`;
    const cites = (citeDiff ? two(d.citations.only_a, d.citations.only_b) : '') + note(`${citeDiff ? '' : '두 구성이 인용한 근거가 같습니다. '}같은 인용 ${esc(d.citations.shared)}개`);
    const comp = d.compliance.length ? table('<th>조치</th><th>A 제외 사유</th><th>B 제외 사유</th>', d.compliance.map(c =>
      `<tr><td>${nm(c.id)}</td><td>${esc(UI.idText((c.a || []).join(' / ') || '없음'))}</td><td>${esc(UI.idText((c.b || []).join(' / ') || '없음'))}</td></tr>`).join('')) : note('규정 판정이 같습니다.');
    const rules = reach(r.a) === 'ok' && reach(r.b) === 'ok' && d.rules.only_a.length + d.rules.only_b.length ?`<p><b>한쪽에만 있는 규칙</b></p>` + two(d.rules.only_a, d.rules.only_b) : '';
    const count = n => `<span class="muted">${n ? n + '개' : '같음'}</span>`;
    return `<div class="panel-sec"><h3>다른 점</h3>` +
      UI.fold(`판단 사실 차이${count(d.facts.length)}`, facts, { open: !!d.facts.length }) +
      UI.fold(`근거 인용 차이${count(citeDiff)}`, cites, { open: !!citeDiff }) +
      UI.fold(`규정 판정 차이${count(d.compliance.length)}`, comp + rules, { open: !!d.compliance.length }) +
      UI.raw({ a: r.a.result, b: r.b.result }, { title: '호출 입력과 결과의 원문' }) + `</div>`;
  }

  function resultView(r) {
    if (!r) return `${UI.empty({ icon: 'git-compare', title: `아직 시험한 결과가 없습니다`, sub: `왼쪽에서 시나리오와 에이전트 둘을 고르고 [시험 실행]을 누르면, 같은 입력에서 두 구성이 계산한 결과가 나란히 보입니다.` })}`;
    if (!r.b) return `<section class="panel"><div class="panel-sec">${sideCard('A', r.a)}</div></section>`;
    const d = r.diff, v = verdict(r), head = `<section class="panel"><div class="panel-head"><div><div class="result-label">${UI.icon('sparkles')}결론</div>` +
      `<h2>${esc(v.title)}</h2>${v.sub ? `<p>${esc(v.sub)}</p>` : ''}`;
    // 서로 다른 시나리오의 시험 둘은 견주지 않는다 — 차이 표를 그리면 설비가 다른 것을 구성의 차이로 읽게 된다. 두 시험을 따로 보이기만 한다
    if (v.apart) return head + `</div></div><div class="panel-sec"><div class="io-two">${sideCard(`A · ${esc(scenarioLabel(r.a))}`, r.a)}${sideCard(`B · ${esc(scenarioLabel(r.b))}`, r.b)}</div></div></section>`;
    const none = t => reach(t) === 'hold' ? '판단 보류' : '없음';
    const same = (x, name) => x.same ? (x.a ? nm(x.a) : esc(none(r.a))) : x.a && x.b ? UI.chipText('다름', 'warning') : `${UI.chipText(x.a ? 'A만 ' + name : 'B만 ' + name, 'warning')}`;
    return head + `</div></div>` +
      `<dl class="turn-facts">${fact('원인', same(d.cause, '가림'))}` +
        `${fact('1순위 조치', same(d.recommended, '정함'))}` +
        `${fact('도구 호출 순서', d.order_same ? '같음' : `${UI.chipText('다름', 'warning')}<small>A에만 ${esc(d.calls_only_a)}회 · B에만 ${esc(d.calls_only_b)}회</small>`)}` +
        `${fact('판단 사실 차이', `<span class="num">${d.facts.length}</span><small>개</small>`)}</dl>` +
      `<div class="panel-sec">${headlineLines(r)}</div>` +
      `<div class="panel-sec"><div class="io-two">${sideCard('A', r.a)}${sideCard('B', r.b)}</div></div>` +
      callTable(r) + rankTable(d) + details(r) + `</section>`;
  }

  // 지난 시험과 비교: 결과 아래의 판 하나
  function historyPane() {
    const h = S.history;
    const rows = h == null ? '' : h.length < 2 ? UI.empty('저장된 시험이 둘 이상 있어야 비교할 수 있습니다', '위에서 시험을 한 번 더 실행하면 비교할 수 있습니다.', 'compact') : UI.section('', ['a', 'b'].map(side =>
      UI.field({ label: side === 'a' ? '바꾸기 전 시험' : '바꾼 뒤 시험', input: `<select data-pick="${side}"><option value="">시험 선택</option>${h.map(t =>
        `<option value="${esc(t.id)}" ${S.pick[side] === t.id ? 'selected' : ''}>${esc(scenarioLabel(t))} · ${esc(t.agent_name || agentName(t.agent_id))} · ${esc(UI.dateTime(t.created_at))} · ${esc(t.recommended ? '1순위 ' + UI.name(t.recommended) : STATUS[t.status]?.[0] || t.status)}${(t.variant?.without_tools || []).length + (t.variant?.without_skills || []).length ? ' · 빼 본 구성' : ''}</option>`).join('')}</select>` })).join(''));
    const label = h == null ? '저장된 시험 불러오기' : '두 시험 비교';
    // 고른 둘이 서로 다른 시나리오면 누르기 전에 말한다(견줄 수 없는 까닭)
    const pa = h?.find(t => t.id === S.pick.a), pb = h?.find(t => t.id === S.pick.b), apart = pa && pb && (pa.asset !== pb.asset || pa.pattern !== pb.pattern);
    return `<section class="panel"><div class="panel-head"><div><h2>지난 시험과 비교</h2><p>규칙이나 지식을 바꾸기 전과 후에, 같은 시나리오의 계산 결과가 그대로인지 봅니다.</p></div></div><div class="panel-sec">` +
      rows + (apart ? note(`고른 두 시험의 시나리오가 다릅니다(「${esc(scenarioLabel(pa))}」와 「${esc(scenarioLabel(pb))}」). 설비와 경보가 다른 시험은 견줄 수 없습니다 — 같은 시나리오의 시험 둘을 고르세요.`, ' data-tone="danger" role="status"') : '') + (S.histError ? UI.errorBlock(h == null ? '저장된 시험을 불러오지 못했습니다' : '두 시험을 비교하지 못했습니다', S.histError) : '') +
      `<footer class="form-foot"><button type="button" class="btn" data-variant="outline" data-act="${h == null ? 'history' : 'diff'}" ${S.histBusy || (h && (h.length < 2 || !S.pick.a || !S.pick.b || apart)) ? 'disabled' : ''}>${UI.icon(h == null ? 'history' : 'git-compare')}${esc(label)}</button></footer></div></section>`;
  }

  function render() {
    if (!S.el) return;
    const open = new Set([...S.el.querySelectorAll('details[open] > summary')].map(x => x.textContent.trim()));      // 다시 그려도 펼친 접기는 그대로 둔다
    const shut = new Set([...S.el.querySelectorAll('details:not([open]) > summary')].map(x => x.textContent.trim()));
    S.el.innerHTML = `<div class="io"><form class="panel io-in" aria-label="시험 조건">${formPane()}</form><div class="io-out"><div data-r="result" aria-live="polite">${S.busy
        ? '<div data-cmp-track></div>' : S.runError ? UI.errorBlock('시험을 실행하지 못했습니다', S.runError) : resultView(S.result)}</div>${S.opts && S.opts.agents.length ? historyPane() : ''}</div></div>`;
    S.el.querySelectorAll('details > summary').forEach(x => { const k = x.textContent.trim(); if (open.has(k)) x.parentElement.open = true; else if (shut.has(k)) x.parentElement.open = false; });
    if (S.busy && S.track) S.track.mount(S.el.querySelector('[data-cmp-track]'));      // 다시 그려도 같은 진행 목록이 새 자리로 옮겨 간다
    if (S.busy) hydLive.busy(S.el.querySelector('[data-act="run"]'), '시험하는 중', S.since);
    if (S.histBusy) hydLive.busy(S.el.querySelector('[data-act="history"],[data-act="diff"]'), S.history == null ? '불러오는 중' : '비교하는 중', S.histSince);
  }

  async function runTrial() {
    if (!S.form.scenario) { S.error = '시나리오를 고르세요.'; render(); return; }      // 고르지 않은 시나리오로 시험하지 않는다
    // 서버가 「입력 고정 → 에이전트 A 시험 → 에이전트 B 시험 → 두 결과 비교」를 그 일이 시작 · 끝날 때 진행 기록에 적는다(hydLive.track 이 읽어 채운다)
    S.since = new Date().toISOString();
    S.track = hydLive.track({ since: S.since, text: '두 구성을 같은 입력으로 계산하는 중', hint: '지금 값을 읽어 입력을 고정하고, 에이전트 A와 B의 구성으로 판단 단계를 차례로 계산합니다. 비교 결과는 모두 끝난 뒤 보입니다.' });
    S.busy = true; S.error = S.runError = null; render();
    try {
      S.result = await postJ(api('/api/agent-trials/run'), { request_id: S.track.id, scenario: S.form.scenario, reuse_latest: S.form.input === 'latest',
        a: { agent: S.form.a }, b: { agent: S.form.b, variant: { without_tools: S.dropTools, without_skills: S.dropSkills } } });
      S.history = null;
    } catch (e) { S.runError = e.message; S.result = null; }
    S.track.stop(); S.track = null;
    S.busy = false; render();
  }

  async function loadHistory() {
    S.histBusy = true; S.histSince = new Date().toISOString(); S.histError = null; render();
    try { S.history = await getJ(api('/api/agent-trials?limit=40')); } catch (e) { S.histError = e.message; }
    S.histBusy = false; render();
  }

  async function diffStored() {
    S.histBusy = true; S.histSince = new Date().toISOString(); S.histError = null; render();
    try { const r = await getJ(api(`/api/agent-trials/diff?a=${encodeURIComponent(S.pick.a)}&b=${encodeURIComponent(S.pick.b)}`)); S.result = { ...r, snapshot: null }; }
    catch (e) { S.histError = e.message; }
    S.histBusy = false; render();
    if (!S.histError) S.el.querySelector('[data-r="result"]')?.scrollIntoView({ block: 'start', behavior: 'smooth' });      // 비교 결과는 위 결과 자리에 열린다
  }

  function bind(el) {
    el.addEventListener('submit', e => e.preventDefault());
    el.addEventListener('toggle', e => { if (e.target.matches && e.target.matches('[data-cmp-drop]')) S.dropOpen = e.target.open; }, true);      // 다시 그려도 펼친 채로
    el.addEventListener('change', e => {
      const t = e.target;
      if (t.dataset.f) { S.form[t.dataset.f] = t.value; if (t.dataset.f === 'b') { S.dropTools = []; S.dropSkills = []; } if (t.dataset.f === 'scenario') S.error = null; render(); }
      else if (t.dataset.drop) {
        const list = t.dataset.drop === 'tool' ? S.dropTools : S.dropSkills;
        const i = list.indexOf(t.value);
        if (!t.checked && i < 0) list.push(t.value); else if (t.checked && i >= 0) list.splice(i, 1);
        render();
      } else if (t.dataset.pick) { S.pick[t.dataset.pick] = t.value; render(); }
    });
    el.addEventListener('click', e => {
      const sum = e.target.closest('[data-cmp-drop] > summary'); if (sum) S.dropOpen = !sum.parentNode.open;      // 펼침은 누른 순간에 적어 둔다(toggle 사건은 다시 그린 뒤에 올 수 있다)
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
