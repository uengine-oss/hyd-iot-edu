# 결과 파일의 꼴

`python run.py write`가 `output/judgement.json`을 씁니다.

- `criteria`: 쓴 조치 기준의 자리
- `decisions`: 정한 것(1순위로 내줄 기준)과 비교 기준 문장
- `events`: 경보마다
  - `id` · `asset`
  - `candidates`: 조치 후보마다 `sop` · `status`(허용 · 제외) · `hits`(맞은 규칙 — `rule_id` · `result` · `reason` · `source` · `conditions`) ·
    `unknown`(확인되지 않은 조건이 있는 규칙 — `missing`에 값이 빈 입력) · `comparison`(비용 · 생산 · 품질 · 에너지 · 감점 · 비교값, 견주지 않았으면 null) ·
    `not_compared`(값이 없어 견주지 못한 까닭) · `rank`(비교값 순위) · `held_back`(1순위로 내주지 않고 뒤에 보이는 까닭)
  - `not_candidates`: 후보가 아닌 SOP와 까닭
  - `order`: 내줄 차례 · `top`: 1순위로 내줄 후보

## 내 조치 기준을 쓸 때

조치 기준 만들기 실습의 `output/sop.json`과 `output/decision_table.csv`를 `app/features/criteria/`에 함께 복사하면 그 기준으로 판정합니다. 제공 기준 `data/criteria/`는 그대로 둡니다.
