/* External effects of a retired generation (A072): what the case already did to the plant and the business systems,
   which of it the business systems can reverse exactly, and the human acknowledgement for the rest. Rework waits for this.
   A122 (F6): one form frame — summary line → table → 담당자 · 역할 · 사유 in one labelled row → buttons bottom-right. */
(function () {
  const states = new Map();
  const kinds = { enterprise: '업무 거래', plc: '설비 명령', cmms: '정비 요청 (원장 미확인)', 'cmms-request': '정비 요청 (접수 불명확)', local: '로컬 실행 기록' };
  function stateFor(id, by) {
    if (!states.has(id)) states.set(id, { data: null, by: by || '', role: '', reason: '', picked: new Set(), busy: false, error: '', notice: '' });
    return states.get(id);
  }
  function label(e) {
    if (e.kind === 'enterprise') return `${esc(UI.who(e.system) || '')} · ${esc(e.skill || '')} · ${esc(e.ref || '')}${e.detail ? ' — ' + esc(e.detail) : ''}`;
    if (e.kind === 'plc') return `${esc(e.cmdId || '')} · ${esc((e.actions || []).map(a => a.code + (a.fan_pct != null ? ' ' + a.fan_pct : '') + (a.load_pct != null ? ' ' + a.load_pct : '') + (a.pump ? ' ' + a.pump : '')).join(', '))} · ${UI.t('ack')} ${esc(UI.status((e.ack || {}).result) || '없음')}`;
    return `${esc(e.ref || e.code || '')}${e.status ? ' · ' + esc(UI.status(e.status)) : ''}`;
  }
  function mount(host, { view, by, changed }) {
    if (!host) return;
    const id = view.instance.proc_inst_id, s = stateFor(id, by);
    const incident = (view.instance.variables_data || []).find(v => v.key === 'incident');
    if (!incident || !incident.value) { host.innerHTML = ''; return; }
    const roleName = role => (view.definition.roles || []).find(r => r.endpoint === role)?.name || UI.who(role);
    async function load() {
      try { s.data = await getJ(API.process + '/api/instances/' + encodeURIComponent(id) + '/effects'); s.error = ''; }
      catch (e) { s.data = null; s.error = e.message; }
      draw();
    }
    function draw() {
      if (!host.isConnected) return;
      const d = s.data;
      if (!d) { host.innerHTML = UI.fold(esc(UI.t('inst.effects')), `<p class="muted">${esc(s.error || UI.t('loading'))}</p>`); return; }
      const res = d.resolution || { pending: [], compensated: [], acknowledged: [] };
      const pending = new Set(res.pending);
      const rows = (d.effects || []).map(e => {
        const state = res.compensated.includes(e.id) ? UI.chipText('보상 완료', 'success') : res.acknowledged.includes(e.id) ? UI.chipText('사람 확인', 'success') : UI.chipText('미해결', 'warning');
        const how = e.reversible ? `되돌릴 수 있음 → ${esc(e.inverse)}` : `되돌릴 수 없음 — ${esc(e.irreversible_reason || '')}`;
        const pick = pending.has(e.id) && !e.reversible ? `<input type="checkbox" data-effect="${esc(e.id)}" ${s.picked.has(e.id) ? 'checked' : ''} ${s.busy ? 'disabled' : ''}>` : '';
        return `<tr><td>${pick}</td><td>${esc(kinds[e.kind] || e.kind)}</td><td>${label(e)}</td><td>${how}</td><td>${state}</td></tr>`;
      }).join('');
      const reversiblePending = (d.effects || []).filter(e => pending.has(e.id) && e.reversible).length;
      const receipts = (d.receipts || []).map(r => `<li>${esc(r.kind === 'review' ? '사람 확인' : '보상')} · ${UI.chip(r.status)} · ${esc(r.request.by)} (${esc(roleName(r.request.role))}) · ${esc(r.request.reason)}${r.error ? ' · <span class="neg">' + esc(r.error) + '</span>' : ''}</li>`).join('');
      const body = `<p class="kv-line">${esc(UI.t('case'))} ${UI.chip(d.incident.state)} · ${esc(UI.t('command'))} ${esc(d.incident.cmdId || '없음')}</p>
        ${rows ? `<table class="inst-table"><thead><tr><th></th><th>종류</th><th>내용</th><th>처리 방법</th><th>상태</th></tr></thead><tbody>${rows}</tbody></table>` : '<p class="muted">기록된 외부 효과가 없습니다.</p>'}
        <div class="form"><section class="form-section"><h4>${esc(UI.t('form.section.who'))}</h4><div class="form-grid">
          ${UI.field({ label: UI.t('form.by'), required: true, input: `<input id="efBy" value="${esc(s.by)}" ${s.busy ? 'disabled' : ''}>` })}
          ${UI.field({ label: UI.t('form.role'), required: true, input: `<select id="efRole" ${s.busy ? 'disabled' : ''}><option value="">${esc(UI.t('form.pickRole'))}</option>${(d.review_roles || []).map(r => `<option value="${esc(r)}" ${r === s.role ? 'selected' : ''}>${esc(roleName(r))}</option>`).join('')}</select>` })}
          ${UI.field({ label: UI.t('form.reason'), required: true, cls: 'wide', input: `<textarea id="efReason" rows="2" ${s.busy ? 'disabled' : ''}>${esc(s.reason)}</textarea>` })}
        </div></section>
        ${UI.actions(`<button class="btn outline" id="efCompensate" ${!reversiblePending || s.busy ? 'disabled' : ''}>되돌릴 수 있는 거래 ${reversiblePending}건 보상 요청</button><button class="btn primary" id="efReview" ${!s.picked.size || s.busy ? 'disabled' : ''}>${esc(UI.t('btn.confirm'))} (${s.picked.size})</button>`, s.error)}</div>
        ${pending.size === 0 && (d.effects || []).length ? `<p class="rework-success" role="status">모든 효과가 해결됐습니다. ${esc(UI.t('inst.rework'))}에서 새 차수를 요청할 수 있습니다.</p>` : ''}
        ${receipts ? UI.fold(`확인 기록 ${(d.receipts || []).length}건`, `<ul>${receipts}</ul>`, { cls: 'small' }) : ''}
        ${s.notice ? `<p role="status">${esc(s.notice)}</p>` : ''}`;
      host.innerHTML = UI.fold(`${esc(UI.t('inst.effects'))} ${pending.size ? UI.chipText(`미해결 ${pending.size}`, 'warning') : ''}`, body, { open: pending.size > 0 });
      host.querySelectorAll('input[data-effect]').forEach(cb => cb.addEventListener('change', e => { e.target.checked ? s.picked.add(e.target.dataset.effect) : s.picked.delete(e.target.dataset.effect); draw(); }));
      host.querySelector('#efBy')?.addEventListener('input', e => s.by = e.target.value);
      host.querySelector('#efRole')?.addEventListener('change', e => s.role = e.target.value);
      host.querySelector('#efReason')?.addEventListener('input', e => s.reason = e.target.value);
      host.querySelector('#efCompensate')?.addEventListener('click', () => send('compensate', null));
      host.querySelector('#efReview')?.addEventListener('click', () => send('review', [...s.picked]));
    }
    async function send(kind, effects) {
      if (s.busy) return;
      if (!s.by.trim() || !s.role || !s.reason.trim()) { s.error = UI.t('form.err.byRoleReason'); draw(); return; }
      s.busy = true; s.error = ''; s.notice = ''; draw();
      const body = { request_id: crypto.randomUUID(), by: s.by, role: s.role, reason: s.reason, effects };
      try {
        const r = await postJ(API.process + '/api/instances/' + encodeURIComponent(id) + '/effects/' + kind, body);
        s.notice = kind === 'review' ? `확인 기록 저장 (${r.request_id})` : `보상 ${UI.status(r.status)} (${(r.results || []).filter(x => x.ok).length}/${(r.effects || []).length})`;
        if (r.status === 'FAILED') s.error = r.error || '보상 실패';
        s.picked.clear();
      } catch (e) { s.error = e.message; }
      s.busy = false;
      await load();
      if (changed) changed();
    }
    // Direct UI check 2026-10-06: the first load was cached per instance. Draw what we have, then re-read the effects every time the detail is (re)drawn.
    if (s.data) draw();
    load();
  }
  window.hydEffects = { mount };
})();
