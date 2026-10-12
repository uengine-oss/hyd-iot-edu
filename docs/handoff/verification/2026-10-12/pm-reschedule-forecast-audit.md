# WO_RESCHEDULE 예측 효과 등록

최초 실제 B 결과는 F/watch-B-final-live/result.json의 agent_boundaries[0].data.receipt.assessment.evidence.evaluate_cards.document.options[1]에 보존되어 있다. 정식 등록된 WO_RESCHEDULE Action이 물리 예측에서 `unsupported non-command effect: WO_RESCHEDULE`로 거부되었다. 정본 schema와 pm_capabilities.cypher는 transaction 능력을 등록했지만 common/hydcommon/forecast.py의 명시 효과 목록에 없었다.

기존 PM 오더 일정 변경은 현재 설비를 수리하거나 제어값을 바꾸지 않는다. 예측 모델은 WO_RESCHEDULE을 이 물리 효과 계약으로 명시 지원한다. transaction 종류를 요구하며, 알 수 없는 코드·코드 누락·잘못된 종류·command 위장은 거부한다. 모든 비명령 효과를 일반적으로 무시하는 대체 경로는 추가하지 않았다.

실제 forecast adapter→카드 소비 회귀는 모델 오류가 제거되고 원래 Action이 보존되는 것을 확인한다. 별도의 source policy·기존 PM 오더·예약 배분·허용 창이 없는 카드는 execution:pm-plan으로 계속 제외된다. 실제 B의 필터/작동유 재고 미확인 및 연기 창 상한은 변경하지 않는다. 예측 지원은 정비 실행 완료 또는 기존 B 처리 완주를 뜻하지 않는다.

집중 검사 F/pytest-pm-reschedule-forecast.log: 신규 능력/누락/미상/타입/실행 경계 및 기존 A 물리 예측 모델·원천·가드 73 passed, 2.01초. 기존 기대값·골든·검사기는 변경하지 않았고 전체 시험은 재실행하지 않았다. 제품 변경은 common/hydcommon/forecast.py 한 파일이며 새 시험은 tests/test_pm_reschedule_forecast.py이다.

이전 17파일 구매 정책 SHA와 전체 원본/운영 manifest는 덮지 않는다. 추가 F/pm-reschedule-forecast-source-sha.json에 변경 모델과 실제 adapter/cards 소비자 및 신규 시험의 SHA를 기록한다. agent/dmn-mcp/process는 Dockerfile에서 공용 라이브러리를 복사하므로 root가 새 판본을 배포한다. 기존 B 결정과 자율 보류는 보존하고, 배포 후 공식 MCP 현재 평가 조회 한 번으로 모델 오류 제거와 남은 독립 제외 사유를 확인한다. 여기서는 라이브 요청·적재·효과·워커 실행을 수행하지 않았다.
