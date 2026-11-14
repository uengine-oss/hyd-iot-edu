/* 관리 › 접수 기록: 들어온 경보와 명령 응답의 접수(source receipt)를 보고, 처리에 실패한 접수를 사유와 함께 다시 처리한다.
   접수는 승인도 설비 복구도 아니다 — 받은 원문과 그때의 처리 정의를 그대로 보관한 기록이다.
   틀(상태 고르기 · 단추 · 목록 자리 · 상세 자리 · 다시 처리 폼)은 index.html 의 관리 화면(#sourceEventsPanel)에 있고, 이 파일은 목록의 줄과 고른 접수의 상세를 그린다:
   줄 = 종류 · 설비 + 상태 뱃지 / 접수 번호와 오류 한 줄, 상세 = 요약(이름–값) → 원문 · 처리 정의 · 이력 · 전송 원문(접기). */
(function () {
  const q=id=>document.getElementById(id), panel=q('sourceEventsPanel');
  if (!panel) return;
  const labels={FAILED:'처리 실패',CONFLICT:'원문 충돌',INVALID:'잘못된 입력',WAITING:'연결 대기',
    PENDING:'처리 대기',CLAIMED:'처리 중',HANDLED:'처리 완료',DUPLICATE:'중복 접수'};
  // 접수 종류 · 전송 방식 · 원문 형식(서버 값 → 화면 말). 표에 없는 값은 원문 그대로 보인다(새 종류를 숨기지 않는다)
  const kinds={RAISE:'경보 발생',CLEAR:'경보 해제',ACK:'명령 응답',REJECT:'명령 관문 거절',STATUS:'설비 상태',INVALID:'잘못된 입력'};
  const sources={kafka:'Kafka 메시지',http:'HTTP 요청'};
  const wires={decoded:'해석한 JSON',bytes:'받은 바이트 그대로',tombstone:'빈 메시지(삭제 표시)'};
  const TONE={FAILED:'danger',CONFLICT:'danger',INVALID:'danger',WAITING:'warning',PENDING:'neutral',CLAIMED:'accent',HANDLED:'success',DUPLICATE:'neutral'};
  const ICON={RAISE:'triangle-alert',CLEAR:'circle-check',ACK:'corner-down-right',REJECT:'shield-alert',STATUS:'activity',INVALID:'circle-x'};
  let cursor=0, selected=null, busy=false, more=false;
  // bad: 실패 문장 — 빨간 한 줄(role=alert). 아니면 회색 상태 줄
  function message(text,bad=false){const m=q('sourceEventMessage');m.textContent=text;if(bad)m.dataset.tone='danger';else delete m.dataset.tone;m.setAttribute('role',bad?'alert':'status');}
  function locked(value){busy=value;for(const id of ['sourceEventRefresh','sourceEventMore','sourceEventStatus']) q(id).disabled=value;
    q('sourceEventRetry').querySelector('button').disabled=value;
    q('sourceEventDetailRefresh').disabled=value||!selected;}
  // 접수 한 줄: 무엇이(종류 · 설비) + 상태 뱃지 하나, 둘째 줄에 접수 번호와 오류 한 줄(A141: 영문 오류 문구는 번역 표로, 원문은 고른 접수의 '오류' 칸에 그대로)
  function rowHtml(row){return `<span class="row-ic">${UI.icon(ICON[row.kind]||'circle-dot')}</span><span class="row-title">${esc((kinds[row.kind]||row.kind)+' · '+(row.asset||'설비 미상'))}</span>${UI.chipText(labels[row.status]||row.status,TONE[row.status]||'neutral')}`+
    `<span class="row-meta">접수 ${esc(row.id)}${row.error?' · '+esc(UI.logText(row.error)):''}</span>`;}
  const kv=rows=>`<dl class="kv">${rows.filter(([,v])=>v!=null&&v!=='').map(([k,v])=>`<dt>${esc(k)}</dt><dd>${esc(typeof v==='string'?v:String(v))}</dd>`).join('')}</dl>`;
  const raw=value=>`<pre class="code">${esc(typeof value==='string'?value:JSON.stringify(value,null,2))}</pre>`;
  function mark(){q('sourceEventList').querySelectorAll('.row').forEach(n=>{if(selected&&n.dataset.receipt===String(selected.id))n.setAttribute('aria-current','true');else n.removeAttribute('aria-current');});}
  // 고른 접수: 머리(종류 · 설비 · 상태) → 요약(이름–값) → 다시 처리(실패한 접수만, 같은 판 안의 폼) → 원문 · 처리 정의 · 이력 · 전송 원문(접기)
  async function detail(id){
    if(busy)return;locked(true);
    try{const row=await getJ(API.process+'/api/source-events/'+encodeURIComponent(id));selected=row;
      const listed=q('sourceEventList').querySelector('[data-receipt="'+row.id+'"]');
      if(listed){if(q('sourceEventStatus').value&&q('sourceEventStatus').value!==row.status)listed.remove();else listed.innerHTML=rowHtml(row);}
      mark();
      q('sourceEventDetail').innerHTML=`<h3>${esc((kinds[row.kind]||row.kind)+' · '+(row.asset||'설비 미상'))}${UI.chipText(labels[row.status]||row.status,TONE[row.status]||'neutral')}<span class="muted num">접수 ${esc(row.id)}</span></h3>
        ${kv([['접수 시각',row.received_at?UI.dateTime(row.received_at):''],['받은 방식',sources[row.source]||row.source],['처리 시도',row.attempts!=null?row.attempts+'회':''],['실패 횟수',row.failures!=null?row.failures+'회':''],['원본 접수 번호',row.parent_id],
          ['오류',row.error],['처리 결과',row.result==null?'':typeof row.result==='string'?row.result:JSON.stringify(row.result)]])}
        <div class="se-folds">${UI.fold('접수 원문',raw(row.payload))}${UI.fold('접수 당시 처리 정의',raw(row.policy))}${UI.fold('처리 이력',raw(row.history))}
          ${UI.fold('전송 원문과 무결성 확인',kv([['형식',wires[row.wire_kind]||row.wire_kind],['지문(SHA-256)',row.wire_sha],['원문(base64)',row.wire_base64],['토픽',row.topic],['파티션',row.partition_no],['위치(offset)',row.offset_no]]))}</div>`;
      q('sourceEventRetry').hidden=row.status!=='FAILED';
      message(row.status==='FAILED'?'원인을 확인한 뒤 같은 접수를 다시 처리할 수 있습니다.':'접수 '+row.id+'번을 읽었습니다.');
    }catch(e){selected=null;q('sourceEventDetail').innerHTML='';q('sourceEventRetry').hidden=true;mark();message('접수를 읽지 못했습니다: '+e.message,true);}
    finally{locked(false);}
  }
  async function retry(event){
    event.preventDefault();if(busy||!selected||selected.status!=='FAILED')return;
    const by=window.hydInbox?.me?.()?.name||'',reason=q('sourceEventReason').value.trim(),id=selected.id;      // 누가 = 이 PC의 담당자(자유 글 칸 없음)
    if(!by){message('담당자 정보를 읽지 못해 보낼 수 없습니다. 화면을 새로 고친 뒤 다시 해 주세요.',true);return;}
    if(!reason){message('다시 처리하는 사유를 적어 주세요.',true);return;}
    locked(true);
    try{await postJ(API.process+'/api/source-events/'+encodeURIComponent(id)+'/retry',{by,reason});
      message('접수 '+id+'의 재시도를 요청했습니다. 완료 결과를 다시 확인하세요.');q('sourceEventRetry').hidden=true;
    }catch(e){message('다시 처리를 요청하지 못했습니다: '+e.message,true);}finally{locked(false);}
    await detail(id);
  }
  async function load(reset){
    if(busy)return;locked(true);
    try{if(reset){cursor=0;selected=null;q('sourceEventList').replaceChildren();q('sourceEventDetail').innerHTML='';q('sourceEventRetry').hidden=true;}
      const status=q('sourceEventStatus').value, rows=await getJ(API.process+'/api/source-events?limit=50&after_id='+cursor+(status?'&status='+encodeURIComponent(status):''));
      for(const row of rows){const button=document.createElement('button');button.className='row';button.type='button';
        button.dataset.receipt=row.id;button.innerHTML=rowHtml(row);
        button.addEventListener('click',()=>detail(row.id));q('sourceEventList').append(button);cursor=row.id;}
      more=rows.length>=50;
      if(!q('sourceEventList').children.length) q('sourceEventDetail').innerHTML=`<div class="sk-none">${UI.empty(status?`「${labels[status]}」 상태인 접수가 없습니다`:'접수가 없습니다','경보가 나거나 명령 응답이 들어오면 여기에 남습니다. 위에서 상태를 「전체」로 바꾸면 모든 접수가 보입니다.')}</div>`;
      message(rows.length?'접수 '+rows.length+'건을 읽었습니다.'+(more?' 더 있으면 [더 보기]를 누르세요.':''):reset?'':'더 읽을 접수가 없습니다.');
    }catch(e){message('접수 목록을 읽지 못했습니다: '+e.message,true);}finally{locked(false);q('sourceEventMore').hidden=!more;}
  }
  q('sourceEventRefresh').addEventListener('click',()=>load(true));
  q('sourceEventMore').addEventListener('click',()=>load(false));
  q('sourceEventDetailRefresh').addEventListener('click',()=>{if(selected)detail(selected.id);});
  q('sourceEventRetry').addEventListener('submit',retry);
  q('sourceEventStatus').addEventListener('change',()=>load(true));
  // 접기를 펼 때 읽는다. 접기가 아닌 자리에 놓였으면 관리 화면을 열 때 읽는다
  if(panel.tagName==='DETAILS') panel.addEventListener('toggle',()=>{if(panel.open)load(true);});
  else window.hydTabs?.onShow(name=>{if(name==='admin')load(true);});
})();
