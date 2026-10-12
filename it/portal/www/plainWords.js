/* A161 처리 기록 — 쉬운 말 사전. 도구 이름 · 시스템 · 값 이름 · 단위 · 규칙 식 · 실행 코드를 사람 말로 바꾼다.
   처리 기록(caseRecord.js)이 쓰고, 다른 화면도 window.hydWords 로 쓸 수 있다. 사전에 없는 것은 지어내지 않고 원래 이름을 그대로 둔다.
   원래 이름(id)은 기본으로 숨기고, 화면의 "원래 이름 보기"를 켜면 이름 옆에 작게 보인다(showIds).

   참고: n8n 실행 화면은 노드 이름을 사람이 붙인 이름으로 보이고 원래 종류(type)는 패널 안쪽에만 둔다
   (https://docs.n8n.io/workflows/executions/), Dify tracing-panel 의 노드 제목도 같은 방식이다(web/app/components/workflow/run/node.tsx). */
(function () {
  const W = { showIds: false };
  try { W.showIds = localStorage.getItem('hyd:record:ids') === '1'; } catch (_) { /* 저장소가 없으면 기본(숨김) */ }

  /* ---------------------------------------------------------------- 시스템 (어디에 물었나 · 어디에 했나) */
  const SERVERS = {
    neo4j: '지식 그래프', 'hyd-dmn': '판단 엔진', enterprise: '업무 DB (생산 · 구매 · 정비)', 'enterprise-maint': '정비 업무 DB',
    'enterprise-purchase': '구매 업무 DB', 'hyd-effects': '메일 · 알림', effects: '메일 · 알림',
  };
  const SYSTEMS = {
    'sys:cmms': '정비 시스템 (CMMS)', 'sys:erp': 'ERP (구매 · 재고)', 'sys:mes': '생산 시스템 (MES)', 'sys:scm': '공급망 (SCM)', 'sys:qms': '품질 시스템',
    'sys:scada': '설비 제어', 'sys:plc': '설비 제어 (PLC)', 'sys:agent': 'AI 일꾼', 'sys:process': '처리 엔진', 'sys:erp-monitor': 'ERP 재고 감시', 'sys:cmms-monitor': '정비 계수기 감시',
    'actr:pump-drive': '펌프 구동부', 'actr:fan-drive': '쿨러 팬 구동부', 'sys:tsdb': '센서 기록 DB', detector: '센서 경보 감지기',
  };
  W.system = id => {
    if (!id) return '';
    if (SYSTEMS[id]) return SYSTEMS[id];
    if (/^sen:/.test(id)) return `센서 ${String(id).slice(4).toUpperCase()}`;
    if (/^sys:/.test(id) || /^actr:/.test(id)) return (UI.names && UI.names[id]) || id.replace(/^\w+:/, '').replace(/[-_]/g, ' ');
    return SERVERS[id] || id;
  };

  /* ---------------------------------------------------------------- 값 이름 · 단위 (센서 태그 · 판단 사실 · 업무 값) */
  const F = {
    ts1: ['유온', '℃'], ts2: ['유온 2', '℃'], ts4: ['캐비닛 온도', '℃'], t_amb: ['주변 온도', '℃'], ce: ['냉각 효율', '%'], ps1: ['토출 압력', 'bar'], fs1: ['유량', 'L/min'],
    vs1: ['진동', 'mm/s'], load: ['펌프 부하', '%'], loadsp: ['펌프 부하 설정', '%'], fanspeedsp: ['쿨러 팬 속도 설정', '%'], valvesp: ['메인 밸브 개도 설정', '%'], load_pct: ['펌프 부하', '%'], fan_pct: ['팬 속도', '%'], score: ['경보 점수', ''], ts1_slope: ['유온 상승 속도', '℃/s'],
    vs1_slope: ['진동 상승 속도', 'mm/s²'], cooler_health: ['쿨러 상태', ''], plc_mode: ['운전 모드', ''], plc_state: ['설비 상태', ''], hot_lot_qty: ['출하 대기 로트', '개'],
    order_due_h: ['납기까지', 'h'], fan100_hours: ['팬 100 % 운전 누적', 'h'], standby_ready: ['예비 설비 준비', ''], order_customer_tier: ['고객 등급', ''],
    order_penalty_per_h: ['지연 보상', '만원/h'], hot_lot_claim: ['출하 로트 클레임', '만원'], oil_analysis_out_of_spec: ['오일 분석 기준 밖', ''],
    cause: ['판정 원인', ''], pattern: ['경보 패턴', ''], failure_mode: ['고장 유형', ''],
    // 정기 정비 (CMMS 계수기 · 계획)
    hours_since_pm: ['마지막 정비 뒤 운전시간', 'h'], pm_since_h: ['마지막 정비 뒤 운전시간', 'h'], pm_interval_h: ['정비 주기', 'h'], pm_tolerance_pct: ['허용 오차', '%'],
    pm_notice_h: ['사전 알림', 'h'], pm_due_in_h: ['정비 기한까지', 'h'], pm_limit_in_h: ['허용 한도까지', 'h'], hours_at_next_window: ['이번 정비 시간의 운전시간', 'h'],
    hours_at_following_window: ['다음 정비 시간의 운전시간', 'h'], pm_crew_available: ['정비 가능 인원', '명'], spare_available: ['정비 키트 재고', '개'],
    night_window_in_h: ['야간 정비 시간까지', 'h'], night_window_at: ['야간 정비 시간', ''], cycle: ['정비 회차', '회'], package: ['정비 묶음', ''], kit_qty: ['키트 수량', '개'],
    kit_part_no: ['키트 부품', ''], bundle_peer: ['함께 정비할 설비', ''], bundle_peer_since_h: ['함께 정비할 설비 운전시간', 'h'], pm_window_open: ['정비 시간 열림', ''],
    configured_base_package: ['등록된 기본 정비 내용', ''], package_semantics: ['정비 내용의 기록 의미', ''],
    // 예비품 (ERP 재고 · 견적)
    part_no: ['부품 번호', ''], name: ['이름', ''], on_hand: ['현재고', '개'], reserved: ['정비 예약', '개'], available: ['가용 재고', '개'], on_order: ['입고 예정', '개'],
    spare_gap: ['가용 재고 − 재주문점', '개'], reorder_point: ['재주문점', '개'], target_stock: ['목표 재고', '개'], need_qty: ['필요 수량', '개'], need_by_days: ['필요일까지', '일'],
    below_since: ['기준 아래로 내려간 시각', ''], spare_quotes: ['공급사 견적', ''], po_amount: ['발주 금액', '만원'], lead_slack_days: ['납기 여유', '일'],
    supplier_fail_rate: ['공급사 불량률(비율)', ''], supplier_avl: ['승인 공급사(AVL)', ''], approved_amount: ['승인 금액', '만원'], approved_qty: ['수량', '개'], approved_supplier: ['공급사', ''],
    approved_unit_price: ['단가', '만원'], approved_part_no: ['부품', ''], lead_d: ['리드타임', '일'], delay_d: ['공급사 지연', '일'],
    // 업무 사실 (MES · ERP)
    due_in_h: ['납기까지', 'h'], remaining_qty: ['남은 수량', '개'], rate_per_h: ['시간당 생산', '개/h'], alt_rate_per_h: ['대체 설비 시간당', '개/h'], alt_free_h: ['대체 설비 빌 때까지', 'h'],
    changeover_h: ['전환 시간', 'h'], fg_stock: ['완제품 재고', '개'], ship_in_h: ['출하까지', 'h'], penalty_per_h: ['지연 보상', '만원/h'], failure_cost: ['고장 비용', '만원'],
    claim_cost: ['클레임 비용', '만원'], customer_tier: ['고객 등급', ''], order_id: ['생산 주문', ''], sales_order: ['판매 계약', ''],
  };
  W.fieldName = (key, context) => { const k = String(key || ''); if(k==='package' && context?.package_semantics==='base_interval_configuration') return '등록된 기본 정비 내용'; const f = F[k] || F[k.toLowerCase()]; return W.caseFields?.[k] || (f ? f[0] : (UI.terms['var.' + k] || k.replace(/_/g, ' '))); };
  W.setpointsText = data => {
    const s = data?.setpoints;
    if (!s) return '';
    return [['FanSpeedSP', '팬 지령'], ['LoadSP', '부하 지령']].map(([k, label]) =>
      s.before?.[k] != null && s.after?.[k] != null ? `${label} ${s.before[k]} % → ${s.after[k]} %` : '').filter(Boolean).join(' · ');
  };
  W.effectText = (job, d) => {
    if (!['EFFECT_COMPENSATION', 'EFFECT_REVIEW'].includes(job)) return '';
    const results = (d.results || []).map(r => `${r.ok ? '되돌림 완료' : '되돌림 실패'}${r.error ? ': ' + r.error : ''}`).join(' · ');
    return `${W.who(d.by)}${d.role ? ' · ' + W.who(d.role) : ''} · 사유: ${d.reason || '기록 없음'}${results ? ' · ' + results : ''}${job === 'EFFECT_REVIEW' ? ' · 되돌릴 수 없는 기존 조치의 영향을 확인했습니다. 조치를 되돌린 것은 아닙니다.' : ''}`;
  };
  W.deferralReason = record => {
    const assessment=record?.assessment || record || {};
    return W.text(assessment.reason || record?.reason || '보류 사유 기록 없음').replace(/\bWO_RESCHEDULE\b/g,W.code('WO_RESCHEDULE'));
  };
  W.deferralEvidenceHtml = record => {
    const e=UI.esc || esc, assessment=record?.assessment || record || {};
    const response=assessment.evidence?.evaluate_cards, evaluated=response?.result==='ok' ? response.document : null;
    const options=Array.isArray(evaluated?.options) ? evaluated.options : null;
    const body=options ? `<p>보류 당시 평가한 대안 ${options.length}개 · 판단 등록 · 승인 · 실행 기록이 아닙니다.</p>`+
      options.map(option=>`<section data-deferral-option><h4>${e(option?.name && option.name!==option.id ? W.text(option.name) : '대안 표시 이름 기록 없음')}</h4><p>${option?.feasible===false ? '후보 제외' : option?.feasible===true ? '평가 당시 후보 · 승인 여부와 별도' : '후보 가능 여부 확인 기록 없음'}</p>${W.maintenanceHtml(option)}${!option?.maintenancePlan && !option?.maintenanceDiagnostics ? (option?.violations || []).map(v=>`<p>${e(v.annotation ? W.text(v.annotation) : '제외 사유 설명 기록 없음 · 원문 확인')}</p>`).join('') : ''}</section>`).join('')
      : '<p>구조화된 대안 평가 근거를 확인할 수 없습니다. 조회되지 않은 사실은 재고 0이나 실행 가능을 뜻하지 않습니다.</p>';
    return `<div data-deferral-evidence><p><b>평가 보류 · 업무 완료 아님</b></p><p>${e(W.deferralReason(record))}</p>${body}`+
      UI.fold('보류 평가 근거 원문',`<pre>${e(JSON.stringify(assessment,null,2))}</pre>`,{cls:'small'}).replace('<details','<details data-deferral-raw')+'</div>';
  };
  W.maintenanceHtml = option => {
    const plan=option?.maintenancePlan, diagnostics=option?.maintenanceDiagnostics, excluded=(option?.violations || []).filter(v=>v.rule==='execution:pm-plan');
    if (!plan && !diagnostics && !excluded.length) return '';
    const e=UI.esc || esc;
    let text='정비 실행 계획 기록 없음 · 새 오더나 다음 정비 시간을 대신 만들지 않습니다.';
    if(!plan && diagnostics) text='검사 도중 확보한 정비 근거입니다. 실행 가능한 계획은 확정되지 않았습니다.';
    if (plan?.code==='WO_RESCHEDULE') text=`기존 정기 정비 오더 일정 변경 · ${plan.ref || '기존 오더 미상'} · 새 오더 생성 아님`;
    else if (plan?.code==='WO_CREATE') text='새 정기 정비 오더 생성 계획 · 기존 오더 일정 변경 아님';
    else if(plan) text='정비 실행 계획 형식 확인 필요 · 실행 가능 여부를 추정하지 않습니다.';
    const window=plan?.window;
    const time=window?.immediate===true ? '즉시 정비 시간' : window?.starts_at ? UI.dateTime(window.starts_at) : '정비 시간 미상';
    const hours=typeof plan?.hours_at_window==='number' ? `해당 시간의 운전시간 ${W.num(plan.hours_at_window)} h` : '';
    const limit=typeof plan?.limit_hours==='number' ? `허용 한도 ${W.num(plan.limit_hours)} h` : '';
    return `<p><b>${e(excluded.length ? '정비 실행 계획 불가 · 후보 제외' : text)}</b>${excluded.length ? '<br>'+e(text) : ''}${plan ? '<br>'+e([time,hours,limit].filter(Boolean).join(' · ')) : ''}</p>`+
      W.maintenanceScopeHtml(plan || diagnostics)+
      excluded.map(v=>`<p>${e(v.annotation ? W.text(v.annotation) : '제외 사유 설명 기록 없음 · 원문 확인 필요')}</p>`).join('')+
      UI.fold('정비 실행 계획 · 제외 근거 원문',`<pre>${e(JSON.stringify({maintenancePlan:plan,maintenanceDiagnostics:diagnostics,violations:excluded},null,2))}</pre>`,{cls:'small'});
  };
  W.maintenanceScopeHtml = plan => {
    if (!plan || !Object.prototype.hasOwnProperty.call(plan,'scope') && !Object.prototype.hasOwnProperty.call(plan,'assets')) return '';
    const e=UI.esc || esc, n=(v,unit='시간')=>typeof v==='number' && Number.isFinite(v) ? `${W.num(v)}${unit}` : '기록 없음';
    const assetName=a=>typeof a==='string' && /^HYD-\d+$/.test(a) ? a : UI.names?.[a] || '설비 표시 이름 기록 없음';
    const assets=Array.isArray(plan.assets) ? plan.assets : [];
    const label=plan.scope==='bundle' && assets.length===2 ? '두 설비 동시 정비 계획 · 설비별 근거' : plan.scope==='single' && assets.length===1 ? '단일 설비 정비 계획 · 이번 차례 근거' : '정비 대상 범위 기록 확인 필요';
    let html=`<p><b>${e(plan.ready===false ? '실행 불가 정비 검사 · 관측한 설비별 근거' : label)}</b> · 대상 ${assets.length}대</p>`;
    const effects={reserve:'부품 예약 계획 · 실물 출고와 별도',issue:'부품 실물 출고 계획 · 정비 완료와 별도',preserve:'기존 오더 부품 할당 보존 · 새 예약이나 재출고 아님'};
    html+=`<p>${e(Object.prototype.hasOwnProperty.call(effects,plan.stock_effect) ? effects[plan.stock_effect] : '부품 처리 방식 기록 없음 · 예약이나 출고를 추정하지 않습니다.')}</p>`;
    if (plan.scope==='bundle') html+='<p>같은 정비 시간에 시행하는 계획입니다. 동종 설비 · 상대 설비 운전시간 · 공통 정비 시간 · 부품 범위는 서버 검사 근거를 확인하세요. 계획은 오더 생성이나 정비 완료가 아닙니다.</p>';
    html+=assets.map(row=>{
      if(!row || typeof row!=='object') return '<p>설비별 정비 근거 형식 확인 필요</p>';
      const service=row.service || {}, parts=Array.isArray(row.parts) ? row.parts : [];
      const a=row.applicability;
      const name=service.package_name || (typeof service.package_interval_h==='number' ? n(service.package_interval_h)+' 정비 묶음' : '이번 차례 정비 묶음 기록 없음');
      return `<div data-pm-asset="${e(row.asset)}"><h4>${e(assetName(row.asset))} · ${e(name)}</h4><p>${service.package_sop ? '원문 절차 '+e(service.package_sop)+' · ' : ''}정비 간격 ${e(n(service.interval_h))} · 마지막 정비 뒤 ${e(n(service.since_pm_h))}</p><p>누적 운전시간 ${e(n(service.total_h))} · 마지막 정비의 누적 기준 ${e(n(service.last_service_total_h))} · 이번 정비 차례 누적 기준 ${e(n(service.next_due_total_h))} · 정비 차례 ${e(n(service.service_position,'번째'))}</p>`+
        (typeof service.package_interval_h==='number' ? `<p>이번 차례 패키지 간격 ${e(n(service.package_interval_h))} · 기본 정비 간격과 구분합니다.</p>` : '')+
        (a && typeof a==='object' ? `<p>원문 동종 설비 범위 ${a.source_model_member===true ? '확인됨' : a.source_model_member===false ? '불일치' : '확인 기록 없음'} · 운전시간 하한 ${e(n(a.lower_hours))} · 실제 ${e(n(a.observed_hours))} · ${a.lower_hours_met===true ? '하한 충족 확인됨' : a.lower_hours_met===false ? '하한 미달' : '하한 판정 기록 없음'}</p><p>목표 시점 운전시간 ${e(n(a.target_hours))} · 허용 상한 ${e(n(a.limit_hours))} · ${a.within_limit===true ? '상한 이내 확인됨' : a.within_limit===false ? '상한 초과' : '상한 판정 기록 없음'} · ${a.common_window_verified===true ? '공통 정비 시간 확인됨' : a.common_window_verified===false ? '공통 정비 시간 불일치' : '공통 정비 시간 확인 기록 없음'}${a.common_start ? ' · '+e(UI.dateTime(a.common_start)) : ''}</p>` : '<p>동종 설비 · 운전시간 하한 · 공통 정비 시간 검사 기록 없음</p>')+
        (parts.length ? '<ul>'+parts.map(p=>`<li>${e(p?.name || p?.part_no || '부품 표시 이름 기록 없음')}${p?.name && p?.part_no ? ' · '+e(p.part_no) : ''} · 필요 ${e(n(p?.qty,'개'))} · 가용 ${e(n(p?.available,'개'))} · ${p?.verified===true ? '부품 근거 확인됨' : p?.verified===false ? '부품 근거 확인 안 됨' : '부품 근거 검증 기록 없음'}${plan.stock_effect==='issue' ? '<p>현재고 '+e(n(p?.on_hand,'개'))+' · 이미 예약한 수량 '+e(n(p?.reserved,'개'))+' · 입고 예정과 실물 출고 가능 여부를 구분합니다.</p>' : plan.stock_effect==='preserve' ? '<p>기존 오더의 확인된 할당 '+e(n(p?.owned_qty,'개'))+' · 새 부품을 자동 할당하지 않습니다.</p>' : ''}</li>`).join('')+'</ul>' : '<p>설비별 부품 근거 기록 없음</p>')+'</div>';
    }).join('');
    const staff=plan.staffing;
    if(staff && typeof staff==='object') html+=`<p><b>정비 인력</b> · 필요 ${e(n(staff.required,'명'))} · 가용 ${e(n(staff.available,'명'))} · 부족 ${e(n(staff.shortfall,'명'))}</p><p>${staff.confirmed===true ? '인력 확보 확인 기록 있음 · 정비 완료와 별도입니다.' : staff.arrangement_required===true ? '인력 확보 필요 · 확보 완료로 확인되지 않았습니다.' : '인력 확보 완료 확인 기록 없음'}</p>`;
    if(Array.isArray(plan.parts_totals) && plan.parts_totals.length) html+='<p><b>전체 대상 설비의 부품 필요량</b></p><ul>'+plan.parts_totals.map(p=>`<li>${e(p?.name || p?.part_no || '부품 번호 기록 없음')} · 총 필요 ${e(n(p?.qty,'개'))} · 실제 가용 ${e(n(p?.available,'개'))}</li>`).join('')+'</ul>'+UI.fold('전체 부품 근거 원문',`<pre>${e(JSON.stringify(plan.parts_totals,null,2))}</pre>`,{cls:'small'});
    return html;
  };
  W.maintenanceReceiptSummary = receipt => {
    const after=receipt?.after, plan=after?.plan, orders=Array.isArray(after?.orders) ? after.orders : [];
    const complete=orders.length && orders.every(o=>o && typeof o.asset==='string' && typeof o.ref==='string' && o.ref && typeof o.status==='string');
    if(!complete) return '설비별 정비 오더 영수증 기록을 확인할 수 없습니다. 계획만으로 생성이나 정비 완료를 판단하지 않습니다.';
    if(plan?.scope==='bundle' && (!Array.isArray(plan.assets) || plan.assets.length!==2 || orders.length!==2 || !plan.assets.every(a=>orders.some(o=>o.asset===a.asset)))) return '두 설비 계획과 실제 오더 영수증 범위가 다릅니다. 두 대의 등록 완료로 판단하지 않습니다.';
    if(orders.every(o=>['취소됨','취소'].includes(o.status))) return `대상 ${orders.length}대의 정비 오더 취소 상태가 영수증에 기록되었습니다. 정비 수행 완료와는 별도입니다.`;
    return `정비 시스템에 대상 ${orders.length}대의 오더 영수증이 기록되었습니다. 오더 등록과 정비 완료는 별도로 확인합니다.`;
  };
  W.maintenanceReceiptHtml = receipt => {
    const after=receipt?.after;
    if(!after || !Object.prototype.hasOwnProperty.call(after,'plan') && !Object.prototype.hasOwnProperty.call(after,'orders')) return '';
    const e=UI.esc || esc, orders=Array.isArray(after.orders) ? after.orders : [];
    const states={'배정됨':'배정됨','완료':'완료','취소됨':'취소됨','취소':'취소',DONE:'처리 완료',FAILED:'처리 실패',PENDING:'대기 중'};
    return `<p><b>${e(W.maintenanceReceiptSummary(receipt))}</b></p>`+
      (after.plan ? `<h4>실행 영수증에 남긴 정비 계획</h4>${W.maintenanceScopeHtml(after.plan)}` : '<p>영수증의 정비 계획 기록 없음</p>')+
      (orders.length ? '<div data-pm-orders><h4>설비별 실제 오더 기록</h4><ul>'+orders.map(o=>{
        if(!o || typeof o!=='object') return '<li>설비별 영수증 정보 읽기 실패</li>';
        const name=typeof o.asset==='string' && /^HYD-\d+$/.test(o.asset) ? o.asset : UI.names?.[o.asset] || '설비 표시 이름 기록 없음';
        const status=Object.prototype.hasOwnProperty.call(states,o.status) ? states[o.status] : '오더 상태 표시 정보 없음';
        const p=o.package, n=v=>typeof v==='number' && Number.isFinite(v) ? `${W.num(v)}시간` : '기록 없음';
        const modes={reserve:'예약 · 실물 출고와 별도',issue:'실물 출고 · 정비 완료와 별도',preserve:'기존 할당 유지 · 새 예약이나 재출고 아님'}, mode=after.plan?.stock_effect;
        return `<li><b>${e(name)} · ${e(o.ref || '오더 번호 기록 없음')} · ${e(status)}</b>${p ? '<p>'+e(p.package_name || '정비 묶음 이름 기록 없음')+' · 이번 정비 차례 누적 기준 '+e(n(p.next_due_total_h))+' · 패키지 간격 '+e(n(p.package_interval_h))+'</p>' : '<p>오더별 패키지 근거 기록 없음</p>'}<p>영수증에 기록된 부품 처리 방식: ${e(Object.prototype.hasOwnProperty.call(modes,mode) ? modes[mode] : '기록 없음 · 예약이나 출고를 추정하지 않습니다.')}</p>${o.window_starts_at ? '<p>정비 시작 시각 '+e(UI.dateTime(o.window_starts_at))+'</p>' : '<p>정비 시작 시각 기록 없음</p>'}</li>`;
      }).join('')+'</ul></div>' : '<p>설비별 실제 오더 기록 없음</p>')+
      UI.fold('정비 오더 영수증 원문',`<pre>${e(JSON.stringify(receipt,null,2))}</pre>`,{cls:'small'});
  };
  W.unit = key => { const k = String(key || ''); const f = F[k] || F[k.toLowerCase()]; return f ? f[1] : ''; };
  W.known = key => !!(F[key] || F[String(key || '').toLowerCase()]);
  const STATES = { REMOTE_AUTO: '원격 자동', REMOTE_MANUAL: '원격 수동', LOCAL: '현장 제어', RUN: '운전 중', STOP: '정지', TRIP: '보호 정지', PASS: '통과', DONE: '완료' };
  W.num = v => {
    if (typeof v !== 'number' || !Number.isFinite(v)) return v;
    const a = Math.abs(v);
    return v.toLocaleString('ko-KR', { maximumFractionDigits: a >= 100 ? 0 : a >= 10 ? 1 : a >= 1 ? 2 : 3 });
  };
  // 값 하나를 화면 말로: 숫자는 자릿수 · 단위, 참거짓은 예 · 아니요, 상태 코드는 한국어, id 는 이름
  W.value = (key, v) => {
    if (v == null || v === '') return '–';
    if (v === true) return '예';
    if (v === false) return '아니요';
    if (typeof v === 'number') { const u = W.unit(key); return `${W.num(v)}${u ? ' ' + u : ''}`; }
    if (typeof v === 'string') {
      if(key==='package_semantics' && v==='base_interval_configuration') return '등록된 기본 정비 설정 · 이번 차례 패키지 선택 아님';
      if (/^\d{4}-\d\d-\d\dT/.test(v)) return UI.dateTime(v);
      if (STATES[v]) return STATES[v];
      if (key === 'pattern' || /^[A-Z][A-Z_]+$/.test(v) && W.pattern(v) !== v) return W.pattern(v);
      return W.text(v);
    }
    if (Array.isArray(v)) return `${v.length}건`;
    return '…';
  };

  /* ---------------------------------------------------------------- 경보 패턴 · 규칙 식 */
  const PATTERNS = { PM_DUE: '정기 정비 도래', SPARE_BELOW_MIN: '예비품 재고 기준 이탈' };
  /* 원인 이름표 — 판단 origin.cause_route(dmn-mcp 가 실제로 원인을 받아 준 근거). 센서 진단(증상 → 고장 유형 ← 원인)이 아닌 업무 경보의
     원인은 고장 판정이 아니라 "왜 이 부품인가"(재고: 부품 → 그 부품이 고치는 원인) · "왜 이 정비인가"(정기 정비: 정비가 막는 고장의 원인)다.
     칸이 없는 판단(이 칸 이전 기록)은 진단 이름표 — 그때 판단 기록은 모두 진단 근거 문장으로 적혔다. 모르는 값은 지어내지 않고 실패한다. */
  const CAUSE_WORDS = {
    diagnosis: { cause: '원인', failureMode: '고장 유형', found: c => `원인을 ‘${c}’${W.josa(c, '으로/로')} 보고`, input: null, inputFm: null },
    part: { cause: '이 부품이 고치는 원인', failureMode: '그 원인이 일으키는 고장', found: c => `이 부품이 고치는 원인 ‘${c}’${W.josa(c, '을/를')} 찾고`,
            input: '이 부품이 고치는 원인', inputFm: '그 원인이 일으키는 고장' },
    prevention: { cause: '정기 정비로 막는 원인', failureMode: '정기 정비로 막는 고장', found: c => `정기 정비로 막는 원인 ‘${c}’${W.josa(c, '을/를')} 찾고`,
                  input: '정기 정비로 막는 원인', inputFm: '정기 정비로 막는 고장' },
  };
  W.causeWords = route => {
    if (route == null) return CAUSE_WORDS.diagnosis;
    if (!CAUSE_WORDS[route]) throw new Error(`판단 origin.cause_route 를 모릅니다: ${route}`);
    return CAUSE_WORDS[route];
  };
  W.startValue = (key,value) => {
    if (value==null || value==='') return '값 없음';
    if (['incident','alert_id','alertId'].includes(key)) return `${key==='incident' ? '사건' : '경보'} 식별값 있음 · 원문 확인`;
    if (key==='pattern') { const label=W.pattern(value); return label===value ? '경보 패턴 표시 이름 기록 없음 · 원문 확인' : label; }
    return W.value(key,value);
  };
  W.pattern = code => (typeof PATTERN_LABEL !== 'undefined' && PATTERN_LABEL[code]) || PATTERNS[code] || UI.idText(code || '');
  const OPS = { '>': '보다 높음', '>=': '이상', '<': '보다 낮음', '<=': '이하', '==': '같음', '!=': '다름' };
  W.op = op => OPS[op] || op;
  W.sym = op => ({ '>=': '≥', '<=': '≤', '==': '=', '!=': '≠' })[op] || op;
  // "TS1 > 55 and CE < 70 and slope(TS1) > 0" → "유온 > 55 ℃ 그리고 냉각 효율 < 70 % 그리고 유온 오르는 중"
  // 설비 태그: 센서(TS1 · PS1 …) · 냉각 효율(CE) · 구동 설정값(LoadSP · FanSpeedSP · ValveSP, it/neo4j/v2/instances.cypher 의 Actuator resource)
  const TAG = String.raw`[A-Z]{2,3}\d|CE|LoadSP|FanSpeedSP|ValveSP`;
  W.rule = expr => {
    if (!expr) return '';
    return String(expr)
      .replace(/PLC\.state\s*==\s*'(\w+)'/g, (m, st) => `설비 상태 ${STATES[st] || st}`)
      .replace(/slope\((\w+)\)\s*>\s*0(?:\.0+)?/gi, (m, t) => `${W.fieldName(t.toLowerCase())} 오르는 중`)
      .replace(/slope\((\w+)\)\s*<=\s*0(?:\.0+)?/gi, (m, t) => `${W.fieldName(t.toLowerCase())} 더 오르지 않음`)
      .replace(new RegExp(String.raw`\b(${TAG})\s*(>=|<=|>|<|==)\s*(-?[\d.]+)`, 'g'), (m, t, op, n) => `${W.fieldName(t.toLowerCase())} ${op} ${n}${W.unit(t.toLowerCase()) ? ' ' + W.unit(t.toLowerCase()) : ''}`)
      .replace(new RegExp(String.raw`\b(${TAG})\b`, 'g'), t => W.fieldName(t.toLowerCase()))
      .replace(/\s+and\s+/gi, ' 그리고 ').replace(/\s+or\s+/gi, ' 또는 ').replace(/>=/g, '≥').replace(/<=/g, '≤');
  };
  // 기준 [tag, op, limit] → "유온 < 55 ℃"
  W.criterion = c => Array.isArray(c) && c.length === 3 ? `${W.fieldName(String(c[0]).toLowerCase())} ${W.sym(c[1])} ${W.num(c[2])}${W.unit(String(c[0]).toLowerCase()) ? ' ' + W.unit(String(c[0]).toLowerCase()) : ''}` : '';

  /* ---------------------------------------------------------------- 실행 코드 (승인 뒤 시스템이 하는 일) */
  const CODES = {
    FAN_SET: ['쿨러 팬 속도', '%'], LOAD_SET: ['펌프 부하', '%'], PUMP_SELECT: ['펌프 전환', ''], WO_CREATE: ['작업지시 등록', ''], WO_RESCHEDULE: ['기존 정비 오더 일정 변경', ''], WO_COMPLETE: ['작업지시 완료', ''],
    PR_CREATE: ['ERP 발주', ''], GR_CONFIRM: ['입고 · 검수', ''], PM_RESET: ['운전시간 계수기 리셋', ''], MAIL: ['메일', ''],
  };
  W.code = c => (CODES[c] || [c])[0];
  // {code, value} 또는 {code, load_pct: 70} → "펌프 부하 70 %"
  W.action = a => {
    if (!a) return '';
    const spec = CODES[a.code];
    const val = a.value != null ? a.value : a.load_pct != null ? a.load_pct : a.fan_pct != null ? a.fan_pct : a.pump != null ? a.pump : null;
    if (!spec) return `${a.name || a.code}${val != null ? ' ' + val : ''}`;
    if (spec[1] && val != null) return `${spec[0]} ${val} ${spec[1]}`;
    return val != null && !/^(sup|SOP)/.test(String(val)) ? `${spec[0]} ${UI.idText(val)}` : spec[0];
  };

  /* ---------------------------------------------------------------- 도구 (무엇을 물었고 무엇을 받았나) */
  const unescapeU = s => String(s).replace(/\\u([0-9a-fA-F]{4})/g, (m, h) => String.fromCharCode(parseInt(h, 16)));
  function parse(x) {
    if (x == null) return null;
    if (typeof x !== 'string') {
      if (Array.isArray(x) && x.length && x.every(y => y && y.type === 'text' && typeof y.text === 'string')) return parse(x.map(y => y.text).join('\n'));
      return x;
    }
    const t = x.trim();
    if (/^[[{]/.test(t)) { try { return JSON.parse(t); } catch (_) { return t; } }
    return t;
  }
  const doc = o => (o && typeof o === 'object' && !Array.isArray(o) && 'document' in o) ? o.document : o;
  const nm = id => W.idName(id);
  const list = (arr, n = 3) => arr.filter(Boolean).slice(0, n).join(', ') + (arr.filter(Boolean).length > n ? ` 외 ${arr.filter(Boolean).length - n}` : '');
  const factsLine = (o, n = 4) => Object.entries(o || {}).filter(([k, v]) => W.known(k) && v != null && typeof v !== 'object').slice(0, n).map(([k, v]) => `${W.fieldName(k,o)} ${W.value(k, v)}`).join(' · ');
  const PURCHASE_TOOLS = new Set(['purchase_context','evaluate_purchase','submit_purchase']);
  W.purchaseTool = raw => {
    const key=UI.toolKey(raw), name=key.startsWith('mcp__hyd-dmn__') ? key.slice('mcp__hyd-dmn__'.length) : key;
    return PURCHASE_TOOLS.has(name) ? name : '';
  };
  function purchaseRecord(output) {
    let value=parse(output);
    if (value?.structured_content || value?.structuredContent) value=parse(value.structured_content || value.structuredContent);
    else if (Array.isArray(value?.content)) value=parse(value.content);
    return value;
  }
  W.purchaseFailed = output => { const record=purchaseRecord(output); return record?.result==='error' || doc(record)?.status==='FAILED'; };
  const purchasePart = part => part && typeof part === 'object' ? [part.name && part.name !== part.id ? part.name : (W.idName(part.id)!==part.id ? W.idName(part.id) : '부품 표시 이름 기록 없음'),part.partNo].filter(Boolean).join(' · ') : '';
  function purchaseQuote(option) {
    const resolved=option?.resolvedSupplier;
    if (!resolved || typeof resolved!=='object') return '';
    const policies={oem:'정본 순정 견적',lowest_approved:'승인된 비순정 최저가',fastest_quote:'전체 견적 최단 납기'};
    const policy=Object.prototype.hasOwnProperty.call(policies,resolved.policy) ? policies[resolved.policy] : '선정 정책 기록 확인 필요';
    const quote=resolved.quote || {}, label=quote.name || resolved.classificationLabel;
    const supplier=label && label!==resolved.id ? label : '공급사 표시 이름 기록 없음';
    return [policy,supplier,typeof quote.price==='number' ? `단가 ${W.num(quote.price)}만원` : '',typeof quote.lead_d==='number' ? `납기 ${W.num(quote.lead_d)}일` : '',quote.avl===true ? '등록 AVL 통과' : quote.avl===false ? '등록 AVL 미통과' : 'AVL 기록 미확인'].filter(Boolean).join(' · ');
  }
  W.purchaseQuote = purchaseQuote;
  W.purchaseEconomics = option => {
    const c=option?.economicComparison;
    if (!c || typeof c!=='object' || Array.isArray(c)) return null;
    return c;
  };
  const costValue = v => typeof v==='number' && Number.isFinite(v) ? `${v.toLocaleString('ko-KR',{maximumFractionDigits:20})}만원` : '금액 기록 미확인';
  W.purchaseCostLabel=option=>`비교 총비용 ${costValue(option?.economicComparison?.total_cost)}`;
  W.purchaseCostSummary = option => {
    const c=W.purchaseEconomics(option);
    return c ? `발주 금액 ${costValue(c.purchase_amount)} · 기대 불량 비용 ${costValue(c.expected_failure_cost)} · 전수 검사 비용 ${costValue(c.inspection_cost)} · 비교 총비용 ${costValue(c.total_cost)}` : '';
  };
  W.purchaseCostDiff = (option,recommended) => {
    const a=W.purchaseEconomics(option), b=W.purchaseEconomics(recommended);
    if (!a || !b || typeof a.total_cost!=='number' || typeof b.total_cost!=='number' || !Number.isFinite(a.total_cost) || !Number.isFinite(b.total_cost)) return '';
    const difference=a.total_cost-b.total_cost;
    return difference===0 ? '비교 총비용 같음 · 순위 구분 사유는 원문 확인' : `추천안보다 비교 총비용 ${difference>0 ? '높음' : '낮음'} · ${costValue(a.total_cost)} (추천 ${costValue(b.total_cost)})`;
  };
  W.purchaseContextHtml = (option, decision = {}) => {
    if (!(option?.actions || []).some(a=>a.code==='PR_CREATE')) return '';
    const values={...(decision.facts || {}),...(option.facts || {})}, part=decision.origin?.part, comparison=W.purchaseEconomics(option);
    const rows=[['구매 대상 부품',purchasePart(part) || (values.part_no || values.spare_part_no ? `부품 번호 ${values.part_no || values.spare_part_no}` : '부품 근거 기록 없음')],
      ...['need_qty','po_amount','lead_slack_days'].filter(k=>values[k]!=null && !(comparison && ['po_amount','need_qty'].includes(k))).map(k=>[W.fieldName(k),W.value(k,values[k])]),
      ['공급사 선정 근거',purchaseQuote(option).replace('등록 AVL 통과','등록 승인 공급사 검사 통과').replace('등록 AVL 미통과','등록 승인 공급사 검사 미통과').replace('AVL 기록 미확인','승인 공급사 검사 기록 미확인') || '공급사 선정 근거 기록 없음 · 현재 값으로 추정하지 않습니다.']];
    if (comparison) {
      rows.push(['필요 수량',typeof comparison.quantity==='number' ? `${W.num(comparison.quantity)}개` : '수량 기록 미확인'],['견적 단가',costValue(comparison.unit_price)]);
      rows.push(...[['발주 금액','purchase_amount'],['기대 불량 비용','expected_failure_cost'],['전수 검사 비용','inspection_cost'],['비교 총비용','total_cost']].map(([label,key])=>[label,costValue(comparison[key])]));
      rows.push(['견적 불량률',typeof comparison.fail_rate==='number' && Number.isFinite(comparison.fail_rate) ? `${W.num(comparison.fail_rate*100)} %` : '기록 미확인']);
      const policy=comparison.policy || {};
      rows.push(['원문 비용 기준',`불량 1개당 손실 ${costValue(policy.loss_per_failure)} · 검사 기준 ${typeof policy.inspection_threshold==='number' ? W.num(policy.inspection_threshold*100)+' % 초과' : '기록 미확인'} · 전수 검사비 ${costValue(policy.inspection_cost)}`]);
    } else rows.push(['구매 총비용 비교','비교 기록 없음 · 발주 금액만으로 총비용을 추정하지 않습니다.']);
    return `<section class="ap-business" aria-label="구매 요청"><b>구매 요청</b><dl class="meta-list">${rows.map(([label,value])=>`<div><dt>${esc(label)}</dt><dd>${esc(value)}</dd></div>`).join('')}</dl><p class="muted">구매요청 계획 · 승인 · 발주 완료 아님</p>${UI.fold('구매요청 근거 원문',`<pre>${esc(JSON.stringify({part:part || null,facts:values,resolvedSupplier:option.resolvedSupplier || null,economicComparison:option.economicComparison || null,actions:option.actions},null,2))}</pre>`,{cls:'small'})}</section>`;
  };
  W.purchaseAsk = (name, input) => {
    const i=parse(input) || {}, use=name==='purchase_context' ? 'ERP 부족 재고와 원문 구매 절차 확인' : name==='evaluate_purchase' ? '구매 후보 비교 · 조회와 계산만' : '현재 처리 건에 구매 판단 등록 요청 · 승인과 실행 아님';
    return [i.asset,i.part_no ? `부품 번호 ${i.part_no}` : '부품 번호 기록 없음',use,name==='evaluate_purchase' && i.overrides && Object.keys(i.overrides).length ? '가정값을 넣은 비교' : ''].filter(Boolean).join(' · ');
  };
  W.purchaseGot = (name, output) => {
    const record=purchaseRecord(output);
    if (record?.result==='error') return `구매 도구가 요청을 거절하거나 처리하지 못했습니다${record.message ? ' · '+W.text(record.message) : ''}`;
    const d=doc(record);
    if (!d || typeof d!=='object' || Array.isArray(d)) return '구매 결과 기록을 확인할 수 없습니다. 원문을 확인하세요.';
    if (name==='purchase_context') {
      if (!d.part || typeof d.part!=='object' || Array.isArray(d.part) || typeof d.part.id!=='string' || !d.part.id || typeof d.part.partNo!=='string' || !d.part.partNo || !Array.isArray(d.procedures)) return '구매 부품 근거 결과 형식을 확인하세요. 원문은 상세에 보존되어 있습니다.';
      const execution=d.procedures.filter(p=>p?.executable===true).length, reference=d.procedures.filter(p=>p?.executable===false).length;
      const unknown=d.procedures.length-execution-reference;
      const titles=list(d.procedures.map(p=>p?.name && p.name!==p.id ? p.name : '절차 표시 이름 기록 없음'),3);
      return [purchasePart(d.part),`원문 구매 절차 ${d.procedures.length}개`,titles,`실행 후보 검토 대상 ${execution}개`,`참고 보관 ${reference}개`,unknown ? `사용 방식 기록 미확인 ${unknown}개` : '', 'ERP 부족부품과 등록 부품의 근거 조회 · 판단 등록 없음'].filter(Boolean).join(' · ');
    }
    if (!d.result || !Array.isArray(d.result.options) || d.result.options.some(o=>!o || typeof o!=='object' || Array.isArray(o))) return '구매 후보 · 판단 결과 형식을 확인하세요. 원문은 상세에 보존되어 있습니다.';
    const options=d.result.options, recommended=d.result.recommended ?? d.recommended;
    const chosen=options.find(o=>o.id===recommended), label=chosen?.name && chosen.name!==chosen.id ? chosen.name : recommended ? (W.idName(recommended)!==recommended ? W.idName(recommended) : '추천 조치 표시 이름 기록 없음') : '';
    const quotes=chosen ? [purchaseQuote(chosen),W.purchaseCostSummary(chosen)].filter(Boolean).join(' · ') : list(options.map(o=>[purchaseQuote(o),W.purchaseCostSummary(o)].filter(Boolean).join(' · ')),3);
    const evidence=[purchasePart(d.origin?.part) || '부품 근거 기록 없음',typeof d.facts?.need_qty==='number' ? `필요 수량 ${W.num(d.facts.need_qty)}개` : '',`구매 후보 ${options.length}개`,options.some(o=>o.feasible===false) ? `규정 등으로 제외 ${options.filter(o=>o.feasible===false).length}개` : '',label ? `추천 ‘${label}’` : '추천 기록 없음',quotes].filter(Boolean);
    if (name==='evaluate_purchase') {
      const state=d.status==='NO_FEASIBLE_OPTION' ? '추천 가능한 구매 후보 없음' : d.status==='REJECTED_BY_GUARDRAIL' ? '검사 규칙으로 구매 판단 중단' : d.status==='EVALUATED' ? '후보 비교 완료' : '후보 비교 상태 기록 확인 필요';
      return [state,'조회 · 계산 결과이며 판단 등록 · 승인 · 실행 아님',...evidence].join(' · ');
    }
    const registered=d.status==='SUBMITTED' && typeof d.id==='string' && !!d.id;
    return [registered ? '구매 판단 등록됨' : '구매 판단 등록 완료 기록 없음','사람 승인 · ERP 실행 완료 아님',...evidence].join(' · ');
  };
  // 지식 그래프 질의 → 사람 말 (무엇과 연결된 무엇을 찾았나)
  function cypherAsk(q) {
    const s = String(q || '');
    const ids = [...s.matchAll(/id\s*[:=]\s*['"]([^'"]+)['"]/g)].map(m => nm(m[1]));
    const labels = [...s.matchAll(/\(\w*:(\w+)/g)].map(m => m[1]);
    const rels = [...s.matchAll(/\[:?(\w*):?([A-Z_]+)\]/g)].map(m => m[2]);
    const LBL = { Skill: '조치 방법', Role: '승인 역할', Incident: '사건', Cause: '원인', FailureMode: '고장 유형', Symptom: '증상', Part: '부품', Measure: '성과 지표', Rule: '규칙', Manual: '매뉴얼' };
    const REL = { APPROVED_BY: '승인 역할', ADDRESSES: '다루는 원인', RAISED_BY: '경보로 열린 사건', MITIGATED_BY: '완화 조치', REMEDIED_BY: '근본 조치', PREVENTED_BY: '예방 조치', INVOLVES_PART: '쓰는 부품', AFFECTS: '영향' };
    if (/\bdb\.index\.fulltext\.queryNodes\s*\(/i.test(s)) return '지식의 이름·본문 검색';
    if (ids.length) return `‘${list(ids, 2)}’와 연결된 것`;
    if (/\$ids|\$id/.test(s) && labels.length) return `${list(labels.map(l => LBL[l]).filter(Boolean), 2)}${rels.length ? '의 ' + list(rels.map(r => REL[r]).filter(Boolean), 2) : ''}`;
    if (labels.length) return list(labels.map(l => LBL[l]).filter(Boolean), 3);
    return '지식 그래프 조회 · 조회 목적 기록 없음 · 원문 확인';
  }
  function rowsGot(o) {
    const v = doc(purchaseRecord(o));
    const rows = Array.isArray(v) ? v : Array.isArray(v?.rows) ? v.rows : Array.isArray(v?.records) ? v.records : null;
    if (rows) {
      const names=rows.map(r=>r && typeof r==='object' ? r.name || r['s.name'] || r.title : '').filter(x=>typeof x==='string' && /[가-힣]/.test(x));
      return `${rows.length}건${names.length ? ' · '+list([...new Set(names)],3) : ''}`;
    }
    return '';
  }
  const purposeLabel = label => `${label} · 조회 목적 기록 없음 · 원문 확인`;
  function sqlAsk() { return purposeLabel('업무 DB 조회'); }
  function shellAsk(i) {
    if (typeof i==='object' && typeof i.description==='string' && /[가-힣]/.test(i.description) && !/\b(?:SELECT|MATCH|CALL)\b|[A-Za-z]+_[A-Za-z_]+/.test(i.description)) return i.description;
    const original=typeof i==='string' ? i : i?.command;
    if(typeof original!=='string')return purposeLabel('명령 실행');
    let command=original.trim();
    const wrapper=/^"[^"]*powershell\.exe"\s+-Command\s+"([\s\S]*)"$/i.exec(command);
    if(wrapper)command=wrapper[1];
    // Only the observed read-command contract is described. Compound or unknown
    // scripts remain unknown; parsing never executes or rewrites the original.
    if (/^Get-Content\b/i.test(command) && !/[\r\n;|`]|&&|\$\(/.test(command)) {
      const path=/-LiteralPath\s+['"]([^'"]+)['"]/i.exec(command)?.[1];
      const purpose=path==='context/task.json' ? '처리 건의 작업 입력' : path?.endsWith('/SKILL.md') ? '스킬 문서 · 등록 여부는 전달 기록 확인' : '파일 목적 기록 없음 · 원문 확인';
      return '파일 본문 읽기 요청 · '+purpose;
    }
    return purposeLabel('명령 실행');
  }
  function genericGot(output) {
    const v=doc(purchaseRecord(output)), rows=rowsGot(output);
    if (rows) return rows;
    if (v==null) return '반환값 없음 · 조회 결과 건수 미확인';
    if (typeof v==='string') return v.length ? `반환 본문 ${v.length}자 · 결과 의미 기록 없음 · 원문 확인` : '반환 본문 없음 · 조회 결과 건수 미확인';
    if (typeof v==='number') return `반환값 ${W.num(v)}`;
    if (typeof v==='boolean') return `반환값 ${v ? '참' : '거짓'}`;
    const known=factsLine(v?.facts || v);
    return known || '결과 형식의 표시 정보 없음 · 원문 확인';
  }
  const TOOLS = {
    'mcp__codex__list_mcp_resources': {name:'참고 자료 목록 조회', minor:true},
    'mcp__codex__list_mcp_resource_templates': {name:'참고 자료 형식 조회', minor:true},
    ToolSearch: { name: '쓸 도구 불러오기', minor: true, ask: i => list(String(i.query || '').replace(/^select:/, '').split(',').map(t => W.toolName(t.trim())), 4), got: o => Array.isArray(o) ? `${o.length}개 준비됨` : '' },
    Write: { name: '파일 쓰기', minor: true, ask: i => UI.baseName(i.file_path || ''), got: () => '썼음' },
    Edit: { name: '파일 고치기', minor: true, ask: i => UI.baseName(i.file_path || ''), got: () => '고침' },
    Read: { name: '파일 읽기', minor: true, ask: i => UI.baseName(i.file_path || '') },
    Bash: { name: '명령 실행', minor: true, ask: shellAsk },
    Glob: { name: '파일 찾기', minor: true, ask: i => i.pattern || '' }, Grep: { name: '내용 찾기', minor: true, ask: i => i.pattern || '' },
    Skill: { name: '스킬 읽기', ask: i => i.skill || i.name || '' },
    'mcp__neo4j__read_neo4j_cypher': { name: '지식 그래프 조회', sys: '지식 그래프', ask: i => cypherAsk(i.query), got: rowsGot },
    'mcp__neo4j__get_neo4j_schema': { name: '지식 그래프 구조 보기', sys: '지식 그래프', ask: () => '어떤 종류의 노드 · 관계가 있나' },
    'mcp__hyd-dmn__diagnose': { name: '원인 진단', sys: '판단 엔진', ask: i => `${i.asset || ''} ‘${W.pattern(i.pattern)}’ 경보의 원인`,
      got: o => { const d = doc(parse(o)) || {}; const c = (d.causes || []).find(x => x.id === d.topCause) || (d.causes || [])[0]; return c ? `가장 유력한 원인 ‘${c.name}’ (점수 ${W.num(c.score)})` : ''; } },
    'mcp__hyd-dmn__business_causes': { name: '업무 경보 원인 찾기', sys: '판단 엔진 · 지식 그래프', ask: i => `${i.asset || ''} ‘${W.pattern(i.pattern)}’ 경보의 원인`,
      got: o => { const d = doc(parse(o)) || {}; return [d.cause && `원인 ‘${nm(d.cause)}’`, d.failure_mode && `고장 유형 ‘${nm(d.failure_mode)}’`, d.part && `부품 ${nm(d.part)}`].filter(Boolean).join(' · '); } },
    'mcp__hyd-dmn__purchase_context': {name:'구매 부품 근거 조회',sys:'판단 엔진 · ERP · 지식 그래프',ask:i=>W.purchaseAsk('purchase_context',i),got:o=>W.purchaseGot('purchase_context',o)},
    'mcp__hyd-dmn__evaluate_purchase': {name:'구매 후보 비교',sys:'판단 엔진',ask:i=>W.purchaseAsk('evaluate_purchase',i),got:o=>W.purchaseGot('evaluate_purchase',o)},
    'mcp__hyd-dmn__submit_purchase': {name:'구매 판단 등록 (승인 · 실행 아님)',sys:'판단 엔진 → 처리 건',ask:i=>W.purchaseAsk('submit_purchase',i),got:o=>W.purchaseGot('submit_purchase',o)},
    'mcp__hyd-dmn__timeseries_query': { name: '센서 기록 조회', sys: '센서 기록 DB', ask: sqlAsk },
    'mcp__hyd-dmn__timeseries_schema': { name: '센서 기록 구조 보기', sys: '센서 기록 DB' },
    'mcp__hyd-dmn__dmn_rules': { name: '판단 규칙표 보기', sys: '판단 엔진', ask: i => nm(i.decision || ''),
      got: o => { const d = doc(parse(o)); return Array.isArray(d) && d[0] ? `‘${d[0].decisionName || nm(d[0].decision)}’ 규칙 ${(d[0].rules || []).length || d.length}개` : ''; } },
    'mcp__hyd-dmn__evaluate_cards': { name: '대안 평가 (후보 · 규정 · 득실 · 순위)', sys: '판단 엔진', ask: i => [i.asset, nm(i.failure_mode || ''), nm(i.cause || '')].filter(Boolean).join(' · ') },
    'mcp__hyd-dmn__gather_facts': { name: '판단 사실 모으기', sys: '판단 엔진', ask: i => [i.asset, nm(i.failure_mode || '')].filter(Boolean).join(' · '),
      got: o => factsLine((doc(parse(o)) || {}).facts) },
    'mcp__hyd-dmn__precedents': { name: '과거 선택 조회', sys: '판단 엔진', ask: i => nm(i.failure_mode || ''),
      got: o => { const d = doc(parse(o)); return Array.isArray(d) ? `${d.length}건 · ${list(d.map(x => nm(x.skill)), 2)}` : ''; } },
    'mcp__hyd-dmn__submit_decision': { name: '판단 제출', sys: '판단 엔진', ask: i => i.recommended ? `추천 ‘${nm(i.recommended)}’` : (i.asset || ''),
      got: o => { const d = doc(parse(o)) || {}; return d.id ? `판단 ${d.id} 저장${d.recommended ? ` · 추천 ‘${nm(d.recommended)}’` : ''}` : ''; } },
    'mcp__hyd-dmn__forecast_actions': { name: '조치 효과 예측', sys: '판단 엔진' },
    'mcp__hyd-dmn__tradeoffs': { name: '성과 지표 득실 경로', sys: '판단 엔진 · 지식 그래프' },
    'mcp__hyd-dmn__inputs': { name: '판단 입력 보기', sys: '판단 엔진' },
    'mcp__enterprise__mes_orders': { name: '생산 주문 조회', sys: '생산 시스템 (MES)', ask: i => i.asset || '', got: o => factsLine((doc(parse(o)) || {}).facts) },
    'mcp__enterprise__erp_contract': { name: '계약 조회', sys: 'ERP', ask: i => i.asset || '', got: o => factsLine((doc(parse(o)) || {}).facts) },
    'mcp__enterprise__erp_inventory': { name: '완제품 재고 조회', sys: 'ERP', ask: i => i.asset || '', got: o => factsLine((doc(parse(o)) || {}).facts) },
    'mcp__enterprise__query': { name: '업무 DB 질의', sys: '업무 DB', ask: sqlAsk, got: rowsGot },
    'mcp__hyd-effects__send_mail': { name: '메일 보내기', sys: '메일', ask: i => `${i.to || ''}${i.subject ? ` · 제목 ‘${i.subject}’` : ''}`, got: () => '보냄' },
  };
  // 업무 MCP 는 서버가 셋(전부 · 정비용 · 구매용)이라 도구 이름으로 한 번 더 찾는다
  const BIZ = {
    pm_status: { name: '정비 계수기 · 계획 조회', sys: '정비 시스템 (CMMS)' }, maintenance_windows: { name: '정비 시간 계획 조회', sys: '정비 시스템 (CMMS)' },
    cmms_history: { name: '정비 이력 조회', sys: '정비 시스템 (CMMS)' }, mes_orders: TOOLS['mcp__enterprise__mes_orders'], spare_stock: { name: '예비품 재고 조회', sys: 'ERP' },
    part_quotes: { name: '공급사 견적 조회', sys: '공급망 (SCM)' }, scm_suppliers: { name: '공급사 조회', sys: '공급망 (SCM)' },
    erp_contract: TOOLS['mcp__enterprise__erp_contract'], erp_inventory: TOOLS['mcp__enterprise__erp_inventory'], query: TOOLS['mcp__enterprise__query'],
  };
  function spec(raw) {
    const t = UI.toolKey(raw);
    if (TOOLS[t]) return TOOLS[t];
    const m = /^mcp__([^_]+(?:[-_][^_]+)*?)__(.+)$/.exec(t);
    if (m && /^enterprise/.test(m[1]) && BIZ[m[2]]) return Object.assign({ ask: i => i.asset || i.part || '', got: o => factsLine((doc(parse(o)) || {}).facts) || rowsGot((doc(parse(o)))) }, BIZ[m[2]], { sys: BIZ[m[2]].sys || SERVERS[m[1]] });
    if (m) return { name:UI.toolName(raw), sys:SERVERS[m[1]] || '도구 서버 표시 이름 미등록' };
    return { name:UI.toolName(raw) };
  }
  W.toolName = raw => spec(raw).name;
  W.toolSystem = raw => spec(raw).sys || '';
  W.minorTool = raw => !!spec(raw).minor;
  // 물은 것 한 줄
  W.ask = (raw, input) => {
    const s = spec(raw), i = parse(input) || {};
    // 사전이 모양을 모르면 아래 일반 요약(원래 값은 화면의 "물은 원문"에 그대로 있다). 사전 결함은 콘솔에 도구 이름과 함께 남긴다
    try { if (s.ask) { const a = s.ask(i); if (a) return UI.clean(a); } } catch (err) { console.warn('[hydWords] 물음 요약 실패', raw, err); }
    const facts=typeof i==='object' ? factsLine(i,3) : '';
    return facts || '도구 요청 목적 기록 없음 · 원문 확인';
  };
  // 받은 것 한 줄 (잘림 · 막힘 · 실패는 상태로 따로)
  W.got = (raw, output) => {
    const s = spec(raw);
    try { if (s.got) { const g = s.got(output); if (g) return UI.clean(g); } } catch (err) { console.warn('[hydWords] 받음 요약 실패', raw, err); }
    return genericGot(output);
  };

  /* ---------------------------------------------------------------- id → 이름: 이 처리 건이 아는 이름(판단 · 진단 카드 · 역할) → 사전(names.json) → 종류 + 꼬리
     사전에 아직 없는 id(새로 적재한 시나리오의 조치 · 역할)도 원래 id 를 그대로 드러내지 않는다. 원래 id 는 "원래 이름 보기"에서. */
  const KIND = { cause: '원인', skill: '조치', fm: '고장 유형', sv: '상태 값', msr: '성과 지표', role: '역할', sup: '공급사', part: '부품', rule: '규칙', evd: '증거',
    pattern: '경보 패턴', sys: '시스템', dec: '판단 규칙', sym: '증상', action: '동작', actr: '구동부', sen: '센서', comp: '부품', asset: '설비', dept: '부서', user: '사용자' };
  W.caseNames = {};
  W.idName = id => {
    if (id == null || id === '') return '';
    const k = String(id);
    if (W.caseNames[k]) return W.caseNames[k];
    if (UI.names && UI.names[k]) return UI.names[k];
    if (UI.performers && UI.performers[k]) return UI.performers[k];
    const m = /^([a-z]+):(.+)$/.exec(k);
    if (m && KIND[m[1]]) return `${KIND[m[1]]} 표시 이름 미등록`;
    return k;
  };
  W.text = t => UI.words(String(t ?? '').replace(UI.ID_RE, m => W.idName(m)));

  /* ---------------------------------------------------------------- 조사: 앞말 끝소리로 고른다 ("발주를" · "씰 마모를" · "WO-1009-E85A를" · "김운전이")
     pair = '을/를' · '이/가' · '은/는' · '과/와' · '으로/로'. 끝 글자가 한글 · 숫자 · 영문이 아니면 "을(를)" 처럼 둘 다 쓴다 */
  const DIGIT_FINAL = { 0: 21, 1: 8, 2: 0, 3: 16, 4: 0, 5: 0, 6: 1, 7: 8, 8: 8, 9: 0 };      // 영 · 일 · 이 · 삼 · 사 · 오 · 육 · 칠 · 팔 · 구 의 받침(0 없음, 8 ㄹ)
  const LETTER_FINAL = { L: 8, M: 16, N: 4, R: 8 };                                          // 엘 · 엠 · 엔 · 알 (나머지 영문 이름은 받침 없음)
  function finalOf(word) {
    const c = String(word ?? '').trim().replace(/[\s’'")\]]+$/, '').slice(-1);
    if (!c) return null;
    const code = c.charCodeAt(0);
    if (code >= 0xAC00 && code <= 0xD7A3) return (code - 0xAC00) % 28;
    if (/\d/.test(c)) return DIGIT_FINAL[c];
    if (/[A-Za-z]/.test(c)) return LETTER_FINAL[c.toUpperCase()] || 0;
    if (c === '%' || c === '℃') return 0;                                                    // 퍼센트 · 도
    return null;
  }
  W.josa = (word, pair) => {
    const [withFinal, without] = pair.split('/'), f = finalOf(word);
    if (f == null) return `${withFinal}(${without})`;
    if (withFinal === '으로') return f && f !== 8 ? '으로' : '로';
    return f ? withFinal : without;
  };
  W.who = id => W.caseNames[id] || UI.names?.[id] || UI.performers?.[id] || (/^agent:/.test(id || '') ? 'AI 에이전트' : /^user:/.test(id || '') ? '담당자 (이름 확인 안 됨)' : W.idName(id)) || '–';

  /* ---------------------------------------------------------------- 원래 이름(id) 보이기 */
  W.id = id => W.showIds && id ? ` <code class="cr-id">${esc(id)}</code>` : '';
  W.setShowIds = on => { W.showIds = !!on; try { localStorage.setItem('hyd:record:ids', on ? '1' : '0'); } catch (_) { /* 이 브라우저에서만 */ } };
  W.parse = parse; W.doc = doc;
  window.hydWords = W;
})();
