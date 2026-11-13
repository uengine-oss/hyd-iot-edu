/* A11 데이터 패브릭 미니 — 업무 DB(Supabase ent)와 시계열 DB(TimescaleDB)를 읽기만 해서 설비 하나로 묶어 본다.
   window.hydFabric.mount(el). 차례: 한 문장 → 원천과 연결의 지금 상태(한 줄씩) → 보기 셋(묶어 보기 = 왼쪽 조건 · 오른쪽 결과, 원천과 표, 클래스 ↔ 표·열).
   색은 상태에만 쓴다 — 어느 원천인지는 글로 쓰고, 칩은 문제가 있는 상태에만 붙인다. 조회문(SQL)과 연결 정보는 「자세히」 접기 안에 있다.
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
  const group = (label, body) => body ? `<section class="rd-group"><h3 class="rd-label">${label}</h3>${body}</section>` : '';
  const srcLabel = id => ((S.sources || []).find(s => s.id === id) || {}).label || id;   // 원천 이름은 서버(fabric.SOURCES) 한 곳
  const val = (v, unit) => v == null ? '<span class="field-hint">값 없음</span>' : `<b>${esc(typeof v === 'number' ? window.hydWords.num(v) : v)}</b>${unit ? ' ' + esc(unit) : ''}`;
  const code = (t) => t ? `<code>${esc(t)}</code>` : '';
  const when = (t) => t ? esc(UI.dateTime ? UI.dateTime(t) : t) : '';

  function rowsTable(columns, rows, max = 10) {
    if (!rows || !rows.length) return '<p class="rd-note">행이 없습니다.</p>';
    const body = rows.slice(0, max).map(r => `<tr>${r.map(v => `<td>${esc(v == null ? '' : typeof v === 'object' ? JSON.stringify(v) : v)}</td>`).join('')}</tr>`).join('');
    return `<div class="rd-scroll"><table class="tbl"><thead><tr>${columns.map(c => `<th>${esc(c)}</th>`).join('')}</tr></thead><tbody>${body}</tbody></table></div>` +
      (rows.length > max ? `<p class="rd-note">${rows.length}행 중 ${max}행을 보입니다.</p>` : '');
  }

  /* ---------- 요약 ---------- */
  // 지금 상태를 한 줄씩: 원천마다 연결됐는지, 클래스가 표 · 열에 닿는지. 응답 전에는 읽는 중, 실제로 못 읽었을 때만 확인 실패
  // (화면을 열 때마다 0.1초씩 실패가 보였다 — 1회차 04 촬영 검토)
  function summary() {
    const line = (tone, name, text) => `<li class="rd-state ${tone}"><span><b>${esc(name)}</b> — ${text}</span></li>`;
    const rows = (S.sources || []).map(s => line(s.ok ? 'ok' : 'bad', `${s.label} · ${s.engine}`,
      s.ok ? `연결됨 · 표 ${s.tables.length}개 · ${s.read_only ? '읽기 전용 확인됨' : '<span class="neg">읽기 전용이 아님</span>'}` : `연결 실패 · ${esc(s.reason)}`));
    if (!S.sources) rows.push(S.errors.sources ? line('bad', '원천', `확인 실패 · ${esc(S.errors.sources)}`) : line('', '원천', '읽는 중…'));
    const cls = S.links ? S.links.classes : [];
    const ok = cls.filter(c => c.state === 'OK').length;
    const unbound = S.links ? S.links.inputs.filter(i => i.state === 'UNBOUND').length : 0;
    rows.push(S.links ? line(S.links.graph.ok && ok === cls.length ? 'ok' : 'warn', '클래스 ↔ 표 · 열',
        `클래스 ${cls.length}개 가운데 ${ok}개 연결됨 · ${S.links.graph.ok ? `판단 입력 중 표 · 열 미연결 ${unbound}개` : esc(S.links.graph.reason)}`)
      : line(S.errors.links ? 'bad' : '', '클래스 ↔ 표 · 열', S.errors.links ? `확인 실패 · ${esc(S.errors.links)}` : '읽는 중…'));
    return `<ul class="rd-status" aria-label="원천과 연결의 지금 상태">${rows.join('')}</ul>`;
  }

  /* ---------- 탭 1: 두 DB 묶어 보기 ---------- */
  function assetCodes() {
    const a = S.links && S.links.classes.find(c => c.klass === 'Asset' && c.source === 'hyd-enterprise');
    return a ? [...(a.matched || []), ...(a.unmatched || [])].map(m => m.key) : [];
  }
  // 왼쪽에 조건, 오른쪽에 결과(기준 5-8)
  function joinTab() {
    const opts = [['asset', '설비 하나로 두 원천 값 합치기'], ...S.queries.map(q => [q.id, q.title])];
    const q = S.queries.find(x => x.id === S.query);
    const form = `<div class="rd-in">` +
      UI.field({ label: '설비', input: `<input id="fabAsset" list="fabAssets" value="${esc(S.asset)}"><datalist id="fabAssets">${assetCodes().map(c => `<option value="${esc(c)}">`).join('')}</datalist>` }) +
      UI.field({ label: '질문', input: `<select id="fabQuery">${opts.map(([k, l]) => `<option value="${esc(k)}"${k === S.query ? ' selected' : ''}>${esc(l)}</option>`).join('')}</select>`,
                 hint: S.errors.queries ? `준비된 질문 목록을 읽지 못했습니다 — ${S.errors.queries}` : q ? q.question : '업무 DB에서 설비 코드로 이어진 표와 시계열 DB의 태그별 최신값을, 어느 원천에서 왔는지와 함께 모읍니다' }) +
      `<div class="rd-in-actions"><button class="btn primary" id="fabRun"${S.busy ? ' disabled' : ''}>${S.busy ? '읽는 중…' : '묶어 보기'}</button></div>` +
      `<p class="rd-in-note">읽기 전용 계정으로만 조회합니다. 조회 한 번은 5초까지이고 행 수 제한이 있습니다. 이 화면에는 쓰는 단추가 없습니다.</p></div>`;
    return `<div class="rd-io">${form}<div class="rd-out" id="fabResult">${result()}</div></div>`;
  }
  // 결과의 차례: 무엇을 물었나(한 문장) → 읽은 값 표 → 「자세히」(실행한 조회문과 받은 행)
  function result() {
    if (S.resultError) return UI.errorBlock('조회하지 못했습니다', S.resultError);
    const r = S.result;
    if (!r) return UI.empty('아직 묶어 본 결과가 없습니다', '왼쪽에서 설비와 질문을 고르고 [묶어 보기]를 누르면, 두 DB에서 읽은 값이 어느 원천 · 표 · 열에서 왔는지와 함께 보입니다.', 'compact');
    const down = Object.entries(r.sources || {}).filter(([, s]) => !s.ok);
    const warn = down.length ? `<p class="rd-state warn">일부 원천을 읽지 못했습니다 — ${down.map(([id, s]) => `${esc(srcLabel(id))}: ${esc(s.reason)}`).join(' · ')}</p>` : '';
    const notes = (r.notes || []).map(n => `<p class="rd-note">${esc(n)}</p>`).join('');
    const answer = r.query === 'asset' ? assetAnswer(r) : `<div class="rd-scroll"><table class="tbl"><thead><tr><th>항목</th><th>값</th><th>원천</th><th>위치</th></tr></thead><tbody>${
      r.answer.map(a => `<tr><td>${esc(a.label)}</td><td>${a.value == null ? chip(a.state) + `<small>${esc(a.reason || '')}</small>` : val(a.value, a.unit)}</td>` +
        `<td>${srcName(a.source, a.source_label)}</td><td>${code(partTable(r, a))}${a.where ? `<small>${esc(a.where)}</small>` : ''}${a.at ? `<small>${when(a.at)}</small>` : ''}</td></tr>`).join('')}</tbody></table></div>`;
    const parts = r.parts.map(p => group(`${srcName(p.source, p.source_label)} · ${esc(p.purpose)}`,
      (p.ok ? `<pre>${esc(p.statement)}</pre>${Object.keys(p.params || {}).length ? `<p class="rd-note">조회 조건: ${Object.entries(p.params).map(([k, v]) => `${esc(window.hydWords.fieldName(k))} ${esc(v !== null && typeof v === 'object' ? JSON.stringify(v) : v)}`).join(' · ')}</p>` : ''}` +
              rowsTable(p.columns, p.rows) + (p.at_row_limit ? '<p class="rd-note">행 제한에 닿아 일부만 보입니다.</p>' : '')
            : `<p class="field-error">${esc(p.reason)}</p><pre>${esc(p.statement)}</pre>`))).join('');
    const used = [...new Set(r.parts.map(p => p.source))].map(id => srcLabel(id)).join(' · ');
    return `<h2 class="rd-conclusion">${esc(r.question || r.title)}</h2>` +
      `<p class="rd-note">${esc(r.asset)} · ${when(r.at)} · 읽은 원천 ${esc(used)} · 조회마다 최대 ${r.row_limit}행${r.partial ? ' · 일부만 읽었습니다' : ''}</p>` +
      warn + notes + answer + `<div class="rd-group">${UI.fold(`자세히 · 실행한 조회 ${r.parts.length}개 (SQL · 받은 행)`, parts, { cls: 'small' })}</div>`;
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
      if (!rows.length) return group(label, `<p class="rd-note">${esc(r.sources[id] && !r.sources[id].ok ? r.sources[id].reason : '연결된 값이 없습니다.')}</p>`);
      return group(`${label} · 연결된 값 ${rows.length}개`, `<div class="rd-scroll"><table class="tbl"><thead><tr><th>클래스</th><th>항목</th><th>값</th><th>위치</th></tr></thead><tbody>${
        rows.map(v => `<tr><td>${esc(KLASS[v.klass] || '연결 없음')}</td><td>${esc(v.label)}${v.klass !== 'InputData' ? ` ${code(v.field)}` : ''}` +
          `${v.inputs && v.inputs.length ? `<small>판단 입력: ${esc(v.inputs.join(', '))}</small>` : ''}</td>` +
          `<td>${v.value == null ? chip(v.state) + `<small>${esc(v.reason || '')}</small>` : val(v.value, v.unit)}${v.anchor ? `<small>저장값 ${when(v.anchor)}</small>` : ''}</td>` +
          `<td>${code(v.from)}${v.where ? `<small>${esc(v.where)}</small>` : ''}${v.age_s != null ? `<small>${esc(v.age_s)}초 전</small>` : ''}</td></tr>`).join('')}</tbody></table></div>`);
    }).join('');
  }

  /* ---------- 탭 2: 원천 · 표 · 샘플 ---------- */
  // 원천마다 한 묶음: 이름과 한 줄 → 표 고르기 → 고른 표의 열(뜻)과 최신 행 → 「자세히」(조회문 · 연결 정보)
  function sourcesTab() {
    if (!S.sources) return S.errors.sources ? UI.errorBlock('원천 상태를 읽지 못했습니다', S.errors.sources) : UI.loading('', 'compact');
    return S.sources.map(s => {
      const head = `<header class="rd-head"><div><div class="rd-title"><h2>${esc(s.label)}</h2>${s.ok ? (s.read_only ? '' : UI.chipText('읽기 전용 아님', 'danger')) : UI.chipText('연결 실패', 'danger')}</div>` +
        `<p class="rd-sub">${esc([s.about, s.engine, s.ok && s.read_only ? '읽기 전용' : ''].filter(Boolean).join(' · '))}</p></div></header>`;
      if (!s.ok) return `<section class="rd-group rd-source">${head}<p class="field-error">${esc(s.reason)}</p>${UI.fold('자세히 · 오류 원문', `<pre>${esc(s.detail)}</pre>`, { cls: 'small' })}</section>`;
      const picked = S.table[s.id];
      const list = `<div class="rd-picks" role="group" aria-label="${esc(s.label)}의 표">${s.tables.map(t => `<button class="btn small${t.name === picked ? '' : ' ghost'}" aria-pressed="${t.name === picked}" data-fab-table="${esc(s.id)}|${esc(t.name)}">${esc(t.name)}</button>`).join('')}</div>`;
      const sm = picked ? S.sample[s.id + '|' + picked] : null;
      const more = (sm && sm.statement ? group('최신 행을 읽은 조회문', `<pre>${esc(sm.statement)}</pre>`) : '') + group('연결 정보', `<p class="rd-note">DB 계정 ${esc(s.user)} · 스키마 ${esc(s.schema)}</p>`);
      return `<section class="rd-group rd-source">${head}${list}${picked ? tableDetail(s.id, picked) : '<p class="rd-note">표 이름을 누르면 열과 최신 행이 보입니다.</p>'}` +
        `<div class="rd-group">${UI.fold('자세히 · 조회문 · 연결 정보', more, { cls: 'small' })}</div></section>`;
    }).join('');
  }
  function tableDetail(sid, name) {
    const meta = (S.tablesBySource && S.tablesBySource[sid] || []).find(t => t.name === name);
    const listError = S.tablesError && S.tablesError[sid];
    const cols = meta ? `<div class="rd-scroll"><table class="tbl"><thead><tr><th>열</th><th>형식</th><th>키</th><th>뜻(주석)</th></tr></thead><tbody>${
      meta.columns.map(c => `<tr><td>${code(c.name)}</td><td>${esc(c.type)}</td><td>${c.pk ? '기본키' : ''}${c.fk ? `→ ${esc(c.fk)}` : ''}</td><td>${esc(c.comment || '')}</td></tr>`).join('')}</tbody></table></div>`
      : listError ? UI.errorBlock('표의 열 목록을 읽지 못했습니다', listError + ' — 표를 다시 누르면 다시 읽습니다') : UI.loading('열을 읽는 중', 'compact');
    const sm = S.sample[sid + '|' + name];
    const sample = !sm ? UI.loading('최신 행을 읽는 중', 'compact') : sm.error ? `<p class="field-error">${esc(sm.error)}</p>` : rowsTable(sm.columns, sm.rows);
    return group(`${code(name)}${meta && meta.comment ? ' · ' + esc(meta.comment) : ''} · 열${meta ? ' ' + meta.columns.length + '개' : ''}`, cols) +
      group(sm && !sm.error ? `최신 ${sm.row_count}행` : '최신 행', sample);
  }

  /* ---------- 탭 3: 클래스 ↔ 표·열 ---------- */
  function linksTab() {
    const L = S.links;
    if (!L) return S.errors.links ? UI.errorBlock('연결을 읽지 못했습니다', S.errors.links) : UI.loading('', 'compact');
    const graph = L.graph.ok ? '' : `<p class="field-error">지식 그래프: ${esc(L.graph.reason)}</p>`;
    const classes = `<div class="rd-scroll"><table class="tbl"><thead><tr><th>클래스 (식별 키)</th><th>원천 위치</th><th>상태</th><th>원천에 있음</th><th>원천에 없음</th></tr></thead><tbody>${
      L.classes.map(c => `<tr><td>${esc(c.label)}<small>${esc(c.key_label || c.key)}</small></td><td>${code(c.table + '.' + c.column)}<small>${srcName(c.source, c.source_label)}${c.window ? ' · ' + esc(c.window) : ''}</small></td>` +
        `<td>${chip(c.state)}${c.reason ? `<small>${esc(c.reason)}</small>` : ''}</td><td>${esc((c.matched || []).map(m => m.key).join(', '))}</td>` +
        `<td>${esc((c.unmatched || []).map(m => `${m.key}${m.name ? ` (${m.name})` : ''}`).join(', '))}</td></tr>`).join('')}</tbody></table></div>`;
    const order = ['MISSING', 'SOURCE_DOWN', 'UNREGISTERED', 'TYPE_CHANGED', 'COMMENT_CHANGED', 'UNBOUND', 'OK', 'DERIVED', 'OUTSIDE'];
    const byState = order.map(st => [st, L.inputs.filter(i => i.state === st)]).filter(([, l]) => l.length);
    const inputTable = (st, list) => {
      const reasons = new Set(list.map(i => i.reason || ''));
      const shared = reasons.size === 1 ? (list[0].reason || (st === 'OK' ? '원천 표 · 열에서 바로 읽음' : '')) : '항목마다 사유가 다릅니다';
      return group(`${esc((STATE[st] || [st])[0])} ${list.length}개${shared ? ' — ' + esc(shared) : ''}`,
        `<div class="rd-scroll"><table class="tbl"><thead><tr><th>판단 입력</th><th>지식 지도 출처</th><th>원천 위치</th>${reasons.size > 1 ? '<th>사유</th>' : ''}</tr></thead><tbody>${list.map(i =>
          `<tr><td>${esc(i.name)}</td><td>${esc(UI.name(i.source) || i.sourceName || '')}</td><td>${code(i.table ? i.table + '.' + i.column : '')}` +
          `<small>${[i.datasource ? srcName(i.datasource, i.source_label || srcLabel(i.datasource)) : '', esc(i.where || (i.key ? i.key + ' = 설비' : ''))].filter(Boolean).join(' · ')}</small></td>${reasons.size > 1 ? `<td>${esc(i.reason || '')}</td>` : ''}</tr>`).join('')}</tbody></table></div>`);
    };
    // 문제가 있는 것이 먼저, 연결된 것이 다음. DB 밖의 값(계산 · 입력)은 연결할 표가 없는 것이라 「자세히」에 둔다
    const inside = byState.filter(([st]) => st !== 'DERIVED' && st !== 'OUTSIDE').map(([st, list]) => inputTable(st, list)).join('');
    const outside = byState.filter(([st]) => st === 'DERIVED' || st === 'OUTSIDE');
    const outsideCount = outside.reduce((n, [, l]) => n + l.length, 0);
    return `<section class="rd-group"><h2 class="rd-sec">클래스 ↔ 표 · 열</h2><p class="rd-note">온톨로지 클래스의 식별 키가 원천의 어느 열과 같은 것을 가리키는지, 지금 DB의 표 목록과 대조해 확인합니다.</p>${graph}${classes}</section>` +
      `<section class="rd-group"><h2 class="rd-sec">판단 입력의 원천</h2><p class="rd-note">지식 지도의 「데이터 출처」 연결과 문서 등록 화면의 업무 데이터 연결(DDL 적재)로 정해진 표와 열입니다.</p>` +
      (inside || (outside.length ? '' : UI.empty('판단 입력이 없습니다', '문서 등록 화면에서 업무 데이터(DDL)를 연결하면 여기에 나옵니다.', 'compact'))) +
      (outside.length ? `<div class="rd-group">${UI.fold(`자세히 · DB에 없는 값(계산 · 입력) ${outsideCount}개`, outside.map(([st, list]) => inputTable(st, list)).join(''), { cls: 'small' })}</div>` : '') + `</section>`;
  }

  /* ---------- 그리기 · 이벤트 ---------- */
  function render() {
    if (!S.el) return;
    const seg = [['join', '두 DB 묶어 보기', null], ['sources', '원천과 표', S.sources ? S.sources.length : null], ['links', '클래스 ↔ 표 · 열', null]].map(([k, l, n]) =>
      `<button type="button" role="tab" class="${k === S.tab ? 'on' : ''}" data-fab-tab="${k}" aria-selected="${k === S.tab}">${esc(l)}${n != null ? `<span class="n">${n}</span>` : ''}</button>`).join('');
    S.el.innerHTML = `<p class="page-lead">업무 DB와 시계열 DB를 읽기만 해서 설비 하나로 묶어 보고, 지식의 클래스가 실제 표와 열에 닿는지 확인합니다.</p>` +
      summary() + `<div class="rd-seg" role="tablist" aria-label="보기">${seg}</div>` +
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
