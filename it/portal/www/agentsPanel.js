/* U1 — 지금 일하는 AI 에이전트 (처리 건 화면의 「자세한 기록 › 실행 중인 AI 에이전트」). GET /api/agents/status (AI 에이전트 실행 서비스의 /health · 설치된 코딩 에이전트) 와
   GET /api/todolist?status=IN_PROGRESS&agent_orch=cliagents (실행 서비스가 잡고 있는 단계: consumer 가 임대한 행) 를 5초마다 읽는다.
   vue3 에는 전역 일꾼 현황 화면이 없다(단계별 agent-monitor 탭뿐) — 회의 L434 "어떤 에이전트들이 지금 동작하고 있다" 를 위해 둔다.
   누르면 그 처리 건의 흐름 탭을 열고 task 상세 패널(taskDetail.js)로 이어진다. 폴백 없음: 일꾼이 안 닿으면 그 사유를 그대로 보인다. */
(function () {
  const A = { status: null, rows: [], err: null, sig: null };
  Object.assign(UI.terms, {
    'agents.title': '실행 중인 AI 에이전트', 'agents.service': 'AI 에이전트 실행 서비스', 'agents.up': '연결됨', 'agents.down': '연결 안 됨', 'agents.inFlight': '실행 중',
    'agents.handled': '처리', 'agents.lastLook': '마지막으로 일을 찾은 시각', 'agents.never': '아직 없음', 'agents.clis': '설치된 코딩 에이전트',
    'agents.worker': '실행 서비스', 'agents.holding': '수행 중인 단계', 'agents.waiting': 'AI 에이전트 차례를 기다리는 단계', 'agents.none': '실행 중인 AI 에이전트가 없습니다', 'agents.noneSub': 'AI 에이전트 단계가 시작되면 여기에 나타납니다',
    'agents.open': '처리 과정 보기', 'agents.rowsFail': '단계 목록을 읽지 못했습니다', 'agents.installed': '설치됨', 'agents.missing': '없음',
    'agents.downWhy': 'AI 에이전트 실행 서비스가 꺼져 있거나 켜지는 중입니다. 1분 뒤에도 같으면 시작.bat을 다시 실행하세요.', 'agents.raw': '연결 오류 원문',
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
    // 줄을 누르면 그 처리 건의 단계 상세가 열린다(줄 자체가 단추)
    return `<button type="button" class="row" data-agent-task="${esc(r.id)}" data-agent-inst="${esc(r.proc_inst_id)}" data-tooltip="${esc(UI.t('agents.open'))}"><span class="row-ic">${UI.icon('bot')}</span><span class="row-title">${esc(UI.flowName(r.activity_name))}</span>${UI.chip(r.draft_status || r.status)}
      <span class="row-meta">${esc(instName(r.proc_inst_id))} · ${esc(UI.dateTime(r.start_date))}</span></button>`;
  }
  function render() {
    const box = document.getElementById('agentsPanel'); if (!box) return;
    const s = A.status, h = (s && s.health) || {};
    const held = A.rows.filter(r => r.consumer), waiting = A.rows.filter(r => !r.consumer);
    // 5초마다 다시 그려도 사람이 펼친 「상세 정보」는 펼친 채로 둔다(다시 그릴 때마다 닫혀서 눌러도 변화가 없는 것처럼 보였다)
    const fold = box.querySelector('.agents-service details'); if (fold) A.metaOpen = fold.open;
    // 실행 서비스의 지금 상태 한 문장(점 색 = 연결됨 · 안 됨) → 처리 수 · 마지막으로 일을 찾은 시각. 설치된 코딩 에이전트 · 오류 원문은 「상세 정보」 접기 안에
    const meta = s ? [[UI.t('agents.clis'), (s.agents || []).map(a => `${esc(a.agent_id)} (${esc(UI.t(a.installed ? 'agents.installed' : 'agents.missing'))})`).join(', ')],
      [UI.t('agents.raw'), s.error ? `<span class="mono">${esc(s.error)}</span>` : '']].filter(([, v]) => v) : [];
    const service = s ? `<div class="agents-service"><p class="agents-state"><i class="dot" data-tone="${s.reachable ? 'ok' : 'danger'}"></i><span><b>${esc(UI.t('agents.service'))}</b> — ${s.reachable
        ? `${esc(UI.t('agents.up'))} · ${esc(UI.t('agents.inFlight'))} ${esc(h.runs_in_flight ?? 0)}건 · ${esc(UI.t('agents.handled'))} ${esc(h.handled ?? 0)}건 · ${esc(UI.t('agents.lastLook'))} ${h.last_poll ? esc(UI.dateTime(h.last_poll)) : esc(UI.t('agents.never'))}`
        : `${esc(UI.t('agents.down'))} · ${esc(UI.t('agents.downWhy'))}`}</span></p>` +
      (meta.length ? UI.fold(esc(UI.t('fold.meta')), `<dl class="kv">${meta.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${v}</dd>`).join('')}</dl>`, { open: !!A.metaOpen }) : '') + `</div>`
      : UI.errorBlock(UI.t('inst.noConn'), A.err || '');
    const byWorker = new Map(); held.forEach(r => { if (!byWorker.has(r.consumer)) byWorker.set(r.consumer, []); byWorker.get(r.consumer).push(r); });
    const section = (label, rows) => `<section class="agents-group"><h3>${esc(label)}</h3><div class="rows">${rows.map(taskItem).join('')}</div></section>`;
    const workers = [...byWorker.values()].map((rows, i) => section(`${UI.t('agents.worker')} ${i + 1} · ${UI.t('agents.holding')} ${rows.length}건`, rows)).join('');
    const wait = waiting.length ? section(`${UI.t('agents.waiting')} ${waiting.length}건`, waiting) : '';
    box.innerHTML = service + (workers || (A.rowsErr ? UI.errorBlock(UI.t('agents.rowsFail'), A.rowsErr) : UI.empty(UI.t('agents.none'), UI.t('agents.noneSub')))) + wait;
    box.querySelectorAll('[data-agent-task]').forEach(b => b.addEventListener('click', async () => {
      const I = window.hydInstances && window.hydInstances.I; if (!I) return;
      I.sel = b.dataset.agentInst; I.taskSel = null; I.tab = 'flow';
      await window.hydInstances.load(true);
      if (window.hydTaskDetail) window.hydTaskDetail.open(b.dataset.agentTask);
    }));
  }

  setInterval(load, 5000);
  window.hydTabs.onShow(name => { if (name === 'instances') load(); });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', load); else load();
})();
