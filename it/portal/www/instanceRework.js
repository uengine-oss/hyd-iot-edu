/* Rework is a reviewed new generation. A lost response replays the same request.
   A122: same form frame as the other panels — title + one hint → impact card → 담당자 · 역할 · 사유 → buttons bottom-right (UIUX_PLAN §1.3). */
(function () {
  const states = new Map();
  const reasons = {
    instance_not_running: '종료된 처리 건은 다시 열지 않습니다.', initial_inputs_unavailable: '시작 값 원문이 없어 복원 범위를 확인해야 합니다.',
    start_workitem_superseded: '이 단계는 이미 다음 차수로 대체됐습니다.', start_workitem_not_reached: '아직 시작하지 않은 단계입니다.',
    ambiguous_workitem_order: '최신 단계를 하나로 결정할 수 없습니다.', ambiguous_previous_producer: '재사용할 선행 결과를 하나로 결정할 수 없습니다.',
    variable_provenance_requires_review: '값의 출처를 확인해야 합니다.', approval_requires_review: '기존 승인에 대한 검토가 필요합니다.',
    service_effects_require_review: '시작된 서비스의 실행 효과를 확인해야 합니다.', incident_rework_effect_contract_pending: '사건의 효과 조회가 연결되지 않았습니다.',
    dependency_restart_requires_scheduler: '다른 흐름에 있는 의존 단계의 재시작 순서를 검토해야 합니다.',
    condition_replay_requires_arrival: '조건을 다시 판단할 선행 단계의 실제 도달 근거를 확인해야 합니다.',
    dependency_control_arrival_unavailable: '이전 단계가 실제로 시작된 근거가 없어 자동으로 다시 열 수 없습니다.',
    ambiguous_dependency_producer: '새 입력을 생산하는 단계를 하나로 결정할 수 없습니다.',
    dependency_cycle_requires_review: '서로의 새 결과를 기다리는 순환 의존을 검토해야 합니다.',
    incident_not_active_for_rework: '현재 사건이 조치 선택 대기 상태가 아니거나 이미 해제됐습니다.',
    incident_effects_require_compensation: '설비 명령·응답 또는 정비 요청이 있어 기존 조치의 후속 검토가 필요합니다.',
    decision_effects_require_compensation: '판단에 연결된 업무 실행 기록이 있습니다. 기존 효과를 먼저 검토해야 합니다.',
    current_decision_original_missing: '현재 판단 원문을 찾을 수 없습니다.', rework_requires_new_decision: '새 판단을 만드는 에이전트 단계부터 선택하세요.',
    approval_decision_original_missing: '승인에 연결된 판단 원문을 찾을 수 없습니다.', approval_effects_require_review: '전달된 승인 또는 다른 단계의 승인이 있어 별도 검토가 필요합니다.',
    untracked_decision_consent: '승인 내역의 출처를 확인할 수 없습니다.'
  };
  const key = id => 'hyd:rework:' + id;
  function stateFor(view, by) {
    const id = view.instance.proc_inst_id;
    if (!states.has(id)) {
      let pending = null;
      try { pending = JSON.parse(sessionStorage.getItem(key(id)) || 'null'); } catch (_) { /* Storage unavailable: in-memory retry still works. */ }
      states.set(id, { workitem: pending?.workitem_id || '', by: pending?.by || by || '', role: pending?.role || '',
        reason: pending?.reason || '', preview: null, confirmed: false, busy: false, error: '', pending, success: null });
    }
    const s = states.get(id);
    const receipt = s.pending && (view.reworks || []).find(r => r.request_id === s.pending.request_id);
    if (receipt) completed(s, id, receipt.result);
    return s;
  }
  function completed(s, id, result) {
    s.success = result; s.pending = null; s.preview = null; s.workitem = ''; s.confirmed = false; s.reason = ''; s.error = '';
    try { sessionStorage.removeItem(key(id)); } catch (_) { /* In-memory state remains authoritative for this page. */ }
  }
  function snapshot(view) { return JSON.stringify([view.instance, view.workitems, view.approvals]); }
  function choices(view) {
    const activities = new Set((view.definition.activities || []).map(a => a.id));
    const latest = new Map();
    (view.workitems || []).forEach(w => {
      const old = latest.get(w.activity_id);
      if (!old || (w.generation || 0) > (old.generation || 0) || ((w.generation || 0) === (old.generation || 0) && w.start_date > old.start_date)) latest.set(w.activity_id, w);
    });
    return [...latest.values()].filter(w => activities.has(w.activity_id) && ['DONE', 'PENDING', 'IN_PROGRESS', 'SUBMITTED'].includes(w.status));
  }
  function mount(host, { view, by, changed }) {
    if (!host) return;
    const id = view.instance.proc_inst_id, s = stateFor(view, by);
    if (s.preview && s.basis !== snapshot(view) && !s.pending) {
      s.preview = null; s.confirmed = false; s.error = '단계 상태가 바뀌었습니다. 영향 범위를 다시 확인하세요.';
    }
    const taskName = wid => (view.workitems || []).find(w => w.id === wid)?.activity_name || wid;
    const roleName = role => (view.definition.roles || []).find(r => r.endpoint === role)?.name || UI.who(role);
    const editable = () => !s.busy && !s.pending;
    const eligible = () => editable() && s.preview?.execution_available && s.by.trim() && s.role && s.reason.trim() && s.confirmed;
    function draw() {
      if (!host.isConnected) return;
      const list = choices(view), p = s.preview;
      const locked = !editable() ? 'disabled' : '';
      let detail = '';
      if (p) {
        const effects = p.effects, inc = effects?.incident;
        const receipts = effects ? Object.values(effects.enterprise_receipts || {}).flat().length : null;
        detail = UI.card({ title: '영향 범위', cls: 'soft', body: `<p>시작: <b>${esc(taskName(p.start_workitem))}</b> · 영향받는 단계 ${esc(p.affected_workitems.length)}건 · 취소될 단계 ${esc(p.cancel_workitems.length)}건</p>
          <p>무효화할 값: ${esc(p.invalidated_variables.join(', ') || '없음')}<br>시작 값으로 복원: ${esc(p.restored_input_variables.join(', ') || '없음')}<br>선행 결과 재사용: ${esc(p.retained_outputs.map(x => x.variable).join(', ') || '없음')}</p>
          ${Object.values(p.reasons || {}).some(items => items.some(x => x.kind === 'condition_recheck')) ? '<p>바뀐 입력을 쓰는 분기 앞의 검토 단계도 다시 수행합니다.</p>' : ''}
          ${inc ? `<p>${esc(UI.t('case'))} ${UI.chip(inc.state)} · ${esc(UI.t('command'))} ${esc(inc.cmdId || '없음')} · 업무 실행 기록 ${esc(receipts)}건 · 이전 승인 폐기 ${esc((p.retire_approvals || []).length)}건</p>` : '<p>연결된 설비 사건이 없는 일반 프로세스입니다.</p>'}
          ${p.blockers.length ? `<div class="rework-blocked"><b>추가 검토가 필요합니다</b><ul>${p.blockers.map(b => `<li>${esc(reasons[b.code] || '지원 범위를 확인해야 합니다.')} ${esc(b.variable || (b.workitem ? taskName(b.workitem) : '') || '')}</li>`).join('')}</ul></div>` : '<p>새 차수를 요청할 수 있습니다. 접수 시 상태와 효과를 다시 확인합니다.</p>'}
          ${UI.fold(esc(UI.t('raw')), `<pre>${esc(JSON.stringify({ workitems: p.affected_workitems, reasons: p.reasons, candidate_variables: p.candidate_variables, blockers: p.blockers, effects: p.effects }, null, 2))}</pre>`, { cls: 'small' })}` });
      }
      const finished = view.instance.status !== 'RUNNING' && !s.pending;   // A091: a finished instance folds this panel to one line
      const body = `${s.success ? `<p class="rework-success" role="status">${esc(s.success.generation)}${esc(UI.t('inst.gen'))} 요청이 접수됐습니다. 새 단계의 진행과 사람 선택을 확인하세요.</p>` : ''}
        ${finished ? '<p class="muted">종료된 처리 건입니다. 다시 수행 이력만 남아 있습니다.</p>' : `<div class="form">
        <section class="form-section"><div class="form-grid">${UI.field({ label: '다시 시작할 단계', required: true, hint: '조건이나 판단 근거가 바뀌었다면 시작할 단계를 고릅니다. 이전 결과는 이력으로 남습니다.', input: `<select id="rwStart" ${locked}><option value="">${esc(UI.t('step'))} 선택</option>${list.map(w => `<option value="${esc(w.id)}" ${w.id === s.workitem ? 'selected' : ''}>${esc(w.activity_name)} · ${esc(w.generation || 0)}${esc(UI.t('inst.gen'))} · ${esc(UI.status(w.status))}</option>`).join('')}</select>` })}
          <div class="field"><label>&nbsp;</label><button class="btn outline" id="rwPreview" ${locked}>${esc(UI.t('btn.effects'))}</button></div></div></section>
        ${detail}
        <section class="form-section"><h4>${esc(UI.t('form.section.who'))}</h4><div class="form-grid">
          ${UI.field({ label: UI.t('form.by'), required: true, input: `<input id="rwBy" value="${esc(s.by)}" ${locked}>` })}
          ${UI.field({ label: UI.t('form.role'), required: true, input: `<select id="rwRole" ${locked}><option value="">${p ? esc(UI.t('form.pickRole')) : '영향 확인 후 선택'}</option>${(p?.request_roles || (s.role ? [s.role] : [])).map(r => `<option value="${esc(r)}" ${r === s.role ? 'selected' : ''}>${esc(roleName(r))}</option>`).join('')}</select>` })}
          ${UI.field({ label: UI.t('form.reason'), required: true, cls: 'wide', input: `<textarea id="rwReason" rows="2" ${locked}>${esc(s.reason)}</textarea>` })}
        </div></section>
        ${s.pending ? `<p>응답을 확인하지 못한 요청이 있습니다. 같은 요청의 결과를 확인하며 중복 차수를 만들지 않습니다.</p>${UI.actions(`<button class="btn" id="rwRetry" ${s.busy ? 'disabled' : ''}>같은 요청 결과 다시 확인</button>`)}` : `
        <label class="check"><input type="checkbox" id="rwConfirm" ${s.confirmed ? 'checked' : ''} ${!p?.execution_available || s.busy ? 'disabled' : ''}> 영향 범위와 이전 승인 처리 내용을 확인했습니다.</label>
        ${UI.actions(`<button class="btn primary" id="rwSubmit" ${eligible() ? '' : 'disabled'}>${esc(UI.t('btn.rework'))}</button>`, s.error)}`}</div>`}
        ${s.busy ? '<p role="status">처리 중입니다…</p>' : ''}${finished && s.error ? `<p class="neg" role="alert">${esc(s.error)}</p>` : ''}`;
      host.innerHTML = UI.fold(esc(UI.t('inst.rework')), body, { open: !finished && (!!s.workitem || !!s.pending) });
      host.querySelector('#rwStart')?.addEventListener('change', e => {
        s.workitem = e.target.value; s.preview = null; s.confirmed = false; s.error = ''; draw();
      });
      for (const [field, selector] of [['by', '#rwBy'], ['role', '#rwRole'], ['reason', '#rwReason']]) {
        const update = e => {
          s[field] = e.target.value; s.confirmed = false;
          const confirm = host.querySelector('#rwConfirm'); if (confirm) confirm.checked = false;
          const submit = host.querySelector('#rwSubmit'); if (submit) submit.disabled = !eligible();
        };
        host.querySelector(selector)?.addEventListener('input', update);
        host.querySelector(selector)?.addEventListener('change', update);
      }
      host.querySelector('#rwConfirm')?.addEventListener('change', e => { s.confirmed = e.target.checked; host.querySelector('#rwSubmit').disabled = !eligible(); });
      host.querySelector('#rwPreview')?.addEventListener('click', preview);
      host.querySelector('#rwSubmit')?.addEventListener('click', () => { if (eligible()) send(); });
      host.querySelector('#rwRetry')?.addEventListener('click', () => { if (!s.busy) send(); });
    }
    async function preview() {
      if (!editable()) return;
      if (!s.workitem) { s.error = '다시 시작할 단계를 선택하세요.'; draw(); return; }
      s.busy = true; s.preview = null; s.confirmed = false; s.error = ''; draw();
      try {
        s.preview = await getJ(API.process + `/api/instances/${encodeURIComponent(id)}/rework-preview?workitem_id=${encodeURIComponent(s.workitem)}`);
        s.basis = snapshot(view);
      } catch (e) { s.error = e.message; }
      finally { s.busy = false; draw(); if (!host.isConnected) await changed(); }
    }
    async function send() {
      if (!s.pending) {
        s.pending = { workitem_id: s.workitem, request_id: crypto.randomUUID(), snapshot_token: s.preview.snapshot_token,
                      by: s.by.trim(), role: s.role, reason: s.reason.trim() };
        try { sessionStorage.setItem(key(id), JSON.stringify(s.pending)); } catch (_) { /* Retain exact request in memory. */ }
      }
      s.busy = true; s.error = ''; draw();
      try {
        const result = await postJ(API.process + `/api/instances/${encodeURIComponent(id)}/rework`, s.pending);
        completed(s, id, result);
      } catch (e) {
        s.error = e.message;
        if (e.status >= 400 && e.status < 500) {
          s.pending = null; s.preview = null; s.confirmed = false;
          try { sessionStorage.removeItem(key(id)); } catch (_) { /* no persistent pending request */ }
          s.error += ' 영향 범위를 다시 확인한 뒤 요청하세요.';
        }
      } finally { s.busy = false; draw(); await changed(); }
    }
    draw();
  }
  window.hydRework = { mount };
})();
