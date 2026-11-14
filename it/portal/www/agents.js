/* AI 에이전트 · 스킬 · 담당 배정 (U2 보기 + B1 직접 만들기).
   원천 하나: 에이전트 = users 표(is_agent), 스킬 = tenant_skills 표, 붙이기 = agent_skills 표, 단계 → 에이전트 = activity_agent_map,
   역할의 구성원 = role_members(늘 이 PC의 담당자 한 명 — 화면에서 사람을 넣고 빼지 않는다). 워커는 실행마다 같은 행을 읽는다(procsvc/agents_store.agent_settings) — 여기서 고친 것이 다음 실행에 쓰인다.
   기본(시드) 에이전트 · 스킬 · 업무분장은 보호: 고치기 · 지우기 대신 "복제해서 고치기". 내가 만든 것은 "내가 만든" 표시, "기준으로 되돌리기"로 지움.
   API: 읽기 GET /api/agents · /api/agents/{id} · /api/skills · /api/skills/{name} (agents_api.py),
        쓰기 POST·PUT·DELETE /api/agents · /api/skills · /api/agent-assignments · /api/roles · POST /api/agents/reset (agent_authoring_api.py).
   레이아웃: process-gpt-vue3 AgentChatInfo.vue(목표 → 성격 → 도구 → 스킬 → 모델) · AgentField.vue:64-170(편집 폼) · SkillDetail.vue(사용 중 에이전트).
   셸(U7)은 window.hydAgents.mount(el) 로 아무 컨테이너에나 그릴 수 있다. */
(function () {
  const MODEL_FROM = { activity: '단계 설정', agent: '에이전트 설정' };
  const TOOLS_FROM = { agent: '에이전트 설정', activity: '단계 설정', 'agent+activity': '에이전트 도구 중 단계가 허용한 것' };
  const SHORT = 240;
  const st = { host: null, tab: 'agents', agents: null, skills: null, pick: { agents: null, skills: null, systems: null }, doc: {}, detail: null, error: '', open: {}, seq: 0,
    form: null, options: null, board: null, boardError: '', busy: false, acting: new Set() };

  const serverName = (name, description) => hydWords.serverName(name, description);   // 도구 서버 이름표는 plainWords.js 하나
  const course = () => window.hydCourseAccess;
  const skillName = (name, labels=[]) => UI.skillLabel(labels.find(s=>(s.name || s.skill_name) === name) || (st.skills || []).find(s=>s.skill_name === name) || {name}).label;
  // 모델은 이 시스템이 정한 하나다(서버 GET /api/course-access 의 model) — 비어 있거나 그 값이면 「기본 모델」
  const modelText = m => !m || m === course().model ? '기본 모델' : m;
  const api = path => API.process + path;
  const del = url => requestJ(url, { method: 'DELETE' });
  // 누가 했나 = 이 PC의 담당자 id. 에이전트 지우기 · 되돌리기 · 단계 배정은 서버가 「누가」를 요구한다(열린 단계의 담당이 바뀐 기록에 남는다 —
  // inbox.actor_or_400, 비면 400). 담당자를 못 읽었으면 다른 값으로 대신하지 않고 까닭과 함께 멈춘다(act 가 그 까닭을 띄운다)
  function me() { const id = window.hydInbox?.me?.()?.id; if (!id) throw new Error('담당자 정보를 읽지 못해 보낼 수 없습니다. 화면을 새로 고친 뒤 다시 해 주세요.'); return id; }
  const icon = (name, cls) => UI.icon(name, cls);
  const tag = (label, tone, plain) => `<span class="tag"${tone ? ` data-tone="${tone}"` : ''}${plain ? ' data-plain' : ''}>${esc(label)}</span>`;
  // 구분 뱃지: 기본 제공 / 내가 만든 것(상태가 아니라 종류라 점 없이)
  const originTag = o => tag(o === 'user' ? '내가 만든 것' : '기본 제공', o === 'user' ? 'brand' : '', true);
  // 오류 · 읽는 중은 ui.js 의 부품을 쓴다. 이름–값은 값이 없는 줄을 그리지 않는다
  const errBox = (what, why) => UI.errorBlock(what, why, { retry: true });      // [다시 시도]는 onClick 의 data-retry 가 받는다
  const loading = () => UI.loading('');
  const kv = rows => { const r = rows.filter(([, v]) => v != null && v !== ''); return r.length ? `<dl class="kv">${r.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${v}</dd>`).join('')}</dl>` : ''; };
  function reason(e) {
    if (e && e.status === 404 && !/[가-힣]/.test(e.message || '')) return '찾을 수 없습니다. 지웠거나 이름이 바뀌었을 수 있습니다. 다시 읽어 보세요.';
    return (e && e.message) || '처리 엔진에 연결할 수 없습니다';
  }
  function longText(key, text) {
    const t = String(text || '');
    if (t.length <= SHORT || st.open[key]) return esc(t) + (t.length > SHORT ? ` <button type="button" class="btn" data-variant="link" data-fold-text="${esc(key)}">줄이기</button>` : '');
    return esc(t.slice(0, SHORT)) + '… ' + `<button type="button" class="btn" data-variant="link" data-fold-text="${esc(key)}">더 보기</button>`;
  }
  const clip = (t, n = 48) => (t.length > n ? t.slice(0, n) + '…' : t);
  const stepLabel = s => `${s.definition_name || UI.defName(s.definition_id)} · ${UI.flowName(s.name)}`;   // 정의에 등록된 이름 먼저
  // 두 번 눌림 막기: 같은 일이 끝날 때까지 그 단추를 끈다(복제가 두 벌 생기거나 붙이기가 409 로 보이지 않게)
  async function once(key, button, work) {
    if (st.acting.has(key)) return null;
    // 누른 단추가 「…중 · 걸린 시간」으로 바뀐다(다시 그려져 단추가 사라졌으면 손대지 않는다)
    st.acting.add(key); const end = button ? hydLive.busy(button, button.textContent.trim() + ' 중') : null;
    try { return await work(); } finally { st.acting.delete(key); if (end && button.isConnected) end(false); }
  }
  // 실행 설정의 도구 서버: 서버가 계산한 servers({서버: 정해진 조회 도구 | null}) 그대로 — 교대 · 질문처럼 조회 도구가 정해진 단계는 그 도구만
  function runServersText(servers) {
    const names = Object.keys(servers || {});
    if (!names.length) return '없음(이 단계에서 쓰는 도구 서버가 없음)';
    return names.map(n => servers[n] ? `${serverName(n)}(정해진 조회 도구 ${servers[n].length}개만)` : serverName(n)).join(', ');
  }

  /* ---------- 읽기 ---------- */
  async function load() {
    const seq = ++st.seq;
    try {
      const [agents, skills] = await Promise.all([getJ(api('/api/agents')), getJ(api('/api/skills'))]);
      if (seq !== st.seq) return;
      requireList(agents, '에이전트 목록'); requireList(skills, '스킬 목록');
      st.agents = agents; st.skills = skills; st.error = ''; st.loaded = true;
      registerNames(agents);
      if (st.pick.skills && !skills.some(s => s.skill_name === st.pick.skills)) st.pick.skills = null;
      const ai = agents.filter(a => a.kind === 'agent'), sys = agents.filter(a => a.kind !== 'agent');
      if (!ai.some(a => a.id === st.pick.agents)) st.pick.agents = ai.length ? ai[0].id : null;
      if (!sys.some(a => a.id === st.pick.systems)) st.pick.systems = sys.length ? sys[0].id : null;
      if (!st.pick.skills && skills.length) st.pick.skills = skills[0].skill_name;
    } catch (e) {
      if (seq !== st.seq) return;
      st.error = reason(e); st.agents = st.agents || []; st.skills = st.skills || [];
    }
    if (st.tab === 'assign') await loadBoard();
    render();
    await loadDetail();
  }
  function registerNames(agents) {                // 처리 건 · 작업함 화면의 "누가"가 에이전트 id 대신 이름으로 보이게
    let changed = false;
    (agents || []).forEach(a => { if (UI.performers[a.id] !== a.name) { UI.performers[a.id] = a.name; changed = true; } });
    if (changed) UI.namesVersion = (UI.namesVersion || 0) + 1;
  }
  async function loadOptions() {
    try { st.options = await getJ(api('/api/agent-authoring/options')); }
    catch (e) { st.options = { servers: [], skills: [], models: [], error: reason(e) }; }
  }
  async function loadBoard() {
    try { st.board = await getJ(api('/api/agent-assignments')); st.boardError = ''; }
    catch (e) { st.boardError = reason(e); }
  }
  async function loadDetail() {
    if (st.tab === 'assign') return;
    const box = st.host && st.host.querySelector('[data-ag-detail]');
    if (!box) return;
    if (st.form) { box.innerHTML = formHtml(); renderMarkdown(box); return; }
    const tab = st.tab, key = st.pick[tab];
    if (!key) { box.innerHTML = emptyDetail(); return; }
    const url = tab === 'skills' ? '/api/skills/' + encodeURIComponent(key) : '/api/agents/' + encodeURIComponent(key);
    box.innerHTML = `<div class="pane-none">${loading()}</div>`;
    try {
      const d = await getJ(api(url));
      if (tab !== st.tab || key !== st.pick[tab] || st.form) return;
      st.detail = d;
      drawDetail();
    } catch (e) {
      box.innerHTML = `<div class="pane-none">${errBox(tab === 'skills' ? '스킬을 읽지 못했습니다' : '에이전트를 읽지 못했습니다', reason(e))}</div>`;
    }
  }
  // 읽어 둔 상세(st.detail)를 그 자리에 그린다 — 스킬 문서 · 작업 규칙의 마크다운은 그린 뒤에 채운다
  function drawDetail() {
    const box = st.host.querySelector('[data-ag-detail]'); if (!box || !st.detail || st.form) return;
    box.innerHTML = st.tab === 'skills' ? skillDetail(st.detail) : agentDetail(st.detail);
    renderMarkdown(box);
    if (st.tab !== 'skills') drawSkillDoc();
  }
  function emptyDetail() {
    const none = (name, title, sub) => `<div class="pane-none">${UI.empty({ icon: name, title: `${title}`, sub: `${sub}` })}</div>`;
    if (st.error) return '';
    return st.tab === 'skills' ? none('file-text', '아직 스킬이 없습니다', '화면 위의 [스킬 만들기]로 작업 요령 문서(SKILL.md)를 쓰면 여기에 나타납니다.')
      : st.tab === 'systems' ? none('cog', '시스템 수행자가 없습니다', '흐름의 시스템 단계를 맡는 수행자가 등록되어 있지 않습니다.')
      : none('bot', '에이전트가 없습니다', '화면 위의 [새 에이전트]로 만들면 여기에 나타납니다.');
  }

  /* ---------- 목록: 묶음 단추(에이전트 · 스킬 · 시스템 수행자 · 담당 배정)로 거르고, 한 줄에 이름 · 구분 뱃지 · 쓰는 것 한 줄 ---------- */
  const ROW_SKELETON = Array.from({ length: 4 }, () => `<div class="sk-row"><div class="skeleton sk-line" style="width:55%"></div><div class="skeleton sk-line" style="width:35%"></div></div>`).join('');
  function agentRow(a) {
    const system = a.kind !== 'agent';
    const meta = system ? (a.goal || a.role || '정해진 업무를 하는 시스템') : `스킬 ${a.skills.length} · 도구 서버 ${a.tools.length ? a.tools.length : '전체'} · ${a.steps.length ? `맡은 단계 ${a.steps.length}` : '맡은 단계 없음'}`;
    return `<button type="button" class="row" data-pick-agent="${esc(a.id)}"${a.id === st.pick[st.tab] && !st.form ? ' aria-current="true"' : ''}><span class="row-ic">${icon(system ? 'cog' : 'bot')}</span>` +
      `<span class="row-title">${esc(a.name)}</span>${system ? '' : originTag(a.origin)}<span class="row-meta">${esc(meta)}</span></button>`;
  }
  function skillRow(s) {
    // 뱃지는 한 줄에 하나: 어느 에이전트에도 붙지 않은 스킬은 그 상태를(주의), 나머지는 기본 제공 / 내가 만든 것을 보인다
    return `<button type="button" class="row" data-pick-skill="${esc(s.skill_name)}"${s.skill_name === st.pick.skills && !st.form ? ' aria-current="true"' : ''}><span class="row-ic">${icon('file-text')}</span>` +
      `<span class="row-title">${esc(s.title)}</span>${s.agents.length ? originTag(s.origin) : tag('붙은 에이전트 없음', 'warn')}<span class="row-meta">${esc(s.description || '설명 없음')}</span></button>`;
  }
  function listHtml() {
    if (!st.agents) return ROW_SKELETON;
    if (st.error && !st.loaded) return '';      // 목록을 한 번도 못 읽었다 — 위의 오류 판만 보인다(「없습니다」가 아니다)
    const note = html => `<div class="pane-list-note">${html}</div>`;
    if (st.tab === 'skills') return (st.skills || []).length ? st.skills.map(skillRow).join('')
      : note(UI.empty('아직 스킬이 없습니다', '화면 위의 [스킬 만들기]로 작업 요령 문서(SKILL.md)를 쓰면 여기에 나타납니다.'));
    const rows = st.agents.filter(a => (a.kind === 'agent') === (st.tab === 'agents'));
    return rows.length ? rows.map(agentRow).join('')
      : note(st.tab === 'agents' ? UI.empty('AI 에이전트가 없습니다', '화면 위의 [새 에이전트]로 만들면 여기에 나타납니다.') : UI.empty('시스템 수행자가 없습니다', '흐름의 시스템 단계를 맡는 수행자가 등록되어 있지 않습니다.'));
  }

  /* ---------- 에이전트 상세(디자인 기준 5-4): 머리 → 스킬 / 도구 서버 두 칸 → 스킬 문서 → 맡은 단계 → 설정 → 작업 규칙 · 자세히(접기) ---------- */
  // 머리의 도구: [시험해 보기](질문하기 화면에서 이 에이전트에게 묻는다) · 내 것이면 [고치기] · 복제 · 지우기, 기본 제공이면 [복제해서 고치기]
  function agentActs(d) {
    if (d.kind !== 'agent') return '';
    const tryIt = `<button type="button" class="btn" data-variant="outline" data-try-agent="${esc(d.id)}">${icon('play')}시험해 보기</button>`;
    if (!d.editable) return tryIt + `<button type="button" class="btn" data-variant="outline" data-clone="${esc(d.id)}">${icon('copy')}복제해서 고치기</button>`;
    return tryIt + `<button type="button" class="btn" data-variant="outline" data-edit-agent>${icon('pencil')}고치기</button>` +
      `<button type="button" class="btn" data-variant="ghost" data-size="icon" data-clone="${esc(d.id)}" aria-label="복제해서 고치기" data-tooltip="복제해서 고치기" data-side="bottom">${icon('copy')}</button>` +
      `<button type="button" class="btn" data-variant="ghost" data-size="icon" data-del-agent aria-label="지우기" data-tooltip="지우기" data-side="bottom">${icon('trash-2')}</button>`;
  }
  const stepUse = s => `<button type="button" class="use" data-goto-flow="${esc(s.definition_id)}">${icon('workflow')}<span><b>${esc(s.definition_name || UI.defName(s.definition_id))}</b>${s.version ? ` <span class="muted num">판본 ${esc(s.version)}</span>` : ''}</span>${icon('chevron-right', 'ic-sm')}<span>${esc(UI.flowName(s.name))}</span>` +
    `<span class="muted">${s.assigned ? '담당 배정으로 맡음 · ' : ''}흐름에서 보기</span></button>`;
  function agentDetail(d) {
    const isAgent = d.kind === 'agent';
    const state = !isAgent ? tag('시스템 수행자') : d.steps.length ? tag('단계를 맡고 있음', 'ok') : tag('맡은 단계 없음');
    const note = !isAgent ? '정해진 업무를 하는 시스템입니다. 스킬 · 도구 서버 같은 에이전트 설정은 쓰지 않습니다.' : d.goal || '목표가 적혀 있지 않습니다.';
    let html = `<div class="panel-head pane-head"><span class="pane-ic"${isAgent ? ' data-kind="agent"' : ''}>${icon(isAgent ? 'bot' : 'cog')}</span>` +
      `<div class="pane-title"><h2>${esc(d.name)}${state}${isAgent ? originTag(d.origin) : ''}</h2><p>${longText('goal:' + d.id, note)}</p></div><div class="pane-acts">${agentActs(d)}</div></div>`;
    if (isAgent) {
      const skills = d.skills.length ? d.skills.map((s, i) => s.found
        ? `<button type="button" class="use" data-skill-doc="${esc(s.skill_name)}" aria-expanded="${s.skill_name === docSkill(d)}">${icon('file-text')}<span><b>${esc(s.title)}</b></span><span class="muted mono">${esc(s.skill_name)}</span></button>`
        : `<div class="use">${icon('circle-alert')}<span><b>본문 없는 스킬</b></span><span class="muted mono">${esc(s.skill_name)}</span></div>`).join('')
        : '<p class="muted">붙은 스킬이 없습니다. 스킬이 없으면 목표와 작업 규칙만으로 판단합니다.</p>';
      const tools = d.tools.length ? d.tools.map(t => `<button type="button" class="use" data-goto-server="${esc(t.name)}">${icon('plug')}<span><b>${esc(serverName(t.name, t.description))}</b></span>` +
        `<span class="muted"><i class="dot" data-tone="${t.registered ? 'ok' : 'danger'}"></i>${t.registered ? '연결됨' : '등록 안 됨'}</span></button>`).join('')
        : '<p class="muted">도구 서버를 정하지 않아, 등록된 도구 서버를 모두 씁니다.</p>';
      html += `<div class="pane-grid"><div class="panel-sec"><h3>${icon('file-text', 'ic-sm')}스킬<span class="muted num">${d.skills ? d.skills.length : ''}</span></h3>${skills}</div>` +
        `<div class="panel-sec"><h3>${icon('plug', 'ic-sm')}도구 서버<span class="muted num">${d.tools.length || ''}</span></h3>${tools}</div></div>` +
        (docSkill(d) ? `<div class="panel-sec" data-skill-doc-box></div>` : '');
    }
    html += `<div class="panel-sec"><h3>${icon('workflow', 'ic-sm')}맡은 단계<span class="muted num">${d.steps.length || ''}</span></h3>` +
      (d.steps.length ? d.steps.map(stepUse).join('') : UI.empty({ title: '맡은 단계가 없습니다', sub: isAgent ? '[담당 배정]에서 단계를 맡기거나, 흐름 화면의 단계 설정에서 이 에이전트를 고르면 여기에 보입니다.' : '이 수행자를 쓰는 흐름 단계가 없습니다.', cls: 'compact',
          action: isAgent ? { label: '담당 배정 열기', attrs: 'data-goto-assign', icon: 'arrow-right' } : null })) + '</div>';
    if (isAgent) {
      const rules = d.work_rules_detail?.error ? d.work_rules_detail.error : d.work_rules_detail ? d.work_rules_detail.label : d.work_rules ? '작업 규칙 내용을 읽지 못했습니다' : '공통 안전 규칙만 적용';
      html += `<div class="panel-sec"><h3>${icon('sliders-horizontal', 'ic-sm')}설정${d.editable ? '<span class="muted">다음 실행부터 적용</span>' : ''}</h3>` +
        kv([['역할', esc(d.role || '')], ['성격 · 말투', d.persona ? longText('persona:' + d.id, d.persona) : ''], ['모델', esc(modelText(d.model))], ['작업 규칙', esc(rules)]]) + '</div>';
      if (d.work_rules_detail && !d.work_rules_detail.error) html += `<div class="panel-sec pane-fold"><details class="fold"><summary>작업 규칙 전문<span class="muted">${esc(d.work_rules_detail.label)}</span></summary><div class="fold-body"><div class="doc prose" data-md="${esc(d.work_rules_detail.content)}"></div></div></details></div>`;
      const run = d.run || {};
      const stepRows = (run.steps || []).map(s => {
        const x = s.settings;
        return `<tr><td>${esc(UI.flowName(s.name))}</td><td>${esc(modelText(x.model))}${x.model_source ? `<p class="muted">${esc(MODEL_FROM[x.model_source] || '')}</p>` : ''}</td>` +
          `<td>${esc(runServersText(s.servers))}${x.tools_source ? `<p class="muted">${esc(TOOLS_FROM[x.tools_source] || '')}</p>` : ''}</td>` +
          `<td>${esc(x.skills.length ? x.skills.map(n => skillName(n, x.skill_labels || [])).join(', ') : '없음')}${x.missing_skills.length ? `<p class="muted" data-tone="danger">본문 없는 스킬 ${x.missing_skills.length}개</p>` : ''}</td></tr>`;
      }).join('');
      const more = `<h4 class="ag-sub">단계별 실제 실행 설정</h4>` + (stepRows ? `<div class="table-container"><table class="table"><thead><tr><th>단계</th><th>모델</th><th>도구 서버</th><th>스킬</th></tr></thead><tbody>${stepRows}</tbody></table></div>`
          : '<p class="muted">맡은 단계가 없어 처리 건에서는 불리지 않습니다.</p>') +
        `<h4 class="ag-sub">실행 지시문에 더해지는 내용</h4>` + (run.instructions ? `<pre class="code">${esc(run.instructions)}</pre><p class="muted">AI 에이전트가 이 내용을 지시문에 넣고, 스킬은 실행 작업 폴더에 SKILL.md 파일로 씁니다.</p>`
          : '<p class="muted">더해지는 내용이 없습니다. 이름 · 목표 · 성격 · 스킬이 비어 있습니다.</p>') +
        `<h4 class="ag-sub">식별자</h4>` + kv([['식별자', `<span class="mono">${esc(d.id)}</span>`], ['등록된 도구 서버', esc(((d.run || {}).servers_registered || []).map(n => serverName(n.name, n.description)).join(', '))]]);
      html += `<div class="panel-sec pane-fold"><details class="fold"><summary>단계별 실행 설정 · 실행 지시문 · 식별자</summary><div class="fold-body">${more}</div></details></div>`;
    } else {
      html += `<div class="panel-sec">${kv([['역할', esc(d.role || '')], ['식별자', `<span class="mono">${esc(d.id)}</span>`]])}</div>`;
    }
    return html;
  }
  // 스킬 문서 칸에 보일 스킬: 고른 것, 없으면 본문이 있는 첫 스킬
  function docSkill(d) {
    const found = (d.skills || []).filter(s => s.found).map(s => s.skill_name);
    return found.includes(st.doc[d.id]) ? st.doc[d.id] : found[0] || '';
  }
  // 마크다운(스킬 문서 · 작업 규칙) → 소독한 HTML(.prose). 문서 머리의 YAML(--- name · description ---)은 본문이 아니라서 뺀다
  async function renderMarkdown(root) {
    const nodes = [...root.querySelectorAll('[data-md]')]; if (!nodes.length) return;
    try {
      await UI.need('markdown');
      nodes.forEach(n => { n.innerHTML = DOMPurify.sanitize(marked.parse(String(n.dataset.md).replace(/^---\n[\s\S]*?\n---\n?/, ''))); n.removeAttribute('data-md'); });
    } catch (e) { nodes.forEach(n => { n.classList.remove('prose'); n.innerHTML = `<pre class="code">${esc(n.dataset.md)}</pre>`; n.removeAttribute('data-md'); }); console.error('마크다운 부품을 싣지 못해 원문으로 보입니다:', e.message); }
  }
  async function drawSkillDoc() {
    const box = st.host.querySelector('[data-skill-doc-box]'), d = st.detail; if (!box || !d) return;
    const name = docSkill(d);
    box.innerHTML = `<h3>${icon('book-open', 'ic-sm')}스킬 문서</h3><div class="doc"><div class="skeleton sk-line" style="width:40%;height:16px"></div><div class="skeleton sk-line" style="margin-top:12px"></div><div class="skeleton sk-line" style="margin-top:8px;width:80%"></div></div>`;
    try {
      const s = await getJ(api('/api/skills/' + encodeURIComponent(name)));
      if (!box.isConnected || st.detail !== d || docSkill(d) !== name) return;
      box.querySelector('.doc').outerHTML = `<div class="doc fade-in"><div class="doc-bar">${icon('file-text', 'ic-sm')}<span class="mono">${esc(name)}/SKILL.md</span><span class="num">${(s.content || '').length.toLocaleString('ko-KR')}자</span></div><div class="prose" data-md="${esc(s.content || '')}"></div></div>`;
      renderMarkdown(box);
    } catch (e) { if (box.isConnected) box.querySelector('.doc').outerHTML = UI.errorBlock('스킬 문서를 읽지 못했습니다', reason(e)); }
  }

  /* ---------- 스킬 상세: 머리 → 스킬 문서 → 붙은 에이전트(붙이기 · 떼기) → 선언한 단계 → 자세히 ---------- */
  function skillDetail(s) {
    const mineAgents = (st.agents || []).filter(a => a.kind === 'agent' && a.editable);
    const attachedIds = new Set(s.agents.map(a => a.id));
    const mine = s.origin === 'user';
    const agents = s.agents.length ? s.agents.map(a => {
      const own = mineAgents.some(m => m.id === a.id);
      return `<div class="ag-attached"><button type="button" class="use" data-goto-agent="${esc(a.id)}">${icon('bot')}<span><b>${esc(a.name)}</b></span><span class="muted">에이전트 보기</span></button>` +
        (own ? `<button type="button" class="btn" data-variant="ghost" data-size="sm" data-detach="${esc(a.id)}">${icon('unlink')}스킬 떼기</button>` : '') + '</div>';
    }).join('') : '<p class="muted">붙은 에이전트가 없습니다. 붙이지 않은 스킬은 어떤 실행에도 들어가지 않습니다.</p>';
    const can = mineAgents.filter(a => !attachedIds.has(a.id));
    const attach = can.length ? `<div class="ag-attach"><select class="select" data-attach-to aria-label="붙일 에이전트"><option value="">에이전트를 고르세요</option>${can.map(a => `<option value="${esc(a.id)}">${esc(a.name)}</option>`).join('')}</select>` +
      `<button type="button" class="btn" data-variant="outline" data-attach disabled>${icon('link')}내 에이전트에 붙이기</button><span class="muted" data-attach-why>붙일 에이전트를 먼저 고르세요.</span></div>`
      : `<p class="muted">${mineAgents.length ? '내 에이전트에는 이미 모두 붙어 있습니다.' : '붙일 수 있는 내 에이전트가 없습니다. 기본 제공 에이전트에는 붙일 수 없으니, 에이전트를 복제하거나 새로 만들어 붙입니다.'}</p>`;
    const acts = mine ? `<button type="button" class="btn" data-variant="outline" data-edit-skill>${icon('pencil')}고치기</button>` +
      `<button type="button" class="btn" data-variant="ghost" data-size="icon" data-del-skill aria-label="지우기" data-tooltip="지우기" data-side="bottom">${icon('trash-2')}</button>` : '';
    return `<div class="panel-head pane-head"><span class="pane-ic">${icon('file-text')}</span><div class="pane-title"><h2>${esc(s.title)}${originTag(s.origin)}</h2>` +
      `<p>${esc(s.description || (mine ? '설명이 적혀 있지 않습니다.' : ''))}</p></div><div class="pane-acts">${acts}</div></div>` +
      `<div class="panel-sec"><h3>${icon('book-open', 'ic-sm')}스킬 문서<span class="muted">${mine ? '붙은 에이전트가 실행될 때 작업 폴더에 SKILL.md로 들어갑니다' : '기본 제공 스킬은 고칠 수 없습니다. 새 스킬을 만들어 씁니다'}</span></h3>` +
      `<div class="doc"><div class="doc-bar">${icon('file-text', 'ic-sm')}<span class="mono">${esc(s.skill_name)}/SKILL.md</span><span class="num">${(s.content || '').length.toLocaleString('ko-KR')}자</span></div><div class="prose" data-md="${esc(s.content || '')}"></div></div></div>` +
      `<div class="panel-sec"><h3>${icon('bot', 'ic-sm')}붙은 에이전트</h3>${agents}${attach}</div>` +
      (s.steps.length ? `<div class="panel-sec"><h3>${icon('workflow', 'ic-sm')}선언한 단계<span class="muted num">${s.steps.length}</span></h3>${s.steps.map(stepUse).join('')}</div>` : '') +
      `<div class="panel-sec pane-fold"><details class="fold"><summary>폴더 이름 · 고친 시각</summary><div class="fold-body">${kv([['폴더 이름', `<span class="mono">${esc(s.skill_name)}</span>`],
        ['고친 시각', s.updated_at ? esc(UI.dateTime(s.updated_at)) : '']])}</div></details></div>`;
  }

  /* ---------- 만들기 · 고치기 폼: 같은 판 안에서 fieldset 으로 열고, 아래에 취소 · 저장(주 단추) ---------- */
  function openForm(kind, d) {
    if (kind === 'agent') {
      st.form = { kind, id: d ? d.id : null, error: '', draft: d ? { name: d.name, role: d.role || '', goal: d.goal || '', persona: d.persona || '', model: '', work_rules: d.work_rules || '',
        tools: d.tools.filter(t => t.registered !== false).map(t => t.name || t), skills: d.skills.map(s => s.skill_name || s) }
        : { name: '', role: '', goal: '', persona: '', model: '', work_rules: '', tools: [], skills: [] } };
    } else {
      st.form = { kind, id: d ? d.skill_name : null, error: '', draft: d ? { skill_name: d.skill_name, description: d.description || '', content: d.content || '' }
        : { skill_name: '', description: '', content: '---\nname: \ndescription: \n---\n\n# 제목\n\n1. 먼저 조회할 값과 도구\n2. 판정 기준\n3. 모를 때 적는 법\n' } };
    }
    if (kind === 'agent' && !['agents', 'systems'].includes(st.tab)) st.tab = 'agents';
    if (kind === 'skill') st.tab = 'skills';
    render(); loadDetail();
    const box = st.host.querySelector('[data-ag-detail]'); if (box) UI.revealDetail(box);
  }
  const check = (attr, value, on, off, label) => `<label class="pane-opt"><input type="checkbox" class="input" ${attr} value="${esc(value)}" ${on ? 'checked' : ''} ${off ? 'disabled' : ''}><span>${label}</span></label>`;
  function formHtml() {
    const f = st.form, d = f.draft, o = st.options || { servers: [], skills: [], models: [] };
    const head = (title, sub) => `<div class="panel-head"><div><h2>${title}</h2><p>${sub}</p></div></div>`;
    if (f.kind === 'agent') {
      // 붙일 수 있는지는 서버 판정(mcp_registry.selectable) 그대로 — 붙일 수 없는 서버는 까닭과 함께 꺼 둔다(이미 붙어 있으면 뗄 수는 있다)
      const tools = o.servers.length ? o.servers.map(s => { const on = d.tools.includes(s.name);
        return check('data-f-tool', s.name, on, !s.selectable && !on, esc(serverName(s.name, s.description)) + (s.selectable ? '' : ` <span class="muted">붙일 수 없음${s.reason ? ' — ' + esc(s.reason) : ''}</span>`)); }).join('')
        : '<p class="muted">등록된 도구 서버가 없습니다.</p>';
      const skills = o.skills.length ? o.skills.map(s => check('data-f-skill', s.skill_name, d.skills.includes(s.skill_name), false, esc(UI.skillLabel(s).label) + (s.origin === 'user' ? ' <span class="muted">내가 만든 것</span>' : ''))).join('')
        : '<p class="muted">아직 스킬이 없습니다. 먼저 [스킬 만들기]로 만든 뒤 이 에이전트를 고쳐 붙입니다.</p>';
      return head(f.id ? '에이전트 고치기' : '새 에이전트', (f.cloned ? '기본 제공 에이전트를 복제한 사본입니다. 저장하지 않고 취소하면 사본은 지워집니다. ' : '') + '저장하면 다음 실행부터 이 설정으로 실행됩니다. 단계를 맡기려면 저장한 뒤 [담당 배정]에서 고릅니다.') +
        `<form data-ag-form class="panel-sec ag-form">${o.error ? UI.errorBlock('도구 서버 · 스킬 목록을 읽지 못했습니다', o.error) : ''}` +
        UI.section('기본', UI.field({ label: '이름', required: true, input: `<input data-f="name" maxlength="60" value="${esc(d.name)}">` }) +
          UI.field({ label: '역할', input: `<input data-f="role" maxlength="200" value="${esc(d.role)}" placeholder="예: 쿨러 열화를 먼저 본다">` }) +
          UI.field({ label: '목표', required: true, cls: 'ag-wide', input: `<textarea data-f="goal" maxlength="500" rows="2">${esc(d.goal)}</textarea>`, hint: '이 에이전트가 무엇을 해내야 하는지 한 문장' }) +
          UI.field({ label: '성격 · 말투', cls: 'ag-wide', input: `<textarea data-f="persona" maxlength="2000" rows="2">${esc(d.persona)}</textarea>` }) +
          UI.readonly('모델', esc(modelText('')), '모델은 이 시스템이 정한 하나를 씁니다. 바꿀 수 없습니다.')) +
        `<fieldset class="fieldset"><legend>도구 서버 (등록된 MCP 서버)</legend><div class="ag-checks">${tools}</div><p class="muted">하나도 고르지 않으면 등록된 서버를 모두 씁니다.</p></fieldset>` +
        `<fieldset class="fieldset"><legend>스킬</legend><div class="ag-checks">${skills}</div></fieldset>` +
        UI.section('작업 규칙', UI.field({ label: '적용할 작업 규칙', input: `<select data-f="work_rules"><option value="">공통 안전 규칙만 적용</option>${d.work_rules && !(o.work_rules || []).some(r => r.key === d.work_rules) ? `<option value="${esc(d.work_rules)}" selected>등록되지 않은 작업 규칙 — 다시 고르세요</option>` : ''}${(o.work_rules || []).map(r => `<option value="${esc(r.key)}" ${d.work_rules === r.key ? 'selected' : ''}>${esc(r.label)}</option>`).join('')}</select>` })) +
          (o.work_rules || []).map(r => `<details class="fold"><summary>${esc(r.label)} 내용</summary><div class="fold-body"><div class="doc prose" data-md="${esc(r.content)}"></div></div></details>`).join('') +
        formActions(f) + `</form>`;
    }
    return head(f.id ? '스킬 고치기' : '스킬 만들기', 'SKILL.md 한 장이 에이전트의 작업 요령입니다. 붙은 에이전트가 실행될 때 작업 폴더에 이 문서가 들어갑니다.') +
      `<form data-ag-form class="panel-sec ag-form">` +
      UI.section('스킬', UI.field({ label: '폴더 이름', required: true, input: `<input data-f="skill_name" class="input mono" maxlength="64" value="${esc(d.skill_name)}" ${f.id ? 'disabled' : ''} placeholder="예: cooler-check">`,
        hint: '영문 소문자 · 숫자 · 하이픈. 문서 머리의 name 과 같아야 합니다' }) +
        UI.field({ label: '설명 한 줄', input: `<input data-f="description" maxlength="300" value="${esc(d.description)}">`, hint: '비우면 문서 머리의 description 이나 첫 제목을 씁니다' }) +
        UI.field({ label: 'SKILL.md', required: true, cls: 'ag-wide', input: `<textarea data-f="content" class="textarea mono" rows="14" spellcheck="false">${esc(d.content)}</textarea>` })) +
      formActions(f) + `</form>`;
  }
  // 폼의 단추 줄: 저장이 안 된 까닭(무엇이 왜)은 단추 줄 바로 위의 오류 판에
  function formActions(f) {
    return (f.error ? UI.errorBlock(f.kind === 'agent' ? '에이전트를 저장하지 못했습니다' : '스킬을 저장하지 못했습니다', f.error) : '') +
      UI.formFoot(UI.btn('save', { submit: true, attrs: st.busy ? 'disabled' : '' }), { cancelAttrs: 'data-f-cancel' });
  }
  function readForm(form) {
    const d = st.form.draft;
    form.querySelectorAll('[data-f]').forEach(n => { if (!n.disabled) d[n.dataset.f] = n.value; });
    if (st.form.kind === 'agent') {
      d.tools = [...form.querySelectorAll('[data-f-tool]:checked')].map(n => n.value);
      d.skills = [...form.querySelectorAll('[data-f-skill]:checked')].map(n => n.value);
    }
    return d;
  }
  async function submitForm(form) {
    if (st.busy) return;
    const f = st.form, d = readForm(form);
    if (f.kind === 'skill' && !f.id && d.content.includes('\nname: \n')) d.content = d.content.replace('\nname: \n', `\nname: ${d.skill_name}\n`);
    st.busy = true;
    hydLive.busy(form.querySelector('button[type="submit"]'), '저장하는 중');      // 실패하면 폼을 다시 그리므로 따로 되돌리지 않는다. 성공하면 폼이 닫힌다
    try {
      let saved;
      if (f.kind === 'agent') saved = f.id ? await postJ(api('/api/agents/' + encodeURIComponent(f.id)), d, 'PUT') : await postJ(api('/api/agents'), d);
      else saved = f.id ? await postJ(api('/api/skills/' + encodeURIComponent(f.id)), d, 'PUT') : await postJ(api('/api/skills'), d);
      UI.toast(f.kind === 'agent' ? `에이전트 '${saved.username}'${window.hydWords.josa(saved.username, '을/를')} 저장했습니다` : `스킬 '${saved.skill_name}'${window.hydWords.josa(saved.skill_name, '을/를')} 저장했습니다`, { tone: 'ok' });
      st.form = null;
      if (f.kind === 'agent') st.pick.agents = saved.id; else st.pick.skills = saved.skill_name;
      st.busy = false;                              // 저장은 끝났다 — 다시 읽는 동안 연 새 폼의 저장 단추가 꺼진 채 남지 않게
      await load();
    } catch (e) {
      st.busy = false;                              // 다시 그리기 전에 풀어야 저장 단추가 살아 있다
      f.error = reason(e);
      const box = st.host.querySelector('[data-ag-detail]'); if (box) box.innerHTML = formHtml();
    } finally { st.busy = false; }
  }

  /* ---------- 담당 배정 (단계별 담당 에이전트, 역할 목록) ---------- */
  function assignHtml() {
    if (st.boardError) return `<div class="pane-none">${errBox('담당 배정을 읽지 못했습니다', st.boardError)}</div>`;
    const b = st.board;
    if (!b) return `<div class="pane-none">${loading()}</div>`;
    const closedWhy = [...new Set(b.steps.map(s => course().assignBlocked(s.definition_id)).filter(Boolean))];
    const rows = b.steps.map(s => {
      const cur = s.assigned ? s.assigned.agent_id : '';
      const opts = [`<option value="">기본 담당 (${esc(s.default_names.join(', '))})</option>`].concat(
        b.agents.filter(a => !s.default_agents.includes(a.id)).map(a => `<option value="${esc(a.id)}" ${a.id === cur ? 'selected' : ''}>${esc(a.name)}${a.origin === 'user' ? ' · 내가 만든 것' : ''}</option>`)).join('');
      const closed = course().assignBlocked(s.definition_id);
      return `<tr${s.assigned ? ' data-pick' : ''}><td>${esc(stepLabel(s))}</td><td>${esc(s.default_names.join(', '))}</td>` +
        `<td><span class="ag-map"><select class="select" data-map="${esc(s.definition_id)}|${esc(s.activity_id)}" aria-label="${esc(s.name)} 담당"${closed ? ' disabled' : ''}>${opts}</select>` +
        `${st.savedMap === s.definition_id + '|' + s.activity_id ? tag(st.savedNote, st.savedTone) : ''}</span></td></tr>`;
    }).join('');
    const steps = `<div class="panel-head"><div><h2>단계별 담당 AI 에이전트</h2><p>흐름 정의는 그대로 두고, 이 단계가 열릴 때 고른 에이전트가 맡습니다. 기본 담당으로 되돌리면 다음에 열리는 단계부터 기본으로 실행됩니다. <b>고르면 바로 저장됩니다.</b></p></div></div>` +
      `<div class="panel-sec">${closedWhy.map(w => `<div class="alert" role="status">${icon('lock')}<h2>지금은 일부 단계의 담당을 바꿀 수 없습니다</h2><section>${esc(w)}</section></div>`).join('')}` +
      (rows ? `<div class="table-container"><table class="table"><thead><tr><th>단계</th><th>기본 담당</th><th>지금 담당</th></tr></thead><tbody>${rows}</tbody></table></div>`
        : UI.empty('에이전트가 맡는 단계가 없습니다', '흐름을 등록하면 그 흐름의 AI 단계가 여기에 나옵니다.')) + `</div>`;
    // 쓰는 사람은 늘 이 PC의 담당자 한 명이고 모든 역할을 맡는다(새 역할도 서버 agent_authoring.create_role 이 담당자를 넣는다) — 사람을 넣고 빼는 칸이 없다.
    // 구성원이 한 명도 없는 역할은 그 사실을 그대로 보인다(그 역할의 사람 단계가 내가 할 일에 뜨지 않는다)
    const roles = (b.roles || []).map(r => {
      // G10: 포털에서 만든 역할은 표시하고 지울 수 있다(흐름 정의가 쓰면 서버가 사유와 함께 거절)
      const mine = r.origin === 'user';
      const none = r.members.length ? '' : `<div class="alert" data-variant="destructive" role="alert">${icon('circle-alert')}<h2>이 역할에 담당자가 연결되어 있지 않습니다</h2><section>이 역할의 사람 단계가 내가 할 일에 뜨지 않습니다. 시작 파일을 다시 실행해 업무 DB를 최신 판으로 맞추세요.</section></div>`;
      return `<li><div class="flow-ver"><b>${esc(UI.performers[r.id] || r.name)}</b>${mine ? originTag('user') : ''}` +
        (mine ? `<span class="flow-ver-acts"><button type="button" class="btn" data-variant="ghost" data-size="sm" data-role-del="${esc(r.id)}">${icon('trash-2')}지우기</button></span>` : '') + `</div>${none}</li>`;
    }).join('');
    const people = `<div class="panel-sec"><h3>${icon('user-check', 'ic-sm')}역할<span class="muted">모든 역할은 이 PC의 담당자가 맡습니다</span></h3>` +
      `<p class="muted">사람 단계는 그 단계의 역할 이름으로 처리 건의 「내가 할 일」에 뜹니다.</p>` +
      (roles ? `<ul class="flow-vers">${roles}</ul>` : UI.empty('역할이 없습니다', '아래에서 역할을 만듭니다.')) +
      `<fieldset class="fieldset ag-role-new"><legend>역할 만들기</legend><div role="group">` +
      UI.field({ label: '역할 이름', input: '<input data-role-name placeholder="내 흐름의 레인 이름과 같게">', hint: '흐름 화면에서 가져온 그림은 레인 이름이 역할 이름과 같으면 그 역할로 이어집니다.' }) +
      UI.field({ label: '키 (선택)', input: '<input data-role-key placeholder="예: s01-organizer">', hint: '흐름 정의가 이 역할을 가리킬 때 쓰는 영문 이름입니다. 비우면 자동으로 정해집니다.' }) +
      `</div><footer class="form-foot"><button type="button" class="btn" data-variant="outline" data-role-add>${icon('plus')}역할 만들기</button></footer></fieldset></div>`;
    return steps + people;
  }
  async function setMap(sel) {
    const [definition_id, activity_id] = sel.dataset.map.split('|');
    try {
      if (sel.value) await postJ(api('/api/agent-assignments'), { definition_id, activity_id, agent_id: sel.value, by: me() }, 'PUT');
      else await del(api(`/api/agent-assignments/${encodeURIComponent(definition_id)}/${encodeURIComponent(activity_id)}`));
      UI.toast(sel.value ? '담당을 바꿨습니다. 다음에 열리는 단계부터 적용됩니다.' : '기본 담당으로 되돌렸습니다.', { tone: 'ok' });
      st.savedMap = sel.dataset.map; st.savedNote = `저장됨 ${UI.time(new Date().toISOString())}`; st.savedTone = 'ok';      // 그 줄에 「저장됨」을 남긴다 — 고르는 순간 값이 조용히 바뀌지 않게
    } catch (e) { UI.toast(reason(e), { tone: 'neg', timeout: 8000 }); st.savedMap = sel.dataset.map; st.savedNote = '저장 안 됨'; st.savedTone = 'danger'; }
    await loadBoard(); await refreshAgents(); render();
  }
  async function refreshAgents() {
    try { st.agents = await getJ(api('/api/agents')); registerNames(st.agents); st.error = ''; } catch (e) { st.error = reason(e); }
  }

  /* ---------- 행동 ---------- */
  // 역할을 만들거나 지운 응답의 knowledge(서버 agent_authoring.sync_roles): 지식 지도에 바로 옮겼는지, 못 옮겼으면 서버가 준 까닭(1분 안에 다시 반영)을 그대로 말한다
  const roleKnowledge = (k, removed = false) => !k ? '' : k.synced ? (removed ? '지식 지도에서도 뺐습니다.' : '지식 지도에도 옮겨, 문서 · 조치 방법의 승인 역할로 바로 고를 수 있습니다.') : (k.reason || '지식 지도에는 아직 반영하지 못했습니다.');
  async function act(fn, ok) {
    try { const out = await fn(); if (ok) UI.toast(typeof ok === 'function' ? ok(out) : ok, { tone: 'ok' }); return out; }
    catch (e) { UI.toast(reason(e), { tone: 'neg', timeout: 8000 }); return null; }
  }
  async function cloneAgent(id, button) {
    const copy = await once('clone:' + id, button, () => act(() => postJ(api('/api/agents/' + encodeURIComponent(id) + '/clone'), {}), c => `'${c.username}'${window.hydWords.josa(c.username, '을/를')} 만들었습니다. 고친 뒤 저장하세요.`));
    if (!copy) return;
    st.pick.agents = copy.id;
    await load();
    await loadOptions();
    const d = await getJ(api('/api/agents/' + encodeURIComponent(copy.id)));
    openForm('agent', d);
    st.form.cloned = copy.id;      // 복제는 누르는 순간 사본이 저장된다 — 이 폼을 저장하지 않고 취소하면 그 사본을 지운다(목록에 「…사본」이 남지 않게)
    loadDetail();
  }
  async function deleteAgent(d) {
    if (!await UI.confirm({ title: `'${d.name}'${window.hydWords.josa(d.name, '을/를')} 지울까요?`, body: '단계 배정도 함께 지워지고, 열려 있는 그 에이전트의 단계는 기본 담당으로 돌아갑니다.', ok: '지우기', danger: true })) return;
    const out = await act(() => del(api('/api/agents/' + encodeURIComponent(d.id) + '?by=' + encodeURIComponent(me()))), o => `지웠습니다.${o.returned_tasks.length ? ` 열려 있던 단계 ${o.returned_tasks.length}건은 기본 담당으로 돌아갔습니다.` : ''}`);
    if (out) { st.pick.agents = null; await load(); }
  }
  async function deleteSkill(s) {
    if (!await UI.confirm({ title: `스킬 '${s.title}'${window.hydWords.josa(s.title, '을/를')} 지울까요?`, body: s.agents.length ? `붙은 에이전트 ${s.agents.length}개에서도 떨어집니다.` : '', ok: '지우기', danger: true })) return;
    const out = await act(() => del(api('/api/skills/' + encodeURIComponent(s.skill_name))), '지웠습니다');
    if (out) { st.pick.skills = null; await load(); }
  }

  /* ---------- 화면 ---------- */
  // 차례: 제목 · 한 문장 · 도구(주 단추 하나) → 왼쪽에 묶음 단추와 목록, 오른쪽에 상세 판(담당 배정은 판 하나) → 맨 아래 「관리에서 되돌리기」 한 줄(되돌리기는 관리 › 내 설정 한 곳)
  function render() {
    if (!st.host) return;
    const count = fn => (st.agents && st.loaded ? st.agents.filter(fn).length : null);      // 못 읽었으면 「0」을 적지 않는다
    const seg = [['agents', '에이전트', count(a => a.kind === 'agent')], ['skills', '스킬', st.skills && st.loaded ? st.skills.length : null], ['systems', '시스템 수행자', count(a => a.kind !== 'agent')], ['assign', '담당 배정', null]]
      .map(([k, l, c]) => `<button type="button" aria-pressed="${k === st.tab}" data-ag-tab="${k}">${esc(l)}${c != null ? `<span class="num">${c}</span>` : ''}</button>`).join('');
    // 주 단추는 화면에 하나: 폼을 쓰는 동안에는 폼의 [저장]이 주 단추라 새로 만들기 단추를 그리지 않는다
    const make = st.form ? '' : `<button type="button" class="btn" data-variant="outline" data-new-skill>${icon('file-text')}스킬 만들기</button><button type="button" class="btn" data-new-agent>${icon('plus')}새 에이전트</button>`;
    const body = st.tab === 'assign' ? `<div class="seg ag-seg" role="group" aria-label="보기">${seg}</div><section class="panel">${assignHtml()}</section>`
      : `<div class="split"><div class="pane-side"><div class="seg" role="group" aria-label="보기">${seg}</div><div class="rows" aria-label="목록">${listHtml()}</div></div><section class="panel" data-ag-detail aria-label="고른 항목"></section></div>`;
    st.host.innerHTML =
      UI.pageHead('agents', { sub: '에이전트는 흐름의 한 단계를 맡아 판단합니다. 방법은 스킬 문서가, 읽고 부를 것은 도구 서버가 정합니다.', tools: make, more: [{ act: 'reload', attrs: 'data-ag-reload' }] }) +
      (st.error ? `<div class="ag-error">${errBox('에이전트와 스킬 목록을 읽지 못했습니다', st.error)}</div>` : '') + body +
      UI.resetLink('agents', '내가 만든 에이전트 · 스킬 · 역할 · 담당 배정을');
  }
  function pick(tab, key) {
    st.tab = tab; st.pick[tab] = key; st.form = null;
    render(); loadDetail();
    const box = st.host.querySelector('[data-ag-detail]'); if (box) UI.revealDetail(box);
  }
  // 다른 화면으로 잇기: 맡은 단계 → 흐름 화면의 그 흐름, 도구 서버 → 도구 연결의 그 서버, 시험해 보기 → 질문하기에서 이 에이전트에게
  function go(tab, prepare) { prepare(); window.hydShell.navigate({ tab }); }
  async function onClick(e) {
    const t = e.target.closest('button');
    if (!t || !st.host.contains(t)) return;
    if (t.hasAttribute('data-ag-reload')) { st.form = null; return load(); }
    if (t.hasAttribute('data-retry')) return t.closest('[data-ag-detail]') ? loadDetail() : load();      // 오류 판의 [다시 시도]: 상세만 못 읽었으면 상세만 다시 읽는다
    if (t.hasAttribute('data-goto-assign')) { st.tab = 'assign'; st.form = null; render(); await loadBoard(); return render(); }
    if (t.dataset.agTab) { st.tab = t.dataset.agTab; st.form = null; if (st.tab === 'assign') { render(); await loadBoard(); } render(); return loadDetail(); }
    if (t.dataset.pickAgent) return pick(st.tab === 'systems' ? 'systems' : 'agents', t.dataset.pickAgent);
    if (t.dataset.pickSkill) return pick('skills', t.dataset.pickSkill);
    if (t.dataset.gotoAgent) return pick('agents', t.dataset.gotoAgent);
    if (t.dataset.skillDoc && st.detail) {      // 에이전트의 스킬 한 줄 → 아래 「스킬 문서」 칸이 그 스킬로 바뀐다
      st.doc[st.detail.id] = t.dataset.skillDoc;
      st.host.querySelectorAll('[data-skill-doc]').forEach(b => b.setAttribute('aria-expanded', String(b === t)));
      return drawSkillDoc();
    }
    if (t.dataset.gotoFlow) return go('flows', () => window.hydFlows.pick(t.dataset.gotoFlow));
    if (t.dataset.gotoServer) return go('mcp', () => window.hydMcp.pick(t.dataset.gotoServer));
    if (t.dataset.tryAgent) return go('ask', () => window.hydAsk.prefer(t.dataset.tryAgent));
    if (t.hasAttribute('data-new-agent')) { await loadOptions(); return openForm('agent'); }
    if (t.hasAttribute('data-new-skill')) return openForm('skill');
    if (t.hasAttribute('data-edit-agent') && st.detail) { await loadOptions(); return openForm('agent', st.detail); }
    if (t.hasAttribute('data-edit-skill') && st.detail) return openForm('skill', st.detail);
    if (t.dataset.clone) return cloneAgent(t.dataset.clone, t);
    if (t.hasAttribute('data-del-agent') && st.detail) return deleteAgent(st.detail);
    if (t.hasAttribute('data-del-skill') && st.detail) return deleteSkill(st.detail);
    if (t.hasAttribute('data-f-cancel')) {
      const cloned = st.form && st.form.cloned;
      st.form = null;
      if (cloned) { await act(() => del(api('/api/agents/' + encodeURIComponent(cloned) + '?by=' + encodeURIComponent(me()))), '저장하지 않아 사본을 지웠습니다'); st.pick.agents = null; return load(); }
      render(); return loadDetail();
    }
    if (t.hasAttribute('data-attach') && st.detail) {
      const sel = st.host.querySelector('[data-attach-to]'), skill = st.detail.skill_name;
      if (!sel || !sel.value) return;      // 고르지 않은 첫 항목에 붙지 않게(단추는 고르기 전까지 꺼져 있다)
      if (await once('attach:' + skill, t, () => act(() => postJ(api('/api/agents/' + encodeURIComponent(sel.value) + '/skills'), { skill_name: skill }), '붙였습니다'))) await load();
      return;
    }
    if (t.dataset.detach && st.detail) {
      const skill = st.detail.skill_name;
      if (await once('detach:' + t.dataset.detach + '/' + skill, t, () => act(() => del(api('/api/agents/' + encodeURIComponent(t.dataset.detach) + '/skills/' + encodeURIComponent(skill))), '뗐습니다'))) await load();
      return;
    }
    if (t.hasAttribute('data-role-add')) {
      const name = (st.host.querySelector('[data-role-name]') || {}).value || '', key = (st.host.querySelector('[data-role-key]') || {}).value || '';
      if (await once('role-add', t, () => act(() => postJ(api('/api/roles'), { name: name.trim(), key: key.trim() || null }), r => `역할 '${r.name}'${window.hydWords.josa(r.name, '을/를')} 만들었습니다. 이 역할도 이 PC의 담당자가 맡습니다. ${roleKnowledge(r.knowledge)}`))) { await loadBoard(); render(); }
      return;
    }
    if (t.dataset.roleDel) {
      const role = ((st.board && st.board.roles) || []).find(r => r.id === t.dataset.roleDel) || {};
      const roleName = role.name || UI.performers[t.dataset.roleDel] || '이름 없는 역할';
      if (!await UI.confirm({ title: `역할 '${roleName}'${window.hydWords.josa(roleName, '을/를')} 지울까요?`,
        body: '흐름 정의가 이 역할을 쓰거나 이 역할에 끝나지 않은 작업이 있으면 지울 수 없고, 그 까닭을 알려 줍니다. 지운 역할은 되살릴 수 없습니다.', ok: '지우기', danger: true })) return;
      if (await act(() => del(api('/api/roles/' + encodeURIComponent(t.dataset.roleDel))), r => `역할을 지웠습니다. ${roleKnowledge(r.knowledge, true)}`)) { await loadBoard(); render(); }
      return;
    }
    if (t.dataset.foldText) { st.open[t.dataset.foldText] = !st.open[t.dataset.foldText]; drawDetail(); }
  }
  function onChange(e) {
    if (e.target.matches('select[data-map]')) setMap(e.target);
    if (e.target.matches('select[data-attach-to]')) {      // 붙일 에이전트를 골라야 [내 에이전트에 붙이기]가 켜진다
      const b = st.host.querySelector('[data-attach]');
      const why = st.host.querySelector('[data-attach-why]');
      if (b) b.disabled = !e.target.value;
      if (why) why.hidden = !!e.target.value;
    }
  }
  function onSubmit(e) {
    if (!e.target.matches('[data-ag-form]')) return;
    e.preventDefault();
    submitForm(e.target);
  }
  function mount(el) {
    if (!el) return;
    if (st.host !== el) {
      course().onChange(() => { if (st.tab === 'assign') render(); });
      st.host = el;
      el.addEventListener('click', onClick);
      el.addEventListener('change', onChange);
      el.addEventListener('submit', onSubmit);
    }
    if (st.form) return;                 // 쓰는 중인 폼은 화면 전환으로 지우지 않는다
    render();
    load();
  }
  // 메뉴를 다시 열 때마다 다시 읽는다(셸 show) — 쓰는 중인 폼은 mount 가 그대로 둔다
  // pick(탭, 키): 다른 화면(도구 연결 · 질문하기)이 이 화면의 에이전트 · 스킬 하나를 고른 채 열 때 부른다
  // 관리 › 내 설정에서 되돌렸으면(이 화면이 그려져 있을 때) 고른 것 · 폼을 비우고 목록을 새로 읽는다
  window.addEventListener('hyd-config-reset', e => { if (!st.host || !['all', 'agents'].includes(e.detail.scope)) return; st.form = null; st.pick = { agents: null, skills: null, systems: null }; st.board = null; load(); });
  window.hydAgents = { mount, show: mount, pick: (tab, key) => { st.tab = tab; st.pick[tab] = key; st.form = null; } };
  // 학생이 만든 에이전트의 이름을 처리 건 · 작업함 화면에도 (화면을 열지 않아도). 실패하면 그 화면들은 이름 대신 식별자를 보인다 —
  // 이 화면(에이전트)을 열면 같은 목록을 다시 읽어 실패 사유가 화면에 보인다. 여기서는 콘솔에 남긴다(삼키지 않는다)
  if (typeof API !== 'undefined') getJ(api('/api/agents')).then(registerNames).catch(e => console.error('에이전트 이름 목록을 읽지 못했습니다:', e.message));
})();
