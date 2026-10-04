/* Explicit definition/version selection; no startup process is seeded here. */
(function () {
  const $r = id => document.getElementById(id);
  let definitions = [], busy = false;
  const message = (text, error=false) => { $r('definitionMessage').textContent=text; $r('definitionMessage').className=error?'neg':'pos'; };
  async function action(fn) {
    if (busy) return;
    busy=true;
    const buttons=[...$r('definitionEditor').querySelectorAll('button')];buttons.forEach(b => b.disabled=true);
    try { await fn(); } catch(e) { message(e.message,true); }
    finally { busy=false;buttons.forEach(b => b.disabled=false); }
  }
  async function refresh(selected) {
    const current = selected || $r('definitionChoice').value;
    definitions = await getJ(API.process+'/api/process/definitions');
    const select=$r('definitionChoice');select.replaceChildren();
    definitions.forEach(d => {
      const option=document.createElement('option');option.value=JSON.stringify([d.id,d.version]);
      option.textContent=`${d.name || d.id} · ${d.id} @ ${d.version}${d.form_source==='legacy-live'?' (기존 폼)':''}`;
      select.appendChild(option);
    });
    if ([...select.options].some(o => o.value===current)) select.value=current;
  }
  function choice() {
    const value=$r('definitionChoice').value;
    if (!value) throw Error('등록된 정의 버전을 선택하세요');
    return JSON.parse(value);
  }
  function objectJson(text, label) {
    const value=JSON.parse(text);
    if (!value || Array.isArray(value) || typeof value!=='object') throw Error(label+'는 JSON 객체여야 합니다');
    return value;
  }
  $r('definitionEditor').addEventListener('toggle', () => {
    if ($r('definitionEditor').open && !definitions.length) action(() => refresh());
  });
  $r('definitionRefresh').addEventListener('click', () => action(() => refresh()));
  $r('definitionCopy').addEventListener('click', () => action(async () => {
    const [id,version]=choice();
    const d=await getJ(API.process+'/api/process/definitions/'+encodeURIComponent(id)+'?version='+encodeURIComponent(version));
    $r('definitionJson').value=JSON.stringify(d,null,2);
    message('정의를 불러왔습니다. 변경할 때는 새 version을 지정하세요.'+('forms' in d?'':' 기존 정의에는 forms가 없습니다. 등록할 새 버전에 폼 계약을 포함하세요.'));
  }));
  $r('definitionFile').addEventListener('change', () => action(async () => {
    const file=$r('definitionFile').files[0];if (!file) return;
    const d=objectJson(await file.text(),'정의');$r('definitionJson').value=JSON.stringify(d,null,2);
    message('파일을 읽었습니다. 등록 버튼을 누르면 서버가 구조와 폼 계약을 검사합니다.');
  }));
  $r('definitionPublish').addEventListener('click', () => action(async () => {
    const d=objectJson($r('definitionJson').value,'정의');
    await postJ(API.process+'/api/process/definitions',{definition:d});
    await refresh(JSON.stringify([d.processDefinitionId,d.version]));
    message(`${d.processDefinitionId} @ ${d.version} 등록 완료. 선택한 버전을 확인하고 실행하세요.`);
  }));
  $r('definitionStart').addEventListener('click', () => action(async () => {
    const [id,version]=choice(),event=$r('definitionEvent').value.trim();
    if (!event) throw Error('시작 이벤트 ID를 입력하세요');
    const alertText=$r('definitionAlert').value.trim();
    const data={definition_id:id,version,event_id:event,variables:objectJson($r('definitionValues').value,'시작 변수'),name:$r('definitionRunName').value.trim() || null};
    if (alertText) data.alert=objectJson(alertText,'경보');
    const inst=await postJ(API.process+'/api/instances/start',data);
    message('실행 시작: '+inst.proc_inst_id);
    window.hydInstancesSelect(inst.proc_inst_id);
  }));
})();
