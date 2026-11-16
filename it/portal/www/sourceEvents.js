/* 관리 › 접수 기록: 들어온 경보와 명령 응답의 접수(source receipt)를 보고, 처리에 실패한 접수를 사유와 함께 다시 처리한다.
   접수는 승인도 설비 복구도 아니다 — 받은 원문과 그때의 처리 정의를 그대로 보관한 기록이다.
   틀은 목록 + 상세(.split)이고 index.html 의 관리 화면(#sourceEventsPanel)에 있다: 왼쪽 = 상태로 거르기 · 목록 · 더 보기, 오른쪽 = 고른 접수 · 다시 처리 폼.
   이 파일은 목록의 줄과 고른 접수의 상세를 그린다: 줄 = 종류 · 설비 + 상태 알약 / 접수 번호와 오류 한 줄,
   상세(디자인기준 5-1) = 머리(이름 + 상태 알약, 아래 보조 줄, 오른쪽 끝 다시 읽기) → 요약(이름–값) → 다시 처리(실패한 접수만) → 원문 · 처리 정의 · 이력 · 전송 원문(접기).
   처음에는 상태를 가리지 않고 전체를 읽는다 — 결함을 넣거나 오일 분석을 보낸 뒤 그 접수가 여기 남았는지 바로 보인다. */
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
  // 아직 고르지 않았을 때의 오른쪽 칸
  const NONE=`<div class="pane-none">${UI.empty('왼쪽 목록에서 접수를 고르면 받은 원문과 처리 결과가 여기에 보입니다.')}</div>`;
  // bad: 실패 문장 — 빨간 한 줄(role=alert). 아니면 회색 상태 줄
  function message(text,bad=false){const m=q('sourceEventMessage');m.textContent=text;if(bad)m.dataset.tone='danger';else delete m.dataset.tone;m.setAttribute('role',bad?'alert':'status');}
  function locked(value){busy=value;for(const id of ['sourceEventRefresh','sourceEventMore','sourceEventStatus']) q(id).disabled=value;
    q('sourceEventRetry').querySelector('button').disabled=value;
    const again=q('sourceEventDetailRefresh');if(again)again.disabled=value||!selected;}
  // 접수 한 줄: 무엇이(종류 · 설비) + 상태 뱃지 하나, 둘째 줄에 접수 번호와 오류 한 줄(A141: 영문 오류 문구는 번역 표로, 원문은 고른 접수의 '오류' 칸에 그대로)
  function rowHtml(row){return `<span class="row-ic">${UI.icon(ICON[row.kind]||'circle-dot')}</span><span class="row-title">${esc((kinds[row.kind]||row.kind)+' · '+(row.asset||'설비 미상'))}</span>${UI.chipText(labels[row.status]||row.status,TONE[row.status]||'neutral')}`+
    `<span class="row-meta">접수 ${esc(row.id)}${row.error?' · '+esc(UI.logText(row.error)):''}</span>`;}
  const kv=rows=>`<dl class="kv">${rows.filter(([,v])=>v!=null&&v!=='').map(([k,v])=>`<dt>${esc(k)}</dt><dd>${v&&v.html!=null?v.html:esc(typeof v==='string'?v:String(v))}</dd>`).join('')}</dl>`;
  // 처리 결과 한 줄: 접수를 처리해 무엇이 됐는지를 글로(처리 건을 열었다 · 설비 응답을 사건에 이었다 · 경보 해제를 반영했다). 서버가 남긴 결과 값 전체는 아래 「처리 결과 원문」 접기에 있다
  function resultLine(row){const r=row.result;if(r==null||r==='')return '';if(typeof r!=='object')return {html:esc(String(r))};
    const did=r.instance?'처리 건을 열었습니다':row.kind==='ACK'&&r.ack?`설비 응답 「${UI.status(r.ack.result)}」을 사건에 이었습니다`:row.kind==='CLEAR'?(r.cleared?'경보 해제를 사건에 반영했습니다':'경보 해제를 받았습니다'):'';
    const ids=[r.incident?'사건 '+UI.id(r.incident):'',r.cmdId?'명령 '+UI.id(r.cmdId):''].filter(Boolean).join(' · ');
    return did||ids?{html:[esc(did),ids].filter(Boolean).join(' · ')}:{html:'<span class="muted">아래 「처리 결과 원문」에 있습니다</span>'};}
  const raw=(value,title)=>UI.raw(value,{title})||`<p class="muted">${esc(title)} 없음</p>`;
  function mark(){q('sourceEventList').querySelectorAll('.row').forEach(n=>{if(selected&&n.dataset.receipt===String(selected.id))n.setAttribute('aria-current','true');else n.removeAttribute('aria-current');});}
  // 고른 접수: 머리(종류 · 설비 · 상태) → 요약(이름–값) → 다시 처리(실패한 접수만, 같은 판 안의 폼) → 원문 · 처리 정의 · 이력 · 전송 원문(접기)
  async function detail(id){
    if(busy)return;locked(true);
    try{const row=await getJ(API.process+'/api/source-events/'+encodeURIComponent(id));selected=row;
      const listed=q('sourceEventList').querySelector('[data-receipt="'+row.id+'"]');
      if(listed){if(q('sourceEventStatus').value&&q('sourceEventStatus').value!==row.status)listed.remove();else listed.innerHTML=rowHtml(row);}
      mark();
      q('sourceEventDetail').innerHTML=`<header class="panel-head pane-head"><div class="pane-title"><h2>${esc((kinds[row.kind]||row.kind)+' · '+(row.asset||'설비 미상'))}${UI.chipText(labels[row.status]||row.status,TONE[row.status]||'neutral')}</h2><p class="num">접수 ${esc(row.id)}${row.received_at?' · '+esc(UI.dateTime(row.received_at)):''}</p></div>
          <div class="pane-acts"><button type="button" class="btn" data-variant="ghost" data-size="icon-sm" id="sourceEventDetailRefresh" aria-label="이 접수 다시 읽기" data-tooltip="이 접수 다시 읽기" data-side="left">${UI.icon('refresh-cw')}</button></div></header>
        <div class="panel-sec">${kv([['처리 결과',resultLine(row)],['오류',row.error],['받은 방식',sources[row.source]||row.source],['처리 시도',row.attempts!=null?row.attempts+'회'+(row.failures?' · 실패 '+row.failures+'회':''):''],['원본 접수 번호',row.parent_id]])}
          ${row.result&&row.result.instance?`<p class="pane-foot"><a class="go" href="#/instances/${encodeURIComponent(row.result.instance)}">처리 건 열기</a></p>`:''}</div>
        <div class="panel-sec pane-fold se-folds">${raw(row.payload,'접수 원문')}${row.result&&typeof row.result==='object'?raw(row.result,'처리 결과 원문'):''}${raw(row.policy,'접수 당시 처리 정의')}${raw(row.history,'처리 이력')}
          ${UI.fold('전송 원문과 무결성 확인',kv([['형식',wires[row.wire_kind]||row.wire_kind],['지문(SHA-256)',row.wire_sha],['원문(base64)',row.wire_base64],['토픽',row.topic],['파티션',row.partition_no],['위치(offset)',row.offset_no]]))}</div>`;
      q('sourceEventRetry').hidden=row.status!=='FAILED';
      message('');
    }catch(e){selected=null;q('sourceEventDetail').innerHTML=NONE;q('sourceEventRetry').hidden=true;mark();message('접수를 읽지 못했습니다: '+e.message,true);}
    finally{locked(false);}
  }
  async function retry(event){
    event.preventDefault();if(busy||!selected||selected.status!=='FAILED')return;
    const by=window.hydInbox?.me?.()?.name||'',reason=q('sourceEventReason').value.trim(),id=selected.id;      // 누가 = 이 PC의 담당자(자유 글 칸 없음)
    if(!by){message('담당자 정보를 읽지 못해 보낼 수 없습니다. 화면을 새로 고친 뒤 다시 해 주세요.',true);return;}
    if(!reason){message('다시 처리하는 사유를 적어 주세요.',true);return;}
    locked(true);
    try{await postJ(API.process+'/api/source-events/'+encodeURIComponent(id)+'/retry',{by,reason});
      UI.toast('접수 '+id+'번을 다시 처리하도록 요청했습니다. 결과는 이 접수의 상태와 처리 이력에 남습니다.',{tone:'ok'});q('sourceEventRetry').hidden=true;q('sourceEventReason').value='';
    }catch(e){message('다시 처리를 요청하지 못했습니다: '+e.message,true);}finally{locked(false);}
    await detail(id);
  }
  async function load(reset){
    if(busy)return;locked(true);
    try{if(reset){cursor=0;selected=null;q('sourceEventList').replaceChildren();q('sourceEventDetail').innerHTML=NONE;q('sourceEventRetry').hidden=true;}
      const status=q('sourceEventStatus').value, rows=await getJ(API.process+'/api/source-events?limit=50&after_id='+cursor+(status?'&status='+encodeURIComponent(status):''));
      for(const row of rows){const button=document.createElement('button');button.className='row';button.type='button';
        button.dataset.receipt=row.id;button.innerHTML=rowHtml(row);
        button.addEventListener('click',()=>detail(row.id));q('sourceEventList').append(button);cursor=row.id;}
      more=rows.length>=50;
      // 빈 상태는 한 문장 + 그 일을 하는 단추 하나(4-10): 접수가 아예 없으면 접수를 만드는 화면으로, 거른 상태에만 없으면 거르기를 푸는 말로
      if(!q('sourceEventList').children.length) q('sourceEventDetail').innerHTML=`<div class="pane-none">${status
        ?UI.empty(`「${labels[status]}」 상태인 접수가 없습니다`,'목록 위에서 상태를 「전체」로 바꾸면 모든 접수가 보입니다.')
        :UI.emptyGo('아직 접수가 없습니다','설비에서 경보가 나거나 명령 응답이 들어오면 여기에 남습니다.','scenario','결함 시뮬레이션 열기')}</div>`;
      message(rows.length||reset?'':'더 읽을 접수가 없습니다.');
    }catch(e){message('접수 목록을 읽지 못했습니다: '+e.message,true);}finally{locked(false);q('sourceEventMore').hidden=!more;}
  }
  q('sourceEventRefresh').addEventListener('click',()=>load(true));
  q('sourceEventMore').addEventListener('click',()=>load(false));
  q('sourceEventDetail').addEventListener('click',ev=>{if(ev.target.closest('#sourceEventDetailRefresh')&&selected)detail(selected.id);});
  q('sourceEventRetry').addEventListener('submit',retry);
  q('sourceEventStatus').addEventListener('change',()=>load(true));
  // 접기를 펼 때 읽는다. 접기가 아닌 자리에 놓였으면 관리 화면을 열 때 읽는다
  if(panel.tagName==='DETAILS') panel.addEventListener('toggle',()=>{if(panel.open)load(true);});
  else window.hydTabs?.onShow(name=>{if(name==='admin')load(true);});
})();
