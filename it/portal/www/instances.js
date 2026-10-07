/* 처리 건 · 내 차례 (instance mode, loaded after hitl.js and instanceSteps.js).
   process 서비스의 instance-mode API 를 읽는다:
     GET  /api/process/mode · /api/process/definition · /api/instances · /api/instances/{id} · /api/todolist?status=IN_PROGRESS · /api/decisions/{id}
     POST /api/todolist/{id}/select (task:select) · /api/todolist/{id}/submit (task:escalate 등 폼) · /api/todolist/{id}/human-response
   상태 의미는 ProcessGPT 와 같다: TODO 예정 → IN_PROGRESS 진행 중(내 차례) → SUBMITTED 제출됨(엔진 차례) → DONE · CANCELLED · PENDING.
   단계 계산은 process-gpt-vue3 의 instanceSteps.js(window.hydSteps) 그대로다.
   A122 (UIUX_PLAN §1.3 · §1.4 · §5): summary cards → 에이전트 활동 + 내 차례 → 폼(사건 / 선택 / 사유·담당) → 목록 + 상세 3탭(결과 · 흐름 · 기록). */
(function () {
  const I = { mode: null, taskSel: null, taskView: null, fieldValues: {}, fieldTask: null, instances: [], sel: null, view: null, todo: [], dec: null, decId: null, asked: [],
              form: { option: null, role: null, by: 'OP-17', reason: '', fan: null, load: null }, msg: '', busy: false, sig: null, tab: 'result', closing: null };
  const who = id => UI.who(id);
  const chip = s => UI.chip(s);
  const STEP_LABEL = { done: UI.t('done'), current: UI.status('IN_PROGRESS'), skipped: UI.status('SKIPPED'), todo: UI.status('TODO') };
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
    const task = I.todo.find(t => t.id === I.taskSel && t.proc_inst_id === I.sel) || I.todo.find(t => t.proc_inst_id === I.sel);
    I.taskView = null;
    if (task) { try { I.taskView = await getJ(API.process + '/api/todolist/' + encodeURIComponent(task.id)); } catch (e) { I.msg = e.message; } }
    const selectTask = I.taskView && I.taskView.tool === 'formHandler:select_card' ? I.taskView : null;
    const decId = selectTask ? await decisionIdOf(selectTask) : null;
    if (decId !== I.decId) { I.decId = decId; I.dec = null; I.form = { option: null, role: null, by: I.form.by, reason: '', fan: null, load: null }; }
    if (I.decId && !I.dec) { try { I.dec = await getJ(API.process + '/api/decisions/' + encodeURIComponent(I.decId)); } catch (e) { I.dec = null; } }
    const sig = JSON.stringify([I.status, I.instances.map(x => [x.proc_inst_id, x.status, x.current_activity_ids]), I.todo.map(t => t.id), I.asked.map(t => [t.id, t.draft_status]), I.sel, I.taskView,
      I.view && I.view.workitems.map(w => [w.id, w.status, w.draft_status]), I.view && I.view.events.length,
      I.view && (I.view.approvals || []).map(a => [a.todo_id, a.status, a.attempts, a.error]), I.dec && I.dec.state, I.msg,
      I.graph && (I.graph.error || I.graph.graph || 'none'), I.graph && I.graph.projection, I.caseProjection, I.tab]);
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

  /* ------------------------------------------------ summary cards (UIUX_PLAN §1.4: 진행 중 · 내 차례 · 질문 only) */
  function renderBanner() {
    const b = $('#instBanner');
    if (!I.mode || I.mode.error) { b.innerHTML = `<div class="inst-banner off">${esc(UI.t('inst.noConn'))} ${esc((I.mode || {}).error || '')}</div>`; return; }
    if (I.mode.mode !== 'instance') {
      b.innerHTML = `<div class="inst-banner off">${esc(UI.t('inst.off'))}</div>`;
      $('#todoList').innerHTML = ''; $('#instList').innerHTML = ''; $('#instDetail').innerHTML = ''; $('#todoPanel').innerHTML = '';
      return;
    }
    const running = I.instances.filter(x => x.status === 'RUNNING').length;
    b.innerHTML = `<div class="stat-cards">
      <div class="card"><span>${esc(UI.t('inst.running'))}</span><b class="num">${running}</b></div>
      <div class="card${I.todo.length ? ' hot' : ''}"><span>${esc(UI.t('inst.myTurn'))}</span><b class="num">${I.todo.length}</b></div>
      <div class="card${I.asked.length ? ' hot' : ''}"><span>${esc(UI.t('inst.asked'))}</span><b class="num">${I.asked.length}</b></div>
    </div>`;
  }

  /* ------------------------------------------------ 내 차례 (human IN_PROGRESS rows) + agent questions */
  function renderTodo() {
    const box = $('#todoList');
    box.innerHTML = '';
    if (!I.todo.length && !I.asked.length) { box.innerHTML = UI.empty(UI.t('inst.noTodo'), UI.t('inst.noTodoSub'), 'compact'); $('#todoPanel').innerHTML = ''; return; }
    I.asked.forEach(t => {
      const inst = I.instances.find(x => x.proc_inst_id === t.proc_inst_id) || {};
      const it = el('div', 'item ask' + (t.proc_inst_id === I.sel ? ' sel' : ''), `<div class="row"><strong>${esc(UI.t('inst.askTitle'))} — ${esc(t.activity_name)}</strong>${chip('HUMAN_ASKED')}</div><span class="sub">${esc(inst.proc_inst_name || t.proc_inst_id)}</span>`);
      keyboardItem(it);
      it.addEventListener('click', () => { I.sel = t.proc_inst_id; I.taskSel = t.id; load(true); });
      box.appendChild(it);
    });
    I.todo.forEach(t => {
      const inst = I.instances.find(x => x.proc_inst_id === t.proc_inst_id) || {};
      const it = el('div', 'item' + (t.proc_inst_id === I.sel ? ' sel' : ''), `<div class="row"><strong>${esc(UI.flowName(t.activity_name))}</strong>${chip(t.status)}</div><span class="sub">${esc(inst.proc_inst_name || t.proc_inst_id)} · ${esc(who(t.user_id))}</span>`);
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
    if (!fields) { box.innerHTML = `<div class="neg">${esc(UI.t('inst.noForm'))}</div>`; return; }
    if (I.fieldTask !== task.id) { I.fieldTask = task.id; I.fieldValues = {}; }
    const control = (f, index) => {
      const id = 'tdField' + index, val = I.fieldValues[f.key] ?? '';
      let input;
      if (f.type === 'select' || f.type === 'boolean') {
        const options = f.type === 'boolean' ? [['true', UI.t('yes')], ['false', UI.t('no')]] : (f.items || []).flatMap(x => typeof x === 'object' ? Object.entries(x) : [[x, x]]);
        input = `<select id="${id}"><option value="">선택하세요</option>${options.map(([v, l]) => `<option value="${esc(v)}" ${String(val) === String(v) ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select>`;
      } else if (['textarea', 'object', 'array'].includes(f.type)) {
        input = `<textarea id="${id}" rows="3" placeholder="${['object', 'array'].includes(f.type) ? 'JSON으로 입력' : ''}">${esc(val)}</textarea>`;
      } else input = `<input id="${id}" type="${['number', 'integer'].includes(f.type) ? 'number' : 'text'}" step="${f.type === 'integer' ? '1' : 'any'}" value="${esc(val)}">`;
      // labels of the definition are the engine's; the two known forms get their user names here (명칭표)
      const label = ({ note: UI.t('form.note') })[f.key] || f.text || f.key;
      return UI.field({ label, required: f.required !== false, cls: ['textarea', 'object', 'array'].includes(f.type) ? 'wide' : '', input });
    };
    const isEscalate = task.tool === 'formHandler:escalate';
    const title = isEscalate ? UI.t('escalate') : UI.flowName(task.activity_name);
    const inputs = Object.entries(task.inputs || {});
    const why = isEscalate ? (task.inputs?.recovered === false ? '효과 확인에서 회복되지 않아 넘어온 사건입니다' : '선택 시간이 지나 넘어온 사건입니다') : (task.description || '');
    const inline = fields.length + 1 <= 2;      // C3: 입력 2개 이하는 카드 안 인라인
    box.innerHTML = `<section class="todo-panel"><div class="detail-head"><div class="row"><h3 style="margin:0">${esc(title)}</h3>${chip(task.status)}<span class="chip tone-neutral sm">${esc(who(task.user_id))}</span></div><div class="sub">${esc(why)}</div></div>
      ${inputs.length ? UI.fold(esc(UI.t('inst.prevTask')), `<div class="ro-grid">${inputs.map(([k, v]) => UI.readonly(k, v !== null && typeof v === 'object' ? `<pre>${esc(JSON.stringify(v, null, 2).slice(0, 1500))}</pre>` : esc(String(v)))).join('')}</div>`, { cls: 'plain' }) : ''}
      <div class="form ${inline ? 'inline-form' : ''}">${inline ? `<div class="form-grid">` : `<section class="form-section"><h4>${esc(UI.t('form.section.who'))}</h4><div class="form-grid">`}
        ${UI.field({ label: UI.t('form.by'), required: true, input: `<input id="tdBy" value="${esc(I.form.by)}">` })}${fields.map(control).join('')}
      ${inline ? '</div>' : '</div></section>'}
      ${UI.actions(`<button class="btn primary" id="tdDone">${esc(isEscalate ? UI.t('btn.confirm') : UI.t('btn.submit'))}</button>`, I.msg)}</div></section>`;
    $('#tdBy').addEventListener('input', e => I.form.by = e.target.value);
    fields.forEach((f, i) => $('#tdField' + i).addEventListener('input', e => I.fieldValues[f.key] = e.target.value));
    $('#tdDone').addEventListener('click', () => {
      try {
        const output = {};
        fields.forEach((f, i) => {
          const value = $('#tdField' + i).value;
          if (!value.trim()) { if (f.required !== false) throw Error(UI.t('form.err.required')); return; }
          output[f.key] = ['object', 'array', 'boolean'].includes(f.type) ? JSON.parse(value) : ['number', 'integer'].includes(f.type) ? Number(value) : value;
        });
        submitTask(task, output);
      } catch (e) { I.msg = e.message; renderTodoPanel(); }
    });
  }

  function timerFor(task) {
    if (!I.view || I.view.instance.proc_inst_id !== task.proc_inst_id) return null;
    const def = I.view.definition || {}, activity = (def.activities || []).find(a => a.id === task.activity_id) || {};
    const ids = (def.events || []).filter(e => e.attachedTo === task.activity_id || (activity.attachedEvents || []).includes(e.id)).map(e => e.id);
    return I.view.workitems.find(w => ids.includes(w.activity_id) && w.status === 'IN_PROGRESS');
  }

  function renderAskPanel(task) {
    const box = $('#todoPanel');
    const events = (I.view && I.view.events || []).filter(e => e.todo_id === task.id);
    const answered = new Set(events.filter(e => e.event_type === 'human_response').map(e => e.job_id));
    const open = events.filter(e => e.event_type === 'human_asked' && !answered.has(e.job_id)).slice(-1)[0];
    if (!open) { box.innerHTML = `<section class="todo-panel"><h3>${esc(UI.t('inst.askTitle'))} — ${esc(task.activity_name)}</h3><p class="muted">${esc(UI.t('inst.askWait'))}</p></section>`; return; }
    const d = open.data || {};
    const options = Array.isArray(d.options) ? d.options.filter(x => typeof x === 'string') : [];
    box.innerHTML = `<section class="todo-panel ask"><div class="detail-head"><div class="row"><h3 style="margin:0">${esc(UI.t('inst.askTitle'))}</h3>${chip('HUMAN_ASKED')}</div><div class="sub">${esc(task.activity_name)}</div></div>
      <p class="prose" style="font-weight:600;margin:0 0 var(--s2)">${esc(humanQuestionText(d))}</p>
      ${options.length ? `<div class="row-wrap" style="margin-bottom:var(--s3)">${options.map((o, i) => `<button class="btn small" type="button" data-human-option="${i}">${esc(o)}</button>`).join(' ')}</div>` : ''}
      <div class="form inline-form"><div class="form-grid">
        ${UI.field({ label: UI.t('form.answer'), required: true, cls: 'wide', hint: UI.t('form.hint.answer'), input: `<textarea id="tdAnswer" rows="2">${esc(I.form.reason)}</textarea>` })}
        ${UI.field({ label: UI.t('form.by'), required: true, input: `<input id="tdBy" value="${esc(I.form.by)}">` })}</div>
      ${UI.actions(`<button class="btn primary" id="tdAnswerGo">${esc(UI.t('btn.answer'))}</button>`, I.msg)}</div></section>`;
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

  /* 조치 선택 폼 — ① 사건 ② 선택 ③ 사유·담당 ④ 결정 (UIUX_PLAN §1.3) */
  function renderSelectPanel(task) {
    const box = $('#todoPanel');
    const d = I.dec;
    if (!d) { box.innerHTML = `<section class="todo-panel"><h3>${esc(UI.t('select'))}</h3><p class="muted">${esc(UI.t('inst.loadingCards'))}</p></section>`; return; }
    const opts = d.options || [];
    if (!I.form.option) I.form.option = d.recommended || (opts.find(o => o.feasible) || opts[0] || {}).id;
    const chosen = opts.find(o => o.id === I.form.option) || {};
    const cmd = p => (chosen.actions || []).find(a => a.kind === 'command' && a.param === p);
    const fanA = cmd('fan_pct'), loadA = cmd('load_pct'), pumpA = cmd('pump');
    if (I.form.cardFor !== I.form.option) { I.form.fan = fanA ? fanA.value : null; I.form.load = loadA ? loadA.value : null; I.form.cardFor = I.form.option; }
    const parameters = { ...(fanA ? { fan_pct: I.form.fan } : {}), ...(loadA ? { load_pct: I.form.load } : {}) };
    const review = window.hydCards?.reviewMatches(I.form.review, d.id, I.form.option, parameters, { workitem: task.id }) ? I.form.review : null;
    const reviewed = review?.snapshot?.options?.[0];
    const changed = (fanA && I.form.fan !== fanA.value) || (loadA && I.form.load !== loadA.value);
    const canApprove = reviewed ? reviewed.feasible : chosen.feasible && !changed;
    const roles = Object.entries(review?.snapshot?.roles || d.roles || {}).sort((a, b) => a[1].level - b[1].level);
    if (!I.form.role) I.form.role = (chosen.approver || {}).id || (roles[0] || [''])[0];
    const maxAbs = Math.max(1, ...opts.map(x => Math.abs(x.score || 0)));
    const cards = opts.map(o => hydCards.cardHtml(o, { rec: d.recommended, chosen: d.chosen, selectable: true, reviewable: true, selected: I.form.option === o.id, pending: true, maxAbs })).join('');
    const timer = timerFor(task);
    const maintenance = (chosen.actions || []).filter(a => a.code === 'WO_CREATE');
    const hasWorkOrder = (I.view?.definition?.activities || []).some(a => a.tool === 'enterprise:WO_CREATE');
    const maintenanceText = maintenance.length ? maintenance.map(a => a.value ?? a.name ?? UI.t('workOrder')).join(', ') : `선택한 조치 이후 정비 점검: ${chosen.name || ''}`;
    const sc = d.scenario || {};
    const inst = I.view?.instance || {};
    box.innerHTML = `<section class="todo-panel"><div class="detail-head"><div class="row"><h3 style="margin:0">${esc(UI.t('select'))}</h3>${chip(d.state)}<span class="chip tone-neutral sm">${esc(who(task.user_id))}</span></div><div class="sub">${esc(inst.proc_inst_name || '')}${timer && timer.due_date ? ` · ${esc(UI.t('form.deadline'))} ${esc(UI.time(timer.due_date))} · ${esc(UI.t('form.timeout'))}` : ''}</div></div>
      ${summaryBlock(d.explanation)}
      <div class="form">
      ${UI.section(UI.t('form.section.case'), `<div class="ro-grid wide">${UI.readonly(UI.t('dec.asset'), esc(d.asset || vars(inst).asset || ''))}${UI.readonly('고장 유형', esc(sc.failureMode || '–'))}${UI.readonly(UI.t('dec.cause'), esc(sc.cause || '–'))}${timer && timer.due_date ? UI.readonly(UI.t('form.deadline'), esc(UI.dateTime(timer.due_date)), UI.t('form.timeout')) : ''}</div>`)}
      ${UI.section(UI.t('form.section.choice'), `<div class="hitl-opts wide">${cards}</div>` +
        (fanA || loadA || pumpA ? `<div class="form-grid wide">${pumpA ? UI.readonly(UI.t('form.pump'), esc(pumpA.value)) : ''}${fanA ? hydCards.rangeField('tdFan', UI.t('form.fan'), fanA, I.form.fan) : ''}${loadA ? hydCards.rangeField('tdLoad', UI.t('form.load'), loadA, I.form.load) : ''}</div>` : '') +
        `<div class="wide" id="tdReviewed">${reviewed ? `<p class="kv-line"><b>${esc(UI.t('card.reviewed'))}</b> · ${esc(UI.dateTime(review.created))}</p>${hydCards.cardHtml(reviewed, { maxAbs })}` : `<p class="field-hint">${esc(UI.t('form.hint.preview'))}</p>`}</div>` +
        (hasWorkOrder ? `<p class="field-hint wide">${esc(UI.t('inst.followWo'))}: ${esc(maintenanceText)}</p>` : ''))}
      ${hydCards.whoFields('td', I.form, roles)}
      ${UI.actions(`<button class="btn outline" id="tdPreview" ${I.busy || !I.form.option ? 'disabled' : ''}>${esc(UI.t('btn.preview'))}</button><button class="btn primary" id="tdGo" ${canApprove && !I.busy ? '' : 'disabled'}>${esc(UI.t('btn.decide'))}</button>`, I.msg)}
      </div></section>`;
    box.querySelectorAll('input[name=hopt]').forEach(r => r.addEventListener('change', () => { I.form.option = r.value; I.form.review = null; I.msg = ''; const o = opts.find(x => x.id === r.value); if (o && o.approver) I.form.role = o.approver.id; renderTodoPanel(); }));
    const on = (id, ev, fn) => { const e = document.getElementById(id); if (e) e.addEventListener(ev, fn); };
    const invalidate = () => { I.form.review = null; $('#tdGo').disabled = true; $('#tdReviewed').innerHTML = `<p class="field-hint">${esc(UI.t('form.hint.preview'))}</p>`; };
    on('tdFan', 'input', e => { I.form.fan = +e.target.value; e.target.nextElementSibling.textContent = e.target.value + ' %'; invalidate(); });
    on('tdLoad', 'input', e => { I.form.load = +e.target.value; e.target.nextElementSibling.textContent = e.target.value + ' %'; invalidate(); });
    on('tdFan', 'change', renderTodoPanel); on('tdLoad', 'change', renderTodoPanel);
    on('tdBy', 'input', e => I.form.by = e.target.value);
    on('tdRole', 'change', e => { I.form.role = e.target.value; I.msg = ''; });
    on('tdReason', 'input', e => I.form.reason = e.target.value);
    on('tdGo', 'click', () => selectCard(task));
    on('tdPreview', 'click', () => previewCard(task, parameters));
  }

  async function previewCard(task, parameters) {
    if (I.busy) return; I.busy = true; I.msg = ''; renderTodoPanel();
    const form = I.form, decision = I.decId, option = form.option;
    try { const review = await postJ(API.process + `/api/todolist/${encodeURIComponent(task.id)}/decision-preview`, { decision, option, parameters });
      if (I.form === form && I.decId === decision && I.form.option === option) I.form.review = review;
    }
    catch (e) { if (I.form === form) { I.form.review = null; I.msg = e.message; } }
    finally { I.busy = false; renderTodoPanel(); }
  }

  async function selectCard(task) {
    if (I.busy) return; I.busy = true;
    try {
      await postJ(API.process + `/api/todolist/${encodeURIComponent(task.id)}/select`, { decision: I.decId, option: I.form.option, by: I.form.by || '승인자', role: I.form.role,
        reason: I.form.reason, fan_pct: I.form.fan, load_pct: I.form.load, review_id: matchingReviewId(task) });
      I.msg = '';
    } catch (e) { I.msg = e.message; }
    finally { I.busy = false; await load(true); }
  }
  function matchingReviewId(task) {
    const option = I.dec?.options?.find(o => o.id === I.form.option);
    const cmd = p => option?.actions?.find(a => a.kind === 'command' && a.param === p);
    const parameters = { ...(cmd('fan_pct') ? { fan_pct: I.form.fan } : {}), ...(cmd('load_pct') ? { load_pct: I.form.load } : {}) };
    return window.hydCards?.reviewMatches(I.form.review, I.decId, I.form.option, parameters, { workitem: task.id }) ? I.form.review.id : null;
  }
  async function submitTask(task, output) {
    if (I.busy) return; I.busy = true;
    try { await postJ(API.process + `/api/todolist/${encodeURIComponent(task.id)}/submit`, { output, by: I.form.by || '확인자' }); I.msg = ''; }
    catch (e) { I.msg = e.message; }
    finally { I.busy = false; await load(true); }
  }

  /* ------------------------------------------------ list (Camunda card order: name / status / step / started · elapsed) */
  function renderList() {
    const box = $('#instList');
    if (!I.instances.length) { box.innerHTML = UI.empty(UI.t('inst.empty'), UI.t('inst.emptySub'), 'compact'); return; }
    box.innerHTML = '';
    const names = {};
    ((I.view && I.view.definition && I.view.definition.activities) || []).forEach(a => { names[a.id] = a.name; });
    I.instances.forEach(x => {
      const started = new Date(x.start_date), ended = x.end_date ? new Date(x.end_date) : null;
      const span = ((ended || new Date()) - started) / 60000;
      const when = x.status === 'RUNNING' ? `${span < 1 ? UI.t('inst.justStarted') : Math.round(span) + UI.t('inst.elapsed')}` : `${ended ? Math.max(1, Math.round(span)) + UI.t('inst.took') + ' ' : ''}${UI.status(x.status)}`;
      const steps = (x.current_activity_ids || []).map(id => `<span class="chip step-chip">${esc(UI.flowName(names[id] || id.replace(/^task:|^ev:/, '')))}</span>`).join('');
      const it = el('div', 'item inst-card ' + esc(x.status) + (x.proc_inst_id === I.sel ? ' sel' : ''), `<div class="row"><strong>${esc(x.proc_inst_name)}</strong>${chip(x.status)}</div>
        <div class="steps">${steps || (x.end_event ? `<span class="chip end">${esc(UI.flowName(String(x.end_event).replace(/^ev:/, '')))}</span>` : '')}</div>
        <span class="sub">${esc(UI.dateTime(x.start_date))} · ${esc(when)}</span>`);
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
  // Dify-tracing row: name · who · duration · status chip · chevron (R8); the step's work item details (and 닫기/취소) live inside
  function stepRow(s, view) {
    const w = view.workitems.filter(x => x.activity_id === s.id).sort((a, b) => (b.generation || 0) - (a.generation || 0) || (b.start_date || '').localeCompare(a.start_date || ''))[0];
    const dur = w && w.start_date && w.end_date ? Math.max(0, (new Date(w.end_date) - new Date(w.start_date)) / 1000) : null;
    const durText = dur == null ? '' : dur < 60 ? `${dur.toFixed(1)} s` : `${Math.floor(dur / 60)}분 ${Math.round(dur % 60)}초`;
    const inst = view.instance;
    const closeBtn = w && w.agent_orch && w.agent_mode && inst.status === 'RUNNING' && (w.status === 'PENDING' || (w.status === 'IN_PROGRESS' && (w.draft_status === 'FAILED' || w.draft_status === 'CANCELLED'))) ? `<button class="btn small outline" data-close-task="${esc(w.id)}">${esc(UI.t('btn.closeTask'))}</button>` : '';
    const cancelBtn = w && w.agent_orch && w.agent_mode && inst.status === 'RUNNING' && w.status === 'IN_PROGRESS' && w.draft_status === 'STARTED' && w.consumer ? `<button class="btn small outline" data-cancel-task="${esc(w.id)}">${esc(UI.t('btn.cancelTask'))}</button>` : '';
    const reasonForm = I.closing && w && I.closing.id === w.id ? `<div class="form inline-form" data-reason-form><div class="form-grid">${UI.field({ label: I.closing.kind === 'close' ? UI.t('inst.closeReason') : UI.t('inst.cancelReason'), required: true, cls: 'wide', input: `<input data-close-reason value="${esc(I.closing.reason || '')}">` })}</div>${UI.actions(`<button class="btn small outline" data-close-abort>${esc(UI.t('btn.cancel'))}</button><button class="btn small primary" data-close-go>${esc(UI.t('btn.confirm'))}</button>`, I.msg)}</div>` : '';
    const body = w ? `<div class="meta"><span>${esc(UI.dateTime(w.start_date))}${w.end_date ? ' → ' + esc(UI.time(w.end_date)) : ''}</span>${w.due_date && !w.end_date ? `<span>${esc(UI.t('inst.due'))} ${esc(UI.time(w.due_date))}</span>` : ''}${w.generation ? `<span>${esc(w.generation)}${esc(UI.t('inst.gen'))}</span>` : ''}${w.draft_status && w.status !== 'DONE' ? `<span>${chip(w.draft_status)}</span>` : ''}</div>
      ${w.log ? `<p class="kv-line">${esc(w.log)}</p>` : ''}
      ${w.output && Object.keys(w.output).length ? UI.fold(`${esc(UI.t('inst.output'))} ${esc(Object.keys(w.output).filter(k => k !== 'text').join(', ') || 'text')}`, `<pre>${esc(JSON.stringify(w.output, null, 1).slice(0, 1500))}</pre>`, { cls: 'small' }) : ''}
      ${w.gateway_decisions ? UI.fold(esc(UI.t('inst.gateway')), `<pre>${esc(JSON.stringify(w.gateway_decisions, null, 1).slice(0, 800))}</pre>`, { cls: 'small' }) : ''}
      ${closeBtn || cancelBtn ? `<div class="row-wrap">${closeBtn}${cancelBtn}</div>` : ''}${reasonForm}` : `<p class="muted">${esc(STEP_LABEL[s.state])}</p>`;
    const chipHtml = s.state === 'skipped' ? UI.chip('SKIPPED') : s.state === 'todo' ? UI.chip('TODO') : chip(s.status || 'DONE');
    return `<details class="fold step-row ${esc(s.state)}" ${s.state === 'current' ? 'open' : ''}><summary><span>${esc(UI.flowName(s.name))}</span><span class="muted" style="font-weight:400">${esc(s.who)}</span>${durText ? `<span class="muted" style="font-weight:400;margin-left:auto">${esc(durText)}</span>` : ''}<span style="margin-left:${durText ? '8px' : 'auto'}">${chipHtml}</span></summary><div class="fold-body">${body}</div></details>`;
  }

  function renderDetail() {
    const box = $('#instDetail');
    if (!I.view) { box.innerHTML = UI.empty(UI.t('inst.select'), UI.t('inst.selectSub')); return; }
    const view = I.view, inst = view.instance, v = vars(inst);
    const st = stepsOf(view);
    const s = st ? st.summary : null;
    const progress = s ? `${s.done}/${s.total} ${UI.t('inst.stepsDone')}${s.current ? ` · ${UI.t('inst.now')}: ${UI.flowName(s.current.name)}` : s.next ? ` · ${UI.t('inst.next')}: ${UI.flowName(s.next.name)}` : s.finished ? ` · ${UI.t('inst.finished')}` : ''}` : '';
    const head = `<div class="detail-head"><div class="row"><h2>${esc(inst.proc_inst_name)}</h2>${chip(inst.status)}</div><div class="sub">${esc(UI.t('inst.started'))} ${esc(UI.dateTime(inst.start_date))}${inst.end_date ? ` · ${esc(UI.t('inst.ended'))} ${esc(UI.dateTime(inst.end_date))}` : ''}${progress ? ' · ' + esc(progress) : ''}</div></div>`;
    const counts = { flow: st ? st.steps.filter(x => x.state === 'current').length || null : null, log: view.events.length };
    const tabs = UI.tabs([['result', UI.t('inst.tab.result')], ['flow', UI.t('inst.tab.flow'), counts.flow], ['log', UI.t('inst.tab.log'), counts.log]], I.tab, 'data-inst-tab');
    box.innerHTML = head + tabs + `<div class="inst-detail-tabs"><div class="tab-pane ${I.tab === 'result' ? 'on' : ''}" data-pane="result">${resultPane(view, v)}</div><div class="tab-pane ${I.tab === 'flow' ? 'on' : ''}" data-pane="flow">${flowPane(view, st)}</div><div class="tab-pane ${I.tab === 'log' ? 'on' : ''}" data-pane="log">${logPane(view)}</div></div>`;
    box.querySelectorAll('[data-inst-tab]').forEach(b => b.addEventListener('click', () => { I.tab = b.dataset.instTab; box.querySelectorAll('[data-inst-tab]').forEach(x => { x.classList.toggle('on', x === b); x.setAttribute('aria-selected', String(x === b)); }); box.querySelectorAll('.tab-pane').forEach(p => p.classList.toggle('on', p.dataset.pane === I.tab)); if (I.tab === 'flow') mountFlow(view); }));
    if (I.tab === 'flow') mountFlow(view);
    window.hydRework?.mount(box.querySelector('#reworkPanel'), { view, by: I.form.by, changed: () => load(true) });
    window.hydEffects?.mount(box.querySelector('#effectsPanel'), { view, by: I.form.by, changed: () => load(true) });
    window.hydTaskDeferral?.mount(box.querySelector('#taskDeferralPanel'), { view, by: I.form.by, changed: () => load(true) });
    wireStepButtons(box);
    wireApprovalButtons(box);
  }
  function mountFlow(view) {
    const host = $('#instFlow'); if (!host || !window.hydFlow) return;
    hydFlow.mount(host, hydFlow.render(view.definition, { workitems: view.workitems, instance: view.instance, caption: '' }), view.instance.proc_inst_id);
  }

  /* 결과 탭: 결정 · 설비 응답 · 효과 확인 · 정비 요청 카드 + 값(라벨 붙은 읽기 전용) + 시작 값 접기 */
  function resultPane(view, v) {
    const inst = view.instance;
    const cards = [];
    const sel = view.workitems.filter(w => w.activity_id === 'task:select' && w.status === 'DONE').sort((a, b) => (b.generation || 0) - (a.generation || 0))[0];
    if (v.chosen_skill || sel) cards.push(UI.card({ title: esc(UI.t('decision')), chips: UI.chipText(v.chosen_skill_kind === 'control' ? UI.t('chip.control') : v.chosen_skill_kind === 'work_order' ? UI.t('chip.workOrder') : UI.t('done'), 'success'),
      value: `<span class="kv">${esc((v.chosen_option && v.chosen_option.name) || v.chosen_skill || '–')}</span>`, sub: `${esc(v.approved_by || (sel && sel.user_id ? who(sel.user_id) : '–'))}${v.approved_role ? ' · ' + esc(who(v.approved_role)) : ''}${sel && sel.end_date ? ' · ' + esc(UI.dateTime(sel.end_date)) : ''}` }));
    const cmdW = view.workitems.filter(w => w.activity_id === 'task:command').sort((a, b) => (b.generation || 0) - (a.generation || 0))[0];
    if (cmdW && cmdW.status !== 'CANCELLED' && cmdW.status !== 'TODO') cards.push(UI.card({ title: esc(UI.t('ack')), chips: chip(cmdW.status), value: v.commands ? `<span class="kv">${esc(Array.isArray(v.commands) ? v.commands.map(c => hydCards.actionLabel(c)).join(' · ') : '')}</span>` : '', sub: cmdW.end_date ? esc(UI.dateTime(cmdW.end_date)) : '' }));
    const reW = view.workitems.filter(w => w.activity_id === 'task:reobserve').sort((a, b) => (b.generation || 0) - (a.generation || 0))[0];
    if (reW && reW.status !== 'CANCELLED' && reW.status !== 'TODO') cards.push(UI.card({ title: esc(UI.t('reobserve')), chips: v.recovered === true ? UI.chipText('회복', 'success') : v.recovered === false ? UI.chipText('미회복', 'danger') : chip(reW.status), sub: reW.end_date ? esc(UI.dateTime(reW.end_date)) : '' }));
    const woW = view.workitems.filter(w => w.activity_id === 'task:work-order').sort((a, b) => (b.generation || 0) - (a.generation || 0))[0];
    if (woW && woW.status !== 'CANCELLED' && woW.status !== 'TODO') cards.push(UI.card({ title: esc(UI.t('workOrder')), chips: chip(woW.status), value: v.work_order && (v.work_order.ref || v.work_order.id) ? `<span class="kv mono">${esc(v.work_order.ref || v.work_order.id)}</span>` : '', sub: esc((v.work_order && v.work_order.detail) || '') }));
    const esW = view.workitems.filter(w => w.activity_id === 'task:escalate').sort((a, b) => (b.generation || 0) - (a.generation || 0))[0];
    if (esW && esW.status !== 'CANCELLED' && esW.status !== 'TODO') cards.push(UI.card({ title: esc(UI.t('escalate')), chips: chip(esW.status), sub: esc(v.note || esW.log || '') }));
    let html = cards.length ? `<div class="cards two">${cards.join('')}</div>` : UI.empty(UI.t('inst.noResult'), inst.status === 'RUNNING' ? UI.t('inst.noResultSub') : '', 'compact');
    // 값: label = definition data name, key as small text, structured values folded (R5 read-only form)
    const internal = new Set(['decision', 'decision_id', 'guide_card', 'candidates', 'compliance', 'incident', 'commands', 'chosen_option', 'alert', 'alert_id']);
    const varRows = (inst.variables_data || []).filter(row => !internal.has(row.key)).map(row => {
      const value = row.value, name = UI.terms['var.' + row.key] || (row.name && row.name !== row.key ? row.name.replace(/\s*[\(—(].*$/, '') : row.key);
      const shown = row.key === 'pattern' && typeof PATTERN_LABEL !== 'undefined' ? (PATTERN_LABEL[value] || value) : row.key === 'chosen_skill_kind' ? (value === 'control' ? UI.t('chip.control') : value === 'work_order' ? UI.t('chip.workOrder') : value)
        : row.key === 'cause' ? (((v.guide_card || {}).causes || []).find(c => c.id === value) || (v.guide_card || {}).topCause || {}).name || value
        : row.key === 'failure_mode' ? (typeof (v.guide_card || {}).failureMode === 'object' ? (v.guide_card.failureMode || {}).name : (v.decision || {}).failureMode) || value
        : row.key === 'chosen_skill' ? ((v.chosen_option || {}).name || value) : row.key === 'approved_role' ? UI.who(value) : value;
      const body = value !== null && typeof value === 'object' ? UI.fold(esc(UI.t('inst.structured')), `<pre>${esc(JSON.stringify(value, null, 2))}</pre>`, { cls: 'small' }) : esc(shown === true ? UI.t('yes') : shown === false ? UI.t('no') : shown ?? UI.t('inst.noValue'));
      const source = (inst.variable_sources || {})[row.key];
      const producer = source?.kind === 'workitem' ? view.workitems.find(w => w.id === source.id) : null;
      const origin = source?.kind === 'input' ? UI.t('inst.source.input') : source?.kind === 'workitem' ? UI.flowName(producer?.activity_name || source.activity) : source?.kind === 'runtime' ? UI.t('inst.source.runtime') : UI.t('inst.source.none');
      return UI.readonly(name, body, origin);
    }).join('');
    html += `<h3 style="font-size:14px;margin:var(--s6) 0 var(--s3)">${esc(UI.t('inst.values'))}</h3><div class="ro-grid">${varRows || `<div class="muted">${esc(UI.t('empty.noData'))}</div>`}</div>`;
    html += `<div style="margin-top:var(--s4)">` + UI.fold(esc(UI.t('inst.initial')), inst.initial_variables == null ? `<p class="muted">${esc(UI.t('empty.noData'))}</p>` : `<pre>${esc(JSON.stringify(inst.initial_variables, null, 2))}</pre>`) + '</div>';
    return html;
  }

  /* 흐름 탭: 흐름도 + 단계 행(Dify tracing) + 패널 4(접기, 열어야 할 때만) */
  function flowPane(view, st) {
    const inst = view.instance;
    let html = `<div class="flow-wrap" id="instFlow"></div>`;
    if (inst.status === 'RUNNING' && inst.flow_state?.end_arrivals?.length) html += `<p class="kv-line">${esc(UI.t('inst.endWaiting'))}</p>`;
    const waitingDependencies = Object.entries(inst.flow_state?.dependency_schedule || {}).filter(([id, spec]) => spec.flow_arrived && view.workitems.some(w => w.id === id && w.status === 'TODO'));
    if (waitingDependencies.length) html += UI.card({ title: esc(UI.t('inst.waitingResult')), cls: 'soft', body: waitingDependencies.map(([id, spec]) => {
      const task = view.workitems.find(w => w.id === id);
      const producers = [...new Set(spec.requires.map(dep => view.workitems.find(w => w.id === dep.workitem)?.activity_name || dep.activity))];
      const missingInitial = (spec.waiting_for || []).filter(x => x.reason === 'initial_input_unavailable').map(x => x.variable);
      const reason = missingInitial.length ? `시작 값 ${missingInitial.join(', ')}이 없습니다. 입력을 확인해 새 처리 건을 시작하세요.`
        : (spec.waiting_for || []).some(x => x.reason === 'fresh_output_unavailable') ? '필요한 결과값이 없어 대기 중입니다.' : `${producers.map(UI.flowName.bind(UI)).join(', ')}의 결과가 확정되면 시작합니다.`;
      return `<p><b>${esc(UI.flowName(task?.activity_name || spec.activity))}</b>: ${esc(reason)}</p>`; }).join('') });
    if (st) {
      html += `<h3 style="font-size:14px;margin:var(--s4) 0 var(--s2)">${esc(UI.t('inst.steps'))}</h3><div class="stack-list" style="gap:var(--s2)">`;
      st.groups.forEach(g => {
        if (g.type === 'step') { html += stepRow(g.step, view); return; }
        html += `<div class="branch-head">${esc(UI.flowName(g.name || '분기'))}</div>`;
        g.lanes.forEach(l => { l.steps.forEach(s => { html += stepRow(s, view); }); });
      });
      html += '</div>';
    } else {
      html += `<div class="inst-tl">${view.timeline.map((t, i) => `${i ? '<span class="arrow">→</span>' : ''}<div class="step ${esc(t.status || '')}"><b>${esc(UI.flowName(t.name))}</b><small>${esc(who(t.performer))}</small><small>${esc(UI.status(t.status) || UI.status('TODO'))}</small></div>`).join('')}</div>`;
    }
    html += `<div class="stack-list" style="margin-top:var(--s4)">${approvalHtml(view)}${workOrderRetryHtml(view)}<div id="taskDeferralPanel"></div><div id="effectsPanel"></div><div id="reworkPanel"></div>` +
      ((view.reworks || []).length ? UI.fold(`${esc(UI.t('inst.reworkHistory'))} <span class="chip tone-neutral sm">${view.reworks.length}</span>`, view.reworks.map(r => `<p>${esc(r.generation)}${esc(UI.t('inst.gen'))} · ${esc(r.request.by)} (${esc(who(r.request.role))}) · ${esc(r.request.reason)}</p>`).join('')) : '') + '</div>';
    return html;
  }
  function workOrderRetryHtml(view) {
    const failed = view.workitems.filter(w => w.tool === 'enterprise:WO_CREATE' && w.status === 'PENDING');
    const approval = (view.approvals || []).find(a => a.status === 'DELIVERED');
    const roles = Object.keys(approval?.payload?.plan?._snapshot?.roles || {});
    return failed.map(w => UI.fold(`${esc(UI.t('inst.woFailed'))} ${UI.chipText('실패', 'danger')}`, `<div data-approval-panel><p class="neg">${esc(w.log || '')}</p><p class="field-hint">자동 재시도를 마쳤습니다. 오류를 해결한 뒤 승인했던 같은 내용으로 다시 전달할 수 있습니다.</p>
      <div class="form"><section class="form-section"><div class="form-grid">${UI.field({ label: UI.t('form.by'), required: true, input: `<input data-retry-by value="${esc(I.form.by || '')}">` })}${UI.field({ label: UI.t('form.role'), required: true, input: `<select data-retry-role><option value="">${esc(UI.t('form.pickRole'))}</option>${roles.map(r => `<option value="${esc(r)}">${esc(who(r))}</option>`).join('')}</select>` })}</div></section>
      ${UI.actions(`<button class="btn primary" data-work-order-retry="${esc(w.id)}" ${I.busy || !roles.length ? 'disabled' : ''}>${esc(UI.t('btn.retry'))}</button>`, !roles.length ? '승인 원문을 확인할 수 없어 별도 검토가 필요합니다.' : I.msg)}</div></div>`, { open: true })).join('');
  }
  function approvalHtml(view) {
    const approvals = view.approvals || [];
    if (!approvals.length) return '';
    const names = { PENDING: '승인 접수 · 전달 대기', FAILED: '승인 전달 실패', DELIVERED: '승인 전달 완료', DISCARDED: '승인 폐기' };
    return approvals.map(a => {
      const p = a.payload || {}, snapshot = (p.plan || {})._snapshot || {};
      const option = (p.plan || {}).option || {};
      const roles = Object.keys(snapshot.roles || {});
      const commandPending = view.workitems.some(w => w.tool === 'incident:command' && w.status === 'PENDING');
      const reviewable = view.instance.status === 'RUNNING' && (a.status === 'FAILED' || (a.status === 'DELIVERED' && commandPending));
      const retry = reviewable ? `<p class="field-hint">${a.status === 'FAILED' ? '승인한 내용은 보존됐습니다. 오류를 확인한 뒤 같은 내용을 다시 전달할 수 있습니다.' : '조건 변경으로 명령이 보류됐다면 판단 단계에서 새 검토를 시작하세요. 사건이 종료됐다면 아래에서 실행 효과를 확인하고 취소할 수 있습니다.'}</p>
        <div class="form"><section class="form-section"><div class="form-grid">${UI.field({ label: UI.t('form.by'), required: true, input: `<input data-retry-by value="${esc(I.form.by || '')}">` })}${UI.field({ label: UI.t('form.role'), required: true, input: `<select data-retry-role><option value="">${esc(UI.t('form.pickRole'))}</option>${roles.map(r => `<option value="${esc(r)}">${esc(who(r))}</option>`).join('')}</select>` })}
        ${UI.field({ label: '폐기 ' + UI.t('form.reason'), cls: 'wide', hint: '사건이 종료되고 실제 조치가 없음을 확인한 경우에만 승인을 폐기하고 처리 건을 취소할 수 있습니다.', input: `<input data-discard-reason placeholder="후속 조치를 진행하지 않고 종료하는 이유">` })}</div></section>
        ${UI.actions(`${a.status === 'FAILED' ? `<button class="btn primary" data-approval-retry="${esc(a.todo_id)}" ${I.busy ? 'disabled' : ''}>${esc(UI.t('btn.retry'))}</button>` : ''}<button class="btn outline" data-approval-discard-preview="${esc(a.todo_id)}" ${I.busy ? 'disabled' : ''}>${esc(UI.t('btn.effects'))}</button>`, I.msg)}
        <div data-discard-preview role="status"></div></div>` : '';
      const discarded = a.status === 'DISCARDED' ? `<p class="field-hint">${(a.history || []).at(-1)?.via === 'rework' ? '다시 수행 요청으로 이전 승인을 폐기했습니다. 새 판단과 새 승인이 필요합니다.' : '처리 건을 취소했습니다.'} 이전 승인·오류는 보존됩니다.</p>${UI.fold(esc(UI.t('raw')), `<pre>${esc(JSON.stringify((a.history || []).at(-1), null, 2))}</pre>`, { cls: 'small' })}` : '';
      return UI.fold(`${esc(UI.t('inst.approval'))} ${chip(a.status, names[a.status] || UI.status(a.status))}`, `<div data-approval-panel><p class="kv-line">${esc(option.name || p.option)} · ${esc(UI.t('card.approver'))} <b>${esc(p.by)}</b> · 전달 시도 ${esc(a.attempts)}회</p>
        ${a.error ? UI.fold('오류 기록', `<pre>${esc(a.error)}</pre>`, { cls: 'small', open: true }) : ''}${retry}${discarded}</div>`, { open: reviewable || a.status === 'FAILED' });
    }).join('');
  }

  /* 기록 탭: 단계 표 + 에이전트 활동(R9 묶음) + 지식 반영(접기) */
  function logPane(view) {
    const inst = view.instance;
    const rows = view.workitems.map(w => `<tr class="${esc(w.status)}"><td>${esc(UI.flowName(w.activity_name))}${w.generation ? `<br><small class="muted">${esc(w.generation)}${esc(UI.t('inst.gen'))}</small>` : ''}</td><td>${chip(w.status)}${w.draft_status && w.status !== 'DONE' ? `<br>${chip(w.draft_status)}` : ''}</td>
      <td>${esc(who(w.user_id))}</td>
      <td>${esc(UI.time(w.start_date))}${w.end_date ? ' → ' + esc(UI.time(w.end_date)) : ''}${w.due_date && !w.end_date ? `<br><small class="muted">${esc(UI.t('inst.due'))} ${esc(UI.time(w.due_date))}</small>` : ''}</td>
      <td class="log">${esc(w.log || '')}${w.output && Object.keys(w.output).length ? UI.fold(`${esc(UI.t('inst.output'))} ${esc(Object.keys(w.output).filter(k => k !== 'text').join(', ') || 'text')}`, `<pre>${esc(JSON.stringify(w.output, null, 1).slice(0, 1500))}</pre>`, { cls: 'small' }) : ''}${UI.fold(esc(UI.t('raw')), `<pre>${esc(JSON.stringify({ id: w.id, activity_id: w.activity_id, generation: w.generation, agent_orch: w.agent_orch, agent_mode: w.agent_mode, consumer: w.consumer, draft_status: w.draft_status, supersedes_id: w.supersedes_id, gateway_decisions: w.gateway_decisions }, null, 1))}</pre>`, { cls: 'small' })}</td></tr>`).join('');
    // R9: a tool call and its result become one record with the duration
    const evs = view.events.slice();
    const started = new Map(); evs.forEach(e => { if (e.event_type === 'tool_usage_started' && e.data?.tool_use_id) started.set(e.data.tool_use_id, e); });
    const merged = new Set();
    const events = evs.slice(-80).reverse().filter(e => !(e.event_type === 'tool_usage_started' && evs.some(x => x.event_type === 'tool_usage_finished' && x.data?.tool_use_id === e.data?.tool_use_id))).map(e => {
      let detail = eventDetail(e), name = e.job_id === 'TASK_REVIEW_REQUIRED' ? e.job_id : e.event_type;
      if (e.event_type === 'tool_usage_finished') { const s0 = started.get(e.data?.tool_use_id); if (s0) detail = `${(e.data.tool || '').replace(/^mcp__/, '').replace(/__/g, ' · ')} · ${Math.round(new Date(e.timestamp) - new Date(s0.timestamp))} ms`; name = 'tool_usage_started'; }
      return UI.eventRecord({ time: e.timestamp, name, actor: e.crew_type || '', detail, raw: e.data });
    }).join('');
    return `<h3 style="font-size:14px;margin:0 0 var(--s2)">${esc(UI.t('inst.steps'))}</h3><div class="table-scroll"><table class="inst-table"><thead><tr><th>${esc(UI.t('inst.stepTable.step'))}</th><th>${esc(UI.t('inst.stepTable.status'))}</th><th>${esc(UI.t('inst.stepTable.who'))}</th><th>${esc(UI.t('inst.stepTable.when'))}</th><th>${esc(UI.t('inst.stepTable.result'))}</th></tr></thead><tbody>${rows}</tbody></table></div>
      <h3 style="font-size:14px;margin:var(--s6) 0 var(--s2)">${esc(UI.t('inst.events'))} <span class="chip tone-neutral sm">${view.events.length}</span></h3><div class="inst-events">${events || `<div class="muted">${esc(UI.t('empty.noData'))}</div>`}</div>
      <div style="margin-top:var(--s4)">${UI.fold(esc(UI.t('inst.graph')), graphHtml(inst))}</div>`;
  }
  function graphHtml(inst) {
    const g = I.graph;
    const pending = g && g.projection, cases = I.caseProjection;
    const sync = `<p class="kv-line">${esc(UI.t('inst.projectionPending'))}: ${pending ? esc(pending.pending) + '건' : esc(UI.t('inst.projectionNone'))} · ${esc(UI.t('inst.projectionAll'))}: ${cases && !cases.error ? esc(cases.pending) + '건' : esc(UI.t('inst.projectionNone'))}</p>
      ${cases && cases.worker_running === false ? '<p class="neg">사건·판단 복구 처리기가 실행 중이 아닙니다.</p>' : ''}
      ${cases && cases.error ? `<p class="neg">반영 상태 조회 실패: ${esc(cases.error)}</p>` : ''}
      ${cases?.knowledge ? `<p class="muted">지식 연결 변경 확인: ${cases.knowledge.last_checked ? esc(UI.dateTime(new Date(cases.knowledge.last_checked * 1000).toISOString())) : '첫 확인 대기'}${cases.knowledge.last_error ? '<br><span class="neg">연결 재확인 실패: ' + esc(cases.knowledge.last_error) + '</span>' : ''}</p>` : ''}
      ${pending && pending.last_error ? UI.fold(pending.last_error.startsWith('ProjectionConflict:') ? '원천 · 그래프 비교 필요' : '반영 재시도 중', `<pre>${esc(pending.last_error)}</pre>`, { cls: 'small', open: true }) : ''}
      ${pending?.last_error?.startsWith('ProjectionConflict:') || cases?.items?.some(x => x.last_error?.startsWith('ProjectionConflict:')) ? '<p class="neg">원천과 그래프의 반영 내역이 맞지 않아 자동 재전송을 보류했습니다. 운영자가 비교한 뒤 복구를 요청해야 합니다.</p>' : ''}
      ${cases && (cases.items || []).some(x => x.last_error) ? UI.fold('사건 · 판단 반영 오류', `<pre>${esc(JSON.stringify(cases.items.filter(x => x.last_error), null, 2))}</pre>`, { cls: 'small' }) : ''}`;
    if (!g) return sync + `<div class="muted">${esc(UI.t('loading'))}</div>`;
    if (g.error) return sync + `<div class="muted">${esc(UI.t('error.load'))}: ${esc(g.error)}</div>`;
    const cy = UI.fold(esc(UI.t('inst.query')), `<pre>${esc(g.cypher)}</pre><pre>${esc(JSON.stringify(g.params))}</pre>`, { cls: 'small' });
    const x = g.graph;
    if (!x) return sync + '<div class="muted">조회 가능한 반영 내역이 없습니다.</div>' + cy;
    const rows = (x.workitems || []).map(w => `<tr class="${esc(w.status)}"><td>${esc(UI.flowName(w.activity_name || w.activity_id || ''))}</td><td>${chip(w.status)}</td><td>${w.executes ? `${esc(w.executes_name || '')}<br><small class="muted">${esc(w.executes_type || '')}</small>` : '–'}</td><td>${w.assigned_to ? esc(who(w.assigned_to)) : '–'}</td></tr>`).join('');
    const warnings = (x.warnings || []).map(w => `<div class="neg">확인 필요: ${esc(w)}</div>`).join('');
    const version = x.definition || {};
    return sync + warnings + `<p class="kv-line">정의 <b>${esc(version.id || '')}</b> · 버전 ${esc(version.version || x.process.version || '')}${x.asset ? ` · ${esc(UI.t('dec.asset'))} ${esc(x.asset)}` : ''}${x.incident ? ` · ${esc(UI.t('case'))} ${esc(x.incident)}` : ''}</p>
      <table class="inst-table"><thead><tr><th>${esc(UI.t('step'))}</th><th>${esc(UI.t('inst.stepTable.status'))}</th><th>${esc(UI.t('knowledge'))}</th><th>${esc(UI.t('inst.stepTable.who'))}</th></tr></thead><tbody>${rows}</tbody></table>${cy}`;
  }
  function eventDetail(e) {
    const d = e.data || {};
    if (d.recovery === 'new_judgment_and_consent') return '현재 조건 검사로 명령을 보류했습니다. 판단 단계에서 새 검토와 승인을 진행하세요. ' + ((d.assessment || {}).reasons || []).join('; ');
    if (d.tool) return `${(d.tool || '').replace(/^mcp__/, '').replace(/__/g, ' · ')}${d.input ? ' ' + JSON.stringify(d.input).slice(0, 120) : ''}${d.output ? ' → ' + String(d.output).slice(0, 120) : ''}`;
    if (d.goal) return `${d.goal}${d.name ? ' · ' + d.name : ''}`;
    if (d.text || d.question) return humanQuestionText(d).slice(0, 160);
    return d.message || d.note || d.content || d.friendly || d.raw_error || (d.output_keys ? UI.t('inst.output') + ' ' + d.output_keys.join(', ') : '') || (d.answer ? UI.t('form.answer') + ' ' + d.answer : '');
  }

  /* ------------------------------------------------ buttons inside the 흐름 tab (R5: inline reason instead of window.prompt) */
  function wireStepButtons(box) {
    box.querySelectorAll('[data-close-task],[data-cancel-task]').forEach(button => button.addEventListener('click', () => {
      I.closing = { id: button.dataset.closeTask || button.dataset.cancelTask, kind: button.dataset.closeTask ? 'close' : 'cancel', reason: '' }; I.msg = ''; renderDetail();
    }));
    box.querySelector('[data-close-abort]')?.addEventListener('click', () => { I.closing = null; renderDetail(); });
    box.querySelector('[data-close-reason]')?.addEventListener('input', e => { if (I.closing) I.closing.reason = e.target.value; });
    box.querySelector('[data-close-go]')?.addEventListener('click', async e => {
      if (I.busy || !I.closing) return;
      const reason = (I.closing.reason || '').trim();
      if (!reason) { I.msg = UI.t('form.err.reason'); renderDetail(); return; }
      I.busy = true; e.currentTarget.disabled = true;
      try { await postJ(API.process + `/api/todolist/${encodeURIComponent(I.closing.id)}/${I.closing.kind}`, { by: I.form.by || '확인자', reason }); I.msg = ''; I.closing = null; }
      catch (err) { I.msg = err.message; }
      finally { I.busy = false; await load(true); }
    });
  }
  function wireApprovalButtons(box) {
    box.querySelectorAll('[data-approval-retry], [data-work-order-retry]').forEach(button => button.addEventListener('click', async () => {
      if (I.busy) return;
      const panel = button.closest('[data-approval-panel]');
      const by = panel.querySelector('[data-retry-by]').value.trim();
      const role = panel.querySelector('[data-retry-role]').value;
      if (!by || !role) { I.msg = UI.t('form.err.byRole'); await load(true); return; }
      I.busy = true; button.disabled = true;
      try {
        const workOrder = button.dataset.workOrderRetry;
        const path = workOrder ? `${encodeURIComponent(workOrder)}/work-order-retry` : `${encodeURIComponent(button.dataset.approvalRetry)}/approval-retry`;
        await postJ(API.process + `/api/todolist/${path}`, { by, role });
        I.msg = '';
      } catch (e) { I.msg = e.message; }
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
        if (!by || !role || !reason) { result.textContent = UI.t('form.err.byRoleReason'); return; }
        const wid = button.dataset.approvalDiscardPreview;
        I.busy = true; button.disabled = true;
        try {
          const evidence = await postJ(API.process + `/api/todolist/${encodeURIComponent(wid)}/approval-discard-preview`, { by, role });
          result.innerHTML = UI.card({ title: '폐기 전 확인', cls: 'soft', body: `<p>${esc(UI.t('case'))} ${UI.chip(evidence.incident.state)} · ${esc(UI.t('command'))} 없음 · 업무 실행 기록 ${esc(evidence.enterprise_receipts.length)}건</p>
            <p>${esc(evidence.outcome)}</p><p>취소할 남은 단계 ${esc(evidence.cancel_workitems.length)}건 · ${esc(UI.t('form.reason'))}: ${esc(reason)}</p>
            ${UI.actions('<button class="btn danger" data-confirm-discard>승인 폐기 · 처리 건 취소</button>')}` });
          const request_id = crypto.randomUUID();
          result.querySelector('[data-confirm-discard]').addEventListener('click', async event => {
            if (I.busy) return;
            I.busy = true; event.currentTarget.disabled = true;
            try { await postJ(API.process + `/api/todolist/${encodeURIComponent(wid)}/approval-discard`, { by, role, reason, request_id }); I.msg = ''; }
            catch (e) { I.msg = e.message; }
            finally { I.busy = false; await load(true); }
          });
        } catch (e) { result.textContent = e.message; }
        finally { I.busy = false; button.disabled = false; }
      });
    });
  }

  /* ------------------------------------------------ hooks */
  window.hydInstancesSelect = id => { I.sel = id; I.taskSel = null; load(true); };
  const _sel = selectTab;
  selectTab = function (name) { _sel(name); if (name === 'instances') load(true); };
  window.hydApp.selectTab = selectTab;
  $('#instReload').addEventListener('click', () => load(true));
  $('#instStatus').addEventListener('change', e => { I.status = e.target.value || null; I.sel = null; load(true); });
  setInterval(() => load(false), 2000);
  window.hydInstances = { I, load };
})();
