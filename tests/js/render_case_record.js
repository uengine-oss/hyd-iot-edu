// C3 시험용: 포털의 실제 ui.js · plainWords.js · resultReport.js · caseRecord.js 를 node vm 에 올리고, 파이썬 시험이 실제 런타임(MemoryRepo ·
// 엔진)으로 만든 처리 건 view 로 처리 기록 모델(hydRecord.build)을 만든다. 화면 DOM 없이 단계 · 문장 · 칸 · "기록에 없는 것"을 돌려준다.
// 사용: node render_case_record.js <it/portal/www> <fixture.json>  → stdout 에 {시나리오: {steps, gaps}} JSON
'use strict';
const fs = require('fs'), path = require('path'), vm = require('vm');
const [www, fixturePath] = process.argv.slice(2);
if (!www || !fixturePath) throw new Error('사용: node render_case_record.js <it/portal/www> <fixture.json> — 인자 두 개가 필요합니다');
const fx = JSON.parse(fs.readFileSync(fixturePath, 'utf8'));

const ctx = {
  console, Date, JSON, Math, Number, String, Object, Array, Set, Map, Promise, RegExp, Error, encodeURIComponent, decodeURIComponent,
  setInterval: () => 0, clearTimeout: () => {}, setTimeout: () => 0, requestAnimationFrame: () => 0,
  document: { readyState: 'complete', getElementById: () => null, querySelectorAll: () => [], querySelector: () => null, addEventListener: () => {} },
  localStorage: { getItem: () => null, setItem: () => {} },
  location: { hash: '' }, addEventListener: () => {},
  hydStream: { subscribe: () => {} },                       // caseRecord.js 가 붙는 실시간 버스(시험에서는 이벤트 없음)
};
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(`
  const esc = (s) => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const API = { process: '' };
  const getJ = async url => { const e = new Error('404 ' + url); e.status = 404; throw e; };
`, ctx);
vm.runInContext(fs.readFileSync(path.join(www, 'ui.js'), 'utf8'), ctx, { filename: 'ui.js' });
vm.runInContext(`UI.names = ${fs.readFileSync(path.join(www, 'names.json'), 'utf8')};`, ctx);
const pick = (file, re) => { const m = fs.readFileSync(path.join(www, file), 'utf8').match(re); if (!m) throw new Error(`${file}: ${re} 를 찾지 못했습니다`); return m[0]; };
vm.runInContext(pick('app.js', /^const PATTERN_LABEL = .*;$/m), ctx);
for (const f of ['plainWords.js', 'approvalCard.js', 'resultReport.js', 'caseRecord.js']) vm.runInContext(fs.readFileSync(path.join(www, f), 'utf8'), ctx, { filename: f });

const out = {};
for (const sc of fx.scenarios) {
  const m = ctx.hydRecord.build(sc.view, sc.ext || {}, []);
  out[sc.name] = {
    steps: m.steps.map(s => ({ key: s.key, type: s.type, title: s.title, actor: s.actor, sentence: s.sentence, state: s.state,
      chips: (s.chips || []).map(c => c.label).join(' '), sections: (s.sections || []).filter(Boolean).map(x => ({ title: x.title, body: x.body })) })),
    gaps: m.gaps.map(g => g.text),
  };
}
process.stdout.write(JSON.stringify(out));
