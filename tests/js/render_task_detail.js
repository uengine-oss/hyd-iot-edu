// U1 시험용 렌더러: 포털의 실제 ui.js · taskDetail.js 를 node vm 에 올리고, 파이썬 시험이 실제 런타임(MemoryRepo · 엔진 · 워커 ·
// 내장 판단 다리)으로 만든 처리 건 view · 단계 상세 · 판단 결과 · 사건 응답을 HTTP 대신 넘겨 task 상세 패널과 "지금" 줄을 그린다.
// 사용: node render_task_detail.js <it/portal/www> <fixture.json>  → stdout 에 {시나리오: {panel, now, hash}} JSON
'use strict';
const fs = require('fs'), path = require('path'), vm = require('vm');
const [www, fixturePath] = process.argv.slice(2);
const fx = JSON.parse(fs.readFileSync(fixturePath, 'utf8'));

const el = () => ({ innerHTML: '', dataset: {}, querySelector: () => null, querySelectorAll: () => [], classList: { toggle() {}, contains: () => false } });
const nowBox = el();
const ctx = {
  console, Date, JSON, Math, Number, String, Object, Array, Set, Map, Promise, RegExp, Error, encodeURIComponent, decodeURIComponent,
  setInterval: () => 0, clearTimeout: () => {}, setTimeout, requestAnimationFrame: () => 0,
  fetch: async () => ({ ok: false }),
  document: { readyState: 'complete', getElementById: id => (id === 'instNow' ? nowBox : null), querySelectorAll: () => [], querySelector: () => null, addEventListener: () => {} },
  location: { hash: '' },
  history: { replaceState: (_s, _t, h) => { ctx.location.hash = h; } },
  addEventListener: () => {},
  __http: {},
};
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(`
  const esc = (s) => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const API = { process: '' };
  const state = { tab: 'instances' };
  const getJ = async url => { if (Object.prototype.hasOwnProperty.call(window.__http, url)) return JSON.parse(JSON.stringify(window.__http[url])); const e = new Error('404 찾을 수 없음 ' + url); e.status = 404; throw e; };
`, ctx);
vm.runInContext(fs.readFileSync(path.join(www, 'ui.js'), 'utf8'), ctx, { filename: 'ui.js' });
vm.runInContext(`UI.names = ${fs.readFileSync(path.join(www, 'names.json'), 'utf8')};`, ctx);
// 화면 이름표 두 개는 원래 파일에서 그 줄만 가져온다(app.js 의 패턴 이름, enterprise.js 의 조치 이름 — 둘 다 DOM 을 쓰는 큰 파일)
const pick = (file, re) => { const m = fs.readFileSync(path.join(www, file), 'utf8').match(re); if (!m) throw new Error(`${file}: ${re} 를 찾지 못했습니다`); return m[0]; };
vm.runInContext(pick('app.js', /^const PATTERN_LABEL = .*;$/m), ctx);
vm.runInContext(pick('enterprise.js', /^const ACTION_KO = [\s\S]*?\n}\n/m) + '\nwindow.hydCards = { actionLabel };', ctx);
vm.runInContext(fs.readFileSync(path.join(www, 'trace.js'), 'utf8'), ctx, { filename: 'trace.js' });   // A161-U1: 처리 과정 행은 trace.js 와 같은 그리기
vm.runInContext(fs.readFileSync(path.join(www, 'taskDetail.js'), 'utf8'), ctx, { filename: 'taskDetail.js' });

(async () => {
  const out = {};
  const TD = ctx.hydTaskDetail;
  for (const sc of fx.scenarios) {
    ctx.__http = sc.http || {};
    ctx.hydInstances = { I: { view: sc.view, mode: sc.mode || { mode: 'instance', time_scale: 20 } } };
    Object.assign(TD.T, { wid: null, act: null, item: null, error: null, rendered: null, dec: null, decId: null, decErr: null, inc: null, incId: null, incErr: null, incAt: 0, incLoading: false, last: {}, pending: null });
    ctx.location.hash = '';
    for (const e of sc.sse || []) TD.onEvent(e);
    const host = el();
    if (sc.hash) {                                   // enter through the address: #/instances/<처리 건>/task/<단계>
      ctx.location.hash = sc.hash;
      ctx.hydInstances.I.sel = null; ctx.hydInstances.I.tab = 'result';
      ctx.hydInstances.load = async () => { TD.mount(host); };          // instances.js load() ends in renderDetail → mount
      TD.fromHash();
      for (let i = 0; i < 5; i++) await new Promise(r => setTimeout(r, 0));
      out[sc.name] = { panel: host.innerHTML, now: nowBox.innerHTML, hash: ctx.location.hash, sel: ctx.hydInstances.I.sel, tab: ctx.hydInstances.I.tab };
      continue;
    }
    TD.mount(host);
    if (sc.wid) await TD.open(sc.wid);
    else if (sc.activity) TD.openActivity(sc.activity);
    await new Promise(r => setTimeout(r, 0));
    TD.render();
    out[sc.name] = { panel: host.innerHTML, now: nowBox.innerHTML, hash: ctx.location.hash };
  }
  process.stdout.write(JSON.stringify(out));
})().catch(e => { console.error(e && e.stack || e); process.exit(1); });
