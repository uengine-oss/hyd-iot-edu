/* K1 내 사례(시스템 › 관리 › 내 설정의 「내 사례」 줄 — configBundle.js 가 [사례 보기]로 연다): 이 PC에서 만든 흐름 · 에이전트 · 스킬 · 도구 서버에 사례 이름 꼬리표를 붙여 묶고,
   사례 하나를 구성 파일로 받는다. 계정 · 소유권의 뜻은 없다.
   모양은 옆 판(디자인기준 4-19 — 표가 든 넓은 판): 머리(이름 · 한 문장 · 닫기) → 사례 고르기와 [이 사례 파일 받기] 한 줄 → 구성 표(구성 · 종류 · 구분 · 사례 이름 칸).
   서버: process GET /api/config/cases · PUT /api/config/cases/tag · GET /api/config/export?case= */
(function () {
  const h = esc;                                       // 포털 공용 이스케이프(ui.js)
  let dlg = null, rows = [], filter = '', busy = false, baseFlows = null, readError = '';      // baseFlows = 기본 제공 흐름의 id(읽지 못했으면 null)
  const drafts = new Map(), key = row => JSON.stringify([row.kind, row.asset_id]);
  const request = (path, init) => requestJ(API.process + path, init);
  const $ = id => dlg.querySelector('#' + id);
  const message = (text, bad = false) => { const m = $('caseMessage'); m.textContent = text; if (bad && text) m.dataset.tone = 'danger'; else delete m.dataset.tone; };
  // [이 사례 파일 받기]는 사례를 골랐을 때만 켜진다 — 꺼져 있으면 까닭이 단추의 도움말과, 사례가 하나라도 있을 때 그 아래 한 줄에 있다
  const exportState = () => { const b = $('caseExport'); b.disabled = !filter || busy; b.title = filter ? '' : '사례를 고르면 받을 수 있습니다.'; $('caseExportWhy').hidden = !!filter || !rows.some(r => r.label); };
  // 구분: 이 목록의 응답(/api/config/cases)에는 기본 제공 표시가 없어, 흐름 목록(/api/flows 의 class_flow)에서 읽는다. 흐름이 아닌 줄은 내가 만든 것만 온다(서버가 그렇게 고른다)
  const origin = row => row.kind !== 'flows' ? '내가 만든 것' : baseFlows == null ? '구분을 읽지 못함' : baseFlows.has(row.asset_id) ? '기본 제공' : '내가 만든 것';

  function build() {
    dlg = document.createElement('dialog');
    dlg.className = 'sheet'; dlg.id = 'caseSheet'; dlg.setAttribute('data-wide', ''); dlg.setAttribute('aria-label', '내 사례');
    dlg.innerHTML = `<header class="sheet-head"><div><h2>내 사례</h2><p class="muted">구성에 사례 이름을 적으면 그 이름으로 묶입니다. 이름을 비우면 묶음에서 빠집니다.</p></div>
        <button type="button" class="btn" data-variant="ghost" data-size="icon" data-case-close aria-label="닫기" data-tooltip="닫기" data-side="left">${UI.icon('x')}</button></header>
      <div class="sheet-body"><div class="case-bar"><select class="select" id="caseFilter" aria-label="사례"><option value="">전체 구성</option></select>
          <button type="button" class="btn" data-variant="outline" id="caseExport" disabled>${UI.actHtml('export', '이 사례 파일 받기')}</button></div>
        <p class="muted" id="caseExportWhy" hidden>사례를 고르면 그 사례의 구성만 파일로 받을 수 있습니다.</p><p id="caseMessage" class="muted" role="status"></p><div id="caseAssets"></div></div>`;
    document.getElementById('view-admin').append(dlg);
    dlg.addEventListener('click', e => { if (e.target === dlg || e.target.closest('[data-case-close]')) dlg.close(); else if (e.target.closest('[data-retry]')) load(); });
    $('caseFilter').addEventListener('change', e => { filter = e.target.value; draw(); });
    $('caseExport').addEventListener('click', async () => {
      if (busy || !filter) return; busy = true; exportState();
      try {
        const data = await request('/api/config/export?case=' + encodeURIComponent(filter));
        const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }));
        const link = document.createElement('a'); link.href = url; link.download = '내-사례-구성-파일.json'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 5000);
        const selected = data.case_selection; message(`사례 구성 ${selected.direct_count}개와 연결 구성 ${selected.dependency_count}개를 파일로 받았습니다.${selected.dependencies.length ? ' 함께 담은 것: ' + selected.dependencies.map(d => d.name + ' (' + d.kind_name + ')').join(', ') : ''} 비밀 값은 포함하지 않습니다.`);
      } catch (e) { message(e.message, true); } finally { busy = false; exportState(); }
    });
  }
  function draw() {
    const labels = [...new Set(rows.map(r => r.label).filter(Boolean))].sort();
    if (filter && !labels.includes(filter)) filter = '';
    $('caseFilter').innerHTML = '<option value="">전체 구성</option>' + labels.map(label => `<option value="${h(label)}" ${label === filter ? 'selected' : ''}>${h(label)}</option>`).join('');
    exportState();
    const shown = rows.map((row, index) => ({ row, index })).filter(({ row }) => !filter || row.label === filter);
    $('caseAssets').innerHTML = readError ? UI.errorBlock('구성 목록을 읽지 못했습니다', readError, { retry: true })
      : shown.length ? `<div class="table-container"><table class="table"><thead><tr><th>구성</th><th>종류</th><th>구분</th><th>사례 이름</th></tr></thead><tbody>` +
        shown.map(({ row, index }) => `<tr data-case-row="${index}"><td>${h(row.name)}</td><td>${h(row.kind_name)}</td><td class="muted">${h(origin(row))}</td>` +
          `<td><input class="input" data-case-label maxlength="60" value="${h(drafts.get(key(row)) ?? row.label)}" placeholder="사례 이름" aria-label="${h(row.name)} 사례 이름"><p class="muted" data-case-status role="status" hidden></p></td></tr>`).join('') + '</tbody></table></div>'
      : UI.empty('아직 묶을 구성이 없습니다', '흐름 · 에이전트 · 스킬 · 도구 서버를 만들면 여기에 나옵니다.');
    $('caseAssets').querySelectorAll('[data-case-label]').forEach(input => input.addEventListener('input', () => drafts.set(key(rows[+input.closest('[data-case-row]').dataset.caseRow]), input.value)));
    // 줄마다 [저장] 단추를 두지 않는다: 이름을 적고 칸을 떠나거나 Enter 를 누르면(change) 그 줄이 저장되고, 저장한 사실이 표 위 한 줄에 남는다
    $('caseAssets').querySelectorAll('[data-case-label]').forEach(input => input.addEventListener('change', async () => {
      const line = input.closest('[data-case-row]'), row = rows[+line.dataset.caseRow], status = line.querySelector('[data-case-status]');
      if (busy || input.value === (row.label || '')) return;
      busy = true; input.disabled = true; $('caseFilter').disabled = true; exportState();
      try {
        const result = await request('/api/config/cases/tag', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ kind: row.kind, asset_id: row.asset_id, label: input.value }) });
        row.label = result.label; drafts.delete(key(row)); busy = false; draw(); const obj = `「${row.name}」${window.hydWords.josa(row.name, '을/를')}`; message(result.label ? `${obj} 「${result.label}」 사례에 넣었습니다.` : `${obj} 사례 묶음에서 뺐습니다.`);
      } catch (e) { status.textContent = e.message; status.dataset.tone = 'danger'; status.hidden = false; }
      finally { busy = false; input.disabled = false; $('caseFilter').disabled = false; exportState(); }
    }));
  }
  async function load() {
    if (busy) return; busy = true; readError = ''; message('구성을 읽는 중…');
    try { const data = await request('/api/config/cases'); if (!Array.isArray(data.assets)) throw new Error('구성 목록 응답 형식이 올바르지 않습니다.'); rows = data.assets;
      try { const f = await request('/api/flows'); baseFlows = new Set([...(f.versions || []).filter(v => v.class_flow).map(v => v.id), ...(f.drafts || []).filter(d => d.class_flow).map(d => d.proc_def_id)]); } catch (e) { baseFlows = null; }
    } catch (e) { rows = []; readError = e.message; }
    busy = false; message(''); draw();
  }
  // 열 때마다 구성 목록을 새로 읽는다(다른 화면에서 만든 것이 바로 보이게)
  function open() { if (!dlg) build(); if (!dlg.open) dlg.showModal(); return load(); }
  window.hydStudentCases = { open };
})();
