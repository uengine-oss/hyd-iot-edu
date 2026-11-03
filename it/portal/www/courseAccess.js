/* 수업 경계 — 정본은 서버다(GET /api/course-access = it/process/procsvc/course_policy.py 의 Policy.view()). 화면은 그 표를 읽기만 한다.
   ① 상단 한 줄: 지금 단계(수업 / PBL, PBL 기한이 지났으면 그 사실).
   ② 막힌 행동: 행동 키를 단 요소(data-course-action="tool_servers.register" 등)만 끄고 서버가 준 까닭을 보인다. 메뉴는 잠그지 않는다.
      화면 모듈은 그릴 때 attrs(키)로 속성을 달고, 표가 늦게 오거나 바뀌면 apply()가 그 요소들만 다시 맞춘다(문서 전체 관찰자 없음).
   ③ 값마다 갈리는 판정: 배정할 수 있는 정의 · 시작할 수 있는 정의 · 가져올 수 있는 흐름 · 수업 모델 · 제공 문서만 받는지. 막힌 까닭은
      서버가 준 문장(표의 reasons — 거절 응답과 같은 문장)만 보인다. 화면에 규칙 문장 사본이 없다.
   ④ PBL 기한: 서버는 판정할 때마다 기한을 지금 시각과 견준다. 화면은 기한 시각에 표를 한 번 다시 읽는다.
   조회 실패는 잠금이 아니다 — 「수업 단계 정보를 읽지 못했습니다 · 다시 시도」를 띄우고 정해진 횟수만 다시 읽는다. 그동안 단추는 그대로 두고
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
  // 목록 판정의 까닭: 서버 문장(수업 단계에서만 있다)
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

  // 그릴 때 다는 속성: 행동 키 + (지금 막혔으면) 꺼짐 · 까닭
  function attrs(key) {
    const why = blocked(key);
    return ` data-course-action="${esc(key)}"` + (why ? ` disabled data-course-off="1" title="${esc(why)}"` : '');
  }
  // 이미 그려진 요소를 지금 표에 맞춘다. 수업 경계 때문에 끈 것만 다시 켠다(다른 까닭으로 꺼진 단추는 건드리지 않는다).
  // 꺼진 단추는 키보드 · 터치로 초점이 가지 않아 title 을 못 읽는다 — 까닭은 단추 바로 뒤 한 줄(data-course-why)로도 보인다(W3-07).
  // 화면 모듈은 attrs 로 그린 뒤 apply(그린 영역)를 부른다.
  function apply(root = document) {
    root.querySelectorAll('[data-course-action]').forEach(node => {
      const why = blocked(node.dataset.courseAction);
      const next = node.nextElementSibling;
      const line = next && next.hasAttribute('data-course-why') ? next : null;
      if (why) {
        node.disabled = true; node.dataset.courseOff = '1'; node.title = why;
        const hint = line || node.insertAdjacentElement('afterend', Object.assign(document.createElement('span'), { className: 'field-hint' }));
        hint.setAttribute('data-course-why', ''); hint.textContent = why;
      } else {
        if (node.dataset.courseOff) { node.disabled = false; delete node.dataset.courseOff; node.removeAttribute('title'); }
        if (line) line.remove();
      }
    });
  }

  function banner() {
    const box = document.getElementById('courseStatus');
    if (!box) return;
    const a = C.access;
    if (!a) {
      // 상단 줄은 좁다 — 보이는 글은 짧게, 서버 사유는 title 로
      box.innerHTML = C.error ? `${UI.chipText('수업 단계 정보 읽기 실패', 'danger')}<button type="button" class="btn small" data-course-retry>다시 시도</button>` : '';
      box.title = C.error ? `수업 단계 정보를 읽지 못했습니다: ${C.error}${C.timer ? ' — 잠시 뒤 다시 읽습니다' : ''}` : '';
      box.querySelector('[data-course-retry]')?.addEventListener('click', () => { C.tries = 0; refresh(); });
      return;
    }
    const until = a.expires ? UI.dateTime(a.expires) : '';
    const label = a.phase === 'pbl' ? `지금 단계: ${a.label}${until ? ` (${until}까지)` : ''}`
      : a.expired ? `지금 단계: ${a.label} (PBL 기한 지남)` : `지금 단계: ${a.label}`;
    const tone = a.phase === 'pbl' ? 'accent' : a.expired ? 'warning' : 'neutral';
    const closed = Object.values(a.actions || {}).filter(x => x && x.allowed === false).map(x => x.reason);
    box.innerHTML = UI.chipText(label, tone);
    box.title = [a.note, a.expired && until ? `PBL 기한(${until})이 지나 수업 단계로 돌아왔습니다.` : '', ...closed].filter(Boolean).join('\n');
  }

  // 서버 표가 이 화면이 읽는 모양인가 — 막힌 행동 · 목록 판정에는 서버 까닭 문장이 있어야 한다(없으면 화면이 문장을 지어내지 않고 실패로 본다)
  function wellFormed(a) {
    if (!a || !['course', 'pbl'].includes(a.phase) || typeof a.actions !== 'object' || !a.actions) return false;
    if (Object.values(a.actions).some(x => !x || (x.allowed === false && !x.reason))) return false;
    return a.phase === 'pbl' || ['assign', 'start', 'import_flow', 'document'].every(k => a.reasons && a.reasons[k]);
  }
  // PBL 기한 시각에 한 번 다시 읽는다(서버가 그때부터 수업 단계로 판정한다)
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
      if (!wellFormed(next)) throw new Error('수업 단계 응답 형식이 올바르지 않습니다 — 서비스가 이 화면과 다른 판일 수 있습니다.');
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
    // 수업 모델(두 단계 모두 하나 — 서버 값). 아직 모르면 null
    get model() { return C.access ? C.access.model : null; },
    // 질문 길이 한도(서버 값 — 질문 계약 한 곳). 아직 모르면 null
    get questionMaxChars() { return C.access ? C.access.question_max_chars : null; },
    // 수업 단계 교대 등록에서 바꿀 수 있는 칸 {flow_name, agent_tasks} — PBL 이면 null
    get handoverEditable() { return C.access ? C.access.handover_editable : null; },
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', refresh); else refresh();
})();
