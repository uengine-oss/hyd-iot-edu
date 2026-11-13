/* U3 도구 연결(MCP) — window.hydMcp.mount(el) 이 그린다.
   ① 도구 지도: tenants.mcp 서버 → 연결 상태(시간 제한) → 도구(사전 이름 · 입력 형식 · 읽기 전용 판정) → 이 서버로 실제로 도는 에이전트 단계 · 담당
   ② 도구 써 보기: 도구 고르기 → 입력 형식에서 만든 폼 → 실제 호출 → 결과 (읽기 전용 도구만, 결과 크기 제한)
   ③ 호출 기록: events 에서 그 도구가 불린 처리 건 · task · 입력 · 결과 요약 · 시각 → #/instances/<id>/task/<taskId>
   ④ 서버 직접 등록 · 고치기 · 지우기 · 연결 검사 · 기준으로 되돌리기 · 비밀 값: 폼 → 연결 검사 통과해야 저장(실패는 사유), 기준 서버는 보기만.
      등록하는 서버는 HTTP 주소 하나다(명령형 stdio 는 서버가 받지 않는다 — 명령으로 띄우는 서버는 HTTP 로 띄워 등록).
   도구 이름은 이름 사전 하나(plainWords.js hydWords.toolName)로 보인다. 서버가 준 도구 설명은 에이전트가 읽는 원문이라 접어 둔다.
   원본: process-gpt-vue3 account-settings/MCPServer.vue(서버 목록 + 검사 요약 · 도구 수 · 펼침) · process-gpt-mcp-validator(도구 목록 · 실패 사유).
   수업 경계: 서버 등록 · 고치기 · 비밀값 · 읽기로 확인은 행동 키 tool_servers.register — 서버(GET /api/course-access)가 막으면 그 단추만
   꺼지고 까닭이 글로 보인다(courseAccess.js). 이 화면은 스크립트가 실렸는지로 단계를 판정하지 않는다.
   API: procsvc/mcp_api.py (/api/mcp/servers · /api/mcp/servers/{name}/tools · …/tools/{tool}/call · /api/mcp/calls),
        procsvc/mcp_registry.py (POST /api/mcp/servers · PUT/DELETE /api/mcp/servers/{name} · POST …/{name}/check · POST /api/mcp/check ·
        POST …/{name}/read-confirm · POST /api/mcp/reset), procsvc/mcp_secrets.py (/api/mcp/secrets). */
(function () {
  // 누가 했나 = 이 PC의 담당자 id(서버 inbox.actor_or_400 은 이름과 id 를 모두 받는다 — 다른 화면(flows.js)과 같이 id 를 보낸다).
  // 담당자를 못 읽었으면 다른 값으로 대신하지 않고 그 자리에서 막는다
  const NEED_ME = '담당자 정보를 읽지 못해 보낼 수 없습니다. 화면을 새로 고친 뒤 다시 해 주세요.';
  function actor() { const id = window.hydInbox?.me?.()?.id || ''; if (!id) UI.toast(NEED_ME, { tone: 'neg', timeout: 8000 }); return id; }
  // ---------------------------------------------------------------- 입력 형식(JSON Schema) → 폼 칸
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

  // ---------------------------------------------------------------- 등록 폼 → 요청 본문
  // 이름=값 줄(접속 헤더). 빈 줄은 건너뛴다. 값의 ******** 는 그대로 보내면 서버가 같은 이름 칸의 옛 비밀값을 유지한다.
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
    const url = String(v.url || '').trim();
    if (!url) throw new Error('주소: 도구 서버의 HTTP 주소가 필요합니다 (예: http://host.docker.internal:8301/mcp)');
    const body = { name, transport: v.transport || 'streamable_http', url };
    const headers = pairsFrom(v.headers, '접속 헤더');
    if (Object.keys(headers).length) body.headers = headers;
    const d = String(v.description || '').trim();
    if (d) body.description = d;
    return body;
  }

  // ---------------------------------------------------------------- 화면
  const T = { streamable_http: 'HTTP', sse: 'SSE(구형)' };      // 카드 칩과 등록 폼이 같은 이름을 쓴다
  const KIND = { refused: '연결 거부', unreachable: '주소 없음', timeout: '시간 초과', auth: '인증 실패', not_mcp: '도구 연결 형식 아님',
    protocol: '프로토콜 오류', server: '서버 오류', closed: '연결 끊김', too_large: '응답 너무 큼', config: '설정 오류', secret: '비밀 값 없음' };
  const S = { el: null, servers: [], tools: {}, sel: null, tab: 'tools', trying: null, results: {}, calls: {}, callTool: '', form: null,
    confirming: null, secrets: null, listTimeout: null, acting: new Set() };
  const api = p => API.process + p;
  const REGISTER = 'tool_servers.register';                 // 수업 경계 행동 키(서버 course_policy.ACTIONS)
  const reg = () => window.hydCourseAccess.attrs(REGISTER);
  const serverLabel = n => hydWords.serverName(n, S.servers.find(s => s.name === n)?.description);
  // 도구 이름은 이름 사전 하나 — 서버가 준 설명(에이전트가 읽는 지시문)을 이름 자리에 쓰지 않는다(H-9: 설명 속 낱말이 이름처럼 보였다)
  const toolLabel = (srv, name) => hydWords.toolName(`mcp__${srv}__${name}`);
  const fieldLabel = f => {
    return [f.label,f.description,window.hydWords?.fieldName(f.key),UI.terms['var.'+f.key]].find(label=>label && /[가-힣]/.test(label)) || `입력 칸(원래 이름 ${f.key})`;
  };
  // 두 번 눌림 막기: 같은 일이 끝날 때까지 그 단추를 끈다
  async function once(key, button, work) {
    if (S.acting.has(key)) return;
    S.acting.add(key); if (button) button.disabled = true;
    try { await work(); } finally { S.acting.delete(key); if (button && button.isConnected) button.disabled = false; }
  }

  const ORIGIN = { seed: ['기준', 'neutral'], user: ['내가 등록', 'accent'], external: ['포털 밖에서 추가', 'warning'] };
  const CHECK = { ok: '연결 검사 통과', failed: '연결 검사 실패', stale: '설정이 바뀌어 다시 검사 필요', never: '연결 검사 전' };
  function originChip(s) { const o = ORIGIN[s.origin]; return o ? UI.chipText(o[0], o[1]) : ''; }

  function statusChip(name) {
    const r = S.tools[name];
    const s = S.servers.find(x => x.name === name);
    if (s && s.config_error) return UI.chipText('설정 오류', 'danger');
    if (!r || r.loading) return UI.chipText('연결 확인 중', 'neutral');
    if (r.status === 'ok') return UI.chipText('연결됨', 'success');
    return UI.chipText(KIND[r.error_kind] || '연결 실패', 'danger');
  }

  async function load() {
    const box = S.el.querySelector('#mcpServers');
    box.innerHTML = `<div class="muted" role="status">${esc(UI.t('loading'))}</div>`;
    try { const r = await getJ(api('/api/mcp/servers')); S.servers = r.servers || []; S.listTimeout = r.list_timeout_s; }
    catch (e) { box.innerHTML = UI.errorBlock('도구 서버 목록을 불러오지 못했습니다', e.message, { retry: true, cls: 'compact' }); box.querySelector('[data-retry]').addEventListener('click', load); return; }
    S.tools = {};
    if (S.sel && !S.servers.some(s => s.name === S.sel)) S.sel = null;
    renderServers(); renderDetail();
    S.servers.filter(s => !s.config_error).forEach(s => probe(s.name));
  }

  async function probe(name) {
    S.tools[name] = { loading: true }; renderServers(); if (S.sel === name) renderDetail();
    try { S.tools[name] = await getJ(api(`/api/mcp/servers/${encodeURIComponent(name)}/tools`)); }      // 시간 한도는 서버 기본값(list_timeout_s)
    catch (e) { S.tools[name] = { status: 'failed', error: e.message, error_kind: null, tools: [] }; }
    renderServers(); if (S.sel === name) renderDetail();
  }

  const stepsText = s => [...new Set(s.tasks.map(t => t.activity_name))].length;
  function renderServers() {
    const box = S.el.querySelector('#mcpServers');
    if (!S.servers.length) { box.innerHTML = UI.empty('등록된 도구 서버가 없습니다', '기준 도구 서버가 없으면 시작.bat을 다시 실행하세요.', 'compact'); return; }
    box.innerHTML = S.servers.map(s => {
      const r = S.tools[s.name] || {};
      const n = r.status === 'ok' ? r.tools.length : null;
      const sub = s.config_error ? '연결 설정 오류' : r.status === 'failed' ? esc(KIND[r.error_kind] || '연결 검사 실패') : s.description && /[가-힣]/.test(s.description) ? esc(s.description) : '[도구 보기]를 누르면 연결 설정을 볼 수 있습니다';
      const who = s.agents.length ? s.agents.map(a => esc(a.name)).join(', ') : '쓰는 에이전트 없음';
      const tasks = stepsText(s);
      return UI.card({
        title: esc(serverLabel(s.name)), chips: statusChip(s.name) + UI.chipText(T[s.transport] || '설정 오류', 'neutral') + originChip(s),
        value: n != null ? `<span class="kv">도구 <b class="num">${n}</b><small>개</small></span>` : '',
        sub, body: `<p class="kv-line">${who}${tasks ? ` · 이 서버로 도는 단계 <b>${tasks}</b>개` : ''}</p>` +
          `<p class="kv-line">${stampGap(s, r) ? `<span class="muted">${esc(stampGap(s, r))}</span>`
            : s.selectable ? '에이전트 도구로 고를 수 있음' : `<span class="muted">${esc(s.reason || '에이전트 도구로 고를 수 없음')}</span>`}</p>`,
        cls: 'clickable mcp-card' + (s.name === S.sel ? ' sel' : '') + (s.config_error || r.status === 'failed' ? ' failed' : ''),
        attrs: `data-name="${esc(s.name)}"`,      // 카드는 단추 역할을 갖지 않는다(단추 안의 단추가 되지 않게) — 키보드와 화면 읽기 도구는 [도구 보기] 단추를 쓴다
        actions: `<button class="btn small" data-open="${esc(s.name)}" aria-pressed="${s.name === S.sel}">도구 보기</button>`,
      });
    }).join('');
    box.querySelectorAll('.mcp-card').forEach(card => {
      card.addEventListener('click', () => select(card.dataset.name));      // 카드 어디를 눌러도 열린다([도구 보기] 단추의 누름도 여기로 올라온다)
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
    const agents = s.agents.length ? s.agents.map(a => `<b>${esc(a.name)}</b>`).join(', ') : '<span class="muted">이 서버를 쓰는 에이전트가 없습니다</span>';
    // 단계마다 실제 담당과 그 실행이 이 서버로 쓰는 도구(서버 계산 — agents_store.run_servers, 워커와 같은 규칙)
    const tasks = s.tasks.length ? s.tasks.map(t => `${esc(UI.flowName(t.activity_name))} <span class="muted">(${esc(t.agent || '담당 없음')}${t.fixed_tools ? ' · 정해진 조회 도구만' : ''})</span>`).join(' · ')
      : '<span class="muted">없음</span>';
    const limit = r.timeout_s || S.listTimeout;
    const status = s.config_error ? `<p class="field-error" role="alert">${esc(s.config_error)}</p>`
      : r.loading ? `<p class="muted" role="status">연결 확인 중…${S.listTimeout ? ` (최대 ${esc(S.listTimeout)}초)` : ''}</p>`
      : r.status === 'ok' ? `<p class="kv-line">연결됨 · 도구 <b>${tools.length}</b>개 · ${esc(hydTrace.fmtMs(r.elapsed_ms))} · ${esc(UI.dateTime(r.checked_at))} 확인</p>`
      : `<p class="field-error" role="alert">${esc(r.error || '연결 실패')}</p><p class="field-hint">${esc(r.checked_at ? UI.dateTime(r.checked_at) + ' 확인' + (limit ? ' · 제한 ' + limit + '초' : '') : '')}</p>`;
    const settings = [['서버 식별자', s.name], ['등록한 설명 원문', s.description || '–'], ['연결 오류 원문', s.config_error || r.error || '없음'], ['서버가 보고한 이름', r.server_info?.name || '–'],
      ['종류', T[s.transport] || '–'], ['주소', s.url || '–'], ...Object.entries(s.headers || {}).map(([k, v]) => ['접속 헤더 ' + k, v])];
    box.innerHTML = `<section class="card mcp-detail"><header class="card-head"><div class="card-title"><h3>${esc(serverLabel(s.name))}</h3>${statusChip(s.name)}</div>` +
      `<div class="card-actions"><button class="btn small" id="mcpProbe" ${r.loading || s.config_error ? 'disabled' : ''}>연결 검사</button>` +
      (s.editable ? `<button class="btn small" id="mcpEdit"${reg()}>고치기</button><button class="btn small" id="mcpDelete">지우기</button>` : '') +
      `</div></header>` +
      status + gateLine(s, r) +
      `<p class="kv-line">쓰는 에이전트: ${agents}</p><p class="kv-line">이 서버로 도는 단계: ${tasks}</p>` +
      UI.fold('설정 보기 (비밀값은 ******** 로 가림)', `<dl class="mcp-kv">${settings.map(([k, v]) => `<dt>${esc(k)}</dt><dd><code>${esc(v)}</code></dd>`).join('')}</dl>` +
        `<p class="field-hint">${s.editable ? '고치기는 연결 검사를 통과해야 저장됩니다.' : '기준(기본 제공) 서버는 고치거나 지울 수 없습니다 — 새 이름으로 등록해 쓰세요.'}</p>`) +
      UI.tabs([['tools', '도구', tools.length], ['calls', '호출 기록']], S.tab, 'data-mcp-tab') +
      `<div id="mcpPane"></div></section>`;
    box.querySelector('#mcpProbe')?.addEventListener('click', e => checkSaved(s.name, e.currentTarget));
    box.querySelector('#mcpEdit')?.addEventListener('click', () => openForm(s));
    box.querySelector('#mcpDelete')?.addEventListener('click', e => removeServer(s, e.currentTarget));
    box.querySelectorAll('[data-mcp-tab]').forEach(b => b.addEventListener('click', () => { S.tab = b.dataset.mcpTab; renderDetail(); }));
    if (S.tab === 'calls') renderCalls(s); else renderTools(s, r);
  }

  function renderTools(s, r) {
    const pane = S.el.querySelector('#mcpPane');
    if (r.loading) { pane.innerHTML = `<div class="muted" role="status">${esc(UI.t('loading'))}</div>`; return; }
    if (r.status !== 'ok') {
      pane.innerHTML = UI.errorBlock('도구 목록을 받지 못했습니다', s.config_error || r.error || '', { retry: !s.config_error, cls: 'compact' });
      pane.querySelector('[data-retry]')?.addEventListener('click', () => probe(s.name));
      return;
    }
    if (!r.tools.length) { pane.innerHTML = UI.empty('이 서버는 도구를 내놓지 않습니다', '', 'compact'); return; }
    const confirmed = new Set(s.read_confirmed || []);
    pane.innerHTML = `<ul class="mcp-tools">${r.tools.map(t => {
      const fields = fieldsOf(t.input_schema);
      const usable = t.callable || (confirmed.has(t.name) && t.confirmable);
      const shape = (fields.length ? `<table class="compact-table"><thead><tr><th>입력 칸</th><th>데이터 형식</th><th>설명</th></tr></thead><tbody>${fields.map(f =>
        `<tr><td><code>${esc(f.key)}</code>${f.required ? ' <i class="req">*</i>' : ''}</td><td>${esc(typeName(f))}</td><td>${esc(f.description || '–')}</td></tr>`).join('')}</tbody></table>` : '<p class="muted">입력 없음</p>') + `<p class="muted">도구 원래 이름 <code>${esc(t.name)}</code></p>`;
      const open = S.trying === t.name;
      // G2 ②: 표시(readOnlyHint)만 없는 도구는 강사가 읽기로 확인할 수 있다 — 확인한 도구는 에이전트 도구 · 써 보기에 들어간다
      const chip = t.callable ? UI.chipText('읽기 전용', 'success') : usable ? UI.chipText('읽기로 확인함', 'success') : UI.chipText('써 보기 불가', 'warning');
      const confirmBtn = !s.editable || t.callable ? '' : usable ? `<button class="btn small" data-unconfirm="${esc(t.name)}"${reg()}>확인 취소</button>`
        : t.confirmable ? `<button class="btn small" data-confirm="${esc(t.name)}"${reg()}>읽기로 확인</button>` : '';
      return `<li class="mcp-tool${open ? ' open' : ''}" data-tool="${esc(t.name)}"><div class="mcp-tool-head"><div><b>${esc(toolLabel(s.name, t.name))}</b> ` + chip +
        `<span class="mcp-desc">${UI.fold('에이전트가 읽는 설명 원문', `<p>${esc(t.description || '설명 없음')}</p>`, { cls: 'small' })}</span>${usable ? '' : `<span class="mcp-why">${esc(t.refuse_reason || '')}</span>`}</div>` +
        `<div class="row-wrap">${confirmBtn}<button class="btn small${open ? ' primary' : ''}" data-try="${esc(t.name)}" ${usable ? '' : 'disabled'} title="${esc(usable ? '' : t.refuse_reason || '')}">${open ? '닫기' : '써 보기'}</button></div></div>` +
        (S.confirming === t.name ? confirmForm(s, t) : '') +
        UI.fold(`입력 형식 · ${fields.length}칸`, shape) + (open ? tryForm(s, t, fields) : '') + '</li>';
    }).join('')}</ul>`;
    pane.querySelectorAll('[data-try]').forEach(b => b.addEventListener('click', () => { S.trying = S.trying === b.dataset.try ? null : b.dataset.try; renderTools(s, r); }));
    pane.querySelectorAll('[data-confirm]').forEach(b => b.addEventListener('click', () => { S.confirming = S.confirming === b.dataset.confirm ? null : b.dataset.confirm; renderTools(s, r); }));
    pane.querySelectorAll('[data-unconfirm]').forEach(b => b.addEventListener('click', () => readConfirm(s, b.dataset.unconfirm, false, b)));
    pane.querySelector('#mcpConfirmSave')?.addEventListener('click', e => readConfirm(s, S.confirming, true, e.currentTarget));
    if (S.trying) wireTry(s, r.tools.find(t => t.name === S.trying));
  }

  function confirmForm(s, t) {
    return `<div class="form mcp-confirm">${UI.section('', UI.field({ label: '읽기라고 본 이유', required: true, input: '<input id="mcpConfirmReason" placeholder="예: 서버 문서상 검색 결과만 돌려주고 아무것도 바꾸지 않는다">',
        hint: `서버가 ‘${toolLabel(s.name, t.name)}’에 읽기 전용 표시를 붙이지 않았습니다. 확인하면 에이전트 도구로 붙고 써 보기도 됩니다. 쓰기로 표시했거나 이름이 쓰기인 도구는 확인할 수 없습니다` }))}` +
      `${UI.actions(`<button class="btn primary" id="mcpConfirmSave"${reg()}>읽기로 확인</button>`)}</div>`;
  }

  function readConfirm(s, tool, on, button) {
    const by = actor(); if (!by) return;
    const reason = on ? ((S.el.querySelector('#mcpConfirmReason') || {}).value || '').trim() : '';
    if (on && !reason) { UI.toast('읽기라고 본 이유를 적으세요', { tone: 'neg' }); return; }
    return once('confirm:' + s.name + '/' + tool, button, async () => {
      try {
        await postJ(api(`/api/mcp/servers/${encodeURIComponent(s.name)}/read-confirm`), { tool, on, by, reason });
        UI.toast(`${serverLabel(s.name)}: ‘${toolLabel(s.name, tool)}’ ${on ? '읽기로 확인했습니다' : '확인을 취소했습니다'}`, { tone: 'ok' }); S.confirming = null;
      } catch (e) { UI.toast(`${serverLabel(s.name)}: ${e.message}`, { tone: 'neg' }); return; }
      await load();
    });
  }

  const typeName = f => ({ string: '글', number: '숫자', integer: '정수', boolean: '예/아니요', enum: '목록', json: 'JSON' })[f.type] + (f.required ? '' : ' · 선택');

  function inputFor(f) {
    const id = `mcpIn-${f.key}`;
    const ph = f.default != null ? `기본값 ${typeof f.default === 'string' ? f.default : JSON.stringify(f.default)}` : '';
    if (f.type === 'enum') return `<select id="${esc(id)}" data-key="${esc(f.key)}"><option value="">${f.required ? '고르세요' : '(비움)'}</option>${f.options.map(o => `<option value="${esc(o)}">${esc(hydWords.value(f.key, o))}</option>`).join('')}</select>`;
    if (f.type === 'boolean') return `<select id="${esc(id)}" data-key="${esc(f.key)}"><option value="">${f.required ? '고르세요' : '(비움)'}</option><option value="true">예</option><option value="false">아니요</option></select>`;
    if (f.type === 'json') return `<textarea id="${esc(id)}" data-key="${esc(f.key)}" rows="3" placeholder="${esc(ph || 'JSON 예: {} 또는 []')}"></textarea>`;
    return `<input id="${esc(id)}" data-key="${esc(f.key)}" ${f.type === 'number' || f.type === 'integer' ? 'inputmode="decimal"' : ''} placeholder="${esc(ph)}">`;
  }

  function tryForm(s, t, fields) {
    const res = S.results[s.name + '/' + t.name];
    const body = fields.length ? UI.section('', fields.map(f => UI.field({label:fieldLabel(f),required:f.required,
      input:inputFor(f),hint:typeName(f)}) + UI.fold('입력 식별자 · 설명 원문',`<code>${esc(f.key)}</code><p>${esc(f.description)}</p>`,{cls:'small'})).join('')) : '<p class="muted">입력 없이 부릅니다</p>';
    return `<div class="mcp-try"><div class="form">${body}${UI.actions('<button class="btn primary" id="mcpCall">실행해 보기</button>')}</div>` +
      `<p class="field-hint">실제 서버를 부릅니다. 읽기 전용 도구만 허용되며 처리 건 · 설비 · 업무 DB 를 바꾸지 않습니다. 결과가 아주 길면 앞부분만 보이고 잘린 크기를 함께 알려 줍니다.</p>` +
      `<div id="mcpResult" aria-live="polite">${res ? resultHtml(res) : ''}</div></div>`;
  }

  function resultHtml(res) {
    if (res.loading) return `<p class="muted" role="status">실행하는 중…</p>`;
    if (res.error) return `<p class="field-error" role="alert">${esc(res.error)}</p>`;
    const r = res.result;
    return `<p class="kv-line">${r.is_error ? UI.chipText('도구가 오류를 돌려줌', 'danger') : UI.chipText('결과', 'success')} · ${esc(hydTrace.fmtMs(res.elapsed_ms))} · ${r.size_chars.toLocaleString()}자` +
      `${r.truncated ? ` · <b>${r.limit_chars.toLocaleString()}자에서 잘림</b>` : ''} · 보낸 입력 <code>${esc(JSON.stringify(res.arguments))}</code></p>` +
      readable(r.text);
  }
  // 도구 결과는 {"result": "<JSON 글>"}처럼 한 번 더 감싸여 온다 — 풀어서 행이면 표로, 아니면 들여 쓴 JSON 으로. 원문은 접어 둔다
  function readable(text) {
    let v; try { v = JSON.parse(text); if (v && typeof v.result === 'string') v = JSON.parse(v.result); } catch (_) { return `<pre class="mcp-out">${esc(text)}</pre>`; }
    const rows = Array.isArray(v) ? v : Array.isArray(v?.rows) ? v.rows : null;
    const flat = rows && rows.length && rows.every(r => r && typeof r === 'object' && !Array.isArray(r));
    const cols = flat ? [...new Set(rows.flatMap(r => Object.keys(r)))] : [];
    const cell = x => esc(x == null ? '' : typeof x === 'object' ? JSON.stringify(x) : String(x));
    const colName = c => { const known = hydWords.fieldName(c); return /[가-힣]/.test(known) ? known : c; };      // 사전에 있는 열만 한국어 이름으로, 모르는 열은 원문 그대로
    const body = flat ? `<div class="table-scroll"><table class="compact-table"><thead><tr>${cols.map(c => `<th>${esc(colName(c))}</th>`).join('')}</tr></thead>`
        + `<tbody>${rows.slice(0, 100).map(r => `<tr>${cols.map(c => `<td>${cell(r[c])}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`
        + (rows.length > 100 ? `<p class="muted">${rows.length}행 중 100행만 표로 보입니다 — 나머지는 원문에</p>` : '')
      : `<pre class="mcp-out">${esc(JSON.stringify(v, null, 2))}</pre>`;
    return body + UI.fold('원문', `<pre class="mcp-out">${esc(text)}</pre>`, { cls: 'small' });
  }

  function wireTry(s, t) {
    if (!t) return;
    const fields = fieldsOf(t.input_schema);
    const key = s.name + '/' + t.name;
    S.el.querySelector('#mcpCall').addEventListener('click', async () => {
      const raws = {}; S.el.querySelectorAll('.mcp-try [data-key]').forEach(i => { raws[i.dataset.key] = i.value; });
      const { args, errors } = argsFrom(fields.map(f=>({...f,description:fieldLabel(f)})),raws);
      const out = S.el.querySelector('#mcpResult');
      if (errors.length) { out.innerHTML = `<p class="field-error" role="alert">${errors.map(esc).join('<br>')}</p>`; return; }
      const by = actor(); if (!by) return;
      const btn = S.el.querySelector('#mcpCall'); btn.disabled = true;
      S.results[key] = { loading: true }; out.innerHTML = resultHtml(S.results[key]);
      try { S.results[key] = await postJ(api(`/api/mcp/servers/${encodeURIComponent(s.name)}/tools/${encodeURIComponent(t.name)}/call`), { arguments: args, by }); }
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
    catch (e) { list.innerHTML = UI.errorBlock('호출 기록을 불러오지 못했습니다', e.message, { retry: true, cls: 'compact' }); list.querySelector('[data-retry]').addEventListener('click', () => renderCalls(s)); return; }
    if (S.sel !== s.name || S.tab !== 'calls') return;
    if (!r.calls.length) { list.innerHTML = UI.empty('아직 이 도구를 부른 처리 건이 없습니다', `최근 도구 이벤트 ${r.scanned}개에서 찾았습니다. 경보로 처리 건이 돌거나 에이전트에게 질문하면 여기 쌓입니다`, 'compact'); return; }
    const STATE = { done: ['완료', 'success'], error: ['오류', 'danger'], running: ['진행 중', 'accent'] };
    list.innerHTML = `<ul class="mcp-calls">${r.calls.map(c => {
      const [label, tone] = STATE[c.state] || ['–', 'neutral'];
      return `<li><div class="mcp-call-head"><span>${esc(UI.dateTime(c.at))}</span> ${UI.chipText(label, tone)} <b>${esc(toolLabel(c.server, c.tool))}</b>` +
        `${c.duration_ms != null ? ` <span class="muted">${esc(hydTrace.fmtMs(c.duration_ms))}</span>` : ''}</div>` +
        `<p class="kv-line">처리 건 <b>${esc(c.instance_name || UI.idText(c.proc_inst_id) || '–')}</b> · 단계 <b>${esc(c.task_name || '–')}</b>` +
        `${c.link ? ` · <a href="${esc(c.link)}">처리 건에서 보기</a>` : ''}</p>` +
        `<p class="kv-line mcp-io"><span>입력</span> <code>${esc(c.input_summary || '–')}</code></p>` +
        `<p class="kv-line mcp-io"><span>결과</span> <code>${esc(c.output_summary || (c.state === 'running' ? '아직 끝나지 않음' : '–'))}</code></p>` +
        UI.fold('입력 · 결과 전체', `<pre class="mcp-out">입력\n${esc(c.input || '–')}\n\n결과\n${esc(c.output || '–')}</pre>`) + '</li>';
    }).join('')}</ul>` + (r.scanned >= r.scan_limit ? `<p class="field-hint">최근 도구 이벤트 ${r.scan_limit}개까지만 훑었습니다. 그보다 오래된 호출은 처리 건 화면에서 보세요.</p>` : '');
  }

  // ---------------------------------------------------------------- 등록 · 고치기 · 지우기 · 연결 검사 · 되돌리기
  // 고를 수 있음 = 마지막 연결 검사 통과 기록(서버 게이트), 지금 상태 = 화면을 열 때 다시 잰 것 — 둘이 갈리면 지금 붙여도 된다고 읽히지 않게
  // 그 사실을 말한다(카드 · 상세가 이 한 문장을 쓴다, 2026-11-01 메뉴 눈 확인 · 11-02 독립 검증)
  function stampGap(s, r) {
    return s.selectable && r && r.status === 'failed'
      ? `지난 연결 검사는 통과했지만 지금은 연결되지 않습니다(${KIND[r.error_kind] || '연결 검사 실패'}) — 서버를 켠 뒤 다시 읽으세요` : '';
  }

  function gateLine(s, r) {
    const gap = stampGap(s, r);
    if (gap) return `<p class="kv-line">${UI.chipText('지금 연결 안 됨', 'warning')} ${esc(gap)}</p>`;
    const c = s.check || {};
    const when = c.checked_at ? ` · ${esc(UI.dateTime(c.checked_at))}` : '';
    if (s.selectable && s.origin === 'seed') return `<p class="kv-line">${UI.chipText('에이전트 도구로 고를 수 있음', 'success')} 기준 서버 — 기본 에이전트도 이 서버를 씁니다</p>`;
    if (s.selectable) return `<p class="kv-line">${UI.chipText('에이전트 도구로 고를 수 있음', 'success')} 연결 검사 통과${when} — 읽기 전용 도구만 에이전트에 붙습니다</p>`;
    return `<p class="kv-line">${UI.chipText('에이전트 도구로 고를 수 없음', 'warning')} ${esc(s.reason || CHECK[c.status] || '연결 검사 전')}${when}</p>`;
  }

  function checkSaved(name, button) {
    const by = actor(); if (!by) return;
    return once('check:' + name, button, async () => {
      S.tools[name] = { loading: true }; renderServers(); if (S.sel === name) renderDetail();
      try {
        const r = await postJ(api(`/api/mcp/servers/${encodeURIComponent(name)}/check`), { by });
        UI.toast(r.check.status === 'ok' ? `${serverLabel(name)}: 연결 검사를 통과했습니다. 도구 ${r.check.tools.length}개` : `${serverLabel(name)}: 연결 검사에 실패했습니다. ${r.check.error || ''}`, { tone: r.check.status === 'ok' ? 'ok' : 'neg' });
      } catch (e) { UI.toast(`${serverLabel(name)}: ${e.message}`, { tone: 'neg' }); }
      await load();
    });
  }

  function openForm(s) {
    const editing = !!s;
    const v = editing ? { name: s.name, transport: s.transport || 'streamable_http', url: s.url || '',
      headers: Object.entries(s.headers || {}).map(([k, x]) => `${k}=${x}`).join('\n'), description: s.description || '' }
      : { name: '', transport: 'streamable_http', url: '', headers: '', description: '' };
    S.form = { editing, v, result: null, busy: false, error: '' };
    S.el.querySelector('#mcpOperator').open = true;
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
    const v = F.v;
    const opt = (val, label) => `<option value="${val}" ${v.transport === val ? 'selected' : ''}>${label}</option>`;
    const fields = [
      UI.field({ label: '이름', required: true, input: `<input data-f="name" value="${esc(v.name)}" ${F.editing ? 'disabled' : ''} placeholder="my-folder">`, hint: '소문자 · 숫자 · 하이픈. 에이전트 도구 칸에 이 이름을 적습니다' }),
      UI.field({ label: '연결 방식', required: true, input: `<select data-f="transport">${opt('streamable_http', T.streamable_http)}${opt('sse', T.sse)}</select>`,
        hint: '도구 서버를 HTTP 로 띄운 주소를 등록합니다. 명령으로 띄우는 서버도 HTTP 로 띄워 그 주소를 적습니다' }),
      UI.field({ label: '주소', required: true, input: `<input data-f="url" value="${esc(v.url)}" placeholder="http://host.docker.internal:8301/mcp">`,
        hint: '내 PC 에서 띄운 서버면 localhost 대신 host.docker.internal 을 씁니다' }),
      UI.field({ label: '접속 헤더', input: `<textarea data-f="headers" rows="2" placeholder="Authorization=Bearer \${SECRET:MY_TOKEN}">${esc(v.headers)}</textarea>`,
        hint: '토큰은 값 대신 \${SECRET:이름} 으로 적고, 값은 위 "비밀 값"에 넣으세요. 값을 그대로 적으면 저장하되 화면에서는 ******** 로 가립니다' }),
      UI.field({ label: '설명', input: `<input data-f="description" maxlength="200" value="${esc(v.description)}" placeholder="이 서버가 하는 일 한 줄">` }),
    ].join('');
    box.innerHTML = `<section class="card mcp-form"><header class="card-head"><div class="card-title"><h3>${F.editing ? `서버 고치기 — ${esc(v.name)}` : '서버 등록'}</h3></div>` +
      `<div class="card-actions"><button class="btn small" id="mcpFormClose">닫기</button></div></header>` +
      `<div class="form">${UI.section('', fields)}${UI.actions(`<button class="btn" id="mcpDry" ${F.busy ? 'disabled' : ''}${reg()}>연결 검사만</button>` +
        `<button class="btn primary" id="mcpSave" ${F.busy ? 'disabled' : ''}${reg()}>${F.editing ? '검사 후 저장' : '검사 후 등록'}</button>`, F.error)}</div>` +
      `<div id="mcpFormResult" aria-live="polite">${F.busy ? '<p class="muted" role="status">연결 검사 중…</p>' : checkHtml(F.result)}</div></section>`;
    box.querySelector('#mcpFormClose').addEventListener('click', () => { S.form = null; renderForm(); });
    box.querySelector('#mcpDry').addEventListener('click', () => submitForm(true));
    box.querySelector('#mcpSave').addEventListener('click', () => submitForm(false));
  }

  // 연결 검사 결과의 도구 이름: 카드와 같은 이름 사전을 먼저 쓴다. 사전에 없는 도구(아직 등록 전인 내 서버)는 서버가 준 한국어 제목, 그것도 없으면 원래 이름
  function checkToolName(t) {
    const raw = `mcp__${(S.form && S.form.v.name || '').trim()}__${t.name}`;
    return hydWords.knownTool(raw) ? hydWords.toolName(raw) : t.title && /[가-힣]/.test(t.title) ? t.title : t.name;
  }
  function checkHtml(c) {
    if (!c) return '';
    if (c.status !== 'ok') return `<p class="field-error" role="alert">연결 검사 실패 — ${esc(c.error || '사유 없음')}</p>`;
    return `<p class="kv-line">${UI.chipText('연결 검사 통과', 'success')} 도구 <b>${c.tools.length}</b>개 · ${esc(hydTrace.fmtMs(c.elapsed_ms))}</p>` +
      `<ul class="mcp-tools">${c.tools.map(t => `<li class="mcp-tool"><b>${esc(checkToolName(t))}</b> ` +
        (t.read_only ? UI.chipText('에이전트에 붙일 수 있음', 'success') : UI.chipText('붙일 수 없음', 'warning')) +
        `<span class="mcp-desc">${UI.fold('에이전트가 읽는 설명 원문', `<p>${esc(t.description || '설명 없음')}</p>`, { cls: 'small' })}</span>${t.read_only ? '' : `<span class="mcp-why">${esc(t.reason || '')}${t.confirmable ? ' — 등록 뒤 "읽기로 확인"할 수 있습니다' : ''}</span>`}</li>`).join('')}</ul>`;
  }

  async function submitForm(dry) {
    const F = S.form;
    if (F.busy) return;
    let body;
    try { body = bodyFrom(readForm()); } catch (e) { F.error = e.message; renderForm(); return; }
    body.by = actor(); if (!body.by) return;
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

  async function removeServer(s, button) {
    const by = actor(); if (!by) return;      // 확인을 묻기 전에 막는다
    const using = s.agents.map(a => a.name);
    const ok = await UI.confirm({ title: `${serverLabel(s.name)} 서버를 지울까요?`, body: using.length ? `이 서버를 쓰는 에이전트: ${using.join(', ')} — 지우면 그 에이전트는 이 서버 없이 실행됩니다.` : '검사 기록도 함께 지웁니다.', ok: '지우기', danger: true });
    if (!ok) return;
    return once('delete:' + s.name, button, async () => {
      try {
        await requestJ(api(`/api/mcp/servers/${encodeURIComponent(s.name)}?force=${using.length ? 'true' : 'false'}&by=${encodeURIComponent(by)}`), { method: 'DELETE' });
        UI.toast(`${serverLabel(s.name)}: 지웠습니다`, { tone: 'ok' }); S.sel = null;
      } catch (e) { UI.toast(`${serverLabel(s.name)}: ${e.message}`, { tone: 'neg' }); }
      await load();
    });
  }

  // ---------------------------------------------------------------- G2 비밀 값 (${SECRET:이름}) — 값은 넣기만 하고 다시 보이지 않는다
  async function loadSecrets() {
    const box = S.el.querySelector('#mcpSecrets');
    try { S.secrets = await getJ(api('/api/mcp/secrets')); }
    catch (e) { box.innerHTML = UI.fold('비밀 값', UI.errorBlock('비밀 값 목록을 불러오지 못했습니다', e.message, { retry: true, cls: 'compact' }), { cls: 'plain', open: true }); box.querySelector('[data-retry]').addEventListener('click', loadSecrets); return; }
    renderSecrets();
  }

  function renderSecrets() {
    const box = S.el.querySelector('#mcpSecrets');
    const list = (S.secrets && S.secrets.secrets) || [];
    const missing = list.filter(x => x.missing).length;
    const rows = list.length ? `<ul class="mcp-tools">${list.map(x => `<li class="mcp-tool"><div class="mcp-tool-head"><div><b>${esc(x.key)}</b> ` +
      (x.stored ? UI.chipText('저장됨', 'success') : UI.chipText('값 없음', 'danger')) +
      `<span class="mcp-desc">${x.used_by.length ? '쓰는 서버: ' + x.used_by.map(n => esc(serverLabel(n))).join(', ') : '쓰는 서버 없음'}${x.updated_at ? ' · ' + esc(UI.dateTime(x.updated_at)) + ' ' + esc(x.updated_by ? UI.who(x.updated_by) : '') : ''}</span></div>` +
      (x.stored ? `<button class="btn small" data-secret-del="${esc(x.key)}"${reg()}>지우기</button>` : '') + '</div></li>').join('')}</ul>` : '<p class="muted">아직 없습니다.</p>';
    const form = `<div class="form">${UI.section('', UI.field({ label: '이름', required: true, input: '<input id="mcpSecretKey" placeholder="MY_TOKEN">', hint: '대문자 · 숫자 · 밑줄' }) +
      UI.field({ label: '값', required: true, input: '<input id="mcpSecretValue" type="password" autocomplete="off">', hint: '저장하면 다시 보이지 않습니다. 토큰이 만료되면 같은 이름으로 다시 넣으세요' }))}` +
      `${UI.actions(`<button class="btn primary" id="mcpSecretSave"${reg()}>저장</button>`)}</div>`;
    box.innerHTML = UI.fold(`비밀 값 <span class="chip tone-neutral sm">${list.length}</span>${missing ? ` ${UI.chipText('값 없음 ' + missing, 'danger')}` : ''}`,
      `<p class="field-hint">${esc((S.secrets && S.secrets.rule) || '')}</p>` + rows + form, { cls: 'plain', open: missing > 0 });
    box.querySelector('#mcpSecretSave')?.addEventListener('click', e => once('secret:save', e.currentTarget, async () => {
      const key = box.querySelector('#mcpSecretKey').value.trim(), value = box.querySelector('#mcpSecretValue').value;
      if (!key) { UI.toast('비밀 값 이름을 적으세요 (대문자 · 숫자 · 밑줄)', { tone: 'neg' }); return; }
      if (!value) { UI.toast('비밀 값을 넣으세요', { tone: 'neg' }); return; }
      const by = actor(); if (!by) return;
      try { await postJ(api(`/api/mcp/secrets/${encodeURIComponent(key)}`), { value, by }, 'PUT'); UI.toast(`${key}: 저장했습니다`, { tone: 'ok' }); }
      catch (err) { UI.toast(err.message, { tone: 'neg' }); return; }
      await loadSecrets();
    }));
    box.querySelectorAll('[data-secret-del]').forEach(b => b.addEventListener('click', async () => {
      const key = b.dataset.secretDel, users = (list.find(x => x.key === key) || {}).used_by || [];
      const by = actor(); if (!by) return;
      if (!await UI.confirm({ title: `비밀 값 ${key} 을 지울까요?`, ok: '지우기', danger: true,
        body: users.length ? `이 값을 쓰는 서버(${users.map(n => serverLabel(n)).join(', ')})는 다시 넣을 때까지 연결 · 호출이 실패합니다. 지운 값은 되살릴 수 없습니다.` : '지운 값은 되살릴 수 없습니다.' })) return;
      await once('secret:del:' + key, b, async () => {
        try { await requestJ(api(`/api/mcp/secrets/${encodeURIComponent(key)}?by=${encodeURIComponent(by)}`), { method: 'DELETE' }); UI.toast(`${key}: 지웠습니다`, { tone: 'ok' }); }
        catch (err) { UI.toast(err.message, { tone: 'neg' }); return; }
        await loadSecrets();
      });
    }));
  }

  async function resetAll(button) {
    const by = actor(); if (!by) return;
    const ok = await UI.confirm({ title: '도구 서버를 기준으로 되돌릴까요?', body: '내가 등록한 서버 · 포털 밖에서 추가한 서버, 모든 연결 검사 기록, 비밀 값을 지웁니다. 기준(기본 제공) 서버는 그대로입니다.', ok: '되돌리기', danger: true });
    if (!ok) return;
    return once('reset', button, async () => {
      try {
        const r = await postJ(api('/api/mcp/reset'), { by });
        UI.toast(`기준으로 되돌렸습니다. 서버 ${r.removed_servers.length}개, 검사 기록 ${r.removed_checks}개, 비밀 값 ${r.removed_secrets}개를 지웠습니다.`, { tone: 'ok' }); S.sel = null; S.form = null; renderForm();
      } catch (e) { UI.toast(e.message, { tone: 'neg' }); }
      await load(); await loadSecrets();
    });
  }

  // 서버 직접 등록 자리 — 수업 단계(서버가 tool_servers.register 를 막음)면 까닭 한 줄과 꺼진 단추
  function renderOperator() {
    const why = window.hydCourseAccess.blocked(REGISTER);
    S.el.querySelector('[data-mcp-intro]').textContent = why ? '준비된 도구 서버와 도구를 보고, 읽기 전용 도구를 직접 불러 결과를 확인합니다. 처리 건 · 질문에서 언제 불렸는지도 봅니다.'
      : '에이전트가 쓰는 도구 서버와 그 도구를 봅니다. 내 서버를 등록하면 연결 검사를 통과해야 저장되고, 그 서버의 읽기 전용 도구만 에이전트 도구로 고를 수 있습니다. 읽기 전용 도구는 직접 불러 결과를 보고, 처리 건 · 질문에서 언제 불렸는지 확인합니다.';
    S.el.querySelector('[data-mcp-why]').textContent = why;
    S.el.querySelector('#mcpAdd').outerHTML = `<button class="btn small" id="mcpAdd"${reg()}>서버 직접 등록</button>`;
    S.el.querySelector('#mcpAdd').addEventListener('click', () => openForm(null));
  }

  function mount(el) {
    if (!el) return;
    S.el = el;
    el.innerHTML = `<div class="page-head"><h1>도구 연결</h1><div class="page-tools"><button class="btn small" id="mcpReload">다시 읽기</button></div></div>` +
      `<p class="muted" data-mcp-intro></p>` +
      `<details class="fold" id="mcpOperator"><summary>서버 직접 등록 · 비밀 값 · 기준으로 되돌리기</summary><p class="field-hint" data-mcp-why></p><div class="row"><button class="btn small" id="mcpAdd">서버 직접 등록</button><button class="btn small" id="mcpReset">기준으로 되돌리기</button></div><div id="mcpSecrets"></div><div id="mcpForm"></div></details><div class="mcp-grid" id="mcpServers"></div><div id="mcpDetail"></div>`;
    el.querySelector('#mcpReload').addEventListener('click', load);
    el.querySelector('#mcpReset').addEventListener('click', e => resetAll(e.currentTarget));
    renderOperator();
    loadSecrets();
    load();
  }
  // 수업 범위가 늦게 오거나 바뀌면 이 화면의 행동 단추를 다시 맞춘다
  window.hydCourseAccess.onChange(() => { if (!S.el) return; renderOperator(); renderDetail(); renderForm(); if (S.secrets) renderSecrets(); });

  window.hydMcp = { mount };
})();
