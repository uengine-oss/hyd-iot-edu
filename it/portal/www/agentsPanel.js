/* U1 — 지금 일하는 AI 일꾼 (처리 건 탭, 접힘). GET /api/agents/status (일꾼 서비스의 /health · 설치된 CLI) 와
   GET /api/todolist?status=IN_PROGRESS&agent_orch=cliagents (일꾼이 잡고 있는 단계: consumer 가 임대한 행) 를 5초마다 읽는다.
   vue3 에는 전역 일꾼 현황 화면이 없다(단계별 agent-monitor 탭뿐) — 회의 L434 "어떤 에이전트들이 지금 동작하고 있다" 를 위해 둔다.
   누르면 그 처리 건의 흐름 탭을 열고 task 상세 패널(taskDetail.js)로 이어진다. 폴백 없음: 일꾼이 안 닿으면 그 사유를 그대로 보인다. */
(function () {
  const A = { status: null, rows: [], err: null, sig: null };
  Object.assign(UI.terms, {
    'agents.title': '지금 일하는 AI 일꾼', 'agents.service': '일꾼 서비스', 'agents.up': '연결됨', 'agents.down': '연결 안 됨', 'agents.inFlight': '실행 중',
    'agents.handled': '처리', 'agents.polls': '폴링', 'agents.lastPoll': '마지막 폴링', 'agents.never': '아직 없음', 'agents.url': '주소', 'agents.clis': '설치된 코딩 에이전트',
    'agents.worker': '일꾼', 'agents.holding': '잡고 있는 단계', 'agents.waiting': '일꾼을 기다리는 단계', 'agents.none': '지금 일하는 일꾼이 없습니다', 'agents.noneSub': '에이전트 단계가 시작되면 여기에 나타납니다',
    'agents.open': '처리 과정 보기', 'agents.rowsFail': '단계 목록을 읽지 못했습니다', 'agents.id': '일꾼 ID', 'agents.installed': '설치됨', 'agents.missing': '없음', 'agents.default': '기본',
  });
  const instName = pid => { const I = window.hydInstances && window.hydInstances.I; const inst = I && I.instances.find(x => x.proc_inst_id === pid); return (inst && inst.proc_inst_name) || UI.defName(pid); };

  async function load() {
    if (typeof state === 'undefined' || state.tab !== 'instances') return;
    try { A.status = await getJ(API.process + '/api/agents/status'); A.err = null; } catch (e) { A.status = null; A.err = e.message; }
    try { A.rows = await getJ(API.process + '/api/todolist?status=IN_PROGRESS&agent_orch=cliagents'); A.rowsErr = null; } catch (e) { A.rows = []; A.rowsErr = e.message; }
    const sig = JSON.stringify([A.status, A.err, A.rowsErr, A.rows.map(r => [r.id, r.consumer, r.draft_status, r.start_date]), UI.namesVersion]);
    if (sig === A.sig) return;
    A.sig = sig; render();
  }

  function taskItem(r) {
    return `<div class="item agent-task"><div class="row"><strong>${esc(UI.flowName(r.activity_name))}</strong>${UI.chip(r.draft_status || r.status)}</div>
      <span class="sub">${esc(instName(r.proc_inst_id))} · ${esc(UI.dateTime(r.start_date))}</span>
      <div class="row-wrap"><button type="button" class="btn small" data-agent-task="${esc(r.id)}" data-agent-inst="${esc(r.proc_inst_id)}">${esc(UI.t('agents.open'))}</button></div></div>`;
  }
  function render() {
    const box = document.getElementById('agentsPanel'); if (!box) return;
    const s = A.status, h = (s && s.health) || {};
    const held = A.rows.filter(r => r.consumer), waiting = A.rows.filter(r => !r.consumer);
    const count = document.getElementById('agentsFoldCount'); if (count) count.textContent = held.length ? String(held.length) : '';
    const dot = document.getElementById('agentsFoldDot'); if (dot) dot.className = 'live-dot ' + (s && s.reachable ? (held.length ? 'on' : 'off') : 'error');
    const service = s ? UI.card({ title: esc(UI.t('agents.service')), chips: s.reachable ? UI.chipText(UI.t('agents.up'), 'success') : UI.chipText(UI.t('agents.down'), 'danger'),
      value: s.reachable ? `<span class="kv">${esc(h.runs_in_flight ?? 0)}</span> <span class="muted">${esc(UI.t('agents.inFlight'))}</span>` : '',
      sub: s.reachable ? `${esc(UI.t('agents.handled'))} ${esc(h.handled ?? 0)}건 · ${esc(UI.t('agents.polls'))} ${esc(h.polls ?? 0)}회 · ${esc(UI.t('agents.lastPoll'))} ${h.last_poll ? esc(UI.dateTime(h.last_poll)) : esc(UI.t('agents.never'))}` : esc(s.error || ''),
      body: UI.metaFold([[UI.t('agents.url'), `<span class="mono">${esc(s.url || '')}</span>`], [UI.t('agents.clis'), (s.agents || []).map(a => `${esc(a.agent_id)} ${a.installed ? UI.chipText(UI.t('agents.installed'), 'success') : UI.chipText(UI.t('agents.missing'))}${a.default ? ' ' + UI.chipText(UI.t('agents.default'), 'accent') : ''}`).join(' ')], [UI.t('error.load'), s.reachable && s.error ? esc(s.error) : '']]), cls: 'soft' })
      : `<p class="neg">${esc(UI.t('inst.noConn'))}${A.err ? ': ' + esc(A.err) : ''}</p>`;
    const byWorker = new Map(); held.forEach(r => { if (!byWorker.has(r.consumer)) byWorker.set(r.consumer, []); byWorker.get(r.consumer).push(r); });
    const workers = [...byWorker.entries()].map(([id, rows], i) => UI.card({ title: `${esc(UI.t('agents.worker'))} ${i + 1}`, chips: UI.chipText(`${rows.length}`, 'accent'),
      body: `<div class="list agent-tasks">${rows.map(taskItem).join('')}</div>` + UI.metaFold([[UI.t('agents.id'), `<span class="mono">${esc(id)}</span>`]]) })).join('');
    const wait = waiting.length ? UI.fold(`${esc(UI.t('agents.waiting'))} <span class="chip tone-neutral sm">${waiting.length}</span>`, `<div class="list agent-tasks">${waiting.map(taskItem).join('')}</div>`, { cls: 'plain' }) : '';
    box.innerHTML = `<div class="agents-grid">${service}${workers || (A.rowsErr ? `<p class="neg">${esc(UI.t('agents.rowsFail'))}: ${esc(A.rowsErr)}</p>` : UI.empty(UI.t('agents.none'), UI.t('agents.noneSub'), 'compact'))}</div>${wait}`;
    box.querySelectorAll('[data-agent-task]').forEach(b => b.addEventListener('click', async () => {
      const I = window.hydInstances && window.hydInstances.I; if (!I) return;
      I.sel = b.dataset.agentInst; I.taskSel = null; I.tab = 'flow';
      await window.hydInstances.load(true);
      if (window.hydTaskDetail) window.hydTaskDetail.open(b.dataset.agentTask);
    }));
  }

  setInterval(load, 5000);
  const _sel = selectTab;
  selectTab = function (name) { _sel(name); if (name === 'instances') load(); };
  window.hydApp.selectTab = selectTab;
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', load); else load();
  window.hydAgents = { A, load, render };
})();
