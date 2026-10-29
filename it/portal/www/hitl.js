/* 조치 선택 패널 · 업무 흐름(승인과 실행) · 조치 방법 목록 · 매뉴얼 등록 · 업무 데이터 연결 (loaded after app.js / enterprise.js / main.js / flow.js).
   - 조치 선택 패널 (이상 확인 · 조치): the agent's ranked action candidates → one human decision. In instance mode the decision is made in the
     처리 건 screen (the legacy /decide endpoint answers 409 there — A122 UIUX_PLAN §1.2), so the panel links there instead of showing a form.
   - 업무 흐름: hydFlow draws the definition of the instance behind the selected decision (UIUX_PLAN §4).
   - 조치 방법: list / edit skills; add a new skill matched to a failure mode (written by the process service)
   - 매뉴얼 등록 · 업무 데이터 연결 (지식 관리 탭) */
(function () {
  const H = { inc: null, decs: [], dec: null, sig: null, form: { option: null, reason: '', role: null, by: 'OP-17', fan: null, load: null }, msg: '', busy: false,
    skills: [], catalog: null, manualCatalog: null, manualCatalogError: '', skillSel: null, skillNew: false, skillDrafts: new Map(), preview: null, mode: null, instByIncident: new Map() };
  getJ(API.process + '/api/process/mode').then(m => { H.mode = m; }).catch(() => { H.mode = null; });
  const instanceMode = () => !H.mode || H.mode.mode === 'instance';
  // Selection values are exact document identities; filenames are business labels.
  function selectManualDocument(id, filename) {
    const select = $('#manualDocumentId'); if (!select) return;
    const value = id || '';
    let option = Array.from(select.options).find(o => o.value === value);
    if (!option) {
      const historical = H.manualDocuments?.get(value);
      filename = filename || historical?.filename;
      option = new Option(filename ? `${filename} · 검토 중인 원문` : '선택한 문서를 등록 이력에서 확인할 수 없습니다', value);
      select.add(option);
    }
    select.value = value;
  }
  function updateManualDocuments(uploads) {
    const select = $('#manualDocumentId'); if (!select) return;
    const selected = select.value;
    const docs = new Map();
    const allDocs = new Map();
    uploads.forEach(u => {
      if (!u.document_id) return;
      if (!allDocs.has(u.document_id) || u.current) allDocs.set(u.document_id, u);
      if (u.current && u.status !== 'ROLLED_BACK') docs.set(u.document_id, u);
    });
    H.manualDocuments = allDocs;
    select.replaceChildren(new Option('새 문서 등록', ''));
    const filenameCounts = new Map();
    docs.forEach(u => filenameCounts.set(u.filename, (filenameCounts.get(u.filename) || 0) + 1));
    docs.forEach(u => {
      const disambiguation = filenameCounts.get(u.filename) > 1 ? ` · ${u.t ? UI.dateTime(u.t) : '등록 시각 미상'}${u.by ? ' · ' + u.by : ''}` : '';
      select.add(new Option(`${u.filename || '파일 이름 없는 문서'}${disambiguation} · 문서 개정`, u.document_id));
    });
    if (selected && !docs.has(selected)) {
      const source = H.preview?.document_id === selected ? H.preview.filename : allDocs.get(selected)?.filename;
      select.add(new Option(source ? `${source} · 검토 중인 원문` : '선택한 문서를 등록 이력에서 확인할 수 없습니다', selected));
    }
    select.value = selected;
  }

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
    const sig = [inc.id, inc.state, decs.length, dec && dec.id, dec && dec.state, H.msg, H.mode && H.mode.mode, UI.namesVersion].join('|');
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
    // A141: 승인 시각은 기록 접기(audit)에 있으므로 카드에서는 뺀다
    return UI.card({ title: esc(UI.idText(ch.name || d.chosen || UI.t('decision'))), chips: UI.chip(d.state) + (d.override ? UI.chipText(UI.t('proc.override'), 'warning') : ''),
      value: `<span class="kv">${esc(d.approvedBy || '–')}<small>${esc(roleName)}</small></span>`,
      sub: d.reason ? `${esc(UI.t('inc.reasonLabel'))}: ${esc(d.reason)}` : '',
      body: (d.executions || []).length ? `<div class="cards two">${d.executions.map(x => UI.card({ title: esc(UI.who(x.system) + (x.code ? ' · ' + hydCards.actionLabel({ code: x.code }) : '')), chips: UI.chip(x.status), value: x.ref ? `<span class="kv mono">${esc(x.ref)}</span>` : '', sub: esc(UI.idText(x.detail || '')), cls: 'soft' })).join('')}</div>` : '' });
  }
  function renderHitl() {
    const box = document.getElementById('hitlPanel'); const inc = H.inc, d = H.dec;
    let html = '<section class="hitl">';
    if (!d) {
      html += inc.state === 'AWAITING_APPROVAL' ? UI.empty(UI.t('inc.waiting'), '', 'compact') : UI.empty(UI.t('inc.noCandidates'), `${UI.status(inc.state)}${inc.reason ? ' · ' + UI.status(inc.reason) : ''}`, 'compact');
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
    html += `<div class="detail-head"><div class="row"><h2 style="font-size:16px">${esc(pending ? UI.t('select') : UI.t('decision'))}</h2>${UI.chip(d.state)}</div><div class="sub">${esc(UI.idText(sc.failureMode || ''))}${sc.cause ? ' · ' + esc(UI.idText(sc.cause)) : ''}</div></div>`;
    html += summaryBlock(d.explanation);
    if (pending && !legacy) {
      // 409 in instance mode: the choice is made in the 처리 건 screen — one link, no dead form (UIUX_PLAN §1.2)
      html += '<div class="hitl-opts">' + opts.map(o => hydCards.cardHtml(o, { rec: d.recommended, chosen: d.chosen, maxAbs, decision: d })).join('') + '</div>';
      html += UI.actions(`<button class="btn primary" id="hGoInstance">${esc(UI.t('btn.goInstance'))}</button>`);
    } else if (pending) {
      const live = inc.state === 'AWAITING_APPROVAL';
      // A141: 사건 정보(설비 · 고장 유형 · 원인 · 경보 시각)는 접기로
      html += UI.metaFold([[UI.t('dec.asset'), esc(inc.asset)], ['고장 유형', esc(UI.idText(sc.failureMode || ''))], [UI.t('dec.cause'), esc(UI.idText(sc.cause || ''))], [UI.t('inc.alertAt'), esc(UI.dateTime(inc.created))]], 'fold.case');
      html += `<div class="form">` +
        UI.section(UI.t('form.section.choice'), `<div class="hitl-opts wide">${opts.map(o => hydCards.cardHtml(o, { rec: d.recommended, chosen: d.chosen, selectable: true, reviewable: true, selected: H.form.option === o.id, pending, maxAbs, decision: d })).join('')}</div>` +
          (live && (fanA || loadA || pumpA) ? `<div class="form-grid wide">${pumpA ? UI.readonly(UI.t('form.pump'), esc(pumpA.value)) : ''}${fanA ? hydCards.rangeField('hFan', UI.t('form.fan'), fanA, H.form.fan) : ''}${loadA ? hydCards.rangeField('hLoad', UI.t('form.load'), loadA, H.form.load) : ''}</div>` : '') +
          `<div class="wide" id="hReviewed">${reviewed ? `<p class="kv-line"><b>${esc(UI.t('card.reviewed'))}</b> · ${esc(UI.time(review.created))}</p>${hydCards.cardHtml(reviewed, { maxAbs, decision: review.snapshot })}` : `<p class="field-hint">${esc(UI.t('form.hint.preview'))}</p>`}</div>`) +
        hydCards.whoFields('h', H.form, roles) +
        UI.actions(`<button class="btn outline" id="hPreview" ${live && !H.busy && H.form.option ? '' : 'disabled'}>${esc(UI.t('btn.preview'))}</button><button class="btn primary" id="hGo" ${live && canApprove && !H.busy ? '' : 'disabled'}>${esc(UI.t('btn.decide'))}</button>`, H.msg) + '</div>';
    } else {
      html += decidedCard(d, inc);
      html += UI.fold(`${esc(UI.t('candidate'))} <span class="chip tone-neutral sm">${opts.length}</span>`, '<div class="hitl-opts">' + opts.map(o => hydCards.cardHtml(o, { rec: d.recommended, chosen: d.chosen, maxAbs, decision: d })).join('') + '</div>', { cls: 'plain' });
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
      try { await openIncident(inc.id); } finally { b.disabled = false; }
    });
  }
  // 사건 → 그 사건을 처리하는 처리 건으로 이동(조치 패널 · 「승인과 실행」 탭이 같이 쓴다). 찾으면 true
  async function openIncident(incId) {
    let id = H.instByIncident.get(incId);
    if (!id) { const list = await getJ(API.process + '/api/instances?limit=1&incident=' + encodeURIComponent(incId)); const found = list[0]; if (found) { id = found.proc_inst_id; H.instByIncident.set(incId, id); } }
    selectTab('instances'); if (id && window.hydInstancesSelect) window.hydInstancesSelect(id);
    return !!id;
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
  window.hydHitl = { H, refreshHitl, decideNow, openIncident };
  setInterval(() => refreshHitl(false), 1500);

  /* ================================================= 승인과 실행: 업무 흐름 — the instance behind the selected decision, drawn from its definition */
  async function instanceFor(incId) {
    if (!incId) return null;
    let id = H.instByIncident.get(incId);
    if (!id) {
      try { const list = await getJ(API.process + '/api/instances?limit=1&incident=' + encodeURIComponent(incId)); const found = list[0]; if (found) { id = found.proc_inst_id; H.instByIncident.set(incId, id); } } catch (e) { }
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
    const vertical = hydFlow.narrow(box);          // A141: 좁은 폭(1024)에서는 세로 배치 — 가로 스크롤 없음
    const sig = [d && d.id, view && view.instance.status, view && view.workitems.map(w => w.id + w.status).join(','), vertical].join('|');
    if (box.dataset.sig === sig) return; box.dataset.sig = sig;
    // 좁은 폭에서는 접기 안에 세로 배치(요약 줄에 처리 건 이름 · 상태), 넓은 폭은 그대로 펼친 가로 흐름도
    if (view) {
      const caption = `<b>${esc(view.instance.proc_inst_name)}</b> ${UI.chip(view.instance.status)}`;
      hydFlow.mount(box, hydFlow.render(view.definition, { workitems: view.workitems, instance: view.instance, vertical, caption: vertical ? '' : caption }), view.instance.proc_inst_id, { fold: vertical ? `${esc(UI.t('proc.flow'))} · ${caption}` : '' });
    } else {
      const def = await hydFlow.latestDefinition();
      if (state.tab !== 'process') return;
      const caption = esc(d ? UI.t('proc.flowManual') : UI.t('proc.flowEmpty'));
      hydFlow.mount(box, hydFlow.render(def, { vertical, caption: vertical ? '' : caption }), 'overview', { fold: vertical ? `${esc(UI.t('proc.flow'))} · <span class="muted" style="font-weight:400">${caption}</span>` : '' });
    }
  }
  setInterval(refreshProcBpmn, 2000);

  /* ================================================= 조치 방법 — Skill = SOP, matched to a failure mode */
  const REL_KO = { MITIGATED_BY: UI.t('skill.rel.mitigate'), REMEDIED_BY: UI.t('skill.rel.remedy'), PREVENTED_BY: UI.t('skill.rel.prevent') };
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
    try { H.skills = requireList(await getJ(API.process + '/api/kg/skills'), '조치 방법 목록'); } catch (e) { $('#skillList').innerHTML = UI.empty(UI.t('error.load'), e.message, 'compact'); return; }
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
      it.innerHTML = `<div class="row"><strong>${esc(k.name)}</strong>${UI.chipText(k.kind === 'control' ? UI.t('skill.kind.control') : UI.t('skill.kind.workOrder'), k.kind === 'control' ? 'accent' : 'warning')}</div><span class="sub">${esc(fm || UI.t('skill.noFm'))} · ${esc(UI.t('card.approver'))} ${esc((k.approver || {}).name || '–')}</span>`;
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
      UI.field({ label: UI.t('skill.relation'), input: `<select id="skRel"><option value="REMEDIED_BY">${esc(UI.t('skill.rel.remedy'))}</option><option value="MITIGATED_BY">${esc(UI.t('skill.rel.mitigate'))}</option><option value="PREVENTED_BY">${esc(UI.t('skill.rel.prevent'))}</option></select>` }) +
      UI.field({ label: UI.t('skill.kind'), input: `<select id="skKind"><option value="work_order">${esc(UI.t('skill.kind.workOrder'))}</option><option value="control">${esc(UI.t('skill.kind.control'))}</option></select>` }) +
      UI.field({ label: UI.t('skill.steps'), required: true, cls: 'wide', input: `<textarea id="skSteps" rows="5" placeholder="현장 제어로 전환하고 잠근다.&#10;벨트를 교체한다.&#10;재가동 후 진동 0.9 mm/s 미만을 확인한다."></textarea>` })) : '';
    const linked = H.skillNew ? '' : `<h3 style="font-size:14px;margin:var(--s4) 0 var(--s2)">${esc(UI.t('skill.stepsTitle'))}</h3><ol class="steps">${(k.steps || []).map(s => `<li>${esc(s.text)} ${s.manual ? `<span class="muted">[${esc(s.manual)}]</span>` : ''}</li>`).join('') || `<li class="muted">${esc(UI.t('skill.noSteps'))}</li>`}</ol>
      <h3 style="font-size:14px;margin:var(--s4) 0 var(--s2)">${esc(UI.t('skill.linked'))}</h3><table class="kvt">
        <tr><th>${esc(UI.t('skill.fm'))}</th><td>${(k.failureModes || []).map(f => `${esc(f.name)} <span class="muted">(${esc(REL_KO[f.relation] || f.relation)})</span>`).join('<br>') || esc(UI.t('skill.none'))}</td></tr>
        <tr><th>${esc(UI.t('skill.causes'))}</th><td>${(k.causes || []).map(x => esc(x.name)).join(', ') || esc(UI.t('skill.allCauses'))}</td></tr>
        <tr><th>${esc(UI.t('skill.actions'))}</th><td>${(k.actions || []).map(a => `${esc(hydCards.actionLabel(a))} <span class="muted">${esc(a.name)}</span>`).join('<br>') || esc(UI.t('skill.none'))}</td></tr>
        <tr><th>${esc(UI.t('skill.rules'))}</th><td>${(k.rules || []).map(r => `<span class="${r.effect === 'EXCLUDE' ? 'hard' : r.effect === 'SELECT' ? '' : 'soft'}">${esc({ EXCLUDE: UI.t('chip.excluded'), SELECT: '후보', PENALTY: UI.t('card.penalty'), WARN: UI.t('card.warn') }[r.effect] || r.effect)} · ${esc(UI.ruleLabel(r))}${UI.fold('규칙 원문',`<pre>${esc(JSON.stringify(r,null,2))}</pre>`,{cls:'small'})}</span>`).join(' ') || esc(UI.t('skill.none'))}</td></tr>
        <tr><th>${esc(UI.t('skill.affects'))}</th><td>${(k.affects || []).map(a => `${esc(a.name)} ${a.sign > 0 ? '↑' : '↓'}`).join(', ') || esc(UI.t('skill.none'))}</td></tr></table>`;
    box.innerHTML = `<div class="detail-head"><div class="row"><h2>${esc(H.skillNew ? UI.t('skill.new') : k.name)}</h2>${k.kind ? UI.chipText(k.kind === 'control' ? UI.t('skill.kind.control') : UI.t('skill.kind.workOrder'), k.kind === 'control' ? 'accent' : 'warning') : ''}</div></div>${H.skillNew ? '' : UI.metaFold([['조치 식별자',esc(k.id)],['절차 번호',esc(k.sopId || '')]])}
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
    let draft = H.skillDrafts.get(key), draftError = '';
    if (!draft) { try { draft = JSON.parse(sessionStorage.getItem(draftKey(key)) || 'null'); } catch (_) { draftError = '저장한 초안을 읽을 수 없습니다.'; } }
    if (draft && (typeof draft !== 'object' || !draft.fields || typeof draft.fields !== 'object' || Array.isArray(draft.fields))) draftError = '저장한 초안의 형식이 올바르지 않습니다.';
    if (draftError) {
      fields.forEach(n => { n.disabled = true; });
      $('#skSave').disabled = true;
      $('#skMsg').textContent = draftError + ' 초안은 보존되어 있습니다. 취소를 누르면 이 초안을 버리고 서버의 저장본을 다시 읽습니다.';
      $('#skReload').addEventListener('click', async () => {
        if (!await UI.confirm({ title: '읽을 수 없는 초안을 버릴까요?', body: '이 브라우저의 초안만 버립니다. 서버의 저장본은 바뀌지 않습니다.', ok: '초안 버리기', danger: true })) return;
        clearSkillDraft(key); box.dataset.key = ''; await loadSkills();
      });
      return;
    }
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
        await loadManualCatalog();
        const preview = await getJ(API.process + '/api/kg/manuals/sources/' + encodeURIComponent(k.source_id) + '/preview');
        selectTab('knowledge'); H.preview = preview;
        selectManualDocument(preview.document_id, preview.filename); renderPreview();
        $('#manualFile').scrollIntoView({ block: 'center' });
      } catch (e) { if (box.dataset.key === key) $('#skMsg').textContent = '원문 확인 실패: ' + e.message; }
      finally { const button = box.querySelector('#skSource'); if (button) button.disabled = false; }
    });
    $('#skSave').addEventListener('click', async (ev) => {
      const b = ev.currentTarget;
      const body = draft.pending || { name: $('#skName').value.trim(), description: $('#skDesc').value, approver: $('#skRole').value, by: $('#skBy').value.trim(), revision: draft.revision, request_id: UI.uuid() };
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
  async function loadManualCatalog() {
    H.manualCatalog = null; H.manualCatalogError = '';
    try {
      const catalog = await getJ(API.process + '/api/kg/manuals/catalog');
      if (!catalog || !Array.isArray(catalog.parts) || !Array.isArray(catalog.roles)) throw new Error('부품 · 담당 역할 목록 응답 형식이 올바르지 않습니다.');
      if (catalog.skills !== undefined && !Array.isArray(catalog.skills)) throw new Error('기존 절차 등록 목록 응답 형식이 올바르지 않습니다.');
      H.manualCatalog = catalog;
    } catch (e) { H.manualCatalogError = '구매 검토 목록 읽기 실패: ' + e.message; }
  }
  function manualLink(preview, procedure) {
    if (preview.links && Object.prototype.hasOwnProperty.call(preview.links, procedure.id)) return preview.links[procedure.id] || {};
    return procedure.link || (procedure.suggestedFailureMode ? {failureMode:procedure.suggestedFailureMode} : {});
  }
  async function loadManualSources(offset = 0) {
    const box = $('#manualSources');
    try {
      const page = await getJ(API.process + '/api/kg/manuals/sources?offset=' + offset);
      box.innerHTML = UI.fold(`보관 원문 <span class="chip tone-neutral sm">${page.total}</span>`, `<p class="muted">${page.total ? offset + 1 : 0}–${offset + page.items.length} / ${page.total}</p>` + page.items.map(s => `<p><a href="${API.process}/api/kg/manuals/sources/${encodeURIComponent(s.source_id)}/original">${esc(s.filename)}</a> · ${esc(UI.dateTime(s.created_at))} · ${s.status === 'READY' ? '텍스트 추출됨' : '페이지/OCR 검토 필요'} <button class="btn small" data-manual-reopen="${esc(s.source_id)}">다시 검토</button></p>`).join('') + `<div class="row-wrap">${offset ? '<button class="btn small" id="manualSourcesPrev">이전</button>' : ''}${page.next_offset !== null ? '<button class="btn small" id="manualSourcesNext">다음</button>' : ''}</div><p id="manualSourcesMsg" class="muted"></p>`, { cls: 'plain' });
      box.querySelectorAll('[data-manual-reopen]').forEach(b => b.addEventListener('click', async () => {
        b.disabled = true;
        try {
          if (!H.catalog) H.catalog = await getJ(API.process + '/api/kg/catalog');
          await loadManualCatalog();
          H.preview = await getJ(API.process + '/api/kg/manuals/sources/' + encodeURIComponent(b.dataset.manualReopen) + '/preview');
          selectManualDocument(H.preview.document_id, H.preview.filename); renderPreview();
        } catch (e) { $('#manualSourcesMsg').textContent = '원문 다시 읽기 실패: ' + e.message; }
        finally { b.disabled = false; }
      }));
      $('#manualSourcesPrev')?.addEventListener('click', () => loadManualSources(Math.max(0, offset - page.limit)));
      $('#manualSourcesNext')?.addEventListener('click', () => loadManualSources(page.next_offset));
    } catch (e) { box.textContent = '보관 원문을 읽지 못했습니다: ' + e.message; }
  }
  /* ---- 이 문서로 답할 수 있는 질문 (A118 골든 퀘스천 → A132 화면). API 그대로:
     POST /api/kg/manuals/batches/{batch}/golden-questions {questions, by, request_id} · GET …/golden-report (없으면 404). 현재 판본(head) 배치만 가능. */
  H.golden = H.golden || {};                      // batch → { report (undefined 읽기 전 · null 없음 · object), error, busy, msg, draft }
  const goldenUrl = (batch, tail) => API.process + '/api/kg/manuals/batches/' + encodeURIComponent(batch) + '/golden-' + tail;
  const goldenFinal = r => r && ['DONE', 'CANCELLED', 'FAILED'].includes(r.status);
  const ITEM_STATUS = { answerable: ['golden.answerable', 'success'], partially_answerable: ['golden.partial', 'warning'], not_yet_answerable: ['golden.notYet', 'neutral'] };
  async function fetchGolden(batch) {
    const g = H.golden[batch] = H.golden[batch] || {};
    try {
      const next = await getJ(goldenUrl(batch, 'report') + '?optional=1');   // A161-U1: 200 + null when there is none (no console 404)
      const changed = JSON.stringify(next) !== JSON.stringify(g.report); g.report = next; g.error = ''; return changed;
    } catch (e) {
      if (e.status === 404) { const changed = g.report !== null; g.report = null; g.error = ''; return changed; }
      g.error = e.message; return true;
    }
  }
  function goldenStatusChip(r) {
    if (!r) return '';
    if (r.status === 'DONE') return UI.chipText(UI.t('golden.done'), 'success');
    if (r.status === 'CANCELLED' || r.status === 'FAILED') return UI.chipText(UI.t('golden.failed'), 'danger');
    return r.corrections ? UI.chipText(UI.t('golden.correcting'), 'warning') : UI.chipText(UI.t('golden.pending'), 'accent');
  }
  function goldenForm(batch, g) {
    const dis = g.busy ? 'disabled' : '';
    return `<div class="form golden-form" data-golden-form="${esc(batch)}"><div class="form-grid">
      ${UI.field({ label: UI.t('golden.questions'), required: true, hint: UI.t('golden.questionsHint'), cls: 'wide', input: `<textarea rows="4" data-golden-q aria-label="${esc(UI.t('golden.questions'))}" ${dis}>${esc(g.draft || '')}</textarea>` })}
      ${UI.field({ label: UI.t('form.by'), input: `<input data-golden-by value="${esc(g.by != null ? g.by : $('#manualBy').value)}" ${dis}>` })}
    </div>${UI.actions(`<button type="button" class="btn primary" data-golden-ask ${dis}>${esc(g.busy ? UI.t('golden.asking') : UI.t('golden.ask'))}</button>`, g.msg || '')}</div>`;
  }
  // A141 다이어트: 질문 카드 = 질문 · 판정 칩 · 답 한 단락. 집계 칩 묶음 · 요약 문단 · 확신도 · 근거 · 질의는 접기 안.
  function goldenItems(r) {
    const items = (r.report && r.report.items) || [];
    const counts = `<div class="card-chips golden-counts">${UI.chipText(`${UI.t('golden.answerable')} ${r.answerable || 0}`, 'success')}${UI.chipText(`${UI.t('golden.partial')} ${r.partially_answerable || 0}`, 'warning')}${UI.chipText(`${UI.t('golden.notYet')} ${r.not_yet_answerable || 0}`, 'neutral')}${UI.chipText(`${UI.t('golden.grounded')} ${r.grounded || 0}`, 'accent')}</div>`;
    const summary = r.report && r.report.summary ? `<p class="card-sub">${esc(r.report.summary)}</p>` : '';
    const cards = items.map(it => {
      const [key, tone] = ITEM_STATUS[it.status] || ['golden.notYet', 'neutral'];
      const cited = it.cited || [];
      const conf = it.confidence ? `<p class="kv-line">${esc(UI.t('golden.confidence'))} <b>${esc(UI.t('golden.conf.' + it.confidence))}</b></p>` : '';
      return UI.card({ title: esc(it.question), cls: 'golden-item', chips: UI.chipText(UI.t(key), tone),
        body: `<p class="golden-answer">${esc(it.answer || '')}</p>`
          + (it.claimed_answer ? UI.fold('근거를 확인하지 못한 에이전트의 답', `<p>${esc(it.claimed_answer)}</p>`, { cls: 'small' }) : '')
          + UI.fold(`${esc(UI.t('golden.evidence'))} <span class="chip tone-neutral sm">${cited.length}</span>`, conf + (cited.length ? `<p class="muted">${esc(UI.t('golden.cited'))}</p><ul class="golden-cited">${cited.map(c => `<li><code>${esc(c)}</code> ${esc(UI.name(c) !== c ? UI.name(c) : '')}</li>`).join('')}</ul>` : `<p class="muted">${esc(UI.t('golden.noCited'))}</p>`)
          + (it.cypher ? UI.fold(esc(UI.t('golden.query')), `<pre>${esc(it.cypher)}</pre>`, { cls: 'small' }) : ''), { cls: 'small' }) });
    }).join('');
    return `<div class="cards golden-items">${cards}</div>` + UI.fold(esc(UI.t('golden.summary')), counts + summary, { cls: 'plain' });
  }
  const goldenCounts = r => r && r.status === 'DONE' ? `<span class="muted" style="font-weight:400">${esc(UI.t('golden.answerable'))} ${r.answerable || 0} · ${esc(UI.t('golden.partial'))} ${r.partially_answerable || 0} · ${esc(UI.t('golden.notYet'))} ${r.not_yet_answerable || 0}</span>` : '';
  function goldenSection(batch, open) {
    const g = H.golden[batch] || {}; const r = g.report;
    let body;
    if (g.error) body = `<p class="neg">${esc(UI.t('golden.err.load'))}: ${esc(g.error)}</p>` + goldenForm(batch, g);
    else if (r === undefined) body = `<p class="muted">${esc(UI.t('loading'))}</p>`;
    else if (r === null || r.status === 'CANCELLED' || r.status === 'FAILED') body = goldenForm(batch, g);
    else if (!goldenFinal(r)) body = UI.empty(UI.t('golden.checking', { n: r.questions }), UI.t('golden.checkingSub'), 'compact') + (r.corrections ? `<p class="muted">${esc(UI.t('golden.corrections', { n: r.corrections.attempts }))}</p>` : '');
    else body = goldenItems(r) + UI.fold(esc(UI.t('golden.askMore')), goldenForm(batch, g), { cls: 'plain', open: !!g.msg || !!g.busy });
    // 기본 접힘: 요약 줄에 판정 칩과 집계 숫자만. 확인 중(진행 · 교정)이거나 요청 중이면 펼친다.
    const autoOpen = !!g.msg || !!g.busy || (r && !goldenFinal(r));
    return UI.fold(`${esc(UI.t('golden.title'))} ${goldenCounts(r)} ${goldenStatusChip(r)}`, body, { open: open !== undefined ? open : autoOpen, cls: 'golden' });
  }
  function renderGolden(batch) {
    const box = $('#manualHistory').querySelector(`[data-golden="${CSS.escape(batch)}"]`); if (!box) return;
    const open = box.querySelector('details.golden')?.open;
    box.innerHTML = goldenSection(batch, open); wireGolden(box);
  }
  function wireGolden(root) {
    root.querySelectorAll('[data-golden-ask]').forEach(b => b.addEventListener('click', async () => {
      const form = b.closest('[data-golden-form]'); const batch = form.dataset.goldenForm; const g = H.golden[batch] = H.golden[batch] || {};
      g.draft = form.querySelector('[data-golden-q]').value; g.by = form.querySelector('[data-golden-by]').value.trim();
      const questions = [...new Set(g.draft.split('\n').map(s => s.trim()).filter(Boolean))];
      if (!questions.length) { g.msg = UI.t('golden.err.empty'); renderGolden(batch); return; }
      if (questions.length > 20) { g.msg = UI.t('golden.err.many'); renderGolden(batch); return; }
      g.busy = true; g.msg = ''; renderGolden(batch);
      try { await postJ(goldenUrl(batch, 'questions'), { questions, by: g.by, request_id: UI.uuid() }); g.draft = ''; await fetchGolden(batch); }
      catch (e) { g.msg = e.message; }
      finally { g.busy = false; renderGolden(batch); }
    }));
  }
  setInterval(async () => {                      // 2초 폴링(기존 패턴): 확인 중인 배치만 다시 읽는다
    if (state.tab !== 'knowledge') return;
    for (const [batch, g] of Object.entries(H.golden)) {
      if (!g.report || goldenFinal(g.report) || g.polling) continue;
      g.polling = true;
      try { if (await fetchGolden(batch)) renderGolden(batch); } finally { g.polling = false; }
    }
  }, 2000);

  async function loadUploads() {
    await loadManualSources();
    try {
      const ups = await getJ(API.process + '/api/kg/manuals');
      updateManualDocuments(ups);
      const history = $('#manualHistory'), wasOpen = !!history.querySelector('details.manual-history[open]');
      const goldenOpen = {}; history.querySelectorAll('[data-golden]').forEach(d => { goldenOpen[d.dataset.golden] = d.querySelector('details.golden')?.open; });
      const current = ups.filter(u => u.current);
      const counts = u => `${UI.t('kn.sections')} ${u.sections} · ${UI.t('kn.procedures')} ${u.procedures} · ${UI.t('kn.steps')} ${u.steps}`;
      const version = u => u.status === 'ROLLED_BACK' ? UI.chipText(UI.t('kn.rolledBack'), 'neutral') : u.current ? UI.chipText(UI.t('kn.current'), 'success') : UI.chipText(UI.t('kn.previous'), 'neutral');
      const buttons = u => `<button class="btn small" data-manual-revise="${esc(u.document_id)}">${esc(UI.t('kn.revise'))}</button>${u.current && u.status === 'ACTIVE' ? `<button class="btn small" data-manual-undo="${esc(u.batch)}">${esc(UI.t('kn.undo'))}</button>` : ''}`;
      // 매뉴얼 배치 카드(R3): 제목 = 파일 · 칩 = 판본 · 핵심 값 = 절·조치 방법·단계 · 본문 = 이 문서로 답할 수 있는 질문(접기)
      // A141: 담당자 · 시각은 아래 "매뉴얼 등록 이력" 접기 표에만 둔다
      const cards = current.map(u => UI.card({ title: `<a href="${API.process}/api/kg/manuals/sources/${encodeURIComponent(u.source_id)}/original">${esc(u.filename)}</a>`, chips: version(u), value: esc(counts(u)),
        actions: buttons(u), cls: 'manual-doc', body: `<div data-golden="${esc(u.batch)}">${goldenSection(u.batch, goldenOpen[u.batch])}</div>` })).join('');
      history.innerHTML = `<h2 class="sec">${esc(UI.t('kn.docs'))} <span class="chip tone-neutral sm">${current.length}</span></h2>`
        + (current.length ? `<div class="cards manual-docs">${cards}</div>` : UI.empty(UI.t('kn.docsEmpty'), UI.t('kn.docsEmptySub'), 'compact'))
        + (ups.length ? UI.fold(`${esc(UI.t('kn.history'))} <span class="chip tone-neutral sm">${ups.length}</span>`, `<div class="table-scroll"><table class="prov"><thead><tr><th>매뉴얼</th><th>등록 내용</th><th>담당자</th><th>등록 시각</th><th>판본</th></tr></thead><tbody>` + ups.map(u => `<tr><td><a href="${API.process}/api/kg/manuals/sources/${encodeURIComponent(u.source_id)}/original">${esc(u.filename)}</a></td><td>${esc(counts(u))}</td><td>${esc(u.by)}</td><td>${esc(UI.dateTime(u.t))}</td><td>${version(u)} ${buttons(u)}</td></tr>`).join('') + '</tbody></table></div><p class="muted">되돌리기는 최신 판본부터 진행합니다. 보관한 원문은 지우지 않습니다.</p>', { open: wasOpen, cls: 'plain manual-history' }) : '')
        + '<p class="muted" id="manualHistoryMsg" role="status"></p>';
      wireGolden(history);
      current.forEach(u => fetchGolden(u.batch).then(() => renderGolden(u.batch)));
      history.querySelectorAll('[data-manual-revise]').forEach(b => b.addEventListener('click', () => {
        selectManualDocument(b.dataset.manualRevise);
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
  function manualIssueMessage(issue, preview, catalog) {
    const names = new Map();
    const remember = row => {
      if (!row || typeof row !== 'object') return;
      const label = row.name || row.annotation;
      if (typeof label === 'string' && /[가-힣]/.test(label) && label !== row.id) {
        if (row.id) names.set(row.id, label);
        if (row.sopId) names.set(row.sopId, `${label} (${row.sopId})`);
        if (row.code) names.set(row.code, label);
      }
      if (Array.isArray(row.inputs)) row.inputs.forEach(remember);
    };
    Object.values(catalog || {}).filter(Array.isArray).forEach(rows => rows.forEach(remember));
    Object.values(preview.knowledge || {}).filter(Array.isArray).forEach(rows => rows.forEach(remember));
    (preview.procedures || []).forEach(p => {
      if (typeof p.name === 'string' && /[가-힣]/.test(p.name) && p.name !== p.id) names.set(p.id, `${p.name} (${p.id})`);
    });
    const kinds = {fm:'고장 유형',cause:'원인',skill:'조치 방법',rule:'규칙',action:'원자 조치',comp:'부품',part:'부품',sup:'공급사',role:'담당 역할',sv:'상태 변수',msr:'성과 지표',dt:'결정표',dec:'판단',in:'입력',sym:'증상',pat:'이상 유형',evidence:'근거'};
    const labelOf = id => names.get(id) || `${kinds[String(id).split(':')[0]] || '검사 대상'} 표시 이름 미등록`;
    let text = String(issue.message || '검사 설명 기록 없음');
    // Exact metadata keys only: labels never change the stored issue or proposal.
    const owner = issue.sop;
    if (owner && !String(owner).startsWith('SOP-')) text = text.split(owner).join(labelOf(owner));
    text = text.replace(/\bSOP-[A-Za-z0-9_-]+\b/g, id => names.get(id) || id);
    text = text.replace(/\b[A-Za-z][A-Za-z0-9_-]*:[A-Za-z0-9_.-]+\b/g, labelOf);
    const fields = {'link.scope':'절차 업무 범위','link.parts':'구매 대상 부품','link.executable':'절차 사용 방식','link.failureMode':'고장 유형 연결','link.approver':'승인 담당자 연결','link.addresses':'관련 원인 연결','link.affects':'영향 연결','knowledge.rules.table':'규칙의 결정표','knowledge.rules.tests':'규칙 입력 조건','failure_mode':'고장 유형','leads_to':'이어지는 고장 유형','component':'대상 부품','symptoms':'증상','disturbs':'상태 영향','penalizes':'감점 지표','applies_to':'적용 대상','outputs':'출력 대상','parts':'부품','cause':'원인'};
    if (fields[issue.field]) text = text.split(issue.field).join(fields[issue.field]);
    text = text.replace(/\b(?:failureMode|approver|relation|addresses|affects|executable|Part|Supplier)\b/g, key => ({failureMode:'고장 유형',approver:'승인 담당자',relation:'고장 유형 관계',addresses:'관련 원인',affects:'영향',executable:'실행 후보 여부',Part:'부품',Supplier:'공급사'})[key]);
    text = text.replace(/\b(?:control|work_order|Action|REQUIRES_INPUT)\b/g, key => ({control:'설비 제어',work_order:'정비 요청',Action:'원자 조치',REQUIRES_INPUT:'필수 입력 연결'})[key]);
    // Action codes in diagnostic sentences resolve through the same real catalog.
    text = text.replace(/\b[A-Z][A-Z0-9_]+\b/g, key => names.get(key) || key);
    return text;
  }
  function manualValidationHtml(v, preview, catalog) {
    if (!v) return UI.card({title:'현재 지식 기준 검사', body:'기계 검사 결과가 없습니다. 검토 완료나 적재 승인으로 판단할 수 없습니다.'});
    if (v.checked !== true || typeof v.technical_ready !== 'boolean' || v.needs_human_review !== true || v.can_commit !== false || !Array.isArray(v.issues)) return UI.card({title:'현재 지식 기준 검사', chips:UI.chipText('검사 정보 읽기 실패','danger'), body:'기계 검사 응답 형식이 올바르지 않습니다. 검토 완료나 적재 승인으로 판단할 수 없습니다.'});
    const issues=v.issues;
    const values=(v.source_value_warnings || []).filter(w => !(preview.warnings || []).includes(w));
    return UI.card({title:'현재 지식 기준 검사', chips:UI.chipText(v.technical_ready === true ? '기계 검사 통과' : '수정할 항목 있음',v.technical_ready === true ? 'neutral' : 'warning'),
      body:`<p>원문 보관을 위한 연결 구조 검사입니다. 사람 검토는 별도로 필요합니다. 이 검사는 검토 완료나 적재 승인이 아닙니다. 실제 견적 · 재고 · 카운터 · 인력은 실행 판단 시 확인합니다. 받은 제안 기준이며, 편집한 연결은 적재할 때 다시 검사합니다.</p>` +
        (values.length ? UI.fold(`원문 수치 확인 필요 ${values.length}개`, `<ul>${values.map(w=>`<li>${esc(w)}</li>`).join('')}</ul>`, {cls:'small', open:true}) : '') +
        (issues.length ? `<ul>${issues.map(x=>`<li>${esc(manualIssueMessage(x,preview,catalog))}${UI.fold('검사 항목 원문',`<pre>${esc(JSON.stringify(x,null,2))}</pre>`,{cls:'small'})}</li>`).join('')}</ul>` : '<p class="muted">현재 지식에서 기계가 찾은 수정 항목은 없습니다.</p>')});
  }
  function manualExecutionHtml(v, preview, catalog) {
    if (!preview.procedures.some(p => manualLink(preview,p).scope === 'purchase') && !v?.execution) return '';
    if (!v || typeof v.executable_ready !== 'boolean' || !Array.isArray(v.execution)) return UI.card({title:'실행 후보 검사', body:'실행 후보 검사 기록이 없습니다. 원문 보관 여부와 실행 후보 가능 여부는 별도로 확인해야 합니다.'});
    return UI.card({title:'실행 후보 검사',body:'원문 보관과 후보 연결의 구조 검사입니다. 실제 구매 승인이나 구매 실행 완료를 뜻하지 않습니다.' + '<ul>' + v.execution.map(row => {
      const p = preview.procedures.find(p => p.id === row.sop);
      const name = p?.name ? `${p.name} (${row.sop})` : '절차 표시 이름 기록 없음';
      const valid = typeof row.executable === 'boolean' && typeof row.ready === 'boolean' && Array.isArray(row.issues);
      const label = !valid ? '연결 구조 검사 정보 읽기 실패' : row.executable === false ? '원문 참고 보관 · 실행 후보 제외' : row.ready ? '실행 후보 기계 검사 통과 · 연결 구조 검사 통과' : '실행 후보 연결 확인 필요';
      const scope=UI.evaluationInfo(row), note=scope.state==='structural' ? '실제 견적 · 재고는 실행 판단 시 확인 · 현재 실제 승인 · 실행 준비는 확인하지 않음' : scope.state==='execution' ? '실제 실행 검사 기록 있음 · 승인 · 실행 완료 아님' : '실제 승인 · 실행 준비 검사 기록 확인 안 됨';
      return `<li><b>${esc(name)}</b> · ${esc(label)}<p class="muted">${esc(note)}</p>${valid && row.issues.length ? '<ul>'+row.issues.map(x=>`<li>${esc(manualIssueMessage(x,preview,catalog))}${UI.fold('검사 항목 원문',`<pre>${esc(JSON.stringify(x,null,2))}</pre>`,{cls:'small'})}</li>`).join('')+'</ul>' : ''}${UI.fold('절차 실행 검사 원문',`<pre>${esc(JSON.stringify(row,null,2))}</pre>`,{cls:'small'})}</li>`;
    }).join('')+'</ul>'});
  }
  function manualPurchaseFields(p, r) {
    const link = manualLink(r,p), purchase = link.scope === 'purchase', catalog = H.manualCatalog;
    const policies={oem:'정본 순정 라벨 견적',lowest_approved:'승인된 비순정 견적 중 최저가',fastest_quote:'전체 견적 중 최단 납기 · 승인 여부 별도 검사'};
    const fixed=(link.actions || []).find(a=>a.action==='action:purchase-request')?.value;
    const fixedName=(catalog?.suppliers || []).find(s=>s.id===fixed)?.name;
    const knownPolicy=Object.prototype.hasOwnProperty.call(policies,link.supplier_policy);
    const supplierState=link.supplier_policy ? `원문 선정 정책: ${knownPolicy ? policies[link.supplier_policy] : '선정 정책 기록 확인 필요'}` : fixed ? `원문 고정 공급사: ${fixedName || '등록 이름 확인 필요'}` : '원문 고정 공급사 값 미상 · 자동으로 추정하지 않습니다.';
    const options = (rows, selected, missing) => {
      const ids = Array.isArray(selected) ? selected : selected ? [selected] : [];
      return (rows || []).map(row=>`<option value="${esc(row.id)}" ${ids.includes(row.id) ? 'selected' : ''}>${esc(row.name || '등록 이름 없음')}${row.partNo ? ' · '+esc(row.partNo) : ''}</option>`).join('') + ids.filter(id=>!(rows || []).some(row=>row.id===id)).map(id=>`<option value="${esc(id)}" selected>${esc(missing)}</option>`).join('');
    };
    return UI.field({label:'절차의 업무 범위',input:`<select id="manualScope-${esc(p.id)}" data-manual-scope="${esc(p.id)}"><option value="fault" ${!link.scope ? 'selected' : ''}>고장 조치 · 고장 유형 연결 필수</option><option value="purchase" ${purchase ? 'selected' : ''}>구매 원문 절차 · 구매 업무 범위</option>${link.scope && !purchase ? `<option value="${esc(link.scope)}" selected>범위 기록을 확인하세요</option>` : ''}</select>`}) +
      `<div class="wide" data-purchase-fields="${esc(p.id)}" ${purchase ? '' : 'hidden'}><p>고장 유형 없이 구매 대상 부품을 명시합니다. 원문 참고 보관은 실행 후보에 넣지 않으며 구매요청을 만들지 않습니다. 실행 후보는 구매요청 · 승인 담당자 · 공급 관계를 별도로 검사합니다.</p>${H.manualCatalogError ? `<p class="neg">${esc(H.manualCatalogError)}</p>` : !catalog ? '<p class="muted">구매 부품 · 담당 역할 목록 확인 전입니다.</p>' : ''}<div class="form-grid">` +
      UI.field({label:'원문 절차의 사용 방식',required:true,input:`<select id="manualExecutable-${esc(p.id)}" data-manual-executable="${esc(p.id)}"><option value="">원문을 확인하고 선택하세요</option><option value="false" ${link.executable === false ? 'selected' : ''}>원문 참고 보관 · 실행 후보 제외</option><option value="true" ${link.executable === true ? 'selected' : ''}>실행 후보로 검토 · 구매요청 연결 검사</option></select>`}) +
      UI.field({label:'구매 대상 부품',required:true,hint:'원문이 명시한 실제 등록 부품을 선택하세요. 여러 부품은 Ctrl 또는 Command를 누르고 선택합니다.',input:`<select id="manualParts-${esc(p.id)}" multiple data-manual-parts="${esc(p.id)}" ${catalog ? '' : 'disabled'}>${options(catalog?.parts,link.parts,'부품 등록 목록에서 확인되지 않음')}</select>`}) +
      UI.field({label:'구매 승인 담당 역할',hint:'실행 후보는 원문에 명시된 구매 승인 담당자가 필요합니다. 참고 보관은 미지정을 그대로 둘 수 있습니다.',input:`<select id="manualApprover-${esc(p.id)}" data-manual-approver="${esc(p.id)}" ${catalog ? '' : 'disabled'}><option value="">원문에 담당 역할 미지정</option>${options(catalog?.roles,link.approver,'담당 역할 등록 목록에서 확인되지 않음')}</select>`}) +
      UI.field({label:'원문 공급사 선정 기준',hint:'원문에 명시한 정책만 고르세요. 정책은 현재 부품별 견적에서 계산하며 실제 승인 · 발주 완료를 뜻하지 않습니다. 정책 선택 시 고정 공급사 값을 보내지 않습니다.',input:`<select id="manualSupplierPolicy-${esc(p.id)}" data-manual-supplier-policy="${esc(p.id)}"><option value="">정책 미지정 · 원문 고정 공급사 값 사용</option>${Object.entries(policies).map(([key,label])=>`<option value="${key}" ${link.supplier_policy===key ? 'selected' : ''}>${esc(label)}</option>`).join('')}${link.supplier_policy!=null && !knownPolicy ? `<option value="${esc(link.supplier_policy)}" selected>선정 정책 기록 확인 필요</option>` : ''}</select>`}) + `<p class="muted wide">${esc(supplierState)} 참고 보관에는 공급사 선정 정책을 지정하지 않습니다.</p><p class="muted wide" data-supplier-review="${esc(p.id)}"></p></div></div>`;
  }
  function manualReferenceFields(p, r) {
    const link=manualLink(r,p), sid=p.existing_skill_id || link.existing_skill_id || '', pin=p.reference_contract_sha256 || link.reference_contract_sha256 || '';
    const rows=H.manualCatalog?.skills || [];
    return `<div class="wide" data-reference-fields="${esc(p.id)}" ${link.kind==='reference' ? '' : 'hidden'}><p>일반 원문 참고 절차입니다. 고장 유형 · 담당 역할 · 부품 · 실행 조치를 지정하지 않고 원문 단계를 보관합니다. 기존 실행 절차를 재참조해도 그 절차의 실행 단계나 소유권을 바꾸지 않습니다.</p>`+
      (H.manualCatalogError ? `<p class="neg">기존 절차 재참조 목록 읽기 실패: ${esc(H.manualCatalogError)}</p>` : !Array.isArray(H.manualCatalog?.skills) ? '<p class="muted">기존 절차 재참조 목록 기록 없음 · 일치하는 실행 계약을 추정하지 않습니다.</p>' : '')+
      UI.field({label:'참고 절차의 사용 방식',required:true,input:`<select data-reference-executable="${esc(p.id)}"><option value="">원문을 확인하고 선택하세요</option><option value="false" ${link.executable===false ? 'selected' : ''}>원문 참고 보관 · 실행 후보 제외</option></select>`})+
      UI.field({label:'기존 실행 절차 재참조',hint:'원문 번호와 전체 단계가 정확히 같은 등록 절차만 재참조할 수 있습니다. 선택하면 조회한 실행 계약의 판본을 고정합니다.',input:`<select data-reference-target="${esc(p.id)}"><option value="">기존 절차 재참조 없음 · 독립 원문 보관</option>${rows.filter(x=>x.reference_contract).map(x=>`<option value="${esc(x.id)}" ${x.id===sid ? 'selected' : ''}>${esc(x.name || '등록 이름 없음')} · ${esc(x.reference_contract.sopId || '원문 번호 미상')}</option>`).join('')}${sid && !rows.some(x=>x.id===sid && x.reference_contract) ? `<option value="${esc(sid)}" selected>참조 대상 등록 정보 읽기 실패</option>` : ''}</select>`})+
      `<input type="hidden" data-reference-pin="${esc(p.id)}" value="${esc(pin)}"><div data-reference-comparison="${esc(p.id)}" role="status"></div></div>`;
  }
  // 2026-10-25 수업 한 바퀴: 검토 화면이 절차 · 단계 · 고장 유형 연결만 보이고 AI가 뽑은 원인 · 증거 · 규칙은 보이지 않아 학생이 원문과 대조해
  // 틀린 항목을 뺄 수 없었다(실라버스 4회차 「원인 · 수행 조건 · 규칙을 원문과 비교해 수정 · 제외」). 항목마다 원문 인용과 [제외]를 둔다.
  const KNOW_GROUPS = [['failure_modes', '고장 유형'], ['causes', '원인'], ['evidence', '확인 증거'], ['rules', '규칙']];
  function manualKnowledgeSummary(group, x, own) {
    // 이 문서에서 새로 나온 고장 유형 · 원인은 아직 카탈로그에 없다 — 제안 안의 이름을 먼저 쓴다(내부 id 를 화면에 내지 않는다)
    const name = id => own[id] || UI.name(id);
    if (group === 'causes') return `사전 확률 ${x.prior ?? '미정'}${x.failure_mode ? ' · ' + name(x.failure_mode) : ''}`;
    if (group === 'evidence') return `${x.tag} ${x.aggregate || ''} ${x.window_seconds ?? ''}초 ${({ lt: '<', gt: '>', gte: '≥' })[x.expect] || x.expect} ${x.threshold} → ${name(x.cause)}`;
    if (group === 'rules') return `${({ SELECT: '후보', EXCLUDE: '제외', PENALTY: '감점', WARN: '경고' })[x.effect] || x.effect} · ${UI.ruleLabel(x)}${x.penalty != null ? ' · ' + x.penalty + '만 원' : ''}${(x.outputs || []).length ? ' → ' + x.outputs.map(o => name(o)).join(', ') : ''}`;
    return (x.symptoms || []).map(y => name(y)).join(', ');
  }
  function manualKnowledgeHtml(r, citation) {
    const k = r.knowledge || {};
    const groups = KNOW_GROUPS.filter(([g]) => (k[g] || []).length);
    if (!groups.length) return '';
    const own = Object.fromEntries(KNOW_GROUPS.flatMap(([g]) => (k[g] || []).filter(x => x && x.id && x.name).map(x => [x.id, x.name])));
    return `<h3>추출한 지식 후보</h3><p class="muted">고장 유형 · 원인 · 확인 증거 · 규칙을 원문 인용과 대조하세요. 원문과 다르거나 근거가 없는 항목은 [제외]를 고르면 적재하지 않습니다.</p>` +
      groups.map(([g, title]) => `<div class="mknow"><h4>${esc(title)} ${(k[g] || []).length}</h4>${k[g].map(x => `<div class="msec">
        <label class="check"><input type="checkbox" data-know-drop="${esc(g)}" value="${esc(x.id)}"> 제외</label> <b>${esc(x.name || x.annotation || x.id)}</b>
        <div class="muted">${esc(manualKnowledgeSummary(g, x, own))}</div>${citation(x.anchor)}</div>`).join('')}</div>`).join('');
  }
  function renderPreview() {
    const r = H.preview; const box = $('#manualResult');
    $('#manualDocumentId').disabled = !!r;
    if (!r) { box.innerHTML = ''; return; }
    const known = (H.catalog || {}).failureModes || [];
    const fms = known.concat(((r.knowledge || {}).failure_modes || []).filter(f => f && f.id && !known.some(k => k.id === f.id)).map(f => ({ id: f.id, name: `${f.name || f.id} (이 문서에서 새로)` })));
    const citation = a => a ? UI.fold(`원문 인용 · ${a.page}쪽${a.located === 'loose' ? ' · 대략 일치 — 문맥 확인 필요' : a.located === 'normalized' ? ' · 공백·기호를 맞춰 찾음' : ''}`, `<pre style="white-space:pre-wrap;overflow-wrap:anywhere">${esc(a.quote)}</pre>`, { cls: 'small' }) : '';
    box.innerHTML = `<div class="mprev"><div class="muted">${esc(r.filename)} · ${r.chars}자 · 절 ${r.sections.length}개 · 절차 ${r.procedures.length}개${r.warnings.length ? ' · 추출 경고 ' + r.warnings.length + '개' : ''}</div>
      ${r.warnings.length ? `<p class="muted">추출 경고를 원문과 대조하고 제안의 단계 · 연결을 검토하세요.</p>${UI.fold(`추출 경고 원문 ${r.warnings.length}개`, `<ol>${r.warnings.map(w=>`<li>${esc(w)}</li>`).join('')}</ol>`, {cls:'small'})}` : ''}
      ${manualValidationHtml(r.validation,r,{...H.catalog,...H.manualCatalog})}
      ${manualExecutionHtml(r.validation,r,{...H.catalog,...H.manualCatalog})}
      <p class="row-wrap"><a href="${API.process}/api/kg/manuals/sources/${encodeURIComponent(r.source_id)}/original">보관한 원본 내려받기</a> <button class="btn small" id="manualFullSource">추출 원문 전체 보기</button></p><div id="manualSourceText"></div>
      <p class="row-wrap"><button class="btn small" id="manualAgentExtract" ${r.status === 'READY' ? '' : 'disabled'}>추출 제안 준비</button> <button class="btn small" id="manualAgentResult">추출 진행 · 결과 확인</button> <span id="manualAgentStatus" role="status" class="muted">${r.extraction ? '추출 제안입니다. 원문을 대조하고 검토 후 적재하세요.' : '현재 결과는 구조화된 줄 파서입니다. 원문에 근거한 추출 제안을 준비할 수 있습니다.'}</span></p>
      <div class="form-grid">${UI.field({ label: '이 문서의 추출 작업', input: `<select id="manualExtractionRuns"><option value="">${esc(UI.t('loading'))}</option></select>` })}</div><button class="btn small" id="manualExtractionMore" style="display:none">이전 추출 작업 더 보기</button>
      ${r.page_reviews ? UI.fold('페이지별 추출 검토 기록', r.page_reviews.map(p => `<p>${esc(p.page)}쪽: ${esc(p.note)}</p>`).join(''), { cls: 'small' }) : ''}
      <div class="mcols"><div><h3>매뉴얼 절</h3>${r.sections.map(s => `<div class="msec"><b>${esc(s.ref)}</b> ${esc(s.title)}${UI.fold('절 본문 전체', `<div class="muted" style="white-space:pre-wrap;overflow-wrap:anywhere">${esc(s.excerpt)}</div>`, { cls: 'small' })}${citation(s.anchor)}</div>`).join('') || `<div class="muted">${esc(UI.t('skill.none'))}</div>`}</div>
      <div><h3>등록할 조치 방법</h3>${r.procedures.map(p => `<div class="mproc"><div class="form-grid">${UI.field({ label: UI.t('skill.sop'), input: `<input aria-label="절차 번호" data-manual-id="${esc(p.id)}" value="${esc(p.id)}">` })}${UI.field({ label: UI.t('skill.name'), input: `<input aria-label="이름" data-manual-name="${esc(p.id)}" value="${esc(p.name)}">` })}
        ${manualPurchaseFields(p,r)}
        ${UI.field({ label: UI.t('skill.fm'), hint:'고장 조치는 필수입니다. 구매 절차와 일반 원문 참고 절차에는 고장 유형을 연결하지 않습니다.', input: `<select data-fm="${esc(p.id)}"><option value="">(고르세요)</option>${fms.map(f => `<option value="${esc(f.id)}" ${f.id === manualLink(r,p).failureMode ? 'selected' : ''}>${esc(f.name)}</option>`).join('')}</select>` })}
        ${UI.field({ label: UI.t('skill.relation'), input: `<select data-rel="${esc(p.id)}"><option value="" ${manualLink(r,p).scope === 'purchase' && !manualLink(r,p).relation ? 'selected' : ''}>고장 유형 관계 없음</option>${['REMEDIED_BY', 'MITIGATED_BY', 'PREVENTED_BY'].map(v => `<option value="${v}" ${(manualLink(r,p).relation || (manualLink(r,p).scope === 'purchase' ? '' : 'REMEDIED_BY')) === v ? 'selected' : ''}>${esc(REL_KO[v])}</option>`).join('')}</select>` })}
        ${UI.field({ label: UI.t('skill.kind'), input: `<select data-kind="${esc(p.id)}"><option value="work_order">${esc(UI.t('skill.kind.workOrder'))}</option><option value="control" ${manualLink(r,p).kind === 'control' ? 'selected' : ''}>${esc(UI.t('skill.kind.control'))}</option><option value="reference" ${manualLink(r,p).kind === 'reference' ? 'selected' : ''}>일반 원문 참고 절차 · 실행 후보 제외</option></select>` })}
        ${manualReferenceFields(p,r)}
        ${UI.field({ label: UI.t('skill.affects'), hint: '상태 변수 또는 성과 지표 id와 방향(+/-)을 쉼표로. 비우면 득실 0', input: `<input aria-label="영향" data-affects="${esc(p.id)}" value="${esc((manualLink(r,p).affects || []).map(a=>a.target+':'+a.sign).join(', '))}" placeholder="예: sv:bearing-wear:- , msr:maint-cost:+">` })}</div>${citation(p.anchor)}
        ${UI.fold('절차 연결 원문',`<pre>${esc(JSON.stringify({inline:p.link,override:r.links && Object.prototype.hasOwnProperty.call(r.links,p.id) ? r.links[p.id] : undefined,suggestedFailureMode:p.suggestedFailureMode,existing_skill_id:p.existing_skill_id,reference_contract_sha256:p.reference_contract_sha256},null,2))}</pre>`,{cls:'small'})}
        <ol>${p.steps.map(s => `<li><textarea aria-label="단계 ${s.order}" data-manual-step="${esc(p.id)}" data-order="${s.order}" rows="2">${esc(s.text)}</textarea> <span class="muted">${esc(s.manual || '')}</span>${citation(s.anchor)}</li>`).join('')}</ol></div>`).join('') || `<div class="muted">${esc(UI.t('skill.none'))}</div>`}</div></div>
      ${manualKnowledgeHtml(r, citation)}
      <label class="check"><input type="checkbox" id="manualReviewed"> 원문 · 단계 · 고장 유형 · 관계를 검토했습니다.</label>
      <p id="manualReviewChanged" class="muted" hidden>검토 내용을 바꿨습니다. 위 검사는 원래 제안 기준입니다. 원문과 바뀐 연결을 대조한 뒤 검토 완료를 표시하세요.</p>
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
        // 방금 접수한 작업(이 브라우저의 요청 기록)을 먼저 고른다 — 2026-10-25: 결과를 연 뒤 다시 [에이전트 추출 요청]을 누르면 목록이 옛 작업을
        // 고른 채로 남아 [결과 확인]이 옛 결과를 새 결과처럼 보였다
        const chosen = extractionState()?.instance || r.extraction?.instance;
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
        const state = previous && !previous.instance ? previous : { request_id: UI.uuid() };
        sessionStorage.setItem(extractionKey, JSON.stringify(state));
        const created = await postJ(extractionUrl, { request_id: state.request_id });
        sessionStorage.setItem(extractionKey, JSON.stringify({ ...state, instance: created.instance }));
        await loadExtractions();
        if (H.preview === r) $('#manualAgentStatus').textContent = '추출 요청을 접수했습니다. 진행 · 결과 확인을 누르세요.';
      } catch (e) { if (H.preview === r) $('#manualAgentStatus').textContent = '접수 확인 실패: ' + e.message + ' 같은 요청으로 다시 확인할 수 있습니다.'; }
      finally { if (H.preview === r) button.disabled = false; }
    });
    $('#manualAgentResult').addEventListener('click', async () => {
      try {
        const instance = $('#manualExtractionRuns').value;
        if (!instance) { $('#manualAgentStatus').textContent = '추출 작업을 선택하세요. 응답을 받지 못한 요청은 추출 요청 버튼으로 접수를 재확인하세요.'; return; }
        const result = await getJ(extractionUrl + '/' + encodeURIComponent(instance));
        if (H.preview !== r) return;
        if (result.preview) { await loadManualCatalog(); H.preview = result.preview; renderPreview(); }
        else {
          const seg = result.progress ? ` · 구간 ${result.progress.done}/${result.progress.total} 완료` + (result.segments || []).filter(s => s.status !== 'DONE').map(s => ` [${s.index}: ${UI.status(s.status)}]`).join('') : '';
          $('#manualAgentStatus').textContent = '추출 상태: ' + UI.status(result.status) + seg + (result.log ? ' · ' + result.log : '') + (result.managed ? ' — 강사 관리 서버에서 처리 중입니다. 오류가 지속되면 강사에게 확인하세요.' : ` — ${UI.t('nav.instances')} 화면에서 단계 · 오류를 확인할 수 있습니다.`);
        }
      } catch (e) { if (H.preview === r) $('#manualAgentStatus').textContent = '결과 확인 실패: ' + e.message; }
    });
    // "sv:ts1:-, msr:maint-cost:+" → [{target, sign}] (A079: reviewed impact of an ingested SOP)
    const parseAffects = text => (text || '').split(',').map(s => s.trim()).filter(Boolean).map(s => { const m = s.match(/^(.*?):([+-])$/); return m ? { target: m[1].trim(), sign: m[2] } : { target: s, sign: '?' }; });
    const c = $('#manualCommit'); if (c) c.addEventListener('click', async () => {
      if (!$('#manualReviewed').checked) { $('#manualMsg').textContent = '원문을 대조하고 검토 완료를 표시하세요.'; return; }
      const links = {};
      for (const s of box.querySelectorAll('[data-fm]')) {
        const id = s.dataset.fm, p = r.procedures.find(p => p.id === id), sug = manualLink(r,p);
        const field = name => box.querySelector(`[data-${name}="${CSS.escape(id)}"]`);
        const scope = field('manual-scope').value;
        links[id] = {...sug,failureMode:s.value || null,relation:field('rel').value || null,kind:field('kind').value,affects:parseAffects(field('affects').value)};
        if (links[id].kind === 'reference') {
          if (field('reference-executable').value!=='false') { $('#manualMsg').textContent=`${p.name}: 일반 원문 참고 보관을 명시적으로 선택하세요.`; return; }
          links[id]={kind:'reference',executable:false,failureMode:null,relation:null,approver:null};
        } else if (scope === 'purchase') {
          if (!H.manualCatalog) { $('#manualMsg').textContent = H.manualCatalogError || '구매 부품 · 담당 역할 목록을 먼저 확인하세요.'; return; }
          const selected = field('manual-executable').value;
          if (!['true','false'].includes(selected)) { $('#manualMsg').textContent = `${p.name}: 원문 참고 보관 또는 실행 후보 검토를 명시적으로 선택하세요.`; return; }
          Object.assign(links[id],{scope:'purchase',executable:selected === 'true',parts:[...field('manual-parts').selectedOptions].map(option=>option.value),approver:field('manual-approver').value || null});
          if (!links[id].parts.length) { $('#manualMsg').textContent = `${p.name}: 원문에 명시한 구매 대상 부품을 선택하세요.`; return; }
          if (links[id].executable && !links[id].approver) { $('#manualMsg').textContent = `${p.name}: 원문에 명시한 구매 승인 담당 역할을 선택하세요.`; return; }
          const policy=field('manual-supplier-policy').value;
          if (policy && !['oem','lowest_approved','fastest_quote'].includes(policy)) { $('#manualMsg').textContent = `${p.name}: 원문 공급사 선정 정책을 확인하세요.`; return; }
          if (!links[id].executable && policy) { $('#manualMsg').textContent = `${p.name}: 원문 참고 보관에는 공급사 선정 정책을 지정하지 않습니다. 정책 선택을 해제하세요.`; return; }
          if (policy) { links[id].supplier_policy=policy; links[id].actions=(links[id].actions || []).map(a=>({...a,value:null})); }
          else delete links[id].supplier_policy;
          if (!links[id].executable) links[id].actions = []; // The explicit reference choice makes no ERP request; original actions stay in the source snapshot.
        } else if (scope === 'fault') { delete links[id].scope; if(sug.scope === 'purchase'){delete links[id].parts; delete links[id].executable;} }
        else { $('#manualMsg').textContent = `${p.name}: 절차의 업무 범위를 확인하세요.`; return; }
      }
      const missing = Object.entries(links).filter(([, v]) => v.kind !== 'reference' && v.scope !== 'purchase' && !v.failureMode).map(([k]) => k);
      if (missing.length) { $('#manualMsg').textContent = `고장 유형을 고르세요: ${missing.join(', ')} — 고장 조치가 아닌 확인 · 참고 절차면 종류를 「일반 원문 참고 절차」로 바꾸세요`; return; }
      c.disabled = true;
      $('#manualMsg').textContent = '적재 중…';
      try {
        const reviewed = structuredClone(r);
        box.querySelectorAll('[data-know-drop]:checked').forEach(input => {
          const group = input.dataset.knowDrop;
          if (reviewed.knowledge && Array.isArray(reviewed.knowledge[group])) reviewed.knowledge[group] = reviewed.knowledge[group].filter(x => x.id !== input.value);
        });
        box.querySelectorAll('[data-manual-name]').forEach(input => { reviewed.procedures.find(p => p.id === input.dataset.manualName).name = input.value; });
        box.querySelectorAll('[data-manual-step]').forEach(input => { reviewed.procedures.find(p => p.id === input.dataset.manualStep).steps.find(s => s.order === Number(input.dataset.order)).text = input.value; });
        for (const select of box.querySelectorAll('[data-reference-target]')) {
          const id=select.dataset.referenceTarget, p=reviewed.procedures.find(p=>p.id===id);
          if (links[id].kind!=='reference') continue;
          if (select.value) {
            const target=H.manualCatalog?.skills?.find(x=>x.id===select.value)?.reference_contract;
            const pin=box.querySelector(`[data-reference-pin="${CSS.escape(id)}"]`).value;
            const number=box.querySelector(`[data-manual-id="${CSS.escape(id)}"]`).value.trim();
            if (!target || target.id!==select.value || !/^[a-f0-9]{64}$/.test(pin) || pin!==target.contract_sha256 || number!==target.sopId || JSON.stringify(p.steps.map(s=>({order:s.order,text:s.text})))!==JSON.stringify(target.steps)) throw new Error(`${p.name}: 원문 번호 · 전체 단계 · 고정한 실행 계약이 일치하지 않습니다. 대조 내용을 다시 확인하세요.`);
            p.existing_skill_id=select.value; p.reference_contract_sha256=pin;
          } else { delete p.existing_skill_id; delete p.reference_contract_sha256; }
        }
        const reviewedLinks = {};
        box.querySelectorAll('[data-manual-id]').forEach(input => {
          const p = reviewed.procedures.find(p => p.id === input.dataset.manualId);
          p.id = input.value.trim(); reviewedLinks[p.id] = links[input.dataset.manualId];
        });
        const request={ ...reviewed, links: reviewedLinks, by: $('#manualBy').value, reviewed: true };
        if (request.previous_batch) {
          const changes=await postJ(API.process + '/api/kg/manuals/changes',request);
          if (H.preview !== r) return;
          if (changes.removed?.length) {
            const labels={Skill:'조치 방법',FailureMode:'고장 유형',Cause:'원인',Evidence:'진단 근거',Rule:'판단 규칙',
              Step:'절차 단계',KnowledgeSource:'이전 원문 판본 연결',ManualSection:'이전 원문 절 연결'};
            const names=changes.removed.map(n=>`${n.labels.map(l=>labels[l] || l).join(' · ')}: ${n.name}`).join('\n');
            const proceed=await UI.confirm({title:'개정으로 지워지는 항목을 확인하세요',
              body:'이전 판본의 다음 항목이 새 지식 지도에서 빠집니다. 원문 보관과 적재 이력은 유지됩니다.\n\n'+names,
              ok:'변경 확인 후 적재',danger:true});
            if (!proceed) { c.disabled=false; $('#manualMsg').textContent='적재하지 않았습니다. 빠진 내용을 검토하세요.'; return; }
          }
        }
        const out = await postJ(API.process + '/api/kg/manuals/commit', request);
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
    const changed = event => { if (event.target.id !== 'manualReviewed') { $('#manualReviewed').checked = false; $('#manualReviewChanged').hidden = false; } };
    box.oninput = changed;
    box.querySelectorAll('[data-manual-scope]').forEach(select => select.addEventListener('change', () => {
      box.querySelector(`[data-purchase-fields="${CSS.escape(select.dataset.manualScope)}"]`).hidden = select.value !== 'purchase';
      $('#manualReviewed').checked = false;
    }));
    box.onchange = changed;
    box.querySelectorAll('[data-kind]').forEach(kind => {
      const id=kind.dataset.kind, field=name=>box.querySelector(`[data-${name}="${CSS.escape(id)}"]`);
      const target=field('reference-target'), pin=field('reference-pin'), comparison=field('reference-comparison');
      const compare=()=>{
        const p=r.procedures.find(p=>p.id===id), registered=H.manualCatalog?.skills?.find(x=>x.id===target.value), contract=registered?.reference_contract;
        const sourceSteps=[...box.querySelectorAll(`[data-manual-step="${CSS.escape(id)}"]`)].map(x=>({order:Number(x.dataset.order),text:x.value}));
        const lines=steps=>`<ol>${steps.map(s=>`<li value="${esc(s.order)}">${esc(s.text)}</li>`).join('')}</ol>`;
        let state='기존 실행 절차 재참조 없음 · 원문 단계만 보관합니다.';
        const typed=contract && contract.id===target.value && typeof contract.sopId==='string' && /^[a-f0-9]{64}$/.test(contract.contract_sha256) && Array.isArray(contract.steps) && contract.steps.every(s=>s && Number.isInteger(s.order) && typeof s.text==='string');
        if(target.value) state=!typed ? '참조 대상 실행 계약 읽기 실패 · 적재할 수 없습니다.' : field('manual-id').value.trim()!==contract.sopId ? '원문 번호 불일치 · 재참조할 수 없습니다.' : JSON.stringify(sourceSteps)!==JSON.stringify(contract.steps) ? '원문 전체 단계와 현재 실행 단계가 다릅니다 · 재참조할 수 없습니다.' : pin.value!==contract.contract_sha256 ? '고정한 실행 계약과 현재 판본이 다릅니다 · 다시 선택하고 검토하세요.' : '원문 번호 · 전체 단계 · 고정한 실행 계약 일치 · 실행 단계 변경 없음';
        const role=manualLink(r,p).approver, roleName=H.manualCatalog?.roles?.find(x=>x.id===role)?.name;
        const sourceSections=r.sections.filter(s=>s.ref===p.section || p.steps.some(step=>step.manual===s.ref));
        comparison.innerHTML=`<p><b>${esc(state)}</b></p><p>원문 담당 역할: ${esc(roleName ? roleName+' · 참고 보관에는 사용하지 않습니다.' : '미상 · 자동으로 채우지 않습니다.')}</p><h4>이 문서의 원문 단계</h4>${lines(sourceSteps)}`+
          (target.value ? `<h4>이 문서의 원문 절 · 판본 대조</h4>${sourceSections.length ? sourceSections.map(s=>`<p><b>${esc(s.ref)} ${esc(s.title || '')}</b></p><p>${esc(s.excerpt || '원문 절 본문 없음')}</p>`).join('') : '<p>연결된 원문 절 기록 없음</p>'}<p>원문 절과 기존 등록 설명의 기준값이 같다고 추정하지 않습니다. 재참조는 기존 실행 기준을 바꾸는 작업이 아닙니다.</p>` : '')+
          (contract ? `<h4>현재 등록된 실행 단계 · ${esc(registered.name || '등록 이름 없음')} (${esc(contract.sopId || '원문 번호 미상')})</h4>${Array.isArray(contract.steps) ? lines(contract.steps) : '<p>실행 단계 정보 읽기 실패</p>'}<p>대상 원문 소유 문서: ${contract.owner ? '등록됨 · 식별자는 원문에서 확인하세요.' : '소유 문서 기록 없음'}</p><h4>현재 실행 단계가 참조하는 등록 설명</h4>${Array.isArray(contract.sections) && contract.sections.length ? contract.sections.map(s=>`<p><b>${esc(s.ref || '절 번호 미상')} ${esc(s.title || '')}</b></p><p>${esc(s.excerpt || '등록 설명 본문 없음')}</p><p class="muted">${s.source_id && s.citation ? '등록된 출처 식별 · 인용 정보는 판본 원문에서 확인하세요.' : '등록된 기존 설명 · 원본 인용 기록 없음'}</p>`).join('') : '<p>등록 설명 기록 없음 · 원문 기준값과 같은 판본이라고 판단할 수 없습니다.</p>'}` : '')+
          UI.fold('참조 대상 · 고정 판본 원문',`<pre>${esc(JSON.stringify({existing_skill_id:target.value || null,reference_contract_sha256:pin.value || null,current_contract:contract || null},null,2))}</pre>`,{cls:'small'});
      };
      const update=()=>{
        const reference=kind.value==='reference'; field('reference-fields').hidden=!reference;
        field('manual-scope').querySelector('[value="fault"]').textContent=reference ? '일반 원문 참고 · 업무 실행 연결 없음' : '고장 조치 · 고장 유형 연결 필수';
        if(reference) field('rel').value='';
        ['fm','rel','affects','manual-scope'].forEach(name=>{field(name).disabled=reference;});
        field('purchase-fields').hidden=reference || field('manual-scope').value!=='purchase';
        compare();
      };
      kind.addEventListener('change',update);
      target.addEventListener('change',()=>{pin.value=H.manualCatalog?.skills?.find(x=>x.id===target.value)?.reference_contract?.contract_sha256 || ''; compare();});
      field('manual-id').addEventListener('input',compare);
      box.querySelectorAll(`[data-manual-step="${CSS.escape(id)}"]`).forEach(input=>input.addEventListener('input',compare));
      update();
    });
    box.querySelectorAll('[data-manual-supplier-policy]').forEach(select => {
      const id=select.dataset.manualSupplierPolicy, usage=box.querySelector(`[data-manual-executable="${CSS.escape(id)}"]`);
      const update=()=>{box.querySelector(`[data-supplier-review="${CSS.escape(id)}"]`).textContent=usage.value==='false' ? (select.value ? '참고 보관에는 선정 정책을 지정할 수 없습니다. 정책 선택을 해제하세요.' : '참고 보관 · 공급사 선택과 구매요청을 하지 않습니다.') : select.value ? '선택한 정책으로 현재 부품별 견적을 계산합니다. 고정 공급사 값을 함께 보내지 않으며, 사람 승인과 구매 실행은 별도입니다.' : '정책 미지정 · 원문 고정 공급사 값으로 검토합니다. 미상인 값을 추정하지 않습니다.';};
      select.addEventListener('change',update); usage.addEventListener('change',update); update();
    });
  }
  $('#manualPreview').addEventListener('click', async () => {
    const f = $('#manualFile').files[0]; if (!f) { $('#manualResult').innerHTML = '<div class="neg">파일을 먼저 선택해 주세요.</div>'; return; }
    const b = $('#manualPreview'); b.disabled = true; b.textContent = '읽는 중…'; H.preview = null;
    $('#manualResult').innerHTML = `<div class="muted" role="status">${esc(UI.t('loading'))}</div>`;
    try {
      const b64 = await new Promise((ok, no) => { const rd = new FileReader(); rd.onload = () => ok(String(rd.result).split(',')[1] || ''); rd.onerror = () => no(new Error('파일을 읽을 수 없습니다.')); rd.readAsDataURL(f); });
      if (!H.catalog) H.catalog = await getJ(API.process + '/api/kg/catalog');
      await loadManualCatalog();
      const preview = await postJ(API.process + '/api/kg/manuals/preview', { filename: f.name, data: b64, document_id: $('#manualDocumentId').value.trim() || null });
      if ($('#manualFile').files[0] !== f) return;
      H.preview = preview; selectManualDocument(preview.document_id, preview.filename); renderPreview();
      await loadManualSources();
    } catch (e) { if ($('#manualFile').files[0] === f) $('#manualResult').innerHTML = `<div class="neg">미리보기 실패: ${esc(e.message)}</div>`; }
    finally { b.disabled = false; b.textContent = UI.t('kn.preview'); }
  });
  $('#manualFile').addEventListener('change', () => {
    H.preview = null;
    const name = $('#manualFile').files[0]?.name;
    // 앞 문서의 「문서 개정」 선택이 다른 파일에 남으면 그 파일이 앞 문서의 개정으로 올라가 앞 문서 지식이 지워진다
    // (2026-10-29 실측: HM-8 다음 HI-01). 등록된 문서의 개정이 골라져 있을 때 이름이 다른 파일을 고르면 새 문서 등록으로
    // 되돌린다. 아직 등록하지 않은 검토 중인 원문은 다음 파일도 같은 문서로 이어 올린다.
    const select = $('#manualDocumentId');
    const registered = select?.value ? H.manualDocuments?.get(select.value) : null;
    if (registered && registered.filename !== name) select.value = '';
    $('#manualFilename').textContent = name || UI.t('kn.noFile'); renderPreview();
  });

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
      <div id="legacyMeaning"></div>
      ${UI.actions(`<button class="btn outline" id="ddlReplan">선택 반영</button><button class="btn primary" id="ddlCommit" ${p.inputs.length ? '' : 'disabled'}>적재</button>`)}<span id="ddlMsg" class="muted"></span></div>`;
    if (window.hydLegacy) hydLegacy.mount($('#legacyMeaning'), { preview: p, text: H.ddlText, by: () => $('#ddlBy').value,   // A9 옛 DB 뜻 복원
      replan: async review => { const sel = {}, sys = {}; p.tables.forEach(t => { sel[t.table] = t.selected; if (t.system) sys[t.table] = t.system; });
        H.ddl = await postJ(API.process + '/api/kg/ddl/preview', { filename: p.filename, text: H.ddlText, selection: sel, systems: sys, datasource: p.datasource, catalog: p.catalog, meaning_review: review || undefined }); renderDdlPreview(); } });
    $('#ddlReplan').addEventListener('click', async () => {
      const selection = {}, systems = {};
      box.querySelectorAll('[data-sys]').forEach(s => { if (s.value) systems[s.dataset.sys] = s.value; });
      box.querySelectorAll('[data-col]').forEach(c => { if (c.checked && systems[c.dataset.col]) (selection[c.dataset.col] = selection[c.dataset.col] || []).push(c.value); });
      try { H.ddl = await postJ(API.process + '/api/kg/ddl/preview', { filename: p.filename, text: H.ddlText, selection, systems, datasource: p.datasource, catalog: p.catalog, meaning_review: p.meaningReview ? p.meaningReview.id : undefined }); renderDdlPreview(); }
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
