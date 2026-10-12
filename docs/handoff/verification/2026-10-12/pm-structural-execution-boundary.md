# PM 선언 지식과 실제 실행 검사 경계

첫 전체 회귀는 10개 실패/2,624개 통과/16개 건너뜀으로 끝났다. 실패는 과거 C1-B 구조·규칙 비교 9개와 기존 보상 목록 계약 1개였다. 원래 시험 기대값·골든·검사기를 완화하지 않았다.

`maintenance_policy`는 기존 스키마의 가산 선택 속성이다. 따라서 과거 PM 선언그래프는 기존 관계·Action·Rule 구조가 맞으면 보관하고 순수 규칙 비교에 사용할 수 있다. 명시된 정책의 타입·원문 근거·품목 범위 검증은 유지한다. 적재 전 `technical_ready`는 이 구조 검사 결과이며 실제 정비 실행 가능을 뜻하지 않는다. PM preflight의 별도 `execution[]`는 실제 context 검사를 수행하지 않았다고 명시하고, 정책이 없으면 그 이유도 표시한다. 원안과 사람 검토·소유권·판본 보호는 유지한다.

순수 카드 엔진의 기본 모드는 `rule_analysis`이다. 실제 decide와 현재 승인 재검사만 `execution`을 명시한다. trial/whatif는 가상 입력의 규칙 비교·모의 순위로 남는다. 결과·카드에 `evaluation_mode`와 정확한 boolean `execution_checked`, 한국어 안내를 제공한다. 규칙상 `feasible`은 이 모드에서 규칙 비교값이며 실제 실행 허가가 아니다.

실제 PM 실행 모드는 `source_id` 유무와 관계없이 typed 정책·전체 실제 context·정비 범위 계획을 요구한다. 저장된 규칙 비교 DEC는 승인하거나 CMMS로 실행할 수 없다. 잘못된 명시 모드, 구조 검사 모드, 문자열/숫자 확인 flag도 거부한다. 과거 A의 모드 필드 없는 계약은 유지하되, PM는 origin/scenario/facts의 pattern을 재확인하므로 옵션에서 metadata를 지워도 실행 검사를 우회하지 못한다. 기존 A 후속 작업지시와 구매·reference 경계는 유지한다.

보상 목록은 기존 4개 원형과 신규 C2 묶음 보상을 별도 registry로 구분한다. 실제 실행·멱등 영수증·보상 조회는 통합 registry를 소비한다. 신규 전체 묶음 보상을 없애거나 출고 반품 미확인 차단을 해제하지 않았다.

초기 국소 실행은 75개 통과/21개 실패였다. 실제 승인용 기존 fixture가 기본 순수 엔진 결과를 DEC로 사용하는 것이 원인이어서 producer 호출에 실제 실행 모드를 명시했다. 기존 21개 assertion은 그대로 유지하며 분석 결과의 승인 차단은 별도 부정 시험으로 확인한다. 이후 넓은 회귀는 284개 통과/1개 건너뜀이다(`F/pytest-pm-mode-wide.log`). 추가 부정·preflight 검사 44개 통과(`F/pytest-pm-mode-negative-final2.log`). 추가 시험의 최초 SOP값 입력 오류와 resolved plan 소비 누락 실패도 앞선 negative 로그에 보존했다. 최종 소스에 대한 확정 넓은 회귀는 `F/pytest-pm-mode-wide-final.log`를 참조한다.

F 경로는 `D:/work/study/hyd-iot-edu/.evidence/delegated-review-20261012`이다. 이 검사 결과는 메인 지식 적재·현장 정비 완료·실제 B 실행 성공 증거가 아니다.

최종 넓은 회귀 `F/pytest-pm-mode-wide-final.log`은 **357개 통과/1개 건너뜀, 125.52초**다. C1-B·entsim·현재 승인·PM·보상·reference·MCP 입력·trial/whatif·적재 전 검사·승인 전달/거절을 포함한다. 마지막 원문 판본 필수 경계를 포함한 `F/pytest-pm-mode-final-boundary.log`도 **87개 통과, 2.34초**다. 제품·시험·문서 쓰기를 종료하고 루트의 최종 전역 검사와 실제 배포 검증에 인계한다.
