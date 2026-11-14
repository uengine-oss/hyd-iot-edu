/* A8 성과 지표 실적 · 역추적 (읽기 전용). window.hydKpi.mount(el)
   관점(재무 → 고객 → 내부 프로세스 → 학습과 성장) → 목표 → 지표 카드. 지표마다 실적 · 목표 · 달성률과 계산 근거(원천 표 · 열 · 식 · 행 수)를,
   원천이 없는 지표는 "계산 불가 — 사유"를 보여 준다. 미달 카드의 "원인 찾기" → 영향 경로와 같은 기간 처리 건 · 조치 · 설비.
   데이터: process 서비스 GET /api/kpi · /api/kpi/trace (it/process/procsvc/kpi.py). 이 화면은 아무것도 쓰지 않는다.
   B5 목표값 바꿔 보기(시험 실행): POST /api/kpi/try · /api/kpi/try/trace 에 {지표: 시험 목표}를 보내 달성/미달 · 달성률 · 역추적을
   그 목표로 다시 판정한다. 지식 그래프의 목표값은 그대로이고 "원래대로"는 시험 목표를 비운다.
   상태 이름 · 기간 이름 · 사유 문장은 서버(kpi.py STATUS · PERIODS · DEFINITIONS)가 학생 말로 보낸 것을 그대로 쓴다(화면 사본 없음).
   짜임(결론 먼저 · 근거 다음 · 원문 접기): 제목 · 한 문장 · 기간 고르기 → 결론(지표 몇 개 가운데 미달 · 달성 몇 개) → (연 것이 있으면) 미달 원인 찾기 →
   관점마다 판 하나(목표별 지표 표: 지표 · 실적 · 목표 · 달성률 · 판정) → 접기 둘(목표값 바꿔 보기 · 계산 정의 표). 계산 근거는 그 지표의 [계산 근거]를 눌렀을 때 줄 아래에 열린다. */
(function () {
  const TONE = { met: 'success', missed: 'danger', no_target: 'neutral', incomparable: 'neutral', partial: 'warning', no_data: 'neutral', unavailable: 'neutral', error: 'danger' };
  let STATUS = {};                                     // 서버 summary.labels (첫 응답에서 받는다)
  const ROLE = { lagging: ['후행 지표', '결과를 재는 지표'], leading: ['선행 지표', '결과를 움직이는 지표'] };
  const EFFECT = { '-1': '나쁜 쪽', '0': '경로마다 다름', '1': '좋은 쪽' };
  const group = (label, body) => body ? `<div class="panel-sec"><h3>${label}</h3>${body}</div>` : '';
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

  const unitText = unit => unit === 'ea' ? '개' : unit || '';
  const errorsHtml = list => (list || []).map(t => `<div class="alert" role="status">${UI.icon('triangle-alert')}<h2>일부 원천을 읽지 못했습니다</h2><section>${escH(t)}</section></div>`).join('');

  /* ---------------- 지표 한 줄 ---------------- */
  function table(rows) {
    if (!rows || !rows.length) return '';
    const cols = [...new Set(rows.flatMap(r => Object.keys(r)))];
    return `<div class="table-container"><table class="table"><thead><tr>${cols.map(c => `<th>${escH(c)}</th>`).join('')}</tr></thead><tbody>${
      rows.map(r => `<tr>${cols.map(c => `<td${typeof r[c] === 'number' ? ' class="num"' : ''}>${escH(r[c] == null ? '–' : typeof r[c] === 'number' ? num(r[c]) : r[c])}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  }
  // 계산 근거: 식 · 원천(표 · 열) · 읽은 행 수 · 설비별 값 → 읽은 행 표
  function basis(m) {
    const d = m.definition || {};
    const rows = [];
    if (d.kind === 'calc' || d.kind === 'formula') {
      rows.push(['식', escH(d.formula)]);
      if (d.sources) rows.push(['원천', d.sources.map(s => `${escH(s.system)} <code>${escH(s.table)}</code> (${escH(s.columns)})`).join(' · ')]);
    }
    if (m.rows && m.rows.length) rows.push(['읽은 행', m.rows.map(r => `${escH(r.system)} <code>${escH(r.table)}</code> ${num(r.rows)}행`).join(' · ')]);
    if (m.note) rows.push(['참고', escH(m.note)]);
    const per = Object.entries(m.perAsset || {});
    if (per.length) rows.push(['설비별', per.map(([a, v]) => `${escH(a)} ${num(v)}${m.perAssetMet && m.perAssetMet[a] === false ? ' (미달)' : ''}`).join(' · ')]);
    return kv(rows) + table(m.detail);
  }
  function measureRow(st, m) {
    const [roleLabel, roleHelp] = ROLE[m.kpiRole] || ['', ''];
    const unit = escH(unitText(m.displayUnit || m.unit));
    const o = m.original;          // B5: 시험 목표가 걸린 지표 — 원래 목표 · 원래 판정을 그 줄의 둘째 줄에
    const trial = o ? `<small>시험 목표 적용 중 — 원래 목표 ${o.target == null ? '없음' : num(o.target) + ' ' + escH(unitText(m.unit))} · 원래 판정 ${escH(STATUS[o.status] || o.status)}${o.rate == null ? '' : ` (달성률 ${num(o.rate)} %)`}</small>` : '';
    const open = st.openMeasure === m.id, hasBasis = m.status !== 'unavailable';
    const actions = (m.status === 'missed' ? `<button type="button" class="btn" data-variant="outline" data-size="sm" data-kpi-trace="${escH(m.id)}">원인 찾기</button>` : '') +
      (hasBasis ? `<button type="button" class="btn" data-variant="ghost" data-size="sm" data-kpi-basis="${escH(m.id)}" aria-expanded="${open}">${open ? '근거 닫기' : '계산 근거'}</button>` : '');
    return `<tr data-kpi="${escH(m.id)}"><td>${escH(m.name)}${roleLabel ? `<small title="${escH(roleHelp)}">${escH(roleLabel)}</small>` : ''}${m.reason ? `<small>${escH(m.reason)}</small>` : ''}${trial}</td>` +
      `<td class="num">${m.value == null ? '–' : `${num(m.value)} ${unit}`}</td><td class="num">${m.target == null ? '–' : `${num(m.target)} ${escH(unitText(m.unit))}`}</td>` +
      `<td class="num">${m.rate == null ? '–' : num(m.rate) + ' %'}</td>` +
      `<td>${m.status === 'missed' || m.status === 'error' ? chip(STATUS[m.status] || m.status, TONE[m.status]) : escH(STATUS[m.status] || m.status)}</td>` +
      `<td>${actions}</td></tr>` +
      (open && hasBasis ? `<tr class="kpi-more"><td colspan="6">${basis(m)}</td></tr>` : '');
  }

  /* ---------------- 역추적 ---------------- */
  function tracePanel(st) {
    const t = st.trace;
    if (!t) return '';
    const head = `<div class="panel-head"><div><h2>${escH(t.title)} — 미달 원인 찾기</h2></div><button type="button" class="btn" data-variant="ghost" data-size="icon-sm" data-kpi-close aria-label="원인 찾기 닫기" data-tooltip="닫기" data-side="left">${UI.icon('x')}</button></div>`;
    const wrap = body => `<section class="panel kpi-trace" id="kpiTrace">${head}${body}</section>`;
    if (t.loading) return wrap(`<div class="panel-body">${hydLive.waitHtml('미달 원인을 찾는 중', { since: t.since, hint: '지식 지도에서 이 지표에 영향을 주는 경로를 찾고, 같은 기간의 처리 기록과 맞춰 보는 중입니다.' })}</div>`);
    if (t.error) return wrap(`<div class="panel-body">${UI.errorBlock('미달 원인을 찾지 못했습니다', t.error)}<footer class="form-foot"><button type="button" class="btn" data-variant="outline" data-size="sm" data-kpi-trace="${escH(t.measure)}">다시 찾기</button></footer></div>`);
    const d = t.data, m = d.measure;
    const effect = v => EFFECT[String(v)] || '영향 불명';
    const summary = `<p class="muted">실적 ${num(m.value)} ${escH(unitText(m.displayUnit || m.unit))} · 목표 ${num(m.target)} ${escH(unitText(m.unit))} · ${escH(d.window.label)} · 처리 건 ${num(d.instancesRead)}건 중 관련 ${num(d.instanceTotal)}건</p>`;
    const insts = d.instances.length ? `<ul class="kpi-lines">${d.instances.map(i => `<li><span><b>${escH(i.asset || '설비 미상')}</b> ${escH(i.patternName || (String(i.pattern || '').endsWith('_TRIP') ? '보호 정지 경보' : '이상 경보'))}
        <small class="muted">${when(i.start)} 시작${i.chosenSkill ? ' · 고른 조치 ' + escH(i.chosenSkillName || name(i.chosenSkill)) : ' · 고른 조치 없음'}${i.causeName ? ' · 원인 ' + escH(i.causeName) : ''}</small>
        <ul class="kpi-why">${i.reasons.map(r => `<li>${escH(r)}</li>`).join('')}</ul></span><a class="btn" data-variant="outline" data-size="sm" href="${escH(i.link)}">처리 건 열기</a></li>`).join('')}</ul>`
      : UI.empty('같은 기간에 이 지표의 영향 경로에 걸린 처리 건이 없습니다', '처리 건이 없거나, 경보 · 조치가 이 지표의 경로와 닿지 않았습니다.');
    const actions = d.actions.length ? `<p class="muted"><b>고른 조치</b> ${d.actions.map(a => `${escH(a.name)} ${a.count}회 (${escH(effect(a.effect))})`).join(' · ')}</p>` : '';
    const assets = d.assets.length ? `<ul class="kpi-lines">${d.assets.map(a => `<li><span><b>${escH(a.asset)}</b> ${a.value == null ? '' : num(a.value) + ' ' + escH(unitText(m.unit))} ${a.met === false ? chip('미달', 'danger') : a.met === true ? '달성' : ''}</span>
        <small>관련 처리 건 ${a.instances}건${a.events.length ? ' · ' + a.events.map(escH).join(' · ') : ''}</small></li>`).join('')}</ul>` : '<p class="muted">설비별 값이 없습니다.</p>';
    const effectText = v => v < 0 ? '오르면 지표 악화' : v > 0 ? '오르면 지표 개선' : '경로마다 다름';
    // 경로마다 방향이 다르면(effect 0) 경로 하나하나의 방향을 함께 보인다
    const drivers = d.drivers.map(x => `<li>${escH(x.path)} — ${effectText(x.effect)}${x.condition ? ` <span class="muted">(${escH(x.condition)})</span>` : ''}${
      x.effect === 0 && (x.paths || []).length > 1 ? `<ul class="kpi-why">${x.paths.map(pp => `<li>${escH(pp.path)} — ${effectText(pp.effect)}</li>`).join('')}</ul>` : ''}</li>`).join('');
    const objectives = d.objectives.map(o => `<li><b>${escH(o.name)}</b>${o.supports.length ? ' → ' + o.supports.map(s => escH(s.name)).join(' → ') : ''}</li>`).join('');
    const skills = d.skills.map(s => `<li>${escH(s.name)} — ${escH(effect(s.effect))}${s.harm.length ? ` <span class="muted">나쁜 경로: ${s.harm.map(escH).join(' / ')}</span>` : ''}</li>`).join('');
    return wrap(`<div class="panel-body">${summary}${errorsHtml(d.sourceErrors)}</div>` +
      group('원인 처리 건', insts + actions) + group('설비', assets) +
      `<div class="panel-sec">${UI.fold(`영향 경로 ${d.drivers.length}개 · 이 지표를 움직이는 조치 방법 · 이 목표가 받치는 목표`,
        `<h4>영향 경로 (지식 그래프의 영향 관계)</h4><ul class="kpi-why">${drivers}</ul><h4>이 지표를 움직이는 조치 방법</h4><ul class="kpi-why">${skills}</ul><h4>이 목표가 받치는 목표</h4><ul class="kpi-why">${objectives}</ul>`)}</div>`);
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
    return `<details class="fold kpi-trial" data-kpi-trial-fold${st.trialOpen || trialOn(st) ? ' open' : ''}><summary>목표값 바꿔 보기 <span class="muted">시험 목표로 달성 · 미달을 다시 판정합니다. 원본 목표는 바꾸지 않습니다</span></summary><div class="fold-body">
      <p class="muted">시험 목표를 넣고 [시험 판정]을 누르면 달성 · 미달과 달성률을 그 목표로 다시 판정합니다. 비운 칸은 지식 그래프의 목표 그대로입니다.</p>
      <div class="table-container"><table class="table"><thead><tr><th>지표</th><th class="num">원래 목표</th><th>시험 목표</th><th>지금 판정</th></tr></thead><tbody>${rows}</tbody></table></div>
      ${st.trialError ? UI.errorBlock('시험 판정을 하지 못했습니다', st.trialError) : ''}
      <footer class="form-foot">${trialOn(st) ? '<button type="button" class="btn" data-variant="ghost" data-kpi-trial-reset>원래대로</button>' : ''}<button type="button" class="btn" data-variant="outline" data-kpi-trial-run>시험 판정</button></footer></div></details>`;
  }

  /* ---------------- 화면 ---------------- */
  function render(st) {
    const el = st.el;
    const periods = Object.entries((st.data && st.data.periods) || st.periods || {});
    const tools = `<div class="page-tools">${periods.length ? `<div class="seg" role="group" aria-label="기간">${periods.map(([k, l]) => `<button type="button" data-kpi-period="${escH(k)}" aria-pressed="${k === st.period}">${escH(l)}</button>`).join('')}</div>` : ''}
      <button type="button" class="btn" data-variant="outline" data-kpi-reload>${UI.icon('refresh-cw')}다시 읽기</button></div>`;
    let body;
    if (st.loading && !st.data) body = hydLive.waitHtml('성과 지표 실적을 계산하는 중', { since: st.since, hint: '시계열 · 업무 DB · 처리 기록을 읽어 지표마다 실적을 계산합니다. 서버가 모두 끝낸 뒤 한 번에 줍니다.' });
    else if (st.error) body = UI.errorBlock('성과 지표를 불러오지 못했습니다', st.error, { retry: true });
    else {
      const d = st.data, s = d.summary;
      STATUS = s.labels;
      const all = d.perspectives.flatMap(p => p.objectives.flatMap(o => o.measures));
      const noVerdict = s.no_target + s.incomparable + s.partial, noCalc = s.unavailable + s.no_data + s.error;
      // 결론 먼저: 지표 몇 개 가운데 미달 · 달성 몇 개. 그 아래에 기간과 판정하지 못한 수
      const head = `<section class="panel kpi-result result"><p class="result-label">결론</p>` +
        `<p class="result-main">지표 ${s.total}개 가운데 ${chip(`미달 ${s.missed}개`, s.missed > 0 ? 'danger' : 'neutral')} ${chip(`달성 ${s.met}개`, s.met > 0 ? 'success' : 'neutral')}</p>` +
        `<p class="result-sub">${escH(d.window.label)}${d.window.start ? ` (${when(d.window.start)} ~ ${when(d.window.end)})` : ''}${s.missed > 0 ? ' · 미달 지표의 [원인 찾기]를 누르면 영향 경로와 같은 기간의 처리 건을 찾습니다' : ''}</p>` +
        kv([['목표 판정 없음', noVerdict ? `${noVerdict}개 <span class="muted">(목표 없음 ${s.no_target} · 단위가 달라 판정 안 함 ${s.incomparable} · 부분 실적 ${s.partial})</span>` : ''],
          ['계산 불가 · 기록 없음', noCalc ? `${noCalc}개 <span class="muted">(원천 없음 ${s.unavailable} · 기록 없음 ${s.no_data} · 조회 실패 ${s.error})</span>` : '']]) + '</section>';
      const persp = d.perspectives.map(p => `<section class="panel kpi-persp"><div class="panel-head"><h2>${escH(p.name)}</h2></div>${p.objectives.map(o =>
        group(`${escH(o.name)}${o.supports.length ? ` <span class="muted">→ 받치는 목표: ${o.supports.map(x => escH(x.name)).join(' · ')}</span>` : ''}`,
          `<div class="table-container"><table class="table kpi-table"><thead><tr><th>지표</th><th class="num">실적</th><th class="num">목표</th><th class="num">달성률</th><th>판정</th><th></th></tr></thead><tbody>${o.measures.map(m => measureRow(st, m)).join('')}</tbody></table></div>`)).join('')}</section>`).join('');
      const defs = `<div class="table-container"><table class="table"><thead><tr><th>지표</th><th class="num">목표</th><th>원천 (표 · 열)</th><th>식 또는 계산 불가 사유</th></tr></thead><tbody>${all.map(m => {
        const df = m.definition || {};
        const src = (df.sources || []).map(x => `${escH(x.system)} <code>${escH(x.table)}</code> ${escH(x.columns)}`).join('<br>') || '–';
        return `<tr><td>${escH(m.name)}</td><td class="num">${m.target == null ? '–' : num(m.target) + ' ' + escH(unitText(m.unit))}</td><td>${src}</td><td>${df.kind === 'unavailable' ? '계산 불가: ' + escH(df.reason) : escH(df.formula)}</td></tr>`;
      }).join('')}</tbody></table></div>`;
      body = head + errorsHtml(d.sourceErrors) + trialNotice(st, d) + tracePanel(st) + persp + trialPanel(st, all) +
        UI.fold(`지표별 계산 정의 표 <span class="muted">${all.length}개 · 원천과 식</span>`, defs);
    }
    el.innerHTML = `<div class="page-head kpi-head"><div><h1>${escH(UI.t('nav.kpi'))}</h1><p>지식 그래프의 관점과 목표마다 지표의 실적 · 목표 · 달성 여부를 보고, 미달 지표의 원인을 처리 건까지 따라갑니다.</p></div>${tools}</div>${body}`;
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
    if (st.trace && st.data) openTrace(st, st.trace.measure);
  }

  async function openTrace(st, measure) {
    const m = st.data && st.data.perspectives.flatMap(p => p.objectives.flatMap(o => o.measures)).find(x => x.id === measure);
    st.trace = { measure, title: m ? m.name : '지표', loading: true, since: new Date().toISOString() };
    render(st);
    const panel = st.el.querySelector('#kpiTrace'); if (panel && panel.scrollIntoView) panel.scrollIntoView({ block: 'nearest' });
    try {
      const data = trialOn(st) ? await postJSON('/api/kpi/try/trace', { measure, period: st.period, targets: st.applied })
        : await getJSON(`/api/kpi/trace?measure=${encodeURIComponent(measure)}&period=${encodeURIComponent(st.period)}`);
      st.trace = { measure, title: st.trace.title, data };
    }
    catch (e) { st.trace = { measure, title: st.trace.title, error: e.message || String(e) }; }
    render(st);
  }

  function mount(el) {
    if (!el) return null;
    if (el._hydKpi) { load(el._hydKpi); return el._hydKpi; }
    const st = { el, period: '24h', data: null, trace: null, loading: false, error: null, targets: {}, applied: {}, trialOpen: false, trialError: null };
    try { st.period = localStorage.getItem('hydKpi.period') || '24h'; } catch (e) { /* 저장소가 없으면 기본 기간 */ }
    // 저장된 기간이 서버가 모르는 이름이면 서버가 400 으로 사유를 낸다 — 그 경우 기본 기간으로 다시 읽는다(아래 load)
    el._hydKpi = st;
    el.addEventListener('click', e => {
      const p = e.target.closest('[data-kpi-period]');
      if (p) { st.period = p.dataset.kpiPeriod; try { localStorage.setItem('hydKpi.period', st.period); } catch (x) { /* 무시 */ } load(st); return; }
      if (e.target.closest('[data-kpi-reload]') || e.target.closest('[data-retry]')) { load(st); return; }
      const t = e.target.closest('[data-kpi-trace]');
      if (t) { openTrace(st, t.dataset.kpiTrace); return; }
      if (e.target.closest('[data-kpi-close]')) { st.trace = null; render(st); return; }
      const b = e.target.closest('[data-kpi-basis]');
      if (b) { st.openMeasure = st.openMeasure === b.dataset.kpiBasis ? null : b.dataset.kpiBasis; render(st); return; }
      if (e.target.closest('[data-kpi-trial-run]')) {
        st.trialOpen = true; st.applied = {};
        for (const [k, v] of Object.entries(st.targets)) if (v !== '' && v != null) st.applied[k] = Number(v);
        st.trace = null; load(st); return;
      }
      if (e.target.closest('[data-kpi-trial-reset]')) { st.targets = {}; st.applied = {}; st.trialError = null; st.trace = null; load(st); }
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
