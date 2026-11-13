/* U5 — 나 · 내 작업함 · 포털 안 알림. process 의 instance-mode API 를 읽는다(procsvc/inbox_api.py):
     GET  /api/inbox/users · /api/inbox?user_id= · /api/inbox/assignments
     GET  /api/inbox/notifications?user_id= · POST /api/inbox/notifications/read · SSE /api/inbox/notifications/stream?user_id=
   HYD 에는 로그인이 없다. 로그인 대신 「사용자 선택」으로 시드의 사람 사용자 중 하나를 고르고 브라우저에 기억한다(localStorage 'hyd.me').
   고르는 자리는 둘이다: 상단 계정 자리(#shellMe)와, 사용자가 있어야 하는 폼 안의 그 자리(pickInline — 다른 메뉴로 보내지 않는다).
   승인할 때는 자유 입력 대신 선택한 사용자와 그 역할이 들어가고, 서버가 그 사람이 그 역할의 구성원인지 · 역할 등급이 카드 승인 역할 이상인지
   둘 다 검사한다(아니면 403). 위임·외부 알림(메신저)은 범위 밖.
   공개: window.hydInbox.mount(el) — 작업함 화면, mountMe(box) — 상단 계정 자리(셸 #shellMe, 안 읽은 수는 셸의 종이 unread()로),
         window.hydInbox.me() · meLabel() · pickInline(무엇을) · whoFields(prefix, form, roles) · byField(prefix, form) — 승인·제출 폼의 담당자 칸.
         사용자가 바뀌면 window 에 'hyd:me' 이벤트를 낸다(폼을 그린 화면이 다시 그린다). */
(function () {
  const KEY = 'hyd.me';
  const X = { people: null, board: null, box: null, notes: [], tab: 'tasks', meId: null, es: null, live: 'off', err: '', mounts: [], meBoxes: [], loading: false, timer: null };
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
      X.err = `사용자 목록을 읽지 못했습니다: ${e.message}`;
      return;
    }
    // 사람 이름을 포털 전체의 "누가" 표시에 등록한다(작업 담당 · 승인자 · 기록이 id 대신 이름으로 보인다)
    X.people.forEach(p => { UI.performers[p.id] = p.name; });
    UI.namesVersion = (UI.namesVersion || 0) + 1;
    if (me()) window.dispatchEvent(new Event('hyd:me'));   // 기억해 둔 사용자가 확인됐다 — 담당자 칸을 그려 둔 화면이 채운다
    if (X.meId && !me()) { X.err = '지난번에 선택한 사용자가 사용자 목록에 없습니다. 다시 선택하세요.'; setMe(null, false); }
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
      // 업무분장(역할마다 사람)도 작업함과 함께 다시 읽는다 — 에이전트 화면에서 사람을 넣고 빼면 다음 읽기에 보인다(W3-19)
      try { X.board = await getJ(url('/api/inbox/assignments')); } catch (e) { X.board = { error: e.message }; }
      render();
    } finally { X.loading = false; }
  }

  function setMe(id, reload = true) {
    X.meId = id || null;
    try { if (X.meId) localStorage.setItem(KEY, X.meId); else localStorage.removeItem(KEY); } catch (e) { /* 저장이 막혀도 이 탭에서는 쓴다 */ }
    connect();
    if (reload) { X.box = null; X.notes = []; refresh(); }
    renderBadges();
    // 승인 폼이 열려 있으면 담당자 칸을 새 사용자로 다시 그린다. 다른 화면은 'hyd:me' 를 듣고 제 폼을 다시 그린다
    if (window.hydInstances && state.tab === 'instances') window.hydInstances.load(true);
    window.dispatchEvent(new Event('hyd:me'));
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
  // 사용자 표기는 한 가지: 「최운전 (운전원)」
  const rolesOf = p => p.roles.map(roleName).join(', ') || '역할 없음';
  const label = p => `${p.name} (${rolesOf(p)})`;
  const meLabel = () => { const m = me(); return m ? label(m) : ''; };
  // 사용자 선택 칸 — 상단 계정 자리와 폼 안에서 같은 것을 쓴다. 바뀌면 아래 문서 수준 change 처리기가 setMe 를 부른다
  function selectHtml(cls = '') {
    const opts = (X.people || []).map(p => `<option value="${esc(p.id)}" ${p.id === X.meId ? 'selected' : ''}>${esc(label(p))}</option>`).join('');
    return `<select data-pick-user class="${cls}" aria-label="사용자 선택"><option value="">사용자 선택</option>${opts}</select>`;
  }
  // 사용자가 있어야 하는 폼의 그 자리에 두는 안내 + 선택 칸(다른 메뉴로 보내지 않는다). what = '승인 · 반려' 처럼 하려는 일
  function pickInline(what = '', role = '') {
    const lead = (what ? `${what}하려면 사용자를 선택하세요.` : '사용자를 선택하세요.') + (role ? ` 이 단계의 담당 역할은 ${role}입니다.` : '');
    return `<div class="pick-user" data-pick-me><span class="pick-user-lead">${esc(lead)}</span>${X.people ? selectHtml() : '<span class="muted">사용자 목록을 읽는 중…</span>'}<span class="field-hint">로그인 대신 쓰는 선택입니다. 누가 했는지가 기록에 남습니다.</span></div>`;
  }
  // 선택한 사용자의 역할로는 할 수 없을 때: 까닭(lead)과 함께 그 자리에서 사용자를 바꾸게 한다
  function switchInline(lead) {
    return `<div class="pick-user warn" data-switch-me role="status"><span class="pick-user-lead">${esc(lead)}</span>${selectHtml()}</div>`;
  }
  document.addEventListener('change', e => { const s = e.target.closest && e.target.closest('[data-pick-user]'); if (s) setMe(s.value); });

  function taskRow(t) {
    const label = t.kind === 'question' ? `AI 질문 — ${UI.flowName(t.activity_name)}` : UI.flowName(t.activity_name);
    const whom = t.assignment === 'me' ? UI.chipText('내 담당', 'accent') : UI.chipText(`${roleName(t.user_id)} 공동 담당`, 'neutral');
    const kind = t.kind === 'approve' ? ' ' + UI.chipText('승인 요청', 'warning') : '';      // 캡스톤 G1 사람 승인(안 고르기)
    const due = t.due_date ? ` · 기한 ${UI.time(t.due_date)}` : '';
    return `<a class="item" href="${esc(t.link)}" data-inbox-link="${esc(t.link)}"><div class="row"><strong>${esc(label)}</strong>${t.kind === 'question' ? UI.chip('HUMAN_ASKED') : whom + kind}</div>
      <span class="sub">${esc(t.proc_inst_name || UI.defName(t.proc_def_id))} · ${esc(ago(t.elapsed_s))}${esc(due)}</span></a>`;
  }

  function tasksHtml() {
    const b = X.box;
    if (!b) return UI.empty('읽는 중…', '', 'compact');
    const rows = [...b.asked, ...b.tasks];
    const list = rows.length ? `<div class="list">${rows.map(taskRow).join('')}</div>`
      : UI.empty('지금 처리할 단계가 없습니다', `${b.roles.map(roleName).join(', ') || '역할 없음'} 담당 단계가 열리면 여기에 표시되고 알림이 옵니다.`, 'compact');
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
      <span class="muted">— ${r.members.length === 1 ? '단계가 열리면 이 담당자에게 배정' : r.members.length ? '공동 담당(구성원 모두의 작업함에 표시)' : '담당자 없음 — 어느 작업함에도 표시되지 않음'}</span></div>`).join('');
    return UI.fold('업무분장 — 역할별 담당자', rows);
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
    // 사용자 목록을 못 읽으면 사용자를 선택할 수 없다 — 다시 시도 단추를 두고, 메뉴를 다시 열어도 셸이 새로 읽는다(failed)
    if (X.err && !X.people) {
      root.innerHTML = UI.errorBlock('내 작업함을 열 수 없습니다', X.err, { retry: true });
      root.querySelector('[data-retry]')?.addEventListener('click', () => refresh());
      return;
    }
    if (!X.people) { root.innerHTML = UI.empty('읽는 중…', '', 'compact'); return; }
    const m = me();
    const unread = (X.box && X.box.unread) || 0;
    const nTasks = X.box ? X.box.tasks.length + X.box.asked.length : null;
    const live = { on: '새 알림 실시간 받는 중', connecting: '실시간 연결 중', off: '실시간 꺼짐 — 화면을 다시 열면 새로 읽습니다' }[X.live];
    root.innerHTML = (m ? `<p class="inbox-owner"><b>${esc(label(m))}</b> 님에게 배정된 단계와 알림입니다.</p>`
        : `<div class="empty"><b>사용자를 선택하면 작업함이 열립니다</b>${pickInline()}</div>`) +
      (X.err ? `<p class="form-msg neg" role="status">${esc(X.err)}</p>` : '') +
      (m ? UI.tabs([['tasks', '내 작업', nTasks], ['notes', '알림', unread]], X.tab, 'data-inbox-tab') +
        `<div class="inbox-body">${X.tab === 'tasks' ? tasksHtml() : notesHtml()}</div><p class="field-hint" aria-live="polite">${esc(live)}</p>` : '');
    root.querySelectorAll('[data-inbox-tab]').forEach(b => b.addEventListener('click', () => { X.tab = b.dataset.inboxTab; render(); }));
    root.querySelectorAll('[data-inbox-link]').forEach(a => a.addEventListener('click', e => {
      e.preventDefault();
      const note = a.dataset.inboxNote, link = a.dataset.inboxLink;
      if (note && !X.notes.find(n => n.id === note)?.is_read) markRead([note]);
      if (link) go(link);
    }));
    root.querySelector('[data-inbox-readall]')?.addEventListener('click', () => markRead(null));
  }

  // 상단 계정 자리(shell.js #shellMe): 사용자 선택 칸 — 로그인 자리에서 바로 고르고 바꾼다
  function mountMe(box) {
    if (!box) return;
    if (!X.meBoxes.includes(box)) X.meBoxes.push(box);
    renderBadges();
  }
  const unread = () => (me() && X.box && X.box.unread) || 0;   // 상단 종(shell.js)이 읽는 안 읽은 알림 수(숫자)
  function renderBadges() {
    const m = me(), unread = (X.box && X.box.unread) || 0;
    X.meBoxes = X.meBoxes.filter(b => b.isConnected);
    X.meBoxes.forEach(b => {
      if (b.contains(document.activeElement)) return;      // 고르는 중에는 다시 그리지 않는다
      b.classList.toggle('needs-pick', !m && !!X.people);
      b.innerHTML = `${UI.icon ? UI.icon('user') : ''}${X.people ? selectHtml('shell-me-select') : `<span class="shell-me-label">${esc(X.err ? '사용자 목록 읽기 실패' : '사용자 읽는 중…')}</span>`}`;
      b.title = m ? `현재 사용자: ${label(m)} — 여기서 바꿉니다(로그인 대신 쓰는 선택)` : '사용자를 선택하세요(로그인 대신 쓰는 선택)';
    });
    if (X.lastUnread !== (m ? unread : 0)) { X.lastUnread = m ? unread : 0; window.dispatchEvent(new Event('hyd:badge')); }   // 종 숫자를 바로 갱신
  }

  function mount(root) {
    if (!root) return;
    if (!X.mounts.includes(root)) X.mounts.push(root);
    renderInto(root);
    refresh();
  }

  /* ------------------------------------------------ 승인 · 제출 폼의 담당자 칸 (instances.js 가 부른다 — 사용자가 없으면 null: 부르는 쪽이 pickInline 을 보인다) */
  const dropStale = form => { if (String(form.by || '').startsWith('user:')) form.by = ''; return null; };   // 사용자 선택을 지웠으면 비운다
  function whoFields(prefix, form, roles, { reasonHint = UI.t('form.hint.reason') } = {}) {
    const m = me(); if (!m) return dropStale(form);
    form.by = m.id;
    if (!m.roles.includes(form.role)) form.role = m.roles[0] || '';
    const known = Object.fromEntries(roles || []);
    const opts = m.roles.map(id => `<option value="${esc(id)}" ${id === form.role ? 'selected' : ''}>${esc((known[id] && known[id].name) || roleName(id))}</option>`).join('');
    return UI.section(UI.t('form.section.who'),
      UI.readonly(UI.t('form.by'), esc(m.name), '화면 오른쪽 위 사용자 선택에서 바꿀 수 있습니다') +
      UI.field({ label: UI.t('form.role'), required: true, hint: '선택한 사용자의 역할로 승인합니다. 이 단계의 승인 역할에 못 미치면 승인되지 않습니다.',
        input: `<select id="${prefix}Role">${opts || '<option value="">역할 없음</option>'}</select>` }) +
      UI.field({ label: UI.t('form.reason'), cls: 'wide', hint: reasonHint, input: `<textarea id="${prefix}Reason" rows="2">${esc(form.reason || '')}</textarea>` }));
  }
  function byField(prefix, form) {
    const m = me(); if (!m) return dropStale(form);
    form.by = m.id;
    return UI.readonly(UI.t('form.by'), esc(label(m)));
  }

  const failed = () => !X.people && !!X.err;
  window.hydInbox = { mount, failed, mountMe, unread, me, meLabel, pickInline, switchInline, whoFields, byField, refresh, X };

  async function boot() {
    const root = document.getElementById('inboxView'); if (root) X.mounts.push(root);
    render();
    await refresh();
    connect();
    setInterval(() => { if (me() && state.tab === 'inbox') refresh(); }, 15000);   // 경과 시간 갱신(새 알림은 SSE 가 바로 부른다)
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
