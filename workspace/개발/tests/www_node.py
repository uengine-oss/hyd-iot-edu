"""포털 화면 JS(it/portal/www)의 실제 함수를 node 의 vm 에 실어 부른다 — DOM 없이 도는 부분(이름 · 형식 · 판정 · 처리 기록 만들기)만.

    from www_node import run
    out = run(['ui.js', 'plainWords.js'], "out(UI.who('user:x'))")

- files: index.html 과 같은 차례로 싣는다(앞 파일의 전역을 뒤 파일이 쓴다). script 는 같은 문맥에서 돌고 out(값)으로 JSON 하나를 돌려준다.
- data: 넘기면 문맥의 DATA 로 보인다. 브라우저 밖이라 바깥 요청(fetch)은 실패로 둔다 — 화면 함수가 서버를 부르면 그 사실이 오류로 드러난다.
- prelude: 화면 파일보다 먼저 같은 문맥에서 도는 JS — 브라우저 쪽 대역(document 등)만 둔다. 우리 화면 코드를 바꾸는 데 쓰지 않는다.
  page_dom(): 실제 index.html 의 요소 나무(태그 · id · data-* · 부모 자식)로 만든 작은 document 대역. 실릴 때 패널에 이벤트를 다는 화면
  파일(definitionRegistry · definitionDeploy)을 싣는다 — 없는 id 는 null(브라우저와 같음)이라 화면이 찾는 칸이 페이지에 없으면 실패로 드러난다.
  할 수 있는 것: getElementById · createElement · querySelector(All) · closest 의 태그 이름과 [data-…] 하나, 단추 disabled · 칸 value · select 의
  option, after · appendChild · replaceChildren, 이벤트 달기 · fire(종류). innerHTML 은 글로만 남는다(그 안의 요소는 찾지 못한다).
- node 가 없으면 까닭을 내고 실패한다(건너뛰지 않는다).
"""
import json
import shutil
import subprocess

import pytest

from conftest import WWW

LOADER = r"""
const fs = require('fs'), path = require('path'), vm = require('vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const ctx = { console, URLSearchParams, Intl, Date, Math, JSON, Map, Set, structuredClone,
  setTimeout: () => 0, clearTimeout: () => {}, setInterval: () => 0, clearInterval: () => {}, requestAnimationFrame: () => 0,
  fetch: () => Promise.reject(new Error('fetch 없음(시험 문맥)')), addEventListener: () => {}, location: { hostname: '127.0.0.1', hash: '' } };
ctx.window = ctx; ctx.globalThis = ctx; ctx.DATA = input.data;
let result; ctx.out = v => { result = v; };
vm.createContext(ctx);
if (input.prelude) vm.runInContext(input.prelude, ctx, { filename: 'test-prelude' });
for (const f of input.files) vm.runInContext(fs.readFileSync(path.join(input.www, f), 'utf8'), ctx, { filename: f });
Promise.resolve(vm.runInContext('(async () => {' + input.script + '\n})()', ctx, { filename: 'test-script' }))
  .then(() => { process.stdout.write(JSON.stringify(result === undefined ? null : result)); process.exit(0); },
        e => { process.stderr.write(String(e && e.stack || e)); process.exit(1); });
"""


def run(files, script, data=None, prelude=None):
    node = shutil.which('node')
    if not node:
        pytest.fail('node 가 없어 포털 화면 JS 를 돌리지 못했다 — 개발 PC에 Node.js 를 설치하고 PATH 에 둔다', pytrace=False)
    proc = subprocess.run([node, '-e', LOADER], input=json.dumps({'www': str(WWW), 'files': files, 'script': script, 'data': data, 'prelude': prelude}),
                          capture_output=True, text=True, encoding='utf-8', timeout=60)
    if proc.returncode:
        pytest.fail(f'포털 JS 실행 실패({", ".join(files)}):\n{proc.stderr[-3000:]}', pytrace=False)
    return json.loads(proc.stdout)


PAGE_DOM_JS = r"""
const TREE = %s;
class El {
  constructor(tag, attrs = {}) {
    this.tagName = tag.toUpperCase(); this.children = []; this.parentElement = null; this.listeners = {};
    this.id = attrs.id || ''; this.dataset = {}; this.disabled = 'disabled' in attrs; this.open = 'open' in attrs;
    this.className = attrs.class || ''; this.textContent = attrs['#text'] || ''; this.innerHTML = ''; this.title = ''; this.files = [];
    this._value = attrs.value != null ? attrs.value : (this.tagName === 'TEXTAREA' ? (attrs['#text'] || '') : '');
    for (const [k, v] of Object.entries(attrs)) if (k.startsWith('data-')) this.dataset[k.slice(5).replace(/-([a-z])/g, (m, c) => c.toUpperCase())] = v;
  }
  get options() { return this.children.filter(c => c.tagName === 'OPTION'); }
  get value() {
    if (this.tagName !== 'SELECT') return this._value;
    const opts = this.options;
    return opts.some(o => o.value === this._value) ? this._value : (opts[0] ? opts[0].value : '');
  }
  set value(v) { this._value = String(v); }
  addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); }
  async fire(type, ev = {}) { for (const fn of this.listeners[type] || []) await fn({ target: this, ...ev }); }
  appendChild(c) { c.parentElement = this; this.children.push(c); return c; }
  append(...cs) { cs.forEach(c => this.appendChild(c)); }
  replaceChildren(...cs) { this.children = []; cs.forEach(c => this.appendChild(c)); }
  after(c) { const sib = this.parentElement.children; c.parentElement = this.parentElement; sib.splice(sib.indexOf(this) + 1, 0, c); }
  before(c) { const sib = this.parentElement.children; c.parentElement = this.parentElement; sib.splice(sib.indexOf(this), 0, c); }
  remove() { if (this.parentElement) { const sib = this.parentElement.children; sib.splice(sib.indexOf(this), 1); this.parentElement = null; } }
  setAttribute(k, v) { if (k.startsWith('data-')) this.dataset[k.slice(5).replace(/-([a-z])/g, (m, c) => c.toUpperCase())] = String(v); else this[k] = v; }
  hasAttribute(k) { return k.startsWith('data-') ? k.slice(5).replace(/-([a-z])/g, (m, c) => c.toUpperCase()) in this.dataset : k in this; }
  matches(sel) {
    const m = /^\[data-([a-z-]+)\]$/.exec(sel);
    if (m) return this.hasAttribute('data-' + m[1]);
    if (/^[a-z]+$/.test(sel)) return this.tagName === sel.toUpperCase();
    throw new Error('page_dom 대역이 모르는 선택자: ' + sel);
  }
  closest(sel) { for (let n = this; n; n = n.parentElement) if (n.matches(sel)) return n; return null; }
  *walk() { for (const c of this.children) { yield c; yield* c.walk(); } }
  querySelectorAll(sel) { return [...this.walk()].filter(n => n.matches(sel)); }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
}
function build(node) { const el = new El(node.tag, node.attrs); for (const c of node.children) el.appendChild(build(c)); return el; }
const root = build(TREE);
const byId = id => { for (const n of root.walk()) if (n.id === id) return n; return null; };
const fetched = [];
globalThis.document = { readyState: 'loading', body: root, documentElement: root, addEventListener() {},
  getElementById: byId, createElement: tag => new El(tag), querySelector: s => root.querySelector(s), querySelectorAll: s => root.querySelectorAll(s) };
globalThis.FETCHED = fetched;
globalThis.fetch = url => { fetched.push(String(url)); return Promise.reject(new Error('fetch 없음(시험 문맥)')); };
"""


def page_dom():
    """index.html 의 body 요소 나무를 JSON 으로 읽어 PAGE_DOM_JS 에 싣는다(글 · 주석은 textarea · option 의 글만)."""
    from html.parser import HTMLParser
    void = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr'}

    class Tree(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.root = {'tag': 'body', 'attrs': {}, 'children': []}
            self.stack = [self.root]

        def handle_starttag(self, tag, attrs):
            node = {'tag': tag, 'attrs': {k: (v if v is not None else '') for k, v in attrs}, 'children': []}
            if tag in ('html', 'head', 'body'):
                return
            self.stack[-1]['children'].append(node)
            if tag not in void:
                self.stack.append(node)

        def handle_endtag(self, tag):
            if tag in ('html', 'head', 'body') or tag in void:
                return
            for i in range(len(self.stack) - 1, 0, -1):
                if self.stack[i]['tag'] == tag:
                    del self.stack[i:]
                    return

        def handle_data(self, data):
            top = self.stack[-1]
            if top['tag'] in ('textarea', 'option', 'button', 'span', 'label', 'summary', 'h4'):
                top['attrs']['#text'] = top['attrs'].get('#text', '') + data

    t = Tree()
    t.feed((WWW / 'index.html').read_text(encoding='utf-8'))
    return PAGE_DOM_JS % json.dumps(t.root, ensure_ascii=False)
