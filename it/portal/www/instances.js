/* 처리 건 — 목록 + 한 건(한 장). loaded after hitl.js · instanceSteps.js · flow.js · caseRecord.js · resultReport.js.
   사건 한 건의 경과 · AI 판단 · 내 승인 · 실행 · 결과를 이 화면 한 곳에서 본다(디자인 기준 5-1 · 5-2 · 5-4, 견본 sample_instances).
   process 서비스를 읽는다(주소는 layers.js API — 같은 출처):
     GET  /api/process/mode · /api/process/definitions/{id} · /api/instances · /api/instances/{id}(+/graph) · /api/graph-projections · /api/todolist… · /api/decisions/{id}
     POST /api/todolist/{id}/select · reject-card · decision-preview (조치 카드) · approve (일반 승인) · submit (폼) · human-response (질문 답) · 승인 전달 재전달 · 폐기 · 단계 닫기 · 실행 취소
   상태 의미는 ProcessGPT 와 같다: TODO 예정 → IN_PROGRESS 진행 중(내가 할 일) → SUBMITTED 제출됨(엔진 차례) → DONE · CANCELLED · PENDING.
   화면(위에서 아래로): 제목 · 묶음 단추(전체 · 내 할 일 · 진행 중 · 끝남 — 같은 목록을 거른다) → 왼쪽 목록(.rows) | 오른쪽 한 건:
     머리(이름 · 상태 뱃지 하나 · 보조 줄 · 더 보기) → 내가 할 일(.turn — 있을 때만, 제품색 면은 이 판 하나) 또는 결과 한 장(끝난 건) → 진행 길(flow.js — bpmn-js) →
     단계 기록(caseRecord.js — 하나뿐인 기록) → 「자세한 기록」 접기(단계 표 원문 · 처리 건 값 · 복구 · 지식 지도 반영 · 실시간 활동 · 실행 중인 AI 에이전트).
   복구용 기능(단계 닫기 · 실행 취소 · 승인 재전달과 폐기 · 다시 수행 · 이전 조치의 영향 · 다시 평가)은 평소에는 「자세한 기록」의 「다시 수행 · 복구」에 있고,
   멈춘 단계가 있을 때(서버 attention)만 그 단계 아래로 올라온다. 쓰는 사람은 늘 담당자 한 명이고 모든 역할을 맡는다(inbox.js 머리말). */
(function () {
  const I = { defNames: {}, defTimers: {}, defAgents: {}, timers: [], role: '', mode: null, taskSel: null, taskView: null, fieldValues: {}, fieldTask: null, instances: [], all: [], sel: null, view: null, todo: [], dec: null, decId: null, asked: [],
              form: { option: null, role: null, by: '', reason: '', fan: null, load: null, mode: null }, msg: '', busy: false, sig: null, listSig: null, filter: 'all', more: 'log', closing: null, listShown: 20, eventsShown: 20,
              retryForm: {}, discardPreview: {}, gone: null,
              pmsg: {} };   // 복구 패널(단계 닫기 'close' · 승인 재전달 · 폐기 · 정비 요청 재전달 = 그 작업 id)마다 따로 두는 오류 글 — 「내가 할 일」의 I.msg 와 섞이지 않는다(W1-24)
  const who = id => UI.roleName(id, I.view?.definition);
  // 복구 패널(다시 수행 · 실행 효과 · 보류 · 재전달 · 단계 닫기)의 담당자 기본값: 이 PC의 담당자 — 못 읽었으면 빈 칸(지어낸 기본 이름을 넣지 않는다)
  const actor = () => window.hydInbox?.me?.()?.id || '';
  // 사람이 처리할 단계인가. 맡은 쪽이 AI 에이전트(agent:…)나 시스템(sys:…)인 작업 행은 워커가 아직 가져가기 전(agent_orch 가 비어 있는 순간)에도 사람 단계가 아니다 —
  // 그 순간 목록 줄이 「승인 대기」 뱃지와 사람 아이콘을 달았다(독립 검토 가-4)
  const isHuman = t => UI.doerOf(t) === 'human' && !/^(agent:|sys:)/.test(String(t.user_id || ''));
  const josa = (word, pair) => window.hydWords ? hydWords.josa(word, pair) : '';
  const WINDOW = 50;                                   // 목록 한 번에 읽는 건수
  // 사건이 아닌 시스템 작업(질문 · 문서 추출 흐름) — 목록에서 사건과 가르는 표시. 서버가 준 흐름 정의 id 로만 가른다
  const SYSTEM_DEFS = new Set(['ask_agent', 'manual_extraction', 'manual_source_extraction', 'golden_questions', 'timeseries_question', 'business_question', 'rule_question']);
  const isSystemJob = x => SYSTEM_DEFS.has(String(x.proc_def_id || '').split('.')[0]);
  // 끝난 처리 건의 결과(정상 · 미달 · 반려 · 지연 · 입고 완료)를 상태 낱말 하나로 — 미달(ESCALATED) 종결도 「완료」로만 보이지 않게
  function outcomeOf(inst) {
    if (!inst || inst.status === 'RUNNING') return null;
    const rep = inst.status === 'COMPLETED' && window.hydResultReport ? hydResultReport.fromValues(UI.valuesOf(inst)) : null;
    if (!rep || !rep.verdict) return { label: UI.status(inst.status), tone: 'neutral' };
    return { label: rep.label || (rep.verdict === 'ok' ? '정상' : rep.verdict === 'fail' ? '미달' : rep.verdict === 'rejected' ? '반려' : UI.status(inst.status)),
             tone: rep.verdict === 'ok' ? 'success' : rep.verdict === 'fail' ? 'danger' : 'neutral', verdict: rep.verdict };      // 반려는 실패가 아니라 사람이 내린 결정이다 — 무채색
  }
  // 이 처리 건에서 내가 할 일(질문 답 먼저, 그다음 승인 · 입력)
  const mineOf = pid => I.asked.find(t => t.proc_inst_id === pid) || I.todo.find(t => t.proc_inst_id === pid) || null;
  const isApprovalTool = tool => ['formHandler:select_card', 'formHandler:approve'].includes(tool);
  // 내가 할 일이 있는 처리 건의 상태 이름은 하나다 — 「내 차례」(질문 · 승인 · 입력을 「승인 대기」 · 「질문」으로 갈라 부르지 않는다. 무엇을 할 차례인지는 그 건의 「내가 할 일」 판이 말한다)
  const turnWord = () => '내 차례';
  /* 처리 건 한 건의 상태 이름과 색 — 정본은 여기 하나다(window.hydInstances.stateOf). 다른 화면이 같은 사건의 상태를 보일 때 이 함수를 쓴다(다른 이름 · 다른 색의 사본을 만들지 않는다).
     x: 처리 건 행(GET /api/instances 의 한 줄 또는 GET /api/instances/{id} 의 instance — status · attention · variables_data · current_activity_ids · proc_def_id · proc_def_version)
     돌려주는 값: { label, tone } — tone 은 UI.chipText 의 것(danger 멈춤 · 미달 / warning 내 차례 / accent 진행 중 / success 정상 / neutral 반려 · 그 밖). 그리기: UI.chipText(s.label, s.tone)
     차례: 멈춤 > 내 차례(질문 · 승인 대기 · 내 차례) > 진행 중(지금 단계가 AI 면 「AI 판단 중」) > 끝난 결과(결과 보고의 낱말 — 정상 · 미달 · 반려 …) */
  function stateOf(x) {
    if (x.attention) return { label: String(x.attention.label || '멈춤').split(' — ')[0], tone: 'danger' };
    const t = x.status === 'RUNNING' ? mineOf(x.proc_inst_id) : null;
    if (t) return { label: turnWord(t), tone: 'warning' };
    if (x.status === 'RUNNING') return { label: aiNow(x) ? 'AI 판단 중' : UI.status(x.status), tone: 'accent' };
    const o = outcomeOf(x);
    return { label: o.label, tone: o.tone };
  }
  const stateChip = x => { const s = stateOf(x); return UI.chipText(s.label, s.tone); };
  // 목록 줄의 아이콘: 멈춤 > 내 차례(질문 · 승인 · 입력) > 진행 중 > 끝난 결과. 사건이 아닌 시스템 작업은 문서 아이콘
  function rowIcon(x, task) {
    if (x.attention) return 'triangle-alert';
    const t = task || (x.status === 'RUNNING' ? mineOf(x.proc_inst_id) : null);
    if (t) return t.draft_status === 'HUMAN_ASKED' ? 'message-circle-question' : 'user-check';
    if (x.status === 'RUNNING') return isSystemJob(x) ? 'file-text' : aiNow(x) ? 'bot' : 'cog';
    const o = outcomeOf(x);
    return isSystemJob(x) ? 'file-text' : o.tone === 'danger' || o.verdict === 'rejected' || x.status === 'CANCELLED' ? 'circle-x' : 'circle-check';
  }
  // 끝난 건의 보조 줄: 「처리 완료」(결과는 같은 줄의 뱃지가 말한다). 결과 보고가 없는 건만 끝 이벤트의 이름을 덧붙인다 — 「끝」 같은 뜻 없는 이름은 적지 않는다
  function endText(x) {
    const o = outcomeOf(x); if (!o) return '';
    const end = String(x.end_label || '').trim();
    const word = !o.verdict && !UI.plainEnd(end) && end !== o.label ? end : o.label;      // 결과 보고가 없는 건만 끝 이벤트의 이름으로 말한다
    return word === o.label ? '처리 완료' : `처리 완료 · ${word}`;
  }
  // 지금 단계가 AI 에이전트의 단계인가(그 흐름 정의에서 읽은 것 — 이름으로 짐작하지 않는다)
  const aiNow = x => { const ag = I.defAgents[`${x.proc_def_id}@${x.proc_def_version}`]; return !!ag && (x.current_activity_ids || []).some(id => ag.has(String(id).replace(/^task:/, ''))); };
  const typingIn = node => { const a = document.activeElement; return !!a && !!node && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName) && node.contains(a); };
  const moreOpen = () => !!document.getElementById('caseMore')?.open;

  /* ------------------------------------------------ load */
  async function load(force) {
    if (state.tab !== 'instances') return;
    // 읽는 중에 다시 읽기를 부르면 그 다음 읽기가 끝날 때 끝나는 약속을 돌려준다(누른 쪽이 새 화면을 기다릴 수 있게)
    if (I.loading) { I.reload = I.reload || force; return I.reloadDone || (I.reloadDone = new Promise(r => { I.reloadResolve = r; })); }
    I.loading = true;
    if (!I.loaded) { renderList(); renderDetail(); }      // 처음 읽는 동안: 빈 화면이 아니라 목록과 한 건의 뼈대(스켈레톤)
    const prevTask = I.taskView ? I.taskView.id : null;
    let loadErr = '';
    try {
    if (window.hydToolNames) await hydToolNames.load();
    try { I.mode = await getJ(API.process + '/api/process/mode'); } catch (e) { I.mode = { error: e.message }; }
    if (!I.mode || I.mode.error) { I.loaded = true; renderBanner(); renderTabs(); renderList(); renderDetail(); return; }
    // 목록: 최근 50건은 늘 읽는다(「전체」 탭과 탭의 건수). 「진행 중」 · 「끝남」 탭은 서버가 상태로 걸러 준 목록을 따로 읽는다 —
    // A083: 서버가 거르지 않으면 최근 50건보다 오래된 진행 중인 건을 포털에서 열 수 없다
    const list = (status) => getJ(API.process + `/api/instances?limit=${WINDOW}` + (status ? '&status=' + encodeURIComponent(status) : '')).then(rows => requireList(rows, '처리 건 목록'));
    try {
      I.all = await list('');
      I.filtered = I.filter === 'running' ? await list('RUNNING')
        : I.filter === 'done' ? (await Promise.all([list('COMPLETED'), list('CANCELLED')])).flat().sort((a, b) => String(b.start_date || '').localeCompare(String(a.start_date || ''))) : null;
      I.listError = '';
    } catch (e) { I.all = []; I.filtered = null; I.listError = e.message; }
    I.instances = I.filtered || I.all;
    // A157: list rows name each row's step from that row's own definition (it showed raw ids like extract-manual when another
    // definition's instance was selected). Each definition version is fetched once; a failed fetch is reported, not hidden.
    // 활동과 이벤트 이름 — 끝 이벤트 이름도 실어 목록이 E_end 같은 id 를 보이지 않게
    const defKey = x => `${x.proc_def_id}@${x.proc_def_version}`;
    await Promise.all([...new Set(I.instances.concat(I.all).filter(x => !(defKey(x) in I.defNames)).map(defKey))].map(async k => {
      const [id, version] = k.split('@');
      try {
        const d = await getJ(API.process + `/api/process/definitions/${encodeURIComponent(id)}?version=${encodeURIComponent(version)}`);
        I.defNames[k] = Object.fromEntries([...(d.activities || []), ...(d.events || [])].filter(a => a.name).map(a => [a.id, a.name]));
        // 기한 타이머(경계 이벤트) → 그 타이머가 붙은 단계. 「내 할 일」 줄의 기한을 이 표로 찾는다(timerFor 와 같은 규칙)
        const eps = Object.fromEntries((d.roles || []).map(r => [r.name, r.endpoint]));
        I.defAgents[k] = new Set((d.activities || []).filter(a => { const ep = a.agent || eps[a.role] || ''; return ep === 'sys:agent' || /^agent:/.test(ep) || a.orchestration === 'cliagents'; }).map(a => a.id));
        I.defTimers[k] = Object.fromEntries([...(d.events || []).filter(e => e.attachedTo).map(e => [e.id, e.attachedTo]), ...(d.activities || []).flatMap(a => (a.attachedEvents || []).map(e => [e, a.id]))]);
      }
      catch (e) { loadErr = `흐름 정의 ${id} ${version}을(를) 읽지 못했습니다: ${e.message}`; }
    }));
    // 담당 작업 목록을 못 읽으면 「지금 할 일이 없습니다」가 아니다 — 사유를 I.todoError 에 두고 지난 목록은 그대로 보인다
    let todoRows = [], todoError = '';
    try { todoRows = requireList(await getJ(API.process + '/api/todolist?status=IN_PROGRESS'), '담당 작업 목록'); } catch (e) { todoError = e.message; }
    // 처음 열면: 내가 할 일이 있는 건이 먼저 보인다. 없으면 목록의 첫 건
    if (!I.sel) {
      const first = todoError ? null : todoRows.find(t => t.draft_status === 'HUMAN_ASKED') || todoRows.find(isHuman);
      if (first) { I.sel = first.proc_inst_id; I.taskSel = first.id; }
      else if (I.instances[0]) I.sel = I.instances[0].proc_inst_id;
    }
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
    // 지식 지도 반영(그래프 질의 · 반영 대기)은 「자세한 기록」의 그 보기를 열어 둔 때만 읽는다(2초마다 Neo4j 질의를 하지 않게, W1-20)
    if (I.more === 'graph' && moreOpen() && I.sel) {
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
    // 거절된 뒤 단계가 사라졌으면(이미 처리됨) 그 사실만 카드 자리에 남긴다(I.gone).
    const nextTask = I.taskView ? I.taskView.id : null;
    if (nextTask !== prevTask) I.msg = '';
    if (nextTask) I.gone = null;
    if (loadErr) I.msg = loadErr;
    const selectTask = I.taskView && I.taskView.tool === 'formHandler:select_card' ? I.taskView : null;
    let decId = null, decIdError = '';
    if (selectTask) { try { decId = await decisionIdOf(selectTask); } catch (e) { decIdError = '이 단계의 조치 후보 묶음을 찾지 못했습니다: ' + e.message; } }
    if (decId !== I.decId) { I.decId = decId; I.dec = null; I.form = { option: null, role: null, by: I.form.by, reason: '', fan: null, load: null, mode: null }; }
    // 조치 후보를 못 읽으면 「불러오는 중」으로 남지 않는다 — 사유를 I.decError 에 둔다(다음 다시 읽기에서 또 시도)
    if (I.decId && !I.dec) { try { I.dec = await getJ(API.process + '/api/decisions/' + encodeURIComponent(I.decId)); I.decError = ''; } catch (e) { I.dec = null; I.decError = e.message; } }
    else if (!I.decId) I.decError = decIdError;
    I.loaded = true;
    // 변경 서명은 화면에 쓰는 값만 담는다. 목록(탭 · 목록)과 고른 처리 건(내가 할 일 · 한 건)을 나눠, 다른 처리 건만 바뀌면 목록만 다시 그린다 —
    // 지금 쓰고 있는 폼은 그대로 둔다(결함: 15초마다 · 다른 처리 건 이벤트마다 폼이 지워짐).
    const row = x => [x.proc_inst_id, x.status, x.current_activity_ids, x.proc_inst_name, x.attention, x.end_label];
    const listSig = JSON.stringify([I.filter, I.listShown, I.instances.map(row), I.all.map(x => [x.proc_inst_id, x.status]), I.todo.map(t => [t.id, t.proc_inst_id, t.status, t.user_id, dueOf(t)]),
      I.asked.map(t => [t.id, t.draft_status]), I.sel, I.taskSel, I.todoError, I.listError, I.role, UI.namesVersion]);
    const sig = JSON.stringify([I.sel, I.taskSel, I.taskView, I.asked.filter(t => t.proc_inst_id === I.sel).map(t => [t.id, t.draft_status]),
      I.view && I.view.workitems.map(w => [w.id, w.status, w.draft_status, w.log]),
      I.view && (I.view.approvals || []).map(a => [a.todo_id, a.status, a.attempts, a.error]), I.view && I.view.attention, I.dec && I.dec.state, I.decError, I.taskViewError, I.msg, I.pmsg, I.gone,
      I.view && [I.view.events.length, I.view.events.at(-1)?.id], I.view && I.view.instance.variables_data, I.view && [I.view.instance.status, I.view.instance.end_label],   // 이벤트는 개수 · 마지막 id 만(1500줄 전체를 2초마다 문자열로 만들지 않는다)
      I.viewErr, I.graph && (I.graph.error || I.graph.graph || 'none'), I.graph && I.graph.projection, caseSig(I.caseProjection), I.more, moreOpen(), I.eventsShown, UI.namesVersion]);
    feedRecord();                                  // 단계 기록은 2초 다시 읽기를 그때그때 받는다(이벤트 · 상태) — 스스로 바뀐 줄만 고친다
    updateKnowledgeChecked();                      // 지식 대조 시각(15초마다 바뀜)은 그 줄만 고친다
    if (!force && sig === I.sig && listSig === I.listSig) return;
    const detail = force || sig !== I.sig;
    I.sig = sig; I.listSig = listSig;
    // 글을 쓰는 중인 자리(「내가 할 일」 카드 · 복구 폼 · 단계 아래의 사유 칸)는 다시 그리지 않는다 — 칸을 통째로 바꾸면 한글 조합이 끊긴다(W1-21).
    // 건너뛴 자리가 있으면 서명을 비워 두어 칸을 떠난 뒤 다음 읽기(2초)에서 그린다
    let held = false;
    keepFocus(() => { renderBanner(); renderTabs(); renderList(); if (detail) held = renderDetail(); });
    if (held) I.sig = null;
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

  /* ------------------------------------------------ 탭(전체 · 내 할 일 · 진행 중 · 끝남) · 연결 실패 */
  // H-10: 진행 중(RUNNING)이어도 사람의 조치를 기다리며 멈춘 처리 건(서버 attention)은 「진행 중」에 세지 않고 따로 센다
  function counts(instances) {
    return { running: instances.filter(x => x.status === 'RUNNING' && !x.attention).length,
             stuck: instances.filter(x => x.status === 'RUNNING' && x.attention) };
  }
  function renderBanner() {
    const b = $('#instBanner');
    if (!I.mode || I.mode.error) {
      b.innerHTML = I.mode ? UI.errorBlock(UI.t('inst.noConn'), (I.mode || {}).error || '', { retry: true }) : '';
      b.querySelector('[data-retry]')?.addEventListener('click', () => load(true));
      return;
    }
    b.innerHTML = '';
  }
  const mineIds = () => new Set(I.asked.concat(I.todo).map(t => t.proc_inst_id));
  function renderTabs() {
    const box = $('#instTabs');
    // 건수: 고른 탭은 지금 읽은 목록, 다른 탭은 최근 50건 안에서 센 값(50건이 다 찼으면 「+」를 붙여 더 있을 수 있음을 밝힌다)
    const full = I.all.length >= WINDOW, plus = n => `${n}${full ? '+' : ''}`;
    const n = {
      all: plus(I.all.length), mine: I.todoError ? '' : String(mineIds().size),
      running: I.filter === 'running' && I.filtered ? `${I.filtered.length}${I.filtered.length >= WINDOW ? '+' : ''}` : plus(I.all.filter(x => x.status === 'RUNNING').length),
      done: I.filter === 'done' && I.filtered ? `${I.filtered.length}${I.filtered.length >= WINDOW ? '+' : ''}` : plus(I.all.filter(x => x.status !== 'RUNNING').length),
    };
    const tab = (k, label) => `<button type="button" data-inst-filter="${k}" aria-pressed="${I.filter === k}">${esc(label)}${n[k] !== '' && I.loaded && !I.listError ? `<span class="num">${esc(n[k])}</span>` : ''}</button>`;
    const html = tab('all', '전체') + tab('mine', '내 할 일') + tab('running', '진행 중') + tab('done', '처리 완료');
    if (box._html !== html) { box.innerHTML = html; box._html = html; }
  }
  // 그 단계에 붙은 기한 타이머 가운데 가장 이른 기한(없으면 null) — 타이머도 진행 중 작업 행으로 같은 목록에 온다
  function dueOf(t) {
    const inst = I.instances.find(x => x.proc_inst_id === t.proc_inst_id);
    const attached = inst ? I.defTimers[`${inst.proc_def_id}@${inst.proc_def_version}`] || {} : {};
    const dues = I.timers.filter(r => r.proc_inst_id === t.proc_inst_id && attached[r.activity_id] === t.activity_id).map(r => r.due_date).sort();
    return dues[0] || null;
  }
  // 역할별 보기(「내 할 일」 탭에서만): 전체 + 지금 열린 일이 있는 역할. 쓰는 사람은 한 명이고 모든 역할을 맡는다 — 보기만 가른다
  function renderRoles() {
    const box = $('#todoRoles'), count = {};
    I.todo.forEach(t => { count[t.user_id] = (count[t.user_id] || 0) + 1; });
    const ids = Object.keys(count).sort((a, b) => who(a).localeCompare(who(b)));
    if (I.role && !ids.includes(I.role)) ids.push(I.role);
    if (I.filter !== 'mine' || (ids.length < 2 && !I.role)) { box.innerHTML = ''; return; }
    const seg = (id, label, n) => `<button type="button" data-todo-role="${esc(id)}" aria-pressed="${I.role === id}">${esc(label)}<span class="num">${n}</span></button>`;
    box.innerHTML = `<div class="seg" role="group" aria-label="역할별 보기">${seg('', '전체', I.todo.length)}${ids.map(id => seg(id, who(id), count[id] || 0)).join('')}</div>`;
    box.querySelectorAll('[data-todo-role]').forEach(b => b.addEventListener('click', () => { I.role = b.dataset.todoRole; I.listShown = UI.PAGE; renderRoles(); renderList(); }));
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

  /* ------------------------------------------------ 목록: 한 줄 = 무슨 사건인지(이름 · 설비) · 지금 상태 칩 하나 · 둘째 줄(시작 시각 · 지금 단계) */
  // 같은 날의 건은 날짜 묶음 머리(오늘 · 어제 · 11월 13일) 아래에 모이고, 줄에는 시각만 적는다(같은 이름이 열 줄 이어져도 날짜와 시각으로 가려진다)
  const dayKey = t => { const d = new Date(t); return isNaN(d) ? '' : `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`; };
  function dayLabel(t) {
    const d = new Date(t); if (isNaN(d)) return '날짜 기록 없음';
    const now = new Date(), y = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1);
    return dayKey(d) === dayKey(now) ? '오늘' : dayKey(d) === dayKey(y) ? '어제' : `${d.getMonth() + 1}월 ${d.getDate()}일`;
  }
  const clock = t => new Date(t).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hour12: false });
  function rowHtml(x, task, short) {
    const names = I.defNames[`${x.proc_def_id}@${x.proc_def_version}`] || {};
    const step = task ? UI.flowName(task.activity_name)
      : x.attention ? (x.attention.steps || []).map(s => UI.flowName(typeof s === 'string' ? s : s.name)).join(' · ')
      : x.status === 'RUNNING' ? (x.current_activity_ids || []).map(id => UI.flowName(names[id] || id.replace(/^task:|^ev:/, ''))).join(' · ') : '';
    const due = task ? dueOf(task) : null;
    const bits = [isSystemJob(x) ? '시스템 작업' : '', x.start_date ? `${short ? clock(x.start_date) : UI.dateTime(x.start_date)} 시작` : '',
      step ? `${step} 단계` : x.status !== 'RUNNING' ? endText(x) : '', task ? who(task.user_id) : '', due ? `기한 ${UI.dateTime(due)}` : ''].filter(Boolean);
    const chip = task ? UI.chipText(turnWord(task), 'warning') : stateChip(x);
    return `<span class="row-ic">${UI.icon(rowIcon(x, task))}</span><span class="row-title">${esc(x.proc_inst_name || '이름 없는 처리 건')}</span>${chip}<span class="row-meta">${esc(bits.join(' · '))}</span>`;
  }
  function renderList() {
    const box = $('#instList');
    renderRoles();
    if (!I.loaded) { box.innerHTML = '<div class="sk-row"><div class="skeleton sk-line" style="width:60%"></div><div class="skeleton sk-line" style="width:85%"></div></div>'.repeat(3); return; }
    if (I.mode && I.mode.error) { box.innerHTML = ''; return; }
    if (I.listError) { box.innerHTML = UI.errorBlock('처리 건 목록을 읽지 못했습니다', I.listError, { retry: true, cls: 'compact' }); box.querySelector('[data-retry]')?.addEventListener('click', () => load(true)); return; }
    box.innerHTML = '';
    const add = (on, job, html, onPick, data = {}) => {
      const it = document.createElement('button');
      it.type = 'button'; it.className = 'row'; it.innerHTML = html;
      if (on) it.setAttribute('aria-current', 'true');
      if (job) it.dataset.job = '';
      Object.assign(it.dataset, data);
      it.addEventListener('click', onPick);
      box.appendChild(it);
    };
    const more = (rest) => { if (!rest) return; const m = el('div', 'rows-more', UI.moreButton(rest)); m.querySelector('button').addEventListener('click', () => { I.listShown += UI.PAGE; renderList(); }); box.appendChild(m); };
    if (I.filter === 'mine') {
      // 「내 할 일」: 한 줄 = 사람이 처리할 단계 하나(에이전트의 질문 먼저). 그 단계의 처리 건을 열고 그 단계를 고른다
      if (I.todoError) {
        box.innerHTML = UI.errorBlock('내가 할 일을 읽지 못했습니다', I.todoError + (I.todo.length || I.asked.length ? ' — 아래는 마지막으로 읽은 목록입니다' : ''), { retry: true, cls: 'compact' });
        box.querySelector('[data-retry]')?.addEventListener('click', () => load(true));
      }
      const tasks = (I.role ? [] : I.asked).concat(I.role ? I.todo.filter(t => t.user_id === I.role) : I.todo.filter(t => !I.asked.some(a => a.id === t.id)));
      if (!tasks.length) { if (!I.todoError) box.insertAdjacentHTML('beforeend', I.role ? UI.empty(`${who(I.role)} 역할로 처리할 단계가 없습니다`, '다른 역할의 일은 「전체」에서 볼 수 있습니다', 'compact') : UI.empty(UI.t('inst.noTodo'), UI.t('inst.noTodoSub'), 'compact')); return; }
      const paged = UI.page(tasks, I.listShown, t => t.proc_inst_id === I.sel && (!I.taskSel || t.id === I.taskSel));
      paged.rows.forEach(t => {
        const x = I.all.concat(I.instances).find(r => r.proc_inst_id === t.proc_inst_id) || { proc_inst_id: t.proc_inst_id, proc_inst_name: t.proc_inst_name, status: 'RUNNING' };
        add(t.proc_inst_id === I.sel && (!I.taskView || I.taskView.id === t.id || t.draft_status === 'HUMAN_ASKED'), false, rowHtml(x, t), () => pick(t.proc_inst_id, t.id), { inst: t.proc_inst_id, todoTask: t.id });
      });
      more(paged.rest);
      return;
    }
    const rows = I.instances;
    if (!rows.length) {
      box.innerHTML = I.filter === 'all' ? UI.emptyGo(UI.t('inst.empty'), UI.t('inst.emptySub'), 'scenario', UI.t('nav.scenario') + ' 열기', 'compact')
        : UI.empty(I.filter === 'running' ? '진행 중인 처리 건이 없습니다' : '처리 완료된 건이 없습니다', '「전체」 탭에서 모든 처리 건을 볼 수 있습니다', 'compact');
      return;
    }
    // 내가 할 일이 있는 건을 위로(그 안에서는 서버가 준 차례 — 최근 것부터)
    const mine = mineIds();
    const ordered = rows.filter(x => mine.has(x.proc_inst_id) && x.status === 'RUNNING').concat(rows.filter(x => !(mine.has(x.proc_inst_id) && x.status === 'RUNNING')));
    const paged = UI.page(ordered, I.listShown, x => x.proc_inst_id === I.sel);
    setTimeout(() => { const cur = box.querySelector('.row[aria-current="true"]'); if (cur && box.scrollHeight > box.clientHeight && (cur.offsetTop < box.scrollTop || cur.offsetTop + cur.offsetHeight > box.scrollTop + box.clientHeight)) box.scrollTop = Math.max(0, cur.offsetTop - 8); }, 0);      // 목록이 잘리는 폭에서도 고른 줄이 보이게
    let group = null;
    paged.rows.forEach(x => {
      const g = mine.has(x.proc_inst_id) && x.status === 'RUNNING' ? '내가 할 일' : dayLabel(x.start_date);
      if (g !== group) { group = g; box.appendChild(el('div', 'rows-group', esc(g))); }
      add(x.proc_inst_id === I.sel, isSystemJob(x), rowHtml(x, null, g !== '내가 할 일'),
        () => pick(x.proc_inst_id, x.proc_inst_id === I.sel ? I.taskSel : null), { inst: x.proc_inst_id });
    });   // 같은 이름의 처리 건(같은 설비 · 같은 흐름)을 처리 건 id로 구별한다
    more(paged.rest);
  }

  /* ------------------------------------------------ 내가 할 일 판 (디자인 기준 5-1 2번, 키트 .turn): 물음 한 문장 · 까닭 한 문장 · 판단에 쓸 숫자 넷 · 단추 줄.
     제품색 면은 이 판 하나뿐이다. 다른 안과 그 손익 · 점수 근거는 [다른 안 고르기]를 눌렀을 때만 판 안에 펼친다. 사유 칸은 반려할 때와 다른 안을 고를 때만 나온다. */
  function handoverInputs(values) {
    const names = {asset:'설비',as_of:'인계 기준시각',shift_label:'교대',work_notes:'작업 메모',handover_summary:'인계안 요약',sender_notes:'인계자 확인 사항',receiver_notes:'인수자 보완 요청'};
    const areas = {equipment:'설비 관측',work_orders:'정비 작업지시',parts:'부품·재고',work_notes:'작업 메모 대조'};
    const states = {observed:'조회 확인',needs_check:'확인 필요',conflict:'기록 불일치'};
    const rows = Object.entries(values || {}).filter(([k, v]) => !['checks','evidence'].includes(k) && v != null && v !== '').map(([k,v]) => UI.readonly(names[k] || k,esc(typeof v==='string' ? v : JSON.stringify(v)))).join('');
    const checks = (Array.isArray(values?.checks) ? values.checks : []).map(c => `<section class="turn-check"><h4>${esc(areas[c.area] || c.area)} · ${esc(states[c.state] || c.state)}</h4><p>${esc(c.finding || '')}</p><p><b>다음 근무자가 확인할 일</b> ${esc(c.next_action || '')}</p><p class="muted">조회 근거 ${(c.evidence_indices || []).map(i=>esc(String(i+1))).join(', ') || '없음 · 확인 필요'}</p></section>`).join('');
    const evidence = (Array.isArray(values?.evidence) ? values.evidence : []).map((e,i) => UI.raw(e, { title: `조회 근거 ${i+1} · ${UI.toolName(e.tool) || e.tool || '도구 기록 없음'}` })).join('');
    return `${rows}${checks}${evidence}`;
  }
  // 판의 틀(키트 .turn): 머리(아이콘 칸 · 「내가 할 일 · 승인」 · 기한 · 물음 한 문장 · 까닭) → 판단에 쓸 숫자(최대 넷) → (펼친 것) → 단추 줄(오른쪽 끝에 어느 역할로 기록되는지) → 까닭 한 줄
  // facts: [[이름, 값, 단위]] · late: 기한 줄(clockLine) · who: 「운전원 역할로 기록됩니다」
  // msg: 막힌 까닭 · 서버가 거절한 까닭(빨간 글) · note: 알아 둘 것(보통 글)
  // 앞 AI 단계가 남긴 알림 가운데 「결과 글」에 대한 것(재생한 결과 글의 조회 값이 준비 당시 값이라는 것 · 지금 값과 다른 곳): 그 글을 읽고 결정하는 자리에도 같은 말을 보인다.
  // 가장 최근에 끝난 AI 단계의 것만 본다(단계 기록의 그 단계 결론 아래에 같은 문장이 있다)
  function resultNotices() {
    const view = I.view; if (!view || !window.hydRecord) return [];
    const agentRows = (view.workitems || []).filter(w => (w.agent_orch === 'cliagents' || w.agent_mode) && w.end_date).sort((a, b) => String(b.end_date).localeCompare(String(a.end_date)));
    if (!agentRows.length) return [];
    return hydRecord.noticeTexts(hydRecord.rowsOf((view.events || []).filter(ev => ev.todo_id === agentRows[0].id))).filter(t => /^결과 글/.test(t));
  }
  function todoCard({ label, icon = 'user-check', title, desc = '', late = '', facts = [], acts = '', who = '', more = '', msg = '', note = '', attrs = '' }) {
    const told = resultNotices().map(t => `<p class="turn-notice">${UI.icon('info')}<span>${esc(t)}</span></p>`).join('');
    if (told) desc += told;
    return `<section class="turn" aria-label="내가 할 일" ${attrs}>
      <div class="turn-head"><span class="turn-badge">${UI.icon(icon, 'ic-lg')}</span><div><div class="turn-eyebrow">${esc(label)}${late}</div><h3>${esc(title)}</h3>${desc}</div></div>
      ${facts.length ? `<dl class="turn-facts">${facts.map(([k, x, u]) => `<div><dt>${esc(k)}</dt><dd class="num">${esc(x)}${u ? `<small>${esc(u)}</small>` : ''}</dd></div>`).join('')}</dl>` : ''}
      ${more ? `<div class="turn-more">${more}</div>` : ''}
      ${acts || who ? `<div class="turn-foot">${acts}${who ? `<span class="who">${who}</span>` : ''}</div>` : ''}
      ${note ? `<p class="turn-msg">${esc(note)}</p>` : ''}${msg ? `<p class="turn-msg" data-tone="danger" role="status">${esc(msg)}</p>` : ''}</section>`;
  }
  const roleLine = name => name ? `${esc(name)} 역할로 기록됩니다` : '';
  // 사유 칸: 반려(꼭 적는다)와 다른 안(적으면 기록에 남는다)일 때만
  const reasonField = (label, hint) => UI.field({ label, cls: 'turn-reason', hint, input: `<textarea id="tdReason" rows="2">${esc(I.form.reason || '')}</textarea>` });
  // 판단에 쓸 숫자(최대 넷): ① 고른 안의 예측이 고르는 근거이면 그 값의 지금 값(경보가 실어 온 관측)과 조치 뒤 예측 ② 판단이 쓴 사실 가운데 판단 엔진의 설명에 그 숫자가 나온 것 먼저.
  // 모두 서버가 준 값이다 — 없으면 그 칸을 그리지 않는다
  function turnFacts(d, chosen) {
    const W = window.hydWords, out = [];
    if (!W || !chosen) return out;
    const now = ((vars(I.view?.instance || {}).alert || {}).evidence || {}).values || {};
    const f = window.hydApprove.forecastDecides(chosen, d.options || []) ? (chosen.forecast || [])[0] : null;
    if (f) {
      const tag = String(f.variable || '').replace(/^sv:/, '');
      const cur = now[tag.toUpperCase()];
      if (cur != null && Number.isFinite(+cur)) out.push([`지금 ${W.fieldName(tag)}`, W.num(+cur), f.unit || W.unit(tag)]);
      out.push([`조치 뒤 예측 ${UI.idText(f.name)}`, W.num(+f.value), f.unit || '']);
    }
    const said = String(d.explanation || '');
    const facts = Object.entries({ ...(d.facts || {}), ...(chosen.facts || {}) }).filter(([k, x]) => typeof x === 'number' && Number.isFinite(x) && W.known(k));
    const named = facts.filter(([, x]) => new RegExp(`(^|[^0-9.])${String(x).replace('.', '\\.')}([^0-9.]|$)`).test(said));
    named.concat(facts.filter(x => !named.includes(x))).forEach(([k, x]) => { if (out.length < 4) out.push([W.fieldName(k), W.num(x), W.unit(k)]); });
    return out;
  }
  function setMode(mode) { I.form.mode = I.form.mode === mode ? null : mode; I.msg = ''; renderTodoPanel(); if (I.form.mode) $('#tdReason')?.focus({ preventScroll: true }); }

  function renderTodoPanel() {
    const box = $('#todoPanel'); if (!box) return;
    const asked = I.asked.find(t => t.proc_inst_id === I.sel);
    if (asked) { renderAskPanel(asked); return; }
    const task = I.taskView;
    if (!task && I.taskViewError) {
      box.innerHTML = UI.errorBlock('이 단계를 열지 못했습니다', I.taskViewError, { retry: true });
      box.querySelector('[data-retry]')?.addEventListener('click', () => load(true));
      return;
    }
    if (!task) {
      const g = I.gone && I.gone.inst === I.sel ? I.gone : null;
      box.innerHTML = g ? `<div class="alert" data-gone>${UI.icon('info')}<h2>${esc(g.title)}</h2><section>이 단계는 이미 처리됐거나 닫혀서 「내 할 일」에서 빠졌습니다. 결과는 아래 단계 기록에서 확인하세요.<br><span class="muted">서버 응답: ${esc(g.text)}</span></section></div>` : '';
      return;
    }
    if (task.tool === 'formHandler:select_card') { renderSelectPanel(task); return; }
    if (task.tool === 'formHandler:approve') { renderApprovePanel(task); return; }
    const fields = task.form && task.form.fields_json;
    if (!fields) { box.innerHTML = UI.errorBlock(UI.flowName(task.activity_name), UI.t('inst.noForm')); return; }
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
    const byMe = window.hydInbox?.byField('td', I.form);   // 제출 · 답은 이 PC의 담당자로만(서버 require_task_actor) — 못 읽었으면 안내만, 단추는 꺼 둔다
    const folds = new Map([...box.querySelectorAll('details')].map(d => [d.querySelector('summary')?.textContent, d.open]));
    box.innerHTML = todoCard({ label: `내가 할 일 · ${isEscalate ? '확인' : '입력'}`, icon: 'pencil', title,
      desc: why ? `<p>${esc(why)}</p>` : '', who: roleLine(who(task.user_id)),
      more: `${inputs.length ? UI.fold(esc(UI.t('inst.prevTask')) + '에서 받은 값', String(task.form?.contract || '').startsWith('shift-handover-') ? handoverInputs(task.inputs) : inputs.map(([k, v]) => UI.readonly(varLabel(k), prevValue(v))).join('')) : ''}
        ${byMe || pickMe()}${UI.section('', fields.map(control).join(''))}`,
      acts: `<button type="button" class="btn" id="tdDone" ${byMe && !I.busy ? '' : 'disabled'}>${UI.icon('check')}${esc(isEscalate ? UI.t('btn.confirm') : UI.t('btn.submit'))}</button>`,
      msg: I.msg });
    box.querySelectorAll('details').forEach(d => { const k = d.querySelector('summary')?.textContent; if (folds.has(k)) d.open = folds.get(k); });
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
  // 승인 단계의 기한 한 줄(1초마다 updateApprovalClock 이 문구를 고친다). 멈추는 타이머(cancelActivity 가 false 가 아님)면 기한이 지나면
  // 이 단계가 닫히고 다음 단계로 넘어가므로 그 단계 이름을 싣는다 — 멈추지 않는 타이머는 지연 알림만 보낸다
  function clockLine(task) {
    const timer = timerFor(task);
    if (!timer || !timer.due_date) return '';
    const def = I.view?.definition || {};
    const ev = (def.events || []).find(e => e.id === timer.activity_id) || {};
    if (ev.cancelActivity === false) return `<span class="late" data-approval-until="${esc(timer.due_date)}"></span>`;
    const nextId = ((def.sequences || []).find(s => s.source === ev.id) || {}).target;
    const next = nextId ? ([...(def.activities || []), ...(def.events || [])].find(a => a.id === nextId) || {}).name : '';
    return `<span class="late" data-approval-until="${esc(timer.due_date)}" data-approval-cut="${esc(next ? UI.flowName(next) : '')}"></span>`;
  }
  // 「이전 단계」가 넘긴 값: 이름은 화면 이름 사전(var.*)으로, 묶음 값은 항목별 한 줄로 읽는다. 더 깊은 값과 긴 글은 접어 둔다
  const varLabel = k => { const n = UI.t('var.' + k); return n === 'var.' + k ? String(k).replace(/_/g, ' ') : n; };
  function prevValue(v) {
    const scalar = x => x === null || x === undefined || x === '' ? '–' : typeof x === 'boolean' ? (x ? '예' : '아니요') : esc(UI.idText(String(x)));
    if (v === null || typeof v !== 'object') return scalar(v);
    const entries = Array.isArray(v) ? v.map((x, i) => [String(i + 1), x]) : Object.entries(v);
    if (!entries.length) return '–';
    const flat = entries.filter(([, x]) => x === null || typeof x !== 'object'), deep = entries.filter(([, x]) => x !== null && typeof x === 'object');
    const rows = flat.map(([k, x]) => `<div><span class="muted">${esc(Array.isArray(v) ? k : varLabel(k))}</span> ${scalar(x)}</div>`).join('');
    return rows + (deep.length ? UI.raw(Object.fromEntries(deep), { title: `세부 값 ${deep.length}개` }) : '');
  }
  // 담당자 정보를 아직 못 읽었으면(업무 DB 연결 문제) 사람 행동의 자리에 그 까닭을 보인다 — 모든 단계 패널이 이 한 줄을 쓴다
  const pickMe = () => `<div class="alert" data-variant="destructive" role="alert" data-pick-me>${UI.icon('circle-alert')}<h2>담당자 정보를 읽지 못해 지금은 처리할 수 없습니다</h2><section>화면을 새로 고친 뒤 다시 해 주세요.</section></div>`;

  function renderAskPanel(task) {
    const box = $('#todoPanel');
    const events = (I.view && I.view.events || []).filter(e => e.todo_id === task.id);
    const answered = new Set(events.filter(e => e.event_type === 'human_response').map(e => e.job_id));
    const open = events.filter(e => e.event_type === 'human_asked' && !answered.has(e.job_id)).slice(-1)[0];
    const stepName = UI.flowName(task.activity_name);
    if (!open) { box.innerHTML = todoCard({ label: `내가 할 일 · ${UI.t('inst.askTitle')}`, icon: 'message-circle-question', title: stepName, desc: `<p>${esc(UI.t('inst.askWait'))}</p>` }); return; }
    const d = open.data || {};
    const options = Array.isArray(d.options) ? d.options.filter(x => typeof x === 'string') : [];
    const byMe = window.hydInbox?.byField('td', I.form);
    box.innerHTML = todoCard({ label: `내가 할 일 · ${UI.t('inst.askTitle')}`, icon: 'message-circle-question', title: humanQuestionText(d),
      desc: `<p>AI 에이전트가 「${esc(stepName)}」 단계에서 묻습니다. 답하면 그 단계가 이어집니다.</p>`,
      more: `${options.length ? `<div class="chips">${options.map((o, i) => `<button class="btn" data-variant="outline" data-size="sm" type="button" data-human-option="${i}">${esc(o)}</button>`).join('')}</div>` : ''}
        ${UI.field({ label: UI.t('form.answer'), required: true, cls: 'turn-reason', hint: UI.t('form.hint.answer'), input: `<textarea id="tdAnswer" rows="2">${esc(I.form.reason)}</textarea>` })}${byMe || pickMe()}`,
      acts: `<button type="button" class="btn" id="tdAnswerGo" ${byMe && !I.busy ? '' : 'disabled'}>${UI.icon('send')}${esc(UI.t('btn.answer'))}</button>`,
      msg: I.msg });
    box.querySelectorAll('[data-human-option]').forEach(button => button.addEventListener('click', () => {
      I.form.reason = options[Number(button.dataset.humanOption)]; $('#tdAnswer').value = I.form.reason;
    }));
    $('#tdAnswer').addEventListener('input', e => I.form.reason = e.target.value);
    $('#tdAnswerGo').addEventListener('click', () => act(task, '질문', () => postJ(API.process + `/api/todolist/${encodeURIComponent(task.id)}/human-response`, { job_id: open.job_id, answer: I.form.reason, by: actor() }), () => { I.form.reason = ''; }));
  }

  /* 조치 카드 승인(formHandler:select_card) */
  function renderSelectPanel(task) {
    const box = $('#todoPanel');
    const focused = box.contains(document.activeElement) ? document.activeElement : null;
    const caret = focused && typeof focused.selectionStart === 'number' ? [focused.selectionStart, focused.selectionEnd] : null;
    const folds = new Map([...box.querySelectorAll('details')].map(el => [el.querySelector('summary')?.textContent, el.open]));
    const d = I.dec;
    if (!d && I.decError) {
      box.innerHTML = todoCard({ label: '내가 할 일 · 승인', title: UI.flowName(task.activity_name), more: UI.errorBlock('조치 후보를 읽지 못했습니다', I.decError, { retry: true }) });
      box.querySelector('[data-retry]')?.addEventListener('click', () => load(true));
      return;
    }
    if (!d) { box.innerHTML = todoCard({ label: '내가 할 일 · 승인', title: UI.flowName(task.activity_name), desc: `<p>${esc(UI.t('inst.loadingCards'))}</p>` }); return; }
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
    const canApprove = (reviewed ? reviewed.feasible : chosen.feasible && !changed) && !UI.executionBlocked(reviewed || chosen, review?.snapshot || d);
    // P5 (audit2): 조치 카드도 일반 승인처럼 이 PC의 담당자(그 승인 역할의 구성원)가 있어야 승인 · 반려한다. 어느 역할이 그 안을 승인할 수 있는지는
    // 서버가 판정해 판단의 각 안에 싣는다(options[].approvable_roles — decisions.approver_roles). 화면은 그 목록만 본다(역할 등급 규칙 사본 없음, W1-11 · W1-25)
    const roleTable = review?.snapshot?.roles || d.roles || {};
    const need = (reviewed || chosen).approver || null;
    const signs = (role, o) => { const opt = (d.options || []).find(x => x.id === o?.id) || o; return !opt?.approver?.id || (opt.approvable_roles || []).includes(role); };
    const meNow = window.hydInbox?.me?.() || null;
    const byMe = window.hydInbox?.byField('td', I.form);          // 담당자 id 를 폼 상태(form.by)에 싣는다
    // 승인 역할은 고른 안이 요구하는 역할로 늘 맞춘다(담당자는 모든 역할의 구성원이다). 그 역할이 없으면 승인할 수 있는 역할 가운데 하나
    if (meNow) { const want = need?.id; I.form.role = want && meNow.roles.includes(want) ? want : (meNow.roles.find(r => signs(r, reviewed || chosen)) || meNow.roles[0] || ''); }
    const needName = need?.id ? (roleTable[need.id]?.name || need.name || UI.who(need.id)) : '';
    const roleName = I.form.role ? (roleTable[I.form.role]?.name || UI.who(I.form.role)) : '';
    const meSigns = !!meNow && signs(I.form.role, reviewed || chosen);
    const meRejects = !!meNow && (!opts.length || opts.some(o => signs(I.form.role, o)));
    const roleHint = meNow && !meSigns ? `이 안은 ${needName} 역할이 승인하는데, 이 PC의 담당자가 그 역할에 들어 있지 않아 승인할 수 없습니다. 메뉴 「AI 에이전트」의 「${UI.t('nav.agents')}」 화면에서 담당 배정을 확인하세요.` : '';
    const timer = timerFor(task);
    const activity = (I.view?.definition?.activities || []).find(a => a.id === task.activity_id);
    const canReject = (activity?.outputData || []).includes('approval');
    const delayed = (I.view?.events || []).some(e => e.data?.report?.outcome === '승인 지연') || vars(I.view?.instance || {}).result_report?.outcome === '승인 지연';
    const maintenance = (chosen.actions || []).filter(a => a.code === 'WO_CREATE');
    const hasWorkOrder = (I.view?.definition?.activities || []).some(a => a.tool === 'enterprise:WO_CREATE');
    const maintenanceText = maintenance.length ? maintenance.map(a => a.value ?? a.name ?? UI.t('workOrder')).join(', ') : `선택한 조치 이후 정비 점검: ${chosen.name || ''}`;
    const sc = d.scenario || {};
    const inst = I.view?.instance || {};
    const P = window.hydApprove.pick(d, I.form.option);
    // 값 조정 · 미리 보기(설비에 보내는 값이 있는 안)와 사건 정보는 [다른 안 고르기]를 편 자리에 있다
    const adjust = fanA || loadA || pumpA || chosen.maintenancePlan || chosen.economicComparison ? UI.fold(fanA || loadA || pumpA ? '조치 값 조정 · 미리 보기' : '현재 조건 다시 확인 · 미리 보기', UI.section('', `${pumpA ? UI.readonly(UI.t('form.pump'), esc(pumpA.value)) : ''}${fanA ? hydCards.rangeField('tdFan', UI.t('form.fan'), fanA, I.form.fan) : ''}${loadA ? hydCards.rangeField('tdLoad', UI.t('form.load'), loadA, I.form.load) : ''}`) +
      `<div id="tdReviewed">${reviewed ? `<p><b>${esc(UI.t('card.reviewed'))}</b> · ${esc(UI.dateTime(review.created))}</p>${hydCards.optionDetail(reviewed, { decision: review.snapshot })}` : `<p class="muted">${esc(UI.t('form.hint.preview'))}</p>`}</div>` +
      UI.actions(`<button type="button" class="btn" data-variant="outline" data-size="sm" id="tdPreview" ${I.busy || !I.form.option ? 'disabled' : ''}>${esc(UI.t('btn.preview'))}</button>`), { open: !!changed || !!reviewed || !!I.form.needPreview }) : '';
    // 실행할 수 있는 안이 하나도 없으면 [승인]이 꺼진 이유와 다음 행동을 까닭 줄에 말한다
    const noneFeasible = !reviewed?.feasible && !opts.some(o => o.feasible);
    const hint = noneFeasible ? ''
      : !canApprove && changed ? '값을 바꿨으면 미리 보기로 다시 확인한 뒤 승인합니다' : !canApprove && P.blocked ? '이 안은 지금 실행할 수 없는 상태라 승인할 수 없습니다 — [다른 안 고르기]에서 까닭을 확인하세요.' : '';
    const caseInfo = UI.metaFold([[UI.t('dec.asset'), esc(d.asset || vars(inst).asset || '')], ['고장 유형', esc(UI.idText(sc.failureMode || ''))], [UI.t('dec.cause'), esc(UI.idText(sc.cause || ''))], [UI.t('form.deadline'), timer && timer.due_date ? esc(UI.dateTime(timer.due_date)) : ''], [UI.t('inst.followWo'), hasWorkOrder ? esc(maintenanceText) : '']], 'fold.case');
    if (I.form.needPreview || noneFeasible) I.form.mode = I.form.mode === 'reject' ? 'reject' : 'more';   // 미리 보기를 해야 하거나 고를 안이 없으면 펼쳐서 까닭을 보인다
    const mode = I.form.mode, name = UI.idText(chosen.name || '');
    const none = P.none ? window.hydApprove.noneSummary(d) : null;
    const title = P.none ? '지금은 승인할 수 있는 안이 없습니다' : `${name}${josa(name, '을/를')} 승인할까요?`;
    // 승인하면 무슨 일이 일어나는가: 서버가 준 그 안의 조치 목록 그대로(없으면 그 줄을 그리지 않는다)
    // 모든 안이 같은 까닭으로 제외됐으면 그 까닭을 여기서 한 번만 말한다(안마다 되풀이하지 않는다 — 원문은 아래 접기에)
    const will = P.none ? `<p>${none.same ? `${esc(none.reasons.join(' · '))}. 그래서 AI 에이전트가 낸 안 ${opts.length}개가 모두 실행 검사에서 제외됐습니다.` : `AI 에이전트가 낸 안 ${opts.length}개가 모두 실행 검사에서 제외됐습니다. 안마다 까닭은 아래에 있습니다.`}</p>`
      : P.actions.length ? `<p>${P.state === 'execution' ? `승인하면 시스템이 ${esc(P.actions.join(' · '))}${josa(P.actions[P.actions.length - 1], '을/를')} 실행합니다.` : `모의 판단에 포함된 조치입니다(승인 · 실행되지 않습니다): ${esc(P.actions.join(' · '))}`}${P.changed ? ' <span class="muted">추천안 대신 직접 고른 안입니다.</span>' : ''}</p>` : P.changed ? '<p class="muted">추천안 대신 직접 고른 안입니다.</p>' : '';
    const previewNow = I.form.needPreview && I.form.option ? `<button type="button" class="btn" data-variant="outline" id="tdPreviewNow" ${I.busy ? 'disabled' : ''}>${esc(UI.t('btn.preview'))}</button>` : '';
    const acts = mode === 'reject'
      ? `<button type="button" class="btn" data-variant="destructive" id="tdRejectCard" ${meRejects && !I.busy ? '' : 'disabled'}>반려 확정</button><button type="button" class="btn" data-variant="ghost" id="tdModeOff">취소</button>`
      // 승인할 안이 없는 상태의 주 행동: 반려해 이 건을 닫는 것(이 흐름이 반려를 받을 때). 새 판단은 「다시 수행」으로 요청한다 — 꺼진 [승인]을 주 단추 자리에 두지 않는다
      : P.none ? `${canReject ? `<button type="button" class="btn" id="tdRejectOpen" ${meRejects && !I.busy ? '' : 'disabled'}>반려하고 이 건 닫기</button>` : ''}<button type="button" class="btn" ${canReject ? 'data-variant="outline" ' : ''}data-case-act="recover">${UI.icon('rotate-ccw')}새 판단 요청하기</button>`
      : `<button type="button" class="btn" id="tdGo" ${canApprove && meSigns && !I.busy ? '' : 'disabled'}>${UI.icon('check')}${esc(UI.t('btn.approve'))}</button>${previewNow}${canReject ? `<button type="button" class="btn" data-variant="outline" id="tdRejectOpen" ${meRejects && !I.busy ? '' : 'disabled'}>${esc(UI.t('btn.reject'))}</button>` : ''}${opts.length > 1 || adjust ? `<button type="button" class="btn" data-variant="ghost" id="tdMore" aria-expanded="${mode === 'more'}">${mode === 'more' ? '다른 안 접기' : '다른 안 고르기'}</button>` : ''}`;
    const more = mode === 'reject' ? reasonField('반려 사유 (필수)', '1~2000자로 적으세요. 반려 결과와 단계 기록에 남습니다.')
      : mode === 'more' || P.none ? (P.none ? window.hydApprove.html(d, I.form.option, { pending: true, adjust, extra: caseInfo }) : window.hydApprove.choicesHtml(d, I.form.option, { pending: true, adjust, extra: caseInfo }))
        + (P.none ? '' : reasonField('사유 (선택)', '다른 안을 고른 까닭을 적으면 단계 기록에 남습니다.')) : '';
    box.innerHTML = todoCard({ label: '내가 할 일 · 승인', title, desc: will, attrs: `aria-busy="${I.busy}"`,
      late: clockLine(task), who: meNow ? roleLine(roleName) : '', facts: P.none ? [] : turnFacts(reviewed ? review.snapshot : d, reviewed || chosen),
      acts, more: (meNow && byMe ? '' : pickMe()) + more,
      note: P.none && mode !== 'reject' ? `${canReject ? '반려하면 설비 명령 없이 이 건이 닫힙니다. ' : ''}설비 값이 다시 들어온 뒤 [새 판단 요청하기]에서 「다시 수행」을 요청하면 AI 에이전트가 지금 값으로 다시 판단합니다.`
        : delayed ? '기한이 지나 승인 지연 알림을 보냈습니다. 승인하거나 반려하면 다음 단계로 넘어갑니다.' : '', msg: roleHint || I.msg || hint });
    const choose = id => { I.form.option = id; I.form.review = null; I.form.needPreview = false; I.msg = ''; const o = opts.find(x => x.id === id); if (o && o.approver) I.form.role = o.approver.id; renderTodoPanel(); };
    box.querySelector('[data-ap-back]')?.addEventListener('click', ev => choose(ev.currentTarget.dataset.apBack));
    box.querySelectorAll('input[name=hopt]').forEach(r => r.addEventListener('change', () => choose(r.value)));
    const on = (id, ev, fn) => { const e = document.getElementById(id); if (e) e.addEventListener(ev, fn); };
    const invalidate = () => { I.form.review = null; const go = $('#tdGo'); if (go) go.disabled = true; $('#tdReviewed').innerHTML = `<p class="muted">${esc(UI.t('form.hint.preview'))}</p>`; };
    on('tdFan', 'input', e => { I.form.fan = +e.target.value; e.target.nextElementSibling.textContent = e.target.value + ' %'; invalidate(); });
    on('tdLoad', 'input', e => { I.form.load = +e.target.value; e.target.nextElementSibling.textContent = e.target.value + ' %'; invalidate(); });
    on('tdFan', 'change', renderTodoPanel); on('tdLoad', 'change', renderTodoPanel);
    on('tdReason', 'input', e => I.form.reason = e.target.value);
    on('tdGo', 'click', () => selectCard(task));
    on('tdRejectOpen', 'click', () => setMode('reject'));
    on('tdModeOff', 'click', () => setMode(I.form.mode));
    on('tdMore', 'click', () => setMode('more'));
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
      else el.textContent = left ? `지연 알림까지 ${t}` : '기한 지남';
    });
  }

  /* 캡스톤 G1 · G7 사람 승인(안 고르기, formHandler:approve): 물음 하나 → 승인 한 번(반려는 사유와 함께). 다른 안과 받은 제안은 [다른 안 고르기]에 */
  function renderApprovePanel(task) {
    const box = $('#todoPanel');
    if (I.form.approveFor !== task.id) { I.form = { ...I.form, option: null, reason: '', role: null, mode: null, approveFor: task.id }; I.msg = ''; }   // 앞 단계에서 고른 역할을 이어 쓰지 않는다(W1-25)
    const act = ((I.view && I.view.instance.proc_inst_id === task.proc_inst_id && I.view.definition) || {}).activities?.find(a => a.id === task.activity_id);
    if (!act) {
      // 처리 건을 못 읽었거나(사유) 정의에 이 단계가 없으면 「불러오는 중」으로 남지 않는다
      const why = I.viewErr ? I.viewErr : I.view ? `흐름 정의에 이 단계(${task.activity_id})가 없습니다 — 흐름 판본이 바뀌었을 수 있습니다` : '';
      box.innerHTML = todoCard({ label: '내가 할 일 · 승인', title: UI.flowName(task.activity_name), more: why ? UI.errorBlock('승인 단계를 열지 못했습니다', why, { retry: true, cls: 'compact' }) : UI.loading('', 'compact') });
      box.querySelector('[data-retry]')?.addEventListener('click', () => load(true));
      return;
    }
    const m = window.hydApprove.proposal(task.inputs, act.approval);
    if (!I.form.option && m.usable) I.form.option = String(((m.rec || m.options[0]) || {})[m.key]);
    // 담당 = 이 처리 건에 묶인 담당(작업 행 user_id — 서버 instances._approval_actor 가 보는 값). 일반 승인은 역할 등급 없이 그 담당 그 자체만 받는다
    const endpoint = task.user_id || (((I.view.definition || {}).roles || []).find(r => r.name === act.role) || {}).endpoint || '';
    const me = window.hydInbox?.me?.() || null;
    const byMe = window.hydInbox?.byField('td', I.form);
    if (me && me.roles.includes(endpoint)) I.form.role = endpoint;      // 승인 역할 = 이 단계의 담당 역할
    const meFits = !me || (String(endpoint).startsWith('user:') ? me.id === endpoint : I.form.role === endpoint);
    const ready = !!byMe && !I.busy && meFits;
    const fitHint = me && !meFits ? `이 단계는 ${UI.roleName(endpoint, I.view.definition)} 역할이 승인하는데, 이 PC의 담당자가 그 역할에 들어 있지 않아 승인 · 반려할 수 없습니다.` : '';
    const cur = m.options.find(o => String(o[m.key]) === String(I.form.option)) || m.rec || m.options[0] || null;
    if (!m.usable || m.problems.length) I.form.mode = I.form.mode === 'reject' ? 'reject' : 'more';   // 제안이 약속과 다르면 받은 값을 펼쳐 보인다
    const mode = I.form.mode, name = cur ? String(cur[m.key]) : '';
    const folds = new Map([...box.querySelectorAll('details')].map(d => [d.querySelector('summary')?.textContent, d.open]));
    const acts = mode === 'reject'
      ? `<button type="button" class="btn" data-variant="destructive" id="tdReject" ${ready ? '' : 'disabled'}>반려 확정</button><button type="button" class="btn" data-variant="ghost" id="tdModeOff">취소</button>`
      : `<button type="button" class="btn" id="tdGo" ${ready && m.usable ? '' : 'disabled'}>${UI.icon('check')}${esc(UI.t('btn.approve'))}</button><button type="button" class="btn" data-variant="outline" id="tdRejectOpen" ${ready ? '' : 'disabled'}>${esc(UI.t('btn.reject'))}</button><button type="button" class="btn" data-variant="ghost" id="tdMore" aria-expanded="${mode === 'more'}">${mode === 'more' ? '다른 안 접기' : '다른 안 고르기'}</button>`;
    const numbers = cur ? Object.entries(cur).filter(([k, x]) => k !== m.key && typeof x === 'number' && Number.isFinite(x)).slice(0, 4).map(([k, x]) => [k === 'score' ? '점수' : varLabel(k), window.hydWords ? hydWords.num(x) : String(x), '']) : [];
    box.innerHTML = todoCard({ label: '내가 할 일 · 승인',
      title: name ? `「${name}」 안을 승인할까요?` : UI.flowName(task.activity_name),
      desc: cur && cur.reason ? `<p>${esc(cur.reason)}</p>` : '', facts: numbers,
      late: clockLine(task), who: byMe ? roleLine(UI.roleName(endpoint, I.view.definition)) : '',
      acts, more: (byMe ? '' : pickMe()) + (mode === 'reject' ? reasonField('반려 사유 (필수)', '반려할 때는 사유가 꼭 필요합니다. 결과 보고에 남습니다.')
        : mode === 'more' ? window.hydApprove.proposalHtml(m, I.form.option, { pending: true }) + reasonField('사유 (선택)', '적으면 단계 기록에 남습니다.') : ''),
      msg: I.msg || fitHint || (!m.usable ? '고를 안이 약속과 달라 승인할 수 없습니다 — 반려하거나 에이전트 단계를 다시 하세요' : '') });
    box.querySelectorAll('details').forEach(d => { const k = d.querySelector('summary')?.textContent; if (folds.has(k)) d.open = folds.get(k); });
    box.querySelector('[data-ap-back]')?.addEventListener('click', ev => { I.form.option = ev.currentTarget.dataset.apBack; I.msg = ''; renderTodoPanel(); });
    box.querySelectorAll('input[name=hopt]').forEach(r => r.addEventListener('change', () => { I.form.option = r.value; I.msg = ''; renderTodoPanel(); }));
    $('#tdReason')?.addEventListener('input', e => I.form.reason = e.target.value);
    $('#tdGo')?.addEventListener('click', () => approveTask(task, '승인'));
    $('#tdRejectOpen')?.addEventListener('click', () => setMode('reject'));
    $('#tdModeOff')?.addEventListener('click', () => setMode(I.form.mode));
    $('#tdMore')?.addEventListener('click', () => setMode('more'));
    $('#tdReject')?.addEventListener('click', () => {
      if (!String(I.form.reason || '').trim()) { I.msg = '반려 사유를 적으세요.'; renderTodoPanel(); $('#tdReason')?.focus(); return; }
      approveTask(task, '반려');
    });
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
    // 결과만 한 줄로 알린다(오른쪽 아래). 실패의 까닭은 판 안에 남는다
    if (!failed && UI.toast) UI.toast(I.doneText || '처리했습니다. 다음 단계로 넘어갑니다.', { tone: 'ok' });
    if (!failed) window.scrollTo({ top: 0, behavior: 'smooth' });      // 누른 뒤의 상태(머리 · 기다림 안내 · 결과)가 첫 화면에 보이게 — 판이 사라지며 화면이 아래로 밀려 있었다
    I.doneText = '';
    return failed;
  }
  function approveTask(task, decision) {
    I.doneText = decision === '승인' ? '승인했습니다. 다음 단계로 넘어갑니다.' : '반려했습니다. 승인 뒤 조치는 실행하지 않습니다.';
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
    I.doneText = '반려했습니다. 승인 뒤 조치는 실행하지 않습니다.';
    return act(task, '승인', () => postJ(API.process + `/api/todolist/${encodeURIComponent(task.id)}/reject-card`, {
      decision: I.decId, by: I.form.by.trim(), role: I.form.role, reason }), () => { I.dec = null; });
  }

  async function selectCard(task) {
    if (!window.hydInbox?.me?.()) return;   // P5: 「나」 없이는 승인하지 않는다(버튼도 꺼져 있다)
    I.doneText = '승인했습니다. 시스템이 실행하고 결과를 확인합니다.';
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

  /* ------------------------------------------------ 한 건: 한 장 (머리 → 내가 할 일 | 결과 → 진행 길 → 단계 기록)
     뼈대는 처리 건이 바뀔 때 한 번만 만들고, 그 뒤에는 조각(머리 · 카드 · 진행 길 · 단계 아래 칸)만 바뀐 것을 고친다 —
     2초마다 다시 읽어도 쓰던 칸 · 펼친 접기 · 옆으로 민 그림이 그대로다. */
  function ensureRecord(view) {
    if (!window.hydRecord) return null;
    if (!I.record) {
      I.recordHost = document.createElement('div'); I.recordHost.id = 'instRecord';
      I.record = hydRecord.mount(I.recordHost, { mine: () => new Set(I.asked.concat(I.todo).filter(t => t.proc_inst_id === I.sel).map(t => t.id)), onDraw: () => { fillSlots(); if (renderRecovery()) I.sig = null; window.hydTaskDetail?.place?.(); refreshTop(); } });   // 단계 줄이 그려진 뒤: 그 아래 칸(단추 · 복구 묶음 · 단계 상세)을 제자리에
      I.record.keep = true;
    }
    I.recordFor = view.instance.proc_inst_id;
    return I.record;
  }
  function feedRecord() {
    if (I.view && window.hydStream) hydStream.fromPoll(I.view.events);
    if (I.view && I.record && I.recordFor === I.view.instance.proc_inst_id) I.record.update(I.view);
  }
  const alertIdOf = inst => { const v = vars(inst); return v.alert_id || (v.alert || {}).alertId || ''; };
  // 머리의 한 줄: 무슨 사건 · 언제 시작 · 몇 단계 가운데 어디(끝난 건은 언제 끝났고 얼마나 걸렸나)
  function metaLine(view) {
    const inst = view.instance, v = vars(inst), bits = [];
    const bit = (icon, text, cls = '') => bits.push(`<span${cls ? ` class="${cls}"` : ''}>${icon ? UI.icon(icon) : ''}${esc(text)}</span>`);
    if (isSystemJob(inst)) bit('file-text', '시스템 작업');
    if (v.pattern) bit('triangle-alert', UI.patternName(v.pattern));
    if (inst.start_date) bit('clock', `${UI.dateTime(inst.start_date)} 시작`);
    if (inst.status === 'RUNNING') {
      const path = window.hydFlow ? hydFlow.pathModel(view.definition || {}, view.workitems, inst) : { nodes: [] }, nodes = path.nodes;
      const at = nodes.findIndex(n => n.state === 'now' || n.state === 'hold' || n.state === 'fail');
      // 뒤에 길이 갈리면 모두 몇 단계가 될지 아직 모른다 — 그때는 「몇 번째 단계」만 말한다
      if (at >= 0) { const n = nodes[at]; bit('route', `${path.fork ? `${at + 1}번째 단계` : `${nodes.length}단계 가운데 ${at + 1}번째`} 「${UI.flowName(n.name)}」${n.state === 'fail' ? '에서 멈춤' : n.state === 'hold' ? '에서 보류' : n.who === 'human' ? '에서 기다리는 중' : ' 진행 중'}`); }
    } else {
      const span = inst.start_date && inst.end_date ? Date.parse(inst.end_date) - Date.parse(inst.start_date) : NaN;
      if (inst.end_date) bit('circle-check', `${UI.time(inst.end_date)} 처리 완료${span >= 0 && window.hydTrace ? ` · ${hydTrace.fmtMs(span)} 걸림` : ''}`);
    }
    return bits.join('');      // 경보 번호는 읽는 값이 아니라 찾을 때 쓰는 번호다 — 머리 줄에 두지 않고 더 보기 메뉴의 「경보 번호 복사」로 낸다
  }
  // 끝난 건은 맨 위에 결과 한 장. 진행 중인데 멈춘 단계가 있으면 그 자리에 무엇이 멈췄고 어디서 조치하는지
  function topCardHtml(view) {
    const inst = view.instance;
    if (inst.status !== 'RUNNING') {
      const html = window.hydResultReport ? hydResultReport.html(view) : '';
      if (html) return html;
      const o = outcomeOf(inst);
      return `<section class="step-card case-result" aria-label="결과"><div class="result"><div class="result-label">${UI.chipText(o.label, o.tone)}결과</div><div class="result-main">${esc(endText(inst))}</div><div class="result-sub">결과 보고가 남지 않은 처리 건입니다. 무엇이 실행됐는지는 아래 단계 기록에 있습니다.</div></div></section>`;
    }
    const a = view.attention;
    if (!a) return '';
    const rows = (a.steps || []).map(s => `<li><span><b>${esc(UI.flowName(s.name))}</b> ${s.label && s.label !== a.label ? `<span class="muted">· ${esc(s.label)}</span>` : ''}${s.reason ? `<br>${esc(UI.logText(s.reason))}` : ''}</span>${s.workitem ? `<button type="button" class="btn" data-variant="outline" data-size="sm" data-goto-step="${esc(s.workitem)}">이 단계에서 조치하기</button>` : ''}</li>`).join('');
    return `<div class="alert" data-variant="destructive" role="status" aria-label="멈춘 단계">${UI.icon('triangle-alert')}<h2>${esc(/사람 조치 필요/.test(a.label || '') ? a.label : `사람 조치 필요 — ${a.label || '멈춤'}`)}</h2><section><ul class="stuck-list">${rows}</ul></section></div>`;
  }
  function flowNotes(view) {
    const inst = view.instance; let html = '';
    if (inst.status === 'RUNNING' && inst.flow_state?.end_arrivals?.length) html += `<p class="muted">${esc(UI.t('inst.endWaiting'))}</p>`;
    const waiting = Object.entries(inst.flow_state?.dependency_schedule || {}).filter(([id, spec]) => spec.flow_arrived && view.workitems.some(w => w.id === id && w.status === 'TODO'));
    waiting.forEach(([id, spec]) => {
      const task = view.workitems.find(w => w.id === id);
      const producers = [...new Set(spec.requires.map(dep => view.workitems.find(w => w.id === dep.workitem)?.activity_name || dep.activity))];
      const missingInitial = (spec.waiting_for || []).filter(x => x.reason === 'initial_input_unavailable').map(x => x.variable);
      const reason = missingInitial.length ? `시작 값 ${missingInitial.join(', ')}이 없습니다. 입력을 확인해 새 처리 건을 시작하세요.`
        : (spec.waiting_for || []).some(x => x.reason === 'fresh_output_unavailable') ? '필요한 결과값이 없어 대기 중입니다.' : `${producers.map(UI.flowName.bind(UI)).join(', ')}의 결과가 확정되면 시작합니다.`;
      html += `<p class="muted"><b>${esc(UI.t('inst.waitingResult'))}</b> · ${esc(UI.flowName(task?.activity_name || spec.activity))}: ${esc(reason)}</p>`;
    });
    return html;
  }
  const setHtml = (node, html) => { if (node && node._html !== html) { node.innerHTML = html; node._html = html; return true; } return false; };
  // 돌려주는 값: 글을 쓰는 중이라 건너뛴 자리가 있으면 true(다음 읽기에서 다시 그린다)
  function renderDetail() {
    const box = $('#instDetail');
    if (!I.view) {
      I.skelFor = null;
      box.innerHTML = I.mode && I.mode.error ? '' : !I.loaded ? '<div class="loading"><div class="skeleton sk-line" style="width:40%;height:20px"></div><div class="skeleton sk-line" style="width:70%"></div><div class="skeleton" style="height:120px;border-radius:12px"></div><div class="skeleton" style="height:240px;border-radius:12px"></div></div>' : I.sel && I.viewErr ? UI.errorBlock(UI.t('inst.cannotOpen'), String(I.viewErr).replace(/^\d{3}\s*/, ''), { retry: true })
        : !I.all.length && !I.listError ? UI.emptyGo(UI.t('inst.empty'), UI.t('inst.emptySub'), 'scenario', UI.t('nav.scenario') + ' 열기') : UI.empty(UI.t('inst.select'), '왼쪽 목록에서 처리 건을 고르면 진행 길과 단계 기록이 여기에 보입니다');
      box.querySelector('[data-retry]')?.addEventListener('click', () => load(true));
      renderRecovery(); renderMore();
      return false;
    }
    const view = I.view, inst = view.instance, pid = inst.proc_inst_id;
    const record = ensureRecord(view);
    if (I.skelFor !== pid || !box.querySelector('#casePath')) {
      box.innerHTML = `<header class="case-head"><div><h2 class="case-title"></h2><div class="case-meta"></div></div>
          <div class="dropdown-menu" id="caseMenu"><button type="button" class="btn" data-variant="outline" data-size="icon-sm" id="caseMenu-trigger" aria-haspopup="menu" aria-controls="caseMenu-menu" aria-expanded="false" aria-label="더 보기" data-tooltip="더 보기" data-side="left">${UI.icon('ellipsis')}</button>
            <div id="caseMenu-popover" data-popover aria-hidden="true" data-align="end"><div role="menu" id="caseMenu-menu" aria-labelledby="caseMenu-trigger"><div role="menuitem" id="instReload" data-case-act="reload">${UI.actHtml('reload')}</div>${alertIdOf(inst) ? `<div role="menuitem" data-id-copy="${esc(alertIdOf(inst))}">${UI.actHtml('copy', '경보 번호 복사')}</div>` : ''}<div role="menuitem" data-case-act="flow">${UI.icon('maximize-2')}전체 흐름 보기</div><div role="menuitem" data-case-act="more">${UI.icon('file-json')}자세한 기록</div></div></div></div></header>
        <div id="todoPanel"></div><div id="caseTop"></div>
        <section aria-label="진행 길"><div class="sec-head"><h2>진행 길</h2><span class="muted" data-path-side></span></div><div id="casePath"></div><div id="caseNotes"></div></section>
        <section aria-label="단계 기록"><div class="sec-head"><h2>단계 기록</h2><span class="muted case-live" data-record-side></span></div><div id="instRecord"></div><div id="taskDetailPanel"></div></section>`;
      const slot = box.querySelector('#instRecord'); if (slot && I.recordHost) slot.replaceWith(I.recordHost);
      I.skelFor = pid; I.recoverIn = null;
      window.hydTaskDetail?.mount(box.querySelector('#taskDetailPanel'));
    }
    let held = false;
    setHtml(box.querySelector('.case-title'), `${esc(inst.proc_inst_name || '이름 없는 처리 건')}${stateChip({ ...inst, attention: view.attention })}`);
    setHtml(box.querySelector('.case-meta'), metaLine(view));
    setHtml(box.querySelector('[data-path-side]'), `흐름 「${esc(UI.flowName(view.definition?.processDefinitionName || UI.defName(inst.proc_def_id)))}」 판 ${esc(inst.proc_def_version ?? '')} · 끌어서 옮기고 휠로 확대합니다`);
    // 내가 할 일(질문 · 승인 · 입력) — 쓰는 중이면 건드리지 않는다. 내 차례가 아닌데 AI 가 일하는 중이면 그 자리에 점선 안내를 둔다
    const panel = box.querySelector('#todoPanel');
    if (typingIn(panel)) held = true; else renderTodoPanel();
    refreshTop();
    const side = box.querySelector('[data-record-side]');
    if (side) {
      const live = inst.status === 'RUNNING';
      // 「끊겼습니다」는 정말 끊긴 때(다시 연결 중 · 끊김)에만 말한다 — 연결을 새로 맺는 1~2초(연결 중)에는 말하지 않는다(승인을 누른 직후 실패처럼 보였다)
      const conn = window.hydStream ? hydStream.conn() : { state: 'off', text: '' }, lost = conn.state === 'retry' || conn.state === 'off';
      setHtml(side, live ? `<i class="dot"${lost ? '' : ' data-tone="ok" data-live'}></i>${lost ? `실시간 연결이 끊겼습니다 — ${esc(conn.text)}. 2초마다 다시 읽습니다` : '새 단계가 아래에 붙습니다'}` : '');
    }
    mountPath(view);
    setHtml(box.querySelector('#caseNotes'), flowNotes(view));
    if (record) record.update(view);
    if (fillSlots()) held = true;
    if (renderRecovery()) held = true;
    renderMore();
    return held;
  }
  // 내 차례가 아니고 멈춘 것도 없는 진행 중인 건: 지금 누가 일하는지 한 줄(점선 안내 — 디자인 기준 5-1 2번)
  function waitNoteHtml(view) {
    if (view.instance.status !== 'RUNNING' || !window.hydFlow) return '';
    const n = hydFlow.pathModel(view.definition || {}, view.workitems, view.instance).nodes.filter(x => x.state === 'now').pop();
    if (!n || n.who === 'human') return '';
    const name = UI.flowName(n.name);
    const step = n.who !== 'agent' && I.record && I.record.model ? I.record.model.steps.find(s => s.w && s.w.id === n.wid) : null;
    // 그 단계가 지켜보는 값이 있으면(효과 확인) 그 값과 남은 시간이 이 자리에도 흘러나온다(caseRecord.js watchLine — 1초마다 그 자리만 채운다)
    if (step && (step.live || step.liveLine) && step.sentence) return `<div class="wait-note">${UI.icon('cog', 'ic-lg')}<span><b>시스템이 「${esc(name)}」 단계를 처리하는 중입니다.</b> ${esc(step.sentence)}${step.liveLine ? `<span class="wait-live">${step.liveLine}</span>` : ''}</span></div>`;
    return n.who === 'agent' ? `<div class="wait-note">${UI.icon('bot', 'ic-lg')}<span><b>AI 에이전트가 「${esc(name)}」 단계를 처리하는 중입니다.</b> 사람의 승인이 필요해지면 요청이 이 자리에 뜹니다.</span></div>`
      : `<div class="wait-note">${UI.icon('cog', 'ic-lg')}<span><b>시스템이 「${esc(name)}」 단계를 처리하는 중입니다.</b> 끝나면 결과가 아래 단계 기록에 붙습니다.</span></div>`;
  }
  // 내가 할 일 판이 없을 때 그 자리에 놓는 것: 끝난 건의 결과 · 멈춘 단계 알림 · 기다림 안내. 단계 기록이 그려진 뒤에도 한 번 더 부른다(기다림 안내가 그 단계의 문장과 지켜보는 값을 쓴다)
  function refreshTop() {
    const box = $('#instDetail'), panel = box && box.querySelector('#todoPanel'), top = box && box.querySelector('#caseTop'), view = I.view;
    if (!panel || !top || !view) return;
    setHtml(top, panel.firstElementChild && !panel.querySelector('[data-gone]') ? '' : topCardHtml(view) || waitNoteHtml(view));
  }
  const mineActs = view => I.asked.concat(I.todo).filter(t => t.proc_inst_id === view.instance.proc_inst_id).map(t => t.activity_id);
  // 진행 길의 상자를 누르면: 지나온 단계는 단계 기록의 그 단계로, 아직 시작하지 않은 단계는 정의에 적힌 입력 · 출력(단계 상세)을 연다
  function pickNode(activityId) {
    const view = I.view; if (!view) return;
    const rows = view.workitems.filter(w => w.activity_id === activityId && w.status !== 'TODO').sort((a, b) => (b.generation || 0) - (a.generation || 0) || String(b.start_date || '').localeCompare(String(a.start_date || '')));
    if (rows[0] && gotoStep(rows[0].id)) return;
    window.hydTaskDetail?.openActivity(activityId);
    setTimeout(() => $('#taskDetailPanel')?.scrollIntoView({ block: 'center', behavior: 'smooth' }), 60);      // 단계 상세는 단계 기록 아래에 열린다 — 누른 자리에서 보이게 그리로 간다
  }
  function mountPath(view) {
    const host = $('#casePath'); if (!host || !window.hydFlow) return;
    hydFlow.mount(host, view, { mine: mineActs(view), onPick: pickNode });
  }
  function openFullFlow() {
    const view = I.view; if (!view || !window.hydFlow) return;
    hydFlow.openFull(view, { mine: mineActs(view) });
  }
  function gotoStep(wid) {
    const li = document.querySelector(`#instRecord .step[data-step="${CSS.escape(wid)}"]`); if (!li) return false;
    li.scrollIntoView({ block: 'center', behavior: 'smooth' });
    li.dataset.flash = ''; setTimeout(() => { delete li.dataset.flash; }, 1600);
    return true;
  }

  /* ------------------------------------------------ 단계 아래 칸: 그 상황일 때만 나오는 것
     실행 중인 AI 단계의 [실행 취소], 멈춘 단계의 [단계 닫기](사유 한 줄), 그리고 멈춘 단계가 있을 때의 복구 묶음(승인 재전달 · 폐기 · 다시 평가 · 이전 조치의 영향 · 다시 수행). */
  function stepExtra(w) {
    const view = I.view; if (!view || !w) return '';
    const inst = view.instance;
    const act = (view.definition?.activities || []).find(a => a.id === w.activity_id);
    const canClose = (w.agent_orch && w.agent_mode && (w.status === 'PENDING' || (w.status === 'IN_PROGRESS' && ['FAILED', 'CANCELLED'].includes(w.draft_status)))) || (act?.type === 'serviceTask' && w.status === 'PENDING');
    const closeBtn = canClose && inst.status === 'RUNNING' ? `<button type="button" class="btn" data-variant="destructive" data-size="sm" data-close-task="${esc(w.id)}">${esc(UI.t('btn.closeTask'))}</button>` : '';
    const cancelBtn = w.agent_orch && w.agent_mode && inst.status === 'RUNNING' && w.status === 'IN_PROGRESS' && w.draft_status === 'STARTED' && w.consumer ? `<button type="button" class="btn" data-variant="outline" data-size="sm" data-cancel-task="${esc(w.id)}">${UI.icon('square')}${esc(UI.t('btn.cancelTask'))}</button>` : '';
    const stuck = ((view.attention || {}).steps || []).filter(s => s.workitem === w.id);
    const why = stuck.map(s => `<div class="alert" data-variant="destructive">${UI.icon('triangle-alert')}<h2>${esc(s.label || '멈춤')}</h2>${s.reason ? `<section>${esc(UI.logText(s.reason))}</section>` : ''}</div>`).join('');
    const reasonForm = I.closing && I.closing.id === w.id ? `<div class="step-form" data-reason-form><p class="muted">${I.closing.kind === 'close' ? '멈춘 단계를 취소로 닫습니다. 업무 실행 성공이나 설비 복구로 기록하지 않습니다.' : '실행 중인 AI 단계에 취소를 요청합니다.'}</p>${UI.section(I.closing.kind === 'close' ? '멈춘 단계 닫기' : 'AI 단계 실행 취소', `${UI.field({ label: '담당자', required: true, input: UI.actorInput('data-close-by', I.closing.by || '') })}${UI.field({ label: I.closing.kind === 'close' ? UI.t('inst.closeReason') : UI.t('inst.cancelReason'), required: true, cls: 'wide', input: `<input data-close-reason value="${esc(I.closing.reason || '')}">` })}`)}${UI.actions(`<button type="button" class="btn" data-variant="ghost" data-size="sm" data-close-abort>${esc(UI.t('btn.cancel'))}</button><button type="button" class="btn" data-size="sm" data-close-go ${I.busy ? 'disabled' : ''}>${esc(UI.t('btn.confirm'))}</button>`, I.pmsg.close || '')}</div>` : '';
    return why || closeBtn || cancelBtn || reasonForm ? `${why}${closeBtn || cancelBtn ? `<div class="chips step-acts">${closeBtn}${cancelBtn}</div>` : ''}${reasonForm}` : '';
  }
  function fillSlots() {
    const host = I.recordHost, view = I.view; if (!host || !view) return false;
    let held = false;
    const byId = new Map(view.workitems.map(w => [w.id, w]));
    host.querySelectorAll('.step[data-key] [data-step-slot]').forEach(slot => {
      const li = slot.closest('.step'), w = byId.get(li.dataset.step);
      let extra = slot.querySelector(':scope > [data-slot-extra]');
      if (!extra) { extra = document.createElement('div'); extra.dataset.slotExtra = ''; slot.prepend(extra); }
      if (typingIn(extra)) { held = true; return; }
      setHtml(extra, w ? stepExtra(w) : '');
    });
    return held;
  }
  /* 복구 묶음: 평소에는 「자세한 기록」의 「다시 수행 · 복구」 보기에, 멈춘 단계가 있을 때는 그 단계 아래에 놓는다(같은 DOM 을 옮긴다 — 쓰던 칸이 남는다) */
  const consentRole = (a, roles) => roles.includes(a?.payload?.role) ? a.payload.role : '';
  function recoverHost() {
    if (!I.recover) {
      I.recover = document.createElement('div'); I.recover.className = 'recover';
      I.recover.innerHTML = '<p class="muted" data-recover-lead></p><div data-approvals></div><div id="taskDeferralPanel"></div><div id="effectsPanel"></div><div id="reworkPanel"></div><div data-rework-history></div>';
    }
    return I.recover;
  }
  function renderRecovery() {
    const view = I.view, home = $('#caseRecoverHome'); if (!home) return false;
    const host = recoverHost();
    if (!view) { if (host.parentElement) host.remove(); home.innerHTML = UI.empty('고른 처리 건이 없습니다', '왼쪽 목록에서 처리 건을 고르면 여기에 보입니다', 'compact'); home._html = null; return false; }
    // 그 상황인가: 서버가 멈춘 단계를 알렸거나(attention), 실패한 승인 전달이 있다
    const stuck = ((view.attention || {}).steps || []).map(s => s.workitem).filter(Boolean);
    const slot = stuck.map(wid => I.recordHost?.querySelector(`.step[data-step="${CSS.escape(wid)}"] [data-step-slot]`)).find(Boolean) || null;
    const target = slot || home;
    if (typingIn(host)) return true;
    if (host.parentElement !== target) { if (target === home) { home.innerHTML = ''; home._html = null; } target.appendChild(host); }
    if (slot) setHtml(home, `<p class="muted">멈춘 단계가 있어 복구 기능을 그 단계 아래에 놓았습니다. <button type="button" class="btn" data-variant="link" data-goto-step="${esc(stuck[0])}">그 단계로 가기</button></p>`);
    if (slot) host.dataset.inStep = ''; else delete host.dataset.inStep;
    setHtml(host.querySelector('[data-recover-lead]'), slot ? '이 단계에서 할 수 있는 조치입니다. 필요한 것을 펼쳐 진행하세요.' : view.instance.status === 'RUNNING' ? '조건이나 판단 근거가 바뀌었을 때 쓰는 기능입니다. 멈춘 단계가 생기면 그 단계 아래에 같은 것이 나옵니다.' : '');
    const ap = host.querySelector('[data-approvals]');
    const folds = new Map([...ap.querySelectorAll('details')].map(d => [d.querySelector('summary')?.textContent.trim(), d.open]));
    if (setHtml(ap, approvalHtml(view) + workOrderRetryHtml(view))) {
      ap.querySelectorAll('details').forEach(d => { const k = d.querySelector('summary')?.textContent.trim(); if (folds.has(k)) d.open = folds.get(k); });
      wireApprovalButtons(ap);
    }
    window.hydTaskDeferral?.mount(host.querySelector('#taskDeferralPanel'), { view, by: actor(), changed: () => load(true) });
    window.hydEffects?.mount(host.querySelector('#effectsPanel'), { view, by: actor(), changed: () => load(true) });
    window.hydRework?.mount(host.querySelector('#reworkPanel'), { view, by: actor(), changed: () => load(true) });
    setHtml(host.querySelector('[data-rework-history]'), (view.reworks || []).length ? UI.fold(`${esc(UI.t('inst.reworkHistory'))} <span class="muted">${view.reworks.length}건</span>`, view.reworks.map(r => `<p>${esc(r.generation)}${esc(UI.t('inst.gen'))} · ${esc(UI.who(r.request.by))} (${esc(who(r.request.role))}) · ${esc(r.request.reason)}</p>`).join('')) : '');
    return false;
  }
  // 재전달 · 폐기 폼의 승인 역할: 승인 기록에 남은 역할을 읽기 전용으로 보이고 값은 숨은 칸에 싣는다. 못 읽었으면 그 까닭
  const roleField = (key, r) => r ? UI.readonly('승인 역할', esc(who(r))) + `<input type="hidden" data-retry-role="${esc(key)}" value="${esc(r)}">`
    : `<input type="hidden" data-retry-role="${esc(key)}" value=""><p class="muted" data-tone="danger">승인 기록에서 승인 역할을 읽지 못했습니다.</p>`;
  function workOrderRetryHtml(view) {
    const failed = view.workitems.filter(w => w.tool === 'enterprise:WO_CREATE' && w.status === 'PENDING');
    const approval = (view.approvals || []).find(a => a.status === 'DELIVERED');
    const roles = Object.keys(approval?.payload?.plan?._snapshot?.roles || {});
    return failed.map(w => { const f = retryForm(w.id); return UI.fold(`${esc(UI.t('inst.woFailed'))} ${UI.chipText('실패', 'danger')}`, `<div data-approval-panel="${esc(w.id)}"><p class="muted" data-tone="danger">${esc(w.log || '')}</p><p class="muted">자동 재시도를 마쳤습니다. 오류를 해결한 뒤 승인했던 같은 내용으로 다시 전달할 수 있습니다.</p>
      ${UI.section('', `${UI.actorInput(`data-retry-by="${esc(w.id)}"`, f.by)}${roleField(w.id, consentRole(approval, roles))}`)}
      ${UI.actions(`<button type="button" class="btn" data-size="sm" data-work-order-retry="${esc(w.id)}" ${I.busy || !roles.length ? 'disabled' : ''}>${esc(UI.t('btn.retry'))}</button>`, !roles.length ? '승인 원문을 확인할 수 없어 별도 검토가 필요합니다.' : I.pmsg[w.id] || '')}</div>`, { open: true }); }).join('');
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
      const retry = lost ? `<p>앞서 보낸 폐기 요청의 응답을 받지 못했습니다. 아래 단추로 결과를 확인하세요. 같은 요청이라 두 번 처리되지 않습니다.</p>${UI.actions(`<button type="button" class="btn" data-variant="outline" data-size="sm" data-discard-retry="${esc(a.todo_id)}" ${I.busy ? 'disabled' : ''}>폐기 결과 확인</button>`, I.pmsg[a.todo_id] || '')}`
        : reviewable ? `<p class="muted">${reviewRequired ? '현재 조건이 달라 기존 동의를 전달할 수 없습니다. 판단 단계의 다시 수행으로 새 판단과 승인을 받으세요.' : a.status === 'FAILED' ? '승인한 내용은 보존됐습니다. 오류를 확인한 뒤 같은 내용을 다시 전달할 수 있습니다.' : '조건 변경으로 명령이 보류됐다면 판단 단계에서 새 검토를 시작하세요. 사건이 종료됐다면 아래에서 실행 효과를 확인하고 취소할 수 있습니다.'}</p>
        ${UI.section('', `${UI.actorInput(`data-retry-by="${esc(a.todo_id)}"`, f.by)}${roleField(a.todo_id, consentRole(a, roles))}
        ${UI.field({ label: '폐기 ' + UI.t('form.reason'), cls: 'wide', hint: '사건이 종료되고 실제 조치가 없음을 확인한 경우에만 승인을 폐기하고 처리 건을 취소할 수 있습니다.', input: `<input data-discard-reason="${esc(a.todo_id)}" value="${esc(f.reason)}" placeholder="후속 조치를 진행하지 않고 종료하는 이유">` })}`)}
        ${UI.actions(`${a.status === 'FAILED' && !reviewRequired ? `<button type="button" class="btn" data-size="sm" data-approval-retry="${esc(a.todo_id)}" ${I.busy ? 'disabled' : ''}>${esc(UI.t('btn.retry'))}</button>` : ''}<button type="button" class="btn" data-variant="outline" data-size="sm" data-approval-discard-preview="${esc(a.todo_id)}" ${I.busy ? 'disabled' : ''}>${esc(UI.t('btn.effects'))}</button>`, I.pmsg[a.todo_id] || '')}
        <div data-discard-preview role="status">${dp ? discardPreviewHtml(dp) : ''}</div>` : '';
      const discarded = a.status === 'DISCARDED' ? `<p class="muted">${(a.history || []).at(-1)?.via === 'rework' ? '다시 수행 요청으로 이전 승인을 폐기했습니다. 새 판단과 새 승인이 필요합니다.' : '처리 건을 취소했습니다.'} 이전 승인·오류는 보존됩니다.</p>${UI.raw((a.history || []).at(-1))}` : '';
      return UI.fold(`${esc(UI.t('inst.approval'))} ${UI.deliveryChip(a.status)}`, `<div data-approval-panel="${esc(a.todo_id)}"><p>${esc(option.name || p.option)} · ${esc(UI.t('card.approver'))} <b>${esc(who(p.role))}</b> · 전달 시도 ${esc(a.attempts)}회</p>
        ${a.error ? UI.raw(a.error, { title: '오류 기록', open: true }) : ''}${retry}${discarded}</div>`, { open: reviewable || a.status === 'FAILED' || !!lost });
    }).join('');
  }

  /* ------------------------------------------------ 「자세한 기록」 접기(한 건의 맨 아래 하나): 개발 · 운영용 보기를 조각 탭으로 바꿔 본다.
     접혀 있거나 고르지 않은 보기는 그리지 않는다. */
  function renderMore() {
    const fold = $('#caseMore'); if (!fold) return;
    UI.markViewTab($('#caseMoreTabs'), b => b.dataset.moreTab === I.more);
    fold.querySelectorAll('.case-more-pane').forEach(p => { p.hidden = p.dataset.more !== I.more; });
    if (!fold.open) return;
    const view = I.view, none = UI.empty('고른 처리 건이 없습니다', '왼쪽 목록에서 처리 건을 고르면 여기에 보입니다', 'compact');
    if (I.more === 'log') { const box = $('#caseLog'); setHtml(box, view ? logPane(view) : none); box.querySelector('[data-events-more]')?.addEventListener('click', () => { I.eventsShown += 40; box._html = null; renderMore(); }); }
    if (I.more === 'values') setHtml($('#caseValues'), view ? valuesPane(view, vars(view.instance)) : none);
    if (I.more === 'graph') setHtml($('#caseGraph'), view ? graphHtml(view.instance) : none);
  }
  /* 처리 건 값: 이름 붙은 읽기 전용 값(어느 단계가 만들었는지) + 시작 값 원문 */
  function valuesPane(view, v) {
    const inst = view.instance;
    // 값: label = definition data name, structured values folded (read-only form)
    const internal = new Set(['decision', 'decision_id', 'guide_card', 'candidates', 'compliance', 'incident', 'commands', 'chosen_option', 'alert', 'alert_id']);
    const varRows = (inst.variables_data || []).filter(row => !internal.has(row.key)).map(row => {
      const value = row.value, name = UI.terms['var.' + row.key] || (row.name && row.name !== row.key ? row.name.replace(/\s*[\(—(].*$/, '') : row.key);
      const shown = row.key === 'pattern' ? UI.patternName(value) : row.key === 'chosen_skill_kind' ? (value === 'control' ? UI.t('chip.control') : value === 'work_order' ? UI.t('chip.workOrder') : value)
        : row.key === 'cause' ? (((v.guide_card || {}).causes || []).find(c => c.id === value) || (v.guide_card || {}).topCause || {}).name || UI.name(value)
        : row.key === 'failure_mode' ? UI.idText((typeof (v.guide_card || {}).failureMode === 'object' ? (v.guide_card.failureMode || {}).name : (v.decision || {}).failureMode) || UI.name(value))
        : row.key === 'chosen_skill' ? ((v.chosen_option || {}).name || UI.name(value)) : row.key === 'approved_role' ? who(value) : typeof value === 'string' ? UI.idText(value) : value;
      const body = value !== null && typeof value === 'object' ? UI.raw(value, { title: UI.t('inst.structured') }) : esc(shown === true ? UI.t('yes') : shown === false ? UI.t('no') : shown ?? UI.t('inst.noValue'));
      const source = (inst.variable_sources || {})[row.key];
      const producer = source?.kind === 'workitem' ? view.workitems.find(w => w.id === source.id) : null;
      const origin = source?.kind === 'input' ? UI.t('inst.source.input') : source?.kind === 'workitem' ? UI.flowName(producer?.activity_name || source.activity) : source?.kind === 'runtime' ? UI.t('inst.source.runtime') : UI.t('inst.source.none');
      return UI.readonly(name, body, origin);
    }).join('');
    return `<dl class="kv"><dt>${esc(UI.t('inst.started'))}</dt><dd>${esc(UI.dateTime(inst.start_date))}</dd>${inst.end_date ? `<dt>${esc(UI.t('inst.ended'))}</dt><dd>${esc(UI.dateTime(inst.end_date))}</dd>` : ''}<dt>처리 건 ID</dt><dd class="mono">${esc(inst.proc_inst_id)}</dd><dt>흐름</dt><dd>${esc(UI.defName(inst.proc_def_id))} <span class="muted">· 판 ${esc(inst.proc_def_version ?? '')}</span></dd></dl>
      <h3 class="case-sub">지금 값</h3>${varRows || `<p class="muted">${esc(UI.t('empty.noData'))}</p>`}
      ${UI.fold(esc(UI.t('inst.initial')) + ' 원문', inst.initial_variables == null ? `<p class="muted">${esc(UI.t('empty.noData'))}</p>` : `<pre class="code">${esc(JSON.stringify(inst.initial_variables, null, 2))}</pre>`)}`;
  }
  /* 단계 표 원문: 작업 행마다 엔진의 상태 값 · 시각 · 메모 · 출력 원문 + 에이전트 활동(도구 호출 · 결과 묶음) */
  function logPane(view) {
    const rows = view.workitems.map(w => `<tr data-status="${esc(w.status)}"><td>${esc(UI.flowName(w.activity_name))}${w.generation ? `<br><span class="muted">${esc(w.generation)}${esc(UI.t('inst.gen'))}</span>` : ''}</td><td>${esc(UI.status(w.status))}${w.draft_status && w.status !== 'DONE' ? `<br><span class="muted">${esc(UI.status(w.draft_status))}</span>` : ''}</td>
      <td>${esc(who(w.user_id))}</td>
      <td class="num">${esc(UI.time(w.start_date))}${w.end_date ? ' → ' + esc(UI.time(w.end_date)) : ''}${w.due_date && !w.end_date ? `<br><span class="muted">${esc(UI.t('inst.due'))} ${esc(UI.time(w.due_date))}</span>` : ''}</td>
      <td class="case-memo">${esc(UI.logText(w.log || ''))}${w.output && Object.keys(w.output).length ? UI.raw(w.output, { title: `${UI.t('inst.output')} ${valueNames(Object.keys(w.output)) || '글'}` }) : ''}${UI.raw({ id: w.id, activity_id: w.activity_id, log: w.log, generation: w.generation, agent_orch: w.agent_orch, agent_mode: w.agent_mode, consumer: w.consumer, draft_status: w.draft_status, supersedes_id: w.supersedes_id, gateway_decisions: w.gateway_decisions })}</td></tr>`).join('');
    // a tool call and its result become one record with the duration
    const evs = view.events.slice();
    const started = new Map(); evs.forEach(e => { if (e.event_type === 'tool_usage_started' && e.data?.tool_use_id) started.set(e.data.tool_use_id, e); });
    // A141: 최근 20건만 먼저, 나머지는 더 보기. 도구 이름은 UI.toolName(원문은 각 기록의 원문 접기에 그대로)
    const all = evs.reverse().filter(e => !(e.event_type === 'tool_usage_started' && evs.some(x => x.event_type === 'tool_usage_finished' && x.data?.tool_use_id === e.data?.tool_use_id)));
    const events = all.slice(0, I.eventsShown).map(e => {
      let detail = eventDetail(e), name = e.job_id === 'TASK_REVIEW_REQUIRED' ? e.job_id : e.event_type;
      if (e.event_type === 'tool_usage_finished') { const s0 = started.get(e.data?.tool_use_id); if (s0) detail = `${UI.toolName(e.data.tool)} · ${hydTrace.fmtMs(new Date(e.timestamp) - new Date(s0.timestamp))}`; name = 'tool_usage_started'; }
      // A132: the worker says where the result came from (result_source file | message)
      const chips = e.event_type === 'task_completed' && e.data?.result_source === 'file' ? `<span class="muted">${esc(UI.t('inst.resultFile'))}</span>` : '';
      return UI.eventRecord({ time: e.timestamp, name, actor: CREW[e.crew_type] || (/^cliagents:/.test(e.crew_type || '') ? 'AI 에이전트' : ''), detail, raw: e.data, chips });
    }).join('') + (all.length > I.eventsShown ? `<button type="button" class="btn more" data-variant="ghost" data-size="sm" data-events-more>${esc(UI.t('inst.eventsMore'))} (남은 ${all.length - I.eventsShown}건)</button>` : '');
    return `<h3 class="case-sub">${esc(UI.t('inst.steps'))} ${view.workitems.length}줄</h3><div class="table-container"><table class="table case-table"><thead><tr><th>${esc(UI.t('inst.stepTable.step'))}</th><th>${esc(UI.t('inst.stepTable.status'))}</th><th>${esc(UI.t('inst.stepTable.who'))}</th><th>${esc(UI.t('inst.stepTable.when'))}</th><th>${esc(UI.t('inst.stepTable.result'))}</th></tr></thead><tbody>${rows}</tbody></table></div>
      <h3 class="case-sub">${esc(UI.t('inst.events'))} ${view.events.length}줄</h3><div class="stream-log case-events">${events || `<p class="muted">${esc(UI.t('empty.noData'))}</p>`}</div>`;
  }
  function graphHtml(inst) {
    const g = I.graph;
    if (!g && !I.caseProjection) return `<p class="muted">${esc(UI.t('loading'))}</p>`;   // 이 탭을 연 뒤 첫 읽기가 끝나기 전
    const pending = g && g.projection, cases = I.caseProjection;
    const sync = `<p>${esc(UI.t('inst.projectionPending'))}: ${pending ? esc(pending.pending) + '건' : esc(UI.t('inst.projectionNone'))} · ${esc(UI.t('inst.projectionAll'))}: ${cases && !cases.error ? esc(cases.pending) + '건' : esc(UI.t('inst.projectionNone'))}</p>
      ${cases && cases.worker_running === false ? `<div class="alert" data-variant="destructive" role="status">${UI.icon('circle-alert')}<h2>지식 지도에 반영하는 작업이 멈춰 있습니다</h2><section>반영이 늦어집니다. 잠시 뒤에도 그대로면 시스템 › 시스템 구성에서 처리 서비스의 상태를 확인하세요.</section></div>` : ''}
      ${cases && cases.error ? `<p class="muted" data-tone="danger">반영 상태 조회 실패: ${esc(cases.error)}</p>` : ''}
      ${cases?.knowledge ? `<p class="muted">지식 연결 변경 확인: <span data-knowledge-checked>${esc(knowledgeChecked(cases))}</span>${cases.knowledge.last_error ? '<br><span class="muted" data-tone="danger">연결 재확인 실패: ' + esc(cases.knowledge.last_error) + '</span>' : ''}</p>` : ''}
      ${pending && pending.last_error ? UI.raw(pending.last_error, { title: pending.last_error.startsWith('ProjectionConflict:') ? '반영이 멈춘 까닭 (오류 원문)' : '반영을 다시 시도하는 중 (오류 원문)' }) : ''}
      ${pending?.last_error?.startsWith('ProjectionConflict:') || cases?.items?.some(x => x.last_error?.startsWith('ProjectionConflict:')) ? `<div class="alert" data-variant="destructive" role="status">${UI.icon('circle-alert')}<h2>지식 지도 자동 반영이 멈췄습니다</h2><section>이 처리 건의 기록과 지식 지도의 내용이 서로 달라 자동 반영을 멈췄습니다. 화면에서 고칠 수 없습니다 — 아래 오류 원문과 함께 시스템 관리자에게 알리세요.</section></div>` : ''}
      ${cases && (cases.items || []).some(x => x.last_error) ? UI.raw(cases.items.filter(x => x.last_error), { title: '사건 · 판단 반영 오류' }) : ''}`;
    if (!g) return sync + `<p class="muted">${esc(UI.t('loading'))}</p>`;
    if (g.error) return sync + `<p class="muted">${esc(UI.t('error.load'))}: ${esc(g.error)}</p>`;
    const cy = UI.raw(g.cypher, { title: UI.t('inst.query'), lang: 'cypher' }) + UI.raw(g.params, { title: '질의 조건 값' });
    const x = g.graph;
    if (!x) return sync + '<p class="muted">조회 가능한 반영 내역이 없습니다.</p>' + cy;
    const rows = (x.workitems || []).map(w => `<tr data-status="${esc(w.status)}"><td>${esc(UI.flowName(w.activity_name || w.activity_id || ''))}</td><td>${UI.chip(w.status)}</td><td>${w.executes ? `${esc(w.executes_name || '')}<br><span class="muted">${esc(w.executes_type || '')}</span>` : '–'}</td><td>${w.assigned_to ? w.assigned_to.split(',').map(id => esc(who(id))).join(', ') : '–'}</td></tr>`).join('');
    const warnings = (x.warnings || []).map(w => `<p class="muted" data-tone="danger">확인 필요: ${esc(w)}</p>`).join('');
    const version = x.definition || {};
    return sync + warnings + `<p>흐름 <b title="${esc(version.id || '')}">${esc(UI.defName(version.id || ''))}</b> · 판 ${esc(version.version || x.process.version || '')}${x.asset ? ` · ${esc(UI.t('dec.asset'))} ${esc(x.asset)}` : ''}</p>
      <div class="table-container"><table class="table case-table"><thead><tr><th>${esc(UI.t('step'))}</th><th>${esc(UI.t('inst.stepTable.status'))}</th><th>${esc(UI.t('knowledge'))}</th><th>${esc(UI.t('inst.stepTable.who'))}</th></tr></thead><tbody>${rows}</tbody></table></div>${cy}`;
  }
  // 기록 줄의 「누가」: 실행기 이름(cliagents:claude-code) 같은 내부 값을 그대로 보이지 않는다. 값 이름(영문 키)은 이름 사전으로, 원문(JSON)은 그 줄의 원문 접기에만 둔다
  const CREW = { agent: 'AI 에이전트', human: '담당자', result: '시스템' };
  const valueNames = keys => (keys || []).filter(k => k !== 'text').map(k => UI.terms['var.' + k] || hydWords.fieldName(k)).join(', ');
  const plainContent = c => { const t = String(c || '').trim(); return /^[\[{]/.test(t) ? '결과를 정해진 꼴(JSON)로 냈습니다 — 원문은 아래에 있습니다' : UI.clean(hydWords.text(t)).slice(0, 200); };
  function eventDetail(e) {
    const d = e.data || {};
    if (d.recovery === 'verify_external_effect') return '외부 작업이 이미 실행됐을 수 있어 자동 재시도를 멈췄습니다. 외부 시스템의 실제 처리 결과를 확인하세요. ' + (d.raw_error || '');
    if (d.recovery === 'new_judgment_and_consent') return '현재 조건 검사로 명령을 보류했습니다. 판단 단계에서 새 검토와 승인을 진행하세요. ' + ((d.assessment || {}).reasons || []).join('; ');
    if (d.tool) return `${UI.toolName(d.tool)}${d.input ? ' ' + String(hydWords.ask(d.tool, d.input) || '').slice(0, 120) : ''}${d.output ? ' → ' + String(hydWords.got(d.tool, d.output) || '').slice(0, 120) : ''}`;      // 처리 과정(trace.js)과 같은 요약 — JSON 원문은 각 기록의 원문 접기에
    if (d.goal) return `${UI.logText(d.goal)}${d.name ? ' · ' + UI.who(d.name) : ''}`;
    if (d.text || d.question) return humanQuestionText(d).slice(0, 160);
    return UI.logText(d.message || d.note || d.friendly || d.raw_error || d.reason || '') || (d.content ? plainContent(d.content) : '') || (d.output_keys ? UI.t('inst.output') + ' ' + valueNames(d.output_keys) : '') || (d.answer ? UI.t('form.answer') + ' ' + d.answer : '');
  }

  /* ------------------------------------------------ 단계 아래 칸의 단추(위임 한 번 — 칸은 스스로 다시 그려진다) */
  function wireStepButtons(box) {        // A161-U1: delegated once — the trace redraws its own steps
    if (box._stepWired) return; box._stepWired = true;
    box.addEventListener('click', async e => {
      const b = e.target.closest('[data-close-task],[data-cancel-task]');
      if (b) { I.closing = { id: b.dataset.closeTask || b.dataset.cancelTask, kind: b.dataset.closeTask ? 'close' : 'cancel', reason: '', by: actor() }; I.pmsg.close = ''; fillSlots(); return; }
      if (e.target.closest('[data-close-abort]')) { I.closing = null; fillSlots(); return; }
      const go = e.target.closest('[data-close-go]'); if (!go || I.busy || !I.closing) return;
      const reason = (I.closing.reason || '').trim(), by = (I.closing.by || '').trim();
      if (!by) { I.pmsg.close = '담당자 정보를 읽지 못했습니다. 화면을 새로 고친 뒤 다시 해 주세요.'; fillSlots(); return; }
      if (!reason) { I.pmsg.close = UI.t('form.err.reason'); fillSlots(); return; }
      I.busy = true; go.disabled = true;
      try { await postJ(API.process + `/api/todolist/${encodeURIComponent(I.closing.id)}/${I.closing.kind}`, { by, reason }); I.pmsg.close = ''; I.closing = null; }
      catch (err) { I.pmsg.close = err.message; }
      finally { I.busy = false; await load(true); fillSlots(); }
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
    return UI.card({ title: '폐기 전 확인', body: `<p>${esc(UI.t('case'))} ${UI.chip(evidence.incident.state)} · ${esc(UI.t('command'))} 없음 · 업무 실행 기록 ${esc(evidence.enterprise_receipts.length)}건</p>
      <p>${esc(evidence.outcome)}</p><p>취소할 남은 단계 ${esc(evidence.cancel_workitems.length)}건 · ${esc(UI.t('form.reason'))}: ${esc(p.reason)}</p>
      ${UI.actions(`<button type="button" class="btn" data-variant="destructive" data-size="sm" data-confirm-discard ${I.busy ? 'disabled' : ''}>승인 폐기 · 처리 건 취소</button>`)}` });
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
      if (!by || !role) { I.pmsg[key] = UI.t('form.err.byRole'); renderRecovery(); return; }
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
    if (taskId && window.hydTaskDetail) hydTaskDetail.T.pending = { pid: id, wid: taskId };
    I.skelFor = null;                                   // 단계 상세가 그 단계를 열도록 뼈대를 새로 붙인다
    pick(id, taskId || null);
  }
  hydTabs.onShow(name => { if (name === 'instances') load(true); });
  const detailBox = $('#instDetail');
  wireStepButtons(detailBox);
  detailBox.addEventListener('click', e => {
    const go = e.target.closest('[data-goto-step]'); if (go) { gotoStep(go.dataset.gotoStep); return; }
    // 머리의 더 보기 메뉴: 다시 읽기 · 전체 흐름 보기 · 자세한 기록 펼치기
    const act = e.target.closest('[data-case-act]'); if (!act) return;
    if (act.dataset.caseAct === 'reload') load(true);
    else if (act.dataset.caseAct === 'flow') openFullFlow();
    else if (act.dataset.caseAct === 'more') { const fold = $('#caseMore'); fold.open = true; fold.scrollIntoView({ block: 'start', behavior: 'smooth' }); }
    // 내가 할 일 판의 [새 판단 요청하기]: 자세한 기록의 「다시 수행 · 복구」 보기를 펼쳐 그 자리로 간다
    else if (act.dataset.caseAct === 'recover') { const fold = $('#caseMore'); I.more = 'recover'; fold.open = true; renderMore(); renderRecovery(); const rw = fold.querySelector('#reworkPanel details'); if (rw) rw.open = true; fold.scrollIntoView({ block: 'start', behavior: 'smooth' }); }
  });
  $('#instTabs').addEventListener('click', e => {
    const b = e.target.closest('[data-inst-filter]'); if (!b || b.dataset.instFilter === I.filter) return;
    I.filter = b.dataset.instFilter; I.listShown = UI.PAGE; if (I.filter !== 'mine') I.role = '';
    // 누른 즉시 지금 아는 것으로 거른 목록을 보이고(최근 50건 안에서), 서버가 상태로 걸러 준 목록은 읽는 대로 바꾼다
    I.filtered = null;
    I.instances = I.filter === 'running' ? I.all.filter(x => x.status === 'RUNNING') : I.filter === 'done' ? I.all.filter(x => x.status !== 'RUNNING') : I.all;
    renderTabs(); renderList(); load(true);
  });
  $('#caseMoreTabs').addEventListener('click', e => { const b = e.target.closest('[data-more-tab]'); if (!b) return; I.more = b.dataset.moreTab; renderMore(); if (I.more === 'graph') load(true); });
  $('#caseMore').addEventListener('click', e => { const go = e.target.closest('[data-goto-step]'); if (go) gotoStep(go.dataset.gotoStep); });
  $('#caseMore').addEventListener('toggle', () => { renderMore(); if ($('#caseMore').open && I.more === 'graph') load(true); });
  window.addEventListener('hyd:me', () => { if (state.tab === 'instances' && I.view && !typingIn($('#todoPanel'))) renderTodoPanel(); });   // 담당자를 읽고 나면 꺼져 있던 단추를 켠다
  setInterval(() => load(false), 2000);
  setInterval(updateApprovalClock, 1000);
  // 셸이 주소에 적는 지금 화면: 처리 건 + 열어 둔 단계(단계 상세가 열려 있으면 그 단계, 아니면 「내 할 일」에서 고른 단계)
  const route = () => ({ inst: I.sel || null, task: (window.hydTaskDetail && hydTaskDetail.T.wid) || I.taskSel || null });
  window.hydInstances = { I, load, openTask, route, counts, stateOf };
})();
