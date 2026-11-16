/* 지식 메뉴의 두 화면: 조치 방법(목록 + 상세 · 손으로 더하기) · 문서 등록(올리기 → AI 추출 → 검토 → 적재, 업무 DB 표 정의 연결).
   (app.js / enterprise.js / main.js 뒤에 실린다. 디자인 기준 5-1 · 5-3 · 7절. 화면의 배치는 knowledge.css 의 「조치 방법 · 문서 등록」 절)
   - 조치 방법: 왼쪽 목록(.rows) · 오른쪽 상세(.panel — 머리는 공통 상세 머리 .pane-head). 첫 화면은 절차 · 대상 고장 유형 · 승인 역할이고, 그 밖의 연결(원인 · 세부 동작 ·
     적용 규칙 · 영향 지표 · 출처)은 「연결된 지식」 접기, 식별자와 지우기는 머리의 더 보기 메뉴에 있다. 손으로 더한 것만 같은 판 안의 폼으로 고치고, 문서에서 온 것은 그 문서를 개정해 고친다.
   - 문서 등록: 맨 위 단계 줄(올리기 → AI 추출 → 검토 → 적재)이 지금 단계를 보이고 그 아래에는 지금 단계의 내용만 있다. 올리기 단계에는 길이 둘이다 —
     「제공 문서에서 고르기」(목록의 줄을 누르면 화면이 같은 출처의 samples/<파일>을 읽어 그 문서를 바로 올린다. 내려받지 않는다)와 「내 파일 올리기」(파일 고르기 + 새 문서 / 개정).
     두 길은 같은 올리기 요청을 보낸다(uploadManual · readDdl) — 서버는 문서를 내용으로 알아본다. 제공 문서를 여럿 고르면 「한 번에 적재」(runBatch — 문서마다 올리기 → AI 추출 → 적재를
     차례로 돌리고, 검토가 필요한 문서는 적재하지 않고 멈춘다)가 나온다. 검토는 목록 + 상세다(왼쪽 제안 목록, 오른쪽 원문 인용과 고칠 칸 — 고칠 칸은 보이지 않는 동안에도 그대로 적재 요청에 실린다).
     단계 줄 아래 「적재한 문서」는 줄마다 이름 · 넣은 내용 · 더 보기 메뉴이고, 줄을 누르면 옆 판(#docSheet)에 그 문서로 답할 수 있는 질문이 열린다. 보관한 원문 · 등록 이력도 옆 판이다.
   - 실시간: AI 추출은 처리 건(매뉴얼 추출 흐름의 AI 에이전트 단계)으로 돈다. 2단계 자리에서 그 단계의 실행 기록(읽는 구간 · 도구 호출 · 에이전트의 말)이
     생기는 대로 흘러나온다(liveStream.js hydLive.agentWork). 끝나면 3단계로 넘어가고 기록은 「추출 과정 보기」에 남는다. 적재는 요청이 차례로 가는 대로
     단계가 하나씩 채워진다(hydLive.steps). 실시간 연결이 끊긴 동안만 5초마다 묻고 그 사실을 화면에 적는다. 한 번에 적재는 문서마다 지금 하는 일이 단계 타임라인(UI.timeline)에 흐른다.
   - 사건 → 처리 건으로 가는 길(openIncident)은 설비 회로 화면(app.js)이 쓴다. 조치 후보와 승인은 처리 건 화면 한 곳에 있다. */
(function () {
  const H = { skills: [], catalog: null, catalogError: '', manualCatalog: null, manualCatalogError: '', skillSel: null, skillNew: false, skillKind: '', skillDrafts: new Map(), preview: null, instByIncident: new Map(),
    docKind: 'manual', commit: null, review: { kind: '', sel: '' }, samples: new Map(), sampleTitles: new Map(), loadedFiles: new Map(), sending: null, sent: null, ddlReading: null,
    uploads: [], picked: new Set(), batch: null, sheet: null };
  const icon = name => UI.icon(name);
  // 폼 아래 · 목록 위의 한 줄: 결과는 회색, 실패는 빨간 글(role=alert)
  const note = (node, text, bad = false) => { if (!node) return; node.textContent = text; if (bad) node.dataset.tone = 'danger'; else delete node.dataset.tone; node.setAttribute('role', bad ? 'alert' : 'status'); };
  const table = (head, rows) => `<div class="table-container"><table class="table"><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table></div>`;
  // 단계 줄(.stream-phases): 끝난 단계는 초록 체크, 지금 단계는 제품색, 남은 단계는 점선. busy = 시스템이 일하는 중(고리가 돈다) — 사람이 할 차례면 돌지 않는다(data-idle)
  function phaseRow(host, names, at, o = {}) {
    if (!host) return;
    host.innerHTML = names.map((n, i) => {
      const st = o.done || i + 1 < at ? 'done' : i + 1 === at ? 'now' : 'todo';
      return `<span class="phase" role="listitem" data-state="${st}"${st === 'now' && !o.busy ? ' data-idle' : ''}${st === 'now' ? ' aria-current="step"' : ''}><i></i>${esc(n)}</span>`;
    }).join('');
  }
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
    // 제공 문서 목록의 「적재됨」: 「등록할 문서」의 개정 선택지와 같은 것(지금 판본이 적재돼 있는 문서)을 파일 이름으로 묶는다
    H.loadedFiles = new Map();
    docs.forEach(u => H.loadedFiles.set(u.filename, (H.loadedFiles.get(u.filename) || []).concat(u.document_id)));
    renderProvided();
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
    if (!H.skills.length) $('#skillList').innerHTML = `<div class="pane-list-note">${UI.loading('')}</div>`;
    try { H.skills = requireList(await getJ(API.process + '/api/kg/skills'), '조치 방법 목록'); }
    catch (e) {
      $('#skillKinds').innerHTML = ''; $('#skillDetail').innerHTML = ''; $('#skillDetail').dataset.key = '';
      $('#skillList').innerHTML = `<div class="pane-list-note">${UI.errorBlock(UI.t('error.load'), e.message, { retry: true })}</div>`;
      $('#skillList').querySelector('[data-retry]')?.addEventListener('click', loadSkills); return;
    }
    if (!H.catalog) { try { H.catalog = await getJ(API.process + '/api/kg/catalog'); H.catalogError = ''; } catch (e) { H.catalogError = e.message; } }
    if (!H.skillSel && H.skills.length && !H.skillNew) H.skillSel = H.skills[0].id;
    renderSkillList(); renderSkillDetail();
  }
  const isControl = k => k.kind === 'control';
  const kindName = k => isControl(k) ? UI.t('skill.kind.control') : UI.t('skill.kind.workOrder');
  const kindIcon = k => icon(isControl(k) ? 'sliders-horizontal' : 'wrench');
  // 목록(디자인 기준 4-13): 맨 위에 종류로 거르는 세그먼트(전체 · 설비 제어 · 정비 요청 + 건수), 줄마다 이름 · 아래 보조 줄(종류 · 대상 고장 유형). 화면에서 직접 더한 것만 줄 끝에 「직접 추가」
  function renderSkillList() {
    const list = $('#skillList'), control = H.skills.filter(isControl).length;
    $('#skillKinds').innerHTML = H.skills.length ? UI.tabs([['', '전체', H.skills.length], ['control', UI.t('skill.kind.control'), control], ['work', UI.t('skill.kind.workOrder'), H.skills.length - control]], H.skillKind, 'data-skill-kind') : '';
    if (!H.skills.length) { list.innerHTML = UI.emptyGo('조치 방법이 아직 없습니다', '문서를 올려 적재하거나 [새 조치 방법]으로 더하면 생깁니다.', 'knowledge', '문서 등록 열기'); return; }
    const shown = H.skills.filter(k => !H.skillKind || (H.skillKind === 'control') === isControl(k));
    list.innerHTML = shown.map(k => {
      const fm = (k.failureModes || []).map(f => f.name).join(', ');
      return `<button type="button" class="row" data-skill="${esc(k.id)}"${k.id === H.skillSel && !H.skillNew ? ' aria-current="true"' : ''}><span class="row-ic">${kindIcon(k)}</span><span class="row-title">${esc(k.name)}</span>` +
        `${k.source_document ? '' : UI.chipText('직접 추가')}<span class="row-meta">${esc(kindName(k))} · ${esc(fm || UI.t('skill.noFm'))}</span></button>`;      // 문서에서 온 것이 보통이라 표시하지 않는다 — 손으로 더한 것만 말한다
    }).join('') || `<div class="pane-list-note">${UI.empty('이 종류의 조치 방법이 없습니다', '위에서 「전체」를 고르면 모두 보입니다.')}</div>`;
  }
  $('#skillKinds').addEventListener('click', ev => { const b = ev.target.closest('[data-skill-kind]'); if (!b) return; H.skillKind = b.dataset.skillKind; renderSkillList(); });
  $('#skillList').addEventListener('click', ev => {
    const row = ev.target.closest('[data-skill]'); if (!row) return;
    H.skillSel = row.dataset.skill; H.skillNew = false; renderSkillList(); renderSkillDetail(); UI.revealDetail($('#skillDetail'));
  });
  function renderSkillDetail() {
    const box = $('#skillDetail'); const c = H.catalog || { roles: [], failureModes: [] };
    const key = H.skillNew ? '__new__' : H.skillSel;
    if (box.dataset.key === key && box.querySelector('[data-skill-body]')) return;
    box.dataset.key = key || '';
    const k = H.skillNew ? { id: '', name: '', description: '', sopId: '', steps: [], failureModes: [], actions: [], rules: [], affects: [], causes: [], performers: [] }
      : H.skills.find(x => x.id === H.skillSel);
    if (!k) { box.innerHTML = `<div class="pane-none">${UI.empty(UI.t('skill.select'), '왼쪽 목록에서 고르면 절차와 대상 고장 유형이 보입니다.')}</div>`; return; }
    const sel = (id, items, cur, blank) => `<select id="${id}"><option value="">${esc(blank)}</option>${items.map(x => `<option value="${esc(x.id)}" ${cur === x.id ? 'selected' : ''}>${esc(x.name)}</option>`).join('')}</select>`;
    const fromDoc = !H.skillNew && !!k.source_document;
    const catalogAlert = H.catalogError && !fromDoc ? `<div class="alert" data-variant="destructive" role="alert">${icon('circle-alert')}<h2>승인 역할 · 고장 유형 목록을 읽지 못했습니다</h2><section>고를 칸이 비어 있습니다 — ${esc(H.catalogError)}. [${esc(UI.t('btn.cancel'))}]를 누르면 다시 읽습니다.</section></div>` : '';
    // 고치는 폼(같은 판 안의 fieldset): 새로 만들 때는 판의 본문이고, 손으로 더한 것을 고칠 때는 [고치기] 접기 안이다. 문서에서 온 것에는 폼이 없다
    const form = fromDoc ? '' : catalogAlert +
      UI.section(H.skillNew ? UI.t('method') : '',
        UI.field({ label: UI.t('skill.name'), required: true, input: `<input id="skName" value="${esc(k.name)}" maxlength="80">` }) +
        UI.field({ label: UI.t('skill.approver'), required: true, input: sel('skRole', c.roles || [], (k.approver || {}).id || '', '승인 역할 선택') }) +
        UI.field({ label: UI.t('skill.desc'), cls: 'wide', input: `<textarea id="skDesc" rows="2">${esc(k.description || '')}</textarea>` })) +
      (H.skillNew ? UI.section('대상과 종류',
        UI.field({ label: UI.t('skill.sop'), required: true, input: `<input id="skSop" placeholder="SOP-FAN-05" maxlength="40">` }) +
        UI.field({ label: UI.t('skill.fm'), required: true, input: sel('skFm', c.failureModes || [], '', '고장 유형 선택') }) +
        UI.field({ label: UI.t('skill.relation'), input: `<select id="skRel"><option value="REMEDIED_BY">${esc(UI.t('skill.rel.remedy'))}</option><option value="MITIGATED_BY">${esc(UI.t('skill.rel.mitigate'))}</option><option value="PREVENTED_BY">${esc(UI.t('skill.rel.prevent'))}</option></select>` }) +
        // 종류: 화면에서 만드는 조치 방법은 정비 요청뿐이다 — 설비에 명령을 내리는 조치(설비 제어)는 서버가 늘 거절하므로 고르는 칸에 두지 않는다
        UI.field({ label: UI.t('skill.kind'), hint: '설비에 명령을 내리는 조치는 기본 제공 조치 방법에만 있습니다.', input: `<select id="skKind" disabled><option value="work_order">${esc(UI.t('skill.kind.workOrder'))}</option></select>` }) +
        UI.field({ label: UI.t('skill.steps'), required: true, cls: 'wide', input: `<textarea id="skSteps" rows="5" placeholder="현장 제어로 전환하고 잠근다.&#10;벨트를 교체한다.&#10;재가동 후 진동 0.9 mm/s 미만을 확인한다."></textarea>` })) : '') +
      UI.formFoot(UI.btn(H.skillNew ? 'add' : 'save', { attrs: 'id="skSave"' }), { cancelAttrs: 'id="skReload"', msgAttrs: 'id="skMsg"' });
    if (H.skillNew) {
      box.innerHTML = `<header class="panel-head pane-head" data-skill-body><div class="pane-title"><h2>${esc(UI.t('skill.new'))}</h2><p>대상 고장 유형과 절차를 적어 조치 방법 하나를 지식 지도에 더합니다.</p></div></header><div class="panel-sec sk-form">${form}</div>`;
    } else {
      // 읽는 차례(디자인 기준 5-1): 머리(이름 · 종류 알약 · 한 문장 · 오른쪽 끝 더 보기) → 절차 → 대상 고장 유형 · 승인 역할 → 「연결된 지식」 접기 → 고치기(손으로 더한 것만).
      // 식별자(조치 식별자 · 절차 번호)는 더 보기 메뉴에서 복사한다 — 첫 화면에 내부 번호를 펼치지 않는다
      const RULE = { EXCLUDE: UI.t('chip.excluded'), SELECT: '후보', PENALTY: UI.t('card.penalty'), WARN: UI.t('card.warn') };
      const kv = rows => `<dl class="kv">${rows.map(([n, v]) => `<dt>${esc(n)}</dt><dd>${v}</dd>`).join('')}</dl>`;
      const first = [
        [UI.t('skill.fm'), (k.failureModes || []).map(f => `${esc(f.name)} <span class="muted">(${esc(REL_KO[f.relation] || f.relation)})</span>`).join('<br>') || esc(UI.t('skill.none'))],
        [UI.t('skill.approver'), esc((k.approver || {}).name || '')]].filter(([, v]) => v);
      const linked = [
        [UI.t('skill.causes'), (k.causes || []).map(x => esc(x.name)).join(', ') || esc(UI.t('skill.allCauses'))],
        [UI.t('skill.actions'), (k.actions || []).map(a => `${esc(hydCards.actionLabel(a))} <span class="muted">${esc(a.name)}</span>`).join('<br>')],
        [UI.t('skill.rules'), (k.rules || []).map(r => `${esc(RULE[r.effect] || r.effect)} — ${esc(UI.ruleLabel(r))}`).join('<br>')],
        [UI.t('skill.affects'), (k.affects || []).map(a => `${esc(a.name)} ${a.sign > 0 ? '↑' : '↓'}`).join(', ')],
        // 출처: 문서에서 온 것은 그 문서를 개정해 고친다(더 보기 › 문서 등록에서 고치기), 손으로 더한 것은 그 사실
        ['출처', fromDoc ? '문서 등록에서 적재한 문서입니다. 이름 · 승인 역할 · 절차는 그 문서를 개정해 고칩니다.' : '이 화면에서 직접 추가']].filter(([, v]) => v);
      const steps = k.steps || [];
      // 더 보기: 문서에서 온 것은 그 문서로 가는 길, 식별자 복사, 지우기(화면에서 직접 더한 것만 — 문서에서 온 것은 그 문서를 되돌리면 함께 지워진다: 서버 skill_graph.remove)
      const menu = UI.moreMenu('skillMore', [
        fromDoc && { label: '문서 등록에서 고치기', icon: 'file-text', attrs: 'id="skSource"' },
        { label: '조치 식별자 복사', icon: 'copy', attrs: `data-id-copy="${esc(k.id)}"` },
        k.sopId && { label: `절차 번호 복사 (${k.sopId})`, icon: 'copy', attrs: `data-id-copy="${esc(k.sopId)}"` },
        !fromDoc && { act: 'remove', attrs: 'id="skDelete"' }]);
      box.innerHTML = `<header class="panel-head pane-head" data-skill-body><div class="pane-title"><h2>${esc(k.name)}${UI.chipText(kindName(k))}${fromDoc ? '' : UI.chipText('직접 추가')}</h2>` +
        `<p>${esc(k.description || (k.sopId ? '절차 번호 ' + k.sopId : ''))}</p></div><div class="pane-acts">${menu}</div></header><div id="skAlert"></div>` +
        `<div class="panel-sec"><h3>${esc(UI.t('skill.stepsTitle'))}<span class="muted num">${steps.length ? '단계 ' + steps.length : ''}</span></h3>` +
          (steps.length ? `<ol class="sk-steps">${steps.map(s => `<li>${esc(s.text)}${s.manual ? ` <span class="muted sk-ref">${esc(s.manual)}</span>` : ''}</li>`).join('')}</ol>` : `<p class="muted">${esc(UI.t('skill.noSteps'))}</p>`) + `</div>` +
        `<div class="panel-sec">${kv(first)}</div>` +
        `<div class="panel-sec pane-fold">${UI.fold(`${esc(UI.t('skill.linked'))}<span class="muted num">${linked.length}</span>`, kv(linked))}</div>` +
        (fromDoc ? `<span id="skMsg" class="muted sk-msg" role="status"></span>`
          : `<div class="panel-sec pane-fold"><details class="fold" data-skill-edit><summary>이름 · 승인 역할 · 설명 고치기</summary><div class="fold-body sk-form">${form}</div></details></div>`);
    }
    $('#skSource')?.addEventListener('click', async (ev) => {
      try {
        await loadManualCatalog();
        const preview = await getJ(API.process + '/api/kg/manuals/sources/' + encodeURIComponent(k.source_id) + '/preview');
        selectTab('knowledge'); showDocKind('manual'); H.preview = preview;
        selectManualDocument(preview.document_id, preview.filename); renderPreview();
        $('#manualUpload').scrollIntoView({ block: 'start' });
      } catch (e) { if (box.dataset.key === key) note($('#skMsg'), '문서를 열지 못했습니다: ' + e.message, true); }
    });
    if (fromDoc) return;
    // 지우기: 확인 → DELETE /api/kg/skills/{id}?by=. 문서의 규칙이 가리키는 조치 방법이면 서버가 409 와 까닭(먼저 되돌릴 문서)을 준다 — 그 문장을 판 위에 그대로 보인다.
    // 지워지면 이 조치 방법을 고른 판단 기록이 몇 건 남는지(decision_cases)와 함께 지운 후보 규칙 수(removed_rules)를 말한다
    $('#skDelete')?.addEventListener('click', async ev => {
      const by = manualActor();
      if (!by) { $('#skAlert').innerHTML = UI.errorBlock('지우지 못했습니다', '담당자 정보를 읽지 못했습니다. 화면을 새로 고친 뒤 다시 해 주세요.'); return; }
      if (!await UI.confirm({ title: `「${k.name}」 조치 방법을 지울까요?`, body: '지식 지도에서 이 조치 방법과 그 절차를 지웁니다. AI가 조치 후보로 더는 고르지 않습니다. 이 조치 방법을 고른 판단 기록은 남습니다.', ok: UI.acts.remove[0], danger: true })) return;
      try {
        const r = await requestJ(API.process + '/api/kg/skills/' + encodeURIComponent(k.id) + '?by=' + encodeURIComponent(by) + '&request_id=' + UI.uuid(), { method: 'DELETE' });
        clearSkillDraft(key); H.skillSel = null; box.dataset.key = '';
        UI.toast(`「${r.name || k.name}」 조치 방법을 지웠습니다.` + (r.decision_cases ? ` 이 조치 방법을 고른 판단 기록 ${r.decision_cases}건은 남습니다.` : ' 이 조치 방법을 고른 판단 기록은 없었습니다.')
          + ((r.removed_rules || []).length ? ` 이 조치 방법만 내던 후보 규칙 ${r.removed_rules.length}개도 함께 지웠습니다.` : ''), { tone: 'ok', timeout: 8000 });
        await loadSkills();
      } catch (e) {
        if (box.dataset.key === key) $('#skAlert').innerHTML = UI.errorBlock('지우지 못했습니다', e.message);
      }
    });
    const fields = [...box.querySelectorAll('.sk-form input, .sk-form textarea, .sk-form select')];
    let draft = H.skillDrafts.get(key), draftError = '';
    if (!draft) { try { draft = JSON.parse(sessionStorage.getItem(draftKey(key)) || 'null'); } catch (_) { draftError = '저장한 초안을 읽을 수 없습니다.'; } }
    if (draft && (typeof draft !== 'object' || !draft.fields || typeof draft.fields !== 'object' || Array.isArray(draft.fields))) draftError = '저장한 초안의 형식이 올바르지 않습니다.';
    if (draft || draftError) box.querySelector('[data-skill-edit]')?.setAttribute('open', '');      // 고치던 것이 있으면 펼쳐서 보인다
    if (draftError) {
      fields.forEach(n => { n.disabled = true; });
      $('#skSave').disabled = true;
      note($('#skMsg'), draftError + ` 초안은 보존되어 있습니다. [${UI.t('btn.cancel')}]를 누르면 이 초안을 버리고 서버의 저장본을 다시 읽습니다.`, true);
      $('#skReload').addEventListener('click', async () => {
        if (!await UI.confirm({ title: '읽을 수 없는 초안을 버릴까요?', body: '이 브라우저의 초안만 버립니다. 서버의 저장본은 바뀌지 않습니다.', ok: '초안 버리기', danger: true })) return;
        clearSkillDraft(key); box.dataset.key = ''; if (key === '__new__') H.skillNew = false; await loadSkills();
      });
      return;
    }
    draft = draft || { revision: k.revision, fields: {}, pending: null };
    fields.forEach(e => { if (draft.fields?.[e.id] != null) e.value = draft.fields[e.id]; });
    const remember = () => { draft.fields = Object.fromEntries(fields.map(e => [e.id, e.value])); saveSkillDraft(key, draft); note($('#skMsg'), UI.t('skill.unsaved')); };
    fields.forEach(e => { e.addEventListener('input', remember); e.addEventListener('change', remember); });
    const lockFields = () => {
      fields.forEach(e => { e.disabled = !!draft.pending; });
      $('#skSave').textContent = draft.pending ? '저장 결과 확인' : key === '__new__' ? UI.t('skill.add') : UI.t('btn.save');
      $('#skReload').disabled = !!draft.pending;
    };
    lockFields();
    if (draft.pending) note($('#skMsg'), '응답을 확인하지 못한 요청입니다. 같은 요청으로 저장 결과를 확인하세요.', true);
    else if (Object.keys(draft.fields).length) note($('#skMsg'), UI.t('skill.unsaved'));
    $('#skReload').addEventListener('click', async () => {      // 취소: 고치던 것을 버리고 저장본을 다시 읽는다. 새로 만들던 것이면 목록으로 돌아간다
      if (draft.pending) return;
      clearSkillDraft(key); box.dataset.key = ''; if (key === '__new__') H.skillNew = false; await loadSkills();
    });
    $('#skSave').addEventListener('click', async (ev) => {
      const b = ev.currentTarget;
      const body = draft.pending || { name: $('#skName').value.trim(), description: $('#skDesc').value, approver: $('#skRole').value, by: manualActor(), revision: draft.revision, request_id: UI.uuid() };
      if (!draft.pending && key === '__new__') Object.assign(body, { sopId: $('#skSop').value.trim(), failureMode: $('#skFm').value, relation: $('#skRel').value, kind: $('#skKind').value, steps: $('#skSteps').value });
      if (!body.name) { note($('#skMsg'), UI.t('skill.nameRequired'), true); $('#skName').focus(); return; }
      if (!draft.pending && !body.approver) { note($('#skMsg'), '승인 역할을 선택하세요.', true); $('#skRole').focus(); return; }
      if (!draft.pending && key === '__new__' && !body.failureMode) { note($('#skMsg'), '대상 고장 유형을 선택하세요.', true); $('#skFm').focus(); return; }
      remember(); draft.pending = body; saveSkillDraft(key, draft); lockFields();
      const end = hydLive.busy(b, '저장하는 중'); note($('#skMsg'), '');
      try {
        const r = await (key === '__new__' ? postJ(API.process + '/api/kg/skills', body)
          : postJ(API.process + '/api/kg/skills/' + encodeURIComponent(k.id), body, 'PUT')).finally(() => end(false));
        if (r.detail && !r.id) throw new Error(r.detail);
        clearSkillDraft(key);
        if (box.dataset.key === key) { H.skillSel = r.id; H.skillNew = false; box.dataset.key = ''; }
        await loadSkills(); UI.toast(UI.t('skill.saved'), { tone: 'ok' });
      } catch (e) {
        if (e.status >= 400 && e.status < 500) { draft.pending = null; saveSkillDraft(key, draft); }
        if (box.dataset.key === key) {
          lockFields(); note($('#skMsg'), '저장하지 못했습니다: ' + e.message + (draft.pending ? ' 응답을 받지 못했습니다. [저장 결과 확인]을 눌러 저장됐는지 확인하세요.' : e.status === 409 ? ` 다른 곳에서 먼저 고쳤을 수 있습니다 — [${UI.t('btn.cancel')}]로 저장본을 다시 읽은 뒤 고치세요.` : ''), true);
        }
      }
    });
  }
  $('#skillNew').addEventListener('click', () => { H.skillNew = true; renderSkillList(); renderSkillDetail(); UI.revealDetail($('#skillDetail')); $('#skName').focus({ preventScroll: true }); });

  /* ================================================= 문서 등록: 매뉴얼 → 조치 방법 */
  // 올릴 것 고르기(매뉴얼 · 업무 DB 표 정의): 한 번에 한 가지 일만 보인다
  function showDocKind(kind) {
    H.docKind = kind;
    UI.markViewTab($('#docKinds'), b => b.dataset.docKind === kind);
    document.querySelectorAll('#view-knowledge [data-doc-pane]').forEach(p => { p.hidden = p.dataset.docPane !== kind; });
  }
  $('#docKinds').addEventListener('click', ev => { const b = ev.target.closest('[data-doc-kind]'); if (b) showDocKind(b.dataset.docKind); });
  // 다른 화면의 「문서 등록 열기」가 올릴 것을 정해 부르면(data-go-doc-kind) 그 보기로 연다 — 표 · 열이 정해지지 않은 판단 입력에서 온 사람은 「업무 DB 표 정의」에 닿아야 한다
  document.addEventListener('click', ev => { const b = ev.target.closest && ev.target.closest('[data-go-doc-kind]'); if (b) showDocKind(b.dataset.goDocKind); });
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
  // "sv:ts1:-, msr:maint-cost:+" → [{target, sign}] (A079: reviewed impact of an ingested SOP)
  const parseAffects = text => (text || '').split(',').map(s => s.trim()).filter(Boolean).map(s => { const m = s.match(/^(.*?):([+-])$/); return m ? { target: m[1].trim(), sign: m[2] } : { target: s, sign: '?' }; });
  /* 적재 요청 하나를 만든다 — 검토 화면의 [검토한 내용 적재]와 「한 번에 적재」가 같은 함수로 만든다(두 길이 서버에 다른 것을 보내지 않게).
     read(p) = 그 절차의 칸 값 { id, name, steps: Map(순서 → 글), fm, rel, kind, affects(글), scope, executable('true' | 'false' | ''), parts[], approver, policy, refExecutable, refTarget, refPin }.
     검토 화면은 고칠 칸에서 읽고(사람이 고친 값), 한 번에 적재는 손대지 않은 칸의 값(untouched — AI 제안 그대로)을 준다. dropped = 적재에서 뺄 지식 후보 [[묶음, id] …].
     → { request } 또는 { stop: 멈춘 까닭, at: 'proc:<절차 id>'(그 절차의 칸을 보여 줄 자리) } */
  function commitRequest(r, read, dropped, by) {
    const links = {}, vals = new Map();
    for (const p of r.procedures) {
      const v = read(p), sug = manualLink(r, p), at = 'proc:' + p.id;
      vals.set(p.id, v);
      let link = { ...sug, failureMode: v.fm || null, relation: v.rel || null, kind: v.kind, affects: parseAffects(v.affects) };
      if (link.kind === 'reference') {
        if (v.refExecutable !== 'false') return { stop: `${p.name}: 일반 원문 참고 보관을 명시적으로 선택하세요.`, at };
        link = { kind: 'reference', executable: false, failureMode: null, relation: null, approver: null };
      } else if (v.scope === 'purchase') {
        if (!H.manualCatalog) return { stop: H.manualCatalogError || '구매 부품 · 담당 역할 목록을 먼저 확인하세요.', at };
        if (!['true', 'false'].includes(v.executable)) return { stop: `${p.name}: 원문 참고 보관 또는 실행 후보 검토를 명시적으로 선택하세요.`, at };
        Object.assign(link, { scope: 'purchase', executable: v.executable === 'true', parts: v.parts, approver: v.approver || null });
        if (!link.parts.length) return { stop: `${p.name}: 원문에 명시한 구매 대상 부품을 선택하세요.`, at };
        if (link.executable && !link.approver) return { stop: `${p.name}: 원문에 명시한 구매 승인 담당 역할을 선택하세요.`, at };
        if (v.policy && !['oem', 'lowest_approved', 'fastest_quote'].includes(v.policy)) return { stop: `${p.name}: 원문 공급사 선정 기준을 확인하세요.`, at };
        if (!link.executable && v.policy) return { stop: `${p.name}: 원문 참고 보관에는 공급사 선정 기준을 지정하지 않습니다. 기준을 「지정하지 않음」으로 바꾸세요.`, at };
        if (v.policy) { link.supplier_policy = v.policy; link.actions = (link.actions || []).map(a => ({ ...a, value: null })); }
        else delete link.supplier_policy;
        if (!link.executable) link.actions = []; // The explicit reference choice makes no ERP request; original actions stay in the source snapshot.
      } else if (v.scope === 'fault') { delete link.scope; if (sug.scope === 'purchase') { delete link.parts; delete link.executable; } }
      else return { stop: `${p.name}: 절차의 업무 범위를 확인하세요.`, at };
      links[p.id] = link;
    }
    const missing = Object.entries(links).filter(([, v]) => v.kind !== 'reference' && v.scope !== 'purchase' && !v.failureMode).map(([k]) => k);
    if (missing.length) return { stop: `고장 유형을 고르세요: ${missing.join(', ')} — 고장 조치가 아닌 확인 · 참고 절차면 종류를 「일반 원문 참고 절차」로 바꾸세요`, at: 'proc:' + missing[0] };
    const reviewed = structuredClone(r);
    dropped.forEach(([group, id]) => { if (reviewed.knowledge && Array.isArray(reviewed.knowledge[group])) reviewed.knowledge[group] = reviewed.knowledge[group].filter(x => x.id !== id); });
    for (const p of reviewed.procedures) { const v = vals.get(p.id); p.name = v.name; p.steps.forEach(s => { if (v.steps.has(s.order)) s.text = v.steps.get(s.order); }); }
    for (const p of reviewed.procedures) {
      const v = vals.get(p.id);
      if (links[p.id].kind !== 'reference') continue;
      if (v.refTarget) {
        const target = H.manualCatalog?.skills?.find(x => x.id === v.refTarget)?.reference_contract;
        if (!target || target.id !== v.refTarget || !/^[a-f0-9]{64}$/.test(v.refPin) || v.refPin !== target.contract_sha256 || v.id.trim() !== target.sopId || JSON.stringify(p.steps.map(s => ({ order: s.order, text: s.text }))) !== JSON.stringify(target.steps))
          return { stop: `${p.name}: 원문 번호나 단계가 연결할 등록 절차와 다릅니다. 대조 내용을 다시 확인하세요.`, at: 'proc:' + p.id };
        p.existing_skill_id = v.refTarget; p.reference_contract_sha256 = v.refPin;
      } else { delete p.existing_skill_id; delete p.reference_contract_sha256; }
    }
    const reviewedLinks = {};
    for (const p of reviewed.procedures) { const old = p.id; p.id = vals.get(old).id.trim(); reviewedLinks[p.id] = links[old]; }
    return { request: { ...reviewed, links: reviewedLinks, by, reviewed: true } };
  }
  // 이 문서의 고장 유형 선택지: 이미 있는 것 + 이 문서에서 새로 나온 것
  const failureModesOf = r => { const known = (H.catalog || {}).failureModes || [];
    return known.concat(((r.knowledge || {}).failure_modes || []).filter(f => f && f.id && !known.some(k => k.id === f.id)).map(f => ({ id: f.id, name: `${f.name || f.id} (이 문서에서 새로)` }))); };
  // 검토 화면의 칸을 하나도 손대지 않았을 때 그 칸들이 갖는 값(= AI 제안 그대로). 「한 번에 적재」가 쓴다 — 검토 화면(renderPreview)의 처음 값과 같아야 한다(시험이 두 길의 적재 요청을 견준다)
  const untouched = r => p => {
    const l = manualLink(r, p), purchase = l.scope === 'purchase', rel = l.relation || (purchase ? '' : 'REMEDIED_BY'), kind = ['control', 'reference'].includes(l.kind) ? l.kind : 'work_order';
    return { id: p.id, name: p.name, steps: new Map(p.steps.map(s => [s.order, s.text])),
      fm: failureModesOf(r).some(f => f.id === l.failureMode) ? l.failureMode : '', rel: kind === 'reference' ? '' : ['REMEDIED_BY', 'MITIGATED_BY', 'PREVENTED_BY'].includes(rel) ? rel : '', kind,
      affects: (l.affects || []).map(a => a.target + ':' + a.sign).join(', '), scope: l.scope || 'fault', executable: l.executable === true ? 'true' : l.executable === false ? 'false' : '',
      parts: Array.isArray(l.parts) ? l.parts : l.parts ? [l.parts] : [], approver: l.approver || '', policy: l.supplier_policy == null ? '' : String(l.supplier_policy),
      refExecutable: l.executable === false ? 'false' : '', refTarget: p.existing_skill_id || l.existing_skill_id || '', refPin: p.reference_contract_sha256 || l.reference_contract_sha256 || '' };
  };
  // 고장 조치인데 고장 유형이 정해지지 않은 절차(검토 화면의 「검토 필요」 줄)
  const needsLink = (r, p) => { const l = manualLink(r, p); return l.kind !== 'reference' && l.scope !== 'purchase' && !l.failureMode; };

  /* ---- 옆 판(#docSheet — 디자인 기준 4-19): 첫 화면에는 「적재한 문서」 목록만 두고 자세한 것은 이 판으로 연다.
     doc(적재한 문서 한 편: 이 문서로 답할 수 있는 질문) · sources(보관한 원문 — 올린 문서는 적재하지 않아도 원문이 남는다. 다시 열어 AI 추출 · 검토를 이어 간다) · history(등록 이력) */
  const docFacts = u => `${UI.t('kn.sections')} ${u.sections} · ${UI.t('kn.procedures')} ${u.procedures} · ${UI.t('kn.steps')} ${u.steps}`;
  const originalUrl = sid => `${API.process}/api/kg/manuals/sources/${encodeURIComponent(sid)}/original`;
  const sheetShell = (title, sub, body) => `<header class="sheet-head"><div><h2>${esc(title)}</h2>${sub ? `<p class="muted">${esc(sub)}</p>` : ''}</div>` +
    `<button type="button" class="btn" data-variant="ghost" data-size="icon" data-doc-sheet-close aria-label="닫기" data-tooltip="닫기" data-side="left">${icon('x')}</button></header><div class="sheet-body" data-doc-sheet-body>${body}</div>`;
  function openSheet(kind, arg) {
    H.sheet = { kind, arg, offset: 0 };
    const d = $('#docSheet'); if (!d.open) d.showModal();
    drawSheet();
  }
  function closeSheet() { const d = $('#docSheet'); H.sheet = null; if (d.open) d.close(); d.innerHTML = ''; }
  async function drawSheet() {
    const d = $('#docSheet'), s = H.sheet; if (!s) return;
    const body = html => { const b = d.querySelector('[data-doc-sheet-body]'); if (b && H.sheet === s) b.innerHTML = html; return b; };
    if (s.kind === 'doc') {
      const u = H.uploads.find(x => x.batch === s.arg);
      if (!u) { closeSheet(); return; }
      d.setAttribute('aria-label', u.filename);
      d.innerHTML = sheetShell(u.filename, `${docFacts(u)} · ${UI.dateTime(u.t)}${u.by ? ' · ' + u.by : ''}`, `<div data-golden="${esc(u.batch)}">${goldenSection(u.batch)}</div>`);
      wireGolden(d); hydCourseAccess.apply(d);
      fetchGolden(u.batch).then(() => renderGolden(u.batch));
      return;
    }
    if (s.kind === 'history') {
      d.setAttribute('aria-label', UI.t('kn.history'));
      const version = u => u.status === 'ROLLED_BACK' ? UI.t('kn.rolledBack') : u.current ? UI.t('kn.current') : UI.t('kn.previous');
      d.innerHTML = sheetShell(UI.t('kn.history'), '되돌리기는 최신 판본부터 진행합니다. 보관한 원문은 지우지 않습니다.', table('<th>문서</th><th>넣은 내용</th><th>담당자</th><th>등록 시각</th><th>판본</th><th></th>',
        H.uploads.map(u => `<tr><td><a href="${originalUrl(u.source_id)}" title="보관한 원본 내려받기">${esc(u.filename)}</a></td><td>${esc(docFacts(u))}</td><td>${esc(u.by)}</td><td>${esc(UI.dateTime(u.t))}</td><td>${esc(version(u))}</td>` +
          `<td class="doc-acts">${u.current && u.status === 'ACTIVE' ? `<button type="button" class="btn" data-variant="destructive" data-size="sm" data-manual-undo="${esc(u.batch)}">${esc(UI.t('kn.undo'))}</button>` : ''}</td></tr>`).join('')));
      return;
    }
    d.setAttribute('aria-label', '보관한 원문');
    d.innerHTML = sheetShell('보관한 원문', '올린 문서의 원문은 적재하지 않아도 남아 있습니다. 다시 열면 AI 추출과 검토를 이어 갑니다.', UI.loading(''));
    try {
      const page = await getJ(API.process + '/api/kg/manuals/sources?offset=' + s.offset);
      if (H.sheet !== s) return;
      const rows = page.items.map(x => `<tr><td><a href="${originalUrl(x.source_id)}" title="보관한 원본 내려받기">${esc(x.filename)}</a></td><td>${esc(UI.dateTime(x.created_at))}</td>` +
        `<td>${x.status === 'READY' ? '글자를 읽음' : UI.chipText('쪽 · 글자 인식 확인 필요', 'warning')}</td><td class="doc-acts"><button type="button" class="btn" data-variant="outline" data-size="sm" data-manual-reopen="${esc(x.source_id)}">다시 열기</button></td></tr>`).join('');
      body((page.total ? table('<th>문서</th><th>올린 시각</th><th>읽은 상태</th><th></th>', rows) : UI.empty('보관한 원문이 아직 없습니다', '문서를 올리면 여기에 남습니다.')) +
        `<footer class="form-foot"><span id="manualSourcesMsg" class="muted" role="status">${page.total ? `${s.offset + 1}–${s.offset + page.items.length} / ${page.total}` : ''}</span>` +
        `${s.offset ? `<button type="button" class="btn" data-variant="outline" data-size="sm" data-sources-go="${Math.max(0, s.offset - page.limit)}">이전</button>` : ''}${page.next_offset !== null ? `<button type="button" class="btn" data-variant="outline" data-size="sm" data-sources-go="${page.next_offset}">다음</button>` : ''}</footer>`);
    } catch (e) { body(UI.errorBlock('보관한 원문 목록을 읽지 못했습니다', e.message, { retry: true })); }
  }
  // 개정할 문서를 골라 「내 파일 올리기」로 보낸다(적재한 문서의 더 보기 › 이 문서 개정 · 이미 적재한 원문의 [이 문서 개정])
  function reviseDoc(documentId, filename) {
    closeSheet();
    selectManualDocument(documentId, filename);
    H.preview = null; H.commit = null; renderPreview(); showPick($('#manualPick'), 'file');
    note($('#manualStatus'), '개정할 문서를 골랐습니다. 새 판본 파일을 고르고 [문서 올리기]를 누르세요.');
    $('#manualUpload').scrollIntoView({ block: 'start' });
  }
  // 판본 되돌리기: 확인 → POST …/rollback. 결과는 「적재한 문서」 아래 한 줄에 남는다.
  // 서버(manual_graph.rollback)가 하는 일: 최신 판본이 넣은 것을 지식 지도에서 빼고 그 판본을 적재하기 전 상태로 돌린다 — 이전 판본이 있으면 그 판본의 내용이 다시 선다(응답 restored_batch).
  // 메뉴 · 확인 창 · 결과 줄이 모두 그 일을 「되돌리기」 한 이름으로 부른다(메뉴는 「이 판본 되돌리기」인데 확인 창은 「등록 취소」였다)
  async function undoBatch(batch) {
    if (!await UI.confirm({ title: '이 판본을 되돌릴까요?', body: '이 판본이 넣은 절 · 조치 방법 · 규칙 연결이 지식 지도에서 빠집니다. 이전 판본이 있으면 그 판본의 내용으로 돌아갑니다. 보관한 원문은 남습니다.', ok: '되돌리기', danger: true })) return;
    closeSheet();
    note($('#manualHistoryMsg'), '판본을 되돌리는 중입니다.');
    try {
      const out = await postJ(API.process + '/api/kg/manuals/batches/' + encodeURIComponent(batch) + '/rollback', { by: manualActor() });
      H.preview = null; H.commit = null; renderPreview(); H.skills = [];
      await loadUploads(); if (window.hydEnt) hydEnt.loadGraph(true);
      note($('#manualHistoryMsg'), out && out.restored_batch ? '판본을 되돌렸습니다. 지식 지도가 이전 판본의 내용으로 돌아갔습니다.' : '판본을 되돌렸습니다. 이 판본이 넣은 내용이 지식 지도에서 빠졌습니다.');
    } catch (e) { note($('#manualHistoryMsg'), '판본을 되돌리지 못했습니다: ' + e.message, true); }
  }
  $('#docSheet').addEventListener('close', () => { H.sheet = null; });
  $('#docSheet').addEventListener('click', async ev => {
    const d = ev.currentTarget, t = sel => ev.target.closest(sel);
    if (ev.target === d || t('[data-doc-sheet-close]')) { closeSheet(); return; }
    if (t('[data-retry]')) { drawSheet(); return; }
    const go = t('[data-sources-go]'); if (go) { H.sheet.offset = Number(go.dataset.sourcesGo); drawSheet(); return; }
    const undo = t('[data-manual-undo]'); if (undo) { undoBatch(undo.dataset.manualUndo); return; }
    const b = t('[data-manual-reopen]'); if (!b) return;
    const end = hydLive.busy(b, '여는 중');
    try {
      if (!H.catalog) H.catalog = await getJ(API.process + '/api/kg/catalog');
      await loadManualCatalog();
      const preview = await getJ(API.process + '/api/kg/manuals/sources/' + encodeURIComponent(b.dataset.manualReopen) + '/preview');
      closeSheet();
      H.preview = preview; selectManualDocument(preview.document_id, preview.filename); renderPreview();
      $('#manualUpload').scrollIntoView({ block: 'start' });
    } catch (e) { end(false); note($('#manualSourcesMsg'), '원문을 다시 읽지 못했습니다: ' + e.message, true); }
  });
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
    return `<div class="doc-q-form" data-golden-form="${esc(batch)}">` +
      UI.field({ label: UI.t('golden.questions'), required: true, hint: UI.t('golden.questionsHint'), error: g.msg || '', input: `<textarea rows="3" data-golden-q aria-label="${esc(UI.t('golden.questions'))}" ${dis}>${esc(g.draft || '')}</textarea>` }) +
      `<footer class="form-foot"><button type="button" class="btn" data-variant="outline" data-golden-ask ${dis}${hydCourseAccess.attrs('documents.golden')}>${esc(g.busy ? UI.t('golden.asking') : UI.t('golden.ask'))}</button></footer></div>`;
  }
  // 질문 한 건: 질문 + 판정 뱃지 하나 → 답 한 단락 → 「근거」 접기(확신도 · 인용한 지식 · 질의 · 근거를 확인하지 못한 답)
  function goldenItems(r) {
    const items = (r.report && r.report.items) || [];
    const head = `<p class="doc-q-sum">${esc(UI.t('golden.answerable'))} <b class="num">${r.answerable || 0}</b> · ${esc(UI.t('golden.partial'))} <b class="num">${r.partially_answerable || 0}</b> · ${esc(UI.t('golden.notYet'))} <b class="num">${r.not_yet_answerable || 0}</b> · ${esc(UI.t('golden.grounded'))} <b class="num">${r.grounded || 0}</b></p>` +
      (r.report && r.report.summary ? `<p class="muted">${esc(r.report.summary)}</p>` : '');
    return head + items.map(it => {
      const [key, tone] = ITEM_STATUS[it.status] || ['golden.notYet', 'neutral'];
      const cited = it.cited || [];
      const more = `<dl class="kv">${it.confidence ? `<dt>${esc(UI.t('golden.confidence'))}</dt><dd>${esc(UI.t('golden.conf.' + it.confidence))}</dd>` : ''}` +
        `<dt>${esc(UI.t('golden.cited'))}</dt><dd>${cited.length ? cited.map(c => UI.name(c) !== c ? `<span title="${esc(c)}">${esc(UI.name(c))}</span>` : `<code class="inline">${esc(c)}</code>`).join(' · ') : esc(UI.t('golden.noCited'))}</dd>` +
        (it.claimed_answer ? `<dt>근거를 확인하지 못한 에이전트의 답</dt><dd>${esc(it.claimed_answer)}</dd>` : '') + `</dl>` +
        (it.cypher ? UI.raw(it.cypher, { title: UI.t('golden.query'), lang: 'cypher' }) : '');
      return `<article class="doc-q"><h4>${esc(it.question)}${UI.chipText(UI.t(key), tone)}</h4><p class="doc-q-answer">${esc(it.answer || '')}</p>${UI.fold(`${esc(UI.t('golden.evidence'))}<span class="muted num">${cited.length}건</span>`, more)}</article>`;
    }).join('');
  }
  // 적재한 문서의 줄을 눌러 연 옆 판(#docSheet) 안에 그린다
  function goldenSection(batch) {
    const g = H.golden[batch] || {}; const r = g.report;
    let body;
    if (g.error) body = UI.errorBlock(UI.t('golden.err.load'), g.error) + goldenForm(batch, g);
    else if (r === undefined) body = UI.loading('');
    else if (r === null || r.status === 'CANCELLED' || r.status === 'FAILED') body = `<p class="muted">이 문서를 읽은 뒤 답할 수 있어야 하는 질문을 적어, 넣은 지식만으로 답이 되는지 확인합니다.</p>` + goldenForm(batch, g);
    else if (!goldenFinal(r)) body = (r.workitem ? '<div data-golden-live></div>' : hydLive.waitHtml(UI.t('golden.checking', { n: r.questions }), { since: g.since })) + `<p class="muted">${esc(UI.t('golden.checkingSub'))}</p>`;
    else body = goldenItems(r) + `<h4 class="doc-q-more">${esc(UI.t('golden.askMore'))}</h4>${goldenForm(batch, g)}`;
    return `<h3 class="doc-q-title">${esc(UI.t('golden.title'))}${goldenStatusChip(r)}</h3>` + body;
  }
  function renderGolden(batch) {
    const box = $('#docSheet').querySelector(`[data-golden="${CSS.escape(batch)}"]`); if (!box) return;
    box.innerHTML = goldenSection(batch); wireGolden(box); hydCourseAccess.apply(box);   // 꺼진 까닭을 단추 옆 한 줄로(W3-07)
    goldenLive(batch, box);
  }
  // 질문을 확인하는 AI 단계(처리 건의 작업 행 r.workitem)의 실행 기록을 그 자리에서 흘려보낸다. 기록 칸은 다시 그려도 같은 것을 옮겨 쓴다
  function goldenLive(batch, box) {
    const g = H.golden[batch] || {}, r = g.report, slot = box.querySelector('[data-golden-live]');
    if (!r || goldenFinal(r) || !r.workitem) { if (g.work) { g.work.stop(); g.work = null; g.host = null; } return; }
    if (!slot) return;
    if (!g.work || g.workId !== r.workitem) {
      if (g.work) g.work.stop();
      g.host = document.createElement('div'); g.workId = r.workitem;
      g.work = hydLive.agentWork(g.host, { tab: 'knowledge', onChange: async () => { if (await fetchGolden(batch)) renderGolden(batch); } });
    }
    slot.replaceChildren(g.host);
    g.work.set({ items: [{ id: r.workitem, instance: r.instance, state: 'run' }], running: true, since: g.since || null, headline: UI.t('golden.checking', { n: r.questions }),
      note: r.corrections ? UI.t('golden.corrections', { n: r.corrections.attempts }) : '' });
  }
  function wireGolden(root) {
    root.querySelectorAll('[data-golden-ask]').forEach(b => b.addEventListener('click', async () => {
      const form = b.closest('[data-golden-form]'); const batch = form.dataset.goldenForm; const g = H.golden[batch] = H.golden[batch] || {};
      g.draft = form.querySelector('[data-golden-q]').value; g.by = manualActor();      // 누가 = 이 PC의 담당자(자유 글 칸 없음)
      const questions = [...new Set(g.draft.split('\n').map(s => s.trim()).filter(Boolean))];
      if (!questions.length) { g.msg = UI.t('golden.err.empty'); renderGolden(batch); return; }
      if (questions.length > 20) { g.msg = UI.t('golden.err.many'); renderGolden(batch); return; }
      g.busy = true; g.msg = ''; renderGolden(batch);
      try { await postJ(goldenUrl(batch, 'questions'), { questions, by: g.by, request_id: UI.uuid() }); g.draft = ''; g.since = new Date().toISOString(); await fetchGolden(batch); }
      catch (e) { g.msg = e.message; }
      finally { g.busy = false; renderGolden(batch); }
    }));
  }
  setInterval(async () => {                      // 작업 행 정보가 없는 확인 중 배치만 2초마다 다시 읽는다 — 작업 행이 있으면 실시간 기록(goldenLive)이 결과를 부른다
    if (state.tab !== 'knowledge') return;
    for (const [batch, g] of Object.entries(H.golden)) {
      if (!g.report || goldenFinal(g.report) || g.polling || g.work) continue;
      g.polling = true;
      try { if (await fetchGolden(batch)) renderGolden(batch); } finally { g.polling = false; }
    }
  }, 2000);

  /* 적재한 문서(디자인 기준 5-3): 줄마다 이름 · 넣은 내용(절 · 조치 방법 · 단계)과 적재 시각 · 더 보기(이 문서 개정 · 보관한 원본 내려받기 · 이 판본 되돌리기).
     줄을 누르면 옆 판에 「이 문서로 답할 수 있는 질문」이 열린다. 「적재됨」 상태는 위의 제공 문서 목록 한 곳에만 있다 — 이 목록의 줄은 모두 지금 적재된 판이라 되돌려진 판일 때만 표시를 단다.
     보관한 원문 · 등록 이력은 구역 머리의 더 보기로 연다(옆 판) */
  async function loadUploads() {
    const history = $('#manualHistory');
    try {
      const [ups, src] = await Promise.all([getJ(API.process + '/api/kg/manuals'), getJ(API.process + '/api/kg/manuals/sources?limit=1').catch(() => null)]);      // 보관한 원문 수는 메뉴 글에만 쓴다 — 못 읽으면 수 없이 두고, 까닭은 그 판을 열 때 보인다
      H.uploads = ups;
      updateManualDocuments(ups);
      const current = ups.filter(u => u.current);
      const row = (u, i) => `<div class="row-act"><button type="button" class="row" data-doc-open="${esc(u.batch)}" aria-haspopup="dialog"><span class="row-ic">${icon('file-text')}</span><span class="row-title">${esc(u.filename)}</span>` +
        `${u.status === 'ROLLED_BACK' ? UI.chipText(UI.t('kn.rolledBack')) : ''}<span class="row-meta">${esc(docFacts(u))} · ${esc(UI.dateTime(u.t))}</span></button>` +
        UI.moreMenu('docMore' + i, [{ label: UI.t('kn.revise'), icon: 'pencil', attrs: `data-manual-revise="${esc(u.document_id)}"` },
          { label: '보관한 원본 내려받기', icon: 'download', attrs: `data-doc-original="${esc(u.source_id)}"` },
          u.status === 'ACTIVE' && { label: UI.t('kn.undo'), icon: 'rotate-ccw', attrs: `data-manual-undo="${esc(u.batch)}"` }]) + `</div>`;
      const tools = UI.moreMenu('docListMore', [{ label: `보관한 원문${src && src.total != null ? ` ${src.total}건` : ''}`, icon: 'folder', attrs: 'data-doc-sheet="sources"' },
        ups.length && { label: `${UI.t('kn.history')} ${ups.length}건`, icon: 'history', attrs: 'data-doc-sheet="history"' }]);
      history.innerHTML = `<div class="sec-head"><h2>적재한 문서</h2><span class="doc-sec-tools"><span class="muted num">${current.length ? current.length + '건' : ''}</span>${tools}</span></div>` +
        (current.length ? `<div class="rows doc-loaded" aria-label="적재한 문서">${current.map(row).join('')}</div>` : UI.empty('아직 적재한 문서가 없습니다', '위에서 문서를 골라 AI 추출 결과를 검토해 적재하면 여기에 생깁니다.')) +
        '<p class="muted" id="manualHistoryMsg" role="status"></p>';
      if (H.sheet && H.sheet.kind !== 'sources') drawSheet();
    } catch (e) {
      history.innerHTML = UI.errorBlock('적재한 문서 목록을 읽지 못했습니다', e.message, { retry: true });
    }
  }
  $('#manualHistory').addEventListener('click', ev => {
    const t = sel => ev.target.closest(sel);
    if (t('[data-retry]')) { loadUploads(); return; }
    const rev = t('[data-manual-revise]'); if (rev) { reviseDoc(rev.dataset.manualRevise); return; }
    const undo = t('[data-manual-undo]'); if (undo) { undoBatch(undo.dataset.manualUndo); return; }
    const org = t('[data-doc-original]'); if (org) { Object.assign(document.createElement('a'), { href: originalUrl(org.dataset.docOriginal), download: '' }).click(); return; }
    const sheet = t('[data-doc-sheet]'); if (sheet) { openSheet(sheet.dataset.docSheet); return; }
    const open = t('[data-doc-open]'); if (open) openSheet('doc', open.dataset.docOpen);
  });
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
  // 자동 검증의 결론: { tone('ok' | 'warn' | 'danger'), tag(뱃지 글), line(한 문장), more(그 아래의 목록과 접기) }
  function manualValidation(v, preview, catalog) {
    if (!v) return { tone: 'warn', tag: '자동 검증 없음', line: '자동 검증 결과가 없습니다. 원문과 직접 대조해 검토하세요.', more: '' };
    if (v.checked !== true || typeof v.technical_ready !== 'boolean' || v.needs_human_review !== true || v.can_commit !== false || !Array.isArray(v.issues))
      return { tone: 'danger', tag: '검증 결과 읽기 실패', line: '자동 검증 응답 형식이 올바르지 않습니다. 원문과 직접 대조해 검토하세요.', more: '' };
    const issues = v.issues;
    const values = (v.source_value_warnings || []).filter(w => !(preview.warnings || []).includes(w));
    const more = (issues.length ? `<ul class="doc-issues">${issues.map(x => `<li>${esc(manualIssueMessage(x, preview, catalog))}</li>`).join('')}</ul>` : '') +
      (values.length ? UI.fold(`원문 수치 확인 필요<span class="muted num">${values.length}개</span>`, `<ul class="doc-issues">${values.map(w => `<li>${esc(w)}</li>`).join('')}</ul>`, { open: true }) : '') +
      (Array.isArray(v.notices) && v.notices.length ? UI.fold(`참고<span class="muted">고칠 곳이 아니라 알고 넘어갈 것 · ${v.notices.length}건</span>`, `<ul class="doc-issues">${v.notices.map(n => `<li>${esc(n.message)}</li>`).join('')}</ul>`) : '') +
      (issues.length ? UI.raw(issues, { title: '검사 항목 원문' }) : '');
    return v.technical_ready === true
      ? { tone: 'ok', tag: '자동 검증 통과', line: '연결 구조에는 문제가 없습니다. 내용이 원문과 맞는지는 아래에서 직접 검토하세요. 고친 연결은 적재할 때 다시 검증합니다.', more }
      : { tone: 'warn', tag: `검토 필요 ${issues.length}건`, line: '문서가 틀렸다는 뜻이 아니라, AI가 채우지 못했거나 사람이 확인해야 하는 곳입니다. 해당 조치 방법에서 값을 고르거나 고친 뒤 적재하세요. 고친 연결은 적재할 때 다시 검증합니다.', more };
  }
  function manualExecutionHtml(v, preview, catalog) {
    if (!preview.procedures.some(p => manualLink(preview,p).scope === 'purchase') && !v?.execution) return '';
    if (!v || typeof v.executable_ready !== 'boolean' || !Array.isArray(v.execution)) return UI.fold('실행 후보 검사', '<p class="muted">실행 후보 검사 기록이 없습니다. 원문 보관 여부와 실행 후보 가능 여부는 별도로 확인해야 합니다.</p>');
    return UI.fold(`실행 후보 검사<span class="muted num">${v.execution.length}건</span>`, '<p class="muted">원문 보관과 후보 연결의 구조 검사입니다. 실제 구매 승인이나 구매 실행 완료를 뜻하지 않습니다.</p>' + '<ul class="doc-issues">' + v.execution.map(row => {
      const p = preview.procedures.find(p => p.id === row.sop);
      const name = p?.name ? `${p.name} (${row.sop})` : '절차 표시 이름 기록 없음';
      const valid = typeof row.executable === 'boolean' && typeof row.ready === 'boolean' && Array.isArray(row.issues);
      const label = !valid ? '연결 구조 검사 정보 읽기 실패' : row.executable === false ? '원문 참고 보관 · 실행 후보 제외' : row.ready ? '실행 후보 기계 검사 통과 · 연결 구조 검사 통과' : '실행 후보 연결 확인 필요';
      const scope=UI.evaluationInfo(row), about=scope.state==='structural' ? '실제 견적 · 재고는 실행 판단 시 확인 · 현재 실제 승인 · 실행 준비는 확인하지 않음' : scope.state==='execution' ? '실제 실행 검사 기록 있음 · 승인 · 실행 완료 아님' : '실제 승인 · 실행 준비 검사 기록 확인 안 됨';
      return `<li><b>${esc(name)}</b> · ${esc(label)}<p class="muted">${esc(about)}</p>${valid && row.issues.length ? '<ul class="doc-issues">'+row.issues.map(x=>`<li>${esc(manualIssueMessage(x,preview,catalog))}</li>`).join('')+'</ul>' : ''}</li>`;
    }).join('')+'</ul>' + UI.raw(v.execution, { title: '실행 후보 검사 원문' }));
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
      `<div class="doc-sub" data-purchase-fields="${esc(p.id)}" ${purchase ? '' : 'hidden'}><p class="muted">고장 유형 없이 구매 대상 부품을 명시합니다. 원문 참고 보관은 실행 후보에 넣지 않으며 구매요청을 만들지 않습니다. 실행 후보는 구매요청 · 승인 담당자 · 공급 관계를 별도로 검사합니다.</p>${H.manualCatalogError ? `<p class="muted" data-tone="danger" role="alert">${esc(H.manualCatalogError)}</p>` : !catalog ? '<p class="muted">구매 부품 · 담당 역할 목록 확인 전입니다.</p>' : ''}<div role="group" class="doc-grid">` +
      UI.field({label:'원문 절차의 사용 방식',required:true,input:`<select id="manualExecutable-${esc(p.id)}" data-manual-executable="${esc(p.id)}"><option value="">원문을 확인하고 선택하세요</option><option value="false" ${link.executable === false ? 'selected' : ''}>원문 참고 보관 · 실행 후보 제외</option><option value="true" ${link.executable === true ? 'selected' : ''}>실행 후보로 검토 · 구매요청 연결 검사</option></select>`}) +
      UI.field({label:'구매 대상 부품',required:true,hint:'원문이 명시한 실제 등록 부품을 선택하세요. 여러 부품은 Ctrl 또는 Command를 누르고 선택합니다.',input:`<select id="manualParts-${esc(p.id)}" multiple data-manual-parts="${esc(p.id)}" ${catalog ? '' : 'disabled'}>${options(catalog?.parts,link.parts,'부품 등록 목록에서 확인되지 않음')}</select>`}) +
      UI.field({label:'구매 승인 담당 역할',hint:'실행 후보는 원문에 명시된 구매 승인 담당자가 필요합니다. 참고 보관은 미지정을 그대로 둘 수 있습니다.',input:`<select id="manualApprover-${esc(p.id)}" data-manual-approver="${esc(p.id)}" ${catalog ? '' : 'disabled'}><option value="">원문에 담당 역할 미지정</option>${options(catalog?.roles,link.approver,'담당 역할 등록 목록에서 확인되지 않음')}</select>`}) +
      UI.field({label:'원문 공급사 선정 기준',hint:'원문에 적힌 기준만 고르세요. 기준을 고르면 지금의 부품별 견적으로 공급사를 계산하고, 원문에 적힌 공급사는 쓰지 않습니다. 실제 승인이나 발주가 끝났다는 뜻은 아닙니다.',input:`<select id="manualSupplierPolicy-${esc(p.id)}" data-manual-supplier-policy="${esc(p.id)}"><option value="">지정하지 않음(원문에 적힌 공급사를 씁니다)</option>${Object.entries(policies).map(([key,label])=>`<option value="${key}" ${link.supplier_policy===key ? 'selected' : ''}>${esc(label)}</option>`).join('')}${link.supplier_policy!=null && !knownPolicy ? `<option value="${esc(link.supplier_policy)}" selected>선정 기준 기록을 확인해야 합니다</option>` : ''}</select>`}) + `</div><p class="muted">${esc(supplierState)} 참고 보관에는 공급사 선정 기준을 지정하지 않습니다.</p><p class="muted" data-supplier-review="${esc(p.id)}"></p></div>`;
  }
  function manualReferenceFields(p, r) {
    const link=manualLink(r,p), sid=p.existing_skill_id || link.existing_skill_id || '', pin=p.reference_contract_sha256 || link.reference_contract_sha256 || '';
    const rows=H.manualCatalog?.skills || [];
    return `<div class="doc-sub" data-reference-fields="${esc(p.id)}" ${link.kind==='reference' ? '' : 'hidden'}><p class="muted">이 절차는 원문만 보관하고 실행 후보에는 넣지 않습니다. 고장 유형 · 담당 역할 · 부품 · 실행 조치는 지정하지 않습니다. 이미 등록된 같은 절차와 연결해도 그 절차의 실행 단계는 바뀌지 않습니다.</p>`+
      (H.manualCatalogError ? `<p class="muted" data-tone="danger" role="alert">이미 등록된 절차 목록을 읽지 못했습니다. ${esc(H.manualCatalogError)}</p>` : !Array.isArray(H.manualCatalog?.skills) ? '<p class="muted">이미 등록된 절차 목록이 없습니다. 같은 절차를 자동으로 짐작해 연결하지 않습니다.</p>' : '')+ `<div role="group" class="doc-grid">` +
      UI.field({label:'참고 절차의 사용 방식',required:true,input:`<select data-reference-executable="${esc(p.id)}"><option value="">원문을 확인하고 선택하세요</option><option value="false" ${link.executable===false ? 'selected' : ''}>원문 참고 보관 · 실행 후보 제외</option></select>`})+
      UI.field({label:'이미 등록된 같은 절차와 연결',hint:'원문 번호와 모든 단계가 정확히 같은 등록 절차만 연결할 수 있습니다. 고르면 지금 등록된 그 절차의 내용을 기준으로 고정합니다.',input:`<select data-reference-target="${esc(p.id)}"><option value="">연결하지 않음(이 문서의 원문만 보관)</option>${rows.filter(x=>x.reference_contract).map(x=>`<option value="${esc(x.id)}" ${x.id===sid ? 'selected' : ''}>${esc(x.name || '등록 이름 없음')} · ${esc(x.reference_contract.sopId || '원문 번호 미상')}</option>`).join('')}${sid && !rows.some(x=>x.id===sid && x.reference_contract) ? `<option value="${esc(sid)}" selected>연결한 절차의 등록 내용을 읽지 못했습니다</option>` : ''}</select>`})+
      `</div><input type="hidden" data-reference-pin="${esc(p.id)}" value="${esc(pin)}"><div class="doc-compare" data-reference-comparison="${esc(p.id)}" role="status"></div></div>`;
  }
  // 2026-10-25 한 바퀴: 검토 화면이 절차 · 단계 · 고장 유형 연결만 보이고 AI가 뽑은 원인 · 증거 · 규칙은 보이지 않아 원문과 대조해
  // 틀린 항목을 뺄 수 없었다. 항목마다 원문 인용과 [적재에서 제외]를 둔다.
  const KNOW_GROUPS = [['failure_modes', '고장 유형', 'triangle-alert'], ['causes', '원인', 'git-branch'], ['evidence', '확인 증거', 'activity'], ['rules', '규칙', 'scale']];
  function manualKnowledgeSummary(group, x, own) {
    // 이 문서에서 새로 나온 고장 유형 · 원인은 아직 카탈로그에 없다 — 제안 안의 이름을 먼저 쓴다(내부 id 를 화면에 내지 않는다)
    const name = id => own[id] || UI.name(id);
    if (group === 'causes') return `사전 확률 ${x.prior ?? '미정'}${x.failure_mode ? ' · ' + name(x.failure_mode) : ''}`;
    if (group === 'evidence') return `${hydWords.fieldName(String(x.tag || '').toLowerCase())} ${hydWords.agg(x.aggregate)}${x.window_seconds != null ? ` ${x.window_seconds}초` : ''} ${hydWords.sym(x.expect)} ${x.threshold} → ${name(x.cause)}`;
    if (group === 'rules') return `${({ SELECT: '후보', EXCLUDE: '제외', PENALTY: '감점', WARN: '경고' })[x.effect] || x.effect} · ${UI.ruleLabel(x)}${x.penalty != null ? ' · ' + x.penalty + '만 원' : ''}${(x.outputs || []).length ? ' → ' + x.outputs.map(o => name(o)).join(', ') : ''}`;
    return (x.symptoms || []).map(y => name(y)).join(', ');
  }
  // 단계 줄(디자인 기준 5-3): 올리기 → AI 추출 → 검토 → 적재. 판(#manualUpload) 맨 위에 두고 지금 단계만 바꾼다. 1단계의 파일 고르기 칸은 1단계에서만 보인다
  const MANUAL_PHASES = ['올리기', 'AI 추출', '검토', '적재'];
  /* 저장된 추출 결과를 쓰는 문서(제공 문서 — 서버 응답의 cache)의 「추출 과정」. AI가 이 문서를 읽은 것은 미리 한 번이고 그때의 도구 호출 기록은 이 PC에 없다.
     없는 과정을 지어내지 않고 있는 사실만 보인다: ① 방금 서버가 한 일(H.trail — 요청이 실제로 오간 차례와 걸린 시간) ② 그 추출 결과에서 절마다 무엇이 뽑혔는지
     (절의 원문 범위 안에 인용이 놓인 조치 방법 · 지식 후보를 센 값). 시간으로 차오르는 막대나 일부러 늦춘 연출은 없다. */
  const anchorCount = r => r.sections.filter(s => s.anchor).length + r.procedures.reduce((n, p) => n + (p.anchor ? 1 : 0) + p.steps.filter(st => st.anchor).length, 0) +
    KNOW_GROUPS.reduce((n, [g]) => n + (((r.knowledge || {})[g]) || []).filter(x => x && x.anchor).length, 0);
  function sectionYield(r) {
    const secs = r.sections.map((s, i) => ({ s, i })).filter(x => x.s.anchor).sort((a, b) => a.s.anchor.page - b.s.anchor.page || a.s.anchor.start - b.s.anchor.start);
    const within = (a, k) => { const cur = secs[k].s.anchor, next = secs[k + 1] && secs[k + 1].s.anchor.page === cur.page ? secs[k + 1].s.anchor.start : Infinity;
      return !!a && a.page === cur.page && a.start >= cur.start && a.start < next; };
    return r.sections.map((s, i) => {
      const k = secs.findIndex(x => x.i === i);
      const procs = r.procedures.filter(p => p.section === s.ref || (!p.section && k >= 0 && within(p.anchor, k)));
      const know = k < 0 ? [] : KNOW_GROUPS.map(([g, title]) => [title, (((r.knowledge || {})[g]) || []).filter(x => x && within(x.anchor, k)).length]).filter(([, n]) => n);
      const got = [procs.length ? `조치 방법 ${procs.length}개(${procs.map(p => p.id).join(' · ')})` : '', ...know.map(([title, n]) => `${title} ${n}개`)].filter(Boolean);
      return { state: 'done', name: `${s.ref} ${s.title || ''}`.trim(), sub: got.length ? got.join(' · ') : '뽑힌 항목 없음 — 절 본문만 보관합니다' };
    });
  }
  function cachedProcessHtml(r) {
    const origin = ((r.extraction || {}).cache || {}).origin || {}, notes = origin.review_notes || [];
    return `<p class="muted" data-cached-note>이 문서는 AI가 미리 읽고 사람이 원문과 대조해 검토해 둔 추출 결과를 씁니다${origin.revision ? `(검토 판 ${esc(origin.revision)})` : ''}. 그때 AI가 부른 도구의 기록은 이 PC에 없습니다 — 아래는 그 추출 결과에서 절마다 뽑힌 것입니다.</p>` +
      `<h3 class="doc-yield-head">절마다 뽑힌 것<span class="muted num">매뉴얼 절 ${r.sections.length}개</span></h3><div data-cached-yield>${UI.timeline(sectionYield(r))}</div>` +
      (notes.length ? UI.fold(`검토하며 고친 곳<span class="muted num">${notes.length}건</span>`, `<ol class="doc-issues">${notes.map(n => `<li>${esc(n)}</li>`).join('')}</ol>`) : '');
  }
  function renderManualSteps(stage, o = {}) {
    const host = $('#manualUpload'); if (!host) return;
    host.dataset.stage = String(stage);
    phaseRow($('#manualSteps'), MANUAL_PHASES, stage, o);
    $('#manualPick').hidden = stage !== 1;
  }
  const manualStage = r => !r ? 1 : !r.extraction ? 2 : H.commit && H.commit.of === r ? 4 : 3;
  function renderPreview() {
    const r = H.preview; const box = $('#manualResult');
    if (H.live && (!r || H.live.source_id !== r.source_id)) { H.live.work.stop(); H.live = null; }      // 다른 문서로 바뀌었다 — 앞 문서의 구독을 끝낸다
    if (H.trail && (!r || H.trail.source_id !== r.source_id)) H.trail = null;
    H.commit = null;      // 다시 그리면 적재 단계(4)가 아니라 검토(3)부터다
    renderManualSteps(manualStage(r));
    if (!r) { box.innerHTML = ''; return; }
    note($('#manualStatus'), '');
    const fms = failureModesOf(r);
    const where = a => `${a.page}쪽${a.located === 'loose' ? ' · 대략 일치 — 문맥 확인 필요' : a.located === 'normalized' ? ' · 공백 · 기호를 맞춰 찾음' : ''}`;
    // 원문 인용: 상세 판의 첫 절에는 펼친 인용(quote)으로, 단계마다의 인용은 접기(citation)로
    const quote = a => a ? `<figure class="doc-quote"><blockquote>${esc(a.quote)}</blockquote><figcaption>${esc(where(a))}</figcaption></figure>` : '<p class="muted">원문 인용 위치가 없습니다. 아래 「원문」에서 직접 찾아 대조하세요.</p>';
    const citation = a => a ? UI.fold(`원문 인용<span class="muted">${esc(where(a))}</span>`, `<figure class="doc-quote"><blockquote>${esc(a.quote)}</blockquote></figure>`) : '';
    // 진행 단계: ① 올리기 → ② AI 추출 → ③ 검토 → ④ 적재. 올리기만 한 문서(r.extraction 없음)에는 절 · 절차 · 검증 칸이 없다 —
    // AI가 읽기 전에 결과나 경고처럼 보이는 것을 두지 않는다(서버도 등록 응답에 절 · 절차를 싣지 않는다: manual_review.registered)
    const stage = r.extraction ? 3 : 2;
    const readWarnings = r.warnings.length ? UI.fold(`${stage === 3 ? '추출 경고' : '문서 읽기 확인'}<span class="muted num">${r.warnings.length}건</span>`, `<ol class="doc-issues">${r.warnings.map(w=>`<li>${esc(w)}</li>`).join('')}</ol>`) : '';
    const sourceFold = UI.fold('원문<span class="muted">보관한 원본 · AI가 읽는 글</span>', `<div class="doc-links"><a class="btn" data-variant="outline" data-size="sm" href="${API.process}/api/kg/manuals/sources/${encodeURIComponent(r.source_id)}/original">${icon('download')}보관한 원본 내려받기</a>` +
      `<button type="button" class="btn" data-variant="outline" data-size="sm" id="manualFullSource">${icon('file-text')}추출 원문 전체 보기</button></div><div id="manualSourceText"></div>`);
    const history = UI.fold('이 문서의 이전 추출 결과', `<div class="doc-links">${UI.field({ label: '추출 작업', input: `<select id="manualExtractionRuns"><option value="">${esc(UI.t('loading'))}</option></select>` })}` +
      `<button type="button" class="btn" data-variant="outline" data-size="sm" id="manualAgentResult">선택한 결과 열기</button><button type="button" class="btn" data-variant="ghost" data-size="sm" id="manualExtractionMore" hidden>이전 추출 작업 더 보기</button></div>`);
    const another = `<button type="button" class="btn" data-variant="ghost" id="manualAnother">다른 문서 올리기</button>`;
    const procWhat = p => { const l = manualLink(r, p), fm = fms.find(f => f.id === l.failureMode);
      return l.kind === 'reference' ? '참고 절차(실행 대상 아님)' : l.scope === 'purchase' ? '구매 절차' : fm ? `${fm.name} · ${REL_KO[l.relation || 'REMEDIED_BY'] || ''}` : '고장 유형 미지정'; };
    if (stage === 2) {
      const ready = r.status === 'READY';
      // 다시 연 문서: 서버가 이 문서의 지금 적재된 판(r.loaded — 언제 · 누가 · 절차 수 · 그 판을 만든 원문이 지금 연 원문인가)을 준다.
      // 적재된 문서를 「아직 AI가 읽기 전」이라고 말하지 않는다
      // 같은 원본 파일을 「새 문서 등록」으로 다시 올린 문서: 이 문서에는 적재된 판이 없지만 서버가 같은 파일로 적재한 다른 문서(r.same_original)를 준다.
      // 그대로 추출 · 적재하면 절차 번호가 그 문서의 것과 겹쳐 적재가 거절되므로, 올린 직후에 그 사실을 말하고 주 단추를 [이 문서 개정]으로 둔다
      const L = r.loaded || null, here = !!(L && L.same_source), twin = L ? null : r.same_original || null;
      const count = x => Array.isArray(x) ? x.length : x;
      const factsOf = x => [x.at ? UI.dateTime(x.at) : '', x.provided ? '기본 제공' : x.by ? UI.who(x.by) : '', count(x.procedures) != null ? `절차 ${count(x.procedures)}개` : ''].filter(Boolean).join(' · ');
      const loadedFacts = L ? factsOf(L) : '';
      box.innerHTML = `<div class="panel-sec mprev" data-doc-stage="2">
        <div class="result"><div class="result-label">${here ? '이미 적재된 문서' : twin ? '이미 적재한 원문' : '올린 문서'}</div><div class="result-main">${esc(r.filename)} <span class="muted num">${r.chars.toLocaleString()}자</span></div>
          <p class="result-sub" id="manualStageNote"${ready && !L && !twin ? ' data-fresh' : ''}>${!ready ? `이 문서는 「${esc(UI.status(r.status))}」 상태라 AI 추출을 시작할 수 없습니다.`
            : here ? `이 원문으로 만든 판이 지식 지도에 적재돼 있습니다 — ${esc(loadedFacts)}. AI 추출을 다시 시작하면 새 결과를 검토해 이 문서를 개정합니다.`
            : L ? `이 문서는 다른 원문${L.filename ? `(${esc(L.filename)})` : ''}으로 만든 판이 적재돼 있습니다 — ${esc(loadedFacts)}. 지금 연 원문은 AI가 아직 읽지 않았습니다. AI 추출을 시작해 검토한 뒤 적재하면 그 판을 개정합니다.`
            : twin ? `같은 원문이 등록한 문서 「${esc(twin.filename || '')}」로 이미 적재돼 있습니다 — ${esc(factsOf(twin))}. 새 문서로 적재하면 절차 번호가 그 문서와 겹쳐 거절됩니다. 고쳐 넣으려면 그 문서의 개정으로 여세요.`
            : '아직 AI가 문서를 읽기 전입니다. AI 추출을 시작하면 문서에서 조치 절차 · 고장 유형 · 원인을 찾아 정리합니다. 결과는 사람이 검토한 뒤에만 지식으로 적재됩니다.'}</p></div>
        <section class="doc-live" id="manualLive" aria-label="AI 추출 과정" hidden><div data-live-trail></div><div class="doc-progress" data-live-progress hidden></div><div data-live-host></div><div data-live-fail></div></section>
        <footer class="form-foot"><span id="manualAgentStatus" role="status" class="muted"></span>${another}<button type="button" class="btn" ${twin ? 'data-variant="outline" ' : ''}id="manualAgentExtract" ${ready ? '' : 'disabled'}>${icon('sparkles')}AI 추출 시작</button>${twin ? `<button type="button" class="btn" id="manualReviseSame">${icon('pencil')}${esc(UI.t('kn.revise'))}</button>` : ''}</footer>
        <div class="doc-folds">${readWarnings}${sourceFold}${history}</div></div>`;
    } else {
      const k = r.knowledge || {}, groups = KNOW_GROUPS.filter(([g]) => (k[g] || []).length);
      const cachedRun = !!(r.extraction && r.extraction.cache);      // 저장된 추출 결과를 쓴 문서 — 과정 접기에 서버가 한 일과 절마다 뽑힌 것을 둔다
      const own = Object.fromEntries(KNOW_GROUPS.flatMap(([g]) => (k[g] || []).filter(x => x && x.id && x.name).map(x => [x.id, x.name])));
      const knowCount = groups.reduce((n, [g]) => n + k[g].length, 0);
      const v = manualValidation(r.validation, r, { ...H.catalog, ...H.manualCatalog });
      // 왼쪽 제안 목록의 한 줄: [data-item] = 종류:식별자. 오른쪽에는 같은 이름의 상세 판([data-pane])이 하나씩 있고 고른 것만 보인다
      const row = (key, kind, ic, title, meta, tag = '') => `<button type="button" class="row" data-item="${esc(key)}" data-group="${kind}" hidden><span class="row-ic">${icon(ic)}</span><span class="row-title">${esc(title)}</span><span data-item-tag>${tag}</span><span class="row-meta">${esc(meta)}</span></button>`;
      const procRows = r.procedures.map(p => row('proc:' + p.id, 'proc', 'list-checks', p.name, `${p.id} · ${procWhat(p)} · 단계 ${p.steps.length}`, needsLink(r, p) ? UI.chipText('검토 필요', 'warning') : '')).join('');
      const knowRows = groups.map(([g, title, ic]) => k[g].map(x => row(`know:${g}:${x.id}`, 'know', ic, x.name || x.annotation || x.id, `${title} · ${manualKnowledgeSummary(g, x, own)}`)).join('')).join('');
      const secRows = r.sections.map((s, i) => row('sec:' + i, 'sec', 'file-text', `${s.ref} ${s.title}`, '매뉴얼 절')).join('');
      const procPanes = r.procedures.map(p => `<section class="panel doc-pane" data-pane="${esc('proc:' + p.id)}" hidden>
        <header class="panel-head"><div><h2><span data-proc-title>${esc(p.name)}</span>${needsLink(r, p) ? UI.chipText('검토 필요', 'warning') : ''}</h2><p><span class="mono">${esc(p.id)}</span> · ${esc(procWhat(p))} · 단계 ${p.steps.length}</p></div></header>
        <div class="panel-sec"><h3>원문 인용</h3>${quote(p.anchor)}</div>
        <div class="panel-sec">${UI.section('이름과 연결', UI.field({ label: UI.t('skill.sop'), input: `<input aria-label="절차 번호" data-manual-id="${esc(p.id)}" value="${esc(p.id)}">` }) + UI.field({ label: UI.t('skill.name'), input: `<input aria-label="이름" data-manual-name="${esc(p.id)}" value="${esc(p.name)}">` }) +
          manualPurchaseFields(p, r) +
          UI.field({ label: UI.t('skill.fm'), hint: '고장 조치는 필수입니다. 구매 절차와 일반 원문 참고 절차에는 고장 유형을 연결하지 않습니다.', input: `<select data-fm="${esc(p.id)}"><option value="">(고르세요)</option>${fms.map(f => `<option value="${esc(f.id)}" ${f.id === manualLink(r,p).failureMode ? 'selected' : ''}>${esc(f.name)}</option>`).join('')}</select>` }) +
          UI.field({ label: UI.t('skill.relation'), input: `<select data-rel="${esc(p.id)}"><option value="" ${manualLink(r,p).scope === 'purchase' && !manualLink(r,p).relation ? 'selected' : ''}>고장 유형 관계 없음</option>${['REMEDIED_BY', 'MITIGATED_BY', 'PREVENTED_BY'].map(v => `<option value="${v}" ${(manualLink(r,p).relation || (manualLink(r,p).scope === 'purchase' ? '' : 'REMEDIED_BY')) === v ? 'selected' : ''}>${esc(REL_KO[v])}</option>`).join('')}</select>` }) +
          UI.field({ label: UI.t('skill.kind'), input: `<select data-kind="${esc(p.id)}"><option value="work_order">${esc(UI.t('skill.kind.workOrder'))}</option><option value="control" ${manualLink(r,p).kind === 'control' ? 'selected' : ''}>${esc(UI.t('skill.kind.control'))}</option><option value="reference" ${manualLink(r,p).kind === 'reference' ? 'selected' : ''}>일반 원문 참고 절차 · 실행 후보 제외</option></select>` }) +
          manualReferenceFields(p, r) +
          UI.field({ label: UI.t('skill.affects'), cls: 'wide', hint: '상태 변수 또는 성과 지표 id와 방향(+/-)을 쉼표로. 비우면 득실 0', input: `<input aria-label="영향" data-affects="${esc(p.id)}" value="${esc((manualLink(r,p).affects || []).map(a=>a.target+':'+a.sign).join(', '))}" placeholder="예: sv:bearing-wear:- , msr:maint-cost:+">` }))}</div>
        <div class="panel-sec"><h3>단계<span class="muted num">${p.steps.length}</span></h3><p class="muted" data-step-lock="${esc(p.id)}" hidden></p><ol class="doc-steps">${p.steps.map(s => `<li><textarea class="textarea" aria-label="단계 ${s.order}" data-manual-step="${esc(p.id)}" data-order="${s.order}" rows="2">${esc(s.text)}</textarea>${s.manual ? `<span class="badge" data-variant="outline">${esc(s.manual)}</span>` : ''}${citation(s.anchor)}</li>`).join('')}</ol></div>
        <div class="panel-sec pane-fold">${UI.raw({inline:p.link,override:r.links && Object.prototype.hasOwnProperty.call(r.links,p.id) ? r.links[p.id] : undefined,suggestedFailureMode:p.suggestedFailureMode,existing_skill_id:p.existing_skill_id,reference_contract_sha256:p.reference_contract_sha256}, { title: '절차 연결 원문' })}</div></section>`).join('');
      const knowPanes = groups.map(([g, title]) => k[g].map(x => `<section class="panel doc-pane" data-pane="${esc(`know:${g}:${x.id}`)}" hidden>
        <header class="panel-head"><div><h2>${esc(x.name || x.annotation || x.id)}</h2><p>${esc(title)}${manualKnowledgeSummary(g, x, own) ? ' · ' + esc(manualKnowledgeSummary(g, x, own)) : ''}</p></div></header>
        <div class="panel-sec"><h3>원문 인용</h3>${quote(x.anchor)}</div>
        <div class="panel-sec"><label class="doc-check"><input type="checkbox" class="input" data-know-drop="${esc(g)}" value="${esc(x.id)}"> 적재에서 제외</label><p class="muted">원문과 다르거나 근거가 없으면 제외합니다. 제외한 항목은 지식 지도에 들어가지 않습니다.</p></div></section>`).join('')).join('');
      const secPanes = r.sections.map((s, i) => `<section class="panel doc-pane" data-pane="sec:${i}" hidden>
        <header class="panel-head"><div><h2>${esc(s.title || s.ref)}</h2><p><span class="mono">${esc(s.ref)}</span> · 매뉴얼 절</p></div></header>
        <div class="panel-sec"><h3>절 본문</h3><div class="doc-text">${esc(s.excerpt)}</div></div>${s.anchor ? `<div class="panel-sec"><h3>원문 인용</h3>${quote(s.anchor)}</div>` : ''}</section>`).join('');
      const kinds = [['proc', '조치 방법', r.procedures.length], ['know', '지식 후보', knowCount], ['sec', '매뉴얼 절', r.sections.length]].filter(([, , n]) => n);
      box.innerHTML = `<div class="mprev" id="manualReview" data-doc-stage="3">
        <div class="panel-sec">
          <div class="result"><div class="result-label">AI 추출 결과 · ${esc(r.filename)}</div>
            <div class="result-main">조치 방법 ${r.procedures.length}개${knowCount ? ` · 지식 후보 ${knowCount}개` : ''} · 매뉴얼 절 ${r.sections.length}개를 찾았습니다</div>
            <p class="result-sub" id="manualAgentStatus" role="status">${cachedRun ? '저장된 추출 결과입니다 — 이 문서는 AI가 다시 읽지 않습니다. 원문과 대조해 검토한 뒤 적재하세요.' : 'AI 추출 결과입니다. 원문과 대조해 검토한 뒤 적재하세요.'}</p></div>
          ${cachedRun ? '<div class="doc-trail-slot" data-live-trail></div>' : ''}
          <div class="doc-valid"><p>${UI.chipText(v.tag, { ok: 'success', warn: 'warning', danger: 'danger' }[v.tone])}<span>${esc(v.line)}</span></p>${v.more}</div>
          <div class="doc-folds">${manualExecutionHtml(r.validation, r, { ...H.catalog, ...H.manualCatalog })}${readWarnings}
            <details class="fold" id="manualProcess"><summary>추출 과정 보기<span class="muted">${cachedRun ? '절마다 뽑힌 것' : 'AI가 읽은 구간과 도구 호출'}</span></summary><div class="fold-body"><div class="doc-live" id="manualLive">${cachedRun ? cachedProcessHtml(r) : ''}<div data-live-host${cachedRun ? ' hidden' : ''}></div><div data-live-fail></div></div></div></details>
            ${sourceFold}${history}
            ${r.page_reviews ? UI.fold('쪽별 추출 검토 기록', r.page_reviews.map(p => `<p>${esc(p.page)}쪽: ${esc(p.note)}</p>`).join('')) : ''}</div>
        </div>
        <div class="panel-sec doc-review">
          <div class="doc-review-bar">${UI.tabs(kinds, '', 'data-review-kind')}<span class="muted">제안을 고르면 오른쪽에 원문 인용과 고칠 칸이 나옵니다.</span></div>
          <div class="split doc-split"><div class="rows" id="manualItems" aria-label="AI가 낸 제안">${procRows}${knowRows}${secRows}</div><div class="doc-detail" id="manualPanes">${procPanes}${knowPanes}${secPanes}</div></div>
        </div>
        <div class="panel-sec doc-confirm">
          <label class="doc-check"><input type="checkbox" class="input" id="manualReviewed"> 원문 · 단계 · 고장 유형 · 관계를 검토했습니다.</label>
          <p id="manualReviewChanged" class="muted" hidden>검토 내용을 바꿨습니다. 위 검사는 원래 제안 기준입니다. 원문과 바뀐 연결을 대조한 뒤 검토 완료를 표시하세요.</p>
          <footer class="form-foot"><span id="manualCommitWhy" class="muted" role="status"></span>${another}<button type="button" class="btn" data-variant="outline" id="manualAgentExtract">AI 추출 다시 하기</button><button type="button" class="btn" id="manualCommit" ${r.status === 'READY' && r.sections.length && r.procedures.length ? '' : 'disabled'}>검토한 내용 적재</button></footer>
        </div></div>
        <div class="panel-sec" id="manualCommitView" data-doc-stage="4" hidden>
          <div class="result"><div class="result-label">적재 · ${esc(r.filename)}</div><div class="result-main" id="manualCommitTitle">검토한 내용을 지식 지도에 적재하는 중입니다</div></div>
          <div id="manualCommitSteps"></div></div>
        <div class="panel-sec doc-msg"><p id="manualMsg" class="muted" role="status"></p><div id="manualDone"></div></div>`;
      // 목록 + 상세: 종류(조치 방법 · 지식 후보 · 매뉴얼 절)를 고르면 그 종류의 제안만 목록에 보이고, 제안을 고르면 그 상세 판만 보인다
      const items = [...box.querySelectorAll('#manualItems [data-item]')], panes = [...box.querySelectorAll('#manualPanes [data-pane]')];
      const showItem = key => { H.review.sel = key;
        items.forEach(b => { if (b.dataset.item === key) b.setAttribute('aria-current', 'true'); else b.removeAttribute('aria-current'); });
        panes.forEach(p => { p.hidden = p.dataset.pane !== key; }); };
      const showKind = (kind, key) => {
        H.review.kind = kind;
        box.querySelectorAll('[data-review-kind]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.reviewKind === kind)));
        items.forEach(b => { b.hidden = b.dataset.group !== kind; });
        const rows = items.filter(b => b.dataset.group === kind);      // 그 종류의 첫 줄을 고른다(「검토 필요」가 붙은 줄이 있으면 그 줄)
        showItem(rows.some(b => b.dataset.item === key) ? key : (rows.find(b => b.querySelector('[data-item-tag] .tag')) || rows[0] || {}).dataset?.item || '');
      };
      H.review.show = (kind, key) => showKind(kind, key);
      box.querySelectorAll('[data-review-kind]').forEach(b => b.addEventListener('click', () => showKind(b.dataset.reviewKind)));
      $('#manualItems').addEventListener('click', ev => { const b = ev.target.closest('[data-item]'); if (b) { showItem(b.dataset.item); UI.revealDetail($('#manualPanes')); } });
      const keep = items.find(b => b.dataset.item === H.review.sel);
      showKind(keep ? keep.dataset.group : kinds[0] ? kinds[0][0] : 'proc', H.review.sel);
      // 제외를 고른 지식 후보는 목록의 그 줄에 「제외」가 붙는다
      box.querySelectorAll('[data-know-drop]').forEach(input => input.addEventListener('change', () => {
        const tag = items.find(b => b.dataset.item === `know:${input.dataset.knowDrop}:${input.value}`)?.querySelector('[data-item-tag]');
        if (tag) tag.innerHTML = input.checked ? UI.chipText('제외', 'neutral') : '';
      }));
    }
    // [이 문서 개정](같은 원문이 이미 적재된 문서로): 등록한 문서 목록의 [이 문서 개정]과 같은 길이다 — 「등록할 문서」를 그 문서로 고른다. 방금 올린 것이
    // 이 원문이면(H.sent — 내 파일이든 제공 문서든) 그 문서의 개정으로 바로 다시 올리고, 아니면(보관한 원문을 다시 연 경우) 파일을 고르게 1단계로 돌아간다
    $('#manualReviseSame')?.addEventListener('click', () => {
      if (H.sent && H.sent.source_id === r.source_id) { selectManualDocument(r.same_original.document_id, r.same_original.filename); uploadManual(H.sent.name, H.sent.blob, r.same_original.document_id); return; }
      reviseDoc(r.same_original.document_id, r.same_original.filename);
    });
    $('#manualAnother').addEventListener('click', () => {      // 1단계로: 고른 파일과 「문서 개정」 선택을 비우고 파일 고르기 칸을 다시 보인다
      H.preview = null; H.commit = null; $('#manualFile').value = ''; $('#manualFilename').textContent = UI.t('kn.noFile'); $('#manualDocumentId').value = ''; renderPreview();
      if (H.batch && !H.batch.running) { H.batch = null; renderProvided(); }
    });
    $('#manualFullSource').addEventListener('click', async () => {
      const end = hydLive.busy($('#manualFullSource'), '읽는 중');
      try {
        const source = await getJ(API.process + '/api/kg/manuals/sources/' + encodeURIComponent(r.source_id));
        if (H.preview !== r) return;
        $('#manualSourceText').innerHTML = source.pages.map(p => UI.fold(`${p.page}쪽 전체`, `<div class="doc-text">${esc(p.text)}</div>`, { open: source.pages.length === 1 })).join('');
      } catch (e) { if (H.preview === r) $('#manualSourceText').innerHTML = UI.errorBlock('원문을 읽지 못했습니다', e.message); }
      finally { end(false); }
    });
    const extractionKey = 'hyd.manual.extraction.' + r.source_id;
    const extractionUrl = API.process + '/api/kg/manuals/sources/' + encodeURIComponent(r.source_id) + '/extractions';
    const extractionState = () => JSON.parse(sessionStorage.getItem(extractionKey) || 'null');
    let extractionOffset = 0;
    const say = (text, bad = false) => note($('#manualAgentStatus'), text, bad);
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
        // 방금 접수한 작업(이 브라우저의 요청 기록)을 먼저 고른다 — 2026-10-25: 결과를 연 뒤 다시 추출을 요청하면 목록이 옛 작업을
        // 고른 채로 남아 [선택한 결과 열기]가 옛 결과를 새 결과처럼 보였다
        const chosen = extractionState()?.instance || r.extraction?.instance;
        if (chosen && Array.from(select.options).some(o => o.value === chosen)) select.value = chosen;
        else if (!select.value && select.options.length > 1) select.selectedIndex = 1;
        extractionOffset = page.next_offset;
        $('#manualExtractionMore').hidden = page.next_offset === null;
        // 이 문서를 AI가 읽은 결과가 이미 있는데(다른 화면에 다녀왔거나 창을 새로 열었을 때) 「아직 읽기 전」이라고 말하지 않는다 — 있는 결과와 여는 길을 말하고 그 접기를 편다
        const noteEl = $('#manualStageNote'), last = page.items[0];
        if (!append && last && noteEl && noteEl.dataset.fresh !== undefined) {
          noteEl.textContent = `AI가 이 문서를 읽은 결과가 있습니다 — 최근 ${UI.dateTime(last.start_date)} · ${UI.status(last.status)}. 아래 「이 문서의 이전 추출 결과」에서 [선택한 결과 열기]로 이어서 검토하거나, AI 추출을 다시 시작하세요.`;
          delete noteEl.dataset.fresh; select.closest('details').open = true;
        }
      } catch (e) { if (H.preview === r) say('추출 이력을 읽지 못했습니다: ' + e.message, true); }
    };
    $('#manualExtractionMore').addEventListener('click', () => loadExtractions(true));
    loadExtractions();
    /* ---- AI 추출의 실시간 표시. H.live = { source_id, instance, host, work(hydLive.agentWork), result(서버가 준 지금 상태), state, error, since }
       서버 GET …/extractions/{instance} 가 주는 것: status · workitem · segments[{index,total,chars,status,instance,workitem}] · progress{done,total} ·
       corrections · log · cache · preview(끝났을 때). 그 작업 행들의 실행 이벤트는 실시간 연결(hydStream)에서 온다. */
    const WAITING = ['TODO', 'IN_PROGRESS', 'SUBMITTED'];
    const SEG = { TODO: ['wait', '차례를 기다리는 중'], IN_PROGRESS: ['run', '읽는 중'], SUBMITTED: ['run', '낸 결과를 검증하는 중'], DONE: ['done', '끝남'],
      FAILED: ['fail', '실패'], CANCELLED: ['fail', '취소됨'], PENDING: ['stop', '검증에서 멈춤 — 사람 확인 필요'] };
    const segLabel = s => `구간 ${s.index}/${s.total}${s.chars ? ` · ${Number(s.chars).toLocaleString()}자` : ''}`;
    /* 방금 서버가 한 일(H.trail): [AI 추출 시작]을 누른 순간부터 요청이 실제로 오간 차례를 단계 목록(hydLive.steps)에 적는다 — 누르자마자 첫 줄이 보이고,
       0.몇 초 만에 끝나는 저장된 결과도 끝난 뒤 거친 단계와 걸린 시간이 결과 요약 아래에 남는다. 단계는 요청이 시작 · 끝난 때에만 넘어간다 */
    function placeTrail() {
      // 자리: 2단계는 실시간 칸(#manualLive) 맨 위, 3단계는 결과 요약 바로 아래(저장된 결과일 때만 — 0.몇 초 만에 끝난 일이 거친 단계를 접지 않고 남긴다)
      const T = H.trail, slot = box.querySelector('[data-live-trail]');
      if (!T || T.source_id !== r.source_id || !slot) return;
      if (T.host.parentElement !== slot) slot.replaceChildren(T.host);
      if (slot.closest('#manualLive')) $('#manualLive').hidden = false;
    }
    function startTrail() {
      const host = document.createElement('div'); host.className = 'doc-trail';
      const T = H.trail = { source_id: r.source_id, host, cached: false, list: hydLive.steps(host, [
        { key: 'open', label: '원문 확인 · 추출 작업 열기', hint: '서버가 보관한 원문을 확인하고 이 문서의 추출 처리 건을 여는 중입니다.' }], { label: '방금 서버가 한 일' }) };
      T.list.start('open'); placeTrail();
      return T;
    }
    function trailOpened(T, created) {
      T.cached = !!created.cache;
      const rev = ((created.cache || {}).origin || {}).revision;
      T.list.done('open', { note: T.cached ? `미리 추출해 검토해 둔 문서와 원문이 같습니다 — AI가 다시 읽지 않고 저장된 추출 결과를 씁니다${rev ? `(검토 판 ${rev})` : ''}`
        : `추출 처리 건을 열었습니다${created.segments > 1 ? ` — 문서를 구간 ${created.segments}개로 나눠 AI가 읽습니다` : ' — AI가 문서를 읽기 시작합니다'}` });
      if (!T.cached) return;
      // 저장된 결과일 때만 뒤 단계가 있다(AI 추출은 아래 실시간 기록이 잇는다): 결과 읽기 요청(GET) → 검토 화면에 쓸 목록 읽기
      const inner = document.createElement('div'), was = T.list;
      T.list = hydLive.steps(inner, [{ key: 'open', label: '원문 확인 · 추출 작업 열기' },
        { key: 'verify', label: '저장된 추출 결과를 원문 · 지금 지식과 대조', hint: '서버가 인용마다 원문의 그 자리에 있는지 보고, 지금 지식 지도와 겹치는 번호가 없는지 견주는 중입니다.' },
        { key: 'prepare', label: '검토 화면 준비', hint: '검토 화면의 고르기 칸에 쓸 고장 유형 · 역할 · 부품 목록을 읽는 중입니다.' }], { label: '방금 서버가 한 일' });
      T.list.done('open', { note: (was.list.find(s => s.key === 'open') || {}).note, t0: was.since('open') });
      T.host.replaceChildren(inner);
    }
    function liveItems(result) {
      const one = s => { const [state, stateText] = SEG[s.status] || ['wait', UI.status(s.status)]; return { id: s.workitem, instance: s.instance, state, stateText }; };
      if (Array.isArray(result.segments) && result.segments.length) return result.segments.map(s => ({ ...one(s), label: segLabel(s) }));
      return result.workitem ? [{ ...one(result), label: '' }] : [];
    }
    function drawLive() {
      const L = H.live, slot = $('#manualLive'); if (!L || !slot || H.preview !== r) return;
      const hostSlot = slot.querySelector('[data-live-host]');
      if (L.host.parentElement !== hostSlot) hostSlot.replaceChildren(L.host);        // 같은 기록 칸을 2단계 → 3단계 「추출 과정 보기」로 옮긴다(다시 만들지 않는다)
      slot.hidden = false; placeTrail();
      const result = L.result;
      const others = L.state === 'failed' && (result.segments || []).some(s => WAITING.includes(s.status));      // 한 구간이 멈췄어도 다른 구간은 계속 돈다
      const running = L.state === 'starting' || L.state === 'running' || others;
      const p = result && result.progress, c = result && result.corrections;
      // 저장된 추출 결과를 쓰는 문서(제공 문서 — 서버 result.cache)는 AI가 다시 읽지 않는다. 한 화면에서 「AI가 읽고 있습니다」와 「다시 읽지 않습니다」를 함께 말하지 않고,
      // 실제로 일어나는 일 하나만 말한다(이것은 키가 있을 때도 같은 제품 동작이라 숨길 재생 사정이 아니다 — 본 것을 사실로 믿을 수 있어야 한다)
      const cached = !!(result && result.cache);
      hostSlot.hidden = cached;      // 저장된 결과에는 AI 실행 기록이 없다 — 빈 기록 칸 대신 서버가 한 일(H.trail)과 절마다 뽑힌 것(cachedProcessHtml)이 그 자리에 있다
      const headline = cached ? (L.state === 'done' ? '저장된 추출 결과를 불러왔습니다' : L.state === 'failed' ? '저장된 추출 결과를 불러오지 못했습니다' : '저장된 추출 결과를 불러오는 중 — 이 문서는 AI가 다시 읽지 않습니다')
        : L.state === 'starting' ? 'AI 추출 작업을 여는 중' : L.state === 'done' ? 'AI 추출이 끝났습니다'
        : L.state === 'failed' ? (others ? '한 구간이 멈췄습니다 — 남은 구간은 계속 읽는 중' : 'AI 추출이 끝나지 않았습니다') : p ? `AI가 문서를 읽고 있습니다 — 구간 ${p.total}개 가운데 ${p.done}개를 마쳤습니다` : 'AI가 문서를 읽고 있습니다';
      const info = [c && c.attempts ? `낸 결과가 검증에서 ${c.attempts}번 되돌아갔습니다${(c.reasons || []).length ? ` — 마지막 사유: ${c.reasons[c.reasons.length - 1]}` : ''}` : ''].filter(Boolean).join(' ');
      L.work.set({ items: result ? liveItems(result) : [], running, since: L.since, headline, note: info });
      // 센 값이 있을 때만 진행 막대(구간 몇 개 가운데 몇 개) — 시간으로 차오르는 막대는 그리지 않는다
      const bar = slot.querySelector('[data-live-progress]');
      if (bar) { const on = stage === 2 && running && p && p.total > 1; bar.hidden = !on;
        if (on) bar.innerHTML = `<div class="progress" role="progressbar" aria-valuemin="0" aria-valuemax="${p.total}" aria-valuenow="${p.done}" aria-label="읽은 구간"><span style="width:${Math.round(p.done / p.total * 100)}%"></span></div><span class="muted num">${p.done} / ${p.total} 구간</span>`; }
      const fail = slot.querySelector('[data-live-fail]');
      if (L.error) fail.innerHTML = `<div class="alert" data-variant="destructive" role="alert">${icon('circle-alert')}<h2>추출 상태를 확인하지 못했습니다</h2><section>${esc(L.error)}</section><footer><button type="button" class="btn" data-variant="outline" data-size="sm" data-live-check>다시 확인</button></footer></div>`;
      else if (L.state === 'failed') {
        const stuck = (result.segments || []).filter(s => s.status !== 'DONE' && !WAITING.includes(s.status)).map(s => `구간 ${s.index}: ${(SEG[s.status] || [0, UI.status(s.status)])[1]}`).join(' · ');
        fail.innerHTML = `<div class="alert" data-variant="destructive" role="alert">${icon('circle-alert')}<h2>AI 추출이 끝나지 않았습니다 — ${esc(UI.status(result.status))}</h2>` +
          `<section>${stuck ? esc(stuck) + '. ' : ''}멈춘 까닭은 위 기록의 마지막 줄에 있습니다. 처리 건 화면에서 이 추출 작업의 단계를 닫거나 다시 진행할 수 있습니다.` +
          (result.log ? UI.raw(result.log, { title: '추출 기록 원문' }) : '') + `</section>` +
          `<footer><button type="button" class="btn" data-variant="outline" data-size="sm" data-live-inst>처리 건에서 보기${icon('arrow-right')}</button></footer></div>`;
      } else fail.innerHTML = '';
      fail.querySelector('[data-live-check]')?.addEventListener('click', () => checkLive(L.instance));
      fail.querySelector('[data-live-inst]')?.addEventListener('click', () => window.hydShell.navigate({ tab: 'instances', inst: L.instance }));
      if (stage === 2) {
        renderManualSteps(2, { busy: running });      // AI가 읽는 동안에만 단계 줄의 고리가 돈다
        const b = $('#manualAgentExtract'), n = $('#manualStageNote');
        if (n) n.hidden = true;
        if (b && !b.classList.contains('lv-busy')) { b.hidden = running && L.state !== 'failed'; b.disabled = b.hidden || r.status !== 'READY'; b.innerHTML = icon('sparkles') + (L.state === 'failed' ? 'AI 추출 다시 시작' : 'AI 추출 시작'); }
      }
    }
    // 서버에 지금 상태를 한 번 묻는다. 부르는 때: 시작 직후 · 단계가 바뀌는 이벤트가 왔을 때 · 다시 연결됐을 때 · 연결이 끊긴 동안의 5초 묻기 · [지금 확인]
    async function checkLive(instance) {
      const L = H.live; if (!L || L.instance !== instance || H.preview !== r) return;
      if (L.checking) { L.again = true; return; }
      L.checking = true; clearTimeout(L.settle);
      const T = H.trail && H.trail.source_id === r.source_id && H.trail.cached ? H.trail.list : null;
      try {
        if (T && T.state('verify') === 'wait') T.start('verify');
        const result = await getJ(extractionUrl + '/' + encodeURIComponent(instance));
        if (H.live !== L || H.preview !== r) return;
        L.result = result; L.error = '';
        if (result.preview) {
          const pv = result.preview, issues = ((pv.validation || {}).issues || []).length;
          if (T && T.state('verify') === 'run') { T.done('verify', { note: `인용 ${anchorCount(pv)}곳이 원문의 그 자리에 있습니다${pv.coverage ? ` · 원문 글자의 ${Math.round(pv.coverage.ratio * 100)} %가 인용에 쓰였습니다` : ''} · 사람이 확인할 곳 ${issues}건` }); T.start('prepare'); }
          await loadManualCatalog(); if (H.live !== L || H.preview !== r) return;
          if (T && T.state('prepare') === 'run') T.done('prepare', { note: `매뉴얼 절 ${pv.sections.length}개 · 조치 방법 ${pv.procedures.length}개를 검토 화면에 올렸습니다` });
          L.state = 'done'; H.preview = result.preview; renderPreview(); return;      // 3단계로 — 기록 칸은 「추출 과정 보기」로 옮겨 간다
        }
        L.state = WAITING.includes(result.status) ? 'running' : 'failed';
        // 에이전트가 결과를 냈고 서버가 검증해 넘기는 사이(SUBMITTED)에는 이벤트가 더 오지 않는다 — 이 상태일 때만 1.5초 뒤 한 번 더 묻는다
        if (result.status === 'SUBMITTED' || (result.segments || []).some(s => s.status === 'SUBMITTED')) L.settle = setTimeout(() => checkLive(instance), 1500);
      } catch (e) { if (H.live === L) L.error = e.message; if (T) ['verify', 'prepare'].forEach(k => { if (T.state(k) === 'run') T.fail(k, { note: e.message }); }); }
      finally { L.checking = false; }
      if (H.live !== L || H.preview !== r) return;
      drawLive();
      if (L.again) { L.again = false; checkLive(instance); }
    }
    function startLive(instance, since) {
      if (H.live) H.live.work.stop();
      const host = document.createElement('div');
      const L = H.live = { source_id: r.source_id, instance, host, result: null, state: 'starting', error: '', since: since || null, checking: false, again: false, settle: 0 };
      L.work = hydLive.agentWork(host, { tab: 'knowledge', pollMs: 5000, onChange: () => checkLive(instance) });
      drawLive(); checkLive(instance);
    }
    // 3단계에서 이미 끝난 추출의 과정 기록: 접기를 처음 열 때 그 작업 행들을 읽어 온다(방금 지켜본 추출은 2단계의 기록 칸이 그대로 옮겨 와 있다)
    function ensureProcess() {
      const ex = r.extraction; if (!ex || !ex.instance) return;
      if (H.live && H.live.instance === ex.instance) { drawLive(); return; }
      if (H.live) H.live.work.stop();
      const host = document.createElement('div');
      const segs = Array.isArray(ex.segments) && ex.segments.length ? ex.segments.map((s, i) => ({ ...s, index: i + 1, total: ex.segments.length, status: 'DONE' })) : null;
      const L = H.live = { source_id: r.source_id, instance: ex.instance, host, state: 'done', error: '', since: null, checking: false, again: false, settle: 0,
        result: segs ? { status: 'DONE', segments: segs } : { status: 'DONE', instance: ex.instance, workitem: ex.workitem, cache: ex.cache } };
      L.work = hydLive.agentWork(host, { tab: 'knowledge', onChange: () => {} });
      drawLive();
    }
    placeTrail();      // 방금 서버가 한 일 — 화면을 다시 그려도 같은 단계 목록이 제자리(2단계 자리 · 3단계 「추출 과정 보기」)에 놓인다
    if (stage === 3) {
      const fold = $('#manualProcess');
      if (H.live && H.live.instance === (r.extraction || {}).instance) { H.live.state = 'done'; drawLive(); }      // 방금 지켜본 추출 — 기록 칸을 접기 안으로 옮긴다
      fold.addEventListener('toggle', () => { if (fold.open) ensureProcess(); });
    }
    $('#manualAgentExtract').addEventListener('click', async () => {
      // 검토하며 고친 칸이 있으면 새 추출 결과가 그 내용을 덮는다 — 먼저 묻는다(고친 표시 = #manualReviewChanged)
      const edited = $('#manualReviewChanged') && !$('#manualReviewChanged').hidden;
      if (edited && !await UI.confirm({ title: 'AI 추출을 다시 할까요?', body: '지금 고친 검토 내용은 새 추출 결과로 바뀌어 사라집니다.', ok: '다시 추출', danger: true })) return;
      const button = $('#manualAgentExtract'); say('');
      const end = hydLive.busy(button, 'AI 추출을 요청하는 중');
      const trail = startTrail();
      try {
        const previous = extractionState();
        const state = previous && !previous.instance ? previous : { request_id: UI.uuid() };
        sessionStorage.setItem(extractionKey, JSON.stringify(state));
        const created = await postJ(extractionUrl, { request_id: state.request_id });
        trailOpened(trail, created);
        const since = new Date().toISOString();
        sessionStorage.setItem(extractionKey, JSON.stringify({ ...state, instance: created.instance, since }));
        if (H.preview !== r) return;
        if (stage === 3) {      // 다시 추출: 올리기만 한 상태(2단계)의 화면으로 돌아가 거기서 지켜본다 — renderPreview 가 방금 요청한 작업을 이어 연다
          const registered = await getJ(API.process + '/api/kg/manuals/sources/' + encodeURIComponent(r.source_id) + '/preview');
          if (H.preview !== r) return;
          if (H.live) { H.live.work.stop(); H.live = null; }
          H.preview = registered; renderPreview(); return;
        }
        end(true);
        loadExtractions();
        startLive(created.instance, since);
      } catch (e) { end(false); if (trail.list.state('open') === 'run') trail.list.fail('open', { note: e.message }); if (H.preview === r) say('AI 추출을 시작하지 못했습니다: ' + e.message + ' — 다시 누르면 같은 요청으로 확인합니다.', true); }
    });
    $('#manualAgentResult').addEventListener('click', async () => {
      const instance = $('#manualExtractionRuns').value;
      if (!instance) { say('열 추출 작업을 선택하세요.', true); return; }
      const end = hydLive.busy($('#manualAgentResult'), '여는 중');
      try {
        const result = await getJ(extractionUrl + '/' + encodeURIComponent(instance));
        if (H.preview !== r) return;
        if (result.preview) { await loadManualCatalog(); if (H.preview !== r) return; if (H.live) { H.live.work.stop(); H.live = null; } H.preview = result.preview; renderPreview(); return; }
        end(false);
        if (stage === 2) startLive(instance, null);      // 아직 도는 중이거나 멈춘 작업 — 그 과정을 2단계 자리에서 그대로 보인다
        else say(`이 추출 작업은 아직 결과가 없습니다: ${UI.status(result.status)}. ${UI.t('nav.instances')} 화면에서 단계와 오류를 확인할 수 있습니다.`, true);
      } catch (e) { end(false); if (H.preview === r) say('추출 결과를 확인하지 못했습니다: ' + e.message, true); }
    });
    // 이 브라우저가 방금 요청한 추출이 아직 결과 전이면(화면을 다시 열었을 때 · 다시 추출을 눌렀을 때) 이어서 지켜본다
    if (stage === 2) {
      const mine = extractionState();
      if (H.live && H.live.source_id === r.source_id) drawLive();
      else if (mine && mine.instance) startLive(mine.instance, mine.since || null);
    }
    const msg = (text, bad = false) => note($('#manualMsg'), text, bad);
    // 4단계(적재) 화면으로 넘기거나(on) 3단계(검토)로 돌아온다. 고칠 칸은 숨겨도 그대로 남는다
    const commitView = (on, o = {}) => {
      H.commit = on ? { of: r } : null;
      $('#manualReview').hidden = on; $('#manualCommitView').hidden = !on;
      renderManualSteps(on ? 4 : 3, o);
    };
    const c = $('#manualCommit'); if (c) c.addEventListener('click', async () => {
      // 아래 검사에서 멈춘 까닭은 누른 단추의 줄(단추 줄의 왼쪽 — 디자인 기준 1-6 「꺼진 · 못 한 까닭은 그 자리에」)에 빨간 글로 보이고, 그 절차의 고칠 칸이 열린다.
      // 서버에 보낸 뒤의 진행 · 결과 글은 4단계 자리(#manualMsg)다
      const why = $('#manualCommitWhy'), stop = (text, key) => { note(why, text, true); if (key) H.review.show('proc', key); };
      note(why, '');
      const by = manualActor(); if (!by) { stop('담당자 정보를 읽지 못했습니다. 화면을 새로 고친 뒤 다시 해 주세요.'); return; }
      if (!$('#manualReviewed').checked) { stop('원문을 대조하고 검토 완료를 표시하세요.'); return; }
      const f = (p, name) => box.querySelector(`[data-${name}="${CSS.escape(p.id)}"]`);
      const built = commitRequest(r, p => ({ id: f(p, 'manual-id').value, name: f(p, 'manual-name').value,
        steps: new Map([...box.querySelectorAll(`[data-manual-step="${CSS.escape(p.id)}"]`)].map(x => [Number(x.dataset.order), x.value])),
        fm: f(p, 'fm').value, rel: f(p, 'rel').value, kind: f(p, 'kind').value, affects: f(p, 'affects').value, scope: f(p, 'manual-scope').value, executable: f(p, 'manual-executable').value,
        parts: [...f(p, 'manual-parts').selectedOptions].map(o => o.value), approver: f(p, 'manual-approver').value, policy: f(p, 'manual-supplier-policy').value,
        refExecutable: f(p, 'reference-executable').value, refTarget: f(p, 'reference-target').value, refPin: f(p, 'reference-pin').value }),
        [...box.querySelectorAll('[data-know-drop]:checked')].map(i => [i.dataset.knowDrop, i.value]), by);
      if (built.stop) { stop(built.stop, built.at); return; }
      const request = built.request;
      // 적재는 요청 둘 · 셋이 차례로 간다 — 4단계 자리에서 지금 어느 요청을 기다리는지 단계 목록이 하나씩 채워진다(서버가 주지 않는 진행률은 그리지 않는다)
      msg(''); $('#manualDone').innerHTML = '';
      commitView(true, { busy: true });
      $('#manualCommitTitle').textContent = '검토한 내용을 지식 지도에 적재하는 중입니다';
      const flow = hydLive.steps($('#manualCommitSteps'), [...(r.previous_batch ? [{ key: 'changes', label: '개정으로 빠지는 항목 확인', hint: '이전 판본과 새 판본을 견주는 중입니다.' }] : []),
        { key: 'commit', label: `검토한 내용을 지식 지도에 적재 — 매뉴얼 절 ${r.sections.length}개 · 조치 방법 ${r.procedures.length}개 · 단계 ${r.procedures.reduce((n, p) => n + p.steps.length, 0)}개` +
            (KNOW_GROUPS.some(([g]) => ((r.knowledge || {})[g] || []).length) ? ' · ' + KNOW_GROUPS.filter(([g]) => ((r.knowledge || {})[g] || []).length).map(([g, title]) => `${title} ${r.knowledge[g].length - box.querySelectorAll(`[data-know-drop="${g}"]:checked`).length}개`).join(' · ') : ''), hint: '절 · 조치 방법 · 단계 · 규칙 연결을 한 번에 넣는 중입니다. 도중에 실패하면 아무것도 들어가지 않습니다.' },
        { key: 'reload', label: '적재한 문서 목록과 지식 지도 다시 읽기' }], { label: '적재 단계' });
      // 적재하지 않고 검토로 돌아갈 때: 단계 줄은 3단계로, 까닭은 그 아래 한 줄로
      const back = (text, bad) => { commitView(false); msg(text, bad); };
      let at = '';
      try {
        if (request.previous_batch) {
          flow.start(at = 'changes');
          const changes=await postJ(API.process + '/api/kg/manuals/changes',request);
          if (H.preview !== r) return;
          flow.done('changes', { note: changes.removed?.length ? `빠지는 항목 ${changes.removed.length}개` : '빠지는 항목 없음' });
          if (changes.removed?.length) {
            const labels={Skill:'조치 방법',FailureMode:'고장 유형',Cause:'원인',Evidence:'진단 근거',Rule:'판단 규칙',
              Step:'절차 단계',KnowledgeSource:'이전 원문 판본 연결',ManualSection:'이전 원문 절 연결'};
            const names=changes.removed.map(n=>`${n.labels.map(l=>labels[l] || l).join(' · ')}: ${n.name}`).join('\n');
            const proceed=await UI.confirm({title:'개정으로 지워지는 항목을 확인하세요',
              body:'이전 판본의 다음 항목이 새 지식 지도에서 빠집니다. 원문 보관과 적재 이력은 유지됩니다.\n\n'+names,
              ok:'변경 확인 후 적재',danger:true});
            if (!proceed) { back('적재하지 않았습니다. 빠지는 내용을 검토하세요.', true); return; }
          }
        }
        flow.start(at = 'commit');
        const out = await postJ(API.process + '/api/kg/manuals/commit', request);
        if (H.preview !== r) return;
        flow.done('commit', { note: `절 ${out.sections} · 조치 방법 ${out.procedures} · 단계 ${out.steps}` });
        const activated = out.candidate_activation && typeof out.candidate_activation === 'object' ? Object.entries(out.candidate_activation) : [];
        msg(`적재 완료: 절 ${out.sections} · 조치 방법 ${out.procedures} · 단계 ${out.steps}. ` + (activated.length
          ? '후보 규칙에 연결: ' + activated.map(([fm, rules]) => `${hydWords.idName(fm)} → ${rules.map(r => hydWords.idName(r)).join(', ')}`).join(' · ') + ' (되돌리면 함께 빠집니다)'
          : '연결된 후보 규칙이 없어 판단 후보는 바뀌지 않았습니다.'));
        H.skills = [];
        flow.start(at = 'reload');
        await loadUploads(); if (window.hydEnt) hydEnt.loadGraph(true);
        if (H.preview !== r) return;
        flow.done('reload');
        renderManualSteps(4, { done: true });
        $('#manualCommitTitle').textContent = '지식 지도에 적재했습니다';
        $('#manualDone').innerHTML = `<footer class="form-foot doc-next"><button type="button" class="btn" data-variant="outline" id="manualNext">다른 문서 올리기</button>${UI.goLink('ontology', '지식 지도에서 보기')}${UI.goLink('scenario', '결함 시뮬레이션으로')}</footer>`;
        $('#manualNext').addEventListener('click', () => $('#manualAnother').click());
      } catch (e) {
        if (H.preview !== r) return;
        if (at && flow.state(at) === 'run') flow.fail(at, { note: e.message });
        renderManualSteps(4);
        $('#manualCommitTitle').textContent = '적재하지 못했습니다';
        msg('적재하지 못했습니다: ' + e.message, true);
        $('#manualDone').innerHTML = `<footer class="form-foot"><button type="button" class="btn" data-variant="outline" id="manualBack">${icon('arrow-left')}검토로 돌아가기</button></footer>`;
        $('#manualBack').addEventListener('click', () => { $('#manualDone').innerHTML = ''; commitView(false); });
      }
    });
    const changed = event => { if ($('#manualReviewed') && event.target.id !== 'manualReviewed' && event.target.id !== 'manualExtractionRuns') { $('#manualReviewed').checked = false; $('#manualReviewChanged').hidden = false; } };
    box.oninput = changed;
    box.querySelectorAll('[data-manual-scope]').forEach(select => select.addEventListener('change', () => {
      box.querySelector(`[data-purchase-fields="${CSS.escape(select.dataset.manualScope)}"]`).hidden = select.value !== 'purchase';
      $('#manualReviewed').checked = false;
    }));
    box.onchange = changed;
    // 이름 칸을 고치면 왼쪽 목록의 그 줄과 판 머리의 이름이 바로 따라간다(적재 전까지 옛 이름이 남아, 고친 것이 들어갔는지 알 수 없었다). 비우면 원래 이름을 보인다
    box.querySelectorAll('[data-manual-name]').forEach(input => input.addEventListener('input', () => {
      const key = 'proc:' + input.dataset.manualName, name = input.value.trim() || r.procedures.find(p => p.id === input.dataset.manualName).name;
      const rowTitle = [...box.querySelectorAll('#manualItems [data-item]')].find(b => b.dataset.item === key)?.querySelector('.row-title');
      const head = [...box.querySelectorAll('#manualPanes [data-pane]')].find(n => n.dataset.pane === key)?.querySelector('[data-proc-title]');
      if (rowTitle) rowTitle.textContent = name;
      if (head) head.textContent = name;
    }));
    box.querySelectorAll('select[data-kind]').forEach(kind => {      // 실행 종류 고르기 칸만(실시간 단계 줄 .line 도 data-kind 를 쓴다)
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
        comparison.innerHTML=`<p><b>${esc(state)}</b></p><p class="muted">원문 담당 역할: ${esc(roleName ? roleName+' · 참고 보관에는 사용하지 않습니다.' : '미상 · 자동으로 채우지 않습니다.')}</p><h4>이 문서의 원문 단계</h4>${lines(sourceSteps)}`+
          (target.value ? `<h4>이 문서의 원문 절 · 판본 대조</h4>${sourceSections.length ? sourceSections.map(s=>`<p><b>${esc(s.ref)} ${esc(s.title || '')}</b></p><p>${esc(s.excerpt || '원문 절 본문 없음')}</p>`).join('') : '<p>연결된 원문 절 기록 없음</p>'}<p class="muted">원문 절과 기존 등록 설명의 기준값이 같다고 추정하지 않습니다. 재참조는 기존 실행 기준을 바꾸는 작업이 아닙니다.</p>` : '')+
          (contract ? `<h4>현재 등록된 실행 단계 · ${esc(registered.name || '등록 이름 없음')} (${esc(contract.sopId || '원문 번호 미상')})</h4>${Array.isArray(contract.steps) ? lines(contract.steps) : '<p>실행 단계 정보 읽기 실패</p>'}<p class="muted">대상 원문 소유 문서: ${contract.owner ? '등록됨 · 식별자는 원문에서 확인하세요.' : '소유 문서 기록 없음'}</p><h4>현재 실행 단계가 참조하는 등록 설명</h4>${Array.isArray(contract.sections) && contract.sections.length ? contract.sections.map(s=>`<p><b>${esc(s.ref || '절 번호 미상')} ${esc(s.title || '')}</b></p><p>${esc(s.excerpt || '등록 설명 본문 없음')}</p><p class="muted">${s.source_id && s.citation ? '등록된 출처 식별 · 인용 정보는 판본 원문에서 확인하세요.' : '등록된 기존 설명 · 원본 인용 기록 없음'}</p>`).join('') : '<p>등록 설명 기록 없음 · 원문 기준값과 같은 판본이라고 판단할 수 없습니다.</p>'}` : '')+
          UI.raw({existing_skill_id:target.value || null,reference_contract_sha256:pin.value || null,current_contract:contract || null}, { title: '참조 대상 · 고정 판본 원문' });
      };
      const update=()=>{
        const reference=kind.value==='reference'; field('reference-fields').hidden=!reference;
        field('manual-scope').querySelector('[value="fault"]').textContent=reference ? '일반 원문 참고 · 업무 실행 연결 없음' : '고장 조치 · 고장 유형 연결 필수';
        if(reference) field('rel').value='';
        ['fm','rel','affects','manual-scope'].forEach(name=>{field(name).disabled=reference;});
        field('purchase-fields').hidden=reference || field('manual-scope').value!=='purchase';
        // 참고 절차의 단계는 그 단계의 원문 인용에 그대로 있는 글만 적재된다(서버 manual_review — 「참고 단계 내용은 검증한 원문 인용에 그대로」). 그래서 이미 인용 그대로인 단계는
        // 고칠 것이 없다 — 열어 두면 고친 뒤 적재에서야 거절되므로 읽기 전용으로 보이고 까닭을 그 자리에서 한 번 말한다(다른 종류에서 고쳐 둔 글은 원문으로 되돌린다).
        // AI가 낸 글이 인용과 다른 단계(인용이 없는 단계 포함)는 원문 문장으로 고쳐야 적재되므로 열어 두고, 무엇으로 고쳐야 하는지 같은 줄에서 말한다
        const verbatim=st=>!!(st.anchor && typeof st.anchor.quote==='string' && st.anchor.quote.includes(st.text));
        const source=new Map(r.procedures.find(p=>p.id===id).steps.map(st=>[st.order,st]));
        let open=0;
        box.querySelectorAll(`[data-manual-step="${CSS.escape(id)}"]`).forEach(input=>{
          const st=source.get(Number(input.dataset.order)), lock=reference && verbatim(st);
          input.readOnly=lock; if(lock) input.value=st.text; else if(reference) open++;
        });
        const lockNote=field('step-lock'); lockNote.hidden=!reference;
        lockNote.textContent=open ? '참고 절차의 단계는 원문 그대로 보관합니다. 원문 인용과 글이 다른 단계만 열려 있습니다 — 원문 문장 그대로 고쳐야 적재됩니다.' : '참고 절차의 단계는 원문 그대로 보관하므로 고칠 수 없습니다. 단계를 고치려면 위에서 종류를 바꾸세요.';
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
  // 올리기 단계의 두 길: 제공 문서에서 고르기(provided) · 내 파일 올리기(file). 고른 길의 칸([data-pick])만 보인다(index.html #manualPick · #ddlPick)
  function showPick(pick, mode) {
    pick.querySelectorAll('[data-pick-mode]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.pickMode === mode)));
    pick.querySelectorAll('[data-pick]').forEach(p => { p.hidden = p.dataset.pick !== mode; });
  }
  document.querySelectorAll('#manualPick, #ddlPick').forEach(pick => pick.addEventListener('click', ev => { const b = ev.target.closest('[data-pick-mode]'); if (b) showPick(pick, b.dataset.pickMode); }));
  // 제공 문서 한 개(같은 출처의 samples/<파일>)를 한 번 읽어 둔다: blob(올릴 때 보내는 바이트 그대로) · text · title(파일 머리의 첫 제목 줄) ·
  // view(새 탭에서 글로 열리는 주소 — 서버는 이 파일을 내려받는 형식으로 주므로 화면이 글 형식으로 다시 싼다)
  function sample(file) {
    if (!H.samples.has(file)) H.samples.set(file, (async () => {
      const res = await fetch('samples/' + encodeURIComponent(file), { cache: 'no-cache' });
      if (!res.ok) throw new Error(`제공 문서 「${file}」를 읽지 못했습니다(HTTP ${res.status}).`);
      const blob = await res.blob(), text = await blob.text();
      return { blob, text, title: (text.match(/^#\s+(.+)$/m) || [])[1] || '', view: URL.createObjectURL(new Blob([blob], { type: 'text/plain;charset=utf-8' })) };
    })().catch(e => { H.samples.delete(file); throw e; }));
    return H.samples.get(file);
  }
  const sampleView = async link => { try { link.href = (await sample(link.dataset.providedView)).view; } catch (_) { /* 못 읽으면 원래 주소(내려받기) 그대로 */ } };
  const toBase64 = blob => new Promise((ok, no) => { const rd = new FileReader(); rd.onload = () => ok(String(rd.result).split(',')[1] || ''); rd.onerror = () => no(new Error('파일을 읽을 수 없습니다.')); rd.readAsDataURL(blob); });
  /* 제공 문서 목록(서버 GET /api/course-access 의 provided_documents — 디자인 기준 5-3). 한 줄의 칸은 모든 줄에서 같은 세로선에 선다:
     고르기 칸(한 번에 적재할 문서) │ 문서 제목 · 아래 파일 이름 │ 상태 알약(「적재됨」 — 제목 칸 바로 오른쪽의 정해진 칸) │ … │ [원문 보기](줄 오른쪽 끝의 글 링크 — 새 탭) │ 꺾쇠.
     줄을 누르면 그 문서를 바로 올린다(적재된 문서는 그 문서의 개정으로) — 목록 위 한 줄과 줄 끝의 꺾쇠가 그것을 말한다 */
  function renderProvided() {
    const box = $('#providedDocs'); if (!box) return;
    const list = hydCourseAccess.access?.provided_documents;
    if (!Array.isArray(list)) { box.innerHTML = hydCourseAccess.error ? UI.errorBlock('제공 문서 목록을 읽지 못했습니다', hydCourseAccess.error, { retry: true }) : UI.loading(''); drawBatch(); return; }
    if (!list.length) { box.innerHTML = UI.empty('제공 문서가 없습니다', '「내 파일 올리기」에서 문서 파일을 골라 올립니다.'); drawBatch(); return; }
    [...H.picked].forEach(f => { if (!list.includes(f)) H.picked.delete(f); });
    const busy = H.sending && H.sending.provided, lock = !!busy || !!(H.batch && H.batch.running);
    box.innerHTML = `<div class="rows doc-prov" data-pickable aria-label="제공 문서">${list.map(f => {
      const loaded = (H.loadedFiles.get(f) || []).length > 0, title = H.sampleTitles.get(f) || '', name = title || f;
      return `<div class="row-act"><label class="doc-pick"><input type="checkbox" class="input" data-batch-pick="${esc(f)}" aria-label="「${esc(name)}」을 한 번에 적재할 문서로 고르기"${H.picked.has(f) ? ' checked' : ''}${lock ? ' disabled' : ''}></label>` +
        `<button type="button" class="row" data-provided="${esc(f)}"${busy === f ? ' aria-current="true"' : ''}${lock ? ' disabled' : ''}><span class="row-title">${esc(name)}</span>` +
        `<span class="doc-state" data-prov-tag>${loaded ? UI.chipText('적재됨', 'success') : ''}</span><span class="row-meta">${esc(title ? f : '')}</span><span class="doc-go" aria-hidden="true">${icon('chevron-right')}</span></button>` +
        `<a class="doc-view" href="samples/${encodeURIComponent(f)}" target="_blank" rel="noopener" data-provided-view="${esc(f)}">원문 보기</a></div>`;
    }).join('')}</div>`;
    box.querySelectorAll('[data-provided-view]').forEach(sampleView);
    drawBatch();
    // 제목은 파일을 읽은 뒤에 채운다(문서 등록 화면이 열려 있을 때만 읽는다)
    if (state.tab === 'knowledge') list.filter(f => !H.sampleTitles.has(f)).forEach(f => {
      H.sampleTitles.set(f, '');
      sample(f).then(s => { if (s.title) { H.sampleTitles.set(f, s.title); renderProvided(); } }, () => H.sampleTitles.delete(f));
    });
  }
  $('#providedDocs').addEventListener('change', ev => {
    const c = ev.target.closest('[data-batch-pick]'); if (!c) return;
    if (c.checked) H.picked.add(c.dataset.batchPick); else H.picked.delete(c.dataset.batchPick);
    drawBatch();
  });
  $('#providedDocs').addEventListener('click', async ev => {
    if (ev.target.closest('[data-retry]')) { hydCourseAccess.refresh(); return; }
    const row = ev.target.closest('[data-provided]'); if (!row || H.sending || (H.batch && H.batch.running)) return;
    const file = row.dataset.provided, mine = H.sending = { provided: file };
    renderProvided();
    let got;
    try { got = await sample(file); }
    catch (e) { if (H.sending === mine) { H.sending = null; renderProvided(); $('#manualResult').innerHTML = `<div class="panel-sec">${UI.errorBlock('문서를 올리지 못했습니다', e.message)}</div>`; } return; }
    if (H.sending !== mine) return;
    // 이미 적재된 제공 문서는 그 문서의 개정으로 올린다(적재한 문서의 [이 문서 개정]과 같다). 같은 이름으로 적재된 문서가 둘 이상이면 고르지 않고 새 문서로 올린다 —
    // 서버가 같은 원문이 적재된 문서를 알려 주고 화면이 [이 문서 개정]을 낸다
    const docs = H.loadedFiles.get(file) || [];
    await uploadManual(file, got.blob, docs.length === 1 ? docs[0] : null, mine);
  });

  /* ---- 한 번에 적재(검토 없이) — 본: process-gpt-vue3 KbUploadZone(「n / 전체 접수 · 실패 n」과 문서별 상태). 서버 주소는 한 편씩 올릴 때와 같다(preview · extractions · changes · commit).
     고른 제공 문서마다 차례로: 올리기 → AI 추출(끝날 때까지 1.5초마다 묻는다 — 지금 읽는 구간이 줄에 흐른다) → 검토가 필요한지 판정 → 적재.
     적재하지 않고 「검토 필요」로 멈추는 때: 자동 검증이 통과하지 못했다 · 고장 유형이 정해지지 않은 조치 방법이 있다 · 손대지 않은 칸으로는 적재 요청을 만들 수 없다(commitRequest 가 멈춤) ·
     개정으로 이전 판의 항목이 빠진다(사람이 확인할 일). 멈춘 문서는 [검토 열기]로 그 문서의 AI 추출 결과를 검토 단계에 연다.
     H.batch = { running, items: [{ file, title, state('todo' | 'now' | 'done' | 'mine' | 'fail'), sub, preview, sent }] } */
  const BATCH_WAITING = ['TODO', 'IN_PROGRESS', 'SUBMITTED'];
  function batchNeedsReview(r) {
    const v = r.validation;
    if (!(r.sections || []).length || !(r.procedures || []).length) return 'AI 추출 결과에 매뉴얼 절이나 조치 방법이 없습니다.';
    if (!v || v.checked !== true || !Array.isArray(v.issues)) return '자동 검증 결과가 없어 사람이 원문과 대조해야 합니다.';
    if (v.technical_ready !== true) return `자동 검증이 「검토 필요 ${v.issues.length}건」을 냈습니다.`;
    if (r.procedures.some(p => needsLink(r, p))) return '고장 유형이 정해지지 않은 조치 방법이 있습니다.';
    return '';
  }
  function drawBatch() {
    const box = $('#manualBatch'); if (!box) return;
    const B = H.batch, n = H.picked.size;
    if (!B) {
      box.innerHTML = n ? `<footer class="form-foot doc-batch-bar"><span class="muted">검토 없이 적재합니다. AI 추출 결과에 사람이 확인할 곳이 있는 문서는 적재하지 않고 멈춥니다.</span>` +
        `<button type="button" class="btn" id="manualBatchRun">${icon('layers')}고른 ${n}개 한 번에 적재</button></footer>` : '';
      return;
    }
    const count = st => B.items.filter(it => it.state === st).length, done = count('done'), need = count('mine'), failed = count('fail'), ended = done + need + failed;
    const items = B.items.map(it => ({ state: it.state, busy: it.state === 'now', name: it.title, sub: it.sub,
      body: it.state === 'mine' && it.preview ? `<button type="button" class="btn" data-variant="outline" data-size="sm" data-batch-review="${esc(it.file)}"${B.running ? ' disabled' : ''}>검토 열기</button>` : '' }));
    box.innerHTML = `<section class="doc-batch" aria-label="한 번에 적재" aria-live="polite"><div class="doc-batch-head"><b class="num">${ended} / ${B.items.length} 처리</b>` +
      `<span class="muted">적재 ${done}${need ? ` · 검토 필요 ${need}` : ''}${failed ? ` · 실패 ${failed}` : ''}</span></div>${UI.progress(ended, B.items.length, { label: '한 번에 적재' })}${UI.timeline(items)}` +
      (B.running ? '' : `<footer class="form-foot doc-next"><button type="button" class="btn" data-variant="outline" id="manualBatchClose">닫기</button>${done ? UI.goLink('ontology', '지식 지도에서 보기') + UI.goLink('scenario', '결함 시뮬레이션으로') : ''}</footer>`) + `</section>`;
  }
  async function runBatch() {
    const by = manualActor(), files = [...H.picked];
    if (!files.length || H.sending || (H.batch && H.batch.running)) return;
    if (!by) { $('#manualBatch').insertAdjacentHTML('beforeend', UI.errorBlock('적재를 시작하지 못했습니다', '담당자 정보를 읽지 못했습니다. 화면을 새로 고친 뒤 다시 해 주세요.')); return; }
    const B = H.batch = { running: true, items: files.map(f => ({ file: f, title: H.sampleTitles.get(f) || f, state: 'todo', sub: '', preview: null, sent: null })) };
    const say = (it, state, sub) => { it.state = state; it.sub = sub; if (H.batch === B) drawBatch(); };
    renderProvided();
    for (const it of B.items) {
      try {
        say(it, 'now', '올리는 중');
        const got = await sample(it.file), data = await toBase64(got.blob);
        if (!H.catalog) H.catalog = await getJ(API.process + '/api/kg/catalog');
        const docs = H.loadedFiles.get(it.file) || [];
        let r = await postJ(API.process + '/api/kg/manuals/preview', { filename: it.file, data, document_id: docs.length === 1 ? docs[0] : null });
        it.preview = r; it.sent = { name: it.file, blob: got.blob, source_id: r.source_id };
        if (r.status !== 'READY') { say(it, 'mine', `검토 필요 — 문서가 「${UI.status(r.status)}」 상태라 AI 추출을 시작할 수 없습니다.`); continue; }
        if (!r.loaded && r.same_original) { say(it, 'mine', `검토 필요 — 같은 원문이 문서 「${r.same_original.filename || ''}」로 이미 적재돼 있습니다. 그 문서의 개정으로 여세요.`); continue; }
        say(it, 'now', 'AI 추출을 요청하는 중');
        const url = API.process + '/api/kg/manuals/sources/' + encodeURIComponent(r.source_id) + '/extractions';
        const created = await postJ(url, { request_id: UI.uuid() });
        let result;
        for (;;) {
          result = await getJ(url + '/' + encodeURIComponent(created.instance));
          if (result.preview || !BATCH_WAITING.includes(result.status)) break;
          const p = result.progress;
          say(it, 'now', result.cache ? 'AI 추출 — 저장된 추출 결과를 불러오는 중' : p && p.total > 1 ? `AI 추출 — 구간 ${p.total}개 가운데 ${p.done}개를 읽었습니다` : 'AI 추출 — AI가 문서를 읽는 중');
          await new Promise(ok => setTimeout(ok, 1500));
        }
        if (!result.preview) { say(it, 'mine', `검토 필요 — AI 추출이 끝나지 않았습니다(${UI.status(result.status)}).`); continue; }
        r = it.preview = result.preview;
        await loadManualCatalog();
        const why = batchNeedsReview(r);
        if (why) { say(it, 'mine', '검토 필요 — ' + why); continue; }
        const built = commitRequest(r, untouched(r), [], by);
        if (built.stop) { say(it, 'mine', '검토 필요 — ' + built.stop); continue; }
        if (built.request.previous_batch) {
          say(it, 'now', '개정으로 빠지는 항목을 확인하는 중');
          const changes = await postJ(API.process + '/api/kg/manuals/changes', built.request);
          if ((changes.removed || []).length) { say(it, 'mine', `검토 필요 — 개정하면 이전 판의 항목 ${changes.removed.length}개가 지식 지도에서 빠집니다.`); continue; }
        }
        say(it, 'now', `지식 지도에 적재하는 중 — 매뉴얼 절 ${r.sections.length}개 · 조치 방법 ${r.procedures.length}개`);
        const out = await postJ(API.process + '/api/kg/manuals/commit', built.request);
        say(it, 'done', `적재 완료 — 절 ${out.sections} · 조치 방법 ${out.procedures} · 단계 ${out.steps}`);
      } catch (e) { say(it, 'fail', '실패 — ' + e.message); }
    }
    B.running = false; H.picked.clear(); H.skills = [];
    await loadUploads(); if (window.hydEnt) hydEnt.loadGraph(true);
    if (H.batch === B) renderProvided();
  }
  $('#manualBatch').addEventListener('click', ev => {
    if (ev.target.closest('#manualBatchRun')) { runBatch(); return; }
    if (ev.target.closest('#manualBatchClose')) { H.batch = null; renderProvided(); return; }
    const b = ev.target.closest('[data-batch-review]'); if (!b) return;
    const it = H.batch && H.batch.items.find(x => x.file === b.dataset.batchReview); if (!it || !it.preview) return;
    // 멈춘 문서의 AI 추출 결과를 검토 단계에 연다 — 한 편씩 올렸을 때와 같은 화면이다
    H.preview = it.preview; H.commit = null; H.sent = it.sent;
    selectManualDocument(it.preview.document_id, it.preview.filename); renderPreview();
    $('#manualUpload').scrollIntoView({ block: 'start' });
  });
  // 올리기 요청 하나 — 내 파일이든 제공 문서든 같다: POST /api/kg/manuals/preview { filename, data(base64), document_id }
  async function uploadManual(name, blob, documentId, mine = {}) {
    H.sending = mine;
    const end = hydLive.busy($('#manualPreview'), '올리는 중'); H.preview = null; H.commit = null; H.sent = null; H.trail = null;
    renderManualSteps(1, { busy: true }); renderProvided();
    $('#manualResult').innerHTML = `<div class="panel-sec">${hydLive.waitHtml('문서를 올리는 중', { hint: '서버가 파일을 받아 글자를 읽고 원문을 보관하는 중입니다. PDF는 쪽 수만큼 더 걸립니다.' })}</div>`;
    note($('#manualStatus'), '');
    try {
      const b64 = await toBase64(blob);
      if (!H.catalog) H.catalog = await getJ(API.process + '/api/kg/catalog');
      await loadManualCatalog();
      const preview = await postJ(API.process + '/api/kg/manuals/preview', { filename: name, data: b64, document_id: documentId || null });
      if (H.sending !== mine) return;
      H.sent = { name, blob, source_id: preview.source_id };
      H.preview = preview; selectManualDocument(preview.document_id, preview.filename); renderPreview();
      loadUploads();
    } catch (e) { if (H.sending === mine) { renderManualSteps(1); $('#manualResult').innerHTML = `<div class="panel-sec">${UI.errorBlock('문서를 올리지 못했습니다', e.message)}</div>`; } }
    finally { end(false); if (H.sending === mine) H.sending = null; renderProvided(); }
  }
  $('#manualPreview').addEventListener('click', () => {
    const f = $('#manualFile').files[0]; if (!f) { note($('#manualStatus'), '올릴 파일을 먼저 선택하세요.', true); return; }
    uploadManual(f.name, f, $('#manualDocumentId').value.trim());
  });
  // 사용 범위(서버 GET /api/course-access): 지금 단계에서는 제공 문서만 올릴 수 있다 — 미리 안내하지 않고 다른 문서를 올리면 서버가 거절한 까닭을
  // 그 자리에 보인다(안내는 벗어난 행동에서만). 질문 확인 단추는 서버가 준 까닭으로 끈다
  function courseScope() { renderProvided(); hydCourseAccess.apply($('#manualHistory')); }
  hydCourseAccess.onChange(courseScope); courseScope();   // 표가 먼저 와 있었으면 바로 그린다
  $('#manualFile').addEventListener('change', () => {
    H.preview = null; H.commit = null; H.sending = null;      // 올리는 중에 다른 파일을 고르면 앞 요청의 응답은 버린다
    const name = $('#manualFile').files[0]?.name;
    // 앞 문서의 「문서 개정」 선택이 다른 파일에 남으면 그 파일이 앞 문서의 개정으로 올라가 앞 문서 지식이 지워진다
    // (2026-10-29 실측: HM-8 다음 HI-01). 등록된 문서의 개정이 골라져 있을 때 이름이 다른 파일을 고르면 새 문서 등록으로
    // 되돌린다. 아직 등록하지 않은 검토 중인 원문은 다음 파일도 같은 문서로 이어 올린다.
    const select = $('#manualDocumentId');
    const registered = select?.value ? H.manualDocuments?.get(select.value) : null;
    if (registered && registered.filename !== name) select.value = '';
    $('#manualFilename').textContent = name || UI.t('kn.noFile'); renderPreview();
  });

  /* ================================================= 업무 DB 표 정의 연결 (DDL → System · InputData, 되돌리기 가능)
     단계: 올리기 → 표와 열 고르기 → 적재. 표 정의를 올리면 표마다 출처 시스템과 판단 입력으로 쓸 열을 고르고, 적재하면 지식 지도에 시스템 · 입력 데이터로 들어간다 */
  const DDL_PHASES = ['올리기', '표와 열 고르기', '적재'];
  function renderDdlSteps(stage, o = {}) { $('#ddlUpload').dataset.stage = String(o.done ? 4 : stage); phaseRow($('#ddlSteps'), DDL_PHASES, stage, o); $('#ddlPick').hidden = stage !== 1; }
  // msg: 이력 위 알림 줄(되돌리기 결과) — 이력을 다시 그리면 그 줄도 새로 만들어지므로 그릴 때 함께 넣는다(한바퀴3: 결과 문장이 바로 지워졌다)
  async function loadIngests(msg = '') {
    const box = $('#ddlHistory'); if (!box) return;
    const line = `<p id="ddlHistoryMsg" class="muted" role="status">${esc(msg)}</p>`;
    try {
      const rows = await getJ(API.process + '/api/kg/ingests');
      const batches = {};
      rows.forEach(r => { (batches[r.batch] = batches[r.batch] || []).push(r); });
      const keys = Object.keys(batches);
      // 제공 예시 줄의 「적재됨」: 이 목록에 그 파일로 넣은 연결이 남아 있을 때
      document.querySelectorAll('#providedDdl [data-provided]').forEach(row => { row.querySelector('[data-prov-tag]').innerHTML = rows.some(r => r.source === row.dataset.provided) ? UI.chipText('적재됨', 'success') : ''; });
      // 적재한 표 정의: 줄마다 스키마 파일 · 넣은 항목 · 더 보기(되돌리기). 연결 번호 같은 식별자는 첫 화면에 두지 않는다
      box.innerHTML = `<div class="sec-head"><h2>적재한 표 정의</h2><span class="muted num">${keys.length ? keys.length + '건' : ''}</span></div>` + (keys.length
        ? `<div class="rows doc-loaded" aria-label="적재한 표 정의">${keys.map((k, i) => `<div class="row-act"><div class="row" data-static data-batch="${esc(k)}"><span class="row-ic">${icon('database')}</span><span class="row-title">${esc((batches[k][0] || {}).source || '')}</span>` +
            `<span class="row-meta">${batches[k].map(r => `${esc(LABEL_KO[r.label] || r.label)} ${r.nodes}`).join(' · ')}</span></div>${UI.moreMenu('ddlMore' + i, [{ label: '되돌리기', icon: 'rotate-ccw', attrs: `data-clear="${esc(k)}"` }])}</div>`).join('')}</div>`
        : UI.empty('아직 적재한 표 정의가 없습니다', '표 정의를 올려 표와 열을 고르고 적재하면 여기에 생깁니다.')) + line;
    } catch (e) { box.innerHTML = line + UI.errorBlock('적재한 표 정의 목록을 읽지 못했습니다', e.message, { retry: true }); }
  }
  $('#ddlHistory').addEventListener('click', async ev => {
    if (ev.target.closest('[data-retry]')) { loadIngests(); return; }
    const b = ev.target.closest('[data-clear]'); if (!b) return;
    if (!await UI.confirm({ title: '이 표 정의를 되돌릴까요?', body: '이 표 정의 파일로 넣은 시스템 · 입력 데이터를 지식 지도에서 지웁니다. 다른 표 정의가 함께 쓰는 항목은 남습니다.', ok: '되돌리기', danger: true })) return;
    note($('#ddlHistoryMsg'), '되돌리는 중입니다.');
    try { const out = await postJ(API.process + '/api/kg/ingests/' + encodeURIComponent(b.dataset.clear) + '?by=' + encodeURIComponent(manualActor()), null, 'DELETE'); await loadIngests(`되돌렸습니다. 지운 항목 ${out.deleted}개 · 되살린 항목 ${out.restored || 0}개 · 남긴 항목 ${out.retained || 0}개`); if (window.hydEnt) hydEnt.loadGraph(true); }
    catch (e) { note($('#ddlHistoryMsg'), '되돌리지 못했습니다: ' + e.message, true); }
  });
  function renderDdlPreview() {
    const p = H.ddl; const box = $('#ddlResult');
    renderDdlSteps(!p ? 1 : H.ddlDone === p ? 3 : 2, { done: !!p && H.ddlDone === p });
    if (!p) { box.innerHTML = ''; return; }
    note($('#ddlStatus'), '');
    const existing = (p.existingSystems || []).map(s => s.id);
    const sysName = id => [...(p.existingSystems || []), ...p.systems].find(s => s.id === id && s.name && s.name !== id)?.name || hydWords.system(id);      // 응답에 이름이 있으면 그것, 없으면 시스템 이름 사전(plainWords.js)
    const sysOptions = sel => [...new Set([...existing, ...p.systems.map(s => s.id), sel].filter(Boolean))].map(id => `<option value="${esc(id)}" title="${esc(id)}" ${id === sel ? 'selected' : ''}>${esc(sysName(id))}</option>`).join('');
    box.innerHTML = `<div class="mprev" data-doc-stage="2">
      <div class="panel-sec"><div class="result"><div class="result-label">올린 표 정의</div><div class="result-main">${esc(p.filename)} <span class="muted num">${Number(p.chars).toLocaleString()}자</span></div>
        <p class="result-sub">표 ${p.tables.length}개를 읽었습니다. 표마다 출처 시스템과 판단 입력으로 쓸 열을 고른 뒤 적재합니다.</p></div>
        ${p.warnings.length ? `<div class="alert" data-ddl-warnings>${icon('info')}<h2>확인할 것 ${p.warnings.length}건</h2><section><ul class="doc-issues">${p.warnings.map(w => `<li>${esc(w)}</li>`).join('')}</ul></section></div>` : ''}</div>
      <div class="panel-sec"><h3>표 → 출처 시스템<span class="muted num">${p.tables.length}</span></h3><div class="ddl-tables">${p.tables.map(t => `<div class="ddl-table"><p class="ddl-name"><b class="mono">${esc(t.table)}</b>${t.comment ? `<span class="muted">${esc(t.comment)}</span>` : ''}</p>
        ${UI.field({ label: '출처 시스템', input: `<select data-sys="${esc(t.table)}"><option value="">(없음 · 적재 안 함)</option>${sysOptions(t.system)}</select>` })}
        <div class="ddl-cols" role="group" aria-label="${esc(t.table)}의 열">${t.columns.map(c => `<label><input type="checkbox" class="input" data-col="${esc(t.table)}" value="${esc(c)}" ${t.selected.includes(c) ? 'checked' : ''}><span class="mono">${esc(c)}</span></label>`).join('')}</div></div>`).join('')}</div></div>
      <div class="panel-sec"><h3>입력 데이터와 실제 위치<span class="muted num">${p.inputs.length}</span></h3>${UI.field({ label: '원천 연결', input: `<select id="ddlSource">${(p.sourceOptions || []).map(o => `<option value="${esc(o.id)}" ${o.id === p.datasource ? 'selected' : ''}>${esc(o.label)} (${esc(o.schema)} 스키마)</option>`).join('')}</select>`,
        hint: (p.sourceNotes || []).join(' ') || '고른 원천의 표 · 열로 잇습니다' })}
        ${p.inputs.length ? table('<th>이름</th><th>데이터 형식</th><th>스키마 · 표 · 열</th><th>업무 시스템</th>', p.inputs.map(i => `<tr><td>${esc(i.name)}</td><td>${esc(i.typeRef)}</td><td class="mono">${esc(i.schema)}.${esc(i.table)}.${esc(i.column)}</td><td title="${esc(i.system)}">${esc(sysName(i.system))}</td></tr>`).join(''))
          : UI.empty('고른 열이 없습니다', '위에서 출처 시스템과 열을 고르고 [고른 열로 다시 읽기]를 누르세요.')}
        ${p.inputs.length ? UI.fold('식별자와 규칙 변수', table('<th>스키마 · 표 · 열</th><th>식별자</th><th>규칙 변수</th>', p.inputs.map(i => `<tr><td class="mono">${esc(i.schema)}.${esc(i.table)}.${esc(i.column)}</td><td><code class="inline">${esc(i.id)}</code></td><td><code class="inline">${esc(i.variable)}</code></td></tr>`).join(''))) : ''}</div>
      <div class="panel-sec pane-fold" id="legacyMeaning"></div>
      <div class="panel-sec"><footer class="form-foot"><span id="ddlMsg" class="muted" role="status"></span><button type="button" class="btn" data-variant="ghost" id="ddlAnother">다른 파일 올리기</button><button type="button" class="btn" data-variant="outline" id="ddlReplan">고른 열로 다시 읽기</button><button type="button" class="btn" id="ddlCommit" ${p.inputs.length && H.ddlDone !== p ? '' : 'disabled'}>${H.ddlDone === p ? '적재 완료' : '적재'}</button></footer><div id="ddlDone"></div></div></div>`;
    const ddlSay = (text, bad = false) => note($('#ddlMsg'), text, bad);
    if (window.hydLegacy) hydLegacy.mount($('#legacyMeaning'), { preview: p, text: H.ddlText, by: () => manualActor(),   // A9 옛 DB 뜻 복원
      replan: async review => { const sel = {}, sys = {}; p.tables.forEach(t => { sel[t.table] = t.selected; if (t.system) sys[t.table] = t.system; });
        H.ddl = await postJ(API.process + '/api/kg/ddl/preview', { filename: p.filename, text: H.ddlText, selection: sel, systems: sys, datasource: p.datasource, catalog: p.catalog, meaning_review: review || undefined }); renderDdlPreview(); } });
    $('#ddlAnother').addEventListener('click', () => { H.ddl = null; H.ddlDone = null; $('#ddlFile').value = ''; $('#ddlFilename').textContent = UI.t('kn.noFile'); renderDdlPreview(); });
    $('#ddlSource').addEventListener('change', async e => {   // 원천을 바꾸면 그 원천의 스키마로 다시 해석한다(서버 ddl_sync.place)
      try { H.ddl = await postJ(API.process + '/api/kg/ddl/preview', { filename: p.filename, text: H.ddlText, datasource: e.target.value, catalog: p.catalog }); renderDdlPreview(); }
      catch (err) { ddlSay('고른 원천으로 다시 읽지 못했습니다: ' + err.message, true); }
    });
    // 열 체크나 출처 시스템을 바꾸면 아래 표(적재할 입력)는 아직 옛 고르기다 — 그대로 [적재]하면 뺀 열이 들어간다. 다시 읽을 때까지 [적재]를 끄고 그 자리에 까닭을 말한다
    box.querySelectorAll('[data-col], [data-sys]').forEach(x => x.addEventListener('change', () => {
      if (H.ddlDone === p) return;
      $('#ddlCommit').disabled = true; ddlSay('고른 열이나 출처 시스템을 바꿨습니다 — [고른 열로 다시 읽기]를 눌러 아래 표를 맞춘 뒤 적재하세요.');
    }));
    $('#ddlReplan').addEventListener('click', async () => {
      const end = hydLive.busy($('#ddlReplan'), '다시 읽는 중');
      const selection = {}, systems = {};
      box.querySelectorAll('[data-sys]').forEach(s => { if (s.value) systems[s.dataset.sys] = s.value; });
      box.querySelectorAll('[data-col]').forEach(c => { if (c.checked && systems[c.dataset.col]) (selection[c.dataset.col] = selection[c.dataset.col] || []).push(c.value); });
      try { H.ddl = await postJ(API.process + '/api/kg/ddl/preview', { filename: p.filename, text: H.ddlText, selection, systems, datasource: p.datasource, catalog: p.catalog, meaning_review: p.meaningReview ? p.meaningReview.id : undefined }); renderDdlPreview(); }
      catch (e) { end(false); ddlSay('고른 열로 다시 읽지 못했습니다: ' + e.message, true); }
    });
    $('#ddlCommit').addEventListener('click', async () => {
      const c = $('#ddlCommit'), end = hydLive.busy(c, '적재하는 중'); ddlSay('');
      renderDdlSteps(3, { busy: true });
      // 적재는 요청 하나다 — 그동안 무엇을 지식 지도에 쓰는지(실제로 보내는 수)를 말하고, 끝나면 쓴 것이 그 줄에 남는다
      const sysN = new Set(p.inputs.map(i => i.system)).size;
      const flow = hydLive.steps($('#ddlDone'), [{ key: 'commit', label: `시스템 ${sysN}개 · 입력 데이터 ${p.inputs.length}개를 지식 지도에 쓰는 중`, hint: '표마다 고른 출처 시스템과 판단 입력으로 쓸 열을 한 번에 넣습니다. 도중에 실패하면 아무것도 들어가지 않습니다.' },
        { key: 'reload', label: '적재한 표 정의 목록과 지식 지도 다시 읽기' }], { label: '적재 단계' });
      flow.start('commit');
      try {
        const out = await postJ(API.process + '/api/kg/ddl/commit', { ...p, by: manualActor() });
        H.ddlDone = p;
        flow.done('commit', { label: '지식 지도에 썼습니다', note: `시스템 ${out.systems}개 · 입력 데이터 ${out.inputs}개` }); flow.start('reload');
        end(true); c.textContent = '적재 완료';
        renderDdlSteps(3, { done: true });
        ddlSay(`적재했습니다. 시스템 ${out.systems}개 · 입력 데이터 ${out.inputs}개. 되돌리려면 아래 「적재한 표 정의」의 더 보기에서 되돌립니다.`);
        await loadIngests(); if (window.hydEnt) hydEnt.loadGraph(true);
        flow.done('reload');
        $('#ddlDone').insertAdjacentHTML('beforeend', `<footer class="form-foot doc-next">${UI.goLink('fabric', '데이터 원천에서 보기')}${UI.goLink('ontology', '지식 지도에서 보기')}</footer>`);
      } catch (e) { end(false); ['commit', 'reload'].forEach(k => { if (flow.state(k) === 'run') flow.fail(k, { note: e.message }); }); renderDdlSteps(2); ddlSay('적재하지 못했습니다: ' + e.message, true); }
    });
  }
  // 표 정의 읽기 요청 하나 — 내 파일이든 제공 예시든 같다: POST /api/kg/ddl/preview { filename, text, catalog }
  async function readDdl(name, text, catalog, row) {
    const mine = H.ddlReading = {}, end = hydLive.busy($('#ddlPreview'), '읽는 중'); H.ddl = null; H.ddlDone = null;
    if (row) { row.disabled = true; row.setAttribute('aria-current', 'true'); }
    renderDdlSteps(1, { busy: true });
    $('#ddlResult').innerHTML = `<div class="panel-sec">${hydLive.waitHtml('표 정의 파일을 읽는 중', { hint: '서버가 표 · 열을 읽고 고른 원천의 실제 표와 맞춰 보는 중입니다.' })}</div>`;
    note($('#ddlStatus'), '');
    try {
      const body = await text();
      const preview = await postJ(API.process + '/api/kg/ddl/preview', { filename: name, text: body, catalog });
      if (H.ddlReading !== mine) return;
      H.ddlText = body; H.ddl = preview; renderDdlPreview(); await loadIngests();
    } catch (e) { if (H.ddlReading === mine) { renderDdlSteps(1); $('#ddlResult').innerHTML = `<div class="panel-sec">${UI.errorBlock('표 정의 파일을 읽지 못했습니다', e.message)}</div>`; } }
    finally { end(false); if (row) { row.disabled = false; row.removeAttribute('aria-current'); } }
  }
  $('#ddlPreview').addEventListener('click', () => {
    const f = $('#ddlFile').files[0]; if (!f) { note($('#ddlStatus'), '표 정의 파일을 먼저 선택하세요.', true); return; }
    readDdl(f.name, () => f.text(), $('#ddlCatalog').value.trim());
  });
  // 제공 예시: 줄을 누르면 화면이 samples/<파일>을 읽어 바로 표와 열 고르기로 간다. 데이터베이스 이름은 「내 파일 올리기」 칸의 처음 값(예시가 맞춰진 값)이다
  $('#providedDdl').addEventListener('click', ev => {
    const row = ev.target.closest('[data-provided]'); if (!row || row.disabled) return;
    readDdl(row.dataset.provided, async () => (await sample(row.dataset.provided)).text, $('#ddlCatalog').defaultValue, row);
  });
  $('#ddlFile').addEventListener('change', () => { H.ddl = null; H.ddlDone = null; H.ddlReading = null; $('#ddlFilename').textContent = $('#ddlFile').files[0]?.name || UI.t('kn.noFile'); renderDdlPreview(); });
  $('#ddlCatalog').addEventListener('input', () => { H.ddl = null; H.ddlDone = null; H.ddlReading = null; renderDdlPreview(); });

  renderManualSteps(1); renderDdlSteps(1); showDocKind('manual');
  /* ------------------------------------------------ tab hooks */
  hydTabs.onShow(name => {
    if (name === 'skills') loadSkills();
    if (name === 'knowledge') { loadUploads(); loadIngests(); renderProvided(); document.querySelectorAll('#providedDdl [data-provided-view]').forEach(sampleView); }
  });
})();
