/* Rework is a reviewed new generation. A lost response replays the same request.
   Same form frame as the other panels — title + one hint → impact card → 담당자 · 역할 · 사유 → buttons bottom-right.
   막힘 사유 문장은 서버가 막힘마다 함께 준다(procsvc/rework.py BLOCKER_TEXT) — 화면은 그 문장을 그대로 보인다. */
(function () {
  const states = new Map();
  const key = id => 'hyd:rework:' + id;
  const valueName = k => UI.t('var.' + k) === 'var.' + k ? hydWords.fieldName(k) : UI.t('var.' + k);   // 화면 사전에 없는 값은 값 이름 사전(plainWords)으로
  const names = keys => keys.map(valueName).join(', ');
  function stateFor(view, by) {
    const id = view.instance.proc_inst_id;
    // 본 처리 건 상태만 들고 있는다 — 다른 처리 건 상태는 응답을 기다리는 요청이 없으면 버린다(세션 저장소에 요청이 따로 남는다)
    for (const [other, st] of states) if (other !== id && !st.pending) states.delete(other);
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
    // 입력 칸에서 글을 쓰는 중이면 다시 그리지 않는다(2초 다시 그리기가 한글 조합을 끊는다) — 칸을 벗어난 뒤 다음 그리기에서 반영된다
    const typing = document.activeElement;
    if (typing && host.contains(typing) && /^(INPUT|TEXTAREA|SELECT)$/.test(typing.tagName)) return;
    const id = view.instance.proc_inst_id, s = stateFor(view, by);
    if (s.preview && s.basis !== snapshot(view) && !s.pending) {
      s.preview = null; s.confirmed = false; s.error = '단계 상태가 바뀌었습니다. 영향 범위를 다시 확인하세요.';
    }
    const taskName = wid => { const name = (view.workitems || []).find(w => w.id === wid)?.activity_name; return name ? UI.flowName(name) : '이름을 찾지 못한 단계'; };
    const roleName = role => (view.definition.roles || []).find(r => r.endpoint === role)?.name || UI.who(role);
    const editable = () => !s.busy && !s.pending;
    const eligible = () => editable() && s.preview?.execution_available && s.by.trim() && s.role && s.reason.trim() && s.confirmed;
    function draw() {
      if (!host.isConnected) return;
      const list = choices(view), p = s.preview;
      const locked = !editable() ? 'disabled' : '';
      /* 요청 역할: 서버는 이 흐름에서 사람이 맡는 역할 가운데 하나만 받고(rework_runtime.request_rework), 이전 승인을 폐기할 때는 그 역할이 그 승인을
         할 수 있는 역할인지 본다(approval_delivery._discard_owner). 후보가 하나면 고를 것이 없으므로 그 값을 그대로 쓰고 한 줄로 보인다.
         여럿이면 어느 역할로 요청하는지에 따라 서버 판정이 달라지므로 고르게 둔다 — 첫 항목을 저절로 보내지 않는다. */
      const roles = p?.request_roles || (s.role ? [s.role] : []);
      if (p && roles.length === 1) s.role = roles[0];
      const roleField = !roles.length ? UI.readonly('요청 역할', p ? '<span class="neg">이 흐름에는 사람이 맡는 역할이 없어 다시 수행을 요청할 수 없습니다.</span>' : `<span class="muted">[${esc(UI.t('btn.effects'))}]를 누르면 표시됩니다.</span>`)
        : roles.length === 1 ? UI.readonly('요청 역할', esc(roleName(roles[0])), '이 흐름에서 사람이 맡는 역할이 하나뿐이라 이 역할로 요청합니다.')
        : UI.field({ label: '요청 역할', required: true, hint: '어느 역할로 다시 수행을 요청하는지 고릅니다. 이전 승인을 폐기해야 하면 그 승인을 할 수 있는 역할이어야 합니다.',
          input: `<select id="rwRole" ${locked}><option value="">${esc(UI.t('form.pickRole'))}</option>${roles.map(r => `<option value="${esc(r)}" ${r === s.role ? 'selected' : ''}>${esc(roleName(r))}</option>`).join('')}</select>` });
      let detail = '';
      if (p) {
        const effects = p.effects, inc = effects?.incident;
        const receipts = effects ? Object.values(effects.enterprise_receipts || {}).flat().length : null;
        detail = UI.card({ title: '영향 범위', cls: 'soft', body: `<p>시작: <b>${esc(taskName(p.start_workitem))}</b> · 영향받는 단계 ${esc(p.affected_workitems.length)}건 · 취소될 단계 ${esc(p.cancel_workitems.length)}건</p>
          <p>다시 만들 값: ${esc(names(p.invalidated_variables) || '없음')}<br>시작 값으로 되돌릴 값: ${esc(names(p.restored_input_variables) || '없음')}<br>앞 단계 결과를 그대로 쓸 값: ${esc(names(p.retained_outputs.map(x => x.variable)) || '없음')}</p>
          ${Object.values(p.reasons || {}).some(items => items.some(x => x.kind === 'condition_recheck')) ? '<p>바뀐 입력을 쓰는 분기 앞의 검토 단계도 다시 수행합니다.</p>' : ''}
          ${inc ? `<p>연결된 사건: ${UI.chip(inc.state)} · 설비 명령 ${inc.cmdId ? '보냄' : '보내지 않음'} · 업무 실행 기록 ${esc(receipts)}건 · 폐기할 이전 승인 ${esc((p.retire_approvals || []).length)}건</p>` : '<p>연결된 설비 사건이 없는 처리 건입니다.</p>'}
          ${p.blockers.length ? `<div class="rework-blocked"><b>추가 검토가 필요합니다</b><ul>${p.blockers.map(b => `<li>${esc(b.text)}${b.variable ? ` <small>(값: ${esc(valueName(b.variable))})</small>` : b.workitem ? ` <small>(단계: ${esc(taskName(b.workitem))})</small>` : ''}</li>`).join('')}</ul></div>` : '<p>새 차수를 요청할 수 있습니다. 접수 시 상태와 효과를 다시 확인합니다.</p>'}
          ${UI.fold(esc(UI.t('raw')), `<pre>${esc(JSON.stringify({ workitems: p.affected_workitems, reasons: p.reasons, candidate_variables: p.candidate_variables, blockers: p.blockers, effects: p.effects }, null, 2))}</pre>`, { cls: 'small' })}` });
      }
      const finished = view.instance.status !== 'RUNNING' && !s.pending;   // A091: a finished instance folds this panel to one line
      const body = `${s.success ? `<p class="rework-success" role="status">${esc(s.success.generation)}${esc(UI.t('inst.gen'))} 요청이 접수됐습니다. 새 단계의 진행과 사람 선택을 확인하세요.</p>` : ''}
        ${finished ? '<p class="muted">종료된 처리 건입니다. 다시 수행 이력만 남아 있습니다.</p>' : `<div class="form">
        <section class="form-section"><div class="form-grid">${UI.field({ label: '다시 시작할 단계', required: true, hint: '조건이나 판단 근거가 바뀌었다면 시작할 단계를 고릅니다. 이전 결과는 이력으로 남습니다.', input: `<select id="rwStart" ${locked}><option value="">${esc(UI.t('step'))} 선택</option>${list.map(w => `<option value="${esc(w.id)}" ${w.id === s.workitem ? 'selected' : ''}>${esc(UI.flowName(w.activity_name))}${w.generation ? ` · ${esc(w.generation)}${esc(UI.t('inst.gen'))}` : ''} · ${esc(UI.status(w.status))}</option>`).join('')}</select>` })}
          <div class="field"><label>&nbsp;</label><button class="btn outline" id="rwPreview" ${locked}>${esc(UI.t('btn.effects'))}</button></div></div></section>
        ${detail}
        <section class="form-section"><h4>${esc(UI.t('form.section.who'))}</h4><div class="form-grid">
          ${UI.actorInput('id="rwBy"', s.by, locked)}
          ${roleField}
          ${UI.field({ label: UI.t('form.reason'), required: true, cls: 'wide', input: `<textarea id="rwReason" rows="2" ${locked}>${esc(s.reason)}</textarea>` })}
        </div></section>
        ${s.pending ? `<p>앞 요청의 응답을 받지 못했습니다. 눌러서 처리됐는지 확인하세요. 같은 요청을 다시 확인하는 것이라 차수가 두 번 만들어지지 않습니다.</p>${UI.actions(`<button class="btn" id="rwRetry" ${s.busy ? 'disabled' : ''}>요청 결과 확인</button>`, s.error)}` : `
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
        s.pending = { workitem_id: s.workitem, request_id: UI.uuid(), snapshot_token: s.preview.snapshot_token,
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
