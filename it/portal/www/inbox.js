/* U5 — 내 작업함 · 포털 안 알림. process 의 instance-mode API 를 읽는다(procsvc/inbox_api.py):
     GET  /api/inbox/users · /api/inbox?user_id= · /api/inbox/notifications?user_id=
     POST /api/inbox/notifications/read · SSE /api/inbox/notifications/stream?user_id=
   HYD 포털에는 로그인이 없고 한 사람이 자기 PC에서 쓴다. 그래서 사람을 고르는 자리가 없다 — 쓰는 사람은 늘 담당자 한 명이고
   (사용자 표의 사람 한 명, 모든 역할의 구성원 — seed.sql · migration 000072), 화면에는 사람 이름이 아니라 그 일을 맡는 역할이 보인다.
   승인할 때는 담당자 id 와 그 단계가 요구하는 역할이 들어가고, 서버가 담당자가 그 역할의 구성원인지 · 역할 등급이 카드 승인 역할
   이상인지 검사한다(아니면 403). 기록에는 승인한 역할이 남는다.
   공개: window.hydInbox.mount(el) — 작업함 화면, unread() — 상단 종(shell.js)이 읽는 안 읽은 알림 수,
         me() — 담당자 행({id, name, roles}), whoFields(prefix, form, roles) · byField(prefix, form) — 승인 · 제출 폼의 역할 · 사유 칸.
         담당자를 읽고 나면 window 에 'hyd:me' 이벤트를 낸다(담당자 id 가 필요한 폼이 다시 그린다). */
(function () {
  const X = { people: null, box: null, notes: [], tab: 'tasks', role: '', es: null, live: 'off', err: '', mounts: [], loading: false, timer: null };

  const roleName = id => UI.who(id);
  const me = () => (X.people || []).find(p => p.id === 'user:me') || null;      // 담당자 행이 없으면 다른 사람으로 대신하지 않는다(loadPeople 이 까닭을 보인다)
  const url = (path, params) => API.process + path + (params ? '?' + new URLSearchParams(params) : '');
  function ago(s) {
    if (s == null) return '–';
    if (s < 60) return '방금';
    if (s < 3600) return `${Math.floor(s / 60)}분 지남`;
    return `${Math.floor(s / 3600)}시간 ${Math.floor((s % 3600) / 60)}분 지남`;
  }

  /* ------------------------------------------------ load */
  async function loadPeople() {
    try { X.people = await getJ(url('/api/inbox/users')); X.err = ''; }
    catch (e) {
      X.people = null;
      X.err = `담당자 정보를 읽지 못했습니다: ${e.message}`;
      return;
    }
    // 사람 이름을 포털 전체의 "누가" 표시에 등록한다(기록이 id 대신 이름으로 보인다)
    X.people.forEach(p => { UI.performers[p.id] = p.name; });
    UI.namesVersion = (UI.namesVersion || 0) + 1;
    if (!me()) { X.err = '사용자 표에 담당자가 없습니다 — 시작 파일을 다시 실행해 업무 DB 를 최신 판으로 맞추세요.'; return; }
    connect();
    window.dispatchEvent(new Event('hyd:me'));   // 담당자가 확인됐다 — 담당자 id 가 필요한 폼이 다시 그린다
  }

  async function refresh() {
    if (X.loading) return; X.loading = true;
    try {
      if (!X.people || !me()) await loadPeople();
      const m = me();
      if (!m) { X.box = null; X.notes = []; render(); return; }
      try {
        const [box, notes] = await Promise.all([getJ(url('/api/inbox', { user_id: m.id })), getJ(url('/api/inbox/notifications', { user_id: m.id, limit: 50 }))]);
        X.box = box; X.notes = notes; X.err = '';
      } catch (e) { X.err = `내 작업함을 읽지 못했습니다: ${e.message}`; }
      render();
    } finally { X.loading = false; }
  }

  /* ------------------------------------------------ SSE: 새 알림 */
  function connect() {
    if (X.es) { X.es.close(); X.es = null; }
    const m = me(); if (!m) { X.live = 'off'; return; }
    const es = new EventSource(url('/api/inbox/notifications/stream', { user_id: m.id }));
    X.es = es; X.live = 'connecting';
    es.onopen = () => { X.live = 'on'; badge(); };
    es.onmessage = () => { clearTimeout(X.timer); X.timer = setTimeout(refresh, 200); };   // 새 알림 → 작업함 · 알림 · 안 읽은 수를 다시 읽는다
    es.onerror = () => {
      if (es.readyState !== EventSource.CLOSED) { X.live = 'connecting'; badge(); return; }
      es.close(); if (X.es === es) X.es = null;
      X.live = 'off'; badge();
      setTimeout(() => { if (!X.es && me()) connect(); }, 15000);
    };
  }

  /* ------------------------------------------------ 이동: #/instances/<id>/task/<taskId> — 주소는 셸(shell.js)이 읽는다 */
  function go(link) {
    if (link) window.hydShell.navigate(link);
  }

  async function markRead(ids) {
    const m = me(); if (!m) return;
    try { await postJ(url('/api/inbox/notifications/read'), ids ? { user_id: m.id, ids } : { user_id: m.id }); }
    catch (e) { X.err = `읽음 처리를 하지 못했습니다: ${e.message}`; }
    await refresh();
  }

  /* ------------------------------------------------ render */
  // 한 줄 = 사람이 처리할 단계 하나. 칩은 그 일을 맡는 역할(단계의 user_id 는 역할 그대로다 — procsvc/inbox.py resolve)
  function taskRow(t) {
    const label = t.kind === 'question' ? `AI 질문 — ${UI.flowName(t.activity_name)}` : UI.flowName(t.activity_name);
    const whom = UI.chipText(roleName(t.user_id), 'neutral');
    const kind = t.kind === 'approve' || t.kind === 'select' ? ' ' + UI.chipText('승인 요청', 'accent') : '';
    const due = t.due_date ? ` · 기한 ${UI.time(t.due_date)}` : '';
    return `<a class="item" href="${esc(t.link)}" data-inbox-link="${esc(t.link)}"><div class="row"><strong>${esc(label)}</strong>${t.kind === 'question' ? UI.chip('HUMAN_ASKED') : whom + kind}</div>
      <span class="sub">${esc(t.proc_inst_name || UI.defName(t.proc_def_id))} · ${esc(ago(t.elapsed_s))}${esc(due)}</span></a>`;
  }

  // 역할별 보기: 전체 + 지금 열린 일이 있는 역할. 「이 일은 어느 역할의 일인가」를 가려 본다(다른 역할로 보면 그 일은 보이지 않는다)
  function roleFilterHtml(tasks) {
    const count = {};
    tasks.forEach(t => { count[t.user_id] = (count[t.user_id] || 0) + 1; });
    const ids = Object.keys(count).sort((a, b) => roleName(a).localeCompare(roleName(b)));
    if (X.role && !ids.includes(X.role)) ids.push(X.role);
    if (ids.length < 2 && !X.role) return '';
    const chip = (id, label, n) => `<button type="button" class="chip-btn${X.role === id ? ' on' : ''}" data-inbox-role="${esc(id)}" aria-pressed="${X.role === id}">${esc(label)} <span class="n">${n}</span></button>`;
    return `<div class="role-filter" role="group" aria-label="역할별 보기">${chip('', '전체', tasks.length)}${ids.map(id => chip(id, roleName(id), count[id] || 0)).join('')}</div>`;
  }

  function tasksHtml() {
    const b = X.box;
    if (!b) return UI.empty('읽는 중…', '', 'compact');
    const shown = X.role ? b.tasks.filter(t => t.user_id === X.role) : b.tasks;
    const rows = [...(X.role ? [] : b.asked), ...shown];
    const list = rows.length ? `<div class="list">${rows.map(taskRow).join('')}</div>`
      : X.role ? UI.empty(`${roleName(X.role)} 역할로 처리할 단계가 없습니다`, '다른 역할의 일은 「전체」에서 볼 수 있습니다', 'compact')
        : UI.emptyGo('지금 처리할 단계가 없습니다', '설비에 경보가 나서 승인이나 입력이 필요해지면 여기에 들어오고 알림이 옵니다', 'scenario', UI.t('nav.scenario'), 'compact');
    return roleFilterHtml(b.tasks) + list;
  }

  function notesHtml() {
    if (!X.notes.length) return UI.empty('알림이 없습니다', '승인이나 입력이 필요한 단계가 열리거나 AI가 질문하거나 처리 건이 끝나면 여기에 쌓입니다.', 'compact');
    const unread = X.notes.filter(n => !n.is_read).length;
    const KIND = { task_assigned: '처리할 단계', workitem_bpm: 'AI 질문', instance_completed: '처리 건 종료' };
    const rows = X.notes.map(n => `<a class="item${n.is_read ? '' : ' unread'}" href="${esc(n.link || '#/inbox')}" data-inbox-note="${esc(n.id)}" data-inbox-link="${esc(n.link || '')}">
      <div class="row"><strong>${esc(n.type === 'task_assigned' ? UI.flowName(n.title) : n.title || '')}</strong>${UI.chipText(KIND[n.type] || '알림', n.is_read ? 'neutral' : 'accent')}</div>
      <span class="sub">${n.is_read ? '' : '안 읽음 · '}${esc(UI.dateTime(n.created_at))}${n.type === 'workitem_bpm' ? '' : n.description ? ' · ' + esc(n.description) : ''}${n.link_error ? ' · ' + esc(n.link_error) : ''}</span></a>`).join('');
    return `<div class="list">${rows}</div>` + UI.actions(`<button class="btn small" data-inbox-readall ${unread ? '' : 'disabled'}>모두 읽음</button>`);
  }

  function render() {
    X.mounts = X.mounts.filter(e => e.isConnected);
    X.mounts.forEach(renderInto);
    badge();
  }

  function renderInto(root) {
    // 담당자 정보를 못 읽으면 작업함을 열 수 없다 — 다시 시도 단추를 두고, 메뉴를 다시 열어도 셸이 새로 읽는다(failed)
    if (X.err && !me()) {
      root.innerHTML = UI.errorBlock('내 작업함을 열 수 없습니다', X.err, { retry: true });
      root.querySelector('[data-retry]')?.addEventListener('click', () => refresh());
      return;
    }
    if (!X.people) { root.innerHTML = UI.empty('읽는 중…', '', 'compact'); return; }
    const unread = (X.box && X.box.unread) || 0;
    const nTasks = X.box ? X.box.tasks.length + X.box.asked.length : null;
    const live = { on: '새 알림 실시간 받는 중', connecting: '실시간 연결 중', off: '실시간 꺼짐 — 화면을 다시 열면 새로 읽습니다' }[X.live];
    root.innerHTML = `<p class="inbox-owner">사람이 승인하거나 입력해야 하는 단계가 여기에 모입니다. 줄마다 그 일을 맡는 역할이 붙어 있습니다.</p>` +
      (X.err ? `<p class="form-msg neg" role="status">${esc(X.err)}</p>` : '') +
      UI.tabs([['tasks', '처리할 단계', nTasks], ['notes', '알림', unread]], X.tab, 'data-inbox-tab') +
      `<div class="inbox-body">${X.tab === 'tasks' ? tasksHtml() : notesHtml()}</div><p class="field-hint" aria-live="polite">${esc(live)}</p>`;
    root.querySelectorAll('[data-inbox-tab]').forEach(b => b.addEventListener('click', () => { X.tab = b.dataset.inboxTab; render(); }));
    root.querySelectorAll('[data-inbox-role]').forEach(b => b.addEventListener('click', () => { X.role = b.dataset.inboxRole; render(); }));
    root.querySelectorAll('[data-inbox-link]').forEach(a => a.addEventListener('click', e => {
      e.preventDefault();
      const note = a.dataset.inboxNote, link = a.dataset.inboxLink;
      if (note && !X.notes.find(n => n.id === note)?.is_read) markRead([note]);
      if (link) go(link);
    }));
    root.querySelector('[data-inbox-readall]')?.addEventListener('click', () => markRead(null));
  }

  const unread = () => (me() && X.box && X.box.unread) || 0;   // 상단 종(shell.js)이 읽는 안 읽은 알림 수(숫자)
  function badge() {
    const n = unread();
    if (X.lastUnread !== n) { X.lastUnread = n; window.dispatchEvent(new Event('hyd:badge')); }   // 종 숫자를 바로 갱신
  }

  function mount(root) {
    if (!root) return;
    if (!X.mounts.includes(root)) X.mounts.push(root);
    renderInto(root);
    refresh();
  }

  /* ------------------------------------------------ 승인 · 제출 폼의 역할 · 사유 칸 (instances.js 가 부른다 — 담당자를 아직 못 읽었으면 null)
     담당자 id 는 폼 상태(form.by)에만 싣고 화면에는 보이지 않는다. 화면에 보이는 것은 승인하는 역할이다. */
  function whoFields(prefix, form, roles, { reasonHint = UI.t('form.hint.reason') } = {}) {
    const m = me(); if (!m) return null;
    form.by = m.id;
    const known = Object.fromEntries(roles || []);
    const name = (known[form.role] && known[form.role].name) || roleName(form.role);
    return UI.section(UI.t('form.section.who'),
      UI.readonly('승인 역할', esc(name), '이 단계를 맡는 역할입니다. 처리 기록에 이 역할로 남습니다') +
      UI.field({ label: UI.t('form.reason'), cls: 'wide', hint: reasonHint, input: `<textarea id="${prefix}Reason" rows="2">${esc(form.reason || '')}</textarea>` }));
  }
  // 제출 · 답변 폼: 보일 칸은 없고 담당자 id 만 폼 상태에 싣는다. 담당자가 있으면 참(빈 표식), 없으면 null
  function byField(prefix, form) {
    const m = me(); if (!m) return null;
    form.by = m.id;
    return '<span hidden data-by-owner></span>';
  }

  const failed = () => !me() && !!X.err;
  window.hydInbox = { mount, failed, unread, me, whoFields, byField, refresh, X };

  async function boot() {
    const root = document.getElementById('inboxView'); if (root) X.mounts.push(root);
    render();
    await refresh();
    setInterval(() => { if (me() && state.tab === 'inbox') refresh(); }, 15000);   // 경과 시간 갱신(새 알림은 SSE 가 바로 부른다)
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
