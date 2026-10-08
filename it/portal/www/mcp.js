/* U3 (A2 MCP 부분) 도구(MCP) — 읽기 전용. window.hydMcp.mount(el) 이 그린다.
   ① 도구 지도: tenants.mcp 서버 → 연결 상태(시간 제한) → 도구(이름 · 설명 · 입력 형식) → 쓰는 에이전트 · 맡은 task
   ② 도구 써 보기: 도구 고르기 → 입력 형식에서 만든 폼 → 실제 호출 → 결과 (읽기 전용 도구만, 결과 크기 제한)
   ③ 호출 기록: events 에서 그 도구가 불린 처리 건 · task · 입력 · 결과 요약 · 시각 → #/instances/<id>/task/<taskId>
   원본: process-gpt-vue3 account-settings/MCPServer.vue(서버 목록 + 검사 요약 · 도구 수 · 펼침) · process-gpt-mcp-validator(도구 목록 · 실패 사유).
   서버 추가 · 수정 · 삭제는 포털에 없다 — 랩업(Claude Code)에서 tenants.mcp 에 넣으면 여기 그대로 나타난다.
   API: procsvc/mcp_api.py (/api/mcp/servers · /api/mcp/servers/{name}/tools · …/tools/{tool}/call · /api/mcp/calls). */
(function () {
  // ---------------------------------------------------------------- 입력 형식(JSON Schema) → 폼 칸 (DOM 없이 시험 가능)
  const SCALAR = ['string', 'number', 'integer', 'boolean'];
  function baseType(prop) {
    if (!prop || typeof prop !== 'object') return { type: 'json', nullable: true };
    if (prop.enum) return { type: 'enum', options: prop.enum.slice(), nullable: false };
    const alts = prop.anyOf || prop.oneOf;
    if (Array.isArray(alts)) {                                  // pydantic Optional[X] = anyOf [X, null]
      const real = alts.filter(a => a && a.type !== 'null');
      const nullable = real.length < alts.length;
      if (real.length === 1) return Object.assign(baseType(real[0]), { nullable });
      return { type: 'json', nullable };
    }
    const t = Array.isArray(prop.type) ? prop.type.filter(x => x !== 'null') : [prop.type];
    if (t.length === 1 && SCALAR.includes(t[0])) return { type: t[0], nullable: Array.isArray(prop.type) && prop.type.includes('null') };
    return { type: 'json', nullable: false };                   // object · array · 섞인 형 → JSON 글
  }
  function fieldsOf(schema) {
    const props = (schema && schema.properties) || {};
    const required = new Set((schema && schema.required) || []);
    return Object.entries(props).map(([key, prop]) => {
      const b = baseType(prop);
      return { key, type: b.type, options: b.options || null, required: required.has(key),
        label: String((prop && (prop.title && prop.title !== key ? prop.title : '')) || ''),
        description: String((prop && prop.description) || ''), default: prop && 'default' in prop ? prop.default : undefined,
        minimum: prop && prop.minimum, maximum: prop && prop.maximum };
    });
  }
  // raw(글) → 값. 비운 선택 칸은 undefined(보내지 않음 — 서버 기본값). 틀리면 Error(사람이 읽는 사유).
  function coerce(f, raw) {
    const text = raw == null ? '' : String(raw).trim();
    const name = f.description || f.key;
    if (text === '') { if (f.required) throw new Error(`${name}: 필수 입력입니다`); return undefined; }
    if (f.type === 'integer') { if (!/^-?\d+$/.test(text)) throw new Error(`${name}: 정수여야 합니다 (입력 "${text}")`); return parseInt(text, 10); }
    if (f.type === 'number') { const n = Number(text); if (!isFinite(n)) throw new Error(`${name}: 숫자여야 합니다 (입력 "${text}")`); return n; }
    if (f.type === 'boolean') { if (text === 'true') return true; if (text === 'false') return false; throw new Error(`${name}: 예/아니요 가운데 고르세요`); }
    if (f.type === 'enum') { const hit = f.options.find(o => String(o) === text); if (hit === undefined) throw new Error(`${name}: 목록에 없는 값입니다`); return hit; }
    if (f.type === 'json') { try { return JSON.parse(text); } catch (e) { throw new Error(`${name}: JSON 형식이 아닙니다 — ${e.message}`); } }
    return text;
  }
  function argsFrom(fields, raws) {
    const args = {}, errors = [];
    for (const f of fields) {
      try { const v = coerce(f, raws[f.key]); if (v !== undefined) args[f.key] = v; } catch (e) { errors.push(e.message); }
    }
    return { args, errors };
  }
  const form = { fieldsOf, coerce, argsFrom };

  // ---------------------------------------------------------------- 화면
  const SERVER_LABEL = { enterprise: '업무 DB', 'hyd-dmn': '판단 엔진', neo4j: '지식 그래프' };   // 이름표만 — 동작은 서버 이름과 무관
  const T = { streamable_http: 'HTTP', stdio: '명령형', sse: 'SSE' };
  const KIND = { exec: '명령 없음', refused: '연결 거부', unreachable: '주소 없음', timeout: '시간 초과', auth: '인증 실패', not_mcp: 'MCP 아님',
    protocol: '프로토콜 오류', server: '서버 오류', closed: '연결 끊김', too_large: '응답 너무 큼', config: '설정 오류' };
  const S = { el: null, servers: [], tools: {}, sel: null, tab: 'tools', trying: null, results: {}, calls: {}, callTool: '', busy: false };
  const api = p => API.process + p;
  const serverLabel = n => SERVER_LABEL[n] ? `${SERVER_LABEL[n]} (${n})` : n;
  const toolLabel = (srv, t) => { const k = UI.toolName(`mcp__${srv}__${t}`); return k.includes(' · ') ? t : `${k} (${t})`; };
  const target = s => s.transport === 'stdio' ? [s.command, ...(s.args || [])].join(' ') : (s.url || '');

  function statusChip(name) {
    const r = S.tools[name];
    const s = S.servers.find(x => x.name === name);
    if (s && s.config_error) return UI.chipText('설정 오류', 'danger');
    if (!r) return UI.chipText('연결 확인 중', 'neutral');
    if (r.loading) return UI.chipText('연결 확인 중', 'neutral');
    if (r.status === 'ok') return UI.chipText('연결됨', 'success');
    return UI.chipText(KIND[r.error_kind] || '연결 실패', 'danger');
  }

  async function load() {
    const box = S.el.querySelector('#mcpServers');
    box.innerHTML = `<div class="muted" role="status">${esc(UI.t('loading'))}</div>`;
    try { const r = await getJ(api('/api/mcp/servers')); S.servers = r.servers || []; }
    catch (e) { box.innerHTML = UI.empty('도구 서버 목록을 불러오지 못했습니다', e.message, 'compact'); return; }
    S.tools = {};
    if (S.sel && !S.servers.some(s => s.name === S.sel)) S.sel = null;
    renderServers(); renderDetail();
    S.servers.filter(s => !s.config_error).forEach(s => probe(s.name));
  }

  async function probe(name) {
    S.tools[name] = { loading: true }; renderServers(); if (S.sel === name) renderDetail();
    try { S.tools[name] = await getJ(api(`/api/mcp/servers/${encodeURIComponent(name)}/tools?timeout=4`)); }
    catch (e) { S.tools[name] = { status: 'failed', error: e.message, error_kind: null, tools: [] }; }
    renderServers(); if (S.sel === name) renderDetail();
  }

  function renderServers() {
    const box = S.el.querySelector('#mcpServers');
    if (!S.servers.length) { box.innerHTML = UI.empty('등록된 도구 서버가 없습니다', '랩업에서 tenants.mcp 에 서버를 넣으면 여기 나타납니다', 'compact'); return; }
    box.innerHTML = S.servers.map(s => {
      const r = S.tools[s.name] || {};
      const n = r.status === 'ok' ? r.tools.length : null;
      const sub = s.config_error ? esc(s.config_error) : r.status === 'failed' ? esc(r.error || '') : esc(target(s));
      const who = s.agents.length ? s.agents.map(a => esc(a.name)).join(', ') : '쓰는 에이전트 없음';
      const tasks = new Set(s.tasks.map(t => t.activity_name)).size;
      return UI.card({
        title: esc(serverLabel(s.name)), chips: statusChip(s.name) + UI.chipText(T[s.transport] || '?', 'neutral'),
        value: n != null ? `<span class="kv">도구 <b class="num">${n}</b><small>개</small></span>` : '',
        sub, body: `<p class="kv-line">${who}${tasks ? ` · 맡은 task <b>${tasks}</b>개` : ''}</p>`,
        cls: 'clickable mcp-card' + (s.name === S.sel ? ' sel' : '') + (s.config_error || r.status === 'failed' ? ' failed' : ''),
        attrs: `data-name="${esc(s.name)}" tabindex="0" role="button" aria-pressed="${s.name === S.sel}"`,
        actions: `<button class="btn small" data-open="${esc(s.name)}">도구 보기</button>`,
      });
    }).join('');
    box.querySelectorAll('.mcp-card').forEach(card => {
      const open = () => select(card.dataset.name);
      card.addEventListener('click', open);
      card.addEventListener('keydown', e => { if ((e.key === 'Enter' || e.key === ' ') && e.target === card) { e.preventDefault(); open(); } });
    });
  }

  function select(name) {
    S.sel = name; S.tab = 'tools'; S.trying = null; S.callTool = '';
    renderServers(); renderDetail(); S.el.querySelector('#mcpDetail').scrollIntoView({ block: 'nearest' });
  }

  function renderDetail() {
    const box = S.el.querySelector('#mcpDetail');
    const s = S.servers.find(x => x.name === S.sel);
    if (!s) { box.innerHTML = ''; return; }
    const r = S.tools[s.name] || { loading: true };
    const tools = r.status === 'ok' ? r.tools : [];
    const agents = s.agents.length ? s.agents.map(a => `<b>${esc(a.name)}</b>`).join(', ') : '<span class="muted">이 서버를 도구로 적은 에이전트가 없습니다</span>';
    const taskNames = [...new Set(s.tasks.map(t => t.activity_name))];
    const undeclared = s.tasks.some(t => !t.declared);
    const tasks = taskNames.length ? taskNames.map(esc).join(' · ') + (undeclared ? ' <span class="muted">(단계에 도구 지정이 없어 테넌트 서버 전부를 씁니다)</span>' : '') : '<span class="muted">없음</span>';
    const status = s.config_error ? `<p class="field-error" role="alert">${esc(s.config_error)}</p>`
      : r.loading ? `<p class="muted" role="status">연결 확인 중… (최대 4초)</p>`
      : r.status === 'ok' ? `<p class="kv-line">연결됨 · 도구 <b>${tools.length}</b>개 · ${esc((r.server_info && r.server_info.name) || '')} ${esc((r.server_info && r.server_info.version) || '')} · ${r.elapsed_ms} ms · ${esc(UI.dateTime(r.checked_at))} 확인</p>`
      : `<p class="field-error" role="alert">${esc(r.error || '연결 실패')}</p><p class="field-hint">${esc(r.checked_at ? UI.dateTime(r.checked_at) + ' 확인 · 제한 ' + (r.timeout_s || 4) + '초' : '')}</p>`;
    const settings = [['종류', T[s.transport] || s.transport || '–'], [s.transport === 'stdio' ? '명령' : '주소', target(s) || '–'],
      ...Object.entries(s.env || {}).map(([k, v]) => ['환경변수 ' + k, v]), ...Object.entries(s.headers || {}).map(([k, v]) => ['접속 헤더 ' + k, v])];
    box.innerHTML = `<section class="card mcp-detail"><header class="card-head"><div class="card-title"><h3>${esc(serverLabel(s.name))}</h3>${statusChip(s.name)}</div>` +
      `<div class="card-actions"><button class="btn small" id="mcpProbe" ${r.loading || s.config_error ? 'disabled' : ''}>연결 다시 확인</button></div></header>` +
      status +
      `<p class="kv-line">쓰는 에이전트: ${agents}</p><p class="kv-line">맡은 task: ${tasks}</p>` +
      UI.fold('설정 보기 (비밀값은 ******** 로 가림)', `<dl class="mcp-kv">${settings.map(([k, v]) => `<dt>${esc(k)}</dt><dd><code>${esc(v)}</code></dd>`).join('')}</dl>` +
        `<p class="field-hint">설정 원천: tenants.mcp — 포털에서는 바꾸지 않습니다. 서버 추가는 랩업(L14·L15)에서 합니다.</p>`) +
      UI.tabs([['tools', '도구', tools.length], ['calls', '호출 기록']], S.tab, 'data-mcp-tab') +
      `<div id="mcpPane"></div></section>`;
    box.querySelector('#mcpProbe')?.addEventListener('click', () => probe(s.name));
    box.querySelectorAll('[data-mcp-tab]').forEach(b => b.addEventListener('click', () => { S.tab = b.dataset.mcpTab; renderDetail(); }));
    if (S.tab === 'calls') renderCalls(s); else renderTools(s, r);
  }

  function renderTools(s, r) {
    const pane = S.el.querySelector('#mcpPane');
    if (r.loading) { pane.innerHTML = `<div class="muted" role="status">${esc(UI.t('loading'))}</div>`; return; }
    if (r.status !== 'ok') { pane.innerHTML = UI.empty('도구 목록을 받지 못했습니다', s.config_error || r.error || '', 'compact'); return; }
    if (!r.tools.length) { pane.innerHTML = UI.empty('이 서버는 도구를 내놓지 않습니다', '', 'compact'); return; }
    pane.innerHTML = `<ul class="mcp-tools">${r.tools.map(t => {
      const fields = fieldsOf(t.input_schema);
      const shape = fields.length ? `<table class="compact-table"><thead><tr><th>입력</th><th>형</th><th>설명</th></tr></thead><tbody>${fields.map(f =>
        `<tr><td><code>${esc(f.key)}</code>${f.required ? ' <i class="req">*</i>' : ''}</td><td>${esc(typeName(f))}</td><td>${esc(f.description || '–')}</td></tr>`).join('')}</tbody></table>` : '<p class="muted">입력 없음</p>';
      const open = S.trying === t.name;
      return `<li class="mcp-tool${open ? ' open' : ''}" data-tool="${esc(t.name)}"><div class="mcp-tool-head"><div><b>${esc(toolLabel(s.name, t.name))}</b> ` +
        (t.callable ? UI.chipText('읽기 전용', 'success') : UI.chipText('써 보기 불가', 'warning')) +
        `<span class="mcp-desc">${esc(t.description || '설명 없음')}</span>${t.callable ? '' : `<span class="mcp-why">${esc(t.refuse_reason || '')}</span>`}</div>` +
        `<button class="btn small${open ? ' primary' : ''}" data-try="${esc(t.name)}" ${t.callable ? '' : 'disabled'} title="${esc(t.callable ? '' : t.refuse_reason || '')}">${open ? '닫기' : '써 보기'}</button></div>` +
        UI.fold(`입력 형식 · ${fields.length}칸`, shape) + (open ? tryForm(s, t, fields) : '') + '</li>';
    }).join('')}</ul>`;
    pane.querySelectorAll('[data-try]').forEach(b => b.addEventListener('click', () => { S.trying = S.trying === b.dataset.try ? null : b.dataset.try; renderTools(s, r); }));
    if (S.trying) wireTry(s, r.tools.find(t => t.name === S.trying));
  }

  const typeName = f => ({ string: '글', number: '숫자', integer: '정수', boolean: '예/아니요', enum: '목록', json: 'JSON' })[f.type] + (f.required ? '' : ' · 선택');

  function inputFor(f) {
    const id = `mcpIn-${f.key}`;
    const ph = f.default != null ? `기본값 ${typeof f.default === 'string' ? f.default : JSON.stringify(f.default)}` : '';
    if (f.type === 'enum') return `<select id="${esc(id)}" data-key="${esc(f.key)}"><option value="">${f.required ? '고르세요' : '(비움)'}</option>${f.options.map(o => `<option value="${esc(o)}">${esc(o)}</option>`).join('')}</select>`;
    if (f.type === 'boolean') return `<select id="${esc(id)}" data-key="${esc(f.key)}"><option value="">${f.required ? '고르세요' : '(비움)'}</option><option value="true">예</option><option value="false">아니요</option></select>`;
    if (f.type === 'json') return `<textarea id="${esc(id)}" data-key="${esc(f.key)}" rows="3" placeholder="${esc(ph || 'JSON 예: {} 또는 []')}"></textarea>`;
    return `<input id="${esc(id)}" data-key="${esc(f.key)}" ${f.type === 'number' || f.type === 'integer' ? 'inputmode="decimal"' : ''} placeholder="${esc(ph)}">`;
  }

  function tryForm(s, t, fields) {
    const res = S.results[s.name + '/' + t.name];
    const body = fields.length ? UI.section('', fields.map(f => UI.field({ label: f.description ? f.description.split(/[.(:]/)[0].slice(0, 40).trim() || f.key : f.key, required: f.required,
      input: inputFor(f), hint: `입력 이름 ${f.key} · ${typeName(f)}${f.description && f.description.length > 40 ? ' · ' + f.description : ''}` })).join('')) : '<p class="muted">입력 없이 부릅니다</p>';
    return `<div class="mcp-try"><div class="form">${body}${UI.actions('<button class="btn primary" id="mcpCall">호출</button>')}</div>` +
      `<p class="field-hint">실제 서버를 부릅니다. 읽기 전용 도구만 허용되며 처리 건 · 설비 · 업무 DB 를 바꾸지 않습니다. 결과는 최대 2만 자까지 보입니다.</p>` +
      `<div id="mcpResult" aria-live="polite">${res ? resultHtml(res) : ''}</div></div>`;
  }

  function resultHtml(res) {
    if (res.loading) return `<p class="muted" role="status">호출 중…</p>`;
    if (res.error) return `<p class="field-error" role="alert">${esc(res.error)}</p>`;
    const r = res.result;
    return `<p class="kv-line">${r.is_error ? UI.chipText('도구가 오류를 돌려줌', 'danger') : UI.chipText('결과', 'success')} · ${res.elapsed_ms} ms · ${r.size_chars.toLocaleString()}자` +
      `${r.truncated ? ` · <b>${r.limit_chars.toLocaleString()}자에서 잘림</b>` : ''} · 보낸 입력 <code>${esc(JSON.stringify(res.arguments))}</code></p>` +
      `<pre class="mcp-out">${esc(r.text)}</pre>`;
  }

  function wireTry(s, t) {
    if (!t) return;
    const fields = fieldsOf(t.input_schema);
    const key = s.name + '/' + t.name;
    S.el.querySelector('#mcpCall').addEventListener('click', async () => {
      const raws = {}; S.el.querySelectorAll('.mcp-try [data-key]').forEach(i => { raws[i.dataset.key] = i.value; });
      const { args, errors } = argsFrom(fields, raws);
      const out = S.el.querySelector('#mcpResult');
      if (errors.length) { out.innerHTML = `<p class="field-error" role="alert">${errors.map(esc).join('<br>')}</p>`; return; }
      const btn = S.el.querySelector('#mcpCall'); btn.disabled = true;
      S.results[key] = { loading: true }; out.innerHTML = resultHtml(S.results[key]);
      try { S.results[key] = await postJ(api(`/api/mcp/servers/${encodeURIComponent(s.name)}/tools/${encodeURIComponent(t.name)}/call`), { arguments: args, timeout: 15, by: '포털' }); }
      catch (e) { S.results[key] = { error: e.message }; }
      out.innerHTML = resultHtml(S.results[key]); btn.disabled = false;
    });
  }

  async function renderCalls(s) {
    const pane = S.el.querySelector('#mcpPane');
    const tools = ((S.tools[s.name] || {}).tools || []).map(t => t.name);
    const filter = `<div class="field mcp-filter"><label for="mcpCallTool">도구</label><select id="mcpCallTool"><option value="">전체</option>${tools.map(t => `<option value="${esc(t)}" ${t === S.callTool ? 'selected' : ''}>${esc(toolLabel(s.name, t))}</option>`).join('')}</select></div>`;
    pane.innerHTML = filter + `<div id="mcpCallList"><div class="muted" role="status">${esc(UI.t('loading'))}</div></div>`;
    pane.querySelector('#mcpCallTool').addEventListener('change', e => { S.callTool = e.target.value; renderCalls(s); });
    const list = pane.querySelector('#mcpCallList');
    let r;
    try { r = await getJ(api(`/api/mcp/calls?server=${encodeURIComponent(s.name)}${S.callTool ? '&tool=' + encodeURIComponent(S.callTool) : ''}&limit=50`)); }
    catch (e) { list.innerHTML = UI.empty('호출 기록을 불러오지 못했습니다', e.message, 'compact'); return; }
    if (S.sel !== s.name || S.tab !== 'calls') return;
    if (!r.calls.length) { list.innerHTML = UI.empty('아직 이 도구를 부른 처리 건이 없습니다', `최근 도구 이벤트 ${r.scanned}개에서 찾았습니다. 경보로 처리 건이 돌면 여기 쌓입니다`, 'compact'); return; }
    const STATE = { done: ['완료', 'success'], error: ['오류', 'danger'], running: ['진행 중', 'accent'] };
    list.innerHTML = `<ul class="mcp-calls">${r.calls.map(c => {
      const [label, tone] = STATE[c.state] || ['–', 'neutral'];
      return `<li><div class="mcp-call-head"><span>${esc(UI.dateTime(c.at))}</span> ${UI.chipText(label, tone)} <b>${esc(toolLabel(c.server, c.tool))}</b>` +
        `${c.duration_ms != null ? ` <span class="muted">${c.duration_ms} ms</span>` : ''}</div>` +
        `<p class="kv-line">처리 건 <b>${esc(c.instance_name || UI.idText(c.proc_inst_id) || '–')}</b> · task <b>${esc(c.task_name || '–')}</b>` +
        `${c.link ? ` · <a href="${esc(c.link)}">처리 건에서 보기</a>` : ''}</p>` +
        `<p class="kv-line mcp-io"><span>입력</span> <code>${esc(c.input_summary || '–')}</code></p>` +
        `<p class="kv-line mcp-io"><span>결과</span> <code>${esc(c.output_summary || (c.state === 'running' ? '아직 끝나지 않음' : '–'))}</code></p>` +
        UI.fold('입력 · 결과 전체', `<pre class="mcp-out">입력\n${esc(c.input || '–')}\n\n결과\n${esc(c.output || '–')}</pre>`) + '</li>';
    }).join('')}</ul>` + (r.scanned >= r.scan_limit ? `<p class="field-hint">최근 도구 이벤트 ${r.scan_limit}개까지만 훑었습니다. 그보다 오래된 호출은 처리 건 화면에서 보세요.</p>` : '');
  }

  function mount(el) {
    if (!el) return;
    S.el = el;
    el.innerHTML = `<div class="page-head"><h1>도구(MCP)</h1><div class="page-tools"><button class="btn small" id="mcpReload">다시 읽기</button></div></div>` +
      `<p class="muted">에이전트가 쓰는 도구 서버와 그 도구를 봅니다. 읽기 전용 도구는 직접 불러 결과를 보고, 처리 건에서 언제 불렸는지 확인합니다. ` +
      `서버 설정은 보기만 합니다 — 랩업에서 추가한 서버도 여기 그대로 나타납니다.</p>` +
      `<div class="mcp-grid" id="mcpServers"></div><div id="mcpDetail"></div>`;
    el.querySelector('#mcpReload').addEventListener('click', load);
    load();
  }

  window.hydMcp = { mount, form };
  if (typeof document === 'undefined') return;
  const host = () => document.getElementById('mcpView');
  document.querySelector('.rail nav button[data-tab="mcp"]')?.addEventListener('click', () => { const el = host(); if (el && S.el !== el) mount(el); });
})();
