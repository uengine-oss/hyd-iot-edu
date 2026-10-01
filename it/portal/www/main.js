/* Main (landing) view: one picture of the whole idea — a hydraulic power unit feeding an IIoT/SCADA backbone, and the
   ontology knowledge map an agent walks to decide what to do. Live values come from state.plant (app.js polling). */
(function () {
  const G = { asset: '#9aa7b5', obs: '#9aa7b5', failure: '#f07167', action: '#f5a623', org: '#b794f6', sys: '#2dd4bf', decision: '#7aa2ff', agent: '#ffffff' };
  // knowledge-map nodes (a readable subset of the real ontology; ids match seed.cypher / seed_enterprise.cypher)
  const N = [
    ['asset', 'HYD-01', 'asset', 700, 318], ['ts1', '센서 TS1', 'asset', 690, 226], ['ce', '센서 CE', 'asset', 706, 410],
    ['sym', '증상 · 유온 상승', 'obs', 800, 176], ['fm', '고장모드 · 냉각 상실', 'failure', 822, 288], ['cause', '원인 · 쿨러 핀 오염', 'failure', 912, 200],
    ['act', '조치 · 팬 속도 상향', 'action', 990, 112], ['sop', 'SOP-COOL-01', 'action', 1105, 152],
    ['agent', 'AI Agent', 'agent', 960, 326], ['scn', '판단 · 납기 vs 보전', 'decision', 1090, 262],
    ['kpi1', 'KPI · 납기 준수', 'org', 1095, 356], ['kpi2', 'KPI · 부품 단가', 'org', 1012, 428], ['dept', '영업팀 · 구매팀', 'org', 1112, 472],
    ['pol', '규정 · 유온 65 ℃', 'org', 826, 450], ['erp', 'ERP', 'sys', 770, 494], ['mes', 'MES', 'sys', 862, 516], ['cmms', 'CMMS', 'sys', 962, 516],
    ['skill', '스킬 · 작업지시', 'sys', 1066, 526],
  ];
  const E = [['asset', 'ts1'], ['asset', 'ce'], ['sym', 'ts1'], ['sym', 'fm'], ['cause', 'fm'], ['cause', 'act'], ['act', 'sop'],
    ['cause', 'scn'], ['scn', 'kpi1'], ['scn', 'kpi2'], ['kpi1', 'dept'], ['kpi2', 'dept'], ['pol', 'scn'], ['erp', 'agent'], ['mes', 'agent'],
    ['cmms', 'agent'], ['skill', 'cmms'], ['agent', 'cause'], ['agent', 'scn'], ['agent', 'fm'], ['agent', 'pol'], ['scn', 'skill']];

  function nodeSvg([id, label, g, x, y]) {
    if (id === 'agent') {
      return `<g class="m-agent"><circle cx="${x}" cy="${y}" r="44" class="m-halo"/><circle cx="${x}" cy="${y}" r="30" fill="#1b2430" stroke="#fff" stroke-width="2"/>` +
        `<text x="${x}" y="${y - 6}" text-anchor="middle" class="m-agent-t">AI</text><text x="${x}" y="${y + 15}" text-anchor="middle" class="m-agent-s">Agent</text></g>`;
    }
    const w = Math.max(64, label.length * 12 + 20);
    return `<g class="m-node"><rect x="${x - w / 2}" y="${y - 13}" width="${w}" height="26" rx="13" fill="#1b2430" stroke="${G[g]}" stroke-width="1.6"/>` +
      `<circle cx="${x - w / 2 + 12}" cy="${y}" r="4" fill="${G[g]}"/><text x="${x - w / 2 + 22}" y="${y + 4.5}" class="m-node-t">${label}</text></g>`;
  }

  function heroSvg() {
    const pos = Object.fromEntries(N.map(n => [n[0], n]));
    const edges = E.map(([a, b]) => {
      const A = pos[a], B = pos[b];
      const agent = a === 'agent' || b === 'agent';
      return `<line x1="${A[3]}" y1="${A[4]}" x2="${B[3]}" y2="${B[4]}" class="m-edge${agent ? ' m-edge-agent' : ''}"/>`;
    }).join('');
    return `<svg viewBox="0 0 1200 580" role="img" aria-labelledby="mainHeroTitle mainHeroDesc" class="m-hero-svg">
  <title id="mainHeroTitle">유압설비 IIoT SCADA와 지식 지도 기반 에이전트 조치 프로세스</title>
  <desc id="mainHeroDesc">왼쪽은 유압 파워유닛과 센서, 가운데는 MQTT와 Kafka로 이어지는 수집·관제 경로, 오른쪽은 온톨로지 지식 지도와 AI 에이전트이며, 승인된 조치가 다시 설비로 돌아가는 폐루프를 그렸다.</desc>
  <defs>
    <pattern id="mGrid" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0V24" fill="none" stroke="#27354a" stroke-width="1"/></pattern>
    <marker id="mArrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#f5a623"/></marker>
    <marker id="mArrowB" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L10 5L0 10z" fill="#7aa2ff"/></marker>
    <linearGradient id="mOil" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#f5a623" stop-opacity=".55"/><stop offset="1" stop-color="#b86e00" stop-opacity=".75"/></linearGradient>
    <radialGradient id="mHalo"><stop offset="0" stop-color="#b794f6" stop-opacity=".55"/><stop offset="1" stop-color="#b794f6" stop-opacity="0"/></radialGradient>
  </defs>
  <rect width="1200" height="580" fill="#16202d"/><rect width="1200" height="580" fill="url(#mGrid)"/>

  <!-- zone bands -->
  <text x="40" y="48" class="m-zone" fill="#f07167">현장 설비 · IIoT  (L1 ~ L2)</text>
  <text x="538" y="48" class="m-zone" fill="#7aa2ff">관제 · 데이터 백본  (L3 ~ L6)</text>
  <text x="660" y="86" class="m-zone" fill="#b794f6">지식 지도 · 에이전트 조치  (L7 ~ L9)</text>
  <line x1="520" y1="60" x2="520" y2="556" class="m-sep"/><line x1="640" y1="60" x2="640" y2="556" class="m-sep"/>

  <!-- hydraulic power unit (ISO-style line art) -->
  <g class="m-hpu">
    <rect x="70" y="360" width="330" height="140" rx="6" class="m-steel"/>
    <rect x="72" y="398" width="326" height="100" rx="4" fill="url(#mOil)" id="mOilBody"/>
    <path class="m-wave" d="M72 398 q20 -6 40 0 t40 0 t40 0 t40 0 t40 0 t40 0 t40 0 t40 0"/>
    <text x="84" y="386" class="m-lbl">오일 탱크</text>
    <rect x="96" y="262" width="118" height="64" rx="8" class="m-steel"/>
    <path d="M110 270v48M124 270v48M138 270v48M152 270v48M166 270v48M180 270v48M194 270v48" class="m-fin"/>
    <text x="104" y="254" class="m-lbl">구동 모터</text>
    <line x1="214" y1="294" x2="236" y2="294" class="m-steel-l"/>
    <circle cx="266" cy="294" r="30" class="m-steel"/><path d="M252 308 L266 274 L280 308 Z" class="m-sym"/>
    <text x="226" y="346" class="m-lbl">펌프</text>
    <path d="M266 324 V360" class="m-pipe"/>
    <path d="M266 264 V206 H330" class="m-pipe m-flow"/>
    <circle cx="300" cy="206" r="15" class="m-steel"/><path d="M300 206 l8 -8" stroke="#f5a623" stroke-width="2"/>
    <rect x="330" y="180" width="86" height="52" rx="4" class="m-steel"/><path d="M344 194h58M344 206h58M344 218h58" class="m-fin"/>
    <text x="336" y="172" class="m-lbl">제어 밸브</text>
    <path d="M416 194 H452 V132" class="m-pipe m-flow"/>
    <rect x="428" y="72" width="48" height="60" rx="3" class="m-steel"/><rect x="436" y="40" width="8" height="40" fill="#cfd8e3"/>
    <text x="382" y="64" class="m-lbl">실린더</text>
    <path d="M416 218 H470 V300" class="m-pipe m-flow m-flow-ret"/>
    <rect x="430" y="300" width="80" height="120" rx="4" class="m-steel"/>
    <path d="M440 312v96M452 312v96M464 312v96M476 312v96M488 312v96M500 312v96" class="m-fin"/>
    <g class="m-fan" style="transform-origin:470px 452px"><circle cx="470" cy="452" r="22" class="m-steel"/><path d="M470 452 l0 -18 M470 452 l16 9 M470 452 l-16 9" stroke="#cfd8e3" stroke-width="3" stroke-linecap="round"/></g>
    <text x="366" y="330" class="m-lbl">오일 쿨러</text>
    <path d="M430 400 H400" class="m-pipe m-flow m-flow-ret"/>
    <!-- sensors -->
    <g class="m-sensor"><circle cx="118" cy="430" r="15"/><text x="118" y="434" text-anchor="middle">TS1</text></g>
    <g class="m-sensor"><circle cx="300" cy="238" r="13"/><text x="300" y="242" text-anchor="middle">PS1</text></g>
    <g class="m-sensor"><circle cx="496" cy="300" r="13"/><text x="496" y="304" text-anchor="middle">CE</text></g>
    <g class="m-sensor"><circle cx="306" cy="328" r="13"/><text x="306" y="332" text-anchor="middle">VS1</text></g>
    <text x="70" y="532" class="m-cap">유압 파워유닛 HYD-01 · 02 · 03  —  soft-PLC · 인터록 65 ℃</text>
    <text x="70" y="552" class="m-live" id="mLive">실시간 값 불러오는 중…</text>
  </g>

  <!-- IIoT / SCADA backbone -->
  <path d="M133 430 C 200 470, 470 520, 540 470" class="m-data"/>
  <path d="M313 238 C 380 250, 470 260, 540 300" class="m-data"/>
  <path d="M509 300 C 520 300, 530 300, 540 300" class="m-data"/>
  <g class="m-bus">
    <rect x="540" y="110" width="80" height="420" rx="10"/>
    <text x="580" y="140" text-anchor="middle" class="m-bus-t">MQTT</text>
    <text x="580" y="158" text-anchor="middle" class="m-bus-s">EMQX</text>
    <path d="M580 170 v34" stroke="#7aa2ff" stroke-width="2" marker-end="url(#mArrowB)"/>
    <text x="580" y="226" text-anchor="middle" class="m-bus-t">DMZ</text>
    <text x="580" y="244" text-anchor="middle" class="m-bus-s">ingest ↑</text>
    <path d="M580 254 v34" stroke="#7aa2ff" stroke-width="2" marker-end="url(#mArrowB)"/>
    <text x="580" y="310" text-anchor="middle" class="m-bus-t">Kafka</text>
    <text x="580" y="328" text-anchor="middle" class="m-bus-s">Redpanda</text>
    <path d="M580 338 v34" stroke="#7aa2ff" stroke-width="2" marker-end="url(#mArrowB)"/>
    <text x="580" y="394" text-anchor="middle" class="m-bus-t">CEP</text>
    <text x="580" y="412" text-anchor="middle" class="m-bus-s">이상 탐지</text>
    <text x="580" y="462" text-anchor="middle" class="m-bus-t">SCADA</text>
    <text x="580" y="480" text-anchor="middle" class="m-bus-s">FUXA · Grafana</text>
  </g>
  <path d="M620 318 H652" class="m-data m-data-solid" marker-end="url(#mArrowB)"/>

  <!-- knowledge map -->
  <circle cx="960" cy="326" r="120" fill="url(#mHalo)"/>
  ${edges}
  ${N.map(nodeSvg).join('')}

  <!-- closed loop: approved action goes back to the plant through L9 + gateway -->
  <path d="M1010 104 C 900 18, 620 12, 454 38" class="m-loop" marker-end="url(#mArrow)"/>
  <rect x="660" y="8" width="296" height="26" rx="13" fill="#16202d" stroke="#f5a623"/>
  <text x="808" y="26" text-anchor="middle" class="m-loop-t">승인된 조치 → L9 → 게이트웨이 검증 → PLC</text>
</svg>`;
  }

  function stagesHtml() {
    const st = [
      ['scenario', '설비 관찰과 제어', 'L1 ~ L6', '결함을 주입하고 센서값과 경보가 어떻게 달라지는지 확인합니다. 운전 모드를 바꾸어 팬과 펌프를 직접 조작해볼 수 있습니다.'],
      ['ontology', '지식 지도 (온톨로지)', 'L7', '설비의 고장이 어떤 원인·조치·매뉴얼과 연결되는지 살펴봅니다. 스킬, 기업 시스템, 승인 담당자까지 관계를 따라갑니다.'],
      ['decision', '판단과 승인', 'L8 ~ L9', '에이전트의 권고와 부서별 영향을 비교합니다. 담당자가 승인한 뒤 설비 조치와 기업 시스템 작업이 어떻게 실행되는지 확인합니다.'],
    ];
    return st.map(([tab, t, l, d], i) => `<button class="m-stage" data-go="${tab}"><span class="m-step">${i + 1}</span><span class="m-st-l">${l}</span><strong>${t}</strong><span class="m-st-d">${d}</span><span class="m-st-go">열기</span></button>`).join('');
  }

  let graphCount = null;
  async function loadCounts() {
    try { const g = await getJ(API.agent + '/api/ontology/graph?asset=HYD-01'); graphCount = { n: g.nodes.length, e: g.edges.length }; } catch (e) { graphCount = null; }
  }

  function renderLive() {
    const live = document.getElementById('mLive'); if (!live) return;
    const u = state.plant && state.plant.units;
    if (!u) { live.textContent = '설비 연결 끊김 · 현재 운전 상태를 확인할 수 없습니다.';
      document.getElementById('mainStats').innerHTML = '<div class="m-unavailable" role="status">설비 연결 끊김 · 현재 운전 상태를 확인할 수 없습니다.</div>'; return; }
    const parts = Object.entries(u).map(([a, x]) => `${a} ${Number(x.tags.TS1).toFixed(1)} ℃ ${x.status.state === 'TRIP' ? 'TRIP' : x.status.mode === 'REMOTE_AUTO' ? '' : '(' + x.status.mode + ')'}`.trim());
    live.textContent = '실시간 유온 TS1  ·  ' + parts.join('   ');
    const hot = Object.values(u).some(x => x.tags.TS1 >= 55 || x.status.state === 'TRIP');
    document.getElementById('mOilBody')?.classList.toggle('hot', hot);
    const box = document.getElementById('mainStats'); if (!box) return;
    const open = (state.incidents || []).filter(i => !i.terminal).length;
    const alarms = Object.values(u).filter(x => x.tags.TS1 >= 55 || x.status.state === 'TRIP').length;
    box.innerHTML = [
      ['설비', `${Object.keys(u).length}기`, alarms ? `고온·트립 ${alarms}기` : '모든 설비 유온 55 ℃ 미만'],
      ['열린 인시던트', $('#openCount').textContent === '연결 끊김' ? '–' : String(open), $('#openCount').textContent === '연결 끊김' ? '프로세스 연결 끊김' : open ? '이상 확인 & 조치에서 확인' : '없음'],
      ['지식 지도', graphCount ? `${graphCount.n}` : '–', graphCount ? `노드 · 관계 ${graphCount.e}` : 'Neo4j 연결 대기'],
      ['시간 배율', `${state.plant.time_scale ?? '–'}×`, `실제 1초 = 시뮬레이션 ${state.plant.time_scale ?? '–'}초`],
    ].map(([k, v, s]) => `<div><span>${k}</span><b class="num">${esc(v)}</b><small>${esc(s)}</small></div>`).join('');
  }

  function init() {
    const box = document.getElementById('mainHero'); if (!box) return;
    box.innerHTML = heroSvg();
    const fitNodes = () => box.querySelectorAll('.m-node').forEach(g => {
      const r = g.querySelector('rect'), t = g.querySelector('text'), dot = g.querySelector('circle');
      const cx = Number(r.getAttribute('x')) + Number(r.getAttribute('width')) / 2;
      const measured = t.getComputedTextLength(); if (!measured) return;
      const w = Math.ceil(measured) + 40;
      r.setAttribute('x', cx - w / 2); r.setAttribute('width', w);
      dot.setAttribute('cx', cx - w / 2 + 12); t.setAttribute('x', cx - w / 2 + 23);
    });
    fitNodes(); document.fonts.ready.then(fitNodes);
    document.getElementById('mainStages').innerHTML = stagesHtml();
    document.querySelectorAll('.m-stage').forEach(b => b.addEventListener('click', () => selectTab(b.dataset.go)));
    document.getElementById('brandHome').addEventListener('click', () => { selectTab('main'); $('#content').focus({preventScroll:true}); });
    document.getElementById('mainArch').addEventListener('click', () => selectTab('home'));
    document.getElementById('mainOperate').addEventListener('click', () => selectTab('incidents'));
    document.getElementById('heroZoom').addEventListener('click', e => {
      const zoomed = box.classList.toggle('zoomed');
      e.currentTarget.setAttribute('aria-pressed', String(zoomed));
      e.currentTarget.textContent = zoomed ? '화면에 맞추기' : '도식 확대';
    });
    loadCounts().then(renderLive);
    setInterval(renderLive, 1000);
  }
  init();
})();
