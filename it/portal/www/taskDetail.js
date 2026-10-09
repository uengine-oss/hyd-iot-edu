/* U1 — task 상세 패널 (처리 건 · 흐름 탭). 흐름도의 task 노드나 단계 행을 누르면 그 단계가 한 일을 다섯 칸으로 보여 준다:
     ① 받은 입력(값과 어느 단계에서 왔는지) ② 처리 과정 타임라인(시작 · 에이전트 판단 메시지 · 도구 호출 · 판단 근거 · 사람 질문 · 완료/실패)
     ③ 판단 · 출력(판단 근거 요지 + 읽기 쉬운 표, 원문은 접기) ④ 다음 단계로 넘긴 값 ⑤ 진행 중이면 그 단계만의 실시간 흐름.
   단계 종류별: 에이전트(원인 점수 · 조건 / 카드 점수 구성 / 판단 메시지), 사람(받은 카드 · 권고 · 고른 것 · 사유 · 승인자 · 대기 경과),
   시스템(보낸 명령 · 설비 응답 · 재측정까지 남은 시간 · 회복 근거), 매뉴얼 추출(원문 · 구간 · 제안 요약)이 같은 패널에 나온다.
   처리 건 머리글 아래 "지금: <단계> — <누가> <무엇을 하는 중>" 한 줄(#instNow), 주소 #/instances/<처리 건>/task/<단계> 로 바로 열기.
   process-gpt-vue3 대응: apps/todolist/WorkItem.vue(업무 상세 탭: 진행 · 기록 · 산출물), apps/todolist/InstanceTimeline.vue
   (events 를 todo_id 로 묶어 업무 하나 = 메시지 하나, isAgentFinished), ui/WorkItemChat.vue(도구 입력 · 결과 접기),
   apps/todolist/InstanceProgress.vue(흐름도 단계 → 그 단계 산출물).
   읽는 것: GET /api/todolist/{id} (inputs · input_sources · 그 단계의 events · form), 처리 건 view(정의 · 변수 출처 · 승인),
   GET /api/decisions/{id}(카드 · 점수 구성 — 순위 · 선택 단계), GET /api/incidents/{id}(명령 · 응답 · 효과 확인 — 시스템 단계),
   GET /api/events/stream(liveStream.js 가 push 때 onEvent 로 넘겨 준다 — todo_id 로 거른다). 엔진을 부르지 않는다(읽기만). */
(function () {
  const LIVE = new Set(['IN_PROGRESS', 'SUBMITTED', 'PENDING', 'NEW']);
  const HIDDEN_OUTPUT = new Set(['text', 'cliagents_session_id']);
  const REFRESH_ON = new Set(['task_started', 'task_completed', 'task_cancelled', 'human_asked', 'human_response', 'error']);
  const DECISION_TOOLS = new Set(['formHandler:rank', 'formHandler:select_card']);
  const HASH_RE = /^#\/instances\/([^/]+)(?:\/task\/([^/]+))?$/;
  const OP = { lt: '<', lte: '≤', gt: '>', gte: '≥', eq: '=', '<': '<', '>=': '≥' };
  const TAG = { TS1: '유온 TS1', PS1: '압력 PS1', VS1: '진동 VS1' };
  const NOTE_SHOW = 600;
  const T = { wid: null, act: null, item: null, error: null, host: null, loading: false, rendered: null,
              dec: null, decId: null, decErr: null, inc: null, incId: null, incErr: null, incAt: 0, last: {}, pending: null };
  Object.assign(UI.terms, {
    'td.inputs': '받은 입력', 'td.trace': '처리 과정', 'td.output': '판단 · 출력', 'td.next': '다음 단계로 넘긴 값', 'td.close': '닫기',
    'td.noInputs': '이 단계는 입력 값을 읽지 않습니다', 'td.noOutput': '아직 출력이 없습니다', 'td.noNext': '넘긴 값 없음', 'td.noTrace': '아직 기록이 없습니다',
    'td.captured': '단계를 시작할 때 고정한 값', 'td.waiting': '필요한 값이 아직 없어 기다리는 중', 'td.current': '처리 건의 현재 값 (단계가 끝난 뒤 바뀌었을 수 있음)',
    'td.from': '에서 받음', 'td.start': '시작', 'td.assigned': '배정', 'td.running': '실행 중', 'td.result': '결과', 'td.error': '오류',
    'td.agentWorking': '에이전트가 작업하는 중…', 'td.humanWaiting': '담당자의 입력을 기다리는 중', 'td.systemWaiting': '시스템 응답을 기다리는 중',
    'td.engineWorking': '제출됨 · 다음 단계로 넘기는 중', 'td.pendingWait': '보류 · 조건이 맞을 때까지 대기', 'td.askWait': '사람의 답변을 기다리는 중',
    'td.delivered': '넘김', 'td.superseded': '다른 차수의 값으로 대체됨', 'td.notYet': '아직 넘기지 않음', 'td.consumers': '받는 단계', 'td.noConsumer': '받는 단계 없음',
    'td.cards': '받은 조치 카드', 'td.chosen': '고른 조치', 'td.reason': '사유', 'td.approver': '승인자', 'td.delivery': '승인 전달', 'td.sent': '보낸 명령', 'td.response': '설비 응답',
    'td.instruction': '에이전트에게 준 지시', 'td.tokens': '모델 사용량', 'td.options': '선택지', 'td.outputKeys': '출력', 'td.prose': '서술 결과',
    'td.planned': '아직 시작하지 않은 단계', 'td.plannedSub': '정의에 적힌 입력과 출력입니다', 'td.expects': '읽을 값', 'td.produces': '만들 값', 'td.who': '수행',
    'td.loadFail': '단계 상세를 읽지 못했습니다', 'td.liveOn': '실시간', 'td.model': '모델',
    // U1 추가: 판단 근거 · 사람 · 시스템 · 매뉴얼 · 지금
    'td.note': '에이전트 판단', 'td.noteMore': '판단 전문', 'td.basis': '판단 근거', 'td.finalText': '에이전트 최종 답변',
    'td.cause': '원인', 'td.prior': '사전확률', 'td.causeScore': '점수', 'td.conditions': '근거 조건', 'td.passedOf': '통과 근거',
    'td.causeFormula': '원인 점수 = 사전확률 × (통과한 근거 가중치 ÷ 전체 근거 가중치). 확인되지 않은 근거가 있으면 점수를 매기지 않습니다.',
    'td.rank': '순위', 'td.card': '카드', 'td.parts': '점수 구성', 'td.verdict': '판정', 'td.formula': '점수 식', 'td.rankRule': '순위 규칙', 'td.selectedBy': '선정 규칙',
    'td.recommended': '권고', 'td.differs': '권고와 다름', 'td.decState': '판단 결과 상태', 'td.wait': '대기', 'td.waitFor': '경과', 'td.dueLeft': '기한까지', 'td.overdue': '기한 지남',
    'td.timeout': '선택 기한이 지나 책임자 확인 단계로 넘어갔습니다', 'td.decFail': '조치 카드를 읽지 못했습니다',
    'td.cmdId': '명령 번호', 'td.ackWait': '설비 응답을 기다리는 중', 'td.ackDone': '설비가 실행함', 'td.ackRejected': '설비가 거부함', 'td.interlock': '인터록',
    'td.criterion': '회복 기준', 'td.remeasure': '재측정', 'td.remeasureIn': '재측정까지', 'td.remeasureDue': '재측정 시각 지남 · 판정 대기', 'td.extensions': '연장',
    'td.cleared': '경보 해제', 'td.recoveryBasis': '회복 근거', 'td.incFail': '사건 상태를 읽지 못했습니다', 'td.scaleNote': '모의 {sim} = 실제 {real} ({x}배속)',
    'td.source': '원문', 'td.pages': '쪽', 'td.chars': '자', 'td.segment': '담당 구간', 'td.feedback': '사람 검토 판정', 'td.sections': '절', 'td.procedures': '절차', 'td.warnings': '주의',
    'td.steps': '단계', 'td.pageReviews': '페이지 검토',
    'td.now': '지금', 'td.ended': '끝', 'td.nowTool': '도구 {tool} 호출 중', 'td.nowNote': '판단을 정리하는 중', 'td.nowBasis': '판단 근거를 기록함', 'td.nowStarted': '작업을 시작함',
    'td.nowClaimed': 'AI 일꾼이 작업 중', 'td.nowQueued': 'AI 일꾼이 집어 가기를 기다리는 중', 'td.nowAsk': '사람의 답변을 기다리는 중', 'td.nowSubmitted': '결과 제출 · 다음 단계로 넘기는 중',
    'td.nowHuman': '선택을 기다리는 중', 'td.nowCmd': '설비 응답을 기다리는 중', 'td.nowReobs': '효과를 확인하는 중', 'td.nowWo': '정비 시스템에 요청하는 중', 'td.nowPending': '보류 · 사람 확인 필요',
    'td.nowSystem': '처리하는 중', 'td.nothing': '지금 진행 중인 단계가 없습니다', 'td.seeOutput': '위 판단 · 출력의 값 그대로',
  });

  // 처리 건 변수의 화면 이름 — 정의 설명문에는 규칙 id(dec:…)·클래스 이름이 섞여 있어 이름표를 따로 둔다(이미 있는 것은 덮지 않음)
  Object.entries({ 'var.alert': '경보 메시지', 'var.guide_card': '원인 분석 카드', 'var.candidates': '조치 후보', 'var.compliance': '규정 판정', 'var.decision': '조치 카드 묶음',
    'var.decision_id': '조치 카드 묶음 번호', 'var.incident': '사건', 'var.commands': '설비 명령', 'var.chosen_option': '고른 조치 카드', 'var.incident_outcome': '사건 결과',
    'var.manual_source': '원문 문서', 'var.review_feedback': '사람 검토 판정', 'var.segment': '담당 구간', 'var.proposal': '추출 제안', 'var.ontology_catalog': '온톨로지 목록' })
    .forEach(([k, label]) => { if (!(k in UI.terms)) UI.terms[k] = label; });

  if (!UI.performers['legacy agent']) UI.performers['legacy agent'] = '내장 판단 파이프라인';   // process instance_mode._bridge_legacy_agent 의 이름

  const view = () => (window.hydInstances && window.hydInstances.I && window.hydInstances.I.view) || null;
  const vars = inst => Object.fromEntries((inst.variables_data || []).map(x => [x.key, x.value]));
  const workitemOf = wid => { const v = view(); return (v && v.workitems.find(w => w.id === wid)) || null; };
  const activityOf = (v, id) => ((v.definition || {}).activities || []).find(a => a.id === id) || null;
  const isEventNode = (v, id) => ((v.definition || {}).events || []).some(e => e.id === id);
  function latestFor(v, activityId) {
    return v.workitems.filter(w => w.activity_id === activityId).sort((a, b) => (b.generation || 0) - (a.generation || 0) || (b.start_date || '').localeCompare(a.start_date || ''))[0] || null;
  }
  const kindOf = w => (w.agent_orch === 'cliagents' || w.agent_mode) ? 'agent' : (!w.agent_orch && !w.agent_mode) ? 'human' : 'system';
  function varName(key, v) {
    const row = ((v.definition || {}).data || []).find(d => d.name === key);
    return UI.terms['var.' + key] || (row && row.description ? UI.idText(row.description.replace(/\s*[\(—(].*$/, '')) : key);
  }
  function fmtMs(ms) { return ms < 1000 ? `${Math.round(ms)} ms` : ms < 60000 ? `${(ms / 1000).toFixed(1)} s` : ms < 3600000 ? `${Math.floor(ms / 60000)}분 ${Math.round((ms % 60000) / 1000)}초` : `${Math.floor(ms / 3600000)}시간 ${Math.round((ms % 3600000) / 60000)}분`; }
  const num = x => typeof x === 'number' && Number.isFinite(x) ? (Number.isInteger(x) ? x.toLocaleString('ko-KR') : String(Math.round(x * 100) / 100)) : (x == null ? '–' : String(x));
  const signed = x => typeof x === 'number' && Number.isFinite(x) ? (x > 0 ? '+' : '') + num(x) : '미확인';
  function brief(x, n = 160) {
    if (x == null) return '';
    if (typeof x === 'string') {
      if (/^select:/.test(x)) return x.slice(7).split(',').map(t => UI.toolName(t.trim())).join(', ').slice(0, n);   // 도구 검색(ToolSearch) "select:mcp__…" → 도구 이름
      return UI.idText(x.replace(/\s+/g, ' ').slice(0, n));
    }
    if (Array.isArray(x) && x.length && x.every(y => y && typeof y === 'object' && typeof y.tool_name === 'string'))     // 도구 검색 결과: 찾은 도구 목록
      return `${x.length}건 · ` + x.map(y => UI.toolName(y.tool_name)).join(', ').slice(0, n);
    if (Array.isArray(x)) return `${x.length}건` + (x.length && typeof x[0] !== 'object' ? ' · ' + x.slice(0, 5).map(y => UI.idText(String(y))).join(', ') : x.length ? ' · ' + Object.keys(x[0]).slice(0, 4).join(', ') : '');
    if (typeof x === 'object') {
      if (typeof x.query === 'string') return brief(x.query, n);
      if (typeof x.sql === 'string') return brief(x.sql, n);
      return Object.keys(x).slice(0, 4).map(k => `${k}: ${typeof x[k] === 'object' && x[k] !== null ? (Array.isArray(x[k]) ? x[k].length + '건' : '…') : UI.idText(String(x[k])).slice(0, 40)}`).join(' · ').slice(0, n);
    }
    return String(x).slice(0, n);
  }
  // a JSON answer is pretty-printed (escaped \uXXXX become letters); prose stays as written
  function readable(text) {
    const s = String(text || '');
    try { return JSON.stringify(JSON.parse(s), null, 2).slice(0, 6000); }
    catch (_) { return s.replace(/\\u([0-9a-fA-F]{4})/g, (m, h) => String.fromCharCode(parseInt(h, 16))).slice(0, 6000); }   // the stored answer is cut at 2,000 chars
  }
  const rawFold = (v, k) => v == null ? '' : `<details class="fold small" data-k="${esc(k)}"><summary>${esc(UI.t('raw'))}</summary><pre>${esc(JSON.stringify(v, null, 2).slice(0, 6000))}</pre></details>`;
  const table = (head, rows) => `<div class="table-scroll"><table class="inst-table td-table"><thead><tr>${head.map(h => `<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`;
  const scoreLabel = k => UI.terms['score.' + k] || k;
  const timeScale = () => { const I = window.hydInstances && window.hydInstances.I; const x = I && I.mode && Number(I.mode.time_scale); return Number.isFinite(x) && x > 0 ? x : null; };

  /* ---------- 값 → 읽기 쉬운 HTML (키별 특수 렌더 → 일반 규칙) ---------- */
  function valueHtml(key, value, v, depth = 0) {
    const special = SPECIAL[key];
    if (special && value && typeof value === 'object') { const html = special(value, v); if (html) return html + rawFold(value, 'raw:' + key); }
    if (value == null) return `<span class="muted">${esc(UI.t('inst.noValue'))}</span>`;
    if (typeof value === 'boolean') return esc(value ? UI.t('yes') : UI.t('no'));
    if (typeof value === 'number') return esc(value.toLocaleString('ko-KR'));
    if (key === 'chosen_skill_kind' && (value === 'control' || value === 'work_order')) return esc(value === 'control' ? UI.t('chip.control') : UI.t('chip.workOrder'));
    if (typeof value === 'string' && key === 'pattern' && typeof PATTERN_LABEL !== 'undefined' && PATTERN_LABEL[value]) return esc(PATTERN_LABEL[value]);
    if (typeof value === 'string') return value.length > 240 ? `<span class="prose">${esc(UI.idText(value.slice(0, 240)))}…</span>${rawFold(value, 'raw:' + key)}` : esc(UI.idText(value));
    if (Array.isArray(value)) {
      if (!value.length) return `<span class="muted">${esc(UI.t('empty.noData'))}</span>`;
      if (value.every(x => typeof x !== 'object' || x === null)) return `<span class="row-wrap">${value.slice(0, 12).map(x => `<span class="chip tone-neutral sm">${esc(UI.name(String(x)) || UI.idText(String(x)))}</span>`).join('')}${value.length > 12 ? `<span class="muted">+${value.length - 12}</span>` : ''}</span>`;
      const cols = [...new Set(value.slice(0, 20).flatMap(x => Object.keys(x || {})))].slice(0, 6);
      return `${table(cols, value.slice(0, 20).map(x => `<tr>${cols.map(c => `<td>${esc(brief(x[c], 60))}</td>`).join('')}</tr>`))}${value.length > 20 ? `<p class="muted">… ${value.length - 20}건 더</p>` : ''}${rawFold(value, 'raw:' + key)}`;
    }
    const entries = Object.entries(value);
    if (!entries.length) return `<span class="muted">${esc(UI.t('empty.noData'))}</span>`;
    const dl = `<dl class="meta-list td-kv">${entries.slice(0, 16).map(([k, x]) => `<div><dt title="${esc(k)}">${esc(UI.terms['var.' + k] || k)}</dt><dd>${x !== null && typeof x === 'object' ? (depth < 1 ? valueHtml(k, x, v, depth + 1) : esc(brief(x, 100))) : esc(brief(x, 120) || UI.t('inst.noValue'))}</dd></div>`).join('')}</dl>`;
    return dl + (depth === 0 ? rawFold(value, 'raw:' + key) : '');
  }
  const optionName = o => (o && UI.idText(o.name || UI.name(o.id) || o.id)) || '';
  function condText(e) {
    const status = e.status || (e.passed === true ? 'PASS' : e.passed === false ? 'FAIL' : 'UNKNOWN');
    const tone = status === 'PASS' ? 'success' : status === 'FAIL' ? 'neutral' : 'warning';
    const label = status === 'PASS' ? UI.t('inc.pass') : status === 'FAIL' ? UI.t('inc.fail') : UI.t('inc.unknown');
    const rule = e.expect && e.threshold != null ? ` ${OP[e.expect] || e.expect} ${num(e.threshold)}` : '';
    return `<div class="td-cond">${UI.chipText(label, tone)} ${esc(UI.idText(e.name || e.id || ''))}${esc(rule)} <span class="muted">· ${esc(UI.t('inc.observed'))} ${esc(num(e.value))}${e.weight != null ? ` · 가중치 ${esc(num(e.weight))}` : ''}</span>${status === 'UNKNOWN' && (e.error || e.reason) ? ` <span class="muted">${esc(UI.idText(e.error || e.reason))}</span>` : ''}</div>`;
  }
  // 원인 점수 · 조건 표 (guide_card.causes — 내장 판단 경로는 agentsvc card.rank_causes 의 prior · score · evidence 그대로)
  function causesTable(causes, top) {
    if (!causes.length) return '';
    const scored = causes.some(c => c.prior != null || (c.evidence || []).length);
    return table([UI.t('td.cause'), UI.t('td.prior'), UI.t('td.causeScore'), UI.t('td.conditions')], causes.map(c => `<tr${c.id === top ? ' class="rec"' : ''}><td>${esc(UI.idText(c.name || UI.name(c.id)))}${c.id === top ? ' ' + UI.chipText(UI.t('dec.causeTop'), 'success') : ''}</td>
      <td>${esc(num(c.prior))}</td><td>${c.score == null && c.probability == null ? `<span class="muted">미확인</span>` : esc(num(c.score != null ? c.score : c.probability))}</td>
      <td>${(c.evidence || []).map(condText).join('') || `<span class="muted">${esc(UI.t('inc.noEvidence'))}</span>`}</td></tr>`)) + (scored ? `<p class="field-hint">${esc(UI.t('td.causeFormula'))}</p>` : '');
  }
  // decision.order: 내장 경로는 "1. 이름" 문자열, 실제 워커는 {id, name, rank, score, sopId, approver} 객체 목록 — 둘 다 읽기 쉬운 줄로
  function orderItem(x) {
    if (x && typeof x === 'object') return `<li>${esc(x.name || UI.name(x.id) || '')}${x.sopId ? ` <span class="muted">${esc(x.sopId)}</span>` : ''}${x.score != null ? `<span class="muted"> · ${esc(UI.t('card.score'))} ${esc(num(x.score))}</span>` : ''}${x.approver ? `<span class="muted"> · ${esc((String(x.approver).match(/\(([^)]+)\)\s*$/) || [])[1] || UI.idText(String(x.approver)))}</span>` : ''}</li>`;
    return `<li>${esc(UI.idText(String(x).replace(/^\d+\.\s*/, '')))}</li>`;
  }
  const SPECIAL = {
    decision(d) {
      const opts = d.options || [];
      if (!opts.length && !d.recommended && !(d.order || []).length) return '';
      const list = opts.length ? `<ol class="td-list">${opts.map(o => `<li>${esc(optionName(o))} ${o.id === d.recommended ? UI.chipText(UI.t('chip.recommended'), 'accent') : ''}${o.id === d.chosen ? UI.chipText(UI.t('chip.chosen'), 'success') : ''}${o.feasible === false ? UI.chipText(UI.t('chip.excluded'), 'danger') : ''}${o.score != null ? `<span class="muted"> · ${esc(UI.t('card.score'))} ${esc(num(o.score))}</span>` : ''}</li>`).join('')}</ol>`
        : (d.order || []).length ? `<ol class="td-list">${d.order.map(orderItem).join('')}</ol>` : '';
      return `${d.explanation ? `<p class="kv-line">${esc(UI.idText(d.explanation))}</p>` : ''}${list}`;
    },
    guide_card(g) {
      const causes = g.causes || [];
      const rec = (g.recommended || []).map(a => `<span class="chip tone-neutral sm">${esc(window.hydCards ? hydCards.actionLabel(a) : (a.code || a.name || ''))}</span>`).join('');
      const fm = typeof g.failureMode === 'object' ? (g.failureMode || {}).name : UI.name(g.failureMode);
      if (!causes.length && !rec && !fm) return '';
      return `${fm ? `<p class="kv-line"><b>${esc(UI.t('var.failure_mode'))}</b> ${esc(UI.idText(fm))}</p>` : ''}${g.withheld && (g.evidence_status || {}).reason ? `<p class="neg">${esc(g.evidence_status.reason)}</p>` : ''}
        ${causes.length ? `<p class="kv-line"><b>${esc(UI.t('inc.causes'))}</b></p>${causesTable(causes, g.topCause)}` : ''}${rec ? `<p class="kv-line"><b>${esc(UI.t('inc.recommended'))}</b></p><div class="row-wrap">${rec}</div>` : ''}`;
    },
    compliance(c) {
      const rows = Object.entries(c).filter(([id]) => !id.startsWith('_'));    // 워커가 붙인 _basis(판정 근거 · 쓴 사실 · 출처)는 후보가 아니다
      if (!rows.length || rows.some(([, x]) => !x || typeof x !== 'object')) return '';
      const basis = c._basis && typeof c._basis === 'object' ? c._basis : null;
      const why = basis && (basis.note || basis.engine) ? `<p class="kv-line"><b>판정 근거</b> ${esc(UI.idText([basis.note, basis.engine].filter(Boolean).join(' · ')))}</p>` : '';
      return why + table([UI.t('candidate'), UI.t('dec.col.result'), UI.t('fold.violations'), UI.t('fold.penalty')], rows.map(([id, x]) => `<tr><td>${esc(UI.name(id))}</td><td>${x.feasible === false ? UI.chipText(UI.t('chip.excluded'), 'danger') : UI.chipText(UI.t('inc.pass'), 'success')}</td><td>${esc((x.excluded || []).map(y => UI.idText(String(y))).join('; '))}</td><td>${esc([...(x.penalties || []), ...(x.warnings || [])].map(y => UI.idText(String(y))).join('; '))}</td></tr>`));
    },
    chosen_option(o) { return o.name ? `<span class="kv">${esc(UI.idText(o.name))}</span>${o.kind ? ' ' + UI.chipText(o.kind === 'control' ? UI.t('chip.control') : UI.t('chip.workOrder')) : ''}` : ''; },
    work_order(w) { return (w.ref || w.id) ? `<span class="kv mono">${esc(w.ref || w.id)}</span>${w.detail ? `<p class="kv-line">${esc(w.detail)}</p>` : ''}` : ''; },
    alert(a) { return a.alertId ? `<p class="kv-line">${esc(a.alertId)} · ${esc(UI.status(a.state))}${a.pattern ? ' · ' + esc((typeof PATTERN_LABEL !== 'undefined' && PATTERN_LABEL[a.pattern]) || UI.idText(a.pattern)) : ''}</p>` : ''; },
    // 매뉴얼 추출 처리 건: 원문 전문(pages)은 쏟지 않고 문서 · 쪽 수 · 글자 수만, 원문은 접기
    manual_source(s) {
      if (!Array.isArray(s.pages)) return '';
      const chars = s.pages.reduce((n, p) => n + String(p.text || '').length, 0);
      return `<p class="kv-line"><b>${esc(s.title || s.name || s.filename || s.source_id || '')}</b> · ${esc(s.pages.length)}${esc(UI.t('td.pages'))} · ${esc(chars.toLocaleString('ko-KR'))}${esc(UI.t('td.chars'))}</p>`;
    },
    // C1: 추출이 가리킬 수 있는 기존 온톨로지 id 목록 — 전부 쏟지 않고 종류별 개수만
    ontology_catalog(c) {
      const kinds = { components: '구성 요소', symptoms: '증상', parts: '부품', actions: '원자 조치', roles: '역할', decision_tables: '결정표', failure_modes: '고장 유형', skills: '스킬' };
      const rows = Object.entries(kinds).filter(([k]) => Array.isArray(c[k]));
      return rows.length ? `<span class="row-wrap">${rows.map(([k, n]) => `<span class="chip tone-neutral sm">${esc(n)} ${esc(c[k].length)}</span>`).join('')}</span>` : '';
    },
    segment(s) { return s.index != null ? `<span class="kv">${esc(s.index)} / ${esc(s.total)}</span>${s.title ? ` <span class="muted">${esc(s.title)}</span>` : ''}` : ''; },
    review_feedback(f) {
      const items = Array.isArray(f) ? f : f.items || f.reviews || [];
      if (!Array.isArray(items) || !items.length) return '';
      const by = items.reduce((m, x) => { const k = x.verdict || x.status || '–'; m[k] = (m[k] || 0) + 1; return m; }, {});
      return `<span class="row-wrap">${Object.entries(by).map(([k, n]) => `<span class="chip tone-neutral sm">${esc({ OK: '맞음', WRONG: '틀림', MISSING: '빠짐' }[k] || k)} ${esc(n)}</span>`).join('')}</span>`;
    },
    proposal(p) {
      if (!Array.isArray(p.procedures) && !Array.isArray(p.sections)) return '';
      const procs = p.procedures || [];
      return `<p class="kv-line">${esc(UI.t('td.sections'))} ${esc((p.sections || []).length)} · ${esc(UI.t('td.procedures'))} ${esc(procs.length)} · ${esc(UI.t('td.pageReviews'))} ${esc((p.page_reviews || []).length)} · ${esc(UI.t('td.warnings'))} ${esc((p.warnings || []).length)}${p.knowledge ? ` · 고장 유형 ${esc((p.knowledge.failure_modes || []).length)} · 원인 ${esc((p.knowledge.causes || []).length)} · 증거 ${esc((p.knowledge.evidence || []).length)} · 규칙 ${esc((p.knowledge.rules || []).length)}` : ''}</p>
        ${procs.length ? table([UI.t('td.procedures'), UI.t('td.sections'), UI.t('td.steps')], procs.slice(0, 30).map(x => `<tr><td>${esc(x.id || '')} ${esc(x.name || '')}</td><td>${esc(x.section || '')}</td><td>${esc((x.steps || []).length)}</td></tr>`)) : ''}
        ${(p.warnings || []).length ? `<ul class="td-list">${p.warnings.slice(0, 8).map(w => `<li>${esc(w)}</li>`).join('')}</ul>` : ''}`;
    },
  };
  // a command is {code, <param>: value} (machine.on_approve) — the label shows the value the plant received
  const cmdLabel = c => { const value = c.value != null ? c.value : Object.entries(c).filter(([k, x]) => k !== 'code' && (typeof x === 'number' || typeof x === 'string')).map(([, x]) => x)[0];
    return window.hydCards ? hydCards.actionLabel({ ...c, value }) : `${c.code}${value != null ? ' ' + value : ''}`; };
  SPECIAL.commands = list => Array.isArray(list) && list.length ? `<span class="row-wrap">${list.map(c => `<span class="chip tone-accent sm">${esc(cmdLabel(c))}</span>`).join('')}</span>` : '';
  SPECIAL.candidates = list => Array.isArray(list) && list.length ? `<span class="row-wrap">${list.map(c => `<span class="chip tone-neutral sm">${esc(typeof c === 'string' ? (UI.name(c) || c) : optionName(c))}</span>`).join('')}</span>` : '';

  /* ---------- 판단 근거 (내장 판단 경로의 evidence 이벤트 · 조치 카드 점수 구성) ---------- */
  function evidenceHtml(d) {
    let h = `${d.content ? `<p class="kv-line">${esc(UI.idText(d.content))}</p>` : ''}${d.method ? `<p class="field-hint">${esc(UI.idText(d.method))}</p>` : ''}`;
    if (Array.isArray(d.causes) && d.causes.length) h += table([UI.t('td.cause'), UI.t('td.prior'), UI.t('td.causeScore'), UI.t('td.passedOf')], d.causes.map(c => `<tr><td>${esc(UI.idText(c.name || UI.name(c.id)))}</td><td>${esc(num(c.prior))}</td><td>${c.score == null ? '<span class="muted">미확인</span>' : esc(num(c.score))}</td><td>${esc(c.passed)} / ${esc(c.evidence)}</td></tr>`));
    if (Array.isArray(d.cards) && d.cards.length && d.cards.some(c => c.parts)) h += cardsTable(d.cards.map(c => ({ ...c, scoreParts: c.parts })), {});
    else if (Array.isArray(d.cards) && d.cards.length) h += table([UI.t('td.card'), UI.t('td.selectedBy')], d.cards.map(c => `<tr><td>${esc(optionName(c))}</td><td>${(c.rules || []).map(r => esc(UI.idText(r))).join('<br>') || '<span class="muted">–</span>'}</td></tr>`));
    if (d.formula && Object.keys(d.formula).length) h += UI.fold(esc(UI.t('td.formula')), Object.entries(d.formula).map(([k, expr]) => `<div>${esc(scoreLabel(k))}: <code>${esc(expr)}</code></div>`).join(''), { cls: 'small' });
    return h;
  }
  // 조치 카드 점수 구성: 순위 · 카드 · 점수 · 구성(성과 지표 · 예측 · 감점 …) · 판정(권고 · 결정 · 제외 사유)
  function cardsTable(opts, { rec, chosen }) {
    return table([UI.t('td.rank'), UI.t('td.card'), UI.t('td.causeScore'), UI.t('td.parts'), UI.t('td.verdict')], opts.map(o => {
      const parts = Object.entries(o.scoreParts || {}).map(([k, x]) => `<span class="td-part">${esc(scoreLabel(k))} <b>${esc(signed(x))}</b></span>`).join('');
      const verdict = [o.id === rec ? UI.chipText(UI.t('chip.recommended'), 'accent') : '', o.id === chosen ? UI.chipText(UI.t('chip.chosen'), 'success') : '',
        o.feasible === false ? UI.chipText(UI.t('chip.excluded'), 'danger') + (o.violations && o.violations[0] ? ` <span class="muted">${esc(UI.idText(o.violations[0].annotation || ''))}</span>` : '') : ''].join(' ');
      return `<tr${o.id === rec ? ' class="rec"' : ''}><td>${o.feasible === false ? '–' : esc(o.rank ?? '–')}</td><td>${esc(optionName(o))}</td><td>${esc(num(o.score))}</td><td>${parts || '<span class="muted">–</span>'}</td><td>${verdict}</td></tr>`;
    }));
  }
  function decisionHtml(d) {
    if (!d) return T.decErr ? `<p class="neg">${esc(UI.t('td.decFail'))}: ${esc(T.decErr)}</p>` : '';
    const rr = d.rankRule || {};
    return `${cardsTable(d.options || [], { rec: d.recommended, chosen: d.chosen })}${rr.annotation || rr.rule ? `<p class="field-hint">${esc(UI.t('td.rankRule'))}: ${esc(UI.idText(rr.annotation || rr.rule))}</p>` : ''}
      ${rr.rankingPolicy && rr.rankingPolicy.components ? UI.fold(esc(UI.t('td.formula')), Object.entries(rr.rankingPolicy.components).map(([k, expr]) => `<div>${esc(scoreLabel(k))}: <code>${esc(expr)}</code></div>`).join(''), { cls: 'small' }) : ''}`;
  }
  const lastOf = (evs, pred) => { for (let i = evs.length - 1; i >= 0; i--) if (pred(evs[i])) return evs[i]; return null; };
  const isNote = e => e.event_type === 'task_working' && (e.data || {}).type === 'text';
  const isEvidence = e => e.event_type === 'task_working' && (e.data || {}).type === 'evidence';
  function noteHtml(text, k) {
    const s = String(text || '');
    return `<blockquote class="td-note">${esc(UI.idText(s.slice(0, NOTE_SHOW)))}${s.length > NOTE_SHOW ? '…' : ''}</blockquote>${s.length > NOTE_SHOW ? `<details class="fold small" data-k="${esc(k)}"><summary>${esc(UI.t('td.noteMore'))}</summary><pre class="td-prose">${esc(s)}</pre></details>` : ''}`;
  }

  /* ---------- ① 받은 입력 ---------- */
  function originText(src, v) {
    if (!src) return UI.t('inst.source.none');
    if (src.kind === 'input') return UI.t('inst.source.input');
    if (src.kind === 'runtime') return UI.t('inst.source.runtime');
    if (src.kind === 'workitem') { const p = v.workitems.find(w => w.id === src.id); const name = UI.flowName((p && p.activity_name) || src.activity || ''); return `${name}${src.generation ? ` (${src.generation}${UI.t('inst.gen')})` : ''} ${UI.t('td.from')}`; }
    return UI.t('inst.source.none');
  }
  function inputsHtml(w, item, v) {
    const act = activityOf(v, w.activity_id) || {};
    const keys = act.inputData || [];
    if (!keys.length) return `<p class="muted">${esc(UI.t('td.noInputs'))}</p>`;
    const current = vars(v.instance);
    const values = item ? item.inputs || {} : current;
    const sources = (item && item.input_sources) || v.instance.variable_sources || {};
    const state = item ? item.input_state : 'current';
    const rows = keys.map(k => UI.readonly(varName(k, v), valueHtml(k, values[k], v), originText(sources[k], v))).join('');
    return `<p class="field-hint">${esc(UI.t(state === 'captured' ? 'td.captured' : state === 'waiting' ? 'td.waiting' : 'td.current'))}</p><div class="ro-grid">${rows}</div>`;
  }

  /* ---------- ② 처리 과정 타임라인 (events + 작업 행 자체) ---------- */
  function timelineItems(w, evs, v, live) {
    const items = [];
    const byTool = new Map();
    const hasStart = evs.some(e => e.event_type === 'task_started'), hasEnd = evs.some(e => ['task_completed', 'task_cancelled'].includes(e.event_type));
    if (!hasStart && w.start_date) items.push({ t: w.start_date, cls: 'done', title: kindOf(w) === 'human' ? UI.t('td.assigned') : UI.t('td.start'), text: UI.who(w.user_id) });
    evs.forEach(e => {
      const d = e.data || {};
      switch (e.event_type) {
        case 'tool_usage_started': { const it = { t: e.timestamp, cls: 'current', title: UI.toolName(d.tool), text: brief(d.input, 200), code: d.tool !== 'ToolSearch', raw: d, key: d.tool_use_id, running: true, k: 'tool:' + e.id }; byTool.set(d.tool_use_id, it); items.push(it); return; }
        case 'tool_usage_finished': {
          const it = byTool.get(d.tool_use_id);
          if (it) { it.cls = d.is_error ? 'fail' : 'done'; it.running = false; it.dur = fmtMs(new Date(e.timestamp) - new Date(it.t)); it.result = brief(d.output, 200); it.rawOut = d; it.error = !!d.is_error; return; }
          items.push({ t: e.timestamp, cls: d.is_error ? 'fail' : 'done', title: UI.toolName(d.tool), result: brief(d.output, 200), rawOut: d, k: 'tool:' + e.id }); return;
        }
        case 'task_started': items.push({ t: e.timestamp, cls: 'done', title: UI.t('td.start'), text: `${UI.who(d.role || 'agent')}${d.name ? ' · ' + UI.who(d.name) : ''}`, foldTitle: d.task_description ? UI.t('td.instruction') : '', foldBody: UI.idText(d.task_description || ''), k: 'start:' + e.id }); return;
        case 'task_working':
          if (d.type === 'text') { items.push({ t: e.timestamp, cls: 'note', title: UI.t('td.note'), html: noteHtml(d.content, 'note:' + e.id), k: 'note:' + e.id }); return; }
          if (d.type === 'evidence') { items.push({ t: e.timestamp, cls: 'note', title: d.name || UI.t('td.basis'), html: evidenceHtml(d), k: 'ev:' + e.id }); return; }
          if (d.type === 'usage') { items.push({ t: e.timestamp, cls: 'done', small: true, title: UI.t('td.tokens'), text: `${UI.t('stream.tokens')} ${(d.usage || {}).input_tokens ?? '–'} / ${(d.usage || {}).output_tokens ?? '–'}` }); return; }
          if (d.name === '승인 접수') { items.push({ t: e.timestamp, cls: 'done', title: d.name, text: `${d.by || ''}${d.role ? ' (' + UI.who(d.role) + ')' : ''}`, raw: d, k: 'w:' + e.id }); return; }
          if (d.session_id || d.model) { items.push({ t: e.timestamp, cls: 'done', title: UI.t('td.start'), text: d.model ? `${UI.t('td.model')} ${d.model}` : '', small: true }); return; }
          items.push({ t: e.timestamp, cls: 'done', title: UI.logText(d.name || UI.t('stream.working')), text: UI.logText(d.content || d.message || ''), code: d.type === 'file_artifact' || /^\s*(```|\{|\[)/.test(d.content || d.message || ''), raw: d.content || d.message ? null : d, k: 'w:' + e.id }); return;   // 에이전트가 쓴 파일 내용 · 결과 JSON을 그대로 말한 메시지는 코드로
        case 'human_asked': items.push({ t: e.timestamp, cls: 'ask', title: UI.t('stream.asked'), text: humanQuestionText(d), options: Array.isArray(d.options) ? d.options.filter(x => typeof x === 'string') : [], k: 'ask:' + e.id }); return;
        case 'human_response': items.push({ t: e.timestamp, cls: 'done', title: UI.t('stream.answered'), text: `${d.answer || ''}${d.by ? ' — ' + d.by : ''}`, k: 'ans:' + e.id }); return;
        case 'task_completed': items.push({ t: e.timestamp, cls: 'done', title: UI.t('stream.done'), text: (d.output_keys || []).length ? `${UI.t('td.outputKeys')} ${d.output_keys.map(k => UI.terms['var.' + k] || k).join(', ')}` : brief(d.text, 160), chip: d.result_source === 'file' ? UI.chipText(UI.t('inst.resultFile')) : '',
          foldTitle: d.text && (d.output_keys || []).length ? UI.t('td.finalText') : '', foldBody: readable(d.text), k: 'done:' + e.id }); return;
        case 'task_cancelled': items.push({ t: e.timestamp, cls: 'fail', title: e.job_id === 'TASK_CANCEL_REQUESTED' ? UI.t('stream.cancelReq') : e.job_id === 'TASK_CLOSED' ? UI.t('stream.closed') : UI.t('stream.stopped'), text: UI.logText(brief(d.goal || d.reason, 200)), raw: d, k: 'c:' + e.id }); return;
        case 'error': items.push({ t: e.timestamp, cls: 'fail', title: d.name || UI.t('stream.error'), text: d.friendly || d.message || brief(d.raw_error || d.content, 200), foldTitle: d.raw_error ? UI.t('raw') : '', foldBody: d.raw_error || '', k: 'err:' + e.id }); return;
        default: items.push({ t: e.timestamp, cls: e.event_type === 'TASK_REVIEW_REQUIRED' || e.job_id === 'TASK_REVIEW_REQUIRED' ? 'ask' : 'done', title: UI.eventName(e.job_id === 'TASK_REVIEW_REQUIRED' ? e.job_id : e.event_type), text: UI.logText(d.message || d.note || d.friendly || d.reason || '') || ((d.assessment || {}).reasons || []).join('; '), raw: d, k: 'x:' + e.id });
      }
    });
    // the engine's own notes on the row (approval accepted, command issued, waiting ACK …) — no timestamp of their own
    String(w.log || '').split(/;\s*/).map(s => s.trim()).filter(Boolean).forEach((seg, i) => items.push({ t: null, order: i, cls: 'done', title: UI.logText(seg), small: true }));
    if (!hasEnd && w.end_date) items.push({ t: w.end_date, cls: w.status === 'CANCELLED' ? 'fail' : 'done', title: UI.status(w.status), text: '' });
    if (live) {
      const k = kindOf(w);
      const title = w.draft_status === 'HUMAN_ASKED' ? UI.t('td.askWait') : w.status === 'PENDING' ? UI.t('td.pendingWait') : w.status === 'SUBMITTED' ? UI.t('td.engineWorking')
        : k === 'agent' ? UI.t('td.agentWorking') : k === 'human' ? UI.t('td.humanWaiting') : UI.t('td.systemWaiting');
      items.push({ t: null, cls: 'current', live: true, title, text: w.due_date ? `${UI.t('inst.due')} ${UI.time(w.due_date)}` : '' });
    }
    return items;
  }
  function timelineHtml(w, evs, v, live) {
    const items = timelineItems(w, evs, v, live);
    if (!items.length) return `<p class="muted">${esc(UI.t('td.noTrace'))}</p>`;
    return `<div class="timeline td-timeline" data-td-timeline>${items.map(it => `<div class="tl ${esc(it.cls)}${it.small ? ' small' : ''}${it.live ? ' live' : ''}"><div class="dot"></div><div class="tl-body">
        <div class="tl-head">${it.t ? `<time title="${esc(UI.dateTime(it.t))}">${esc(UI.time(it.t))}</time>` : it.live ? `<i class="live-dot on"></i>` : '<time></time>'}<b>${esc(it.title)}</b>${it.chip || ''}${it.running ? `<span class="chip tone-accent sm">${esc(UI.t('td.running'))}</span>` : ''}${it.dur ? `<span class="dur">${esc(it.dur)}</span>` : ''}</div>
        ${it.text ? `<div class="tl-text">${it.code ? `<code>${esc(it.text)}</code>` : esc(it.text)}</div>` : ''}${it.html || ''}${it.result != null ? `<div class="tl-text res${it.error ? ' neg' : ''}">→ <code>${esc(it.result)}</code></div>` : ''}
        ${it.options && it.options.length ? `<div class="row-wrap">${it.options.map(o => `<span class="chip tone-neutral sm">${esc(o)}</span>`).join('')}</div>` : ''}
        ${it.foldTitle ? `<details class="fold small" data-k="${esc(it.k)}"><summary>${esc(it.foldTitle)}</summary><pre>${esc(it.foldBody)}</pre></details>` : ''}
        ${it.raw || it.rawOut ? `<details class="fold small" data-k="${esc(it.k)}:raw"><summary>${esc(UI.t('raw'))}</summary><pre>${esc(JSON.stringify(it.rawOut ? { ...(it.raw || {}), ...it.rawOut } : it.raw, null, 2).slice(0, 6000))}</pre></details>` : ''}
      </div></div>`).join('')}</div>`;
  }

  /* ---------- ③ 판단 · 출력 ---------- */
  function waitRow(w) {
    if (!w.start_date) return '';
    const end = w.end_date ? new Date(w.end_date) : new Date();
    const spent = fmtMs(Math.max(0, end - new Date(w.start_date)));
    const due = w.due_date && !w.end_date ? new Date(w.due_date) - new Date() : null;
    const dueText = due == null ? '' : due >= 0 ? ` · ${UI.t('td.dueLeft')} ${fmtMs(due)}` : ` · ${UI.t('td.overdue')}`;
    return UI.readonly(UI.t('td.wait'), `${esc(UI.t('td.waitFor'))} <b>${esc(spent)}</b>${esc(dueText)}`, w.due_date ? `${UI.t('inst.due')} ${UI.dateTime(w.due_date)}` : '');
  }
  function selectHtml(w, item, v) {
    const current = vars(v.instance);
    const approval = (v.approvals || []).find(a => a.todo_id === w.id);
    const d = T.dec && T.dec.id === current.decision_id ? T.dec : null;
    const decision = d || (item && item.inputs && item.inputs.decision) || current.decision || {};
    const opts = decision.options || [];
    const chosenId = (w.output || {}).chosen_skill || (d && d.chosen) || (w.status === 'DONE' ? current.chosen_skill : null);
    const chosen = opts.find(o => o.id === chosenId) || (w.status === 'DONE' ? current.chosen_option : null) || (chosenId ? { id: chosenId } : null);
    const recId = decision.recommended;
    const rec = opts.find(o => o.id === recId) || (recId ? { id: recId } : null);
    const p = (approval && approval.payload) || {};
    const cards = d ? decisionHtml(d) : opts.length ? cardsTable(opts, { rec: recId, chosen: chosenId }) : (T.decErr ? `<p class="neg">${esc(UI.t('td.decFail'))}: ${esc(T.decErr)}</p>` : `<span class="muted">${esc(UI.t('empty.noData'))}</span>`);
    const timeout = w.status === 'CANCELLED' && /select-timeout/.test(w.log || '');
    const kindChip = k => k ? ' ' + UI.chipText(k === 'control' ? UI.t('chip.control') : UI.t('chip.workOrder')) : '';
    const rows = [
      UI.readonly(UI.t('td.recommended'), rec ? `<span class="kv">${esc(optionName(rec))}</span>` : `<span class="muted">${esc(UI.t('inst.noValue'))}</span>`),
      UI.readonly(UI.t('td.chosen'), chosen ? `<span class="kv">${esc(optionName(chosen))}</span>${kindChip((w.output || {}).chosen_skill_kind || (w.status === 'DONE' ? current.chosen_skill_kind : ''))}${recId && chosen.id !== recId ? ' ' + UI.chipText(UI.t('td.differs'), 'warning') : ''}` : timeout ? `<span class="neg">${esc(UI.t('td.timeout'))}</span>` : `<span class="muted">${esc(UI.t('inst.noValue'))}</span>`),
      UI.readonly(UI.t('td.reason'), esc(p.reason || (d && d.reason) || (w.status === 'DONE' ? current.note : '') || '') || `<span class="muted">${esc(UI.t('inst.noValue'))}</span>`),
      UI.readonly(UI.t('td.approver'), esc(p.by || (d && d.approvedBy) || (w.status === 'DONE' ? current.approved_by : '') || '–') + ((p.role || (d && d.approvedRole)) ? ` (${esc(UI.who(p.role || d.approvedRole))})` : '')),
      waitRow(w),
      d ? UI.readonly(UI.t('td.decState'), UI.chip(d.state)) : '',
      approval ? UI.readonly(UI.t('td.delivery'), `${UI.chip(approval.status)} <span class="muted">· ${esc(approval.attempts)}회 시도</span>${approval.error ? `<p class="neg">${esc(approval.error)}</p>` : ''}`) : '',
    ];
    return `<div class="ro-grid">${rows.join('')}</div><p class="kv-line" style="margin-top:var(--s3)"><b>${esc(UI.t('td.cards'))}</b></p>${cards}${rawFold(w.output, 'raw:output')}`;
  }
  function incidentHtml(w, v) {
    const current = vars(v.instance);
    if (!current.incident) return '';
    if (T.incErr && T.incId === current.incident) return `<p class="neg">${esc(UI.t('td.incFail'))}: ${esc(T.incErr)}</p>`;
    const inc = T.inc && T.inc.id === current.incident ? T.inc : null;
    if (!inc) return `<p class="muted">${esc(UI.t('loading'))}</p>`;
    const tool = w.tool || ((activityOf(v, w.activity_id) || {}).tool) || '';
    const rows = [];
    if (tool === 'incident:command') {
      rows.push(UI.readonly(UI.t('td.sent'), SPECIAL.commands(current.commands) || SPECIAL.commands(inc.actions) || `<span class="muted">${esc(UI.t('inst.noValue'))}</span>`, inc.approvedBy ? `${UI.t('td.approver')} ${inc.approvedBy}` : ''));
      if (inc.cmdId) rows.push(UI.readonly(UI.t('td.cmdId'), `<span class="mono">${esc(inc.cmdId)}</span>`));
      const ack = inc.ack;
      rows.push(UI.readonly(UI.t('td.response'), ack ? `${ack.result === 'DONE' ? UI.chipText(UI.t('td.ackDone'), 'success') : UI.chipText(UI.t('td.ackRejected'), 'danger')}${ack.reason ? ` <span class="muted">${esc(UI.logText(ack.reason))}</span>` : ''}${ack.interlock ? ` · ${esc(UI.t('td.interlock'))} ${esc(ack.interlock)}` : ''}`
        : inc.state === 'AWAITING_ACK' ? `<span class="muted">${esc(UI.t('td.ackWait'))}</span>` : esc(UI.status(inc.state)), ack && ack.t ? UI.dateTime(ack.t) : ''));
    }
    if (tool === 'incident:reobserve') rows.push(...reobserveRows(inc));
    return rows.length ? `<div class="ro-grid">${rows.join('')}</div>` : '';
  }
  // 재측정까지 남은 시간: 사건 이력의 RE_OBSERVING 기록(시각 · "모의 900초 = 실제 45초")에서 계산 — 배속은 서버가 적은 값을 쓴다
  function reobsWindow(inc) {
    const h = (inc.history || []).filter(x => x.state === 'RE_OBSERVING').pop();
    const m = h && String(h.note || '').match(/^(\d+(?:\.\d+)?) sim-s = (\d+(?:\.\d+)?) s$/);
    if (!h || !m) return null;
    const sim = Number(m[1]), real = Number(m[2]);
    return { at: new Date(h.t), sim, real, due: new Date(new Date(h.t).getTime() + real * 1000), scale: real > 0 ? Math.round(sim / real) : null };
  }
  function reobserveRows(inc) {
    const rows = [];
    const crit = (inc.recoveryPolicy || {}).criterion;
    if (Array.isArray(crit)) rows.push(UI.readonly(UI.t('td.criterion'), `<span class="kv">${esc(TAG[crit[0]] || crit[0])} ${esc(OP[crit[1]] || crit[1])} ${esc(num(crit[2]))}</span> + ${esc(UI.t('td.cleared'))}`));
    const win = reobsWindow(inc);
    if (win) {
      const left = win.due - new Date();
      const scaleText = UI.t('td.scaleNote').replace('{sim}', fmtMs(win.sim * 1000)).replace('{real}', fmtMs(win.real * 1000)).replace('{x}', win.scale ?? '–');
      const value = inc.state === 'RE_OBSERVING' ? (left > 0 ? `${esc(UI.t('td.remeasureIn'))} <b class="td-count">${esc(fmtMs(left))}</b>` : esc(UI.t('td.remeasureDue'))) : `${esc(UI.dateTime(win.due.toISOString()))}`;
      rows.push(UI.readonly(UI.t('td.remeasure'), value + (inc.reobsExtensions ? ` · ${esc(UI.t('td.extensions'))} ${esc(inc.reobsExtensions)}회` : ''), scaleText));
    }
    rows.push(UI.readonly(UI.t('td.cleared'), esc(inc.cleared ? UI.t('yes') : UI.t('no'))));
    const verdict = (inc.history || []).filter(x => ['RESOLVED', 'ESCALATED'].includes(x.state)).pop();
    if (verdict) {
      const m = String(verdict.note || '').match(/^(\w+) ([\d.\-]+|None) (<|>=) ([\d.]+)$/);
      const text = m ? `${TAG[m[1]] || m[1]} ${m[2]} ${OP[m[3]]} ${m[4]}` : UI.logText(verdict.note || inc.reason || '');
      rows.push(UI.readonly(UI.t('td.recoveryBasis'), `${UI.chip(verdict.state)} ${esc(text)}`, UI.dateTime(verdict.t)));
    }
    return rows;
  }
  function basisHtml(w, evs) {
    const ev = lastOf(evs, isEvidence), note = lastOf(evs, isNote);
    const parts = [];
    if (ev) parts.push(evidenceHtml(ev.data));
    if (note) parts.push(noteHtml(note.data.content, 'basis-note'));
    return parts.length ? `<div class="td-basis"><p class="td-basis-title">${esc(UI.t('td.basis'))}</p>${parts.join('')}</div>` : '';
  }
  function outputHtml(w, item, v, evs) {
    const k = kindOf(w), tool = (item && item.tool) || w.tool || ((activityOf(v, w.activity_id) || {}).tool) || '';
    if (tool === 'formHandler:select_card') return selectHtml(w, item, v);
    if (k === 'system') {
      const rows = [];
      Object.entries(w.output || {}).filter(([key]) => !HIDDEN_OUTPUT.has(key)).forEach(([key, val]) => rows.push(UI.readonly(varName(key, v), valueHtml(key, val, v))));
      if (!rows.length && w.log) rows.push(UI.readonly(UI.t('td.result'), esc(UI.logText(w.log))));
      const inc = tool.startsWith('incident:') ? incidentHtml(w, v) : '';
      return inc || rows.length ? `${inc}${rows.length ? `<div class="ro-grid">${rows.join('')}</div>` : ''}${rawFold(w.output, 'raw:output')}` : `<p class="muted">${esc(UI.t('td.noOutput'))}</p>`;
    }
    const basis = k === 'agent' ? basisHtml(w, evs) : '';
    const cards = k === 'agent' && DECISION_TOOLS.has(tool) && (T.dec || T.decErr) ? `<p class="kv-line"><b>${esc(UI.t('td.parts'))}</b></p>${decisionHtml(T.dec && T.dec.id === vars(v.instance).decision_id ? T.dec : null)}` : '';
    const wait = k === 'human' ? `<div class="ro-grid">${waitRow(w)}</div>` : '';
    const out = w.output && Object.keys(w.output).length ? w.output : (w.draft && typeof w.draft === 'object' && !w.draft._human_request ? w.draft : null);
    if (!out) return `${basis}${cards}${wait}<p class="muted">${esc(UI.t('td.noOutput'))}</p>`;
    const fields = Object.fromEntries((((item && item.form) || {}).fields_json || []).map(f => [f.key, f.text]));
    const keys = Object.keys(out).filter(key => !HIDDEN_OUTPUT.has(key));
    const rows = keys.map(key => UI.readonly(UI.terms['var.' + key] || fields[key] || varName(key, v), valueHtml(key, out[key], v))).join('');
    const prose = !keys.length && typeof out.text === 'string' ? UI.readonly(UI.t('td.prose'), `<pre class="td-prose">${esc(out.text.slice(0, 4000))}</pre>`) : '';
    return `${basis}${wait}${w.draft && !w.output ? `<p class="field-hint">${esc(UI.status('FB_REQUESTED'))} · ${esc(UI.t('inst.structured'))}</p>` : ''}<div class="ro-grid">${rows}${prose}</div>${cards}${rawFold(out, 'raw:output')}`;
  }

  /* ---------- ④ 다음 단계로 넘긴 값 ---------- */
  function nextHtml(w, v) {
    const act = activityOf(v, w.activity_id) || {};
    const keys = act.outputData || [];
    if (!keys.length) return `<p class="muted">${esc(UI.t('td.noNext'))}</p>`;
    const current = vars(v.instance), sources = v.instance.variable_sources || {};
    const acts = (v.definition || {}).activities || [];
    return `<div class="ro-grid">${keys.map(key => {
      const src = sources[key];
      const mine = src && src.kind === 'workitem' && src.id === w.id;
      const value = (w.output || {})[key] !== undefined ? w.output[key] : (mine ? current[key] : undefined);
      const state = mine ? UI.chipText(UI.t('td.delivered'), 'success') : src && src.kind === 'workitem' ? UI.chipText(UI.t('td.superseded'), 'warning') : UI.chipText(UI.t('td.notYet'));
      const consumers = acts.filter(a => a.id !== w.activity_id && ((a.inputData || []).includes(key) || Object.keys(a.inputBindings || {}).includes(key))).map(a => { const c = latestFor(v, a.id); return `${UI.flowName(a.name)}${c ? ` (${UI.status(c.status)})` : ''}`; });
      const shown = value === undefined ? `<span class="muted">${esc(UI.t('inst.noValue'))}</span>`
        : value !== null && typeof value === 'object' && (w.output || {})[key] !== undefined ? `<span class="muted">${esc(UI.t('td.seeOutput'))}</span>` : valueHtml(key, value, v);
      return UI.readonly(varName(key, v), `${state} ${shown}`, `${UI.t('td.consumers')}: ${consumers.join(', ') || UI.t('td.noConsumer')}`);
    }).join('')}</div>`;
  }

  /* ---------- 아직 시작하지 않은 단계 (정의만) ---------- */
  function plannedHtml(v, actId) {
    const act = activityOf(v, actId); if (!act) return '';
    const roleEp = ((v.definition || {}).roles || []).find(r => r.name === act.role);
    return `<section class="card task-detail" data-task-detail><header class="card-head"><div class="card-title"><h3>${esc(UI.flowName(act.name))}</h3><span class="card-chips">${UI.chip('TODO')}</span></div><div class="card-actions"><button type="button" class="btn small" data-td-close>${esc(UI.t('td.close'))}</button></div></header>
      <p class="card-sub">${esc(UI.t('td.planned'))} · ${esc(UI.t('td.plannedSub'))}</p>
      <div class="ro-grid">${UI.readonly(UI.t('td.who'), esc(UI.who(act.agent || (roleEp && roleEp.endpoint) || act.role || '')))}${UI.readonly(UI.t('td.expects'), (act.inputData || []).map(k => `<span class="chip tone-neutral sm">${esc(varName(k, v))}</span>`).join(' ') || esc(UI.t('empty.noData')))}${UI.readonly(UI.t('td.produces'), (act.outputData || []).map(k => `<span class="chip tone-neutral sm">${esc(varName(k, v))}</span>`).join(' ') || esc(UI.t('empty.noData')))}</div>
      ${act.description ? `<p class="kv-line" style="margin-top:var(--s3)">${esc(act.description)}</p>` : ''}</section>`;
  }

  /* ---------- render ---------- */
  const section = (k, title, body, count, open) => `<details class="fold td-section" data-k="${k}" ${open ? 'open' : ''}><summary>${esc(title)}${count != null ? ` <span class="chip tone-neutral sm">${esc(count)}</span>` : ''}</summary><div class="fold-body">${body}</div></details>`;
  function eventsOf(w, v, item) {
    const seen = new Set();
    return [...v.events.filter(e => e.todo_id === w.id), ...((item && item.events) || [])].filter(e => e && e.id && !seen.has(e.id) && seen.add(e.id)).sort((a, b) => String(a.timestamp || '').localeCompare(String(b.timestamp || '')));
  }
  function render() {
    renderNow();
    const host = T.host; if (!host) return;
    const v = view();
    if (!v || (!T.wid && !T.act)) { host.innerHTML = ''; highlight(); return; }
    if (T.act) { host.innerHTML = plannedHtml(v, T.act); highlight(); return; }
    const w = workitemOf(T.wid);
    if (!w) { host.innerHTML = ''; highlight(); return; }
    const item = T.item && T.item.id === w.id ? T.item : null;
    const first = T.rendered !== w.id;
    const wasOpen = new Set([...host.querySelectorAll('details[data-k][open]')].map(d => d.dataset.k));
    const live = LIVE.has(w.status) && v.instance.status === 'RUNNING';
    const evs = eventsOf(w, v, item);
    const k = kindOf(w);
    const span = w.start_date && w.end_date ? new Date(w.end_date) - new Date(w.start_date) : NaN;
    const dur = span >= 0 ? fmtMs(span) : '';
    const act = activityOf(v, w.activity_id) || {};
    const inputCount = (act.inputData || []).length, outCount = (act.outputData || []).length;
    const toolCount = evs.filter(e => e.event_type === 'tool_usage_started').length;
    host.innerHTML = `<section class="card task-detail ${esc(k)}${live ? ' live' : ''}" data-task-detail>
      <header class="card-head"><div class="card-title"><h3>${esc(UI.flowName(w.activity_name))}</h3><span class="card-chips">${UI.chip(w.status)}${w.draft_status && w.status !== 'DONE' ? UI.chip(w.draft_status) : ''}${UI.chipText(k === 'agent' ? UI.t('agent') : k === 'human' ? UI.who(w.user_id) : UI.t('system'), k === 'agent' ? 'accent' : 'neutral')}${live ? `<span class="chip tone-success sm"><i class="live-dot on"></i> ${esc(UI.t('td.liveOn'))}</span>` : ''}</span></div><div class="card-actions"><button type="button" class="btn small" data-td-close>${esc(UI.t('td.close'))}</button></div></header>
      <p class="card-sub">${esc(UI.dateTime(w.start_date))}${w.end_date ? ' → ' + esc(UI.time(w.end_date)) : ''}${dur ? ' · ' + esc(dur) : ''}${w.generation ? ` · ${esc(w.generation)}${esc(UI.t('inst.gen'))}` : ''}${w.due_date && !w.end_date ? ` · ${esc(UI.t('inst.due'))} ${esc(UI.time(w.due_date))}` : ''}</p>
      ${T.error ? `<p class="neg">${esc(UI.t('td.loadFail'))}: ${esc(T.error)}</p>` : ''}
      <div class="td-sections">
        ${section('inputs', UI.t('td.inputs'), inputsHtml(w, item, v), inputCount, first ? inputCount > 0 : wasOpen.has('inputs'))}
        ${section('trace', UI.t('td.trace'), timelineHtml(w, evs, v, live), toolCount || null, first ? true : wasOpen.has('trace'))}
        ${section('output', UI.t('td.output'), outputHtml(w, item, v, evs), null, first ? true : wasOpen.has('output'))}
        ${section('next', UI.t('td.next'), nextHtml(w, v), outCount, first ? outCount > 0 : wasOpen.has('next'))}
      </div></section>`;
    if (!first) host.querySelectorAll('details[data-k]:not(.td-section)').forEach(d => { if (wasOpen.has(d.dataset.k)) d.open = true; });
    T.rendered = w.id;
    const tl = host.querySelector('[data-td-timeline]'); if (tl && live) tl.scrollTop = tl.scrollHeight;
    highlight();
  }
  function highlight() {
    if (typeof document === 'undefined' || !document.querySelectorAll) return;
    const w = T.wid && workitemOf(T.wid);
    const actId = T.act || (w && w.activity_id);
    document.querySelectorAll('#instDetail .f-node[data-node]').forEach(g => g.classList.toggle('picked', !!actId && g.dataset.node === actId));
    document.querySelectorAll('#instDetail .step-row[data-step-task]').forEach(d => d.classList.toggle('picked', !!w && d.dataset.stepTask === w.id));
  }

  /* ---------- 지금: <단계> — <누가> <무엇을 하는 중> ---------- */
  function doingOf(w, v) {
    const k = kindOf(w), tool = (activityOf(v, w.activity_id) || {}).tool || '';
    if (w.status === 'PENDING') return [UI.t('system'), UI.t('td.nowPending')];
    if (k === 'agent') {
      if (w.draft_status === 'HUMAN_ASKED') return [UI.t('agent'), UI.t('td.nowAsk')];
      if (w.status === 'SUBMITTED') return [UI.t('agent'), UI.t('td.nowSubmitted')];
      const evs = [...v.events.filter(e => e.todo_id === w.id), ...(T.last[w.id] || [])];
      const open = new Set(); let last = null;
      evs.sort((a, b) => String(a.timestamp || '').localeCompare(String(b.timestamp || ''))).forEach(e => {
        const d = e.data || {};
        if (e.event_type === 'tool_usage_started') open.add(d.tool_use_id); else if (e.event_type === 'tool_usage_finished') open.delete(d.tool_use_id);
        last = e;
      });
      const running = [...open].pop();
      if (running != null) { const s = lastOf(evs, e => e.event_type === 'tool_usage_started' && (e.data || {}).tool_use_id === running); return [UI.t('agent'), UI.t('td.nowTool').replace('{tool}', UI.toolName(((s || {}).data || {}).tool))]; }
      if (last && isNote(last)) return [UI.t('agent'), UI.t('td.nowNote')];
      if (last && isEvidence(last)) return [UI.t('agent'), UI.t('td.nowBasis')];
      return [UI.t('agent'), w.consumer ? (last ? UI.t('td.nowClaimed') : UI.t('td.nowStarted')) : UI.t('td.nowQueued')];
    }
    if (k === 'human') {
      const spent = w.start_date ? ` · ${fmtMs(Math.max(0, new Date() - new Date(w.start_date)))} ${UI.t('td.waitFor')}` : '';
      const due = w.due_date ? new Date(w.due_date) - new Date() : null;
      return [UI.who(w.user_id), `${UI.t('td.nowHuman')}${spent}${due == null ? '' : due >= 0 ? ` · ${UI.t('td.dueLeft')} ${fmtMs(due)}` : ` · ${UI.t('td.overdue')}`}`];
    }
    if (tool === 'incident:command') return [UI.t('system'), UI.t('td.nowCmd')];
    if (tool === 'incident:reobserve') {
      const inc = T.inc && T.inc.id === vars(v.instance).incident ? T.inc : null, win = inc && reobsWindow(inc);
      const left = win ? win.due - new Date() : null;
      return [UI.t('system'), `${UI.t('td.nowReobs')}${left == null ? '' : left > 0 ? ` · ${UI.t('td.remeasureIn')} ${fmtMs(left)}` : ` · ${UI.t('td.remeasureDue')}`}`];
    }
    if (tool === 'enterprise:WO_CREATE') return [UI.t('system'), UI.t('td.nowWo')];
    return [UI.t('system'), UI.t('td.nowSystem')];
  }
  function nowHtml(v) {
    const inst = v.instance;
    if (inst.status !== 'RUNNING') {
      const end = inst.end_event ? ((v.definition || {}).events || []).find(e => e.id === inst.end_event) : null;
      return `<div class="td-now done" role="status"><b>${esc(UI.t('td.ended'))}</b> ${esc(UI.flowName((end && end.name) || UI.status(inst.status)))}</div>`;
    }
    const cur = v.workitems.filter(w => LIVE.has(w.status) && !isEventNode(v, w.activity_id));
    if (!cur.length) return `<div class="td-now" role="status"><b>${esc(UI.t('td.now'))}</b> <span class="muted">${esc(UI.t('td.nothing'))}</span></div>`;
    return `<div class="td-now" role="status"><i class="live-dot on"></i><b>${esc(UI.t('td.now'))}</b> ${cur.map(w => { const [who, what] = doingOf(w, v); return `<span class="td-now-item"><button type="button" class="linkish" data-td-open="${esc(w.id)}">${esc(UI.flowName(w.activity_name))}</button> — ${esc(who)} ${esc(what)}</span>`; }).join('<span class="muted"> · </span>')}</div>`;
  }
  function renderNow() {
    if (typeof document === 'undefined' || !document.getElementById) return;
    const box = document.getElementById('instNow'); const v = view();
    if (!box) return;
    if (!v) { box.innerHTML = ''; return; }
    box.innerHTML = nowHtml(v);
    ensureIncident(v);
  }

  /* ---------- state ---------- */
  async function ensureDecision(v, w, tool) {
    const id = vars(v.instance).decision_id;
    if (!id || !DECISION_TOOLS.has(tool)) return;
    if (T.decId === id && T.dec && !LIVE.has(w.status)) return;
    try { const d = await getJ(API.process + '/api/decisions/' + encodeURIComponent(id)); T.dec = d; T.decId = id; T.decErr = null; }
    catch (e) { T.dec = null; T.decId = id; T.decErr = e.message; }
  }
  async function ensureIncident(v, force) {
    const id = vars(v.instance).incident;
    const needs = v.workitems.some(w => /^incident:/.test((activityOf(v, w.activity_id) || {}).tool || '') && (LIVE.has(w.status) || (T.wid === w.id)));
    if (!id || !needs || T.incLoading) return;
    if (!force && T.incId === id && Date.now() - T.incAt < 3000) return;
    T.incLoading = true;
    try { T.inc = await getJ(API.process + '/api/incidents/' + encodeURIComponent(id)); T.incErr = null; }
    catch (e) { T.inc = null; T.incErr = e.message; }
    finally { T.incId = id; T.incAt = Date.now(); T.incLoading = false; }
  }
  async function refresh() {
    if (!T.wid || T.loading) return; T.loading = true;
    const wid = T.wid;
    try {
      const item = await getJ(API.process + '/api/todolist/' + encodeURIComponent(wid)); if (T.wid === wid) { T.item = item; T.error = null; }
      const v = view(), w = workitemOf(wid);
      if (v && w) { await ensureDecision(v, w, item.tool || ''); if (/^incident:/.test(item.tool || '')) await ensureIncident(v, true); }
    }
    catch (e) { if (T.wid === wid) T.error = e.message; }
    finally { T.loading = false; }
  }
  function setHash(pid, wid) {
    if (typeof location === 'undefined' || typeof history === 'undefined' || !pid) return;
    const h = `#/instances/${encodeURIComponent(pid)}` + (wid ? `/task/${encodeURIComponent(wid)}` : '');
    if (location.hash !== h) history.replaceState(null, '', h);
  }
  const ourHash = () => typeof location !== 'undefined' && HASH_RE.test(location.hash);
  async function open(wid) {
    if (!wid) return;
    T.act = null;
    if (T.wid !== wid) { T.wid = wid; T.item = null; T.error = null; }
    const v = view(); if (v && workitemOf(wid)) setHash(v.instance.proc_inst_id, wid);
    render();
    await refresh(); render();
    const panel = T.host && T.host.querySelector('[data-task-detail]');
    if (panel && panel.scrollIntoView) panel.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }
  function openActivity(actId) {
    const v = view(); const w = v && latestFor(v, actId);
    if (w) return open(w.id);
    T.wid = null; T.item = null; T.act = actId; render();
    const panel = T.host && T.host.querySelector('[data-task-detail]');
    if (panel && panel.scrollIntoView) panel.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }
  function close() { const v = view(); T.wid = null; T.act = null; T.item = null; T.rendered = null; if (v && ourHash()) setHash(v.instance.proc_inst_id, null); render(); }
  function mount(host) {
    T.host = host || null;
    const v = view();
    if (T.pending && v && v.instance.proc_inst_id === T.pending.pid) {        // a #/instances/<id>/task/<id> link: open once the instance is on screen
      const wid = T.pending.wid; T.pending = null;
      if (wid && workitemOf(wid)) { open(wid); return; }
    }
    if (T.wid && !workitemOf(T.wid)) { T.wid = null; T.item = null; T.rendered = null; if (v && ourHash()) setHash(v.instance.proc_inst_id, null); }   // another instance is selected now
    if (T.act) { if (!v || !activityOf(v, T.act)) T.act = null; }
    render();
  }
  // ⑤ liveStream.js hands every pushed SSE event here; the open task takes its own events, the 지금 line takes every task's latest
  function onEvent(e) {
    if (!e || !e.todo_id) return;
    const list = T.last[e.todo_id] || (T.last[e.todo_id] = []);
    if (!list.some(x => x.id === e.id)) { list.push(e); if (list.length > 20) list.shift(); }
    if (e.todo_id !== T.wid) { renderNow(); return; }
    if (T.item && !T.item.events.some(x => x.id === e.id)) T.item.events.push(e);
    render();
    if (REFRESH_ON.has(e.event_type)) refresh().then(render);
  }
  function isLive() { const w = T.wid && workitemOf(T.wid); const v = view(); return !!(w && v && LIVE.has(w.status) && v.instance.status === 'RUNNING'); }
  const onInstances = () => typeof state !== 'undefined' && state.tab === 'instances';
  // a #/instances/<처리 건>/task/<단계> address (shared link, reload) selects the instance, shows its 흐름 tab and opens the step
  function fromHash() {
    if (typeof location === 'undefined') return;
    const m = location.hash.match(HASH_RE); if (!m || !window.hydInstances) return;
    const pid = decodeURIComponent(m[1]), wid = m[2] ? decodeURIComponent(m[2]) : null;
    const I = window.hydInstances.I;
    if (I.sel === pid && (!wid || wid === T.wid) && onInstances()) return;
    I.sel = pid; I.taskSel = null; if (wid) I.tab = 'flow';
    T.pending = { pid, wid };
    if (onInstances()) window.hydInstances.load(true); else window.hydApp.selectTab('instances');
  }

  if (typeof document !== 'undefined' && document.addEventListener) {
    setInterval(() => { if (T.wid && onInstances() && isLive()) refresh().then(render); }, 2500);
    setInterval(() => { if (onInstances()) renderNow(); }, 1000);    // countdowns (기한 · 재측정) tick without a reload
    document.addEventListener('click', e => {
      if (e.target.closest('[data-td-close]')) { close(); return; }
      const now = e.target.closest('[data-td-open]');
      if (now) { const tab = document.querySelector('#instDetail [data-inst-tab="flow"]'); if (tab && !tab.classList.contains('on')) tab.click(); open(now.dataset.tdOpen); return; }
      if (!e.target.closest('#instDetail')) return;
      const node = e.target.closest('.f-node[data-node]');
      if (node) { openActivity(node.dataset.node); return; }
      const row = e.target.closest('.step-row[data-step-task]');
      if (row && e.target.closest('summary') && row.dataset.stepTask) open(row.dataset.stepTask);
    });
    // the instance detail is redrawn by instances.js every few seconds: re-apply the highlight after each redraw
    const observe = () => { const box = document.getElementById('instDetail'); if (!box) return; new MutationObserver(() => { if (T.wid || T.act) requestAnimationFrame(highlight); }).observe(box, { childList: true, subtree: true }); };
    const boot = () => { observe(); fromHash(); };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
    if (typeof window !== 'undefined' && window.addEventListener) window.addEventListener('hashchange', fromHash);
  }

  window.hydTaskDetail = { open, openActivity, close, mount, onEvent, render, renderNow, nowHtml, refresh, fromHash, T };
})();
