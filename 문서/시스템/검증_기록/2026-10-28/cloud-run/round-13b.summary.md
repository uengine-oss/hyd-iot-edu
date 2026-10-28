# 수업 한 바퀴 결과

판정 3개 · 실패 1개 · 별도 콘솔/통신 오류 실습 0개 · 측정 안 함 0개(통과 아님)

## 13 — 통과 2/3
- 통과 [quality] 보충 자료 추가가 기존 제조 지식을 초기화하지 않음
- 통과 [normal] 학생 교대 스킬 저장
- **실패** [normal] 실습이 끝까지 돌았다 — TimeoutError: Locator.click: Timeout 20000ms exceeded.
Call log:
  - waiting for locator("[data-ag-form]").locator("button[type=submit]")
    - locator resolved to <button disabled type="submit" class="btn primary">저장</button>
  - attempting click action
    2 × waiting for element to be visible, en
