/* A11 데이터 패브릭 미니 — 업무 DB(Supabase ent)와 시계열 DB(TimescaleDB)를 읽기만 해서 설비 하나로 묶어 본다.
   window.hydFabric.mount(el). 요약(두 원천 상태 · 클래스 연결) 먼저, 탭: 묶어 보기 · 원천과 표 · 클래스 ↔ 표·열.
   API: process /api/fabric/* (procsvc/fabric_api.py) — 에이전트의 MCP 도구 hyd-dmn fabric_query 와 같은 함수다. 쓰기 버튼 없음. */
(function () {
  const S = { el: null, tab: 'join', sources: null, links: null, queries: [], errors: {}, result: null, resultError: '', busy: false,
              table: {}, sample: {}, asset: 'HYD-01', query: 'asset' };
  const SRC_TONE = { 'hyd-enterprise': 'accent', 'hyd-timeseries': 'success' };
  const KLASS = { Asset: '설비', Sensor: '센서', Actuator: '구동기 설정값', InputData: '판단 입력', Part: '부품', Supplier: '공급사' };
  const STATE = { OK: ['연결됨', 'success'], MISSING: ['원천에 없음', 'danger'], SOURCE_DOWN: ['원천 연결 실패', 'danger'],
    UNBOUND: ['표 · 열 미연결', 'warning'], DERIVED: ['계산하는 값', 'neutral'], OUTSIDE: ['DB 밖 값', 'neutral'], UNREGISTERED: ['등록 안 된 원천', 'danger'],
    NOT_ONE_ROW: ['설비별 1행 아님', 'warning'], NO_DATA: ['기록 없음', 'warning'], TYPE_CHANGED: ['형식 바뀜', 'danger'], COMMENT_CHANGED: ['뜻 바뀜', 'warning'] };
  const chip = (state) => { const [l, t] = STATE[state] || [state || '–', 'neutral']; return UI.chipText(l, t); };
  const srcChip = (id, label) => UI.chipText(label || id, SRC_TONE[id] || 'neutral');
  const val = (v, unit) => v == null ? '<span class="field-hint">값 없음</span>' : `<b>${esc(typeof v === 'number' ? (Number.isInteger(v) ? v : v.toFixed(v < 10 ? 3 : 1)) : v)}</b>${unit ? ` <small>${esc(unit)}</small>` : ''}`;
  const code = (t) => t ? `<code>${esc(t)}</code>` : '';
  const when = (t) => t ? esc(UI.dateTime ? UI.dateTime(t) : t) : '';

  function rowsTable(columns, rows, max = 10) {
    if (!rows || !rows.length) return UI.empty('행 없음');
    const body = rows.slice(0, max).map(r => `<tr>${r.map(v => `<td>${esc(v == null ? '' : typeof v === 'object' ? JSON.stringify(v) : v)}</td>`).join('')}</tr>`).join('');
    return `<div class="table-scroll"><table class="compact-table"><thead><tr>${columns.map(c => `<th>${esc(c)}</th>`).join('')}</tr></thead><tbody>${body}</tbody></table></div>` +
      (rows.length > max ? `<p class="field-hint">${rows.length}행 중 ${max}행 표시</p>` : '');
  }

  /* ---------- 요약 ---------- */
  function summary() {
    const cards = (S.sources || []).map(s => `<section class="card${s.ok ? '' : ' hot'}"><span>${esc(s.label)} · ${esc(s.engine)}</span>` +
      `<b>${s.ok ? '연결됨' : '연결 실패'}</b><small>${s.ok ? `표 ${s.tables.length}개 · 읽기 전용 ${s.read_only ? '확인' : '아님'}` : esc(s.reason)}</small></section>`);
    if (!S.sources) cards.push(`<section class="card hot"><span>원천</span><b>확인 실패</b><small>${esc(S.errors.sources || '읽는 중…')}</small></section>`);
    const cls = S.links ? S.links.classes : [];
    const ok = cls.filter(c => c.state === 'OK').length;
    const unbound = S.links ? S.links.inputs.filter(i => i.state === 'UNBOUND').length : 0;
    cards.push(`<section class="card"><span>클래스 ↔ 표 · 열</span><b>${S.links ? `${ok} / ${cls.length}` : '–'}</b><small>${S.links ?
      (S.links.graph.ok ? `판단 입력 중 표 · 열 미연결 ${unbound}개` : esc(S.links.graph.reason)) : esc(S.errors.links || '읽는 중…')}</small></section>`);
    cards.push(`<section class="card"><span>쓰기</span><b>없음</b><small>전용 읽기 계정 · 읽기 전용 트랜잭션 · 5초 · 행 제한</small></section>`);
    return `<div class="stat-cards">${cards.join('')}</div>`;
  }

  /* ---------- 탭 1: 두 DB 묶어 보기 ---------- */
  function assetCodes() {
    const a = S.links && S.links.classes.find(c => c.klass === 'Asset' && c.source === 'hyd-enterprise');
    return a ? [...(a.matched || []), ...(a.unmatched || [])].map(m => m.key) : [];
  }
  function joinTab() {
    const opts = [['asset', '설비 하나로 두 원천 값 합치기'], ...S.queries.map(q => [q.id, q.title])];
    const q = S.queries.find(x => x.id === S.query);
    const form = `<div class="card">${UI.section('', UI.field({ label: '설비', input: `<input id="fabAsset" list="fabAssets" value="${esc(S.asset)}"><datalist id="fabAssets">${assetCodes().map(c => `<option value="${esc(c)}">`).join('')}</datalist>` }) +
      UI.field({ label: '질문', input: `<select id="fabQuery">${opts.map(([k, l]) => `<option value="${esc(k)}"${k === S.query ? ' selected' : ''}>${esc(l)}</option>`).join('')}</select>`,
                 hint: q ? q.question : '업무 DB에서 설비 코드로 이어진 표와 시계열 DB의 태그별 최신값을 출처와 함께 모읍니다' }))}` +
      UI.actions(`<button class="btn primary" id="fabRun"${S.busy ? ' disabled' : ''}>${S.busy ? '읽는 중…' : '묶어 보기'}</button>`) + '</div>';
    return form + `<div id="fabResult">${result()}</div>`;
  }
  function result() {
    if (S.resultError) return UI.card({ title: '조회 실패', chips: UI.chipText('실패', 'danger'), body: `<p>${esc(S.resultError)}</p>` });
    const r = S.result;
    if (!r) return UI.empty('설비와 질문을 고르고 "묶어 보기"를 누르세요', '두 DB에서 읽은 값마다 어느 원천 · 표 · 열에서 왔는지 함께 보입니다');
    const down = Object.entries(r.sources || {}).filter(([, s]) => !s.ok);
    const warn = down.length ? `<p class="form-msg neg" role="status">일부 원천을 읽지 못했습니다 — ${down.map(([id, s]) => `${esc(id === 'hyd-enterprise' ? '업무 DB' : '시계열 DB')}: ${esc(s.reason)}`).join(' · ')}</p>` : '';
    const notes = (r.notes || []).map(n => `<p class="field-hint">${esc(n)}</p>`).join('');
    const answer = r.query === 'asset' ? assetAnswer(r) : `<div class="table-scroll"><table class="compact-table"><thead><tr><th>항목</th><th>값</th><th>출처</th><th>위치</th></tr></thead><tbody>${
      r.answer.map(a => `<tr><td>${esc(a.label)}</td><td>${a.value == null ? chip(a.state) + ` <small>${esc(a.reason || '')}</small>` : val(a.value, a.unit)}</td>` +
        `<td>${srcChip(a.source, a.source_label)}</td><td>${code(partTable(r, a))}${a.where ? ` <small>${esc(a.where)}</small>` : ''}${a.at ? ` <small>${when(a.at)}</small>` : ''}</td></tr>`).join('')}</tbody></table></div>`;
    const parts = r.parts.map(p => `<section class="form-section"><h4>${srcChip(p.source, p.source_label)} ${esc(p.purpose)}</h4>` +
      (p.ok ? `<pre>${esc(p.statement)}</pre>${Object.keys(p.params || {}).length ? `<p class="field-hint">값: ${esc(JSON.stringify(p.params))}</p>` : ''}` +
              rowsTable(p.columns, p.rows) + (p.at_row_limit ? '<p class="field-hint">행 제한에 닿았습니다 — 일부만 보입니다</p>' : '')
            : `<p class="form-msg neg">${esc(p.reason)}</p><pre>${esc(p.statement)}</pre>`) + '</section>').join('');
    return UI.card({ title: esc(r.question || r.title), chips: srcSummary(r) + (r.partial ? UI.chipText('일부만', 'warning') : ''),
      sub: `${esc(r.asset)} · ${when(r.at)} · 원천 조회마다 최대 ${r.row_limit}행 · 읽기 전용`,
      body: warn + notes + answer + UI.fold(`실행한 조회 ${r.parts.length}개 (SQL · 행)`, parts) });
  }
  function partTable(r, a) {
    const p = r.parts.find(x => x.id === a.part);
    const m = p && /from\s+([\w."]+)/i.exec(p.statement);
    return m ? m[1].replace(/"/g, '') + (a.column ? ' → ' + a.column : '') : a.column || '';
  }
  function srcSummary(r) {
    const used = [...new Set(r.parts.map(p => p.source))];
    return used.map(id => srcChip(id, id === 'hyd-enterprise' ? '업무 DB' : '시계열 DB')).join(' ');
  }
  function assetAnswer(r) {
    const groups = [['hyd-enterprise', '업무 DB'], ['hyd-timeseries', '시계열 DB']];
    return groups.map(([id, label]) => {
      const rows = r.answer.filter(v => v.source === id);
      if (!rows.length) return `<h4>${label}</h4>` + UI.empty(r.sources[id] && !r.sources[id].ok ? r.sources[id].reason : '연결된 값이 없습니다');
      return `<h4>${srcChip(id, label)} 연결된 값 ${rows.length}개</h4><div class="table-scroll"><table class="compact-table"><thead><tr><th>클래스</th><th>항목</th><th>값</th><th>위치</th></tr></thead><tbody>${
        rows.map(v => `<tr><td>${esc(KLASS[v.klass] || '연결 없음')}</td><td>${esc(v.label)}${v.klass !== 'InputData' ? ` ${code(v.field)}` : ''}` +
          `${v.inputs && v.inputs.length ? `<br><small>판단 입력: ${esc(v.inputs.join(', '))}</small>` : ''}</td>` +
          `<td>${v.value == null ? chip(v.state) + ` <small>${esc(v.reason || '')}</small>` : val(v.value, v.unit)}${v.anchor ? `<br><small>저장값 ${when(v.anchor)}</small>` : ''}</td>` +
          `<td>${code(v.from)} <small>${esc(v.where || '')}</small>${v.age_s != null ? ` <small>${esc(v.age_s)}초 전</small>` : ''}</td></tr>`).join('')}</tbody></table></div>`;
    }).join('');
  }

  /* ---------- 탭 2: 원천 · 표 · 샘플 ---------- */
  function sourcesTab() {
    if (!S.sources) return UI.empty('원천 상태를 읽지 못했습니다', S.errors.sources || '');
    return S.sources.map(s => {
      if (!s.ok) return UI.card({ title: esc(s.label), chips: UI.chipText('연결 실패', 'danger'), sub: esc(s.engine), body: `<p>${esc(s.reason)}</p>` + UI.fold('원문 오류', `<pre>${esc(s.detail)}</pre>`) });
      const picked = S.table[s.id];
      const list = `<div class="toolbar">${s.tables.map(t => `<button class="btn small${t.name === picked ? ' primary' : ''}" data-fab-table="${esc(s.id)}|${esc(t.name)}">${esc(t.name)}</button>`).join('')}</div>`;
      const detail = picked ? tableDetail(s.id, picked) : '<p class="field-hint">표를 누르면 열과 최신 샘플이 보입니다</p>';
      return UI.card({ title: esc(s.label), chips: srcChip(s.id, s.engine) + UI.chipText(s.read_only ? '읽기 전용' : '읽기 전용 아님', s.read_only ? 'success' : 'danger'),
        sub: `${esc(s.about)} · 계정 ${esc(s.user)} · 스키마 ${esc(s.schema)}`, body: list + detail });
    }).join('');
  }
  function tableDetail(sid, name) {
    const meta = (S.tablesBySource && S.tablesBySource[sid] || []).find(t => t.name === name);
    const cols = meta ? `<div class="table-scroll"><table class="compact-table"><thead><tr><th>열</th><th>형식</th><th>키</th><th>뜻(주석)</th></tr></thead><tbody>${
      meta.columns.map(c => `<tr><td>${code(c.name)}</td><td>${esc(c.type)}</td><td>${c.pk ? '기본키' : ''}${c.fk ? `→ ${esc(c.fk)}` : ''}</td><td>${esc(c.comment || '')}</td></tr>`).join('')}</tbody></table></div>` : '<p class="field-hint">열 읽는 중…</p>';
    const sm = S.sample[sid + '|' + name];
    const sample = !sm ? '<p class="field-hint">샘플 읽는 중…</p>' : sm.error ? `<p class="form-msg neg">${esc(sm.error)}</p>` :
      `<h4>최신 ${sm.row_count}행</h4><pre>${esc(sm.statement)}</pre>` + rowsTable(sm.columns, sm.rows);
    const keys = meta ? meta.columns.filter(c => c.pk || c.fk).map(c => c.name + (c.fk ? ' → ' + c.fk : ' (기본키)')).join(' · ') : '';
    return `<h4>${code(name)} ${esc(meta && meta.comment || '')}</h4>` + sample + UI.fold(`열 ${meta ? meta.columns.length : '–'}개${keys ? ' · ' + esc(keys) : ''}`, cols);
  }

  /* ---------- 탭 3: 클래스 ↔ 표·열 ---------- */
  function linksTab() {
    const L = S.links;
    if (!L) return UI.empty('연결을 읽지 못했습니다', S.errors.links || '');
    const graph = L.graph.ok ? '' : `<p class="form-msg neg">지식 그래프: ${esc(L.graph.reason)}</p>`;
    const classes = `<div class="table-scroll"><table class="compact-table"><thead><tr><th>클래스 (식별 키)</th><th>원천 위치</th><th>상태</th><th>원천에 있음</th><th>원천에 없음</th></tr></thead><tbody>${
      L.classes.map(c => `<tr><td>${esc(c.label)} <small>${esc(c.key_label || c.key)}</small></td><td>${srcChip(c.source, c.source_label)} ${code(c.table + '.' + c.column)}${c.window ? ` <small>${esc(c.window)}</small>` : ''}</td>` +
        `<td>${chip(c.state)}${c.reason ? ` <small>${esc(c.reason)}</small>` : ''}</td><td>${esc((c.matched || []).map(m => m.key).join(', '))}</td>` +
        `<td>${esc((c.unmatched || []).map(m => `${m.key}${m.name ? ` (${m.name})` : ''}`).join(', '))}</td></tr>`).join('')}</tbody></table></div>`;
    const order = ['OK', 'MISSING', 'SOURCE_DOWN', 'UNREGISTERED', 'TYPE_CHANGED', 'COMMENT_CHANGED', 'UNBOUND', 'DERIVED', 'OUTSIDE'];
    const byState = order.map(st => [st, L.inputs.filter(i => i.state === st)]).filter(([, l]) => l.length);
    const inputs = byState.map(([st, list]) => UI.fold(`${chip(st)} ${list.length}개 — ${esc(list[0].reason || (st === 'OK' ? '원천 표 · 열에서 바로 읽음' : ''))}`,
      `<div class="table-scroll"><table class="compact-table"><thead><tr><th>판단 입력</th><th>출처</th><th>원천 위치</th></tr></thead><tbody>${list.map(i =>
        `<tr><td>${esc(i.name)}</td><td>${esc(UI.name(i.source) || i.sourceName || '')}</td><td>${i.datasource ? srcChip(i.datasource, i.datasource === 'hyd-enterprise' ? '업무 DB' : '시계열 DB') : ''} ${code(i.table ? i.table + '.' + i.column : '')} <small>${esc(i.where || (i.key ? i.key + ' = 설비' : ''))}</small></td></tr>`).join('')}</tbody></table></div>`,
      { open: st !== 'OUTSIDE' && st !== 'DERIVED' && list.length <= 8 })).join('');
    return UI.card({ title: '클래스 ↔ 표 · 열', sub: '온톨로지 클래스의 식별 키가 원천의 어느 열과 같은 것을 가리키는지, 살아 있는 카탈로그에 대어 확인합니다', body: graph + classes }) +
      UI.card({ title: '판단 입력의 원천', sub: '지식 그래프의 SOURCED_FROM 링크와 업무 데이터 연결(DDL 적재)로 생긴 표 · 열 바인딩', body: inputs || UI.empty('판단 입력이 없습니다') });
  }

  /* ---------- 그리기 · 이벤트 ---------- */
  function render() {
    if (!S.el) return;
    const tabs = UI.tabs([['join', '두 DB 묶어 보기'], ['sources', '원천과 표', S.sources ? S.sources.length : null], ['links', '클래스 ↔ 표 · 열']], S.tab, 'data-fab-tab');
    S.el.innerHTML = summary() + tabs + `<div class="fab-body">${S.tab === 'join' ? joinTab() : S.tab === 'sources' ? sourcesTab() : linksTab()}</div>`;
  }
  async function load() {
    const [src, links, queries] = await Promise.allSettled([getJ(API.process + '/api/fabric/sources'), getJ(API.process + '/api/fabric/links'), getJ(API.process + '/api/fabric/queries')]);
    S.sources = src.status === 'fulfilled' ? src.value : null; S.errors.sources = src.status === 'rejected' ? src.reason.message : '';
    S.links = links.status === 'fulfilled' ? links.value : null; S.errors.links = links.status === 'rejected' ? links.reason.message : '';
    S.queries = queries.status === 'fulfilled' ? queries.value : [];
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
    S.table[sid] = name; render();
    S.tablesBySource = S.tablesBySource || {};
    try {
      if (!S.tablesBySource[sid]) S.tablesBySource[sid] = (await getJ(`${API.process}/api/fabric/sources/${encodeURIComponent(sid)}/tables`)).tables;
      S.sample[sid + '|' + name] = await getJ(`${API.process}/api/fabric/sources/${encodeURIComponent(sid)}/tables/${encodeURIComponent(name)}/sample?limit=5`);
    } catch (e) { S.sample[sid + '|' + name] = { error: e.message }; }
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
  window.hydFabric = { mount };
  // 셸이 화면을 열 때 그린다(U7 셸이 직접 mount 를 불러도 된다). 처음 열릴 때 한 번, 다시 열면 상태를 새로 읽는다.
  const view = document.getElementById('view-fabric'), host = document.getElementById('fabricView');
  if (view && host) new MutationObserver(() => { if (view.classList.contains('active')) mount(host); }).observe(view, { attributes: true, attributeFilter: ['class'] });
})();
