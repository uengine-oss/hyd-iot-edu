/* 홈: 이 시스템의 이야기를 그림 한 장으로 — 유압 파워유닛(OT)의 값이 MQTT · DMZ · Kafka · 탐지를 지나 지식 지도와 AI 에이전트(IT)에 닿고,
   사람이 승인한 조치는 명령 관문(DMZ)을 거쳐 PLC 로 내려간다(PLC 가 받을지 정한다). 실시간 값은 app.js 가 읽은 state.plant 를 쓴다.
   그림 아래: 숫자 타일 한 줄(설비 · 열린 사건 · 내가 할 일 · 지식 항목 — 누르면 그 화면) · 처음이라면 이 순서로(네 걸음). 모양은 canvas.css(그림 .m-* 와 아래쪽 .hm-*). 디자인 기준 5-7. */
(function () {
  const G = { asset: '#9aa7b5', obs: '#9aa7b5', failure: '#f07167', action: '#f5a623', org: '#b794f6', sys: '#2dd4bf', decision: '#7aa2ff', agent: '#ffffff' };
  // 지식 지도의 항목(실제 온톨로지에서 읽기 좋게 고른 일부 — it/neo4j/v2/instances.cypher 구조판 + 매뉴얼 HM-8 의 절차)
  const N = [
    ['asset', 'HYD-01', 'asset', 700, 318], ['ts1', '센서 TS1', 'asset', 690, 226], ['ce', '센서 CE', 'asset', 706, 410],
    ['sym', '증상 · 유온 상승', 'obs', 800, 176], ['fm', '고장 유형 · 냉각 상실', 'failure', 822, 288], ['cause', '원인 · 쿨러 핀 오염', 'failure', 912, 200],
    ['act', '조치 · 팬 속도 상향', 'action', 990, 112], ['sop', '절차 SOP-COOL-11', 'action', 1105, 152],
    ['agent', '인공지능 에이전트', 'agent', 960, 326], ['scn', '판단 · 납기 vs 보전', 'decision', 1090, 262],
    ['kpi1', '성과 지표 · 납기 준수율', 'org', 1095, 356], ['kpi2', '성과 지표 · 부품 단가', 'org', 1012, 428], ['dept', '영업팀 · 구매팀', 'org', 1112, 472],
    ['pol', '규정 · 유온 65 ℃', 'org', 826, 450], ['erp', '구매 · 재고', 'sys', 770, 494], ['mes', '생산 관리', 'sys', 862, 516], ['cmms', '정비 관리', 'sys', 962, 516],
    ['skill', '조치 · 정비 요청', 'sys', 1066, 526],
  ];
  const E = [['asset', 'ts1'], ['asset', 'ce'], ['sym', 'ts1'], ['sym', 'fm'], ['cause', 'fm'], ['cause', 'act'], ['act', 'sop'],
    ['cause', 'scn'], ['scn', 'kpi1'], ['scn', 'kpi2'], ['kpi1', 'dept'], ['kpi2', 'dept'], ['pol', 'scn'], ['erp', 'agent'], ['mes', 'agent'],
    ['cmms', 'agent'], ['skill', 'cmms'], ['agent', 'cause'], ['agent', 'scn'], ['agent', 'fm'], ['agent', 'pol'], ['scn', 'skill']];

  function nodeSvg([id, label, g, x, y]) {
    if (id === 'agent') {
      const [first, ...rest] = String(label).split(/\s+/);
      // 원 안에 두 줄로 쓴다: 세 글자를 넘으면 원 폭에 맞춘다
      const fit = text => Array.from(text).length > 3 ? ' textLength="46" lengthAdjust="spacingAndGlyphs"' : '';
      const second = rest.join(' ');
      return `<g class="m-agent"><circle cx="${x}" cy="${y}" r="44" class="m-halo"/><circle cx="${x}" cy="${y}" r="30" fill="#1b2430" stroke="#fff" stroke-width="2"/>` +
        `<text x="${x}" y="${y - 6}" text-anchor="middle" class="m-agent-t"${fit(first)}>${esc(first)}</text><text x="${x}" y="${y + 15}" text-anchor="middle" class="m-agent-s"${fit(second)}>${esc(second)}</text></g>`;
    }
    const w = Math.max(64, label.length * 12 + 20);
    return `<g class="m-node"><rect x="${x - w / 2}" y="${y - 13}" width="${w}" height="26" rx="13" fill="#1b2430" stroke="${G[g]}" stroke-width="1.6"/>` +
      `<circle cx="${x - w / 2 + 12}" cy="${y}" r="4" fill="${G[g]}"/><text x="${x - w / 2 + 22}" y="${y + 4.5}" class="m-node-t">${label}</text></g>`;
  }

  // 가운데 줄: 값이 지나는 길. 칸마다 영역(OT · DMZ · IT)을 적는다 — 관제(운전 화면)와 MQTT 는 OT, 수집 중계는 DMZ, Kafka 와 탐지는 IT
  const BUS = [
    { y: 142, t: '관제', s: '운전 화면', zone: 'OT' },
    { y: 218, t: 'MQTT', s: '메시지 중계' },
    { y: 296, t: 'DMZ', s: '수집 중계', zone: 'DMZ' },
    { y: 374, t: 'Kafka', s: '이벤트 저장', zone: 'IT' },
    { y: 452, t: '탐지', s: '이상 판정' },
  ];
  const ZONE_FILL = { OT: '#f07167', DMZ: '#f5a623', IT: '#7aa2ff' };

  function heroSvg() {
    const pos = Object.fromEntries(N.map(n => [n[0], n]));
    const edges = E.map(([a, b]) => {
      const A = pos[a], B = pos[b];
      const agent = a === 'agent' || b === 'agent';
      return `<line x1="${A[3]}" y1="${A[4]}" x2="${B[3]}" y2="${B[4]}" class="m-edge${agent ? ' m-edge-agent' : ''}"/>`;
    }).join('');
    const bus = BUS.map(c => `${c.zone ? `<text x="548" y="${c.y - 16}" class="hm-zone-tag" fill="${ZONE_FILL[c.zone]}">${c.zone}</text>` : ''}` +
      `<text x="580" y="${c.y}" text-anchor="middle" class="m-bus-t">${c.t}</text><text x="580" y="${c.y + 18}" text-anchor="middle" class="m-bus-s">${c.s}</text>`).join('');
    return `<svg viewBox="0 0 1200 580" role="img" aria-labelledby="mainHeroTitle mainHeroDesc" class="m-hero-svg">
  <title id="mainHeroTitle">유압설비와 지식 지도 기반 에이전트 조치 흐름</title>
  <desc id="mainHeroDesc">왼쪽은 OT 영역의 유압 파워유닛과 센서와 PLC, 가운데는 값이 MQTT, DMZ의 수집 중계, Kafka, 탐지를 지나는 길, 오른쪽은 IT 영역의 지식 지도와 AI 에이전트다. 사람이 승인한 조치는 DMZ의 명령 관문을 거쳐 PLC로 내려가고, PLC가 받을지 정한다.</desc>
  <defs>
    <pattern id="mGrid" width="24" height="24" patternUnits="userSpaceOnUse"><circle cx="12" cy="12" r="1" fill="#27354a"/></pattern>
    <marker id="mArrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#f5a623"/></marker>
    <marker id="mArrowB" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L10 5L0 10z" fill="#7aa2ff"/></marker>
    <linearGradient id="mOil" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#f5a623" stop-opacity=".55"/><stop offset="1" stop-color="#b86e00" stop-opacity=".75"/></linearGradient>
    <radialGradient id="mHalo"><stop offset="0" stop-color="#b794f6" stop-opacity=".55"/><stop offset="1" stop-color="#b794f6" stop-opacity="0"/></radialGradient>
  </defs>
  <rect width="1200" height="580" fill="#16202d"/><rect width="1200" height="580" fill="url(#mGrid)"/>

  <!-- 영역 이름 -->
  <text x="40" y="48" class="m-zone" fill="#f07167">OT · 현장 설비</text>
  <text x="580" y="92" text-anchor="middle" class="m-zone" fill="#7aa2ff">값이 지나는 길</text>
  <text x="660" y="86" class="m-zone" fill="#7aa2ff">IT · 지식 지도 · AI 에이전트</text>
  <line x1="520" y1="60" x2="520" y2="556" class="m-sep"/><line x1="640" y1="60" x2="640" y2="556" class="m-sep"/>

  <!-- 유압 파워유닛 -->
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
    <!-- PLC: 승인된 명령을 받을지 정하고 밸브를 움직인다 -->
    <path d="M230 128 H404 V180" class="hm-ctl"/>
    <rect x="116" y="104" width="114" height="48" rx="8" class="hm-plc"/>
    <text x="173" y="124" text-anchor="middle" class="m-bus-t">PLC</text><text x="173" y="142" text-anchor="middle" class="m-bus-s">제어 · 보호 정지</text>
    <!-- 센서 -->
    <g class="m-sensor"><circle cx="118" cy="430" r="15"/><text x="118" y="434" text-anchor="middle">TS1</text></g>
    <g class="m-sensor"><circle cx="300" cy="238" r="13"/><text x="300" y="242" text-anchor="middle">PS1</text></g>
    <g class="m-sensor"><circle cx="496" cy="300" r="13"/><text x="496" y="304" text-anchor="middle">CE</text></g>
    <g class="m-sensor"><circle cx="306" cy="328" r="13"/><text x="306" y="332" text-anchor="middle">VS1</text></g>
    <text x="70" y="532" class="m-cap">유압 파워유닛 HYD-01 · 02 · 03  —  보호 정지 65 ℃</text>
    <text x="70" y="552" class="m-live" id="mLive">실시간 값 불러오는 중…</text>
  </g>

  <!-- 값이 지나는 길: 센서 → MQTT(관제가 지금 값을 받는다) → DMZ 수집 중계 → Kafka → 탐지 → 경보 -->
  <path d="M133 430 C 230 506, 500 440, 540 232" class="m-data"/>
  <path d="M313 238 C 380 236, 480 228, 540 220" class="m-data"/>
  <path d="M509 298 C 522 282, 530 252, 540 226" class="m-data"/>
  <g class="m-bus">
    <rect x="540" y="110" width="80" height="420" rx="10"/>
    <line x1="540" y1="262" x2="620" y2="262" class="m-sep"/><line x1="540" y1="340" x2="620" y2="340" class="m-sep"/>
    ${bus}
    <path d="M580 196 v-22" stroke="#7aa2ff" stroke-width="2" marker-end="url(#mArrowB)"/>
    <path d="M580 246 v24" stroke="#7aa2ff" stroke-width="2" marker-end="url(#mArrowB)"/>
    <path d="M580 324 v24" stroke="#7aa2ff" stroke-width="2" marker-end="url(#mArrowB)"/>
    <path d="M580 402 v24" stroke="#7aa2ff" stroke-width="2" marker-end="url(#mArrowB)"/>
  </g>
  <path d="M620 452 H654" class="m-data m-data-solid" marker-end="url(#mArrowB)"/>
  <text x="637" y="442" text-anchor="middle" class="m-bus-s">경보</text>

  <!-- 지식 지도 -->
  <circle cx="960" cy="326" r="120" fill="url(#mHalo)"/>
  ${edges}
  ${N.map(nodeSvg).join('')}

  <!-- 닫힌 고리: 사람이 승인한 조치 → 명령 관문(DMZ) → PLC. PLC 가 받을지 정한다 -->
  <path d="M1010 100 C 930 14, 700 6, 580 26 S 270 10, 180 98" class="m-loop" marker-end="url(#mArrow)"/>
  <rect x="744" y="6" width="150" height="26" rx="13" class="hm-tag"/>
  <text x="819" y="24" text-anchor="middle" class="m-loop-t">사람이 승인한 조치</text>
  <rect x="520" y="14" width="120" height="26" rx="13" class="hm-tag"/>
  <text x="580" y="32" text-anchor="middle" class="m-loop-t">명령 관문 · DMZ</text>
  <text x="246" y="96" class="m-bus-s">PLC가 받을지 정한다</text>
</svg>`;
  }

  // 처음이라면 이 순서로: 이 시스템의 이야기 순서 — 지식을 넣는다 → 사건이 생긴다 → AI가 판단하고 사람이 승인한다 → (자기 것) 흐름을 만든다.
  // 제목은 메뉴 표의 이름 그대로다(메뉴 › 화면 — app.js hydMenu) — 눌러서 열리는 화면의 제목과 같다
  function stagesHtml() {
    const st = [['knowledge', '설비 매뉴얼을 올려 AI 에이전트가 판단에 쓸 지식을 만듭니다.'], ['scenario', '설비에 결함을 넣어 경보를 냅니다. 경보가 나면 처리 건이 열립니다.'],
      ['instances', 'AI 에이전트의 판단을 읽고 승인하거나 반려한 뒤 실행 결과를 확인합니다.'], ['flows', '직접 그린 흐름을 가져와 등록하고 배포해 처리 건으로 돌립니다.']];
    return st.map(([tab, text], i) => {
      const menu = hydMenu.of(tab), title = menu.tabs.length > 1 ? `${menu.name} › ${hydMenu.name(tab)}` : hydMenu.name(tab);
      return `<button type="button" class="row" data-go="${tab}"><span class="row-ic num">${i + 1}</span><span class="row-title">${esc(title)}</span><span class="row-meta">${esc(text)}</span>${UI.icon('chevron-right')}</button>`;
    }).join('');
  }

  // 지식 수: 처음 한 번 읽고, 실패하면 사유를 두고 30초 뒤 다시 읽는다(시작 직후 Neo4j 가 늦게 떠도 새로 고침 없이 채워진다)
  let graphCount = null, graphError = '';
  async function loadCounts() {
    try { const g = await getJ(API.agent + '/api/ontology/graph?asset=HYD-01'); graphCount = { n: g.nodes.length, e: g.edges.length }; graphError = ''; }
    catch (e) { graphCount = null; graphError = e.message; setTimeout(() => loadCounts().then(renderLive), 30000); }
  }

  function renderLive() {
    const live = document.getElementById('mLive'); if (!live) return;
    const box = document.getElementById('mainStats');
    const u = state.plant && state.plant.units;
    if (!u) { live.textContent = UI.t('main.noConn'); box.innerHTML = UI.errorBlock(UI.t('main.noConn'), `${state.plantError || ''} ${UI.t('plant.noConnSub')}`.trim()); box.dataset.sig = ''; return; }
    const parts = Object.entries(u).map(([a, x]) => `${a} ${Number(x.tags.TS1).toFixed(1)} ℃ ${x.status.state === 'TRIP' ? UI.status('TRIP') : x.status.mode === 'REMOTE_AUTO' ? '' : '(' + UI.status(x.status.mode) + ')'}`.trim());
    live.textContent = UI.t('main.liveTs1') + '  ·  ' + parts.join('   ');
    const hot = Object.values(u).some(x => x.tags.TS1 >= TS_HOT || x.status.state === 'TRIP');      // 기준은 app.js TS_HOT 한 곳
    document.getElementById('mOilBody')?.classList.toggle('hot', hot);
    const open = (state.incidents || []).filter(i => !i.terminal).length;
    const alarms = Object.values(u).filter(x => x.tags.TS1 >= TS_HOT || x.status.state === 'TRIP').length;
    const n = v => Number(v).toLocaleString('ko-KR');
    // 숫자 타일 넷: [이름, 값, 한 줄, 주의인가, 까닭(title), 누르면 갈 화면]. 배율은 여기 두지 않는다(결함 시뮬레이션 화면 머리에 있다)
    const rows = [
      [UI.t('main.assets'), `${Object.keys(u).length}기`, alarms ? `${UI.t('main.hot')} ${alarms}기` : UI.t('main.cool'), !!alarms, '', 'trends'],
      // 사건 목록을 못 읽었으면 「0 · 없음」이 아니다(app.js 의 사건 목록 사유)
      state.incidentError ? [UI.t('main.openCases'), '읽기 실패', '처리 건 목록을 읽지 못했습니다', true, state.incidentError, 'instances']
        : [UI.t('main.openCases'), state.incidentsRead ? String(open) : '–', open ? '경과와 결과를 봅니다' : UI.t('main.none'), false, '', 'instances'],
      state.todo == null ? ['내가 할 일', state.todoError ? '읽기 실패' : '–', state.todoError ? '할 일 수를 읽지 못했습니다' : UI.t('loading'), !!state.todoError, state.todoError || '', 'instances']
        : ['내가 할 일', String(state.todo), state.todo ? '승인하거나 답할 처리 건이 있습니다' : UI.t('main.none'), false, '', 'instances'],
      [UI.t('main.knowledge'), graphCount ? n(graphCount.n) : '–', graphCount ? `${UI.t('main.links')} ${n(graphCount.e)}` : graphError ? '지식 수를 읽지 못했습니다. 30초 뒤 다시 읽습니다.' : UI.t('loading'), !!graphError, graphError, 'ontology'],      // 서버 사유는 길어 줄 높이를 흔든다 — title 로
    ];
    const sig = JSON.stringify(rows);
    if (box.dataset.sig === sig) return;      // 1초마다 불리지만 값이 같으면 다시 그리지 않는다
    box.dataset.sig = sig;
    box.innerHTML = rows.map(([k, v, s, warn, why, tab]) => `<button type="button" class="stat" data-go-tab="${tab}"${warn ? ' data-tone="warn"' : ''}${why ? ` title="${esc(why)}"` : ''}>` +
      `<span class="stat-label">${esc(k)}</span><span class="stat-value num">${esc(v)}</span><span class="stat-sub">${esc(s)}</span></button>`).join('');
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
    // 다른 화면 주소로 들어왔으면 홈이 가려진 채라 글자 폭을 잴 수 없다 — 홈이 보일 때 다시 맞춘다
    window.hydTabs.onShow(name => { if (name === 'main') fitNodes(); });
    const stages = document.getElementById('mainStages');
    stages.innerHTML = stagesHtml();
    stages.querySelectorAll('[data-go]').forEach(b => b.addEventListener('click', () => { selectTab(b.dataset.go); $('#content').focus({ preventScroll: true }); }));
    document.getElementById('brandHome').addEventListener('click', () => { selectTab('main'); $('#content').focus({ preventScroll: true }); });
    document.getElementById('mainArch').addEventListener('click', () => { selectTab('home'); $('#content').focus({ preventScroll: true }); });
    loadCounts().then(renderLive);
    setInterval(renderLive, 1000);
  }
  init();
})();
