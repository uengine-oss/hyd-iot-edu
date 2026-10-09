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
    return OK.has(s) ? 'ok' : FAIL.has(s) ? 'fail' : s ? 'other' : '';
  }
  const num = x => (typeof x === 'number' && Number.isFinite(x) ? x.toLocaleString('ko-KR', { maximumFractionDigits: 2 }) : x == null || x === '' ? '–' : x === true ? '예' : x === false ? '아니오' : x);
  const LABEL = { ok: '정상', fail: '미달', other: '확인 결과', wait: '확인 중' };

  function fromValues(v) {
    const r = v.result_report;
    if (r && typeof r === 'object') {
      // C2/C3 계약: outcome(화면 배지 문구: 정상 · 미달 · 지연 · 입고 완료 · 승인 지연 · 알림) + level/verdict(ok · fail · info → 색)
      const level = String(r.level ?? r.verdict ?? '').toLowerCase();
      const verdict = level === 'info' ? 'other' : verdictOf(r.level ?? r.verdict ?? r.ok ?? r.status ?? r.outcome);
      const free = r.verdict && !OK.has(String(r.verdict).toLowerCase()) && !FAIL.has(String(r.verdict).toLowerCase()) && String(r.verdict).toLowerCase() !== 'info' ? String(r.verdict) : '';
      return { verdict: verdict || verdictOf(r.outcome), label: r.outcome ? String(r.outcome) : free, title: r.title, summary: r.summary || r.text, values: Array.isArray(r.values) ? r.values : [] };
    }
    if (v.test_run && typeof v.test_run === 'object') return { verdict: verdictOf(v.test_run.ok ?? v.test_run.verdict), title: '시운전 확인', summary: v.test_run.summary || '', values: Array.isArray(v.test_run.values) ? v.test_run.values : [] };
    if (typeof v.recovered === 'boolean') return { verdict: v.recovered ? 'ok' : 'fail', title: '재관측 확인', summary: v.recovered ? '경보가 풀리고 기준 안으로 돌아왔습니다' : '기준 안으로 돌아오지 않았습니다', values: [] };
    if (typeof v.received === 'boolean' || (v.goods_receipt && typeof v.goods_receipt === 'object')) {
      const g = v.goods_receipt || {}, ok = v.received === true || g.ok === true;
      return { verdict: ok ? 'ok' : 'fail', title: '입고 확인', summary: g.detail || (ok ? '입고와 검수가 끝났습니다' : '기한 안에 입고되지 않았습니다'), values: [] };
    }
    return null;
  }

  // 시스템이 한 일: 사람 · 에이전트 단계가 아닌 끝난 작업 행(시간 순)
  function systemSteps(view) {
    const human = w => !w.agent_orch && !w.agent_mode;
    const agent = w => !!w.agent_mode || w.agent_orch === 'cliagents';
    return (view.workitems || []).filter(w => !human(w) && !agent(w) && ['DONE', 'IN_PROGRESS', 'SUBMITTED', 'PENDING'].includes(w.status) && !/timeout/.test(w.activity_id || ''))
      .sort((a, b) => String(a.start_date || '').localeCompare(String(b.start_date || '')));
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
    const tone = verdict === 'ok' ? 'ok' : verdict === 'fail' ? 'fail' : verdict === 'wait' ? 'wait' : 'other';
    const label = (rep && rep.label) || (verdict === 'other' && done && !rep ? '처리 끝' : LABEL[verdict]);
    const chosen = (v.chosen_option && v.chosen_option.name) || '';
    // 승인자는 사람 id(user:…)로 저장된다 — 화면에는 이름(id)으로 (C3: 블랙박스 점검에서 id만 보이던 곳)
    const personName = id => { const p = window.hydInbox && window.hydInbox.X && (window.hydInbox.X.people || []).find(x => x.id === id); return p ? `${p.name} (${id})` : id; };
    const values = (rep && rep.values || []).map(x => `<div class="rr-val ${x.ok === false ? 'bad' : x.ok === true ? 'good' : ''}"><span>${e(UI.idText(x.name))}</span><b class="num">${e(num(x.value))}${x.unit ? ' ' + e(x.unit) : ''}</b>${x.limit != null ? `<small>기준 ${e(x.limit)}</small>` : ''}</div>`).join('');
    const steps = sys.map(w => {
      const st = w.status === 'DONE' ? 'done' : 'run';
      const ref = refOf(w.output);
      return `<li class="${st}"><span class="rr-dot" aria-hidden="true"></span><span class="rr-step">${e(UI.flowName ? UI.flowName(w.activity_name) : w.activity_name)}</span>${ref ? `<span class="mono rr-ref">${e(ref)}</span>` : ''}<span class="muted rr-time">${w.end_date ? e(UI.time(w.end_date)) : e(UI.t('trace.running'))}</span></li>`;
    }).join('');
    return `<section class="rr-card tone-${tone}" aria-label="결과 보고">
      <div class="rr-head"><span class="rr-badge">${e(label)}</span><div><h4>${e((rep && rep.title) || '결과 보고')}</h4>${rep && rep.summary ? `<p>${e(UI.idText(rep.summary))}</p>` : !done ? '<p>시스템이 실행하고 확인하는 중입니다. 끝나면 여기에 결과가 올라옵니다.</p>' : ''}</div></div>
      ${values ? `<div class="rr-vals">${values}</div>` : ''}
      ${chosen || v.approved_by ? `<p class="rr-who"><span class="ap-label">승인한 안</span> <b>${e(UI.idText(chosen || '–'))}</b>${v.approved_by ? ` · ${e(personName(v.approved_by))}${v.approved_role ? ` (${e(UI.who(v.approved_role))})` : ''}` : ''}</p>` : ''}
      ${steps ? `<div class="rr-steps-wrap"><span class="ap-label">시스템이 한 일</span><ol class="rr-steps">${steps}</ol></div>` : ''}
    </section>`;
  }
  window.hydResultReport = { html, verdictOf, fromValues };
})();
