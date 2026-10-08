/* AI 에이전트 · 스킬 보기 (U2 · TODO A2) — 읽기 전용.
   원천 하나: 에이전트 = users 표(is_agent), 스킬 = tenant_skills 표, 붙이기 = agent_skills 표. 수강생은 랩업(Claude Code)에서
   이 표에 넣고, 이 화면은 "다시 읽기" 때 그대로 보여 준다. 워커도 실행마다 같은 행을 읽는다(procsvc/agents_store.agent_settings).
   API: GET /api/agents · /api/agents/{id} · /api/skills · /api/skills/{name} (procsvc/agents_api.py). 쓰기 버튼 없음.
   레이아웃: process-gpt-vue3 AgentChatInfo.vue(목표 → 성격 → 도구 → 스킬 → 모델, 긴 글은 펼치기)와 SkillDetail.vue(사용 중 에이전트).
   셸(U7)은 window.hydAgents.mount(el) 로 아무 컨테이너에나 그릴 수 있다. */
(function () {
  const SERVER_WORDS = { neo4j: '지식 그래프', enterprise: '업무 DB', 'hyd-dmn': '판단 규칙 · 시계열' };
  const MODEL_FROM = { activity: '단계 설정', agent: '에이전트 설정' };
  const TOOLS_FROM = { agent: '에이전트 설정', activity: '단계 설정', 'agent+activity': '에이전트 도구 중 단계가 허용한 것' };
  const SHORT = 80;
  const st = { host: null, tab: 'agents', agents: null, skills: null, pick: { agents: null, skills: null }, detail: null, error: '', open: {}, seq: 0 };

  const serverName = (name, description) => description || SERVER_WORDS[name] || name;
  const modelText = m => m || '실행기 기본 모델';
  function reason(e) {
    if (e && e.status === 409) return '처리 엔진이 처리 건 모드로 켜져 있지 않아 에이전트 설정을 읽을 수 없습니다. 강의 배포 설정으로 처리 엔진을 다시 켜야 합니다.';
    if (e && e.status === 404) return '찾을 수 없습니다. 랩업에서 지웠거나 이름이 바뀌었을 수 있습니다. 다시 읽어 보세요.';
    return '불러오지 못했습니다: ' + ((e && e.message) || '처리 엔진에 연결할 수 없습니다');
  }
  function longText(key, text) {
    const t = String(text || '');
    if (t.length <= SHORT || st.open[key]) return esc(t) + (t.length > SHORT ? ` <button type="button" class="btn small" data-fold-text="${esc(key)}">접기</button>` : '');
    return esc(t.slice(0, SHORT)) + '… ' + `<button type="button" class="btn small" data-fold-text="${esc(key)}">펼치기</button>`;
  }
  const clip = (t, n = 48) => (t.length > n ? t.slice(0, n) + '…' : t);
  const stepLabel = s => `${s.definition_name || UI.defName(s.definition_id)} · ${s.name}`;   // 정의에 등록된 이름 먼저(영문 id 노출 0)
  const chips = (items, tone = 'neutral') => items.length ? items.map(t => UI.chipText(t, tone)).join(' ') : '<span class="muted">없음</span>';

  async function load() {
    const seq = ++st.seq;
    try {
      const [agents, skills] = await Promise.all([getJ(API.process + '/api/agents'), getJ(API.process + '/api/skills')]);
      if (seq !== st.seq) return;
      st.agents = agents; st.skills = skills; st.error = '';
      if (st.pick.agents && !agents.some(a => a.id === st.pick.agents)) st.pick.agents = null;
      if (st.pick.skills && !skills.some(s => s.skill_name === st.pick.skills)) st.pick.skills = null;
      if (!st.pick.agents && agents.length) st.pick.agents = agents[0].id;
      if (!st.pick.skills && skills.length) st.pick.skills = skills[0].skill_name;
    } catch (e) {
      if (seq !== st.seq) return;
      st.error = reason(e); st.agents = st.agents || []; st.skills = st.skills || [];
    }
    render();
    await loadDetail();
  }
  async function loadDetail() {
    const key = st.tab === 'agents' ? st.pick.agents : st.pick.skills;
    const box = st.host && st.host.querySelector('[data-ag-detail]');
    if (!box) return;
    if (!key) { box.innerHTML = emptyDetail(); return; }
    const url = st.tab === 'agents' ? '/api/agents/' + encodeURIComponent(key) : '/api/skills/' + encodeURIComponent(key);
    const tab = st.tab;
    box.innerHTML = UI.empty('불러오는 중', '', 'compact');
    try {
      const d = await getJ(API.process + url);
      if (tab !== st.tab || key !== (tab === 'agents' ? st.pick.agents : st.pick.skills)) return;
      st.detail = d;
      box.innerHTML = tab === 'agents' ? agentDetail(d) : skillDetail(d);
    } catch (e) {
      box.innerHTML = `<div class="neg" role="status">${esc(reason(e))}</div>`;
    }
  }
  function emptyDetail() {
    return st.tab === 'agents'
      ? UI.empty('에이전트가 없습니다', '랩업에서 users 표에 에이전트를 넣으면 여기에 나타납니다.')
      : UI.empty('아직 스킬이 없습니다', '랩업에서 SKILL.md 를 스킬 저장소(tenant_skills 표)에 넣고 에이전트에 붙이면 여기에 나타납니다.');
  }

  /* ---------- 목록 ---------- */
  function agentItem(a) {
    const sel = a.id === st.pick.agents ? ' sel' : '';
    const agentSteps = a.steps.filter(s => s.agent).length;
    const count = a.kind === 'agent' ? `맡은 단계 ${agentSteps} · 도구 ${a.tools.length} · 스킬 ${a.skills.length}` : `맡은 단계 ${a.steps.length}`;
    return `<div class="item${sel}" role="button" tabindex="0" data-pick-agent="${esc(a.id)}" title="${esc(a.name)}">` +
      `<div class="row"><strong>${esc(a.name)}</strong>${UI.chipText(a.kind === 'agent' ? 'AI 에이전트' : '시스템 수행자', a.kind === 'agent' ? 'accent' : 'neutral')}</div>` +
      `<span class="sub">${esc(clip(a.goal || a.role || '목표가 적혀 있지 않습니다'))}</span><span class="sub">${esc(count)}</span></div>`;
  }
  function skillItem(s) {
    const sel = s.skill_name === st.pick.skills ? ' sel' : '';
    const who = s.agents.length ? s.agents.map(a => a.name).join(', ') : '붙은 에이전트 없음';
    return `<div class="item${sel}" role="button" tabindex="0" data-pick-skill="${esc(s.skill_name)}">` +
      `<div class="row"><strong>${esc(s.title)}</strong>${UI.chipText(s.agents.length ? `에이전트 ${s.agents.length}` : '미배정', s.agents.length ? 'accent' : 'warning')}</div>` +
      `<span class="sub">${esc(s.description || '설명 없음')}</span><span class="sub">${esc(who)}</span></div>`;
  }
  function listHtml() {
    if (st.tab === 'agents') {
      const agents = (st.agents || []).filter(a => a.kind === 'agent'), systems = (st.agents || []).filter(a => a.kind !== 'agent');
      return (agents.length ? agents.map(agentItem).join('') : UI.empty('AI 에이전트가 없습니다', '', 'compact')) +
        (systems.length ? UI.fold(`시스템 수행자 <span class="chip tone-neutral sm">${systems.length}</span>`, systems.map(agentItem).join(''),
          { open: systems.some(a => a.id === st.pick.agents), cls: 'small' }) : '');
    }
    return (st.skills || []).length ? st.skills.map(skillItem).join('') : UI.empty('아직 스킬이 없습니다', '', 'compact');
  }

  /* ---------- 에이전트 상세 (요약 먼저, 실행 설정·지시문은 펼침) ---------- */
  function agentDetail(d) {
    const isAgent = d.kind === 'agent';
    const toolChips = d.tools.length ? d.tools.map(t => `<span class="chip tone-${t.registered ? 'success' : 'danger'}" title="${esc(t.name)}">${esc(serverName(t.name, t.description))}${t.registered ? '' : ' · 등록 안 됨'}</span>`).join(' ')
      : `<span class="muted">${isAgent ? '지정 없음 — 등록된 도구 서버를 모두 씁니다' : '없음'}</span>`;
    const skillBtns = d.skills.length ? d.skills.map(s => s.found
      ? `<button type="button" class="btn small" data-goto-skill="${esc(s.skill_name)}" title="${esc(s.description)}">${esc(s.title)}</button>`
      : `<span class="chip tone-danger" title="${esc(s.skill_name)}">본문 없는 스킬</span>`).join(' ') : '<span class="muted">없음</span>';
    const steps = d.steps.length ? chips(d.steps.map(stepLabel), 'neutral')
      : '<span class="muted">맡은 단계가 없습니다. 흐름 정의에서 이 에이전트를 담당자로 둔 단계가 없으면 처리 건에서 불리지 않습니다.</span>';
    const rows = [['역할', esc(d.role || '–')], ['목표', longText('goal:' + d.id, d.goal || '–')]];
    if (isAgent) rows.push(['성격 · 말투', d.persona ? longText('persona:' + d.id, d.persona) : '<span class="muted">적혀 있지 않습니다</span>'],
      ['모델', esc(modelText(d.model))], ['쓰는 도구', toolChips], ['스킬', skillBtns]);
    rows.push(['맡은 단계', steps]);
    const summary = `<dl class="meta-list" style="grid-template-columns:1fr">${rows.map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${v}</dd></div>`).join('')}</dl>`;
    let html = `<div class="detail-head"><div class="row"><h2>${esc(d.name)}</h2>${UI.chipText(isAgent ? 'AI 에이전트' : '시스템 수행자', isAgent ? 'accent' : 'neutral')}</div>` +
      `<div class="sub">${isAgent ? '이 설정으로 실제 실행됩니다 — 워커가 실행마다 같은 원천을 읽습니다.' : '정해진 업무를 하는 시스템입니다. 에이전트 설정은 쓰지 않습니다.'}</div></div>` +
      UI.card({ title: '요약', body: summary });
    if (isAgent) {
      const run = d.run || {};
      const stepRows = (run.steps || []).map(s => {
        const x = s.settings;
        const tools = x.tools == null ? '등록된 도구 서버 전부' : x.tools.length ? x.tools.map(t => serverName(t)).join(', ') : '없음(겹치는 도구가 없음)';
        return `<tr><td>${esc(s.name)}</td><td>${esc(modelText(x.model))}${x.model_source ? `<br><span class="muted">${esc(MODEL_FROM[x.model_source] || '')}</span>` : ''}</td>` +
          `<td>${esc(tools)}${x.tools_source ? `<br><span class="muted">${esc(TOOLS_FROM[x.tools_source] || '')}</span>` : ''}</td>` +
          `<td>${esc(x.skills.length ? x.skills.join(', ') : '없음')}${x.missing_skills.length ? `<br><span class="neg">본문 없음: ${esc(x.missing_skills.join(', '))}</span>` : ''}</td></tr>`;
      }).join('');
      html += UI.fold(`단계별 실제 실행 설정 <span class="chip tone-neutral sm">${(run.steps || []).length}</span>`,
        stepRows ? `<div class="table-scroll"><table class="compact-table"><thead><tr><th>단계</th><th>모델</th><th>도구 서버</th><th>스킬 파일</th></tr></thead><tbody>${stepRows}</tbody></table></div>`
          : UI.empty('맡은 단계가 없습니다', '처리 건에서는 불리지 않습니다.', 'compact'));
      html += UI.fold('실행 지시문에 더해지는 내용', run.instructions ? `<pre>${esc(run.instructions)}</pre><p class="muted">워커가 이 내용을 지시문에 넣고, 스킬은 실행 작업 폴더에 SKILL.md 파일로 씁니다.</p>`
        : UI.empty('더해지는 내용이 없습니다', '이름·목표·성격·스킬이 비어 있습니다.', 'compact'));
    }
    html += UI.metaFold([['저장 위치', '사용자 표(users)'], ['식별자', `<span class="mono">${esc(d.id)}</span>`],
      ['등록된 도구 서버', esc(((d.run || {}).servers_registered || []).map(n => serverName(n.name, n.description)).join(', '))]]);
    return html;
  }

  /* ---------- 스킬 상세 ---------- */
  function skillDetail(s) {
    const agents = s.agents.length ? s.agents.map(a => `<button type="button" class="btn small" data-goto-agent="${esc(a.id)}">${esc(a.name)}</button>`).join(' ')
      : '<span class="muted">붙은 에이전트가 없습니다. 붙이지 않은 스킬은 어떤 실행에도 들어가지 않습니다.</span>';
    const steps = s.steps.length ? chips(s.steps.map(stepLabel)) : '<span class="muted">없음</span>';
    const summary = `<dl class="meta-list" style="grid-template-columns:1fr">` +
      [['설명', esc(s.description || '–')], ['붙은 에이전트', agents], ['선언한 단계', steps], ['고친 시각', esc(s.updated_at ? UI.dateTime(s.updated_at) : '–')]]
        .map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${v}</dd></div>`).join('') + '</dl>';
    return `<div class="detail-head"><div class="row"><h2>${esc(s.title)}</h2>${UI.chipText('에이전트 스킬', 'accent')}</div>` +
      `<div class="sub">붙은 에이전트가 실행될 때 작업 폴더에 이 문서가 SKILL.md 로 들어갑니다.</div></div>` +
      UI.card({ title: '요약', body: summary }) +
      UI.card({ title: '스킬 문서', body: `<pre style="max-height:480px;overflow:auto">${esc(s.content || '')}</pre>` }) +
      UI.metaFold([['폴더 이름', `<span class="mono">${esc(s.skill_name)}</span>`], ['저장 위치', '스킬 저장소(tenant_skills 표)'], ['길이', esc((s.content || '').length.toLocaleString('ko-KR') + '자')]]);
  }

  /* ---------- 화면 ---------- */
  function render() {
    if (!st.host) return;
    const n = st.agents ? st.agents.filter(a => a.kind === 'agent').length : null, m = st.skills ? st.skills.length : null;
    st.host.innerHTML =
      `<div class="page-head"><h1>AI 에이전트</h1><div class="page-tools"><button type="button" class="btn small" data-ag-reload>다시 읽기</button></div></div>` +
      `<p class="muted">보기 전용입니다. 에이전트·스킬은 랩업(Claude Code)에서 추가하고, 다시 읽으면 여기와 다음 실행에 함께 나타납니다.</p>` +
      (st.error ? `<div class="neg" role="status">${esc(st.error)}</div>` : '') +
      UI.tabs([['agents', '에이전트', n], ['skills', '스킬', m]], st.tab, 'data-ag-tab') +
      `<div class="split"><div><div class="list">${st.agents ? listHtml() : UI.empty('불러오는 중', '', 'compact')}</div></div><div class="detail" data-ag-detail></div></div>`;
  }
  function pick(tab, key) {
    st.tab = tab; st.pick[tab] = key;
    render(); loadDetail();
    const box = st.host.querySelector('[data-ag-detail]'); if (box) UI.revealDetail(box);
  }
  function onClick(e) {
    const t = e.target.closest('button, [data-pick-agent], [data-pick-skill]');
    if (!t || !st.host.contains(t)) return;
    if (t.hasAttribute('data-ag-reload')) return load();
    if (t.dataset.agTab) { st.tab = t.dataset.agTab; render(); return loadDetail(); }
    if (t.dataset.pickAgent) return pick('agents', t.dataset.pickAgent);
    if (t.dataset.pickSkill) return pick('skills', t.dataset.pickSkill);
    if (t.dataset.gotoSkill) return pick('skills', t.dataset.gotoSkill);
    if (t.dataset.gotoAgent) return pick('agents', t.dataset.gotoAgent);
    if (t.dataset.foldText) {
      st.open[t.dataset.foldText] = !st.open[t.dataset.foldText];
      const box = st.host.querySelector('[data-ag-detail]');
      if (box && st.detail && st.tab === 'agents') box.innerHTML = agentDetail(st.detail);
    }
  }
  function onKey(e) {
    if ((e.key === 'Enter' || e.key === ' ') && e.target.matches('[data-pick-agent], [data-pick-skill]')) { e.preventDefault(); e.target.click(); }
  }

  function mount(el) {
    if (!el) return;
    if (st.host !== el) {
      st.host = el;
      el.addEventListener('click', onClick);
      el.addEventListener('keydown', onKey);
    }
    render();
    load();
  }
  window.hydAgents = { mount };

  // 지금 셸: 사이드바 "AI 에이전트"로 화면이 열릴 때마다 다시 읽는다 (U7 셸은 mount 를 직접 부른다)
  const host = document.getElementById('agentsView');
  const view = host && host.closest('.view');
  if (view) {
    const show = () => { if (view.classList.contains('active')) mount(host); };
    new MutationObserver(show).observe(view, { attributes: true, attributeFilter: ['class'] });
    show();
  }
})();
