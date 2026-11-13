/* B7 오일 분석 결과 입력 — window.hydOilInput.mount(el). 주소 #/oil
   작동유에는 실시간 센서가 없다. 정기 오일 분석 결과(설비 · 분석 항목 · 측정값 · 기준 이탈 여부 · 메모)를 사람이 넣으면 서버가
   센서 경보와 같은 모양의 경보(OIL_ANALYSIS, 출처 = 사람 입력, 입력자 = 이 PC의 담당자)를 만들어 같은 경보 경로로 보낸다. 기준 안이면 경보 없음 + 사유.
   어느 흐름이 여는지는 경보 정책(배포된 흐름)이 정한다 — 배포 흐름이 없으면 사람 검토(경보 분류).
   서버: process GET /api/human-alerts/form · POST /api/human-alerts (it/process/procsvc/human_alert.py). */
(function () {
  const O = { el: null, form: null, err: '', sending: false, last: null,
              draft: { asset: '', item: '', value: '', out: null, memo: '' } };      // 설비 · 항목은 사람이 고른다(미리 골라 두면 고르지 않은 설비로 경보가 열린다)
  const api = p => API.process + p;

  function meNow() { return (window.hydInbox && window.hydInbox.me && window.hydInbox.me()) || null; }

  window.addEventListener('hyd:me', () => { if (O.el && O.el.isConnected) render(); });
  async function mount(el) {
    O.el = el; render();
    try { O.form = await getJ(api('/api/human-alerts/form')); O.err = ''; }
    catch (e) { O.err = '입력 칸을 읽지 못했습니다: ' + e.message; }
    render();
  }
  function show() { render(); }
  // 입력 칸을 못 읽었으면 셸이 메뉴를 다시 열 때 새로 읽는다(새로 고침 전까지 굳지 않게) — 오류 자리의 [다시 시도]도 같은 길
  const failed = () => !O.form && !!O.err;
  const pattern = () => O.form && O.form.patterns.find(p => p.code === 'OIL_ANALYSIS');

  async function send() {
    const p = pattern(), d = O.draft, m = meNow();
    if (!p || O.sending) return;
    if (!d.asset) { O.err = '설비를 고르세요'; render(); return; }
    if (!d.item) { O.err = '분석 항목을 고르세요'; render(); return; }
    if (d.out === null) { O.err = '기준 이탈 여부를 고르세요'; render(); return; }
    // 입력자는 늘 이 PC의 담당자다. 못 읽었으면 다른 이름으로 대신하지 않고 막는다(자유 글 칸 없음)
    if (!m) { O.err = '담당자 정보를 읽지 못해 보낼 수 없습니다. 화면을 새로 고친 뒤 다시 해 주세요.'; render(); return; }
    O.sending = true; O.err = ''; render();
    try {
      O.last = await postJ(api('/api/human-alerts'), {
        pattern: p.code, asset: d.asset, item: d.item, out_of_spec: d.out, memo: d.memo,
        value: d.value === '' ? null : Number(d.value), by: m.id });      // 입력자는 담당자 id 만 보낸다 — 이름은 서버가 사용자 표에서 읽는다(human_alert.py entered_by)
      if (O.last.raised) { d.memo = ''; d.value = ''; d.out = null; }
    } catch (e) { O.err = e.message; }
    finally { O.sending = false; render(); }
  }

  function resultHtml() {
    const r = O.last;
    if (!r) return '';
    // 결과: 결론 한 줄(경보를 만들었는가) → 서버가 준 까닭 → 어느 흐름이 여는가 → 처리 건으로 가는 길
    if (!r.raised) return `<section class="oil-result" role="status"><h2>경보를 만들지 않았습니다</h2><p>${esc(r.reason)}</p></section>`;
    const target = r.definition || {};
    return `<section class="oil-result" role="status"><h2>경보를 만들었습니다</h2><p>${esc(r.reason)}</p>
      <p>${esc(r.route === 'response' ? '배포된 흐름' : '사람 검토')} · ${esc(r.route_text)} — ${esc(target.name || '흐름')} (판본 ${esc(target.version || '')})</p>
      ${r.instance ? `<a class="btn" href="#/instances/${encodeURIComponent(r.instance)}">처리 건 보기 →</a>` : ''}</section>`;
  }

  function render() {
    if (!O.el) return;
    const p = pattern(), d = O.draft, m = meNow();
    if (!O.form) {
      O.el.innerHTML = O.err ? UI.errorBlock('입력 칸을 읽지 못했습니다', O.err, { retry: true }) : UI.loading('입력 칸을 읽는 중…');
      O.el.querySelector('[data-retry]')?.addEventListener('click', () => mount(O.el));
      return;
    }
    if (!p) { O.el.innerHTML = UI.empty('오일 분석 입력 칸이 서버에 없습니다', '처리 서비스가 이 화면과 다른 판일 수 있습니다. 강사에게 알리세요.'); return; }
    const opt = (v, t, sel) => `<option value="${esc(v)}" ${v === sel ? 'selected' : ''}>${esc(t)}</option>`;
    const unit = (p.items.find(i => i.key === d.item) || {}).unit || '';
    // 폼(디자인 기준 5-6): 한 열 · 폭 720px 까지, 이름표는 입력 위, 단추 줄은 맨 아래 왼쪽. 꺼진 단추의 까닭과 오류는 단추 옆에 글로
    const why = !m ? '담당자 정보를 읽지 못해 보낼 수 없습니다. 화면을 새로 고친 뒤 다시 해 주세요.' : O.err;
    O.el.innerHTML = `<div class="oil-form"><div class="form-grid">
        ${UI.field({ label: '설비', required: true, input: `<select id="oilAsset"><option value="">설비 선택</option>${O.form.assets.map(a => opt(a, a, d.asset)).join('')}</select>` })}
        ${UI.field({ label: '분석 항목', required: true, input: `<select id="oilItem"><option value="">항목 선택</option>${p.items.map(i => opt(i.key, i.text, d.item)).join('')}</select>` })}
        ${UI.field({ label: `측정값${unit ? ' (' + unit + ')' : ''}`, hint: '없으면 비워 둡니다', input: `<input id="oilValue" type="number" step="any" value="${esc(d.value)}">` })}
        ${UI.field({ label: '기준 이탈 여부', required: true, input: `<div class="oil-choice" role="radiogroup" aria-label="기준 이탈 여부">
            <label><input type="radio" name="oilOut" value="1" ${d.out === true ? 'checked' : ''}> 예 (기준 이탈)</label>
            <label><input type="radio" name="oilOut" value="0" ${d.out === false ? 'checked' : ''}> 아니요 (기준 안)</label></div>` })}
        ${UI.field({ label: '메모', input: `<textarea id="oilMemo" rows="3" maxlength="2000">${esc(d.memo)}</textarea>` })}
      </div>
      <div class="oil-actions"><button type="button" class="btn primary" id="oilSend" ${O.sending || !m ? 'disabled' : ''}>${O.sending ? '보내는 중…' : '입력 보내기'}</button>${why ? `<p class="form-msg neg" role="alert">${esc(why)}</p>` : ''}</div></div>` + resultHtml();
    wire();
  }
  function wire() {
    const q = s => O.el.querySelector(s), d = O.draft;
    q('#oilAsset')?.addEventListener('change', e => { d.asset = e.target.value; });
    q('#oilItem')?.addEventListener('change', e => { d.item = e.target.value; render(); });
    q('#oilValue')?.addEventListener('input', e => { d.value = e.target.value; });
    q('#oilMemo')?.addEventListener('input', e => { d.memo = e.target.value; });
    O.el.querySelectorAll('input[name="oilOut"]').forEach(r => r.addEventListener('change', e => { d.out = e.target.value === '1'; }));
    q('#oilSend')?.addEventListener('click', send);
  }

  window.hydOilInput = { mount, show, failed };
})();
