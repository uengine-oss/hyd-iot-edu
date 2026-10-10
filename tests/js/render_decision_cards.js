// 라이브 3차 남은 것(카드 머리말) 시험용: 포털의 실제 ui.js · plainWords.js · approvalCard.js · caseRecord.js 와 enterprise.js 의 카드 그리기
// 부분을 node vm 에 올리고, 판단 결과(options · facts · origin)로 세 화면을 그린다 — 승인 카드(hydApprove.html), 처리 기록의 비교한 대안 ·
// 지식 경로(hydRecord.altHtml · knowledgeHtml), 조치 판단 카드(hydCards.cardHtml). DOM 없이 HTML 글을 돌려준다.
// 사용: node render_decision_cards.js <it/portal/www> <fixture.json>  → stdout 에 {이름: {approval, alts, path, cards[]}} JSON
'use strict';
const fs = require('fs'), path = require('path'), vm = require('vm');
const [www, fixturePath] = process.argv.slice(2);
if (!www || !fixturePath) throw new Error('사용: node render_decision_cards.js <it/portal/www> <fixture.json> — 인자 두 개가 필요합니다');
const fx = JSON.parse(fs.readFileSync(fixturePath, 'utf8'));

const ctx = {
  console, Date, JSON, Math, Number, String, Object, Array, Set, Map, Promise, RegExp, Error, encodeURIComponent, decodeURIComponent,
  setInterval: () => 0, clearTimeout: () => {}, setTimeout: () => 0, requestAnimationFrame: () => 0,
  document: { readyState: 'complete', getElementById: () => null, querySelectorAll: () => [], querySelector: () => null, addEventListener: () => {} },
  localStorage: { getItem: () => null, setItem: () => {} },
  location: { hash: '' }, addEventListener: () => {},
  hydStream: { subscribe: () => {} },
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
// enterprise.js 는 DOM 을 쓰는 큰 파일이라 카드 그리기 부분(signNum ~ cardHtml)만 원래 파일에서 가져온다
vm.runInContext(pick('enterprise.js', /^function signNum[\s\S]*?\n}\n(?=function reviewMatches)/m) + '\nwindow.hydCards = { cardHtml, actionLabel };', ctx);
for (const f of ['plainWords.js', 'approvalCard.js', 'resultReport.js', 'caseRecord.js']) vm.runInContext(fs.readFileSync(path.join(www, f), 'utf8'), ctx, { filename: f });

const out = {};
for (const [name, d] of Object.entries(fx.decisions)) {
  ctx.hydWords.caseNames = fx.names || {};
  out[name] = {
    approval: ctx.hydApprove.html(d, d.recommended),
    alts: ctx.hydRecord.altHtml(d),
    path: ctx.hydRecord.knowledgeHtml({ v: {} }, null, d),
    cards: (d.options || []).map(o => ctx.hydCards.cardHtml(o, { rec: d.recommended, maxAbs: 4, decision: d })),
  };
}
process.stdout.write(JSON.stringify(out));
