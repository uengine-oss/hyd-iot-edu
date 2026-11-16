/* A8 성과 지표 실적 · 역추적 (읽기 전용). window.hydKpi.mount(el)
   학생이 하는 일: 기간을 골라 지표의 달성 여부를 보고, 미달의 원인을 처리 건까지 따라간다.
   데이터: process 서비스 GET /api/kpi · /api/kpi/trace (it/process/procsvc/kpi.py). 이 화면은 아무것도 쓰지 않는다.
   B5 목표값 바꿔 보기(시험 실행): POST /api/kpi/try · /api/kpi/try/trace 에 {지표: 시험 목표}를 보내 달성/미달 · 달성률 · 역추적을
   그 목표로 다시 판정한다. 지식 그래프의 목표값은 그대로이고 "원래대로"는 시험 목표를 비운다.
   상태 이름 · 기간 이름 · 사유 문장은 서버(kpi.py STATUS · PERIODS · DEFINITIONS)가 학생 말로 보낸 것을 그대로 쓴다(화면 사본 없음).
   짜임(디자인기준 5-4 현황 — 본: shadcn/ui dashboard-01 의 SectionCards 와 그 아래 보기): 머리 → 기간 거르기(세그먼트) → 숫자 카드 넷(미달 · 달성 · 판정하지 않음 · 계산할 수 없음)
   → 고른 카드의 지표(관점마다 카드 격자 — 이름 · 값 · 판정 알약, 계산할 수 없는 지표는 까닭 표) → 접기 하나(목표값 바꿔 보기).
   숫자 카드 넷은 요약이면서 보기 고르기다(dashboard-01 의 카드 아래 탭 자리): 누른 카드의 지표만 아래에 보인다. 처음에는 미달이 있으면 미달, 없으면 달성 → 판정하지 않음 → 계산할 수 없음 차례로 고른다.
   지표 카드를 누르면 옆 판(4-19)에 그 지표의 계산 근거가, 미달 카드의 「원인 찾기」를 누르면 같은 옆 판의 「미달 원인」 보기에 영향 경로와 같은 기간의 처리 건이 열린다(처리 건에서 보기 → 처리 건 화면). */
(function () {
  const TONE = { met: 'success', missed: 'danger', partial: 'warning', error: 'danger' };      // 알약은 판정이 있을 때만(달성 · 미달 · 부분 실적). 목표가 없는 지표는 판정 칸을 비운다
  let STATUS = {};                                     // 서버 summary.labels (첫 응답에서 받는다)
  const ROLE = { lagging: ['후행 지표', '결과를 재는 지표'], leading: ['선행 지표', '결과를 움직이는 지표'] };
  const EFFECT = { '-1': '나쁜 쪽', '0': '경로마다 다름', '1': '좋은 쪽' };
  // 숫자 카드 넷 = 보기 넷: [키, 이름, 그 보기에 드는 상태, 숫자 색, 그 보기가 무엇인지 한 줄(고른 보기의 지표 위에 한 번)]
  const GROUPS = [
    ['missed', '미달', ['missed'], 'danger', ''],
    ['met', '달성', ['met'], 'ok', ''],
    ['open', '판정하지 않음', ['no_target', 'incomparable', 'partial'], '', '목표가 없거나 목표와 단위가 달라 달성 여부를 판정하지 않은 지표입니다. 실적은 계산됩니다.'],
    ['dead', '계산할 수 없음', ['unavailable', 'no_data', 'error'], '', '원천 데이터가 없거나 이 기간에 기록이 없어 실적을 계산하지 못한 지표입니다.'],
  ];
  const groupOf = status => (GROUPS.find(g => g[2].includes(status)) || GROUPS[3])[0];
  const kv = rows => { const r = rows.filter(([, x]) => x != null && x !== ''); return r.length ? `<dl class="kv">${r.map(([k, x]) => `<dt>${esc(k)}</dt><dd>${x}</dd>`).join('')}</dl>` : ''; };
  const escH = esc;                                    // 포털 공용 이스케이프(ui.js)
  const chip = (label, tone = 'neutral') => UI.chipText(label, tone);
  const num = v => v == null || Number.isNaN(Number(v)) ? '–' : Number(v).toLocaleString('ko-KR', { maximumFractionDigits: 2 });
  const when = v => { if (!v) return '–'; const d = new Date(v); return Number.isNaN(d.getTime()) ? String(v) : d.toLocaleString('ko-KR', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }); };
  const name = id => UI.name(id);

  // 지표 계산은 시계열 · 업무 DB · 그래프 · 처리 기록을 함께 읽어 몇 초 걸린다 — 공용 요청 함수에 읽기 제한만 30초로(화면은 「계산하는 중」을 보인다)
  const SLOW = { timeout: 30000 };
  const getJSON = path => getJ(API.process + path, SLOW);
  const postJSON = (path, body) => postJ(API.process + path, body, 'POST', SLOW);
  const trialOn = st => Object.keys(st.applied || {}).length > 0;

  // 지표 단위의 영문 약자(지식 그래프의 값)를 화면 말로: ea → 개, h → 시간. 그 밖의 단위(℃ · % · kWh/일 · 만원/월)는 그대로
  const unitText = unit => String(unit || '').replace(/\bea\b/g, '개').replace(/\/h\b/g, '/시간').replace(/^h$/, '시간');
  const errorsHtml = list => (list || []).map(t => `<div class="alert" role="status">${UI.icon('triangle-alert')}<h2>일부 원천을 읽지 못했습니다</h2><section>${escH(t)}</section></div>`).join('');
  const measures = d => d.perspectives.flatMap(p => p.objectives.flatMap(o => o.measures.map(m => ({ p, o, m }))));

  /* ---------------- 지표 카드 · 계산 근거 ---------------- */
  function table(rows) {
    if (!rows || !rows.length) return '';
    const cols = [...new Set(rows.flatMap(r => Object.keys(r)))];
    return `<div class="table-container"><table class="table"><thead><tr>${cols.map(c => `<th>${escH(c)}</th>`).join('')}</tr></thead><tbody>${
      rows.map(r => `<tr>${cols.map(c => `<td${typeof r[c] === 'number' ? ' class="num"' : ''}>${escH(r[c] == null ? '–' : typeof r[c] === 'number' ? num(r[c]) : r[c])}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  }
  // 계산 근거: 식 · 원천(표 · 열) · 읽은 행 수 · 설비별 값 → 읽은 행 표. 계산할 수 없는 지표는 그 까닭이 식 자리에 온다
  function basis(m) {
    const d = m.definition || {};
    const rows = [];
    if (d.kind === 'calc' || d.kind === 'formula') rows.push(['식', escH(d.formula)]);
    else if (d.kind === 'unavailable') rows.push(['계산할 수 없는 까닭', escH(d.reason)]);
    if (d.sources && d.sources.length) rows.push(['원천', d.sources.map(s => `${escH(s.system)} <code>${escH(s.table)}</code> (${escH(s.columns)})`).join(' · ')]);
    if (m.rows && m.rows.length) rows.push(['읽은 행', m.rows.map(r => `${escH(r.system)} <code>${escH(r.table)}</code> ${num(r.rows)}행`).join(' · ')]);
    if (m.note) rows.push(['참고', escH(m.note)]);
    const per = Object.entries(m.perAsset || {});
    if (per.length) rows.push(['설비별', per.map(([a, v]) => `${escH(a)} ${num(v)}${m.perAssetMet && m.perAssetMet[a] === false ? ' (미달)' : ''}`).join(' · ')]);
    return kv(rows) + table(m.detail);
  }
  const pillOf = m => TONE[m.status] ? chip(STATUS[m.status] || m.status, TONE[m.status]) : '';
  /* 지표 카드 하나(숫자 카드 4-17의 모양 그대로 — UI.statCard 는 맨 카드와 링크 카드만 내므로, 누르면 옆 판을 여는 카드는 같은 클래스로 여기서 낸다):
     이름(누르면 계산 근거 — 카드 전체가 눌린다) · 오른쪽 위 판정 알약(달성 · 미달 · 부분 실적일 때만) · 큰 실적 · 목표와 달성률 한 줄(목표가 있을 때만) · 미달이면 아래 고정 줄에 「원인 찾기」 */
  function measureCard(m) {
    const unit = unitText(m.displayUnit || m.unit);
    const o = m.original;          // B5: 시험 목표가 걸린 지표 — 원래 목표 · 원래 판정을 아래 한 줄에
    const line = o ? `시험 목표 ${num(m.target)} · 원래 ${o.target == null ? '목표 없음' : '목표 ' + num(o.target)} · ${STATUS[o.status] || o.status}`
      : [m.target == null ? '' : `목표 ${num(m.target)} ${unitText(m.unit)}`, m.rate == null ? '' : `달성률 ${num(m.rate)} %`].filter(Boolean).join(' · ');
    const pill = pillOf(m);
    return `<article class="stat kpi-card" data-kpi="${escH(m.id)}" data-status="${escH(m.status)}">` +
      `<button type="button" class="stat-label kpi-name" data-kpi-basis="${escH(m.id)}" aria-haspopup="dialog" title="계산 근거 보기">${escH(m.name)}</button>${pill ? `<span class="stat-pill">${pill}</span>` : ''}` +
      `<span class="stat-value num">${m.value == null ? '–' : num(m.value)}${unit ? `<small>${escH(unit)}</small>` : ''}</span>` +
      (line ? `<span class="stat-note num">${escH(line)}</span>` : '') +
      (m.status === 'missed' ? `<span class="stat-foot"><button type="button" class="go" data-kpi-trace="${escH(m.id)}" aria-haspopup="dialog">원인 찾기</button></span>` : '') + `</article>`;
  }

  /* ---------------- 옆 판: 지표 하나의 계산 근거와(미달이면) 미달 원인 ---------------- */
  function traceHtml(st) {
    const t = st.trace;
    if (!t || t.loading) return hydLive.waitHtml('미달 원인을 찾는 중', { since: t && t.since, hint: '지식 지도에서 이 지표에 영향을 주는 경로를 찾고, 같은 기간의 처리 기록과 맞춰 보는 중입니다.' });
    if (t.error) return UI.errorBlock('미달 원인을 찾지 못했습니다', t.error) + `<footer class="form-foot"><button type="button" class="btn" data-variant="outline" data-size="sm" data-kpi-trace="${escH(t.measure)}">다시 찾기</button></footer>`;
    const d = t.data, m = d.measure;
    const effect = v => EFFECT[String(v)] || '영향 불명';
    const sec = (title, side, body) => `<section class="kpi-sheet-sec"><h3>${title}${side ? `<span class="muted num">${side}</span>` : ''}</h3>${body}</section>`;
    // 결론 먼저: 관련 처리 건이 몇 건인가 → 그 처리 건(처리 건에서 보기) → 설비 → 영향 경로(접기)
    const lead = d.instanceTotal ? `같은 기간의 처리 건 ${num(d.instancesRead)}건 가운데 ${num(d.instanceTotal)}건이 이 지표에 영향을 주는 경로에 걸려 있습니다.`
      : `같은 기간의 처리 건 ${num(d.instancesRead)}건 가운데 이 지표의 영향 경로에 걸린 건이 없습니다.`;
    const insts = d.instances.length ? `<ul class="kpi-lines">${d.instances.map(i => `<li><div><b>${escH(i.asset || '설비 미상')} · ${escH(i.patternName || (String(i.pattern || '').endsWith('_TRIP') ? '보호 정지 경보' : '이상 경보'))}</b>
        <small>${when(i.start)} 시작${i.chosenSkill ? ' · 고른 조치 ' + escH(i.chosenSkillName || name(i.chosenSkill)) : ' · 고른 조치 없음'}${i.causeName ? ' · 원인 ' + escH(i.causeName) : ''}</small>
        <ul class="kpi-why">${i.reasons.map(r => `<li>${escH(r)}</li>`).join('')}</ul></div><a class="go" href="${escH(i.link)}" data-kpi-go>처리 건에서 보기</a></li>`).join('')}</ul>`
      : `<p class="muted">처리 건이 없거나, 경보 · 조치가 이 지표의 경로와 닿지 않았습니다.</p>`;
    const actions = d.actions.length ? `<p class="muted"><b>고른 조치</b> ${d.actions.map(a => `${escH(a.name)} ${a.count}회 (${escH(effect(a.effect))})`).join(' · ')}</p>` : '';
    const assets = d.assets.length ? `<ul class="kpi-lines">${d.assets.map(a => `<li><div><b>${escH(a.asset)}</b> ${a.value == null ? '' : num(a.value) + ' ' + escH(unitText(m.unit))} ${a.met === false ? chip('미달', 'danger') : a.met === true ? chip('달성', 'success') : ''}
        <small>관련 처리 건 ${a.instances}건${a.events.length ? ' · ' + a.events.map(escH).join(' · ') : ''}</small></div></li>`).join('')}</ul>` : '<p class="muted">설비별 값이 없습니다.</p>';
    const effectText = v => v < 0 ? '오르면 지표 악화' : v > 0 ? '오르면 지표 개선' : '경로마다 다름';
    // 경로마다 방향이 다르면(effect 0) 경로 하나하나의 방향을 함께 보인다
    const drivers = d.drivers.map(x => `<li>${escH(x.path)} — ${effectText(x.effect)}${x.condition ? ` <span class="muted">(${escH(x.condition)})</span>` : ''}${
      x.effect === 0 && (x.paths || []).length > 1 ? `<ul class="kpi-why">${x.paths.map(pp => `<li>${escH(pp.path)} — ${effectText(pp.effect)}</li>`).join('')}</ul>` : ''}</li>`).join('');
    const objectives = d.objectives.map(o => `<li><b>${escH(o.name)}</b>${o.supports.length ? ' → ' + o.supports.map(s => escH(s.name)).join(' → ') : ''}</li>`).join('');
    const skills = d.skills.map(s => `<li>${escH(s.name)} — ${escH(effect(s.effect))}${s.harm.length ? ` <span class="muted">나쁜 경로: ${s.harm.map(escH).join(' / ')}</span>` : ''}</li>`).join('');
    return `<p class="kpi-lead">${escH(lead)}</p><p class="muted num">실적 ${num(m.value)} ${escH(unitText(m.displayUnit || m.unit))} · 목표 ${num(m.target)} ${escH(unitText(m.unit))} · ${escH(d.window.label)}</p>${errorsHtml(d.sourceErrors)}` +
      sec('원인 처리 건', d.instances.length ? d.instances.length + '건' : '', insts + actions) + sec('설비', '', assets) +
      UI.fold(`영향 경로<span class="muted num">${d.drivers.length}</span>`, `<ul class="kpi-why">${drivers || '<li>없음</li>'}</ul>`) +
      UI.fold(`이 지표를 움직이는 조치 방법<span class="muted num">${d.skills.length}</span>`, `<ul class="kpi-why">${skills || '<li>없음</li>'}</ul>`) +
      UI.fold(`이 목표가 받치는 목표<span class="muted num">${d.objectives.length}</span>`, `<ul class="kpi-why">${objectives || '<li>없음</li>'}</ul>`);
  }
  function basisHtml(hit) {
    const { o, m } = hit, [roleLabel, roleHelp] = ROLE[m.kpiRole] || ['', ''];
    return kv([['실적', m.value == null ? '–' : `${num(m.value)} ${escH(unitText(m.displayUnit || m.unit))}`], ['목표', m.target == null ? '없음' : `${num(m.target)} ${escH(unitText(m.unit))}`], ['달성률', m.rate == null ? '' : num(m.rate) + ' %'],
        ['지표 종류', roleLabel ? `${escH(roleLabel)} <span class="muted">— ${escH(roleHelp)}</span>` : ''], ['받치는 목표', o.supports.map(x => escH(x.name)).join(' · ')], ['까닭', m.reason ? escH(m.reason) : '']]) +
      `<section class="kpi-sheet-sec"><h3>계산 근거</h3>${basis(m) || '<p class="muted">계산 근거가 기록되지 않았습니다.</p>'}</section>`;
  }
  // 옆 판은 화면 본문(다시 그려지는 자리) 밖에 하나 두고, 여는 동안에는 그 안만 다시 그린다 — 원인을 찾는 동안 판이 닫혔다 다시 열리지 않게
  function paintSheet(st) {
    const dlg = st.sheet, open = st.open;
    const hit = open && st.data ? measures(st.data).find(x => x.m.id === open.id) : null;
    if (!hit) { if (dlg.open) dlg.close(); return; }
    const { p, o, m } = hit, missed = m.status === 'missed';
    const view = missed ? open.view : 'basis';
    dlg.innerHTML = `<header class="sheet-head"><div><h2>${escH(m.name)} ${pillOf(m) || `<span class="muted kpi-sheet-status">${escH(STATUS[m.status] || m.status)}</span>`}</h2><p class="muted">${escH(p.name)} › ${escH(o.name)}</p></div>` +
      `<button type="button" class="btn" data-variant="ghost" data-size="icon" data-kpi-sheet-close aria-label="닫기" data-tooltip="닫기" data-side="left">${UI.icon('x')}</button></header>` +
      (missed ? UI.viewTabs([['trace', '미달 원인'], ['basis', '계산 근거']], view, 'data-kpi-view', { label: '지표 보기' }) : '') +
      `<div class="sheet-body" data-kpi-sheet-view="${view}">${view === 'trace' ? traceHtml(st) : basisHtml(hit)}</div>`;
    if (!dlg.open) dlg.showModal();
  }

  /* ---------------- B5 목표값 바꿔 보기 ---------------- */
  // 시험 목표가 걸려 있으면 화면 위(결론 아래)에 무엇이 바뀌었는지 먼저 말한다
  function trialNotice(st, d) {
    if (!trialOn(st)) return '';
    const changed = (d.trial && d.trial.changed) || [];
    const so = d.summaryOriginal;           // 원래 목표로 본 요약(시험 판정 전)
    return `<div class="alert" role="status">${UI.icon('flask-conical')}<h2>시험 목표 ${Object.keys(st.applied).length}개를 적용해 판정한 결과입니다</h2><section><p>${escH((d.trial && d.trial.note) || '')}</p>` +
      (so ? `<p>원래 목표로는 미달 ${so.missed} · 달성 ${so.met} → 시험 목표로는 미달 ${d.summary.missed} · 달성 ${d.summary.met}</p>` : '') +
      (changed.length ? `<ul class="kpi-why">${changed.map(c => `<li><b>${escH(c.name)}</b> 실적 ${num(c.value)} ${escH(c.unit || '')} — 목표 ${c.before.target == null ? '없음' : num(c.before.target)} → <b>${num(c.after.target)}</b> · ${escH(STATUS[c.before.status] || c.before.status)} → <b>${escH(STATUS[c.after.status] || c.after.status)}</b></li>`).join('')}</ul>`
        : '<p>판정이 바뀐 지표가 없습니다(실적이 없거나 계산 불가인 지표는 목표를 바꿔도 그대로입니다).</p>') +
      `</section><footer><button type="button" class="btn" data-variant="outline" data-size="sm" data-kpi-trial-reset>원래대로</button></footer></div>`;
  }
  function trialPanel(st, all) {
    st.targets = st.targets || {}; st.applied = st.applied || {};
    const rows = all.map(m => `<tr><td>${escH(m.name)}</td><td class="num">${(m.original ? m.original.target : m.target) == null ? '–' : num(m.original ? m.original.target : m.target) + ' ' + escH(unitText(m.unit))}</td>
      <td><input type="number" step="any" class="input" data-kpi-target="${escH(m.id)}" value="${st.targets[m.id] ?? ''}" placeholder="그대로" aria-label="${escH(m.name)} 시험 목표"></td>
      <td>${escH(STATUS[m.status] || m.status)}</td></tr>`).join('');
    // 접기: 실적을 보러 온 사람에게는 보조 도구다. 한 번 쓰면(시험 목표를 넣거나 판정하면) 펴 둔다
    return `<details class="fold kpi-trial" data-kpi-trial-fold${st.trialOpen || trialOn(st) ? ' open' : ''}><summary>목표값 바꿔 보기</summary><div class="fold-body">
      <p class="muted">시험 목표로 달성 · 미달을 다시 판정합니다. 비운 칸은 원래 목표 그대로이고, 원본 목표는 바뀌지 않습니다.</p>
      <div class="table-container"><table class="table"><thead><tr><th>지표</th><th class="num">원래 목표</th><th>시험 목표</th><th>지금 판정</th></tr></thead><tbody>${rows}</tbody></table></div>
      ${st.trialError ? UI.errorBlock('시험 판정을 하지 못했습니다', st.trialError) : ''}
      <footer class="form-foot">${trialOn(st) ? '<button type="button" class="btn" data-variant="ghost" data-kpi-trial-reset>원래대로</button>' : ''}<button type="button" class="btn" data-variant="outline" data-kpi-trial-run>시험 판정</button></footer></div></details>`;
  }

  /* ---------------- 화면 ---------------- */
  // 숫자 카드(4-17)를 보기 고르기로: UI.statCard 의 마크업을 단추로 바꿔 쓴다(고른 카드는 aria-pressed)
  const statButton = (key, on, o) => UI.statCard({ ...o, attrs: `data-kpi-group="${key}" aria-pressed="${on}"` }).replace(/^<div/, '<button type="button"').replace(/<\/div>$/, '</button>');
  function render(st) {
    const el = st.el;
    const periods = Object.entries((st.data && st.data.periods) || st.periods || {});
    const win = st.data && st.data.window;
    // 기간 거르기(세그먼트). 그 기간이 언제부터 언제까지인지는 고른 칸의 도움말에 둔다
    const range = win && win.start ? `${when(win.start)} ~ ${when(win.end)}` : '';
    const tools = periods.length ? `<div class="kpi-bar"><div class="seg" role="group" aria-label="기간">${periods.map(([k, l]) => `<button type="button" data-kpi-period="${escH(k)}" aria-pressed="${k === st.period}"${k === st.period && range ? ` title="${escH(range)}"` : ''}>${escH(l)}</button>`).join('')}</div></div>` : '';
    let body;
    if (st.loading && !st.data) body = hydLive.waitHtml('성과 지표 실적을 계산하는 중', { since: st.since, hint: '시계열 · 업무 DB · 처리 기록을 읽어 지표마다 실적을 계산합니다. 서버가 모두 끝낸 뒤 한 번에 줍니다.' });
    else if (st.error) body = UI.errorBlock('성과 지표를 불러오지 못했습니다', st.error, { retry: true });
    else {
      const d = st.data, s = d.summary;
      STATUS = s.labels;
      const all = measures(d);
      const count = Object.fromEntries(GROUPS.map(([k]) => [k, all.filter(x => groupOf(x.m.status) === k).length]));
      // 처음 고르는 보기: 미달이 있으면 미달(이 화면의 일은 미달의 원인을 따라가는 것이다), 없으면 지표가 있는 첫 보기
      if (!st.group || (st.groupAuto && !count[st.group])) { st.group = (GROUPS.find(([k]) => count[k]) || GROUPS[0])[0]; st.groupAuto = true; }
      const head = `<div class="stats kpi-stats" role="group" aria-label="판정 요약 — 누르면 그 지표가 아래에 보입니다">` +
        GROUPS.map(([k, label, , tone]) => statButton(k, k === st.group, { label, value: String(count[k]), unit: '개', tone: count[k] ? tone : '' })).join('') + '</div>';
      const [gKey, gLabel, , , gSays] = GROUPS.find(g => g[0] === st.group);
      const shown = all.filter(x => groupOf(x.m.status) === gKey);
      let list;
      if (!shown.length) list = UI.empty({ title: `이 기간에 「${gLabel}」인 지표가 없습니다`, sub: '위의 다른 카드를 누르거나 기간을 바꿔 보세요.' });
      else if (gKey === 'dead')      // 실적이 없는 지표는 카드(큰 숫자)가 아니라 까닭 표로 — 「–」가 화면을 채우지 않게. 줄을 누르면 그 지표의 계산 정의가 옆 판에 열린다
        list = `<div class="table-container"><table class="table kpi-dead"><thead><tr><th>지표</th><th>관점</th><th>상태</th><th>까닭</th></tr></thead><tbody>${shown.map(({ p, m }) =>
          `<tr data-kpi="${escH(m.id)}"><td><button type="button" class="btn" data-variant="link" data-kpi-basis="${escH(m.id)}" aria-haspopup="dialog">${escH(m.name)}</button></td><td>${escH(p.name)}</td><td>${m.status === 'error' ? chip(STATUS[m.status] || m.status, 'danger') : escH(STATUS[m.status] || m.status)}</td><td>${escH(m.reason || (m.definition || {}).reason || '')}</td></tr>`).join('')}</tbody></table></div>`;
      else list = d.perspectives.map(p => {
        const cards = shown.filter(x => x.p === p).map(x => measureCard(x.m));
        return cards.length ? `<section class="kpi-persp" aria-label="${escH(p.name)}"><div class="sec-head"><h2>${escH(p.name)}</h2><span class="muted num">${cards.length}</span></div><div class="kpi-grid">${cards.join('')}</div></section>` : '';
      }).join('');
      body = head + errorsHtml(d.sourceErrors) + trialNotice(st, d) + `<div class="kpi-list" data-kpi-list="${gKey}" aria-live="polite">${list}${shown.length && gSays ? UI.scope(gSays) : ''}</div>` +
        `<div class="kpi-folds">${trialPanel(st, all.map(x => x.m))}</div>`;
    }
    // 화면 머리는 한 번만 그린다 — 읽는 동안 연 「…」 메뉴가 결과가 올 때 다시 그려져 닫히지 않게. 그 아래(기간 거르기와 본문)만 다시 그린다
    if (!el.querySelector(':scope > [data-kpi-body]')) el.innerHTML = UI.pageHead('kpi', { sub: '기간을 골라 지표의 달성 여부를 보고, 미달의 원인을 처리 건까지 따라갑니다.', more: [{ act: 'reload', attrs: 'data-kpi-reload' }] }) + '<div data-kpi-body></div>';
    el.querySelector(':scope > [data-kpi-body]').innerHTML = tools + body;
    paintSheet(st);
  }

  async function load(st) {
    st.loading = true; st.since = new Date().toISOString(); st.error = null; render(st);
    try {
      st.data = trialOn(st) ? await postJSON('/api/kpi/try', { period: st.period, targets: st.applied })
        : await getJSON(`/api/kpi?period=${encodeURIComponent(st.period)}`);
      st.periods = st.data.periods;
      if (trialOn(st)) st.trialError = null;
    } catch (e) {
      if (trialOn(st)) { st.trialError = '시험 판정을 하지 못했습니다: ' + (e.message || String(e)); st.applied = {}; st.loading = false; return load(st); }
      if (e.status === 400 && st.period !== '24h') {      // 저장해 둔 기간을 서버가 모른다 — 기본 기간으로 바꾸고 그 사실을 알린다(말없이 바꾸지 않는다)
        st.period = '24h'; try { localStorage.removeItem('hydKpi.period'); } catch (x) { /* 저장소가 없는 브라우저 — 지울 것이 없다 */ }
        UI.toast('저장해 둔 기간을 서버가 알지 못해 기본 기간(24시간)으로 바꿨습니다.', { tone: 'neutral', timeout: 8000 });
        st.loading = false; return load(st);
      }
      st.error = e.message || String(e); st.data = null;
    }
    st.loading = false; render(st);
    if (st.open && st.open.view === 'trace' && st.data && st.sheet.open) openTrace(st, st.open.id);      // 기간 · 시험 목표가 바뀌었으면 열려 있는 원인 찾기도 그 조건으로 다시
  }

  // 미달 원인 찾기: 옆 판의 「미달 원인」 보기를 열고, 영향 경로와 같은 기간의 처리 건을 읽는다(읽는 동안 그 자리에 무엇을 하는 중인지와 걸린 시간)
  async function openTrace(st, measure) {
    st.open = { id: measure, view: 'trace' };
    st.trace = { measure, loading: true, since: new Date().toISOString() };
    paintSheet(st);
    try {
      const data = trialOn(st) ? await postJSON('/api/kpi/try/trace', { measure, period: st.period, targets: st.applied })
        : await getJSON(`/api/kpi/trace?measure=${encodeURIComponent(measure)}&period=${encodeURIComponent(st.period)}`);
      if (!st.trace || st.trace.measure !== measure) return;      // 그 사이 다른 지표를 열었다
      st.trace = { measure, data };
    }
    catch (e) { if (!st.trace || st.trace.measure !== measure) return; st.trace = { measure, error: e.message || String(e) }; }
    if (st.open && st.open.id === measure) paintSheet(st);
  }

  function mount(el) {
    if (!el) return null;
    if (el._hydKpi) { load(el._hydKpi); return el._hydKpi; }
    const st = { el, period: '24h', data: null, trace: null, open: null, group: '', groupAuto: true, loading: false, error: null, targets: {}, applied: {}, trialOpen: false, trialError: null };
    try { st.period = localStorage.getItem('hydKpi.period') || '24h'; } catch (e) { /* 저장소가 없으면 기본 기간 */ }
    // 저장된 기간이 서버가 모르는 이름이면 서버가 400 으로 사유를 낸다 — 그 경우 기본 기간으로 다시 읽는다(아래 load)
    el._hydKpi = st;
    // 옆 판(4-19): 화면 구역 안, 다시 그려지는 자리(el) 밖에 하나
    const dlg = st.sheet = document.createElement('dialog');
    dlg.className = 'sheet'; dlg.setAttribute('data-wide', ''); dlg.setAttribute('data-kpi-sheet', ''); dlg.setAttribute('aria-label', '지표 자세히');
    el.after(dlg);
    dlg.addEventListener('close', () => { st.open = null; st.trace = null; });
    dlg.addEventListener('click', e => {
      if (e.target === dlg || e.target.closest('[data-kpi-sheet-close]') || e.target.closest('[data-kpi-go]')) { dlg.close(); return; }      // 바깥 · 닫기 · 처리 건으로 가는 링크
      const v = e.target.closest('[data-kpi-view]');
      if (v) { if (v.dataset.kpiView === 'trace' && !(st.trace && st.trace.measure === st.open.id)) openTrace(st, st.open.id); else { st.open.view = v.dataset.kpiView; paintSheet(st); } return; }
      const t = e.target.closest('[data-kpi-trace]');
      if (t) openTrace(st, t.dataset.kpiTrace);
    });
    el.addEventListener('click', e => {
      const p = e.target.closest('[data-kpi-period]');
      if (p) { st.period = p.dataset.kpiPeriod; try { localStorage.setItem('hydKpi.period', st.period); } catch (x) { /* 무시 */ } load(st); return; }
      if (e.target.closest('[data-kpi-reload]') || e.target.closest('[data-retry]')) { load(st); return; }
      const g = e.target.closest('[data-kpi-group]');
      if (g) { st.group = g.dataset.kpiGroup; st.groupAuto = false; render(st); return; }
      const t = e.target.closest('[data-kpi-trace]');
      if (t) { openTrace(st, t.dataset.kpiTrace); return; }
      const b = e.target.closest('[data-kpi-basis]');
      if (b) { st.open = { id: b.dataset.kpiBasis, view: 'basis' }; paintSheet(st); return; }
      if (e.target.closest('[data-kpi-trial-run]')) {
        st.trialOpen = true; st.applied = {};
        for (const [k, v] of Object.entries(st.targets)) if (v !== '' && v != null) st.applied[k] = Number(v);
        load(st); return;
      }
      if (e.target.closest('[data-kpi-trial-reset]')) { st.targets = {}; st.applied = {}; st.trialError = null; load(st); }
    });
    el.addEventListener('toggle', e => { if (e.target.matches && e.target.matches('[data-kpi-trial-fold]')) st.trialOpen = e.target.open; }, true);
    el.addEventListener('change', e => {
      const t = e.target.closest('[data-kpi-target]');
      if (t) { st.trialOpen = true; if (t.value === '') delete st.targets[t.dataset.kpiTarget]; else st.targets[t.dataset.kpiTarget] = t.value; }
    });
    load(st);
    return st;
  }

  // 셸이 처음 열 때 mount, 다시 열 때마다 show(같은 기간으로 다시 계산)
  window.hydKpi = { mount, show: mount };
})();
