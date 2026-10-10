/* A091 → A161-U1 — 실시간 이벤트 버스. process 의 GET /api/events/stream (server-sent events) 을 하나만 열고, 들어온 이벤트를
   ① 화면마다 붙은 실시간 처리 과정(trace.js: 처리 건 상세 · task 상세 · 질문하기) ② task 상세 ③ 머리글 한 줄 ④ 처리 건 화면의 "전체 활동" 목록에 나눠 준다.

   끊김 없이: 서버가 프레임마다 id(=이벤트 시각)를 붙이므로 브라우저가 스스로 다시 붙을 때 Last-Event-ID 로 그 자리부터 받는다.
   서버가 닫아 버린 경우(재시작 · 5xx)는 마지막 시각을 since 로 주고 2 · 4 · 8 … 30초 간격으로 다시 연다. 같은 id 는 한 번만(최근 5,000개 기억).
   지킴이: 2초마다 다시 읽는 처리 건 화면이 스트림보다 10초 넘게 새로운 기록을 보면 스트림이 멈춘 것으로 보고 다시 연다.
   읽기 쉽게: 모델 사용량 · 실행 시작 줄은 숨기고, 도구 호출 시작과 결과는 한 줄(소요 시간), 처리 건 · 단계별로 묶고, 호스트 경로 · 모델 이름은 지운다.
   참고: process-gpt-vue3 components/ui/EventTimeline.vue(도구 시작이 열고 끝이 닫는 한 줄), Dify workflow/run/tracing-panel.tsx(단계별 묶음). */
(function () {
  const S = { es: null, rows: [], ids: new Set(), idOrder: [], starts: {}, finished: new Set(), connected: false, filter: 'all', paused: false,
              reloadTimer: null, lastKey: null, showAll: false, lastTs: null, lastAt: 0, backoff: 0, subs: new Set(), off: false };
  const MAX = 200, SHOWN = 40, IDS = 5000;
  const KIND = {
    tool_usage_started: ['tool', 'stream.tool'], tool_usage_finished: ['tool', 'stream.tool'],
    task_started: ['task', 'stream.start'], task_completed: ['task', 'stream.done'], task_working: ['work', 'stream.working'], task_cancelled: ['task', 'stream.cancel'],
    task_deferred: ['task', 'stream.deferred'], task_reassessment_requested: ['task', 'stream.reassess'],
    human_asked: ['human', 'stream.asked'], human_response: ['human', 'stream.answered'], error: ['error', 'stream.error'],
  };
  const RELOAD_ON = new Set(['task_started', 'task_completed', 'task_cancelled', 'task_deferred', 'human_asked', 'human_response', 'error']);
  const noise = e => e.event_type === 'task_working' && e.data && (e.data.type === 'usage' || e.data.type === 'run_start');

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
    if (e.event_type === 'task_started' && e.data && (e.data.goal || e.data.name) && e.todo_id) activityByTodo[e.todo_id] = e.data.goal || e.data.name;
    if (w) return UI.flowName(w.activity_name);
    return UI.flowName(activityByTodo[e.todo_id] || '');
  }
  const fmtMs = ms => window.hydTrace ? hydTrace.fmtMs(ms) : `${Math.round(ms)} ms`;
  function brief(v, n = 120) {
    if (v == null) return '';
    if (typeof v === 'string') return UI.clean(v.replace(/\s+/g, ' ')).slice(0, n);
    if (Array.isArray(v)) return `${v.length}건`;
    if (typeof v === 'object') {
      for (const k of ['query', 'sql', 'command', 'description', 'file_path', 'path']) if (typeof v[k] === 'string') return brief(v[k], n);
      return Object.keys(v).slice(0, 3).map(k => `${k} ${typeof v[k] === 'object' ? '…' : UI.clean(String(v[k])).slice(0, 40)}`).join(' · ').slice(0, n);
    }
    return String(v).slice(0, n);
  }

  function describe(e) {
    const d = e.data || {};
    switch (e.event_type) {
      case 'tool_usage_started': return { title: UI.toolName(d.tool), text: brief(d.input), dur: S.finished.has(d.tool_use_id) ? '' : UI.t('inst.running'), running: !S.finished.has(d.tool_use_id) };
      case 'tool_usage_finished': {
        const started = S.starts[d.tool_use_id], o = UI.outcome(d.output, d.is_error);
        return { title: UI.toolName(d.tool), text: o.text || brief(d.output), dur: started ? fmtMs(new Date(e.timestamp) - started) : '', tone: o.tone };
      }
      case 'task_working': return { title: d.type === 'text' ? '에이전트 판단' : d.type === 'file_artifact' ? UI.t('trace.file') : UI.clean(UI.logText(d.name || '')) || UI.t('stream.working'),
        text: d.type === 'file_artifact' ? UI.baseName(d.path || '') : brief(d.content || d.message || '', 160) };
      case 'task_started': return { title: activityOf(e) || UI.t('step'), text: UI.t('trace.picked') };
      case 'task_completed': return { title: activityOf(e) || UI.t('step'), text: (d.output_keys || []).length ? UI.t('trace.outputs') + ' ' + d.output_keys.map(k => UI.terms['var.' + k] || k).join(', ') : brief(d.text) };
      case 'task_cancelled': {
        if (e.job_id === 'TASK_CANCEL_REQUESTED') return { title: UI.t('stream.cancelReq'), text: UI.logText(brief(d.goal, 160)) };
        if (e.job_id === 'TASK_CLOSED') return { title: UI.t('stream.closed'), text: UI.logText(brief(d.goal || d.reason, 160)) };
        return { title: (activityOf(e) || UI.t('step')) + ' · ' + UI.t('stream.stopped'), text: UI.logText(brief(d.goal, 160)) };
      }
      case 'human_asked': return { title: UI.t('stream.asked'), text: humanQuestionText(d).slice(0, 160) };
      case 'human_response': return { title: UI.t('stream.answered'), text: (d.answer || '').slice(0, 160) };
      case 'error': return { title: d.name ? UI.clean(d.name) : UI.t('stream.error'), text: UI.clean(d.friendly || d.raw_error || d.message || '').slice(0, 160), tone: 'fail' };
      default: { const text = UI.clean(UI.logText(d.message || d.note || d.content || d.reason || '')); return { title: UI.eventName(e.job_id === 'TASK_REVIEW_REQUIRED' ? e.job_id : e.event_type), text: text.slice(0, 140) }; }
    }
  }

  /* ---------------------------------------------------------------- 받기 */
  function remember(id) {
    S.ids.add(id); S.idOrder.push(id);
    if (S.idOrder.length > IDS) S.ids.delete(S.idOrder.shift());
  }
  function push(e, fresh) {
    if (!e || !e.id || S.ids.has(e.id)) return false;
    remember(e.id);
    if (e.timestamp && (!S.lastTs || e.timestamp > S.lastTs)) S.lastTs = e.timestamp;
    S.lastAt = Date.now();
    if (e.event_type === 'tool_usage_started' && e.data && e.data.tool_use_id) S.starts[e.data.tool_use_id] = new Date(e.timestamp);
    if (e.event_type === 'tool_usage_finished' && e.data && e.data.tool_use_id) S.finished.add(e.data.tool_use_id);
    activityOf(e);
    if (!noise(e)) { S.rows.unshift({ e, fresh }); if (S.rows.length > MAX) S.rows.pop(); }
    // every subscriber gets every event (history too: a trace mounted after the event still wants it)
    if (window.hydTrace) hydTrace.onEvent(e);
    S.subs.forEach(fn => { try { fn(e, fresh); } catch (_) { /* one screen's bug must not stop the stream */ } });
    if (fresh && RELOAD_ON.has(e.event_type)) scheduleReload();
    if (fresh && !noise(e)) ticker(e);
    if (fresh && window.hydTaskDetail) window.hydTaskDetail.onEvent(e);   // U1: the open task panel takes its own task's events at once
    return true;
  }
  function scheduleReload() {
    clearTimeout(S.reloadTimer);
    S.reloadTimer = setTimeout(() => { if (window.hydInstances && state.tab === 'instances') window.hydInstances.load(true); }, 200);
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
    document.querySelectorAll('[data-live-conn]').forEach(n => { n.textContent = text; n.className = 'live-conn ' + (ok ? 'on' : 'off'); });
  }

  /* ---------------------------------------------------------------- 전체 활동 목록 (처리 건 · 단계별 묶음) */
  function render() {
    const box = document.getElementById('streamList'); if (!box || S.paused) return;
    const merged = r => r.e.event_type === 'tool_usage_started' && r.e.data && S.finished.has(r.e.data.tool_use_id);   // R9: started+finished = one row
    const rows = S.rows.filter(r => !merged(r)).filter(r => S.filter === 'all' ? true
      : S.filter === 'work' ? (KIND[r.e.event_type] || [''])[0] === 'work'
      : (KIND[r.e.event_type] || [''])[0] === S.filter || (S.filter === 'task' && !KIND[r.e.event_type]));
    if (!rows.length) { box.innerHTML = UI.empty(UI.t('stream.empty'), UI.t('stream.emptySub'), 'compact'); return; }
    const limit = S.showAll ? 120 : SHOWN;
    let html = '', group = null;
    rows.slice(0, limit).forEach(({ e, fresh }) => {
      const g = `${e.proc_inst_id || ''}|${e.todo_id || ''}`;
      if (g !== group) {
        group = g;
        const act = activityOf(e);
        html += `<div class="stream-group" data-inst="${esc(e.proc_inst_id || '')}" data-todo="${esc(e.todo_id || '')}" tabindex="0"><b>${esc(instName(e.proc_inst_id))}</b>${act ? `<span>${esc(act)}</span>` : ''}</div>`;
      }
      const kind = KIND[e.event_type] || ['task', ''];
      const label = kind[1] ? UI.t(kind[1]) : UI.eventName(e.event_type);
      const { title, text, dur, running, tone } = describe(e);
      html += `<div class="stream-row ${kind[0]}${fresh ? ' new' : ''}${tone && tone !== 'ok' ? ' ' + esc(tone) : ''}" data-inst="${esc(e.proc_inst_id || '')}">
        <time title="${esc(UI.dateTime(e.timestamp))}">${esc(UI.time(e.timestamp))}</time>
        <span class="kind">${running && window.hydTrace ? hydTrace.spinner('sm') : ''}${esc(label)}</span>
        <div class="body"><b>${esc(title)}</b>${text ? `<span class="txt">${esc(text)}</span>` : ''}</div>
        ${dur ? `<span class="dur">${esc(dur)}</span>` : '<span></span>'}
      </div>`;
    });
    box.innerHTML = html + (rows.length > limit ? `<button type="button" class="btn small" id="streamMore">${esc(UI.t('stream.all'))} (${rows.length})</button>` : '');
    S.rows.forEach(r => { r.fresh = false; });
    box.querySelectorAll('[data-inst]').forEach(row => row.addEventListener('click', () => {
      if (!row.dataset.inst) return;
      if (row.dataset.todo && window.hydInstancesOpenTask) window.hydInstancesOpenTask(row.dataset.inst, null);
      else if (window.hydInstancesSelect) window.hydInstancesSelect(row.dataset.inst);
    }));
    box.querySelector('#streamMore')?.addEventListener('click', () => { S.showAll = true; render(); });
    const count = document.getElementById('streamCount'); if (count) count.textContent = `${rows.length}`;
    const foldCount = document.getElementById('streamFoldCount'); if (foldCount) foldCount.textContent = `${rows.length}`;
  }
  let renderTimer = 0;
  const renderSoon = () => { if (renderTimer) return; renderTimer = setTimeout(() => { renderTimer = 0; render(); }, 120); };

  /* ---------------------------------------------------------------- 연결 */
  function connect() {
    if (S.es) { S.es.close(); S.es = null; }
    connState(UI.t('header.connecting'), false);
    // a reconnect we start ourselves resumes after the newest event we hold (the browser's own retry sends Last-Event-ID)
    const es = new EventSource(API.process + '/api/events/stream' + (S.lastTs ? '?since=' + encodeURIComponent(S.lastTs) : ''));
    S.es = es;
    es.onopen = () => {
      S.connected = true; S.backoff = 0; S.openedAt = Date.now(); connState(UI.t('header.connected'), true);
      const t = document.getElementById('streamTicker');
      if (t && !S.lastKey) t.innerHTML = `<i class="live-dot on"></i><span>${esc(UI.t('header.waiting'))}</span>`;
    };
    es.addEventListener('history', ev => { try { push(JSON.parse(ev.data), false); } catch (e) { /* ignore a bad frame */ } renderSoon(); });
    es.onmessage = ev => { let e; try { e = JSON.parse(ev.data); } catch (_) { return; } if (push(e, true)) renderSoon(); };
    // A147: a dropped connection (readyState CONNECTING) is retried by the browser itself (Last-Event-ID resumes it).
    // A non-200 answer closes the EventSource for good: legacy mode answers 409 → "실시간 꺼짐", anything else → our own backoff.
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
  // 지킴이: the 2-second instance poll saw events the stream never delivered → the stream is stuck; reopen it from our last id.
  // It also feeds those events to the bus so nothing is missing in the meantime.
  function fromPoll(events) {
    if (!Array.isArray(events) || !events.length) return;
    const newest = events.reduce((m, e) => (e.timestamp && e.timestamp > m ? e.timestamp : m), '');
    const behind = S.lastTs && newest > S.lastTs && (Date.parse(newest) - Date.parse(S.lastTs)) > 10000;
    if (behind && !S.off && S.connected && Date.now() - (S.openedAt || 0) > 15000) { connect(); }
  }
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible' && !S.off && (!S.es || S.es.readyState === EventSource.CLOSED)) connect(); });

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
  // subscribe(fn): fn(event, fresh) for every event from now on; returns an unsubscribe function
  const subscribe = fn => { S.subs.add(fn); return () => S.subs.delete(fn); };
  window.hydStream = { S, render, subscribe, fromPoll, push, connected: () => S.connected };
})();
