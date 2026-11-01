/* Source receipts are neither approval nor physical recovery. */
(function () {
  const q=id=>document.getElementById(id), panel=q('sourceEventsPanel');
  if (!panel) return;
  const labels={FAILED:'처리 실패',CONFLICT:'원문 충돌',INVALID:'잘못된 입력',WAITING:'연결 대기',
    PENDING:'처리 대기',CLAIMED:'처리 중',HANDLED:'처리 완료',DUPLICATE:'중복 접수'};
  // 접수 종류 · 전송 방식 · 원문 형식(서버 값 → 화면 말). 표에 없는 값은 원문 그대로 보인다(새 종류를 숨기지 않는다)
  const kinds={RAISE:'경보 발생',CLEAR:'경보 해제',ACK:'명령 응답',REJECT:'명령 관문 거절',STATUS:'설비 상태',INVALID:'잘못된 입력'};
  const sources={kafka:'Kafka 메시지',http:'HTTP 요청'};
  const wires={decoded:'해석한 JSON',bytes:'받은 바이트 그대로',tombstone:'빈 메시지(삭제 표시)'};
  let cursor=0, selected=null, busy=false;
  function message(text){q('sourceEventMessage').textContent=text;}
  function locked(value){busy=value;for(const id of ['sourceEventRefresh','sourceEventMore','sourceEventStatus']) q(id).disabled=value;
    q('sourceEventRetry').querySelector('button').disabled=value;
    q('sourceEventDetailRefresh').disabled=value||!selected;}
  function rowText(row){return '#'+row.id+' · '+(labels[row.status]||row.status)+' · '+(row.asset||'설비 미상')+' · '+(kinds[row.kind]||row.kind)+(row.error?' · '+UI.logText(row.error):'');}   // A141: 영문 오류 문구는 번역 표로, 원문은 선택 접수의 '오류' 칸에 그대로
  function field(parent,label,value){const title=document.createElement('h3'),body=document.createElement('pre');
    title.textContent=label;body.textContent=typeof value==='string'?value:JSON.stringify(value,null,2);
    body.style.cssText='white-space:pre-wrap;overflow-wrap:anywhere';parent.append(title,body);}
  async function detail(id){
    if(busy)return;locked(true);
    try{const row=await getJ(API.process+'/api/source-events/'+encodeURIComponent(id));selected=row;
      const listed=q('sourceEventList').querySelector('[data-receipt="'+row.id+'"]');
      if(listed){if(q('sourceEventStatus').value&&q('sourceEventStatus').value!==row.status)listed.remove();else listed.textContent=rowText(row);}
      const box=q('sourceEventDetail');box.replaceChildren();
      field(box,'접수 '+row.id+' · '+(labels[row.status]||row.status),{종류:kinds[row.kind]||row.kind,출처:sources[row.source]||row.source,설비:row.asset,
        접수시각:row.received_at,처리시도:row.attempts,실패횟수:row.failures,원본접수:row.parent_id,
        오류:row.error,처리결과:row.result});
      field(box,'접수 원문',row.payload);field(box,'접수 당시 처리 정의',row.policy);field(box,'처리 이력',row.history);
      const wire=document.createElement('details'),summary=document.createElement('summary');summary.textContent='전송 원문과 무결성 확인';wire.append(summary);
      field(wire,'원문 보존 형식',{형식:wires[row.wire_kind]||row.wire_kind,'지문(SHA-256)':row.wire_sha,'원문(base64)':row.wire_base64,
        토픽:row.topic,파티션:row.partition_no,'위치(offset)':row.offset_no});box.append(wire);
      q('sourceEventRetry').hidden=row.status!=='FAILED';
      message(row.status==='FAILED'?'원인을 확인한 뒤 같은 접수를 다시 처리할 수 있습니다.':'조회한 접수 '+row.id);
    }catch(e){selected=null;q('sourceEventRetry').hidden=true;message('접수 조회 실패: '+e.message);}
    finally{locked(false);}
  }
  async function load(reset){
    if(busy)return;locked(true);
    try{if(reset){cursor=0;selected=null;q('sourceEventList').replaceChildren();q('sourceEventDetail').replaceChildren();q('sourceEventRetry').hidden=true;}
      const status=q('sourceEventStatus').value, rows=await getJ(API.process+'/api/source-events?limit=50&after_id='+cursor+(status?'&status='+encodeURIComponent(status):''));
      for(const row of rows){const button=document.createElement('button');button.className='btn';button.type='button';
        button.dataset.receipt=row.id;button.textContent=rowText(row);
        button.addEventListener('click',()=>detail(row.id));q('sourceEventList').append(button);cursor=row.id;}
      message(rows.length?'접수 '+rows.length+'개를 읽었습니다. 마지막 번호 '+cursor:'이 조건에서 더 읽을 접수가 없습니다.');
    }catch(e){message('접수 목록 조회 실패: '+e.message);}finally{locked(false);}
  }
  q('sourceEventRefresh').addEventListener('click',()=>load(true));
  q('sourceEventMore').addEventListener('click',()=>load(false));
  q('sourceEventDetailRefresh').addEventListener('click',()=>{if(selected)detail(selected.id);});
  q('sourceEventStatus').addEventListener('change',()=>load(true));
  panel.addEventListener('toggle',()=>{if(panel.open)load(true);});
  q('sourceEventRetry').addEventListener('submit',async event=>{
    event.preventDefault();if(busy||!selected||selected.status!=='FAILED')return;
    const by=q('sourceEventActor').value.trim(),reason=q('sourceEventReason').value.trim(),id=selected.id;
    if(!by||!reason){message('담당자와 재시도 이유를 적어 주세요.');return;}
    locked(true);
    try{await postJ(API.process+'/api/source-events/'+encodeURIComponent(id)+'/retry',{by,reason});
      message('접수 '+id+'의 재시도를 요청했습니다. 완료 결과를 다시 확인하세요.');q('sourceEventRetry').hidden=true;
    }catch(e){message('재시도 접수 실패: '+e.message);}finally{locked(false);}
    await detail(id);
  });
})();
