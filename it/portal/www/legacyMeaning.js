/* A9 옛 DB 뜻 복원 — 지식 관리 › 업무 데이터 연결 안의 접기 섹션.
   흐름: DDL 미리보기 → "AI에게 뜻 후보 묻기"(에이전트 작업 한 건) → 열마다 후보 · 근거 · 확신도 → 사람이 승인 · 고치기 · 거부
   → 검토 저장(감사 기록) → 미리보기에 그 검토만 반영 → 기존 "적재". AI 후보는 승인 전에는 미리보기 · 그래프 어디에도 들어가지 않는다.
   hitl.js 의 DDL 미리보기가 window.hydLegacy.mount(el, ctx)로 부른다. ctx = {preview, text, by(), replan(reviewId|null)}. */
(function () {
  const API_BASE = () => API.process + '/api/kg/ddl/meanings';
  const S = { key: null, run: null, data: null, error: null, timer: null, drafts: {}, saved: null, busy: false };
  const EV = { name: '이름 패턴', comment: '주석', sample: '샘플 값 분포', key: '키 관계' };
  const VERDICT = { APPROVE: '승인', EDIT: '고치기', REJECT: '거부' };
  const VTONE = { APPROVE: 'success', EDIT: 'accent', REJECT: 'danger' };
  let el = null, ctx = null;

  const keyOf = c => `${c.preview.filename}|${c.text.length}|${c.text.slice(0, 200)}`;
  const short = k => k.split('.').slice(1).join('.');                       // public.T_EQP01.C_PRS_A → T_EQP01.C_PRS_A
  const targets = () => {
    const o = (S.data && S.data.ontology) || {};
    const m = {};
    [...(o.stateVariables || []), ...(o.measures || [])].forEach(v => { m[v.id] = v; });
    return m;
  };
  const linkText = link => {
    if (!link || link.kind === 'none') return '<span class="muted">연결 없음</span>';
    if (link.kind === 'asset_key') return '설비 식별 열';
    const t = link.name ? link : targets()[link.target];
    return t ? `${esc(t.name)}${t.unit ? ' · ' + esc(t.unit) : ''}` : '<span class="neg">목록에 없는 대상</span>';
  };
  const pct = v => Math.round((v || 0) * 100) + '%';

  function stop() { if (S.timer) { clearInterval(S.timer); S.timer = null; } }

  async function load() {
    if (!S.run) return;
    try { S.data = await getJ(API_BASE() + '/' + encodeURIComponent(S.run)); S.error = null; }
    catch (e) { S.error = '후보를 읽지 못했습니다: ' + e.message; }
    if (!S.data || ['DONE', 'FAILED', 'CANCELLED'].includes(S.data.status) || !document.body.contains(el)) stop();
    render();
  }

  function poll() { stop(); S.timer = setInterval(load, 3000); load(); }

  async function ask() {
    if (S.busy) return; S.busy = true; S.error = null; render();
    try {
      const p = ctx.preview;
      const out = await postJ(API_BASE(), { filename: p.filename, text: ctx.text, datasource: p.datasource, catalog: p.catalog, by: ctx.by(), request_id: window.crypto && crypto.randomUUID ? crypto.randomUUID() : undefined });
      S.run = out.instance; S.data = null; S.drafts = {}; S.saved = null; poll();
    } catch (e) { S.error = e.message; }
    finally { S.busy = false; render(); }
  }

  function decisions() {
    return Object.entries(S.drafts).filter(([, d]) => d.verdict).map(([column, d]) => {
      const out = { column, verdict: d.verdict, note: d.note || '' };
      if (d.verdict === 'EDIT') {
        out.meaning = d.meaning || ''; out.unit = d.unit || null;
        out.link = d.link === 'asset_key' ? { kind: 'asset_key', target: null } : d.link && d.link !== 'none' ? { kind: 'represents', target: d.link } : { kind: 'none', target: null };
      }
      return out;
    });
  }

  async function save() {
    const list = decisions();
    if (!list.length) { S.error = '승인 · 고치기 · 거부 중 하나라도 고른 뒤 저장하세요'; render(); return; }
    if (S.busy) return; S.busy = true; S.error = null; render();
    try {
      S.saved = await postJ(API_BASE() + '/' + encodeURIComponent(S.run) + '/reviews', { by: ctx.by(), decisions: list });
      await ctx.replan(S.saved.id);                                          // the preview now carries only this review's approvals
      await load();
    } catch (e) { S.error = '검토 저장 실패: ' + e.message; }
    finally { S.busy = false; render(); }
  }

  /* ---------- 그리기 */
  function evidenceHtml(c) {
    if (!c.evidence.length) return `<span class="muted">${esc(c.reason || '근거 없음')}</span>`;
    return c.evidence.map(e => `<div class="kv-line"><b>${esc(EV[e.kind] || e.kind)}</b> ${esc(e.text)}</div>`).join('');
  }

  function observationHtml(col) {
    if (!col) return '';
    const s = col.samples, k = col.keys || {};
    const rows = [
      ['이름 조각', esc((col.name.tokens || []).join(' · '))],
      ['형', esc(col.type) + (col.nullable ? '' : ' · 비어 있지 않음')],
      ['샘플', !s ? '덤프에 행 없음' : s.nulls === s.rows ? `${s.rows}행 모두 비어 있음` :
        `${s.rows}행 · 서로 다른 값 ${s.distinct}` + (s.min != null ? ` · ${esc(s.min)} ~ ${esc(s.max)} (평균 ${esc(s.mean)})` : '')
        + (s.top ? ` · 자주 나온 값 ${s.top.map(([v, n]) => `${esc(v)}(${n})`).join(', ')}` : '')],
      ['키', [k.primaryKey ? '기본 키' : '', k.declared ? '선언된 참조 ' + esc(k.declared) : '',
        (k.sameName || []).length ? '같은 이름 열 ' + k.sameName.map(x => esc(short(x))).join(', ') : '',
        (k.inferred || []).length ? '값이 겹침(추론) ' + k.inferred.map(x => `${esc(short(x.column))} ${pct(x.overlap)}`).join(', ') : ''].filter(Boolean).join(' · ') || '없음'],
    ];
    if (col.assetTags) rows.push(['설비 태그와 겹침', `${col.assetTags.matched} / ${col.assetTags.of}`]);
    return `<dl class="meta-list">${rows.map(([a, b]) => `<div><dt>${a}</dt><dd>${b}</dd></div>`).join('')}</dl>`;
  }

  function decisionHtml(c) {
    const d = S.drafts[c.column] || {};
    const opts = ['', 'APPROVE', 'EDIT', 'REJECT'].filter(v => v !== 'APPROVE' || c.status === 'proposed')
      .map(v => `<option value="${v}" ${d.verdict === v ? 'selected' : ''}>${v ? VERDICT[v] : '보류'}</option>`).join('');
    let edit = '';
    if (d.verdict === 'EDIT') {
      const t = targets();
      const linkOpts = [['none', '연결 없음'], ['asset_key', '설비 식별 열'], ...Object.values(t).map(v => [v.id, v.name + (v.unit ? ' · ' + v.unit : '')])]
        .map(([v, l]) => `<option value="${esc(v)}" ${(d.link || 'none') === v ? 'selected' : ''}>${esc(l)}</option>`).join('');
      edit = `<div class="form-grid">${UI.field({ label: '뜻', input: `<input data-edit="meaning" data-col="${esc(c.column)}" value="${esc(d.meaning || '')}">` })}
        ${UI.field({ label: '단위', input: `<input data-edit="unit" data-col="${esc(c.column)}" value="${esc(d.unit || '')}">` })}
        ${UI.field({ label: '온톨로지 연결', input: `<select data-edit="link" data-col="${esc(c.column)}">${linkOpts}</select>` })}</div>`;
    }
    const note = d.verdict === 'REJECT' || d.verdict === 'EDIT' ? `<input data-edit="note" data-col="${esc(c.column)}" placeholder="이유(선택)" value="${esc(d.note || '')}">` : '';
    return `<select data-verdict="${esc(c.column)}" aria-label="${esc(short(c.column))} 결정">${opts}</select>${note}${edit}`;
  }

  function candidatesHtml() {
    const data = S.data, cols = {};
    (data.columns || []).forEach(c => { cols[c.key] = c; });
    const head = `<thead><tr><th>열</th><th>AI 뜻 후보</th><th>연결</th><th>확신도</th><th>근거</th><th>결정</th></tr></thead>`;
    const row = c => `<tr>
        <td><b>${esc(short(c.column))}</b>${UI.fold('관찰', observationHtml(cols[c.column]), { cls: 'small' })}</td>
        <td>${c.status === 'proposed' ? `${esc(c.meaning)}${c.unit ? ` <span class="muted">(${esc(c.unit)})</span>` : ''}${c.alternatives.length ? `<div class="muted">다른 해석: ${c.alternatives.map(esc).join(', ')}</div>` : ''}` : UI.chipText('근거 없음', 'warning')}</td>
        <td>${linkText(c.link)}</td><td>${pct(c.confidence)}</td><td>${evidenceHtml(c)}</td><td>${decisionHtml(c)}</td></tr>`;
    const proposed = data.candidates.filter(c => c.status === 'proposed').sort((a, b) => b.confidence - a.confidence);
    const blank = data.candidates.filter(c => c.status !== 'proposed');
    const table = list => `<div class="table-scroll"><table class="prov">${head}<tbody>${list.map(row).join('')}</tbody></table></div>`;
    const chosen = decisions();
    const counts = ['APPROVE', 'EDIT', 'REJECT'].map(v => `${VERDICT[v]} ${chosen.filter(d => d.verdict === v).length}`).join(' · ');
    return `${data.summary ? `<p class="kv-line"><b>AI 요약</b> ${esc(data.summary)}</p>` : ''}
      ${proposed.length ? table(proposed) : UI.empty('AI가 뜻을 제안한 열이 없습니다', '모두 근거 없음으로 냈습니다 — 아래에서 직접 고치거나 거부할 수 있습니다')}
      ${blank.length ? UI.fold(`AI가 근거 없음으로 낸 열 <span class="chip tone-warning sm">${blank.length}</span>`, table(blank), { cls: 'small', open: blank.some(c => S.drafts[c.column] && S.drafts[c.column].verdict) }) : ''}
      ${UI.actions(`<button class="btn primary" id="lmSave" ${S.busy ? 'disabled' : ''}>검토 저장 · 미리보기에 반영</button>`, '')}
      <p class="muted">고른 결정: ${counts} · 보류 ${data.candidates.length - chosen.length}. 보류 · 거부한 열은 반영되지 않습니다. AI가 낸 후보는 저장해도 회사 DB에 쓰지 않습니다.</p>`;
  }

  function appliedHtml() {
    const r = ctx.preview.meaningReview;
    if (!r) return '';
    const sql = (r.commentSql || []).join('\n');
    return UI.card({
      title: '미리보기에 반영된 뜻 검토', chips: UI.chipText(`승인 ${r.approved} · 고치기 ${r.edited} · 거부 ${r.rejected}`, 'success'),
      body: `<p class="kv-line"><b>${esc(r.by)}</b> · ${esc(UI.dateTime(r.createdAt))} · 반영한 입력 ${r.applied.length}개</p>
        ${r.reflected.map(x => `<div class="kv-line"><b>${esc(short(x.column))}</b> → ${esc(x.comment)} · ${linkText(x.link)}</div>`).join('')}
        ${sql ? UI.fold('DB 담당자에게 줄 열 주석 SQL (실행하지 않음)', `<pre>${esc(sql)}</pre>`, { cls: 'small' }) : ''}`,
      actions: `<button class="btn small" id="lmUnapply">검토 빼고 미리보기 (원래대로)</button>`,
    });
  }

  function historyHtml() {
    const list = (S.data && S.data.reviews) || [];
    if (!list.length) return '';
    const cur = ctx.preview.meaningReview && ctx.preview.meaningReview.id;
    return UI.fold(`이 후보에 대한 검토 기록 <span class="chip tone-neutral sm">${list.length}</span>`, list.map(r => `<div class="kv-line">
        <b>${esc(r.by)}</b> · ${esc(UI.dateTime(r.createdAt))} · 승인 ${r.approved} · 고치기 ${r.edited} · 거부 ${r.rejected}
        ${r.id === cur ? UI.chipText('지금 반영 중', 'success') : `<button class="btn small" data-use-review="${esc(r.id)}">이 검토로 미리보기</button>`}
        ${UI.fold('결정', r.decisions.map(d => `<div>${esc(short(d.column))} ${UI.chipText(VERDICT[d.verdict], VTONE[d.verdict])} ${d.after ? esc(d.after.meaning) : ''}${d.note ? ` <span class="muted">— ${esc(d.note)}</span>` : ''}</div>`).join(''), { cls: 'small' })}</div>`).join(''), { cls: 'small' });
  }

  function statusHtml() {
    const d = S.data;
    if (!d) return `<p class="muted" role="status"><span class="live-dot on"></span> 작업을 여는 중…</p>`;
    const working = !['DONE', 'FAILED', 'CANCELLED'].includes(d.status);
    const corr = d.corrections ? ` · 근거 검사에서 되돌려 보냄 ${d.corrections.attempts}회${d.corrections.reasons && d.corrections.reasons.length ? ` (마지막 사유: ${esc(d.corrections.reasons[d.corrections.reasons.length - 1])})` : ''}` : '';
    return `<p class="kv-line" role="status">${working ? '<span class="live-dot on"></span> ' : ''}<b>AI 뜻 후보 작업</b> ${UI.chip(d.status)} · 열 ${d.columns.length}개${corr}
      ${working ? '<span class="muted"> — AI 일꾼이 관찰 결과만 보고 후보를 쓰는 중입니다.</span>' : ''}</p>`;
  }

  function render() {
    if (!el || !ctx) return;
    const L = ctx.preview.legacy || {};
    const sampleRows = Object.values(L.samples || {}).reduce((a, b) => a + b, 0);
    const done = S.data && S.data.candidates;
    const sumLine = `뜻이 없는 열 ${L.targets || 0}개 · 덤프 샘플 행 ${sampleRows}개`
      + (S.data ? ` · AI 후보 ${done ? S.data.candidates.length + '건' : UI.status(S.data.status)}` : '')
      + (ctx.preview.meaningReview ? ' · 검토 반영 중' : '');
    let body = '';
    if (L.error) body += `<p class="neg">샘플 행을 읽지 못했습니다: ${esc(L.error)}</p>`;
    body += appliedHtml();
    if (!L.targets) body += UI.empty('뜻을 복원할 열이 없습니다', '모든 열에 주석(업무 뜻)이 있습니다');
    else if (!S.run) body += UI.card({
      title: '코드 이름 열의 뜻 후보 받기',
      body: `<p class="muted">열 이름 조각 · 샘플 값 분포 · 키 관계를 관찰해 AI 일꾼에게 넘깁니다. 후보는 사람이 승인한 것만 미리보기와 적재에 들어갑니다.</p>
        ${(L.notes || []).map(n => `<p class="muted">${esc(n)}</p>`).join('')}`,
      actions: `<button class="btn primary" id="lmAsk" ${S.busy ? 'disabled' : ''}>AI에게 뜻 후보 묻기</button>`,
    });
    else {
      body += statusHtml();
      if (done) body += candidatesHtml();
      body += historyHtml();
      if (done || (S.data && ['FAILED', 'CANCELLED'].includes(S.data.status))) body += `<p><button class="btn small" id="lmAgain">후보 다시 받기</button></p>`;
    }
    if (S.error) body += `<p class="neg" role="alert">${esc(S.error)}</p>`;
    el.innerHTML = UI.fold(`옛 DB 뜻 복원 <span class="chip tone-neutral sm">${esc(sumLine)}</span>`, body, { open: !!(S.run || ctx.preview.meaningReview) });
    wire();
  }

  function wire() {
    const on = (sel, fn) => { const b = el.querySelector(sel); if (b) b.addEventListener('click', fn); };
    on('#lmAsk', ask);
    on('#lmAgain', () => { S.run = null; S.data = null; S.drafts = {}; ask(); });
    on('#lmSave', save);
    on('#lmUnapply', async () => { try { await ctx.replan(null); } catch (e) { S.error = e.message; render(); } });
    el.querySelectorAll('[data-use-review]').forEach(b => b.addEventListener('click', async () => {
      try { await ctx.replan(b.dataset.useReview); } catch (e) { S.error = e.message; render(); }
    }));
    el.querySelectorAll('[data-verdict]').forEach(s => s.addEventListener('change', () => {
      const col = s.dataset.verdict, c = S.data.candidates.find(x => x.column === col);
      const d = S.drafts[col] = Object.assign(S.drafts[col] || {}, { verdict: s.value });
      if (s.value === 'EDIT' && d.meaning == null) {                       // start the edit from the AI's words
        d.meaning = c.meaning || ''; d.unit = c.unit || '';
        d.link = c.link.kind === 'represents' ? c.link.target : c.link.kind;
      }
      render();
    }));
    el.querySelectorAll('[data-edit]').forEach(i => i.addEventListener('change', () => {
      (S.drafts[i.dataset.col] = S.drafts[i.dataset.col] || {})[i.dataset.edit] = i.value;
    }));
  }

  window.hydLegacy = {
    mount(target, context) {
      el = target; ctx = context;
      const key = keyOf(context);
      if (S.key !== key) { stop(); Object.assign(S, { key, run: null, data: null, error: null, drafts: {}, saved: null, busy: false }); }
      const applied = context.preview.meaningReview;
      if (!S.run && applied && applied.instance) { S.run = applied.instance; load(); }     // a reviewed preview reopens its candidates
      render();
    },
  };
})();
