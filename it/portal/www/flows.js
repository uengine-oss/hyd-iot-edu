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
  const pure = { parseFields, fieldsText, parseValue, minutesOf, isoOf };

  if (typeof document === 'undefined') { window.hydFlows = { pure }; return; }

  // ---------------------------------------------------------------- 화면
  const S = { el: null, cat: null, view: null, mapping: null, list: null, busy: false, timer: null, result: null };
  const api = p => API.process + p;
  const h = s => esc(s);
  async function call(method, path, body) {
    const r = await fetch(api(path), { method, cache: 'no-store', headers: body ? { 'Content-Type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) {
      const d = j.detail;
      const e = new Error(typeof d === 'string' ? d : (d && d.reason) || `요청 실패 (${r.status})`);
      e.problems = (d && d.problems) || null; e.status = r.status;
      throw e;
    }
    return j;
  }
  const partName = p => p ? UI.flowName(p.name) : '';
  const roleOpts = (sel, human) => S.cat.roles.filter(r => !human || r.human).map(r => `<option value="${h(r.name)}" ${r.name === sel ? 'selected' : ''}>${h(r.name)}</option>`).join('');
  const agentOpts = sel => S.cat.agents.map(a => `<option value="${h(a.id)}" ${a.id === sel ? 'selected' : ''}>${h(UI.who(a.id) !== a.id ? UI.who(a.id) : a.name)}</option>`).join('');
  const nodeName = id => { const p = S.view && S.view.parsed; if (!p) return id; for (const k of ['tasks', 'starts', 'ends', 'boundaries', 'gateways']) { const n = p[k].find(x => x.id === id); if (n) return n.name || '(이름 없음)'; } return id; };

  function mount(el) {
    S.el = el;
    el.innerHTML = `
      <section class="card form" aria-label="그림 가져오기">
        <h3>그림 가져오기</h3>
        <p class="field-hint">demo.bpmn.io 에서 흐름을 그리고 왼쪽 아래 <b>Download BPMN diagram</b> 으로 받은 .bpmn 파일을 고릅니다. 같은 흐름 id 로 다시 가져오면 앞서 고른 매핑이 남습니다.</p>
        <div class="form-grid">
          ${UI.field({ label: '.bpmn 파일', input: '<input type="file" id="flowFile" accept=".bpmn,.xml,application/xml,text/xml">', required: true })}
          ${UI.field({ label: '흐름 id (비우면 그림의 프로세스 id)', input: '<input id="flowId" placeholder="예: oil_check" autocomplete="off">' })}
        </div>
        <div class="form-actions"><span class="form-msg" id="flowImportMsg" role="status"></span><button class="btn primary" id="flowImport">가져오기</button></div>
      </section>
      <div id="flowEditor"></div>
      ${UI.fold('내가 가져온 흐름 · 판본', '<div id="flowList"></div><div class="form-actions"><button class="btn small danger" id="flowReset">기준으로 되돌리기</button></div>', { open: true })}`;
    el.querySelector('#flowImport').addEventListener('click', doImport);
    el.querySelector('#flowReset').addEventListener('click', doReset);
    return Promise.all([loadCatalog(), loadList()]);
  }

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
      S.view = await call('POST', '/api/flows/import', { xml, file_name: file.name, definition_id: S.el.querySelector('#flowId').value.trim() || null });
      S.mapping = S.view.mapping;
      const r = S.view.reimport || {};
      msg.textContent = r.previous ? `다시 가져옴 — 매핑 유지 ${r.kept.length} · 새 task ${r.new.length} · 사라진 task ${r.dropped.length}` : `가져옴 — task ${S.view.parsed.tasks.length}개`;
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
    const patterns = S.cat.patterns.map(pt => `<label class="chk"><input type="checkbox" data-pattern="${h(pt)}" ${(start.patterns || []).includes(pt) ? 'checked' : ''}> ${h(typeof PATTERN_LABEL !== 'undefined' && PATTERN_LABEL[pt] || pt)}</label>`).join(' ');
    box.innerHTML = `
      <section class="card form" aria-label="매핑">
        <h3>${h(m.name || p.process.name || v.definition_id)} <span class="muted">· 흐름 id ${h(v.definition_id)} · 다음 판본 ${h(v.next_version)}</span></h3>
        <div class="form-grid">${UI.field({ label: '흐름 이름', input: `<input id="flowName" value="${h(m.name || p.process.name || '')}">` })}
          ${UI.readonly('그림 파일', h(v.file_name || '–'), `task ${p.tasks.length} · 분기 ${p.gateways.length} · 선 ${p.flows.length}`)}</div>
        ${UI.section('시작 조건', `
          <div class="field wide"><label class="chk"><input type="radio" name="flowStart" value="alert" ${start.kind === 'alert' ? 'checked' : ''}> 설비 경보로 시작</label>
            <div class="chk-row">${patterns}</div><p class="field-hint">경보 정책(회복 기준)은 기준 흐름의 계약을 그대로 씁니다.</p></div>
          <div class="field wide"><label class="chk"><input type="radio" name="flowStart" value="human" ${start.kind === 'human' ? 'checked' : ''}> 사람 입력 · 직접 시작</label>
            <textarea id="flowStartFields" rows="3" spellcheck="false" placeholder="값이름 | 표시 이름 | 종류 | 고를 값&#10;예) oil_iso | ISO 청정도 | text">${h(fieldsText(start.fields))}</textarea>
            <p class="field-hint">한 줄에 칸 하나. 종류: ${TYPES.map(t => TYPE_LABEL[t] + ' ' + t).join(' · ')}</p></div>`)}
        ${lanes ? UI.section('칸(레인) → 담당 역할', `<table class="compact-table"><thead><tr><th>그림의 칸</th><th>역할</th></tr></thead><tbody>${lanes}</tbody></table>`) : ''}
        ${UI.section('task → 부품 · 담당', `<table class="compact-table flow-map"><thead><tr><th>그림의 task</th><th>부품</th><th>담당</th><th>세부</th></tr></thead><tbody>${p.tasks.map(taskRow).join('')}</tbody></table>`)}
        ${p.boundaries.length ? UI.section('시간 초과(경계 타이머)', p.boundaries.map(timerRow).join('')) : ''}
        ${branchSection()}
        <div id="flowProblems">${resultBlock(v.check)}</div>
        <div class="form-actions"><span class="form-msg" id="flowMsg" role="status"></span>
          <button class="btn" id="flowCheck">검사</button><button class="btn primary" id="flowRegister">판본 등록</button></div>
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
      <optgroup label="일반 부품">${S.cat.parts.filter(x => x.group === 'general').map(opt).join('')}${wo ? `<option value="${h(wo.key)}" ${wo.key === m.part ? 'selected' : ''}>작업지시</option>` : ''}</optgroup></select>`;
    let who = '<span class="muted">–</span>', detail = '';
    if (part && part.kind === 'human') who = `<select data-role="${h(t.id)}"><option value="">${part.group === 'scenario' ? '부품 기본: ' + h(part.role) : '(칸의 역할)'}</option>${roleOpts(m.role || '', true)}</select>`;
    if (part && part.kind === 'agent') who = `<select data-agent="${h(t.id)}">${agentOpts(m.agent || part.agent || (S.cat.agents[0] || {}).id)}</select>`;
    if (part && part.kind === 'service') who = `<span>${h(part.role)}</span>`;
    if (part && part.group === 'scenario') {
      const outs = (part.form && part.form.fields_json || []).map(f => `<code>${h(f.key)}</code>`).join(' ');
      detail = `<p class="kv-line">받는 값 ${part.inputs.map(x => `<code>${h(x)}</code>`).join(' ') || '–'} · 내는 값 ${outs || (part.outputs.map(x => `<code>${h(x)}</code>`).join(' ') || '–')}${part.approval ? ' · <b>사람 승인</b>' : ''}${part.effect ? ` · <b>${h(part.effect)}</b>(승인 뒤)` : ''}</p>`;
    } else if (part && part.key === 'human') {
      detail = `<textarea data-fields="${h(t.id)}" rows="2" spellcheck="false" placeholder="값이름 | 표시 이름 | 종류">${h(fieldsText(m.fields))}</textarea>
        <input data-inputs="${h(t.id)}" value="${h((m.inputs || []).join(', '))}" placeholder="받을 값 (쉼표) — ${h(avail(t.id).join(', '))}">`;
    } else if (part && part.key === 'agent') {
      detail = `<textarea data-instruction="${h(t.id)}" rows="2" placeholder="지시문 — 무엇을 조회 · 계산해 무엇을 낼지">${h(m.instruction || '')}</textarea>
        <textarea data-outputs="${h(t.id)}" rows="2" spellcheck="false" placeholder="결과 값 — 값이름 | 표시 이름 | 종류">${h(fieldsText(m.outputs))}</textarea>
        <input data-inputs="${h(t.id)}" value="${h((m.inputs || []).join(', '))}" placeholder="받을 값 (쉼표) — ${h(avail(t.id).join(', '))}">`;
    }
    const lane = (S.view.parsed.lanes.find(l => l.id === t.lane) || {}).name;
    return `<tr data-row="${h(t.id)}"><td><b>${h(t.name || '(이름 없음)')}</b><br><small class="muted">${h(t.type_label)}${lane ? ' · ' + h(lane) : ''}</small></td><td>${sel}</td><td>${who}</td><td>${detail}</td></tr>`;
  }
  const avail = id => [...new Set(((S.view.check.available || {})[id] || []).map(x => x.value))];
  // 값 이름 → 사람이 읽는 이름(부품 폼 · 내가 적은 폼 칸의 표시 이름). 없으면 값 이름 그대로.
  function valueLabel(key) {
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
      <input type="number" min="0.1" step="any" data-timer="${h(b.id)}" value="${h(m ? minutesOf(m) : '')}" placeholder="${dflt ? '기본 ' + minutesOf(dflt) + '분' : '분'}"><p class="field-hint">분 (20배속에서는 실제 시간이 1/20)</p></div>`;
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
          <td><select data-var="${h(f.id)}" ${c.default ? 'disabled' : ''}><option value="">(값)</option>${vals.map(x => `<option value="${h(x)}" ${x === c.var ? 'selected' : ''}>${h(valueLabel(x) ? valueLabel(x) + ' · ' + x : x)}</option>`).join('')}</select></td>
          <td><select data-op="${h(f.id)}" ${c.default ? 'disabled' : ''}>${S.cat.ops.map(o => `<option ${o === (c.op || '==') ? 'selected' : ''}>${h(o)}</option>`).join('')}</select></td>
          <td><input data-value="${h(f.id)}" value="${h(c.value === undefined ? '' : c.value === true ? '예' : c.value === false ? '아니요' : c.value)}" placeholder="기준 (예/아니요 · 숫자 · 글)" ${c.default ? 'disabled' : ''}></td></tr>`;
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
  const resultBlock = c => c && c.ok ? `<p class="kv-line pos" role="status">사전 검사 통과 — 판본으로 등록할 수 있습니다 (등록해도 운영 판본은 그대로, 배포는 따로).</p>` : problemsBlock(c && c.problems);

  function collect() {
    const box = S.el.querySelector('#flowEditor'), m = S.mapping;
    m.name = box.querySelector('#flowName').value.trim();
    const kind = (box.querySelector('input[name=flowStart]:checked') || {}).value;
    m.start = kind === 'alert' ? { kind, patterns: [...box.querySelectorAll('[data-pattern]')].filter(c => c.checked).map(c => c.dataset.pattern) }
      : kind === 'human' ? { kind, fields: parseFields(box.querySelector('#flowStartFields').value) } : {};
    box.querySelectorAll('[data-lane]').forEach(s => { if (s.value) m.lanes[s.dataset.lane] = s.value; else delete m.lanes[s.dataset.lane]; });
    box.querySelectorAll('[data-part]').forEach(s => {
      const id = s.dataset.part, prev = m.tasks[id] || {};
      m.tasks[id] = s.value ? (prev.part === s.value ? prev : { part: s.value }) : {};
      if (!s.value) delete m.tasks[id];
    });
    const set = (attr, fn) => box.querySelectorAll(`[data-${attr}]`).forEach(x => { const t = m.tasks[x.dataset[attr]]; if (t) fn(t, x); });
    set('role', (t, x) => { if (x.value) t.role = x.value; else delete t.role; });
    set('agent', (t, x) => { t.agent = x.value; });
    set('fields', (t, x) => { t.fields = parseFields(x.value); });
    set('outputs', (t, x) => { t.outputs = parseFields(x.value); });
    set('instruction', (t, x) => { t.instruction = x.value.trim(); });
    set('inputs', (t, x) => { t.inputs = x.value.split(',').map(s => s.trim()).filter(Boolean); });
    box.querySelectorAll('[data-timer]').forEach(x => { const iso = isoOf(x.value); if (iso) m.timers[x.dataset.timer] = iso; else delete m.timers[x.dataset.timer]; });
    box.querySelectorAll('[data-default]').forEach(x => {
      const id = x.dataset.default;
      if (x.checked) { m.flows[id] = { default: true }; return; }
      const v = box.querySelector(`[data-var="${CSS.escape(id)}"]`).value;
      if (!v) { delete m.flows[id]; return; }
      m.flows[id] = { var: v, op: box.querySelector(`[data-op="${CSS.escape(id)}"]`).value, value: parseValue(box.querySelector(`[data-value="${CSS.escape(id)}"]`).value) };
    });
    return m;
  }

  function wire(box) {
    box.addEventListener('change', e => {
      try { collect(); } catch (err) { S.el.querySelector('#flowMsg').textContent = err.message; S.el.querySelector('#flowMsg').className = 'form-msg neg'; return; }
      if (e.target.matches('[data-part],[data-default],input[name=flowStart]')) renderEditor();
      clearTimeout(S.timer); S.timer = setTimeout(() => recheck(false), 300);
    });
    box.querySelector('#flowCheck').addEventListener('click', () => recheck(true));
    box.querySelector('#flowRegister').addEventListener('click', doRegister);
    box.addEventListener('click', e => {
      const li = e.target.closest('[data-goto]'); if (!li) return;
      const row = box.querySelector(`[data-row="${CSS.escape(li.dataset.goto)}"]`);
      if (row) { row.scrollIntoView({ block: 'center' }); row.classList.add('flash'); setTimeout(() => row.classList.remove('flash'), 1500); }
    });
  }

  async function recheck(save) {
    const msg = S.el.querySelector('#flowMsg');
    try {
      collect();
      const id = encodeURIComponent(S.view.definition_id);
      const v = save ? await call('PUT', `/api/flows/${id}/mapping`, { mapping: S.mapping }) : await call('POST', `/api/flows/${id}/check`, { mapping: S.mapping });
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
      msg.textContent = `${r.name} 판본 ${r.version} 을(를) 등록했습니다.`; msg.className = 'form-msg pos';
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
      const name = (vs[vs.length - 1] || {}).name || (d && d.mapping && d.mapping.name) || id;
      const rows = vs.map(v => `<li>판본 <b>${h(v.version)}</b> · ${h(UI.dateTime(v.registered_at))}
        <a class="btn small" href="${h(api(`/api/flows/${encodeURIComponent(id)}/versions/${encodeURIComponent(v.version)}/bpmn`))}" download>그림 받기</a>
        <button class="btn small" data-start="${h(id)}" data-version="${h(v.version)}">직접 시작</button><div data-startbox="${h(id + '@' + v.version)}"></div></li>`).join('');
      return UI.card({ title: h(name), sub: `흐름 id ${h(id)}${d ? ' · 매핑 초안 있음' : ''}`, body: rows ? `<ul class="flow-versions">${rows}</ul>` : '<p class="muted">등록한 판본 없음</p>',
        actions: d ? `<button class="btn small" data-open="${h(id)}">매핑 열기</button>` : '' });
    }).join('');
    box.querySelectorAll('[data-open]').forEach(b => b.addEventListener('click', () => openDraft(b.dataset.open)));
    box.querySelectorAll('[data-start]').forEach(b => b.addEventListener('click', () => startForm(b.dataset.start, b.dataset.version)));
  }

  async function startForm(id, version) {
    const slot = S.el.querySelector(`[data-startbox="${CSS.escape(id + '@' + version)}"]`);
    try {
      const d = await call('GET', `/api/process/definitions/${encodeURIComponent(id)}?version=${encodeURIComponent(version)}`);
      if (d.alertPolicy) { slot.innerHTML = '<p class="field-hint">설비 경보로 시작하는 흐름입니다 — 배포한 뒤 경보가 들어오면 시작됩니다.</p>'; return; }
      const fields = (d.startForm && d.startForm.fields_json) || [];
      slot.innerHTML = `<div class="form-grid">${fields.map(f => UI.field({ label: f.text || f.key, input: f.type === 'select'
        ? `<select data-sv="${h(f.key)}">${(f.items || []).map(i => `<option>${h(typeof i === 'string' ? i : Object.keys(i)[0])}</option>`).join('')}</select>`
        : f.type === 'boolean' ? `<select data-sv="${h(f.key)}" data-bool="1"><option value="true">예</option><option value="false">아니요</option></select>`
        : `<input data-sv="${h(f.key)}" data-kind="${h(f.type)}">` })).join('')}</div>
        <div class="form-actions"><button class="btn primary small" data-go="1">시작</button></div>`;
      slot.querySelector('[data-go]').addEventListener('click', async () => {
        const variables = {};
        try {
          slot.querySelectorAll('[data-sv]').forEach(x => {
            const k = x.dataset.sv, kind = x.dataset.kind;
            if (x.dataset.bool) variables[k] = x.value === 'true';
            else if (kind === 'number' || kind === 'integer') { if (x.value.trim() === '' || !isFinite(Number(x.value))) throw new Error(`${k}: 숫자를 넣으세요`); variables[k] = Number(x.value); }
            else if (kind === 'object' || kind === 'array') variables[k] = JSON.parse(x.value || (kind === 'array' ? '[]' : '{}'));
            else variables[k] = x.value;
          });
          const inst = await call('POST', '/api/instances/start', { definition_id: id, version, event_id: `flow-${id}-${Date.now()}`, variables, name: d.processDefinitionName });
          UI.toast('처리 건을 시작했습니다', { tone: 'ok' });
          if (window.hydShell) window.hydShell.navigate({ tab: 'instances', inst: inst.proc_inst_id });
        } catch (e) { UI.toast(e.message, { tone: 'neg' }); }
      });
    } catch (e) { slot.innerHTML = UI.errorBlock('시작 폼을 읽지 못했습니다', e.message); }
  }

  async function doReset() {
    const ok = await UI.confirm({ title: '기준으로 되돌리기', body: '내가 가져온 흐름 · 판본 · 매핑 초안을 지웁니다. 기준 흐름은 그대로입니다.', ok: '되돌리기', danger: true });
    if (!ok) return;
    try {
      const r = await call('POST', '/api/flows/reset');
      UI.toast(`되돌림 — 판본 ${r.versions} · 초안 ${r.drafts} 지움`, { tone: 'ok' });
      S.view = null; S.mapping = null; S.el.querySelector('#flowEditor').innerHTML = ''; loadList();
    } catch (e) { UI.toast(e.message, { tone: 'neg', timeout: 8000 }); }
  }

  window.hydFlows = { mount, pure };
})();
