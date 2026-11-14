/* A161-U1 — 결과 보고 카드 (세 시나리오 공통). 승인 뒤 시스템이 실행 · 확인을 끝내면 승인한 사람이 "보기만" 하는 한 장.
   판정(정상 / 미달 / 확인 중) · 측정값 · 승인한 안 · 승인한 사람 · 시스템이 한 일(명령 · 작업지시 · 발주 · 메일 · 대기 · 정비 · 입고 · 확인) 순서.

   데이터 계약(앞쪽부터 먼저 쓴다 — 시나리오 이름을 코드에 두지 않는다):
   1) 처리 건 값 result_report = { verdict: 'ok'|'fail'|'정상'|'미달'|…, title?, summary?, values?: [{ name, value, unit?, limit? , ok? }] }
      — 결과 보고 시스템 task(C2 의 일반 부품)가 내는 값.
   2) 없으면 알려진 확인 값: recovered(재관측) · received / goods_receipt(입고) · test_run(시운전) · maintenance(정비 수행).
   참고 화면(모방): Dify 실행 결과 상단 상태 카드 web/app/components/workflow/run/status.tsx(상태 · 걸린 시간 · 단계 수),
   n8n 실행 목록의 성공/실패 배지 + 실행 단계 목록(https://docs.n8n.io/workflows/executions/), process-gpt-vue3 src/components/apps/todolist/InstanceOutput.vue(처리 건 결과물 카드) · src/ds/components/PgAlert.vue(강조 상자). */
(function () {
  const e = s => (typeof esc === 'function' ? esc(s) : String(s ?? ''));
  const OK = new Set(['ok', 'pass', 'passed', 'normal', 'recovered', 'true', '정상', '회복', '통과', '완료']);
  const FAIL = new Set(['fail', 'failed', 'not_ok', 'abnormal', 'not_recovered', 'false', '미달', '미회복', '지연', '실패', 'late', 'overdue']);
  function verdictOf(raw) {
    if (raw === true) return 'ok'; if (raw === false) return 'fail';
    const s = String(raw ?? '').trim().toLowerCase();
    return ['rejected', '반려'].includes(s) ? 'rejected' : OK.has(s) ? 'ok' : FAIL.has(s) ? 'fail' : s ? 'other' : '';
  }
  const num = x => (typeof x === 'number' && Number.isFinite(x) ? x.toLocaleString('ko-KR', { maximumFractionDigits: 2 }) : x == null || x === '' ? '–' : x === true ? '예' : x === false ? '아니요' : x);
  const orderWarned = new Set();   // 흐름 순서 없음 경고를 이미 남긴 처리 건
  const LABEL = { ok: '정상', fail: '미달', rejected: '반려', other: '확인 결과', wait: '확인 중' };

  // Stored receipt and report remain immutable; derive only this known system receipt's display.
  function receiptDetail(receipt) {
    const original = receipt?.detail;
    const plan = receipt?.after?.plan, orders = receipt?.after?.orders;
    if (original !== 'Source-scoped maintenance orders registered' || receipt?.ok !== true || receipt?.code !== 'WO_CREATE' ||
        plan?.code !== 'WO_CREATE' || !Array.isArray(plan.assets) || !plan.assets.length || !Array.isArray(orders) || orders.length !== plan.assets.length ||
        !orders.some(o => o.id === receipt.ref) || orders.some(o => !o.id || !o.asset || !plan.assets.some(a => a.asset === o.asset)) ||
        new Set(orders.map(o => o.asset)).size !== orders.length) return original;
    return '원문 정비 범위 ' + orders.map(o => o.asset).join(', ') + ' 정비 요청 등록';
  }
  function reportSummary(report, values) {
    const original = report?.summary || report?.text;
    const receipt = values?.work_order, detail = receiptDetail(receipt);
    const expected = receipt?.ref && `정비 요청 ${receipt.ref} 등록 · 생산팀 공지 — ${receipt.detail}`;
    return detail !== receipt?.detail && report?.refs?.work_order === receipt?.ref && original === expected
      ? `정비 요청 ${receipt.ref} 등록 · 생산팀 공지 — ${detail}` : original;
  }
  // 사건과 이 보고의 관계 한 줄: 보고가 사건을 닫았는가, 아니면 사건은 이미(앞 단계 — 정비 요청 등록 · 입고 등에서) 끝났는가
  function incidentMeaning(report, incident, read) {
    if (read?.state === 'loading') return '사건 상태를 읽는 중입니다';
    if (read?.state === 'error') return '사건 상태를 읽지 못했습니다';
    const now = incident?.state ? (UI.status ? UI.status(incident.state) : incident.state) : null;
    if (report?.incident_closed === true) return '이 보고가 사건을 닫았습니다' + (now ? ` (지금 사건: ${now})` : '');
    if (report?.incident_closed === false) return now ? `사건은 이 보고가 닫지 않았습니다 — 지금 사건: ${now}${incident.state === 'CLOSED' ? '(앞 단계에서 이미 닫힘)' : ''}` : '사건은 이 보고가 닫지 않았습니다';
    return '이 보고에는 사건을 닫았는지 기록이 없습니다' + (now ? ` (지금 사건: ${now})` : '');
  }

  function fromValues(v) {
    const r = v.result_report;
    if (r && typeof r === 'object') {
      // C2/C3 계약: outcome(화면 배지 문구: 정상 · 미달 · 지연 · 입고 완료 · 승인 지연 · 알림) + level/verdict(ok · fail · info → 색)
      const level = String(r.level ?? r.verdict ?? '').toLowerCase();
      const verdict = level === 'info' ? 'other' : verdictOf(r.level ?? r.verdict ?? r.ok ?? r.status ?? r.outcome);
      const free = r.verdict && !OK.has(String(r.verdict).toLowerCase()) && !FAIL.has(String(r.verdict).toLowerCase()) && !['info', 'rejected'].includes(String(r.verdict).toLowerCase()) ? String(r.verdict) : '';
      const alertId = v.alert_id || v.alert?.alertId;
      const summary = reportSummary(r, v);
      const shownSummary = alertId && typeof summary === 'string' ? summary.split(`경보 ${alertId}. `).join('') : summary;
      return { verdict: verdict || verdictOf(r.outcome), label: r.outcome ? String(r.outcome) : free, title: r.title, summary: shownSummary, values: Array.isArray(r.values) ? r.values : [],
               valuesError: r.values_error || '' };
    }
    if (v.test_run && typeof v.test_run === 'object') return { verdict: verdictOf(v.test_run.ok ?? v.test_run.verdict), title: '시운전 확인', summary: v.test_run.summary || '', values: Array.isArray(v.test_run.values) ? v.test_run.values : [] };
    if (typeof v.recovered === 'boolean') return { verdict: v.recovered ? 'ok' : 'fail', title: '효과 확인', summary: v.recovered ? '경보가 풀리고 기준 안으로 돌아왔습니다' : '기준 안으로 돌아오지 않았습니다', values: [] };
    if (typeof v.received === 'boolean' || (v.goods_receipt && typeof v.goods_receipt === 'object')) {
      const g = v.goods_receipt || {}, ok = v.received === true || g.ok === true;
      return { verdict: ok ? 'ok' : 'fail', title: '입고 확인', summary: g.detail || (ok ? '입고와 검수가 끝났습니다' : '기한 안에 입고되지 않았습니다'), values: [] };
    }
    return null;
  }

  // 시스템이 한 일: 사람 · 에이전트 단계가 아닌 끝난 작업 행 — 시작 시각 순, 같은 시각(한 전이 사슬에서 연달아 끝남)이면 흐름 순서(서버 flow_order)
  function systemSteps(view) {
    const human = w => !w.agent_orch && !w.agent_mode;
    const agent = w => !!w.agent_mode || w.agent_orch === 'cliagents';
    const events = new Set((view.definition?.events || []).map(ev => ev.id));
    const order = view.flow_order || {};
    return (view.workitems || []).filter(w => !human(w) && !agent(w) && !events.has(w.activity_id) && ['DONE', 'IN_PROGRESS', 'SUBMITTED', 'PENDING'].includes(w.status))
      .sort((a, b) => String(a.start_date || '').localeCompare(String(b.start_date || '')) || (order[a.activity_id] ?? 0) - (order[b.activity_id] ?? 0));
  }
  function refOf(out) {
    if (!out || typeof out !== 'object') return '';
    for (const v of Object.values(out)) if (v && typeof v === 'object' && (v.ref || v.id) && typeof (v.ref || v.id) === 'string') return v.ref || v.id;
    return '';
  }

  function html(view) {
    const inst = view.instance || {};
    const v = Object.fromEntries((inst.variables_data || []).map(r => [r.key, r.value]));
    const rep = fromValues(v);
    const sys = systemSteps(view);
    if (!rep && !v.approved_by && !sys.length) return '';
    const done = inst.status === 'COMPLETED';
    const verdict = rep ? rep.verdict || 'other' : done ? 'other' : 'wait';
    const tone = verdict === 'ok' ? 'ok' : verdict === 'fail' ? 'fail' : verdict === 'wait' ? 'wait' : 'other';      // 반려는 실패가 아니라 사람이 내린 결정이다 — 무채색
    const label = (rep && rep.label) || (verdict === 'other' && done && !rep ? '처리 완료' : LABEL[verdict]);
    const approvalKey = (view.definition?.activities || []).find(a => a.tool === 'formHandler:approve')?.approval?.key || 'slot';
    const chosen = (v.chosen_option && v.chosen_option.name) || v.approved_option?.[approvalKey] || '';
    // 승인자 이름은 승인 경로가 처리 건 값에 넣은 approved_by_name(서버가 사람 목록에서 고른 이름) — 화면이 따로 찾지 않는다
    // 이름 칸이 없는 옛 기록은 담당자 id(user:…)를 그대로 내지 않고 사람 이름 사전으로 바꾼다
    const approver = v.approved_by_name || (v.approved_by ? UI.who(v.approved_by) : '');
    // 흐름 순서가 응답에 없으면 같은 시각에 끝난 단계의 앞뒤를 가를 수 없다 — 학생이 고칠 일이 아니므로 화면이 아니라 개발자 도구에, 처리 건마다 한 번
    if (!view.flow_order && sys.length > 1 && !orderWarned.has(inst.proc_inst_id)) {
      orderWarned.add(inst.proc_inst_id);
      console.error('[hydResultReport] 처리 건 응답에 flow_order 가 없어 같은 시각에 끝난 단계의 순서를 가를 수 없습니다', inst.proc_inst_id);
    }
    // 결과 한 장(디자인 기준 5-2): 결과 문장 하나(판정 — 요약)와 그 아래 값 · 승인한 안. 흰 바탕, 왼쪽에 상태색 점 하나.
    // 시스템이 한 일의 목록은 바로 아래 단계 기록이 보이므로 여기에 다시 그리지 않는다(한 가지는 한 곳에서)
    const summary = rep && rep.summary ? UI.idText(rep.summary) : !done && inst.status === 'RUNNING' ? '시스템이 실행하고 확인하는 중입니다. 끝나면 결과가 여기에 올라옵니다.' : '';
    const end = inst.end_label && inst.end_label !== label ? inst.end_label : '';
    const values = (rep && rep.values || []).map(x => `<dt>${e(UI.idText(x.name))}</dt><dd class="num"${x.ok === false ? ' data-bad' : ''}>${e(num(x.value))}${x.unit ? ' ' + e(x.unit) : ''}${x.limit != null ? ` <span class="muted">· 기준 ${e(x.limit)}</span>` : ''}${x.ok === false ? ' · 기준 밖' : ''}</dd>`).join('');
    const who = chosen || v.approved_by ? `<dt>승인한 안</dt><dd>${e(UI.idText(chosen || '–'))}${approver ? ` <span class="muted">· ${e(approver)}${v.approved_role ? ` (${e(UI.roleName(v.approved_role, view.definition))})` : ''}</span>` : ''}</dd>` : '';
    // 결론 카드(키트 .step-card > .result): 상태 뱃지 + 보고 제목 → 결과 한 문장 → 값 · 승인한 안. 끝 이벤트의 이름이 「끝」처럼 뜻 없는 말이면 그 줄을 그리지 않는다
    const TONE = { ok: 'success', fail: 'danger', wait: 'accent', other: 'neutral' };
    const endLine = end && !UI.plainEnd(end) ? `처리 건은 「${end}」에서 끝났습니다.` : '';
    return `<section class="step-card case-result" data-tone="${tone}" aria-label="결과"><div class="result">
      <div class="result-label">${UI.chipText(label, TONE[tone])}${e((rep && rep.title) || '결과')}</div>
      <div class="result-main">${e(summary || label)}</div>
      ${endLine ? `<div class="result-sub">${e(endLine)}</div>` : ''}</div>
      ${values || who ? `<dl class="kv">${values}${who}</dl>` : ''}
      ${rep && rep.valuesError ? `<p class="muted" data-tone="danger">${e(rep.valuesError)}</p>` : ''}
    </section>`;
  }
  window.hydResultReport = { html, fromValues, receiptDetail, incidentMeaning };
})();
