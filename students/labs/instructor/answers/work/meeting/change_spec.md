# 변경 명세 — 담당자 없는 할 일 표시

## 바꿀 것
- 담당자가 없는 할 일은 `owner` 를 `null`, `unassigned` 를 `true` 로 적는다.
- 결과에 `unassigned_todos` 목록을 더하고 담당자 없는 할 일의 이름을 넣는다.
- 모든 할 일에 `unassigned` 칸을 둔다(담당자가 있으면 `false`).

## 지킬 것 (기존 동작 유지)
- 제목 · 날짜 · 결정사항을 고르는 기준은 그대로다.
- 담당자가 있는 할 일의 `task` · `owner` · `due` 는 예전 결과와 같아야 한다.
- memo1 · memo2 의 결정사항과 할 일은 바꾸기 전 결과(`work/meeting/before/`)와 같아야 한다.
- 메모에 없는 담당자를 짐작해서 채우지 않는다.

## 확인할 경우

### 경우 1 — 담당자가 모두 있는 메모
- 상황: memo3 에는 할 일 두 개가 있고 둘 다 담당자가 있다.
- 행동: Skill 로 memo3 을 정리한다.
- 기대 결과: 두 할 일 모두 `unassigned` 가 `false` 이고 `unassigned_todos` 는 비어 있다.

### 경우 2 — 담당자가 없는 할 일이 섞인 메모
- 상황: memo4 에는 할 일 세 개가 있고 그 가운데 두 개는 맡을 사람이 정해지지 않았다.
- 행동: Skill 로 memo4 를 정리한다.
- 기대 결과: 담당자 있는 한 개는 `unassigned` 가 `false`, 나머지 두 개는 `owner` 가 `null` 이고 `unassigned` 가 `true` 이며 `unassigned_todos` 에 두 개가 들어 있다.

### 경우 3 — 예전 메모
- 상황: memo1 · memo2 는 바꾸기 전에 이미 정리한 결과가 있다.
- 행동: 고친 Skill 로 다시 정리한다.
- 기대 결과: 결정사항과 할 일(task · owner · due)이 바꾸기 전과 같다.
