/* B3 흐름 가져오기 — bpmn.io 에서 그린 .bpmn → task 별 부품 · 담당 → 시작 조건 → 분기 조건 → 사전 검사 → 판본 등록.
   window.hydFlows.mount(el) 이 그린다(셸 MOUNTS.flows). UI 는 돌아갈 만큼만(다듬기는 실라버스 뒤).
   API: procsvc/flows_api.py (/api/flows/catalog · import · {id} · {id}/mapping · {id}/check · {id}/register ·
        {id}/versions/{v}/bpmn · reset), 직접 시작은 기존 POST /api/instances/start.
   원본 대조: process-gpt-vue3 ProcessGPTBackend.ts:573-685(proc_def.bpmn · 판본 snapshot) — 화면 모델러는 만들지 않는다(DECISIONS 110 ②). */
(function () {
  // ---------------------------------------------------------------- 순수 함수 (DOM 없이 시험 — tests/test_bpmn_import.py)
  const TYPES = ['text', 'textarea', 'number', 'integer', 'boolean', 'select', 'object', 'array'];
  const TYPE_LABEL = { text: '글', textarea: '긴 글', number: '숫자', integer: '정수', boolean: '예/아니요', select: '고르기', object: '묶음(JSON)', array: '목록(JSON)' };
  // "값이름 | 표시 이름 | 종류 | 고를 값(쉼표)" 한 줄에 칸 하나. 틀리면 Error(몇 번째 줄인지).
  function parseFields(text) {
    const out = [];
    String(text || '').split('\n').map(s => s.trim()).filter(Boolean).forEach((line, i) => {
      const [key, label, type, items] = line.split('|').map(s => (s || '').trim());
      const kind = type || 'text';
      if (!key) throw new Error(`${i + 1}번째 줄: 값 이름이 비었습니다`);
      if (!TYPES.includes(kind)) throw new Error(`${i + 1}번째 줄: 종류 '${kind}'는 쓸 수 없습니다 (${TYPES.join(', ')})`);
      const f = { key, text: label || key, type: kind };
      if (kind === 'select') {
        f.items = String(items || '').split(',').map(s => s.trim()).filter(Boolean);
        if (!f.items.length) throw new Error(`${i + 1}번째 줄: 고르기 칸에는 고를 값을 쉼표로 적으세요`);
      }
      out.push(f);
    });
    return out;
  }
  function fieldsText(fields) {
    return (fields || []).map(f => [f.key, f.text && f.text !== f.key ? f.text : '', f.type && f.type !== 'text' ? f.type : '', (f.items || []).join(',')]
      .join(' | ').replace(/( \| )+$/, '')).join('\n');
  }
  // 분기 기준 칸의 글 → 값: 예/아니요 · 숫자는 그 값, 나머지는 글.
  function parseValue(raw) {
    const t = String(raw ?? '').trim();
    if (t === '예' || t === 'true' || t === 'True') return true;
    if (t === '아니요' || t === 'false' || t === 'False') return false;
    if (t !== '' && isFinite(Number(t))) return Number(t);
    return t;
  }
  const minutesOf = iso => { const m = /^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$/.exec(String(iso || '')); return m ? (+(m[1] || 0)) * 60 + (+(m[2] || 0)) + (+(m[3] || 0)) / 60 : null; };
  const isoOf = minutes => { const n = Number(minutes); return isFinite(n) && n > 0 ? (Number.isInteger(n) ? `PT${n}M` : `PT${Math.round(n * 60)}S`) : ''; };
  const CONFIG = {
    server: ['연결 서버', 'text'], tool: ['실행할 도구', 'text'], arguments: ['도구에 보낼 값', 'object'],
    output: ['결과를 담을 값 이름', 'text'], extract: ['결과에서 꺼낼 값', 'object'], effect: ['호출 목적', 'boolean'],
    duration: ['기다릴 시간', 'text'], until: ['기다릴 시각이 담긴 값', 'text'], label: ['대기 중 표시할 이름', 'text'],
    outcome: ['처리 결과', 'outcome'], title: ['보고 제목', 'text'], summary: ['보고 내용', 'textarea'], notify: ['추가 보고 대상', 'array'],
    mail: ['공지 메일', 'object'], component: ['정비할 부품', 'component'], sop: ['조치 방법', 'text'],
    work_order_var: ['정비 요청이 담긴 값', 'text'], purchase_order_var: ['발주가 담긴 값', 'text'],
    immediate: ['바로 입고 처리', 'boolean'], criteria: ['확인 기준', 'object'], settle: ['안정될 때까지 기다릴 시간', 'text'],
    reset_counter: ['통과하면 운전시간 초기화', 'boolean'], window_var: ['정비 예정 시간이 담긴 값', 'text']
  };
  function configValue(key, raw) {
    if (raw.trim() === '') return undefined;
    const [label, type] = CONFIG[key] || [key, 'text'];
    if (type === 'boolean') { if (!['true', 'false'].includes(raw)) throw Error(`${label}: 예 또는 아니요를 고르세요`); return raw === 'true'; }
    if (type === 'object' || type === 'array') {
      let value; try { value = JSON.parse(raw); } catch (_) { throw Error(`${label}: 입력한 묶음의 문법을 확인하세요`); }
      if (type === 'array') { if (!Array.isArray(value)) throw Error(`${label}: 대괄호로 묶은 목록을 넣으세요`); return value; }
      if (!value || Array.isArray(value) || typeof value !== 'object') throw Error(`${label}: 이름과 값으로 된 묶음을 넣으세요`);
      return value;
    }
    return raw.trim();
  }
  const pure = { parseFields, fieldsText, parseValue, minutesOf, isoOf, configValue };

  if (typeof document === 'undefined') { window.hydFlows = { pure }; return; }

  // ---------------------------------------------------------------- 화면
  const S = { el: null, cat: null, view: null, mapping: null, list: null, busy: false, timer: null, result: null };
  const api = p => API.process + p;
  const h = s => esc(s);
  // 공용 요청 함수 하나(requestJ) — 고칠 곳 목록(problems)은 서버 사유 칸(error.detail)에서 꺼낸다
  async function call(method, path, body) {
    try {
      return await requestJ(api(path), { ...(method === 'GET' ? {} : { method }), ...(body ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {}) });
    } catch (e) { e.problems = (e.detail && e.detail.problems) || null; throw e; }
  }
  // 두 번 누름 방지: 요청이 끝날 때까지 그 버튼을 잠그고 같은 동작을 다시 보내지 않는다
  const locks = new Set();
  async function once(name, button, fn) {
    if (locks.has(name)) return;
    locks.add(name); const was = button ? button.disabled : false; if (button) button.disabled = true;
    try { return await fn(); } finally { locks.delete(name); if (button && button.isConnected) button.disabled = was; }
  }
  const partName = p => p ? ({ human: '담당자 입력', agent: '에이전트 작업' }[p.key] || UI.flowName(p.name)) : '';
  const roleOpts = (sel, human) => S.cat.roles.filter(r => !human || r.human).map(r => `<option value="${h(r.name)}" ${r.name === sel ? 'selected' : ''}>${h(r.name)}</option>`).join('');
  const agentOpts = sel => S.cat.agents.map(a => `<option value="${h(a.id)}" ${a.id === sel ? 'selected' : ''}>${h(a.name && a.name !== a.id ? a.name : UI.who(a.id) !== a.id ? UI.who(a.id) : 'AI 에이전트')}</option>`).join('');
  const nodeName = id => { const p = S.view && S.view.parsed; if (!p) return id; for (const k of ['tasks', 'starts', 'ends', 'boundaries', 'gateways']) { const n = p[k].find(x => x.id === id); if (n) return n.name || '(이름 없음)'; } return id; };

  function mount(el) {
    S.el = el;
    el.innerHTML = `
      <section class="card form" aria-label="그림 가져오기">
        <header class="card-head"><div class="card-title"><h3>그림 가져오기</h3></div></header>
        <p class="field-hint">제공된 교대 인수인계 흐름을 demo.bpmn.io 에서 열어 고친 뒤 왼쪽 아래 <b>Download BPMN diagram</b> 으로 받은 .bpmn 파일을 고릅니다. 수업에서는 이 흐름만 등록됩니다. 같은 흐름 id 로 다시 가져오면 앞서 고른 매핑이 남습니다.</p>
        <div class="form-grid">
          ${UI.field({ label: '.bpmn 파일', input: '<input type="file" id="flowFile" accept=".bpmn,.xml,application/xml,text/xml">', required: true })}
          ${UI.field({ label: '흐름 id (비우면 그림의 프로세스 id)', input: '<input id="flowId" placeholder="예: oil_check" autocomplete="off">', hint: ' ' })}
        </div>
        <div class="form-actions"><span class="form-msg" id="flowImportMsg" role="status"></span><button class="btn primary" id="flowImport">가져오기</button></div>
      </section>
      <div id="flowEditor"></div>
      ${UI.fold('내가 가져온 흐름 · 판본', '<div id="flowList"></div><div class="form-actions"><button class="btn small danger" id="flowReset">기준으로 되돌리기</button></div>', { open: true })}`;
    el.querySelector('#flowImport').addEventListener('click', e => once('import', e.currentTarget, doImport));
    el.querySelector('#flowReset').addEventListener('click', doReset);
    idField();
    return Promise.all([loadCatalog(), loadList()]);
  }
  // 수업 경계(서버 GET /api/course-access 의 importable_flow): 수업 단계에서는 제공 흐름 하나만 가져온다 — 흐름 id 칸을 그 흐름으로 고정해
  // 다른 id 를 적어 거절당하지 않게 한다. PBL(값 null)이면 칸을 연다
  function idField() {
    const input = S.el && S.el.querySelector('#flowId'); if (!input) return;
    const only = hydCourseAccess.access && hydCourseAccess.access.importable_flow;
    input.disabled = !!only; input.value = only ? '' : input.value;
    input.placeholder = only ? `수업 단계: ${only} (그림의 프로세스 id 그대로)` : '예: oil_check';
    const hint = input.closest('.field')?.querySelector('.field-hint');
    if (hint) hint.textContent = only ? hydCourseAccess.importBlocked('') : '';
  }
  hydCourseAccess.onChange(() => { idField(); if (S.list) renderList(); });

  async function loadCatalog() { S.cat = await call('GET', '/api/flows/catalog'); }
  async function loadList() {
    const box = S.el.querySelector('#flowList');
    try { S.list = await call('GET', '/api/flows'); }
    catch (e) { box.innerHTML = UI.errorBlock('목록을 불러오지 못했습니다', e.message); return; }
    renderList();
  }

  async function doImport() {
    const msg = S.el.querySelector('#flowImportMsg');
    const file = S.el.querySelector('#flowFile').files[0];
    if (!file) { msg.textContent = '.bpmn 파일을 고르세요'; msg.className = 'form-msg neg'; return; }
    msg.textContent = '읽는 중…'; msg.className = 'form-msg';
    try {
      const xml = await file.text();
      S.view = await call('POST', '/api/flows/import', { xml, file_name: file.name, start_patterns: [], definition_id: S.el.querySelector('#flowId').value.trim() || null });
      S.mapping = S.view.mapping;
      const r = S.view.reimport || {};
      msg.textContent = r.previous ? `다시 가져옴 — 매핑 유지 ${r.kept.length} · 새 단계 ${r.new.length} · 사라진 단계 ${r.dropped.length}` : `가져옴 — 단계 ${S.view.parsed.tasks.length}개`;
      msg.className = 'form-msg pos';
      renderEditor(); loadList();
    } catch (e) {
      msg.textContent = e.message; msg.className = 'form-msg neg';
      S.el.querySelector('#flowEditor').innerHTML = e.problems ? problemsBlock(e.problems) : '';
    }
  }

  async function openDraft(id) {
    try { S.view = await call('GET', '/api/flows/' + encodeURIComponent(id)); S.mapping = S.view.mapping; renderEditor(); S.el.querySelector('#flowEditor').scrollIntoView({ block: 'start' }); }
    catch (e) { UI.toast(e.message, { tone: 'neg' }); }
  }

  // ------------------------------------------------ 매핑 화면
  function renderEditor() {
    const v = S.view, p = v.parsed, m = S.mapping, box = S.el.querySelector('#flowEditor');
    const lanes = p.lanes.length ? p.lanes.map(l => `<tr><td>${h(l.name || '(이름 없음)')}</td><td><select data-lane="${h(l.id)}"><option value="">(고르지 않음)</option>${roleOpts(m.lanes[l.id] || '', false)}</select></td></tr>`).join('') : '';
    const start = m.start || {};
    const patterns = S.cat.patterns.map(pt => `<label class="chk"><input type="checkbox" data-pattern="${h(pt)}" ${(start.patterns || []).includes(pt) ? 'checked' : ''}> ${h(UI.patternName(pt))}</label>`).join(' ');
    box.innerHTML = `
      <section class="card form" aria-label="매핑">
        <h3>${h(m.name || p.process.name || '가져온 흐름')} <span class="muted">· 다음 판본 ${h(v.next_version)}</span></h3>
        <div class="form-grid">${UI.field({ label: '흐름 이름', input: `<input id="flowName" value="${h(m.name || p.process.name || '')}">` })}
          ${UI.readonly('그림 파일', h(v.file_name || '–'), `단계 ${p.tasks.length} · 분기 ${p.gateways.length} · 선 ${p.flows.length}`)}</div>
        ${UI.section('시작 조건', `
          <div class="field wide"><label class="chk"><input type="radio" name="flowStart" value="alert" ${start.kind === 'alert' ? 'checked' : ''}> 경보로 시작</label>
            <div class="chk-row">${patterns}</div><p class="field-hint">경보 정책(회복 기준)은 기준 흐름의 계약을 그대로 씁니다.</p></div>
          <div class="field wide"><label class="chk"><input type="radio" name="flowStart" value="human" ${start.kind === 'human' ? 'checked' : ''}> 사람 입력 · 직접 시작</label>
            <textarea id="flowStartFields" rows="3" spellcheck="false" placeholder="값이름 | 표시 이름 | 종류 | 고를 값&#10;예) oil_iso | ISO 청정도 | text">${h(fieldsText(start.fields))}</textarea>
            <p class="field-hint">한 줄에 칸 하나. 종류: ${TYPES.map(t => TYPE_LABEL[t] + ' ' + t).join(' · ')}</p></div>`)}
        ${lanes ? UI.section('담당 구역별 역할', `<table class="compact-table"><thead><tr><th>그림의 칸</th><th>역할</th></tr></thead><tbody>${lanes}</tbody></table>`) : ''}
        ${UI.section('단계별 부품 · 담당 · 설정', `<table class="compact-table flow-map"><thead><tr><th>그림의 단계</th><th>부품</th><th>담당</th><th>설정</th></tr></thead><tbody>${p.tasks.map(taskRow).join('')}</tbody></table>`)}
        ${p.boundaries.length ? UI.section('알림 기한', p.boundaries.map(timerRow).join('')) : ''}
        ${branchSection()}
        <div id="flowProblems">${resultBlock(v.check)}</div>
        <div class="form-actions"><span class="form-msg" id="flowMsg" role="status"></span>
          <button class="btn" id="flowCheck">저장 · 검사</button><button class="btn primary" id="flowRegister">판본 등록</button></div>
      </section>`;
    wire(box);
    fieldEditors(box);
  }

  /* A161-U1 (A160 결함 6): "값이름 | 표시 이름 | 종류 | 고를 값" 한 줄 문법을 화면에 보이지 않고, 칸마다 입력 행(값 이름 · 화면 이름 · 종류 · 고를 값)으로 받는다.
     행을 고치면 숨긴 글 칸에 같은 문법으로 다시 써 넣으므로 검사 · 등록(collect → parseFields)은 그대로다. process-gpt-vue3 FormDefinition.vue 의 칸 목록 편집과 같은 모양. */
  function fieldEditors(box) {
    box.querySelectorAll('textarea[data-fields], textarea[data-outputs], #flowStartFields').forEach(ta => {
      if (ta.dataset.rows) return;
      let rows; try { rows = parseFields(ta.value); } catch (_) { return; }      // a hand-written text that does not parse stays as text
      ta.dataset.rows = '1'; ta.hidden = true;
      const ed = document.createElement('div'); ed.className = 'field-rows';
      const sync = () => { ta.value = fieldsText(rows.filter(r => r.key)); ta.dispatchEvent(new Event('input', { bubbles: true })); };
      const draw = () => {
        ed.innerHTML = (rows.length ? `<div class="field-row head"><span>값 이름</span><span>화면 이름</span><span>종류</span><span>고를 값</span><span></span></div>` : '')
          + rows.map((r, i) => `<div class="field-row" data-i="${i}"><input data-k="key" value="${h(r.key)}" placeholder="예) oil_iso" aria-label="값 이름">
            <input data-k="text" value="${h(r.text && r.text !== r.key ? r.text : '')}" placeholder="예) ISO 청정도" aria-label="화면 이름">
            <select data-k="type" aria-label="종류">${TYPES.map(t => `<option value="${t}" ${t === (r.type || 'text') ? 'selected' : ''}>${h(TYPE_LABEL[t] || t)}</option>`).join('')}</select>
            <input data-k="items" value="${h((r.items || []).join(', '))}" placeholder="${r.type === 'select' ? '쉼표로 구분' : '고르기일 때만'}" ${r.type === 'select' ? '' : 'disabled'} aria-label="고를 값">
            <button type="button" class="chip-x" data-del aria-label="칸 빼기" title="칸 빼기">×</button></div>`).join('')
          + `<button type="button" class="btn small ghost" data-add>+ 칸 추가</button>`;
      };
      ed.addEventListener('input', e => {
        const row = e.target.closest('[data-i]'); if (!row) return;
        const r = rows[+row.dataset.i], k = e.target.dataset.k;
        if (k === 'items') r.items = e.target.value.split(',').map(x => x.trim()).filter(Boolean);
        else if (k === 'text') r.text = e.target.value.trim() || r.key; else if (k === 'key') r.key = e.target.value.trim();
        sync();
      });
      ed.addEventListener('change', e => { if (e.target.dataset.k === 'type') { rows[+e.target.closest('[data-i]').dataset.i].type = e.target.value; sync(); draw(); } });
      ed.addEventListener('click', e => {
        if (e.target.closest('[data-add]')) { rows.push({ key: '', text: '', type: 'text' }); draw(); ed.querySelector('.field-row:last-of-type input')?.focus(); }
        const del = e.target.closest('[data-del]'); if (del) { rows.splice(+del.closest('[data-i]').dataset.i, 1); sync(); draw(); }
      });
      draw(); ta.after(ed);
    });
    box.querySelectorAll('.field-hint').forEach(p => { if (/^한 줄에 칸 하나/.test(p.textContent)) p.textContent = '사람이 입력할 칸을 한 줄씩 추가합니다. 고르기 칸은 고를 값을 쉼표로 적습니다.'; });
  }

  function taskRow(t) {
    const m = S.mapping.tasks[t.id] || {};
    const part = S.cat.parts.find(x => x.key === m.part);
    const scen = S.cat.parts.filter(x => x.group === 'scenario' && !(x.effect === '작업지시'));
    const wo = S.cat.parts.find(x => x.effect === '작업지시');
    const opt = x => `<option value="${h(x.key)}" ${x.key === m.part ? 'selected' : ''}>${h(partName(x))}</option>`;
    const sel = `<select data-part="${h(t.id)}"><option value="">(부품 고르기)</option><optgroup label="시나리오 부품">${scen.map(opt).join('')}</optgroup>
      <optgroup label="일반 부품">${S.cat.parts.filter(x => x.group === 'general').map(opt).join('')}${wo ? `<option value="${h(wo.key)}" ${wo.key === m.part ? 'selected' : ''}>정비 요청</option>` : ''}</optgroup></select>`;
    let who = '<span class="muted">–</span>', detail = '';
    if (part && part.kind === 'human') who = `<select data-role="${h(t.id)}"><option value="">${part.group === 'scenario' ? '부품 기본: ' + h(part.role) : '(칸의 역할)'}</option>${roleOpts(m.role || '', true)}</select>`;
    if (part && part.kind === 'agent') who = `<select data-agent="${h(t.id)}">${agentOpts(m.agent || part.agent || (S.cat.agents[0] || {}).id)}</select>`;
    if (part && part.kind === 'service') who = '<span>시스템</span>';
    if (part && part.group === 'scenario') {
      const outs = (part.form && part.form.fields_json || []).map(f => `<code>${h(f.key)}</code>`).join(' ');
      detail = `<details class="flow-contract"><summary>연결 값 보기</summary><p class="kv-line">받는 값 ${part.inputs.map(x => `<code>${h(x)}</code>`).join(' ') || '–'} · 내는 값 ${outs || (part.outputs.map(x => `<code>${h(x)}</code>`).join(' ') || '–')}${part.approval ? ' · <b>사람 승인</b>' : ''}${part.effect ? ` · <b>${h(UI.flowName(part.effect))}</b>(승인 뒤)` : ''}</p></details>`;
    } else if (part && part.key === 'human') {
      detail = `<textarea data-fields="${h(t.id)}" rows="2" spellcheck="false" placeholder="값이름 | 표시 이름 | 종류">${h(fieldsText(m.fields))}</textarea>
        <input data-inputs="${h(t.id)}" value="${h((m.inputs || []).join(', '))}" placeholder="받을 값 (쉼표) — ${h(avail(t.id).join(', '))}">`;
    } else if (part && part.key === 'human:approve') {     // 캡스톤 G1: 고를 안이 든 값 · 구분 칸 · 추천 · 지는 안 · 근거 자료 (part.config 가 칸 설명)
      const cfg = m.config || {};
      detail = Object.entries(part.config).map(([k, hint]) => `<input data-approval="${h(t.id)}" data-cfg="${h(k)}" value="${h(cfg[k] || '')}" placeholder="${h(k)} — ${h(hint)}">`).join('')
        + `<p class="kv-line">받을 수 있는 값 ${avail(t.id).map(x => `<code>${h(x)}</code>`).join(' ') || '–'} · 내는 값 <code>approval</code> <code>approval_reason</code> · <b>사람 승인</b></p>`;
    } else if (part && part.key === 'agent') {
      detail = `<textarea data-instruction="${h(t.id)}" rows="2" placeholder="지시문 — 무엇을 조회 · 계산해 무엇을 낼지">${h(m.instruction || '')}</textarea>
        <textarea data-outputs="${h(t.id)}" rows="2" spellcheck="false" placeholder="결과 값 — 값이름 | 표시 이름 | 종류">${h(fieldsText(m.outputs))}</textarea>
        <input data-inputs="${h(t.id)}" value="${h((m.inputs || []).join(', '))}" placeholder="받을 값 (쉼표) — ${h(avail(t.id).join(', '))}">`;
    }
    if (part?.key === 'task:decide') detail += UI.field({ label: '에이전트 지시문', input: `<textarea data-instruction="${h(t.id)}" rows="3">${h(m.instruction ?? part.contract?.instruction ?? '')}</textarea>` });
    if (part?.config && part.kind === 'service') detail += serviceFields(t, part, m.config || {});
    const lane = (S.view.parsed.lanes.find(l => l.id === t.lane) || {}).name;
    const dependency = ((S.view.check.dependencies || {}).items || []).find(x => x.node_id === t.id);
    if (dependency) detail += dependencyLine(dependency);
    return `<tr data-row="${h(t.id)}"><td data-label="단계"><b>${h(t.name || '(이름 없음)')}</b><br><small class="muted">${h(t.type_label)}${lane ? ' · ' + h(lane) : ''}</small></td><td data-label="부품">${sel}</td><td data-label="담당">${who}</td><td data-label="설정">${detail}</td></tr>`;
  }
  const avail = id => [...new Set(((S.view.check.available || {})[id] || []).map(x => x.value))];
  function serviceFields(task, part, config) {
    return `<div class="flow-service-fields">${Object.keys(part.config).map(key => {
      const [label, type] = CONFIG[key] || [key, 'text'], value = config[key];
      if (key === 'mail' && !config.mail?.arguments && !config.mail?.server && !config.mail?.tool) return `<fieldset class="flow-mail"><legend>공지 메일</legend>${[['to','받는 사람'],['cc','참조'],['subject','메일 제목'],['body','메일 내용']].map(([k,label]) => UI.field({label,input: k === 'body' ? `<textarea data-mail="${h(task.id)}" data-mail-key="${k}" rows="3">${h(config.mail?.[k] ?? '')}</textarea>` : `<input data-mail="${h(task.id)}" data-mail-key="${k}" value="${h(config.mail?.[k] ?? '')}">`})).join('')}</fieldset>`;
      const attrs = `data-service="${h(task.id)}" data-cfg="${h(key)}" aria-label="${h(label)}"`;
      let input;
      if (['boolean', 'outcome', 'component'].includes(type)) {
        const choices = type === 'boolean' ? (key === 'effect' ? [['true', '변경 실행'], ['false', '조회만']] : [['true', '예'], ['false', '아니요']])
          : type === 'component' ? [['cooler', '쿨러'], ['pump', '펌프'], ['fan', '팬']]
          : ['정상', '입고 완료', '미달', '지연', '알림', '승인 지연', '반려'].map(x => [x, x]);
        input = `<select ${attrs}><option value="">기본값 사용</option>${choices.map(([v, name]) => `<option value="${h(v)}" ${String(value) === v ? 'selected' : ''}>${h(name)}</option>`).join('')}</select>`;
      } else if (['object', 'array', 'textarea'].includes(type)) input = `<textarea ${attrs} rows="3" spellcheck="false">${h(value === undefined ? '' : type !== 'textarea' ? JSON.stringify(value, null, 2) : value)}</textarea>`;
      else input = `<input ${attrs} value="${h(value ?? '')}">`;
      return UI.field({ label, input, hint: type === 'object' ? '이름과 값을 중괄호로 묶어 입력합니다. 처리 건 값은 {값 이름}으로 연결합니다.' : ['duration', 'settle'].includes(key) ? '예: PT10M은 10분, PT2H는 2시간입니다.' : '' });
    }).join('')}</div>`;
  }
  // 값 이름 → 사람이 읽는 이름(부품 폼 · 내가 적은 폼 칸의 표시 이름). 없으면 값 이름 그대로.
  function valueLabel(key) {
    const known = { approval: '승인 결과', approval_reason: '거절 사유', recovered: '설비 회복 여부', passed: '확인 통과 여부', received: '입고 확인 여부' };
    if (known[key]) return known[key];
    for (const p of S.cat.parts) for (const f of (p.form && p.form.fields_json) || []) if (f.key === key && f.text) return f.text.split(' (')[0];
    const m = S.mapping || {};
    for (const f of [...((m.start || {}).fields || []), ...Object.values(m.tasks || {}).flatMap(t => [...(t.fields || []), ...(t.outputs || [])])]) if (f.key === key && f.text && f.text !== key) return f.text;
    return '';
  }

  function timerRow(b) {
    const m = S.mapping.timers[b.id];
    const host = S.view.parsed.tasks.find(t => t.id === b.attached_to);
    const part = host && S.cat.parts.find(x => x.key === (S.mapping.tasks[host.id] || {}).part);
    const dflt = b.timer || (part && part.default_timer);
    return `<div class="field" data-row="${h(b.id)}"><label>${h(b.name || '시간 초과')} — ${h(host ? host.name : '')}</label>
      <input type="number" min="0.1" step="any" data-timer="${h(b.id)}" value="${h(m ? minutesOf(m) : '')}" placeholder="${dflt ? '기본 ' + minutesOf(dflt) + '분' : '분'}"><p class="field-hint">분</p></div>`;
  }

  function branchSection() {
    const p = S.view.parsed;
    const rows = p.gateways.filter(g => g.gateway_type === 'exclusiveGateway').map(g => {
      const outs = p.flows.filter(f => f.source === g.id);
      if (outs.length < 2) return '';
      const vals = avail(g.id);
      return `<div class="field wide" data-row="${h(g.id)}"><label>분기 '${h(g.name || '(이름 없음)')}'</label><table class="compact-table"><tbody>${outs.map(f => {
        const c = S.mapping.flows[f.id] || {};
        return `<tr data-row="${h(f.id)}"><td>→ ${h(nodeName(f.target))}${f.name ? `<br><small class="muted">${h(f.name)}</small>` : ''}</td>
          <td><label class="chk"><input type="checkbox" data-default="${h(f.id)}" ${c.default ? 'checked' : ''}> 그 밖의 경우</label></td>
          <td><select data-var="${h(f.id)}" aria-label="분기할 값" ${c.default ? 'disabled' : ''}><option value="">값 선택</option>${vals.map(x => `<option value="${h(x)}" ${x === c.var ? 'selected' : ''}>${h(valueLabel(x) || x)}</option>`).join('')}</select></td>
          <td><select data-op="${h(f.id)}" aria-label="비교 방법" ${c.default ? 'disabled' : ''}>${S.cat.ops.map(o => `<option value="${h(o)}" ${o === (c.op || '==') ? 'selected' : ''}>${h(({ '==': '같음', '!=': '다름', '>': '초과', '>=': '이상', '<': '미만', '<=': '이하' })[o] || o)}</option>`).join('')}</select></td>
          <td>${c.var === 'approval' ? `<select data-value="${h(f.id)}" aria-label="승인 결과" ${c.default ? 'disabled' : ''}><option value="">결과 선택</option>${['승인', '반려'].map(x => `<option ${c.value === x ? 'selected' : ''}>${x}</option>`).join('')}</select>` : `<input data-value="${h(f.id)}" aria-label="비교할 값" value="${h(c.value === undefined ? '' : c.value === true ? '예' : c.value === false ? '아니요' : c.value)}" placeholder="기준 (예/아니요 · 숫자 · 글)" ${c.default ? 'disabled' : ''}>`}</td></tr>`;
      }).join('')}</tbody></table></div>`;
    }).join('');
    return rows ? UI.section('분기 조건 (앞 단계 값 기준)', rows) : '';
  }

  function problemsBlock(problems) {
    if (!problems || !problems.length) return '';
    return `<div class="card flow-problems" role="alert"><b>고칠 곳 ${problems.length}건</b><ul>${problems.map(x => {
      const w = x.where || {};
      return `<li ${w.id ? `data-goto="${h(w.id)}"` : ''}>${w.kind_label ? `<b>${h(w.kind_label)} ${h(w.name || w.id)}</b> — ` : ''}${h(x.reason)}</li>`;
    }).join('')}</ul></div>`;
  }
  function dependencyLine(item) {
    return `<p class="field-hint flow-dependency" role="status">연결 도구 준비 상태: ${h(item.reason)}</p>`;
  }
  function dependenciesBlock(dependencies) {
    if (!dependencies || !dependencies.items || !dependencies.items.length) return '';
    const count = dependencies.attention_count || 0;
    return `<div class="card flow-dependencies" role="status"><b>${count ? `연결 도구 준비가 필요한 단계 ${count}개` : '연결 도구의 저장된 검사 확인'}</b><ul>${dependencies.items.map(item => `<li><b>${h(item.node_name)}</b> — ${h(item.reason)}</li>`).join('')}</ul><p class="field-hint">${h(dependencies.note)}</p><p class="field-hint">구조 검사 통과는 실제 연결을 보장하지 않습니다.</p></div>`;
  }
  const resultBlock = c => (c && c.ok ? `<p class="kv-line pos" role="status">구조 검사 통과 — 판본으로 등록할 수 있습니다. 외부 도구 연결 성공을 뜻하지 않습니다 (운영 배포는 따로).</p>` : problemsBlock(c && c.problems)) + dependenciesBlock(c && c.dependencies);

  function collect() {
    const box = S.el.querySelector('#flowEditor'), m = structuredClone(S.mapping);
    const switched = new Set();
    m.name = box.querySelector('#flowName').value.trim();
    const kind = (box.querySelector('input[name=flowStart]:checked') || {}).value;
    m.start = kind === 'alert' ? { kind, patterns: [...box.querySelectorAll('[data-pattern]')].filter(c => c.checked).map(c => c.dataset.pattern) }
      : kind === 'human' ? { kind, fields: parseFields(box.querySelector('#flowStartFields').value) } : {};
    box.querySelectorAll('[data-lane]').forEach(s => { if (s.value) m.lanes[s.dataset.lane] = s.value; else delete m.lanes[s.dataset.lane]; });
    box.querySelectorAll('[data-part]').forEach(s => {
      const id = s.dataset.part, prev = m.tasks[id] || {};
      if (prev.part !== s.value) switched.add(id);
      m.tasks[id] = s.value ? (prev.part === s.value ? prev : { part: s.value }) : {};
      if (!s.value) delete m.tasks[id];
    });
    const set = (attr, fn) => box.querySelectorAll(`[data-${attr}]`).forEach(x => { const t = m.tasks[x.dataset[attr]]; if (t && !switched.has(x.dataset[attr])) fn(t, x); });
    set('role', (t, x) => { if (x.value) t.role = x.value; else delete t.role; });
    set('agent', (t, x) => { t.agent = x.value; });
    set('fields', (t, x) => { t.fields = parseFields(x.value); });
    set('outputs', (t, x) => { t.outputs = parseFields(x.value); });
    set('instruction', (t, x) => { t.instruction = x.value.trim(); });
    set('inputs', (t, x) => { t.inputs = x.value.split(',').map(s => s.trim()).filter(Boolean); });
    set('approval', (t, x) => { t.config = t.config || {}; if (x.value.trim()) t.config[x.dataset.cfg] = x.value.trim(); else delete t.config[x.dataset.cfg]; });
    set('service', (t, x) => {
      const value = configValue(x.dataset.cfg, x.value);
      t.config = t.config || {};
      if (value === undefined) delete t.config[x.dataset.cfg]; else t.config[x.dataset.cfg] = value;
    });
    set('mail', (t, x) => { t.config ||= {}; t.config.mail ||= {}; if (x.value.trim()) t.config.mail[x.dataset.mailKey] = x.value.trim(); else delete t.config.mail[x.dataset.mailKey]; if (!Object.keys(t.config.mail).length) delete t.config.mail; });
    box.querySelectorAll('[data-timer]').forEach(x => { const iso = isoOf(x.value); if (iso) m.timers[x.dataset.timer] = iso; else delete m.timers[x.dataset.timer]; });
    box.querySelectorAll('[data-default]').forEach(x => {
      const id = x.dataset.default;
      if (x.checked) { m.flows[id] = { default: true }; return; }
      const v = box.querySelector(`[data-var="${CSS.escape(id)}"]`).value;
      if (!v) { delete m.flows[id]; return; }
      m.flows[id] = { var: v, op: box.querySelector(`[data-op="${CSS.escape(id)}"]`).value, value: parseValue(box.querySelector(`[data-value="${CSS.escape(id)}"]`).value) };
    });
    for (const task of Object.values(m.tasks)) {
      const part = S.cat.parts.find(p => p.key === task.part);
      if (task.config && part?.kind === 'service') {
        const allowed = new Set(Object.keys(part.config || {}));
        task.config = Object.fromEntries(Object.entries(task.config).filter(([key]) => allowed.has(key)));
        if (!Object.keys(task.config).length) delete task.config;
      }
    }
    S.mapping = m;
    return m;
  }

  function wire(box) {
    S.events?.abort(); S.events = new AbortController();
    const on = (type, fn) => box.addEventListener(type, fn, { signal: S.events.signal });
    on('input', () => { S.revision = (S.revision || 0) + 1; });
    on('change', e => {
      S.revision = (S.revision || 0) + 1;
      try { collect(); } catch (err) { S.el.querySelector('#flowMsg').textContent = err.message; S.el.querySelector('#flowMsg').className = 'form-msg neg'; return; }
      if (e.target.matches('[data-part],[data-default],[data-var],input[name=flowStart]')) renderEditor();
      clearTimeout(S.timer); S.timer = setTimeout(() => recheck(false), 300);
    });
    box.querySelector('#flowCheck').addEventListener('click', e => once('check', e.currentTarget, () => recheck(true)));
    box.querySelector('#flowRegister').addEventListener('click', e => once('register', e.currentTarget, doRegister));
    on('click', e => {
      const li = e.target.closest('[data-goto]'); if (!li) return;
      const row = box.querySelector(`[data-row="${CSS.escape(li.dataset.goto)}"]`);
      if (row) { row.scrollIntoView({ block: 'center' }); row.classList.add('flash'); setTimeout(() => row.classList.remove('flash'), 1500); }
    });
  }

  async function recheck(save) {
    const msg = S.el.querySelector('#flowMsg');
    if (save) msg.textContent = '검사 중…';
    try {
      collect();
      const revision = S.revision, view = S.view;
      const id = encodeURIComponent(S.view.definition_id);
      const v = save ? await call('PUT', `/api/flows/${id}/mapping`, { mapping: S.mapping }) : await call('POST', `/api/flows/${id}/check`, { mapping: S.mapping });
      if (view !== S.view || revision !== S.revision) return;
      const changed = JSON.stringify(v.check.available) !== JSON.stringify(S.view.check.available);
      S.view = Object.assign(S.view, { check: v.check, next_version: v.next_version, versions: v.versions });
      if (changed) renderEditor(); else S.el.querySelector('#flowProblems').innerHTML = resultBlock(v.check);
      if (save) { S.el.querySelector('#flowMsg').textContent = '매핑을 저장했습니다'; S.el.querySelector('#flowMsg').className = 'form-msg pos'; }
    } catch (e) { msg.textContent = e.message; msg.className = 'form-msg neg'; }
  }

  async function doRegister() {
    const msg = S.el.querySelector('#flowMsg');
    try {
      collect();
      const r = await call('POST', `/api/flows/${encodeURIComponent(S.view.definition_id)}/register`, { mapping: S.mapping });
      UI.toast(`판본 ${r.version} 등록 — 운영 판본은 그대로입니다`, { tone: 'ok' });
      msg.textContent = `${r.name} 판본 ${r.version}${window.hydWords.josa(String(r.version), '을/를')} 등록했습니다.`; msg.className = 'form-msg pos';
      await recheck(false); loadList();
    } catch (e) {
      msg.textContent = e.message; msg.className = 'form-msg neg';
      if (e.problems) S.el.querySelector('#flowProblems').innerHTML = problemsBlock(e.problems);
    }
  }

  // ------------------------------------------------ 목록 · 그림 받기 · 직접 시작 · 되돌리기
  function renderList() {
    const box = S.el.querySelector('#flowList'), L = S.list || { drafts: [], versions: [] };
    if (!L.drafts.length && !L.versions.length) { box.innerHTML = UI.empty('가져온 흐름이 없습니다', '위에서 .bpmn 파일을 가져오면 여기 남습니다', 'compact'); return; }
    const ids = [...new Set([...L.drafts.map(d => d.proc_def_id), ...L.versions.map(v => v.id)])];
    box.innerHTML = ids.map(id => {
      const vs = L.versions.filter(v => v.id === id), d = L.drafts.find(x => x.proc_def_id === id);
      const alertStart = d?.mapping?.start?.kind === 'alert';
      const registeredName = (vs[vs.length - 1] || {}).name || (d && d.mapping && d.mapping.name);
      const name = registeredName && registeredName !== id ? registeredName : UI.terms['def.' + id] || '이름 미등록 흐름';
      const rows = vs.map(v => `<li>판본 <b>${h(v.version)}</b> · ${h(UI.dateTime(v.registered_at))}
        <a class="btn small" href="${h(api(`/api/flows/${encodeURIComponent(id)}/versions/${encodeURIComponent(v.version)}/bpmn`))}" download>그림 받기</a>
        ${alertStart ? '<span class="muted">경보가 들어오면 시작</span>' : `<button class="btn small" data-start="${h(id)}" data-version="${h(v.version)}"${hydCourseAccess.startBlocked(id) ? ` disabled title="${h(hydCourseAccess.startBlocked(id))}"` : ''}>직접 시작</button><div data-startbox="${h(id + '@' + v.version)}"></div>`}</li>`).join('');
      return UI.card({ title: h(name), sub: d ? '매핑 초안 있음' : '', body: (rows ? `<ul class="flow-versions">${rows}</ul>` : '<p class="muted">등록한 판본 없음</p>') + UI.metaFold([['흐름 식별자', h(id)]]),
        actions: (d ? `<button class="btn small" data-open="${h(id)}">매핑 열기</button>` : '') + `<button class="btn small danger" data-delete-flow="${h(id)}">이 흐름 지우기</button><div data-delete-box="${h(id)}"></div>` });
    }).join('');
    box.querySelectorAll('[data-open]').forEach(b => b.addEventListener('click', () => openDraft(b.dataset.open)));
    box.querySelectorAll('[data-start]').forEach(b => b.addEventListener('click', () => startForm(b.dataset.start, b.dataset.version)));
    box.querySelectorAll('[data-delete-flow]').forEach(b => b.addEventListener('click', () => deleteForm(b.dataset.deleteFlow)));
  }

  function deleteForm(id) {
    const box = S.el.querySelector(`[data-delete-box="${CSS.escape(id)}"]`);
    box.innerHTML = `<div class="form"><p class="field-hint">선택한 학생 흐름의 모든 판본과 초안을 지웁니다. 진행 중인 처리 건이나 기준 흐름은 지울 수 없습니다.</p>${UI.field({ label: '담당자', required: true, input: '<input data-delete-by>' })}<div class="form-actions"><span class="form-msg" role="status"></span><button class="btn small" data-delete-cancel>취소</button><button class="btn small danger" data-delete-confirm>이 흐름 지우기</button></div></div>`;
    box.querySelector('[data-delete-cancel]').onclick = () => { box.innerHTML = ''; };
    box.querySelector('[data-delete-confirm]').onclick = async ev => {
      const by = box.querySelector('[data-delete-by]').value.trim(), msg = box.querySelector('.form-msg');
      if (!by) { msg.textContent = '담당자를 적어 주세요.'; return; }
      if (S.deleting) return;
      S.deleting = true; box.querySelectorAll('button,input').forEach(n => { n.disabled = true; });
      try {
        const result = await call('DELETE', '/api/flows/' + encodeURIComponent(id) + '?by=' + encodeURIComponent(by));
        if (S.view?.definition_id === id) { S.view = null; S.mapping = null; S.el.querySelector('#flowEditor').innerHTML = ''; }
        UI.toast(result.projection_pending ? `흐름을 지웠습니다. 그래프 기록 ${result.projection_pending}건은 정리를 다시 시도하고 있습니다.` : '선택한 흐름을 지웠습니다.', { tone: result.projection_pending ? 'warning' : 'ok' }); await loadList();
      } catch (e) { msg.textContent = e.message; box.querySelectorAll('button,input').forEach(n => { n.disabled = false; }); }
      finally { S.deleting = false; }
    };
  }

  async function startForm(id, version) {
    const slot = S.el.querySelector(`[data-startbox="${CSS.escape(id + '@' + version)}"]`);
    try {
      const d = await call('GET', `/api/process/definitions/${encodeURIComponent(id)}?version=${encodeURIComponent(version)}`);
      if (d.alertPolicy) { slot.innerHTML = '<p class="field-hint">경보로 시작하는 흐름입니다 — 배포한 뒤 경보가 들어오면 시작됩니다.</p>'; return; }
      const fields = (d.startForm && d.startForm.fields_json) || [];
      slot.innerHTML = `<div class="form-grid">${fields.map(f => UI.field({ label: f.text || f.key, input: f.type === 'select'
        ? `<select data-sv="${h(f.key)}">${(f.items || []).map(i => `<option>${h(typeof i === 'string' ? i : Object.keys(i)[0])}</option>`).join('')}</select>`
        : f.type === 'boolean' ? `<select data-sv="${h(f.key)}" data-bool="1"><option value="true">예</option><option value="false">아니요</option></select>`
        : f.type === 'textarea' ? `<textarea data-sv="${h(f.key)}" data-kind="textarea" rows="4"></textarea>`
        : `<input data-sv="${h(f.key)}" data-kind="${h(f.type)}">` })).join('')}</div>
        <div class="form-actions"><button class="btn primary small" data-go="1">시작</button></div>`;
      // 시작 이벤트 id 는 폼을 열 때 한 번 만든다 — 두 번 누르거나 응답을 잃고 다시 눌러도 서버의 중복 실행 방지가 같은 처리 건으로 묶는다
      let eventId = `flow-${id}-${UI.uuid()}`;
      const go = slot.querySelector('[data-go]');
      go.addEventListener('click', () => once('start:' + id + '@' + version, go, async () => {
        const variables = {};
        try {
          slot.querySelectorAll('[data-sv]').forEach(x => {
            const k = x.dataset.sv, kind = x.dataset.kind;
            if (x.dataset.bool) variables[k] = x.value === 'true';
            else if (kind === 'number' || kind === 'integer') { if (x.value.trim() === '' || !isFinite(Number(x.value))) throw new Error(`${k}: 숫자를 넣으세요`); variables[k] = Number(x.value); }
            else if (kind === 'object' || kind === 'array') variables[k] = JSON.parse(x.value || (kind === 'array' ? '[]' : '{}'));
            else variables[k] = x.value;
          });
          const inst = await call('POST', '/api/instances/start', { definition_id: id, version, event_id: eventId, variables, name: d.processDefinitionName });
          eventId = `flow-${id}-${UI.uuid()}`;   // 시작됐으면 다음 누름은 새 처리 건
          UI.toast('처리 건을 시작했습니다', { tone: 'ok' });
          if (window.hydShell) window.hydShell.navigate({ tab: 'instances', inst: inst.proc_inst_id });
        } catch (e) { UI.toast(e.message, { tone: 'neg' }); }
      }));
    } catch (e) { slot.innerHTML = UI.errorBlock('시작 폼을 읽지 못했습니다', e.message); }
  }

  async function doReset() {
    const ok = await UI.confirm({ title: '기준으로 되돌리기', body: '가져온 흐름 · 판본 · 매핑 초안을 지웁니다. 기준 흐름과, 지금 경보에 배포된 흐름(수업 흐름 포함)은 남깁니다.', ok: '되돌리기', danger: true });
    if (!ok) return;
    try {
      const r = await call('POST', '/api/flows/reset');
      UI.toast(`되돌림 — 판본 ${r.versions} · 초안 ${r.drafts} 지움` + ((r.kept || []).length ? ` · 배포 중이라 남김: ${r.kept.join(', ')}` : ''), { tone: 'ok', timeout: 8000 });
      S.view = null; S.mapping = null; S.el.querySelector('#flowEditor').innerHTML = ''; loadList();
    } catch (e) { UI.toast(e.message, { tone: 'neg', timeout: 8000 }); }
  }

  window.hydFlows = { mount, pure };
})();
