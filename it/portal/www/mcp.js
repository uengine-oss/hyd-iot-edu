/* U3 (A2 MCP 부분) 도구(MCP) — 읽기 전용. window.hydMcp.mount(el) 이 그린다.
   ① 도구 지도: tenants.mcp 서버 → 연결 상태(시간 제한) → 도구(이름 · 설명 · 입력 형식) → 쓰는 에이전트 · 맡은 task
   ② 도구 써 보기: 도구 고르기 → 입력 형식에서 만든 폼 → 실제 호출 → 결과 (읽기 전용 도구만, 결과 크기 제한)
   ③ 호출 기록: events 에서 그 도구가 불린 처리 건 · task · 입력 · 결과 요약 · 시각 → #/instances/<id>/task/<taskId>
   원본: process-gpt-vue3 account-settings/MCPServer.vue(서버 목록 + 검사 요약 · 도구 수 · 펼침) · process-gpt-mcp-validator(도구 목록 · 실패 사유).
   ④ B2 등록 · 고치기 · 지우기 · 연결 검사 · 기준으로 되돌리기: 폼 → 연결 검사 통과해야 저장(실패는 사유), 기준 서버는 보기만,
      학생 서버는 "내가 등록" 표시. 검사를 통과한 서버의 읽기 전용 도구만 에이전트 도구로 고를 수 있다(/api/mcp/selectable).
   랩업(Claude Code)에서 tenants.mcp 에 넣은 서버도 여기 그대로 나타난다("포털 밖에서 추가" — 연결 검사를 해야 쓰인다).
   API: procsvc/mcp_api.py (/api/mcp/servers · /api/mcp/servers/{name}/tools · …/tools/{tool}/call · /api/mcp/calls),
        procsvc/mcp_registry.py (POST /api/mcp/servers · PUT/DELETE /api/mcp/servers/{name} · POST …/{name}/check · POST /api/mcp/check ·
        GET /api/mcp/selectable · POST /api/mcp/reset). */
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

  // ---------------------------------------------------------------- B2 등록 폼 → 요청 본문 (DOM 없이 시험 가능)
  // 이름=값 줄(환경변수 · 접속 헤더). 빈 줄은 건너뛴다. 값의 ******** 는 그대로 보내면 서버가 옛 비밀값을 유지한다.
  function pairsFrom(text, label) {
    const out = {};
    String(text || '').split('\n').map(l => l.trim()).filter(Boolean).forEach(line => {
      const at = line.indexOf('=');
      if (at <= 0) throw new Error(`${label}: '${line}' 줄에 '이름=값' 의 = 가 없습니다`);
      out[line.slice(0, at).trim()] = line.slice(at + 1).trim();
    });
    return out;
  }
  function bodyFrom(v) {
    const name = String(v.name || '').trim();
    if (!name) throw new Error('이름: 필수 입력입니다 (예: my-folder — 소문자 · 숫자 · 하이픈)');
    const body = { name, transport: v.transport || 'streamable_http' };
    if (body.transport === 'stdio') {
      const command = String(v.command || '').trim();
      if (!command) throw new Error('명령: 명령형 서버는 실행할 명령이 필요합니다 (예: npx)');
      body.command = command;
      body.args = String(v.args || '').split(/\s+/).filter(Boolean);
      const env = pairsFrom(v.env, '환경변수');
      if (Object.keys(env).length) body.env = env;
    } else {
      const url = String(v.url || '').trim();
      if (!url) throw new Error('주소: HTTP 서버는 주소가 필요합니다 (예: http://host.docker.internal:8301/mcp)');
      body.url = url;
      const headers = pairsFrom(v.headers, '접속 헤더');
      if (Object.keys(headers).length) body.headers = headers;
    }
    const d = String(v.description || '').trim();
    if (d) body.description = d;
    return body;
  }
  const register = { bodyFrom, pairsFrom };

  // ---------------------------------------------------------------- 화면
  const SERVER_LABEL = { enterprise: '업무 DB', 'hyd-dmn': '판단 엔진', neo4j: '지식 그래프' };   // 이름표만 — 동작은 서버 이름과 무관
  const T = { streamable_http: 'HTTP', stdio: '명령형', sse: 'SSE' };
  const KIND = { exec: '명령 없음', refused: '연결 거부', unreachable: '주소 없음', timeout: '시간 초과', auth: '인증 실패', not_mcp: 'MCP 아님',
    protocol: '프로토콜 오류', server: '서버 오류', closed: '연결 끊김', too_large: '응답 너무 큼', config: '설정 오류', secret: '비밀 값 없음' };
  const S = { el: null, servers: [], tools: {}, sel: null, tab: 'tools', trying: null, results: {}, calls: {}, callTool: '', busy: false, form: null,
    confirming: null, secrets: null };
  const api = p => API.process + p;
  const serverLabel = n => SERVER_LABEL[n] ? `${SERVER_LABEL[n]} (${n})` : n;
  const toolLabel = (srv, t) => { const k = UI.toolName(`mcp__${srv}__${t}`); return k.includes(' · ') ? t : `${k} (${t})`; };
  const target = s => s.transport === 'stdio' ? [s.command, ...(s.args || [])].join(' ') : (s.url || '');

  const ORIGIN = { seed: ['기준', 'neutral'], user: ['내가 등록', 'accent'], external: ['포털 밖에서 추가', 'warning'] };
  const CHECK = { ok: '연결 검사 통과', failed: '연결 검사 실패', stale: '설정이 바뀌어 다시 검사 필요', never: '연결 검사 전' };
  function originChip(s) { const o = ORIGIN[s.origin]; return o ? UI.chipText(o[0], o[1]) : ''; }

  function statusChip(name) {
    const r = S.tools[name];
    const s = S.servers.find(x => x.name === name);
    if (s && s.config_error) return UI.chipText('설정 오류', 'danger');
    if (!r) return UI.chipText('연결 확인 중', 'neutral');
    if (r.loading) return UI.chipText('연결 확인 중', 'neutral');
    if (r.status === 'ok') return UI.chipText('연결됨', 'success');
    // A161-U1 (결함 10): 명령형(stdio) 서버는 워커 PC 에서 뜬다 — 포털 쪽 컨테이너에 명령이 없는 것은 고장이 아니다
    if (s && s.transport === 'stdio' && r.error_kind === 'exec') return UI.chipText('워커에서 실행', 'neutral');
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
    if (!S.servers.length) { box.innerHTML = UI.empty('등록된 도구 서버가 없습니다', '"서버 등록"으로 내 서버를 등록하거나 랩업에서 tenants.mcp 에 넣으면 여기 나타납니다', 'compact'); return; }
    box.innerHTML = S.servers.map(s => {
      const r = S.tools[s.name] || {};
      const n = r.status === 'ok' ? r.tools.length : null;
      const workerSide = s.transport === 'stdio' && r.error_kind === 'exec';
      const sub = s.config_error ? esc(s.config_error) : workerSide ? '이 서버는 워커 PC 에서 실행됩니다. 포털에서는 도구 목록을 미리 볼 수 없습니다' : r.status === 'failed' ? esc(UI.clean(r.error || '')) : esc(target(s));
      const who = s.agents.length ? s.agents.map(a => esc(a.name)).join(', ') : '쓰는 에이전트 없음';
      const tasks = new Set(s.tasks.map(t => t.activity_name)).size;
      return UI.card({
        title: esc(serverLabel(s.name)), chips: statusChip(s.name) + UI.chipText(T[s.transport] || '?', 'neutral') + originChip(s),
        value: n != null ? `<span class="kv">도구 <b class="num">${n}</b><small>개</small></span>` : '',
        sub, body: `<p class="kv-line">${who}${tasks ? ` · 맡은 task <b>${tasks}</b>개` : ''}</p>` +
          `<p class="kv-line">${s.selectable ? '에이전트 도구로 고를 수 있음' : s.origin === 'seed' ? '<span class="muted">기본 에이전트가 쓰는 서버</span>' : `<span class="muted">에이전트 도구로 고르려면 연결 검사 필요 · ${esc(CHECK[(s.check || {}).status] || '검사 필요')}</span>`}</p>`,
        cls: 'clickable mcp-card' + (s.name === S.sel ? ' sel' : '') + (s.config_error || (r.status === 'failed' && !workerSide) ? ' failed' : ''),
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
      `<div class="card-actions"><button class="btn small" id="mcpProbe" ${r.loading || s.config_error ? 'disabled' : ''}>연결 검사</button>` +
      (s.editable ? `<button class="btn small" id="mcpEdit">고치기</button><button class="btn small" id="mcpDelete">지우기</button>` : '') +
      `</div></header>` +
      status + gateLine(s) +
      `<p class="kv-line">쓰는 에이전트: ${agents}</p><p class="kv-line">맡은 task: ${tasks}</p>` +
      UI.fold('설정 보기 (비밀값은 ******** 로 가림)', `<dl class="mcp-kv">${settings.map(([k, v]) => `<dt>${esc(k)}</dt><dd><code>${esc(v)}</code></dd>`).join('')}</dl>` +
        `<p class="field-hint">설정 원천: tenants.mcp. ${s.editable ? '고치기는 연결 검사를 통과해야 저장됩니다.' : '기준(기본 제공) 서버는 고치거나 지울 수 없습니다 — 새 이름으로 등록해 쓰세요.'}</p>`) +
      UI.tabs([['tools', '도구', tools.length], ['calls', '호출 기록']], S.tab, 'data-mcp-tab') +
      `<div id="mcpPane"></div></section>`;
    box.querySelector('#mcpProbe')?.addEventListener('click', () => checkSaved(s.name));
    box.querySelector('#mcpEdit')?.addEventListener('click', () => openForm(s));
    box.querySelector('#mcpDelete')?.addEventListener('click', () => removeServer(s));
    box.querySelectorAll('[data-mcp-tab]').forEach(b => b.addEventListener('click', () => { S.tab = b.dataset.mcpTab; renderDetail(); }));
    if (S.tab === 'calls') renderCalls(s); else renderTools(s, r);
  }

  function renderTools(s, r) {
    const pane = S.el.querySelector('#mcpPane');
    if (r.loading) { pane.innerHTML = `<div class="muted" role="status">${esc(UI.t('loading'))}</div>`; return; }
    if (r.status !== 'ok') { pane.innerHTML = UI.empty('도구 목록을 받지 못했습니다', s.config_error || r.error || '', 'compact'); return; }
    if (!r.tools.length) { pane.innerHTML = UI.empty('이 서버는 도구를 내놓지 않습니다', '', 'compact'); return; }
    const confirmed = new Set(s.read_confirmed || []);
    pane.innerHTML = `<ul class="mcp-tools">${r.tools.map(t => {
      const fields = fieldsOf(t.input_schema);
      const usable = t.callable || (confirmed.has(t.name) && t.confirmable);
      const shape = fields.length ? `<table class="compact-table"><thead><tr><th>입력</th><th>형</th><th>설명</th></tr></thead><tbody>${fields.map(f =>
        `<tr><td><code>${esc(f.key)}</code>${f.required ? ' <i class="req">*</i>' : ''}</td><td>${esc(typeName(f))}</td><td>${esc(f.description || '–')}</td></tr>`).join('')}</tbody></table>` : '<p class="muted">입력 없음</p>';
      const open = S.trying === t.name;
      // G2 ②: 표시(readOnlyHint)만 없는 도구는 강사가 읽기로 확인할 수 있다 — 확인한 도구는 에이전트 도구 · 써 보기에 들어간다
      const chip = t.callable ? UI.chipText('읽기 전용', 'success') : usable ? UI.chipText('강사 확인 읽기', 'success') : UI.chipText('써 보기 불가', 'warning');
      const confirmBtn = !s.editable || t.callable ? '' : usable ? `<button class="btn small" data-unconfirm="${esc(t.name)}">확인 취소</button>`
        : t.confirmable ? `<button class="btn small" data-confirm="${esc(t.name)}">읽기로 확인</button>` : '';
      return `<li class="mcp-tool${open ? ' open' : ''}" data-tool="${esc(t.name)}"><div class="mcp-tool-head"><div><b>${esc(toolLabel(s.name, t.name))}</b> ` + chip +
        `<span class="mcp-desc">${esc(t.description || '설명 없음')}</span>${usable ? '' : `<span class="mcp-why">${esc(t.refuse_reason || '')}</span>`}</div>` +
        `<div class="row-wrap">${confirmBtn}<button class="btn small${open ? ' primary' : ''}" data-try="${esc(t.name)}" ${usable ? '' : 'disabled'} title="${esc(usable ? '' : t.refuse_reason || '')}">${open ? '닫기' : '써 보기'}</button></div></div>` +
        (S.confirming === t.name ? confirmForm(t) : '') +
        UI.fold(`입력 형식 · ${fields.length}칸`, shape) + (open ? tryForm(s, t, fields) : '') + '</li>';
    }).join('')}</ul>`;
    pane.querySelectorAll('[data-try]').forEach(b => b.addEventListener('click', () => { S.trying = S.trying === b.dataset.try ? null : b.dataset.try; renderTools(s, r); }));
    pane.querySelectorAll('[data-confirm]').forEach(b => b.addEventListener('click', () => { S.confirming = S.confirming === b.dataset.confirm ? null : b.dataset.confirm; renderTools(s, r); }));
    pane.querySelectorAll('[data-unconfirm]').forEach(b => b.addEventListener('click', () => readConfirm(s, b.dataset.unconfirm, false)));
    pane.querySelector('#mcpConfirmSave')?.addEventListener('click', () => readConfirm(s, S.confirming, true));
    if (S.trying) wireTry(s, r.tools.find(t => t.name === S.trying));
  }

  function confirmForm(t) {
    return `<div class="form mcp-confirm">${UI.section('', UI.field({ label: '확인한 사람', required: true, input: '<input id="mcpConfirmBy" placeholder="강사 이름">' }) +
      UI.field({ label: '읽기라고 본 이유', required: true, input: '<input id="mcpConfirmReason" placeholder="예: 서버 문서상 검색 결과만 돌려주고 아무것도 바꾸지 않는다">',
        hint: `서버가 ${esc(t.name)} 에 읽기 전용 표시를 붙이지 않았습니다. 확인하면 에이전트 도구로 붙고 써 보기도 됩니다. 쓰기로 표시했거나 이름이 쓰기인 도구는 확인할 수 없습니다` }))}` +
      `${UI.actions('<button class="btn primary" id="mcpConfirmSave">읽기로 확인</button>')}</div>`;
  }

  async function readConfirm(s, tool, on) {
    const by = on ? (S.el.querySelector('#mcpConfirmBy') || {}).value : '포털';
    const reason = on ? (S.el.querySelector('#mcpConfirmReason') || {}).value : '';
    try {
      await postJ(api(`/api/mcp/servers/${encodeURIComponent(s.name)}/read-confirm`), { tool, on, by, reason });
      UI.toast(`${s.name}: ${tool} ${on ? '읽기로 확인했습니다' : '확인을 취소했습니다'}`, { tone: 'ok' }); S.confirming = null;
    } catch (e) { UI.toast(`${s.name}: ${e.message}`, { tone: 'neg' }); return; }
    await load();
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

  // ---------------------------------------------------------------- B2 등록 · 고치기 · 지우기 · 연결 검사 · 되돌리기
  function gateLine(s) {
    const c = s.check || {};
    const when = c.checked_at ? ` · ${esc(UI.dateTime(c.checked_at))}` : '';
    if (s.selectable) return `<p class="kv-line">${UI.chipText('에이전트 도구로 고를 수 있음', 'success')} 연결 검사 통과${when} — 읽기 전용 도구만 에이전트에 붙습니다</p>`;
    return `<p class="kv-line">${UI.chipText('에이전트 도구로 고를 수 없음', 'warning')} ${esc(CHECK[c.status] || '연결 검사 전')}${when}` +
      `${c.status === 'failed' && c.error ? ` — ${esc(c.error)}` : ''}${c.status === 'ok' ? ' — 읽기 전용으로 표시한 도구가 없습니다(표시만 없는 도구는 "읽기로 확인")' : ''}</p>`;
  }

  async function checkSaved(name) {
    S.tools[name] = { loading: true }; renderServers(); if (S.sel === name) renderDetail();
    try {
      const r = await postJ(api(`/api/mcp/servers/${encodeURIComponent(name)}/check`), { timeout: 8, by: '포털' });
      UI.toast(r.check.status === 'ok' ? `${name}: 연결 검사 통과 · 도구 ${r.check.tools.length}개` : `${name}: 연결 검사 실패 — ${r.check.error || ''}`, { tone: r.check.status === 'ok' ? 'pos' : 'neg' });
    } catch (e) { UI.toast(`${name}: ${e.message}`, { tone: 'neg' }); }
    await load();
  }

  function openForm(s) {
    const editing = !!s;
    const v = editing ? { name: s.name, transport: s.transport || 'streamable_http', command: s.command || '', args: (s.args || []).join(' '), url: s.url || '',
      env: Object.entries(s.env || {}).map(([k, x]) => `${k}=${x}`).join('\n'), headers: Object.entries(s.headers || {}).map(([k, x]) => `${k}=${x}`).join('\n'),
      description: s.description || '' } : { name: '', transport: 'streamable_http', command: '', args: '', url: '', env: '', headers: '', description: '' };
    S.form = { editing, v, result: null, busy: false, error: '' };
    renderForm(); S.el.querySelector('#mcpForm').scrollIntoView({ block: 'nearest' });
  }

  function readForm() {
    const box = S.el.querySelector('#mcpForm');
    box.querySelectorAll('[data-f]').forEach(i => { S.form.v[i.dataset.f] = i.value; });
    return S.form.v;
  }

  function renderForm() {
    const box = S.el.querySelector('#mcpForm');
    const F = S.form;
    if (!F) { box.innerHTML = ''; return; }
    const v = F.v, stdio = v.transport === 'stdio';
    const opt = (val, label) => `<option value="${val}" ${v.transport === val ? 'selected' : ''}>${label}</option>`;
    const fields = [
      UI.field({ label: '이름', required: true, input: `<input data-f="name" value="${esc(v.name)}" ${F.editing ? 'disabled' : ''} placeholder="my-folder">`, hint: '소문자 · 숫자 · 하이픈. 에이전트 도구 칸에 이 이름을 적습니다' }),
      UI.field({ label: '전송 방식', required: true, input: `<select data-f="transport">${opt('streamable_http', 'HTTP (streamable)')}${opt('sse', 'SSE (구형)')}${opt('stdio', '명령형 (stdio)')}</select>`,
        hint: stdio ? '연결 검사는 process 컨테이너 안에서 이 명령을 띄웁니다 — 컨테이너에 없는 명령은 "명령 없음"으로 거절됩니다' : '주소는 process 컨테이너에서 닿아야 합니다(내 PC 의 서버면 host.docker.internal)' }),
      stdio ? UI.field({ label: '명령', required: true, input: `<input data-f="command" value="${esc(v.command)}" placeholder="npx">`, hint: '실행기만 받습니다: npx · uvx · uv · node · python · deno · bunx · pipx' }) : '',
      stdio ? UI.field({ label: '인자', input: `<input data-f="args" value="${esc(v.args)}" placeholder="-y @modelcontextprotocol/server-filesystem /data">`, hint: '공백으로 나눕니다' }) : '',
      stdio ? UI.field({ label: '환경변수', input: `<textarea data-f="env" rows="2" placeholder="이름=값 (한 줄에 하나)">${esc(v.env)}</textarea>`, hint: '비밀은 \${SECRET:이름} 으로 적고 값은 "비밀 값"에 넣으세요. 값을 그대로 적으면 저장하되 화면 · 응답에서는 ******** 로 가립니다' }) : '',
      !stdio ? UI.field({ label: '주소', required: true, input: `<input data-f="url" value="${esc(v.url)}" placeholder="http://host.docker.internal:8301/mcp">` }) : '',
      !stdio ? UI.field({ label: '접속 헤더', input: `<textarea data-f="headers" rows="2" placeholder="Authorization=Bearer \${SECRET:GOOGLE_TOKEN}">${esc(v.headers)}</textarea>`,
        hint: '토큰은 값 대신 \${SECRET:이름} 으로 적고, 값은 위 "비밀 값"에 넣으세요(구글 연결 방법은 사용자 안내 T5). 값을 그대로 적으면 저장하되 화면에서는 ******** 로 가립니다' }) : '',
      UI.field({ label: '설명', input: `<input data-f="description" value="${esc(v.description)}" placeholder="이 서버가 하는 일 한 줄">` }),
    ].join('');
    box.innerHTML = `<section class="card mcp-form"><header class="card-head"><div class="card-title"><h3>${F.editing ? `서버 고치기 — ${esc(v.name)}` : '서버 등록'}</h3></div>` +
      `<div class="card-actions"><button class="btn small" id="mcpFormClose">닫기</button></div></header>` +
      `<div class="form">${UI.section('', fields)}${UI.actions(`<button class="btn" id="mcpDry" ${F.busy ? 'disabled' : ''}>연결 검사만</button>` +
        `<button class="btn primary" id="mcpSave" ${F.busy ? 'disabled' : ''}>${F.editing ? '검사 후 저장' : '검사 후 등록'}</button>`, F.error)}</div>` +
      `<div id="mcpFormResult" aria-live="polite">${F.busy ? '<p class="muted" role="status">연결 검사 중… (최대 8초)</p>' : checkHtml(F.result)}</div></section>`;
    box.querySelector('#mcpFormClose').addEventListener('click', () => { S.form = null; renderForm(); });
    box.querySelector('[data-f="transport"]').addEventListener('change', () => { readForm(); renderForm(); });
    box.querySelector('#mcpDry').addEventListener('click', () => submitForm(true));
    box.querySelector('#mcpSave').addEventListener('click', () => submitForm(false));
  }

  function checkHtml(c) {
    if (!c) return '';
    if (c.status !== 'ok') return `<p class="field-error" role="alert">연결 검사 실패 — ${esc(c.error || '사유 없음')}</p>`;
    return `<p class="kv-line">${UI.chipText('연결 검사 통과', 'success')} 도구 <b>${c.tools.length}</b>개 · ${c.elapsed_ms} ms</p>` +
      `<ul class="mcp-tools">${c.tools.map(t => `<li class="mcp-tool"><b>${esc(t.name)}</b> ` +
        (t.read_only ? UI.chipText('에이전트에 붙일 수 있음', 'success') : UI.chipText('붙일 수 없음', 'warning')) +
        `<span class="mcp-desc">${esc(t.description || '설명 없음')}</span>${t.read_only ? '' : `<span class="mcp-why">${esc(t.reason || '')}${t.confirmable ? ' — 등록 뒤 강사가 "읽기로 확인"할 수 있습니다' : ''}</span>`}</li>`).join('')}</ul>`;
  }

  async function submitForm(dry) {
    const F = S.form;
    let body;
    try { body = bodyFrom(readForm()); } catch (e) { F.error = e.message; renderForm(); return; }
    body.timeout = 8; body.by = '포털';
    F.busy = true; F.error = ''; F.result = null; renderForm();
    try {
      const r = dry ? await postJ(api('/api/mcp/check'), body)
        : F.editing ? await postJ(api(`/api/mcp/servers/${encodeURIComponent(body.name)}`), body, 'PUT')
        : await postJ(api('/api/mcp/servers'), body);
      F.result = r.check; F.busy = false;
      if (!dry) {
        UI.toast(`${body.name}: ${F.editing ? '고쳤습니다' : '등록했습니다'} · 에이전트에 붙일 수 있는 도구 ${r.gate.read_tools.length}개`, { tone: 'ok' });
        (r.warnings || []).forEach(w => UI.toast(`${body.name}: ${w}`, { tone: 'neg' }));
        S.form = null; renderForm(); S.sel = body.name; await load(); return;
      }
    } catch (e) {
      F.busy = false; F.error = e.message;
    }
    renderForm();
  }

  async function removeServer(s) {
    const using = s.agents.map(a => a.name);
    const ok = await UI.confirm({ title: `${s.name} 서버를 지울까요?`, body: using.length ? `이 서버를 도구로 적은 에이전트: ${using.join(', ')} — 지우면 그 에이전트는 이 서버 없이 실행됩니다.` : '검사 기록도 함께 지웁니다.', ok: '지우기', danger: true });
    if (!ok) return;
    try {
      await requestJ(api(`/api/mcp/servers/${encodeURIComponent(s.name)}?force=${using.length ? 'true' : 'false'}&by=${encodeURIComponent('포털')}`), { method: 'DELETE' });
      UI.toast(`${s.name}: 지웠습니다`, { tone: 'ok' }); S.sel = null;
    } catch (e) { UI.toast(`${s.name}: ${e.message}`, { tone: 'neg' }); }
    await load();
  }

  // ---------------------------------------------------------------- G2 비밀 값 (${SECRET:이름}) — 값은 넣기만 하고 다시 보이지 않는다
  async function loadSecrets() {
    const box = S.el.querySelector('#mcpSecrets');
    try { S.secrets = await getJ(api('/api/mcp/secrets')); }
    catch (e) { box.innerHTML = UI.fold('비밀 값', UI.empty('비밀 값 목록을 불러오지 못했습니다', e.message, 'compact'), { cls: 'plain' }); return; }
    renderSecrets();
  }

  function renderSecrets() {
    const box = S.el.querySelector('#mcpSecrets');
    const list = (S.secrets && S.secrets.secrets) || [];
    const missing = list.filter(x => x.missing).length;
    const rows = list.length ? `<ul class="mcp-tools">${list.map(x => `<li class="mcp-tool"><div class="mcp-tool-head"><div><b>${esc(x.key)}</b> ` +
      (x.stored ? UI.chipText('저장됨', 'success') : x.from_env ? UI.chipText('환경 변수', 'neutral') : UI.chipText('값 없음', 'danger')) +
      `<span class="mcp-desc">${x.used_by.length ? '쓰는 서버: ' + x.used_by.map(esc).join(', ') : '쓰는 서버 없음'}${x.updated_at ? ' · ' + esc(UI.dateTime(x.updated_at)) + ' ' + esc(x.updated_by || '') : ''}</span></div>` +
      (x.stored ? `<button class="btn small" data-secret-del="${esc(x.key)}">지우기</button>` : '') + '</div></li>').join('')}</ul>` : '<p class="muted">아직 없습니다.</p>';
    const form = `<div class="form">${UI.section('', UI.field({ label: '이름', required: true, input: '<input id="mcpSecretKey" placeholder="GOOGLE_TOKEN">', hint: '대문자 · 숫자 · 밑줄' }) +
      UI.field({ label: '값', required: true, input: '<input id="mcpSecretValue" type="password" autocomplete="off">', hint: '저장하면 다시 보이지 않습니다. 토큰이 만료되면 같은 이름으로 다시 넣으세요' }))}` +
      `${UI.actions('<button class="btn primary" id="mcpSecretSave">저장</button>')}</div>`;
    box.innerHTML = UI.fold(`비밀 값 <span class="chip tone-neutral sm">${list.length}</span>${missing ? ` ${UI.chipText('값 없음 ' + missing, 'danger')}` : ''}`,
      `<p class="field-hint">${esc((S.secrets && S.secrets.rule) || '')}</p>` + rows + form, { cls: 'plain', open: missing > 0 });
    box.querySelector('#mcpSecretSave')?.addEventListener('click', async () => {
      const key = box.querySelector('#mcpSecretKey').value.trim(), value = box.querySelector('#mcpSecretValue').value;
      try { await postJ(api(`/api/mcp/secrets/${encodeURIComponent(key)}`), { value, by: '포털' }, 'PUT'); UI.toast(`${key}: 저장했습니다`, { tone: 'ok' }); }
      catch (e) { UI.toast(e.message, { tone: 'neg' }); return; }
      await loadSecrets();
    });
    box.querySelectorAll('[data-secret-del]').forEach(b => b.addEventListener('click', async () => {
      try { await requestJ(api(`/api/mcp/secrets/${encodeURIComponent(b.dataset.secretDel)}?by=${encodeURIComponent('포털')}`), { method: 'DELETE' }); }
      catch (e) { UI.toast(e.message, { tone: 'neg' }); return; }
      await loadSecrets();
    }));
  }

  async function resetAll() {
    const ok = await UI.confirm({ title: '도구 서버를 기준으로 되돌릴까요?', body: '내가 등록한 서버 · 포털 밖에서 추가한 서버, 모든 연결 검사 기록, 비밀 값을 지웁니다. 기준(기본 제공) 서버는 그대로입니다.', ok: '되돌리기', danger: true });
    if (!ok) return;
    try {
      const r = await postJ(api('/api/mcp/reset'), { by: '포털' });
      UI.toast(`기준으로 되돌림 — 서버 ${r.removed_servers.length}개 · 검사 기록 ${r.removed_checks}개 지움`, { tone: 'ok' }); S.sel = null; S.form = null; renderForm();
    } catch (e) { UI.toast(e.message, { tone: 'neg' }); }
    await load();
  }

  function mount(el) {
    if (!el) return;
    S.el = el;
    el.innerHTML = `<div class="page-head"><h1>도구(MCP)</h1><div class="page-tools"><button class="btn small primary" id="mcpAdd">서버 등록</button>` +
      `<button class="btn small" id="mcpReload">다시 읽기</button><button class="btn small" id="mcpReset">기준으로 되돌리기</button></div></div>` +
      `<p class="muted">에이전트가 쓰는 도구 서버와 그 도구를 봅니다. 내 서버를 등록하면 연결 검사를 통과해야 저장되고, 그 서버의 읽기 전용 도구만 에이전트 도구로 고를 수 있습니다. ` +
      `읽기 전용 도구는 직접 불러 결과를 보고, 처리 건에서 언제 불렸는지 확인합니다.</p>` +
      `<div id="mcpSecrets"></div><div id="mcpForm"></div><div class="mcp-grid" id="mcpServers"></div><div id="mcpDetail"></div>`;
    el.querySelector('#mcpReload').addEventListener('click', load);
    el.querySelector('#mcpAdd').addEventListener('click', () => openForm(null));
    el.querySelector('#mcpReset').addEventListener('click', resetAll);
    load(); loadSecrets();
  }

  window.hydMcp = { mount, form, register };
  if (typeof document === 'undefined') return;
  const host = () => document.getElementById('mcpView');
  document.querySelector('.rail nav button[data-tab="mcp"]')?.addEventListener('click', () => { const el = host(); if (el && S.el !== el) mount(el); });
})();
