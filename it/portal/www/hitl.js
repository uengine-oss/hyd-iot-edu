/* 조치 선택 패널 · 업무 흐름(승인과 실행) · 조치 방법 목록 · 매뉴얼 등록 · 업무 데이터 연결 (loaded after app.js / enterprise.js / main.js / flow.js).
   - 조치 선택 패널 (이상 확인 · 조치): the agent's ranked action candidates → one human decision. In instance mode the decision is made in the
     처리 건 screen (the legacy /decide endpoint answers 409 there — A122 UIUX_PLAN §1.2), so the panel links there instead of showing a form.
   - 업무 흐름: hydFlow draws the definition of the instance behind the selected decision (UIUX_PLAN §4).
   - 조치 방법: list / edit skills; add a new skill matched to a failure mode (written by the process service)
   - 매뉴얼 등록 · 업무 데이터 연결 (지식 관리 탭) */
(function () {
  const H = { inc: null, decs: [], dec: null, sig: null, form: { option: null, reason: '', role: null, by: 'OP-17', fan: null, load: null }, msg: '', busy: false,
    skills: [], catalog: null, skillSel: null, skillNew: false, skillDrafts: new Map(), preview: null, mode: null, instByIncident: new Map() };
  getJ(API.process + '/api/process/mode').then(m => { H.mode = m; }).catch(() => { H.mode = null; });
  const instanceMode = () => !H.mode || H.mode.mode === 'instance';

  /* ================================================= 조치 선택 패널 (이상 확인 · 조치) */
  async function refreshHitl(force) {
    const box = document.getElementById('hitlPanel'); if (!box) return;
    const inc = state.tab === 'incidents' ? state.detail : null;
    if (!inc) { if (box.innerHTML) box.innerHTML = ''; H.sig = null; return; }
    let decs = [];
    try { decs = (await getJ(API.process + '/api/decisions')).filter(d => (d.origin || {}).incident === inc.id); } catch (e) { }
    const prim = decs[0] || null;
    let dec = null;
    if (prim) { try { dec = await getJ(API.process + '/api/decisions/' + prim.id); } catch (e) { } }
    if (state.tab !== 'incidents' || state.detail?.id !== inc.id) return;
    const sig = [inc.id, inc.state, decs.length, dec && dec.id, dec && dec.state, H.msg, H.mode && H.mode.mode].join('|');
    if (!force && sig === H.sig) return;
    if (H.inc && (H.inc.id !== inc.id || H.dec?.id !== dec?.id)) H.form = { option: null, reason: '', role: null, by: 'OP-17', fan: null, load: null };
    H.sig = sig; H.inc = inc; H.decs = decs; H.dec = dec;
    renderHitl();
  }
  const cmdOf = (o, param) => ((o && o.actions) || []).find(a => a.kind === 'command' && a.param === param);
  function decidedCard(d, inc) {
    const opts = d.options || [];
    const ch = opts.find(o => o.id === d.chosen) || {};
    const approved = (d.history || []).find(h => h.state === 'APPROVED' || h.state === 'REJECTED');
    const roleName = ((d.roles || {})[d.approvedRole] || {}).name || d.approvedRole || '';
    return UI.card({ title: esc(ch.name || d.chosen || UI.t('decision')), chips: UI.chip(d.state) + (d.override ? UI.chipText(UI.t('proc.override'), 'warning') : ''),
      value: `<span class="kv">${esc(d.approvedBy || '–')}<small>${esc(roleName)}</small></span>${approved ? `<span class="kv"><small>${esc(UI.dateTime(approved.t))}</small></span>` : ''}`,
      sub: d.reason ? `${esc(UI.t('inc.reasonLabel'))}: ${esc(d.reason)}` : '',
      body: (d.executions || []).length ? `<div class="cards two">${d.executions.map(x => UI.card({ title: esc(UI.who(x.system) + (x.code ? ' · ' + hydCards.actionLabel({ code: x.code }) : '')), chips: UI.chip(x.status), value: x.ref ? `<span class="kv mono">${esc(x.ref)}</span>` : '', sub: esc(x.detail || ''), cls: 'soft' })).join('')}</div>` : '' });
  }
  function renderHitl() {
    const box = document.getElementById('hitlPanel'); const inc = H.inc, d = H.dec;
    let html = '<section class="hitl">';
    if (!d) {
      html += inc.state === 'AWAITING_APPROVAL' ? UI.empty(UI.t('inc.waiting'), '', 'compact') : UI.empty(UI.t('inc.noCandidates'), `${UI.status(inc.state)}${inc.reason ? ' · ' + inc.reason : ''}`, 'compact');
      box.innerHTML = html + '</section>'; return;
    }
    const opts = d.options || [];
    const maxAbs = Math.max(1, ...opts.map(o => Math.abs(o.score || 0)));
    const pending = d.state === 'PENDING_APPROVAL';
    const legacy = !instanceMode();
    if (!H.form.option) H.form.option = d.recommended || (opts.find(o => o.feasible) || opts[0] || {}).id;
    const chosenOpt = opts.find(o => o.id === H.form.option);
    const fanA = cmdOf(chosenOpt, 'fan_pct'), loadA = cmdOf(chosenOpt, 'load_pct'), pumpA = cmdOf(chosenOpt, 'pump');
    if (H.form.cardFor !== H.form.option) { H.form.fan = fanA ? fanA.value : null; H.form.load = loadA ? loadA.value : null; H.form.cardFor = H.form.option; }
    const parameters = { ...(fanA ? { fan_pct: H.form.fan } : {}), ...(loadA ? { load_pct: H.form.load } : {}) };
    const review = window.hydCards?.reviewMatches(H.form.review, d.id, H.form.option, parameters, { kind: "legacy", incident: inc.id }) ? H.form.review : null;
    const reviewed = review?.snapshot?.options?.[0];
    const changed = (fanA && H.form.fan !== fanA.value) || (loadA && H.form.load !== loadA.value);
    const canApprove = reviewed ? reviewed.feasible : chosenOpt?.feasible && !changed;
    const roles = Object.entries(review?.snapshot?.roles || d.roles || {}).sort((a, b) => a[1].level - b[1].level);
    if (!H.form.role) H.form.role = ((chosenOpt && chosenOpt.approver) || {}).id || (roles[0] || [''])[0];
    const sc = d.scenario || {};
    html += `<div class="detail-head"><div class="row"><h2 style="font-size:16px">${esc(pending ? UI.t('select') : UI.t('decision'))}</h2>${UI.chip(d.state)}</div><div class="sub">${esc(sc.failureMode || '')}${sc.cause ? ' · ' + esc(sc.cause) : ''}</div></div>`;
    html += summaryBlock(d.explanation);
    if (pending && !legacy) {
      // 409 in instance mode: the choice is made in the 처리 건 screen — one link, no dead form (UIUX_PLAN §1.2)
      html += '<div class="hitl-opts">' + opts.map(o => hydCards.cardHtml(o, { rec: d.recommended, chosen: d.chosen, maxAbs })).join('') + '</div>';
      html += UI.actions(`<button class="btn primary" id="hGoInstance">${esc(UI.t('btn.goInstance'))}</button>`);
    } else if (pending) {
      const live = inc.state === 'AWAITING_APPROVAL';
      html += `<div class="form">` +
        UI.section(UI.t('form.section.case'), `<div class="ro-grid wide">${UI.readonly(UI.t('dec.asset'), esc(inc.asset))}${UI.readonly('고장 유형', esc(sc.failureMode || '–'))}${UI.readonly(UI.t('dec.cause'), esc(sc.cause || '–'))}${UI.readonly(UI.t('inc.alertAt'), esc(UI.dateTime(inc.created)))}</div>`) +
        UI.section(UI.t('form.section.choice'), `<div class="hitl-opts wide">${opts.map(o => hydCards.cardHtml(o, { rec: d.recommended, chosen: d.chosen, selectable: true, reviewable: true, selected: H.form.option === o.id, pending, maxAbs })).join('')}</div>` +
          (live && (fanA || loadA || pumpA) ? `<div class="form-grid wide">${pumpA ? UI.readonly(UI.t('form.pump'), esc(pumpA.value)) : ''}${fanA ? hydCards.rangeField('hFan', UI.t('form.fan'), fanA, H.form.fan) : ''}${loadA ? hydCards.rangeField('hLoad', UI.t('form.load'), loadA, H.form.load) : ''}</div>` : '') +
          `<div class="wide" id="hReviewed">${reviewed ? `<p class="kv-line"><b>${esc(UI.t('card.reviewed'))}</b> · ${esc(UI.time(review.created))}</p>${hydCards.cardHtml(reviewed, { maxAbs })}` : `<p class="field-hint">${esc(UI.t('form.hint.preview'))}</p>`}</div>`) +
        hydCards.whoFields('h', H.form, roles) +
        UI.actions(`<button class="btn outline" id="hPreview" ${live && !H.busy && H.form.option ? '' : 'disabled'}>${esc(UI.t('btn.preview'))}</button><button class="btn primary" id="hGo" ${live && canApprove && !H.busy ? '' : 'disabled'}>${esc(UI.t('btn.decide'))}</button>`, H.msg) + '</div>';
    } else {
      html += decidedCard(d, inc);
      html += UI.fold(`${esc(UI.t('candidate'))} <span class="chip tone-neutral sm">${opts.length}</span>`, '<div class="hitl-opts">' + opts.map(o => hydCards.cardHtml(o, { rec: d.recommended, chosen: d.chosen, maxAbs })).join('') + '</div>', { cls: 'plain' });
    }
    html += '</section>';
    box.innerHTML = html;
    box.querySelectorAll('input[name=hopt]').forEach(r => r.addEventListener('change', () => { H.form.option = r.value; H.form.review = null; H.msg = ''; const o = (H.dec.options || []).find(x => x.id === r.value); if (o && o.approver) H.form.role = o.approver.id; renderHitl(); }));
    const on = (id, ev, fn) => { const e = document.getElementById(id); if (e) e.addEventListener(ev, fn); };
    const invalidate = () => { H.form.review = null; const go = $('#hGo'); if (go) go.disabled = true; const r = $('#hReviewed'); if (r) r.innerHTML = `<p class="field-hint">${esc(UI.t('form.hint.preview'))}</p>`; };
    on('hFan', 'input', e => { H.form.fan = +e.target.value; e.target.nextElementSibling.textContent = e.target.value + ' %'; invalidate(); });
    on('hLoad', 'input', e => { H.form.load = +e.target.value; e.target.nextElementSibling.textContent = e.target.value + ' %'; invalidate(); });
    on('hFan', 'change', renderHitl); on('hLoad', 'change', renderHitl);
    on('hBy', 'input', e => H.form.by = e.target.value);
    on('hRole', 'change', e => { H.form.role = e.target.value; H.msg = ''; });
    on('hReason', 'input', e => H.form.reason = e.target.value);
    on('hGo', 'click', decideNow);
    on('hPreview', 'click', () => previewChoice(parameters));
    on('hGoInstance', 'click', async () => {
      const b = $('#hGoInstance'); b.disabled = true;
      try {
        let id = H.instByIncident.get(inc.id);
        if (!id) { const list = await getJ(API.process + '/api/instances?limit=50'); const found = list.find(x => (x.variables_data || []).some(v => v.key === 'incident' && v.value === inc.id)); if (found) { id = found.proc_inst_id; H.instByIncident.set(inc.id, id); } }
        selectTab('instances'); if (id && window.hydInstancesSelect) window.hydInstancesSelect(id);
      } finally { b.disabled = false; }
    });
  }
  async function previewChoice(parameters) {
    if (H.busy) return; H.busy = true; H.msg = ''; renderHitl();
    const form = H.form, decision = H.dec.id, option = form.option;
    try { const review = await postJ(API.process + `/api/incidents/${encodeURIComponent(H.inc.id)}/decision-preview`, { decision, option, parameters });
      if (H.form === form && H.dec?.id === decision && H.form.option === option) H.form.review = review;
    } catch (e) { if (H.form === form) { H.form.review = null; H.msg = e.message; } }
    finally { H.busy = false; if (H.inc) renderHitl(); }
  }
  async function decideNow() {
    if (H.busy) return; H.busy = true;
    const go = $('#hGo'); if (go) { go.disabled = true; go.textContent = '처리 중…'; }
    try {
      await postJ(API.process + `/api/incidents/${H.inc.id}/decide`, { decision: H.dec.id, option: H.form.option, by: H.form.by || '승인자', role: H.form.role,
        reason: H.form.reason, fan_pct: H.form.fan, load_pct: H.form.load, review_id: matchingReviewId(H.form, H.dec) });
      H.msg = '';
      await refreshSlow();
    } catch (e) { H.msg = e.message; }
    finally { H.busy = false; await refreshHitl(true); }
  }
  function matchingReviewId(form, decision) {
    const option = decision?.options?.find(o => o.id === form.option);
    const parameters = { ...(cmdOf(option, 'fan_pct') ? { fan_pct: form.fan } : {}), ...(cmdOf(option, 'load_pct') ? { load_pct: form.load } : {}) };
    return window.hydCards?.reviewMatches(form.review, decision?.id, form.option, parameters, { kind: "legacy", incident: H.inc.id }) ? form.review.id : null;
  }
  window.hydHitl = { H, refreshHitl, decideNow };
  setInterval(() => refreshHitl(false), 1500);

  /* ================================================= 승인과 실행: 업무 흐름 — the instance behind the selected decision, drawn from its definition */
  async function instanceFor(incId) {
    if (!incId) return null;
    let id = H.instByIncident.get(incId);
    if (!id) {
      try { const list = await getJ(API.process + '/api/instances?limit=50'); const found = list.find(x => (x.variables_data || []).some(v => v.key === 'incident' && v.value === incId)); if (found) { id = found.proc_inst_id; H.instByIncident.set(incId, id); } } catch (e) { }
    }
    if (!id) return null;
    try { return await getJ(API.process + '/api/instances/' + encodeURIComponent(id)); } catch (e) { return null; }
  }
  async function refreshProcBpmn() {
    if (state.tab !== 'process') return;
    const box = document.getElementById('procBpmn'); if (!box || !window.hydFlow) return;
    const d = hydEnt.ent.decDetail;
    const incId = d && (d.origin || {}).incident;
    const view = await instanceFor(incId);
    if (state.tab !== 'process' || hydEnt.ent.decDetail?.id !== d?.id) return;
    const sig = [d && d.id, view && view.instance.status, view && view.workitems.map(w => w.id + w.status).join(',')].join('|');
    if (box.dataset.sig === sig) return; box.dataset.sig = sig;
    if (view) {
      hydFlow.mount(box, hydFlow.render(view.definition, { workitems: view.workitems, instance: view.instance, caption: `<b>${esc(view.instance.proc_inst_name)}</b> ${UI.chip(view.instance.status)}` }), view.instance.proc_inst_id);
    } else {
      const def = await hydFlow.latestDefinition();
      if (state.tab !== 'process') return;
      hydFlow.mount(box, hydFlow.render(def, { caption: esc(d ? UI.t('proc.flowManual') : UI.t('proc.flowEmpty')) }), 'overview');
    }
  }
  setInterval(refreshProcBpmn, 2000);

  /* ================================================= 조치 방법 — Skill = SOP, matched to a failure mode */
  const REL_KO = { MITIGATED_BY: UI.t('skill.rel.mitigate'), REMEDIED_BY: UI.t('skill.rel.remedy') };
  const draftKey = key => 'hyd:skill-edit:' + key;
  function saveSkillDraft(key, draft) {
    H.skillDrafts.set(key, draft);
    try { sessionStorage.setItem(draftKey(key), JSON.stringify(draft)); } catch (_) { /* Same-page retry remains available. */ }
  }
  function clearSkillDraft(key) {
    H.skillDrafts.delete(key);
    try { sessionStorage.removeItem(draftKey(key)); } catch (_) { /* In-memory copy has been cleared. */ }
  }
  async function loadSkills() {
    if (!H.skills.length) $('#skillList').innerHTML = `<div class="muted" role="status">${esc(UI.t('loading'))}</div>`;
    try { H.skills = await getJ(API.process + '/api/kg/skills'); } catch (e) { $('#skillList').innerHTML = UI.empty(UI.t('error.load'), e.message, 'compact'); return; }
    if (!H.catalog) { try { H.catalog = await getJ(API.process + '/api/kg/catalog'); } catch (e) { H.catalog = { roles: [], failureModes: [], manualSections: [] }; } }
    if (!H.skillSel && H.skills.length && !H.skillNew) H.skillSel = H.skills[0].id;
    renderSkillList(); renderSkillDetail();
  }
  function renderSkillList() {
    const list = $('#skillList'); list.innerHTML = '';
    for (const k of H.skills) {
      const it = el('div', 'item' + (k.id === H.skillSel && !H.skillNew ? ' sel' : ''));
      keyboardItem(it);
      const fm = (k.failureModes || []).map(f => `${f.name} (${REL_KO[f.relation] || f.relation})`).join(', ');
      it.innerHTML = `<div class="row"><strong>${esc(k.name)}</strong>${UI.chipText(k.kind === 'control' ? UI.t('skill.kind.control') : UI.t('skill.kind.workOrder'), k.kind === 'control' ? 'accent' : 'warning')}</div><span class="sub">${esc(k.sopId || '')} · ${esc(fm || UI.t('skill.noFm'))} · ${esc(UI.t('card.approver'))} ${esc((k.approver || {}).name || '–')}</span>`;
      it.addEventListener('click', () => { H.skillSel = k.id; H.skillNew = false; renderSkillList(); renderSkillDetail(); UI.revealDetail($('#skillDetail')); });
      list.append(it);
    }
  }
  function renderSkillDetail() {
    const box = $('#skillDetail'); const c = H.catalog || { roles: [], failureModes: [] };
    const key = H.skillNew ? '__new__' : H.skillSel;
    if (box.dataset.key === key && box.querySelector('#skName')) return;
    box.dataset.key = key || '';
    const k = H.skillNew ? { id: '', name: '', description: '', sopId: '', steps: [], failureModes: [], actions: [], rules: [], affects: [], causes: [], performers: [] }
      : H.skills.find(x => x.id === H.skillSel);
    if (!k) { box.innerHTML = UI.empty(UI.t('skill.select')); return; }
    const sel = (id, items, cur) => `<select id="${id}">${items.map(x => `<option value="${esc(x.id)}" ${cur === x.id ? 'selected' : ''}>${esc(x.name)}</option>`).join('')}</select>`;
    const newForm = H.skillNew ? UI.section('대상과 종류',
      UI.field({ label: UI.t('skill.sop'), required: true, input: `<input id="skSop" placeholder="SOP-FAN-05" maxlength="40">` }) +
      UI.field({ label: UI.t('skill.fm'), required: true, input: sel('skFm', c.failureModes || [], '') }) +
      UI.field({ label: UI.t('skill.relation'), input: `<select id="skRel"><option value="REMEDIED_BY">${esc(UI.t('skill.rel.remedy'))}</option><option value="MITIGATED_BY">${esc(UI.t('skill.rel.mitigate'))}</option></select>` }) +
      UI.field({ label: UI.t('skill.kind'), input: `<select id="skKind"><option value="work_order">${esc(UI.t('skill.kind.workOrder'))}</option><option value="control">${esc(UI.t('skill.kind.control'))}</option></select>` }) +
      UI.field({ label: UI.t('skill.steps'), required: true, cls: 'wide', input: `<textarea id="skSteps" rows="5" placeholder="현장 제어로 전환하고 잠근다.&#10;벨트를 교체한다.&#10;재가동 후 진동 0.9 mm/s 미만을 확인한다."></textarea>` })) : '';
    const linked = H.skillNew ? '' : `<h3 style="font-size:14px;margin:var(--s4) 0 var(--s2)">${esc(UI.t('skill.stepsTitle'))}</h3><ol class="steps">${(k.steps || []).map(s => `<li>${esc(s.text)} ${s.manual ? `<span class="muted">[${esc(s.manual)}]</span>` : ''}</li>`).join('') || `<li class="muted">${esc(UI.t('skill.noSteps'))}</li>`}</ol>
      <h3 style="font-size:14px;margin:var(--s4) 0 var(--s2)">${esc(UI.t('skill.linked'))}</h3><table class="kvt">
        <tr><th>${esc(UI.t('skill.fm'))}</th><td>${(k.failureModes || []).map(f => `${esc(f.name)} <span class="muted">(${esc(REL_KO[f.relation] || f.relation)})</span>`).join('<br>') || esc(UI.t('skill.none'))}</td></tr>
        <tr><th>${esc(UI.t('skill.causes'))}</th><td>${(k.causes || []).map(x => esc(x.name)).join(', ') || esc(UI.t('skill.allCauses'))}</td></tr>
        <tr><th>${esc(UI.t('skill.actions'))}</th><td>${(k.actions || []).map(a => `${esc(hydCards.actionLabel(a))} <span class="muted">${esc(a.name)}</span>`).join('<br>') || esc(UI.t('skill.none'))}</td></tr>
        <tr><th>${esc(UI.t('skill.rules'))}</th><td>${(k.rules || []).map(r => `<span class="${r.effect === 'EXCLUDE' ? 'hard' : r.effect === 'SELECT' ? '' : 'soft'}">${esc({ EXCLUDE: UI.t('chip.excluded'), SELECT: '후보', PENALTY: UI.t('card.penalty'), WARN: UI.t('card.warn') }[r.effect] || r.effect)} · ${esc(r.annotation || r.id)}</span>`).join(' ') || esc(UI.t('skill.none'))}</td></tr>
        <tr><th>${esc(UI.t('skill.affects'))}</th><td>${(k.affects || []).map(a => `${esc(a.name)} ${a.sign > 0 ? '↑' : '↓'}`).join(', ') || esc(UI.t('skill.none'))}</td></tr></table>`;
    box.innerHTML = `<div class="detail-head"><div class="row"><h2>${esc(H.skillNew ? UI.t('skill.new') : k.name)}</h2>${k.kind ? UI.chipText(k.kind === 'control' ? UI.t('skill.kind.control') : UI.t('skill.kind.workOrder'), k.kind === 'control' ? 'accent' : 'warning') : ''}</div>${k.sopId ? `<div class="sub">${esc(k.sopId)}</div>` : ''}</div>
      <div class="form skill-edit">` +
      UI.section(UI.t('method'),
        UI.field({ label: UI.t('skill.name'), required: true, input: `<input id="skName" value="${esc(k.name)}" maxlength="80">` }) +
        UI.field({ label: UI.t('skill.approver'), input: sel('skRole', c.roles || [], (k.approver || {}).id || 'role:maint-mgr') }) +
        UI.field({ label: UI.t('skill.desc'), cls: 'wide', input: `<textarea id="skDesc" rows="2">${esc(k.description || '')}</textarea>` })) + newForm +
      UI.section(UI.t('form.section.who'), UI.field({ label: UI.t('form.by'), input: `<input id="skBy" value="지식 관리자">` })) +
      UI.actions(`<button class="btn outline" id="skReload">${esc(UI.t('btn.cancel'))}</button><button class="btn primary" id="skSave">${esc(H.skillNew ? UI.t('skill.add') : UI.t('btn.save'))}</button>`) +
      `<span id="skMsg" class="muted" role="status"></span></div>
      ${k.source_document ? `<p class="kv-line">${esc(UI.t('skill.fromDoc'))} <button class="btn small" id="skSource">${esc(UI.t('skill.openDoc'))}</button></p>` : ''}${linked}`;
    const fields = [...box.querySelectorAll('input, textarea, select')];
    let draft = H.skillDrafts.get(key);
    if (!draft) { try { draft = JSON.parse(sessionStorage.getItem(draftKey(key)) || 'null'); } catch (_) { /* Use the viewed revision. */ } }
    draft = draft || { revision: k.revision, fields: {}, pending: null };
    fields.forEach(e => { if (draft.fields?.[e.id] != null) e.value = draft.fields[e.id]; });
    const remember = () => { draft.fields = Object.fromEntries(fields.map(e => [e.id, e.value])); saveSkillDraft(key, draft); $('#skMsg').textContent = UI.t('skill.unsaved'); };
    fields.forEach(e => { e.addEventListener('input', remember); e.addEventListener('change', remember); });
    const lockFields = () => {
      fields.forEach(e => { e.disabled = !!draft.pending || !!k.source_document; });
      $('#skSave').disabled = !!k.source_document && !draft.pending;
      $('#skSave').textContent = draft.pending ? '같은 요청 결과 다시 확인' : key === '__new__' ? UI.t('skill.add') : UI.t('btn.save');
      $('#skReload').disabled = !!draft.pending;
    };
    lockFields();
    if (draft.pending) $('#skMsg').textContent = '응답을 확인하지 못한 요청입니다. 같은 요청으로 저장 결과를 확인하세요.';
    else if (Object.keys(draft.fields).length) $('#skMsg').textContent = UI.t('skill.unsaved');
    $('#skReload').addEventListener('click', async () => {
      if (draft.pending) return;
      clearSkillDraft(key); box.dataset.key = ''; await loadSkills();
    });
    $('#skSource')?.addEventListener('click', async (ev) => {
      ev.currentTarget.disabled = true;
      try {
        const preview = await postJ(API.process + '/api/kg/manuals/sources/' + encodeURIComponent(k.source_id) + '/preview', {});
        selectTab('knowledge'); H.preview = preview;
        $('#manualDocumentId').value = preview.document_id; renderPreview();
        $('#manualFile').scrollIntoView({ block: 'center' });
      } catch (e) { if (box.dataset.key === key) $('#skMsg').textContent = '원문 확인 실패: ' + e.message; }
      finally { const button = box.querySelector('#skSource'); if (button) button.disabled = false; }
    });
    $('#skSave').addEventListener('click', async (ev) => {
      const b = ev.currentTarget;
      const body = draft.pending || { name: $('#skName').value.trim(), description: $('#skDesc').value, approver: $('#skRole').value, by: $('#skBy').value.trim(), revision: draft.revision, request_id: crypto.randomUUID() };
      if (!draft.pending && key === '__new__') Object.assign(body, { sopId: $('#skSop').value.trim(), failureMode: $('#skFm').value, relation: $('#skRel').value, kind: $('#skKind').value, steps: $('#skSteps').value });
      if (!body.name) { $('#skMsg').textContent = UI.t('skill.nameRequired'); $('#skName').focus(); return; }
      remember(); draft.pending = body; saveSkillDraft(key, draft); lockFields();
      b.disabled = true; $('#skMsg').textContent = '저장 중…';
      try {
        const r = key === '__new__' ? await postJ(API.process + '/api/kg/skills', body)
          : await postJ(API.process + '/api/kg/skills/' + encodeURIComponent(k.id), body, 'PUT');
        if (r.detail && !r.id) throw new Error(r.detail);
        clearSkillDraft(key);
        if (box.dataset.key === key) { H.skillSel = r.id; H.skillNew = false; box.dataset.key = ''; }
        await loadSkills(); if (H.skillSel === r.id && box.querySelector('#skMsg')) $('#skMsg').textContent = UI.t('skill.saved');
      } catch (e) {
        if (e.status >= 400 && e.status < 500) { draft.pending = null; saveSkillDraft(key, draft); }
        if (box.dataset.key === key) {
          lockFields(); $('#skMsg').textContent = '저장 결과: ' + e.message + (draft.pending ? ' 같은 요청으로 결과를 다시 확인하세요.' : ' 현재 내용을 다시 확인한 뒤 수정하세요.');
        }
      } finally { if (box.contains(b)) b.disabled = !!k.source_document && !draft.pending; }
    });
  }
  $('#skillNew').addEventListener('click', () => { H.skillNew = true; renderSkillList(); renderSkillDetail(); UI.revealDetail($('#skillDetail')); $('#skName').focus({ preventScroll: true }); });

  /* ================================================= 매뉴얼 등록 → 조치 방법 (지식 관리) */
  async function loadManualSources(offset = 0) {
    const box = $('#manualSources');
    try {
      const page = await getJ(API.process + '/api/kg/manuals/sources?offset=' + offset);
      box.innerHTML = UI.fold(`보관 원문 <span class="chip tone-neutral sm">${page.total}</span>`, `<p class="muted">${page.total ? offset + 1 : 0}–${offset + page.items.length} / ${page.total}</p>` + page.items.map(s => `<p><a href="${API.process}/api/kg/manuals/sources/${encodeURIComponent(s.source_id)}/original">${esc(s.filename)}</a> · ${esc(UI.dateTime(s.created_at))} · ${s.status === 'READY' ? '텍스트 추출됨' : '페이지/OCR 검토 필요'} <button class="btn small" data-manual-reopen="${esc(s.source_id)}">다시 검토</button></p>`).join('') + `<div class="row-wrap">${offset ? '<button class="btn small" id="manualSourcesPrev">이전</button>' : ''}${page.next_offset !== null ? '<button class="btn small" id="manualSourcesNext">다음</button>' : ''}</div><p id="manualSourcesMsg" class="muted"></p>`, { cls: 'plain' });
      box.querySelectorAll('[data-manual-reopen]').forEach(b => b.addEventListener('click', async () => {
        b.disabled = true;
        try {
          if (!H.catalog) H.catalog = await getJ(API.process + '/api/kg/catalog');
          H.preview = await postJ(API.process + '/api/kg/manuals/sources/' + encodeURIComponent(b.dataset.manualReopen) + '/preview', {});
          $('#manualDocumentId').value = H.preview.document_id; renderPreview();
        } catch (e) { $('#manualSourcesMsg').textContent = '원문 다시 읽기 실패: ' + e.message; }
        finally { b.disabled = false; }
      }));
      $('#manualSourcesPrev')?.addEventListener('click', () => loadManualSources(Math.max(0, offset - page.limit)));
      $('#manualSourcesNext')?.addEventListener('click', () => loadManualSources(page.next_offset));
    } catch (e) { box.textContent = '보관 원문을 읽지 못했습니다: ' + e.message; }
  }
  async function loadUploads() {
    await loadManualSources();
    try {
      const ups = await getJ(API.process + '/api/kg/manuals');
      const history = $('#manualHistory'), wasOpen = !!history.querySelector('details[open]');
      history.innerHTML = ups.length ? UI.fold(`매뉴얼 등록 이력 <span class="chip tone-neutral sm">${ups.length}</span>`, `<div class="table-scroll"><table class="prov"><thead><tr><th>매뉴얼</th><th>등록 내용</th><th>담당자</th><th>등록 시각</th><th>판본</th></tr></thead><tbody>` + ups.map(u => `<tr><td><a href="${API.process}/api/kg/manuals/sources/${encodeURIComponent(u.source_id)}/original">${esc(u.filename)}</a></td><td>절 ${u.sections} · 조치 방법 ${u.procedures} · 단계 ${u.steps}</td><td>${esc(u.by)}</td><td>${esc(UI.dateTime(u.t))}</td><td>${u.status === 'ROLLED_BACK' ? '되돌림' : u.current ? '현재 판본' : '이전 판본'} <button class="btn small" data-manual-revise="${esc(u.document_id)}">이 문서 개정</button>${u.current && u.status === 'ACTIVE' ? ` <button class="btn small" data-manual-undo="${esc(u.batch)}">이 판본 되돌리기</button>` : ''}</td></tr>`).join('') + '</tbody></table></div><p class="muted" id="manualHistoryMsg">되돌리기는 최신 판본부터 진행합니다. 보관한 원문은 지우지 않습니다.</p>', { open: wasOpen, cls: 'plain' }) : '';
      history.querySelectorAll('[data-manual-revise]').forEach(b => b.addEventListener('click', () => {
        $('#manualDocumentId').value = b.dataset.manualRevise;
        $('#manualHistoryMsg').textContent = '개정할 문서를 선택했습니다. 새 판본 파일을 선택하고 미리보기에서 다시 검토하세요.';
        H.preview = null; renderPreview();
      }));
      history.querySelectorAll('[data-manual-undo]').forEach(b => b.addEventListener('click', async () => {
        b.disabled = true;
        try {
          await postJ(API.process + '/api/kg/manuals/batches/' + encodeURIComponent(b.dataset.manualUndo) + '/rollback', { by: $('#manualBy').value });
          H.preview = null; renderPreview(); H.skills = [];
          await loadUploads(); if (window.hydEnt) hydEnt.loadGraph(true);
        } catch (e) { $('#manualHistoryMsg').textContent = '되돌리기 실패: ' + e.message; b.disabled = false; }
      }));
    } catch (e) { $('#manualHistory').textContent = '등록 이력을 읽지 못했습니다: ' + e.message; }
  }
  function renderPreview() {
    const r = H.preview; const box = $('#manualResult');
    if (!r) { box.innerHTML = ''; return; }
    const fms = (H.catalog || {}).failureModes || [];
    const citation = a => a ? UI.fold(`원문 인용 · ${a.page}쪽`, `<pre style="white-space:pre-wrap;overflow-wrap:anywhere">${esc(a.quote)}</pre>`, { cls: 'small' }) : '';
    box.innerHTML = `<div class="mprev"><div class="muted">${esc(r.filename)} · ${r.chars}자 · 절 ${r.sections.length}개 · 절차 ${r.procedures.length}개${r.warnings.length ? ' · <span class="neg">' + r.warnings.map(esc).join(' ') + '</span>' : ''}</div>
      <p class="row-wrap"><a href="${API.process}/api/kg/manuals/sources/${encodeURIComponent(r.source_id)}/original">보관한 원본 내려받기</a> <button class="btn small" id="manualFullSource">추출 원문 전체 보기</button></p><div id="manualSourceText"></div>
      <p class="row-wrap"><button class="btn small" id="manualAgentExtract" ${r.status === 'READY' ? '' : 'disabled'}>에이전트 추출 요청</button> <button class="btn small" id="manualAgentResult">추출 진행 · 결과 확인</button> <span id="manualAgentStatus" role="status" class="muted">${r.extraction ? '에이전트 제안입니다. 원문을 대조하고 검토 후 적재하세요.' : '현재 결과는 구조화된 줄 파서입니다. 일반 문서는 에이전트 추출을 요청하세요.'}</span></p>
      <div class="form-grid">${UI.field({ label: '이 문서의 추출 작업', input: `<select id="manualExtractionRuns"><option value="">${esc(UI.t('loading'))}</option></select>` })}</div><button class="btn small" id="manualExtractionMore" style="display:none">이전 추출 작업 더 보기</button>
      ${r.page_reviews ? UI.fold('페이지별 추출 검토 기록', r.page_reviews.map(p => `<p>${esc(p.page)}쪽: ${esc(p.note)}</p>`).join(''), { cls: 'small' }) : ''}
      <div class="mcols"><div><h3>매뉴얼 절</h3>${r.sections.map(s => `<div class="msec"><b>${esc(s.ref)}</b> ${esc(s.title)}${UI.fold('절 본문 전체', `<div class="muted" style="white-space:pre-wrap;overflow-wrap:anywhere">${esc(s.excerpt)}</div>`, { cls: 'small' })}${citation(s.anchor)}</div>`).join('') || `<div class="muted">${esc(UI.t('skill.none'))}</div>`}</div>
      <div><h3>등록할 조치 방법</h3>${r.procedures.map(p => `<div class="mproc"><div class="form-grid">${UI.field({ label: UI.t('skill.sop'), input: `<input aria-label="절차 번호" data-manual-id="${esc(p.id)}" value="${esc(p.id)}">` })}${UI.field({ label: UI.t('skill.name'), input: `<input aria-label="이름" data-manual-name="${esc(p.id)}" value="${esc(p.name)}">` })}
        ${UI.field({ label: UI.t('skill.fm'), required: true, input: `<select data-fm="${esc(p.id)}"><option value="">(고르세요)</option>${fms.map(f => `<option value="${esc(f.id)}" ${f.id === p.suggestedFailureMode ? 'selected' : ''}>${esc(f.name)}</option>`).join('')}</select>` })}
        ${UI.field({ label: UI.t('skill.relation'), input: `<select data-rel="${esc(p.id)}"><option value="REMEDIED_BY">${esc(UI.t('skill.rel.remedy'))}</option><option value="MITIGATED_BY">${esc(UI.t('skill.rel.mitigate'))}</option></select>` })}
        ${UI.field({ label: UI.t('skill.kind'), input: `<select data-kind="${esc(p.id)}"><option value="work_order">${esc(UI.t('skill.kind.workOrder'))}</option><option value="control">${esc(UI.t('skill.kind.control'))}</option></select>` })}
        ${UI.field({ label: UI.t('skill.affects'), hint: '상태 변수 또는 성과 지표 id와 방향(+/-)을 쉼표로. 비우면 득실 0', input: `<input aria-label="영향" data-affects="${esc(p.id)}" placeholder="예: sv:bearing-wear:- , msr:maint-cost:+">` })}</div>${citation(p.anchor)}
        <ol>${p.steps.map(s => `<li><textarea aria-label="단계 ${s.order}" data-manual-step="${esc(p.id)}" data-order="${s.order}" rows="2">${esc(s.text)}</textarea> <span class="muted">${esc(s.manual || '')}</span>${citation(s.anchor)}</li>`).join('')}</ol></div>`).join('') || `<div class="muted">${esc(UI.t('skill.none'))}</div>`}</div></div>
      <label class="check"><input type="checkbox" id="manualReviewed"> 원문 · 단계 · 고장 유형 · 관계를 검토했습니다.</label>
      ${UI.actions(`<button class="btn primary" id="manualCommit" ${r.status === 'READY' && r.sections.length && r.procedures.length ? '' : 'disabled'}>검토한 내용 적재</button>`)}<span id="manualMsg" class="muted"></span></div>`;
    $('#manualFullSource').addEventListener('click', async () => {
      try {
        const source = await getJ(API.process + '/api/kg/manuals/sources/' + encodeURIComponent(r.source_id));
        if (H.preview !== r) return;
        $('#manualSourceText').innerHTML = source.pages.map(p => UI.fold(`${p.page}쪽 전체`, `<pre style="white-space:pre-wrap;overflow-wrap:anywhere">${esc(p.text)}</pre>`, { cls: 'small' })).join('');
      } catch (e) { if (H.preview === r) $('#manualSourceText').textContent = '원문 조회 실패: ' + e.message; }
    });
    const extractionKey = 'hyd.manual.extraction.' + r.source_id;
    const extractionUrl = API.process + '/api/kg/manuals/sources/' + encodeURIComponent(r.source_id) + '/extractions';
    const extractionState = () => JSON.parse(sessionStorage.getItem(extractionKey) || 'null');
    let extractionOffset = 0;
    const loadExtractions = async (append = false) => {
      try {
        const page = await getJ(extractionUrl + '?offset=' + (append ? extractionOffset : 0));
        if (H.preview !== r) return;
        const select = $('#manualExtractionRuns');
        if (!append) select.innerHTML = '<option value="">추출 작업 선택</option>';
        for (const run of page.items) {
          const option = document.createElement('option'); option.value = run.proc_inst_id;
          option.textContent = UI.dateTime(run.start_date) + ' · ' + UI.status(run.status);
          select.append(option);
        }
        const chosen = r.extraction?.instance || extractionState()?.instance;
        if (chosen && Array.from(select.options).some(o => o.value === chosen)) select.value = chosen;
        else if (!select.value && select.options.length > 1) select.selectedIndex = 1;
        extractionOffset = page.next_offset;
        $('#manualExtractionMore').style.display = page.next_offset === null ? 'none' : '';
      } catch (e) { if (H.preview === r) $('#manualAgentStatus').textContent = '추출 이력 조회 실패: ' + e.message; }
    };
    $('#manualExtractionMore').addEventListener('click', () => loadExtractions(true));
    loadExtractions();
    $('#manualAgentExtract').addEventListener('click', async () => {
      const button = $('#manualAgentExtract'); button.disabled = true;
      try {
        const previous = extractionState();
        const state = previous && !previous.instance ? previous : { request_id: crypto.randomUUID() };
        sessionStorage.setItem(extractionKey, JSON.stringify(state));
        const created = await postJ(extractionUrl, { request_id: state.request_id });
        sessionStorage.setItem(extractionKey, JSON.stringify({ ...state, instance: created.instance }));
        await loadExtractions();
        if (H.preview === r) $('#manualAgentStatus').textContent = (created.segments > 1 ? `긴 문서라 ${created.segments}개 구간으로 접수됨(결과는 하나로 병합). ` : '추출 작업 접수됨. ') + '진행 · 결과 확인을 누르세요. 접수는 추출 완료가 아닙니다.';
      } catch (e) { if (H.preview === r) $('#manualAgentStatus').textContent = '접수 확인 실패: ' + e.message + ' 같은 요청으로 다시 확인할 수 있습니다.'; }
      finally { if (H.preview === r) button.disabled = false; }
    });
    $('#manualAgentResult').addEventListener('click', async () => {
      try {
        const instance = $('#manualExtractionRuns').value;
        if (!instance) { $('#manualAgentStatus').textContent = '추출 작업을 선택하세요. 응답을 받지 못한 요청은 추출 요청 버튼으로 접수를 재확인하세요.'; return; }
        const result = await getJ(extractionUrl + '/' + encodeURIComponent(instance));
        if (H.preview !== r) return;
        if (result.preview) { H.preview = result.preview; renderPreview(); }
        else {
          const seg = result.progress ? ` · 구간 ${result.progress.done}/${result.progress.total} 완료` + (result.segments || []).filter(s => s.status !== 'DONE').map(s => ` [${s.index}: ${UI.status(s.status)}]`).join('') : '';
          $('#manualAgentStatus').textContent = '추출 상태: ' + UI.status(result.status) + seg + (result.log ? ' · ' + result.log : '') + ` — ${UI.t('nav.instances')} 화면에서 단계 · 오류를 확인할 수 있습니다.`;
        }
      } catch (e) { if (H.preview === r) $('#manualAgentStatus').textContent = '결과 확인 실패: ' + e.message; }
    });
    // "sv:ts1:-, msr:maint-cost:+" → [{target, sign}] (A079: reviewed impact of an ingested SOP)
    const parseAffects = text => (text || '').split(',').map(s => s.trim()).filter(Boolean).map(s => { const m = s.match(/^(.*?):([+-])$/); return m ? { target: m[1].trim(), sign: m[2] } : { target: s, sign: '?' }; });
    const c = $('#manualCommit'); if (c) c.addEventListener('click', async () => {
      if (!$('#manualReviewed').checked) { $('#manualMsg').textContent = '원문을 대조하고 검토 완료를 표시하세요.'; return; }
      const links = {};
      box.querySelectorAll('[data-fm]').forEach(s => { const id = s.dataset.fm; links[id] = { failureMode: s.value || null, relation: box.querySelector(`[data-rel="${CSS.escape(id)}"]`).value, kind: box.querySelector(`[data-kind="${CSS.escape(id)}"]`).value, affects: parseAffects(box.querySelector(`[data-affects="${CSS.escape(id)}"]`).value) }; });
      const missing = Object.entries(links).filter(([, v]) => !v.failureMode).map(([k]) => k);
      if (missing.length) { $('#manualMsg').textContent = `고장 유형을 고르세요: ${missing.join(', ')}`; return; }
      c.disabled = true;
      $('#manualMsg').textContent = '적재 중…';
      try {
        const reviewed = structuredClone(r);
        box.querySelectorAll('[data-manual-name]').forEach(input => { reviewed.procedures.find(p => p.id === input.dataset.manualName).name = input.value; });
        box.querySelectorAll('[data-manual-step]').forEach(input => { reviewed.procedures.find(p => p.id === input.dataset.manualStep).steps.find(s => s.order === Number(input.dataset.order)).text = input.value; });
        const reviewedLinks = {};
        box.querySelectorAll('[data-manual-id]').forEach(input => {
          const p = reviewed.procedures.find(p => p.id === input.dataset.manualId);
          p.id = input.value.trim(); reviewedLinks[p.id] = links[input.dataset.manualId];
        });
        const out = await postJ(API.process + '/api/kg/manuals/commit', { ...reviewed, links: reviewedLinks, by: $('#manualBy').value, reviewed: true });
        if (H.preview !== r) return;
        const activated = out.candidate_activation && typeof out.candidate_activation === 'object' ? Object.entries(out.candidate_activation) : [];
        $('#manualMsg').textContent = `적재 완료: 절 ${out.sections} · 조치 방법 ${out.procedures} · 단계 ${out.steps}. ` + (activated.length
          ? '후보 규칙에 연결: ' + activated.map(([fm, rules]) => `${fm} → ${rules.join(', ')}`).join(' · ') + ' (되돌리면 함께 빠집니다)'
          : '연결된 후보 규칙이 없어 판단 후보는 바뀌지 않았습니다.');
        c.textContent = '적재 완료';
        H.skills = [];
        await loadUploads(); if (window.hydEnt) hydEnt.loadGraph(true);
      } catch (e) { if (H.preview === r) { $('#manualMsg').textContent = '실패: ' + e.message; c.disabled = false; } }
    });
    box.oninput = event => { if (event.target.id !== 'manualReviewed') $('#manualReviewed').checked = false; };
  }
  $('#manualPreview').addEventListener('click', async () => {
    const f = $('#manualFile').files[0]; if (!f) { $('#manualResult').innerHTML = '<div class="neg">파일을 먼저 선택해 주세요.</div>'; return; }
    const b = $('#manualPreview'); b.disabled = true; b.textContent = '읽는 중…'; H.preview = null;
    $('#manualResult').innerHTML = `<div class="muted" role="status">${esc(UI.t('loading'))}</div>`;
    try {
      const b64 = await new Promise((ok, no) => { const rd = new FileReader(); rd.onload = () => ok(String(rd.result).split(',')[1] || ''); rd.onerror = () => no(new Error('파일을 읽을 수 없습니다.')); rd.readAsDataURL(f); });
      if (!H.catalog) H.catalog = await getJ(API.process + '/api/kg/catalog');
      const preview = await postJ(API.process + '/api/kg/manuals/preview', { filename: f.name, data: b64, document_id: $('#manualDocumentId').value.trim() || null });
      if ($('#manualFile').files[0] !== f) return;
      H.preview = preview; renderPreview();
      await loadManualSources();
    } catch (e) { if ($('#manualFile').files[0] === f) $('#manualResult').innerHTML = `<div class="neg">미리보기 실패: ${esc(e.message)}</div>`; }
    finally { b.disabled = false; b.textContent = UI.t('kn.preview'); }
  });
  $('#manualFile').addEventListener('change', () => { H.preview = null; $('#manualFilename').textContent = $('#manualFile').files[0]?.name || UI.t('kn.noFile'); renderPreview(); });

  /* ================================================= 업무 데이터 연결 (DDL → System · InputData, 되돌리기 가능) */
  async function loadIngests() {
    try {
      const rows = await getJ(API.process + '/api/kg/ingests');
      const box = $('#ddlHistory'); if (!box) return;
      const batches = {};
      rows.forEach(r => { (batches[r.batch] = batches[r.batch] || []).push(r); });
      const keys = Object.keys(batches);
      box.innerHTML = keys.length ? UI.fold(`연결 배치 <span class="chip tone-neutral sm">${keys.length}</span>`, `<div class="table-scroll"><table class="prov"><thead><tr><th>배치</th><th>사용 항목</th><th>출처</th><th></th></tr></thead><tbody>`
        + keys.map(k => `<tr><td><code>${esc(k)}</code></td><td>${batches[k].map(r => `${esc(LABEL_KO[r.label] || r.label)} ${r.nodes}`).join(' · ')}</td><td class="muted">${esc((batches[k][0] || {}).source || '')}</td><td><button class="btn small" data-clear="${esc(k)}">되돌리기</button></td></tr>`).join('') + '</tbody></table></div>', { cls: 'plain', open: true }) : '';
      box.querySelectorAll('[data-clear]').forEach(b => b.addEventListener('click', async () => {
        if (!confirm(`${b.dataset.clear} 배치의 변경을 되돌립니다. 다른 배치가 사용하는 항목은 유지합니다. 계속할까요?`)) return;
        b.disabled = true;
        try { const out = await postJ(API.process + '/api/kg/ingests/' + encodeURIComponent(b.dataset.clear) + '?by=' + encodeURIComponent($('#ddlBy').value), null, 'DELETE'); $('#ddlMsg').textContent = `되돌리기 완료: ${out.deleted} 삭제 · ${out.restored || 0} 복원 · ${out.retained || 0} 유지`; await loadIngests(); if (window.hydEnt) hydEnt.loadGraph(true); }
        catch (e) { $('#ddlMsg').textContent = '되돌리기 실패: ' + e.message; b.disabled = false; }
      }));
    } catch (e) { }
  }
  function renderDdlPreview() {
    const p = H.ddl; const box = $('#ddlResult');
    if (!p) { box.innerHTML = ''; return; }
    const existing = (p.existingSystems || []).map(s => s.id);
    const sysOptions = sel => [...new Set([...existing, ...p.systems.map(s => s.id), sel].filter(Boolean))].map(id => `<option value="${esc(id)}" ${id === sel ? 'selected' : ''}>${esc(id)}</option>`).join('');
    box.innerHTML = `<div class="mprev"><div class="muted">${esc(p.filename)} · ${p.chars}자 · 테이블 ${p.tables.length}개${p.warnings.length ? ' · <span class="neg">' + p.warnings.map(esc).join(' ') + '</span>' : ''}</div>
      <div class="mcols"><div><h3>테이블 → 출처 시스템</h3>${p.tables.map(t => `<div class="msec"><b>${esc(t.table)}</b> <span class="muted">${esc(t.comment || '')}</span>
        ${UI.field({ label: '출처 시스템', input: `<select data-sys="${esc(t.table)}"><option value="">(없음 · 적재 안 함)</option>${sysOptions(t.system)}</select>` })}
        <div class="ddlcols">${t.columns.map(c => `<label><input type="checkbox" data-col="${esc(t.table)}" value="${esc(c)}" ${t.selected.includes(c) ? 'checked' : ''}> ${esc(c)}</label>`).join('')}</div></div>`).join('')}</div>
      <div><h3>입력 데이터와 실제 위치</h3><p class="muted">${esc(p.datasource)} / ${esc(p.catalog)}</p><div class="table-scroll"><table class="prov"><thead><tr><th>이름</th><th>형</th><th>스키마 · 표 · 열</th><th>업무 시스템</th></tr></thead><tbody>${p.inputs.map(i => `<tr><td>${esc(i.name)}</td><td>${esc(i.typeRef)}</td><td>${esc(i.schema)}<br>${esc(i.table)}<br>${esc(i.column)}</td><td>${esc(i.system)}</td></tr>`).join('') || '<tr><td colspan="4" class="muted">고른 열이 없습니다</td></tr>'}</tbody></table></div>${UI.fold('식별자와 규칙 변수', p.inputs.map(i => `<p>${esc(i.schema)} · ${esc(i.table)} · ${esc(i.column)}<br><code>${esc(i.id)}</code> <code>${esc(i.variable)}</code></p>`).join(''), { cls: 'small' })}</div></div>
      ${UI.actions(`<button class="btn outline" id="ddlReplan">선택 반영</button><button class="btn primary" id="ddlCommit" ${p.inputs.length ? '' : 'disabled'}>적재</button>`)}<span id="ddlMsg" class="muted"></span></div>`;
    $('#ddlReplan').addEventListener('click', async () => {
      const selection = {}, systems = {};
      box.querySelectorAll('[data-sys]').forEach(s => { if (s.value) systems[s.dataset.sys] = s.value; });
      box.querySelectorAll('[data-col]').forEach(c => { if (c.checked && systems[c.dataset.col]) (selection[c.dataset.col] = selection[c.dataset.col] || []).push(c.value); });
      try { H.ddl = await postJ(API.process + '/api/kg/ddl/preview', { filename: p.filename, text: H.ddlText, selection, systems, datasource: p.datasource, catalog: p.catalog }); renderDdlPreview(); }
      catch (e) { $('#ddlMsg').textContent = '실패: ' + e.message; }
    });
    $('#ddlCommit').addEventListener('click', async () => {
      const c = $('#ddlCommit'); c.disabled = true; $('#ddlMsg').textContent = '적재 중…';
      try {
        const out = await postJ(API.process + '/api/kg/ddl/commit', { ...p, by: $('#ddlBy').value });
        $('#ddlMsg').textContent = `적재 완료: 시스템 ${out.systems} · 입력 데이터 ${out.inputs}. 되돌리려면 아래 이력에서 "되돌리기".`;
        c.textContent = '적재 완료';
        await loadIngests(); if (window.hydEnt) hydEnt.loadGraph(true);
      } catch (e) { $('#ddlMsg').textContent = '실패: ' + e.message; c.disabled = false; }
    });
  }
  $('#ddlPreview').addEventListener('click', async () => {
    const f = $('#ddlFile').files[0]; if (!f) { $('#ddlResult').innerHTML = '<div class="neg">파일을 먼저 선택해 주세요.</div>'; return; }
    const b = $('#ddlPreview'); b.disabled = true; b.textContent = '읽는 중…'; H.ddl = null;
    $('#ddlResult').innerHTML = `<div class="muted" role="status">${esc(UI.t('loading'))}</div>`;
    try {
      H.ddlText = await f.text();
      const preview = await postJ(API.process + '/api/kg/ddl/preview', { filename: f.name, text: H.ddlText, datasource: $('#ddlDatasource').value.trim(), catalog: $('#ddlCatalog').value.trim() });
      if ($('#ddlFile').files[0] !== f) return;
      H.ddl = preview; renderDdlPreview(); await loadIngests();
    } catch (e) { if ($('#ddlFile').files[0] === f) $('#ddlResult').innerHTML = `<div class="neg">미리보기 실패: ${esc(e.message)}</div>`; }
    finally { b.disabled = false; b.textContent = UI.t('kn.preview'); }
  });
  $('#ddlFile').addEventListener('change', () => { H.ddl = null; $('#ddlFilename').textContent = $('#ddlFile').files[0]?.name || UI.t('kn.noFile'); renderDdlPreview(); });
  ['ddlDatasource', 'ddlCatalog'].forEach(id => $('#' + id).addEventListener('input', () => { H.ddl = null; renderDdlPreview(); }));

  /* ------------------------------------------------ tab hooks */
  const _sel = selectTab;
  selectTab = function (name) {
    _sel(name);
    if (name === 'skills') loadSkills();
    if (name === 'knowledge') { loadUploads(); loadIngests(); }
    if (name === 'incidents') refreshHitl(true);
    if (name === 'process') refreshProcBpmn();
    if (name !== 'incidents') { const b = document.getElementById('hitlPanel'); if (b) b.innerHTML = ''; H.sig = null; }
  };
  window.hydApp.selectTab = selectTab;
})();
