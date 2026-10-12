# PM Action 실행 계약 감사 — 2026-10-12

원문 `docs/samples/PM-02_powerpack-pm-checklist.md`, 실제 제안 `.evidence/a161-c3/proposal-PM-02.json`, 생산 코드 callchain을 대조했다. 증거 정본은 `D:/work/study/hyd-iot-edu/.evidence/final-completion-20261012/PM-action-contract-audit.json`이다. 최초 보고서의 한글은 Windows 파이프 인코딩 오류로 물음표가 되었으며 원래 판단을 UTF-8로 다시 작성했다.

PM13의 원문 3단계는 기존 정비 오더 시행 시간을 그다음 창으로 옮기는 것이다. 제안 actions=[]지만 후보 출력에 포함된다. cards/guardrail은 빈 Action을 거부하지 않는다. instances._run_work_order→work_orders.request_for_option는 process-definition-followup WO_CREATE를 생성하므로 원문 일정 변경을 새 오더 생성으로 바꿀 위험이 있다.

cards.option_window는 PM13에 적용되는 기한 규칙과 실제 following 창 ID가 함께 있으면 그다음 창을 보존한다. ID 없이 운전시간만 있으면 None이며 기본 maintenance_window를 사용할 위험이 있다. 기존 오더나 목표 창이 미상이면 해당 대안은 실행 불가여야 한다.

PM21~23은 현장 LOTO·잔압 해제·교체·시운전 패키지이며 현재 후보 출력에는 없다. 참고 원문으로 보관하고 자동 시스템 효과나 정비 완료를 추정하지 않는다.

후보 hours_since_pm이 미확인이면 unknown trace를 남기지만 PM은 options=[]/EVALUATED로 끝날 수 있다. EXCLUDE/PENALTY의 필수 unknown은 후보를 차단하고 WARN은 경고이며 승인 재검사는 필수 unknown을 거부한다. 알려진 거짓 AND 항목이면 나머지 unknown은 무관하다는 기존 계약을 유지한다.

원문 납기24시간·생산 오더 존재·즉시 정지 감점80만 원은 제안 규칙에서 빠지고 warning에 입력·감점지표 부족이 명시됐다. 존재하지 않는 규칙 누락을 엔진이 자동 차단하지 않으므로 원문 완전 지원이라고 할 수 없다.

근본 수정 범위는 명시 WO_RESCHEDULE, 기존 오더 ID/상태, 목표 창/기한, 실제 CMMS 원천, 승인 스냅샷, 멱등·재검증·롤백이다. A의 일반 후속 정비는 보존한다. 구현 후 시험·배포 근거를 별도로 기록한다.

ProcessGPT/ontology-studio 대조는 기존 manual-reference-model-audit.md의 실제 실행 결과/실패 기록 및 source node/좌표 경계를 참고했다. 이번 로컬 refs 경로가 없어 upstream 소스를 새로 읽었다고 주장하지 않는다. 기존 검사기·golden·원문 제안은 불변이다.
