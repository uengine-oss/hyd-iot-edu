/* External service consent is separate from portal identity. Only verified server state can enable tools. */
(function () {
  const serviceTitle=p=>({'google-drive':'구글 드라이브','google-calendar':'구글 캘린더'}[p.id] || p.title);
  const STATES = {preparation_required:['준비 필요','warning'],login_required:['계정 연결 필요','neutral'],login_complete:['연결 확인 중','accent'],checking:['연결 확인 중','accent'],connected:['사용 가능','success'],disconnected:['계정 연결 필요','neutral'],failed:['실패','danger']};
  const REASONS = {cancelled:'외부 서비스 연결을 취소했습니다. 다시 연결할 수 있습니다.',expired:'외부 서비스 동의 시간이 지났습니다. 다시 연결하세요.',access_denied:'외부 서비스에서 동의를 취소했습니다.',insufficient_scope:'필요한 사용 권한이 부족합니다. 해당 서비스에서 다시 동의하세요.',insufficient_permissions:'필요한 사용 권한이 부족합니다. 해당 서비스에서 다시 동의하세요.',token_expired:'계정 연결이 만료됐습니다. 해당 서비스에서 다시 연결하세요.',invalid_grant:'계정 연결이 만료되거나 해제됐습니다. 다시 연결하세요.',popup_blocked:'인증창을 열지 못했습니다. 아래 버튼으로 다시 여세요.'};
  function display(row) {
    if (!row) return {label:'계정 연결 필요',tone:'neutral',message:'서비스를 선택하고 연결하세요.'};
    if (['token_expired','invalid_grant','login_expired','refresh_rejected'].includes(row.reason_code)) return {label:'재연결 필요',tone:'warning',message:REASONS[row.reason_code] || '계정 연결을 갱신하지 못했습니다. 해당 서비스에서 다시 연결하세요.'};
    const pair=STATES[row.status];
    const specific=row.reason_code==='api_key_required' ? '이 서버에는 표준 로그인 창이 없습니다. 접속키를 사용하는 서비스라면 제공자가 안내한 연결 방식을 선택하세요.' : row.reason_code==='denied' ? '외부 서비스에서 동의를 취소했습니다.' : row.reason_code==='scope_missing' ? '필요한 사용 권한이 부족합니다. 해당 서비스에서 다시 동의하세요.' : '';
    return {label:pair?.[0] || '상태 확인 필요',tone:pair?.[1] || 'warning',message:specific || REASONS[row.reason_code] || (row.status==='preparation_required' ? '운영자의 서비스 연결 준비가 필요합니다. 개인 토큰을 가져올 필요는 없습니다.' : row.status==='connected' ? '서비스 연결과 도구 검사를 통과했습니다.' : row.status==='login_complete' || row.status==='checking' ? '서비스 동의를 받았습니다. 사용할 도구를 확인하고 있습니다.' : row.status==='failed' ? '연결을 완료하지 못했습니다. 다시 연결하거나 운영자에게 확인을 요청하세요.' : '해당 서비스에서 로그인하고 사용 권한에 동의하세요.')};
  }
  function rowOf(value,expectedId) {
    if (!value || typeof value.id!=='string' || typeof value.status!=='string' || value.shared!==true || (expectedId && value.id!==expectedId)) throw new Error('연결 상태 응답을 읽을 수 없습니다.');
    return value;
  }
  const expiryMs=value=>typeof value==='number' && Number.isFinite(value) ? value*1000 : Date.parse(value);
  function validReturn(event, attempt, origin, popup) {
    const d=event?.data;
    return !!attempt && !!popup && event.origin===origin && event.source===popup && d?.type==='mcp-connection-return' && d.connection_id===attempt.connection_id && d.attempt_id===attempt.attempt_id && d.state===attempt.state;
  }
  function createController(deps) {
    const s={catalog:[],connections:[],configuration:null,selection:'',url:'',row:null,phase:'loading',message:'',attempt:null,popup:null,blocked:false,busy:false};
    let generation=0, disposed=false, listing=0, revision=0;
    const checking=new Set();
    const notify=()=>{if(!disposed) deps.onChange?.(s);};
    const live=g=>!disposed && g===generation;
    const endpoint=id=>'/api/mcp/connections/'+encodeURIComponent(id);
    function closePopup(){try {if(s.popup && !s.popup.closed) s.popup.close();}catch(_){} s.popup=null;}
    function selectedRow(){
      const preset=s.catalog.find(p=>p.id===s.selection);
      const candidates=s.connections.filter(r=>s.selection==='other' ? r.url===s.url.trim() : r.url===preset?.url && (r.preset===s.selection || r.name===s.selection));
      return candidates.find(r=>r.id===s.attempt?.connection_id) || candidates.find(r=>r.status==='connected') || candidates[candidates.length-1] || null;
    }
    async function refresh() {
      const ticket=++listing, g=generation, rev=revision;
      try {
        const result=await deps.get('/api/mcp/connections');
        if(!live(g) || ticket!==listing || rev!==revision)return;
        if(!Array.isArray(result?.catalog) || !Array.isArray(result?.connections))throw new Error('서비스 목록 응답을 읽을 수 없습니다.');
        s.catalog=result.catalog; s.connections=result.connections; s.configuration=result.configuration || null; s.message='';
        if(!s.selection && s.catalog.length)s.selection=s.catalog[0].id;
        s.row=selectedRow(); if(!s.attempt)s.phase='ready'; notify();
        if(s.row?.status==='login_complete')await verify(s.row.id,g);
      } catch(e){if(live(g) && ticket===listing){s.phase='error';s.message='서비스 연결 상태를 불러오지 못했습니다. 다시 읽기를 눌러 주세요.';notify();}}
    }
    async function verify(id,g=generation) {
      if(checking.has(id) || !live(g))return;
      checking.add(id); revision++;s.busy=true; s.phase='checking';notify();
      try {
        const row=rowOf(await deps.post(endpoint(id)+'/check',{}),id);
        if(!live(g))return;
        s.row=row;s.connections=s.connections.filter(r=>r.id!==id).concat(row);s.phase='ready';
        if(['connected','failed'].includes(row.status)){s.attempt=null;closePopup();if(row.status==='connected')deps.onConnected?.(row);}
      } catch(e){if(live(g)){s.phase='error';s.message='도구 연결 검사를 완료하지 못했습니다. 다시 연결해 주세요.';s.attempt=null;closePopup();}}
      finally{checking.delete(id);if(live(g)){s.busy=false;notify();}}
    }
    function select(value) {
      if(s.busy || s.attempt)return false;
      generation++;s.selection=value;s.row=null;s.message='';s.phase='ready';s.blocked=false; s.row=selectedRow();notify();return true;
    }
    function setUrl(value){if(s.busy || s.attempt)return;s.url=value;if(s.selection==='other'){generation++;s.row=selectedRow();s.phase='ready';s.message='';notify();}}
    async function connect({accessKey='',keyMode=''}={}) {
      if(s.busy || s.attempt)return;
      const preset=s.catalog.find(p=>p.id===s.selection);
      if(!preset && s.selection!=='other'){s.message='먼저 서비스를 선택하세요.';notify();return;}
      let url=s.selection==='other' ? s.url.trim() : preset.url;
      try {const parsed=new URL(url);if(!['http:','https:'].includes(parsed.protocol) || parsed.username || parsed.password)throw new Error();}catch(_){s.message='서버의 전체 주소를 적으세요. 주소에 비밀번호를 넣지 마세요.';notify();return;}
      const keyed=s.selection==='other' && s.row?.reason_code==='api_key_required';
      if(keyed && (!accessKey || !['bearer','api-key'].includes(keyMode))){s.message='서비스 접속키와 제공자가 안내한 연결 방식을 선택하세요.';notify();return;}
      const g=++generation;s.busy=true;s.message='';s.phase='preparing';s.blocked=false;
      // Open synchronously in the click turn. This owns no service session until start succeeds.
      s.popup=preset ? deps.open('about:blank') : null;notify();
      try {
        const body=preset ? {name:preset.id,url,preset:preset.id,scopes:preset.scopes || []} : keyed ? {url,auth_mode:'api_key',access_key:accessKey,key_header:keyMode==='bearer'?'Authorization':'X-API-Key',key_prefix:keyMode==='bearer'?'Bearer':''} : {url,auth_mode:'auto'};
        const existing=selectedRow();
        const row=preset && existing ? rowOf(existing) : rowOf(await deps.post('/api/mcp/connections/prepare',body));if(!live(g))return;
        s.row=row;s.connections=s.connections.filter(r=>r.id!==row.id).concat(row);
        if(row.status==='connected' && !preset){s.phase='ready';closePopup();deps.onConnected?.(row);return;}
        if(row.status==='preparation_required' || row.status==='failed'){s.phase='ready';closePopup();return;}
        const attempt=await deps.post(endpoint(row.id)+'/start',{});if(!live(g))return;
        if(attempt?.connection_id!==row.id || !attempt.attempt_id || !attempt.state || !Number.isFinite(expiryMs(attempt.expires_at)))throw new Error('연결 시작 응답을 읽을 수 없습니다.');
        const auth=new URL(attempt.authorization_url);if(auth.username || auth.password || (auth.protocol!=='https:' && !(auth.protocol==='http:' && ['localhost','127.0.0.1','[::1]'].includes(auth.hostname))))throw new Error('안전한 서비스 인증 주소가 아닙니다.');
        s.attempt=attempt;s.phase='authorizing';
        if(s.popup){s.popup.location.href=auth.href;}else if(!preset){s.popup=deps.open(auth.href);}
        if(!s.popup){s.blocked=true;s.message=REASONS.popup_blocked;}
      } catch(e){if(live(g)){const setup=['storage_unavailable','callback_not_configured','client_not_configured','runtime_unavailable'].includes(e.code);s.phase=setup?'preparation_required':'error';s.message=setup?'운영자의 서비스 연결 준비가 필요합니다. 개인 토큰을 가져올 필요는 없습니다.':'외부 서비스 연결을 시작하지 못했습니다. 운영자의 준비 상태를 확인해 주세요.';closePopup();}}
      finally{if(live(g)){s.busy=false;notify();}}
    }
    function reopen(){if(!s.attempt)return;s.popup=deps.open(s.attempt.authorization_url);s.blocked=!s.popup;if(!s.blocked)s.message='';notify();}
    async function poll() {
      if(!s.attempt || s.busy || disposed)return;
      if(expiryMs(s.attempt.expires_at)<=deps.now()){await cancel('expired');return;}
      const g=generation,id=s.attempt.connection_id,rev=revision;
      try{
        const row=rowOf(await deps.get(endpoint(id)),id);if(!live(g) || rev!==revision || s.attempt?.connection_id!==id)return;
        s.row=row;
        if(row.status==='login_complete'){await verify(id,g);return;}
        if(row.status==='connected'){s.attempt=null;s.phase='ready';closePopup();deps.onConnected?.(row);}
        else if(['failed','disconnected','preparation_required'].includes(row.status)){s.attempt=null;closePopup();s.phase='ready';}
        else if(s.popup?.closed && !s.blocked){s.blocked=true;s.message='서비스 인증창이 닫혔거나 별도 창으로 전환됐습니다. 동의를 마쳤다면 연결 확인을 기다리세요. 필요하면 인증창을 다시 열거나 연결을 취소할 수 있습니다.';}
        notify();
      }catch(e){if(live(g)){s.message='연결 진행 상태를 조회하지 못했습니다. 서비스 동의가 완료됐는지 다시 확인하고 있습니다.';notify();}}
    }
    async function returned(event) {if(!validReturn(event,s.attempt,deps.origin,s.popup))return false;await poll();return true;}
    async function cancel(reason='cancelled') {
      if(!s.attempt || s.busy)return;
      const g=generation,id=s.attempt.connection_id;revision++;s.busy=true;notify();
      try{const row=rowOf(await deps.post(endpoint(id)+'/cancel',{}),id);if(!live(g))return;s.row=row;s.attempt=null;closePopup();s.phase='ready';s.message=REASONS[reason];}
      catch(e){if(live(g))s.message='취소 요청을 확인하지 못했습니다. 연결 상태를 다시 확인하세요.';}
      finally{if(live(g)){s.busy=false;notify();}}
    }
    async function disconnect() {
      if(!s.row || s.busy || s.attempt)return;
      const g=generation,id=s.row.id;revision++;s.busy=true;notify();
      try{const row=rowOf(await deps.post(endpoint(id)+'/disconnect',{}),id);if(row.status!=='disconnected')throw new Error('연결 해제를 확인하지 못했습니다.');if(!live(g))return;s.row=row;s.connections=s.connections.filter(r=>r.id!==id).concat(row);s.message='공용 서비스 연결을 해제했습니다.';deps.onConnected?.(row);}
      catch(e){if(live(g))s.message='연결을 해제하지 못했습니다. 기존 상태를 유지합니다.';}
      finally{if(live(g)){s.busy=false;notify();}}
    }
    function dispose(){disposed=true;generation++;closePopup();}
    return {state:s,refresh,select,setUrl,connect,reopen,poll,returned,cancel,disconnect,dispose};
  }
  const mounted=new WeakMap();
  // 포털 공용 요청 함수(requestJ) 하나로 — 같은 주소(nginx 프록시, HttpOnly 연결 쿠키)라 credentials 를 싣고 20초 제한. 서버 까닭 코드는 error.code 로
  async function request(path,body) {
    try {
      return await requestJ(path,{credentials:'same-origin',timeout:20000,...(body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})});
    } catch (error) { error.code=error.detail?.reason_code; throw error; }
  }
  function mount(host,{onConnected}={}) {
    if(!host)return;
    mounted.get(host)?.dispose();
    const e=esc;
    host.innerHTML=UI.card({title:'서비스 연결',body:`<p>현재 수업에서 함께 쓰는 공용 연결입니다. 다른 학생의 개인 계정을 자동으로 섞어 쓰지 않습니다.</p>
      <div class="form-grid"><div class="field"><label for="mcpConnectService">서비스</label><select id="mcpConnectService"><option value="">서비스 목록 조회 중</option></select></div>
      <div class="field" data-connect-url hidden><label for="mcpConnectUrl">서버 주소</label><input id="mcpConnectUrl" type="url" placeholder="https://서비스주소/mcp" autocomplete="url"></div></div>
      <div data-connect-key hidden><div class="form-grid"><div class="field"><label for="mcpConnectKey">서비스 접속키</label><input id="mcpConnectKey" type="password" autocomplete="new-password"></div>
      <div class="field"><label for="mcpConnectKeyMode">접속키 방식</label><select id="mcpConnectKeyMode"><option value="">서비스 제공자가 안내한 방식 선택</option><option value="bearer">기본 접속키 방식</option><option value="api-key">전용 접속키 방식</option></select></div></div><p class="field-hint">접속키가 필요한 서버에만 사용합니다. 이 화면에서 키를 보내면 주소나 브라우저 저장소에 보관하지 않습니다.</p></div>
      <div class="row"><button class="btn primary" data-connect-start>연결</button><button class="btn small" data-connect-refresh>다시 읽기</button><button class="btn small" data-connect-reopen hidden>인증창 다시 열기</button><button class="btn small" data-connect-cancel hidden>연결 취소</button><button class="btn small" data-connect-disconnect hidden>연결 해제</button></div>
      <div data-connect-status role="status" aria-live="polite"></div><details class="fold small"><summary>운영자 연결 준비 상태</summary><div data-connect-operator></div></details>`});
    const select=host.querySelector('#mcpConnectService'),url=host.querySelector('#mcpConnectUrl'),status=host.querySelector('[data-connect-status]');
    let catalogKey='';
    const controller=createController({get:path=>request(path),post:(path,body)=>request(path,body),open:href=>window.open(href,'_blank','popup,width=620,height=720'),origin:location.origin,now:()=>Date.now(),onConnected,onChange:s=>{
      const key=JSON.stringify(s.catalog.map(p=>[p.id,p.title]));
      if(key!==catalogKey){catalogKey=key;select.innerHTML=s.catalog.map(p=>`<option value="${e(p.id)}">${e(serviceTitle(p))}</option>`).join('')+'<option value="other">다른 서버 주소</option>';}
      select.value=s.selection;select.disabled=s.busy || !!s.attempt;url.disabled=s.busy || !!s.attempt;host.querySelector('[data-connect-url]').hidden=s.selection!=='other';
      const keyed=s.selection==='other' && s.row?.reason_code==='api_key_required';
      host.querySelector('[data-connect-key]').hidden=!keyed;host.querySelector('#mcpConnectKey').disabled=s.busy;host.querySelector('#mcpConnectKeyMode').disabled=s.busy;
      if(s.row?.status==='connected')host.querySelector('#mcpConnectKey').value='';
      const setupNeeded=!s.row && s.configuration && (!s.configuration.storage_ready || !s.configuration.callback_ready);
      const shown=display(setupNeeded ? {status:'preparation_required'} : s.row),active=s.phase==='preparing' || s.phase==='authorizing' || s.phase==='checking';
      status.innerHTML=UI.chipText(active ? '연결 확인 중' : s.phase==='loading' ? '조회 중' : s.phase==='preparation_required' ? '준비 필요' : s.phase==='error' ? '실패' : shown.label,active?'accent':shown.tone)+`<p>${e(s.message || (s.phase==='authorizing' ? '열린 서비스 창에서 로그인하고 사용 권한에 동의하세요. 동의 후 연결 검사를 자동으로 진행합니다.' : shown.message))}</p>`;
      const start=host.querySelector('[data-connect-start]');start.disabled=s.busy || !!s.attempt || s.phase==='loading' || !s.selection;start.textContent=keyed ? '접속키로 연결' : s.row?.status==='connected' ? '다시 연결' : ['token_expired','invalid_grant'].includes(s.row?.reason_code) ? '해당 서비스에 다시 연결' : '연결';
      host.querySelector('[data-connect-reopen]').hidden=!s.blocked;host.querySelector('[data-connect-cancel]').hidden=!s.attempt;host.querySelector('[data-connect-disconnect]').hidden=s.row?.status!=='connected';
      host.querySelector('[data-connect-cancel]').disabled=s.busy;host.querySelector('[data-connect-disconnect]').disabled=s.busy;
      host.querySelector('[data-connect-operator]').innerHTML=`<p>${s.configuration?.storage_ready ? '연결 정보 보관 준비됨' : '운영자 연결 정보 보관 준비 필요'} · ${s.configuration?.callback_ready ? '서비스 반환 주소 준비됨' : '서비스 반환 주소 준비 필요'}</p><ul>${s.catalog.map(p=>`<li>${e(serviceTitle(p))}: ${e((Array.isArray(p.operator_requirements) ? p.operator_requirements.join(' · ') : p.operator_requirements) || '추가 준비 안내 없음')}</li>`).join('')}</ul>`;
    }});
    select.addEventListener('change',()=>controller.select(select.value));url.addEventListener('input',()=>controller.setUrl(url.value));
    host.querySelector('[data-connect-start]').addEventListener('click',()=>controller.connect({accessKey:host.querySelector('#mcpConnectKey').value,keyMode:host.querySelector('#mcpConnectKeyMode').value}));host.querySelector('[data-connect-refresh]').addEventListener('click',()=>controller.refresh());host.querySelector('[data-connect-reopen]').addEventListener('click',()=>controller.reopen());host.querySelector('[data-connect-cancel]').addEventListener('click',()=>controller.cancel());
    host.querySelector('[data-connect-disconnect]').addEventListener('click',async()=>{if(await UI.confirm({title:'공용 서비스 연결을 해제할까요?',body:'수업에서 이 연결을 사용하는 도구는 다시 연결할 때까지 사용할 수 없습니다.',ok:'연결 해제',danger:true}))controller.disconnect();});
    const message=event=>controller.returned(event);window.addEventListener('message',message);
    const timer=setInterval(()=>{if(!host.isConnected){dispose();return;}controller.poll();},1500);
    function dispose(){clearInterval(timer);window.removeEventListener('message',message);controller.dispose();}
    mounted.set(host,{dispose});controller.refresh();return controller;
  }
  window.hydMcpConnections={mount,createController,display,validReturn,request};
})();
