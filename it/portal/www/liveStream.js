/* A091 — 실시간 이벤트 스트림. process 의 GET /api/events/stream (server-sent events) 을 구독해 에이전트 도구 호출 · 단계 전이 ·
   사람의 답변 · 오류가 생기는 즉시 보여 준다. 2초 폴링을 대체하지 않고 앞에 둔다: 스트림이 단계 전이를 알리면 처리 건 화면을 바로 새로 읽는다.
   A122 (uiux-refs R9, F9): a tool call and its result are one row with the duration on the right; previews are readable text, not raw JSON. */
(function () {
  const S = { es: null, rows: [], byId: new Set(), starts: {}, finished: new Set(), connected: false, filter: 'all', paused: false, reloadTimer: null, lastKey: null, showAll: false };
  const MAX = 160, SHOWN = 40;
  const KIND = {
    tool_usage_started: ['tool', 'stream.tool'], tool_usage_finished: ['tool', 'stream.tool'],
    task_started: ['task', 'stream.start'], task_completed: ['task', 'stream.done'], task_working: ['work', 'stream.working'], task_cancelled: ['task', 'stream.cancel'],
    task_deferred: ['task', 'stream.deferred'], task_reassessment_requested: ['task', 'stream.reassess'],
    human_asked: ['human', 'stream.asked'], human_response: ['human', 'stream.answered'], error: ['error', 'stream.error'],
  };
  const RELOAD_ON = new Set(['task_started', 'task_completed', 'task_cancelled', 'task_deferred', 'human_asked', 'human_response', 'error']);

  function instName(id) {
    const I = window.hydInstances && window.hydInstances.I;
    const inst = I && I.instances.find(x => x.proc_inst_id === id);
    if (inst) return inst.proc_inst_name || id;
    if (!id) return '';
    return UI.defName(id);          // A141: 'anomaly_response.…' → 설비 이상 조치 (UI.terms def.*)
  }
  const activityByTodo = {};          // task_started carries the activity's goal; later events of the same work item reuse it
  function activityOf(e) {
    const I = window.hydInstances && window.hydInstances.I;
    const view = I && I.view;
    const w = view && view.workitems.find(x => x.id === e.todo_id);
    if (w) return UI.flowName(w.activity_name);
    if (e.event_type === 'task_started' && e.data && (e.data.goal || e.data.name) && e.todo_id) activityByTodo[e.todo_id] = e.data.goal || e.data.name;
    return UI.flowName(activityByTodo[e.todo_id] || (e.data && e.event_type === 'task_started' && (e.data.goal || e.data.name)) || '');
  }
  function shortTool(t) { return UI.toolName(t); }   // A141: 도구 이름은 UI.terms tool.* (원문은 처리 건 기록의 원문 접기에)
  function fmtMs(ms) { return ms < 1000 ? `${Math.round(ms)} ms` : ms < 60000 ? `${(ms / 1000).toFixed(1)} s` : `${Math.floor(ms / 60000)}분 ${Math.round((ms % 60000) / 1000)}초`; }
  // F9: a readable one-line preview instead of 140 chars of JSON
  function brief(v, n = 120) {
    if (v == null) return '';
    if (typeof v === 'string') return v.replace(/\s+/g, ' ').slice(0, n);
    if (Array.isArray(v)) return `${v.length}건` + (v.length && typeof v[0] === 'object' ? ' · ' + Object.keys(v[0]).slice(0, 4).join(', ') : '');
    if (typeof v === 'object') {
      const keys = Object.keys(v);
      if (typeof v.query === 'string') return brief(v.query, n);
      if (typeof v.sql === 'string') return brief(v.sql, n);
      return keys.slice(0, 3).map(k => `${k}: ${typeof v[k] === 'object' ? (Array.isArray(v[k]) ? v[k].length + '건' : '…') : String(v[k]).slice(0, 40)}`).join(' · ').slice(0, n);
    }
    return String(v).slice(0, n);
  }

  function describe(e) {
    const d = e.data || {};
    switch (e.event_type) {
      case 'tool_usage_started': return { title: shortTool(d.tool), text: brief(d.input), dur: S.finished.has(d.tool_use_id) ? '' : UI.t('inst.running') };
      case 'tool_usage_finished': {
        const started = S.starts[d.tool_use_id];
        const dur = started ? fmtMs(new Date(e.timestamp) - started) : '';
        return { title: shortTool(d.tool), text: brief(d.output), dur };
      }
      case 'task_working': return { title: d.type === 'usage' ? UI.t('stream.model') : (d.name || d.type || UI.t('stream.working')), text: d.content || d.message || (d.usage ? `${UI.t('stream.tokens')} ${d.usage.input_tokens ?? '–'} / ${d.usage.output_tokens ?? '–'}` : '') };
      case 'task_started': return { title: activityOf(e) || d.name || UI.t('step'), text: d.goal || '' };
      case 'task_completed': return { title: activityOf(e) || UI.t('step'), text: (d.output_keys || []).length ? UI.t('inst.output') + ' ' + d.output_keys.join(', ') : brief(d.text) };
      case 'task_cancelled': {                     // A098: three different things used to look identical in the stream
        if (e.job_id === 'TASK_CANCEL_REQUESTED') return { title: UI.t('stream.cancelReq'), text: UI.logText(brief(d.goal, 160)) };
        if (e.job_id === 'TASK_CLOSED') return { title: UI.t('stream.closed'), text: UI.logText(brief(d.goal || d.reason, 160)) };
        return { title: (activityOf(e) || UI.t('step')) + ' · ' + UI.t('stream.stopped'), text: UI.logText(brief(d.goal, 160)) };   // A141: 영문 취소 사유 → 번역 표
      }
      case 'human_asked': return { title: UI.t('stream.asked'), text: humanQuestionText(d).slice(0, 160) };
      case 'human_response': return { title: UI.t('stream.answered'), text: (d.answer || '').slice(0, 160) };
      case 'error': return { title: d.name || UI.t('stream.error'), text: (d.friendly || d.raw_error || d.message || '').slice(0, 160) };
      default: { const text = d.message || d.note || d.content || d.reason || ''; return text ? { title: text.slice(0, 120), text: '' } : { title: UI.eventName(e.event_type), text: '' }; }
    }
  }

  function push(e, fresh) {
    if (!e || !e.id || S.byId.has(e.id)) return;
    S.byId.add(e.id);
    if (e.event_type === 'tool_usage_started' && e.data && e.data.tool_use_id) S.starts[e.data.tool_use_id] = new Date(e.timestamp);
    if (e.event_type === 'tool_usage_finished' && e.data && e.data.tool_use_id) S.finished.add(e.data.tool_use_id);
    S.rows.unshift({ e, fresh });
    if (S.rows.length > MAX) { const gone = S.rows.pop(); S.byId.delete(gone.e.id); }
    if (fresh && RELOAD_ON.has(e.event_type)) scheduleReload();
    if (fresh) ticker(e);
  }
  function scheduleReload() {
    clearTimeout(S.reloadTimer);
    S.reloadTimer = setTimeout(() => { if (window.hydInstances && state.tab === 'instances') window.hydInstances.load(true); }, 250);
  }

  function ticker(e) {
    const t = document.getElementById('streamTicker'); if (!t) return;
    S.lastKey = e.id;
    const kind = KIND[e.event_type];
    const { title } = describe(e);
    t.innerHTML = `<i class="live-dot ${kind ? kind[0] : ''}"></i><span>${esc(kind ? UI.t(kind[1]) : UI.eventName(e.event_type))}</span><b>${esc(title)}</b>`;
    t.classList.remove('flash'); void t.offsetWidth; t.classList.add('flash');
  }
  function connState(text, ok) {
    const c = document.getElementById('streamConn'); if (c) { c.textContent = text; c.className = 'stream-conn ' + (ok ? 'on' : 'off'); }
    const t = document.getElementById('streamTicker');
    if (t && !ok) t.innerHTML = `<i class="live-dot off"></i><span>${esc(text)}</span>`;
  }

  function render() {
    const box = document.getElementById('streamList'); if (!box || S.paused) return;
    const isUsage = r => r.e.event_type === 'task_working' && r.e.data && r.e.data.type === 'usage';   // token counters: noise unless asked for
    const merged = r => r.e.event_type === 'tool_usage_started' && r.e.data && S.finished.has(r.e.data.tool_use_id);   // R9: started+finished = one row
    const rows = S.rows.filter(r => !merged(r)).filter(r => S.filter === 'all' ? !isUsage(r)
      : S.filter === 'work' ? (KIND[r.e.event_type] || [''])[0] === 'work'
      : (KIND[r.e.event_type] || [''])[0] === S.filter || (S.filter === 'task' && !KIND[r.e.event_type]));
    if (!rows.length) { box.innerHTML = UI.empty(UI.t('stream.empty'), UI.t('stream.emptySub'), 'compact'); return; }
    const limit = S.showAll ? 80 : SHOWN;
    box.innerHTML = rows.slice(0, limit).map(({ e, fresh }) => {
      const kind = KIND[e.event_type] || ['task', ''];
      const label = kind[1] ? UI.t(kind[1]) : UI.eventName(e.event_type);
      const { title, text, dur } = describe(e);
      const act = activityOf(e);
      return `<div class="stream-row ${kind[0]}${fresh ? ' new' : ''}" data-inst="${esc(e.proc_inst_id || '')}" tabindex="0">
        <time title="${esc(UI.dateTime(e.timestamp))}">${esc(UI.time(e.timestamp))}</time>
        <span class="kind">${esc(label)}</span>
        <div class="body"><b>${esc(title)}</b>${text ? `<span class="txt">${esc(text)}</span>` : ''}</div>
        <span class="where">${esc(instName(e.proc_inst_id))}${act ? ' · ' + esc(act) : ''}</span>
        ${dur ? `<span class="dur">${esc(dur)}</span>` : ''}
      </div>`;
    }).join('') + (rows.length > limit ? `<button type="button" class="btn small" id="streamMore">${esc(UI.t('stream.all'))} (${rows.length})</button>` : '');
    S.rows.forEach(r => { r.fresh = false; });
    box.querySelectorAll('.stream-row[data-inst]').forEach(row => row.addEventListener('click', () => { if (row.dataset.inst && window.hydInstancesSelect) window.hydInstancesSelect(row.dataset.inst); }));
    box.querySelector('#streamMore')?.addEventListener('click', () => { S.showAll = true; render(); });
    const count = document.getElementById('streamCount'); if (count) count.textContent = `${rows.length}`;
    const foldCount = document.getElementById('streamFoldCount'); if (foldCount) foldCount.textContent = `${rows.length}`;   // A141: 접힌 요약 줄의 건수
  }

  function connect() {
    if (S.es) { S.es.close(); S.es = null; }
    connState(UI.t('header.connecting'), false);
    const es = new EventSource(API.process + '/api/events/stream');
    S.es = es;
    es.onopen = () => {
      S.connected = true; S.backoff = 0; connState(UI.t('header.connected'), true);
      const t = document.getElementById('streamTicker');
      if (t && !S.lastKey) t.innerHTML = `<i class="live-dot on"></i><span>${esc(UI.t('header.waiting'))}</span>`;
    };
    es.addEventListener('history', ev => { try { push(JSON.parse(ev.data), false); } catch (e) { /* ignore a bad frame */ } render(); });
    es.onmessage = ev => { try { push(JSON.parse(ev.data), true); } catch (e) { return; } render(); };
    // A147: a dropped connection (readyState CONNECTING) is retried by the browser itself; ids keep the list deduplicated.
    // A non-200 answer closes the EventSource for good (readyState CLOSED): legacy mode answers 409 → show "실시간 꺼짐",
    // anything else (process restarting, 5xx) → reconnect with backoff 2 · 4 · 8 … 30 s.
    es.onerror = () => {
      S.connected = false;
      if (es.readyState !== EventSource.CLOSED) { connState(UI.t('header.disconnected'), false); return; }
      es.close(); if (S.es === es) S.es = null;
      afterClose();
    };
  }
  async function afterClose() {
    let legacy = false;
    try { legacy = !(await getJ(API.process + '/api/process/mode')).definition; } catch (_) { /* process unreachable: retry below */ }
    if (legacy) { S.off = true; connState(UI.t('header.streamOff'), false); return; }
    connState(UI.t('header.disconnected'), false);
    S.backoff = Math.min(30000, (S.backoff || 1000) * 2);
    clearTimeout(S.retryTimer); S.retryTimer = setTimeout(connect, S.backoff);
  }

  function mount() {
    const box = document.getElementById('streamPanel'); if (!box) return;
    box.innerHTML = `<div class="stream-head"><div><h3>${esc(UI.t('stream.title'))} <small class="chip tone-neutral sm" id="streamCount"></small></h3></div>
      <div class="stream-tools"><span id="streamConn" class="stream-conn off">${esc(UI.t('header.connecting'))}</span>
        <div class="chips small" id="streamFilter">${[['all', 'stream.filter.all'], ['tool', 'stream.filter.tool'], ['task', 'stream.filter.task'], ['human', 'stream.filter.human'], ['error', 'stream.filter.error'], ['work', 'stream.filter.work']].map(([k, l]) => `<button class="chip${k === 'all' ? ' on' : ''}" data-f="${k}" type="button">${esc(UI.t(l))}</button>`).join('')}</div>
        <button class="btn small" id="streamPause" type="button" aria-pressed="false">${esc(UI.t('stream.pause'))}</button></div></div>
      <div class="stream-list" id="streamList"></div>`;
    box.querySelectorAll('#streamFilter .chip').forEach(c => c.addEventListener('click', () => {
      S.filter = c.dataset.f; box.querySelectorAll('#streamFilter .chip').forEach(x => x.classList.toggle('on', x === c)); render();
    }));
    const pause = document.getElementById('streamPause');
    pause.addEventListener('click', () => { S.paused = !S.paused; pause.textContent = S.paused ? UI.t('stream.resume') : UI.t('stream.pause'); pause.setAttribute('aria-pressed', String(S.paused)); if (!S.paused) render(); });
    render();
    connect();
  }
  document.addEventListener('DOMContentLoaded', mount);
  if (document.readyState !== 'loading') mount();
  window.hydStream = { S, render };
})();
