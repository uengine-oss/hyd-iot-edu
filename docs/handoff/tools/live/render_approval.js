// 실제 ui.js · enterprise.js · approvalCard.js 를 node vm 에 올려 C 판단으로 승인 카드를 그리고 id 잔재를 찾는다.
'use strict';
const fs = require('fs'), path = require('path'), vm = require('vm');
const [www, decisionPath] = process.argv.slice(2);
let d = JSON.parse(fs.readFileSync(decisionPath, 'utf8')); d = d.decision || d;
const el = () => ({ innerHTML: '', dataset: {}, style: {}, querySelector: () => null, querySelectorAll: () => [], addEventListener() {}, appendChild() {}, classList: { toggle() {}, add() {}, remove() {}, contains: () => false } });
const ctx = { console, Date, JSON, Math, Number, String, Object, Array, Set, Map, Promise, RegExp, Error, encodeURIComponent, decodeURIComponent,
  setInterval: () => 0, clearInterval() {}, clearTimeout() {}, setTimeout: () => 0, requestAnimationFrame: () => 0, fetch: async () => ({ ok: false }),
  localStorage: { getItem: () => null, setItem() {} }, navigator: {}, matchMedia: () => ({ matches: false, addEventListener() {} }),
  document: { readyState: 'loading', getElementById: () => el(), querySelectorAll: () => [], querySelector: () => el(), addEventListener() {}, createElement: el, body: el(), documentElement: el() },
  location: { hash: '', search: '' }, history: { replaceState() {} }, addEventListener() {} };
ctx.window = ctx; vm.createContext(ctx);
vm.runInContext("const esc = (s) => String(s ?? '').replace(/[&<>\"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '\"': '&quot;' }[c])); const API = { process: '' };", ctx);
vm.runInContext(fs.readFileSync(path.join(www, 'ui.js'), 'utf8'), ctx, { filename: 'ui.js' });
const pick = (file, re) => fs.readFileSync(path.join(www, file), 'utf8').match(re)[0];
vm.runInContext(pick('enterprise.js', /^const ACTION_KO = [\s\S]*?\n}\n/m) + '\nwindow.hydCards = { actionLabel };', ctx);
vm.runInContext(fs.readFileSync(path.join(www, 'approvalCard.js'), 'utf8'), ctx, { filename: 'approvalCard.js' });
vm.runInContext("UI.names = JSON.parse(" + JSON.stringify(fs.readFileSync(path.join(www, 'names.json'), 'utf8')) + ")", ctx);
ctx.__d = d;
const html = vm.runInContext('hydApprove.html(__d, __d.recommended, { pending: true })', ctx);
const text = html.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');
const m = text.match(/승인하면 시스템이.{0,40}/); const k = text.match(/지식 그래프 근거.{0,60}/);
console.log(JSON.stringify({ hydCards: !!ctx.hydCards, do: m && m[0], kg: k && k[0], ids: [...new Set(text.match(/\b(?:skill|sup|user|role):[a-z0-9-]+/g) || [])] }, null, 1));
