/* 관리 › 흐름 정의 등록 · 판본 고르기 · 직접 실행(GET · POST /api/process/definitions, POST /api/instances/start). 시작할 때 정의를 심지 않는다.
   두 관리 패널(이 파일 · 뒤에 실리는 definitionDeploy.js)이 쓰는 것은 여기 한 벌(window.hydDefinitions): 패널 일(task) · 흐름 이름(name). */
(function () {
  const $r = id => document.getElementById(id);

  // 패널 일: 도는 동안 패널의 단추를 모두 끄고(두 번 눌림 막기), 끝나면 그 전 상태 그대로 되돌린다 — 원래 꺼져 있던 단추(운영 중 · 배포 불가 ·
  // 수업 경계)가 살아나지 않게. 실패는 패널 알림 줄에 그 문장 그대로. after(): 끝난 뒤 그 패널이 단추 상태를 다시 맞추는 함수(W3-28 — 두 벌이던 것)
  function task(panel, note, after) {
    let busy = false;
    const say = (text, error = false) => { note.textContent = text; note.className = 'form-msg ' + (error ? 'neg' : 'pos'); };
    async function run(fn) {
      if (busy) return;
      busy = true;
      const buttons = [...panel.querySelectorAll('button')].map(b => [b, b.disabled]);
      buttons.forEach(([b]) => { b.disabled = true; });
      try { await fn(); } catch (e) { say(e.message, true); }
      finally { busy = false; buttons.forEach(([b, was]) => { b.disabled = was; }); after(); }
    }
    return { run, say, get busy() { return busy; } };
  }
  // 흐름 이름: 정의의 이름(id 를 그대로 이름으로 쓴 것은 이름이 아니다), 없으면 화면 이름표 — 내부 id 를 보이지 않는다
  const name = (id, given) => (given && given !== id ? given : UI.defName(id));

  // 붙여 넣은 JSON 글 → 객체. 틀리면 어디(줄 · 글자)가 틀렸는지 한국어로 — 브라우저의 영문 SyntaxError 를 그대로 보이지 않는다(W3-17)
  function readObject(text, label) {
    const src = String(text ?? '');
    if (!src.trim()) throw Error(`${label} 칸이 비어 있습니다 — { } 로 묶은 JSON 객체를 적으세요`);
    let value;
    try { value = JSON.parse(src); }
    catch (e) { throw Error(`${label} JSON을 읽지 못했습니다${spot(src, e)} — 쉼표 · 따옴표 · 괄호가 짝이 맞는지 확인하세요`); }
    if (!value || Array.isArray(value) || typeof value !== 'object') throw Error(`${label}는 { } 로 묶은 JSON 객체여야 합니다`);
    return value;
  }
  // 틀린 자리: 브라우저마다 오류 문장이 달라(크롬 「… (line L column C)」 · 「position N」, 파이어폭스 「line L column C」) 수만 읽어 줄 · 글자로 쓴다.
  // 크롬이 자리 없이 「Unexpected token 'x'」만 주면 그 글자를, 글이 중간에 끝났으면 그 사실을, 그 밖의 꼴이면 자리 없이(문장은 그래도 실패로 보인다)
  function spot(src, e) {
    const msg = String(e && e.message || '');
    const lc = /line (\d+) column (\d+)/.exec(msg);
    if (lc) return ` (${lc[1]}번째 줄 ${lc[2]}번째 글자)`;
    const pos = /position (\d+)/.exec(msg);
    if (pos) { const lines = src.slice(0, Number(pos[1])).split('\n'); return ` (${lines.length}번째 줄 ${lines[lines.length - 1].length + 1}번째 글자)`; }
    const tok = /Unexpected token '(.+?)'/.exec(msg);
    if (tok) return ` (「${tok[1]}」 글자가 올 자리가 아닙니다)`;
    return /end of (JSON )?(input|data)/i.test(msg) ? ' (닫지 않은 괄호나 따옴표가 있습니다)' : '';
  }
  const optionLabel = d => `${name(d.id, d.name)} · 판본 ${d.version}`;

  window.hydDefinitions = { task, name, readObject, optionLabel };   // readObject · optionLabel 은 시험(test_www_definitionRegistry)도 부른다

  let definitions = [];
  const panel = task($r('definitionEditor'), $r('definitionMessage'), syncStart), action = panel.run, message = panel.say;
  // 수업 경계(서버 GET /api/course-access 의 startable_definitions): 수업 단계에서 시작할 수 없는 정의를 고르면 [실행]을 끄고 까닭을 보인다
  function syncStart() {
    const button=$r('definitionStart'), value=$r('definitionChoice').value;
    const why=value ? hydCourseAccess.startBlocked(JSON.parse(value)[0]) : '';
    if (!panel.busy) button.disabled=!!why;
    // 까닭은 마우스를 올려야 보이는 title 이 아니라 단추 옆 한 줄로(W3-07 — 꺼진 단추는 키보드 · 터치로 초점이 가지 않는다)
    let note=button.parentElement.querySelector('[data-start-why]');
    if (!note) { note=document.createElement('span'); note.className='field-hint'; note.dataset.startWhy=''; button.after(note); }
    note.textContent=why;
  }
  async function refresh(selected) {
    const current = selected || $r('definitionChoice').value;
    definitions = await getJ(API.process+'/api/process/definitions');
    const select=$r('definitionChoice');select.replaceChildren();
    // 빈 항목을 먼저 둔다 — 고르지 않은 첫 판본이 [실행] · [고친 판본 불러오기]로 나가지 않게(choice() 가 빈 값을 막는다)
    const blank=document.createElement('option');blank.value='';blank.textContent='정의 판본 선택';select.appendChild(blank);
    definitions.forEach(d => {
      const option=document.createElement('option');option.value=JSON.stringify([d.id,d.version]);
      option.textContent=optionLabel(d);
      select.appendChild(option);
    });
    if ([...select.options].some(o => o.value===current)) select.value=current;
    syncStart();
  }
  function choice() {
    const value=$r('definitionChoice').value;
    if (!value) throw Error('등록된 정의 판본을 고르세요');
    return JSON.parse(value);
  }
  // 시작 요청 번호: 학생이 지어 적지 않게 폼을 열 때 채워 둔다(flows.js 직접 시작과 같은 UI.uuid). 응답을 잃고 다시 눌러도 같은 번호라 두 번 시작되지 않고,
  // 시작에 성공한 뒤에만 새 번호로 바꾼다. 학생이 고쳐 적은 번호는 건드리지 않는다
  function newEvent(force) { const input=$r('definitionEvent'); if (force || !input.value.trim()) input.value='manual-'+UI.uuid(); }
  $r('definitionEditor').addEventListener('toggle', () => {
    if (!$r('definitionEditor').open) return;
    newEvent(false);
    if (!definitions.length) action(() => refresh());
  });
  $r('definitionRefresh').addEventListener('click', () => action(() => refresh()));
  $r('definitionChoice').addEventListener('change', syncStart);
  hydCourseAccess.onChange(syncStart);
  $r('definitionCopy').addEventListener('click', () => action(async () => {
    const [id,version]=choice();
    const d=await getJ(API.process+'/api/process/definitions/'+encodeURIComponent(id)+'?version='+encodeURIComponent(version));
    $r('definitionJson').value=JSON.stringify(d,null,2);
    message('고른 판본을 불러왔습니다. 고쳐서 등록하려면 "version" 칸을 새 판본 번호로 바꾸세요 — 같은 판본 번호는 다시 쓸 수 없습니다.');
  }));
  $r('definitionFile').addEventListener('change', () => action(async () => {
    const file=$r('definitionFile').files[0];if (!file) return;
    const d=readObject(await file.text(),'정의 파일');$r('definitionJson').value=JSON.stringify(d,null,2);
    message('파일을 읽었습니다. [등록]을 누르면 서버가 흐름 구조와 입력 양식을 검사합니다.');
  }));
  $r('definitionPublish').addEventListener('click', () => action(async () => {
    const d=readObject($r('definitionJson').value,'정의');
    await postJ(API.process+'/api/process/definitions',{definition:d});
    const key=JSON.stringify([d.processDefinitionId,d.version]);
    await refresh(key);
    if ($r('definitionChoice').value!==key) throw Error('등록은 됐지만 목록에 그 판본이 보이지 않습니다 — [목록 새로 읽기]를 누르세요');
    const row=definitions.find(x => x.id===d.processDefinitionId && x.version===d.version);
    message(`「${name(row.id,row.name)}」의 새 판본(${row.version})을 등록하고 골라 두었습니다. 아래 [실행]으로 시작할 수 있습니다.`);
  }));
  $r('definitionStart').addEventListener('click', () => action(async () => {
    const [id,version]=choice(),event=$r('definitionEvent').value.trim();
    if (!event) throw Error('시작 요청 번호를 적으세요 — 같은 번호로 다시 실행하면 서버가 중복으로 보고 시작하지 않습니다');
    const alertText=$r('definitionAlert').value.trim();
    const data={definition_id:id,version,event_id:event,variables:readObject($r('definitionValues').value,'시작 변수'),name:$r('definitionRunName').value.trim() || null};
    if (alertText) data.alert=readObject(alertText,'경보');
    const inst=await postJ(API.process+'/api/instances/start',data);
    newEvent(true);
    message('처리 건을 시작했습니다 — 처리 건 화면에서 이어 봅니다');
    selectTab('instances'); window.hydInstancesSelect(inst.proc_inst_id);
  }));
})();
