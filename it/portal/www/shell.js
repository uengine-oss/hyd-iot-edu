/* A5 (U7) 포털 셸 — 수강생 동선 메뉴 · 상단바("나" · 알림 배지) · 해시 주소 · 새 화면 자리(mount).
   맨 마지막에 읽힌다(app.js · enterprise.js · hitl.js · instances.js 가 감싼 selectTab 을 한 번 더 감싼다). 기존 화면 로직은 건드리지 않는다.
   참고: process-gpt-vue3 src/router/MainRoutes.ts(경로 → 화면, /todolist/:taskId · /instancelist/:instId),
         src/layouts/full/vertical-header/VerticalHeader.vue:146·224(알림 배지를 'update-notification-badge' 이벤트로 갱신),
         src/layouts/full/vertical-sidebar/VerticalSidebar.vue:115-117(머리글 묶음 + 항목).
   계약 문서: docs/handoff/verification/2026-10-08/u7-shell.md

   주소: #/<화면>                         예) #/decision · #/inbox
         #/instances/<처리 건 id>
         #/instances/<처리 건 id>/task/<task id>
   '#/'로 시작하지 않는 해시(#content 같은 본문 건너뛰기)는 주소로 보지 않는다. */
(function () {
  // 새 화면: 메뉴 키 → 전역 이름. 컨테이너는 <section id="view-<키>"> 안의 <div id="<키>View">.
  const MOUNTS = { inbox: 'hydInbox', agents: 'hydAgents', mcp: 'hydMcp', compare: 'hydCompare', eval: 'hydEval', whatif: 'hydWhatif', kpi: 'hydKpi', fabric: 'hydFabric' };
  MOUNTS.flows = 'hydFlows';                                         // B3 흐름 가져오기 (flows.js)
  const mounted = {};
  let applying = false;

  /* ------------------------------------------------ 주소 ↔ 화면 */
  function parse(hash) {
    const raw = String(hash || '');
    if (raw && !raw.startsWith('#/')) return null;                       // 일반 앵커 — 주소 아님
    const parts = raw.replace(/^#\/?/, '').split('/').filter(Boolean).map(p => { try { return decodeURIComponent(p); } catch (e) { return p; } });
    const route = { tab: parts[0] || 'main' };
    if (route.tab === 'instances' && parts[1]) {
      route.inst = parts[1];
      if (parts[2] === 'task' && parts[3]) route.task = parts[3];
    }
    return route;
  }
  function format(route) {
    let h = '#/' + encodeURIComponent(route.tab || 'main');
    if (route.tab === 'instances' && route.inst) {
      h += '/' + encodeURIComponent(route.inst);
      if (route.task) h += '/task/' + encodeURIComponent(route.task);
    }
    return h;
  }
  // 처리 건 화면이 지금 보여 주는 것. A1 이 hydInstances.route() 를 주면 그것을, 아니면 I.sel · I.taskSel 을 읽는다.
  function instanceRoute() {
    const H = window.hydInstances;
    if (!H) return {};
    if (typeof H.route === 'function') { try { return H.route() || {}; } catch (e) { return {}; } }
    return H.I ? { inst: H.I.sel || null, task: H.I.taskSel || null } : {};
  }
  function currentRoute() {
    const tab = state.tab;
    return tab === 'instances' ? { tab, ...instanceRoute() } : { tab };
  }
  function writeHash(mode) {
    const h = format(currentRoute());
    if (h === location.hash) return;
    if (mode === 'push') history.pushState(null, '', h); else history.replaceState(null, '', h);
  }

  /* ------------------------------------------------ 처리 건 · task 열기 */
  function openInstance(inst, task) {
    const H = window.hydInstances;
    // A1 훅: openTask(inst, task) 가 있으면 task 상세(다섯 칸)까지 그쪽이 연다.
    if (H && typeof H.openTask === 'function') { selectTab('instances'); H.openTask(inst, task || null); return; }
    // 기본: 처리 건 선택 상태를 먼저 맞춘 뒤 화면을 연다(instances.js 의 selectTab 감싸기가 load(true) 를 부른다).
    if (H && H.I) { H.I.sel = inst; H.I.taskSel = task || null; }
    selectTab('instances');
  }
  function apply(route) {
    if (!route) return;
    if (!document.getElementById('view-' + route.tab)) {
      UI.toast(UI.t('shell.unknownRoute'), { tone: 'neg' });
      route = { tab: 'main' };
      history.replaceState(null, '', format(route));
    }
    applying = true;
    try {
      if (route.tab === 'instances' && route.inst) openInstance(route.inst, route.task);
      else selectTab(route.tab);
    } finally { applying = false; }
  }

  /* ------------------------------------------------ 새 화면 자리 */
  function mountFailed(name, box, error) {
    mounted[name] = false;
    box.innerHTML = UI.errorBlock(UI.t('shell.mountFail'), (error && error.message) || String(error || ''), { retry: true });
    box.querySelector('[data-retry]')?.addEventListener('click', () => show(name));
  }
  function show(name) {
    const key = MOUNTS[name];
    if (!key) return;
    const box = document.getElementById(name + 'View');
    if (!box) return;
    const mod = window[key];
    if (!mod || typeof mod.mount !== 'function') {
      if (!mounted[name]) box.innerHTML = UI.empty(UI.t('shell.notReady'), UI.t('shell.notReadySub'));
      return;
    }
    if (!mounted[name]) {
      mounted[name] = true;
      box.innerHTML = '';
      try {
        const out = mod.mount(box);
        if (out && typeof out.then === 'function') out.catch(e => mountFailed(name, box, e));
      } catch (e) { mountFailed(name, box, e); }
      return;
    }
    if (typeof mod.show === 'function') {
      try { const out = mod.show(box); if (out && typeof out.then === 'function') out.catch(e => UI.toast(e.message || String(e), { tone: 'neg' })); }
      catch (e) { UI.toast(e.message || String(e), { tone: 'neg' }); }
    }
  }

  /* ------------------------------------------------ 상단바 */
  function setGroup(name) {
    const button = document.querySelector(`.rail nav button[data-tab="${name}"]`);
    let group = button && button.previousElementSibling;
    while (group && !group.classList.contains('navgroup')) group = group.previousElementSibling;
    const box = document.getElementById('pageGroup');
    if (box) { box.textContent = group ? group.textContent : ''; box.hidden = !group; }
  }
  function renderMe() {
    const box = document.getElementById('shellMe');
    if (!box) return;
    const H = window.hydInbox;
    if (H && typeof H.mountMe === 'function') {
      try { box.innerHTML = ''; H.mountMe(box); return; }
      catch (e) { box.innerHTML = `${UI.icon('user')}<span>${esc(UI.t('shell.me'))} · ${esc(e.message || '')}</span>`; return; }
    }
    box.innerHTML = `${UI.icon('user')}<span class="shell-me-label">${esc(UI.t('shell.me'))} <b>${esc(UI.t('shell.meNone'))}</b></span>`;
    box.title = '내 작업함 기능이 붙으면 여기서 나를 고릅니다';
  }
  async function refreshBadge() {
    const badge = document.getElementById('shellBadge'), bell = document.getElementById('shellBell');
    if (!badge || !bell) return;
    const H = window.hydInbox;
    if (!H || typeof H.badge !== 'function') { badge.hidden = true; bell.setAttribute('aria-label', UI.t('shell.bell')); bell.title = UI.t('shell.bell'); return; }
    try {
      const n = Math.max(0, Number(await H.badge()) || 0);
      badge.hidden = n === 0;
      badge.textContent = n > 99 ? '99+' : String(n);
      const label = n ? UI.t('shell.bellCount', { n }) : UI.t('shell.bell');
      bell.setAttribute('aria-label', label); bell.title = label;
    } catch (e) {
      badge.hidden = true;
      bell.title = '알림 수를 읽지 못했습니다: ' + (e.message || e);
    }
  }

  /* ------------------------------------------------ selectTab 감싸기 */
  const previousSelect = selectTab;
  selectTab = function (name) {
    previousSelect(name);
    if (state.tab !== name) return;                                   // 없는 화면 — app.js 가 무시했다
    setGroup(name);
    show(name);
    if (!applying) writeHash('push');
  };
  window.hydApp.selectTab = selectTab;

  function start() {
    const bell = document.getElementById('shellBell');
    if (bell) {
      bell.insertAdjacentHTML('afterbegin', UI.icon('bell'));
      bell.addEventListener('click', () => { selectTab('inbox'); document.getElementById('content')?.focus({ preventScroll: true }); });
    }
    renderMe();
    refreshBadge();
    setInterval(refreshBadge, 5000);
    window.addEventListener('hyd:badge', refreshBadge);              // 작업함이 읽음 처리 뒤 바로 갱신하려면 이 이벤트를 쏜다
    const onHash = () => { const route = parse(location.hash); if (route && format(route) !== format(currentRoute())) apply(route); };
    window.addEventListener('hashchange', onHash);
    window.addEventListener('popstate', onHash);
    const first = parse(location.hash);
    if (first && location.hash) apply(first);
    else { setGroup(state.tab); show(state.tab); writeHash('replace'); }
    // 처리 건 화면 안에서 고른 처리 건 · task 를 주소에 반영(새로고침 · 링크 유지). 기록을 쌓지 않고 바꿔 쓴다.
    setInterval(() => { if (state.tab === 'instances') writeHash('replace'); }, 1000);
  }

  window.hydShell = {
    parse, format, href: format,
    navigate(target) { location.hash = typeof target === 'string' ? target : format(target); },
    route: currentRoute,
    refreshBadge, renderMe, show,
    mounted,
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
