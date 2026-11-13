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
  const st = { host: null, tab: 'agents', agents: null, skills: null, pick: { agents: null, skills: null }, detail: null, error: '', open: {}, seq: 0,
    form: null, options: null, board: null, boardError: '', busy: false, acting: new Set() };

  const serverName = (name, description) => hydWords.serverName(name, description);   // 도구 서버 이름표는 plainWords.js 하나
  const course = () => window.hydCourseAccess;
  const skillName = (name, labels=[]) => UI.skillLabel(labels.find(s=>(s.name || s.skill_name) === name) || (st.skills || []).find(s=>s.skill_name === name) || {name}).label;
  // 모델은 두 단계 모두 강사가 정한 수업 모델 하나다(서버 GET /api/course-access 의 model) — 비어 있거나 그 값이면 「수업 모델」
  const modelText = m => !m || m === course().model ? '수업 모델' : m;
  const api = path => API.process + path;
  const del = url => requestJ(url, { method: 'DELETE' });
  // 누가 했나 = 이 PC의 담당자 id. 에이전트 지우기 · 되돌리기 · 단계 배정은 서버가 「누가」를 요구한다(열린 단계의 담당이 바뀐 기록에 남는다 —
  // inbox.actor_or_400, 비면 400). 담당자를 못 읽었으면 다른 값으로 대신하지 않고 까닭과 함께 멈춘다(act 가 그 까닭을 띄운다)
  function me() { const id = window.hydInbox?.me?.()?.id; if (!id) throw new Error('담당자 정보를 읽지 못해 보낼 수 없습니다. 화면을 새로 고친 뒤 다시 해 주세요.'); return id; }
  const mineChip = o => UI.chipText(o === 'user' ? '내가 만든' : '기본', 'neutral');      // 색은 상태에만 쓴다 — 기본 / 내가 만든은 글로 가른다
  // 키-값 · 이름표 붙은 묶음(기준 4절). 값이 없는 줄은 그리지 않는다. 오류 · 읽는 중 · 빈 상태는 ui.js 의 부품을 쓴다
  const errBox = (what, why) => UI.errorBlock(what, why, { retry: true, cls: 'compact' });      // [다시 시도]는 onClick 의 data-retry 가 받는다
  const loading = () => UI.loading('', 'compact');
  const blank = (title, sub = '') => UI.empty(title, sub, 'compact');
  const kv = rows => { const r = rows.filter(([, v]) => v != null && v !== ''); return r.length ? `<dl class="kv">${r.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${v}</dd>`).join('')}</dl>` : ''; };
  const group = (label, body) => body ? `<section class="rd-group"><h3 class="rd-label">${esc(label)}</h3>${body}</section>` : '';
  function reason(e) {
    if (e && e.status === 404 && !/[가-힣]/.test(e.message || '')) return '찾을 수 없습니다. 지웠거나 이름이 바뀌었을 수 있습니다. 다시 읽어 보세요.';
    return (e && e.message) || '처리 엔진에 연결할 수 없습니다';
  }
  function longText(key, text) {
    const t = String(text || '');
    if (t.length <= SHORT || st.open[key]) return esc(t) + (t.length > SHORT ? ` <button type="button" class="link-btn" data-fold-text="${esc(key)}">줄이기</button>` : '');
    return esc(t.slice(0, SHORT)) + '… ' + `<button type="button" class="link-btn" data-fold-text="${esc(key)}">더 보기</button>`;
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
    box.innerHTML = loading();
    try {
      const d = await getJ(api(url));
      if (tab !== st.tab || key !== (tab === 'agents' ? st.pick.agents : st.pick.skills) || st.form) return;
      st.detail = d;
      box.innerHTML = tab === 'agents' ? agentDetail(d) : skillDetail(d);
    } catch (e) {
      box.innerHTML = errBox(tab === 'agents' ? '에이전트를 읽지 못했습니다' : '스킬을 읽지 못했습니다', reason(e));
    }
  }
  function emptyDetail() {
    return st.tab === 'agents'
      ? blank('에이전트가 없습니다', '화면 위의 [새 에이전트]로 만들면 여기에 나타납니다.')
      : blank('아직 스킬이 없습니다', '화면 위의 [새 스킬]로 작업 요령 문서(SKILL.md)를 쓰면 여기에 나타납니다.');
  }

  /* ---------- 목록 ---------- */
  function agentItem(a) {
    const sel = a.id === st.pick.agents && !st.form ? ' sel' : '';
    return `<div class="item${sel}" role="button" tabindex="0" data-pick-agent="${esc(a.id)}" title="${esc(a.name)}">` +
      `<div class="row"><strong>${esc(a.name)}</strong>${a.kind === 'agent' ? mineChip(a.origin) : ''}</div>` +
      `<span class="sub">${esc(clip(a.goal || a.role || '목표가 적혀 있지 않습니다'))}</span></div>`;
  }
  function skillItem(s) {
    const sel = s.skill_name === st.pick.skills && !st.form ? ' sel' : '';
    // 칩은 한 줄에 하나: 어느 에이전트에도 붙지 않은 스킬은 그 상태를, 나머지는 기본 / 내가 만든을 보인다
    return `<div class="item${sel}" role="button" tabindex="0" data-pick-skill="${esc(s.skill_name)}">` +
      `<div class="row"><strong>${esc(s.title)}</strong>${s.agents.length ? mineChip(s.origin) : UI.chipText('미배정', 'warning')}</div>` +
      `<span class="sub">${esc(clip(s.description || '설명 없음'))}</span></div>`;
  }
  function listHtml() {
    if (st.tab === 'agents') {
      const agents = (st.agents || []).filter(a => a.kind === 'agent'), systems = (st.agents || []).filter(a => a.kind !== 'agent');
      return (agents.length ? `<div class="list">${agents.map(agentItem).join('')}</div>` : blank('AI 에이전트가 없습니다', '화면 위의 [새 에이전트]로 만듭니다.')) +
        (systems.length ? UI.fold(`시스템 수행자 ${systems.length}`, `<div class="list">${systems.map(agentItem).join('')}</div>`,
          { open: systems.some(a => a.id === st.pick.agents), cls: 'small' }) : '');
    }
    return (st.skills || []).length ? `<div class="list">${st.skills.map(skillItem).join('')}</div>` : blank('아직 스킬이 없습니다', '화면 위의 [새 스킬]로 만듭니다.');
  }

  /* ---------- 에이전트 상세 (요약 먼저, 실행 설정·지시문은 펼침) ---------- */
  function agentActions(d) {
    if (d.kind !== 'agent') return '';
    const clone = `<button type="button" class="btn small" data-clone="${esc(d.id)}">복제해서 고치기</button>`;
    if (!d.editable) return clone;
    return `<button type="button" class="btn small" data-edit-agent>고치기</button>${clone}<button type="button" class="btn danger small" data-del-agent>지우기</button>`;
  }
  // 읽는 차례(기준 5-1 · 5-6): 이름과 한 줄 → 맡는 일 → 쓰는 것 → 맡은 단계 → 「자세히」(실행 설정 · 지시문 · 식별자)
  function agentDetail(d) {
    const isAgent = d.kind === 'agent';
    const tools = d.tools.length ? d.tools.map(t => `<span title="${esc(t.name)}">${esc(serverName(t.name, t.description))}</span>${t.registered ? '' : ' <span class="neg">(등록 안 됨)</span>'}`).join(', ')
      : isAgent ? '지정하지 않아 등록된 도구 서버를 모두 씁니다' : '';
    const skills = d.skills.map(s => s.found
      ? `<button type="button" class="link-btn" data-goto-skill="${esc(s.skill_name)}" title="${esc(s.description)}">${esc(s.title)}</button>`
      : `<span class="neg" title="${esc(s.skill_name)}">본문 없는 스킬</span>`).join(', ');
    const rules = d.work_rules_detail?.error ? `<span class="neg">${esc(d.work_rules_detail.error)}</span>` : d.work_rules_detail ? esc(d.work_rules_detail.label)
      : d.work_rules ? `<span class="neg">업무 규칙 내용을 읽지 못했습니다</span>` : '공통 안전 규칙만 적용';
    const steps = d.steps.length ? `<ul class="rd-lines">${d.steps.map(s => `<li><span>${esc(stepLabel(s))}</span>${s.assigned ? '<small>담당 배정으로 맡음</small>' : ''}</li>`).join('')}</ul>`
      : `<p class="rd-note">맡은 단계가 없습니다. [담당 배정]에서 단계를 맡기면 그 단계가 이 에이전트로 실행됩니다.</p>`;
    const note = !isAgent ? '정해진 업무를 하는 시스템입니다. 에이전트 설정은 쓰지 않습니다.'
      : d.editable ? '내가 만든 에이전트입니다. 고친 내용은 다음 실행부터 쓰입니다.'
        : '기본 에이전트는 수업 기준이라 고칠 수 없습니다. 복제해서 사본을 고칩니다.';
    let html = `<header class="rd-head"><div><div class="rd-title"><h2>${esc(d.name)}</h2>${isAgent ? mineChip(d.origin) : ''}</div><p class="rd-sub">${esc(note)}</p></div>` +
      `<div class="rd-actions">${agentActions(d)}</div></header>` +
      group('맡는 일', kv([['역할', esc(d.role || '')], ['목표', d.goal ? `<p>${longText('goal:' + d.id, d.goal)}</p>` : ''],
        ['성격 · 말투', isAgent && d.persona ? `<p>${longText('persona:' + d.id, d.persona)}</p>` : '']])) +
      (isAgent ? group('쓰는 것', kv([['모델', esc(modelText(d.model))], ['도구 서버', tools], ['스킬', skills || '없음'], ['업무 규칙', rules]])) : '') +
      group('맡은 단계', steps);
    const more = [];
    if (isAgent) {
      const run = d.run || {};
      const stepRows = (run.steps || []).map(s => {
        const x = s.settings;
        return `<tr><td>${esc(UI.flowName(s.name))}</td><td>${esc(modelText(x.model))}${x.model_source ? `<small>${esc(MODEL_FROM[x.model_source] || '')}</small>` : ''}</td>` +
          `<td>${esc(runServersText(s.servers))}${x.tools_source ? `<small>${esc(TOOLS_FROM[x.tools_source] || '')}</small>` : ''}</td>` +
          `<td>${esc(x.skills.length ? x.skills.map(n=>skillName(n,x.skill_labels || [])).join(', ') : '없음')}${x.missing_skills.length ? `<small class="neg">본문 없는 스킬 ${x.missing_skills.length}개</small>` : ''}${UI.fold('설정 식별자 원문',`<pre>${esc(JSON.stringify({skills:x.skills,missing_skills:x.missing_skills,tools:x.tools},null,2))}</pre>`,{cls:'small'})}</td></tr>`;
      }).join('');
      more.push(group('단계별 실제 실행 설정', stepRows ? `<div class="rd-scroll"><table class="tbl"><thead><tr><th>단계</th><th>모델</th><th>도구 서버</th><th>스킬 파일</th></tr></thead><tbody>${stepRows}</tbody></table></div>`
        : `<p class="rd-note">맡은 단계가 없어 처리 건에서는 불리지 않습니다.</p>`));
      more.push(group('실행 지시문에 더해지는 내용', run.instructions ? `<pre class="rd-doc">${esc(run.instructions)}</pre><p class="rd-note">AI 에이전트가 이 내용을 지시문에 넣고, 스킬은 실행 작업 폴더에 SKILL.md 파일로 씁니다.</p>`
        : `<p class="rd-note">더해지는 내용이 없습니다. 이름 · 목표 · 성격 · 스킬이 비어 있습니다.</p>`));
      if (d.work_rules_detail && !d.work_rules_detail.error) more.push(group('업무 규칙 원문 · ' + d.work_rules_detail.label, `<pre class="rd-doc">${esc(d.work_rules_detail.content)}</pre>`));
    }
    more.push(group('식별자', kv([['식별자', `<span class="mono">${esc(d.id)}</span>`],
      ['등록된 도구 서버', esc(((d.run || {}).servers_registered || []).map(n => serverName(n.name, n.description)).join(', '))]])));
    html += `<div class="rd-group">${UI.fold(isAgent ? '자세히 · 단계별 실행 설정 · 실행 지시문 · 식별자' : '자세히 · 식별자', more.join(''), { cls: 'small' })}</div>`;
    return html;
  }

  /* ---------- 스킬 상세 ---------- */
  // 읽는 차례: 이름과 한 줄 → 설명 → 스킬 문서(읽을 내용) → 붙은 에이전트 · 선언한 단계 → 「자세히」
  function skillDetail(s) {
    const mineAgents = (st.agents || []).filter(a => a.kind === 'agent' && a.editable);
    const attachedIds = new Set(s.agents.map(a => a.id));
    const agents = s.agents.length ? `<ul class="rd-lines">${s.agents.map(a => {
      const own = mineAgents.some(m => m.id === a.id);
      return `<li><button type="button" class="link-btn" data-goto-agent="${esc(a.id)}">${esc(a.name)}</button>` +
        (own ? `<button type="button" class="btn small ghost" data-detach="${esc(a.id)}" title="이 에이전트에서 스킬을 뗍니다">스킬 떼기</button>` : '') + '</li>';
    }).join('')}</ul>` : '<p class="rd-note">붙은 에이전트가 없습니다. 붙이지 않은 스킬은 어떤 실행에도 들어가지 않습니다.</p>';
    const can = mineAgents.filter(a => !attachedIds.has(a.id));
    const attach = can.length ? `<div class="rd-inline"><select data-attach-to aria-label="붙일 에이전트"><option value="">에이전트 선택</option>${can.map(a => `<option value="${esc(a.id)}">${esc(a.name)}</option>`).join('')}</select>` +
      `<button type="button" class="btn small" data-attach disabled title="붙일 에이전트를 먼저 고르세요">내 에이전트에 붙이기</button></div>`
      : `<p class="rd-note">붙일 수 있는 내 에이전트가 없습니다. 기본 에이전트에는 붙일 수 없으니 복제해서 붙이세요.</p>`;
    const mine = s.origin === 'user';
    const actions = mine ? `<button type="button" class="btn small" data-edit-skill>고치기</button><button type="button" class="btn danger small" data-del-skill>지우기</button>` : '';
    return `<header class="rd-head"><div><div class="rd-title"><h2>${esc(s.title)}</h2>${mineChip(s.origin)}</div>` +
      `<p class="rd-sub">${mine ? '붙은 에이전트가 실행될 때 작업 폴더에 이 문서가 SKILL.md 로 들어갑니다.' : '기본 스킬은 수업 기준이라 고칠 수 없습니다. 새 스킬을 만들어 씁니다.'}</p></div>` +
      `<div class="rd-actions">${actions}</div></header>` +
      group('설명', s.description ? `<p class="rd-p">${esc(s.description)}</p>` : '') +
      group('스킬 문서', `<pre class="rd-doc">${esc(s.content || '')}</pre>`) +
      group('붙은 에이전트', agents + attach) +
      group('선언한 단계', s.steps.length ? `<ul class="rd-lines">${s.steps.map(x => `<li><span>${esc(stepLabel(x))}</span></li>`).join('')}</ul>` : '') +
      `<div class="rd-group">${UI.fold('자세히 · 폴더 이름 · 길이 · 고친 시각', kv([['폴더 이름', `<span class="mono">${esc(s.skill_name)}</span>`],
        ['길이', esc((s.content || '').length.toLocaleString('ko-KR') + '자')], ['고친 시각', s.updated_at ? esc(UI.dateTime(s.updated_at)) : '']]), { cls: 'small' })}</div>`;
  }

  /* ---------- 만들기 · 고치기 폼 ---------- */
  function openForm(kind, d) {
    if (kind === 'agent') {
      st.form = { kind, id: d ? d.id : null, error: '', draft: d ? { name: d.name, role: d.role || '', goal: d.goal || '', persona: d.persona || '', model: '', work_rules: d.work_rules || '',
        tools: d.tools.filter(t => t.registered !== false).map(t => t.name || t), skills: d.skills.map(s => s.skill_name || s) }
        : { name: '', role: '', goal: '', persona: '', model: '', work_rules: '', tools: [], skills: [] } };
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
      // 붙일 수 있는지는 서버 판정(mcp_registry.selectable) 그대로 — 붙일 수 없는 서버는 까닭과 함께 꺼 둔다(이미 붙어 있으면 뗄 수는 있다)
      const tools = o.servers.length ? o.servers.map(s => { const on = d.tools.includes(s.name), off = !s.selectable && !on;
        return `<label class="check"><input type="checkbox" data-f-tool value="${esc(s.name)}" ${on ? 'checked' : ''} ${off ? 'disabled' : ''}> ` +
          `<span>${esc(serverName(s.name, s.description))}${s.selectable ? '' : ` <small class="muted">붙일 수 없음${s.reason ? ' — ' + esc(s.reason) : ''}</small>`}</span></label>`; }).join('')
        : '<span class="muted">등록된 도구 서버가 없습니다</span>';
      const skills = o.skills.length ? o.skills.map(s => `<label class="check"><input type="checkbox" data-f-skill value="${esc(s.skill_name)}" ${d.skills.includes(s.skill_name) ? 'checked' : ''}> ` +
        `<span>${esc(UI.skillLabel(s).label)}${s.origin === 'user' ? ' <small class="muted">내가 만든</small>' : ''}</span></label>`).join('') : '<span class="muted">아직 스킬이 없습니다. [스킬]에서 먼저 만드세요.</span>';
      return `<header class="rd-head"><div><div class="rd-title"><h2>${f.id ? '에이전트 고치기' : '새 에이전트'}</h2></div>` +
        `<p class="rd-sub">저장하면 다음 실행부터 이 설정으로 실행됩니다. 단계를 맡기려면 저장한 뒤 [담당 배정]에서 고릅니다.</p></div></header>` +
        `<form data-ag-form class="rd-form rd-group">` +
        UI.section('기본', UI.field({ label: '이름', required: true, input: `<input data-f="name" maxlength="60" value="${esc(d.name)}">` }) +
          UI.field({ label: '역할', input: `<input data-f="role" maxlength="200" value="${esc(d.role)}" placeholder="예: 쿨러 열화를 먼저 본다">` }) +
          UI.field({ label: '목표', required: true, input: `<textarea data-f="goal" maxlength="500">${esc(d.goal)}</textarea>`, hint: '이 에이전트가 무엇을 해내야 하는지 한 문장' }) +
          UI.field({ label: '성격 · 말투', input: `<textarea data-f="persona" maxlength="2000">${esc(d.persona)}</textarea>` }) +
          UI.readonly('모델', esc(modelText('')), '수업용 모델 하나를 씁니다. 바꿀 수 없습니다.')) +
        UI.section('쓰는 도구 (등록된 MCP 서버)', `<div class="rd-checks">${tools}<p class="field-hint">하나도 고르지 않으면 등록된 서버를 모두 씁니다.</p></div>`) +
        UI.section('스킬', `<div class="rd-checks">${skills}</div>`) +
        UI.section('업무 규칙', UI.field({ label: '적용할 업무 규칙', input: `<select data-f="work_rules"><option value="">공통 안전 규칙만 적용</option>${d.work_rules && !(o.work_rules || []).some(r => r.key === d.work_rules) ? `<option value="${esc(d.work_rules)}" selected>등록되지 않은 업무 규칙 — 다시 선택하세요</option>` : ''}${(o.work_rules || []).map(r => `<option value="${esc(r.key)}" ${d.work_rules === r.key ? 'selected' : ''}>${esc(r.label)}</option>`).join('')}</select>` }) +
          (o.work_rules || []).map(r => UI.fold(esc(r.label) + ' 내용', `<pre>${esc(r.content)}</pre>`, { cls: 'small' })).join('')) +
        formActions(f) + `</form>`;
    }
    return `<header class="rd-head"><div><div class="rd-title"><h2>${f.id ? '스킬 고치기' : '새 스킬'}</h2></div>` +
      `<p class="rd-sub">SKILL.md 한 장이 에이전트의 작업 요령입니다. 붙은 에이전트가 실행될 때 작업 폴더에 이 문서가 들어갑니다.</p></div></header>` +
      `<form data-ag-form class="rd-form rd-group">` +
      UI.section('', UI.field({ label: '폴더 이름', required: true, input: `<input data-f="skill_name" class="mono" maxlength="64" value="${esc(d.skill_name)}" ${f.id ? 'disabled' : ''} placeholder="예: cooler-check">`,
        hint: '영문 소문자 · 숫자 · 하이픈. 문서 머리의 name 과 같아야 합니다' }) +
        UI.field({ label: '설명 한 줄', input: `<input data-f="description" maxlength="300" value="${esc(d.description)}">`, hint: '비우면 문서 머리의 description 이나 첫 제목을 씁니다' }) +
        UI.field({ label: 'SKILL.md', required: true, cls: 'wide', input: `<textarea data-f="content" class="mono" rows="14">${esc(d.content)}</textarea>` })) +
      formActions(f) + `</form>`;
  }
  // 폼의 단추 줄: 맨 아래 왼쪽에 주 단추 → 보조 단추(기준 5-6). 저장이 안 된 까닭은 단추 줄 바로 위에
  function formActions(f) {
    return (f.error ? `<p class="field-error" role="alert">${esc(f.error)}</p>` : '') +
      `<div class="rd-form-actions"><button type="submit" class="btn primary" ${st.busy ? 'disabled' : ''}>저장</button><button type="button" class="btn" data-f-cancel>취소</button></div>`;
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
    if (st.boardError) return errBox('담당 배정을 읽지 못했습니다', st.boardError);
    const b = st.board;
    if (!b) return loading();
    const closedWhy = [...new Set(b.steps.map(s => course().assignBlocked(s.definition_id)).filter(Boolean))];
    const rows = b.steps.map(s => {
      const cur = s.assigned ? s.assigned.agent_id : '';
      const opts = [`<option value="">기본 담당 (${esc(s.default_names.join(', '))})</option>`].concat(
        b.agents.filter(a => !s.default_agents.includes(a.id)).map(a => `<option value="${esc(a.id)}" ${a.id === cur ? 'selected' : ''}>${esc(a.name)}${a.origin === 'user' ? ' · 내가 만든' : ''}</option>`)).join('');
      const closed = course().assignBlocked(s.definition_id);
      return `<tr${s.assigned ? ' class="pick"' : ''}><td>${esc(stepLabel(s))}</td><td>${esc(s.default_names.join(', '))}</td>` +
        `<td><select data-map="${esc(s.definition_id)}|${esc(s.activity_id)}" aria-label="${esc(s.name)} 담당"${closed ? ` disabled title="${esc(closed)}"` : ''}>${opts}</select></td></tr>`;
    }).join('');
    const steps = `<section class="rd-group"><h2 class="rd-sec">단계별 담당 AI 에이전트</h2>` +
      `<p class="rd-note">흐름 정의는 그대로 두고, 이 단계가 열릴 때 고른 에이전트가 맡습니다. 기본 담당으로 되돌리면 다음에 열리는 단계부터 기본으로 실행됩니다.</p>` +
      closedWhy.map(w => `<p class="rd-note">${esc(w)}</p>`).join('') +
      (rows ? `<div class="rd-scroll"><table class="tbl"><thead><tr><th>단계</th><th>기본 담당</th><th>지금 담당</th></tr></thead><tbody>${rows}</tbody></table></div>`
        : blank('에이전트가 맡는 단계가 없습니다', '흐름을 등록하면 그 흐름의 AI 단계가 여기에 나옵니다.')) + `</section>`;
    // 쓰는 사람은 늘 이 PC의 담당자 한 명이고 모든 역할을 맡는다(새 역할도 서버 agent_authoring.create_role 이 담당자를 넣는다) — 사람을 넣고 빼는 칸이 없다.
    // 구성원이 한 명도 없는 역할은 그 사실을 그대로 보인다(그 역할의 사람 단계가 내가 할 일에 뜨지 않는다)
    const roles = (b.roles || []).map(r => {
      // G10: 포털에서 만든 역할은 표시하고 지울 수 있다(흐름 정의가 쓰면 서버가 사유와 함께 거절)
      const mine = r.origin === 'user' ? `<span class="rd-inline"><small class="muted">내가 만든</small><button type="button" class="btn small danger" data-role-del="${esc(r.id)}">지우기</button></span>` : '';
      const none = r.members.length ? '' : '<br><span class="neg">이 역할에 담당자가 연결되어 있지 않아, 이 역할의 사람 단계가 내가 할 일에 뜨지 않습니다. 시작 파일을 다시 실행해 업무 DB를 최신 판으로 맞추세요.</span>';
      return `<li><span>${esc(UI.performers[r.id] || r.name)}${none}</span>${mine}</li>`;
    }).join('');
    const people = `<section class="rd-group"><h2 class="rd-sec">역할</h2>` +
      `<p class="rd-note">모든 역할은 이 PC의 담당자가 맡습니다. 사람 단계는 그 단계의 역할 이름으로 내가 할 일에 뜹니다.</p>` +
      (roles ? `<ul class="rd-lines">${roles}</ul>` : blank('역할이 없습니다', '아래에서 역할을 만듭니다.')) +
      `<div class="rd-group"><h3 class="rd-label">역할 만들기</h3>` +
      `<div class="rd-inline" role="group" aria-label="역할 만들기"><input data-role-name placeholder="역할 이름 (내 흐름의 레인 이름과 같게)" aria-label="새 역할 이름">` +
      `<input data-role-key placeholder="키 (선택, 예: s01-organizer)" aria-label="새 역할 키"><button type="button" class="btn small" data-role-add>역할 만들기</button></div>` +
      `<p class="rd-note">흐름 화면에서 가져온 그림은 레인 이름이 역할 이름과 같으면 그 역할로 이어집니다. 새로 만든 역할도 이 PC의 담당자가 맡습니다.</p></div></section>`;
    return steps + people;
  }
  async function setMap(sel) {
    const [definition_id, activity_id] = sel.dataset.map.split('|');
    try {
      if (sel.value) await postJ(api('/api/agent-assignments'), { definition_id, activity_id, agent_id: sel.value, by: me() }, 'PUT');
      else await del(api(`/api/agent-assignments/${encodeURIComponent(definition_id)}/${encodeURIComponent(activity_id)}`));
      UI.toast(sel.value ? '담당을 바꿨습니다. 다음에 열리는 단계부터 적용됩니다.' : '기본 담당으로 되돌렸습니다.', { tone: 'ok' });
    } catch (e) { UI.toast(reason(e), { tone: 'neg', timeout: 8000 }); }
    await loadBoard(); await refreshAgents(); render();
  }
  async function refreshAgents() {
    try { st.agents = await getJ(api('/api/agents')); registerNames(st.agents); st.error = ''; } catch (e) { st.error = reason(e); }
  }

  /* ---------- 행동 ---------- */
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
  async function resetAll() {
    if (!await UI.confirm({ title: '기준으로 되돌릴까요?', body: '내가 만든 에이전트와 스킬, 스킬 붙이기, 역할, 단계 배정을 모두 지웁니다. 흐름이 쓰는 역할은 남깁니다. 기본 에이전트와 기본 역할은 그대로입니다.', ok: '되돌리기', danger: true })) return;
    const out = await act(() => postJ(api('/api/agents/reset'), { by: me() }),
      o => {      // 지운 것만 문장으로(0인 것은 뺀다)
        const removed = [['에이전트', o.agents, '개'], ['스킬', o.skills, '개'], ['스킬 붙이기', o.attachments, '건'], ['역할', o.roles, '개'], ['단계 배정', o.assignments, '건']]
          .filter(([, n]) => n > 0).map(([name, n, unit]) => `${name} ${n}${unit}`);
        return (removed.length ? `되돌렸습니다. 내가 만든 ${removed.join(', ')}${window.hydWords.josa(removed[removed.length - 1], '을/를')} 지웠습니다.` : '되돌렸습니다. 지울 것이 없었습니다.')
          + (o.kept_roles.length ? ` 흐름이 쓰는 역할 ${o.kept_roles.length}개는 남겼습니다.` : '') + (o.returned_tasks.length ? ` 열려 있던 단계 ${o.returned_tasks.length}건은 기본 담당으로 돌아갔습니다.` : '');
      });
    if (out) { st.form = null; st.pick = { agents: null, skills: null }; st.board = null; await load(); }
  }

  /* ---------- 화면 ---------- */
  // 차례: 제목 · 한 문장 · 주 단추 하나 → 보기 바꾸기(조각 탭) → 왼쪽 목록 · 오른쪽 상세 → 맨 아래 「기준으로 되돌리기」
  function render() {
    if (!st.host) return;
    const n = st.agents ? st.agents.filter(a => a.kind === 'agent').length : null, m = st.skills ? st.skills.length : null;
    const seg = [['agents', '에이전트', n], ['skills', '스킬', m], ['assign', '담당 배정']].map(([k, l, c]) =>
      `<button type="button" role="tab" class="${k === st.tab ? 'on' : ''}" data-ag-tab="${k}" aria-selected="${k === st.tab}">${esc(l)}${c != null ? `<span class="n">${c}</span>` : ''}</button>`).join('');
    // 주 단추는 화면에 하나: 폼을 쓰는 동안에는 폼의 [저장]이 주 단추라 새로 만들기 단추를 그리지 않는다
    const make = st.form || st.tab === 'assign' ? '' : st.tab === 'agents' ? `<button type="button" class="btn primary" data-new-agent>새 에이전트</button>` : `<button type="button" class="btn primary" data-new-skill>새 스킬</button>`;
    const body = st.tab === 'assign' ? assignHtml()
      : `<div class="rd-split"><div class="rd-side">${st.agents ? listHtml() : loading()}</div><div data-ag-detail></div></div>`;
    st.host.innerHTML =
      `<div class="page-head"><h1>${esc(UI.t('nav.agents'))}</h1><div class="page-tools"><button type="button" class="btn" data-ag-reload title="코딩 랩에서 만든 것도 다시 읽으면 함께 보입니다">다시 읽기</button>${make}</div></div>` +
      `<p class="page-lead">AI 에이전트와 스킬을 만들고, 흐름의 단계를 어느 에이전트가 맡을지 정합니다.</p>` +
      (st.error ? errBox('에이전트와 스킬 목록을 읽지 못했습니다', st.error) : '') +
      `<div class="rd-seg" role="tablist" aria-label="보기">${seg}</div>` + body +
      `<p class="rd-foot"><span>내가 만든 에이전트 · 스킬 · 역할 · 담당 배정을 모두 지우고 수업 기준으로 돌아갑니다.</span><button type="button" class="btn small danger" data-ag-reset>기준으로 되돌리기</button></p>`;
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
    if (t.hasAttribute('data-retry')) return t.closest('[data-ag-detail]') ? loadDetail() : load();      // 오류 블록의 [다시 시도]: 상세만 못 읽었으면 상세만 다시 읽는다
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
    if (t.dataset.clone) return cloneAgent(t.dataset.clone, t);
    if (t.hasAttribute('data-del-agent') && st.detail) return deleteAgent(st.detail);
    if (t.hasAttribute('data-del-skill') && st.detail) return deleteSkill(st.detail);
    if (t.hasAttribute('data-f-cancel')) { st.form = null; render(); return loadDetail(); }
    if (t.hasAttribute('data-attach') && st.detail) {
      const sel = st.host.querySelector('[data-attach-to]'), skill = st.detail.skill_name;
      if (sel && !sel.value) { UI.toast('스킬을 붙일 에이전트를 고르세요', { tone: 'neg' }); return; }      // 고르지 않은 첫 항목에 붙지 않게
      if (sel && await once('attach:' + skill, t, () => act(() => postJ(api('/api/agents/' + encodeURIComponent(sel.value) + '/skills'), { skill_name: skill }), '붙였습니다'))) await load();
      return;
    }
    if (t.dataset.detach && st.detail) {
      const skill = st.detail.skill_name;
      if (await once('detach:' + t.dataset.detach + '/' + skill, t, () => act(() => del(api('/api/agents/' + encodeURIComponent(t.dataset.detach) + '/skills/' + encodeURIComponent(skill))), '뗐습니다'))) await load();
      return;
    }
    if (t.hasAttribute('data-role-add')) {
      const name = (st.host.querySelector('[data-role-name]') || {}).value || '', key = (st.host.querySelector('[data-role-key]') || {}).value || '';
      if (await once('role-add', t, () => act(() => postJ(api('/api/roles'), { name: name.trim(), key: key.trim() || null }), r => `역할 '${r.name}'${window.hydWords.josa(r.name, '을/를')} 만들었습니다. 이 역할도 이 PC의 담당자가 맡습니다.`))) { await loadBoard(); render(); }
      return;
    }
    if (t.dataset.roleDel) {
      const role = ((st.board && st.board.roles) || []).find(r => r.id === t.dataset.roleDel) || {};
      const roleName = role.name || UI.performers[t.dataset.roleDel] || '이름 없는 역할';
      if (!await UI.confirm({ title: `역할 '${roleName}'${window.hydWords.josa(roleName, '을/를')} 지울까요?`,
        body: '흐름 정의가 이 역할을 쓰거나 이 역할에 끝나지 않은 작업이 있으면 지울 수 없고, 그 까닭을 알려 줍니다. 지운 역할은 되살릴 수 없습니다.', ok: '지우기', danger: true })) return;
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
    if (e.target.matches('select[data-attach-to]')) {      // 붙일 에이전트를 골라야 [내 에이전트에 붙이기]가 켜진다
      const b = st.host.querySelector('[data-attach]');
      if (b) { b.disabled = !e.target.value; b.title = e.target.value ? '' : '붙일 에이전트를 먼저 고르세요'; }
    }
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
      course().onChange(() => { if (st.tab === 'assign') render(); });
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
  // 메뉴를 다시 열 때마다 다시 읽는다(셸 show) — 쓰는 중인 폼은 mount 가 그대로 둔다
  window.hydAgents = { mount, show: mount };
  // 학생이 만든 에이전트의 이름을 처리 건 · 작업함 화면에도 (화면을 열지 않아도). 실패하면 그 화면들은 이름 대신 식별자를 보인다 —
  // 이 화면(에이전트)을 열면 같은 목록을 다시 읽어 실패 사유가 화면에 보인다. 여기서는 콘솔에 남긴다(삼키지 않는다)
  if (typeof API !== 'undefined') getJ(api('/api/agents')).then(registerNames).catch(e => console.error('에이전트 이름 목록을 읽지 못했습니다:', e.message));
})();
