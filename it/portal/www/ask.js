/* B5 에이전트에게 질문하기 — window.hydAsk.mount(el). 주소 #/ask
   질문 하나 = 처리 건 하나(정식 정의 ask_agent). 답할 에이전트를 고르고 보내면, 에이전트가 무엇을 읽고 불렀는지가 실시간 상자에 한 줄씩 붙고
   (디자인 기준 7절 — hydLive.agentWork: 도구 호출이 생기는 대로, 연결이 끊긴 동안만 다시 묻는다), 끝나면 그 자리에 답이 온다:
   답(결론) → 근거(실행한 질의 · 조회 결과 · 실행 기록에서 확인됐는지) → 처리 과정(접기) 또는 「답할 수 없음 + 이유」, 그리고 「처리 건에서 보기」.
   한 질문 → 한 답(이전 질문을 기억하지 않음). 서버: process GET/POST /api/ask* (it/process/procsvc/ask.py).
   짜임: 왼쪽에 질문 칸(답할 에이전트 → 질문 → [보내기])과 그 아래 질문 · 답, 오른쪽에 지난 질문 목록.
   원본 대응: process-gpt-vue3 ui/WorkItemChat.vue(도구 입력 · 결과 접기), apps/todolist/InstanceTimeline.vue(작업 하나 = 메시지 하나). */
(function () {
  const LIVE = new Set(['waiting', 'running', 'submitted', 'correcting', 'asking']);
  const STATE = { waiting: ['대기 중', ''], running: ['조회 중', 'brand'], submitted: ['정리 중', 'brand'], correcting: ['답 형식 확인 중', 'warn'],
    asking: ['사람에게 질문', 'warn'], done: ['답변 완료', 'ok'], failed: ['실패', 'danger'], closed: ['종료', ''], broken: ['오류', 'danger'] };
  const A = { el: null, status: null, statusErr: '', agents: [], agent: '', wanted: '', wantedMiss: '', draft: '', sending: false, err: '', cur: null, history: [], timer: null, histErr: '',
    work: null, workHost: null, workFor: null, processOpen: false, retryNote: '', retryId: null };
  const api = path => API.process + '/api/ask' + path;
  const uuid = () => UI.uuid();   // 비보안 문맥(IP 주소로 연 포털)에서도 같은 공용 생성기
  const icon = (name, cls) => UI.icon(name, cls);
  const tag = (label, tone) => `<span class="tag"${tone ? ` data-tone="${tone}"` : ''}>${esc(label)}</span>`;
  const alertBox = (name, title, body, variant) => `<div class="alert"${variant ? ` data-variant="${variant}" role="alert"` : ' role="status"'}>${icon(name)}<h2>${esc(title)}</h2>${body ? `<section>${body}</section>` : ''}</div>`;
  // AI 키 없이 도는 재생 모드: 저장된 답이 있는 질문에만 답한다 — 그 질문을 예시 단추로 보이고, 다시 진행은 같은 거절이라 숨긴다
  const replay = () => A.status?.worker?.ai_mode === 'replay';
  const recorded = () => A.status?.worker?.replay_questions || [];
  const picks = () => recorded().length ? `<div class="ask-picks"><p class="muted">지금 답할 수 있는 질문 — 누르면 질문 칸에 들어갑니다</p><div class="chips">${recorded().map(q => `<button type="button" class="chip" data-ask-pick="${esc(q)}">${esc(q)}</button>`).join('')}</div></div>` : '';

  async function loadStatus() {
    try {
      A.status = await getJ(api('/status')); A.statusErr = '';
      A.agents = A.status.agents || [];
      // 다른 화면(에이전트의 [시험해 보기])이 고른 에이전트가 있으면 그 에이전트로. 질문에 답할 수 없는 에이전트면 그 사실을 말하고 기본 에이전트로 둔다
      if (A.wanted) { const id = A.wanted; A.wanted = ''; if (A.agents.some(a => a.id === id)) { A.agent = id; A.wantedMiss = ''; } else A.wantedMiss = UI.who(id); }
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
      A.cur = await postJ(api(''), { question: q, agent: A.agent || null, by: ((window.hydInbox && window.hydInbox.me && window.hydInbox.me()) || {}).name || '', request_id: uuid() });
      A.draft = ''; const t = A.el.querySelector('#askText'); if (t) t.value = '';
      poll();
      loadHistory().then(render);
    } catch (e) { A.err = e.message; }
    finally { A.sending = false; render(); }
  }
  async function open(id) {
    if (A.cur?.id !== id) { A.retryNote = ''; A.retryId = null; A.processOpen = false; }
    try { A.cur = await getJ(api('/' + encodeURIComponent(id))); A.err = ''; poll(); }
    catch (e) { A.err = '질문을 읽지 못했습니다: ' + e.message; }
    render();
    const thread = A.el.querySelector('[data-ask-thread]'); if (thread && A.cur) thread.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }
  async function retry() {
    if (!A.cur || A.cur.state !== 'failed' || A.sending) return;
    A.retryNote = A.el.querySelector('#askRetryNote')?.value || A.retryNote || '';
    A.sending = true; A.err = ''; render();
    A.retryId = A.retryId || uuid();
    try {
      A.cur = await postJ(api('/' + encodeURIComponent(A.cur.id) + '/retry'),
        { request_id: A.retryId, by: A.cur.asked_by, reason: A.retryNote.trim() || '연결 상태 확인 후 같은 질문을 다시 진행합니다.' });
      A.retryId = null; poll(); loadHistory().then(render);
    } catch (e) { A.err = e.message; }
    finally { A.sending = false; render(); }
  }
  // 질문의 상태(대기 → 조회 → 정리 → 끝)는 1.5초마다 다시 읽는다. 도구 호출 줄은 실시간 연결(hydLive.agentWork)로 온다
  async function refresh() {
    if (!A.cur) return;
    try {
      const was = A.cur.state, id = A.cur.id;
      const next = await getJ(api('/' + encodeURIComponent(id)));
      if (!A.cur || A.cur.id !== id) return;
      A.cur = next;
      if (was !== A.cur.state && !LIVE.has(A.cur.state)) loadHistory().then(render);
    } catch (e) { A.err = '진행 상황을 읽지 못했습니다: ' + e.message; }
    render();
  }
  function poll() {
    clearTimeout(A.timer);
    if (!A.cur || !LIVE.has(A.cur.state)) return;
    A.timer = setTimeout(async () => {
      const view = document.getElementById('view-ask');
      if (view && !view.classList.contains('active')) { poll(); return; }           // 화면을 떠나 있으면 읽지 않고 기다린다
      await refresh(); poll();
    }, 1500);
  }
  async function reset() {
    const ok = await UI.confirm({ title: '끝난 질문 기록을 지울까요?', body: '끝난 질문 기록을 목록에서 지웁니다. 질문 정의 · 에이전트 · 업무 DB · 지식은 그대로입니다.', ok: '지우기', danger: true });
    if (!ok) return;
    try { const r = await postJ(api('/reset'), {}); UI.toast(r.note, { tone: 'ok' }); if (A.cur && !LIVE.has(A.cur.state)) A.cur = null; }
    catch (e) { A.err = '지우지 못했습니다: ' + e.message; }
    await loadHistory();
    // 서버는 처리 건이 끝난 질문만 지운다. 화면에는 「실패」인데 처리 건이 아직 끝나지 않은 질문은 남는다 — 지워진 것처럼 보이지 않게 그 사실을 말한다
    const left = A.history.filter(h => !LIVE.has(h.state)).length;
    A.keptNote = left ? `질문 ${left}건은 지워지지 않았습니다. 처리 건이 아직 끝나지 않은 질문입니다 — 그 질문을 열어 [처리 건에서 보기]로 확인하세요.` : '';
    render();
  }

  /* ---------------------------------------------------------------- 그리기
     A161-U1: 질문 칸은 한 번만 그리고(입력 중에 다시 그려 글자 · 초점을 잃지 않게), 질문 · 답 부분만 갱신한다. */
  function readyHtml() {
    if (A.statusErr) return UI.errorBlock('질문 기능의 상태를 읽지 못했습니다', A.statusErr, { retry: true });
    const s = A.status;
    if (!s) return UI.loading('');
    const miss = A.wantedMiss ? alertBox('info', `「${A.wantedMiss}」에게는 질문할 수 없습니다`, '질문에 답할 수 있게 설정된 에이전트가 아닙니다. 아래에서 다른 에이전트를 고르세요.') : '';
    if (s.ready) return miss;      // 준비됐으면 따로 말하지 않는다 — 안 될 때만 까닭을 보인다
    return miss + alertBox('triangle-alert', '지금은 답할 AI 에이전트가 없습니다', esc(s.reason || ''));
  }
  function agentOptions() {
    return A.agents.map(a => `<option value="${esc(a.id)}" ${a.id === A.agent ? 'selected' : ''}>${esc(a.name)}${a.default ? ' (기본)' : a.mine ? ' (내가 만든 것)' : ''}</option>`).join('');
  }
  // 고른 에이전트가 무엇을 하고 질문에 어떤 도구 서버 · 스킬을 쓰는지 한 줄씩
  function agentLine() {
    const a = A.agents.find(x => x.id === A.agent);
    if (!a) return '';
    // 질문에 실제로 연결하는 도구 서버(서버 계산 a.servers — 질문용 조회 도구가 있는 서버만, AI 에이전트 실행 서비스와 같은 규칙)와 질문에는 쓰지 않는 서버(a.left_out)
    const serverLabel = t => hydWords.serverName(t);
    const rows = [[a.goal || a.role ? '하는 일' : '', esc(a.goal || a.role || '')],
      ['질문에 쓰는 도구 서버', a.servers.length ? a.servers.map(t => esc(serverLabel(t))).join(', ') : ''],
      ['스킬', a.skills.length ? a.skills.map(esc).join(', ') : ''],
      ['질문에는 쓰지 않는 도구 서버', a.left_out.length ? a.left_out.map(t => esc(serverLabel(t))).join(', ') + ' <span class="muted">— 질문용 조회 도구가 없습니다</span>' : '']].filter(([k, v]) => k && v);
    return (rows.length ? `<dl class="kv ask-agent">${rows.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${v}</dd>`).join('')}</dl>` : '') +
      (a.servers.length ? '' : alertBox('triangle-alert', '이 에이전트에는 질문에 쓸 도구 서버가 없습니다', '조회할 도구가 없어 답할 수 없습니다. 다른 에이전트를 고르거나, 에이전트 · 스킬 화면에서 이 에이전트에 도구 서버를 붙이세요.'));
  }
  // 답(결론) → 근거. 답할 수 없으면 그 이유가 답 자리에 온다
  function resultHtml(v) {
    const r = v.result;
    if (!r) return '';
    if (r.kind === 'answered') {
      const check = c => c ? `<p class="muted">${esc(c.note)}${c.missing?.length ? `: ${esc(c.missing.join(', '))}` : ''}</p>` : '';
      const ev = (r.evidence || []).map(x => `<li>${icon(x.verified ? 'circle-check' : 'triangle-alert')}<div><p><b>${esc(UI.toolName(x.tool))}</b> — ${x.verified ? '실행 기록에서 확인됨' : '실행 기록에 없음'}</p>
          ${x.result != null ? `<p class="muted">에이전트 요약: ${esc(window.hydTrace ? hydTrace.outBrief(x.result, 200) : String(x.result))}</p>` : ''}
          ${check(x.result_check)}${UI.raw(UI.clean(x.query), { title: '조회문', lang: /\bMATCH\b/i.test(x.query || '') ? 'cypher' : /\bSELECT\b/i.test(x.query || '') ? 'sql' : '' })}${x.actual_result ? UI.raw(x.actual_result, { title: '실제 조회 결과' }) : '<p class="muted">실제 조회 결과 원문이 남아 있지 않습니다.</p>'}</div></li>`).join('');
      return `<div class="result"><div class="result-label">답</div><div class="prose ask-answer" data-md="${esc(UI.clean(r.answer))}"></div>${check(r.answer_check)}</div>`
        + `<details class="fold" open><summary>근거<span class="muted">실행 기록과 맞은 근거 ${esc(r.verified)}건 · 성공한 조회 ${esc(r.queried)}건</span></summary><div class="fold-body">`
        + (ev ? `<ul class="evid ask-evid">${ev}</ul>` : '<p class="muted">근거로 적은 질의가 없습니다.</p>') + (r.note ? `<p class="muted">고른 근거: ${esc(UI.clean(r.note))}</p>` : '') + '</div></details>';
    }
    return `<div class="result">${alertBox('triangle-alert', '답할 수 없음', esc(UI.clean(r.reason || '이유가 기록되지 않았습니다')) +
      `<p class="muted">${r.by === 'server' ? '에이전트가 낸 답을 실제 도구 호출 기록과 대조했지만 근거를 찾지 못했습니다.' : '에이전트가 조회해 보고 답할 수 없다고 했습니다.'}</p>`)}</div>`
      + (r.claimed ? UI.fold('에이전트가 낸 답<span class="muted">근거 확인 안 됨</span>', `<div class="prose" data-md="${esc(UI.clean(r.claimed))}"></div>`) : '');
  }
  // 에이전트가 하는 일의 실시간 상자(hydLive.agentWork) — 질문마다 하나. 도는 동안은 답 자리에 그대로 보이고, 끝나면 「처리 과정」 접기 안으로 들어간다
  function workOf(v) {
    if (!v.workitem) return null;
    if (A.workFor !== v.workitem) {
      if (A.work) A.work.stop();
      A.workFor = v.workitem;
      A.workHost = document.createElement('div'); A.workHost.className = 'ask-work';
      A.work = hydLive.agentWork(A.workHost, { tab: 'ask', onChange: () => { if (A.cur && LIVE.has(A.cur.state)) refresh(); } });
    }
    const live = LIVE.has(v.state), [label] = STATE[v.state] || [v.state], who = v.agent ? v.agent.name : 'AI 에이전트';
    A.work.set({ items: [{ id: v.workitem, instance: v.id, state: live ? 'run' : v.state === 'done' ? 'done' : 'fail' }], running: live, since: v.started,
      headline: live ? `${who}${window.hydWords.josa(who, '이/가')} 일하는 중 — ${label}` : `${who}의 처리 과정`, note: '' });
    return A.workHost;
  }
  function threadHtml() {
    const v = A.cur;
    if (!v) return `${UI.empty({ icon: 'message-circle-question', title: `아직 보낸 질문이 없습니다`, sub: `${replay() ? '위의 질문 단추를 누르면 질문 칸에 들어갑니다. [보내기]를 누르면 에이전트가 조회하는 과정과 답이 여기에 나옵니다.'
      : '위 칸에 질문을 적고 [보내기]를 누르면 에이전트가 조회하는 과정과 답이 여기에 나옵니다. 예: 완제품 재고가 가장 적은 설비와 그 수량은? · HYD-01 팬 진동 최근 최대값은?'}` })}`;
    const [label, tone] = STATE[v.state] || [v.state, ''];
    const live = LIVE.has(v.state), calls = (v.tool_calls || []).length;
    // 차례: 질문 → 누가 · 상태 → (도는 동안) 실시간 상자 / (끝난 뒤) 답 → 근거 → 처리 과정(접기)
    // 처리 건의 단계가 이미 열려 실시간 상자가 과정을 보이는 동안에는 서버의 「아직 질문을 맡지 않았습니다」(상태 waiting 의 글)를 함께 적지 않는다 — 상자가 지금 일어나는 일을 말한다
    return `<div class="ask-q"><div class="ask-bubble">${esc(v.question)}</div><span class="muted">${esc(v.asked_by || '')} · ${esc(UI.dateTime(v.started))}</span></div>
      <section class="panel ask-a">
        <div class="panel-head pane-head"><span class="pane-ic" data-kind="agent">${icon('bot')}</span><div class="pane-title"><h2>${esc(v.agent ? v.agent.name : 'AI 에이전트')}${tag(label, tone)}</h2></div>
          <div class="pane-acts"><a class="btn" data-variant="outline" data-size="sm" href="${esc(v.link)}">처리 건에서 보기${icon('arrow-right')}</a></div></div>
        <div class="panel-sec ask-body">
          ${live ? `<div data-ask-work>${v.workitem ? '' : hydLive.waitHtml('에이전트가 질문을 받는 중', { since: v.started, hint: '처리 건이 열리고 에이전트가 일을 시작하면 조회 과정이 여기에 한 줄씩 붙습니다.' })}</div>${v.message && !(v.state === 'waiting' && v.workitem) ? `<p class="typing">${esc(UI.clean(v.message))}</p>` : ''}` : ''}
          ${!live && v.state === 'failed' ? alertBox('circle-alert', '답을 받지 못했습니다', esc(UI.clean(v.message || '에이전트 실행이 실패했습니다.')), 'destructive') : ''}
          ${!live && v.state !== 'failed' && !v.result && v.message ? `<p class="muted">${esc(UI.clean(v.message))}</p>` : ''}
          ${resultHtml(v)}
          ${!live && v.workitem ? `<details class="fold ask-process" ${A.processOpen ? 'open' : ''}><summary>처리 과정<span class="muted">도구 호출 ${calls}건</span></summary><div class="fold-body"><div data-ask-work></div></div></details>` : ''}
          ${v.state === 'failed' && replay() ? alertBox('info', '같은 질문을 다시 진행할 수 없습니다', 'AI 키가 없을 때 쓰는 재생 모드에서는 저장된 답이 있는 질문에만 답합니다. 위의 질문 단추에 있는 질문을 보내 보세요.') : ''}
          ${v.state === 'failed' && !replay() ? UI.field({ label: '다시 진행할 때 반영할 내용(선택)', input: `<textarea id="askRetryNote" rows="2">${esc(A.retryNote || '')}</textarea>` }) +
            `<footer class="form-foot"><button type="button" class="btn" data-variant="outline" id="askRetry" ${A.sending ? 'disabled' : ''}>${icon('rotate-ccw')}같은 질문 다시 진행</button></footer>` : ''}
        </div></section>`;
  }
  function historyHtml() {
    if (A.histErr) return `<div class="pane-list-note">${UI.errorBlock('지난 질문을 읽지 못했습니다', A.histErr, { retry: true })}</div>`;
    if (!A.history.length) return `<div class="pane-list-note">${UI.empty('아직 질문이 없습니다', '질문을 보내면 여기에 쌓이고, 누르면 그 답을 다시 볼 수 있습니다.')}</div>`;
    const kind = h => h.verdict === 'answered' ? tag('답함', 'ok') : h.verdict === 'unanswerable' ? tag('답할 수 없음', 'warn') : tag((STATE[h.state] || [h.state])[0], (STATE[h.state] || [0, ''])[1]);
    return A.history.map(h => `<button type="button" class="row" data-ask-open="${esc(h.id)}"${A.cur && A.cur.id === h.id ? ' aria-current="true"' : ''}><span class="row-ic">${icon('message-square')}</span><span class="row-title">${esc(h.question)}</span>${kind(h)}
      <span class="row-meta">${esc(h.agent ? h.agent.name : '')} · ${esc(UI.dateTime(h.started))}</span></button>`).join('');
  }
  function formHtml() {
    const off = A.sending || !A.draft.trim();
    return `<div class="panel-sec ask-compose">${readyHtml()}
        ${UI.field({ label: '답할 에이전트', input: `<select id="askAgent">${agentOptions()}</select>` })}${agentLine()}
        ${UI.field({ label: '질문', input: `<textarea id="askText" rows="3" maxlength="${esc(window.hydCourseAccess.questionMaxChars || '')}" placeholder="에이전트가 자기 도구로 조회해 답할 수 있는 것을 묻습니다 (Enter 보내기 · Shift+Enter 줄바꿈)"></textarea>` })}${replay() ? picks() : ''}
        <footer class="form-foot"><span class="muted" role="status" data-ask-why></span><button type="button" class="btn" id="askSend" ${off ? 'disabled' : ''}>${icon('send')}보내기</button></footer></div>`;
  }
  const layout = () => `<div class="ask-layout"><div class="ask-main"><section class="panel" data-ask-form aria-label="질문 보내기"></section><div data-ask-err class="pane-msg"></div><div class="ask-thread" data-ask-thread></div></div>
        <aside class="ask-side pane-side"><div class="sec-head"><h2>지난 질문</h2><button type="button" class="btn" data-variant="ghost" data-size="sm" id="askReset" hidden>${icon('trash-2')}끝난 기록 지우기</button></div><div class="rows" data-ask-history></div><div data-ask-kept class="pane-msg"></div></aside></div>`;
  async function renderMarkdown(root) {
    const nodes = [...root.querySelectorAll('[data-md]')]; if (!nodes.length) return;
    try { await UI.need('markdown'); nodes.forEach(n => { n.innerHTML = DOMPurify.sanitize(marked.parse(n.dataset.md)); n.removeAttribute('data-md'); }); }
    catch (e) { nodes.forEach(n => { n.textContent = n.dataset.md; n.removeAttribute('data-md'); }); console.error('마크다운 부품을 싣지 못해 글 그대로 보입니다:', e.message); }
  }
  const syncSend = form => {
    const b = form.querySelector('#askSend'), why = form.querySelector('[data-ask-why]');
    if (b) b.disabled = A.sending || !A.draft.trim();
    const q = A.draft.trim();
    if (why) why.textContent = !q ? ''
      : replay() && recorded().length && !recorded().includes(q) ? 'AI 키가 없을 때 쓰는 재생 모드에서는 위의 질문에만 답합니다. 이 질문은 보내도 답을 받지 못합니다.' : '';
  };
  function render() {
    if (!A.el) return;
    if (!A.el.querySelector('[data-ask-form]')) {
      A.el.innerHTML = layout();
      A.el.querySelector('#askReset').addEventListener('click', reset);
      A.el.querySelector('[data-ask-history]').addEventListener('click', e => {
        const row = e.target.closest('[data-ask-open]');
        if (row) open(row.dataset.askOpen); else if (e.target.closest('[data-retry]')) loadHistory().then(render);
      });
    }
    const form = A.el.querySelector('[data-ask-form]');
    const formSig = JSON.stringify([A.status, A.statusErr, A.agents.map(a => a.id), A.agent, A.sending, A.wantedMiss]);
    if (form._sig !== formSig) {
      form._sig = formSig;
      form.innerHTML = formHtml();
      const t = form.querySelector('#askText'); if (t) t.value = A.draft;
      wireForm(form);
    } else syncSend(form);
    A.el.querySelector('[data-ask-err]').innerHTML = A.err ? UI.errorBlock('질문을 처리하지 못했습니다', A.err) : '';
    const thread = A.el.querySelector('[data-ask-thread]');
    const v = A.cur, host = v ? workOf(v) : null;
    const proc = thread.querySelector('.ask-process'); if (proc) A.processOpen = proc.open;
    const tSig = JSON.stringify([replay(), v && [v.id, v.state, v.message, (v.tool_calls || []).length, v.result, (v.agent || {}).name, v.workitem, A.sending]]);
    if (thread._sig !== tSig) {
      thread._sig = tSig;
      thread.innerHTML = threadHtml();
      const slot = thread.querySelector('[data-ask-work]'); if (slot && host) slot.replaceWith(host);
      thread.querySelector('.ask-process')?.addEventListener('toggle', e => { A.processOpen = e.target.open; });
      thread.querySelector('#askRetry')?.addEventListener('click', retry);
      renderMarkdown(thread);
    }
    const hist = A.el.querySelector('[data-ask-history]');
    const hSig = JSON.stringify([A.history, A.histErr, A.cur && A.cur.id]);
    if (hist._sig !== hSig) { hist._sig = hSig; hist.innerHTML = historyHtml(); }
    A.el.querySelector('#askReset').hidden = !A.history.length;
    A.el.querySelector('[data-ask-kept]').innerHTML = A.keptNote && A.history.length ? alertBox('info', '지워지지 않은 질문이 있습니다', esc(A.keptNote)) : '';
  }
  function wireForm(form) {
    const q = s => form.querySelector(s);
    q('#askAgent')?.addEventListener('change', e => { A.agent = e.target.value; A.wantedMiss = ''; render(); });
    q('[data-retry]')?.addEventListener('click', () => loadStatus().then(render));
    const t = q('#askText');
    t?.addEventListener('input', e => { A.draft = e.target.value; syncSend(form); });
    t?.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); } });
    q('#askSend')?.addEventListener('click', send);
    form.querySelectorAll('[data-ask-pick]').forEach(b => b.addEventListener('click', () => { A.draft = b.dataset.askPick; t.value = A.draft; t.focus(); syncSend(form); }));
  }

  // 셸이 처음 열 때 mount, 다시 열 때 show. prefer(에이전트 id): 다른 화면(에이전트의 [시험해 보기])이 이 화면을 그 에이전트를 고른 채 열 때 부른다
  window.hydAsk = { mount, show, prefer: id => { A.wanted = id; } };
})();
