/* 흐름 그림 보기 — bpmn-js NavigatedViewer(보기 전용)로 .bpmn 한 장을 어두운 캔버스에 그대로 보여 준다(디자인 기준 6-2). 포털은 그리지 않는다.
   흐름 화면(flows.js)이 쓴다: 가져온 그림 · 등록한 판본의 그림을 학생이 그린 배치 그대로 보이고, 배치 정보(BPMNDiagram)가 없으면
   hydBpmnLayout.ensureLayout 으로 자동 배치한 뒤 그 사실을 그림 위에 알린다. [전체 흐름 보기]는 같은 그림을 큰 대화상자에 맞춰 연다.

   window.hydBpmnView
     open(container, xml)            → { viewer, laidOut }   bpmn-js 를 싣고(UI.need) 그림 하나를 연다. 색은 어두운 캔버스의 값
     fit(viewer) · zoom(viewer, ±1)   화면에 맞춤 · 축소 확대
     mount(host, { key, title, load }) 캔버스 한 판(도구: 축소 · 확대 · 화면에 맞춤 · 전체 흐름 보기). load() → { xml, laidOut?, note? }.
                                      같은 key 로 다시 부르면 다시 그리지 않는다(끌어 옮긴 자리 · 배율이 남는다).
   처리 건의 진행 길(flow.js)은 같은 bpmn-js 에 상태 표시(끝남 · 지금 · 남음)를 얹는다. 캔버스의 치수와 안내 줄 · 대화상자의 모양(flow-canvas · flow-note ·
   flow-wait · dialog.flow-dialog)은 case.css 의 한 벌을 함께 쓴다. */
(function () {
  const cv = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const hasLayout = xml => /<(\w+:)?BPMNDiagram[\s>]/.test(xml);
  const LAID_OUT = '배치 정보가 없어 자동으로 놓았습니다 — bpmn.io에서 열어 배치를 고치면 그대로 보입니다';

  async function open(container, xml) {
    await UI.need('bpmn');
    let laidOut = false;
    if (!hasLayout(xml)) { await UI.need('bpmn-layout'); const laid = await hydBpmnLayout.ensureLayout(xml); xml = laid.xml; laidOut = laid.laidOut; }
    const viewer = new BpmnJS({ container, bpmnRenderer: { defaultFillColor: cv('--cv-node'), defaultStrokeColor: '#8493a8', defaultLabelColor: cv('--cv-ink') },
      textRenderer: { defaultStyle: { fontFamily: 'Pretendard Variable, sans-serif', fontSize: 13 }, externalStyle: { fontSize: 12 } } });
    try { await viewer.importXML(xml); } catch (e) { viewer.destroy(); throw new Error('BPMN 그림을 열지 못했습니다 — ' + (e.message || e)); }
    return { viewer, laidOut };
  }
  // 전체를 맞춰 보이되 가장자리와 위 도구 줄에 붙지 않게 조금 물린다
  function fit(viewer) { const canvas = viewer.get('canvas'); canvas.zoom('fit-viewport', 'auto'); canvas.zoom(canvas.zoom() * 0.88); }
  function zoom(viewer, dir) { const canvas = viewer.get('canvas'); canvas.zoom(Math.min(2.5, Math.max(0.2, canvas.zoom() * (dir > 0 ? 1.2 : 1 / 1.2)))); }

  const tools = (prefix, more) => `<span class="cv-tools" role="group" aria-label="그림 도구"><button type="button" data-${prefix}-zoom="-1" aria-label="축소" data-tooltip="축소" data-side="bottom">${UI.icon('minus')}</button>` +
    `<button type="button" data-${prefix}-zoom="1" aria-label="확대" data-tooltip="확대" data-side="bottom">${UI.icon('plus')}</button>` +
    `<button type="button" data-${prefix}-fit aria-label="화면에 맞춤" data-tooltip="화면에 맞춤" data-side="bottom">${UI.icon('scan')}</button>${more}</span>`;
  const frame = (prefix, title, more, label) => `<div class="canvas-bar">${title ? `<span class="cv-legend flow-title">${esc(title)}</span>` : ''}<span class="grow"></span>${tools(prefix, more)}</div>` +
    `<div class="bpmn" data-${prefix}-stage role="img" aria-label="${esc(label)}"></div><p class="flow-note" data-${prefix}-note hidden></p><div class="flow-wait" data-${prefix}-wait>${UI.loading('', 'compact')}</div>`;
  function note(root, prefix, got) {
    const text = [got.laidOut ? LAID_OUT : '', got.note || ''].filter(Boolean).join(' · ');
    const p = root.querySelector(`[data-${prefix}-note]`); p.hidden = !text; p.textContent = text;
  }

  /* 캔버스 한 판. host._bv = { key, V(viewer), src } */
  function mount(host, o) {
    if (host._bv && host._bv.key === o.key) return;
    if (host._bv && host._bv.viewer) host._bv.viewer.destroy();
    const B = host._bv = { key: o.key, viewer: null, src: null, o };
    host.innerHTML = `<div class="canvas flow-canvas">${frame('bv', o.title, `<button type="button" class="wide" data-bv-all>${UI.icon('maximize-2')}전체 흐름 보기</button>`, o.title || '흐름 그림')}</div>`;
    const wait = host.querySelector('[data-bv-wait]');
    (async () => {
      const src = await o.load();
      const got = await open(host.querySelector('[data-bv-stage]'), src.xml);
      if (host._bv !== B) { got.viewer.destroy(); return; }      // 그리는 사이 다른 흐름을 골랐다
      B.viewer = got.viewer; B.src = { xml: src.xml, laidOut: got.laidOut || !!src.laidOut, note: src.note || '' };
      wait.remove(); note(host, 'bv', B.src); fit(B.viewer);
    })().catch(err => {
      if (host._bv !== B) return;
      console.error('[hydBpmnView] 흐름 그림을 그리지 못했습니다', o.key, err);
      wait.innerHTML = UI.errorBlock('흐름 그림을 그리지 못했습니다', err.message, { retry: true });
      wait.querySelector('[data-retry]').addEventListener('click', () => { host._bv = null; mount(host, o); });
    });
    if (host._bvWired) return;
    host._bvWired = true;
    host.addEventListener('click', ev => {
      const now = host._bv; if (!now || !now.viewer) return;
      const z = ev.target.closest('[data-bv-zoom]');
      if (z) zoom(now.viewer, Number(z.dataset.bvZoom));
      else if (ev.target.closest('[data-bv-fit]')) fit(now.viewer);
      else if (ev.target.closest('[data-bv-all]')) openFull(now.o.title, now.src);
    });
  }

  /* 전체 흐름: 큰 대화상자에 전체를 맞춰 연다. 닫으면 그림을 치운다 */
  function openFull(title, src) {
    document.querySelector('dialog.flow-dialog')?.remove();
    const dlg = document.createElement('dialog');
    dlg.className = 'dialog flow-dialog';
    dlg.setAttribute('aria-label', `전체 흐름 — ${title || '흐름'}`);
    dlg.innerHTML = `<div><div class="canvas">${frame('fd', title, `<button type="button" class="wide" data-fd-close>${UI.icon('x')}닫기</button>`, '전체 흐름')}</div></div>`;
    document.body.append(dlg);
    let viewer = null, down = false;
    dlg.addEventListener('pointerdown', ev => { down = ev.target === dlg; });
    dlg.addEventListener('click', ev => {
      if ((ev.target === dlg && down) || ev.target.closest('[data-fd-close]')) { dlg.close(); return; }
      if (!viewer) return;
      const z = ev.target.closest('[data-fd-zoom]');
      if (z) zoom(viewer, Number(z.dataset.fdZoom)); else if (ev.target.closest('[data-fd-fit]')) fit(viewer);
    });
    dlg.addEventListener('close', () => { if (viewer) viewer.destroy(); dlg.remove(); });
    dlg.showModal();
    open(dlg.querySelector('[data-fd-stage]'), src.xml).then(got => {
      if (!dlg.isConnected) { got.viewer.destroy(); return; }
      viewer = got.viewer; dlg.querySelector('[data-fd-wait]').remove(); note(dlg, 'fd', { laidOut: got.laidOut || src.laidOut, note: src.note }); fit(viewer);
    }).catch(err => { console.error('[hydBpmnView] 전체 흐름을 그리지 못했습니다', err); const w = dlg.querySelector('[data-fd-wait]'); if (w) w.innerHTML = UI.errorBlock('흐름 그림을 그리지 못했습니다', err.message); });
    dlg.querySelector('[data-fd-close]').focus();
    return dlg;
  }

  window.hydBpmnView = { open, fit, zoom, mount, openFull, hasLayout };
})();
