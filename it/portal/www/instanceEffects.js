/* External effects of a retired generation (A072): what the case already did to the plant and the business systems,
   which of it the business systems can reverse exactly, and the human acknowledgement for the rest. Rework waits for this.
   One form frame — summary line → table → 담당자 · 역할 · 사유 in one labelled row → buttons bottom-right.
   효과 조회(GET …/effects)는 업무 시스템 원장을 읽어 몇 초 걸린다 — 처리 건 화면이 2초마다 다시 그려도 처리 건이 바뀌었을 때(단계 · 승인 ·
   효과 영수증)만 다시 읽는다. */
(function () {
  const states = new Map();
  const kinds = { enterprise: '업무 거래', plc: '설비 명령', cmms: '정비 요청(업무 시스템 확인 전)', 'cmms-request': '정비 요청(접수 여부 모름)', local: '포털 안 실행 기록' };
  // A147: a lost response keeps the exact request (same request_id) so a retry never creates a second compensation/review (instanceRework.js pattern)
  const key = id => 'hyd:effects:' + id;
  function stateFor(id, by) {
    // 본 처리 건 상태만 들고 있는다 — 응답을 기다리는 요청이 없는 다른 처리 건 상태는 버린다(요청은 세션 저장소에 따로 남는다)
    for (const [other, st] of states) if (other !== id && !st.pending) states.delete(other);
    if (!states.has(id)) {
      let pending = null;
      try { pending = JSON.parse(sessionStorage.getItem(key(id)) || 'null'); } catch (_) { /* Storage unavailable: in-memory retry still works. */ }
      states.set(id, { data: null, by: pending?.body.by || by || '', role: pending?.body.role || '', reason: pending?.body.reason || '', picked: new Set(), busy: false, error: '', notice: '', pending });
    }
    return states.get(id);
  }
  function clearPending(s, id) {
    s.pending = null;
    try { sessionStorage.removeItem(key(id)); } catch (_) { /* nothing persisted */ }
  }
  function label(e) {
    if (e.kind === 'enterprise') return `${esc(UI.who(e.system) || '')} · ${esc(UI.idText(e.skill || ''))} · ${esc(e.ref || '')}${e.detail ? ' — ' + esc(e.detail) : ''}`;
    if (e.kind === 'plc') return `${esc(e.cmdId || '')} · ${esc((e.actions || []).map(a => hydCards.actionLabel({ code: a.code, value: a.fan_pct ?? a.load_pct ?? a.pump })).join(', '))} · ${UI.t('ack')} ${esc(UI.status((e.ack || {}).result) || '없음')}`;
    return `${esc(e.ref || e.code || '')}${e.status ? ' · ' + esc(UI.status(e.status)) : ''}`;
  }
  // 효과 목록이 바뀔 수 있는 처리 건 변화(단계 상태 · 승인 전달 · 효과 영수증 · 차수) — 같으면 다시 읽지 않는다
  const basisOf = view => JSON.stringify([view.instance.status, view.instance.rework_generation,
    (view.workitems || []).map(w => [w.id, w.status]), (view.approvals || []).map(a => [a.todo_id, a.status]),
    (view.effects || []).map(r => [r.request_id, r.status])]);
  function mount(host, { view, by, changed }) {
    if (!host) return;
    // 입력 칸에서 글을 쓰는 중이면 다시 그리지 않는다(2초 다시 그리기가 한글 조합을 끊는다)
    const typing = document.activeElement;
    if (typing && host.contains(typing) && /^(INPUT|TEXTAREA|SELECT)$/.test(typing.tagName)) return;
    const id = view.instance.proc_inst_id, s = stateFor(id, by);
    const incident = (view.instance.variables_data || []).find(v => v.key === 'incident');
    if (!incident || !incident.value) { host.innerHTML = ''; return; }
    const roleName = role => (view.definition.roles || []).find(r => r.endpoint === role)?.name || UI.who(role);
    async function load() {
      try { s.data = await getJ(API.process + '/api/instances/' + encodeURIComponent(id) + '/effects'); s.error = ''; }
      catch (e) { s.data = null; s.error = e.message; }
      // 서버에 이 요청의 영수증이 있으면 이미 처리된 것이다(영수증은 결과와 함께 저장된다) — 같은 요청을 다시 보내지 않는다
      const done = s.pending && (s.data?.receipts || []).find(r => r.request_id === s.pending.body.request_id);
      if (done) { clearPending(s, id); s.notice = `응답을 받지 못했던 이전 요청은 처리돼 있습니다 (${done.kind === 'review' ? '확인 기록' : '되돌림 ' + UI.status(done.status)})`; }
      draw();
    }
    function draw() {
      if (!host.isConnected) return;
      const d = s.data;
      if (!d) {
        host.innerHTML = UI.fold(esc(UI.t('inst.effects')), s.error ? UI.errorBlock('실행 효과를 읽지 못했습니다', s.error, { retry: true }) : UI.loading(), { open: !!s.error });
        host.querySelector('[data-retry]')?.addEventListener('click', () => { s.basis = null; load(); });
        return;
      }
      const res = d.resolution || { pending: [], compensated: [], acknowledged: [] };
      const pending = new Set(res.pending);
      const rows = (d.effects || []).map(e => {
        const state = res.compensated.includes(e.id) ? UI.chipText('되돌림 완료', 'success') : res.acknowledged.includes(e.id) ? UI.chipText('사람 확인', 'success') : UI.chipText('미해결', 'warning');
        const how = e.compensation_refused ? '업무 시스템이 되돌리기를 거절함 — 사람 확인으로 정리' : e.reversible ? `되돌릴 수 있음 → ${esc(UI.name(e.inverse))}` : `되돌릴 수 없음 — ${esc(e.irreversible_reason || '')}`;
        const pick = pending.has(e.id) && (!e.reversible || e.compensation_refused) ? `<input type="checkbox" data-effect="${esc(e.id)}" aria-label="${esc(`${kinds[e.kind] || '실행 효과'} ${e.ref || e.cmdId || e.code || ''} 확인에 포함`)}" ${s.picked.has(e.id) ? 'checked' : ''} ${s.busy ? 'disabled' : ''}>` : '';
        return `<tr><td>${pick}</td><td>${esc(kinds[e.kind] || '종류 표시 이름 미등록')}</td><td>${label(e)}</td><td>${how}</td><td>${state}</td></tr>`;
      }).join('');
      const reversiblePending = (d.effects || []).filter(e => pending.has(e.id) && e.reversible && !e.compensation_refused).length;
      const receipts = (d.receipts || []).map(r => `<li>${esc(r.kind === 'review' ? '사람 확인' : '되돌림')} · ${UI.chip(r.status)} · ${esc(UI.who(r.request.by))} (${esc(roleName(r.request.role))}) · ${esc(r.request.reason)}${r.error ? ' · <span class="muted" data-tone="danger">' + esc(r.error) + '</span>' : ''}</li>`).join('');
      /* 확인 역할: 서버는 이 흐름에서 사람이 맡는 역할 가운데 하나만 받고, 그 역할이 이전 승인을 한 역할과 같거나 높은지 본다
         (effect_compensation._authorize_review · _review_level). 후보가 하나면 고를 것이 없으므로 그 값을 쓰고 한 줄로 보인다.
         여럿이면 고른 역할에 따라 서버 판정이 달라지므로 고르게 둔다 — 첫 항목을 저절로 보내지 않는다. */
      const roles = d.review_roles || [];
      if (roles.length === 1 && !s.pending) s.role = roles[0];
      const roleField = !roles.length ? UI.readonly('확인 역할', '<span class="muted" data-tone="danger">이 흐름에는 사람이 맡는 역할이 없어 되돌리기와 확인을 요청할 수 없습니다.</span>')
        : roles.length === 1 ? UI.readonly('확인 역할', esc(roleName(roles[0])), '이 흐름에서 사람이 맡는 역할이 하나뿐이라 이 역할로 요청합니다.')
        : UI.field({ label: '확인 역할', required: true, hint: '어느 역할로 되돌리기와 확인을 요청하는지 고릅니다. 이전 승인을 한 역할과 같거나 더 높은 역할이어야 합니다.',
          input: `<select id="efRole" ${s.busy ? 'disabled' : ''}><option value="">${esc(UI.t('form.pickRole'))}</option>${roles.map(r => `<option value="${esc(r)}" ${r === s.role ? 'selected' : ''}>${esc(roleName(r))}</option>`).join('')}</select>` });
      const body = `<p>연결된 사건: ${UI.chip(d.incident.state)} · 설비 명령 ${d.incident.cmdId ? '보냄' : '보내지 않음'}</p>
        ${rows ? `<div class="table-container"><table class="table case-table"><thead><tr><th>확인</th><th>종류</th><th>내용</th><th>처리 방법</th><th>상태</th></tr></thead><tbody>${rows}</tbody></table></div>` : '<p class="muted">기록된 외부 효과가 없습니다.</p>'}
        <div><fieldset class="fieldset"><legend>${esc(UI.t('form.section.who'))}</legend><div role="group">
          ${UI.actorInput('id="efBy"', s.by, s.busy ? 'disabled' : '')}
          ${roleField}
          ${UI.field({ label: UI.t('form.reason'), required: true, cls: 'wide', input: `<textarea id="efReason" rows="2" ${s.busy ? 'disabled' : ''}>${esc(s.reason)}</textarea>` })}
        </div></fieldset>
        ${s.pending ? `<p>앞 요청의 응답을 받지 못했습니다. 눌러서 처리됐는지 확인하세요. 같은 요청을 다시 확인하는 것이라 두 번 처리되지 않습니다.</p>${UI.actions(`<button type="button" class="btn" data-variant="outline" id="efRetry" ${s.busy ? 'disabled' : ''}>요청 결과 확인</button>`, s.error)}`
          : UI.actions(`<button class="btn" data-variant="outline" id="efCompensate" ${!reversiblePending || s.busy ? 'disabled' : ''}>되돌릴 수 있는 거래 ${reversiblePending}건 되돌리기</button><button class="btn" id="efReview" ${!s.picked.size || s.busy ? 'disabled' : ''}>${esc(UI.t('btn.confirm'))} (${s.picked.size})</button>`, s.error)}</div>
        ${pending.size === 0 && (d.effects || []).length ? `<p class="rework-done" role="status">모든 효과가 해결됐습니다. ${esc(UI.t('inst.rework'))}에서 새 차수를 요청할 수 있습니다.</p>` : ''}
        ${receipts ? UI.fold(`확인 기록 ${(d.receipts || []).length}건`, `<ul>${receipts}</ul>`) : ''}
        ${s.notice ? `<p role="status">${esc(s.notice)}</p>` : ''}`;
      host.innerHTML = UI.fold(`${esc(UI.t('inst.effects'))} ${pending.size ? UI.chipText(`확인할 조치 ${pending.size}`, 'neutral') : ''}`, body, { open: !!s.pending });   // A161-U1 결함 8: 끝난 처리 건에서 폼이 펼쳐져 나오지 않게(필요할 때 연다)
      host.querySelectorAll('input[data-effect]').forEach(cb => cb.addEventListener('change', e => { e.target.checked ? s.picked.add(e.target.dataset.effect) : s.picked.delete(e.target.dataset.effect); draw(); }));
      host.querySelector('#efBy')?.addEventListener('input', e => s.by = e.target.value);
      host.querySelector('#efRole')?.addEventListener('change', e => s.role = e.target.value);
      host.querySelector('#efReason')?.addEventListener('input', e => s.reason = e.target.value);
      // 업무 시스템의 거래를 실제로 취소하는 요청이다 — 빠진 칸을 먼저 알리고, 확인을 받은 뒤 보낸다
      host.querySelector('#efCompensate')?.addEventListener('click', async () => {
        if (s.busy) return;
        if (!s.by.trim() || !s.role || !s.reason.trim()) { s.error = UI.t('form.err.byRoleReason'); draw(); return; }
        const yes = await UI.confirm({ title: `업무 거래 ${reversiblePending}건을 되돌릴까요?`, body: '업무 시스템에 이미 넣은 거래(발주 · 정비 요청 등)를 취소합니다. 되돌린 거래는 다시 살릴 수 없습니다.', ok: '되돌리기', danger: true });
        if (yes) send('compensate', null);
      });
      host.querySelector('#efReview')?.addEventListener('click', () => send('review', [...s.picked]));
      host.querySelector('#efRetry')?.addEventListener('click', () => send());
    }
    async function send(kind, effects) {
      if (s.busy) return;
      if (!s.pending) {
        if (!s.by.trim() || !s.role || !s.reason.trim()) { s.error = UI.t('form.err.byRoleReason'); draw(); return; }
        s.pending = { kind, body: { request_id: UI.uuid(), by: s.by, role: s.role, reason: s.reason, effects } };
        try { sessionStorage.setItem(key(id), JSON.stringify(s.pending)); } catch (_) { /* Retain exact request in memory. */ }
      }
      ({ kind } = s.pending);
      s.busy = true; s.error = ''; s.notice = ''; draw();
      try {
        const r = await postJ(API.process + '/api/instances/' + encodeURIComponent(id) + '/effects/' + kind, s.pending.body);
        s.notice = kind === 'review' ? '확인 기록을 저장했습니다' : `되돌리기 요청 결과: ${UI.status(r.status)} (${(r.effects || []).length}건 중 ${(r.results || []).filter(x => x.ok).length}건 성공)`;
        if (r.status === 'FAILED') s.error = r.error || '되돌리지 못했습니다';
        clearPending(s, id); s.picked.clear();
      } catch (e) {
        s.error = e.message;
        if (e.status >= 400 && e.status < 500) clearPending(s, id);    // the server refused this request: a new one is needed
      }
      s.busy = false;
      s.basis = null;
      await load();
      if (changed) changed();
    }
    if (s.data) draw();
    const basis = basisOf(view);
    if (basis !== s.basis) { s.basis = basis; load(); }
    else if (!s.data) draw();
  }
  window.hydEffects = { mount };
})();
