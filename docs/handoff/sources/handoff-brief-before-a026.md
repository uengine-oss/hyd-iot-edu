## 0. 30초 브리핑

**최신 상태:** A028 실제 CMMS 참조/종결순서 결함을 수정했다. 전체382검사, 실제Pg/SQLite/HTTP6/6, legacy bridge 인스턴스40/40, 직접legacy48/48을 확인했다. 새 Codex 워커 시작은 자동 승인 심사에서 `blocked by policy`로 거절되어 미실행이다. 기본 instance/20×/legacy·설비3기RUN·PowerShell worker0·개인config불변을 확인했다(`a028-restored.json`). [WORK_ORDER_RECOVERY.md](WORK_ORDER_RECOVERY.md)에 실패→수정→실측과 남은 경계를 기록했다. A026 원문19검사 모듈의 API/검토/원자적그래프 연결로 진행한다. 아래 A028 미수정 문단은 발견 당시의 기록이다.

현재 목표는 회의 원문·HYD 구현·uengine-oss 저장소 지도를 대조하고, 잘못된 구조를 필요한 만큼 교체해 정의·온톨로지·규칙·현재 데이터에 따라 실행되는 강의용 시스템을 만드는 것이다. 회의1·2 전문과 47개 저장소 지도는 확인했다. 코드 열람 범위는 REPOSITORY_REVIEW에 따로 적었으며 47개 전체 코드를 통독했다는 뜻은 아니다.

A022에서 업무 MCP의 postgres/ent 밖 조회 결함을 고쳤다. 전용 읽기 역할과 AST 검사, 실제 DB+HTTP 49/49, 전체 단위319 passed, 실제 Codex의 두 정의·컬럼 오류수정·0행과거절 구별까지 검증했다. 기본 설비 정의2.0은 실제 Codex 네 작업→사람 승인→PLC→재관측→CMMS→종결 **36/36**을 통과했다. A023의 호출별 앱 도구 제외도 적용하고 새 워커의 두 정의로 재검증했다.

A021 타이머/콜백복구는 실제Pg11/11·PLC ACK 뒤 강제종료38/38을 확인했으나, 이어진 실제Codex 실행에서 DB 부모/자식잠금 교착이 드러났다. 실패상태를 보존하고 저장/RPC 잠금순서를 수정했다. 교착반례7/7→수정후7/7, 전체334검사. A024 실제Codex 두건은 업무질문→worker재시작/cache부재→같은세션으로답변반영→서로다른DB조회/분기에성공했다. 포털 직접클릭은 도구제약으로 미검수다.

교착 수정 후 A021 실제Codex36/36에 이어, A025 승인복구의 새 실제Codex도 **38/38, exit0**을 통과했다(`a025-codex-scenario.log`, 인스턴스666d3935-cd1b-4b15-bf3b-e82b2d4dfcd1). 네 작업269초/MCP20건, 승인DELIVERED1회, 재관측601초/TS1=51.49/CLEAR, CMMS WO-1003-4CBB/ev:closed를 확인했다. PowerShell worker/자식0·20×/legacy·3설비RUN 복구 완료(`a025-worker-stop.json`, `a025-restored.json`). **추가 실제 결함 A028:** Incident는 CMMS 응답 전에 임시 WO-INC 번호/SOP-COOL-03으로 생성·종결을 기록했고, 실제 CMMS는 WO-1003-4CBB/SOP-COOL-02다. 이 불일치는38검사의 범위 밖이며 미수정이다. A026 독립 원문 모듈19/전체367검사 통과, API/그래프/에이전트 추출 연결 전이다. 일반claim지연·외부상태/outbox·stale승인/미지원경보·SOP·전체강의검수는 미완료이며 Goal은 active다.

이전 브리핑은 [보존본](sources/handoff-brief-before-a022.md)에 있다. §2~8 및 §9의 과거 수치는 당시 기록이며 최신 재개점은 §9 G다.

