/* K1 내 사례(시스템 › 관리의 「내가 만든 설정」 접기 안 — configBundle.js 가 싣는다): 이 PC에서 만든 흐름 · 에이전트 · 스킬 · 도구 서버에 사례 이름 꼬리표를 붙여 묶고,
   사례 하나를 출발본 파일로 받는다. 계정 · 소유권의 뜻은 없다. 모양은 그 접기의 다른 일(출발본 내보내기 · 불러오기)과 같다: 제목 · 한 문장 · 표 한 장(카드로 싸지 않는다).
   서버: process GET /api/config/cases · PUT /api/config/cases/tag · GET /api/config/export?case= */
(function () {
  const h = esc;                                       // 포털 공용 이스케이프(ui.js)
  async function mount(host) {
    let rows = [], filter = '', busy = false;
    const drafts = new Map(), key = row => JSON.stringify([row.kind, row.asset_id]);
    const base = () => typeof API !== 'undefined' ? API.process : '';
    const request = (path, init) => requestJ(base() + path, init);
    host.innerHTML = `<section class="rd-group rd-part"><h3 class="rd-sec">내 사례</h3>
      <p class="rd-note">이 PC에서 만든 흐름 · 에이전트 · 스킬 · 도구 서버를 사례 이름으로 묶습니다. 계정 소유권을 바꾸는 기능은 아닙니다. 줄마다 사례 이름을 적고 저장하세요. 이름을 비우고 저장하면 꼬리표만 뗍니다.</p>
      <div class="rd-inline"><label for="caseFilter">사례</label><select id="caseFilter"><option value="">전체 구성</option></select><button type="button" class="btn small" id="caseReload">다시 읽기</button><button type="button" class="btn small" id="caseExport" disabled>이 사례 파일 받기</button><span class="form-msg" id="caseExportWhy"></span></div>
      <p id="caseMessage" class="rd-note" role="status"></p><div id="caseAssets"></div></section>`;
    const $ = id => host.querySelector('#' + id);
    const message = (text, bad = false) => { $('caseMessage').textContent = text; $('caseMessage').className = 'rd-note' + (bad ? ' neg' : ''); };
    // [이 사례 파일 받기]는 사례를 골랐을 때만 켜진다 — 꺼져 있으면 까닭을 옆에 쓴다
    const exportState = () => { $('caseExport').disabled = !filter || busy; $('caseExportWhy').textContent = filter ? '이 사례와 실행에 필요한 연결 구성을 파일로 받습니다.' : '사례를 고르면 받을 수 있습니다.'; };
    function draw() {
      const labels = [...new Set(rows.map(r => r.label).filter(Boolean))].sort();
      if (filter && !labels.includes(filter)) filter = '';
      $('caseFilter').innerHTML = '<option value="">전체 구성</option>' + labels.map(label => `<option value="${h(label)}" ${label === filter ? 'selected' : ''}>${h(label)}</option>`).join('');
      exportState();
      const shown = rows.map((row, index) => ({ row, index })).filter(({ row }) => !filter || row.label === filter);
      $('caseAssets').innerHTML = shown.length ? `<div class="rd-scroll"><table class="tbl"><thead><tr><th>구성</th><th>종류</th><th>사례 이름</th><th></th></tr></thead><tbody>` +
        shown.map(({ row, index }) => `<tr data-case-row="${index}"><td>${h(row.name)}</td><td>${h(row.kind_name)}</td>` +
          `<td><input data-case-label maxlength="60" value="${h(drafts.get(key(row)) ?? row.label)}" aria-label="${h(row.name)} 사례 이름"></td>` +
          `<td><button type="button" class="btn small" data-case-save>저장</button> <span class="form-msg" role="status"></span></td></tr>`).join('') + '</tbody></table></div>'
        : UI.empty('아직 묶을 구성이 없습니다', '학생이 만든 흐름 · 에이전트 · 스킬 · 도구 서버가 여기에 표시됩니다.');
      $('caseAssets').querySelectorAll('[data-case-label]').forEach(input => input.addEventListener('input', () => drafts.set(key(rows[+input.closest('[data-case-row]').dataset.caseRow]), input.value)));
      $('caseAssets').querySelectorAll('[data-case-save]').forEach(button => button.addEventListener('click', async () => {
        if (busy) return;
        const line = button.closest('[data-case-row]'), row = rows[+line.dataset.caseRow], input = line.querySelector('[data-case-label]'), status = line.querySelector('.form-msg');
        busy = true; button.disabled = true; $('caseReload').disabled = true; $('caseFilter').disabled = true; exportState();
        try {
          const result = await request('/api/config/cases/tag', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ kind: row.kind, asset_id: row.asset_id, label: input.value }) });
          row.label = result.label; drafts.delete(key(row)); message(result.label ? '사례 꼬리표를 저장했습니다.' : '사례 꼬리표를 뗐습니다.'); busy = false; draw();
        } catch (e) { status.textContent = e.message; status.className = 'form-msg neg'; }
        finally { busy = false; button.disabled = false; $('caseReload').disabled = false; $('caseFilter').disabled = false; exportState(); }
      }));
    }
    async function load() {
      if (busy) return; busy = true; $('caseReload').disabled = true; message('내 사례 구성을 읽는 중…');
      try { const data = await request('/api/config/cases'); if (!Array.isArray(data.assets)) throw new Error('구성 목록 응답 형식이 올바르지 않습니다.'); rows = data.assets; busy = false; draw(); message(''); }
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
