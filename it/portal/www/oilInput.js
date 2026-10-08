/* B7 오일 분석 결과 입력 — window.hydOilInput.mount(el). 주소 #/oil
   작동유에는 실시간 센서가 없다. 정기 오일 분석 결과(설비 · 분석 항목 · 측정값 · 기준 이탈 여부 · 메모)를 사람이 넣으면 서버가
   센서 경보와 같은 모양의 경보(OIL_ANALYSIS, 출처 = 사람 입력, 입력자)를 만들어 같은 경보 경로로 보낸다. 기준 안이면 경보 없음 + 사유.
   어느 흐름이 여는지는 경보 정책(배포된 흐름)이 정한다 — 배포 흐름이 없으면 사람 검토(경보 분류).
   서버: process GET /api/human-alerts/form · POST /api/human-alerts (it/process/procsvc/human_alert.py). */
(function () {
  const O = { el: null, form: null, err: '', sending: false, last: null,
              draft: { asset: 'HYD-01', item: '', value: '', out: null, memo: '', by: '' } };
  const api = p => API.process + p;
  if (typeof PATTERN_LABEL !== 'undefined' && !PATTERN_LABEL.OIL_ANALYSIS) PATTERN_LABEL.OIL_ANALYSIS = '오일 분석 기준 이탈 (사람 입력)';

  function meNow() { return (window.hydInbox && window.hydInbox.me && window.hydInbox.me()) || null; }

  async function mount(el) {
    O.el = el; render();
    try { O.form = await getJ(api('/api/human-alerts/form')); O.err = ''; }
    catch (e) { O.err = '입력 칸을 읽지 못했습니다: ' + e.message; }
    const p = pattern();
    if (p && !O.draft.item) O.draft.item = p.items[0].key;
    render();
  }
  function show() { render(); }
  const pattern = () => O.form && O.form.patterns.find(p => p.code === 'OIL_ANALYSIS');

  async function send() {
    const p = pattern(), d = O.draft, m = meNow();
    if (!p || O.sending) return;
    const by = m ? m.id : d.by.trim();
    if (d.out === null) { O.err = '기준 이탈 여부를 고르세요'; render(); return; }
    if (!by) { O.err = '입력자를 적거나 내 작업함에서 "나"를 고르세요'; render(); return; }
    O.sending = true; O.err = ''; render();
    try {
      O.last = await postJ(api('/api/human-alerts'), {
        pattern: p.code, asset: d.asset, item: d.item, out_of_spec: d.out, memo: d.memo,
        value: d.value === '' ? null : Number(d.value), by, by_name: m ? (m.name || m.id) : by, role: m && (m.roles || [])[0] || null });
      if (O.last.raised) { d.memo = ''; d.value = ''; d.out = null; }
    } catch (e) { O.err = e.message; }
    finally { O.sending = false; render(); }
  }

  function resultHtml() {
    const r = O.last;
    if (!r) return '';
    if (!r.raised) return `<div class="summary prose" role="status"><p style="margin:0">${UI.chipText('경보 없음', 'neutral')} ${esc(r.reason)}</p></div>`;
    const target = r.definition || {};
    return `<div class="summary prose" role="status"><p style="margin:0 0 var(--s2)">${UI.chipText('경보 만듦', 'warning')} ${esc(r.reason)}</p>
      <p style="margin:0 0 var(--s2)">${UI.chipText(r.route === 'response' ? '배포된 흐름' : '사람 검토', r.route === 'response' ? 'success' : 'neutral')}
        ${esc(r.route_text)} — ${esc(target.name || '흐름')} (판본 ${esc(target.version || '')})</p>
      ${r.instance ? `<div class="form-actions"><a class="btn small" href="#/instances/${encodeURIComponent(r.instance)}">처리 건 보기 →</a></div>` : ''}</div>`;
  }

  function render() {
    if (!O.el) return;
    const p = pattern(), d = O.draft, m = meNow();
    if (!O.form) { O.el.innerHTML = O.err ? UI.errorBlock('입력 칸을 읽지 못했습니다', O.err) : UI.loading('입력 칸을 읽는 중…'); return; }
    if (!p) { O.el.innerHTML = UI.empty('사람 입력 경보 종류가 없습니다', '서버의 human_alert 계약을 확인하세요'); return; }
    const opt = (v, t, sel) => `<option value="${esc(v)}" ${v === sel ? 'selected' : ''}>${esc(t)}</option>`;
    const unit = (p.items.find(i => i.key === d.item) || {}).unit || '';
    const body = `<p class="field-hint">작동유는 실시간 센서가 없어 정기 오일 분석 결과를 사람이 넣습니다. 기준 이탈이면 센서 경보와 같은 길로 처리 건이 열립니다.</p>
      <div class="form-grid">
        ${UI.field({ label: '설비', required: true, input: `<select id="oilAsset">${O.form.assets.map(a => opt(a, a, d.asset)).join('')}</select>` })}
        ${UI.field({ label: '분석 항목', required: true, input: `<select id="oilItem">${p.items.map(i => opt(i.key, i.text, d.item)).join('')}</select>` })}
        ${UI.field({ label: `측정값${unit ? ' (' + unit + ')' : ''}`, hint: '없으면 비워 둡니다', input: `<input id="oilValue" type="number" step="any" value="${esc(d.value)}">` })}
        ${UI.field({ label: '기준 이탈 여부', required: true, input: `<div class="chk-row">
            <label class="chk"><input type="radio" name="oilOut" value="1" ${d.out === true ? 'checked' : ''}> 예 (기준 이탈)</label>
            <label class="chk"><input type="radio" name="oilOut" value="0" ${d.out === false ? 'checked' : ''}> 아니요 (기준 안)</label></div>` })}
        ${m ? UI.field({ label: '입력자', input: `<p style="margin:0">${esc(m.name || m.id)} <span class="muted">(내 작업함의 "나")</span></p>` })
            : UI.field({ label: '입력자', required: true, hint: '내 작업함에서 "나"를 고르면 자동으로 들어갑니다', input: `<input id="oilBy" maxlength="120" value="${esc(d.by)}">` })}
      </div>
      ${UI.field({ label: '메모', input: `<textarea id="oilMemo" rows="2" maxlength="2000">${esc(d.memo)}</textarea>` })}`;
    O.el.innerHTML = UI.card({ title: '오일 분석 결과 입력', body,
      actions: `<button class="btn primary" id="oilSend" ${O.sending ? 'disabled' : ''}>${O.sending ? '보내는 중…' : '입력 보내기'}</button>` })
      + (O.err ? `<p class="neg" role="status">${esc(O.err)}</p>` : '') + resultHtml();
    wire();
  }
  function wire() {
    const q = s => O.el.querySelector(s), d = O.draft;
    q('#oilAsset')?.addEventListener('change', e => { d.asset = e.target.value; });
    q('#oilItem')?.addEventListener('change', e => { d.item = e.target.value; render(); });
    q('#oilValue')?.addEventListener('input', e => { d.value = e.target.value; });
    q('#oilMemo')?.addEventListener('input', e => { d.memo = e.target.value; });
    q('#oilBy')?.addEventListener('input', e => { d.by = e.target.value; });
    O.el.querySelectorAll('input[name="oilOut"]').forEach(r => r.addEventListener('change', e => { d.out = e.target.value === '1'; }));
    q('#oilSend')?.addEventListener('click', send);
  }

  window.hydOilInput = { mount, show, _state: O, _render: render };
})();
