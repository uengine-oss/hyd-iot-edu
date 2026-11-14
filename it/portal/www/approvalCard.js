/* A161-U1 — 승인 요약 카드 (세 시나리오 공통: 긴급 대응 · 정기 정비 · 예비품 구매).
   확정된 흐름 모양: 에이전트가 추천안 하나를 짧은 이유와 함께 가져오고 → 담당자가 한 번 승인하고 → 시스템이 실행 · 확인 · 결과 보고.
   그래서 승인 화면은 "카드 한 장": 추천안 · 이유 몇 줄 · 핵심 근거(지식 그래프 경로 + 출처 절) · 승인 버튼. 진 안과 그 이유는 접기.

   참고 화면(모방):
   - Camunda Tasklist 작업 상세 — 머리(작업 이름 · 처리 건 · 기한 · 담당) 아래 요약, 맨 아래 한 줄 행동 버튼(완료).
     https://docs.camunda.io/docs/components/tasklist/userguide/using-tasklist/
   - process-gpt-vue3 (/Users/uengine/process-gpt/services/frontend) src/components/apps/todolist/WorkItem.vue · DefaultWorkItem.vue:33,92
     — 작업 머리 · 내용 · 하단 주 버튼 하나, src/ds/components/PgCard.vue(안쪽 여백 · 둥근 모서리) · PgAlert.vue(강조 상자) · PgChip.vue.
   - Linear 이슈 사이드 요약 — 칩 한 줄 · 회색 작은 라벨 · 값.
   데이터는 판단 결과(options · recommended · explanation)만 쓴다. 시나리오 이름 · id 를 코드에 두지 않는다. */
(function () {
  const e = s => (typeof esc === 'function' ? esc(s) : String(s ?? ''));
  const num = v => Number.isFinite(+v) ? window.hydWords.num(+v) : '';   // 숫자 형식은 포털 하나(plainWords W.num — 크기별 자릿수, W1-12)

  // 판단 설명에서 그 안을 말한 문장 하나를 꺼낸다("2순위 '팬 최대'(…)는 … 남습니다.") — 진 이유를 판단 엔진 설명(규칙 문장) 그대로 보인다
  function sentenceAbout(text, name) {
    if (!text || !name) return '';
    const parts = String(text).split(/(?<=[.。])\s+/);
    return parts.find(p => p.includes(`'${name}'`) || p.includes(`‘${name}’`) || p.includes(`"${name}"`)) || '';
  }
  const scoreText = o => window.hydWords?.purchaseEconomics(o) ? hydWords.purchaseCostLabel(o) : Number.isFinite(+o.score) ? `${num(o.score)}점` : '';

  /* 머리말 값(라이브 3차): 예측은 "이 안을 고르면 설비가 어떻게 되나"다. 판단 엔진은 모든 안에 예측을 붙인다(순위 식의 예측 · 품질 성분,
     규정의 예측 유온 검사, 승인 순간 재확인이 쓴다). 그러나 머리말에는 고르는 근거일 때만 둔다 — 설비를 바꾸는 안(kind control)이거나,
     안마다 예측이 달라 비교가 되는 때. 설비 명령이 없는 업무 안(발주 · 정비 오더)끼리 예측이 모두 같으면 그 값은 '지금 설비 그대로'라
     고르는 데 쓰이지 않으므로, 그 안의 업무 값(카드마다 다른 사실 · 작업지시의 정비 시점)을 머리말로 둔다. 시나리오 이름으로 가르지 않는다. */
  const fcKey = o => (o.forecast || []).map(f => `${f.variable}=${num(f.value)}`).join('|');
  function forecastDecides(o, options) {
    if (!Array.isArray(options)) throw new Error('forecastDecides: 같은 판단의 안 목록(options)이 필요합니다');
    if (!(o.forecast || []).length) return false;
    if (o.kind === 'control') return true;
    return options.some(x => x.id !== o.id && (x.forecast || []).length && fcKey(x) !== fcKey(o));
  }
  // 이 안의 업무 값(글): 판단 수준에서는 비어 있는 카드별 사실(발주 금액 · 공급사 불량률 · 납기 여유 · AVL — 규칙이 이 값으로 감점 · 제외)
  // + 예측이 머리말이 아닌 업무 안이 작업지시를 내면 카드가 실어 온 정비 시점과 그때의 운전시간
  function ownValues(o, d) {
    const W = window.hydWords, facts = d.facts || {};
    const out = Object.entries(o.facts || {}).filter(([k, x]) => W.known(k) && x != null && typeof x !== 'object' && facts[k] == null)
      .map(([k, x]) => `${W.fieldName(k,o.facts)} ${W.value(k, x)}`);
    const w = o.window;
    if (w && !forecastDecides(o, d.options) && (o.actions || []).some(a => a.code === 'WO_CREATE')) {
      out.push(`정비 시점 ${w.name}${w.starts_at ? ` (${UI.dateTime(w.starts_at)})` : ''}`);
      if (w.basis && W.known(w.basis) && facts[w.basis] != null) out.push(`${W.fieldName(w.basis)} ${W.value(w.basis, facts[w.basis])}`);
    }
    return out;
  }
  function businessContext(o, d) {
    if((o.actions || []).some(a=>a.code==='PR_CREATE')) return window.hydWords.purchaseContextHtml(o,d);
    if (o.kind === 'control' || forecastDecides(o, d.options)) return '';
    const values = { ...(d.facts || {}), ...(o.facts || {}) }, W = window.hydWords;
    const purchase = (o.actions || []).some(a => a.code === 'PO_CREATE');
    const maintenance = (o.actions || []).some(a => a.code === 'WO_CREATE');
    const keys = purchase ? ['part_no', 'need_qty', 'po_amount', 'lead_slack_days'] : maintenance ? ['hours_since_pm', 'pm_interval_h', 'pm_due_in_h', 'spare_available'] : [];
    const rows = keys.filter(k => values[k] != null).map(k => `<dt>${e(W.fieldName(k))}</dt><dd>${e(W.value(k, values[k]))}</dd>`).join('');
    return rows ? `<section class="cr-sec" aria-label="${purchase ? '구매 요청' : '정비 요청'}"><h4 class="cr-h">${purchase ? '구매 요청' : '정비 요청'}</h4><dl class="kv">${rows}</dl></section>` : '';
  }

  // 짧은 이유(최대 4줄): 머리말 값(예측 또는 이 안의 업무 값) · 좋아지는 지표 · 나빠지는 지표 · 같은 선택 선례 · 주의(감점 · 경고)
  // d: 같은 판단({options, facts}). opt.head=false 면 머리말 값을 빼고(처리 기록처럼 머리말을 따로 그린 곳)
  function reasons(o, d, opt = {}) {
    const out = [];
    if (opt.head !== false) {
      if (forecastDecides(o, d.options)) {
        const f = (o.forecast || []).slice(0, 2).map(x => `${e(UI.idText(x.name))} <b class="num">${e(num(x.value))}${x.unit ? ' ' + e(x.unit) : ''}</b>`);
        out.push(`예측 ${f.join(' · ')}`);
      } else {
        const v = ownValues(o, d);
        if (v.length) out.push(`이 안의 값 ${v.map(e).join(' · ')}`);
      }
    }
    const g = (o.gains || []).filter(x => !x.conditional).map(x => e(x.name));
    if (g.length) out.push(`좋아지는 것 ${g.join(' · ')}`);
    const l = (o.losses || []).filter(x => !x.conditional).map(x => e(x.name));
    if (l.length) out.push(`감수할 것 ${l.join(' · ')}`);
    if (o.precedent && o.precedent.n) out.push(`과거 같은 선택 ${o.precedent.n}건(${e(UI.t('card.precedentFixed'))})${o.precedent.reasons && o.precedent.reasons[0] ? ` — ${e(o.precedent.reasons[0])}` : ''}`);   // 선례는 미리 넣은 예시 고정(dmn_mcp) — 실제 승인 이력처럼 읽히지 않게
    const warn = [...(o.penalties || []), ...(o.warnings || [])].map(v => e(UI.idText(v.annotation || v.message || v.name || v.rule || '')));
    if (warn.length) out.push(`<b>주의</b> ${warn.slice(0, 2).join(' · ')}`);
    return out.slice(0, 4);
  }

  // 핵심 근거: 지식 그래프 경로 하나(조치 → … → 지표) + 출처 절(매뉴얼 · 규칙 근거)
  function evidence(o) {
    const path = (o.tradeoffEvaluation || []).find(p => (p.nodes || []).length > 1) || null;
    // 경로의 첫 노드는 이 안(스킬) 자신이다 — 문서에서 적재한 스킬 id 는 정적 이름 사전(names.json)에 없으므로 카드의 이름을 쓴다
    const pathHtml = path ? path.nodes.map(n => `<span class="ap-node">${e(n === o.id ? UI.idText(o.name || n) : UI.name ? UI.name(n) : n)}</span>`).join(UI.icon('arrow-right')) : '';
    const refs = new Map();
    (o.steps || []).forEach(s => { if (s.manual && s.manual.ref) refs.set(s.manual.ref, s.manual.title || ''); });
    (o.selectedBy || []).forEach(r => (r.sources || []).forEach(src => { if (!refs.has(src)) refs.set(src, ''); }));
    const refHtml = [...refs].slice(0, 4).map(([ref, title]) => `<span class="badge" data-variant="secondary" title="${e(title)}">${e(ref)}${title ? ' ' + e(title) : ''}</span>`).join(' ');
    if (!pathHtml && !refHtml) return '';
    return `<div class="ap-evidence">${pathHtml ? `<div class="ap-row"><span class="ap-label">지식 지도 근거</span><span class="ap-path">${pathHtml}</span></div>` : ''}
      ${refHtml ? `<div class="ap-row"><span class="ap-label">출처</span><span class="chips">${refHtml}</span></div>` : ''}</div>`;
  }

  // 추천안과 견준 점수 항목 차이(지는 쪽 큰 것 2개 · 이기는 쪽 큰 것 1개) — "어디서 졌나"를 말로. 승인 카드 · 처리 기록이 이 하나를 쓴다
  // (numbers: 처리 기록처럼 점수 차이 숫자를 함께 보일 때)
  function partDiff(o, rec, options, { numbers = false } = {}) {
    const economic=window.hydWords?.purchaseCostDiff(o,rec);
    if (economic) return economic;
    const a = o.scoreParts || {}, b = (rec && rec.scoreParts) || {};
    const d = Object.keys({ ...a, ...b }).map(k => [k, (+a[k] || 0) - (+b[k] || 0)]).filter(([, x]) => Math.abs(x) >= 0.05);
    const part = ([k, x]) => UI.t('score.' + k) + (numbers ? ` ${x > 0 ? '+' : ''}${num(x)}` : '');
    const lose = d.filter(([, x]) => x < 0).sort((x, y) => x[1] - y[1]).slice(0, 2).map(part);
    const win = d.filter(([, x]) => x > 0).sort((x, y) => y[1] - x[1]).slice(0, 1).map(part);
    const f = forecastDecides(o, options) ? (o.forecast || [])[0] : null, rf = rec && (rec.forecast || []).find(x => f && x.variable === f.variable);
    const fc = f && rf ? `${UI.idText(f.name)} ${num(f.value)}${f.unit ? ' ' + f.unit : ''} (추천 ${num(rf.value)}${rf.unit ? ' ' + rf.unit : ''})` : '';
    return [lose.length ? `${lose.join(' · ')}에서 뒤짐` : '', win.length ? `${win.join(' · ')}에서 앞섬` : '', fc].filter(Boolean).join(' · ');
  }

  // 진 안 한 줄: 이름 · 점수 · 진 이유(제외 규칙 > 점수 항목 차이 + 에이전트 설명의 그 문장)
  function lostRow(o, rec, d, chosenId, pending) {
    const explanation = d.explanation;
    const out = !o.feasible;
    const said = UI.idText(sentenceAbout(explanation, o.name).replace(/^\s*\d+순위\s*/, ''));
    const why = out && (o.violations || [])[0] ? `제외 — ${e(UI.idText(o.violations[0].annotation || o.violations[0].message || o.violations[0].rule || ''))}`
      : e(partDiff(o, rec, d.options) || (rec && Number.isFinite(+o.score) && Number.isFinite(+rec.score) ? `추천안보다 점수가 ${num(rec.score - o.score)} 낮습니다` : ''));
    const pick = pending && o.feasible && !UI.executionBlocked(o,d) ? `<label class="ap-switch"><input type="radio" name="hopt" value="${e(o.id)}" ${o.id === chosenId ? 'checked' : ''}> 이 안으로 변경</label>` : '';
    return `<li class="ap-lost"${out ? ' data-out' : ''}><div class="ap-lost-head"><b>${e(UI.idText(o.name))}</b>${out ? UI.chipText(UI.t('chip.excluded'), 'danger') : `<span class="muted num">${e(scoreText(o))}</span>`}${pick}</div>${UI.evaluationHtml(o,d)}${window.hydWords?.purchaseContextHtml(o,d) || ''}${window.hydWords?.maintenanceHtml(o) || ''}${why ? `<p>${why}</p>` : ''}${said && !out ? `<p class="muted">${e(said)}</p>` : ''}</li>`;
  }

  /* d: 판단 결과 { options, recommended, explanation }, chosenId: 지금 승인할 안, opt: { pending, adjust(html), extra(html) } */
  // 추천이 없고 모든 안이 제외됐을 때: 제외된 안을 「1순위」로 띄우지 않고, 추천할 안이 없다는 것과 안마다 제외 사유를 보인다
  const excludedWhy = o => (o.violations || []).map(v => UI.idText(v.annotation || v.message || v.rule || '')).filter(Boolean);
  /* 모든 안이 제외됐을 때의 까닭을 화면 말로: 안마다의 첫 사유(다른 값을 몰라서 따라 걸린 규칙 — unknown 이 붙은 것 — 은 뺀다)에서
     운영자에게 하는 말(「— … 확인하고 다시 판단하세요」)과 내부 이름 괄호(「(forecast_ts1)」)를 떼어 낸 문장. 모든 안의 까닭이 같으면 same = true 로 한 번만 말한다.
     받은 원문은 noneHtml 의 접기 안에 그대로 있다 */
  function noneSummary(d) {
    const opts = d.options || [];
    const plain = t => UI.idText(String(t || '')).split(' — ')[0].replace(/\s*\([a-z][a-z0-9_]*(?:,\s*[a-z][a-z0-9_]*)*\)/g, '').replace(/\s+/g, ' ').trim().replace(/[.:]+$/, '');
    const main = o => { const vs = o.violations || []; const own = vs.filter(v => !(v.unknown || []).length); return [...new Set((own.length ? own : vs).map(v => plain(v.annotation || v.message || '')).filter(Boolean))]; };
    const per = opts.map(o => ({ name: UI.idText(o.name || o.id), reasons: main(o) }));
    const key = r => r.reasons.join('|');
    const same = per.length > 0 && !!per[0].reasons.length && per.every(r => key(r) === key(per[0]));
    return { same, reasons: same ? per[0].reasons : [], per };
  }
  function noneHtml(d, opt) {
    const opts = d.options || [], sum = noneSummary(d);
    // 까닭이 모두 같으면 판의 머리가 이미 한 번 말했다 — 여기서는 제외된 안의 이름만 늘어놓고, 안마다의 사유 원문(규칙 이름 · 내부 값 이름 포함)은 접어 둔다
    if (sum.same) return `<div class="ap-card" data-ap-none>
      <div class="ap-row"><span class="ap-label">제외된 안 ${opts.length}개</span><span class="chips">${sum.per.map(r => `<span class="badge" data-variant="secondary">${e(r.name)}</span>`).join('')}</span></div>
      ${UI.fold('안마다의 제외 사유 원문', `<ul class="ap-lost-list">${opts.map(o => `<li class="ap-lost"><div class="ap-lost-head"><b>${e(UI.idText(o.name || o.id))}</b></div>${excludedWhy(o).map(w => `<p>${e(w)}</p>`).join('') || '<p>실행 검사를 통과하지 못했습니다</p>'}</li>`).join('')}</ul>`)}
      ${opt.adjust || ''}
      ${d.explanation ? UI.fold('판단 엔진 설명 전문 (규칙 문장)', `<p class="prose" style="margin:0">${e(UI.idText(d.explanation))}</p>`) : ''}
      ${opt.extra || ''}
    </div>`;
    return `<div class="ap-card" data-ap-none>
      <p class="ap-desc">안마다 제외된 까닭이 다릅니다.</p>
      <ul class="ap-lost-list">${opts.map(o => { const why = excludedWhy(o); return `<li class="ap-lost" data-out><div class="ap-lost-head"><b>${e(UI.idText(o.name || o.id))}</b>${UI.chipText(UI.t('chip.excluded'), 'danger')}</div><p>제외 — ${e(why.length ? why.join(' · ') : '실행 검사를 통과하지 못했습니다')}</p></li>`; }).join('')}</ul>
      ${opt.adjust || ''}
      ${d.explanation ? UI.fold('판단 엔진 설명 전문 (규칙 문장)', `<p class="prose" style="margin:0">${e(UI.idText(d.explanation))}</p>`) : ''}
      ${opt.extra || ''}
    </div>`;
  }
  function html(d, chosenId, opt = {}) {
    const opts = d.options || [];
    if (opts.length && !d.recommended && !opts.some(o => o.feasible)) return noneHtml(d, opt);
    const rec = opts.find(o => o.id === d.recommended) || opts.find(o => o.feasible) || opts[0] || {};
    const cur = opts.find(o => o.id === chosenId) || rec;
    const changed = cur.id !== rec.id;
    const others = opts.filter(o => o.id !== cur.id).sort((a, b) => (b.feasible - a.feasible) || ((a.rank || 99) - (b.rank || 99)));
    const rs = reasons(cur, d);
    const actions = (cur.actions || []).map(a => window.hydCards ? hydCards.actionLabel(a, cur) : a.name).filter(Boolean);
    const evaluation=UI.evaluationInfo(cur,d), blocked=UI.executionBlocked(cur,d);
    return `<div class="ap-card"${changed ? ' data-changed' : ''}>
      <div class="ap-head"><span class="ap-kicker">${changed ? '직접 고른 안' : evaluation.state==='analysis' ? '모의 판단 1순위' : evaluation.state==='execution' ? '판단 엔진 1순위 (AI가 고른 원인 · 근거로 계산)' : '1순위 (실행 가능 여부 미검증)'}</span>${changed && !blocked ? `<button type="button" class="btn" data-variant="ghost" data-size="sm" data-ap-back="${e(rec.id)}">추천안으로 되돌리기</button>` : ''}</div>
      ${UI.evaluationHtml(cur,d,{raw:false})}
      <h4 class="ap-title">${e(UI.idText(cur.name || '–'))}</h4>
      ${cur.description ? `<p class="ap-desc">${e(UI.idText(cur.description))}</p>` : ''}
      ${businessContext(cur, d)}
      ${window.hydWords?.maintenanceHtml(cur) || ''}
      ${rs.length ? `<ul class="ap-reasons">${rs.map(r => `<li>${r}</li>`).join('')}</ul>` : ''}
      ${actions.length ? `<p class="ap-do"><span class="ap-label">${evaluation.state==='execution' ? '승인하면 시스템이' : '모의 판단에 포함된 조치(승인 · 실행되지 않음)'}</span> ${actions.map(a => `<span class="badge" data-variant="secondary">${e(a)}</span>`).join(' ')}</p>` : ''}
      ${evidence(cur)}
      ${opt.adjust || ''}
      ${others.length ? UI.fold(`다른 조치 안 ${others.length}개 비교`, `<ul class="ap-lost-list">${others.map(o => lostRow(o, rec, d, chosenId, opt.pending)).join('')}</ul>`) : ''}
      ${d.explanation ? UI.fold('판단 엔진 설명 전문 (규칙 문장)', `<p class="prose" style="margin:0">${e(UI.idText(d.explanation))}</p>`) : ''}
      ${opt.extra || ''}
      ${UI.evaluationRawHtml(cur,d)}
    </div>`;
  }
  /* ---------------- 처리 건 화면의 「내가 할 일」 카드(디자인 기준 5-4)가 쓰는 두 조각 ----------------
     카드의 첫 화면은 물음 하나 · 승인하면 일어나는 일 · 단추뿐이다. 왜 이것이 1순위인지와 다른 안은 바로 아래 단계 기록의 AI 단계가 보이고,
     [다른 안 고르기]를 눌렀을 때만 이 표(choicesHtml)가 카드 안에 펼쳐진다. */
  // 지금 승인할 안과 추천안 · 승인하면 시스템이 하는 일(서버가 준 조치 목록) · 평가 상태
  function pick(d, chosenId) {
    const opts = d.options || [];
    const rec = opts.find(o => o.id === d.recommended) || opts.find(o => o.feasible) || opts[0] || {};
    const cur = opts.find(o => o.id === chosenId) || rec;
    const actions = (cur.actions || []).map(a => window.hydCards ? hydCards.actionLabel(a, cur) : a.name).filter(Boolean);
    return { rec, cur, changed: cur.id !== rec.id, actions, state: UI.evaluationInfo(cur, d).state, blocked: UI.executionBlocked(cur, d),
             none: opts.length > 0 && !d.recommended && !opts.some(o => o.feasible) };
  }
  // 고를 수 있는 안 전부를 표 한 장으로: 고르기 · 조치(둘째 줄에 고른 까닭 또는 진 까닭) · 점수. opt: { pending, adjust(html), extra(html) }
  function choicesHtml(d, chosenId, opt = {}) {
    const { rec, cur } = pick(d, chosenId);
    const opts = [...(d.options || [])].sort((a, b) => (b.id === rec.id) - (a.id === rec.id) || (b.feasible - a.feasible) || ((a.rank || 99) - (b.rank || 99)));
    const rows = opts.map(o => {
      const out = !o.feasible, can = opt.pending && o.feasible && !UI.executionBlocked(o, d);
      const said = UI.idText(sentenceAbout(d.explanation, o.name).replace(/^\s*\d+순위\s*/, ''));
      const why = o.id === rec.id ? reasons(o, d).join(' · ')
        : out ? `제외 — ${e(excludedWhy(o).join(' · ') || '실행 검사를 통과하지 못했습니다')}`
        : e(partDiff(o, rec, d.options) || (Number.isFinite(+o.score) && Number.isFinite(+rec.score) ? `추천안보다 점수가 ${num(rec.score - o.score)} 낮습니다` : '')) + (said ? `<br>${e(said)}` : '');
      return { pick: o.id === cur.id, out, name: UI.idText(o.name), forId: `hopt-${o.id}`, noteHtml: why, score: out ? null : Number.isFinite(+o.score) ? +o.score : null, scoreHtml: out ? '제외' : Number.isFinite(+o.score) ? null : e(scoreText(o)),
        lead: `<input type="radio" class="input" name="hopt" id="hopt-${e(o.id)}" value="${e(o.id)}" ${o.id === cur.id ? 'checked' : ''} ${can ? '' : 'disabled'} aria-label="${e(UI.idText(o.name))} 안 고르기">`,
        nameHtml: (o.id === rec.id ? ' <span class="muted">· 1순위</span>' : '') + UI.evaluationHtml(o, d, { raw: false }) + (window.hydWords?.purchaseContextHtml(o, d) || '') + (window.hydWords?.maintenanceHtml(o) || '') };
    });
    return `${UI.optionsTable(rows, { lead: '고르기', cls: 'ap-choices' })}
      ${evidence(cur)}${opt.adjust || ''}
      ${d.explanation ? UI.fold('판단 엔진 설명 전문 (규칙 문장)', `<p class="prose" style="margin:0">${e(UI.idText(d.explanation))}</p>`) : ''}
      ${opt.extra || ''}${UI.evaluationRawHtml(cur, d)}`;
  }

  /* ---------------- 캡스톤 G7: 일반 사람 승인(formHandler:approve)의 "추천 1 + 지는 안 펼치기" 카드 ----------------
     에이전트 task 가 낸 처리 건 값(예: proposal)을 승인 부품 설정(approval: options · key · recommended · losers · docs)으로 읽는다.
     칸 약속(출발본 T6 요령): options[{<key, 기본 slot>, reason, score, …}] · recommended = 추천 안의 key 값 · losers[{<key>, why}] · docs[{title, link}].
     약속에서 벗어난 곳은 숨기지 않는다 — 무엇이 다른지 적고 받은 값을 JSON 그대로 펼쳐 보인다(problems). 서버 검사는 procsvc/approval_part.py. */
  const KEY_DEFAULT = 'slot';
  const isObj = x => x !== null && typeof x === 'object' && !Array.isArray(x);
  function at(values, path) {
    let cur = values;
    for (const part of String(path).split('.')) {
      if (Array.isArray(cur) && /^\d+$/.test(part) && +part < cur.length) cur = cur[+part];
      else if (isObj(cur) && Object.prototype.hasOwnProperty.call(cur, part)) cur = cur[part];
      else return undefined;
    }
    return cur;
  }

  /* values: 이 task 가 받은 값, cfg: 활동의 approval 설정 → { key, options, usable, rec, losers, docs, problems, raw } */
  function proposal(values, cfg) {
    cfg = cfg || {};
    const key = cfg.key || KEY_DEFAULT, problems = [], raw = {};
    if (!cfg.options) return { key, options: [], usable: false, rec: null, losers: [], docs: [], raw, problems: ['승인 설정에 고를 안 값(options)이 없습니다'] };
    const options = at(values || {}, cfg.options);
    raw[cfg.options] = options;
    let usable = Array.isArray(options) && options.length > 0;
    if (options === undefined) problems.push(`고를 안 '${cfg.options}' 이(가) 받은 값에 없습니다`);
    else if (!usable) problems.push(`고를 안 '${cfg.options}' 이(가) 비어 있거나 목록이 아닙니다`);
    const list = usable ? options : [];
    const seen = new Set();
    list.forEach((o, i) => {
      const n = i + 1;
      if (!isObj(o) || o[key] == null || o[key] === '') { problems.push(`${n}번째 안에 구분 칸 '${key}' 이(가) 없습니다`); usable = false; return; }
      if (seen.has(String(o[key]))) { problems.push(`'${key}' 값 ${o[key]} 이(가) 두 번 있습니다`); usable = false; }
      seen.add(String(o[key]));
      if (typeof o.reason !== 'string' || !o.reason.trim()) problems.push(`${n}번째 안(${o[key]})에 이유 칸 'reason' 이(가) 없습니다`);
      if (!Number.isFinite(o.score)) problems.push(`${n}번째 안(${o[key]})의 점수 칸 'score' 가 숫자가 아닙니다`);
    });
    let rec = null;
    if (cfg.recommended) {
      const r = at(values || {}, cfg.recommended);
      raw[cfg.recommended] = r;
      rec = list.find(o => isObj(o) && String(o[key]) === String(r)) || null;
      if (r !== undefined && !rec) problems.push(`추천 '${r}' 이(가) 고를 안 목록에 없습니다`);   // 칸이 없으면 추천 없음(선택 칸 — approval_part.CONFIG)
    }
    const listOf = (field, ok, what) => {
      if (!cfg[field]) return [];
      const v = at(values || {}, cfg[field]);
      raw[cfg[field]] = v;
      if (v === undefined) return [];   // 선택 칸 — 없으면 빈 목록(서버 approval_part 와 같은 규칙, W1-27)
      if (!Array.isArray(v)) { problems.push(`${what} '${cfg[field]}' 이(가) 목록이 아닙니다`); return []; }
      v.forEach((x, i) => { const why = ok(x); if (why) problems.push(`${what} ${i + 1}번째: ${why}`); });
      return v.filter(x => !ok(x));
    };
    const losers = listOf('losers', x => !isObj(x) || x[key] == null ? `구분 칸 '${key}' 이(가) 없습니다` : typeof x.why !== 'string' || !x.why.trim() ? `진 이유 칸 'why' 가 없습니다` : '', '지는 안');
    const docs = listOf('docs', x => !isObj(x) || typeof x.title !== 'string' ? `제목 칸 'title' 이(가) 없습니다` : !/^https?:\/\//.test(String(x.link || '')) ? `링크 칸 'link' 가 http(s) 주소가 아닙니다` : '', '근거 자료');
    return { key, options: list.filter(isObj), usable, rec, losers, docs, problems, raw };
  }

  const shown = v => (v !== null && typeof v === 'object' ? JSON.stringify(v) : String(v));
  function optionFacts(o, key) {
    return Object.entries(o).filter(([k, v]) => ![key, 'reason', 'score'].includes(k) && v != null && v !== '')
      .map(([k, v]) => `<span class="badge" data-variant="secondary">${e(k)} ${e(shown(v))}</span>`).join(' ');
  }

  /* m: proposal(...) 결과, chosenId: 지금 고른(또는 승인된) 안의 key 값, opt: { pending, extra(html) } */
  function proposalHtml(m, chosenId, opt = {}) {
    const key = m.key;
    const rec = m.rec || m.options[0] || null;
    const cur = m.options.find(o => String(o[key]) === String(chosenId)) || rec;
    const changed = !!(cur && rec && cur !== rec);
    const others = m.options.filter(o => o !== cur);
    const pick = o => opt.pending && m.usable ? `<label class="ap-switch"><input type="radio" name="hopt" value="${e(o[key])}"> 이 안으로 변경</label>` : '';
    const otherRows = others.map(o => `<li class="ap-lost"><div class="ap-lost-head"><b>${e(o[key])}</b><span class="muted num">${e(scoreText(o))}</span>${pick(o)}</div>${o.reason ? `<p>${e(o.reason)}</p>` : ''}${optionFacts(o, key) ? `<p class="chips">${optionFacts(o, key)}</p>` : ''}</li>`);
    const loserRows = m.losers.map(x => `<li class="ap-lost" data-out><div class="ap-lost-head"><b>${e(x[key])}</b>${UI.chipText(UI.t('chip.excluded'), 'danger')}</div><p>${e(x.why)}</p></li>`);
    const docs = m.docs.map(d => `<a class="chip" href="${e(d.link)}" target="_blank" rel="noopener noreferrer">${e(d.title)}</a>`).join(' ');
    const off = m.problems.length ? `<div class="alert ap-off" data-variant="destructive" role="alert">${UI.icon('circle-alert')}<h2>에이전트 제안이 칸 약속과 다릅니다</h2><section>아래에 받은 값을 그대로 보입니다.<ul>${m.problems.map(p => `<li>${e(p)}</li>`).join('')}</ul></section></div>`
      + UI.raw(m.raw, { title: '받은 값 그대로', open: true }) : '';
    const head = cur ? `<div class="ap-head"><span class="ap-kicker">${changed ? '직접 고른 안' : m.rec ? 'AI 에이전트 추천' : '첫 번째 안 (추천 표시 없음)'}</span>${changed && opt.pending ? `<button type="button" class="btn" data-variant="ghost" data-size="sm" data-ap-back="${e(rec[key])}">추천안으로 되돌리기</button>` : ''}</div>
      <h4 class="ap-title">${e(cur[key])}</h4>${cur.reason ? `<p class="ap-desc">${e(cur.reason)}</p>` : ''}
      <ul class="ap-reasons">${Number.isFinite(cur.score) ? `<li>점수 <b class="num">${e(scoreText(cur))}</b></li>` : ''}${optionFacts(cur, key) ? `<li class="chips">${optionFacts(cur, key)}</li>` : ''}</ul>` : `<p class="muted">고를 안이 없습니다.</p>`;
    const lost = otherRows.length + loserRows.length;
    return `<div class="ap-card"${changed ? ' data-changed' : ''}>${head}
      ${docs ? `<div class="ap-evidence"><div class="ap-row"><span class="ap-label">근거 자료</span><span class="chips">${docs}</span></div></div>` : ''}
      ${lost ? UI.fold(`다른 안 ${otherRows.length}개 · 제외된 안 ${loserRows.length}개 비교`, `<ul class="ap-lost-list">${[...otherRows, ...loserRows].join('')}</ul>`) : ''}
      ${off}${opt.extra || ''}</div>`;
  }

  window.hydApprove = { html, reasons, partDiff, forecastDecides, ownValues, sentenceAbout, proposal, proposalHtml, pick, choicesHtml, noneSummary };
})();
