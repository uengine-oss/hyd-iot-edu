/* AI 에이전트 · 스킬 · 담당 배정 (U2 보기 + B1 직접 만들기).
   원천 하나: 에이전트 = users 표(is_agent), 스킬 = tenant_skills 표, 붙이기 = agent_skills 표, 단계 → 에이전트 = activity_agent_map,
   역할 → 사람 = role_members. 워커는 실행마다 같은 행을 읽는다(procsvc/agents_store.agent_settings) — 여기서 고친 것이 다음 실행에 쓰인다.
   기본(시드) 에이전트 · 스킬 · 업무분장은 보호: 고치기 · 지우기 대신 "복제해서 고치기". 내가 만든 것은 "내가 만든" 표시, "기준으로 되돌리기"로 지움.
   API: 읽기 GET /api/agents · /api/agents/{id} · /api/skills · /api/skills/{name} (agents_api.py),
        쓰기 POST·PUT·DELETE /api/agents · /api/skills · /api/agent-assignments · /api/role-members · POST /api/agents/reset (agent_authoring_api.py).
   레이아웃: process-gpt-vue3 AgentChatInfo.vue(목표 → 성격 → 도구 → 스킬 → 모델) · AgentField.vue:64-170(편집 폼) · SkillDetail.vue(사용 중 에이전트).
   셸(U7)은 window.hydAgents.mount(el) 로 아무 컨테이너에나 그릴 수 있다. */
(function () {
  const SERVER_WORDS = { neo4j: '지식 그래프', enterprise: '업무 DB', 'hyd-dmn': '판단 규칙 · 시계열' };
  const MODEL_FROM = { activity: '단계 설정', agent: '에이전트 설정' };
  const TOOLS_FROM = { agent: '에이전트 설정', activity: '단계 설정', 'agent+activity': '에이전트 도구 중 단계가 허용한 것' };
  const SHORT = 80;
  const st = { host: null, tab: 'agents', agents: null, skills: null, pick: { agents: null, skills: null }, detail: null, error: '', open: {}, seq: 0,
    form: null, options: null, board: null, boardError: '', busy: false };

  const serverName = (name, description) => description || SERVER_WORDS[name] || name;
  const modelText = m => m || '실행기 기본 모델';
  const api = path => API.process + path;
  const del = url => requestJ(url, { method: 'DELETE' });
  const mineChip = o => o === 'user' ? UI.chipText('내가 만든', 'success') : UI.chipText('기본', 'neutral');
  function reason(e) {
    if (e && e.status === 409 && /legacy mode/.test(e.message || '')) return '처리 엔진이 처리 건 모드로 켜져 있지 않아 에이전트 설정을 읽을 수 없습니다. 강의 배포 설정으로 처리 엔진을 다시 켜야 합니다.';
    if (e && e.status === 404 && !/[가-힣]/.test(e.message || '')) return '찾을 수 없습니다. 지웠거나 이름이 바뀌었을 수 있습니다. 다시 읽어 보세요.';
    return (e && e.message) || '처리 엔진에 연결할 수 없습니다';
  }
  function longText(key, text) {
    const t = String(text || '');
    if (t.length <= SHORT || st.open[key]) return esc(t) + (t.length > SHORT ? ` <button type="button" class="btn small" data-fold-text="${esc(key)}">접기</button>` : '');
    return esc(t.slice(0, SHORT)) + '… ' + `<button type="button" class="btn small" data-fold-text="${esc(key)}">펼치기</button>`;
  }
  const clip = (t, n = 48) => (t.length > n ? t.slice(0, n) + '…' : t);
  const stepLabel = s => `${s.definition_name || UI.defName(s.definition_id)} · ${UI.flowName(s.name)}`;   // 정의에 등록된 이름 먼저(영문 id 노출 0)
  const chips = (items, tone = 'neutral') => items.length ? items.map(t => UI.chipText(t, tone)).join(' ') : '<span class="muted">없음</span>';
  function checkChip(c) {
    if (!c) return '';
    if (c.error) return ' ' + UI.chipText('검사 상태 모름', 'warning');
    if (c.ok === true || c.status === 'ok' || c.status === 'passed') return ' ' + UI.chipText('연결 확인됨', 'success');
    if (c.ok === false || c.status === 'failed' || c.status === 'error') return ' ' + UI.chipText('연결 실패', 'danger');
    return '';
  }

  /* ---------- 읽기 ---------- */
  async function load() {
    const seq = ++st.seq;
    try {
      const [agents, skills] = await Promise.all([getJ(api('/api/agents')), getJ(api('/api/skills'))]);
      if (seq !== st.seq) return;
      st.agents = agents; st.skills = skills; st.error = '';
      registerNames(agents);
      if (st.pick.agents && !agents.some(a => a.id === st.pick.agents)) st.pick.agents = null;
      if (st.pick.skills && !skills.some(s => s.skill_name === st.pick.skills)) st.pick.skills = null;
      if (!st.pick.agents && agents.length) st.pick.agents = agents[0].id;
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
    if (st.form) { box.innerHTML = formHtml(); return; }
    const key = st.tab === 'agents' ? st.pick.agents : st.pick.skills;
    if (!key) { box.innerHTML = emptyDetail(); return; }
    const url = st.tab === 'agents' ? '/api/agents/' + encodeURIComponent(key) : '/api/skills/' + encodeURIComponent(key);
    const tab = st.tab;
    box.innerHTML = UI.empty('불러오는 중', '', 'compact');
    try {
      const d = await getJ(api(url));
      if (tab !== st.tab || key !== (tab === 'agents' ? st.pick.agents : st.pick.skills) || st.form) return;
      st.detail = d;
      box.innerHTML = tab === 'agents' ? agentDetail(d) : skillDetail(d);
    } catch (e) {
      box.innerHTML = `<div class="neg" role="status">${esc(reason(e))}</div>`;
    }
  }
  function emptyDetail() {
    return st.tab === 'agents'
      ? UI.empty('에이전트가 없습니다', '"새 에이전트"로 만들거나 랩업에서 users 표에 넣으면 여기에 나타납니다.')
      : UI.empty('아직 스킬이 없습니다', '"새 스킬"로 SKILL.md 를 쓰거나 랩업에서 tenant_skills 표에 넣으면 여기에 나타납니다.');
  }

  /* ---------- 목록 ---------- */
  function agentItem(a) {
    const sel = a.id === st.pick.agents && !st.form ? ' sel' : '';
    const agentSteps = a.steps.filter(s => s.agent).length;
    const count = a.kind === 'agent' ? `맡은 단계 ${agentSteps} · 도구 ${a.tools.length} · 스킬 ${a.skills.length}` : `맡은 단계 ${a.steps.length}`;
    return `<div class="item${sel}" role="button" tabindex="0" data-pick-agent="${esc(a.id)}" title="${esc(a.name)}">` +
      `<div class="row"><strong>${esc(a.name)}</strong>${a.kind === 'agent' ? mineChip(a.origin) : UI.chipText('시스템 수행자', 'neutral')}</div>` +
      `<span class="sub">${esc(clip(a.goal || a.role || '목표가 적혀 있지 않습니다'))}</span><span class="sub">${esc(count)}</span></div>`;
  }
  function skillItem(s) {
    const sel = s.skill_name === st.pick.skills && !st.form ? ' sel' : '';
    const who = s.agents.length ? s.agents.map(a => a.name).join(', ') : '붙은 에이전트 없음';
    return `<div class="item${sel}" role="button" tabindex="0" data-pick-skill="${esc(s.skill_name)}">` +
      `<div class="row"><strong>${esc(s.title)}</strong>${mineChip(s.origin)}${s.agents.length ? '' : UI.chipText('미배정', 'warning')}</div>` +
      `<span class="sub">${esc(s.description || '설명 없음')}</span><span class="sub">${esc(who)}</span></div>`;
  }
  function listHtml() {
    if (st.tab === 'agents') {
      const agents = (st.agents || []).filter(a => a.kind === 'agent'), systems = (st.agents || []).filter(a => a.kind !== 'agent');
      return `<button type="button" class="btn primary small" data-new-agent style="width:100%;margin-bottom:var(--s2)">새 에이전트</button>` +
        (agents.length ? agents.map(agentItem).join('') : UI.empty('AI 에이전트가 없습니다', '', 'compact')) +
        (systems.length ? UI.fold(`시스템 수행자 <span class="chip tone-neutral sm">${systems.length}</span>`, systems.map(agentItem).join(''),
          { open: systems.some(a => a.id === st.pick.agents), cls: 'small' }) : '');
    }
    return `<button type="button" class="btn primary small" data-new-skill style="width:100%;margin-bottom:var(--s2)">새 스킬</button>` +
      ((st.skills || []).length ? st.skills.map(skillItem).join('') : UI.empty('아직 스킬이 없습니다', '', 'compact'));
  }

  /* ---------- 에이전트 상세 (요약 먼저, 실행 설정·지시문은 펼침) ---------- */
  function agentActions(d) {
    if (d.kind !== 'agent') return '';
    if (!d.editable) return `<button type="button" class="btn primary small" data-clone="${esc(d.id)}">복제해서 고치기</button>`;
    return `<button type="button" class="btn primary small" data-edit-agent>고치기</button> <button type="button" class="btn small" data-clone="${esc(d.id)}">복제</button> ` +
      `<button type="button" class="btn danger small" data-del-agent>지우기</button>`;
  }
  function agentDetail(d) {
    const isAgent = d.kind === 'agent';
    const toolChips = d.tools.length ? d.tools.map(t => `<span class="chip tone-${t.registered ? 'success' : 'danger'}" title="${esc(t.name)}">${esc(serverName(t.name, t.description))}${t.registered ? '' : ' · 등록 안 됨'}</span>`).join(' ')
      : `<span class="muted">${isAgent ? '지정 없음 — 등록된 도구 서버를 모두 씁니다' : '없음'}</span>`;
    const skillBtns = d.skills.length ? d.skills.map(s => s.found
      ? `<button type="button" class="btn small" data-goto-skill="${esc(s.skill_name)}" title="${esc(s.description)}">${esc(s.title)}</button>`
      : `<span class="chip tone-danger" title="${esc(s.skill_name)}">본문 없는 스킬</span>`).join(' ') : '<span class="muted">없음</span>';
    const steps = d.steps.length ? d.steps.map(s => UI.chipText(stepLabel(s) + (s.assigned ? ' (배정)' : ''), s.assigned ? 'accent' : 'neutral')).join(' ')
      : '<span class="muted">맡은 단계가 없습니다. "담당 배정" 탭에서 단계를 맡기면 그 단계가 이 에이전트로 실행됩니다.</span>';
    const rows = [['역할', esc(d.role || '–')], ['목표', longText('goal:' + d.id, d.goal || '–')]];
    if (isAgent) rows.push(['성격 · 말투', d.persona ? longText('persona:' + d.id, d.persona) : '<span class="muted">적혀 있지 않습니다</span>'],
      ['모델', esc(modelText(d.model))], ['쓰는 도구', toolChips], ['스킬', skillBtns]);
    rows.push(['맡은 단계', steps]);
    const summary = `<dl class="meta-list" style="grid-template-columns:1fr">${rows.map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${v}</dd></div>`).join('')}</dl>`;
    const note = !isAgent ? '정해진 업무를 하는 시스템입니다. 에이전트 설정은 쓰지 않습니다.'
      : d.editable ? '내가 만든 에이전트입니다. 고친 내용은 다음 실행부터 쓰입니다.'
        : '기본 에이전트는 수업 기준이라 고칠 수 없습니다. "복제해서 고치기"로 사본을 만들어 고치세요.';
    let html = `<div class="detail-head"><div class="row"><h2>${esc(d.name)}</h2>${isAgent ? mineChip(d.origin) : UI.chipText('시스템 수행자', 'neutral')}</div>` +
      `<div class="sub">${esc(note)}</div></div>` +
      UI.card({ title: '요약', body: summary, actions: agentActions(d) });
    if (isAgent) {
      const run = d.run || {};
      const stepRows = (run.steps || []).map(s => {
        const x = s.settings;
        const tools = x.tools == null ? '등록된 도구 서버 전부' : x.tools.length ? x.tools.map(t => serverName(t)).join(', ') : '없음(겹치는 도구가 없음)';
        return `<tr><td>${esc(UI.flowName(s.name))}</td><td>${esc(modelText(x.model))}${x.model_source ? `<br><span class="muted">${esc(MODEL_FROM[x.model_source] || '')}</span>` : ''}</td>` +
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
    const mineAgents = (st.agents || []).filter(a => a.kind === 'agent' && a.editable);
    const attachedIds = new Set(s.agents.map(a => a.id));
    const agents = s.agents.length ? s.agents.map(a => {
      const own = mineAgents.some(m => m.id === a.id);
      return `<span class="row" style="display:inline-flex;gap:4px"><button type="button" class="btn small" data-goto-agent="${esc(a.id)}">${esc(a.name)}</button>` +
        (own ? `<button type="button" class="btn small" data-detach="${esc(a.id)}" title="이 에이전트에서 떼기">떼기</button>` : '') + '</span>';
    }).join(' ') : '<span class="muted">붙은 에이전트가 없습니다. 붙이지 않은 스킬은 어떤 실행에도 들어가지 않습니다.</span>';
    const can = mineAgents.filter(a => !attachedIds.has(a.id));
    const attach = can.length ? `<div class="row" style="gap:var(--s2);margin-top:var(--s2)"><select data-attach-to aria-label="붙일 에이전트">${can.map(a => `<option value="${esc(a.id)}">${esc(a.name)}</option>`).join('')}</select>` +
      `<button type="button" class="btn small" data-attach>내 에이전트에 붙이기</button></div>`
      : `<p class="muted">붙일 수 있는 내 에이전트가 없습니다. 기본 에이전트에는 붙일 수 없으니 복제해서 붙이세요.</p>`;
    const steps = s.steps.length ? chips(s.steps.map(stepLabel)) : '<span class="muted">없음</span>';
    const summary = `<dl class="meta-list" style="grid-template-columns:1fr">` +
      [['설명', esc(s.description || '–')], ['붙은 에이전트', agents + attach], ['선언한 단계', steps], ['고친 시각', esc(s.updated_at ? UI.dateTime(s.updated_at) : '–')]]
        .map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${v}</dd></div>`).join('') + '</dl>';
    const mine = s.origin === 'user';
    const actions = mine ? `<button type="button" class="btn primary small" data-edit-skill>고치기</button> <button type="button" class="btn danger small" data-del-skill>지우기</button>` : '';
    return `<div class="detail-head"><div class="row"><h2>${esc(s.title)}</h2>${mineChip(s.origin)}</div>` +
      `<div class="sub">${mine ? '붙은 에이전트가 실행될 때 작업 폴더에 이 문서가 SKILL.md 로 들어갑니다.' : '기본 스킬은 수업 기준이라 고칠 수 없습니다. 새 스킬을 만들어 쓰세요.'}</div></div>` +
      UI.card({ title: '요약', body: summary, actions }) +
      UI.card({ title: '스킬 문서', body: `<pre style="max-height:480px;overflow:auto">${esc(s.content || '')}</pre>` }) +
      UI.metaFold([['폴더 이름', `<span class="mono">${esc(s.skill_name)}</span>`], ['저장 위치', '스킬 저장소(tenant_skills 표)'], ['길이', esc((s.content || '').length.toLocaleString('ko-KR') + '자')]]);
  }

  /* ---------- 만들기 · 고치기 폼 ---------- */
  function openForm(kind, d) {
    if (kind === 'agent') {
      st.form = { kind, id: d ? d.id : null, error: '', draft: d ? { name: d.name, role: d.role || '', goal: d.goal || '', persona: d.persona || '', model: d.model || '',
        tools: d.tools.filter(t => t.registered !== false).map(t => t.name || t), skills: d.skills.map(s => s.skill_name || s) }
        : { name: '', role: '', goal: '', persona: '', model: '', tools: [], skills: [] } };
    } else {
      st.form = { kind, id: d ? d.skill_name : null, error: '', draft: d ? { skill_name: d.skill_name, description: d.description || '', content: d.content || '' }
        : { skill_name: '', description: '', content: '---\nname: \ndescription: \n---\n\n# 제목\n\n1. 먼저 조회할 값과 도구\n2. 판정 기준\n3. 모를 때 적는 법\n' } };
    }
    render(); loadDetail();
    const box = st.host.querySelector('[data-ag-detail]'); if (box) UI.revealDetail(box);
  }
  function formHtml() {
    const f = st.form, d = f.draft, o = st.options || { servers: [], skills: [], models: [] };
    if (f.kind === 'agent') {
      const tools = o.servers.length ? o.servers.map(s => `<label class="check"><input type="checkbox" data-f-tool value="${esc(s.name)}" ${d.tools.includes(s.name) ? 'checked' : ''}> ` +
        `<span>${esc(serverName(s.name, s.description))}${checkChip(s.check)}</span></label>`).join('') : '<span class="muted">등록된 도구 서버가 없습니다</span>';
      const skills = o.skills.length ? o.skills.map(s => `<label class="check"><input type="checkbox" data-f-skill value="${esc(s.skill_name)}" ${d.skills.includes(s.skill_name) ? 'checked' : ''}> ` +
        `<span>${esc(s.description || s.skill_name)} ${mineChip(s.origin)}</span></label>`).join('') : '<span class="muted">아직 스킬이 없습니다 — 스킬 탭에서 먼저 만드세요</span>';
      return `<div class="detail-head"><div class="row"><h2>${f.id ? '에이전트 고치기' : '새 에이전트'}</h2>${UI.chipText('내가 만든', 'success')}</div>` +
        `<div class="sub">저장하면 다음 실행부터 이 설정으로 실행됩니다. 단계를 맡기려면 저장 뒤 "담당 배정" 탭에서 고르세요.</div></div>` +
        `<form data-ag-form>` +
        UI.section('프로필', UI.field({ label: '이름', required: true, input: `<input data-f="name" maxlength="60" value="${esc(d.name)}">` }) +
          UI.field({ label: '역할', input: `<input data-f="role" maxlength="200" value="${esc(d.role)}" placeholder="예: 쿨러 열화를 먼저 본다">` }) +
          UI.field({ label: '목표', required: true, input: `<textarea data-f="goal" maxlength="500">${esc(d.goal)}</textarea>`, hint: '이 에이전트가 무엇을 해내야 하는지 한 문장' }) +
          UI.field({ label: '성격 · 말투', input: `<textarea data-f="persona" maxlength="2000">${esc(d.persona)}</textarea>` }) +
          UI.field({ label: '모델', input: `<input data-f="model" list="agModels" value="${esc(d.model)}"><datalist id="agModels">${o.models.map(m => `<option value="${esc(m)}">`).join('')}</datalist>`, hint: '비우면 실행기 기본 모델' })) +
        UI.section('쓸 도구 (등록된 MCP 서버)', `<div>${tools}<p class="field-hint">하나도 고르지 않으면 등록된 서버를 모두 씁니다.</p></div>`) +
        UI.section('스킬', `<div>${skills}</div>`) +
        UI.actions(`<button type="button" class="btn" data-f-cancel>취소</button><button type="submit" class="btn primary" ${st.busy ? 'disabled' : ''}>저장</button>`, f.error) +
        `</form>`;
    }
    return `<div class="detail-head"><div class="row"><h2>${f.id ? '스킬 고치기' : '새 스킬'}</h2>${UI.chipText('내가 만든', 'success')}</div>` +
      `<div class="sub">SKILL.md 한 장 = 에이전트의 작업 요령. 붙은 에이전트가 실행될 때 작업 폴더에 이 문서가 들어갑니다.</div></div>` +
      `<form data-ag-form>` +
      UI.section('', UI.field({ label: '폴더 이름', required: true, input: `<input data-f="skill_name" class="mono" maxlength="64" value="${esc(d.skill_name)}" ${f.id ? 'disabled' : ''} placeholder="예: cooler-check">`,
        hint: '영문 소문자 · 숫자 · 하이픈. 문서 머리의 name 과 같아야 합니다' }) +
        UI.field({ label: '설명 한 줄', input: `<input data-f="description" maxlength="300" value="${esc(d.description)}">`, hint: '비우면 문서 머리의 description 이나 첫 제목을 씁니다' }) +
        UI.field({ label: 'SKILL.md', required: true, input: `<textarea data-f="content" class="mono" rows="14">${esc(d.content)}</textarea>` })) +
      UI.actions(`<button type="button" class="btn" data-f-cancel>취소</button><button type="submit" class="btn primary" ${st.busy ? 'disabled' : ''}>저장</button>`, f.error) +
      `</form>`;
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
    try {
      let saved;
      if (f.kind === 'agent') saved = f.id ? await postJ(api('/api/agents/' + encodeURIComponent(f.id)), d, 'PUT') : await postJ(api('/api/agents'), d);
      else saved = f.id ? await postJ(api('/api/skills/' + encodeURIComponent(f.id)), d, 'PUT') : await postJ(api('/api/skills'), d);
      UI.toast(f.kind === 'agent' ? `에이전트 '${saved.username}'을(를) 저장했습니다` : `스킬 '${saved.skill_name}'을(를) 저장했습니다`, { tone: 'ok' });
      st.form = null;
      if (f.kind === 'agent') st.pick.agents = saved.id; else st.pick.skills = saved.skill_name;
      await load();
    } catch (e) {
      st.busy = false;                              // 다시 그리기 전에 풀어야 저장 단추가 살아 있다
      f.error = reason(e);
      const box = st.host.querySelector('[data-ag-detail]'); if (box) box.innerHTML = formHtml();
    } finally { st.busy = false; }
  }

  /* ---------- 담당 배정 (단계 → 에이전트, 역할 → 사람) ---------- */
  function assignHtml() {
    if (st.boardError) return `<div class="neg" role="status">${esc(st.boardError)}</div>`;
    const b = st.board;
    if (!b) return UI.empty('불러오는 중', '', 'compact');
    const rows = b.steps.map(s => {
      const cur = s.assigned ? s.assigned.agent_id : '';
      const opts = [`<option value="">기본 담당 (${esc(s.default_names.join(', '))})</option>`].concat(
        b.agents.filter(a => !s.default_agents.includes(a.id)).map(a => `<option value="${esc(a.id)}" ${a.id === cur ? 'selected' : ''}>${esc(a.name)}${a.origin === 'user' ? ' · 내가 만든' : ''}</option>`)).join('');
      return `<tr><td>${esc(stepLabel(s))}</td><td>${esc(s.default_names.join(', '))}</td>` +
        `<td><select data-map="${esc(s.definition_id)}|${esc(s.activity_id)}" aria-label="${esc(s.name)} 담당">${opts}</select></td>` +
        `<td>${s.assigned ? UI.chipText('배정됨', 'accent') : UI.chipText('기본', 'neutral')}</td></tr>`;
    }).join('');
    const steps = UI.card({ title: '단계 → 담당 에이전트',
      body: `<p class="muted">흐름 정의는 그대로 두고, 이 단계가 열릴 때 고른 에이전트가 맡습니다. 기본 담당으로 되돌리면 다음에 열리는 단계부터 기본으로 실행됩니다.</p>` +
        (b.bridge_note ? `<p class="chip tone-warning" role="note" style="white-space:normal;display:block;line-height:1.5;padding:6px 10px;height:auto">${esc(b.bridge_note)}</p>` : '') +
        (rows ? `<div class="table-scroll"><table class="compact-table"><thead><tr><th>단계</th><th>기본 담당</th><th>지금 담당</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>`
          : UI.empty('에이전트가 맡는 단계가 없습니다', '', 'compact')) });
    const roles = (b.roles || []).map(r => {
      const ids = new Set(r.members.map(m => m.id));
      const members = r.members.length ? r.members.map(m => `<span class="chip tone-${m.origin === 'user' ? 'success' : 'neutral'}">${esc(m.name)}${m.origin === 'user'
        ? `<button type="button" class="chip-x" data-unmember="${esc(r.id)}|${esc(m.id)}" aria-label="${esc(m.name)} 빼기" title="빼기">×</button>` : ''}</span>`).join(' ')
        : '<span class="neg">아무도 없음 — 이 역할의 사람 단계는 누구의 작업함에도 뜨지 않습니다</span>';
      const can = (b.people || []).filter(p => !ids.has(p.id));
      const add = can.length ? `<select data-member-pick="${esc(r.id)}" aria-label="${esc(UI.performers[r.id] || r.name)}에 넣을 사람">${can.map(p => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('')}</select>` +
        ` <button type="button" class="btn small" data-member-add="${esc(r.id)}">넣기</button>` : '';
      const rule = r.members.length === 1 ? '한 명 → 그 사람에게 바로 배정' : r.members.length > 1 ? '여러 명 → 역할 공용' : '';
      // G10: 포털에서 만든 역할은 표시하고 지울 수 있다(흐름 정의가 쓰면 서버가 사유와 함께 거절)
      const mine = r.origin === 'user' ? ` ${UI.chipText('내가 만든', 'accent')} <button type="button" class="btn small" data-role-del="${esc(r.id)}">지우기</button>` : '';
      return `<tr><td>${esc(UI.performers[r.id] || r.name)}${mine}</td><td>${members}${rule ? `<br><span class="muted">${esc(rule)}</span>` : ''}</td><td>${add}</td></tr>`;
    }).join('');
    const newRole = `<div class="row-wrap" role="group" aria-label="역할 만들기"><input data-role-name placeholder="역할 이름 (내 흐름의 레인 이름과 같게)" aria-label="새 역할 이름">` +
      `<input data-role-key placeholder="키 (선택, 예: s01-organizer)" aria-label="새 역할 키"><button type="button" class="btn small" data-role-add>역할 만들기</button></div>` +
      `<p class="muted">흐름 가져오기는 레인 이름이 역할 이름과 같으면 그 역할로 잇습니다. 만든 역할에 사람을 넣어야 그 사람 작업함에 뜹니다.</p>`;
    const people = UI.card({ title: '역할 → 사람 (업무분장)',
      body: `<p class="muted">기본 업무분장은 뺄 수 없고, 넣은 사람만 뺄 수 있습니다. 사람 단계는 이 표로 담당자가 정해집니다.</p>` +
        (roles ? `<div class="table-scroll"><table class="compact-table"><thead><tr><th>역할</th><th>사람</th><th>넣기</th></tr></thead><tbody>${roles}</tbody></table></div>` : UI.empty('역할이 없습니다', '', 'compact')) +
        UI.fold('역할 만들기', newRole, { cls: 'plain' }) });
    return steps + people;
  }
  async function setMap(sel) {
    const [definition_id, activity_id] = sel.dataset.map.split('|');
    try {
      if (sel.value) await postJ(api('/api/agent-assignments'), { definition_id, activity_id, agent_id: sel.value }, 'PUT');
      else await del(api(`/api/agent-assignments/${encodeURIComponent(definition_id)}/${encodeURIComponent(activity_id)}`));
      UI.toast(sel.value ? '담당을 바꿨습니다 — 다음에 열리는 단계부터 적용됩니다' : '기본 담당으로 되돌렸습니다', { tone: 'ok' });
    } catch (e) { UI.toast(reason(e), { tone: 'neg', timeout: 8000 }); }
    await loadBoard(); await refreshAgents(); render();
  }
  async function refreshAgents() {
    try { st.agents = await getJ(api('/api/agents')); registerNames(st.agents); } catch (e) { /* 목록 오류는 다음 다시 읽기에서 */ }
  }
  async function member(role_id, user_id, add) {
    try {
      if (add) await postJ(api('/api/role-members'), { role_id, user_id });
      else await del(api(`/api/role-members?role_id=${encodeURIComponent(role_id)}&user_id=${encodeURIComponent(user_id)}`));
      UI.toast(add ? '역할에 넣었습니다' : '역할에서 뺐습니다', { tone: 'ok' });
    } catch (e) { UI.toast(reason(e), { tone: 'neg', timeout: 8000 }); }
    await loadBoard(); render();
  }

  /* ---------- 행동 ---------- */
  async function act(fn, ok) {
    try { const out = await fn(); if (ok) UI.toast(typeof ok === 'function' ? ok(out) : ok, { tone: 'ok' }); return out; }
    catch (e) { UI.toast(reason(e), { tone: 'neg', timeout: 8000 }); return null; }
  }
  async function cloneAgent(id) {
    const copy = await act(() => postJ(api('/api/agents/' + encodeURIComponent(id) + '/clone'), {}), c => `'${c.username}'을(를) 만들었습니다 — 고친 뒤 저장하세요`);
    if (!copy) return;
    st.pick.agents = copy.id;
    await load();
    await loadOptions();
    const d = await getJ(api('/api/agents/' + encodeURIComponent(copy.id)));
    openForm('agent', d);
  }
  async function deleteAgent(d) {
    if (!await UI.confirm({ title: `'${d.name}'을(를) 지울까요?`, body: '단계 배정도 함께 지워지고, 열려 있는 그 에이전트의 단계는 기본 담당으로 돌아갑니다.', ok: '지우기', danger: true })) return;
    const out = await act(() => del(api('/api/agents/' + encodeURIComponent(d.id))), o => `지웠습니다${o.returned_tasks.length ? ` · 열린 단계 ${o.returned_tasks.length}건은 기본 담당으로` : ''}`);
    if (out) { st.pick.agents = null; await load(); }
  }
  async function deleteSkill(s) {
    if (!await UI.confirm({ title: `스킬 '${s.title}'을(를) 지울까요?`, body: s.agents.length ? `붙은 에이전트 ${s.agents.length}개에서도 떨어집니다.` : '', ok: '지우기', danger: true })) return;
    const out = await act(() => del(api('/api/skills/' + encodeURIComponent(s.skill_name))), '지웠습니다');
    if (out) { st.pick.skills = null; await load(); }
  }
  async function resetAll() {
    if (!await UI.confirm({ title: '기준으로 되돌릴까요?', body: '내가 만든 에이전트 · 스킬 · 단계 배정 · 넣은 업무분장을 모두 지웁니다. 기본 에이전트와 기본 업무분장은 그대로입니다.', ok: '되돌리기', danger: true })) return;
    const out = await act(() => postJ(api('/api/agents/reset'), {}),
      o => `되돌렸습니다 — 에이전트 ${o.agents} · 스킬 ${o.skills} · 단계 배정 ${o.assignments} · 업무분장 ${o.role_members}` + (o.returned_tasks.length ? ` · 열린 단계 ${o.returned_tasks.length}건 기본 담당으로` : ''));
    if (out) { st.form = null; st.pick = { agents: null, skills: null }; st.board = null; await load(); }
  }

  /* ---------- 화면 ---------- */
  function render() {
    if (!st.host) return;
    const n = st.agents ? st.agents.filter(a => a.kind === 'agent').length : null, m = st.skills ? st.skills.length : null;
    const body = st.tab === 'assign' ? assignHtml()
      : `<div class="split"><div><div class="list">${st.agents ? listHtml() : UI.empty('불러오는 중', '', 'compact')}</div></div><div class="detail" data-ag-detail></div></div>`;
    st.host.innerHTML =
      `<div class="page-head"><h1>AI 에이전트</h1><div class="page-tools"><button type="button" class="btn small" data-ag-reload>다시 읽기</button>` +
      `<button type="button" class="btn small" data-ag-reset title="내가 만든 것만 지웁니다">기준으로 되돌리기</button></div></div>` +
      `<p class="muted">에이전트 · 스킬을 만들고 단계에 맡겨 보세요. 기본 에이전트는 보호되어 복제해서 고칩니다. 랩업(Claude Code)에서 넣은 것도 다시 읽으면 함께 보입니다.</p>` +
      (st.error ? `<div class="neg" role="status">${esc(st.error)}</div>` : '') +
      UI.tabs([['agents', '에이전트', n], ['skills', '스킬', m], ['assign', '담당 배정']], st.tab, 'data-ag-tab') + body;
  }
  function pick(tab, key) {
    st.tab = tab; st.pick[tab] = key; st.form = null;
    render(); loadDetail();
    const box = st.host.querySelector('[data-ag-detail]'); if (box) UI.revealDetail(box);
  }
  async function onClick(e) {
    const t = e.target.closest('button, [data-pick-agent], [data-pick-skill]');
    if (!t || !st.host.contains(t)) return;
    if (t.hasAttribute('data-ag-reload')) { st.form = null; return load(); }
    if (t.hasAttribute('data-ag-reset')) return resetAll();
    if (t.dataset.agTab) { st.tab = t.dataset.agTab; st.form = null; if (st.tab === 'assign') { render(); await loadBoard(); } render(); return loadDetail(); }
    if (t.dataset.pickAgent) return pick('agents', t.dataset.pickAgent);
    if (t.dataset.pickSkill) return pick('skills', t.dataset.pickSkill);
    if (t.dataset.gotoSkill) return pick('skills', t.dataset.gotoSkill);
    if (t.dataset.gotoAgent) return pick('agents', t.dataset.gotoAgent);
    if (t.hasAttribute('data-new-agent')) { await loadOptions(); return openForm('agent'); }
    if (t.hasAttribute('data-new-skill')) return openForm('skill');
    if (t.hasAttribute('data-edit-agent') && st.detail) { await loadOptions(); return openForm('agent', st.detail); }
    if (t.hasAttribute('data-edit-skill') && st.detail) return openForm('skill', st.detail);
    if (t.dataset.clone) return cloneAgent(t.dataset.clone);
    if (t.hasAttribute('data-del-agent') && st.detail) return deleteAgent(st.detail);
    if (t.hasAttribute('data-del-skill') && st.detail) return deleteSkill(st.detail);
    if (t.hasAttribute('data-f-cancel')) { st.form = null; render(); return loadDetail(); }
    if (t.hasAttribute('data-attach') && st.detail) {
      const sel = st.host.querySelector('[data-attach-to]');
      if (sel && await act(() => postJ(api('/api/agents/' + encodeURIComponent(sel.value) + '/skills'), { skill_name: st.detail.skill_name }), '붙였습니다')) await load();
      return;
    }
    if (t.dataset.detach && st.detail) {
      if (await act(() => del(api('/api/agents/' + encodeURIComponent(t.dataset.detach) + '/skills/' + encodeURIComponent(st.detail.skill_name))), '뗐습니다')) await load();
      return;
    }
    if (t.dataset.memberAdd) { const sel = st.host.querySelector(`[data-member-pick="${CSS.escape(t.dataset.memberAdd)}"]`); return sel && member(t.dataset.memberAdd, sel.value, true); }
    if (t.dataset.unmember) { const [r, u] = t.dataset.unmember.split('|'); return member(r, u, false); }
    if (t.hasAttribute('data-role-add')) {
      const name = (st.host.querySelector('[data-role-name]') || {}).value || '', key = (st.host.querySelector('[data-role-key]') || {}).value || '';
      if (await act(() => postJ(api('/api/roles'), { name: name.trim(), key: key.trim() || null }), r => `역할 '${r.name}'(${r.id})을 만들었습니다 — 사람을 넣으세요`)) { await loadBoard(); render(); }
      return;
    }
    if (t.dataset.roleDel) {
      if (await act(() => del(api('/api/roles/' + encodeURIComponent(t.dataset.roleDel))), '역할을 지웠습니다')) { await loadBoard(); render(); }
      return;
    }
    if (t.dataset.foldText) {
      st.open[t.dataset.foldText] = !st.open[t.dataset.foldText];
      const box = st.host.querySelector('[data-ag-detail]');
      if (box && st.detail && st.tab === 'agents' && !st.form) box.innerHTML = agentDetail(st.detail);
    }
  }
  function onChange(e) {
    if (e.target.matches('select[data-map]')) setMap(e.target);
  }
  function onSubmit(e) {
    if (!e.target.matches('[data-ag-form]')) return;
    e.preventDefault();
    submitForm(e.target);
  }
  function onKey(e) {
    if ((e.key === 'Enter' || e.key === ' ') && e.target.matches('[data-pick-agent], [data-pick-skill]')) { e.preventDefault(); e.target.click(); }
  }

  function mount(el) {
    if (!el) return;
    if (st.host !== el) {
      st.host = el;
      el.addEventListener('click', onClick);
      el.addEventListener('change', onChange);
      el.addEventListener('submit', onSubmit);
      el.addEventListener('keydown', onKey);
    }
    if (st.form) return;                 // 쓰는 중인 폼은 화면 전환으로 지우지 않는다
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
  // 학생이 만든 에이전트의 이름을 처리 건 · 작업함 화면에도 (화면을 열지 않아도) — 실패하면 id 대신 이름이 안 보일 뿐, 화면은 그대로
  if (typeof API !== 'undefined') getJ(api('/api/agents')).then(registerNames).catch(() => {});
})();
