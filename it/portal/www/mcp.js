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
  const S = { el: null, servers: [], tools: {}, sel: null, tab: 'tools', trying: null, info: null, openCall: null, results: {}, callTool: '', form: null,
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
    // 누른 단추가 「…중 · 걸린 시간」으로 바뀐다(다시 그려져 단추가 사라졌으면 손대지 않는다)
    S.acting.add(key); const end = button ? hydLive.busy(button, button.textContent.trim() + ' 중') : null;
    try { await work(); } finally { S.acting.delete(key); if (end && button.isConnected) end(false); }
  }

  const ORIGIN = { seed: '기준 서버', user: '내가 등록한 서버', external: '포털 밖에서 추가한 서버' };
  // 키-값 · 이름표 붙은 묶음(기준 4절). 값이 없는 줄은 그리지 않는다
  const kv = rows => { const r = rows.filter(([, v]) => v != null && v !== ''); return r.length ? `<dl class="kv">${r.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${v}</dd>`).join('')}</dl>` : ''; };
  const group = (label, body) => body ? `<section class="rd-group"><h3 class="rd-label">${esc(label)}</h3>${body}</section>` : '';
  const CHECK = { ok: '연결 검사 통과', failed: '연결 검사 실패', stale: '설정이 바뀌어 다시 검사 필요', never: '연결 검사 전' };

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
    box.innerHTML = UI.loading('', 'compact');
    try { const r = await getJ(api('/api/mcp/servers')); S.servers = r.servers || []; S.listTimeout = r.list_timeout_s; }
    catch (e) { box.innerHTML = UI.errorBlock('도구 서버 목록을 불러오지 못했습니다', e.message, { retry: true, cls: 'compact' }); box.querySelector('[data-retry]').addEventListener('click', load); return; }
    S.tools = {};
    if (S.sel && !S.servers.some(s => s.name === S.sel)) S.sel = null;
    if (!S.sel && S.servers.length) S.sel = S.servers[0].name;      // 상세 자리를 비워 두지 않는다 — 첫 서버를 고른 채 연다
    renderServers(); renderDetail();
    S.servers.filter(s => !s.config_error).forEach(s => probe(s.name));
  }

  async function probe(name) {
    S.tools[name] = { loading: true }; renderServers(); if (S.sel === name) renderDetail();
    try { S.tools[name] = await getJ(api(`/api/mcp/servers/${encodeURIComponent(name)}/tools`)); }      // 시간 한도는 서버 기본값(list_timeout_s)
    catch (e) { S.tools[name] = { status: 'failed', error: e.message, error_kind: null, tools: [] }; }
    renderServers(); if (S.sel === name) renderDetail();
  }

  // 목록 한 줄: 이름 + 연결 상태 칩 하나, 둘째 줄에 에이전트 도구로 고를 수 있는지(지금 연결이 끊겼으면 그 사실)
  function renderServers() {
    const box = S.el.querySelector('#mcpServers');
    if (!S.servers.length) { box.innerHTML = UI.empty('등록된 도구 서버가 없습니다', '기준 도구 서버가 없으면 시작.bat을 다시 실행하세요. 내 서버는 화면 위의 [서버 등록]으로 붙입니다.', 'compact'); return; }
    box.innerHTML = `<div class="list">${S.servers.map(s => {
      const r = S.tools[s.name] || {};
      const count = r.status === 'ok' ? `도구 ${r.tools.length}개 · ` : '';
      const sub = s.config_error ? '연결 설정 오류' : stampGap(s, r) || count + (s.selectable ? '에이전트 도구로 고를 수 있음' : s.reason || '에이전트 도구로 고를 수 없음');
      return `<div class="item${s.name === S.sel ? ' sel' : ''}" role="button" tabindex="0" data-name="${esc(s.name)}" aria-pressed="${s.name === S.sel}">` +
        `<div class="row"><strong>${esc(serverLabel(s.name))}</strong>${statusChip(s.name)}</div><span class="sub">${esc(sub)}</span></div>`;
    }).join('')}</div>`;
    box.querySelectorAll('[data-name]').forEach(item => {
      item.addEventListener('click', () => select(item.dataset.name));
      item.addEventListener('keydown', ev => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); select(item.dataset.name); } });
    });
  }

  function select(name) {
    S.sel = name; S.tab = 'tools'; S.trying = null; S.info = null; S.openCall = null; S.callTool = '';
    if (S.form) { S.form = null; renderForm(); }      // 다른 서버를 고르면 쓰던 등록 폼을 닫는다(상세 자리는 하나다)
    renderServers(); renderDetail(); UI.revealDetail(S.el.querySelector('#mcpDetail'));
  }

  // 읽는 차례(기준 5-1): 이름 + 연결 상태 → 에이전트 도구로 고를 수 있는지 → 쓰는 곳 → 도구 · 호출 기록 → 「자세히」(연결 설정)
  function renderDetail() {
    const box = S.el.querySelector('#mcpDetail');
    if (S.form) { box.innerHTML = ''; return; }      // 등록 · 고치기 폼을 쓰는 동안 상세 자리는 폼이 쓴다
    const s = S.servers.find(x => x.name === S.sel);
    if (!s) { box.innerHTML = S.servers.length ? UI.empty('도구 서버를 고르세요', '왼쪽 목록에서 고르면 그 서버의 도구와 호출 기록이 보입니다.', 'compact') : ''; return; }
    const r = S.tools[s.name] || { loading: true };
    const tools = r.status === 'ok' ? r.tools : [];
    // 단계마다 실제 담당과 그 실행이 이 서버로 쓰는 도구(서버 계산 — agents_store.run_servers, 워커와 같은 규칙)
    const tasks = s.tasks.length ? `<ul class="rd-lines">${s.tasks.map(t => `<li><span>${esc(UI.flowName(t.activity_name))}</span><small>${esc(t.agent || '담당 없음')}${t.fixed_tools ? ' · 정해진 조회 도구만' : ''}</small></li>`).join('')}</ul>` : '';
    const limit = r.timeout_s || S.listTimeout;
    const status = s.config_error ? `<p class="field-error" role="alert">${esc(s.config_error)}</p>`
      : r.loading ? hydLive.waitHtml('연결 확인 중', { since: r.since, hint: `도구 서버가 도구 목록을 돌려주기를 기다립니다${S.listTimeout ? ` (최대 ${S.listTimeout}초)` : ''}.` })
      : r.status === 'ok' ? `<p class="rd-note">도구 ${tools.length}개 · 응답 ${esc(hydTrace.fmtMs(r.elapsed_ms))} · ${esc(UI.dateTime(r.checked_at))} 확인</p>`
      : `<p class="field-error" role="alert">${esc(r.error || '연결 실패')}</p>${r.checked_at ? `<p class="rd-note">${esc(UI.dateTime(r.checked_at) + ' 확인' + (limit ? ' · 제한 ' + limit + '초' : ''))}</p>` : ''}`;
    const settings = [['서버 식별자', s.name], ['등록한 설명 원문', s.description], ['연결 오류 원문', s.config_error || r.error], ['서버가 보고한 이름', r.server_info?.name],
      ['종류', T[s.transport]], ['주소', s.url], ...Object.entries(s.headers || {}).map(([k, v]) => ['접속 헤더 ' + k, v])];
    const about = [s.description && /[가-힣]/.test(s.description) ? s.description : '', ORIGIN[s.origin] || '', T[s.transport] || ''].filter(Boolean).join(' · ');
    const seg = [['tools', '도구', r.status === 'ok' ? tools.length : null], ['calls', '호출 기록', null]].map(([k, l, n]) =>
      `<button type="button" role="tab" class="${k === S.tab ? 'on' : ''}" data-mcp-tab="${k}" aria-selected="${k === S.tab}">${esc(l)}${n != null ? `<span class="n">${n}</span>` : ''}</button>`).join('');
    box.innerHTML = `<header class="rd-head"><div><div class="rd-title"><h2>${esc(serverLabel(s.name))}</h2>${statusChip(s.name)}</div>${about ? `<p class="rd-sub">${esc(about)}</p>` : ''}</div>` +
      `<div class="rd-actions"><button class="btn small" id="mcpProbe" ${r.loading || s.config_error ? 'disabled' : ''}>연결 검사</button>` +
      (s.editable ? `<button class="btn small" id="mcpEdit"${reg()}>고치기</button><button class="btn small danger" id="mcpDelete">지우기</button>` : '') +
      `</div></header>` +
      `<div class="rd-group">${gateLine(s, r)}${status}</div>` +
      group('쓰는 곳', kv([['쓰는 에이전트', s.agents.length ? s.agents.map(a => esc(a.name)).join(', ') : '이 서버를 쓰는 에이전트가 없습니다'], ['이 서버로 도는 단계', tasks]])) +
      `<div class="rd-group"><div class="rd-seg" role="tablist" aria-label="보기">${seg}</div><div id="mcpPane"></div></div>` +
      `<div class="rd-group">${UI.fold('자세히 · 연결 설정 (비밀값은 ******** 로 가림)', kv(settings.map(([k, v]) => [k, v ? `<code>${esc(v)}</code>` : ''])) +
        `<p class="rd-note">${s.editable ? '고치기는 연결 검사를 통과해야 저장됩니다.' : '기준(기본 제공) 서버는 고치거나 지울 수 없습니다. 새 이름으로 등록해 씁니다.'}</p>`, { cls: 'small' })}</div>`;
    box.querySelector('#mcpProbe')?.addEventListener('click', ev => checkSaved(s.name, ev.currentTarget));
    box.querySelector('#mcpEdit')?.addEventListener('click', () => openForm(s));
    box.querySelector('#mcpDelete')?.addEventListener('click', ev => removeServer(s, ev.currentTarget));
    box.querySelectorAll('[data-mcp-tab]').forEach(b => b.addEventListener('click', () => { S.tab = b.dataset.mcpTab; renderDetail(); }));
    if (S.tab === 'calls') renderCalls(s); else renderTools(s, r);
  }

  // 도구 한 줄: 이름과 쓸 수 있는지. 설명 원문 · 입력 형식은 [설명 · 입력 형식]을 눌렀을 때, 폼은 [써 보기]를 눌렀을 때 그 줄 아래에 열린다
  function renderTools(s, r) {
    const pane = S.el.querySelector('#mcpPane');
    if (r.loading) { pane.innerHTML = UI.loading('', 'compact'); return; }
    if (r.status !== 'ok') {
      pane.innerHTML = UI.errorBlock('도구 목록을 받지 못했습니다', s.config_error || r.error || '', { retry: !s.config_error, cls: 'compact' });
      pane.querySelector('[data-retry]')?.addEventListener('click', () => probe(s.name));
      return;
    }
    if (!r.tools.length) { pane.innerHTML = UI.empty('이 서버는 도구를 내놓지 않습니다', '서버가 도구 목록을 비워 돌려줬습니다. 서버 쪽 설정을 확인하세요.', 'compact'); return; }
    const confirmed = new Set(s.read_confirmed || []);
    pane.innerHTML = `<ul class="mcp-tools">${r.tools.map(t => {
      const fields = fieldsOf(t.input_schema);
      const usable = t.callable || (confirmed.has(t.name) && t.confirmable);
      const open = S.trying === t.name, info = S.info === t.name;
      // G2 ②: 표시(readOnlyHint)만 없는 도구는 강사가 읽기로 확인할 수 있다 — 확인한 도구는 에이전트 도구 · 써 보기에 들어간다
      const kind = t.callable ? '읽기 전용' : usable ? '읽기로 확인함' : '';
      const confirmBtn = !s.editable || t.callable ? '' : usable ? `<button class="btn small" data-unconfirm="${esc(t.name)}"${reg()}>확인 취소</button>`
        : t.confirmable ? `<button class="btn small" data-confirm="${esc(t.name)}"${reg()}>읽기로 확인</button>` : '';
      const more = !info ? '' : `<div class="rd-tool-more"><h4 class="rd-label">에이전트가 읽는 설명 원문</h4><p class="rd-p">${esc(t.description || '설명 없음')}</p><h4 class="rd-label">입력 형식</h4>` +
        (fields.length ? `<div class="rd-scroll"><table class="tbl"><thead><tr><th>입력 칸</th><th>데이터 형식</th><th>설명</th></tr></thead><tbody>${fields.map(f =>
          `<tr><td><code>${esc(f.key)}</code>${f.required ? ' <i class="req">*</i>' : ''}</td><td>${esc(typeName(f))}</td><td>${esc(f.description || '')}</td></tr>`).join('')}</tbody></table></div>` : '<p class="rd-note">입력 없이 부릅니다.</p>') +
        `<p class="rd-note">도구 원래 이름 <code>${esc(t.name)}</code></p></div>`;
      return `<li class="mcp-tool${open ? ' open' : ''}" data-tool="${esc(t.name)}"><div class="mcp-tool-head"><div><b>${esc(toolLabel(s.name, t.name))}</b>${usable ? '' : ' ' + UI.chipText('써 보기 불가', 'warning')}` +
        `<span class="mcp-desc">${esc([kind, fields.length ? `입력 ${fields.length}칸` : '입력 없음'].filter(Boolean).join(' · '))}</span>${usable ? '' : `<span class="mcp-why">${esc(t.refuse_reason || '')}</span>`}</div>` +
        `<div class="rd-actions">${confirmBtn}<button class="btn small ghost" data-info="${esc(t.name)}" aria-expanded="${info}">${info ? '설명 닫기' : '설명 · 입력 형식'}</button>` +
        `<button class="btn small" data-try="${esc(t.name)}" aria-expanded="${open}" ${usable ? '' : 'disabled'}>${open ? '닫기' : '써 보기'}</button></div></div>` +
        (S.confirming === t.name ? confirmForm(s, t) : '') + more + (open ? tryForm(s, t, fields) : '') + '</li>';
    }).join('')}</ul>`;
    pane.querySelectorAll('[data-try]').forEach(b => b.addEventListener('click', () => { S.trying = S.trying === b.dataset.try ? null : b.dataset.try; renderTools(s, r); }));
    pane.querySelectorAll('[data-info]').forEach(b => b.addEventListener('click', () => { S.info = S.info === b.dataset.info ? null : b.dataset.info; renderTools(s, r); }));
    pane.querySelectorAll('[data-confirm]').forEach(b => b.addEventListener('click', () => { S.confirming = S.confirming === b.dataset.confirm ? null : b.dataset.confirm; renderTools(s, r); }));
    pane.querySelectorAll('[data-unconfirm]').forEach(b => b.addEventListener('click', () => readConfirm(s, b.dataset.unconfirm, false, b)));
    pane.querySelector('#mcpConfirmSave')?.addEventListener('click', ev => readConfirm(s, S.confirming, true, ev.currentTarget));
    if (S.trying) wireTry(s, r.tools.find(t => t.name === S.trying));
  }

  function confirmForm(s, t) {
    return `<div class="form mcp-confirm">${UI.section('', UI.field({ label: '읽기라고 본 이유', required: true, input: '<input id="mcpConfirmReason" placeholder="예: 서버 문서상 검색 결과만 돌려주고 아무것도 바꾸지 않는다">',
        hint: `서버가 ‘${toolLabel(s.name, t.name)}’에 읽기 전용 표시를 붙이지 않았습니다. 확인하면 에이전트 도구로 붙고 써 보기도 됩니다. 쓰기로 표시했거나 이름이 쓰기인 도구는 확인할 수 없습니다` }))}` +
      `<div class="rd-form-actions"><button class="btn" id="mcpConfirmSave"${reg()}>읽기로 확인</button></div></div>`;
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
    // 칸 도움말: 데이터 형식 · 원래 이름, 그리고 이름표로 쓰지 않은 설명 원문(이름표가 이미 설명이면 되풀이하지 않는다)
    const hint = f => [typeName(f), '원래 이름 ' + f.key, f.description && f.description !== fieldLabel(f) ? f.description : ''].filter(Boolean).join(' · ');
    const body = fields.length ? UI.section('', fields.map(f => UI.field({ label: fieldLabel(f), required: f.required, input: inputFor(f), hint: hint(f) })).join('')) : '<p class="rd-note">입력 없이 부릅니다.</p>';
    return `<div class="mcp-try"><div class="form rd-form">${body}<div class="rd-form-actions"><button class="btn" id="mcpCall">실행해 보기</button></div></div>` +
      `<p class="rd-note">실제 서버를 부릅니다. 읽기 전용 도구만 허용되며 처리 건 · 설비 · 업무 DB 를 바꾸지 않습니다. 결과가 아주 길면 앞부분만 보이고 잘린 크기를 함께 알려 줍니다.</p>` +
      `<div id="mcpResult" aria-live="polite">${res ? resultHtml(res) : ''}</div></div>`;
  }

  function resultHtml(res) {
    if (res.loading) return hydLive.waitHtml('도구를 실행하는 중', { since: res.since, hint: '도구 서버의 응답을 기다립니다. 서버가 결과를 한 번에 줍니다.' });
    if (res.error) return `<p class="field-error" role="alert">${esc(res.error)}</p>`;
    const r = res.result;
    // 결론(받았는지 · 오류인지) → 결과 → 원문 차례. 걸린 시간 · 길이 · 보낸 입력은 둘째 줄
    return `<h4 class="rd-label rd-group">결과</h4><p class="rd-state ${r.is_error ? 'bad' : 'ok'}">${r.is_error ? '도구가 오류를 돌려줬습니다' : '결과를 받았습니다'}${r.truncated ? ` — ${r.limit_chars.toLocaleString()}자에서 잘렸습니다` : ''}</p>` +
      `<p class="rd-note">${esc(hydTrace.fmtMs(res.elapsed_ms))} · ${r.size_chars.toLocaleString()}자 · 보낸 입력 <code>${esc(JSON.stringify(res.arguments))}</code></p>` +
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
    const body = flat ? `<div class="rd-scroll"><table class="tbl"><thead><tr>${cols.map(c => `<th>${esc(colName(c))}</th>`).join('')}</tr></thead>`
        + `<tbody>${rows.slice(0, 100).map(r => `<tr>${cols.map(c => `<td>${cell(r[c])}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`
        + (rows.length > 100 ? `<p class="rd-note">${rows.length}행 중 100행만 표로 보입니다. 나머지는 원문에 있습니다.</p>` : '')
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
      S.results[key] = { loading: true, since: new Date().toISOString() }; out.innerHTML = resultHtml(S.results[key]);
      try { S.results[key] = await postJ(api(`/api/mcp/servers/${encodeURIComponent(s.name)}/tools/${encodeURIComponent(t.name)}/call`), { arguments: args, by }); }
      catch (e) { S.results[key] = { error: e.message }; }
      out.innerHTML = resultHtml(S.results[key]); btn.disabled = false;
    });
  }

  async function renderCalls(s) {
    const pane = S.el.querySelector('#mcpPane');
    const tools = ((S.tools[s.name] || {}).tools || []).map(t => t.name);
    const filter = `<div class="rd-inline rd-call-filter"><label for="mcpCallTool" class="rd-note">도구</label><select id="mcpCallTool"><option value="">전체</option>${tools.map(t => `<option value="${esc(t)}" ${t === S.callTool ? 'selected' : ''}>${esc(toolLabel(s.name, t))}</option>`).join('')}</select></div>`;
    pane.innerHTML = filter + `<div id="mcpCallList">${UI.loading('', 'compact')}</div>`;
    pane.querySelector('#mcpCallTool').addEventListener('change', ev => { S.callTool = ev.target.value; S.openCall = null; renderCalls(s); });
    const list = pane.querySelector('#mcpCallList');
    let r;
    try { r = await getJ(api(`/api/mcp/calls?server=${encodeURIComponent(s.name)}${S.callTool ? '&tool=' + encodeURIComponent(S.callTool) : ''}&limit=50`)); }
    catch (err) { list.innerHTML = UI.errorBlock('호출 기록을 불러오지 못했습니다', err.message, { retry: true, cls: 'compact' }); list.querySelector('[data-retry]').addEventListener('click', () => renderCalls(s)); return; }
    if (S.sel !== s.name || S.tab !== 'calls') return;
    if (!r.calls.length) { list.innerHTML = UI.emptyGo('아직 이 도구를 부른 처리 건이 없습니다', `최근 도구 이벤트 ${r.scanned}개에서 찾았습니다. 경보로 처리 건이 돌거나 에이전트에게 질문하면 여기에 쌓입니다.`, 'ask', '질문하기', 'compact'); return; }
    drawCalls(s, r);
  }
  // 호출 한 줄: 도구 · 시각 · 어느 처리 건의 어느 단계 → 입력 · 결과 요약. 상태 칩은 끝나지 않았거나 오류일 때만. 전체 원문은 그 줄을 열었을 때
  function drawCalls(s, r) {
    const list = S.el.querySelector('#mcpCallList');
    if (!list) return;
    const STATE = { error: ['오류', 'danger'], running: ['진행 중', 'accent'] };
    list.innerHTML = `<ul class="mcp-calls">${r.calls.map((c, i) => {
      const state = STATE[c.state], open = S.openCall === i;
      return `<li><div class="mcp-call-head"><b>${esc(toolLabel(c.server, c.tool))}</b>${state ? UI.chipText(state[0], state[1]) : ''}` +
        `<span class="muted">${esc(UI.dateTime(c.at))}${c.duration_ms != null ? ' · ' + esc(hydTrace.fmtMs(c.duration_ms)) : ''}</span></div>` +
        `<p class="rd-note">${esc([c.instance_name || UI.idText(c.proc_inst_id), c.task_name].filter(Boolean).join(' · '))}` +
        `${c.link ? ` · <a href="${esc(c.link)}">처리 건에서 보기</a>` : ''}</p>` +
        kv([['입력', c.input_summary ? `<code>${esc(c.input_summary)}</code>` : ''], ['결과', c.output_summary ? `<code>${esc(c.output_summary)}</code>` : c.state === 'running' ? '아직 끝나지 않음' : '']]) +
        `<button type="button" class="link-btn" data-call-open="${i}" aria-expanded="${open}">${open ? '전체 닫기' : '입력 · 결과 전체 보기'}</button>` +
        (open ? `<pre class="mcp-out">입력\n${esc(c.input || '–')}\n\n결과\n${esc(c.output || '–')}</pre>` : '') + '</li>';
    }).join('')}</ul>` + (r.scanned >= r.scan_limit ? `<p class="rd-note">최근 도구 이벤트 ${r.scan_limit}개까지만 훑었습니다. 그보다 오래된 호출은 처리 건 화면에서 보세요.</p>` : '');
    list.querySelectorAll('[data-call-open]').forEach(b => b.addEventListener('click', () => { const i = Number(b.dataset.callOpen); S.openCall = S.openCall === i ? null : i; drawCalls(s, r); }));
  }

  // ---------------------------------------------------------------- 등록 · 고치기 · 지우기 · 연결 검사 · 되돌리기
  // 고를 수 있음 = 마지막 연결 검사 통과 기록(서버 게이트), 지금 상태 = 화면을 열 때 다시 잰 것 — 둘이 갈리면 지금 붙여도 된다고 읽히지 않게
  // 그 사실을 말한다(카드 · 상세가 이 한 문장을 쓴다, 2026-11-01 메뉴 눈 확인 · 11-02 독립 검증)
  function stampGap(s, r) {
    return s.selectable && r && r.status === 'failed'
      ? `지난 연결 검사는 통과했지만 지금은 연결되지 않습니다(${KIND[r.error_kind] || '연결 검사 실패'}) — 서버를 켠 뒤 다시 읽으세요` : '';
  }

  // 에이전트 도구로 고를 수 있는지 한 문장(상태는 앞의 점 색으로 — 초록 = 고를 수 있음, 노랑 = 지금은 안 됨)
  function gateLine(s, r) {
    const gap = stampGap(s, r);
    if (gap) return `<p class="rd-state warn">${esc(gap)}</p>`;
    const c = s.check || {};
    const when = c.checked_at ? ` · ${esc(UI.dateTime(c.checked_at))}` : '';
    if (s.selectable && s.origin === 'seed') return `<p class="rd-state ok">에이전트 도구로 고를 수 있음 — 기준 서버라 기본 에이전트도 이 서버를 씁니다</p>`;
    if (s.selectable) return `<p class="rd-state ok">에이전트 도구로 고를 수 있음 — 연결 검사 통과${when}, 읽기 전용 도구만 에이전트에 붙습니다</p>`;
    return `<p class="rd-state warn">에이전트 도구로 고를 수 없음 — ${esc(s.reason || CHECK[c.status] || '연결 검사 전')}${when}</p>`;
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
    renderForm(); renderDetail(); renderServers(); UI.revealDetail(S.el.querySelector('#mcpForm'));
  }

  function readForm() {
    const box = S.el.querySelector('#mcpForm');
    box.querySelectorAll('[data-f]').forEach(i => { S.form.v[i.dataset.f] = i.value; });
    return S.form.v;
  }

  function renderForm() {
    const box = S.el.querySelector('#mcpForm');
    const F = S.form;
    const add = S.el.querySelector('#mcpAdd'); if (add) add.hidden = !!F;      // 주 단추는 화면에 하나 — 폼을 쓰는 동안에는 폼의 [검사 후 등록]이 주 단추다
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
        hint: '토큰은 값 대신 \${SECRET:이름} 으로 적고, 값은 화면 아래 [고급]의 비밀 값에 넣으세요. 값을 그대로 적으면 저장하되 화면에서는 ******** 로 가립니다' }),
      UI.field({ label: '설명', input: `<input data-f="description" maxlength="200" value="${esc(v.description)}" placeholder="이 서버가 하는 일 한 줄">` }),
    ].join('');
    // 폼은 상세 자리에 한 열로(기준 5-6): 제목 → 칸 → 맨 아래 왼쪽에 주 단추 · 보조 단추
    box.innerHTML = `<header class="rd-head"><div><div class="rd-title"><h2>${F.editing ? `서버 고치기 — ${esc(v.name)}` : '서버 등록'}</h2></div>` +
      `<p class="rd-sub">연결 검사를 통과해야 저장됩니다. 저장한 서버의 읽기 전용 도구만 에이전트 도구로 고를 수 있습니다.</p></div></header>` +
      `<div class="form rd-form rd-group">${UI.section('', fields)}${F.error ? `<p class="field-error" role="alert">${esc(F.error)}</p>` : ''}` +
      `<div class="rd-form-actions"><button class="btn primary" id="mcpSave" ${F.busy ? 'disabled' : ''}${reg()}>${F.editing ? '검사 후 저장' : '검사 후 등록'}</button>` +
      `<button class="btn" id="mcpDry" ${F.busy ? 'disabled' : ''}${reg()}>연결 검사만</button><button class="btn" id="mcpFormClose">취소</button></div></div>` +
      `<div id="mcpFormResult" class="rd-group" aria-live="polite">${F.busy ? hydLive.waitHtml('연결 검사 중', { since: F.since, hint: `적은 주소의 서버에 연결해 인사를 주고받고 도구 목록을 받는 중입니다${S.listTimeout ? ` (최대 ${S.listTimeout}초)` : ''}. 통과해야 저장합니다.` }) : checkHtml(F.result)}</div>`;
    box.querySelector('#mcpFormClose').addEventListener('click', () => { S.form = null; renderForm(); renderDetail(); });
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
    return `<p class="rd-state ok">연결 검사를 통과했습니다 — 도구 ${c.tools.length}개 · ${esc(hydTrace.fmtMs(c.elapsed_ms))}</p>` +
      `<ul class="mcp-tools">${c.tools.map(t => `<li class="mcp-tool"><b>${esc(checkToolName(t))}</b>${t.read_only ? '' : ' ' + UI.chipText('붙일 수 없음', 'warning')}` +
        `<span class="mcp-desc">${esc(t.read_only ? '에이전트에 붙일 수 있음' : (t.reason || '') + (t.confirmable ? ' — 등록 뒤 [읽기로 확인]할 수 있습니다' : ''))}</span>` +
        `<span class="mcp-desc">${esc(t.description || '설명 없음')}</span></li>`).join('')}</ul>`;
  }

  async function submitForm(dry) {
    const F = S.form;
    if (F.busy) return;
    let body;
    try { body = bodyFrom(readForm()); } catch (e) { F.error = e.message; renderForm(); return; }
    body.by = actor(); if (!body.by) return;
    F.busy = true; F.since = new Date().toISOString(); F.error = ''; F.result = null; renderForm();
    try {
      const r = dry ? await postJ(api('/api/mcp/check'), body)
        : F.editing ? await postJ(api(`/api/mcp/servers/${encodeURIComponent(body.name)}`), body, 'PUT')
        : await postJ(api('/api/mcp/servers'), body);
      F.result = r.check; F.busy = false;
      if (!dry) {
        UI.toast(`${body.name}: ${F.editing ? '고쳤습니다' : '등록했습니다'} · 에이전트에 붙일 수 있는 도구 ${r.gate.read_tools.length}개`, { tone: 'ok' });
        (r.warnings || []).forEach(w => UI.toast(`${body.name}: ${w}`, { tone: 'neg' }));
        S.form = null; renderForm(); S.sel = body.name; S.trying = null; S.info = null; await load(); return;
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
    catch (e) { box.innerHTML = `<h3 class="rd-label">비밀 값</h3>` + UI.errorBlock('비밀 값 목록을 불러오지 못했습니다', e.message, { retry: true, cls: 'compact' }); box.querySelector('[data-retry]').addEventListener('click', loadSecrets); S.el.querySelector('#mcpOperator').open = true; return; }
    renderSecrets();
  }

  function renderSecrets() {
    const box = S.el.querySelector('#mcpSecrets');
    const list = (S.secrets && S.secrets.secrets) || [];
    const missing = list.filter(x => x.missing).length;
    const rows = list.length ? `<ul class="mcp-tools">${list.map(x => `<li class="mcp-tool"><div class="mcp-tool-head"><div><b>${esc(x.key)}</b>${x.stored ? '' : ' ' + UI.chipText('값 없음', 'danger')}` +
      `<span class="mcp-desc">${x.stored ? '저장됨 · ' : ''}${x.used_by.length ? '쓰는 서버: ' + x.used_by.map(n => esc(serverLabel(n))).join(', ') : '쓰는 서버 없음'}${x.updated_at ? ' · ' + esc(UI.dateTime(x.updated_at)) + ' ' + esc(x.updated_by ? UI.who(x.updated_by) : '') : ''}</span></div>` +
      (x.stored ? `<button class="btn small danger" data-secret-del="${esc(x.key)}"${reg()}>지우기</button>` : '') + '</div></li>').join('')}</ul>` : '<p class="rd-note">아직 넣은 비밀 값이 없습니다.</p>';
    const form = `<div class="form rd-form">${UI.section('', UI.field({ label: '이름', required: true, input: '<input id="mcpSecretKey" placeholder="MY_TOKEN">', hint: '대문자 · 숫자 · 밑줄' }) +
      UI.field({ label: '값', required: true, input: '<input id="mcpSecretValue" type="password" autocomplete="off">', hint: '저장하면 다시 보이지 않습니다. 토큰이 만료되면 같은 이름으로 다시 넣으세요' }))}` +
      `<div class="rd-form-actions"><button class="btn" id="mcpSecretSave"${reg()}>비밀 값 저장</button></div></div>`;
    box.innerHTML = `<h3 class="rd-label">비밀 값</h3>` + ((S.secrets && S.secrets.rule) ? `<p class="rd-note">${esc(S.secrets.rule)}</p>` : '') + rows + form;
    const operator = S.el.querySelector('#mcpOperator');
    operator.querySelector('[data-mcp-missing]').textContent = missing ? ` — 값이 없는 비밀 값 ${missing}개` : '';
    if (missing) operator.open = true;
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
    S.el.querySelector('[data-mcp-intro]').textContent = why ? '준비된 도구 서버(MCP)와 그 도구를 보고, 읽기 전용 도구를 직접 불러 결과를 확인합니다.'
      : '에이전트가 쓰는 도구 서버(MCP)와 그 도구를 보고, 내 서버를 등록해 에이전트 도구로 씁니다.';
    S.el.querySelector('[data-mcp-why]').textContent = why;
    S.el.querySelector('#mcpAdd').outerHTML = `<button class="btn primary" id="mcpAdd"${reg()}${S.form ? ' hidden' : ''}>서버 등록</button>`;
    S.el.querySelector('#mcpAdd').addEventListener('click', () => openForm(null));
  }

  function mount(el) {
    if (!el) return;
    S.el = el;
    // 차례: 제목 · 한 문장 · 주 단추 하나 → 왼쪽 서버 목록 · 오른쪽 상세(등록 폼도 이 자리) → 맨 아래 「고급」(비밀 값 · 기준으로 되돌리기)
    el.innerHTML = `<div class="page-head"><h1>${esc(UI.t('nav.mcp'))}</h1><div class="page-tools"><button class="btn" id="mcpReload">다시 읽기</button><button class="btn primary" id="mcpAdd">서버 등록</button></div></div>` +
      `<p class="page-lead" data-mcp-intro></p><p class="rd-note" data-mcp-why></p>` +
      `<div class="rd-split"><div class="rd-side"><div id="mcpServers"></div></div><div><div id="mcpForm"></div><div id="mcpDetail"></div></div></div>` +
      `<details class="fold small rd-advanced" id="mcpOperator"><summary>고급 · 비밀 값 · 기준으로 되돌리기<span class="neg" data-mcp-missing></span></summary><div class="fold-body"><div id="mcpSecrets"></div>` +
      `<p class="rd-foot"><span>내가 등록한 서버, 포털 밖에서 추가한 서버, 모든 연결 검사 기록과 비밀 값을 지우고 수업 기준으로 돌아갑니다.</span><button class="btn small danger" id="mcpReset">기준으로 되돌리기</button></p></div></details>`;
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
