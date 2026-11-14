/* A5 (U7) 포털 셸 — 위 막대의 알림 종 · 화면 찾기(Ctrl K) · 해시 주소 · 새 화면 자리(mount). 메뉴 줄 · 위 막대의 위치 표시는 app.js 가 주 메뉴 표(index.html)로 그린다.
   맨 마지막에 읽힌다 — 탭 진입 표(app.js hydTabs.onShow)의 마지막 일로 새 화면 자리 · 주소를 맞춘다.
   주소(해시)를 읽고 쓰는 곳은 이 파일 하나다 — 처리 건 화면은 hydInstances.openTask · route 로만 잇는다.
   새 화면을 그리는 길도 여기 하나다(MOUNTS → mount 한 번, 다시 열 때 show). 처음 읽기에 실패한 화면은 failed() 가 참이면 다시 연 때 새로 그린다.
   참고: process-gpt-vue3 src/router/MainRoutes.ts(경로 → 화면, /todolist/:taskId · /instancelist/:instId),
         src/layouts/full/vertical-header/VerticalHeader.vue:146·224(알림 배지를 'update-notification-badge' 이벤트로 갱신),
         src/layouts/full/vertical-sidebar/VerticalSidebar.vue:115-117(머리글 묶음 + 항목).
   화면 규칙: workspace/개발/문서/UIUX_PLAN.md

   주소: #/<화면>                         예) #/decision · #/skills (화면 이름은 index.html 의 view-<이름>. 그 화면이 든 메뉴와 탭이 고른 상태가 된다)
         #/instances/<처리 건 id>
         #/instances/<처리 건 id>/task/<task id>
         #/inbox                           옛 「내 작업함」 주소 — 처리 건 화면으로 보낸다(작업함은 처리 건 화면의 「내가 할 일」 · 「알림」으로 합쳤다)
   '#/'로 시작하지 않는 해시(#content 같은 본문 건너뛰기)는 주소로 보지 않는다. */
(function () {
  // 새 화면: 메뉴 키 → 전역 이름. 컨테이너는 <section id="view-<키>"> 안의 <div id="<키>View">.
  const MOUNTS = { agents: 'hydAgents', mcp: 'hydMcp', compare: 'hydCompare', eval: 'hydEval', whatif: 'hydWhatif', kpi: 'hydKpi',
    fabric: 'hydFabric', ask: 'hydAsk', flows: 'hydFlows', oil: 'hydOilInput' };
  const mounted = {};
  let applying = false;
  // 옮긴 화면의 옛 주소 → 지금 화면. 알림 · 즐겨찾기에 남은 옛 링크가 「없는 화면」으로 떨어지지 않게 한다
  const MOVED = { inbox: 'instances' };

  /* ------------------------------------------------ 주소 ↔ 화면 */
  function parse(hash) {
    const raw = String(hash || '');
    if (raw && !raw.startsWith('#/')) return null;                       // 일반 앵커 — 주소 아님
    const parts = raw.replace(/^#\/?/, '').split('/').filter(Boolean).map(p => { try { return decodeURIComponent(p); } catch (e) { return p; } });
    const route = { tab: MOVED[parts[0]] || parts[0] || 'main' };
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
  // 처리 건 화면이 지금 보여 주는 것(instances.js 의 route: 고른 처리 건 · 열어 둔 단계)
  function instanceRoute() {
    const H = window.hydInstances;
    return H ? H.route() : {};
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
    window.hydInstances.openTask(inst, task || null);   // 고를 처리 건 · 단계를 먼저 맞춘 뒤 화면을 연다(selectTab 이 다시 읽는다)
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
      // 화면 모듈이 실리지 않았다(스크립트 오류) — 「준비 중」이 아니라 실패로 보인다(W2-20)
      console.error(`화면 모듈 ${key} 이(가) 없습니다 — index.html 의 스크립트 오류를 개발자 도구 콘솔에서 확인`);
      if (!mounted[name]) box.innerHTML = UI.errorBlock('이 화면을 불러오지 못했습니다', '화면 프로그램이 실리지 않았습니다 — 화면을 새로 고쳐도 같으면 시스템 관리자에게 알리세요.', { retry: true });
      box.querySelector('[data-retry]')?.addEventListener('click', () => location.reload());
      return;
    }
    // 처음 읽기에 실패한 화면(사람 목록 · 입력 칸 · 패턴 등)은 다시 열 때 새로 그린다 — 한 번 실패하면 새로 고침 전까지 굳지 않게
    if (mounted[name] && typeof mod.failed === 'function' && mod.failed()) mounted[name] = false;
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

  /* ------------------------------------------------ 상단바 (머리줄의 「메뉴 › 화면」 위치 표시는 app.js updateNavigation 이 주 메뉴 표로 쓴다) */
  async function refreshBadge() {
    const badge = document.getElementById('shellBadge'), bell = document.getElementById('shellBell');
    if (!badge || !bell) return;
    try {
      const n = Math.max(0, Number(window.hydInbox.unread()) || 0);   // 안 읽은 알림 수
      badge.hidden = n === 0;                                         // 점만 찍는다 — 몇 건인지는 종의 이름표(aria-label · title)가 말한다
      const label = n ? UI.t('shell.bellCount', { n }) : UI.t('shell.bell');
      bell.setAttribute('aria-label', label); bell.title = label;
    } catch (e) {
      badge.hidden = true;
      bell.title = '알림 수를 읽지 못했습니다: ' + (e.message || e);
    }
  }

  /* ------------------------------------------------ 탭 진입(셸은 맨 마지막에 실려 표의 마지막 일이다) */
  hydTabs.onShow(name => {
    show(name);
    if (!applying) writeHash('push');
  });

  /* ------------------------------------------------ 화면 찾기(Ctrl K) — 키트의 명령 팔레트(dialog.command-dialog)
     화면 22개를 메뉴별로 묶어 보여 주고 이름으로 거른다(거르기 · 위아래 화살표 · Enter 는 키트가 한다). 목록은 메뉴 표(app.js hydMenu) 그대로라 메뉴 줄과 어긋나지 않는다.
     거르는 글: 「메뉴 이름 + 화면 이름」(data-filter)과 띄어쓰기를 뺀 이름 · 주소 이름(data-keywords — 「지식지도」 · 「skills」로도 찾는다).
     다른 코드가 열 때: hydShell.find() */
  function fillFinder() {
    const strip = s => s.replace(/[\s·]+/g, '');
    document.getElementById('kbarMenu').innerHTML = hydMenu.list.map(m => `<div role="group" aria-labelledby="kbarGroup-${esc(m.id)}"><span role="heading" id="kbarGroup-${esc(m.id)}">${esc(m.name)}</span>${
      m.tabs.map(t => `<div role="menuitem" id="kbarItem-${esc(t)}" data-tab="${esc(t)}" data-filter="${esc(m.name + ' ' + hydMenu.name(t))}" data-keywords="${esc([strip(hydMenu.name(t)), strip(m.name + hydMenu.name(t)), t].join(' '))}">${UI.icon(m.icon)}<span>${esc(hydMenu.name(t))}</span></div>`).join('')}</div>`).join('');
    const command = document.querySelector('#kbar .command');
    if (typeof command.refresh === 'function') command.refresh();      // 키트가 이미 이 팔레트를 준비했으면(문서가 다 읽힌 뒤) 새 목록을 다시 읽게 한다
  }
  function openFinder() {
    const dlg = document.getElementById('kbar'), input = document.getElementById('kbarInput');
    if (dlg.open) return;
    input.value = '';
    dlg.querySelectorAll('[role="menuitem"]').forEach(n => n.toggleAttribute('data-here', n.dataset.tab === state.tab));
    dlg.showModal();
    input.dispatchEvent(new Event('input'));      // 지난번에 거른 것을 풀고 첫 줄을 고른 상태로(키트가 input 이벤트에 목록을 다시 거른다)
    input.focus();
  }
  function startFinder() {
    const dlg = document.getElementById('kbar');
    fillFinder();
    document.getElementById('kbarOpen').addEventListener('click', openFinder);
    document.addEventListener('keydown', e => {
      if ((e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && e.key.toLowerCase() === 'k') { e.preventDefault(); if (dlg.open) dlg.close(); else openFinder(); }
    });
    // 고른 줄(눌렀거나 Enter): 그 화면으로 간다. 대화상자는 키트가 닫는다
    dlg.addEventListener('click', e => { const item = e.target.closest('[role="menuitem"][data-tab]'); if (item) window.hydShell.navigate({ tab: item.dataset.tab }); });
    // 바깥(어두운 바탕)을 누르면 닫는다 — 안에서 누르기 시작해 바깥에서 뗀 것은 닫지 않는다
    let pressedOutside = false;
    dlg.addEventListener('pointerdown', e => { pressedOutside = e.target === dlg; });
    dlg.addEventListener('click', e => { if (e.target === dlg && pressedOutside) dlg.close(); });
  }

  function start() {
    startFinder();
    const bell = document.getElementById('shellBell');
    // 종 = 알림: 처리 건 화면으로 가서 「알림」 접기를 펼쳐 보인다(inbox.js openNotices)
    if (bell) bell.addEventListener('click', () => { selectTab('instances'); window.hydInbox.openNotices(); });
    refreshBadge();
    setInterval(refreshBadge, 5000);
    window.addEventListener('hyd:badge', refreshBadge);              // 알림 모듈(inbox.js)이 읽음 처리 뒤 바로 갱신하려면 이 이벤트를 쏜다
    const onHash = () => { const route = parse(location.hash); if (route && format(route) !== format(currentRoute())) apply(route); if (route && location.hash !== format(currentRoute())) writeHash('replace'); };
    window.addEventListener('hashchange', onHash);
    window.addEventListener('popstate', onHash);
    const first = parse(location.hash);
    if (first && location.hash) { apply(first); writeHash('replace'); }      // 옛 주소(#/inbox)로 들어왔으면 지금 주소로 바꿔 적는다
    else { show(state.tab); writeHash('replace'); }
    // 처리 건 화면 안에서 고른 처리 건 · task 를 주소에 반영(새로고침 · 링크 유지). 기록을 쌓지 않고 바꿔 쓴다.
    setInterval(() => { if (state.tab === 'instances') writeHash('replace'); }, 1000);
  }

  window.hydShell = {
    parse, format, href: format,
    // 링크로 이동: 같은 주소를 다시 눌러도(해시 변화 없음) 그 화면을 다시 연다
    navigate(target) { const h = typeof target === 'string' ? target : format(target); if (location.hash === h) apply(parse(h)); else location.hash = h; },
    route: currentRoute,
    find: openFinder,
    refreshBadge, show,
    mounted,
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
