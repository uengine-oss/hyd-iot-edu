// 견본의 틀: 메뉴 줄 · 위 막대 · 명령 팔레트를 한 곳에서 그린다(견본 다섯 장이 함께 쓴다).
// 포털에 옮길 때는 이 표(MENU)와 마크업이 index.html · app.js 의 메뉴 정의 자리로 간다 — 디자인기준.md 「틀」 절.
const ICONS = '../vendor/lucide/icons.svg';
const icon = (name, cls = '') => `<svg class="ic ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><use href="${ICONS}#${name}"/></svg>`;
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

// 메뉴 여덟과 그 안의 화면. href 가 있는 것은 견본이 있는 화면이다.
const MENU = [
  { id: 'main', name: '홈', icon: 'house', views: [{ id: 'main', name: '홈' }] },
  { id: 'instances', name: '처리 건', icon: 'inbox', count: 1, views: [{ id: 'instances', name: '처리 건', href: 'case.html' }] },
  { id: 'knowledge', name: '지식', icon: 'book-open', views: [
    { id: 'ontology', name: '지식 지도', href: 'graph.html' }, { id: 'skills', name: '조치 방법' }, { id: 'knowledge', name: '문서 등록' }, { id: 'fabric', name: '데이터 원천' }] },
  { id: 'flows', name: '흐름', icon: 'workflow', views: [{ id: 'flows', name: '흐름' }] },
  { id: 'agents', name: 'AI 에이전트', icon: 'bot', views: [
    { id: 'agents', name: '에이전트 · 스킬', href: 'agents.html' }, { id: 'mcp', name: '도구 연결' }, { id: 'ask', name: '질문하기' }] },
  { id: 'plant', name: '유압 설비', icon: 'factory', views: [
    { id: 'scenario', name: '결함 시뮬레이션' }, { id: 'oil', name: '오일 분석 입력' }, { id: 'trends', name: '실시간 모니터링', href: 'plant.html' }, { id: 'circuit', name: '설비 회로' }, { id: 'process', name: '업무 시스템 기록' }] },
  { id: 'trial', name: '판단 실험', icon: 'flask-conical', views: [
    { id: 'decision', name: '규칙 판단' }, { id: 'whatif', name: '조건별 손익' }, { id: 'eval', name: '판단 채점' }, { id: 'compare', name: '에이전트 시험 비교' }] },
  { id: 'system', name: '시스템', icon: 'settings', views: [
    { id: 'home', name: '시스템 구성', href: 'system.html' }, { id: 'kpi', name: '성과 지표' }, { id: 'admin', name: '관리' }] },
];

function sidebar(menuId, viewId) {
  const item = (m) => {
    const active = m.id === menuId;
    if (m.views.length === 1) {
      const v = m.views[0];
      return `<li><a href="${v.href || '#'}" ${active ? 'aria-current="page"' : ''} data-tooltip="${esc(m.name)}" data-side="right">${icon(m.icon)}<span>${esc(m.name)}</span>${m.count ? `<span class="nav-count num" aria-label="내가 할 일 ${m.count}건">${m.count}</span>` : ''}</a></li>`;
    }
    return `<li><details ${active ? 'open' : ''} data-menu="${m.id}"><summary ${active ? 'data-active="true"' : ''} data-tooltip="${esc(m.name)}" data-side="right">${icon(m.icon)}<span>${esc(m.name)}</span></summary>
      <ul>${m.views.map((v) => `<li><a href="${v.href || '#'}" ${v.id === viewId ? 'aria-current="page"' : ''}><span>${esc(v.name)}</span></a></li>`).join('')}</ul></details></li>`;
  };
  return `<aside id="sidebar" class="sidebar" data-side="left" aria-label="메뉴">
  <nav aria-label="주 메뉴">
    <header><a class="brand" href="#" aria-label="홈으로"><span class="brand-mark">${icon('droplets')}</span><span class="brand-text"><span class="brand-name">HYD</span><br><span class="brand-sub">설비 · 프로세스 · AI</span></span></a></header>
    <section class="scrollbar-sm"><div role="group" aria-label="메뉴"><ul>${MENU.map(item).join('')}</ul></div></section>
    <footer><a class="rail-status" href="system.html" id="railStatus" data-tooltip="서비스 상태" data-side="right"><i class="dot" data-tone="ok" data-live></i><span>서비스 <b class="num" id="svcOk">–</b><span class="sep"> · </span><span class="num" id="svcScale">–</span>배속</span></a></footer>
  </nav>
</aside>`;
}

function topbar(menuId, viewId) {
  const m = MENU.find((x) => x.id === menuId); const v = m.views.find((x) => x.id === viewId) || m.views[0];
  const crumb = m.views.length > 1 ? `<span>${esc(m.name)}</span>${icon('chevron-right')}<b>${esc(v.name)}</b>` : `<b>${esc(m.name)}</b>`;
  return `<header class="topbar">
    <button type="button" class="btn" data-variant="ghost" data-size="icon-sm" id="railToggle" aria-label="메뉴 줄 접기 · 펴기">${icon('panel-left')}</button>
    <nav class="crumb" aria-label="위치">${crumb}</nav>
    <span class="topbar-space"></span>
    <span class="live-pill" id="livePill" role="status"><i class="dot" data-tone="ok" data-live></i><span>실시간 연결됨</span></span>
    <button type="button" class="kbar-btn" id="kbarOpen" aria-label="화면 찾기">${icon('search')}<span>화면 찾기</span><kbd>Ctrl K</kbd></button>
    <button type="button" class="btn bell" data-variant="ghost" data-size="icon-sm" aria-label="알림 1건">${icon('bell')}<i></i></button>
  </header>`;
}

function palette() {
  const groups = MENU.map((m) => `<div role="group" aria-labelledby="kg-${m.id}"><span role="heading" id="kg-${m.id}">${esc(m.name)}</span>${
    m.views.map((v) => `<div role="menuitem" data-filter="${esc(m.name + ' ' + v.name)}" data-href="${v.href || '#'}">${icon(m.icon)}<span>${esc(v.name)}</span></div>`).join('')}</div>`).join('');
  return `<dialog id="kbar" class="command-dialog" aria-label="화면 찾기" onpointerdown="this.dataset.backdropPress = event.target === this" onclick="if (event.target === this && this.dataset.backdropPress === 'true') this.close()">
    <div class="command"><header>${icon('search')}<input type="text" id="kbarInput" placeholder="화면 이름으로 찾기" autocomplete="off" spellcheck="false" aria-autocomplete="list" role="combobox" aria-expanded="true" aria-controls="kbarMenu"></header>
      <div role="menu" id="kbarMenu" aria-orientation="vertical" data-empty="맞는 화면이 없습니다.">${groups}</div></div></dialog>`;
}

async function pollStatus() {
  // 실제 서비스의 /healthz 를 읽는다(포털과 같은 출처의 /svc/…). 읽지 못한 서비스는 세지 않는다.
  const names = ['process', 'agent', 'agent-worker', 'enterprise-sim', 'plant-sim', 'detector', 'cmd-gateway', 'connect-ingest', 'connect-sink'];
  const res = await Promise.all(names.map((n) => fetch(`/svc/${n}/healthz`, { cache: 'no-store' }).then((r) => r.ok).catch(() => false)));
  const ok = res.filter(Boolean).length;
  const el = document.getElementById('svcOk'); if (el) el.textContent = `${ok}/${names.length}`;
  const dot = document.querySelector('#railStatus .dot'); if (dot) dot.dataset.tone = ok === names.length ? 'ok' : ok ? 'warn' : 'danger';
  try { const s = await fetch('/svc/plant-sim/api/state', { cache: 'no-store' }).then((r) => r.json()); document.getElementById('svcScale').textContent = Math.round(s.time_scale); } catch { /* 설비 서비스가 꺼져 있으면 배속 자리는 – 로 둔다 */ }
}

export function mountShell() {
  const { menu, view } = document.body.dataset;
  const main = document.querySelector('main');
  main.classList.add('app-main');
  main.insertAdjacentHTML('beforebegin', sidebar(menu, view));
  main.insertAdjacentHTML('afterbegin', topbar(menu, view));
  document.body.insertAdjacentHTML('beforeend', palette() + '<div id="toaster" class="toaster" data-align="end"></div>');
  try { if (localStorage.getItem('rail') === 'mini') document.documentElement.dataset.rail = 'mini'; } catch { /* 저장소를 못 쓰면 펼친 채로 */ }
  document.getElementById('railToggle').addEventListener('click', () => {
    if (matchMedia('(min-width: 768px)').matches) {
      const mini = document.documentElement.dataset.rail === 'mini';
      if (mini) delete document.documentElement.dataset.rail; else document.documentElement.dataset.rail = 'mini';
      try { localStorage.setItem('rail', mini ? 'full' : 'mini'); } catch { /* 위와 같다 */ }
    } else document.getElementById('sidebar').toggle?.();
  });
  // 메뉴는 고른 것 하나만 펼친다
  document.querySelectorAll('#sidebar details').forEach((d) => d.addEventListener('toggle', () => { if (d.open) document.querySelectorAll('#sidebar details[open]').forEach((o) => { if (o !== d) o.open = false; }); }));
  const kbar = document.getElementById('kbar');
  const openKbar = () => { kbar.showModal(); document.getElementById('kbarInput').focus(); };
  document.getElementById('kbarOpen').addEventListener('click', openKbar);
  document.addEventListener('keydown', (e) => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); kbar.open ? kbar.close() : openKbar(); } });
  kbar.addEventListener('click', (e) => { const it = e.target.closest('[role="menuitem"]'); if (it && it.dataset.href && it.dataset.href !== '#') location.href = it.dataset.href; });
  pollStatus(); setInterval(pollStatus, 5000);
}

export function toast(title, text = '', category = 'success') {
  document.dispatchEvent(new CustomEvent('basecoat:toast', { detail: { config: { category, title, description: text } } }));
}
export { icon, esc, MENU };
