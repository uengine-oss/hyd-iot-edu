# 수업 한 바퀴 결과

판정 5개 · 실패 1개 · 별도 콘솔/통신 오류 실습 0개 · 측정 안 함 0개(통과 아님)

## 13 — 통과 4/5
- 통과 [quality] 보충 자료 추가가 기존 제조 지식을 초기화하지 않음
- 통과 [normal] 학생 교대 스킬 저장
- 통과 [normal] 학생 교대 에이전트 저장
- 통과 [normal] 교대 BPMN 가져오기 — 가져옴 — 단계 9개
- **실패** [normal] 실습이 끝까지 돌았다 — TimeoutError: Locator.select_option: Timeout 20000ms exceeded.
Call log:
  - waiting for locator("#flowEditor select[data-var='seq_3']")
    - locator resolved to <select data-var="seq_3" aria-label="분기할 값">…</select>
  - attempting select option action
    2 × waiting for element to be visible and 
