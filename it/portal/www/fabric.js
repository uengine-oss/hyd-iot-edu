/* A11 데이터 패브릭 미니 — 업무 DB(Supabase ent)와 시계열 DB(TimescaleDB)를 읽기만 해서 설비 하나로 묶어 본다.
   window.hydFabric.mount(el). 차례(결론 먼저 · 근거 다음 · 원문 접기): 원천과 연결의 지금 상태(숫자 타일) → 보기 셋(묶어 보기 = 왼쪽 조건 · 오른쪽 결과, 원천과 표, 클래스 ↔ 표·열).
   색은 상태에만 쓴다 — 어느 원천인지는 글로 쓰고, 뱃지는 문제가 있는 상태에만 붙인다. 조회문(SQL)과 연결 정보는 접기 안에 있다. 화면 제목과 한 문장은 index.html 에, 배치는 screens.css 에 있다.
   API: process /api/fabric/* (procsvc/fabric_api.py) — 에이전트의 MCP 도구 hyd-dmn fabric_query 와 같은 함수다. 쓰기 버튼 없음. */
(function () {
  const S = { el: null, tab: 'join', sources: null, links: null, queries: [], errors: {}, result: null, resultError: '', busy: false,
              table: {}, sample: {}, asset: 'HYD-01', query: 'asset' };
  const KLASS = { Asset: '설비', Sensor: '센서', Actuator: '구동기 설정값', InputData: '판단 입력', Part: '부품', Supplier: '공급사' };
  const STATE = { OK: ['연결됨', 'success'], MISSING: ['원천에 없음', 'danger'], SOURCE_DOWN: ['원천 연결 실패', 'danger'],
    UNBOUND: ['표 · 열 미연결', 'warning'], DERIVED: ['계산으로 정하는 값', 'neutral'], OUTSIDE: ['DB에 없는 값(입력 · 계산)', 'neutral'], UNREGISTERED: ['등록 안 된 원천', 'danger'],
    NOT_ONE_ROW: ['설비마다 한 행이 아님', 'warning'], NO_DATA: ['기록 없음', 'warning'], TYPE_CHANGED: ['형식 바뀜', 'danger'], COMMENT_CHANGED: ['뜻 바뀜', 'warning'] };
  // 상태: 연결됨은 글로, 문제가 있는 상태만 칩으로(한 화면에 색 있는 칩이 줄줄이 서지 않게)
  const chip = (state) => { const [l, t] = STATE[state] || [state || '–', 'neutral']; return state === 'OK' ? esc(l) : UI.chipText(l, t); };
  const srcName = (id, label) => esc(label || id);
  const group = (label, body) => body ? `<h3>${label}</h3>${body}` : '';
  const table = (head, rows) => `<div class="table-container"><table class="table"><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table></div>`;
  const dot = tone => `<i class="dot"${tone ? ` data-tone="${tone}"` : ''}></i>`;
  const srcLabel = id => ((S.sources || []).find(s => s.id === id) || {}).label || id;   // 원천 이름은 서버(fabric.SOURCES) 한 곳
  const val = (v, unit) => v == null ? '<span class="muted">값 없음</span>' : `<b>${esc(typeof v === 'number' ? window.hydWords.num(v) : v)}</b>${unit ? ' ' + esc(unit) : ''}`;
  const code = (t) => t ? `<code class="inline">${esc(t)}</code>` : '';
  const when = (t) => t ? esc(UI.dateTime ? UI.dateTime(t) : t) : '';

  function rowsTable(columns, rows, max = 10) {
    if (!rows || !rows.length) return '<p class="muted">행이 없습니다.</p>';
    const body = rows.slice(0, max).map(r => `<tr>${r.map(v => `<td>${esc(v == null ? '' : typeof v === 'object' ? JSON.stringify(v) : v)}</td>`).join('')}</tr>`).join('');
    return table(columns.map(c => `<th>${esc(c)}</th>`).join(''), body) + (rows.length > max ? `<p class="muted">${rows.length}행 중 ${max}행을 보입니다.</p>` : '');
  }

  /* ---------- 지금 상태 ---------- */
  // 숫자 타일 한 줄: 원천마다 연결됐는지, 클래스가 표 · 열에 닿는지. 응답 전에는 읽는 중, 실제로 못 읽었을 때만 확인 실패
  // (화면을 열 때마다 0.1초씩 실패가 보였다 — 1회차 04 촬영 검토)
  function summary() {
    const tile = (tone, name, value, sub) => `<div class="stat"><div class="stat-label">${esc(name)}</div><div class="stat-value">${dot(tone)}${esc(value)}</div><div class="stat-note">${sub}</div></div>`;
    const tiles = (S.sources || []).map(s => tile(s.ok ? (s.read_only ? 'ok' : 'warn') : 'danger', `${s.label} · ${s.engine}`, s.ok ? '연결됨' : '연결 실패',
      s.ok ? `표 ${s.tables.length}개 · ${s.read_only ? '읽기 전용 확인됨' : '읽기 전용이 아님'}` : esc(s.reason)));
    if (!S.sources) tiles.push(S.errors.sources ? tile('danger', '원천', '확인 실패', esc(S.errors.sources)) : tile('', '원천', '읽는 중…', '업무 DB와 시계열 DB의 연결을 확인하고 있습니다'));
    const cls = S.links ? S.links.classes : [];
    const ok = cls.filter(c => c.state === 'OK').length;
    const unbound = S.links ? S.links.inputs.filter(i => i.state === 'UNBOUND').length : 0;
    tiles.push(S.links ? tile(S.links.graph.ok && ok === cls.length ? 'ok' : 'warn', '클래스 ↔ 표 · 열', `${ok} / ${cls.length} 연결됨`, S.links.graph.ok ? `판단 입력 중 표 · 열 미연결 ${unbound}개` : esc(S.links.graph.reason))
      : S.errors.links ? tile('danger', '클래스 ↔ 표 · 열', '확인 실패', esc(S.errors.links)) : tile('', '클래스 ↔ 표 · 열', '읽는 중…', '지식의 클래스와 원천의 표를 대조하고 있습니다'));
    return `<div class="stats fab-stats" aria-label="원천과 연결의 지금 상태">${tiles.join('')}</div>`;
  }

  /* ---------- 탭 1: 두 DB 묶어 보기 ---------- */
  function assetCodes() {
    const a = S.links && S.links.classes.find(c => c.klass === 'Asset' && c.source === 'hyd-enterprise');
    return a ? [...(a.matched || []), ...(a.unmatched || [])].map(m => m.key) : [];
  }
  // 왼쪽에 조건, 오른쪽에 결과(디자인 기준 5-6)
  function joinTab() {
    const opts = [['asset', '설비 하나로 두 원천 값 합치기'], ...S.queries.map(q => [q.id, q.title])];
    const q = S.queries.find(x => x.id === S.query);
    const form = `<div class="fab-in">` + UI.section('조건',
      UI.field({ label: '설비', input: `<input id="fabAsset" list="fabAssets" value="${esc(S.asset)}"><datalist id="fabAssets">${assetCodes().map(c => `<option value="${esc(c)}">`).join('')}</datalist>` }) +
      UI.field({ label: '질문', input: `<select id="fabQuery">${opts.map(([k, l]) => `<option value="${esc(k)}"${k === S.query ? ' selected' : ''}>${esc(l)}</option>`).join('')}</select>`,
                 error: S.errors.queries ? `준비된 질문 목록을 읽지 못했습니다 — ${S.errors.queries}` : '',
                 hint: q ? q.question : '업무 DB에서 설비 코드로 이어진 표와 시계열 DB의 태그별 최신값을, 어느 원천에서 왔는지와 함께 모읍니다' })) +
      `<footer class="form-foot"><button type="button" class="btn" id="fabRun"${S.busy ? ' disabled aria-busy="true"' : ''}>${S.busy ? '읽는 중…' : UI.icon('database') + '묶어 보기'}</button></footer>` +
      `<p class="muted">읽기 전용 계정으로만 조회합니다. 조회 한 번은 5초까지이고 행 수 제한이 있습니다. 이 화면에는 쓰는 단추가 없습니다.</p></div>`;
    return `<div class="fab-io">${form}<div class="fab-out" id="fabResult">${result()}</div></div>`;
  }
  // 결과의 차례: 무엇을 물었나(결론 한 문장) → 읽은 값 표 → 접기(실행한 조회문과 받은 행)
  function result() {
    if (S.resultError) return UI.errorBlock('조회하지 못했습니다', S.resultError);
    const r = S.result;
    if (!r) return UI.empty('아직 묶어 본 결과가 없습니다', '왼쪽에서 설비와 질문을 고르고 [묶어 보기]를 누르면, 두 DB에서 읽은 값이 어느 원천 · 표 · 열에서 왔는지와 함께 보입니다.');
    const down = Object.entries(r.sources || {}).filter(([, s]) => !s.ok);
    const warn = down.length ? `<div class="alert" data-variant="destructive" role="alert">${UI.icon('circle-alert')}<h2>일부 원천을 읽지 못했습니다</h2><section>${down.map(([id, s]) => `${esc(srcLabel(id))}: ${esc(s.reason)}`).join(' · ')}</section></div>` : '';
    const notes = (r.notes || []).map(n => `<p class="muted">${esc(n)}</p>`).join('');
    const answer = r.query === 'asset' ? assetAnswer(r) : table('<th>항목</th><th>값</th><th>원천</th><th>위치</th>',
      r.answer.map(a => `<tr><td>${esc(a.label)}</td><td>${a.value == null ? chip(a.state) + `<small>${esc(a.reason || '')}</small>` : val(a.value, a.unit)}</td>` +
        `<td>${srcName(a.source, a.source_label)}</td><td>${code(partTable(r, a))}${a.where ? `<small>${esc(a.where)}</small>` : ''}${a.at ? `<small>${when(a.at)}</small>` : ''}</td></tr>`).join(''));
    const parts = r.parts.map(p => group(`${srcName(p.source, p.source_label)} · ${esc(p.purpose)}`,
      (p.ok ? `<pre class="code">${esc(p.statement)}</pre>${Object.keys(p.params || {}).length ? `<p class="muted">조회 조건: ${Object.entries(p.params).map(([k, v]) => `${esc(window.hydWords.fieldName(k))} ${esc(v !== null && typeof v === 'object' ? JSON.stringify(v) : v)}`).join(' · ')}</p>` : ''}` +
              rowsTable(p.columns, p.rows) + (p.at_row_limit ? '<p class="muted">행 제한에 닿아 일부만 보입니다.</p>' : '')
            : `<p class="muted" data-tone="danger">${esc(p.reason)}</p><pre class="code">${esc(p.statement)}</pre>`))).join('');
    const used = [...new Set(r.parts.map(p => p.source))].map(id => srcLabel(id)).join(' · ');
    return `<div class="result"><div class="result-label">물은 것</div><div class="result-main">${esc(r.question || r.title)}</div>` +
      `<p class="result-sub">${esc(r.asset)} · ${when(r.at)} · 읽은 원천 ${esc(used)} · 조회마다 최대 ${r.row_limit}행${r.partial ? ' · 일부만 읽었습니다' : ''}</p></div>` +
      warn + notes + answer + UI.fold(`실행한 조회<span class="muted">SQL · 받은 행 · ${r.parts.length}개</span>`, parts);
  }
  function partTable(r, a) {
    const p = r.parts.find(x => x.id === a.part);
    const m = p && /from\s+([\w."]+)/i.exec(p.statement);
    return m ? m[1].replace(/"/g, '') + (a.column ? ' → ' + a.column : '') : a.column || '';
  }
  function assetAnswer(r) {
    const groups = [['hyd-enterprise', '업무 DB'], ['hyd-timeseries', '시계열 DB']];
    return groups.map(([id, label]) => {
      const rows = r.answer.filter(v => v.source === id);
      if (!rows.length) return group(label, `<p class="muted">${esc(r.sources[id] && !r.sources[id].ok ? r.sources[id].reason : '연결된 값이 없습니다.')}</p>`);
      return group(`${label} · 연결된 값 ${rows.length}개`, table('<th>클래스</th><th>항목</th><th>값</th><th>위치</th>',
        rows.map(v => `<tr><td>${esc(KLASS[v.klass] || '연결 없음')}</td><td>${esc(v.label)}${v.klass !== 'InputData' ? ` ${code(v.field)}` : ''}` +
          `${v.inputs && v.inputs.length ? `<small>판단 입력: ${esc(v.inputs.join(', '))}</small>` : ''}</td>` +
          `<td>${v.value == null ? chip(v.state) + `<small>${esc(v.reason || '')}</small>` : val(v.value, v.unit)}${v.anchor ? `<small>저장값 ${when(v.anchor)}</small>` : ''}</td>` +
          `<td>${code(v.from)}${v.where ? `<small>${esc(v.where)}</small>` : ''}${v.age_s != null ? `<small>${esc(v.age_s)}초 전</small>` : ''}</td></tr>`).join('')));
    }).join('');
  }

  /* ---------- 탭 2: 원천 · 표 · 샘플 ---------- */
  // 원천마다 판 하나: 이름과 한 줄 → 표 고르기(조각) → 고른 표의 열(뜻)과 최신 행 → 접기(조회문 · 연결 정보)
  function sourcesTab() {
    if (!S.sources) return S.errors.sources ? UI.errorBlock('원천 상태를 읽지 못했습니다', S.errors.sources) : UI.loading('');
    return S.sources.map(s => {
      const head = `<header class="panel-head"><div><h2>${esc(s.label)}${s.ok ? (s.read_only ? '' : UI.chipText('읽기 전용 아님', 'danger')) : UI.chipText('연결 실패', 'danger')}</h2>` +
        `<p>${esc([s.about, s.engine, s.ok && s.read_only ? '읽기 전용' : ''].filter(Boolean).join(' · '))}</p></div></header>`;
      if (!s.ok) return `<section class="panel">${head}<div class="panel-sec">${UI.errorBlock('이 원천에 연결하지 못했습니다', s.reason)}${UI.fold('오류 원문', `<pre class="code">${esc(s.detail)}</pre>`)}</div></section>`;
      const picked = S.table[s.id];
      const list = `<div class="chips fab-picks" role="group" aria-label="${esc(s.label)}의 표">${s.tables.map(t => `<button type="button" class="chip" aria-pressed="${t.name === picked}" data-fab-table="${esc(s.id)}|${esc(t.name)}">${esc(t.name)}</button>`).join('')}</div>`;
      const sm = picked ? S.sample[s.id + '|' + picked] : null;
      const more = (sm && sm.statement ? group('최신 행을 읽은 조회문', `<pre class="code">${esc(sm.statement)}</pre>`) : '') + group('연결 정보', `<p class="muted">DB 계정 ${esc(s.user)} · 스키마 ${esc(s.schema)}</p>`);
      return `<section class="panel">${head}<div class="panel-sec"><h3>표<span class="muted num">${s.tables.length}</span></h3>${list}${picked ? tableDetail(s.id, picked) : '<p class="muted">표 이름을 누르면 열과 최신 행이 보입니다.</p>'}</div>` +
        `<div class="panel-sec sk-fold">${UI.fold('조회문 · 연결 정보', more)}</div></section>`;
    }).join('');
  }
  function tableDetail(sid, name) {
    const meta = (S.tablesBySource && S.tablesBySource[sid] || []).find(t => t.name === name);
    const listError = S.tablesError && S.tablesError[sid];
    const cols = meta ? table('<th>열</th><th>형식</th><th>키</th><th>뜻(주석)</th>',
      meta.columns.map(c => `<tr><td>${code(c.name)}</td><td>${esc(c.type)}</td><td>${c.pk ? '기본키' : ''}${c.fk ? `→ ${esc(c.fk)}` : ''}</td><td>${esc(c.comment || '')}</td></tr>`).join(''))
      : listError ? UI.errorBlock('표의 열 목록을 읽지 못했습니다', listError + ' — 표를 다시 누르면 다시 읽습니다') : UI.loading('열을 읽는 중');
    const sm = S.sample[sid + '|' + name];
    const sample = !sm ? UI.loading('최신 행을 읽는 중') : sm.error ? UI.errorBlock('최신 행을 읽지 못했습니다', sm.error) : rowsTable(sm.columns, sm.rows);
    return `<div class="fab-out">` + group(`${code(name)}${meta && meta.comment ? ' · ' + esc(meta.comment) : ''} · 열${meta ? ' ' + meta.columns.length + '개' : ''}`, cols) +
      group(sm && !sm.error ? `최신 ${sm.row_count}행` : '최신 행', sample) + `</div>`;
  }

  /* ---------- 탭 3: 클래스 ↔ 표·열 ---------- */
  function linksTab() {
    const L = S.links;
    if (!L) return S.errors.links ? UI.errorBlock('연결을 읽지 못했습니다', S.errors.links) : UI.loading('');
    const graph = L.graph.ok ? '' : UI.errorBlock('지식 그래프를 읽지 못했습니다', L.graph.reason);
    const classes = table('<th>클래스 (식별 키)</th><th>원천 위치</th><th>상태</th><th>원천에 있음</th><th>원천에 없음</th>',
      L.classes.map(c => `<tr><td>${esc(c.label)}<small>${esc(c.key_label || c.key)}</small></td><td>${code(c.table + '.' + c.column)}<small>${srcName(c.source, c.source_label)}${c.window ? ' · ' + esc(c.window) : ''}</small></td>` +
        `<td>${chip(c.state)}${c.reason ? `<small>${esc(c.reason)}</small>` : ''}</td><td>${esc((c.matched || []).map(m => m.key).join(', '))}</td>` +
        `<td>${esc((c.unmatched || []).map(m => `${m.key}${m.name ? ` (${m.name})` : ''}`).join(', '))}</td></tr>`).join(''));
    const order = ['MISSING', 'SOURCE_DOWN', 'UNREGISTERED', 'TYPE_CHANGED', 'COMMENT_CHANGED', 'UNBOUND', 'OK', 'DERIVED', 'OUTSIDE'];
    const byState = order.map(st => [st, L.inputs.filter(i => i.state === st)]).filter(([, l]) => l.length);
    const inputTable = (st, list) => {
      const reasons = new Set(list.map(i => i.reason || ''));
      const shared = reasons.size === 1 ? (list[0].reason || (st === 'OK' ? '원천 표 · 열에서 바로 읽음' : '')) : '항목마다 사유가 다릅니다';
      return group(`${esc((STATE[st] || [st])[0])} ${list.length}개${shared ? ' — ' + esc(shared) : ''}`,
        table(`<th>판단 입력</th><th>지식 지도 출처</th><th>원천 위치</th>${reasons.size > 1 ? '<th>사유</th>' : ''}`, list.map(i =>
          `<tr><td>${esc(i.name)}</td><td>${esc(UI.name(i.source) || i.sourceName || '')}</td><td>${code(i.table ? i.table + '.' + i.column : '')}` +
          `<small>${[i.datasource ? srcName(i.datasource, i.source_label || srcLabel(i.datasource)) : '', esc(i.where || (i.key ? i.key + ' = 설비' : ''))].filter(Boolean).join(' · ')}</small></td>${reasons.size > 1 ? `<td>${esc(i.reason || '')}</td>` : ''}</tr>`).join('')));
    };
    // 문제가 있는 것이 먼저, 연결된 것이 다음. DB 밖의 값(계산 · 입력)은 연결할 표가 없는 것이라 접기에 둔다
    const inside = byState.filter(([st]) => st !== 'DERIVED' && st !== 'OUTSIDE').map(([st, list]) => inputTable(st, list)).join('');
    const outside = byState.filter(([st]) => st === 'DERIVED' || st === 'OUTSIDE');
    const outsideCount = outside.reduce((n, [, l]) => n + l.length, 0);
    return `<section class="panel"><div class="panel-sec"><h3>클래스 ↔ 표 · 열</h3><p class="muted">온톨로지 클래스의 식별 키가 원천의 어느 열과 같은 것을 가리키는지, 지금 DB의 표 목록과 대조해 확인합니다.</p>${graph}${classes}</div></section>` +
      `<section class="panel"><div class="panel-sec"><h3>판단 입력의 원천</h3><p class="muted">지식 지도의 「데이터 출처」 연결과 문서 등록 화면의 업무 DB 표 정의 연결로 정해진 표와 열입니다.</p><div class="fab-out">` +
      (inside || (outside.length ? '' : UI.emptyGo('판단 입력이 없습니다', '문서 등록 화면에서 업무 DB 표 정의를 연결하면 여기에 나옵니다.', 'knowledge', '문서 등록 열기'))) + `</div></div>` +
      (outside.length ? `<div class="panel-sec sk-fold">${UI.fold(`DB에 없는 값(계산 · 입력)<span class="muted num">${outsideCount}개</span>`, `<div class="fab-out">${outside.map(([st, list]) => inputTable(st, list)).join('')}</div>`)}</div>` : '') + `</section>`;
  }

  /* ---------- 그리기 · 이벤트 ---------- */
  function render() {
    if (!S.el) return;
    S.el.innerHTML = summary() + UI.tabs([['join', '두 DB 묶어 보기'], ['sources', '원천과 표', S.sources ? S.sources.length : null], ['links', '클래스 ↔ 표 · 열']], S.tab, 'data-fab-tab') +
      `<div class="fab-body">${S.tab === 'join' ? joinTab() : S.tab === 'sources' ? sourcesTab() : linksTab()}</div>`;
  }
  async function load() {
    const [src, links, queries] = await Promise.allSettled([getJ(API.process + '/api/fabric/sources'), getJ(API.process + '/api/fabric/links'), getJ(API.process + '/api/fabric/queries')]);
    S.sources = src.status === 'fulfilled' ? src.value : null; S.errors.sources = src.status === 'rejected' ? src.reason.message : '';
    S.links = links.status === 'fulfilled' ? links.value : null; S.errors.links = links.status === 'rejected' ? links.reason.message : '';
    // 질문 목록을 못 읽으면 조용히 빈 목록으로 두지 않는다 — 사유를 질문 칸 아래에(기본 질문 하나로는 계속 묶어 볼 수 있다)
    S.queries = queries.status === 'fulfilled' ? queries.value : []; S.errors.queries = queries.status === 'rejected' ? queries.reason.message : '';
    render();
  }
  async function run() {
    S.asset = (document.getElementById('fabAsset').value || '').trim(); S.query = document.getElementById('fabQuery').value;
    S.busy = true; S.resultError = ''; render();
    try { S.result = await postJ(API.process + '/api/fabric/query', { asset: S.asset, query: S.query, limit: 50 }); }
    catch (e) { S.result = null; S.resultError = e.message; }
    finally { S.busy = false; render(); }
  }
  async function pickTable(sid, name) {
    S.table[sid] = name;
    S.tablesBySource = S.tablesBySource || {}; S.tablesError = S.tablesError || {};
    delete S.tablesError[sid]; delete S.sample[sid + '|' + name];
    render();
    if (!S.tablesBySource[sid]) {
      try { S.tablesBySource[sid] = (await getJ(`${API.process}/api/fabric/sources/${encodeURIComponent(sid)}/tables`)).tables; }
      catch (e) { S.tablesError[sid] = e.message; }
    }
    try { S.sample[sid + '|' + name] = await getJ(`${API.process}/api/fabric/sources/${encodeURIComponent(sid)}/tables/${encodeURIComponent(name)}/sample?limit=5`); }
    catch (e) { S.sample[sid + '|' + name] = { error: e.message }; }
    render();
  }
  function mount(el) {
    if (!el) return;
    if (S.el !== el) {
      S.el = el;
      el.addEventListener('click', e => {
        const tab = e.target.closest('[data-fab-tab]'); if (tab) { S.tab = tab.dataset.fabTab; render(); return; }
        if (e.target.closest('#fabRun')) { run(); return; }
        const t = e.target.closest('[data-fab-table]'); if (t) { const [sid, name] = t.dataset.fabTable.split('|'); pickTable(sid, name); }
      });
      el.addEventListener('change', e => { if (e.target.id === 'fabQuery') { S.query = e.target.value; S.asset = document.getElementById('fabAsset').value; render(); } });
    }
    render(); load();
  }
  // 셸이 처음 열 때 mount, 다시 열면 show 로 상태를 새로 읽는다
  window.hydFabric = { mount, show: mount };
})();
