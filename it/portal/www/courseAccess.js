/* Course controls follow the same server boundary as the API and worker: course actions are open, controls the
   course does not use stay off with a reason before anyone fills them in. There is no unlock step. */
(() => {
  let access = null;
  const editSelector = '[data-new-agent],[data-new-skill],[data-edit-agent],[data-del-agent],[data-clone],'
    +'[data-edit-skill],[data-del-skill],[data-attach],[data-detach],[data-ag-reset]';
  const closedTabs = new Set(['ask','compare','eval','mcp','admin']);
  const off = (node, why) => { if (node) { node.disabled = true; node.title = why; } };

  function apply() {
    const caps = access?.capabilities || {};
    document.querySelectorAll('#agentsView button').forEach(button => {
      if (!button.matches(editSelector))return;
      const permitted = caps.agent_authoring === true && !button.matches('[data-ag-reset]');
      button.disabled = !permitted;
      button.title = permitted ? '' : '수업에서는 전체 초기화를 사용할 수 없습니다.';
    });
    document.querySelectorAll('.rail nav button[data-tab]').forEach(button => {
      if (!closedTabs.has(button.dataset.tab))return;
      button.disabled = !((button.dataset.tab === 'ask' && caps.free_questions === true) ||
        (button.dataset.tab === 'mcp' && caps.tool_inspection === true));
      button.title = button.disabled ? '수업에서는 사용하지 않는 메뉴입니다. 준비된 흐름과 에이전트 화면을 사용하세요.' : '';
    });
    if (!access)return;
    // 서버가 거절할 조작은 채우기 전에 막고 까닭을 보인다
    off(document.querySelector('#skillNew'), '조치 방법은 매뉴얼을 적재하면 생깁니다. [지식 관리]에서 제공 문서를 적재하세요.');
    ['#ddlFile', '#ddlPreview'].forEach(s => off(document.querySelector(s), '옛 DB 스키마 뜻 복원은 수업에서 쓰지 않습니다.'));
    const assignable = new Set(access.assignable_definitions || []);
    document.querySelectorAll('#agentsView select[data-map]').forEach(sel => {
      if (!assignable.has(sel.dataset.map.split('|')[0])) off(sel, '수업에서는 교대 인수인계 단계에만 내 에이전트를 배정합니다.');
    });
    if (caps.model_settings !== true) document.querySelectorAll('#agentsView input[data-f="model"]').forEach(input => {
      input.placeholder = '수업 기본 모델'; off(input, '수업 모델은 강사가 지정한 기본 모델을 사용합니다.');
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
