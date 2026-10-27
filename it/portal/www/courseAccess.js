/* Course controls use the same server authority as the API and worker. */
(() => {
  let access = null;
  const root = document.createElement('details');
  root.id = 'courseAccessPanel';
  root.className = 'card';
  root.style.cssText = 'margin:12px;padding:10px;font-size:12px';
  root.innerHTML = `<summary id="courseAccessLabel">수업 기능 확인 중</summary>
    <p id="courseAccessHelp">기본 에이전트는 바로 실행할 수 있습니다.</p>
    <form id="courseUnlockForm"><label for="courseUnlockCode">강사 해제 코드</label>
    <input id="courseUnlockCode" type="password" autocomplete="off" spellcheck="false" maxlength="512" style="width:100%">
    <button type="submit" class="btn small" id="courseUnlockGo">교대 실습 열기</button></form>
    <p id="courseUnlockMessage" role="status"></p>`;
  document.querySelector('#navigation').append(root);

  const editSelector = '[data-new-agent],[data-new-skill],[data-edit-agent],[data-del-agent],[data-clone],'
    +'[data-edit-skill],[data-del-skill],[data-attach],[data-detach],[data-ag-reset]';
  const closedTabs = new Set(['ask','compare','eval','mcp','flows','admin']);

  function apply() {
    const opened = access?.unlocked === true;
    document.querySelectorAll('#agentsView button').forEach(button => {
      if (!button.matches(editSelector))return;
      button.disabled = !opened;
      button.title = opened ? '' : '마지막 날 강사 코드로 교대 실습을 열 수 있습니다.';
    });
    document.querySelectorAll('.rail nav button[data-tab]').forEach(button => {
      if (closedTabs.has(button.dataset.tab)) {
        button.disabled = true;
        button.title = '이 수업에서는 준비된 에이전트와 교대 실습만 사용합니다.';
      }
    });
    const extract = document.querySelector('#manualAgentExtract');
    if (extract && !opened) { extract.disabled = true; extract.title = '강사 해제 코드가 필요합니다.'; }
    document.querySelector('#courseAccessLabel').textContent = access ? `수업 기능 · ${access.label}` : '수업 기능 · 연결 확인 필요';
    document.querySelector('#courseAccessHelp').textContent = opened
      ? '교대 실습의 에이전트·스킬 편집과 제공 문서 처리가 열렸습니다.'
      : '기본 에이전트는 실행됩니다. 추가 기능은 마지막 날 강사 코드로 엽니다.';
    document.querySelector('#courseUnlockForm').hidden = opened;
  }

  async function refresh() {
    try { access = await getJ(API.process + '/api/course-access'); }
    catch (_) { access = null; }
    apply();
  }

  document.querySelector('#courseUnlockForm').addEventListener('submit', async event => {
    event.preventDefault();
    const input = document.querySelector('#courseUnlockCode');
    const button = document.querySelector('#courseUnlockGo');
    const message = document.querySelector('#courseUnlockMessage');
    if (!input.value.trim()) { message.textContent = '강사 해제 코드를 입력하세요.'; return; }
    button.disabled = true;
    try {
      access = await postJ(API.process + '/api/course-access/unlock', {code: input.value.trim()});
      input.value = '';
      message.textContent = '교대 실습이 열렸습니다. 재시작해도 유지됩니다.';
      apply();
    } catch (error) { input.value = ''; message.textContent = error.message; }
    finally { button.disabled = false; }
  });
  new MutationObserver(apply).observe(document.querySelector('main'), {childList:true,subtree:true});
  window.hydCourseAccess = {refresh};
  refresh();
})();
