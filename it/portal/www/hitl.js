/* HITL · BPMN · skill catalog · manual upload (loaded after app.js / enterprise.js / main.js).
   - BPMN-style flow of the anomaly → action process, highlighted with the live state of one incident + its decision
   - HITL panel: the agent's ranked options (ontology · skills · KPI · policies · precedents) → one human decision
   - skill catalog: list / edit / add agent skills (written to the ontology by the process service)
   - manual upload: manual → ManualSection / Procedure / Step nodes */
(function () {
  const H = { inc: null, decs: [], dec: null, sig: null, form: { option: null, reason: '', role: null, by: 'OP-17', fan: null, load: null }, msg: '', busy: false,
    skills: [], catalog: null, skillSel: null, skillNew: false, skillDrafts: new Map(), preview: null };

  /* ================================================= BPMN renderer */
  const LANES = ['설비 · 탐지 (L1~L4)', '에이전트 (L8)', '사람 · HITL', '프로세스 (L9)', '기업 시스템', '온톨로지 (L7)'];
  const NODES = {
    start: { lane: 0, x: 186, kind: 'start', label: '이상 발생' },
    alert: { lane: 0, x: 300, kind: 'task', label: '경보 RAISE · CEP' },
    diag: { lane: 1, x: 390, kind: 'task', label: '원인 진단 (T1 · 증거)' },
    lookup: { lane: 1, x: 555, kind: 'task', label: '조치 조회 (T2 · T3)', sub: '스킬 · KPI · 규정 · 선례' },
    rank: { lane: 1, x: 715, kind: 'task', label: '우선순위 · 가드레일' },
    decide: { lane: 2, x: 840, kind: 'task', label: '조치 의사결정', sub: '역할 권한 · 사유' },
    gw: { lane: 2, x: 975, kind: 'gateway', label: '즉시 제어?' },
    cmd: { lane: 3, x: 1100, kind: 'task', label: 'action.cmd → PLC', sub: '게이트웨이 5종 검증' },
    reobs: { lane: 3, x: 1262, kind: 'task', label: 'ACK · 15분 재관측' },
    close: { lane: 3, x: 1380, kind: 'end', label: '종결' },
    exec: { lane: 4, x: 1100, kind: 'task', label: '기업 스킬 실행', sub: 'CMMS · ERP · MES · QMS' },
    learn: { lane: 5, x: 1100, kind: 'task', label: '판단 사례 기록', sub: 'Decision → 다음 판단 선례' },
  };
  const FLOWS = [['start', 'alert'], ['alert', 'diag'], ['diag', 'lookup'], ['lookup', 'rank'], ['rank', 'decide'], ['decide', 'gw'],
    ['gw', 'cmd', '예'], ['gw', 'exec', '기업 스킬'], ['cmd', 'reobs'], ['reobs', 'close'], ['decide', 'learn', '', 'msg'], ['learn', 'lookup', '환류', 'loop']];
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
  document.addEventListener('click', e => {
    const b = e.target.closest('[data-bpmn-fit]'); if (!b) return;
    const region = b.parentElement.nextElementSibling;
    const fit = region.classList.toggle('fit');
    b.setAttribute('aria-pressed', String(fit));
    b.textContent = fit ? '읽기 편한 크기로 보기' : '전체 흐름 보기';
  });

  /* ================================================= HITL decision panel (이상 확인 & 조치) */
  const money = v => v == null ? '–' : (v > 0 ? '+' : '') + Number(v).toLocaleString('ko-KR', { maximumFractionDigits: 1 });
  async function refreshHitl(force) {
    const box = document.getElementById('hitlPanel'); if (!box) return;
    const inc = state.tab === 'incidents' ? state.detail : null;
    if (!inc) { if (box.innerHTML) box.innerHTML = ''; H.sig = null; return; }
    let decs = [];
    try { decs = (await getJ(API.process + '/api/decisions')).filter(d => (d.origin || {}).incident === inc.id); } catch (e) { }
    const prim = decs.find(d => (d.scenario || {}).id === 'sc:delivery-vs-maintenance') || decs[0] || null;
    let dec = null;
    if (prim) { try { dec = await getJ(API.process + '/api/decisions/' + prim.id); } catch (e) { } }
    if (state.tab !== 'incidents' || state.detail?.id !== inc.id) return;
    const sig = [inc.id, inc.state, decs.length, dec && dec.id, dec && dec.state, H.msg].join('|');
    if (!force && sig === H.sig) return;
    if (H.inc && H.inc.id !== inc.id) H.form = { option: null, reason: '', role: null, by: 'OP-17', fan: null, load: null };
    H.sig = sig; H.inc = inc; H.decs = decs; H.dec = dec;
    renderHitl();
  }
  function cardVals(inc) {
    const r = ((inc.card || {}).recommended || []);
    return { fan: (r.find(a => a.code === 'FAN_BOOST') || {}).value ?? 100, load: (r.find(a => a.code === 'REDUCE_LOAD') || {}).value ?? 80,
      fanR: (r.find(a => a.code === 'FAN_BOOST') || {}).paramRange || [80, 100], loadR: (r.find(a => a.code === 'REDUCE_LOAD') || {}).paramRange || [60, 90] };
  }
  function renderHitl() {
    const box = document.getElementById('hitlPanel'); const inc = H.inc, d = H.dec;
    let html = '<section class="hitl">' + bpmnSvg({ inc, dec: d }, `<b>${esc(inc.id)}</b> 조치 프로세스 — ${esc(inc.asset)} · 경보 ${esc(inc.alertId)}`);
    if (!d) {
      html += `<div class="hitl-wait">${inc.state === 'AWAITING_APPROVAL' ? '에이전트가 온톨로지 · 스킬 · KPI로 조치 우선순위를 계산하고 있다…' : '이 인시던트에 연결된 전사 판단이 없다. 아래 가이드 카드로 즉시 제어만 승인할 수 있다.'}</div></section>`;
      box.innerHTML = html; return;
    }
    const kname = Object.fromEntries((d.kpis || []).map(k => [k.id, k.name]));
    const opts = [...(d.options || [])].sort((a, b) => (b.feasible - a.feasible) || (b.total - a.total));
    const maxAbs = Math.max(1, ...opts.map(o => Math.abs(o.total)));
    const pending = d.state === 'PENDING_APPROVAL';
    if (!H.form.option) H.form.option = d.recommended;
    const cv = cardVals(inc);
    if (H.form.fan == null) { H.form.fan = cv.fan; H.form.load = cv.load; }
    const roles = Object.entries(d.roles || {}).sort((a, b) => a[1].level - b[1].level);
    if (!H.form.role) { const ro = opts.find(o => o.id === H.form.option); H.form.role = ((ro && ro.approver) || {}).id || (roles[0] || [''])[0]; }
    html += `<div class="hitl-head"><h2>조치 의사결정 (HITL) <span class="pill ${esc(d.state)}">${esc(d.state)}</span></h2>
      <p>${esc((d.scenario || {}).name || '')} — 에이전트가 온톨로지의 스킬 · KPI · 규정 · 과거 선례로 매긴 우선순위다. 하나를 골라 결정하면 즉시 제어는 게이트웨이 경로로, 나머지 스킬은 기업 시스템에서 실행되고, 이 판단은 온톨로지에 기록되어 다음 판단에 반영된다.</p></div>`;
    html += '<div class="hitl-opts">';
    opts.forEach((o, i) => {
      const cooling = (o.skills || []).some(s => s.id === 'skill:cooling-adjust');
      const imp = Object.entries(o.impacts || {}).filter(([, v]) => v).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1])).slice(0, 4);
      const sel = H.form.option === o.id;
      html += `<label class="hopt ${o.feasible ? '' : 'out'} ${sel ? 'sel' : ''} ${o.id === d.recommended ? 'rec' : ''} ${o.id === d.chosen ? 'chosen' : ''}">
        <input type="radio" name="hopt" value="${esc(o.id)}" ${sel ? 'checked' : ''} ${o.feasible && pending ? '' : 'disabled'}>
        <span class="hrank">${o.feasible ? i + 1 : '–'}</span>
        <span class="hbody"><span class="htitle">${esc(o.name)}${o.id === d.recommended ? ' <em class="star">권고</em>' : ''}${cooling ? ' <em class="ot">즉시 제어 포함</em>' : ''}${o.id === d.chosen ? ' <em class="done">결정됨</em>' : ''}</span>
          <span class="hbar"><i style="width:${Math.round(Math.abs(o.total) / maxAbs * 100)}%" class="${o.total >= 0 ? 'pos' : 'neg'}"></i><b class="num">${money(o.total)}만원</b></span>
          <span class="hkpi">${imp.map(([k, v]) => `<span class="${v > 0 ? 'pos' : 'neg'}">${esc(kname[k] || k)} ${money(v)}</span>`).join('')}</span>
          <span class="hskill">${(o.skills || []).map(s => `<span>${esc(s.name)} → ${esc(s.systemName || s.system)}</span>`).join('') || '<span class="none">실행할 스킬 없음</span>'}</span>
          <span class="hmeta">승인: ${esc((o.approver || {}).name || '–')}${o.precedent && o.precedent.n ? ` · 선례 ${o.precedent.n}건 (${Math.round(o.precedent.share * 100)} %)` : ''}
            ${(o.violations || []).map(v => `<span class="hard">${esc(v.name)}</span>`).join('')}${(o.softPenalties || []).map(v => `<span class="soft">${esc(v.name)}</span>`).join('')}</span>
        </span></label>`;
    });
    html += '</div>';
    const chosenOpt = opts.find(o => o.id === H.form.option);
    const cooling = chosenOpt && (chosenOpt.skills || []).some(s => s.id === 'skill:cooling-adjust');
    if (pending) {
      html += `<div class="hitl-form">
        ${cooling && inc.state === 'AWAITING_APPROVAL' ? `<div class="hparam"><label>팬 속도 <input type="range" id="hFan" min="${cv.fanR[0]}" max="${cv.fanR[1]}" value="${H.form.fan}"><output>${H.form.fan}</output> %</label>
          <label>펌프 부하 <input type="range" id="hLoad" min="${cv.loadR[0]}" max="${cv.loadR[1]}" value="${H.form.load}"><output>${H.form.load}</output> %</label><span class="muted">범위는 온톨로지 Action 파라미터</span></div>` : ''}
        <div class="hwho"><label>결정자 <input id="hBy" value="${esc(H.form.by)}"></label>
          <label>역할 <select id="hRole">${roles.map(([id, r]) => `<option value="${esc(id)}" ${id === H.form.role ? 'selected' : ''}>${esc(r.name)} (직급 ${r.level})</option>`).join('')}</select></label></div>
        <label class="hreason">판단 사유 <textarea id="hReason" rows="2" placeholder="예: 고객 납기가 우선, 야간 정비창에 세척 인력 확보됨">${esc(H.form.reason)}</textarea></label>
        <div class="hact"><button class="btn primary" id="hGo">이 조치로 결정</button><span class="neg" id="hMsg">${esc(H.msg)}</span><span class="muted">선택한 안의 승인 역할이 기본값이다. 다른 역할로 바꿔 권한 검사를 확인해 볼 수 있다.</span></div></div>`;
    } else {
      html += `<div class="hitl-done">결정: <b>${esc((opts.find(o => o.id === d.chosen) || {}).name || d.chosen || '')}</b> · ${esc(d.approvedBy || '')} (${esc((d.roles[d.approvedRole] || {}).name || d.approvedRole || '')})${d.override ? ' · 권고와 다른 선택' : ''}${d.reason ? ' · 사유: ' + esc(d.reason) : ''}
        <div class="muted">이 판단은 온톨로지에 Decision 노드로 기록됐고, 같은 판단의 다음 권고 계산에 "현장 판단 선례"로 반영된다.</div>
        ${(d.executions || []).map(x => `<div class="hx"><span class="pill ${x.status === 'DONE' ? 'CLOSED' : x.status === 'VIA_HITL' ? 'AWAITING_APPROVAL' : 'ESCALATED'}">${esc(x.status)}</span> ${esc(x.skill)} — ${esc(x.detail || '')}</div>`).join('')}</div>`;
    }
    const others = H.decs.filter(x => x.id !== d.id);
    if (others.length) html += '<div class="hitl-others">같은 경보에서 함께 올라온 판단: ' + others.map(x => `<a href="#" data-dec="${esc(x.id)}">${esc((x.scenario || {}).name || '')} <span class="pill ${esc(x.state)}">${esc(x.state)}</span></a>`).join(' ') + '</div>';
    html += '</section>';
    box.innerHTML = html;
    box.querySelectorAll('input[name=hopt]').forEach(r => r.addEventListener('change', () => { H.form.option = r.value; H.msg = ''; const o = (H.dec.options || []).find(x => x.id === r.value); if (o && o.approver) H.form.role = o.approver.id; renderHitl(); }));
    const on = (id, ev, fn) => { const e = document.getElementById(id); if (e) e.addEventListener(ev, fn); };
    on('hFan', 'input', e => { H.form.fan = +e.target.value; e.target.nextElementSibling.textContent = e.target.value; });
    on('hLoad', 'input', e => { H.form.load = +e.target.value; e.target.nextElementSibling.textContent = e.target.value; });
    on('hBy', 'input', e => H.form.by = e.target.value);
    on('hRole', 'change', e => { H.form.role = e.target.value; H.msg = ''; });
    on('hReason', 'input', e => H.form.reason = e.target.value);
    on('hGo', 'click', decideNow);
    box.querySelectorAll('[data-dec]').forEach(a => a.addEventListener('click', ev => { ev.preventDefault(); hydEnt.ent.decSel = a.dataset.dec; selectTab('process'); }));
  }
  async function decideNow() {
    if (H.busy) return; H.busy = true;
    const go = $('#hGo'); if (go) { go.disabled = true; go.textContent = '처리 중…'; }
    try {
      await postJ(API.process + `/api/incidents/${H.inc.id}/decide`, { decision: H.dec.id, option: H.form.option, by: H.form.by || '승인자', role: H.form.role,
        reason: H.form.reason, fan_pct: H.form.fan, load_pct: H.form.load });
      H.msg = '';
      await refreshSlow();
    } catch (e) { H.msg = e.message; }
    finally { H.busy = false; await refreshHitl(true); }
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
    box.innerHTML = bpmnSvg(inc ? { inc, dec: d } : null, inc ? `판단 <b>${esc(d.id)}</b> · 인시던트 ${esc(inc.id)}의 진행` : (d ? '수동으로 실행한 판단이다. 설비 인시던트와 연결된 판단을 고르면 진행 상태가 표시된다.' : '판단을 고르면 진행 상태가 표시된다.'));
  }
  setInterval(refreshProcBpmn, 2000);

  /* ================================================= skill catalog */
  async function loadSkills() {
    if (!H.skills.length) $('#skillList').innerHTML = '<div class="muted" role="status">스킬을 불러오는 중…</div>';
    try { H.skills = await getJ(API.process + '/api/kg/skills'); } catch (e) { $('#skillList').innerHTML = `<div class="muted">process(8080) 또는 Neo4j에 연결할 수 없다. ${esc(e.message)}</div>`; return; }
    if (!H.catalog) { try { H.catalog = await getJ(API.process + '/api/kg/catalog'); } catch (e) { H.catalog = { systems: [], processes: [], roles: [], actions: [] }; } }
    if (!H.skillSel && H.skills.length && !H.skillNew) H.skillSel = H.skills[0].id;
    renderSkillList(); renderSkillDetail();
  }
  function renderSkillList() {
    const list = $('#skillList'); list.innerHTML = '';
    for (const k of H.skills) {
      const it = el('div', 'item' + (k.id === H.skillSel && !H.skillNew ? ' sel' : ''));
      keyboardItem(it);
      it.innerHTML = `<strong>${esc(k.name)}</strong><span>${esc((k.system || {}).name || '')} · 승인 ${esc((k.approver || {}).name || '–')}${k.edited ? ' · 편집됨' : ''}</span><span class="d">${esc(k.description || '')}</span>`;
      it.addEventListener('click', () => { H.skillSel = k.id; H.skillNew = false; renderSkillList(); renderSkillDetail(); });
      list.append(it);
    }
  }
  function renderSkillDetail() {
    const box = $('#skillDetail'); const c = H.catalog || { systems: [], processes: [], roles: [] };
    const key = H.skillNew ? '__new__' : H.skillSel;
    if (box.dataset.key === key && box.querySelector('#skName')) return;
    box.dataset.key = key || '';
    const k = H.skillNew ? { id: '(새 스킬)', name: '', description: '', detail: '입력: \n실행: \n파라미터: \n산출: \n가드레일: ', policies: [], infos: [], actions: [], usedBy: [] } : H.skills.find(x => x.id === H.skillSel);
    if (!k) { box.innerHTML = '<div class="empty">왼쪽에서 스킬을 고른다.</div>'; return; }
    const sel = (id, items, cur) => `<select id="${id}">${items.map(x => `<option value="${esc(x.id)}" ${cur === x.id ? 'selected' : ''}>${esc(x.name)}</option>`).join('')}</select>`;
    box.innerHTML = `<div class="skill-edit"><div class="muted mono">${esc(k.id)}${k.updatedBy ? ' · 최근 편집 ' + esc(k.updatedBy) + ' ' + esc((k.updatedAt || '').slice(0, 16)) : ''}</div>
      <label>이름 (name)<input id="skName" value="${esc(k.name)}" maxlength="80"></label>
      <label>설명 (description)<textarea id="skDesc" rows="2">${esc(k.description || '')}</textarea></label>
      <label>스킬 상세 (detail) — 입력 · 실행 · 파라미터 · 산출 · 가드레일<textarea id="skDetail" rows="8" class="mono">${esc(k.detail || '')}</textarea></label>
      <div class="skill-rels"><label>실행 시스템 ${sel('skSys', c.systems, (k.system || {}).id)}</label><label>업무 프로세스 ${sel('skProc', c.processes, (k.process || {}).id)}</label><label>승인 역할 ${sel('skRole', c.roles, (k.approver || {}).id)}</label></div>
      <div class="approve-row"><input id="skBy" value="지식 관리자" aria-label="편집자"><button class="btn primary" id="skSave">${H.skillNew ? '온톨로지에 추가' : '저장'}</button><span id="skMsg" class="muted" role="status"></span></div>
      ${H.skillNew ? '' : `<h3>온톨로지 연결 (읽기)</h3><table class="kvt">
        <tr><th>거는 규정</th><td>${k.policies.map(p => `<span class="${p.kind === 'HARD' ? 'hard' : 'soft'}">${esc(p.kind)} · ${esc(p.name)}</span>`).join(' ') || '없음'}</td></tr>
        <tr><th>필요한 정보</th><td>${k.infos.map(i => `${esc(i.name)} <span class="muted">(${esc(i.system)})</span>`).join('<br>') || '없음'}</td></tr>
        <tr><th>구현하는 조치</th><td>${k.actions.map(a => esc(a.name)).join(', ') || '없음'}</td></tr>
        <tr><th>쓰는 판단 대안</th><td>${k.usedBy.map(u => `${esc(u.scenario)} — ${esc(u.option)}`).join('<br>') || '없음'}</td></tr></table>`}</div>`;
    const fields = [...box.querySelectorAll('input, textarea, select')];
    const draft = H.skillDrafts.get(key);
    if (draft) fields.forEach(e => { if (draft[e.id] != null) e.value = draft[e.id]; });
    const remember = () => { H.skillDrafts.set(key, Object.fromEntries(fields.map(e => [e.id, e.value]))); $('#skMsg').textContent = '저장하지 않은 변경 사항'; };
    fields.forEach(e => { e.addEventListener('input', remember); e.addEventListener('change', remember); });
    if (draft) $('#skMsg').textContent = '저장하지 않은 변경 사항';
    $('#skSave').addEventListener('click', async (ev) => {
      const b = ev.currentTarget;
      const body = { name: $('#skName').value.trim(), description: $('#skDesc').value, detail: $('#skDetail').value, system: $('#skSys').value, process: $('#skProc').value, approver: $('#skRole').value, by: $('#skBy').value.trim() };
      if (!body.name) { $('#skMsg').textContent = '스킬 이름을 입력하세요.'; $('#skName').focus(); return; }
      b.disabled = true; $('#skMsg').textContent = '저장 중…';
      try {
        const r = key === '__new__' ? await postJ(API.process + '/api/kg/skills', body)
          : await postJ(API.process + '/api/kg/skills/' + encodeURIComponent(k.id), body, 'PUT');
        if (r.detail && !r.id) throw new Error(r.detail);
        H.skillDrafts.delete(key);
        if (box.dataset.key === key) { H.skillSel = r.id; H.skillNew = false; box.dataset.key = ''; }
        await loadSkills(); if (H.skillSel === r.id) $('#skMsg').textContent = '온톨로지에 반영했다.';
      } catch (e) { if (box.dataset.key === key) $('#skMsg').textContent = '실패: ' + e.message; }
      finally { b.disabled = false; }
    });
  }
  $('#skillNew').addEventListener('click', () => { H.skillNew = true; renderSkillList(); renderSkillDetail(); });

  /* ================================================= manual upload → SOP ingestion */
  async function loadUploads() {
    try {
      const ups = await getJ(API.process + '/api/kg/manuals');
      $('#manualHistory').innerHTML = ups.length ? '<div class="muted">적재 이력: ' + ups.map(u => `${esc(u.filename)} (절 ${u.sections} · 절차 ${u.procedures}, ${esc(u.by)} ${esc((u.t || '').slice(0, 16))})`).join(' · ') + '</div>' : '';
    } catch (e) { }
  }
  function renderPreview() {
    const r = H.preview; const box = $('#manualResult');
    if (!r) { box.innerHTML = ''; return; }
    const acts = (H.catalog || {}).actions || [];
    box.innerHTML = `<div class="mprev"><div class="muted">${esc(r.filename)} · ${r.chars}자 · 절 ${r.sections.length}개 · 절차 ${r.procedures.length}개${r.warnings.length ? ' · <span class="neg">' + r.warnings.map(esc).join(' ') + '</span>' : ''}</div>
      <div class="mcols"><div><h3>매뉴얼 절 (ManualSection)</h3>${r.sections.map(s => `<div class="msec"><b>${esc(s.ref)}</b> ${esc(s.title)}<div class="muted">${esc(s.excerpt)}</div></div>`).join('') || '<div class="muted">없음</div>'}</div>
      <div><h3>SOP (Procedure → Step)</h3>${r.procedures.map(p => `<div class="mproc"><b>${esc(p.id)}</b> ${esc(p.name)}
        <label class="muted">연결할 조치 <select data-link="${esc(p.id)}"><option value="">(연결 안 함)</option>${acts.map(a => `<option value="${esc(a.id)}" ${a.id === p.suggestedAction ? 'selected' : ''}>${esc(a.name)}</option>`).join('')}</select></label>
        <ol>${p.steps.map(s => `<li>${esc(s.text)} <span class="muted">${esc(s.manual || '')}</span></li>`).join('')}</ol></div>`).join('') || '<div class="muted">없음</div>'}</div></div>
      <div class="approve-row"><button class="btn primary" id="manualCommit" ${r.sections.length || r.procedures.length ? '' : 'disabled'}>온톨로지에 적재</button><span id="manualMsg" class="muted"></span></div></div>`;
    const c = $('#manualCommit'); if (c) c.addEventListener('click', async () => {
      c.disabled = true;
      $('#manualMsg').textContent = '적재 중…';
      const links = {}; box.querySelectorAll('[data-link]').forEach(s => links[s.dataset.link] = s.value || null);
      try {
        const out = await postJ(API.process + '/api/kg/manuals/commit', { ...r, links, by: $('#manualBy').value });
        if (H.preview !== r) return;
        $('#manualMsg').textContent = `적재 완료: 절 ${out.sections} · 절차 ${out.procedures} · 단계 ${out.steps}. 지식 지도를 다시 읽는다.`;
        c.textContent = '적재 완료';
        await loadUploads(); if (window.hydEnt) hydEnt.loadGraph(true);
      } catch (e) { if (H.preview === r) { $('#manualMsg').textContent = '실패: ' + e.message; c.disabled = false; } }
    });
  }
  $('#manualPreview').addEventListener('click', async () => {
    const f = $('#manualFile').files[0]; if (!f) { $('#manualResult').innerHTML = '<div class="neg">파일을 먼저 고른다.</div>'; return; }
    const b = $('#manualPreview'); b.disabled = true; b.textContent = '읽는 중…'; H.preview = null;
    $('#manualResult').innerHTML = '<div class="muted" role="status">매뉴얼을 읽는 중…</div>';
    try {
      const b64 = await new Promise((ok, no) => { const rd = new FileReader(); rd.onload = () => ok(String(rd.result).split(',')[1] || ''); rd.onerror = () => no(new Error('파일을 읽을 수 없습니다.')); rd.readAsDataURL(f); });
      if (!H.catalog) H.catalog = await getJ(API.process + '/api/kg/catalog');
      const preview = await postJ(API.process + '/api/kg/manuals/preview', { filename: f.name, data: b64 });
      if ($('#manualFile').files[0] !== f) return;
      H.preview = preview; renderPreview();
    } catch (e) { if ($('#manualFile').files[0] === f) $('#manualResult').innerHTML = `<div class="neg">미리보기 실패: ${esc(e.message)}</div>`; }
    finally { b.disabled = false; b.textContent = '미리보기'; }
  });
  $('#manualFile').addEventListener('change', () => { H.preview = null; renderPreview(); });

  /* ------------------------------------------------ tab hooks */
  const _sel = selectTab;
  selectTab = function (name) {
    _sel(name);
    if (name === 'skills') loadSkills();
    if (name === 'ontology') loadUploads();
    if (name === 'incidents') refreshHitl(true);
    if (name === 'process') refreshProcBpmn();
    if (name !== 'incidents') { const b = document.getElementById('hitlPanel'); if (b) b.innerHTML = ''; H.sig = null; }
  };
  window.hydApp.selectTab = selectTab;
})();
