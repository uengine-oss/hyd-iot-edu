/* A161 처리 기록 — 처리 건 한 건을 "무슨 일이 어떤 순서로 왜 일어났나" 이야기로 보인다. 블랙박스 없이: 시작(신호 · 값 · 시각) →
   AI 일꾼(받은 일 · 스킬 · 가져온 데이터 · 지식 경로 + 출처 절 · 도구 호출마다 물음 → 받음 · 비교한 대안과 진 이유 · 추천) →
   사람 승인(누가 · 언제 · 무엇을) → 시스템 처리(무엇을 어느 시스템에 · 결과) → 확인(값 vs 기준) → 결과 보고. 끝에 "기록에 없는 것".
   시나리오 이름 · task id 를 코드에 두지 않는다. 단계 종류는 작업 행의 주체(에이전트 · 사람 · 시스템)와 tool 로만 가른다.

   데이터(모두 이미 있는 읽기 API):
     GET /api/instances/{id}   처리 건 · 정의 · 작업 행 · 이벤트(도구 호출 · 에이전트 말 · 시스템 기록) · 승인 기록
     GET /api/decisions/{id}   판단: 대안(점수 · 점수 항목 · 제외 규칙 · 득실 경로 · SOP 절 · 매뉴얼 출처) · 가져온 데이터(provenance) · 승인 이력
     GET /api/incidents/{id}   사건: 설비 명령 번호 · 설비 응답 · 재관측 기준과 잰 값
     GET /api/agents           AI 일꾼 설정(목표 · 스킬 · 붙인 도구 서버)
   실시간: liveStream.js 버스(hydStream.subscribe)의 SSE 이벤트를 받아 같은 그리기 함수로 채운다. 2초 다시 읽기는 instances.js 가 넘긴다.

   참고 화면(모방, 로고 없음):
   - process-gpt-vue3 (/Users/uengine/process-gpt/services/frontend)
     src/components/ui/EventTimeline.vue:1-120,1306-1420 — 세로 목록의 작업 카드: 머리(아바타 · 제목 · 설명 · 오른쪽 상태 점 배지) · 메타 줄 · 결과 칸, 사람 질문 칸
     src/ds/components/PgToolSteps.vue · PgToolStep.vue — 왼쪽 1px 세로선 위 도구 한 줄(아이콘 16 · 글 15/24 · 실행 중 회전 13)
     src/components/apps/todolist/InstanceOutput.vue — 처리 건 결과물을 카드로(제목 + 읽기 전용 값)
   - Dify 실행 추적 web/app/components/workflow/run/tracing-panel.tsx · node.tsx — 노드 행 = 색 블록 아이콘 · 이름 · 오른쪽 걸린 시간 · 상태,
     누르면 입력 · 출력 펼침; status.tsx — 맨 위 상태 · 걸린 시간 · 단계 수 요약 (github.com/langgenius/dify)
   - n8n 실행 화면 https://docs.n8n.io/workflows/executions/ — 실행 한 건의 노드 순서 · 노드마다 성공 표시 · 들어간 값 / 나온 값(표 ↔ 원문 JSON 전환) */
(function () {
  const W = () => window.hydWords;
  const TR = () => window.hydTrace;
  const e = s => esc(s);
  const ts = x => { const t = x ? Date.parse(x) : NaN; return Number.isFinite(t) ? t : null; };
  const fmtMs = ms => TR() ? TR().fmtMs(ms) : `${Math.round(ms / 1000)} s`;
  const hhmmss = t => { const d = new Date(t); return Number.isNaN(d.getTime()) ? '' : d.toLocaleTimeString('en-GB', { hour12: false }); };
  const icon = (k, cls) => TR() ? TR().icon(k, cls) : '';
  const vars = inst => Object.fromEntries(((inst && inst.variables_data) || []).map(r => [r.key, r.value]));
  const nm = id => W().idName(id);
  const named = (name, id) => `${e(name)}${W().id(id)}`;
  const isAgent = w => !!(w.agent_orch || w.agent_mode) && (w.agent_orch === 'cliagents' || !!w.agent_mode);
  const isHuman = w => !w.agent_orch && !w.agent_mode;
  const CHECK = /^(incident:reobserve|plant:test-run|enterprise:GR_CONFIRM)$/;
  const PLANT = /^(plant:|incident:(command|reobserve)$)/;          // 설비에 닿는 단계(설비 명령 · 재관측 · 정비 모사 · 시운전)
  const CASE_LEVEL = new Set(['SCENARIO_BUTTON', 'CASE_LINK_FAILED']);   // 단계(todo)가 아니라 처리 건에 붙는 기록 — 시작 단계에 보인다
  const LANE = { person: '사람', agent: 'AI 일꾼', system: '시스템' };
  const firstSentence = t => { const s = UI.clean(W().text(String(t || ''))).replace(/`[^`]*`에?/g, '').replace(/\*\*/g, '').trim(); const m = s.match(/^[^\n]*?[.。](?=\s|$)/); return (m ? m[0] : s.split('\n')[0]).slice(0, SENTENCE_MAX_CHARS); };
  const isoDur = s => { const m = /^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$/.exec(String(s || '')); if (!m) return s || ''; return [m[1] && `${m[1]}일`, m[2] && `${m[2]}시간`, m[3] && `${m[3]}분`, m[4] && `${m[4]}초`].filter(Boolean).join(' '); };
  const virtual = plan => plan && plan.virtual_s != null ? `가상 ${fmtMs(plan.virtual_s * 1000)} = 실제 ${fmtMs((plan.real_s || 0) * 1000)}` : plan && plan.real_s != null ? `실제 ${fmtMs(plan.real_s * 1000)}${plan.virtual ? ` (가상 ${isoDur(plan.virtual)})` : ''}` : '';
  const chip = (label, tone = 'neutral', title = '') => ({ label, tone, title });
  // 화면 한도 · 다시 읽기 주기 (글자 수 · 줄 수 · ms)
  const SENTENCE_MAX_CHARS = 220, NOTE_MAX_CHARS = 600, RAW_MAX_CHARS = 12000;
  const EVENTS_WINDOW = 1500;          // 처리 건 화면이 싣는 최신 기록 줄 수 = procsvc/instances.py EVENTS_WINDOW (서버가 events_page 를 안 줄 때만 씀)
  const OLDER_PAGE_ROWS = 500, LIVE_MAX_ROWS = 3000;
  const EXT_REFRESH_MS = 4000, SHARED_TTL_MS = 60000;
  // 처리 건과 상관없이 같은 목록: AI 일꾼 설정(목표 · 스킬 · 도구) · 사람 이름(승인한 사람 id → 이름)
  const SHARED_LISTS = { agents: '/api/agents', people: '/api/inbox/users' };
  // 판단 · 사건 · AI 일꾼 설정 읽기 상태: 'none'(번호 없음) · 'loading' · 'error' · 'ok' — 읽는 중을 실패로 보이지 않는다
  const extState = (x, id) => !id ? 'none' : x === undefined ? 'loading' : x && x.error ? 'error' : 'ok';

  /* ================================================================ 이벤트 → 도구 호출 · 말 · 시스템 기록 행 */
  function rowsOf(evs) {
    const rows = [], byTool = new Map();
    for (const ev of evs) {
      const d = ev.data || {};
      if (ev.event_type === 'tool_usage_started') {
        const r = { key: 't:' + (d.tool_use_id || ev.id), kind: 'tool', t0: ev.timestamp, tool: d.tool, input: d.input, status: 'running', minor: W().minorTool(d.tool) };
        byTool.set(d.tool_use_id, r); rows.push(r);
      } else if (ev.event_type === 'tool_usage_finished') {
        let r = byTool.get(d.tool_use_id);
        if (!r) { r = { key: 't:' + (d.tool_use_id || ev.id), kind: 'tool', t0: ev.timestamp, tool: d.tool, minor: W().minorTool(d.tool) }; rows.push(r); }
        const o = UI.outcome(d.output, d.is_error);
        Object.assign(r, { t1: ev.timestamp, output: d.output, status: o.tone === 'ok' ? 'ok' : o.tone, badge: o.label, full: d.full_output || null });
      } else if (ev.event_type === 'task_working' && d.type === 'text' && d.content) {
        rows.push({ key: 'n:' + ev.id, kind: 'note', t0: ev.timestamp, text: UI.clean(W().text(d.content)) });
      } else if (ev.event_type === 'task_working' && d.type === 'skill_used') {
        // A161-G1: 에이전트가 스킬 파일을 연 순간 (어떤 도구로)
        rows.push({ key: 'k:' + ev.id, kind: 'skill', t0: ev.timestamp, data: d });
      } else if (ev.event_type === 'task_working' && d.type === 'skills_provided') {
        rows.push({ key: 'kp:' + ev.id, kind: 'note', t0: ev.timestamp, minor: true, text: UI.clean(d.content || '') });
      } else if (ev.event_type === 'task_working' && d.type === 'file_artifact') {
        rows.push({ key: 'f:' + ev.id, kind: 'file', t0: ev.timestamp, minor: true, text: UI.baseName(d.path || '') });
      } else if (ev.event_type === 'task_working' && (d.type === 'notice' || d.type === 'evidence')) {
        rows.push({ key: 'n:' + ev.id, kind: 'note', t0: ev.timestamp, text: UI.clean(W().text(d.content || d.name || '')) });
      } else if (ev.event_type === 'task_working' && d.name && !d.type) {
        rows.push({ key: 's:' + ev.id, kind: 'sys', t0: ev.timestamp, job: ev.job_id, text: UI.clean(UI.logText(d.name)), data: d });
      } else if (ev.event_type === 'error') {
        rows.push({ key: 'e:' + ev.id, kind: 'error', t0: ev.timestamp, text: UI.clean(d.friendly || d.message || d.name || '오류'), data: d });
      } else if (ev.event_type === 'human_asked') {
        rows.push({ key: 'a:' + ev.id, kind: 'note', t0: ev.timestamp, text: '사람에게 물음: ' + UI.clean(d.text || d.question || '') });
      } else if (ev.event_type === 'human_response') {
        rows.push({ key: 'r:' + ev.id, kind: 'note', t0: ev.timestamp, text: `사람의 답: ${d.answer || ''}${d.by ? ' — ' + d.by : ''}` });
      }
    }
    return rows;
  }

  /* ================================================================ 모델 */
  function build(view, ext = {}, live = []) {
    const inst = view.instance, v = vars(inst), def = view.definition || {};
    const acts = Object.fromEntries((def.activities || []).map(a => [a.id, a]));
    const evDefs = Object.fromEntries((def.events || []).map(x => [x.id, x]));
    const all = new Map();
    (view.events || []).concat(live).forEach(x => { if (x && x.id && !all.has(x.id) && (!x.proc_inst_id || x.proc_inst_id === inst.proc_inst_id)) all.set(x.id, x); });
    const evs = [...all.values()].sort((a, b) => String(a.timestamp || '').localeCompare(String(b.timestamp || '')) || String(a.id).localeCompare(String(b.id)));
    const byTodo = new Map(); evs.forEach(x => { const k = x.todo_id || ''; if (!byTodo.has(k)) byTodo.set(k, []); byTodo.get(k).push(x); });
    const running = inst.status === 'RUNNING';
    const d = ext.decision && !ext.decision.error ? ext.decision : null;
    const inc = ext.incident && !ext.incident.error ? ext.incident : null;
    const agents = Object.fromEntries(((ext.agents) || []).map(a => [a.id, a]));
    const sources = inst.variable_sources || {};
    const producedBy = wid => Object.entries(sources).filter(([, s]) => s && s.kind === 'workitem' && s.id === wid).map(([k]) => k);
    W().caseNames = caseNames(v, d, ext.agents, ext.people);
    const read = {
      decision: { state: extState(ext.decision, v.decision_id), error: ext.decision && ext.decision.error },
      incident: { state: extState(ext.incident, v.incident), error: ext.incident && ext.incident.error },
      agents: { state: ext.agentsErr ? 'error' : ext.agents ? 'ok' : 'loading', error: ext.agentsErr },
      people: { state: ext.peopleErr ? 'error' : ext.people ? 'ok' : 'loading', error: ext.peopleErr },
    };
    const ctx = { inst, v, d, inc, agents, read, view, running, byTodo, acts, evDefs, gaps: [], producedBy, olderDone: !!ext.olderDone };
    const steps = [];
    steps.push(startStep(ctx));
    const neverRan = w => w.status === 'CANCELLED' && !byTodo.has(w.id) && /^cancelled:/i.test(String(w.log || '').trim());
    const wis = (view.workitems || []).filter(w => !(w.status === 'TODO' && !byTodo.has(w.id)) && !neverRan(w))
      .filter(w => !(evDefs[w.activity_id] && w.status === 'CANCELLED'))        // 울리지 않은 타이머(승인이 먼저 옴)는 일어난 일이 아니다
      .filter(w => !(evDefs[w.activity_id] && evDefs[w.activity_id].eventDefinition !== 'timer'))
      .sort((a, b) => (ts(a.start_date) ?? 9e15) - (ts(b.start_date) ?? 9e15) || (ts(a.end_date) ?? 9e15) - (ts(b.end_date) ?? 9e15));
    const agentCount = wis.filter(isAgent).length;
    wis.forEach(w => {
      const act = acts[w.activity_id] || {};
      const live = running && ['IN_PROGRESS', 'SUBMITTED', 'PENDING', 'NEW'].includes(w.status);
      const base = { key: w.id, w, act, t0: w.start_date, t1: w.end_date, live, gen: w.generation || 0,
        name: UI.flowName(w.activity_name || act.name || w.activity_id), rows: rowsOf(byTodo.get(w.id) || []) };
      let s;
      if (evDefs[w.activity_id]) s = timerStep(ctx, base);
      else if (isAgent(w)) s = agentStep(ctx, base, agentCount);
      else if (isHuman(w)) s = humanStep(ctx, base);
      else if (w.tool === 'process:report') s = reportStep(ctx, base);
      else if (CHECK.test(w.tool || '')) s = checkStep(ctx, base);
      else s = systemStep(ctx, base);
      s.state = s.state || (w.status === 'DONE' || w.status === 'COMPLETED' ? 'ok' : w.status === 'CANCELLED' ? 'stop' : w.draft_status === 'FAILED' ? 'fail' : live ? (w.status === 'PENDING' ? 'wait' : 'run') : 'idle');
      if (w.status === 'CANCELLED' && !s.stopNote) s.stopNote = UI.logText(w.log) || '취소됨';
      steps.push(s);
    });
    if (!running && !steps.some(s => s.type === 'report')) { const r = endStep(ctx); if (r) steps.push(r); }
    gapsOf(ctx, steps);
    const t0 = inst.start_date, t1 = inst.end_date;
    return { inst, v, steps, gaps: ctx.gaps, running, t0, t1, tools: steps.reduce((n, s) => n + (s.rows || []).filter(r => r.kind === 'tool').length, 0),
      outcome: window.hydResultReport ? hydResultReport.fromValues(v) : null, decision: d };
  }

  // 이 처리 건이 이미 아는 이름: 판단의 대안 · 승인 역할 · 시나리오(원인 · 고장 유형), 진단 카드의 원인 · 조치, AI 일꾼 이름
  function caseNames(v, d, agents, people) {
    const n = {};
    const put = (id, name) => { if (id && name && typeof name === 'string' && !n[id]) n[id] = name; };
    if (d) {
      (d.options || []).forEach(o => { put(o.id, o.name); if (o.approver) put(o.approver.id, o.approver.name); });
      Object.entries(d.roles || {}).forEach(([id, r]) => put(id, r && r.name));
      const o = d.origin || {}, sc = d.scenario || {};
      put(o.cause, sc.cause); put(o.failureMode, sc.failureMode);
    }
    const gc = v.guide_card || {};
    (gc.causes || []).forEach(c => { put(c.id, c.name); put(c.failureModeId, c.failureMode); });
    (gc.skills || []).forEach(k => { put(k.id, k.name); if (k.approver) put(k.approver.id, k.approver.name); });
    if (v.chosen_option) put(v.chosen_option.id, v.chosen_option.name);
    (agents || []).forEach(a => put(a.id, a.name));
    (people || []).forEach(p => put(p.id, p.name));
    return n;
  }

  /* ---------------------------------------------------------------- 시작 */
  function startStep(ctx) {
    const { inst, v } = ctx;
    const alert = v.alert || (inst.initial_variables || {}).alert || null;
    if (alert && typeof alert === 'object') {
      const ev = alert.evidence || {};
      const biz = !!alert.source && alert.source !== 'detector' && /erp|cmms|mes|scm/i.test(alert.source);
      const pressed = biz && !!ev.trigger;                           // 업무 감시가 아니라 수업 버튼이 연 처리 건(근거 값은 감시와 같은 칸)
      const who = pressed ? (ev.requested_by || '나 미선택') : (alert.observedBy && alert.observedBy.name) || (biz ? `${String(alert.source).toUpperCase()} 감시` : '센서 경보 감지기');
      const defn = ev.definition || {};
      // 버튼 기록 줄의 시각은 누른 때(data.at)다 — 기록 줄의 timestamp 는 처리 건에 붙인 때라 센서 경보로 열린 A 에서는 경보 뒤 시각이 된다
      const caseRows = rowsOf((ctx.byTodo.get('') || []).filter(x => CASE_LEVEL.has(x.job_id)))
        .map(r => r.job === 'SCENARIO_BUTTON' && r.data && r.data.at ? Object.assign(r, { t0: r.data.at }) : r);
      const plantBound = (ctx.view.definition && ctx.view.definition.activities || []).some(a => PLANT.test(a.tool || ''));
      const shown = biz ? Object.entries(ev).filter(([k, x]) => W().known(k) && x != null && typeof x !== 'object' && !/^(spare_below_min|pm_due)$/.test(k))
        : Object.entries(ev.values || {}).map(([k, x]) => [k.toLowerCase(), x]).concat(Object.entries(ev).filter(([k, x]) => /^(ts1|ce|ps1|fs1|vs1|load)$/.test(k) && typeof x === 'number' && !(ev.values || {})[k.toUpperCase()]));
      const chips = [chip(W().pattern(alert.pattern), 'danger')].concat(shown.slice(0, 6).map(([k, x]) => chip(`${W().fieldName(k)} ${W().value(k, x)}`)));
      const sentence = pressed ? `${who}${W().josa(who, '이/가')} ${ev.trigger}${W().josa(ev.trigger, '을/를')} 눌러 ${alert.asset || ''} ‘${W().pattern(alert.pattern)}’ 처리 건을 열었습니다. 근거는 그때의 업무 데이터 값입니다.`
        : biz ? `${who}${W().josa(who, '이/가')} ${alert.asset || ''} 업무 데이터에서 ‘${W().pattern(alert.pattern)}’${W().josa(W().pattern(alert.pattern), '을/를')} 발견해 처리 건을 열었습니다.`
        : `${alert.asset || ''} 센서 값이 경보 규칙에 걸려 ‘${W().pattern(alert.pattern)}’ 경보가 났고, 처리 건이 열렸습니다.`;
      const pressRows = pressed ? [['누른 사람', ev.requested_by || '나 미선택', ''], ['누른 시각', UI.dateTime ? UI.dateTime(ev.requested_at) : ev.requested_at, '']] : [];
      const table = shown.length || pressRows.length ? kvTable(pressRows.concat(shown.map(([k, x]) => [W().fieldName(k), W().value(k, x), k]))) : '';
      if (biz && !plantBound) chips.push(chip('설비 명령 없음'));
      const sections = [
        sec('들어온 값', table || '<p class="muted">값 없음</p>', { open: true }),
        caseRows.length ? sec(`수업 버튼 기록 ${caseRows.length}줄`, toolListHtml(caseRows, false, 'start'), { open: true }) : '',
        biz && !plantBound ? sec('이 흐름의 끝','<p>이 흐름은 업무 시스템에서 끝납니다 — 설비 명령 · 재관측 · 정비 수행 · 시운전 단계가 없습니다(흐름 설계). 처리되면 시작한 업무 데이터의 표시가 꺼집니다.</p>', { open: true }) : '',
        defn.rule || defn.condition ? sec('걸린 규칙', `<p>${e(W().rule(defn.rule || defn.condition))}</p>${defn.clearRule ? `<p class="muted">풀리는 조건: ${e(W().rule(defn.clearRule))}</p>` : ''}${defn.severity ? `<p class="muted">심각도 ${e(defn.severity)}</p>` : ''}`) : '',
        sec('경보 원문', rawBlock(alert), { raw: true }),
      ];
      return { key: 'start', type: 'start', lane: pressed ? 'person' : 'system', icon: biz ? 'schedule' : 'warn',
        title: pressed ? '수업 버튼으로 시작' : biz ? '업무 데이터 감시가 시작' : '센서 경보로 시작',
        actor: who, t0: alert.t || inst.start_date, t1: inst.start_date, sentence, chips, sections, rows: caseRows,
        state: caseRows.some(r => r.kind === 'error') ? 'bad' : 'ok', ids: [alert.alertId, alert.pattern], biz, pressed };
    }
    const init = inst.initial_variables || {};
    const rows = Object.entries(init).filter(([, x]) => x != null && typeof x !== 'object').slice(0, 8);
    return { key: 'start', type: 'start', lane: 'person', icon: 'flag', title: '시작', actor: '시작한 사람 · 화면', t0: inst.start_date, t1: inst.start_date,
      sentence: `‘${UI.defName(inst.proc_def_id)}’ 처리 건이 시작됐습니다.`, chips: rows.slice(0, 4).map(([k, x]) => chip(`${W().fieldName(k)} ${UI.clean(String(x)).slice(0, 40)}`)),
      sections: [rows.length ? sec('시작 값', kvTable(rows.map(([k, x]) => [W().fieldName(k), UI.clean(String(x)), k])), { open: true }) : '', sec('시작 값 원문', rawBlock(init), { raw: true })], state: 'ok' };
  }

  /* ---------------------------------------------------------------- AI 일꾼 */
  function agentStep(ctx, b, agentCount) {
    const { v, d, agents } = ctx, w = b.w;
    const evs = ctx.byTodo.get(w.id) || [];
    const started = evs.find(x => x.event_type === 'task_started');
    const done = [...evs].reverse().find(x => x.event_type === 'task_completed');
    const ag = agents[w.user_id] || null;
    const produced = ctx.producedBy(w.id);
    const owns = k => produced.includes(k) || (agentCount === 1 && !produced.length);
    const tools = b.rows.filter(r => r.kind === 'tool');
    const major = tools.filter(r => !r.minor);
    const out = w.output || {};
    const chips = [], sections = [];
    // 받은 일
    const desc = (started && started.data && started.data.task_description) || w.query || '';
    const instr = (/\[Instruction\]\s*([\s\S]*?)(?:\n\[|$)/.exec(desc) || [])[1] || '';
    if (instr || ag) sections.push(sec('받은 일', `${instr ? `<p>${e(UI.clean(W().text(instr.trim())))}</p>` : ''}${ag && ag.goal ? `<p class="muted">이 AI 일꾼의 목표: ${e(ag.goal)}</p>` : ''}`, { open: true }));
    // 스킬 · 붙인 도구 묶음 (설정 기준 — 처리 건에는 기록되지 않음)
    const skillCalls = tools.filter(r => r.tool === 'Skill');
    const sd = started && started.data ? started.data : {};
    if (Array.isArray(sd.skills)) {
      // A161-G1: 이 실행이 받은 스킬(그때의 본문 해시)과 실제로 연 스킬 파일 — 처리 건 기록 그대로
      const used = b.rows.filter(r => r.kind === 'skill');
      const servers = (ag && ag.tools) || [];
      const src = x => x === 'activity' ? '이 단계가 지정' : x === 'agent' ? 'AI 일꾼 설정' : (x || '');
      const prov = sd.skills.length ? `<div class="cr-scroll"><table class="cr-table"><thead><tr><th>스킬</th><th>판(본문 해시)</th><th>어디서 왔나</th><th>길이</th><th>설명</th></tr></thead><tbody>${
        sd.skills.map(k => `<tr><td><b>${e(k.name)}</b>${W().id(k.path)}${k.written === false ? ` ${UI.chipText('작업 폴더에 못 넣음', 'danger')}${k.error ? ` <span class="muted">${e(k.error)}</span>` : ''}` : ''}</td><td><code class="cr-ver" title="${e(k.sha256 || '')}">${e(k.version || '')}</code>${k.updated_at ? ` <span class="muted">${e(UI.dateTime(k.updated_at))} 저장본</span>` : ''}</td><td>${e(src(k.source))}</td><td class="num">${k.chars != null ? e(W().num(k.chars)) + '자' : ''}</td><td class="muted">${e(UI.clean(k.description || ''))}</td></tr>`).join('')}</tbody></table></div>`
        : '<p class="muted">제공된 스킬 없음 — 받은 일 지시문만 따랐습니다.</p>';
      const miss = (sd.skills_missing || []).length ? `<p class="cr-gapline">배정됐지만 본문이 없어 넣지 못한 스킬: ${e(sd.skills_missing.join(', '))}</p>` : '';
      const read = used.length ? `<ul class="cr-list">${used.map(r => { const x = r.data; return `<li>${e(hhmmss(r.t0))} <b>${e(x.skill)}</b>의 ${e(x.file || 'SKILL.md')} — ${e(W().toolName(x.via))}로 열었습니다${x.known === false ? ` ${UI.chipText('제공 목록에 없는 스킬', 'warning')}` : x.version ? ` <span class="muted">판 ${e(x.version)}</span>` : ''}</li>`; }).join('')}</ul>`
        : sd.skills.length ? `<p class="muted">${b.live ? '아직 스킬 파일을 연 기록이 없습니다.' : '이 실행에서 스킬 파일을 연 기록이 없습니다 — 작업 폴더에는 있었지만 AI 일꾼이 열어 보지 않았습니다.'}</p>` : '';
      sections.push(sec(`쓴 스킬 · 도구 묶음`, `<h6>제공된 스킬 ${sd.skills.length}개 <span class="muted">(실행 시작 때 작업 폴더에 넣은 본문)</span></h6>${prov}${miss}
        ${sd.skills.length ? `<h6>실제로 읽은 스킬 ${used.length}건</h6>${read}` : ''}
        ${ag ? `<dl class="cr-kv"><div><dt>AI 일꾼</dt><dd>${named(ag.name || W().who(w.user_id), w.user_id)}</dd></div><div><dt>쓸 수 있는 도구</dt><dd>${servers.map(x => `<span class="chip tone-neutral sm">${e(W().system(x))}</span>`).join(' ') || '–'}</dd></div></dl>` : ''}`, { open: true }));
      if (sd.skills.length) chips.push(chip(`스킬 ${sd.skills.map(k => k.name).join(', ')}${used.length ? ` · 읽음 ${used.length}` : ' · 안 읽음'}`, used.length ? 'accent' : 'neutral'));
    } else if (ag || skillCalls.length) {
      const servers = (ag && ag.tools) || [];
      sections.push(sec('쓴 스킬 · 도구 묶음', `${skillCalls.length ? `<p>이 처리 건에서 읽은 스킬: ${skillCalls.map(r => `<b>${e(W().ask(r.tool, r.input))}</b>`).join(', ')}</p>` : ''}
        ${ag ? `<dl class="cr-kv"><div><dt>AI 일꾼</dt><dd>${named(ag.name || W().who(w.user_id), w.user_id)}</dd></div>
          <div><dt>스킬</dt><dd>${(ag.skills || []).length ? ag.skills.map(s => `<span class="chip tone-accent sm">${e(s)}</span>`).join(' ') : '<span class="muted">없음 — 받은 일 지시문만 따름</span>'}</dd></div>
          <div><dt>쓸 수 있는 도구</dt><dd>${servers.map(s => `<span class="chip tone-neutral sm">${e(W().system(s))}</span>`).join(' ') || '–'}</dd></div></dl>
          ${skillCalls.length ? '' : '<p class="cr-gapline">스킬은 AI 일꾼의 지금 설정입니다. 이 처리 건에서 실제로 읽었는지는 기록되지 않습니다.</p>'}` : ''}`));
      if (ag && (ag.skills || []).length) chips.push(chip(`스킬 ${ag.skills.join(', ')}`, 'accent'));
    }
    // 가져온 데이터 (판단이 쓴 사실의 출처 + 도구로 직접 읽은 값)
    const prov = owns('decision') && d && Array.isArray(d.provenance) ? d.provenance : [];
    const pw = W().causeWords(d && d.origin && d.origin.cause_route);
    const provName = p => (p.variable === 'cause' && pw.input) || (p.variable === 'failure_mode' && pw.inputFm) || p.name || W().fieldName(p.variable);
    const dataCalls = major.filter(r => /업무|ERP|MES|CMMS|SCM|센서|정비|구매|생산|공급/.test(W().toolSystem(r.tool)));
    if (prov.length || dataCalls.length) {
      const provRows = prov.map(p => `<tr><td>${named(provName(p), p.variable)}</td><td class="num">${e(W().value(p.variable, p.value))}</td><td>${e(p.sourceName || W().system(p.source))}${W().id(p.source)}</td><td class="muted">${e(UI.clean(p.how || ''))}</td></tr>`).join('');
      sections.push(sec(`가져온 데이터 ${prov.length ? prov.length + '건' : ''}`, `${prov.length ? `<div class="cr-scroll"><table class="cr-table"><thead><tr><th>값</th><th>읽은 값</th><th>어느 시스템</th><th>어떻게</th></tr></thead><tbody>${provRows}</tbody></table></div>` : ''}
        ${dataCalls.length ? `<p class="muted">도구로 직접 읽은 곳: ${[...new Set(dataCalls.map(r => W().toolSystem(r.tool)))].map(x => e(x)).join(' · ')} (아래 도구 호출에 물음 · 받음)</p>` : ''}`, { open: !!prov.length }));
      chips.push(chip(`데이터 ${prov.length || dataCalls.length}건`));
    }
    // 지식 경로 (진단: 경보 → 증상 → 고장 유형 ← 원인 · 증거, 판단: 원인 → 조치 → 규칙 · 출처 절 · 득실 경로)
    const kg = knowledgeHtml(ctx, owns('guide_card') || owns('cause') ? v.guide_card : null, owns('decision') ? d : null);
    if (kg) sections.push(sec('지식 경로 · 출처', kg, { open: true }));
    // 도구 호출 — 물음 → 받음 한 줄씩, 보조 작업(도구 불러오기 · 파일 · 명령)은 접어 둔다
    if (b.rows.length) {
      const minor = b.rows.filter(r => r.minor).length;
      sections.push(sec(`도구 호출 ${tools.length}회${minor ? ` · 보조 작업 ${minor}건 포함` : ''}`, toolListHtml(b.rows, b.live, b.key), { open: b.live, cls: 'cr-tools' }));
      chips.unshift(chip(`도구 ${tools.length}회`));
    }
    // 비교한 대안 · 추천
    let rec = null;
    if (owns('decision') && d && (d.options || []).length) {
      rec = d.options.find(o => o.id === d.recommended) || null;
      sections.push(sec(`비교한 대안 ${d.options.length}개`, altHtml(d), { open: true }));
      if (rec) chips.push(chip(`추천 ${W().text(rec.name)}`, 'success'));
    } else if (owns('decision') && v.decision_id && !d) {
      const r = ctx.read.decision;
      sections.push(sec('비교한 대안', r.state === 'loading' ? '<p class="muted">판단 기록을 읽는 중입니다…</p>'
        : `<p class="cr-gapline">판단 기록${W().id(v.decision_id)}을 읽지 못했습니다 — ${e(r.error || '이유 모름')}</p>`, { open: true }));
    }
    const cause = owns('cause') && v.cause ? (((v.guide_card || {}).causes || []).find(c => c.id === v.cause) || {}).name || nm(v.cause) : '';
    const cw = W().causeWords(d && d.origin && d.origin.cause_route);
    if (cause) chips.push(chip(`${cw.cause} ${cause}`, 'warning'));
    if (done && done.data && done.data.text) sections.push(sec('AI 일꾼이 남긴 말', `<p class="prose">${e(UI.clean(W().text(done.data.text)).replace(/`/g, ''))}</p>`));
    sections.push(sec('결과 값 원문', rawBlock(out), { raw: true }));
    // 한 문장
    const parts = [];
    if (tools.length) parts.push(`도구를 ${tools.length}번 써서`);
    if (cause) parts.push(cw.found(cause));
    let sentence;
    if (rec) sentence = `${parts.join(' ')} 대안 ${d.options.length}개를 비교해 ‘${W().text(rec.name)}’${W().josa(W().text(rec.name), '을/를')} 추천했습니다.`;
    else if (cause) sentence = `${parts.join(' ')} 판단을 넘겼습니다.`;
    else if (done && done.data && done.data.text) sentence = (parts.length ? parts.join(' ') + ' ' : '') + firstSentence(done.data.text);
    else sentence = b.live ? (tools.length ? `도구를 ${tools.length}번 썼고, 지금 일하는 중입니다.` : 'AI 일꾼이 일을 받기를 기다리는 중입니다.') : '기록된 결과 문장이 없습니다.';
    const lastOpen = b.live ? [...b.rows].reverse().find(r => r.kind === 'tool' && r.status === 'running') : null;
    return Object.assign(b, { type: 'agent', lane: 'agent', icon: 'agent', title: b.name, actor: ag ? ag.name : W().who(w.user_id) || 'AI 일꾼', sentence, chips, sections,
      now: lastOpen ? `${W().toolName(lastOpen.tool)} — ${W().ask(lastOpen.tool, lastOpen.input)}` : b.live ? '다음 행동을 정하는 중' : '', ids: [w.user_id, w.activity_id] });
  }

  function knowledgeHtml(ctx, gc, d) {
    const out = [];
    if (gc && typeof gc === 'object') {
      const top = (gc.causes || []).find(c => c.id === gc.topCause) || (gc.causes || [])[0];
      const pat = (gc.alert && gc.alert.pattern) || ctx.v.pattern;
      if (top) out.push(pathHtml([['경보', W().pattern(pat), pat], ['증상', (top.symptoms || []).join(' · ')], ['고장 유형', top.failureMode, top.failureModeId], ['원인', top.name, top.id]], ['→', '→', '←']));
      const causes = (gc.causes || []);
      if (causes.length) out.push(`<h6>원인 후보와 증거 — 센서 기록 DB 에서 잰 값</h6><div class="cr-scroll"><table class="cr-table"><thead><tr><th>원인</th><th>점수</th><th>증거</th><th>잰 값</th><th>기준</th><th>판정</th></tr></thead><tbody>${
        causes.map(c => (c.evidence || [{}]).map((x, i) => `<tr class="${c.id === (top && top.id) ? 'win' : ''}">${i === 0 ? `<td rowspan="${(c.evidence || [{}]).length}">${named(c.name, c.id)}</td><td rowspan="${(c.evidence || [{}]).length}" class="num">${e(W().num(c.score))}</td>` : ''}<td>${e(x.name || '–')}</td><td class="num">${x.value != null ? e(W().num(x.value)) : '–'}</td><td class="num">${x.threshold != null ? `${x.expect === 'lt' ? '<' : x.expect === 'gte' ? '≥' : x.expect === 'gt' ? '>' : x.expect === 'lte' ? '≤' : ''} ${e(W().num(x.threshold))}` : '–'}</td><td>${x.status ? UI.chipText(x.passed ? '맞음' : '아님', x.passed ? 'success' : 'neutral') : ''}</td></tr>`).join('')).join('')}</tbody></table></div>`);
    }
    if (d) {
      const o = d.origin || {}, rec = (d.options || []).find(x => x.id === d.recommended);
      if (o.cause_basis) out.push(`<p class="muted">원인을 정한 근거: ${e(basisText(o.cause_basis))}</p>`);
      if (rec) {
        const REL = { MITIGATED_BY: '완화 조치', REMEDIED_BY: '근본 조치', PREVENTED_BY: '예방 조치' };
        const fm = o.failureMode, cause = o.cause, cw = W().causeWords(o.cause_route);
        out.push(`<h6>추천안에 이른 길</h6>` + pathHtml([[cw.cause, nm(cause), cause], [cw.failureMode, nm(fm), fm], [REL[rec.relation] || '조치', W().text(rec.name), rec.id]], ['→', '→']));
        const rules = (rec.selectedBy || []).map(r => `<li>${UI.chipText('후보로 고른 규칙', 'accent')} ${e(W().text(r.annotation || nm(r.rule)))}${W().id(r.rule)}${(r.sources || []).length ? ` <span class="muted">출처 ${r.sources.map(x => e(x)).join(', ')}</span>` : ''}</li>`).join('');
        const steps = (rec.steps || []).map(s => `<li><b>${e(s.order || '')}.</b> ${e(W().text(s.text || ''))}${s.manual ? `<div class="cr-src">${UI.chipText(s.manual.ref || s.manual.id, 'neutral')} <b>${e(s.manual.title || '')}</b>${s.manual.excerpt ? ` — <span class="muted">“${e(W().text(s.manual.excerpt))}”</span>` : ''}</div>` : ''}</li>`).join('');
        if (rules) out.push(`<ul class="cr-list">${rules}</ul>`);
        if (steps) out.push(`<h6>추천안의 작업 순서와 출처 문서 절</h6><ol class="cr-list">${steps}</ol>`);
        const paths = (rec.tradeoffEvaluation || []).filter(p => (p.edges || []).length || (p.nodes || []).length).slice(0, 4);
        if (paths.length) out.push(`<h6>회사 성과 지표에 미치는 길 (득 · 실)</h6><ul class="cr-list">${paths.map(p => `<li>${UI.chipText(p.good === false ? '실' : '득', p.good === false ? 'danger' : 'success')} <b>${e(p.name || '')}</b> <span class="cr-chain">${chainText(p, rec)}</span>${(p.conds || []).length ? ` <span class="muted">(조건: ${e(p.conds.join(', '))})</span>` : ''}</li>`).join('')}</ul>`);
      }
      if (d.rankRule && d.rankRule.annotation) out.push(UI.fold('점수를 매기는 법', `<p class="prose">${e(W().text(d.rankRule.annotation))}</p>${(d.rankRule.sources || []).length ? `<p class="muted">출처 ${d.rankRule.sources.map(x => e(x)).join(', ')}</p>` : ''}`, { cls: 'small' }));
    }
    return out.join('');
  }
  const basisText = s => String(s).replace(/ontology/gi, '지식 그래프').replace(/same query as diagnose/i, '원인 진단과 같은 질의').replace(/via business_causes/i, '— 업무 경보 원인 찾기 도구')
    .replace(/failure mode/gi, '고장 유형').replace(/FailureMode/g, '고장 유형').replace(/\bpattern\b/gi, '경보 패턴').replace(/\bsymptom\b/gi, '증상').replace(/\bcause\b/gi, '원인').replace(/\bCause\b/g, '원인')
    .replace(/\bSkill\b/g, '조치').replace(/\bPart\b/g, '부품').replace(/-PREVENTED_BY->/g, '→ 예방 조치 →').replace(/-INVOLVES_PART->/g, '→ 쓰는 부품 →')
    .replace(/-CAUSES->/g, '→ 일으키는 고장 →').replace(/\bpart\b/g, '부품').replace(/\bskill\b/g, '조치').replace(/\bT1\b/g, '').replace(/\s+/g, ' ').trim();
  function chainText(p, rec) {
    if ((p.nodes || []).length) return p.nodes.map(n => e(nm(n))).join(' → ');
    const edges = p.edges || [];
    const parts = [e(W().text(rec.name))];
    edges.forEach(x => parts.push(`${e(nm(x.target))}${x.note ? ` <span class="muted">(${e(x.note)}${x.unit && !/[a-z%]$/i.test(String(x.note)) ? ' ' + e(x.unit) : ''})</span>` : ''}`));
    return parts.join(' → ') + (p.dir != null ? ` ${p.dir > 0 ? '↑' : '↓'}` : '');
  }
  function pathHtml(nodes, arrows) {
    return `<div class="cr-path">${nodes.map(([label, name, id], i) => `${i ? `<span class="cr-arrow" aria-hidden="true">${arrows[i - 1] || '→'}</span>` : ''}<span class="cr-node"><small>${e(label)}</small><b>${e(name || '–')}</b>${W().id(id)}</span>`).join('')}</div>`;
  }

  // 대안: 추천안 + 나머지(점수 · 진 이유 · 에이전트가 그 안에 대해 한 말)
  function altHtml(d) {
    const opts = [...(d.options || [])].sort((a, b) => (b.id === d.recommended) - (a.id === d.recommended) || (b.feasible - a.feasible) || ((a.rank || 99) - (b.rank || 99)));
    const rec = opts.find(o => o.id === d.recommended) || opts[0];
    const said = o => window.hydApprove ? W().text(hydApprove.sentenceAbout(d.explanation, o.name).replace(/^\s*\d+순위\s*/, '')) : '';
    // 머리말 값: 예측이 고르는 근거인 안(설비를 바꾸는 안 · 안마다 예측이 갈림)만 예측, 아니면 이 안의 업무 값(approvalCard.js forecastDecides)
    const fcFirst = o => hydApprove.forecastDecides(o, d.options);
    const fc = o => fcFirst(o) ? (o.forecast || []).slice(0, 2).map(f => `${W().text(f.name)} ${W().num(+f.value)}${f.unit || ''}`).join(' · ') : '';
    // 카드마다 다른 사실(결정 수준에서는 "후보마다 계산"으로 비어 있는 값 — 발주 금액 · 공급사 불량률 등): 규칙이 이 값으로 감점 · 제외한다
    const own = o => hydApprove.ownValues(o, d).join(' · ');
    const why = o => {
      // 추천안의 이유 줄: 위에 그린 머리말이 이 안의 값이면 다시 적지 않는다(예측 머리말은 예전대로 이유 줄 앞에도 둔다)
      if (o.id === rec.id) return hydApprove.reasons(o, d, { head: fcFirst(o) }).join(' · ');
      if (!o.feasible) return `제외 — ${W().text(((o.violations || [])[0] || {}).annotation || ((o.violations || [])[0] || {}).rule || '규정 위반')}`;
      const a = o.scoreParts || {}, b = rec.scoreParts || {};
      const diff = Object.keys({ ...a, ...b }).map(k => [k, (+a[k] || 0) - (+b[k] || 0)]).filter(([, x]) => Math.abs(x) >= 0.05);
      const lose = diff.filter(([, x]) => x < 0).sort((x, y) => x[1] - y[1]).slice(0, 2).map(([k, x]) => `${UI.t('score.' + k)} ${W().num(x)}`);
      const win = diff.filter(([, x]) => x > 0).sort((x, y) => y[1] - x[1]).slice(0, 1).map(([k, x]) => `${UI.t('score.' + k)} +${W().num(x)}`);
      const pen = [...(o.penalties || []), ...(o.warnings || [])].map(x => W().text(x.annotation || x.message || '')).filter(Boolean)[0];
      return [lose.length ? `추천안보다 ${lose.join(' · ')}` : '', win.length ? `${win.join('')}는 앞섬` : '', pen ? `감점 · 경고: ${pen}` : ''].filter(Boolean).join(' / ') || (Number.isFinite(+o.score) && Number.isFinite(+rec.score) ? `점수 ${W().num(rec.score - o.score)} 낮음` : '');
    };
    const rows = opts.map(o => {
      const tag = o.id === rec.id ? UI.chipText('추천', 'success') : !o.feasible ? UI.chipText('제외', 'danger') : UI.chipText('짐', 'neutral');
      return `<li class="cr-alt ${o.id === rec.id ? 'win' : !o.feasible ? 'out' : ''}"><div class="cr-alt-head">${tag}<b>${e(W().text(o.name))}</b>${W().id(o.id)}<span class="num muted">${Number.isFinite(+o.score) && o.score !== null ? e(W().num(+o.score)) + '점' : ''}</span>${o.approver && o.approver.name ? `<span class="muted">승인 ${e(o.approver.name)}</span>` : ''}</div>
        ${fc(o) ? `<p class="muted">예측 ${e(fc(o))}</p>` : ''}${own(o) ? `<p class="muted">이 안의 값 ${e(own(o))}</p>` : ''}<p>${o.id === rec.id ? why(o) : e(why(o))}</p>${o.id !== rec.id && said(o) ? `<p class="cr-said">AI 일꾼: “${e(said(o))}”</p>` : ''}</li>`;
    }).join('');
    return `<ol class="cr-alts">${rows}</ol>${d.explanation ? UI.fold('AI 일꾼의 판단 설명 전문', `<p class="prose">${e(W().text(d.explanation))}</p>`, { cls: 'small' }) : ''}`;
  }

  /* ---------------------------------------------------------------- 사람 */
  function humanStep(ctx, b) {
    const { d, v, view } = ctx, w = b.w;
    const appr = (view.approvals || []).find(a => a.todo_id === w.id) || null;
    const hist = d && (d.history || []).filter(h => h.state === 'APPROVED').pop();
    // 판단의 승인 이력은 처리 건 전체 것이다 — 승인 카드 단계(select_card · 승인 전달 기록)가 따로 있으면 그 단계에만 붙인다(책임자 확인 같은 다른 사람 단계에 같은 승인을 또 그리지 않게)
    const claimed = (view.workitems || []).some(x => x.tool === 'formHandler:select_card' || (view.approvals || []).some(a => a.todo_id === x.id));
    const isApproval = !!(appr || w.tool === 'formHandler:select_card' || (hist && !claimed));
    if (!isApproval) {
      const out = w.output || {}, who = W().who(w.user_id);
      return Object.assign(b, { type: 'human', lane: 'person', icon: 'human', title: b.name, actor: who,
        sentence: w.status === 'DONE' ? `${who}${W().josa(who, '이/가')} ‘${b.name}’${W().josa(b.name, '을/를')} 마쳤습니다.` : b.live ? `${who}의 입력을 기다리는 중입니다.` : UI.logText(w.log),
        chips: Object.entries(out).filter(([, x]) => x != null && typeof x !== 'object').slice(0, 4).map(([k, x]) => chip(`${W().fieldName(k)} ${W().value(k, x)}`)),
        sections: [sec('입력한 값', rawBlock(out), { raw: true })] });
    }
    const byId = (hist && hist.by) || (appr && appr.payload && appr.payload.by) || v.approved_by || '';
    const by = byId ? W().who(byId) : '';        // 승인 화면에서 고른 "나"는 user:… id 로 남는다 → 사람 이름
    const role = (hist && hist.role) || (appr && appr.payload && appr.payload.role) || v.approved_role || '';
    const when = (hist && hist.t) || (appr && appr.created_at) || w.end_date;
    const optId = (hist && hist.option) || v.chosen_skill || (appr && appr.payload && appr.payload.option);
    const opt = (d && (d.options || []).find(o => o.id === optId)) || v.chosen_option || {};
    const changed = d && optId && d.recommended && optId !== d.recommended;
    const reason = (hist && hist.reason) || (appr && appr.payload && appr.payload.reason) || '';
    const plan = (appr && appr.payload && appr.payload.plan) || {};
    const todo = [...(plan.ot || []), ...(plan.enterprise || [])];
    const acts = todo.length ? todo : (opt.actions || []);
    const sections = [];
    if (by || when) sections.push(sec('누가 · 언제 · 무엇을', `<dl class="cr-kv"><div><dt>승인한 사람</dt><dd><b>${e(by || '–')}</b>${W().id(byId !== by ? byId : '')}${role ? ` · ${e(W().who(role))}${W().id(role)}` : ''}</dd></div>
      <div><dt>승인한 시각</dt><dd>${e(when ? new Date(when).toLocaleDateString('ko-KR', { month: 'numeric', day: 'numeric' }) + ' ' + hhmmss(when) : '–')}</dd></div><div><dt>고른 안</dt><dd>${named(W().text(opt.name || nm(optId) || '–'), optId)} ${changed ? UI.chipText('추천안 대신 고름', 'warning') : d ? UI.chipText('추천안 그대로', 'success') : ''}</dd></div>
      ${opt.approver && opt.approver.name ? `<div><dt>필요한 승인 권한</dt><dd>${e(opt.approver.name)}</dd></div>` : ''}${reason ? `<div><dt>남긴 사유</dt><dd>${e(reason)}</dd></div>` : ''}
      <div><dt>기다린 시간</dt><dd>${e(b.t0 && b.t1 ? fmtMs(ts(b.t1) - ts(b.t0)) : '–')} <span class="muted">(승인 요청이 올라온 때부터)</span></dd></div></dl>`, { open: true }));
    if (acts.length) sections.push(sec('승인으로 시스템에 넘긴 일', `<ul class="cr-list">${acts.map(a => `<li>${e(W().action({ code: a.code, value: a.value }))} <span class="muted">→ ${e(W().system(a.system || a.target))}</span>${W().id(a.code)}</li>`).join('')}</ul>`, { open: true }));
    const cc = appr && appr.payload && appr.payload.current_check;
    if (cc) sections.push(sec('승인 순간 다시 확인한 값', `<p>${cc.allowed ? UI.chipText('그대로 실행해도 됨', 'success') : UI.chipText('실행 불가', 'danger')} ${(cc.reasons || []).map(r => e(W().text(r.annotation || r.rule || r))).join(' · ')}${cc.checked_at ? ` <span class="muted">${e(hhmmss(cc.checked_at))}</span>` : ''}</p>
      ${kvTable(Object.entries(cc.facts || {}).filter(([k, x]) => W().known(k) && x != null && typeof x !== 'object').map(([k, x]) => [W().fieldName(k), W().value(k, x), k]))}${(cc.unknown || []).length ? `<p class="cr-gapline">모르는 값: ${e(cc.unknown.join(', '))}</p>` : ''}`));
    if (appr) sections.push(sec('승인 전달 기록', `<ul class="cr-list">${(appr.history || []).map(h => `<li>${e(hhmmss(h.t))} ${e({ PENDING: '승인 접수', DELIVERED: '시스템에 전달 완료', FAILED: '전달 실패', DISCARDED: '승인 폐기' }[h.status] || UI.status(h.status))}${h.by ? ` · ${e(W().who(h.by))}` : ''}</li>`).join('')}</ul><p class="muted">전달 시도 ${e(appr.attempts)}회 · 지금 ${e({ PENDING: '전달 대기', DELIVERED: '전달 완료', FAILED: '전달 실패', DISCARDED: '폐기' }[appr.status] || UI.status(appr.status))}</p>`));
    sections.push(sec('승인 원문', rawBlock(appr ? appr.payload : w.output), { raw: true }));
    const chips = [chip(`${by || '–'}${role ? ' · ' + W().who(role) : ''}`, 'accent'), chip(W().text(opt.name || nm(optId) || '–'), changed ? 'warning' : d ? 'success' : 'neutral')];
    if (b.t0 && b.t1) chips.push(chip(`기다림 ${fmtMs(ts(b.t1) - ts(b.t0))}`));
    const subject = by || W().who(role), optName = W().text(opt.name || nm(optId));
    // 판단을 못 읽었으면 추천안과 같은지 모른다 — 모르는 것은 말하지 않는다
    const how = !d ? '' : changed ? '추천안 대신 골라 ' : '추천안 그대로 ';
    const sentence = w.status === 'DONE' ? `${subject}${role && by ? `(${W().who(role)})` : ''}${W().josa(subject, '이/가')} ${when ? hhmmss(when) + '에 ' : ''}‘${optName}’${W().josa(optName, '을/를')} ${how}승인했습니다.`
      : b.live ? `${W().who(w.user_id)}의 승인을 기다리는 중입니다.` : UI.logText(w.log);
    return Object.assign(b, { type: 'approve', lane: 'person', icon: 'human', title: b.name, actor: by ? `${by}${role ? ' · ' + W().who(role) : ''}` : W().who(w.user_id), sentence, chips, sections,
      now: b.live ? '담당자가 승인 카드를 보고 있습니다' : '', ids: [w.activity_id, role] });
  }

  /* ---------------------------------------------------------------- 시스템 처리 */
  const sysRowsHtml = (b) => b.rows.length ? toolListHtml(b.rows, b.live, b.key) : '';
  function mailOf(o) { const n = o && o.notice; return n && n.arguments ? n : null; }
  function systemStep(ctx, b) {
    const { v, inc } = ctx, w = b.w, out = w.output || {};
    const chips = [], sections = [];
    let icon = 'system', sentence = '', target = '';
    const tool = w.tool || '';
    if (tool === 'incident:command') {
      icon = 'command'; target = '설비 제어';
      const cmds = Array.isArray(v.commands) ? v.commands : [];
      const label = cmds.map(c => W().action(c)).join(' · ') || '명령';
      const ack = inc && inc.ack;
      sentence = `${target}에 ‘${label}’ 명령${inc && inc.cmdId ? `(${inc.cmdId})` : ''}을 보냈고, ${ack ? `설비가 ${ack.result === 'DONE' ? '실행 완료' : UI.status(ack.result)}로 답했습니다${ack.interlock ? ` (안전 연동 ${ack.interlock === 'PASS' ? '통과' : UI.status(ack.interlock)})` : ''}.` : ackMissing(ctx, inc)}`;
      chips.push(chip(label, 'accent'));
      if (inc && inc.cmdId) chips.push(chip(inc.cmdId));
      if (ack) chips.push(chip(`응답 ${ack.result === 'DONE' ? '완료' : UI.status(ack.result)}`, ack.result === 'DONE' ? 'success' : 'danger'));
      const hist = inc ? (inc.history || []).filter(h => /CMD_ISSUED|AWAITING_ACK|ACKED|ACK_/.test(h.state)) : [];
      if (hist.length) sections.push(sec('설비와 주고받은 기록', `<ul class="cr-list">${hist.map(h => `<li>${e(hhmmss(h.t))} ${e(UI.status(h.state))}${h.note ? ` · ${e(W().rule(UI.logText(h.note)))}` : ''}</li>`).join('')}</ul>`, { open: true }));
      if (!inc) incidentGap(ctx, '설비 응답(명령 번호 · 응답 · 안전 연동)');
    } else if (/WO_CREATE/.test(tool)) {
      icon = 'workorder'; target = '정비 시스템 (CMMS)';
      const wo = out.work_order || v.work_order || {};
      const win = (wo.after && wo.after.window) || '';
      sentence = wo.ref ? `${target}에 작업지시 ${wo.ref}${W().josa(wo.ref, '을/를')} 등록했습니다${win ? ` — ${UI.words(win)}` : ''}.` : `${target}에 작업지시를 등록하는 중입니다.`;
      if (wo.ref) chips.push(chip(wo.ref, 'accent'));
      if (win) chips.push(chip(UI.words(win)));
      if (wo.detail) sections.push(sec('등록한 내용', `<p>${e(W().text(wo.detail))}</p>`, { open: true }));
      const m = mailOf(wo); if (m) { sentence += ` 그리고 ${m.arguments.to}에게 메일을 보냈습니다.`; chips.push(chip('메일 1통')); sections.push(sec('보낸 메일', mailHtml(m), { open: true })); }
    } else if (/PR_CREATE/.test(tool)) {
      icon = 'order'; target = 'ERP';
      const po = out.purchase_order || v.purchase_order || {};
      const sup = supplierName(ctx, v.approved_supplier);
      sentence = po.ref ? `${target}에 발주 ${po.ref}${W().josa(po.ref, '을/를')} 넣었습니다 — ${sup} ${v.approved_qty != null ? v.approved_qty + '개' : ''} ${v.approved_amount != null ? W().num(v.approved_amount) + '만원' : ''}${po.after && po.after.lead_d != null ? `, 리드타임 ${po.after.lead_d}일` : ''}.` : `${target}에 발주를 넣는 중입니다.`;
      if (po.ref) chips.push(chip(po.ref, 'accent'));
      if (v.approved_amount != null) chips.push(chip(`${W().num(v.approved_amount)}만원`));
      if (v.approved_qty != null) chips.push(chip(`${v.approved_qty}개`));
      sections.push(sec('발주 값 (승인 순간 서버가 견적으로 확정)', kvTable([['공급사', sup, v.approved_supplier], ['부품', W().text(v.approved_part_no || '–'), ''], ['수량', W().value('approved_qty', v.approved_qty), ''], ['단가', W().value('approved_unit_price', v.approved_unit_price), ''], ['금액', W().value('approved_amount', v.approved_amount), '']]), { open: true }));
      const m = mailOf(po); if (m) { sentence += ` 공급사 · 입고 부서에 메일을 보냈습니다.`; chips.push(chip('메일 1통')); sections.push(sec('보낸 메일', mailHtml(m), { open: true })); }
    } else if (tool === 'plant:restore') {
      icon = 'schedule'; target = '정비 시스템 · 설비';
      const m = out.maintenance || v.maintenance || {};
      const waitEv = b.rows.find(r => r.kind === 'sys' && r.data && r.data.plan);
      const skipped = b.rows.find(r => r.kind === 'sys' && r.job === 'WAIT_SKIPPED');
      sentence = w.status === 'DONE' ? `${skipped ? '즉시 ' : waitEv ? '예정된 정비 시간까지 기다린 뒤 ' : ''}정비를 했고, 작업지시 ${m.work_order || ''} 완료와 설비 ${({ all: '전체', pump: '펌프', cooler: '쿨러', fan: '쿨러 팬' })[m.component] || nm(m.component) || ''} 복구를 기록했습니다.`
        : waitEv ? `예정된 정비 시간까지 기다리는 중입니다 (${virtual(waitEv.data.plan)}).` : '정비를 하는 중입니다.';
      if (waitEv) chips.push(chip(`대기 ${virtual(waitEv.data.plan)}`));
      if (m.work_order) chips.push(chip(`${m.work_order} 완료`, 'success'));
      if (m.notice) sections.push(sec('정비 완료 알림', `<p>${e(W().text(m.notice))}</p>`, { open: true }));
    } else if (tool === 'process:wait') {
      icon = 'timer'; target = '처리 엔진';
      const p = (out.waited) || ((b.rows.find(r => r.data && r.data.plan) || {}).data || {}).plan;
      sentence = p ? `${p.label || '정해진 시간'}까지 기다렸습니다 (${virtual(p)}).` : '정해진 시간까지 기다리는 중입니다.';
    } else if (tool === 'mcp:call') {
      icon = 'tool'; const r = Object.values(out).find(x => x && x.tool) || {};
      target = W().system(r.server); sentence = r.tool ? `${target}의 ‘${W().toolName(`mcp__${r.server}__${r.tool}`)}’${W().josa(W().toolName(`mcp__${r.server}__${r.tool}`), '을/를')} 불렀습니다.` : '승인 뒤 도구를 부르는 중입니다.';
    } else {
      sentence = UI.logText(w.log) || (w.status === 'DONE' ? `‘${b.name}’${W().josa(b.name, '을/를')} 마쳤습니다.` : `‘${b.name}’${W().josa(b.name, '을/를')} 하는 중입니다.`);
      target = W().who(w.user_id);
    }
    if (b.rows.length) sections.push(sec(`시스템 기록 ${b.rows.length}줄`, sysRowsHtml(b), { open: b.live }));
    if (w.log) sections.push(sec('엔진 메모', `<p class="muted">${e(UI.logText(w.log))}</p>`));
    sections.push(sec('결과 값 원문', rawBlock(out), { raw: true }));
    if (w.status === 'PENDING') sentence = `멈춤 — ${UI.logText(w.log) || '조건이 맞지 않아 보류'}`;
    return Object.assign(b, { type: 'system', lane: 'system', icon, title: b.name, actor: target || '시스템', sentence, chips, sections,
      now: b.live ? (b.rows.length ? b.rows[b.rows.length - 1].text || '' : '시스템이 처리하는 중') : '', ids: [w.tool] });
  }
  // 설비 응답이 없을 때: 진행 중이면 기다림, 사건을 읽는 중 · 못 읽음 · 끝났는데 응답 기록 없음을 가른다
  function ackMissing(ctx, inc) {
    if (inc) return ctx.running ? '설비의 응답을 기다립니다.' : '설비 응답이 사건 기록에 남지 않았습니다.';
    const r = ctx.read.incident;
    return r.state === 'loading' ? '설비 응답을 읽는 중입니다.' : '설비 응답은 사건 기록을 읽지 못해 알 수 없습니다 (아래 "기록에 없는 것").';
  }
  // 사건 기록이 없을 때 이유별 한 줄 — 번호 없음 · 읽는 중 · 실패(서버 사유)를 섞지 않는다
  function incidentGap(ctx, what) {
    const r = ctx.read.incident;
    if (r.state === 'loading') return;
    ctx.gaps.push({ key: 'inc', strong: true, text: r.state === 'none' ? `처리 건 값에 사건 번호가 없어 ${what}을 보이지 못했습니다.`
      : `사건 기록을 읽지 못해 ${what}을 보이지 못했습니다 — ${r.error || '이유 모름'}` });
  }
  function supplierName(ctx, sid) {
    if (!sid) return '–';
    const o = ctx.d && (ctx.d.options || []).find(x => (x.actions || []).some(a => a.value === sid));
    const n = UI.name(sid);
    return n !== sid ? n : o ? W().text(o.name).replace(/\s*(표준|대체|최저가)?\s*발주$/, '') : sid;
  }
  const mailHtml = m => `<dl class="cr-kv"><div><dt>받는 사람</dt><dd>${e(m.arguments.to || '')}</dd></div><div><dt>제목</dt><dd>${e(m.arguments.subject || '')}</dd></div>
    <div><dt>본문</dt><dd>${e(W().text(m.arguments.body || ''))}</dd></div>${m.called_at ? `<div><dt>보낸 시각</dt><dd>${e(hhmmss(m.called_at))}</dd></div>` : ''}${m.idempotent != null ? `<div><dt>중복 방지</dt><dd>같은 일을 다시 해도 한 통만</dd></div>` : ''}</dl>`;

  /* ---------------------------------------------------------------- 확인 (값 vs 기준) */
  function checkStep(ctx, b) {
    const { v, inc } = ctx, w = b.w, out = w.output || {};
    const chips = [], sections = [];
    let sentence = '', icon = 'check', verdict = null;
    if (w.tool === 'incident:reobserve') {
      const hist = inc ? inc.history || [] : [];
      const obs = hist.find(h => h.state === 'RE_OBSERVING');
      const fin = [...hist].reverse().find(h => /RESOLVED|ESCALATED|NOT_RECOVERED|MITIGATION_FAILED/.test(h.state) && h.note);
      const crit = inc && inc.recoveryPolicy && inc.recoveryPolicy.criterion;
      const m = fin && /(\w+)\s+(-?[\d.]+)\s*(<=|>=|<|>)\s*(-?[\d.]+)/.exec(fin.note);
      const rec = out.recovered != null ? out.recovered : v.recovered;
      verdict = rec;
      if (!inc) incidentGap(ctx, '재관측 기준 · 사건 기록');
      const tag = m ? m[1].toLowerCase() : crit ? String(crit[0]).toLowerCase() : '';
      const valTxt = m ? `${W().fieldName(tag)} ${W().num(+m[2])} ${W().unit(tag)}` : '';
      sentence = rec == null ? `설비가 기준 안으로 돌아오는지 지켜보는 중입니다${obs && obs.note ? ` (${UI.logText(obs.note)})` : ''}.`
        : `${obs && obs.note ? UI.logText(obs.note) + ' 동안 ' : ''}지켜본 뒤 ${reobsBasis(valTxt, crit, rec)}${rec ? '회복으로' : '미회복으로'} 판정했습니다.`;
      // A161-G3: 지켜본 동안의 값 흐름 (사건 reobsSeries, 작업지시 뒤 재관측은 REOBSERVATION 이벤트 reading.series)
      const evSeries = (b.rows.find(r => r.data && r.data.reading && r.data.reading.series) || {}).data;
      const series = (inc && inc.reobsSeries) || (evSeries && evSeries.reading.series) || (out.reading && out.reading.series) || null;
      if (series && series.error) {
        // 백엔드가 값 흐름을 읽지 못한 경우 — "값이 없었다"와 구별해 사유를 그대로 보인다
        b.series = series;
        sections.unshift(sec('지켜본 동안의 값', `<p class="cr-gapline">값 흐름을 읽지 못했습니다: ${e(series.error)}</p>`, { open: true }));
        chips.push(chip('값 흐름 못 읽음', 'warning'));
      } else if (series && (series.points || []).length) {
        b.series = series;
        sentence = `${seriesSentence(series)} — ${rec == null ? '판정 중' : rec ? '회복으로 판정' : '미회복으로 판정'}했습니다.`;
        sections.unshift(sec('지켜본 동안의 값', seriesHtml(series), { open: true }));
        chips.push(chip(`기준 안 ${Math.round((series.inside_share || 0) * 100)} %`, series.inside_last ? 'success' : 'danger'));
      }
      if (valTxt) chips.push(chip(valTxt, rec ? 'success' : 'danger'));
      if (crit) chips.push(chip(`기준 ${W().criterion(crit)}`));
      if (inc && inc.cleared != null) chips.push(chip(`경보 해제 ${inc.cleared ? '예' : '아니요'}`, inc.cleared ? 'success' : 'warning'));
      if (hist.length) sections.push(sec('사건 기록', `<ul class="cr-list">${hist.filter(h => /RE_OBSERV|RESOLVED|ESCALATED|RECOVER|CLOSED/.test(h.state)).map(h => `<li>${e(hhmmss(h.t))} ${e(UI.status(h.state))}${h.note ? ` · ${e(W().rule(UI.logText(h.note)))}` : ''}</li>`).join('')}</ul>`, { open: true }));
      if (rec != null && !b.series) ctx.gaps.push({ key: 'reobs', text: '재관측은 마지막에 잰 값 하나만 남습니다. 지켜본 동안의 값 흐름은 처리 건에 저장되지 않습니다 (센서 기록 DB 에는 있음).' });
    } else if (w.tool === 'plant:test-run') {
      const tr = out.test_run || v.test_run || null;
      const settle = b.rows.find(r => r.job === 'TEST_RUN_STARTED');
      verdict = tr ? tr.passed : null;
      sentence = tr ? `${settle && settle.data && settle.data.plan ? `안정될 때까지 기다린 뒤(${virtual(settle.data.plan)}) ` : ''}${(tr.readings || []).length}개 값을 재어 ${tr.passed ? '모두 기준 안 — 통과' : '기준 밖 값이 있어 미달'}로 판정했습니다.${tr.counter && tr.counter.detail ? ` ${W().text(tr.counter.detail)}.` : ''}`
        : settle ? `시운전 — 안정될 때까지 기다리는 중입니다 (${virtual(settle.data.plan)}).` : '시운전을 준비하는 중입니다.';
      (tr && tr.readings || []).forEach(r => chips.push(chip(`${W().fieldName(String(r.tag).toLowerCase())} ${r.value == null ? '모름' : W().num(r.value)} ${W().sym(r.op)} ${W().num(r.limit)}${W().unit(String(r.tag).toLowerCase()) ? ' ' + W().unit(String(r.tag).toLowerCase()) : ''}`, r.ok ? 'success' : 'danger')));
      if (tr) sections.push(sec('잰 값과 기준', `<div class="cr-scroll"><table class="cr-table"><thead><tr><th>값</th><th>잰 값</th><th>기준</th><th>판정</th></tr></thead><tbody>${(tr.readings || []).map(r => `<tr><td>${named(W().fieldName(String(r.tag).toLowerCase()), r.tag)}</td><td class="num">${r.value == null ? '모름' : e(W().value(String(r.tag).toLowerCase(), r.value))}</td><td class="num">${e(W().sym(r.op))} ${e(W().num(r.limit))}</td><td>${UI.chipText(r.ok ? '통과' : '미달', r.ok ? 'success' : 'danger')}</td></tr>`).join('')}</tbody></table></div>${tr.at ? `<p class="muted">잰 시각 ${e(hhmmss(tr.at))}</p>` : ''}`, { open: true }));
    } else {   // 입고 확인
      icon = 'receipt';
      const gr = out.goods_receipt || v.goods_receipt || null;
      const waitR = b.rows.find(r => r.job === 'RECEIPT_WAIT'), delayR = b.rows.find(r => r.job === 'RECEIPT_DELAYED');
      verdict = gr ? true : w.status === 'CANCELLED' ? false : null;
      sentence = gr ? `입고 예정까지 기다린 뒤${waitR ? `(${virtual(waitR.data.plan)})` : ''} 입고 · 검수 ${gr.ref || ''}${W().josa(gr.ref || '검수', '을/를')} 기록했습니다 — ${W().text(gr.detail || '')}.`
        : w.status === 'CANCELLED' ? `입고를 기다리던 중 ${delayR ? '공급사가 납기를 늦췄고, ' : ''}정해 둔 기한이 먼저 와서 멈췄습니다. 입고는 기록되지 않았습니다.`
        : waitR ? `입고 예정까지 기다리는 중입니다 (${virtual(waitR.data.plan)}${delayR ? ', 공급사 지연 반영' : ''}).` : '입고를 확인하는 중입니다.';
      if (waitR) chips.push(chip(`리드타임 ${waitR.data.plan.lead_d != null ? waitR.data.plan.lead_d + '일' : ''}`));
      if (delayR) chips.push(chip(`공급사 지연 ${delayR.data.plan.delay_d}일`, 'warning'));
      if (gr) chips.push(chip(gr.ref || '입고', 'success'));
      if (w.status === 'CANCELLED') { chips.push(chip('입고 없음', 'danger')); b.stopNote = '기한이 먼저 와서 멈춤'; }
    }
    if (b.rows.length) sections.push(sec(`시스템 기록 ${b.rows.length}줄`, sysRowsHtml(b), { open: b.live }));
    sections.push(sec('결과 값 원문', rawBlock(out), { raw: true }));
    return Object.assign(b, { type: 'check', lane: 'system', icon, title: b.name, actor: /^(incident:reobserve|plant:test-run)$/.test(w.tool) ? '설비 · 센서' : 'ERP', sentence, chips, sections, verdict,
      state: w.status === 'DONE' && verdict === false ? 'bad' : undefined, now: b.live ? '확인하는 중' : '', ids: [w.tool] });
  }

  // "토출 압력 182 bar — 기준 ‘토출 압력 ≥ 165 bar’ 안이라 " · 잰 값 · 기준을 모르면 그 말을 빼고 판정만
  function reobsBasis(valTxt, crit, rec) {
    const basis = [valTxt, crit ? `기준 ‘${W().criterion(crit)}’` : ''].filter(Boolean).join(' — ');
    return basis ? `${basis}${rec ? ' 안이라 ' : ' 밖이라 '}` : '';
  }
  const SIDE = { '<': '아래', '<=': '이하', '>': '위', '>=': '이상' };
  function seriesSentence(x) {
    const tag = String(x.tag || '').toLowerCase(), u = W().unit(tag);
    const span = x.from && x.to ? fmtMs(ts(x.to) - ts(x.from)) : '';
    return `${span ? span + ' 동안 ' : ''}${W().fieldName(tag)} ${W().num(x.first)}→${W().num(x.last)}${u ? ' ' + u : ''}, 기준 ${W().num(x.limit)}${u ? ' ' + u : ''} ${SIDE[x.op] || ''} ${Math.round((x.inside_share || 0) * 100)} %`;
  }
  // 작은 선 그림: 값 흐름 + 기준선(점선) + 마지막 점
  function seriesHtml(x) {
    const pts = (x.points || []).filter(p => Number.isFinite(+p.v));
    const W0 = 280, H0 = 64, pad = 4;
    const vals = pts.map(p => +p.v).concat([+x.limit]);
    let lo = Math.min(...vals), hi = Math.max(...vals); if (hi - lo < 1e-6) { hi += 1; lo -= 1; }
    const t0 = ts(pts[0].t), t1 = ts(pts[pts.length - 1].t) || t0 + 1;
    const X = t => pad + (W0 - 2 * pad) * ((ts(t) - t0) / Math.max(1, t1 - t0));
    const Y = v => pad + (H0 - 2 * pad) * (1 - (v - lo) / (hi - lo));
    const line = pts.map((p, i) => `${i ? 'L' : 'M'}${X(p.t).toFixed(1)},${Y(+p.v).toFixed(1)}`).join(' ');
    const last = pts[pts.length - 1], tag = String(x.tag || '').toLowerCase(), u = W().unit(tag);
    const svg = `<svg class="cr-spark" viewBox="0 0 ${W0} ${H0}" role="img" aria-label="${e(seriesSentence(x))}">
      <line x1="${pad}" x2="${W0 - pad}" y1="${Y(+x.limit).toFixed(1)}" y2="${Y(+x.limit).toFixed(1)}" class="lim"/>
      <path d="${line}" class="val"/><circle cx="${X(last.t).toFixed(1)}" cy="${Y(+last.v).toFixed(1)}" r="3" class="${x.inside_last ? 'ok' : 'bad'}"/></svg>`;
    return `<div class="cr-series">${svg}<dl class="cr-kv"><div><dt>처음 → 마지막</dt><dd class="num">${e(W().num(x.first))} → ${e(W().num(x.last))}${u ? ' ' + e(u) : ''}</dd></div>
      <div><dt>가장 낮음 · 높음</dt><dd class="num">${e(W().num(x.min))} · ${e(W().num(x.max))}${u ? ' ' + e(u) : ''}</dd></div>
      <div><dt>기준</dt><dd>${e(W().fieldName(tag))} ${e(W().sym(x.op))} ${e(W().num(x.limit))}${u ? ' ' + e(u) : ''} <span class="muted">(점선)</span></dd></div>
      <div><dt>기준 안에 있던 몫</dt><dd class="num">${Math.round((x.inside_share || 0) * 100)} %</dd></div>
      <div><dt>잰 값 수</dt><dd class="num">${e(x.samples)}개${x.step_s ? ` <span class="muted">(점 하나 ≈ ${e(W().num(x.step_s))}초 평균)</span>` : ''}</dd></div>
      ${x.extensions ? `<div><dt>관측 연장</dt><dd>${e(x.extensions)}회</dd></div>` : ''}</dl></div>`;
  }

  /* ---------------------------------------------------------------- 타이머 (정해 둔 시간이 지나 울림) */
  function timerStep(ctx, b) {
    const ev = ctx.evDefs[b.w.activity_id] || {};
    const host = ev.attachedTo ? UI.flowName((ctx.acts[ev.attachedTo] || {}).name || ev.attachedTo) : '';
    const dur = isoDur(ev.timer || ev.duration || ev.timerDuration || '');
    return Object.assign(b, { type: 'timer', lane: 'system', icon: 'timer', title: b.name, actor: '처리 엔진 타이머', t0: b.w.end_date || b.w.start_date,
      sentence: b.w.status === 'DONE' ? `${host ? `‘${host}’에 걸어 둔 ` : ''}기한${dur ? `(${dur})` : ''}이 지나 ‘${b.name}’${W().josa(b.name, '이/가')} 울렸습니다${ev.cancelActivity === false ? ' — 원래 일은 계속됩니다' : host ? ` — ‘${host}’${W().josa(host, '은/는')} 멈춥니다` : ''}.` : `‘${b.name}’ 기한을 재는 중입니다.`,
      chips: dur ? [chip(`기한 ${dur}`, 'warning')] : [], sections: [], ids: [b.w.activity_id] });
  }

  /* ---------------------------------------------------------------- 결과 보고 */
  function reportStep(ctx, b) {
    const w = b.w, rep = (w.output || {}).result_report || null;
    const vv = rep && window.hydResultReport ? hydResultReport.fromValues({ result_report: rep }) : null;
    const tone = vv ? (vv.verdict === 'ok' ? 'success' : vv.verdict === 'fail' ? 'danger' : 'neutral') : 'neutral';
    const chips = rep ? [chip(rep.outcome || (vv && vv.label) || '결과', tone)].concat((rep.values || []).map(x => chip(`${W().text(x.name)} ${W().num(x.value)}${x.unit ? ' ' + x.unit : ''}${x.limit != null ? ` (기준 ${x.limit})` : ''}`, x.ok === false ? 'danger' : x.ok === true ? 'success' : 'neutral'))) : [];
    const sections = [];
    if (rep) {
      sections.push(sec('보고 내용', `<p><b>${e(W().text(rep.title || ''))}</b></p>${rep.summary ? `<p>${e(W().text(rep.summary))}</p>` : ''}
        ${Object.keys(rep.refs || {}).length ? `<p class="muted">남긴 번호 ${Object.entries(rep.refs).map(([k, r]) => `${e({ work_order: '작업지시', purchase_order: '발주', goods_receipt: '입고', mcp_receipt: '도구 영수증' }[k] || W().fieldName(k))} ${e(r)}`).join(' · ')}</p>` : ''}
        ${rep.incident_closed != null ? `<p class="muted">사건 ${rep.incident_closed ? '닫음' : '그대로'} · 담당자 알림 보냄</p>` : ''}`, { open: true }));
      const facts = Object.entries(rep.facts || {}).filter(([, x]) => x != null && typeof x !== 'object');
      if (facts.length) sections.push(sec('보고에 실은 값', kvTable(facts.map(([k, x]) => [W().fieldName(k) === k.replace(/_/g, ' ') ? (UI.terms['var.' + k] || k) : W().fieldName(k), k === 'approved_role' || k === 'approved_by' ? W().who(x) : k === 'approved_supplier' ? supplierName(ctx, x) : W().value(k, x), k]))));
    }
    sections.push(sec('결과 보고 원문', rawBlock(rep), { raw: true }));
    return Object.assign(b, { type: 'report', lane: 'system', icon: 'flag', title: b.name, actor: '처리 엔진 → 담당자 알림',
      sentence: rep ? `${W().text(rep.title || '결과')}: ${rep.outcome || ''}${rep.summary ? ' — ' + W().text(rep.summary) : ''}` : '결과를 정리하는 중입니다.', chips, sections,
      state: rep && vv && vv.verdict === 'fail' ? 'bad' : undefined, ids: [w.tool] });
  }
  // 결과 보고 단계가 없는 흐름: 처리 건 값으로 결과를 만든다(끝난 경우만)
  function endStep(ctx) {
    const { inst, v } = ctx;
    const rep = window.hydResultReport ? hydResultReport.fromValues(v) : null;
    const end = inst.end_event ? (UI.terms['val.' + String(inst.end_event).replace(/^ev:/, '')] || UI.flowName(String(inst.end_event).replace(/^ev:/, ''))) : '';
    const label = rep ? (rep.label || (rep.verdict === 'ok' ? '정상' : rep.verdict === 'fail' ? '미달' : '확인 결과')) : UI.status(inst.status);
    return { key: 'end', type: 'end', lane: 'system', icon: 'flag', title: '끝', actor: '처리 엔진', t0: inst.end_date, t1: inst.end_date,
      sentence: `${rep && rep.title ? rep.title + ': ' : ''}${label}${rep && rep.summary ? ' — ' + W().text(rep.summary) : ''}${end ? ` (끝: ${end})` : ''}.`,
      chips: [chip(label, rep && rep.verdict === 'ok' ? 'success' : rep && rep.verdict === 'fail' ? 'danger' : 'neutral')], sections: [], state: rep && rep.verdict === 'fail' ? 'bad' : 'ok' };
  }

  /* ---------------------------------------------------------------- 기록에 없는 것 (블랙박스 점검) */
  function gapsOf(ctx, steps) {
    const G = ctx.gaps;
    const tools = steps.flatMap(s => (s.rows || []).filter(r => r.kind === 'tool'));
    const cut = tools.filter(r => r.status === 'warn' && !(r.full && r.full.stored)), blocked = tools.filter(r => r.status === 'blocked');
    if (cut.length) G.push({ key: 'cut', strong: true, text: `도구 결과 ${cut.length}건이 너무 커서 잘렸습니다 (${[...new Set(cut.map(r => W().toolName(r.tool)))].join(', ')}). AI 일꾼은 그 결과를 다 보지 못했고, 원래 결과는 워커 PC 의 임시 파일에만 있어 처리 건에 남지 않습니다. 그 뒤 판단은 판단 엔진이 저장한 값(아래 대안 · 데이터)으로 확인할 수 있습니다.` });
    if (blocked.length) G.push({ key: 'blocked', text: `안전 장치가 막은 명령 ${blocked.length}건 — 실행되지 않았고, 막힌 명령의 결과는 없습니다.` });
    const startedData = s => ((ctx.byTodo.get(s.key) || []).find(x => x.event_type === 'task_started') || {}).data || {};
    const skillsRecorded = steps.filter(s => s.type === 'agent').every(s => Array.isArray(startedData(s).skills));
    if (steps.some(s => s.type === 'agent')) {
      if (ctx.read.agents.state === 'error') G.push({ key: 'agents', strong: true, text: `AI 일꾼 설정(목표 · 스킬 · 쓸 수 있는 도구)을 읽지 못했습니다 — ${ctx.read.agents.error}. 다시 읽는 중입니다.` });
      if (!skillsRecorded && !tools.some(r => r.tool === 'Skill')) G.push({ key: 'skill', strong: true, text: '어떤 스킬(SKILL.md)을 실제로 읽었는지는 처리 건에 기록되지 않습니다. 화면의 스킬은 AI 일꾼의 지금 설정이라, 처리 뒤 설정을 바꾸면 달라 보일 수 있습니다.' });
      G.push({ key: 'think', text: 'AI 모델 안쪽의 생각은 기록되지 않습니다. 남는 것은 AI 일꾼이 쓴 말 · 부른 도구 · 받은 결과 · 낸 결과 값입니다. (모델 사용량 줄은 일부러 숨김)' });
      steps.filter(s => s.type === 'agent' && !(s.rows || []).length && !s.live).forEach(s => G.push({ key: 'noev:' + s.key, strong: true, text: `‘${s.title}’ 단계는 도구 호출 기록이 없습니다 (결과 값만 남음).` }));
    }
    const start = steps[0];
    if (start && start.pressed && !(start.rows || []).some(r => r.kind === 'sys')) G.push({ key: 'button', strong: true, text: '수업 버튼 기록(누른 사람 · 시각)이 처리 건 기록에 없습니다 — 시작 경보의 근거 값에만 남았습니다.' });
    if (start && (start.rows || []).some(r => r.kind === 'error')) G.push({ key: 'link', strong: true, text: '수업 버튼 누름을 이 처리 건에 붙이지 못했습니다(시작 단계의 오류 줄). 누가 · 언제 눌렀는지는 감사 기록에만 있습니다.' });
    if (ctx.read.people.state === 'error' && steps.some(s => s.lane === 'person' && s.type !== 'start')) G.push({ key: 'people', strong: true, text: `사람 이름 목록을 읽지 못해 승인 · 입력한 사람이 원래 이름(id)으로 보일 수 있습니다 — ${ctx.read.people.error}` });
    if (steps.some(s => s.type === 'approve' && s.w && s.w.status === 'DONE')) G.push({ key: 'who', text: '승인한 사람 이름은 승인 화면에 입력한 값입니다. 로그인으로 본인 확인을 하지 않습니다.' });
    const pg = ctx.view.events_page;
    if (pg ? pg.has_more && !ctx.olderDone : (ctx.view.events || []).length >= EVENTS_WINDOW) G.push({ key: 'cap', strong: true, text: pg ? '이 처리 건은 기록이 많아 가장 최근 줄부터 받았습니다. 맨 위 "이전 기록 더 보기"로 앞쪽 기록을 더 받을 수 있습니다.' : `이 처리 건은 기록이 많아 가장 최근 ${W().num(EVENTS_WINDOW)}줄만 받았습니다. 앞쪽 도구 호출 일부가 빠졌을 수 있습니다.` });
    if (ctx.read.decision.state === 'error') G.push({ key: 'dec', strong: true, text: `판단 기록을 읽지 못해 대안 · 가져온 데이터 · 지식 경로를 보이지 못했습니다 — ${ctx.read.decision.error}` });
    if (ctx.d && !(ctx.d.provenance || []).length) G.push({ key: 'prov', text: '판단에 가져온 데이터의 출처 목록(provenance)이 없습니다. 도구 호출의 받은 값으로만 확인할 수 있습니다.' });
    if (steps.some(s => s.type === 'system' && /메일/.test(s.sentence || ''))) G.push({ key: 'mail', text: '메일은 보냄 결과(성공)까지만 기록됩니다. 받는 사람이 읽었는지는 알 수 없습니다 (수업 메일함 Inbucket 에서 확인).' });
  }

  /* ================================================================ HTML 조각 */
  function sec(title, body, { open = false, raw = false, cls = '' } = {}) {
    if (!body) return '';
    return { title, body, open, raw, cls };
  }
  function kvTable(rows) {
    if (!rows.length) return '';
    return `<dl class="cr-kv">${rows.map(([k, x, id]) => `<div><dt>${e(k)}${W().id(id)}</dt><dd class="num">${e(x)}</dd></div>`).join('')}</dl>`;
  }
  function pretty(x) {
    if (x == null) return '';
    let o = x; if (typeof x === 'string') { try { o = JSON.parse(x); } catch (_) { return UI.clean(x).slice(0, RAW_MAX_CHARS); } }
    return UI.clean(JSON.stringify(o, null, 2)).slice(0, RAW_MAX_CHARS);
  }
  const rawBlock = x => x == null || (typeof x === 'object' && !Object.keys(x).length) ? '' : `<pre class="cr-pre">${e(pretty(x))}</pre>`;
  /* A161-G2: 큰 도구 결과 원문 — GET /api/event-payloads/{ref}?offset&limit 로 나눠 받아 붙이고, 다 받은 JSON 은 키마다 접어 보인다 */
  const PAY = new Map();
  const PAY_CHUNK = 60000;
  function fullHtml(fo, k) {
    const src = fo.source === 'cli_saved_file' ? 'AI 일꾼이 받지 못한 큰 결과(CLI 가 임시 파일로 뺌)' : '화면 기록에서 잘린 결과';
    const head = `<div class="cr-full"><div class="cr-full-h"><b>원문</b> <span class="muted">${e(src)}${fo.chars != null ? ` · ${e(W().num(fo.chars))}자` : ''}${fo.cut ? ' · 보관 한도에서 잘림' : ''}${fo.content_type ? ` · ${e(fo.content_type === 'json' ? 'JSON' : '글')}` : ''}</span>${fo.sha256 ? `<code class="cr-id" title="sha256">${e(String(fo.sha256).slice(0, 12))}</code>` : ''}</div>`;
    if (!fo.stored || !fo.ref) return head + `<p class="cr-gapline">원문을 보관하지 못했습니다: ${e(fo.error || '이유가 기록되지 않음')}</p></div>`;
    const st = PAY.get(fo.ref);
    const summary = fo.summary ? `<pre class="cr-pre small">${e(String(fo.summary))}</pre>` : '';
    if (!st) return head + summary + `<button type="button" class="btn small" data-cr-payload="${e(fo.ref)}">원문 보기</button></div>`;
    if (st.error) return head + summary + `<p class="cr-gapline">원문을 읽지 못했습니다: ${e(st.error)}</p><button type="button" class="btn small" data-cr-payload="${e(fo.ref)}">다시 읽기</button></div>`;
    const done = st.next == null;
    let body = '';
    if (done && fo.content_type === 'json') { try { body = jsonFold(JSON.parse(st.text), k); } catch (_) { body = ''; } }
    if (!body) body = `<pre class="cr-pre">${e(st.text)}</pre>`;
    return head + `<p class="muted">받은 만큼 ${e(W().num(st.text.length))} / ${e(W().num(st.total || fo.chars || 0))}자</p>${body}${st.loading ? '<p class="muted">받는 중…</p>' : !done ? `<button type="button" class="btn small" data-cr-payload="${e(fo.ref)}" data-offset="${e(st.next)}">다음 부분 더 보기</button>` : ''}</div>`;
  }
  // JSON 을 키마다 접기(두 단계까지), 배열은 건수 · 짧은 값은 한 줄
  function jsonFold(v, k, depth = 0) {
    const small = x => x == null || typeof x !== 'object';
    if (small(v)) return `<code>${e(JSON.stringify(v))}</code>`;
    const entries = Array.isArray(v) ? v.map((x, i) => [i, x]) : Object.entries(v);
    if (depth >= 2) return `<pre class="cr-pre">${e(JSON.stringify(v, null, 2).slice(0, 20000))}</pre>`;
    return `<ul class="cr-json">${entries.slice(0, 200).map(([key, x]) => small(x) ? `<li><span class="cr-jk">${e(key)}</span> <code>${e(String(JSON.stringify(x)).slice(0, 300))}</code></li>`
      : `<li><details data-k="${e(k + ':j:' + depth + ':' + key)}"><summary><span class="cr-jk">${e(key)}</span> <span class="muted">${Array.isArray(x) ? x.length + '건' : '{' + Object.keys(x).length + '칸}'}</span></summary>${jsonFold(x, k + ':' + key, depth + 1)}</details></li>`).join('')}${entries.length > 200 ? `<li class="muted">… ${entries.length - 200}개 더</li>` : ''}</ul>`;
  }
  async function loadPayload(ref, offset) {
    const st = PAY.get(ref) || { text: '', next: 0 };
    if (st.loading) return;
    st.loading = true; st.error = null; PAY.set(ref, st); redrawAll();
    try {
      const r = await getJ(`${API.process}/api/event-payloads/${encodeURIComponent(ref)}?offset=${encodeURIComponent(offset || 0)}&limit=${PAY_CHUNK}`);
      st.text = (offset ? st.text : '') + (r.content || ''); st.next = r.next_offset == null ? null : r.next_offset; st.total = r.chars;
    } catch (err) { st.error = err.status === 404 ? '보관된 원문이 없습니다 (지워졌거나 다른 처리 건)' : err.message; }
    finally { st.loading = false; redrawAll(); }
  }
  function redrawAll() { mounted.forEach(C => C.draw && C.draw(true)); }

  function toolListHtml(rows, live, stepKey) {
    const minor = rows.filter(r => r.minor).length;
    const items = rows.map(r => {
      const time = `<time>${e(hhmmss(r.t0))}</time>`;
      if (r.kind === 'note') return `<li class="cr-r note">${time}<span class="cr-rm">${icon('note')}</span><div><q>${e(r.text.slice(0, NOTE_MAX_CHARS))}${r.text.length > NOTE_MAX_CHARS ? '…' : ''}</q></div></li>`;
      if (r.kind === 'skill') return `<li class="cr-r skill">${time}<span class="cr-rm ok">${icon('file')}</span><div><b>스킬 읽음</b> ${e(r.data.skill)} · ${e(r.data.file || '')} <span class="muted">(${e(W().toolName(r.data.via))})</span></div></li>`;
      if (r.kind === 'file') return `<li class="cr-r minor">${time}<span class="cr-rm">${icon('file')}</span><div>결과 파일 ${e(r.text)}</div></li>`;
      if (r.kind === 'sys') return `<li class="cr-r sys">${time}<span class="cr-rm">${icon('system')}</span><div><b>${e(r.text)}</b>${sysDetail(r)}</div></li>`;
      if (r.kind === 'error') return `<li class="cr-r err">${time}<span class="cr-rm">${icon('warn')}</span><div><b>${e(r.text)}</b>${UI.fold('원문', `<pre class="cr-pre">${e(pretty(r.data))}</pre>`, { cls: 'small' })}</div></li>`;
      const sys = W().toolSystem(r.tool);
      const ask = W().ask(r.tool, r.input);
      const fo = r.full;
      const got = r.status === 'running' ? '' : fo && fo.stored && fo.summary ? `원문 ${W().num(fo.original_chars || fo.chars || 0)}자를 따로 보관 — ${String(fo.summary).split('\n')[0]}`
        : fo && fo.stored === false ? `원문을 보관하지 못함 — ${fo.error || '이유 모름'}` : r.status === 'warn' ? '결과가 너무 커서 잘림 — 받은 내용 없음' : r.status === 'blocked' ? '안전 장치가 막아 실행 안 됨' : W().got(r.tool, r.output);
      const mark = r.status === 'running' ? (live && TR() ? TR().spinner('sm') : icon('event')) : icon(r.status === 'ok' ? 'check' : r.status === 'fail' ? 'x' : 'warn');
      const dur = r.t0 && r.t1 ? `<span class="cr-dur">${e(fmtMs(ts(r.t1) - ts(r.t0)))}</span>` : '';
      const full = fo ? fullHtml(fo, stepKey + ':' + r.key) : '';
      const io = full + `${r.input != null ? `<div class="cr-io"><span>물은 원문</span><pre class="cr-pre">${e(pretty(r.input))}</pre></div>` : ''}${r.output != null ? `<div class="cr-io"><span>받은 원문</span><pre class="cr-pre">${e(pretty(r.output))}</pre></div>` : ''}`;
      return `<li class="cr-r tool ${e(r.status)}${r.minor ? ' minor' : ''}">${time}<span class="cr-rm ${e(r.status)}">${mark}</span><div>
        <details class="cr-call" data-k="${e(stepKey + ':' + r.key)}"><summary><b>${e(W().toolName(r.tool))}</b>${sys ? `<span class="cr-sys">${e(sys)}</span>` : ''}${r.badge ? UI.chipText(r.badge, r.status === 'fail' ? 'danger' : 'warning') : ''}${dur}${W().id(r.tool)}
        <div class="cr-qa">${ask ? `<span class="cr-q">물음</span> ${e(ask)}` : ''}${fo && fo.stored ? ` ${UI.chipText('원문 보관', 'success')}` : ''}${got || r.status !== 'running' ? `<br><span class="cr-a">받음</span> ${e(got || '결과 받음 (펼쳐서 보기)')}` : ''}</div></summary>${io}</details></div></li>`;
    }).join('');
    return `${minor ? `<label class="cr-minor-toggle"><input type="checkbox" data-cr-minor> 보조 작업 ${minor}건도 보기 <span class="muted">(쓸 도구 불러오기 · 파일 쓰기 · 명령 실행)</span></label>` : ''}<ol class="cr-rows">${items}</ol>`;
  }
  function sysDetail(r) {
    const d = r.data || {};
    if (d.plan) return ` <span class="muted">${e(d.plan.label || '')} ${e(virtual(d.plan))}${d.plan.source ? ` · ${e(W().text(d.plan.source))}` : ''}</span>`;
    if (d.notice) return ` <span class="muted">${e(W().text(d.notice))}</span>`;
    if (d.by) return ` <span class="muted">${e(W().who(d.by))}${d.role ? ' · ' + e(W().who(d.role)) : ''}</span>`;
    if (d.readings) return ` <span class="muted">${e(d.passed ? '통과' : '미달')}</span>`;
    if (d.receipt) return ` <span class="muted">${e(d.receipt.ref || '')} ${e(W().text(d.receipt.detail || ''))}</span>`;
    if (d.report) return ` <span class="muted">${e(d.report.outcome || '')}</span>`;
    return '';
  }

  const STATE_MARK = { ok: ['check', 'ok', '끝남'], bad: ['warn', 'bad', '기준 밖'], fail: ['x', 'fail', '실패'], stop: ['x', 'stop', '멈춤'], wait: ['pause', 'wait', '기다림'], idle: ['event', 'idle', '아직'] };
  function stateHtml(s) {
    if (s.state === 'run') return `<span class="cr-state run">${TR() ? TR().spinner('sm') : ''}<span>진행 중</span></span>`;
    const [k, cls, label] = STATE_MARK[s.state] || STATE_MARK.idle;
    return `<span class="cr-state ${cls}">${icon(k)}<span>${s.state === 'stop' && s.stopNote ? e(s.stopNote) : label}</span></span>`;
  }
  function stepHtml(s, i, n, open) {
    const dur = s.t0 && s.t1 && s.type !== 'start' && s.type !== 'timer' ? fmtMs(ts(s.t1) - ts(s.t0)) : '';
    const liveDur = s.live && s.t0 && !s.t1 ? `<span class="cr-dur live" data-since="${e(s.t0)}">${e(fmtMs(Date.now() - ts(s.t0)))}</span>` : '';
    const chips = (s.chips || []).filter(c => c && c.label).map(c => `<span class="chip tone-${c.tone} sm">${e(c.label)}</span>`).join('');
    const secs = (s.sections || []).filter(Boolean);
    const body = secs.map((x, j) => x.raw ? `<details class="cr-sec raw" data-k="${e(s.key + ':raw' + j)}"><summary>${e(x.title)}</summary>${x.body}</details>`
      : `<details class="cr-sec ${x.cls || ''}" data-k="${e(s.key + ':' + j)}" ${x.open ? 'data-open-default' : ''}><summary>${e(x.title)}</summary><div class="cr-sec-body">${x.body}</div></details>`).join('');
    const next = i < n - 1 ? `<button type="button" class="btn small ghost cr-next" data-cr-next="${i + 1}">다음 단계 ▸</button>` : '';
    return `<div class="cr-rail lane-${e(s.lane)}"><span class="cr-dot">${icon(s.icon)}</span></div>
      <div class="cr-card">
        <button type="button" class="cr-head" data-cr-toggle aria-expanded="${open}">
          <span class="cr-no">${i + 1}</span>
          <span class="cr-title"><b>${e(s.title)}</b><span class="cr-actor lane-${e(s.lane)}">${e(LANE[s.lane])} · ${e(s.actor || '')}</span>${(s.ids || []).filter(Boolean).map(id => W().id(id)).join('')}</span>
          <span class="cr-meta"><time title="${e(s.t0 ? UI.dateTime(s.t0) : '')}">${e(s.t0 ? hhmmss(s.t0) : '')}</time>${dur ? `<span class="cr-dur">${e(dur)}</span>` : liveDur}${stateHtml(s)}</span>
        </button>
        <p class="cr-sentence">${e(s.sentence || '')}</p>
        ${s.live && s.now ? `<p class="cr-now">${TR() ? TR().spinner('sm') : ''}<span class="tr-shimmer">${e(s.now)}</span></p>` : ''}
        ${chips ? `<div class="cr-chips">${chips}</div>` : ''}
        ${body ? `<div class="cr-detail">${body}${next}</div>` : `<div class="cr-detail">${next}</div>`}
      </div>`;
  }
  function headHtml(m) {
    const inst = m.inst, rep = m.outcome;
    const el = m.t0 ? (m.t1 ? fmtMs(ts(m.t1) - ts(m.t0)) : null) : null;
    const tone = m.running ? 'accent' : rep && rep.verdict === 'ok' ? 'success' : rep && rep.verdict === 'fail' ? 'danger' : inst.status === 'COMPLETED' ? 'success' : 'neutral';
    const label = m.running ? '진행 중' : rep ? (rep.label || (rep.verdict === 'ok' ? '정상' : rep.verdict === 'fail' ? '미달' : '끝')) : UI.status(inst.status);
    const people = m.steps.filter(s => s.lane === 'person' && s.type !== 'start').length, ai = m.steps.filter(s => s.lane === 'agent').length, sys = m.steps.filter(s => s.lane === 'system' && s.type !== 'start').length;
    const strip = m.steps.map((s, i) => `<button type="button" class="cr-pill lane-${e(s.lane)} st-${e(s.state)}" data-cr-go="${i}" title="${e(s.sentence || '')}">${icon(s.icon)}<span>${e(s.title)}</span></button>`).join('<span class="cr-pill-arrow" aria-hidden="true">›</span>');
    return `<div class="cr-summary">
      <div class="cr-sum-row"><span class="chip tone-${tone}">${e(label)}</span><span>시작 <b>${e(m.t0 ? UI.dateTime(m.t0) : '–')}</b></span><span>걸린 시간 <b ${el ? '' : `data-since="${e(m.t0 || '')}"`}>${e(el || (m.t0 ? fmtMs(Date.now() - ts(m.t0)) : '–'))}</b></span>
        <span>단계 <b>${m.steps.length}</b></span><span>AI 도구 호출 <b>${m.tools}</b></span></div>
      <div class="cr-legend"><span class="lane-person">사람 ${people}</span><span class="lane-agent">AI 일꾼 ${ai}</span><span class="lane-system">시스템 ${sys}</span>
        <span class="cr-tools-bar"><button type="button" class="btn small ghost" data-cr-all>${'모두 펼치기'}</button><label class="cr-ids"><input type="checkbox" data-cr-ids ${W().showIds ? 'checked' : ''}> 원래 이름(id) 보기</label></span></div>
      <nav class="cr-strip" aria-label="처리 순서">${strip}</nav>
    </div>`;
  }
  function gapsHtml(m) {
    if (!m.gaps.length) return '';
    const uniq = [...new Map(m.gaps.map(g => [g.key, g])).values()].sort((a, b) => (b.strong ? 1 : 0) - (a.strong ? 1 : 0));
    return UI.fold(`기록에 없는 것 <span class="chip tone-warning sm">${uniq.length}</span> <span class="muted">— 이 처리 건에서 화면이 보여 줄 수 없는 부분</span>`,
      `<ul class="cr-gaps">${uniq.map(g => `<li class="${g.strong ? 'strong' : ''}">${e(g.text)}</li>`).join('')}</ul>`, { cls: 'cr-gapfold' });
  }

  /* ================================================================ 컨트롤러: mount(host) → { update(view), ingest(event) } */
  // 같은 목록은 처리 기록 여럿이 같이 쓴다(1분 보관). 실패는 던져서 처리 기록이 "기록에 없는 것"에 사유를 보인다
  const SHARED = {};
  async function sharedList(key) {
    const c = SHARED[key] || (SHARED[key] = { at: 0, rows: null });
    if (c.rows && Date.now() - c.at < SHARED_TTL_MS) return c.rows;
    c.rows = await getJ(API.process + SHARED_LISTS[key]); c.at = Date.now();
    return c.rows;
  }
  const mounted = new Set();
  function mount(host) {
    const C = { host, view: null, live: new Map(), ext: {}, open: new Set(), userTouched: new Set(), raf: 0, fetching: false, pid: null };
    host.classList.add('cr');
    host.innerHTML = '<div data-cr-head></div><div data-cr-older></div><ol class="cr-story" data-cr-steps></ol><div data-cr-gaps></div>';
    host.addEventListener('click', ev => {
      const t = ev.target;
      const tog = t.closest('[data-cr-toggle]');
      if (tog && host.contains(tog)) { const li = tog.closest('[data-key]'); setOpen(li, !li.classList.contains('open'), true); return; }
      const go = t.closest('[data-cr-go],[data-cr-next]');
      if (go) { const i = +(go.dataset.crGo ?? go.dataset.crNext); const li = host.querySelectorAll('[data-cr-steps] > li')[i]; if (li) { setOpen(li, true, true); li.scrollIntoView({ block: 'start', behavior: 'smooth' }); li.querySelector('[data-cr-toggle]')?.focus({ preventScroll: true }); } return; }
      const pay = t.closest('[data-cr-payload]');
      if (pay) { loadPayload(pay.dataset.crPayload, +(pay.dataset.offset || 0)); return; }
      if (t.closest('[data-cr-older-btn]')) { loadOlder(); return; }
      if (t.closest('[data-cr-all]')) { const lis = [...host.querySelectorAll('[data-cr-steps] > li')]; const openAll = lis.some(li => !li.classList.contains('open')); lis.forEach(li => setOpen(li, openAll, true)); t.closest('[data-cr-all]').textContent = openAll ? '모두 접기' : '모두 펼치기'; }
    });
    host.addEventListener('change', ev => {
      if (ev.target.matches('[data-cr-ids]')) { W().setShowIds(ev.target.checked); C.lastHtml = {}; draw(true); }
      if (ev.target.matches('[data-cr-minor]')) ev.target.closest('.cr-sec-body, .cr-detail')?.classList.toggle('show-minor', ev.target.checked);
    });
    function setOpen(li, open, user) {
      if (!li) return;
      li.classList.toggle('open', open); li.querySelector('[data-cr-toggle]')?.setAttribute('aria-expanded', String(open));
      if (open) C.open.add(li.dataset.key); else C.open.delete(li.dataset.key);
      if (user) C.userTouched.add(li.dataset.key);
      if (open) li.querySelectorAll('details[data-open-default]:not([data-seen])').forEach(d => { d.open = true; d.dataset.seen = '1'; });
    }
    C.update = view => {
      if (!view || !view.instance) return;
      if (C.pid !== view.instance.proc_inst_id) { C.pid = view.instance.proc_inst_id; C.live.clear(); C.ext = {}; C.open.clear(); C.userTouched.clear(); C.lastHtml = {}; C.olderBefore = undefined; C.olderCount = 0; C.olderErr = null; }
      C.view = view; fetchExt(); schedule();
    };
    C.ingest = ev => {
      if (!ev || !ev.id || C.live.has(ev.id) || !C.pid || (ev.proc_inst_id && ev.proc_inst_id !== C.pid)) return;
      C.live.set(ev.id, ev); if (C.live.size > LIVE_MAX_ROWS) C.live.delete(C.live.keys().next().value);
      schedule();
    };
    // A161-G4: 처리 건 화면은 최신 기록 한 창만 준다 — 더 오래된 기록은 /api/events?before=… 로 한 쪽씩
    async function loadOlder() {
      const pg = C.view && C.view.events_page; if (!pg || C.olderBusy) return;
      const before = C.olderBefore !== undefined ? C.olderBefore : pg.before;
      if (!before) return;
      C.olderBusy = true; drawOlder();
      try {
        const r = await getJ(`${API.process}/api/events?proc_inst_id=${encodeURIComponent(C.pid)}&before=${encodeURIComponent(before)}&limit=${OLDER_PAGE_ROWS}&page=true`);
        const rows = Array.isArray(r) ? r : r.events || [];
        rows.forEach(x => { if (x && x.id && !C.live.has(x.id)) C.live.set(x.id, x); });
        C.olderCount = (C.olderCount || 0) + rows.length;
        C.olderBefore = Array.isArray(r) ? null : (r.has_more ? r.before : null);
        if (!C.olderBefore) C.ext.olderDone = true;
      } catch (err) { C.olderErr = err.message; }
      finally { C.olderBusy = false; draw(true); }
    }
    function drawOlder() {
      const box = host.querySelector('[data-cr-older]'); const pg = C.view && C.view.events_page;
      const more = pg && pg.has_more && !C.ext.olderDone;
      box.innerHTML = more ? `<div class="cr-older"><button type="button" class="btn small" data-cr-older-btn ${C.olderBusy ? 'disabled' : ''}>${C.olderBusy ? '받는 중…' : '이전 기록 더 보기'}</button><span class="muted">최근 ${e(W().num(pg.limit || 0))}줄${C.olderCount ? ` + 이전 ${e(W().num(C.olderCount))}줄` : ''}을 보고 있습니다. 앞쪽 기록이 더 있습니다.</span>${C.olderErr ? `<span class="neg">${e(C.olderErr)}</span>` : ''}</div>`
        : C.olderCount ? `<p class="muted cr-older">이전 기록 ${e(W().num(C.olderCount))}줄을 더 받아 처음부터 모두 보고 있습니다.</p>` : '';
    }
    async function fetchExt() {
      if (C.fetching || !C.view) return;
      const inst = C.view.instance, v = vars(inst), running = inst.status === 'RUNNING', now = Date.now();
      const stale = key => now - (C.ext[key + 'At'] || 0) > EXT_REFRESH_MS;
      // 다시 읽기: 번호가 바뀜 · 진행 중이면 주기마다 · 방금 끝남 · 지난번에 실패(주기마다 다시 시도)
      const due = (key, id) => id && (C.ext[key + 'Id'] !== id || (running && stale(key)) || (!running && C.ext[key + 'Running']) || (C.ext[key] && C.ext[key].error && stale(key)));
      const jobs = [];
      if (due('decision', v.decision_id)) jobs.push(['decision', v.decision_id, `/api/decisions/${encodeURIComponent(v.decision_id)}`]);
      if (due('incident', v.incident)) jobs.push(['incident', v.incident, `/api/incidents/${encodeURIComponent(v.incident)}`]);
      Object.keys(SHARED_LISTS).forEach(key => { if (!C.ext[key] || (C.ext[key + 'Err'] && stale(key))) jobs.push([key]); });
      if (!jobs.length) return;
      C.fetching = true;
      try {
        await Promise.all(jobs.map(async ([key, id, url]) => {
          if (SHARED_LISTS[key]) {
            C.ext[key + 'At'] = Date.now();
            try { C.ext[key] = await sharedList(key); C.ext[key + 'Err'] = null; } catch (err) { C.ext[key] = C.ext[key] || []; C.ext[key + 'Err'] = err.message; }
            return;
          }
          C.ext[key + 'Id'] = id; C.ext[key + 'At'] = Date.now(); C.ext[key + 'Running'] = running;
          try { C.ext[key] = await getJ(API.process + url); } catch (err) { C.ext[key] = { error: err.message }; }
        }));
      } finally { C.fetching = false; schedule(); }
    }
    function schedule() { if (C.raf) return; C.raf = requestAnimationFrame(() => { C.raf = 0; draw(); }); }
    function draw(force) {
      if (!C.view) return;
      let m;
      try { m = C.model = build(C.view, C.ext, [...C.live.values()]); }
      catch (err) { host.querySelector('[data-cr-steps]').innerHTML = `<li class="cr-error">${e('처리 기록을 그리지 못했습니다: ' + err.message)}</li>`; return; }
      drawOlder();
      const head = headHtml(m);
      const headBox = host.querySelector('[data-cr-head]');
      if (force || headBox._html !== head) { headBox.innerHTML = head; headBox._html = head; }
      const box = host.querySelector('[data-cr-steps]');
      const want = m.steps.map(s => s.key);
      [...box.children].forEach(li => { if (!want.includes(li.dataset.key)) li.remove(); });
      m.steps.forEach((s, i) => {
        let li = [...box.children].find(x => x.dataset.key === s.key);
        const open = C.userTouched.has(s.key) ? C.open.has(s.key) : (s.live || C.open.has(s.key));
        const html = stepHtml(s, i, m.steps.length, open);
        if (!li) { li = document.createElement('li'); li.dataset.key = s.key; li.className = 'cr-step cr-new'; setTimeout(() => li.classList.remove('cr-new'), 900); }
        if (force || li._html !== html) {
          const openK = new Set([...li.querySelectorAll('details[data-k][open]')].map(d => d.dataset.k));
          const seen = new Set([...li.querySelectorAll('details[data-k][data-seen]')].map(d => d.dataset.k));
          const minorOn = new Set([...li.querySelectorAll('[data-cr-minor]:checked')].map(x => x.closest('details[data-k]')?.dataset.k));
          li.innerHTML = html; li._html = html;
          li.querySelectorAll('details[data-k]').forEach(d => { if (openK.has(d.dataset.k)) d.open = true; if (seen.has(d.dataset.k)) d.dataset.seen = '1'; if (minorOn.has(d.dataset.k)) { const c = d.querySelector('[data-cr-minor]'); if (c) { c.checked = true; d.querySelector('.cr-sec-body')?.classList.add('show-minor'); } } });
        }
        li.dataset.lane = s.lane; li.dataset.state = s.state; li.classList.toggle('live', !!s.live);
        if (box.children[i] !== li) box.insertBefore(li, box.children[i] || null);
        if (open && !li.classList.contains('open')) setOpen(li, true, false);
        else if (open) li.querySelectorAll('details[data-open-default]:not([data-seen])').forEach(x => { x.open = true; x.dataset.seen = '1'; });   // 실행 중에 새로 생긴 칸(도구 호출 등)도 펼친다
        else if (!open && li.classList.contains('open') && !C.userTouched.has(s.key)) setOpen(li, false, false);
      });
      const gaps = gapsHtml(m), gbox = host.querySelector('[data-cr-gaps]');
      if (gbox._html !== gaps) { const wasOpen = !!gbox.querySelector('details[open]'); gbox.innerHTML = gaps; gbox._html = gaps; if (wasOpen) gbox.querySelector('details')?.setAttribute('open', ''); }
    }
    C.draw = draw;
    mounted.add(C);
    return C;
  }
  // SSE 버스: 이벤트를 붙어 있는 처리 기록마다(각자 처리 건으로 거름)
  function onEvent(ev) { mounted.forEach(C => { if (!C.host.isConnected && !C.keep) { mounted.delete(C); return; } C.ingest(ev); }); }
  function wireBus() { if (window.hydStream && hydStream.subscribe) hydStream.subscribe(onEvent); else setTimeout(wireBus, 500); }
  wireBus();

  window.hydRecord = { mount, build, rowsOf, mounted, altHtml, knowledgeHtml };   // altHtml · knowledgeHtml: 판단 한 건만으로 그리는 부분(시험 · 다른 화면)
})();
