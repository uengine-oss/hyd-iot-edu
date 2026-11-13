/* 지식 메뉴의 두 화면: 조치 방법(목록 · 상세 · 손으로 더하기) · 문서 등록(매뉴얼 등록 → AI 추출 → 검토 · 적재, 업무 데이터 연결).
   (app.js / enterprise.js / main.js / flow.js 뒤에 실린다)
   - 조치 방법: 왼쪽 목록 · 오른쪽 상세. 읽을 내용(절차 · 연결된 지식)이 먼저이고, 고치는 칸은 [고치기]를 열었을 때 보인다.
   - 문서 등록: 맨 위 단계 줄(문서 등록 → AI 추출 → 검토 · 적재)이 지금 단계를 보이고, 등록된 문서는 표 한 장이다(줄을 누르면 그 문서로 답할 수 있는 질문).
   - 사건 → 처리 건으로 가는 길(openIncident)은 설비 회로 화면(app.js)이 쓴다. 조치 후보와 승인은 처리 건 화면 한 곳에 있다. */
(function () {
  const H = { skills: [], catalog: null, catalogError: '', manualCatalog: null, manualCatalogError: '', skillSel: null, skillNew: false, skillDrafts: new Map(), preview: null, instByIncident: new Map() };
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

  // 사건 → 그 사건을 처리하는 처리 건으로 이동(설비 회로 화면의 [이 사건의 처리 건 보기]가 쓴다). 찾으면 true
  async function openIncident(incId) {
    let id = H.instByIncident.get(incId);
    if (!id) { const list = await getJ(API.process + '/api/instances?limit=1&incident=' + encodeURIComponent(incId)); const found = list[0]; if (found) { id = found.proc_inst_id; H.instByIncident.set(incId, id); } }
    if (!id) return false;              // 못 찾으면 탭을 옮기지 않는다 — 부르는 쪽이 그 자리에 「찾지 못함」을 보인다
    selectTab('instances'); window.hydInstancesSelect(id);
    return true;
  }
  window.hydHitl = { H, openIncident };

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
    if (!H.skills.length) $('#skillList').innerHTML = UI.loading('', 'compact');
    try { H.skills = requireList(await getJ(API.process + '/api/kg/skills'), '조치 방법 목록'); }
    catch (e) { $('#skillList').innerHTML = UI.errorBlock(UI.t('error.load'), e.message, { retry: true, cls: 'compact' }); $('#skillList').querySelector('[data-retry]')?.addEventListener('click', loadSkills); return; }
    if (!H.catalog) { try { H.catalog = await getJ(API.process + '/api/kg/catalog'); H.catalogError = ''; } catch (e) { H.catalogError = e.message; } }
    if (!H.skillSel && H.skills.length && !H.skillNew) H.skillSel = H.skills[0].id;
    renderSkillList(); renderSkillDetail();
  }
  const kindName = k => k.kind === 'control' ? UI.t('skill.kind.control') : UI.t('skill.kind.workOrder');
  // 목록 한 줄: 이름, 둘째 줄에 종류 · 대상 고장 유형(종류는 색 칩이 아니라 글로)
  function renderSkillList() {
    const list = $('#skillList'); list.innerHTML = '';
    if (!H.skills.length) { list.innerHTML = UI.emptyGo('조치 방법이 없습니다', '문서를 등록해 적재하거나 [새 조치 방법]으로 손으로 더합니다.', 'knowledge', '문서 등록 열기', 'compact'); return; }
    for (const k of H.skills) {
      const it = el('div', 'item' + (k.id === H.skillSel && !H.skillNew ? ' sel' : ''));
      keyboardItem(it);
      const fm = (k.failureModes || []).map(f => f.name).join(', ');
      it.innerHTML = `<div class="row"><strong>${esc(k.name)}</strong></div><span class="sub">${esc(kindName(k))} · ${esc(fm || UI.t('skill.noFm'))}</span>`;
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
    if (!k) { box.innerHTML = UI.empty(UI.t('skill.select'), '왼쪽 목록에서 고르면 절차와 연결된 지식이 보입니다.', 'compact'); return; }
    const sel = (id, items, cur, blank) => `<select id="${id}"><option value="">${esc(blank)}</option>${items.map(x => `<option value="${esc(x.id)}" ${cur === x.id ? 'selected' : ''}>${esc(x.name)}</option>`).join('')}</select>`;
    const newForm = H.skillNew ? UI.section('대상과 종류',
      UI.field({ label: UI.t('skill.sop'), required: true, input: `<input id="skSop" placeholder="SOP-FAN-05" maxlength="40">` }) +
      UI.field({ label: UI.t('skill.fm'), required: true, input: sel('skFm', c.failureModes || [], '', '고장 유형 선택') }) +
      UI.field({ label: UI.t('skill.relation'), input: `<select id="skRel"><option value="REMEDIED_BY">${esc(UI.t('skill.rel.remedy'))}</option><option value="MITIGATED_BY">${esc(UI.t('skill.rel.mitigate'))}</option><option value="PREVENTED_BY">${esc(UI.t('skill.rel.prevent'))}</option></select>` }) +
      UI.field({ label: UI.t('skill.kind'), input: `<select id="skKind"><option value="work_order">${esc(UI.t('skill.kind.workOrder'))}</option><option value="control">${esc(UI.t('skill.kind.control'))}</option></select>` }) +
      UI.field({ label: UI.t('skill.steps'), required: true, cls: 'wide', input: `<textarea id="skSteps" rows="5" placeholder="현장 제어로 전환하고 잠근다.&#10;벨트를 교체한다.&#10;재가동 후 진동 0.9 mm/s 미만을 확인한다."></textarea>` })) : '';
    // 읽는 차례(기준 5-1): 이름 · 한 줄 → 절차 → 연결된 지식(키-값) → [고치기](이름 · 승인 역할 · 설명) → 「자세히」(식별자)
    const RULE = { EXCLUDE: UI.t('chip.excluded'), SELECT: '후보', PENALTY: UI.t('card.penalty'), WARN: UI.t('card.warn') };
    const kvRows = rows => { const r = rows.filter(([, v]) => v); return r.length ? `<dl class="kv">${r.map(([n, v]) => `<dt>${esc(n)}</dt><dd>${v}</dd>`).join('')}</dl>` : ''; };
    const linked = H.skillNew ? '' : `<section class="rd-group"><h3 class="rd-label">${esc(UI.t('skill.stepsTitle'))}</h3><ol class="steps">${(k.steps || []).map(s => `<li>${esc(s.text)} ${s.manual ? `<span class="muted">[${esc(s.manual)}]</span>` : ''}</li>`).join('') || `<li class="muted">${esc(UI.t('skill.noSteps'))}</li>`}</ol></section>
      <section class="rd-group"><h3 class="rd-label">${esc(UI.t('skill.linked'))}</h3>${kvRows([
        [UI.t('skill.fm'), (k.failureModes || []).map(f => `${esc(f.name)} <span class="muted">(${esc(REL_KO[f.relation] || f.relation)})</span>`).join('<br>') || esc(UI.t('skill.none'))],
        [UI.t('skill.causes'), (k.causes || []).map(x => esc(x.name)).join(', ') || esc(UI.t('skill.allCauses'))],
        [UI.t('skill.actions'), (k.actions || []).map(a => `${esc(hydCards.actionLabel(a))} <span class="muted">${esc(a.name)}</span>`).join('<br>')],
        [UI.t('skill.rules'), (k.rules || []).map(r => `${esc(RULE[r.effect] || r.effect)} — ${esc(UI.ruleLabel(r))}`).join('<br>')],
        [UI.t('skill.affects'), (k.affects || []).map(a => `${esc(a.name)} ${a.sign > 0 ? '↑' : '↓'}`).join(', ')],
        [UI.t('skill.approver'), esc((k.approver || {}).name || '')]])}</section>`;
    const about = H.skillNew ? '지식 지도에 조치 방법 하나를 손으로 더합니다. 대상 고장 유형과 절차를 적습니다.' : [kindName(k), k.sopId ? '절차 번호 ' + k.sopId : ''].filter(Boolean).join(' · ');
    box.innerHTML = `<header class="rd-head"><div><div class="rd-title"><h2>${esc(H.skillNew ? UI.t('skill.new') : k.name)}</h2></div><p class="rd-sub">${esc(about)}</p></div></header>
      ${H.catalogError ? `<p class="field-error" role="alert">승인 역할 · 고장 유형 목록을 읽지 못해 고를 칸이 비어 있습니다 — ${esc(H.catalogError)}. [변경 취소]를 누르면 다시 읽습니다.</p>` : ''}
      ${H.skillNew ? '' : (k.description ? `<p class="rd-p rd-group">${esc(k.description)}</p>` : '') + (k.source_document ? `<p class="rd-note">${esc(UI.t('skill.fromDoc'))} <button class="link-btn" id="skSource">${esc(UI.t('skill.openDoc'))} →</button></p>` : '') + linked}
      ${H.skillNew ? '' : `<div class="rd-group"><details class="fold small" data-skill-edit><summary>${k.source_document ? '이름 · 승인 역할 · 설명 (문서에서 온 것이라 여기서 고칠 수 없습니다)' : '고치기 · 이름 · 승인 역할 · 설명'}</summary>`}<div class="form skill-edit rd-form${H.skillNew ? ' rd-group' : ''}">` +
      UI.section(H.skillNew ? UI.t('method') : '',
        UI.field({ label: UI.t('skill.name'), required: true, input: `<input id="skName" value="${esc(k.name)}" maxlength="80">` }) +
        UI.field({ label: UI.t('skill.approver'), required: true, input: sel('skRole', c.roles || [], (k.approver || {}).id || '', '승인 역할 선택') }) +
        UI.field({ label: UI.t('skill.desc'), cls: 'wide', input: `<textarea id="skDesc" rows="2">${esc(k.description || '')}</textarea>` })) + newForm +
      `<p><span id="skMsg" class="muted" role="status"></span></p>` +
      `<div class="rd-form-actions"><button class="btn${H.skillNew ? ' primary' : ''}" id="skSave">${esc(H.skillNew ? UI.t('skill.add') : UI.t('btn.save'))}</button><button class="btn" id="skReload">${esc(UI.t('btn.cancel'))}</button></div>` +
      `</div>${H.skillNew ? '' : '</details></div>'}` +
      (H.skillNew ? '' : `<div class="rd-group">${UI.fold('자세히 · 식별자', kvRows([['조치 식별자', `<span class="mono">${esc(k.id)}</span>`], ['절차 번호', esc(k.sopId || '')]]), { cls: 'small' })}</div>`);
    const fields = [...box.querySelectorAll('input, textarea, select')];
    let draft = H.skillDrafts.get(key), draftError = '';
    if (!draft) { try { draft = JSON.parse(sessionStorage.getItem(draftKey(key)) || 'null'); } catch (_) { draftError = '저장한 초안을 읽을 수 없습니다.'; } }
    if (draft && (typeof draft !== 'object' || !draft.fields || typeof draft.fields !== 'object' || Array.isArray(draft.fields))) draftError = '저장한 초안의 형식이 올바르지 않습니다.';
    if (draft || draftError) box.querySelector('[data-skill-edit]')?.setAttribute('open', '');      // 고치던 것이 있으면 펼쳐서 보인다
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
      $('#skSave').textContent = draft.pending ? '저장 결과 확인' : key === '__new__' ? UI.t('skill.add') : UI.t('btn.save');
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
      const body = draft.pending || { name: $('#skName').value.trim(), description: $('#skDesc').value, approver: $('#skRole').value, by: manualActor(), revision: draft.revision, request_id: UI.uuid() };
      if (!draft.pending && key === '__new__') Object.assign(body, { sopId: $('#skSop').value.trim(), failureMode: $('#skFm').value, relation: $('#skRel').value, kind: $('#skKind').value, steps: $('#skSteps').value });
      if (!body.name) { $('#skMsg').textContent = UI.t('skill.nameRequired'); $('#skName').focus(); return; }
      if (!draft.pending && !body.approver) { $('#skMsg').textContent = '승인 역할을 선택하세요.'; $('#skRole').focus(); return; }
      if (!draft.pending && key === '__new__' && !body.failureMode) { $('#skMsg').textContent = '대상 고장 유형을 선택하세요.'; $('#skFm').focus(); return; }
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
          lockFields(); $('#skMsg').textContent = '저장하지 못했습니다: ' + e.message + (draft.pending ? ' 응답을 받지 못했습니다. [저장 결과 확인]을 눌러 저장됐는지 확인하세요.' : e.status === 409 ? ' 다른 곳에서 먼저 고쳤을 수 있습니다 — [변경 취소]로 저장본을 다시 읽은 뒤 고치세요.' : '');
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
    } catch (e) { H.manualCatalogError = '구매 부품 · 담당 역할 목록을 읽지 못했습니다: ' + e.message; }
  }
  function manualLink(preview, procedure) {
    if (preview.links && Object.prototype.hasOwnProperty.call(preview.links, procedure.id)) return preview.links[procedure.id] || {};
    return procedure.link || (procedure.suggestedFailureMode ? {failureMode:procedure.suggestedFailureMode} : {});
  }
  async function loadManualSources(offset = 0) {
    const box = $('#manualSources');
    try {
      const page = await getJ(API.process + '/api/kg/manuals/sources?offset=' + offset);
      box.innerHTML = UI.fold(`자세히 · 보관한 원문 ${page.total}건 (다시 열기)`, `<p class="muted">${page.total ? offset + 1 : 0}–${offset + page.items.length} / ${page.total}</p>` + page.items.map(s => `<p><a href="${API.process}/api/kg/manuals/sources/${encodeURIComponent(s.source_id)}/original">${esc(s.filename)}</a> · ${esc(UI.dateTime(s.created_at))} · ${s.status === 'READY' ? '텍스트 추출됨' : '페이지/OCR 검토 필요'} <button class="btn small" data-manual-reopen="${esc(s.source_id)}">다시 열기</button></p>`).join('') + `<div class="row-wrap">${offset ? '<button class="btn small" id="manualSourcesPrev">이전</button>' : ''}${page.next_offset !== null ? '<button class="btn small" id="manualSourcesNext">다음</button>' : ''}</div><p id="manualSourcesMsg" class="muted"></p>`, { cls: 'small' });
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
    } catch (e) {
      box.innerHTML = UI.errorBlock('보관한 원문 목록을 읽지 못했습니다', e.message, { retry: true, cls: 'compact' });
      box.querySelector('[data-retry]')?.addEventListener('click', () => loadManualSources(offset));
    }
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
    </div>${g.msg ? `<p class="field-error" role="alert">${esc(g.msg)}</p>` : ''}<div class="rd-form-actions"><button type="button" class="btn" data-golden-ask ${dis}${hydCourseAccess.attrs('documents.golden')}>${esc(g.busy ? UI.t('golden.asking') : UI.t('golden.ask'))}</button></div></div>`;
  }
  // 질문 한 건: 질문 + 판정 칩 하나 → 답 한 단락 → 「근거」 접기(확신도 · 인용한 지식 · 질의 · 근거를 확인하지 못한 답)
  function goldenItems(r) {
    const items = (r.report && r.report.items) || [];
    const head = `<p class="rd-p">${esc(UI.t('golden.answerable'))} ${r.answerable || 0} · ${esc(UI.t('golden.partial'))} ${r.partially_answerable || 0} · ${esc(UI.t('golden.notYet'))} ${r.not_yet_answerable || 0} · ${esc(UI.t('golden.grounded'))} ${r.grounded || 0}</p>` +
      (r.report && r.report.summary ? `<p class="rd-note">${esc(r.report.summary)}</p>` : '');
    return head + items.map(it => {
      const [key, tone] = ITEM_STATUS[it.status] || ['golden.notYet', 'neutral'];
      const cited = it.cited || [];
      const more = (it.confidence ? `<p class="rd-note">${esc(UI.t('golden.confidence'))} ${esc(UI.t('golden.conf.' + it.confidence))}</p>` : '') +
        (cited.length ? `<p class="rd-note">${esc(UI.t('golden.cited'))}</p><ul class="golden-cited">${cited.map(c => `<li title="${esc(c)}">${UI.name(c) !== c ? esc(UI.name(c)) : `<code>${esc(c)}</code>`}</li>`).join('')}</ul>` : `<p class="rd-note">${esc(UI.t('golden.noCited'))}</p>`) +
        (it.claimed_answer ? `<p class="rd-note">근거를 확인하지 못한 에이전트의 답</p><p>${esc(it.claimed_answer)}</p>` : '') +
        (it.cypher ? `<p class="rd-note">${esc(UI.t('golden.query'))}</p><pre>${esc(it.cypher)}</pre>` : '');
      return `<section class="rd-group rd-item golden-item"><header class="rd-head"><div class="rd-title"><h4>${esc(it.question)}</h4>${UI.chipText(UI.t(key), tone)}</div></header>` +
        `<p class="golden-answer rd-p">${esc(it.answer || '')}</p>${UI.fold(`${esc(UI.t('golden.evidence'))} ${cited.length}건`, more, { cls: 'small' })}</section>`;
    }).join('');
  }
  // 등록된 문서 표에서 줄을 열었을 때 그 아래에 그린다(접기 없이)
  function goldenSection(batch) {
    const g = H.golden[batch] || {}; const r = g.report;
    let body;
    if (g.error) body = UI.errorBlock(UI.t('golden.err.load'), g.error, { cls: 'compact' }) + goldenForm(batch, g);
    else if (r === undefined) body = UI.loading('', 'compact');
    else if (r === null || r.status === 'CANCELLED' || r.status === 'FAILED') body = `<p class="rd-note">이 문서를 읽은 뒤 답할 수 있어야 하는 질문을 적어, 넣은 지식만으로 답이 되는지 확인합니다.</p>` + goldenForm(batch, g);
    else if (!goldenFinal(r)) body = UI.loading(UI.t('golden.checking', { n: r.questions }), 'compact') + `<p class="rd-note">${esc(UI.t('golden.checkingSub'))}${r.corrections ? ' · ' + esc(UI.t('golden.corrections', { n: r.corrections.attempts })) : ''}</p>`;
    else body = goldenItems(r) + `<section class="rd-group"><h4 class="rd-label">${esc(UI.t('golden.askMore'))}</h4>${goldenForm(batch, g)}</section>`;
    return `<div class="rd-title"><h3 class="rd-label">${esc(UI.t('golden.title'))}</h3>${goldenStatusChip(r)}</div>` + body;
  }
  function renderGolden(batch) {
    const box = $('#manualHistory').querySelector(`[data-golden="${CSS.escape(batch)}"]`); if (!box) return;
    box.innerHTML = goldenSection(batch); wireGolden(box); hydCourseAccess.apply(box);   // 꺼진 까닭을 단추 옆 한 줄로(W3-07)
  }
  function wireGolden(root) {
    root.querySelectorAll('[data-golden-ask]').forEach(b => b.addEventListener('click', async () => {
      const form = b.closest('[data-golden-form]'); const batch = form.dataset.goldenForm; const g = H.golden[batch] = H.golden[batch] || {};
      g.draft = form.querySelector('[data-golden-q]').value; g.by = manualActor();      // 누가 = 이 PC의 담당자(자유 글 칸 없음)
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
      const current = ups.filter(u => u.current);
      if (H.docOpen && !current.some(u => u.batch === H.docOpen)) H.docOpen = null;
      const counts = u => `${UI.t('kn.sections')} ${u.sections} · ${UI.t('kn.procedures')} ${u.procedures} · ${UI.t('kn.steps')} ${u.steps}`;
      const versionText = u => u.status === 'ROLLED_BACK' ? UI.t('kn.rolledBack') : u.current ? UI.t('kn.current') : UI.t('kn.previous');
      const buttons = u => `<span class="rd-actions"><button class="btn small" data-manual-revise="${esc(u.document_id)}">${esc(UI.t('kn.revise'))}</button>${u.current && u.status === 'ACTIVE' ? `<button class="btn small danger" data-manual-undo="${esc(u.batch)}">${esc(UI.t('kn.undo'))}</button>` : ''}</span>`;
      const file = u => `<a href="${API.process}/api/kg/manuals/sources/${encodeURIComponent(u.source_id)}/original" title="보관한 원본 내려받기">${esc(u.filename)}</a>`;
      // 등록된 문서 표: 문서 · 판본 · 절 · 조치 방법 · 단계 · 동작. [질문 확인]을 누르면 그 줄 아래에 「이 문서로 답할 수 있는 질문」이 열린다
      const rows = current.map(u => `<tr class="${u.batch === H.docOpen ? 'pick' : ''}"><td>${file(u)}</td><td>${u.status === 'ROLLED_BACK' ? UI.chipText(UI.t('kn.rolledBack'), 'neutral') : esc(versionText(u))}</td>` +
        `<td class="r">${esc(u.sections)}</td><td class="r">${esc(u.procedures)}</td><td class="r">${esc(u.steps)}</td>` +
        `<td><span class="rd-actions"><button class="btn small ghost" data-doc-open="${esc(u.batch)}" aria-expanded="${u.batch === H.docOpen}">${u.batch === H.docOpen ? '질문 닫기' : '질문 확인'}</button>${buttons(u)}</span></td></tr>` +
        (u.batch === H.docOpen ? `<tr class="rd-row-more"><td colspan="6"><div data-golden="${esc(u.batch)}">${goldenSection(u.batch)}</div></td></tr>` : '')).join('');
      history.innerHTML = `<h2 class="rd-sec rd-group">${esc(UI.t('kn.docs'))}</h2>`
        + (current.length ? `<div class="rd-scroll"><table class="tbl rd-kpi-table"><thead><tr><th>문서</th><th>판본</th><th class="r">${esc(UI.t('kn.sections'))}</th><th class="r">${esc(UI.t('kn.procedures'))}</th><th class="r">${esc(UI.t('kn.steps'))}</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>`
          : UI.empty(UI.t('kn.docsEmpty'), UI.t('kn.docsEmptySub'), 'compact'))
        + '<p class="muted" id="manualHistoryMsg" role="status"></p>'
        + (ups.length ? UI.fold(`자세히 · ${esc(UI.t('kn.history'))} ${ups.length}건`, `<div class="rd-scroll"><table class="tbl"><thead><tr><th>매뉴얼</th><th>등록 내용</th><th>담당자</th><th>등록 시각</th><th>판본</th><th></th></tr></thead><tbody>` + ups.map(u => `<tr><td>${file(u)}</td><td>${esc(counts(u))}</td><td>${esc(u.by)}</td><td>${esc(UI.dateTime(u.t))}</td><td>${esc(versionText(u))}</td><td>${buttons(u)}</td></tr>`).join('') + '</tbody></table></div><p class="rd-note">되돌리기는 최신 판본부터 진행합니다. 보관한 원문은 지우지 않습니다.</p>', { open: wasOpen, cls: 'small manual-history' }) : '');
      history.querySelectorAll('[data-doc-open]').forEach(b => b.addEventListener('click', () => { H.docOpen = H.docOpen === b.dataset.docOpen ? null : b.dataset.docOpen; loadUploads(); }));
      wireGolden(history); hydCourseAccess.apply(history);
      current.forEach(u => fetchGolden(u.batch).then(() => renderGolden(u.batch)));
      history.querySelectorAll('[data-manual-revise]').forEach(b => b.addEventListener('click', () => {
        selectManualDocument(b.dataset.manualRevise);
        $('#manualHistoryMsg').textContent = '개정할 문서를 선택했습니다. 새 판본 파일을 선택하고 [문서 등록]을 누르세요.';
        H.preview = null; renderPreview();
      }));
      history.querySelectorAll('[data-manual-undo]').forEach(b => b.addEventListener('click', async () => {
        if (!await UI.confirm({ title: '이 판의 등록을 취소할까요?', body: '이 판이 넣은 절 · 조치 방법 · 규칙 연결이 지식 지도에서 빠집니다. 보관한 원문은 남습니다.', ok: '등록 취소', danger: true })) return;
        b.disabled = true;
        try {
          await postJ(API.process + '/api/kg/manuals/batches/' + encodeURIComponent(b.dataset.manualUndo) + '/rollback', { by: manualActor() });
          H.preview = null; renderPreview(); H.skills = [];
          await loadUploads(); if (window.hydEnt) hydEnt.loadGraph(true);
          $('#manualHistoryMsg').textContent = '등록을 취소했습니다. 지식 지도에서 이 판의 내용이 빠졌습니다.';
        } catch (e) { const m = $('#manualHistoryMsg'); m.className = 'form-msg neg'; m.setAttribute('role', 'alert'); m.textContent = '등록을 취소하지 못했습니다: ' + e.message; b.disabled = false; }
      }));
    } catch (e) {
      $('#manualHistory').innerHTML = UI.errorBlock('등록 이력을 읽지 못했습니다', e.message, { retry: true, cls: 'compact' });
      $('#manualHistory').querySelector('[data-retry]')?.addEventListener('click', loadUploads);
    }
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
    const kinds = {fm:'고장 유형',cause:'원인',skill:'조치 방법',rule:'규칙',action:'세부 동작',comp:'부품',part:'부품',sup:'공급사',role:'담당 역할',sv:'상태 변수',msr:'성과 지표',dt:'결정표',dec:'판단',in:'입력',sym:'증상',pat:'이상 유형',evidence:'근거'};
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
    text = text.replace(/\b(?:control|work_order|Action|REQUIRES_INPUT)\b/g, key => ({control:'설비 제어',work_order:'정비 요청',Action:'세부 동작',REQUIRES_INPUT:'필수 입력 연결'})[key]);
    // Action codes in diagnostic sentences resolve through the same real catalog.
    text = text.replace(/\b[A-Z][A-Z0-9_]+\b/g, key => names.get(key) || key);
    return text;
  }
  function manualValidationHtml(v, preview, catalog) {
    const block = body => `<section class="rd-group"><h3 class="rd-label">자동 검증</h3>${body}</section>`;
    if (!v) return block('<p class="rd-note">자동 검증 결과가 없습니다. 원문과 직접 대조해 검토하세요.</p>');
    if (v.checked !== true || typeof v.technical_ready !== 'boolean' || v.needs_human_review !== true || v.can_commit !== false || !Array.isArray(v.issues)) return block('<p class="rd-state bad">검증 결과를 읽지 못했습니다 — 자동 검증 응답 형식이 올바르지 않습니다. 원문과 직접 대조해 검토하세요.</p>');
    const issues=v.issues;
    const values=(v.source_value_warnings || []).filter(w => !(preview.warnings || []).includes(w));
    return block(`<p class="rd-state ${v.technical_ready === true ? 'ok' : 'warn'}">${v.technical_ready === true ? '자동 검증을 통과했습니다 — 연결 구조에는 문제가 없습니다. 내용이 원문과 맞는지는 아래에서 직접 검토하세요.' : `검토가 필요한 곳이 ${issues.length}건 있습니다 — 문서가 틀렸다는 뜻이 아니라, AI가 채우지 못했거나 사람이 확인해야 하는 곳입니다. 해당 절차에서 값을 고르거나 고친 뒤 적재하세요.`}</p><p class="rd-note">고친 연결은 적재할 때 다시 검증합니다.</p>` +
        (values.length ? UI.fold(`원문 수치 확인 필요 ${values.length}개`, `<ul>${values.map(w=>`<li>${esc(w)}</li>`).join('')}</ul>`, {cls:'small', open:true}) : '') +
        (Array.isArray(v.notices) && v.notices.length ? UI.fold(`참고 ${v.notices.length}건 (고칠 곳이 아니라 알고 넘어갈 것)`, `<ul>${v.notices.map(n => `<li>${esc(n.message)}</li>`).join('')}</ul>`, { cls: 'small' }) : '') +
        (issues.length ? `<ul>${issues.map(x=>`<li>${esc(manualIssueMessage(x,preview,catalog))}</li>`).join('')}</ul>${UI.fold('검사 항목 원문',`<pre>${esc(JSON.stringify(issues,null,2))}</pre>`,{cls:'small'})}` : '<p class="rd-note">현재 지식에서 기계가 찾은 수정 항목은 없습니다.</p>'));
  }
  function manualExecutionHtml(v, preview, catalog) {
    if (!preview.procedures.some(p => manualLink(preview,p).scope === 'purchase') && !v?.execution) return '';
    const block = body => `<section class="rd-group"><h3 class="rd-label">실행 후보 검사</h3>${body}</section>`;
    if (!v || typeof v.executable_ready !== 'boolean' || !Array.isArray(v.execution)) return block('<p class="rd-note">실행 후보 검사 기록이 없습니다. 원문 보관 여부와 실행 후보 가능 여부는 별도로 확인해야 합니다.</p>');
    return block('<p class="rd-note">원문 보관과 후보 연결의 구조 검사입니다. 실제 구매 승인이나 구매 실행 완료를 뜻하지 않습니다.</p>' + '<ul>' + v.execution.map(row => {
      const p = preview.procedures.find(p => p.id === row.sop);
      const name = p?.name ? `${p.name} (${row.sop})` : '절차 표시 이름 기록 없음';
      const valid = typeof row.executable === 'boolean' && typeof row.ready === 'boolean' && Array.isArray(row.issues);
      const label = !valid ? '연결 구조 검사 정보 읽기 실패' : row.executable === false ? '원문 참고 보관 · 실행 후보 제외' : row.ready ? '실행 후보 기계 검사 통과 · 연결 구조 검사 통과' : '실행 후보 연결 확인 필요';
      const scope=UI.evaluationInfo(row), note=scope.state==='structural' ? '실제 견적 · 재고는 실행 판단 시 확인 · 현재 실제 승인 · 실행 준비는 확인하지 않음' : scope.state==='execution' ? '실제 실행 검사 기록 있음 · 승인 · 실행 완료 아님' : '실제 승인 · 실행 준비 검사 기록 확인 안 됨';
      return `<li><b>${esc(name)}</b> · ${esc(label)}<p class="muted">${esc(note)}</p>${valid && row.issues.length ? '<ul>'+row.issues.map(x=>`<li>${esc(manualIssueMessage(x,preview,catalog))}</li>`).join('')+'</ul>' : ''}</li>`;
    }).join('')+'</ul>' + UI.fold('실행 후보 검사 원문',`<pre>${esc(JSON.stringify(v.execution,null,2))}</pre>`,{cls:'small'}));
  }
  function manualPurchaseFields(p, r) {
    const link = manualLink(r,p), purchase = link.scope === 'purchase', catalog = H.manualCatalog;
    const policies={oem:'순정품 견적',lowest_approved:'승인된 대체품 견적 중 최저가',fastest_quote:'납기가 가장 빠른 견적(승인 여부는 따로 검사)'};
    const fixed=(link.actions || []).find(a=>a.action==='action:purchase-request')?.value;
    const fixedName=(catalog?.suppliers || []).find(s=>s.id===fixed)?.name;
    const knownPolicy=Object.prototype.hasOwnProperty.call(policies,link.supplier_policy);
    const supplierState=link.supplier_policy ? `원문이 정한 공급사 선정 기준: ${knownPolicy ? policies[link.supplier_policy] : '기록을 확인해야 합니다'}.` : fixed ? `원문에 적힌 공급사: ${fixedName || '등록된 이름을 확인해야 합니다'}.` : '원문에 공급사가 적혀 있지 않습니다. 공급사를 자동으로 추정하지 않습니다.';
    const options = (rows, selected, missing) => {
      const ids = Array.isArray(selected) ? selected : selected ? [selected] : [];
      return (rows || []).map(row=>`<option value="${esc(row.id)}" ${ids.includes(row.id) ? 'selected' : ''}>${esc(row.name || '등록 이름 없음')}${row.partNo ? ' · '+esc(row.partNo) : ''}</option>`).join('') + ids.filter(id=>!(rows || []).some(row=>row.id===id)).map(id=>`<option value="${esc(id)}" selected>${esc(missing)}</option>`).join('');
    };
    return UI.field({label:'절차의 업무 범위',input:`<select id="manualScope-${esc(p.id)}" data-manual-scope="${esc(p.id)}"><option value="fault" ${!link.scope ? 'selected' : ''}>고장 조치 · 고장 유형 연결 필수</option><option value="purchase" ${purchase ? 'selected' : ''}>구매 원문 절차 · 구매 업무 범위</option>${link.scope && !purchase ? `<option value="${esc(link.scope)}" selected>범위 기록을 확인하세요</option>` : ''}</select>`}) +
      `<div class="wide" data-purchase-fields="${esc(p.id)}" ${purchase ? '' : 'hidden'}><p>고장 유형 없이 구매 대상 부품을 명시합니다. 원문 참고 보관은 실행 후보에 넣지 않으며 구매요청을 만들지 않습니다. 실행 후보는 구매요청 · 승인 담당자 · 공급 관계를 별도로 검사합니다.</p>${H.manualCatalogError ? `<p class="neg">${esc(H.manualCatalogError)}</p>` : !catalog ? '<p class="muted">구매 부품 · 담당 역할 목록 확인 전입니다.</p>' : ''}<div class="form-grid">` +
      UI.field({label:'원문 절차의 사용 방식',required:true,input:`<select id="manualExecutable-${esc(p.id)}" data-manual-executable="${esc(p.id)}"><option value="">원문을 확인하고 선택하세요</option><option value="false" ${link.executable === false ? 'selected' : ''}>원문 참고 보관 · 실행 후보 제외</option><option value="true" ${link.executable === true ? 'selected' : ''}>실행 후보로 검토 · 구매요청 연결 검사</option></select>`}) +
      UI.field({label:'구매 대상 부품',required:true,hint:'원문이 명시한 실제 등록 부품을 선택하세요. 여러 부품은 Ctrl 또는 Command를 누르고 선택합니다.',input:`<select id="manualParts-${esc(p.id)}" multiple data-manual-parts="${esc(p.id)}" ${catalog ? '' : 'disabled'}>${options(catalog?.parts,link.parts,'부품 등록 목록에서 확인되지 않음')}</select>`}) +
      UI.field({label:'구매 승인 담당 역할',hint:'실행 후보는 원문에 명시된 구매 승인 담당자가 필요합니다. 참고 보관은 미지정을 그대로 둘 수 있습니다.',input:`<select id="manualApprover-${esc(p.id)}" data-manual-approver="${esc(p.id)}" ${catalog ? '' : 'disabled'}><option value="">원문에 담당 역할 미지정</option>${options(catalog?.roles,link.approver,'담당 역할 등록 목록에서 확인되지 않음')}</select>`}) +
      UI.field({label:'원문 공급사 선정 기준',hint:'원문에 적힌 기준만 고르세요. 기준을 고르면 지금의 부품별 견적으로 공급사를 계산하고, 원문에 적힌 공급사는 쓰지 않습니다. 실제 승인이나 발주가 끝났다는 뜻은 아닙니다.',input:`<select id="manualSupplierPolicy-${esc(p.id)}" data-manual-supplier-policy="${esc(p.id)}"><option value="">지정하지 않음(원문에 적힌 공급사를 씁니다)</option>${Object.entries(policies).map(([key,label])=>`<option value="${key}" ${link.supplier_policy===key ? 'selected' : ''}>${esc(label)}</option>`).join('')}${link.supplier_policy!=null && !knownPolicy ? `<option value="${esc(link.supplier_policy)}" selected>선정 기준 기록을 확인해야 합니다</option>` : ''}</select>`}) + `<p class="muted wide">${esc(supplierState)} 참고 보관에는 공급사 선정 기준을 지정하지 않습니다.</p><p class="muted wide" data-supplier-review="${esc(p.id)}"></p></div></div>`;
  }
  function manualReferenceFields(p, r) {
    const link=manualLink(r,p), sid=p.existing_skill_id || link.existing_skill_id || '', pin=p.reference_contract_sha256 || link.reference_contract_sha256 || '';
    const rows=H.manualCatalog?.skills || [];
    return `<div class="wide" data-reference-fields="${esc(p.id)}" ${link.kind==='reference' ? '' : 'hidden'}><p>이 절차는 원문만 보관하고 실행 후보에는 넣지 않습니다. 고장 유형 · 담당 역할 · 부품 · 실행 조치는 지정하지 않습니다. 이미 등록된 같은 절차와 연결해도 그 절차의 실행 단계는 바뀌지 않습니다.</p>`+
      (H.manualCatalogError ? `<p class="neg">이미 등록된 절차 목록을 읽지 못했습니다. ${esc(H.manualCatalogError)}</p>` : !Array.isArray(H.manualCatalog?.skills) ? '<p class="muted">이미 등록된 절차 목록이 없습니다. 같은 절차를 자동으로 짐작해 연결하지 않습니다.</p>' : '')+
      UI.field({label:'참고 절차의 사용 방식',required:true,input:`<select data-reference-executable="${esc(p.id)}"><option value="">원문을 확인하고 선택하세요</option><option value="false" ${link.executable===false ? 'selected' : ''}>원문 참고 보관 · 실행 후보 제외</option></select>`})+
      UI.field({label:'이미 등록된 같은 절차와 연결',hint:'원문 번호와 모든 단계가 정확히 같은 등록 절차만 연결할 수 있습니다. 고르면 지금 등록된 그 절차의 내용을 기준으로 고정합니다.',input:`<select data-reference-target="${esc(p.id)}"><option value="">연결하지 않음(이 문서의 원문만 보관)</option>${rows.filter(x=>x.reference_contract).map(x=>`<option value="${esc(x.id)}" ${x.id===sid ? 'selected' : ''}>${esc(x.name || '등록 이름 없음')} · ${esc(x.reference_contract.sopId || '원문 번호 미상')}</option>`).join('')}${sid && !rows.some(x=>x.id===sid && x.reference_contract) ? `<option value="${esc(sid)}" selected>연결한 절차의 등록 내용을 읽지 못했습니다</option>` : ''}</select>`})+
      `<input type="hidden" data-reference-pin="${esc(p.id)}" value="${esc(pin)}"><div data-reference-comparison="${esc(p.id)}" role="status"></div></div>`;
  }
  // 2026-10-25 수업 한 바퀴: 검토 화면이 절차 · 단계 · 고장 유형 연결만 보이고 AI가 뽑은 원인 · 증거 · 규칙은 보이지 않아 학생이 원문과 대조해
  // 틀린 항목을 뺄 수 없었다(실라버스 4회차 「원인 · 수행 조건 · 규칙을 원문과 비교해 수정 · 제외」). 항목마다 원문 인용과 [제외]를 둔다.
  const KNOW_GROUPS = [['failure_modes', '고장 유형'], ['causes', '원인'], ['evidence', '확인 증거'], ['rules', '규칙']];
  function manualKnowledgeSummary(group, x, own) {
    // 이 문서에서 새로 나온 고장 유형 · 원인은 아직 카탈로그에 없다 — 제안 안의 이름을 먼저 쓴다(내부 id 를 화면에 내지 않는다)
    const name = id => own[id] || UI.name(id);
    if (group === 'causes') return `사전 확률 ${x.prior ?? '미정'}${x.failure_mode ? ' · ' + name(x.failure_mode) : ''}`;
    if (group === 'evidence') return `${hydWords.fieldName(String(x.tag || '').toLowerCase())} ${hydWords.agg(x.aggregate)}${x.window_seconds != null ? ` ${x.window_seconds}초` : ''} ${hydWords.sym(x.expect)} ${x.threshold} → ${name(x.cause)}`;
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
  // 단계 줄(기준 5-5): 문서 등록 → AI 추출 → 검토 · 적재. 등록 칸(#manualUpload) 맨 위에 한 번 두고 지금 단계만 바꾼다
  function renderManualSteps(stage) {
    const host = $('#manualUpload'); if (!host) return;
    let bar = host.querySelector('#manualSteps');
    if (!bar) { bar = el('ol', 'rd-steps'); bar.id = 'manualSteps'; bar.setAttribute('aria-label', '문서 등록 단계'); host.prepend(bar); }
    $('#manualPreview')?.classList.toggle('primary', stage === 1);      // 주 단추는 지금 단계의 것 하나: 2단계는 [AI 추출 시작], 3단계는 [검토한 내용 적재]
    bar.innerHTML = ['문서 등록', 'AI 추출', '검토 · 적재'].map((s, i) => `<li class="${i + 1 < stage ? 'done' : i + 1 === stage ? 'on' : ''}"${i + 1 === stage ? ' aria-current="step"' : ''}><span class="n">${i + 1 < stage ? '✓' : i + 1}</span>${s}</li>`).join('');
  }
  function renderPreview() {
    const r = H.preview; const box = $('#manualResult');
    $('#manualDocumentId').disabled = !!r;
    renderManualSteps(!r ? 1 : r.extraction ? 3 : 2);
    if (!r) { box.innerHTML = ''; return; }
    const known = (H.catalog || {}).failureModes || [];
    const fms = known.concat(((r.knowledge || {}).failure_modes || []).filter(f => f && f.id && !known.some(k => k.id === f.id)).map(f => ({ id: f.id, name: `${f.name || f.id} (이 문서에서 새로)` })));
    const citation = a => a ? UI.fold(`원문 인용 · ${a.page}쪽${a.located === 'loose' ? ' · 대략 일치 — 문맥 확인 필요' : a.located === 'normalized' ? ' · 공백·기호를 맞춰 찾음' : ''}`, `<pre class="rd-wrap">${esc(a.quote)}</pre>`, { cls: 'small' }) : '';
    // 진행 단계: ① 문서 등록 → ② AI 추출 → ③ 검토 · 적재. 등록만 한 문서(r.extraction 없음)에는 절 · 절차 · 검증 칸이 없다 —
    // AI가 읽기 전에 결과나 경고처럼 보이는 것을 두지 않는다(서버도 등록 응답에 절 · 절차를 싣지 않는다: manual_review.registered)
    const stage = r.extraction ? 3 : 2;
    const readWarnings = r.warnings.length ? UI.fold(`${stage === 3 ? '추출 경고' : '문서 읽기 확인'} ${r.warnings.length}건`, `<ol>${r.warnings.map(w=>`<li>${esc(w)}</li>`).join('')}</ol>`, {cls:'small'}) : '';
    const sourceLinks = `<p class="row-wrap"><a href="${API.process}/api/kg/manuals/sources/${encodeURIComponent(r.source_id)}/original">보관한 원본 내려받기</a> <button class="btn small" id="manualFullSource">추출 원문 전체 보기</button></p><div id="manualSourceText"></div>`;
    const history = UI.fold('이 문서의 이전 추출 결과', `<div class="form-grid">${UI.field({ label: '추출 작업', input: `<select id="manualExtractionRuns"><option value="">${esc(UI.t('loading'))}</option></select>` })}</div><p class="row-wrap"><button class="btn small" id="manualAgentResult">선택한 결과 열기</button> <button class="btn small" id="manualExtractionMore" hidden>이전 추출 작업 더 보기</button></p>`, { cls: 'small' });
    // 검토 화면의 절차 한 건: 요약 줄이 먼저, 수정 칸은 접는다(칸은 접혀 있어도 그대로 적재 요청에 실린다). 고장 유형이 비어 사람이 채워야 하는 절차만 펼친다
    const needsLink = p => { const l = manualLink(r, p); return l.kind !== 'reference' && l.scope !== 'purchase' && !l.failureMode; };
    const procHead = p => {
      const l = manualLink(r, p), fm = fms.find(f => f.id === l.failureMode);
      const what = l.kind === 'reference' ? '참고 절차(실행 대상 아님)' : l.scope === 'purchase' ? '구매 절차' : fm ? `${fm.name} · ${REL_KO[l.relation || 'REMEDIED_BY'] || ''}` : '고장 유형 미지정';
      return `<div class="mproc-head"><span><b>${esc(p.id)}</b> ${esc(p.name)}</span><span class="muted">${esc(what)} · 단계 ${p.steps.length}</span>${needsLink(p) ? UI.chipText('검토 필요', 'warning') : ''}</div>`;
    };
    if (stage === 2) {
      const ready = r.status === 'READY';
      box.innerHTML = `<div class="mprev">
        <div class="mstage"><p class="mstage-title"><b>${esc(r.filename)}</b> 문서를 등록했습니다 <span class="muted">· ${r.chars.toLocaleString()}자</span></p>
          <p class="muted">${ready ? '아직 AI가 문서를 읽기 전입니다. AI 추출을 시작하면 문서에서 조치 절차 · 고장 유형 · 원인을 찾아 정리합니다. 결과는 사람이 검토한 뒤에만 지식으로 적재됩니다.' : `이 문서는 「${esc(UI.status(r.status))}」 상태라 AI 추출을 시작할 수 없습니다.`}</p>
          ${readWarnings}${sourceLinks}
          <p class="row-wrap"><button class="btn primary" id="manualAgentExtract" ${ready ? '' : 'disabled'}>AI 추출 시작</button> <span id="manualAgentStatus" role="status" class="muted"></span></p>
          ${history}</div></div>`;
    } else box.innerHTML = `<div class="mprev"><div class="muted">${esc(r.filename)} · ${r.chars.toLocaleString()}자 · 절 ${r.sections.length}개 · 절차 ${r.procedures.length}개</div>
      <p class="muted" id="manualAgentStatus" role="status">AI 추출 결과입니다. 원문과 대조해 검토한 뒤 적재하세요.</p>
      ${readWarnings}
      ${manualValidationHtml(r.validation,r,{...H.catalog,...H.manualCatalog})}
      ${manualExecutionHtml(r.validation,r,{...H.catalog,...H.manualCatalog})}
      ${sourceLinks}
      <p class="row-wrap"><button class="btn small" id="manualAgentExtract">AI 추출 다시 하기</button></p>
      ${history}
      ${r.page_reviews ? UI.fold('페이지별 추출 검토 기록', r.page_reviews.map(p => `<p>${esc(p.page)}쪽: ${esc(p.note)}</p>`).join(''), { cls: 'small' }) : ''}
      <div class="mcols"><div><h3>매뉴얼 절</h3>${r.sections.map(s => `<div class="msec"><b>${esc(s.ref)}</b> ${esc(s.title)}${UI.fold('절 본문 전체', `<div class="muted rd-wrap">${esc(s.excerpt)}</div>`, { cls: 'small' })}${citation(s.anchor)}</div>`).join('') || `<div class="muted">${esc(UI.t('skill.none'))}</div>`}</div>
      <div><h3>등록할 조치 방법</h3><p class="muted">절차마다 요약을 보고, 원문과 다르면 「연결 · 단계 수정」을 열어 고치세요.</p>${r.procedures.map(p => `<div class="mproc">${procHead(p)}<details class="fold small mproc-edit" ${needsLink(p) ? 'open' : ''}><summary>연결 · 단계 수정</summary><div class="fold-body"><div class="form-grid">${UI.field({ label: UI.t('skill.sop'), input: `<input aria-label="절차 번호" data-manual-id="${esc(p.id)}" value="${esc(p.id)}">` })}${UI.field({ label: UI.t('skill.name'), input: `<input aria-label="이름" data-manual-name="${esc(p.id)}" value="${esc(p.name)}">` })}
        ${manualPurchaseFields(p,r)}
        ${UI.field({ label: UI.t('skill.fm'), hint:'고장 조치는 필수입니다. 구매 절차와 일반 원문 참고 절차에는 고장 유형을 연결하지 않습니다.', input: `<select data-fm="${esc(p.id)}"><option value="">(고르세요)</option>${fms.map(f => `<option value="${esc(f.id)}" ${f.id === manualLink(r,p).failureMode ? 'selected' : ''}>${esc(f.name)}</option>`).join('')}</select>` })}
        ${UI.field({ label: UI.t('skill.relation'), input: `<select data-rel="${esc(p.id)}"><option value="" ${manualLink(r,p).scope === 'purchase' && !manualLink(r,p).relation ? 'selected' : ''}>고장 유형 관계 없음</option>${['REMEDIED_BY', 'MITIGATED_BY', 'PREVENTED_BY'].map(v => `<option value="${v}" ${(manualLink(r,p).relation || (manualLink(r,p).scope === 'purchase' ? '' : 'REMEDIED_BY')) === v ? 'selected' : ''}>${esc(REL_KO[v])}</option>`).join('')}</select>` })}
        ${UI.field({ label: UI.t('skill.kind'), input: `<select data-kind="${esc(p.id)}"><option value="work_order">${esc(UI.t('skill.kind.workOrder'))}</option><option value="control" ${manualLink(r,p).kind === 'control' ? 'selected' : ''}>${esc(UI.t('skill.kind.control'))}</option><option value="reference" ${manualLink(r,p).kind === 'reference' ? 'selected' : ''}>일반 원문 참고 절차 · 실행 후보 제외</option></select>` })}
        ${manualReferenceFields(p,r)}
        ${UI.field({ label: UI.t('skill.affects'), hint: '상태 변수 또는 성과 지표 id와 방향(+/-)을 쉼표로. 비우면 득실 0', input: `<input aria-label="영향" data-affects="${esc(p.id)}" value="${esc((manualLink(r,p).affects || []).map(a=>a.target+':'+a.sign).join(', '))}" placeholder="예: sv:bearing-wear:- , msr:maint-cost:+">` })}</div>${citation(p.anchor)}
        ${UI.fold('절차 연결 원문',`<pre>${esc(JSON.stringify({inline:p.link,override:r.links && Object.prototype.hasOwnProperty.call(r.links,p.id) ? r.links[p.id] : undefined,suggestedFailureMode:p.suggestedFailureMode,existing_skill_id:p.existing_skill_id,reference_contract_sha256:p.reference_contract_sha256},null,2))}</pre>`,{cls:'small'})}
        <ol>${p.steps.map(s => `<li><textarea aria-label="단계 ${s.order}" data-manual-step="${esc(p.id)}" data-order="${s.order}" rows="2">${esc(s.text)}</textarea> <span class="muted">${esc(s.manual || '')}</span>${citation(s.anchor)}</li>`).join('')}</ol></div></details></div>`).join('') || `<div class="muted">${esc(UI.t('skill.none'))}</div>`}</div></div>
      ${manualKnowledgeHtml(r, citation)}
      <label class="check"><input type="checkbox" id="manualReviewed"> 원문 · 단계 · 고장 유형 · 관계를 검토했습니다.</label>
      <p id="manualReviewChanged" class="muted" hidden>검토 내용을 바꿨습니다. 위 검사는 원래 제안 기준입니다. 원문과 바뀐 연결을 대조한 뒤 검토 완료를 표시하세요.</p>
      <p id="manualMsg" class="form-msg" role="status"></p><div class="rd-form-actions"><button class="btn primary" id="manualCommit" ${r.status === 'READY' && r.sections.length && r.procedures.length ? '' : 'disabled'}>검토한 내용 적재</button></div><div id="manualDone"></div></div>`;
    $('#manualFullSource').addEventListener('click', async () => {
      try {
        const source = await getJ(API.process + '/api/kg/manuals/sources/' + encodeURIComponent(r.source_id));
        if (H.preview !== r) return;
        $('#manualSourceText').innerHTML = source.pages.map(p => UI.fold(`${p.page}쪽 전체`, `<pre class="rd-wrap">${esc(p.text)}</pre>`, { cls: 'small' })).join('');
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
        $('#manualExtractionMore').hidden = page.next_offset === null;
      } catch (e) { if (H.preview === r && $('#manualAgentStatus')) $('#manualAgentStatus').textContent = '추출 이력 조회 실패: ' + e.message; }
    };
    $('#manualExtractionMore').addEventListener('click', () => loadExtractions(true));
    loadExtractions();
    const say = (text, bad = false) => { const s = $('#manualAgentStatus'); if (!s) return; s.textContent = text; s.className = bad ? 'neg' : 'muted'; };
    const WAITING = ['TODO', 'IN_PROGRESS', 'SUBMITTED'];
    const progressOf = result => result.progress ? ` · 구간 ${result.progress.done}/${result.progress.total} 완료` : '';
    // 추출 결과를 연다. 아직 진행 중이면 watch 일 때 3초 뒤 다시 확인한다(같은 문서 화면이 열려 있는 동안만, 최대 10분)
    const openResult = async (instance, watch, tries = 0) => {
      if (H.preview !== r) return;
      if (watch && state.tab !== 'knowledge') { setTimeout(() => openResult(instance, true, tries), 3000); return; }
      try {
        const result = await getJ(extractionUrl + '/' + encodeURIComponent(instance));
        if (H.preview !== r) return;
        if (result.preview) { await loadManualCatalog(); if (H.preview !== r) return; H.preview = result.preview; renderPreview(); return; }
        if (WAITING.includes(result.status)) {
          say(`AI 추출 중…${progressOf(result)} (보통 1~2분 걸립니다. 끝나면 결과가 여기에 표시됩니다)`);
          if (watch && tries < 200) setTimeout(() => openResult(instance, true, tries + 1), 3000);
          else if (watch) say('AI 추출이 10분 넘게 끝나지 않았습니다. 「이 문서의 이전 추출 결과」에서 나중에 다시 열 수 있습니다.', true);
          return;
        }
        const stuck = (result.segments || []).filter(s => s.status !== 'DONE').map(s => ` [구간 ${s.index}: ${UI.status(s.status)}]`).join('');
        say(`AI 추출이 끝나지 않았습니다: ${UI.status(result.status)}${progressOf(result)}${stuck}. ${UI.t('nav.instances')} 화면에서 이 추출 작업의 단계와 오류를 확인할 수 있습니다.`, true);
        const s = $('#manualAgentStatus');
        if (s) s.insertAdjacentHTML('beforeend', ` <button type="button" class="link-btn" data-go-tab="instances">${esc(UI.t('nav.instances'))} 열기 →</button>`);
        if (s && result.log) s.insertAdjacentHTML('beforeend', ' ' + UI.fold('추출 기록 원문', `<pre class="rd-wrap">${esc(result.log)}</pre>`, { cls: 'small' }));      // 엔진 기록 원문은 문장에 잇지 않고 접어 둔다
      } catch (e) { if (H.preview === r) say('추출 결과를 확인하지 못했습니다: ' + e.message, true); }
    };
    $('#manualAgentExtract').addEventListener('click', async () => {
      // 검토하며 고친 칸이 있으면 새 추출 결과가 그 내용을 덮는다 — 먼저 묻는다(고친 표시 = #manualReviewChanged)
      const edited = $('#manualReviewChanged') && !$('#manualReviewChanged').hidden;
      if (edited && !await UI.confirm({ title: 'AI 추출을 다시 할까요?', body: '지금 고친 검토 내용은 새 추출 결과로 바뀌어 사라집니다.', ok: '다시 추출', danger: true })) return;
      const button = $('#manualAgentExtract'); button.disabled = true;
      say('AI 추출을 요청하는 중…');
      try {
        const previous = extractionState();
        const state = previous && !previous.instance ? previous : { request_id: UI.uuid() };
        sessionStorage.setItem(extractionKey, JSON.stringify(state));
        const created = await postJ(extractionUrl, { request_id: state.request_id });
        sessionStorage.setItem(extractionKey, JSON.stringify({ ...state, instance: created.instance }));
        await loadExtractions();
        if (H.preview === r) openResult(created.instance, true);
      } catch (e) { if (H.preview === r) { say('AI 추출을 시작하지 못했습니다: ' + e.message + ' — 다시 누르면 같은 요청으로 확인합니다.', true); button.disabled = false; } }
    });
    $('#manualAgentResult').addEventListener('click', () => {
      const instance = $('#manualExtractionRuns').value;
      if (!instance) { say('열 추출 작업을 선택하세요.', true); return; }
      openResult(instance, false);
    });
    // 이 브라우저가 방금 요청한 추출이 아직 결과 전이면(화면을 다시 열었을 때) 이어서 지켜본다
    if (stage === 2 && extractionState()?.instance) openResult(extractionState().instance, true);
    // "sv:ts1:-, msr:maint-cost:+" → [{target, sign}] (A079: reviewed impact of an ingested SOP)
    const parseAffects = text => (text || '').split(',').map(s => s.trim()).filter(Boolean).map(s => { const m = s.match(/^(.*?):([+-])$/); return m ? { target: m[1].trim(), sign: m[2] } : { target: s, sign: '?' }; });
    const c = $('#manualCommit'); if (c) c.addEventListener('click', async () => {
      $('#manualMsg').className = 'form-msg neg';      // 아래 검사에서 멈춘 까닭은 오류로 보인다(진행 · 완료는 그 자리에서 색을 바꾼다)
      const by = manualActor(); if (!by) { $('#manualMsg').textContent = '담당자 정보를 읽지 못했습니다. 화면을 새로 고친 뒤 다시 해 주세요.'; return; }
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
          if (policy && !['oem','lowest_approved','fastest_quote'].includes(policy)) { $('#manualMsg').textContent = `${p.name}: 원문 공급사 선정 기준을 확인하세요.`; return; }
          if (!links[id].executable && policy) { $('#manualMsg').textContent = `${p.name}: 원문 참고 보관에는 공급사 선정 기준을 지정하지 않습니다. 기준을 「지정하지 않음」으로 바꾸세요.`; return; }
          if (policy) { links[id].supplier_policy=policy; links[id].actions=(links[id].actions || []).map(a=>({...a,value:null})); }
          else delete links[id].supplier_policy;
          if (!links[id].executable) links[id].actions = []; // The explicit reference choice makes no ERP request; original actions stay in the source snapshot.
        } else if (scope === 'fault') { delete links[id].scope; if(sug.scope === 'purchase'){delete links[id].parts; delete links[id].executable;} }
        else { $('#manualMsg').textContent = `${p.name}: 절차의 업무 범위를 확인하세요.`; return; }
      }
      const missing = Object.entries(links).filter(([, v]) => v.kind !== 'reference' && v.scope !== 'purchase' && !v.failureMode).map(([k]) => k);
      missing.forEach(id => { const d = box.querySelector(`[data-fm="${CSS.escape(id)}"]`)?.closest('details'); if (d) d.open = true; });
      if (missing.length) { $('#manualMsg').textContent = `고장 유형을 고르세요: ${missing.join(', ')} — 고장 조치가 아닌 확인 · 참고 절차면 종류를 「일반 원문 참고 절차」로 바꾸세요`; return; }
      c.disabled = true;
      $('#manualMsg').className = 'form-msg'; $('#manualMsg').textContent = '적재 중…';
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
            if (!target || target.id!==select.value || !/^[a-f0-9]{64}$/.test(pin) || pin!==target.contract_sha256 || number!==target.sopId || JSON.stringify(p.steps.map(s=>({order:s.order,text:s.text})))!==JSON.stringify(target.steps)) throw new Error(`${p.name}: 원문 번호나 단계가 연결할 등록 절차와 다릅니다. 대조 내용을 다시 확인하세요.`);
            p.existing_skill_id=select.value; p.reference_contract_sha256=pin;
          } else { delete p.existing_skill_id; delete p.reference_contract_sha256; }
        }
        const reviewedLinks = {};
        box.querySelectorAll('[data-manual-id]').forEach(input => {
          const p = reviewed.procedures.find(p => p.id === input.dataset.manualId);
          p.id = input.value.trim(); reviewedLinks[p.id] = links[input.dataset.manualId];
        });
        const request={ ...reviewed, links: reviewedLinks, by, reviewed: true };
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
          ? '후보 규칙에 연결: ' + activated.map(([fm, rules]) => `${hydWords.idName(fm)} → ${rules.map(r => hydWords.idName(r)).join(', ')}`).join(' · ') + ' (되돌리면 함께 빠집니다)'
          : '연결된 후보 규칙이 없어 판단 후보는 바뀌지 않았습니다.');
        c.textContent = '적재 완료';
        $('#manualMsg').className = 'form-msg pos';
        $('#manualDone').innerHTML = `<div class="rd-form-actions"><button class="btn" data-go-tab="ontology">지식 지도에서 보기 →</button><button class="btn" data-go-tab="skills">조치 방법에서 보기 →</button></div>`;
        H.skills = [];
        await loadUploads(); if (window.hydEnt) hydEnt.loadGraph(true);
      } catch (e) { if (H.preview === r) { $('#manualMsg').className = 'form-msg neg'; $('#manualMsg').textContent = '적재하지 못했습니다: ' + e.message; c.disabled = false; } }
    });
    const changed = event => { if ($('#manualReviewed') && event.target.id !== 'manualReviewed' && event.target.id !== 'manualExtractionRuns') { $('#manualReviewed').checked = false; $('#manualReviewChanged').hidden = false; } };
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
        let state='이미 등록된 절차와 연결하지 않고, 이 문서의 원문 단계만 보관합니다.';
        const typed=contract && contract.id===target.value && typeof contract.sopId==='string' && /^[a-f0-9]{64}$/.test(contract.contract_sha256) && Array.isArray(contract.steps) && contract.steps.every(s=>s && Number.isInteger(s.order) && typeof s.text==='string');
        if(target.value) state=!typed ? '연결할 절차의 등록 내용을 읽지 못해 적재할 수 없습니다.' : field('manual-id').value.trim()!==contract.sopId ? '원문 번호가 등록된 절차와 달라 연결할 수 없습니다.' : JSON.stringify(sourceSteps)!==JSON.stringify(contract.steps) ? '원문의 단계가 등록된 절차의 단계와 달라 연결할 수 없습니다.' : pin.value!==contract.contract_sha256 ? '고른 뒤에 등록된 절차가 바뀌었습니다. 연결할 절차를 다시 고르고 검토하세요.' : '원문 번호와 모든 단계가 등록된 절차와 같습니다. 등록된 절차의 실행 단계는 바뀌지 않습니다.';
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
      const update=()=>{box.querySelector(`[data-supplier-review="${CSS.escape(id)}"]`).textContent=usage.value==='false' ? (select.value ? '참고 보관에는 공급사 선정 기준을 지정할 수 없습니다. 기준을 「지정하지 않음」으로 바꾸세요.' : '참고 보관은 공급사를 고르지 않고 구매 요청도 만들지 않습니다.') : select.value ? '고른 기준으로 지금의 부품별 견적에서 공급사를 계산합니다. 원문에 적힌 공급사는 쓰지 않으며, 사람 승인과 구매 실행은 따로 진행됩니다.' : '기준을 지정하지 않으면 원문에 적힌 공급사로 검토합니다. 원문에 없는 값은 추정하지 않습니다.';};
      select.addEventListener('change',update); usage.addEventListener('change',update); update();
    });
  }
  // 담당자 = 이 PC의 담당자(inbox.js me — 이름으로 적재 이력에 남는다). 화면에 담당자 칸은 없다
  const manualActor = () => window.hydInbox?.me?.()?.name || '';
  $('#manualPreview').addEventListener('click', async () => {
    const f = $('#manualFile').files[0]; if (!f) { $('#manualResult').innerHTML = '<p class="field-error" role="alert">등록할 파일을 먼저 선택하세요.</p>'; return; }
    const b = $('#manualPreview'); b.disabled = true; b.textContent = '등록하는 중…'; H.preview = null;
    $('#manualResult').innerHTML = UI.loading('문서를 등록하는 중', 'compact');
    try {
      const b64 = await new Promise((ok, no) => { const rd = new FileReader(); rd.onload = () => ok(String(rd.result).split(',')[1] || ''); rd.onerror = () => no(new Error('파일을 읽을 수 없습니다.')); rd.readAsDataURL(f); });
      if (!H.catalog) H.catalog = await getJ(API.process + '/api/kg/catalog');
      await loadManualCatalog();
      const preview = await postJ(API.process + '/api/kg/manuals/preview', { filename: f.name, data: b64, document_id: $('#manualDocumentId').value.trim() || null });
      if ($('#manualFile').files[0] !== f) return;
      H.preview = preview; selectManualDocument(preview.document_id, preview.filename); renderPreview();
      await loadManualSources();
    } catch (e) { if ($('#manualFile').files[0] === f) $('#manualResult').innerHTML = UI.errorBlock('문서를 등록하지 못했습니다', e.message, { cls: 'compact' }); }
    finally { b.disabled = false; b.textContent = UI.t('kn.preview'); }
  });
  // 수업 경계(서버 GET /api/course-access): 수업 단계에서는 제공 문서만 등록된다 — 미리 안내하지 않고 다른 문서를 올리면 서버 거절 까닭을
  // 미리보기 실패로 보인다(안내는 벗어난 행동에서만). 골든 질문 평가 단추는 서버 까닭으로 끈다
  function courseScope() {
    // 제공 문서 받기 링크: 서버 수업 경계가 가진 제공 문서 목록(course-access provided_documents = 강사 서명 추출 묶음) 하나에서 그린다(W2-21)
    const docs = $('#providedDocs');
    if (docs) {
      const list = hydCourseAccess.access?.provided_documents;
      docs.innerHTML = Array.isArray(list) ? list.map(f => `<a href="samples/${encodeURIComponent(f)}" download>${esc(f)}</a>`).join(' · ')
        : hydCourseAccess.error ? `<span class="neg">수업 단계 정보를 읽지 못해 목록이 없습니다</span>` : esc(UI.t('loading'));
    }
    hydCourseAccess.apply($('#manualHistory'));
  }
  hydCourseAccess.onChange(courseScope); courseScope();   // 표가 먼저 와 있었으면 바로 그린다
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
  // msg: 이력 위 알림 줄(되돌리기 결과) — 이력을 다시 그리면 그 줄도 새로 만들어지므로 그릴 때 함께 넣는다(한바퀴3: 결과 문장이 바로 지워졌다)
  async function loadIngests(msg = '') {
    const box = $('#ddlHistory'); if (!box) return;
    try {
      const rows = await getJ(API.process + '/api/kg/ingests');
      const batches = {};
      rows.forEach(r => { (batches[r.batch] = batches[r.batch] || []).push(r); });
      const keys = Object.keys(batches);
      box.innerHTML = `<p id="ddlHistoryMsg" class="muted" role="status">${esc(msg)}</p>` + (keys.length ? `<section class="rd-group"><h3 class="rd-label">연결 이력 ${keys.length}건</h3><div class="rd-scroll"><table class="tbl"><thead><tr><th>스키마 파일</th><th>넣은 항목</th><th>연결 번호</th><th></th></tr></thead><tbody>`
        + keys.map(k => `<tr><td>${esc((batches[k][0] || {}).source || '')}</td><td>${batches[k].map(r => `${esc(LABEL_KO[r.label] || r.label)} ${r.nodes}`).join(' · ')}</td><td><code>${esc(k)}</code></td><td><button class="btn small danger" data-clear="${esc(k)}">되돌리기</button></td></tr>`).join('') + '</tbody></table></div></section>' : '');
      box.querySelectorAll('[data-clear]').forEach(b => b.addEventListener('click', async () => {
        if (!await UI.confirm({ title: '이 연결을 되돌릴까요?', body: '이 스키마 파일로 넣은 시스템 · 입력 데이터를 지식 지도에서 지웁니다. 다른 연결이 함께 쓰는 항목은 남습니다.', ok: '되돌리기', danger: true })) return;
        b.disabled = true;
        try { const out = await postJ(API.process + '/api/kg/ingests/' + encodeURIComponent(b.dataset.clear) + '?by=' + encodeURIComponent(manualActor()), null, 'DELETE'); await loadIngests(`되돌렸습니다. 지운 항목 ${out.deleted}개 · 되살린 항목 ${out.restored || 0}개 · 남긴 항목 ${out.retained || 0}개`); if (window.hydEnt) hydEnt.loadGraph(true); }
        catch (e) { const m = $('#ddlHistoryMsg'); m.className = 'form-msg neg'; m.setAttribute('role', 'alert'); m.textContent = '되돌리지 못했습니다: ' + e.message; b.disabled = false; }
      }));
    } catch (e) { box.innerHTML = `<p id="ddlHistoryMsg" class="muted" role="status">${esc(msg)}</p>` + UI.errorBlock('연결 이력을 읽지 못했습니다', e.message, { retry: true, cls: 'compact' }); box.querySelector('[data-retry]')?.addEventListener('click', () => loadIngests()); }
  }
  function renderDdlPreview() {
    const p = H.ddl; const box = $('#ddlResult');
    if (!p) { box.innerHTML = ''; return; }
    const existing = (p.existingSystems || []).map(s => s.id);
    const sysName = id => [...(p.existingSystems || []), ...p.systems].find(s => s.id === id && s.name && s.name !== id)?.name || hydWords.system(id);      // 응답에 이름이 있으면 그것, 없으면 시스템 이름 사전(plainWords.js)
    const sysOptions = sel => [...new Set([...existing, ...p.systems.map(s => s.id), sel].filter(Boolean))].map(id => `<option value="${esc(id)}" title="${esc(id)}" ${id === sel ? 'selected' : ''}>${esc(sysName(id))}</option>`).join('');
    box.innerHTML = `<div class="mprev"><div class="muted">${esc(p.filename)} · ${p.chars}자 · 테이블 ${p.tables.length}개${p.warnings.length ? ' · <span class="neg">' + p.warnings.map(esc).join(' ') + '</span>' : ''}</div>
      <div class="mcols"><div><h3>테이블 → 출처 시스템</h3>${p.tables.map(t => `<div class="msec"><b>${esc(t.table)}</b> <span class="muted">${esc(t.comment || '')}</span>
        ${UI.field({ label: '출처 시스템', input: `<select data-sys="${esc(t.table)}"><option value="">(없음 · 적재 안 함)</option>${sysOptions(t.system)}</select>` })}
        <div class="ddlcols">${t.columns.map(c => `<label><input type="checkbox" data-col="${esc(t.table)}" value="${esc(c)}" ${t.selected.includes(c) ? 'checked' : ''}> ${esc(c)}</label>`).join('')}</div></div>`).join('')}</div>
      <div><h3>입력 데이터와 실제 위치</h3>${UI.field({ label: '원천 연결', input: `<select id="ddlSource">${(p.sourceOptions || []).map(o => `<option value="${esc(o.id)}" ${o.id === p.datasource ? 'selected' : ''}>${esc(o.label)} (${esc(o.schema)} 스키마)</option>`).join('')}</select>`,
        hint: (p.sourceNotes || []).join(' ') || '고른 원천의 표 · 열로 잇습니다' })}<div class="rd-scroll"><table class="tbl"><thead><tr><th>이름</th><th>데이터 형식</th><th>스키마 · 표 · 열</th><th>업무 시스템</th></tr></thead><tbody>${p.inputs.map(i => `<tr><td>${esc(i.name)}</td><td>${esc(i.typeRef)}</td><td>${esc(i.schema)}<br>${esc(i.table)}<br>${esc(i.column)}</td><td title="${esc(i.system)}">${esc(sysName(i.system))}</td></tr>`).join('') || '<tr><td colspan="4" class="muted">고른 열이 없습니다</td></tr>'}</tbody></table></div>${UI.fold('식별자와 규칙 변수', p.inputs.map(i => `<p>${esc(i.schema)} · ${esc(i.table)} · ${esc(i.column)}<br><code>${esc(i.id)}</code> <code>${esc(i.variable)}</code></p>`).join(''), { cls: 'small' })}</div></div>
      <div id="legacyMeaning"></div>
      <p><span id="ddlMsg" class="muted" role="status"></span></p><div class="rd-form-actions"><button class="btn" id="ddlCommit" ${p.inputs.length ? '' : 'disabled'}>적재</button><button class="btn" id="ddlReplan">고른 열로 다시 읽기</button></div></div>`;
    const ddlSay = (text, bad = false) => { const m = $('#ddlMsg'); if (!m) return; m.textContent = text; m.className = bad ? 'form-msg neg' : 'muted'; m.setAttribute('role', bad ? 'alert' : 'status'); };
    if (window.hydLegacy) hydLegacy.mount($('#legacyMeaning'), { preview: p, text: H.ddlText, by: () => manualActor(),   // A9 옛 DB 뜻 복원
      replan: async review => { const sel = {}, sys = {}; p.tables.forEach(t => { sel[t.table] = t.selected; if (t.system) sys[t.table] = t.system; });
        H.ddl = await postJ(API.process + '/api/kg/ddl/preview', { filename: p.filename, text: H.ddlText, selection: sel, systems: sys, datasource: p.datasource, catalog: p.catalog, meaning_review: review || undefined }); renderDdlPreview(); } });
    $('#ddlSource').addEventListener('change', async e => {   // 원천을 바꾸면 그 원천의 스키마로 다시 해석한다(서버 ddl_sync.place)
      try { H.ddl = await postJ(API.process + '/api/kg/ddl/preview', { filename: p.filename, text: H.ddlText, datasource: e.target.value, catalog: p.catalog }); renderDdlPreview(); }
      catch (err) { ddlSay('고른 원천으로 다시 읽지 못했습니다: ' + err.message, true); }
    });
    $('#ddlReplan').addEventListener('click', async () => {
      const selection = {}, systems = {};
      box.querySelectorAll('[data-sys]').forEach(s => { if (s.value) systems[s.dataset.sys] = s.value; });
      box.querySelectorAll('[data-col]').forEach(c => { if (c.checked && systems[c.dataset.col]) (selection[c.dataset.col] = selection[c.dataset.col] || []).push(c.value); });
      try { H.ddl = await postJ(API.process + '/api/kg/ddl/preview', { filename: p.filename, text: H.ddlText, selection, systems, datasource: p.datasource, catalog: p.catalog, meaning_review: p.meaningReview ? p.meaningReview.id : undefined }); renderDdlPreview(); }
      catch (e) { ddlSay('고른 열로 다시 읽지 못했습니다: ' + e.message, true); }
    });
    $('#ddlCommit').addEventListener('click', async () => {
      const c = $('#ddlCommit'); c.disabled = true; ddlSay('적재 중…');
      try {
        const out = await postJ(API.process + '/api/kg/ddl/commit', { ...p, by: manualActor() });
        ddlSay(`적재했습니다. 시스템 ${out.systems}개 · 입력 데이터 ${out.inputs}개. 되돌리려면 아래 연결 이력에서 [되돌리기]를 누르세요.`);
        c.textContent = '적재 완료';
        await loadIngests(); if (window.hydEnt) hydEnt.loadGraph(true);
      } catch (e) { ddlSay('적재하지 못했습니다: ' + e.message, true); c.disabled = false; }
    });
  }
  $('#ddlPreview').addEventListener('click', async () => {
    const f = $('#ddlFile').files[0]; if (!f) { $('#ddlResult').innerHTML = '<p class="field-error" role="alert">스키마 파일을 먼저 선택하세요.</p>'; return; }
    const b = $('#ddlPreview'); b.disabled = true; b.textContent = '읽는 중…'; H.ddl = null;
    $('#ddlResult').innerHTML = UI.loading('스키마 파일을 읽는 중', 'compact');
    try {
      H.ddlText = await f.text();
      const preview = await postJ(API.process + '/api/kg/ddl/preview', { filename: f.name, text: H.ddlText, catalog: $('#ddlCatalog').value.trim() });
      if ($('#ddlFile').files[0] !== f) return;
      H.ddl = preview; renderDdlPreview(); await loadIngests();
    } catch (e) { if ($('#ddlFile').files[0] === f) $('#ddlResult').innerHTML = UI.errorBlock('스키마 파일을 읽지 못했습니다', e.message, { cls: 'compact' }); }
    finally { b.disabled = false; b.textContent = UI.t('kn.ddlPreview'); }
  });
  $('#ddlFile').addEventListener('change', () => { H.ddl = null; $('#ddlFilename').textContent = $('#ddlFile').files[0]?.name || UI.t('kn.noFile'); renderDdlPreview(); });
  $('#ddlCatalog').addEventListener('input', () => { H.ddl = null; renderDdlPreview(); });

  renderManualSteps(1);
  /* ------------------------------------------------ tab hooks */
  hydTabs.onShow(name => {
    if (name === 'skills') loadSkills();
    if (name === 'knowledge') { loadUploads(); loadIngests(); }
  });
})();
