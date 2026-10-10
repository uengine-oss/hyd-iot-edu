# 6-4 · Skill에 새 요구를 넣고 예전 결과도 유지하기

## 만들 것

변경 명세 `work/meeting/change_spec.md`, 새 요구를 반영한 Skill(`.claude/skills/meeting-notes/SKILL.md`), 새 메모 두 개의 결과 `work/meeting/memo3.result.json` · `memo4.result.json`, 그리고 다시 정리한 memo1 · memo2 결과.

## 왜 만드나

새 요구가 생겼을 때 "고쳐 줘"라고만 하면, 새 기능은 생기지만 원래 되던 것이 조용히 바뀌는 일이 생깁니다. 그래서 고치기 전에 두 가지를 먼저 글로 정합니다. 무엇을 바꾸는가, 무엇은 그대로여야 하는가. 그리고 "이런 상황에서 이렇게 하면 이런 결과가 나와야 한다"를 예로 적어 둡니다. 명세를 먼저 쓰고(SDD), 상황 · 행동 · 기대 결과로 확인하는(BDD) 방식입니다.

## 주어지는 자료

- 새 요구: **담당자가 없는 할 일은 따로 표시한다**
- `day6/memos/memo3.md` — 할 일마다 담당자가 있는 메모
- `day6/memos/memo4.md` — 담당자가 없는 할 일이 섞인 메모
- `day6/expected/memo3.result.json` · `memo4.result.json` — 두 메모의 기대 결과
- 첫 랩에서 만든 memo1 · memo2 결과

## Claude Code에 전달할 요구사항의 뼈대

**첫째, 지금 결과를 따로 둡니다.** 고친 뒤 비교할 기준입니다.

```
mkdir -p work/meeting/before
cp work/meeting/memo1.result.json work/meeting/memo2.result.json work/meeting/before/
```

**둘째, 명세를 먼저 쓰게 합니다.** Skill을 바로 고치게 하지 않습니다.

- **목표**: 변경 명세를 `work/meeting/change_spec.md`에 쓴다.
- **명세에 들어갈 것**
  - 바꿀 것: 담당자 없는 할 일은 `owner`가 `null`, `unassigned`가 `true`. 결과에 `unassigned_todos` 목록을 더한다. 담당자가 있는 할 일은 `unassigned`가 `false`
  - 지킬 것: 예전 메모의 날짜 · 결정사항 · 할 일(`task` · `owner` · `due`)은 그대로다. 담당자를 짐작해서 채우지 않는다
  - 확인할 경우: 상황 · 행동 · 기대 결과로 세 가지 이상(담당자가 모두 있는 메모, 섞인 메모, 예전 메모)
- 명세를 읽고 내가 동의한 뒤에 다음으로 갑니다.

**셋째, 명세대로 고치고 확인합니다.**

- **목표**: 명세대로 Skill을 고치고 memo3 · memo4를 정리한 뒤, memo1 · memo2를 다시 정리한다.
- **완료 기준**: memo3 · memo4 결과가 기대 결과와 같고(할 일의 표현은 달라도 담당자 · 기한 · 표시는 같다), memo1 · memo2는 바꾸기 전과 같다.

## 무엇이 나오면 성공

```
python -m labcheck 6-4
```

- 변경 명세에 바꿀 것 · 지킬 것 · 상황 · 행동 · 기대 결과가 있다
- memo3 · memo4: 담당자 없는 할 일만 표시됐고 `unassigned_todos`에 모두 들어 있다
- memo4: 담당자를 짐작해 채우지 않았다
- memo1 · memo2: 날짜 · 결정사항 · 할 일이 바꾸기 전과 같다

## 다음 랩에서 어떻게 쓰이나

"바꿀 것과 지킬 것을 먼저 적고, 예로 확인한다"는 방식은 마지막 날 종합 랩에서 내 업무를 직접 만들 때 그대로 씁니다.
