/* 프로세스 인스턴스 · 할일 목록 (instance mode, loaded after hitl.js and instanceSteps.js).
   process 서비스의 instance-mode API 를 읽는다:
     GET  /api/process/mode · /api/process/definition · /api/instances · /api/instances/{id} · /api/todolist?status=IN_PROGRESS · /api/decisions/{id}
     POST /api/todolist/{id}/select (task:select) · /api/todolist/{id}/submit (task:escalate 등 폼) · /api/todolist/{id}/human-response
   상태 의미는 ProcessGPT 와 같다: TODO 예정 → IN_PROGRESS 처리 중(내 할일) → SUBMITTED 제출(엔진 차례) → DONE · CANCELLED · PENDING.
   단계 계산은 process-gpt-vue3 의 instanceSteps.js(window.hydSteps) 그대로다. */
(function () {
  const I = { mode: null, taskSel: null, taskView: null, fieldValues: {}, fieldTask: null, instances: [], sel: null, view: null, todo: [], dec: null, decId: null, asked: [],
              form: { option: null, role: null, by: 'OP-17', reason: '', fan: null, load: null }, msg: '', busy: false, sig: null };
  const PERFORMER = { 'sys:agent': 'AI 에이전트', 'role:operator': '운전원', 'role:prod-mgr': '생산관리자', 'role:maint-mgr': '정비관리자', 'sys:scada': 'SCADA', 'sys:process': '프로세스', 'sys:cmms': 'CMMS' };
  const who = id => PERFORMER[id] || id || '–';
  const pill = s => `<span class="pill ${esc(s)}">${esc(UI.status(s))}</span>`;
  const STEP_LABEL = { done: '완료', current: '진행 중', skipped: '건너뜀', todo: '예정' };
  const isHuman = t => !t.agent_orch && !t.agent_mode;

  /* ------------------------------------------------ load */
  async function load(force) {
    if (state.tab !== 'instances') return;
    if (I.loading) { I.reload = I.reload || force; return; }
    I.loading = true;
    try {
    try { I.mode = await getJ(API.process + '/api/process/mode'); } catch (e) { I.mode = { error: e.message }; }
    if (!I.mode || I.mode.mode !== 'instance') { renderBanner(); return; }
    // A083: the server filters by status; without it a RUNNING case older than the newest 50 is unreachable from the portal
    try { I.instances = await getJ(API.process + '/api/instances?limit=50' + (I.status ? '&status=' + encodeURIComponent(I.status) : '')); } catch (e) { I.instances = []; }
    let todoRows = [];
    try { todoRows = await getJ(API.process + '/api/todolist?status=IN_PROGRESS'); } catch (e) { I.msg = e.message; }
    I.todo = todoRows.filter(isHuman); I.asked = todoRows.filter(t => t.draft_status === 'HUMAN_ASKED');
    if (!I.sel && I.instances[0]) I.sel = I.instances[0].proc_inst_id;
    I.view = null;
    if (I.sel) { try { I.view = await getJ(API.process + '/api/instances/' + encodeURIComponent(I.sel)); } catch (e) { I.view = null; } }
    I.graph = null;
    if (I.sel) { try { I.graph = await getJ(API.process + '/api/instances/' + encodeURIComponent(I.sel) + '/graph'); } catch (e) { I.graph = { error: e.message }; } }
    try { I.caseProjection = await getJ(API.process + '/api/graph-projections'); } catch (e) { I.caseProjection = { error: e.message }; }
    try { I.worker = await getJ(API.process + '/api/agents/status'); } catch (e) { I.worker = { reachable: false, error: e.message }; }
    const task = I.todo.find(t => t.id === I.taskSel && t.proc_inst_id === I.sel) || I.todo.find(t => t.proc_inst_id === I.sel);
    I.taskView = null;
    if (task) { try { I.taskView = await getJ(API.process + '/api/todolist/' + encodeURIComponent(task.id)); } catch(e) { I.msg = e.message; } }
    const selectTask = I.taskView && I.taskView.tool === 'formHandler:select_card' ? I.taskView : null;
    const decId = selectTask ? await decisionIdOf(selectTask) : null;
    if (decId !== I.decId) { I.decId = decId; I.dec = null; I.form = { option: null, role: null, by: I.form.by, reason: '', fan: null, load: null }; }
    if (I.decId && !I.dec) { try { I.dec = await getJ(API.process + '/api/decisions/' + encodeURIComponent(I.decId)); } catch (e) { I.dec = null; } }
    const sig = JSON.stringify([I.status, I.instances.map(x => [x.proc_inst_id, x.status, x.current_activity_ids]), I.todo.map(t => t.id), I.asked.map(t => [t.id, t.draft_status]), I.sel, I.taskView,
      I.view && I.view.workitems.map(w => [w.id, w.status, w.draft_status]), I.view && I.view.events.length,
      I.view && (I.view.approvals || []).map(a => [a.todo_id,a.status,a.attempts,a.error]), I.dec && I.dec.state, I.msg,
      I.graph && (I.graph.error || I.graph.graph || 'none'), I.graph && I.graph.projection, I.caseProjection,
      I.worker && [I.worker.reachable, (I.worker.health || {}).runs_in_flight, (I.worker.health || {}).handled]]);
    if (!force && sig === I.sig) return;
    I.sig = sig;
    renderBanner(); renderTodo(); renderList(); renderDetail();
    } finally {
      I.loading = false;
      if (I.reload) { I.reload = false; load(true); }
    }
  }
  const vars = inst => Object.fromEntries((inst.variables_data || []).map(v => [v.key, v.value]));
  async function decisionIdOf(task) {
    if (I.view && I.view.instance.proc_inst_id === task.proc_inst_id) return vars(I.view.instance).decision_id || null;
    try { return vars((await getJ(API.process + '/api/instances/' + encodeURIComponent(task.proc_inst_id))).instance).decision_id || null; } catch (e) { return null; }
  }

  /* ------------------------------------------------ banner */
  function renderBanner() {
    const b = $('#instBanner');
    if (!I.mode || I.mode.error) { b.innerHTML = `<div class="inst-banner off">프로세스 서비스에 연결할 수 없습니다. ${esc((I.mode || {}).error || '')}</div>`; return; }
    if (I.mode.mode !== 'instance') {
      b.innerHTML = `<div class="inst-banner off"><b>지금은 legacy 모드입니다.</b> 에이전트가 가이드 카드를 먼저 내고 인시던트가 열리는 v2 방식으로 동작합니다.
        인스턴스 모드를 켜려면 <code>.env</code>에 <code>PROCESS_MODE=instance</code>를 두고 Supabase(<code>cd it/supabase && supabase start</code>)를 띄운 뒤 process 서비스를 다시 시작합니다. 자세한 절차는 <code>docs/handoff/HANDOFF.md</code>.</div>`;
      $('#todoList').innerHTML = '<div class="muted">instance 모드에서만 표시됩니다.</div>'; $('#instList').innerHTML = ''; $('#instDetail').innerHTML = '<div class="empty">instance 모드에서만 표시됩니다.</div>'; $('#todoPanel').innerHTML = '';
      return;
    }
    const running = I.instances.filter(x => x.status === 'RUNNING').length;
    const w = I.worker || {}, h = w.health || {};
    const workerChip = !w.reachable ? `<span class="stat warn"><i class="live-dot off"></i>워커 응답 없음</span>`
      : `<span class="stat ok"><i class="live-dot on"></i>워커 ${esc(h.agent_type || 'cliagents')} · 실행 중 ${esc(h.runs_in_flight ?? 0)}/${esc(h.max_concurrent_runs ?? 1)} · 처리 ${esc(h.handled ?? 0)}</span>`;
    const agents = (w.agents || []).filter(a => a.installed).map(a => esc(a.agent_id) + (a.default ? ' (기본)' : '')).join(' · ');
    b.innerHTML = `<div class="inst-status">
      <span class="stat"><small>정의</small><b>${esc(I.mode.definition)}</b></span>
      <span class="stat"><small>실행 중</small><b class="num">${running}</b></span>
      <span class="stat${I.todo.length ? ' hot' : ''}"><small>내 할일</small><b class="num">${I.todo.length}</b></span>
      ${I.asked.length ? `<span class="stat warn"><small>에이전트 질문</small><b class="num">${I.asked.length}</b></span>` : ''}
      ${workerChip}
      <span class="stat"><small>CLI</small><b>${agents || '없음'}</b></span>
      <span class="stat"><small>다리</small><b>${esc(I.mode.agent_bridge || 'off')}</b></span>
      <span class="stat"><small>배율</small><b class="num">${esc(I.mode.time_scale)}×</b></span>
      <details class="stat-help"><summary>이 화면은 어떻게 도나</summary><p>에이전트 작업은 agent_orch=cliagents 워커가 <code>fetch_pending_task</code>로 집어 선택된 CLI(Claude Code · Codex)를 서브프로세스로 실행하고 <code>save_task_result</code>로 제출합니다. 서비스 작업은 process 서비스가, 사람 작업은 이 화면에서 제출합니다. 제출(SUBMITTED)된 작업은 엔진이 다음 작업을 열며 DONE으로 바꿉니다. 저장소 ${esc(I.mode.repo)} · 엔진 ${esc(I.mode.engine || '')}${!w.reachable ? ` · 워커 주소 <code>${esc(w.url || '')}</code>${w.error ? ' · ' + esc(w.error) : ''} — ${I.mode.agent_bridge === 'legacy' ? '지금은 레거시 다리가 에이전트 작업 네 개를 대신 채웁니다.' : '에이전트 작업은 워커가 뜰 때까지 IN_PROGRESS로 기다립니다.'} 워커는 <code>scripts/run_worker_host.sh</code>로 띄웁니다.` : ''}</p></details>
    </div>`;
  }

  /* ------------------------------------------------ todolist (human tasks = IN_PROGRESS rows assigned to a role) + agent questions */
  function renderTodo() {
    const box = $('#todoList');
    box.innerHTML = '';
    if (!I.todo.length && !I.asked.length) { box.innerHTML = '<div class="muted">사람이 할 작업이 없습니다. 에이전트 작업이 끝나면 "조치 카드 선택"이 여기에 나타납니다.</div>'; $('#todoPanel').innerHTML = ''; return; }
    I.asked.forEach(t => {
      const inst = I.instances.find(x => x.proc_inst_id === t.proc_inst_id) || {};
      const it = el('div', 'item ask' + (t.proc_inst_id === I.sel ? ' sel' : ''), `<strong>에이전트 질문 — ${esc(t.activity_name)}</strong> ${pill('HUMAN_ASKED')}
        <span>${esc(inst.proc_inst_name || t.proc_inst_id)} · 에이전트가 사람의 확인을 기다립니다</span>`);
      keyboardItem(it);
      it.addEventListener('click', () => { I.sel = t.proc_inst_id; I.taskSel = t.id; load(true); });
      box.appendChild(it);
    });
    I.todo.forEach(t => {
      const inst = I.instances.find(x => x.proc_inst_id === t.proc_inst_id) || {};
      const it = el('div', 'item' + (t.proc_inst_id === I.sel ? ' sel' : ''), `<strong>${esc(t.activity_name)}</strong> ${pill(t.status)}
        <span>${esc(inst.proc_inst_name || t.proc_inst_id)} · 수행 ${esc(who(t.user_id))} · 폼 ${esc((t.tool || '').replace('formHandler:', '') || '–')}</span>
        <span class="muted">${esc(t.description || '')}</span>`);
      keyboardItem(it);
      it.addEventListener('click', () => { I.sel = t.proc_inst_id; I.taskSel = t.id; load(true); });
      box.appendChild(it);
    });
    renderTodoPanel();
  }

  function renderTodoPanel() {
    const box = $('#todoPanel');
    const asked = I.asked.find(t => t.proc_inst_id === I.sel);
    if (asked) { renderAskPanel(asked); return; }
    const task = I.taskView;
    if (!task) { box.innerHTML = ''; return; }
    if (task.tool === 'formHandler:select_card') { renderSelectPanel(task); return; }
    const fields = task.form && task.form.fields_json;
    if (!fields) { box.innerHTML = '<div class="neg">이 작업의 폼 계약을 찾을 수 없습니다.</div>'; return; }
    if (I.fieldTask !== task.id) { I.fieldTask = task.id; I.fieldValues = {}; }
    const control = (f, index) => {
      const id = 'tdField' + index, val = I.fieldValues[f.key] ?? '';
      let input;
      if (f.type === 'select' || f.type === 'boolean') {
        const options = f.type === 'boolean' ? [['true','예'],['false','아니요']] : (f.items || []).flatMap(x => typeof x === 'object' ? Object.entries(x) : [[x,x]]);
        input = `<select id="${id}"><option value="">선택하세요</option>${options.map(([v,l]) => `<option value="${esc(v)}" ${String(val)===String(v)?'selected':''}>${esc(l)}</option>`).join('')}</select>`;
      } else if (['textarea','object','array'].includes(f.type)) {
        input = `<textarea id="${id}" rows="3" placeholder="${['object','array'].includes(f.type)?'JSON으로 입력':''}">${esc(val)}</textarea>`;
      } else input = `<input id="${id}" type="${['number','integer'].includes(f.type)?'number':'text'}" step="${f.type==='integer'?'1':'any'}" value="${esc(val)}">`;
      return `<label>${esc(f.text || f.key)}${f.required===false?' (선택)':' *'}${input}</label>`;
    };
    box.innerHTML = `<section class="todo-panel"><h3>${esc(task.activity_name)} — ${esc(who(task.user_id))}</h3><p class="muted">${esc(task.description || '')}</p>
      <p class="muted">정의 ${esc(task.proc_def_id)} · 버전 ${esc(task.version)} · ${task.form_source==='definition-version'?'해당 버전에 고정된 폼':'기존 정의: 현재 폼 사용'}</p>
      ${Object.keys(task.inputs || {}).length ? `<details open><summary>이 작업에 전달된 입력</summary><pre style="white-space:pre-wrap;overflow-wrap:anywhere">${esc(JSON.stringify(task.inputs,null,2))}</pre></details>` : ''}
      ${task.input_state === 'captured' ? '<p class="muted">작업을 시작할 때 지정한 출처에서 받은 입력입니다. 이후 다른 작업의 결과로 바뀌지 않습니다.</p>' : ''}
      <div class="todo-form"><label>확인자 <input id="tdBy" value="${esc(I.form.by)}"></label>${fields.map(control).join('')}
      <button class="btn primary" id="tdDone">작업 제출</button><span class="neg">${esc(I.msg)}</span></div></section>`;
    $('#tdBy').addEventListener('input', e => I.form.by = e.target.value);
    fields.forEach((f,i) => $('#tdField'+i).addEventListener('input', e => I.fieldValues[f.key] = e.target.value));
    $('#tdDone').addEventListener('click', () => {
      try {
        const output = {};
        fields.forEach((f,i) => {
          const value = $('#tdField'+i).value;
          if (!value.trim()) { if (f.required!==false) throw Error((f.text || f.key)+' 값을 입력하세요'); return; }
          output[f.key] = ['object','array','boolean'].includes(f.type) ? JSON.parse(value) : ['number','integer'].includes(f.type) ? Number(value) : value;
        });
        submitTask(task,output);
      } catch(e) { I.msg=e.message; renderTodoPanel(); }
    });
  }

  function timerFor(task) {
    if (!I.view || I.view.instance.proc_inst_id !== task.proc_inst_id) return null;
    const def = I.view.definition || {}, activity = (def.activities || []).find(a => a.id === task.activity_id) || {};
    const ids = (def.events || []).filter(e => e.attachedTo===task.activity_id || (activity.attachedEvents || []).includes(e.id)).map(e => e.id);
    return I.view.workitems.find(w => ids.includes(w.activity_id) && w.status==='IN_PROGRESS');
  }

  function renderAskPanel(task) {
    const box = $('#todoPanel');
    const events = (I.view && I.view.events || []).filter(e => e.todo_id === task.id);
    const answered = new Set(events.filter(e => e.event_type === 'human_response').map(e => e.job_id));
    const open = events.filter(e => e.event_type === 'human_asked' && !answered.has(e.job_id)).slice(-1)[0];
    if (!open) { box.innerHTML = `<section class="todo-panel"><h3>에이전트 질문 — ${esc(task.activity_name)}</h3><p class="muted">질문 이벤트를 읽는 중…</p></section>`; return; }
    const d = open.data || {};
    const options = Array.isArray(d.options) ? d.options.filter(x => typeof x === 'string') : [];
    box.innerHTML = `<section class="todo-panel ask"><h3>에이전트가 묻습니다 — ${esc(task.activity_name)}</h3>
      <div class="summary">${esc(humanQuestionText(d))}</div>
      ${options.length ? `<div class="human-options">${options.map((o,i) => `<button class="btn" type="button" data-human-option="${i}">${esc(o)}</button>`).join(' ')}</div>` : ''}
      <div class="todo-form"><label>답변 <textarea id="tdAnswer" rows="2">${esc(I.form.reason)}</textarea></label><label>담당자 <input id="tdBy" value="${esc(I.form.by)}"></label>
      <button class="btn primary" id="tdAnswerGo">답변 보내기</button><span class="neg">${esc(I.msg)}</span></div>
      <p class="muted">에이전트는 같은 작업을 이어서 답변을 반영합니다. 이 답변은 설비 조치를 승인하거나 도구 권한을 바꾸지 않습니다.</p></section>`;
    box.querySelectorAll('[data-human-option]').forEach(button => button.addEventListener('click', () => {
      I.form.reason = options[Number(button.dataset.humanOption)]; $('#tdAnswer').value = I.form.reason;
    }));
    $('#tdAnswer').addEventListener('input', e => I.form.reason = e.target.value);
    $('#tdBy').addEventListener('input', e => I.form.by = e.target.value);
    $('#tdAnswerGo').addEventListener('click', async () => {
      if (I.busy) return; I.busy = true;
      try { await postJ(API.process + `/api/todolist/${encodeURIComponent(task.id)}/human-response`, { job_id: open.job_id, answer: I.form.reason, by: I.form.by || '담당자' }); I.msg = ''; I.form.reason = ''; }
      catch (e) { I.msg = e.message; }
      finally { I.busy = false; await load(true); }
    });
  }

  function renderSelectPanel(task) {
    const box = $('#todoPanel');
    const d = I.dec;
    if (!d) { box.innerHTML = `<section class="todo-panel"><h3>조치 카드 선택</h3><p class="muted">에이전트가 제출한 조치 카드를 불러오는 중… (decision_id ${esc(I.decId || '없음')})</p></section>`; return; }
    const opts = d.options || [];
    if (!I.form.option) I.form.option = d.recommended || (opts.find(o => o.feasible) || opts[0] || {}).id;
    const chosen = opts.find(o => o.id === I.form.option) || {};
    const cmd = p => (chosen.actions || []).find(a => a.kind === 'command' && a.param === p);
    const fanA = cmd('fan_pct'), loadA = cmd('load_pct'), pumpA = cmd('pump');
    if (I.form.cardFor !== I.form.option) { I.form.fan = fanA ? fanA.value : null; I.form.load = loadA ? loadA.value : null; I.form.cardFor = I.form.option; }
    const parameters = { ...(fanA ? {fan_pct:I.form.fan} : {}), ...(loadA ? {load_pct:I.form.load} : {}) };
    const review = window.hydCards?.reviewMatches(I.form.review,d.id,I.form.option,parameters,{workitem:task.id}) ? I.form.review : null;
    const reviewed = review?.snapshot?.options?.[0];
    const changed = (fanA && I.form.fan !== fanA.value) || (loadA && I.form.load !== loadA.value);
    const canApprove = reviewed ? reviewed.feasible : chosen.feasible && !changed;
    const roles = Object.entries(review?.snapshot?.roles || d.roles || {}).sort((a, b) => a[1].level - b[1].level);
    if (!I.form.role) I.form.role = (chosen.approver || {}).id || (roles[0] || [''])[0];
    const cards = window.hydCards ? opts.map(o => hydCards.cardHtml(o, { rec: d.recommended, chosen: d.chosen, selectable: true, reviewable:true, selected: I.form.option === o.id, pending: true, maxAbs: Math.max(1, ...opts.map(x => Math.abs(x.score || 0))) })).join('')
      : opts.map(o => `<label class="todo-opt${I.form.option === o.id ? ' sel' : ''}${o.feasible ? '' : ' infeasible'}"><input type="radio" name="hopt" value="${esc(o.id)}" ${I.form.option === o.id ? 'checked' : ''} ${o.feasible ? '' : 'disabled'}>
          <div><b>${o.rank}. ${esc(o.sopId)} ${esc(o.name)}${o.id === d.recommended ? ' · 권고' : ''}</b><span class="muted">점수 ${esc(o.score)} · 승인 ${esc((o.approver || {}).name || '–')}${o.feasible ? '' : ' · 규정상 제외'}</span></div></label>`).join('');
    const timer = timerFor(task);
    const maintenance = (chosen.actions || []).filter(a => a.code === 'WO_CREATE');
    const hasWorkOrder = (I.view?.definition?.activities || []).some(a => a.tool === 'enterprise:WO_CREATE');
    const maintenanceText = maintenance.length ? maintenance.map(a => a.value ?? a.name ?? '작업지시').join(', ')
      : `선택한 조치 이후 정비 점검: ${chosen.name || ''}`;
    box.innerHTML = `<section class="todo-panel"><h3>조치 카드 선택 (HITL) — ${esc(who(task.user_id))}${timer && timer.due_date ? ` · 기한 ${esc(UI.time(timer.due_date))} 지나면 생산관리자로 넘어갑니다` : ''}</h3>
      <div class="summary">${esc(d.explanation || '')}</div>
      <div class="todo-opts">${cards}</div>
      <div id="tdReviewed">${reviewed ? `<h3>현재 입력으로 다시 계산한 검토본</h3><p>생성: ${esc(UI.dateTime(review.created))}. 이 검토본을 확인한 뒤 결정하면 아래 조치값이 적용됩니다.</p>${hydCards.cardHtml(reviewed)}<p>${esc(review.snapshot.explanation || '')}</p>` : '<p class="muted">조치값을 바꾸면 새 예측을 먼저 검토해야 합니다. 제외된 카드도 현재 조건으로 다시 계산할 수 있습니다.</p>'}</div>
      ${hasWorkOrder ? `<p><b>함께 승인할 후속 작업지시:</b> ${esc(maintenanceText)}. 설비 제어를 고르면 회복 확인 뒤 발행하며, 작업지시만 고르면 바로 발행합니다. 이 프로세스의 종결은 작업지시 접수까지이며 실제 정비 완료는 CMMS에서 확인합니다.</p>` : ''}
      <div class="todo-form">
        ${pumpA ? `<span class="muted">운전 펌프 → <b>${esc(pumpA.value)}</b> (PLC PumpSelect)</span>` : ''}
        ${fanA ? `<label>팬 속도 <input type="range" id="tdFan" min="${fanA.min ?? 0}" max="${fanA.max ?? 100}" value="${I.form.fan}"><output>${I.form.fan}</output> %</label>` : ''}
        ${loadA ? `<label>펌프 부하 <input type="range" id="tdLoad" min="${loadA.min ?? 60}" max="${loadA.max ?? 100}" value="${I.form.load}"><output>${I.form.load}</output> %</label>` : ''}
        <label>결정자 <input id="tdBy" value="${esc(I.form.by)}"></label>
        <label>역할 <select id="tdRole">${roles.map(([id, r]) => `<option value="${esc(id)}" ${id === I.form.role ? 'selected' : ''}>${esc(r.name)} (직급 ${r.level})</option>`).join('')}</select></label>
        <label>판단 사유 <textarea id="tdReason" rows="2">${esc(I.form.reason)}</textarea></label>
        <button class="btn" id="tdPreview" ${I.busy || !I.form.option ? 'disabled' : ''}>새 예측 검토</button>
        <button class="btn primary" id="tdGo" ${canApprove && !I.busy ? '' : 'disabled'}>${reviewed ? '검토한 조치로 결정' : '이 카드로 결정'}</button><span class="neg">${esc(I.msg)}</span></div>
      <p class="muted">고른 카드의 승인 역할보다 낮은 역할이면 process가 거절합니다(403). 제출되면 gw:control 이 즉시 제어 / 작업지시 경로를 가르고, 결정은 온톨로지에 판단 사례로 기록됩니다.</p></section>`;
    box.querySelectorAll('input[name=hopt]').forEach(r => r.addEventListener('change', () => { I.form.option = r.value; I.form.review=null; I.msg = ''; const o = opts.find(x => x.id === r.value); if (o && o.approver) I.form.role = o.approver.id; renderTodoPanel(); }));
    const on = (id, ev, fn) => { const e = document.getElementById(id); if (e) e.addEventListener(ev, fn); };
    const invalidate = () => { I.form.review=null; $('#tdGo').disabled=true; $('#tdReviewed').textContent='조치값이 바뀌었습니다. 새 예측을 검토하세요.'; };
    on('tdFan', 'input', e => { I.form.fan = +e.target.value; e.target.nextElementSibling.textContent = e.target.value; invalidate(); });
    on('tdLoad', 'input', e => { I.form.load = +e.target.value; e.target.nextElementSibling.textContent = e.target.value; invalidate(); });
    on('tdFan','change',renderTodoPanel); on('tdLoad','change',renderTodoPanel);
    on('tdBy', 'input', e => I.form.by = e.target.value);
    on('tdRole', 'change', e => { I.form.role = e.target.value; I.msg = ''; });
    on('tdReason', 'input', e => I.form.reason = e.target.value);
    on('tdGo', 'click', () => selectCard(task));
    on('tdPreview','click',() => previewCard(task,parameters));
  }

  async function previewCard(task,parameters) {
    if (I.busy) return; I.busy=true; I.msg=''; renderTodoPanel();
    const form=I.form, decision=I.decId, option=form.option;
    try { const review=await postJ(API.process+`/api/todolist/${encodeURIComponent(task.id)}/decision-preview`,
      {decision,option,parameters});
      if(I.form===form && I.decId===decision && I.form.option===option) I.form.review=review;
    }
    catch(e) { if(I.form===form) { I.form.review=null; I.msg=e.message; } }
    finally { I.busy=false; renderTodoPanel(); }
  }

  async function selectCard(task) {
    if (I.busy) return; I.busy = true;
    try {
      await postJ(API.process + `/api/todolist/${encodeURIComponent(task.id)}/select`, { decision: I.decId, option: I.form.option, by: I.form.by || '승인자', role: I.form.role,
        reason: I.form.reason, fan_pct: I.form.fan, load_pct: I.form.load, review_id:matchingReviewId(task) });
      I.msg = '';
    } catch (e) { I.msg = e.message; }
    finally { I.busy = false; await load(true); }
  }
  function matchingReviewId(task) {
    const option=I.dec?.options?.find(o=>o.id===I.form.option);
    const cmd=p=>option?.actions?.find(a=>a.kind==='command' && a.param===p);
    const parameters={...(cmd('fan_pct') ? {fan_pct:I.form.fan} : {}),...(cmd('load_pct') ? {load_pct:I.form.load} : {})};
    return window.hydCards?.reviewMatches(I.form.review,I.decId,I.form.option,parameters,{workitem:task.id}) ? I.form.review.id : null;
  }
  async function submitTask(task, output) {
    if (I.busy) return; I.busy = true;
    try { await postJ(API.process + `/api/todolist/${encodeURIComponent(task.id)}/submit`, { output, by: I.form.by || '확인자' }); I.msg = ''; }
    catch (e) { I.msg = e.message; }
    finally { I.busy = false; await load(true); }
  }

  /* ------------------------------------------------ instances */
  function renderList() {
    const box = $('#instList');
    if (!I.instances.length) { box.innerHTML = '<div class="muted">아직 인스턴스가 없습니다. 결함 시뮬레이션에서 열화를 주입하면 경보가 인스턴스를 엽니다.</div>'; return; }
    box.innerHTML = '';
    const names = {};
    ((I.view && I.view.definition && I.view.definition.activities) || []).forEach(a => { names[a.id] = a.name; });
    I.instances.forEach(x => {
      const started = new Date(x.start_date), ended = x.end_date ? new Date(x.end_date) : null;
      const span = ((ended || new Date()) - started) / 60000;
      const when = x.status === 'RUNNING' ? `${span < 1 ? '방금 시작' : Math.round(span) + '분 경과'}` : `${ended ? Math.max(1, Math.round(span)) + '분 만에 ' : ''}${UI.status(x.status)}`;
      const steps = (x.current_activity_ids || []).map(id => `<span class="chip step-chip">${esc(names[id] || id.replace(/^task:|^ev:/, ''))}</span>`).join('');
      const it = el('div', 'item inst-card ' + esc(x.status) + (x.proc_inst_id === I.sel ? ' sel' : ''), `<div class="row"><strong>${esc(x.proc_inst_name)}</strong>${pill(x.status)}</div>
        <div class="steps">${steps || (x.end_event ? `<span class="chip end">${esc(x.end_event)}</span>` : '')}</div>
        <span class="muted">${esc(when)} · ${esc(UI.time(x.start_date))} · <code>${esc(x.proc_inst_id.slice(-8))}</code></span>`);
      keyboardItem(it);
      it.addEventListener('click', () => { I.sel = x.proc_inst_id; load(true); });
      box.appendChild(it);
    });
  }

  function stepsOf(view) {
    const def = view.definition;
    if (!window.hydSteps || !def) return null;
    const workList = view.workitems.filter(w => !(def.events || []).some(e => e.id === w.activity_id))
      .map(w => ({ tracingTag: w.activity_id, status: w.status, taskId: w.id, startDate: w.start_date, endDate: w.end_date, generation: w.generation || 0, task: w }));
    const steps = hydSteps.buildSteps({ activities: def.activities, sequences: def.sequences, events: def.events, gateways: def.gateways,
      workList, whoOf: w => who(w.task.user_id), finished: ['COMPLETED', 'CANCELLED'].includes(view.instance.status) });
    return { steps, groups: hydSteps.groupSteps(steps), summary: hydSteps.summarizeSteps(steps) };
  }
  const stepHtml = s => `<div class="step ${esc(s.state)}${s.mine ? ' mine' : ''}"><b>${esc(s.name)}</b><small>${esc(s.who)}</small><small>${esc(STEP_LABEL[s.state] || s.state)}${s.status && s.status !== 'DONE' && s.state !== 'skipped' ? ' · ' + esc(UI.status(s.status)) : ''}</small></div>`;

  function renderDetail() {
    const box = $('#instDetail');
    if (!I.view) { box.innerHTML = '<div class="empty">인스턴스를 선택하면 작업 흐름 · 변수 · 할일 목록 · 에이전트 도구 기록을 확인할 수 있습니다.</div>'; return; }
    const inst = I.view.instance, v = vars(inst);
    const waitingDependencies = Object.entries(inst.flow_state?.dependency_schedule || {}).filter(([id, spec]) =>
      spec.flow_arrived && I.view.workitems.some(w => w.id === id && w.status === 'TODO'));
    const dependencyWaiting = waitingDependencies.length ? `<section class="box" id="instanceDependencyWaiting"><h3>새 결과를 기다리는 작업</h3>${waitingDependencies.map(([id, spec]) => {
      const task = I.view.workitems.find(w => w.id === id);
      const producers = [...new Set(spec.requires.map(dep => I.view.workitems.find(w => w.id === dep.workitem)?.activity_name || dep.activity))];
      const missingInitial = (spec.waiting_for || []).filter(x => x.reason === 'initial_input_unavailable').map(x => x.variable);
      const reason = missingInitial.length ? `시작 입력 ${missingInitial.join(', ')}이 없습니다. 입력을 확인해 새 실행을 시작하세요.`
        : (spec.waiting_for || []).some(x => x.reason === 'fresh_output_unavailable') ? '지정한 생산 작업에 필요한 결과값이 없어 대기 중입니다.'
        : `${producers.join(', ')}의 결과가 확정되면 시작합니다.`;
      return `<p><b>${esc(task?.activity_name || spec.activity)}</b>: ${esc(reason)}</p>`;
    }).join('')}</section>` : '';
    const st = stepsOf(I.view);
    let flow;
    if (st) {
      flow = st.groups.map((g, i) => {
        const arrow = i ? '<span class="arrow">→</span>' : '';
        if (g.type === 'step') return arrow + stepHtml(g.step);
        return arrow + `<div class="branch ${g.decided ? 'decided' : 'open'}"><small class="gw">${esc(g.name || '분기')}</small>${g.lanes.map(l => `<div class="lane ${esc(l.state)}">${l.steps.map(stepHtml).join('<span class="arrow">→</span>')}</div>`).join('')}</div>`;
      }).join('');
      const s = st.summary;
      flow = `<div class="inst-summary">${s.done}/${s.total} 단계 완료${s.current ? ` · 지금: <b>${esc(s.current.name)}</b>` : s.next ? ` · 다음: <b>${esc(s.next.name)}</b>` : s.finished ? ' · 끝' : ''}</div><div class="inst-tl">${flow}</div>`;
    } else {
      flow = `<div class="inst-tl">${I.view.timeline.map((t, i) => `${i ? '<span class="arrow">→</span>' : ''}<div class="step ${esc(t.status || '')}"><b>${esc(t.name)}</b><small>${esc(who(t.performer))}</small><small>${esc(UI.status(t.status) || '예정')}</small></div>`).join('')}</div>`;
    }
    const varRows = (inst.variables_data || []).map(row => {
      const value = row.value, name = row.name || row.key;
      const body = value !== null && typeof value === 'object' ? `<details><summary>구조화된 값</summary><pre>${esc(JSON.stringify(value,null,2))}</pre></details>` : esc(value === true?'예':value === false?'아니오':value ?? '값 없음');
      const source = (inst.variable_sources || {})[row.key];
      const producer = source?.kind === 'workitem' ? I.view.workitems.find(w => w.id === source.id) : null;
      const origin = source?.kind === 'input' ? '출처: 시작 입력' : source?.kind === 'workitem'
        ? `출처: ${producer?.activity_name || source.activity} · 작업 ${source.id} · 정의 ${source.version}`
        : source?.kind === 'runtime' ? '출처: 서버 전이' : '출처 기록 없음';
      return `<div><span>${esc(name)} <small>${esc(row.key)}</small></span>${body}<p class="muted" style="overflow-wrap:anywhere">${esc(origin)}</p></div>`;
    }).join('');
    const inputSnapshot = `<section class="box" id="instanceInputSnapshot"><h3>시작 입력과 현재 결과</h3>
      <p>새 실행은 시작할 때 받은 입력을 보존합니다. 아래 현재 변수는 작업 결과에 따라 바뀔 수 있으며, 값마다 마지막으로 기록한 출처를 표시합니다.</p>
      ${inst.initial_variables == null ? '<p>이전 실행에는 시작 입력 원문이 별도로 저장되지 않았습니다. 현재 결과를 최초 입력으로 간주하지 않습니다.</p>'
        : `<details><summary>보존된 시작 입력 보기</summary><pre>${esc(JSON.stringify(inst.initial_variables, null, 2))}</pre></details>`}</section>`;
    const rows = I.view.workitems.map(w => `<tr class="${esc(w.status)}"><td>${esc(w.activity_name)}<br><small class="muted">${esc(w.activity_id)} · 세대 ${esc(w.generation || 0)}</small>${w.supersedes_id ? `<details><summary>이전 작업 ID</summary><code style="overflow-wrap:anywhere">${esc(w.supersedes_id)}</code></details>` : ''}</td><td>${pill(w.status)}${w.draft_status ? `<br><small class="muted">${esc(w.draft_status)}</small>` : ''}</td>
      <td>${esc(who(w.user_id))}${w.agent_orch ? `<br><small class="muted">${esc(w.agent_orch)}${w.agent_mode ? ' · ' + esc(w.agent_mode) : ''}${w.consumer ? ' · ' + esc(w.consumer) : ''}</small>` : ''}${w.agent_orch && w.agent_mode && inst.status === 'RUNNING' && (w.status === 'PENDING' || (w.status === 'IN_PROGRESS' && (w.draft_status === 'FAILED' || w.draft_status === 'CANCELLED'))) ? `<br><button class="btn" data-close-task="${esc(w.id)}" title="멈춘 에이전트 작업을 사유와 함께 닫습니다. 사건이 진행 중이면 거절됩니다.">작업 닫기</button>` : ''}${w.agent_orch && w.agent_mode && inst.status === 'RUNNING' && w.status === 'IN_PROGRESS' && w.draft_status === 'STARTED' && w.consumer ? `<br><button class="btn" data-cancel-task="${esc(w.id)}" title="실행 중인 에이전트 작업을 취소합니다. 워커가 다음 확인(2초 안)에서 멈추고 점유를 놓습니다. 그 뒤 작업 닫기 또는 재작업으로 처리합니다.">실행 취소</button>` : ''}</td>
      <td>${esc(UI.time(w.start_date))}${w.end_date ? ' → ' + esc(UI.time(w.end_date)) : ''}${w.due_date && !w.end_date ? '<br><small class="muted">기한 ' + esc(UI.time(w.due_date)) + '</small>' : ''}</td>
      <td class="log">${esc(w.log || '')}${w.output && Object.keys(w.output).length ? `<details><summary>출력 ${Object.keys(w.output).filter(k => k !== 'text').join(', ') || 'text'}</summary><pre>${esc(JSON.stringify(w.output, null, 1).slice(0, 1500))}</pre></details>` : ''}${w.gateway_decisions ? `<details><summary>게이트웨이 판정</summary><pre>${esc(JSON.stringify(w.gateway_decisions, null, 1).slice(0, 800))}</pre></details>` : ''}</td></tr>`).join('');
    const events = I.view.events.slice(-80).reverse().map(e => UI.eventRecord({ time: e.timestamp, name: e.job_id==='TASK_REVIEW_REQUIRED' ? e.job_id : e.event_type, actor: e.crew_type || '', detail: eventDetail(e), raw: e.data })).join('');
    box.innerHTML = `<h2>${esc(inst.proc_inst_name)} ${pill(inst.status)} <small class="muted">${esc(inst.proc_inst_id)}</small></h2>
      <div class="muted">정의 ${esc(inst.proc_def_id)} · 버전 ${esc(inst.proc_def_version)} · 시작 ${esc(UI.dateTime(inst.start_date))}${inst.end_date ? ' · 종료 ' + esc(UI.dateTime(inst.end_date)) + ' (' + esc(inst.end_event || '') + ')' : ''} · 참여 ${esc((inst.participants || []).map(who).join(', ') || '–')}</div>
      ${inst.status === 'RUNNING' && inst.flow_state?.end_arrivals?.length ? '<p class="box" id="instanceEndWaiting">일부 경로가 종료 지점에 도달했습니다. 남은 작업이 끝나면 전체 실행이 종료됩니다.</p>' : ''}
      ${dependencyWaiting}
      <h3>작업 흐름 · 현재 세대 ${esc(inst.rework_generation || 0)}</h3>${flow}${approvalHtml()}${workOrderRetryHtml()}
      <div id="taskDeferralPanel"></div><div id="effectsPanel"></div><div id="reworkPanel"></div>
      ${(I.view.reworks || []).length ? `<section class="box" id="reworkHistory"><h3>재작업 요청 이력</h3>${I.view.reworks.map(r => `<p>세대 ${esc(r.generation)} · ${esc(r.request.by)} (${esc(who(r.request.role))}) · ${esc(r.request.reason)}</p><details><summary>요청과 새 작업 연결</summary><pre>${esc(JSON.stringify({request_id:r.request_id, previous:r.request.workitem_id, started:r.result.start_workitem}, null, 2))}</pre></details>`).join('')}</section>` : ''}
      ${inputSnapshot}<h3>변수 (variables_data)</h3><div class="inst-vars">${varRows || '<div class="muted">없음</div>'}</div>
      <h3>작업 (todolist)</h3><table class="inst-table"><thead><tr><th>작업</th><th>상태</th><th>수행자</th><th>시각</th><th>기록 · 출력</th></tr></thead><tbody>${rows}</tbody></table>
      <h3>에이전트 실행 기록 (events) <small class="muted">${I.view.events.length}건</small></h3><div class="inst-events">${events || '<div class="muted">아직 기록이 없습니다.</div>'}</div>
      ${graphHtml()}`;
    window.hydRework?.mount(box.querySelector('#reworkPanel'), {view:I.view,by:I.form.by,changed:()=>load(true)});
    window.hydEffects?.mount(box.querySelector('#effectsPanel'), {view:I.view,by:I.form.by,changed:()=>load(true)});
    window.hydTaskDeferral?.mount(box.querySelector('#taskDeferralPanel'), {view:I.view,by:I.form.by,changed:()=>load(true)});
    box.querySelectorAll('[data-close-task]').forEach(button => button.addEventListener('click', async () => {
      if (I.busy) return;
      const reason = window.prompt('이 에이전트 작업을 닫는 사유를 적으세요 (기록에 남습니다)');
      if (!reason || !reason.trim()) return;
      I.busy = true; button.disabled = true;
      try { await postJ(API.process + `/api/todolist/${encodeURIComponent(button.dataset.closeTask)}/close`, { by: I.form.by || '확인자', reason: reason.trim() }); I.msg = ''; }
      catch (e) { I.msg = e.message; }
      finally { I.busy = false; await load(true); }
    }));
    box.querySelectorAll('[data-cancel-task]').forEach(button => button.addEventListener('click', async () => {
      if (I.busy) return;
      const reason = window.prompt('실행 중인 에이전트 작업을 취소하는 사유를 적으세요 (기록에 남습니다)');
      if (!reason || !reason.trim()) return;
      I.busy = true; button.disabled = true;
      try { await postJ(API.process + `/api/todolist/${encodeURIComponent(button.dataset.cancelTask)}/cancel`, { by: I.form.by || '확인자', reason: reason.trim() }); I.msg = ''; }
      catch (e) { I.msg = e.message; }
      finally { I.busy = false; await load(true); }
    }));
    box.querySelectorAll('[data-approval-retry], [data-work-order-retry]').forEach(button => button.addEventListener('click', async () => {
      if (I.busy) return;
      const panel = button.closest('[data-approval-panel]');
      const by = panel.querySelector('[data-retry-by]').value.trim();
      const role = panel.querySelector('[data-retry-role]').value;
      if (!by || !role) { I.msg = '복구 요청자와 역할을 입력하세요'; await load(true); return; }
      I.busy = true; button.disabled = true;
      try {
        const workOrder = button.dataset.workOrderRetry;
        const path = workOrder ? `${encodeURIComponent(workOrder)}/work-order-retry` : `${encodeURIComponent(button.dataset.approvalRetry)}/approval-retry`;
        await postJ(API.process + `/api/todolist/${path}`, {by,role});
        I.msg = '';
      } catch(e) { I.msg = e.message; }
      finally { I.busy = false; await load(true); }
    }));
    box.querySelectorAll('[data-approval-discard-preview]').forEach(button => {
      const panel = button.closest('[data-approval-panel]');
      const result = panel.querySelector('[data-discard-preview]');
      panel.querySelectorAll('input,select').forEach(input => input.addEventListener('input', () => { result.innerHTML = ''; }));
      button.addEventListener('click', async () => {
        if (I.busy) return;
        const by = panel.querySelector('[data-retry-by]').value.trim();
        const role = panel.querySelector('[data-retry-role]').value;
        const reason = panel.querySelector('[data-discard-reason]').value.trim();
        if (!by || !role || !reason) { result.textContent = '담당자·역할·폐기 사유를 입력하세요.'; return; }
        const wid = button.dataset.approvalDiscardPreview;
        I.busy = true; button.disabled = true;
        try {
          const evidence = await postJ(API.process + `/api/todolist/${encodeURIComponent(wid)}/approval-discard-preview`, {by,role});
          result.innerHTML = `<p>사건 상태: ${esc(evidence.incident.state)} · 명령 없음 · 기업 실행 원장 ${esc(evidence.enterprise_receipts.length)}건.</p>
            <p>${esc(evidence.outcome)}</p><p>취소할 남은 작업 ${esc(evidence.cancel_workitems.length)}건 · 사유: ${esc(reason)}</p>
            <button class="btn" data-confirm-discard>확인한 승인 폐기 · 인스턴스 취소</button>`;
          const request_id = crypto.randomUUID();
          result.querySelector('[data-confirm-discard]').addEventListener('click', async event => {
            if (I.busy) return;
            I.busy = true; event.currentTarget.disabled = true;
            try {
              await postJ(API.process + `/api/todolist/${encodeURIComponent(wid)}/approval-discard`, {by,role,reason,request_id});
              I.msg = '';
            } catch (e) { I.msg = e.message; }
            finally { I.busy = false; await load(true); }
          });
        } catch (e) { result.textContent = e.message; }
        finally { I.busy = false; button.disabled = false; }
      });
    });
  }
  function workOrderRetryHtml() {
    const failed = I.view.workitems.filter(w => w.tool === 'enterprise:WO_CREATE' && w.status === 'PENDING');
    const approval = (I.view.approvals || []).find(a => a.status === 'DELIVERED');
    const roles = Object.keys(approval?.payload?.plan?._snapshot?.roles || {});
    return failed.map(w => `<section class="approval-status" data-approval-panel><h3>작업지시 발행 실패 · ${esc(w.activity_name)}</h3>
      <p>자동 재시도를 마쳤습니다. 오류를 해결한 뒤 승인했던 같은 내용으로 다시 전달할 수 있습니다. 설비 완화와 작업지시 발행은 별도 결과입니다.</p>
      <p class="neg">${esc(w.log || '')}</p><div class="todo-form">
      <label>복구 요청자 <input data-retry-by value="${esc(I.form.by || '')}"></label>
      <label>역할 <select data-retry-role><option value="">역할 선택</option>${roles.map(r=>`<option value="${esc(r)}">${esc(who(r))}</option>`).join('')}</select></label>
      <button class="btn" data-work-order-retry="${esc(w.id)}" ${I.busy || !roles.length ? 'disabled' : ''}>같은 작업지시 재전달</button></div>
      ${!roles.length ? '<p>승인 원문을 확인할 수 없어 별도 검토가 필요합니다.</p>' : ''}${I.msg ? `<p class="neg">${esc(I.msg)}</p>` : ''}</section>`).join('');
  }
  function approvalHtml() {
    const approvals = I.view.approvals || [];
    if (!approvals.length) return '';
    const names = {PENDING:'승인 접수 · 전달 대기',FAILED:'승인 전달 실패',DELIVERED:'승인 전달 완료',DISCARDED:'승인 폐기 · 이력 보존'};
    return '<h3>승인 전달 상태</h3>' + approvals.map(a => {
      const p = a.payload || {}, snapshot = (p.plan || {})._snapshot || {};
      const option = (p.plan || {}).option || {};
      const roles = Object.keys(snapshot.roles || {});
      const commandPending = I.view.workitems.some(w => w.tool === 'incident:command' && w.status === 'PENDING');
      const reviewable = I.view.instance.status === 'RUNNING' && (a.status==='FAILED' || (a.status==='DELIVERED' && commandPending));
      const retry = reviewable ? `<p>${a.status==='FAILED'?'승인한 내용은 보존됐습니다. 오류를 확인한 뒤 같은 내용을 다시 전달할 수 있습니다.':'조건 변경으로 명령이 보류됐다면 판단 작업에서 새 검토를 시작하세요. 사건이 종료됐다면 아래에서 실행 효과를 확인하고 취소할 수 있습니다.'}</p>
        <div class="todo-form"><label>복구 요청자 <input data-retry-by value="${esc(I.form.by || '')}"></label>
        <label>역할 <select data-retry-role><option value="">역할 선택</option>${roles.map(r=>`<option value="${esc(r)}">${esc(who(r))}</option>`).join('')}</select></label>
        ${a.status==='FAILED'?`<button class="btn" data-approval-retry="${esc(a.todo_id)}" ${I.busy?'disabled':''}>같은 승인 내용 재전달</button>`:''}</div>
        <p>사건이 종료되고 실제 조치가 없음을 확인한 경우에만 승인을 폐기하고 인스턴스를 취소할 수 있습니다. 기존 효과가 있거나 불명확하면 별도 확인이 필요합니다.</p>
        <label>폐기 사유 <input data-discard-reason placeholder="후속 조치를 진행하지 않고 종료하는 이유"></label>
        <button class="btn" data-approval-discard-preview="${esc(a.todo_id)}" ${I.busy?'disabled':''}>폐기 전 사건·실행 효과 확인</button>
        <div data-discard-preview role="status"></div>` : '';
      const discarded = a.status === 'DISCARDED' ? `<p>${(a.history || []).at(-1)?.via==='rework'?'재작업 요청으로 이전 승인을 폐기했습니다. 새 판단과 새 승인이 필요합니다.':'인스턴스를 취소했습니다.'} 이전 승인·오류는 보존되며 정상 회복이나 외부 조치 취소를 뜻하지 않습니다.</p>
        <details><summary>폐기 담당자·사유·확인 근거</summary><pre>${esc(JSON.stringify((a.history || []).at(-1), null, 2))}</pre></details>` : '';
      return `<section class="todo-panel" data-approval-panel><b>${esc(names[a.status] || a.status)}</b>
        · ${esc(option.name || p.option)} · 승인자 ${esc(p.by)} · 전달 시도 ${esc(a.attempts)}회
        ${a.status==='DELIVERED'?'<p class="muted">승인 정보와 선행 업무 조치가 반영됐습니다. 후속 조치와 최종 결과는 작업 흐름에서 확인하세요.</p>':''}
        ${a.error?`<details open><summary>오류 기록</summary><pre>${esc(a.error)}</pre></details>`:''}
        ${retry}${discarded}${I.msg?`<p class="neg">${esc(I.msg)}</p>`:''}</section>`;
    }).join('');
  }
  function graphHtml() {
    const g = I.graph;
    const pending = g && g.projection, cases = I.caseProjection;
    const sync = `<div id="projectionStatus" class="box"><b>그래프 반영 상태</b><p>선택한 실행의 반영 대기: ${pending ? esc(pending.pending)+'건' : '조회하지 못함'}<br>사건·판단 반영 대기(전체): ${cases && !cases.error ? esc(cases.pending)+'건' : '조회하지 못함'}</p>
      ${cases && cases.worker_running === false ? '<p class="neg">사건·판단 복구 처리기가 실행 중이 아닙니다.</p>' : ''}
      ${cases && cases.error ? `<p class="neg">반영 상태 조회 실패: ${esc(cases.error)}</p>` : ''}
      ${cases?.knowledge ? `<p>지식 연결 변경 확인: ${cases.knowledge.last_checked ? esc(UI.dateTime(new Date(cases.knowledge.last_checked*1000).toISOString())) : '첫 확인 대기'}${cases.knowledge.last_error ? '<br><span class="neg">연결 재확인 실패: '+esc(cases.knowledge.last_error)+'</span>' : ''}</p>` : ''}
      ${pending && pending.last_error ? `<details open><summary>${pending.last_error.startsWith('ProjectionConflict:') ? '원천·그래프 비교 필요' : '실행 반영 재시도 중'}</summary><pre>${esc(pending.last_error)}</pre></details>` : ''}
      ${pending?.last_error?.startsWith('ProjectionConflict:') || cases?.items?.some(x=>x.last_error?.startsWith('ProjectionConflict:')) ? '<p class="neg">원천과 그래프의 반영 내역이 맞지 않아 자동 재전송을 보류했습니다. 운영자가 현재 원천과 그래프를 비교한 뒤 복구를 요청해야 합니다.</p>' : ''}
      ${cases && (cases.items || []).some(x => x.last_error) ? `<details><summary>사건·판단 반영 오류</summary><pre>${esc(JSON.stringify(cases.items.filter(x => x.last_error),null,2))}</pre></details>` : ''}
      <small class="muted">업무 원천 저장과 그래프 반영은 별도입니다. 대기가 없어도 아래 연결 경고를 확인하세요.</small></div>`;
    const head = '<h3>온톨로지 Execution 레이어 <small class="muted">Neo4j에 투영된 정의 버전 · 인스턴스 · 작업</small></h3>' + sync;
    if (!g) return head + '<div class="muted">그래프를 읽는 중…</div>';
    if (g.error) return head + `<div class="muted">그래프를 읽지 못했습니다: ${esc(g.error)}</div>`;
    const cy = `<details><summary>이 표를 만든 Cypher (Neo4j 브라우저 localhost:7474 에 그대로 붙여 넣고 <code>$id</code> 에 인스턴스 id 를 넣으면 같은 결과)</summary><pre>${esc(g.cypher)}</pre><pre>${esc(JSON.stringify(g.params))}</pre></details>`;
    const x = g.graph;
    if (!x) return head + '<div class="muted">조회 가능한 실행 그래프가 없습니다. 원천 저장 상태와 반영 대기를 확인하세요.</div>' + cy;
    const pi = x.instance || {};
    const bind = (x.bindings || []).map(b => `<span class="pill">${esc(b.role_name || '')} → ${esc(b.endpoint || '')}</span>`).join(' ');
    const rows = (x.workitems || []).map(w => `<tr class="${esc(w.status)}"><td>${esc(w.activity_name || w.activity_id || '')}<details><summary>작업 ID</summary><code>${esc(w.id)}</code></details></td><td>${pill(w.status)}${w.draft_status ? `<br><small class="muted">${esc(w.draft_status)}</small>` : ''}</td>
      <td>${w.executes ? `${esc(w.executes_name || '')}<br><small class="muted">${esc(w.executes_type || '')}</small><details><summary>노드 ID</summary><code>${esc(w.executes)}</code></details>` : '<span class="muted">–</span>'}</td>
      <td>${w.assigned_to ? `${esc(who(w.assigned_to))}<br><small class="muted">kind ${esc(w.assigned_kind || '')}</small>` : '<span class="muted">–</span>'}</td>
      <td>${esc(w.agent_orch || '')}${w.agent_mode ? ' · ' + esc(w.agent_mode) : ''}${w.tool ? '<br><small class="muted">' + esc(w.tool) + '</small>' : ''}</td></tr>`).join('');
    const warnings = (x.warnings || []).map(w => `<div class="neg">투영 확인 필요: ${esc(w)}</div>`).join('');
    const version = x.definition || {};
    return head + warnings + `<div class="muted">실행 정의 <b>${esc(version.id || '')}</b> · 버전 ${esc(version.version || x.process.version || '')}<br><code>(:ProcessInstance {id: ${esc(pi.id || '')}})</code> ${pill(pi.status)} -[:INSTANCE_OF {version ${esc(x.process.version ?? '')}}]-&gt; <code>${esc(x.process.id || '')}</code>${x.asset ? ` · -[:ON_ASSET]-&gt; ${esc(x.asset)}` : ''}${x.incident ? ` · -[:HANDLES]-&gt; ${esc(x.incident)}` : ''}<br>ROLE_BOUND ${bind || '<span class="muted">없음</span>'}</div>
      <table class="inst-table"><thead><tr><th>작업</th><th>상태</th><th>실행 노드<br><small>EXECUTES</small></th><th>담당자<br><small>ASSIGNED_TO</small></th><th>처리 방식 · 도구</th></tr></thead><tbody>${rows}</tbody></table>${cy}`;
  }
  function eventDetail(e) {
    const d = e.data || {};
    if (d.recovery === 'new_judgment_and_consent') return '현재 조건 검사로 명령을 보류했습니다. 판단 작업에서 새 검토와 승인을 진행하세요. ' + ((d.assessment || {}).reasons || []).join('; ');
    if (d.tool) return `${d.tool}${d.input ? ' ' + JSON.stringify(d.input).slice(0, 120) : ''}${d.output ? ' → ' + String(d.output).slice(0, 120) : ''}`;
    if (d.goal) return `${d.goal}${d.name ? ' · ' + d.name : ''}`;
    if (d.text || d.question) return humanQuestionText(d).slice(0, 160);
    return d.message || d.note || d.content || d.friendly || d.raw_error || (d.output_keys ? '출력 ' + d.output_keys.join(', ') : '') || (d.answer ? '답변 ' + d.answer : '');
  }

  /* ------------------------------------------------ hooks */
  window.hydInstancesSelect = id => { I.sel=id; I.taskSel=null; load(true); };
  Object.assign(UI.eventNames, { task_started: '작업 시작', task_completed: '작업 완료', task_working: '작업 진행', tool_usage_started: '도구 호출', tool_usage_finished: '도구 결과',
    human_asked: '사람에게 질문', human_response: '사람의 답변', task_cancelled: '작업 취소', error: '오류',
    INSTANCE_STARTED: '인스턴스 시작', INCIDENT_OPENED: '인시던트 생성', TASK_COMPLETED: '작업 완료', TASK_PENDING: '진행 불가(조건 미충족)', TASK_REVIEW_REQUIRED: '새 판단·승인 필요', SELECT_TIMEOUT: '선택 시간 초과' });
  const _sel = selectTab;
  selectTab = function (name) { _sel(name); if (name === 'instances') load(true); };
  window.hydApp.selectTab = selectTab;
  $('#instReload').addEventListener('click', () => load(true));
  $('#instStatus').addEventListener('change', e => { I.status = e.target.value || null; I.sel = null; load(true); });
  setInterval(() => load(false), 2000);
  window.hydInstances = { I, load };
})();
