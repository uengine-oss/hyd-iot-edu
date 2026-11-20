/* 수업 경계 — 정본은 서버다(GET /api/course-access = it/process/procsvc/course_policy.py 의 Policy.view()). 화면은 그 표를 읽기만 한다.
   ① 메뉴 줄 맨 아래 한 줄(#courseStatus): PBL 기간과 그 기한, PBL 기간이 끝났으면 그 사실만. PBL 선언이 없던 때에는 줄이 없다 —
      늘 같은 그 상태를 메뉴 아래에 띄우면 학생이 읽을 것이 없는 글만 남는다.
   ② 막힌 행동: 행동 키를 단 단추(data-course-action="tool_servers.register" 등)는 aria-disabled 로 둔다(키보드 · 터치로 닿는다). 까닭은 늘 붙이지 않고,
      학생이 그 단추를 누르거나 Enter · Space 를 칠 때만 동작을 막고(요청을 보내지 않는다) 단추 바로 뒤 한 줄(data-course-why)에 서버가 준 까닭을 보인다.
      메뉴는 잠그지 않는다. 화면 모듈은 그릴 때 attrs(키)로 속성을 달고, 표가 늦게 오거나 바뀌면 apply()가 그 요소들만 다시 맞춘다(문서 전체 관찰자 없음).
   ③ 값마다 갈리는 판정: 배정할 수 있는 정의 · 시작할 수 있는 정의 · 가져올 수 있는 흐름 · 모델 · 제공 문서만 받는지. 막힌 까닭은
      서버가 준 문장(표의 reasons — 거절 응답과 같은 문장)만 보인다. 화면에 규칙 문장 사본이 없다.
   ④ PBL 기한: 서버는 판정할 때마다 기한을 지금 시각과 견준다. 화면은 기한 시각에 표를 한 번 다시 읽는다.
   조회 실패는 잠금이 아니다 — 「단계 정보 읽기 실패 · 다시 시도」를 띄우고 정해진 횟수만 다시 읽는다. 그동안 단추는 그대로 두고
   서버가 판정한다(거절이면 서버의 학생용 까닭이 그대로 보인다). */
(() => {
  const RETRY_S = [3, 10, 30];            // 실패 뒤 자동으로 다시 읽는 간격(초). 다 쓰면 [다시 시도] 단추만 남는다
  const C = { access: null, error: '', tries: 0, timer: 0, expiry: 0, loading: false };
  const listeners = [];
  const MAX_TIMER_MS = 2 ** 31 - 1;       // setTimeout 이 받는 가장 긴 기다림(약 24.8일) — 더 먼 기한은 그때 다시 잰다

  // 행동 키 → 막혔으면 서버가 준 까닭, 열렸거나 아직 모르면 ''
  function blocked(key) {
    const a = C.access && C.access.actions ? C.access.actions[key] : null;
    if (!a) return '';
    return a.allowed === false ? a.reason : '';
  }
  // 목록 판정의 까닭: 서버 문장(PBL 기간이 아닐 때만 있다)
  const reason = key => (C.access && C.access.reasons && C.access.reasons[key]) || '';
  // 목록 판정: 서버 값이 null 이면 PBL(제한 없음), 목록이면 그 안의 것만
  const outside = (list, id) => Array.isArray(list) && !list.includes(id);
  function assignBlocked(definitionId) {
    return C.access && outside(C.access.assignable_definitions, definitionId) ? reason('assign') : '';
  }
  function startBlocked(definitionId) {
    return C.access && outside(C.access.startable_definitions, definitionId) ? reason('start') : '';
  }
  function importBlocked(flowId) {
    const only = C.access && C.access.importable_flow;
    return only && flowId !== only ? reason('import_flow') : '';
  }

  // 그릴 때 다는 속성: 행동 키 + (지금 막혔으면) aria-disabled · 막힘 표시. 까닭 문장은 속성에 싣지 않는다 — 누를 때 표에서 읽는다(press)
  function attrs(key) {
    return ` data-course-action="${esc(key)}"` + (blocked(key) ? ' aria-disabled="true" data-course-off="1"' : '');
  }
  // 이미 그려진 요소를 지금 표에 맞춘다. 수업 경계 때문에 막은 것만 다시 연다(다른 까닭으로 꺼진 단추는 건드리지 않는다).
  // 열린 단추 뒤에 남은 까닭 줄은 지운다. 화면 모듈은 attrs 로 그린 뒤 apply(그린 영역)를 부른다.
  const whyLine = node => { const next = node.nextElementSibling; return next && next.hasAttribute('data-course-why') ? next : null; };
  function apply(root = document) {
    root.querySelectorAll('[data-course-action]').forEach(node => {
      if (blocked(node.dataset.courseAction)) { node.setAttribute('aria-disabled', 'true'); node.dataset.courseOff = '1'; return; }
      if (node.dataset.courseOff) { node.removeAttribute('aria-disabled'); delete node.dataset.courseOff; }
      whyLine(node)?.remove();
    });
  }
  // 막힌 단추를 눌렀다(마우스 · 터치 · 키보드의 Enter · Space 모두 click 으로 온다): 그 단추의 동작을 막고 — 화면 모듈의 처리기보다 먼저(문서의 잡는 단계) —
  // 단추 바로 뒤에 서버 까닭 한 줄을 보인다(다시 눌러도 한 줄). role=status 라 화면 낭독기도 그때 읽는다(W3-07: 꺼진 단추는 초점이 가지 않아 까닭을 읽을 길이 없었다)
  function press(ev) {
    const node = ev.target.closest && ev.target.closest('[data-course-off]');
    if (!node) return;
    const why = blocked(node.dataset.courseAction);
    if (!why) { apply(node.parentElement || document); return; }      // 표가 그새 열렸다 — 이번 누름부터 그대로 지나간다
    ev.preventDefault(); ev.stopImmediatePropagation();
    const hint = whyLine(node) || node.insertAdjacentElement('afterend', Object.assign(document.createElement('span'), { className: 'muted' }));
    hint.setAttribute('data-course-why', ''); hint.setAttribute('role', 'status'); hint.textContent = why;
  }
  document.addEventListener('click', press, true);

  function banner() {
    const box = document.getElementById('courseStatus');
    if (!box) return;
    const a = C.access;
    if (!a) {
      // 메뉴 줄 아래는 좁다 — 보이는 글은 짧게, 서버 사유는 title 로. 색 면을 두지 않고 글자색으로만 말한다(portal-kit.css .course-status)
      box.innerHTML = C.error ? `<span data-tone="danger">단계 정보 읽기 실패</span> <button type="button" class="btn" data-variant="link" data-size="sm" data-course-retry>다시 시도</button>` : '';
      box.title = C.error ? `지금 단계를 읽지 못했습니다: ${C.error}${C.timer ? ' — 잠시 뒤 다시 읽습니다' : ''}` : '';
      box.querySelector('[data-course-retry]')?.addEventListener('click', () => { C.tries = 0; refresh(); });
      return;
    }
    box.removeAttribute('title');
    // PBL 선언이 없던 때는 그리지 않는다 — 막힌 행동의 까닭은 학생이 그 단추를 누를 때 그 자리에서 말한다(press)
    if (a.phase !== 'pbl' && !a.expired) { box.innerHTML = ''; return; }
    const until = a.expires ? UI.dateTime(a.expires) : '';
    // PBL 기간이면 그 기한을, 기한이 지났으면 끝났다는 사실만 말한다. 강사가 선언에 적은 한 줄(note)과 끝난 기한은 누르면(키보드 · 터치 포함) 펼쳐진다
    const label = a.phase === 'pbl' ? `PBL 기간${until ? ` · ${until}까지` : ''}` : 'PBL 기간이 끝났습니다';
    const tone = a.phase === 'pbl' ? 'run' : 'warn';
    const notes = [a.note, a.expired && until ? `PBL 기간은 ${until}까지였습니다.` : ''].filter(Boolean);
    const was = !!box.querySelector('details[open]');
    box.innerHTML = notes.length
      ? `<details${was ? ' open' : ''}><summary data-tone="${tone}">${UI.icon('chevron-right')}<span>${esc(label)}</span></summary><div class="course-why">${notes.map(n => `<p>${esc(n)}</p>`).join('')}</div></details>`
      : `<span data-tone="${tone}">${esc(label)}</span>`;
  }

  // 서버 표가 이 화면이 읽는 모양인가 — 막힌 행동 · 목록 판정에는 서버 까닭 문장이 있어야 한다(없으면 화면이 문장을 지어내지 않고 실패로 본다)
  function wellFormed(a) {
    if (!a || !['course', 'pbl'].includes(a.phase) || typeof a.actions !== 'object' || !a.actions) return false;
    if (Object.values(a.actions).some(x => !x || (x.allowed === false && !x.reason))) return false;
    return a.phase === 'pbl' || ['assign', 'start', 'import_flow', 'document'].every(k => a.reasons && a.reasons[k]);
  }
  // PBL 기한 시각에 한 번 다시 읽는다(서버가 그때부터 PBL 선언이 없던 때처럼 판정한다)
  function watchExpiry() {
    clearTimeout(C.expiry); C.expiry = 0;
    const a = C.access;
    if (!a || a.phase !== 'pbl' || !a.expires) return;
    const left = Date.parse(a.expires) - Date.now();
    if (Number.isFinite(left)) C.expiry = setTimeout(refresh, Math.min(Math.max(left, 0) + 1000, MAX_TIMER_MS));
  }

  async function refresh() {
    if (C.loading) return;
    C.loading = true; clearTimeout(C.timer); C.timer = 0;
    try {
      const next = await getJ(API.process + '/api/course-access');
      if (!wellFormed(next)) throw new Error('단계 정보 응답 형식이 올바르지 않습니다 — 서비스가 이 화면과 다른 판본일 수 있습니다.');
      C.access = next; C.error = ''; C.tries = 0;
    } catch (e) {
      C.access = null; C.error = e.message || String(e);
      if (C.tries < RETRY_S.length) C.timer = setTimeout(refresh, RETRY_S[C.tries++] * 1000);
    } finally { C.loading = false; }
    watchExpiry(); banner(); apply();
    listeners.forEach(fn => { try { fn(C.access); } catch (e) { console.error(e); } });
  }

  window.hydCourseAccess = {
    refresh, apply, attrs, blocked, assignBlocked, startBlocked, importBlocked, reason,
    onChange(fn) { listeners.push(fn); },
    get access() { return C.access; },
    get error() { return C.error; },
    // 이 포털에 연결된 모델(PBL 기간이든 아니든 하나 — 서버 값). 아직 모르면 null
    get model() { return C.access ? C.access.model : null; },
    // 질문 길이 한도(서버 값 — 질문 계약 한 곳). 아직 모르면 null
    get questionMaxChars() { return C.access ? C.access.question_max_chars : null; },
    // 교대 흐름 등록에서 바꿀 수 있는 칸 {flow_name, agent_tasks} — PBL 기간이면 null(모든 칸)
    get handoverEditable() { return C.access ? C.access.handover_editable : null; },
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', refresh); else refresh();
})();
