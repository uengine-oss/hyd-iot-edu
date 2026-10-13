Scenario: 정상 R05 - 답으로 사례 S07이 정해지고 결정이 없으면 승인 대기가 된다
Given 요청 R05에 적힌 것은 설비 HYD-01, 경보 패턴 COOLER_DEGRADATION, 사례 S02다
And 사람이 R05의 질문 1번에 S07이라고 답했다 (답한 사람 권도현)
And R05에 대한 사람의 결정은 없다
And 사례 S07의 경보 패턴은 COOLER_DEGRADATION이다
And 사례 S07의 TS1 avg 120초 값은 59.4다
And 사례 S07의 TS1 avg 120초 관측은 충분하다
And 사례 S07의 신선도는 한도 안이다
When 요청 R05를 처리한다
Then 상태는 승인_대기다
And 긴급은 false다
And 사례는 S07이다
And 근거 상태는 SUPPORTED다
And 상태는 확정이 아니다
And 승인 칸은 비어 있다
And 질문 1번의 선택지는 S02, S01, S07이다

Scenario: 긴급 R03 - 운전원이 SOP-COOL-11을 승인하면 확정이 된다
Given 요청 R03에 적힌 것은 설비 HYD-01, 경보 패턴 COOLER_DEGRADATION, 사례 S01이다
And R03의 질문에 대한 사람의 답은 없다
And 운전원 문태식이 R03의 조치 SOP-COOL-11을 승인했다 (사유 없음)
And 사례 S01의 경보 패턴은 COOLER_DEGRADATION이다
And 사례 S01의 TS1 avg 120초 값은 60.7이다
And 사례 S01의 TS1 avg 120초 관측은 충분하다
And 사례 S01의 신선도는 한도 안이다
When 요청 R03을 처리한다
Then 상태는 확정이다
And 긴급은 true다
And 사례는 S01이다
And 근거 상태는 SUPPORTED다

Scenario: 긴급 R04 - 답으로 사례 S01이 정해져도 결정이 없으면 승인 대기에 머문다
Given 요청 R04에 적힌 것은 설비 없음, 경보 패턴 없음, 사례 없음이다
And 사람이 R04의 질문 1번에 HYD-01이라고 답했다 (답한 사람 서유나)
And 사람이 R04의 질문 2번에 S01이라고 답했다 (답한 사람 서유나)
And R04에 대한 사람의 결정은 없다
And 사례 S01의 경보 패턴은 COOLER_DEGRADATION이다
And 사례 S01의 TS1 avg 120초 값은 60.7이다
And 사례 S01의 TS1 avg 120초 관측은 충분하다
And 사례 S01의 신선도는 한도 안이다
When 요청 R04를 처리한다
Then 상태는 승인_대기다
And 긴급은 true다
And 사례는 S01이다
And 근거 상태는 SUPPORTED다
And 상태는 확정이 아니다
And 승인 칸은 비어 있다
And 질문 1번의 선택지는 HYD-01, HYD-02, HYD-03이다
And 질문 2번의 선택지는 S01, S04, S07, S10이다

Scenario: 미입력 R01 - 질문 1번에 답이 없으면 질문 대기로 멈춘다
Given 요청 R01에 적힌 것은 설비 없음, 경보 패턴 PUMP_LEAKAGE, 사례 없음이다
And R01의 질문에 대한 사람의 답은 없다
And R01에 대한 사람의 결정은 없다
When 요청 R01을 처리한다
Then 상태는 질문_대기다
And 긴급은 null이다
And 사례는 null이다
And 근거 상태는 null이다
And 상태는 확정이 아니다
And 승인 칸은 비어 있다
And 질문은 한 건이다
And 질문 1번의 선택지는 S04, S05다

Scenario: 미입력 R08 - 맞는 사례가 0건이고 답이 없으면 질문 대기로 멈춘다
Given 요청 R08에 적힌 것은 설비 HYD-03, 경보 패턴 PUMP_LEAKAGE, 사례 없음이다
And R08의 질문에 대한 사람의 답은 없다
And R08에 대한 사람의 결정은 없다
When 요청 R08을 처리한다
Then 상태는 질문_대기다
And 긴급은 null이다
And 사례는 null이다
And 근거 상태는 null이다
And 상태는 확정이 아니다
And 승인 칸은 비어 있다
And 질문 1번의 선택지는 없다

Scenario: 거절 R07 - 사유를 적어 거절하면 반려가 된다
Given 요청 R07에 적힌 것은 설비 HYD-03, 경보 패턴 없음, 사례 없음이다
And 사람이 R07의 질문 1번에 S03이라고 답했다 (답한 사람 임채원)
And 생산관리자 남기훈이 R07을 거절했다 (절차 번호 없음, 사유 「현장에서 팬 쪽을 먼저 살펴본 뒤에 다시 요청한다」)
And 사례 S03의 경보 패턴은 COOLER_DEGRADATION이다
And 사례 S03의 TS1 avg 120초 값은 58.6이다
And 사례 S03의 TS1 avg 120초 관측은 충분하다
And 사례 S03의 신선도는 한도 안이다
When 요청 R07을 처리한다
Then 상태는 반려다
And 긴급은 false다
And 사례는 S03이다
And 근거 상태는 SUPPORTED다
And 상태는 확정이 아니다
