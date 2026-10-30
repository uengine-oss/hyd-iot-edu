/* B5 에이전트에게 질문하기 — window.hydAsk.mount(el). 주소 #/ask
   질문 하나 = 처리 건 하나(정식 정의 ask_agent). 답할 에이전트를 고르고 보내면, 진행 중에는 도구 호출이 한 줄씩 나타나고(1.5초마다 다시 읽음),
   끝나면 답 + 근거(실행한 질의 · 조회 결과 · 실행 기록에서 확인됐는지) 또는 "답할 수 없음 + 이유"와 "처리 과정 보기" 링크.
   한 질문 → 한 답(이전 질문을 기억하지 않음). 지난 질문 목록. 서버: process GET/POST /api/ask* (it/process/procsvc/ask.py).
   원본 대응: process-gpt-vue3 ui/WorkItemChat.vue(도구 입력 · 결과 접기), apps/todolist/InstanceTimeline.vue(작업 하나 = 메시지 하나). */
(function () {
  const LIVE = new Set(['waiting', 'running', 'submitted', 'correcting', 'asking']);
  const STATE = { waiting: ['대기', 'neutral'], running: ['조회 중', 'accent'], submitted: ['정리 중', 'accent'], correcting: ['형식 고치는 중', 'warning'],
    asking: ['사람에게 질문', 'warning'], done: ['끝', 'success'], failed: ['실패', 'danger'], closed: ['닫힘', 'neutral'], broken: ['오류', 'danger'] };
  const A = { el: null, status: null, statusErr: '', agents: [], agent: '', draft: '', sending: false, err: '', cur: null, history: [], timer: null, histErr: '' };
  const api = path => API.process + '/api/ask' + path;
  const uuid = () => UI.uuid();   // 비보안 문맥(IP 주소로 연 포털)에서도 같은 공용 생성기
  const toolName = c => UI.toolName(c.raw_tool || c.tool);
  // 키 없는 PC(AI 응답 재생): 강의에서 다룬 질문에만 저장된 답이 있다 — 예시를 그 질문으로 보이고, 다시 진행은 같은 거절이라 숨긴다
  const replay = () => A.status?.worker?.ai_mode === 'replay';
  const recorded = () => A.status?.worker?.replay_questions || [];
  const picks = () => recorded().length ? `<div class="row-wrap ask-picks">${recorded().map(q => `<button type="button" class="btn small" data-ask-pick="${esc(q)}">${esc(q)}</button>`).join('')}</div>` : '';

  async function loadStatus() {
    try {
      A.status = await getJ(api('/status')); A.statusErr = '';
      A.agents = A.status.agents || [];
      if (!A.agent || !A.agents.some(a => a.id === A.agent)) A.agent = A.status.default || (A.agents[0] && A.agents[0].id) || '';
    } catch (e) { A.status = null; A.statusErr = e.message; }
  }
  async function loadHistory() {
    try { A.history = await getJ(api('')); A.histErr = ''; } catch (e) { A.histErr = e.message; }
  }
  async function mount(el) {
    A.el = el; render();
    await Promise.all([loadStatus(), loadHistory()]);
    render();
  }
  function show() { Promise.all([loadStatus(), loadHistory()]).then(render); }

  async function send() {
    const q = A.draft.trim();
    if (!q || A.sending) return;
    A.sending = true; A.err = ''; render();
    try {
      A.cur = await postJ(api(''), { question: q, agent: A.agent || null, by: ((window.hydInbox && window.hydInbox.me && window.hydInbox.me()) || {}).name || '수강생', request_id: uuid() });
      A.draft = '';
      poll();
      loadHistory().then(render);
    } catch (e) { A.err = e.message; }
    finally { A.sending = false; render(); }
  }
  async function open(id) {
    if (A.cur?.id!==id) { A.retryNote='';A.retryId=null; }
    try { A.cur = await getJ(api('/' + encodeURIComponent(id))); A.err = ''; poll(); }
    catch (e) { A.err = '질문을 읽지 못했습니다: ' + e.message; }
    render();
  }
  async function retry() {
    if (!A.cur || A.cur.state!=='failed' || A.sending) return;
    A.retryNote=A.el.querySelector('#askRetryNote')?.value || A.retryNote || '';
    A.sending=true; A.err=''; render();
    A.retryId=A.retryId || uuid();
    try {
      A.cur=await postJ(api('/'+encodeURIComponent(A.cur.id)+'/retry'),
        {request_id:A.retryId,by:A.cur.asked_by,reason:A.retryNote.trim() || '연결 상태 확인 후 같은 질문을 다시 진행합니다.'});
      A.retryId=null;poll();loadHistory().then(render);
    } catch(e) { A.err=e.message; }
    finally { A.sending=false;render(); }
  }
  function poll() {
    clearTimeout(A.timer);
    if (!A.cur || !LIVE.has(A.cur.state)) return;
    A.timer = setTimeout(async () => {
      const view = document.getElementById('view-ask');
      if (view && !view.classList.contains('active')) { poll(); return; }           // 화면을 떠나 있으면 읽지 않고 기다린다
      try {
        const was = A.cur.state;
        A.cur = await getJ(api('/' + encodeURIComponent(A.cur.id)));
        if (was !== A.cur.state && !LIVE.has(A.cur.state)) loadHistory().then(render);
        if (A.traceWid) loadItem();                                       // A161-U1: the trace also re-reads (SSE may lag)
      } catch (e) { A.err = '진행 상황을 읽지 못했습니다: ' + e.message; }
      render(); poll();
    }, 1500);
  }
  async function reset() {
    const ok = UI.confirm ? await UI.confirm({ title: '지난 질문 기록 지우기', body: '끝난 질문 기록을 목록에서 지웁니다. 질문 정의 · 에이전트 · 업무 DB · 지식은 그대로입니다.', danger: true })
      : window.confirm('끝난 질문 기록을 지울까요?');
    if (!ok) return;
    try { const r = await postJ(api('/reset'), {}); UI.toast && UI.toast(r.note, { tone: 'pos' }); if (A.cur && A.cur.state === 'done') A.cur = null; }
    catch (e) { A.err = '지우지 못했습니다: ' + e.message; }
    await loadHistory(); render();
  }

  /* ---------------------------------------------------------------- 그리기
     A161-U1: 질문 칸은 한 번만 그리고(입력 중에 다시 그려 글자 · 초점을 잃지 않게), 대화 부분만 갱신한다.
     대화 = 질문 말풍선 → 에이전트 카드(실시간 처리 과정: trace.js, SSE 로 도구 호출이 생기는 즉시) → 답 카드.
     참고: Dify base/chat/chat/answer/workflow-process.tsx(답 위의 "처리 과정" 접이 카드, 실행 중 회전) · tool-detail.tsx(도구 한 줄, 펼치면 요청 · 응답),
           process-gpt-vue3 components/ui/WorkItemChat.vue · ds/components/PgMessage.vue(사용자 말풍선 오른쪽, 에이전트 왼쪽). */
  function readyHtml() {
    if (A.statusErr) return `<p class="neg" role="status">질문 기능 상태를 읽지 못했습니다: ${esc(A.statusErr)}</p>`;
    const s = A.status;
    if (!s) return '<p class="muted">상태를 확인하는 중…</p>';
    if (s.ready) return replay() ? UI.chipText('강사가 저장한 답 재생', 'neutral') : `<span class="live-conn on">답할 일꾼 연결됨</span>`;
    return `<div class="ask-warn" role="status">${UI.chipText('지금은 답할 일꾼이 없습니다', 'warning')} <span>${esc(s.reason || '')}</span></div>`;
  }
  function agentOptions() {
    return A.agents.map(a => `<option value="${esc(a.id)}" ${a.id === A.agent ? 'selected' : ''}>${esc(a.name)}${a.default ? ' (기본)' : a.mine ? ' (내가 만든 것)' : ''}</option>`).join('');
  }
  function agentLine() {
    const a = A.agents.find(x => x.id === A.agent);
    if (!a) return '';
    // 에이전트의 도구는 서버 이름이다(neo4j · hyd-dmn · 학생 서버) — 도구 id 용 UI.toolName 은 「도구 표시 이름 미등록」을 보였다(2026-10-25 수업 한 바퀴).
    // 기본 서버는 사람 이름으로, 학생이 지은 서버 이름은 그대로 보인다
    const serverLabel = t => hydWords.serverName(t);
    const tools = a.tools.length ? a.tools.map(t => UI.chipText(serverLabel(t), 'neutral')).join(' ') : UI.chipText('도구 전부', 'neutral');
    return `<p class="field-hint">${esc(a.goal || a.role || '')}</p><div class="row-wrap ask-tools">${tools}${a.skills.length ? ' ' + a.skills.map(x => UI.chipText(x, 'accent')).join(' ') : ''}</div>`;
  }
  function resultHtml(v) {
    const r = v.result;
    if (!r) return '';
    if (r.kind === 'answered') {
      const ev = (r.evidence || []).map(e => `<li>${UI.chipText(e.verified ? '실행 기록에서 확인됨' : '실행 기록에 없음', e.verified ? 'success' : 'warning')} <b>${esc(UI.toolName(e.tool))}</b>
          <div class="ask-query"><code>${esc(UI.clean(e.query))}</code></div>${e.result != null ? `<div class="muted">에이전트 요약: ${esc(window.hydTrace ? hydTrace.outBrief(e.result, 200) : String(e.result))}</div>` : ''}
          <div class="muted">실제 조회 결과: ${esc(e.actual_result || '원문 없음')}</div>
          ${e.result_check ? `<p class="field-hint">${esc(e.result_check.note)}${e.result_check.missing?.length ? `: ${esc(e.result_check.missing.join(', '))}` : ''}</p>` : ''}</li>`).join('');
      return `<div class="ask-answer"><p>${esc(UI.clean(r.answer))}</p>
        <div class="card-chips">${UI.chipText(`조회 기록 ${r.verified}개 확인`, 'neutral')} ${UI.chipText(`성공한 조회 ${r.queried}건`, 'neutral')}</div>
        ${r.answer_check ? `<p class="field-hint">${esc(r.answer_check.note)}${r.answer_check.missing?.length ? `: ${esc(r.answer_check.missing.join(', '))}` : ''}</p>` : ''}</div>`
        + UI.fold(`근거 — 실행한 질의 · 조회 결과 <span class="chip tone-neutral sm">${(r.evidence || []).length}</span>`, `<ol class="stack-list">${ev}</ol>`
          + (r.note ? `<p class="field-hint">고른 근거: ${esc(UI.clean(r.note))}</p>` : ''), { cls: 'small' });
    }
    return `<div class="ask-answer warn" role="status"><p>${UI.chipText('답할 수 없음', 'warning')} ${esc(UI.clean(r.reason || '이유가 기록되지 않았습니다'))}</p>
      <p class="muted">${r.by === 'server' ? '에이전트가 낸 답을 실제 도구 호출 기록과 대조했지만 근거를 찾지 못했습니다.' : '에이전트가 조회해 보고 답할 수 없다고 했습니다.'}</p></div>`
      + (r.claimed ? UI.fold('에이전트가 낸 답 (근거 확인 안 됨)', `<p>${esc(UI.clean(r.claimed))}</p>`, { cls: 'small' }) : '');
  }
  // the agent's work as a live trace (one work item, flat rows) — fed by GET /api/todolist/{id} and the SSE bus
  function ensureTrace(v) {
    if (!window.hydTrace || !v.workitem) return null;
    if (A.traceWid === v.workitem && A.traceErr) return null;     // 처리 과정을 못 읽은 질문 — 다른 질문을 열면 다시 읽는다
    if (A.traceWid !== v.workitem) {
      A.traceErr = '';
      A.traceWid = v.workitem; A.item = null;
      A.traceHost = document.createElement('div'); A.traceHost.className = 'ask-trace';
      A.trace = hydTrace.mount(A.traceHost, { flat: true, workitem: () => A.traceWid, detachedOk: true });
      loadItem();
    }
    return A.trace;
  }
  async function loadItem() {
    const wid = A.traceWid; if (!wid) return;
    // 처리 과정을 못 읽으면 빈 접기로 두지 않는다 — 처리 과정 자리를 버리고 질문이 가진 도구 호출 목록 + 사유 한 줄로 그린다
    try { const item = await getJ(API.process + '/api/todolist/' + encodeURIComponent(wid)); if (wid === A.traceWid) { A.item = item; A.traceErr = ''; feed(); } }
    catch (e) { if (wid === A.traceWid) { A.traceErr = e.message; A.traceHost = null; A.trace = null; render(); } }
  }
  function feed() {
    if (!A.trace || !A.item || !A.cur) return;
    hydTrace.TR.mounted.add(A.trace);
    A.trace.update({ instance: { status: LIVE.has(A.cur.state) ? 'RUNNING' : 'COMPLETED' }, definition: { activities: [] }, workitems: [A.item], events: A.item.events || [] });
  }
  function callRow(c) {
    const tone = c.running ? 'accent' : c.ok ? 'success' : c.ok === false ? 'danger' : 'neutral';
    const label = c.running ? '실행 중' : c.ok ? '성공' : c.ok === false ? '실패' : '끝';
    return `<li>${UI.chipText(label, tone)} <b>${esc(toolName(c))}</b> <span class="muted">${esc(UI.clean(c.input_text || ''))}</span>${c.problem ? `<div class="neg">${esc(UI.clean(c.problem))}</div>` : ''}</li>`;
  }
  function threadHtml(staticCalls) {
    const v = A.cur;
    if (!v) return replay() ? UI.empty('강의에서 다룬 질문을 골라 보내세요', '이 PC는 강의 때 강사가 저장한 답을 보여 줍니다. 위의 질문 단추를 누르면 질문 칸에 들어갑니다.')
      : UI.empty('질문을 적고 보내세요', '예: 완제품 재고가 가장 적은 설비와 그 수량은? · HYD-01 팬 진동 최근 최대값은? · 어떤 규칙이 지금 성립하나?');
    const [label, tone] = STATE[v.state] || [v.state, 'neutral'];
    const live = LIVE.has(v.state);
    const calls = v.tool_calls || [];
    return `<div class="ask-thread">
      <div class="ask-q"><div class="ask-bubble">${esc(v.question)}</div><span class="muted">${esc(v.asked_by || '')} · ${esc(UI.dateTime(v.started))}</span></div>
      <div class="ask-a card">
        <div class="ask-a-head"><span class="tr-block k-agent${live ? ' live' : ''}">${window.hydTrace ? hydTrace.icon('agent') : ''}</span><b>${esc(v.agent ? v.agent.name : '')}</b>${UI.chipText(label, tone)}
          <span class="muted">${esc(UI.clean(v.message || ''))}</span><span class="ask-count">${window.hydTrace ? hydTrace.icon('tool') : ''}${calls.length}</span></div>
        <details class="fold small ask-process" ${live || A.processOpen ? 'open' : ''}><summary>처리 과정 · 도구 호출 ${calls.length} ${live && window.hydTrace ? hydTrace.spinner('sm') : ''}</summary><div class="fold-body">${A.traceErr ? `<p class="field-hint">자세한 처리 과정을 읽지 못해 도구 호출 목록만 보입니다 — ${esc(A.traceErr)}</p>` : ''}<div data-ask-trace>${staticCalls ? `<ol class="stack-list">${calls.map(callRow).join('')}</ol>` : ''}</div></div></details>
        ${resultHtml(v)}
        ${v.state==='failed' && !replay() ? UI.field({label:'다시 진행할 때 반영할 내용(선택)',input:`<textarea id="askRetryNote" rows="2" maxlength="1000">${esc(A.retryNote || '')}</textarea>`}) : ''}
        <div class="form-actions">${v.state==='failed' && !replay() ? `<button class="btn small" id="askRetry" ${A.sending?'disabled':''}>같은 질문 다시 진행</button>` : ''}<a class="btn small ghost" href="${esc(v.link)}">처리 과정 보기 →</a></div></div></div>`;
  }
  function historyHtml() {
    if (A.histErr) return `<p class="neg">${esc('지난 질문을 읽지 못했습니다: ' + A.histErr)}</p>`;
    if (!A.history.length) return '<p class="muted">아직 질문이 없습니다.</p>';
    const kind = h => h.verdict === 'answered' ? UI.chipText('답함', 'success') : h.verdict === 'unanswerable' ? UI.chipText('답할 수 없음', 'warning')
      : UI.chipText((STATE[h.state] || [h.state])[0], (STATE[h.state] || [0, 'neutral'])[1]);
    return `<div class="list ask-history">${A.history.map(h => `<button type="button" class="item${A.cur && A.cur.id === h.id ? ' sel' : ''}" data-ask-open="${esc(h.id)}"><div class="row"><strong>${esc(h.question)}</strong>${kind(h)}</div>
      <span class="sub">${esc(h.agent ? h.agent.name : '')} · 도구 ${h.calls}건 · ${esc(UI.dateTime(h.started))}</span></button>`).join('')}</div>`
      + `<div class="form-actions"><button type="button" class="btn small" id="askReset">끝난 질문 기록 지우기</button></div>`;
  }
  function formHtml() {
    return `<header class="card-head"><div class="card-title"><h3>에이전트에게 질문하기</h3></div><div class="card-actions">${readyHtml()}</div></header>
        <div class="form-grid">${UI.field({ label: '답할 에이전트', input: `<select id="askAgent">${agentOptions()}</select>` })}</div>${agentLine()}
        <div class="ask-input">${UI.field({ label: '질문', hint: replay() ? '이 PC는 강의에서 다룬 질문에만 강사가 저장한 답으로 답합니다. 아래 질문을 눌러 넣고 보내세요.'
          : 'Enter 보내기 · Shift+Enter 줄바꿈. 에이전트는 자기 도구로 실제 조회한 결과만으로 답합니다.', input: `<textarea id="askText" rows="3" maxlength="1000"></textarea>` })}${replay() ? picks() : ''}</div>
        <div class="form-actions"><button class="btn primary" id="askSend" ${A.sending || !A.draft.trim() ? 'disabled' : ''}>${A.sending ? '보내는 중…' : '보내기'}</button></div>`;
  }
  const layout = (form, err, thread, hist) => `<div class="ask-layout"><div class="ask-main"><section class="card ask-compose" data-ask-form>${form}</section><div data-ask-err>${err}</div><div data-ask-thread>${thread}</div></div>
        <aside class="ask-side"><h2 class="sec">지난 질문</h2><div data-ask-history>${hist}</div></aside></div>`;
  function render() {
    if (!A.el) return;
    if (!A.el.querySelector('[data-ask-form]')) {
      A.el.innerHTML = layout('', '', '', '');
      if (!A.el.querySelector('[data-ask-form]')) {      // no live DOM (node 시험): one static page
        A.el.innerHTML = layout(formHtml(), A.err ? `<p class="neg" role="status">${esc(A.err)}</p>` : '', threadHtml(true), historyHtml()); return;
      }
    }
    const form = A.el.querySelector('[data-ask-form]');
    const formSig = JSON.stringify([A.status, A.statusErr, A.agents.map(a => a.id), A.agent, A.sending]);
    if (form._sig !== formSig) {
      form._sig = formSig;
      form.innerHTML = formHtml();
      const t = form.querySelector('#askText'); t.value = A.draft;
      wireForm(form);
    } else { const b = form.querySelector('#askSend'); if (b) b.disabled = A.sending || !A.draft.trim(); }
    A.el.querySelector('[data-ask-err]').innerHTML = A.err ? `<p class="neg" role="status">${esc(A.err)}</p>` : '';
    const thread = A.el.querySelector('[data-ask-thread]');
    const v = A.cur, trace = v ? ensureTrace(v) : null;
    const proc = thread.querySelector('.ask-process'); if (proc) A.processOpen = proc.open;
    const tSig = JSON.stringify(v && [v.id, v.state, v.message, (v.tool_calls || []).length, v.result, (v.agent || {}).name, A.sending, A.traceErr]);
    if (thread._sig !== tSig) {
      thread._sig = tSig;
      thread.innerHTML = threadHtml(!A.traceHost);
      const slot = thread.querySelector('[data-ask-trace]'); if (slot && A.traceHost) slot.replaceWith(A.traceHost);
      thread.querySelector('.ask-process')?.addEventListener('toggle', e => { A.processOpen = e.target.open; });
      thread.querySelector('#askRetry')?.addEventListener('click',retry);
    }
    if (trace) feed();
    const hist = A.el.querySelector('[data-ask-history]');
    const hSig = JSON.stringify([A.history, A.histErr, A.cur && A.cur.id]);
    if (hist._sig !== hSig) {
      hist._sig = hSig; hist.innerHTML = historyHtml();
      hist.querySelectorAll('[data-ask-open]').forEach(b => b.addEventListener('click', () => open(b.dataset.askOpen)));
      hist.querySelector('#askReset')?.addEventListener('click', reset);
    }
  }
  function wireForm(form) {
    const q = s => form.querySelector(s);
    q('#askAgent')?.addEventListener('change', e => { A.agent = e.target.value; render(); });
    const t = q('#askText');
    t?.addEventListener('input', e => { A.draft = e.target.value; const b = q('#askSend'); if (b) b.disabled = A.sending || !A.draft.trim(); });
    t?.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); } });
    q('#askSend')?.addEventListener('click', send);
    form.querySelectorAll('[data-ask-pick]').forEach(b => b.addEventListener('click', () => {
      A.draft = b.dataset.askPick; t.value = A.draft; t.focus(); const s = q('#askSend'); if (s) s.disabled = A.sending;
    }));
  }

  // 셸이 처음 열 때 mount, 다시 열 때 show
  window.hydAsk = { mount, show, _state: A, _render: render };
})();
