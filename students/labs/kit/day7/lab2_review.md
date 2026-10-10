# 7-2 · 검토 에이전트가 근거와 조건을 확인하게 만들기

## 만들 것

추천안을 받아 문제를 찾아 표시하는 검토 프로그램 `work/review.py`, 그리고 두 입력의 검토 결과 `work/day7/review_ok.json` · `review_missing_evidence.json`.

## 왜 만드나

분석 에이전트가 추천 이유를 그럴듯하게 썼더라도, 아무도 출처 · 규정 · 숫자를 확인하지 않으면 잘못된 제안이 그대로 통과합니다. 역할을 나눈다는 것은 결과를 다음 사람에게 넘기는 것만이 아니라, 받은 쪽이 다시 확인하는 것까지를 뜻합니다. 검토는 추천안이 스스로 말하는 내용이 아니라 원래 자료를 기준으로 봅니다.

## 주어지는 자료

- `day7/inputs/case_base.json` — 비교 자료(검토의 기준)
- `day7/inputs/proposal_ok.json` — 정상 추천안
- `day7/inputs/proposal_missing_evidence.json` — 1위 조치의 근거가 빠진 추천안

## Claude Code에 전달할 요구사항의 뼈대

- **목표**: 비교 자료와 추천안을 받아 지적 사항을 찾고 통과 · 반려를 낸다.
- **찾을 것 세 가지**

| 종류 | 무엇인가 |
|---|---|
| 근거 누락 | 순위에 오른 조치에 문서 근거가 없다, 또는 비교 자료에 없는 근거가 적혀 있다 |
| 조건 위반 | 결정표 판정이 제외인 조치가 순위에 있다, 필요한 시간이 작업 가능 시간보다 긴 조치가 순위에 있다, 제어를 실행했다고 적혀 있다 |
| 이유 불일치 | 적힌 순편익이 비교표의 효과 − 비용과 다르다, 적힌 판정이 결정표와 다르다, 순위가 순편익 순서와 다르다, 추천이 1위와 다르다 |

- **출력 모양**: `python work/review.py --case <비교 자료> --proposal <추천안>`

```json
{"case_id": "…", "verdict": "반려", "findings": [{"type": "근거 누락", "action_id": "ACT-…", "detail": "…"}]}
```

  지적이 하나도 없으면 `verdict`는 `통과`, `findings`는 빈 목록.
- **꼭 지킬 것**: 판정 · 효과 · 비용 · 근거는 추천안이 아니라 비교 자료에서 읽어 대조한다.
- **완료 기준**: 정상 추천안은 통과, 근거가 빠진 추천안은 근거 누락으로 반려된다. 두 결과를 `work/day7/`에 저장한다.

```
python work/review.py --case day7/inputs/case_base.json --proposal day7/inputs/proposal_ok.json > work/day7/review_ok.json
python work/review.py --case day7/inputs/case_base.json --proposal day7/inputs/proposal_missing_evidence.json > work/day7/review_missing_evidence.json
```

앞 랩에서 내가 만든 `work/day7/proposal_base.json`도 검토에 넣어 봅니다. 그리고 그 파일의 순편익 숫자 하나를 일부러 고쳐서 검토가 잡는지 봅니다.

## 무엇이 나오면 성공

```
python -m labcheck 7-2
```

- 정상 추천안은 통과한다
- 근거가 빠진 추천안은 근거 누락으로 반려된다
- 제외인 조치를 추천한 추천안, 시간이 모자란 조치를 추천한 추천안은 조건 위반으로 반려된다
- 숫자와 순위가 비교표와 다른 추천안은 이유 불일치로 반려된다
- 지적마다 종류와 설명이 있다

확인은 주어진 두 입력 말고도 준비된 다른 추천안 세 개를 넣어 봅니다.

## 다음 랩에서 어떻게 쓰이나

다음 랩에서는 추천에 필요한 정보(작업 가능 시간)가 아예 비어 있는 경우를 다룹니다. 검토가 틀린 것을 걸러 낸다면, 다음 랩은 모르는 것을 사람에게 묻습니다.
