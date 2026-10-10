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
      if (r === undefined) problems.push(`추천 값 '${cfg.recommended}' 이(가) 받은 값에 없습니다`);
      else if (!rec) problems.push(`추천 '${r}' 이(가) 고를 안 목록에 없습니다`);
    }
    const listOf = (field, ok, what) => {
      if (!cfg[field]) return [];
      const v = at(values || {}, cfg[field]);
      raw[cfg[field]] = v;
      if (v === undefined) { problems.push(`${what} '${cfg[field]}' 이(가) 받은 값에 없습니다`); return []; }
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
      .map(([k, v]) => `<span class="chip tone-neutral sm">${e(k)} ${e(shown(v))}</span>`).join(' ');
  }

  /* m: proposal(...) 결과, chosenId: 지금 고른(또는 승인된) 안의 key 값, opt: { pending, extra(html) } */
  function proposalHtml(m, chosenId, opt = {}) {
    const key = m.key;
    const rec = m.rec || m.options[0] || null;
    const cur = m.options.find(o => String(o[key]) === String(chosenId)) || rec;
    const changed = !!(cur && rec && cur !== rec);
    const others = m.options.filter(o => o !== cur);
    const pick = o => opt.pending && m.usable ? `<label class="ap-switch"><input type="radio" name="hopt" value="${e(o[key])}"> 이 안으로 바꾸기</label>` : '';
    const otherRows = others.map(o => `<li class="ap-lost"><div class="ap-lost-head"><b>${e(o[key])}</b><span class="muted num">${e(scoreText(o))}</span>${pick(o)}</div>${o.reason ? `<p>${e(o.reason)}</p>` : ''}${optionFacts(o, key) ? `<p class="row-wrap">${optionFacts(o, key)}</p>` : ''}</li>`);
    const loserRows = m.losers.map(x => `<li class="ap-lost out"><div class="ap-lost-head"><b>${e(x[key])}</b>${UI.chipText(UI.t('chip.excluded'), 'danger')}</div><p>${e(x.why)}</p></li>`);
    const docs = m.docs.map(d => `<a class="chip tone-neutral sm" href="${e(d.link)}" target="_blank" rel="noopener noreferrer">${e(d.title)}</a>`).join(' ');
    const off = m.problems.length ? `<div class="ap-off" role="alert"><p class="field-error"><b>에이전트 제안이 칸 약속과 다릅니다</b> — 아래에 받은 값을 그대로 보입니다.</p><ul>${m.problems.map(p => `<li>${e(p)}</li>`).join('')}</ul></div>`
      + UI.fold('받은 값 그대로 (JSON)', `<pre class="mono">${e(JSON.stringify(m.raw, null, 2))}</pre>`, { cls: 'small', open: true }) : '';
    const head = cur ? `<div class="ap-head"><span class="ap-kicker">${changed ? '담당자가 바꾼 안' : m.rec ? 'AI 에이전트 추천' : '첫 번째 안 (추천 표시 없음)'}</span>${changed && opt.pending ? `<button type="button" class="btn small ghost" data-ap-back="${e(rec[key])}">추천안으로 되돌리기</button>` : ''}</div>
      <h4 class="ap-title">${e(cur[key])}</h4>${cur.reason ? `<p class="ap-desc">${e(cur.reason)}</p>` : ''}
      <ul class="ap-reasons">${Number.isFinite(cur.score) ? `<li>점수 <b class="num">${e(scoreText(cur))}</b></li>` : ''}${optionFacts(cur, key) ? `<li class="row-wrap">${optionFacts(cur, key)}</li>` : ''}</ul>` : `<p class="muted">고를 안이 없습니다.</p>`;
    const lost = otherRows.length + loserRows.length;
    return `<div class="ap-card ${changed ? 'changed' : ''}">${head}
      ${docs ? `<div class="ap-evidence"><div class="ap-row"><span class="ap-label">근거 자료</span><span class="row-wrap">${docs}</span></div></div>` : ''}
      ${lost ? UI.fold(`다른 안 ${otherRows.length}개 · 빠진 안 ${loserRows.length}개는 왜 졌나`, `<ul class="ap-lost-list">${[...otherRows, ...loserRows].join('')}</ul>`, { cls: 'small' }) : ''}
      ${off}${opt.extra || ''}</div>`;
  }

  window.hydApprove = { html, reasons, sentenceAbout, proposal, proposalHtml };
})();
