# 결과 파일의 꼴

`python run.py rules`가 `output/`에 두 파일을 씁니다. 판단 기능 만들기 실습이 이 꼴을 그대로 읽습니다.

## output/sop.json

- `model`: 쓴 설비 모델의 자리
- `failure_modes`: 고장 유형마다 `id` · `name` · `component` · `causes`(원인의 `id` · `name`)
- `sops`: SOP마다 `id` · `name` · `kind`(원격 조치 · 정비 요청) · `source_section` · `steps`(수행 단계 — 매뉴얼 번호 줄의 `order` · `text` · `line`) ·
  `items`(조건 문장 — `item` 항목 · `refs` 원문 번호 · `text` 원문 인용 · `rules` 옮긴 규칙) · `components` · `assets`(건 설비) · `scope_reason`
- `relations`: 관계마다 `type` · `from` · `to` · `source` · `text`

## output/decision_table.csv

`app/features/decision_table.csv`와 같은 내용입니다. 열 이름과 쓸 수 있는 값은 그 파일 첫 줄에 있습니다.
