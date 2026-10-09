/* A161-U1 — 실시간 처리 과정(trace). 처리 건 한 건이 흐르는 모습을 단계 카드 + 그 안의 행(도구 호출 · 에이전트 말 · 사람 질문 · 시스템 동작)으로
   끊김 없이 보여 준다. 같은 그리기 함수를 처리 건 상세(흐름 탭) · task 상세(처리 과정) · 에이전트에게 질문하기가 함께 쓴다.

   참고 화면(모방):
   - Dify 실행 추적 web/app/components/workflow/run/node.tsx · tracing-panel.tsx — 단계 행 = 꺾쇠 · 색 아이콘(24px 둥근 사각) · 이름 · 오른쪽 소요 시간 · 상태 아이콘(실행 중 회전),
     펼치면 입력 · 출력 코드 블록. status.tsx — 상태 · 걸린 시간 · 단계 수 요약 카드.
   - Dify 답변의 도구 호출 base/chat/chat/answer/tool-detail.tsx — "도구 사용" 한 줄, 펼치면 요청 · 응답 두 블록.
   - process-gpt-vue3 components/ui/EventTimeline.vue · shared/agentTimeline — tool_usage_started 가 행을 열고 tool_usage_finished 가 닫는다(짝은 tool_use_id),
     ds/components/PgToolSteps.vue — 왼쪽 세로선 위 도구 단계, 실행 중이면 13px 회전 표시. .pg-tl__hitl — 사람에게 묻는 상자.

   입력: 처리 건 view(정의 · 작업 행 · events) + liveStream 버스가 미는 SSE 이벤트(같은 id 는 한 번만). 2초 다시 읽기가 늦어도 SSE 가 먼저 그린다.
   그리기: 키가 있는 부분 갱신(단계 · 행). 이미 있는 행은 내용이 바뀐 것만 바꾸고 펼친 상자는 그대로 둔다 — 전체를 다시 그려 접히던 문제(A160 결함 15)를 없앤다.
   화면 정리: 모델 사용량(usage) · 실행 시작(run_start) 줄은 숨기고, 호스트 경로 · 모델 이름은 UI.clean, 원문 JSON 은 접기에만. */
(function () {
  Object.assign(UI.terms, {
    'trace.title': '처리 과정', 'trace.live': '실시간', 'trace.follow': '새 기록 따라가기', 'trace.empty': '아직 기록이 없습니다', 'trace.emptySub': '단계가 시작되면 여기에 바로 나타납니다',
    'trace.request': '요청', 'trace.response': '응답', 'trace.instruction': '에이전트에게 준 지시', 'trace.final': '에이전트 최종 답변', 'trace.file': '결과 파일 작성',
    'trace.truncated': '결과 잘림', 'trace.truncatedText': '결과가 너무 커서 일부만 받았습니다', 'trace.blocked': '안전 장치가 막음', 'trace.blockedText': '허용되지 않은 명령이라 실행하지 않았습니다',
    'trace.failed': '실패', 'trace.running': '실행 중', 'trace.took': '걸림', 'trace.waitHuman': '담당자의 입력을 기다리는 중', 'trace.waitAgent': 'AI 에이전트가 일을 받기를 기다리는 중',
    'trace.working': 'AI 에이전트가 작업하는 중', 'trace.thinking': '다음 행동을 정하는 중', 'trace.waitSystem': '시스템이 처리하는 중', 'trace.waitTimer': '정해진 시간까지 기다리는 중',
    'trace.submitted': '결과를 받아 다음 단계로 넘기는 중', 'trace.pending': '조건이 맞을 때까지 보류', 'trace.asked': '사람에게 묻는 중', 'trace.left': '남음', 'trace.overdue': '기한 지남',
    'trace.picked': '맡음', 'trace.done': '끝남', 'trace.outputs': '넘긴 값', 'trace.steps': '단계', 'trace.tools': '도구 호출', 'trace.status': '상태', 'trace.elapsed': '걸린 시간',
    'trace.gen': '회차', 'trace.detail': '단계 자세히', 'trace.answer': '답변', 'trace.more': '이전 기록 {n}건 더 보기', 'trace.case': '처리 건 전체', 'trace.next': '다음',
    'trace.kind.agent': 'AI 에이전트', 'trace.kind.human': '담당자', 'trace.kind.system': '시스템', 'trace.kind.timer': '대기', 'trace.kind.event': '이벤트',
    'trace.act.command': '설비 명령', 'trace.act.mail': '메일', 'trace.act.order': '발주', 'trace.act.receipt': '입고 확인', 'trace.act.schedule': '일정', 'trace.act.workorder': '정비 요청',
    'trace.act.record': '기록', 'trace.act.check': '확인', 'trace.act.approve': '승인',
  });

  /* ---------------------------------------------------------------- 시간 */
  function fmtMs(ms) {
    if (!Number.isFinite(ms) || ms < 0) return '';
    if (ms < 1000) return `${Math.round(ms)} ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)} s`;
    if (ms < 3600000) return `${Math.floor(ms / 60000)}분 ${Math.round((ms % 60000) / 1000)}초`;
    return `${Math.floor(ms / 3600000)}시간 ${Math.round((ms % 3600000) / 60000)}분`;
  }
  const ts = x => { const t = x ? Date.parse(x) : NaN; return Number.isFinite(t) ? t : null; };

  /* ---------------------------------------------------------------- 아이콘 (16px 선 그림, 브랜드 자산 없음) */
  const P = {
    agent: '<path d="M8 1.5l1.6 3.9 3.9 1.6-3.9 1.6L8 12.5 6.4 8.6 2.5 7l3.9-1.6z"/><path d="M13 11l.6 1.4L15 13l-1.4.6L13 15l-.6-1.4L11 13l1.4-.6z"/>',
    human: '<circle cx="8" cy="5" r="2.6"/><path d="M2.8 14c.6-2.8 2.7-4.3 5.2-4.3s4.6 1.5 5.2 4.3"/>',
    system: '<circle cx="8" cy="8" r="2.2"/><path d="M8 1.8v2M8 12.2v2M1.8 8h2M12.2 8h2M3.6 3.6l1.4 1.4M11 11l1.4 1.4M3.6 12.4L5 11M11 5l1.4-1.4"/>',
    timer: '<circle cx="8" cy="9" r="5.2"/><path d="M8 6.3V9l1.8 1.4M6.3 1.8h3.4"/>',
    command: '<path d="M9.2 1.6L3.4 9h4.2l-.8 5.4L12.6 7H8.4z"/>',
    mail: '<rect x="1.8" y="3.5" width="12.4" height="9" rx="1.4"/><path d="M2.2 4.3L8 8.8l5.8-4.5"/>',
    order: '<path d="M1.8 2.5h2l1.6 7.6h7l1.4-5.4H4.2"/><circle cx="6.4" cy="13" r="1"/><circle cx="11.6" cy="13" r="1"/>',
    receipt: '<path d="M2.2 5L8 2l5.8 3v6L8 14l-5.8-3z"/><path d="M2.2 5L8 8l5.8-3M8 8v6"/>',
    schedule: '<rect x="2" y="3" width="12" height="11" rx="1.4"/><path d="M2 6.5h12M5.2 1.6v2.6M10.8 1.6v2.6"/>',
    workorder: '<path d="M10.4 2.2a3.2 3.2 0 00-3.8 4.2L2.2 10.8l2.9 2.9 4.4-4.4a3.2 3.2 0 004.2-3.8L11.6 7.6 9.5 6.5 8.4 4.4z"/>',
    event: '<circle cx="8" cy="8" r="5.4"/>',
    gateway: '<path d="M8 1.8L14.2 8 8 14.2 1.8 8z"/>',
    check: '<path d="M3.4 8.4l3 3 6.2-6.6"/>',
    x: '<path d="M4.2 4.2l7.6 7.6M11.8 4.2l-7.6 7.6"/>',
    pause: '<path d="M6 4v8M10 4v8"/>',
    warn: '<path d="M8 2.2l6.2 11H1.8z"/><path d="M8 6.6v3.2M8 11.6v.1"/>',
    chevron: '<path d="M6 3.8L10.2 8 6 12.2"/>',
    tool: '<path d="M10.2 2.4a3 3 0 00-3.6 3.9L2.4 10.5l3.1 3.1 4.2-4.2a3 3 0 003.9-3.6L11.5 7.9 9.6 6.4 8.1 4.5z"/>',
    note: '<path d="M2.6 3h10.8v7.4H8.4L5 13.2v-2.8H2.6z"/>',
    file: '<path d="M4 1.8h5.2L12 4.6v9.6H4z"/><path d="M9 1.8v3h3"/>',
    ask: '<circle cx="8" cy="8" r="6"/><path d="M6.3 6.2a1.8 1.8 0 113 1.3c-.7.5-1.3.9-1.3 1.9M8 11.4v.1"/>',
    flag: '<path d="M3.4 14.2V2M3.4 2.6h8.8l-1.8 3 1.8 3H3.4"/>',
  };
  const icon = (k, cls = '') => `<svg class="tr-ic ${cls}" viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">${P[k] || P.event}</svg>`;
  const spinner = (cls = '') => `<span class="tr-spin ${cls}" role="img" aria-label="${esc(UI.t('trace.running'))}"></span>`;

  /* ---------------------------------------------------------------- 단계 종류 · 하는 일 (시나리오 이름을 쓰지 않는다: 정의의 tool · 이름 · 사건 종류로만) */
  const isAgent = w => !!(w.agent_orch || w.agent_mode) && (w.agent_orch === 'cliagents' || !!w.agent_mode);
  function stepKind(w, def) {
    const evDef = ((def || {}).events || []).find(e => e.id === w.activity_id);
    if (evDef) return evDef.eventDefinition === 'timer' ? 'timer' : 'event';
    if (isAgent(w)) return 'agent';
    if (!w.agent_orch && !w.agent_mode) return 'human';
    return 'system';
  }
  // 시스템 · 사람 단계가 하는 일(아이콘 · 칩). B(예약 · 정비창 대기 · 교체) · C(발주 · 메일 · 입고 확인) 같은 단계도 tool · 이름으로 잡힌다.
  function actionOf(w, act) {
    const s = `${(act && act.tool) || w.tool || ''} ${w.activity_name || ''} ${(act && act.name) || ''}`.toLowerCase();
    if (/incident:command|명령|command/.test(s)) return 'command';
    if (/mail|메일|smtp/.test(s)) return 'mail';
    if (/purchase|발주|order_create|po_create|:po\b/.test(s)) return 'order';
    if (/receipt|입고|goods_receipt|grn/.test(s)) return 'receipt';
    if (/schedule|예약|일정|calendar|정비창/.test(s)) return 'schedule';
    if (/wo_create|work.?order|정비 요청|작업지시/.test(s)) return 'workorder';
    if (/approve|승인/.test(s)) return 'approve';
    if (/reobserve|효과 확인|확인/.test(s)) return 'check';
    return '';
  }
  const ACT_ICON = { command: 'command', mail: 'mail', order: 'order', receipt: 'receipt', schedule: 'schedule', workorder: 'workorder', approve: 'human', check: 'timer' };

  /* ---------------------------------------------------------------- 이벤트 → 행 */
  const HIDDEN = d => d && (d.type === 'usage' || d.type === 'run_start' || d.session_id && !d.content && !d.message && d.type !== 'text');
  function brief(x, n = 140) {
    if (x == null) return '';
    if (typeof x === 'string') {
      if (/^select:/.test(x)) return x.slice(7).split(',').map(t => UI.toolName(t.trim())).join(', ').slice(0, n);
      return UI.clean(UI.idText(x.replace(/\s+/g, ' '))).slice(0, n);
    }
    if (Array.isArray(x) && x.length && x.every(y => y && typeof y === 'object' && typeof y.tool_name === 'string')) return `${x.length}건 · ` + x.map(y => UI.toolName(y.tool_name)).join(', ').slice(0, n);
    if (Array.isArray(x)) return `${x.length}건`;
    if (typeof x === 'object') {
      for (const k of ['query', 'sql', 'command', 'description', 'pattern', 'file_path', 'path', 'url', 'question']) if (typeof x[k] === 'string') return brief(x[k], n);
      return Object.keys(x).slice(0, 3).map(k => `${UI.terms['var.' + k] || k} ${typeof x[k] === 'object' && x[k] !== null ? (Array.isArray(x[k]) ? x[k].length + '건' : '…') : UI.clean(String(x[k])).slice(0, 40)}`).join(' · ').slice(0, n);
    }
    return String(x).slice(0, n);
  }
  const unescapeU = s => String(s).replace(/\\u([0-9a-fA-F]{4})/g, (m, h) => String.fromCharCode(parseInt(h, 16)));
  // a tool's result in one readable line: rows → "N건 · 값 · 값", an object → its first values, JSON text is parsed first (no raw JSON, no \uXXXX)
  function values(o, out = [], depth = 0) {
    if (out.length >= 4 || o == null || depth > 3) return out;
    if (typeof o === 'string') { const t = UI.clean(UI.idText(unescapeU(o).replace(/\s+/g, ' '))).trim(); if (t && t.length < 80 && !/^(ok|true|false|null)$/i.test(t)) out.push(t.slice(0, 40)); return out; }
    if (typeof o === 'number') { out.push(String(Math.round(o * 1000) / 1000)); return out; }
    if (Array.isArray(o)) { o.slice(0, 3).forEach(x => values(x, out, depth + 1)); return out; }
    if (typeof o === 'object') Object.values(o).forEach(x => values(x, out, depth + 1));
    return out;
  }
  function outBrief(x, n = 120) {
    if (x == null) return '';
    let v = x;
    if (typeof x === 'string') {
      const t = x.trim();
      if (/^[[{]/.test(t)) { try { v = JSON.parse(t); } catch (_) { return UI.clean(unescapeU(t).replace(/\s+/g, ' ')).slice(0, n); } }
      else return brief(x, n);
    }
    if (Array.isArray(v) && v.length && v.every(y => y && typeof y === 'object' && typeof y.tool_name === 'string')) return brief(v, n);
    if (Array.isArray(v) && v.length && v.every(y => y && typeof y === 'object' && y.type === 'text' && typeof y.text === 'string')) return outBrief(v.map(y => y.text).join('\n'), n);
    const vals = values(v);
    if (Array.isArray(v)) return (`${v.length}건` + (vals.length ? ' · ' + vals.join(' · ') : '')).slice(0, n);
    if (v && typeof v === 'object' && v.result === 'ok' && !vals.length) return '성공';
    return vals.join(' · ').slice(0, n) || brief(v, n);
  }
  const hhmmss = t => { const d = new Date(t); return Number.isNaN(d.getTime()) ? '' : d.toLocaleTimeString('en-GB', { hour12: false }); };
  function pretty(v) {
    if (v == null) return '';
    let s = v;
    if (typeof v === 'string') { try { s = JSON.parse(v); } catch (_) { return UI.clean(v).replace(/\\u([0-9a-fA-F]{4})/g, (m, h) => String.fromCharCode(parseInt(h, 16))).slice(0, 8000); } }
    return UI.clean(JSON.stringify(s, null, 2)).slice(0, 8000);
  }
  const codeBlock = (title, body, k) => body ? `<details class="tr-code" data-k="${esc(k)}"><summary>${esc(title)}</summary><pre>${esc(body)}</pre></details>` : '';

  // events of one work item → rows (chronological). tool start/end pair by tool_use_id (EventTimeline.vue 와 같은 짝짓기)
  function rowsOf(evs, w) {
    const rows = [], byTool = new Map();
    for (const e of evs) {
      const d = e.data || {};
      switch (e.event_type) {
        case 'tool_usage_started': {
          const r = { key: 'tool:' + (d.tool_use_id || e.id), kind: 'tool', status: 'running', t0: e.timestamp, tool: d.tool, title: UI.toolName(d.tool), text: brief(d.input), input: d.input };
          byTool.set(d.tool_use_id, r); rows.push(r); break;
        }
        case 'tool_usage_finished': {
          let r = byTool.get(d.tool_use_id);
          if (!r) { r = { key: 'tool:' + (d.tool_use_id || e.id), kind: 'tool', t0: null, tool: d.tool, title: UI.toolName(d.tool), text: '' }; rows.push(r); }
          const o = UI.outcome(d.output, d.is_error);
          Object.assign(r, { status: o.tone === 'ok' ? 'ok' : o.tone, t1: e.timestamp, output: d.output, result: o.text || outBrief(d.output, 140), badge: o.label });
          break;
        }
        case 'task_started':
          rows.push({ key: 'start:' + e.id, kind: 'start', status: 'ok', t0: e.timestamp, title: UI.t('trace.picked'), text: w && isAgent(w) ? UI.t('agent') : UI.who(d.name || d.role || ''), fold: d.task_description ? [UI.t('trace.instruction'), UI.clean(UI.idText(d.task_description))] : null });
          break;
        case 'task_working':
          if (HIDDEN(d)) break;
          if (d.type === 'text') { rows.push({ key: 'note:' + e.id, kind: 'note', status: 'ok', t0: e.timestamp, title: UI.t('td.note') || '에이전트 판단', note: UI.clean(UI.idText(d.content || '')) }); break; }
          if (d.type === 'file_artifact') { rows.push({ key: 'file:' + e.id, kind: 'file', status: 'ok', t0: e.timestamp, title: UI.t('trace.file'), text: UI.baseName(d.path || '') || '', fold: [UI.t('trace.response'), pretty(d.content)] }); break; }
          if (d.type === 'evidence') { rows.push({ key: 'ev:' + e.id, kind: 'note', status: 'ok', t0: e.timestamp, title: d.name || UI.t('td.basis') || '판단 근거', note: UI.clean(UI.idText(d.content || d.method || '')) }); break; }
          rows.push({ key: 'w:' + e.id, kind: 'system', status: 'ok', t0: e.timestamp, title: UI.clean(UI.logText(d.name || '')) || UI.t('stream.working'), text: brief(d.content || d.message || (d.by ? `${d.by}${d.role ? ' · ' + UI.who(d.role) : ''}` : ''), 160), raw: d.content || d.message ? null : d });
          break;
        case 'human_asked':
          rows.push({ key: 'ask:' + e.id, kind: 'ask', status: 'wait', t0: e.timestamp, job: e.job_id, title: UI.t('stream.asked'), note: typeof humanQuestionText === 'function' ? humanQuestionText(d) : (d.text || d.question || ''), options: Array.isArray(d.options) ? d.options.filter(x => typeof x === 'string') : [] });
          break;
        case 'human_response': {
          const ask = rows.find(r => r.kind === 'ask' && r.job === e.job_id); if (ask) ask.status = 'ok';
          rows.push({ key: 'ans:' + e.id, kind: 'answer', status: 'ok', t0: e.timestamp, title: UI.t('stream.answered'), text: `${d.answer || ''}${d.by ? ' — ' + d.by : ''}` });
          break;
        }
        case 'task_completed':
          rows.push({ key: 'done:' + e.id, kind: 'done', status: 'ok', t0: e.timestamp, title: UI.t('stream.done'),
            text: (d.output_keys || []).length ? `${UI.t('trace.outputs')} ${d.output_keys.map(k => UI.terms['var.' + k] || k).join(', ')}` : brief(d.text, 160),
            fold: d.text && (d.output_keys || []).length ? [UI.t('trace.final'), UI.clean(String(d.text))] : null });
          break;
        case 'task_cancelled':
          rows.push({ key: 'c:' + e.id, kind: 'stop', status: 'fail', t0: e.timestamp, title: e.job_id === 'TASK_CANCEL_REQUESTED' ? UI.t('stream.cancelReq') : e.job_id === 'TASK_CLOSED' ? UI.t('stream.closed') : UI.t('stream.stopped'), text: UI.clean(UI.logText(brief(d.goal || d.reason, 200))) });
          break;
        case 'error':
          rows.push({ key: 'err:' + e.id, kind: 'error', status: 'fail', t0: e.timestamp, title: d.name ? UI.clean(d.name) : UI.t('stream.error'), text: UI.clean(d.friendly || d.message || brief(d.raw_error || d.content, 200)), fold: d.raw_error ? [UI.t('raw'), UI.clean(d.raw_error)] : null });
          break;
        default: {
          const name = e.job_id === 'TASK_REVIEW_REQUIRED' ? e.job_id : e.event_type;
          rows.push({ key: 'x:' + e.id, kind: 'system', status: e.job_id === 'TASK_REVIEW_REQUIRED' ? 'wait' : 'ok', t0: e.timestamp, title: UI.eventName(name),
            text: UI.clean(UI.logText(d.message || d.note || d.friendly || d.reason || '') || ((d.assessment || {}).reasons || []).join('; ')), raw: d });
        }
      }
    }
    return rows;
  }

  /* ---------------------------------------------------------------- 모델: 처리 건 → 단계(작업 행) 목록 */
  function build({ view, events, onlyWorkitem }) {
    const def = (view && view.definition) || {};
    const acts = Object.fromEntries((def.activities || []).map(a => [a.id, a]));
    const order = Object.fromEntries((def.activities || []).map((a, i) => [a.id, i]));
    const all = new Map();
    (view ? view.events || [] : []).concat(events || []).forEach(e => { if (e && e.id && !all.has(e.id)) all.set(e.id, e); });
    const evs = [...all.values()].sort((a, b) => String(a.timestamp || '').localeCompare(String(b.timestamp || '')) || String(a.id).localeCompare(String(b.id)));
    const byTodo = new Map();
    evs.forEach(e => { const k = e.todo_id || ''; if (!byTodo.has(k)) byTodo.set(k, []); byTodo.get(k).push(e); });
    // a branch the engine cancelled before anyone worked on it (other path won, case ended) did not happen — the diagram shows it
    // as skipped; the trace lists only what ran. A person's close/cancel leaves events, so it stays.
    const neverRan = w => w.status === 'CANCELLED' && !byTodo.has(w.id) && /^cancelled:/i.test(String(w.log || '').trim());
    let wis = (view ? view.workitems || [] : []).filter(w => (w.status !== 'TODO' || byTodo.has(w.id)) && !neverRan(w));
    if (onlyWorkitem) wis = wis.filter(w => w.id === onlyWorkitem);
    const running = view && view.instance && view.instance.status === 'RUNNING';
    const steps = wis.map(w => {
      const kind = stepKind(w, def), act = acts[w.activity_id] || {};
      const rows = rowsOf(byTodo.get(w.id) || [], w);
      // the engine's own notes on the row (approval accepted, command issued …) — system steps have no events of their own
      if (kind !== 'agent') String(w.log || '').split(/;\s*/).map(s => s.trim()).filter(Boolean).forEach((seg, i) => rows.push({ key: 'log:' + i + ':' + seg.slice(0, 40), kind: 'system', status: 'ok', t0: null, title: UI.clean(UI.logText(seg)), small: true }));
      const live = running && ['IN_PROGRESS', 'SUBMITTED', 'PENDING', 'NEW'].includes(w.status);
      const toolsOpen = rows.some(r => r.kind === 'tool' && r.status === 'running');
      let state = w.status === 'DONE' || w.status === 'COMPLETED' ? 'ok' : w.status === 'CANCELLED' ? (w.draft_status === 'FAILED' ? 'fail' : 'skip') : w.draft_status === 'FAILED' ? 'fail'
        : !live ? 'idle' : w.status === 'PENDING' ? 'pending' : w.draft_status === 'HUMAN_ASKED' ? 'ask' : kind === 'human' ? 'wait' : kind === 'timer' ? 'timer' : 'run';
      const waitText = !live ? '' : w.draft_status === 'HUMAN_ASKED' ? UI.t('trace.asked') : w.status === 'PENDING' ? UI.t('trace.pending') : w.status === 'SUBMITTED' ? UI.t('trace.submitted')
        : kind === 'human' ? UI.t('trace.waitHuman') : kind === 'timer' ? UI.t('trace.waitTimer') : kind === 'agent' ? (w.consumer || rows.length ? (toolsOpen ? '' : UI.t('trace.thinking')) : UI.t('trace.waitAgent')) : UI.t('trace.waitSystem');
      return { key: w.id, w, kind, action: kind === 'system' || kind === 'human' ? actionOf(w, act) : '', name: UI.flowName(w.activity_name || act.name || w.activity_id), who: kind === 'agent' ? UI.t('agent') : UI.who(w.user_id),
        state, live, waitText, t0: w.start_date, t1: w.end_date, due: live ? w.due_date : null, gen: w.generation || 0, rows, tools: rows.filter(r => r.kind === 'tool').length, order: order[w.activity_id] ?? 999 };
    }).sort((a, b) => (ts(a.t0) ?? 9e15) - (ts(b.t0) ?? 9e15) || a.order - b.order);
    const loose = rowsOf(byTodo.get('') || [], null);       // instance-level records without a work item
    const inst = view && view.instance;
    return { steps, loose, inst, done: steps.filter(s => s.state === 'ok').length, total: (def.activities || []).length,
      tools: steps.reduce((n, s) => n + s.tools, 0), running: !!running, t0: inst && inst.start_date, t1: inst && inst.end_date };
  }

  /* ---------------------------------------------------------------- HTML */
  const STATE_ICON = { ok: ['check', 'ok'], fail: ['x', 'fail'], skip: ['x', 'skip'], wait: ['pause', 'wait'], ask: ['ask', 'wait'], pending: ['pause', 'wait'], timer: ['timer', 'wait'], idle: ['event', 'idle'], warn: ['warn', 'warn'], blocked: ['warn', 'warn'] };
  function stateMark(state) {
    if (state === 'run' || state === 'running') return spinner();
    const [k, cls] = STATE_ICON[state] || STATE_ICON.idle;
    return `<span class="tr-state ${cls}">${icon(k)}</span>`;
  }
  function durHtml(t0, t1, live) {
    if (t0 && t1) return `<span class="tr-dur">${esc(fmtMs(ts(t1) - ts(t0)))}</span>`;
    if (t0 && live) return `<span class="tr-dur live" data-since="${esc(t0)}">${esc(fmtMs(Date.now() - ts(t0)))}</span>`;
    return '';
  }
  function rowHtml(r, live) {
    const time = r.t0 ? `<time title="${esc(UI.dateTime(r.t0))}">${esc(hhmmss(r.t0))}</time>` : '<time></time>';
    if (r.kind === 'tool') {
      // Dify tool-detail: the line is the toggle; open it for 요청 · 응답 (원문은 여기에만)
      const sec = (title, body) => body ? `<div class="tr-code"><div class="tr-code-h">${esc(title)}</div><pre>${esc(body)}</pre></div>` : '';
      const io = sec(UI.t('trace.request'), pretty(r.input)) + sec(UI.t('trace.response'), pretty(r.output));
      const mark = r.status === 'running' && live ? spinner('sm') : stateMark(r.status === 'running' ? 'idle' : r.status);
      const line = `<b>${esc(r.title)}</b>${r.text ? `<span class="tr-txt">${esc(r.text)}</span>` : ''}${r.badge ? `<span class="chip tone-${r.status === 'fail' ? 'danger' : 'warning'} sm">${esc(r.badge)}</span>` : ''}${r.t1 ? durHtml(r.t0, r.t1) : r.status === 'running' && live ? durHtml(r.t0, null, true) : ''}`;
      return `<div class="tr-row tr-k-tool ${esc(r.status)}">${time}<span class="tr-mark">${mark}</span><div class="tr-main">
        ${io ? `<details class="tr-tool" data-k="${esc(r.key)}"><summary class="tr-sum"><div class="tr-line">${line}</div>${r.result && r.status !== 'running' ? `<div class="tr-res">${esc(r.result)}</div>` : ''}</summary><div class="tr-io">${io}</div></details>`
          : `<div class="tr-line">${line}</div>${r.result && r.status !== 'running' ? `<div class="tr-res">${esc(r.result)}</div>` : ''}`}</div></div>`;
    }
    const ic = { start: 'flag', note: 'note', file: 'file', ask: 'ask', answer: 'human', done: 'check', stop: 'x', error: 'warn', system: 'system' }[r.kind] || 'event';
    const body = r.kind === 'note' ? `<blockquote class="tr-note">${esc(r.note.slice(0, 700))}${r.note.length > 700 ? '…' : ''}</blockquote>${r.note.length > 700 ? codeBlock(UI.t('more'), r.note, r.key + ':more') : ''}`
      : r.kind === 'ask' ? `<div class="tr-hitl"><p>${esc(r.note || '')}</p>${r.options && r.options.length ? `<div class="row-wrap">${r.options.map(o => `<span class="chip tone-neutral sm">${esc(o)}</span>`).join('')}</div>` : ''}</div>` : '';
    return `<div class="tr-row tr-k-${esc(r.kind)} ${esc(r.status)}${r.small ? ' small' : ''}">${time}<span class="tr-mark">${icon(ic, 'k-' + r.kind)}</span><div class="tr-main">
      <div class="tr-line"><b>${esc(r.title)}</b>${r.text ? `<span class="tr-txt">${esc(r.text)}</span>` : ''}</div>${body}
      ${r.fold ? codeBlock(r.fold[0], r.fold[1], r.key + ':f') : ''}${r.raw ? codeBlock(UI.t('raw'), pretty(r.raw), r.key + ':raw') : ''}</div></div>`;
  }
  function stepHeadHtml(s) {
    const ik = s.kind === 'agent' ? 'agent' : s.kind === 'timer' ? 'timer' : s.kind === 'event' ? 'event' : ACT_ICON[s.action] || (s.kind === 'human' ? 'human' : 'system');
    const due = s.due ? (() => { const left = ts(s.due) - Date.now(); return `<span class="tr-due${left < 0 ? ' over' : ''}" data-until="${esc(s.due)}">${esc(left >= 0 ? `${fmtMs(left)} ${UI.t('trace.left')}` : UI.t('trace.overdue'))}</span>`; })() : '';
    const actChip = s.action ? `<span class="tr-act">${esc(UI.t('trace.act.' + s.action))}</span>` : '';
    return `<span class="tr-chev">${icon('chevron')}</span><span class="tr-block k-${esc(s.kind)}${s.live ? ' live' : ''}">${icon(ik)}</span>
      <span class="tr-name"><b>${esc(s.name)}</b><span class="tr-who">${esc(s.who)}</span>${actChip}${s.gen ? `<span class="tr-gen">${esc(s.gen + 1)}${esc(UI.t('trace.gen'))}</span>` : ''}</span>
      <span class="tr-meta">${s.tools ? `<span class="tr-count">${icon('tool')}${s.tools}</span>` : ''}${due}${durHtml(s.t0, s.t1, s.live)}${stateMark(s.state)}</span>`;
  }
  function waitRowHtml(s) {
    if (!s.live || !s.waitText) return '';
    return `<div class="tr-row tr-k-wait"><time></time><span class="tr-mark">${s.state === 'run' ? spinner('sm') : icon('pause', 'k-wait')}</span><div class="tr-main"><div class="tr-line"><span class="tr-shimmer">${esc(s.waitText)}</span></div></div></div>`;
  }

  /* ---------------------------------------------------------------- 키 있는 부분 갱신 */
  function patchChildren(box, items, keyOf, htmlOf, make) {
    const want = items.map(keyOf);
    const have = new Map([...box.children].filter(n => n.dataset && n.dataset.key).map(n => [n.dataset.key, n]));
    have.forEach((n, k) => { if (!want.includes(k)) n.remove(); });
    let prev = null;
    items.forEach((it, i) => {
      const k = want[i], html = htmlOf(it);
      let node = have.get(k);
      if (!node) { node = make(it, html); node.dataset.key = k; node.classList.add('tr-new'); setTimeout(() => node.classList.remove('tr-new'), 900); }
      else if (node._html !== html) morph(node, html);
      node._html = html;
      const next = prev ? prev.nextSibling : box.firstChild;
      if (next !== node) box.insertBefore(node, next);
      prev = node;
    });
  }
  // replace the content but keep every <details data-k> the user opened
  function morph(node, html) {
    const open = new Set([...node.querySelectorAll('details[data-k][open]')].map(d => d.dataset.k));
    const scroll = [...node.querySelectorAll('pre')].map(p => p.scrollTop);
    node.innerHTML = html;
    node.querySelectorAll('details[data-k]').forEach(d => { if (open.has(d.dataset.k)) d.open = true; });
    node.querySelectorAll('pre').forEach((p, i) => { if (scroll[i]) p.scrollTop = scroll[i]; });
  }
  const div = (cls, html) => { const d = document.createElement('div'); d.className = cls; d.innerHTML = html; return d; };

  /* ---------------------------------------------------------------- 컨트롤러: mount(host, opts) → { update(view), ingest(event), model } */
  function mount(host, opts = {}) {
    const C = { host, opts, view: null, live: new Map(), openSteps: new Map(), model: null, raf: 0, follow: opts.follow !== false, lastTouch: 0, shown: opts.shown || 60 };
    host.classList.add('tr');
    host.innerHTML = `${opts.summary ? '<div class="tr-summary" data-tr-summary></div>' : ''}<div class="tr-loose" data-tr-loose></div><div class="tr-steps" data-tr-steps></div><div class="tr-empty" data-tr-empty></div>`;
    host.addEventListener('click', e => {
      const head = e.target.closest('[data-tr-head]'); if (!head || !host.contains(head)) return;
      const step = head.closest('[data-key]'); const k = step.dataset.key;
      const open = !step.classList.contains('open'); C.openSteps.set(k, open); step.classList.toggle('open', open); head.setAttribute('aria-expanded', String(open));
      if (opts.onStep) opts.onStep(k, open);
    });
    const touch = () => { C.lastTouch = Date.now(); };
    host.addEventListener('wheel', touch, { passive: true }); host.addEventListener('touchmove', touch, { passive: true });
    C.update = view => { C.view = view; schedule(); };
    C.ingest = e => {
      if (!e || !e.id || C.live.has(e.id)) return false;
      if (opts.instance && e.proc_inst_id && e.proc_inst_id !== opts.instance()) return false;
      if (opts.workitem && e.todo_id !== opts.workitem()) return false;
      C.live.set(e.id, e); if (C.live.size > 3000) C.live.delete(C.live.keys().next().value);
      schedule(); return true;
    };
    C.reset = () => { C.live.clear(); C.openSteps.clear(); host.querySelector('[data-tr-steps]').innerHTML = ''; const l = host.querySelector('[data-tr-loose]'); if (l) l.innerHTML = ''; };
    function schedule() { if (C.raf) return; C.raf = requestAnimationFrame(() => { C.raf = 0; draw(); }); }
    function draw() {
      if (!host.isConnected && !opts.detachedOk) return;
      const view = C.view;
      const m = C.model = build({ view, events: [...C.live.values()], onlyWorkitem: opts.workitem ? opts.workitem() : null });
      const stepsBox = host.querySelector('[data-tr-steps]');
      const sum = host.querySelector('[data-tr-summary]');
      if (sum) sum.innerHTML = summaryHtml(m);
      if (opts.flat) {             // one work item (task 상세 · 질문하기): rows only, no step card
        const s = m.steps[0];
        const rows = s ? s.rows.slice(-C.shown) : [];
        const items = rows.map(r => ({ r, live: s.live }));
        if (s && s.live && s.waitText) items.push({ wait: s });
        patchChildren(stepsBox, items, x => x.wait ? 'wait-now' : x.r.key, x => x.wait ? waitRowHtml(x.wait) : rowHtml(x.r, x.live), (x, html) => div('tr-item', html));
        host.querySelector('[data-tr-empty]').innerHTML = items.length ? '' : UI.empty(UI.t('trace.empty'), UI.t('trace.emptySub'), 'compact');
        followNewest(stepsBox);
        return;
      }
      const loose = host.querySelector('[data-tr-loose]');
      if (loose) patchChildren(loose, m.loose.slice(-6), r => r.key, r => rowHtml(r, m.running), (r, html) => div('tr-item', html));
      // steps: the card stays, its head is rewritten only when it changed, its rows are patched by key (new rows fade in)
      patchChildren(stepsBox, m.steps, s => s.key, s => 'step', () => {
        const node = document.createElement('section'); node.className = 'tr-step';
        node.innerHTML = '<button type="button" class="tr-head" data-tr-head aria-expanded="false"></button><div class="tr-body"><div class="tr-rows"></div></div>'; return node;
      });
      m.steps.forEach(s => {
        const node = [...stepsBox.children].find(n => n.dataset.key === s.key); if (!node) return;
        const head = node.querySelector('[data-tr-head]'), hh = stepHeadHtml(s);
        if (head._html !== hh) { head.innerHTML = hh; head._html = hh; }
        const items = s.rows.map(r => ({ r })); if (s.live && s.waitText) items.push({ wait: s });
        const extra = opts.stepExtra ? opts.stepExtra(s) : ''; if (extra) items.push({ extra });
        patchChildren(node.querySelector('.tr-rows'), items, x => x.wait ? 'wait-now' : x.extra ? 'extra' : x.r.key, x => x.wait ? waitRowHtml(x.wait) : x.extra ? `<div class="tr-extra">${x.extra}</div>` : rowHtml(x.r, s.live), (x, html) => div('tr-item', html));
        if (!s.rows.length && !(s.live && s.waitText) && !node.querySelector('.tr-none')) node.querySelector('.tr-rows').innerHTML = `<p class="tr-none">${esc(s.live ? UI.t('trace.working') : UI.t('trace.empty'))}</p>`;
        else if (s.rows.length || (s.live && s.waitText)) node.querySelector('.tr-none')?.remove();
      });
      // open state: running · waiting steps open by default, finished ones folded unless the user opened them
      m.steps.forEach(s => {
        const node = [...stepsBox.children].find(n => n.dataset.key === s.key); if (!node) return;
        const user = C.openSteps.get(s.key);
        const open = user != null ? user : (s.live || (opts.openAll === true));
        node.classList.toggle('open', open); node.classList.toggle('live', s.live); node.dataset.state = s.state;
        const head = node.querySelector('[data-tr-head]'); if (head) head.setAttribute('aria-expanded', String(open));
      });
      host.querySelector('[data-tr-empty]').innerHTML = m.steps.length || m.loose.length ? '' : UI.empty(UI.t('trace.empty'), UI.t('trace.emptySub'), 'compact');
      followNewest(stepsBox);
      if (opts.onDraw) opts.onDraw(m);
    }
    function followNewest(box) {
      if (!C.follow || Date.now() - C.lastTouch < 6000) return;
      const fresh = box.querySelectorAll('.tr-new'); const last = fresh[fresh.length - 1];
      if (last && last.scrollIntoView && C.model && C.model.running) last.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
    C.draw = draw;
    TR.mounted.add(C);
    return C;
  }
  // Dify status.tsx: 상태 · 걸린 시간 · 단계 · 도구 호출
  function summaryHtml(m) {
    if (!m.inst) return '';
    const st = m.inst.status, tone = st === 'RUNNING' ? 'run' : st === 'COMPLETED' ? 'ok' : st === 'CANCELLED' || st === 'FAILED' ? 'fail' : 'idle';
    const el = m.t0 ? (m.t1 ? `<b>${esc(fmtMs(ts(m.t1) - ts(m.t0)))}</b>` : `<b data-since="${esc(m.t0)}">${esc(fmtMs(Date.now() - ts(m.t0)))}</b>`) : '<b>–</b>';
    return `<div class="tr-status ${tone}"><div><span>${esc(UI.t('trace.status'))}</span><b class="tr-st">${tone === 'run' ? spinner('sm') : stateMark(tone)} ${esc(UI.status(st))}</b></div>
      <div><span>${esc(UI.t('trace.elapsed'))}</span>${el}</div><div><span>${esc(UI.t('trace.steps'))}</span><b>${m.done} / ${m.total}</b></div><div><span>${esc(UI.t('trace.tools'))}</span><b>${m.tools}</b></div></div>`;
  }

  /* ---------------------------------------------------------------- 1초 시계: 경과 · 남은 시간 (다시 그리지 않고 글자만) */
  const TR = { mounted: new Set() };
  setInterval(() => {
    if (typeof document === 'undefined' || !document.querySelectorAll) return;
    const now = Date.now();
    document.querySelectorAll('[data-since]').forEach(n => { const t = ts(n.dataset.since); if (t != null) n.textContent = fmtMs(now - t); });
    document.querySelectorAll('[data-until]').forEach(n => { const t = ts(n.dataset.until); if (t == null) return; const left = t - now; n.textContent = left >= 0 ? `${fmtMs(left)} ${UI.t('trace.left')}` : UI.t('trace.overdue'); n.classList.toggle('over', left < 0); });
    TR.mounted.forEach(C => { if (!C.host.isConnected) TR.mounted.delete(C); });
  }, 1000);
  // every pushed SSE event goes to every mounted trace (each filters by its own instance / work item)
  function onEvent(e) { TR.mounted.forEach(C => C.ingest(e)); }

  window.hydTrace = { mount, build, rowsOf, onEvent, fmtMs, outBrief, hhmmss, icon, spinner, summaryHtml, rowHtml, waitRowHtml, TR };
})();
