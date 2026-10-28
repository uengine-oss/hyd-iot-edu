# 수업 한 바퀴 결과

판정 5개 · 실패 1개 · 별도 콘솔/통신 오류 실습 0개 · 측정 안 함 0개(통과 아님)

## 13 — 통과 4/5
- 통과 [quality] 보충 자료 추가가 기존 제조 지식을 초기화하지 않음
- 통과 [normal] 학생 교대 스킬 저장
- 통과 [normal] 학생 교대 에이전트 저장
- 통과 [normal] 교대 BPMN 가져오기 — 다시 가져옴 — 매핑 유지 0 · 새 단계 9 · 사라진 단계 0
- **실패** [normal] 실습이 끝까지 돌았다 — TimeoutError: Locator.get_attribute: Timeout 20000ms exceeded.
Call log:
  - waiting for locator("#flowEditor div.field[data-row]").filter(has_text="분기 '검토 결정'").first.locator("tr[data-row]").filter(has_text="→ 인수 확인 기록 완료").first

py", line 481, in get_attribute
    return await self._frame.get_att
