/* Shared presentation helpers. API identifiers stay unchanged — only on-screen wording lives here.
   A122 (workspace/개발/문서/UIUX_PLAN.md §4 용어 · §5 상태): every user-facing phrase comes from UI.terms,
   every status chip from UI.chip(), every form field from UI.field(). Change the wording here and all screens follow. */
// 포털 전체의 HTML 이스케이프 하나(이 파일이 가장 먼저 실린다 — 다른 화면은 사본을 두지 않는다)
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const UI = {
  toolCallKey(event) {
    return JSON.stringify([event.proc_inst_id ?? null,event.todo_id ?? null,event.job_id ?? null,event.data?.tool_use_id || event.id]);
  },
  evaluationInfo(record, parent) {
    const owns = value => value && typeof value === 'object' && ['evaluation_mode','execution_checked'].some(k => Object.prototype.hasOwnProperty.call(value,k));
    const source = owns(record) ? record : owns(parent) ? parent : {};
    const mode=source.evaluation_mode, checked=source.execution_checked;
    const parentConflict=owns(record) && owns(parent) && (parent.evaluation_mode!==mode || parent.execution_checked!==checked);
    const state=parentConflict ? 'unknown' : mode==='execution' && checked===true ? 'execution' : mode==='rule_analysis' && checked===false ? 'analysis' : mode==='structural' && checked===false ? 'structural' : 'unknown';
    return {state, recorded:owns(source), raw:{evaluation_mode:mode,execution_checked:checked,pattern:source.pattern,execution_notice:source.execution_notice,...(parentConflict ? {parent:{evaluation_mode:parent.evaluation_mode,execution_checked:parent.execution_checked}} : {})}};
  },
  executionBlocked(record, parent) {
    const info=this.evaluationInfo(record,parent);
    // Historical records retain the server's approval compatibility checks.
    return info.recorded && info.state!=='execution';
  },
  evaluationRawHtml(record, parent) {
    const info=this.evaluationInfo(record,parent);
    if(info.state==='execution') return '';
    return this.fold('평가 범위 원문',`<pre>${esc(JSON.stringify(info.raw,null,2))}</pre>`,{cls:'small'}).replace('<details','<details data-evaluation-raw');
  },
  evaluationHtml(record, parent, opt = {}) {
    const info=this.evaluationInfo(record,parent);
    if(info.state==='execution') return '';
    const text=info.state==='analysis' ? '규칙 비교 · 모의 순위 / 실제 승인 · 실행 준비는 확인하지 않음' : info.state==='structural' ? '구조 검사 / 실제 승인 · 실행 준비는 확인하지 않음' : '승인 · 실행 준비 검사 기록 확인 안 됨 · 실행 가능 여부 확인 안 됨';
    return `<div class="muted" role="status" data-evaluation-notice><p>${esc(text)}</p>${opt.raw===false ? '' : this.evaluationRawHtml(record,parent)}</div>`;
  },
  skillLabel(k, historical = false) {
    const raw = k.name || k.skill_name || k.skill || '';
    if (k.title && k.title !== raw && /[가-힣]/.test(k.title)) return {label:k.title, note:'', raw};
    if (k.description && /[가-힣]/.test(k.description)) return {label:k.description, note:historical ? '당시 설명' : '등록 설명', raw};
    return {label:raw || '이름 없는 스킬', note:'', raw};   // 한국어 이름 · 설명이 없으면 등록된 스킬 이름 그대로
  },
  ruleLabel(r) { return this.idText(r.annotation || this.names[r.rule || r.id] || '규칙 표시 이름 미등록'); },
  toolKey(t) {
    const raw=String(t || ''); if(raw==='shell')return 'Bash';
    const alias=/^([^/\s]+)\/([^/\s]+)$/.exec(raw);
    return alias ? `mcp__${alias[1]}__${alias[2]}` : raw;
  },
  // _provided_skills omits written on a verified file; Codex adds prompt
  // delivery after checking registered bytes/hash. Missing metadata is unknown.
  skillDelivery(k) {
    if (k.written === false) return {kind:'failed', label:'작업 폴더에 못 넣음', tone:'danger'};
    if (k.delivery === 'prompt') return {kind:'prompt', label:'프롬프트로 본문 전달', tone:'neutral'};
    if ((k.delivery == null || k.delivery === 'file') && (k.written === true || (k.path && k.sha256))) return {kind:'file', label:'파일 전달', tone:'neutral'};
    return {kind:'unknown', label:'전달 상태 기록 없음', tone:'warning'};
  },
  skillDeliverySummary(entries) {
    const counts = {file:0,prompt:0,failed:0,unknown:0};
    entries.forEach(k => counts[this.skillDelivery(k).kind]++);
    return [['file','파일 전달'],['prompt','프롬프트로 본문 전달'],['failed','전달 실패'],['unknown','전달 상태 기록 없음']]
      .filter(([k])=>counts[k]).map(([k,n])=>`${n} ${counts[k]}개`).join(' · ') || '제공된 스킬 없음';
  },
  /* ---------- 명칭표 (UIUX_PLAN §4) — 화면 문구만. 코드·API·DB 이름은 그대로다. ---------- */
  terms: {
    // 메뉴 · 헤더
    // 화면 이름 nav.<화면>: 메뉴 줄 · 위 막대 · 화면 찾기에 보이는 이름이자 화면 제목(h1)이다 — 한 곳에서 정해 서로 어긋나지 않게 한다. 메뉴 이름은 nav.menu.<메뉴>(index.html 의 주 메뉴 표)
    'nav.main': '홈', 'nav.home': '시스템 구성', 'nav.scenario': '결함 시뮬레이션', 'nav.incidents': '설비 회로', 'nav.trends': '실시간 모니터링',
    'nav.ontology': '지식 지도', 'nav.skills': '조치 방법', 'nav.decision': '규칙 판단', 'nav.process': '업무 시스템 기록', 'nav.instances': '처리 건',
    'nav.knowledge': '문서 등록', 'nav.admin': '관리', 'nav.mcp': '도구 연결',
    'header.services': '서비스', 'header.noResponse': '응답 없음', 'header.connected': '연결됨', 'header.connecting': '연결 중', 'header.waiting': '실시간 연결됨',
    // 공통 단위
    'case': '사건', 'step': '단계', 'agent': 'AI 에이전트', 'system': '시스템',
    'candidate': '조치 후보', 'decision': '결정', 'decisions': '판단 결과', 'method': '조치 방법', 'select': '조치 선택', 'escalate': '책임자 확인',
    'workOrder': '정비 요청', 'command': '설비에 명령', 'control': '설비 제어', 'ack': '설비 응답',
    'alert': '설비 경보', 'closed': '종결', 'done': '완료', 'knowledge': '지식', 'kpi': '성과 지표',
    // 버튼
    'btn.approve': '승인', 'btn.reject': '반려', 'btn.submit': '제출', 'btn.answer': '답변', 'btn.rework': '다시 수행', 'btn.confirm': '확인',
    'btn.preview': '예측 다시 보기', 'btn.effects': '영향 보기', 'btn.reassess': '다시 평가', 'btn.reload': '다시 읽기', 'btn.save': '저장', 'btn.cancel': '변경 취소',
    'btn.run': '모의 판단', 'btn.running': '판단 중…', 'btn.fit': '전체 흐름 보기', 'btn.more': '더 보기',
    'btn.retry': '같은 내용 다시 전달', 'btn.closeTask': '단계 닫기', 'btn.cancelTask': '실행 취소',
    // 폼 라벨
    'form.reason': '사유', 'form.note': '메모', 'form.answer': '답변', 'form.fan': '팬 속도', 'form.load': '펌프 부하', 'form.pump': '운전 펌프',
    'form.section.who': '사유',
    'form.hint.preview': '조치값을 바꿨으면 예측을 다시 본 뒤 결정합니다',
    'form.hint.answer': '답변은 같은 단계에서 이어서 반영됩니다', 'form.pickRole': '역할 선택',
    'form.deadline': '기한',
    'form.err.required': '필수 항목을 입력하세요', 'form.err.reason': '사유를 입력하세요', 'form.err.byRole': '담당자 정보나 승인 기록의 역할을 읽지 못해 보낼 수 없습니다. 화면을 새로 고친 뒤 다시 해 주세요.', 'form.err.byRoleReason': '사유를 입력하세요. 사유를 적었는데도 이 안내가 보이면 화면을 새로 고친 뒤 다시 해 주세요.',
    // 카드 칩
    'chip.recommended': '추천', 'chip.chosen': '결정', 'chip.excluded': '제외', 'chip.control': '설비 제어', 'chip.workOrder': '정비 요청',
    'card.score': '점수', 'card.approver': '승인 역할', 'card.precedent': '과거 같은 선택', 'card.precedentFixed': '미리 넣은 사례 기준', 'card.forecastTs1': '예상 유온', 'card.evidence': '근거 보기', 'card.expected': '예상 영향',
    'card.scoreHow': '점수 계산 방법', 'card.reviewed': '검토한 조치값', 'card.baseSop': '기준 절차', 'card.forecastLimits': '예측 조건과 한계', 'card.steps': '절차',
    'card.penalty': '감점', 'card.warn': '경고', 'card.noAction': '세부 동작 없음',
    'score.bsc': '성과 지표', 'score.forecast': '예측', 'score.warn': '경고', 'score.penalty': '감점', 'score.precedent': '과거 선택', 'score.delivery': '납기', 'score.quality': '품질',
    // 조치 판단 규칙
    'dec.asset': '설비', 'dec.mode': '운전 모드', 'dec.state': '설비 상태', 'dec.fan': '팬 100 % 연속 운전 (시간)', 'dec.standby': '예비 펌프',
    'dec.empty': '설비와 이상 패턴을 고르고 판단을 실행하세요', 'dec.loading': '규칙을 사실에 대어 보는 중…',
    'dec.cause': '원인', 'dec.causeTop': '판정', 'dec.causeMore': '다른 원인 후보', 'dec.candidates': '조치 후보', 'dec.rules': '적용한 규칙', 'dec.inputs': '판단에 쓴 값', 'dec.trace': '처리 과정',
    'dec.summaryMore': '자세히', 'dec.fired': '발동', 'dec.notApplicable': '해당 없음', 'dec.noFact': '사실 없음', 'dec.ruleSelect': '후보 선택', 'dec.ruleCompliance': '규정 적합성',
    'dec.col.rule': '규칙', 'dec.col.target': '대상', 'dec.col.result': '결과', 'dec.col.input': '입력 데이터', 'dec.col.source': '출처', 'dec.col.value': '값', 'dec.col.how': '가져온 방법',
    'dec.failed': '판단 실패', 'dec.noPatterns': '이상 패턴을 불러오지 못했습니다',
    // 이상 확인 · 조치
    'inc.list': '사건',
    'inc.noCandidates': '고를 조치 후보가 없습니다', 'inc.alertAt': '경보 시각', 'inc.approvedBy': '승인자',
    'inc.causes': '가능한 원인', 'inc.recommended': '권장 조치', 'inc.noEvidence': '증거 규칙 없음', 'inc.unknown': '판정 미확인', 'inc.pass': '조건 충족', 'inc.fail': '조건 미충족',
    'inc.observed': '관측',
    // 처리 건
    'inst.running': '진행 중',
    'inst.empty': '아직 처리 건이 없습니다', 'inst.emptySub': '설비에 경보가 나면 처리 건이 생깁니다. 결함 시뮬레이션에서 결함을 주입해 보세요', 'inst.select': '처리 건을 선택하세요',
    'inst.noTodo': '지금 할 일이 없습니다', 'inst.noTodoSub': '승인이나 입력이 필요한 단계가 열리면 여기에 나타나고 알림이 옵니다', 'inst.noConn': '처리 서비스에 연결할 수 없습니다',
    'inst.started': '시작', 'inst.ended': '종료',
    'inst.initial': '시작 값', 'inst.steps': '단계', 'inst.events': '에이전트 활동',
    'inst.waitingResult': '새 결과를 기다리는 단계', 'inst.endWaiting': '일부 경로가 종료 지점에 닿았습니다. 남은 단계가 끝나면 처리 건이 종료됩니다.',
    'inst.approval': '승인 전달', 'inst.effects': '이전 조치의 영향', 'inst.rework': '다시 수행', 'inst.reworkHistory': '다시 수행 이력', 'inst.reassess': '다시 평가', 'inst.woFailed': '정비 요청 전달 실패',
    'inst.gen': '차', 'inst.askTitle': '에이전트의 질문', 'inst.askWait': '질문을 읽는 중…', 'inst.loadingCards': '조치 후보를 불러오는 중…', 'inst.noForm': '이 단계의 입력 양식을 찾을 수 없습니다',
    'inst.followWo': '함께 발행될 정비 요청', 'inst.source.input': '시작 값', 'inst.source.runtime': '시스템', 'inst.source.none': '출처 없음', 'inst.structured': '구조화된 값', 'inst.noValue': '값 없음',
    'var.asset': '설비', 'var.pattern': '이상 패턴', 'var.cause': '원인', 'var.failure_mode': '고장 유형', 'var.chosen_skill': '고른 조치', 'var.chosen_skill_kind': '조치 종류', 'var.recovered': '회복', 'var.work_order': '정비 요청', 'var.note': '메모', 'var.approved_by': '승인자', 'var.approved_by_name': '승인자 이름', 'var.approved_role': '승인 역할', 'var.alert_id': '경보', 'var.incident':'사건', 'var._deferral':'보류 평가 기록',
    // 처리 건 변수의 화면 이름(정의 설명문에는 규칙 id · 클래스 이름이 섞여 화면 이름으로 쓰지 않는다)
    'var.alert': '경보 메시지', 'var.guide_card': '원인 분석 카드', 'var.candidates': '조치 후보', 'var.compliance': '규정 판정', 'var.decision': '조치 카드 묶음', 'var.decision_id': '조치 카드 묶음 번호', 'var.commands': '설비 명령', 'var.chosen_option': '고른 조치 카드', 'var.incident_outcome': '사건 결과', 'var.manual_source': '원문 문서', 'var.review_feedback': '사람 검토 판정', 'var.segment': '담당 구간', 'var.proposal': '추출 제안', 'var.ontology_catalog': '지식 목록', 'ontology.field.AnomalyPattern.code':'이상 패턴 코드', 'ontology.class.AnomalyPattern':'이상 패턴', 'val.SPARE_BELOW_MIN':'예비품 재고 기준 이탈', 'val.PM_DUE':'정기 정비 도래',
    'var.package_semantics':'정비 내용의 기록 의미','var.configured_base_package':'등록된 기본 정비 내용','val.base_interval_configuration':'등록된 기본 정비 설정 · 이번 차례 패키지 선택 아님',
    'inst.output': '출력', 'inst.due': '기한', 'inst.prevTask': '이전 단계',
    'inst.projectionPending': '반영 대기', 'inst.projectionAll': '사건 · 판단 반영 대기 (전체)', 'inst.projectionNone': '조회하지 못함', 'inst.query': '질의 보기',
    'inst.stepTable.step': '단계', 'inst.stepTable.status': '상태', 'inst.stepTable.who': '누가', 'inst.stepTable.when': '시각', 'inst.stepTable.result': '결과',
    'inst.closeReason': '이 단계를 닫는 사유', 'inst.cancelReason': '실행을 취소하는 사유',
    // 승인과 실행
    'proc.flow': '업무 흐름', 'proc.select': '판단을 선택하세요',
    'proc.manual': '수동 실행', 'proc.override': '추천과 다른 선택', 'proc.submitted': '제출', 'proc.executions': '실행 결과', 'proc.history': '이력',
    'proc.noChange': '변경 없음', 'proc.noTx': '아직 실행 이력이 없습니다', 'tx.beforeAfter': '변경 전·후', 'tx.col.field': '항목', 'tx.col.before': '변경 전', 'tx.col.after': '변경 후', 'tx.noDiff': '바뀐 값 없음', 'tx.created': '새로 만듦', 'proc.noEnt': '기업 시스템에 연결할 수 없습니다', 'proc.listError': '판단 목록을 갱신할 수 없습니다. 마지막으로 받은 목록입니다.',
    'proc.legend.done': '완료', 'proc.legend.now': '진행 중', 'proc.legend.stop': '중단', 'proc.legend.skipped': '건너뜀',
    // 설비
    'plant.ts1': '유온', 'plant.ce': '냉각 효율', 'plant.cp': '냉각 능력', 'plant.fan': '팬 속도', 'plant.load': '펌프 부하', 'plant.ps1': '토출 압력', 'plant.fs1': '유량', 'plant.vs1': '팬 진동', 'plant.pump': '운전 펌프',
    'plant.health': '쿨러 성능 비율', 'plant.phase': '경보', 'plant.state': '설비 상태', 'plant.lastCmd': '최근 명령 결과',
    'plant.modes': '운전 모드', 'plant.noCmd': '아직 누른 단추와 검증된 명령이 없습니다',
    'plant.noConn': '설비 값을 읽지 못했습니다', 'plant.noConnSub': '가상 설비(plant-sim)가 응답하면 저절로 다시 보입니다.',
    'plant.standby': '예비', 'plant.none': '아직 없음', 'plant.faultOn': '결함 진행 중', 'plant.current': '현재 상태',
    // 홈
    'main.assets': '설비', 'main.openCases': '경보로 열린 처리 건', 'main.knowledge': '지식 항목',
    'main.hot': '고온 · 정지', 'main.cool': '모든 설비 유온 55 ℃ 미만', 'main.noConn': '설비 연결 끊김', 'main.none': '없음', 'main.links': '연결',
    'main.liveTs1': '실시간 유온',
    // 지식 지도 · 지식 관리 · 조치 방법
    'onto.loadFail': '지식을 불러올 수 없습니다',
    'kn.noFile': '선택한 파일 없음', 'kn.preview': '문서 등록', 'kn.ddlPreview': '미리보기',
    'kn.docs': '등록된 매뉴얼', 'kn.docsEmpty': '등록된 매뉴얼이 없습니다', 'kn.docsEmptySub': '위에서 매뉴얼 파일을 등록하고 AI 추출 결과를 검토해 적재하면 여기에 표시됩니다', 'kn.history': '매뉴얼 등록 이력',
    'kn.current': '현재 판본', 'kn.previous': '이전 판본', 'kn.rolledBack': '되돌림', 'kn.revise': '이 문서 개정', 'kn.undo': '이 판본 되돌리기', 'kn.sections': '절', 'kn.procedures': '조치 방법', 'kn.steps': '단계',
    // 이 문서로 답할 수 있는 질문 (A118 골든 퀘스천 — 화면 문구만)
    'golden.title': '이 문서로 답할 수 있는 질문', 'golden.questions': '질문', 'golden.questionsHint': '한 줄에 하나 · 최대 20개 · 이 문서를 읽은 뒤 답할 수 있어야 하는 질문을 적습니다',
    'golden.ask': '확인 요청', 'golden.asking': '요청 중…', 'golden.askMore': '다른 질문 확인하기', 'golden.pending': '진행 중', 'golden.correcting': '교정 중', 'golden.done': '완료', 'golden.failed': '실패',
    'golden.checking': '질문 {n}개를 지식에 대어 보는 중…', 'golden.checkingSub': 'AI 에이전트가 이 문서가 넣은 지식만으로 답하는지 확인합니다',
    'golden.answerable': '답할 수 있음', 'golden.partial': '일부', 'golden.notYet': '아직 못 함', 'golden.grounded': '근거 있음', 'golden.confidence': '확신도',
    'golden.conf.high': '높음', 'golden.conf.medium': '보통', 'golden.conf.low': '낮음', 'golden.evidence': '근거 보기', 'golden.cited': '인용한 지식 항목', 'golden.noCited': '인용한 항목 없음', 'golden.query': '질의 보기',
    'golden.err.empty': '질문을 한 줄 이상 적으세요', 'golden.err.many': '질문은 최대 20개입니다', 'golden.err.load': '확인 결과를 읽지 못했습니다', 'golden.corrections': '형식 교정 {n}회',
    'inst.resultFile': '결과 파일로 제출',
    // A141 다이어트: 보조 정보 접기 · 에이전트 도구 이름 · 정의 이름
    'fold.meta': '상세 정보', 'fold.case': '사건 정보', 'fold.kpi': '성과 지표 영향', 'fold.penalty': '감점 · 경고', 'fold.violations': '제외 사유',
    'inst.eventsMore': '이전 활동 더 보기', 'card.sop': '절차 번호', 'log.raw': '원문',
    'def.anomaly_response': '설비 이상 조치', 'def.alert_triage': '미지원 경보 현장 검토', 'def.ask_agent': '에이전트에게 질문하기',
    'def.c3_cooling': '냉각 긴급 대응', 'def.c3_pm': '정기 정비', 'def.c3_spare': '예비품 구매',
    'def.manual_extraction': '매뉴얼 추출', 'def.manual_source_extraction': '문서 원천 추출', 'def.golden_questions': '매뉴얼 확인 질문', 'def.timeseries_question': '시계열 질문', 'def.business_question': '업무 질문', 'def.rule_question': '규칙 질문',
    'skill.new': '새 조치 방법', 'skill.select': '조치 방법을 선택하세요', 'skill.name': '이름', 'skill.desc': '설명', 'skill.approver': '승인 역할', 'skill.kind': '종류',
    'skill.kind.control': '설비 제어', 'skill.kind.workOrder': '정비 요청', 'skill.rel.remedy': '근본 조치', 'skill.rel.mitigate': '즉시 완화', 'skill.rel.prevent': '예방 조치', 'skill.sop': '절차 번호', 'skill.fm': '대상 고장 유형', 'skill.relation': '관계',
    'skill.steps': '절차 — 한 줄에 한 단계', 'skill.stepsTitle': '절차', 'skill.linked': '연결된 지식', 'skill.causes': '해당 원인', 'skill.actions': '세부 동작', 'skill.rules': '적용 규칙', 'skill.affects': '영향 지표',
    'skill.allCauses': '고장 유형의 모든 원인', 'skill.noSteps': '절차 없음', 'skill.none': '없음', 'skill.noFm': '대상 고장 유형 없음', 'skill.add': '추가', 'skill.unsaved': '저장하지 않은 변경 사항',
    'skill.saved': '저장했습니다', 'skill.nameRequired': '이름을 입력하세요', 'skill.fromDoc': '등록한 매뉴얼에서 만든 조치 방법입니다. 매뉴얼 개정 화면에서 수정합니다.', 'skill.openDoc': '매뉴얼 개정 열기',
    // 스트림
    'stream.title': '에이전트 활동', 'stream.filter.all': '전체', 'stream.filter.tool': '도구', 'stream.filter.task': '단계', 'stream.filter.human': '사람', 'stream.filter.error': '오류', 'stream.filter.work': '진행',
    'stream.pause': '멈춤', 'stream.resume': '다시 흐르게', 'stream.empty': '아직 활동이 없습니다', 'stream.emptySub': '에이전트가 일하면 여기에 실시간으로 나타납니다', 'stream.all': '모두 보기',
    'stream.tool': '도구', 'stream.start': '단계 시작', 'stream.done': '단계 완료', 'stream.working': '진행', 'stream.cancel': '단계 취소', 'stream.deferred': '보류', 'stream.reassess': '다시 평가 요청',
    'stream.asked': '사람에게 질문', 'stream.answered': '사람의 답변', 'stream.error': '오류', 'stream.cancelReq': '실행 취소 요청 (사람)', 'stream.closed': '단계 닫음 (사람)', 'stream.stopped': '실행 멈춤',
    // 흐름도 (정의 이름 → 화면 이름, UIUX_PLAN §4)
    'flow.lane.agent': '에이전트', 'flow.lane.human': '담당자', 'flow.lane.system': '시스템',
    'flow.name.경보 수신': '설비 경보', 'flow.name.원인 진단': '원인 진단', 'flow.name.조치 후보 조회': '조치 후보 조회', 'flow.name.규정 검토': '규정 검토', 'flow.name.우선순위 · 카드 작성': '조치 후보 정리',
    'flow.name.조치 카드 선택 (HITL)': '조치 선택', 'flow.name.상급자 호출': '책임자 확인', 'flow.name.PLC 명령 발행': '설비에 명령', 'flow.name.재관측 (15분)': '효과 확인 (15분)', 'flow.name.정비 작업지시': '정비 요청',
    'flow.name.선택 시간 초과': '선택 시간 초과', 'flow.name.종결': '종결', 'flow.name.에스컬레이션 종료': '책임자 확인으로 종료',
    'flow.name.즉시 제어 포함?': '설비 제어가 있나?', 'flow.name.회복?': '회복됐나?',
    // A6: 끝 이벤트 id가 이름 없이 오는 자리(처리 건 목록 end_event · 로그 "instance ended (ev:…)") — 정의 events[].name과 같은 말
    'flow.name.start': '시작', 'flow.name.alert': '설비 경보', 'flow.name.select-timeout': '선택 시간 초과', 'flow.name.unhandled-alert': '미지원 경보 접수', 'flow.name.review-recorded': '현장 검토 기록 완료',
    'flow.name.escalate': '책임자 확인', 'flow.name.triage': '현장 검토', 'flow.name.end': '종료', 'flow.name.끝': '처리 완료', 'flow.name.closed': '종결', 'flow.name.escalated': '책임자 확인으로 종료', 'flow.name.rejected': '반려', 'flow.name.accepted': '승인',
    'flow.seq.선택 스킬 kind == control': '설비 제어', 'flow.seq.선택 스킬 kind == work_order': '정비 요청만', 'flow.seq.TS1 < 55 and 경보 해제': '회복', 'flow.seq.미회복': '미회복',
    // 일반
    // A161-U1: 결과 값(영문 코드) → 화면 말 (판단 · 출력 칸)
    'val.answered': '답함', 'val.unanswerable': '답할 수 없음', 'val.not_answerable': '답할 수 없음', 'val.ok': '정상', 'val.normal': '정상', 'val.abnormal': '비정상',
    'val.recovered': '회복', 'val.not_recovered': '미회복', 'val.approved': '승인', 'val.rejected': '반려', 'val.pending': '대기',
    'inst.cannotOpen': '이 처리 건은 열 수 없습니다',
    'empty.noData': '없음', 'loading': '불러오는 중…', 'error.load': '불러오지 못했습니다', 'more': '자세히', 'raw': '원문', 'yes': '예', 'no': '아니요',
  },
  t(key, vars) {
    let s = Object.prototype.hasOwnProperty.call(this.terms, key) ? this.terms[key] : key;
    if (vars) for (const [k, v] of Object.entries(vars)) s = s.replace('{' + k + '}', v);
    return s;
  },
  /* definition names (process definition JSON) → display names; the definition itself is not changed */
  flowName(name) { return this.terms['flow.name.' + name] || name; },
  // 조건식 이름(교대 흐름의 sender_decision == 'approve')은 그림에 사람 말로 보인다 — 「인계자 승인」
  flowSeq(name) {
    if (this.terms['flow.seq.' + name]) return this.terms['flow.seq.' + name];
    const m = /^\s*(\w+)\s*==\s*'(\w+)'\s*$/.exec(name || '');
    const who = { sender_decision: '인계자', receiver_decision: '인수자' }, what = { approve: '승인', revise: '보완 요청', reject: '거절', confirm: '확인' };
    return m && who[m[1]] && what[m[2]] ? `${who[m[1]]} ${what[m[2]]}` : name || '';
  },
  defName(id) { const base=String(id || '').split('.')[0]; return this.terms['def.'+base] || this.names[id] || '흐름 표시 이름 미등록'; },
  // 도구 표시 이름은 plainWords(hydWords) 사전 하나가 정한다(W3-09) — 이 함수는 그 문을 연다
  toolName(t) { return window.hydWords.toolName(t); },
  toolIdentityFold(raw) {
    if (!raw || window.hydWords.knownTool(raw)) return '';
    return this.fold('호출 도구 원문',`<pre class="code">${esc(raw)}</pre>`);
  },

  /* ---------- A141 원문 id → 이름 (names.json: workspace/개발/scripts/portal_names.py 가 Neo4j 실제 이름으로 생성) ----------
     응답에 이름이 있으면 그것을 쓰고, 없을 때만 이 사전으로 바꾼다. 사전에 없는 id 는 그대로 둔다(지어내지 않음). */
  names: {}, namesVersion: 0,
  // 문장 속 원래 id(접두어:이름 — fm: · cause: · action: · in: · sen: · dept: · ks:manual:… 등)는 접두어 목록 없이 한 꼴로 찾고, 사전에 있는 것만 이름으로 바꾼다(W2-02)
  ID_RE: /\b[a-z][a-z-]*:[A-Za-z0-9_][A-Za-z0-9_.:%-]*/g,
  name(id) { return (id && this.names[id]) || id || ''; },
  idText(text) { return this.words(String(text ?? '').replace(this.ID_RE, m => this.names[m] || m)); },
  // A161-U1: 화면에 쓰지 않는 말(데이터 · 온톨로지 원문에 남은 것) → 화면 말. "정비창"은 "예정된 정비 시간"으로 부른다(사용자 결정 2026-10-09).
  // 문장 속 경보 패턴 코드(그래프 규칙 설명 「COOLER_DEGRADATION 경보에서 …」 등)도 사람 이름으로 — 표에 있는 코드만 바꾼다
  words(text) { return String(text ?? '').replace(/야간\s*정비창/g, '야간 정비 시간').replace(/정비창/g, '예정된 정비 시간').replace(/\b[A-Z][A-Z_]{3,}[A-Z]\b/g, code => this.patterns[code] || code); },
  // 이름 사전 읽기: 실패를 삼키지 않는다 — 머리에 한 번 알리고 10초 뒤 다시 읽는다(그동안 원래 id · 「표시 이름 미등록」이 보일 수 있다, W1-28)
  async loadNames() {
    try {
      const r = await fetch('names.json', { cache: 'no-store' });
      if (!r.ok) throw new Error(`요청 실패 ${r.status}`);
      this.names = await r.json(); this.namesVersion = Object.keys(this.names).length; this.namesError = '';
    } catch (e) {
      this.namesError = e.message;
      console.error('이름 사전(names.json)을 읽지 못했습니다', e);
      if (this.toast) this.toast(`이름 사전을 읽지 못해 원래 id 가 보일 수 있습니다(${e.message}) — 10초 뒤 다시 읽습니다`, { tone: 'neg', timeout: 8000 });
      setTimeout(() => this.loadNames(), 10000);
    }
  },

  /* ---------- A141 단계 로그(영문) → 화면 문구. 원문은 호출하는 쪽이 접기에 보존한다.
     A155: process 는 로그를 "조각; 조각; "으로 덧붙인다(procsvc instances.py·engine.py). logText 가 ';'로 먼저 자르므로
     패턴은 조각 하나에 맞춰야 한다 — ';'를 품은 패턴은 맞을 수 없다. ---------- */
  logPatterns: [
    [/^cancelled: (?:ev:|task:)?([\w-]+) completed first;?$/, m => m[1] === 'select-timeout' ? '선택 시간 초과가 먼저 와서 취소' : '다른 갈래가 먼저 끝나 취소'],   // A147: 경계 타이머 경쟁
    [/^human approval accepted$/, () => '담당자 승인 접수'],
    [/^delivery tracked separately$/, () => '전달은 별도로 추적'],
    [/^approval accepted by (.+)$/, (m, U) => `${U.who(m[1])} 승인 접수`],
    [/^delivery pending$/, () => '전달 대기'],
    [/^approval discarded: (.+)$/, () => '승인 폐기'],
    [/^cancelled: instance closed by a person$/, () => '담당자가 처리 건을 닫아 취소'],
    [/^fired at (\S+)$/, m => `발생 ${m[1].replace('T', ' ').replace(/\.\d+Z?$|Z$/, '')}`],
    [/^\[Rejected (\d+)\/(\d+)\] ?(.*)$/, m => `[형식 반려 ${m[1]}/${m[2]}] ${m[3]}`.trim()],
    [/^\[Error\] ?(.*)$/, m => `[오류] ${m[1]}`.trim()],
    [/^\[DELIVERY RETRY\] ?(.*)$/, m => `[전달 재시도] ${m[1]}`.trim()],
    [/^CMMS retry requested by (.+?) \((.+)\)$/, (m, U) => `${U.who(m[1])} 정비 요청 재시도`],
    [/^\[Lease expired after (\d+) claims: run marked FAILED\]$/, m => `실행 임대 ${m[1]}회 만료 · 실패 처리`],
    [/^submitted by (.+)$/, (m, U) => `${U.who(m[1])} 제출`],
    [/^waiting for the incident re-observation verdict$/, () => '효과 확인 결과 대기'],
    [/^cancelled: incident (\w+) before any action \(cleared=(True|False)\)$/, (m, U) => `조치 전 사건 종료(${U.status(m[1])})로 취소`],
    [/^reached by abort: incident (\w+) before any action \(cleared=(True|False)\)$/, (m, U) => `조치 전 사건 종료(${U.status(m[1])})로 도달`],
    [/^rework superseded: (.+)$/, () => '다시 수행으로 대체됨'],
    [/^\[Lease expired: reclaimed by (.+?) \(claim (\d+)\)\]$/, m => `실행 임대 만료 · 다른 작업자가 이어받음 (${m[2]}번째)`],
    [/^action\.cmd (CMD-[\w-]+) issued$/, m => `설비 명령 ${m[1]} 전송`],
    [/^waiting ACK$/, () => '설비 응답 대기'],
    [/^waiting ACK until (\S+)$/, (m, U) => `설비 응답 대기(${U.dateTime(m[1])}까지)`],   // instances.py 명령 전송 로그
    [/^\[Cancel requested by (.+?)\] ?(.*)$/, (m, U) => `[${U.who(m[1])} 실행 취소 요청] ${m[2]}`.trim()],
    [/^\[Closed by (.+?)\] ?(.*)$/, (m, U) => `[${U.who(m[1])} 단계 닫음] ${m[2]}`.trim()],
    [/^\[DEFERRED\] ?(.*)$/, m => `[보류] ${m[1]}`.trim()],
    [/^cleared before any action$/, () => '조치 전에 경보 해제'],
    [/^cleared=(True|False) (\w+)=(-?[\d.]+|None) \(criterion (.+)\)$/, m => `경보 해제 ${m[1] === 'True' ? '예' : '아니요'} · ${m[2]} ${m[3] === 'None' ? '값 없음' : m[3]} (기준 ${m[4]})`],
    [/^alert (ALT-[\w-]+)$/, m => `경보 ${m[1]}`],
    [/^source handler lease expired$/, () => '원천 처리기 임대 만료'],
    [/^[A-Z_]{4,}$/, (m, U) => U.status(m[0])],
  ],
  /* ---------- A161-U1 화면 정리: 호스트 경로 → 파일 이름, 모델 이름 → "AI 모델", 내부 오류 문구 → 사용자 말 (원문은 접기에만) ---------- */
  PATH_RE: /(?:[A-Za-z]:\\|\/(?:Users|home|private|tmp|var|root|opt|mnt|workspace|app)\/)[^\s"'`<>()\],;]*|(?:\.evidence|\.claude)\/[^\s"'`<>()\],;]*/g,
  MODEL_RE: /\b(?:claude-(?:opus|sonnet|haiku)[\w.-]*|claude-\d[\w.-]*|gpt-[\w.-]+|o\d-[\w.-]+|gemini-[\w.-]+|frentis-[\w.-]+)\b/gi,
  baseName(p) { const parts = String(p || '').split(/[\\/]+/).filter(Boolean); return parts.length ? parts[parts.length - 1] : ''; },
  // 흐름 정의의 단계 · 이벤트 id(task:x · ev:x · gw:x)와 온톨로지 id 를 화면 이름으로 (A160 결함 11)
  plain(text) {
    return this.idText(String(text ?? '')).replace(/\b(?:task|ev|gw):([A-Za-z0-9_-]+)/g, (m, id) => { const n = this.flowName(id); return n !== id ? n : (this.names[m] || id.replace(/[-_]/g, ' ')); });
  },
  clean(text) {
    if (text == null) return '';
    return this.words(this.mask(text));
  },
  // 원문 칸(물은 원문 · 받은 원문)용: 이 PC 경로 · 모델 이름만 가리고 글은 그대로 — 코드 값을 이름으로 바꾸지 않는다(words 는 설명 문장용).
  // 한바퀴3: 「물은 원문」의 "pattern": "COOLER_DEGRADATION" 이 "쿨러 성능 저하"로 바뀌어 원문이 실제 호출과 달랐다
  mask(text) {
    if (text == null) return '';
    return String(text).replace(this.PATH_RE, m => this.baseName(m) || '작업 폴더').replace(this.MODEL_RE, 'AI 모델');
  },
  // 도구 결과 문구로 본 상태: ok | warn(잘림 · 막힘) | fail. 칩이 "완료"인데 실제로는 잘린 결과를 받은 경우를 가려낸다(A160 결함 5)
  outcome(output, isError) {
    const s = typeof output === 'string' ? output : (output && typeof output === 'object' && typeof output.error === 'string' ? output.error : '');
    if (/exceeds maximum allowed tokens|result \(\d[\d,]*\s*characters\) exceeds/i.test(s)) return { tone: 'warn', label: this.t('trace.truncated'), text: this.t('trace.truncatedText') };
    if (/Contains brace with quote|requires approval|was blocked|not allowed|permission denied for this tool|denied by/i.test(s)) return { tone: 'blocked', label: this.t('trace.blocked'), text: this.t('trace.blockedText') };
    if (isError) return { tone: 'fail', label: this.t('trace.failed'), text: '' };
    return { tone: 'ok', label: '', text: '' };
  },
  logText(raw) {
    const text = String(raw ?? '').trim(); if (!text) return '';
    return text.split(/;\s*/).map(s => s.trim()).filter(Boolean).map(seg => {
      for (const [re, fn] of this.logPatterns) { const m = seg.match(re); if (m) return fn(m, this); }
      return this.idText(seg);
    }).join(' · ');
  },
  // 보조 메타(담당자 · 시각 · id)는 기본 접기: items = [[label, value]], 값이 비면 뺀다
  metaFold(items, label = 'fold.meta') {
    const rows = (items || []).filter(([, v]) => v != null && v !== '' && v !== '–');
    if (!rows.length) return '';
    return this.fold(esc(this.t(label)), `<dl class="kv">${rows.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${v}</dd>`).join('')}</dl>`);
  },

  /* ---------- 상태 이름 (UIUX_PLAN §5 + 사건 상태) ---------- */
  states: {
    PENDING_APPROVAL: "승인 대기", AWAITING_APPROVAL: "조치 선택 대기", GUIDE_RECEIVED: "분석 완료", CMD_ISSUED: "명령 전송", AWAITING_ACK: "설비 응답 대기",
    ACKED: "설비 응답", RE_OBSERVING: "효과 확인 중", RESOLVED: "이상 완화", WORK_ORDER_CREATED: "정비 요청 완료", CLOSED: "종결",
    ESCALATED: "책임자 확인", REJECTED_BY_OPERATOR: "반려", RESOLVED_WITHOUT_ACTION: "자연 회복", APPROVED: "승인됨", EXECUTED: "실행 완료",
    PARTIAL: "일부 실행", REJECTED: "반려", CLOSED_UNAPPROVED: "승인 전 종료", FAILED: "실패", SUBMITTED: "제출됨", DONE: "완료", RUNNING: "진행 중",
    RUN: "운전 중", TRIP: "보호 정지", STOP: "계획 정지", RAISED: "경보 발생", RAISE: "경보 발생", CLEAR: "경보 해제", CLEARING: "회복 확인 중",
    CANDIDATE: "이상 징후", IDLE: "감시 중", VIA_HITL: "사람 승인 필요", REMOTE_AUTO: "원격 자동", REMOTE_MANUAL: "원격 수동", LOCAL: "현장 제어",
    WITHHELD: "데이터 부족", REJECTED_BY_GUARDRAIL: "안전 규칙으로 중단", NO_FEASIBLE_OPTION: "가능한 조치 없음", NOT_APPLICABLE: "해당 없음", EVALUATED: "판단 완료",
    NEW: "생성", TODO: "예정", IN_PROGRESS: "진행 중", PENDING: "보류", HUMAN_ASKED: '답변 기다림', FB_REQUESTED: '반영 중', STARTED: '진행 중', CANCELLED: "취소",
    COMPLETED: "완료", SKIPPED: "건너뜀", DELIVERED: "전달 완료", DISCARDED: "폐기", OK: "완료",
    UNSUPPORTED_ALERT_PATTERN: "정의에 없는 경보 패턴", SELECT_TIMEOUT: "선택 시간 초과", NOT_RECOVERED: "미회복",
    RECORDED: "기록됨", HANDLED: "처리 완료", QUEUED: "대기열", CLAIMED: "처리 중", WAITING: "대기", SUPERSEDED: "대체됨", ACTIVE: "현재 판본", ROLLED_BACK: "되돌림",   // A6
    UNKNOWN: "판정 불가", UNSUPPORTED: "지원하지 않음", READY: "준비됨", OCR_REQUIRED: "글자 인식 필요", AWAITING_AGENT: "에이전트 대기", BLOCKED_FOR_REVIEW: "사람 확인 필요", CORRECTED: "교정됨",
    PROCESS_RESTART_REVIEW: "서비스 재시작 후 재검토", MITIGATION_FAILED: "완화 실패", ACK_TIMEOUT: "설비 응답 시간 초과", PASS: "통과", INTERLOCK: "안전 연동",
  },
  tones: {
    neutral: ['TODO', 'NEW', 'SKIPPED', 'IDLE', 'STOP', 'NOT_APPLICABLE', 'GUIDE_RECEIVED', 'LOCAL', 'DISCARDED', 'CLOSED_UNAPPROVED', 'CANCELLED'],
    accent: ['IN_PROGRESS', 'SUBMITTED', 'RUNNING', 'STARTED', 'FB_REQUESTED', 'APPROVED', 'CMD_ISSUED', 'AWAITING_ACK', 'REMOTE_AUTO', 'RE_OBSERVING', 'DELIVERED'],
    success: ['DONE', 'COMPLETED', 'CLOSED', 'EXECUTED', 'RESOLVED', 'RESOLVED_WITHOUT_ACTION', 'RUN', 'ACKED', 'WORK_ORDER_CREATED', 'EVALUATED', 'CLEAR', 'OK'],
    warning: ['PENDING', 'HUMAN_ASKED', 'PENDING_APPROVAL', 'AWAITING_APPROVAL', 'PARTIAL', 'VIA_HITL', 'WITHHELD', 'REMOTE_MANUAL', 'CLEARING', 'CANDIDATE', 'ESCALATED'],
    danger: ['FAILED', 'REJECTED', 'REJECTED_BY_OPERATOR', 'REJECTED_BY_GUARDRAIL', 'NO_FEASIBLE_OPTION', 'TRIP', 'RAISED', 'RAISE'],
  },
  // 처리 건 값(variables_data 행 목록) → {키: 값} — 화면 모듈이 같은 펼치기를 따로 두지 않는다(W1-11)
  valuesOf(inst) { return Object.fromEntries(((inst && inst.variables_data) || []).map(r => [r.key, r.value])); },
  // 작업 행의 주체: AI 에이전트(워커 단계) · 사람(사람 단계) · 시스템(그 밖 — 서비스 · 설비 · 타이머)
  doerOf(w) { return w.agent_orch === 'cliagents' || w.agent_mode ? 'agent' : !w.agent_orch && !w.agent_mode ? 'human' : 'system'; },
  // 처리 건 작업 행을 일어난 차례로: 시작 시각 → 끝 시각 → 같은 순간이면 흐름 순서(서버 view.flow_order = 정의의 흐름 차례 — 단계 id → 순번).
  // 한 트랜잭션에서 연달아 끝난 시스템 단계(정비 오더 등록 → 결과 보고)는 시각이 같다 — 시각만으로는 순서가 거꾸로 보일 수 있다(W1-01).
  workitemOrder(view) {
    const rank = new Map(Object.entries(view?.flow_order || {}));
    const at = x => { const t = x ? Date.parse(x) : NaN; return Number.isFinite(t) ? t : 9e15; };
    return (a, b) => at(a.start_date) - at(b.start_date) || at(a.end_date) - at(b.end_date) || (rank.get(a.activity_id) ?? 9e9) - (rank.get(b.activity_id) ?? 9e9);
  },
  // 승인 전달(승인한 내용을 업무 시스템 · 설비로 넘기는 일)의 상태 — 단계 상태(PENDING = 보류)와 다른 축이라 이름표를 따로 둔다(W1-04)
  deliveryStates: { PENDING: '전달 대기', DELIVERED: '전달 완료', FAILED: '전달 실패', DISCARDED: '승인 폐기' },
  deliveryChip(value) { return this.chip(value, this.deliveryStates[value] || this.status(value), { PENDING: 'warning', DELIVERED: 'success', FAILED: 'danger', DISCARDED: 'neutral' }[value]); },
  status(value) { return this.states[value] || value || "–"; },
  toneOf(value) { for (const [tone, list] of Object.entries(this.tones)) if (list.includes(value)) return tone; return 'neutral'; },
  // 상태 뱃지(키트에 더한 .tag — 점 + 글). tone 은 지금 이름(neutral · accent · success · warning · danger)으로 받아 키트의 data-tone 으로 바꾼다. 보통(neutral)은 속성이 없다
  toneAttr(tone) { const t = { accent: 'brand', success: 'ok', warning: 'warn', danger: 'danger' }[tone]; return t ? ` data-tone="${t}"` : ''; },
  chip(value, label, tone) {
    return `<span class="tag"${this.toneAttr(tone || this.toneOf(value))} data-status="${esc(value || '')}">${esc(label != null ? label : this.status(value))}</span>`;
  },
  chipText(label, tone = 'neutral') { return `<span class="tag"${this.toneAttr(tone)}>${esc(label)}</span>`; },

  /* ---------- 경보 패턴 이름(감지기 · 업무 경보 · 인터록 트립 코드 → 사람 말). 포털 전체가 이 표 하나를 쓴다 ---------- */
  // 경보 패턴 코드 → 이름: 그래프(AnomalyPattern.name)가 정본 — agent /api/ontology/patterns 를 한 번 읽어 채운다(화면 사본 없음, G3b-8)
  patterns: {}, patternsError: '',
  async loadPatterns() {
    try {
      const list = await getJ(API.agent + '/api/ontology/patterns');
      this.patterns = Object.fromEntries(requireList(list, '경보 패턴 목록').filter(p => p.code && p.name).map(p => [p.code, p.name]));
      this.patternsError = ''; this.namesVersion += 1;   // 이름이 바뀌었으니 서명에 namesVersion 을 쓰는 화면이 다시 그린다
    } catch (e) {
      this.patternsError = e.message;
      console.error('경보 패턴 이름을 읽지 못했습니다', e);
      if (this.toast) this.toast(`경보 패턴 이름을 읽지 못해 영문 코드가 보일 수 있습니다(${e.message}) — 10초 뒤 다시 읽습니다`, { tone: 'neg', timeout: 8000 });
      setTimeout(() => this.loadPatterns(), 10000);
    }
  },
  // 표에 없는 코드(PBL 에서 학생이 만든 경보 등)는 지어내지 않고 원래 코드를 그대로 둔다
  patternName(code) { return code ? this.patterns[code] || this.idText(code) : ''; },

  /* ---------- 수행 주체 (명칭표 "행위자") ---------- */
  // 시스템(sys:* · actr:* · 감지기) 이름은 plainWords W.system 한 길(W2-03 — 「정비 시스템」/「정비 관리」 두 벌이었다) — 그래프 id 의 이름은 names.json(portal_names.PLAIN). 여기는 사람 역할 · 수행 갈래만
  performers: { agent: 'AI 에이전트', 'role:operator': '운전원', operator: '운전원', 'role:prod-mgr': '생산관리자', 'role:maint-mgr': '설비보전팀장',
    'role:plant-mgr': '공장장', 'role:quality-mgr': '품질팀장', 'role:purchasing-mgr': '구매팀장', 'role:purchasing': '구매 담당', plc: '설비', process: '시스템',
    cliagents: 'AI 에이전트', human: '담당자', result: '시스템' },
  // 시드의 기본 AI 수행자 이름(제품 이름이 붙음)은 화면에서 「인공지능 에이전트」 — 처리 기록 · 그래프의 실행 주체 노드(id 가 다름)도 같은 이름이라 이름으로 본다
  // 사람 이름은 내 작업함이 사람 목록을 읽으면 performers 에 채운다(inbox.js). 읽기 전 · 못 읽은 사람 id 는 원래 id(user:…)를 보이지 않는다
  who(id) {
    if (id == null || id === '') return '–';
    if (this.performers[id]) return this.performers[id];
    if (/^(sys|actr|sen):/.test(id) || id === 'detector') return window.hydWords.system(id);
    return /^user:/.test(id) ? '담당자 (이름 확인 안 됨)' : /^agent:/.test(id) ? 'AI 에이전트' : id;
  },
  roleName(id, definition) { return (definition?.roles || []).find(r => r.endpoint === id)?.name || this.who(id); },
  // 담당자 값: 쓰는 사람은 늘 담당자 한 명이다(inbox.js 머리말). 담당자 id 는 숨은 칸에 실어 보내고 화면에는 아무것도 그리지 않는다(못 읽었을 때만 까닭 한 줄).
  // attrs 는 입력 요소의 속성 원문(id="rwBy" · data-retry-by 등) — 읽는 코드는 그대로 .value 를 읽는다.
  actorInput(attrs, value, extra = '') {
    const m = window.hydInbox?.me?.();
    if (m) return `<input type="hidden" ${attrs} value="${esc(m.id)}">`;      // 화면에 칸을 그리지 않는다 — 쓰는 사람이 한 명이라 보일 정보가 없다
    // 서버는 사람 행동을 등록된 담당자(user:…)로만 받는다 — 자유 글 칸을 두지 않는다(W1-08)
    return `<input type="hidden" ${attrs} value=""><span class="muted" data-tone="danger" role="alert" data-pick-me>담당자 정보를 읽지 못했습니다. 화면을 새로 고치세요.</span>`;
  },
  // 요청 id(같은 요청을 다시 보낼 때 서버가 알아보는 번호). 포털은 127.0.0.1 에만 열리므로(compose.yaml) 늘 보안 문맥 — randomUUID 가 있다
  uuid() { return window.crypto.randomUUID(); },
  // 서버가 영문으로 돌려주는 거절 사유 → 학생이 읽을 한국어 한 줄(모르는 문구는 그대로 둔다)
  serverTexts: [
    [/^no such work item$/, '작업을 찾지 못했습니다 — 이미 처리됐거나 지워졌을 수 있습니다.'],
    // 입력 검사(422)의 프레임워크 기본 문구 — 2026-10-25 수업 한 바퀴: [다시 평가] 긴 사유에 「String should have at most 2000 characters」가 그대로 보였다
    [/^String should have at most (\d+) characters?$/, m => `${m[1]}자 이하로 줄여 적으세요.`],
    [/^String should have at least (\d+) characters?$/, m => `${m[1]}자 이상 적으세요.`],
    [/^Field required$/, '필수 항목을 입력하세요.'],
    [/^Input should be a valid (integer|number)/, '숫자를 입력하세요.'],
  ],
  // 422 detail 배열의 한 줄: 칸 이름(아는 것만 한국어) + 번역한 문구
  validationText(x) {
    const field = ({ reason: '사유', by: '담당자', note: '메모', name: '이름' })[(x && x.loc || []).slice(-1)[0]];
    const text = this.serverText(x && x.msg || JSON.stringify(x));
    return field ? `${field}: ${text}` : text;
  },
  serverText(message) {
    const text = String(message ?? '');
    for (const [re, out] of this.serverTexts) { const m = re.exec(text.trim()); if (m) return typeof out === 'function' ? out(m) : out; }
    return text;
  },

  dateTime(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value || '–' : date.toLocaleString('ko-KR', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false });
  },
  // 시각(시:분:초, 24시간) — 포털의 시각 형식 하나(처리 과정 · 처리 기록 · 결과 보고가 같은 꼴, W1-14)
  time(value) {
    if (value == null || value === '') return '–';   // new Date(null) 은 1970년 0시 — 「09:00:00」을 지어 보이지 않는다
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value || '–' : date.toLocaleTimeString('en-GB', { hour12: false });
  },
  eventNames: {
    task_deferred: '진단 보류', task_reassessment_requested: '다시 평가 요청',
    GUIDE_SUBMITTED: '분석 결과 제출', GUIDE_APPROVED: '분석 결과 승인',
    DECISION_SUBMITTED: '조치 후보 제출', DECISION_APPROVED: '조치 승인', DECISION_DENIED: '승인 권한 부족', DECISION_REJECTED: '조치 반려',
    CMD_ISSUED: '설비에 명령', ACK_RECEIVED: '설비 응답', INCIDENT_CREATED: '사건 시작', INCIDENT_OPENED: '사건 시작', INCIDENT_CLOSED: '사건 종결',
    STATE_CHANGED: '상태 변경', REOBSERVE_DONE: '효과 확인 완료', ACK_DONE: '설비 응답 완료', ALERT_CLEARED: '경보 해제', CMD_PUBLISHED: '설비에 명령',
    MANUAL_INGESTED: '매뉴얼 등록', REOBSERVATION: '효과 확인', REOBSERVATION_EXTENDED: '효과 확인 연장', APPROVAL_CURRENT_CHECK: '승인 조건 재확인',
    SKILL_EDITED: '조치 방법 수정', SKILL_EXECUTED: '조치 실행', WORK_ORDER_CREATED: '정비 요청', EFFECT_ACKNOWLEDGED: '영향 확인 기록',
    INCIDENT_ENDED_BEFORE_ACTION: '조치 전 사건 종료', INCIDENT_REOPENED: '사건 다시 열림', TIMER_IGNORED: '지난 타이머 무시', MANUAL_GOLDEN_REQUESTED: '매뉴얼 확인 질문 요청',
    INSTANCE_STARTED: '처리 건 시작', TASK_COMPLETED: '단계 완료', TASK_PENDING: '조건 미충족', TASK_REVIEW_REQUIRED: '새 판단 · 승인 필요', SELECT_TIMEOUT: '선택 시간 초과',
    task_started: '단계 시작', task_completed: '단계 완료', task_working: '진행', tool_usage_started: '도구 호출', tool_usage_finished: '도구 결과',
    human_asked: '사람에게 질문', human_response: '사람의 답변', task_cancelled: '단계 취소', error: '오류',
    '명령 검증 통과': '명령 검증 통과', '명령 거절': '명령 거절',
    ACK_REJECTED: '설비 명령 거절', GUIDE_REJECTED: '분석 결과 반려', WORK_ORDER_FAILED: '정비 요청 실패', SKILL_FAILED: '조치 실행 실패', SKILL_CREATED: '조치 방법 추가',   // A6
    AGENT_TASK_CLOSED: '에이전트 작업 닫음', MANUAL_ROLLED_BACK: '매뉴얼 되돌림', DDL_INGESTED: '업무 데이터 구조 등록', DDL_SOURCE_DRIFT: '업무 데이터 구조 변경 감지',
    INGEST_CLEARED: '업무 데이터 연결 해제', SCM_SOURCE_SYNCED: '공급망 원천 동기화',
  },
  eventName(name) { return this.eventNames[name] || this.states[name] || name || '–'; },
  // chips: optional pre-rendered small chips after the actor (A132: `결과 파일로 제출` on a task_completed whose result_source is file)
  // extra: optional pre-rendered fold before the raw fold (A147: 기업 거래의 `변경 전·후`)
  eventRecord({ time, name, actor = '', detail = '', raw, chips = '', extra = '' }) {
    // 실시간 줄(.line)과 같은 모양: 아이콘 + 굵은 한 문장 + 보조 줄(누가 · 무엇) + 오른쪽 시각. 원문은 그 아래 접기
    const sub = [actor ? esc(this.who(actor)) : '', detail ? esc(detail) : ''].filter(Boolean).join(' · ');
    return `<article class="event-record"><div class="line">${this.icon('circle-dot')}<span class="line-text"><b>${esc(this.eventName(name))}</b>${chips ? `<span class="line-chips">${chips}</span>` : ''}${sub ? `<span class="line-sub">${sub}</span>` : ''}</span><time class="line-time num" title="${esc(this.dateTime(time))}">${esc(this.time(time))}</time></div>${extra}${raw ? `<details class="fold"><summary>${esc(this.t('raw'))}</summary><div class="fold-body"><pre class="code">${esc(JSON.stringify(raw, null, 2))}</pre></div></details>` : ''}</article>`;
  },
  /* ---------- 공통 부품 — 키트(vendor/basecoat)와 portal-kit.css 의 마크업을 낸다(디자인 기준 8-2). 함수 이름 · 인자 · 반환 꼴은 화면 모듈이 부르던 그대로다 ---------- */
  // card: 제목 · 보조 한 줄 · (오른쪽) 뱃지와 단추 · 핵심 값 · 본문
  card({ title, chips = '', value = '', sub = '', body = '', cls = '', actions = '', attrs = '' }) {
    const side = chips || actions ? `<div class="card-action">${chips}${actions}</div>` : '';
    return `<div class="card${cls ? ' ' + cls : ''}" ${attrs}>` +
      (title || sub || side ? `<header>${title ? `<h3>${title}</h3>` : ''}${sub ? `<p>${sub}</p>` : ''}${side}</header>` : '') +
      (value || body ? `<section>${value ? `<div class="stat-value num">${value}</div>` : ''}${body}</section>` : '') + '</div>';
  },
  // field: 이름표 위 · 입력 아래 · 필수 * · 도움말 또는 오류 한 줄. 입력 요소에 클래스가 없으면 키트의 것(input · textarea · select)을 붙인다
  kitInput(html) {
    return String(html).replace(/<(input|textarea|select)\b(?![^>]*\bclass=)([^>]*)>/, (all, tag, rest) =>
      tag === 'input' && /\btype="(checkbox|radio|range|file|hidden)"/.test(rest) ? all : `<${tag} class="${tag}"${rest}>`);
  },
  field({ label, input, hint = '', required = false, cls = '', error = '' }) {
    const inputId = /\bid="([^"]+)"/.exec(input)?.[1];
    // 도움말 · 오류 줄의 field-hint · field-error 는 모양이 아니라 찾는 이름이다(flows.js idField 가 도움말을 바꿔 쓴다)
    return `<div role="group" class="field${cls ? ' ' + cls : ''}"${error ? ' data-invalid' : ''}><label${inputId ? ` for="${inputId}"` : ''}>${esc(label)}${required ? ' <span aria-hidden="true">*</span>' : ''}</label>${this.kitInput(input)}${error ? `<p class="field-error" role="alert">${esc(error)}</p>` : hint ? `<p class="field-hint">${esc(hint)}</p>` : ''}</div>`;
  },
  // 폼의 한 묶음: 제목(legend) + 입력 격자
  section(title, body, cls = '') { return `<fieldset class="fieldset${cls ? ' ' + cls : ''}">${title ? `<legend>${esc(title)}</legend>` : ''}<div role="group">${body}</div></fieldset>`; },
  // 폼 아래의 단추 줄: (왼쪽) 못 한 까닭 한 줄 · (오른쪽) 단추
  actions(body, msg = '') { return `<footer class="form-foot">${msg ? `<span class="muted" data-tone="danger" role="status">${esc(msg)}</span>` : ''}${body}</footer>`; },
  // fold: 요약 한 줄 + 꺾쇠. 옛 크기 이름(small)은 받지 않는다 — 접기의 모양은 하나다
  fold(summary, body, { open = false, cls = '' } = {}) {
    const extra = cls.split(/\s+/).filter(c => c && c !== 'small').join(' ');
    return `<details class="fold${extra ? ' ' + extra : ''}" ${open ? 'open' : ''}><summary>${summary}</summary><div class="fold-body">${body}</div></details>`;
  },
  // empty: 제목 한 줄 + 보조 한 줄(무엇을 하면 채워지는지)
  empty(title, sub = '', cls = '') { return `<section class="empty${cls ? ' ' + cls : ''}"><header><h3>${esc(title)}</h3>${sub ? `<p>${esc(sub)}</p>` : ''}</header></section>`; },
  // emptyGo: 빈 화면 + 다음 할 일로 가는 단추 하나(tab = 화면 이름, index.html 의 view-<이름>). 「없음」에서 끝나지 않고 무엇을 하면 채워지는지로 잇는다
  emptyGo(title, sub, tab, label, cls = '') {
    return `<section class="empty${cls ? ' ' + cls : ''}"><header><h3>${esc(title)}</h3>${sub ? `<p>${esc(sub)}</p>` : ''}</header><footer><button type="button" class="btn" data-variant="outline" data-size="sm" data-go-tab="${esc(tab)}">${esc(label)}${this.icon('arrow-right')}</button></footer></section>`;
  },
  // tabs: 같은 대상의 보기를 바꾸는 묶음 단추(.seg). items = [[key, label, count?]]
  tabs(items, active, attr = 'data-tab-key') {
    return `<div class="seg" role="group">${items.map(([k, l, n]) => `<button type="button" aria-pressed="${k === active}" ${attr}="${esc(k)}">${esc(l)}${n != null ? `<span class="num">${esc(n)}</span>` : ''}</button>`).join('')}</div>`;
  },
  // paged list (A122 coordinator request): first `shown` rows, the selected row pinned on top when it is beyond them, one 더 보기 button
  PAGE: 20,
  page(items, shown, isSelected) {
    const head = items.slice(0, shown);
    const pinned = items.slice(shown).find(isSelected);
    return { rows: pinned ? [pinned, ...head] : head, rest: Math.max(0, items.length - shown), pinned: !!pinned };
  },
  moreButton(rest, attr = 'data-more') { return rest > 0 ? `<button type="button" class="btn more" data-variant="ghost" data-size="sm" ${attr}>${esc(this.t('btn.more'))} (남은 ${rest}건)</button>` : ''; },
  // 읽기만 하는 이름–값 한 줄(이전 단계 입력 · 변수). 여럿이 이어지면 줄이 맞게 놓인다(portal-kit.css dl.kv + dl.kv)
  readonly(label, value, sub = '') { return `<dl class="kv"><dt>${esc(label)}</dt><dd>${value}${sub ? `<p class="muted">${esc(sub)}</p>` : ''}</dd></dl>`; },

  // Human-readable labels belong to the UI; API step names and raw records stay intact.
  steps: {
    freshness: ['데이터 상태 확인', '최근 데이터가 들어오는지 확인합니다.'],
    t1_causes: ['고장 원인 조회', '경보와 증상에 연결된 원인 후보를 찾습니다.'],
    evidence: ['관측값으로 근거 확인', '센서 이력에서 각 원인을 뒷받침하는 조건을 확인합니다.'],
    rank: ['원인 후보 비교', '사전확률과 관측 근거로 원인 후보의 순위를 정합니다.'],
    t2_actions: ['조치 방법 조회', '원인에 연결된 조치, 허용 범위, 절차와 매뉴얼을 찾습니다.'],
    card: ['분석 결과 작성', '원인과 권장 조치를 근거와 함께 정리합니다.'],
    guardrail: ['제약과 근거 검증', '권고가 정해진 제약을 지키고 근거를 갖추었는지 검사합니다.'],
    submit: ['승인 절차로 전달', '판단 결과를 담당자가 검토할 수 있도록 전달합니다.'],
    enterprise: ['관련 업무 판단 연결', '설비 문제와 연결된 생산·정비·품질 판단을 실행합니다.'],
    ontology_context: ['판단에 필요한 지식 조회', '상황에 연결된 조치 방법, 성과 지표와 규정을 찾습니다.'],
    precedents: ['이전 판단 사례 확인', '같은 상황에서 사람이 승인한 선택을 살펴봅니다.'],
    info_routing: ['정보를 가진 시스템 찾기', '필요한 정보를 어느 기업 시스템에서 조회할지 확인합니다.'],
    fetch: ['기업 시스템 정보 조회', '생산·정비·품질 시스템에서 현재 정보를 읽습니다.'],
    impacts: ['대안별 영향 계산', '각 대안이 성과 지표에 미치는 금액 영향을 계산합니다.'],
    policies: ['규정 위반 확인', '제외할 대안과 불이익을 반영할 대안을 구분합니다.'],
    perspectives: ['부서와 전사 관점 비교', '부서별 목표와 회사 전체 목표에서 유리한 대안을 비교합니다.'],
    recommend: ['권고안 정리', '권고안, 선택 근거와 필요한 승인 역할을 정리합니다.'],
    error: ['처리 실패', '실패 원인은 아래 처리 기록에서 확인할 수 있습니다.'],
  },
  revealDetail(detail) {
    const split = detail.closest(".split");
    if (split && getComputedStyle(split).gridTemplateColumns.split(" ").length === 1) detail.scrollIntoView({ block: "start" });
  },
  /* ---------- 아이콘: Lucide(vendor/lucide/icons.svg — 쓰는 것만 묶은 한 파일). 이름 목록은 vendor/lucide/icons.txt, 없는 이름은 workspace/개발/scripts/portal_vendor.sh 의 ICONS 에 더한다 ---------- */
  // 옛 이름(이 포털이 손으로 그리던 아이콘) → Lucide 이름. 새로 쓰는 코드는 Lucide 이름을 그대로 적는다
  iconNames: { home: 'house', map: 'network', alert: 'triangle-alert', chart: 'chart-line', nodes: 'network', skills: 'list-checks', decision: 'scale', process: 'workflow',
    gear: 'settings', book: 'book-open', agent: 'bot', tool: 'plug', compare: 'git-compare', score: 'clipboard-check', whatif: 'calculator', kpi: 'gauge', fabric: 'database' },
  icon(name, cls = '') {
    return `<svg class="ic${cls ? ' ' + cls : ''}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><use href="vendor/lucide/icons.svg#${esc(this.iconNames[name] || name)}"/></svg>`;
  },
  // HTML 에 적어 둔 아이콘 자리([data-icon="<이름>"])에 아이콘을 그린다 — 틀(index.html)과 화면 모듈이 문자열로 svg 를 적지 않아도 된다. 같은 자리를 두 번 그리지 않는다
  fillIcons(root = document) {
    root.querySelectorAll('[data-icon]').forEach(n => { if (n.dataset.iconDone) return; n.dataset.iconDone = '1'; n.insertAdjacentHTML('afterbegin', this.icon(n.dataset.icon)); });
  },

  /* ---------- 큰 부품은 필요할 때 싣는다: await UI.need('bpmn') → 전역 BpmnJS 를 쓸 수 있다 ----------
     이름: bpmn(흐름 그림 보기 — BpmnJS) · bpmn-layout(배치 정보가 없는 BPMN 자동 배치 — BpmnAutoLayout) · graph(지식 지도 — cytoscape + fcose) · chart(시계열 차트 — uPlot)
          · markdown(마크다운 → 소독한 HTML — marked + DOMPurify) · code(구문 강조 — Prism).
     같은 부품은 한 번만 싣고(부르는 곳이 여럿이어도 같은 Promise), 못 실으면 어느 파일을 왜 못 실었는지와 함께 실패한다(조용히 넘어가지 않는다). 실패한 뒤 다시 부르면 다시 싣는다. */
  parts: {
    bpmn: { css: ['vendor/bpmn-js/diagram-js.css', 'vendor/bpmn-js/bpmn-js.css', 'vendor/bpmn-js/bpmn-font/css/bpmn.css'], js: ['vendor/bpmn-js/bpmn-navigated-viewer.production.min.js'], global: 'BpmnJS' },
    'bpmn-layout': { js: ['vendor/bpmn-auto-layout/bpmn-auto-layout.min.js', 'bpmnLayout.js'], global: 'hydBpmnLayout' },      // bpmnLayout.js: hydBpmnLayout.ensureLayout(xml) — 선의 양 끝을 채운 뒤 BpmnAutoLayout 으로 배치한다
    graph: { js: ['vendor/cytoscape/cytoscape.min.js', 'vendor/cytoscape-fcose/layout-base.js', 'vendor/cytoscape-fcose/cose-base.js', 'vendor/cytoscape-fcose/cytoscape-fcose.js'], global: 'cytoscape' },
    chart: { css: ['vendor/uplot/uPlot.min.css'], js: ['vendor/uplot/uPlot.iife.min.js'], global: 'uPlot' },
    markdown: { js: ['vendor/marked/marked.umd.js', 'vendor/dompurify/purify.min.js'], global: 'marked' },
    code: { js: ['vendor/prism/prism.min.js'], attrs: { 'data-manual': '' }, global: 'Prism' },
  },
  needing: {},
  need(name) {
    const part = this.parts[name];
    if (!part) return Promise.reject(new Error(`UI.need: 모르는 부품 이름 '${name}' — ${Object.keys(this.parts).join(' · ')} 중 하나`));
    if (this.needing[name]) return this.needing[name];
    const css = href => new Promise((ok, fail) => {
      const link = Object.assign(document.createElement('link'), { rel: 'stylesheet', href });
      link.onload = ok; link.onerror = () => { link.remove(); fail(new Error(`부품 ${name} 의 모양 파일을 싣지 못했습니다: ${href}`)); };
      // 화면별 CSS 보다 앞(키트 바로 뒤)에 둔다 — 포털의 값(portal-kit.css)이 부품의 기본 모양을 이기게
      document.head.insertBefore(link, document.head.querySelector('link[href="portal-kit.css"]'));
    });
    const js = src => new Promise((ok, fail) => {
      const script = Object.assign(document.createElement('script'), { src, async: false });
      Object.entries(part.attrs || {}).forEach(([k, v]) => script.setAttribute(k, v));
      script.onload = ok; script.onerror = () => { script.remove(); fail(new Error(`부품 ${name} 의 파일을 싣지 못했습니다: ${src}`)); };
      document.head.append(script);
    });
    // 스크립트는 적힌 차례대로 하나씩(뒤 파일이 앞 파일의 전역을 쓴다 — fcose 는 layout-base → cose-base 차례)
    const load = async () => {
      await Promise.all((part.css || []).map(css));
      for (const src of part.js) await js(src);
      if (typeof window[part.global] === 'undefined') throw new Error(`부품 ${name} 을 실었지만 전역 ${part.global} 이 없습니다 — vendor/ 의 파일이 다른 판일 수 있습니다`);
      return window[part.global];
    };
    return this.needing[name] = load().catch(e => { delete this.needing[name]; throw e; });
  },
};

/* A115 (r14 A12, process-gpt-vue3 shared/hitlFeedback humanQuestionText): a person's question card reads `text`, and an
   SDK agent's `question` when there is no text — before, an SDK question showed an empty card. */
function humanQuestionText(data) {
  return String((data && (data.text || data.question)) || "");
}
UI.loadNames();   // A141: 원문 id → 이름 사전(정적 names.json). 읽기 전에는 id 가 그대로 보이고, 화면은 주기 갱신 때 따라온다.

/* A5 (U7 포털 셸): 수강생 동선 메뉴 이름 · 새 화면 아이콘 · 토스트 · 확인 대화상자 · 로딩/오류 블록.
   덧붙이기만 한다(위 UI 객체는 그대로). 화면 규칙: workspace/개발/문서/UIUX_PLAN.md */
Object.assign(UI.terms, {
  'var.approval': '승인 여부', 'var.approval_reason': '결정 사유', 'var.result_report': '결과 보고', 'var.request_id': '요청 번호', 'var.approved_option': '승인한 안',
  'nav.agents': '에이전트 · 스킬', 'nav.compare': '에이전트 시험 비교', 'nav.flows': '흐름', 'nav.oil': '오일 분석 입력', 'nav.eval': '판단 채점',
  'nav.whatif': '조건별 손익', 'nav.kpi': '성과 지표', 'nav.fabric': '데이터 원천',
  'nav.ask': '질문하기',   // B5
  // 메뉴 여덟(index.html 주 메뉴의 data-menu)
  'nav.menu.main': '홈', 'nav.menu.instances': '처리 건', 'nav.menu.knowledge': '지식', 'nav.menu.flows': '흐름', 'nav.menu.agents': 'AI 에이전트',
  'nav.menu.plant': '유압 설비', 'nav.menu.trial': '판단 실험', 'nav.menu.system': '시스템',
  'shell.railFold': '메뉴 줄 접기', 'shell.railOpen': '메뉴 줄 펴기',
  'shell.bell': '알림', 'shell.bellCount': '새 알림 {n}건',
  'shell.mountFail': '화면을 그리지 못했습니다', 'shell.unknownRoute': '없는 화면 주소입니다. 홈으로 이동했습니다.',
  'dialog.ok': '확인', 'dialog.cancel': '취소', 'state.retry': '다시 시도',
});
(function () {
  // 읽는 중: 내용이 놓일 자리에 스켈레톤 줄 셋. 무엇을 읽는지 글을 받았으면 그 아래 한 줄로 보인다(받지 않았으면 낭독기만 읽는다).
  // 1초 안에 끝나는 읽기에만 쓴다 — 오래 걸리는 일은 과정이 흘러나오는 실시간 상자(hydLive)로 보인다(디자인 기준 7절)
  UI.loading = function (text, cls = '') {
    return `<div class="loading${cls ? ' ' + cls : ''}" role="status" aria-live="polite"><div class="skeleton sk-line" style="width:38%"></div><div class="skeleton sk-line" style="width:72%"></div><div class="skeleton sk-line" style="width:54%"></div>${text ? `<p>${esc(text)}</p>` : `<span class="sr-only">${esc(this.t('loading'))}</span>`}</div>`;
  };
  // 오류 판: 무엇을 못 했는지 + 사람이 읽을 까닭 한 줄 + (선택) 다시 시도 단추. 단추는 data-retry 로 찾아 붙인다.
  UI.errorBlock = function (title, reason = '', { retry = false, cls = '' } = {}) {
    return `<div class="alert${cls ? ' ' + cls : ''}" data-variant="destructive" role="alert">${this.icon('circle-alert')}<h2>${esc(title || this.t('error.load'))}</h2>${reason ? `<section>${esc(reason)}</section>` : ''}${retry ? `<footer><button type="button" class="btn" data-variant="outline" data-size="sm" data-retry>${esc(this.t('state.retry'))}</button></footer>` : ''}</div>`;
  };

  // 알림 한 줄(키트의 토스트 — index.html 의 #toaster): 오른쪽 아래에 잠깐 뜬다. tone = 'ok' | 'neg' | 'neutral'. 같은 문구가 겹치면 하나만 둔다.
  // 성공 · 실패의 결과만 알린다 — 진행은 토스트로 알리지 않는다(디자인 기준 4절). 돌려주는 값은 그 토스트 노드(.close() 로 닫는다)
  UI.toast = function (message, { tone = 'neutral', timeout = 4000 } = {}) {
    if (!['ok', 'neg', 'neutral'].includes(tone)) console.error(`UI.toast: 모르는 tone '${tone}' — ok · neg · neutral 중 하나`, message);   // 색이 빠진 채 조용히 지나가지 않게(W3-22)
    const host = document.getElementById('toaster');
    if (host && typeof host.toast !== 'function') window.basecoat.init('toaster');      // 문서가 다 읽히기 전에 불렸다 — 키트가 스스로 준비하기 전이라 지금 준비시킨다
    if (!host || typeof host.toast !== 'function') throw new Error('알림 자리(#toaster)가 준비되지 않았습니다 — index.html 이 vendor/basecoat/basecoat.min.js 를 ui.js 보다 먼저 싣는지 확인');
    const text = String(message ?? '');
    [...host.querySelectorAll('.toast')].filter(n => n.dataset.text === text).forEach(n => n.remove());
    const node = host.toast({ category: { ok: 'success', neg: 'error' }[tone] || 'info', title: text, duration: timeout > 0 ? timeout : -1 });
    node.dataset.text = text;
    return node;
  };

  // A161-U1 (A160 결함 11): 브라우저 기본 파일 칸("Choose File / No file chosen")을 한국어 파일 고르기(지식 관리와 같은 모양)로 바꾼다.
  // input 자체는 그대로 두고 감싸기만 하므로 각 화면의 change 처리 · files 읽기는 바뀌지 않는다.
  UI.enhanceFiles = function (root = document) {
    root.querySelectorAll('input[type=file]').forEach(input => {
      if (input.closest('.file-picker') || input.dataset.enhanced) return;
      input.dataset.enhanced = '1';
      const wrap = document.createElement('label'); wrap.className = 'file-picker';
      const btn = document.createElement('span'); btn.className = 'btn'; btn.dataset.variant = 'outline'; btn.dataset.size = 'sm'; btn.textContent = '파일 선택';
      const name = document.createElement('span'); name.className = 'file-name'; name.textContent = '선택한 파일 없음';
      input.parentNode.insertBefore(wrap, input); wrap.append(btn, input, name);
      if (!input.getAttribute('aria-label')) input.setAttribute('aria-label', '파일 선택');
      input.addEventListener('change', () => { name.textContent = input.files && input.files[0] ? input.files[0].name : '선택한 파일 없음'; });
    });
  };
  if (typeof document !== 'undefined' && document.addEventListener && typeof MutationObserver !== 'undefined') {
    const boot = () => { UI.enhanceFiles(); let t = 0; new MutationObserver(() => { if (!t) t = setTimeout(() => { t = 0; UI.enhanceFiles(); }, 50); }).observe(document.body, { childList: true, subtree: true }); };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else if (document.body) boot();
  }

  // 확인 대화상자(키트의 alert-dialog): Promise<boolean>. 위험한 행동(danger)은 확인 단추가 빨강이고, 기본 초점은 취소에 둔다. Esc 는 취소다.
  // confirm-dialog 는 모양이 아니라 찾는 이름이다(시험 · 확인 도구가 이 창을 이 이름으로 찾는다)
  UI.confirm = function ({ title = '', body = '', ok, cancel, danger = false } = {}) {
    return new Promise(resolve => {
      const dlg = document.createElement('dialog');
      dlg.className = 'alert-dialog confirm-dialog';
      dlg.innerHTML = `<form method="dialog"><header><h2>${esc(title)}</h2>${body ? `<p>${esc(body)}</p>` : ''}</header>
        <footer><button value="cancel" class="btn" data-variant="outline" autofocus>${esc(cancel || this.t('dialog.cancel'))}</button><button value="ok" class="btn" data-variant="${danger ? 'destructive' : 'primary'}">${esc(ok || this.t('dialog.ok'))}</button></footer></form>`;
      document.body.append(dlg);
      dlg.addEventListener('close', () => { dlg.remove(); resolve(dlg.returnValue === 'ok'); });
      dlg.showModal();
    });
  };
  // A work item may remain PENDING after its execution has ended. Match the
  // terminal receipt to that run so late text cannot reopen it; a new start can.
  // One envelope boundary for inline MCP results and verified stored originals.
  UI.normalizeToolOutput = (raw,contentType) => {
    if(contentType==='text') return typeof raw==='string' && raw.trim() ? {state:'text',raw,value:raw,isError:false} : {state:'invalid',raw,value:null,error:'보관된 텍스트 응답이 비어 있거나 읽을 수 없습니다',isError:false};
    let value=raw, isError=false;
    const seen=new Set();
    while (true) {
      if (value==null) return {state:'invalid',raw,value:null,error:'도구 응답 값이 없습니다',isError};
      if (typeof value==='string') {
        const text=value.trim();
        if (/^[\[{]/.test(text)) {
          try { value=JSON.parse(text); continue; }
          catch (_) { return {state:'invalid',raw,value:null,error:'구조화 응답을 JSON으로 읽을 수 없습니다',isError}; }
        }
        return {state:'text',raw,value,isError};
      }
      if (typeof value!=='object') return {state:'inline',raw,value,isError};
      if (seen.has(value)) return {state:'invalid',raw,value:null,error:'응답 봉투가 순환합니다',isError};
      seen.add(value);
      isError ||= value.is_error===true || value.isError===true || value.result==='error' || value.result==='failed';
      if (value.kind==='tool_output_preview' && value.truncated===true) return {state:'needs_full',raw,value:null,error:'미리보기는 축약됐습니다. 보관된 전체 결과를 확인하세요',isError};
      if (value.structured_content!=null || value.structuredContent!=null) { value=value.structured_content ?? value.structuredContent; continue; }
      const content=Array.isArray(value) ? value : value.content;
      if (Array.isArray(content) && content.length && content.every(x=>x?.type==='text' && typeof x.text==='string')) { value=content.map(x=>x.text).join(''); continue; }
      if (!Array.isArray(value) && Array.isArray(value.content)) return {state:'invalid',raw,value:null,error:'지원하지 않거나 비어 있는 도구 응답 블록입니다',isError};
      if (!Array.isArray(value) && Object.keys(value).length===1 && 'result' in value) { value=value.result; continue; }
      return {state:'inline',raw,value,isError};
    }
  };
  const toolPayloads=new Map();
  const payloadKey=(ev,direction='output')=>{
    const ref=ev.data?.[direction==='input' ? 'full_input' : 'full_output'];
    return JSON.stringify([ev.proc_inst_id,ref?.ref,ref?.sha256,direction]);
  };
  const payloadReference=(ev,direction)=>ev.data?.[direction==='input' ? 'full_input' : 'full_output'];
  const payloadChanged=()=>window.dispatchEvent(new CustomEvent('hyd-tool-payload'));
  const charCount=s=>Array.from(s).length;
  UI.fullToolIO = (ev,direction='output',hydrate=false) => {
    const fo=payloadReference(ev,direction), raw=ev.data?.[direction];
    if (!fo) {
      if (direction==='output' && ev.data?.output_truncated) return {state:'needs_full',raw,value:null,error:'미리보기는 축약됐지만 원문 참조가 없습니다'};
      return UI.normalizeToolOutput(raw);
    }
    if (!fo.stored || !fo.ref) return {state:'unavailable',raw,value:null,error:`원문을 보관하지 못했습니다: ${fo.error || '보관 참조 없음'}`,reference:fo};
    if (!/^[0-9a-f]{64}$/.test(fo.ref) || !ev.proc_inst_id || !ev.todo_id || !ev.job_id || !fo.sha256) return {state:'invalid',raw,value:null,error:'원문 참조 · 작업 소유권 기록이 완전하지 않습니다',reference:fo};
    const key=payloadKey(ev,direction), cached=toolPayloads.get(key);
    if (cached && cached.event.proc_inst_id!==ev.proc_inst_id) return {state:'invalid',raw,value:null,error:'원문 처리 건과 선택한 처리 건이 다릅니다',reference:fo};
    if (cached && ['ref','sha256','chars','original_chars','cut','content_type','source'].some(k=>cached.reference[k]!==fo[k])) return {state:'invalid',raw,value:null,error:'원문 보관 메타데이터가 기존 확인 기록과 다릅니다',reference:fo};
    if (!cached && hydrate) queueMicrotask(()=>UI.loadFullToolIO(ev,direction));
    return cached ? {...cached.result,reference:fo,text:cached.text} : {state:'needs_full',raw,value:null,error:'미리보기는 축약됐고 전체 결과가 보관돼 있습니다',reference:fo};
  };
  UI.loadFullToolIO = (ev,direction='output',retry=false) => {
    const fo=payloadReference(ev,direction), key=payloadKey(ev,direction);
    const prior=toolPayloads.get(key);
    if (prior && !retry) return prior.promise ? prior.promise.then(()=>UI.fullToolIO(ev,direction)) : Promise.resolve(UI.fullToolIO(ev,direction));
    if (!fo?.stored || !/^[0-9a-f]{64}$/.test(fo.ref || '') || !ev.proc_inst_id || !ev.todo_id || !ev.job_id || !fo.sha256) return Promise.resolve({state:'invalid',value:null,error:'원문 참조 · 작업 소유권 기록이 완전하지 않습니다'});
    const entry={event:ev,reference:{...fo},text:'',result:{state:'loading',raw:ev.data?.[direction],value:null,error:'보관된 원문을 읽는 중입니다'}};
    toolPayloads.set(key,entry); payloadChanged();
    entry.promise=(async()=>{
      try {
        let offset=0, total=null;
        do {
          const chunk=await getJ(`${API.process}/api/event-payloads/${encodeURIComponent(fo.ref)}?offset=${offset}&limit=200000`);
          if (chunk.id!==fo.ref || chunk.proc_inst_id!==ev.proc_inst_id) throw new Error('원문 식별자 · 처리 건 소유권이 일치하지 않습니다');
          if (chunk.source!==fo.source || chunk.meta?.original_chars!==fo.original_chars || (!fo.cut && fo.original_chars!==fo.chars)) throw new Error('원문 출처 · 원래 길이가 일치하지 않습니다');
          if (chunk.meta?.content_sha256!==fo.sha256 || chunk.content_type!==fo.content_type || chunk.meta?.cut!==!!fo.cut) throw new Error('원문 SHA · 형식 · 잘림 기록이 일치하지 않습니다');
          if (chunk.offset!==offset || typeof chunk.content!=='string' || !Number.isSafeInteger(chunk.chars) || chunk.chars!==fo.chars || (total!=null && total!==chunk.chars)) throw new Error('원문 부분 순서 · 전체 길이가 일치하지 않습니다');
          total=chunk.chars;
          const end=offset+charCount(chunk.content);
          if (end>total || (chunk.next_offset==null ? end!==total : chunk.next_offset!==end || end<=offset)) throw new Error('원문 페이지 경계가 일치하지 않습니다');
          entry.text+=chunk.content; offset=chunk.next_offset;
        } while (offset!=null);
        if (charCount(entry.text)!==fo.chars) throw new Error('원문 전체 길이가 일치하지 않습니다');
        if (!window.crypto?.subtle) throw new Error('이 주소에서는 원문 SHA 검증을 사용할 수 없습니다');
        const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(entry.text));
        const sha=Array.from(new Uint8Array(bytes),x=>x.toString(16).padStart(2,'0')).join('');
        if (sha!==fo.sha256) throw new Error('읽은 원문의 SHA가 보관 기록과 다릅니다');
        if (fo.cut) entry.result={state:'truncated',raw:entry.text,value:null,error:'보관 한도에서 원문이 잘렸습니다. 전체 결과를 판정할 수 없습니다'};
        else if (fo.content_type==='json') {
          let parsed; try { parsed=JSON.parse(entry.text); } catch (_) { throw new Error('보관된 원문이 유효한 JSON이 아닙니다'); }
          entry.result={...UI.normalizeToolOutput(parsed),state:'complete'};
          if (entry.result.error) entry.result.state='invalid';
        } else if(fo.content_type==='text') {
          entry.result=UI.normalizeToolOutput(entry.text,'text');
          if(!entry.result.error) entry.result.state='complete';
        } else throw new Error('보관된 원문의 형식을 지원하지 않습니다');
      } catch (err) { entry.result={state:'unavailable',raw:entry.text,value:null,error:err.status===404 ? '보관된 원문이 없습니다 (삭제되었거나 접근 권한 없음)' : err.message}; }
      finally { entry.promise=null; payloadChanged(); }
      return entry.result;
    })();
    return entry.promise;
  };
  UI.toolAsk = (ev,hydrate=false) => {
    const io=UI.fullToolIO(ev,'input',hydrate);
    return {...io,summary:['inline','text','complete'].includes(io.state) ? window.hydWords ? hydWords.ask(ev.data?.tool,io.value) : '도구 요청 목적 기록 없음 · 원문 확인' : io.error};
  };
  UI.toolResult = (ev,hydrate=false) => {
    const io=UI.fullToolIO(ev,'output',hydrate), data=ev.data || {};
    if (data.attempt_failed) return {...io,status:'fail',badge:'실패한 시도',summary:'도구 실행이 실패했습니다'};
    if (!['inline','text','complete'].includes(io.state)) return {...io,status:data.is_error ? 'fail' : 'warn',badge:io.state==='loading' ? '원문 읽는 중' : '원문 확인 필요',summary:io.error};
    const outcome=UI.outcome(io.value,data.is_error || io.isError);
    if (UI.toolKey(data.tool)==='mcp__hyd-effects__send_mail' && outcome.tone==='ok' && !window.hydWords?.mailReceipt(io.value)) return {...io,status:'warn',badge:'발송 영수증 확인 필요',summary:'메일 발송 영수증을 확인할 수 없습니다'};
    if(io.reference?.content_type==='text' && outcome.tone==='ok') return {...io,status:'ok',badge:'텍스트 응답 확인',summary:`도구 텍스트 응답 · ${UI.clean(io.value.split('\n')[0]).slice(0,160)}`};
    const failed=window.hydWords?.purchaseTool(data.tool) && hydWords.purchaseFailed(io.value);
    return {...io,status:failed ? 'fail' : outcome.tone==='ok' ? 'ok' : outcome.tone,badge:failed ? '구매 요청 처리 실패' : outcome.label,
      summary:outcome.tone==='blocked' ? outcome.text : outcome.tone==='fail' ? typeof io.value?.message==='string' ? UI.clean(io.value.message) : '도구가 오류를 반환했습니다' : window.hydWords ? hydWords.got(data.tool,io.value) : ''};
  };
  UI.fullToolIOHtml = (ev,direction='output') => {
    const fo=payloadReference(ev,direction); if(!fo)return '';
    const io=UI.fullToolIO(ev,direction,true), label=direction==='input' ? '전달한 입력 전문' : '보관된 결과 전문';
    const raw=io.text || (io.state==='complete' && io.raw!=null ? typeof io.raw==='string' ? io.raw : JSON.stringify(io.raw,null,2) : '');
    const key=payloadKey(ev,direction);
    return `<div class="tr-code" data-tool-payload data-tool-ref="${esc(fo.ref || '')}" data-tool-direction="${esc(direction)}" data-tool-payload-state="${esc(io.state)}"><div class="tr-code-h">${esc(label)} · ${esc(fo.chars ?? '길이 미확인')}자</div>${io.error ? `<p class="muted">${esc(io.error)}</p>` : ''}${raw ? `<details class="fold" data-k="payload:${esc(key)}"><summary>원문</summary><div class="fold-body"><pre class="code">${esc(raw)}</pre></div></details>` : ''}${['unavailable','invalid'].includes(io.state) && fo.stored ? `<button type="button" class="btn" data-variant="outline" data-size="sm" data-tool-payload-retry="${esc(key)}">원문 다시 읽기</button>` : ''}</div>`;
  };
  if(typeof document!=='undefined' && document.addEventListener) document.addEventListener('click',event=>{
    const button=event.target.closest('[data-tool-payload-retry]'); if(!button)return;
    const entry=toolPayloads.get(button.dataset.toolPayloadRetry); if(entry) UI.loadFullToolIO(entry.event,JSON.parse(button.dataset.toolPayloadRetry)[3],true);
  });
  UI.recordedDecision = (decision, recorded, id) => {
    if (!id || decision?.id!==id) return null;
    if (!recorded) return decision;
    const matches = d => d?.id===id && (!recorded.recommended || d.recommended===recorded.recommended) &&
      (recorded.order || []).every(o=>(d.options || []).some(x=>x.id===o.id && (o.rank==null || x.rank===o.rank) && (o.score==null || x.score===o.score)));
    return [decision.original_decision,decision].find(matches) || null;
  };
  UI.taskExecution = (w, events = [], instance = {}) => {
    const relevant = events.filter(ev => ev.todo_id === w.id);
    const ordered = [...relevant].sort((a,b) => String(a.timestamp || '').localeCompare(String(b.timestamp || '')));
    const terminals = new Set(['task_deferred','task_completed','task_cancelled','task_failed']);
    const runId = ev => ev.data?.receipt?.id || String(ev.job_id || '').replace(/^deferral:/,'');
    const starts = ordered.filter(ev => ev.event_type === 'task_started');
    const latestStart = starts.at(-1);
    const terminal = [...ordered].reverse().find(ev => terminals.has(ev.event_type) &&
      (!latestStart || runId(ev) === runId(latestStart)) &&
      (!latestStart || String(ev.timestamp || '') >= String(latestStart.timestamp || '')));
    const eligible = instance.status === 'RUNNING' && ['IN_PROGRESS','SUBMITTED','PENDING','NEW'].includes(w.status);
    const agent = !!(w.agent_orch || w.agent_mode);
    const awaiting = eligible && agent && !latestStart && !terminal;
    return { live: eligible && !terminal && !awaiting, awaiting,
      terminal: terminal || null };
  };
})();

// [data-go-tab="화면 이름"] 단추: 다음 할 일이 있는 화면으로 옮긴다(빈 화면 · 완료 안내 · 사본을 지운 자리의 「이제 어디서 하는가」 링크가 함께 쓴다 — UI.emptyGo)
if (typeof document !== 'undefined') document.addEventListener('click', e => { const b = e.target.closest && e.target.closest('[data-go-tab]'); if (b && typeof selectTab === 'function') selectTab(b.dataset.goTab); });
