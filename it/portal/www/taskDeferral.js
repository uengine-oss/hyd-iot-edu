/* A reassessment requests fresh evidence; it never approves an action. A122: same form frame as the other panels. */
(function () {
  const states = new Map();
  function mount(host, { view, by, changed }) {
    if (!host) return;
    const rows = view.workitems.filter(w => view.instance.status === 'RUNNING' && w.status === 'PENDING' && w.draft?._deferral
      && (w.generation || 0) === (view.instance.rework_generation || 0));
    host.innerHTML = '';
    // A lost response can outlive the original PENDING state. Keep its receipt lookup available even after the task advances or defers again.
    for (const w of view.workitems) {
      const prefix = 'hyd:reassess:' + w.id + ':';
      let keys = [];
      try { keys = Object.keys(sessionStorage).filter(k => k.startsWith(prefix)); } catch (_) {}
      for (const key of keys) {
        if (rows.some(r => key === 'hyd:reassess:' + r.id + ':' + r.draft._deferral.id)) continue;
        let request;
        try { request = JSON.parse(sessionStorage.getItem(key)); } catch (_) { continue; }
        if (!request?.request_id) continue;
        const panel = document.createElement('div');
        panel.innerHTML = UI.fold(`${esc(UI.t('inst.reassess'))} · 접수 확인 — ${esc(w.activity_name)}`, `<p>${esc(request.by)} · ${esc(request.reason)}</p>${UI.actions('<button class="btn" data-reassess-receipt>같은 요청의 접수 결과 확인</button>')}<p role="status"></p>`, { open: true });
        panel.querySelector('button').addEventListener('click', async e => {
          e.target.disabled = true;
          try {
            await postJ(API.process + `/api/todolist/${encodeURIComponent(w.id)}/reassess`, request);
            try { sessionStorage.removeItem(key); } catch (_) {}
            states.delete(key); await changed(); panel.remove();
          } catch (error) { panel.querySelector('[role=status]').textContent = error.message; e.target.disabled = false; }
        });
        host.appendChild(panel);
      }
    }
    rows.forEach(w => {
      const d = w.draft._deferral, key = 'hyd:reassess:' + w.id + ':' + d.id;
      if (!states.has(key)) {
        let pending = null;
        try { pending = JSON.parse(sessionStorage.getItem(key) || 'null'); } catch (_) {}
        states.set(key, { by: pending?.by || by || '', reason: pending?.reason || '', pending, error: '', busy: false });
      }
      const s = states.get(key), panel = document.createElement('div');
      panel.dataset.deferralTask = w.id;
      const draw = () => {
        const locked = s.busy || s.pending ? 'disabled' : '';
        panel.innerHTML = UI.fold(`${esc(UI.t('inst.reassess'))} — ${esc(w.activity_name)} ${UI.chipText('보류', 'warning')}`, `<p>${esc(d.reason)}</p>
          <p class="muted">${esc(UI.dateTime(d.at))} · ${d.assessment.status === 'UNKNOWN' ? '근거 확인 불가' : '현재 근거가 조건에 맞지 않음'}</p>
          ${UI.fold('관측 근거와 보류 기록', `<pre style="white-space:pre-wrap;overflow-wrap:anywhere">${esc(JSON.stringify(d.assessment.evidence, null, 2))}</pre>`, { cls: 'small' })}
          <div class="form"><section class="form-section"><h4>${esc(UI.t('form.section.who'))}</h4><div class="form-grid">
            ${UI.field({ label: UI.t('form.by'), required: true, input: `<input data-reassess-by value="${esc(s.by)}" ${locked}>` })}
            ${UI.field({ label: UI.t('form.reason'), required: true, cls: 'wide', hint: '원천을 다시 조회해 평가합니다. 조치가 제안되면 별도 선택 단계에서 확인합니다.', input: `<textarea data-reassess-reason rows="2" ${locked}>${esc(s.reason)}</textarea>` })}
          </div></section>${UI.actions(`<button class="btn primary" data-reassess ${s.busy ? 'disabled' : ''}>${s.pending ? '같은 요청의 접수 결과 확인' : esc(UI.t('btn.reassess'))}</button>`, s.error)}</div>`, { open: true });
        panel.querySelector('[data-reassess-by]').addEventListener('input', e => s.by = e.target.value);
        panel.querySelector('[data-reassess-reason]').addEventListener('input', e => s.reason = e.target.value);
        panel.querySelector('[data-reassess]').addEventListener('click', async () => {
          if (s.busy) return;
          if (!s.by.trim() || !s.reason.trim()) { s.error = UI.t('form.err.required'); draw(); return; }
          s.pending ||= { deferral_id: d.id, request_id: crypto.randomUUID(), by: s.by.trim(), reason: s.reason.trim() };
          try { sessionStorage.setItem(key, JSON.stringify(s.pending)); } catch (_) {}
          s.busy = true; s.error = ''; draw();
          try {
            await postJ(API.process + `/api/todolist/${encodeURIComponent(w.id)}/reassess`, s.pending);
            s.pending = null;
            try { sessionStorage.removeItem(key); } catch (_) {}
            await changed();
          } catch (e) { s.error = e.message; }
          finally { s.busy = false; if (panel.isConnected) draw(); }
        });
      };
      host.appendChild(panel); draw();
    });
  }
  window.hydTaskDeferral = { mount };
})();
