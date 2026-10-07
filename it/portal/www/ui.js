/* Shared presentation helpers. API identifiers stay unchanged — only on-screen wording lives here.
   A122 (docs/handoff/UIUX_PLAN.md §2 명칭표 · §3 공통 컴포넌트 · §5.2 상태): every user-facing phrase comes from UI.terms,
   every status chip from UI.chip(), every form field from UI.field(). Change the wording here and all screens follow. */
const UI = {
  /* ---------- 명칭표 (UIUX_PLAN §2) — 화면 문구만. 코드·API·DB 이름은 그대로다. ---------- */
  terms: {
    // 메뉴 · 헤더
    'nav.main': '홈', 'nav.home': '시스템 구성', 'nav.scenario': '결함 시뮬레이션', 'nav.incidents': '이상 확인 · 조치', 'nav.trends': '실시간 모니터링',
    'nav.ontology': '지식 지도', 'nav.skills': '조치 방법', 'nav.decision': '조치 판단 규칙', 'nav.process': '승인과 실행', 'nav.instances': '처리 건',
    'nav.knowledge': '지식 관리', 'nav.admin': '관리',
    'nav.group.plant': '설비', 'nav.group.decide': '판단과 처리', 'nav.group.manage': '관리',
    'header.services': '서비스', 'header.noResponse': '응답 없음', 'header.connected': '연결됨', 'header.connecting': '연결 중', 'header.waiting': '연결됨 · 대기', 'header.disconnected': '끊김 · 재연결 중', 'header.streamOff': '실시간 꺼짐 (기본 처리 모드)',
    'header.open': '진행 중', 'header.simTime': '시뮬레이션 시각', 'header.scale': '시간 배율', 'header.simBadge': '시뮬레이션', 'header.menu': '메뉴',
    // 공통 단위
    'case': '사건', 'instance': '처리 건', 'step': '단계', 'myTurn': '내 차례', 'agent': 'AI 에이전트', 'operator': '운전원', 'system': '시스템',
    'candidate': '조치 후보', 'decision': '결정', 'decisions': '판단 결과', 'method': '조치 방법', 'select': '조치 선택', 'escalate': '책임자 확인',
    'reobserve': '효과 확인', 'reobserve15': '효과 확인 (15분)', 'workOrder': '정비 요청', 'command': '설비에 명령', 'control': '설비 제어', 'ack': '설비 응답',
    'alert': '설비 경보', 'closed': '종결', 'done': '완료', 'knowledge': '지식', 'rule': '규칙', 'kpi': '성과 지표',
    // 버튼
    'btn.decide': '결정', 'btn.approve': '승인', 'btn.reject': '반려', 'btn.submit': '제출', 'btn.answer': '답변', 'btn.rework': '다시 수행', 'btn.confirm': '확인',
    'btn.preview': '예측 다시 보기', 'btn.effects': '영향 보기', 'btn.reassess': '다시 평가', 'btn.reload': '다시 읽기', 'btn.save': '저장', 'btn.cancel': '변경 취소',
    'btn.run': '판단 실행', 'btn.running': '판단 중…', 'btn.all': '전체 보기', 'btn.fit': '전체 흐름 보기', 'btn.unfit': '읽기 편한 크기로 보기', 'btn.more': '더 보기',
    'btn.retry': '같은 내용 다시 전달', 'btn.closeTask': '단계 닫기', 'btn.cancelTask': '실행 취소', 'btn.goInstance': '처리 건에서 선택하기 →',
    // 폼 라벨
    'form.by': '담당자', 'form.role': '역할', 'form.reason': '사유', 'form.note': '메모', 'form.answer': '답변', 'form.fan': '팬 속도', 'form.load': '펌프 부하', 'form.pump': '운전 펌프',
    'form.section.case': '사건', 'form.section.choice': '선택', 'form.section.who': '사유 · 담당', 'form.required': '필수',
    'form.hint.role': '카드의 승인 역할 이상이어야 합니다', 'form.hint.reason': '왜 이 조치를 고르는지 한 줄로 적습니다', 'form.hint.preview': '조치값을 바꿨으면 예측을 다시 본 뒤 결정합니다',
    'form.hint.answer': '답변은 같은 단계에서 이어서 반영됩니다', 'form.useCurrent': '현재 값 사용', 'form.pickRole': '역할 선택',
    'form.timeout': '10분 안에 고르지 않으면 책임자에게 넘어갑니다', 'form.deadline': '기한',
    'form.err.required': '필수 항목을 입력하세요', 'form.err.reason': '사유를 입력하세요', 'form.err.byRole': '담당자와 역할을 입력하세요', 'form.err.byRoleReason': '담당자 · 역할 · 사유를 입력하세요',
    // 카드 칩
    'chip.recommended': '추천', 'chip.chosen': '결정', 'chip.excluded': '제외', 'chip.control': '설비 제어', 'chip.workOrder': '정비 요청',
    'card.score': '점수', 'card.approver': '승인', 'card.precedent': '과거 같은 선택', 'card.forecastTs1': '예상 유온', 'card.evidence': '근거 보기', 'card.expected': '예상 영향',
    'card.scoreHow': '점수 계산 방법', 'card.reviewed': '검토한 조치값', 'card.baseSop': '기준 절차', 'card.forecastLimits': '예측 조건과 한계', 'card.steps': '절차',
    'card.penalty': '감점', 'card.warn': '경고', 'card.noAction': '세부 동작 없음',
    'score.bsc': '성과 지표', 'score.forecast': '예측', 'score.warn': '경고', 'score.penalty': '감점', 'score.precedent': '과거 선택', 'score.delivery': '납기', 'score.quality': '품질',
    // 조치 판단 규칙
    'dec.conditions': '판단 조건', 'dec.asset': '설비', 'dec.pattern': '이상 패턴', 'dec.mode': '운전 모드', 'dec.state': '설비 상태', 'dec.fan': '팬 100 % 누적 (시간)', 'dec.standby': '예비 펌프',
    'dec.standbyReady': '가용', 'dec.standbyBusy': '정비 중', 'dec.empty': '설비와 이상 패턴을 고르고 판단을 실행하세요', 'dec.loading': '규칙을 사실에 대어 보는 중…',
    'dec.cause': '원인', 'dec.causeTop': '판정', 'dec.causeMore': '다른 원인 후보', 'dec.candidates': '조치 후보', 'dec.rules': '적용한 규칙', 'dec.inputs': '판단에 쓴 값', 'dec.trace': '처리 과정',
    'dec.summaryMore': '자세히', 'dec.fired': '발동', 'dec.notApplicable': '해당 없음', 'dec.noFact': '사실 없음', 'dec.ruleSelect': '후보 선택', 'dec.ruleCompliance': '규정 적합성',
    'dec.col.rule': '규칙', 'dec.col.target': '대상', 'dec.col.result': '결과', 'dec.col.input': '입력 데이터', 'dec.col.source': '출처', 'dec.col.value': '값', 'dec.col.how': '가져온 방법',
    'dec.failed': '판단 실패', 'dec.noPatterns': '이상 패턴을 불러오지 못했습니다',
    // 이상 확인 · 조치
    'inc.select': '설비를 선택하세요', 'inc.selectSub': '위 설비 카드를 누르면 사건과 조치 과정이 보입니다', 'inc.noAlert': '경보 없음', 'inc.noAlertSub': '결함을 주입하면 여기에 나타납니다',
    'inc.noCase': '사건 없음', 'inc.list': '사건', 'inc.listAll': '전체 사건', 'inc.progress': '조치 과정', 'inc.evidence': '분석 근거', 'inc.agentTrace': '에이전트 처리 과정', 'inc.log': '기록',
    'inc.decisionCard': '결정', 'inc.waiting': '조치 후보를 만드는 중…', 'inc.noCandidates': '고를 조치 후보가 없습니다', 'inc.alertAt': '경보', 'inc.approvedBy': '승인',
    'inc.runOnly': '분석만 있음', 'inc.noTrace': '이 경보의 에이전트 처리 기록이 없습니다', 'inc.noGuide': '아직 분석 결과가 없습니다', 'inc.freshness': '데이터 상태', 'inc.fresh': '정상', 'inc.stale': '신뢰 불가',
    'inc.causes': '가능한 원인', 'inc.recommended': '권장 조치', 'inc.range': '허용 범위', 'inc.constraints': '제약', 'inc.noEvidence': '증거 규칙 없음', 'inc.unknown': '판정 미확인', 'inc.pass': '조건 충족', 'inc.fail': '조건 미충족',
    'inc.observed': '관측', 'inc.woPending': '정비 요청 발행 대기', 'inc.reasonLabel': '사유',
    // 처리 건
    'inst.running': '진행 중', 'inst.myTurn': '내 차례', 'inst.asked': '질문', 'inst.activity': '에이전트 활동', 'inst.list': '처리 건', 'inst.recent': '최근 50건', 'inst.filterRunning': '진행 중', 'inst.filterDone': '완료',
    'inst.empty': '아직 처리 건이 없습니다', 'inst.emptySub': '경보가 나면 여기에 나타납니다', 'inst.select': '처리 건을 선택하세요', 'inst.selectSub': '결과 · 흐름 · 기록을 볼 수 있습니다',
    'inst.noTodo': '지금 할 일이 없습니다', 'inst.noTodoSub': '차례가 오면 여기에 나타납니다', 'inst.off': '처리 건 기능이 꺼져 있습니다. 관리자에게 문의하세요.', 'inst.noConn': '처리 서비스에 연결할 수 없습니다',
    'inst.tab.result': '결과', 'inst.tab.flow': '흐름', 'inst.tab.log': '기록', 'inst.started': '시작', 'inst.ended': '종료', 'inst.justStarted': '방금 시작', 'inst.elapsed': '분 경과', 'inst.took': '분 만에',
    'inst.values': '값', 'inst.initial': '시작 값', 'inst.steps': '단계', 'inst.events': '에이전트 활동', 'inst.graph': '지식 반영', 'inst.now': '지금', 'inst.next': '다음', 'inst.finished': '끝',
    'inst.stepsDone': '단계 완료', 'inst.waitingResult': '새 결과를 기다리는 단계', 'inst.endWaiting': '일부 경로가 종료 지점에 닿았습니다. 남은 단계가 끝나면 처리 건이 종료됩니다.',
    'inst.approval': '승인 전달', 'inst.effects': '이전 조치의 영향', 'inst.rework': '다시 수행', 'inst.reworkHistory': '다시 수행 이력', 'inst.reassess': '다시 평가', 'inst.woFailed': '정비 요청 전달 실패',
    'inst.gen': '차', 'inst.askTitle': '에이전트의 질문', 'inst.askWait': '질문을 읽는 중…', 'inst.loadingCards': '조치 후보를 불러오는 중…', 'inst.noForm': '이 단계의 입력 양식을 찾을 수 없습니다',
    'inst.followWo': '함께 발행될 정비 요청', 'inst.source.input': '시작 값', 'inst.source.runtime': '시스템', 'inst.source.none': '출처 없음', 'inst.structured': '구조화된 값', 'inst.noValue': '값 없음',
    'inst.noResult': '아직 결정된 조치가 없습니다', 'inst.noResultSub': '단계가 끝나면 결과가 여기에 나타납니다',
    'var.asset': '설비', 'var.pattern': '이상 패턴', 'var.cause': '원인', 'var.failure_mode': '고장 유형', 'var.chosen_skill': '고른 조치', 'var.chosen_skill_kind': '조치 종류', 'var.recovered': '회복', 'var.work_order': '정비 요청', 'var.note': '메모', 'var.approved_by': '승인자', 'var.approved_role': '승인 역할', 'var.alert_id': '경보',
    'inst.output': '출력', 'inst.gateway': '분기 판정', 'inst.due': '기한', 'inst.prevTask': '이전 단계', 'inst.inputs': '전달된 값', 'inst.raw': '원문',
    'inst.projectionPending': '반영 대기', 'inst.projectionAll': '사건 · 판단 반영 대기 (전체)', 'inst.projectionNone': '조회하지 못함', 'inst.query': '질의 보기',
    'inst.stepTable.step': '단계', 'inst.stepTable.status': '상태', 'inst.stepTable.who': '누가', 'inst.stepTable.when': '시각', 'inst.stepTable.result': '결과',
    'inst.closeReason': '이 단계를 닫는 사유', 'inst.cancelReason': '실행을 취소하는 사유',
    // 승인과 실행
    'proc.flow': '업무 흐름', 'proc.list': '판단 결과', 'proc.empty': '아직 제출된 판단이 없습니다', 'proc.emptySub': '경보가 나면 에이전트가 조치 후보를 제출합니다', 'proc.select': '판단을 선택하세요',
    'proc.manual': '수동 실행', 'proc.override': '추천과 다른 선택', 'proc.submitted': '제출', 'proc.executions': '실행 결과', 'proc.history': '이력', 'proc.systems': '기업 시스템 현황', 'proc.tx': '시스템 실행 이력',
    'proc.noChange': '변경 없음', 'proc.noTx': '아직 실행 이력이 없습니다', 'tx.beforeAfter': '변경 전·후', 'tx.col.field': '항목', 'tx.col.before': '변경 전', 'tx.col.after': '변경 후', 'tx.noDiff': '바뀐 값 없음', 'tx.created': '새로 만듦', 'proc.noEnt': '기업 시스템에 연결할 수 없습니다', 'proc.listError': '판단 목록을 갱신할 수 없습니다. 마지막으로 받은 목록입니다.',
    'proc.flowEmpty': '판단을 선택하면 진행 상태가 표시됩니다', 'proc.flowManual': '수동 실행 판단은 진행 상태가 없습니다', 'proc.approving': '승인 중…', 'proc.rejecting': '반려 중…',
    'proc.legend.done': '완료', 'proc.legend.now': '진행 중', 'proc.legend.stop': '중단', 'proc.legend.skipped': '건너뜀',
    'sys.MES': '생산 주문', 'sys.CMMS': '정비 요청', 'sys.ERP': '구매 · 출하', 'sys.QMS': '품질 처분', 'sys.EMS': '에너지 제어',
    // 설비
    'plant.ts1': '유온', 'plant.ce': '냉각 효율', 'plant.cp': '냉각 능력', 'plant.fan': '팬 속도', 'plant.load': '펌프 부하', 'plant.ps1': '토출 압력', 'plant.fs1': '유량', 'plant.vs1': '팬 진동', 'plant.pump': '운전 펌프',
    'plant.health': '쿨러 성능 비율', 'plant.phase': '경보', 'plant.state': '설비 상태', 'plant.lastCmd': '최근 명령 결과', 'plant.trip': '보호 정지 기준 65 °C', 'plant.spark': '압력 추이 · 1초 간격',
    'plant.faults': '결함 실험', 'plant.modes': '운전 모드', 'plant.manual': '수동 조작 · 적용 시 원격 수동으로 전환', 'plant.recentCmd': '최근 제어 요청 결과', 'plant.noCmd': '아직 명령 기록이 없습니다',
    'plant.noConn': '설비 시뮬레이터에 연결할 수 없습니다', 'plant.noConnSub': '연결되면 자동으로 다시 표시됩니다', 'plant.scaleNote': '설비 시뮬레이션 배율입니다. 탐지와 효과 확인 시간은 서비스 시작 시 설정한 배율을 씁니다.',
    'plant.standby': '예비', 'plant.none': '아직 없음', 'plant.faultOn': '결함 진행 중', 'plant.current': '현재 상태',
    // 홈
    'main.assets': '설비', 'main.openCases': '열린 사건', 'main.knowledge': '지식 항목', 'main.scale': '시간 배율', 'main.go.scenario': '결함 시뮬레이션', 'main.go.incidents': '이상 확인 · 조치', 'main.go.instances': '처리 건',
    'main.go.scenario.sub': '설비에 결함을 넣고 경보를 봅니다', 'main.go.incidents.sub': '사건의 원인과 조치 과정을 봅니다', 'main.go.instances.sub': '내 차례와 처리 흐름을 봅니다',
    'main.hot': '고온 · 정지', 'main.cool': '모든 설비 유온 55 ℃ 미만', 'main.noConn': '설비 연결 끊김', 'main.none': '없음', 'main.links': '연결', 'main.waitNeo': '지식 저장소 연결 대기',
    'main.liveTs1': '실시간 유온', 'main.zoom': '도식 확대', 'main.unzoom': '화면에 맞추기', 'main.check': '설비 상태 확인', 'main.arch': '시스템 구성 보기',
    // 지식 지도 · 지식 관리 · 조치 방법
    'onto.stats': '항목 {n} · 연결 {e} · 조치 방법 {s} · 규칙 {r} · 성과 지표 {k}', 'onto.path': '강조 경로 {n}개', 'onto.found': '검색 결과 {n}개', 'onto.scroll': '지도 안에서 좌우로 이동',
    'onto.hint': '항목을 누르면 연결된 관계가 강조됩니다', 'onto.out': '나가는 관계', 'onto.in': '들어오는 관계', 'onto.loadFail': '지식을 불러올 수 없습니다', 'onto.loadFailSub': '연결을 확인하고 다시 읽기를 누르세요',
    'kn.manual': '매뉴얼 등록', 'kn.ddl': '업무 데이터 연결', 'kn.query': '질의 보기', 'kn.pickFile': '파일 선택', 'kn.noFile': '선택한 파일 없음', 'kn.preview': '미리보기', 'kn.by': '담당자',
    'kn.docs': '등록된 매뉴얼', 'kn.docsEmpty': '등록된 매뉴얼이 없습니다', 'kn.docsEmptySub': '위에서 매뉴얼 파일을 골라 미리보기 뒤 적재하면 여기에 나타납니다', 'kn.history': '매뉴얼 등록 이력',
    'kn.current': '현재 판본', 'kn.previous': '이전 판본', 'kn.rolledBack': '되돌림', 'kn.revise': '이 문서 개정', 'kn.undo': '이 판본 되돌리기', 'kn.sections': '절', 'kn.procedures': '조치 방법', 'kn.steps': '단계',
    // 이 문서로 답할 수 있는 질문 (A118 골든 퀘스천 — 화면 문구만)
    'golden.title': '이 문서로 답할 수 있는 질문', 'golden.questions': '질문', 'golden.questionsHint': '한 줄에 하나 · 최대 20개 · 이 문서를 읽은 뒤 답할 수 있어야 하는 질문을 적습니다',
    'golden.ask': '확인 요청', 'golden.asking': '요청 중…', 'golden.askMore': '다른 질문 확인하기', 'golden.pending': '진행 중', 'golden.correcting': '교정 중', 'golden.done': '완료', 'golden.failed': '실패',
    'golden.checking': '질문 {n}개를 지식에 대어 보는 중…', 'golden.checkingSub': 'AI 에이전트가 이 문서가 넣은 지식만으로 답하는지 확인합니다', 'golden.none': '아직 확인한 질문이 없습니다',
    'golden.answerable': '답할 수 있음', 'golden.partial': '일부', 'golden.notYet': '아직 못 함', 'golden.grounded': '근거 있음', 'golden.confidence': '확신도',
    'golden.conf.high': '높음', 'golden.conf.medium': '보통', 'golden.conf.low': '낮음', 'golden.evidence': '근거 보기', 'golden.cited': '인용한 지식 항목', 'golden.noCited': '인용한 항목 없음', 'golden.query': '질의 보기',
    'golden.err.empty': '질문을 한 줄 이상 적으세요', 'golden.err.many': '질문은 최대 20개입니다', 'golden.err.load': '확인 결과를 읽지 못했습니다', 'golden.corrections': '형식 교정 {n}회',
    'inst.resultFile': '결과 파일로 제출',
    // A141 다이어트: 보조 정보 접기 · 에이전트 도구 이름 · 정의 이름
    'fold.meta': '상세 정보', 'fold.case': '사건 정보', 'fold.kpi': '성과 지표 영향', 'fold.penalty': '감점 · 경고', 'fold.violations': '제외 사유', 'golden.summary': '집계 · 요약',
    'inst.eventsMore': '이전 활동 더 보기', 'inst.valuesFold': '값', 'card.sop': '절차 번호', 'log.raw': '원문',
    'def.anomaly_response': '설비 이상 조치', 'def.manual_extraction': '매뉴얼 추출', 'def.golden_questions': '매뉴얼 확인 질문', 'def.timeseries_question': '시계열 질문', 'def.business_question': '업무 질문', 'def.rule_question': '규칙 질문',
    'tool.Write': '파일 쓰기', 'tool.Read': '파일 읽기', 'tool.Edit': '파일 수정', 'tool.Glob': '파일 찾기', 'tool.Grep': '내용 검색', 'tool.PowerShell': '명령 실행', 'tool.Bash': '명령 실행', 'tool.ToolSearch': '도구 검색', 'tool.WebFetch': '웹 읽기', 'tool.WebSearch': '웹 검색', 'tool.Agent': '하위 에이전트',
    'tool.mcp__neo4j__read_neo4j_cypher': '지식 그래프 조회', 'tool.mcp__neo4j__write_neo4j_cypher': '지식 그래프 쓰기', 'tool.mcp__neo4j__get_neo4j_schema': '지식 그래프 구조 조회',
    'tool.mcp__hyd-dmn__timeseries_query': '시계열 조회', 'tool.mcp__hyd-dmn__timeseries_schema': '시계열 구조 조회', 'tool.mcp__hyd-dmn__dmn_rules': '판단 규칙 조회', 'tool.mcp__hyd-dmn__evaluate_cards': '조치 후보 평가', 'tool.mcp__hyd-dmn__diagnose': '원인 진단',
    'tool.mcp__hyd-dmn__gather_facts': '사실 수집', 'tool.mcp__hyd-dmn__inputs': '판단 입력 조회', 'tool.mcp__hyd-dmn__prometheus_metadata': '지표 목록 조회', 'tool.mcp__hyd-dmn__prometheus_query': '지표 조회', 'tool.mcp__hyd-dmn__prometheus_series': '지표 시계열 조회', 'tool.mcp__hyd-dmn__precedents': '과거 선택 조회', 'tool.mcp__hyd-dmn__submit_decision': '판단 제출',
    'tool.mcp__enterprise__query': '업무 데이터 조회', 'tool.mcp__enterprise__describe_catalog': '업무 데이터 목록', 'tool.mcp__enterprise__describe_schema': '업무 데이터 구조', 'tool.mcp__enterprise__mes_orders': '생산 주문 조회', 'tool.mcp__enterprise__erp_contract': '계약 조회', 'tool.mcp__enterprise__erp_inventory': '재고 조회',
    'skill.list': '조치 방법', 'skill.new': '새 조치 방법', 'skill.select': '조치 방법을 선택하세요', 'skill.name': '이름', 'skill.desc': '설명', 'skill.approver': '승인 역할', 'skill.kind': '종류',
    'skill.kind.control': '설비 제어', 'skill.kind.workOrder': '정비 요청', 'skill.rel.remedy': '근본 조치', 'skill.rel.mitigate': '즉시 완화', 'skill.sop': '절차 번호', 'skill.fm': '대상 고장 유형', 'skill.relation': '관계',
    'skill.steps': '절차 — 한 줄에 한 단계', 'skill.stepsTitle': '절차', 'skill.linked': '연결된 지식', 'skill.causes': '해당 원인', 'skill.actions': '세부 동작', 'skill.rules': '적용 규칙', 'skill.affects': '영향 지표',
    'skill.allCauses': '고장 유형의 모든 원인', 'skill.noSteps': '절차 없음', 'skill.none': '없음', 'skill.noFm': '대상 고장 유형 없음', 'skill.add': '추가', 'skill.unsaved': '저장하지 않은 변경 사항',
    'skill.saved': '저장했습니다', 'skill.nameRequired': '이름을 입력하세요', 'skill.fromDoc': '등록한 매뉴얼에서 만든 조치 방법입니다. 매뉴얼 개정 화면에서 수정합니다.', 'skill.openDoc': '매뉴얼 개정 열기',
    // 스트림
    'stream.title': '에이전트 활동', 'stream.filter.all': '전체', 'stream.filter.tool': '도구', 'stream.filter.task': '단계', 'stream.filter.human': '사람', 'stream.filter.error': '오류', 'stream.filter.work': '진행',
    'stream.pause': '멈춤', 'stream.resume': '다시 흐르게', 'stream.empty': '아직 활동이 없습니다', 'stream.emptySub': '에이전트가 일하면 여기에 실시간으로 나타납니다', 'stream.all': '모두 보기',
    'stream.tool': '도구', 'stream.toolDone': '도구 결과', 'stream.start': '단계 시작', 'stream.done': '단계 완료', 'stream.working': '진행', 'stream.cancel': '단계 취소', 'stream.deferred': '보류', 'stream.reassess': '다시 평가 요청',
    'stream.asked': '사람에게 질문', 'stream.answered': '사람의 답변', 'stream.error': '오류', 'stream.model': '모델 응답 중', 'stream.tokens': '토큰', 'stream.cancelReq': '실행 취소 요청 (사람)', 'stream.closed': '단계 닫음 (사람)', 'stream.stopped': '실행 멈춤',
    // 흐름도 (정의 이름 → 화면 이름, UIUX_PLAN §4.1)
    'flow.lane.agent': '에이전트', 'flow.lane.human': '담당자', 'flow.lane.system': '시스템',
    'flow.name.경보 수신': '설비 경보', 'flow.name.원인 진단': '원인 진단', 'flow.name.조치 후보 조회': '조치 후보 조회', 'flow.name.규정 검토': '규정 검토', 'flow.name.우선순위 · 카드 작성': '조치 후보 정리',
    'flow.name.조치 카드 선택 (HITL)': '조치 선택', 'flow.name.상급자 호출': '책임자 확인', 'flow.name.PLC 명령 발행': '설비에 명령', 'flow.name.재관측 (15분)': '효과 확인 (15분)', 'flow.name.정비 작업지시': '정비 요청',
    'flow.name.선택 시간 초과': '선택 시간 초과', 'flow.name.종결': '종결', 'flow.name.에스컬레이션 종료': '책임자 확인으로 종료',
    'flow.name.즉시 제어 포함?': '설비 제어가 있나?', 'flow.name.회복?': '회복됐나?',
    'flow.name.escalate': '책임자 확인', 'flow.name.triage': '현장 검토', 'flow.name.end': '종료', 'flow.name.closed': '종결', 'flow.name.escalated': '책임자 확인으로 종료', 'flow.name.closed-by-human': '사람이 닫음', 'flow.name.rejected': '반려', 'flow.name.accepted': '승인',
    'flow.seq.선택 스킬 kind == control': '설비 제어', 'flow.seq.선택 스킬 kind == work_order': '정비 요청만', 'flow.seq.TS1 < 55 and 경보 해제': '회복', 'flow.seq.미회복': '미회복',
    // 일반
    'empty.noData': '없음', 'loading': '불러오는 중…', 'error.load': '불러오지 못했습니다', 'more': '자세히', 'raw': '원문', 'yes': '예', 'no': '아니요', 'and': '·',
  },
  t(key, vars) {
    let s = Object.prototype.hasOwnProperty.call(this.terms, key) ? this.terms[key] : key;
    if (vars) for (const [k, v] of Object.entries(vars)) s = s.replace('{' + k + '}', v);
    return s;
  },
  /* definition names (process definition JSON) → display names; the definition itself is not changed */
  flowName(name) { return this.terms['flow.name.' + name] || name; },
  flowSeq(name) { return this.terms['flow.seq.' + name] || name || ''; },
  defName(id) { const base = String(id || '').split('.')[0]; return this.terms['def.' + base] || base.replace(/_/g, ' '); },
  toolName(t) { const raw = String(t || ''); return this.terms['tool.' + raw] || raw.replace(/^mcp__/, '').replace(/__/g, ' · '); },

  /* ---------- A141 원문 id → 이름 (names.json: scripts/portal_names.py 가 Neo4j 실제 이름으로 생성) ----------
     응답에 이름이 있으면 그것을 쓰고, 없을 때만 이 사전으로 바꾼다. 사전에 없는 id 는 그대로 둔다(지어내지 않음). */
  names: {}, namesVersion: 0,
  ID_RE: /\b(?:fm|cause|rule|skill|sym|ap|evd|msr|sv|dec|dt|act|part|sup|comp|sens|actr|role|org|sys|asset|obj|persp|ks|ms|step|ev|src|proc|task|gw|inp|xv|fc):[A-Za-z0-9_][A-Za-z0-9_.:-]*/g,
  name(id) { return (id && this.names[id]) || id || ''; },
  idText(text) { return String(text ?? '').replace(this.ID_RE, m => this.names[m] || m); },
  async loadNames() {
    try { const r = await fetch('names.json', { cache: 'no-store' }); if (r.ok) { this.names = await r.json(); this.namesVersion = Object.keys(this.names).length; } } catch (e) { /* 사전이 없으면 id 그대로 보인다 */ }
  },

  /* ---------- A141 단계 로그(영문) → 화면 문구. 원문은 호출하는 쪽이 접기에 보존한다. ---------- */
  logPatterns: [
    [/^cancelled: instance ended \((?:ev:)?([\w-]+)\)$/, (m, U) => `처리 건 종료(${U.flowName(m[1])})로 취소`],
    [/^cancelled: (?:ev:|task:)?([\w-]+) completed first;?$/, m => m[1] === 'select-timeout' ? '선택 시간 초과가 먼저 와서 취소' : '다른 갈래가 먼저 끝나 취소'],   // A147: 경계 타이머 경쟁
    [/^human approval accepted; delivery tracked separately$/, () => '담당자 승인 접수 · 전달은 별도로 추적'],
    [/^approval accepted by (.+?); delivery pending$/, (m, U) => `${U.who(m[1])} 승인 접수 · 전달 대기`],
    [/^submitted by (.+)$/, (m, U) => `${U.who(m[1])} 제출`],
    [/^waiting for the incident re-observation verdict$/, () => '효과 확인 결과 대기'],
    [/^cancelled: incident (\w+) before any action \(cleared=(True|False)\)$/, (m, U) => `조치 전 사건 종료(${U.status(m[1])})로 취소`],
    [/^reached by abort: incident (\w+) before any action \(cleared=(True|False)\)$/, (m, U) => `조치 전 사건 종료(${U.status(m[1])})로 도달`],
    [/^rework superseded: (.+)$/, () => '다시 수행으로 대체됨'],
    [/^\[Lease expired: reclaimed by (.+?) \(claim (\d+)\)\]$/, m => `실행 임대 만료 · 다른 작업자가 이어받음 (${m[2]}번째)`],
    [/^action\.cmd (CMD-[\w-]+) issued; waiting ACK$/, m => `설비 명령 ${m[1]} 전송 · 응답 대기`],
    [/^\[Cancel requested by (.+?)\] ?(.*)$/, (m, U) => `[${U.who(m[1])} 실행 취소 요청] ${m[2]}`.trim()],
    [/^\[Closed by (.+?)\] ?(.*)$/, (m, U) => `[${U.who(m[1])} 단계 닫음] ${m[2]}`.trim()],
    [/^\[DEFERRED\] ?(.*)$/, m => `[보류] ${m[1]}`.trim()],
    [/^(\d+(?:\.\d+)?) sim-s = (\d+(?:\.\d+)?) s$/, m => `시뮬레이션 ${m[1]}초 = 실제 ${m[2]}초`],
    [/^cleared before any action$/, () => '조치 전에 경보 해제'],
    [/^cleared=(True|False) (\w+)=([\d.]+) \(criterion (.+)\)$/, m => `경보 해제 ${m[1] === 'True' ? '예' : '아니요'} · ${m[2]} ${m[3]} (기준 ${m[4]})`],
    [/^alert (ALT-[\w-]+)$/, m => `경보 ${m[1]}`],
    [/^source handler lease expired$/, () => '원천 처리기 임대 만료'],
    [/^[A-Z_]{4,}$/, (m, U) => U.status(m[0])],
  ],
  logText(raw) {
    const text = String(raw ?? '').trim(); if (!text) return '';
    return text.split(/;\s+/).map(s => s.trim()).filter(Boolean).map(seg => {
      for (const [re, fn] of this.logPatterns) { const m = seg.match(re); if (m) return fn(m, this); }
      return this.idText(seg);
    }).join(' · ');
  },
  // 번역된 문구 + 원문 접기(원문이 다를 때만)
  logHtml(raw, cls = 'kv-line') {
    const text = this.logText(raw); if (!text) return '';
    return `<p class="${cls}">${esc(text)}</p>` + (text !== String(raw).trim() ? this.fold(esc(this.t('log.raw')), `<pre>${esc(raw)}</pre>`, { cls: 'small' }) : '');
  },
  // 보조 메타(담당자 · 시각 · id)는 기본 접기: items = [[label, value]], 값이 비면 뺀다
  metaFold(items, label = 'fold.meta') {
    const rows = (items || []).filter(([, v]) => v != null && v !== '' && v !== '–');
    if (!rows.length) return '';
    return this.fold(esc(this.t(label)), `<dl class="meta-list">${rows.map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${v}</dd></div>`).join('')}</dl>`, { cls: 'small' });
  },

  /* ---------- 상태 이름 (UIUX_PLAN §5.2 D3 + 사건 상태) ---------- */
  states: {
    PENDING_APPROVAL: "승인 대기", AWAITING_APPROVAL: "조치 선택 대기", GUIDE_RECEIVED: "분석 완료", CMD_ISSUED: "명령 전송", AWAITING_ACK: "설비 응답 대기",
    ACKED: "설비 응답", RE_OBSERVING: "효과 확인 중", RESOLVED: "이상 완화", WORK_ORDER_CREATED: "정비 요청 완료", CLOSED: "종결",
    ESCALATED: "책임자 확인 중", REJECTED_BY_OPERATOR: "조치 거부", RESOLVED_WITHOUT_ACTION: "자연 회복", APPROVED: "승인됨", EXECUTED: "실행 완료",
    PARTIAL: "일부 실행", REJECTED: "반려", FAILED: "실패", SUBMITTED: "제출됨", DONE: "완료", RUNNING: "진행 중",
    RUN: "운전 중", TRIP: "보호 정지", STOP: "계획 정지", RAISED: "경보 발생", RAISE: "경보 발생", CLEAR: "경보 해제", CLEARING: "회복 확인 중",
    CANDIDATE: "이상 징후", IDLE: "감시 중", VIA_HITL: "사람 승인 필요", REMOTE_AUTO: "원격 자동", REMOTE_MANUAL: "원격 수동", LOCAL: "현장 제어",
    WITHHELD: "데이터 부족", REJECTED_BY_GUARDRAIL: "안전 규칙으로 중단", NO_FEASIBLE_OPTION: "가능한 조치 없음", NOT_APPLICABLE: "해당 없음", EVALUATED: "판단 완료",
    NEW: "생성", TODO: "예정", IN_PROGRESS: "진행 중", PENDING: "보류", HUMAN_ASKED: '답변 기다림', FB_REQUESTED: '반영 중', STARTED: '진행 중', CANCELLED: "취소",
    COMPLETED: "완료", SKIPPED: "건너뜀", DELIVERED: "전달 완료", DISCARDED: "폐기", OK: "완료",
    UNSUPPORTED_ALERT_PATTERN: "정의에 없는 경보 패턴", SELECT_TIMEOUT: "선택 시간 초과", NOT_RECOVERED: "미회복",
    PROCESS_RESTART_REVIEW: "서비스 재시작 후 재검토", MITIGATION_FAILED: "완화 실패", ACK_TIMEOUT: "설비 응답 시간 초과", PASS: "통과", INTERLOCK: "인터록",
  },
  tones: {
    neutral: ['TODO', 'NEW', 'SKIPPED', 'IDLE', 'STOP', 'NOT_APPLICABLE', 'GUIDE_RECEIVED', 'LOCAL', 'DISCARDED'],
    accent: ['IN_PROGRESS', 'SUBMITTED', 'RUNNING', 'STARTED', 'FB_REQUESTED', 'APPROVED', 'CMD_ISSUED', 'AWAITING_ACK', 'REMOTE_AUTO', 'RE_OBSERVING', 'DELIVERED'],
    success: ['DONE', 'COMPLETED', 'CLOSED', 'EXECUTED', 'RESOLVED', 'RESOLVED_WITHOUT_ACTION', 'RUN', 'ACKED', 'WORK_ORDER_CREATED', 'EVALUATED', 'CLEAR', 'OK'],
    warning: ['PENDING', 'HUMAN_ASKED', 'PENDING_APPROVAL', 'AWAITING_APPROVAL', 'PARTIAL', 'VIA_HITL', 'WITHHELD', 'ESCALATED', 'REMOTE_MANUAL', 'CLEARING', 'CANDIDATE'],
    danger: ['CANCELLED', 'FAILED', 'REJECTED', 'REJECTED_BY_OPERATOR', 'REJECTED_BY_GUARDRAIL', 'NO_FEASIBLE_OPTION', 'TRIP', 'RAISED', 'RAISE'],
  },
  status(value) { return this.states[value] || value || "–"; },
  toneOf(value) { for (const [tone, list] of Object.entries(this.tones)) if (list.includes(value)) return tone; return 'neutral'; },
  chip(value, label, tone) {
    const t = tone || this.toneOf(value);
    return `<span class="chip tone-${t}" data-status="${esc(value || '')}">${esc(label != null ? label : this.status(value))}</span>`;
  },
  chipText(label, tone = 'neutral') { return `<span class="chip tone-${tone}">${esc(label)}</span>`; },

  /* ---------- 수행 주체 (명칭표 "행위자") ---------- */
  performers: { 'sys:agent': 'AI 에이전트', agent: 'AI 에이전트', 'role:operator': '운전원', operator: '운전원', 'role:prod-mgr': '생산관리자', 'role:maint-mgr': '설비보전팀장',
    'role:plant-mgr': '공장장', 'role:quality-mgr': '품질팀장', 'role:purchasing-mgr': '구매팀장', 'sys:scada': '설비', plc: '설비', 'sys:process': '시스템', process: '시스템',
    'sys:cmms': '정비 시스템', detector: '탐지기', legacy: 'AI 에이전트', cliagents: 'AI 에이전트', human: '담당자', result: '시스템' },
  who(id) { return this.performers[id] || id || '–'; },

  dateTime(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value || '–' : date.toLocaleString('ko-KR', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false });
  },
  time(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value || '–' : date.toLocaleTimeString('ko-KR', { hour12: false });
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
  },
  eventName(name) { return this.eventNames[name] || this.states[name] || name || '–'; },
  // chips: optional pre-rendered small chips after the actor (A132: `결과 파일로 제출` on a task_completed whose result_source is file)
  // extra: optional pre-rendered fold before the raw fold (A147: 기업 거래의 `변경 전·후`)
  eventRecord({ time, name, actor = '', detail = '', raw, chips = '', extra = '' }) {
    return `<article class="event-record"><header><time title="${esc(this.dateTime(time))}">${esc(this.time(time))}</time><strong>${esc(this.eventName(name))}</strong><span>${esc(this.who(actor))}</span>${chips}</header>${detail ? `<p>${esc(detail)}</p>` : ''}${extra}${raw ? `<details class="fold small"><summary>${esc(this.t('raw'))}</summary><pre>${esc(JSON.stringify(raw, null, 2))}</pre></details>` : ''}</article>`;
  },
  condition(value) {
    return { 'cmms_cleans_60d >= 3': '최근 60일 동안 쿨러 세척 3회 이상', 'qms_hot_min > 0': '과열 구간에 생산된 로트가 있음' }[value] || value;
  },

  /* ---------- 공통 컴포넌트 (UIUX_PLAN §3, uiux-refs R3·R5·R6·R10·R12) ---------- */
  // card: 제목 · 칩 · 핵심 값 · 보조 1줄 · 본문 (R3 순서)
  card({ title, chips = '', value = '', sub = '', body = '', cls = '', actions = '', attrs = '' }) {
    return `<section class="card ${cls}" ${attrs}>` +
      (title || chips || actions ? `<header class="card-head"><div class="card-title">${title ? `<h3>${title}</h3>` : ''}${chips ? `<span class="card-chips">${chips}</span>` : ''}</div>${actions ? `<div class="card-actions">${actions}</div>` : ''}</header>` : '') +
      (value ? `<div class="card-value">${value}</div>` : '') + (sub ? `<p class="card-sub">${sub}</p>` : '') + (body ? `<div class="card-body">${body}</div>` : '') + '</section>';
  },
  // field: 라벨 위 · 입력 아래 · 필수 * · 도움말 1줄 (R5)
  field({ label, input, hint = '', required = false, cls = '', error = '' }) {
    return `<div class="field ${cls}"><label>${esc(label)}${required ? ' <i class="req" aria-hidden="true">*</i>' : ''}</label>${input}${error ? `<p class="field-error" role="alert">${esc(error)}</p>` : hint ? `<p class="field-hint">${esc(hint)}</p>` : ''}</div>`;
  },
  // form section: 제목 + 필드 격자 (R6)
  section(title, body, cls = '') { return `<section class="form-section ${cls}">${title ? `<h4>${esc(title)}</h4>` : ''}<div class="form-grid">${body}</div></section>`; },
  actions(body, msg = '') { return `<div class="form-actions">${msg ? `<span class="form-msg neg" role="status">${esc(msg)}</span>` : ''}${body}</div>`; },
  // fold: 요약 한 줄 + 꺾쇠 (R12)
  fold(summary, body, { open = false, cls = '' } = {}) { return `<details class="fold ${cls}" ${open ? 'open' : ''}><summary>${summary}</summary><div class="fold-body">${body}</div></details>`; },
  // empty: 굵은 한 줄 + 보조 한 줄 (R10)
  empty(title, sub = '', cls = '') { return `<div class="empty ${cls}"><b>${esc(title)}</b>${sub ? `<span>${esc(sub)}</span>` : ''}</div>`; },
  // tabs: 밑줄형 (R12). items = [[key, label, count?]]
  tabs(items, active, attr = 'data-tab-key') {
    return `<div class="tabs" role="tablist">${items.map(([k, l, n]) => `<button type="button" role="tab" class="tab${k === active ? ' on' : ''}" ${attr}="${esc(k)}" aria-selected="${k === active}">${esc(l)}${n != null ? ` <span class="chip tone-neutral sm">${esc(n)}</span>` : ''}</button>`).join('')}</div>`;
  },
  // paged list (A122 coordinator request): first `shown` rows, the selected row pinned on top when it is beyond them, one 더 보기 button
  PAGE: 20,
  page(items, shown, isSelected) {
    const head = items.slice(0, shown);
    const pinned = items.slice(shown).find(isSelected);
    return { rows: pinned ? [pinned, ...head] : head, rest: Math.max(0, items.length - shown), pinned: !!pinned };
  },
  moreButton(rest, attr = 'data-more') { return rest > 0 ? `<button type="button" class="btn small" ${attr} style="width:100%;margin-top:var(--s2)">${esc(this.t('btn.more'))} (남은 ${rest}건)</button>` : ''; },
  // read-only labelled value (이전 단계 입력 · 변수)
  readonly(label, value, sub = '') { return `<div class="field ro"><label>${esc(label)}</label><div class="ro-value">${value}</div>${sub ? `<p class="field-hint">${esc(sub)}</p>` : ''}</div>`; },

  // Labels and units follow enterprise-sim/entsim/data.py. Unknown fields retain their exact key/value.
  facts: {
    due_in_h: ['납기까지', '시간'], remaining_qty: ['생산 잔량', '개'], rate_per_h: ['생산 속도', '개/시간'],
    hour_value: ['생산 시간당 가치', '만원/시간'], alt_asset: ['대체 설비', ''], alt_free_h: ['대체 설비 가용 시간', '시간'],
    alt_rate_per_h: ['대체 설비 생산 속도', '개/시간'], changeover_h: ['설비 전환 시간', '시간'], order_id: ['생산오더', ''],
    sales_order: ['판매 주문', ''], customer_tier: ['고객 구분', ''], penalty_per_h: ['시간당 지체상금', '만원/시간'],
    failure_cost: ['돌발 고장 비용', '만원'], claim_cost: ['품질 클레임 비용', '만원'],
    fg_item: ['완제품 품목', ''], fg_stock: ['완제품 재고', '개'], ship_in_h: ['출하까지', '시간'],
    cleans_60d: ['최근 60일 세척 횟수', '회'], last_clean_days: ['마지막 세척 후', '일'], clean_h: ['세척 소요', '시간'],
    clean_cost: ['세척 비용', '만원'], night_in_h: ['야간 정비창까지', '시간'], oil_risk_per_h: ['시간당 작동유 위험 비용', '만원/시간'], mtbf_h: ['평균 고장 간격', '시간'],
    hot_min: ['과열 지속 시간', '분'], auto_lot: ['자동차 고객 로트', ''], auto_qty: ['자동차 고객 수량', '개'],
    gen_lot: ['일반 고객 로트', ''], gen_qty: ['일반 고객 수량', '개'], inspect_h: ['검사 소요', '시간'],
    inspect_cost: ['전수검사 비용', '만원'], sample_cost: ['표본검사 비용', '만원'],
    gen_defect_p: ['일반 고객 불량 확률', '확률'], auto_defect_p: ['자동차 고객 불량 확률', '확률'],
    gen_claim: ['일반 고객 클레임 손실', '만원'], auto_claim: ['자동차 고객 클레임 손실', '만원'],
    std_price: ['기준 구매 단가', '만원'], contract_kw: ['계약 전력', 'kW'], demand_kw: ['현재 전력 수요', 'kW'],
    fan_boost_kw: ['팬 증속 추가 전력', 'kW'], basic_rate: ['기본 요금 단가', '만원/kW'], peak_h: ['피크 시간', '시간'],
    peak_window: ['피크 시간대', ''], outdoor_c: ['외기 온도', '°C'], energy_rate: ['전력량 요금 단가', '만원/kWh'],
  },
  factList(facts) {
    return '<dl class="fact-list">' + Object.entries(facts || {}).map(([key, value]) => {
      const short = key.replace(/^(mes|erp|cmms|qms|scm|ems)_/, '');
      let spec = this.facts[short];
      const supplier = short.match(/^([abc])_(price|fail|lead_d|avl)$/);
      if (supplier) { const field = { price: ['구매 단가', '만원'], fail: ['고장 확률', '확률'], lead_d: ['납기', '일'], avl: ['승인 공급사', '여부'] }[supplier[2]]; spec = [supplier[1].toUpperCase() + ' 공급사 ' + field[0], field[1]]; }
      const [label, unit] = spec || [key, ''];
      const shown = unit === '확률' ? Number(value) * 100 + ' %' : unit === '여부' ? (value ? '예' : '아니요') : `${typeof value === 'number' ? value.toLocaleString('ko-KR') : value}${unit ? ' ' + unit : ''}`;
      return `<div title="${esc(key)}"><dt>${esc(label)}</dt><dd>${esc(shown)}</dd></div>`;
    }).join('') + '</dl>';
  },
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
  icon(name) {
    const paths = {
      home: "M3 10 12 3l9 7v11h-6v-7H9v7H3Z",
      map: "M4 4h6v6H4Zm10 10h6v6h-6ZM7 10v7h7M10 7h7v7",
      play: "m8 5 11 7-11 7Z",
      alert: "m12 3 10 18H2Zm0 6v5m0 3v1",
      chart: "M4 3v17h17M7 15l4-5 4 2 5-7",
      nodes: "M9 6h6M7 8v8m10-8v8M9 18h6M4 3h5v5H4Zm11 0h5v5h-5ZM4 16h5v5H4Zm11 0h5v5h-5Z",
      skills: "M5 3h14v18H5Zm4 5h6m-6 4h6m-6 4h4",
      decision: "M5 4h14v16H5Zm3 4 1 1 2-2m2 1h3M8 13l1 1 2-2m2 1h3",
      process: "M3 4h6v6H3Zm12 10h6v6h-6ZM9 7h9v7M6 10v7h9",
      gear: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Zm8 4-2-1 1-2-2-2-2 1-1-2h-4l-1 2-2-1-2 2 1 2-2 1v4l2 1-1 2 2 2 2-1 1 2h4l1-2 2 1 2-2-1-2 2-1Z",
      book: "M4 4h7a3 3 0 0 1 3 3v13a2 2 0 0 0-2-2H4Zm16 0h-7a3 3 0 0 0-3 3v13a2 2 0 0 1 2-2h8Z",
    };
    return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${paths[name] || paths.home}"/></svg>`;
  },
};

/* A115 (r14 A12, process-gpt-vue3 shared/hitlFeedback humanQuestionText): a person's question card reads `text`, and an
   SDK agent's `question` when there is no text — before, an SDK question showed an empty card. */
function humanQuestionText(data) {
  return String((data && (data.text || data.question)) || "");
}
UI.loadNames();   // A141: 원문 id → 이름 사전(정적 names.json). 읽기 전에는 id 가 그대로 보이고, 화면은 주기 갱신 때 따라온다.
