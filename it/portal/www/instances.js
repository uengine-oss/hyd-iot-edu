/* 처리 건 · 내가 할 일 (loaded after hitl.js and instanceSteps.js). 옛 「내 작업함」 화면의 처리할 단계 목록(역할별 보기 · 기한)이 이 화면의 「내가 할 일」이다 —
   사람이 처리할 열린 단계는 GET /api/todolist 하나로 읽는다(알림은 inbox.js 가 이 화면의 「알림」 접기에 그린다).
   process 서비스를 읽는다(주소는 layers.js API — 같은 출처):
     GET  /api/process/mode · /api/process/definitions/{id} · /api/instances · /api/instances/{id}(+/graph) · /api/graph-projections · /api/todolist… · /api/decisions/{id}
     POST /api/todolist/{id}/select · reject-card · decision-preview (조치 카드) · approve (일반 승인) · submit (폼) · human-response (질문 답) · 승인 전달 재전달 · 폐기 · 단계 닫기 · 실행 취소
   상태 의미는 ProcessGPT 와 같다: TODO 예정 → IN_PROGRESS 진행 중(내가 할 일) → SUBMITTED 제출됨(엔진 차례) → DONE · CANCELLED · PENDING.
   화면: 요약 카드 → 내가 할 일 → 단계 패널(카드 하나에 행동 하나) → 목록 + 상세 4탭(진행 상황 · 처리 기록 · 결과 · 단계 표) → 알림. */
(function () {
  const I = { defNames: {}, defTimers: {}, timers: [], role: '', mode: null, taskSel: null, taskView: null, fieldValues: {}, fieldTask: null, instances: [], sel: null, view: null, todo: [], dec: null, decId: null, asked: [],
              form: { option: null, role: null, by: '', reason: '', fan: null, load: null }, msg: '', busy: false, sig: null, listSig: null, tab: 'flow', closing: null, listShown: 20, todoShown: 6, eventsShown: 20,
              retryForm: {}, discardPreview: {}, gone: null,
              pmsg: {} };   // 상세 패널(단계 닫기 'close' · 승인 재전달 · 폐기 · 정비 요청 재전달 = 그 작업 id)마다 따로 두는 오류 글 — 단계 패널의 I.msg 와 섞이지 않는다(W1-24)
  const who = id => UI.roleName(id, I.view?.definition);
  // 상세 패널(다시 수행 · 실행 효과 · 보류 · 재전달 · 단계 닫기)의 담당자 기본값: 고른 「나」 — 없으면 빈 칸(지어낸 기본 이름을 넣지 않는다)
  const actor = () => window.hydInbox?.me?.()?.id || '';
  const isHuman = t => UI.doerOf(t) === 'human';
  // C3: 끝난 처리 건의 결과(정상 · 미달 · 지연 · 입고 완료)를 상태 칩 옆에 — 미달(ESCALATED) 종결도 "완료"로만 보이지 않게
  const outcomeChip = inst => {
    if (!inst || inst.status !== 'COMPLETED' || !window.hydResultReport) return '';
    const rep = hydResultReport.fromValues(UI.valuesOf(inst));
    if (!rep || !rep.verdict) return '';
    const tone = rep.verdict === 'ok' ? 'success' : ['fail', 'rejected'].includes(rep.verdict) ? 'danger' : 'neutral';
    return UI.chipText(rep.label || (rep.verdict === 'ok' ? '정상' : rep.verdict === 'fail' ? '미달' : '확인 결과'), tone);
  };

  /* ------------------------------------------------ load */
  async function load(force) {
    if (state.tab !== 'instances') return;
    // 읽는 중에 다시 읽기를 부르면 그 다음 읽기가 끝날 때 끝나는 약속을 돌려준다(누른 쪽이 새 화면을 기다릴 수 있게)
    if (I.loading) { I.reload = I.reload || force; return I.reloadDone || (I.reloadDone = new Promise(r => { I.reloadResolve = r; })); }
    I.loading = true;
    const prevTask = I.taskView ? I.taskView.id : null;
    let loadErr = '';
    try {
    if (window.hydToolNames) await hydToolNames.load();
    try { I.mode = await getJ(API.process + '/api/process/mode'); } catch (e) { I.mode = { error: e.message }; }
    if (!I.mode || I.mode.error) { renderBanner(); return; }
    // A083: the server filters by status; without it a RUNNING case older than the newest 50 is unreachable from the portal
    try { I.instances = requireList(await getJ(API.process + '/api/instances?limit=50' + (I.status ? '&status=' + encodeURIComponent(I.status) : '')), '처리 건 목록'); I.listError = ''; } catch (e) { I.instances = []; I.listError = e.message; }
    // A157: list chips name each row's step from that row's own definition (it showed raw ids like extract-manual when another
    // definition's instance was selected). Each definition version is fetched once; a failed fetch is reported, not hidden.
    // 활동과 이벤트 이름 — 끝 이벤트 이름도 실어 목록 칩이 E_end 같은 id 를 보이지 않게
    const defKey = x => `${x.proc_def_id}@${x.proc_def_version}`;
    await Promise.all([...new Set(I.instances.filter(x => !(defKey(x) in I.defNames)).map(defKey))].map(async k => {
      const [id, version] = k.split('@');
      try {
        const d = await getJ(API.process + `/api/process/definitions/${encodeURIComponent(id)}?version=${encodeURIComponent(version)}`);
        I.defNames[k] = Object.fromEntries([...(d.activities || []), ...(d.events || [])].filter(a => a.name).map(a => [a.id, a.name]));
        // 기한 타이머(경계 이벤트) → 그 타이머가 붙은 단계. 「내가 할 일」 줄의 기한을 이 표로 찾는다(timerFor 와 같은 규칙)
        I.defTimers[k] = Object.fromEntries([...(d.events || []).filter(e => e.attachedTo).map(e => [e.id, e.attachedTo]), ...(d.activities || []).flatMap(a => (a.attachedEvents || []).map(e => [e, a.id]))]);
      }
      catch (e) { loadErr = `흐름 정의 ${id} ${version}을(를) 읽지 못했습니다: ${e.message}`; }
    }));
    // 담당 작업 목록을 못 읽으면 「지금 할 일이 없습니다」가 아니다 — 사유를 I.todoError 에 두고 지난 목록은 그대로 보인다
    let todoRows = [], todoError = '';
    try { todoRows = requireList(await getJ(API.process + '/api/todolist?status=IN_PROGRESS'), '담당 작업 목록'); } catch (e) { todoError = e.message; }
    if (!I.sel && I.instances[0]) I.sel = I.instances[0].proc_inst_id;
    // 고른 처리 건의 진행 중 작업은 전체 목록 한도와 상관없이 빠짐없이 읽는다(GET /api/todolist?proc_inst_id=…&status=IN_PROGRESS)
    if (I.sel && !todoError) {
      try {
        const mine = requireList(await getJ(API.process + '/api/todolist?proc_inst_id=' + encodeURIComponent(I.sel) + '&status=IN_PROGRESS'), '처리 건 작업 목록');
        const seen = new Set(todoRows.map(t => t.id));
        todoRows = todoRows.concat(mine.filter(t => t.proc_inst_id === I.sel && !seen.has(t.id)));
      } catch (e) { todoError = e.message; }
    }
    I.todoError = todoError;
    if (!todoError) { I.todo = todoRows.filter(isHuman); I.asked = todoRows.filter(t => t.draft_status === 'HUMAN_ASKED'); I.timers = todoRows.filter(t => t.due_date && !isHuman(t)); }
    // Polling must not erase the snapshot used by an already visible action.
    // A click can render synchronously while any of these requests is waiting.
    let nextView = null, nextViewErr = null;
    if (I.sel) { try { nextView = await getJ(API.process + '/api/instances/' + encodeURIComponent(I.sel)); } catch (e) { nextViewErr = e.message; } }   // A161-U1 (결함 1): 열 수 없는 이유를 보인다
    I.view = nextView; I.viewErr = nextViewErr;
    // 지식 반영(그래프 질의 · 반영 대기)은 「단계 표」 탭의 접기에만 보인다 — 그 탭일 때만 읽는다(2초마다 Neo4j 질의를 하지 않게, W1-20)
    if (I.tab === 'log' && I.sel) {
      const [graph, projection] = await Promise.all([
        getJ(API.process + '/api/instances/' + encodeURIComponent(I.sel) + '/graph').catch(e => ({ error: e.message })),
        getJ(API.process + '/api/graph-projections').catch(e => ({ error: e.message }))]);
      I.graph = graph; I.caseProjection = projection;
    } else { I.graph = null; I.caseProjection = null; }
    const task = I.todo.find(t => t.id === I.taskSel && t.proc_inst_id === I.sel) || I.todo.find(t => t.proc_inst_id === I.sel);
    let nextTaskView = null, taskViewError = '';
    if (task) { try { nextTaskView = await getJ(API.process + '/api/todolist/' + encodeURIComponent(task.id)); } catch (e) { taskViewError = e.message; } }
    I.taskView = nextTaskView; I.taskViewError = taskViewError;
    // 다른 단계 · 처리 건으로 넘어가면 지난 단계의 오류 문구를 지운다(다른 처리 건의 승인 카드에 붙어 나오지 않게).
    // 거절된 뒤 단계가 사라졌으면(다른 담당자가 먼저 처리) 그 사실만 패널 자리에 남긴다(I.gone).
    const nextTask = I.taskView ? I.taskView.id : null;
    if (nextTask !== prevTask) I.msg = '';
    if (nextTask) I.gone = null;
    if (loadErr) I.msg = loadErr;
    const selectTask = I.taskView && I.taskView.tool === 'formHandler:select_card' ? I.taskView : null;
    let decId = null, decIdError = '';
    if (selectTask) { try { decId = await decisionIdOf(selectTask); } catch (e) { decIdError = '이 단계의 조치 후보 묶음을 찾지 못했습니다: ' + e.message; } }
    if (decId !== I.decId) { I.decId = decId; I.dec = null; I.form = { option: null, role: null, by: I.form.by, reason: '', fan: null, load: null }; }
    // 조치 후보를 못 읽으면 「불러오는 중」으로 남지 않는다 — 사유를 I.decError 에 둔다(다음 다시 읽기에서 또 시도)
    if (I.decId && !I.dec) { try { I.dec = await getJ(API.process + '/api/decisions/' + encodeURIComponent(I.decId)); I.decError = ''; } catch (e) { I.dec = null; I.decError = e.message; } }
    else if (!I.decId) I.decError = decIdError;
    // 변경 서명은 화면에 쓰는 값만 담는다. 목록(요약 · 내가 할 일 · 처리 건 목록)과 고른 처리 건(작업 패널 · 상세)을 나눠,
    // 다른 처리 건만 바뀌면 목록만 다시 그린다 — 지금 쓰고 있는 폼은 그대로 둔다(결함: 15초마다 · 다른 처리 건 이벤트마다 폼이 지워짐).
    const listSig = JSON.stringify([I.status, I.listShown, I.instances.map(x => [x.proc_inst_id, x.status, x.current_activity_ids, x.proc_inst_name, x.attention]), I.todo.map(t => [t.id, t.proc_inst_id, t.status, dueOf(t)]),
      I.asked.map(t => [t.id, t.draft_status]), I.sel, I.todoShown, I.todoError, I.role, UI.namesVersion]);
    const sig = JSON.stringify([I.sel, I.taskSel, I.taskView, I.asked.filter(t => t.proc_inst_id === I.sel).map(t => [t.id, t.draft_status]),
      I.view && I.view.workitems.map(w => [w.id, w.status, w.draft_status, w.log]),
      I.view && (I.view.approvals || []).map(a => [a.todo_id, a.status, a.attempts, a.error]), I.dec && I.dec.state, I.decError, I.taskViewError, I.msg, I.pmsg, I.gone,
      I.view && [I.view.events.length, I.view.events.at(-1)?.id], I.view && I.view.instance.variables_data,   // 이벤트는 개수 · 마지막 id 만(1500줄 전체를 2초마다 문자열로 만들지 않는다)
      I.viewErr, I.graph && (I.graph.error || I.graph.graph || 'none'), I.graph && I.graph.projection, caseSig(I.caseProjection), I.tab, I.eventsShown, UI.namesVersion]);
    feedTrace();                                   // A161-U1: the live trace takes the fresh view every poll (events · statuses), without a redraw
    updateKnowledgeChecked();                      // 지식 대조 시각(15초마다 바뀜)은 그 줄만 고친다
    if (!force && sig === I.sig && listSig === I.listSig) return;
    const detail = force || sig !== I.sig;
    I.sig = sig; I.listSig = listSig;
    // 글을 쓰는 중인 영역(단계 패널 · 상세의 입력 칸)은 다시 그리지 않는다 — 칸을 통째로 바꾸면 한글 조합이 끊긴다(W1-21).
    // 건너뛴 영역이 있으면 서명을 비워 두어 칸을 떠난 뒤 다음 읽기(2초)에서 그린다
    const typingIn = id => { const a = document.activeElement; return !!a && /^(INPUT|TEXTAREA)$/.test(a.tagName) && !!document.getElementById(id)?.contains(a); };
    const holdPanel = typingIn('todoPanel'), holdDetail = detail && typingIn('instDetail');
    keepFocus(() => { renderBanner(); renderTodo(detail && !holdPanel); renderList(); if (detail && !holdDetail) renderDetail(); });
    if (holdPanel || holdDetail) I.sig = null;
    } finally {
      I.loading = false;
      const done = I.reloadResolve; I.reloadDone = null; I.reloadResolve = null;
      if (I.reload) { I.reload = false; load(true).finally(() => done && done()); }
      else if (done) done();
    }
  }
  // 반영 상태 중 화면에 보이는 값만(대기 수 · 처리기 실행 · 오류). knowledge.last_checked(15초마다 바뀌는 대조 시각)는 넣지 않는다
  const caseSig = c => c && [c.error || null, c.pending, c.worker_running, (c.items || []).filter(x => x.last_error).map(x => [x.kind, x.source_id, x.last_error]), c.knowledge ? [!!c.knowledge.last_checked, c.knowledge.last_error || null] : null];
  const knowledgeChecked = c => c && c.knowledge && c.knowledge.last_checked ? UI.dateTime(new Date(c.knowledge.last_checked * 1000).toISOString()) : '첫 확인 대기';
  function updateKnowledgeChecked() { document.querySelectorAll('[data-knowledge-checked]').forEach(x => { const t = knowledgeChecked(I.caseProjection); if (x.textContent !== t) x.textContent = t; }); }
  // 다시 그릴 때 입력 중이던 칸의 포커스 · 커서를 되돌린다(값은 각 폼이 상태에 담아 다시 그린다)
  function focusKey(x) {
    if (x.id) return '#' + CSS.escape(x.id);
    const attrs = [...x.attributes].filter(a => a.name.startsWith('data-')).map(a => `[${a.name}="${CSS.escape(a.value)}"]`).join('');
    return attrs ? x.tagName.toLowerCase() + attrs : null;
  }
  function keepFocus(fn) {
    const root = document.getElementById('view-instances') || document.body, a = document.activeElement;
    const key = a && a !== document.body && root.contains(a) && /^(INPUT|TEXTAREA|SELECT|BUTTON)$/.test(a.tagName) ? focusKey(a) : null;
    let caret = null;
    try { caret = a && typeof a.selectionStart === 'number' ? [a.selectionStart, a.selectionEnd] : null; } catch (_) { caret = null; }
    fn();
    if (!key || (document.activeElement === a && a.isConnected)) return;
    const next = root.querySelector(key);
    if (!next || next.disabled || next.type === 'hidden') return;
    next.focus({ preventScroll: true });
    if (caret && next.setSelectionRange) { try { next.setSelectionRange(...caret); } catch (_) { /* number 칸 등 커서 없는 칸 */ } }
  }
  const vars = inst => UI.valuesOf(inst);
  async function decisionIdOf(task) {
    if (I.view && I.view.instance.proc_inst_id === task.proc_inst_id) return vars(I.view.instance).decision_id || null;
    return vars((await getJ(API.process + '/api/instances/' + encodeURIComponent(task.proc_inst_id))).instance).decision_id || null;   // 실패는 부르는 쪽이 I.decError 로 보인다
  }

  /* ------------------------------------------------ summary cards (UIUX_PLAN §1: 진행 중 · 내가 할 일 · 질문 only) */
  // H-10: 진행 중(RUNNING)이어도 사람의 조치를 기다리며 멈춘 처리 건(서버 attention)은 「진행 중」에 세지 않고 따로 센다 — 카드 이름은 서버 문장
  function counts(instances) {
    return { running: instances.filter(x => x.status === 'RUNNING' && !x.attention).length,
             stuck: instances.filter(x => x.status === 'RUNNING' && x.attention) };
  }
  function renderBanner() {
    const b = $('#instBanner');
    if (!I.mode || I.mode.error) { b.innerHTML = `<div class="inst-banner off">${esc(UI.t('inst.noConn'))} ${esc((I.mode || {}).error || '')}</div>`; return; }
    const { running, stuck } = counts(I.instances);
    b.innerHTML = `<div class="stat-cards">
      <div class="card"><span>${esc(UI.t('inst.running'))}</span><b class="num">${running}</b></div>${stuck.length ? `
      <div class="card hot"><span>${esc(stuck[0].attention.label)}</span><b class="num">${stuck.length}</b></div>` : ''}
      <div class="card${I.todo.length ? ' todo' : ''}"${I.todoError ? ` title="${esc(I.todoError)}"` : ''}><span>${esc(UI.t('inst.myTurn'))}</span><b class="num">${I.todoError ? '읽기 실패' : I.todo.length}</b></div>
      <div class="card${I.asked.length ? ' todo' : ''}"><span>${esc(UI.t('inst.asked'))}</span><b class="num">${I.asked.length}</b></div>
    </div>`;
  }

  /* ------------------------------------------------ 내가 할 일 (human IN_PROGRESS rows) + agent questions */
  // 그 단계에 붙은 기한 타이머 가운데 가장 이른 기한(없으면 null) — 타이머도 진행 중 작업 행으로 같은 목록에 온다
  function dueOf(t) {
    const inst = I.instances.find(x => x.proc_inst_id === t.proc_inst_id);
    const attached = inst ? I.defTimers[`${inst.proc_def_id}@${inst.proc_def_version}`] || {} : {};
    const dues = I.timers.filter(r => r.proc_inst_id === t.proc_inst_id && attached[r.activity_id] === t.activity_id).map(r => r.due_date).sort();
    return dues[0] || null;
  }
  // 역할별 보기: 전체 + 지금 열린 일이 있는 역할. 「이 일은 어느 역할의 일인가」를 가려 본다(쓰는 사람은 한 명이고 모든 역할을 맡는다 — 보기만 가른다)
  function renderRoles() {
    const box = $('#todoRoles'), count = {};
    I.todo.forEach(t => { count[t.user_id] = (count[t.user_id] || 0) + 1; });
    const ids = Object.keys(count).sort((a, b) => who(a).localeCompare(who(b)));
    if (I.role && !ids.includes(I.role)) ids.push(I.role);
    if (ids.length < 2 && !I.role) { box.innerHTML = ''; return; }
    const chip = (id, label, n) => `<button type="button" class="chip-btn${I.role === id ? ' on' : ''}" data-todo-role="${esc(id)}" aria-pressed="${I.role === id}">${esc(label)} <span class="n">${n}</span></button>`;
    box.innerHTML = `<div class="role-filter" role="group" aria-label="역할별 보기">${chip('', '전체', I.todo.length)}${ids.map(id => chip(id, who(id), count[id] || 0)).join('')}</div>`;
    box.querySelectorAll('[data-todo-role]').forEach(b => b.addEventListener('click', () => { I.role = b.dataset.todoRole; I.todoShown = 6; renderTodo(false); }));
  }
  // 쓰는 사람은 늘 담당자 한 명이고 모든 역할을 맡는다(inbox.js 머리말) — 사람 단계는 전부 내가 할 일이다. 줄마다 그 일을 맡는 역할을 보인다.
  function renderTodo(withPanel = true) {
    const box = $('#todoList');
    box.innerHTML = '';
    renderRoles();
    if (I.todoError) {
      box.innerHTML = UI.errorBlock('내가 할 일을 읽지 못했습니다', I.todoError + (I.todo.length || I.asked.length ? ' — 아래는 마지막으로 읽은 목록입니다' : ''), { retry: true, cls: 'compact' });
      box.querySelector('[data-retry]')?.addEventListener('click', () => load(true));
    }
    if (!I.todo.length && !I.asked.length) { if (!I.todoError) box.innerHTML = UI.empty(UI.t('inst.noTodo'), UI.t('inst.noTodoSub'), 'compact'); if (withPanel) renderTodoPanel(); return; }   // 「내가 할 일」 제목 아래가 비어 보이지 않게 늘 한 줄을 둔다(처리 건이 하나도 없을 때도)
    (I.role ? [] : I.asked).forEach(t => {
      const inst = I.instances.find(x => x.proc_inst_id === t.proc_inst_id) || {};
      const it = el('div', 'item ask' + (t.proc_inst_id === I.sel ? ' sel' : ''), `<div class="row"><strong>${esc(UI.t('inst.askTitle'))} — ${esc(UI.flowName(t.activity_name))}</strong>${UI.chip('HUMAN_ASKED')}</div><span class="sub">${esc(inst.proc_inst_name || '이름 없는 처리 건')}</span>`);
      keyboardItem(it);
      it.addEventListener('click', () => pick(t.proc_inst_id, t.id));
      box.appendChild(it);
    });
    const row = t => {
      const inst = I.instances.find(x => x.proc_inst_id === t.proc_inst_id) || {};
      // 한 줄 = 사람이 처리할 단계 하나. 칩은 그 일을 맡는 역할(단계의 user_id 는 역할 그대로다 — procsvc/inbox.py resolve)과 승인 단계 표시, 아래 줄은 처리 건 이름과 기한
      const approval = ['formHandler:select_card', 'formHandler:approve'].includes(t.tool) ? UI.chipText('승인 요청', 'accent') : '';
      const due = dueOf(t);
      const it = el('div', 'item' + (t.proc_inst_id === I.sel ? ' sel' : ''), `<div class="row"><strong>${esc(UI.flowName(t.activity_name))}</strong>${UI.chipText(who(t.user_id), 'neutral')}${approval}</div><span class="sub">${esc(inst.proc_inst_name || '이름 없는 처리 건')}${due ? ` · 기한 ${esc(UI.dateTime(due))}` : ''}</span>`);
      it.dataset.todoTask = t.id;
      keyboardItem(it);
      it.addEventListener('click', () => pick(t.proc_inst_id, t.id));
      return it;
    };

    // A141: 처음 6건 + 더 보기 (선택된 건은 위로 고정) — 한 화면에 많이 보이지 않게
    const shown = I.role ? I.todo.filter(t => t.user_id === I.role) : I.todo;
    if (I.role && !shown.length) box.insertAdjacentHTML('beforeend', UI.empty(`${who(I.role)} 역할로 처리할 단계가 없습니다`, '다른 역할의 일은 「전체」에서 볼 수 있습니다', 'compact'));
    const paged = UI.page(shown, I.todoShown, t => t.proc_inst_id === I.sel);
    paged.rows.forEach(t => box.appendChild(row(t)));
    if (paged.rest) { const more = el('div', 'todo-more', UI.moreButton(paged.rest)); more.querySelector('button').addEventListener('click', () => { I.todoShown += UI.PAGE; renderTodo(false); }); box.appendChild(more); }

    if (withPanel) renderTodoPanel();
  }
  // 다른 처리 건 · 단계를 고르면 지난 단계의 오류 · "이미 처리됨" 안내를 지운다
  function pick(sel, taskSel) {
    if (sel !== I.sel || taskSel !== I.taskSel) { I.msg = ''; I.gone = null; }
    I.sel = sel; I.taskSel = taskSel; load(true);
  }
  // 거절된 요청: 서버가 4xx 로 거절하면 단계가 이미 닫혔을 수 있다 — 다시 읽은 뒤 단계가 없으면 패널 자리에 이 안내를 남긴다
  function refused(task, e, what) {
    I.msg = e.message;
    if (e.status >= 400 && e.status < 500) I.gone = { inst: task.proc_inst_id, task: task.id, title: `이미 처리된 ${what}입니다`, text: e.message };
  }

  function handoverInputs(values) {
    const names = {asset:'설비',as_of:'인계 기준시각',shift_label:'교대',work_notes:'작업 메모',handover_summary:'인계안 요약',sender_notes:'인계자 확인 사항',receiver_notes:'인수자 보완 요청'};
    const areas = {equipment:'설비 관측',work_orders:'정비 작업지시',parts:'부품·재고',work_notes:'작업 메모 대조'};
    const states = {observed:'조회 확인',needs_check:'확인 필요',conflict:'기록 불일치'};
    const rows = Object.entries(values || {}).filter(([k]) => !['checks','evidence'].includes(k)).map(([k,v]) => UI.readonly(names[k] || k,esc(typeof v==='string' ? v : JSON.stringify(v)))).join('');
    const checks = (Array.isArray(values?.checks) ? values.checks : []).map(c => `<section class="form-section"><h4>${esc(areas[c.area] || c.area)} · ${esc(states[c.state] || c.state)}</h4><p>${esc(c.finding || '')}</p><p><b>다음 근무자가 확인할 일</b> ${esc(c.next_action || '')}</p><p class="field-hint">조회 근거 ${(c.evidence_indices || []).map(i=>esc(String(i+1))).join(', ') || '없음 · 확인 필요'}</p></section>`).join('');
    const evidence = (Array.isArray(values?.evidence) ? values.evidence : []).map((e,i) => UI.fold(`조회 근거 ${i+1} · ${esc(UI.toolName(e.tool) || e.tool || '도구 기록 없음')}`,`<pre>${esc(JSON.stringify(e,null,2))}</pre>`,{cls:'plain'})).join('');
    return `<div class="ro-grid">${rows}</div>${checks}${evidence}`;
  }

  function renderTodoPanel() {
    const box = $('#todoPanel');
    const asked = I.asked.find(t => t.proc_inst_id === I.sel);
    if (asked) { renderAskPanel(asked); return; }
    const task = I.taskView;
    if (!task && I.taskViewError) {
      box.innerHTML = `<section class="todo-panel">${UI.errorBlock('이 단계를 열지 못했습니다', I.taskViewError, { retry: true })}</section>`;
      box.querySelector('[data-retry]')?.addEventListener('click', () => load(true));
      return;
    }
    if (!task) {
      const g = I.gone && I.gone.inst === I.sel ? I.gone : null;
      box.innerHTML = g ? `<section class="todo-panel" data-gone><h3 style="margin:0">${esc(g.title)}</h3><p class="field-hint">이 단계는 이미 처리됐거나 닫혀서 「내가 할 일」 목록에서 빠졌습니다. 결과는 아래 처리 건 상세의 진행 상황과 처리 기록에서 확인하세요.</p><p class="muted">서버 응답: ${esc(g.text)}</p></section>` : '';
      return;
    }
    if (task.tool === 'formHandler:select_card') { renderSelectPanel(task); return; }
    if (task.tool === 'formHandler:approve') { renderApprovePanel(task); return; }
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
    const byMe = window.hydInbox?.byField('td', I.form);   // 제출 · 답은 고른 「나」로만(서버 require_task_actor) — 없으면 안내만, 단추는 꺼 둔다
    box.innerHTML = `<section class="todo-panel"><div class="detail-head"><div class="row"><h3 style="margin:0">${esc(title)}</h3>${UI.chip(task.status)}<span class="chip tone-neutral sm">${esc(who(task.user_id))}</span></div><div class="sub">${esc(why)}</div></div>
      ${inputs.length ? UI.fold(esc(UI.t('inst.prevTask')), String(task.form?.contract || '').startsWith('shift-handover-') ? handoverInputs(task.inputs) : `<div class="ro-grid">${inputs.map(([k, v]) => UI.readonly(varLabel(k), prevValue(v))).join('')}</div>`, { cls: 'plain' }) : ''}
      <div class="form ${inline ? 'inline-form' : ''}">${inline ? `<div class="form-grid">` : `<section class="form-section"><h4>입력</h4><div class="form-grid">`}
        ${byMe || pickMe()}${fields.map(control).join('')}
      ${inline ? '</div>' : '</div></section>'}
      ${UI.actions(`<button class="btn primary" id="tdDone" ${byMe && !I.busy ? '' : 'disabled'}>${esc(isEscalate ? UI.t('btn.confirm') : UI.t('btn.submit'))}</button>`, I.msg)}</div></section>`;
    fields.forEach((f, i) => $('#tdField' + i).addEventListener('input', e => I.fieldValues[f.key] = e.target.value));
    $('#tdDone').addEventListener('click', () => {
      try {
        const output = {};
        fields.forEach((f, i) => {
          const value = $('#tdField' + i).value;
          if (!value.trim()) { if (f.required !== false) throw Error(UI.t('form.err.required')); return; }
          const label = f.text || UI.t('var.' + f.key);
          if (['object', 'array', 'boolean'].includes(f.type)) {
            try { output[f.key] = JSON.parse(value); } catch (_) { throw Error(`‘${label}’ 칸은 ${f.type === 'boolean' ? 'true 또는 false' : f.type === 'array' ? '[ ]로 감싼 목록(JSON)' : '{ }로 감싼 값(JSON)'}으로 적어야 합니다.`); }
          } else if (['number', 'integer'].includes(f.type)) {
            output[f.key] = Number(value);
            if (!Number.isFinite(output[f.key]) || (f.type === 'integer' && !Number.isInteger(output[f.key]))) throw Error(`‘${label}’ 칸에는 ${f.type === 'integer' ? '정수' : '숫자'}를 적으세요.`);
          } else output[f.key] = value;
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
  // 승인 단계의 기한 칩(1초마다 updateApprovalClock 이 문구를 고친다). 멈추는 타이머(cancelActivity 가 false 가 아님)면 기한이 지나면
  // 이 단계가 닫히고 다음 단계로 넘어가므로 그 단계 이름을 싣는다 — 멈추지 않는 타이머는 지연 알림만 보낸다
  function clockChip(task) {
    const timer = timerFor(task);
    if (!timer || !timer.due_date) return '';
    const def = I.view?.definition || {};
    const ev = (def.events || []).find(e => e.id === timer.activity_id) || {};
    if (ev.cancelActivity === false) return `<span class="chip tone-warning" data-approval-until="${esc(timer.due_date)}"></span>`;
    const nextId = ((def.sequences || []).find(s => s.source === ev.id) || {}).target;
    const next = nextId ? ([...(def.activities || []), ...(def.events || [])].find(a => a.id === nextId) || {}).name : '';
    return `<span class="chip tone-warning" data-approval-until="${esc(timer.due_date)}" data-approval-cut="${esc(next ? UI.flowName(next) : '')}"></span>`;
  }
  // 「이전 단계」가 넘긴 값: 이름은 화면 이름 사전(var.*)으로, 묶음 값은 항목별 한 줄로 읽는다. 더 깊은 값과 긴 글은 접어 둔다
  const varLabel = k => { const n = UI.t('var.' + k); return n === 'var.' + k ? String(k).replace(/_/g, ' ') : n; };
  function prevValue(v) {
    const scalar = x => x === null || x === undefined || x === '' ? '–' : typeof x === 'boolean' ? (x ? '예' : '아니요') : esc(UI.idText(String(x)));
    if (v === null || typeof v !== 'object') return scalar(v);
    const entries = Array.isArray(v) ? v.map((x, i) => [String(i + 1), x]) : Object.entries(v);
    if (!entries.length) return '–';
    const flat = entries.filter(([, x]) => x === null || typeof x !== 'object'), deep = entries.filter(([, x]) => x !== null && typeof x === 'object');
    const rows = flat.map(([k, x]) => `<div class="kv-line"><span class="muted">${esc(Array.isArray(v) ? k : varLabel(k))}</span> ${scalar(x)}</div>`).join('');
    return rows + (deep.length ? UI.fold(`세부 값 ${deep.length}개`, `<pre>${esc(JSON.stringify(Object.fromEntries(deep), null, 2).slice(0, 1500))}</pre>`, { cls: 'small' }) : '');
  }
  // 담당자 정보를 아직 못 읽었으면(업무 DB 연결 문제) 사람 행동의 자리에 그 까닭을 보인다 — 모든 단계 패널이 이 한 줄을 쓴다
  const pickMe = () => `<p class="form-msg neg" role="alert" data-pick-me>담당자 정보를 읽지 못해 지금은 처리할 수 없습니다. 화면을 새로 고친 뒤 다시 해 주세요.</p>`;

  function renderAskPanel(task) {
    const box = $('#todoPanel');
    const events = (I.view && I.view.events || []).filter(e => e.todo_id === task.id);
    const answered = new Set(events.filter(e => e.event_type === 'human_response').map(e => e.job_id));
    const open = events.filter(e => e.event_type === 'human_asked' && !answered.has(e.job_id)).slice(-1)[0];
    if (!open) { box.innerHTML = `<section class="todo-panel"><h3>${esc(UI.t('inst.askTitle'))} — ${esc(task.activity_name)}</h3><p class="muted">${esc(UI.t('inst.askWait'))}</p></section>`; return; }
    const d = open.data || {};
    const options = Array.isArray(d.options) ? d.options.filter(x => typeof x === 'string') : [];
    const byMe = window.hydInbox?.byField('td', I.form);
    box.innerHTML = `<section class="todo-panel ask"><div class="detail-head"><div class="row"><h3 style="margin:0">${esc(UI.t('inst.askTitle'))}</h3>${UI.chip('HUMAN_ASKED')}</div><div class="sub">${esc(task.activity_name)}</div></div>
      <p class="prose" style="font-weight:600;margin:0 0 var(--s2)">${esc(humanQuestionText(d))}</p>
      ${options.length ? `<div class="row-wrap" style="margin-bottom:var(--s3)">${options.map((o, i) => `<button class="btn small" type="button" data-human-option="${i}">${esc(o)}</button>`).join(' ')}</div>` : ''}
      <div class="form inline-form"><div class="form-grid">
        ${UI.field({ label: UI.t('form.answer'), required: true, cls: 'wide', hint: UI.t('form.hint.answer'), input: `<textarea id="tdAnswer" rows="2">${esc(I.form.reason)}</textarea>` })}
        ${byMe || pickMe()}</div>
      ${UI.actions(`<button class="btn primary" id="tdAnswerGo" ${byMe && !I.busy ? '' : 'disabled'}>${esc(UI.t('btn.answer'))}</button>`, I.msg)}</div></section>`;
    box.querySelectorAll('[data-human-option]').forEach(button => button.addEventListener('click', () => {
      I.form.reason = options[Number(button.dataset.humanOption)]; $('#tdAnswer').value = I.form.reason;
    }));
    $('#tdAnswer').addEventListener('input', e => I.form.reason = e.target.value);
    $('#tdAnswerGo').addEventListener('click', () => act(task, '질문', () => postJ(API.process + `/api/todolist/${encodeURIComponent(task.id)}/human-response`, { job_id: open.job_id, answer: I.form.reason, by: actor() }), () => { I.form.reason = ''; }));
  }

  /* 조치 선택 폼 — ① 사건 ② 선택 ③ 사유·담당 ④ 결정 (UIUX_PLAN §1) */
  function renderSelectPanel(task) {
    const box = $('#todoPanel');
    const focused = box.contains(document.activeElement) ? document.activeElement : null;
    const caret = focused && typeof focused.selectionStart === 'number' ? [focused.selectionStart, focused.selectionEnd] : null;
    const folds = new Map([...box.querySelectorAll('details')].map(el => [el.querySelector('summary')?.textContent, el.open]));
    const d = I.dec;
    if (!d && I.decError) {
      box.innerHTML = `<section class="todo-panel"><h3>${esc(UI.t('select'))}</h3>${UI.errorBlock('조치 후보를 읽지 못했습니다', I.decError, { retry: true })}</section>`;
      box.querySelector('[data-retry]')?.addEventListener('click', () => load(true));
      return;
    }
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
    const canApprove = (reviewed ? reviewed.feasible : chosen.feasible && !changed) && !UI.executionBlocked(reviewed || chosen,review?.snapshot || d);
    const roles = Object.entries(review?.snapshot?.roles || d.roles || {}).map(([id, role]) => [id, { ...role, name: role.name || UI.who(id) }]).sort((a, b) => a[1].level - b[1].level);
    if (!I.form.role) I.form.role = (chosen.approver || {}).id || (roles[0] || [''])[0];
    // P5 (audit2): 조치 카드도 일반 승인처럼 「나」(그 승인 역할의 구성원)가 있어야 승인 · 거절한다. 어느 역할이 그 안을 승인할 수 있는지는
    // 서버가 판정해 판단의 각 안에 싣는다(options[].approvable_roles — decisions.approver_roles). 화면은 그 목록만 본다(역할 등급 규칙 사본 없음, W1-11 · W1-25)
    const roleTable = review?.snapshot?.roles || d.roles || {};
    const need = (reviewed || chosen).approver || null;
    const signs = (role, o) => { const opt = (d.options || []).find(x => x.id === o?.id) || o; return !opt?.approver?.id || (opt.approvable_roles || []).includes(role); };
    const meNow = window.hydInbox?.me?.() || null;
    // 승인 역할은 고른 안이 요구하는 역할로 늘 맞춘다(담당자는 모든 역할의 구성원이다). 그 역할이 없으면 승인할 수 있는 역할 가운데 하나
    if (meNow) { const want = need?.id; I.form.role = want && meNow.roles.includes(want) ? want : (meNow.roles.find(r => signs(r, reviewed || chosen)) || meNow.roles[0] || ''); }
    const needName = need?.id ? (roleTable[need.id]?.name || need.name || UI.who(need.id)) : '';
    const meSigns = !!meNow && signs(I.form.role, reviewed || chosen);
    const meRejects = !!meNow && (!opts.length || opts.some(o => signs(I.form.role, o)));
    const roleHint = meNow && !meSigns ? `이 안은 ${needName} 역할이 승인하는데, 이 PC의 담당자가 그 역할에 들어 있지 않아 승인할 수 없습니다. 메뉴 「AI 에이전트」의 「${UI.t('nav.agents')}」 화면에서 담당 배정을 확인하세요.` : '';
    const maxAbs = Math.max(1, ...opts.map(x => Math.abs(x.score || 0)));
    const timer = timerFor(task);
    const activity = (I.view?.definition?.activities || []).find(a => a.id === task.activity_id);
    const canReject = (activity?.outputData || []).includes('approval');
    const delayed = (I.view?.events || []).some(e => e.data?.report?.outcome === '승인 지연') || vars(I.view?.instance || {}).result_report?.outcome === '승인 지연';
    const maintenance = (chosen.actions || []).filter(a => a.code === 'WO_CREATE');
    const hasWorkOrder = (I.view?.definition?.activities || []).some(a => a.tool === 'enterprise:WO_CREATE');
    const maintenanceText = maintenance.length ? maintenance.map(a => a.value ?? a.name ?? UI.t('workOrder')).join(', ') : `선택한 조치 이후 정비 점검: ${chosen.name || ''}`;
    const sc = d.scenario || {};
    const inst = I.view?.instance || {};
    // A161-U1: 승인 화면 = 요약 카드 한 장(추천안 · 짧은 이유 · 핵심 근거 · 승인 한 번). 진 안 · 값 조정 · 사건 정보는 접기 (approvalCard.js)
    const adjust = fanA || loadA || pumpA || chosen.maintenancePlan || chosen.economicComparison ? UI.fold(fanA || loadA || pumpA ? '조치 값 조정 · 미리 보기' : '현재 조건 다시 확인 · 미리 보기', `<div class="form-grid">${pumpA ? UI.readonly(UI.t('form.pump'), esc(pumpA.value)) : ''}${fanA ? hydCards.rangeField('tdFan', UI.t('form.fan'), fanA, I.form.fan) : ''}${loadA ? hydCards.rangeField('tdLoad', UI.t('form.load'), loadA, I.form.load) : ''}</div>` +
      `<div id="tdReviewed">${reviewed ? `<p class="kv-line"><b>${esc(UI.t('card.reviewed'))}</b> · ${esc(UI.dateTime(review.created))}</p>${hydCards.cardHtml(reviewed, { maxAbs, decision: review.snapshot })}` : `<p class="field-hint">${esc(UI.t('form.hint.preview'))}</p>`}</div>` +
      `<div class="form-actions"><button class="btn small outline" id="tdPreview" ${I.busy || !I.form.option ? 'disabled' : ''}>${esc(UI.t('btn.preview'))}</button></div>`, { cls: 'small', open: !!changed || !!reviewed || !!I.form.needPreview }) : '';
    // 실행할 수 있는 안이 하나도 없으면 [승인]이 꺼진 이유와 다음 행동을 행동 줄에 말한다
    const noneFeasible = !reviewed?.feasible && !opts.some(o => o.feasible);
    const hint = noneFeasible ? `실행할 수 있는 안이 없어 승인할 수 없습니다. 조건이 바뀌면 에이전트가 다시 판단합니다 — ${canReject ? '지금은 사유를 적고 [반려]를 누르세요.' : '처리 건의 「다시 수행」으로 새 판단을 요청하세요.'}`
      : !canApprove && changed ? '값을 바꿨으면 미리 보기로 다시 확인한 뒤 승인합니다' : '';
    const previewNow = I.form.needPreview && I.form.option ? `<button class="btn outline" id="tdPreviewNow" ${I.busy ? 'disabled' : ''}>${esc(UI.t('btn.preview'))}</button>` : '';
    const caseInfo = UI.metaFold([[UI.t('dec.asset'), esc(d.asset || vars(inst).asset || '')], ['고장 유형', esc(UI.idText(sc.failureMode || ''))], [UI.t('dec.cause'), esc(UI.idText(sc.cause || ''))], [UI.t('form.deadline'), timer && timer.due_date ? esc(UI.dateTime(timer.due_date)) : ''], [UI.t('inst.followWo'), hasWorkOrder ? esc(maintenanceText) : '']], 'fold.case');
    box.innerHTML = `<section class="todo-panel approve" aria-busy="${I.busy}"><div class="detail-head"><div class="row"><h3 style="margin:0">승인 요청</h3>${UI.chip(d.state)}<span class="chip tone-neutral sm">${esc(who(task.user_id))}</span>${clockChip(task)}</div><div class="sub">${esc(inst.proc_inst_name || '')} · ${esc(UI.flowName(task.activity_name || '').replace(/\s*\((?:HITL|hitl)\)\s*/g, ''))}</div></div>
      ${window.hydApprove.html(d, I.form.option, { pending: true, adjust, extra: caseInfo })}
      ${delayed ? '<p class="approval-delay" role="status">승인 지연 알림을 보냈습니다. 승인하거나 반려하면 다음 단계로 넘어갑니다.</p>' : ''}
      <div class="form">
      ${meNow ? hydInbox.whoFields('td', I.form, roles, canReject ? { reasonHint: '반려할 때는 사유를 1~2000자로 적으세요. 반려 결과와 처리 기록에 남습니다.' } : {}) : pickMe()}
      ${UI.actions(`${canReject ? `<button class="btn outline" id="tdRejectCard" ${meRejects && !I.busy ? '' : 'disabled'}>${esc(UI.t('btn.reject'))}</button>` : ''}${previewNow}<button class="btn primary" id="tdGo" ${canApprove && meSigns && !I.busy ? '' : 'disabled'}>${esc(UI.t('btn.approve'))}</button>`, roleHint || I.msg || hint)}
      </div></section>`;
    box.querySelector('[data-ap-back]')?.addEventListener('click', ev => { I.form.option = ev.currentTarget.dataset.apBack; I.form.review = null; I.form.needPreview = false; I.msg = ''; const o = opts.find(x => x.id === I.form.option); if (o && o.approver) I.form.role = o.approver.id; renderTodoPanel(); });
    box.querySelectorAll('input[name=hopt]').forEach(r => r.addEventListener('change', () => { I.form.option = r.value; I.form.review = null; I.form.needPreview = false; I.msg = ''; const o = opts.find(x => x.id === r.value); if (o && o.approver) I.form.role = o.approver.id; renderTodoPanel(); }));
    const on = (id, ev, fn) => { const e = document.getElementById(id); if (e) e.addEventListener(ev, fn); };
    const invalidate = () => { I.form.review = null; $('#tdGo').disabled = true; $('#tdReviewed').innerHTML = `<p class="field-hint">${esc(UI.t('form.hint.preview'))}</p>`; };
    on('tdFan', 'input', e => { I.form.fan = +e.target.value; e.target.nextElementSibling.textContent = e.target.value + ' %'; invalidate(); });
    on('tdLoad', 'input', e => { I.form.load = +e.target.value; e.target.nextElementSibling.textContent = e.target.value + ' %'; invalidate(); });
    on('tdFan', 'change', renderTodoPanel); on('tdLoad', 'change', renderTodoPanel);
    on('tdReason', 'input', e => I.form.reason = e.target.value);
    on('tdGo', 'click', () => selectCard(task));
    on('tdRejectCard', 'click', () => rejectCard(task));
    on('tdPreview', 'click', () => previewCard(task, parameters));
    on('tdPreviewNow', 'click', () => previewCard(task, parameters));
    box.querySelectorAll('details').forEach(el => { const key = el.querySelector('summary')?.textContent; if (folds.has(key)) el.open = folds.get(key); });
    if (I.form.needPreview) { const fold = $('#tdPreview')?.closest('details'); if (fold) fold.open = true; }
    if (I.busy) box.querySelectorAll('input, select, textarea, button').forEach(el => { el.disabled = true; });
    else if (focused?.id) { const next = document.getElementById(focused.id); next?.focus({ preventScroll: true }); if (caret && next?.setSelectionRange) next.setSelectionRange(...caret); }
    updateApprovalClock();
  }

  function updateApprovalClock() {
    document.querySelectorAll('[data-approval-until]').forEach(el => {
      const left = Math.max(0, Math.ceil((Date.parse(el.dataset.approvalUntil) - Date.now()) / 1000));
      const t = left < 60 ? left + '초' : Math.ceil(left / 60) + '분', next = el.dataset.approvalCut;
      // P18: 멈추는 타이머는 기한이 지나면 이 단계가 닫힌다 — 「지연 알림」이 아니다
      if (next !== undefined) el.textContent = left ? `기한까지 ${t} — 지나면 ${next ? `「${next}」 단계로 넘어갑니다` : '이 단계가 닫힙니다'}` : `기한 지남 — ${next ? `「${next}」 단계로 넘어가는 중` : '이 단계를 닫는 중'}`;
      else el.textContent = left ? `지연 알림까지 ${t}` : '기한 지남 · 승인 대기';
    });
  }

  /* 캡스톤 G1 · G7 사람 승인(안 고르기): 에이전트 제안 카드(추천 1 + 지는 안 펼치기) → 승인 한 번(반려는 사유와 함께). 승인자 = "나" */
  function renderApprovePanel(task) {
    const box = $('#todoPanel');
    if (I.form.approveFor !== task.id) { I.form = { ...I.form, option: null, reason: '', role: null, approveFor: task.id }; I.msg = ''; }   // 앞 단계에서 고른 역할을 이어 쓰지 않는다(W1-25)
    const act = ((I.view && I.view.instance.proc_inst_id === task.proc_inst_id && I.view.definition) || {}).activities?.find(a => a.id === task.activity_id);
    if (!act) {
      // 처리 건을 못 읽었거나(사유) 정의에 이 단계가 없으면 「불러오는 중」으로 남지 않는다
      const why = I.viewErr ? I.viewErr : I.view ? `흐름 정의에 이 단계(${task.activity_id})가 없습니다 — 흐름 판본이 바뀌었을 수 있습니다` : '';
      box.innerHTML = `<section class="todo-panel"><h3>${esc(UI.flowName(task.activity_name))}</h3>${why ? UI.errorBlock('승인 단계를 열지 못했습니다', why, { retry: true, cls: 'compact' }) : `<p class="muted">${esc(UI.t('loading'))}</p>`}</section>`;
      box.querySelector('[data-retry]')?.addEventListener('click', () => load(true));
      return;
    }
    const m = window.hydApprove.proposal(task.inputs, act.approval);
    if (!I.form.option && m.usable) I.form.option = String(((m.rec || m.options[0]) || {})[m.key]);
    // 담당 = 이 처리 건에 묶인 담당(작업 행 user_id — 서버 instances._approval_actor 가 보는 값). 일반 승인은 역할 등급 없이 그 담당 그 자체만 받는다
    const endpoint = task.user_id || (((I.view.definition || {}).roles || []).find(r => r.name === act.role) || {}).endpoint || '';
    const me = window.hydInbox?.me?.() || null;
    if (me && me.roles.includes(endpoint)) I.form.role = endpoint;      // 승인 역할 = 이 단계의 담당 역할
    const who = window.hydInbox && window.hydInbox.whoFields('td', I.form, [[endpoint, { name: UI.roleName(endpoint, I.view.definition) }]], { reasonHint: '반려할 때는 사유가 꼭 필요합니다. 결과 보고에 남습니다.' });
    const meFits = !me || (String(endpoint).startsWith('user:') ? me.id === endpoint : I.form.role === endpoint);
    const ready = !!who && !I.busy && meFits;
    const fitHint = me && !meFits ? `이 단계는 ${UI.roleName(endpoint, I.view.definition)} 역할이 승인하는데, 이 PC의 담당자가 그 역할에 들어 있지 않아 승인 · 반려할 수 없습니다.` : '';
    box.innerHTML = `<section class="todo-panel approve"><div class="detail-head"><div class="row"><h3 style="margin:0">승인 요청</h3>${UI.chip(task.status)}<span class="chip tone-neutral sm">${esc(who ? UI.roleName(endpoint, I.view.definition) : UI.roleName(task.user_id, I.view.definition))}</span>${clockChip(task)}</div><div class="sub">${esc((I.view.instance || {}).proc_inst_name || '')} · ${esc(UI.flowName(task.activity_name))}</div></div>
      ${window.hydApprove.proposalHtml(m, I.form.option, { pending: true })}
      <div class="form">${who || pickMe()}
      ${UI.actions(`<button class="btn outline" id="tdReject" ${ready ? '' : 'disabled'}>${esc(UI.t('btn.reject'))}</button><button class="btn primary" id="tdGo" ${ready && m.usable ? '' : 'disabled'}>${esc(UI.t('btn.approve'))}</button>`,
        I.msg || fitHint || (!m.usable ? '고를 안이 약속과 달라 승인할 수 없습니다 — 반려하거나 에이전트 단계를 다시 하세요' : ''))}</div></section>`;
    box.querySelector('[data-ap-back]')?.addEventListener('click', ev => { I.form.option = ev.currentTarget.dataset.apBack; I.msg = ''; renderTodoPanel(); });
    box.querySelectorAll('input[name=hopt]').forEach(r => r.addEventListener('change', () => { I.form.option = r.value; I.msg = ''; renderTodoPanel(); }));
    $('#tdReason')?.addEventListener('input', e => I.form.reason = e.target.value);
    $('#tdGo').addEventListener('click', () => approveTask(task, '승인'));
    $('#tdReject').addEventListener('click', () => approveTask(task, '반려'));
    updateApprovalClock();
  }

  // 단계 패널의 쓰기 한 번(승인 · 거절 · 제출 · 답 · 조치 카드 승인 · 거절 공통): 바쁨 → 단추를 끈 채 다시 그림 → 요청 → 다시 읽기가 끝날 때까지
  // 단추를 꺼 둔다. 응답 뒤 옛 단추가 잠깐 켜져 있다가 두 번째 요청이 「이미 처리됨」으로 거절되는 틈이 없다(W1-07)
  async function act(task, what, send, done) {
    if (I.busy) return null; I.busy = true; I.msg = ''; renderTodoPanel();
    let failed = null;
    try { await send(); I.msg = ''; if (done) done(); }
    catch (e) { failed = e; refused(task, e, what); }
    try { await load(true); } finally { I.busy = false; renderTodoPanel(); }
    return failed;
  }
  function approveTask(task, decision) {
    return act(task, '승인', () => postJ(API.process + `/api/todolist/${encodeURIComponent(task.id)}/approve`, { decision, option: decision === '승인' ? I.form.option : null,
      by: I.form.by, role: I.form.role, reason: I.form.reason }), () => { I.form.approveFor = null; });
  }

  async function previewCard(task, parameters) {
    if (I.busy) return; I.busy = true; I.msg = ''; renderTodoPanel();
    const form = I.form, decision = I.decId, option = form.option;
    try { const review = await postJ(API.process + `/api/todolist/${encodeURIComponent(task.id)}/decision-preview`, { decision, option, parameters });
      if (I.form === form && I.decId === decision && I.form.option === option) { I.form.review = review; I.form.needPreview = false; }
    }
    catch (e) { if (I.form === form) { I.form.review = null; I.msg = e.message; } }
    finally { I.busy = false; renderTodoPanel(); }
  }

  async function rejectCard(task) {
    if (I.busy || !window.hydInbox?.me?.()) return;   // P5: 「나」 없이는 거절하지 않는다(버튼도 꺼져 있다)
    const reason = I.form.reason.trim();
    if (!reason || Array.from(reason).length > 2000) { I.msg = '반려 사유를 1~2000자로 적으세요.'; renderTodoPanel(); $('#tdReason')?.focus(); return; }
    if (!I.form.by.trim() || !I.form.role) { I.msg = '담당자 정보를 읽지 못해 보낼 수 없습니다. 화면을 새로 고친 뒤 다시 해 주세요.'; renderTodoPanel(); return; }
    return act(task, '승인', () => postJ(API.process + `/api/todolist/${encodeURIComponent(task.id)}/reject-card`, {
      decision: I.decId, by: I.form.by.trim(), role: I.form.role, reason }), () => { I.dec = null; });
  }

  async function selectCard(task) {
    if (!window.hydInbox?.me?.()) return;   // P5: 「나」 없이는 승인하지 않는다(버튼도 꺼져 있다)
    const e = await act(task, '승인', () => postJ(API.process + `/api/todolist/${encodeURIComponent(task.id)}/select`, { decision: I.decId, option: I.form.option, by: I.form.by, role: I.form.role,
      reason: I.form.reason, fan_pct: I.form.fan, load_pct: I.form.load, review_id: matchingReviewId(task) }), () => { I.form.needPreview = false; });
    // 검토한 예측이 오래됐다는 거절: 승인 전에 [미리 보기]로 지금 조건을 다시 확인해야 한다 — 미리 보기 버튼을 승인 옆에 꺼내 보인다
    // 서버가 주는 기계용 코드(instance_mode.REVIEW_REQUIRED, G4-16)로 판정한다 — 안내 문장 글자로 판정하지 않는다
    if (e && e.detail?.code === 'review_required') { I.form.needPreview = true; I.form.review = null; I.msg = e.message.replace(/[.\s]*$/, '') + ' — [미리 보기]로 지금 조건을 다시 확인한 뒤 승인하세요.'; renderTodoPanel(); }
  }
  function matchingReviewId(task) {
    const option = I.dec?.options?.find(o => o.id === I.form.option);
    const cmd = p => option?.actions?.find(a => a.kind === 'command' && a.param === p);
    const parameters = { ...(cmd('fan_pct') ? { fan_pct: I.form.fan } : {}), ...(cmd('load_pct') ? { load_pct: I.form.load } : {}) };
    return window.hydCards?.reviewMatches(I.form.review, I.decId, I.form.option, parameters, { workitem: task.id }) ? I.form.review.id : null;
  }
  function submitTask(task, output) {
    return act(task, '단계', () => postJ(API.process + `/api/todolist/${encodeURIComponent(task.id)}/submit`, { output, by: actor() }));
  }

  /* ------------------------------------------------ list (Camunda card order: name / status / step / started · elapsed) */
  function renderList() {
    const box = $('#instList');
    if (I.listError) { box.innerHTML = UI.errorBlock('처리 건 목록을 읽지 못했습니다', I.listError, { retry: true, cls: 'compact' }); box.querySelector('[data-retry]')?.addEventListener('click', () => load(true)); return; }
    if (!I.instances.length) { box.innerHTML = UI.emptyGo(UI.t('inst.empty'), UI.t('inst.emptySub'), 'scenario', UI.t('nav.scenario'), 'compact'); return; }
    box.innerHTML = '';
    const paged = UI.page(I.instances, I.listShown, x => x.proc_inst_id === I.sel);
    paged.rows.forEach(x => {
      const started = new Date(x.start_date), ended = x.end_date ? new Date(x.end_date) : null;
      const span = ((ended || new Date()) - started) / 60000;
      const when = x.status === 'RUNNING' ? `${span < 1 ? UI.t('inst.justStarted') : Math.round(span) + UI.t('inst.elapsed')}` : `${ended ? Math.max(1, Math.round(span)) + UI.t('inst.took') + ' ' : ''}${UI.status(x.status)}`;
      const names = I.defNames[`${x.proc_def_id}@${x.proc_def_version}`] || {};
      const steps = (x.current_activity_ids || []).map(id => `<span class="chip step-chip">${esc(UI.flowName(names[id] || id.replace(/^task:|^ev:/, '')))}</span>`).join('');
      const stuckSteps = x.attention ? (x.attention.steps || []).map(n => `<span class="chip tone-danger sm">${esc(UI.flowName(n))}</span>`).join('') : '';
      const it = el('div', 'item inst-card ' + esc(x.status) + (x.proc_inst_id === I.sel ? ' sel' : ''), `<div class="row"><strong>${esc(x.proc_inst_name)}</strong>${x.attention ? UI.chipText(x.attention.label, 'danger') : UI.chip(x.status)}${outcomeChip(x)}</div>
        <div class="steps">${stuckSteps || steps || (x.end_label ? `<span class="chip end">${esc(x.end_label)}</span>` : '')}</div>
        <span class="sub">${esc(UI.dateTime(x.start_date))} · ${esc(when)}</span>`);
      it.dataset.inst = x.proc_inst_id;   // 같은 이름의 처리 건(같은 설비 · 같은 흐름)을 처리 건 id로 구별한다
      keyboardItem(it);
      // A161: 끝난 처리 건은 처리 기록부터(가르칠 때 "설명한 대로 됐나"를 바로 본다), 진행 중이면 진행 상황부터
      it.addEventListener('click', () => { if (I.sel !== x.proc_inst_id && window.hydRecord) I.tab = x.status === 'RUNNING' ? 'flow' : 'record'; pick(x.proc_inst_id, x.proc_inst_id === I.sel ? I.taskSel : null); });
      box.appendChild(it);
    });
    if (paged.rest) { const more = el('div', '', UI.moreButton(paged.rest)); more.querySelector('button').addEventListener('click', () => { I.listShown += UI.PAGE; renderList(); }); box.appendChild(more); }
  }

  function stepsOf(view) {
    const def = view.definition;
    if (!window.hydSteps || !def) return null;
    const workList = view.workitems.filter(w => !(def.events || []).some(e => e.id === w.activity_id))
      .map(w => ({ tracingTag: w.activity_id, status: w.status, startDate: w.start_date, endDate: w.end_date, generation: w.generation || 0 }));
    const steps = hydSteps.buildSteps({ activities: def.activities, sequences: def.sequences, events: def.events, gateways: def.gateways,
      workList, finished: ['COMPLETED', 'CANCELLED'].includes(view.instance.status) });
    return steps;
  }
  /* A161-U1: 처리 건 상세 = process-gpt-vue3 apps/todolist/WorkItem.vue 의 탭(진행 · 결과 · 기록) + Dify run/status.tsx 요약 카드.
     다시 그릴 때 실시간 처리 과정(#instTrace)과 task 상세(#taskDetailPanel)는 같은 DOM 을 옮겨 붙이고, 펼쳐 둔 접기는 제목으로 다시 연다(결함 15). */
  function keepOpen(box, fn) {
    const open = new Set([...box.querySelectorAll('details[open] > summary')].map(x => x.textContent.trim()));
    const shut = new Set([...box.querySelectorAll('details:not([open]) > summary')].map(x => x.textContent.trim()));
    fn();
    box.querySelectorAll('details > summary').forEach(x => { const t = x.textContent.trim(); if (open.has(t)) x.parentElement.open = true; else if (shut.has(t)) x.parentElement.open = false; });
  }
  function ensureTrace(view) {
    if (!window.hydTrace) return null;
    if (!I.trace || I.traceFor !== view.instance.proc_inst_id) {
      I.traceHost = document.createElement('div'); I.traceHost.id = 'instTrace';
      I.trace = hydTrace.mount(I.traceHost, { instance: () => I.sel, detachedOk: true, stepExtra: stepExtra,
        onDraw: m => { const box = document.getElementById('instSummary'); if (box) box.innerHTML = hydTrace.summaryHtml(m); } });
      I.traceFor = view.instance.proc_inst_id;
    }
    return I.trace;
  }
  function feedTrace() {
    if (I.view && window.hydStream) hydStream.fromPoll(I.view.events);
    if (I.view && I.trace && I.traceFor === I.view.instance.proc_inst_id) { hydTrace.TR.mounted.add(I.trace); I.trace.update(I.view); }
    if (I.view && I.record && I.recordFor === I.view.instance.proc_inst_id) I.record.update(I.view);   // A161 처리 기록도 2초 다시 읽기를 받는다
  }
  /* A161 처리 기록: 처리 건 하나 = 시작 → AI 에이전트 → 승인 → 시스템 처리 → 확인 → 결과 보고 이야기 (caseRecord.js). 처리 과정(trace)과 같이 DOM 을 옮겨 붙여 펼친 칸을 지킨다 */
  function ensureRecord(view) {
    if (!window.hydRecord) return null;
    if (!I.record || I.recordFor !== view.instance.proc_inst_id) {
      if (I.record) hydRecord.mounted.delete(I.record);   // keep=true 라 SSE 정리가 지우지 않는다 — 지난 처리 건 기록이 이벤트 · 다시 그리기를 계속 받지 않게
      I.recordHost = document.createElement('div'); I.recordHost.id = 'instRecord';
      I.record = hydRecord.mount(I.recordHost); I.record.keep = true;
      I.recordFor = view.instance.proc_inst_id;
    }
    return I.record;
  }
  function renderDetail() {
    const box = $('#instDetail');
    if (!I.view) {
      box.innerHTML = I.sel && I.viewErr ? UI.errorBlock(UI.t('inst.cannotOpen'), String(I.viewErr).replace(/^\d{3}\s*/, ''), { retry: true }) : UI.empty(UI.t('inst.select'), UI.t('inst.selectSub'));
      box.querySelector('[data-retry]')?.addEventListener('click', () => load(true));
      return;
    }
    const view = I.view, inst = view.instance, v = vars(inst);
    const steps = stepsOf(view);
    const trace = ensureTrace(view);
    const head = `<div class="detail-head"><div class="row"><h2>${esc(inst.proc_inst_name)}</h2>${UI.chip(inst.status)}${outcomeChip(inst)}</div><div id="instNow"></div></div>
      <div id="instSummary">${trace && trace.model ? hydTrace.summaryHtml(trace.model) : ''}</div>`
      + UI.metaFold([[UI.t('inst.started'), esc(UI.dateTime(inst.start_date))], [UI.t('inst.ended'), inst.end_date ? esc(UI.dateTime(inst.end_date)) : ''], ['ID', `<span class="mono">${esc(inst.proc_inst_id)}</span>`]]);
    const counts = { flow: steps ? steps.filter(x => x.state === 'current').length || null : null, log: view.workitems.length };
    const tabs = UI.tabs([['flow', UI.t('inst.tab.flow'), counts.flow], ['record', UI.t('inst.tab.record')], ['result', UI.t('inst.tab.result')], ['log', UI.t('inst.tab.log'), counts.log]], I.tab, 'data-inst-tab');
    const record = ensureRecord(view);
    const keepTd = box.querySelector('#taskDetailPanel');
    keepOpen(box, () => {
      box.innerHTML = head + tabs + `<div class="inst-detail-tabs"><div class="tab-pane ${I.tab === 'flow' ? 'on' : ''}" data-pane="flow">${flowPane(view)}</div><div class="tab-pane ${I.tab === 'record' ? 'on' : ''}" data-pane="record"><div id="instRecord"></div></div><div class="tab-pane ${I.tab === 'result' ? 'on' : ''}" data-pane="result">${resultPane(view, v)}</div><div class="tab-pane ${I.tab === 'log' ? 'on' : ''}" data-pane="log">${logPane(view)}</div></div>`;
      const slot = box.querySelector('#instTrace'); if (slot && I.traceHost) slot.replaceWith(I.traceHost);
      const rslot = box.querySelector('#instRecord'); if (rslot && I.recordHost) rslot.replaceWith(I.recordHost);
      const td = box.querySelector('#taskDetailPanel'); if (td && keepTd && keepTd !== td) td.replaceWith(keepTd);
      // 패널들도 이 안에서 그린다 — 펼쳐 둔 다시 수행 · 실행 효과 · 보류 접기가 다시 그리기로 닫혀 입력 칸 포커스를 잃지 않게
      window.hydRework?.mount(box.querySelector('#reworkPanel'), { view, by: actor(), changed: () => load(true) });
      window.hydEffects?.mount(box.querySelector('#effectsPanel'), { view, by: actor(), changed: () => load(true) });
      window.hydTaskDeferral?.mount(box.querySelector('#taskDeferralPanel'), { view, by: actor(), changed: () => load(true) });
    });
    if (trace) trace.update(view);
    if (record) record.update(view);
    const showTab = k => { I.tab = k; box.querySelectorAll('[data-inst-tab]').forEach(x => { x.classList.toggle('on', x.dataset.instTab === k); x.setAttribute('aria-selected', String(x.dataset.instTab === k)); }); box.querySelectorAll('.tab-pane').forEach(p => p.classList.toggle('on', p.dataset.pane === I.tab)); if (I.tab === 'flow') mountFlow(view); if (I.tab === 'log') load(true); };
    box.querySelectorAll('[data-inst-tab]').forEach(b => b.addEventListener('click', () => showTab(b.dataset.instTab)));
    box.querySelector('[data-open-result]')?.addEventListener('click', () => { showTab('result'); box.querySelector('.inst-detail-tabs')?.scrollIntoView({ block: 'start', behavior: 'smooth' }); });
    // A161: 결과 보고 카드의 "처리 기록 보기" → 처리 기록 탭
    box.querySelectorAll('[data-open-record]').forEach(b => b.addEventListener('click', () => { showTab('record'); box.querySelector('.inst-detail-tabs')?.scrollIntoView({ block: 'start', behavior: 'smooth' }); }));
    box.querySelector('[data-events-more]')?.addEventListener('click', () => { I.eventsShown += 40; renderDetail(); });
    if (I.tab === 'flow') mountFlow(view);
    window.hydTaskDetail?.mount(box.querySelector('#taskDetailPanel'));
    wireApprovalButtons(box);
  }
  // agent step: 단계 닫기 · 실행 취소 (사유 한 줄) + 자세히 — inside the trace step (A161-U1; buttons are delegated because the trace redraws by itself)
  function stepExtra(s) {
    const view = I.view, w = s.w; if (!view || !w) return '';
    const inst = view.instance;
    const act = (view.definition?.activities || []).find(a => a.id === w.activity_id);
    const canClose = (w.agent_orch && w.agent_mode && (w.status === 'PENDING' || (w.status === 'IN_PROGRESS' && ['FAILED', 'CANCELLED'].includes(w.draft_status)))) || (act?.type === 'serviceTask' && w.status === 'PENDING');
    const closeBtn = canClose && inst.status === 'RUNNING' ? `<button class="btn small outline" data-close-task="${esc(w.id)}">${esc(UI.t('btn.closeTask'))}</button>` : '';
    const cancelBtn = w.agent_orch && w.agent_mode && inst.status === 'RUNNING' && w.status === 'IN_PROGRESS' && w.draft_status === 'STARTED' && w.consumer ? `<button class="btn small outline" data-cancel-task="${esc(w.id)}">${esc(UI.t('btn.cancelTask'))}</button>` : '';
    const reasonForm = I.closing && I.closing.id === w.id ? `<div class="form inline-form" data-reason-form><p class="field-hint">멈춘 단계를 취소로 닫습니다. 업무 실행 성공이나 설비 복구로 기록하지 않습니다.</p><div class="form-grid">${UI.field({ label: '담당자', required: true, input: UI.actorInput('data-close-by', I.closing.by || '') })}${UI.field({ label: I.closing.kind === 'close' ? UI.t('inst.closeReason') : UI.t('inst.cancelReason'), required: true, cls: 'wide', input: `<input data-close-reason value="${esc(I.closing.reason || '')}">` })}</div>${UI.actions(`<button class="btn small outline" data-close-abort>${esc(UI.t('btn.cancel'))}</button><button class="btn small primary" data-close-go ${I.busy ? 'disabled' : ''}>${esc(UI.t('btn.confirm'))}</button>`, I.pmsg.close || '')}</div>` : '';
    return `<div class="row-wrap tr-actions"><button type="button" class="btn small ghost" data-td-open="${esc(w.id)}">${esc(UI.t('trace.detail'))}</button>${closeBtn}${cancelBtn}</div>${reasonForm}`;
  }
  function mountFlow(view) {
    const host = $('#instFlow'); if (!host || !window.hydFlow) return;
    hydFlow.mount(host, hydFlow.render(view.definition, { workitems: view.workitems, instance: view.instance, caption: '', vertical: hydFlow.narrow(host) }), view.instance.proc_inst_id);
  }

  /* 결과 탭: 결정 · 설비 응답 · 효과 확인 · 정비 요청 카드 + 값(라벨 붙은 읽기 전용) + 시작 값 접기 */
  function resultPane(view, v) {
    const inst = view.instance;
    // 결과 = 결과 보고 카드 하나(resultReport.js). 단계마다 무엇을 했는지는 「처리 기록」 탭이 보인다 — 정의의 단계 id 로 카드를 고르던 묶음은
    // 기준 흐름(task:select …)에만 맞고 수업 흐름(T_approve …)에서는 비어 지웠다(W1-05)
    const report = window.hydResultReport ? hydResultReport.html(view) : '';
    let html = report || UI.empty(UI.t('inst.noResult'), inst.status === 'RUNNING' ? UI.t('inst.noResultSub') : '', 'compact');
    // 값: label = definition data name, key as small text, structured values folded (read-only form)
    const internal = new Set(['decision', 'decision_id', 'guide_card', 'candidates', 'compliance', 'incident', 'commands', 'chosen_option', 'alert', 'alert_id']);
    const varRows = (inst.variables_data || []).filter(row => !internal.has(row.key)).map(row => {
      const value = row.value, name = UI.terms['var.' + row.key] || (row.name && row.name !== row.key ? row.name.replace(/\s*[\(—(].*$/, '') : row.key);
      const shown = row.key === 'pattern' ? UI.patternName(value) : row.key === 'chosen_skill_kind' ? (value === 'control' ? UI.t('chip.control') : value === 'work_order' ? UI.t('chip.workOrder') : value)
        : row.key === 'cause' ? (((v.guide_card || {}).causes || []).find(c => c.id === value) || (v.guide_card || {}).topCause || {}).name || UI.name(value)
        : row.key === 'failure_mode' ? UI.idText((typeof (v.guide_card || {}).failureMode === 'object' ? (v.guide_card.failureMode || {}).name : (v.decision || {}).failureMode) || UI.name(value))
        : row.key === 'chosen_skill' ? ((v.chosen_option || {}).name || UI.name(value)) : row.key === 'approved_role' ? who(value) : typeof value === 'string' ? UI.idText(value) : value;
      const body = value !== null && typeof value === 'object' ? UI.fold(esc(UI.t('inst.structured')), `<pre>${esc(JSON.stringify(value, null, 2))}</pre>`, { cls: 'small' }) : esc(shown === true ? UI.t('yes') : shown === false ? UI.t('no') : shown ?? UI.t('inst.noValue'));
      const source = (inst.variable_sources || {})[row.key];
      const producer = source?.kind === 'workitem' ? view.workitems.find(w => w.id === source.id) : null;
      const origin = source?.kind === 'input' ? UI.t('inst.source.input') : source?.kind === 'workitem' ? UI.flowName(producer?.activity_name || source.activity) : source?.kind === 'runtime' ? UI.t('inst.source.runtime') : UI.t('inst.source.none');
      return UI.readonly(name, body, origin);
    }).join('');
    // A141: 값 격자(출처 포함)는 기본 접기
    const varCount = (inst.variables_data || []).filter(row => !internal.has(row.key)).length;
    html += `<div class="stack-list" style="margin-top:var(--s4)">` + UI.fold(`${esc(UI.t('inst.valuesFold'))} <span class="chip tone-neutral sm">${varCount}</span>`, `<div class="ro-grid">${varRows || `<div class="muted">${esc(UI.t('empty.noData'))}</div>`}</div>`)
      + UI.fold(esc(UI.t('inst.initial')), inst.initial_variables == null ? `<p class="muted">${esc(UI.t('empty.noData'))}</p>` : `<pre>${esc(JSON.stringify(inst.initial_variables, null, 2))}</pre>`) + '</div>';
    return html;
  }

  /* 흐름 탭: 흐름도 + 단계 행(Dify tracing) + 패널 4(접기, 열어야 할 때만) */
  function flowPane(view) {
    const inst = view.instance;
    let html = `<div class="flow-wrap" id="instFlow"></div><div id="taskDetailPanel"></div>`;   // U1: task 상세 패널 자리 (taskDetail.js)
    if (inst.status === 'RUNNING' && inst.flow_state?.end_arrivals?.length) html += `<p class="kv-line">${esc(UI.t('inst.endWaiting'))}</p>`;
    const waitingDependencies = Object.entries(inst.flow_state?.dependency_schedule || {}).filter(([id, spec]) => spec.flow_arrived && view.workitems.some(w => w.id === id && w.status === 'TODO'));
    if (waitingDependencies.length) html += UI.card({ title: esc(UI.t('inst.waitingResult')), cls: 'soft', body: waitingDependencies.map(([id, spec]) => {
      const task = view.workitems.find(w => w.id === id);
      const producers = [...new Set(spec.requires.map(dep => view.workitems.find(w => w.id === dep.workitem)?.activity_name || dep.activity))];
      const missingInitial = (spec.waiting_for || []).filter(x => x.reason === 'initial_input_unavailable').map(x => x.variable);
      const reason = missingInitial.length ? `시작 값 ${missingInitial.join(', ')}이 없습니다. 입력을 확인해 새 처리 건을 시작하세요.`
        : (spec.waiting_for || []).some(x => x.reason === 'fresh_output_unavailable') ? '필요한 결과값이 없어 대기 중입니다.' : `${producers.map(UI.flowName.bind(UI)).join(', ')}의 결과가 확정되면 시작합니다.`;
      return `<p><b>${esc(UI.flowName(task?.activity_name || spec.activity))}</b>: ${esc(reason)}</p>`; }).join('') });
    // 결과 보고 카드(승인 뒤 시스템 실행 · 확인 → 결과 보고)는 「결과」 탭 한 곳에만 그린다 — 여기는 그리로 가는 길 하나
    if (window.hydResultReport && hydResultReport.html(view)) html += `<p class="kv-line see-result">승인 뒤의 실행과 확인, 결과 보고는 「${esc(UI.t('inst.tab.result'))}」 탭에 있습니다. <button type="button" class="link-btn" data-open-result>${esc(UI.t('inst.tab.result'))} 탭 열기 →</button></p>`;
    html += `<div class="sec-row"><h3>${esc(UI.t('trace.title'))}</h3>${inst.status === 'RUNNING' ? `<span class="live-conn ${window.hydStream && hydStream.connected() ? 'on' : 'off'}" data-live-conn>${esc(UI.t(window.hydStream && hydStream.connected() ? 'header.connected' : 'header.connecting'))}</span>` : ''}</div><div id="instTrace"></div>`;
    html += `<div class="stack-list" style="margin-top:var(--s4)">${approvalHtml(view)}${workOrderRetryHtml(view)}<div id="taskDeferralPanel"></div><div id="effectsPanel"></div><div id="reworkPanel"></div>` +
      ((view.reworks || []).length ? UI.fold(`${esc(UI.t('inst.reworkHistory'))} <span class="chip tone-neutral sm">${view.reworks.length}</span>`, view.reworks.map(r => `<p>${esc(r.generation)}${esc(UI.t('inst.gen'))} · ${esc(UI.who(r.request.by))} (${esc(who(r.request.role))}) · ${esc(r.request.reason)}</p>`).join('')) : '') + '</div>';
    return html;
  }
  // 복구 폼의 역할 = 그 승인을 했던 역할(승인 기록). 쓰는 사람은 모든 역할을 맡으므로 고르게 하지 않는다
  const consentRole = (a, roles) => roles.includes(a?.payload?.role) ? a.payload.role : '';
  function workOrderRetryHtml(view) {
    const failed = view.workitems.filter(w => w.tool === 'enterprise:WO_CREATE' && w.status === 'PENDING');
    const approval = (view.approvals || []).find(a => a.status === 'DELIVERED');
    const roles = Object.keys(approval?.payload?.plan?._snapshot?.roles || {});
    return failed.map(w => { const f = retryForm(w.id); return UI.fold(`${esc(UI.t('inst.woFailed'))} ${UI.chipText('실패', 'danger')}`, `<div data-approval-panel="${esc(w.id)}"><p class="neg">${esc(w.log || '')}</p><p class="field-hint">자동 재시도를 마쳤습니다. 오류를 해결한 뒤 승인했던 같은 내용으로 다시 전달할 수 있습니다.</p>
      <div class="form"><section class="form-section"><div class="form-grid">${UI.actorInput(`data-retry-by="${esc(w.id)}"`, f.by)}${(r => r ? UI.readonly('승인 역할', esc(who(r))) + `<input type="hidden" data-retry-role="${esc(w.id)}" value="${esc(r)}">` : `<input type="hidden" data-retry-role="${esc(w.id)}" value=""><p class="form-msg neg">승인 기록에서 승인 역할을 읽지 못했습니다.</p>`)(consentRole(approval, roles))}</div></section>
      ${UI.actions(`<button class="btn primary" data-work-order-retry="${esc(w.id)}" ${I.busy || !roles.length ? 'disabled' : ''}>${esc(UI.t('btn.retry'))}</button>`, !roles.length ? '승인 원문을 확인할 수 없어 별도 검토가 필요합니다.' : I.pmsg[w.id] || '')}</div></div>`, { open: true }); }).join('');
  }
  // 재전달 · 폐기 폼의 칸 값은 다시 그려도 남도록 상태에 둔다(작업 id 마다). 담당자 기본값은 지금의 승인자 칸 값("나"면 그 id)
  function retryForm(key) {
    const f = I.retryForm[key] || (I.retryForm[key] = { by: null, role: '', reason: '' });
    if (f.by == null || (String(f.by).startsWith('user:') && f.by !== actor())) f.by = actor();
    return f;
  }
  // A147: 승인 폐기 요청은 보내기 전에 sessionStorage 에 보존(같은 request_id) — 응답을 잃으면 같은 요청으로 결과만 다시 확인한다(instanceRework.js 와 같은 방식)
  const discardKey = wid => 'hyd:discard:' + wid;
  function discardPending(wid) { try { return JSON.parse(sessionStorage.getItem(discardKey(wid)) || 'null'); } catch (_) { return I.discardPending?.[wid] || null; } }
  function setDiscardPending(wid, req) {
    I.discardPending = { ...(I.discardPending || {}), [wid]: req };
    try { req ? sessionStorage.setItem(discardKey(wid), JSON.stringify(req)) : sessionStorage.removeItem(discardKey(wid)); } catch (_) { /* in-memory copy above */ }
    if (!req) delete I.discardPending[wid];
  }
  function approvalHtml(view) {
    const approvals = view.approvals || [];
    if (!approvals.length) return '';
    return approvals.map(a => {
      const p = a.payload || {}, snapshot = (p.plan || {})._snapshot || {};
      const reviewRequired = (a.history || []).at(-1)?.kind === 'review_required';
      const option = (p.plan || {}).option || {};
      const roles = Object.keys(snapshot.roles || {});
      const commandPending = view.workitems.some(w => w.tool === 'incident:command' && w.status === 'PENDING');
      const reviewable = view.instance.status === 'RUNNING' && (a.status === 'FAILED' || (a.status === 'DELIVERED' && commandPending));
      let lost = discardPending(a.todo_id);
      if (lost && a.status === 'DISCARDED') { setDiscardPending(a.todo_id, null); lost = null; }   // the server holds the outcome: nothing to replay
      const f = retryForm(a.todo_id), dp = I.discardPreview[a.todo_id];
      const retry = lost ? `<p>앞서 보낸 폐기 요청의 응답을 받지 못했습니다. 아래 단추로 결과를 확인하세요. 같은 요청이라 두 번 처리되지 않습니다.</p>${UI.actions(`<button class="btn" data-discard-retry="${esc(a.todo_id)}" ${I.busy ? 'disabled' : ''}>폐기 결과 확인</button>`, I.pmsg[a.todo_id] || '')}`
        : reviewable ? `<p class="field-hint">${reviewRequired ? '현재 조건이 달라 기존 동의를 전달할 수 없습니다. 판단 단계의 다시 수행으로 새 판단과 승인을 받으세요.' : a.status === 'FAILED' ? '승인한 내용은 보존됐습니다. 오류를 확인한 뒤 같은 내용을 다시 전달할 수 있습니다.' : '조건 변경으로 명령이 보류됐다면 판단 단계에서 새 검토를 시작하세요. 사건이 종료됐다면 아래에서 실행 효과를 확인하고 취소할 수 있습니다.'}</p>
        <div class="form"><section class="form-section"><div class="form-grid">${UI.actorInput(`data-retry-by="${esc(a.todo_id)}"`, f.by)}${(r => r ? UI.readonly('승인 역할', esc(who(r))) + `<input type="hidden" data-retry-role="${esc(a.todo_id)}" value="${esc(r)}">` : `<input type="hidden" data-retry-role="${esc(a.todo_id)}" value=""><p class="form-msg neg">승인 기록에서 승인 역할을 읽지 못했습니다.</p>`)(consentRole(a, roles))}
        ${UI.field({ label: '폐기 ' + UI.t('form.reason'), cls: 'wide', hint: '사건이 종료되고 실제 조치가 없음을 확인한 경우에만 승인을 폐기하고 처리 건을 취소할 수 있습니다.', input: `<input data-discard-reason="${esc(a.todo_id)}" value="${esc(f.reason)}" placeholder="후속 조치를 진행하지 않고 종료하는 이유">` })}</div></section>
        ${UI.actions(`${a.status === 'FAILED' && !reviewRequired ? `<button class="btn primary" data-approval-retry="${esc(a.todo_id)}" ${I.busy ? 'disabled' : ''}>${esc(UI.t('btn.retry'))}</button>` : ''}<button class="btn outline" data-approval-discard-preview="${esc(a.todo_id)}" ${I.busy ? 'disabled' : ''}>${esc(UI.t('btn.effects'))}</button>`, I.pmsg[a.todo_id] || '')}
        <div data-discard-preview role="status">${dp ? discardPreviewHtml(dp) : ''}</div></div>` : '';
      const discarded = a.status === 'DISCARDED' ? `<p class="field-hint">${(a.history || []).at(-1)?.via === 'rework' ? '다시 수행 요청으로 이전 승인을 폐기했습니다. 새 판단과 새 승인이 필요합니다.' : '처리 건을 취소했습니다.'} 이전 승인·오류는 보존됩니다.</p>${UI.fold(esc(UI.t('raw')), `<pre>${esc(JSON.stringify((a.history || []).at(-1), null, 2))}</pre>`, { cls: 'small' })}` : '';
      return UI.fold(`${esc(UI.t('inst.approval'))} ${UI.deliveryChip(a.status)}`, `<div data-approval-panel="${esc(a.todo_id)}"><p class="kv-line">${esc(option.name || p.option)} · ${esc(UI.t('card.approver'))} <b>${esc(who(p.role))}</b> · 전달 시도 ${esc(a.attempts)}회</p>
        ${a.error ? UI.fold('오류 기록', `<pre>${esc(a.error)}</pre>`, { cls: 'small', open: true }) : ''}${retry}${discarded}</div>`, { open: reviewable || a.status === 'FAILED' || !!lost });
    }).join('');
  }

  /* 기록 탭: 단계 표 + 에이전트 활동(도구 호출 · 결과 묶음) + 지식 반영(접기) */
  function logPane(view) {
    const inst = view.instance;
    const rows = view.workitems.map(w => `<tr class="${esc(w.status)}"><td>${esc(UI.flowName(w.activity_name))}${w.generation ? `<br><small class="muted">${esc(w.generation)}${esc(UI.t('inst.gen'))}</small>` : ''}</td><td>${UI.chip(w.status)}${w.draft_status && w.status !== 'DONE' ? `<br>${UI.chip(w.draft_status)}` : ''}</td>
      <td>${esc(who(w.user_id))}</td>
      <td>${esc(UI.time(w.start_date))}${w.end_date ? ' → ' + esc(UI.time(w.end_date)) : ''}${w.due_date && !w.end_date ? `<br><small class="muted">${esc(UI.t('inst.due'))} ${esc(UI.time(w.due_date))}</small>` : ''}</td>
      <td class="log">${esc(UI.logText(w.log || ''))}${w.output && Object.keys(w.output).length ? UI.fold(`${esc(UI.t('inst.output'))} ${esc(Object.keys(w.output).filter(k => k !== 'text').join(', ') || 'text')}`, `<pre>${esc(JSON.stringify(w.output, null, 1).slice(0, 1500))}</pre>`, { cls: 'small' }) : ''}${UI.fold(esc(UI.t('raw')), `<pre>${esc(JSON.stringify({ id: w.id, activity_id: w.activity_id, log: w.log, generation: w.generation, agent_orch: w.agent_orch, agent_mode: w.agent_mode, consumer: w.consumer, draft_status: w.draft_status, supersedes_id: w.supersedes_id, gateway_decisions: w.gateway_decisions }, null, 1))}</pre>`, { cls: 'small' })}</td></tr>`).join('');
    // a tool call and its result become one record with the duration
    const evs = view.events.slice();
    const started = new Map(); evs.forEach(e => { if (e.event_type === 'tool_usage_started' && e.data?.tool_use_id) started.set(e.data.tool_use_id, e); });
    const merged = new Set();
    // A141: 최근 20건만 먼저, 나머지는 더 보기. 도구 이름은 UI.toolName(원문은 각 기록의 원문 접기에 그대로)
    const all = evs.reverse().filter(e => !(e.event_type === 'tool_usage_started' && evs.some(x => x.event_type === 'tool_usage_finished' && x.data?.tool_use_id === e.data?.tool_use_id)));
    const events = all.slice(0, I.eventsShown).map(e => {
      let detail = eventDetail(e), name = e.job_id === 'TASK_REVIEW_REQUIRED' ? e.job_id : e.event_type;
      if (e.event_type === 'tool_usage_finished') { const s0 = started.get(e.data?.tool_use_id); if (s0) detail = `${UI.toolName(e.data.tool)} · ${hydTrace.fmtMs(new Date(e.timestamp) - new Date(s0.timestamp))}`; name = 'tool_usage_started'; }
      // A132: the worker says where the result came from (result_source file | message); only the file case gets a chip
      const chips = e.event_type === 'task_completed' && e.data?.result_source === 'file' ? `<span class="chip tone-neutral sm">${esc(UI.t('inst.resultFile'))}</span>` : '';
      return UI.eventRecord({ time: e.timestamp, name, actor: e.crew_type || '', detail, raw: e.data, chips });
    }).join('') + (all.length > I.eventsShown ? `<button type="button" class="btn small" data-events-more style="width:100%;margin-top:var(--s2)">${esc(UI.t('inst.eventsMore'))} (남은 ${all.length - I.eventsShown}건)</button>` : '');
    return `<h3 style="font-size:14px;margin:0 0 var(--s2)">${esc(UI.t('inst.steps'))}</h3><div class="table-scroll"><table class="inst-table"><thead><tr><th>${esc(UI.t('inst.stepTable.step'))}</th><th>${esc(UI.t('inst.stepTable.status'))}</th><th>${esc(UI.t('inst.stepTable.who'))}</th><th>${esc(UI.t('inst.stepTable.when'))}</th><th>${esc(UI.t('inst.stepTable.result'))}</th></tr></thead><tbody>${rows}</tbody></table></div>
      <h3 style="font-size:14px;margin:var(--s6) 0 var(--s2)">${esc(UI.t('inst.events'))} <span class="chip tone-neutral sm">${view.events.length}</span></h3><div class="inst-events">${events || `<div class="muted">${esc(UI.t('empty.noData'))}</div>`}</div>
      <div style="margin-top:var(--s4)">${UI.fold(esc(UI.t('inst.graph')), graphHtml(inst))}</div>`;
  }
  function graphHtml(inst) {
    const g = I.graph;
    if (!g && !I.caseProjection) return `<p class="muted">${esc(UI.t('loading'))}</p>`;   // 이 탭을 연 뒤 첫 읽기가 끝나기 전
    const pending = g && g.projection, cases = I.caseProjection;
    const sync = `<p class="kv-line">${esc(UI.t('inst.projectionPending'))}: ${pending ? esc(pending.pending) + '건' : esc(UI.t('inst.projectionNone'))} · ${esc(UI.t('inst.projectionAll'))}: ${cases && !cases.error ? esc(cases.pending) + '건' : esc(UI.t('inst.projectionNone'))}</p>
      ${cases && cases.worker_running === false ? '<p class="neg" role="status">지식 지도에 반영하는 작업이 멈춰 있어 반영이 늦어집니다. 잠시 뒤에도 그대로면 강사에게 알리세요.</p>' : ''}
      ${cases && cases.error ? `<p class="neg">반영 상태 조회 실패: ${esc(cases.error)}</p>` : ''}
      ${cases?.knowledge ? `<p class="muted">지식 연결 변경 확인: <span data-knowledge-checked>${esc(knowledgeChecked(cases))}</span>${cases.knowledge.last_error ? '<br><span class="neg">연결 재확인 실패: ' + esc(cases.knowledge.last_error) + '</span>' : ''}</p>` : ''}
      ${pending && pending.last_error ? UI.fold(pending.last_error.startsWith('ProjectionConflict:') ? '반영이 멈춘 까닭 (오류 원문)' : '반영을 다시 시도하는 중 (오류 원문)', `<pre>${esc(pending.last_error)}</pre>`, { cls: 'small' }) : ''}
      ${pending?.last_error?.startsWith('ProjectionConflict:') || cases?.items?.some(x => x.last_error?.startsWith('ProjectionConflict:')) ? '<p class="neg" role="status">이 처리 건의 기록과 지식 지도의 내용이 서로 달라 자동 반영을 멈췄습니다. 화면에서 고칠 수 없으니 강사에게 알리세요.</p>' : ''}
      ${cases && (cases.items || []).some(x => x.last_error) ? UI.fold('사건 · 판단 반영 오류', `<pre>${esc(JSON.stringify(cases.items.filter(x => x.last_error), null, 2))}</pre>`, { cls: 'small' }) : ''}`;
    if (!g) return sync + `<div class="muted">${esc(UI.t('loading'))}</div>`;
    if (g.error) return sync + `<div class="muted">${esc(UI.t('error.load'))}: ${esc(g.error)}</div>`;
    const cy = UI.fold(esc(UI.t('inst.query')), `<pre>${esc(g.cypher)}</pre><pre>${esc(JSON.stringify(g.params))}</pre>`, { cls: 'small' });
    const x = g.graph;
    if (!x) return sync + '<div class="muted">조회 가능한 반영 내역이 없습니다.</div>' + cy;
    const rows = (x.workitems || []).map(w => `<tr class="${esc(w.status)}"><td>${esc(UI.flowName(w.activity_name || w.activity_id || ''))}</td><td>${UI.chip(w.status)}</td><td>${w.executes ? `${esc(w.executes_name || '')}<br><small class="muted">${esc(w.executes_type || '')}</small>` : '–'}</td><td>${w.assigned_to ? w.assigned_to.split(',').map(id => esc(who(id))).join(', ') : '–'}</td></tr>`).join('');
    const warnings = (x.warnings || []).map(w => `<div class="neg">확인 필요: ${esc(w)}</div>`).join('');
    const version = x.definition || {};
    return sync + warnings + `<p class="kv-line">흐름 <b title="${esc(version.id || '')}">${esc(UI.defName(version.id || ''))}</b> · 판 ${esc(version.version || x.process.version || '')}${x.asset ? ` · ${esc(UI.t('dec.asset'))} ${esc(x.asset)}` : ''}</p>
      <table class="inst-table"><thead><tr><th>${esc(UI.t('step'))}</th><th>${esc(UI.t('inst.stepTable.status'))}</th><th>${esc(UI.t('knowledge'))}</th><th>${esc(UI.t('inst.stepTable.who'))}</th></tr></thead><tbody>${rows}</tbody></table>${cy}`;
  }
  function eventDetail(e) {
    const d = e.data || {};
    if (d.recovery === 'verify_external_effect') return '외부 작업이 이미 실행됐을 수 있어 자동 재시도를 멈췄습니다. 외부 시스템의 실제 처리 결과를 확인하세요. ' + (d.raw_error || '');
    if (d.recovery === 'new_judgment_and_consent') return '현재 조건 검사로 명령을 보류했습니다. 판단 단계에서 새 검토와 승인을 진행하세요. ' + ((d.assessment || {}).reasons || []).join('; ');
    if (d.tool) return `${UI.toolName(d.tool)}${d.input ? ' ' + String(hydWords.ask(d.tool, d.input) || '').slice(0, 120) : ''}${d.output ? ' → ' + String(hydWords.got(d.tool, d.output) || '').slice(0, 120) : ''}`;      // 처리 과정(trace.js)과 같은 요약 — JSON 원문은 각 기록의 원문 접기에
    if (d.goal) return `${UI.logText(d.goal)}${d.name ? ' · ' + UI.who(d.name) : ''}`;
    if (d.text || d.question) return humanQuestionText(d).slice(0, 160);
    return UI.logText(d.message || d.note || d.friendly || d.raw_error || d.reason || '') || d.content || (d.output_keys ? UI.t('inst.output') + ' ' + d.output_keys.join(', ') : '') || (d.answer ? UI.t('form.answer') + ' ' + d.answer : '');
  }

  /* ------------------------------------------------ buttons inside the 흐름 tab (inline reason instead of window.prompt) */
  function wireStepButtons(box) {        // A161-U1: delegated once — the trace redraws its own steps
    if (box._stepWired) return; box._stepWired = true;
    box.addEventListener('click', async e => {
      const b = e.target.closest('[data-close-task],[data-cancel-task]');
      if (b) { I.closing = { id: b.dataset.closeTask || b.dataset.cancelTask, kind: b.dataset.closeTask ? 'close' : 'cancel', reason: '', by: actor() }; I.pmsg.close = ''; I.trace?.draw(); return; }
      if (e.target.closest('[data-close-abort]')) { I.closing = null; I.trace?.draw(); return; }
      const go = e.target.closest('[data-close-go]'); if (!go || I.busy || !I.closing) return;
      const reason = (I.closing.reason || '').trim(), by = (I.closing.by || '').trim();
      if (!by) { I.pmsg.close = '담당자 정보를 읽지 못했습니다. 화면을 새로 고친 뒤 다시 해 주세요.'; I.trace?.draw(); return; }
      if (!reason) { I.pmsg.close = UI.t('form.err.reason'); I.trace?.draw(); return; }
      I.busy = true; go.disabled = true;
      try { await postJ(API.process + `/api/todolist/${encodeURIComponent(I.closing.id)}/${I.closing.kind}`, { by, reason }); I.pmsg.close = ''; I.closing = null; }
      catch (err) { I.pmsg.close = err.message; }
      finally { I.busy = false; await load(true); I.trace?.draw(); }
    });
    box.addEventListener('input', e => { if (e.target.matches('[data-close-reason]') && I.closing) I.closing.reason = e.target.value; if (e.target.matches('[data-close-by]') && I.closing) I.closing.by = e.target.value; });
  }
  async function sendDiscard(wid) {
    const req = discardPending(wid); if (!req || I.busy) return;
    I.busy = true;
    try { await postJ(API.process + `/api/todolist/${encodeURIComponent(wid)}/approval-discard`, req); setDiscardPending(wid, null); I.pmsg[wid] = ''; }
    catch (e) {
      I.pmsg[wid] = e.message;
      if (e.status >= 400 && e.status < 500) setDiscardPending(wid, null);   // refused (other request, wrong role …): a new preview is needed
    }
    finally { I.busy = false; await load(true); }
  }
  function discardPreviewHtml(p) {
    const evidence = p.evidence;
    return UI.card({ title: '폐기 전 확인', cls: 'soft', body: `<p>${esc(UI.t('case'))} ${UI.chip(evidence.incident.state)} · ${esc(UI.t('command'))} 없음 · 업무 실행 기록 ${esc(evidence.enterprise_receipts.length)}건</p>
      <p>${esc(evidence.outcome)}</p><p>취소할 남은 단계 ${esc(evidence.cancel_workitems.length)}건 · ${esc(UI.t('form.reason'))}: ${esc(p.reason)}</p>
      ${UI.actions(`<button class="btn danger" data-confirm-discard ${I.busy ? 'disabled' : ''}>승인 폐기 · 처리 건 취소</button>`)}` });
  }
  function wireApprovalButtons(box) {
    // 칸 값을 상태로(다시 그려도 남는다). 값을 바꾸면 이미 받아 둔 폐기 전 확인은 무효
    box.querySelectorAll('[data-retry-by],[data-retry-role],[data-discard-reason]').forEach(input => {
      const key = input.dataset.retryBy || input.dataset.retryRole || input.dataset.discardReason;
      const field = 'retryBy' in input.dataset ? 'by' : 'retryRole' in input.dataset ? 'role' : 'reason';
      const save = () => {
        const f = retryForm(key); if (f[field] === input.value) return;
        f[field] = input.value;
        if (I.discardPreview[key]) { delete I.discardPreview[key]; const r = input.closest('[data-approval-panel]')?.querySelector('[data-discard-preview]'); if (r) r.innerHTML = ''; }
      };
      input.addEventListener('input', save); input.addEventListener('change', save);
    });
    box.querySelectorAll('[data-discard-retry]').forEach(button => button.addEventListener('click', () => { button.disabled = true; sendDiscard(button.dataset.discardRetry); }));
    box.querySelectorAll('[data-approval-retry], [data-work-order-retry]').forEach(button => button.addEventListener('click', async () => {
      if (I.busy) return;
      const panel = button.closest('[data-approval-panel]');
      const by = panel.querySelector('[data-retry-by]').value.trim();
      const role = panel.querySelector('[data-retry-role]').value;
      const key = button.dataset.workOrderRetry || button.dataset.approvalRetry;
      if (!by || !role) { I.pmsg[key] = UI.t('form.err.byRole'); renderDetail(); return; }
      I.busy = true; button.disabled = true;
      try {
        const workOrder = button.dataset.workOrderRetry;
        const path = workOrder ? `${encodeURIComponent(workOrder)}/work-order-retry` : `${encodeURIComponent(button.dataset.approvalRetry)}/approval-retry`;
        await postJ(API.process + `/api/todolist/${path}`, { by, role });
        I.pmsg[key] = '';
      } catch (e) { I.pmsg[key] = e.message; }
      finally { I.busy = false; await load(true); }
    }));
    box.querySelectorAll('[data-approval-discard-preview]').forEach(button => {
      const panel = button.closest('[data-approval-panel]');
      const result = panel.querySelector('[data-discard-preview]');
      const wid = button.dataset.approvalDiscardPreview;
      const wireConfirm = target => target.querySelector('[data-confirm-discard]')?.addEventListener('click', async event => {
        const p = I.discardPreview[wid];
        if (I.busy || !p) return;
        event.currentTarget.disabled = true;
        delete I.discardPreview[wid];
        setDiscardPending(wid, { by: p.by, role: p.role, reason: p.reason, request_id: p.request_id });
        await sendDiscard(wid);
      });
      wireConfirm(result);   // 다시 그려도 받아 둔 폐기 전 확인(같은 request_id)이 남는다
      button.addEventListener('click', async () => {
        if (I.busy) return;
        const by = panel.querySelector('[data-retry-by]').value.trim();
        const role = panel.querySelector('[data-retry-role]').value;
        const reason = panel.querySelector('[data-discard-reason]').value.trim();
        if (!by || !role || !reason) { result.textContent = UI.t('form.err.byRoleReason'); return; }
        I.busy = true; button.disabled = true;
        try {
          const evidence = await postJ(API.process + `/api/todolist/${encodeURIComponent(wid)}/approval-discard-preview`, { by, role });
          I.discardPreview[wid] = { evidence, by, role, reason, request_id: UI.uuid() };
          I.busy = false;
          const live = document.querySelector(`[data-approval-panel="${CSS.escape(wid)}"] [data-discard-preview]`) || result;
          live.innerHTML = discardPreviewHtml(I.discardPreview[wid]);
          wireConfirm(live);
        } catch (e) { result.textContent = e.message; }
        finally { I.busy = false; button.disabled = false; }
      });
    });
  }

  /* ------------------------------------------------ hooks */
  window.hydInstancesSelect = id => pick(id, null);
  // 주소 #/instances/<처리 건>/task/<단계> 는 셸(shell.js)만 읽는다 — 셸이 이 함수로 처리 건을 고르고, 그 단계가 화면에 오면 단계 상세가 연다
  function openTask(id, taskId) {
    if (taskId) { I.tab = 'flow'; if (window.hydTaskDetail) hydTaskDetail.T.pending = { pid: id, wid: taskId }; }
    pick(id, taskId || null);
  }
  hydTabs.onShow(name => { if (name === 'instances') load(true); });
  wireStepButtons($('#instDetail'));
  $('#instReload').addEventListener('click', () => load(true));
  $('#instStatus').addEventListener('change', e => { I.status = e.target.value || null; I.sel = null; I.listShown = UI.PAGE; load(true); });
  setInterval(() => load(false), 2000);
  setInterval(updateApprovalClock, 1000);
  // 셸이 주소에 적는 지금 화면: 처리 건 + 열어 둔 단계(단계 상세가 열려 있으면 그 단계, 아니면 「내가 할 일」에서 고른 단계)
  const route = () => ({ inst: I.sel || null, task: (window.hydTaskDetail && hydTaskDetail.T.wid) || I.taskSel || null });
  window.hydInstances = { I, load, openTask, route, counts };
})();
