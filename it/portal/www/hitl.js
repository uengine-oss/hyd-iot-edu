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
    if (H.inc && H.inc.id !== inc.id) H.form = { option: null, reason: '', role: null, by: 'OP-17', fan: null, load: null };
    H.sig = sig; H.inc = inc; H.decs = decs; H.dec = dec;
    renderHitl();
  }
  const cmdOf = (o, param) => ((o && o.actions) || []).find(a => a.kind === 'command' && a.param === param);
  function renderHitl() {
    const box = document.getElementById('hitlPanel'); const inc = H.inc, d = H.dec;
    let html = '<section class="hitl">' + bpmnSvg({ inc, dec: d }, `<b>${esc(inc.id)}</b> 조치 프로세스 — ${esc(inc.asset)} · 경보 ${esc(inc.alertId)}`);
    if (!d) {
      html += `<div class="hitl-wait">${inc.state === 'AWAITING_APPROVAL' ? '에이전트가 고장 유형에 매칭된 조치 방법(SOP)을 규칙 · 예측 · 성과 지표로 비교하고 있습니다…' : '이 인시던트에는 조치 카드가 없습니다. 아래 가이드 카드에서 설비 제어를 승인할 수 있습니다.'}</div></section>`;
      setDiagramContent(box, html, inc.id); return;
    }
    const opts = d.options || [];
    const maxAbs = Math.max(1, ...opts.map(o => Math.abs(o.score || 0)));
    const pending = d.state === 'PENDING_APPROVAL';
    if (!H.form.option) H.form.option = d.recommended || (opts.find(o => o.feasible) || {}).id;
    const chosenOpt = opts.find(o => o.id === H.form.option);
    const fanA = cmdOf(chosenOpt, 'fan_pct'), loadA = cmdOf(chosenOpt, 'load_pct');
    if (H.form.cardFor !== H.form.option) { H.form.fan = fanA ? fanA.value : null; H.form.load = loadA ? loadA.value : null; H.form.cardFor = H.form.option; }
    const roles = Object.entries(d.roles || {}).sort((a, b) => a[1].level - b[1].level);
    if (!H.form.role) H.form.role = ((chosenOpt && chosenOpt.approver) || {}).id || (roles[0] || [''])[0];
    const sc = d.scenario || {};
    html += `<div class="hitl-head"><h2>조치 카드 선택 (HITL) <span class="pill ${esc(d.state)}">${esc(UI.status(d.state))}</span></h2>
      <p>${esc(sc.failureMode || '')} — 원인 '${esc(sc.cause || '')}'. 에이전트가 이 고장 유형에 매칭된 조치 방법(스킬 = SOP)을 온톨로지의 DMN 규칙으로 고르고 거른 뒤, 예측 · BSC 득실 · 선례로 순위를 매겼다. 카드마다 "출처 보기"로 규칙 · SOP 단계 · 매뉴얼 근거를 확인하고 하나를 고르면, PLC 명령은 게이트웨이를 거쳐 설비로, 작업지시 · 구매는 기업 시스템으로 가고, 이 선택은 판단 사례로 기록되어 다음 판단의 선례가 된다.</p>
      <div class="summary">${esc(d.explanation || '')}</div></div>`;
    html += '<div class="hitl-opts">' + opts.map(o => hydCards.cardHtml(o, { rec: d.recommended, chosen: d.chosen, selectable: true, selected: H.form.option === o.id, pending, maxAbs })).join('') + '</div>';
    if (d.rankRule) html += `<p class="muted">순위 규칙 ${esc(d.rankRule.rule)}: ${esc(d.rankRule.annotation || '')}</p>`;
    if (pending) {
      const live = inc.state === 'AWAITING_APPROVAL';
      html += `<div class="hitl-form">
        ${live && (fanA || loadA) ? `<div class="hparam">${fanA ? `<label>팬 속도 <input type="range" id="hFan" min="${fanA.min ?? 0}" max="${fanA.max ?? 100}" value="${H.form.fan}"><output>${H.form.fan}</output> %</label>` : ''}
          ${loadA ? `<label>펌프 부하 <input type="range" id="hLoad" min="${loadA.min ?? 60}" max="${loadA.max ?? 100}" value="${H.form.load}"><output>${H.form.load}</output> %</label>` : ''}<span class="muted">기본값은 SOP의 값, 범위는 온톨로지 원자 조치(Action)의 min · max</span></div>` : ''}
        <div class="hwho"><label>결정자 <input id="hBy" value="${esc(H.form.by)}"></label>
          <label>역할 <select id="hRole">${roles.map(([id, r]) => `<option value="${esc(id)}" ${id === H.form.role ? 'selected' : ''}>${esc(r.name)} (직급 ${r.level})</option>`).join('')}</select></label></div>
        <label class="hreason">판단 사유 <textarea id="hReason" rows="2" placeholder="예: 납기 오더가 남아 있어 부하를 크게 줄일 수 없음, 야간 세척 인력 확보됨">${esc(H.form.reason)}</textarea></label>
        <div class="hact"><button class="btn primary" id="hGo">이 카드로 결정</button><span class="neg" id="hMsg">${esc(H.msg)}</span><span class="muted">고른 카드의 승인 역할이 기본값이다. 다른 역할로 바꿔 권한 검사를 확인해 볼 수 있다.</span></div></div>`;
    } else {
      const ch = opts.find(o => o.id === d.chosen) || {};
      html += `<div class="hitl-done">결정: <b>${esc(ch.sopId || '')} ${esc(ch.name || d.chosen || '')}</b> · ${esc(d.approvedBy || '')} (${esc(((d.roles || {})[d.approvedRole] || {}).name || d.approvedRole || '')})${d.override ? ' · 권고와 다른 선택' : ''}${d.reason ? ' · 사유: ' + esc(d.reason) : ''}
        <div class="muted">이 선택은 온톨로지에 판단 사례(DecisionCase -CHOSE-> Skill)로 기록됐고, 같은 고장 유형의 다음 판단에서 선례 점수로 반영된다.</div>
        ${(d.executions || []).map(x => `<div class="hx"><span class="pill ${x.status === 'DONE' ? 'CLOSED' : x.status === 'VIA_HITL' ? 'AWAITING_APPROVAL' : 'ESCALATED'}">${esc(UI.status(x.status))}</span> ${esc(x.code || x.skill)} — ${esc(x.detail || '')}</div>`).join('')}</div>`;
    }
    html += '</section>';
    setDiagramContent(box, html, inc.id);
    box.querySelectorAll('input[name=hopt]').forEach(r => r.addEventListener('change', () => { H.form.option = r.value; H.msg = ''; const o = (H.dec.options || []).find(x => x.id === r.value); if (o && o.approver) H.form.role = o.approver.id; renderHitl(); }));
    const on = (id, ev, fn) => { const e = document.getElementById(id); if (e) e.addEventListener(ev, fn); };
    on('hFan', 'input', e => { H.form.fan = +e.target.value; e.target.nextElementSibling.textContent = e.target.value; });
    on('hLoad', 'input', e => { H.form.load = +e.target.value; e.target.nextElementSibling.textContent = e.target.value; });
    on('hBy', 'input', e => H.form.by = e.target.value);
    on('hRole', 'change', e => { H.form.role = e.target.value; H.msg = ''; });
    on('hReason', 'input', e => H.form.reason = e.target.value);
    on('hGo', 'click', decideNow);
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
    setDiagramContent(box, bpmnSvg(inc ? { inc, dec: d } : null, inc ? `판단 <b>${esc(d.id)}</b> · 인시던트 ${esc(inc.id)}의 진행` : (d ? '수동으로 실행한 판단입니다. 설비 인시던트와 연결된 판단을 선택하면 진행 상태를 확인할 수 있습니다.' : '판단을 선택하면 진행 상태를 확인할 수 있습니다.')), d?.id || 'overview');
  }
  setInterval(refreshProcBpmn, 2000);

  /* ================================================= skill catalog — 조치 방법 = Skill = SOP, 고장 유형에 매칭 */
  const REL_KO = { MITIGATED_BY: '즉시 완화', REMEDIED_BY: '근본 조치' };
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
      <div class="approve-row"><input id="skBy" value="지식 관리자" aria-label="편집자"><button class="btn primary" id="skSave">${H.skillNew ? '온톨로지에 추가' : '저장'}</button><span id="skMsg" class="muted" role="status"></span></div>
      ${H.skillNew ? '<p class="muted">새 스킬은 SOP 번호 · 단계 · 고장 유형 매칭이 있어야 온톨로지 스키마를 지킨다 (Skill = SOP, FailureMode → Skill).</p>' : `<h3>SOP 단계</h3><ol class="steps">${(k.steps || []).map(s => `<li>${esc(s.text)} ${s.manual ? `<span class="muted">[${esc(s.manual)}]</span>` : ''}</li>`).join('') || '<li class="muted">단계 없음</li>'}</ol>
      <h3>연결된 지식</h3><table class="kvt">
        <tr><th>매칭된 고장 유형</th><td>${(k.failureModes || []).map(f => `${esc(f.name)} <span class="muted">(${esc(REL_KO[f.relation] || f.relation)})</span>`).join('<br>') || '없음'}</td></tr>
        <tr><th>해당 원인 한정</th><td>${(k.causes || []).map(x => esc(x.name)).join(', ') || '고장 유형의 모든 원인'}</td></tr>
        <tr><th>원자 조치</th><td>${(k.actions || []).map(a => `${esc(a.code)}${a.value != null ? '=' + esc(a.value) : ''} <span class="muted">${esc(a.name)}</span>`).join('<br>') || '없음'}</td></tr>
        <tr><th>규칙 (DMN)</th><td>${(k.rules || []).map(r => `<span class="${r.effect === 'EXCLUDE' ? 'hard' : r.effect === 'SELECT' ? '' : 'soft'}">${esc(r.effect)} · ${esc(r.annotation || r.id)}</span>`).join(' ') || '없음'}</td></tr>
        <tr><th>움직이는 변수 · 성과 지표</th><td>${(k.affects || []).map(a => `${esc(a.name)} ${a.sign > 0 ? '↑' : '↓'}`).join(', ') || '없음'}</td></tr></table>`}</div>`;
    const fields = [...box.querySelectorAll('input, textarea, select')];
    const draft = H.skillDrafts.get(key);
    if (draft) fields.forEach(e => { if (draft[e.id] != null) e.value = draft[e.id]; });
    const remember = () => { H.skillDrafts.set(key, Object.fromEntries(fields.map(e => [e.id, e.value]))); $('#skMsg').textContent = '저장하지 않은 변경 사항'; };
    fields.forEach(e => { e.addEventListener('input', remember); e.addEventListener('change', remember); });
    if (draft) $('#skMsg').textContent = '저장하지 않은 변경 사항';
    $('#skSave').addEventListener('click', async (ev) => {
      const b = ev.currentTarget;
      const body = { name: $('#skName').value.trim(), description: $('#skDesc').value, approver: $('#skRole').value, by: $('#skBy').value.trim() };
      if (key === '__new__') Object.assign(body, { sopId: $('#skSop').value.trim(), failureMode: $('#skFm').value, relation: $('#skRel').value, kind: $('#skKind').value, steps: $('#skSteps').value });
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
  $('#skillNew').addEventListener('click', () => { H.skillNew = true; renderSkillList(); renderSkillDetail(); UI.revealDetail($('#skillDetail')); $('#skName').focus({preventScroll:true}); });

  /* ================================================= manual upload → SOP 스킬 인제스천 (고장 유형에 매칭) */
  async function loadUploads() {
    try {
      const ups = await getJ(API.process + '/api/kg/manuals');
      const history = $('#manualHistory'), wasOpen = !!history.querySelector('details[open]');
      history.innerHTML = ups.length ? `<details class="technical" ${wasOpen ? 'open' : ''}><summary>매뉴얼 등록 이력 · ${ups.length}건</summary><div class="table-scroll"><table class="prov"><thead><tr><th>매뉴얼</th><th>등록 내용</th><th>등록자</th><th>등록 시각</th></tr></thead><tbody>` + ups.map(u => `<tr><td>${esc(u.filename)}</td><td>매뉴얼 절 ${u.sections}개 · SOP 스킬 ${u.procedures}개 · 단계 ${u.steps}개</td><td>${esc(u.by)}</td><td>${esc(UI.dateTime(u.t))}</td></tr>`).join('') + '</tbody></table></div></details>' : '';
    } catch (e) { }
  }
  function renderPreview() {
    const r = H.preview; const box = $('#manualResult');
    if (!r) { box.innerHTML = ''; return; }
    const fms = (H.catalog || {}).failureModes || [];
    box.innerHTML = `<div class="mprev"><div class="muted">${esc(r.filename)} · ${r.chars}자 · 절 ${r.sections.length}개 · 절차 ${r.procedures.length}개${r.warnings.length ? ' · <span class="neg">' + r.warnings.map(esc).join(' ') + '</span>' : ''}</div>
      <div class="mcols"><div><h3>매뉴얼 절 (ManualSection)</h3>${r.sections.map(s => `<div class="msec"><b>${esc(s.ref)}</b> ${esc(s.title)}<div class="muted">${esc(s.excerpt)}</div></div>`).join('') || '<div class="muted">없음</div>'}</div>
      <div><h3>SOP → 조치 방법 스킬 (Skill → Step)</h3>${r.procedures.map(p => `<div class="mproc"><b>${esc(p.id)}</b> ${esc(p.name)}
        <label class="muted">매칭할 고장 유형 <select data-fm="${esc(p.id)}"><option value="">(고르세요)</option>${fms.map(f => `<option value="${esc(f.id)}" ${f.id === p.suggestedFailureMode ? 'selected' : ''}>${esc(f.name)}</option>`).join('')}</select></label>
        <label class="muted">관계 <select data-rel="${esc(p.id)}"><option value="REMEDIED_BY">근본 조치</option><option value="MITIGATED_BY">즉시 완화</option></select></label>
        <label class="muted">종류 <select data-kind="${esc(p.id)}"><option value="work_order">정비 작업지시</option><option value="control">설비 제어</option></select></label>
        <ol>${p.steps.map(s => `<li>${esc(s.text)} <span class="muted">${esc(s.manual || '')}</span></li>`).join('')}</ol></div>`).join('') || '<div class="muted">없음</div>'}</div></div>
      <div class="approve-row"><button class="btn primary" id="manualCommit" ${r.sections.length || r.procedures.length ? '' : 'disabled'}>온톨로지에 적재</button><span id="manualMsg" class="muted"></span></div></div>`;
    const c = $('#manualCommit'); if (c) c.addEventListener('click', async () => {
      const links = {};
      box.querySelectorAll('[data-fm]').forEach(s => { const id = s.dataset.fm; links[id] = { failureMode: s.value || null, relation: box.querySelector(`[data-rel="${CSS.escape(id)}"]`).value, kind: box.querySelector(`[data-kind="${CSS.escape(id)}"]`).value }; });
      const missing = Object.entries(links).filter(([, v]) => !v.failureMode).map(([k]) => k);
      if (missing.length) { $('#manualMsg').textContent = `고장 유형을 고르세요: ${missing.join(', ')} — 조치 방법(SOP)은 고장 유형에 매칭되어야 합니다.`; return; }
      c.disabled = true;
      $('#manualMsg').textContent = '적재 중…';
      try {
        const out = await postJ(API.process + '/api/kg/manuals/commit', { ...r, links, by: $('#manualBy').value });
        if (H.preview !== r) return;
        $('#manualMsg').textContent = `적재 완료: 절 ${out.sections} · SOP 스킬 ${out.procedures} · 단계 ${out.steps}. 지식 지도와 스킬 목록을 새로 불러옵니다.`;
        c.textContent = '적재 완료';
        H.skills = [];
        await loadUploads(); if (window.hydEnt) hydEnt.loadGraph(true);
      } catch (e) { if (H.preview === r) { $('#manualMsg').textContent = '실패: ' + e.message; c.disabled = false; } }
    });
  }
  $('#manualPreview').addEventListener('click', async () => {
    const f = $('#manualFile').files[0]; if (!f) { $('#manualResult').innerHTML = '<div class="neg">파일을 먼저 선택해 주세요.</div>'; return; }
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
  $('#manualFile').addEventListener('change', () => { H.preview = null; $('#manualFilename').textContent = $('#manualFile').files[0]?.name || '선택한 파일 없음'; renderPreview(); });

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
