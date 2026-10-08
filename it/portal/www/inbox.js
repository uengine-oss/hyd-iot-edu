/* U5 (TODO A3) — 나 · 내 작업함 · 포털 안 알림. process 의 instance-mode API 를 읽는다(procsvc/inbox_api.py):
     GET  /api/inbox/users · /api/inbox?user_id= · /api/inbox/assignments
     GET  /api/inbox/notifications?user_id= · POST /api/inbox/notifications/read · SSE /api/inbox/notifications/stream?user_id=
   HYD 에는 로그인이 없다. "나"는 시드의 사람 사용자 중 하나를 고르고 브라우저에 기억한다(localStorage 'hyd.me').
   승인할 때는 자유 입력 대신 "나"와 "내 역할"이 들어가고, 서버가 그 사람이 그 역할의 구성원인지 · 역할 등급이 카드 승인 역할 이상인지
   둘 다 검사한다(아니면 403). 위임·외부 알림(메신저)은 범위 밖.
   공개: window.hydInbox.mount(el) — 작업함 화면, window.hydInbox.badge() — 상단 "나 · 안 읽은 알림" 단추(요소를 돌려준다),
         window.hydInbox.me() · whoFields(prefix, form, roles) · byField(prefix, form) — 승인·제출 폼의 승인자 칸. */
(function () {
  const KEY = 'hyd.me';
  const X = { people: null, board: null, box: null, notes: [], tab: 'tasks', meId: null, es: null, live: 'off', err: '', mounts: [], badges: [], loading: false, timer: null };
  try { X.meId = localStorage.getItem(KEY); } catch (e) { X.meId = null; }

  const roleName = id => UI.who(id);
  const me = () => (X.people || []).find(p => p.id === X.meId) || null;
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
      X.err = e.status === 409 ? '내 작업함은 처리 건 방식(PROCESS_MODE=instance)에서만 열립니다.' : `사용자 목록을 읽지 못했습니다: ${e.message}`;
      return;
    }
    // 사람 이름을 포털 전체의 "누가" 표시에 등록한다(작업 담당 · 승인자 · 기록이 id 대신 이름으로 보인다)
    X.people.forEach(p => { UI.performers[p.id] = p.name; });
    UI.namesVersion = (UI.namesVersion || 0) + 1;
    if (X.meId && !me()) { X.err = '기억해 둔 "나"가 사용자 목록에 없습니다. 다시 고르세요.'; setMe(null, false); }
  }

  async function refresh() {
    if (X.loading) return; X.loading = true;
    try {
      if (!X.people) await loadPeople();
      const m = me();
      if (!m) { X.box = null; X.notes = []; render(); return; }
      try {
        const [box, notes] = await Promise.all([getJ(url('/api/inbox', { user_id: m.id })), getJ(url('/api/inbox/notifications', { user_id: m.id, limit: 50 }))]);
        X.box = box; X.notes = notes; X.err = '';
      } catch (e) { X.err = `내 작업함을 읽지 못했습니다: ${e.message}`; }
      if (!X.board) { try { X.board = await getJ(url('/api/inbox/assignments')); } catch (e) { X.board = { error: e.message }; } }
      render();
    } finally { X.loading = false; }
  }

  function setMe(id, reload = true) {
    X.meId = id || null;
    try { if (X.meId) localStorage.setItem(KEY, X.meId); else localStorage.removeItem(KEY); } catch (e) { /* 저장이 막혀도 이 탭에서는 쓴다 */ }
    connect();
    if (reload) { X.box = null; X.notes = []; refresh(); }
    // 승인 폼이 열려 있으면 승인자 칸을 새 "나"로 다시 그린다
    if (window.hydInstances && state.tab === 'instances') window.hydInstances.load(true);
  }

  /* ------------------------------------------------ SSE: 새 알림 */
  function connect() {
    if (X.es) { X.es.close(); X.es = null; }
    const m = me(); if (!m) { X.live = 'off'; return; }
    const es = new EventSource(url('/api/inbox/notifications/stream', { user_id: m.id }));
    X.es = es; X.live = 'connecting';
    es.onopen = () => { X.live = 'on'; renderBadges(); };
    es.onmessage = () => { clearTimeout(X.timer); X.timer = setTimeout(refresh, 200); };   // 새 알림 → 작업함 · 알림 · 안 읽은 수를 다시 읽는다
    es.onerror = () => {
      if (es.readyState !== EventSource.CLOSED) { X.live = 'connecting'; renderBadges(); return; }
      es.close(); if (X.es === es) X.es = null;
      X.live = 'off'; renderBadges();
      setTimeout(() => { if (!X.es && me()) connect(); }, 15000);
    };
  }

  /* ------------------------------------------------ 이동: #/instances/<id>/task/<taskId> */
  function go(link) {
    if (!link) return;
    if (location.hash === link) route(); else location.hash = link;
  }
  function route() {
    const m = /^#\/instances\/([^/]+)(?:\/task\/([^/]+))?$/.exec(location.hash);
    if (!m) { if (location.hash === '#/inbox') selectTab('inbox'); return; }
    const [, pid, tid] = m.map(decodeURIComponent);
    selectTab('instances');
    if (tid && window.hydInstancesOpenTask) window.hydInstancesOpenTask(pid, tid);
    else if (window.hydInstancesSelect) window.hydInstancesSelect(pid);
  }
  window.addEventListener('hashchange', route);

  async function markRead(ids) {
    const m = me(); if (!m) return;
    try { await postJ(url('/api/inbox/notifications/read'), ids ? { user_id: m.id, ids } : { user_id: m.id }); }
    catch (e) { X.err = `읽음 처리를 하지 못했습니다: ${e.message}`; }
    await refresh();
  }

  /* ------------------------------------------------ render */
  function pickerHtml() {
    const m = me();
    const opts = (X.people || []).map(p => `<option value="${esc(p.id)}" ${p.id === X.meId ? 'selected' : ''}>${esc(p.name)} · ${esc(p.roles.map(roleName).join(', ') || '역할 없음')}</option>`).join('');
    return UI.field({ label: '나', hint: m ? '이 브라우저가 기억합니다. 승인할 때 승인자와 역할이 나로 채워집니다.' : '먼저 나를 고르세요. 나에게 온 단계와 알림이 여기에 모입니다.',
      input: `<select data-inbox-me><option value="">고르기</option>${opts}</select>` });
  }

  function taskRow(t) {
    const label = t.kind === 'question' ? `AI 질문 — ${UI.flowName(t.activity_name)}` : UI.flowName(t.activity_name);
    const whom = t.assignment === 'me' ? UI.chipText('나에게', 'accent') : UI.chipText(`역할 공용 · ${roleName(t.user_id)}`, 'neutral');
    const due = t.due_date ? ` · 기한 ${UI.time(t.due_date)}` : '';
    return `<a class="item" href="${esc(t.link)}" data-inbox-link="${esc(t.link)}"><div class="row"><strong>${esc(label)}</strong>${t.kind === 'question' ? UI.chip('HUMAN_ASKED') : whom}</div>
      <span class="sub">${esc(t.proc_inst_name || UI.defName(t.proc_def_id))} · ${esc(ago(t.elapsed_s))}${esc(due)}</span></a>`;
  }

  function tasksHtml() {
    const b = X.box;
    if (!b) return UI.empty('읽는 중…', '', 'compact');
    const rows = [...b.asked, ...b.tasks];
    const list = rows.length ? `<div class="list">${rows.map(taskRow).join('')}</div>`
      : UI.empty('지금 나에게 온 단계가 없습니다', `내 역할(${b.roles.map(roleName).join(', ') || '없음'})의 사람 단계가 열리면 여기에 뜨고 알림이 옵니다.`, 'compact');
    const gaps = (b.unassigned_roles || []).length
      ? `<p class="field-hint">담당자가 없는 역할: ${esc(b.unassigned_roles.map(r => `${roleName(r.role_id)} ${r.open_tasks}건`).join(', '))} — 업무분장에 사람이 없어 누구의 작업함에도 뜨지 않습니다.</p>` : '';
    return list + gaps + boardFold();
  }

  function boardFold() {
    const bd = X.board;
    if (!bd) return '';
    if (bd.error) return `<p class="field-hint">업무분장을 읽지 못했습니다: ${esc(bd.error)}</p>`;
    const name = id => (X.people || []).find(p => p.id === id)?.name || UI.who(id);
    const rows = bd.roles.map(r => `<div class="kv-line"><b>${esc(roleName(r.id))}</b> · ${r.members.length ? esc(r.members.map(name).join(', ')) : '사람 없음'}
      <span class="muted">— ${r.members.length === 1 ? '단계가 열리면 이 사람에게 바로' : r.members.length ? '역할 공용(구성원 모두의 작업함에)' : '누구의 작업함에도 안 뜸'}</span></div>`).join('');
    return UI.fold('업무분장 — 역할마다 사람', rows);
  }

  function notesHtml() {
    if (!X.notes.length) return UI.empty('알림이 없습니다', '사람 단계가 오거나 AI가 질문하거나 내 처리 건이 끝나면 여기에 쌓입니다.', 'compact');
    const unread = X.notes.filter(n => !n.is_read).length;
    const KIND = { task_assigned: '내 차례', workitem_bpm: 'AI 질문', instance_completed: '처리 건 종료' };
    const rows = X.notes.map(n => `<a class="item${n.is_read ? '' : ' unread'}" href="${esc(n.link || '#/inbox')}" data-inbox-note="${esc(n.id)}" data-inbox-link="${esc(n.link || '')}">
      <div class="row"><strong>${esc(n.type === 'task_assigned' ? UI.flowName(n.title) : n.title || '')}</strong>${UI.chipText(KIND[n.type] || '알림', n.is_read ? 'neutral' : 'accent')}</div>
      <span class="sub">${n.is_read ? '' : '안 읽음 · '}${esc(UI.dateTime(n.created_at))}${n.type === 'workitem_bpm' ? '' : n.description ? ' · ' + esc(n.description) : ''}${n.link_error ? ' · ' + esc(n.link_error) : ''}</span></a>`).join('');
    return `<div class="list">${rows}</div>` + UI.actions(`<button class="btn small" data-inbox-readall ${unread ? '' : 'disabled'}>모두 읽음</button>`);
  }

  function render() {
    X.mounts = X.mounts.filter(e => e.isConnected);
    X.mounts.forEach(renderInto);
    renderBadges();
  }

  function renderInto(root) {
    if (X.err && !X.people) { root.innerHTML = UI.empty('내 작업함을 열 수 없습니다', X.err); return; }
    if (!X.people) { root.innerHTML = UI.empty('읽는 중…', '', 'compact'); return; }
    const m = me();
    const unread = (X.box && X.box.unread) || 0;
    const nTasks = X.box ? X.box.tasks.length + X.box.asked.length : null;
    const live = { on: '새 알림 실시간 받는 중', connecting: '실시간 연결 중', off: '실시간 꺼짐 — 화면을 다시 열면 새로 읽습니다' }[X.live];
    root.innerHTML = `<div class="form"><section class="form-section"><div class="form-grid">${pickerHtml()}</div></section></div>` +
      (X.err ? `<p class="form-msg neg" role="status">${esc(X.err)}</p>` : '') +
      (m ? UI.tabs([['tasks', '내 작업', nTasks], ['notes', '알림', unread]], X.tab, 'data-inbox-tab') +
        `<div class="inbox-body">${X.tab === 'tasks' ? tasksHtml() : notesHtml()}</div><p class="field-hint" aria-live="polite">${esc(live)}</p>` : '');
    root.querySelector('[data-inbox-me]')?.addEventListener('change', e => setMe(e.target.value));
    root.querySelectorAll('[data-inbox-tab]').forEach(b => b.addEventListener('click', () => { X.tab = b.dataset.inboxTab; render(); }));
    root.querySelectorAll('[data-inbox-link]').forEach(a => a.addEventListener('click', e => {
      e.preventDefault();
      const note = a.dataset.inboxNote, link = a.dataset.inboxLink;
      if (note && !X.notes.find(n => n.id === note)?.is_read) markRead([note]);
      if (link) go(link);
    }));
    root.querySelector('[data-inbox-readall]')?.addEventListener('click', () => markRead(null));
  }

  function badge() {
    const b = el('button', 'btn small inbox-badge');
    b.type = 'button';
    b.addEventListener('click', () => { if (location.hash === '#/inbox') selectTab('inbox'); else location.hash = '#/inbox'; });
    X.badges.push(b);
    renderBadges();
    return b;
  }
  function renderBadges() {
    const m = me(), unread = (X.box && X.box.unread) || 0;
    X.badges.forEach(b => {
      b.innerHTML = m ? `${esc(m.name)}${unread ? ` <span class="chip tone-accent sm">알림 ${unread}</span>` : ''}` : '나 고르기';
      b.title = m ? `나: ${m.name} · 안 읽은 알림 ${unread}건 — 내 작업함 열기` : '나를 골라 내 작업함과 알림을 받습니다';
    });
  }

  function mount(root) {
    if (!root) return;
    if (!X.mounts.includes(root)) X.mounts.push(root);
    renderInto(root);
    refresh();
  }

  /* ------------------------------------------------ 승인 · 제출 폼의 승인자 칸 (enterprise.js whoFields · instances.js 가 부른다) */
  const dropStale = form => { if (String(form.by || '').startsWith('user:')) form.by = ''; return null; };   // "나"를 지웠으면 자유 입력으로
  function whoFields(prefix, form, roles, { reasonHint = UI.t('form.hint.reason') } = {}) {
    const m = me(); if (!m) return dropStale(form);
    form.by = m.id;
    if (!m.roles.includes(form.role)) form.role = m.roles[0] || '';
    const known = Object.fromEntries(roles || []);
    const opts = m.roles.map(id => `<option value="${esc(id)}" ${id === form.role ? 'selected' : ''}>${esc((known[id] && known[id].name) || roleName(id))}</option>`).join('');
    return UI.section(UI.t('form.section.who'),
      UI.readonly(UI.t('form.by'), `${esc(m.name)} <span class="muted">(나)</span>`, '바꾸려면 내 작업함에서 나를 다시 고르세요') +
      UI.field({ label: UI.t('form.role'), required: true, hint: '내 역할로만 승인합니다. 카드의 승인 역할이 더 높으면 서버가 거부합니다.',
        input: `<select id="${prefix}Role">${opts || '<option value="">내 역할 없음</option>'}</select>` }) +
      UI.field({ label: UI.t('form.reason'), cls: 'wide', hint: reasonHint, input: `<textarea id="${prefix}Reason" rows="2">${esc(form.reason || '')}</textarea>` }));
  }
  function byField(prefix, form) {
    const m = me(); if (!m) return dropStale(form);
    form.by = m.id;
    return UI.readonly(UI.t('form.by'), `${esc(m.name)} <span class="muted">(나)</span>`);
  }

  window.hydInbox = { mount, badge, me, whoFields, byField, refresh, X };

  // 목록 행은 <a>(주소 복사·새 탭 가능) — 링크 색 대신 기존 목록 행 모양을 쓴다
  const style = el('style', null, '.inbox-body a.item{display:block;color:inherit;text-decoration:none}.inbox-body a.item.unread strong{font-weight:700}.inbox-body a.item:not(.unread){opacity:.78}.inbox-badge{white-space:nowrap}');
  document.head.appendChild(style);

  async function boot() {
    const root = document.getElementById('inboxView'); if (root) X.mounts.push(root);
    const slot = document.getElementById('inboxBadge'); if (slot && !slot.firstChild) slot.appendChild(badge());
    render();
    await refresh();
    connect(); route();
    setInterval(() => { if (me() && state.tab === 'inbox') refresh(); }, 15000);   // 경과 시간 갱신(새 알림은 SSE 가 바로 부른다)
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
