/* 안내형 재생 모드 — 온라인 학생이 AI 키 · 설비 접근 없이 강사가 확정한 실습 경로를 포털에서 직접 따라 한다.
   계약: 문서/시스템/참조/재생모드.md

   켜는 법(주소 뒤 쿼리):
     ?replay=<사례 id>         재생. 포털이 서비스로 보내는 모든 요청(fetch · EventSource · iframe · 링크 · 새 창)을 이 파일이 받는다.
                               읽기(GET)는 녹화한 응답으로, 쓰기(POST 등)는 안내서가 정한 다음 행동일 때만 녹화한 응답으로 답한다.
                               네트워크로는 같은 출처의 정적 파일만 나간다. AI 호출 · 설비 명령은 생기지 않는다.
     ?replay-record=<사례 id>  강사 녹화. 실제 스택에 붙은 포털에서 요청 · 응답을 그대로 기록해 내려받는다.
   둘 다 없으면 아무것도 바꾸지 않는다 — 실제 실행 경로는 이 파일이 있어도 그대로다.

   이 파일은 다른 포털 스크립트보다 먼저 읽혀야 한다(index.html 에서 ui.js 앞). */
(() => {
  'use strict';
  const params = new URLSearchParams(location.search);
  const replayId = params.get('replay');
  const recordId = params.get('replay-record');
  if (!replayId && !recordId) { if (params.get('live') !== '1') defaultToReplay(); return; }

  /* 키 없는 학생의 기본은 재생이다(문서/시스템/2_기준.md 12절). 주소에 쿼리 없이 연 포털이 실제 실행을 할 수 없으면
     경고와 함께 사례 고르기(재생)로 옮긴다. 실제 실행이 되는 배포는 그대로 연다:
       - 서비스가 답하지 않는다(네트워크 오류)            → 재생으로(「실습 서비스에 연결할 수 없음」)
       - 처리 건 방식이 아니거나 내장 판단(AGENT_BRIDGE=legacy) → 그대로(키 없이 도는 기존 실행)
       - 워커 경로(AGENT_BRIDGE=off)인데 워커가 안 닿는다     → 재생으로(「AI 키(워커) 연결 없음」)
       - 서비스가 오류로 답하는 등 판단할 수 없으면           → 그대로(실제 실행을 막지 않는다)
     ?live=1 이면 확인하지 않고 실제 실행으로 연다(재생 화면의 「그래도 실제 실행으로 열기」). */
  async function defaultToReplay() {
    const moved = {};
    String(window.HYD_PORTS_RAW || '').split(/\s+/).filter(Boolean).forEach(kv => { const [a, b] = kv.split('=').map(Number); if (a && b) moved[a] = b; });
    const proc = `http://${location.hostname || 'localhost'}:${moved[8080] || 8080}`;
    const get = async path => {
      const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), 4000);
      try { return await window.fetch(proc + path, { cache: 'no-store', signal: ctl.signal }); } finally { clearTimeout(timer); }
    };
    let reason = null;
    try {
      const r = await get('/api/process/mode');
      if (!r.ok) return;
      const mode = await r.json();
      if (mode.mode !== 'instance' || mode.agent_bridge !== 'off') return;
      const w = await get('/api/agents/status');
      if (!w.ok) return;
      if ((await w.json()).reachable) return;
      reason = 'worker';
    } catch (e) {
      if (e && e.name === 'SyntaxError') return;   // JSON 이 아닌 답: 판단하지 않는다
      reason = 'service';
    }
    location.replace(new URL(`replay/index.html?from=${reason}`, location.href).href);
  }
  const MODE = replayId ? 'replay' : 'record';
  const CASE_ID = replayId || recordId;
  if (!/^[a-z0-9][a-z0-9-]{1,80}$/.test(CASE_ID)) { document.addEventListener('DOMContentLoaded', () => fatal(`사례 이름이 올바르지 않습니다: ${CASE_ID}`)); return; }

  const RealDate = Date, realFetch = window.fetch.bind(window), RealES = window.EventSource;
  const realLocal = (() => { try { return window.localStorage; } catch (_) { return null; } })();
  const realSession = (() => { try { return window.sessionStorage; } catch (_) { return null; } })();
  const BASE = new URL('replay/', location.href);

  /* ------------------------------------------------------------------ 요청 → 녹화 키 */
  // 포털은 서비스마다 호스트 포트를 직접 부른다(layers.js P()). 녹화 키는 호스트와 바뀐 포트에 상관없이 「서비스 이름 + 경로 + 정렬한 쿼리」다.
  const SERVICES = { 8000: 'plant', 8090: 'gateway', 8092: 'detector', 8091: 'agent', 8080: 'process', 3000: 'grafana', 7474: 'neo4j',
    8095: 'enterprise', 8093: 'ingest', 8094: 'sink', 1881: 'fuxa', 9090: 'prometheus', 8085: 'console', 9644: 'redpanda',
    18083: 'emqx', 8199: 'enterprise-mcp', 8198: 'dmn-mcp', 8097: 'worker', 8098: 'worker2' };
  const MOVED = {};   // 이 PC에서 옮긴 바깥 포트 → 원래 포트(nginx 가 넣는 HYD_PORTS_RAW)
  String(window.HYD_PORTS_RAW || '').split(/\s+/).filter(Boolean).forEach(kv => { const [a, b] = kv.split('=').map(Number); if (a && b) MOVED[b] = a; });
  const LOCAL_HOSTS = new Set([location.hostname, 'localhost', '127.0.0.1']);
  const VOLATILE = new Set(['since', '_', 't', 'ts', 'now', 'from', 'to']);
  function classify(raw) {
    let u; try { u = new URL(String(raw), location.href); } catch (_) { return { kind: 'external', origin: String(raw) }; }
    if (u.protocol === 'data:' || u.protocol === 'blob:' || u.protocol === 'about:') return { kind: 'static', url: u };
    const query = [...u.searchParams.entries()].sort((a, b) => (a[0] + '=' + a[1]).localeCompare(b[0] + '=' + b[1]));
    const qs = query.length ? '?' + query.map(([k, v]) => `${k}=${v}`).join('&') : '';
    const loose = query.filter(([k]) => !VOLATILE.has(k));
    const lqs = loose.length ? '?' + loose.map(([k, v]) => `${k}=${v}`).join('&') : '';
    if (u.origin === location.origin) {
      if (!u.pathname.startsWith('/api/')) return { kind: 'static', url: u };
      return { kind: 'api', url: u, service: 'portal', path: u.pathname, key: 'portal' + u.pathname + qs, loose: 'portal' + u.pathname + lqs, volatile: loose.length !== query.length };
    }
    const port = Number(u.port || (u.protocol === 'https:' ? 443 : 80));
    const service = SERVICES[MOVED[port] || port];
    if (!service || !LOCAL_HOSTS.has(u.hostname)) return { kind: 'external', origin: u.origin, url: u };
    return { kind: 'api', url: u, service, path: u.pathname, key: service + u.pathname + qs, loose: service + u.pathname + lqs, volatile: loose.length !== query.length };
  }
  // 짧은 내용 해시(cyrb53) — 같은 응답 본문을 한 번만 저장한다
  function hash(str) {
    let h1 = 0xdeadbeef, h2 = 0x41c6ce57;
    for (let i = 0; i < str.length; i++) { const c = str.charCodeAt(i); h1 = Math.imul(h1 ^ c, 2654435761); h2 = Math.imul(h2 ^ c, 1597334677); }
    h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);
    h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
    return (4294967296 * (2097151 & h2) + (h1 >>> 0)).toString(36);
  }
  // 녹화 당시와 지금의 포털 판본을 견주는 표(스크립트 · 스타일 파일과 그 ?v= 꼬리표). replay* 파일은 뺀다
  function portalFingerprint() {
    const list = [...document.querySelectorAll('script[src],link[rel="stylesheet"][href]')]
      .map(n => n.getAttribute('src') || n.getAttribute('href')).filter(s => !/(^|\/)replay[^/]*$/.test(s.split('?')[0]));
    return hash(list.join('\n'));
  }
  const bodyText = body => body == null ? '' : typeof body === 'string' ? body : (body instanceof URLSearchParams ? body.toString() : '');
  const jsonResponse = (status, obj) => new Response(JSON.stringify(obj), { status, headers: { 'Content-Type': 'application/json' } });

  /* ------------------------------------------------------------------ 안내 카드 공용(녹화 · 재생) */
  const PANEL_CSS = `.replay-panel{position:fixed;right:var(--s4,16px);bottom:var(--s4,16px);z-index:1000;width:min(380px,calc(100vw - 32px));max-height:calc(100vh - 32px);overflow:auto;box-shadow:0 8px 28px rgba(24,36,59,.18);border-color:var(--warn,#a86b06)}
.replay-head{display:flex;gap:var(--s2,8px);align-items:center}.replay-head strong{font-size:14px}
.replay-sub,.replay-meta,.replay-count,.replay-clock{margin:0;color:var(--ink-3,#65748b);font-size:12px}
.replay-step h3{margin:4px 0;font-size:15px}.replay-step p{margin:0 0 4px}.replay-input{font-weight:600}
.replay-actions{display:flex;flex-wrap:wrap;gap:var(--s2,8px)}.replay-msg{margin:0;font-size:13px}.replay-msg:empty{display:none}
.replay-msg.tone-info{color:var(--chip-accent-fg,#184f95);background:var(--chip-accent-bg,#cde2fb);padding:6px 8px;border-radius:var(--radius-sm,8px)}
.replay-msg.tone-warn{color:var(--chip-warning-fg,#734500);background:var(--chip-warning-bg,#f9dca4);padding:6px 8px;border-radius:var(--radius-sm,8px)}
.replay-dl{display:grid;grid-template-columns:auto 1fr;gap:2px 8px;font-size:12px;margin:8px 0}.replay-dl dt{color:var(--ink-3,#65748b)}.replay-dl dd{margin:0}
.replay-panel.collapsed .replay-sub,.replay-panel.collapsed .replay-body{display:none}
@media (max-width:720px){.replay-panel{left:8px;right:8px;bottom:8px;width:auto;max-height:45vh}}`;
  function panelShell(title, sub) {
    if (!document.getElementById('replayStyle')) { const st = document.createElement('style'); st.id = 'replayStyle'; st.textContent = PANEL_CSS; document.head.append(st); }
    const box = document.createElement('aside'); box.className = 'replay-panel card'; box.setAttribute('aria-label', '재생 안내');
    box.innerHTML = `<div class="replay-head"><span class="chip tone-warning sm">${MODE === 'replay' ? '재생 모드' : '녹화 모드'}</span><strong>${esc(title)}</strong></div><p class="replay-sub">${esc(sub)}</p>`;
    const body = document.createElement('div'); body.className = 'replay-body';
    const actions = document.createElement('div'); actions.className = 'replay-actions';
    box.append(body, actions); document.body.append(box);
    const badge = document.querySelector('.env-badge'); if (badge) { badge.textContent = MODE === 'replay' ? '재생 모드 · 저장된 기록' : '녹화 중'; badge.title = '실제 설비 · AI 와 연결하지 않은 상태입니다'; }
    return { box, body, actions };
  }
  function button(label, tone, fn) { const b = document.createElement('button'); b.type = 'button'; b.className = 'btn small' + (tone ? ' ' + tone : ''); b.textContent = label; b.addEventListener('click', fn); return b; }
  const esc = s => String(s ?? '').replace(/[&<>"]/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch]));
  const mmss = ms => { const s = Math.max(0, Math.round(ms / 1000)); return `${Math.floor(s / 60)}분 ${s % 60}초`; };

  /* ================================================================== 녹화 */
  if (MODE === 'record') {
    const REC = { format: 'hyd-replay-recording/1', case: CASE_ID, started_wall: RealDate.now(), frames: {}, bodies: {}, writes: [], streams: {}, urls: {} };
    const t = () => RealDate.now() - REC.started_wall;
    const lastPortalFetch = {};
    const keepBody = text => { const h = hash(text); if (!(h in REC.bodies)) REC.bodies[h] = text; return h; };
    function addFrame(key, status, text, opaque) {
      const list = REC.frames[key] || (REC.frames[key] = []);
      const h = opaque ? null : keepBody(text);
      const last = list[list.length - 1];
      if (last && last[1] === status && last[2] === h) return;
      list.push([t(), status, h]);
    }
    window.fetch = async function (input, init = {}) {
      const url = typeof input === 'string' || input instanceof URL ? String(input) : input.url;
      const method = String(init.method || (typeof input === 'object' && input.method) || 'GET').toUpperCase();
      const c = classify(url);
      if (c.kind !== 'api') return realFetch(input, init);
      const tReq = t();
      const res = await realFetch(input, init);
      const opaque = res.type === 'opaque';
      const text = opaque ? '' : await res.clone().text();
      if (method === 'GET') {
        REC.urls[c.key] = { url, opaque, volatile: c.volatile }; lastPortalFetch[c.key] = RealDate.now();
        addFrame(c.key, opaque ? 200 : res.status, text, opaque);
      } else {
        REC.writes.push({ t_req: tReq, t_res: t(), method, key: c.key, request: bodyText(init.body), status: res.status, response: keepBody(text) });
      }
      return res;
    };
    // 포털이 그 화면을 떠나도 한 번 본 읽기는 2초마다 다시 읽어 둔다 — 학생이 강사와 다른 때 다른 화면을 열어도 그 시점의 응답이 있게
    setInterval(() => {
      for (const [key, info] of Object.entries(REC.urls)) {
        if (info.opaque || info.volatile || RealDate.now() - (lastPortalFetch[key] || 0) < 1800) continue;
        lastPortalFetch[key] = RealDate.now();
        realFetch(info.url, { cache: 'no-store' }).then(async r => addFrame(key, r.status, await r.text(), false)).catch(() => {});
      }
    }, 2000);
    if (RealES) {
      window.EventSource = class extends RealES {
        constructor(url, opts) {
          super(url, opts);
          const c = classify(url), key = c.kind === 'api' ? c.loose : String(url), seen = new WeakSet();
          const log = ev => { if (seen.has(ev)) return; seen.add(ev); (REC.streams[key] || (REC.streams[key] = [])).push([t(), ev.type, ev.data, ev.lastEventId || '']); };
          super.addEventListener('message', log);
          this.__log = log;
        }
        addEventListener(type, fn, o) { if (type !== 'message' && type !== 'open' && type !== 'error') super.addEventListener(type, this.__log); return super.addEventListener(type, fn, o); }
      };
    }
    window.hydReplay = {
      mode: 'record',
      exportRecording: () => ({ ...REC, ended_wall: RealDate.now(), portal_fingerprint: portalFingerprint() }),
    };
    const download = () => {
      const blob = new Blob([JSON.stringify(window.hydReplay.exportRecording())], { type: 'application/json' });
      const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `${CASE_ID}.recording.json`; a.click();
    };
    window.hydReplay.save = download;
    // 실습 영상 촬영과 같은 실행을 녹화할 때(&quiet=1)는 화면에 아무것도 띄우지 않는다. 끝나면 Ctrl+Shift+S 로 녹화 파일을 내려받는다
    document.addEventListener('keydown', e => { if (e.ctrlKey && e.shiftKey && (e.key === 'S' || e.key === 's')) { e.preventDefault(); download(); } });
    if (params.get('quiet') === '1') return;
    document.addEventListener('DOMContentLoaded', () => {
      const box = panelShell('녹화 중', `사례 ${CASE_ID} · 실제 스택에 붙어 요청과 응답을 기록합니다. 안내서에 적은 행동만 순서대로 하세요. 끝나면 [녹화 저장](또는 Ctrl+Shift+S).`);
      const stat = document.createElement('p'); stat.className = 'replay-meta'; box.body.append(stat);
      box.actions.append(button('녹화 저장', 'primary', download));
      setInterval(() => { stat.textContent = `경과 ${Math.round(t() / 1000)}초 · 읽기 ${Object.keys(REC.frames).length}종 · 쓰기 ${REC.writes.length}건`; }, 1000);
    });
    return;
  }

  /* ================================================================== 재생 */
  const KEY = s => `hyd.replay:${CASE_ID}:${s}`;
  // 사례마다 포털의 브라우저 저장소를 따로 둔다 — 다른 사례 · 실제 실행의 저장 값과 섞이지 않는다
  function namespaced(real, prefix) {
    if (!real) return real;
    const keys = () => { const out = []; for (let i = 0; i < real.length; i++) { const k = real.key(i); if (k && k.startsWith(prefix)) out.push(k.slice(prefix.length)); } return out; };
    const api = {
      getItem: k => real.getItem(prefix + k), setItem: (k, v) => real.setItem(prefix + k, String(v)), removeItem: k => real.removeItem(prefix + k),
      clear: () => keys().forEach(k => real.removeItem(prefix + k)), key: i => keys()[i] ?? null, get length() { return keys().length; },
    };
    return new Proxy(api, {
      ownKeys: () => keys(),
      getOwnPropertyDescriptor: (target, k) => (typeof k === 'string' && !(k in target) && real.getItem(prefix + k) !== null)
        ? { enumerable: true, configurable: true, writable: true, value: real.getItem(prefix + k) } : Reflect.getOwnPropertyDescriptor(target, k),
      get: (target, k) => (k in target) ? target[k] : (typeof k === 'string' ? (real.getItem(prefix + k) ?? undefined) : undefined),
    });
  }
  try {
    Object.defineProperty(window, 'localStorage', { configurable: true, value: namespaced(realLocal, KEY('ls:')) });
    Object.defineProperty(window, 'sessionStorage', { configurable: true, value: namespaced(realSession, KEY('ss:')) });
  } catch (e) { document.addEventListener('DOMContentLoaded', () => fatal('브라우저 저장소를 사례별로 나눌 수 없어 재생을 멈췄습니다: ' + e.message)); }
  const store = {
    get: k => { try { return JSON.parse(realLocal.getItem(KEY(k)) || 'null'); } catch (_) { return null; } },
    set: (k, v) => { try { realLocal.setItem(KEY(k), JSON.stringify(v)); } catch (_) { /* 이 탭 안에서는 메모리로 계속 */ } },
  };
  function clearCase(id) {
    for (const s of [realLocal, realSession]) {
      if (!s) continue;
      const doomed = []; for (let i = 0; i < s.length; i++) { const k = s.key(i); if (k && k.startsWith(`hyd.replay:${id}:`)) doomed.push(k); }
      doomed.forEach(k => s.removeItem(k));
    }
  }

  const R = { ready: null, rec: null, guide: null, prog: null, blocked: [], misses: {}, error: '' };
  // 진행: done = 끝낸 녹화 행동 수, base = 그 행동 직후의 녹화 시각(ms), wall = 그 순간의 실제 시각, item = 안내 항목 위치
  const fresh = () => ({ done: 0, base: 0, wall: RealDate.now(), item: 0, skipped: 0 });
  function cap() { const next = R.rec.actions[R.prog.done]; return next ? next.t_req - 1 : R.rec.duration; }
  function vt() { return Math.max(0, Math.min(R.prog.base + (RealDate.now() - R.prog.wall), cap())); }
  function save() { store.set('progress', R.prog); }

  // 화면 시계도 녹화 시각을 따른다(남은 기한 · 경과 시간이 녹화 당시와 같게)
  class ReplayDate extends RealDate {
    constructor(...a) { if (a.length === 0 && R.rec) super(R.rec.started_wall + vt()); else super(...a); }
    static now() { return R.rec ? R.rec.started_wall + vt() : RealDate.now(); }
  }
  window.Date = ReplayDate;

  R.ready = (async () => {
    const getJSON = async path => {
      const r = await realFetch(new URL(path, BASE), { cache: 'no-store' });
      if (!r.ok) throw new Error(`${path} 를 읽지 못했습니다(${r.status})`);
      if (!path.endsWith('.gz')) return r.json();
      // 녹화는 gzip 으로 둔다(scripts/replay_case.py). 서버가 이미 풀어 준 경우(Content-Encoding)는 그대로 읽는다
      const buf = new Uint8Array(await r.arrayBuffer());
      if (buf[0] !== 0x1f || buf[1] !== 0x8b) return JSON.parse(new TextDecoder().decode(buf));
      if (typeof DecompressionStream !== 'function') throw new Error('이 브라우저는 녹화 파일(gzip)을 풀 수 없습니다. 최신 Chrome · Edge · Firefox · Safari 로 여세요');
      return new Response(new Blob([buf]).stream().pipeThrough(new DecompressionStream('gzip'))).json();
    };
    const index = await getJSON('cases.json');
    const entry = (index.cases || []).find(c => c.id === CASE_ID);
    if (!entry) throw new Error(`재생 사례 목록(replay/cases.json)에 「${CASE_ID}」가 없습니다`);
    const [guide, rec] = await Promise.all([getJSON(entry.guide), getJSON(entry.recording)]);
    const problems = checkPair(guide, rec);
    if (problems.length) throw new Error('안내서와 녹화가 맞지 않습니다 — ' + problems.join(' / '));
    R.entry = entry; R.guide = guide; R.rec = rec;
    const saved = store.get('progress');
    R.prog = saved && saved.recording === rec.id ? saved : { ...fresh(), recording: rec.id };
    save();
  })();
  R.ready.catch(e => { R.error = e.message; });

  // 안내서의 행동 항목과 녹화의 행동이 같은 순서 · 같은 요청인지(빌드 도구 scripts/replay_case.py 와 같은 검사)
  function checkPair(guide, rec) {
    const out = [];
    if (guide.recording !== rec.id) out.push(`안내서가 가리키는 녹화 ${guide.recording} ≠ 녹화 ${rec.id}`);
    const acts = guide.items.filter(i => i.kind === 'action');
    if (acts.length !== rec.actions.length) out.push(`행동 수 ${acts.length} ≠ 녹화 행동 수 ${rec.actions.length}`);
    acts.forEach((g, n) => { const a = rec.actions[n]; if (a && (a.method !== g.match.method || !new RegExp('^' + g.match.key + '$').test(a.key))) out.push(`${n + 1}번째 행동 ${g.match.method} ${g.match.key} ≠ 녹화 ${a.method} ${a.key}`); });
    return out;
  }
  function frameAt(c) {
    const pick = list => { if (!list || !list.length) return null; let f = null; const v = vt(); for (const x of list) { if (x[0] <= v) f = x; else break; } return f || (list[0][0] <= cap() ? list[0] : null); };
    let f = pick(R.rec.frames[c.key]);
    if (!f && c.loose !== c.key) { for (const [k, list] of Object.entries(R.rec.frames)) if (k.split('?')[0] === c.key.split('?')[0] && looseOf(k) === c.loose) { f = pick(list); if (f) break; } }
    return f;
  }
  const looseOf = k => { const [p, q] = k.split('?'); if (!q) return k; const kept = q.split('&').filter(kv => !VOLATILE.has(kv.split('=')[0])); return kept.length ? p + '?' + kept.join('&') : p; };
  const bodyOf = h => h == null ? '' : R.rec.bodies[h];

  function deepSubset(want, got) {
    if (want === null || typeof want !== 'object') return want === got;
    if (got === null || typeof got !== 'object') return false;
    return Object.entries(want).every(([k, v]) => deepSubset(v, got[k]));
  }
  function currentAction() {
    const acts = R.guide.items.map((it, i) => ({ it, i })).filter(x => x.it.kind === 'action');
    return acts[R.prog.done] || null;
  }
  function writeAllowed(c, method) {
    return (R.guide.allow || []).some(a => a.method === method && new RegExp('^' + a.key + '$').test(c.key));
  }
  function refuse(message) { note(message, 'warn'); return jsonResponse(409, { detail: '재생 모드: ' + message, replay: true }); }

  async function answer(c, method, text) {
    await R.ready;
    if (method === 'GET' || method === 'HEAD') {
      const f = frameAt(c);
      if (!f) { R.misses[c.key] = (R.misses[c.key] || 0) + 1; render(); return jsonResponse(404, { detail: '재생 모드: 이 화면의 응답은 이 사례의 녹화에 없습니다. 안내된 화면으로 돌아가세요.', replay: true }); }
      return new Response(bodyOf(f[2]), { status: f[1], headers: { 'Content-Type': 'application/json' } });
    }
    const next = currentAction();
    const expected = next && R.rec.actions[R.prog.done];
    if (expected && expected.method === method && expected.key === c.key) {
      let got = null; try { got = text ? JSON.parse(text) : {}; } catch (_) { got = null; }
      if (next.it.match.body && !deepSubset(next.it.match.body, got)) return refuse(`정해진 입력과 다릅니다. 이 사례는 강사가 정한 입력만 받습니다 — ${next.it.input || next.it.title}`);
      // 자유 글 칸(질문에 대한 답 · 사유 등, 안내서 match.free)은 어떤 글이든 받는다. 다만 이어지는 결과는 강사가 쓴 글로 녹화된 것임을 알린다
      const free = next.it.match.free || [];
      if (free.some(f => !String((got || {})[f] ?? '').trim())) return refuse('빈칸이 있습니다. 글을 적은 뒤 다시 누르세요.');
      R.prog.done += 1; R.prog.base = expected.t_res; R.prog.wall = RealDate.now(); R.prog.item = Math.max(R.prog.item, next.i + 1); save(); render();
      if (free.length) {
        let said = {}; try { said = JSON.parse(expected.request || '{}'); } catch (_) { /* 녹화 본문이 JSON 이 아니면 원문 없이 알린다 */ }
        note(`적은 글은 받았습니다. 다만 이어지는 결과는 강사가 쓴 「${free.map(f => said[f] ?? '').join(' / ')}」로 녹화된 것이고, 지금 AI가 내 글을 읽고 답한 것이 아닙니다. 내 글로 직접 해 보려면 실제 실행(본인 키)으로 하세요.`, 'info');
      }
      return new Response(bodyOf(expected.response), { status: expected.status, headers: { 'Content-Type': 'application/json' } });
    }
    if (writeAllowed(c, method)) {
      const prior = R.rec.writes.filter(w => w.method === method && w.key === c.key);
      const w = prior.filter(x => x.t_req <= vt()).pop() || prior[0];
      if (w) return new Response(bodyOf(w.response), { status: w.status, headers: { 'Content-Type': 'application/json' } });
    }
    if (!next) return refuse('이 사례의 안내된 행동을 모두 마쳤습니다. 처음부터 다시 하려면 재생 안내의 「처음부터 다시 하기」를 누르세요.');
    return refuse(`지금 할 행동은 「${next.it.title}」입니다. 안내 순서 밖의 조작은 녹화에 없어 재생하지 않습니다(바뀐 것 없음). 다른 조작을 직접 해 보려면 실제 실행(본인 키)으로 하세요.`);
  }

  window.fetch = async function (input, init = {}) {
    const url = typeof input === 'string' || input instanceof URL ? String(input) : input.url;
    const method = String(init.method || (typeof input === 'object' && input.method) || 'GET').toUpperCase();
    const c = classify(url);
    if (c.kind === 'static') return realFetch(input, init);
    if (c.kind === 'external') { block(c.origin, 'fetch'); throw new TypeError('재생 모드: 외부 호출을 막았습니다'); }
    if (init.mode === 'no-cors') { await R.ready; return new Response(null, { status: 200 }); }   // 상태 점 확인(불투명 응답)
    return answer(c, method, bodyText(init.body));
  };
  function block(what, how) { R.blocked.push({ what: String(what), how, at: RealDate.now() }); render(); }

  // 실시간 이벤트(SSE): 녹화한 이벤트를 녹화 시각에 맞춰 흘린다
  class ReplayES extends EventTarget {
    constructor(url) {
      super(); this.url = String(url); this.readyState = 0; this.withCredentials = false; this.onopen = this.onmessage = this.onerror = null;
      const c = classify(url);
      if (c.kind !== 'api') { block(c.origin || url, 'EventSource'); setTimeout(() => { this.readyState = 2; this._emit('error', {}); }, 0); return; }
      this._key = c.loose; this._sent = 0;
      R.ready.then(() => {
        if (this.readyState === 2) return;
        this._list = R.rec.streams[this._key] || [];
        this.readyState = 1; this._emit('open', {}); this._tick(); this._timer = setInterval(() => this._tick(), 500);
      }, () => { this.readyState = 2; this._emit('error', {}); });
    }
    _tick() { const v = vt(); while (this._sent < this._list.length && this._list[this._sent][0] <= v) { const [, type, data, id] = this._list[this._sent++]; this._emit(type, { data, lastEventId: id }); } }
    _emit(type, init) {
      const ev = type === 'open' || type === 'error' ? new Event(type) : new MessageEvent(type, init);
      const h = this['on' + type]; if (typeof h === 'function') h.call(this, ev);
      this.dispatchEvent(ev);
    }
    close() { this.readyState = 2; clearInterval(this._timer); }
  }
  ReplayES.CONNECTING = 0; ReplayES.OPEN = 1; ReplayES.CLOSED = 2;
  window.EventSource = ReplayES;
  window.WebSocket = class { constructor(url) { block(url, 'WebSocket'); throw new Error('재생 모드: 실시간 소켓은 쓰지 않습니다'); } };
  const realXhrOpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (method, url, ...rest) {
    if (classify(url).kind !== 'static') { block(url, 'XMLHttpRequest'); throw new Error('재생 모드: 이 요청은 재생하지 않습니다'); }
    return realXhrOpen.call(this, method, url, ...rest);
  };
  if (navigator.sendBeacon) { const realBeacon = navigator.sendBeacon.bind(navigator); navigator.sendBeacon = (url, data) => { if (classify(url).kind !== 'static') { block(url, 'sendBeacon'); return false; } return realBeacon(url, data); }; }
  const realOpen = window.open.bind(window);
  window.open = (url, ...rest) => { if (url && classify(url).kind !== 'static') { block(url, 'window.open'); note('재생 모드에서는 외부 도구 창을 열지 않습니다. 녹화된 포털 화면만 따라 합니다.', 'warn'); return null; } return realOpen(url, ...rest); };
  // 그래프(Grafana) 같은 바깥 화면 틀은 빈 안내로 바꾼다
  const srcDesc = Object.getOwnPropertyDescriptor(HTMLIFrameElement.prototype, 'src');
  Object.defineProperty(HTMLIFrameElement.prototype, 'src', {
    configurable: true, get() { return srcDesc.get.call(this); },
    set(v) {
      if (classify(v).kind === 'static') return srcDesc.set.call(this, v);
      block(v, 'iframe');
      this.srcdoc = '<p style="font:14px sans-serif;color:#4b5c73;padding:16px">재생 모드: 이 외부 화면(그래프 서비스)은 녹화하지 않았습니다. 같은 값은 포털의 다른 화면에서 확인합니다.</p>';
    },
  });
  document.addEventListener('click', e => {
    const a = e.target.closest && e.target.closest('a[href]'); if (!a) return;
    const href = a.getAttribute('href'); if (!href || href.startsWith('#')) return;
    if (classify(a.href).kind !== 'static') { e.preventDefault(); e.stopPropagation(); block(a.href, 'link'); note('재생 모드에서는 외부 도구 링크를 열지 않습니다.', 'warn'); }
  }, true);

  /* ------------------------------------------------------------------ 화면: 재생 안내 카드 */
  let P = null, lastNote = null;
  function note(text, tone) { lastNote = { text, tone, at: RealDate.now() }; render(); }
  function fatal(text) {
    const box = panelShell('재생을 시작하지 못했습니다', text);
    box.actions.append(button('사례 고르기', 'primary', () => { location.href = new URL('index.html', BASE).href; }));
  }
  function activeView() { const v = document.querySelector('.view.active'); return v ? v.id.replace(/^view-/, '') : ''; }
  function advanceSoft() {
    // 행동 항목은 포털에서 그 행동을 해야 넘어간다. 학생이 앞의 설명 · 화면 항목을 건너뛰고 행동을 했으면 그 행동 뒤로 옮긴다
    let moved = false;
    while (R.prog.item < R.guide.items.length) {
      const it = R.guide.items[R.prog.item];
      if (it.kind === 'action' && R.guide.items.slice(0, R.prog.item + 1).filter(x => x.kind === 'action').length <= R.prog.done) { R.prog.item += 1; moved = true; continue; }
      break;
    }
    if (moved) save();
  }
  function render() {
    if (MODE !== 'replay' || !document.body) return;
    if (R.error) { if (!P) { P = {}; fatal(R.error); } return; }
    if (!R.rec) return;
    if (!P) {
      P = panelShell(R.guide.title, `저장된 실행 기록을 다시 보여 줍니다. 지금 AI가 새로 추론하거나 설비에 명령을 보내지 않습니다.`);
      P.step = document.createElement('div'); P.step.className = 'replay-step'; P.body.append(P.step);
      P.msg = document.createElement('p'); P.msg.className = 'replay-msg'; P.msg.setAttribute('role', 'status'); P.body.append(P.msg);
      P.more = document.createElement('details'); P.more.className = 'fold replay-more'; P.body.append(P.more);
      P.box.classList.toggle('collapsed', !!store.get('collapsed'));
    }
    advanceSoft();
    const items = R.guide.items, it = items[R.prog.item], total = items.length;
    const v = vt(), c = cap();
    let html = it
      ? `<p class="replay-count">${R.prog.item + 1} / ${total} 단계 · ${esc(it.section || '')}</p><h3>${esc(it.title)}</h3><p>${esc(it.text)}</p>${it.input ? `<p class="replay-input">정해진 입력: ${esc(it.input)}</p>` : ''}`
      : `<p class="replay-count">${total} / ${total} 단계</p><h3>안내된 단계를 모두 마쳤습니다</h3><p>관찰 기록과 근거 연결표를 저장하세요. 다시 하려면 「처음부터 다시 하기」를 누르세요.</p>`;
    html += `<p class="replay-clock">녹화 시각 ${mmss(v)}${v < c ? ` · 다음 변화까지 녹화 ${mmss(c - v)}` : ' · 다음 행동을 기다리는 중'}</p>`;
    if (P.step.dataset.html !== html) { P.step.innerHTML = html; P.step.dataset.html = html; }
    // 버튼은 바뀔 때만 다시 만든다(1초마다 다시 그려도 포커스 · 클릭을 잃지 않게)
    const sig = [R.prog.item, it && it.kind, it && activeView() === it.view, v < c, P.box.classList.contains('collapsed')].join('|');
    if (P.actions.dataset.sig !== sig) {
      P.actions.dataset.sig = sig;
      P.actions.innerHTML = '';
      // 카드 하나에 주 행동 하나: 설명은 「확인했습니다」, 화면은 그 화면이 아니면 「열기」 · 그 화면이면 「확인했습니다」
      const confirm = () => button('확인했습니다', 'primary', () => { R.prog.item += 1; save(); render(); });
      if (it && it.kind === 'note') P.actions.append(confirm());
      if (it && it.kind === 'view') P.actions.append(activeView() === it.view ? confirm()
        : button(`「${it.view_label || it.view}」 화면 열기`, 'primary', () => { const b = document.querySelector(`.rail nav button[data-tab="${it.view}"]`); if (b) b.click(); setTimeout(render, 50); }));
      if (v < c) P.actions.append(button('기다리지 않고 넘기기', '', () => { R.prog.base = c; R.prog.wall = RealDate.now(); R.prog.skipped += 1; save(); render(); }));
      P.actions.append(button(P.box.classList.contains('collapsed') ? '안내 펼치기' : '안내 접기', 'outline', () => { const on = !P.box.classList.contains('collapsed'); P.box.classList.toggle('collapsed', on); store.set('collapsed', on); render(); }));
    }
    const recent = lastNote && RealDate.now() - lastNote.at < (lastNote.tone === 'info' ? 60000 : 15000) ? lastNote : null;
    P.msg.textContent = recent ? recent.text : ''; P.msg.className = 'replay-msg' + (recent ? ' tone-' + recent.tone : '');
    const missN = Object.values(R.misses).reduce((a, b) => a + b, 0);
    const lec = R.guide.lecture || {}, cond = R.rec.conditions || {};
    const fpNow = portalFingerprint(), fpOk = fpNow === R.rec.portal_fingerprint;
    const more = `<summary>판본 · 녹화 조건 · 다시 하기</summary>
      <dl class="replay-dl">
        <dt>강의</dt><dd>${esc((lec.courses || []).join(' · '))} ${esc(lec.session || '')} ${esc(lec.lab || '')}</dd>
        <dt>녹화</dt><dd>${esc(R.rec.recorded_at || '')} · 길이 ${mmss(R.rec.duration)} · 행동 ${R.rec.actions.length}건</dd>
        <dt>녹화 조건</dt><dd>${esc(cond.summary || '')}</dd>
        <dt>포털 판본</dt><dd>${fpOk ? '녹화 당시와 같음' : '<b>녹화 당시와 다름</b> — 화면이 녹화와 어긋날 수 있습니다. 강사에게 알리세요.'}</dd>
        <dt>외부 전송</dt><dd>0건 (막은 시도 ${R.blocked.length}건)</dd>
        <dt>녹화에 없는 화면 요청</dt><dd>${missN}건</dd>
      </dl>`;
    if (P.more.dataset.html !== more) { const open = P.more.open; P.more.innerHTML = more; P.more.dataset.html = more; P.more.open = open; P.more.append(P.resetRow || (P.resetRow = resetRow())); }
  }
  function resetRow() {
    const row = document.createElement('div'); row.className = 'replay-actions';
    row.append(button('처음부터 다시 하기', '', () => { clearCase(CASE_ID); location.reload(); }));
    row.append(button('사례 고르기', 'outline', () => { location.href = new URL('index.html', BASE).href; }));
    return row;
  }
  window.hydReplay = {
    mode: 'replay', caseId: CASE_ID, ready: () => R.ready, state: () => ({ done: R.prog && R.prog.done, item: R.prog && R.prog.item, vt: R.rec ? vt() : null, blocked: R.blocked.slice(), misses: { ...R.misses }, error: R.error }),
  };
  // 실시간 표시가 「연결됨」으로 읽혀 실제 서비스와 이어진 것처럼 보이지 않게, 재생 중에는 그 문구만 바꾼다(ui.js 의 문구 사전은 그대로)
  document.addEventListener('DOMContentLoaded', () => {
    if (typeof UI === 'undefined' || typeof UI.t !== 'function') return;
    const t = UI.t, words = { 'header.connected': '녹화 재생 중', 'header.waiting': '녹화 이벤트 기다리는 중', 'header.services': '녹화한 서비스' };
    UI.t = function (k, ...a) { return words[k] || t.call(this, k, ...a); };
  });
  const start = () => { R.ready.then(render, render); setInterval(render, 1000); };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
