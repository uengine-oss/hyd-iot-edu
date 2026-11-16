/* U3 도구 연결(MCP) — window.hydMcp.mount(el) 이 그린다.
   ① 도구 지도: tenants.mcp 서버 → 연결 상태(시간 제한) → 도구(사전 이름 · 입력 형식 · 읽기 전용 판정) → 이 서버로 실제로 도는 에이전트 단계 · 담당
   ② 도구 써 보기: 도구 고르기 → 입력 형식에서 만든 폼 → 실제 호출 → 결과 (읽기 전용 도구만, 결과 크기 제한)
   ③ 호출 기록: events 에서 그 도구가 불린 처리 건 · task · 입력 · 결과 요약 · 시각 → #/instances/<id>/task/<taskId>
   ④ 서버 직접 등록 · 고치기 · 지우기 · 연결 검사 · 비밀 값: 폼 → 연결 검사 통과해야 저장(실패는 사유), 기준 서버는 보기만.
   화면은 목록 + 상세다(디자인기준 5-1 — 본: process-gpt-lite 인스턴스 화면): 왼쪽 서버 목록 │ 머리(이름 · 연결 상태 알약 · 보조 줄, 오른쪽 끝 [연결 검사]와 「…」)
   → 도구 목록 | 호출 기록(보기 탭) → 쓰는 곳(접기) → 연결 설정(접기). 화면 아래에 설정 줄(4-16 — 본: lite 설정 시트): 잠긴 까닭 · 비밀 값.
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
  const T = { streamable_http: 'HTTP', sse: 'SSE(구형)' };      // 목록 · 상세와 등록 폼이 같은 이름을 쓴다
  const KIND = { refused: '연결 거부', unreachable: '주소 없음', timeout: '시간 초과', auth: '인증 실패', not_mcp: '도구 연결 형식 아님',
    protocol: '프로토콜 오류', server: '서버 오류', closed: '연결 끊김', too_large: '응답 너무 큼', config: '설정 오류', secret: '비밀 값 없음' };
  const S = { el: null, servers: [], tools: {}, sel: null, tab: 'tools', trying: null, openCall: null, results: {}, callTool: '', form: null,
    confirming: null, secrets: null, listTimeout: null, acting: new Set() };
  const api = p => API.process + p;
  const REGISTER = 'tool_servers.register';                 // 수업 경계 행동 키(서버 course_policy.ACTIONS) — 등록 · 고치기 · 지우기 · 되돌리기 · 비밀 값이 같은 키다
  const reg = () => window.hydCourseAccess.attrs(REGISTER);
  const serverLabel = n => hydWords.serverName(n, S.servers.find(s => s.name === n)?.description);
  // 도구 이름은 이름 사전 하나 — 서버가 준 설명(에이전트가 읽는 지시문)을 이름 자리에 쓰지 않는다(H-9: 설명 속 낱말이 이름처럼 보였다)
  const toolLabel = (srv, name) => hydWords.toolName(`mcp__${srv}__${name}`);
  const fieldLabel = f => {
    return [f.label,f.description,window.hydWords?.fieldName(f.key),UI.terms['var.'+f.key]].find(label=>label && /[가-힣]/.test(label)) || ({ query: '질의문', params: '질의에 넣을 값', limit: '가져올 수', name: '이름', id: '식별자' }[f.key] || `입력 칸(원래 이름 ${f.key})`);
  };
  // 두 번 눌림 막기: 같은 일이 끝날 때까지 그 단추를 끈다
  async function once(key, button, work) {
    if (S.acting.has(key)) return;
    // 누른 단추가 「…중 · 걸린 시간」으로 바뀐다(다시 그려져 단추가 사라졌으면 손대지 않는다)
    S.acting.add(key); const end = button ? hydLive.busy(button, (button.textContent.trim() || button.getAttribute('aria-label') || '') + ' 중') : null;
    try { await work(); } finally { S.acting.delete(key); if (end && button.isConnected) end(false); }
  }

  const ORIGIN = { seed: '기본 제공', user: '내가 등록한 것', external: '포털 밖에서 추가한 것' };
  const icon = (name, cls) => UI.icon(name, cls);
  const tag = (label, tone) => `<span class="tag"${tone ? ` data-tone="${tone}"` : ''}>${esc(label)}</span>`;
  // 이름–값. 값이 없는 줄은 그리지 않는다
  const kv = rows => { const r = rows.filter(([, v]) => v != null && v !== ''); return r.length ? `<dl class="kv">${r.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${v}</dd>`).join('')}</dl>` : ''; };
  const CHECK = { ok: '연결 검사 통과', failed: '연결 검사 실패', stale: '설정이 바뀌어 다시 검사 필요', never: '연결 검사 전' };
  const failAlert = (title, why) => `<div class="alert" data-variant="destructive" role="alert">${icon('circle-alert')}<h2>${esc(title)}</h2>${why ? `<section>${why}</section>` : ''}</div>`;

  // 연결 상태 뱃지: 점 + 글(연결됨 초록 · 실패 빨강 · 확인 중 회색)
  function statusTag(name) {
    const r = S.tools[name];
    const s = S.servers.find(x => x.name === name);
    if (s && s.config_error) return tag('설정 오류', 'danger');
    if (!r || r.loading) return tag('연결 확인 중');
    if (r.status === 'ok') return tag('연결됨', 'ok');
    return tag(KIND[r.error_kind] || '연결 실패', 'danger');
  }

  async function load() {
    const box = S.el.querySelector('#mcpServers');
    box.innerHTML = Array.from({ length: 4 }, () => `<div class="sk-row"><div class="skeleton sk-line" style="width:55%"></div><div class="skeleton sk-line" style="width:35%"></div></div>`).join('');
    try { const r = await getJ(api('/api/mcp/servers')); S.servers = r.servers || []; S.listTimeout = r.list_timeout_s; }
    catch (e) { box.innerHTML = `<div class="pane-list-note">${UI.errorBlock('도구 서버 목록을 불러오지 못했습니다', e.message, { retry: true })}</div>`; box.querySelector('[data-retry]').addEventListener('click', load); return; }
    S.tools = {};
    if (S.sel && !S.servers.some(s => s.name === S.sel)) S.sel = null;
    if (!S.sel && S.servers.length) S.sel = S.servers[0].name;      // 상세 자리를 비워 두지 않는다 — 첫 서버를 고른 채 연다
    renderServers(); renderDetail();
    S.servers.filter(s => !s.config_error).forEach(s => probe(s.name));
  }

  async function probe(name) {
    S.tools[name] = { loading: true, since: new Date().toISOString() }; renderServers(); if (S.sel === name) renderDetail();
    try { S.tools[name] = await getJ(api(`/api/mcp/servers/${encodeURIComponent(name)}/tools`)); }      // 시간 한도는 서버 기본값(list_timeout_s)
    catch (e) { S.tools[name] = { status: 'failed', error: e.message, error_kind: null, tools: [] }; }
    renderServers(); if (S.sel === name) renderDetail();
  }

  // 목록 한 줄: 이름 + 연결 상태 뱃지 하나, 둘째 줄에 에이전트 도구로 고를 수 있는지(지금 연결이 끊겼으면 그 사실)
  function renderServers() {
    const box = S.el.querySelector('#mcpServers');
    if (!S.servers.length) { box.innerHTML = `<div class="pane-list-note">${UI.empty('등록된 도구 서버가 없습니다', '기본 제공 도구 서버가 없으면 시작 파일을 다시 실행하세요. 내 서버는 화면 위의 [서버 등록]으로 붙입니다.')}</div>`; return; }
    box.innerHTML = S.servers.map(s => {
      const r = S.tools[s.name] || {};
      // 줄의 보조 글: 도구 수만. 에이전트 도구로 고를 수 있는 것은 보통이라 줄마다 되풀이하지 않고, 고를 수 없을 때만 그 까닭을 적는다
      const count = r.status === 'ok' ? `도구 ${r.tools.length}개` : '';
      const sub = s.config_error ? '연결 설정 오류' : stampGap(s, r) || (s.selectable ? count || '도구 목록을 읽는 중' : [count, s.reason || '에이전트 도구로 고를 수 없음'].filter(Boolean).join(' · '));
      return `<button type="button" class="row" data-name="${esc(s.name)}"${s.name === S.sel && !S.form ? ' aria-current="true"' : ''}><span class="row-ic">${icon('plug')}</span>` +
        `<span class="row-title">${esc(serverLabel(s.name))}</span>${statusTag(s.name)}<span class="row-meta">${esc(sub)}</span></button>`;
    }).join('');
    box.querySelectorAll('[data-name]').forEach(item => item.addEventListener('click', () => select(item.dataset.name)));
  }

  function select(name) {
    S.sel = name; S.tab = 'tools'; S.trying = null; S.openCall = null; S.callTool = ''; S.removed = null;
    if (S.form) { S.form = null; renderForm(); }      // 다른 서버를 고르면 쓰던 등록 폼을 닫는다(상세 자리는 하나다)
    renderServers(); renderDetail(); UI.revealDetail(S.el.querySelector('#mcpPanel'));
  }

  /* 읽는 차례(디자인기준 5-1): 머리(이름 + 연결 상태 알약, 보조 줄 = 기본 제공인지 · 연결 방식 · 마지막 확인, 오른쪽 끝에 [연결 검사]와 「…」)
     → (그 상황일 때만) 연결 확인 중의 과정 · 연결 실패의 까닭 · 에이전트 도구로 고를 수 있는지 → 도구 목록 | 호출 기록(보기 탭) → 쓰는 곳(접기 — 에이전트 · 흐름) → 연결 설정(접기) */
  const row = (attrs, ic, title, right, meta) => `<button type="button" class="row" ${attrs}><span class="row-ic">${icon(ic)}</span><span class="row-title">${title}</span>${right || ''}${meta ? `<span class="row-meta">${meta}</span>` : ''}</button>`;
  function renderDetail() {
    const box = S.el.querySelector('#mcpDetail');
    if (S.form) { box.innerHTML = ''; return; }      // 등록 · 고치기 폼을 쓰는 동안 상세 자리는 폼이 쓴다
    const s = S.servers.find(x => x.name === S.sel);
    if (!s) { box.innerHTML = removedNote() + (S.servers.length ? `<div class="pane-none">${UI.empty({ title: '도구 서버를 고르세요', sub: '왼쪽 목록에서 고르면 그 서버의 도구와 호출 기록이 보입니다.' })}</div>` : ''); return; }
    const r = S.tools[s.name] || { loading: true };
    const tools = r.status === 'ok' ? r.tools : [];
    const limit = r.timeout_s || S.listTimeout;
    // 그 상황일 때만 뜨는 줄: 설정 오류 · 확인하는 동안의 과정 · 연결 실패의 까닭. 연결돼 있으면 머리의 알약과 보조 줄이 이미 말한다
    const status = s.config_error ? failAlert('연결 설정에 오류가 있습니다', esc(s.config_error))
      : r.loading && r.track ? '<div data-mcp-track></div>'
      : r.loading ? hydLive.waitHtml('연결 확인 중', { since: r.since, hint: `도구 서버가 도구 목록을 돌려주기를 기다립니다${S.listTimeout ? ` (최대 ${S.listTimeout}초)` : ''}.` })
      : r.status === 'ok' ? ''
      : failAlert('지금 이 서버에 연결되지 않습니다', esc(r.error || '연결 실패') + (r.checked_at ? `<p class="muted">${esc(UI.dateTime(r.checked_at) + ' 확인' + (limit ? ' · 제한 ' + limit + '초' : ''))}</p>` : ''));
    const settings = [['서버 식별자', s.name], ['등록한 설명 원문', s.description], ['연결 오류 원문', s.config_error || r.error], ['서버가 보고한 이름', r.server_info?.name],
      ['종류', T[s.transport]], ['주소', s.url], ...Object.entries(s.headers || {}).map(([k, v]) => ['접속 헤더 ' + k, v])];
    const sub = [ORIGIN[s.origin] || '기본 제공', s.description && /[가-힣]/.test(s.description) ? s.description : '', T[s.transport] ? T[s.transport] + ' 연결' : '',
      r.status === 'ok' ? `응답 ${hydTrace.fmtMs(r.elapsed_ms)} · ${UI.dateTime(r.checked_at)} 확인` : ''].filter(Boolean).join(' · ');
    const tabs = UI.viewTabs([['tools', '도구', r.status === 'ok' ? tools.length : null], ['calls', '호출 기록', null]], S.tab, 'data-mcp-tab', { small: true });
    const agents = s.agents.map(a => row(`data-goto-agent="${esc(a.id)}"`, 'bot', esc(a.name), '<span class="go">에이전트 보기</span>')).join('');
    // 이 서버로 도는 에이전트 단계(서버 계산 — agents_store.run_servers, AI 에이전트 실행 서비스와 같은 규칙)는 흐름마다 한 줄로 모은다(단계 열두 줄을 늘어놓지 않는다)
    const byFlow = new Map();
    s.tasks.forEach(t => { if (!byFlow.has(t.definition)) byFlow.set(t.definition, { name: t.definition_name || UI.defName(t.definition), steps: [] }); byFlow.get(t.definition).steps.push(UI.flowName(t.activity_name)); });
    const steps = [...byFlow].map(([id, f]) => row(`data-goto-flow="${esc(id)}"`, 'workflow', esc(f.name), `<span class="go">흐름에서 보기</span>`, esc(f.steps.join(' · ')))).join('');
    // 이 서버의 도구를 직접 부르는 흐름 단계(「승인 뒤 MCP 호출」 — 서버 mcp_dependencies.steps_using). 지우면 이 단계가 멈춘다
    const calls = (s.flow_steps || []).map(t => row(`data-goto-flow="${esc(t.definition)}"`, 'zap', `${esc(t.definition_name || UI.defName(t.definition))} <span class="ag-step">${icon('chevron-right', 'ic-sm')}${esc(UI.flowName(t.activity_name))}</span>`,
      `<span class="go">흐름에서 보기</span>`, esc([`도구 ${t.tool || '미정'}`, `판본 ${t.version}`, t.running ? `진행 중 ${t.running}건` : ''].filter(Boolean).join(' · ')))).join('');
    const used = [s.agents.length ? `에이전트 ${s.agents.length}` : '', byFlow.size ? `흐름 ${byFlow.size}` : '', calls ? `부르는 흐름 단계 ${s.flow_steps.length}` : ''].filter(Boolean).join(' · ');
    const uses = (agents ? `<h4 class="mcp-h">쓰는 에이전트</h4><div class="rows">${agents}</div>` : '') +
      (calls ? `<div data-mcp-calls><h4 class="mcp-h">이 서버를 부르는 흐름 단계</h4><div class="rows">${calls}</div></div>` : '') +
      (steps ? `<div data-mcp-flows><h4 class="mcp-h">이 서버로 도는 흐름</h4><div class="rows">${steps}</div></div>` : '');
    const gate = gateLine(s, r);
    // 방금 한 연결 검사의 과정(서버 진행 기록 — 단계마다 무엇을 받았는지와 걸린 시간): 다시 검사하거나 다시 읽을 때까지 남는다
    const rec = !r.loading && S.lastCheck && S.lastCheck.name === s.name ? S.lastCheck.rec : null;
    const checked = rec && (rec.steps || []).length ? `<div data-mcp-checked><h3>방금 한 연결 검사<span class="muted">${esc(UI.dateTime(rec.ended_at || rec.updated_at))}</span></h3>${UI.timeline(rec.steps.map(x => ({ state: x.state === 'ok' ? 'done' : x.state === 'fail' ? 'fail' : 'todo', name: x.label, sub: x.note || '',
      time: x.started_at && x.ended_at ? hydTrace.fmtMs(Date.parse(x.ended_at) - Date.parse(x.started_at)) : '' })))}</div>` : '';
    const canEdit = s.editable && !window.hydCourseAccess.blocked(REGISTER);      // 잠긴 단계에서는 고치기 · 지우기를 그리지 않는다 — 까닭은 화면 아래 설정 줄이 한 번 말한다
    box.innerHTML = `<div class="panel-head pane-head"><div class="pane-title"><h2>${esc(serverLabel(s.name))}${statusTag(s.name)}</h2><p>${esc(sub)}</p></div>` +
      `<div class="pane-acts"><button type="button" class="btn" data-variant="outline" id="mcpProbe" ${r.loading || s.config_error ? 'disabled' : ''}>${icon('activity')}연결 검사</button>` +
      (canEdit ? UI.moreMenu('mcpMore', [{ icon: 'pencil', label: '고치기', attrs: 'id="mcpEdit"' }, { act: 'remove', attrs: 'id="mcpDelete"' }]) : '') + `</div></div>` +
      (gate || status || checked ? `<div class="panel-sec mcp-state">${gate}${status}${checked}</div>` : '') +
      `<div class="panel-sec mcp-main">${tabs}<div id="mcpPane"></div></div>` +
      `<div class="panel-sec pane-fold">${UI.fold(`쓰는 곳<span class="muted">${esc(used || '쓰는 에이전트 · 흐름 없음')}</span>`, uses || '<p class="muted">이 서버를 쓰는 에이전트도, 이 서버로 도는 흐름 단계도 없습니다.</p>', { cls: 'mcp-uses' })}` +
        UI.fold('연결 설정', `${kv(settings.map(([k, v]) => [k, v ? `<code class="inline">${esc(v)}</code>` : '']))}` +
        `<p class="muted">비밀 값은 ******** 로 가려 보입니다. ${s.editable ? '고치기는 연결 검사를 통과해야 저장됩니다.' : '기본 제공 서버는 고치거나 지울 수 없습니다. 내 서버는 새 이름으로 등록해 씁니다.'}</p>`) + `</div>`;
    if (r.loading && r.track) r.track.mount(box.querySelector('[data-mcp-track]'));      // [연결 검사]가 도는 동안: 서버가 적는 단계(hydLive.track)
    box.querySelector('#mcpProbe')?.addEventListener('click', ev => checkSaved(s.name, ev.currentTarget));
    box.querySelector('#mcpEdit')?.addEventListener('click', () => openForm(s));
    box.querySelector('#mcpDelete')?.addEventListener('click', () => removeServer(s, null));
    box.querySelectorAll('[data-mcp-tab]').forEach(b => b.addEventListener('click', () => { S.tab = b.dataset.mcpTab; renderDetail(); }));
    box.querySelectorAll('[data-goto-agent]').forEach(b => b.addEventListener('click', () => { window.hydAgents.pick('agents', b.dataset.gotoAgent); window.hydShell.navigate({ tab: 'agents' }); }));
    box.querySelectorAll('[data-goto-flow]').forEach(b => b.addEventListener('click', () => { window.hydFlows.pick(b.dataset.gotoFlow); window.hydShell.navigate({ tab: 'flows' }); }));
    // 펼친 채로 다시 그려도(연결 확인이 끝날 때) 그대로 둔다 — 누른 그 자리에서 적는다(toggle 은 한 박자 늦게 온다)
    const fold = box.querySelector('.mcp-uses'); fold.open = !!S.usesOpen; fold.querySelector('summary').addEventListener('click', () => { S.usesOpen = !fold.open; });
    if (S.tab === 'calls') renderCalls(s); else renderTools(s, r);
  }

  // 도구 한 줄: 이름 · 쓸 수 있는지 한 줄 · [써 보기] 하나. 누르면 그 줄 아래에 입력 폼과 「에이전트가 읽는 설명 · 입력 형식」 접기가 열린다.
  // 써 볼 수 없는 도구(쓰기 도구)는 단추가 꺼져 있고 그 까닭이 줄에 보이며, 설명 접기는 줄 아래에 바로 있다
  function renderTools(s, r) {
    const pane = S.el.querySelector('#mcpPane');
    if (r.loading) { pane.innerHTML = UI.loading(''); return; }
    if (r.status !== 'ok') {
      pane.innerHTML = UI.errorBlock('도구 목록을 받지 못했습니다', s.config_error || r.error || '', { retry: !s.config_error });
      pane.querySelector('[data-retry]')?.addEventListener('click', () => probe(s.name));
      return;
    }
    if (!r.tools.length) { pane.innerHTML = UI.empty('이 서버는 도구를 내놓지 않습니다', '서버가 도구 목록을 비워 돌려줬습니다. 서버 쪽 설정을 확인하세요.'); return; }
    const confirmed = new Set(s.read_confirmed || []);
    pane.innerHTML = `<ul class="mcp-tools">${r.tools.map(t => {
      const fields = fieldsOf(t.input_schema);
      const usable = t.callable || (confirmed.has(t.name) && t.confirmable);
      const open = S.trying === t.name;
      // G2 ②: 표시(readOnlyHint)만 없는 도구는 읽기로 확인할 수 있다 — 확인한 도구는 에이전트 도구 · 써 보기에 들어간다
      const kind = t.callable ? '읽기 전용' : usable ? '읽기로 확인함' : '';
      const confirmBtn = !s.editable || t.callable ? '' : usable ? `<button type="button" class="btn" data-variant="outline" data-size="sm" data-unconfirm="${esc(t.name)}"${reg()}>확인 취소</button>`
        : t.confirmable ? `<button type="button" class="btn" data-variant="outline" data-size="sm" data-confirm="${esc(t.name)}"${reg()}>읽기로 확인</button>` : '';
      const more = UI.fold('에이전트가 읽는 설명 · 입력 형식', `<div class="mcp-more"><h4>에이전트가 읽는 설명 원문</h4><p>${esc(t.description || '설명 없음')}</p><h4>입력 형식</h4>` +
        (fields.length ? `<div class="table-container"><table class="table"><thead><tr><th>입력 칸</th><th>데이터 형식</th><th>설명</th></tr></thead><tbody>${fields.map(f =>
          `<tr><td><code class="inline">${esc(f.key)}</code>${f.required ? ' <span class="mcp-req" aria-label="필수">*</span>' : ''}</td><td>${esc(typeName(f))}</td><td>${esc(f.description || '')}</td></tr>`).join('')}</tbody></table></div>` : '<p class="muted">입력 없이 부릅니다.</p>') +
        `<p class="muted">도구 원래 이름 <code class="inline">${esc(t.name)}</code></p></div>`, { cls: 'mcp-info' });
      return `<li class="mcp-tool" data-tool="${esc(t.name)}"><div class="mcp-tool-head"><div><b>${esc(toolLabel(s.name, t.name))}</b>${usable ? '' : ' ' + tag('써 보기 불가', 'warn')}` +
        `<span class="mcp-desc">${esc([kind, fields.length ? `입력 ${fields.length}칸` : '입력 없음'].filter(Boolean).join(' · '))}</span>${usable ? '' : `<span class="mcp-why">${esc(t.refuse_reason || '')}</span>`}</div>` +
        `<div class="mcp-acts">${confirmBtn}<button type="button" class="btn" data-variant="outline" data-size="sm" data-try="${esc(t.name)}" aria-expanded="${open}" ${usable ? '' : 'disabled'}>${open ? '닫기' : `${icon('play')}써 보기`}</button></div></div>` +
        (S.confirming === t.name ? confirmForm(s, t) : '') + (open ? tryForm(s, t, fields, more) : usable ? '' : more) + '</li>';
    }).join('')}</ul>`;
    pane.querySelectorAll('[data-try]').forEach(b => b.addEventListener('click', () => { S.trying = S.trying === b.dataset.try ? null : b.dataset.try; renderTools(s, r); }));
    pane.querySelectorAll('[data-confirm]').forEach(b => b.addEventListener('click', () => { S.confirming = S.confirming === b.dataset.confirm ? null : b.dataset.confirm; renderTools(s, r); }));
    pane.querySelectorAll('[data-unconfirm]').forEach(b => b.addEventListener('click', () => readConfirm(s, b.dataset.unconfirm, false, b)));
    pane.querySelector('#mcpConfirmSave')?.addEventListener('click', ev => readConfirm(s, S.confirming, true, ev.currentTarget));
    if (S.trying) wireTry(s, r.tools.find(t => t.name === S.trying));
  }

  function confirmForm(s, t) {
    return `<div class="mcp-sub">${UI.section('', UI.field({ label: '읽기라고 본 이유', required: true, input: '<input id="mcpConfirmReason" placeholder="예: 서버 문서상 검색 결과만 돌려주고 아무것도 바꾸지 않는다">',
        hint: `서버가 ‘${toolLabel(s.name, t.name)}’에 읽기 전용 표시를 붙이지 않았습니다. 확인하면 에이전트 도구로 붙고 써 보기도 됩니다. 쓰기로 표시했거나 이름이 쓰기인 도구는 확인할 수 없습니다` }), 'mcp-one')}` +
      `<div data-mcp-confirm-msg></div><footer class="form-foot"><button type="button" class="btn" data-variant="outline" id="mcpConfirmSave"${reg()}>읽기로 확인</button></footer></div>`;
  }

  function readConfirm(s, tool, on, button) {
    const by = actor(); if (!by) return;
    const reason = on ? ((S.el.querySelector('#mcpConfirmReason') || {}).value || '').trim() : '';
    if (on && !reason) { S.el.querySelector('[data-mcp-confirm-msg]').innerHTML = failAlert('읽기로 확인하지 못했습니다', '읽기라고 본 이유를 적으세요.'); return; }
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

  function tryForm(s, t, fields, more = '') {
    const res = S.results[s.name + '/' + t.name];
    // 칸 도움말: 데이터 형식 · 원래 이름, 그리고 이름표로 쓰지 않은 설명 원문(이름표가 이미 설명이면 되풀이하지 않는다)
    const hint = f => [typeName(f), '원래 이름 ' + f.key, f.description && f.description !== fieldLabel(f) ? f.description : ''].filter(Boolean).join(' · ');
    const body = fields.length ? UI.section('', fields.map(f => UI.field({ label: fieldLabel(f), required: f.required, input: inputFor(f), hint: hint(f) })).join('')) : '<p class="muted">입력 없이 부릅니다.</p>';
    return `<div class="mcp-sub mcp-try">${body}<p class="muted">실제 서버를 부릅니다. 읽기 전용 도구만 허용되며 처리 건 · 설비 · 업무 DB를 바꾸지 않습니다. 결과가 아주 길면 앞부분만 보이고 잘린 크기를 함께 알려 줍니다.</p>` +
      `<footer class="form-foot"><button type="button" class="btn" id="mcpCall">${icon('play')}실행해 보기</button></footer>` +
      `<div id="mcpResult" class="pane-msg" aria-live="polite">${res ? resultHtml(res) : ''}</div>${more}</div>`;
  }

  function resultHtml(res) {
    if (res.loading) return hydLive.waitHtml(`${res.label || '도구'} 실행하는 중`, { since: res.since, hint: `${res.server || '도구 서버'}의 응답을 기다립니다. 서버가 결과를 한 번에 줍니다.` });
    if (res.error) return failAlert('도구를 실행하지 못했습니다', esc(res.error));
    const r = res.result;
    // 결론(받았는지 · 오류인지) → 결과 → 원문 차례. 걸린 시간 · 길이 · 보낸 입력은 둘째 줄
    return `<div class="result"><div class="result-label">결과</div><div class="result-main">${r.is_error ? '도구가 오류를 돌려줬습니다' : '결과를 받았습니다'}${r.truncated ? ` — ${r.limit_chars.toLocaleString()}자에서 잘렸습니다` : ''}</div>` +
      `<div class="result-sub">${esc(hydTrace.fmtMs(res.elapsed_ms))} · ${r.size_chars.toLocaleString()}자</div></div>` +
      readable(r.text, res.arguments);
  }
  // 도구 결과는 {"result": "<JSON 글>"}처럼 한 번 더 감싸여 온다 — 풀어서 행이면 표로, 아니면 들여 쓴 JSON 으로. 원문은 접어 둔다
  function readable(text, sent) {
    // 결과는 표로 풀 수 있으면 표로 보이고 원문은 접어 둔다. 표로 풀 수 없으면 받은 결과의 원문 판을 펼쳐 보인다(원문 판은 하나뿐이다)
    const raw = open => UI.raw(sent ?? {}, { title: '보낸 입력 원문' }) + UI.raw(text, { title: '받은 결과 원문', open });
    let v; try { v = JSON.parse(text); if (v && typeof v.result === 'string') v = JSON.parse(v.result); } catch (_) { return raw(true); }
    const rows = Array.isArray(v) ? v : Array.isArray(v?.rows) ? v.rows : null;
    const flat = rows && rows.length && rows.every(r => r && typeof r === 'object' && !Array.isArray(r));
    const cols = flat ? [...new Set(rows.flatMap(r => Object.keys(r)))] : [];
    const cell = x => esc(x == null ? '' : typeof x === 'object' ? JSON.stringify(x) : String(x));
    const colName = c => { const known = hydWords.fieldName(c); return /[가-힣]/.test(known) ? known : c; };      // 사전에 있는 열만 한국어 이름으로, 모르는 열은 원문 그대로
    const body = flat ? `<div class="table-container mcp-rows"><table class="table"><thead><tr>${cols.map(c => `<th>${esc(colName(c))}</th>`).join('')}</tr></thead>`
        + `<tbody>${rows.slice(0, 100).map(r => `<tr>${cols.map(c => `<td>${cell(r[c])}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`
        + (rows.length > 100 ? `<p class="muted">${rows.length}행 중 100행만 표로 보입니다. 나머지는 원문에 있습니다.</p>` : '')
      : '';
    return body + raw(!flat);
  }

  function wireTry(s, t) {
    if (!t) return;
    const fields = fieldsOf(t.input_schema);
    const key = s.name + '/' + t.name;
    S.el.querySelector('#mcpCall').addEventListener('click', async () => {
      const raws = {}; S.el.querySelectorAll('.mcp-try [data-key]').forEach(i => { raws[i.dataset.key] = i.value; });
      const { args, errors } = argsFrom(fields.map(f=>({...f,description:fieldLabel(f)})),raws);
      const out = S.el.querySelector('#mcpResult');
      if (errors.length) { out.innerHTML = failAlert('입력을 확인하세요', errors.map(esc).join('<br>')); return; }
      const by = actor(); if (!by) return;
      const btn = S.el.querySelector('#mcpCall'); btn.disabled = true;
      S.results[key] = { loading: true, since: new Date().toISOString(), label: `「${toolLabel(s.name, t.name)}」`, server: serverLabel(s.name) }; out.innerHTML = resultHtml(S.results[key]);
      try { S.results[key] = await postJ(api(`/api/mcp/servers/${encodeURIComponent(s.name)}/tools/${encodeURIComponent(t.name)}/call`), { arguments: args, by }); }
      catch (e) { S.results[key] = { error: e.message }; }
      if (out.isConnected) { out.innerHTML = resultHtml(S.results[key]); btn.disabled = false; }
    });
  }

  async function renderCalls(s) {
    const pane = S.el.querySelector('#mcpPane');
    const tools = ((S.tools[s.name] || {}).tools || []).map(t => t.name);
    const filter = `<div class="mcp-filter">${UI.field({ label: '도구', input: `<select id="mcpCallTool"><option value="">전체</option>${tools.map(t => `<option value="${esc(t)}" ${t === S.callTool ? 'selected' : ''}>${esc(toolLabel(s.name, t))}</option>`).join('')}</select>` })}</div>`;
    pane.innerHTML = filter + `<div id="mcpCallList">${UI.loading('')}</div>`;
    pane.querySelector('#mcpCallTool').addEventListener('change', ev => { S.callTool = ev.target.value; S.openCall = null; renderCalls(s); });
    const list = pane.querySelector('#mcpCallList');
    let r;
    try { r = await getJ(api(`/api/mcp/calls?server=${encodeURIComponent(s.name)}${S.callTool ? '&tool=' + encodeURIComponent(S.callTool) : ''}&limit=50`)); }
    catch (err) { list.innerHTML = UI.errorBlock('호출 기록을 불러오지 못했습니다', err.message, { retry: true }); list.querySelector('[data-retry]').addEventListener('click', () => renderCalls(s)); return; }
    if (S.sel !== s.name || S.tab !== 'calls') return;
    if (!r.calls.length) { list.innerHTML = UI.emptyGo('아직 이 도구를 부른 처리 건이 없습니다', `최근 도구 이벤트 ${r.scanned}개에서 찾았습니다. 경보로 처리 건이 돌거나 에이전트에게 질문하면 여기에 쌓입니다.`, 'ask', '질문하기'); return; }
    drawCalls(s, r);
  }
  // 호출 한 줄(실시간 줄과 같은 모양): 도구 · 어느 처리 건의 어느 단계 · 시각. 상태 뱃지는 끝나지 않았거나 오류일 때만. 입력 · 결과는 그 줄을 열었을 때
  function drawCalls(s, r) {
    const list = S.el.querySelector('#mcpCallList');
    if (!list) return;
    const STATE = { error: ['오류', 'danger'], running: ['진행 중', 'run'] };
    list.innerHTML = `<ul class="mcp-calls">${r.calls.map((c, i) => {
      const state = STATE[c.state], open = S.openCall === i;
      return `<li><div class="line" data-kind="${c.state === 'error' ? 'fail' : 'tool'}">${icon('plug')}<span class="line-text"><b>${esc(toolLabel(c.server, c.tool))}</b>${state ? ' ' + tag(state[0], state[1]) : ''}` +
        `<span class="line-sub">${esc([c.instance_name || UI.idText(c.proc_inst_id), c.task_name].filter(Boolean).join(' · '))}</span></span>` +
        `<time class="line-time num">${esc(UI.dateTime(c.at))}${c.duration_ms != null ? ' · ' + esc(hydTrace.fmtMs(c.duration_ms)) : ''}</time></div>` +
        `<div class="mcp-call-body">${kv([['입력', c.input_summary ? `<code class="inline">${esc(c.input_summary)}</code>` : ''], ['결과', c.output_summary ? `<code class="inline">${esc(c.output_summary)}</code>` : c.state === 'running' ? '아직 끝나지 않음' : '']])}` +
        `<div class="mcp-call-acts"><button type="button" class="btn" data-variant="link" data-call-open="${i}" aria-expanded="${open}">${open ? '전체 닫기' : '입력 · 결과 전체 보기'}</button>` +
        `${c.link ? `<a class="btn" data-variant="link" href="${esc(c.link)}">처리 건에서 보기${icon('arrow-right')}</a>` : ''}</div>` +
        (open ? UI.raw(c.input, { title: '입력 원문', open: true }) + UI.raw(c.output, { title: '결과 원문', open: true }) : '') + '</div></li>';
    }).join('')}</ul>` + (r.scanned >= r.scan_limit ? `<p class="muted">최근 도구 이벤트 ${r.scan_limit}개까지만 훑었습니다. 그보다 오래된 호출은 처리 건 화면에서 보세요.</p>` : '');
    list.querySelectorAll('[data-call-open]').forEach(b => b.addEventListener('click', () => { const i = Number(b.dataset.callOpen); S.openCall = S.openCall === i ? null : i; drawCalls(s, r); }));
  }

  // ---------------------------------------------------------------- 등록 · 고치기 · 지우기 · 연결 검사 · 되돌리기
  // 고를 수 있음 = 마지막 연결 검사 통과 기록(서버 게이트), 지금 상태 = 화면을 열 때 다시 잰 것 — 둘이 갈리면 지금 붙여도 된다고 읽히지 않게
  // 그 사실을 말한다(목록 · 상세가 이 한 문장을 쓴다, 2026-11-01 메뉴 눈 확인 · 11-02 독립 검증)
  function stampGap(s, r) {
    return s.selectable && r && r.status === 'failed'
      ? `지난 연결 검사는 통과했지만 지금은 연결되지 않습니다(${KIND[r.error_kind] || '연결 검사 실패'}) — 서버를 켠 뒤 다시 읽으세요` : '';
  }

  // 에이전트 도구로 고를 수 있는지 한 문장(상태는 앞의 점 색으로 — 초록 = 고를 수 있음, 주황 = 지금은 안 됨)
  function gateLine(s, r) {
    const line = (tone, text) => `<p class="mcp-gate"><i class="dot" data-tone="${tone}"></i><span>${text}</span></p>`;
    const gap = stampGap(s, r);
    if (gap) return line('warn', esc(gap));
    const c = s.check || {};
    const when = c.checked_at ? ` · ${esc(UI.dateTime(c.checked_at))}` : '';
    if (s.selectable && s.origin === 'seed') return '';      // 기본 제공 서버가 연결돼 있다는 것은 머리의 뱃지가 이미 말한다 — 같은 상태를 한 판에 두 번 적지 않는다
    if (s.selectable) return line('ok', `에이전트 도구로 고를 수 있음 — 연결 검사 통과${when}, 읽기 전용 도구만 에이전트에 붙습니다`);
    return line('warn', `에이전트 도구로 고를 수 없음 — ${esc(s.reason || CHECK[c.status] || '연결 검사 전')}${when}`);
  }

  function checkSaved(name, button) {
    const by = actor(); if (!by) return;
    return once('check:' + name, button, async () => {
      const track = hydLive.track({ text: '연결 검사 중', hint: `도구 서버에 연결해 인사를 주고받고 도구 목록을 받습니다${S.listTimeout ? ` (최대 ${S.listTimeout}초)` : ''}.` });
      S.tools[name] = { loading: true, track }; renderServers(); if (S.sel === name) renderDetail();
      try {
        const r = await postJ(api(`/api/mcp/servers/${encodeURIComponent(name)}/check`), { by, request_id: track.id });
        UI.toast(r.check.status === 'ok' ? `${serverLabel(name)}: 연결 검사를 통과했습니다. 도구 ${r.check.tools.length}개` : `${serverLabel(name)}: 연결 검사에 실패했습니다. ${r.check.error || ''}`, { tone: r.check.status === 'ok' ? 'ok' : 'neg' });
      } catch (e) { UI.toast(`${serverLabel(name)}: ${e.message}`, { tone: 'neg' }); }
      finally { track.stop(); }
      // 검사가 1초 안에 끝나면 도는 동안의 단계 목록을 볼 틈이 없다 — 서버가 적은 진행 기록(무엇을 불렀고 무엇을 받았는지)을 한 번 읽어 그 서버의 상세에 남긴다
      try { S.lastCheck = { name, rec: await getJ(api('/api/progress/' + encodeURIComponent(track.id))) }; }
      catch (e) { S.lastCheck = null; console.error('연결 검사의 진행 기록을 읽지 못했습니다:', e.message); }
      await load();
    });
  }

  function openForm(s) {
    const editing = !!s;
    const v = editing ? { name: s.name, transport: s.transport || 'streamable_http', url: s.url || '',
      headers: Object.entries(s.headers || {}).map(([k, x]) => `${k}=${x}`).join('\n'), description: s.description || '' }
      : { name: '', transport: 'streamable_http', url: '', headers: '', description: '' };
    S.form = { editing, v, result: null, busy: false, error: '' };
    renderForm(); renderDetail(); renderServers(); UI.revealDetail(S.el.querySelector('#mcpPanel'));
  }

  function readForm() {
    const box = S.el.querySelector('#mcpForm');
    box.querySelectorAll('[data-f]').forEach(i => { S.form.v[i.dataset.f] = i.value; });
    return S.form.v;
  }

  function renderForm() {
    const box = S.el.querySelector('#mcpForm');
    const F = S.form;
    const add = S.el.querySelector('#mcpAdd'); if (add) add.hidden = !!F || !!window.hydCourseAccess.blocked(REGISTER);      // 주 단추는 화면에 하나 — 폼을 쓰는 동안에는 폼의 [검사 후 등록]이 주 단추다
    if (!F) { box.innerHTML = ''; return; }
    const v = F.v;
    const opt = (val, label) => `<option value="${val}" ${v.transport === val ? 'selected' : ''}>${label}</option>`;
    const fields = [
      UI.field({ label: '이름', required: true, input: `<input data-f="name" value="${esc(v.name)}" ${F.editing ? 'disabled' : ''} placeholder="my-folder">`, hint: '소문자 · 숫자 · 하이픈. 에이전트 도구 칸에 이 이름을 적습니다' }),
      UI.field({ label: '연결 방식', required: true, input: `<select data-f="transport">${opt('streamable_http', T.streamable_http)}${opt('sse', T.sse)}</select>`,
        hint: '도구 서버를 HTTP 로 띄운 주소를 등록합니다. 명령으로 띄우는 서버도 HTTP 로 띄워 그 주소를 적습니다' }),
      UI.field({ label: '주소', required: true, cls: 'mcp-wide', input: `<input data-f="url" value="${esc(v.url)}" placeholder="http://host.docker.internal:8301/mcp">`,
        hint: '내 PC 에서 띄운 서버면 localhost 대신 host.docker.internal 을 씁니다' }),
      UI.field({ label: '접속 헤더', cls: 'mcp-wide', input: `<textarea data-f="headers" rows="2" placeholder="Authorization=Bearer \${SECRET:MY_TOKEN}">${esc(v.headers)}</textarea>`,
        hint: '토큰은 값 대신 \${SECRET:이름} 으로 적고, 값은 화면 아래 「비밀 값」 줄에서 넣으세요. 값을 그대로 적으면 저장하되 화면에서는 ******** 로 가립니다' }),
      UI.field({ label: '설명', cls: 'mcp-wide', input: `<input data-f="description" maxlength="200" value="${esc(v.description)}" placeholder="이 서버가 하는 일 한 줄">` }),
    ].join('');
    // 폼은 상세 자리에(디자인기준 5-1): 제목 → 칸 → 못 한 까닭 → 취소 · 연결 검사만 · 검사 후 등록(주 단추) → 검사 과정과 결과
    box.innerHTML = `<div class="panel-head"><div><h2>${F.editing ? `서버 고치기 — ${esc(v.name)}` : '서버 등록'}</h2>` +
      `<p>연결 검사를 통과해야 저장됩니다. 저장한 서버의 읽기 전용 도구만 에이전트 도구로 고를 수 있습니다.</p></div></div>` +
      `<div class="panel-sec mcp-form">${UI.section('연결', fields)}${F.error ? failAlert(F.editing ? '서버를 고치지 못했습니다' : '서버를 등록하지 못했습니다', esc(F.error)) : ''}` +
      UI.formFoot(`<button type="button" class="btn" data-variant="outline" id="mcpDry" ${F.busy ? 'disabled' : ''}${reg()}>연결 검사만</button>` +
        `<button type="button" class="btn" id="mcpSave" ${F.busy ? 'disabled' : ''}${reg()}>${F.editing ? '검사 후 저장' : '검사 후 등록'}</button>`, { cancelAttrs: 'id="mcpFormClose"' }) +
      `<div id="mcpFormResult" class="pane-msg" aria-live="polite">${F.busy ? '<div data-mcp-track></div>' : checkHtml(F.result)}</div></div>`;
    if (F.busy && F.track) F.track.mount(box.querySelector('[data-mcp-track]'));      // 다시 그려도 같은 진행 목록이 새 자리로 옮겨 간다
    box.querySelector('#mcpFormClose').addEventListener('click', () => { S.form = null; renderForm(); renderServers(); renderDetail(); });
    box.querySelector('#mcpDry').addEventListener('click', () => submitForm(true));
    box.querySelector('#mcpSave').addEventListener('click', () => submitForm(false));
  }

  // 연결 검사 결과의 도구 이름: 목록과 같은 이름 사전을 먼저 쓴다. 사전에 없는 도구(아직 등록 전인 내 서버)는 서버가 준 한국어 제목, 그것도 없으면 원래 이름
  function checkToolName(t) {
    const raw = `mcp__${(S.form && S.form.v.name || '').trim()}__${t.name}`;
    return hydWords.knownTool(raw) ? hydWords.toolName(raw) : t.title && /[가-힣]/.test(t.title) ? t.title : t.name;
  }
  function checkHtml(c) {
    if (!c) return '';
    if (c.status !== 'ok') return failAlert('연결 검사에 실패했습니다', esc(c.error || '서버가 까닭을 주지 않았습니다'));
    return `<div class="alert" role="status">${icon('circle-check')}<h2>연결 검사를 통과했습니다 — 도구 ${c.tools.length}개 · ${esc(hydTrace.fmtMs(c.elapsed_ms))}</h2></div>` +
      `<ul class="mcp-tools">${c.tools.map(t => `<li class="mcp-tool"><b>${esc(checkToolName(t))}</b>${t.read_only ? '' : ' ' + tag('붙일 수 없음', 'warn')}` +
        `<span class="mcp-desc">${esc(t.read_only ? '에이전트에 붙일 수 있음' : (t.reason || '') + (t.confirmable ? ' — 등록 뒤 [읽기로 확인]할 수 있습니다' : ''))}</span>` +
        `<span class="mcp-desc">${esc(t.description || '설명 없음')}</span></li>`).join('')}</ul>`;
  }

  async function submitForm(dry) {
    const F = S.form;
    if (F.busy) return;
    let body;
    try { body = bodyFrom(readForm()); } catch (e) { F.error = e.message; renderForm(); return; }
    body.by = actor(); if (!body.by) return;
    // 서버가 「연결 → 인사(initialize) → 도구 목록 → 저장」을 그 일이 시작 · 끝날 때 진행 기록에 적는다(hydLive.track 이 읽어 채운다)
    F.track = hydLive.track({ text: '연결 검사 중', hint: `적은 주소의 서버에 연결해 인사를 주고받고 도구 목록을 받습니다${S.listTimeout ? ` (최대 ${S.listTimeout}초)` : ''}. 통과해야 저장합니다.` });
    body.request_id = F.track.id;
    F.busy = true; F.error = ''; F.result = null; renderForm();
    try {
      const r = dry ? await postJ(api('/api/mcp/check'), body)
        : F.editing ? await postJ(api(`/api/mcp/servers/${encodeURIComponent(body.name)}`), body, 'PUT')
        : await postJ(api('/api/mcp/servers'), body);
      F.track.stop(); F.result = r.check; F.busy = false;
      if (!dry) {
        UI.toast(`${body.name}: ${F.editing ? '고쳤습니다' : '등록했습니다'} · 에이전트에 붙일 수 있는 도구 ${r.gate.read_tools.length}개`, { tone: 'ok' });
        (r.warnings || []).forEach(w => UI.toast(`${body.name}: ${w}`, { tone: 'neg' }));
        S.form = null; renderForm(); S.sel = body.name; S.trying = null; await load(); return;
      }
    } catch (e) {
      F.track.stop(); F.busy = false; F.error = e.message;
    }
    renderForm();
  }

  // 지우기 확인: 이 서버를 쓰는 에이전트와 이 서버를 부르는 흐름 단계(서버 flow_steps)를 함께 보이고, 지운 뒤에 무엇이 달라지는지 말한다.
  // 쓰는 것이 있으면 서버는 force 없이 지우지 않는다(409) — 확인 창에서 그것을 읽고 지우기로 했으므로 force 로 보낸다
  const stepText = t => `「${t.definition_name || UI.defName(t.definition)}」의 「${UI.flowName(t.activity_name)}」(도구 ${t.tool || '미정'}${t.running ? ` · 진행 중인 처리 건 ${t.running}건` : ''})`;
  async function removeServer(s, button) {
    const by = actor(); if (!by) return;      // 확인을 묻기 전에 막는다
    const using = s.agents.map(a => a.name), calls = (s.flow_steps || []).map(stepText);
    const body = [using.length ? `이 서버를 쓰는 에이전트: ${using.join(', ')}.` : '이 서버를 쓰는 에이전트는 없습니다.',
      calls.length ? `이 서버를 부르는 흐름 단계: ${calls.join(', ')}.` : '이 서버를 부르는 흐름 단계는 없습니다.',
      using.length ? '지우면 그 에이전트는 이 서버 없이 실행됩니다.' : '', calls.length ? '그 흐름 단계는 실행될 때 서버가 없다는 까닭으로 멈춥니다.' : '',
      '연결 검사 기록도 함께 지웁니다. 지운 서버는 다시 등록해야 합니다.'].filter(Boolean).join(' ');
    const ok = await UI.confirm({ title: `${serverLabel(s.name)} 서버를 지울까요?`, body, ok: '지우기', danger: true });
    if (!ok) return;
    return once('delete:' + s.name, button, async () => {
      try {
        const r = await requestJ(api(`/api/mcp/servers/${encodeURIComponent(s.name)}?force=${using.length || calls.length ? 'true' : 'false'}&by=${encodeURIComponent(by)}`), { method: 'DELETE' });
        const left = r.flow_steps_still_calling_it || [], naming = r.agents_still_naming_it || [];
        UI.toast(`${serverLabel(s.name)}: 지웠습니다`, { tone: 'ok' }); S.sel = null;
        S.removed = left.length || naming.length ? { name: serverLabel(s.name), steps: left, agents: naming } : null;
      } catch (e) { UI.toast(`${serverLabel(s.name)}: ${e.message}`, { tone: 'neg', timeout: 8000 }); }
      await load();
    });
  }
  // 방금 지운 서버를 아직 가리키는 것(지우기 응답의 flow_steps_still_calling_it · agents_still_naming_it) — 다른 서버를 고를 때까지 상세 자리에 남는다
  function removedNote() {
    const d = S.removed; if (!d) return '';
    const rows = [...d.steps.map(t => `<li>${icon('zap')}<span><b>${esc(t.definition_name)}</b> ${esc(UI.flowName(t.activity_name))} <span class="muted">도구 ${esc(t.tool || '미정')} · 판본 ${esc(t.version)}${t.running ? ` · 진행 중 ${t.running}건` : ''}</span></span></li>`),
      ...d.agents.map(n => `<li>${icon('bot')}<span><b>${esc(n)}</b> <span class="muted">이 서버 없이 실행됩니다</span></span></li>`)].join('');
    return `<div class="alert" data-mcp-removed>${icon('triangle-alert')}<h2>지운 ${esc(d.name)} 서버를 아직 가리키는 곳이 있습니다</h2><section>` +
      (d.steps.length ? `<p>아래 흐름 단계는 실행될 때 서버가 없다는 까닭으로 멈춥니다. 흐름에서 그 단계의 도구 서버를 바꾸거나 같은 이름으로 서버를 다시 등록하세요.</p>` : '') + `<ul class="evid">${rows}</ul></section></div>`;
  }

  /* ---------------------------------------------------------------- 화면 아래의 설정 줄(디자인기준 4-16 — 본: process-gpt-lite 설정 시트의 줄: 굵은 이름 · 한 줄 설명 · 오른쪽 동작 하나)
     ① 잠긴 까닭: 서버가 tool_servers.register 를 막으면 「내 도구 서버」 줄이 그 까닭(서버 문장)을 말한다 — 머리의 [서버 등록]은 그리지 않는다(꺼진 주 단추를 가장 진한 자리에 두지 않는다).
     ② 비밀 값(${SECRET:이름}): 줄 하나에 이름 · 쓰는 서버 · [지우기]. 값은 넣기만 하고 다시 보이지 않는다. 넣는 폼은 「비밀 값 넣기」 줄의 [넣기]가 연다.
        잠긴 단계이고 넣어 둔 값도 없으면 비밀 값 줄을 그리지 않는다(쓸 서버를 등록할 수 없다).
     되돌리기는 관리 › 내 설정 한 곳에 있고 같은 키로 잠긴다(configBundle.js SCOPES) */
  async function loadSecrets() {
    try { S.secrets = await getJ(api('/api/mcp/secrets')); S.secretsError = ''; }
    catch (e) { S.secretsError = e.message; }
    renderOperator();
  }
  function renderOperator() {
    const box = S.el.querySelector('#mcpOperator'); if (!box) return;
    const why = window.hydCourseAccess.blocked(REGISTER);
    const add = S.el.querySelector('#mcpAdd');
    add.outerHTML = `<button type="button" class="btn" id="mcpAdd"${reg()}${S.form || why ? ' hidden' : ''}>${icon('plus')}서버 등록</button>`;
    S.el.querySelector('#mcpAdd').addEventListener('click', () => openForm(null));
    const list = (S.secrets && S.secrets.secrets) || [];
    const rows = [];
    if (why) rows.push(UI.settingRow({ title: '내 도구 서버', desc: why, attrs: 'data-mcp-why' }));
    if (S.secretsError) rows.push(`<div class="setting" data-mcp-secrets-error>${UI.errorBlock('비밀 값 목록을 불러오지 못했습니다', S.secretsError, { retry: true })}</div>`);
    else if (!why || list.length) {
      list.forEach(x => rows.push(UI.settingRow({ title: x.key, attrs: `data-secret="${esc(x.key)}"`,
        desc: [x.stored ? '저장됨' : '값 없음 — 이 이름을 쓰는 서버는 값을 넣을 때까지 연결되지 않습니다', x.used_by.length ? '쓰는 서버: ' + x.used_by.map(n => serverLabel(n)).join(', ') : '쓰는 서버 없음',
          x.updated_at ? UI.dateTime(x.updated_at) + (x.updated_by ? ' ' + UI.who(x.updated_by) : '') : ''].filter(Boolean).join(' · '),
        action: (x.stored ? '' : tag('값 없음', 'danger')) + (x.stored ? `<button type="button" class="btn" data-variant="ghost" data-size="sm" data-secret-del="${esc(x.key)}"${reg()}>${icon('trash-2')}지우기</button>` : '') })));
      rows.push(UI.settingRow({ title: '비밀 값 넣기', desc: (S.secrets && S.secrets.rule) || '접속 헤더에 ${SECRET:이름}으로 적은 토큰의 값을 넣습니다. 저장하면 다시 보이지 않습니다.',
        action: `<button type="button" class="btn" data-variant="outline" data-size="sm" id="mcpSecretOpen" aria-expanded="${!!S.secretOpen}"${reg()}>${icon('plus')}넣기</button>` }));
    }
    const form = S.secretOpen && !why ? `<div class="mcp-secret-new">${UI.section('', UI.field({ label: '이름', required: true, input: '<input id="mcpSecretKey" placeholder="MY_TOKEN">', hint: '대문자 · 숫자 · 밑줄' }) +
      UI.field({ label: '값', required: true, input: '<input id="mcpSecretValue" type="password" autocomplete="off">', hint: '토큰이 만료되면 같은 이름으로 다시 넣으세요' }))}` +
      `<div data-mcp-secret-msg class="pane-msg"></div>${UI.formFoot(`<button type="button" class="btn" id="mcpSecretSave"${reg()}>비밀 값 저장</button>`, { cancelAttrs: 'id="mcpSecretCancel"' })}</div>` : '';
    box.hidden = !rows.length;
    box.innerHTML = rows.length ? `<div class="settings">${rows.join('')}</div>${form}` : '';
    const say = html => { box.querySelector('[data-mcp-secret-msg]').innerHTML = html; };
    box.querySelector('[data-retry]')?.addEventListener('click', loadSecrets);
    box.querySelector('#mcpSecretOpen')?.addEventListener('click', () => { S.secretOpen = !S.secretOpen; renderOperator(); S.el.querySelector('#mcpSecretKey')?.focus(); });
    box.querySelector('#mcpSecretCancel')?.addEventListener('click', () => { S.secretOpen = false; renderOperator(); });
    box.querySelector('#mcpSecretSave')?.addEventListener('click', e => once('secret:save', e.currentTarget, async () => {
      const key = box.querySelector('#mcpSecretKey').value.trim(), value = box.querySelector('#mcpSecretValue').value;
      if (!key) { say(failAlert('비밀 값을 저장하지 못했습니다', '이름을 적으세요 (대문자 · 숫자 · 밑줄).')); return; }
      if (!value) { say(failAlert('비밀 값을 저장하지 못했습니다', '값을 넣으세요.')); return; }
      const by = actor(); if (!by) return;
      try { await postJ(api(`/api/mcp/secrets/${encodeURIComponent(key)}`), { value, by }, 'PUT'); UI.toast(`${key}: 저장했습니다`, { tone: 'ok' }); S.secretOpen = false; }
      catch (err) { say(failAlert('비밀 값을 저장하지 못했습니다', esc(err.message))); return; }
      await loadSecrets();
    }));
    box.querySelectorAll('[data-secret-del]').forEach(b => b.addEventListener('click', async () => {
      const key = b.dataset.secretDel, users = (list.find(x => x.key === key) || {}).used_by || [];
      const by = actor(); if (!by) return;
      if (!await UI.confirm({ title: `비밀 값 ${key}${window.hydWords.josa(key, '을/를')} 지울까요?`, ok: '지우기', danger: true,
        body: users.length ? `이 값을 쓰는 서버(${users.map(n => serverLabel(n)).join(', ')})는 다시 넣을 때까지 연결 · 호출이 실패합니다. 지운 값은 되살릴 수 없습니다.` : '지운 값은 되살릴 수 없습니다.' })) return;
      await once('secret:del:' + key, b, async () => {
        try { await requestJ(api(`/api/mcp/secrets/${encodeURIComponent(key)}?by=${encodeURIComponent(by)}`), { method: 'DELETE' }); UI.toast(`${key}: 지웠습니다`, { tone: 'ok' }); }
        catch (err) { UI.toast(`${key}: ${err.message}`, { tone: 'neg', timeout: 8000 }); return; }
        await loadSecrets();
      });
    }));
    window.hydCourseAccess.apply(box);
  }

  function mount(el) {
    if (!el) return;
    S.el = el;
    // 차례: 제목 · 한 문장 · 주 단추 하나 → 왼쪽 서버 목록 · 오른쪽 상세(등록 폼도 이 자리) → 화면 아래 설정 줄(잠긴 까닭 · 비밀 값)과 「관리에서 되돌리기」 한 줄
    el.innerHTML = UI.pageHead('mcp', { sub: '에이전트가 부르는 도구 서버(MCP)와 그 도구를 보고, 직접 불러 결과를 확인합니다.', tools: '<button type="button" class="btn" id="mcpAdd" hidden>서버 등록</button>', more: [{ act: 'reload', attrs: 'id="mcpReload"' }] }) +
      `<div class="split"><div class="pane-side"><div class="rows" id="mcpServers" aria-label="도구 서버 목록"></div></div><section class="panel" id="mcpPanel" aria-label="고른 도구 서버"><div id="mcpForm"></div><div id="mcpDetail"></div></section></div>` +
      `<section class="pane-foot mcp-set" id="mcpOperator" aria-label="비밀 값과 등록" hidden></section>` +
      UI.resetLink('mcp', '내가 등록한 도구 서버와 비밀 값을');
    el.querySelector('#mcpReload').addEventListener('click', () => { S.lastCheck = null; load(); loadSecrets(); });
    renderOperator();
    loadSecrets();
    load();
  }
  // 수업 범위가 늦게 오거나 바뀌면 이 화면의 행동 단추를 다시 맞춘다
  window.hydCourseAccess.onChange(() => { if (!S.el) return; renderOperator(); renderDetail(); renderForm(); });

  // pick(서버 이름): 다른 화면(에이전트의 도구 서버)이 이 화면을 그 서버를 고른 채 열 때 부른다. show: 다시 열 때 그 서버를 고른다
  function show() { if (S.el && S.want) { const name = S.want; S.want = null; if (S.servers.some(s => s.name === name)) select(name); } }
  // 관리 › 내 설정에서 되돌렸으면(이 화면이 그려져 있을 때) 고른 것 · 폼을 비우고 다시 읽는다
  window.addEventListener('hyd-config-reset', e => { if (!S.el || !['all', 'mcp'].includes(e.detail.scope)) return; S.sel = null; S.form = null; S.secretOpen = false; renderForm(); load(); loadSecrets(); });
  window.hydMcp = { mount, show, pick: name => { S.want = name; S.sel = name; } };
})();
