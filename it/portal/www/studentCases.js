/* K1 내 사례(시스템 › 관리의 「내가 만든 설정」 접기 안 — configBundle.js 가 싣는다): 이 PC에서 만든 흐름 · 에이전트 · 스킬 · 도구 서버에 사례 이름 꼬리표를 붙여 묶고,
   사례 하나를 출발본 파일로 받는다. 계정 · 소유권의 뜻은 없다. 제목 · 한 문장 · 도구 줄 · 표 한 장(키트의 table).
   서버: process GET /api/config/cases · PUT /api/config/cases/tag · GET /api/config/export?case= */
(function () {
  const h = esc;                                       // 포털 공용 이스케이프(ui.js)
  async function mount(host) {
    let rows = [], filter = '', busy = false, baseFlows = null;      // baseFlows = 기본 제공 흐름의 id(읽지 못했으면 null)
    const drafts = new Map(), key = row => JSON.stringify([row.kind, row.asset_id]);
    const base = () => typeof API !== 'undefined' ? API.process : '';
    const request = (path, init) => requestJ(base() + path, init);
    host.innerHTML = `<section class="cases" data-kit><div class="sec-head"><h2>내 사례</h2></div>
      <p class="muted">구성에 사례 이름을 적어 묶고, 사례를 골라 파일로 받습니다. 이름을 비우면 묶음에서 빠집니다.</p>
      <div class="admin-tools"><div role="group" class="field"><label for="caseFilter">사례</label><select class="select" id="caseFilter"><option value="">전체 구성</option></select></div>
        <button type="button" class="btn" data-variant="outline" data-size="sm" id="caseExport" disabled>${UI.actHtml('export', '이 사례 파일 받기')}</button><span class="muted" id="caseExportWhy"></span><button type="button" class="btn" data-variant="ghost" data-size="icon-sm" id="caseReload" aria-label="${h(UI.acts.reload[0])}" data-tooltip="${h(UI.acts.reload[0])}" data-side="top">${UI.icon(UI.acts.reload[1])}</button></div>
      <p id="caseMessage" class="muted" role="status"></p><div id="caseAssets"></div></section>`;
    const $ = id => host.querySelector('#' + id);
    const message = (text, bad = false) => { const m = $('caseMessage'); m.textContent = text; if (bad) m.dataset.tone = 'danger'; else delete m.dataset.tone; };
    // [이 사례 파일 받기]는 사례를 골랐을 때만 켜진다 — 꺼져 있으면 까닭을 옆에 쓴다
    const exportState = () => { $('caseExport').disabled = !filter || busy; $('caseExportWhy').textContent = filter ? '' : '사례를 고르면 받을 수 있습니다.'; };
    // 구분: 이 목록의 응답(/api/config/cases)에는 기본 제공 표시가 없어, 흐름 목록(/api/flows 의 class_flow)에서 읽는다. 흐름이 아닌 줄은 내가 만든 것만 온다(서버가 그렇게 고른다)
    const origin = row => row.kind !== 'flows' ? '<span class="tag" data-tone="brand" data-plain>내가 만든 것</span>' : baseFlows == null ? '<span class="muted">구분을 읽지 못함</span>'
      : baseFlows.has(row.asset_id) ? '<span class="tag" data-plain>기본 제공</span>' : '<span class="tag" data-tone="brand" data-plain>내가 만든 것</span>';
    function draw() {
      const labels = [...new Set(rows.map(r => r.label).filter(Boolean))].sort();
      if (filter && !labels.includes(filter)) filter = '';
      $('caseFilter').innerHTML = '<option value="">전체 구성</option>' + labels.map(label => `<option value="${h(label)}" ${label === filter ? 'selected' : ''}>${h(label)}</option>`).join('');
      exportState();
      const shown = rows.map((row, index) => ({ row, index })).filter(({ row }) => !filter || row.label === filter);
      $('caseAssets').innerHTML = shown.length ? `<div class="table-container"><table class="table"><thead><tr><th>구성</th><th>종류</th><th>구분</th><th>사례 이름</th></tr></thead><tbody>` +
        shown.map(({ row, index }) => `<tr data-case-row="${index}"><td>${h(row.name)}</td><td>${h(row.kind_name)}</td><td>${origin(row)}</td>` +
          `<td><input class="input" data-case-label maxlength="60" value="${h(drafts.get(key(row)) ?? row.label)}" placeholder="사례 이름" aria-label="${h(row.name)} 사례 이름"> <span class="muted" data-case-status role="status"></span></td></tr>`).join('') + '</tbody></table></div>'
        : UI.empty('아직 묶을 구성이 없습니다', '흐름 · 에이전트 · 스킬 · 도구 서버를 만들면 여기에 나옵니다.', 'compact');
      $('caseAssets').querySelectorAll('[data-case-label]').forEach(input => input.addEventListener('input', () => drafts.set(key(rows[+input.closest('[data-case-row]').dataset.caseRow]), input.value)));
      // 줄마다 [저장] 단추를 두지 않는다: 이름을 적고 칸을 떠나거나 Enter 를 누르면(change) 그 줄이 저장된다
      $('caseAssets').querySelectorAll('[data-case-label]').forEach(button => button.addEventListener('change', async () => {
        const line = button.closest('[data-case-row]'), row = rows[+line.dataset.caseRow], input = button, status = line.querySelector('[data-case-status]');
        if (busy || input.value === (row.label || '')) return;
        busy = true; button.disabled = true; $('caseReload').disabled = true; $('caseFilter').disabled = true; exportState();
        try {
          const result = await request('/api/config/cases/tag', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ kind: row.kind, asset_id: row.asset_id, label: input.value }) });
          row.label = result.label; drafts.delete(key(row)); message(result.label ? `「${result.label}」 사례에 넣었습니다.` : '사례 묶음에서 뺐습니다.'); busy = false; draw();
        } catch (e) { status.textContent = e.message; status.dataset.tone = 'danger'; }
        finally { busy = false; button.disabled = false; $('caseReload').disabled = false; $('caseFilter').disabled = false; exportState(); }
      }));
    }
    async function load() {
      if (busy) return; busy = true; $('caseReload').disabled = true; message('내 사례 구성을 읽는 중…');
      try { const data = await request('/api/config/cases'); if (!Array.isArray(data.assets)) throw new Error('구성 목록 응답 형식이 올바르지 않습니다.'); rows = data.assets;
        try { const f = await request('/api/flows'); baseFlows = new Set([...(f.versions || []).filter(v => v.class_flow).map(v => v.id), ...(f.drafts || []).filter(d => d.class_flow).map(d => d.proc_def_id)]); } catch (e) { baseFlows = null; }
        busy = false; draw(); message(''); }
      catch (e) { message(e.message, true); }
      finally { busy = false; $('caseReload').disabled = false; exportState(); }
    }
    $('caseFilter').addEventListener('change', e => { filter = e.target.value; draw(); });
    $('caseReload').addEventListener('click', load);
    $('caseExport').addEventListener('click', async () => {
      if (busy || !filter) return; busy = true; exportState();
      try {
        const data = await request('/api/config/export?case=' + encodeURIComponent(filter));
        const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }));
        const link = document.createElement('a'); link.href = url; link.download = '내-사례-출발본.json'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 5000);
        const selected = data.case_selection; message(`사례 구성 ${selected.direct_count}개와 연결 구성 ${selected.dependency_count}개를 파일로 받았습니다.${selected.dependencies.length ? ' 함께 담은 것: ' + selected.dependencies.map(d => d.name + ' (' + d.kind_name + ')').join(', ') : ''} 비밀값은 포함하지 않습니다.`);
      } catch (e) { message(e.message, true); } finally { busy = false; exportState(); }
    });
    await load();
  }
  window.hydStudentCases = { mount };
})();
