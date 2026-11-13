/* A091 → A161-U1 — 실시간 이벤트 버스. process 의 GET /api/events/stream (server-sent events) 을 하나만 열고, 들어온 이벤트를
   ① 화면마다 붙은 실시간 처리 과정(trace.js: 처리 건 상세 · task 상세 · 질문하기) ② task 상세 ③ 머리글 한 줄 ④ 처리 건 화면의 "전체 활동" 목록에 나눠 준다.

   끊김 없이: 서버가 프레임마다 id(=이벤트 시각)를 붙이므로 브라우저가 스스로 다시 붙을 때 Last-Event-ID 로 그 자리부터 받는다.
   서버가 닫아 버린 경우(재시작 · 5xx)는 마지막 시각을 since 로 주고 2 · 4 · 8 … 30초 간격으로 다시 연다. 같은 id 는 한 번만(최근 5,000개 기억).
   지킴이: 2초마다 다시 읽는 처리 건 화면이 스트림보다 10초 넘게 새로운 기록을 보면 스트림이 멈춘 것으로 보고 다시 연다.
   읽기 쉽게: 모델 사용량 · 실행 시작 줄은 숨기고, 도구 호출 시작과 결과는 한 줄(소요 시간), 처리 건 · 단계별로 묶고, 호스트 경로 · 모델 이름은 지운다.
   참고: process-gpt-vue3 components/ui/EventTimeline.vue(도구 시작이 열고 끝이 닫는 한 줄), Dify workflow/run/tracing-panel.tsx(단계별 묶음). */
(function () {
  const S = { es: null, rows: [], ids: new Set(), idOrder: [], starts: new Map(), finished: new Map(), connected: false, filter: 'all', paused: false,
              reloadTimer: null, lastKey: null, showAll: false, lastTs: null, lastCursor: null, lastAt: 0, backoff: 0, subs: new Set(),
              conn: 'connecting', connSubs: new Set(), fails: 0, downTimer: 0, asleep: false, hideTimer: 0 };
  const MAX = 200, SHOWN = 40, IDS = 5000;
  const KIND = {
    tool_usage_started: ['tool', 'stream.tool'], tool_usage_finished: ['tool', 'stream.tool'],
    task_started: ['task', 'stream.start'], task_completed: ['task', 'stream.done'], task_working: ['work', 'stream.working'], task_cancelled: ['task', 'stream.cancel'],
    task_deferred: ['task', 'stream.deferred'], task_reassessment_requested: ['task', 'stream.reassess'],
    human_asked: ['human', 'stream.asked'], human_response: ['human', 'stream.answered'], error: ['error', 'stream.error'],
  };
  const RELOAD_ON = new Set(['task_started', 'task_completed', 'task_cancelled', 'task_deferred', 'human_asked', 'human_response', 'error']);
  const noise = e => e.event_type === 'task_working' && e.data && e.data.type === 'run_start';

  function instName(id) {
    const I = window.hydInstances && window.hydInstances.I;
    const inst = I && I.instances.find(x => x.proc_inst_id === id);
    if (inst) return inst.proc_inst_name || id;
    if (!id) return '';
    return UI.defName(id);          // A141: 'anomaly_response.…' → 설비 이상 조치 (UI.terms def.*)
  }
  // 하루 수업 동안 탭을 열어 두어도 쌓이지 않게: 도구 시작 · 끝 · 단계 이름 기억은 id 기억(IDS)과 같은 상한, 오래된 것부터 버린다(W2-23)
  function bounded(map, key, value) { map.delete(key); map.set(key, value); if (map.size > IDS) map.delete(map.keys().next().value); }
  const activityByTodo = new Map();    // task_started carries the activity's goal; later events of the same work item reuse it
  function activityOf(e) {
    const I = window.hydInstances && window.hydInstances.I;
    const view = I && I.view;
    const w = view && view.workitems.find(x => x.id === e.todo_id);
    if (e.event_type === 'task_started' && e.data && (e.data.goal || e.data.name) && e.todo_id) bounded(activityByTodo, e.todo_id, e.data.goal || e.data.name);
    if (w) return UI.flowName(w.activity_name);
    return UI.flowName(activityByTodo.get(e.todo_id) || '');
  }
  const fmtMs = ms => window.hydTrace ? hydTrace.fmtMs(ms) : `${Math.round(ms)} ms`;
  function brief(v, n = 120) {
    if (v == null) return '';
    if (typeof v === 'string') return UI.clean(v.replace(/\s+/g, ' ')).slice(0, n);
    if (Array.isArray(v)) return `${v.length}건`;
    if (typeof v === 'object') {
      for (const k of ['query', 'sql', 'command', 'description', 'file_path', 'path']) if (typeof v[k] === 'string') return brief(v[k], n);
      return Object.keys(v).slice(0, 3).map(k => `${hydWords.fieldName(k)} ${typeof v[k] === 'object' ? '…' : UI.clean(String(v[k])).slice(0, 40)}`).join(' · ').slice(0, n);
    }
    return String(v).slice(0, n);
  }

  function describe(e) {
    const d = e.data || {};
    switch (e.event_type) {
      case 'tool_usage_started': return { title: UI.toolName(d.tool), text: hydWords.ask(d.tool, d.input), dur: S.finished.has(d.tool_use_id) ? '' : UI.t('inst.running'), running: !S.finished.has(d.tool_use_id) };
      case 'tool_usage_finished': {
        const started = S.starts.get(d.tool_use_id), o = UI.outcome(d.output, d.is_error);
        return { title: UI.toolName(d.tool), text: o.text || brief(d.output), dur: started ? fmtMs(new Date(e.timestamp) - started) : '', tone: o.tone };
      }
      case 'task_working': return { title: ['text','public_text'].includes(d.type) ? 'AI 에이전트 판단' : d.type === 'file_artifact' ? UI.t('trace.file') : UI.clean(UI.logText(d.name || '')) || UI.t('stream.working'),
        text: d.type === 'file_artifact' ? UI.baseName(d.path || '') : brief(d.content || d.message || '', 160) };
      case 'task_started': return { title: activityOf(e) || UI.t('step'), text: UI.t('trace.picked') };
      case 'task_completed': return { title: activityOf(e) || UI.t('step'), text: (d.output_keys || []).length ? UI.t('trace.outputs') + ' ' + d.output_keys.map(k => UI.terms['var.' + k] || hydWords.fieldName(k)).join(', ') : brief(d.text) };
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
    if (e.stream_cursor && (!S.lastCursor || e.stream_cursor > S.lastCursor)) S.lastCursor = e.stream_cursor;
    S.lastAt = Date.now();
    if (e.event_type === 'tool_usage_started' && e.data && e.data.tool_use_id) bounded(S.starts, e.data.tool_use_id, new Date(e.timestamp));
    if (e.event_type === 'tool_usage_finished' && e.data && e.data.tool_use_id) bounded(S.finished, e.data.tool_use_id, true);
    activityOf(e);
    if (!noise(e)) { S.rows.unshift({ e, fresh }); if (S.rows.length > MAX) S.rows.pop(); }
    // every subscriber gets every event (history too: a trace mounted after the event still wants it)
    if (window.hydTrace) hydTrace.onEvent(e);
    // 한 화면의 오류가 스트림을 멈추게 두지 않는다 — 다만 삼키지 않고 어느 구독 화면 · 어느 이벤트였는지 개발자 도구에 남긴다
    S.subs.forEach(fn => { try { fn(e, fresh); } catch (err) { console.error('[hydStream] 구독 화면 오류', fn.name || '(이름 없는 구독)', e.event_type, e.id, err); } });
    if (fresh && RELOAD_ON.has(e.event_type)) scheduleReload(e);
    if (fresh && !noise(e)) ticker(e);
    if (fresh && window.hydTaskDetail) window.hydTaskDetail.onEvent(e);   // U1: the open task panel takes its own task's events at once
    return true;
  }
  // 고른 처리 건의 이벤트만 상세를 강제로 다시 그린다. 다른 처리 건의 이벤트는 바뀐 것만(목록) 다시 그리는 보통 읽기 — 지금 쓰는 폼을 지우지 않는다
  function scheduleReload(e) {
    const I = window.hydInstances && window.hydInstances.I;
    const mine = !e || !e.proc_inst_id || !I || e.proc_inst_id === I.sel;
    S.reloadForce = S.reloadForce || mine;
    clearTimeout(S.reloadTimer);
    S.reloadTimer = setTimeout(() => { const force = S.reloadForce; S.reloadForce = false; if (window.hydInstances && state.tab === 'instances') window.hydInstances.load(force); }, 200);
  }

  /* 위 막대의 연결 상태 알약(#streamTicker): 점과 글은 연결 상태만 말한다 — 이어져 있으면 살아 있는 초록 점과 「실시간 연결됨」, 아니면 회색 점(끊김은 빨강)과 그 상태.
     방금 받은 활동은 알약을 누르면 펼쳐지는 판에 있다(알약의 글이 활동 이름으로 바뀌면 연결 상태가 가려지고, 다시 이어진 뒤에도 「끊김」이 남았다). */
  function paintTicker() {
    const t = document.getElementById('streamTicker'); if (!t) return;
    const { state, ok, text } = connOf(), last = S.lastSeen;
    const dot = ok ? ' data-tone="ok" data-live' : state === 'off' ? ' data-tone="danger"' : '';
    t.innerHTML = `<summary><i class="dot"${dot}></i><span>${esc(ok ? UI.t('header.waiting') : text)}</span></summary><div class="ticker-detail">${
      last ? `<p class="ticker-head">방금 받은 활동 · <span class="num">${esc(UI.time(last.at))}</span></p><p class="ticker-what"><b>${esc(last.label)}</b>${last.name ? ` · ${esc(last.name)}` : ''}</p>${last.body}`
        : `<p class="ticker-head">${esc(ok ? '아직 받은 활동이 없습니다. AI 에이전트나 시스템이 일하면 여기에 가장 최근 것이 보입니다.' : '연결되면 AI 에이전트와 시스템의 활동이 실시간으로 들어옵니다.')}</p>`}</div>`;
  }
  function ticker(e) {
    S.lastKey = e.id;
    const kind = KIND[e.event_type];
    const { title, text } = describe(e);
    const isTool=e.event_type==='tool_usage_started'||e.event_type==='tool_usage_finished';
    const raw=(e.data||{}).tool||'';
    const label=isTool ? (e.event_type==='tool_usage_started'?'도구 실행 중':(e.data?.is_error||e.data?.attempt_failed)?'도구 호출 실패':'도구 호출 완료') : kind ? UI.t(kind[1]) : UI.eventName(e.event_type);
    // 한 줄: 「종류 · 이름」(도구 이름은 포털 사전 하나(hydWords) — 사전에 없으면 서버 등록 이름. 종류와 이름이 같은 말이면 한 번만), 그 아래 보조 한 줄. 원래 도구 이름은 사전에 없는 도구일 때만 접어서
    const name=isTool ? UI.toolName(raw) : title !== label ? title : '';
    const more=isTool ? window.hydWords.toolSystem(raw) || '' : text || '';
    S.lastSeen = { at: e.timestamp || new Date().toISOString(), label, name, body: `${more ? `<p>${esc(more)}</p>` : ''}${isTool ? UI.toolIdentityFold(raw) : ''}` };
    paintTicker();
    if(isTool&&!window.hydWords.knownTool(raw)&&window.hydToolNames){
      window.hydToolNames.load().then(()=>{if(S.lastKey===e.id && S.connected) tickerNameRefresh(e);});
    }
  }
  function tickerNameRefresh(e) {
    if (S.lastSeen) { S.lastSeen.name = UI.toolName((e.data||{}).tool); paintTicker(); }
  }
  /* 연결 상태는 이 한 곳이 정한다 — 색만이 아니라 글자로: 연결 중 · 연결됨 · 다시 연결 중 · 끊김 · 쉬는 중(화면이 가려짐).
     「다시 연결 중」이 10초를 넘기거나 세 번 실패하면 「끊김」이라고 말한다(그래도 다시 연결은 계속 시도한다). 화면은 onConn 으로 받아
     끊긴 동안만 묻기(폴링)로 바꾸고 그 사실을 적는다(hydLive.agentWork). */
  Object.assign(UI.terms, { 'live.retry': '다시 연결 중', 'live.off': '끊김 · 다시 연결을 시도하는 중', 'live.paused': '화면이 가려져 쉬는 중' });
  const CONN_TEXT = { connecting: 'header.connecting', on: 'header.connected', retry: 'live.retry', off: 'live.off', paused: 'live.paused' };
  const connOf = () => ({ state: S.conn, ok: S.conn === 'on', text: UI.t(CONN_TEXT[S.conn]) });
  function setConn(state) {
    const changed = S.conn !== state;
    S.conn = state; S.connected = state === 'on';
    if (state === 'on' || state === 'paused' || state === 'connecting') { clearTimeout(S.downTimer); S.downTimer = 0; if (state === 'on') S.fails = 0; }
    else if (state === 'retry' && !S.downTimer) S.downTimer = setTimeout(() => { S.downTimer = 0; if (S.conn === 'retry') setConn('off'); }, 10000);
    const { text, ok } = connOf();
    const c = document.getElementById('streamConn'); if (c) { c.textContent = text; c.className = 'stream-conn ' + (ok ? 'on' : 'off'); }
    paintTicker();
    document.querySelectorAll('[data-live-conn]').forEach(n => { n.textContent = text; n.className = 'live-conn ' + (ok ? 'on' : state); });
    if (changed) S.connSubs.forEach(fn => { try { fn(connOf()); } catch (err) { console.error('[hydStream] 연결 상태 구독 화면 오류', fn.name || '(이름 없는 구독)', state, err); } });
  }

  /* ---------------------------------------------------------------- 전체 활동 목록 (처리 건 · 단계별 묶음) */
  function render() {
    const box = document.getElementById('streamList'); if (!box || S.paused) return;
    const merged = r => r.e.event_type === 'tool_usage_started' && r.e.data && S.finished.has(r.e.data.tool_use_id);   // started+finished = one row
    const publicRows = window.hydTrace ? hydTrace.publicNotes(S.rows.map(r=>r.e)).map(e=>({e,fresh:S.rows.some(r=>r.e.id===e.id && r.fresh)})) : S.rows;
    const rows = publicRows.filter(r => !merged(r)).filter(r => S.filter === 'all' ? true
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
      if (window.hydInstancesSelect) window.hydInstancesSelect(row.dataset.inst);
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
    clearTimeout(S.retryTimer); S.asleep = false;
    if (S.conn !== 'retry' && S.conn !== 'off') setConn('connecting');      // 끊긴 뒤의 재시도는 「다시 연결 중 · 끊김」 그대로 둔다
    // a reconnect we start ourselves resumes after the newest event we hold (the browser's own retry sends Last-Event-ID)
    const resume = S.lastCursor || S.lastTs;
    const es = new EventSource(API.process + '/api/events/stream' + (resume ? '?since=' + encodeURIComponent(resume) : ''));
    S.es = es;
    es.onopen = () => {
      S.backoff = 0; S.openedAt = Date.now(); setConn('on');
    };
    // 깨진 기록 줄 하나가 나머지를 막지 않게 건너뛰되, 건너뛴 줄은 개발자 도구에 남긴다
    es.addEventListener('history', ev => { try { push(JSON.parse(ev.data), false); } catch (err) { console.error('[hydStream] 지난 기록 줄을 읽지 못해 건너뜁니다', err, ev.data); } renderSoon(); });
    es.onmessage = ev => { let e; try { e = JSON.parse(ev.data); } catch (err) { console.error('[hydStream] 실시간 기록 줄을 읽지 못해 건너뜁니다', err, ev.data); return; } if (push(e, true)) renderSoon(); };
    // A147: a dropped connection (readyState CONNECTING) is retried by the browser itself (Last-Event-ID resumes it).
    // A non-200 answer (서버가 아직 준비 안 됨 503 · 프록시 502 …) closes the EventSource for good → our own backoff.
    es.onerror = () => {
      if (S.es !== es) return;                      // 우리가 닫은 옛 연결의 뒤늦은 오류
      if (es.readyState !== EventSource.CLOSED) { setConn(S.conn === 'off' ? 'off' : 'retry'); return; }
      es.close(); S.es = null;
      afterClose();
    };
  }
  function afterClose() {
    S.fails += 1;
    setConn(S.fails >= 3 || S.conn === 'off' ? 'off' : 'retry');
    S.backoff = Math.min(30000, (S.backoff || 1000) * 2);
    clearTimeout(S.retryTimer); S.retryTimer = setTimeout(connect, S.backoff);
  }
  // 지킴이: the 2-second instance poll saw events the stream never delivered → the stream is stuck; reopen it from our last id.
  // It also feeds those events to the bus so nothing is missing in the meantime.
  function fromPoll(events) {
    if (!Array.isArray(events) || !events.length) return;
    const newest = events.reduce((m, e) => (e.timestamp && e.timestamp > m ? e.timestamp : m), '');
    const behind = S.lastTs && newest > S.lastTs && (Date.parse(newest) - Date.parse(S.lastTs)) > 10000;
    if (behind && S.connected && Date.now() - (S.openedAt || 0) > 15000) { connect(); }
  }
  // 가려진 화면(다른 창 · 다른 브라우저 탭)은 30초 뒤 구독을 멈춘다 — 보지 않는 탭이 연결을 쥐고 있지 않게. 돌아오면 마지막으로 받은 자리(since)부터
  // 다시 열어 그사이 기록을 이어 받는다(같은 id 는 한 번만 — push 의 중복 제거).
  function sleep() {
    if (document.visibilityState !== 'hidden') return;
    if (S.es) { S.es.close(); S.es = null; }
    clearTimeout(S.retryTimer); S.asleep = true; setConn('paused');
  }
  document.addEventListener('visibilitychange', () => {
    clearTimeout(S.hideTimer);
    if (document.visibilityState === 'hidden') { S.hideTimer = setTimeout(sleep, 30000); return; }
    if (S.asleep || !S.es || S.es.readyState === EventSource.CLOSED) connect();
  });

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
  // onConn(fn): fn({state, ok, text}) — 연결 상태가 바뀔 때마다. 지금 상태는 conn()
  const onConn = fn => { S.connSubs.add(fn); return () => S.connSubs.delete(fn); };
  window.hydStream = { S, render, subscribe, fromPoll, push, connected: () => S.connected, conn: connOf, onConn, connect };
})();

/* 실시간 표시의 공용 부품 — window.hydLive. 오래 걸리는 일을 「도는 고리 + …중」으로 두지 않고, 지금 무엇을 하는지와 얼마나 됐는지를 보인다.
   모든 화면이 위의 연결 하나(hydStream)와 처리 과정 그리기(hydTrace)를 함께 쓴다 — 화면마다 따로 구독하지 않는다.

   - waitHtml(글, {since, hint, late})  한 번에 결과만 오는 일: 「글 · 걸린 시간」, late 초(기본 3)가 지나면 「아직 하는 중입니다 — hint」 한 줄.
   - busy(단추, 글, since)              누른 단추가 「글 · 걸린 시간」으로 바뀐다. 돌려준 함수를 부르면 원래대로. 다시 그린 단추에는 since 를 넘겨 시간을 잇는다.
   - steps(자리, [{key, label}])        여러 단계인 일: 단계 목록이 하나씩 채워진다(start · done · fail · skip).
   - track({글, hint})                  서버가 단계를 적어 주는 일(판단 채점 · 시험 비교 · 출발본 · 도구 서버 연결 검사): 요청에 request_id 를 싣고,
                                        도는 동안 서버의 진행 기록(GET /api/progress/{id})을 1초마다 읽어 단계 목록을 채운다. 요청이 끝나면 stop().
   - follow(자리, 단계들)               다른 화면에서 이어지는 일(결함 주입 → 경보 → 처리 건): 다음 사실을 기다려 한 줄씩 그린다.
   - agentWork(자리, 설정)              AI 에이전트가 처리 건의 한 단계로 하는 일(문서 추출 · 질문 확인 · 뜻 후보): 도구 호출 · 에이전트의 말이
                                        생기는 대로 흘러나온다. 연결이 끊긴 동안만 묻기(폴링)로 바꾸고 그 사실을 적는다. 가려지면 멈추고 돌아오면 이어 받는다.
   서버가 주지 않는 진행률은 그리지 않는다 — 모르면 걸린 시간만 보인다. */
(function () {
  const fmt = ms => hydTrace.fmtMs(Math.max(0, ms));
  const spin = () => hydTrace.spinner('sm');
  const iso = () => new Date().toISOString();
  const timeHtml = since => `<span class="lv-time" data-since="${esc(since)}">${esc(fmt(Date.now() - Date.parse(since)))}</span>`;   // 글자는 trace.js 의 1초 시계가 올린다
  const lateHtml = (since, hint, late = 3) => {
    if (!hint) return '';
    const at = Date.parse(since) + late * 1000;
    return `<span class="lv-late" data-late-at="${at}"${Date.now() >= at ? '' : ' hidden'}>아직 하는 중입니다 — ${esc(hint)}</span>`;
  };
  setInterval(() => {                                   // 「아직 하는 중」 줄은 때가 되면 나타난다(다시 그리지 않고)
    if (typeof document === 'undefined' || !document.querySelectorAll) return;
    const now = Date.now();
    document.querySelectorAll('.lv-late[hidden]').forEach(n => { if (now >= Number(n.dataset.lateAt)) n.hidden = false; });
  }, 500);

  function waitHtml(text, o = {}) {
    const since = o.since || iso();
    return `<div class="lv-wait${o.cls ? ' ' + esc(o.cls) : ''}" role="status" aria-live="polite"><span class="lv-wait-line">${spin()}<b>${esc(text)}</b>${timeHtml(since)}</span>${lateHtml(since, o.hint, o.late)}</div>`;
  }
  function busy(btn, label, since) {
    if (!btn) return () => {};
    const was = { html: btn.innerHTML, disabled: btn.disabled };
    btn.disabled = true; btn.setAttribute('aria-busy', 'true'); btn.classList.add('lv-busy');
    btn.innerHTML = `${spin()}<span>${esc(label)}</span>${timeHtml(since || iso())}`;
    return disabled => {
      if (!btn.classList.contains('lv-busy')) return;
      btn.innerHTML = was.html; btn.removeAttribute('aria-busy'); btn.classList.remove('lv-busy'); btn.disabled = disabled == null ? was.disabled : !!disabled;
    };
  }

  /* ---------------------------------------------------------------- 단계 목록 */
  const MARK = { ok: 'check', fail: 'x', skip: 'x' };
  function steps(host, defs, o = {}) {
    const C = { host, list: defs.map(d => ({ key: d.key, label: d.label, note: d.note || '', state: 'wait', t0: null, t1: null, hint: d.hint || '', link: null })), go: new Map() };
    const find = key => C.list.find(s => s.key === key);
    function stepHtml(s, i) {
      const mark = s.state === 'run' ? spin() : MARK[s.state] ? hydTrace.icon(MARK[s.state]) : `<i>${i + 1}</i>`;
      const time = s.state === 'run' && s.t0 ? timeHtml(s.t0) : s.t0 && s.t1 ? `<span class="lv-time">${esc(fmt(Date.parse(s.t1) - Date.parse(s.t0)))}</span>` : '';
      const link = s.link ? `<button type="button" class="link-btn" data-lv-go="${esc(s.key)}">${esc(s.link.text)}</button>` : '';
      return `<li class="lv-step ${s.state}" data-step="${esc(s.key)}"${s.state === 'run' ? ' aria-current="step"' : ''}><span class="lv-mark">${mark}</span>` +
        `<div class="lv-step-main"><b>${esc(s.label)}</b>${s.note ? `<span class="lv-note">${esc(s.note)}</span>` : ''}${s.state === 'run' ? lateHtml(s.t0, s.hint) : ''}${link}</div>${time}</li>`;
    }
    function draw() { host.innerHTML = `<ol class="lv-steps" aria-label="${esc(o.label || '진행 단계')}">${C.list.map(stepHtml).join('')}</ol>`; }
    function set(key, state, more = {}) {
      const s = find(key); if (!s) throw new Error(`단계 목록에 없는 단계입니다: ${key}`);
      if (state === 'run') { s.t0 = iso(); s.t1 = null; } else if (state !== 'wait') { s.t0 = s.t0 || iso(); s.t1 = iso(); }
      if (more.t0) s.t0 = more.t0;                                   // 서버가 적은 시각(track) — 화면이 읽은 때가 아니라 일이 시작 · 끝난 때
      if (more.t1 && state !== 'run') s.t1 = more.t1;
      Object.assign(s, { state }, more.label != null ? { label: more.label } : {}, more.note != null ? { note: more.note } : {}, more.hint != null ? { hint: more.hint } : {});
      if (more.link) { s.link = more.link; C.go.set(key, more.link); }
      draw();
    }
    host.addEventListener('click', e => { const b = e.target.closest('[data-lv-go]'); const l = b && C.go.get(b.dataset.lvGo); if (l && l.go) l.go(); });
    Object.assign(C, { start: (k, m) => set(k, 'run', m), done: (k, m) => set(k, 'ok', m), fail: (k, m) => set(k, 'fail', m), skip: (k, m) => set(k, 'skip', m),
      note: (k, note) => { const s = find(k); if (s && s.note !== note) { s.note = note; draw(); } }, state: k => (find(k) || {}).state, since: k => (find(k) || {}).t0 });
    draw();
    return C;
  }

  /* ---------------------------------------------------------------- 서버가 적는 진행 기록 따라 읽기
     서버는 일의 실제 경계에서만 단계의 시작 · 끝 · 실패를 적는다(procsvc/progress.py). 화면은 그 기록을 읽어 그대로 그린다 — 진행률을 지어내지 않는다.
       const T = hydLive.track({ text: '기준으로 되돌리는 중', hint });   T.mount(자리);
       try { await postJ(url, { …, request_id: T.id }); } finally { T.stop(); }
     - 요청이 서버에 닿기 전(기록 없음)에는 「글 · 걸린 시간」만 보이고, 기록이 생기면 그 아래에 단계 목록이 채워진다. 일하다 알게 된 단계는 뒤에 붙는다.
     - 화면이 다시 그려져 자리가 바뀌면 새 자리에 다시 mount 한다(같은 목록이 옮겨 간다). 자리가 화면에 없거나 화면이 가려진 동안은 읽지 않는다.
     - 기록을 읽지 못하면 그 사실을 한 줄로 적고 다시 읽는다 — 본 요청은 그대로 돌고, 결과는 부른 화면이 그대로 보인다.
     - 읽기는 stop() 이나 서버 기록의 끝(done · failed)에서 멈춘다. 부른 화면은 요청이 끝나는 자리(finally)에서 stop() 을 부른다. */
  function track(o = {}) {
    const T = { id: UI.uuid(), since: o.since || iso(), stopped: false, ended: false, reading: false, timer: 0, keys: null, list: null, seen: {}, reads: 0 };
    const root = document.createElement('div'); root.className = 'lv-track';
    root.innerHTML = waitHtml(o.text || '', { since: T.since, hint: o.hint }) + '<div data-lv-track-steps></div><p class="lv-work-conn" data-lv-track-err role="status" hidden></p>';
    const box = root.querySelector('[data-lv-track-steps]'), err = root.querySelector('[data-lv-track-err]');
    function apply(rec) {
      const keys = rec.steps.map(s => s.key).join('\n');
      if (keys !== T.keys) {                                         // 단계가 생겼거나 늘었다 — 목록을 다시 세우고 지금까지의 상태를 다시 적는다
        T.keys = keys; T.seen = {};
        const inner = document.createElement('div'); box.replaceChildren(inner);
        T.list = rec.steps.length ? steps(inner, rec.steps.map(s => ({ key: s.key, label: s.label })), { label: o.label || '진행 단계' }) : null;
      }
      rec.steps.forEach(s => {
        const sig = [s.state, s.label, s.note, s.started_at, s.ended_at].join('|');
        if (T.seen[s.key] === sig) return;
        T.seen[s.key] = sig;
        const more = { label: s.label, note: s.note || '', t0: s.started_at, t1: s.ended_at };
        if (s.state === 'run') T.list.start(s.key, more); else if (s.state === 'ok') T.list.done(s.key, more); else if (s.state === 'fail') T.list.fail(s.key, more);
      });
      if (rec.state === 'done' || rec.state === 'failed') { T.ended = true; clearInterval(T.timer); T.timer = 0; }
    }
    async function read() {
      if (T.stopped || T.ended || T.reading || !root.isConnected || document.visibilityState === 'hidden') return;
      T.reading = true;
      try {
        const rec = await getJ(API.process + '/api/progress/' + encodeURIComponent(T.id));
        T.reads += 1;
        if (!T.stopped) apply(rec);
        err.hidden = true; err.textContent = '';
      } catch (e) {
        err.hidden = false; err.textContent = `진행 상황을 읽지 못했습니다(${e.message}). 요청은 그대로 진행 중이고, 끝나면 결과가 보입니다.`;
      } finally { T.reading = false; }
    }
    T.mount = host => {
      if (!host) return T;
      host.replaceChildren(root);
      if (!T.timer && !T.stopped && !T.ended) { T.timer = setInterval(read, o.every_ms || 1000); read(); }
      return T;
    };
    T.stop = () => { T.stopped = true; clearInterval(T.timer); T.timer = 0; };
    return T;
  }

  /* ---------------------------------------------------------------- 이어지는 일 따라가기
     stages: [{ key, label(기다리는 말), hint, check(앞 단계의 사실) → 사실 | null (async 가능), done(사실) → 끝난 말, note(사실) → 둘째 줄,
                link(사실) → {text, go()}, timeout_s, timeoutText }]
     1초마다 지금 단계의 check 만 부른다(가려진 화면에서는 부르지 않고, 돌아오면 이어서 확인한다). 자리가 화면에서 사라지면 스스로 멈춘다.
     check 가 실패하면 그 사유를 그 줄에 적고 다시 확인한다(삼키지 않는다). */
  function follow(host, stages, o = {}) {
    const list = steps(host, stages.map(s => ({ key: s.key, label: s.label, hint: s.hint })), { label: o.label || '이어지는 과정' });
    const F = { list, i: 0, fact: o.start, stopped: false, checking: false, timer: 0 };
    F.stop = () => { F.stopped = true; clearInterval(F.timer); };
    async function tick() {
      if (F.stopped || F.checking) return;
      if (!host.isConnected) { F.stop(); return; }
      if (document.visibilityState === 'hidden') return;
      const s = stages[F.i]; F.checking = true;
      try {
        const got = await s.check(F.fact);
        if (F.stopped) return;
        if (got) {
          F.fact = got;
          list.done(s.key, { label: s.done ? s.done(got) : s.label, note: s.note ? s.note(got) : '', link: s.link ? s.link(got) : null });
          F.i += 1;
          if (F.i < stages.length) list.start(stages[F.i].key); else { F.stop(); if (o.onDone) o.onDone(got); }
        } else if (s.timeout_s && Date.now() - Date.parse(list.since(s.key)) > s.timeout_s * 1000) {
          list.fail(s.key, { note: s.timeoutText || `${s.timeout_s}초를 기다렸지만 아직 일어나지 않았습니다.` }); F.stop();
        } else list.note(s.key, '');
      } catch (e) { list.note(s.key, `확인하지 못했습니다(${e.message}) — 다시 확인합니다`); }
      finally { F.checking = false; }
    }
    list.start(stages[0].key);
    F.timer = setInterval(tick, o.every_ms || 1000); tick();
    return F;
  }

  /* ---------------------------------------------------------------- AI 에이전트가 하는 일(처리 건의 한 단계)을 실시간으로
     agentWork(host, { tab, pollMs, onChange }) → W.  W.set({ items: [{id(작업 행), instance, label, state, stateText}], running, since, headline, note })
     - 작업 행마다 처리 과정 한 칸(hydTrace 의 줄 그리기 — 질문하기와 같은 것). 줄은 연결 하나(hydStream)에서 온다.
     - 단계가 바뀌는 이벤트(시작 · 끝 · 실패 · 사람 질문)가 오면 그 작업 행을 다시 읽고 onChange 를 부른다(부르는 화면이 결과를 다시 읽는다).
     - 연결이 끊긴 동안만 pollMs 마다 다시 읽고, 그 사실을 화면에 적는다. 다시 연결되면 묻기를 멈춘다.
     - 가려지면(다른 메뉴 · 다른 창) 받기를 멈추고, 돌아오면 작업 행을 다시 읽어 그사이 기록을 이어 받는다. */
  const WORKS = new Set();
  const STEP_EVENTS = new Set(['task_started', 'task_completed', 'task_cancelled', 'task_deferred', 'task_reassessment_requested', 'human_asked', 'human_response', 'error']);
  const tabNow = () => (typeof state === 'object' && state ? state.tab : '');
  function agentWork(host, o = {}) {
    const pollMs = o.pollMs || 5000;
    const W = { host, items: [], running: false, since: null, headline: '', note: '', segs: new Map(), awake: false, poll: 0, changeTimer: 0, stopped: false };
    host.classList.add('lv-work');
    host.innerHTML = `<div class="lv-work-head"><span class="lv-now" data-lv-now></span><span class="lv-work-tools"><span class="live-conn" data-live-conn></span>` +
      `<button type="button" class="btn ghost small" data-lv-refresh>지금 확인</button></span></div><p class="lv-work-note" data-lv-note hidden></p><p class="lv-work-conn" data-lv-conn role="status" hidden></p><div class="lv-work-body" data-lv-body></div>`;
    const q = sel => host.querySelector(sel);
    const awakeNow = () => !W.stopped && document.visibilityState !== 'hidden' && (!o.tab || tabNow() === o.tab);
    const live = it => W.running && !['done', 'fail', 'stop'].includes(it.state);

    function drawHead() {
      const c = hydStream.conn();
      q('[data-live-conn]').textContent = c.text; q('[data-live-conn]').className = 'live-conn ' + (c.ok ? 'on' : c.state);
      const now = (W.running ? spin() : '') + `<b>${esc(W.headline)}</b>` + (W.since && W.running ? timeHtml(W.since) : '');
      const nowBox = q('[data-lv-now]'); if (nowBox._html !== now) { nowBox.innerHTML = now; nowBox._html = now; }
      const note = q('[data-lv-note]'); note.hidden = !W.note; note.textContent = W.note || '';
      const lost = W.running && W.awake && (c.state === 'retry' || c.state === 'off');
      const cn = q('[data-lv-conn]'); cn.hidden = !lost;
      cn.textContent = lost ? `실시간 연결이 끊겨 ${Math.round(pollMs / 1000)}초마다 확인합니다. 다시 연결되면 바로 이어서 보입니다.` : '';
      q('[data-lv-refresh]').hidden = !W.running;
    }
    function segOf(it) {
      let seg = W.segs.get(it.id);
      if (seg) return seg;
      // 작업 행 하나 = 접히는 한 줄. 도는 동안과 멈췄을 때는 펼쳐 기록이 보이고, 끝나면 한 줄로 접힌다(사람이 여닫은 뒤에는 그대로 둔다)
      const node = document.createElement('details'); node.className = 'lv-seg'; node.dataset.wid = it.id; node.open = true;
      node.innerHTML = `<summary class="lv-seg-head" data-lv-seg-head></summary><p class="field-error" data-lv-seg-err role="alert" hidden></p><p class="lv-work-note" data-lv-seg-none hidden>이 단계에는 남은 실행 기록이 없습니다.</p><div class="lv-log" data-lv-log tabindex="0" aria-label="처리 과정"></div>`;
      const traceHost = document.createElement('div');
      node.querySelector('[data-lv-log]').append(traceHost);
      node.querySelector('summary').addEventListener('click', () => { seg.byHand = true; });
      seg = { node, item: null, err: '', byHand: false, trace: hydTrace.mount(traceHost, { flat: true, workitem: () => it.id, detachedOk: true, shown: 200 }) };
      W.segs.set(it.id, seg);
      return seg;
    }
    const SEG_STATE = { wait: '차례를 기다리는 중', run: '하는 중', done: '끝남', fail: '실패', stop: '멈춤' };
    function drawSegs() {
      const body = q('[data-lv-body]');
      W.items.forEach((it, i) => {
        const seg = segOf(it);
        if (body.children[i] !== seg.node) body.insertBefore(seg.node, body.children[i] || null);
        const head = seg.node.querySelector('[data-lv-seg-head]');
        const alone = W.items.length < 2 && !it.label;
        head.hidden = alone;
        if (alone) seg.node.open = true; else if (!seg.byHand) seg.node.open = live(it) && it.state !== 'wait' || it.state === 'fail' || it.state === 'stop';
        const t0 = seg.item && seg.item.start_date, t1 = seg.item && seg.item.end_date;
        const time = live(it) && t0 ? timeHtml(t0) : t0 && t1 ? `<span class="lv-time">${esc(fmt(Date.parse(t1) - Date.parse(t0)))}</span>` : '';
        const html = `<b>${esc(it.label || '')}</b><span class="lv-seg-state ${esc(it.state || '')}">${esc(it.stateText || SEG_STATE[it.state] || '')}</span>${time}`;
        if (head._html !== html) { head.innerHTML = html; head._html = html; }
        seg.node.dataset.state = it.state || '';
        const none = !live(it) && !!seg.item && !(seg.item.events || []).length;      // 끝난 단계인데 기록이 없다(저장된 결과로 끝난 추출 등) — 빈 기록 칸 대신 그 사실을 말한다
        seg.node.querySelector('[data-lv-seg-none]').hidden = !none; seg.node.querySelector('[data-lv-log]').hidden = none;
        const err = seg.node.querySelector('[data-lv-seg-err]'); err.hidden = !seg.err; err.textContent = seg.err ? `처리 과정을 읽지 못했습니다 — ${seg.err}` : '';
      });
      [...W.segs.keys()].filter(id => !W.items.some(it => it.id === id)).forEach(id => { const seg = W.segs.get(id); hydTrace.TR.mounted.delete(seg.trace); seg.node.remove(); W.segs.delete(id); });
    }
    function feed(it) {
      const seg = W.segs.get(it.id); if (!seg || !seg.item) return;
      if (W.awake) hydTrace.TR.mounted.add(seg.trace);
      seg.trace.update({ instance: { status: live(it) ? 'RUNNING' : 'COMPLETED' }, definition: { activities: [] }, workitems: [seg.item], events: seg.item.events || [] });
    }
    async function load(it) {
      const seg = segOf(it);
      try { seg.item = await getJ(API.process + '/api/todolist/' + encodeURIComponent(it.id)); seg.err = ''; }
      catch (e) { seg.err = e.message; }
      if (W.stopped) return;
      feed(it); drawSegs();
    }
    const loadAll = () => Promise.all(W.items.map(load));
    function changed() { clearTimeout(W.changeTimer); W.changeTimer = setTimeout(() => { if (!W.stopped && o.onChange) o.onChange(); }, 300); }
    function setPoll() {
      const c = hydStream.conn();
      const need = W.awake && W.running && (c.state === 'retry' || c.state === 'off');
      if (need && !W.poll) W.poll = setInterval(() => { loadAll(); changed(); }, pollMs);
      if (!need && W.poll) { clearInterval(W.poll); W.poll = 0; }
      drawHead();
    }
    function wake() {
      const want = awakeNow();
      if (want === W.awake) return;
      W.awake = want;
      W.segs.forEach(seg => { if (want) hydTrace.TR.mounted.add(seg.trace); else hydTrace.TR.mounted.delete(seg.trace); });
      if (want && W.running) { loadAll(); changed(); }    // 돌아왔다: 그사이 기록을 이어 받는다
      setPoll();
    }
    W.wake = wake;
    W.offBus = hydStream.subscribe(e => {
      if (!W.awake || !e) return;
      const it = W.items.find(x => x.id === e.todo_id) || (e.proc_inst_id && W.items.find(x => x.instance === e.proc_inst_id));
      if (!it || !STEP_EVENTS.has(e.event_type)) return;
      load(it); changed();
    });
    W.offConn = hydStream.onConn(c => { if (c.ok && W.awake && W.running) { loadAll(); changed(); } setPoll(); });
    q('[data-lv-refresh]').addEventListener('click', () => { loadAll(); changed(); });
    W.set = next => {
      const before = W.items.map(it => it.id).join('|');
      Object.assign(W, { items: next.items || [], running: !!next.running, since: next.since || W.since, headline: next.headline || '', note: next.note || '' });
      W.awake = awakeNow();
      drawSegs(); drawHead(); setPoll();
      if (W.items.map(it => it.id).join('|') !== before) loadAll(); else W.items.forEach(feed);
    };
    W.reload = loadAll;
    W.stop = () => { W.stopped = true; W.awake = false; clearInterval(W.poll); W.poll = 0; clearTimeout(W.changeTimer); W.offBus(); W.offConn(); W.segs.forEach(seg => hydTrace.TR.mounted.delete(seg.trace)); WORKS.delete(W); };
    WORKS.add(W);
    return W;
  }
  document.addEventListener('visibilitychange', () => WORKS.forEach(W => W.wake()));
  if (window.hydTabs) hydTabs.onShow(() => WORKS.forEach(W => W.wake()));

  window.hydLive = { waitHtml, busy, steps, track, follow, agentWork, timeHtml, WORKS };
})();
