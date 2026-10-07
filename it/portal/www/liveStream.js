/* A091 — 실시간 이벤트 스트림. process 의 GET /api/events/stream (server-sent events) 을 구독해 에이전트 도구 호출 · 작업 전이 ·
   사람의 답변 · 오류가 생기는 즉시 보여 준다. 2초 폴링을 대체하지 않고 앞에 둔다: 스트림이 작업 전이를 알리면 인스턴스 화면을 바로 새로 읽는다.
   events 테이블의 행을 그대로 쓴다(ProcessGPT 와 같은 event_type · crew_type · data). */
(function () {
  const S = { es: null, rows: [], byId: new Set(), starts: {}, connected: false, filter: 'all', paused: false, reloadTimer: null, lastKey: null };
  const MAX = 160;
  const KIND = {
    tool_usage_started: ['tool', '도구 호출'], tool_usage_finished: ['tool', '도구 결과'],
    task_started: ['task', '작업 시작'], task_completed: ['task', '작업 완료'], task_working: ['work', '진행'], task_cancelled: ['task', '작업 취소'],
    task_deferred: ['task', '보류'], task_reassessment_requested: ['task', '재평가 요청'],
    human_asked: ['human', '사람에게 질문'], human_response: ['human', '사람의 답변'], error: ['error', '오류'],
  };
  const RELOAD_ON = new Set(['task_started', 'task_completed', 'task_cancelled', 'task_deferred', 'human_asked', 'human_response', 'error']);

  function instName(id) {
    const I = window.hydInstances && window.hydInstances.I;
    const inst = I && I.instances.find(x => x.proc_inst_id === id);
    if (inst) return inst.proc_inst_name || id;
    if (!id) return '';
    return id.split('.')[0].replace(/_/g, ' ') + ' · ' + id.slice(-6);
  }
  const activityByTodo = {};          // task_started carries the activity's goal; later events of the same work item reuse it
  function activityOf(e) {
    const I = window.hydInstances && window.hydInstances.I;
    const view = I && I.view;
    const w = view && view.workitems.find(x => x.id === e.todo_id);
    if (w) return w.activity_name;
    if (e.event_type === 'task_started' && e.data && (e.data.goal || e.data.name) && e.todo_id) activityByTodo[e.todo_id] = e.data.goal || e.data.name;
    return activityByTodo[e.todo_id] || (e.data && e.event_type === 'task_started' && (e.data.goal || e.data.name)) || '';
  }
  function shortTool(t) { return String(t || '').replace(/^mcp__/, '').replace(/__/g, ' · '); }
  function fmtMs(ms) { return ms < 1000 ? `${Math.round(ms)} ms` : ms < 60000 ? `${(ms / 1000).toFixed(1)} s` : `${Math.floor(ms / 60000)}분 ${Math.round((ms % 60000) / 1000)}초`; }

  function describe(e) {
    const d = e.data || {};
    switch (e.event_type) {
      case 'tool_usage_started': return { title: shortTool(d.tool), text: d.input ? JSON.stringify(d.input).slice(0, 140) : '' };
      case 'tool_usage_finished': {
        const started = S.starts[d.tool_use_id];
        const dur = started ? fmtMs(new Date(e.timestamp) - started) : '';
        return { title: shortTool(d.tool), text: typeof d.output === 'string' ? d.output.slice(0, 140) : d.output ? JSON.stringify(d.output).slice(0, 140) : '', dur };
      }
      case 'task_working': return { title: d.type === 'usage' ? '모델 응답 중' : (d.name || d.type || '진행'), text: d.content || d.message || (d.usage ? `토큰 입력 ${d.usage.input_tokens ?? '–'} · 출력 ${d.usage.output_tokens ?? '–'}` : '') };
      case 'task_started': return { title: activityOf(e) || d.name || '작업', text: d.goal || d.agent || '' };
      case 'task_completed': return { title: activityOf(e) || '작업', text: (d.output_keys || []).length ? '출력 ' + d.output_keys.join(', ') : (d.text || '').slice(0, 140) };
      case 'task_cancelled': {                     // A098: three different things used to look identical in the stream
        if (e.job_id === 'TASK_CANCEL_REQUESTED') return { title: '실행 취소 요청 (사람)', text: (d.goal || '').slice(0, 160) };
        if (e.job_id === 'TASK_CLOSED') return { title: '작업 닫음 (사람)', text: (d.goal || d.reason || '').slice(0, 160) };
        return { title: (activityOf(e) || '작업') + ' · 워커가 실행을 멈춤', text: (d.goal || '').slice(0, 160) };
      }
      case 'human_asked': return { title: '사람에게 질문', text: humanQuestionText(d).slice(0, 160) };
      case 'human_response': return { title: '사람의 답변', text: (d.answer || '').slice(0, 160) };
      case 'error': return { title: d.name || '오류', text: (d.friendly || d.raw_error || d.message || '').slice(0, 160) };
      default: return { title: e.event_type, text: d.message || d.note || d.content || '' };
    }
  }

  function push(e, fresh) {
    if (!e || !e.id || S.byId.has(e.id)) return;
    S.byId.add(e.id);
    if (e.event_type === 'tool_usage_started' && e.data && e.data.tool_use_id) S.starts[e.data.tool_use_id] = new Date(e.timestamp);
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
    const [, label] = KIND[e.event_type] || ['', e.event_type];
    const { title } = describe(e);
    t.innerHTML = `<i class="live-dot ${KIND[e.event_type] ? KIND[e.event_type][0] : ''}"></i><span>${esc(label)}</span><b>${esc(title)}</b>`;
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
    const rows = S.rows.filter(r => S.filter === 'all' ? !isUsage(r)
      : S.filter === 'work' ? (KIND[r.e.event_type] || [''])[0] === 'work'
      : (KIND[r.e.event_type] || [''])[0] === S.filter || (S.filter === 'task' && !KIND[r.e.event_type]));
    if (!rows.length) { box.innerHTML = '<div class="stream-empty">아직 흐르는 이벤트가 없습니다. 결함을 주입하면 에이전트의 도구 호출이 여기에 실시간으로 나타납니다.</div>'; return; }
    box.innerHTML = rows.slice(0, 80).map(({ e, fresh }) => {
      const [cls, label] = KIND[e.event_type] || ['task', UI.eventNames[e.event_type] || e.event_type];
      const { title, text, dur } = describe(e);
      const act = activityOf(e);
      return `<div class="stream-row ${cls}${fresh ? ' new' : ''}" data-inst="${esc(e.proc_inst_id || '')}" tabindex="0">
        <time title="${esc(UI.dateTime(e.timestamp))}">${esc(UI.time(e.timestamp))}</time>
        <span class="kind">${esc(label)}</span>
        <div class="body"><b>${esc(title)}</b>${text ? `<span class="txt">${esc(text)}</span>` : ''}</div>
        <span class="where">${esc(instName(e.proc_inst_id))}${act ? ' · ' + esc(act) : ''}</span>
        ${dur ? `<span class="dur">${esc(dur)}</span>` : ''}
      </div>`;
    }).join('');
    S.rows.forEach(r => { r.fresh = false; });
    box.querySelectorAll('.stream-row[data-inst]').forEach(row => row.addEventListener('click', () => { if (row.dataset.inst && window.hydInstancesSelect) window.hydInstancesSelect(row.dataset.inst); }));
    const count = document.getElementById('streamCount'); if (count) count.textContent = `${S.rows.length}건`;
  }

  function connect() {
    if (S.es) { S.es.close(); S.es = null; }
    connState('연결 중…', false);
    const es = new EventSource(API.process + '/api/events/stream');
    S.es = es;
    es.onopen = () => {
      S.connected = true; connState('실시간 연결됨', true);
      const t = document.getElementById('streamTicker');
      if (t && !S.lastKey) t.innerHTML = '<i class="live-dot on"></i><span>실시간 연결됨 · 이벤트 대기</span>';
    };
    es.addEventListener('history', ev => { try { push(JSON.parse(ev.data), false); } catch (e) { /* ignore a bad frame */ } render(); });
    es.onmessage = ev => { try { push(JSON.parse(ev.data), true); } catch (e) { return; } render(); };
    es.onerror = () => { S.connected = false; connState('끊김 · 재연결 중', false); };   // EventSource reconnects by itself; ids keep the list deduplicated
  }

  function mount() {
    const box = document.getElementById('streamPanel'); if (!box) return;
    box.innerHTML = `<div class="stream-head"><div><h3>실시간 에이전트 스트림 <small id="streamCount"></small></h3><span class="muted">events 테이블의 행이 생기는 즉시 서버가 밀어 줍니다 (server-sent events)</span></div>
      <div class="stream-tools"><span id="streamConn" class="stream-conn off">연결 중…</span>
        <div class="chips small" id="streamFilter">${[['all', '전체'], ['tool', '도구'], ['task', '작업'], ['human', '사람'], ['error', '오류'], ['work', '진행·토큰']].map(([k, l]) => `<button class="chip${k === 'all' ? ' on' : ''}" data-f="${k}" type="button">${l}</button>`).join('')}</div>
        <button class="btn small" id="streamPause" type="button" aria-pressed="false">멈춤</button></div></div>
      <div class="stream-list" id="streamList"></div>`;
    box.querySelectorAll('#streamFilter .chip').forEach(c => c.addEventListener('click', () => {
      S.filter = c.dataset.f; box.querySelectorAll('#streamFilter .chip').forEach(x => x.classList.toggle('on', x === c)); render();
    }));
    const pause = document.getElementById('streamPause');
    pause.addEventListener('click', () => { S.paused = !S.paused; pause.textContent = S.paused ? '다시 흐르게' : '멈춤'; pause.setAttribute('aria-pressed', String(S.paused)); if (!S.paused) render(); });
    render();
    connect();
  }
  document.addEventListener('DOMContentLoaded', mount);
  if (document.readyState !== 'loading') mount();
  window.hydStream = { S, render };
})();
