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
  const num = (v, d = 1) => Number.isFinite(+v) ? (+v).toFixed(d).replace(/\.0+$/, '') : '';

  // 판단 설명에서 그 안을 말한 문장 하나를 꺼낸다("2순위 '팬 최대'(…)는 … 남습니다.") — 진 이유를 에이전트 말 그대로 보인다
  function sentenceAbout(text, name) {
    if (!text || !name) return '';
    const parts = String(text).split(/(?<=[.。])\s+/);
    return parts.find(p => p.includes(`'${name}'`) || p.includes(`‘${name}’`) || p.includes(`"${name}"`)) || '';
  }
  const scoreText = o => Number.isFinite(+o.score) ? `${num(o.score, 2)}점` : '';

  // 짧은 이유(최대 4줄): 예측 값 · 좋아지는 지표 · 나빠지는 지표 · 같은 선택 선례 · 주의(감점 · 경고)
  function reasons(o) {
    const out = [];
    const f = (o.forecast || []).slice(0, 2).map(x => `${e(UI.idText(x.name))} <b class="num">${e(num(x.value))}${e(x.unit || '')}</b>`);
    if (f.length) out.push(`예측 ${f.join(' · ')}`);
    const g = (o.gains || []).filter(x => !x.conditional).map(x => e(x.name));
    if (g.length) out.push(`좋아지는 것 ${g.join(' · ')}`);
    const l = (o.losses || []).filter(x => !x.conditional).map(x => e(x.name));
    if (l.length) out.push(`<span class="neg-soft">감수할 것 ${l.join(' · ')}</span>`);
    if (o.precedent && o.precedent.n) out.push(`과거 같은 선택 ${o.precedent.n}건${o.precedent.reasons && o.precedent.reasons[0] ? ` — ${e(o.precedent.reasons[0])}` : ''}`);
    const warn = [...(o.penalties || []), ...(o.warnings || [])].map(v => e(UI.idText(v.annotation || v.message || v.name || v.rule || '')));
    if (warn.length) out.push(`<span class="neg-soft">주의 ${warn.slice(0, 2).join(' · ')}</span>`);
    return out.slice(0, 4);
  }

  // 핵심 근거: 지식 그래프 경로 하나(조치 → … → 지표) + 출처 절(매뉴얼 · 규칙 근거)
  function evidence(o) {
    const path = (o.tradeoffEvaluation || []).find(p => (p.nodes || []).length > 1) || null;
    const pathHtml = path ? path.nodes.map(n => `<span class="ap-node">${e(UI.name ? UI.name(n) : n)}</span>`).join('<span class="ap-arrow" aria-hidden="true">→</span>') : '';
    const refs = new Map();
    (o.steps || []).forEach(s => { if (s.manual && s.manual.ref) refs.set(s.manual.ref, s.manual.title || ''); });
    (o.selectedBy || []).forEach(r => (r.sources || []).forEach(src => { if (!refs.has(src)) refs.set(src, ''); }));
    const refHtml = [...refs].slice(0, 4).map(([ref, title]) => `<span class="chip tone-neutral sm" title="${e(title)}">${e(ref)}${title ? ' ' + e(title) : ''}</span>`).join(' ');
    if (!pathHtml && !refHtml) return '';
    return `<div class="ap-evidence">${pathHtml ? `<div class="ap-row"><span class="ap-label">지식 그래프 근거</span><span class="ap-path">${pathHtml}</span></div>` : ''}
      ${refHtml ? `<div class="ap-row"><span class="ap-label">출처</span><span class="row-wrap">${refHtml}</span></div>` : ''}</div>`;
  }

  // 추천안과 견준 점수 항목 차이(지는 쪽 큰 것 2개 · 이기는 쪽 큰 것 1개) — "어디서 졌나"를 숫자 대신 말로
  function partDiff(o, rec) {
    const a = o.scoreParts || {}, b = (rec && rec.scoreParts) || {};
    const d = Object.keys({ ...a, ...b }).map(k => [k, (+a[k] || 0) - (+b[k] || 0)]).filter(([, x]) => Math.abs(x) >= 0.05);
    const lose = d.filter(([, x]) => x < 0).sort((x, y) => x[1] - y[1]).slice(0, 2).map(([k]) => UI.t('score.' + k));
    const win = d.filter(([, x]) => x > 0).sort((x, y) => y[1] - x[1]).slice(0, 1).map(([k]) => UI.t('score.' + k));
    const f = (o.forecast || [])[0], rf = rec && (rec.forecast || []).find(x => f && x.variable === f.variable);
    const fc = f && rf ? `${UI.idText(f.name)} ${num(f.value)}${f.unit || ''} (추천 ${num(rf.value)}${rf.unit || ''})` : '';
    return [lose.length ? `${lose.join(' · ')}에서 뒤짐` : '', win.length ? `${win.join(' · ')}에서 앞섬` : '', fc].filter(Boolean).join(' · ');
  }

  // 진 안 한 줄: 이름 · 점수 · 진 이유(제외 규칙 > 점수 항목 차이 + 에이전트 설명의 그 문장)
  function lostRow(o, rec, explanation, chosenId, pending) {
    const out = !o.feasible;
    const said = UI.idText(sentenceAbout(explanation, o.name).replace(/^\s*\d+순위\s*/, ''));
    const why = out && (o.violations || [])[0] ? `제외 — ${e(UI.idText(o.violations[0].annotation || o.violations[0].message || o.violations[0].rule || ''))}`
      : e(partDiff(o, rec) || (rec && Number.isFinite(+o.score) && Number.isFinite(+rec.score) ? `추천안보다 점수가 ${num(rec.score - o.score, 2)} 낮습니다` : ''));
    const pick = pending && o.feasible ? `<label class="ap-switch"><input type="radio" name="hopt" value="${e(o.id)}" ${o.id === chosenId ? 'checked' : ''}> 이 안으로 바꾸기</label>` : '';
    return `<li class="ap-lost ${out ? 'out' : ''}"><div class="ap-lost-head"><b>${e(UI.idText(o.name))}</b>${out ? UI.chipText(UI.t('chip.excluded'), 'danger') : `<span class="muted num">${e(scoreText(o))}</span>`}${pick}</div>${why ? `<p>${why}</p>` : ''}${said && !out ? `<p class="muted">${e(said)}</p>` : ''}</li>`;
  }

  /* d: 판단 결과 { options, recommended, explanation }, chosenId: 지금 승인할 안, opt: { pending, adjust(html), extra(html) } */
  function html(d, chosenId, opt = {}) {
    const opts = d.options || [];
    const rec = opts.find(o => o.id === d.recommended) || opts.find(o => o.feasible) || opts[0] || {};
    const cur = opts.find(o => o.id === chosenId) || rec;
    const changed = cur.id !== rec.id;
    const others = opts.filter(o => o.id !== cur.id).sort((a, b) => (b.feasible - a.feasible) || ((a.rank || 99) - (b.rank || 99)));
    const rs = reasons(cur);
    const actions = (cur.actions || []).map(a => window.hydCards ? hydCards.actionLabel(a) : a.name).filter(Boolean);
    return `<div class="ap-card ${changed ? 'changed' : ''}">
      <div class="ap-head"><span class="ap-kicker">${changed ? '담당자가 바꾼 안' : 'AI 에이전트 추천'}</span>${changed ? `<button type="button" class="btn small ghost" data-ap-back="${e(rec.id)}">추천안으로 되돌리기</button>` : ''}</div>
      <h4 class="ap-title">${e(UI.idText(cur.name || '–'))}</h4>
      ${cur.description ? `<p class="ap-desc">${e(UI.idText(cur.description))}</p>` : ''}
      ${rs.length ? `<ul class="ap-reasons">${rs.map(r => `<li>${r}</li>`).join('')}</ul>` : ''}
      ${actions.length ? `<p class="ap-do"><span class="ap-label">승인하면 시스템이</span> ${actions.map(a => `<span class="chip tone-neutral sm">${e(a)}</span>`).join(' ')}</p>` : ''}
      ${evidence(cur)}
      ${opt.adjust || ''}
      ${others.length ? UI.fold(`다른 안 ${others.length}개는 왜 졌나`, `<ul class="ap-lost-list">${others.map(o => lostRow(o, rec, d.explanation, chosenId, opt.pending)).join('')}</ul>`, { cls: 'small' }) : ''}
      ${d.explanation ? UI.fold('에이전트 설명 전문', `<p class="prose" style="margin:0">${e(UI.idText(d.explanation))}</p>`, { cls: 'small' }) : ''}
      ${opt.extra || ''}
    </div>`;
  }
  window.hydApprove = { html, reasons, sentenceAbout };
})();
