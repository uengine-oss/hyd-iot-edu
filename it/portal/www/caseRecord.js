/* A161 처리 기록 — 처리 건 한 건을 "무슨 일이 어떤 순서로 왜 일어났나" 이야기로 보인다. 블랙박스 없이: 시작(신호 · 값 · 시각) →
   AI 에이전트(받은 일 · 스킬 · 가져온 데이터 · 지식 경로 + 출처 절 · 도구 호출마다 물음 → 받음 · 비교한 대안과 진 이유 · 추천) →
   사람 승인(누가 · 언제 · 무엇을) → 시스템 처리(무엇을 어느 시스템에 · 결과) → 확인(값 vs 기준) → 결과 보고. 끝에 "기록에 없는 것".
   시나리오 이름 · task id 를 코드에 두지 않는다. 단계 종류는 작업 행의 주체(에이전트 · 사람 · 시스템)와 tool 로만 가른다.

   데이터(모두 이미 있는 읽기 API):
     GET /api/instances/{id}   처리 건 · 정의 · 작업 행 · 이벤트(도구 호출 · 에이전트 말 · 시스템 기록) · 승인 기록
     GET /api/decisions/{id}   판단: 대안(점수 · 점수 항목 · 제외 규칙 · 득실 경로 · SOP 절 · 매뉴얼 출처) · 가져온 데이터(provenance) · 승인 이력
     GET /api/incidents/{id}   사건: 설비 명령 번호 · 설비 응답 · 재관측 기준과 잰 값
     GET /api/agents           AI 에이전트 설정(목표 · 스킬 · 붙인 도구 서버)
   실시간: liveStream.js 버스(hydStream.subscribe)의 SSE 이벤트를 받아 같은 그리기 함수로 채운다. 2초 다시 읽기는 instances.js 가 넘긴다.

   참고 화면(모방, 로고 없음):
   - process-gpt-vue3 (/Users/uengine/process-gpt/services/frontend)
     src/components/ui/EventTimeline.vue:1-120,1306-1420 — 세로 목록의 작업 카드: 머리(아바타 · 제목 · 설명 · 오른쪽 상태 점 배지) · 메타 줄 · 결과 칸, 사람 질문 칸
     src/ds/components/PgToolSteps.vue · PgToolStep.vue — 왼쪽 1px 세로선 위 도구 한 줄(아이콘 16 · 글 15/24 · 실행 중 회전 13)
     src/components/apps/todolist/InstanceOutput.vue — 처리 건 결과물을 카드로(제목 + 읽기 전용 값)
   - Dify 실행 추적 web/app/components/workflow/run/tracing-panel.tsx · node.tsx — 노드 행 = 색 블록 아이콘 · 이름 · 오른쪽 걸린 시간 · 상태,
     누르면 입력 · 출력 펼침; status.tsx — 맨 위 상태 · 걸린 시간 · 단계 수 요약 (github.com/langgenius/dify)
   - n8n 실행 화면 https://docs.n8n.io/workflows/executions/ — 실행 한 건의 노드 순서 · 노드마다 성공 표시 · 들어간 값 / 나온 값(표 ↔ 원문 JSON 전환) */
/* 2026-11-14 한 장으로: 이 파일이 처리 건 한 건의 하나뿐인 「단계 기록」을 그린다(디자인 기준 5-2 · 5-3). 탭 넷과 요약 띠 · 단계 순서 칩 줄 ·
   「원래 이름(id) 보기」 체크 칸은 없앴다. 단계는 번호 붙은 세로 줄이고, AI 단계는 결론 → 근거(판단을 가른 값 · 비교한 조치) → 「자세한 실행 기록」 접기,
   사람 · 시스템 단계는 한 문장 + 「자세히」 접기다. 세는 숫자 칩 · 스킬 전달 표 · 해시 · 단서 조항 · 원문 JSON · 「기록에 없는 것」은 모두 그 단계의 접기 안에 있다. */
(function () {
  const W = () => window.hydWords;
  const TR = () => window.hydTrace;
  const e = s => esc(s);
  const ts = x => { const t = x ? Date.parse(x) : NaN; return Number.isFinite(t) ? t : null; };
  const fmtMs = ms => TR().fmtMs(ms), hhmmss = t => TR().hhmmss(t);   // 시간 표시는 trace.js 하나
  // 결과 값이 아직 없을 때의 문장 — 진행 중일 때만 「…하는 중」. 끝났거나 멈춘 단계는 그 상태와 함께 「결과 기록 없음」(진행 중처럼 읽히지 않게)
  const notYet = (b, doing) => b.live ? doing : `결과 기록이 없습니다 — 단계 상태: ${UI.status(b.w.status)}${b.w.draft_status === 'FAILED' ? ' · 실행 실패' : ''}.`;
  const icon = (k, cls) => TR() ? TR().icon(k, cls) : '';
  const vars = inst => UI.valuesOf(inst);
  const nm = id => W().idName(id);
  const named = (name, id) => `${e(name)}${W().id(id)}`;
  // 맡은 쪽이 AI 에이전트(agent:…)인 작업 행은 워커가 가져가기 전(agent_orch 가 비어 있는 순간)에도 AI 단계다 — 그 순간 사람 단계로 그리지 않는다
  const byAgent = w => /^agent:/.test(String(w.user_id || ''));
  const isAgent = w => UI.doerOf(w) === 'agent' || byAgent(w), isHuman = w => UI.doerOf(w) === 'human' && !byAgent(w);
  const CHECK = /^(incident:reobserve|plant:test-run|enterprise:GR_CONFIRM)$/;
  const PLANT = /^(plant:|incident:(command|reobserve)$)/;          // 설비에 닿는 단계(설비 명령 · 재관측 · 정비 모사 · 시운전)
  const CASE_LEVEL = new Set(['SCENARIO_BUTTON', 'CASE_LINK_FAILED']);   // 단계(todo)가 아니라 처리 건에 붙는 기록 — 시작 단계에 보인다
  const LANE = { person: '담당자', agent: 'AI 에이전트', system: '시스템' };
  const firstSentence = t => { const s = UI.clean(W().text(String(t || ''))).replace(/`[^`]*`에?/g, '').replace(/\*\*/g, '').trim(); const m = s.match(/^[^\n]*?[.。](?=\s|$)/); return (m ? m[0] : s.split('\n')[0]).slice(0, SENTENCE_MAX_CHARS); };
  const isoDur = s => { const m = /^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$/.exec(String(s || '')); if (!m) return s || ''; return [m[1] && `${m[1]}일`, m[2] && `${m[2]}시간`, m[3] && `${m[3]}분`, m[4] && `${m[4]}초`].filter(Boolean).join(' '); };
  // 설비 시간(TIME_SCALE 배속 — 설비 · 감지 · 재관측이 쓰는 시계)과 실제 시간을 한 형식으로: 「설비 시간 20분 (실제 1분)」. 사람 단계 시한은 실제 시간만
  const simSpan = (simS, realMs) => simS != null ? `설비 시간 ${fmtMs(simS * 1000)}${realMs != null ? ` (실제 ${fmtMs(realMs)})` : ''}` : realMs != null ? `실제 ${fmtMs(realMs)}` : '';
  const virtual = plan => plan && plan.virtual_s != null ? simSpan(plan.virtual_s, (plan.real_s || 0) * 1000) : plan && plan.real_s != null ? `실제 ${fmtMs(plan.real_s * 1000)}${plan.virtual ? ` (설비 시간 ${isoDur(plan.virtual)})` : ''}` : '';
  const chip = (label, tone = 'neutral', title = '') => ({ label, tone, title });
  // 화면 한도 · 다시 읽기 주기 (글자 수 · 줄 수 · ms)
  const SENTENCE_MAX_CHARS = 220, NOTE_MAX_CHARS = 600;
  const OLDER_PAGE_ROWS = 500, LIVE_MAX_ROWS = 3000;
  const EXT_REFRESH_MS = 4000, SHARED_TTL_MS = 60000;
  // 처리 건과 상관없이 같은 목록: AI 에이전트 설정(목표 · 스킬 · 도구) · 사람 이름(승인한 사람 id → 이름)
  const SHARED_LISTS = { agents: '/api/agents', people: '/api/inbox/users' };
  // 판단 · 사건 · AI 에이전트 설정 읽기 상태: 'none'(번호 없음) · 'loading' · 'error' · 'ok' — 읽는 중을 실패로 보이지 않는다
  const extState = (x, id) => !id ? 'none' : x === undefined ? 'loading' : x && x.error ? 'error' : 'ok';

  /* ================================================================ 이벤트 → 도구 호출 · 말 · 시스템 기록 행 */
  // 서버가 기록 줄에 적어 보내는 작업자 말(「수업 버튼 [쿨러 열화 주입]」 — procsvc/instances.py · main.py)은 화면에서 「결함 시뮬레이션 [쿨러 열화 주입]」으로 읽는다. 원문 접기에는 받은 그대로 둔다
  const noJargon = t => String(t || '').replace(/수업 버튼\s*(?=\[)/g, '결함 시뮬레이션 ').replace(/수업 버튼/g, '결함 시뮬레이션 단추');
  function rowsOf(evs) {
    if (window.hydTrace) evs=hydTrace.publicNotes(evs);
    const rows = [], byTool = new Map();
    for (const ev of evs) {
      const d = ev.data || {};
      if (ev.event_type === 'tool_usage_started') {
        const prior=byTool.get(UI.toolCallKey(ev));
        if (prior) { Object.assign(prior,{t0:ev.timestamp,tool:d.tool,input:d.input,inputEvent:ev,fullInput:d.full_input || null,minor:W().minorTool(d.tool)}); continue; }
        const r = { key: 't:' + UI.toolCallKey(ev), kind: 'tool', t0: ev.timestamp, tool: d.tool, input: d.input, inputEvent:ev, fullInput:d.full_input || null, status: 'running', minor: W().minorTool(d.tool) };
        byTool.set(UI.toolCallKey(ev), r); rows.push(r);
      } else if (ev.event_type === 'tool_usage_finished') {
        let r = byTool.get(UI.toolCallKey(ev));
        if (!r) { r = { key: 't:' + UI.toolCallKey(ev), kind: 'tool', t0: ev.timestamp, tool: d.tool, minor: W().minorTool(d.tool) }; rows.push(r); byTool.set(UI.toolCallKey(ev),r); }
        const result=UI.toolResult(ev);
        Object.assign(r, { t1: ev.timestamp, output: d.output, status:result.status, badge:result.badge, ioEvent:ev, full: d.full_output || null });
      } else if (ev.event_type === 'task_working' && d.type === 'text' && d.content) {
        rows.push({ key: 'n:' + ev.id, kind: 'note', t0: ev.timestamp, text: UI.clean(W().text(d.content)), data:d });
      } else if (ev.event_type === 'task_working' && d.type === 'skill_used') {
        // TOOL_START audit: a read request, not proof of successful reading/use.
        rows.push({ key: 'k:' + ev.id, kind: 'skill', t0: ev.timestamp, job: ev.job_id, data: d });
      } else if (ev.event_type === 'task_working' && d.type === 'skills_provided') {
        rows.push({ key: 'kp:' + ev.id, kind: 'note', t0: ev.timestamp, minor: true, data: d,
          text: Array.isArray(d.skills) ? UI.skillDeliverySummary(d.skills) + ((d.missing || []).length ? ` · 본문 없음: ${d.missing.join(', ')}` : '') : '스킬 전달 상태 기록 없음' });
      } else if (ev.event_type === 'task_working' && d.type === 'file_artifact') {
        rows.push({ key: 'f:' + ev.id, kind: 'file', t0: ev.timestamp, minor: true, text: UI.baseName(d.path || '') });
      } else if (ev.event_type === 'task_working' && (d.type === 'notice' || d.type === 'evidence')) {
        rows.push({ key: 'n:' + ev.id, kind: 'note', t0: ev.timestamp, text: UI.clean(W().text(d.content || d.name || '')) });
      } else if (ev.event_type === 'task_working' && d.name && !d.type) {
        // 서버가 기록 줄 이름에 적어 보내는 「수업 버튼 [쿨러 열화 주입]」은 화면에서 「결함 시뮬레이션 [쿨러 열화 주입]」으로 읽는다(서버 문구는 instances.py — 화면은 원문 접기에 그대로 둔다)
        rows.push({ key: 's:' + ev.id, kind: 'sys', t0: ev.timestamp, job: ev.job_id, text: noJargon(UI.clean(UI.logText(d.name))) + (d.attempt_failed ? ' · 실패한 시도' : ''), data: d });
      } else if (ev.event_type === 'error') {
        rows.push({ key: 'e:' + ev.id, kind: 'error', t0: ev.timestamp, text: noJargon(UI.clean(d.friendly || d.message || d.name || '오류')), data: d });
      } else if (ev.event_type === 'human_asked') {
        rows.push({ key: 'a:' + ev.id, kind: 'note', t0: ev.timestamp, text: '사람에게 물음: ' + UI.clean(d.text || d.question || '') });
      } else if (ev.event_type === 'human_response') {
        rows.push({ key: 'r:' + ev.id, kind: 'note', t0: ev.timestamp, text: `사람의 답: ${d.answer || ''}` });   // 답한 사람은 늘 담당자 한 명 — 담당자 id(user:…) 꼬리를 붙이지 않는다
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
    (view.definition?.roles || []).forEach(r => { if (r.endpoint && r.name) W().caseNames[r.endpoint] = r.name; });
    // 이 처리 건 정의가 붙인 칸 이름 — 화면 사전(plainWords F · UI.terms var.*)에 없는 칸에만 쓰인다(W.fieldName). 정의 설명문이 화면 이름을 덮지 않는다
    W().caseFields = Object.fromEntries((inst.variables_data || []).filter(r => r.name && r.name !== r.key).map(r => [r.key, r.name]));
    const forms = [view.definition?.startForm, ...Object.values(view.definition?.forms || {}), ...(view.definition?.activities || []).map(a => a.form)];
    forms.forEach(f => (f?.fields_json || []).forEach(x => { if (x.key && x.text && x.text !== x.key) W().caseFields[x.key] = x.text; }));
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
      .sort(UI.workitemOrder(view));
    const agentCount = wis.filter(isAgent).length;
    wis.forEach(w => {
      const act = acts[w.activity_id] || {};
      const execution = UI.taskExecution(w, byTodo.get(w.id) || [], inst);
      const live = execution.live;
      const base = { key: w.id, w, act, t0: w.start_date, t1: w.end_date, live, awaiting: execution.awaiting, terminal: execution.terminal, gen: w.generation || 0,
        name: UI.flowName(w.activity_name || act.name || w.activity_id), rows: rowsOf(byTodo.get(w.id) || []) };
      let s;
      if (evDefs[w.activity_id]) s = timerStep(ctx, base);
      else if (isAgent(w)) s = agentStep(ctx, base, agentCount);
      else if (isHuman(w) && act.type !== 'serviceTask') s = humanStep(ctx, base);
      else if (w.tool === 'process:report') s = reportStep(ctx, base);
      else if (CHECK.test(w.tool || '')) s = checkStep(ctx, base);
      else s = systemStep(ctx, base);
      s.state = s.state || (w.status === 'DONE' || w.status === 'COMPLETED' ? 'ok' : w.status === 'CANCELLED' ? 'stop' : w.draft_status === 'FAILED' ? 'fail' : execution.awaiting || execution.terminal?.event_type === 'task_deferred' ? 'wait' : live ? (w.status === 'PENDING' ? 'wait' : 'run') : 'idle');
      // 일은 끝냈는데 엔진이 아직 다음 단계로 넘기지 않은 순간(작업 행이 진행 중 · 제출됨): 「남음」(점선)이 아니라 「지금」으로 보인다
      if (s.state === 'idle' && running && ['IN_PROGRESS', 'SUBMITTED'].includes(w.status)) s.state = 'run';
      if (w.status === 'CANCELLED' && !s.stopNote) s.stopNote = UI.logText(w.log) || '취소됨';
      steps.push(s);
    });
    for (const ev of byTodo.get('') || []) {
      if (!['EFFECT_COMPENSATION', 'EFFECT_REVIEW'].includes(ev.job_id)) continue;
      const data = ev.data || {}, failed = ev.event_type === 'error' || (data.results || []).some(r => r.ok === false);
      steps.push({ key: 'effect:' + ev.id, type: 'effect', lane: 'person', icon: failed ? 'warn' : 'check',
        title: ev.job_id === 'EFFECT_REVIEW' ? '이전 조치 영향 확인' : '이전 조치 되돌리기', actor: W().who(data.by),
        t0: ev.timestamp, t1: ev.timestamp, sentence: W().effectText(ev.job_id, data), state: failed ? 'fail' : 'ok',
        sections: [sec('기록 원문', rawBlock(data), { raw: true })] });
    }
    if (!running && !steps.some(s => s.type === 'report')) { const r = endStep(ctx); if (r) steps.push(r); }
    gapsOf(ctx, steps);
    const t0 = inst.start_date, t1 = inst.end_date;
    return { inst, v, steps, gaps: ctx.gaps, running, t0, t1, tools: steps.reduce((n, s) => n + (s.rows || []).filter(r => r.kind === 'tool').length, 0),
      outcome: window.hydResultReport ? hydResultReport.fromValues(v) : null, decision: d,
      namesUnread: read.agents.state === 'error' || read.people.state === 'error' };   // 이름 목록(AI 에이전트 · 사람)을 못 읽음 — 머리 요약에 한 줄(사유는 「기록에 없는 것」)
  }

  // 이 처리 건이 이미 아는 이름: 판단의 대안 · 승인 역할 · 시나리오(원인 · 고장 유형), 진단 카드의 원인 · 조치, AI 에이전트 이름
  function caseNames(v, d, agents, people) {
    const n = {};
    const put = (id, name) => { if (id && name && typeof name === 'string' && !n[id]) n[id] = name; };
    if (d) {
      [...(d.original_decision?.options || []),...(d.options || [])].forEach(o => { put(o.id, o.name); if (o.approver) put(o.approver.id, o.approver.name); });
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
      const pressed = biz && !!ev.trigger;                           // 업무 감시가 아니라 사람이 화면의 단추를 눌러 연 처리 건(근거 값은 감시와 같은 칸)
      // 누른 사람: 담당자(requested_user)가 있을 때만 이름. 옛 판이 자리표로 남긴 기록은 「담당자 기록 없음」으로 보인다
      const presser = ev.requested_user ? ev.requested_by : '담당자 기록 없음';
      const who = pressed ? presser : (alert.observedBy && alert.observedBy.name) || (biz ? `${String(alert.source).toUpperCase()} 감시` : W().system('detector'));
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
        : `${alert.asset || ''}의 ${shown.length ? shown.slice(0, 2).map(([k, x]) => `${W().fieldName(k)} ${W().value(k, x)}`).join(' · ') + ' 값이' : '센서 값이'} 경보 규칙에 걸려 ‘${W().pattern(alert.pattern)}’ 경보가 났고, 처리 건이 열렸습니다.`;
      const pressRows = pressed ? [['누른 사람', presser, ''], ['누른 시각', UI.dateTime ? UI.dateTime(ev.requested_at) : ev.requested_at, '']] : [];
      const table = shown.length || pressRows.length ? kvTable(pressRows.concat(shown.map(([k, x]) => [W().fieldName(k), W().value(k, x), k]))) : '';
      if (biz && !plantBound) chips.push(chip('설비 명령 없음'));
      const sections = [
        sec('들어온 값', table || '<p class="muted">값 없음</p>', { open: true }),
        caseRows.length ? sec(`화면에서 누른 기록 ${caseRows.length}줄`, toolListHtml(caseRows, false, 'start'), { open: true }) : '',
        biz && !plantBound ? sec('이 흐름의 끝','<p>이 흐름은 업무 시스템에서 끝납니다 — 설비 명령 · 재관측 · 정비 수행 · 시운전 단계가 없습니다(흐름 설계). 처리되면 시작한 업무 데이터의 표시가 꺼집니다.</p>', { open: true }) : '',
        defn.rule || defn.condition ? sec('걸린 규칙', `<p>${e(W().rule(defn.rule || defn.condition))}</p>${defn.clearRule ? `<p class="muted">풀리는 조건: ${e(W().rule(defn.clearRule))}</p>` : ''}${defn.severity ? `<p class="muted">심각도 ${e(defn.severity)}</p>` : ''}`) : '',
        sec('경보 원문', rawBlock(alert), { raw: true }),
      ];
      return { key: 'start', type: 'start', lane: pressed ? 'person' : 'system', icon: biz ? 'schedule' : 'warn',
        title: pressed ? '담당자가 직접 시작' : biz ? '업무 데이터 감시가 시작' : '센서 경보로 시작',
        actor: who, t0: alert.t || inst.start_date, t1: inst.start_date, sentence, chips, sections, rows: caseRows,
        state: caseRows.some(r => r.kind === 'error') ? 'bad' : 'ok', ids: [alert.alertId, alert.pattern], biz, pressed };
    }
    const init = inst.initial_variables || {};
    const rows = Object.entries(init).filter(([, x]) => x != null && typeof x !== 'object').slice(0, 8);
    return { key: 'start', type: 'start', lane: 'person', icon: 'flag', title: '시작', actor: '경보 없이 직접 시작', t0: inst.start_date, t1: inst.start_date,
      sentence: `‘${ctx.view.definition?.processDefinitionName || inst.proc_inst_name || UI.defName(inst.proc_def_id)}’ 처리 건이 시작됐습니다.`, chips: rows.slice(0, 4).map(([k, x]) => chip(`${W().fieldName(k)} ${W().startValue(k,x)}`)),
      sections: [rows.length ? sec('시작 값', kvTable(rows.map(([k, x]) => [W().fieldName(k), W().startValue(k,x), k])), { open: true }) : '', sec('시작 값 원문', rawBlock(init), { raw: true })], state: 'ok' };
  }

  /* ---------------------------------------------------------------- AI 에이전트 */
  function agentStep(ctx, b, agentCount) {
    const { v, agents } = ctx, w = b.w;
    const recorded = w.output?.decision || w.draft?.decision;
    const recordedId = w.output?.decision_id || w.draft?.decision_id ||
      (ctx.producedBy(w.id).includes('decision_id') ? ctx.d?.id : null);
    const d = recorded ? UI.recordedDecision(ctx.d,recorded,recordedId) : ctx.d;
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
    if (instr || ag) sections.push(sec('받은 일', `${instr ? `<p>${e(UI.clean(W().text(instr.trim())))}</p>` : ''}${ag && ag.goal ? `<p class="muted">이 AI 에이전트의 목표: ${e(ag.goal)}</p>` : ''}`, { open: true }));
    // 스킬 · 붙인 도구 묶음 (설정 기준 — 처리 건에는 기록되지 않음)
    const skillCalls = tools.filter(r => r.tool === 'Skill');
    const provided = evs.filter(x => x.event_type === 'task_working' && x.data?.type === 'skills_provided');
    const starts = evs.filter(x => x.event_type === 'task_started');
    // Keep each execution's delivery snapshot separate. A later read request
    // must not turn an earlier failed/missing delivery into a successful one.
    const runs = starts.length ? starts.map(x => {
      const fallback = x.job_id && provided.find(p => p.job_id === x.job_id);
      return {event:x, data:Array.isArray(x.data?.skills) ? x.data : fallback ? {...fallback.data, skills_missing:fallback.data.missing} : x.data || {}};
    }) : provided.map(x => ({event:x, data:{...x.data, skills_missing:x.data.missing}}));
    if (runs.length) {
      const used = b.rows.filter(r => r.kind === 'skill');
      const servers = (ag && ag.tools) || [];
      const src = x => x === 'activity' ? '이 단계가 지정' : x === 'agent' ? 'AI 에이전트 설정' : (x || '');
      const delivery = runs.map(({event, data:sd}, i) => {
        const skills = Array.isArray(sd.skills) ? sd.skills : null;
        const head = `<h4 class="cr-h">실행 ${i + 1} · 스킬 전달 기록${event.timestamp ? ` <span class="muted">${e(UI.dateTime(event.timestamp))}</span>` : ''}</h4>`;
        if (!skills) return head + '<p class="cr-gapline">스킬 전달 기록이 없습니다. 전달 여부를 확인할 수 없습니다.</p>';
        const table = skills.length ? `<div class="table-container"><table class="table cr-table"><thead><tr><th>스킬 · 전달 상태</th><th>저장본</th><th>어디서 왔나</th><th>길이</th><th>설명</th></tr></thead><tbody>${skills.map(k => {
          const status = UI.skillDelivery(k);
          const name=UI.skillLabel(k,true);
          return `<tr><td><b>${e(name.label)}</b>${name.note ? ` <span class="muted">(${e(name.note)})</span>` : ''} ${UI.chipText(status.label, status.tone)}${k.error ? ` <span class="muted">${e(k.error)}</span>` : ''}${status.kind === 'prompt' ? `<span class="muted"> · ${k.verified_registered_content === true ? '등록 본문 확인됨' : '등록 본문 확인 기록 없음'}</span>` : ''}${UI.fold('스킬 식별자 · 전달 원문',rawBlock(k))}</td><td>${k.updated_at ? `${e(UI.dateTime(k.updated_at))} 저장` : '<span class="muted">저장 시각 기록 없음</span>'}${W().showIds && k.version ? ` <code class="cr-ver" title="${e(k.sha256 || '')}">${e(k.version)}</code>` : ''}</td><td>${e(src(k.source))}</td><td class="num">${k.chars != null ? e(W().num(k.chars)) + '자' : ''}</td><td class="muted">${e(UI.clean(k.description || ''))}</td></tr>`;
        }).join('')}</tbody></table></div>` : '';
        const note = skills.some(k => UI.skillDelivery(k).kind === 'prompt') ? '<p class="muted">프롬프트로 본문을 전달했습니다. 파일 읽기 없이 작업 지시에서 본문을 받을 수 있습니다.</p>' : '';
        const miss = (sd.skills_missing || []).length ? `<p class="cr-gapline">배정됐지만 본문이 없어 넣지 못한 스킬: ${e(sd.skills_missing.join(', '))}</p>` : '';
        return head + `<p>${e(UI.skillDeliverySummary(skills))}</p>` + table + note + miss;
      }).join('');
      const read = used.length ? `<ul class="cr-list">${used.map(r => { const x = r.data; return `<li>${e(hhmmss(r.t0))} <b>${e(x.recorded ? `스킬 ${x.skill}` : UI.skillLabel(x,true).label)}</b> — ${e(W().toolName(x.via))} 요청${x.known === false ? ` ${UI.chipText('제공 목록에 없는 스킬', 'warning')}` : W().showIds && x.version ? ` <code class="cr-ver">${e(x.version)}</code>` : ''}${UI.fold('읽기 요청 원문',rawBlock(x))}${W().id(r.job)}</li>`; }).join('')}</ul>` : '<p class="muted">파일 읽기 기록 없음</p>';
      sections.push(sec('스킬 전달 · 파일 읽기 기록', `${delivery}<h4 class="cr-h">이 단계의 파일 읽기 요청 ${used.length}건 <span class="muted">(모든 실행의 도구 호출 기록)</span></h4>${read}
        <p class="muted">스킬 파일을 읽으라고 요청한 기록입니다. 실제로 읽어서 일에 썼는지는 이 기록에 남지 않습니다.</p>
        ${ag ? `<dl class="cr-kv"><div><dt>AI 에이전트</dt><dd>${named(ag.name || W().who(w.user_id), w.user_id)}</dd></div><div><dt>쓸 수 있는 도구</dt><dd>${servers.map(x => `<span class="badge" data-variant="secondary">${e(W().system(x))}</span>`).join(' ') || '–'}</dd></div></dl>` : ''}`, { open: true }));
      const skills = runs.flatMap(r => Array.isArray(r.data.skills) ? r.data.skills : []);
      if (skills.length) chips.push(chip(UI.skillDeliverySummary(skills), skills.some(k=>k.written === false) ? 'danger' : 'neutral'));
      chips.push(chip(used.length ? `파일 읽기 요청 ${used.length}건` : '파일 읽기 기록 없음', 'neutral'));
    } else {
      const servers = (ag && ag.tools) || [];
      sections.push(sec('스킬 전달 · 파일 읽기 기록', `<p class="cr-gapline">스킬 전달 기록이 없습니다. 전달 여부를 확인할 수 없습니다.</p>${skillCalls.length ? `<p>이 처리 건의 스킬 도구 호출: ${skillCalls.map(r => `<b>${e(W().ask(r.tool, r.input))}</b>`).join(', ')}</p>` : ''}
        ${ag ? `<dl class="cr-kv"><div><dt>AI 에이전트</dt><dd>${named(ag.name || W().who(w.user_id), w.user_id)}</dd></div>
          <div><dt>현재 설정의 스킬</dt><dd>${(ag.skills || []).length ? ag.skills.map(s => `<span class="badge" data-variant="secondary">${e(s)}</span>`).join(' ') : '<span class="muted">설정 없음</span>'}</dd></div>
          <div><dt>쓸 수 있는 도구</dt><dd>${servers.map(s => `<span class="badge" data-variant="secondary">${e(W().system(s))}</span>`).join(' ') || '–'}</dd></div></dl>
          <p class="cr-gapline">현재 설정은 이 처리 건에 전달된 스킬의 기록이 아닙니다.</p>` : ''}`, {open:true}));
    }
    // 가져온 데이터 (판단이 쓴 사실의 출처 + 도구로 직접 읽은 값)
    const prov = owns('decision') && d && Array.isArray(d.provenance) ? d.provenance : [];
    const pw = W().causeWords(d && d.origin && d.origin.cause_route);
    const provName = p => (p.variable === 'cause' && pw.input) || (p.variable === 'failure_mode' && pw.inputFm) || p.name || W().fieldName(p.variable);
    const dataCalls = major.filter(r => /업무|ERP|MES|CMMS|SCM|센서|정비|구매|생산|공급/.test(W().toolSystem(r.tool)));
    if (prov.length || dataCalls.length) {
      const provRows = prov.map(p => `<tr><td>${named(provName(p), p.variable)}</td><td class="num">${e(W().value(p.variable, p.value))}</td><td>${e((p.source && W().system(p.source)) || p.sourceName || '')}${W().id(p.source)}</td><td class="muted">${e(UI.clean(p.how || ''))}</td></tr>`).join('');
      sections.push(sec(`가져온 데이터 ${prov.length ? prov.length + '건' : ''}`, `${prov.length ? `<div class="table-container"><table class="table cr-table"><thead><tr><th>값</th><th>읽은 값</th><th>어느 시스템</th><th>어떻게</th></tr></thead><tbody>${provRows}</tbody></table></div>` : ''}
        ${dataCalls.length ? `<p class="muted">도구로 직접 읽은 곳: ${[...new Set(dataCalls.map(r => W().toolSystem(r.tool)))].map(x => e(x)).join(' · ')} (요청과 결과는 아래 도구 호출에 있습니다)</p>` : ''}`, { open: !!prov.length }));
      chips.push(chip(`데이터 ${prov.length || dataCalls.length}건`));
    }
    // 지식 경로 (진단: 경보 → 증상 → 고장 유형 ← 원인 · 증거, 판단: 원인 → 조치 → 규칙 · 출처 절 · 득실 경로)
    const kg = knowledgeHtml(ctx, owns('guide_card') || owns('cause') ? v.guide_card : null, owns('decision') ? d : null);
    if (kg) sections.push(sec('지식 경로 · 출처', kg, { open: true }));
    // 도구 호출 — 요청 → 결과 한 줄씩, 보조 작업(도구 불러오기 · 파일 · 명령)은 접어 둔다
    if (b.rows.length) {
      const minor = b.rows.filter(r => r.minor).length;
      sections.push(sec(`도구 호출 ${tools.length}회${minor ? ` · 보조 작업 ${minor}건 포함` : ''}`, toolListHtml(b.rows, b.live, b.key), { open: b.live, cls: 'cr-tools' }));
      chips.unshift(chip(`도구 ${tools.length}회`));
    }
    // A deferral contains evaluated evidence, not a registered recommendation.
    evs.filter(ev=>ev.event_type==='task_deferred').forEach(ev=>{
      sections.push(sec('보류 당시 평가 근거', W().deferralEvidenceHtml(ev.data?.receipt || ev.data), {open:true}));
    });
    // 비교한 대안 · 추천
    let rec = null;
    if (owns('decision') && d && (d.options || []).length) {
      rec = d.options.find(o => o.id === d.recommended) || null;
      sections.push(sec(`비교한 대안 ${d.options.length}개`, altHtml(d), { open: true }));
      if (rec) chips.push(chip(`${UI.evaluationInfo(rec,d).state==='analysis' ? '모의 1순위' : '추천'} ${W().text(rec.name)}`, 'success'));
    } else if (owns('decision') && v.decision_id && !d) {
      const r = ctx.read.decision;
      sections.push(sec('비교한 대안', r.state === 'loading' ? '<p class="muted">판단 기록을 읽는 중입니다…</p>'
        : `<p class="cr-gapline">판단 기록${W().id(v.decision_id)}을 읽지 못했습니다 — ${e(r.error || '이유 모름')}</p>`, { open: true }));
    }
    const cause = owns('cause') && v.cause ? (((v.guide_card || {}).causes || []).find(c => c.id === v.cause) || {}).name || nm(v.cause) : '';
    const cw = W().causeWords(d && d.origin && d.origin.cause_route);
    if (cause) chips.push(chip(`${cw.cause} ${cause}`, 'warning'));
    // 끝맺는 말이 산문이면 그대로, 출력 계약(JSON — SQL · 적재 통계가 든다)이면 산문 칸에 흘리지 않고 원문 접기로(W1-13)
    if (done && done.data && done.data.text) {
      const said = String(done.data.text).trim();
      sections.push(/^[{[]/.test(said) ? sec('AI 에이전트가 낸 결과 원문', `<pre class="code">${e(said)}</pre>`) : sec('AI 에이전트가 남긴 말', `<p class="prose">${e(UI.clean(W().text(said)).replace(/`/g, ''))}</p>`));
    }
    sections.push(sec('결과 값 원문', rawBlock(out), { raw: true }));
    // 한 문장
    const parts = [];
    if (tools.length) parts.push(`도구를 ${tools.length}번 써서`);
    if (cause) parts.push(cw.found(cause));
    let sentence;
    if (rec) sentence = UI.evaluationInfo(rec,d).state==='analysis'
      ? `${parts.join(' ')} 대안 ${d.options.length}개를 규칙으로 비교해 ‘${W().text(rec.name)}’${W().josa(W().text(rec.name), '을/를')} 모의 1순위로 계산했습니다. 실제 승인 · 실행 준비는 확인하지 않았습니다.`
      : `${parts.join(' ')} 대안 ${d.options.length}개를 비교해 ‘${W().text(rec.name)}’${W().josa(W().text(rec.name), '을/를')} 추천했습니다.`;
    else if (cause) sentence = `${parts.join(' ')} 판단을 넘겼습니다.`;
    else if (done && done.data && done.data.text) sentence = (parts.length ? parts.join(' ') + ' ' : '') + firstSentence(done.data.text);
    else sentence = b.terminal?.event_type === 'task_deferred' ? `도구를 ${tools.length}번 쓴 실행은 평가를 보류했습니다. 다시 평가할 때까지 기다립니다.` : b.awaiting ? 'AI 에이전트가 일을 받기를 기다리는 중입니다.' : b.live ? (tools.length ? `도구를 ${tools.length}번 썼고, 지금 일하는 중입니다.` : 'AI 에이전트가 실행을 시작했습니다.') : '기록된 결과 문장이 없습니다.';
    if (recorded && d && d!==ctx.d) sentence = `당시 ${sentence}`;
    const lastOpen = b.live ? [...b.rows].reverse().find(r => r.kind === 'tool' && r.status === 'running') : null;
    return Object.assign(b, { type: 'agent', lane: 'agent', icon: 'agent', title: b.name, actor: ag ? ag.name : W().who(w.user_id) || 'AI 에이전트', sentence, chips, sections,
      now: lastOpen ? `${W().toolName(lastOpen.tool)} — ${W().ask(lastOpen.tool, lastOpen.input)}` : b.live ? '다음 행동을 정하는 중' : '', ids: [w.user_id, w.activity_id] });
  }

  function knowledgeHtml(ctx, gc, d) {
    const out = [];
    if (gc && typeof gc === 'object') {
      const top = (gc.causes || []).find(c => c.id === gc.topCause) || (gc.causes || [])[0];
      const pat = (gc.alert && gc.alert.pattern) || ctx.v.pattern;
      if (top) out.push(pathHtml([['경보', W().pattern(pat), pat], ['증상', (top.symptoms || []).join(' · ')], ['고장 유형', top.failureMode, top.failureModeId], ['원인', top.name, top.id]], ['→', '→', '←']));
      const causes = (gc.causes || []);
      if (causes.length) out.push(`<h4 class="cr-h">원인 후보와 증거 — 센서 기록에서 잰 값</h4><div class="table-container"><table class="table cr-table"><thead><tr><th>원인</th><th>점수</th><th>증거</th><th>잰 값</th><th>기준</th><th>판정</th></tr></thead><tbody>${
        causes.map(c => (c.evidence || [{}]).map((x, i) => `<tr${c.id === (top && top.id) ? ' data-pick' : ''}>${i === 0 ? `<td rowspan="${(c.evidence || [{}]).length}">${named(c.name, c.id)}</td><td rowspan="${(c.evidence || [{}]).length}" class="num">${e(W().num(c.score))}</td>` : ''}<td>${e(x.name || '–')}</td><td class="num">${x.value != null ? e(W().num(x.value)) : '–'}</td><td class="num">${x.threshold != null ? `${e(W().sym(x.expect))} ${e(W().num(x.threshold))}` : '–'}</td><td>${x.status ? UI.chipText(x.passed ? '맞음' : '아님', x.passed ? 'success' : 'neutral') : ''}</td></tr>`).join('')).join('')}</tbody></table></div>`);
    }
    if (d) {
      const o = d.origin || {}, rec = (d.options || []).find(x => x.id === d.recommended);
      if (o.cause_basis) out.push(`<p class="muted">${o.cause_route === 'purchase-part' ? '구매 부품을 정한 근거' : '원인을 정한 근거'}: ${e(basisText(o.cause_basis))}</p>` + UI.fold('판단 근거 설명 원문', rawBlock({cause_basis:o.cause_basis})));
      if (rec) {
        const REL = { MITIGATED_BY: '완화 조치', REMEDIED_BY: '근본 조치', PREVENTED_BY: '예방 조치' };
        const fm = o.failureMode, cause = o.cause, cw = W().causeWords(o.cause_route);
        const path = o.cause_route === 'purchase-part' ? [['구매 대상 부품', o.part?.name || o.part?.partNo || '부품 이름 기록 없음', o.part?.id], ['구매 절차', W().text(rec.name), rec.id]]
          : [[cw.cause, nm(cause), cause], [cw.failureMode, nm(fm), fm], [REL[rec.relation] || '조치', W().text(rec.name), rec.id]];
        out.push(`<h4 class="cr-h">추천안에 이른 길</h4>` + pathHtml(path, path.slice(1).map(()=>'→')));
        const rules = (rec.selectedBy || []).map(r => `<li>${UI.chipText('후보로 고른 규칙', 'accent')} ${e(W().text(r.annotation || nm(r.rule)))}${W().id(r.rule)}${(r.sources || []).length ? ` <span class="muted">출처 ${r.sources.map(x => e(x)).join(', ')}</span>` : ''}</li>`).join('');
        const steps = (rec.steps || []).map(s => `<li><b>${e(s.order || '')}.</b> ${e(W().text(s.text || ''))}${s.manual ? `<div class="cr-src">${UI.chipText(s.manual.ref || s.manual.id, 'neutral')} <b>${e(s.manual.title || '')}</b>${s.manual.excerpt ? ` — <span class="muted">“${e(W().text(s.manual.excerpt))}”</span>` : ''}</div>` : ''}</li>`).join('');
        if (rules) out.push(`<ul class="cr-list">${rules}</ul>`);
        if (steps) out.push(`<h4 class="cr-h">추천안의 작업 순서와 출처 문서 절</h4><ol class="cr-list">${steps}</ol>`);
        const paths = (rec.tradeoffEvaluation || []).filter(p => (p.edges || []).length || (p.nodes || []).length).slice(0, 4);
        if (paths.length) out.push(`<h4 class="cr-h">회사 성과 지표에 미치는 길 (이득과 손실)</h4><ul class="cr-list">${paths.map(p => `<li>${UI.chipText(p.good === false ? '손실' : '이득', p.good === false ? 'danger' : 'success')} <b>${e(p.name || '')}</b> <span class="cr-chain">${chainText(p, rec)}</span>${(p.conds || []).length ? ` <span class="muted">(조건: ${e(p.conds.join(', '))})</span>` : ''}</li>`).join('')}</ul>`);
      }
      if (d.rankRule && d.rankRule.annotation) out.push(UI.fold('점수를 매기는 법', `<p class="prose">${e(W().text(d.rankRule.annotation))}</p>${(d.rankRule.sources || []).length ? `<p class="muted">출처 ${d.rankRule.sources.map(x => e(x)).join(', ')}</p>` : ''}`));
    }
    return out.join('');
  }
  const basisText = s => String(s).replace(/AnomalyPattern\.code/g, UI.terms['ontology.field.AnomalyPattern.code']).replace(/\bAnomalyPattern\b/g, UI.terms['ontology.class.AnomalyPattern']).replace(/ontology/gi, '지식 그래프').replace(/same query as diagnose/i, '원인 진단과 같은 질의').replace(/via business_causes/i, '— 업무 경보 원인 찾기 도구')
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

  // 대안: 추천안 + 나머지(점수 · 진 이유 · 판단 엔진 설명이 그 안에 대해 한 말)
  function altHtml(d) {
    const opts = [...(d.options || [])].sort((a, b) => (b.id === d.recommended) - (a.id === d.recommended) || (b.feasible - a.feasible) || ((a.rank || 99) - (b.rank || 99)));
    const rec = opts.find(o => o.id === d.recommended) || opts[0];
    const said = o => window.hydApprove ? W().text(hydApprove.sentenceAbout(d.explanation, o.name).replace(/^\s*\d+순위\s*/, '')) : '';
    // 머리말 값: 예측이 고르는 근거인 안(설비를 바꾸는 안 · 안마다 예측이 갈림)만 예측, 아니면 이 안의 업무 값(approvalCard.js forecastDecides)
    const fcFirst = o => hydApprove.forecastDecides(o, d.options);
    const fc = o => fcFirst(o) ? (o.forecast || []).slice(0, 2).map(f => `${W().text(f.name)} ${W().num(+f.value)}${f.unit ? ' ' + f.unit : ''}`).join(' · ') : '';
    // 카드마다 다른 사실(결정 수준에서는 "후보마다 계산"으로 비어 있는 값 — 발주 금액 · 공급사 불량률 등): 규칙이 이 값으로 감점 · 제외한다
    const own = o => hydApprove.ownValues(o, d).join(' · ');
    const why = o => {
      // 추천안의 이유 줄: 예측은 위의 「예측 …」 줄이 이미 보이므로 이유 줄 앞에 다시 적지 않는다(W1-26)
      if (o.id === rec.id) return hydApprove.reasons(o, d, { head: false }).join(' · ');
      if (!o.feasible) return `제외 — ${W().text(((o.violations || [])[0] || {}).annotation || ((o.violations || [])[0] || {}).rule || '규정 위반')}`;
      const pen = [...(o.penalties || []), ...(o.warnings || [])].map(x => W().text(x.annotation || x.message || '')).filter(Boolean)[0];
      return [hydApprove.partDiff(o, rec, opts, { numbers: true }), pen ? `감점 · 경고: ${pen}` : ''].filter(Boolean).join(' / ') || (Number.isFinite(+o.score) && Number.isFinite(+rec.score) ? `점수 ${W().num(rec.score - o.score)} 낮음` : '');
    };
    const rows = opts.map(o => {
      const tag = o.id === rec.id ? UI.chipText(UI.evaluationInfo(o,d).state==='analysis' ? '모의 1순위' : '추천', 'success') : !o.feasible ? UI.chipText('제외', 'danger') : UI.chipText('미채택', 'neutral');
      return `<li class="cr-alt"${o.id === rec.id ? ' data-pick' : !o.feasible ? ' data-out' : ''}><div class="cr-alt-head">${tag}<b>${e(W().text(o.name))}</b>${W().id(o.id)}<span class="num muted">${W().purchaseEconomics(o) ? e(W().purchaseCostLabel(o)) : Number.isFinite(+o.score) && o.score !== null ? e(W().num(+o.score)) + '점' : ''}</span>${o.approver && o.approver.name ? `<span class="muted">승인 역할: ${e(o.approver.name)}</span>` : ''}</div>
        ${UI.evaluationHtml(o,d)}${W().purchaseContextHtml(o,d)}${W().maintenanceHtml(o)}${fc(o) ? `<p class="muted">예측 ${e(fc(o))}</p>` : ''}${own(o) ? `<p class="muted">이 안의 값 ${e(own(o))}</p>` : ''}<p>${o.id === rec.id ? why(o) : e(why(o))}</p>${o.id !== rec.id && said(o) ? `<p class="cr-said">AI 에이전트: “${e(said(o))}”</p>` : ''}</li>`;
    }).join('');
    return `<ol class="cr-alts">${rows}</ol>${d.explanation ? UI.fold('판단 엔진 설명 전문 (규칙 문장)', `<p class="prose">${e(W().text(d.explanation))}</p>`) : ''}`;
  }

  /* ---------------------------------------------------------------- 사람 */
  function humanStep(ctx, b) {
    const { d, v, view } = ctx, w = b.w;
    const rejected = b.rows.find(r => r.job === 'APPROVAL_REJECTED');
    if (rejected || w.output?.approval === '반려') {
      const data = rejected?.data || {}, reason = data.reason || w.output?.approval_reason || '';
      const person = W().who(data.by || w.user_id);
      return Object.assign(b, { type: 'approve', lane: 'person', icon: 'human', title: '승인 요청 반려', actor: person,
        sentence: `${person}${W().josa(person, '이/가')} 요청을 반려했습니다. 승인 뒤 조치는 실행하지 않았습니다.`,
        chips: [chip('반려', 'danger')], sections: [sec('반려 사유', `<p>${e(reason)}</p>`, { open: true })] });
    }
    const appr = (view.approvals || []).find(a => a.todo_id === w.id) || null;
    const accepted = [...(ctx.byTodo.get(w.id) || [])].reverse().find(x => x.job_id === 'APPROVAL_ACCEPTED');
    if (w.tool === 'formHandler:approve' && accepted) {
      const data = accepted.data || {}, key = b.act.approval?.key || 'slot', option = data.option || {}, who = W().who(data.by);
      return Object.assign(b, { type: 'approve', lane: 'person', icon: 'human', title: b.name, actor: who,
        sentence: `${who}${W().josa(who, '이/가')} ‘${option[key] ?? '선택 기록 없음'}’ 안을 승인했습니다.`, chips: [chip('승인', 'success')],
        sections: [sec('담당자의 결정', kvTable([['승인 역할', W().who(data.role), ''], ['고른 안', option[key] ?? '기록 없음', ''], ['사유', data.reason || '기록 없음', '']]), { open: true }), sec('고른 안 원문', rawBlock(option), { raw: true })] });
    }
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
    const by = byId ? W().who(byId) : '';        // 승인한 담당자는 user:… id 로 남는다 → 사람 이름
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
      ${kvTable(Object.entries(cc.facts || {}).filter(([k, x]) => W().known(k) && x != null && typeof x !== 'object').map(([k, x]) => [W().fieldName(k,cc.facts), W().value(k, x), k]))}${(cc.unknown || []).length ? `<p class="cr-gapline">그 순간 읽지 못한 값: ${e(cc.unknown.map(k => W().fieldName(k, cc.facts)).join(', '))}</p>` : ''}`));
    if (appr) sections.push(sec('승인 전달 기록', `<ul class="cr-list">${(appr.history || []).map(h => `<li>${e(hhmmss(h.t))} ${e(UI.deliveryStates[h.status] || UI.status(h.status))}${h.by ? ` · ${e(W().who(h.by))}` : ''}</li>`).join('')}</ul><p class="muted">전달 시도 ${e(appr.attempts)}회 · 지금 ${e(UI.deliveryStates[appr.status] || UI.status(appr.status))}</p>`));
    sections.push(sec('승인 원문', rawBlock(appr ? appr.payload : w.output), { raw: true }));
    const chips = [chip(`${by || '–'}${role ? ' · ' + W().who(role) : ''}`, 'accent'), chip(W().text(opt.name || nm(optId) || '–'), changed ? 'warning' : d ? 'success' : 'neutral')];
    if (b.t0 && b.t1) chips.push(chip(`기다림 ${fmtMs(ts(b.t1) - ts(b.t0))}`));
    const subject = by || W().who(role), optName = W().text(opt.name || nm(optId));
    // 판단을 못 읽었으면 추천안과 같은지 모른다 — 모르는 것은 말하지 않는다
    const how = !d ? '' : changed ? '추천안 대신 골라 ' : '추천안 그대로 ';
    const sentence = w.status === 'DONE' ? `${subject}${role && by ? `(${W().who(role)})` : ''}${W().josa(subject, '이/가')} ${when ? hhmmss(when) + '에 ' : ''}‘${optName}’${W().josa(optName, '을/를')} ${how}승인했습니다.`
      : b.live ? `${W().who(w.user_id)}의 승인을 기다리는 중입니다.` : UI.logText(w.log);
    return Object.assign(b, { type: 'approve', lane: 'person', icon: 'human', title: b.name, actor: by ? `${by}${role ? ' · ' + W().who(role) : ''}` : W().who(w.user_id), sentence, chips, sections,
      now: b.live ? '위의 「내가 할 일」에서 승인하거나 반려하면 다음 단계로 넘어갑니다.' : '', ids: [w.activity_id, role] });
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
      icon = 'command'; target = W().system('sys:scada');
      const cmds = Array.isArray(v.commands) ? v.commands : [];
      const label = cmds.map(c => W().action(c)).join(' · ') || '명령';
      const ack = inc && inc.ack;
      sentence = `${target}에 ‘${label}’ 명령${inc && inc.cmdId ? `(${inc.cmdId})` : ''}을 보냈고, ${ack ? `설비가 ${ack.result === 'DONE' ? '실행 완료' : UI.status(ack.result)}로 답했습니다${ack.interlock ? ` (안전 연동 ${UI.status(ack.interlock)})` : ''}.` : ackMissing(ctx, inc)}`;
      chips.push(chip(label, 'accent'));
      if (inc && inc.cmdId) chips.push(chip(inc.cmdId));
      if (ack) chips.push(chip(`응답 ${ack.result === 'DONE' ? '완료' : UI.status(ack.result)}`, ack.result === 'DONE' ? 'success' : 'danger'));
      const hist = inc ? (inc.history || []).filter(h => /CMD_ISSUED|AWAITING_ACK|ACKED|ACK_/.test(h.state)) : [];
      if (hist.length) sections.push(sec('설비와 주고받은 기록', `<ul class="cr-list">${hist.map(h => `<li>${e(hhmmss(h.t))} ${e(UI.status(h.state))}${h.note ? ` · ${e(W().rule(UI.logText(h.note)))}` : ''}</li>`).join('')}</ul>`, { open: true }));
      if (!inc) incidentGap(ctx, '설비 응답(명령 번호 · 응답 · 안전 연동)');
    } else if (/WO_CREATE|WO_RESCHEDULE/.test(tool)) {
      icon = 'workorder'; target = W().system('sys:cmms');
      const wo = out.work_order || (w.status === 'CANCELLED' ? {} : v.work_order) || {};
      const win = (wo.after && wo.after.window) || '';
      const scoped=W().maintenanceReceiptHtml(wo);
      sentence = scoped ? W().maintenanceReceiptSummary(wo) : /WO_RESCHEDULE/.test(tool) || wo.skill==='skill:reschedule-maintenance' ? (wo.ref ? `${target}의 기존 정비 오더 ${wo.ref} 일정 변경 영수증이 기록됐습니다. 정비를 마쳤는지는 정비 수행 단계에서 확인합니다.` : '기존 정비 오더 일정 변경 결과 기록을 확인할 수 없습니다.') : wo.ref ? `${target}에 정비 오더 ${wo.ref}${W().josa(wo.ref, '을/를')} 등록했습니다${win ? ` — ${UI.words(win)}` : ''}.` : b.live ? `${target}에 정비 오더를 등록하는 중입니다.` : `${target}의 정비 요청 등록 결과가 없습니다.${w.status === 'CANCELLED' ? ' 이 단계는 취소되었습니다.' : ''}`;
      if (wo.ref) chips.push(chip(wo.ref, 'accent'));
      if (win) chips.push(chip(UI.words(win)));
      if(scoped) sections.push(sec('설비별 정비 범위 · 오더 영수증',scoped,{open:true}));
      else if (wo.detail) sections.push(sec('등록한 내용', `<p>${e(W().text(hydResultReport.receiptDetail(wo)))}</p>`, { open: true }));
      const m = mailOf(wo); if (m) { sentence += ` 그리고 ${m.arguments.to}에게 메일을 보냈습니다.`; chips.push(chip('메일 1통')); sections.push(sec('보낸 메일', mailHtml(m), { open: true })); }
    } else if (/PR_CREATE/.test(tool)) {
      icon = 'order'; target = W().system('sys:erp');
      const po = out.purchase_order || v.purchase_order || {};
      const sup = supplierName(ctx, v.approved_supplier);
      sentence = po.ref ? `${target}에 발주 ${po.ref}${W().josa(po.ref, '을/를')} 넣었습니다 — ${sup} ${v.approved_qty != null ? v.approved_qty + '개' : ''} ${v.approved_amount != null ? W().num(v.approved_amount) + '만원' : ''}${po.after && po.after.lead_d != null ? `, 리드타임 ${po.after.lead_d}일` : ''}.` : notYet(b, `${target}에 발주를 넣는 중입니다.`);
      if (po.ref) chips.push(chip(po.ref, 'accent'));
      if (v.approved_amount != null) chips.push(chip(`${W().num(v.approved_amount)}만원`));
      if (v.approved_qty != null) chips.push(chip(`${v.approved_qty}개`));
      sections.push(sec('발주 값 (승인 순간 서버가 견적으로 확정)', kvTable([['공급사', sup, v.approved_supplier], ['부품', W().text(v.approved_part_no || '–'), ''], ['수량', W().value('approved_qty', v.approved_qty), ''], ['단가', W().value('approved_unit_price', v.approved_unit_price), ''], ['금액', W().value('approved_amount', v.approved_amount), '']]), { open: true }));
      const m = mailOf(po); if (m) { sentence += ` 공급사 · 입고 부서에 메일을 보냈습니다.`; chips.push(chip('메일 1통')); sections.push(sec('보낸 메일', mailHtml(m), { open: true })); }
    } else if (tool === 'plant:restore') {
      icon = 'schedule'; target = `${W().system('sys:cmms')} · 설비`;
      const m = out.maintenance || v.maintenance || {};
      const waitEv = b.rows.find(r => r.kind === 'sys' && r.data && r.data.plan);
      const skipped = b.rows.find(r => r.kind === 'sys' && r.job === 'WAIT_SKIPPED');
      sentence = w.status === 'DONE' ? `${skipped ? '즉시 ' : waitEv ? '예정된 정비 시간까지 기다린 뒤 ' : ''}정비를 했고, 정비 오더 ${m.work_order || ''} 완료와 설비 ${({ all: '전체', pump: '펌프', cooler: '쿨러', fan: '쿨러 팬' })[m.component] || nm(m.component) || ''} 복구를 기록했습니다.`
        : !b.live ? notYet(b) : waitEv ? `예정된 정비 시간까지 기다리는 중입니다 (${virtual(waitEv.data.plan)}).` : '정비를 하는 중입니다.';
      if (waitEv) chips.push(chip(`대기 ${virtual(waitEv.data.plan)}`));
      if (m.work_order) chips.push(chip(`${m.work_order} 완료`, 'success'));
      if (m.notice) sections.push(sec('정비 완료 알림', `<p>${e(W().text(m.notice))}</p>`, { open: true }));
    } else if (tool === 'process:wait') {
      icon = 'timer'; target = W().system('sys:process');
      const p = (out.waited) || ((b.rows.find(r => r.data && r.data.plan) || {}).data || {}).plan;
      sentence = p ? `${p.label || '정해진 시간'}까지 기다렸습니다 (${virtual(p)}).` : notYet(b, '정해진 시간까지 기다리는 중입니다.');
    } else if (tool === 'mcp:call') {
      icon = 'tool'; const r = Object.values(out).find(x => x && x.tool) || {};
      target = W().system(r.server); sentence = r.tool ? `${target}의 ‘${W().toolName(`mcp__${r.server}__${r.tool}`)}’${W().josa(W().toolName(`mcp__${r.server}__${r.tool}`), '을/를')} 불렀습니다.` : notYet(b, '승인 뒤 도구를 부르는 중입니다.');
    } else {
      sentence = UI.logText(w.log) || (w.status === 'DONE' ? `‘${b.name}’${W().josa(b.name, '을/를')} 마쳤습니다.` : notYet(b, `‘${b.name}’${W().josa(b.name, '을/를')} 하는 중입니다.`));
      target = W().who(w.user_id);
    }
    if (b.rows.length) sections.push(sec(`시스템 기록 ${b.rows.length}줄`, sysRowsHtml(b), { open: b.live }));
    if (w.log) sections.push(sec('처리 메모', `<p class="muted">${e(UI.logText(w.log))}</p>`));
    sections.push(sec('결과 값 원문', rawBlock(out), { raw: true }));
    if (w.status === 'PENDING') sentence = `조건 대기 — ${UI.logText(w.log) || '조건이 맞을 때까지 기다립니다'}`;
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
  // 승인한 공급사 이름은 서버가 승인 때 업무 DB 공급사 원장(ent.suppliers.name)에서 확정한 approved_supplier_name 하나 — 공급사는 그래프 시드가
  // 아니라 업무 DB 동기화로 생겨 이름 사전에 없고, 판단 카드 선택지 이름에서 떼어 내면 선택지에 없는 자리에서 id 가 보였다
  function supplierName(ctx, sid) {
    if (!sid) return '–';
    const v = ctx.v || {};
    return sid === v.approved_supplier && v.approved_supplier_name ? v.approved_supplier_name : `공급사 이름이 처리 건 값에 없음 (${sid})`;
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
      const m = fin && fin.reobservation;           // 서버가 사건 이력에 남긴 칸(machine._go): tag · op · limit · value · cleared · recovered
      const rec = out.recovered != null ? out.recovered : v.recovered;
      verdict = rec;
      if (!inc) incidentGap(ctx, '재관측 기준 · 사건 기록');
      const tag = m && m.tag ? m.tag.toLowerCase() : crit ? String(crit[0]).toLowerCase() : '';
      const valTxt = m && m.tag ? `${W().fieldName(tag)} ${m.value == null ? '값 없음' : `${W().num(m.value)} ${W().unit(tag)}`}` : '';
      // 지켜본 길이는 판정 줄의 설비 시간(연장까지 — 시작 줄의 15분이 아니라 끝난 때의 값), 없으면 시작 줄의 계획 값
      const simS = m && m.sim_s != null ? m.sim_s : obs && obs.reobservation && obs.reobservation.sim_s != null ? obs.reobservation.sim_s : null;
      const span = simSpan(simS, null);
      sentence = rec == null ? `설비가 기준 안으로 돌아오는지 지켜보는 중입니다${span ? ` (${span})` : ''}.`
        : `${span ? span + ' 동안 ' : ''}지켜본 뒤 ${reobsBasis(valTxt, crit, rec)}${rec ? '회복으로' : '미회복으로'} 판정했습니다.`;
      // 지켜보는 동안(1분 남짓)은 실제로 보는 값이 흘러나온다: 지금 값(설비 상태 1초 값) · 기준 · 판정까지 남은 시간(서버가 기록 줄에 적은 마감 시각 — 연장되면 새 마감) · 서버가 적은 기록 줄
      // (시스템 단계는 워커가 가져가는 일이 아니라 실행 판정(live)이 서지 않는다 — 작업 행이 아직 끝나지 않았는지로 본다)
      if (ctx.running && rec == null && !w.end_date && ['IN_PROGRESS', 'SUBMITTED'].includes(w.status)) {
        const ro = (obs && obs.reobservation) || {};
        const plan = [...b.rows].reverse().map(r => r.data && r.data.plan).find(p => p && p.due_at) || null;
        const watch = { asset: v.asset || (inc && inc.asset) || '', tag: String(ro.tag || (crit && crit[0]) || ''), op: ro.op || (crit && crit[1]) || '', limit: ro.limit != null ? ro.limit : crit ? crit[2] : null, plan, simS };
        if (watch.asset && watch.tag) { b.liveBox = watchBox(b, watch); b.liveLine = watchLine(watch); }
      }
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
        sentence = `${seriesSentence(series, simS)} — ${rec == null ? '판정 중' : rec ? '회복으로 판정' : '미회복으로 판정'}했습니다.`;
        sections.unshift(sec('지켜본 동안의 값', seriesHtml(series), { open: true }));
        chips.push(chip(`기준 안 ${Math.round((series.inside_share || 0) * 100)} %`, series.inside_last ? 'success' : 'danger'));
      }
      if (valTxt) chips.push(chip(valTxt, rec ? 'success' : 'danger'));
      if (crit) chips.push(chip(`기준 ${W().criterion(crit)}`));
      if (inc && inc.cleared != null) chips.push(chip(`경보 해제 ${inc.cleared ? '예' : '아니요'}`, inc.cleared ? 'success' : 'warning'));
      if (hist.length) sections.push(sec('사건 기록', `<ul class="cr-list">${hist.filter(h => /RE_OBSERV|RESOLVED|ESCALATED|RECOVER|CLOSED/.test(h.state)).map(h => `<li>${e(hhmmss(h.t))} ${e(UI.status(h.state))}${h.note ? ` · ${e(W().rule(UI.logText(h.note)))}` : ''}</li>`).join('')}</ul>`, { open: true }));
      if (rec != null && !b.series) ctx.gaps.push({ key: 'reobs', text: '재관측은 마지막에 잰 값 하나만 남습니다. 지켜본 동안의 값 흐름은 처리 건에 저장되지 않습니다 (센서 기록에는 있음).' });
    } else if (w.tool === 'plant:test-run') {
      const tr = out.test_run || v.test_run || null;
      const settle = b.rows.find(r => r.job === 'TEST_RUN_STARTED');
      verdict = tr ? tr.passed : null;
      sentence = tr ? `${settle && settle.data && settle.data.plan ? `안정될 때까지 기다린 뒤(${virtual(settle.data.plan)}) ` : ''}${(tr.readings || []).length}개 값을 재어 ${tr.passed ? '모두 기준 안 — 통과' : '기준 밖 값이 있어 미달'}로 판정했습니다.${tr.counter && tr.counter.detail ? ` ${W().text(tr.counter.detail)}.` : ''}`
        : !b.live ? notYet(b) : settle ? `시운전 — 안정될 때까지 기다리는 중입니다 (${virtual(settle.data.plan)}).` : '시운전을 준비하는 중입니다.';
      (tr && tr.readings || []).forEach(r => chips.push(chip(`${W().fieldName(String(r.tag).toLowerCase())} ${r.value == null ? '모름' : W().num(r.value)} ${W().sym(r.op)} ${W().num(r.limit)}${W().unit(String(r.tag).toLowerCase()) ? ' ' + W().unit(String(r.tag).toLowerCase()) : ''}`, r.ok ? 'success' : 'danger')));
      if (tr) sections.push(sec('잰 값과 기준', `<div class="table-container"><table class="table cr-table"><thead><tr><th>값</th><th>잰 값</th><th>기준</th><th>판정</th></tr></thead><tbody>${(tr.readings || []).map(r => `<tr><td>${named(W().fieldName(String(r.tag).toLowerCase()), r.tag)}</td><td class="num">${r.value == null ? '모름' : e(W().value(String(r.tag).toLowerCase(), r.value))}</td><td class="num">${e(W().sym(r.op))} ${e(W().num(r.limit))}</td><td>${UI.chipText(r.ok ? '통과' : '미달', r.ok ? 'success' : 'danger')}</td></tr>`).join('')}</tbody></table></div>${tr.at ? `<p class="muted">잰 시각 ${e(hhmmss(tr.at))}</p>` : ''}`, { open: true }));
    } else {   // 입고 확인
      icon = 'receipt';
      const gr = out.goods_receipt || v.goods_receipt || null;
      const waitR = b.rows.find(r => r.job === 'RECEIPT_WAIT'), delayR = b.rows.find(r => r.job === 'RECEIPT_DELAYED');
      verdict = gr ? true : w.status === 'CANCELLED' ? false : null;
      sentence = gr ? `입고 예정까지 기다린 뒤${waitR ? `(${virtual(waitR.data.plan)})` : ''} 입고 · 검수 ${gr.ref || ''}${W().josa(gr.ref || '검수', '을/를')} 기록했습니다 — ${W().text(gr.detail || '')}.`
        : w.status === 'CANCELLED' ? `입고를 기다리던 중 ${delayR ? '공급사가 납기를 늦췄고, ' : ''}정해 둔 기한이 먼저 와서 멈췄습니다. 입고는 기록되지 않았습니다.`
        : !b.live ? notYet(b) : waitR ? `입고 예정까지 기다리는 중입니다 (${virtual(waitR.data.plan)}${delayR ? ', 공급사 지연 반영' : ''}).` : '입고를 확인하는 중입니다.';
      if (waitR) chips.push(chip(`리드타임 ${waitR.data.plan.lead_d != null ? waitR.data.plan.lead_d + '일' : ''}`));
      if (delayR) chips.push(chip(`공급사 지연 ${delayR.data.plan.delay_d}일`, 'warning'));
      if (gr) chips.push(chip(gr.ref || '입고', 'success'));
      if (w.status === 'CANCELLED') { chips.push(chip('입고 없음', 'danger')); b.stopNote = '기한이 먼저 와서 멈춤'; }
    }
    if (b.rows.length) sections.push(sec(`시스템 기록 ${b.rows.length}줄`, sysRowsHtml(b), { open: b.live }));
    sections.push(sec('결과 값 원문', rawBlock(out), { raw: true }));
    return Object.assign(b, { type: 'check', lane: 'system', icon, title: b.name, actor: /^(incident:reobserve|plant:test-run)$/.test(w.tool) ? '설비 · 센서' : '구매 · 재고 관리', sentence, chips, sections, verdict,
      state: w.status === 'DONE' && verdict === false ? 'bad' : undefined, now: b.live ? '확인하는 중' : '', ids: [w.tool] });
  }

  /* 효과 확인(재관측)을 지켜보는 동안의 실시간 표시. 값은 지어내지 않는다:
     - 지금 값: 화면이 1초마다 받는 설비 상태(app.js state.plant — [data-cr-tag] 자리를 tickWatch 가 채운다). 못 받으면 「–」
     - 기준: 사건 기록의 재관측 기준(태그 · 비교 · 한계)
     - 판정까지: 서버가 기록 줄(REOBSERVE_STARTED · REOBSERVATION_EXTENDED)에 적은 마감 시각. 마감이 없으면 그 칸을 그리지 않는다(시간으로 차오르는 막대를 만들지 않는다) */
  const watchUnit = w => W().unit(String(w.tag).toLowerCase());
  const watchValue = w => `<span data-cr-tag="${e(w.asset + ':' + w.tag)}" data-cr-op="${e(w.op)}" data-cr-limit="${e(w.limit == null ? '' : w.limit)}">–</span>`;
  function watchLine(w) {
    const u = watchUnit(w);
    return `지금 ${e(W().fieldName(String(w.tag).toLowerCase()))} <b class="num">${watchValue(w)}${u ? ' ' + e(u) : ''}</b>${w.limit != null ? ` · 기준 ${e(W().sym(w.op))} ${e(W().num(w.limit))}${u ? ' ' + e(u) : ''}` : ''}${w.plan ? ` · <b class="num" data-cr-until="${e(w.plan.due_at)}" data-cr-label>–</b>` : ''}`;
  }
  function watchBox(b, w) {
    const u = watchUnit(w), name = W().fieldName(String(w.tag).toLowerCase());
    const lines = b.rows.filter(r => r.kind === 'sys' || r.kind === 'error').map(r => {
      const d = r.data || {}, rd = d.reading, p = d.plan;
      const sub = [rd && rd.value != null ? `${name} ${W().num(rd.value)}${u ? ' ' + u : ''} — 기준 ${rd.inside ? '안' : '밖'}` : '', p && p.window_s != null && !rd ? `${fmtMs(p.window_s * 1000)} 동안 지켜봅니다` : '', p && p.due_at ? `판정 예정 ${hhmmss(p.due_at)}` : ''].filter(Boolean).join(' · ');
      return `<div class="line" data-kind="${r.kind === 'error' ? 'fail' : 'ok'}">${UI.icon(r.kind === 'error' ? 'x' : 'check')}<span class="line-text"><b>${e(noJargon(r.text).replace(/효과 재관측/g, '효과 확인').replace(/재관측/g, '효과 확인'))}</b>${sub ? `<span class="line-sub">${e(sub)}</span>` : ''}</span><span class="line-time num">${e(hhmmss(r.t0))}</span></div>`;
    }).join('');
    return `<div class="stream" data-cr-watch><div class="stream-head"><i class="dot" data-tone="brand" data-live></i><span><b>효과 확인</b><span class="muted"> — 설비가 기준 안으로 돌아오는지 지켜보는 중</span></span>${b.t0 ? `<span class="elapsed num" data-since="${e(b.t0)}">${e(fmtMs(Date.now() - ts(b.t0)))}</span>` : ''}</div>
      <dl class="turn-facts watch-facts"><div><dt>지금 ${e(name)}</dt><dd class="num">${watchValue(w)}${u ? `<small>${e(u)}</small>` : ''}<span class="tag" data-cr-inside hidden></span></dd></div>
        ${w.limit != null ? `<div><dt>기준</dt><dd class="num">${e(W().sym(w.op))} ${e(W().num(w.limit))}${u ? `<small>${e(u)}</small>` : ''}</dd></div>` : ''}
        ${w.plan ? `<div><dt>판정까지</dt><dd class="num" data-cr-until="${e(w.plan.due_at)}">–</dd></div>` : ''}
        ${w.simS != null ? `<div><dt>지켜보는 시간</dt><dd class="num">${e(fmtMs(w.simS * 1000))}<small>설비 시간${w.plan && w.plan.window_s != null ? ` · 실제 ${e(fmtMs(w.plan.window_s * 1000))}` : ''}</small></dd></div>` : ''}</dl>
      ${lines ? `<div class="stream-log" data-cr-livelog>${lines}</div>` : ''}</div>`;
  }
  // 1초마다: 지켜보는 값과 남은 시간을 그 자리에 적는다(다시 그리지 않는다). 기준 안 · 밖은 서버가 준 비교(op · 한계)로만 가른다
  const INSIDE = { '<': (a, b) => a < b, '<=': (a, b) => a <= b, '>': (a, b) => a > b, '>=': (a, b) => a >= b };
  function tickWatch() {
    if (typeof document === 'undefined' || !document.querySelectorAll) return;
    const units = typeof state === 'object' && state && state.plant && state.plant.units ? state.plant.units : null;
    document.querySelectorAll('[data-cr-tag]').forEach(n => {
      const [asset, tag] = n.dataset.crTag.split(':');
      const raw = units && units[asset] && units[asset].tags ? units[asset].tags[tag] : null, val = raw == null ? null : Number(raw);
      const text = val == null || !Number.isFinite(val) ? '–' : W().num(val);
      if (n.textContent !== text) n.textContent = text;
      const badge = n.parentElement.querySelector('[data-cr-inside]'), cmp = INSIDE[n.dataset.crOp], limit = n.dataset.crLimit === '' ? null : Number(n.dataset.crLimit);
      if (badge && cmp && limit != null && val != null && Number.isFinite(val)) { const inside = cmp(val, limit); badge.hidden = false; badge.textContent = inside ? '기준 안' : '기준 밖'; badge.dataset.tone = inside ? 'ok' : 'warn'; }
    });
    document.querySelectorAll('[data-cr-until]').forEach(n => {
      const left = Math.ceil((Date.parse(n.dataset.crUntil) - Date.now()) / 1000);
      const text = Number.isFinite(left) ? (left > 0 ? ('crLabel' in n.dataset ? '판정까지 ' : '') + fmtMs(left * 1000) : '판정하는 중') : '–';
      if (n.textContent !== text) n.textContent = text;
    });
  }
  setInterval(tickWatch, 1000);

  // "토출 압력 182 bar — 기준 ‘토출 압력 ≥ 165 bar’ 안이라 " · 잰 값 · 기준을 모르면 그 말을 빼고 판정만
  function reobsBasis(valTxt, crit, rec) {
    const basis = [valTxt, crit ? `기준 ‘${W().criterion(crit)}’` : ''].filter(Boolean).join(' — ');
    return basis ? `${basis}${rec ? ' 안이라 ' : ' 밖이라 '}` : '';
  }
  const SIDE = { '<': '아래', '<=': '이하', '>': '위', '>=': '이상' };
  function seriesSentence(x, simS = null) {
    const tag = String(x.tag || '').toLowerCase(), u = W().unit(tag);
    const span = simSpan(simS, x.from && x.to ? ts(x.to) - ts(x.from) : null);
    return `${span ? span + ' 동안 ' : ''}${W().fieldName(tag)} ${W().num(x.first)}→${W().num(x.last)}${u ? ' ' + u : ''}, 기준(${W().num(x.limit)}${u ? ' ' + u : ''} ${SIDE[x.op] || ''}) 안에 있던 시간 ${Math.round((x.inside_share || 0) * 100)} %`;
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
      <path d="${line}" class="val"/><circle cx="${X(last.t).toFixed(1)}" cy="${Y(+last.v).toFixed(1)}" r="3" ${x.inside_last ? 'data-ok' : 'data-bad'}/></svg>`;
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
    const dur = isoDur(ev.timer || '');   // 정의 · 엔진의 타이머 칸은 timer 하나(engine.py)
    return Object.assign(b, { type: 'timer', lane: 'system', icon: 'timer', title: b.name, actor: `${W().system('sys:process')} · 기한 확인`, t0: b.w.end_date || b.w.start_date,
      sentence: b.w.status === 'DONE' ? `${host ? `‘${host}’에 걸어 둔 ` : ''}기한${dur ? `(${dur})` : ''}이 지나 ‘${b.name}’${W().josa(b.name, '이/가')} 울렸습니다${ev.cancelActivity === false ? ' — 원래 일은 계속됩니다' : host ? ` — ‘${host}’${W().josa(host, '은/는')} 멈춥니다` : ''}.` : `‘${b.name}’ 기한을 재는 중입니다.`,
      chips: dur ? [chip(`기한 ${dur}`, 'warning')] : [], sections: [], ids: [b.w.activity_id] });
  }

  /* ---------------------------------------------------------------- 결과 보고 */
  function reportStep(ctx, b) {
    const w = b.w, rep = (w.output || {}).result_report || null;
    const vv = rep && window.hydResultReport ? hydResultReport.fromValues({ ...ctx.v, result_report: rep }) : null;
    const tone = vv ? (vv.verdict === 'ok' ? 'success' : ['fail', 'rejected'].includes(vv.verdict) ? 'danger' : 'neutral') : 'neutral';
    const chips = rep ? [chip(rep.outcome || (vv && vv.label) || '결과', tone)].concat((rep.values || []).map(x => chip(`${W().text(x.name)} ${W().num(x.value)}${x.unit ? ' ' + x.unit : ''}${x.limit != null ? ` (기준 ${x.limit})` : ''}`, x.ok === false ? 'danger' : x.ok === true ? 'success' : 'neutral'))) : [];
    const sections = [];
    if (rep) {
      sections.push(sec('보고 내용', `<p><b>${e(W().text(rep.title || ''))}</b></p>${rep.summary ? `<p>${e(W().text(vv?.summary || rep.summary))}</p>` : ''}
        ${Object.keys(rep.refs || {}).length ? `<p class="muted">남긴 번호 ${Object.entries(rep.refs).map(([k, r]) => `${e({ work_order: '정비 오더', purchase_order: '발주', goods_receipt: '입고', mcp_receipt: '도구 영수증' }[k] || W().fieldName(k))} ${e(r)}`).join(' · ')}</p>` : ''}
        ${rep.incident_closed != null ? `<p class="muted">${e(hydResultReport.incidentMeaning(rep, ctx.inc, ctx.read.incident))}${rep.notification_count == null ? '' : rep.notification_count > 0 ? ` · 담당자 ${e(rep.notification_count)}명에게 알림` : ' · 알림 받을 담당자 없음'}</p>` : ''}`, { open: true }));
      const facts = Object.entries(rep.facts || {}).filter(([, x]) => x != null && typeof x !== 'object');
      if (facts.length) sections.push(sec('보고에 실은 값', kvTable(facts.map(([k, x]) => [W().fieldName(k) === k.replace(/_/g, ' ') ? (UI.terms['var.' + k] || k) : W().fieldName(k), k === 'approved_role' || k === 'approved_by' ? W().who(x) : k === 'approved_supplier' ? supplierName(ctx, x) : W().value(k, x), k]))));
    }
    sections.push(sec('결과 보고 원문', rawBlock(rep), { raw: true }));
    return Object.assign(b, { type: 'report', lane: 'system', icon: 'flag', title: b.name, actor: `${W().system('sys:process')} → 담당자 알림`,
      sentence: rep ? `${W().text(rep.title || '결과')}: ${rep.outcome || ''}${rep.summary ? ' — ' + W().text(vv?.summary || rep.summary) : ''}` : notYet(b, '결과를 정리하는 중입니다.'), chips, sections,
      state: rep && vv && vv.verdict === 'fail' ? 'bad' : undefined, ids: [w.tool] });
  }
  // 결과 보고 단계가 없는 흐름: 처리 건 값으로 결과를 만든다(끝난 경우만)
  function endStep(ctx) {
    const { inst, v } = ctx;
    const rep = window.hydResultReport ? hydResultReport.fromValues(v) : null;
    const end = inst.end_label || '';   // 끝난 곳의 이름은 서버가 정한다(engine.end_label — P1-08)
    const label = rep ? (rep.label || (rep.verdict === 'ok' ? '정상' : rep.verdict === 'fail' ? '미달' : '확인 결과')) : UI.status(inst.status);
    return { key: 'end', type: 'end', lane: 'system', icon: 'flag', title: '처리 완료', actor: W().system('sys:process'), t0: inst.end_date, t1: inst.end_date,
      sentence: `${rep && rep.title ? rep.title + ': ' : ''}${label}${rep && rep.summary ? ' — ' + W().text(rep.summary) : ''}${end ? ` (끝난 곳: ${end})` : ''}.`,
      chips: [chip(label, rep && rep.verdict === 'ok' ? 'success' : rep && rep.verdict === 'fail' ? 'danger' : 'neutral')], sections: [], state: rep && rep.verdict === 'fail' ? 'bad' : 'ok' };
  }

  /* ---------------------------------------------------------------- 기록에 없는 것 (블랙박스 점검) */
  function gapsOf(ctx, steps) {
    const G = ctx.gaps;
    const tools = steps.flatMap(s => (s.rows || []).filter(r => r.kind === 'tool'));
    const cut = tools.filter(r => r.status === 'warn' && !(r.full && r.full.stored)), blocked = tools.filter(r => r.status === 'blocked');
    if (cut.length) G.push({ key: 'cut', strong: true, text: `도구 결과 ${cut.length}건이 너무 커서 잘렸습니다 (${[...new Set(cut.map(r => W().toolName(r.tool)))].join(', ')}). AI 에이전트는 그 결과를 다 보지 못했고, 잘린 뒤의 원래 결과는 처리 건에 남지 않습니다. 그 뒤 판단은 판단 엔진이 저장한 값(아래 대안 · 데이터)으로 확인할 수 있습니다.` });
    if (blocked.length) G.push({ key: 'blocked', text: `안전 장치가 막은 명령 ${blocked.length}건 — 실행되지 않았고, 막힌 명령의 결과는 없습니다.` });
    const skillsRecorded = steps.filter(s => s.type === 'agent').every(s => {
      const evs = ctx.byTodo.get(s.key) || [], starts = evs.filter(x=>x.event_type === 'task_started');
      const provided = evs.filter(x=>x.data?.type === 'skills_provided' && Array.isArray(x.data.skills));
      return starts.length ? starts.every(x=>Array.isArray(x.data?.skills) || (x.job_id && provided.some(p=>p.job_id === x.job_id))) : provided.length > 0;
    });
    if (steps.some(s => s.type === 'agent')) {
      if (ctx.read.agents.state === 'error') G.push({ key: 'agents', strong: true, text: `AI 에이전트 설정(목표 · 스킬 · 쓸 수 있는 도구)을 읽지 못했습니다 — ${ctx.read.agents.error}. 다시 읽는 중입니다.` });
      if (!skillsRecorded) G.push({ key: 'skill', strong: true, text: '일부 실행의 스킬 전달 상태가 기록되지 않았습니다. 현재 AI 에이전트 설정으로 누락된 실행의 전달 여부를 확인할 수 없습니다.' });
      G.push({ key: 'think', text: 'AI 모델 안쪽의 생각은 기록되지 않습니다. 남는 것은 AI 에이전트가 쓴 말과 부른 도구, 받은 결과, 낸 결과 값입니다.' });
      steps.filter(s => s.type === 'agent' && !(s.rows || []).length && !s.live).forEach(s => G.push({ key: 'noev:' + s.key, strong: true, text: `‘${s.title}’ 단계는 도구 호출 기록이 없습니다 (결과 값만 남음).` }));
    }
    const start = steps[0];
    if (start && start.pressed && !(start.rows || []).some(r => r.kind === 'sys')) G.push({ key: 'button', strong: true, text: '화면에서 누른 기록(누른 사람 · 시각)이 처리 건 기록에 없습니다 — 시작 경보의 근거 값에만 남았습니다.' });
    if (start && (start.rows || []).some(r => r.kind === 'error')) G.push({ key: 'link', strong: true, text: '화면에서 누른 기록을 이 처리 건에 붙이지 못했습니다(시작 단계의 오류 줄). 누가 · 언제 눌렀는지는 감사 기록에만 있습니다.' });
    if (ctx.read.people.state === 'error' && steps.some(s => s.lane === 'person' && s.type !== 'start')) G.push({ key: 'people', strong: true, text: `사람 이름 목록을 읽지 못해 승인 · 입력한 사람이 원래 이름(id)으로 보일 수 있습니다 — ${ctx.read.people.error}` });
    if (steps.some(s => s.type === 'approve' && s.w && s.w.status === 'DONE')) G.push({ key: 'who', text: '승인은 이 PC의 담당자 이름으로 기록됩니다. 로그인으로 본인 확인을 하지는 않습니다.' });
    const pg = ctx.view.events_page;
    if (pg && pg.has_more && !ctx.olderDone) G.push({ key: 'cap', strong: true, text: '이 처리 건은 기록이 많아 가장 최근 줄부터 받았습니다. 맨 위 "이전 기록 더 보기"로 앞쪽 기록을 더 받을 수 있습니다.' });
    if (ctx.read.decision.state === 'error') G.push({ key: 'dec', strong: true, text: `판단 기록을 읽지 못해 대안 · 가져온 데이터 · 지식 경로를 보이지 못했습니다 — ${ctx.read.decision.error}` });
    if (ctx.d && !(ctx.d.provenance || []).length) G.push({ key: 'prov', text: '판단에 가져온 데이터의 출처 목록이 없습니다. 도구 호출의 받은 값으로만 확인할 수 있습니다.' });
    if (steps.some(s => s.type === 'system' && /메일/.test(s.sentence || ''))) G.push({ key: 'mail', text: '메일은 보냄 결과(성공)까지만 기록됩니다. 받는 사람이 읽었는지는 알 수 없습니다 (보낸 내용은 위 「보낸 메일」에서 확인).' });
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
    let o = x; if (typeof x === 'string') { try { o = JSON.parse(x); } catch (_) { return UI.mask(x); } }
    return UI.mask(JSON.stringify(o, null, 2));          // 원문 칸 — 코드 값을 이름으로 바꾸지 않는다(UI.mask)
  }
  const rawBlock = x => x == null || (typeof x === 'object' && !Object.keys(x).length) ? '' : `<pre class="code">${e(pretty(x))}</pre>`;
  // Full original retrieval and integrity state are shared with Trace/TaskDetail in UI.
  function redrawAll() { mounted.forEach(C => C.draw && C.draw(true)); }

  /* 도구 호출 목록: 같은 도구는 한 줄로 묶고 횟수를 붙인다(Langfuse 「조회 (3/3)」 — 여섯 번 부른 것을 여섯 줄로 늘어놓지 않는다).
     줄을 누르면 그 도구를 부른 요청 · 결과와 원문이 차례대로 열린다. 말 · 스킬 읽기 · 시스템 기록 · 오류는 그 아래에 시각 순으로 둔다. */
  function callHtml(r, live) {
    const ask = r.inputEvent ? UI.toolAsk(r.inputEvent, true).summary : W().ask(r.tool, r.input);
    const fo = r.full;
    const result = r.ioEvent ? UI.toolResult(r.ioEvent, true) : null;
    if (result) { r.status = result.status; r.badge = result.badge; }
    const got = r.status === 'running' ? '' : result ? result.summary : W().got(r.tool, r.output);
    const dur = r.t0 && r.t1 ? fmtMs(ts(r.t1) - ts(r.t0)) : '';
    const full = (r.fullInput && r.inputEvent ? UI.fullToolIOHtml(r.inputEvent, 'input') : '') + (fo && r.ioEvent ? UI.fullToolIOHtml(r.ioEvent) : '');
    const io = full + `${r.input != null ? `<div class="cr-io"><span>요청 원문</span><pre class="code">${e(pretty(r.input))}</pre></div>` : ''}${r.output != null ? `<div class="cr-io"><span>${fo ? '결과 미리보기' : '결과 원문'}</span><pre class="code">${e(pretty(r.output))}</pre></div>` : ''}`;
    return { ask, got, dur, io, stored: !!(fo && fo.stored),
      line: `<div class="tg-call"><div class="tg-line"><time>${e(hhmmss(r.t0))}</time><span>${ask ? `<span class="cr-q">요청</span> ${e(ask)}` : ''}${got || r.status !== 'running' ? ` <span class="cr-a">→</span> ${e(got || '결과를 받았습니다')}` : live ? ' <span class="muted">실행 중</span>' : ''}${r.badge ? ` <span class="tg-warn" data-state="${e(r.status)}">${e(r.badge)}</span>` : ''}${fo && fo.stored ? ' <span class="muted">· 원문 보관</span>' : ''}</span>${dur ? `<span class="cr-dur num">${e(dur)}</span>` : ''}</div>${io}</div>` };
  }
  function toolListHtml(rows, live, stepKey) {
    const tools = rows.filter(r => r.kind === 'tool'), rest = rows.filter(r => r.kind !== 'tool');
    const groups = new Map();
    tools.forEach(r => { if (!groups.has(r.tool)) groups.set(r.tool, []); groups.get(r.tool).push(r); });
    const minor = [...groups.values()].filter(g => g.every(r => r.minor)).reduce((n, g) => n + g.length, 0) + rest.filter(r => r.minor).length;
    const groupHtml = [...groups].map(([tool, list]) => {
      const calls = list.map(r => callHtml(r, live));
      const sys = W().toolSystem(tool);
      const total = list.reduce((n, r) => n + (r.t0 && r.t1 ? ts(r.t1) - ts(r.t0) : 0), 0);
      const bad = list.filter(r => r.status === 'fail').length, warn = list.filter(r => r.status === 'warn' || r.status === 'blocked').length, running = list.some(r => r.status === 'running');
      const state = bad ? `<span class="tg-warn" data-state="fail">실패 ${bad}회</span>` : warn ? `<span class="tg-warn" data-state="warn">${e(list.find(r => r.badge)?.badge || '확인 필요')}${warn > 1 ? ` ${warn}회` : ''}</span>` : '';
      return `<li class="tg"${list.every(r => r.minor) ? ' data-minor' : ''}><details class="cr-call" data-k="${e(stepKey + ':g:' + tool)}"><summary><span class="tg-name"><b>${e(W().toolName(tool))}</b>${sys ? `<span class="muted">${e(sys)}</span>` : ''}</span><span class="tg-meta">${state}${running && live ? '<i class="dot" data-tone="brand" data-live></i>' : ''}<span class="num">${list.length}회</span>${total ? `<span class="cr-dur num">${e(fmtMs(total))}</span>` : ''}</span></summary>
        <div class="tg-body"><div class="cr-io"><span>도구 식별자</span><code>${e(tool)}</code></div>${UI.toolIdentityFold(tool)}${calls.map(c => c.line).join('')}</div></details></li>`;
    }).join('');
    const items = rest.map(r => {
      const time = `<time>${e(hhmmss(r.t0))}</time>`;
      if (r.kind === 'note') return `<li class="cr-r"${r.minor ? ' data-minor' : ''}>${time}<div><q>${e(r.text.slice(0, NOTE_MAX_CHARS))}${r.text.length > NOTE_MAX_CHARS ? '…' : ''}</q>${r.data ? `<details class="cr-raw" data-k="${e(stepKey + ':' + r.key)}"><summary>원문</summary><pre class="code">${e(JSON.stringify(r.data, null, 2))}</pre></details>` : ''}</div></li>`;
      if (r.kind === 'skill') return `<li class="cr-r">${time}<div><b>스킬 파일 읽기 요청</b> ${e(UI.skillLabel(r.data, true).label)} <span class="muted">(${e(W().toolName(r.data.via))}) · 읽기 요청은 읽기 성공을 뜻하지 않습니다</span><details class="cr-raw" data-k="${e(stepKey + ':' + r.key)}"><summary>원문</summary>${rawBlock(r.data)}</details></div></li>`;
      if (r.kind === 'file') return `<li class="cr-r" data-minor>${time}<div>결과 파일 ${e(r.text)}</div></li>`;
      if (r.kind === 'sys') return `<li class="cr-r">${time}<div><b>${e(r.text)}</b>${sysDetail(r)}</div></li>`;
      if (r.kind === 'error') return `<li class="cr-r" data-err>${time}<div><b>${e(r.text)}</b><details class="cr-raw" data-k="${e(stepKey + ':' + r.key)}"><summary>원문</summary><pre class="code">${e(pretty(r.data))}</pre></details></div></li>`;
      return '';
    }).join('');
    return `${minor ? `<label class="cr-minor-toggle"><input type="checkbox" data-cr-minor> 보조 작업 ${minor}건도 보기 <span class="muted">(쓸 도구 불러오기 · 파일 쓰기 · 명령 실행)</span></label>` : ''}${groupHtml ? `<ul class="tg-list">${groupHtml}</ul>` : ''}${items ? `<ol class="cr-rows">${items}</ol>` : ''}`;
  }
  function sysDetail(r) {
    const d = r.data || {};
    if (r.job === 'MCP_RESULT_VALUES') return kvTable(Object.entries(d.values || {}).map(([k, value]) => [W().fieldName(k), W().value(k, value), k]));
    if (d.setpoints) return ` <span class="muted">${e(W().who(d.by))} · ${e(W().setpointsText(d))}</span>`;
    if (W().effectText(r.job, d)) return ` <span class="muted">${e(W().effectText(r.job, d))}</span>`;
    if (d.plan) return ` <span class="muted">${e(d.plan.label || '')} ${e(virtual(d.plan))}${d.plan.source ? ` · ${e(W().text(d.plan.source))}` : ''}</span>`;
    if (d.notice) return ` <span class="muted">${e(W().text(d.notice))}</span>`;
    if (d.by) return ` <span class="muted">${e(W().who(d.by))}${d.role ? ' · ' + e(W().who(d.role)) : ''}${d.reason ? ' · ' + e(d.reason) : ''}</span>`;
    if (d.readings) return ` <span class="muted">${e(d.passed ? '통과' : '미달')}</span>`;
    if (d.receipt) return ` <span class="muted">${e(d.receipt.ref || '')} ${e(W().text(d.receipt.detail || ''))}</span>`;
    if (d.report) return ` <span class="muted">${e(d.report.outcome || '')}</span>`;
    return '';
  }

  /* ---------------------------------------------------------------- 단계 한 줄 (디자인 기준 5-1 4번 · 5-2, 키트 .steps > .step)
     표시(끝남 초록 체크 · 지금 제품색 · 남음 점선 · 실패 빨강) · 이름 · 누가(아이콘 + 이름) · 오른쪽에 시각과 걸린 시간, 그 아래 한 문장.
     AI 단계: 끝난 뒤는 결론 → 근거(펼쳐서) → 후보 비교(.opts) → 실행 기록(접힘 — 그 안에 구획마다 접기와 원문 JSON), 일하는 중은 실시간 상자(.stream — 7절).
     사람 · 시스템 단계는 한 문장 + 「자세히」 접기. 세는 숫자 · 값 · 내부 값 · 원문은 모두 접기 안이다. */
  const PIN = { ok: 'done', run: 'now', wait: 'now', idle: 'todo', bad: 'fail', fail: 'fail', stop: 'fail' };
  const PREFIX = { bad: '기준 밖 — ', fail: '실패 — ' };
  const WHO_ICON = { agent: 'bot', person: 'user', system: 'cog' };
  const markIcon = s => { const st = PIN[s.state] || 'todo'; return st === 'done' ? 'check' : st === 'fail' ? 'x' : st === 'todo' ? 'circle-dashed' : s.lane === 'agent' ? 'bot' : s.lane === 'person' ? 'user-check' : 'cog'; };
  // 「자세히」 접기 안의 구획: 작은 머리글과 내용. 원문(JSON)만 한 번 더 접는다
  function sectionsHtml(s, secs) {
    return secs.filter(Boolean).map((x, j) => x.raw ? `<details class="fold" data-k="${e(s.key + ':raw' + j)}"><summary>${e(x.title)}</summary><div class="fold-body">${x.body}</div></details>`
      : `<section class="cr-sec ${x.cls || ''}"><h4 class="cr-h">${e(x.title)}</h4><div class="cr-sec-body">${x.body}</div></section>`).join('');
  }
  // AI 단계의 「실행 기록」 안: 구획마다 접기 하나(원문 포함) — 줄들 아래에 놓인다
  const foldsHtml = (s, secs) => secs.filter(Boolean).map((x, j) => `<details class="fold" data-k="${e(s.key + ':sec' + j)}"><summary>${e(x.title)}</summary><div class="fold-body ${x.cls || ''}">${x.body}</div></details>`).join('');
  // 단계마다 모아 두던 값(세는 숫자 · 값)은 접기 안의 한 줄로 — 뱃지에는 상태 낱말만 넣는다(디자인 기준 4절)
  const factsLine = s => { const f = (s.chips || []).filter(c => c && c.label && !/^[–\-\s·]+$/.test(c.label)).map(c => e(c.label)); return f.length ? `<p class="cr-facts">${f.join(' <span class="sep">·</span> ')}</p>` : ''; };
  function gapLines(gaps) {
    return gaps.length ? `<section class="cr-sec cr-gap"><h4 class="cr-h">기록에 없는 것</h4><ul class="cr-gaps">${gaps.map(g => `<li${g.strong ? ' data-strong' : ''}>${e(g.text)}</li>`).join('')}</ul></section>` : '';
  }
  function idsLine(s) {
    const ids = [...new Set([s.w && s.w.id, ...(s.ids || [])].filter(Boolean))];
    const extra = s.w ? [s.gen ? `${s.gen + 1}회차` : '', s.w.status ? `단계 상태 ${UI.status(s.w.status)}${s.w.draft_status && s.w.status !== 'DONE' ? ' · ' + UI.status(s.w.draft_status) : ''}` : ''].filter(Boolean) : [];
    return ids.length || extra.length ? `<p class="cr-ids"><span class="muted">내부 값</span> ${ids.map(id => `<code class="inline">${e(id)}</code>`).join(' ')}${extra.length ? ` <span class="muted">${e(extra.join(' · '))}</span>` : ''}</p>` : '';
  }
  const stepLink = s => s.w ? `<p class="cr-more"><button type="button" class="btn" data-variant="link" data-td-open="${e(s.w.id)}">이 단계가 받은 값과 다음 단계로 넘긴 값 보기</button></p>` : '';

  /* 실시간 줄(키트 .line): AI 가 한 일 한 가지 = 한 줄. 아이콘(끝남 체크 · 하는 중은 도구 종류 · 실패 ×) + 굵은 한 문장 + 보조 줄(어느 도구 · 물음 → 받은 것) + 오른쪽 시각.
     보조 작업(쓸 도구 불러오기 · 파일 읽기 · 명령 실행)은 줄로 세우지 않는다 — 스킬 문서 읽기와 결과 파일 작성은 그 기록 줄이 따로 온다 */
  const TOOL_ICON = [[/diagnos|cause/i, 'network'], [/evaluat|rank|compar/i, 'scale'], [/submit|decision/i, 'send'], [/neo4j|cypher|graph/i, 'network'], [/sql|query|select|timeseries/i, 'database'], [/mail|notify/i, 'send']];
  const toolIcon = tool => (TOOL_ICON.find(([re]) => re.test(String(tool || ''))) || [0, 'plug'])[1];
  const lineRows = s => (s.rows || []).filter(r => (r.kind === 'tool' && !r.minor) || r.kind === 'skill' || r.kind === 'file' || r.kind === 'error');
  function lineOf(r, live, fresh) {
    const wrap = (kind, icon, text, sub, pending) => `<div class="line"${kind ? ` data-kind="${kind}"` : ''}${pending ? ' data-pending' : ''}${fresh ? ' data-new' : ''}>${UI.icon(icon)}<span class="line-text"><b>${e(text)}</b>${sub ? `<span class="line-sub" title="${e(sub)}">${e(sub)}</span>` : ''}</span><span class="line-time num">${e(hhmmss(r.t0))}</span></div>`;
    if (r.kind === 'tool') {
      const name = W().toolName(r.tool), sys = W().toolSystem(r.tool);
      const ask = r.inputEvent ? UI.toolAsk(r.inputEvent, true).summary : W().ask(r.tool, r.input);
      if (r.status === 'running') return live ? wrap('tool', toolIcon(r.tool), `${name} 중`, [sys, ask].filter(Boolean).join(' · '), true)
        : wrap('', toolIcon(r.tool), `${name} — 결과 기록 없음`, [sys, ask].filter(Boolean).join(' · '));
      // 받은 것은 기록 줄의 미리보기로 요약한다. 화면이 보관된 원문을 다시 읽는 사정(「원문 읽는 중」)은 AI 가 한 일이 아니라 이 줄에 적지 않는다 — 잘림 · 막힘만 꼬리에 붙인다
      const got = W().got(r.tool, r.output);
      const bad = r.status === 'fail', flag = ['warn', 'blocked'].includes(r.status) && r.badge ? ` — ${r.badge}` : '';
      return wrap(bad ? 'fail' : 'ok', bad ? 'x' : 'check', bad ? `${name}에 실패했습니다` : `${name}${W().josa(name, '을/를')} 마쳤습니다${flag}`, [sys, [ask, got].filter(Boolean).join(' → ')].filter(Boolean).join(' · '));
    }
    if (r.kind === 'skill') return wrap('ok', 'check', '스킬 문서를 읽었습니다', UI.skillLabel(r.data, true).label);
    if (r.kind === 'file') return wrap('ok', 'check', '결과를 적었습니다', r.text);
    if (r.kind === 'error') return wrap('fail', 'x', r.text, '');
    return '';
  }
  // 단계 줄(키트 .stream-phases): 실제 사건에서만 나온다 — 일 받기 → (부른 도구들, 부른 차례대로) → 결과 제출. 시간으로 넘기지 않는다
  function phasesOf(s) {
    const list = s.awaiting ? [{ name: '일 받기', state: 'now' }] : [];
    lineRows(s).filter(r => r.kind !== 'error').forEach(r => {
      const name = r.kind === 'tool' ? W().toolName(r.tool).replace(/\s*\(.*\)\s*$/, '') : r.kind === 'skill' ? '스킬 읽기' : '결과 작성';      // 단계 줄에는 짧은 이름만(괄호 설명은 아래 줄에 있다)
      const state = r.kind === 'tool' && r.status === 'running' ? 'now' : 'done';
      const last = list[list.length - 1];
      if (last && last.name === name) last.state = state; else list.push({ name, state });
    });
    if (!s.awaiting && !list.some(x => x.state === 'now')) list.push({ name: '다음 행동 정하기', state: 'now' });
    list.push({ name: '결과 제출', state: 'todo' });
    const MAX = 5;
    return list.length > MAX ? [{ name: `앞 단계 ${list.length - MAX + 1}개`, state: 'done' }, ...list.slice(-(MAX - 1))] : list;
  }
  // 일하는 중인 AI 단계: 실시간 상자(머리 · 단계 줄 · 한 줄씩 붙는 줄). seen: 이미 그린 줄(새 줄만 한 번 비친다)
  function liveBox(s, seen) {
    const rows = lineRows(s);
    const lines = rows.map(r => { const fresh = seen && !seen.has(r.key); if (seen) seen.add(r.key); return lineOf(r, true, fresh); }).join('');
    const note = [...(s.rows || [])].reverse().find(r => r.kind === 'note' && !r.minor);
    const lastTool = rows[rows.length - 1];
    const typing = note && (!lastTool || String(note.t0) >= String(lastTool.t1 || lastTool.t0)) ? `<div class="typing">${e(note.text.slice(0, NOTE_MAX_CHARS))}</div>` : '';
    const actor = s.actor || 'AI 에이전트';
    const conn = window.hydStream && !hydStream.connected() ? `<p class="stream-lost" role="status">연결이 끊겼습니다 — 다시 이으면 이어서 보입니다. 그동안은 2초마다 다시 읽습니다.</p>` : '';
    return `<div class="stream" data-cr-live><div class="stream-head"><i class="dot" data-tone="brand" data-live></i><span><b>${e(actor)}</b><span class="muted">${e(W().josa(actor, '이/가'))} ${s.awaiting ? '일을 받기를 기다리는 중' : '일하는 중'}</span></span>${s.t0 ? `<span class="elapsed num" data-since="${e(s.t0)}">${e(fmtMs(Date.now() - ts(s.t0)))}</span>` : ''}</div>${conn}
      <div class="stream-phases">${phasesOf(s).map(p => `<span class="phase" data-state="${p.state}"><i></i>${e(p.name)}</span>`).join('')}</div>
      <div class="stream-log" data-cr-livelog>${lines || `<div class="line">${UI.icon('circle-dashed')}<span class="line-text muted">${s.awaiting ? 'AI 워커가 이 일을 가져가면 한 일이 여기에 한 줄씩 붙습니다.' : '아직 부른 도구가 없습니다. 도구를 부르면 한 줄씩 붙습니다.'}</span><span></span></div>`}</div>${typing}</div>`;
  }

  // AI 단계의 첫 화면에 놓을 것(5-2): 결론 문장 · 근거(원인 · 판단을 가른 값 · 까닭) · 비교한 조치. 모두 서버가 준 값에서만 뽑는다 — 없으면 그 줄을 그리지 않는다
  function agentFront(s, m) {
    const v = m.v || {}, w = s.w, sources = (m.inst.variable_sources || {});
    const produced = Object.entries(sources).filter(([, x]) => x && x.kind === 'workitem' && x.id === w.id).map(([k]) => k);
    const agentCount = m.steps.filter(x => x.type === 'agent').length;
    const owns = k => produced.includes(k) || (agentCount === 1 && !produced.length);
    const recorded = w.output?.decision || w.draft?.decision;
    const recordedId = w.output?.decision_id || w.draft?.decision_id || (produced.includes('decision_id') ? m.decision?.id : null);
    const d = owns('decision') ? (recorded ? UI.recordedDecision(m.decision, recorded, recordedId) : m.decision) : null;
    const gc = owns('guide_card') || owns('cause') ? v.guide_card : null;
    const top = gc && typeof gc === 'object' ? ((gc.causes || []).find(c => c.id === (v.cause || gc.topCause)) || (gc.causes || []).find(c => c.id === gc.topCause) || (gc.causes || [])[0]) : null;
    const cause = owns('cause') && v.cause ? (top && top.id === v.cause ? top.name : nm(v.cause)) : '';
    const opts = d && (d.options || []).length ? [...d.options].sort((a, b) => (b.id === d.recommended) - (a.id === d.recommended) || (b.feasible - a.feasible) || ((a.rank || 99) - (b.rank || 99))) : [];
    const rec = opts.find(o => o.id === d.recommended) || null;
    const recName = rec ? W().text(rec.name) : '';
    const mock = rec && UI.evaluationInfo(rec, d).state === 'analysis';
    let verdict = '';
    if (rec && cause) verdict = `원인은 ${cause}${W().josa(cause, '으로/로')} 보고, 「${recName}」${W().josa(recName, '을/를')} ${mock ? '모의 1순위로 계산했습니다' : '추천합니다'}.`;
    else if (rec) verdict = `조치 ${opts.length}개를 비교해 「${recName}」${W().josa(recName, '을/를')} ${mock ? '모의 1순위로 계산했습니다' : '추천합니다'}.`;
    else if (cause) verdict = `원인을 ${cause}${W().josa(cause, '으로/로')} 판단했습니다.`;
    // 결론 아래 한 줄: 추천안의 예측 · 좋아지는 것 · 감수할 것(승인 카드와 같은 함수 — approvalCard.js reasons)
    const sub = rec && window.hydApprove ? hydApprove.reasons(rec, d).slice(0, 3).join(' · ') : '';
    // 근거: 원인(고장 유형) → 원인 판정에 쓴 관측값(잰 값과 기준, 여섯 줄까지) → 판단 엔진이 그 안에 대해 한 말
    const evid = [];
    if (cause) evid.push(['network', `지식 지도의 원인 후보 가운데 <b>${e(cause)}</b>${W().josa(cause, '이/가')} 관측값과 맞습니다${top && top.failureMode ? ` <span class="muted">— 고장 유형: ${e(top.failureMode)}</span>` : ''}.`]);
    const tagOf = x => x.tag || (x.coverage && x.coverage.tag) || '';      // 증거가 읽은 시계열 태그(단위를 여기서 찾는다)
    const unit = x => tagOf(x) ? W().unit(String(tagOf(x)).toLowerCase()) : '';
    (top ? (top.evidence || []).filter(x => x && x.name && x.value != null).slice(0, 6) : []).forEach(x =>
      evid.push(['activity', `<b>${e(x.name)} ${e(W().num(x.value))}${unit(x) ? ' ' + e(unit(x)) : ''}</b>${x.threshold != null ? ` — 기준 ${e(W().sym(x.expect))} ${e(W().num(x.threshold))}${unit(x) ? ' ' + e(unit(x)) : ''}${x.status ? `, ${x.passed ? '맞음' : '아님'}` : ''}` : ''}`]));
    if (rec) {
      const ref = rec.sopId || (((rec.steps || []).find(x => x.manual && x.manual.ref) || {}).manual || {}).ref;
      const said = window.hydApprove ? W().text(hydApprove.sentenceAbout(d.explanation, rec.name)) : '';
      if (said) evid.push(['scale', e(said)]);
      else if (Number.isFinite(+rec.score) && opts.length > 1) evid.push(['scale', `조치 ${opts.length}개를 순위 식으로 견줘 <b>「${e(recName)}」</b>${ref ? ` <span class="muted mono">${e(ref)}</span>` : ''}${W().josa(recName, '이/가')} <b class="num">${e(W().num(+rec.score))}점</b>으로 가장 높았습니다.`]);
    }
    return { verdict, sub, evid, opts, rec, d, mock };
  }
  // 후보 비교 표(키트 .opts): 순위 · 이름(둘째 줄에 진 까닭) · 종류 · 점수 · 막대 · 승인 역할. 고른 줄은 제품색
  function optsTable(f) {
    const { opts, rec, d } = f;
    const KIND = { control: UI.t('chip.control'), work_order: UI.t('chip.workOrder') };
    const cost = o => W().purchaseEconomics(o);
    const score = o => !o.feasible ? '제외' : cost(o) ? W().purchaseCostLabel(o) : Number.isFinite(+o.score) && o.score !== null ? W().num(+o.score) : '';
    const max = Math.max(0, ...opts.filter(o => o.feasible && !cost(o) && Number.isFinite(+o.score)).map(o => +o.score));
    const why = o => {
      if (rec && o.id === rec.id) return '';
      if (!o.feasible) return W().text(((o.violations || [])[0] || {}).annotation || ((o.violations || [])[0] || {}).rule || '규정 위반');
      const pen = [...(o.penalties || []), ...(o.warnings || [])].map(x => W().text(x.annotation || x.message || '')).filter(Boolean)[0];
      return [window.hydApprove && rec ? hydApprove.partDiff(o, rec, opts) : '', pen ? `감점 · 경고: ${pen}` : ''].filter(Boolean).join(' / ');
    };
    const has = { kind: opts.some(o => KIND[o.kind]), bar: max > 0, role: opts.some(o => o.approver && o.approver.name) };
    const rows = opts.map((o, i) => `<tr${rec && o.id === rec.id ? ' data-pick' : ''}${o.feasible ? '' : ' data-out'}><td><span class="rank num">${e(o.rank || i + 1)}</span></td>
      <td><b>${e(W().text(o.name))}</b>${o.sopId ? ` <span class="muted mono">${e(o.sopId)}</span>` : ''}${why(o) ? `<span class="opts-why">${e(why(o))}</span>` : ''}</td>
      ${has.kind ? `<td>${e(KIND[o.kind] || '')}</td>` : ''}<td class="num">${e(score(o))}</td>${has.bar ? `<td>${o.feasible && !cost(o) && Number.isFinite(+o.score) ? `<div class="bar"><i style="width:${Math.max(0, Math.round(+o.score / max * 100))}%"></i></div>` : ''}</td>` : ''}${has.role ? `<td>${e((o.approver && o.approver.name) || '')}</td>` : ''}</tr>`).join('');
    return `<div class="table-container"><table class="opts"><thead><tr><th></th><th>후보</th>${has.kind ? '<th>종류</th>' : ''}<th>점수</th>${has.bar ? '<th></th>' : ''}${has.role ? '<th>승인 역할</th>' : ''}</tr></thead><tbody>${rows}</tbody></table></div>`;
  }
  function agentCard(s, m, gaps, seen) {
    const failed = ['fail', 'stop', 'bad'].includes(s.state);
    if (s.live && !failed) return liveBox(s, seen);
    const f = agentFront(s, m);
    const lines = lineRows(s), tools = (s.rows || []).filter(r => r.kind === 'tool').length;
    const dur = s.t0 && s.t1 ? fmtMs(ts(s.t1) - ts(s.t0)) : '';
    let result;
    if (f.verdict) result = `<div class="result"><div class="result-label">${UI.icon('sparkles', 'ic-sm')}결론</div><div class="result-main">${e(f.verdict)}</div>${f.sub ? `<div class="result-sub">${f.sub}</div>` : ''}</div>`;
    else {
      // 결론 값이 없는 끝난 단계: 실패 · 멈춤이면 서버가 남긴 오류 문장, 아니면 그 단계의 한 문장
      const err = [...(s.rows || [])].reverse().find(r => r.kind === 'error');
      const stopped = ['fail', 'stop'].includes(s.state);
      const text = (PREFIX[s.state] || (s.state === 'stop' ? `${s.stopNote || '멈춤'} — ` : '')) + (stopped && err ? err.text : stopped ? '결론을 내지 못하고 끝났습니다.' : s.sentence || '');
      result = `<div class="result"><div class="result-label">${UI.icon(stopped ? 'circle-alert' : 'sparkles', 'ic-sm')}${stopped ? '결론 없음' : '결론'}</div><div class="result-main">${e(text)}</div></div>`;
    }
    const evid = f.evid.length ? `<details class="fold" open data-k="${e(s.key + ':evid')}"><summary>근거<span class="muted">${f.evid.length}가지</span></summary><div class="fold-body"><ul class="evid">${f.evid.map(([ic, html]) => `<li>${UI.icon(ic)}<span>${html}</span></li>`).join('')}</ul></div></details>` : '';
    const alts = f.opts.length ? `<details class="fold" data-k="${e(s.key + ':opts')}"><summary>후보 비교<span class="muted">${f.opts.length}개${f.rec ? ` 가운데 ${f.mock ? '모의 ' : ''}1위` : ''}</span></summary><div class="fold-body" data-flush>${optsTable(f)}</div></details>` : '';
    const secs = [...(s.sections || [])].filter(Boolean).filter(x => !(f.opts.length && /^비교한 대안/.test(x.title)));      // 바로 위 「후보 비교」와 같은 것은 또 두지 않는다
    const exec = `<details class="fold" data-k="${e(s.key + ':more')}"><summary>실행 기록<span class="muted">도구 호출 ${tools}번${dur ? ` · ${e(dur)}` : ''}</span></summary><div class="fold-body cr-detail" data-flush>
      ${lines.length ? `<div class="stream-log cr-lines">${lines.map(r => lineOf(r, false, false)).join('')}</div>` : '<p class="muted">도구 호출 기록이 없습니다.</p>'}
      ${factsLine(s)}${foldsHtml(s, secs)}${stepLink(s)}${idsLine(s)}${gapLines(gaps)}</div></details>`;
    return `<div class="step-card">${result}${evid}${alts}${exec}</div>`;
  }
  // 한 단계의 조각 셋: 표시 아이콘 · 머리(이름 · 누가 · 시각) · 본문
  function stepParts(s, i, m, gaps, mine, seen) {
    const dur = s.t0 && s.t1 && s.type !== 'start' && s.type !== 'timer' && ts(s.t1) - ts(s.t0) >= 0 ? fmtMs(ts(s.t1) - ts(s.t0)) : '';
    const waiting = s.live && !s.t1 && !['fail', 'stop'].includes(s.state);
    const when = s.t0 ? `<span class="step-time num" title="${e(UI.dateTime(s.t0))}">${e(hhmmss(s.t0))}${waiting ? (s.lane === 'person' ? '부터 기다림' : ' 시작') : dur ? ` · ${e(dur)}` : ''}</span>` : '';
    const names = [...new Set(String(s.actor || '').split(' · ').filter(Boolean))];
    const myTurn = mine && s.w && mine.has(s.w.id);
    const who = `<span class="step-who">${UI.icon(WHO_ICON[s.lane] || 'cog')}${e((names.length ? names : [LANE[s.lane]]).join(' · '))}${myTurn ? ' · 내 차례' : ''}${s.gen ? ` · ${e(s.gen + 1)}회차` : ''}</span>`;
    const hold = s.state === 'wait' && s.w && s.w.status === 'PENDING' ? UI.chipText('보류', 'warning') : '';
    const head = `<span class="step-title">${e(s.title)}</span>${who}${hold}${when}`;
    if (s.type === 'agent') return { mark: markIcon(s), head, body: agentCard(s, m, gaps, seen) };
    const pre = PREFIX[s.state] || (s.state === 'stop' ? `${s.stopNote || '멈춤'} — ` : '');
    const secs = (s.sections || []).filter(Boolean);
    const inside = factsLine(s) + sectionsHtml(s, secs) + stepLink(s) + idsLine(s) + gapLines(gaps);
    const waitsMe = s.live && s.now && s.lane === 'person';      // 사람을 기다리는 단계는 문장 하나(무엇을 하면 넘어가는지)
    const body = `<p class="step-say">${e(waitsMe ? s.now : pre + (s.sentence || ''))}</p>${s.liveBox || ''}${s.live && s.now && !waitsMe && !s.liveBox ? `<p class="step-now"><i class="dot" data-tone="brand" data-live></i><span>${e(s.now)}</span></p>` : ''}
      ${inside ? `<details class="fold" data-plain data-k="${e(s.key + ':more')}"><summary>자세히</summary><div class="fold-body cr-detail">${inside}</div></details>` : ''}`;
    return { mark: markIcon(s), head, body };
  }
  /* 남은 단계: 정해진 데까지만 화살표로 잇고, 길이 갈리는 곳부터는 가지마다 한 줄씩 적는다 — 어느 가지로 갈지는 아직 나지 않은 결과가 정하므로
     한 길(「… → 결과 보고: 정상」)을 미리 골라 적지 않는다. 가지 안에서 또 갈리면 거기까지만 적고 그 갈림의 이름을 댄다 */
  const PLAIN_END = new Set(['끝', '종료', '완료', 'end', 'End', '']);
  function restHtml(rest, fork) {
    const arrow = UI.icon('arrow-right'), chain = names => names.map(n => `<span>${e(UI.flowName(n))}</span>`).join(arrow);
    const line = rest.length ? `<div class="rest">${chain(rest.map(n => n.name))}</div>` : '';
    if (!fork) return line;
    const q = String(fork.name || '').replace(/\?$/, '').trim();
    const branch = b => {
      const tail = b.more ? `<span class="muted">「${e(UI.flowName(b.more))}」에서 다시 갈림</span>` : b.end != null ? `<span class="muted">${PLAIN_END.has(String(b.end).trim()) ? '처리 완료' : `처리 완료(${e(UI.flowName(b.end))})`}</span>` : '';
      const parts = [b.steps.length ? chain(b.steps) : '', tail].filter(Boolean).join(arrow);
      return `<li><b>${e(UI.flowSeq(b.label) || b.label || '조건에 맞으면')}</b>${parts ? arrow + parts : ''}</li>`;
    };
    return `${line}<p class="rest-fork">${rest.length ? '그 뒤 ' : '이 단계가 끝나면 '}${q ? `「${e(UI.flowName(q))}」에 따라` : '결과에 따라'} 길이 갈립니다.</p><ul class="rest-branches">${fork.branches.map(branch).join('')}</ul>`;
  }

  // 「기록에 없는 것」을 그 단계의 접기 안으로 보낸다: 종류별로 그 말이 가리키는 단계(없으면 마지막 단계)
  function gapsByStep(m) {
    const uniq = [...new Map(m.gaps.map(g => [g.key, g])).values()].sort((a, b) => (b.strong ? 1 : 0) - (a.strong ? 1 : 0));
    const steps = m.steps, last = t => [...steps].reverse().find(t);
    const home = g => {
      const k = g.key;
      if (k.startsWith('noev:')) return k.slice(5);
      if (k === 'button' || k === 'link') return 'start';
      if (['cut', 'blocked', 'agents', 'skill', 'think', 'dec', 'prov'].includes(k)) return (last(s => s.type === 'agent') || {}).key;
      if (k === 'people' || k === 'who') return (last(s => s.type === 'approve') || last(s => s.lane === 'person' && s.type !== 'start') || {}).key;
      if (k === 'mail') return (last(s => s.type === 'system' && /메일/.test(s.sentence || '')) || {}).key;
      if (k === 'reobs') return (last(s => s.type === 'check') || {}).key;
      if (k === 'inc') return (last(s => s.w && /^incident:/.test(s.w.tool || '')) || {}).key;
      return null;
    };
    const out = new Map();
    uniq.forEach(g => { const key = (steps.find(s => s.key === home(g)) || steps[steps.length - 1] || {}).key; if (!key) return; if (!out.has(key)) out.set(key, []); out.get(key).push(g); });
    return out;
  }

  /* ================================================================ 컨트롤러: mount(host, opts) → { update(view), ingest(event) }
     opts.mine()  — 지금 내가 처리할 작업 id 묶음(그 단계에 「내 차례」를 붙인다)
     opts.onDraw(model, host) — 그린 뒤 부른다. 단계마다 [data-step-slot] 칸이 있고 그 안은 부른 쪽이 채운다(멈춘 단계의 복구 단추 등) — 다시 그려도 그 칸은 건드리지 않는다 */
  // 같은 목록은 처리 기록 여럿이 같이 쓴다(1분 보관). 실패는 던져서 처리 기록이 "기록에 없는 것"에 사유를 보인다
  const SHARED = {};
  async function sharedList(key) {
    const c = SHARED[key] || (SHARED[key] = { at: 0, rows: null });
    if (c.rows && Date.now() - c.at < SHARED_TTL_MS) return c.rows;
    c.rows = await getJ(API.process + SHARED_LISTS[key]); c.at = Date.now();
    return c.rows;
  }
  const mounted = new Set();
  function mount(host, opts = {}) {
    const C = { host, opts, view: null, live: new Map(), older: new Map(), ext: {}, raf: 0, fetching: false, pid: null };
    host.classList.add('cr');
    host.innerHTML = '<div data-cr-older></div><p class="cr-gapline" data-cr-names hidden role="status">이름 목록을 읽지 못해 일부 사람 · AI 에이전트의 이름이 보이지 않습니다. 다시 읽는 중입니다.</p><div class="steps" data-cr-steps role="list"></div>';
    C.seen = new Map();                                    // 단계마다 이미 그린 실시간 줄(새 줄만 한 번 비친다)
    host.addEventListener('click', ev => { if (ev.target.closest('[data-cr-older-btn]')) loadOlder(); });
    host.addEventListener('change', ev => {
      if (ev.target.matches('[data-cr-minor]')) ev.target.closest('.cr-sec-body, .fold-body')?.toggleAttribute('data-show-minor', ev.target.checked);
    });
    C.update = view => {
      if (!view || !view.instance) return;
      if (C.pid !== view.instance.proc_inst_id) { C.pid = view.instance.proc_inst_id; C.live.clear(); C.older.clear(); C.ext = {}; C.olderBefore = undefined; C.olderCount = 0; C.olderErr = null; C.seen.clear(); host.querySelector('[data-cr-steps]').innerHTML = ''; }
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
        // 앞쪽 기록은 실시간 줄(상한 LIVE_MAX_ROWS — 먼저 넣은 것부터 버림)과 따로 둔다: 사람이 더 보기로 받은 줄이 상한에 밀려 빠지지 않게(W1-30)
        rows.forEach(x => { if (x && x.id && !C.live.has(x.id)) C.older.set(x.id, x); });
        C.olderCount = (C.olderCount || 0) + rows.length;
        C.olderBefore = Array.isArray(r) ? null : (r.has_more ? r.before : null);
        if (!C.olderBefore) C.ext.olderDone = true;
        C.olderErr = null;
      } catch (err) { C.olderErr = err.message; }
      finally { C.olderBusy = false; draw(true); }
    }
    function drawOlder() {
      const box = host.querySelector('[data-cr-older]'); const pg = C.view && C.view.events_page;
      const more = pg && pg.has_more && !C.ext.olderDone;
      box.innerHTML = more ? `<div class="cr-older"><button type="button" class="btn" data-variant="outline" data-size="sm" data-cr-older-btn ${C.olderBusy ? 'disabled' : ''}>${C.olderBusy ? '받는 중…' : '이전 기록 더 보기'}</button><span class="muted">최근 ${e(W().num(pg.limit || 0))}줄${C.olderCount ? ` + 이전 ${e(W().num(C.olderCount))}줄` : ''}을 보고 있습니다. 앞쪽 기록이 더 있습니다.</span>${C.olderErr ? `<span class="muted" data-tone="danger">${e(C.olderErr)}</span>` : ''}</div>`
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
      const box = host.querySelector('[data-cr-steps]');
      let m;
      try { m = C.model = build(C.view, C.ext, [...C.older.values(), ...C.live.values()]); }
      catch (err) {
        console.error('단계 기록 그리기 실패', C.view?.instance?.proc_inst_id, err);   // 좌표(처리 건 · 줄)는 개발자 도구에
        box.innerHTML = `<div class="alert" data-variant="destructive">${UI.icon('circle-alert')}<h2>단계 기록을 그리지 못했습니다</h2><section>화면 프로그램 오류입니다. 화면을 새로 고쳐도 같으면 아래 오류 원문과 함께 시스템 관리자에게 알리세요.${UI.fold('오류 원문', `<pre class="code">${e(err.stack || err.message)}</pre>`)}</section></div>`;
        return;
      }
      drawOlder();
      host.querySelector('[data-cr-names]').hidden = !m.namesUnread;
      // 아직 울리지 않은 기한 타이머는 일어난 일이 아니다 — 단계 줄로 그리지 않는다(기한은 「내가 할 일」 카드와 「자세한 기록」의 단계 표에 있다)
      const shown = m.steps.filter(s => !(s.type === 'timer' && s.w && s.w.status !== 'DONE'));
      const gaps = gapsByStep(m), mine = opts.mine ? opts.mine() : null;
      // 남은 단계는 이름만 한 줄(진행 길의 남은 상자와 같은 차례)
      const path = m.running && window.hydFlow ? hydFlow.pathModel(C.view.definition || {}, C.view.workitems, m.inst) : null;
      const rest = path ? path.nodes.filter(n => n.state === 'todo') : [], fork = path ? path.fork : null;
      const want = shown.map(s => s.key).concat(rest.length || fork ? ['next'] : []);
      [...box.children].forEach(li => { if (!want.includes(li.dataset.key)) li.remove(); });
      const place = (key, i, state, parts) => {
        let li = [...box.children].find(x => x.dataset.key === key);
        if (!li) {
          li = document.createElement('div'); li.dataset.key = key; li.setAttribute('role', 'listitem');
          li.className = 'step fade-in';
          li.innerHTML = '<span class="step-mark"></span><div class="step-head"></div><div class="step-body"><div class="step-main"></div><div class="step-slot" data-step-slot></div></div>';
        }
        li.dataset.state = state;
        const mark = li.querySelector('.step-mark'), head = li.querySelector('.step-head');
        if (mark._icon !== parts.mark) { mark.innerHTML = UI.icon(parts.mark); mark._icon = parts.mark; }
        if (head._html !== parts.head) { head.innerHTML = parts.head; head._html = parts.head; }
        const main = li.querySelector('.step-main'), html = parts.body;
        if (force || main._html !== html) {
          // 펼친 접기 · 「보조 작업도 보기」 · 원문 칸의 스크롤 자리를 지킨다. 그 안에서 글을 쓰는 중이면 바꾸지 않는다(다음 그리기에서 반영)
          if (main.contains(document.activeElement) && /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName)) { schedule(); }
          else {
            const openK = new Set([...main.querySelectorAll('details[data-k][open]')].map(d => d.dataset.k));
            const minorOn = !!main.querySelector('[data-cr-minor]:checked');
            const scroll = new Map([...main.querySelectorAll('details[data-k][open] pre')].map((p, j) => [j, p.scrollTop]));
            const log = main.querySelector('[data-cr-livelog]'), follow = !log || log.scrollTop + log.clientHeight >= log.scrollHeight - 8;      // 맨 아래를 보고 있을 때만 새 줄을 따라간다
            const logTop = log ? log.scrollTop : 0;
            main.innerHTML = html; main._html = html;
            const next = main.querySelector('[data-cr-livelog]'); if (next) next.scrollTop = follow ? next.scrollHeight : logTop;
            main.querySelectorAll('details[data-k]').forEach(d => { if (openK.has(d.dataset.k)) d.open = true; });
            if (minorOn) { const c = main.querySelector('[data-cr-minor]'); if (c) { c.checked = true; c.closest('.cr-sec-body, .fold-body')?.setAttribute('data-show-minor', ''); } }
            [...main.querySelectorAll('details[data-k][open] pre')].forEach((p, j) => { if (scroll.get(j)) p.scrollTop = scroll.get(j); });
          }
        }
        if (box.children[i] !== li) box.insertBefore(li, box.children[i] || null);
        return li;
      };
      shown.forEach((s, i) => {
        if (!C.seen.has(s.key)) C.seen.set(s.key, new Set());
        const li = place(s.key, i, PIN[s.state] || 'todo', stepParts(s, i, m, gaps.get(s.key) || [], mine, C.seen.get(s.key)));
        li.dataset.lane = s.lane;
        if (s.live) li.dataset.live = ''; else delete li.dataset.live;
        if (s.w) li.dataset.step = s.w.id; else delete li.dataset.step;
      });
      // 남은 단계는 맨 아래 한 줄에 화살표로 이어 적는다(진행 길의 남은 상자와 같은 차례)
      if (rest.length || fork) place('next', shown.length, 'todo', { mark: 'circle-dashed', head: '<span class="step-title">남은 단계</span>', body: restHtml(rest, fork) });
      tickWatch();
      if (opts.onDraw) opts.onDraw(m, host);
    }
    C.draw = draw;
    mounted.add(C);
    return C;
  }
  // SSE 버스: 이벤트를 붙어 있는 처리 기록마다(각자 처리 건으로 거름)
  function onEvent(ev) { mounted.forEach(C => { if (!C.host.isConnected && !C.keep) { mounted.delete(C); return; } C.ingest(ev); }); }
  function wireBus() { if (window.hydStream && hydStream.subscribe) hydStream.subscribe(onEvent); else setTimeout(wireBus, 500); }
  wireBus();
  window.addEventListener('hyd-tool-payload',redrawAll);

  window.hydRecord = { mount, build, rowsOf, mounted, altHtml, knowledgeHtml, pretty, agentFront };   // altHtml · knowledgeHtml: 판단 한 건만으로 그리는 부분(시험 · 다른 화면)
})();
