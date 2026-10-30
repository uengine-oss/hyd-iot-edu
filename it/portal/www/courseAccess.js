/* 수업 경계 — 정본은 서버다(GET /api/course-access = it/process/procsvc/course_policy.py 의 Policy.view()). 화면은 그 표를 읽기만 한다.
   ① 상단 한 줄: 지금 단계(수업 / PBL, PBL 기한이 지났으면 그 사실).
   ② 막힌 행동: 행동 키를 단 요소(data-course-action="tool_servers.register" 등)만 끄고 서버가 준 까닭을 보인다. 메뉴는 잠그지 않는다.
      화면 모듈은 그릴 때 attrs(키)로 속성을 달고, 표가 늦게 오거나 바뀌면 apply()가 그 요소들만 다시 맞춘다(문서 전체 관찰자 없음).
   ③ 값마다 갈리는 판정: 배정할 수 있는 정의 · 시작할 수 있는 정의 · 가져올 수 있는 흐름 · 수업 모델 · 제공 문서만 받는지.
   조회 실패는 잠금이 아니다 — 「수업 범위를 읽지 못했습니다 · 다시 시도」를 띄우고 정해진 횟수만 다시 읽는다. 그동안 단추는 그대로 두고
   서버가 판정한다(거절이면 서버의 학생용 까닭이 그대로 보인다). */
(() => {
  const RETRY_S = [3, 10, 30];            // 실패 뒤 자동으로 다시 읽는 간격(초). 다 쓰면 [다시 시도] 단추만 남는다
  const C = { access: null, error: '', tries: 0, timer: 0, loading: false };
  const listeners = [];
  const PBL_LATER = 'PBL 단계에서 엽니다.';

  // 행동 키 → 막혔으면 서버가 준 까닭, 열렸거나 아직 모르면 ''
  function blocked(key) {
    const a = C.access && C.access.actions ? C.access.actions[key] : null;
    if (!a) return '';
    return a.allowed === false ? (a.reason || `수업 단계에서 열지 않은 기능입니다. ${PBL_LATER}`) : '';
  }
  // 목록 판정: 서버 값이 null 이면 PBL(제한 없음), 목록이면 그 안의 것만
  const outside = (list, id) => Array.isArray(list) && !list.includes(id);
  function assignBlocked(definitionId) {
    return C.access && outside(C.access.assignable_definitions, definitionId) ? `수업 단계에서는 이 단계에 내 에이전트를 배정하지 않습니다. ${PBL_LATER}` : '';
  }
  function startBlocked(definitionId) {
    return C.access && outside(C.access.startable_definitions, definitionId) ? `수업 단계에서는 준비된 흐름만 시작합니다. 이 흐름은 ${PBL_LATER}` : '';
  }
  function importBlocked(flowId) {
    const only = C.access && C.access.importable_flow;
    return only && flowId !== only ? `수업 단계에서 직접 가져오는 흐름은 제공한 흐름 하나입니다. 다른 흐름은 ${PBL_LATER}` : '';
  }

  // 그릴 때 다는 속성: 행동 키 + (지금 막혔으면) 꺼짐 · 까닭
  function attrs(key) {
    const why = blocked(key);
    return ` data-course-action="${esc(key)}"` + (why ? ` disabled data-course-off="1" title="${esc(why)}"` : '');
  }
  // 이미 그려진 요소를 지금 표에 맞춘다. 수업 경계 때문에 끈 것만 다시 켠다(다른 까닭으로 꺼진 단추는 건드리지 않는다)
  function apply(root = document) {
    root.querySelectorAll('[data-course-action]').forEach(node => {
      const why = blocked(node.dataset.courseAction);
      if (why) { node.disabled = true; node.dataset.courseOff = '1'; node.title = why; }
      else if (node.dataset.courseOff) { node.disabled = false; delete node.dataset.courseOff; node.removeAttribute('title'); }
    });
  }

  function banner() {
    const box = document.getElementById('courseStatus');
    if (!box) return;
    const a = C.access;
    if (!a) {
      // 상단 줄은 좁다 — 보이는 글은 짧게, 서버 사유는 title 로
      box.innerHTML = C.error ? `${UI.chipText('수업 범위 읽기 실패', 'danger')}<button type="button" class="btn small" data-course-retry>다시 시도</button>` : '';
      box.title = C.error ? `수업 범위를 읽지 못했습니다: ${C.error}${C.timer ? ' — 잠시 뒤 다시 읽습니다' : ''}` : '';
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

  async function refresh() {
    if (C.loading) return;
    C.loading = true; clearTimeout(C.timer); C.timer = 0;
    try {
      const next = await getJ(API.process + '/api/course-access');
      if (!next || !['course', 'pbl'].includes(next.phase) || typeof next.actions !== 'object') throw new Error('수업 범위 응답 형식이 올바르지 않습니다 — 서비스가 이 화면과 다른 판일 수 있습니다.');
      C.access = next; C.error = ''; C.tries = 0;
    } catch (e) {
      C.access = null; C.error = e.message || String(e);
      if (C.tries < RETRY_S.length) C.timer = setTimeout(refresh, RETRY_S[C.tries++] * 1000);
    } finally { C.loading = false; }
    banner(); apply();
    listeners.forEach(fn => { try { fn(C.access); } catch (e) { console.error(e); } });
  }

  window.hydCourseAccess = {
    refresh, apply, attrs, blocked, assignBlocked, startBlocked, importBlocked,
    onChange(fn) { listeners.push(fn); },
    get access() { return C.access; },
    get error() { return C.error; },
    // 수업 모델(두 단계 모두 하나 — 서버 값). 아직 모르면 null
    get model() { return C.access ? C.access.model : null; },
    // 수업 단계에서는 제공 문서만 받는다(서버 값 'provided'), PBL 이면 null
    get documentsProvidedOnly() { return !!(C.access && C.access.documents === 'provided'); },
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', refresh); else refresh();
})();
