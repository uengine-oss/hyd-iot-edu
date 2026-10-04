/* HITL · BPMN · skill catalog · manual upload (loaded after app.js / enterprise.js / main.js).
   - BPMN-style flow of the anomaly → action process, highlighted with the live state of one incident + its decision
   - HITL panel: the agent's ranked action cards (스킬 = SOP; DMN rules · forecasts · BSC trade-offs · precedents) → one human decision
   - skill catalog: list / edit SOP skills, add a new SOP skill matched to a failure mode (written by the process service)
   - manual upload: manual → ManualSection nodes + one SOP skill per procedure, matched to a failure mode */
(function () {
  const H = { inc: null, decs: [], dec: null, sig: null, form: { option: null, reason: '', role: null, by: 'OP-17', fan: null, load: null }, msg: '', busy: false,
    skills: [], catalog: null, skillSel: null, skillNew: false, skillDrafts: new Map(), preview: null };

  /* ================================================= BPMN renderer */
  const LANES = ['설비 · 탐지 (L1~L4)', '에이전트 (L8)', '사람 · HITL', '프로세스 (L9)', '기업 시스템', '온톨로지 (L7)'];
  const NODES = {
    start: { lane: 0, x: 186, kind: 'start', label: '이상 발생' },
    alert: { lane: 0, x: 300, kind: 'task', label: '경보 RAISE · CEP' },
    diag: { lane: 1, x: 390, kind: 'task', label: '고장 원인 분석' },
    lookup: { lane: 1, x: 555, kind: 'task', label: '조치 방법(SOP) 조회', sub: 'DMN 후보 · 규정 규칙' },
    rank: { lane: 1, x: 715, kind: 'task', label: '카드 순위 · 가드레일', sub: '예측 · BSC 득실 · 선례' },
    decide: { lane: 2, x: 840, kind: 'task', label: '조치 의사결정', sub: '역할 권한 · 사유' },
    gw: { lane: 2, x: 975, kind: 'gateway', label: '즉시 제어?' },
    cmd: { lane: 3, x: 1100, kind: 'task', label: 'action.cmd → PLC', sub: '게이트웨이 5종 검증' },
    reobs: { lane: 3, x: 1262, kind: 'task', label: 'ACK · 15분 재관측' },
    close: { lane: 3, x: 1380, kind: 'end', label: '종결' },
    exec: { lane: 4, x: 1100, kind: 'task', label: '작업지시 · 구매 실행', sub: 'CMMS · ERP' },
    learn: { lane: 5, x: 1100, kind: 'task', label: '판단 사례 기록', sub: 'DecisionCase → 다음 선례' },
  };
  const FLOWS = [['start', 'alert'], ['alert', 'diag'], ['diag', 'lookup'], ['lookup', 'rank'], ['rank', 'decide'], ['decide', 'gw'],
    ['gw', 'cmd', '예'], ['gw', 'exec', '작업지시'], ['cmd', 'reobs'], ['reobs', 'close'], ['decide', 'learn', '', 'msg'], ['learn', 'lookup', '환류', 'loop']];
  const LANE_H = 74, TOP = 8, LEFT = 150, TW = 146, TH = 46;

  function nodeState(ctx) {
    const st = {}; Object.keys(NODES).forEach(k => st[k] = 'todo');
    if (!ctx || !ctx.inc) return st;
    const inc = ctx.inc, dec = ctx.dec, hist = new Set((inc.history || []).map(h => h.state));
    ['start', 'alert', 'diag', 'lookup', 'rank'].forEach(k => st[k] = 'done');
    const decided = dec && ['APPROVED', 'EXECUTED', 'PARTIAL'].includes(dec.state);
    st.decide = inc.state === 'AWAITING_APPROVAL' && !decided ? 'now' : (decided || hist.has('CMD_ISSUED') || inc.state === 'REJECTED_BY_OPERATOR') ? 'done' : st.decide;
    if (decided || hist.has('CMD_ISSUED') || inc.state === 'REJECTED_BY_OPERATOR') st.gw = 'done';
    if (hist.has('CMD_ISSUED')) st.cmd = hist.has('ACKED') ? 'done' : 'now';
    if (hist.has('RE_OBSERVING')) st.reobs = inc.state === 'RE_OBSERVING' ? 'now' : 'done';
    if (inc.state === 'CLOSED' || inc.state === 'REJECTED_BY_OPERATOR') st.close = 'done';
    if (inc.state === 'ESCALATED') { st.reobs = 'fail'; st.close = 'fail'; }
    if (dec) { st.exec = dec.state === 'EXECUTED' ? 'done' : dec.state === 'PARTIAL' ? 'fail' : st.exec; }
    if (decided) st.learn = 'done';
    return st;
  }
  function bpmnSvg(ctx, caption) {
    const W = 1460, Hh = TOP + LANES.length * LANE_H + 8;
    const st = nodeState(ctx);
    const cy = n => TOP + NODES[n].lane * LANE_H + LANE_H / 2;
    let s = `<svg viewBox="0 0 ${W} ${Hh}" class="bpmn" role="img" aria-label="조치 프로세스 BPMN 흐름도"><defs>` +
      '<marker id="bArr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="#4a5566"/></marker>' +
      '<marker id="bArrP" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="#6d28d9"/></marker></defs>';
    LANES.forEach((l, i) => {
      const y = TOP + i * LANE_H;
      s += `<rect x="4" y="${y}" width="${W - 8}" height="${LANE_H}" class="b-lane ${i % 2 ? 'alt' : ''}"/><rect x="4" y="${y}" width="${LEFT - 14}" height="${LANE_H}" class="b-lanehead"/>` +
        `<text x="16" y="${y + LANE_H / 2 + 4}" class="b-lanet">${esc(l)}</text>`;
    });
    const edge = (a, b, label, kind) => {
      const A = NODES[a], B = NODES[b];
      const ax = A.x + (A.kind === 'task' ? TW / 2 : 18), bx = B.x - (B.kind === 'task' ? TW / 2 : 18);
      const ay = cy(a), by = cy(b);
      let d;
      if (kind === 'loop') d = `M${A.x - TW / 2} ${ay} C ${A.x - 260} ${ay}, ${B.x + 40} ${by + 70}, ${B.x} ${by + TH / 2 + 2}`;
      else if (kind === 'msg') d = `M${A.x} ${ay + TH / 2} C ${A.x} ${ay + 150}, ${B.x - 180} ${by}, ${B.x - TW / 2} ${by}`;
      else if (ay === by) d = `M${ax} ${ay} H${bx}`;
      else d = `M${ax} ${ay} H${(ax + bx) / 2} V${by} H${bx}`;
      const done = st[a] === 'done' && st[b] !== 'todo';
      const cls = kind === 'loop' ? 'b-flow loop' : kind === 'msg' ? 'b-flow msg' : 'b-flow' + (done ? ' done' : '');
      let out = `<path d="${d}" class="${cls}" marker-end="url(#${kind === 'loop' ? 'bArrP' : 'bArr'})"/>`;
      if (label) {
        const lx = kind === 'loop' ? B.x + 150 : (ax + bx) / 2 - 12, ly = kind === 'loop' ? by + 96 : by - 12;
        out += `<text x="${lx}" y="${ly}" text-anchor="${kind === 'loop' ? 'start' : 'end'}" class="b-flowt ${kind || ''}">${esc(label)}</text>`;
      }
      return out;
    };
    FLOWS.forEach(f => s += edge(...f));
    for (const [id, n] of Object.entries(NODES)) {
      const y = cy(id), cls = 'b-node ' + st[id];
      if (n.kind === 'task') {
        s += `<g class="${cls}"><rect x="${n.x - TW / 2}" y="${y - TH / 2}" width="${TW}" height="${TH}" rx="9"/>` +
          `<text x="${n.x}" y="${y + (n.sub ? -3 : 4)}" text-anchor="middle" class="b-t">${esc(n.label)}</text>` +
          (n.sub ? `<text x="${n.x}" y="${y + 13}" text-anchor="middle" class="b-s">${esc(n.sub)}</text>` : '') + '</g>';
      } else if (n.kind === 'gateway') {
        s += `<g class="${cls}"><path d="M${n.x} ${y - 22} L${n.x + 22} ${y} L${n.x} ${y + 22} L${n.x - 22} ${y} Z"/><text x="${n.x}" y="${y + 5}" text-anchor="middle" class="b-g">×</text>` +
          `<text x="${n.x}" y="${y - 28}" text-anchor="middle" class="b-s">${esc(n.label)}</text></g>`;
      } else {
        s += `<g class="${cls} ${n.kind}"><circle cx="${n.x}" cy="${y}" r="17"/><text x="${n.x}" y="${y + 34}" text-anchor="middle" class="b-s">${esc(n.label)}</text></g>`;
      }
    }
    s += '</svg>';
    return `<div class="bpmn-cap"><span>${caption || ''}</span><span class="b-legend"><span><i class="done"></i>완료</span><span><i class="now"></i>진행 중</span><span><i class="fail"></i>실패 · 에스컬레이션</span><span><i class="loop"></i>지식 환류</span></span></div><div class="bpmn-tools"><span>흐름도를 좌우로 이동해 다음 단계를 확인할 수 있습니다.</span><button type="button" class="btn small" data-bpmn-fit aria-pressed="false">전체 흐름 보기</button></div><div class="bpmn-scroll" tabindex="0" role="region" aria-label="업무 흐름도, 좌우 방향키로 이동">${s}</div>`;
  }
  window.hydBpmn = bpmnSvg;
  function setDiagramContent(box, html, key) {
    const old = box.querySelector('.bpmn-scroll');
    const same = box.dataset.diagramKey === key;
    const left = same && old ? old.scrollLeft : 0;
    const fit = same && old?.classList.contains('fit');
    const focus = same && document.activeElement === old ? 'region' :
      same && document.activeElement?.matches('[data-bpmn-fit]') && box.contains(document.activeElement) ? 'button' : null;
    box.innerHTML = html; box.dataset.diagramKey = key;
    const region = box.querySelector('.bpmn-scroll'), button = box.querySelector('[data-bpmn-fit]');
    if (!region) return;
    region.classList.toggle('fit', !!fit); region.scrollLeft = left;
    button.setAttribute('aria-pressed', String(!!fit));
    button.textContent = fit ? '읽기 편한 크기로 보기' : '전체 흐름 보기';
    if (focus) (focus === 'region' ? region : button).focus({preventScroll:true});
  }
  document.addEventListener('click', e => {
    const b = e.target.closest('[data-bpmn-fit]'); if (!b) return;
    const region = b.parentElement.nextElementSibling;
    const fit = region.classList.toggle('fit');
    b.setAttribute('aria-pressed', String(fit));
    b.textContent = fit ? '읽기 편한 크기로 보기' : '전체 흐름 보기';
  });

  /* ================================================= HITL decision panel (이상 확인 & 조치) — ontology v2 action cards */
  async function refreshHitl(force) {
    const box = document.getElementById('hitlPanel'); if (!box) return;
    const inc = state.tab === 'incidents' ? state.detail : null;
    if (!inc) { if (box.innerHTML) box.innerHTML = ''; H.sig = null; return; }
    let decs = [];
    try { decs = (await getJ(API.process + '/api/decisions')).filter(d => (d.origin || {}).incident === inc.id); } catch (e) { }
    const prim = decs[0] || null;
    let dec = null;
    if (prim) { try { dec = await getJ(API.process + '/api/decisions/' + prim.id); } catch (e) { } }
    if (state.tab !== 'incidents' || state.detail?.id !== inc.id) return;
    const sig = [inc.id, inc.state, decs.length, dec && dec.id, dec && dec.state, H.msg].join('|');
    if (!force && sig === H.sig) return;
    if (H.inc && (H.inc.id !== inc.id || H.dec?.id !== dec?.id)) H.form = { option: null, reason: '', role: null, by: 'OP-17', fan: null, load: null };
    H.sig = sig; H.inc = inc; H.decs = decs; H.dec = dec;
    renderHitl();
  }
  const cmdOf = (o, param) => ((o && o.actions) || []).find(a => a.kind === 'command' && a.param === param);
  function renderHitl() {
    const box = document.getElementById('hitlPanel'); const inc = H.inc, d = H.dec;
    let html = '<section class="hitl">' + bpmnSvg({ inc, dec: d }, `<b>${esc(inc.id)}</b> 조치 프로세스 — ${esc(inc.asset)} · 경보 ${esc(inc.alertId)}`);
    if (!d) {
      html += `<div class="hitl-wait">${inc.state === 'AWAITING_APPROVAL' ? '에이전트가 고장 유형에 매칭된 조치 방법(SOP)을 규칙 · 예측 · 성과 지표로 비교하고 있습니다…' : `이 사건에는 승인할 조치 카드가 없습니다. 현재 상태: ${esc(inc.state)}${inc.reason ? ' · '+esc(inc.reason) : ''}. 사람 검토 작업과 사건 기록을 확인하세요.`}</div></section>`;
      setDiagramContent(box, html, inc.id); return;
    }
    const opts = d.options || [];
    const maxAbs = Math.max(1, ...opts.map(o => Math.abs(o.score || 0)));
    const pending = d.state === 'PENDING_APPROVAL';
    if (!H.form.option) H.form.option = d.recommended || (opts.find(o => o.feasible) || opts[0] || {}).id;
    const chosenOpt = opts.find(o => o.id === H.form.option);
    const fanA = cmdOf(chosenOpt, 'fan_pct'), loadA = cmdOf(chosenOpt, 'load_pct'), pumpA = cmdOf(chosenOpt, 'pump');
    if (H.form.cardFor !== H.form.option) { H.form.fan = fanA ? fanA.value : null; H.form.load = loadA ? loadA.value : null; H.form.cardFor = H.form.option; }
    const parameters = {...(fanA ? {fan_pct:H.form.fan} : {}),...(loadA ? {load_pct:H.form.load} : {})};
    const review = window.hydCards?.reviewMatches(H.form.review,d.id,H.form.option,parameters,{kind:"legacy",incident:inc.id}) ? H.form.review : null;
    const reviewed = review?.snapshot?.options?.[0];
    const changed=(fanA && H.form.fan!==fanA.value)||(loadA && H.form.load!==loadA.value);
    const canApprove=reviewed ? reviewed.feasible : chosenOpt?.feasible && !changed;
    const roles = Object.entries(review?.snapshot?.roles || d.roles || {}).sort((a, b) => a[1].level - b[1].level);
    if (!H.form.role) H.form.role = ((chosenOpt && chosenOpt.approver) || {}).id || (roles[0] || [''])[0];
    const sc = d.scenario || {};
    html += `<div class="hitl-head"><h2>조치 카드 선택 (HITL) <span class="pill ${esc(d.state)}">${esc(UI.status(d.state))}</span></h2>
      <p>${esc(sc.failureMode || '')} — 원인 '${esc(sc.cause || '')}'. 에이전트가 이 고장 유형에 매칭된 조치 방법(스킬 = SOP)을 온톨로지의 DMN 규칙으로 고르고 거른 뒤, 예측 · BSC 득실 · 선례로 순위를 매겼다. 카드마다 "출처 보기"로 규칙 · SOP 단계 · 매뉴얼 근거를 확인하고 하나를 고르면, PLC 명령은 게이트웨이를 거쳐 설비로, 작업지시 · 구매는 기업 시스템으로 가고, 이 선택은 판단 사례로 기록되어 다음 판단의 선례가 된다.</p>
      <div class="summary">${esc(d.explanation || '')}</div></div>`;
    html += '<div class="hitl-opts">' + opts.map(o => hydCards.cardHtml(o, { rec: d.recommended, chosen: d.chosen, selectable: true, reviewable: true, selected: H.form.option === o.id, pending, maxAbs })).join('') + '</div>';
    if (d.rankRule) html += `<p class="muted">순위 규칙 ${esc(d.rankRule.rule)}: ${esc(d.rankRule.annotation || '')}</p>`;
    if (pending) {
      const live = inc.state === 'AWAITING_APPROVAL';
      html += `<div id="hReviewed">${reviewed ? `<h3>현재 입력으로 검토한 조치</h3><p>${esc(UI.time(review.created))} · ${esc(review.snapshot.explanation || '')}</p>${hydCards.cardHtml(reviewed, {maxAbs})}` : '<p class="muted">조치값을 바꾸면 새 예측을 검토한 뒤 승인하세요. 검토만으로 설비 명령은 나가지 않습니다.</p>'}</div><div class="hitl-form">
        ${live && pumpA ? `<div class="hparam"><span>운전 펌프 → <b>${esc(pumpA.value)}</b> (PLC PumpSelect, 범위 조정 없음)</span></div>` : ''}
        ${live && (fanA || loadA) ? `<div class="hparam">${fanA ? `<label>팬 속도 <input type="range" id="hFan" min="${fanA.min ?? 0}" max="${fanA.max ?? 100}" value="${H.form.fan}"><output>${H.form.fan}</output> %</label>` : ''}
          ${loadA ? `<label>펌프 부하 <input type="range" id="hLoad" min="${loadA.min ?? 60}" max="${loadA.max ?? 100}" value="${H.form.load}"><output>${H.form.load}</output> %</label>` : ''}<span class="muted">기본값은 SOP의 값, 범위는 온톨로지 원자 조치(Action)의 min · max</span></div>` : ''}
        <div class="hwho"><label>결정자 <input id="hBy" value="${esc(H.form.by)}"></label>
          <label>역할 <select id="hRole">${roles.map(([id, r]) => `<option value="${esc(id)}" ${id === H.form.role ? 'selected' : ''}>${esc(r.name)} (직급 ${r.level})</option>`).join('')}</select></label></div>
        <label class="hreason">판단 사유 <textarea id="hReason" rows="2" placeholder="예: 납기 오더가 남아 있어 부하를 크게 줄일 수 없음, 야간 세척 인력 확보됨">${esc(H.form.reason)}</textarea></label>
        <div class="hact"><button class="btn" id="hPreview" ${live && !H.busy && H.form.option ? '' : 'disabled'}>새 예측 검토</button><button class="btn primary" id="hGo" ${live && canApprove && !H.busy ? '' : 'disabled'}>${reviewed ? '검토한 조치로 결정' : '이 카드로 결정'}</button><span class="neg" id="hMsg">${esc(H.msg)}</span><span class="muted">고른 카드의 승인 역할이 기본값이다. 다른 역할로 바꿔 권한 검사를 확인해 볼 수 있다.</span></div></div>`;
    } else {
      const ch = opts.find(o => o.id === d.chosen) || {};
      html += `<div class="hitl-done">결정: <b>${esc(ch.sopId || '')} ${esc(ch.name || d.chosen || '')}</b> · ${esc(d.approvedBy || '')} (${esc(((d.roles || {})[d.approvedRole] || {}).name || d.approvedRole || '')})${d.override ? ' · 권고와 다른 선택' : ''}${d.reason ? ' · 사유: ' + esc(d.reason) : ''}
        <div class="muted">이 선택은 온톨로지에 판단 사례(DecisionCase -CHOSE-> Skill)로 기록됐고, 같은 고장 유형의 다음 판단에서 선례 점수로 반영된다.</div>
        ${(d.executions || []).map(x => `<div class="hx"><span class="pill ${x.status === 'DONE' ? 'CLOSED' : x.status === 'VIA_HITL' ? 'AWAITING_APPROVAL' : 'ESCALATED'}">${esc(UI.status(x.status))}</span> ${esc(x.code || x.skill)} — ${esc(x.detail || '')}</div>`).join('')}</div>`;
    }
    html += '</section>';
    setDiagramContent(box, html, inc.id);
    box.querySelectorAll('input[name=hopt]').forEach(r => r.addEventListener('change', () => { H.form.option = r.value; H.form.review=null; H.msg = ''; const o = (H.dec.options || []).find(x => x.id === r.value); if (o && o.approver) H.form.role = o.approver.id; renderHitl(); }));
    const on = (id, ev, fn) => { const e = document.getElementById(id); if (e) e.addEventListener(ev, fn); };
    const invalidate = () => { H.form.review=null; $('#hGo').disabled=true; $('#hReviewed').textContent='조치값이 바뀌었습니다. 새 예측을 검토하세요.'; };
    on('hFan', 'input', e => { H.form.fan = +e.target.value; e.target.nextElementSibling.textContent = e.target.value; invalidate(); });
    on('hLoad', 'input', e => { H.form.load = +e.target.value; e.target.nextElementSibling.textContent = e.target.value; invalidate(); });
    on('hFan','change',renderHitl); on('hLoad','change',renderHitl);
    on('hBy', 'input', e => H.form.by = e.target.value);
    on('hRole', 'change', e => { H.form.role = e.target.value; H.msg = ''; });
    on('hReason', 'input', e => H.form.reason = e.target.value);
    on('hGo', 'click', decideNow);
    on('hPreview','click',() => previewChoice(parameters));
  }
  async function previewChoice(parameters) {
    if (H.busy) return; H.busy=true; H.msg=''; renderHitl();
    const form=H.form, decision=H.dec.id, option=form.option;
    try { const review=await postJ(API.process+`/api/incidents/${encodeURIComponent(H.inc.id)}/decision-preview`,
      {decision,option,parameters});
      if (H.form===form && H.dec?.id===decision && H.form.option===option) H.form.review=review;
    } catch(e) { if(H.form===form) { H.form.review=null; H.msg=e.message; } }
    finally { H.busy=false; if(H.inc) renderHitl(); }
  }
  async function decideNow() {
    if (H.busy) return; H.busy = true;
    const go = $('#hGo'); if (go) { go.disabled = true; go.textContent = '처리 중…'; }
    try {
      await postJ(API.process + `/api/incidents/${H.inc.id}/decide`, { decision: H.dec.id, option: H.form.option, by: H.form.by || '승인자', role: H.form.role,
        reason: H.form.reason, fan_pct: H.form.fan, load_pct: H.form.load, review_id: matchingReviewId(H.form,H.dec) });
      H.msg = '';
      await refreshSlow();
    } catch (e) { H.msg = e.message; }
    finally { H.busy = false; await refreshHitl(true); }
  }
  function matchingReviewId(form,decision) {
    const option=decision?.options?.find(o=>o.id===form.option);
    const parameters={...(cmdOf(option,'fan_pct') ? {fan_pct:form.fan} : {}),...(cmdOf(option,'load_pct') ? {load_pct:form.load} : {})};
    return window.hydCards?.reviewMatches(form.review,decision?.id,form.option,parameters,{kind:"legacy",incident:H.inc.id}) ? form.review.id : null;
  }
  window.hydHitl = { H, refreshHitl, decideNow };
  setInterval(() => refreshHitl(false), 1500);

  /* L9 view: BPMN for the selected decision's incident */
  async function refreshProcBpmn() {
    if (state.tab !== 'process') return;
    const box = document.getElementById('procBpmn'); if (!box) return;
    const d = hydEnt.ent.decDetail; let inc = null;
    const incId = d && (d.origin || {}).incident;
    if (incId) { try { inc = await getJ(API.process + '/api/incidents/' + incId); } catch (e) { } }
    if (state.tab !== 'process' || hydEnt.ent.decDetail?.id !== d?.id) return;
    const sig = [d && d.id, d && d.state, inc && inc.state].join('|');
    if (box.dataset.sig === sig) return; box.dataset.sig = sig;
    setDiagramContent(box, bpmnSvg(inc ? { inc, dec: d } : null, inc ? `판단 <b>${esc(d.id)}</b> · 인시던트 ${esc(inc.id)}의 진행` : (d ? '수동으로 실행한 판단입니다. 설비 인시던트와 연결된 판단을 선택하면 진행 상태를 확인할 수 있습니다.' : '판단을 선택하면 진행 상태를 확인할 수 있습니다.')), d?.id || 'overview');
  }
  setInterval(refreshProcBpmn, 2000);

  /* ================================================= skill catalog — 조치 방법 = Skill = SOP, 고장 유형에 매칭 */
  const REL_KO = { MITIGATED_BY: '즉시 완화', REMEDIED_BY: '근본 조치' };
  const draftKey = key => 'hyd:skill-edit:' + key;
  function saveSkillDraft(key, draft) {
    H.skillDrafts.set(key, draft);
    try { sessionStorage.setItem(draftKey(key), JSON.stringify(draft)); } catch (_) { /* Same-page retry remains available. */ }
  }
  function clearSkillDraft(key) {
    H.skillDrafts.delete(key);
    try { sessionStorage.removeItem(draftKey(key)); } catch (_) { /* In-memory copy has been cleared. */ }
  }
  async function loadSkills() {
    if (!H.skills.length) $('#skillList').innerHTML = '<div class="muted" role="status">스킬을 불러오는 중…</div>';
    try { H.skills = await getJ(API.process + '/api/kg/skills'); } catch (e) { $('#skillList').innerHTML = `<div class="muted">스킬 목록을 불러오지 못했습니다. 업무 서비스와 지식 저장소 연결을 확인해 주세요. ${esc(e.message)}</div>`; return; }
    if (!H.catalog) { try { H.catalog = await getJ(API.process + '/api/kg/catalog'); } catch (e) { H.catalog = { roles: [], failureModes: [], manualSections: [] }; } }
    if (!H.skillSel && H.skills.length && !H.skillNew) H.skillSel = H.skills[0].id;
    renderSkillList(); renderSkillDetail();
  }
  function renderSkillList() {
    const list = $('#skillList'); list.innerHTML = '';
    for (const k of H.skills) {
      const it = el('div', 'item' + (k.id === H.skillSel && !H.skillNew ? ' sel' : ''));
      keyboardItem(it);
      const fm = (k.failureModes || []).map(f => `${f.name} (${REL_KO[f.relation] || f.relation})`).join(', ');
      it.innerHTML = `<strong><span class="mono">${esc(k.sopId || '')}</span> ${esc(k.name)}</strong><span>${esc(fm || '고장 유형 매칭 없음')} · 승인 ${esc((k.approver || {}).name || '–')}</span><span class="d">${esc(k.description || '')}</span>`;
      it.addEventListener('click', () => { H.skillSel = k.id; H.skillNew = false; renderSkillList(); renderSkillDetail(); UI.revealDetail($('#skillDetail')); });
      list.append(it);
    }
  }
  function renderSkillDetail() {
    const box = $('#skillDetail'); const c = H.catalog || { roles: [], failureModes: [] };
    const key = H.skillNew ? '__new__' : H.skillSel;
    if (box.dataset.key === key && box.querySelector('#skName')) return;
    box.dataset.key = key || '';
    const k = H.skillNew ? { id: '(새 SOP 스킬)', name: '', description: '', sopId: '', steps: [], failureModes: [], actions: [], rules: [], affects: [], causes: [], performers: [] }
      : H.skills.find(x => x.id === H.skillSel);
    if (!k) { box.innerHTML = '<div class="empty">목록에서 스킬을 선택해 주세요.</div>'; return; }
    const sel = (id, items, cur) => `<select id="${id}">${items.map(x => `<option value="${esc(x.id)}" ${cur === x.id ? 'selected' : ''}>${esc(x.name)}</option>`).join('')}</select>`;
    const newForm = H.skillNew ? `
      <div class="skill-rels"><label>SOP 번호 <input id="skSop" placeholder="SOP-FAN-05" maxlength="40"></label>
        <label>매칭할 고장 유형 ${sel('skFm', c.failureModes || [], '')}</label>
        <label>관계 <select id="skRel"><option value="REMEDIED_BY">근본 조치 (REMEDIED_BY)</option><option value="MITIGATED_BY">즉시 완화 (MITIGATED_BY)</option></select></label></div>
      <label>종류 <select id="skKind"><option value="work_order">정비 작업지시 (work_order)</option><option value="control">설비 제어 (control)</option></select></label>
      <label><span id="skStepsLabel">SOP 단계 — 한 줄에 한 단계</span><textarea id="skSteps" rows="5" aria-labelledby="skStepsLabel" placeholder="LOCAL로 전환하고 잠근다.&#10;벨트를 교체한다.&#10;재가동 후 VS1 0.9 mm/s 미만을 확인한다."></textarea></label>` : '';
    box.innerHTML = `<div class="skill-edit"><div class="muted"><span class="mono">${esc(k.id)}</span>${k.kind ? ' · ' + esc(k.kind === 'control' ? '설비 제어' : '정비 작업지시') : ''}${(k.performers || []).length ? ' · 수행: ' + esc(k.performers.join(', ')) : ''}</div>
      <label>스킬(SOP) 이름<input id="skName" value="${esc(k.name)}" maxlength="80"></label>
      <label><span id="skDescLabel">어떤 조치인가요?</span><textarea id="skDesc" rows="2" aria-labelledby="skDescLabel">${esc(k.description || '')}</textarea></label>
      <label>승인 역할 ${sel('skRole', c.roles || [], (k.approver || {}).id || 'role:maint-mgr')}</label>${newForm}
      <div class="approve-row"><input id="skBy" value="지식 관리자" aria-label="편집자"><button class="btn primary" id="skSave">${H.skillNew ? '온톨로지에 추가' : '저장'}</button><button class="btn" id="skReload">변경 취소·현재 내용 다시 확인</button><span id="skMsg" class="muted" role="status"></span></div>
      ${k.source_document ? '<p>보관 원문에서 등록한 스킬입니다. 원문과 검토 이력을 함께 유지하도록 문서 개정 화면에서 수정하세요. <button class="btn" id="skSource">원문·문서 개정 열기</button></p>' : ''}
      ${H.skillNew ? '<p class="muted">새 스킬은 SOP 번호 · 단계 · 고장 유형 매칭이 있어야 온톨로지 스키마를 지킨다 (Skill = SOP, FailureMode → Skill).</p>' : `<h3>SOP 단계</h3><ol class="steps">${(k.steps || []).map(s => `<li>${esc(s.text)} ${s.manual ? `<span class="muted">[${esc(s.manual)}]</span>` : ''}</li>`).join('') || '<li class="muted">단계 없음</li>'}</ol>
      <h3>연결된 지식</h3><table class="kvt">
        <tr><th>매칭된 고장 유형</th><td>${(k.failureModes || []).map(f => `${esc(f.name)} <span class="muted">(${esc(REL_KO[f.relation] || f.relation)})</span>`).join('<br>') || '없음'}</td></tr>
        <tr><th>해당 원인 한정</th><td>${(k.causes || []).map(x => esc(x.name)).join(', ') || '고장 유형의 모든 원인'}</td></tr>
        <tr><th>원자 조치</th><td>${(k.actions || []).map(a => `${esc(a.code)}${a.value != null ? '=' + esc(a.value) : ''} <span class="muted">${esc(a.name)}</span>`).join('<br>') || '없음'}</td></tr>
        <tr><th>규칙 (DMN)</th><td>${(k.rules || []).map(r => `<span class="${r.effect === 'EXCLUDE' ? 'hard' : r.effect === 'SELECT' ? '' : 'soft'}">${esc(r.effect)} · ${esc(r.annotation || r.id)}</span>`).join(' ') || '없음'}</td></tr>
        <tr><th>움직이는 변수 · 성과 지표</th><td>${(k.affects || []).map(a => `${esc(a.name)} ${a.sign > 0 ? '↑' : '↓'}`).join(', ') || '없음'}</td></tr></table>`}</div>`;
    const fields = [...box.querySelectorAll('input, textarea, select')];
    let draft = H.skillDrafts.get(key);
    if (!draft) { try { draft = JSON.parse(sessionStorage.getItem(draftKey(key)) || 'null'); } catch (_) { /* Use the viewed revision. */ } }
    draft = draft || { revision: k.revision, fields: {}, pending: null };
    fields.forEach(e => { if (draft.fields?.[e.id] != null) e.value = draft.fields[e.id]; });
    const remember = () => { draft.fields = Object.fromEntries(fields.map(e => [e.id, e.value])); saveSkillDraft(key, draft); $('#skMsg').textContent = '저장하지 않은 변경 사항'; };
    fields.forEach(e => { e.addEventListener('input', remember); e.addEventListener('change', remember); });
    const lockFields = () => {
      fields.forEach(e => { e.disabled = !!draft.pending || !!k.source_document; });
      $('#skSave').disabled = !!k.source_document && !draft.pending;
      $('#skSave').textContent = draft.pending ? '같은 요청 결과 다시 확인' : key === '__new__' ? '온톨로지에 추가' : '저장';
      $('#skReload').disabled = !!draft.pending;
    };
    lockFields();
    if (draft.pending) $('#skMsg').textContent = '응답을 확인하지 못한 요청입니다. 같은 요청으로 저장 결과를 확인하세요.';
    else if (Object.keys(draft.fields).length) $('#skMsg').textContent = '저장하지 않은 변경 사항';
    $('#skReload').addEventListener('click', async () => {
      if (draft.pending) return;
      clearSkillDraft(key); box.dataset.key = ''; await loadSkills();
    });
    $('#skSource')?.addEventListener('click', async (ev) => {
      ev.currentTarget.disabled = true;
      try {
        const preview = await postJ(API.process + '/api/kg/manuals/sources/' + encodeURIComponent(k.source_id) + '/preview', {});
        selectTab('ontology'); H.preview = preview;
        $('#manualDocumentId').value = preview.document_id; renderPreview();
        $('#manualFile').scrollIntoView({block:'center'});
      } catch (e) { if (box.dataset.key === key) $('#skMsg').textContent = '원문 확인 실패: ' + e.message; }
      finally { const button = box.querySelector('#skSource'); if (button) button.disabled = false; }
    });
    $('#skSave').addEventListener('click', async (ev) => {
      const b = ev.currentTarget;
      const body = draft.pending || { name: $('#skName').value.trim(), description: $('#skDesc').value, approver: $('#skRole').value, by: $('#skBy').value.trim(), revision: draft.revision, request_id: crypto.randomUUID() };
      if (!draft.pending && key === '__new__') Object.assign(body, { sopId: $('#skSop').value.trim(), failureMode: $('#skFm').value, relation: $('#skRel').value, kind: $('#skKind').value, steps: $('#skSteps').value });
      if (!body.name) { $('#skMsg').textContent = '스킬 이름을 입력하세요.'; $('#skName').focus(); return; }
      remember(); draft.pending = body; saveSkillDraft(key, draft); lockFields();
      b.disabled = true; $('#skMsg').textContent = '저장 중…';
      try {
        const r = key === '__new__' ? await postJ(API.process + '/api/kg/skills', body)
          : await postJ(API.process + '/api/kg/skills/' + encodeURIComponent(k.id), body, 'PUT');
        if (r.detail && !r.id) throw new Error(r.detail);
        clearSkillDraft(key);
        if (box.dataset.key === key) { H.skillSel = r.id; H.skillNew = false; box.dataset.key = ''; }
        await loadSkills(); if (H.skillSel === r.id && box.querySelector('#skMsg')) $('#skMsg').textContent = '온톨로지에 반영했다.';
      } catch (e) {
        if (e.status >= 400 && e.status < 500) { draft.pending = null; saveSkillDraft(key, draft); }
        if (box.dataset.key === key) {
          lockFields(); $('#skMsg').textContent = '저장 결과: ' + e.message + (draft.pending ? ' 같은 요청으로 결과를 다시 확인하세요.' : ' 현재 내용을 다시 확인한 뒤 수정하세요.');
        }
      } finally { if (box.contains(b)) b.disabled = !!k.source_document && !draft.pending; }
    });
  }
  $('#skillNew').addEventListener('click', () => { H.skillNew = true; renderSkillList(); renderSkillDetail(); UI.revealDetail($('#skillDetail')); $('#skName').focus({preventScroll:true}); });

  /* ================================================= manual upload → SOP 스킬 인제스천 (고장 유형에 매칭) */
  async function loadManualSources(offset = 0) {
    const box = $('#manualSources');
    try {
      const page = await getJ(API.process + '/api/kg/manuals/sources?offset=' + offset);
      box.innerHTML = `<details><summary>보관 원문 · ${page.total}판본 (적재 전 파일 포함)</summary><p class="muted">${page.total ? offset + 1 : 0}–${offset + page.items.length} / ${page.total}</p>` + page.items.map(s => `<p><a href="${API.process}/api/kg/manuals/sources/${encodeURIComponent(s.source_id)}/original">${esc(s.filename)}</a> · ${esc(UI.dateTime(s.created_at))} · ${s.status === 'READY' ? '텍스트 추출됨' : '페이지/OCR 검토 필요'} <button class="btn" data-manual-reopen="${esc(s.source_id)}">다시 검토</button></p>`).join('') + `<div>${offset ? '<button class="btn" id="manualSourcesPrev">이전</button>' : ''}${page.next_offset !== null ? '<button class="btn" id="manualSourcesNext">다음</button>' : ''}</div><p id="manualSourcesMsg" class="muted"></p></details>`;
      box.querySelectorAll('[data-manual-reopen]').forEach(b => b.addEventListener('click', async () => {
        b.disabled = true;
        try {
          if (!H.catalog) H.catalog = await getJ(API.process + '/api/kg/catalog');
          H.preview = await postJ(API.process + '/api/kg/manuals/sources/' + encodeURIComponent(b.dataset.manualReopen) + '/preview', {});
          $('#manualDocumentId').value = H.preview.document_id; renderPreview();
        } catch (e) { $('#manualSourcesMsg').textContent = '원문 다시 읽기 실패: ' + e.message; }
        finally { b.disabled = false; }
      }));
      $('#manualSourcesPrev')?.addEventListener('click', () => loadManualSources(Math.max(0, offset - page.limit)));
      $('#manualSourcesNext')?.addEventListener('click', () => loadManualSources(page.next_offset));
    } catch (e) { box.textContent = '보관 원문을 읽지 못했습니다: ' + e.message; }
  }
  async function loadUploads() {
    await loadManualSources();
    try {
      const ups = await getJ(API.process + '/api/kg/manuals');
      const history = $('#manualHistory'), wasOpen = !!history.querySelector('details[open]');
      history.innerHTML = ups.length ? `<details class="technical" ${wasOpen ? 'open' : ''}><summary>매뉴얼 등록 이력 · ${ups.length}건</summary><div class="table-scroll"><table class="prov"><thead><tr><th>매뉴얼</th><th>등록 내용</th><th>등록자</th><th>등록 시각</th><th>판본</th></tr></thead><tbody>` + ups.map(u => `<tr><td><a href="${API.process}/api/kg/manuals/sources/${encodeURIComponent(u.source_id)}/original">${esc(u.filename)}</a></td><td>절 ${u.sections} · SOP ${u.procedures} · 단계 ${u.steps}</td><td>${esc(u.by)}</td><td>${esc(UI.dateTime(u.t))}</td><td>${u.status === 'ROLLED_BACK' ? '되돌림' : u.current ? '현재 판본' : '이전 판본'} <button class="btn" data-manual-revise="${esc(u.document_id)}">이 문서 개정</button>${u.current && u.status === 'ACTIVE' ? ` <button class="btn" data-manual-undo="${esc(u.batch)}">이 판본 되돌리기</button>` : ''}</td></tr>`).join('') + '</tbody></table></div><p class="muted" id="manualHistoryMsg">되돌리기는 최신 판본부터 진행합니다. 다른 규칙·실행의 참조나 외부 편집이 있으면 먼저 조정해야 합니다. 보관한 원문은 지우지 않습니다.</p></details>' : '';
      history.querySelectorAll('[data-manual-revise]').forEach(b => b.addEventListener('click', () => {
        $('#manualDocumentId').value = b.dataset.manualRevise;
        $('#manualHistoryMsg').textContent = '개정할 문서를 선택했습니다. 새 판본 파일을 선택하고 미리보기에서 다시 검토하세요.';
        H.preview = null; renderPreview();
      }));
      history.querySelectorAll('[data-manual-undo]').forEach(b => b.addEventListener('click', async () => {
        b.disabled = true;
        try {
          await postJ(API.process + '/api/kg/manuals/batches/' + encodeURIComponent(b.dataset.manualUndo) + '/rollback', {by: $('#manualBy').value});
          H.preview = null; renderPreview(); H.skills = [];
          await loadUploads(); if (window.hydEnt) hydEnt.loadGraph(true);
        } catch (e) { $('#manualHistoryMsg').textContent = '되돌리기 실패: ' + e.message; b.disabled = false; }
      }));
    } catch (e) { $('#manualHistory').textContent = '등록 이력을 읽지 못했습니다: ' + e.message; }
  }
  function renderPreview() {
    const r = H.preview; const box = $('#manualResult');
    if (!r) { box.innerHTML = ''; return; }
    const fms = (H.catalog || {}).failureModes || [];
    const citation = a => a ? `<details><summary>원문 인용 · ${a.page}쪽</summary><pre style="white-space:pre-wrap;overflow-wrap:anywhere">${esc(a.quote)}</pre></details>` : '';
    box.innerHTML = `<div class="mprev"><div class="muted">${esc(r.filename)} · ${r.chars}자 · 절 ${r.sections.length}개 · 절차 ${r.procedures.length}개${r.warnings.length ? ' · <span class="neg">' + r.warnings.map(esc).join(' ') + '</span>' : ''}</div>
      <p><a href="${API.process}/api/kg/manuals/sources/${encodeURIComponent(r.source_id)}/original">보관한 원본 내려받기</a> · <button class="btn" id="manualFullSource">추출 원문 전체 보기</button></p><div id="manualSourceText"></div>
      <p><button class="btn" id="manualAgentExtract" ${r.status === 'READY' ? '' : 'disabled'}>에이전트 추출 요청</button> <button class="btn" id="manualAgentResult">추출 진행·결과 확인</button> <span id="manualAgentStatus" role="status">${r.extraction ? '에이전트 제안입니다. 원문을 대조하고 검토 후 적재하세요.' : '현재 결과는 구조화된 줄 파서입니다. 일반 문서는 에이전트 추출을 요청하세요.'}</span></p>
      <label>이 문서의 추출 작업 <select id="manualExtractionRuns"><option value="">작업 목록 읽는 중…</option></select></label> <button class="btn" id="manualExtractionMore" style="display:none">이전 추출 작업 더 보기</button>
      ${r.page_reviews ? `<details><summary>페이지별 추출 검토 기록</summary>${r.page_reviews.map(p => `<p>${esc(p.page)}쪽: ${esc(p.note)}</p>`).join('')}</details>` : ''}
      <div class="mcols"><div><h3>매뉴얼 절 (ManualSection)</h3>${r.sections.map(s => `<div class="msec"><b>${esc(s.ref)}</b> ${esc(s.title)}<details><summary>절 본문 전체</summary><div class="muted" style="white-space:pre-wrap;overflow-wrap:anywhere">${esc(s.excerpt)}</div></details>${citation(s.anchor)}</div>`).join('') || '<div class="muted">없음</div>'}</div>
      <div><h3>SOP → 조치 방법 스킬 (Skill → Step)</h3>${r.procedures.map(p => `<div class="mproc"><label>등록할 SOP 번호 <input aria-label="등록할 SOP 번호" data-manual-id="${esc(p.id)}" value="${esc(p.id)}"></label><label>이름 <input aria-label="SOP 이름" data-manual-name="${esc(p.id)}" value="${esc(p.name)}"></label>${citation(p.anchor)}
        <label class="muted">매칭할 고장 유형 <select data-fm="${esc(p.id)}"><option value="">(고르세요)</option>${fms.map(f => `<option value="${esc(f.id)}" ${f.id === p.suggestedFailureMode ? 'selected' : ''}>${esc(f.name)}</option>`).join('')}</select></label>
        <label class="muted">관계 <select data-rel="${esc(p.id)}"><option value="REMEDIED_BY">근본 조치</option><option value="MITIGATED_BY">즉시 완화</option></select></label>
        <label class="muted">종류 <select data-kind="${esc(p.id)}"><option value="work_order">정비 작업지시</option><option value="control">설비 제어</option></select></label>
        <ol>${p.steps.map(s => `<li><textarea aria-label="SOP ${esc(p.id)} 단계 ${s.order}" data-manual-step="${esc(p.id)}" data-order="${s.order}" rows="2">${esc(s.text)}</textarea> <span class="muted">${esc(s.manual || '')}</span>${citation(s.anchor)}</li>`).join('')}</ol></div>`).join('') || '<div class="muted">없음</div>'}</div></div>
      <label><input type="checkbox" id="manualReviewed"> 원문·단계·고장 유형·관계를 검토했습니다. 규칙의 실행 후보는 자동으로 바뀌지 않습니다.</label>
      <div class="approve-row"><button class="btn primary" id="manualCommit" ${r.status === 'READY' && r.sections.length && r.procedures.length ? '' : 'disabled'}>검토한 내용 적재</button><span id="manualMsg" class="muted"></span></div></div>`;
    $('#manualFullSource').addEventListener('click', async () => {
      try {
        const source = await getJ(API.process + '/api/kg/manuals/sources/' + encodeURIComponent(r.source_id));
        if (H.preview !== r) return;
        $('#manualSourceText').innerHTML = source.pages.map(p => `<details><summary>${p.page}쪽 전체</summary><pre style="white-space:pre-wrap;overflow-wrap:anywhere">${esc(p.text)}</pre></details>`).join('');
      } catch (e) { if (H.preview === r) $('#manualSourceText').textContent = '원문 조회 실패: ' + e.message; }
    });
    const extractionKey = 'hyd.manual.extraction.' + r.source_id;
    const extractionUrl = API.process + '/api/kg/manuals/sources/' + encodeURIComponent(r.source_id) + '/extractions';
    const extractionState = () => JSON.parse(sessionStorage.getItem(extractionKey) || 'null');
    let extractionOffset = 0;
    const loadExtractions = async (append = false) => {
      try {
        const page = await getJ(extractionUrl + '?offset=' + (append ? extractionOffset : 0));
        if (H.preview !== r) return;
        const select = $('#manualExtractionRuns');
        if (!append) select.innerHTML = '<option value="">추출 작업 선택</option>';
        for (const run of page.items) {
          const option = document.createElement('option'); option.value = run.proc_inst_id;
          option.textContent = UI.dateTime(run.start_date) + ' · ' + run.status + ' · ' + run.proc_inst_id.slice(-8);
          select.append(option);
        }
        const chosen = r.extraction?.instance || extractionState()?.instance;
        if (chosen && Array.from(select.options).some(o => o.value === chosen)) select.value = chosen;
        else if (!select.value && select.options.length > 1) select.selectedIndex = 1;
        extractionOffset = page.next_offset;
        $('#manualExtractionMore').style.display = page.next_offset === null ? 'none' : '';
      } catch (e) { if (H.preview === r) $('#manualAgentStatus').textContent = '추출 이력 조회 실패: ' + e.message; }
    };
    $('#manualExtractionMore').addEventListener('click', () => loadExtractions(true));
    loadExtractions();
    $('#manualAgentExtract').addEventListener('click', async () => {
      const button = $('#manualAgentExtract'); button.disabled = true;
      try {
        const previous = extractionState();
        const state = previous && !previous.instance ? previous : {request_id: crypto.randomUUID()};
        sessionStorage.setItem(extractionKey, JSON.stringify(state));
        const created = await postJ(extractionUrl, {request_id: state.request_id});
        sessionStorage.setItem(extractionKey, JSON.stringify({...state, instance: created.instance}));
        await loadExtractions();
        if (H.preview === r) $('#manualAgentStatus').textContent = '추출 작업 접수됨. 워커 실행 후 진행·결과 확인을 누르세요. 접수는 추출 완료가 아닙니다.';
      } catch (e) { if (H.preview === r) $('#manualAgentStatus').textContent = '접수 확인 실패: ' + e.message + ' 같은 요청으로 다시 확인할 수 있습니다.'; }
      finally { if (H.preview === r) button.disabled = false; }
    });
    $('#manualAgentResult').addEventListener('click', async () => {
      try {
        const instance = $('#manualExtractionRuns').value;
        if (!instance) { $('#manualAgentStatus').textContent = '추출 작업을 선택하세요. 응답을 받지 못한 요청은 추출 요청 버튼으로 접수를 재확인하세요.'; return; }
        const result = await getJ(extractionUrl + '/' + encodeURIComponent(instance));
        if (H.preview !== r) return;
        if (result.preview) { H.preview = result.preview; renderPreview(); }
        else $('#manualAgentStatus').textContent = '추출 상태: ' + result.status + (result.log ? ' · ' + result.log : '') + ' — 프로세스 인스턴스 화면에서 작업·오류를 확인할 수 있습니다.';
      } catch (e) { if (H.preview === r) $('#manualAgentStatus').textContent = '결과 확인 실패: ' + e.message; }
    });
    const c = $('#manualCommit'); if (c) c.addEventListener('click', async () => {
      if (!$('#manualReviewed').checked) { $('#manualMsg').textContent = '원문을 대조하고 검토 완료를 표시하세요.'; return; }
      const links = {};
      box.querySelectorAll('[data-fm]').forEach(s => { const id = s.dataset.fm; links[id] = { failureMode: s.value || null, relation: box.querySelector(`[data-rel="${CSS.escape(id)}"]`).value, kind: box.querySelector(`[data-kind="${CSS.escape(id)}"]`).value }; });
      const missing = Object.entries(links).filter(([, v]) => !v.failureMode).map(([k]) => k);
      if (missing.length) { $('#manualMsg').textContent = `고장 유형을 고르세요: ${missing.join(', ')} — 조치 방법(SOP)은 고장 유형에 매칭되어야 합니다.`; return; }
      c.disabled = true;
      $('#manualMsg').textContent = '적재 중…';
      try {
        const reviewed = structuredClone(r);
        box.querySelectorAll('[data-manual-name]').forEach(input => { reviewed.procedures.find(p => p.id === input.dataset.manualName).name = input.value; });
        box.querySelectorAll('[data-manual-step]').forEach(input => { reviewed.procedures.find(p => p.id === input.dataset.manualStep).steps.find(s => s.order === Number(input.dataset.order)).text = input.value; });
        const reviewedLinks = {};
        box.querySelectorAll('[data-manual-id]').forEach(input => {
          const p = reviewed.procedures.find(p => p.id === input.dataset.manualId);
          p.id = input.value.trim(); reviewedLinks[p.id] = links[input.dataset.manualId];
        });
        const out = await postJ(API.process + '/api/kg/manuals/commit', { ...reviewed, links: reviewedLinks, by: $('#manualBy').value, reviewed: true });
        if (H.preview !== r) return;
        $('#manualMsg').textContent = `적재 완료: 절 ${out.sections} · SOP ${out.procedures} · 단계 ${out.steps}. 실행 후보 규칙은 변경하지 않았습니다.`;
        c.textContent = '적재 완료';
        H.skills = [];
        await loadUploads(); if (window.hydEnt) hydEnt.loadGraph(true);
      } catch (e) { if (H.preview === r) { $('#manualMsg').textContent = '실패: ' + e.message; c.disabled = false; } }
    });
    box.oninput = event => { if (event.target.id !== 'manualReviewed') $('#manualReviewed').checked = false; };
  }
  $('#manualPreview').addEventListener('click', async () => {
    const f = $('#manualFile').files[0]; if (!f) { $('#manualResult').innerHTML = '<div class="neg">파일을 먼저 선택해 주세요.</div>'; return; }
    const b = $('#manualPreview'); b.disabled = true; b.textContent = '읽는 중…'; H.preview = null;
    $('#manualResult').innerHTML = '<div class="muted" role="status">매뉴얼을 읽는 중…</div>';
    try {
      const b64 = await new Promise((ok, no) => { const rd = new FileReader(); rd.onload = () => ok(String(rd.result).split(',')[1] || ''); rd.onerror = () => no(new Error('파일을 읽을 수 없습니다.')); rd.readAsDataURL(f); });
      if (!H.catalog) H.catalog = await getJ(API.process + '/api/kg/catalog');
      const preview = await postJ(API.process + '/api/kg/manuals/preview', { filename: f.name, data: b64, document_id: $('#manualDocumentId').value.trim() || null });
      if ($('#manualFile').files[0] !== f) return;
      H.preview = preview; renderPreview();
      await loadManualSources();
    } catch (e) { if ($('#manualFile').files[0] === f) $('#manualResult').innerHTML = `<div class="neg">미리보기 실패: ${esc(e.message)}</div>`; }
    finally { b.disabled = false; b.textContent = '미리보기'; }
  });
  $('#manualFile').addEventListener('change', () => { H.preview = null; $('#manualFilename').textContent = $('#manualFile').files[0]?.name || '선택한 파일 없음'; renderPreview(); });

  /* ================================================= DDL upload → System · InputData 인제스천 (되돌리기 가능) */
  async function loadIngests() {
    try {
      const rows = await getJ(API.process + '/api/kg/ingests');
      const box = $('#ddlHistory'); if (!box) return;
      const batches = {};
      rows.forEach(r => { (batches[r.batch] = batches[r.batch] || []).push(r); });
      const keys = Object.keys(batches);
      box.innerHTML = keys.length ? `<details class="technical" open><summary>인제스천 배치 · ${keys.length}건 (활성 배치의 사용 관계)</summary><div class="table-scroll"><table class="prov"><thead><tr><th>배치</th><th>사용 노드</th><th>출처</th><th></th></tr></thead><tbody>`
        + keys.map(k => `<tr><td><code>${esc(k)}</code></td><td>${batches[k].map(r => `${esc(r.label)} ${r.nodes}`).join(' · ')}</td><td class="muted">${esc((batches[k][0] || {}).source || '')}</td><td><button class="btn small" data-clear="${esc(k)}">되돌리기</button></td></tr>`).join('') + '</tbody></table></div></details>' : '<div class="muted">인제스천 배치가 없습니다.</div>';
      box.querySelectorAll('[data-clear]').forEach(b => b.addEventListener('click', async () => {
        if (!confirm(`${b.dataset.clear} 배치의 변경을 되돌립니다. 다른 배치가 사용하는 노드는 유지하며 이전 상태를 복원합니다. 계속할까요?`)) return;
        b.disabled = true;
        try { const out = await postJ(API.process + '/api/kg/ingests/' + encodeURIComponent(b.dataset.clear) + '?by=' + encodeURIComponent($('#ddlBy').value), null, 'DELETE'); $('#ddlMsg').textContent = `되돌리기 완료: ${out.deleted} 삭제 · ${out.restored || 0} 원래 상태 복원 · ${out.retained || 0} 유지`; await loadIngests(); if (window.hydEnt) hydEnt.loadGraph(true); }
        catch (e) { $('#ddlMsg').textContent = '되돌리기 실패: ' + e.message; b.disabled = false; }
      }));
    } catch (e) { }
  }
  function renderDdlPreview() {
    const p = H.ddl; const box = $('#ddlResult');
    if (!p) { box.innerHTML = ''; return; }
    const existing = (p.existingSystems || []).map(s => s.id);
    const sysOptions = sel => [...new Set([...existing, ...p.systems.map(s => s.id), sel].filter(Boolean))].map(id => `<option value="${esc(id)}" ${id === sel ? 'selected' : ''}>${esc(id)}</option>`).join('');
    box.innerHTML = `<div class="mprev"><div class="muted">${esc(p.filename)} · ${p.chars}자 · 테이블 ${p.tables.length}개 · 배치 <code>${esc(p.batch)}</code>${p.warnings.length ? ' · <span class="neg">' + p.warnings.map(esc).join(' ') + '</span>' : ''}</div>
      <div class="mcols"><div><h3>테이블 → 출처 시스템 (System)</h3>${p.tables.map(t => `<div class="msec"><b>${esc(t.table)}</b> <span class="muted">${esc(t.comment || '')}</span>
        <label class="muted">출처 시스템 <select data-sys="${esc(t.table)}"><option value="">(없음 · 적재 안 함)</option>${sysOptions(t.system)}</select></label>
        <div class="ddlcols">${t.columns.map(c => `<label><input type="checkbox" data-col="${esc(t.table)}" value="${esc(c)}" ${t.selected.includes(c) ? 'checked' : ''}> ${esc(c)}</label>`).join('')}</div></div>`).join('')}</div>
      <div><h3>입력 데이터와 실제 위치</h3><p class="muted">${esc(p.datasource)} / ${esc(p.catalog)}</p><div class="table-scroll"><table class="prov"><thead><tr><th>이름</th><th>형</th><th>스키마 · 표 · 열</th><th>업무 시스템</th></tr></thead><tbody>${p.inputs.map(i => `<tr><td>${esc(i.name)}</td><td>${esc(i.typeRef)}</td><td>${esc(i.schema)}<br>${esc(i.table)}<br>${esc(i.column)}</td><td>${esc(i.system)}</td></tr>`).join('') || '<tr><td colspan="4" class="muted">고른 열이 없습니다</td></tr>'}</tbody></table></div><details class="technical"><summary>식별자와 규칙 변수</summary>${p.inputs.map(i => `<p>${esc(i.schema)} · ${esc(i.table)} · ${esc(i.column)}<br>노드 <code>${esc(i.id)}</code><br>변수 <code>${esc(i.variable)}</code></p>`).join('')}</details></div></div>
      <div class="approve-row"><button class="btn" id="ddlReplan">선택 반영</button><button class="btn primary" id="ddlCommit" ${p.inputs.length ? '' : 'disabled'}>온톨로지에 적재</button><span id="ddlMsg" class="muted"></span></div></div>`;
    $('#ddlReplan').addEventListener('click', async () => {
      const selection = {}, systems = {};
      box.querySelectorAll('[data-sys]').forEach(s => { if (s.value) systems[s.dataset.sys] = s.value; });
      box.querySelectorAll('[data-col]').forEach(c => { if (c.checked && systems[c.dataset.col]) (selection[c.dataset.col] = selection[c.dataset.col] || []).push(c.value); });
      try { H.ddl = await postJ(API.process + '/api/kg/ddl/preview', { filename: p.filename, text: H.ddlText, selection, systems, datasource: p.datasource, catalog: p.catalog }); renderDdlPreview(); }
      catch (e) { $('#ddlMsg').textContent = '실패: ' + e.message; }
    });
    $('#ddlCommit').addEventListener('click', async () => {
      const c = $('#ddlCommit'); c.disabled = true; $('#ddlMsg').textContent = '적재 중…';
      try {
        const out = await postJ(API.process + '/api/kg/ddl/commit', { ...p, by: $('#ddlBy').value });
        $('#ddlMsg').textContent = `적재 완료: 시스템 ${out.systems} · 입력 데이터 ${out.inputs} (배치 ${out.batch}). 되돌리려면 아래 이력에서 "되돌리기".`;
        c.textContent = '적재 완료';
        await loadIngests(); if (window.hydEnt) hydEnt.loadGraph(true);
      } catch (e) { $('#ddlMsg').textContent = '실패: ' + e.message; c.disabled = false; }
    });
  }
  $('#ddlPreview').addEventListener('click', async () => {
    const f = $('#ddlFile').files[0]; if (!f) { $('#ddlResult').innerHTML = '<div class="neg">파일을 먼저 선택해 주세요.</div>'; return; }
    const b = $('#ddlPreview'); b.disabled = true; b.textContent = '읽는 중…'; H.ddl = null;
    $('#ddlResult').innerHTML = '<div class="muted" role="status">DDL 을 읽는 중…</div>';
    try {
      H.ddlText = await f.text();
      const preview = await postJ(API.process + '/api/kg/ddl/preview', { filename: f.name, text: H.ddlText, datasource: $('#ddlDatasource').value.trim(), catalog: $('#ddlCatalog').value.trim() });
      if ($('#ddlFile').files[0] !== f) return;
      H.ddl = preview; renderDdlPreview(); await loadIngests();
    } catch (e) { if ($('#ddlFile').files[0] === f) $('#ddlResult').innerHTML = `<div class="neg">미리보기 실패: ${esc(e.message)}</div>`; }
    finally { b.disabled = false; b.textContent = '미리보기'; }
  });
  $('#ddlFile').addEventListener('change', () => { H.ddl = null; $('#ddlFilename').textContent = $('#ddlFile').files[0]?.name || '선택한 파일 없음'; renderDdlPreview(); });
  ['ddlDatasource', 'ddlCatalog'].forEach(id => $('#' + id).addEventListener('input', () => { H.ddl = null; renderDdlPreview(); }));

  /* ------------------------------------------------ tab hooks */
  const _sel = selectTab;
  selectTab = function (name) {
    _sel(name);
    if (name === 'skills') loadSkills();
    if (name === 'ontology') { loadUploads(); loadIngests(); }
    if (name === 'incidents') refreshHitl(true);
    if (name === 'process') refreshProcBpmn();
    if (name !== 'incidents') { const b = document.getElementById('hitlPanel'); if (b) b.innerHTML = ''; H.sig = null; }
  };
  window.hydApp.selectTab = selectTab;
})();
