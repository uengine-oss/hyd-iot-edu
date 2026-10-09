/* A161-U1 — 수업 시나리오 원인 버튼 (결함 시뮬레이션 화면 맨 위). 버튼은 "원인"만 만든다. 감지와 처리 건 시작은 시스템이 한다.
   목록(TRIGGERS)만 고치면 버튼이 늘어난다 — 시나리오 화면 코드는 이 목록 말고 없다.
   - 준비 확인: 그 서비스의 API 목록(openapi.json)에 주소가 있을 때만 버튼을 켠다. 없으면 "준비 중"(B · C 백엔드가 아직 없는 스택에서도 화면이 깨지지 않게,
     콘솔 404 를 만들지 않게). 화면을 처음 열 때 한 번만 확인한다.
   참고 화면(모방): n8n 수동 실행 "Test workflow" 버튼 카드 · Linear 빈 상태 카드(제목 · 한 줄 설명 · 버튼 하나). 카드 하나에 행동 하나(CLAUDE.md §4). */
(function () {
  const TRIGGERS = [
    { key: 'A', title: '긴급 대응', who: '설비 센서가 알려 줌', button: '쿨러 열화 주입', asset: 'HYD-01',
      desc: 'HYD-01 쿨러 성능을 떨어뜨립니다. 유온이 오르면 감지기가 경보를 내고 처리 건이 시작됩니다.',
      run: () => postJ(API.plant + '/api/fault', { asset: 'HYD-01', type: 'cooler_degradation' }) },
    { key: 'B', title: '정기 정비', who: '운전시간 계수기가 알려 줌', button: '운전시간 +300 h', asset: 'HYD-02',
      desc: 'HYD-02 운전시간을 300시간 앞당깁니다. 정비 주기에 닿으면 정비 계획 처리 건이 시작됩니다.',
      probe: null, run: null },
    { key: 'C', title: '예비품 구매', who: '창고 재고가 알려 줌', button: '자재 출고 −2', asset: 'HYD-03',
      desc: '씰 키트 2개를 출고합니다. 재고가 재주문점 아래로 내려가면 구매 처리 건이 시작됩니다.',
      needs: ['process', '/api/simulate/spare-issue'],
      run: () => postJ(API.process + '/api/simulate/spare-issue', { qty: 2, asset: 'HYD-03', by: '수업 버튼', reason: '수업 시나리오 C 원인 만들기' }) },
  ];
  const ready = {};
  const say = t => { const m = document.getElementById('scenarioMsg'); if (m) m.textContent = t; };

  function draw(host) {
    host.innerHTML = `<div class="sec-head" style="margin-top:0"><h2>수업 시나리오 시작</h2><span class="muted">버튼은 원인만 만듭니다. 감지 · 처리 건 시작은 시스템이 합니다</span></div>
      <div class="trig-grid">${TRIGGERS.map(t => {
        const ok = ready[t.key] === true, wait = ready[t.key] === undefined;
        return `<article class="trig-card ${ok ? '' : 'off'}"><div class="trig-head"><span class="trig-key">${esc(t.key)}</span><div><h3>${esc(t.title)}</h3><span class="muted">${esc(t.who)} · ${esc(t.asset)}</span></div></div>
          <p>${esc(t.desc)}</p>
          <button type="button" class="btn ${ok ? 'primary' : ''}" data-trig="${esc(t.key)}" ${ok ? '' : 'disabled'}>${esc(ok ? t.button : wait ? '확인 중…' : `${t.button} · 준비 중`)}</button></article>`;
      }).join('')}</div>`;
  }
  const specs = {};
  const paths = svc => specs[svc] || (specs[svc] = getJ(API[svc] + '/openapi.json').then(j => Object.keys(j.paths || {})).catch(() => []));
  let probed = false;
  async function probeAll(host) {
    if (probed) return; probed = true;
    await Promise.all(TRIGGERS.map(async t => {
      if (!t.run) { ready[t.key] = false; return; }
      if (!t.needs) { ready[t.key] = true; return; }
      ready[t.key] = (await paths(t.needs[0])).includes(t.needs[1]);
    }));
    draw(host);
  }
  function mount() {
    const view = document.getElementById('view-scenario'); if (!view || document.getElementById('trigPanel')) return;
    const host = document.createElement('section'); host.id = 'trigPanel'; host.className = 'trig-panel';
    view.querySelector('.page-head').after(host);
    draw(host);
    if (view.classList.contains('active') || location.hash.includes('scenario')) probeAll(host);
    document.addEventListener('click', e => { if (e.target.closest('[data-tab="scenario"]')) probeAll(host); });
    host.addEventListener('click', async e => {
      const b = e.target.closest('[data-trig]'); if (!b) return;
      const t = TRIGGERS.find(x => x.key === b.dataset.trig); if (!t || !t.run) return;
      b.disabled = true; say(`${t.title}: ${t.button} 요청 중…`);
      try { await t.run(); say(`${t.title}: ${t.button} 완료. 감지되면 처리 건 화면에 새 건이 나타납니다.`); if (typeof logLine === 'function') logLine(`${t.asset} ${t.button}`); }
      catch (err) { say(`${t.title}: 실패 — ${err.message}`); }
      finally { b.disabled = false; }
    });
  }
  window.hydTriggers = { TRIGGERS, mount };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount); else mount();
})();
