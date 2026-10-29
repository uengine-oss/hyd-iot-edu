/* Course controls follow the same server boundary as the API and worker: course actions are open, menus the
   course does not use stay off with a reason. There is no unlock step. */
(() => {
  let access = null;
  const editSelector = '[data-new-agent],[data-new-skill],[data-edit-agent],[data-del-agent],[data-clone],'
    +'[data-edit-skill],[data-del-skill],[data-attach],[data-detach],[data-ag-reset]';
  const closedTabs = new Set(['ask','compare','eval','mcp','admin']);

  function apply() {
    document.querySelectorAll('#agentsView button').forEach(button => {
      if (!button.matches(editSelector))return;
      const permitted = access?.capabilities?.agent_authoring === true && !button.matches('[data-ag-reset]');
      button.disabled = !permitted;
      button.title = permitted ? '' : '수업에서는 전체 초기화를 사용할 수 없습니다.';
    });
    document.querySelectorAll('.rail nav button[data-tab]').forEach(button => {
      if (closedTabs.has(button.dataset.tab)) {
        button.disabled = !((button.dataset.tab === 'ask' && access?.capabilities?.free_questions === true) ||
          (button.dataset.tab === 'mcp' && access?.capabilities?.tool_inspection === true));
        button.title = '수업에서는 사용하지 않는 메뉴입니다. 준비된 흐름과 에이전트 화면을 사용하세요.';
      }
    });
    const operator = document.querySelector('#mcpOperator');
    if (operator) operator.hidden = true;
  }

  async function refresh() {
    try { access = await getJ(API.process + '/api/course-access'); }
    catch (_) { access = null; }
    apply();
  }

  new MutationObserver(apply).observe(document.querySelector('main'), {childList:true,subtree:true});
  window.hydCourseAccess = {refresh};
  refresh();
})();
