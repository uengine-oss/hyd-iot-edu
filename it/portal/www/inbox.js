/* U5 — 포털 안 알림 · 담당자. process 의 instance-mode API 를 읽는다(procsvc/inbox_api.py):
     GET  /api/inbox/users · /api/inbox/notifications?user_id= · /api/inbox/notifications/unread-count?user_id=
     POST /api/inbox/notifications/read · SSE /api/inbox/notifications/stream?user_id=
   옛 「내 작업함」 화면은 처리 건 화면으로 합쳤다(2026-11-14 구조 개편). 사람이 처리할 열린 단계는 처리 건 화면의 「내가 할 일」 한 곳이 보이고
   (instances.js — GET /api/todolist 하나로 읽는다. 역할별 보기 · 기한도 그 자리), 이 파일은 그 화면의 「알림」 접기(#noticeView)와 위 막대의 종 숫자,
   그리고 담당자 정보를 맡는다.
   HYD 포털에는 로그인이 없고 한 사람이 자기 PC에서 쓴다. 그래서 사람을 고르는 자리가 없다 — 쓰는 사람은 늘 담당자 한 명이고
   (사용자 표의 사람 한 명, 모든 역할의 구성원 — seed.sql · migration 000072), 화면에는 사람 이름이 아니라 그 일을 맡는 역할이 보인다.
   승인할 때는 담당자 id 와 그 단계가 요구하는 역할이 들어가고, 서버가 담당자가 그 역할의 구성원인지 · 역할 등급이 카드 승인 역할
   이상인지 검사한다(아니면 403). 기록에는 승인한 역할이 남는다.
   공개: window.hydInbox.unread() — 상단 종(shell.js)이 읽는 안 읽은 알림 수, openNotices() — 처리 건 화면의 「알림」 접기를 펼쳐 보인다(종이 부른다),
         me() — 담당자 행({id, name, roles}), whoFields(prefix, form, roles) · byField(prefix, form) — 승인 · 제출 폼의 역할 · 사유 칸.
         담당자를 읽고 나면 window 에 'hyd:me' 이벤트를 낸다(담당자 id 가 필요한 폼이 다시 그린다). */
(function () {
  const X = { people: null, notes: null, unread: 0, es: null, live: 'off', err: '', loading: false, timer: null };

  const roleName = id => UI.who(id);
  const me = () => (X.people || []).find(p => p.id === 'user:me') || null;      // 담당자 행이 없으면 다른 사람으로 대신하지 않는다(loadPeople 이 까닭을 보인다)
  const url = (path, params) => API.process + path + (params ? '?' + new URLSearchParams(params) : '');

  /* ------------------------------------------------ load */
  async function loadPeople() {
    try { X.people = requireList(await getJ(url('/api/inbox/users')), '담당자 목록'); X.err = ''; }      // 목록이 아닌 응답을 그대로 두면 me() 가 다른 화면의 제출에서 터진다
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
      if (!m) { X.notes = null; X.unread = 0; render(); return; }
      try {
        const [notes, count] = await Promise.all([getJ(url('/api/inbox/notifications', { user_id: m.id, limit: 50 })), getJ(url('/api/inbox/notifications/unread-count', { user_id: m.id }))]);
        X.notes = requireList(notes, '알림 목록'); X.unread = Math.max(0, Number(count.unread) || 0); X.err = '';
      } catch (e) { X.err = `알림을 읽지 못했습니다: ${e.message}`; }
      render();
    } finally { X.loading = false; }
  }

  /* ------------------------------------------------ SSE: 새 알림 */
  function connect() {
    if (X.es) { X.es.close(); X.es = null; }
    const m = me(); if (!m) { X.live = 'off'; return; }
    const es = new EventSource(url('/api/inbox/notifications/stream', { user_id: m.id }));
    X.es = es; X.live = 'connecting';
    es.onopen = () => { X.live = 'on'; render(); };
    es.onmessage = () => { clearTimeout(X.timer); X.timer = setTimeout(refresh, 200); };   // 새 알림 → 알림 목록 · 안 읽은 수를 다시 읽는다
    es.onerror = () => {
      if (es.readyState !== EventSource.CLOSED) { X.live = 'connecting'; render(); return; }
      es.close(); if (X.es === es) X.es = null;
      X.live = 'off'; render();
      setTimeout(() => { if (!X.es && me()) connect(); }, 15000);
    };
  }

  async function markRead(ids) {
    const m = me(); if (!m) return;
    try { await postJ(url('/api/inbox/notifications/read'), ids ? { user_id: m.id, ids } : { user_id: m.id }); }
    catch (e) { X.err = `읽음 처리를 하지 못했습니다: ${e.message}`; }
    await refresh();
  }

  /* ------------------------------------------------ render: 처리 건 화면의 「알림」 접기 */
  function notesHtml() {
    if (!X.notes) return X.err ? '' : UI.empty('읽는 중…', '', 'compact');
    if (!X.notes.length) return UI.empty('알림이 없습니다', '승인이나 입력이 필요한 단계가 열리거나 AI가 질문하거나 처리 건이 끝나면 여기에 쌓입니다.', 'compact');
    const KIND = { task_assigned: '처리할 단계', workitem_bpm: 'AI 질문', instance_completed: '처리 건 종료' };
    const rows = X.notes.map(n => `<a class="item${n.is_read ? '' : ' unread'}" href="${esc(n.link || '#/instances')}" data-inbox-note="${esc(n.id)}" data-inbox-link="${esc(n.link || '')}">
      <div class="row"><strong>${esc(n.type === 'task_assigned' ? UI.flowName(n.title) : n.title || '')}</strong>${UI.chipText(KIND[n.type] || '알림', n.is_read ? 'neutral' : 'accent')}</div>
      <span class="sub">${n.is_read ? '' : '안 읽음 · '}${esc(UI.dateTime(n.created_at))}${n.type === 'workitem_bpm' ? '' : n.description ? ' · ' + esc(n.description) : ''}${n.link_error ? ' · ' + esc(n.link_error) : ''}</span></a>`).join('');
    return `<div class="list">${rows}</div>` + UI.actions(`<button class="btn small" data-inbox-readall ${X.unread ? '' : 'disabled'}>모두 읽음</button>`);
  }

  function render() {
    badge();
    const count = document.getElementById('noticeFoldCount');
    if (count) { count.hidden = !X.unread; count.textContent = X.unread ? `안 읽은 알림 ${X.unread}건` : ''; }
    const root = document.getElementById('noticeView'); if (!root) return;
    // 담당자 정보를 못 읽으면 알림을 읽을 수 없다 — 까닭과 [다시 시도]
    if (X.err && !me()) {
      root.innerHTML = UI.errorBlock('알림을 열 수 없습니다', X.err, { retry: true, cls: 'compact' });
      root.querySelector('[data-retry]')?.addEventListener('click', () => refresh());
      return;
    }
    const live = { on: '새 알림을 실시간으로 받고 있습니다.', connecting: '실시간 연결을 맺는 중입니다.', off: '실시간 연결이 끊겼습니다. 15초 뒤 다시 연결합니다.' }[X.live];
    root.innerHTML = `<p class="field-hint">알림 줄을 누르면 그 처리 건의 그 단계가 열리고 읽음으로 바뀝니다.</p>` +
      (X.err ? UI.errorBlock('알림을 읽지 못했습니다', X.err.replace(/^알림을 읽지 못했습니다: /, '') + (X.notes ? ' 아래는 마지막으로 읽은 목록입니다.' : ''), { retry: true, cls: 'compact' }) : '') +
      `<div class="inbox-body">${notesHtml()}</div><p class="field-hint" aria-live="polite">${esc(live)}</p>`;
    root.querySelectorAll('[data-inbox-link]').forEach(a => a.addEventListener('click', e => {
      e.preventDefault();
      const note = a.dataset.inboxNote, link = a.dataset.inboxLink;
      if (note && !X.notes.find(n => n.id === note)?.is_read) markRead([note]);
      if (link) window.hydShell.navigate(link);      // #/instances/<id>/task/<taskId> — 주소는 셸(shell.js)이 읽는다
    }));
    root.querySelector('[data-inbox-readall]')?.addEventListener('click', () => markRead(null));
    root.querySelector('[data-retry]')?.addEventListener('click', () => refresh());
  }

  const unread = () => (me() && X.unread) || 0;   // 상단 종(shell.js)이 읽는 안 읽은 알림 수(숫자)
  function badge() {
    const n = unread();
    if (X.lastUnread !== n) { X.lastUnread = n; window.dispatchEvent(new Event('hyd:badge')); }   // 종 숫자를 바로 갱신
  }
  // 종을 누르면: 처리 건 화면의 「알림」 접기를 펼치고 그 자리로 간다(부르는 쪽이 먼저 처리 건 화면을 연다)
  function openNotices() {
    const fold = document.getElementById('noticeFold');
    fold.open = true;
    fold.scrollIntoView({ block: 'start', behavior: 'smooth' });
    fold.querySelector('summary').focus({ preventScroll: true });
    refresh();
  }

  /* ------------------------------------------------ 승인 · 제출 폼의 역할 · 사유 칸 (instances.js 가 부른다 — 담당자를 아직 못 읽었으면 null)
     담당자 id 는 폼 상태(form.by)에만 싣고 화면에는 보이지 않는다. 화면에 보이는 것은 승인하는 역할이다. */
  function whoFields(prefix, form, roles, { reasonHint = UI.t('form.hint.reason') } = {}) {
    const m = me(); if (!m) return null;
    form.by = m.id;
    const known = Object.fromEntries(roles || []);
    const name = (known[form.role] && known[form.role].name) || roleName(form.role);
    return UI.section('승인 역할 · 사유',
      UI.readonly('승인 역할', esc(name), '이 단계를 맡는 역할입니다. 처리 기록에 이 역할로 남습니다') +
      UI.field({ label: UI.t('form.reason'), cls: 'wide', hint: reasonHint, input: `<textarea id="${prefix}Reason" rows="2">${esc(form.reason || '')}</textarea>` }));
  }
  // 제출 · 답변 폼: 보일 칸은 없고 담당자 id 만 폼 상태에 싣는다. 담당자가 있으면 참(빈 표식), 없으면 null
  function byField(prefix, form) {
    const m = me(); if (!m) return null;
    form.by = m.id;
    return '<span hidden data-by-owner></span>';
  }

  window.hydInbox = { unread, me, whoFields, byField, refresh, openNotices };

  async function boot() {
    render();
    await refresh();
    setInterval(() => { if (me() && state.tab === 'instances') refresh(); }, 15000);   // 다른 창에서 읽음 처리한 것을 맞춘다(새 알림은 SSE 가 바로 부른다)
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
