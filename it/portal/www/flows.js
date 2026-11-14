/* B3 흐름 — bpmn.io 에서 그린 .bpmn → 단계마다 종류 · 담당 → 시작 조건 → 분기 조건 → 사전 검사 → 판본 등록 → (배포) → 시작.
   화면은 목록 + 상세다(index.html view-flows, 디자인 기준 5-4). 왼쪽은 이 시스템의 흐름 전부(기본 제공 · 내가 가져온 것), 오른쪽은 고른 흐름 하나:
     머리(이름 · 상태) → 단계 줄(가져오기 → 단계 설정 · 검사 → 판본 등록 → 배포 → 시작 가운데 어디까지 왔는지) → 흐름 그림 → 단계 설정 → 검사 · 판본 등록 — 이 파일이 #flowsView 에,
     판본 · 배포 — definitionDeploy.js 가 #definitionDeployPanel 에, 시작 — 이 파일이 #flowsStart 에 그린다.
   흐름 그림은 bpmn-js 로 학생이 그린 배치 그대로 보여 주기만 한다(flow.js 의 hydFlow.show — 처리 건의 진행 길과 같은 부품). 포털에서 그리지 않는다.
   window.hydFlows.mount(el) 이 그린다(셸 MOUNTS.flows).
   API: procsvc/flows_api.py (/api/flows/catalog · import · {id} · {id}/mapping · {id}/check · {id}/register ·
        {id}/versions/{v}/bpmn · reset), 직접 시작은 기존 POST /api/instances/start.
   원본 대조: process-gpt-vue3 ProcessGPTBackend.ts:573-685(proc_def.bpmn · 판본 snapshot) — 화면 모델러는 만들지 않는다(bpmn.io 에서 그린다). */
(function () {
  // ---------------------------------------------------------------- 값 다루기
  const TYPES = ['text', 'textarea', 'number', 'integer', 'boolean', 'select', 'object', 'array'];
  const TYPE_LABEL = { text: '글', textarea: '긴 글', number: '숫자', integer: '정수', boolean: '예/아니요', select: '고르기', object: '묶음(JSON)', array: '목록(JSON)' };
  // 칸 배열(값 이름 · 화면 이름 · 종류 · 고를 값) 검사 — 틀리면 몇 번째 칸인지 학생 말로. 값 이름이 빈 새 줄은 뺀다
  function checkFields(rows) {
    return (rows || []).filter(r => (r.key || '').trim() || (r.text || '').trim()).map((r, i) => {
      const key = (r.key || '').trim(), type = r.type || 'text';
      if (!key) throw new Error(`${i + 1}번째 칸: 값 이름(영문)을 적으세요`);
      if (!TYPES.includes(type)) throw new Error(`${i + 1}번째 칸: 종류 '${type}'는 쓸 수 없습니다`);
      const f = { key, text: (r.text || '').trim() || key, type };
      if (type === 'select') {
        f.items = (r.items || []).map(x => String(x).trim()).filter(Boolean);
        if (!f.items.length) throw new Error(`${i + 1}번째 칸(${f.text}): 고르기 칸에는 고를 값을 쉼표로 적으세요`);
      }
      return f;
    });
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
    server: ['도구 서버', 'text'], tool: ['실행할 도구', 'text'], arguments: ['도구에 보낼 값', 'object'],
    output: ['결과를 담을 값 이름', 'text'], extract: ['결과에서 꺼낼 값', 'object'], effect: ['호출 목적', 'boolean'],
    duration: ['기다릴 시간', 'text'], until: ['기다릴 시각이 담긴 값', 'text'], label: ['대기 중 표시할 이름', 'text'],
    outcome: ['처리 결과', 'outcome'], title: ['보고 제목', 'text'], summary: ['보고 내용', 'textarea'], notify: ['추가 보고 대상', 'array'],
    mail: ['공지 메일', 'object'], component: ['정비할 부품', 'component'], sop: ['조치 방법', 'text'],
    work_order_var: ['정비 요청이 담긴 값', 'text'], purchase_order_var: ['발주가 담긴 값', 'text'],
    criteria: ['확인 기준', 'object'], settle: ['안정될 때까지 기다릴 시간', 'text'],
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

  // ---------------------------------------------------------------- 상태 · 도우미
  // sel: 고른 흐름 id · kind: 목록 거르기(all · base · mine) · importing: 가져오기 폼을 쓰는 중 · view/mapping: 고른 흐름의 초안(GET /api/flows/{id})
  // xml: 이번에 가져온 그림 원문(흐름 id → 글) — 서버는 초안의 그림을 다시 주지 않으므로, 가져온 직후의 그림은 이 원문으로 그린다
  const S = { el: null, cat: null, list: null, defs: [], listError: '', sel: null, kind: 'all', importing: false, view: null, mapping: null, viewError: '',
    xml: {}, starts: {}, drawn: null, timer: null, revision: 0, events: null, startKey: '', defCache: new Map(), deleting: false };
  const $ = id => document.getElementById(id);
  const api = p => API.process + p;
  const h = s => esc(s);
  const icon = (name, cls) => UI.icon(name, cls);
  const tag = (label, tone, plain) => `<span class="tag"${tone ? ` data-tone="${tone}"` : ''}${plain ? ' data-plain' : ''}>${h(label)}</span>`;
  // 알림 자리 하나에 적는 말: 실패는 키트의 오류 판(무엇이 · 왜), 된 일은 보통 판, 하는 중은 실시간 한 줄
  const okBox = (title, body = '') => `<div class="alert" role="status">${icon('circle-check')}<h2>${h(title)}</h2>${body ? `<section>${body}</section>` : ''}</div>`;
  const infoBox = (title, body = '') => `<div class="alert" role="status">${icon('info')}<h2>${h(title)}</h2>${body ? `<section>${body}</section>` : ''}</div>`;
  const failBox = (title, why) => UI.errorBlock(title, why);
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
    // 누른 단추가 「…중 · 걸린 시간」으로 바뀐다(다시 그려져 단추가 사라졌으면 손대지 않는다)
    locks.add(name); const end = button ? hydLive.busy(button, button.textContent.trim() + ' 중') : null;
    try { return await fn(); } finally { locks.delete(name); if (end && button.isConnected) end(); }
  }
  const partName = p => p ? ({ human: '담당자 입력', agent: 'AI 에이전트 작업' }[p.key] || UI.flowName(p.name)) : '';
  const roleOpts = (sel, human) => S.cat.roles.filter(r => !human || r.human).map(r => `<option value="${h(r.name)}" ${r.name === sel ? 'selected' : ''}>${h(r.name)}</option>`).join('');
  const agentOpts = sel => S.cat.agents.map(a => `<option value="${h(a.id)}" ${a.id === sel ? 'selected' : ''}>${h(a.name && a.name !== a.id ? a.name : UI.who(a.id) !== a.id ? UI.who(a.id) : 'AI 에이전트')}</option>`).join('');
  const nodeName = id => { const p = S.view && S.view.parsed; if (!p) return id; for (const k of ['tasks', 'starts', 'ends', 'boundaries', 'gateways']) { const n = p[k].find(x => x.id === id); if (n) return n.name || '(이름 없음)'; } return id; };
  // 누가 했는지: 판본 등록 · 지우기 · 되돌리기는 이 PC의 담당자로 기록한다(서버 flows_api 가 by 를 요구한다) — 없으면 그 자리에서 안내하고 보내지 않는다
  const meId = () => window.hydInbox?.me?.()?.id || '';
  const NEED_ME = '담당자 정보를 읽지 못했습니다. 화면을 새로 고친 뒤 다시 해 주세요.';

  // ---------------------------------------------------------------- 흐름 목록
  // 한 줄 = 흐름 하나: 가져온 초안(drafts) · 가져와 등록한 판본(versions) · 정의로 등록된 흐름(defs)을 흐름 id 로 묶는다
  function items() {
    const L = S.list || { drafts: [], versions: [] };
    const ids = [...new Set([...L.drafts.map(d => d.proc_def_id), ...L.versions.map(v => v.id), ...S.defs.map(r => r.id)])];
    return ids.map(id => {
      const draft = L.drafts.find(x => x.proc_def_id === id) || null, files = L.versions.filter(v => v.id === id), rows = S.defs.filter(r => r.id === id);
      const mine = (!!draft || files.length > 0) && !(draft?.class_flow || files.some(v => v.class_flow));
      const given = (files[files.length - 1] || {}).name || (draft && draft.mapping && draft.mapping.name) || (rows[0] || {}).name;
      const versions = [...new Set([...files.map(v => String(v.version)), ...rows.map(r => String(r.version))])];
      return { id, name: hydDefinitions.name(id, given), draft, files, mine, versions, deployed: (rows.find(r => r.deployed_version) || {}).deployed_version || null };
    }).sort((a, b) => rank(a) - rank(b));      // 내가 가져온 것 → 그림과 함께 들어 있는 기본 제공 흐름 → 정의로만 등록된 기본 흐름
  }
  const rank = x => (x.mine ? 0 : x.draft || x.files.length ? 1 : 2);
  // 시작 방식은 정의에서 읽는다(경보로 시작하는가 — alertPolicy). 흐름 이름으로 가르지 않는다. 아직 읽지 못했으면 null
  const startKind = x => S.starts[x.id] || (!x.versions.length && S.sel === x.id && S.mapping && S.mapping.start ? (S.mapping.start.kind === 'alert' ? 'alert' : S.mapping.start.kind === 'human' ? 'direct' : null) : null);
  // 상태 뱃지: 경보로 시작하는 흐름은 배포해야 쓰인다(운영 중 / 배포 전). 직접 시작하는 흐름(질문하기 · 문서 추출 · 교대 인수인계처럼 화면이나 사람이 여는 것)은
  // 등록돼 있으면 쓸 수 있다 — 「등록됨」만 적으면 안 쓰이는 것처럼 읽힌다
  function stateTag(x) {
    if (x.deployed) return tag(`운영 중`, 'ok');
    if (!x.versions.length) return tag('등록 전');
    const kind = startKind(x);
    return kind === 'direct' ? tag('시작 가능', 'ok') : kind === 'alert' ? tag('배포 전', 'warn') : tag('등록됨');
  }
  async function loadStarts() {
    const todo = items().filter(x => x.versions.length && !S.starts[x.id]);
    await Promise.all(todo.map(async x => { try { const d = await defOf(x.id, x.deployed || x.versions[x.versions.length - 1]); S.starts[x.id] = d.alertPolicy ? 'alert' : 'direct'; } catch (_) { /* 못 읽은 흐름은 「등록됨」으로 남는다 — 고르면 그 까닭이 상세에 보인다 */ } }));
    if (todo.length && S.el) { renderList(); if (!S.importing) { drawHead(); drawSteps(); markPrimary(); } }
  }
  const itemOf = id => items().find(x => x.id === id) || null;
  function renderList() {
    const all = items(), shown = all.filter(x => S.kind === 'all' || (S.kind === 'mine') === x.mine);
    $('flowKind').innerHTML = [['all', '전체', all.length], ['base', '기본 제공', all.filter(x => !x.mine).length], ['mine', '내가 가져온 것', all.filter(x => x.mine).length]]
      .map(([k, label, n]) => `<button type="button" aria-pressed="${k === S.kind}" data-flow-kind="${k}">${h(label)}${S.list ? `<span class="num">${n}</span>` : ''}</button>`).join('');      // 목록을 못 읽었으면 「0」을 적지 않는다
    const box = $('flowList');
    if (S.listError) { box.innerHTML = `<div class="pane-list-note">${UI.errorBlock('흐름 목록을 불러오지 못했습니다', S.listError, { retry: true })}</div>`; return; }
    if (!S.list) { box.innerHTML = Array.from({ length: 4 }, () => `<div class="sk-row"><div class="skeleton sk-line" style="width:55%"></div><div class="skeleton sk-line" style="width:35%"></div></div>`).join(''); return; }
    if (!shown.length) {
      box.innerHTML = `<div class="pane-list-note">${S.kind === 'mine' ? UI.empty('내가 가져온 흐름이 없습니다', '화면 위의 [흐름 가져오기]로 bpmn.io에서 그린 .bpmn 파일을 가져오면 여기에 남습니다.')
        : UI.empty('등록된 흐름이 없습니다', '화면 위의 [흐름 가져오기]로 .bpmn 파일을 가져오면 여기에 나타납니다.')}</div>`;
      return;
    }
    box.innerHTML = shown.map(x => {
      const state = stateTag(x);
      const meta = [x.mine ? '내가 가져온 것' : '기본 제공', x.versions.length ? `판본 ${x.versions[x.versions.length - 1]}${x.versions.length > 1 ? ` 외 ${x.versions.length - 1}` : ''}` : '판본 없음'].join(' · ');
      return `<button type="button" class="row" data-open="${h(x.id)}"${x.id === S.sel && !S.importing ? ' aria-current="true"' : ''}><span class="row-ic">${icon('workflow')}</span><span class="row-title">${h(x.name)}</span>${state}<span class="row-meta">${h(meta)}</span></button>`;
    }).join('');
  }

  async function loadCatalog() { S.cat = await call('GET', '/api/flows/catalog'); }
  async function loadList() {
    try {
      const [list, defs] = await Promise.all([call('GET', '/api/flows'), call('GET', '/api/process/definitions')]);
      S.list = list; S.defs = defs; S.listError = '';
    } catch (e) { S.listError = e.message; renderList(); if (!S.list) drawDetail(); return; }
    const all = items();
    loadStarts();
    // 다른 화면(에이전트의 맡은 단계)이 열어 달라고 한 흐름이 있으면 그 흐름을 고른다
    if (S.wanted) { const id = S.wanted; S.wanted = null; if (all.some(x => x.id === id)) { S.importing = false; S.kind = 'all'; return select(id); } }
    if (S.sel && !all.some(x => x.id === S.sel)) { S.sel = null; S.view = null; S.mapping = null; }
    if (!S.sel && all.length && !S.importing) return select(all[0].id);
    renderList();
    if (!S.importing && S.sel) refreshDetail();
    else if (!all.length && !S.importing) drawDetail();
  }

  // ---------------------------------------------------------------- 고르기 · 상세의 틀
  async function select(id, reveal) {
    S.sel = id; S.importing = false; S.view = null; S.mapping = null; S.viewError = ''; S.drawn = null;
    clearTimeout(S.timer);
    renderList(); drawDetail();
    if (reveal) UI.revealDetail($('flowPanel'));
    window.hydDefinitionDeploy.select(id);
    const item = itemOf(id);
    if (item && item.draft) {
      try { const view = await call('GET', '/api/flows/' + encodeURIComponent(id)); if (S.sel !== id || S.importing) return; S.view = view; S.mapping = view.mapping; }
      catch (e) { if (S.sel !== id || S.importing) return; S.viewError = e.message; }
      drawDetail();
    }
  }
  // 고른 흐름을 그대로 둔 채 다시 그린다(목록을 새로 읽은 뒤 · 등록 뒤)
  function refreshDetail() { drawDetail(); drawStart(); }

  function drawDetail() {
    const box = S.el;
    if (S.importing) return;
    const item = itemOf(S.sel);
    if (!item) markPrimary();
    if (!item) {
      S.drawn = null; $('definitionDeployPanel').hidden = true; $('flowsStart').hidden = true;
      box.innerHTML = S.listError ? '' : `<div class="pane-none">${S.list ? `${UI.empty({ icon: 'workflow', title: `흐름을 고르세요`, sub: `왼쪽 목록에서 흐름을 고르면 그림과 단계 설정, 판본이 여기에 보입니다. 새 흐름은 화면 위의 [흐름 가져오기]로 가져옵니다.` })}` : UI.loading('')}</div>`;
      return;
    }
    if (S.drawn !== item.id) {
      S.drawn = item.id;
      box.innerHTML = `<div class="panel-head pane-head" id="flowHead"></div>
        <div class="stream-phases flow-phases" id="flowSteps" role="list" aria-label="이 흐름이 어디까지 왔는지"></div>
        <div id="flowNote"></div>
        <div class="panel-sec"><h3>${icon('workflow', 'ic-sm')}흐름 그림</h3><div id="flowPicture"></div></div>
        <div class="panel-sec pane-fold" id="flowEditorSec" hidden><details class="fold" id="flowEditorFold"><summary>단계 설정<span class="muted" id="flowEditorSum"></span></summary><div class="fold-body"><div id="flowEditor"></div></div></details></div>
        <div class="panel-sec" id="flowRegisterSec" hidden><h3>${icon('clipboard-check', 'ic-sm')}검사 · 판본 등록<span class="muted" id="flowNextVersion"></span></h3><div id="flowProblems"></div><div id="flowMsg" aria-live="polite"></div><footer class="form-foot" id="flowActions"></footer></div>`;
      wire();
    }
    drawHead(); drawSteps(); drawPicture(); drawEditorFrame(); drawStart();
  }

  // 머리: 이름 + 상태 뱃지 + 한 문장. 오른쪽에 자주 쓰지 않는 동작(그림 받기 · 지우기)
  function drawHead() {
    const item = itemOf(S.sel), head = $('flowHead'); if (!item || !head) return;
    const p = S.view && S.view.parsed, st = window.hydDefinitionDeploy.status();
    const state = item.deployed ? tag('운영 중', 'ok') + tag(`판본 ${item.deployed}`, '', true) : stateTag(item);      // 상태(점 있는 이름표)와 판본(종류 뱃지)을 한 뱃지에 섞지 않는다
    const what = S.viewError ? '' : p ? `단계 ${p.tasks.length}개 · 갈림 ${p.gateways.length}개 · 연결선 ${p.flows.length}개${item.mine && S.view.file_name ? ` · ${S.view.file_name}` : ''}.`
      : item.draft ? '단계 설정을 읽는 중입니다.' : '그림 파일 없이 정의로 등록된 흐름입니다. 단계 설정은 정의에 들어 있어 여기서 고치지 않습니다.';
    const start = st ? (st.alert_entry ? `경보(${(st.alert_patterns || []).map(x => UI.patternName(x)).join(' · ') || '시작 조건의 경보'})가 나면 시작합니다.` : '직접 시작하는 흐름입니다 — 배포 없이, 등록한 판본으로 엽니다.') : '';
    const last = item.files[item.files.length - 1];
    const more = [last ? `<a role="menuitem" href="${h(api(`/api/flows/${encodeURIComponent(item.id)}/versions/${encodeURIComponent(last.version)}/bpmn`))}" download>${icon('download')}그림 받기 (.bpmn · 판본 ${h(last.version)})</a>` : '',
      item.mine ? `<div role="menuitem" data-flow-delete="${h(item.id)}">${icon('trash-2')}이 흐름 지우기</div>` : ''].filter(Boolean).join('');
    head.innerHTML = `<span class="pane-ic">${icon('workflow')}</span><div class="pane-title"><h2>${h(item.name)}${state}${tag(item.mine ? '내가 가져온 것' : '기본 제공', item.mine ? 'brand' : '', true)}</h2><p>${h([what, start].filter(Boolean).join(' '))}</p></div>` +
      (more ? `<div class="pane-acts"><div class="dropdown-menu" id="flowMore"><button type="button" class="btn" data-variant="outline" data-size="icon" id="flowMore-trigger" aria-haspopup="menu" aria-controls="flowMore-menu" aria-expanded="false" aria-label="더 보기" data-tooltip="더 보기" data-side="left">${icon('ellipsis')}</button>` +
        `<div id="flowMore-popover" data-popover aria-hidden="true" data-align="end"><div role="menu" id="flowMore-menu" aria-labelledby="flowMore-trigger">${more}</div></div></div></div>` : '');
  }

  // 단계 줄: 이 흐름이 끝낸 단계는 초록 체크, 다음에 할 단계 하나가 제품색이다. 사람이 할 차례를 가리킬 뿐이라 도는 고리는 쓰지 않는다(data-idle)
  // 단계는 흐름에 맞는 것만 보인다: 그림을 가져온 흐름은 「가져오기 → 단계 설정 · 검사 → 판본 등록」부터, 그림 파일 없이 정의로 등록된 흐름은 「판본 등록」부터.
  // 「배포」는 경보로 시작하는 흐름에만 있다(직접 시작하는 흐름은 등록한 판본으로 바로 연다)
  const directStart = item => startKind(item) === 'direct';
  function stepsOf(item) {
    const v = S.view, registered = item.versions.length > 0, imported = !!item.draft || item.files.length > 0;
    const steps = [];
    if (imported) steps.push(['import', '가져오기', true], ['check', '단계 설정 · 검사', registered || !!(v && v.check && v.check.ok)]);
    steps.push(['register', '판본 등록', registered]);
    if (!directStart(item)) steps.push(['deploy', '배포', !!item.deployed]);
    steps.push(['start', '시작', false]);
    return steps;
  }
  // 지금 할 단계: 끝나지 않은 첫 단계
  const nowStep = item => (stepsOf(item).find(([, , done]) => !done) || [])[0];
  function drawSteps() {
    const item = itemOf(S.sel), box = $('flowSteps'); if (!item || !box) return;
    const steps = stepsOf(item), at = steps.findIndex(([, , done]) => !done);
    box.innerHTML = steps.map(([, name], i) => `<span class="phase" role="listitem" data-state="${i < at ? 'done' : i === at ? 'now' : 'todo'}"${i === at ? ' data-idle aria-current="step"' : ''}><i></i>${h(name)}</span>`).join('');
    markPrimary();
  }
  // 주 단추는 화면에 하나: 단계 줄이 「지금」이라고 말하는 단계의 단추만 주 단추이고 나머지는 보통 단추다.
  // 고른 흐름에 지금 누를 단추가 없을 때(경보를 기다리는 흐름 · 읽기만 하는 흐름)만 화면 머리의 [흐름 가져오기]가 주 단추다
  function markPrimary() {
    const item = !S.importing && itemOf(S.sel), at = item ? nowStep(item) : null;
    const set = (node, on) => { if (!node) return false; if (on) node.removeAttribute('data-variant'); else node.setAttribute('data-variant', 'outline'); return on; };
    const used = [set($('flowCheck'), at === 'check'), set($('flowRegister'), at === 'register'),
      ...[...document.querySelectorAll('#deployVersions [data-deploy]')].map(b => set(b, at === 'deploy' && b.hasAttribute('data-deploy-next') && !b.disabled)),
      set(document.querySelector('#flowsStart [data-go]'), at === 'start' && !document.querySelector('#flowsStart [data-go]')?.disabled)].some(Boolean);
    set($('flowImportOpen'), !used && !S.importing);
  }
  window.addEventListener('hyd:deployed', () => { if (!S.el || !S.list) return; S.defs = window.hydDefinitionDeploy.rows(); renderList(); if (!S.importing) { drawHead(); drawSteps(); } });
  window.addEventListener('hyd:deploy-status', () => { if (!S.el || S.importing) return; const st = window.hydDefinitionDeploy.status(); if (st) S.starts[st.id] = st.alert_entry ? 'alert' : 'direct'; renderList(); drawHead(); drawSteps(); drawStart(); });

  // ---------------------------------------------------------------- 흐름 그림(bpmn-js, 보기 전용)
  const defOf = (id, version) => {
    const key = id + '@' + version;
    if (!S.defCache.has(key)) { const job = call('GET', `/api/process/definitions/${encodeURIComponent(id)}?version=${encodeURIComponent(version)}`); S.defCache.set(key, job); job.catch(() => S.defCache.delete(key)); }
    return S.defCache.get(key);
  };
  // 초안의 단계 · 갈림 · 선(서버가 그림에서 읽은 것) → 그림 없는 정의 꼴. 등록 전 초안을 다시 열었을 때만 쓴다(서버가 초안의 그림 원문을 다시 주지 않는다)
  const parsedDef = (item, p) => ({ processDefinitionId: item.id, processDefinitionName: item.name,
    events: [...p.starts.map(x => ({ id: x.id, name: x.name, type: 'startEvent' })), ...p.ends.map(x => ({ id: x.id, name: x.name, type: 'endEvent' })),
      ...p.boundaries.map(x => ({ id: x.id, name: x.name, type: 'boundaryEvent', attachedTo: x.attached_to, eventDefinition: 'timer' }))],
    activities: p.tasks.map(t => ({ id: t.id, name: t.name, type: t.bpmn_type })), gateways: p.gateways.map(g => ({ id: g.id, name: g.name, type: g.gateway_type })),
    sequences: p.flows.map(f => ({ id: f.id, source: f.source, target: f.target, name: f.name })) });
  function drawPicture() {
    const item = itemOf(S.sel), host = $('flowPicture'); if (!item || !host) return;
    const version = item.deployed || item.versions[item.versions.length - 1] || null, fresh = S.xml[item.id];
    if (!fresh && !version && !S.view) {      // 등록 전 초안: 단계 설정을 읽어야 그릴 수 있다
      if (S.viewError) host.innerHTML = UI.errorBlock('흐름 그림을 그리지 못했습니다', S.viewError);
      else if (!host._flow) host.innerHTML = `<div class="canvas flow-canvas"><div class="flow-wait">${UI.loading('', 'compact')}</div></div>`;
      return;
    }
    window.hydFlow.show(host, {
      key: `${item.id}|${fresh ? 'file' + fresh.length : version ? 'v' + version : 'draft' + (item.draft.updated_at || '')}`,
      title: item.name, cap: fresh ? '방금 가져온 그림' : version ? '판본 ' + version : '등록 전 초안', mine: !!item.mine,
      load: async () => {
        if (fresh) return { xml: fresh, source: 'file' };
        if (version) {
          const got = await window.hydFlow.xmlOf(await defOf(item.id, version));
          return got;
        }
        return { xml: window.hydFlow.defToXml(parsedDef(item, S.view.parsed)), source: 'draft',
          note: '등록 전 초안은 가져온 그림을 다시 받을 수 없어 단계에서 자동으로 그렸습니다 — 그림을 다시 가져오거나 판본으로 등록하면 그린 배치 그대로 보입니다' };
      },
    });
  }

  // ---------------------------------------------------------------- 가져오기
  // 수업 경계(서버 GET /api/course-access 의 importable_flow): 수업 단계에서는 제공 흐름 하나만 가져온다 — 흐름 id 칸을 그 흐름으로 고정해
  // 다른 id 를 적어 거절당하지 않게 한다. PBL(값 null)이면 칸을 연다
  const ID_HINT = '비우면 그림 파일에 적힌 이름을 씁니다. 같은 이름으로 다시 가져오면 앞서 정한 단계 설정이 남습니다.';
  function idField() {
    const input = S.el && S.el.querySelector('#flowId'); if (!input) return;
    const only = hydCourseAccess.access && hydCourseAccess.access.importable_flow;
    input.disabled = !!only; input.value = only ? '' : input.value;
    input.placeholder = only ? '그림 파일에 적힌 이름 그대로' : '예: oil_check';
    const hint = input.closest('.field')?.querySelector('p');
    if (hint) hint.textContent = only ? '지금은 그림 파일에 적힌 이름을 그대로 씁니다.' : ID_HINT;
    const note = S.el.querySelector('[data-import-only]');      // 까닭 문장은 서버 수업 경계 한 곳(course_policy) — 폼 맨 위에서 먼저 말한다
    if (note) note.innerHTML = only ? infoBox('지금 가져올 수 있는 그림이 정해져 있습니다', h(hydCourseAccess.reason('import_flow'))) : '';
  }
  hydCourseAccess.onChange(() => { idField(); if (S.list && !S.importing) drawStart(); });
  function openImport() {
    S.importing = true; S.drawn = null; clearTimeout(S.timer); S.events?.abort(); markPrimary();
    $('definitionDeployPanel').hidden = true; $('flowsStart').hidden = true;
    renderList();
    S.el.innerHTML = `<div class="panel-head"><div><h2>흐름 가져오기</h2><p>흐름은 bpmn.io에서 그립니다. 그려서 받은 .bpmn 파일을 고르면 서버가 단계와 갈림, 시작과 끝을 읽습니다.</p></div></div>
      <div class="panel-sec">
        <div data-import-only></div>
        <ol class="flow-how"><li><a href="https://demo.bpmn.io" target="_blank" rel="noopener">demo.bpmn.io</a>에서 흐름을 그리거나, 받은 .bpmn 파일을 열어 고칩니다.</li><li>왼쪽 아래 <b>Download BPMN diagram</b>으로 .bpmn 파일을 받습니다.</li><li>아래에서 그 파일을 고르고 [가져오기]를 누릅니다.</li></ol>
        ${UI.section('가져올 그림', UI.field({ label: '.bpmn 파일', input: '<input type="file" id="flowFile" accept=".bpmn,.xml,application/xml,text/xml">', required: true }) +
          UI.field({ label: '흐름 구분 이름(영문)', input: '<input id="flowId" placeholder="예: oil_check" autocomplete="off">', hint: ID_HINT }))}
        <div id="flowImportMsg" aria-live="polite"></div>
        <footer class="form-foot"><button type="button" class="btn" data-variant="outline" id="flowImportCancel">취소</button><button type="button" class="btn" id="flowImport">${icon('file-up')}가져오기</button></footer>
      </div>`;
    S.el.querySelector('#flowImport').addEventListener('click', e => once('import', e.currentTarget, doImport));
    S.el.querySelector('#flowImportCancel').addEventListener('click', closeImport);
    idField();
    UI.revealDetail($('flowPanel'));
  }
  function closeImport() {
    S.importing = false;
    const all = items();
    if (S.sel && all.some(x => x.id === S.sel)) select(S.sel); else if (all.length) select(all[0].id); else { renderList(); drawDetail(); }
  }
  async function doImport() {
    const msg = S.el.querySelector('#flowImportMsg');
    const file = S.el.querySelector('#flowFile').files[0];
    if (!file) { msg.innerHTML = failBox('가져올 파일을 고르지 않았습니다', 'bpmn.io에서 받은 .bpmn 파일을 고른 뒤 [가져오기]를 누르세요.'); return; }
    msg.innerHTML = hydLive.waitHtml('그림을 읽는 중', { hint: '서버가 BPMN 그림에서 단계 · 갈림 · 시작과 끝을 읽고, 같은 이름으로 가져온 적이 있으면 앞서 정한 단계 설정과 맞춰 보는 중입니다.' });
    try {
      const xml = await file.text();
      const view = await call('POST', '/api/flows/import', { xml, file_name: file.name, start_patterns: [], definition_id: S.el.querySelector('#flowId').value.trim() || null });
      const r = view.reimport || {};
      S.xml[view.definition_id] = xml;
      S.importing = false;
      await loadListOnly();
      S.sel = view.definition_id; S.view = view; S.mapping = view.mapping; S.viewError = ''; S.drawn = null;
      renderList(); drawDetail(); window.hydDefinitionDeploy.select(view.definition_id);
      $('flowNote').innerHTML = `<div class="flow-note-box">${okBox(r.previous ? '그림을 다시 가져왔습니다' : '그림을 가져왔습니다',
        h(r.previous ? `단계 설정을 유지한 단계 ${r.kept.length}개, 새 단계 ${r.new.length}개, 사라진 단계 ${r.dropped.length}개입니다.` : `단계 ${view.parsed.tasks.length}개를 읽었습니다.`) + ' 아래 「단계 설정」에서 단계마다 종류와 담당을 정한 뒤 검사하세요.')}</div>`;
      UI.revealDetail($('flowPanel'));
    } catch (e) {
      // 무엇이 왜 안 됐는지: 서버의 까닭 한 문장, 그림에서 고칠 곳이 있으면 그 목록
      msg.innerHTML = failBox('그림을 가져오지 못했습니다', e.message) + (e.problems ? problemsBlock(e.problems, '그림에서 고칠 곳', false) : '');
    }
  }
  async function loadListOnly() {
    try { const [list, defs] = await Promise.all([call('GET', '/api/flows'), call('GET', '/api/process/definitions')]); S.list = list; S.defs = defs; S.listError = ''; }
    catch (e) { S.listError = e.message; }
  }

  // ---------------------------------------------------------------- 단계 설정
  // 고칠 수 있는가: 기본 제공 흐름(서버 class_flow)은 읽기만. 수업 단계의 제공 교대 흐름은 서버가 정한 칸만 연다(W3-08)
  function drawEditorFrame() {
    const item = itemOf(S.sel), sec = $('flowEditorSec'), reg = $('flowRegisterSec'); if (!item || !sec) return;
    if (!item.draft) { sec.hidden = true; reg.hidden = true; return; }
    sec.hidden = false;
    if (S.viewError) { $('flowEditor').innerHTML = UI.errorBlock('단계 설정을 읽지 못했습니다', S.viewError, { retry: true }); $('flowEditorFold').open = true; reg.hidden = true; return; }
    if (!S.view) { $('flowEditor').innerHTML = UI.loading(''); reg.hidden = true; return; }
    const fold = $('flowEditorFold');
    if (fold.dataset.for !== item.id) { fold.dataset.for = item.id; fold.open = !S.view.class_flow; }      // 내가 가져온 흐름은 펼쳐서, 기본 제공은 접어서 연다
    renderEditor();
  }
  /* 기본 제공 흐름의 단계 설정은 읽기 전용 표다(고칠 수 없는 것을 꺼진 입력 칸 수십 개로 그리지 않는다): 이름–값 한 벌(흐름 이름 · 시작 조건 · 칸마다의 역할)
     → 단계 표(단계 · 종류 · 누가 · 기한) → 갈림 표(갈림 · 가는 곳 · 조건). 고쳐 쓰려면 그림을 받아 bpmn.io 에서 고친 뒤 다른 이름으로 가져온다 */
  function readOnlyEditor(v, p, m) {
    const start = m.start || {};
    const agentName = id => { const a = S.cat.agents.find(x => x.id === id); return a && a.name && a.name !== a.id ? a.name : UI.who(id) !== id ? UI.who(id) : 'AI 에이전트'; };
    const timers = {}; p.boundaries.forEach(b => { const host = p.tasks.find(t => t.id === b.attached_to), part = host && S.cat.parts.find(x => x.key === (m.tasks[host.id] || {}).part);
      const iso = m.timers[b.id] || b.timer || (part && part.default_timer); if (host && iso) timers[host.id] = `${minutesOf(iso)}분 · ${b.name || '시간 초과'}`; });
    const steps = p.tasks.map(t => { const tm = m.tasks[t.id] || {}, part = S.cat.parts.find(x => x.key === tm.part), lane = (p.lanes.find(l => l.id === t.lane) || {}).name;
      const who = !part ? '–' : part.kind === 'agent' ? agentName(tm.agent || part.agent || '') : part.kind === 'service' ? '시스템' : tm.role || part.role || m.lanes[t.lane] || lane || '–';
      return `<tr><td><b>${h(UI.flowName(t.name || '(이름 없음)'))}</b></td><td>${h(part ? partName(part) : '정해지지 않음')}</td><td>${h(who)}</td><td class="muted">${h(timers[t.id] || '')}</td></tr>`; }).join('');
    const branches = p.gateways.filter(g => g.gateway_type === 'exclusiveGateway').flatMap(g => { const outs = p.flows.filter(f => f.source === g.id); if (outs.length < 2) return [];
      return outs.map((f, i) => `<tr>${i ? '' : `<td rowspan="${outs.length}"><b>${h(UI.flowName(g.name || '(이름 없는 갈림)'))}</b></td>`}<td>${h(branchWords(m.flows[f.id] || {}) || UI.flowSeq(f.name) || f.name || '조건 없음')}</td><td>${h(UI.flowName(nodeName(f.target)))}</td></tr>`); }).join('');
    const kv = [['흐름 이름', h(m.name || p.process.name || '')], ['시작', start.kind === 'alert' ? `경보로 시작 — ${(start.patterns || []).map(x => h(UI.patternName(x))).join(' · ') || '경보 종류 없음'}` : start.kind === 'human' ? `사람 입력으로 시작${(start.fields || []).length ? ` — ${start.fields.map(f => h(f.text || f.key)).join(' · ')}` : ''}` : '–'],
      ...p.lanes.filter(l => m.lanes[l.id]).map(l => [`칸 「${h(l.name || '이름 없음')}」`, h(m.lanes[l.id])])];
    return `<section aria-label="단계 설정" class="flow-editor flow-readonly"><dl class="kv">${kv.map(([k, x]) => `<dt>${k}</dt><dd>${x}</dd>`).join('')}</dl>
      <div class="table-container"><table class="table"><thead><tr><th>단계</th><th>종류</th><th>누가</th><th>기한</th></tr></thead><tbody>${steps}</tbody></table></div>
      ${branches ? `<div class="table-container"><table class="table"><thead><tr><th>갈림</th><th>조건</th><th>가는 곳</th></tr></thead><tbody>${branches}</tbody></table></div>` : ''}
      <p class="muted">기본 제공 흐름은 읽기만 합니다. 고쳐 쓰려면 그림을 받아 bpmn.io에서 고친 뒤 다른 흐름 구분 이름으로 가져옵니다.</p></section>`;
  }
  function renderEditor() {
    const v = S.view, p = v.parsed, m = S.mapping, box = $('flowEditor');
    $('flowEditorSum').textContent = `단계 ${p.tasks.length} · 갈림 ${p.gateways.length}${v.class_flow ? '' : v.check && v.check.ok ? ' · 검사 통과' : ` · 고칠 곳 ${((v.check || {}).problems || []).length}`}`;
    if (v.class_flow) { box.innerHTML = readOnlyEditor(v, p, m); drawRegister(); drawHead(); drawSteps(); return; }
    const start = m.start || {};
    const patterns = S.cat.patterns.map(pt => `<label class="pane-opt"><input type="checkbox" class="input" data-pattern="${h(pt)}" ${(start.patterns || []).includes(pt) ? 'checked' : ''}>${h(UI.patternName(pt))}</label>`).join('');
    const lanes = p.lanes.map(l => UI.field({ label: l.name || '(이름 없는 칸)', input: `<select data-lane="${h(l.id)}"><option value="">(고르지 않음)</option>${roleOpts(m.lanes[l.id] || '', false)}</select>` })).join('');
    box.innerHTML = `<section aria-label="단계 설정" class="flow-editor">
        <div data-editable-note></div>
        ${UI.section('흐름', UI.field({ label: '흐름 이름', input: `<input id="flowName" value="${h(m.name || p.process.name || '')}">` }))}
        ${UI.section('시작 조건', `
          <div class="flow-start"><label class="pane-opt"><input type="radio" class="input" name="flowStart" value="alert" ${start.kind === 'alert' ? 'checked' : ''}>경보로 시작</label>
            <div class="flow-opts">${patterns}</div><p class="muted">회복 기준은 기준 흐름의 것을 그대로 씁니다.</p></div>
          <div class="flow-start"><label class="pane-opt"><input type="radio" class="input" name="flowStart" value="human" ${start.kind === 'human' ? 'checked' : ''}>사람 입력 · 직접 시작</label>
            <div id="flowStartFields" data-rows-of="start"></div>
            <p class="muted">칸마다 값 이름(영문) · 화면 이름 · 종류를 고릅니다. 고르기 칸의 고를 값은 쉼표로 나눕니다.</p></div>`, 'flow-one')}
        ${lanes ? UI.section('그림의 칸(레인)마다 맡는 역할', lanes) : ''}
        <fieldset class="fieldset"><legend>단계별 종류와 담당, 설정</legend><div class="flow-tasks">${p.tasks.map(taskRow).join('')}</div></fieldset>
        ${p.boundaries.length ? UI.section('알림 기한', p.boundaries.map(timerRow).join('')) : ''}
        ${branchSection()}
      </section>`;
    fieldEditors(box);
    // 잠금은 칸 줄 편집기(fieldEditors)가 줄 · 단추를 그린 뒤에 건다 — 전에는 그 앞이라 시작 입력 · 출력 칸 줄이 잠기지 않았다(한바퀴3)
    const controls = 'section input, section select, section textarea, section button[data-add], section button[data-del]';
    const editable = hydCourseAccess.handoverEditable;   // 수업 단계의 제공 교대 흐름: 서버가 정한 칸만 연다(W3-08) — PBL 이면 null
    if (!v.class_flow && editable && v.definition_id === hydCourseAccess.access?.importable_flow) {
      const agentOk = new Set(editable.agent_tasks || []);
      // 칸 줄 더하기 · 빼기(data-add · data-del)도 잠근다 — 단추가 열려 있으면 학생이 시작 입력 줄을 더했다가 등록에서야 거절됐다(한바퀴3)
      box.querySelectorAll(controls).forEach(n => {
        const open = (n.id === 'flowName' && editable.flow_name) || (n.matches('[data-agent]') && agentOk.has(n.dataset.agent));
        if (!open) { n.disabled = true; n.title = '지금 단계에서는 흐름 이름과 초안 단계의 AI 에이전트만 바꿉니다'; }
      });
      box.querySelector('[data-editable-note]').innerHTML = infoBox('지금은 흐름 이름과 초안 단계의 AI 에이전트만 바꿀 수 있습니다', `초안 단계 ${agentOk.size}곳의 AI 에이전트와 흐름 이름을 바꿉니다. 나머지 칸은 제공한 그대로 읽기만 합니다.`);
    }
    drawRegister();
    drawHead(); drawSteps();
  }
  // 검사 · 판본 등록 절: 검사 결과(통과 또는 고칠 곳) → 알림 한 줄 → 단추. 기본 제공 흐름에는 이 절이 없다
  function drawRegister() {
    const v = S.view, sec = $('flowRegisterSec');
    sec.hidden = !!v.class_flow;
    if (v.class_flow) return;
    $('flowNextVersion').textContent = `다음 판본 ${v.next_version}`;
    $('flowProblems').innerHTML = resultBlock(v.check);
    $('flowActions').innerHTML = actionsHtml();
    markPrimary();
  }

  /* 칸 목록 편집(값 이름 · 화면 이름 · 종류 · 고를 값 한 행씩) — 매핑의 칸 배열을 그대로 들고(el._rows) collect 가 그것을 읽는다.
     화면 이름에 「|」 · 「,」가 들어가도 깨지지 않는다(W3-16). process-gpt-vue3 FormDefinition.vue 의 칸 목록 편집과 같은 모양. */
  function fieldEditors(box) {
    box.querySelectorAll('[data-rows-of]').forEach(ed => {
      if (ed._rows) return;
      const of = ed.dataset.rowsOf, task = S.mapping.tasks[ed.dataset.fields || ed.dataset.outputs] || {};
      const source = of === 'start' ? (S.mapping.start || {}).fields : of === 'fields' ? task.fields : task.outputs;
      const rows = ed._rows = structuredClone(source || []);
      ed.classList.add('flow-rows');
      const sync = () => ed.dispatchEvent(new Event('change', { bubbles: true }));   // wire 의 change → collect → 검사
      const draw = () => {
        ed.innerHTML = (rows.length ? `<div class="flow-row-line flow-row-head"><span>값 이름</span><span>화면 이름</span><span>종류</span><span>고를 값</span><span></span></div>` : '')
          + rows.map((r, i) => `<div class="flow-row-line" data-i="${i}"><input class="input" data-k="key" value="${h(r.key)}" placeholder="예) oil_iso" aria-label="값 이름">
            <input class="input" data-k="text" value="${h(r.text && r.text !== r.key ? r.text : '')}" placeholder="예) ISO 청정도" aria-label="화면 이름">
            <select class="select" data-k="type" aria-label="종류">${TYPES.map(t => `<option value="${t}" ${t === (r.type || 'text') ? 'selected' : ''}>${h(TYPE_LABEL[t] || t)}</option>`).join('')}</select>
            <input class="input" data-k="items" value="${h((r.items || []).join(', '))}" placeholder="${r.type === 'select' ? '쉼표로 구분' : '고르기일 때만'}" ${r.type === 'select' ? '' : 'disabled'} aria-label="고를 값">
            <button type="button" class="btn" data-variant="ghost" data-size="icon-sm" data-del aria-label="칸 빼기" data-tooltip="칸 빼기">${icon('x')}</button></div>`).join('')
          + `<button type="button" class="btn" data-variant="ghost" data-size="sm" data-add>${icon('plus')}칸 추가</button>`;
      };
      ed.addEventListener('input', e => {
        const row = e.target.closest('[data-i]'); if (!row) return;
        const r = rows[+row.dataset.i], k = e.target.dataset.k;
        if (k === 'items') r.items = e.target.value.split(',').map(x => x.trim()).filter(Boolean);
        else if (k === 'text') r.text = e.target.value; else if (k === 'key') r.key = e.target.value.trim();
      });
      ed.addEventListener('change', e => { if (e.target.dataset.k === 'type') { rows[+e.target.closest('[data-i]').dataset.i].type = e.target.value; draw(); } });
      ed.addEventListener('click', e => {
        if (e.target.closest('[data-add]')) { rows.push({ key: '', text: '', type: 'text' }); draw(); ed.querySelector('.flow-row-line:last-of-type input')?.focus(); }
        const del = e.target.closest('[data-del]'); if (del) { rows.splice(+del.closest('[data-i]').dataset.i, 1); sync(); draw(); }
      });
      draw();
    });
  }

  // 단계 한 칸: 그림의 단계 이름 → 단계 종류 · 담당(두 칸) → 그 종류의 설정
  function taskRow(t) {
    const m = S.mapping.tasks[t.id] || {};
    const part = S.cat.parts.find(x => x.key === m.part);
    const fixed = S.cat.parts.filter(x => x.group === 'scenario' && !(x.effect === '작업지시'));
    const wo = S.cat.parts.find(x => x.effect === '작업지시');
    const opt = x => `<option value="${h(x.key)}" ${x.key === m.part ? 'selected' : ''}>${h(partName(x))}</option>`;
    // 정해진 단계: 설비 이상 조치 · 교대 인수인계 흐름이 쓰는, 받는 값과 내는 값이 정해진 단계. 일반 단계: 무엇을 받고 낼지 여기서 정하는 단계
    const sel = `<select data-part="${h(t.id)}" aria-label="단계 종류"><option value="">단계 종류 선택</option><optgroup label="정해진 단계 (설비 이상 조치 · 교대 인수인계)">${fixed.map(opt).join('')}</optgroup>
      <optgroup label="일반 단계">${S.cat.parts.filter(x => x.group === 'general').map(opt).join('')}${wo ? `<option value="${h(wo.key)}" ${wo.key === m.part ? 'selected' : ''}>정비 요청</option>` : ''}</optgroup></select>`;
    let who = '<span class="muted">단계 종류를 고르면 정해집니다</span>', detail = '';
    if (part && part.kind === 'human') who = `<select class="select" data-role="${h(t.id)}" aria-label="담당 역할"><option value="">${part.group === 'scenario' ? '기본 역할: ' + h(part.role) : '(칸의 역할)'}</option>${roleOpts(m.role || '', true)}</select>`;
    // 사람이 고르지 않은 AI 에이전트가 저장 · 등록되지 않게: 매핑 값이나 단계 종류의 기본값이 있을 때만 미리 고르고, 없으면 빈 항목으로 둔다(등록 전에 doRegister 가 검사한다)
    if (part && part.kind === 'agent') who = `<select class="select" data-agent="${h(t.id)}" data-step="${h(t.name || '(이름 없음)')}" aria-label="AI 에이전트"><option value="">AI 에이전트 선택</option>${agentOpts(m.agent || part.agent || '')}</select>`;
    if (part && part.kind === 'service') who = '<span class="flow-who">시스템</span>';
    const codes = list => list.map(x => `<code class="inline">${h(x)}</code>`).join(' ') || '–';
    if (part && part.group === 'scenario') {
      const outs = (part.form && part.form.fields_json || []).map(f => f.key);
      detail = `<details class="fold flow-contract"><summary>연결 값 보기</summary><div class="fold-body"><dl class="kv"><dt>받는 값</dt><dd>${codes(part.inputs)}</dd><dt>내는 값</dt><dd>${codes(outs.length ? outs : part.outputs)}</dd>` +
        `${part.approval ? '<dt>승인</dt><dd>사람 승인이 있어야 다음으로 갑니다</dd>' : ''}${part.effect ? `<dt>실행</dt><dd>${h(UI.flowName(part.effect))} (승인 뒤)</dd>` : ''}</dl></div></details>`;
    } else if (part && part.key === 'human') {
      detail = `<div class="flow-sub"><p class="flow-sub-h">담당자가 적을 칸</p><div data-fields="${h(t.id)}" data-rows-of="fields"></div></div>${inputsField(t, m)}`;
    } else if (part && part.key === 'human:approve') {     // 캡스톤 G1: 고를 안이 든 값 · 구분 칸 · 추천 · 지는 안 · 근거 자료 (part.config 가 칸 설명)
      const cfg = m.config || {};
      detail = `<div class="flow-fields">${Object.entries(part.config).map(([k, hint]) => UI.field({ label: hint, input: `<input data-approval="${h(t.id)}" data-cfg="${h(k)}" value="${h(cfg[k] || '')}" aria-label="${h(hint)}">` })).join('')}</div>`
        + `<dl class="kv"><dt>받을 수 있는 값</dt><dd>${codes(avail(t.id))}</dd><dt>내는 값</dt><dd>${codes(['approval', 'approval_reason'])} · 사람 승인</dd></dl>`;
    } else if (part && part.key === 'agent') {
      detail = UI.field({ label: '지시문', input: `<textarea data-instruction="${h(t.id)}" rows="2" aria-label="지시문">${h(m.instruction || '')}</textarea>`, hint: '무엇을 조회하고 계산해 무엇을 낼지 적습니다.' })
        + `<div class="flow-sub"><p class="flow-sub-h">결과 값</p><div data-outputs="${h(t.id)}" data-rows-of="outputs"></div></div>${inputsField(t, m)}`;
    }
    if (part?.key === 'task:decide') detail += UI.field({ label: 'AI 에이전트 지시문', input: `<textarea data-instruction="${h(t.id)}" rows="3">${h(m.instruction ?? part.contract?.instruction ?? '')}</textarea>` });
    if (part?.config && part.kind === 'service') detail += serviceFields(t, part, m.config || {});
    const lane = (S.view.parsed.lanes.find(l => l.id === t.lane) || {}).name;
    const dependency = ((S.view.check.dependencies || {}).items || []).find(x => x.node_id === t.id);
    if (dependency) detail += dependencyLine(dependency);
    return `<div class="flow-task" data-row="${h(t.id)}"><div class="flow-task-head"><b>${h(t.name || '(이름 없음)')}</b><span class="muted">${h(t.type_label)}${lane ? ' · ' + h(lane) : ''}</span></div>` +
      `<div class="flow-task-pick">${UI.field({ label: '단계 종류', input: sel })}<div role="group" class="field"><label>담당</label>${who}</div></div>${detail ? `<div class="flow-task-detail">${detail}</div>` : ''}</div>`;
  }
  const avail = id => [...new Set(((S.view.check.available || {})[id] || []).map(x => x.value))];
  // 「받을 값」 칸: 이름표를 칸 위에 둔다(자리표시 글만 있으면 값을 넣는 순간 무슨 칸인지 사라진다)
  const inputsField = (t, m) => UI.field({ label: '받을 값', input: `<input data-inputs="${h(t.id)}" value="${h((m.inputs || []).join(', '))}" aria-label="받을 값">`,
    hint: `쉼표로 나눕니다. 고를 수 있는 값: ${avail(t.id).join(', ') || '없음'}` });
  function serviceFields(task, part, config) {
    return `<div class="flow-fields">${Object.keys(part.config).map(key => {
      const [label, type] = CONFIG[key] || [key, 'text'], value = config[key];
      if (key === 'mail' && !config.mail?.arguments && !config.mail?.server && !config.mail?.tool) return `<fieldset class="fieldset flow-mail"><legend>공지 메일</legend><div role="group">${[['to','받는 사람'],['cc','참조'],['subject','메일 제목'],['body','메일 내용']].map(([k,label]) => UI.field({label,input: k === 'body' ? `<textarea data-mail="${h(task.id)}" data-mail-key="${k}" rows="3">${h(config.mail?.[k] ?? '')}</textarea>` : `<input data-mail="${h(task.id)}" data-mail-key="${k}" value="${h(config.mail?.[k] ?? '')}">`})).join('')}</div></fieldset>`;
      const attrs = `data-service="${h(task.id)}" data-cfg="${h(key)}" aria-label="${h(label)}"`;
      let input;
      if (['boolean', 'outcome', 'component'].includes(type)) {
        const choices = type === 'boolean' ? (key === 'effect' ? [['true', '변경 실행'], ['false', '조회만']] : [['true', '예'], ['false', '아니요']])
          : type === 'component' ? [['cooler', '쿨러'], ['pump', '펌프'], ['fan', '팬']]
          : S.cat.report_outcomes.map(x => [x, x]);                       // 서버가 준 목록(effect_parts.REPORT_OUTCOMES 한 곳)
        input = `<select ${attrs}><option value="">기본값 사용</option>${choices.map(([v, name]) => `<option value="${h(v)}" ${String(value) === v ? 'selected' : ''}>${h(name)}</option>`).join('')}</select>`;
      } else if (['object', 'array', 'textarea'].includes(type)) input = `<textarea ${attrs} rows="3" spellcheck="false">${h(value === undefined ? '' : type !== 'textarea' ? JSON.stringify(value, null, 2) : value)}</textarea>`;
      else input = `<input ${attrs} value="${h(value ?? '')}">`;
      return UI.field({ label, input, cls: ['object', 'array', 'textarea'].includes(type) ? 'flow-wide' : '', hint: type === 'object' ? '이름과 값을 중괄호로 묶어 입력합니다. 처리 건 값은 {값 이름}으로 연결합니다.' : ['duration', 'settle'].includes(key) ? '예: PT10M은 10분, PT2H는 2시간입니다.' : '' });
    }).join('')}</div>`;
  }
  // 값 이름 → 사람이 읽는 이름(부품 폼 · 내가 적은 폼 칸의 표시 이름). 없으면 값 이름 그대로.
  function valueLabel(key) {
    const known = { approval: '승인 결과', approval_reason: '반려 사유', recovered: '설비 회복 여부', passed: '확인 통과 여부', received: '입고 확인 여부' };
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
    return `<div data-row="${h(b.id)}">${UI.field({ label: `${b.name || '시간 초과'} — ${host ? host.name : ''}`, hint: '분',
      input: `<input type="number" min="0.1" step="any" data-timer="${h(b.id)}" value="${h(m ? minutesOf(m) : '')}" placeholder="${dflt ? '기본 ' + minutesOf(dflt) + '분' : '분'}">` })}</div>`;
  }

  // 고르기 값의 표시 이름(approve → 「인수자에게 전달」): 단계 종류의 폼 · 내가 적은 폼 칸에 적힌 고를 값에서 찾는다. 화면에 값 사전을 따로 두지 않는다
  function valueName(key, value) {
    if (value === true) return '예'; if (value === false) return '아니요';
    const fields = [...S.cat.parts.flatMap(p => (p.form && p.form.fields_json) || []), ...((S.mapping.start || {}).fields || []), ...Object.values(S.mapping.tasks || {}).flatMap(t => [...(t.fields || []), ...(t.outputs || [])])];
    for (const f of fields) if (f.key === key) for (const item of f.items || []) if (item && typeof item === 'object' && value in item) return String(item[value]);
    return '';
  }
  const OP_WORD = { '==': '일 때', '!=': '아닐 때', '>': '보다 클 때', '>=': '이상일 때', '<': '보다 작을 때', '<=': '이하일 때' };
  // 가지 하나를 사람 말로: 「인계자 검토가 「인수자에게 전달」일 때」. 조건을 아직 정하지 않았으면 빈 글
  function branchWords(c) {
    if (c.default) return '그 밖의 경우';
    if (!c.var || c.value === undefined || c.value === '') return '';
    const what = valueLabel(c.var) || c.var, shown = valueName(c.var, c.value) || (c.value === true ? '예' : c.value === false ? '아니요' : String(c.value));
    return `${what}${window.hydWords.josa(what, '이/가')} 「${shown}」${OP_WORD[c.op || '=='] || ''}`;
  }
  function branchSection() {
    const p = S.view.parsed;
    const names = p.gateways.map(g => g.name || '');
    const rows = p.gateways.filter(g => g.gateway_type === 'exclusiveGateway').map(g => {
      const outs = p.flows.filter(f => f.source === g.id);
      if (outs.length < 2) return '';
      const vals = avail(g.id);
      // 이름이 같은 갈림이 여럿이면(「검토 결정」 여섯) 어느 단계 뒤의 갈림인지로 구별한다
      const after = p.flows.filter(f => f.target === g.id).map(f => nodeName(f.source)).join(' · ');
      const title = `${g.name || '(이름 없는 갈림)'}${after && (names.filter(n => n === (g.name || '')).length > 1 || !g.name) ? ` — 「${after}」 뒤` : ''}`;
      return `<div class="flow-branch" data-row="${h(g.id)}"><p class="flow-sub-h">갈림 「${h(title)}」</p>${outs.map(f => {
        const c = S.mapping.flows[f.id] || {}, words = branchWords(c);
        // 그림의 선 이름이 식 원문(sender_decision == 'approve')이면 사람 말을 앞에 두고 원문은 보조 글씨로
        const raw = f.name && /[=<>!'"]/.test(f.name) ? f.name : '', label = f.name && !raw ? f.name : '';
        const choices = [...new Set(S.cat.parts.flatMap(x => (x.form && x.form.fields_json) || []).filter(x => x.key === c.var).flatMap(x => (x.items || []).filter(i => i && typeof i === 'object').map(i => Object.keys(i)[0])))];
        const value = c.var === 'approval' ? `<select class="select" data-value="${h(f.id)}" aria-label="승인 결과" ${c.default ? 'disabled' : ''}><option value="">결과 선택</option>${['승인', '반려'].map(x => `<option ${c.value === x ? 'selected' : ''}>${x}</option>`).join('')}</select>`
          : choices.length ? `<select class="select" data-value="${h(f.id)}" aria-label="비교할 값" ${c.default ? 'disabled' : ''}><option value="">값 선택</option>${choices.map(x => `<option value="${h(x)}" ${c.value === x ? 'selected' : ''}>${h(valueName(c.var, x) || x)}</option>`).join('')}${c.value !== undefined && c.value !== '' && !choices.includes(c.value) ? `<option value="${h(c.value)}" selected>${h(c.value)}</option>` : ''}</select>`
          : `<input class="input" data-value="${h(f.id)}" aria-label="비교할 값" value="${h(c.value === undefined ? '' : c.value === true ? '예' : c.value === false ? '아니요' : c.value)}" placeholder="기준 (예/아니요 · 숫자 · 글)" ${c.default ? 'disabled' : ''}>`;
        return `<div class="flow-branch-line" data-row="${h(f.id)}"><span class="flow-branch-to">${icon('corner-down-right', 'ic-sm')}<span><b>${h(nodeName(f.target))}</b>${words || label ? `<small>${h(words || label)}</small>` : '<small class="muted">조건을 아직 정하지 않았습니다</small>'}${raw ? `<small class="muted mono">그림의 선 이름 ${h(raw)}</small>` : ''}</span></span>
          <label class="pane-opt"><input type="checkbox" class="input" data-default="${h(f.id)}" ${c.default ? 'checked' : ''}>그 밖의 경우</label>
          <select class="select" data-var="${h(f.id)}" aria-label="분기할 값" ${c.default ? 'disabled' : ''}><option value="">값 선택</option>${vals.map(x => `<option value="${h(x)}" ${x === c.var ? 'selected' : ''}>${h(valueLabel(x) || x)}</option>`).join('')}</select>
          <select class="select" data-op="${h(f.id)}" aria-label="비교 방법" ${c.default ? 'disabled' : ''}>${S.cat.ops.map(o => `<option value="${h(o)}" ${o === (c.op || '==') ? 'selected' : ''}>${h(({ '==': '같음', '!=': '다름', '>': '초과', '>=': '이상', '<': '미만', '<=': '이하' })[o] || o)}</option>`).join('')}</select>
          ${value}</div>`;
      }).join('')}</div>`;
    }).join('');
    return rows ? `<fieldset class="fieldset"><legend>갈림마다 어느 가지로 갈지 (앞 단계 값 기준)</legend><div class="flow-branches">${rows}</div></fieldset>` : '';
  }

  // 고칠 곳: 무엇(어느 단계 · 갈림)이 왜 안 되는지 한 줄씩. 줄을 누르면 그 칸으로 간다
  function problemsBlock(problems, title, linked = true) {
    if (!problems || !problems.length) return '';
    return `<div class="alert" data-variant="destructive" role="alert">${icon('circle-alert')}<h2>${h(title || '고칠 곳')} ${problems.length}건</h2><section><ul class="flow-issues">${problems.map(x => {
      const w = x.where || {};
      const text = `${w.kind_label ? `<b>${h(w.kind_label)} ${h(w.name || w.id)}</b> — ` : ''}${h(x.reason)}`;
      return w.id && linked ? `<li><button type="button" class="btn" data-variant="link" data-goto="${h(w.id)}">${text}</button></li>` : `<li>${text}</li>`;
    }).join('')}</ul></section></div>`;
  }
  function dependencyLine(item) {
    return `<p class="muted flow-dependency" role="status">${icon('plug', 'ic-sm')}연결 도구 준비 상태: ${h(item.reason)}</p>`;
  }
  function dependenciesBlock(dependencies) {
    if (!dependencies || !dependencies.items || !dependencies.items.length) return '';
    const count = dependencies.attention_count || 0;
    return `<div class="alert" role="status">${icon(count ? 'triangle-alert' : 'plug')}<h2>${count ? `연결 도구 준비가 필요한 단계 ${count}개` : '연결 도구의 저장된 검사 확인'}</h2><section><ul class="flow-issues">${dependencies.items.map(item => `<li><b>${h(item.node_name)}</b> — ${h(item.reason)}</li>`).join('')}</ul><p class="muted">${h(dependencies.note)} 구조 검사 통과는 실제 연결을 보장하지 않습니다.</p></section></div>`;
  }
  const resultBlock = c => (c && c.ok ? okBox('구조 검사를 통과했습니다', '판본으로 등록할 수 있습니다. 외부 도구에 실제로 연결되는지는 이 검사로 알 수 없습니다.' + (S.mapping && S.mapping.start && S.mapping.start.kind === 'alert' ? ' 경보로 시작하는 흐름이라, 등록한 뒤 「판본 · 배포」에서 배포해야 경보에 쓰입니다.' : ''))
    : problemsBlock(c && c.problems)) + dependenciesBlock(c && c.dependencies);

  function collect() {
    const box = $('flowEditor'), m = structuredClone(S.mapping);
    const switched = new Set();
    m.name = box.querySelector('#flowName').value.trim();
    const kind = (box.querySelector('input[name=flowStart]:checked') || {}).value;
    m.start = kind === 'alert' ? { kind, patterns: [...box.querySelectorAll('[data-pattern]')].filter(c => c.checked).map(c => c.dataset.pattern) }
      : kind === 'human' ? { kind, fields: checkFields(box.querySelector('#flowStartFields')._rows) } : {};
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
    set('fields', (t, x) => { t.fields = checkFields(x._rows); });
    set('outputs', (t, x) => { t.outputs = checkFields(x._rows); });
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

  // 검사 · 판본 등록 절의 단추: 서버가 지금 등록할 수 없다고 하면(register.allowed=false — 수업 경계 · 기준 id) [판본 등록] 대신 그 까닭(W3-08).
  // 주 단추는 이 흐름이 지금 할 단계의 것 하나: 검사를 통과했으면 [판본 등록], 아직이면 [저장 · 검사]
  function actionsHtml() {
    const v = S.view || {}, reg = v.register || null;
    const check = `<button type="button" class="btn" data-variant="outline" id="flowCheck">저장 · 검사</button>`;
    if (reg && reg.allowed === false) return `<span class="muted" data-register-why>${h(reg.reason || '지금은 판본으로 등록할 수 없습니다')}</span>${check}`;
    return `${check}<button type="button" class="btn" data-variant="outline" id="flowRegister">${icon('upload')}판본 등록</button>`;
  }
  const sayMsg = html => { const m = $('flowMsg'); if (m) m.innerHTML = html; };
  function wire() {
    S.events?.abort(); S.events = new AbortController();
    const box = S.el, on = (type, fn) => box.addEventListener(type, fn, { signal: S.events.signal });
    const inEditor = e => !!e.target.closest('#flowEditor');
    on('input', e => { if (inEditor(e)) S.revision += 1; });
    on('change', e => {
      if (!inEditor(e)) return;
      S.revision += 1;
      try { collect(); } catch (err) { sayMsg(failBox('단계 설정에 고칠 곳이 있습니다', err.message)); return; }
      if (e.target.matches('[data-part],[data-default],[data-var],[data-op],[data-value],input[name=flowStart]')) renderEditor();
      clearTimeout(S.timer); S.timer = setTimeout(() => recheck(false), 300);
    });
    on('click', e => {
      const check = e.target.closest('#flowCheck'), reg = e.target.closest('#flowRegister'), go = e.target.closest('[data-goto]'), del = e.target.closest('[data-flow-delete]');
      if (check) once('check', check, () => recheck(true));
      else if (reg) once('register', reg, doRegister);
      else if (del) deleteFlow(del.dataset.flowDelete);
      else if (e.target.closest('[data-goto-deploy]')) $('definitionDeployPanel').scrollIntoView({ block: 'start', behavior: 'smooth' });
      else if (e.target.closest('[data-goto-start]')) $('flowsStart').scrollIntoView({ block: 'start', behavior: 'smooth' });
      else if (e.target.closest('[data-retry]') && e.target.closest('#flowEditor')) select(S.sel);
      else if (go) {      // 고칠 곳 한 줄 → 그 단계 · 갈림의 칸으로(접혀 있으면 펼친다)
        $('flowEditorFold').open = true;
        const row = $('flowEditor').querySelector(`[data-row="${CSS.escape(go.dataset.goto)}"]`);
        if (row) { row.scrollIntoView({ block: 'center' }); row.dataset.flash = '1'; setTimeout(() => { delete row.dataset.flash; }, 1500); }
        else sayMsg(infoBox('그 자리는 단계 설정에 칸이 없습니다', '그림 자체(시작 · 끝 · 선)를 고쳐야 하는 곳입니다. bpmn.io에서 그림을 고친 뒤 다시 가져오세요.'));
      }
    });
  }

  async function recheck(save) {
    if (!S.view) return;
    if (save) sayMsg(hydLive.waitHtml('단계 설정을 저장하고 검사하는 중', { hint: '단계마다 고른 종류 · 담당 · 넘길 값이 흐름으로 돌 수 있는지 서버가 검사하는 중입니다.' }));
    try {
      collect();
      const revision = S.revision, view = S.view;
      const id = encodeURIComponent(S.view.definition_id);
      const v = save ? await call('PUT', `/api/flows/${id}/mapping`, { mapping: S.mapping }) : await call('POST', `/api/flows/${id}/check`, { mapping: S.mapping });
      if (view !== S.view) return;                 // 그 사이 다른 흐름을 열었다 — 이 응답은 그 화면의 것이 아니다
      if (revision !== S.revision) {
        // 응답을 기다리는 동안 칸을 고쳤다: 저장은 끝났으니 그 사실을 알리고(「검사 중…」이 남지 않게), 지금 칸 값으로 다시 검사한다
        if (save) sayMsg(infoBox('단계 설정을 저장했습니다', '저장한 뒤에 고친 칸은 아직 저장되지 않았습니다. [저장 · 검사]를 다시 누르세요.'));
        clearTimeout(S.timer); S.timer = setTimeout(() => recheck(false), 300);
        return;
      }
      const changed = JSON.stringify(v.check.available) !== JSON.stringify(S.view.check.available);
      S.view = Object.assign(S.view, { check: v.check, next_version: v.next_version, versions: v.versions, register: v.register, class_flow: v.class_flow });
      if (changed) renderEditor();
      else { drawRegister(); $('flowEditorSum').textContent = `단계 ${S.view.parsed.tasks.length} · 갈림 ${S.view.parsed.gateways.length}${v.check.ok ? ' · 검사 통과' : ` · 고칠 곳 ${(v.check.problems || []).length}`}`; drawSteps(); }
      if (save) sayMsg(v.check.ok ? okBox('단계 설정을 저장했습니다', `${h(UI.dateTime(new Date().toISOString()))}에 저장했고 구조 검사를 통과했습니다. [판본 등록]으로 판본을 만듭니다.`) : infoBox('단계 설정을 저장했습니다', '위의 고칠 곳을 고치면 판본으로 등록할 수 있습니다.'));
      else if (!$('flowMsg').querySelector('.lv-wait')) sayMsg('');
    } catch (e) { sayMsg(failBox(save ? '단계 설정을 저장하지 못했습니다' : '단계 설정을 검사하지 못했습니다', e.message)); }
  }

  async function doRegister() {
    if (!meId()) { sayMsg(failBox('판본을 등록하지 못했습니다', NEED_ME)); return; }
    try {
      collect();
      const unpicked = [...$('flowEditor').querySelectorAll('select[data-agent]')].find(x => x.value === '');
      if (unpicked) { $('flowEditorFold').open = true; sayMsg(failBox('판본을 등록하지 못했습니다', `「${unpicked.dataset.step}」 단계를 맡을 AI 에이전트를 고르세요.`)); unpicked.focus(); return; }
      const defId = S.view.definition_id;
      const r = await call('POST', `/api/flows/${encodeURIComponent(defId)}/register`, { mapping: S.mapping, by: meId() });
      const registered = `${r.name} 판본 ${r.version}${window.hydWords.josa(String(r.version), '을/를')} 등록했습니다`;
      UI.toast(`${registered}. 운영 판본은 그대로입니다.`, { tone: 'ok' });
      // 다음 할 일: 등록만으로는 경보에 쓰이지 않는다 — 바로 아래 「판본 · 배포」가 새 판본을 보이고, 그리로 가는 길을 함께 보인다
      S.defCache.clear(); delete S.xml[defId]; delete S.starts[defId];      // 그림은 이제 등록한 판본의 것으로 그린다
      S.starts[defId] = S.mapping.start && S.mapping.start.kind === 'alert' ? 'alert' : 'direct';
      await recheck(false);
      await loadListOnly(); renderList(); drawHead(); drawSteps(); drawPicture();
      await window.hydDefinitionDeploy.reload(defId);
      drawStart();
      const item = itemOf(defId);
      sayMsg(okBox(registered, item && directStart(item)
        ? `직접 시작하는 흐름이라 배포는 필요 없습니다. 아래 「시작」에서 이 판본으로 처리 건을 엽니다. <button type="button" class="btn" data-variant="link" data-goto-start>시작으로 이동${icon('arrow-right')}</button>`
        : `경보로 시작하는 흐름입니다. 아래 「판본 · 배포」에서 이 판본을 배포해야 다음 경보부터 쓰입니다. <button type="button" class="btn" data-variant="link" data-goto-deploy>판본 · 배포로 이동${icon('arrow-right')}</button>`));
    } catch (e) {
      sayMsg(failBox('판본을 등록하지 못했습니다', e.message));
      if (e.problems) $('flowProblems').innerHTML = problemsBlock(e.problems);
    }
  }

  // ---------------------------------------------------------------- 지우기 · 시작 · 되돌리기
  async function deleteFlow(id) {
    const item = itemOf(id); if (!item) return;
    // 누가 지웠는지는 담당자 id 로 남긴다(서버 flows_api._who 가 사용자 표의 사람 user:* 만 받는다) — 자유 글 칸을 두지 않는다
    const by = meId();
    if (!by) { $('flowNote').innerHTML = `<div class="flow-note-box">${failBox('흐름을 지우지 못했습니다', NEED_ME)}</div>`; return; }
    if (S.deleting) return;
    if (!await UI.confirm({ title: `「${item.name}」 흐름을 지울까요?`, body: '이 흐름의 모든 판본과 단계 설정 초안을 지웁니다. 진행 중인 처리 건이 있거나 지금 배포된 흐름이면 지울 수 없고, 그 까닭을 알려 줍니다.', ok: '지우기', danger: true })) return;
    S.deleting = true;
    try {
      const result = await call('DELETE', '/api/flows/' + encodeURIComponent(id) + '?by=' + encodeURIComponent(by));
      delete S.xml[id]; S.sel = null; S.view = null; S.mapping = null;
      UI.toast(result.projection_pending ? `흐름을 지웠습니다. 그래프 기록 ${result.projection_pending}건은 정리를 다시 시도하고 있습니다.` : `「${item.name}」 흐름을 지웠습니다.`, { tone: result.projection_pending ? 'neutral' : 'ok' });
      await loadList(); window.hydDefinitionDeploy.reload();
    } catch (e) { const note = $('flowNote'); if (note) note.innerHTML = `<div class="flow-note-box">${failBox('흐름을 지우지 못했습니다', e.message)}</div>`; }
    finally { S.deleting = false; }
  }

  // 「시작」 절: 경보로 시작하는 흐름은 경보를 만드는 화면으로 잇고, 직접 시작하는 흐름은 시작 폼을 바로 보인다
  function drawStart() {
    const item = itemOf(S.sel), box = $('flowsStart');
    if (!item || !item.versions.length || S.importing) { box.hidden = true; S.startKey = ''; return; }
    box.hidden = false;
    const chosen = box.querySelector('[data-start-version]')?.value;
    const version = item.versions.includes(chosen) ? chosen : item.deployed || item.versions[item.versions.length - 1];
    const key = `${item.id}@${version}|${item.versions.join(',')}|${hydCourseAccess.startBlocked(item.id)}`;
    if (S.startKey === key) return;
    S.startKey = key;
    const pick = item.versions.length > 1 ? UI.field({ label: '시작할 판본', input: `<select data-start-version>${item.versions.map(v => `<option value="${h(v)}" ${v === version ? 'selected' : ''}>${h(v)}${v === item.deployed ? ' (운영)' : ''}</option>`).join('')}</select>` }) : '';
    box.innerHTML = `<h3>${icon('play', 'ic-sm')}시작<span class="muted">판본 ${h(version)}</span></h3>${pick}<div data-start-body>${UI.loading('')}</div>`;
    box.querySelector('[data-start-version]')?.addEventListener('change', () => drawStart());
    startBody(item, version, box.querySelector('[data-start-body]'));
  }
  async function startBody(item, version, slot) {
    const id = item.id;
    try {
      const d = await defOf(id, version);
      if (!slot.isConnected) return;
      if (d.alertPolicy) {
        slot.innerHTML = `<footer class="form-foot"><span class="muted" role="status">${item.deployed ? '경보가 나면 처리 건이 열립니다.' : '배포한 뒤 경보가 나면 처리 건이 열립니다.'}</span><button type="button" class="btn" data-variant="outline" data-go-tab="oil">오일 분석 입력${icon('arrow-right')}</button><button type="button" class="btn" data-variant="outline" data-go-tab="scenario">결함 시뮬레이션${icon('arrow-right')}</button></footer>`;
        return;
      }
      const fields = (d.startForm && d.startForm.fields_json) || [], blocked = hydCourseAccess.startBlocked(id);
      slot.innerHTML = (fields.length ? UI.section('시작할 때 넣을 값', fields.map(f => UI.field({ label: f.text || f.key, input: f.type === 'select'
        ? `<select data-sv="${h(f.key)}" data-choose="${h(f.text || f.key)}"><option value="">고르세요</option>${(f.items || []).map(i => `<option>${h(typeof i === 'string' ? i : Object.keys(i)[0])}</option>`).join('')}</select>`
        : f.type === 'boolean' ? `<select data-sv="${h(f.key)}" data-bool="1" data-choose="${h(f.text || f.key)}"><option value="">고르세요</option><option value="true">예</option><option value="false">아니요</option></select>`
        : f.type === 'textarea' ? `<textarea data-sv="${h(f.key)}" data-kind="textarea" rows="4"></textarea>`
        : `<input data-sv="${h(f.key)}" data-kind="${h(f.type)}" data-label="${h(f.text || f.key)}">` })).join('')) : '<p class="muted">넣을 값 없이 바로 시작합니다.</p>') +
        `<div data-start-msg aria-live="polite"></div><footer class="form-foot">${blocked ? `<span class="muted">${h(blocked)}</span>` : ''}<button type="button" class="btn" data-variant="outline" data-go="1"${blocked ? ' disabled' : ''}>${icon('play')}처리 건 시작</button></footer>`;
      markPrimary();
      // 시작 이벤트 id 는 폼을 열 때 한 번 만든다 — 두 번 누르거나 응답을 잃고 다시 눌러도 서버의 중복 실행 방지가 같은 처리 건으로 묶는다
      let eventId = `flow-${id}-${UI.uuid()}`;
      const go = slot.querySelector('[data-go]'), msg = slot.querySelector('[data-start-msg]');
      go.addEventListener('click', () => once('start:' + id + '@' + version, go, async () => {
        const variables = {};
        try {
          slot.querySelectorAll('[data-sv]').forEach(x => {
            const k = x.dataset.sv, kind = x.dataset.kind;
            if (x.dataset.choose && x.value === '') throw new Error(`${x.dataset.choose}: 값을 고르세요`);      // 고르지 않은 값(첫 항목 · 「예」)이 시작 값으로 들어가지 않게
            if (x.dataset.bool) variables[k] = x.value === 'true';
            else if (kind === 'number' || kind === 'integer') { if (x.value.trim() === '' || !isFinite(Number(x.value))) throw new Error(`${x.dataset.label}: 숫자를 넣으세요`); variables[k] = Number(x.value); }
            else if (kind === 'object') variables[k] = x.value.trim() ? window.hydDefinitions.readObject(x.value, x.dataset.label) : {};      // 틀린 자리를 한국어로(브라우저의 영문 SyntaxError 를 보이지 않는다)
            else if (kind === 'array') {
              let list; try { list = JSON.parse(x.value.trim() || '[]'); } catch (_) { throw new Error(`${x.dataset.label}: 목록의 문법을 확인하세요. 쉼표, 따옴표, 대괄호가 짝이 맞아야 합니다.`); }
              if (!Array.isArray(list)) throw new Error(`${x.dataset.label}: 대괄호로 묶은 목록을 넣으세요`);
              variables[k] = list;
            }
            else variables[k] = x.value;
          });
          const inst = await call('POST', '/api/instances/start', { definition_id: id, version, event_id: eventId, variables, name: d.processDefinitionName });
          eventId = `flow-${id}-${UI.uuid()}`;   // 시작됐으면 다음 누름은 새 처리 건
          msg.innerHTML = '';
          UI.toast('처리 건을 시작했습니다', { tone: 'ok' });
          if (window.hydShell) window.hydShell.navigate({ tab: 'instances', inst: inst.proc_inst_id });
        } catch (e) { msg.innerHTML = failBox('처리 건을 시작하지 못했습니다', e.message); }
      }));
    } catch (e) { if (slot.isConnected) slot.innerHTML = UI.errorBlock('시작 폼을 읽지 못했습니다', e.message); }
  }

  // ---------------------------------------------------------------- 올리기
  function mount(el) {
    S.el = el;
    $('flowImportOpen').addEventListener('click', openImport);
    $('flowReload').addEventListener('click', () => once('reload', null, async () => { S.defCache.clear(); await Promise.all([loadCatalog(), loadList()]); await window.hydDefinitionDeploy.reload(); }));
    // 보기 탭: 흐름(목록 + 고른 흐름) · 경보별 운영 흐름
    $('flowViews').addEventListener('click', e => { const b = e.target.closest('[data-flow-view]'); if (!b) return;
      UI.markViewTab($('flowViews'), x => x === b);
      document.querySelectorAll('#view-flows [data-flow-pane]').forEach(p => { p.hidden = p.dataset.flowPane !== b.dataset.flowView; }); });
    $('flowKind').addEventListener('click', e => { const b = e.target.closest('[data-flow-kind]'); if (b) { S.kind = b.dataset.flowKind; renderList(); } });
    $('flowList').addEventListener('click', e => {
      const row = e.target.closest('[data-open]');
      if (row) select(row.dataset.open, true); else if (e.target.closest('[data-retry]')) loadList();
    });
    renderList(); drawDetail();
    return Promise.all([loadCatalog(), loadList()]);
  }

  // 다시 열 때(셸 show): 카탈로그(에이전트 · 역할 · 부품)와 목록을 새로 읽는다. 한 번 읽고 굳으면 「에이전트 · 스킬」 화면에서 새로 만든 에이전트가
  // 단계의 에이전트 고르기에 없었다(한바퀴3 17 — 실라버스 118행에서 만든 인수인계 에이전트를 119행에서 고를 수 없음). 펼친 단계 설정은 지금 칸 값을
  // 담아(collect) 다시 그린다.
  async function show() {
    const before = JSON.stringify((S.cat && S.cat.agents) || []);
    await Promise.all([loadCatalog(), loadList()]);
    if (!S.importing && S.view && S.mapping && $('flowEditor') && JSON.stringify(S.cat.agents) !== before) { collect(); renderEditor(); }
  }

  // 관리 › 내 설정에서 되돌렸으면(이 화면이 그려져 있을 때) 고른 흐름 · 초안을 비우고 목록과 배포를 새로 읽는다
  window.addEventListener('hyd-config-reset', async e => {
    if (!S.el || !['all', 'flows', 'deploy'].includes(e.detail.scope)) return;
    if (e.detail.scope !== 'deploy') { S.xml = {}; S.defCache.clear(); S.sel = null; S.view = null; S.mapping = null; S.importing = false; }
    await loadList(); window.hydDefinitionDeploy.reload();
  });
  // pick(흐름 id): 다른 화면이 이 화면을 그 흐름을 고른 채 열 때 부른다(화면을 여는 것은 셸 — 열릴 때 목록을 읽고 고른다)
  window.hydFlows = { mount, show, pick: id => { S.wanted = id; } };
})();
